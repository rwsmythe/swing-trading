"""Phase 14 close-out (P14.N1) — row-replacement error colspans track the new
Chart column: hyp-rec table 9->10, open-positions table 10->11. Pre-existing
under-spanned form targets (entry/exit/stop) stay at the default 8 (out of
scope; documented in app.py)."""
from __future__ import annotations

import types

from swing.web.app import _row_error_colspan


def _req(hx_target):
    return types.SimpleNamespace(headers={"HX-Target": hx_target})


def test_row_error_colspan_hyprec_is_10():
    assert _row_error_colspan(_req("hyp-rec-row-NVDA")) == 10


def test_row_error_colspan_open_position_is_11():
    assert _row_error_colspan(_req("open-position-42")) == 11


def test_row_error_colspan_default_is_8():
    # watchlist + form targets fall through to the default (pre-existing).
    assert _row_error_colspan(_req("watchlist-row-NVDA")) == 8
    assert _row_error_colspan(_req("entry-form-NVDA")) == 8
