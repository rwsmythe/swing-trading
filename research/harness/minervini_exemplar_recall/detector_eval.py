# research/harness/minervini_exemplar_recall/detector_eval.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

import pandas as pd

from swing.patterns.foundation import CandidateWindow, generate_candidate_windows

from .constants import H2_MIN_BARS
from .exemplar_reader import ExemplarRow
from .ohlcv_reader import slice_to


def _lazy_pattern_detect_registry():
    """Deferred import of _pattern_detect_registry to keep swing.pipeline.runner (and its
    swing.data.ohlcv_archive transitive import) OUT of the module-level import graph.
    L2 LOCK: swing.data.ohlcv_archive must NOT appear in sys.modules when the evaluator
    modules are imported (test_l2_lock.py). Tests monkeypatch _REGISTRY before calling
    _resolve_registry(); the lazy default is never invoked in that path."""
    from swing.pipeline.runner import _pattern_detect_registry  # noqa: PLC0415
    return _pattern_detect_registry()


# Module-level so tests can monkeypatch with a fake registry. The production path
# resolves the real 5 detectors lazily on first call via _lazy_pattern_detect_registry.
_REGISTRY = _lazy_pattern_detect_registry

_ANCHOR_MODE_LIMITED_CLASSES = frozenset({"cup_with_handle", "high_tight_flag"})
_SKIP_REASONS = frozenset(
    {"coverage_skip", "window_generation_error", "no_windows", "detector_error_all"}
)


@dataclass(frozen=True)
class DetectorVerdict:
    skip_reason: str | None
    fired_classes: tuple[str, ...]
    fired_any_class: bool
    fired_expected_class: bool | None  # None for unmapped
    geometric_by_class: dict[str, float]
    h2_anchor_mode_limited_possible: bool
    h2_anchor_mode_limited_reason: str | None


def select_window(windows: list[CandidateWindow]) -> CandidateWindow:
    """Production-faithful: the LAST (most-recent-anchor) window (runner.py:1776)."""
    return windows[-1]


def _resolve_registry():
    reg = _REGISTRY
    return reg() if callable(reg) else reg


def _skip_verdict(reason: str, expected_class: str | None) -> DetectorVerdict:
    anchor_limited = expected_class in _ANCHOR_MODE_LIMITED_CLASSES
    return DetectorVerdict(
        skip_reason=reason,
        fired_classes=(),
        fired_any_class=False,
        fired_expected_class=(None if expected_class == "unmapped" else False),
        geometric_by_class={},
        h2_anchor_mode_limited_possible=anchor_limited,
        h2_anchor_mode_limited_reason=(
            "V1 zigzag_pivot anchors swing-lows; swing-high-anchored "
            f"{expected_class} may be under-anchored (spec 12.9)"
            if anchor_limited
            else None
        ),
    )


def evaluate_h2(
    *,
    exemplar: ExemplarRow,
    session: date,
    exemplar_full: pd.DataFrame,
    stage_conn: sqlite3.Connection,
) -> DetectorVerdict:
    expected = exemplar.detector_class
    sliced = slice_to(exemplar_full, session)
    if len(sliced) < H2_MIN_BARS:
        return _skip_verdict("coverage_skip", expected)

    try:
        windows = generate_candidate_windows(
            sliced, "zigzag_pivot", ticker=exemplar.tiingo_symbol, timeframe="daily"
        )
    except Exception:  # noqa: BLE001 - window generation raised (non-monotonic / NaN)
        return _skip_verdict("window_generation_error", expected)
    if not windows:
        return _skip_verdict("no_windows", expected)

    window = select_window(windows)
    geometric_by_class: dict[str, float] = {}
    attempts = 0
    failures = 0
    for detector_fn, pattern_class, _version in _resolve_registry():
        attempts += 1
        try:
            evidence = detector_fn(
                sliced, window, conn=stage_conn, ticker=exemplar.tiingo_symbol, asof_date=session
            )
            geometric_by_class[pattern_class] = float(getattr(evidence, "geometric_score", 0.0))
        except Exception:  # noqa: BLE001 - isolate one bad detector, continue the others
            failures += 1
            continue

    if attempts > 0 and failures == attempts:
        return _skip_verdict("detector_error_all", expected)

    fired_classes = tuple(sorted(c for c, s in geometric_by_class.items() if s > 0.0))
    fired_any = len(fired_classes) > 0
    if expected == "unmapped":
        fired_expected: bool | None = None
    else:
        fired_expected = expected in fired_classes

    anchor_limited = (
        expected in _ANCHOR_MODE_LIMITED_CLASSES and fired_expected is False
    )
    return DetectorVerdict(
        skip_reason=None,
        fired_classes=fired_classes,
        fired_any_class=fired_any,
        fired_expected_class=fired_expected,
        geometric_by_class=geometric_by_class,
        h2_anchor_mode_limited_possible=anchor_limited,
        h2_anchor_mode_limited_reason=(
            "V1 zigzag_pivot anchors swing-lows; swing-high-anchored "
            f"{expected} may be under-anchored (spec 12.9)"
            if anchor_limited
            else None
        ),
    )


def evaluate_h2_all_windows(
    *,
    exemplar: ExemplarRow,
    session: date,
    exemplar_full: pd.DataFrame,
    stage_conn: sqlite3.Connection,
) -> list[dict]:
    """NON-PRODUCTION diagnostic (--h2-all-windows): run the 5 detectors against EVERY window,
    not just windows[-1]. Production uses windows[-1] only (runner.py:1776); this scan can turn a
    deployed miss into a harness hit on an older anchor, so it is written to a SEPARATE file clearly
    labeled non-production and never feeds results.csv (spec section 6 / 10.2)."""
    sliced = slice_to(exemplar_full, session)
    if len(sliced) < H2_MIN_BARS:
        return []
    try:
        windows = generate_candidate_windows(
            sliced, "zigzag_pivot", ticker=exemplar.tiingo_symbol, timeframe="daily"
        )
    except Exception:  # noqa: BLE001
        return []
    rows: list[dict] = []
    for wi, window in enumerate(windows):
        fired: list[str] = []
        for detector_fn, pattern_class, _v in _resolve_registry():
            try:
                ev = detector_fn(
                    sliced, window, conn=stage_conn, ticker=exemplar.tiingo_symbol, asof_date=session
                )
                if float(getattr(ev, "geometric_score", 0.0)) > 0.0:
                    fired.append(pattern_class)
            except Exception:  # noqa: BLE001
                continue
        rows.append({
            "exemplar_id": exemplar.exemplar_id,
            "ticker": exemplar.ticker,
            "session": session.isoformat(),
            "window_index": str(wi),
            "anchor_date": window.anchor_date.isoformat(),
            "fired_classes": ";".join(sorted(fired)),
        })
    return rows
