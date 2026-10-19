"""22-F T-D0 -- the INV-MODEL roster and its AST closure (plan section 5, T-D0;
R1-03, R52; section 1.2 row 11).

The ROSTER is the 118 distinct INV-MODEL origin functions of the pinned
``triage.json`` (sha256 ``b18eb936b1ffe4bb81595aa16768351449915295ecc7f7f78c9158fde955cb13``,
bytes hashed before derivation; the file lives in the durable evidence dir,
NOT the checkout).  It is COMMITTED here so this test reads nothing outside
the repository (R2-01 as ruled).  Each member is classified by a READ of the
objects it validates (the constructing lines are recorded in the executing
ledger):

* ``persisted`` -- the object is built from a DB row (a ``_row_to_*`` mapper
  or a repo/reader row loop constructs it).  Each persisted member's quoted
  CHECK/trigger (migration file:line + the Python mirror line) is in the
  executing ledger; a persisted member with none is FND-3 there, by name.
* ``computed`` -- otherwise (view models, ``metrics/*``, ``config``, API and
  operator-input objects).  These are FND-4, by name, in the executing ledger.

THE CLOSURE (both directions).  P = every module- or class-level function in
``swing/**/*.py`` named ``__post_init__`` / ``_require_*`` / ``_validate_*``
whose body contains a ``Raise``.  P must EQUAL the roster's pattern-named
members UNION ``UNREACHED`` (a reasoned exclusion map), and every roster and
``UNREACHED`` key must resolve to a real function -- a stale entry FAILS.  The
three roster members named by ``triage.py`` rather than by the pattern
(``NAME_LISTED``) are checked for existence only.  A NEW raising validator
lands in neither list and turns this RED: its author must classify it.

LATER-ARC ADDITIONS.  ``ROSTER`` stays exactly the pinned 118; a raising
validator an arc ADDS after the pin is classified by that arc in
``LATER_ARC_ROSTER`` (same ``persisted``/``computed`` vocabulary, each entry
with the arc and the constructing site in a comment), and the closure reads
the union.

DECLARED BOUND (a limit, not an exemption): the ``UNREACHED`` reasons are
verified by the census instrument (``escape_census.py``, outside the repo) at
commit time, not by this test.  This test proves MEMBERSHIP, not
reachability.
"""
from __future__ import annotations

import ast

from tests._22f_ast import REPO_ROOT, iter_sources

_PATTERN_PREFIXES = ("_require_", "_validate_")

_UNREACHED_REASON = (
    "no operator root reaches it in the census call graph (`escape_census.py`)")

# Named by `triage.py:8` rather than by the pattern; existence-checked only.
NAME_LISTED = frozenset({
    "data.models._provenance_snapshot_dict",
    "metrics.honesty._check_finite",
    "monitoring.tool_health.worst_of",
})

