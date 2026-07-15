"""Arc 20-C (D24) — the equity_delta diagnostic view.

The cash-coherence badge used to light on an unresolved equity_delta with NO
destination (the dead ``<span>`` at status_strip.html.j2:24 — a call-to-action
with no action). This read-only diagnostic view is that destination: it shows
the OOF-NETTED breakdown (ledger current_equity vs broker NLV vs Sigma declared
OOF MV vs swing-NLV vs the netted delta) and routes the operator to the DATA
FIX (journal oof-buy / the cash paths / the forensic-decomposition playbook).

Display-basis LOCK (RD's banked stored-vs-emit note): the DISPLAYED delta is
OOF-NETTED (ledger - swing_nlv); the RAW ``reconciliation_runs.equity_delta_
dollars`` (ledger - source_nlv, OOF-INCLUSIVE) is shown ONLY when explicitly
labeled raw. A future reader must never consume the raw field un-netted.

Distinguishing arithmetic (feedback_regression_test_arithmetic): with
ledger=1544.86, source_nlv=2010.70, declared_oof_mv=454.90, swing_nlv=1555.80
the NETTED delta is -10.94 (the real residual) while the RAW OOF-inclusive gap
is -465.84. A view that displayed the raw field as the headline delta would
surface -465.84 (~the declared MV) — the false-drift the netting exists to
kill. So the presence of -10.94 as the netted delta AND -465.84 only under a
raw label distinguishes the correct (netted) display from the wrong (raw) one.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app

_DIAGNOSTIC_PATH = "/reconcile/equity-delta"


def _seed_swing_scoped_equity_delta(
    db_path: Path,
    *,
    ledger: float = 1544.86,
    source_nlv: float = 2010.70,
    declared_oof_mv: float = 454.90,
    swing_nlv: float = 1555.80,
    resolution: str = "unresolved",
) -> int:
    """Seed a completed schwab_api run + a swing-scoped equity_delta row.

    The run's ``equity_delta_dollars`` column is stamped RAW (ledger minus
    source_nlv, OOF-INCLUSIVE) per the production writer; the discrepancy's
    ``actual_value_json`` carries the netted breakdown per the swing-scoped
    fire path.
    """
    raw_delta = round(ledger - source_nlv, 2)
    conn = sqlite3.connect(str(db_path))
    try:
        rcur = conn.execute(
            "INSERT INTO reconciliation_runs (source, state, started_ts, "
            "finished_ts, period_start, period_end, "
            "account_equity_journal_dollars, account_equity_source_dollars, "
            "equity_delta_dollars) VALUES ('schwab_api', 'completed', '1', "
            "'2', '2026-05-01', '2026-05-31', ?, ?, ?)",
            (ledger, source_nlv, raw_delta),
        )
        run_id = int(rcur.lastrowid)
        import json

        expected = json.dumps(
            {"equity_dollars": ledger, "basis": "ledger"}, sort_keys=True
        )
        actual = json.dumps(
            {
                "equity_dollars": swing_nlv,
                "swing_nlv": swing_nlv,
                "source_nlv": source_nlv,
                "declared_oof_mv": declared_oof_mv,
                "basis": "net_liq_minus_declared_oof",
            },
            sort_keys=True,
        )
        netted_delta = round(ledger - swing_nlv, 2)
        dcur = conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, field_name, expected_value_json, "
            "actual_value_json, delta_text, material_to_review, created_at, "
            "resolution) VALUES (?, 'equity_delta', 'net_liquidating_value', "
            "?, ?, ?, 1, '2026-05-31T12:00:00', ?)",
            (
                run_id,
                expected,
                actual,
                f"${netted_delta:+.2f} (ledger minus swing_nlv)",
                resolution,
            ),
        )
        disc_id = int(dcur.lastrowid)
        conn.commit()
        return disc_id
    finally:
        conn.close()


def test_diagnostic_renders_netted_breakdown(seeded_db: tuple[Config, Path]):
    cfg, cfg_path = seeded_db
    _seed_swing_scoped_equity_delta(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(_DIAGNOSTIC_PATH)
    assert r.status_code == 200, r.text[:400]
    body = r.text
    # Netted breakdown lines (each labeled).
    assert "1544.86" in body  # ledger current_equity
    assert "2010.70" in body  # broker NLV (raw source)
    assert "454.90" in body  # Sigma declared-OOF MV
    assert "1555.80" in body  # swing-NLV (netted)
    # The DISPLAYED headline delta is NETTED (-10.94), NOT the raw -465.84.
    assert "-10.94" in body
    # The raw OOF-inclusive field is present ONLY under a raw label.
    assert "-465.84" in body
    assert "OOF-inclusive" in body or "OOF inclusive" in body


def test_diagnostic_netted_delta_is_not_the_raw_headline(
    seeded_db: tuple[Config, Path],
):
    """The netted delta and the raw delta both appear, but the raw one must be
    labeled raw/OOF-inclusive — never surfaced as the primary delta."""
    cfg, cfg_path = seeded_db
    _seed_swing_scoped_equity_delta(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(_DIAGNOSTIC_PATH)
    assert r.status_code == 200, r.text[:400]
    # A data attribute pins the netted headline for a stable assertion.
    assert 'data-netted-delta="-10.94"' in r.text


def test_diagnostic_routes_to_the_data_fix(seeded_db: tuple[Config, Path]):
    """THE PRINCIPLE: a coherence finding routes to the DATA FIX, not a
    bail-water button. The view must cite the three data-fix paths."""
    cfg, cfg_path = seeded_db
    _seed_swing_scoped_equity_delta(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(_DIAGNOSTIC_PATH)
    body = r.text
    assert "journal oof-buy" in body
    assert "broker-ledger-forensic-reconciliation-2026-07-10.md" in body


def test_diagnostic_graceful_when_no_active_finding(
    seeded_db: tuple[Config, Path],
):
    """No unresolved equity_delta on the latest run -> a graceful empty state
    (200, not 404/500)."""
    cfg, cfg_path = seeded_db
    _seed_swing_scoped_equity_delta(
        cfg.paths.db_path, resolution="acknowledged_immaterial"
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(_DIAGNOSTIC_PATH)
    assert r.status_code == 200, r.text[:400]
    assert "no active equity delta" in r.text.lower()


def _seed_raw_equity_delta_envelopes(
    db_path: Path, *, expected_json: str, actual_json: str,
) -> None:
    """Seed a completed run + an unresolved equity_delta with ARBITRARY raw
    envelope strings via raw INSERT (bypassing the dataclass validator — the
    reachable malformed / legacy case; insert_discrepancy is a raw INSERT)."""
    conn = sqlite3.connect(str(db_path))
    try:
        rcur = conn.execute(
            "INSERT INTO reconciliation_runs (source, state, started_ts, "
            "finished_ts, period_start, period_end, equity_delta_dollars) "
            "VALUES ('schwab_api', 'completed', '1', '2', '2026-05-01', "
            "'2026-05-31', -5.0)",
        )
        run_id = int(rcur.lastrowid)
        conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, field_name, expected_value_json, "
            "actual_value_json, delta_text, material_to_review, created_at, "
            "resolution) VALUES (?, 'equity_delta', 'net_liquidating_value', "
            "?, ?, 'x', 1, '2026-05-31', 'unresolved')",
            (run_id, expected_json, actual_json),
        )
        conn.commit()
    finally:
        conn.close()


def test_diagnostic_degrades_on_malformed_json(seeded_db: tuple[Config, Path]):
    """A malformed JSON envelope (reachable via raw INSERT / legacy row) must
    render 200 (graceful), NOT 500 — the get_discrepancy dataclass validator
    would have raised (Codex R1 MAJOR)."""
    cfg, cfg_path = seeded_db
    _seed_raw_equity_delta_envelopes(
        cfg.paths.db_path, expected_json="{not json", actual_json="also broken",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(_DIAGNOSTIC_PATH)
    assert r.status_code == 200, r.text[:400]


def test_diagnostic_degrades_on_nan_constant(seeded_db: tuple[Config, Path]):
    """A JSON NaN constant (which the dataclass validator rejects on read)
    must render 200, not 500."""
    cfg, cfg_path = seeded_db
    _seed_raw_equity_delta_envelopes(
        cfg.paths.db_path,
        expected_json='{"equity_dollars": NaN, "basis": "ledger"}',
        actual_json='{"equity_dollars": NaN, "basis": "net_liq"}',
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(_DIAGNOSTIC_PATH)
    assert r.status_code == 200, r.text[:400]


def test_diagnostic_legacy_net_liq_basis(seeded_db: tuple[Config, Path]):
    """On the legacy (nothing-declared) net_liq basis, swing_nlv == source_nlv
    and declared_oof_mv is 0 — the netted delta equals the raw delta and the
    view still renders."""
    cfg, cfg_path = seeded_db
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        import json

        rcur = conn.execute(
            "INSERT INTO reconciliation_runs (source, state, started_ts, "
            "finished_ts, period_start, period_end, "
            "account_equity_journal_dollars, account_equity_source_dollars, "
            "equity_delta_dollars) VALUES ('schwab_api', 'completed', '1', "
            "'2', '2026-05-01', '2026-05-31', 1000.0, 1020.0, -20.0)",
        )
        run_id = int(rcur.lastrowid)
        conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, field_name, expected_value_json, "
            "actual_value_json, delta_text, material_to_review, created_at, "
            "resolution) VALUES (?, 'equity_delta', 'net_liquidating_value', "
            "?, ?, '$-20.00 (ledger minus net_liq)', 1, '2026-05-31', "
            "'unresolved')",
            (
                run_id,
                json.dumps({"equity_dollars": 1000.0, "basis": "ledger"},
                           sort_keys=True),
                json.dumps({"equity_dollars": 1020.0, "basis": "net_liq"},
                           sort_keys=True),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(_DIAGNOSTIC_PATH)
    assert r.status_code == 200, r.text[:400]
    assert 'data-netted-delta="-20.00"' in r.text
