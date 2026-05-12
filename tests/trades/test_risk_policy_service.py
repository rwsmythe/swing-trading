"""Phase 9 T-A.4 — risk_policy service tests.

Covers:
  - 6-step supersession sequence (predecessor flagged inactive BEFORE
    successor INSERT, FK pointer set AFTER; spec §4.1).
  - Caller-held transaction rejection (Phase 8 R3→R4 lesson).
  - Field whitelist + RiskPolicy __post_init__ propagation.
  - Atomic rollback on mid-tx fault.
  - read_active_policy delegate.
  - check_and_reconcile_toml_divergence: identity-no-divergence;
    divergent-with-frozen-Config-immutability; pre-v17 silent skip;
    no-active-policy silent skip.
  - seed_initial_policy idempotence.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

import pytest

from swing.config import load as load_cfg
from swing.data.db import ensure_schema
from swing.data.repos.risk_policy import (
    NoActivePolicyError,
    get_active_policy,
    get_policy_by_id,
)
from swing.trades.risk_policy import (
    CallerHeldTransactionError,
    check_and_reconcile_toml_divergence,
    read_active_policy,
    seed_initial_policy,
    supersede_active_policy,
)
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase9_service.db")


@pytest.fixture
def cfg(tmp_path: Path):
    """A real frozen Config built from _minimal_config (risk_equity_floor=7500.0)."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    return load_cfg(_minimal_config(project, home))


@pytest.fixture
def cfg_divergent(cfg):
    """Same Config with risk_equity_floor flipped to 5000.0 (diverges from seed)."""
    return dataclasses.replace(
        cfg,
        account=dataclasses.replace(cfg.account, risk_equity_floor=5000.0),
    )


# ---------------------------------------------------------------------------
# §1 — supersede_active_policy 6-step sequence
# ---------------------------------------------------------------------------


def test_supersede_creates_new_active_policy(conn: sqlite3.Connection) -> None:
    new_id = supersede_active_policy(
        conn,
        field_updates={"max_account_risk_per_trade_pct": 0.75},
        notes="operator test",
    )
    assert new_id == 2

    predecessor = get_policy_by_id(conn, policy_id=1)
    assert predecessor is not None
    assert predecessor.is_active == 0
    assert predecessor.effective_to is not None
    assert predecessor.superseded_by_policy_id == 2

    successor = get_policy_by_id(conn, policy_id=2)
    assert successor is not None
    assert successor.is_active == 1
    assert successor.effective_to is None
    assert successor.superseded_by_policy_id is None
    assert successor.max_account_risk_per_trade_pct == 0.75
    # Other fields copied from predecessor.
    assert successor.capital_floor_constant_dollars == 7500.0
    assert successor.scratch_epsilon_R == 0.10
    assert successor.policy_notes == "operator test"


def test_supersede_carries_cfg_cascade_default_note(
    conn: sqlite3.Connection,
) -> None:
    new_id = supersede_active_policy(
        conn,
        field_updates={"capital_floor_constant_dollars": 8500.0},
        source="cfg_cascade",
    )
    successor = get_policy_by_id(conn, policy_id=new_id)
    assert successor is not None
    assert successor.policy_notes == (
        "auto-cascade from cfg.account.risk_equity_floor edit"
    )


def test_supersede_rejects_caller_held_transaction(
    conn: sqlite3.Connection,
) -> None:
    """Phase 8 R3→R4 lesson: function rejects caller-held tx; does NOT
    auto-detect (auto-detect re-introduces the very race the explicit lock
    closes — see CLAUDE.md gotcha 'in_transaction auto-detect')."""
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(CallerHeldTransactionError):
        supersede_active_policy(
            conn,
            field_updates={"max_account_risk_per_trade_pct": 0.75},
        )
    conn.rollback()


def test_supersede_rejects_invalid_field(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="not a risk_policy field"):
        supersede_active_policy(
            conn,
            field_updates={"not_a_real_field": 1.0},
        )


def test_supersede_rejects_pk_or_metadata_field(
    conn: sqlite3.Connection,
) -> None:
    """Operator MUST NOT smuggle policy_id / effective_from / created_at /
    is_active / superseded_by_policy_id / effective_to via field_updates —
    those are server-stamped at supersession time per dispatch brief §0.3
    #9 + spec §A.10."""
    for forbidden in (
        "policy_id",
        "effective_from",
        "effective_to",
        "is_active",
        "superseded_by_policy_id",
        "created_at",
    ):
        with pytest.raises(ValueError, match="not a risk_policy field"):
            supersede_active_policy(conn, field_updates={forbidden: "x"})


def test_supersede_propagates_dataclass_validator_error(
    conn: sqlite3.Connection,
) -> None:
    """Invalid value (NaN) raised at RiskPolicy(__post_init__) bubbles up
    + transaction rolled back (no successor row created, predecessor still
    active)."""
    with pytest.raises(ValueError, match="not finite"):
        supersede_active_policy(
            conn,
            field_updates={"max_account_risk_per_trade_pct": float("nan")},
        )
    p = get_active_policy(conn)
    assert p.policy_id == 1
    assert p.is_active == 1


