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

import json
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
    """Return today's action_session_for_run(now()) ISO date.

    Used as the reconciliation_run's period_{start,end} for audit rows
    emitted on tamper rejection (plan §A.4.1: WHEN the audit happened).
    Note: post-Codex-R2 the cached-candidate lookup at POST time
    anchors on a hidden form-emitted ``sector_industry_evaluation_run_id``
    (mirroring chart_pattern's anchor pattern), NOT this session date.
    The discrepancy's ``expected.session`` field carries the cached
    candidate's eval_run.action_session_date (matches what the operator
    saw at form-render time), which MAY differ from this value when
    the pipeline is stale.
    """
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
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector_industry_evaluation_run_id=eval_id,
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
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector_industry_evaluation_run_id=eval_id,
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
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector_industry_evaluation_run_id=eval_id,
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
    eval_id, _ = _seed_candidate_with_sector_industry(
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


# =====================================================================
# T-D.2 — On sector mismatch rejection, an ad-hoc system_audit run +
# sector_tamper discrepancy persists (separate transaction; persists
# even though entry POST is rejected).
# =====================================================================


def test_sector_mismatch_emits_system_audit_reconciliation_run(
    seeded_db, monkeypatch,
):
    """Discriminating: pre-T-D.2 the rejection returned 400 with no
    audit-trail emission. Post-fix: a reconciliation_runs row with
    ``source='system_audit'``, ``state='completed'`` is inserted +
    a sector_tamper discrepancy row attached to it.

    The audit emit is in a SEPARATE TRANSACTION from the entry POST
    (which is rejected). Plan §A.4.1: "Discriminating test T-D.2.5:
    assert that after rejection, reconciliation_runs has +1 row AND
    reconciliation_discrepancies has +1 row of type 'sector_tamper'."
    """
    cfg, cfg_path = seeded_db
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector="Technology",  # tampered
            industry="Biotechnology",
            sector_industry_evaluation_run_id=eval_id,
        )
    assert resp.status_code == 400
    conn = connect(cfg.paths.db_path)
    try:
        runs = conn.execute(
            "SELECT run_id, source, state, period_start, period_end "
            "FROM reconciliation_runs"
        ).fetchall()
        discs = conn.execute(
            "SELECT discrepancy_type, field_name, ticker, "
            "expected_value_json, actual_value_json, material_to_review, "
            "trade_id, fill_id "
            "FROM reconciliation_discrepancies"
        ).fetchall()
    finally:
        conn.close()
    assert len(runs) == 1, (
        f"Expected 1 reconciliation_runs row, got {len(runs)}. "
        f"Rows: {runs!r}"
    )
    run_id, source, state, period_start, period_end = runs[0]
    assert source == "system_audit", source
    assert state == "completed", state
    # Plan §A.4.1: period_start = period_end =
    # action_session_for_run(now()) — describes WHEN the audit happened.
    expected_session = _today_action_session_iso()
    assert period_start == expected_session, (period_start, expected_session)
    assert period_end == expected_session, (period_end, expected_session)
    assert len(discs) == 1, (
        f"Expected 1 sector_tamper discrepancy row, got {len(discs)}. "
        f"Rows: {discs!r}"
    )
    (dtype, field_name, ticker, exp_json, act_json, material, trade_id,
     fill_id) = discs[0]
    assert dtype == "sector_tamper", dtype
    assert field_name == "sector", field_name
    assert ticker == "TAMP", ticker
    # Material default is 0 per MATERIAL_BY_TYPE['sector_tamper'] (V1
    # advisory; V2 elevates per spec §3.3.2).
    assert material == 0, material
    # trade_id + fill_id NULL — entry POST was rejected; no trade row
    # exists to attribute the discrepancy to.
    assert trade_id is None, trade_id
    assert fill_id is None, fill_id
    # Spec §3.3.1 JSON shape — expected_value carries cached;
    # actual_value carries form-submitted.
    exp = json.loads(exp_json)
    act = json.loads(act_json)
    assert exp == {
        "sector": "Healthcare",
        "industry": "Biotechnology",
        "session": expected_session,
    }, exp
    assert act == {
        "sector": "Technology",
        "industry": "Biotechnology",
    }, act


