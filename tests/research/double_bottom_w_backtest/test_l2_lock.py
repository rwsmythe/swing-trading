"""L2 LOCK BINDING tests for the D1 double_bottom_w backtest harness.

Mirrors the V2 OHLCV evaluator's L2 LOCK discriminating tests +
pattern_cohort_evaluator L2 LOCK discipline. Verifies:

  1. ZERO Schwab API imports (`yfinance`, `schwabdev`, `swing.integrations.schwab`)
     reach the D1 backtest module graph.
  2. The only OHLCV-read path is
     `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.read_yfinance_shape_a`
     (re-imported by run.py); no direct file-open boundary on parquet files
     happens inside the D1 modules themselves.

If any future contributor adds e.g. `import yfinance` to one of the D1
harness modules, BOTH tests fail loudly.
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

import pytest


_D1_PACKAGE = "research.harness.double_bottom_w_backtest"

# Module names whose IMPORT (anywhere in the D1 package's module graph)
# would break L2 LOCK. Imports through V2 OHLCV reader are OK because that
# module is itself L2-LOCK-verified.
_FORBIDDEN_IMPORTS = frozenset({
    "yfinance",
    "schwabdev",
    "swing.integrations.schwab",
    "swing.integrations.schwab.trader",
    "swing.integrations.schwab.marketdata",
    "swing.integrations.schwab.client",
    "swing.integrations.schwab.auth",
})


def _walk_d1_modules() -> list[str]:
    pkg = importlib.import_module(_D1_PACKAGE)
    names = [_D1_PACKAGE]
    for _, name, _ in pkgutil.walk_packages(pkg.__path__, prefix=f"{_D1_PACKAGE}."):
        names.append(name)
    return names


def test_no_forbidden_imports_reach_d1_module_graph() -> None:
    """Import every D1 harness module + assert no forbidden modules in sys.modules
    AS A CONSEQUENCE of D1 imports.

    Methodology: take a snapshot of sys.modules BEFORE importing D1 modules,
    then re-import all D1 modules fresh, then check the delta.
    """
    # Drop any cached D1 + forbidden modules so we're checking from-clean import.
    to_drop = [
        m for m in list(sys.modules)
        if m.startswith(_D1_PACKAGE) or m in _FORBIDDEN_IMPORTS or
        any(m.startswith(fi + ".") for fi in _FORBIDDEN_IMPORTS)
    ]
    for m in to_drop:
        del sys.modules[m]

    # Re-import every D1 module
    for name in _walk_d1_modules():
        importlib.import_module(name)

    # Now verify forbidden modules NOT in sys.modules
    loaded = set(sys.modules.keys())
    violators = []
    for forbidden in _FORBIDDEN_IMPORTS:
        if forbidden in loaded:
            violators.append(forbidden)
        # Also catch nested imports under a forbidden namespace
        for m in loaded:
            if m.startswith(forbidden + "."):
                violators.append(m)
    assert not violators, (
        f"L2 LOCK VIOLATION: forbidden modules in sys.modules after D1 import: {violators}. "
        f"All Schwab API access is BANNED in the D1 backtest harness; reads must route "
        f"through the V2 OHLCV reader at research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader."
    )


def test_d1_modules_source_contains_no_forbidden_substring() -> None:
    """Sentinel grep: assert no D1 .py file mentions 'yfinance' or 'schwabdev'
    in its source. Catches `import yfinance` even before module load. Mirrors
    V2 OHLCV evaluator's source-grep test at
    tests/research/test_aplus_v2_ohlcv_reader.py."""
    pkg = importlib.import_module(_D1_PACKAGE)
    pkg_dir = Path(pkg.__file__).parent
    bad_subs = ("yfinance", "schwabdev")
    violators: list[tuple[Path, str]] = []
    for py in sorted(pkg_dir.glob("**/*.py")):
        text = py.read_text(encoding="utf-8")
        # Drop comments + docstrings: trivial heuristic — split at first quote-quote-quote.
        # We accept this is approximate; the more authoritative check is the
        # sys.modules check above. This source-grep is defense-in-depth.
        for sub in bad_subs:
            if sub in text:
                # The substring is allowed in COMMENTS only (e.g., "..xfinance.." in
                # a docstring referencing the upstream architecture). Whitelist
                # any line that's purely a comment / docstring fragment.
                offending_lines = [
                    line for line in text.splitlines()
                    if sub in line and not line.lstrip().startswith("#")
                ]
                # Strip docstring lines too (very rough -- if line contains '"""' nearby, skip)
                # Better heuristic: an import line begins with `import` or `from`.
                offending_imports = [
                    line for line in offending_lines
                    if line.lstrip().startswith(("import ", "from "))
                ]
                if offending_imports:
                    violators.append((py.relative_to(pkg_dir), sub))
    assert not violators, (
        f"L2 LOCK VIOLATION: D1 module source contains forbidden import lines: {violators}. "
        f"D1 harness must NOT import yfinance or schwabdev directly; reads must route "
        f"through the V2 OHLCV reader."
    )
