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
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from swing.data.models import PatternEvaluation
from swing.data.repos import pattern_evaluations as evals_repo
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.patterns.foundation import current_stage
from swing.web.view_models.metrics.shared import BaseLayoutVM

log = logging.getLogger(__name__)


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
class VolumeProfileRow:
    """Gap B.2 (T-A.6c.3) — 30-session volume sum + 50d avg ratio surface.

    Per plan §G.3 Step 4: read OHLCV via the archive (window_days=80) +
    compute (a) 30-session sum from the latest 30 bars + (b) 50d avg from
    the preceding 50 bars + (c) ratio_pct = 100.0 * (recent_avg /
    prior_avg) where recent_avg = recent_30session_volume_sum / 30.

    Non-negative validation via ``__post_init__`` per CLAUDE.md
    Literal-not-runtime-enforced gotcha + paired-discipline LOCK; ratio_pct
    is unbounded (can be 0 to >>100).
    """

    recent_30session_volume_sum: int
    prior_50day_avg_volume: float
    ratio_pct: float

    def __post_init__(self) -> None:
        if self.recent_30session_volume_sum < 0:
            raise ValueError(
                "VolumeProfileRow.recent_30session_volume_sum must be "
                f"non-negative; got {self.recent_30session_volume_sum!r}"
            )
        if self.prior_50day_avg_volume < 0:
            raise ValueError(
                "VolumeProfileRow.prior_50day_avg_volume must be "
                f"non-negative; got {self.prior_50day_avg_volume!r}"
            )


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
    # Gap B.2 (T-A.6c.3): structured volume profile surface. None when
    # archive empty or insufficient bars (<50 prior).
    volume_profile: VolumeProfileRow | None = None
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
    current_evaluation_id: int | None = None,
    composite_score: float | None = None,
    cohort_limit: int = 20,
) -> tuple[OutcomeDistributionRow, ...]:
    """Gap B.4 (T-A.6c.4) outcome distribution per spec section 5.10 item 8.

    Cohort = "last N similar-score candidates" per spec — evaluations with
    composite_score in ``[score - 0.1, score + 0.1]`` for the SAME
    pattern_class, ordered by pe.id DESC + LIMIT N. The CTE picks the N
    cohort evaluations FIRST; the outer query LEFT JOINs trades for
    outcome bucketing per OQ-6:

    - ``reached_1r``: trade.state IN ('closed','reviewed') AND
      realized_R_if_plan_followed >= 1.0 (V1 proxy; the more precise
      max(daily_high since entry) >= entry + (entry - stop) is V2; the
      realized-R surrogate is bias-equivalent for cohort statistics).
    - ``hit_stop``: trade.state IN ('closed','reviewed') AND
      realized_R_if_plan_followed < 0.

    Suppression at n<5 per Phase 10 honesty.suppress_for_n (V1 simplified
    to a numeric guard since the per-cohort n is bounded by the cohort
    LIMIT not the universe-of-exemplars).

    When called without ``current_evaluation_id`` / ``composite_score`` (older
    callers / partial fixtures), falls back to the pattern_class-only V1
    triggered-only surface (backward compat).
    """
    if current_evaluation_id is None or composite_score is None:
        # Backward-compat (V1 triggered-only).
        n_row = conn.execute(
            "SELECT COUNT(*) FROM pattern_exemplars "
            "WHERE proposed_pattern_class = ? "
            "  AND label_source IN ('closed_loop_review',"
            " 'organic_trade_history', 'curated_gold')",
            (pattern_class,),
        ).fetchone()
        n = int(n_row[0]) if n_row else 0
        if n == 0:
            return (OutcomeDistributionRow(pattern_class=pattern_class, n=0),)
        confirmed_row = conn.execute(
            "SELECT COUNT(*) FROM pattern_exemplars "
            "WHERE proposed_pattern_class = ? "
            "  AND label_source IN ('closed_loop_review',"
            " 'organic_trade_history', 'curated_gold') "
            "  AND final_decision = 'confirmed'",
            (pattern_class,),
        ).fetchone()
        confirmed = int(confirmed_row[0]) if confirmed_row else 0
        triggered_pct = (confirmed / n) * 100.0 if n > 0 else None
        return (OutcomeDistributionRow(
            pattern_class=pattern_class, n=n,
            triggered_pct=triggered_pct,
        ),)

    # Gap B.4 cohort + outcome bucketing per plan §D.3 SQL skeleton.
    # CTE picks N cohort evaluations FIRST (LIMIT at evaluation unit per
    # R4 MAJOR #1 LOCK), then LEFT JOIN trades for per-evaluation
    # aggregation. MAX(CASE ...) ensures one row per cohort evaluation
    # regardless of trade JOIN cardinality (Expansion #8 unit lock).
    score_low = composite_score - 0.1
    score_high = composite_score + 0.1
    cohort_rows = conn.execute(
        """
        WITH cohort AS (
            SELECT pe.id AS evaluation_id, pe.composite_score, pe.ticker,
                   pe.pipeline_run_id
            FROM pattern_evaluations pe
            WHERE pe.pattern_class = ?
              AND pe.composite_score BETWEEN ? AND ?
              AND pe.id != ?
            ORDER BY pe.id DESC
            LIMIT ?
        )
        SELECT cohort.evaluation_id,
               MAX(CASE WHEN t.id IS NOT NULL THEN 1 ELSE 0 END)
                 AS has_trade,
               MAX(CASE WHEN t.id IS NOT NULL
                        AND t.state IN ('closed', 'reviewed')
                        AND t.realized_R_if_plan_followed IS NOT NULL
                        AND t.realized_R_if_plan_followed >= 1.0
                        THEN 1 ELSE 0 END) AS reached_1r,
               MAX(CASE WHEN t.id IS NOT NULL
                        AND t.state IN ('closed', 'reviewed')
                        AND t.realized_R_if_plan_followed IS NOT NULL
                        AND t.realized_R_if_plan_followed < 0
                        THEN 1 ELSE 0 END) AS hit_stop
        FROM cohort
        LEFT JOIN candidates c
            ON c.ticker = cohort.ticker
           AND c.evaluation_run_id = (
               SELECT evaluation_run_id FROM pipeline_runs
               WHERE id = cohort.pipeline_run_id)
        LEFT JOIN trades t ON t.candidate_id = c.id
        GROUP BY cohort.evaluation_id
        """,
        (
            pattern_class, score_low, score_high, current_evaluation_id,
            cohort_limit,
        ),
    ).fetchall()
    cohort_n = len(cohort_rows)
    if cohort_n < 5:
        # Suppression at n<5 per honesty discipline.
        # Still expose triggered_pct via the legacy fallback so the
        # surface degrades gracefully (per spec the legacy text is
        # NOT suppressed below 5; reached_1r + hit_stop ARE suppressed).
        # Compute legacy triggered fraction over confirmed exemplars.
        n_row = conn.execute(
            "SELECT COUNT(*) FROM pattern_exemplars "
            "WHERE proposed_pattern_class = ? "
            "  AND label_source IN ('closed_loop_review',"
            " 'organic_trade_history', 'curated_gold')",
            (pattern_class,),
        ).fetchone()
        n_exemplars = int(n_row[0]) if n_row else 0
        confirmed = 0
        triggered_pct: float | None = None
        if n_exemplars > 0:
            confirmed_row = conn.execute(
                "SELECT COUNT(*) FROM pattern_exemplars "
                "WHERE proposed_pattern_class = ? "
                "  AND label_source IN ('closed_loop_review',"
                " 'organic_trade_history', 'curated_gold') "
                "  AND final_decision = 'confirmed'",
                (pattern_class,),
            ).fetchone()
            confirmed = int(confirmed_row[0]) if confirmed_row else 0
            triggered_pct = (confirmed / n_exemplars) * 100.0
        return (OutcomeDistributionRow(
            pattern_class=pattern_class,
            n=cohort_n,
            triggered_pct=triggered_pct,
            reached_1r_pct=None,
            hit_stop_pct=None,
        ),)

    reached_1r_count = sum(int(r[2]) for r in cohort_rows)
    hit_stop_count = sum(int(r[3]) for r in cohort_rows)
    reached_1r_pct = 100.0 * (reached_1r_count / cohort_n)
    hit_stop_pct = 100.0 * (hit_stop_count / cohort_n)
    # Triggered = fraction of cohort with any trade opened. V1 simplification:
    # use cohort has_trade aggregate as triggered proxy.
    triggered_count = sum(int(r[1]) for r in cohort_rows)
    triggered_pct = 100.0 * (triggered_count / cohort_n)
    return (OutcomeDistributionRow(
        pattern_class=pattern_class,
        n=cohort_n,
        triggered_pct=triggered_pct,
        reached_1r_pct=reached_1r_pct,
        hit_stop_pct=hit_stop_pct,
    ),)


