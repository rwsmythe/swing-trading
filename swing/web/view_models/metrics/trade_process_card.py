"""View-model for spec §4.1 trade-process card (Sub-bundle B Task T-B.2).

Composes per-cohort tabs (4 cohorts + "all closed trades" toggle) wrapping
the per-cohort :class:`swing.metrics.process.TradeProcessMetricsResult`.

Per plan §A.18 + §I.5: extends :class:`BaseLayoutVM` and populates
``unresolved_material_discrepancies_count`` via
:func:`swing.metrics.discrepancies.count_unresolved_material` per
constructor.

Default-active tab: FIRST cohort tab per spec §4.1 binding "primary axis:
per-hypothesis-cohort, with 'all closed trades' as default toggle; never
a non-cohort default" (plan §E Task B.2 interpretation: the per-cohort
view is the default; "all" is a non-default toggle).

Per plan §E + §A.9: V1 surfaces are pure server-rendered; per-tab
navigation is via simple ``<a>`` anchors with query-string
``?cohort=<name>`` for the active-tab selection — NO HTMX OOB-swap, NO
HX-Redirect, NO embedded forms.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.evaluation.dates import action_session_for_run
from swing.metrics.cohort import count_per_cohort
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.metrics.process import (
    TradeProcessMetricsResult,
    compute_trade_process_metrics,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM

# Special sentinel for the "all closed trades" tab. Distinguishes the
# operator-facing toggle from a missing/blank cohort label (a cohort with
# the literal string "all" would be orphan — see ``count_per_cohort`` for
# orphan-label surfacing).
ALL_COHORTS_KEY: str = "__all__"


@dataclass(frozen=True)
class CohortTabVM:
    """Per-cohort tab descriptor.

    ``cohort_key`` is either the canonical cohort name OR ``ALL_COHORTS_KEY``
    (the "all closed trades" toggle).

    ``label`` is the operator-facing display string (cohort name OR
    "All closed trades").

    ``n_closed`` is the cohort's closed-trade count — used by the
    template for the "5 trades" badge alongside the tab label.

    ``metrics`` is the per-cohort :class:`TradeProcessMetricsResult`
    aggregate.

    ``is_active`` flags the currently-selected tab.
    """

    cohort_key: str
    label: str
    n_closed: int
    metrics: TradeProcessMetricsResult
    is_active: bool

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError(
                f"CohortTabVM.label must be non-empty; got {self.label!r}"
            )
        if not self.cohort_key:
            raise ValueError(
                f"CohortTabVM.cohort_key must be non-empty; got "
                f"{self.cohort_key!r}"
            )
        if self.n_closed < 0:
            raise ValueError(
                f"CohortTabVM.n_closed must be >= 0; got {self.n_closed!r}"
            )


@dataclass(frozen=True)
class TradeProcessCardVM(BaseLayoutVM):
    """VM for ``GET /metrics/trade-process``. Extends BaseLayoutVM per
    §A.8 + §I.5 — populates ``unresolved_material_discrepancies_count``
    via the shared helper.
    """

    cohort_tabs: tuple[CohortTabVM, ...] = field(default_factory=tuple)
    active_cohort_key: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.cohort_tabs:
            raise ValueError(
                "TradeProcessCardVM.cohort_tabs must be non-empty; "
                "every cohort (including registry cohorts at n=0) + "
                "the All tab is rendered"
            )
        # active_cohort_key MUST match one tab.
        active_count = sum(1 for t in self.cohort_tabs if t.is_active)
        if active_count != 1:
            raise ValueError(
                f"TradeProcessCardVM must have exactly 1 active tab; "
                f"got {active_count}"
            )
        keys = {t.cohort_key for t in self.cohort_tabs}
        if self.active_cohort_key not in keys:
            raise ValueError(
                f"TradeProcessCardVM.active_cohort_key {self.active_cohort_key!r} "
                f"not present in cohort_tabs"
            )


def build_trade_process_card_vm(
    *, cfg: Config, conn: sqlite3.Connection | None = None,
    active_cohort_key: str | None = None,
) -> TradeProcessCardVM:
    """Factory per plan §A.18: populate every metrics-VM field eagerly.

    ``active_cohort_key`` is the operator-supplied query-string parameter
    selecting which tab is rendered as active. When ``None`` or unknown,
    falls back to the FIRST cohort tab (NOT the All tab) per spec §4.1.
    """
    own_conn = conn is None
    if own_conn:
        conn = connect(cfg.paths.db_path)
    assert conn is not None
    try:
        cohort_counts = count_per_cohort(conn)
        unresolved = count_unresolved_material(conn)
        recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)
        banner_resolve_link = (
            fetch_first_pending_ambiguity_resolve_link_path(conn)
        )

        # Order: hypothesis_registry order then any orphan labels. The
        # count_per_cohort helper iterates registry rows by id, then
        # appends orphans — preserve insertion order in dict (Python 3.7+).
        registered_names = list(cohort_counts.keys())

        # Determine the default active tab: FIRST cohort name (not "all").
        # When operator supplies an explicit active_cohort_key matching a
        # tab, use it.
        default_active = registered_names[0] if registered_names else ALL_COHORTS_KEY
        if active_cohort_key is None or active_cohort_key not in (
            *registered_names, ALL_COHORTS_KEY,
        ):
            active_key = default_active
        else:
            active_key = active_cohort_key

        tabs: list[CohortTabVM] = []
        for name in registered_names:
            metrics = compute_trade_process_metrics(
                conn, hypothesis_label=name,
            )
            tabs.append(
                CohortTabVM(
                    cohort_key=name,
                    label=name,
                    n_closed=cohort_counts[name],
                    metrics=metrics,
                    is_active=(name == active_key),
                ),
            )
        # All-cohorts toggle: aggregate over hypothesis_label=None.
        all_metrics = compute_trade_process_metrics(conn, hypothesis_label=None)
        tabs.append(
            CohortTabVM(
                cohort_key=ALL_COHORTS_KEY,
                label="All closed trades",
                n_closed=all_metrics.n_closed,
                metrics=all_metrics,
                is_active=(active_key == ALL_COHORTS_KEY),
            ),
        )
    finally:
        if own_conn:
            conn.close()

    return TradeProcessCardVM(
        session_date=action_session_for_run(datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,
        banner_resolve_link=banner_resolve_link,
        cohort_tabs=tuple(tabs),
        active_cohort_key=active_key,
    )
