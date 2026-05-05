"""Phase 7 Sub-C C.14 — final shim deletion regression tests.

After C.14, the legacy Exit-shape API surface is GONE:
  * ``swing.data.models.Exit`` (stub class)
  * ``swing.data.repos.trades.insert_exit_with_event`` (raising stub)
  * ``swing.data.repos.trades.list_exits_for_trade`` (fills-backed shim)
  * ``swing.data.repos.trades.list_all_exits`` (fills-backed shim)
  * ``swing.data.repos.trades._ExitLikeRow`` (NamedTuple)

These ImportError-discriminating tests catch a future re-introduction of
any shim symbol or a partial-deletion bug. Discriminating: under buggy
code that re-defines any of these symbols, ``hasattr(...)`` returns True
and the import succeeds — the assertion fails.
"""
from __future__ import annotations

import importlib

import pytest


def test_c14_exit_dataclass_import_raises_import_error():
    """``from swing.data.models import Exit`` MUST raise ImportError."""
    models = importlib.import_module("swing.data.models")
    assert not hasattr(models, "Exit"), (
        "Exit was deleted in C.14 — re-introduction is a regression"
    )
    with pytest.raises(ImportError):
        from swing.data.models import Exit  # noqa: F401


def test_c14_list_all_exits_import_raises_import_error():
    """``from swing.data.repos.trades import list_all_exits`` MUST raise."""
    repos = importlib.import_module("swing.data.repos.trades")
    assert not hasattr(repos, "list_all_exits"), (
        "list_all_exits was deleted in C.14 — re-introduction is a regression"
    )
    with pytest.raises(ImportError):
        from swing.data.repos.trades import list_all_exits  # noqa: F401


def test_c14_list_exits_for_trade_import_raises_import_error():
    """``list_exits_for_trade`` shim MUST be deleted."""
    repos = importlib.import_module("swing.data.repos.trades")
    assert not hasattr(repos, "list_exits_for_trade"), (
        "list_exits_for_trade was deleted in C.14 — re-introduction is a "
        "regression"
    )
    with pytest.raises(ImportError):
        from swing.data.repos.trades import list_exits_for_trade  # noqa: F401


def test_c14_insert_exit_with_event_import_raises_import_error():
    """``insert_exit_with_event`` raising stub MUST be deleted."""
    repos = importlib.import_module("swing.data.repos.trades")
    assert not hasattr(repos, "insert_exit_with_event"), (
        "insert_exit_with_event was deleted in C.14 — re-introduction is a "
        "regression"
    )
    with pytest.raises(ImportError):
        from swing.data.repos.trades import insert_exit_with_event  # noqa: F401


def test_c14_exit_like_row_import_raises_import_error():
    """``_ExitLikeRow`` NamedTuple MUST be deleted."""
    repos = importlib.import_module("swing.data.repos.trades")
    assert not hasattr(repos, "_ExitLikeRow"), (
        "_ExitLikeRow was deleted in C.14 — re-introduction is a regression"
    )
    with pytest.raises(ImportError):
        from swing.data.repos.trades import _ExitLikeRow  # noqa: F401
