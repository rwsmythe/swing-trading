from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CollapseResult:
    canonical: Any | None        # canonical detection view (longest chain), or None on exclusion
    collapsed_ids: list[int]
    # 'inconsistent_detection_series' (strict-prefix invariant violated) | None.
    # no_candidate_join is decided in run.py (candidate is None), NOT here.
    exclusion_reason: str | None


def _sorted_bars(detection) -> tuple:
    """The detection's frozen bars sorted date-ascending. Each bar is
    (observation_date, open, high, low, close)."""
    return tuple(sorted(detection.bars, key=lambda b: b[0]))


def collapse_detections(detections) -> CollapseResult:
    """spec 2.3 (entry/join correction): one shadow signal per (run, ticker) group. The
    canonical detection is a PURE BAR SOURCE -- the geometric detection.pivot is no longer
    consulted. Canonical = the LONGEST frozen observation chain (most bars), tie-broken by
    lowest detection_id.

    The `inconsistent_detection_series` gate enforces the STRICT date-prefix invariant the
    longest-chain rule relies on (Codex R1-#1): after sorting each chain by observation_date,
    every non-canonical chain's date list MUST equal canonical_dates[:len(chain)] (a true
    prefix -- no missing interior sessions, no divergent dates) AND its OHLC on every shared
    date MUST match the canonical's. ANY violation -> exclude. This is NOT an overlap-only
    check (which would silently accept a gappy A=[d1,d3] vs B=[d1,d2,d3]).

    collapsed_ids = every non-canonical detection in the group (group_size - 1), preserving the
    detection-level reconciliation invariant on both the success and exclusion paths.
    """
    group = sorted(detections, key=lambda d: d.detection_id)
    # longest chain, tie low id: max over (len(bars), -detection_id).
    canonical = max(group, key=lambda d: (len(_sorted_bars(d)), -d.detection_id))
    canonical_bars = _sorted_bars(canonical)
    canonical_dates = [b[0] for b in canonical_bars]
    canonical_by_date = {b[0]: b for b in canonical_bars}

    for d in group:
        if d.detection_id == canonical.detection_id:
            continue
        dbars = _sorted_bars(d)
        ddates = [b[0] for b in dbars]
        # strict date-prefix: dates must be exactly the canonical's leading dates.
        if ddates != canonical_dates[: len(ddates)]:
            return CollapseResult(None, [], "inconsistent_detection_series")
        # OHLC on every shared date must match the canonical (full tuple equality).
        for b in dbars:
            if b != canonical_by_date[b[0]]:
                return CollapseResult(None, [], "inconsistent_detection_series")

    collapsed = [d.detection_id for d in group if d.detection_id != canonical.detection_id]
    return CollapseResult(canonical, collapsed, None)
