# tests/research/minervini_exemplar_recall/test_l2_lock.py
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import research.harness.minervini_exemplar_recall as pkg

_FORBIDDEN = (
    "yfinance",
    "schwabdev",
    "swing.integrations.schwab",
    "swing.data.ohlcv_archive",
)

# tiingo_pull / qa_compare / qa_montage are data-acq scripts that MAY import yfinance/mpl;
# the L2 LOCK governs the EVALUATOR import graph, so we test exactly the evaluator modules.
_EVALUATOR_MODULES = (
    "constants", "exceptions", "ohlcv_reader", "exemplar_reader", "rs_proxy",
    "screen_eval", "stage_db", "detector_eval", "timing", "control_cohort",
    "scorecard", "output", "run",
)


class _NoImportSentinel:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, item):
        raise AssertionError(f"L2 LOCK violated: forbidden module {self._name!r} was imported")


def test_evaluator_modules_do_not_import_forbidden(monkeypatch):
    for name in list(sys.modules):
        if name.startswith("research.harness.minervini_exemplar_recall") or name in _FORBIDDEN:
            monkeypatch.delitem(sys.modules, name, raising=False)
    for forbidden in _FORBIDDEN:
        monkeypatch.setitem(sys.modules, forbidden, _NoImportSentinel(forbidden))
    for mod in _EVALUATOR_MODULES:
        importlib.import_module(f"research.harness.minervini_exemplar_recall.{mod}")
    for forbidden in _FORBIDDEN:
        loaded = sys.modules.get(forbidden)
        assert isinstance(loaded, _NoImportSentinel), (
            f"L2 LOCK: {forbidden} was replaced by a real import"
        )


def test_evaluator_sources_contain_no_forbidden_import_lines():
    pkg_dir = Path(pkg.__file__).parent
    banned = (
        "import yfinance", "from yfinance",
        "import schwabdev", "from schwabdev",
        "from swing.integrations.schwab", "swing.integrations.schwab.",
        "from swing.data.ohlcv_archive", "swing.data.ohlcv_archive.", "import swing.data.ohlcv_archive",
    )
    for mod in _EVALUATOR_MODULES:
        src = (pkg_dir / f"{mod}.py").read_text(encoding="utf-8")
        for line in src.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            for token in banned:
                assert token not in stripped, f"{mod}.py imports forbidden: {stripped!r}"