ROSTER: dict[str, str] = {
    "config.LatchesConfig.__post_init__": "computed",
    "config.PipelineConfig.__post_init__": "computed",
    "config.SchwabIntegrationConfig.__post_init__": "computed",
    "config.StopAdvisoryConfig.__post_init__": "computed",
    "data.models.AccountEquitySnapshot.__post_init__": "persisted",
    "data.models.CashMovement.__post_init__": "persisted",
    "data.models.ChartRender.__post_init__": "persisted",
    "data.models.Fill.__post_init__": "persisted",
    "data.models.HypothesisStatusHistory.__post_init__": "persisted",
    "data.models.LatchOrderIntent._validate_dates": "persisted",
    "data.models.LatchOrderIntent._validate_enums": "persisted",
    "data.models.LatchOrderIntent._validate_kind_conditionals": "persisted",
    "data.models.LatchOrderIntent._validate_scalars": "persisted",
    "data.models.LatchOrderIntent._validate_shape_exclusion": "persisted",
    "data.models.LatchOrderIntent._validate_validity_columns": "persisted",
    "data.models.LatchViewEvent.__post_init__": "persisted",
    "data.models.PatternDetectionEvent.__post_init__": "persisted",
    "data.models.PatternEvaluation.__post_init__": "persisted",
    "data.models.PatternExemplar.__post_init__": "persisted",
    "data.models.PatternForwardObservation.__post_init__": "persisted",
    "data.models.ProvenanceCorrection.__post_init__": "persisted",
    "data.models.ReconciliationDiscrepancy.__post_init__": "persisted",
    "data.models.ReconciliationRun.__post_init__": "persisted",
    "data.models.RiskPolicy.__post_init__": "persisted",
    "data.models.SchwabApiCall.__post_init__": "persisted",
    "data.models.Trade.__post_init__": "persisted",
    "data.models._provenance_snapshot_dict": "persisted",
    "data.models._require_audit_timestamp": "persisted",
    "data.models._require_broker_snapshot_envelope": "persisted",
    "data.models._require_extended_iso_date": "persisted",
    "data.models._require_iso_seconds_ts": "persisted",
    "data.models._require_iso_session_date": "persisted",
    "data.models._require_snapshot_fields": "persisted",
    "data.models._require_utc_conversion": "persisted",
    "data.models._require_value_envelope": "persisted",
    "data.repos.trades._validate_chart_pattern_invariant": "computed",
    "data.yfinance_audit_context._validate_install": "computed",
    "latches.classification.LatchDisposition.__post_init__": "computed",
    "latches.classification.TelemetryHealth.__post_init__": "computed",
    "latches.identity.LatchIdentity.__post_init__": "computed",
    "latches.identity._require_positive_int": "computed",
    "latches.models.DegradedFire.__post_init__": "computed",
    "latches.models.Latch.__post_init__": "computed",
    "latches.models.Latch._validate_lapse_diagnostics": "computed",
    "latches.models.SessionStructuralVerdict.__post_init__": "computed",
    "latches.models._require_finite_number": "computed",
    "latches.models._require_positive_int": "persisted",
    "latches.order_intent.OrderDelta.__post_init__": "computed",
    "metrics.capital.CapitalFrictionResult.__post_init__": "computed",
    "metrics.capital.CapitalFrictionTrendPoint.__post_init__": "computed",
    "metrics.funnel.IdentificationFunnelPoint.__post_init__": "computed",
    "metrics.funnel.IdentificationFunnelResult.__post_init__": "computed",
    "metrics.honesty.BootstrapCI.__post_init__": "computed",
    "metrics.honesty.SuppressedMetric.__post_init__": "computed",
    "metrics.honesty.WilsonCI.__post_init__": "computed",
    "metrics.honesty._check_finite": "computed",
    "metrics.maturity.MaturityStageResult.__post_init__": "computed",
    "metrics.maturity.MaturityStageRow.__post_init__": "computed",
    "metrics.process.MetricCellA.__post_init__": "computed",
    "metrics.process.MetricCellB.__post_init__": "computed",
    "metrics.process.MetricCellC.__post_init__": "computed",
    "metrics.process.PointMetricCell.__post_init__": "computed",
    "metrics.process.TradeProcessMetricsResult.__post_init__": "computed",
    "metrics.process._TradeMetricInputs.__post_init__": "computed",
    "metrics.process_grade_trend.ProcessGradeTrendPoint.__post_init__": "computed",
    "metrics.process_grade_trend.ProcessGradeTrendResult.__post_init__": "computed",
    "metrics.process_grade_trend.RollingLinePoint.__post_init__": "computed",
    "metrics.process_grade_trend.RollingMetricSeries.__post_init__": "computed",
    "metrics.tier.CohortStatistics.__post_init__": "computed",
    "metrics.tier.DeviationOutcomeResult.__post_init__": "computed",
    "metrics.tier.DeviationOutcomeRow.__post_init__": "computed",
    "metrics.tier.TierComparisonResult.__post_init__": "computed",
    "monitoring.research_health.ResearchHealthCheck.__post_init__": "computed",
    "monitoring.research_health.ResearchHealthStatus.__post_init__": "computed",
    "monitoring.tool_health.worst_of": "computed",
    "patterns.active_learning.CandidatePriority.__post_init__": "computed",
    "trades.entry.EntryRequest.__post_init__": "computed",
    "trades.entry_auto_fill.EntryAutoFillResult.__post_init__": "computed",
    "trades.exit_auto_fill.ExitAutoFillCandidate.__post_init__": "computed",
    "trades.exit_auto_fill.ExitAutoFillResult.__post_init__": "computed",
    "trades.latched_origin.LatchedProvenance.__post_init__": "computed",
    "trades.reconciliation_auto_correct._require_custom_value": "computed",
    "trades.reconciliation_auto_correct._validate_correction_target": "computed",
    "trades.reconciliation_auto_correct._validate_override_combo": "computed",
    "trades.review.ReviewPriors.__post_init__": "computed",
    "web.price_cache.PriceSnapshot.__post_init__": "computed",
    "web.view_models.account.AccountSnapshotFormVM.__post_init__": "computed",
    "web.view_models.config.ConfigPageVM.__post_init__": "computed",
    "web.view_models.dashboard.DashboardVM.__post_init__": "computed",
    "web.view_models.journal.JournalVM.__post_init__": "computed",
    "web.view_models.journal.TradeDrilldownVM.__post_init__": "computed",
    "web.view_models.metrics.capital_friction.CapitalFrictionVM.__post_init__": "computed",
    "web.view_models.metrics.deviation_outcome.DeviationOutcomeVM.__post_init__": "computed",
    "web.view_models.metrics.hypothesis_progress_card.CohortProgressVM.__post_init__": "computed",
    "web.view_models.metrics.hypothesis_progress_card.HypothesisProgressCardVM.__post_init__":
        "computed",
    "web.view_models.metrics.identification_funnel.IdentificationFunnelVM.__post_init__":
        "computed",
    "web.view_models.metrics.maturity_stage.MaturityStageVM.__post_init__": "computed",
    "web.view_models.metrics.process_grade_trend.ProcessGradeTrendVM.__post_init__": "computed",
    "web.view_models.metrics.process_grade_trend.RollingSeriesDisplay.__post_init__": "computed",
    "web.view_models.metrics.tier_comparison.TierComparisonVM.__post_init__": "computed",
    "web.view_models.metrics.trade_process_card.CohortTabVM.__post_init__": "computed",
    "web.view_models.metrics.trade_process_card.TradeProcessCardVM.__post_init__": "computed",
    "web.view_models.patterns.review_form.CriterionBreakdownRow.__post_init__": "computed",
    "web.view_models.pipeline.PipelineVM.__post_init__": "computed",
    "web.view_models.reconcile.ReconcileDiscrepancyErrorVM.__post_init__": "computed",
    "web.view_models.reconcile.ReconcileEquityDeltaDiagnosticVM.__post_init__": "computed",
    "web.view_models.reconcile.ReconcileOrphanAcknowledgeVM.__post_init__": "computed",
    "web.view_models.reconcile.ReconcileSimpleAcknowledgeVM.__post_init__": "computed",
    "web.view_models.schwab.SchwabCallSummary.__post_init__": "computed",
    "web.view_models.schwab.SchwabSetupErrorVM.__post_init__": "computed",
    "web.view_models.schwab.SchwabSetupVM.__post_init__": "computed",
    "web.view_models.schwab.SchwabStatusVM.__post_init__": "computed",
    "web.view_models.trades.CadenceCompleteVM.__post_init__": "computed",
    "web.view_models.trades.DiscrepancyDisplay.__post_init__": "computed",
    "web.view_models.trades.ReviewVM.__post_init__": "computed",
    "web.view_models.trades.ReviewsPendingVM.__post_init__": "computed",
    "web.view_models.trades.TradeDetailVM.__post_init__": "computed",
    "web.view_models.watchlist.WatchlistVM.__post_init__": "computed",
}

