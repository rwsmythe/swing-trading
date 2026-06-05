"""BaseLayoutVM mixin + shared metric VM dataclasses (plan §A.6 + §A.18).

Phase 10 introduces ``BaseLayoutVM`` as the canonical mixin that every
metrics-page VM extends. The base-layout fields are the 5 fields already
present on the existing DashboardVM / PipelineVM / JournalVM / WatchlistVM
/ ConfigVM / PageErrorVM family (per CLAUDE.md "base.html.j2 is shared —
new vm.foo field requires adding to EVERY base-layout VM" gotcha), plus
the new Phase 10 field ``unresolved_material_discrepancies_count`` per
plan §A.18 Codex R2 Major #6 restructure (discrepancies-helper landed in
Sub-bundle A T-A.7.1; populated from Sub-bundle A onward in every new
metrics VM; existing 6 base-layout VMs retrofit in Sub-bundle E T-E.3).

**Plan §A.6 type deviation (banked in return report §5):** plan §A.6 spec'd
``stale_banner: bool = False`` but ``base.html.j2`` renders
``{{ vm.stale_banner }}`` (the partial substitutes the actual banner text)
and existing DashboardVM/PipelineVM/JournalVM use ``str | None``. The
``BaseLayoutVM`` field type is set to ``str | None = None`` to match
existing pattern so rendered output is correct. Discriminating regression
test in T-A.7 checks FIELD NAMES only (not types) per plan §A.7 wording.
"""

from __future__ import annotations

from dataclasses import dataclass

from swing.evaluation.dates import PageKind


@dataclass(frozen=True)
class BaseLayoutVM:
    """Shared base-layout fields for every Phase 10 metrics-page VM.

    Mixin contract: every new metrics-page VM inherits these fields so the
    shared ``base.html.j2`` template renders without ``UndefinedError``.

    Per plan §A.18 + §I.5 LOCK: every metrics-page VM constructor
    populates ``unresolved_material_discrepancies_count`` from
    :func:`swing.metrics.discrepancies.count_unresolved_material` from the
    start (Sub-bundle A T-A.8 ``MetricsIndexVM`` + Sub-bundles B/C/D/E
    surface VMs). Existing 6 base-layout VMs retrofit in Sub-bundle E
    T-E.3 (cross-bundle pin via the skipped regression test in T-A.7).
    """

    # Issue #5 topbar policy: every base-layout (metrics/account/patterns-
    # queue) page is HISTORY_ANALYSIS (about the last completed session).
    # Class-level (NOT a dataclass field); subclasses override only if forward.
    PAGE_KIND = PageKind.HISTORY_ANALYSIS

    session_date: str
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0
    # Phase 12.5 #1 Task T-1.8 — banner counter for tier-1 multi-leg
    # auto-redirects on the latest completed reconciliation_run. Populated
    # from :func:`swing.metrics.discrepancies.count_recent_multi_leg_auto_corrections`
    # at every base-layout-mounted VM's builder site so the T-1.9 banner
    # block in ``base.html.j2`` reads ``vm.recent_multi_leg_auto_correction_count``
    # without ``UndefinedError`` (CLAUDE.md "base.html.j2 is shared" gotcha).
    # Default 0 keeps the banner suppressed when no recent multi-leg
    # auto-redirects exist OR when constructed in tests outside the
    # populating builder path.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 12.5 #2 T-2.7 -- banner link to FIRST pending-ambiguity
    # discrepancy resolve form. None when no pending-ambiguity row in the
    # banner-count set; URL when one exists. Populated by Pass B retrofit
    # (T-2.9) at every base-layout-mounted VM's builder site; default None
    # keeps the banner advisory text-only when no pending-ambiguity row
    # exists.
    banner_resolve_link: str | None = None

    def __post_init__(self) -> None:
        # Per plan §A.6 watch: lock asserts session_date is non-empty so
        # downstream Jinja `{{ vm.session_date }}` substitution always
        # has a meaningful value (NOT an empty `<span class="date"></span>`).
        if not self.session_date:
            raise ValueError(
                f"BaseLayoutVM.session_date must be non-empty; got "
                f"{self.session_date!r}"
            )
        if self.unresolved_material_discrepancies_count < 0:
            raise ValueError(
                "BaseLayoutVM.unresolved_material_discrepancies_count must be >= 0; "
                f"got {self.unresolved_material_discrepancies_count!r}"
            )
        if self.recent_multi_leg_auto_correction_count < 0:
            raise ValueError(
                "BaseLayoutVM.recent_multi_leg_auto_correction_count must be >= 0; "
                f"got {self.recent_multi_leg_auto_correction_count!r}"
            )
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "BaseLayoutVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "BaseLayoutVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


@dataclass(frozen=True)
class ConfidenceBadgeVM:
    """Per-metric confidence-floor + low-confidence + window-not-full badge
    rendering.

    Composed alongside a metric value (WilsonCI/BootstrapCI/point) at the
    template layer. Multiple flags can be True simultaneously per spec §5
    decoupling discipline: ``low_confidence`` (3 <= n < 5),
    ``confidence_floor_warning`` (n < global_confidence_floor_n), and the
    Class-D cadence flag ``window_not_full_warning`` (5 <= effective_n < N).

    Codex R2 Minor #1 fix: ``window_not_full_warning`` field added so
    Sub-bundle E's process-grade-trend surface can convey the spec §5.4
    "rolling window not yet at N" badge without inventing per-surface
    extension fields. Defaults False so existing surfaces don't need to
    populate it.
    """

    low_confidence: bool
    confidence_floor_warning: bool
    text: str
    window_not_full_warning: bool = False

    def __post_init__(self) -> None:
        # text may be empty for the "no badge" rendering path (all flags
        # False); discriminating tests in T-A.6 cover the truthy + non-
        # truthy cases.
        pass


@dataclass(frozen=True)
class ProvisionalBadgeVM:
    """PROVISIONAL/LIVE dynamic badge per spec §0.5 §11.4 + plan §A.6.

    Surfaces on §3.4 + §3.5 operational metrics indicating whether the
    capital denominator is a snapshot ("LIVE") or the
    ``capital_floor_constant_dollars`` fallback ("PROVISIONAL").
    """

    is_provisional: bool
    text: str


@dataclass(frozen=True)
class SuppressionRowVM:
    """Spec §5.6 suppression-placeholder rendering.

    Composed when a metric is suppressed (n below class floor or
    diversity-failure). Renders as italic placeholder text per spec §5.6;
    the dashboard layer never renders an empty cell / "—" / "N/A" (all
    three are ambiguous between "computation failed" and "intentionally
    suppressed").
    """

    metric_name: str
    placeholder_text: str

    def __post_init__(self) -> None:
        if not self.placeholder_text:
            raise ValueError(
                "SuppressionRowVM.placeholder_text must be non-empty; got "
                f"{self.placeholder_text!r}"
            )
