from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from research.harness.shadow_expectancy.constants import (
    ATTRIBUTED_EXCLUDED_REASONS, UNATTRIBUTED_REASONS)
from research.harness.shadow_expectancy.exceptions import ShadowExpectancyError


@dataclass(frozen=True)
class DetectionLevel:
    total_detections: int
    collapsed_duplicate: int
    unique_signals: int


@dataclass(frozen=True)
class SignalOutcome:
    hypothesis: str | None   # None = a PRE-/NON-attribution unattributed state
    terminal: str            # 'closed'|'open_at_horizon'|'never_triggered'|'excluded'
                             #  |'unattributed'
    reason: str | None       # funnel reason for excluded/never_triggered/unattributed, else None


def build_funnel(detection: DetectionLevel, *, signal_outcomes) -> dict:
    # C-review M1 + R3-M1: ONE `unattributed` bucket whose value is a per-reason breakdown. The
    # six PRE-/NON-attribution reasons (no_candidate_join, matched_no_hypothesis, multi_match,
    # no_canonical_detection, inconsistent_detection_series, inconsistent_trigger_state) are
    # COUNTERS inside it -- matched_no_hypothesis and multi_match are reasons WITHIN
    # unattributed, NOT separate top-level buckets.
    unattributed: dict[str, int] = defaultdict(int)
    per_hyp: dict[str, dict] = {}

    def _blank():
        return {"closed": 0, "open_at_horizon": 0, "never_triggered": 0,
                "excluded": defaultdict(int)}

    for o in signal_outcomes:
        is_unattr_terminal = o.terminal == "unattributed"
        is_no_hypothesis = o.hypothesis is None
        if is_unattr_terminal or is_no_hypothesis:
            # A PRE-/NON-attribution state (Codex R4-m1 / writing-plans R4-M1): one of the six
            # UNATTRIBUTED_REASONS (no_candidate_join, matched_no_hypothesis, multi_match,
            # no_canonical_detection, inconsistent_detection_series, inconsistent_trigger_state)
            # -> a per-reason counter inside `unattributed`, never a hypothesis. (invalid_ohlc /
            # degenerate_risk on an ATTRIBUTED signal are per-hypothesis -- the branch below --
            # so they never reach here.)
            #
            # Defensive integrity (writing-plans R4-M1): a VALID unattributed outcome must
            # satisfy ALL THREE -- hypothesis is None AND terminal == "unattributed" AND reason in
            # UNATTRIBUTED_REASONS. ANY partial combination is a producer-contract violation and
            # RAISES (not silently counted): e.g. (hypothesis=None, terminal="closed",
            # reason="no_candidate_join") or (hypothesis="A+ baseline", terminal="unattributed",
            # reason="multi_match"). Unlike a bare `assert`, this is not stripped under -O.
            if not (is_unattr_terminal and is_no_hypothesis
                    and o.reason in UNATTRIBUTED_REASONS):
                raise ShadowExpectancyError(
                    "malformed unattributed outcome: require hypothesis is None AND "
                    "terminal=='unattributed' AND reason in UNATTRIBUTED_REASONS; "
                    f"got hypothesis={o.hypothesis!r} terminal={o.terminal!r} "
                    f"reason={o.reason!r}")
            unattributed[o.reason] += 1
            continue
        # Attributed branch: hypothesis is set AND terminal != "unattributed".
        # writing-plans R5: validate the reason PER terminal so an UNATTRIBUTED_REASONS reason (or
        # any wrong reason) can never be silently miscounted under a hypothesis. The producer
        # (run_harness) sets reason=None for closed/open_at_horizon, reason="never_triggered" for
        # never_triggered, and a post-attribution ATTRIBUTED_EXCLUDED_REASONS reason for excluded.
        card = per_hyp.setdefault(o.hypothesis, _blank())
        if o.terminal in ("closed", "open_at_horizon"):
            if o.reason is not None:
                raise ShadowExpectancyError(
                    f"attributed {o.terminal!r} outcome must have reason=None; got "
                    f"reason={o.reason!r} (hypothesis={o.hypothesis!r})")
            card[o.terminal] += 1
        elif o.terminal == "never_triggered":
            if o.reason != "never_triggered":
                raise ShadowExpectancyError(
                    "attributed never_triggered outcome must have reason=='never_triggered'; got "
                    f"reason={o.reason!r} (hypothesis={o.hypothesis!r})")
            card["never_triggered"] += 1
        elif o.terminal == "excluded":  # Codex M5: post-attribution per-hypothesis exclusion
            if o.reason not in ATTRIBUTED_EXCLUDED_REASONS:
                raise ShadowExpectancyError(
                    "attributed excluded outcome requires a post-attribution exclusion reason "
                    f"(one of {sorted(ATTRIBUTED_EXCLUDED_REASONS)}); got reason={o.reason!r} "
                    f"(hypothesis={o.hypothesis!r}) -- UNATTRIBUTED_REASONS are rejected here")
            card["excluded"][o.reason] += 1
        else:  # writing-plans R4-M1: an unknown terminal on an attributed signal is a contract violation
            raise ShadowExpectancyError(
                f"unknown terminal status {o.terminal!r} for attributed signal "
                f"hypothesis={o.hypothesis!r}")

    return {
        "detection_level": {
            "total_detections": detection.total_detections,
            "collapsed_duplicate_detection": detection.collapsed_duplicate,
            "unique_signals": detection.unique_signals,
        },
        # ONE bucket; its value is the per-reason breakdown (incl. matched_no_hypothesis +
        # multi_match).
        "unattributed": dict(unattributed),
        "per_hypothesis": {
            h: {**{k: v for k, v in c.items() if k != "excluded"},
                "excluded": dict(c["excluded"])}
            for h, c in per_hyp.items()
        },
    }
