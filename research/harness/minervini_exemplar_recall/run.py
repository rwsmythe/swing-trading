# research/harness/minervini_exemplar_recall/run.py
from __future__ import annotations

import argparse
import hashlib
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from swing.config import Config

from . import control_cohort, detector_eval, output, scorecard, stage_db, timing
from .constants import DEFAULT_CONTROL_SEED, screenable_floor
from .exceptions import TiingoArchiveMissingError
from .exemplar_reader import read_exemplars
from .ohlcv_reader import read_full
from .scorecard import ControlSummary, ExemplarSummary

_SURFACED = {"surfaced_aplus", "surfaced_watch"}
_ATTRITION = {"skip_insufficient_history", "no_data"}


def _load_full_safe(symbol: str, tiingo_dir: Path):
    # ONLY a missing archive maps to no_data. A malformed CSV / parser error must SURFACE
    # (do not swallow data-quality failures as no_data) -- Codex R1 minor.
    try:
        return read_full(symbol, tiingo_dir=tiingo_dir)
    except TiingoArchiveMissingError:
        return None


def _first_gate(mode_result) -> str | None:
    for se in mode_result.sessions:
        if se.screen.outcome == "skip_gate_rejection" and se.screen.gate_attribution:
            return se.screen.gate_attribution.first_rejecting_gate
    return None


_OUTCOME_RANK = {
    "surfaced_aplus": 4, "surfaced_watch": 3, "skip_gate_rejection": 2,
    "skip_insufficient_history": 1, "no_data": 0,
}


def _best_session(mode_result):
    """The highest-outcome (most representative) session, or None."""
    best = None
    for se in mode_result.sessions:
        cur_rank = _OUTCOME_RANK.get(se.screen.outcome, 0)
        best_rank = _OUTCOME_RANK.get(best.screen.outcome, 0) if best is not None else -1
        if best is None or cur_rank > best_rank:
            best = se
    return best


def _rep_gate_passes(mode_result) -> dict | None:
    """gate_passes from the highest-outcome (most representative) screenable session."""
    se = _best_session(mode_result)
    return se.screen.gate_passes if se else None


def _rep_rs_path(mode_result) -> str:
    """rs_path of the representative (highest-outcome) session, not sessions[0] -- in a sweep
    sessions[0] is usually entry-60bd and can report P1 even when the best/firing session used
    P0 (Codex R2)."""
    se = _best_session(mode_result)
    return (se.screen.rs_path if se and se.screen.rs_path else "")


