"""Phase 5 Task 5.3 + 5.4 — trade-entry form template renders the Chart
Pattern section (algo display + override dropdown + hidden snapshot
inputs) when a cached classification exists, and the "Not classified"
stub when it doesn't; POST /trades/entry reads the new form fields and
builds an EntryRequest carrying the snapshot.

Spec §3.6 form fragment. The Chart Pattern section lives in its own
shared include partial (``partials/trade_entry_chart_pattern_section.html.j2``)
per CLAUDE.md HTMX OOB-swap discipline — any future row-reload OOB-swap
path that re-renders this section will reach the same markup, no
hand-duplication.

Assertions use exact fragments (per discriminating-test discipline +
2026-04-26 lesson: substring-match assertions almost never distinguish
pre-fix from post-fix on rendered HTML). Each fragment is a complete,
unambiguous element so a regression that drops an attribute, changes
the option value, or swaps element nesting will fail.
"""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect, ensure_schema
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot

from ..test_view_models._pattern_classification_seed import (
    seed_pipeline_with_classification,
)


def _patch_price_cache(monkeypatch):
    """Stub PriceCache so the route doesn't try to fetch prices."""
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_entry_form_renders_chart_pattern_section_when_evaluated(
    seeded_db, monkeypatch,
):
    """Discriminating: pre-Task-5.3, the form template doesn't reference
    chart_pattern_* fields so none of these tokens render. Post-fix:
    hidden snapshot inputs + override dropdown are present.
    """
    cfg, cfg_path = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Hidden snapshot inputs — exact fragments.
    assert (
        '<input type="hidden" name="chart_pattern_algo" value="flag">'
        in body
    )
    assert (
        '<input type="hidden" name="chart_pattern_algo_confidence" '
        'value="0.78">'
        in body
    )
    assert (
        '<input type="hidden" name="chart_pattern_classification_pipeline_run_id" '
        f'value="{run_id}">'
        in body
    )

    # Override dropdown options — exact fragments.
    assert '<option value="">Accept algo</option>' in body
    assert '<option value="flag">flag</option>' in body
    assert '<option value="none">none</option>' in body
    assert '<option value="other">other (specify)</option>' in body
    # Free-text companion input for "other".
    assert 'name="chart_pattern_operator_other"' in body

    # Algo display fragment — exact "<strong>flag</strong> (0.78)".
    assert "<strong>flag</strong> (0.78)" in body


def test_entry_form_renders_not_classified_stub_when_unevaluated(
    seeded_db, monkeypatch,
):
    """Compounding-confound: with a watchlist row but NO classification,
    the override surface must NOT render — the operator should not be
    able to submit a value the CLI parity gate would have refused.

    Discriminating: post-Task-5.3 the stub fragment text shows up, and
    the override dropdown is structurally absent. With the algo-display
    dropdown structurally tied to ``chart_pattern_algo_evaluated``, this
    catches a regression that renders the dropdown unconditionally.
    """
    cfg, cfg_path = seeded_db
    # Seed a watchlist row for NOPE but NO classification.
    conn = ensure_schema(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, last_qualified_date, "
            "status, qualification_count, not_qualified_streak, "
            "last_data_asof_date, entry_target, last_close) "
            "VALUES ('NOPE', '2026-04-01','2026-04-26','watch',1,0,"
            "'2026-04-25',110.0,100.0)"
        )
        conn.commit()
    finally:
        conn.close()
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=NOPE")
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert (
        '<div class="subtitle">Not classified '
        "(out-of-scope or no recent pipeline run).</div>"
    ) in body
    # Override dropdown MUST NOT appear when unevaluated (cached-only
    # consumption gate's UI half — the CLI half is Task 5.5).
    assert 'name="chart_pattern_operator"' not in body
    # Hidden algo input also absent (no snapshot to flow).
    assert 'name="chart_pattern_algo"' not in body


# ---------------------------------------------------------------------
# Task 5.4 — POST /trades/entry persists the chart_pattern snapshot.
# ---------------------------------------------------------------------


