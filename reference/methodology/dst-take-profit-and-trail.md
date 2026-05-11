# Disciplined Swing Trader — Take-profit + Trail Rules

**Source:** *The Disciplined Swing Trader: Forging Consistency from Knowledge*, Dani (@trades_lakes), self-published / community-authored. Chapters 10 (Rule-Based Exits) and 11 (Risk Management) of the 86-page PDF at `reference/The Disciplined Swing Trader_ Forging Consistency from Knowledge.pdf`.

**Transcribed:** 2026-05-10 by orchestrator (PDF-extracted via PyMuPDF; verified verbatim against pp. 28-34).

**Status:** ~ PARTIAL — 3/5 rules CONFIRMED-with-correction; 2/5 rules NOT-PRESENT-IN-SOURCE.

---

## Provenance correction (operator-attention)

This DST is **NOT** the well-known commercial book of similar title; it is a community-authored work by **Dani (@trades_lakes)** explicitly framed as: *"Based on the Principles of my trading psychologist and girlfriend Alma (@joke.la), Qullamaggie, Peoplewish and Experienced Traders... AI used to fix the language from my notes"* (cover page). The sell-side rules are derivative paraphrases of:

1. **Qullamaggie** (Kristjan Kullamägi) — primary
2. **peoplewish** — peoplewish Q&A logs cited heavily
3. **Realsimpleariel** — cited for ADR-extension trim
4. **Livermore** — invoked once for stop discipline

**Implication for the 3e.8 §6.4 [UNVERIFIED] D-flag triage:** The "DST D.x" labels in the 3e.8 investigation point to this book as the doctrinal source — but doctrinally, the rules trace to Qullamaggie/peoplewish primary. The Qullamaggie MCP server (per `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/reference_qullamaggie_mcp.md`) IS the closer-to-source provenance for verification of the D rules. DST acts as a structured aggregator of the Q+peoplewish corpus.

---

## D.1 — Initial stop placement (LOD of breakout candle)

**Source citation:** Ch 10, pp. 28-30, "Pillar 1: Mechanical Stop-Losses" (also Ch 11, p. 32-33 reinforcing).

**Status:** CORRECTED — 3e.8 paraphrased "swing low or breakout pivot's reaction low"; actual DST rule is **LOD (Low of Day) of the entry/breakout candle**, NOT swing low or reaction low.

**Transcription (verbatim):**

```
The Initial Stop (LOD Rule):
Both Qullamaggie and "peoplewish" heavily reference using the Low of Day (LOD)
of the entry/breakout candle as the initial stop-loss, especially for swing trades.

Peoplewish is explicit: "stop out must come from day 1 LOD ONLY. There is no other
way to stop out between days 1 and 3."

Why LOD? It represents a clear level where buying interest failed on the crucial
breakout day. A violation suggests the immediate breakout momentum has failed. It's
objective and based on the day's actual price action.

Execution: Place a hard stop-loss order (market order preferred) at your defined
LOD level immediately after entry. "If you get stopped out you get stopped out, you
don't start rationalising stuff... no second guessing)." - Qullamaggie paraphrasing
Livermore. "Of course I hit the stop, why would I not?... The only way to make
millions in the market is to hit your stops." - Qullamaggie.
```

**Day-1 Red Close override (additional rule; not in original 3e.8 D-set):**

```
The "Day 1 Red Close" Rule (Potential Override): Peoplewish adds a crucial
discretionary (or rule-based) overlay: "I dont hold day 1 red names... say it
doesnt trigger your stop by EOD but you're red on it... I just cut it." This
requires a specific rule in YOUR plan: Do you exit any position closing red on
Day 1, regardless of the LOD stop, or only under certain conditions...
```

**Operator notes:** Verify against current framework `swing/trades/entry.py` initial-stop derivation. The framework currently allows operator-specified `initial_stop` at entry without enforcing LOD specifically. LOD-as-stop is operator-discipline today, not framework-enforced. Day-1-red-close override is not surfaced anywhere in the framework.

---

## D.2 — Take partial profit into strength (50% on Day 3-5)

**Source citation:** Ch 10, p. 30, "Pillar 2: Managing Winners — Initial Partial Profit Taking (Day 3-5 Rule)".

