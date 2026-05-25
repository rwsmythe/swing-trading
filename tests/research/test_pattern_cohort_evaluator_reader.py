"""Tests for pattern cohort harness ohlcv_reader RE-EXPORT integrity.

Includes 5 BINDING L2 LOCK reinforcement tests per plan §F + §K:
  - Test 1 (§F.1): identity-preserving re-export (`is` identity)
  - Test 2 (§F.2): file-open mock (spy 4 boundaries) -- via the re-export
  - Test 3 (§F.3): import-graph mock (sentinel 4 forbidden modules) +
                   source-grep across 6 harness .py files
  - Test 4 (§F.4): byte-checksum discriminating (both Shape A planted)
  - Test 5 (§E.7 + §F.5): defensive read_or_fetch_archive signature lock +
                          exception hierarchy
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _make_shape_a_parquet(path: Path, n_bars: int = 250, sentinel_close: float = 100.0):
    """Write a Shape A parquet (lowercase OHLCV + asof_date column)."""
    dates = pd.date_range(end="2026-04-30", periods=n_bars, freq="B")
    df = pd.DataFrame({
        "asof_date": [d.date().isoformat() for d in dates],
        "open": [sentinel_close] * n_bars,
        "high": [sentinel_close + 1.0] * n_bars,
        "low": [sentinel_close - 1.0] * n_bars,
        "close": [sentinel_close] * n_bars,
        "volume": [1_000_000] * n_bars,
    })
    df.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# L2 LOCK Test 1: identity-preserving re-export per §F.1
# ---------------------------------------------------------------------------

def test_ohlcv_reader_re_export_identity():
    """L2 LOCK reinforcement test #1: harness's ohlcv_reader symbols are
    IDENTICALLY the V2 OHLCV evaluator's symbols (same object, not a
    re-implementation). Catches accidental shadow re-implementation that
    would bypass V2's existing 5 BINDING discriminating tests.
    """
    from research.harness.aplus_v2_ohlcv_evaluator import (
        ohlcv_reader as v2_reader,
    )
    from research.harness.pattern_cohort_evaluator import (
        ohlcv_reader as pc_reader,
    )
    assert pc_reader.read_yfinance_shape_a is v2_reader.read_yfinance_shape_a
    assert (
        pc_reader.read_yfinance_shape_a_sliced
        is v2_reader.read_yfinance_shape_a_sliced
    )
    assert pc_reader.BothExistDiagnostic is v2_reader.BothExistDiagnostic


# ---------------------------------------------------------------------------
# L2 LOCK Test 2: file-open mock per §F.2 (verbatim from V2 §F.1)
# ---------------------------------------------------------------------------

def test_pattern_cohort_reader_never_opens_schwab_api_parquet(tmp_path, monkeypatch):
    """L2 LOCK reinforcement test #2: file-open mock asserts harness reader
    NEVER opens {TICKER}.schwab_api.parquet for any synthetic test ticker.

    Spy on multiple file-open boundaries (pd.read_parquet + pathlib.Path.open
    + builtins.open + pyarrow) to catch any indirect path that bypasses pandas.
    """
    import builtins
    import pathlib
    synth = "ZZSYNTH2"
    yfinance_path = tmp_path / f"{synth}.yfinance.parquet"
    schwab_path = tmp_path / f"{synth}.schwab_api.parquet"
    _make_shape_a_parquet(yfinance_path, n_bars=250)
    _make_shape_a_parquet(schwab_path, n_bars=300)

    opened_paths: list[str] = []
    real_read_parquet = pd.read_parquet
    real_path_open = pathlib.Path.open
    real_builtins_open = builtins.open

    def _spy_read_parquet(path, *args, **kwargs):
        opened_paths.append(str(path))
        return real_read_parquet(path, *args, **kwargs)

    def _spy_path_open(self, *args, **kwargs):
        opened_paths.append(str(self))
        return real_path_open(self, *args, **kwargs)

    def _spy_builtins_open(file, *args, **kwargs):
        opened_paths.append(str(file))
        return real_builtins_open(file, *args, **kwargs)

    monkeypatch.setattr("pandas.read_parquet", _spy_read_parquet)
    monkeypatch.setattr(pathlib.Path, "open", _spy_path_open)
    monkeypatch.setattr(builtins, "open", _spy_builtins_open)

    try:
        import pyarrow.parquet as pq
        real_read_table = pq.read_table

        def _spy_read_table(source, *args, **kwargs):
            opened_paths.append(str(source))
            return real_read_table(source, *args, **kwargs)
        monkeypatch.setattr("pyarrow.parquet.read_table", _spy_read_table)
    except ImportError:
        pass

    from research.harness.pattern_cohort_evaluator.ohlcv_reader import (
        read_yfinance_shape_a,
    )
    read_yfinance_shape_a(synth, tmp_path)

    assert all("schwab_api" not in p for p in opened_paths), (
        f"Harness reader opened schwab_api parquet on at least one boundary: "
        f"{[p for p in opened_paths if 'schwab_api' in p]} "
        f"(all spied paths: {opened_paths})"
    )
    assert any(p.endswith(f"{synth}.yfinance.parquet") for p in opened_paths)


# ---------------------------------------------------------------------------
# L2 LOCK Test 3: import-graph mock + 6-file source-grep per §F.3
# ---------------------------------------------------------------------------

def test_pattern_cohort_module_set_does_NOT_import_schwab_or_yfinance(monkeypatch):  # noqa: N802
    """L2 LOCK reinforcement test #3: import-graph mock + source-grep asserts
    pattern_cohort harness modules NEVER import schwabdev / swing.integrations.schwab /
    yfinance / swing.data.ohlcv_archive -- directly OR indirectly.
    """
    import sys
    forbidden_modules = (
        "yfinance",
        "schwabdev",
        "swing.integrations.schwab",
        "swing.data.ohlcv_archive",
    )
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("research.harness.pattern_cohort_evaluator"):
            del sys.modules[mod_name]
        for forbidden in forbidden_modules:
            if mod_name == forbidden or mod_name.startswith(forbidden + "."):
                del sys.modules[mod_name]

    class _NoImportSentinel:
        def __init__(self, name): self._name = name

        def __getattr__(self, attr):
            raise AssertionError(
                f"pattern_cohort module attempted to access {attr!r} on banned import "
                f"target {self._name!r}"
            )

    for forbidden in forbidden_modules:
        monkeypatch.setitem(sys.modules, forbidden, _NoImportSentinel(forbidden))

    # Import all pattern_cohort modules -- must NOT trigger any forbidden module load.
    # cohort_reader / detector_invoker / output / run will be added at T-PC.1.2..T-PC.4;
    # the source-grep below catches them then.
    import research.harness.pattern_cohort_evaluator  # noqa: F401
    import research.harness.pattern_cohort_evaluator.exceptions  # noqa: F401
    import research.harness.pattern_cohort_evaluator.ohlcv_reader  # noqa: F401

    for forbidden in forbidden_modules:
        loaded = sys.modules.get(forbidden)
        assert isinstance(loaded, _NoImportSentinel), (
            f"Harness import chain replaced sentinel for {forbidden!r} with real "
            f"module {type(loaded).__name__} (L2 LOCK violation: indirect "
            f"import path loaded the real module)"
        )

    # Defense-in-depth: source-grep across ALL harness .py files
    import pathlib
    pc_dir = (
        pathlib.Path(__file__).resolve().parents[2]
        / "research" / "harness" / "pattern_cohort_evaluator"
    )
    banned_imports = (
        "import yfinance", "from yfinance",
        "import schwabdev", "from schwabdev",
        "from swing.integrations.schwab", "swing.integrations.schwab.",
        "from swing.data.ohlcv_archive", "swing.data.ohlcv_archive.",
        "import swing.data.ohlcv_archive",
        "read_or_fetch_archive",
    )
    for py_path in pc_dir.glob("*.py"):
        text = py_path.read_text(encoding="utf-8")
        for banned in banned_imports:
            assert banned not in text, (
                f"Harness module {py_path.name} contains banned import substring "
                f"{banned!r} (L2 LOCK violation per gotcha #17)"
            )


# ---------------------------------------------------------------------------
# L2 LOCK Test 4: byte-checksum discriminating per §F.4
# ---------------------------------------------------------------------------

def test_pattern_cohort_reads_only_yfinance_bytes_when_both_shape_a_files_exist(tmp_path):
    """L2 LOCK reinforcement test #4: plant both schwab_api Shape A AND
    yfinance Shape A; assert harness reads ONLY yfinance bytes via byte-checksum.
    """
    synth = "ZZBOTH2"
    yfinance_path = tmp_path / f"{synth}.yfinance.parquet"
    schwab_path = tmp_path / f"{synth}.schwab_api.parquet"
    _make_shape_a_parquet(yfinance_path, n_bars=250, sentinel_close=100.0)
    _make_shape_a_parquet(schwab_path, n_bars=250, sentinel_close=999.0)

    from research.harness.pattern_cohort_evaluator.ohlcv_reader import (
        BothExistDiagnostic,
        read_yfinance_shape_a,
    )
    diag = BothExistDiagnostic()
    df = read_yfinance_shape_a(synth, tmp_path, diagnostic=diag)

    assert df["Close"].iloc[-1] == 100.0, (
        f"Harness read schwab_api content (close={df['Close'].iloc[-1]}); "
        f"expected yfinance content (close=100.0)"
    )
    assert diag.count == 0, (
        "Both-exist diagnostic should NOT trigger for yfinance Shape A "
        "vs schwab_api Shape A pair (only fires on Shape A vs legacy)"
    )


# ---------------------------------------------------------------------------
# L2 LOCK Test 5 (defensive): read_or_fetch_archive signature lock per §E.7
# ---------------------------------------------------------------------------

def test_read_or_fetch_archive_has_no_prefer_source_kwarg():
    """Defensive test per cumulative gotcha #17 (Expansion #2 refinement BINDING):
    if production refactor ever adds a `prefer_source` kwarg, this test fires
    + flags that harness's read-only bypass justification (per OQ-3 + OQ-16 LOCK)
    needs re-evaluation.
    """
    import inspect

    from swing.data.ohlcv_archive import read_or_fetch_archive
    params = inspect.signature(read_or_fetch_archive).parameters
    assert "prefer_source" not in params


# ---------------------------------------------------------------------------
# Exception hierarchy test per plan §G T-PC.1.1 Step 13
# ---------------------------------------------------------------------------

def test_exception_hierarchy():
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import (
        OhlcvCoverageError as V2OhlcvCoverageError,
    )
    from research.harness.pattern_cohort_evaluator.exceptions import (
        BothCohortModesSuppliedError,
        CohortInputSchemaError,
        MalformedAsofDateError,
        NeitherCohortModeSuppliedError,
        OhlcvCoverageError,
        PatternCohortEvaluatorError,
    )
    assert OhlcvCoverageError is V2OhlcvCoverageError
    assert issubclass(CohortInputSchemaError, PatternCohortEvaluatorError)
    assert issubclass(MalformedAsofDateError, PatternCohortEvaluatorError)
    assert issubclass(BothCohortModesSuppliedError, PatternCohortEvaluatorError)
    assert issubclass(NeitherCohortModeSuppliedError, PatternCohortEvaluatorError)


def test_version_constant_set():
    """v0.1.0 per spec §K.1 frontmatter."""
    from research.harness.pattern_cohort_evaluator import __version__
    assert __version__ == "0.1.0"