def _seed_aapl_watchlist(cfg) -> None:
    """Seed an AAPL watchlist row so build_entry_form_vm can re-render
    the form on the refusal path. Mirrors test_post_entry_success_emits_row_and_oobs."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()


def _patch_price_cache_with_snapshot(monkeypatch):
    """Stub PriceCache to return a usable snapshot for AAPL POST flows."""
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _post_entry(client, **fields):
    """POST /trades/entry with minimum-valid form merged with overrides.

    Empty-string values flow through as the form would actually post (the
    HTML form sends ``value=""`` for hidden inputs of None values).
    """
    base = {
        "ticker": "AAPL",
        "entry_date": "2026-04-26",
        "entry_price": "10.0",
        "shares": "1",
        "initial_stop": "9.0",
        "rationale": "aplus-setup",
        "notes": "",
    }
    base.update({k: ("" if v is None else str(v)) for k, v in fields.items()})
    return client.post(
        "/trades/entry", data=base, headers={"HX-Request": "true"},
    )


def test_post_entry_with_chart_pattern_override_persists(seeded_db, monkeypatch):
    """POST with hidden snapshot inputs + operator='flag' override
    persists all four columns to the trades row.

    Discriminating: pre-Task-5.4 the route doesn't accept the new
    fields, so the columns stay NULL. Post-fix: ('flag', 0.78, 'flag',
    run_id) round-trip via INSERT.
    """
    cfg, cfg_path = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL", pattern="flag", confidence=0.78,
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence="0.78",
            chart_pattern_classification_pipeline_run_id=str(run_id),
            chart_pattern_operator="flag",
        )
    assert resp.status_code == 200, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT chart_pattern_algo, chart_pattern_algo_confidence, "
            "chart_pattern_operator, chart_pattern_classification_pipeline_run_id "
            "FROM trades WHERE ticker='AAPL'"
        ).fetchone()
    finally:
        conn.close()
    assert row == ("flag", 0.78, "flag", run_id)


def test_post_entry_with_accept_algo_persists_NULL_operator(seeded_db, monkeypatch):
    """Operator chooses "Accept algo" (empty option value) → operator
    column persists NULL while the algo snapshot still lands."""
    cfg, cfg_path = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL", pattern="flag", confidence=0.78,
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence="0.78",
            chart_pattern_classification_pipeline_run_id=str(run_id),
            chart_pattern_operator="",  # Accept algo
        )
    assert resp.status_code == 200, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT chart_pattern_algo, chart_pattern_algo_confidence, "
            "chart_pattern_operator, chart_pattern_classification_pipeline_run_id "
            "FROM trades WHERE ticker='AAPL'"
        ).fetchone()
    finally:
        conn.close()
    # algo + audit anchor both land; operator NULL.
    assert row == ("flag", 0.78, None, run_id)


def test_post_entry_other_with_text_canonicalizes(seeded_db, monkeypatch):
    """Operator submits 'other' + free-text with embedded ZWSP/tab —
    canonicalize_hypothesis_label strips invisibles per spec §3.6.

    Discriminating: the raw input ``"  pennant​\t  "`` has a
    leading space, an embedded zero-width space (U+200B), and a tab
    + trailing whitespace. Post-canonicalization → ``"pennant"``.
    """
    cfg, cfg_path = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL", pattern="flag", confidence=0.78,
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence="0.78",
            chart_pattern_classification_pipeline_run_id=str(run_id),
            chart_pattern_operator="other",
            chart_pattern_operator_other="  pennant​\t  ",
        )
    assert resp.status_code == 200, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT chart_pattern_operator FROM trades WHERE ticker='AAPL'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "pennant"


def test_post_entry_with_tampered_form_returns_400_with_error_banner(
    seeded_db, monkeypatch,
):
    """Code-review I1 — hidden-form-field tampering must NOT bubble a
    generic 500.

    Plan §Task 5.4 (lines 3801-3802) explicitly anticipated this:
    ``record_entry`` re-validates the chart_pattern invariant via
    ``_validate_chart_pattern_invariant`` and raises ``ValueError`` when
    a tampered POST passes the route's cached-only gate but violates the
    cross-column rule. The route must catch that ValueError and re-render
    the form with a 400 banner, mirroring the SoftWarn / Duplicate /
    HardCap handlers.

    Tampered scenario: ``chart_pattern_algo='flag'`` + valid run_id
    (cached-only gate accepts it because ``cache_evaluated`` is True with
    algo+anchor non-NULL) + ``chart_pattern_algo_confidence=''`` (coerces
    to ``None``). The invariant ``algo='flag' requires confidence
    NOT NULL`` then fires inside ``record_entry``.

    Discriminating: pre-fix the route does NOT catch ValueError →
    TestClient with ``raise_server_exceptions=False`` records a 500;
    post-fix the route catches it, re-renders the form, returns 400 with
    a banner referencing ``chart_pattern``. Asserts no trade row was
    inserted in either case (record_entry's ``with conn:`` rolls back).
    """
    cfg, cfg_path = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL", pattern="flag", confidence=0.78,
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(
            client,
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence="",  # tampered: empty → None
            chart_pattern_classification_pipeline_run_id=str(run_id),
            chart_pattern_operator="",  # Accept algo (no override)
        )
    # Post-fix: 400 (re-rendered form). Pre-fix: 500 (unhandled ValueError).
    assert resp.status_code == 400, (
        f"Expected 400 (chart_pattern invariant re-render), got "
        f"{resp.status_code}. Body[:500]: {resp.text[:500]!r}"
    )
    # Banner text must reference chart_pattern (substring of the invariant
    # message raised by _validate_chart_pattern_invariant).
    assert "chart_pattern" in resp.text, (
        "Response body must contain the invariant message (substring "
        f"'chart_pattern'). Body[:500]: {resp.text[:500]!r}"
    )
    # No trade row inserted (transaction rolled back / never started).
    conn = connect(cfg.paths.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='AAPL'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_post_entry_refuses_operator_override_when_no_cache(seeded_db, monkeypatch):
    """Cached-only consumption gate (spec §1.1 #5 + §3.7 R1 C1) — POST
    mirrors CLI refusal. No trade row inserted.

    Compounding-confound: include a watchlist row (so the form would
    re-render gracefully) but NO classification row. The refusal must
    fire on the (operator submitted, no cache snapshot) condition,
    NOT the absence of a watchlist row.
    """
    cfg, cfg_path = seeded_db
    _seed_aapl_watchlist(cfg)
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            chart_pattern_algo="",
            chart_pattern_algo_confidence="",
            chart_pattern_classification_pipeline_run_id="",
            chart_pattern_operator="flag",  # operator submitted override w/o cache
        )
    assert resp.status_code == 400, resp.text
    assert "Chart-pattern override requires a cached classification" in resp.text
    conn = connect(cfg.paths.db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    finally:
        conn.close()
    assert count == 0