**Status:** CORRECTED — 3e.8 paraphrased "1/4 to 1/3 reduction"; actual DST/peoplewish rule is **50% on Day 3, 4, or 5** (counting entry day as Day 1).

**Transcription (verbatim):**

```
Initial Partial Profit Taking (Day 3-5 Rule):
Peoplewish advocates for a mechanical partial sale: "Always sell 50% - Any more
you'll feel like you missed out. Any less and youll fell like you should have
sold more. 50% is the perfect amount..." (from pinned message). He specifies
doing this on Day 3, 4, or 5 (counting entry day as Day 1).

Make it Non-Subjective: Choose which day (e.g., "End of Day 3" or "End of Day 4")
and put it in your plan. Stick to it initially. This locks in some gain, reduces
psychological pressure, and makes holding the remainder easier.

Exception (Conviction): Peoplewish notes high-conviction exceptions like MSTR
where he "threw my sell 50% on day 3-5 out the window. I've seen that setup before
and knew where it was going."
```

**Operator notes:** This is a TIME-DRIVEN trim (Day 3-5 calendar window), not an R-multiple-driven trim. The 3e.8 §4.B "Recommendation B" proposed a +1R-driven trim at default 25%. These are DIFFERENT triggers:
- **Doctrine (D.2 actual):** Day 3-5 calendar trigger; 50% sale
- **3e.8 §4.B proposed:** +1R first-time trigger; 25% sale (configurable)

The 3e.8 §4.B operator-tunable defaults can be adjusted to match D.2 (trim_first_pct_default=0.50; replace +1R trigger with day-count trigger). Or the framework can support BOTH triggers (calendar OR R-multiple). Worth flagging in the §4.B implementation brief.

**Cross-reference:** §3e.8 §4.B (trim/sell-into-strength advisory) commissioned in implementation bundle 2. Operator should decide whether to keep R-multiple trigger (current 3e.8 design) OR switch to D.2-faithful Day-3-5 trigger OR support both.

---

## D.3 — 10DSMA primary trail; speed-correlated MA selection

**Source citation:** Ch 10, pp. 30-31, "Pillar 2: Managing Winners — Trailing Stops for the Remainder (The MA Trail)".

**Status:** CORRECTED — 3e.8 paraphrased "10-EMA fast movers vs 20-SMA steady names"; actual DST rule is:
- **Primary trail:** 10-day Simple Moving Average (10**DSMA** — Simple, NOT Exponential)
- **Speed-correlated selection:** strongest stocks → 10-day; strong → 20-day; slower institutional → 50-day (Qullamaggie quote)
- **Maturity stage** is NOT how the DST text frames the MA selection — it frames it by **stock strength/speed**, not by trade-maturity

**Transcription (verbatim):**

```
The Core MA: The 10-day Simple Moving Average (10DSMA) is frequently cited
by Peoplewish as the primary trailing stop after the initial partial sale. "Sell 50%
day 3. 50% close below the 10DSMA."

Other MAs (Contextual): Qullamaggie also mentions the 20-day and 50-day MAs,
particularly for slower institutional stocks or as secondary/tertiary stops. "The
strongest stocks find support on the 10day, the strong ones the 20day and the slower
ones on the 50day..." You might define using the 20DMA if the 10DMA is violated but
price holds the 20DMA, but start simply with the 10DMA rule.

Execution: Sell the remaining position (or another defined portion) on the first
CLOSE below the chosen trailing MA (e.g., 10DSMA). Not just an intraday touch. "I
wait to see how it closes." - Qullamaggie.
```

**Operator notes:** Two material differences from the 3e.8 paraphrase + Tier-3 #6 framing:

1. **EMA vs SMA.** Doctrine says SMA. Framework's `swing/trades/advisory.py` rules `trail_10MA` / `trail_20MA` consume `ctx.sma10` / `ctx.sma20` (i.e., already SMA per current code). Match. The 3e.8 paraphrase introducing "EMA" was incorrect — no operational impact.

2. **Stock-strength vs trade-maturity gating.** Doctrine selects MA by **stock characteristic** (10-day for strongest fast movers; 20-day for strong; 50-day for slower institutional names). Tier-3 #6 selects MA by **trade-maturity stage** (20MA pre-+2R; upgrade to 10MA post-+2R). These are TWO DIFFERENT gating principles. The Tier-3 #6 framing is project/operator-policy, NOT direct DST/Qullamaggie doctrine. The 3e.8 §4.A and §4.A.bis recommendations both gate on maturity_stage; doctrinally, gating by stock-speed (e.g., per-trade `is_fast_mover` flag) would be the source-faithful choice.

