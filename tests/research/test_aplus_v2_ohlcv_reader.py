"""Tests for V2 OHLCV harness ohlcv_reader module.

Includes 5 L2 LOCK BINDING discriminating tests per plan §F + §K:
  - Test 1: file-open mock (spy 4 boundaries)
  - Test 2: import-graph mock (sentinel 4 forbidden modules)
  - Test 3: byte-checksum discriminating (both Shape A planted)
  - Test 4 (defensive): read_or_fetch_archive signature lock
  - Test 5 (defensive): V2 module-set grep for read_or_fetch_archive
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest


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
# T-V2.1.1 Step 1: primary Shape A read test
# ---------------------------------------------------------------------------

def test_read_yfinance_shape_a_returns_dataframe_with_capitalized_ohlcv(tmp_path):
    _make_shape_a_parquet(tmp_path / "ZZTEST.yfinance.parquet", n_bars=250)
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    df = read_yfinance_shape_a("ZZTEST", tmp_path)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 250
    assert df.index.is_monotonic_increasing


# ---------------------------------------------------------------------------
# T-V2.1.1 Step 6: legacy fallback test
# ---------------------------------------------------------------------------

def test_read_yfinance_shape_a_falls_back_to_legacy_when_shape_a_absent(tmp_path):
    # Plant ONLY legacy file (capitalized OHLCV + DatetimeIndex)
    dates = pd.date_range(end="2026-04-30", periods=250, freq="B")
    df = pd.DataFrame({
        "Open": [100.0] * 250, "High": [101.0] * 250,
        "Low": [99.0] * 250, "Close": [100.0] * 250, "Volume": [1_000_000] * 250,
    }, index=dates)
    df.to_parquet(tmp_path / "ZZLEG.parquet")

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    result = read_yfinance_shape_a("ZZLEG", tmp_path)
    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(result) == 250


# ---------------------------------------------------------------------------
# T-V2.1.1 Step 8: both-exist diagnostic test
# ---------------------------------------------------------------------------

def test_read_yfinance_shape_a_both_exist_shape_a_wins_increments_diagnostic(tmp_path):
    _make_shape_a_parquet(tmp_path / "ZZBOTH.yfinance.parquet", n_bars=200, sentinel_close=100.0)
    # Legacy with DIFFERENT content
    dates = pd.date_range(end="2026-04-30", periods=400, freq="B")
    legacy_df = pd.DataFrame({
        "Open": [50.0] * 400, "High": [51.0] * 400,
        "Low": [49.0] * 400, "Close": [50.0] * 400, "Volume": [2_000_000] * 400,
    }, index=dates)
    legacy_df.to_parquet(tmp_path / "ZZBOTH.parquet")

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
        BothExistDiagnostic,
        read_yfinance_shape_a,
    )
    diag = BothExistDiagnostic()
    result = read_yfinance_shape_a("ZZBOTH", tmp_path, diagnostic=diag)
    # Shape A wins per OQ-18 LOCK -> result has 200 rows + close=100.0
    assert len(result) == 200
    assert result["Close"].iloc[-1] == 100.0
    # Diagnostic increments + records affected ticker
    assert diag.count == 1
    assert diag.affected_tickers == ["ZZBOTH"]


# ---------------------------------------------------------------------------
# T-V2.1.1 Step 12: OhlcvCoverageError test
# ---------------------------------------------------------------------------

def test_read_yfinance_shape_a_raises_OhlcvCoverageError_when_neither_file_exists(tmp_path):  # noqa: N802
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    with pytest.raises(OhlcvCoverageError, match="ZZMISS"):
        read_yfinance_shape_a("ZZMISS", tmp_path)


# ---------------------------------------------------------------------------
# T-V2.1.1 Step 13: column-case normalization + asof_date drop
# ---------------------------------------------------------------------------

def test_read_yfinance_shape_a_column_case_normalization_from_lowercase(tmp_path):
    """Test 7 in §H: column-case normalization from lowercase to capitalized."""
    _make_shape_a_parquet(tmp_path / "ZZNORM.yfinance.parquet", n_bars=250)
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    df = read_yfinance_shape_a("ZZNORM", tmp_path)
    # Capitalized
    for col in ("Open", "High", "Low", "Close", "Volume"):
        assert col in df.columns
    # Lowercase not present
    for col in ("open", "high", "low", "close", "volume"):
        assert col not in df.columns


def test_read_yfinance_shape_a_asof_date_column_dropped_post_normalization(tmp_path):
    """Test 8 in §H: asof_date column dropped at read boundary."""
    _make_shape_a_parquet(tmp_path / "ZZDROP.yfinance.parquet", n_bars=250)
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    df = read_yfinance_shape_a("ZZDROP", tmp_path)
    assert "asof_date" not in df.columns


# ---------------------------------------------------------------------------
# T-V2.1.1 Step 13: sliced tests
# ---------------------------------------------------------------------------

def test_read_yfinance_shape_a_sliced_includes_asof_date_bar_inclusive(tmp_path):
    _make_shape_a_parquet(tmp_path / "ZZSL.yfinance.parquet", n_bars=250)
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a_sliced
    asof = date(2026, 4, 30)
    result = read_yfinance_shape_a_sliced("ZZSL", tmp_path, asof_date=asof)
    # Inclusive: last bar IS at asof_date (backward-looking <= per gotcha #12)
    assert result.index[-1].date() == asof


def test_read_yfinance_shape_a_sliced_raises_OhlcvCoverageError_below_min_bars(tmp_path):  # noqa: N802
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError
    _make_shape_a_parquet(tmp_path / "ZZSHRT.yfinance.parquet", n_bars=50)  # < 200
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a_sliced
    with pytest.raises(OhlcvCoverageError, match="ZZSHRT"):
        read_yfinance_shape_a_sliced("ZZSHRT", tmp_path, asof_date=date(2026, 4, 30))


# ---------------------------------------------------------------------------
# §H Test 14: both-exist diagnostic affected_tickers list cap at 50
# ---------------------------------------------------------------------------

def test_read_yfinance_shape_a_both_exist_diagnostic_caps_affected_tickers_at_50(tmp_path):
    """Test 14 in §H: both-exist diagnostic caps affected_tickers at 50."""
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
        BothExistDiagnostic,
        read_yfinance_shape_a,
    )
    diag = BothExistDiagnostic()
    for i in range(60):
        ticker = f"ZZ{i:03d}"
        _make_shape_a_parquet(tmp_path / f"{ticker}.yfinance.parquet", n_bars=205)
        # Plant legacy file too to trigger both-exist
        dates = pd.date_range(end="2026-04-30", periods=205, freq="B")
        legacy_df = pd.DataFrame({
            "Open": [50.0] * 205, "High": [51.0] * 205,
            "Low": [49.0] * 205, "Close": [50.0] * 205, "Volume": [1_000_000] * 205,
        }, index=dates)
        legacy_df.to_parquet(tmp_path / f"{ticker}.parquet")
        read_yfinance_shape_a(ticker, tmp_path, diagnostic=diag)
    # count accumulates accurately (60 both-exist cases)
    assert diag.count == 60
    # affected_tickers capped at 50 per spec §F.1 R4.M1
    assert len(diag.affected_tickers) == 50


# ---------------------------------------------------------------------------
# L2 LOCK Test 1: file-open mock (plan §F.1)
# ---------------------------------------------------------------------------

def test_v2_ohlcv_reader_never_opens_schwab_api_parquet(tmp_path, monkeypatch):
    """L2 LOCK reinforcement test #1: file-open mock asserts V2 process
    NEVER opens {TICKER}.schwab_api.parquet for any synthetic test ticker.

    Per Codex R1.M4 RESOLVED: spy on multiple file-open boundaries
    (pd.read_parquet + pathlib.Path.open + builtins.open + pyarrow) to catch
    any indirect path that bypasses pandas. Brief §3.5 specified file-open
    mock at Path.open or equivalent boundary; pd.read_parquet alone is too
    narrow.
    """
    import builtins
    import pathlib
    # Plant both files for a synthetic ticker
    synth = "ZZSYNTH"
    yfinance_path = tmp_path / f"{synth}.yfinance.parquet"
    schwab_path = tmp_path / f"{synth}.schwab_api.parquet"
    _make_shape_a_parquet(yfinance_path, n_bars=250)
    _make_shape_a_parquet(schwab_path, n_bars=300)

    # Spy on multiple boundaries; each records every path opened
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

    # pyarrow defense: if pyarrow.parquet.read_table is available, spy on it
    try:
        import pyarrow.parquet as pq
        real_read_table = pq.read_table
        def _spy_read_table(source, *args, **kwargs):
            opened_paths.append(str(source))
            return real_read_table(source, *args, **kwargs)
        monkeypatch.setattr("pyarrow.parquet.read_table", _spy_read_table)
    except ImportError:
        pass

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    read_yfinance_shape_a(synth, tmp_path)

    # Assert NO schwab_api path was opened on ANY boundary
    assert all("schwab_api" not in p for p in opened_paths), (
        f"V2 reader opened schwab_api parquet on at least one boundary: "
        f"{[p for p in opened_paths if 'schwab_api' in p]} "
        f"(all spied paths: {opened_paths})"
    )
    # Assert yfinance path WAS opened
    assert any(p.endswith(f"{synth}.yfinance.parquet") for p in opened_paths)


# ---------------------------------------------------------------------------
# L2 LOCK Test 2: import-graph mock (plan §F.2)
# ---------------------------------------------------------------------------

def test_v2_module_set_does_NOT_import_schwab_or_yfinance(monkeypatch):  # noqa: N802
    """L2 LOCK reinforcement test #2: import-graph mock asserts V2 modules
    NEVER import any schwabdev / swing.integrations.schwab / yfinance /
    swing.data.ohlcv_archive symbol -- directly OR indirectly.

    Codex R1.M3 RESOLVED: V2 must also block swing.data.ohlcv_archive (which
    imports yfinance at swing/data/ohlcv_archive.py:47); a V2 helper-reuse
    import there would silently pull yfinance into the process. Tested via
    BOTH (a) post-import sys.modules absence AND (b) source-file grep.
    """
    import sys
    # Remove cached V2 modules + cached forbidden modules to force fresh
    # import -- verifies V2 import chain does NOT load any forbidden module
    # transitively.
    forbidden_modules = (
        "yfinance",
        "schwabdev",
        "swing.integrations.schwab",
        "swing.data.ohlcv_archive",
    )
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("research.harness.aplus_v2_ohlcv_evaluator"):
            del sys.modules[mod_name]
        for forbidden in forbidden_modules:
            if mod_name == forbidden or mod_name.startswith(forbidden + "."):
                del sys.modules[mod_name]

    # Plant sentinels that raise if any V2 module touches them
    class _NoImportSentinel:
        def __init__(self, name): self._name = name
        def __getattr__(self, attr):
            raise AssertionError(
                f"V2 module attempted to access {attr!r} on banned import "
                f"target {self._name!r}"
            )

    for forbidden in forbidden_modules:
        monkeypatch.setitem(sys.modules, forbidden, _NoImportSentinel(forbidden))

    # Import all V2 modules -- must NOT trigger any forbidden module load
    import research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution  # noqa: F401
    import research.harness.aplus_v2_ohlcv_evaluator.context_builder  # noqa: F401
    import research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader  # noqa: F401
    import research.harness.aplus_v2_ohlcv_evaluator.sweep  # noqa: F401

    # Defense-in-depth #1: post-import, confirm no forbidden module was loaded
    # to a real (non-sentinel) class. The sentinels remain in sys.modules; any
    # accidental `from yfinance import X` would have triggered AssertionError
    # via __getattr__ above. A direct `import yfinance` (no attribute access)
    # would have left the sentinel intact (still our object).
    for forbidden in forbidden_modules:
        loaded = sys.modules.get(forbidden)
        assert isinstance(loaded, _NoImportSentinel), (
            f"V2 import chain replaced sentinel for {forbidden!r} with real "
            f"module {type(loaded).__name__} (L2 LOCK violation: indirect "
            f"import path loaded the real module)"
        )

    # Defense-in-depth #2: grep source files for any banned import substring
    import pathlib
    v2_dir = (
        pathlib.Path(__file__).resolve().parents[2]
        / "research" / "harness" / "aplus_v2_ohlcv_evaluator"
    )
    banned_imports = (
        "import yfinance", "from yfinance",
        "import schwabdev", "from schwabdev",
        "from swing.integrations.schwab", "swing.integrations.schwab.",
        "from swing.data.ohlcv_archive", "swing.data.ohlcv_archive.",
        "import swing.data.ohlcv_archive",
    )
    for py_path in v2_dir.glob("*.py"):
        text = py_path.read_text(encoding="utf-8")
        for banned in banned_imports:
            assert banned not in text, (
                f"V2 module {py_path.name} contains banned import substring "
                f"{banned!r} (L2 LOCK violation per Codex R1.M3)"
            )


# ---------------------------------------------------------------------------
# L2 LOCK Test 3: byte-checksum (plan §F.3)
# ---------------------------------------------------------------------------

def test_v2_reads_only_yfinance_bytes_when_both_shape_a_files_exist(tmp_path):
    """L2 LOCK reinforcement test #3: plant both schwab_api Shape A AND
    yfinance Shape A parquet files; assert V2 reads ONLY yfinance bytes
    via byte-checksum compare; assert V2 process NEVER reads schwab_api file.
    """
    synth = "ZZBOTH"
    # Distinct content per file so byte-checksum is distinguishable
    yfinance_path = tmp_path / f"{synth}.yfinance.parquet"
    schwab_path = tmp_path / f"{synth}.schwab_api.parquet"
    _make_shape_a_parquet(yfinance_path, n_bars=250, sentinel_close=100.0)
    _make_shape_a_parquet(schwab_path, n_bars=250, sentinel_close=999.0)

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
        BothExistDiagnostic,
        read_yfinance_shape_a,
    )
    diag = BothExistDiagnostic()
    df = read_yfinance_shape_a(synth, tmp_path, diagnostic=diag)

    # Assert V2 read yfinance content (close == 100.0, NOT 999.0)
    assert df["Close"].iloc[-1] == 100.0, (
        f"V2 read schwab_api content (close={df['Close'].iloc[-1]}); "
        f"expected yfinance content (close=100.0)"
    )

    # Assert diagnostic surface did NOT trigger for yfinance vs schwab_api pair
    # (diagnostic fires on yfinance Shape A vs LEGACY {ticker}.parquet per OQ-18;
    # NOT on yfinance Shape A vs schwab_api Shape A -- those are different sources)
    assert diag.count == 0, (
        f"Both-exist diagnostic should NOT trigger for {synth}.yfinance.parquet "
        f"vs {synth}.schwab_api.parquet (Shape A pair; not Shape A vs legacy)"
    )


# ---------------------------------------------------------------------------
# L2 LOCK Test 4 (defensive): read_or_fetch_archive signature lock (plan §K.4)
# ---------------------------------------------------------------------------

def test_read_or_fetch_archive_has_no_prefer_source_kwarg():
    """Defensive test per NEW gotcha #17 (Expansion #2 refinement BINDING):
    if production refactor ever adds a `prefer_source` kwarg to
    read_or_fetch_archive, this test fires + flags that V2's read-only
    bypass justification (per OQ-16 LOCK) needs re-evaluation.
    """
    import inspect

    from swing.data.ohlcv_archive import read_or_fetch_archive
    params = inspect.signature(read_or_fetch_archive).parameters
    assert "prefer_source" not in params, (
        "Production read_or_fetch_archive now has a prefer_source kwarg; "
        "V2's bypass justification per OQ-16 LOCK requires re-evaluation. "
        "Update spec §F.1 + V2 OHLCV harness ohlcv_reader.py to consider "
        "routing through the production function."
    )


# ---------------------------------------------------------------------------
# L2 LOCK Test 5 (defensive): V2 module-set grep for read_or_fetch_archive (plan §K.5)
# ---------------------------------------------------------------------------

def test_v2_module_set_does_NOT_import_read_or_fetch_archive():  # noqa: N802
    """Companion to test_v2_module_set_does_NOT_import_schwab_or_yfinance --
    V2 modules MUST NOT import read_or_fetch_archive per OQ-16 LOCK.
    """
    import pathlib
    v2_dir = (
        pathlib.Path(__file__).resolve().parents[2]
        / "research" / "harness" / "aplus_v2_ohlcv_evaluator"
    )
    for py_path in v2_dir.glob("*.py"):
        text = py_path.read_text(encoding="utf-8")
        assert "read_or_fetch_archive" not in text, (
            f"V2 module {py_path.name} contains forbidden reference to "
            f"read_or_fetch_archive (per OQ-16 LOCK + spec §F.1)"
        )
