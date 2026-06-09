from __future__ import annotations

import importlib
import sys
from pathlib import Path

import research.harness.shadow_expectancy as pkg

_FORBIDDEN = (
    "yfinance", "schwabdev", "swing.integrations.schwab", "swing.data.ohlcv_archive",
)
_EVALUATOR_MODULES = (
    "constants", "exceptions", "io", "validate", "collapse", "attribution",
    "bracket", "simulator", "scorecard", "funnel", "output", "run",
)


class _NoImportSentinel:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, item):
        raise AssertionError(f"L2 LOCK violated: forbidden module {self._name!r} imported")


def test_evaluator_modules_do_not_import_forbidden(monkeypatch):
    for name in list(sys.modules):
        if name.startswith("research.harness.shadow_expectancy") or name in _FORBIDDEN:
            monkeypatch.delitem(sys.modules, name, raising=False)
    for forbidden in _FORBIDDEN:
        monkeypatch.setitem(sys.modules, forbidden, _NoImportSentinel(forbidden))
    for mod in _EVALUATOR_MODULES:
        importlib.import_module(f"research.harness.shadow_expectancy.{mod}")
    for forbidden in _FORBIDDEN:
        assert isinstance(sys.modules.get(forbidden), _NoImportSentinel), \
            f"L2 LOCK: {forbidden} was replaced by a real import"


def test_evaluator_sources_contain_no_forbidden_import_lines():
    pkg_dir = Path(pkg.__file__).parent
    banned = (
        "import yfinance", "from yfinance", "import schwabdev", "from schwabdev",
        "from swing.integrations.schwab", "swing.integrations.schwab.",
        "from swing.data.ohlcv_archive", "swing.data.ohlcv_archive.",
        "import swing.data.ohlcv_archive",
    )
    for mod in _EVALUATOR_MODULES:
        src = (pkg_dir / f"{mod}.py").read_text(encoding="utf-8")
        for line in src.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            for token in banned:
                assert token not in stripped, f"{mod}.py imports forbidden: {stripped!r}"