**Cross-reference:** §3e.8 §4.A.bis (maturity-stage hint advisory) commissioned in implementation bundle 3. Operator should consider whether the hint's framing "Maturity stage X → recommended trail-MA: YMA" is the right framing or whether it should instead be "Stock speed Z → recommended trail-MA: YMA" (where speed is a separate per-trade attribute). For V1 the maturity-stage gating is operationally simpler (uses existing Phase 8 schema); the doctrinal-faithful version would require new "stock_speed_class" capture at entry.

---

## D.4 — Tighten stop after +2R

**Source citation:** **NOT-PRESENT-IN-SOURCE.**

**Status:** NOT-PRESENT-IN-SOURCE — DST Ch 10 + Ch 11 do NOT contain a +2R-driven stop-tightening rule. The 3e.8 paraphrase attributing this to DST is incorrect.

**What DST DOES contain (Breakeven Stop Rule, Ch 10 p. 31):**

```
The Breakeven Stop Rule:
When do you move your stop on the remaining position to breakeven? Peoplewish
provides a clear sequence: AFTER selling the initial 50% (on Day 3-5) AND only
once the trailing MA (10DSMA) surpasses your average entry cost. "I then move the
rest up to break even until the 10DMA surpasses my average and thats when the
trailing starts." This prevents getting stopped out prematurely on normal volatility
before the trend truly establishes.
```

**Operator notes:** The actual DST stop-tightening sequence is:
1. After 50% sale (Day 3-5), keep stop at LOD
2. When 10DSMA crosses above average entry cost → move remaining-50% stop to breakeven
3. After breakeven established → trail behind 10DSMA on close-below-MA basis

This is a **sequence-driven** progression (50%-sale-event → MA-crossover-event), NOT an **R-multiple-driven** progression (+1R → +2R → +3R). The Tier-3 #6 framing's "+1.5R / +2R" thresholds are project/operator-policy, NOT in DST doctrine.

**Cross-reference:** §3e.8 §4.A (full classification-altering trail-MA gating) deferred. The deferral is reinforced — there is no doctrinal +2R-tighten rule in DST to anchor V2.1 §VII.F routing on. If the operator wants doctrine-faithful trail-management gating, the gating principle would be sequence-of-events (50%-trim → 10DSMA-crosses-entry-cost) NOT R-multiples. Worth re-thinking §4.A's framing entirely.

---

## D.5 — 7-10 day vs 7-week time-stop

**Source citation:** **NOT-PRESENT-IN-SOURCE.**

**Status:** NOT-PRESENT-IN-SOURCE — DST does NOT contain ANY time-stop framing. No mention of "time stop", "7-week", "7-10 day", "days max", or equivalent calendar-based exit rule.

**What DST DOES contain (the Day 3-5 partial-sale window):**

The Day 3-5 partial-sale window IS a calendar-based event but it is a **trim** trigger, NOT a **time-stop** trigger. The trade is not exited on Day 3-5 — only 50% trimmed. The remainder rides until 10DSMA close-below.

**Operator notes:** The 3e.8 §6.4 row "DST D.5: 7-10 day vs 7-week time stop" attributed a time-stop rule to DST that does not appear. The closest DST construct is the Day 3-5 partial-sale window — which has fundamentally different semantics (trim, not exit).

The "7-week rule" specifically is a Minervini construct (M.4 in `minervini-sell-side-rules.md`) — not DST.

**Cross-reference:** §3e.8 §4.C / §4.C.bis (time-stop discipline) deferred. The deferral is reinforced — no doctrinal DST time-stop rule exists. If the operator wants a time-stop default change, the only doctrinal anchor available is whatever Minervini's M.4 actually says (per the Minervini scaffolding file). The Q.1 (Qullamaggie 3-5 day) reference cited in 3e.8 §3.C may also need re-verification through the Qullamaggie MCP.

---

## Additional sell-side rules not in original 3e.8 D-set

DST Chapter 10 contains TWO additional sell-side rules that the 3e.8 investigation did not surface as standalone D-numbered claims. Captured here for completeness; these are doctrine the framework currently does not implement.