# =====================================================================
# T-D.2 — On industry mismatch rejection, ad-hoc audit row carries
# field_name='industry'.
# =====================================================================


def test_industry_mismatch_emits_audit_with_field_name_industry(
    seeded_db, monkeypatch,
):
    """Industry-mismatch audit row carries ``field_name='industry'``
    (separate code path from sector mismatch's ``field_name='sector'``).

    Discriminating: a regression that flattens both paths to a single
    ``field_name='sector'`` would fail here.
    """
    cfg, cfg_path = seeded_db
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector="Healthcare",
            industry="Medical-Devices",  # tampered
            sector_industry_evaluation_run_id=eval_id,
        )
    assert resp.status_code == 400
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT field_name, actual_value_json "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1, rows
    field_name, act_json = rows[0]
    assert field_name == "industry", field_name
    act = json.loads(act_json)
    assert act["industry"] == "Medical-Devices", act


# =====================================================================
# T-D.2 — Sector-first short-circuit when BOTH fields mismatch.
# Recon doc §5: sector wins; field_name='sector'.
# =====================================================================


def test_both_mismatch_short_circuits_to_sector(seeded_db, monkeypatch):
    """When BOTH sector and industry mismatch cached, sector is checked
    first → audit row carries ``field_name='sector'`` and only ONE
    discrepancy row is emitted (not two).

    Discriminating: a regression that emits per-field discrepancies
    (two rows) would fail here.
    """
    cfg, cfg_path = seeded_db
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector="Technology",  # tampered
            industry="Software-Application",  # also tampered
            sector_industry_evaluation_run_id=eval_id,
        )
    assert resp.status_code == 400
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT field_name FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1, (
        f"Expected exactly 1 discrepancy row (sector-first short-circuit); "
        f"got {len(rows)}: {rows!r}"
    )
    assert rows[0][0] == "sector"


# =====================================================================
# T-D.2 — Audit emit's transaction is independent of the entry POST's
# (rejected) transaction. Even if a downstream consumer query under the
# same connection lifecycle fails, the audit row persists.
# =====================================================================


def test_audit_row_persists_across_session_separation(
    seeded_db, monkeypatch,
):
    """The audit row commits via its OWN transaction (separate from
    any record_entry transaction, which is never invoked on rejection).
    A fresh DB connection opened AFTER the rejection sees the row.

    Discriminating: a regression that wraps the audit emit inside a
    transaction-scope that gets rolled back (e.g., re-using a
    deferred-tx connection that the route eventually closes without
    commit) would fail here.
    """
    cfg, cfg_path = seeded_db
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector="Technology",
            industry="Biotechnology",
            sector_industry_evaluation_run_id=eval_id,
        )
    assert resp.status_code == 400
    # Fresh connection — verify the row truly persisted to disk.
    conn = connect(cfg.paths.db_path)
    try:
        run_state = conn.execute(
            "SELECT state FROM reconciliation_runs"
        ).fetchone()
        disc_count = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert run_state is not None, "No reconciliation_runs row found"
    assert run_state[0] == "completed", run_state[0]
    assert disc_count == 1, disc_count


# =====================================================================
# Codex R1 Critical #1 regression coverage — blank-field tamper bypass.
# Pre-fix predicate ``cached_sector and sector and cached_sector !=
# sector`` skipped the check when EITHER side was empty. Post-fix
# strict ``cached_sector != sector`` rejects any deviation, including
# blank-form-vs-non-empty-cached.
# =====================================================================


