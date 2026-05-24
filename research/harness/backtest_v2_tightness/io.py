"""CSV + markdown emit for the backtest harness."""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

from research.harness.backtest_v2_tightness.walkforward import Trade


RESULTS_CSV_HEADER = [
    "pattern_id",
    "ticker",
    "ruleset_name",
    "n_eval_runs_in_pattern",
    "pivot",
    "initial_stop",
    "entry_date",
    "entry_price",
    "exit_date",
    "exit_price",
    "exit_reason",
    "r_multiple",
    "days_held",
    "status",
    "forward_bars_available",
    "max_forward_close",
    "max_close_pct_of_pivot",
]


def write_results_csv(trades: list[Trade], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(RESULTS_CSV_HEADER)
        for t in trades:
            w.writerow([
                t.pattern_id,
                t.ticker,
                t.ruleset_name,
                t.n_eval_runs_in_pattern,
                f"{t.pivot:.4f}",
                f"{t.initial_stop:.4f}",
                t.entry_date.isoformat() if t.entry_date else "",
                f"{t.entry_price:.4f}" if t.entry_price is not None else "",
                t.exit_date.isoformat() if t.exit_date else "",
                f"{t.exit_price:.4f}" if t.exit_price is not None else "",
                t.exit_reason,
                f"{t.r_multiple:.4f}" if t.r_multiple is not None else "",
                t.days_held if t.days_held is not None else "",
                t.status,
                t.forward_bars_available,
                f"{t.max_forward_close:.4f}" if t.max_forward_close is not None else "",
                f"{t.max_close_pct_of_pivot:.1f}" if t.max_close_pct_of_pivot is not None else "",
            ])


def aggregate_stats(trades: list[Trade]) -> dict:
    """Per-ruleset aggregate stats.

    Returns dict mapping ruleset_name -> stats dict with:
      total_patterns, winners, losers, untriggered, open_positions,
      win_rate, avg_R_winner, avg_R_loser, expectancy_R, avg_days_held,
      max_R, min_R.

    Winners: closed trades with r_multiple > 0.
    Losers: closed trades with r_multiple <= 0 (includes BE-stop exits at 0).
    Win rate denominator excludes untriggered (per brief OQ-4 default: separate).
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
        # Expectancy includes open positions at unrealized R (informational only).
        all_R = [t.r_multiple for t in rs_trades if t.r_multiple is not None]
        expectancy_closed_R = (
            statistics.mean(t.r_multiple for t in closed) if closed else None
        )
        avg_days_held_closed = (
            statistics.mean(t.days_held for t in closed if t.days_held is not None)
            if closed else None
        )

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
            "expectancy_R_closed": expectancy_closed_R,
            "expectancy_R_all_triggered": (
                statistics.mean(all_R) if all_R else None
            ),
            "avg_days_held_closed": avg_days_held_closed,
            "max_R": max(all_R) if all_R else None,
            "min_R": min(all_R) if all_R else None,
            "exit_reasons": dict(_count_exit_reasons(rs_trades)),
        }
    return out


def _count_exit_reasons(trades: list[Trade]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for t in trades:
        counts[t.exit_reason] += 1
    return counts


def _fmt_R(v: float | None) -> str:
    return f"{v:+.3f}R" if v is not None else "n/a"


def _fmt_pct(v: float | None) -> str:
    return f"{v * 100:.1f}%" if v is not None else "n/a"


def write_summary_markdown(
    cohort_trades: list[Trade],
    cohort_label: str,
    control_trades: list[Trade] | None,
    control_label: str,
    output_path: Path,
    *,
    n_patterns: int,
    n_control_patterns: int,
    population_notes: str = "",
) -> None:
    """Write markdown summary with per-ruleset aggregate stats + cross-ruleset
    comparison + control-cohort comparison."""
    cohort_stats = aggregate_stats(cohort_trades)
    control_stats = aggregate_stats(control_trades) if control_trades else {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# V2 vcp.tightness_range_factor=1.005 Walk-Forward Backtest Summary")
    lines.append("")
    lines.append(f"**Cohort:** {cohort_label} ({n_patterns} unique VCP patterns)")
    if control_trades:
        lines.append(f"**Control:** {control_label} ({n_control_patterns} unique VCP patterns)")
    lines.append("")
    if population_notes:
        lines.append(population_notes)
        lines.append("")

    # Per-ruleset table for cohort
    lines.append("## Per-ruleset aggregate stats — cohort (loosened)")
    lines.append("")
    lines.append("| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg days held |")
    lines.append("|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|---------------|")
    for rs in sorted(cohort_stats.keys()):
        s = cohort_stats[rs]
        lines.append(
            "| {rs} | {n} | {ntr} | {ncl} | {w} | {l} | {u} | {o} | {wr} | {avg_w} | {avg_l} | {exp} | {dh} |".format(
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
                dh=f"{s['avg_days_held_closed']:.1f}d" if s["avg_days_held_closed"] is not None else "n/a",
            )
        )
    lines.append("")

    # Exit-reason breakdown
    lines.append("## Exit-reason breakdown — cohort")
    lines.append("")
    lines.append("| Ruleset | stop_hit | trail_stop | target_3R | close_below_50d | open_at_data_tail | untriggered | entry_gap_below_stop |")
    lines.append("|---------|----------|------------|-----------|-----------------|-------------------|-------------|----------------------|")
    for rs in sorted(cohort_stats.keys()):
        er = cohort_stats[rs]["exit_reasons"]
        lines.append(
            "| {rs} | {sh} | {ts} | {t3} | {cb} | {od} | {un} | {eg} |".format(
                rs=rs,
                sh=er.get("stop_hit", 0),
                ts=er.get("trail_stop", 0),
                t3=er.get("target_3R", 0),
                cb=er.get("close_below_50d", 0),
                od=er.get("open_at_data_tail", 0),
                un=er.get("untriggered", 0),
                eg=er.get("entry_gap_below_stop", 0),
            )
        )
    lines.append("")

    # Control table
    if control_trades:
        lines.append("## Per-ruleset aggregate stats — control (baseline 5 A+; sweep_point=0.67)")
        lines.append("")
        lines.append("| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed |")
        lines.append("|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|")
        for rs in sorted(control_stats.keys()):
            s = control_stats[rs]
            lines.append(
                "| {rs} | {n} | {ntr} | {ncl} | {w} | {l} | {u} | {o} | {wr} | {avg_w} | {avg_l} | {exp} |".format(
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
                )
            )
        lines.append("")

        # Cross-cohort comparison
        lines.append("## Cross-cohort expectancy comparison")
        lines.append("")
        lines.append("| Ruleset | Cohort expectancy R (closed) | Control expectancy R (closed) | Delta |")
        lines.append("|---------|------------------------------|-------------------------------|-------|")
        for rs in sorted(set(cohort_stats.keys()) | set(control_stats.keys())):
            c_exp = cohort_stats.get(rs, {}).get("expectancy_R_closed")
            ctrl_exp = control_stats.get(rs, {}).get("expectancy_R_closed")
            delta = (c_exp - ctrl_exp) if (c_exp is not None and ctrl_exp is not None) else None
            lines.append(
                "| {rs} | {c} | {ctrl} | {d} |".format(
                    rs=rs,
                    c=_fmt_R(c_exp),
                    ctrl=_fmt_R(ctrl_exp),
                    d=_fmt_R(delta) if delta is not None else "n/a",
                )
            )
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- R-multiple = (exit_price - entry_price) / (entry_price - initial_stop).")
    lines.append("- Win-rate denominator = closed trades (excludes untriggered + open).")
    lines.append("- Entry = next-session open after first close above pivot.")
    lines.append("- Pivot + initial_stop from V1-persisted `candidates.pivot` + `candidates.initial_stop` at FIRST eval_run in pattern group.")
    lines.append("- OHLCV source: V2 Shape A reader at `~/swing-data/prices-cache/` (L2 LOCK preserved).")
    lines.append("- L6 caveat: pivots come from V1 persistence (NOT current archive); forward-walk uses current archive. See findings doc.")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
