# Shadow-Expectancy Engine — Design Spec

**Date:** 2026-06-08
**Status:** Design — pending adversarial review + writing-plans
**Author role:** Research Director / CIO evaluator (see [`docs/research-director-context.md`](../../research-director-context.md))
**Phase:** copowers:brainstorming output

---

## 1. Purpose & context

The live trading record (16 trades, 12.5% win rate, −0.083R expectancy, ~−$73 realized) does **not** measure whether the production strategy has edge, for two reasons: (a) 12 of 16 trades were deliberate sub-A+ hypothesis tests (the pre-registered investigation plan v0.1, migration 0008), most of them **H3 "Sub-A+ VCP-not-formed"** whose success criterion is literally *confirm negative R*; and (b) the one hypothesis whose positive result would prove the strategy can make money — **H1 "A+ baseline produces positive expectancy", target 20 closed — sits at ~1 closed.** At the operator's A+ signal rate (~5 on a good night, often 0) H1 will not reach its decision criterion by hand-trading in any reasonable timeframe.

**The shadow-expectancy engine decouples "does the strategy have edge?" from "does the operator execute it?"** by mechanically forward-walking *every emitted signal* through a fixed ruleset to a realized R-multiple, accumulating per-hypothesis expectancy evidence at **signal-pace** (dozens/night via the #23-widened watch pool) instead of operator-trade-pace (~50/year). This is exactly the "shadow mode" the governing strategy already endorses (V2.1 §VII.C: ≥30 signals / ≥6 months before a production promotion).

It is a **research-evidence engine, not an operator-facing trading surface.** An operator-facing surface is a later promotion, out of scope.

---

## 2. Locked decisions (from brainstorming, 2026-06-08)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Data substrate | **Build on the v22 temporal log (read-only consumer)** — implement the "replay engine" the v22 schema reserves, consuming the immutable, already-frozen `ohlc_today_json` bars; forward-only accumulation. No schema change in V1 (see D8). Reproducible by construction; no mutable-archive drift (kills gotchas #26/#37). |
| D2 | Fill realism | **Deterministic gap-aware fills**, no randomness. Also emit the level-perfect number as a free optimistic upper bound → every result is a `[realistic, optimistic]` bracket. |
| D3 | Ruleset scope | **Core + Day-3–5 partial** (multi-leg). One mechanical ruleset held constant across all signals; hypotheses vary the *signal*, not the ruleset (NOT a ruleset sweep — that sank the W-arc). |
| D4 | Partial trigger (ruling a) | Sell 50% at the **close of session 3** after entry, **gated on `close > entry`** (in-profit only); session-N configurable. The one methodology-anchored parameter; ratification against source text routes through V2.1 §VII.F if desired. |
| D5 | Horizon (ruling b) | Follow to natural exit or **126 sessions (~6 months)**, whichever first; mark-to-market + flag anything still open. Effective horizon is bounded by bars that actually exist in the log; report the effective value. |
| D6 | Initial-stop basis | **Entry-bar low-of-day** (DST D.1), configurable. |
| D7 | MA-trail data source | Computed from **frozen forward bars only**; trail activates once the window fills. Zero pre-detection archive reads → fully reproducible from the immutable log. |
| D8 | Persistence | **No new production schema.** Emit a per-run report artifact (mirrors `minervini-recall`). Reserved temporal-log terminal-state writeback deferred. |

---

## 3. Placement & architecture

Follows the `minervini-recall` precedent exactly:

- **Logic:** thin Approach-A modules under **`research/harness/shadow_expectancy/`**, reusing production *pure-leaf* functions only.
- **Entry point:** one new CLI subcommand **`swing diagnose shadow-expectancy`** (the only `swing/` change → L2 LOCK stays light).
- **Posture:** a **pure read-only consumer** of the frozen temporal log + a per-run artifact writer. No new production write-path; no migration.

**Reuse matrix:**

| Capability | Source | Reuse / build |
|---|---|---|
| Frozen forward bars + entry-trigger state | `pattern_forward_observations` / `pattern_detection_events` | reuse (read-only) |
| Signal enumeration + bucket | `candidates` table / `fetch_candidates_for_run` | reuse (read-only) |
| Hypothesis attribution | `swing/recommendations/hypothesis.py::match_candidate_to_hypotheses` | reuse (pure, post-hoc) |
| Breakeven / MA-trail / close-below-MA predicates | `swing/trades/advisory.py` | reuse as decision predicates |
| R-multiple / realized-pnl / shares-remaining math | `swing/trades/derived_metrics.py`, `equity.py` | reuse (pure, on simulated fills) |
| Per-hypothesis scorecard metrics | `swing/metrics/` (9-metric framework + Wilson CI) | reuse |
| **Management-rule simulator (multi-leg state machine)** | — | **BUILD (the only substantial new code)** |
| **Day-3–5 partial rule** | — | **BUILD (not codified anywhere)** |
| **Detection→candidate joiner + hypothesis attribution glue** | — | **BUILD (thin)** |
| **Deterministic gap-aware fill model + bracket** | — | **BUILD (thin)** |

---

## 4. Data flow

```
pattern_detection_events  (frozen signal: ticker, detection_date, structural anchors, pivot/stop context)
        │  join by (ticker, detection_date)
        ▼
candidates row            (bucket = aplus|watch, pivot, initial_stop, criteria, adr_pct, …)
        │  match_candidate_to_hypotheses(candidate, registry)
        ▼
hypothesis attribution    (H1 ⇐ bucket==aplus; H2/H3/H4 ⇐ watch + specific criterion-miss sets)
        │
        │  replay pattern_forward_observations (immutable ohlc_today_json, one bar/session)
        ▼
MANAGEMENT-RULE SIMULATOR  (§5)  → multi-leg fills → realized R (deterministic-gap & level-perfect)
        │
        ▼
per-hypothesis aggregation → scorecard (expectancy_R, win rate + Wilson CI, profit factor,
                                        avg win/loss R, open-at-horizon count) → report artifact
```

Every input is frozen → re-running yields identical numbers (the reproducibility guarantee).

---

## 5. The management-rule simulator (the substantial build)

A deterministic, bar-by-bar state machine over a detection's frozen forward observations. State per shadow-trade: `shares_remaining`, `current_stop`, `legs[]` (each leg = action/qty/price), `entry_price`, `entry_session_index`, indicator window (frozen forward closes).

**5.0 Per-bar evaluation order (no look-ahead).** For each forward session after entry: (1) **stop test first** — if `bar.low ≤ current_stop` (the stop as it stood at the *prior* session's close), exit per §5.6 and terminate; (2) else apply **end-of-day signals** using `bar.close` — Day-3–5 partial (§5.3), breakeven raise (§5.4), MA-trail close-below (§5.5) — which update `current_stop` / `shares_remaining` for the *next* session. This prevents using a same-session close to both raise the stop and test it.

**5.1 Entry.** Use the temporal log's existing `triggered_open` event (`high ≥ pivot AND close ≥ structural_low`) as the entry session. Entry fill (deterministic-gap) = `max(pivot, entry_bar.open)` — a gap-up through the pivot pays the open, not the unreachable pivot. Level-perfect fill = `pivot`. Open the entry leg at a nominal `initial_shares` unit (e.g. 100 units; sizing is notional because expectancy is reported in R, which is size-invariant); all later leg quantities are fractions of this unit.

**5.2 Initial stop (D6).** `current_stop = entry_bar.low` (low-of-day of the entry candle). Risk-per-share = `entry_fill − initial_stop`; this is the R denominator (per `derived_metrics`).

**5.3 Day-3–5 partial (D3/D4).** At the close of session `N=3` after entry, if `bar.close > entry_fill` (in profit), sell 50% of `initial_shares` as a leg at `bar.close`. Gap-aware is moot (it's a close). Unconditional-if-in-profit; no R gate (calendar-based per doctrine). If not in profit at session N, no partial fires (managed by stop/trail). `N` and the in-profit gate are configurable.

**5.4 Breakeven move.** Reuse `suggest_breakeven` semantics: once `r_so_far ≥ breakeven_r_trigger` (default +1R, configurable) and `current_stop < entry_fill`, raise `current_stop = entry_fill`.

**5.5 MA trailing stop (D7).** Reuse `suggest_trail_ma` / `suggest_exit_close_below_ma` semantics, MA period configurable (default 20-day). The SMA is computed from **frozen forward closes only**; the trail **activates once the trailing window is available** (≥ MA-period frozen forward bars) AND the maturity gate is satisfied (reusing the existing `+1.5R_to_+2R` / `>=+2R_trail_eligible` staging). Before activation, the trade is managed by §5.2 + §5.4 + §5.3. When active, a session whose `close < SMA(period)` triggers a close-below-MA exit, executed per §5.6. *Consequence (documented):* long-period trails (50-day) activate later than in live trading where pre-history exists; freezing SMAs at detection is the V2 hardening.

**5.6 Exits & gap-aware downside.** Two exit mechanisms, both deterministic:
- **Price-level stops** (initial stop §5.2, breakeven stop §5.4) — an intrabar order. Triggered in §5.0 step (1) when `bar.low ≤ current_stop`; fills (deterministic-gap) at `min(current_stop, bar.open)` — a gap-down through the stop realizes the true >1R loss, not a fictitious −1R; level-perfect fills at `current_stop`.
- **Close-below-MA trail** (§5.5) — an end-of-day signal, not a price order. When an *active* trail's session closes below `SMA(period)`, the exit executes at the **next session's open**; deterministic-gap and level-perfect coincide (both = next open).

Either way the exit closes the remaining leg and the shadow-trade is terminal (`triggered_closed_at_stop`).

**5.7 Horizon / censoring (D5).** If no exit by `min(126, bars_available)` sessions post-entry, the trade is **open-at-horizon**: mark-to-market the remaining shares at the last frozen close, record realized-so-far R for closed legs + unrealized R for the open remainder, and **flag it in a separate bucket** (mirrors `open_at_tail_count`; honors #27 no-silent-caps). Open-at-horizon trades are reported but excluded from the "closed-only" expectancy headline; the report shows both closed-only and including-MTM figures.

**5.8 Multi-leg R.** Realized R = Σ over legs of `(leg.exit_price − entry_fill) × leg.qty / (risk_per_share × initial_shares)`, computed via the pure `derived_metrics` functions. Computed twice per trade (deterministic-gap = headline; level-perfect = optimistic), yielding the `[realistic, optimistic]` bracket. Invariant: `optimistic_R ≥ realistic_R` always (asserted in tests).

---

## 6. Hypothesis attribution

- Each detection is joined to its contemporaneous `candidates` row by `(ticker, detection_date)`; the existing matcher tags the hypothesis (H1 ⇐ `bucket=='aplus'`; H2/H3/H4 ⇐ watch + the frozen criterion-miss sets).
- **Registry:** V1 uses the **current active registry** (the 4 frozen v0.1 hypotheses, stable since 2026-04-25; the temporal log only carries data from after that date, so point-in-time = current here). True point-in-time registry replay is a V2 concern, documented.
- **A+ isolation:** the #23 pool-widening put the watch population in the log; A+ remains distinguishable via the candidate `bucket` field (the matcher's H1 keys on it). A detection with no matching candidate row is **skipped with an audit entry** (#27), never silently dropped.

---

## 7. Output

A per-run artifact directory (e.g. `research/studies/shadow-expectancy-runs/<run-id>/`) containing:

1. **Per-hypothesis scorecard** (reusing the 9-metric framework): n closed / n open-at-horizon, expectancy_R `[realistic, optimistic]`, win rate + Wilson CI, profit factor, avg win/loss R, payoff ratio, median holding sessions. Suppressed below sample floors per the existing honesty layer.
2. **Per-trade ledger:** ticker, detection_date, hypothesis, bucket, every leg (action/qty/price/session), realized R bracket, exit reason, open-at-horizon flag.
3. **Run manifest:** effective horizon, parameter values (N, breakeven_r, MA period, etc.), detection count, skipped-no-candidate count, temporal-log date span.

Headline for the operator: **H1's closed-trade count and expectancy bracket** — the number that tells us whether to keep investing in the A+ strategy.

---

## 8. Reproducibility guarantees

- Trade-path bars are read from the immutable frozen `ohlc_today_json` → no mutable-archive drift.
- No randomness (deterministic fills).
- SMAs from frozen forward bars only → no pre-detection archive read.
- Same temporal-log state + same parameters → byte-identical scorecard. A reproducibility test asserts this.

---

## 9. Testing strategy

- **Golden hand-computed walks** (each R hand-verified under both fill models): (a) gap-up entry; (b) gap-down stop blowing through 1R (realistic < −1R, optimistic = −1R); (c) partial-at-session-3-then-trail winner (multi-leg R); (d) horizon-censored runner (open-at-horizon MTM); (e) not-in-profit-at-N (no partial fires).
- **Bracket invariant:** `optimistic_R ≥ realistic_R` for every trade.
- **Reproducibility:** identical inputs → identical output.
- **Attribution:** A+ candidate → H1; watch+proximity_20ma-only → H2; etc. (mirror the matcher's own tests).
- **No-candidate skip emits an audit entry** (#27).
- Fast suite stays green (baseline ~7268+).

---

## 10. Scope / YAGNI — explicitly OUT

- Climax-top / ADR-extension trim (rarely fires, hardest to model; V2).
- Stochastic slippage (non-reproducible; conflicts with D1).
- Ruleset sweep / matrix (repeats the W-arc mistake).
- Operator-facing dashboard surface (later promotion).
- Backfill over the mutable OHLCV archive (re-inherits #26/#37).
- New production schema / temporal-log terminal-state writeback (deferred; V1 is read + artifact only).
- Freezing SMAs at detection (V2 hardening that would let long-MA trails activate immediately).

---

## 11. Risks & limitations (state them honestly in the report)

1. **Right-censoring understates expectancy** — winners run longest and are likeliest to hit the horizon; the closed-only headline is a *lower* bound on true expectancy. Mitigated by the MTM bucket + dual reporting, not eliminated.
2. **Effective horizon is bounded by the temporal log's current post-trigger depth** — if that depth < 126 sessions today, V1 is bounded by it; extending the observe-step horizon is a separate small follow-on.
3. **Paper ≠ real** — no operator psychology, no real slippage beyond the gap model, signal-set survivorship. A better edge estimate than 16 contaminated trades, not ground truth.
4. **MA-trail activation lag** (D7 consequence) makes V1 a slightly more *stop/breakeven/partial*-driven strategy early than live; documented, V2-hardenable.
5. **Sample maturity** — H1 still accrues only as A+ signals fire forward; the engine accelerates relative to hand-trading but does not manufacture history. Expect weeks-to-months to a decision-grade H1 n, not days.

---

## 12. Success criteria

- `swing diagnose shadow-expectancy` emits the §7 artifact over the live temporal log.
- All §9 tests pass; fast suite green on the merged head.
- The H1 bucket shows **shadow-closed trades ≫ the 1 live closed**, with an expectancy bracket and Wilson CI — i.e. the engine measurably accelerates the H1 evidence the project has been starved of.
- Zero production write-path changes; L2 LOCK preserved (one CLI subcommand only).
