"""Phase 14 close-out (P14.N1) — the shared thumbnail render cap is one
process-wide instance reused by the journal route and the new dashboard
thumbnail routes (DRY extraction, behavior-identical)."""
from __future__ import annotations

import threading


def test_shared_cap_constants_present_and_reused():
    import swing.web.thumbnail_render as tr
    assert isinstance(
        tr._THUMBNAIL_RENDER_SEMAPHORE, type(threading.BoundedSemaphore(1)),
    )
    assert tr._THUMBNAIL_RENDER_TIMEOUT_S == 2.0
    assert tr._THUMBNAIL_CACHE_CONTROL == "private, max-age=60"
    # journal route imports the SAME instance (one process-wide cap)
    import swing.web.routes.journal as j
    assert j._THUMBNAIL_RENDER_SEMAPHORE is tr._THUMBNAIL_RENDER_SEMAPHORE
    assert j._THUMBNAIL_RENDER_TIMEOUT_S is tr._THUMBNAIL_RENDER_TIMEOUT_S
    assert j._THUMBNAIL_CACHE_CONTROL is tr._THUMBNAIL_CACHE_CONTROL
