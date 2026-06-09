from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.harness.shadow_expectancy.constants import PRICE_TICK_DECIMALS


def normalize_tick(price: float) -> float:
    return round(float(price), PRICE_TICK_DECIMALS)


@dataclass(frozen=True)
class CollapseResult:
    canonical: Any | None
    collapsed_ids: list[int]
    # no_candidate_join (no candidate row) | no_canonical_detection (candidate present, no
    # pivot match; C-review M4) | inconsistent_detection_series | inconsistent_trigger_state
    # | None
    exclusion_reason: str | None


def collapse_detections(detections, candidate_pivot) -> CollapseResult:
    """Spec 6 / Codex C4: one shadow-trade per unique (run, ticker). The group is
    ALL detections for that (run, ticker). The canonical detection is the one whose
    pivot == candidate.pivot (tick-normalized), tie-broken by lowest detection_id.
    The consistency gates run over the WHOLE group (NOT just the pivot-matching
    subset): EVERY detection in the group MUST share an identical frozen forward
    series AND an identical first triggered_open session, else exclude. The collapsed
    set is every non-canonical detection in the group, so collapsed_duplicate ==
    group_size - 1 (covering non-pivot-matching detections too).
    """
    if candidate_pivot is None:
        return CollapseResult(None, [], "no_candidate_join")
    group = sorted(detections, key=lambda d: d.detection_id)
    target = normalize_tick(candidate_pivot)
    matching = [d for d in group if normalize_tick(d.pivot) == target]
    if not matching:
        # C-review M4: the candidate row EXISTS (candidate_pivot is not None) but NO
        # detection pivot matches it -> a canonical-detection / collapse integrity fault,
        # NOT a missing candidate. Distinct reason `no_canonical_detection`, routed to the
        # unattributed bucket like `inconsistent_*` (a substrate-integrity exclusion).
        return CollapseResult(None, [], "no_canonical_detection")
    # Consistency gates across the ENTIRE group (Codex C4 + R5-M1), keyed off the
    # canonical's frozen series / first trigger.
    canonical = matching[0]  # group is id-sorted, so this is the lowest-id pivot match
    if any(d.forward_series_key != canonical.forward_series_key for d in group):
        return CollapseResult(None, [], "inconsistent_detection_series")
    if any(d.first_trigger_session != canonical.first_trigger_session for d in group):
        return CollapseResult(None, [], "inconsistent_trigger_state")
    collapsed = [d.detection_id for d in group if d.detection_id != canonical.detection_id]
    return CollapseResult(canonical, collapsed, None)