### D.6 (NEW) — Parabolic handling via intraday EMAs

**Source citation:** Ch 10, p. 31, "Handling Parabolics & Extensions".

**Transcription (verbatim):**

```
Handling Parabolics & Extensions:
Qullamaggie mentions tightening stops significantly on parabolic moves, potentially
using intraday EMAs (e.g., 60min 20EMA or even 5min 50EMA for very fast moves)
because daily MAs lag too much. "If you get a parabolic move it's all about
aggressively protecting profits."
```

**Operator notes:** Cross-references §3e.8 §4.D (parabolic-extension detector) commissioned in implementation bundle 2. Doctrine-faithful implementation of parabolic-trim would shift to intraday MAs (60min 20EMA / 5min 50EMA) rather than just emitting a daily-bar-based detection signal. Worth flagging in the §4.D implementation brief — the V1 "+25% in 5 days + 15% above 20MA" is a detection rule; the doctrine-correct response is to switch the trailing-MA reference to intraday rather than just trim.

### D.7 (NEW) — ADR-multiple extension trim (Realsimpleariel)

**Source citation:** Ch 10, p. 31, "Handling Parabolics & Extensions" (continued).

**Transcription (verbatim):**

```
"Realsimpleariel" suggested a systematic approach based on ADR multiples from
the 50SMA: Consider trimming portions once a stock is extremely extended (e.g.,
>7x ADR above 50SMA), selling additional pieces as the extension increases (8x,
9x, 10x). Your plan could incorporate a version of this for extreme situations.
```

**Operator notes:** ADR-multiple extension is a quantitative parabolic-detector with explicit threshold (>7x ADR above 50SMA). This is the closest doctrine source for §3e.8 §4.D's threshold defaults. The 3e.8 §4.D defaults (25% in 5 days / 15% above 20MA) are arbitrary; D.7's >7x ADR above 50SMA is doctrine-anchored. Worth re-anchoring §4.D's thresholds to D.7's formulation in the implementation brief.

---

## Footnotes / qualifiers (as printed)

The DST source frames these rules as "starting points to be customized in your own Trading Plan." The author repeatedly emphasizes operator-discretion within the rule framework — e.g., "Choose which day (e.g., End of Day 3 or End of Day 4) and put it in your plan."

---

## Usage notes (not from source — interpretive)

- This file is **reference material only**. Do not edit production code to "match" the rules above without routing the change through the research-branch promotion cycle per V2 Addendum Addition 2 (source-of-truth correction protocol).
- Three of the original 3e.8 D-flag claims required CORRECTION (D.1, D.2, D.3); two required NOT-PRESENT-IN-SOURCE disposition (D.4, D.5). Two ADDITIONAL rules surfaced during transcription (D.6 parabolic-intraday-EMA + D.7 ADR-extension-trim) that were not in the original 3e.8 D-set.
- The "DST" source is community-authored derivative of Qullamaggie/peoplewish; doctrinal verification at the source level should route through the Qullamaggie MCP server (`mcp__qullamaggie__*` tools) for primary attribution.
- The Tier-3 #6 maturity-stage framing in the project (default 20MA pre-+2R; upgrade to 10MA post-+2R) is **project/operator-policy** layered on the doctrine — DST doctrinally selects MA by **stock-strength/speed** (per Qullamaggie quote), NOT by trade-maturity-stage. Operator may want to revisit whether maturity-stage gating or stock-speed gating is the better V1 default. The Phase 8 schema supports maturity_stage; would need new schema for stock_speed_class.
- Numerical thresholds in the source take precedence over arbitrary 3e.8 defaults. Once §4.B / §4.D / §4.A.bis dispatches are drafted, the implementation briefs should re-anchor defaults to the doctrine values surfaced here:
  - §4.B trim_first_pct_default: doctrine = **0.50** (peoplewish "always sell 50%"); 3e.8 default was 0.25
  - §4.B trigger: doctrine = **Day 3-5 calendar window**; 3e.8 default was first-time +1R
  - §4.D parabolic threshold: doctrine = **>7x ADR above 50SMA** (Realsimpleariel); 3e.8 default was 25% in 5 days + 15% above 20MA
  - §4.A.bis MA selection: doctrine = **stock-speed-driven** (strongest→10/strong→20/slow→50); 3e.8 design = maturity-stage-driven
