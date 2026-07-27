"""LatchIdentity + the shared identity-column contract (RD finding 4)."""
from __future__ import annotations

import pytest

from swing.latches.constants import (
    DEFAULT_LATCH_HORIZON_SESSIONS,
    LATCH_CLEAR_REASONS,
    LATCH_STATES,
    LATCH_ZONE_CAP_PCT,
    latch_horizon_sessions,
)
from swing.latches.identity import LATCH_IDENTITY_COLUMNS, LatchIdentity


def _ident(**over):
    base = dict(
        candidate_id=8851, evaluation_run_id=99, ticker="VSTS",
        detection_date="2026-06-25", pipeline_run_id=112,
    )
    base.update(over)
    return LatchIdentity(**base)


def test_identity_carries_both_id_spaces():
    i = _ident()
    assert (i.evaluation_run_id, i.ticker) == (99, "VSTS")
    assert (i.ticker, i.detection_date) == ("VSTS", "2026-06-25")
    assert i.candidate_id == 8851
    assert i.pipeline_run_id == 112


def test_identity_allows_absent_pipeline_run_id():
    assert _ident(pipeline_run_id=None).pipeline_run_id is None


@pytest.mark.parametrize("bad", ["", "  ", "2026-6-25", "26-06-25", "garbage"])
def test_identity_rejects_malformed_detection_date(bad):
    with pytest.raises(ValueError, match="detection_date"):
        _ident(detection_date=bad)


def test_identity_rejects_blank_ticker():
    with pytest.raises(ValueError, match="ticker"):
        _ident(ticker="   ")


@pytest.mark.parametrize("field", ["candidate_id", "evaluation_run_id"])
def test_identity_rejects_bool_and_nonpositive_ints(field):
    with pytest.raises(ValueError, match=field):
        _ident(**{field: True})
    with pytest.raises(ValueError, match=field):
        _ident(**{field: 0})


def test_identity_column_contract_is_the_five_shared_columns():
    """21-B copies this tuple verbatim; a silent reorder/rename breaks the join."""
    assert LATCH_IDENTITY_COLUMNS == (
        "candidate_id", "evaluation_run_id", "ticker",
        "detection_date", "pipeline_run_id",
    )


def test_locked_constants():
    assert LATCH_ZONE_CAP_PCT == 3.0
    assert LATCH_STATES == frozenset({
        "armed", "order_resting", "filled", "invalidated", "horizon_expired",
        "superseded"})
    assert LATCH_CLEAR_REASONS == frozenset({
        "fill", "invalidation", "horizon", "superseded"})


def test_horizon_is_derived_from_the_observe_window_not_hard_coded():
    """RD gate ruling (section A.4): the latch horizon MUST track the shadow
    engine's ENTRY window. Binding at the source is what stops a future change
    to the observe window from silently manufacturing a live-vs-shadow
    divergence."""
    from types import SimpleNamespace
    cfg = SimpleNamespace(
        pipeline=SimpleNamespace(observe_max_pending_window_sessions=44))
    assert latch_horizon_sessions(cfg) == 44          # tracks cfg, not a literal


def test_default_horizon_mirrors_the_pipeline_config_default():
    """#11 mirror drift-pin. The module default exists only for the pure
    derivation's signature; if PipelineConfig's default moves and this does
    not, production and the tests would silently disagree."""
    from swing.config import PipelineConfig
    assert (DEFAULT_LATCH_HORIZON_SESSIONS
            == PipelineConfig().observe_max_pending_window_sessions == 30)


def test_zone_escape_is_not_a_clear_reason():
    """Section A.7.1: zone escape is a RENDER attribute of the armed state.
    A future contributor adding it here would clear latches whose resting
    orders are still valid and would desynchronize the panel from the broker."""
    assert not {r for r in LATCH_CLEAR_REASONS if "zone" in r}