def _compute_trend_template_state(
    conn: sqlite3.Connection, *, ticker: str, window_end_date: str,
) -> str:
    """Gap B.1 (T-A.6c.3) — V1 trend-template state via current_stage.

    Per plan §G.3 Step 3 + CLAUDE.md NEW gotcha #12
    (`date.fromisoformat()` cross-type-boundary discipline):
    ``pattern_evaluations.window_end_date`` is TEXT; ``current_stage``
    requires a ``date`` object. Wrap in try/except ValueError so a
    malformed window_end_date (rare; would indicate prior data corruption)
    falls back to 'undefined' + WARN logs rather than 500'ing the review
    form.
    """
    try:
        asof_date = date.fromisoformat(window_end_date)
    except (ValueError, TypeError) as exc:
        log.warning(
            "patterns_review_form: malformed window_end_date %r for "
            "ticker %s; falling back to trend_template_state='undefined' "
            "(exception: %s)",
            window_end_date, ticker, exc,
        )
        return "undefined"
    try:
        return current_stage(conn, ticker, asof_date)
    except Exception as exc:  # defense-in-depth; current_stage is read-only
        log.warning(
            "patterns_review_form: current_stage(%s, %s) raised %s; "
            "falling back to 'undefined'",
            ticker, window_end_date, exc,
        )
        return "undefined"


