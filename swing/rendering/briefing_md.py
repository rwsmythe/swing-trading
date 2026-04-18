"""Markdown briefing renderer — transition output (spec §6.4)."""
from __future__ import annotations

from swing.rendering.view_models import BriefingViewModel


def render_briefing_md(vm: BriefingViewModel) -> str:
    parts: list[str] = []
    parts.append(f"# Swing Briefing \u2014 {vm.action_session_date}")
    parts.append(f"_Data as of {vm.data_asof_date} \u00b7 Generated {vm.generated_at}_\n")

    parts.append("## Market Weather")
    parts.append(f"**Status:** {vm.status_strip.weather.status}")
    parts.append(f"_{vm.status_strip.weather.rationale}_")
    parts.append(f"Implication: {vm.status_strip.weather.sizing_implication}\n")

    parts.append("## Account")
    a = vm.status_strip.account
    parts.append(f"Equity ${a.equity:.2f} \u00b7 Positions {a.open_count} / {a.soft_warn} warn / {a.hard_cap} cap\n")

    parts.append("## Today's Decisions")
    if not vm.todays_decisions:
        parts.append("_No decisions today \u2014 watchlist below._\n")
    else:
        for d in vm.todays_decisions:
            parts.append(f"### {d.ticker} \u2014 {d.action_text}")
            parts.append(f"Risk ${d.risk_dollars:.0f} ({d.risk_pct:.2f}%) \u00b7 TT {d.tt_score} \u00b7 VCP {d.vcp_score}")
            parts.append(f"_{d.rationale}_\n")

    if vm.open_positions:
        parts.append("## Open Positions")
        parts.append("| Ticker | Shares | Entry | Stop | Last | Unrl | R | Days |")
        parts.append("|---|---|---|---|---|---|---|---|")
        for p in vm.open_positions:
            parts.append(
                f"| {p.ticker} | {p.shares} | ${p.entry_price:.2f} | ${p.current_stop:.2f} | "
                f"${p.last_close:.2f} | ${p.unrealized_pnl:.2f} | {p.r_so_far:.2f}R | {p.days_open} |"
            )
        for p in vm.open_positions:
            for s in p.advisory:
                parts.append(f"- **{p.ticker} \u00b7 {s.rule}:** {s.message}")
        parts.append("")

    if vm.watchlist:
        parts.append("## Watchlist")
        parts.append("| Flag | Ticker | Last | Pivot | %\u2192 | ADR | Stop | Status |")
        parts.append("|---|---|---|---|---|---|---|---|")
        for w in vm.watchlist:
            flag = "\u26a1" if w.is_near_trigger else ""
            adr = f"{w.adr_pct:.1f}%" if w.adr_pct is not None else ""
            parts.append(
                f"| {flag} | {w.ticker} | ${w.current_close:.2f} | ${w.entry_target:.2f} | "
                f"{w.pct_to_pivot:+.2f}% | {adr} | ${w.current_stop:.2f} | {w.status} |"
            )
        parts.append("")

    return "\n".join(parts)