# Raising validators ADDED after the pinned triage (see the module docstring).
LATER_ARC_ROSTER: dict[str, str] = {
    # D79 T4: built only by `exit_auto_fill.exit_record_flags` from the exit
    # POST's typed values and the submitted map (computed, never from a DB
    # row); reached from the web exit POST only (the CLI `trade exit` formats
    # the value-tuple text directly and never constructs the flag).
    "trades.exit_auto_fill.ExitRecordFlag.__post_init__": "computed",
}

UNREACHED: dict[str, str] = {
    "cli._validate_diagnose_db_path": _UNREACHED_REASON,
    "data.models.EntryIntentAttestation.__post_init__": _UNREACHED_REASON,
    "data.models.LatchOrderMandateLink.__post_init__": _UNREACHED_REASON,
    "data.models.WatchlistCloseTrackFlag.__post_init__": _UNREACHED_REASON,
    "data.models.WatchlistCloseTrackFlagEvent.__post_init__": _UNREACHED_REASON,
    "data.models.YfinanceCall.__post_init__": _UNREACHED_REASON,
    "integrations.schwab.marketdata_ladder._validate_ticker": _UNREACHED_REASON,
    "integrations.schwab.models.OhlcvBar.__post_init__": _UNREACHED_REASON,
    "integrations.schwab.models.SchwabAccountResponse.__post_init__": _UNREACHED_REASON,
    "integrations.schwab.models.SchwabExecutionLeg.__post_init__": _UNREACHED_REASON,
    "integrations.schwab.models.SchwabOrderResponse.__post_init__": _UNREACHED_REASON,
    "integrations.schwab.models.SchwabPriceHistoryWindow.__post_init__": _UNREACHED_REASON,
    "integrations.schwab.models.SchwabQuoteResponse.__post_init__": _UNREACHED_REASON,
    "integrations.schwab.models.SchwabTransactionResponse.__post_init__": _UNREACHED_REASON,
    "latches.constants.DerivationField.__post_init__": _UNREACHED_REASON,
    "latches.models.DailyBar.__post_init__": _UNREACHED_REASON,
    "latches.models.EntryRecord.__post_init__": _UNREACHED_REASON,
    "latches.models.FireRow.__post_init__": _UNREACHED_REASON,
    "latches.models.OrderAlarm.__post_init__": _UNREACHED_REASON,
    "latches.models.OrdersResolution.__post_init__": _UNREACHED_REASON,
    "latches.models.RestingOrder.__post_init__": _UNREACHED_REASON,
    "latches.order_intent.PreparedOrderResult.__post_init__": _UNREACHED_REASON,
    "monitoring.stoplights.Stoplight.__post_init__": _UNREACHED_REASON,
    "monitoring.tool_health.ToolHealthCheck.__post_init__": _UNREACHED_REASON,
    "monitoring.tool_health.ToolHealthStatus.__post_init__": _UNREACHED_REASON,
    "patterns.cup_with_handle.CupWithHandleEvidence.__post_init__": _UNREACHED_REASON,
    "patterns.double_bottom_w.DoubleBottomWEvidence.__post_init__": _UNREACHED_REASON,
    "patterns.drift_logging.FeatureDistributionLog.__post_init__": _UNREACHED_REASON,
    "patterns.flat_base.FlatBaseEvidence.__post_init__": _UNREACHED_REASON,
    "patterns.foundation.CandidateWindow.__post_init__": _UNREACHED_REASON,
    "patterns.foundation.Swing.__post_init__": _UNREACHED_REASON,
    "patterns.high_tight_flag.HighTightFlagEvidence.__post_init__": _UNREACHED_REASON,
    "patterns.labeling.CodexReviewResponse.__post_init__": _UNREACHED_REASON,
    "patterns.labeling.RetroactiveCodexSelection.__post_init__": _UNREACHED_REASON,
    "patterns.labeling.SilverLabelResponse.__post_init__": _UNREACHED_REASON,
    "patterns.labeling._validate_rule_criteria": _UNREACHED_REASON,
    "patterns.labeling._validate_silver_confidence": _UNREACHED_REASON,
    "patterns.labeling._validate_silver_evaluation": _UNREACHED_REASON,
    "patterns.template_matching.TemplateMatchExemplar.__post_init__": _UNREACHED_REASON,
    "patterns.template_matching.TemplateMatchHit.__post_init__": _UNREACHED_REASON,
    "patterns.vcp.VCPEvidence.__post_init__": _UNREACHED_REASON,
    "trades.cohort_provenance_correction._require_naive_datetime": _UNREACHED_REASON,
    "trades.cohort_provenance_correction._require_session_date": _UNREACHED_REASON,
    "trades.entry_date_correction._validate_target_date": _UNREACHED_REASON,
    "trades.exit_auto_fill.PossibleDuplicateFill.__post_init__": _UNREACHED_REASON,
    "web.ohlcv_cache.OhlcvBundle.__post_init__": _UNREACHED_REASON,
    "web.view_models.error.PageErrorVM.__post_init__": _UNREACHED_REASON,
    "web.view_models.metrics.hypothesis_progress_card.TransitionEntry.__post_init__":
        _UNREACHED_REASON,
    "web.view_models.metrics.shared.BaseLayoutVM.__post_init__": _UNREACHED_REASON,
    "web.view_models.metrics.shared.SuppressionRowVM.__post_init__": _UNREACHED_REASON,
    "web.view_models.patterns.exemplars.CriterionRow.__post_init__": _UNREACHED_REASON,
    "web.view_models.patterns.review_form.VolumeProfileRow.__post_init__": _UNREACHED_REASON,
    "web.view_models.reconcile.ReconcileDiscrepancyResolveVM.__post_init__": _UNREACHED_REASON,
}


