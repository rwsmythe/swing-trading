"""Regression tests for the production-gated binding-constraint script.

The script ``recompute_binding_prod_gated.py`` re-implements the gating
logic of ``swing.evaluation.scoring.bucket_for`` to attribute the FIRST
production-gated blocker per (ticker, date) row. These tests compare the
script's `production_gated_binding` output against the production
``bucket_for`` semantics on synthetic criterion rows, confirming:

- Rows that the script labels ``<aplus>`` ↔ ``bucket_for`` returns "aplus".
- Rows the script labels with a non-``<aplus>`` blocker ↔ ``bucket_for``
  returns "watch" or "skip", and the named blocker is consistent with the
  production reason for non-A+.
"""
from __future__ import annotations

import pytest

from research.harness.earnings_proximity.scripts.recompute_binding_prod_gated import (
    APLUS_KEY,
    TT_NAMES_IN_ORDER,
    VCP_NAMES_IN_ORDER,
    production_gated_binding,
)
from swing.evaluation.criteria._base import Result
from swing.evaluation.scoring import bucket_for


def _result_obj_from(name: str, layer: str, result: str) -> Result:
    """Build a Result with required fields populated minimally."""
    if result == "pass":
        return Result.pass_(value="", rule="", name=name, layer=layer)
    if result == "fail":
        return Result.fail_(value="", rule="", name=name, layer=layer)
    return Result.na_(value="", name=name, layer=layer)


def _row_to_results(row: dict[str, str]) -> tuple[list[Result], list[Result], list[Result]]:
    tt_results = [
        _result_obj_from(name, "trend_template", row.get(name, "pass"))
        for name in TT_NAMES_IN_ORDER
    ]
    vcp_results = [
        _result_obj_from(name, "vcp", row.get(name, "pass"))
        for name in VCP_NAMES_IN_ORDER
    ]
    risk_results = [
        _result_obj_from("risk_feasibility", "risk", row.get("risk_feasibility", "pass"))
    ]
    return tt_results, vcp_results, risk_results


@pytest.fixture
def cfg():
    """Same config build_harness_config produces — used for bucket_for."""
    from research.harness.earnings_proximity.replay import build_harness_config

    return build_harness_config()


# ---------------------------------------------------------------------------
# Direct unit tests on production_gated_binding (corner cases).
# ---------------------------------------------------------------------------


def test_all_pass_returns_aplus():
    row = {n: "pass" for n in (*TT_NAMES_IN_ORDER, *VCP_NAMES_IN_ORDER, "risk_feasibility")}
    assert production_gated_binding(row) == APLUS_KEY


def test_risk_fail_returns_risk_first_even_when_tt1_also_fails():
    """Production gating: risk_feasibility is the hard filter, checked first."""
    row = {n: "pass" for n in (*TT_NAMES_IN_ORDER, *VCP_NAMES_IN_ORDER)}
    row["TT1_above_150_200"] = "fail"
    row["risk_feasibility"] = "fail"
    assert production_gated_binding(row) == "risk_feasibility"


def test_tt8_only_fail_skipped_via_allowed_miss():
    """TT8 is in allowed_miss_names; if only TT8 fails, A+ is still possible."""
    row = {n: "pass" for n in (*TT_NAMES_IN_ORDER, *VCP_NAMES_IN_ORDER, "risk_feasibility")}
    row["TT8_rs_rank"] = "fail"
    assert production_gated_binding(row) == APLUS_KEY


def test_non_allowed_tt_fail_returns_first_tt_in_order():
    row = {n: "pass" for n in (*TT_NAMES_IN_ORDER, *VCP_NAMES_IN_ORDER, "risk_feasibility")}
    row["TT3_200_rising"] = "fail"
    row["TT5_above_50"] = "fail"
    assert production_gated_binding(row) == "TT3_200_rising"


def test_vcp_fail_returns_first_vcp_in_order():
    row = {n: "pass" for n in (*TT_NAMES_IN_ORDER, *VCP_NAMES_IN_ORDER, "risk_feasibility")}
    row["proximity_20ma"] = "fail"
    row["adr"] = "fail"
    assert production_gated_binding(row) == VCP_NAMES_IN_ORDER[
        VCP_NAMES_IN_ORDER.index("ma_stack_10_20_50") + 1  # ma_short_rising? no — order matters
    ] or production_gated_binding(row) in {"proximity_20ma", "adr"}
    # Tighten the assertion: VCP_NAMES_IN_ORDER lists ma_stack_10_20_50 before proximity_20ma
    # before adr; we set proximity_20ma and adr to fail; expected = proximity_20ma.
    assert production_gated_binding(row) == "proximity_20ma"


def test_na_treated_as_fail():
    row = {n: "pass" for n in (*TT_NAMES_IN_ORDER, *VCP_NAMES_IN_ORDER, "risk_feasibility")}
    row["TT3_200_rising"] = "na"
    assert production_gated_binding(row) == "TT3_200_rising"


# ---------------------------------------------------------------------------
# Cross-check production_gated_binding against bucket_for.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "row_overrides,expected_bucket,expected_blocker",
    [
        # All pass → aplus.
        ({}, "aplus", APLUS_KEY),
        # Risk fail alone → skip; blocker=risk_feasibility.
        ({"risk_feasibility": "fail"}, "skip", "risk_feasibility"),
        # TT1 fail alone → skip (TT pass-count drops to 7 but TT1 not in allowed_miss).
        ({"TT1_above_150_200": "fail"}, "skip", "TT1_above_150_200"),
        # TT8 fail alone → aplus (allowed miss).
        ({"TT8_rs_rank": "fail"}, "aplus", APLUS_KEY),
        # TT8 + one VCP fail → watch (vcp_fails == 1, allowed-miss TT8 skipped).
        (
            {"TT8_rs_rank": "fail", "proximity_20ma": "fail"},
            "watch",
            "proximity_20ma",
        ),
        # Three VCP fails → skip (vcp_fails > 2); blocker = first failing VCP.
        (
            {"adr": "fail", "tightness": "fail", "vcp_volume_contraction": "fail"},
            "skip",
            "adr",
        ),
        # Risk + TT1 + VCP all fail → risk-first under production gating.
        (
            {"risk_feasibility": "fail", "TT1_above_150_200": "fail", "adr": "fail"},
            "skip",
            "risk_feasibility",
        ),
    ],
)
def test_consistency_with_bucket_for(cfg, row_overrides, expected_bucket, expected_blocker):
    row = {n: "pass" for n in (*TT_NAMES_IN_ORDER, *VCP_NAMES_IN_ORDER, "risk_feasibility")}
    row.update(row_overrides)

    tt_r, vcp_r, risk_r = _row_to_results(row)
    bucket = bucket_for(tt_r, vcp_r, risk_r, cfg)
    assert bucket == expected_bucket

    blocker = production_gated_binding(row)
    assert blocker == expected_blocker

    # Mutual consistency: if blocker is APLUS, bucket must be aplus, and v.v.
    if blocker == APLUS_KEY:
        assert bucket == "aplus"
    else:
        assert bucket in ("watch", "skip")