def test_supersede_atomic_rollback_on_mid_tx_fault(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject a fault between predecessor UPDATE and successor INSERT;
    assert full rollback (predecessor still active, no successor row)."""
    from swing.data.repos import risk_policy as repo_mod

    def boom(*a, **kw):  # noqa: ARG001
        raise RuntimeError("synthetic mid-tx fault")

    monkeypatch.setattr(repo_mod, "insert_policy", boom)

    with pytest.raises(RuntimeError, match="synthetic"):
        supersede_active_policy(
            conn, field_updates={"max_account_risk_per_trade_pct": 0.75},
        )

    p = get_active_policy(conn)
    assert p.policy_id == 1
    assert p.is_active == 1
    assert p.effective_to is None  # rolled back
    assert conn.in_transaction is False


# ---------------------------------------------------------------------------
# §2 — read_active_policy delegate
# ---------------------------------------------------------------------------


def test_read_active_policy_delegates(conn: sqlite3.Connection) -> None:
    p = read_active_policy(conn)
    assert p.policy_id == 1


# ---------------------------------------------------------------------------
# §3 — check_and_reconcile_toml_divergence
# ---------------------------------------------------------------------------


def test_check_and_reconcile_no_divergence_returns_identity(
    conn: sqlite3.Connection, cfg,
) -> None:
    """When TOML matches risk_policy, returns (cfg, None) — original Config
    unchanged identity-test."""
    new_cfg, divergence = check_and_reconcile_toml_divergence(conn, cfg)
    assert divergence is None
    assert new_cfg is cfg  # identity test — no replacement when no divergence


def test_check_and_reconcile_with_divergence_returns_corrected_cfg(
    conn: sqlite3.Connection, cfg_divergent, caplog,
) -> None:
    """Divergent TOML → return (corrected_cfg, divergence_dict).
    Original Config UNCHANGED (frozen-dataclass immutability)."""
    original = cfg_divergent
    with caplog.at_level("WARNING", logger="swing.trades.risk_policy"):
        new_cfg, divergence = check_and_reconcile_toml_divergence(
            conn, original,
        )
    assert divergence == {
        "field": "capital_floor_constant_dollars",
        "toml_value": 5000.0,
        "policy_value": 7500.0,
    }
    assert "diverges from risk_policy" in caplog.text.lower()
    # Corrected Config has the policy value.
    assert new_cfg.account.risk_equity_floor == 7500.0
    # Original Config unchanged.
    assert original.account.risk_equity_floor == 5000.0
    # Returned object is a new instance.
    assert new_cfg is not original


def test_check_and_reconcile_pre_v17_silent_skip(
    tmp_path: Path, cfg,
) -> None:
    """On a pre-v17 DB (no risk_policy table), helper returns (cfg, None)
    silently — does NOT raise. Ensures swing db-migrate from v16 → v17 can
    run without hitting a divergence check that depends on the schema it's
    about to create."""
    db_path = tmp_path / "pre_v17.db"
    pre_conn = sqlite3.connect(db_path)
    # Brand-new DB; no schema_version table.
    new_cfg, divergence = check_and_reconcile_toml_divergence(pre_conn, cfg)
    pre_conn.close()
    assert divergence is None
    assert new_cfg is cfg


def test_check_and_reconcile_no_active_policy_silent_skip(
    conn: sqlite3.Connection, cfg,
) -> None:
    """v17 schema present but zero active rows (test fixture pre-seed OR
    operator UPDATE that flagged every row inactive). Helper returns (cfg,
    None) — does NOT raise."""
    conn.execute("UPDATE risk_policy SET is_active = 0")
    new_cfg, divergence = check_and_reconcile_toml_divergence(conn, cfg)
    assert divergence is None
    assert new_cfg is cfg


# ---------------------------------------------------------------------------
# §4 — seed_initial_policy idempotence
# ---------------------------------------------------------------------------


def test_seed_initial_policy_returns_existing_id_when_active(
    conn: sqlite3.Connection, cfg,
) -> None:
    """Idempotent: when a row with is_active=1 already exists (migration
    seed), seed_initial_policy returns its policy_id without inserting a
    new row."""
    n_before = conn.execute("SELECT COUNT(*) FROM risk_policy").fetchone()[0]
    pid = seed_initial_policy(conn, cfg)
    n_after = conn.execute("SELECT COUNT(*) FROM risk_policy").fetchone()[0]
    assert pid == 1  # the migration seed
    assert n_after == n_before  # no new row inserted


def test_seed_initial_policy_inserts_when_no_active_row(
    conn: sqlite3.Connection, cfg,
) -> None:
    """When no active row exists (e.g., post-test-fixture wipe), seed
    inserts a new policy_id from cfg defaults."""
    conn.execute("UPDATE risk_policy SET is_active = 0")
    conn.commit()  # release the implicit transaction before invoking the service
    with pytest.raises(NoActivePolicyError):
        get_active_policy(conn)

    pid = seed_initial_policy(conn, cfg)
    assert pid >= 2  # new row past the existing inactive seed
    new = get_active_policy(conn)
    assert new.policy_id == pid
    assert new.is_active == 1
    assert new.capital_floor_constant_dollars == cfg.account.risk_equity_floor
