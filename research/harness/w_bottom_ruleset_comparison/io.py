"""CSV + summary markdown + manifest JSON emit for the D2 ruleset comparison.

Preserves D1's 27-column CSV schema (dispatch brief Section 4.1) so downstream
tooling (auditor scripts; future per-ruleset cross-comparison plots) can
consume D1 + D2 artifacts identically. Row count grows from 36 (D1: 12
patterns x 3 rulesets) to 300-1200 (D2: 50-200 patterns x 6 rulesets).

Summary markdown adds a CROSS-RULESET COMPARISON TABLE (NEW; dispatch brief
Section 4.2) ranking the 6 rulesets by expectancy + per-bucket analysis.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from research.harness.w_bottom_ruleset_comparison.walkforward import Trade


RESULTS_CSV_HEADER = [
    "pattern_id",
    "ticker",
    "ruleset_name",
    "anchor_asof_date",
    "effective_asof_date",
    "max_observed_asof_date",
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
    """27-column per-(pattern, ruleset) row dump (preserves D1 schema)."""
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
        all_closed_R = [t.r_multiple for t in closed if t.r_multiple is not None]
        all_triggered_R = [
            t.r_multiple for t in rs_trades if t.r_multiple is not None
        ]
        expectancy_closed = (
            statistics.mean(all_closed_R) if all_closed_R else None
        )
        expectancy_triggered = (
            statistics.mean(all_triggered_R) if all_triggered_R else None
        )
        std_R_closed = (
            statistics.stdev(all_closed_R) if len(all_closed_R) >= 2 else None
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

        max_drawdown = None
        if closed:
            dd_vals = [t.drawdown_to_exit_R for t in closed if t.drawdown_to_exit_R is not None]
            if dd_vals:
                max_drawdown = max(dd_vals)

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
            "expectancy_R_triggered": expectancy_triggered,
            "std_R_closed": std_R_closed,
            "max_drawdown_closed": max_drawdown,
            "avg_days_held_closed": avg_days_closed,
            "avg_days_held_open": avg_days_open,
            "max_R": max(all_triggered_R) if all_triggered_R else None,
            "min_R": min(all_triggered_R) if all_triggered_R else None,
            "exit_reasons": dict(exit_reasons),
        }
    return out


def cross_ruleset_comparison(
    trades: list[Trade],
) -> list[tuple[str, dict]]:
    """Ranked list of (ruleset_name, stats) sorted by expectancy_R_closed
    descending; rulesets with no closed trades sort to the bottom."""
    stats = aggregate_stats(trades)

    def _sort_key(item: tuple[str, dict]) -> tuple[int, float]:
        name, s = item
        exp = s["expectancy_R_closed"]
        if exp is None:
            return (1, 0.0)  # bottom group
        return (0, -exp)  # higher expectancy = better rank

    return sorted(stats.items(), key=_sort_key)


def write_summary_markdown(
    trades: list[Trade],
    output_path: Path,
    *,
    n_patterns: int,
    cohort_label: str,
    population_notes: str = "",
) -> None:
    stats = aggregate_stats(trades)
    ranked = cross_ruleset_comparison(trades)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# W-Bottom Ruleset Comparison Backtest Summary")
    lines.append("")
    lines.append(f"**Cohort:** {cohort_label} ({n_patterns} unique W patterns)")
    lines.append("")
    if population_notes:
        lines.append(population_notes)
        lines.append("")

    # NEW: Cross-ruleset comparison table (brief Section 4.2)
    lines.append("## Cross-ruleset comparison (ranked by expectancy_R_closed)")
    lines.append("")
    lines.append(
        "| Rank | Ruleset | Win-rate | Mean R closed | Std R closed | Mean R triggered | Max drawdown closed | Avg sessions closed |"
    )
    lines.append(
        "|------|---------|----------|---------------|--------------|------------------|---------------------|---------------------|"
    )
    for rank, (rs_name, s) in enumerate(ranked, start=1):
        lines.append(
            "| {r} | {rs} | {wr} | {exp_c} | {std} | {exp_t} | {dd} | {dhc} |".format(
                r=rank,
                rs=rs_name,
                wr=_fmt_pct(s["win_rate_closed"]),
                exp_c=_fmt_R(s["expectancy_R_closed"]),
                std=f"{s['std_R_closed']:.3f}R" if s["std_R_closed"] is not None else "n/a",
                exp_t=_fmt_R(s["expectancy_R_triggered"]),
                dd=_fmt_R(s["max_drawdown_closed"]),
                dhc=f"{s['avg_days_held_closed']:.1f}d" if s["avg_days_held_closed"] is not None else "n/a",
            )
        )
    lines.append("")

    # Per-ruleset aggregate stats (mirrors D1)
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

    # Exit-reason breakdown (expanded with D/E/F exit reasons)
    lines.append("## Exit-reason breakdown")
    lines.append("")
    all_reasons = sorted({r for s in stats.values() for r in s["exit_reasons"]})
    header = "| Ruleset | " + " | ".join(all_reasons) + " |"
    sep = "|---------|" + "|".join("-" * (len(r) + 2) for r in all_reasons) + "|"
    lines.append(header)
    lines.append(sep)
    for rs in sorted(stats.keys()):
        er = stats[rs]["exit_reasons"]
        row = "| " + rs + " | " + " | ".join(str(er.get(r, 0)) for r in all_reasons) + " |"
        lines.append(row)
    lines.append("")

    # Composite-score bucket analysis
    bucket_stats = _composite_bucket_stats(trades)
    if bucket_stats:
        lines.append("## Per-composite-score-bucket analysis")
        lines.append("")
        lines.append(
            "| Bucket | Ruleset | Patterns | Triggered | Closed | Winners | Expectancy R closed |"
        )
        lines.append(
            "|--------|---------|----------|-----------|--------|---------|---------------------|"
        )
        for bucket_label in sorted(bucket_stats):
            for rs in sorted(bucket_stats[bucket_label]):
                bs = bucket_stats[bucket_label][rs]
                lines.append(
                    "| {b} | {rs} | {n} | {ntr} | {ncl} | {w} | {exp} |".format(
                        b=bucket_label,
                        rs=rs,
                        n=bs["total"],
                        ntr=bs["triggered"],
                        ncl=bs["closed"],
                        w=bs["winners"],
                        exp=_fmt_R(bs["expectancy_R_closed"]),
                    )
                )
        lines.append("")

    # Per-pattern detail (sorted; capped to first 400 rows for summary brevity)
    sorted_trades = sorted(trades, key=lambda x: (x.ticker, x.trough_1_date, x.ruleset_name))
    cap = 400
    lines.append(
        f"## Per-pattern detail (first {min(len(sorted_trades), cap)} rows; sorted by ticker then trough_1_date)"
    )
    lines.append("")
    lines.append(
        "| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |"
    )
    lines.append(
        "|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|"
    )
    for t in sorted_trades[:cap]:
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
    if len(sorted_trades) > cap:
        lines.append("")
        lines.append(f"_(per-pattern detail truncated at {cap} rows; see results.csv for full table)_")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- R-multiple = (exit_price - entry_price) / (entry_price - initial_stop).")
    lines.append("- For scale-out trades (Ruleset F), r_multiple is the WEIGHTED final R:")
    lines.append("  scale_fraction * scale_R + (1 - scale_fraction) * final_R.")
    lines.append("- exit_reason `_after_scaleout` suffix indicates scale-out fired before final exit.")
    lines.append("- Win-rate denominator = closed trades (excludes untriggered + open).")
    lines.append("- Entry = next-session open after first close > center_peak_price.")
    lines.append("- Initial stop varies per ruleset:")
    lines.append("    - A/B/C/D/F: trough_2_price * 0.99 (canonical W right-shoulder buffer)")
    lines.append("    - E: max(trough_2 * 0.99, entry * 0.92) (O'Neil 8% max loss floor)")
    lines.append(
        "- Trigger search window lower bound: STRICTLY AFTER "
        "max(trough_1_date, trough_2_date, effective_asof_date) "
        "where effective_asof = max(anchor_asof, max_observed_asof). "
        "Upper bound (INCLUSIVE): effective_asof + 60 business days."
    )
    lines.append("- All non-momentum-gate exits CLOSE-based; momentum_gate_fail (F) is OPEN-based at session 6.")
    lines.append("- OHLCV source: V2 Shape A reader at ~/swing-data/prices-cache/ (L2 LOCK preserved).")
    lines.append("- L6 caveat: forward-walk bars come from CURRENT archive; may differ from V1 contemporaneous state.")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _composite_bucket_stats(
    trades: list[Trade],
) -> dict[str, dict[str, dict]]:
    """Per-(composite_bucket, ruleset) stats."""
    buckets: dict[str, dict[str, list[Trade]]] = defaultdict(lambda: defaultdict(list))
    for t in trades:
        c = t.composite_score
        if c >= 0.9:
            label = "composite_0.9_plus"
        elif c >= 0.7:
            label = "composite_0.7_to_0.9"
        else:
            label = "composite_below_0.7"
        buckets[label][t.ruleset_name].append(t)

    out: dict[str, dict[str, dict]] = {}
    for blabel, by_rs in buckets.items():
        out[blabel] = {}
        for rs_name, rs_trades in by_rs.items():
            closed = [t for t in rs_trades if t.status == "closed"]
            winners = [t for t in closed if t.r_multiple is not None and t.r_multiple > 0]
            triggered = [t for t in rs_trades if t.triggered]
            closed_R = [t.r_multiple for t in closed if t.r_multiple is not None]
            out[blabel][rs_name] = {
                "total": len(rs_trades),
                "triggered": len(triggered),
                "closed": len(closed),
                "winners": len(winners),
                "expectancy_R_closed": (
                    statistics.mean(closed_R) if closed_R else None
                ),
            }
    return out


def per_ruleset_patterns_count(trades: list[Trade]) -> dict[str, int]:
    """Count distinct pattern_id values per ruleset (Codex R1 M#5).

    For D2, every ruleset should process the SAME population of patterns;
    surfacing per-ruleset counts in the manifest makes any divergence
    (e.g., a future ruleset that skip-emits patterns) operator-visible.
    """
    out: dict[str, set[str]] = defaultdict(set)
    for t in trades:
        out[t.ruleset_name].add(t.pattern_id)
    return {rs: len(pids) for rs, pids in out.items()}


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
    per_ruleset_patterns: dict[str, int] | None = None,
    both_exist_diagnostic_count: int = 0,
    rulesets_count: int = 6,
    l2_lock_preserved: bool = True,
    harness_version: str = "0.1.0",
    source_artifact_manifest_path: str | None = None,
    source_artifact_manifest_sha256: str | None = None,
    source_results_csv_sha256: str | None = None,
    source_cohort_input_sha256: str | None = None,
    recency_filter_active: bool = True,
) -> None:
    """Emit manifest.json with full provenance + 6-ruleset enumeration.

    Per dispatch brief Section 4.3 + Codex R1 M#5: includes per-ruleset
    patterns_count + both-exist diagnostic count (V1 source-ladder
    consistency surface) in addition to SHA / ruleset / L2 fields.
    """
    manifest = {
        "harness_version": harness_version,
        "harness_name": "w_bottom_ruleset_comparison",
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
        "rulesets_count": rulesets_count,
        "rulesets_enumerated": [
            "A_minervini_trail_ma",
            "B_fixed_R_multiple",
            "C_close_below_50d",
            "D_minervini_stage2_progression",
            "E_oneil_cup_with_handle_measured_move",
            "F_qullamaggie_momentum_burst",
        ],
        "per_ruleset_patterns_count": per_ruleset_patterns or {},
        "both_exist_diagnostic_count": both_exist_diagnostic_count,
        "skipped_patterns": skipped_patterns,
        "l2_lock_preserved": l2_lock_preserved,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