def _module_name(rel_path: str) -> str:
    """``swing/data/models.py`` -> ``data.models`` (the roster's naming, which
    drops the ``swing.`` prefix); a package ``__init__`` names the package."""
    parts = rel_path[:-len(".py")].split("/")[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_pattern_name(name: str) -> bool:
    return name == "__post_init__" or name.startswith(_PATTERN_PREFIXES)


def _walk(root=REPO_ROOT) -> tuple[set[str], set[str]]:
    """Return ``(P, every)``: P = the raising pattern-named module/class-level
    functions; ``every`` = every module/class-level function's dotted name
    (for the existence check).  Nested classes count as class level; a def
    inside a def does not."""
    raising: set[str] = set()
    every: set[str] = set()

    def visit(body, prefix: list[str]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                visit(node.body, prefix + [node.name])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                dotted = ".".join(prefix + [node.name])
                every.add(dotted)
                if _is_pattern_name(node.name) and any(
                        isinstance(sub, ast.Raise) for sub in ast.walk(node)):
                    raising.add(dotted)

    for rel, tree, _lines in iter_sources(root, ("swing/**/*.py",)):
        visit(tree.body, [_module_name(rel)])
    return raising, every


def _pattern_members(names) -> set[str]:
    return {n for n in names if _is_pattern_name(n.rsplit(".", 1)[-1])}


def test_roster_and_unreached_are_well_formed() -> None:
    assert len(ROSTER) == 118
    assert len(UNREACHED) == 53
    assert set(ROSTER.values()) <= {"persisted", "computed"}
    assert not set(ROSTER) & set(UNREACHED)
    assert set(LATER_ARC_ROSTER.values()) <= {"persisted", "computed"}
    assert not set(LATER_ARC_ROSTER) & (set(ROSTER) | set(UNREACHED))
    assert _pattern_members(LATER_ARC_ROSTER) == set(LATER_ARC_ROSTER)
    assert NAME_LISTED <= set(ROSTER)
    assert set(ROSTER) - _pattern_members(ROSTER) == NAME_LISTED
    assert _pattern_members(UNREACHED) == set(UNREACHED)
    assert set(UNREACHED.values()) == {_UNREACHED_REASON}


def test_every_roster_and_unreached_key_resolves_to_a_real_function() -> None:
    _raising, every = _walk()
    stale = sorted((set(ROSTER) | set(UNREACHED) | set(LATER_ARC_ROSTER))
                   - every)
    assert not stale, (
        "roster/UNREACHED entries that no longer name a function in swing/ "
        f"(remove or re-point them): {stale}")


def test_raising_validator_set_equals_roster_union_unreached() -> None:
    raising, _every = _walk()
    declared = (_pattern_members(ROSTER) | set(UNREACHED)
                | set(LATER_ARC_ROSTER))
    unclassified = sorted(raising - declared)
    no_longer_raising = sorted(declared - raising)
    assert not unclassified, (
        "NEW raising validator(s) not classified -- ROSTER is the pinned 118 "
        "and is never extended; classify each into LATER_ARC_ROSTER "
        "(persisted with its CHECK/trigger quote, or computed -> FND-4), with "
        "the adding arc and the constructing site in a comment, or into "
        f"UNREACHED with the census reason: {unclassified}")
    assert not no_longer_raising, (
        "declared validator(s) that no longer raise (or no longer match the "
        f"pattern): {no_longer_raising}")
