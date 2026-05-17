"""Post-Phase-12 Sub-bundle 2 Task T-2.0 — SchwabStatusVM + SchwabCallSummary view-model tests.

Per plan §B T-2.0 acceptance criteria + dispatch brief §0.5 BINDING contracts:
- §0.5 #2: state triplet is LIVE/PROVISIONAL/DEGRADED (NOT spec §7.1's misnamed
  CONFIGURED/PROVISIONAL/NOT_CONFIGURED). Plan §A.0.1 D3 LOCK; V2.1 §VII.F
  amendment banked.
- §0.5 #3: state_reason is None iff state == 'LIVE' invariant — both branches
  discriminatingly tested (tests 11+12).
- §0.5 #13: base-layout VM banner pin — 5 base-layout fields default-initialized
  per Phase 10 Sub-bundle E T-E.3 retrofit pattern.

Discriminating-test pattern (12 cases) maps 1:1 to plan §B T-2.0 enumeration.
Each test is small + asserts a single observable behavior so a Codex finding
that re-litigates a LOCK can be pinpointed precisely.
"""
from __future__ import annotations

import pytest

from swing.web.view_models.schwab import (
    SchwabCallSummary,
    SchwabStatusVM,
)


def _valid_call_summary(**overrides) -> SchwabCallSummary:
    """Helper — minimal-valid SchwabCallSummary construction."""
    defaults = {
        "started_ts": "2026-05-17T10:00:00+00:00",
        "endpoint": "trader.account_orders",
        "status": "success",
        "http_status": 200,
        "error_excerpt": None,
    }
    defaults.update(overrides)
    return SchwabCallSummary(**defaults)


def _valid_status_vm(**overrides) -> SchwabStatusVM:
    """Helper — minimal-valid SchwabStatusVM construction (LIVE state)."""
    defaults = {
        "session_date": "2026-05-17",
        "environment": "production",
        "state": "LIVE",
        "state_reason": None,
        "tokens_db_path": "/home/user/swing-data/schwab-tokens.production.db",
        "refresh_token_expires_at": "2026-05-24T17:05:00+00:00",
        "refresh_token_days_remaining": 6,
        "refresh_token_severity": "ok",
        "recent_calls": [],
        "last_success_at": "2026-05-17T10:00:00+00:00",
        "last_failure_at": None,
        "degraded_banner_active": False,
    }
    defaults.update(overrides)
    return SchwabStatusVM(**defaults)


# ---------------------------------------------------------------------------
# (1) Valid construction; base-layout fields default-initialized.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_valid_construction_with_base_layout_defaults():
    """Test 1 — minimal-valid construction succeeds + base-layout fields
    default-initialized per Phase 10 Sub-bundle E T-E.3 retrofit pattern."""
    vm = _valid_status_vm()
    assert vm.state == "LIVE"
    assert vm.environment == "production"
    # Base-layout fields default-initialized (5 fields per Phase 10 T-E.3).
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.price_source_degraded_until is None
    assert vm.ohlcv_source_degraded is False
    assert vm.unresolved_material_discrepancies_count == 0


# ---------------------------------------------------------------------------
# (2) Invalid environment rejected.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_invalid_environment_rejected():
    """Test 2 — `environment` must be 'production' or 'sandbox'."""
    with pytest.raises(ValueError, match="environment"):
        _valid_status_vm(environment="banana")


# ---------------------------------------------------------------------------
# (3) Invalid state rejected.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_invalid_state_rejected():
    """Test 3 — `state` must be LIVE/PROVISIONAL/DEGRADED per plan §A.0.1
    D3 (shipped CLI triplet, NOT spec §7.1's misnamed CONFIGURED/...).
    BINDING contract; V2.1 §VII.F amendment banked for spec."""
    with pytest.raises(ValueError, match="state"):
        _valid_status_vm(state="CONFIGURED")  # Spec's misnamed value
    with pytest.raises(ValueError, match="state"):
        _valid_status_vm(state="banana")


