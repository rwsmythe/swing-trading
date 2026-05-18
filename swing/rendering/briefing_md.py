"""Markdown briefing renderer — transition output (spec §6.4)."""
from __future__ import annotations

from swing.rendering.view_models import BriefingViewModel


def render_briefing_md(vm: BriefingViewModel) -> str:
    parts: list[str] = []
    parts.append(f"# Swing Briefing \u2014 {vm.action_session_date}")
    parts.append(f"_Data as of {vm.data_asof_date} \u00b7 Generated {vm.generated_at}_\n")

    # Schwab API arc-closer Sub-bundle D Task T-D.5 \u2014 degraded banner.
    # Emitted near the top (after header, before market weather) when the
    # most-recent schwab_api_calls row's status != 'success'. Generic copy
    # per spec \u00a73.4.4 / \u00a77.2 \u2014 does NOT echo error_message body content
    # (operator runs `swing schwab status` for diagnostic detail).
    if vm.schwab_degraded_endpoint is not None:
        endpoint = vm.schwab_degraded_endpoint
        parts.append(
            f"> **Schwab integration: degraded** \u2014 most recent API call "
            f"to `{endpoint}` did not succeed. Run `swing schwab status` to "
            f"diagnose.\n"
        )

    parts.append("## Market Weather")
    parts.append(f"**Status:** {vm.status_strip.weather.status}")
    parts.append(f"_{vm.status_strip.weather.rationale}_")
    parts.append(f"Implication: {vm.status_strip.weather.sizing_implication}\n")

    parts.append("## Account")
    a = vm.status_strip.account
    parts.append(
        f"Equity ${a.equity:.2f} \u00b7 Positions {a.open_count} / "
        f"{a.soft_warn} warn / {a.hard_cap} cap\n"
    )

    parts.append("## Today's Decisions")
    if not vm.todays_decisions:
        parts.append("_No decisions today \u2014 watchlist below._\n")
    else:
        for d in vm.todays_decisions:
            parts.append(f"### {d.ticker} \u2014 {d.action_text}")
            parts.append(
                f"Risk ${d.risk_dollars:.0f} ({d.risk_pct:.2f}%) \u00b7 "
                f"TT {d.tt_score} \u00b7 VCP {d.vcp_score}"
            )
            parts.append(f"_{d.rationale}_\n")

    if vm.open_positions:
        parts.append("## Open Positions")
        parts.append("| Ticker | Shares | Entry | Stop | Last | Unrl | R | Days |")
        parts.append("|---|---|---|---|---|---|---|---|")
        for p in vm.open_positions:
            parts.append(
                f"| {p.ticker} | {p.shares} | "
                f"${p.entry_price:.2f} | ${p.current_stop:.2f} | "
                f"${p.last_close:.2f} | ${p.unrealized_pnl:.2f} | "
                f"{p.r_so_far:.2f}R | {p.days_open} |"
            )
        for p in vm.open_positions:
            for s in p.advisory:
                parts.append(f"- **{p.ticker} \u00b7 {s.rule}:** {s.message}")
        parts.append("")

    # Phase 8 §7.4 — Daily Management Snapshot subsection. Always-emitted
    # heading (stable section anchor); body branches between (a) per-trade
    # rows, (b) no-open-positions marker, (c) open-trades-but-no-snapshots
    # operator-actionable marker per Codex R3 M3.
    parts.append("## Daily Management Snapshot")
    if vm.daily_management_snapshots:
        parts.append(
            "| Ticker | As-of session | MFE-to-date (R) | "
            "MAE-to-date (R) | Maturity stage | Trail-MA eligible |"
        )
        parts.append("|---|---|---|---|---|---|")
        for s in vm.daily_management_snapshots:
            mfe = f"{s.open_MFE_R_to_date:.2f}" if s.open_MFE_R_to_date is not None else ""
            mae = f"{s.open_MAE_R_to_date:.2f}" if s.open_MAE_R_to_date is not None else ""
            stage = s.maturity_stage or ""
            eligible = "yes" if s.trail_MA_eligibility_flag == 1 else "no"
            parts.append(
                f"| {s.ticker} | {s.data_asof_session} | {mfe} | {mae} | "
                f"{stage} | {eligible} |"
            )
        parts.append("")
    elif vm.daily_management_open_trade_count_without_snapshot > 0:
        n = vm.daily_management_open_trade_count_without_snapshot
        parts.append(
            f"_{n} open positions; no daily-management snapshot available "
            f"(pipeline step skipped or failed)._\n"
        )
    else:
        parts.append("_No open positions to manage._\n")

    # Phase 12 Sub-bundle C T-C.9 — Reconciliation status section per
    # spec §7.5. Emit ONLY when ANY of the three counters is > 0 (avoid
    # noise on clean runs); the operator's daily/weekly cadence card
    # reads from the dashboard banner; this briefing section is a written
    # summary that pairs the actionable count with the CLI command lines
    # so operator can copy/paste from the briefing into their terminal.
    #
    # Phase 12.5 #1 T-1.11 — widen predicate to include the multi-leg
    # auto-redirect counter; add the F22-locked line "- Multi-leg
    # auto-redirects applied this run: K" IMMEDIATELY BEFORE the tier-1
    # auto-corrected line WHEN K > 0 (line itself omitted when K == 0).
    # F22 wording is BINDING: "applied this run" verbatim — do NOT
    # paraphrase to "(last 7 days)" or "(this run)" (spec §11.2).
    pending = vm.reconciliation_pending_count
    tier1_recent = vm.reconciliation_tier1_recent_count
    tier1_multi_leg_redirected = (
        vm.reconciliation_tier1_multi_leg_redirected_count
    )
    if pending > 0 or tier1_recent > 0 or tier1_multi_leg_redirected > 0:
        parts.append("## Reconciliation status")
        if tier1_multi_leg_redirected > 0:
            parts.append(
                f"- Multi-leg auto-redirects applied this run: "
                f"{tier1_multi_leg_redirected}"
            )
        parts.append(f"- Tier-1 auto-corrected (last 7 days): {tier1_recent}")
        parts.append(f"- Tier-2 pending operator review: {pending}")
        parts.append("")
        parts.append(
            "View pending ambiguities: "
            "`swing journal discrepancy list-pending-ambiguities`"
        )
        parts.append(
            "Resolve a specific one: "
            "`swing journal discrepancy resolve-ambiguity <id> "
            "--choice <code> --reason <text>`"
        )
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
