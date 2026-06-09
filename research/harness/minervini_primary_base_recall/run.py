from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from research.harness.minervini_exemplar_recall.ohlcv_reader import read_full, slice_to
from research.harness.minervini_exemplar_recall.exceptions import TiingoArchiveMissingError

from . import output, precision_control, scorecard, timing
from .cohort import resolve_cohort
from .constants import (
    CONTROL_K,
    DEFAULT_CONTROL_SEED,
    MAX_CONTROL_AGE_BARS,
    MIN_BASE_BARS,
    MIN_HISTORY_BARS,
    WINDOW_BACK,
    WINDOW_FWD,
    YOUNG_NAME_CEILING_BARS,
    ZIGZAG_THRESHOLD_PCT,
    depth_cap,
)


def _load_full_safe(symbol: str, tiingo_dir: Path):
    try:
        return read_full(symbol, tiingo_dir=tiingo_dir)
    except TiingoArchiveMissingError:
        return None


def _entry_pos(bars, entry_anchor) -> int | None:
    mask = bars.index.date >= entry_anchor
    return int(mask.argmax()) if mask.any() else None


def run_harness(
    *,
    exemplars_csv: Path,
    tiingo_dir: Path,
    output_dir: Path,
    window_back: int = WINDOW_BACK,
    window_fwd: int = WINDOW_FWD,
    control_k: int = CONTROL_K,
    bootstrap_b: int = 2000,
    only: tuple[str, ...] | None = None,
) -> tuple[Path, Path, Path, Path]:
    exemplars_csv = Path(exemplars_csv)
    if not exemplars_csv.exists():
        raise ValueError(f"exemplars CSV not found: {exemplars_csv}")
    resolved = resolve_cohort(exemplars_csv)
    if only:
        wanted = set(only)
        resolved = [r for r in resolved if r.member.exemplar_id in wanted]

    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_dir) / f"primary-base-recall-{iso}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results_rows: list[dict] = []
    per_session_rows: list[dict] = []
    per_exemplar: list[dict] = []
    # recall rows: (exemplar_id, fired), only over sub_floor evaluable members (bars >= MIN_HISTORY).
    sweep_recall_rows: list[tuple[str, bool]] = []
    # bootstrap rows are keyed by TICKER (row[0]) per the frozen ticker_clustered_bootstrap contract,
    # kept SEPARATE from the exemplar_id-keyed recall display rows (Codex WP-R2 M2).
    sweep_bootstrap_rows: list[tuple[str, bool]] = []
    single_recall_rows: list[tuple[str, bool]] = []
    sweep_miss_rows: list[tuple[str, str | None]] = []
    # stratified diagnostics + precision (Codex WP-R1 C1/M2/M6).
    precision_rows: list[dict] = []
    positive_control_rows: list[tuple[str, bool, str]] = []  # (exemplar_id, sweep_fired, first_reject)
    history_excluded_rows: list[tuple[str, int]] = []        # (exemplar_id, bars_through_anchor)

    for idx, rm in enumerate(resolved):
        row = rm.row
        symbol = row.tiingo_symbol   # populated by read_exemplars (Codex WP-R1 M5: no tiingo_symbol import)
        full = _load_full_safe(symbol, Path(tiingo_dir))
        data_source = "tiingo" if full is not None else "no_data"
        bars_through_anchor = (
            len(slice_to(full, row.entry_anchor)) if full is not None else 0
        )
        eligible_count = 0

        modes: dict[str, timing.TimingResult] = {}
        if full is not None:
            modes = timing.evaluate_exemplar(
                full, row.entry_anchor, row.date_precision,
                window_back=window_back, window_fwd=window_fwd,
            )

        # Emit single_session rows ONLY for day/exact precision; month rows are SWEEP-ONLY (Codex
        # WP-R1 M1 -- never ship a misleading single_session fired=False row for AMZN/DKS).
        emit_modes = (
            ("single_session", "window_sweep")
            if row.date_precision in ("day", "exact")
            else ("window_sweep",)
        )
        for mode in emit_modes:
            res = modes.get(mode)
            fired = bool(res.fired) if res else False
            # The verdict at the best (firing, else last) session for diagnostics.
            best = None
            if res and res.sessions:
                best = next((s for s in res.sessions if s.verdict.fired), res.sessions[-1])
            v = best.verdict if best else None
            results_rows.append({
                "exemplar_id": row.exemplar_id, "ticker": row.ticker, "role": rm.member.role,
                "timing_mode": mode, "fired": str(fired),
                "first_rejecting_criterion": (v.first_rejecting_criterion if v else "") or "",
                "base_start_date": (v.base_start_date.isoformat() if v and v.base_start_date else ""),
                "base_high": (f"{v.base_high:.4f}" if v and v.base_high is not None else ""),
                "correction_depth_pct": (
                    f"{v.correction_depth_pct:.4f}" if v and v.correction_depth_pct is not None else ""
                ),
                "base_duration_bars": (str(v.base_duration_bars) if v and v.base_duration_bars is not None else ""),
                "emergence_close": (f"{v.emergence_close:.4f}" if v and v.emergence_close is not None else ""),
                "data_source": data_source,
                "bars_through_anchor": str(bars_through_anchor),
                "date_precision": row.date_precision,
            })
            if res:
                for se in res.sessions:
                    per_session_rows.append({
                        "exemplar_id": row.exemplar_id, "ticker": row.ticker, "timing_mode": mode,
                        "session": se.session.isoformat(), "fired": str(se.verdict.fired),
                        "first_rejecting_criterion": se.verdict.first_rejecting_criterion or "",
                    })

        # Recall denominators: sub_floor evaluable (bars >= MIN_HISTORY_BARS) only.
        evaluable = rm.member.role == "sub_floor" and bars_through_anchor >= MIN_HISTORY_BARS
        if evaluable:
            sweep = modes.get("window_sweep")
            sweep_fired = bool(sweep.fired) if sweep else False
            sweep_recall_rows.append((row.exemplar_id, sweep_fired))
            sweep_bootstrap_rows.append((row.ticker, sweep_fired))  # ticker-keyed (WP-R2 M2)
            # first_rejecting at the best sweep session (None if fired).
            if sweep and sweep.sessions:
                best = next((s for s in sweep.sessions if s.verdict.fired), sweep.sessions[-1])
                sweep_miss_rows.append((row.exemplar_id, best.verdict.first_rejecting_criterion))
            # Single-session recall ONLY for day-precision evaluable (BODY-only, n=1).
            if row.date_precision in ("day", "exact"):
                single = modes.get("single_session")
                single_recall_rows.append((row.exemplar_id, bool(single.fired) if single else False))
        # YHOO positive control reported separately (Codex WP-R1 M2).
        if rm.member.role == "positive_control":
            sweep = modes.get("window_sweep")
            pc_fired = bool(sweep.fired) if sweep else False
            pc_reject = ""
            if sweep and sweep.sessions and not pc_fired:
                pc_reject = sweep.sessions[-1].verdict.first_rejecting_criterion or ""
            positive_control_rows.append((row.exemplar_id, pc_fired, pc_reject))
        # JNPR-style history-exclusion reported separately (Codex WP-R1 M2): a sub_floor name below
        # the history floor is NOT a screen miss -- it is below Minervini's own >=2-month minimum.
        if rm.member.role == "sub_floor" and bars_through_anchor < MIN_HISTORY_BARS:
            history_excluded_rows.append((row.exemplar_id, bars_through_anchor))

        # Precision controls (own pre-filtered young-window sampler) -- PERSISTED + scored (C1).
        control_single_flags: list[bool] = []
        control_window_flags: list[bool] = []
        if full is not None:
            entry_pos = _entry_pos(full, row.entry_anchor)
            bounds = timing.sweep_bounds(
                full, row.entry_anchor, row.date_precision,
                window_back=window_back, window_fwd=window_fwd,
            )
            if entry_pos is not None and bounds is not None:
                anchors, eligible_count = precision_control.sample_young_controls(
                    full, entry_pos=entry_pos, sweep_start=bounds[0], sweep_end=bounds[1],
                    k=control_k, base_seed=DEFAULT_CONTROL_SEED, exemplar_index=idx,
                )
                for a in anchors:
                    cres = precision_control.screen_control_anchor(
                        full, a, window_back=window_back, window_fwd=window_fwd
                    )
                    control_single_flags.append(cres.single_session_fired)
                    control_window_flags.append(cres.window_fired)
        # Exemplar side of the contrast: single-session is meaningful ONLY for day/exact rows (None
        # for month -> sweep-only). window best-of applies to all rows.
        ex_single_fired = (
            bool(modes["single_session"].fired)
            if (row.date_precision in ("day", "exact") and "single_session" in modes)
            else None
        )
        ex_window_fired = bool(modes["window_sweep"].fired) if "window_sweep" in modes else False
        precision_rows.append({
            "exemplar_id": row.exemplar_id, "role": rm.member.role,
            "eligible_control_count": eligible_count, "k_controls": len(control_single_flags),
            "contrast": scorecard.precision_contrast(
                exemplar_single_fired=ex_single_fired, exemplar_window_fired=ex_window_fired,
                control_single_flags=control_single_flags, control_window_flags=control_window_flags,
            ),
        })

        per_exemplar.append({
            "exemplar_id": row.exemplar_id, "ticker": row.ticker, "role": rm.member.role,
            "date_precision": row.date_precision, "bars_through_anchor": bars_through_anchor,
            "data_source": data_source,
            "eligible_control_count_before_sampling": eligible_count,
            "book_citation": rm.member.book_citation,
        })

    n_evaluable = sum(
        1 for e in per_exemplar
        if e["role"] == "sub_floor" and e["bars_through_anchor"] >= MIN_HISTORY_BARS
    )
    finished_iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    results_path = run_dir / "results.csv"
    per_session_path = run_dir / "per_session.csv"
    summary_path = run_dir / "summary.md"
    manifest_path = run_dir / "manifest.json"

    output.write_results_csv(results_rows, results_path)
    output.write_per_session_csv(per_session_rows, per_session_path)
    output.write_summary_md(
        _summary_lines(
            sweep_recall_rows, sweep_bootstrap_rows, single_recall_rows, sweep_miss_rows,
            positive_control_rows, history_excluded_rows, precision_rows, bootstrap_b,
        ),
        summary_path,
    )
    output.write_manifest_json(
        {
            "harness_version": "0.1.0",
            "n_total": len(resolved),
            "n_evaluable": n_evaluable,
            "only_filter": list(only) if only else None,
            "per_exemplar": per_exemplar,
            "thresholds": {
                "MIN_HISTORY_BARS": MIN_HISTORY_BARS, "MIN_BASE_BARS": MIN_BASE_BARS,
                "ZIGZAG_THRESHOLD_PCT": ZIGZAG_THRESHOLD_PCT,
                "YOUNG_NAME_CEILING_BARS": YOUNG_NAME_CEILING_BARS,
                "depth_caps": {"<=25": depth_cap(25), "26-200": depth_cap(26), ">200": depth_cap(201)},
            },
            "control_params": {
                "control_k": control_k, "control_seed": DEFAULT_CONTROL_SEED,
                "max_control_age_bars": MAX_CONTROL_AGE_BARS,
                "window_back": window_back, "window_fwd": window_fwd,
            },
            "bootstrap_b": bootstrap_b,
            "started_iso_utc": iso, "finished_iso_utc": finished_iso,
            "l2_lock_preserved": True,
        },
        manifest_path,
    )
    return results_path, per_session_path, summary_path, manifest_path


