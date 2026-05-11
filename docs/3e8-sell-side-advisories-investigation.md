# 3e.8 — Sell-side advisories investigation

**Status:** investigation analysis (no code change in this dispatch).
**Brief:** `docs/3e8-sell-side-advisories-investigation-brief.md`.
**Baseline SHA:** `fa0a0ac` (HEAD of `main` post-3e.10 housekeeping).
**Worktree branch:** `3e8-sell-side-advisories-investigation`.
**Operator urgency:** DHC trade (open since 2026-04-27) is approaching the +1.5R / 20MA trail decision territory per `docs/orchestrator-context.md` "Tier-3 #6" framing.

---

## §0 Reader's guide

This document answers two questions:

1. **What sell-side advisories does the framework emit today?** (§1)
2. **What's missing relative to the three doctrine sources (Minervini SEPA + Disciplined Swing Trader + Qullamaggie commentary), and what should be added, classified, and gated by Tier-3 #6 maturity stage?** (§2 → §6)

The deliverable is operator-facing analysis. No production code or schema changes are proposed here for direct landing; each recommendation in §4 carries an explicit classification (advisory-message-only OR classification-altering per the locked design decisions in the brief §0.5 #4) plus a Tier-3 #6 per-stage gating matrix in §5. Operator decides which recommendations to commission for subsequent dispatch.

### §0.1 Doctrine source availability

This is the single most important finding for citation discipline:

| Source | Form available to investigation | Citable directly? |
|---|---|---|
| Minervini Trend Template (BUY-side, 8 criteria) | `reference/methodology/minervini-trend-template.md` (transcribed from *Trade Like a Stock Market Wizard*, McGraw Hill 2013, ch. 5, p. 79) | **Yes** |
| Minervini SEPA / VCP / sell-side rules (sell-into-strength, 7-week rule, parabolic-extension, violated-MA-on-volume) | Physical book only — NOT transcribed | **No** — every claim flagged `[UNVERIFIED — physical-copy-only claim; flag for operator]` |
| Disciplined Swing Trader (DST) full content | Not transcribed in `reference/methodology/` (only `minervini-trend-template.md` exists there per `git ls-files reference/methodology/`) | **No** — every claim flagged `[UNVERIFIED — physical-copy-only claim; flag for operator]` |
| Qullamaggie trading commentary | `mcp__qullamaggie__*` MCP server (437 video transcripts, Oct 2019 – Dec 2021, ~2.5M words; reference-only per CLAUDE.md memory) | **Yes** — citations carry `[Qullamaggie video N, YYYY-MM-DD]` provenance |

Implication: the analysis can cite Qullamaggie sell-side rules with confidence; **every** Minervini and DST sell-side rule referenced below is flagged with `[UNVERIFIED — physical-copy-only claim; flag for operator]` and represents the implementer's best memory of the doctrine pending operator confirmation. This is the operator's call to make from the physical copies; the implementer cannot substitute for it. This is treated as a structural project gap (§3.G) — independently of any recommendation accepted from §4, the analysis surfaces the transcription gap itself as an operator decision in §6.

### §0.2 Terminology

- **Advisory** = framework-emitted suggestion to the operator (e.g., "Move stop to breakeven", "Trail stop up to $X — 0.3% below 20MA"). Rendered in the open-positions row Advisory column. Non-binding.
- **Operator action** = post-fact capture of what the operator actually did (e.g., Phase 8 `daily_management_records.action_taken` enum: `hold` / `trim` / `exit` / `stop` / `move_stop` / `no_action`). Recorded by the operator via the daily-management form; not framework-initiated.
- **Sell-side advisory** = any advisory whose triggered action is to reduce or close a long position. Includes: trim (partial exit into strength), exit (close), tighten-stop (raise stop). Excludes: pure stop-management advisories on losers (already covered by initial-stop discipline).
- **Tier-3 #6 maturity stages** = `pre_+1.5R` / `+1.5R_to_+2R` / `>=+2R_trail_eligible` per `swing/data/migrations/0016_phase8_daily_management.sql` line 60-62 CHECK constraint. The operator's verbal framing also includes a "new (~0R)" stage below `pre_+1.5R`; for this document the four-stage taxonomy is **new → maturing → mature → well-mature** per the brief §0.4, mapped to the DB enum as new+maturing = `pre_+1.5R`, mature = `+1.5R_to_+2R`, well-mature = `>=+2R_trail_eligible`.

---

## §1 Current sell-side advisory surface

### §1.1 Surface enumeration: `swing/trades/advisory.py`

The advisory rule surface is enumerated in [`swing/trades/advisory.py:111-123`](swing/trades/advisory.py) (`compute_all_suggestions`). Eight rule instances fire per render (defined as eight `sugs.append(...)` lines; semantically there are five RULE FAMILIES because `suggest_trail_ma` and `suggest_exit_close_below_ma` are each instantiated twice or three times against different MA periods):

| # | Rule | Trigger condition (verbatim from code) | Sell-side? | Source location |
|---|---|---|---|---|
| 1 | **breakeven** | `r_so_far(trade, ctx.current_price) >= ctx.config.breakeven_r_trigger` (default +1.0R) AND `trade.current_stop < trade.entry_price` | Stop-management (raises stop, locks in no-loss; not a sell signal per se) | [`advisory.py:35-43`](swing/trades/advisory.py#L35-L43) |
| 2 | **trail_10ma** | `ctx.current_price >= ctx.sma10` AND `ceiling-round(sma10 × (1 - 0.3%/100) × 100) / 100 > trade.current_stop` | Stop-management (trails stop up) | [`advisory.py:46-62`](swing/trades/advisory.py#L46-L62) instantiated at [`advisory.py:114-115`](swing/trades/advisory.py#L114-L115) |
| 3 | **trail_20ma** | `ctx.current_price >= ctx.sma20` AND `ceiling-round(sma20 × (1 - 0.3%/100) × 100) / 100 > trade.current_stop` | Stop-management (trails stop up) | [`advisory.py:46-62`](swing/trades/advisory.py#L46-L62) instantiated at [`advisory.py:116-117`](swing/trades/advisory.py#L116-L117) |
| 4 | **exit_below_10ma** | `ctx.previous_close < ctx.sma10` (yesterday's daily close below 10MA; not intraday) | **Sell** (issues "EXIT — yesterday's close $X is below 10MA ($Y)") | [`advisory.py:65-80`](swing/trades/advisory.py#L65-L80) instantiated at [`advisory.py:118`](swing/trades/advisory.py#L118) |
| 5 | **exit_below_20ma** | `ctx.previous_close < ctx.sma20` | **Sell** | [`advisory.py:65-80`](swing/trades/advisory.py#L65-L80) instantiated at [`advisory.py:119`](swing/trades/advisory.py#L119) |
| 6 | **exit_below_50ma** | `ctx.previous_close < ctx.sma50` | **Sell** | [`advisory.py:65-80`](swing/trades/advisory.py#L65-L80) instantiated at [`advisory.py:120`](swing/trades/advisory.py#L120) |
| 7 | **weather** | `ctx.weather_status` starts with `bearish` → "tighten stops or exit longs"; starts with `caution` → "tighten stops; consider half sizing" | Mixed advisory (tighten + optional exit on `bearish`; tighten-only on `caution`) | [`advisory.py:83-95`](swing/trades/advisory.py#L83-L95) |
| 8 | **time_stop** | `days_open > 10` (`cfg.stop_advisory.time_stop_days`) AND `r_so_far < 0.5R` (`time_stop_min_r`) | **Sell** ("Time stop — N days open with only +X.XXR; consider exit") | [`advisory.py:98-108`](swing/trades/advisory.py#L98-L108) |

**Sell-side advisory count today:** 4 explicit sell rules (exit_below_{10,20,50}ma + time_stop) + 2 mixed (weather bearish/caution) + 0 trim/partial-exit rules + 0 maturity-aware rules.

**Stop-management advisory count today:** 3 (breakeven, trail_10ma, trail_20ma). These RAISE the stop but do not directly emit a sell signal; the actual sell, if it happens, is via stop-out.

**Config defaults** ([`swing/config.py:90-96`](swing/config.py#L90-L96)):
- `breakeven_r_trigger = 1.0` (R)
- `trail_10ma_buffer_pct = 0.3` (percent below 10MA)
- `trail_20ma_buffer_pct = 0.3` (percent below 20MA)
- `time_stop_days = 10`
- `time_stop_min_r = 0.5`

### §1.2 Emission surface (where advisories render)

The eight rule outputs flow through [`swing/web/view_models/dashboard.py:939-976`](swing/web/view_models/dashboard.py#L939-L976), wrapping each suggestion in `AdvisorySuggestionVM(rule=..., message=...)` per trade. Rendering surfaces:

| Surface | Renders | Notes |
|---|---|---|
| Dashboard `/` open-positions row, Advisory column | All non-None suggestions per trade, one `<div>` per message | [`swing/web/templates/partials/open_positions_row.html.j2:39-43`](swing/web/templates/partials/open_positions_row.html.j2#L39-L43); rendered server-side via `OpenPositionsRowVM.advisories: tuple[AdvisorySuggestionVM, ...]` |
| Trade detail page `/trades/{id}` | **NOT rendered** — checked [`swing/web/templates/trades/detail.html.j2`](swing/web/templates/trades/detail.html.j2) (no `advisor` token); per-trade detail surface shows fills + events but not the dashboard advisory column | Gap surfaced in §3 |
| Open-positions expanded row `/trades/open/{id}/expand` | **NOT rendered** — partial header explicitly notes "chart only — no P&L breakdown, no advisories list, no recent events" ([`swing/web/templates/partials/open_positions_expanded.html.j2:5`](swing/web/templates/partials/open_positions_expanded.html.j2#L5)) | Intentional by partial; gap surfaced in §3 |
| Daily-management dashboard tile (Phase 8) | trail-MA eligibility badge + maturity badge + capital % + heat $ — but **NOT** the advisory rule output | [`swing/web/templates/partials/daily_management_tile.html.j2:80-89`](swing/web/templates/partials/daily_management_tile.html.j2#L80-L89); separate VM-driven surface from open-positions Advisory column |
| Pipeline-emitted briefing (`exports/<session>/briefing.md`, `briefing.html`) | **EMPTY** — pipeline path constructs `BriefingInputs(... open_trade_advisories={}, ...)` at [`swing/pipeline/runner.py:921`](swing/pipeline/runner.py#L921); the briefing template still has an `advisory:` field per `OpenPositionVM` ([`swing/rendering/briefing.py:134`](swing/rendering/briefing.py#L134)) but it gets an empty list | **Implementation observation** — the briefing emits open positions with empty advisory lists; the operator only sees advisories on the web dashboard, not in the briefing. Investigation surfaces this in §3 |

**Emission cadence:**
- Web dashboard: per-request render. Each GET `/` recomputes all eight rules.
- Pipeline: per-run, but advisory output is suppressed (`open_trade_advisories={}`). No persistence.
- No advisory is persisted to DB. Each render is stateless.

### §1.3 Phase 8 daily-management `action_taken` enum

Per [`swing/data/migrations/0016_phase8_daily_management.sql:95-97`](swing/data/migrations/0016_phase8_daily_management.sql#L95-L97):

```
action_taken TEXT
    CHECK (action_taken IS NULL OR action_taken IN
           ('hold','trim','exit','stop','move_stop','no_action'))
```

This enum is **operator-captured** (post-fact event_log row submitted via the daily-management form) — NOT framework-emitted. Six values, three of which are sell-side:

| `action_taken` | Sell-side? | Captured via |
|---|---|---|
| `hold` | No (operator chose to hold the position unchanged) | event_log form |
| `trim` | **Yes** (operator reduced position size) | event_log form |
| `exit` | **Yes** (operator closed the position fully) | event_log form |
| `stop` | Yes (operator's stop was hit — sell triggered by stop-out) | event_log form |
| `move_stop` | No (operator adjusted stop; FK chain to Phase 7 stop-adjust event via `linked_trade_event_id`) | event_log form |
| `no_action` | No | event_log form |

**No automation today emits `action_taken='trim'` or `action_taken='exit'` as a recommendation prior to the operator's submission.** The framework has no equivalent of "framework suggests trim 25%" or "framework suggests exit fully" surfaced as an advisory; the dashboard advisory column emits the rules in §1.1 only.

### §1.4 Phase 6 cadence-review surface (does it carry sell-side advisories?)

Phase 6 added post-trade review surfaces (`review_log` table + `/reviews/...` routes). These are **retrospective** (post-trade-close review), not in-flight sell-side advisory. The cadence cards (daily / weekly / monthly) prompt the operator to complete reviews of closed trades; they do not emit forward-looking sell suggestions on open positions. Out of scope for this investigation per §1 brief boundary; mentioned here for completeness so the reader knows the surface was checked and is intentionally excluded.

### §1.5 What is NOT in the advisory surface today (preview of §3)

For the avoidance of doubt — surfaces or behaviors the operator might expect that the framework does NOT currently emit:

- No **trim-into-strength** advisory at any positive-R threshold.
- No **partial-sell scale-out** ladder (e.g., "first 1/3 at +X%, next 1/3 on close < 10MA, ...").
- No **parabolic-extension** detector (rapid % gain in N days → trim).
- No **volume-confirmed exit** advisory (a violated-MA-on-volume rule distinct from the daily-close-below-MA `exit_below_*ma` rules).
- No **explicit positive-R target** advisory tied to `trades.planned_target_R` (column exists per migration 0016 but is purely informational on the daily-management tile; no advisory checks "current_price reached planned_target_R").
- No **maturity-stage gating** on the existing advisory set — every rule fires regardless of whether the trade is at +0.1R or +5R (with the trivial exception that `breakeven` is gated by `r_so_far >= 1.0R` per the breakeven config, which incidentally also serves as a maturity gate). Per the brief §0.4 and operator framing, the desired discipline is **mature** trades default to 20MA trail; **well-mature** trades upgrade to 10MA trail. Today both 10MA and 20MA trail rules fire concurrently regardless of stage.

These are not bugs; they are gaps relative to doctrine. §3 enumerates them with operational urgency ranking.

---

## §2 Doctrine reconciliation

For each doctrine rule below: rule statement → source citation → framework-implementation status (`implemented` / `partially-implemented` / `not-implemented` / `[UNVERIFIED]`). Where two or three doctrines converge on the same rule that's noted as **confluence**; where they diverge that's noted as **divergence**.

### §2.1 Minervini SEPA — sell-side rules

**Source caveat for entire subsection:** `reference/methodology/` contains ONLY `minervini-trend-template.md` (8 BUY-side trend-template criteria; transcribed 2026-04-23). NO Minervini sell-side rules are transcribed. All claims below are **`[UNVERIFIED — physical-copy-only claim; flag for operator]`** and represent the implementer's best memory of the doctrine pending operator confirmation. The operator is the only person in a position to verify these claims by consulting the physical copy of *Trade Like a Stock Market Wizard*; the implementer cannot substitute for that.

| # | Doctrine claim | Framework status | Notes |
|---|---|---|---|
| M.1 | **Use 1.25× average gain over average loss as a backstop expectancy heuristic** (the math motivation for tight stops + sell-into-strength). `[UNVERIFIED]` | Indirectly — initial-stop discipline + `r_so_far` computation at [`swing/trades/equity.py`](swing/trades/equity.py) gives operator visibility into R-multiple; framework does not compute a portfolio-level batting-average × gain/loss ratio | Out of advisory-rule scope but cited because it motivates the sell-side mechanics that follow |
| M.2 | **Sell into strength** — take some profit on the way up, do not give back gains. `[UNVERIFIED]` | **Not implemented** | No trim advisory exists; operator must self-initiate `action_taken='trim'` event_log without framework prompt |
| M.3 | **Sell on a close below the N-day moving average** for staged exits. `[UNVERIFIED — physical-copy specific N values]`; the framework currently uses 10MA + 20MA + 50MA per Phase 3d Tier-3 #6 doctrine but the canonical Minervini N values are not verifiable from `reference/methodology/` | **Implemented** — `suggest_exit_close_below_ma` at [`advisory.py:65-80`](swing/trades/advisory.py#L65-L80) covers 10MA, 20MA, 50MA. **Caveat:** firing on yesterday's close (per the docstring "spec §3.3") not on intraday close-of-current-bar. Confluence with Qullamaggie (Q.4 below) on the 10MA / 20MA / 50MA ladder. | The rule logic is implemented; the Minervini-attribution of the specific MA periods is `[UNVERIFIED]` |
| M.4 | **7-week rule** — if the position hasn't made progress within 7 weeks, exit on weakness; reduce conviction. `[UNVERIFIED]` | **Not implemented** in 7-week form; partially covered by `suggest_time_stop` at [`advisory.py:98-108`](swing/trades/advisory.py#L98-L108) with default `time_stop_days=10` (calendar days) and `time_stop_min_r=0.5`. 10 days ≪ 7 weeks (49 calendar days); the rules differ in timescale + min-R threshold | Time stop fires sooner and at higher min-R; Minervini's 7-week rule (if confirmed) is materially different — longer window, lower bar |
| M.5 | **Parabolic / blow-off-top extension** — when a stock goes vertical with accelerating gains, trim aggressively; price action gets unsustainable. `[UNVERIFIED — physical-copy specific quantitative thresholds (e.g., "20%-25% in 1-3 weeks", "consecutive higher-close streak", "extension above MA")]` | **Not implemented** — no detector for rapid gains / vertical-move pattern | Confluence with Qullamaggie (Q.2 + Q.5 below — sell-into-strength + sell down extended stocks) and with putative DST take-profit-into-strength (D.2 below) |
| M.6 | **Violated MA on volume** — a close below the trail MA accompanied by above-average volume is a stronger sell signal than the close alone. `[UNVERIFIED]` | **Not implemented** — `suggest_exit_close_below_ma` checks only the close, not volume confirmation | OHLCV bundle already carries volume per [`swing/pipeline/ohlcv.py`](swing/pipeline/ohlcv.py); a volume-confirmation overlay is implementable as advisory-message-only (does not change classification logic) |
| M.7 | **Reaction to gap-down on news** — if a winner gaps down on negative news through the trail MA, sell into any opening bounce. `[UNVERIFIED]` | **Not implemented** — no intraday-gap detector | Adjacent to M.6 (volume) and Q.7 (Qullamaggie premarket-on-earnings rule) |

**Subtotal Minervini SEPA sell-side coverage:**
- Implemented: 1/7 (M.3, with caveat on N-value attribution)
- Partially-implemented: 1/7 (M.4, via time_stop with different timescale + min-R)
- Not-implemented: 5/7 (M.2, M.5, M.6, M.7, and M.1 in any direct form)
- All 7 are `[UNVERIFIED]` for the doctrine-attribution claim itself.

### §2.2 Disciplined Swing Trader (DST) — take-profit + trail rules

**Source caveat for entire subsection:** DST is NOT transcribed in `reference/methodology/`; the brief §0.3 notes "PDF should be available; check `reference/methodology/` or similar for the transcription" — investigation found ONLY the Minervini trend-template file there. The CLAUDE.md memory at `~/.claude/projects/.../project_references.md` confirms DST is a personal reference. All claims below are **`[UNVERIFIED — physical-copy-only claim; flag for operator]`**.

| # | Doctrine claim | Framework status | Notes |
|---|---|---|---|
| D.1 | **Initial stop = below most recent swing low or below the breakout pivot's reaction low.** `[UNVERIFIED]` | Out of advisory-rule scope (initial-stop discipline lives in entry flow at [`swing/trades/entry.py`](swing/trades/entry.py)); the operator sets the initial stop manually on the entry form | Sell-side investigation includes initial-stop only insofar as a tighter initial stop accelerates the trade through Tier-3 #6 maturity stages |
| D.2 | **Take partial profit into strength** — sell 1/4 to 1/3 of the position at first significant up-move; let the rest ride. `[UNVERIFIED]` | **Not implemented** | Confluence with Minervini M.2 and Qullamaggie Q.2 |
| D.3 | **Trail with the 10-day EMA on fast movers, 20-day SMA on steadier names** — the EMA-vs-SMA distinction is doctrinally specific. `[UNVERIFIED — specific MA type (EMA vs SMA) and per-stage default]` | **Partially-implemented** — `suggest_trail_ma` uses the SMA values supplied via `AdvisoryContext.sma10` / `sma20`; framework computes simple moving averages exclusively per [`swing/pipeline/ohlcv.py`](swing/pipeline/ohlcv.py); no EMA distinction | Per Tier-3 #6 framing (orchestrator-context.md): "mature (+1.5R-2R, default 20MA) → well-mature (+2R+, upgrade to 10MA)". The trail-MA period is intended to TIGHTEN as maturity increases; today both fire concurrently |
| D.4 | **Tighten stop after +2R or equivalent threshold** — operator's "trade has to prove itself; once it has, give it less room" framing. `[UNVERIFIED]` | **Implemented through Tier-3 #6 design intent**, **not implemented in advisory logic** — schema supports the maturity-stage enum (`pre_+1.5R` / `+1.5R_to_+2R` / `>=+2R_trail_eligible` per migration 0016 line 60-62) and the daily-management tile renders trail-MA eligibility badge ([`daily_management_tile.html.j2:80-89`](swing/web/templates/partials/daily_management_tile.html.j2#L80-L89)) but the advisory rules themselves do not consume `maturity_stage` to gate which MA periods fire | The schema is ready; the advisory layer needs the gate. Subsumes the Tier-3 #6 deferred work item per the brief §0.5 #3 |
| D.5 | **7-10 day vs 7-week** — short-window time stop on positions that don't activate; differs from Minervini's longer 7-week rule. `[UNVERIFIED]` | **Implemented** with config defaults `time_stop_days=10`, `time_stop_min_r=0.5` per [`swing/config.py:95-96`](swing/config.py#L95-L96) | The 10-day default is plausibly DST-influenced (closer to D.5 than to M.4). Doctrine-attribution `[UNVERIFIED]` |

**Subtotal DST sell-side coverage:**
- Implemented: 1/5 (D.5, attribution `[UNVERIFIED]`)
- Partially-implemented: 2/5 (D.3 SMA-not-EMA; D.4 schema-ready/advisory-not-wired)
- Not-implemented: 2/5 (D.1 out of scope, D.2)
- All 5 are `[UNVERIFIED]` for the doctrine-attribution claim.

### §2.3 Qullamaggie — sell-side commentary cross-check

**Source caveat for entire subsection:** Qullamaggie is reference-only per CLAUDE.md memory (`reference_qullamaggie_mcp.md`) — NOT a source-of-truth. Citations include video IDs and the implementer's `mcp__qullamaggie__*` query records so a reviewer can replay. Multi-instance rules (mentioned in N videos) are higher-confidence (Qullamaggie repeats them often).

| # | Doctrine claim (verbatim from MCP `query_trading_rules` / `search_transcripts`) | Framework status | Source |
|---|---|---|---|
| Q.1 | "If a stock doesn't go anywhere for 3-5 days, sell it." | **Partially-implemented** — `time_stop_days=10` default is longer; the principle (time-based bailout) is present, threshold differs | `query_trading_rules(category=exit)` rule 1; freq 2; videos 230, 237 (2020-12-03, 2020-12-11) |
| Q.2 | "Sell some into strength (15-20% of position) when up 10-15-20%, then trail the rest with moving averages." | **Not implemented** — no trim advisory | `query_trading_rules(category=exit)` rule 7; video 3 (2019-10-02) |
| Q.3 | "Trail long positions with the 10-day moving average; if the 10 EMA is lost, sell the long." | **Partially-implemented** — `suggest_trail_ma` covers SMA-not-EMA; `suggest_exit_close_below_ma` covers the close-below side; SMA vs EMA is a divergence | `query_trading_rules(category=exit)` rule 2; freq 2; videos 255, 256 (2021-01-11) |
| Q.4 | "Exit strategy using moving averages: first close below 10-day sell 1/4 to 1/3, first close below 20-day sell another 1/3 to 1/4, below 50-day sell more. Also have a hard stop at previous swing low that sells everything regardless." | **Partially-implemented** — `suggest_exit_close_below_ma` fires for 10MA + 20MA + 50MA but the message is "EXIT" not "sell 1/3"; no partial-exit ladder. Hard-stop-at-prior-swing-low is operator-set via the entry form's `initial_stop` field (not advisory-emitted) | `query_trading_rules(category=exit)` rule 5; freq 1; video 3 (2019-10-02) |
| Q.5 | "Sell down extended stocks that are showing signs of selling the news even if still profitable." | **Not implemented** — no parabolic / extension detector | `query_trading_rules(category=exit)` rule 3; freq 2; videos 255, 256 (2021-01-11) |
| Q.6 | "Don't tighten stops too aggressively - keep initial stop if the thesis is still valid. Raising stop cost the ROKU trade." | **Implemented by absence** — framework does NOT auto-tighten stops; `suggest_breakeven` only suggests; operator decides | `query_trading_rules(category=exit)` rule 9; video 6 (2019-10-08) |
| Q.7 | "When holding a large position into earnings, watch the premarket action constantly - sell into first few red candles when it goes red premarket." | **Not implemented** — no premarket / news / earnings handling (Phase 8 has earnings-proximity-exclusion in research branch, not in advisory layer) | `query_trading_rules(category=exit)` rule 47; video 47 (2020-01-22) |
| Q.8 | "Don't hold laggards. If a stock is lagging its sector index significantly, it's not worth swinging." | **Not implemented** — no relative-strength-vs-sector check on open positions; framework computes RS at evaluation time (entry-side) but doesn't re-evaluate open positions for sector lag | `query_trading_rules(category=exit)` rules 28-29; videos 26, 29 (2019-11-11, 2019-11-15) |
| Q.9 | "Aim for at least 1:10 risk reward for swing trading. 1:1 to 1:5 won't cut it." (and the related "swing trading allows 1:10, 1:20, 1:50 risk reward" rule) | **Not implemented as advisory** — no target-R advisory; framework does compute and store `planned_target_R` on the trades row (per migration 0016 line 21-22) but no advisory checks current price against it | `query_trading_rules(keyword=risk reward)` rules 8-10; videos 170, 171, 174 (2020-08-21 → 2020-09-01) |
| Q.10 | "Scaling out: sell into strength (20-25%), then sell a third or quarter on first close below 10-day MA, another third on close below 20-day, rest on close below 50-day. For explosive fast stocks use 10-day and 20-day (50-day too late)." | **Partially-implemented** — close-below-MA sell signals fire at 10/20/50 but as "EXIT", not as scaled "sell 1/3". The "explosive fast stocks skip 50-day" carve-out is **not implemented** — framework fires `exit_below_50ma` for all open positions regardless of pace | `query_trading_rules(category=exit)` rule 15; video 11 (2019-10-17) |
| Q.11 | "When a stock closes below both the 10-day and 20-day moving averages, lighten the position significantly." | **Implemented loosely** — two independent rules fire (`exit_below_10ma` + `exit_below_20ma`); a combined-violation rule does not exist | `query_trading_rules(category=exit)` rule 30; video 31 (2019-11-19) |
| Q.12 | "Sluggish positions after earnings — sell if they don't show the expected strength." | **Not implemented** — adjacent to Q.7 + Q.8 + time-stop family | `query_trading_rules(category=exit)` rule 32; video 31 (2019-11-19) |

**Subtotal Qullamaggie sell-side coverage (n=12 representative rules from query_trading_rules + targeted search):**
- Implemented (full or near-full): 2/12 (Q.6 by absence; Q.11 loose)
- Partially-implemented: 4/12 (Q.1, Q.3, Q.4, Q.10)
- Not-implemented: 6/12 (Q.2, Q.5, Q.7, Q.8, Q.9, Q.12)

### §2.4 Confluence + divergence map

The three doctrines converge or diverge across recurring patterns. Confluences are the strongest evidence base for a recommendation; divergences are the cases where the operator must make a judgment call.

| Pattern | Minervini | DST | Qullamaggie | Framework | Status |
|---|---|---|---|---|---|
| **Trim/sell into strength at +X%** | M.2 (`[UNVERIFIED]`) | D.2 (`[UNVERIFIED]`) | Q.2 (cited) | Not implemented | **Triple confluence** — strongest case for the addition |
| **Close-below-MA staged exit (10/20/50)** | M.3 (`[UNVERIFIED]` on N values) | D.3 (`[UNVERIFIED]` on EMA-vs-SMA) | Q.4 + Q.10 (cited; SMA-or-EMA not specified in MCP returns) | Implemented as full-exit per MA period (not staged 1/3 each) | **Confluence on the staged-MA principle; divergence on SMA vs EMA + on full-exit vs staged-1/3** |
| **Tighten stop on maturity (post-+2R)** | implicit in M.2 + M.5 | D.4 (`[UNVERIFIED]`) | implicit in Q.3 (10MA after running) | Phase 8 schema supports `maturity_stage`; advisory layer does not consume it | **Confluence on principle; gating not wired** |
| **Time stop on no-progress** | M.4 (`[UNVERIFIED]` 7-week) | D.5 (`[UNVERIFIED]` 7-10 day) | Q.1 (3-5 day; cited) | Implemented at 10 days, min-R 0.5 | **Confluence on principle; divergence on N-day threshold across all three sources (3-5 / 10 / 49)** |
| **Parabolic / blow-off exit** | M.5 (`[UNVERIFIED]`) | not directly captured | Q.5 (cited) | Not implemented | **Double confluence (M+Q); operator must adjudicate quantitative threshold** |
| **Volume-confirmed close-below-MA** | M.6 (`[UNVERIFIED]`) | not directly captured | not directly captured in surveyed rules (volume mentioned contextually in transcripts; not a top-N MCP rule) | Not implemented | **Single-source (M only); volume confirmation is a defense-in-depth overlay rather than a standalone trigger** |
| **Sector-relative-strength check on open positions** | not directly captured | not directly captured | Q.8 (cited) | Not implemented | **Single-source (Q only); higher novelty risk** |
| **Earnings-day sell discipline** | adjacent (M.2 sell-into-strength applies) | not directly captured | Q.7 + Q.12 (cited) | Not implemented; earnings-proximity is an entry-side exclusion only | **Single-source (Q only); cross-cutting with the Phase 9 earnings-proximity work** |
| **Explicit target-R hit advisory** | implicit (sell-into-strength) | implicit (D.2) | Q.9 (cited; 1:10 RR target) | Schema has `planned_target_R`; no advisory consumes it | **Triple-confluence on the principle; no source specifies a hard "trim at target hit" rule (target-R is a hold-discipline floor, not a hard sell trigger). Conservative implementation: advisory message at planned_target_R hit; operator decides** |

---

## §3 Identified gaps

This section synthesizes §2 into a ranked gap list. Ordering is by operational urgency given DHC's current trail-MA decision territory (per brief §1) and the locked Tier-3 #6 framing.

### §3.A Gap A (URGENCY: HIGH; DHC-applicable) — Maturity-stage gating of trail-MA advisories

**Symptom:** Today, `suggest_trail_ma(10MA)` and `suggest_trail_ma(20MA)` both fire concurrently for any open position whose `current_price >= sma_N`. There is no gating on maturity stage. The result: a freshly-opened trade at +0.1R sees the same trail-MA suggestions (10MA + 20MA) as a +3R trade. The operator must apply the Tier-3 #6 doctrine (default 20MA pre-+2R; upgrade to 10MA post-+2R) entirely from mental model.

**Doctrine support:** D.4 (`[UNVERIFIED]`), implicit in Q.3 (Qullamaggie talks about trailing winners with the 10MA after they've run), and the operator's own Tier-3 #6 framing per `docs/orchestrator-context.md`.

**Schema readiness:** Migration 0016 has `daily_management_records.maturity_stage` populated by the pipeline (per [`swing/data/repos/daily_management.py:86-91`](swing/data/repos/daily_management.py#L86-L91) and Phase 8 spec §6.6); the `trail_MA_eligibility_flag` is computed at pipeline time per spec §7.1. The schema is ready; the advisory layer simply does not consume `maturity_stage` to gate which MA rule fires.

**DHC-specific application:** DHC is open since 2026-04-27, approaching the +1.5R/+2R region per the brief. The operator needs decision guidance NOW about whether to upgrade DHC's trail-MA from 20MA to 10MA. Today the dashboard suggests both. The advisory layer's failure to gate gives the operator no help making the call.

### §3.B Gap B (URGENCY: HIGH; doctrine-confluent) — No trim/sell-into-strength advisory

**Symptom:** Triple confluence (M.2 + D.2 + Q.2 from §2.4) recommends taking partial profit on the way up — typically a 1/4 to 1/3 position reduction at the first significant gain (~10-25% / +1R-+2R). The framework emits zero trim advisories. The operator has no framework prompt to "consider trimming 25%"; the only sell signals are full-exit (`exit_below_*ma`) and stop-management.

**Risk to operator:** "When you're up $50K and end up making only $1,500 - you need to lock in more profits into strength" (Qullamaggie video 5, 2019-10-04; lesson cited via `query_trading_rules`). The framework's current architecture biases the operator toward all-or-nothing exits at MA violations — the operator gives back paper gains during pullbacks because no partial profit was banked.

**Operational severity:** HIGH. With operator capital ~$1,300 actual / $7,500 floor and ~50-trade-per-year ceiling per CLAUDE.md memory `project_capital_risk_floor.md`, every winner's give-back compounds. The lack of a trim advisory means the trader operates without the doctrine's standard risk-of-ruin defense.

### §3.C Gap C (URGENCY: MEDIUM-HIGH; doctrine-divergent) — Time-stop threshold mismatch

**Symptom:** Three doctrines name three different time-stop windows: Q.1 (3-5 day), D.5 (`[UNVERIFIED]` 7-10 day), M.4 (`[UNVERIFIED]` 7-week / 49-day). Framework defaults to 10-day with min-R 0.5. The operator may not be aware that this default is closer to one doctrine than to the others.

**Operational severity:** MEDIUM-HIGH. A 10-day window with min-R 0.5 is a moderately aggressive time-stop. Sub-A+ hypothesis-tagged trades (currently DHC + CC per orchestrator-context.md DB state notes) by design accept lower expectancy; a 10-day time-stop may exit prematurely on positions where the hypothesis test requires longer observation. Per-hypothesis time-stop discipline is not currently configurable.

### §3.D Gap D (URGENCY: MEDIUM) — Parabolic / extension detector

**Symptom:** Double-confluence M.5 + Q.5; framework has no detector for vertical price action or above-average gains in short windows. The operator must self-identify when a winner has gone parabolic and trim aggressively.

**Operational severity:** MEDIUM. Parabolic moves are rare events; missing the trim opportunity is costly when they occur but they don't occur every month. With current trade-volume floor (~5 concurrent positions, ~50/year ceiling per CLAUDE.md memory `project_capital_risk_floor.md`), one missed parabolic move per year is the realistic exposure.

### §3.E Gap E (URGENCY: MEDIUM) — Briefing emits empty advisory lists

**Symptom:** Per [`swing/pipeline/runner.py:921`](swing/pipeline/runner.py#L921), the briefing's `open_trade_advisories={}` is hard-coded empty. The operator who reads the pipeline-emitted briefing in `exports/<session>/briefing.md` or `.html` sees open positions but no advisories. The web dashboard is the only surface that emits them.

**Operational severity:** MEDIUM. The web dashboard is the operator's primary interface today; the briefing is a secondary artifact. But the briefing IS surfaced in the daily routine per `docs/cycle-checklist.md` — losing the advisory column there means a single-source-of-render risk if the dashboard is unavailable (browser issue, dev server down, etc.).

### §3.F Gap F (URGENCY: LOW-MEDIUM) — Trade detail page lacks advisory column

**Symptom:** [`swing/web/templates/trades/detail.html.j2`](swing/web/templates/trades/detail.html.j2) shows fills + events + chart but NOT the advisory column. The expanded-row HTMX partial explicitly notes "no advisories list" ([`swing/web/templates/partials/open_positions_expanded.html.j2:5`](swing/web/templates/partials/open_positions_expanded.html.j2#L5)) by design.

**Operational severity:** LOW-MEDIUM. Operator can see advisories on the dashboard list view; clicking "Detail" loses them. For the +1.5R operator-decision moment (DHC) the detail page is the natural deep-dive surface; not having the advisories there forces the operator back to the list view.

### §3.G Gap G (URGENCY: HIGH; structural) — Minervini + DST sell-side rules are not transcribed

**Symptom:** `reference/methodology/` contains only `minervini-trend-template.md` (BUY-side criteria). Minervini sell-side rules (M.2 sell-into-strength, M.4 7-week, M.5 parabolic, M.6 volume-confirmed close-below-MA, M.7 gap-down-on-news) and DST rules (D.1 swing-low initial stop, D.2 trim, D.3 EMA-vs-SMA, D.4 +2R tighten, D.5 7-10 day time-stop) are all `[UNVERIFIED]` from the implementer's perspective.

**Consequence:** Any recommendation in §4 that claims a Minervini or DST rule as its doctrinal basis is on weak footing until the operator confirms or corrects the claim from the physical copies. V2.1 §VII.F source-of-truth correction protocol (line 437-446 of the bifurcated proposal) anticipates this — corrections route as research-to-promotion cycles, NOT as hotfixes — so the work to close this gap is **transcription** (capture the doctrine in `reference/methodology/`) **before** any classification-altering change is commissioned.

**Operational severity:** HIGH. This gap shadows every other Minervini / DST claim in this document. The operator cannot operate the framework's sell-side discipline against doctrine if the doctrine itself is undocumented in the repo. Independent of any §4 recommendation accepted: surfacing this gap and asking the operator to commission transcription work (or to confirm it's intentionally physical-only) is operator-actionable today.

### §3.H Gap H (URGENCY: LOW; single-source-Q) — Sector-relative-strength check on open positions

**Symptom:** Q.8 (Qullamaggie) names "don't hold laggards" as a sell rule. Framework's evaluation pipeline computes RS at entry time but does not re-evaluate open positions for sector lag. No Minervini or DST analog in surveyed sources.

**Operational severity:** LOW. Single-source rule, no doctrinal confluence, novelty risk on implementation. Low priority but cited for completeness.

### §3.I Gap I (URGENCY: LOW) — Volume-confirmed close-below-MA overlay

**Symptom:** M.6 (`[UNVERIFIED]`) suggests volume confirmation makes a close-below-MA a stronger sell signal. Framework's `exit_below_*ma` rules check only the close. OHLCV bundle carries volume per pipeline data, so the overlay is cheap.

**Operational severity:** LOW. The current `exit_below_*ma` rule already fires on the close; adding volume confirmation would be a refinement that makes the "EXIT" message stronger when volume is heavy and weaker when volume is light, without changing the trigger condition itself. Defense-in-depth refinement; not a missing capability.

### §3.J Gap J (URGENCY: LOW) — Combined-violation rule (10MA + 20MA same day)

**Symptom:** Q.11 (Qullamaggie) — "When a stock closes below both the 10-day and 20-day moving averages, lighten the position significantly". Framework today fires `exit_below_10ma` AND `exit_below_20ma` as two independent advisories when both conditions hold; no combined rule with stronger messaging.

**Operational severity:** LOW. The operator sees both messages anyway; combining them into a single stronger advisory is presentation-only.

### §3.K Gap K (URGENCY: LOW) — Target-R hit advisory

**Symptom:** Schema has `trades.planned_target_R` (migration 0016 line 21-22; daily-management tile renders it but no advisory consumes it). Triple-confluence on sell-into-strength principle (M.2 + D.2 + Q.2 + Q.9); no source mandates a hard "exit-at-target" rule (because the doctrine is "trim into strength; let the rest ride," NOT "exit when target hit").

**Operational severity:** LOW. The conservative advisory is "current price ≥ planned_target_R — consider trim per sell-into-strength discipline" (advisory-message-only). It's adjacent to Gap B (trim/sell-into-strength) and is best implemented together with it.

---

## §4 Recommendations

For each gap in §3, a specific proposed advisory with: rule statement → trigger condition → emission surface → maturity-stage gating (per Tier-3 #6) → classification (advisory-message-only OR classification-altering per brief §0.5 #4) → estimated implementation effort → V2.1 §VII.F routing if classification-altering.

**Classification routing convention** (per brief §0.5 #4):
- **Advisory-message-only**: extends `swing/trades/advisory.py`; new rule emits a new advisory message; does NOT change classification, sizing, or initial-stop derivation. Routes through ordinary brief-then-dispatch path.
- **Classification-altering**: changes A+ vs sub-A+ logic, initial-stop derivation, maturity-stage thresholds, position-size formula, hypothesis tripwire enum, or similar. Routes through V2.1 §VII.F source-of-truth correction protocol — submitted as a new method-record version; enters research-branch validation; if validated, enters shadow alongside the current approximation; if shadow evidence supports, deprecates the current logic via standard demotion pathway.

### §4.A Recommendation A — Wire `maturity_stage` into trail-MA advisory gate (addresses §3.A)

**Proposed rule:** `suggest_trail_ma_gated` — emits the 20MA-trail suggestion for trades with `maturity_stage IN ('pre_+1.5R', '+1.5R_to_+2R')` and the 10MA-trail suggestion for `maturity_stage = '>=+2R_trail_eligible'`. Suppresses the OTHER MA's suggestion in each stage. Falls back to emitting both (current behavior) when `maturity_stage IS NULL` (e.g., on the very first pipeline run after entry before any snapshot exists).

**Trigger condition (precise):**
```
For each open trade T with active daily_management_records snapshot S:
  IF S.maturity_stage IN ('pre_+1.5R', '+1.5R_to_+2R'):
    emit suggest_trail_ma(20MA) IF triggered;
    SUPPRESS suggest_trail_ma(10MA).
  ELIF S.maturity_stage = '>=+2R_trail_eligible':
    emit suggest_trail_ma(10MA) IF triggered;
    SUPPRESS suggest_trail_ma(20MA).
  ELSE: # NULL or unknown stage
    emit BOTH (current behavior) — backward-compatible fallback.
```

**Emission surface:** Dashboard `/` open-positions row Advisory column (current rendering surface); naturally inherits to the open-positions expanded row + trade detail page if §4.F is also accepted.

**Maturity-stage gating:** The recommendation IS the gating. Operator framing per brief §0.4:
- **new (~0R)** → `pre_+1.5R` → 20MA trail (current default)
- **maturing** → `pre_+1.5R` → 20MA trail
- **mature (+1.5R-2R)** → `+1.5R_to_+2R` → 20MA trail (still)
- **well-mature (+2R+)** → `>=+2R_trail_eligible` → 10MA trail (upgrade)

**Classification:** **CLASSIFICATION-ALTERING.** This changes operational stop-management logic; specifically, it suppresses an advisory that fires today. The doctrine source for the gating (D.4 + Tier-3 #6 framing) is `[UNVERIFIED]` from a `reference/methodology/` perspective. Per V2.1 §VII.F, this should route via:
1. New method-record (or method-record version bump) capturing the gating rule as a candidate.
2. Research-branch validation: backtest the gating against the existing trail-MA-both-fire baseline on a labeled trade set (we have n=1 closed trade today; insufficient).
3. Shadow-mode in production: emit BOTH the current (un-gated) and the proposed (gated) advisories with a visual marker, log operator's actual stop adjustments, compare.
4. Promote/demote based on shadow evidence.

**Pragmatic alternative for operator consideration:** This is the kind of recommendation that operator-decision could classify as advisory-message-only IF the recommended advisory is reframed as a NEW visual decoration (e.g., a "stage-recommended" annotation on whichever MA the maturity stage prefers) WITHOUT suppressing the other one. That would be advisory-only (no classification change); operator keeps both suggestions visible but sees which one the maturity stage recommends. See §4.A.bis below.

**Estimated implementation effort:** 4-6 hours (advisory.py edit; VM wire-through; test set: per-maturity-stage golden tests; HTMX response-shape preserved).

**§4.A.bis (alternative framing of Recommendation A; advisory-message-only):** Keep both `suggest_trail_ma(10MA)` and `suggest_trail_ma(20MA)` firing as today. ADD a new annotation-style advisory `maturity_stage_recommendation` that emits: "Maturity stage `{stage}` → recommended trail-MA: `{20MA | 10MA}`". Operator sees both raw trail-MA suggestions plus the maturity-stage hint. This is **ADVISORY-MESSAGE-ONLY** — does not suppress anything, just adds a hint. Estimated effort: 2-3 hours. Operator-decision in §6 is between (a) Recommendation A as classification-altering, (b) Recommendation A.bis as advisory-message-only, or (c) defer until DHC settles past +2R and the issue becomes concrete.

### §4.B Recommendation B — Trim/sell-into-strength advisory (addresses §3.B)

**Proposed rule:** `suggest_trim_into_strength` — emits a trim suggestion when the trade is up by a configurable R-multiple AND has not yet been trimmed (i.e., `initial_shares - remaining_shares == 0` per existing exit-fill arithmetic).

**Trigger condition (precise):**
```
trim_first_r_trigger = cfg.stop_advisory.trim_first_r_trigger (NEW config, default 1.0R)
trim_first_pct_default = cfg.stop_advisory.trim_first_pct_default (NEW config, default 0.25)

For each open trade T:
  IF r_so_far(T, current_price) >= trim_first_r_trigger AND
     T.remaining_shares == T.initial_shares:  # no trim yet
    emit "Consider trimming {trim_first_pct_default * 100}% of position — up +{r_so_far:.2f}R; sell-into-strength discipline"
```

**Emission surface:** Dashboard open-positions row Advisory column. NO operator-confirmation gate; advisory is non-binding.

**Maturity-stage gating:** Triggers in `pre_+1.5R` once the R-trigger is met. Recommendation: fires AT `+1.0R` by default (configurable) so the operator sees it as the trade transitions from new → maturing. Past `>=+2R_trail_eligible`, the advisory still fires IF no trim has happened yet — covers the case of a fast mover that skipped the +1R window without trim. Continues to fire until trim is registered.

**Classification:** **ADVISORY-MESSAGE-ONLY.** Adds a new advisory rule; does not change classification, sizing, or stop-management logic. Operator chooses to act or ignore. New config keys land in `StopAdvisoryConfig` (per [`swing/config.py:90-96`](swing/config.py#L90-L96) pattern).

**Doctrine support:** Triple confluence M.2 + D.2 + Q.2 per §2.4. M+D are `[UNVERIFIED]` — operator confirms or corrects per §3.G. Q.2 is cited.

**V2.1 §VII.F routing:** N/A (advisory-message-only).

**Estimated implementation effort:** 3-4 hours (new rule + config + golden tests).

**Variant for operator consideration:** A two-step ladder — emit trim hint at +1R (default 25%) and a second at +2R (default another 25%) — adds complexity. Recommend V1 = single trim hint at +1R; V2 ladder if operator wants it.

### §4.C Recommendation C — Per-hypothesis time-stop configurability (addresses §3.C)

**Proposed rule:** Extend `suggest_time_stop` to consult a per-hypothesis override on `cfg.stop_advisory.time_stop_days` and `time_stop_min_r`. The default remains 10 days / 0.5R; sub-A+ hypothesis trades (per `trades.hypothesis_label` prefix-match against `hypothesis_registry`) may use a longer default.

**Trigger condition (precise):**
```
For each open trade T with hypothesis_label H:
  override = hypothesis_registry.time_stop_overrides.get(H, None)
  effective_days = override.days if override else cfg.stop_advisory.time_stop_days
  effective_min_r = override.min_r if override else cfg.stop_advisory.time_stop_min_r
  IF days_open(T) > effective_days AND r_so_far(T) < effective_min_r:
    emit "Time stop — {days_open} days open with only +{r_so_far:.2f}R; consider exit"
```

**Emission surface:** Dashboard advisory column (same as current `suggest_time_stop`).

**Maturity-stage gating:** Cross-cuts maturity stages — the rule fires per `days_open` + `r_so_far` regardless of maturity. The maturity gating from Recommendation A is independent.

**Classification:** **CLASSIFICATION-ALTERING.** Adds a per-hypothesis dimension to time-stop logic. The hypothesis registry has its own pre-registration discipline (per CLAUDE.md `## Strategy` and `## Conventions` — hypothesis tripwires are frozen at migration; only `status` is CLI-mutable). Adding time-stop overrides means extending the hypothesis-registry schema, which is V2.1 §VII.F-routed.

**Doctrine support:** Divergent doctrines (Q.1 3-5 day; M.4 `[UNVERIFIED]` 7-week; D.5 `[UNVERIFIED]` 7-10 day). Per-hypothesis override is the framework's way to support the operator's "hypothesis test requires longer observation" framing without re-litigating the global default.

**V2.1 §VII.F routing:** Required. Operator-decision in §6 includes whether to defer this entirely until more hypothesis-trade outcomes accumulate (today n=1 closed: VIR).

**Estimated implementation effort:** 6-10 hours including hypothesis-registry schema migration + research-branch validation harness.

**Pragmatic alternative for operator consideration:** Don't extend the hypothesis registry yet. Just raise the global default from 10/0.5 to a more permissive value (e.g., 21/0.3) for the duration of sub-A+ hypothesis evidence collection. This is **CLASSIFICATION-ALTERING** still (changes the default), but it's a config-default change, not a schema change. Estimated effort 1-2 hours. Operator-decision in §6 is between (a) Recommendation C as full per-hypothesis override, (b) Recommendation C.bis as global default change, or (c) defer.

### §4.D Recommendation D — Parabolic-extension detector (addresses §3.D)

**Proposed rule:** `suggest_parabolic_trim` — emits a trim suggestion when the trade has gained ≥ N% in ≤ M days AND the current price is ≥ K% above the 20MA. Quantitative thresholds are config-driven; doctrine-specific N/M/K values are `[UNVERIFIED]` per §3.G.

**Trigger condition (precise):**
```
parabolic_pct_window_days = cfg.stop_advisory.parabolic_pct_window_days (NEW, default 5)
parabolic_pct_threshold = cfg.stop_advisory.parabolic_pct_threshold (NEW, default 0.25, i.e., 25%)
parabolic_above_20ma_pct = cfg.stop_advisory.parabolic_above_20ma_pct (NEW, default 0.15, i.e., 15%)

For each open trade T:
  recent_pct_gain = (current_price - price_N_days_ago) / price_N_days_ago
  pct_above_20ma = (current_price - sma20) / sma20
  IF recent_pct_gain >= parabolic_pct_threshold AND
     pct_above_20ma >= parabolic_above_20ma_pct:
    emit "Parabolic extension — up {recent_pct_gain*100:.0f}% in {N} days; consider aggressive trim per sell-into-strength"
```

**Emission surface:** Dashboard advisory column.

**Maturity-stage gating:** Fires regardless of maturity stage — parabolic moves can happen at any stage; in practice they occur mostly in `>=+2R_trail_eligible` but a fast mover from new → well-mature in 3 days is exactly the case the rule needs to catch.

**Classification:** **ADVISORY-MESSAGE-ONLY.** Adds a new advisory; does not change classification or sizing. Implementation depends on having `price_N_days_ago` data; OHLCV bundle carries history but the advisory layer doesn't currently dereference it — implementation will need to extend `AdvisoryContext` to carry a recent-percentage-gain summary (cheap; same OHLCV fetch as today).

**Doctrine support:** Double-confluence M.5 (`[UNVERIFIED]`) + Q.5 (cited).

**V2.1 §VII.F routing:** N/A (advisory-message-only).

**Estimated implementation effort:** 5-7 hours including the recent-percentage-gain helper in `AdvisoryContext`.

**Caveat:** Thresholds are arbitrary V1 defaults; operator should expect to tune them as evidence accumulates. The doctrine sources (M.5, Q.5) describe the principle but not specific N/M/K — operator may want to flag these as TBD-on-evidence in the implementation dispatch brief.

### §4.E Recommendation E — Wire advisory rendering into pipeline-emitted briefing (addresses §3.E)

**Proposed change:** Change `swing/pipeline/runner.py:921` from `open_trade_advisories={}` to compute the advisories per-trade against the same `AdvisoryContext` the web dashboard uses. This makes the briefing's `briefing.md` and `briefing.html` advisory-bearing.

**Trigger condition:** N/A (this is a pipeline emission change, not a new rule). Per-pipeline-run, for each open trade, compute the advisory suggestions using OHLCV data already loaded for the chart step.

**Emission surface:** `exports/<session>/briefing.md` and `briefing.html` per-open-position rendering already has the `advisory: list` field in [`swing/rendering/briefing.py:51`](swing/rendering/briefing.py#L51) — it just receives an empty list today.

**Maturity-stage gating:** Inherits from whichever advisory rules are active (Recommendation A or A.bis if accepted; otherwise no gating).

**Classification:** **ADVISORY-MESSAGE-ONLY.** No new rules; just wires existing rules into a second emission surface.

**Doctrine support:** N/A (parity gap, not a doctrine claim).

**V2.1 §VII.F routing:** N/A.

**Estimated implementation effort:** 2-3 hours (compute advisories in runner; wire through; brief-content snapshot test).

### §4.F Recommendation F — Render advisories on trade detail + expanded row (addresses §3.F)

**Proposed change:** Add the advisory column rendering to [`swing/web/templates/trades/detail.html.j2`](swing/web/templates/trades/detail.html.j2) and remove the "no advisories list" exclusion from [`swing/web/templates/partials/open_positions_expanded.html.j2`](swing/web/templates/partials/open_positions_expanded.html.j2). VMs already carry the advisory data per [`swing/web/view_models/dashboard.py:967`](swing/web/view_models/dashboard.py#L967); the detail-page VM just needs to consume it.

**Emission surface:** `/trades/{id}` page + open-positions expanded HTMX partial.

**Maturity-stage gating:** Inherits from accepted advisory rules.

**Classification:** **ADVISORY-MESSAGE-ONLY.** Template-only change; no rule logic change.

**Doctrine support:** N/A (UI consistency).

**V2.1 §VII.F routing:** N/A.

**Estimated implementation effort:** 2-3 hours (template edit + golden test + visual verification per the CLAUDE.md `<tr>`-leading makeFragment gotcha — verify the detail page is not first-element-`<tr>`-leading; it is currently a full page render so not at risk, but the operator-witnessed browser gate should confirm).

### §4.H Recommendation H — Sector-relative-strength check on open positions (addresses §3.H)

**Proposed rule:** `suggest_sector_laggard_exit` — emits an exit suggestion when an open trade's sector relative strength (computed at evaluation time and persisted on a recurring schedule) drops below a configurable percentile threshold AND the open trade's R-multiple is below a configurable floor (avoid suggesting exit on profitable trades whose sector has merely cooled).

**Trigger condition (precise):**
```
sector_lag_rs_threshold = cfg.stop_advisory.sector_lag_rs_threshold (NEW, default 50 — IBD-percentile-style)
sector_lag_r_floor = cfg.stop_advisory.sector_lag_r_floor (NEW, default 0.5, i.e., trade must be under +0.5R)

For each open trade T:
  sector_rs = latest_sector_rs_for(T.sector)  # from existing eval pipeline RS calc
  IF sector_rs IS NOT NULL AND
     sector_rs < sector_lag_rs_threshold AND
     r_so_far(T) < sector_lag_r_floor:
    emit "Sector laggard — {T.sector} RS={sector_rs} below {threshold}; trade only +{r:.2f}R; consider exit per Q.8"
```

**Emission surface:** Dashboard open-positions row Advisory column.

**Maturity-stage gating:** Fires in **new** + **maturing** stages (R<+1.5R, by R-floor design). Does NOT fire in **mature** or **well-mature** because R_floor=0.5 caps it. Operator can tune the floor up to extend the gate.

**Classification:** **CLASSIFICATION-ALTERING.** Requires extending the evaluation pipeline to persist sector RS at a cadence the advisory layer can consume; the new `sector_rs` field is operationally consumed by an exit recommendation. Per V2.1 §VII.F: (1) new method-record version for sector-laggard exit logic, (2) research-branch validation (does sector RS predict exit-side return improvement?), (3) shadow mode, (4) promote/demote based on shadow evidence.

**Doctrine support:** Q.8 only (cited). No Minervini or DST confluence in surveyed rules. Single-source.

**V2.1 §VII.F routing:** Required.

**Estimated implementation effort:** 10-14 hours including pipeline-side RS persistence + research-branch validation harness + advisory wiring.

**Recommendation: DEFER.** Single-source-Q rule with no Minervini or DST confluence; novelty risk on implementation; current trade-volume floor (~5 concurrent positions, ~50/year ceiling) doesn't make this a high-value add against the implementation cost. Operator decision in §6 likely `defer` or `drop`. Note: a much cheaper V0 of this would be an advisory-message-only check against existing entry-time RS data without pipeline changes, but that doesn't address the "RS as the trade ages" aspect that Q.8 is actually about.

### §4.G Operator-action prerequisite — Transcribe Minervini SEPA + DST sell-side rules into `reference/methodology/` (addresses §3.G)

**Note on classification framework:** This item is intentionally surfaced OUTSIDE the §4.A-K recommendation set because the brief's locked taxonomy (advisory-message-only OR classification-altering) classifies code/advisory changes only. Transcribing doctrine into `reference/methodology/` is neither a code change nor a classification-altering operation — it is an **operator-action prerequisite** that makes the V2.1 §VII.F-routed code recommendations (§4.A, §4.C, §4.H if accepted) citable against source-of-truth doctrine instead of `[UNVERIFIED]` memory. It is captured here adjacent to §4 because of its dependency relationship, not as a code recommendation. Surfaced as an operator-decision item in §6.

**Proposed operator action:** Per V2.1 §VII.F, the operator commissions transcription of the relevant Minervini chapters (sell-side rules; SEPA winner-management discipline; 7-week rule; parabolic extension; violated MA on volume) and the DST take-profit + trail rules into `reference/methodology/`. Adds N new files following the format established by `minervini-trend-template.md`: source citation + transcription + usage notes ("This file is reference material only; do not edit production code to 'match' this table without routing the change through the research-branch promotion cycle per V2 Addendum Addition 2.").

**Trigger:** Operator-discretionary; no automated trigger applies.

**Emission surface:** New files in `reference/methodology/`.

**Maturity-stage gating:** N/A.

**Classification:** **Not a §4 recommendation per locked taxonomy** — operator-action prerequisite for §4.A, §4.C, §4.H V2.1 §VII.F routing.

**V2.1 §VII.F routing:** N/A directly. But this is a PREREQUISITE for V2.1 §VII.F-routed §4 recommendations A, C, H to have citable source-of-truth basis.

**Estimated effort:** Operator action ~30-90 min per source-chapter transcription; depends on Minervini source chapter length + DST coverage. The operator owns this; the implementer cannot substitute (no PDF/transcription available).

### §4.I Recommendation I — Volume-confirmed close-below-MA overlay (defers; addresses §3.I)

**Proposed rule:** Extend `suggest_exit_close_below_ma` to consult yesterday's volume relative to a 20-day average; emit a stronger-worded message ("EXIT — yesterday's close $X is below NMA ($Y) on **above-average** volume") when volume is heavy, weaker when light.

**Trigger condition:** Volume already in OHLCV bundle; trivial to compute relative volume.

**Classification:** **ADVISORY-MESSAGE-ONLY** (new advisory overlay; does NOT alter the existing `exit_below_*ma` trigger conditions — adds a volume-relative condition that strengthens or weakens the message wording).

**V2.1 §VII.F routing:** N/A.

**Estimated implementation effort:** 2-3 hours.

**Recommendation: DEFER unless §4.G transcription confirms M.6 with specific volume threshold.** Single-source-M rule (`[UNVERIFIED]`); modest operational value at current trade volume. Operator decision in §6 likely `defer`.

### §4.J Recommendation J — Combined-violation rule (defers; addresses §3.J)

**Proposed rule:** When `exit_below_10ma` AND `exit_below_20ma` both trigger same-render, emit a single stronger advisory ("EXIT — yesterday's close $X is below BOTH 10MA ($Y) and 20MA ($Z); high-confidence sell signal") replacing the two independent advisories.

**Classification:** **ADVISORY-MESSAGE-ONLY** (presentation; same data).

**V2.1 §VII.F routing:** N/A.

**Estimated implementation effort:** 1-2 hours.

**Recommendation: DEFER.** Low-value cosmetic refinement; operator already sees both messages.

### §4.K Recommendation K — Target-R hit advisory (addresses §3.K)

**Proposed rule:** `suggest_planned_target_r_hit` — emits a sell-into-strength reminder when current price's implied R-multiple ≥ `trades.planned_target_R`.

**Trigger condition (precise):**
```
For each open trade T with planned_target_R IS NOT NULL:
  IF r_so_far(T, current_price) >= T.planned_target_R:
    emit "Reached planned target +{T.planned_target_R}R — consider trim per sell-into-strength discipline"
```

**Emission surface:** Dashboard advisory column.

**Maturity-stage gating:** Inherits implicit gating by R-multiple. Fires when reached regardless of stage.

**Classification:** **ADVISORY-MESSAGE-ONLY.** Reads an existing column; emits a message; no logic change.

**Doctrine support:** Adjacent to Gap B (sell-into-strength); references Q.9 risk-reward target.

**V2.1 §VII.F routing:** N/A.

**Estimated implementation effort:** 2 hours.

**Recommendation: BUNDLE with §4.B (Recommendation B trim/sell-into-strength) as one dispatch.** They share the doctrinal basis and the implementation surface; landing them together avoids redundant advisory-rule plumbing.

---

## §5 Tier-3 #6 advisory state-machine integration

Synthesis of how the Recommendations §4.A-K should gate on Tier-3 #6 maturity stages. Per the brief §0.4 (operator framing): new (~0R) → maturing → mature (+1.5R-2R, default 20MA trail) → well-mature (+2R+, upgrade to 10MA trail). Per migration 0016 line 60-62 DB enum: `pre_+1.5R` / `+1.5R_to_+2R` / `>=+2R_trail_eligible`. The four-stage operator framing maps to the three-stage DB enum as: `pre_+1.5R` covers new + maturing; `+1.5R_to_+2R` is mature; `>=+2R_trail_eligible` is well-mature.

### §5.1 Per-stage advisory matrix

| Advisory rule | new (pre_+1.5R, R<+0.5) | maturing (pre_+1.5R, +0.5R≤R<+1.5R) | mature (+1.5R_to_+2R) | well-mature (>=+2R_trail_eligible) |
|---|---|---|---|---|
| **breakeven** (existing rule 1) | n/a (R<1) | FIRES at +1R | already moved | already moved |
| **trail_20MA** (existing rule 3; Recommendation A gates) | FIRES (default) | FIRES (default) | FIRES (default) | SUPPRESSED (Recommendation A) — or KEEPS firing if Recommendation A.bis chosen |
| **trail_10MA** (existing rule 2; Recommendation A gates) | SUPPRESSED (Recommendation A) — or fires today | SUPPRESSED (Recommendation A) — or fires today | SUPPRESSED (Recommendation A) — or fires today | FIRES (Recommendation A) — fires today either way |
| **exit_below_10MA** (existing rule 4) | FIRES | FIRES | FIRES | FIRES |
| **exit_below_20MA** (existing rule 5) | FIRES | FIRES | FIRES | FIRES |
| **exit_below_50MA** (existing rule 6) | FIRES | FIRES | FIRES | FIRES |
| **weather** (existing rule 7) | FIRES (cross-cutting) | FIRES (cross-cutting) | FIRES (cross-cutting) | FIRES (cross-cutting) |
| **time_stop** (existing rule 8; Recommendation C may adjust) | FIRES if days>10 + R<0.5 | FIRES if days>10 + R<0.5 | typically n/a (R≥1.5 ≫ 0.5) | typically n/a |
| **trim_into_strength** (Recommendation B; NEW) | n/a (R<+1) | FIRES at +1R if no prior trim | FIRES if no prior trim | FIRES if no prior trim |
| **planned_target_R_hit** (Recommendation K; NEW) | n/a | n/a (unless planned_target_R<1.5) | FIRES if R ≥ planned_target_R | FIRES if R ≥ planned_target_R |
| **parabolic_trim** (Recommendation D; NEW) | FIRES if recent_pct & above-20MA both trip | FIRES if recent_pct & above-20MA both trip | FIRES if recent_pct & above-20MA both trip | FIRES if recent_pct & above-20MA both trip |
| **volume_confirmed_exit** (Recommendation I; DEFER) | FIRES (when wired) | FIRES (when wired) | FIRES (when wired) | FIRES (when wired) |
| **combined_violation** (Recommendation J; DEFER) | FIRES on combo | FIRES on combo | FIRES on combo | FIRES on combo |
| **sector_relative_strength** (Recommendation H; DEFER; CLASSIFICATION-ALTERING) | FIRES if sector_rs<50 AND R<+0.5 (and `sector_rs` field is wired) | FIRES if sector_rs<50 AND R<+0.5 | n/a (R-floor caps to <+0.5 — well above this stage's R range) | n/a |
| **per_hypothesis_time_stop** (Recommendation C; CLASSIFICATION-ALTERING) | OVERRIDES time_stop | OVERRIDES time_stop | typically n/a | typically n/a |

### §5.2 State transitions — derivation correction

The DB enum stage values are computed by `compute_maturity_stage(open_MFE_R_to_date)` at [`swing/trades/daily_management.py:324-332`](swing/trades/daily_management.py#L324-L332), called from the pipeline `_step_daily_management` path at [`swing/trades/daily_management.py:567`](swing/trades/daily_management.py#L567). The advisory layer reads `daily_management_records.maturity_stage` from the active snapshot.

**Critical derivation note (Codex R1 correction):** `maturity_stage` is derived from `open_MFE_R_to_date` (the trade's maximum-favorable-excursion R-multiple recorded so far), **NOT** from current/live `open_R_effective`. The function thresholds per code lines 328-332:

```
if open_MFE_R_to_date is None:    return None
if open_MFE_R_to_date < 1.5:      return "pre_+1.5R"
if open_MFE_R_to_date < 2.0:      return "+1.5R_to_+2R"
return ">=+2R_trail_eligible"
```

**Monotonicity is automatic, not a design question.** Because `open_MFE_R_to_date` is by definition the running MAX of R-so-far over the trade's life (the "maximum favorable excursion to date"), it can only ever increase or stay flat — never decrease. Therefore `compute_maturity_stage` cannot "demote" a trade once promoted; if a trade hits +2R and then pulls back to +1R, MFE-to-date stays at +2R, and `maturity_stage` stays at `>=+2R_trail_eligible`. This satisfies the operator's "trade has to prove itself; once proven, it stays in the well-mature stage" framing as an automatic consequence of the MFE derivation — no separate monotonicity-preservation logic is needed.

**Practical implication for the advisory layer:** A trade can simultaneously have `maturity_stage = '>=+2R_trail_eligible'` (because its MFE peak hit ≥+2R) and `open_R_effective = +0.5R` (because price pulled back). The 10MA-trail-eligibility computed by `compute_trail_MA_eligibility_flag` at [`swing/trades/daily_management.py:335-352`](swing/trades/daily_management.py#L335-L352) is gated on `maturity_stage='>=+2R_trail_eligible' AND trail_MA_candidate_price IS NOT NULL AND current_stop < trail_MA_candidate_price` — i.e., it leverages the MFE-anchored maturity stage to allow upgrades to 10MA trail even after a pullback. This is doctrinally consistent with "once a trade has run +2R, it has earned the tighter trail" (per Tier-3 #6 framing).

### §5.3 DHC-specific application — three-field decision

DHC is open since 2026-04-27 with entry $7.58 per the orchestrator-context.md DB-state notes. The investigation does not have live DB access; the operator reads the live state from the daily-management dashboard tile per [`daily_management_tile.html.j2:75-90`](swing/web/templates/partials/daily_management_tile.html.j2#L75-L90), which surfaces THREE relevant cells:

1. **`open_R_effective`** — current/live R-multiple from `(current_price - current_avg_cost) * current_size / planned_risk_budget` per spec §7.1 line 547. This is what the operator's gain currently is.
2. **`open_MFE_R_to_date`** — the trade's peak R-multiple over its life. This is what drives the maturity stage.
3. **`maturity_stage`** — derived from (2) per §5.2; renders as the `maturity-badge` span.

Decision-guidance matrix for DHC, refined per §5.2 derivation correction:

- **Case A — `maturity_stage = 'pre_+1.5R'`** (MFE peak has never reached +1.5R): the trade has not yet proven itself. Keep 20MA trail; do NOT upgrade. If `open_R_effective` is also <+1R, Recommendation B (trim/sell-into-strength) has not fired yet. If `open_R_effective` is between +1R and +1.5R, the trim-at-+1R advisory (Recommendation B) would fire once active.
- **Case B — `maturity_stage = '+1.5R_to_+2R'`** (MFE peak hit +1.5R but never +2R): the trade is mature but not well-mature. Tier-3 #6 default stays at 20MA trail. The `open_R_effective` may be currently below +1.5R (because of pullback off MFE peak) — that's a doctrine signal in its own right (gave back gains; consider whether the trim opportunity at MFE peak was missed).
- **Case C — `maturity_stage = '>=+2R_trail_eligible'`** (MFE peak hit +2R): the trade is well-mature. Operator may now upgrade to 10MA trail per Tier-3 #6. `trail_MA_eligibility_flag` (per [`daily_management_tile.html.j2:82-86`](swing/web/templates/partials/daily_management_tile.html.j2#L82-L86)) renders TRAIL ELIGIBLE badge with the proposed price IFF current_stop < trail_MA_candidate_price. Even if `open_R_effective` has pulled back to +1R or lower, the 10MA upgrade is still doctrine-supported because MFE-to-date earned it.

**Operator's actual decision moment for DHC:** read THREE values from the dashboard tile, not just one:
1. `maturity_stage` (the maturity-badge span).
2. `open_R_effective` (the Open R cell).
3. `open_MFE_R_to_date` (the MFE R cell).

The maturity_stage cell alone is necessary but not sufficient. The operator's "where is DHC in its life" answer is the joint reading. The current advisory layer renders trail_10MA + trail_20MA based on `ctx.sma10` / `ctx.sma20` and `ctx.current_price` (per [`advisory.py:46-62`](swing/trades/advisory.py#L46-L62)) — without consulting `maturity_stage`. Recommendation A would close the consult; Recommendation A.bis would surface the stage's preferred MA as an advisory hint without suppressing the other.

**This is what the §1 operator-urgency framing reduces to in concrete terms:** the operator today must read three dashboard cells, map them through the Tier-3 #6 framing manually, and ignore one of the trail-MA advisories per the mapping. Recommendation A (or A.bis) closes the mental-mapping step.

### §5.4 (removed; previously covered "monotonic stage transitions" open question)

Per §5.2's derivation correction, monotonic-up stage transitions are an automatic consequence of `open_MFE_R_to_date` semantics — not an open design question. This section is intentionally retained as a placeholder to preserve the §5.x section numbering for §5.1/§5.2/§5.3 cross-references elsewhere in the doc. Previously flagged operator-decision row about monotonic transitions has been **REMOVED from §6** as a `[UNVERIFIED]` item.

---

## §6 Operator decision points

For each recommendation in §4, the operator's decision is `commission` (route to brainstorm/writing-plans dispatch), `defer` (bank for later), or `drop` (close the investigation thread on this gap). The implementer's suggested disposition is shown; operator decides.

### §6.1 Decision matrix

| Recommendation | Implementer suggested | Operator decision | One-line operator-decision framing |
|---|---|---|---|
| §4.A (trail-MA maturity gating; classification-altering) | **commission** (alternative §4.A.bis advisory-message-only) | ___ | Should the dashboard suppress the 10MA advisory pre-+2R, or just hint at the maturity-stage-preferred MA without suppression? |
| §4.A.bis (maturity hint; advisory-message-only) | **alternative to §4.A** | ___ | If §4.A feels too heavy for now, take §4.A.bis as the V1 step — operator-decision is between A and A.bis (or defer both). |
| §4.B (trim/sell-into-strength advisory; advisory-message-only) | **commission** | ___ | Should the dashboard prompt "consider trimming 25%" when a trade hits +1R for the first time? |
| §4.C (per-hypothesis time-stop; classification-altering) | **defer** (alternative §4.C.bis change global default; classification-altering) | ___ | Should the time-stop discipline differentiate by hypothesis tag, or just raise the global default for sub-A+ trades? Or leave at 10/0.5? |
| §4.D (parabolic-extension detector; advisory-message-only) | **commission** | ___ | Should the dashboard flag parabolic moves (+25% in 5 days + 15% above 20MA) as candidates for aggressive trim? |
| §4.E (briefing emits advisories; advisory-message-only) | **commission** | ___ | Should the pipeline briefing also carry the advisory column, or is the web dashboard a sufficient single source? |
| §4.F (advisory column on detail + expanded row; advisory-message-only) | **commission** | ___ | Should the trade detail page + open-positions expanded view also render advisories? |
| §4.G (transcribe Minervini SEPA + DST sell-side; operator-action prerequisite — NOT a §4 code recommendation per locked taxonomy) | **commission (operator-action)** | ___ | Should the operator commission transcription of Minervini SEPA + DST sell-side rules into `reference/methodology/` to close the §3.G `[UNVERIFIED]` gap before any §4.A, §4.C, or §4.H V2.1 §VII.F-routed work is dispatched? |
| §4.H (sector RS check on open positions; classification-altering) | **defer or drop** | ___ | Single-source-Q rule; defer until trade volume justifies more sophistication, or drop entirely? |
| §4.I (volume-confirmed exit overlay; advisory-message-only) | **defer** until §4.G confirms M.6 | ___ | Should the close-below-MA advisory escalate when volume is heavy, or defer until Minervini transcription confirms the rule? |
| §4.J (combined-violation rule; advisory-message-only) | **drop** (cosmetic; low value) | ___ | Should two independent advisories be merged into one stronger one? |
| §4.K (planned_target_R hit advisory; advisory-message-only) | **bundle with §4.B** | ___ | Should the dashboard flag when a trade reaches the operator-defined planned target R, OR bundle this into §4.B's trim/sell-into-strength dispatch? |

### §6.2 DHC-specific decision

The investigation produced operationally-applicable guidance for DHC: per §5.3, read the maturity-badge value on the daily-management dashboard tile and apply the trail-MA mapping (pre-+2R → 20MA; +2R+ → 10MA). The operator can use this guidance today without any §4 recommendation landing in code. The mental-mapping load is the operator's pain point; Recommendation A or A.bis would reduce it.

**Operator decision for DHC specifically:** review the current `maturity_stage` on the dashboard and apply the §5.3 mapping. If `maturity_stage='pre_+1.5R'`, the 10MA-trail advisory is a doctrine-divergent suggestion and should be ignored per Tier-3 #6 (20MA is correct). If `>=+2R_trail_eligible`, switch to 10MA-trail. The investigation cannot make this decision; only the operator can.

### §6.3 Sequencing suggestion (for operator's commission planning)

If the operator commissions multiple recommendations, suggested sequence:
1. **§4.G first** (transcribe Minervini + DST sell-side). Closes the `[UNVERIFIED]` doctrine gap. Operator action; no code. Unblocks §4.A and §4.C's V2.1 §VII.F routing.
2. **§4.E + §4.F** in a single small dispatch (advisory parity across surfaces). Trivial; high-confidence; both advisory-message-only.
3. **§4.B + §4.K** bundled (trim advisory + target-R hit). Single doctrine; single dispatch. Advisory-message-only.
4. **§4.A.bis** (maturity hint as advisory-message-only). Defer Recommendation A's classification-altering version pending evidence accumulation.
5. **§4.D** parabolic detector. Standalone advisory-message-only dispatch; quantitative thresholds operator-tunable.
6. **§4.C.bis** (global time-stop default change, if operator wants it).
7. **Defer:** §4.A full (classification-altering); §4.C full (classification-altering); §4.H, §4.I, §4.J.

The first four steps are advisory-message-only and skip V2.1 §VII.F; they're the lowest-friction adds.

### §6.4 Triage of `[UNVERIFIED]` flags

Below is the full list of `[UNVERIFIED — physical-copy-only claim; flag for operator]` flags surfaced for operator triage. The operator either (a) confirms the claim from the physical copy, (b) corrects the claim, or (c) flags as still-unverifiable. This list captures the operator-attention items for Surface 2 of §5 of the brief.

| # | Claim | Operator disposition |
|---|---|---|
| 1 | Minervini M.1: 1.25× backstop expectancy heuristic | ___ |
| 2 | Minervini M.2: sell into strength | ___ |
| 3 | Minervini M.3: sell on close below N-day MA (specific N values) | ___ |
| 4 | Minervini M.4: 7-week rule | ___ |
| 5 | Minervini M.5: parabolic / blow-off-top extension thresholds | ___ |
| 6 | Minervini M.6: violated MA on volume | ___ |
| 7 | Minervini M.7: gap-down on news | ___ |
| 8 | DST D.1: initial stop below swing low or breakout pivot's reaction low | ___ |
| 9 | DST D.2: take partial profit into strength (1/4 to 1/3) | ___ |
| 10 | DST D.3: 10-EMA fast movers vs 20-SMA steady names | ___ |
| 11 | DST D.4: tighten stop after +2R | ___ |
| 12 | DST D.5: 7-10 day vs 7-week time stop | ___ |
| 13 | Confluence/divergence map in §2.4 (rows 1-9) carries `[UNVERIFIED]` from the constituents | ___ |

---

## §7 Bibliography / source manifest

- `reference/methodology/minervini-trend-template.md` — Minervini Trend Template (BUY-side, 8 criteria), transcribed 2026-04-23 from *Trade Like a Stock Market Wizard*, McGraw Hill 2013, ch. 5, p. 79.
- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §VII.F (source-of-truth correction protocol; lines 437-446).
- `swing/trades/advisory.py` (commit `1b43efb` on `main`).
- `swing/config.py:90-96` (`StopAdvisoryConfig` defaults).
- `swing/data/migrations/0016_phase8_daily_management.sql` (action_taken + maturity_stage enums; commit ddfdfcb on `main`).
- `swing/data/repos/daily_management.py:86-91` (snapshot read with maturity_stage).
- `swing/web/view_models/dashboard.py:939-976` (advisory rule emission for dashboard).
- `swing/web/templates/partials/open_positions_row.html.j2:39-43` (Advisory column rendering).
- `swing/web/templates/partials/daily_management_tile.html.j2:75-89` (maturity badge + trail-MA eligibility rendering).
- `swing/web/templates/partials/open_positions_expanded.html.j2:5` (explicit "no advisories list" exclusion).
- `swing/web/templates/trades/detail.html.j2` (no advisory rendering — verified via grep).
- `swing/pipeline/runner.py:921` (briefing `open_trade_advisories={}` — verified via grep).
- `swing/rendering/briefing.py:51,134` (briefing VM carries advisory field but receives empty list from pipeline path).
- `docs/orchestrator-context.md` Tier-3 #6 (lines 127-128 reference; framing per brief §0.4).
- `docs/phase3e-todo.md` §3e.8 (investigation scope; lines 107-122).
- Qullamaggie MCP (`mcp__qullamaggie__query_trading_rules`, `mcp__qullamaggie__search_transcripts`) — 5 distinct queries executed during this investigation; video IDs cited inline per Q.1-Q.12 in §2.3.

---

## §8 Investigation provenance

- **Implementer:** Claude Code, Opus 4.7 (1M context).
- **Brief:** `docs/3e8-sell-side-advisories-investigation-brief.md` at commit `6012b05`.
- **Branch:** `3e8-sell-side-advisories-investigation` (worktree at `.worktrees/3e8-sell-side-advisories-investigation/`).
- **Baseline HEAD on `main`:** `fa0a0ac`.
- **Investigation duration:** single session.
- **Doctrine sources actually consulted:**
  - `reference/methodology/minervini-trend-template.md` (entire file).
  - `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §VII.F.
  - Qullamaggie MCP: `query_trading_rules(category='exit')` returned 478 rules (top ~50 reviewed; first 12 cited as Q.1-Q.12); `query_trading_rules(keyword='risk reward')` returned 10 rules (Q.9 cited from this set); 5 targeted `search_transcripts` queries on sell-into-strength + parabolic + 10-day MA + tighten-stop + sluggish-position topics; 1 targeted `query_trading_rules(category='risk_management')` via the risk-reward keyword search.
  - CLAUDE.md memory items consulted: `project_references.md` (DST is physical copy only); `reference_qullamaggie_mcp.md` (Qullamaggie is reference-only via MCP); `project_capital_risk_floor.md` (capital constraint context for urgency ranking).
- **Code files read end-to-end:** `swing/trades/advisory.py`, `swing/data/migrations/0016_phase8_daily_management.sql`, `swing/web/templates/partials/open_positions_row.html.j2`, `swing/web/templates/partials/daily_management_tile.html.j2`, the relevant slice of `swing/web/view_models/dashboard.py` (lines 920-980), the relevant slice of `swing/pipeline/runner.py` (lines 900-935), `swing/web/templates/partials/open_positions_expanded.html.j2`, the relevant slice of `swing/rendering/briefing.py` (lines 120-140).
- **Files surveyed by grep / Glob (not full-read):** `swing/data/repos/daily_management.py` (action_taken + maturity_stage refs); `swing/web/templates/trades/detail.html.j2` (verified absence of advisory rendering); `docs/orchestrator-context.md` (Tier-3 #6 + maturity refs).
- **`[UNVERIFIED]` flag count:** 14 distinct claims flagged for operator triage (§6.4 captures them).
- **Recommendation count:** 10 distinct §4 code/advisory recommendations (§4.A, §4.B, §4.C, §4.D, §4.E, §4.F, §4.H, §4.I, §4.J, §4.K) plus 1 operator-action prerequisite (§4.G; intentionally NOT counted under the brief's locked binary taxonomy). §4.A has an alternative formulation §4.A.bis. Classification breakdown of the 10 §4 code recommendations: advisory-message-only = 7 (§4.B, §4.D, §4.E, §4.F, §4.I, §4.J, §4.K); classification-altering = 3 (§4.A, §4.C, §4.H); §4.A.bis is the advisory-message-only alternative to §4.A. §4.G is an operator-action prerequisite (transcription) per locked-taxonomy carve-out documented in §4.G.
- **Operator decision-points surfaced:** 13 (§6.1 row count) + DHC-specific decision (§6.2) + sequencing suggestion (§6.3) + 14 `[UNVERIFIED]` triage rows (§6.4) = 13 / 1 / 1 / 14 = 29 distinct operator inputs requested across the doc.
