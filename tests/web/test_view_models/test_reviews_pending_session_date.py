"""Slice A (A1): /reviews/pending topbar date is stamped from last_completed_session.

The shared topbar `<span class="date">{{ vm.session_date }}</span>` was blank because
`build_reviews_pending_vm` never set `session_date` (ReviewsPendingVM redefines the field
with an empty default and is NOT a BaseLayoutVM subclass, so the empty default slipped
through). It must mirror the sibling `build_review_vm`: backward-looking
`last_completed_session(datetime.now()).isoformat()` (the session-anchor read/write gotcha
family — backward-looking content gets the backward-looking anchor).
"""
from __future__ import annotations

import re
from datetime import datetime

from fastapi.testclient import TestClient

import swing.web.view_models.trades as trades_mod
from swing.evaluation.dates import last_completed_session
from swing.web.app import create_app


def test_reviews_pending_topbar_date_is_last_completed_session(seeded_db, monkeypatch):
    """Pre-fix: session_date defaults to "" -> span inner text "" != ISO date -> FAIL.
    Post-fix: build_reviews_pending_vm stamps last_completed_session(FIXED).isoformat().

    The clock is frozen so the route and the assertion share the same instant
    (Codex R1-M2: two independent datetime.now() calls can straddle a session
    boundary -> flake). build_reviews_pending_vm resolves the module-global
    `datetime` name at call time, so monkeypatching trades_mod.datetime works.
    """
    cfg, cfg_path = seeded_db
    FIXED = datetime(2026, 6, 3, 21, 0, 0)

    class _FrozenDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return FIXED

    monkeypatch.setattr(trades_mod, "datetime", _FrozenDT)
    expected = last_completed_session(FIXED).isoformat()
    # The expected value is a real ISO date, NOT the empty string the pre-fix
    # code would render.
    assert expected != ""

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/reviews/pending")
    assert r.status_code == 200
    m = re.search(r'<span class="date">([^<]*)</span>', r.text)
    assert m is not None, "topbar date span not found in /reviews/pending"
    assert m.group(1).strip() == expected