def _compute_volume_profile(
    *, cfg, ticker: str,
) -> VolumeProfileRow | None:
    """Gap B.2 (T-A.6c.3) — V1 volume profile via OHLCV archive.

    Per plan §G.3 Step 4: read OHLCV via ``read_or_fetch_archive``
    (window_days=80) + compute 30-session sum + 50d avg ratio. Returns
    None when archive empty or fewer than 80 bars available.
    """
    try:
        from datetime import datetime as _dt

        from swing.data.ohlcv_archive import read_or_fetch_archive
        from swing.evaluation.dates import last_completed_session

        end_date = last_completed_session(_dt.now())
        df = read_or_fetch_archive(
            ticker=ticker,
            end_date=end_date,
            cache_dir=cfg.paths.prices_cache_dir,
            archive_history_days=cfg.archive.archive_history_days,
        )
        if df is None or df.empty:
            return None
        if len(df) < 80:
            log.warning(
                "patterns_review_form: volume_profile insufficient bars "
                "for %s (have %d, need 80); skipping",
                ticker, len(df),
            )
            return None
        recent = df["Volume"].iloc[-30:].sum()
        prior_window = df["Volume"].iloc[-80:-30]
        prior_avg = float(prior_window.mean())
        recent_sum = int(recent)
        if prior_avg <= 0:
            return None
        recent_avg_per_day = recent_sum / 30.0
        ratio_pct = 100.0 * (recent_avg_per_day / prior_avg)
        return VolumeProfileRow(
            recent_30session_volume_sum=recent_sum,
            prior_50day_avg_volume=prior_avg,
            ratio_pct=ratio_pct,
        )
    except Exception as exc:  # fail-soft; missing archive must NOT 500
        log.warning(
            "patterns_review_form: volume_profile compute failed for "
            "%s: %s", ticker, exc,
        )
        return None


def build_patterns_review_form_vm(
    conn: sqlite3.Connection,
    *,
    candidate_id: int,
    session_date: str,
    cfg=None,
) -> PatternReviewFormVM | None:
    """Build the VM for the 8-item review surface. Returns None when the
    pattern_evaluations row does not exist (caller renders 404).

    Gap B.1 + B.2 (T-A.6c.3): when ``cfg`` is supplied, populates
    ``trend_template_state`` via ``current_stage`` + ``volume_profile``
    via OHLCV archive. Backward-compatible: ``cfg=None`` callers (older
    tests) get 'undefined' + ``volume_profile=None``.
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
        current_evaluation_id=candidate_id,
        composite_score=float(ev.composite_score),
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

    # Gap B.1 + B.2 (T-A.6c.3) live data when cfg supplied.
    trend_template_state = "n/a"
    volume_profile: VolumeProfileRow | None = None
    if cfg is not None:
        trend_template_state = _compute_trend_template_state(
            conn, ticker=ev.ticker, window_end_date=ev.window_end_date,
        )
        volume_profile = _compute_volume_profile(
            cfg=cfg, ticker=ev.ticker,
        )

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
        trend_template_state=trend_template_state,
        rs_rank=rs_rank,
        volume_profile_text="(not available)",
        volume_profile=volume_profile,
        outcome_distribution_rows=outcome_rows,
        structural_evidence_pretty=structural_pretty,
        geometric_score_pretty=geom_pretty,
    )
