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
    # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect advisory banner counter.
    # Same default-0 contract as the sibling banner: error pages keep the
    # advisory suppressed unless an error handler explicitly populates it.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity discrepancy
    # resolve form. None when no pending-ambiguity row exists.
    banner_resolve_link: str | None = None

    def __post_init__(self) -> None:
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "PageErrorVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "PageErrorVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )
