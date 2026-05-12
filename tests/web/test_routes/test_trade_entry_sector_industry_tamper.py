"""Phase 9 Sub-bundle D — Task D.1 + D.2: sector/industry tamper hardening
at ``POST /trades/entry``.

Mirrors the chart_pattern hardening pattern (commits ``117dc97`` +
``2b9d6f3`` per docs/phase9-bundle-D-task-D0-recon.md). The route-layer
extension:

1. Looks up the cached candidate by ``(ticker, action_session_for_run(now()))``
   joined to ``evaluation_runs.action_session_date``.
2. Compares the form-submitted sector + industry against the cached.
3. On mismatch: rejects with HTTP 400 (HTMX-friendly error fragment)
   AND emits an ad-hoc ``reconciliation_runs`` row (``source='system_audit'``,
   ``state='completed'``) + ``sector_tamper`` discrepancy via Bundle B's
   repo entry points (``insert_run`` + ``insert_discrepancy``).
4. The audit-row INSERT happens in a SEPARATE TRANSACTION before the
   rejection fragment renders, so the audit persists even though the
   entry POST itself never commits its transaction.

TWO discrete code paths per plan §G T-D.1: sector mismatch + industry
mismatch are checked sequentially (sector-first short-circuit).

Discriminating-test discipline: assertions reference exact spec §3.3.1
JSON-shape fields + exact CHECK enum values; substring matches only when
exact-fragment assertion is too brittle for layout shifts.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect, ensure_schema
from swing.evaluation.dates import action_session_for_run
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache_with_snapshot(monkeypatch):
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=10.5, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _today_action_session_iso() -> str:
    """Return the same anchor the route uses for the cached lookup."""
    return action_session_for_run(datetime.now()).isoformat()


def _seed_candidate_with_sector_industry(
    db_path: Path,
    *,
    ticker: str,
    sector: str,
    industry: str,
    action_session_iso: str | None = None,
) -> tuple[int, int]:
    """Seed an evaluation_runs row with action_session_date anchored to
    today's session + a candidate row carrying the given sector/industry.

    Returns ``(evaluation_run_id, candidate_id)``.

    The action_session anchor defaults to ``action_session_for_run(now())``
    so the route's POST-time lookup (which uses that same helper) finds
    the row.
    """
    session = action_session_iso or _today_action_session_iso()
    conn = ensure_schema(db_path)
    try:
        # Seed watchlist row so the form can re-render gracefully on
        # the rejection path (mirrors chart_pattern test pattern).
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, "
            "last_qualified_date, status, qualification_count, "
            "not_qualified_streak, last_data_asof_date, entry_target, "
            "last_close) VALUES (?, '2026-04-01', ?, 'watch', 1, 0, ?, "
            "11.0, 10.0)",
            (ticker, session, session),
        )
        cur = conn.execute(
            "INSERT INTO evaluation_runs (run_ts, data_asof_date, "
            "action_session_date, finviz_csv_path, tickers_evaluated, "
            "aplus_count, watch_count, skip_count, excluded_count, "
            "error_count) VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0)",
            (f"{session}T08:00:00", session, session),
        )
        eval_id = int(cur.lastrowid)
        # Pipeline_runs row links eval -> route's
        # latest_completed_pipeline_run binding (consumed by form-render
        # for the snapshot anchor; happy-path tests need it so the form
        # would have rendered with cached values).
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, finished_ts, trigger, "
            "data_asof_date, action_session_date, state, lease_token, "
            "evaluation_run_id) VALUES (?, ?, 'manual', ?, ?, 'complete', "
            "'tok-d1', ?)",
            (
                f"{session}T08:00:00",
                f"{session}T09:00:00",
                session,
                session,
                eval_id,
            ),
        )
        cand_cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
            "close, pivot, initial_stop, adr_pct, tight_streak, "
            "pullback_pct, prior_trend_pct, rs_rank, rs_return_12w_vs_spy, "
            "rs_method, pattern_tag, notes, sector, industry) "
            "VALUES (?, ?, 'watch', 10.0, 10.0, 9.5, 2.0, 5, NULL, NULL, "
            "NULL, NULL, 'fallback_spy', NULL, NULL, ?, ?)",
            (eval_id, ticker, sector, industry),
        )
        cand_id = int(cand_cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    return eval_id, cand_id


def _post_entry(client, **fields):
    """POST /trades/entry with minimum-valid form merged with overrides."""
    from tests.web.conftest import full_phase7_entry_payload
    base = full_phase7_entry_payload(
        ticker="TAMP",
        entry_date="2026-04-26",
        entry_price="10.0",
        shares="1",
        initial_stop="9.0",
        rationale="aplus-setup",
        notes="",
    )
    base.update({k: ("" if v is None else str(v)) for k, v in fields.items()})
    return client.post(
        "/trades/entry", data=base, headers={"HX-Request": "true"},
    )


# =====================================================================
# T-D.1 — Form sector + industry MATCH cached → entry proceeds.
# Regression-clean: existing chart_pattern hardening still works AND
# sector/industry match path does NOT reject.
# =====================================================================


def test_post_entry_with_matching_sector_industry_proceeds(
    seeded_db, monkeypatch,
):
    """Discriminating: post-T-D.1 the route checks sector/industry against
    the cached candidate. When they match, the route proceeds to
    record_entry. A trade row is inserted; no reconciliation_runs row is
    emitted (no audit needed on the happy path).
    """
    cfg, cfg_path = seeded_db
    _seed_candidate_with_sector_industry(
        cfg.paths.db_path,
        ticker="TAMP",
        sector="Technology",
        industry="Software-Application",
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            sector="Technology",
            industry="Software-Application",
        )
    assert resp.status_code == 200, (
        f"Expected 200 on matching sector/industry, got "
        f"{resp.status_code}. Body[:500]: {resp.text[:500]!r}"
    )
    # Trade row inserted.
    conn = connect(cfg.paths.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
        # NO reconciliation_runs row emitted on the happy path.
        recon_count = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_runs"
        ).fetchone()[0]
        sector_tamper_count = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1, (
        f"Expected 1 trade row, got {count} — happy path must insert."
    )
    assert recon_count == 0, (
        f"Expected 0 reconciliation_runs on happy path, got {recon_count}."
    )
    assert sector_tamper_count == 0, (
        f"Expected 0 sector_tamper discrepancies on happy path, got "
        f"{sector_tamper_count}."
    )


# =====================================================================
# T-D.1 — Form sector mismatches cached → reject 400 (HTMX error frag).
# =====================================================================


def test_post_entry_with_sector_mismatch_rejects_400(
    seeded_db, monkeypatch,
):
    """Discriminating: pre-T-D.1 the route did NOT compare form
    sector/industry against cached; a tampered POST silently persisted.
    Post-fix: sector mismatch returns 400 with a banner referencing
    'sector'; NO trade row inserted.
    """
    cfg, cfg_path = seeded_db
    _seed_candidate_with_sector_industry(
        cfg.paths.db_path,
        ticker="TAMP",
        sector="Healthcare",
        industry="Biotechnology",
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(
            client,
            sector="Technology",  # tampered: doesn't match cached
            industry="Biotechnology",  # matches cached
        )
    assert resp.status_code == 400, (
        f"Expected 400 (sector tamper rejection), got {resp.status_code}. "
        f"Body[:500]: {resp.text[:500]!r}"
    )
    assert "sector" in resp.text.lower(), (
        f"Expected response body to reference 'sector'. "
        f"Body[:500]: {resp.text[:500]!r}"
    )
    # No trade row inserted.
    conn = connect(cfg.paths.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0, (
        f"Expected 0 trade rows on rejection, got {count}."
    )


# =====================================================================
# T-D.1 — Form industry mismatches cached → reject 400 (HTMX error frag).
# Separate code path from sector check (plan §G T-D.1 "TWO discrete tests").
# =====================================================================


def test_post_entry_with_industry_mismatch_rejects_400(
    seeded_db, monkeypatch,
):
    """Discriminating: industry mismatch is a separate code path from
    sector mismatch (sector-first short-circuit means industry only
    fires when sector matches). This test pins the industry-only path:
    form sector matches cached + industry differs → reject 400.
    """
    cfg, cfg_path = seeded_db
    _seed_candidate_with_sector_industry(
        cfg.paths.db_path,
        ticker="TAMP",
        sector="Healthcare",
        industry="Biotechnology",
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(
            client,
            sector="Healthcare",  # matches cached
            industry="Medical-Devices",  # tampered: doesn't match cached
        )
    assert resp.status_code == 400, (
        f"Expected 400 (industry tamper rejection), got {resp.status_code}. "
        f"Body[:500]: {resp.text[:500]!r}"
    )
    assert "industry" in resp.text.lower(), (
        f"Expected response body to reference 'industry'. "
        f"Body[:500]: {resp.text[:500]!r}"
    )
    # No trade row inserted.
    conn = connect(cfg.paths.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


# =====================================================================
# T-D.1 — Backward-compat: empty form sector + industry skip the check.
# CLI / bare cURL callers that don't post the hidden inputs must still
# work (default Form("") values produce empty strings).
# =====================================================================


def test_post_entry_with_empty_sector_industry_skips_tamper_check(
    seeded_db, monkeypatch,
):
    """Backward-compat: an empty form sector AND empty industry (CLI /
    bare cURL caller that doesn't emit the hidden inputs) must NOT
    trigger the tamper check, regardless of whether a cached row exists.

    Plan §G T-D.1 + §A.4 don't explicitly enumerate this case, but the
    chart_pattern hardening precedent (``cp_algo_value is None``
    early-out) is binding. Without this, CLI tests + bare cURL flows
    would break on every test that touches a cached ticker.
    """
    cfg, cfg_path = seeded_db
    _seed_candidate_with_sector_industry(
        cfg.paths.db_path,
        ticker="TAMP",
        sector="Healthcare",
        industry="Biotechnology",
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            sector="",  # empty: bare cURL / CLI caller
            industry="",
        )
    # Entry proceeds with operator-supplied (empty) sector/industry —
    # NO 400 from tamper check.
    assert resp.status_code == 200, (
        f"Expected 200 (backward-compat empty sector/industry), got "
        f"{resp.status_code}. Body[:500]: {resp.text[:500]!r}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1, (
        f"Expected 1 trade row, got {count} — backward-compat path must "
        f"proceed."
    )


# =====================================================================
# T-D.1 — Off-pipeline ticker (no cached candidate) → skip the check.
# Same shape as chart_pattern's ``cp_anchor_value is None`` early-out.
# =====================================================================


def test_post_entry_with_no_cached_candidate_skips_tamper_check(
    seeded_db, monkeypatch,
):
    """When no candidate row exists for (ticker, action_session_for_run(now())),
    the tamper check is SKIPPED and the entry proceeds with operator-
    supplied sector/industry values. Backward-compat for off-pipeline /
    fresh-install / mid-walk-DB scenarios.

    Discriminating: this test seeds NO candidate row. Pre-fix and
    post-fix both return 200 (entry proceeds). Pre-fix because the
    route never compared anything; post-fix because the lookup yields
    no row and the check is gated. The discriminator is the absence of
    a 400 + audit row — covered by the rejection tests above.
    """
    cfg, cfg_path = seeded_db
    # Seed only a watchlist row (no candidate / evaluation_run).
    session = _today_action_session_iso()
    conn = ensure_schema(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, "
            "last_qualified_date, status, qualification_count, "
            "not_qualified_streak, last_data_asof_date, entry_target, "
            "last_close) VALUES ('TAMP', '2026-04-01', ?, 'watch', 1, "
            "0, ?, 11.0, 10.0)",
            (session, session),
        )
        conn.commit()
    finally:
        conn.close()
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            sector="Anything",
            industry="Anything-Else",
        )
    assert resp.status_code == 200, (
        f"Expected 200 (no cached candidate → skip check), got "
        f"{resp.status_code}. Body[:500]: {resp.text[:500]!r}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
        recon_count = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_runs"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1
    assert recon_count == 0, (
        f"Expected 0 audit rows when no cached candidate exists; got "
        f"{recon_count}."
    )


# T-D.2 audit-emit tests are added in the T-D.2 commit (mirrored on
# this same file per dispatch brief §0.4 + plan §G T-D.2 file map).

