"""Phase 14 SB4 Slice 0 Task 0.1: process-wide matplotlib render lock.

charts.py renders through pyplot GLOBAL state (matplotlib.pyplot, mpf.plot,
plt.subplots, plt.close) which is NOT thread-safe. Every top-level public
``render_*_svg`` acquires the process-wide ``_RENDER_LOCK`` (an RLock) exactly
once at its boundary. RLock makes a helper that delegates to another serialized
renderer on the same thread safe (Codex R5 M#1 self-deadlock guard).
"""
import inspect

import pytest

import swing.web.charts as charts


def test_render_lock_is_reentrant():
    lock = charts._RENDER_LOCK
    assert lock.acquire(blocking=False) is True
    assert lock.acquire(blocking=False) is True  # reentrant -> no deadlock
    lock.release()
    lock.release()


def test_serialized_render_decorator_runs_under_lock():
    seen = []

    @charts._serialized_render
    def fake_render():
        seen.append(charts._RENDER_LOCK.acquire(blocking=False))
        charts._RENDER_LOCK.release()
        return b"<svg/>"

    assert fake_render() == b"<svg/>"
    assert seen == [True]


# Codex R1 M#2: assert EVERY public renderer is wrapped (global coverage,
# R4 M#1) so a future renderer added without the decorator is caught.
_PUBLIC_RENDERERS = (
    "render_watchlist_thumbnail_svg", "render_ticker_detail_svg",
    "render_position_detail_svg", "render_market_weather_svg",
    "render_theme2_annotated_svg",
)  # verified at swing/web/charts.py:492/540/628/752/898


def test_all_public_renderers_are_serialized():
    # Each public render_*_svg must be wrapped by _serialized_render. The
    # decorator uses functools.wraps, so detect the marker we set on it.
    for name in _PUBLIC_RENDERERS:
        fn = getattr(charts, name)
        assert getattr(fn, "_is_serialized_render", False), \
            f"{name} is not wrapped by _serialized_render"


def test_no_public_renderer_left_undecorated():
    # Guard against a NEW public renderer added later without the decorator.
    for name, fn in inspect.getmembers(charts, inspect.isfunction):
        if name.startswith("render_") and name.endswith("_svg"):
            assert getattr(fn, "_is_serialized_render", False), \
                f"public renderer {name} must be @_serialized_render"


@pytest.mark.parametrize("renderer_name", [
    "render_watchlist_thumbnail_svg", "render_ticker_detail_svg",
    "render_position_detail_svg", "render_market_weather_svg",
    "render_theme2_annotated_svg",
])
def test_public_renderer_no_deadlock_under_held_lock(renderer_name,
                                                     renderer_args_for):
    fn = getattr(charts, renderer_name)
    args, kwargs = renderer_args_for(renderer_name)  # valid planted inputs
    with charts._RENDER_LOCK:            # reentrant: must complete, not block
        out = fn(*args, **kwargs)
    assert out is not None
