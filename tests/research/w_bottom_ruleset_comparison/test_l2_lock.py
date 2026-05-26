"""L2 LOCK BINDING tests for D2 harness (mirrors D1 dispatch brief Section 5.4).

(a) Source-grep sentinel: no `import yfinance` / `import schwabdev` /
    `swing.integrations.schwab` in NEW D2 module sources.
(b) Import-graph sentinel: post-import, sys.modules does NOT contain
    yfinance / schwabdev / swing.integrations.schwab as imported names.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


_D2_PACKAGE_DIR = Path(__file__).parent.parent.parent.parent / "research" / "harness" / "w_bottom_ruleset_comparison"


def test_source_grep_no_forbidden_imports():
    """Sentinel: D2 module sources MUST NOT contain forbidden import
    statements per L2 LOCK BINDING (no Schwab/yfinance dependencies at
    backtest time; all OHLCV reads route through the V2 Shape A reader)."""
    assert _D2_PACKAGE_DIR.exists(), f"D2 package dir missing: {_D2_PACKAGE_DIR}"
    forbidden_patterns = (
        "import yfinance",
        "from yfinance",
        "import schwabdev",
        "from schwabdev",
        "from swing.integrations.schwab",
        "import swing.integrations.schwab",
    )
    offenders = []
    for source_file in _D2_PACKAGE_DIR.glob("*.py"):
        body = source_file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in body:
                offenders.append((source_file.name, pattern))
    assert not offenders, (
        f"D2 module sources contain forbidden imports per L2 LOCK BINDING: {offenders}"
    )


def test_import_graph_post_import_excludes_forbidden_modules():
    """Sentinel: importing the D2 package must NOT pull yfinance / schwabdev
    / swing.integrations.schwab into sys.modules (transitively)."""
    # Strip any pre-existing imports of D2 + L2-forbidden modules so the
    # test is order-independent. (Test isolation: do NOT pop the production
    # swing module tree itself; just check forbidden modules after import.)
    for mod_name in list(sys.modules):
        if (
            mod_name.startswith("research.harness.w_bottom_ruleset_comparison")
            or mod_name.startswith("yfinance")
            or mod_name.startswith("schwabdev")
            or mod_name.startswith("swing.integrations.schwab")
        ):
            sys.modules.pop(mod_name, None)

    # Fresh import of the D2 package + its submodules.
    import research.harness.w_bottom_ruleset_comparison  # noqa: F401
    import research.harness.w_bottom_ruleset_comparison.rulesets  # noqa: F401
    import research.harness.w_bottom_ruleset_comparison.walkforward  # noqa: F401
    import research.harness.w_bottom_ruleset_comparison.io  # noqa: F401
    import research.harness.w_bottom_ruleset_comparison.run  # noqa: F401

    forbidden_prefixes = (
        "yfinance",
        "schwabdev",
        "swing.integrations.schwab",
    )
    offenders = [
        m for m in sys.modules
        if any(m == p or m.startswith(p + ".") for p in forbidden_prefixes)
    ]
    assert not offenders, (
        f"L2 LOCK violation: forbidden modules present in sys.modules after "
        f"D2 import: {offenders}"
    )