def test_post_entry_with_blank_sector_vs_non_empty_cached_rejects(
    seeded_db, monkeypatch,
):
    """Tamper-by-blanking: cached sector is non-empty but form posts
    sector="" + industry=correct. Pre-fix this bypassed the check
    silently. Post-fix: rejected (field_name='sector', actual.sector="").
    """
    cfg, cfg_path = seeded_db
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector="",  # blanked
            industry="Biotechnology",
            sector_industry_evaluation_run_id=eval_id,
        )
    assert resp.status_code == 400, (
        f"Expected 400 (blank-sector tamper rejection), got "
        f"{resp.status_code}. Body[:500]: {resp.text[:500]!r}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT field_name, actual_value_json "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchall()
        trade_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert trade_count == 0
    assert len(rows) == 1, rows
    field_name, act_json = rows[0]
    assert field_name == "sector"
    act = json.loads(act_json)
    assert act == {"sector": "", "industry": "Biotechnology"}, act


def test_post_entry_with_blank_industry_vs_non_empty_cached_rejects(
    seeded_db, monkeypatch,
):
    """Symmetric to the sector-blank tamper: form sector matches cached
    + industry posted as "". Cached industry is non-empty → rejected
    on the industry branch.
    """
    cfg, cfg_path = seeded_db
    eval_id, _ = _seed_candidate_with_sector_industry(
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
            sector="Healthcare",
            industry="",  # blanked
            sector_industry_evaluation_run_id=eval_id,
        )
    assert resp.status_code == 400
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT field_name, actual_value_json "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchall()
        trade_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert trade_count == 0
    assert len(rows) == 1, rows
    field_name, act_json = rows[0]
    assert field_name == "industry"
    act = json.loads(act_json)
    assert act == {"sector": "Healthcare", "industry": ""}, act


# =====================================================================
# Codex R1 Major #1 regression coverage — form-render anchor alignment.
# The POST-time cached-candidate lookup must use the SAME anchor as the
# form-render (latest_evaluation_run_id for watchlist origin /
# latest_completed_pipeline_run.evaluation_run_id for hyp-recs). A
# stale-pipeline scenario (today's action_session has NO eval but a
# prior eval exists) must still trigger the tamper check against the
# stale row — pre-fix the today-anchored lookup found nothing and
# silently accepted the tampered POST.
# =====================================================================


def test_stale_pipeline_form_render_anchor_used_at_post(
    seeded_db, monkeypatch,
):
    """Stale-pipeline scenario: today's action_session has NO eval_run
    (the most recent eval is from a prior session). Pre-fix the
    POST-time lookup keyed on today's session found nothing and
    silently accepted any tampered sector/industry. Post-fix: POST
    mirrors form-render's ``latest_evaluation_run_id`` anchor and
    finds the stale row → strict comparison fires.

    Audit row's ``expected.session`` carries the STALE eval's
    action_session_date (the data the operator actually saw), NOT
    today's session. This is the Codex R1 Major #1 alignment fix.
    """
    cfg, cfg_path = seeded_db
    # Seed an eval_run + candidate anchored to a prior session (NOT
    # today). ``action_session_date`` deliberately != today.
    stale_session = "2026-04-01"
    eval_id, _ = _seed_candidate_with_sector_industry(
        cfg.paths.db_path,
        ticker="TAMP",
        sector="Healthcare",
        industry="Biotechnology",
        action_session_iso=stale_session,
    )
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(
            client,
            sector="Technology",  # tampered
            industry="Biotechnology",
            sector_industry_evaluation_run_id=eval_id,
        )
    assert resp.status_code == 400, (
        f"Expected 400 (stale-pipeline tamper rejection), got "
        f"{resp.status_code}. Body[:500]: {resp.text[:500]!r}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        runs = conn.execute(
            "SELECT source, state, period_start, period_end "
            "FROM reconciliation_runs"
        ).fetchall()
        rows = conn.execute(
            "SELECT field_name, expected_value_json, "
            "actual_value_json "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchall()
    finally:
        conn.close()
    assert len(runs) == 1
    source, state, period_start, period_end = runs[0]
    # Run's period_{start,end} are TODAY's action_session per plan §A.4.1
    # — they describe WHEN the audit happened, not the cached data's
    # anchor.
    expected_today = _today_action_session_iso()
    assert source == "system_audit"
    assert state == "completed"
    assert period_start == expected_today, (period_start, expected_today)
    assert period_end == expected_today
    assert len(rows) == 1
    field_name, exp_json, act_json = rows[0]
    assert field_name == "sector"
    exp = json.loads(exp_json)
    # Discrepancy's expected.session reflects the cached candidate's
    # eval_run.action_session_date (stale), NOT today.
    assert exp["session"] == stale_session, (
        f"expected.session must carry the stale eval anchor "
        f"({stale_session!r}); got {exp['session']!r}"
    )
    assert exp["sector"] == "Healthcare"
    act = json.loads(act_json)
    assert act == {"sector": "Technology", "industry": "Biotechnology"}


# =====================================================================
# Codex R2 — explicit anchor + tampered-anchor rejection. A POST that
# supplies an evaluation_run_id which references no candidate row for
# the ticker is itself a tampering signal — reject without emitting an
# audit row (no cached values to attribute the discrepancy against).
# =====================================================================


def test_post_entry_with_tampered_anchor_rejects_without_audit_emit(
    seeded_db, monkeypatch,
):
    """A tampered POST sends ``sector_industry_evaluation_run_id``
    pointing at an eval_id that has NO candidate row for this ticker.
    The route rejects with 400 and emits NO audit row (the anchor is
    forged; there is no cached value to compare against).

    Discriminating: a regression that silently skipped the check on
    "no candidate row found" — accepting the tampered POST as if the
    anchor were the bare-cURL skip path — would let this case slip
    through.
    """
    cfg, cfg_path = seeded_db
    # Seed a candidate for ticker AAA so eval_id is a valid foreign
    # key reference, but it has NO entry for ticker TAMP.
    eval_id, _ = _seed_candidate_with_sector_industry(
        cfg.paths.db_path,
        ticker="AAA",
        sector="Healthcare",
        industry="Biotechnology",
    )
    # Also seed a watchlist row for TAMP so the rerender path has data.
    conn = ensure_schema(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, "
            "last_qualified_date, status, qualification_count, "
            "not_qualified_streak, last_data_asof_date, entry_target, "
            "last_close) VALUES ('TAMP', '2026-04-01', ?, 'watch', "
            "1, 0, ?, 11.0, 10.0)",
            (_today_action_session_iso(), _today_action_session_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(
            client,
            sector="Anything",
            industry="Anything-Else",
            sector_industry_evaluation_run_id=eval_id,  # references AAA, not TAMP
        )
    assert resp.status_code == 400, (
        f"Expected 400 (tampered-anchor rejection), got "
        f"{resp.status_code}. Body[:500]: {resp.text[:500]!r}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        # No audit row — we can't emit a sector_tamper discrepancy
        # without cached values to compare against.
        recon_count = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_runs"
        ).fetchone()[0]
        disc_count = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies"
        ).fetchone()[0]
        trade_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert recon_count == 0, recon_count
    assert disc_count == 0, disc_count
    assert trade_count == 0


def test_post_entry_with_bogus_anchor_pointing_at_nonexistent_eval_rejects(
    seeded_db, monkeypatch,
):
    """A POST that posts an eval_id which doesn't exist in
    evaluation_runs at all → same rejection shape as the tampered
    valid-eval-id case above. No FK violation; no 500; clean 400.
    """
    cfg, cfg_path = seeded_db
    # Seed a watchlist row for TAMP.
    conn = ensure_schema(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, "
            "last_qualified_date, status, qualification_count, "
            "not_qualified_streak, last_data_asof_date, entry_target, "
            "last_close) VALUES ('TAMP', '2026-04-01', ?, 'watch', "
            "1, 0, ?, 11.0, 10.0)",
            (_today_action_session_iso(), _today_action_session_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(
            client,
            sector="Anything",
            industry="Anything-Else",
            sector_industry_evaluation_run_id=999_999,
        )
    assert resp.status_code == 400
    conn = connect(cfg.paths.db_path)
    try:
        recon_count = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_runs"
        ).fetchone()[0]
        trade_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert recon_count == 0
    assert trade_count == 0

