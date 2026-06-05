# Minervini SEPA Sell-side Rules

**Sources:** *Trade Like a Stock Market Wizard*, Mark Minervini, McGraw Hill 2013 (TLSMW) · *Think & Trade Like a Champion*, Mark Minervini, Access Publishing 2017 (TTLC).
**Reviewed:** 2026-05-10 by Reid Smythe (TLSMW only). **Think & Trade verification added 2026-06-04** (TTLC transcribed + now agent-readable — see `reference/books-corpus-index.md`).
**Status:** ✓ substantially COMPLETE across the two primary Minervini works — M.2 CONFIRMED (both books); **M.3, M.5, M.6 UPGRADED to CONFIRMED-QUANTITATIVE by TTLC**; M.1 clarified (the "1.25" traces to TTLC's 1.25–2.5% risk-per-trade sizing, not an expectancy backstop); M.7 BRIEF-MENTION (TTLC frames gap-down as a sizing/risk argument, not a discrete sell trigger); **M.4 (7-week time-stop) NOT-PRESENT in EITHER primary book** (community attribution unsupported by the two primary texts).

> **2026-06-04 provenance correction.** This file previously stated *Think & Trade Like a Champion* was "NOT AVAILABLE to operator" and left M.1/M.4/M.5/M.6 unverifiable on that premise. **That premise was false** — TTLC is transcribed at `reference/Books/mark-minervini-think-trade-like-a-champion-access-publishing-group-2017/`. The TTLC verification layer below resolves those gaps. (TTLC line refs are to the transcribed `.md`.) This is a **source-verification update only**; any production-code change it motivates still routes through the V2.1 §VII.F source-of-truth correction protocol.

---

## Provenance + scope

TLSMW (2013) is **primarily an entry-side text** (trend-template, VCP, RS, leadership, fundamentals); its sole dedicated sell-side passage is "sell into strength" (Ch 13). **TTLC (2017) is where Minervini's structured sell-side discipline actually lives** — it contains explicit, often quantitative, sell rules: post-breakout "violations" (20-day/50-day MA closes), the climax-top / selling-into-strength framework, staggered stops, position-sizing risk bounds, and the 50/80 rule.

**Third work, still NOT transcribed:** *Mindset Secrets for Winning* (2019) — present as `reference/Books/mind-secrets-for-winning-mark-minervini/`; primarily psychology, low sell-rule density (not re-reviewed here).

Status taxonomy per rule:
- **CONFIRMED-QUANTITATIVE** — a Minervini text provides a specific quantitative anchor.
- **CONFIRMED-QUALITATIVE** — the principle is articulated without specific thresholds.
- **BRIEF-MENTION-NO-DETAIL** — touched on, no actionable specifics.
- **NOT-PRESENT** — absent from both transcribed primary works (TLSMW + TTLC).

---

## M.1 — 1.25× backstop expectancy heuristic

**Status:** NOT-PRESENT *as framed* — neither TLSMW nor TTLC contains a "1.25× backstop expectancy" multiple.

**TTLC verification (2026-06-04):** TTLC's only "1.25" is a **position-sizing risk bound**, not an expectancy backstop: *"your maximum risk should be no more than 1.25 to 2.5 percent of your equity on any one trade"* (TTLC §"HOW MUCH RISK IS TOO MUCH?" / §8 sizing, md ~L2135, L2153, L2195). The 3e.8 "1.25× backstop expectancy heuristic" attribution appears to be a **conflation/garble of this 1.25–2.5%-of-equity risk-per-trade rule** — which IS Minervini doctrine, but is a sizing rule, not an exit/expectancy rule. **Disposition:** retire the "1.25× backstop expectancy" label; if the intent was the risk-per-trade floor, cite TTLC's 1.25–2.5% equity-risk band instead.

---

## M.2 — Sell into strength

**Status:** CONFIRMED-QUANTITATIVE (TLSMW) — **reinforced by TTLC.**

**TLSMW Ch 13, p. 296 (verbatim, operator-transcribed 2026-05-10):**

> Once a stock amasses a percentage gain that is a multiple of your stop loss, you should rarely allow that position to turn into a loss. For instance, let's say your stop loss is set at 7 percent. If you have a 20 percent gain in a stock, you shouldn't allow that position to give up all that profit and produce a loss. To guard against that, you could move up your stop loss to breakeven or trail a stop to lock in the majority of the gain. … There are two ways you can sell: -Into strength … -Into weakness … Selling into strength is a learned practice of professional traders. It's important to recognize when a stock is running up rapidly and may be exhausting itself. … You need to have a plan for both selling into strength and selling into weakness.

**TTLC verification (2026-06-04):** TTLC restates and expands this. The breakeven anchor is named the **"breakeven or better rule"** (TTLC index p.196–197) and §"NEVER LET A GOOD-SIZE GAIN TURN INTO A LOSS" (md ~L1417). Selling-into-strength gets a dedicated treatment (md ~L2229–2231, L2495: *"you still want to learn how to sell into strength … you don't want to give a stock the chance to break and give back a large portion of your profits"*). Confirms the two anchors: (1) quantitative R-multiple-of-stop ("once gain is a multiple of stop loss, never let it turn into a loss → breakeven or trail"); (2) qualitative sell-into-strength discipline.

**Cross-reference (unchanged):** M.2's recommended ACTION is **stop-tightening (breakeven/trail)**, the doctrine anchor for §3e.8 §4.A — NOT §4.B trim (DST D.2 remains the trim anchor). TTLC corroborates the stop-tightening framing.

---

## M.3 — Sell on close below N-day MA (specific N values)

**Status:** **UPGRADED BRIEF-MENTION → CONFIRMED-QUANTITATIVE by TTLC.** TLSMW used MAs entry-side only; TTLC gives explicit MA-violation **sell** signals.

**TTLC verification (2026-06-04)** — §"IF THINGS DON'T GO AS PLANNED" / "Violations Soon After a Breakout" / "WATCH FOR MULTIPLE VIOLATIONS" (md ~L515–575, L597) and §9 trailing use (md ~L2441):

> Once a stock breaks out of a proper base … it should hold above its 20-day moving average; I don't want to see the price close below its 20-day line soon after a breakout. … after a stock breaks out of a proper VCP, if it closes below its 20-day moving average shortly thereafter, the probability of it being successful before stopping you out is cut in about half. If the stock closes below the 50-day line on heavy volume, it's an even worse sign. … a close below the 20-day moving average is not significant on its own; it's when it occurs soon after a stock breaks out of a proper base … particularly if additional violations are triggered.

Explicit "violations" list (md ~L573–575): **a close below the 20-day MA** · **a close below the 50-day MA on heavy volume** · full retracement of a good-size gain. Trailing use (md ~L2441): *"Some leaders can go an amazing distance before they close below the 50-day line."*

**Important nuance:** TTLC treats the 20-day close as **probability-reducing + context-dependent (soon-after-breakout) + judgment-call within a multi-violation confluence**, NOT a hard single-trigger sell (*"I won't necessarily sell just for that reason alone"*; *"I'll either reduce my position or get out entirely"* depending on how many violations stack). The 50-day close is a stronger, trailing-stop-grade signal.

**Cross-reference:** the framework's `exit_below_10ma`/`exit_below_20ma`/`exit_below_50ma` now have a **real Minervini doctrine anchor** (20-day soon-after-breakout; 50-day-on-volume as trail) — previously "operator-policy only." Note the doctrine-faithful framing is multi-violation/judgment, not single-trigger; any production alignment routes through §VII.F.

---

## M.4 — 7-week rule (time-stop)

**Status:** **NOT-PRESENT — confirmed absent from BOTH TLSMW and TTLC.**

**TTLC verification (2026-06-04):** Targeted search of TTLC for "7 week / seven week / 49 day / time stop / time-based" found **no time-based exit rule.** ("27-week" hits refer to Netflix's *base* duration, entry-side.) The nearest related concept is **opportunity-cost / turnover** (TTLC §4 "TURNOVER AND OPPORTUNITY COST", md ~L1121) — a rationale for rotating out of dead-money positions, but NOT a quantified 7-week/49-day time-stop. **The widely community-attributed "7-week rule" is unsupported by either primary Minervini text.** If a time-stop is desired, it remains a non-Minervini choice (Qullamaggie Q.1's 3–5 day window is the only doctrine anchor, and is far more aggressive).

**Cross-reference (reinforced):** §3e.8 §4.C/§4.C.bis time-stop deferral stands; the doctrine landscape (no Minervini time-stop; only aggressive Q.1) suggests any default change would TIGHTEN, not loosen.

---

## M.5 — Parabolic / blow-off-top (climax) extension thresholds

**Status:** **UPGRADED BRIEF-MENTION → CONFIRMED-QUANTITATIVE by TTLC.** This corrects the prior doc's claim that "Minervini provides no quantitative anchor." TTLC's §"THE CLIMAX TOP" is an explicit, quantified climax-detection framework.

**TTLC verification (2026-06-04)** — §"THE CLIMAX TOP" (md ~L2315–2391):

- **Climax-top magnitude/velocity:** *"A climax top occurs when the stock price runs up 25 to 50 percent or more over the course of one to three weeks. Some can advance 70 to 80 percent in just 5 or 10 days."* (md L2321; sell-signal list L2361.)
- **Up/down-day count:** *"Look for 70 percent or more up days versus down days over a 7- to 15-day period (example: 7 of 10 days are up)."* … *"once the stock is extended, look for 6 to 10 days of accelerated advance, with only 2 or 3 days being down."* (md L2355.)
- **Last-blast / spread / gaps:** look for the **largest up day and/or widest daily spread since the move began**, plus **recent exhaustion gaps** (md L2355, L2371).
- **Worked examples:** QCOM 1999 +80% in 9 days then +73% in 6 days (+260% in 2 months, then −88%) (md L2323, L2329); TSLA 2014 doubled in 30 days, +51% in 14 days on 3 gaps, 10 of 14 up (md L2345); GMCR 2007 "classic exhaustive sell signals" (md L2389).

**Cross-reference (CORRECTION):** §3e.8 §4.D parabolic detector now has a **Minervini quantitative anchor** (the climax-top thresholds above), in addition to DST D.7 (>7× ADR above 50SMA). The prior disposition ("Minervini provides no quantitative anchor → DST D.7 sole anchor") is **superseded.** §4.D defaults could be re-anchored to the TTLC climax thresholds (25–50%/1–3wk or 70–80%/5–10d; ≥70% up-days over 7–15d; widest-spread + exhaustion-gap) — via §VII.F.

---

## M.6 — Violated MA on volume

**Status:** **UPGRADED BRIEF-MENTION → CONFIRMED-QUALITATIVE-PLUS by TTLC** (specific MA + volume-as-distribution; "heavy" is relative, not a single numeric threshold).

**TTLC verification (2026-06-04):** the **close below the 50-day MA on heavy volume** is an explicitly-listed violation and "an even worse sign" than the 20-day close (md ~L519, L575). During a run-up, *"the day with the heaviest volume … Does the heavy volume come on a down day? If so, then you are seeing large investors liquidating their positions"* (md ~L2375) — heavy down-volume = distribution. So the volume-confirmation principle is doctrine-correct AND tied to a specific MA (50-day); what remains unspecified is a numeric volume multiple ("heavy" is judged relative to the advance).

**Cross-reference:** §3e.8 §4.I (volume-confirmed close-below-MA) — the gate-trichotomy "OUTCOME 2 (qualitative, no threshold)" should be revised: TTLC supplies the **specific MA (50-day) + qualitative heavy-volume** anchor, even if not a numeric multiple. Revisit whether §4.I can now be doctrine-anchored at 50-day-on-heavy-volume rather than parked in the second-source-gate bucket (via §VII.F).

---

## M.7 — Gap-down on news

**Status:** BRIEF-MENTION-NO-DETAIL (both books) — **TTLC frames gap-down as a sizing/risk argument, not a standalone exit trigger.**

**TTLC verification (2026-06-04):** gap-down-on-news appears as (a) **contingency/"disaster plan"** content (*"the stock you bought yesterday is set to gap down huge because the company is being investigated by the SEC…"* — md ~L379) and (b) a **position-sizing rationale**: an overnight 50% gap makes a 5–10% stop "worthless" — *"There is nothing but dead air…"* — so don't overconcentrate (md ~L2193, L1525). No discrete "sell on gap-down-on-news" rule; the doctrine is "size so a gap can't ruin you + have a contingency plan," not a quantified exit.

---

## Additional TTLC sell-side rules now available (beyond the original M.1–M.7 taxonomy)

These surfaced during the 2026-06-04 TTLC review and are candidates for the "Minervini + body-of-knowledge reference review" backlog item:

- **The 50/80 Rule** (TTLC §5, md ~L1271) — late-stage probability heuristic on tops.
- **Breakeven-or-better rule** (TTLC index p.196–197) — quantified version of M.2's breakeven anchor.
- **Staggered stops** + **"adding exposure without adding risk"** (TTLC §3, md ~L897, L937) — exposure/stop management.
- **Reversal recovery vs. violation** distinction (TTLC §1 "SQUATS AND REVERSAL RECOVERIES", md ~L577–597) — give a new position a week or two within stop confines; distinguish recoverable squats from genuine violations.

---

## Footnotes / qualifiers

TLSMW frames sell discipline as a chapter-end aside; **TTLC is the structured sell-side text** (post-breakout violations, climax-top selling, staggered stops, the 50/80 rule). Together the two primary works now give a substantially-complete picture of Minervini sell-side doctrine.

## Usage notes (interpretive — not source)

- **Reference material only.** Do not edit production code to "match" these rules without routing through the research-branch promotion cycle (V2.1 §VII.F source-of-truth correction protocol).
- **2026-06-04 net result of the TTLC verification:** of the seven 3e.8 M-flags — M.2 CONFIRMED (both books, reinforced); **M.3 + M.5 + M.6 upgraded to CONFIRMED-QUANTITATIVE/QUALITATIVE-PLUS** (real Minervini anchors now exist for MA-violation exits and parabolic/climax detection); M.7 BRIEF-MENTION (sizing/risk framing); M.1 retired-as-framed (1.25 → risk-per-trade %); **M.4 NOT-PRESENT in either primary book** (community-attributed 7-week rule unsupported).
- **Disposition reversals to fold into the relevant §3e.8 briefs (each via §VII.F):**
  - **§4.D parabolic detector** — now HAS a Minervini quantitative anchor (TTLC climax-top thresholds); the "DST D.7 is the sole anchor" disposition is superseded.
  - **§4.I volume-confirmed exit** — now has a TTLC anchor (50-day close on heavy volume); reconsider moving it out of the second-source-gate bucket.
  - **exit_below_20ma / exit_below_50ma** — now doctrine-anchored (20-day soon-after-breakout; 50-day-on-volume), with the multi-violation/judgment nuance.
  - **§4.A trail-tightening** — M.2 anchor reinforced by TTLC's "breakeven-or-better rule."
  - **§4.C time-stop** — reinforced ABSENT (no Minervini 7-week rule in either book).
- Rule labels (M.1–M.7) are project-internal taxonomy from the 3e.8 investigation, not Minervini's numbering.
