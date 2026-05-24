"""Typed exceptions for the V2 OHLCV criterion-evaluator harness."""
from __future__ import annotations


class OhlcvCoverageError(Exception):
    """Raised when a candidate's OHLCV archive has fewer than 200 bars at
    its data_asof_date (insufficient for trend_template MA200 per
    swing/evaluation/criteria/trend_template.py:24-29).
    """


class MissingRsUniversePathError(Exception):
    """Raised when cfg.paths.rs_universe_path is unset or the file is
    unreadable. V2 fails-fast at universe load.
    """


class EmptyRsUniverseError(Exception):
    """Raised when the loaded RS universe is empty OR has fewer than
    --min-universe-size tickers (default 100).
    """


class InvalidRsUniverseError(Exception):
    """Raised when the loaded RS universe contains more than 5% shape-invalid
    rows (>10 rows whichever is greater). Lists first 20 invalid symbols
    in the message.
    """


class PostCleanupUniverseTooSmallError(Exception):
    """Raised when AFTER dropping invalid + dedup rows the accepted-ticker
    count falls below --min-universe-size. Separate from EmptyRsUniverseError
    because the original universe passed the pre-cleanup threshold.
    """


class OutOfRangeSubstitutionError(Exception):
    """Raised when a sweep_value falls outside the cfg dataclass field's
    documented range (e.g., trend_template.min_passes substituted with 9 when
    only 8 TT criteria exist).
    """


class MalformedAsofDateError(Exception):
    """Raised when evaluation_runs.data_asof_date is not a valid
    ISO YYYY-MM-DD string (cumulative gotcha #12 discipline).
    """