# ---------------------------------------------------------------------------
# (4) Invalid severity rejected.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_invalid_severity_rejected():
    """Test 4 — `refresh_token_severity` must be ok/warn/error."""
    with pytest.raises(ValueError, match="severity"):
        _valid_status_vm(refresh_token_severity="critical")


# ---------------------------------------------------------------------------
# (5) Negative unresolved_material_discrepancies_count rejected.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_negative_unresolved_count_rejected():
    """Test 5 — base-layout banner count must be >= 0."""
    with pytest.raises(ValueError, match="unresolved_material_discrepancies_count"):
        _valid_status_vm(unresolved_material_discrepancies_count=-1)


# ---------------------------------------------------------------------------
# (6) recent_calls non-list rejected.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_recent_calls_non_list_rejected():
    """Test 6 — `recent_calls` must be a list."""
    with pytest.raises((ValueError, TypeError), match="recent_calls"):
        _valid_status_vm(recent_calls="not-a-list")


# ---------------------------------------------------------------------------
# (7) recent_calls list-of-non-SchwabCallSummary rejected.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_recent_calls_list_of_wrong_type_rejected():
    """Test 7 — `recent_calls` must be list[SchwabCallSummary]."""
    with pytest.raises((ValueError, TypeError), match="recent_calls"):
        _valid_status_vm(recent_calls=[{"endpoint": "x"}])


# ---------------------------------------------------------------------------
# (8) SchwabCallSummary smoke construction valid.
# ---------------------------------------------------------------------------

def test_schwab_call_summary_smoke_construction():
    """Test 8 — minimal-valid SchwabCallSummary construction succeeds."""
    cs = _valid_call_summary()
    assert cs.status == "success"
    assert cs.endpoint == "trader.account_orders"
    assert cs.http_status == 200


# ---------------------------------------------------------------------------
# (9) SchwabCallSummary unknown status rejected.
# ---------------------------------------------------------------------------

def test_schwab_call_summary_unknown_status_rejected():
    """Test 9 — `status` must be in the audit-row enum
    (success/auth_failed/rate_limited/error)."""
    with pytest.raises(ValueError, match="status"):
        _valid_call_summary(status="banana")


# ---------------------------------------------------------------------------
# (10) Frozen — attribute mutation raises + nav_back_to_config_url default.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_frozen_and_nav_default():
    """Test 10 — VM is frozen (FrozenInstanceError on mutation) AND
    `nav_back_to_config_url` defaults to "/config"."""
    vm = _valid_status_vm()
    assert vm.nav_back_to_config_url == "/config"
    with pytest.raises((AttributeError, Exception)):
        vm.state = "DEGRADED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# (11) state == 'LIVE' with non-None state_reason rejected.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_live_with_non_none_state_reason_rejected():
    """Test 11 (Codex R3 Minor #2 + plan §B T-2.0 invariant) —
    `state_reason is None iff state == 'LIVE'`. LIVE means all signals OK
    so reason is None; non-None reason is contradictory.

    Discriminating: a future fork that drops the invariant would render a
    LIVE badge with the most-recent DEGRADED reason text bleeding through,
    misleading the operator."""
    with pytest.raises(ValueError, match="state_reason"):
        _valid_status_vm(state="LIVE", state_reason="all good")


# ---------------------------------------------------------------------------
# (12) state in {PROVISIONAL, DEGRADED} with None or empty state_reason rejected.
# ---------------------------------------------------------------------------

def test_schwab_status_vm_non_live_with_none_or_empty_state_reason_rejected():
    """Test 12 (mirror of #11) — non-LIVE states REQUIRE a non-empty reason
    per `cli_schwab.py:826-831` rendering pattern + operator-actionability.

    Discriminating: a future fork that allows None on DEGRADED would render
    a red badge with no explanatory text — operator sees "DEGRADED" with
    no clue what to do."""
    with pytest.raises(ValueError, match="state_reason"):
        _valid_status_vm(state="PROVISIONAL", state_reason=None)
    with pytest.raises(ValueError, match="state_reason"):
        _valid_status_vm(state="DEGRADED", state_reason="")
    with pytest.raises(ValueError, match="state_reason"):
        _valid_status_vm(state="DEGRADED", state_reason="   ")  # whitespace-only
