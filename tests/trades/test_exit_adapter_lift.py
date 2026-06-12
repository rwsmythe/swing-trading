import swing.web.view_models.dashboard as dash
from swing.trades.equity import _ExitShape, list_all_exitshape_via_fills


def test_dashboard_reexports_shared_adapter():
    # The dashboard module must reference the SHARED adapter, not a local dupe.
    assert dash.list_all_exitshape_via_fills is list_all_exitshape_via_fills
    assert not hasattr(dash, "_list_all_exitshape_via_fills") or \
        dash._list_all_exitshape_via_fills is list_all_exitshape_via_fills
    # _ExitShape is importable from the shared home.
    assert _ExitShape is not None
