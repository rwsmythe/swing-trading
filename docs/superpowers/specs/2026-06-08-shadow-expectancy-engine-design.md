# Shadow-Expectancy Engine — Design Spec

**Date:** 2026-06-08
**Status:** Design — Codex-reviewed (rounds 1-5 resolutions folded in); pending convergence + writing-plans
**Author role:** Research Director / CIO evaluator (see [`docs/research-director-context.md`](../../research-director-context.md))
**Phase:** copowers:brainstorming output

---

## 1. Purpose & context

The live trading record (16 trades, 12.5% win rate, −0.083R expectancy, ~−$73 realized) does **not** measure whether the production strategy has edge, for two reasons: (a) 12 of 16 trades were deliberate sub-A+ hypothesis tests (the pre-registered investigation plan v0.1, migration 0008), most of them **H3 "Sub-A+ VCP-not-formed"** whose success criterion is literally *confirm negative R*; and (b) the one hypothesis whose positive result would prove the strategy can make money — **H1 "A+ baseline produces positive expectancy", target 20 closed — sits at ~1 closed.** At the operator's A+ signal rate (~5 on a good night, often 0) H1 will not reach its decision criterion by hand-trading in any reasonable timeframe.

**The shadow-expectancy engine decouples "does the strategy have edge?" from "does the operator execute it?"** by mechanically forward-walking *every emitted signal* through a fixed ruleset to a realized R-multiple, accumulating per-hypothesis expectancy evidence at **signal-pace** instead of operator-trade-pace. This is exactly the "shadow mode" the governing strategy already endorses (V2.1 §VII.C: ≥30 signals / ≥6 months before a production promotion).

It is a **research-evidence engine, not an operator-facing trading surface.** An operator-facing surface is a later promotion, out of scope. The shadow scorecard is **never co-mingled** with the live hand-traded hypothesis counts (`compute_hypothesis_progress`); it is reported separately and explicitly labeled "mechanical-ruleset shadow evidence."

---

