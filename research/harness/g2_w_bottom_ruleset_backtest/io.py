"""Artifact emitters for the G2 W-bottom ruleset backtest.

Writes the smoke artifact bundle:
  - manifest.json: run timestamp + substrate SHAs + counts + provenance
  - summary.md: human-readable run summary (per-substrate + cross-ruleset)
  - scorecard.csv: 9-metric scorecard per (ruleset, substrate) cell
  - per_trade_detail.csv: per-(ruleset, substrate, trade) forensic rows
  - narrative_synthesis.md: per-ruleset narrative + cross-substrate
    consistency (DESCRIPTIVE labels only; gotcha #33 banned-verdict-terms
    LOCK preserved)

ASCII discipline LOCKED (gotcha #32 declared-scope; all emitted files
are ASCII-only).
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, fields as dc_fields
from datetime import datetime, timezone
from pathlib import Path

from research.harness.g2_w_bottom_ruleset_backtest.scorecard import (
    R_DOLLAR_SIZE_AT_7500_FLOOR,
    SCORECARD_CSV_HEADER,
    ScorecardRow,
    write_scorecard_csv,
)
from research.harness.w_bottom_ruleset_comparison.walkforward import Trade


# Per-trade CSV header: field order matches Trade dataclass fields verbatim
# for round-trip parity with the existing harness's results.csv schema.
_TRADE_FIELD_NAMES: tuple[str, ...] = tuple(f.name for f in dc_fields(Trade))

PER_TRADE_DETAIL_HEADER: tuple[str, ...] = ("substrate_name",) + _TRADE_FIELD_NAMES


def write_per_trade_detail_csv(
    trades_by_substrate: dict[str, list[Trade]], output_path: Path
) -> None:
    """Emit per-trade rows tagged with substrate_name for forensic analysis.

    One row per (ruleset, trade) within each substrate; substrate_name
    surfaces as the leading column so cross-substrate comparison can
    GROUP BY substrate downstream.
    """
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(PER_TRADE_DETAIL_HEADER)
        for substrate_name in sorted(trades_by_substrate.keys()):
            for trade in trades_by_substrate[substrate_name]:
                row = [substrate_name]
                for field_name in _TRADE_FIELD_NAMES:
                    row.append(_csv_format_trade_field(getattr(trade, field_name)))
                writer.writerow(row)


def _csv_format_trade_field(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_manifest(
    output_path: Path,
    *,
    started_at_utc: datetime,
    finished_at_utc: datetime,
    substrates_summary: dict[str, dict],
    rulesets_total: int,
    rulesets_existing_af: int,
    rulesets_new_ghi: int,
    scorecard_row_count: int,
    per_trade_row_count: int,
    r_dollar_size_at_7500_floor: float,
    cache_dir: str,
    g2_version: str = "1.0",
) -> None:
    """Emit run manifest JSON.

    Contents:
      - run_started_utc / run_finished_utc / duration_seconds
      - g2_version (methodology semantic version)
      - rulesets_total / rulesets_existing_af / rulesets_new_ghi
      - substrates_summary: per-substrate metadata (name, fixture_path,
        cohort_sha256, n_unique, n_filtered, filter_spec)
      - scorecard_row_count + per_trade_row_count
      - r_dollar_size_at_7500_floor (= $75 LOCK per brief Sec 11 Q4)
      - cache_dir (the OHLCV Shape A archive directory consumed)
      - schwab_api_calls: 0 (L2 LOCK assertion)
      - production_swing_writes: 0 (L2 LOCK assertion)
      - yfinance_fetches: 0 (L2 LOCK assertion; all OHLCV via Shape A cache)
    """
    manifest = {
        "g2_version": g2_version,
        "run_started_utc": started_at_utc.isoformat(),
        "run_finished_utc": finished_at_utc.isoformat(),
        "duration_seconds": (finished_at_utc - started_at_utc).total_seconds(),
        "rulesets_total": rulesets_total,
        "rulesets_existing_af": rulesets_existing_af,
        "rulesets_new_ghi": rulesets_new_ghi,
        "substrates_summary": substrates_summary,
        "scorecard_row_count": scorecard_row_count,
        "per_trade_row_count": per_trade_row_count,
        "r_dollar_size_at_7500_floor": r_dollar_size_at_7500_floor,
        "cache_dir": cache_dir,
        "schwab_api_calls": 0,
        "production_swing_writes": 0,
        "yfinance_fetches_at_backtest_time": 0,
    }
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


def write_summary_markdown(
    output_path: Path,
    *,
    started_at_utc: datetime,
    scorecard_rows: list[ScorecardRow],
    substrates_summary: dict[str, dict],
    cache_dir: str,
) -> None:
    """Emit human-readable summary.md with per-substrate scorecard tables.

    Format:
      # G2 W-Bottom Ruleset Backtest -- Smoke Summary
      Started: <ISO>
      Cache dir: <path>
      ## Substrate <name> (N_filtered of N_raw verdicts; filter spec)
      | ruleset | n_patterns | n_triggered | n_closed | expectancy_R | ...
      [... cross-substrate consistency note at end ...]

    DESCRIPTIVE labels only; NO PARTIAL POSITIVE / NEGATIVE / POSITIVE
    per gotcha #33 LOCK.
    """
    lines: list[str] = []
    lines.append("# G2 W-Bottom Ruleset Backtest -- Smoke Summary")
    lines.append("")
    lines.append(f"Run started UTC: {started_at_utc.isoformat()}")
    lines.append(f"Cache dir: {cache_dir}")
    lines.append("")
    lines.append(
        f"R dollar size at $7500 floor: ${R_DOLLAR_SIZE_AT_7500_FLOOR:.2f}/R "
        f"(1% risk * $7500 floor; brief Sec 11 Q4 LOCK)."
    )
    lines.append("")

    # Per-substrate scorecard tables
    substrate_names = sorted({row.substrate_name for row in scorecard_rows})
    for sub_name in substrate_names:
        meta = substrates_summary.get(sub_name, {})
        lines.append(f"## Substrate: {sub_name}")
        lines.append("")
        if meta:
            lines.append(
                f"Patterns: {meta.get('n_filtered', '?')} of "
                f"{meta.get('n_raw', '?')} raw verdicts; "
                f"filter spec: {meta.get('filter_spec', '?')}."
            )
            lines.append(
                f"Fixture: `{meta.get('fixture_path', '?')}` "
                f"(SHA256 `{meta.get('cohort_sha256', '?')}`)."
            )
            lines.append(
                f"Substrate window days (earliest-to-latest asof): "
                f"{meta.get('substrate_window_days', '?')}."
            )
            lines.append("")
        lines.append(
            "| Ruleset | N_patterns | N_triggered | N_closed | "
            "Expectancy_R | Win_rate | Avg_win_R | Avg_loss_R | "
            "Profit_factor | Trigger_conv | Median_days | "
            "Open_at_tail_n | Open_at_tail_rate | Est_$/period |"
        )
        lines.append(
            "|---------|-----------:|------------:|---------:|"
            "-------------:|---------:|----------:|-----------:|"
            "--------------:|-------------:|------------:|"
            "---------------:|-------------------:|-------------:|"
        )
        for row in sorted(
            [r for r in scorecard_rows if r.substrate_name == sub_name],
            key=lambda r: r.ruleset_name,
        ):
            lines.append(
                "| " + " | ".join(
                    [
                        row.ruleset_name,
                        str(row.n_patterns),
                        str(row.n_triggered),
                        str(row.n_closed),
                        _fmt_or_na(row.expectancy_R),
                        _fmt_or_na(row.win_rate),
                        _fmt_or_na(row.avg_win_R),
                        _fmt_or_na(row.avg_loss_R),
                        _fmt_or_na(row.profit_factor),
                        _fmt_or_na(row.trigger_conversion_rate),
                        _fmt_or_na(row.median_time_in_trade_sessions, "{:.1f}"),
                        str(row.open_at_tail_count),
                        _fmt_or_na(row.open_at_tail_rate),
                        _fmt_or_na(row.estimated_dollar_per_period, "${:.2f}"),
                    ]
                ) + " |"
            )
        lines.append("")

    # Cross-substrate consistency block (descriptive only)
    lines.append("## Cross-substrate scorecard observations")
    lines.append("")
    lines.append(
        "Per gotcha #33 (cohort-validity-vs-verdict-criteria), each "
        "(ruleset, substrate) cell's scorecard is its own data point. "
        "Cross-substrate comparison surfaces ruleset robustness vs "
        "cohort-specificity DESCRIPTIVELY across the 9 metrics; no "
        "single categorical verdict is emitted (banned-verdict-terms "
        "LOCK preserved)."
    )
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _fmt_or_na(value, fmt: str = "{:.4f}") -> str:
    if value is None:
        return "n/a"
    return fmt.format(value)


def write_narrative_synthesis_markdown(
    output_path: Path,
    *,
    scorecard_rows: list[ScorecardRow],
) -> None:
    """Emit per-ruleset narrative interpretation across the 9 metrics.

    Per brief Sec 1.4: 'Headline interpretation is narrative across the
    9 metrics; the findings doc may emit DESCRIPTIVE narrative ... but
    NEVER the banned terms.' This module emits ONLY mechanical
    metric-grouping narrative; verdict-style synthesis is operator-paired
    in the findings doc.
    """
    lines: list[str] = []
    lines.append("# G2 W-Bottom Ruleset Backtest -- Narrative Synthesis")
    lines.append("")
    lines.append(
        "Per-ruleset descriptive interpretation across the 9-metric "
        "scorecard. NO categorical verdict labels emitted per cohort-"
        "validity discipline (gotcha #33 third canonical application)."
    )
    lines.append("")

    ruleset_names = sorted({row.ruleset_name for row in scorecard_rows})
    for rs_name in ruleset_names:
        rs_rows = sorted(
            [r for r in scorecard_rows if r.ruleset_name == rs_name],
            key=lambda r: r.substrate_name,
        )
        lines.append(f"## Ruleset: {rs_name}")
        lines.append("")
        for row in rs_rows:
            lines.append(f"### Substrate: {row.substrate_name}")
            lines.append("")
            lines.append(_describe_row(row))
            lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _describe_row(row: ScorecardRow) -> str:
    """Generate descriptive narrative for one scorecard row.

    Avoids categorical verdict labels; uses neutral metric-summary
    language (e.g., 'expectancy is X.YR with Z winners' rather than
    'this ruleset is profitable / positive').
    """
    if row.n_triggered == 0:
        return (
            f"All {row.n_patterns} patterns failed to trigger entry under "
            f"this ruleset; no closed trades; estimated dollar projection "
            f"is $0.00 (trigger conversion rate 0.0)."
        )
    parts = [
        f"Of {row.n_patterns} patterns, {row.n_triggered} triggered entry "
        f"(conversion rate {row.trigger_conversion_rate:.3f}); "
        f"{row.n_closed} closed and {row.open_at_tail_count} remain open "
        f"at the data tail."
    ]
    if row.expectancy_R is None:
        parts.append("No closed trades; expectancy metrics undefined.")
    else:
        parts.append(
            f"Expectancy {row.expectancy_R:+.3f}R across closed trades; "
            f"win rate {row.win_rate:.3f}; "
            f"avg winner {_fmt_or_na(row.avg_win_R, '{:+.3f}R')}; "
            f"avg loser {_fmt_or_na(row.avg_loss_R, '{:.3f}R')}; "
            f"profit factor {_fmt_or_na(row.profit_factor, '{:.3f}')}; "
            f"median time in trade "
            f"{_fmt_or_na(row.median_time_in_trade_sessions, '{:.1f}')} "
            f"sessions."
        )
        if row.estimated_dollar_per_period is not None:
            parts.append(
                f"At $75/R sizing ($7500 floor + 1% risk per brief Sec 11 Q4) "
                f"the estimated dollar per period extrapolation is "
                f"${row.estimated_dollar_per_period:+.2f} over "
                f"{row.substrate_window_days}-day substrate window."
            )
    return " ".join(parts)
