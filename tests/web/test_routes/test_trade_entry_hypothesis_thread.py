"""Phase 4.5 — POST /trades/entry threads hypothesis_label through to
record_entry; ToCToU snapshot-trust; soft-warn confirm round-trip
preserves the snapshot AS-IS through fragment-faithful resubmit;
rationale-fail re-render preserves resolved label.

Discriminating tests use a UNIQUE non-matcher SNAPSHOT_TEST_LABEL so
three-way discrimination is observable:
  - bug A (no thread):           persisted = NULL
  - bug B (route re-resolves):   persisted = matcher's "A+ baseline (aplus)"
  - bug C (form_values omits / misspells in soft-warn): NULL after force
  - fix:                         persisted = SNAPSHOT_TEST_LABEL
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app
from tests.web.conftest import full_phase7_entry_payload
from swing.web.price_cache import PriceCache, PriceSnapshot

# Phase 4.5 — load-bearing constant for snapshot-trust discrimination.
# Plain ASCII, single-spaced, no Cf/Cc → canonicalize_hypothesis_label
# returns it unchanged. Distinct from any matcher output (matcher labels
# always begin with one of "A+ baseline" / "Near-A+ defensible: extension
# test" / "Sub-A+ VCP-not-formed" / "Capital-blocked: smaller-position
# test"). See plan §"Matcher output for the seed fixture".
SNAPSHOT_TEST_LABEL = (
    "Phase 4.5 snapshot test label - matcher does not emit this string"
)


def _seed_aplus_pipeline(db_path: Path, ticker: str) -> None:
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def _read_persisted_hypothesis_label(db_path: Path, ticker: str) -> str | None:
    """Read the most-recent trade row for ticker; return its
    hypothesis_label (or None if no row)."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT hypothesis_label FROM trades WHERE ticker = ? "
            "ORDER BY id DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()


def _parse_hidden_inputs(html: str) -> dict[str, str]:
    """Extract every <input type="hidden" name="..." value="..."> tag
    into a dict. Mirrors what a real browser would submit for the form
    that contains the parsed fragment (Codex R1 Major 1: the soft-warn
    round-trip MUST replay the server's actual hidden-input names, not
    a hand-crafted set that masks misspellings).

    Coupling acknowledgment (Codex R2 Minor 1): the regex pins the
    expected Jinja2 emission shape — `type="hidden"` first, then
    `name="..."`, then `value="..."`, double-quoted, single ASCII
    space between attributes. soft_warn_confirm.html.j2 emits exactly
    this shape (see lines 32-36 of that template). If a future template
    change reorders attributes or switches quoting, this helper will
    silently miss inputs and the round-trip test will fail with a
    confusing "missing key" error rather than a clean signal. That is
    an acceptable maintenance cost for V1 — the alternative is parsing
    HTML with a real DOM library, which adds a test dependency that
    isn't justified at this scope. Document this coupling near
    soft_warn_confirm.html.j2 if a reviewer asks; do not add a
    backwards-compatibility shim here.
    """
    return dict(re.findall(
        r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
        html,
    ))


def test_post_entry_snapshot_trust_persists_operator_submitted_label(
    seeded_db, monkeypatch,
):
    """Discriminating snapshot-trust (per Codex R1 Major 2 + Major 3).

    POST with hypothesis_label=SNAPSHOT_TEST_LABEL (a string the
    matcher would never emit) for AAPL (which has an active A+
    recommendation; matcher would emit "A+ baseline (aplus)" if
    re-resolved at submit time). Persisted value MUST equal the
    operator-submitted snapshot, NOT the matcher's current output.

    Three-way discrimination:
    - Bug A (no Form param / no thread): persisted = NULL → fails.
    - Bug B (route re-resolves at submit): persisted = "A+ baseline
      (aplus)" ≠ SNAPSHOT_TEST_LABEL → fails.
    - Fix: persisted = SNAPSHOT_TEST_LABEL → passes.
    """
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_post = client.post("/trades/entry", data=full_phase7_entry_payload(
            ticker="AAPL",
            entry_date="2026-04-15",
            entry_price="180.0",
            shares="1",
            initial_stop="170.0",
            rationale="aplus-setup",
            hypothesis_label=SNAPSHOT_TEST_LABEL,
            sector="",
            industry="",
            origin="watchlist",
        ), headers={"HX-Request": "true"})
        assert r_post.status_code in (200, 201, 302), r_post.text

    persisted = _read_persisted_hypothesis_label(cfg.paths.db_path, "AAPL")
    assert persisted == SNAPSHOT_TEST_LABEL, (
        "snapshot-at-entry-surface contract: persisted hypothesis_label "
        f"must equal the operator-submitted snapshot exactly; got {persisted!r}"
    )