## 2. Locked decisions (brainstorming + round-1/2 Codex review, 2026-06-08)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Data substrate | **Build on the v22 temporal log (read-only consumer)** — implement the "replay engine" the v22 schema reserves, consuming the immutable, already-frozen `ohlc_today_json` bars; forward-only. No schema change in V1 (D8). Reproducible by construction; no mutable-archive drift (kills #26/#37). |
| D2 | Fill realism + the bracket | **A single, realizable entry fill is used for both bracket arms** (`entry_fill = max(pivot, entry_bar.open)` — you cannot fill below the bar's traded range, so "enter at pivot" on a gap-up is a fantasy and is NOT used). The R **denominator is therefore identical** across arms; the bracket varies **only the EXIT fills**: the **realistic** arm fills price-stops at `min(stop, bar.open)` (gap-through) and MA exits at next-open; the **favorable-reprice** arm fills price-stops at the stop level and MA exits at `max(signal_close, next_open)`. `favorable_R ≥ realistic_R` by construction (same denominator, weakly-better numerator). The **realistic arm is the execution-transfer estimate; the favorable-reprice arm is a non-executable upper-bound reference** (labeled `favorable_reprice`, kept out of any realism-transfer claim). |
| D3 | Ruleset scope | **Core + Day-3–5 partial** (multi-leg). One mechanical ruleset held constant across all signals; hypotheses vary the *signal*, not the ruleset (NOT a sweep — that sank the W-arc). |
| D4 | Partial trigger | Sell 50% at the **close of session 3** after entry, **gated on `close > entry_fill`** (in-profit only); session-N configurable. The one methodology-anchored parameter; ratification routes through V2.1 §VII.F if desired. |
| D5 | Horizon | Follow to natural exit or **126 sessions (~6 months)**, whichever first. Effective horizon is bounded by bars that actually exist in the log; report the effective value. |
| D6 | Initial-stop basis | **Entry-bar low-of-day** (DST D.1), configurable. Trades with a **non-positive risk denominator** (`entry_fill ≤ initial_stop`) are **excluded with a `degenerate_risk` funnel reason** (§7) — no valid R denominator exists. |
| D7 | MA-trail data source | Computed from **frozen forward bars only**; trail activates once the window fills. Zero pre-detection archive reads → fully reproducible from the immutable log. |
| D8 | Persistence | **No new production schema.** Emit a per-run report artifact (mirrors `minervini-recall`). Reserved temporal-log terminal-state writeback deferred. |
| D9 | Entry-bar ordering | The entry bar's own low does **not** trigger a same-session stop (breakout-from-base assumption); the stop is live from the *next* session. The **ambiguous subset** is precisely the trades where `entry_bar.low < entry_fill` (the bar traded below the fill intraday, so an adverse low-after-trigger ordering is possible). For that subset only, a **same-bar-adverse sensitivity** treats the trade as an immediate −1R stop on the entry session; the report shows the headline under both the base assumption and the all-ambiguous-adverse assumption, with the ambiguous count (§5.1.1). |
| D10 | Censoring reporting | **No "lower bound" claim.** Report four survival-aware scenarios per hypothesis: (1) closed-only, (2) MTM-at-horizon, (3) forced-exit-at-horizon-open, (4) **`stop-level-adverse`** (every open assumed to fill exactly at its current stop — explicitly **excludes** future overnight gap-through-stop risk, so it is not an absolute worst case). |
| D11 | Unit of analysis | **Headline = triggered-trade expectancy** (conditional on entry firing). Also report the **trigger rate** and a **per-signal expectancy** (non-triggered signals counted as no-trade / 0R). Both are emitted; never conflated. |
| D12 | MA-trail scope | V1 = a **maturity-staged 10/20-MA proxy** of the doctrinal 10/20/50 selection (20-day pre-maturity, 10-day once ≥+2R). The 50-day "slower institutional" character arm is **deferred to V2**; the V1 number is labeled a proxy. |

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
| Per-run frozen signal + bucket + criteria | `candidates` table / `fetch_candidates_for_run` | reuse (read-only) |
| Hypothesis attribution | `swing/recommendations/hypothesis.py::match_candidate_to_hypotheses` | reuse (pure, post-hoc) |
| Breakeven / MA-trail / close-below-MA / maturity-stage hint predicates | `swing/trades/advisory.py` | reuse as decision predicates |
| R-multiple / realized-pnl / shares-remaining math | `swing/trades/derived_metrics.py`, `equity.py` | reuse (pure, on simulated fills) |
| Per-hypothesis scorecard metrics + Wilson/honesty suppression | `swing/metrics/` | reuse |
| **Management-rule simulator (multi-leg state machine)** | — | **BUILD (the substantial new code)** |
| **Day-3–5 partial rule** | — | **BUILD (not codified anywhere)** |
| **Detection→per-run-candidate joiner + attribution glue** | — | **BUILD (thin)** |
| **Deterministic gap-aware exit-fill model + favorable repricing** | — | **BUILD (thin)** |

---

## 4. Data flow

```
pattern_detection_events  (frozen: ticker, detection_date, pipeline_run_id, structural anchors)
        │  one shadow-trade per UNIQUE (pipeline_run_id, ticker) candidate signal
        │  (multiple pattern-class detections for the same ticker/run collapse to one;
        │   §6 asserts candidate uniqueness per (run, ticker))
        ▼
candidates row (per-run frozen)   (bucket, pivot, initial_stop, per-criterion results, adr_pct, …)
        │  match_candidate_to_hypotheses(candidate, registry)
        ▼
hypothesis attribution    (H1 ⇐ bucket==aplus; H2/H3/H4 ⇐ watch + frozen criterion-miss sets)
        │
        │  replay pattern_forward_observations (immutable ohlc_today_json, one bar/session)
        ▼
MANAGEMENT-RULE SIMULATOR  (§5)  → multi-leg fills → realized R (realistic + favorable-reprice exits)
        │
        ▼
denominator funnel + per-hypothesis aggregation → scorecard (§7) → report artifact
```

Every input is frozen → re-running yields identical canonicalized metrics (§8).

---

## 5. The management-rule simulator (the substantial build)

A deterministic, bar-by-bar state machine over a detection's frozen forward observations. State per shadow-trade: `shares_remaining` (fractional, exact — no integer rounding), `current_stop`, `legs[]` (each = action/qty/price/session), `entry_fill`, `entry_session_index`, indicator window (frozen forward closes).

**5.0 Per-bar evaluation order (no look-ahead; total precedence for simultaneous conditions).** For each forward session after the entry session, in this exact order:
1. **Price-level stop test (intrabar)** — using `current_stop` *as it stood at the prior session's close*: if `bar.low ≤ current_stop`, exit per §5.6 and terminate. (The entry bar itself does not self-test; see §5.1.1.)
2. If not stopped, evaluate **end-of-day signals on `bar.close`** in this fixed order:
   a. **MA-trail close-below** (§5.5): if an active trail's `close < SMA(period)`, schedule a full exit at next-session open (§5.6) and **terminate further EOD processing**;
   b. else **Day-N partial** (§5.3): if `session_index == N` and in profit, take the 50% leg at `close`;
   c. then **breakeven raise** (§5.4): update `current_stop` for the *next* session.
A golden test exercises a bar where stop-eligibility, partial-eligibility, and an MA-close all occur.

**5.0.1 Input validation (pre-simulation, Codex R3-M3 + R4-M3/m2).** Before simulating a signal, validate: the candidate (`pivot` and `initial_stop` finite, **`pivot > 0`**, **`initial_stop ≥ 0`**, `pivot > initial_stop`); every frozen bar on the trade path (all OHLC finite and non-negative; `low ≤ min(open, close)`; `high ≥ max(open, close)`; `high ≥ low`); and the forward series itself (**strictly chronological, no duplicate sessions**). Any signal failing validation is **excluded under funnel reason `invalid_ohlc`** — frozen JSON can still hold a historically-frozen bad bar even though production now raises `SchwabBarConsistencyError` at fetch. No R math runs on invalid inputs.

**5.1 Entry.** Entry timing comes from the **frozen `triggered_open` event of the canonical detection** for the (run, ticker) (§6) — NOT recomputed. The observe step marks `triggered_open` only on forward sessions **strictly after `detection_date`**, so the detection-day bar can never retroactively trigger an entry (no look-ahead, by construction — Codex R4-M2). Entry session = that detection's first `triggered_open` forward observation; the entry-bar OHLC comes from its frozen `ohlc_today_json`. A **single realizable entry fill** is used for both bracket arms: `entry_fill = max(detection.pivot, entry_bar.open)`. (Entering at `pivot` on a gap-up is unrealizable, so it is not modeled — see D2.) Open the entry leg at a nominal `initial_shares` unit (e.g. 100.0 fractional units); all later leg quantities are exact fractions.

**5.1.1 Entry-bar ordering policy (D9).** OHLC cannot disambiguate whether the entry bar's intraday low (which becomes the initial stop, §5.2) occurred before or after the breakout. V1 base policy: the stop is **live from the session after entry** (the consolidation low is assumed to precede the breakout trigger). The **ambiguous subset** is exactly the trades where `entry_bar.low < entry_fill` — the bar traded below the fill that session, so an adverse "low after trigger" ordering is physically possible and would have stopped the trade out for a −1R on day 0. For that subset, a **same-bar-adverse sensitivity** recomputes the headline treating those trades as an immediate −1R. Trades with `entry_bar.low ≥ entry_fill` carry no entry-session stop risk and are never flagged. The report shows the headline under (i) the base assumption and (ii) all-ambiguous-adverse, plus the ambiguous count; if they materially diverge, it says so.

**5.2 Initial stop (D6).** `current_stop = initial_stop = entry_bar.low`. Risk-per-share = `entry_fill − initial_stop`, **identical across both bracket arms** (single entry fill). If the **risk denominator is non-positive** (`entry_fill ≤ initial_stop`), the trade is **excluded with funnel reason `degenerate_risk`** (§7) — no valid R denominator exists.

**5.3 Day-3–5 partial (D3/D4).** At the close of session `N=3` after entry, if `bar.close > entry_fill` (in profit), sell 50% of `initial_shares` as a leg at `bar.close`. Calendar-based; no R gate. If not in profit at session N, no partial fires. Because entry is fixed across arms (D2), the partial-firing decision is identical in both arms. `N` and the in-profit gate are configurable.

**5.4 Breakeven move.** Reuse `suggest_breakeven`: once `r_so_far ≥ breakeven_r_trigger` (default +1R, configurable) and `current_stop < entry_fill`, raise `current_stop = entry_fill`. Computed on the single (realistic) decision path.

**5.5 MA trailing stop (D7/D12).** Reuse `suggest_trail_ma` / `suggest_exit_close_below_ma` / the maturity-stage hint, **maturity-staged 10/20-MA** (default 20-day; 10-day once ≥+2R). SMA computed from **frozen forward closes only**; the trail **activates once ≥ MA-period frozen forward bars exist** AND the maturity gate is satisfied. Before activation, the trade is managed by §5.2 + §5.4 + §5.3. The doctrinal **50-day arm is deferred to V2**; the V1 number is labeled a maturity-staged-10/20 proxy.

**5.6 Exits, gap-aware fills, and exit reasons.** All management *decisions* are computed once on the realistic path; the two arms differ **only in exit fill price**. Terminal `exit_reason` ∈ `initial_stop` / `breakeven_stop` / `ma_close_below` / `horizon_mtm` / `never_triggered` / `degenerate_risk`:
- **Price-level stops** (initial §5.2, breakeven §5.4) — intrabar order at the same triggering session for both arms. **Realistic** fill = `min(current_stop, bar.open)` (gap-down realizes the true >1R loss); **favorable-reprice** fill = `current_stop`.
- **Close-below-MA trail** (§5.5) — EOD signal; both arms exit on the same next session. **Realistic** fill = next-session open; **favorable-reprice** fill = `max(signal_close, next_open)`. The favorable-reprice fill is a **non-executable upper-bound reference**, not a realism-transfer claim.

**5.7 Horizon / censoring (D5/D10).** If no exit by `min(126, bars_available)` sessions post-entry, the trade is **open-at-horizon**. Per-hypothesis aggregation reports **four survival-aware scenarios** (no single "true" number, no "lower bound" claim): (1) **closed-only**; (2) **MTM-at-horizon** (mark remaining shares at last frozen close); (3) **forced-exit-at-horizon-open** (next available open after the horizon; **if no post-horizon open exists in the log, this collapses to MTM and is annotated as such**); (4) **`stop-level-adverse`** (every open filled at its current stop — **excludes** future overnight gap-through-stop risk, so it is a conservative-but-not-absolute-worst bound). The spread across scenarios *is* the censoring uncertainty; honors #27.

**5.8 Multi-leg R + the bracket.** Realized R = Σ over legs of `(leg.exit_price − entry_fill) × leg.qty / (risk_per_share × initial_shares)`, via the pure `derived_metrics` functions, on a **fixed entry_fill / fixed denominator**. The realistic and favorable-reprice numbers differ only by exit fills (§5.6), so `favorable_R ≥ realistic_R` per trade by construction. Reported as `[realistic, favorable_reprice]`. The headline / realism-transfer estimate is the **realistic** value; favorable-reprice is a context bound. For **open-at-horizon** trades there is no stop/MA exit fill to reprice, so realistic and favorable-reprice **coincide** under the MTM and forced-exit scenarios (and under `stop-level-adverse`, both arms use the same stop level); the arms diverge only where an actual gap-through-stop exit occurred on a closed trade (Codex R3-m2).

---

## 6. Hypothesis attribution

- **Unit of forward-walk:** one shadow-trade per **unique `(pipeline_run_id, ticker)` candidate signal**. Multiple pattern-class detections for the same ticker/run collapse to one shadow-trade; counting each would double-count. The **canonical detection** is chosen deterministically: the detection whose `pivot == candidate.pivot`, tie-broken by lowest `detection_id`. Entry timing + the entry bar come from that canonical detection's frozen `triggered_open` (§5.1); the candidate row supplies `bucket`/criteria for **attribution only**. Writing-plans MUST verify `candidate.pivot == canonical detection.pivot` (compared at **normalized price-tick precision**, not raw float equality — Codex R5-m1; normalized values recorded in the ledger) and that all collapsed detections for the `(run, ticker)` carry **both an identical frozen forward-OHLC series AND an identical first `triggered_open` session** — same pivot + same bars can still yield a different per-detection trigger via structural anchors (Codex R5-M1). On OHLC divergence the signal is excluded under `inconsistent_detection_series`; on trigger-state divergence, under `inconsistent_trigger_state`. The collapsed detection IDs are recorded in the ledger (Codex R3-M1 / R4-M1).
- **Join + uniqueness (Codex R2-M4):** writing-plans MUST assert that `candidates` has at most one row per `(pipeline_run_id, ticker)` (and test it); if the schema permits duplicates, dedupe deterministically and record it. The matcher tags the hypothesis (H1 ⇐ `bucket=='aplus'`; H2/H3/H4 ⇐ watch + the frozen criterion-miss sets).
- **Immutability (Codex R1-M1):** writing-plans MUST verify the joined candidate fields (`bucket`, `pivot`, `initial_stop`, per-criterion results) are immutable post-insert; if any is not provably frozen, source it from the frozen `pattern_detection_events` copy. A test asserts a candidate row is unchanged insert→read.
- **Registry:** V1 uses the current active registry (4 frozen v0.1 hypotheses, stable since 2026-04-25; the log carries data only from after that date, so point-in-time = current). The manifest emits the registry version/hash; point-in-time replay is a V2 concern.
- **A+ isolation:** the #23 pool-widening put the watch population in the log; A+ stays distinguishable via the candidate `bucket`. A detection with **no joinable candidate row** is counted in the funnel (§7) with its skip reason, never silently dropped (#27).

**6.1 Hypothesis-criterion ↔ shadow-metric mapping (Codex R1-M7).**

| Hyp | Registered criterion | Shadow metric reported against it |
|---|---|---|
| H1 | mean R > 0 AND Wilson-LB win-rate > 30% | triggered-trade mean R + Wilson-LB win-rate, A+ bucket |
| H2 | mean R within 25% of A+ baseline | watch∩proximity_20ma-only mean R vs H1 mean R |
| H3 | confirm **negative** mean R | watch∩(tightness|vcp) mean R |
| H4 | mean R positive (smaller position) | (watch/skip)∩risk_feasibility-only mean R — production `_capital_blocked_match` accepts bucket∈{watch,skip} (Codex writing-plans R2-M5) |

Shadow evidence is explicitly "**H-x under the canonical mechanical ruleset**" — a well-defined proxy, *not* identical to the operator's hand-traded outcome. Divergence between shadow and hand-traded results is itself a reported finding.

---

## 7. Output

A per-run artifact directory (e.g. `research/studies/shadow-expectancy-runs/<run-id>/`) containing:

1. **Denominator funnel — two levels (Codex R3-M2).** *Detection-level reconciliation:* total emitted detections → `collapsed_duplicate_detection` (non-canonical duplicates for a (run,ticker)) → unique `(run,ticker)` signals. *Signal-level outcomes:* the per-signal pipeline order is **collapse → candidate-join → attribute → validate → simulate**; signals flow unique → joinable-to-candidate → attributed → triggered (entered) → {closed, open-at-horizon} → excluded, with **reasons** (`no_candidate_join`, `matched_no_hypothesis`, `multi_match`, `no_canonical_detection`, `inconsistent_detection_series`, `inconsistent_trigger_state`, `invalid_ohlc`, `degenerate_risk`, `insufficient_forward_depth`, `missing_observations`, `lifecycle`, `never_triggered`). **Routing (Codex writing-plans R1-M5/M6, R2-M4):** the **`unattributed`** bucket holds only the *pre-/non-attribution* states — `no_candidate_join` (no candidate row), `matched_no_hypothesis` (candidate exists but matches zero hypotheses), `multi_match` (candidate matched >1 of the mutually-exclusive hypotheses — defensive, ~0 in practice), `no_canonical_detection` (candidate exists but no detection pivot matches it — a substrate/collapse integrity fault), and the collapse-stage `inconsistent_detection_series` / `inconsistent_trigger_state` (caught before the matcher). `matched_no_hypothesis` is a *reason within* `unattributed` (reported with its own counter in the reason breakdown), NOT a separate top-level bucket. **Reconciliation invariant (Codex writing-plans R3-M1):** Σ(`unattributed` reason counts) + Σ(per-hypothesis terminal-status counts) == `unique_signals`, asserted in a test. The 4 seeded hypotheses are mutually exclusive by their exact-miss-set definitions, so each signal attributes to AT MOST one; a defensive `multi_match` unattributed reason guards a future non-exclusive hypothesis and keeps the invariant exact (no signal is ever counted in two hypotheses). The per-`unattributed`-reason breakdown is surfaced in `summary.md`, not just the manifest. **Validation failures (`invalid_ohlc`, `degenerate_risk`) are caught AFTER attribution and reported PER-HYPOTHESIS**, so per-bucket data-quality rates are never hidden in a global bucket. Terminal trade statuses apply only at the signal level; the two levels are reported separately and reconciled, never mixed. Makes the selected-sample risk explicit (Codex R1-M3).
2. **Per-hypothesis scorecard:** triggered-trade expectancy_R `[realistic, favorable_reprice]` under each of the four censoring scenarios (D10); trigger rate; per-signal expectancy (D11); win rate + Wilson CI; avg win/loss R; payoff ratio; **profit factor (suppressed/annotated below sample floors)**; median holding sessions. Suppressed below sample floors; the same-bar-adverse sensitivity (D9) shown alongside.
3. **Per-trade ledger:** ticker, detection_date, run_id, hypothesis, bucket, every leg (action/qty/price/session), realized R bracket, `exit_reason`, open-at-horizon flag, entry-bar-ambiguity flag.
4. **Run manifest:** effective horizon, parameters (N, breakeven_r, MA staging), temporal-log min/max dates, registry version/hash, counts at each funnel stage.

Headline for the operator: **H1's triggered-trade count and realistic expectancy** under the four censoring scenarios — the number that tells us whether to keep investing in the A+ strategy.

---

## 8. Reproducibility guarantees

- Trade-path bars read from the immutable frozen `ohlc_today_json` → no mutable-archive drift.
- No randomness (deterministic fills); SMAs from frozen forward bars only → no archive read.
- **Reproducibility scoped to the canonicalized metric payload** (sorted keys, fixed float precision, excluding run-id/timestamps/formatting). A test asserts identical canonical payload across re-runs on the same log state + parameters.

---

## 9. Testing strategy

- **Golden hand-computed walks** (R hand-verified, both fill arms): (a) gap-up entry (single entry fill; ambiguous-subset flag if `low < entry_fill`); (b) gap-down stop blowing through 1R (realistic < −1R, favorable-reprice = −1R); (c) partial-at-3-then-trail winner (multi-leg R); (d) horizon-censored runner (all four D10 scenarios, incl. forced-exit→MTM collapse when no post-horizon open; realistic == favorable for open trades); (e) not-in-profit-at-N (no partial); (f) **degenerate-risk** entry (non-positive denominator) excluded; (g) **invalid_ohlc** bar (NaN/negative/`high < low`) excluded with its funnel reason.
- **Bracket bound:** `favorable_R ≥ realistic_R` for every trade (fixed denominator), with a test asserting the denominator is identical across arms.
- **Entry-bar ambiguity:** the subset is exactly `entry_bar.low < entry_fill`; the same-bar-adverse sensitivity differs from the headline only over that subset and is not applied to `low ≥ entry_fill` trades.
- **Attribution + uniqueness + immutability + collapse-consistency:** A+→H1 etc.; one shadow-trade per unique (run,ticker); canonical detection = `pivot==candidate.pivot` tie-broken by lowest detection_id; `candidate.pivot != detection.pivot` excludes; collapsed detections share an identical frozen forward series AND first `triggered_open` session (else `inconsistent_detection_series` / `inconsistent_trigger_state`); pivot match compared at normalized tick precision; a `no_candidate_join` signal lands in the `unattributed` bucket, not a hypothesis; candidate row unchanged insert→read.
- **No look-ahead:** the detection-day bar never triggers entry; entry is the canonical detection's first frozen `triggered_open` strictly after `detection_date`.
- **Simultaneous EOD conditions:** §5.0 precedence is deterministic.
- **Unit-of-analysis:** trigger rate + per-signal vs triggered-trade expectancy both emitted, distinct.
- **Denominator funnel (two-level):** detection-level reconciles emitted → `collapsed_duplicate_detection` → unique signals; signal-level lands each unique signal in exactly one terminal bucket; the two levels reconcile; reasons (incl. `invalid_ohlc`, `inconsistent_detection_series`) recorded.
- **Reproducibility:** identical canonical payload across re-runs.
- Fast suite stays green (baseline ~7268+).

---

## 10. Scope / YAGNI — explicitly OUT

- Climax-top / ADR-extension trim (V2).
- 50-day MA character arm + character-based 10/20/50 selection (V2; V1 is a maturity-staged 10/20 proxy).
- Entry-side execution optimism (unrealizable on gap-ups; the single realistic entry is used — D2).
- Stochastic slippage (non-reproducible; conflicts with D1/D2).
- Ruleset sweep / matrix (repeats the W-arc mistake).
- Operator-facing dashboard surface (later promotion).
- Backfill over the mutable OHLCV archive (re-inherits #26/#37).
- New production schema / temporal-log terminal-state writeback (deferred).
- Freezing SMAs at detection (V2 hardening).
- Point-in-time registry replay (V2).
- Future gap-through-stop modeling for *open* (censored) trades (the `stop-level-adverse` scenario explicitly excludes it — D10).

---

## 11. Risks & limitations (state them honestly in the report)

1. **Censoring is two-sided.** Open-at-horizon trades may resolve better *or worse* than MTM; we do NOT claim a lower bound. The four-scenario spread (D10) is the honest band. Note `stop-level-adverse` still excludes future gap-through risk, so it is conservative-but-not-absolute.
2. **Effective horizon is bounded by the log's current post-trigger depth** — if < 126 sessions today, V1 is bounded by it; extending the observe-step horizon is a separate follow-on.
3. **Selected-sample risk.** "Every emitted signal" is qualified by the funnel (§7); if exclusions correlate with outcomes, expectancy is biased. The funnel surfaces the rate per reason per hypothesis.
4. **Conditional-on-trigger vs per-signal.** Headline = triggered-trade expectancy; per-signal (non-triggers as no-trade) reported alongside (D11).
5. **Only the realistic arm transfers to live fills.** The favorable-reprice arm is a non-executable upper-bound reference; do not read it as an achievable result.
6. **Entry optimism is not modeled** — the single realistic entry (`max(pivot, open)`) is used for both arms because filling below the bar's traded range is impossible; the bracket reflects EXIT execution uncertainty only.
7. **MA-trail activation lag + 10/20 proxy** (D7/D12) make V1 slightly more *stop/breakeven/partial*-driven, shorter-MA than full doctrine; V2-hardenable.
8. **Mechanical-ruleset proxy.** Shadow evidence tests each hypothesis under one fixed ruleset (§6.1), not the operator's hand-management; kept separate from live counts.
9. **Sample maturity.** H1 still accrues only as A+ signals fire forward; the engine accelerates relative to hand-trading but does not manufacture history. Weeks-to-months to a decision-grade H1 n.

---

## 12. Success criteria

- `swing diagnose shadow-expectancy` emits the §7 artifact (funnel + four-scenario scorecard + ledger + manifest) over the live temporal log.
- All §9 tests pass; fast suite green on the merged head.
- The H1 bucket shows **triggered shadow trades ≫ the 1 live closed**, with the four-scenario realistic expectancy + Wilson CI — i.e. the engine measurably accelerates the H1 evidence the project has been starved of, with honest uncertainty bands.
- Zero production write-path changes; L2 LOCK preserved (one CLI subcommand only).
