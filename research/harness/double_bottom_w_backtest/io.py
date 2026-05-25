"""CSV + summary markdown + manifest JSON emit for the D1 backtest harness."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.double_bottom_w_backtest.walkforward import Trade


RESULTS_CSV_HEADER = [
    "pattern_id",
    "ticker",
    "ruleset_name",
    "anchor_asof_date",
    "effective_asof_date",  # Codex R3 M#2
    "max_observed_asof_date",  # Codex R3 M#2
    "trough_1_date",
    "center_peak_price",
    "trough_2_price",
    "initial_stop",
    "composite_score",
    "triggered",
    "entry_date",
    "entry_price",
    "exit_date",
    "exit_price",
    "exit_reason",
    "r_multiple",
    "trade_pnl_dollars",
    "peak_unrealized_R",
    "drawdown_to_exit_R",
    "days_held",
    "status",
    "forward_bars_available",
    "max_forward_close",
    "max_close_pct_of_peak",
    "days_t2_to_asof",
]


def write_results_csv(trades: list[Trade], output_path: Path) -> None:
    """25-column per-(pattern, ruleset) row dump (post-Codex-R1 M#7).

    Includes near-miss diagnostic columns (max_forward_close +
    max_close_pct_of_peak) for untriggered pattern analysis per V2 precedent.
    """
    import csv

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(RESULTS_CSV_HEADER)
        for t in trades:
            w.writerow(
                [
                    t.pattern_id,
                    t.ticker,
                    t.ruleset_name,
                    t.anchor_asof_date.isoformat(),
                    t.effective_asof_date.isoformat() if t.effective_asof_date else "",
                    t.max_observed_asof_date.isoformat() if t.max_observed_asof_date else "",
                    t.trough_1_date.isoformat(),
                    f"{t.center_peak_price:.4f}",
                    f"{t.trough_2_price:.4f}",
                    f"{t.initial_stop:.4f}",
                    f"{t.composite_score:.4f}",
                    "true" if t.triggered else "false",
                    t.entry_date.isoformat() if t.entry_date else "",
                    f"{t.entry_price:.4f}" if t.entry_price is not None else "",
                    t.exit_date.isoformat() if t.exit_date else "",
                    f"{t.exit_price:.4f}" if t.exit_price is not None else "",
                    t.exit_reason,
                    f"{t.r_multiple:.4f}" if t.r_multiple is not None else "",
                    f"{t.trade_pnl_dollars:.2f}" if t.trade_pnl_dollars is not None else "",
                    f"{t.peak_unrealized_R:.4f}" if t.peak_unrealized_R is not None else "",
                    f"{t.drawdown_to_exit_R:.4f}" if t.drawdown_to_exit_R is not None else "",
                    t.days_held if t.days_held is not None else "",
                    t.status,
                    t.forward_bars_available,
                    f"{t.max_forward_close:.4f}" if t.max_forward_close is not None else "",
                    f"{t.max_close_pct_of_peak:.1f}" if t.max_close_pct_of_peak is not None else "",
                    t.days_t2_to_asof if t.days_t2_to_asof is not None else "",
                ]
            )


def _fmt_R(v: float | None) -> str:
    return f"{v:+.3f}R" if v is not None else "n/a"


def _fmt_pct(v: float | None) -> str:
    return f"{v * 100:.1f}%" if v is not None else "n/a"


def aggregate_stats(trades: list[Trade]) -> dict[str, dict]:
    """Per-ruleset aggregate stats; closed = exit fired; open = data-tail unrealized.

    win_rate denominator excludes untriggered + open (closed-only).
    """
    by_rs: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        by_rs[t.ruleset_name].append(t)

    out: dict[str, dict] = {}
    for rs_name, rs_trades in by_rs.items():
        closed = [t for t in rs_trades if t.status == "closed"]
        winners = [t for t in closed if t.r_multiple is not None and t.r_multiple > 0]
        losers = [t for t in closed if t.r_multiple is not None and t.r_multiple <= 0]
        untriggered = [t for t in rs_trades if t.status == "untriggered"]
        open_pos = [t for t in rs_trades if t.status == "open"]
        n_triggered = len(closed) + len(open_pos)
        n_closed = len(closed)

        win_rate = len(winners) / n_closed if n_closed else None
        avg_R_winner = (
            statistics.mean(t.r_multiple for t in winners) if winners else None
        )
        avg_R_loser = (
            statistics.mean(t.r_multiple for t in losers) if losers else None
        )
        all_R = [t.r_multiple for t in rs_trades if t.r_multiple is not None]
        expectancy_closed = (
            statistics.mean(t.r_multiple for t in closed) if closed else None
        )
        avg_days_closed = (
            statistics.mean(t.days_held for t in closed if t.days_held is not None)
            if closed else None
        )
        avg_days_open = (
            statistics.mean(t.days_held for t in open_pos if t.days_held is not None)
            if open_pos else None
        )

        exit_reasons: dict[str, int] = defaultdict(int)
        for t in rs_trades:
            exit_reasons[t.exit_reason] += 1

        out[rs_name] = {
            "total_patterns": len(rs_trades),
            "n_triggered": n_triggered,
            "n_closed": n_closed,
            "winners": len(winners),
            "losers": len(losers),
            "untriggered": len(untriggered),
            "open_positions": len(open_pos),
            "win_rate_closed": win_rate,
            "avg_R_winner": avg_R_winner,
            "avg_R_loser": avg_R_loser,
            "expectancy_R_closed": expectancy_closed,
            "expectancy_R_all_triggered": (
                statistics.mean(all_R) if all_R else None
            ),
            "avg_days_held_closed": avg_days_closed,
            "avg_days_held_open": avg_days_open,
            "max_R": max(all_R) if all_R else None,
            "min_R": min(all_R) if all_R else None,
            "exit_reasons": dict(exit_reasons),
        }
    return out


def write_summary_markdown(
    trades: list[Trade],
    output_path: Path,
    *,
    n_patterns: int,
    cohort_label: str,
    population_notes: str = "",
) -> None:
    stats = aggregate_stats(trades)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Double-Bottom-W Walk-Forward Backtest Summary")
    lines.append("")
    lines.append(f"**Cohort:** {cohort_label} ({n_patterns} unique W patterns)")
    lines.append("")
    if population_notes:
        lines.append(population_notes)
        lines.append("")

    # Per-ruleset aggregate stats
    lines.append("## Per-ruleset aggregate stats")
    lines.append("")
    lines.append(
        "| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |"
    )
    lines.append(
        "|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|"
    )
    for rs in sorted(stats.keys()):
        s = stats[rs]
        lines.append(
            "| {rs} | {n} | {ntr} | {ncl} | {w} | {l} | {u} | {o} | {wr} | {avg_w} | {avg_l} | {exp} | {dhc} | {dho} |".format(
                rs=rs,
                n=s["total_patterns"],
                ntr=s["n_triggered"],
                ncl=s["n_closed"],
                w=s["winners"],
                l=s["losers"],
                u=s["untriggered"],
                o=s["open_positions"],
                wr=_fmt_pct(s["win_rate_closed"]),
                avg_w=_fmt_R(s["avg_R_winner"]),
                avg_l=_fmt_R(s["avg_R_loser"]),
                exp=_fmt_R(s["expectancy_R_closed"]),
                dhc=f"{s['avg_days_held_closed']:.1f}d" if s["avg_days_held_closed"] is not None else "n/a",
                dho=f"{s['avg_days_held_open']:.1f}d" if s["avg_days_held_open"] is not None else "n/a",
            )
        )
    lines.append("")

    # Exit-reason breakdown
    lines.append("## Exit-reason breakdown")
    lines.append("")
    lines.append(
        "| Ruleset | stop_hit | trail_stop | target_3R | close_below_50d | open_at_data_tail | untriggered | ohlcv_empty | entry_gap_below_stop |"
    )
    lines.append(
        "|---------|----------|------------|-----------|-----------------|-------------------|-------------|-------------|----------------------|"
    )
    for rs in sorted(stats.keys()):
        er = stats[rs]["exit_reasons"]
        lines.append(
            "| {rs} | {sh} | {ts} | {t3} | {cb} | {od} | {un} | {oe} | {eg} |".format(
                rs=rs,
                sh=er.get("stop_hit", 0),
                ts=er.get("trail_stop", 0),
                t3=er.get("target_3R", 0),
                cb=er.get("close_below_50d", 0),
                od=er.get("open_at_data_tail", 0),
                un=er.get("untriggered", 0),
                oe=er.get("ohlcv_empty", 0),
                eg=er.get("entry_gap_below_stop", 0),
            )
        )
    lines.append("")

    # Per-pattern detail
    lines.append("## Per-pattern detail (composite>=0.7; sorted by ticker then trough_1_date)")
    lines.append("")
    lines.append(
        "| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |"
    )
    lines.append(
        "|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|"
    )
    for t in sorted(trades, key=lambda x: (x.ticker, x.trough_1_date, x.ruleset_name)):
        lines.append(
            "| {pid} | {comp} | {dt} | {rs} | {st} | {ed} | {xd} | {xr} | {r} | {dh} | {peak} | {dd} | {pnl} |".format(
                pid=t.pattern_id,
                comp=f"{t.composite_score:.3f}",
                dt=t.days_t2_to_asof if t.days_t2_to_asof is not None else "n/a",
                rs=t.ruleset_name,
                st=t.status,
                ed=t.entry_date.isoformat() if t.entry_date else "n/a",
                xd=t.exit_date.isoformat() if t.exit_date else "n/a",
                xr=t.exit_reason,
                r=_fmt_R(t.r_multiple),
                dh=t.days_held if t.days_held is not None else "n/a",
                peak=_fmt_R(t.peak_unrealized_R),
                dd=_fmt_R(t.drawdown_to_exit_R),
                pnl=f"${t.trade_pnl_dollars:+.2f}" if t.trade_pnl_dollars is not None else "n/a",
            )
        )
    lines.append("")

    # Near-miss diagnostic for untriggered patterns
    untrig = [t for t in trades if t.status == "untriggered" and t.ruleset_name == "A_minervini_trail_ma"]
    if untrig:
        lines.append("## Near-miss diagnostic (untriggered patterns; Ruleset A surface; max forward close as % of peak)")
        lines.append("")
        lines.append("| pattern_id | composite | fwd_bars_in_window | max_forward_close | %_of_peak | center_peak |")
        lines.append("|------------|-----------|--------------------|--------------------|-----------|-------------|")
        for t in sorted(untrig, key=lambda x: (-(x.max_close_pct_of_peak or 0))):
            lines.append(
                "| {pid} | {comp} | {fb} | {mc} | {pct} | {pk} |".format(
                    pid=t.pattern_id,
                    comp=f"{t.composite_score:.3f}",
                    fb=t.forward_bars_available,
                    mc=f"{t.max_forward_close:.2f}" if t.max_forward_close is not None else "n/a",
                    pct=f"{t.max_close_pct_of_peak:.1f}%" if t.max_close_pct_of_peak is not None else "n/a",
                    pk=f"{t.center_peak_price:.2f}",
                )
            )
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- R-multiple = (exit_price - entry_price) / (entry_price - initial_stop).")
    lines.append("- Win-rate denominator = closed trades (excludes untriggered + open).")
    lines.append("- Entry = next-session open after first close > center_peak_price.")
    lines.append("- Initial stop = trough_2_price * 0.99 (canonical W right-shoulder).")
    lines.append("- Trigger search window: max(trough_1, trough_2, asof) + 1 BD lower, asof + 60 BD upper.")
    lines.append("- All exits CLOSE-based (no intraday Low/High triggers) per dispatch brief.")
    lines.append("- OHLCV source: V2 Shape A reader at ~/swing-data/prices-cache/ (L2 LOCK preserved).")
    lines.append("- L6 caveat: forward-walk bars come from CURRENT archive; may differ from V1 contemporaneous state.")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(
    output_path: Path,
    *,
    started_at_utc: datetime,
    finished_at_utc: datetime,
    cohort_csv_path: str,
    cohort_csv_sha256: str | None,
    cache_dir: str,
    n_unique_verdicts_pre_filter: int,
    n_verdicts_after_adjacency_merge: int,
    n_patterns_after_recency_filter: int,
    recency_max_calendar_days: int,
    composite_threshold: float,
    max_trigger_search_business_days: int,
    n_trades_emitted: int,
    n_distinct_tickers: int,
    skipped_patterns: dict[str, int],
    l2_lock_preserved: bool = True,
    harness_version: str = "0.1.0",
    source_artifact_manifest_path: str | None = None,
    source_artifact_manifest_sha256: str | None = None,
    source_results_csv_sha256: str | None = None,
    source_cohort_input_sha256: str | None = None,
    recency_filter_active: bool = True,
) -> None:
    """Emit manifest.json.

    Codex R1 M#5: source provenance fields added so the manifest carries a
    bidirectional pointer back to the upstream pattern_cohort_evaluator run
    (whose `results.csv` is gitignored due to size). When --results-csv is
    used at runtime, `cohort_csv_sha256` IS the source results.csv hash.
    When --cohort-fixture is used, `source_results_csv_sha256` records the
    SHA from the upstream manifest's `cohort_input_sha256` field (which
    identifies the cohort-CSV input to pattern_cohort_evaluator) and
    `source_artifact_manifest_*` fields point at the upstream run's
    manifest.json for full provenance chase.
    """
    manifest = {
        "harness_version": harness_version,
        "harness_name": "double_bottom_w_backtest",
        "started_at_utc": started_at_utc.isoformat(),
        "finished_at_utc": finished_at_utc.isoformat(),
        "runtime_seconds": (finished_at_utc - started_at_utc).total_seconds(),
        "cohort_csv_path": cohort_csv_path,
        "cohort_csv_sha256": cohort_csv_sha256,
        "source_artifact_manifest_path": source_artifact_manifest_path,
        "source_artifact_manifest_sha256": source_artifact_manifest_sha256,
        "source_results_csv_sha256": source_results_csv_sha256,
        "source_cohort_input_sha256": source_cohort_input_sha256,
        "cache_dir": cache_dir,
        "composite_threshold": composite_threshold,
        "recency_max_calendar_days": recency_max_calendar_days,
        "recency_filter_active": recency_filter_active,
        "max_trigger_search_business_days": max_trigger_search_business_days,
        "n_unique_verdicts_pre_filter": n_unique_verdicts_pre_filter,
        "n_verdicts_after_adjacency_merge": n_verdicts_after_adjacency_merge,
        "n_patterns_after_recency_filter": n_patterns_after_recency_filter,
        "n_distinct_tickers": n_distinct_tickers,
        "n_trades_emitted": n_trades_emitted,
        "skipped_patterns": skipped_patterns,
        "l2_lock_preserved": l2_lock_preserved,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
