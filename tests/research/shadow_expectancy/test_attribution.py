from __future__ import annotations

from research.harness.shadow_expectancy.attribution import attribute_hypotheses
from swing.data.models import Candidate, CriterionResult
from swing.data.repos.hypothesis import list_hypotheses
from tests.research.shadow_expectancy.testkit import make_db


def _cand(bucket, criteria):
    return Candidate(
        ticker="AAA", bucket=bucket, close=10.0, pivot=10.0, initial_stop=9.0,
        adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="fallback_spy",
        pattern_tag=None, notes=None,
        criteria=tuple(CriterionResult(n, lyr, r) for n, lyr, r in criteria),
    )


def _active_registry(conn):
    return list_hypotheses(conn, status_filter="active")


def test_aplus_maps_to_h1(tmp_path):
    conn = make_db(tmp_path)  # migration 0008 seeds the 4 active hypotheses
    names = attribute_hypotheses(_cand("aplus", []), registry=_active_registry(conn))
    assert "A+ baseline" in names


def test_watch_proximity_only_maps_to_h2(tmp_path):
    conn = make_db(tmp_path)
    cand = _cand("watch", [("proximity_20ma", "trend_template", "fail")])
    names = attribute_hypotheses(cand, registry=_active_registry(conn))
    assert "Near-A+ defensible: extension test" in names
    # exclusivity: a proximity-only miss is NOT H3/H4.
    assert "Sub-A+ VCP-not-formed" not in names
    assert "Capital-blocked: smaller-position test" not in names


def test_watch_tightness_miss_maps_to_h3(tmp_path):
    # Verified against swing/recommendations/hypothesis.py _sub_aplus_vcp_not_formed_match:
    # watch AND (tightness OR vcp_volume_contraction) in non-pass AND non-pass subset of
    # (DOCTRINE_DEFENSIBLE_MISS_SET | {tightness, vcp_volume_contraction}).
    conn = make_db(tmp_path)
    cand = _cand("watch", [("tightness", "vcp", "fail")])
    names = attribute_hypotheses(cand, registry=_active_registry(conn))
    assert "Sub-A+ VCP-not-formed" in names
    assert "Near-A+ defensible: extension test" not in names  # not a proximity-only miss


def test_watch_vcp_volume_contraction_miss_also_maps_to_h3(tmp_path):
    conn = make_db(tmp_path)
    cand = _cand("watch", [("vcp_volume_contraction", "vcp", "fail")])
    assert "Sub-A+ VCP-not-formed" in attribute_hypotheses(
        cand, registry=_active_registry(conn))


def test_watch_risk_feasibility_only_maps_to_h4(tmp_path):
    # Verified against _capital_blocked_match: bucket in (watch, skip) AND non-pass set
    # is EXACTLY {risk_feasibility}.
    conn = make_db(tmp_path)
    cand = _cand("watch", [("risk_feasibility", "risk", "fail")])
    names = attribute_hypotheses(cand, registry=_active_registry(conn))
    assert "Capital-blocked: smaller-position test" in names
    assert "Sub-A+ VCP-not-formed" not in names   # risk_feasibility is not a VCP trigger


def test_skip_risk_feasibility_only_maps_to_h4(tmp_path):
    # C-review M5 + spec 6.1: production _capital_blocked_match accepts bucket in
    # ("watch", "skip") for a risk_feasibility-ONLY miss -- and `skip` is in fact the
    # production-realized bucket (risk_feasibility is a hard pre-filter that drives
    # bucket_for to 'skip'). The watch-only test above missed the dominant real case.
    # Verified against swing/recommendations/hypothesis.py:_capital_blocked_match:254-256.
    conn = make_db(tmp_path)
    cand = _cand("skip", [("risk_feasibility", "risk", "fail")])
    names = attribute_hypotheses(cand, registry=_active_registry(conn))
    assert "Capital-blocked: smaller-position test" in names
    assert "Sub-A+ VCP-not-formed" not in names


def test_unmatched_watch_falls_to_baseline(tmp_path):
    # Renamed from test_no_match_returns_empty: with the engine opted in
    # (include_baseline=True via attribute_hypotheses) and the v26 testkit
    # seeding the active baseline row, a watch/{orderliness} miss now attributes
    # to the broad-watch baseline (the honest complement). Spec §7.2.
    conn = make_db(tmp_path)
    cand = _cand("watch", [("orderliness", "vcp", "fail")])
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == [
        "Broad-watch baseline"]


def test_non_watch_unmatched_stays_empty(tmp_path):
    # Preserve a genuine empty-match (matched_no_hypothesis stays reachable):
    # baseline requires bucket=='watch', so a skip/{tightness} miss matches NOTHING
    # even opted in. Spec §7.2 / §9.1.
    conn = make_db(tmp_path)
    cand = _cand("skip", [("tightness", "vcp", "fail")])
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == []


def test_h2_exact_does_not_cannibalize_to_baseline(tmp_path):
    # Fixture 2 at the attribution level: {proximity_20ma} -> H2 ONLY.
    conn = make_db(tmp_path)
    cand = _cand("watch", [("proximity_20ma", "trend_template", "fail")])
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == [
        "Near-A+ defensible: extension test"]


def test_h3_flip_active_vs_closed(tmp_path):
    # Fixture 4: the dominant {tightness, vcp_volume_contraction} shape.
    conn = make_db(tmp_path)
    cand = _cand("watch", [("tightness", "vcp", "fail"),
                           ("vcp_volume_contraction", "vcp", "fail")])
    # Fresh testkit -> H3 active -> H3 claims it.
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == [
        "Sub-A+ VCP-not-formed"]
    # Close H3 (mirror the live DB) -> falls to the baseline.
    conn.execute(
        "UPDATE hypothesis_registry SET status='closed-target-met' "
        "WHERE name='Sub-A+ VCP-not-formed'")
    conn.commit()
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == [
        "Broad-watch baseline"]
