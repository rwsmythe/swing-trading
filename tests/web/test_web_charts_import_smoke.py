"""Phase 14 Sub-bundle 3 (chart-surface uniformity) T-3.6 packaging gate.

T-3.2..T-3.5 made ``swing.web.charts`` import ``mplfinance`` at module load
(candlestick conversion). ``swing web`` launches the FastAPI app, which imports
``swing.web.charts`` transitively via ``swing.web.app`` -> routes. Therefore the
``[web]`` install extra MUST declare ``mplfinance``.

The import-smoke tests alone pass in a dev environment that already has
mplfinance (via the ``dev`` / ``charts`` extras), so they cannot catch a
``[web]``-only profile regression. The metadata test below is the real
packaging guarantee: it parses ``pyproject.toml`` and asserts ``mplfinance``
is in the ``web`` extra.
"""

from __future__ import annotations


def test_web_charts_imports_cleanly():
    import importlib

    importlib.import_module("swing.web.charts")  # mplfinance present at module load


def test_web_app_imports_cleanly():
    import importlib

    importlib.import_module("swing.web.app")


def test_web_extra_declares_mplfinance():
    import pathlib
    import tomllib

    root = pathlib.Path(__file__).resolve().parents[2]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    web = data["project"]["optional-dependencies"]["web"]
    assert any(dep.replace(" ", "").startswith("mplfinance>=") for dep in web), web
