"""Phase 13 T2.SB1 T-A.1.6 + T2.SB6b T-A.6.6b — ``/patterns/exemplars`` VM.

Per plan §G.1 T-A.1.6 + §A.3 base-layout VM banner pin + §A.18 discrepancies
helper hand-off LOCK + spec §5.9 step 5: operator spot-check surface for
silver-tier exemplars produced by ``swing patterns label-exemplars``.

T2.SB6b T-A.6.6b Deficiency 1 fold-in extends the VM with per-exemplar
chart SVG bytes + per-criterion PASS/FAIL table + narrative text. Reuses
the T-A.6.1 ``render_theme2_annotated_svg`` substrate renderer + T-A.6.2
``get_cached_chart_svg`` cache helper verbatim (L17 LOCK).

Operator actions per spec §5.9 step 5 (silver -> gold promotion + flips):
  - promote_to_gold: silver row's label_source flipped to ``curated_gold`` +
    ``gold_validated_at`` server-stamped.
  - reject: silver row's final_decision flipped to ``rejected``.
  - relabel: final_decision='relabeled' + operator-corrected
    ``final_pattern_class``.
  - watch: final_decision='watch'.

Banner field population per forward-binding lesson #12: every base-layout-
mounted VM populates ``unresolved_material_discrepancies_count`` +
``banner_resolve_link`` + ``recent_multi_leg_auto_correction_count`` so
``base.html.j2`` renders without ``UndefinedError``.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Literal

from swing.data.models import PatternExemplar
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM

# L15 LOCK: CriterionRow.status Literal type hint MUST have explicit
# runtime validation per CLAUDE.md gotcha "Literal[...] not runtime-
# enforced". Canonical frozenset below; __post_init__ checks against it.
_CRITERION_STATUS_VALUES: frozenset[str] = frozenset({"pass", "fail"})


@dataclass(frozen=True)
class CriterionRow:
    """One row of the per-criterion PASS/FAIL table per spec section 5.2
    through 5.6 criteria.

    Drawn from ``labeler_evidence_json.rule_criteria`` payload. The frozen
    dataclass + explicit ``__post_init__`` Literal validation defends
    against malformed payloads at construction time (per CLAUDE.md gotcha
    + L15 LOCK).
    """

    name: str
    status: Literal["pass", "fail"]
    evidence_value: str = ""
    threshold: str = ""
    tolerance: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _CRITERION_STATUS_VALUES:
            raise ValueError(
                "CriterionRow.status must be 'pass' or 'fail'; got "
                f"{self.status!r}"
            )


@dataclass(frozen=True)
class ExemplarRender:
    """Rendered per-exemplar payload for the enhanced exemplars surface.

    Carries the original ``PatternExemplar`` plus the Deficiency 1 fold-in
    fields. All optional + default empty/None so the template guards via
    ``{% if %}`` checks gracefully when payloads are absent or malformed.
    """

    exemplar: PatternExemplar
    chart_svg_bytes: bytes | None = None
    criterion_rows: tuple[CriterionRow, ...] = ()
    narrative_text: str | None = None


@dataclass(frozen=True)
class PatternExemplarsVM(BaseLayoutVM):
    """VM for ``GET /patterns/exemplars`` operator spot-check surface."""

    silver_rows: tuple[PatternExemplar, ...] = ()
    gold_rows: tuple[PatternExemplar, ...] = ()
    other_rows: tuple[PatternExemplar, ...] = ()
    total_count: int = 0
    # Empty-cohort advisory text per plan §A.16 + spec §5.10 graceful-at-n=0.
    empty_advisory: str | None = None
    # Phase 13 T2.SB1 LOCK: action_form_values dict round-trips hidden anchors
    # through soft-warn confirm fragments per Phase 9 Sub-bundle D Codex R3
    # Critical #1 closure (form-render hidden anchors must round-trip through
    # `form_values` dict so tampered force=true resubmits don't bypass).
    action_form_values: dict[str, str] = field(default_factory=dict)
    # Phase 13 T2.SB6b T-A.6.6b Deficiency 1 fold-in: per-exemplar enhanced
    # rendering keyed by exemplar.id. Empty mapping when no chart data
    # available; template guards each render via {% if %}.
    exemplar_renders: dict[int, ExemplarRender] = field(
        default_factory=dict,
    )


def _parse_criterion_rows(
    labeler_evidence_json: str | None,
) -> tuple[CriterionRow, ...]:
    """Parse the rule_criteria payload defensively per L17 LOCK + spec
    section A.16 graceful empty-state discipline.

    Accepted shapes (silver-tier subagent emission per spec section 5.7):
      [
        {"name": "stage_2", "status": "pass", "evidence_value": "...",
         "threshold": "...", "tolerance": "..."},
        ...
      ]
    Returns an empty tuple on JSON-decode failure, non-list payload, or
    rows with non-pass/non-fail status (per __post_init__ validation).
    """
    if not labeler_evidence_json:
        return ()
    try:
        data = json.loads(labeler_evidence_json)
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, dict):
        return ()
    rule_criteria = data.get("rule_criteria") or []
    if not isinstance(rule_criteria, list):
        return ()
    rows: list[CriterionRow] = []
    for item in rule_criteria:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        status = item.get("status")
        if not isinstance(name, str) or not name:
            continue
        if status not in ("pass", "fail"):
            continue
        evidence_value = item.get("evidence_value", "")
        threshold = item.get("threshold", "")
        tolerance_val = item.get("tolerance")
        try:
            rows.append(CriterionRow(
                name=name,
                status=status,  # type: ignore[arg-type]
                evidence_value=(
                    str(evidence_value) if evidence_value is not None
                    else ""
                ),
                threshold=str(threshold) if threshold is not None else "",
                tolerance=(
                    str(tolerance_val) if tolerance_val is not None
                    else None
                ),
            ))
        except ValueError:
            # Defensive: status validation should have already gated, but
            # the dataclass __post_init__ catches any straggler. Skip the
            # bad row rather than poison the entire surface.
            continue
    return tuple(rows)


def _parse_narrative_text(
    labeler_evidence_json: str | None,
) -> str | None:
    if not labeler_evidence_json:
        return None
    try:
        data = json.loads(labeler_evidence_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    narrative = data.get("narrative")
    if isinstance(narrative, str) and narrative:
        return narrative
    return None


def _lookup_most_recent_theme2_chart_svg(
    conn: sqlite3.Connection, *, ticker: str, pattern_class: str,
) -> bytes | None:
    """Look up the most recent ``theme2_annotated`` cache row for the
    given (ticker, pattern_class), regardless of pipeline_run_id.

    The substrate ``get_cached_chart_svg`` keys on pipeline_run_id — for
    the exemplars surface we want the most recent chart_renders row
    matching (ticker, surface, pattern_class) since the exemplar
    dataclass does NOT carry a pipeline_run_id pointer. Done in the VM
    builder (not the substrate) per L7 LOCK (substrate API FROZEN).
    """
    row = conn.execute(
        "SELECT chart_svg_bytes FROM chart_renders "
        "WHERE ticker = ? AND surface = 'theme2_annotated' "
        "  AND pattern_class = ? "
        "ORDER BY id DESC LIMIT 1",
        (ticker, pattern_class),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return bytes(row[0])


def _build_exemplar_render(
    conn: sqlite3.Connection, *, exemplar: PatternExemplar,
    bars_fetcher: object | None = None,
) -> ExemplarRender:
    """Build one ExemplarRender per spec section 4.6 + plan G.9 T-A.6.6b.

    Cache-hit path: reads bytes from chart_renders via the substrate
    cache table. Cache-miss path (per Codex R1 MAJOR #6 closure + plan
    G.9 T-A.6.6b acceptance #3 "renderer invoked once per cache miss"):
    if a ``bars_fetcher`` callable is injected by the route handler,
    fetch bars for the exemplar window + invoke
    ``render_theme2_annotated_svg`` once + surface the live bytes to
    the caller. The cache is NOT written back from this path (the
    canonical chart_renders cache key requires a pipeline_run_id anchor
    per spec section C.2 + ChartRender invariant; the exemplar has no
    such anchor). The pipeline's per-run chart-render step is the
    canonical cache write path; live renders here are read-through-only
    so a transient empty render bytes cannot blank a known-good cache
    row (F6 lesson preserved by structural impossibility).

    Per L17 LOCK: NO duplicate matplotlib code; renderer reuse via the
    substrate is the contract. ``bars_fetcher`` signature: callable
    accepting ``(ticker: str)`` and returning a pandas DataFrame OR
    None on unavailable.
    """
    cached_svg = _lookup_most_recent_theme2_chart_svg(
        conn, ticker=exemplar.ticker,
        pattern_class=exemplar.proposed_pattern_class,
    )
    rows = _parse_criterion_rows(exemplar.labeler_evidence_json)
    narrative = _parse_narrative_text(exemplar.labeler_evidence_json)

    if cached_svg is None and bars_fetcher is not None:
        # Cache miss + bars_fetcher injected: invoke the substrate
        # renderer once + write the bytes back to the cache.
        try:
            bars = bars_fetcher(exemplar.ticker)  # type: ignore[operator]
        except Exception:  # noqa: BLE001 - defense-in-depth
            bars = None
        if bars is not None and not bars.empty:
            try:
                from swing.data.models import (
                    ChartRender,
                    PatternEvaluation,
                )
                from swing.data.repos.chart_renders import (
                    refresh_chart_render,
                )
                from swing.web.charts import render_theme2_annotated_svg

                # Synthesize a PatternEvaluation from the exemplar fields
                # so the substrate annotation renderer can consume the
                # structural_evidence_json + window dates. The exemplar
                # does not carry geometric/composite/detector_version
                # fields; synthesize neutral defaults purely for the
                # render path.
                synth_pe = PatternEvaluation(
                    id=None,
                    pipeline_run_id=0,
                    ticker=exemplar.ticker,
                    pattern_class=exemplar.proposed_pattern_class,
                    detector_version="exemplar_synthesized",
                    geometric_score=0.0,
                    geometric_score_json="{}",
                    composite_score=0.0,
                    structural_evidence_json=(
                        exemplar.structural_evidence_json or "{}"
                    ),
                    feature_distribution_log_json="{}",
                    window_start_date=exemplar.start_date,
                    window_end_date=exemplar.end_date,
                    created_at=exemplar.created_at,
                )
                live_svg = render_theme2_annotated_svg(
                    ticker=exemplar.ticker,
                    bars=bars,
                    pattern_evaluation=synth_pe,
                )
                # Cache NOT written back per docstring contract above —
                # the canonical chart_renders cache key requires a
                # pipeline_run_id anchor (spec section C.2 + ChartRender
                # invariant). Live bytes serve the operator's request;
                # the pipeline's per-run chart-render step is the
                # canonical cache write path. V2 candidate banked:
                # pipeline-run-agnostic exemplar cache key shape.
                cached_svg = live_svg
                del refresh_chart_render, ChartRender  # noqa
            except Exception:  # noqa: BLE001 - degraded fallback
                cached_svg = None

    return ExemplarRender(
        exemplar=exemplar,
        chart_svg_bytes=cached_svg,
        criterion_rows=rows,
        narrative_text=narrative,
    )


def build_patterns_exemplars_vm(
    conn: sqlite3.Connection,
    *,
    session_date: str,
    bars_fetcher: object | None = None,
) -> PatternExemplarsVM:
    """Build the VM for the operator spot-check surface.

    Per §A.3 + forward-binding lesson #12: populates banner fields from the
    Phase 10 discrepancies helper at construction time so the
    ``base.html.j2`` banner block renders without ``UndefinedError``.

    T2.SB6b T-A.6.6b Deficiency 1 fold-in: builds per-exemplar enhanced
    renders for silver + gold rows (other tiers skip enhanced render;
    they're not the operator review focus). ``bars_fetcher`` optional
    callable per Codex R1 MAJOR #6 closure: when injected, cache-miss
    paths invoke ``render_theme2_annotated_svg`` once per exemplar.
    """
    all_rows = exemplars_repo.list_exemplars(conn)
    silver = tuple(
        r for r in all_rows
        if r.label_source in ("claude_silver", "codex_silver")
    )
    gold = tuple(r for r in all_rows if r.label_source == "curated_gold")
    other = tuple(
        r for r in all_rows
        if r.label_source not in (
            "claude_silver", "codex_silver", "curated_gold",
        )
    )

    empty_advisory: str | None = None
    if not all_rows:
        empty_advisory = (
            "No exemplars yet. Run `swing patterns label-exemplars` "
            "(per Phase 13 T-A.1.5) to bootstrap a silver-tier corpus."
        )

    exemplar_renders: dict[int, ExemplarRender] = {}
    for r in (*silver, *gold):
        if r.id is None:
            continue
        exemplar_renders[r.id] = _build_exemplar_render(
            conn, exemplar=r, bars_fetcher=bars_fetcher,
        )

    return PatternExemplarsVM(
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
        silver_rows=silver,
        gold_rows=gold,
        other_rows=other,
        total_count=len(all_rows),
        empty_advisory=empty_advisory,
        exemplar_renders=exemplar_renders,
    )