def _summary_lines(
    sweep_rows, sweep_bootstrap_rows, single_rows, miss_rows, positive_control_rows,
    history_excluded_rows, precision_rows, bootstrap_b,
) -> list[str]:
    lines = ["# Minervini primary-base recall - summary", ""]
    lines.append("NOTE: n~3 proof-of-concept. Raw fractions are PRIMARY; Wilson + bootstrap are")
    lines.append("MECHANICAL/EXPLORATORY at this n, NOT evidence of stable performance. Precision is a")
    lines.append("same-ticker temporal-specificity contrast, NOT a population base rate.")
    lines.append("")
    lines.append("## Recall (sub-floor evaluable {AMZN-1997, BODY, DKS})")
    sweep = scorecard.recall_fraction(sweep_rows)
    lines.append(
        f"sub-floor sweep recall (RAW): {sweep.successes}/{sweep.n} "
        f"(fired: {';'.join(sweep.fired_ids) or '-'}; missed: {';'.join(sweep.missed_ids) or '-'})"
    )
    w = scorecard.wilson(sweep.successes, sweep.n)
    lines.append(f"  Wilson 95pct (MECHANICAL at n={w.n}): [{w.lower:.3f}, {w.upper:.3f}]")
    # Exploratory ticker-clustered bootstrap (Codex WP-R1 M6) over the TICKER-keyed rows (WP-R2 M2).
    # Guard the zero-row case (WP-R2 M1): emit NA rather than a meaningless [0.000, 0.000] interval
    # (the frozen primitive does not crash on empty input -- the resampler's comprehension is empty --
    # but a degenerate interval would mislead). The empty path is exercised by the CLI no-Tiingo test.
    if sweep.n == 0:
        lines.append("  ticker-clustered bootstrap (EXPLORATORY): NA (no evaluable rows)")
    else:
        boot = scorecard.bootstrap(sweep_bootstrap_rows, b=bootstrap_b, base_seed=DEFAULT_CONTROL_SEED)
        lines.append(
            f"  ticker-clustered bootstrap 95pct (EXPLORATORY): [{boot.lower:.3f}, {boot.upper:.3f}]"
        )
    single = scorecard.recall_fraction(single_rows)
    lines.append(
        f"day-precision single-session recall (RAW, BODY-only n={single.n}): "
        f"{single.successes}/{single.n} -- single yes/no, NO interval"
    )
    hist = scorecard.first_rejection_histogram(miss_rows)
    lines.append(f"sweep first-rejecting-criterion histogram: {hist}")
    lines.append("")
    lines.append("## Positive control (YHOO -- sufficient-history documented primary base)")
    if positive_control_rows:
        for eid, fired, reject in positive_control_rows:
            tail = "" if fired else f" (first_rejecting_criterion={reject or '-'})"
            lines.append(f"- {eid}: window-sweep fired={fired}{tail}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Below-minimum (reported, NOT a screen miss -- below Minervini's >=2-month floor)")
    if history_excluded_rows:
        for eid, bars in history_excluded_rows:
            lines.append(f"- {eid}: history-excluded ({bars} bars < MIN_HISTORY_BARS)")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Precision (same-ticker young-window control; single-session per-anchor PRIMARY)")
    for pr in precision_rows:
        c = pr["contrast"]
        single_rate = "NA" if c.control_single_rate is None else f"{c.control_single_rate:.3f}"
        window_rate = "NA" if c.control_window_rate is None else f"{c.control_window_rate:.3f}"
        lines.append(
            f"- {pr['exemplar_id']} ({pr['role']}): control single-session per-anchor fire "
            f"(PRIMARY)={single_rate}; window best-of (SEPARATE)={window_rate}; "
            f"k={pr['k_controls']}, eligible_before_sampling={pr['eligible_control_count']}; "
            f"exemplar single={c.exemplar_single_fired} window={c.exemplar_window_fired}"
        )
    lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="primary-base-recall")
    p.add_argument("--exemplars-csv", type=Path, required=True)
    p.add_argument("--tiingo-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("exports/research"))
    p.add_argument("--window-back", type=int, default=WINDOW_BACK)
    p.add_argument("--window-fwd", type=int, default=WINDOW_FWD)
    p.add_argument("--control-k", type=int, default=CONTROL_K)
    p.add_argument("--bootstrap-b", type=int, default=2000)
    p.add_argument("--only", type=str, default=None)
    args = p.parse_args(argv)
    only = tuple(s.strip() for s in args.only.split(",") if s.strip()) if args.only else None
    try:
        results, per_session, summary, manifest = run_harness(
            exemplars_csv=args.exemplars_csv, tiingo_dir=args.tiingo_dir, output_dir=args.output_dir,
            window_back=args.window_back, window_fwd=args.window_fwd, control_k=args.control_k,
            bootstrap_b=args.bootstrap_b, only=only,
        )
    except ValueError as exc:
        p.error(str(exc))
        return 2
    print(f"results.csv:     {results}")
    print(f"per_session.csv: {per_session}")
    print(f"summary.md:      {summary}")
    print(f"manifest.json:   {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
