"""Task 4 (tuition-vs-error): correct entry_intent at review (web).

The review form pre-populates the PERSISTED entry_intent (NULL falls back to
the advisory suggestion derived from the hypothesis label). The POST persists
the explicit <select> control via the dedicated ``update_entry_intent`` writer
(server-stamped; 4-tier rejection ladder; empty -> NULL; bad -> 400 + cleared
anchor). The review fields/state ALSO transition via ``complete_trade_review``;
the intent write is a SEPARATE ``with conn:`` (service-tx-nesting gotcha).
"""
from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


def _make_app(
    tmp_path: Path,
    *,
    entry_intent: str | None = None,
    hypothesis_label: str | None = None,
):
    db_path = tmp_path / "task4.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        t1 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-20T09:30:00",
                entry_intent=entry_intent,
                hypothesis_label=hypothesis_label,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-20T09:30:00",
                action="entry", quantity=10.0, price=10.0,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-25T09:30:00",
                action="exit", quantity=10.0, price=11.5, reason="manual",
            ),
            event_ts="2026-04-25T09:30:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t1,))
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


def _intent(app) -> str | None:
    db_path = app.state.cfg.paths.db_path
    return connect(db_path).execute(
        "SELECT entry_intent FROM trades WHERE id=1").fetchone()[0]


def _grades(app):
    db_path = app.state.cfg.paths.db_path
    return connect(db_path).execute(
        "SELECT entry_grade, process_grade, reviewed_at FROM trades WHERE id=1",
    ).fetchone()


def test_review_form_prepopulates_persisted_intent(tmp_path: Path) -> None:
    app = _make_app(tmp_path, entry_intent="standard")
    with TestClient(app) as client:
        r = client.get("/trades/1/review")
    assert r.status_code == 200
    assert 'name="entry_intent"' in r.text
    # The persisted 'standard' option is pre-selected.
    assert 'value="standard" selected' in r.text or (
        'value="standard"' in r.text and "selected" in r.text)


def test_review_form_null_intent_falls_back_to_suggestion(tmp_path: Path) -> None:
    # NULL entry_intent + a by-design hypothesis label -> the suggestion
    # (hypothesis_test_by_design) is the pre-selected default.
    app = _make_app(
        tmp_path, entry_intent=None, hypothesis_label="sub-a+ extension test",
    )
    with TestClient(app) as client:
        r = client.get("/trades/1/review")
    assert r.status_code == 200
    assert 'name="entry_intent"' in r.text
    assert 'value="hypothesis_test_by_design"' in r.text and "selected" in r.text


def test_review_post_persists_intent_via_update_entry_intent(
    tmp_path: Path,
) -> None:
    app = _make_app(tmp_path, entry_intent=None)
    with TestClient(app) as client:
        r = client.post(
            "/trades/1/review",
            data={"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                  "lesson_learned": "clean", "mistake_tags": ["none_observed"],
                  "entry_intent": "standard"},
            headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/reviews/pending"
    # entry_intent persisted via the dedicated writer ...
    assert _intent(app) == "standard"
    # ... AND the review grades/state persisted via complete_trade_review.
    entry_grade, process_grade, reviewed_at = _grades(app)
    assert entry_grade == "A"
    assert process_grade is not None
    assert reviewed_at is not None


def test_review_post_empty_intent_persists_null(tmp_path: Path) -> None:
    app = _make_app(tmp_path, entry_intent=None)
    with TestClient(app) as client:
        r = client.post(
            "/trades/1/review",
            data={"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                  "lesson_learned": "clean", "mistake_tags": ["none_observed"],
                  "entry_intent": ""},
            headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    # The ... or None gotcha: "" -> NULL, not "".
    assert _intent(app) is None


def test_review_post_omitted_intent_preserves_persisted(tmp_path: Path) -> None:
    """Codex R1 Major: a review POST that OMITS entry_intent entirely
    (legacy/bare POST) must PRESERVE the persisted operator-stamped intent
    -- absence != clear (symmetric with the CLI's omitted --entry-intent).
    """
    app = _make_app(tmp_path, entry_intent="standard")
    with TestClient(app) as client:
        r = client.post(
            "/trades/1/review",
            data={"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                  "lesson_learned": "clean", "mistake_tags": ["none_observed"]},
            headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/reviews/pending"
    # The field was absent -> persisted 'standard' is preserved, NOT cleared.
    assert _intent(app) == "standard"
    # The review still completed.
    _, _, reviewed_at = _grades(app)
    assert reviewed_at is not None


def test_review_post_present_empty_clears_persisted(tmp_path: Path) -> None:
    """When entry_intent IS present but empty ("" = operator chose
    Unclassified), the persisted intent is explicitly cleared to NULL."""
    app = _make_app(tmp_path, entry_intent="standard")
    with TestClient(app) as client:
        r = client.post(
            "/trades/1/review",
            data={"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                  "lesson_learned": "clean", "mistake_tags": ["none_observed"],
                  "entry_intent": ""},
            headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    # Present-empty -> explicit clear to NULL.
    assert _intent(app) is None


def test_review_post_bad_intent_rejected_400_and_clears(tmp_path: Path) -> None:
    import inspect
    from swing.web.routes.trades import review_post
    # Discriminator: FastAPI silently ignores an unknown form field, so PRE-
    # Task-4 a bad-intent submit would 204 (param absent). This static gate
    # fails PRE-Task-4 and passes POST.
    assert "entry_intent" in inspect.signature(review_post).parameters
    app = _make_app(tmp_path, entry_intent=None)
    with TestClient(app) as client:
        r = client.post(
            "/trades/1/review",
            data={"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                  "lesson_learned": "clean", "mistake_tags": ["none_observed"],
                  "entry_intent": "foo"},
            headers={"HX-Request": "true"})
    # PRE-FIX: the value reaches the CHECK -> 500. POST-FIX: validated against
    # ENTRY_INTENTS BEFORE the DB -> a clean 400 + re-rendered review form.
    assert r.status_code == 400
    assert 'name="lesson_learned"' in r.text          # form re-rendered
    assert "entry_intent" in r.text.lower() or "entry intent" in r.text.lower()
    # Bad anchor cleared: the rejected "foo" is NOT selected anywhere.
    assert 'value="foo"' not in r.text
    # Nothing persisted (the POST short-circuited before the writers).
    assert _intent(app) is None
    _, _, reviewed_at = _grades(app)
    assert reviewed_at is None