def run_harness(
    *,
    exemplars_csv: Path,
    tiingo_dir: Path,
    output_dir: Path,
    window_back: int = 60,
    window_fwd: int = 5,
    control_k: int = 5,
    bootstrap_b: int = 2000,
    h2_all_windows: bool = False,
    only: tuple[str, ...] | None = None,
) -> tuple[Path, Path, Path, Path]:
    exemplars_csv = Path(exemplars_csv)
    if not exemplars_csv.exists():
        raise ValueError(f"exemplars CSV not found: {exemplars_csv}")
    config = Config.from_defaults()
    exemplars_all = read_exemplars(exemplars_csv)
    n_curated_all = len(exemplars_all)
    raw_total = max(0, len(exemplars_csv.read_text(encoding="utf-8").splitlines()) - 1)
    n_excluded = max(0, raw_total - n_curated_all)  # curated=no rows (spec section 10.1)
    exemplars = exemplars_all
    if only:
        wanted = set(only)
        exemplars = [e for e in exemplars_all if e.exemplar_id in wanted]
    spy_full = _load_full_safe("SPY", Path(tiingo_dir))

    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_dir) / f"minervini-exemplar-recall-{iso}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results_rows: list[dict] = []
    per_session_rows: list[dict] = []
    summaries: dict[str, list[ExemplarSummary]] = {"single_session": [], "window_sweep": []}
    control_summaries: dict[str, list[ControlSummary]] = {"single_session": [], "window_sweep": []}
    skip_reason_counts: Counter = Counter()  # coverage/skip-reason counters (spec 10.1, gotcha #27)
    per_exemplar_provenance: list[dict] = []
    all_windows_rows: list[dict] = []

    for idx, ex in enumerate(exemplars):
        full = _load_full_safe(ex.tiingo_symbol, Path(tiingo_dir))
        if full is None:
            # No sessions are produced for a missing archive, so the per-session skip counters
            # below never fire -> count it explicitly here (Codex R2 minor; never silent).
            skip_reason_counts["archive_missing"] += 1
            modes = {
                m: timing.ExemplarTimingResult(m, (), "skip", "no_data", False, False, (), ())
                for m in ("single_session", "window_sweep")
            }
        else:
            modes = timing.evaluate_exemplar(
                ex, exemplar_full=full, spy_full=spy_full, config=config,
                window_back=window_back, window_fwd=window_fwd,
            )
        data_source = "vicr_yfinance" if ex.tiingo_symbol == "VICR" else "tiingo"
        for mode, res in modes.items():
            faith = res.h2_faithful_fired_expected if ex.detector_class != "unmapped" else None
            isod = res.h2_isolated_fired_expected if ex.detector_class != "unmapped" else None
            fired_faithful = ";".join(
                sorted({c for se in res.sessions for c in se.h2_faithful.fired_classes})
            )
            fired_isolated = ";".join(
                sorted({c for se in res.sessions for c in se.h2_isolated.fired_classes})
            )
            anchor_limited = any(
                se.h2_isolated.h2_anchor_mode_limited_possible for se in res.sessions
            )
            rs_path = _rep_rs_path(res)  # representative (best-outcome) session, not sessions[0]
            # coverage/skip-reason counters across BOTH variants (never silent)
            for se in res.sessions:
                for verdict in (se.h2_faithful, se.h2_isolated):
                    if verdict.skip_reason:
                        skip_reason_counts[verdict.skip_reason] += 1
            results_rows.append({
                "exemplar_id": ex.exemplar_id, "ticker": ex.ticker, "timing_mode": mode,
                "h1_outcome": res.best_h1_outcome, "best_bucket": res.best_bucket,
                "first_rejecting_gate": _first_gate(res) or "",
                "h2_fired_faithful": str(faith), "h2_fired_isolated": str(isod),
                "fired_classes_faithful": fired_faithful, "fired_classes_isolated": fired_isolated,
                "rs_path": rs_path,
                "data_source": data_source,
                # n_bars from the SAME representative (best-outcome) session that backs h1_outcome,
                # rs_path and gate_passes -- not sessions[-1] (the entry+5bd tail of a sweep), which
                # would make the row internally inconsistent (Codex executing-plans R1 minor).
                "n_bars": str(_best_session(res).screen.n_sliced if res.sessions else 0),
                "screenable": str(res.best_h1_outcome not in _ATTRITION),
                "h2_anchor_mode_limited_possible": str(anchor_limited),
                "h2_anchor_mode_limited_reason": (
                    next((se.h2_isolated.h2_anchor_mode_limited_reason for se in res.sessions
                          if se.h2_isolated.h2_anchor_mode_limited_reason), "") or ""
                ),
            })
            for se in res.sessions:
                per_session_rows.append({
                    "exemplar_id": ex.exemplar_id, "ticker": ex.ticker, "timing_mode": mode,
                    "session": se.session.isoformat(), "h1_outcome": se.screen.outcome,
                    "bucket": se.screen.bucket or "",
                    "fired_faithful_expected": str(se.h2_faithful.fired_expected_class),
                    "fired_isolated_expected": str(se.h2_isolated.fired_expected_class),
                    "fired_classes_faithful": ";".join(se.h2_faithful.fired_classes),
                    "fired_classes_isolated": ";".join(se.h2_isolated.fired_classes),
                })
            if mode == "window_sweep":
                per_exemplar_provenance.append({
                    "exemplar_id": ex.exemplar_id, "data_source": data_source,
                    "rs_path": rs_path,  # representative session
                    "rs_paths_all": sorted(
                        {se.screen.rs_path for se in res.sessions if se.screen.rs_path}
                    ),
                })
            summaries[mode].append(ExemplarSummary(
                ex.exemplar_id, ex.ticker, ex.detector_class, res.best_h1_outcome,
                _first_gate(res), faith, isod, _rep_gate_passes(res),
            ))

        if h2_all_windows and full is not None:
            all_windows_rows.extend(
                _h2_all_windows_rows(ex, full, window_back=window_back, window_fwd=window_fwd)
            )

        # controls (only when we have the ticker's bars)
        if full is not None:
            anchors = control_cohort.sample_control_anchors(
                full, ex.entry_anchor, k=control_k, window_back=window_back, window_fwd=window_fwd,
                screenable_floor=screenable_floor(config), base_seed=DEFAULT_CONTROL_SEED,
                exemplar_index=idx,
            )
            for anchor in anchors:
                cmodes = control_cohort.evaluate_control(
                    ex, anchor, exemplar_full=full, spy_full=spy_full, config=config,
                    window_back=window_back, window_fwd=window_fwd,
                )
                for mode, cres in cmodes.items():
                    control_summaries[mode].append(ControlSummary(
                        ticker=ex.ticker, detector_class=ex.detector_class,
                        surfaced=cres.best_h1_outcome in _SURFACED,
                        fired_faithful=cres.h2_faithful_fired_expected,
                        fired_isolated=cres.h2_isolated_fired_expected,
                    ))

    cards = {
        m: scorecard.build_scorecard(m, summaries[m], control_summaries[m],
                                     bootstrap_b=bootstrap_b, base_seed=DEFAULT_CONTROL_SEED)
        for m in ("single_session", "window_sweep")
    }

    n_screenable = sum(1 for e in summaries["window_sweep"] if e.h1_outcome not in _ATTRITION)
    finished_iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    results_path = run_dir / "results.csv"
    per_session_path = run_dir / "per_session.csv"
    summary_path = run_dir / "summary.md"
    manifest_path = run_dir / "manifest.json"
    output.write_results_csv(results_rows, results_path)
    output.write_per_session_csv(per_session_rows, per_session_path)
    output.write_summary_md(_summary_lines(cards, exemplars), summary_path)
    output.write_manifest_json(
        _manifest(
            exemplars_csv=exemplars_csv, exemplars=exemplars, config=config,
            window_back=window_back, window_fwd=window_fwd, control_k=control_k,
            bootstrap_b=bootstrap_b, started_iso=iso, finished_iso=finished_iso,
            n_excluded=n_excluded, n_screenable=n_screenable, only=only,
            per_exemplar_provenance=per_exemplar_provenance,
            skip_reason_counts=dict(skip_reason_counts),
        ),
        manifest_path,
    )
    if h2_all_windows:
        output.write_h2_all_windows_csv(all_windows_rows, run_dir / "h2_all_windows_diagnostic.csv")
    return results_path, per_session_path, summary_path, manifest_path


