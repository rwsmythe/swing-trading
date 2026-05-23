"""Sensitivity sweep: 1D parameter-sweep over persisted ``candidate_criteria``.

For each (variable, sweep_point) pair, substitute the variable's value into
the per-candidate bucket recomputation and emit ``SweepEntry`` counts.

This is a first-order approximation -- cross-coupling between variables is
acknowledged but NOT modeled (one variable at a time; others held at the
production cfg). Per Phase 13 T4.SB spec sec1.5.1 amendment for OQ-1.3.

V1 substitution semantics support two classes of variables:

  - **Gate variables** (``trend_template.min_passes``, ``vcp.watch_max_fails``):
    full bucket-level resimulation -- substitute the gate value + walk
    ``bucket_for`` semantics including the ``allowed_miss_names`` invariant.
  - **Threshold variables** (15 = 3 trend_template + 8 vcp + 1 risk + 3 rs):
    V1 LIMITATION -- per-criterion bucket resimulation requires the criterion
    evaluator harness to re-run against original OHLCV bars with the
    substituted threshold (V2; depends on OHLCV cache validity at original
    data_asof_date). For these, V1 returns ``persisted_bucket`` (parity-
    preserving). The output formatter calls this out explicitly per spec
    sec1.5.1 cross-coupling caveat.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from research.harness.aplus_sensitivity.variables import SweepVariable
from swing.config import Config


@dataclass(frozen=True)
class SweepEntry:
    """One row in the sensitivity matrix.

    ``kind`` mirrors ``SweepVariable.kind`` per Expansion #11 taxonomy
    propagation discipline (dataclass -> CSV header -> markdown matrix ->
    test fixtures all carry the same enum).
    """

    variable_name: str
    kind: str  # "gate" | "threshold_additive" | "threshold_multiplicative"
    sweep_point: float | int
    aplus_count: int
    watch_count: int
    skip_count: int
    excluded_count: int
    delta_aplus: int  # vs current_value entry's aplus_count
    delta_watch: int


@dataclass(frozen=True)
class SweepResult:
    eval_runs_window: int
    eval_run_id_range: tuple[int, int]
    total_candidates: int
    entries: tuple[SweepEntry, ...]


_LAST_N_EVAL_RUNS_SQL = (
    "SELECT id FROM evaluation_runs ORDER BY id DESC LIMIT ?"
)


def run_sensitivity_sweep(
    conn: sqlite3.Connection,
    *,
    variables: tuple[SweepVariable, ...],
    cfg: Config,
    eval_runs_window: int = 20,
) -> SweepResult:
    """Run the 1D sensitivity sweep over ``candidates`` + ``candidate_criteria``.

    Reads-only; no DB writes. Returns one ``SweepEntry`` per
    (variable, sweep_point) pair, plus aggregate metadata.
    """
    eval_run_ids = [
        row[0]
        for row in conn.execute(_LAST_N_EVAL_RUNS_SQL, (eval_runs_window,))
    ]
    if not eval_run_ids:
        return SweepResult(
            eval_runs_window=eval_runs_window,
            eval_run_id_range=(0, 0),
            total_candidates=0,
            entries=(),
        )

    placeholders = ",".join("?" for _ in eval_run_ids)
    sql = (
        "SELECT c.id, c.bucket, cc.layer, cc.criterion_name, "
        "       cc.result, cc.value, cc.rule "
        "FROM candidates c "
        "LEFT JOIN candidate_criteria cc ON cc.candidate_id = c.id "
        f"WHERE c.evaluation_run_id IN ({placeholders})"
    )
    rows = list(conn.execute(sql, eval_run_ids))

    candidate_ids = {r[0] for r in rows}
    total_candidates = len(candidate_ids)

    entries: list[SweepEntry] = []
    for var in variables:
        current_aplus = current_watch = 0
        sub_entries: list[SweepEntry] = []
        for point in var.sweep_points:
            counts = _recompute_counts_at(
                rows=rows,
                variable_name=var.name,
                sweep_value=point,
                cfg=cfg,
            )
            sub_entries.append(SweepEntry(
                variable_name=var.name,
                kind=var.kind,
                sweep_point=point,
                aplus_count=counts["aplus"],
                watch_count=counts["watch"],
                skip_count=counts["skip"],
                excluded_count=counts["excluded"],
                delta_aplus=0,  # filled below
                delta_watch=0,
            ))
            if point == var.current_value:
                current_aplus = counts["aplus"]
                current_watch = counts["watch"]
        # Fill deltas relative to the current-value entry.
        for e in sub_entries:
            entries.append(SweepEntry(
                variable_name=e.variable_name,
                kind=e.kind,
                sweep_point=e.sweep_point,
                aplus_count=e.aplus_count,
                watch_count=e.watch_count,
                skip_count=e.skip_count,
                excluded_count=e.excluded_count,
                delta_aplus=e.aplus_count - current_aplus,
                delta_watch=e.watch_count - current_watch,
            ))

    return SweepResult(
        eval_runs_window=eval_runs_window,
        eval_run_id_range=(min(eval_run_ids), max(eval_run_ids)),
        total_candidates=total_candidates,
        entries=tuple(entries),
    )


def _recompute_counts_at(
    *,
    rows: list[tuple],
    variable_name: str,
    sweep_value: float | int,
    cfg: Config,
) -> dict[str, int]:
    """Recompute (aplus, watch, skip, excluded) counts under the
    hypothetical that ``variable_name`` = ``sweep_value``.

    See module docstring for V1 substitution semantics (gate vs threshold).
    """
    counts = {"aplus": 0, "watch": 0, "skip": 0, "excluded": 0}
    by_candidate: dict[int, dict] = {}
    # Map persisted ``candidate_criteria.layer`` values
    # ('trend_template'/'vcp'/'risk') onto our short bucket names.
    _layer_bucket = {"trend_template": "tt", "vcp": "vcp", "risk": "risk"}
    for cid, bucket, layer, name, result, value, rule in rows:
        cand = by_candidate.setdefault(cid, {
            "bucket": bucket,
            "tt": [],
            "vcp": [],
            "risk": [],
        })
        if layer is None:
            continue
        slot = _layer_bucket.get(layer)
        if slot is None:
            continue
        cand[slot].append(
            {"name": name, "result": result, "value": value, "rule": rule}
        )

    allowed_miss = set(cfg.trend_template.allowed_miss_names)
    prod_min_passes = cfg.trend_template.min_passes
    for _cid, c in by_candidate.items():
        new_bucket = _bucket_for_substituted(
            tt=c["tt"], vcp=c["vcp"], risk=c["risk"],
            variable_name=variable_name, sweep_value=sweep_value,
            persisted_bucket=c["bucket"],
            allowed_miss_names=allowed_miss,
            prod_trend_template_min_passes=prod_min_passes,
        )
        counts[new_bucket] = counts.get(new_bucket, 0) + 1
    return counts


def _bucket_for_substituted(
    *,
    tt: list[dict],
    vcp: list[dict],
    risk: list[dict],
    variable_name: str,
    sweep_value: float | int,
    persisted_bucket: str,
    allowed_miss_names: set[str],
    prod_trend_template_min_passes: int,
) -> str:
    """Mirror of ``swing.evaluation.scoring.bucket_for`` for the 2 gate
    variables. For threshold variables, returns ``persisted_bucket`` (V1
    limitation per ``_recompute_counts_at`` docstring).

    Faithfully encodes the bucket_for semantics:

      1. Risk hard filter -- any non-pass = skip.
      2. Trend-template gate -- ``tt_passes >= min_passes`` AND every TT
         failing name is in ``allowed_miss_names``.
      3. VCP gate -- ``vcp_fails == 0`` -> aplus; ``<= watch_max_fails`` ->
         watch; else skip.

    ``vcp_fails`` counts both 'fail' AND 'na' results (matching
    ``bucket_for`` semantics: insufficient data is a fail per
    ``swing/evaluation/scoring.py`` docstring).
    """
    # 1. Risk hard filter.
    if any(r["result"] != "pass" for r in risk):
        return "skip"

    tt_passes = sum(1 for r in tt if r["result"] == "pass")
    tt_fails = [r["name"] for r in tt if r["result"] != "pass"]

    if variable_name == "trend_template.min_passes":
        # Substituted min_passes; allowed_miss_names invariant preserved.
        if tt_passes < int(sweep_value):
            return "skip"
        if not all(n in allowed_miss_names for n in tt_fails):
            return "skip"
        return _vcp_to_bucket(vcp, watch_max_fails=2)

    if variable_name == "vcp.watch_max_fails":
        # Production trend-template gate (passed from cfg via caller, NOT a
        # module global -- avoids order/concurrency hazards per R2 Minor #1
        # LOCK).
        if tt_passes < prod_trend_template_min_passes:
            return "skip"
        if not all(n in allowed_miss_names for n in tt_fails):
            return "skip"
        return _vcp_to_bucket(vcp, watch_max_fails=int(sweep_value))

    # Threshold-variable sweep entry -- V1 returns persisted_bucket
    # (resimulation requires V2 criterion evaluator harness).
    return persisted_bucket


def _vcp_to_bucket(vcp: list[dict], *, watch_max_fails: int) -> str:
    vcp_fails = sum(1 for r in vcp if r["result"] in ("fail", "na"))
    if vcp_fails == 0:
        return "aplus"
    if vcp_fails <= watch_max_fails:
        return "watch"
    return "skip"
