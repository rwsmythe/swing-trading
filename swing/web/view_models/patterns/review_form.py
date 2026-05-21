"""Phase 13 T2.SB6b T-A.6.3 — ``/patterns/{candidate_id}/review`` view model.

Per plan G.9 T-A.6.3 + spec section 5.10 (lines 760-801): closed-loop
review surface backed by a ``pattern_evaluations`` row. Renders the 8-item
v2 brief 9.2 checklist plus the 6-decision form per spec lines 778-783.

Per L9 LOCK (T3.SB3 R1 M#2): the POST handler RECOMPUTES
``proposed_pattern_class`` from ``pattern_evaluations.pattern_class`` at
POST time; the VM exposes the recomputed value for GET render only +
no operator-supplied hidden input drives persistence.

Per L11 LOCK: extends ``BaseLayoutVM`` + populates banner fields via the
Phase 10 discrepancies helper.

Per L16 LOCK: ASCII-only narrative text.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from swing.data.models import PatternEvaluation
from swing.data.repos import pattern_evaluations as evals_repo
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class CriterionBreakdownRow:
    """One per-criterion breakdown row rendered in the geometric-score table.

    Drawn from ``pattern_evaluations.geometric_score_json`` ``criteria``
    list; ``result`` is one of pass/fail/marginal per spec section 5.10
    item 2.
    """

    name: str
    result: str  # 'pass' | 'fail' | 'marginal' | 'unknown'
    score: float | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        # Runtime validation per CLAUDE.md gotcha "Literal[...] not runtime-
        # enforced" — explicit frozenset gate replicating the type contract.
        _allowed = frozenset({"pass", "fail", "marginal", "unknown"})
        if self.result not in _allowed:
            raise ValueError(
                f"CriterionBreakdownRow.result must be one of {_allowed}; "
                f"got {self.result!r}"
            )


@dataclass(frozen=True)
class UncertaintyReasonRow:
    """One per-criterion uncertainty-reason row per spec section 5.10 item 7.

    Drawn from ``pattern_evaluations.structural_evidence_json.criteria_pass``
    (boolean per criterion) augmented with optional notes from the same
    payload's ``criteria_notes`` mapping. Defensive defaults so a row
    renders even when the upstream payload is partial.
    """

    name: str
    passed: bool
    note: str | None = None


@dataclass(frozen=True)
class OutcomeDistributionRow:
    """One per-pattern-class outcome bucket per spec section 5.10 item 8.

    Renders "of the last N similar-score candidates, X% triggered, Y%
    reached 1R, Z% hit stop". V1 fills triggered_pct = exemplars confirmed
    + organic_trade_history fraction; reached_1r_pct / hit_stop_pct
    populated when Phase 10 ``cohort.py`` resolves outcomes per pattern
    class (T-A.6.5 surfaces the deeper composition).
    """

    pattern_class: str
    n: int
    triggered_pct: float | None = None
    reached_1r_pct: float | None = None
    hit_stop_pct: float | None = None


@dataclass(frozen=True)
class PatternReviewFormVM(BaseLayoutVM):
    """VM for ``GET /patterns/{candidate_id}/review`` 8-item checklist
    surface + 6-decision form.

    L11 LOCK: extends ``BaseLayoutVM`` so the shared ``base.html.j2``
    layout renders without ``UndefinedError`` and the banner pin block
    populates from the Phase 10 discrepancies helper.
    """

    candidate_id: int = 0
    ticker: str = ""
    proposed_pattern_class: str = ""
    geometric_score: float = 0.0
    composite_score: float = 0.0
    template_match_score: float | None = None
    template_match_nearest_exemplar_ids: tuple[int, ...] = ()
    window_start_date: str = ""
    window_end_date: str = ""
    pipeline_run_id: int = 0
    # 8-item checklist surfaces.
    criterion_breakdown_rows: tuple[CriterionBreakdownRow, ...] = ()
    uncertainty_reason_rows: tuple[UncertaintyReasonRow, ...] = ()
    trend_template_state: str = "n/a"
    rs_rank: int | None = None
    volume_profile_text: str = "(not available)"
    outcome_distribution_rows: tuple[OutcomeDistributionRow, ...] = ()
    # Annotated chart bytes — None when the cache has no row OR the GET
    # render path skipped live render (V1 keeps the renderer at T-A.6.6
    # wiring; T-A.6.3 VM exposes the field so T-A.6.6 can populate without
    # a second VM hop).
    annotated_chart_svg_bytes: bytes | None = None
    structural_evidence_pretty: str = ""
    geometric_score_pretty: str = ""
    # action_form_values dict round-trips hidden anchors through soft-warn
    # confirm fragments. T2.SB6b ships ZERO soft-warn pathways for the
    # review form; reserved for future expansion.
    action_form_values: dict[str, str] = field(default_factory=dict)


def _parse_geometric_score_breakdown(
    geometric_score_json: str | None,
) -> tuple[CriterionBreakdownRow, ...]:
    if not geometric_score_json:
        return ()
    try:
        data = json.loads(geometric_score_json)
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, dict):
        return ()
    criteria = data.get("criteria") or []
    if not isinstance(criteria, list):
        return ()
    rows: list[CriterionBreakdownRow] = []
    for item in criteria:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        result = item.get("result", "unknown")
        if not isinstance(name, str) or not name:
            continue
        if result not in ("pass", "fail", "marginal", "unknown"):
            result = "unknown"
        score_val = item.get("score")
        score: float | None = (
            float(score_val)
            if isinstance(score_val, (int, float))
            else None
        )
        note_val = item.get("note")
        note = note_val if isinstance(note_val, str) and note_val else None
        rows.append(CriterionBreakdownRow(
            name=name, result=result, score=score, note=note,
        ))
    return tuple(rows)


def _parse_uncertainty_reasons(
    structural_evidence_json: str | None,
) -> tuple[UncertaintyReasonRow, ...]:
    if not structural_evidence_json:
        return ()
    try:
        data = json.loads(structural_evidence_json)
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, dict):
        return ()
    cp = data.get("criteria_pass") or {}
    notes = data.get("criteria_notes") or {}
    if not isinstance(cp, dict):
        return ()
    rows: list[UncertaintyReasonRow] = []
    for name, passed in cp.items():
        if not isinstance(name, str):
            continue
        if not isinstance(passed, bool):
            continue
        note_val = notes.get(name) if isinstance(notes, dict) else None
        note = note_val if isinstance(note_val, str) and note_val else None
        rows.append(UncertaintyReasonRow(
            name=name, passed=passed, note=note,
        ))
    return tuple(rows)


def _parse_template_match_ids(
    template_match_nearest_exemplar_ids_json: str | None,
) -> tuple[int, ...]:
    if not template_match_nearest_exemplar_ids_json:
        return ()
    try:
        data = json.loads(template_match_nearest_exemplar_ids_json)
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, list):
        return ()
    out: list[int] = []
    for x in data:
        if isinstance(x, int):
            out.append(x)
    # Top-3 per spec section 5.10 item 3.
    return tuple(out[:3])


def _lookup_rs_rank(
    conn: sqlite3.Connection, *, ticker: str, pipeline_run_id: int,
) -> int | None:
    """Look up RS rank from the most recent candidates row tied to the
    pipeline_run.
    """
    row = conn.execute(
        "SELECT rs_rank FROM candidates "
        "JOIN pipeline_runs ON pipeline_runs.evaluation_run_id "
        "  = candidates.evaluation_run_id "
        "WHERE pipeline_runs.id = ? AND candidates.ticker = ? "
        "ORDER BY candidates.id DESC LIMIT 1",
        (pipeline_run_id, ticker),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return int(row[0])


def _build_outcome_distribution(
    conn: sqlite3.Connection, *, pattern_class: str,
) -> tuple[OutcomeDistributionRow, ...]:
    """V1 outcome distribution from pattern_exemplars; T-A.6.5 metric tile
    surfaces the deeper Phase 10 cohort composition.

    The review form's surface is intentionally light — a single row for
    the current pattern_class showing n + confirmed/relabeled mix. The
    9th metric tile at T-A.6.5 carries the cross-pattern view + the 1R /
    stop bucketing per Phase 10.
    """
    n_row = conn.execute(
        "SELECT COUNT(*) FROM pattern_exemplars "
        "WHERE proposed_pattern_class = ? "
        "  AND label_source IN ('closed_loop_review', 'organic_trade_history',"
        " 'curated_gold')",
        (pattern_class,),
    ).fetchone()
    n = int(n_row[0]) if n_row else 0
    if n == 0:
        return (OutcomeDistributionRow(pattern_class=pattern_class, n=0),)
    confirmed_row = conn.execute(
        "SELECT COUNT(*) FROM pattern_exemplars "
        "WHERE proposed_pattern_class = ? "
        "  AND label_source IN ('closed_loop_review', 'organic_trade_history',"
        " 'curated_gold') "
        "  AND final_decision = 'confirmed'",
        (pattern_class,),
    ).fetchone()
    confirmed = int(confirmed_row[0]) if confirmed_row else 0
    triggered_pct = (confirmed / n) * 100.0 if n > 0 else None
    return (OutcomeDistributionRow(
        pattern_class=pattern_class, n=n,
        triggered_pct=triggered_pct,
    ),)


def build_patterns_review_form_vm(
    conn: sqlite3.Connection,
    *,
    candidate_id: int,
    session_date: str,
) -> PatternReviewFormVM | None:
    """Build the VM for the 8-item review surface. Returns None when the
    pattern_evaluations row does not exist (caller renders 404).
    """
    ev: PatternEvaluation | None = evals_repo.get_evaluation_by_id(
        conn, candidate_id,
    )
    if ev is None:
        return None
    breakdown = _parse_geometric_score_breakdown(ev.geometric_score_json)
    uncertainty = _parse_uncertainty_reasons(ev.structural_evidence_json)
    template_ids = _parse_template_match_ids(
        ev.template_match_nearest_exemplar_ids_json,
    )
    rs_rank = _lookup_rs_rank(
        conn, ticker=ev.ticker, pipeline_run_id=ev.pipeline_run_id,
    )
    outcome_rows = _build_outcome_distribution(
        conn, pattern_class=ev.pattern_class,
    )
    # Pretty-prints (ASCII-only JSON for in-template inspection).
    try:
        structural_pretty = json.dumps(
            json.loads(ev.structural_evidence_json), indent=2, sort_keys=True,
        )
    except json.JSONDecodeError:
        structural_pretty = ev.structural_evidence_json or ""
    try:
        geom_pretty = json.dumps(
            json.loads(ev.geometric_score_json), indent=2, sort_keys=True,
        )
    except (json.JSONDecodeError, TypeError):
        geom_pretty = ev.geometric_score_json or ""

    return PatternReviewFormVM(
        session_date=session_date,
        unresolved_material_discrepancies_count=(
            count_unresolved_material(conn)
        ),
        recent_multi_leg_auto_correction_count=(
            count_recent_multi_leg_auto_corrections(conn)
        ),
        banner_resolve_link=(
            fetch_first_pending_ambiguity_resolve_link_path(conn)
        ),
        candidate_id=candidate_id,
        ticker=ev.ticker,
        proposed_pattern_class=ev.pattern_class,
        geometric_score=float(ev.geometric_score),
        composite_score=float(ev.composite_score),
        template_match_score=ev.template_match_score,
        template_match_nearest_exemplar_ids=template_ids,
        window_start_date=ev.window_start_date,
        window_end_date=ev.window_end_date,
        pipeline_run_id=ev.pipeline_run_id,
        criterion_breakdown_rows=breakdown,
        uncertainty_reason_rows=uncertainty,
        trend_template_state="n/a",
        rs_rank=rs_rank,
        volume_profile_text="(not available)",
        outcome_distribution_rows=outcome_rows,
        structural_evidence_pretty=structural_pretty,
        geometric_score_pretty=geom_pretty,
    )