def _summary_lines(cards, exemplars) -> list[str]:
    lines = ["# Minervini Exemplar Recall - summary", ""]
    lines.append(f"Exemplars evaluated (curated=yes): {len(exemplars)}")
    lines.append("")
    lines.append(
        "NOTE: the negative-control cohort is a SAME-TICKER temporal-specificity contrast,"
    )
    lines.append("NOT a population false-fire base rate (spec section 8/12.10).")
    lines.append("")
    for mode, card in cards.items():
        lines.append(f"## {mode}")
        lines.append(f"- screening recall (full set): {card.screening_recall_full:.3f}")
        lines.append(f"- screening recall (screenable): {card.screening_recall_screenable:.3f}")
        w = card.screening_wilson_screenable
        lines.append(
            f"- Wilson 95pct (screenable, PRIMARY): [{w.lower:.3f}, {w.upper:.3f}] n={w.n}"
        )
        b = card.screening_bootstrap_screenable
        lines.append(
            f"- ticker-clustered bootstrap 95pct (EXPLORATORY): [{b.lower:.3f}, {b.upper:.3f}]"
        )
        lines.append(f"- bucket distribution: {card.bucket_distribution}")
        lines.append(f"- first-rejecting-gate histogram: {card.gate_attribution_hist}")
        lines.append(f"- per-gate pass rate (screenable): {card.per_gate_pass_rate_screenable}")
        lines.append(f"- per-detector recall faithful: {card.detector_recall.per_class_faithful}")
        lines.append(f"- per-detector recall isolated: {card.detector_recall.per_class_isolated}")
        lines.append(f"- Stage-2 delta (isolated - faithful): {card.detector_recall.stage2_delta}")
        lines.append(f"- specificity contrast (control): {card.specificity_contrast}")
        lines.append("")
    return lines


