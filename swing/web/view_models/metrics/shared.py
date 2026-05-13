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

    session_date: str
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0

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


@dataclass(frozen=True)
class ConfidenceBadgeVM:
    """Per-metric confidence-floor + low-confidence badge rendering.

    Composed alongside a metric value (WilsonCI/BootstrapCI/point) at the
    template layer. Both flags can be True (3 <= n < 5 + below
    global_confidence_floor_n) — at our current n state this is the
    common case.
    """

    low_confidence: bool
    confidence_floor_warning: bool
    text: str

    def __post_init__(self) -> None:
        # text may be empty for the "no badge" rendering path (both flags
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