def test_post_entry_persists_NULL_for_non_matching_ticker(
    seeded_db, monkeypatch,
):
    """Effective-contract pin (brief §4.11). Empty-string-→-None-→-NULL
    chain through the route boundary's `or None` coercion plus
    record_entry's canonicalize_hypothesis_label.

    Note: this test does NOT discriminate "thread vs no-thread" (both
    bug-present and bug-fixed persist NULL on a no-match POST). Its
    purpose is to PIN the no-match contract going forward and catch a
    regression where future code persisted a non-NULL placeholder
    (e.g., persisted "" instead of NULL).
    """
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "ZZZ": PriceSnapshot(
                ticker="ZZZ", price=100.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_post = client.post("/trades/entry", data=full_phase7_entry_payload(
            ticker="ZZZ",
            entry_date="2026-04-15",
            entry_price="100.0",
            shares="1",
            initial_stop="90.0",
            rationale="vcp-breakout",
            hypothesis_label="",
            sector="",
            industry="",
            origin="watchlist",
        ), headers={"HX-Request": "true"})
        assert r_post.status_code in (200, 201, 302), r_post.text

    persisted = _read_persisted_hypothesis_label(cfg.paths.db_path, "ZZZ")
    assert persisted is None, (
        f"non-matching ticker must persist NULL hypothesis_label; got {persisted!r}"
    )


def test_post_entry_soft_warn_round_trip_via_fragment_faithful_resubmit(
    seeded_db, monkeypatch,
):
    """Discriminating soft-warn round-trip (per Codex R1 Major 1 +
    Major 2). With soft_warn_open exceeded:

    1. First POST submits hypothesis_label=SNAPSHOT_TEST_LABEL.
    2. Server returns the soft-warn confirm fragment.
    3. Test PARSES the fragment's hidden inputs (does NOT hand-craft);
       this catches misspellings or omissions of any field name.
    4. Test submits the parsed dict + force=true.
    5. Asserts persisted == SNAPSHOT_TEST_LABEL.

    Bug A (form_values omits hypothesis_label): fragment lacks the
    hidden input; parsed dict has no `hypothesis_label` key; second POST
    submits without it; route's `Form("")` default → `or None` → NULL
    persisted → fails.
    Bug B (form_values misspells the key): fragment emits
    name="hypothesis" (not "hypothesis_label"); the route's Form param
    receives the default ""; persisted = NULL → fails. (Hand-crafted
    second POST would mask this; fragment-faithful resubmit exposes it.)
    Bug C (route re-resolves at submit): persisted = "A+ baseline
    (aplus)" ≠ SNAPSHOT_TEST_LABEL → fails.
    Fix: persisted = SNAPSHOT_TEST_LABEL → passes.
    """
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")

    # Trip soft-warn (default soft_warn_open=4) by seeding 4 unrelated
    # open trades.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for t in ("MSFT", "NVDA", "AMD", "TSLA"):
                insert_trade_with_event(
                    conn,
                    Trade(
                        id=None, ticker=t, entry_date="2026-04-10",
                        entry_price=100.0, initial_shares=1,
                        initial_stop=90.0, current_stop=90.0,
                        state="entered",
                        watchlist_entry_target=None,
                        watchlist_initial_stop=None,
                        notes=None,
                    ),
                    event_ts="2026-04-10T09:30:00",
                )
    finally:
        conn.close()

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # First POST → soft-warn confirm fragment.
        r_first = client.post("/trades/entry", data=full_phase7_entry_payload(
            ticker="AAPL",
            entry_date="2026-04-15",
            entry_price="180.0",
            shares="1",
            initial_stop="170.0",
            rationale="aplus-setup",
            hypothesis_label=SNAPSHOT_TEST_LABEL,
            sector="",
            industry="",
            origin="watchlist",
        ), headers={"HX-Request": "true"})
        assert r_first.status_code == 200
        # Pre-flight: confirm fragment carries the operator's snapshot
        # AS-IS in a hidden input named exactly "hypothesis_label".
        assert (
            f'name="hypothesis_label" value="{SNAPSHOT_TEST_LABEL}"'
            in r_first.text
        ), (
            "soft-warn confirm fragment must emit hypothesis_label hidden "
            f"input with snapshot value; first response: {r_first.text!r}"
        )

        # Fragment-faithful resubmit (Codex R1 Major 1): parse the
        # fragment's hidden inputs verbatim; submit them + force=true.
        # This is what a real browser does when the operator clicks
        # "Submit anyway" on the confirm form.
        fragment_data = _parse_hidden_inputs(r_first.text)
        assert fragment_data.get("hypothesis_label") == SNAPSHOT_TEST_LABEL, (
            f"fragment must carry hypothesis_label key; got {fragment_data!r}"
        )
        fragment_data["force"] = "true"

        r_second = client.post(
            "/trades/entry", data=fragment_data,
            headers={"HX-Request": "true"},
        )
        assert r_second.status_code in (200, 201, 302), r_second.text

    persisted = _read_persisted_hypothesis_label(cfg.paths.db_path, "AAPL")
    assert persisted == SNAPSHOT_TEST_LABEL, (
        "post-force-submit DB row MUST carry the operator's snapshot "
        f"(soft-warn round-trip preservation); got {persisted!r}"
    )


def test_post_entry_rationale_fail_re_render_preserves_resolved_label(
    seeded_db, monkeypatch,
):
    """Re-render preservation (brief §3.E final bullet). A rationale-
    validation failure (rationale='other' without notes) returns 400 +
    re-rendered form. The rebuild path calls build_entry_form_vm,
    which re-resolves the matcher deterministically; the response must
    carry name="hypothesis_label" value="A+ baseline (aplus)" exactly.

    Bug (build_entry_form_vm regressed on resolution): re-render's
    hidden-input value is empty or stale → fails.
    Bug (re-render path stops calling build_entry_form_vm): re-render
    lacks the field entirely → fails.

    Note: this test does not depend on Task 4's Form-param edits to
    pass — the rationale-fail path runs before the EntryRequest
    construction. After Task 3 the test would already pass; we co-locate
    it in Task 4 for thematic grouping with the other POST-level
    integration tests (per Codex R1 Major 4 consolidation).
    """
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Test discriminates the rationale=other ⇒ notes-required guard;
        # omit `notes` (helper supplies a default that would mask the gate).
        payload = full_phase7_entry_payload(
            ticker="AAPL",
            entry_date="2026-04-15",
            entry_price="180.0",
            shares="1",
            initial_stop="170.0",
            rationale="other",
            hypothesis_label=SNAPSHOT_TEST_LABEL,  # arbitrary input value
            sector="",
            industry="",
            origin="watchlist",
        )
        del payload["notes"]
        r_fail = client.post("/trades/entry", data=payload,
                              headers={"HX-Request": "true"})
        assert r_fail.status_code == 400, r_fail.text
        # Re-render's hidden input carries the matcher-RE-RESOLVED label
        # (NOT the operator's submitted SNAPSHOT_TEST_LABEL). The
        # rationale-fail path goes through build_entry_form_vm, which
        # re-resolves deterministically; per snapshot-at-entry-surface
        # decision §2.4, this re-resolve is correct because the DB state
        # has not changed and the matcher is pure.
        assert (
            'name="hypothesis_label" value="A+ baseline (aplus)"'
            in r_fail.text
        ), (
            "rationale-fail re-render must carry matcher-resolved label "
            f"in hidden input; response: {r_fail.text!r}"
        )