def _h2_all_windows_rows(ex, full, *, window_back, window_fwd) -> list[dict]:
    """Diagnostic: scan ALL windows under an ISOLATED stage (past the Stage-2 gate) at EVERY
    session of BOTH timing modes (Codex R2: cover the sweep sessions that drive best-of H2 recall,
    not just the entry anchor). Each row is tagged timing_mode + session. Non-production, separate
    file only, off by default (it is the most expensive path in the harness)."""
    modes = {
        "single_session": timing.single_session(full, ex.entry_anchor),
        "window_sweep": timing.sweep_sessions(
            full, ex.entry_anchor, window_back=window_back, window_fwd=window_fwd
        ),
    }
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        conn = stage_db.build_stage_db(Path(td) / "iso.db")
        try:
            for mode, sessions in modes.items():
                for session in sessions:
                    stage_db.seed_session(
                        conn, ticker=ex.tiingo_symbol, session=session,
                        tt_results=(), mode="isolated"
                    )
                    for row in detector_eval.evaluate_h2_all_windows(
                        exemplar=ex, session=session, exemplar_full=full, stage_conn=conn
                    ):
                        row["timing_mode"] = mode
                        rows.append(row)
        finally:
            conn.close()
    return rows


def _manifest(
    *, exemplars_csv, exemplars, config, window_back, window_fwd, control_k, bootstrap_b,
    started_iso, finished_iso, n_excluded, n_screenable, only, per_exemplar_provenance,
    skip_reason_counts,
) -> dict:
    raw = Path(exemplars_csv).read_bytes()
    return {
        "harness_version": "0.1.0",
        "exemplar_set_sha256": hashlib.sha256(raw).hexdigest(),
        "n_total": len(exemplars),
        "n_screenable": n_screenable,
        "n_excluded": n_excluded,
        "n_unmapped": sum(1 for e in exemplars if e.detector_class == "unmapped"),
        "only_filter": list(only) if only else None,
        "window_back": window_back,
        "window_fwd": window_fwd,
        "control_k": control_k,
        "control_seed": DEFAULT_CONTROL_SEED,
        "bootstrap_b": bootstrap_b,
        "started_iso_utc": started_iso,
        "finished_iso_utc": finished_iso,
        "per_exemplar_provenance": per_exemplar_provenance,
        "skip_reason_counts": skip_reason_counts,
        "config_snapshot": {
            "min_passes": config.trend_template.min_passes,
            "allowed_miss_names": list(config.trend_template.allowed_miss_names),
            "rs_rank_min_pass": config.rs.rs_rank_min_pass,
            "fallback_extreme_pct": config.rs.fallback_extreme_pct,
            "horizon_weeks": config.rs.horizon_weeks,
            "rising_ma_period_days": config.trend_template.rising_ma_period_days,
            "screenable_floor": screenable_floor(config),
        },
        "l2_lock_preserved": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="minervini-recall")
    p.add_argument("--exemplars-csv", type=Path, required=True)
    p.add_argument("--tiingo-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("exports/research"))
    p.add_argument("--window-back", type=int, default=60)
    p.add_argument("--window-fwd", type=int, default=5)
    p.add_argument("--control-k", type=int, default=5)
    p.add_argument("--bootstrap-b", type=int, default=2000)
    p.add_argument("--h2-all-windows", action="store_true")
    p.add_argument("--only", type=str, default=None)
    args = p.parse_args(argv)
    only = tuple(s.strip() for s in args.only.split(",") if s.strip()) if args.only else None
    try:
        results, per_session, summary, manifest = run_harness(
            exemplars_csv=args.exemplars_csv, tiingo_dir=args.tiingo_dir,
            output_dir=args.output_dir,
            window_back=args.window_back, window_fwd=args.window_fwd, control_k=args.control_k,
            bootstrap_b=args.bootstrap_b, h2_all_windows=args.h2_all_windows, only=only,
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
