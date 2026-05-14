"""View-model for page_error.html.j2 — full-page HTML error responses."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageErrorVM:
    """Context for page_error.html.j2. The base layout (base.html.j2)
    dereferences vm.session_date, vm.stale_banner, and vm.price_source_degraded
    on every render; this VM supplies base-layout-compatible defaults so an
    error page doesn't turn into a 500 via UndefinedError. Spec §3.2."""
    session_date: str                     # today's action_session_for_run() value, or "n/a"
    stale_banner: None = None             # never stale on an error page
    price_source_degraded: bool = False   # degraded-cache banner not shown
    status_code: int = 400
    detail: str = "Invalid request"
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
    # Phase 10 Sub-bundle E T-E.3 — unresolved-material discrepancy banner
    # count (plan §A.18 + §I.5). Default 0 keeps the error page's banner
    # block suppressed; production error handlers may opt in by passing
    # the helper result. Per the cross-bundle pin's regression test the
    # FIELD NAME is the binding artifact.
    unresolved_material_discrepancies_count: int = 0
