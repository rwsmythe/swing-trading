"""Shared OHLC finiteness predicate (Phase 18 Arc 18-A).

ONE source of truth for "are these OHLC values finite?" -- consumed by BOTH
write barriers that must reject non-finite OHLC before it reaches durable
storage:

- ``swing.data.ohlcv_archive._trim_trailing_ragged`` (DataFrame-row shape) --
  the Arc-8 trailing-ragged trim on the per-ticker OHLCV archive.
- ``swing.pipeline.temporal_metadata.build_ohlc_today_json`` (bar-dict shape)
  + its caller ``swing.pipeline.runner._step_pattern_observe`` -- the
  temporal-log (``pattern_forward_observations``) write path.

Extracting the predicate here (the ``swing/data`` layer) is the C1 fix for the
root cause: the two paths each had their OWN finiteness logic (one present as
``isna().any()``, one missing entirely), so the Arc-8 barrier never reached the
second path. A single predicate cannot re-diverge.

Layer rule (verified-healthy): ``swing/data`` NEVER imports ``swing/pipeline``;
pipeline modules import FROM here. Stdlib-only (``math``) so it adds no
dependency weight to the pure ``temporal_metadata`` module.
"""
from __future__ import annotations

import math


def is_finite_ohlc(*values: float) -> bool:
    """True iff EVERY supplied value is finite (not NaN, not +/-inf).

    Operates on bare VALUES, not a container, so ONE predicate serves both the
    DataFrame-row shape (capitalized Open/High/Low/Close columns) and the
    bar-dict shape (lowercase open/high/low/close keys) without a third copy.

    Volume is EXEMPT by construction: callers pass only the OHLC values they
    wish to gate and never pass Volume (Arc-8: legitimately volume-less bars
    exist and must not be trimmed/skipped). An empty call returns True (no
    values to reject), matching ``_trim_trailing_ragged``'s "no OHLC columns ->
    no-op" arm.

    Uses ``math.isfinite`` -- the SAME finiteness definition the engine gate
    ``research/harness/shadow_expectancy/validate.py:_finite_nonneg`` uses, so
    the writer's "suspenders" reject exactly the set the engine's "belt"
    rejects (NaN AND inf). The engine additionally enforces ``>= 0``; that stays
    the engine's job -- this predicate is finiteness ONLY (hence the name) and
    adds no over-rejection of legitimate values at the write barrier (LOCK 4).

    Inputs MUST be real numbers (float-coercible: Python/NumPy floats). A
    non-numeric input is a programming error, not a data state. Both call sites
    supply numeric OHLC (the archive's float64 columns; the bar dict's
    ``float(...)``-coerced values).
    """
    return all(math.isfinite(v) for v in values)
