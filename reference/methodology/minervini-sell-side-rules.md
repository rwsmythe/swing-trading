# Minervini SEPA Sell-side Rules

**Source:** *Trade Like a Stock Market Wizard*, Mark Minervini, McGraw Hill 2013 (TLSMW; physical copy).
**Reviewed:** 2026-05-10 by Reid Smythe.
**Status:** ~ PARTIAL — 1/7 rules CONFIRMED-with-quantitative-anchor; 5/7 rules BRIEF-MENTION-OR-ABSENT in TLSMW; 1/7 rule NOT-PRESENT-IN-AVAILABLE-SOURCES.

---

## Provenance + scope

This file captures operator's review of *Trade Like a Stock Market Wizard* (TLSMW, 2013) for sell-side content. Operator finding 2026-05-10: TLSMW is **primarily an entry-side text** (the trend-template, VCP, RS, leadership, fundamentals). Sell-side content is sparse — only "sell into strength" (M.2 in Ch 13 "Selling at a Profit") gets dedicated discussion. Other sell-side topics get brief mentions without quantitative detail.

**Other Minervini works (NOT available to operator per CLAUDE.md memory + 2026-05-10 confirmation):**
- *Think & Trade Like a Champion* (2017) — anecdotally where the 7-week rule (M.4) and more sell-side specifics appear
- *Mindset Secrets for Winning* (2019)

These books are **NOT-AVAILABLE** for verification. Rules attributed to Minervini that don't appear in TLSMW remain `[UNVERIFIED]` against the source CLAUDE.md auto-memory designates — they are unverifiable for now (not "pending check"). Operator may revisit if they acquire the second/third books.

**Implication for 3e.8 §6.4 [UNVERIFIED] M-flag triage:** the 3e.8 investigation cited "M.x" rules as Minervini doctrine without specifying which Minervini work. Some claims (especially M.4 7-week rule + M.5 parabolic thresholds + M.6 volume-confirmed-close) may be from the unavailable Think & Trade or from secondhand community paraphrase rather than from TLSMW directly. Where TLSMW is silent AND no other source is available, those rules remain unverifiable.

For each rule below, status is one of:
- **CONFIRMED-QUANTITATIVE** — TLSMW provides a specific quantitative anchor
- **CONFIRMED-QUALITATIVE** — TLSMW articulates the principle without specific thresholds
- **BRIEF-MENTION-NO-DETAIL** — TLSMW touches on the topic but provides no actionable specifics
- **NOT-PRESENT-IN-AVAILABLE-SOURCES** — absent from TLSMW; verification source not available to operator

---

## M.1 — 1.25× backstop expectancy heuristic

**Source citation:** TLSMW — BRIEF-MENTION-NO-DETAIL or NOT-PRESENT per operator review 2026-05-10.

**Status:** NOT-PRESENT-IN-AVAILABLE-SOURCES — TLSMW does not contain a specific 1.25× backstop expectancy figure. Likely community-derived or from another Minervini work.

**Operator notes:** The 3e.8 investigation cited a "1.25× backstop expectancy heuristic" as Minervini doctrine. TLSMW discusses expectancy generally but no specific 1.25× figure was found. Provenance unknown.

---

## M.2 — Sell into strength

**Source citation:** TLSMW Ch 13, p. 296, "Selling at a Profit" section.

**Status:** CONFIRMED-QUANTITATIVE — TLSMW articulates a quantitative R-multiple-of-stop-loss anchor PLUS a qualitative selling-into-strength principle.

**Transcription (verbatim):**

> Selling at a Profit
>
> Once a stock amasses a percentage gain that is a multiple of your stop loss, you should rarely allow that position to turn into a loss. For instance, let's say your stop loss is set at 7 percent. If you have a 20 percent gain in a stock, you shouldn't allow that position to give up all that profit and produce a loss. To guard against that, you could move up your stop loss to breakeven or trail a stop to lock in the majority of the gain. You may feel foolish breaking even on a position that was previously a decent gain; however, you will feel even worse if you let a nice gain turn into a loss.
>     At some point you have to close out a trade. There are two ways you can sell:
>     
>     -Into strength, which means cashing out shares while the share price is rising
>     -Into weakness, which means selling while the share price is declining
>     
>     Selling into strength is a learned practice of professional traders. It's important to recognize when a stock is running up rapidly and may be exhausting itself. You can unload your position easily when buyers are plentiful. Or you could sell into the first signs of weakness immediately after such a price run has broken down. You need to have a plan for both selling into strength and selling into weakness.

**Operator notes (operator-supplied):** No specifics provided, just general strategies for ensuring a profit does not turn into a loss.

**Orchestrator interpretation (additional):** the quote ACTUALLY contains TWO anchors:

1. **Quantitative R-multiple anchor (operationally significant):** "Once a stock amasses a percentage gain that is a multiple of your stop loss" → in the framework's R-multiple terms, this is "once `r_so_far` ≥ K" (where K is the multiple). The 7%/20% example = 20/7 = ~2.86R. The principle: **at some R-multiple of stop loss, never let the position turn into a loss.** Recommended action: move stop to breakeven OR trail to lock in majority of gain.

2. **Qualitative selling-into-strength principle:** match what operator described — directional discipline + recognition of exhaustion + having a plan for both strength + weakness exits.

**Critical implication for §3e.8 §4.B vs §4.A:** M.2's recommended ACTION is **stop-tightening (breakeven or trail)**, NOT trim-into-strength (the §3e.8 §4.B framing). M.2 is therefore a doctrine anchor for **§3e.8 §4.A** (trail-MA tightening), NOT for §4.B (trim). The two recommendations actually address different doctrinal threads:
- M.2 quantitative anchor → §4.A trail-tightening (breakeven-once-multiple-of-stop-reached)
- DST D.2 qualitative trim discipline → §4.B trim-into-strength

The 3e.8 investigation conflated these by framing both under "sell-into-strength." Worth re-examining the §4.A and §4.B implementation briefs separately.

**Cross-reference:** §3e.8 §4.A (trail-MA gating; deferred) AND §4.B (trim/sell-into-strength advisory; commissioned in implementation bundle 2). M.2 strengthens the doctrinal basis for an §4.A-equivalent rule that triggers stop-tightening when `r_so_far ≥ K` (some configurable R-multiple, e.g., 2R or 3R per the TLSMW example).

---

## M.3 — Sell on close below N-day MA (specific N values)

**Source citation:** TLSMW — BRIEF-MENTION-NO-DETAIL per operator review 2026-05-10.

**Status:** BRIEF-MENTION-NO-DETAIL — TLSMW emphasizes moving averages on the entry side (50/150/200 day per the trend-template). Sell-side use of MAs is implied by the trend-template's definition of uptrend but not given as a specific sell-rule with thresholds.

**Operator notes:** No quantitative threshold or specific MA-period sell-rule found in TLSMW. May be in unavailable Think & Trade.

**Cross-reference:** Existing framework rules `exit_below_10ma` / `exit_below_20ma` / `exit_below_50ma` are operator-policy choices, not directly TLSMW-anchored. DST D.3 (10DSMA primary trail per peoplewish/Qullamaggie) is the closest doctrine anchor; it covers 10/20/50 by stock-speed.

---

## M.4 — 7-week rule (time-stop)

**Source citation:** TLSMW — NOT-PRESENT per operator review 2026-05-10. **Likely in Think & Trade Like a Champion (2017), but that book is NOT AVAILABLE to operator** per CLAUDE.md memory + 2026-05-10 confirmation.

**Status:** NOT-PRESENT-IN-AVAILABLE-SOURCES — confirmed absent from TLSMW; secondary verification source not available.

**Operator notes:** 7-week / 49-day time-stop rule is widely community-attributed to Minervini but does not appear in TLSMW. Without Think & Trade, this rule remains unverifiable from Minervini sources.

**Cross-reference:** §3e.8 §4.C / §4.C.bis (time-stop discipline) deferral is REINFORCED — neither TLSMW nor DST contains a time-stop rule. The sole remaining doctrine source for time-stop is Qullamaggie's Q.1 (3-5 day window), which is much more aggressive than the 10-day framework default. Without Minervini's 7-week rule confirmed, the doctrine landscape on time-stops favors the AGGRESSIVE end (Q.1 3-5 day) — operator may want to reconsider whether the 10-day default is too lenient rather than too aggressive.

---

## M.5 — Parabolic / blow-off-top extension thresholds

**Source citation:** TLSMW — BRIEF-MENTION-NO-DETAIL per operator review 2026-05-10.

**Status:** BRIEF-MENTION-NO-DETAIL — TLSMW discusses parabolic / blow-off-top patterns as recognizable end-of-move signals; per operator review, no specific quantitative thresholds (e.g., "X% in Y days" or "above N×ATR from the MA") were found. Recognition of parabolic is treated as a chart-pattern recognition skill, not a quantitative trigger.

**Operator notes:** No specific N/M/K thresholds in TLSMW for parabolic detection.

**Cross-reference:** §3e.8 §4.D (parabolic-extension detector) commissioned in implementation bundle 2. The doctrinal anchor for §4.D's quantitative thresholds is **DST D.7** (Realsimpleariel's >7x ADR above 50SMA) — NOT Minervini. Worth re-anchoring §4.D's defaults in the implementation brief from arbitrary 25%/5d/15% to D.7's >7x ADR above 50SMA framework.

---

## M.6 — Violated MA on volume

**Source citation:** TLSMW — BRIEF-MENTION-NO-DETAIL per operator review 2026-05-10.

**Status:** BRIEF-MENTION-NO-DETAIL — TLSMW emphasizes volume confirmation generally (heavy volume on breakout = strength; heavy volume on breakdown = weakness) but per operator review, no specific quantitative volume threshold for the close-below-MA case was found. The volume-as-confirmation principle is doctrine-correct; the specific threshold is not specified.

**Operator notes:** Qualitative volume principle present; no quantitative threshold.

**Cross-reference:** §3e.8 §4.I (volume-confirmed close-below-MA overlay) deferred-with-§4.G-completion-gate-trichotomy. **Trichotomy resolves to OUTCOME 2 (qualitative without threshold → escalate to second-source gate).** §4.I now joins §4.H + §4.J in the second-source-gate bucket — revisit only if a doctrine-confluent volume-threshold rule surfaces from another doctrine source.

---

## M.7 — Gap-down on news

**Source citation:** TLSMW — BRIEF-MENTION-NO-DETAIL per operator review 2026-05-10.

**Status:** BRIEF-MENTION-NO-DETAIL — TLSMW discusses gap risk and news-driven moves generally but per operator review, no specific gap-down-on-news exit rule was articulated as a standalone discipline.

**Operator notes:** No standalone gap-down-on-news rule in TLSMW.

---

## Footnotes / qualifiers (as printed)

TLSMW frames sell discipline as a chapter-end aside (Ch 13 "Selling at a Profit") rather than a structured rule set. The book's primary contribution is the entry-side framework (trend-template + VCP + leadership). Sell-side material is treated as "the other half of the equation" but with significantly less detail than the buy-side.

---

## Usage notes (not from source — interpretive)

- This file is **reference material only**. Do not edit production code to "match" the rules above without routing the change through the research-branch promotion cycle per V2 Addendum Addition 2 (source-of-truth correction protocol).
- Of the seven 3e.8 M-flag claims: only M.2 (sell-into-strength) is CONFIRMED-QUANTITATIVE in TLSMW; M.3, M.5, M.6, M.7 are BRIEF-MENTION-NO-DETAIL; M.1 + M.4 are NOT-PRESENT-IN-AVAILABLE-SOURCES. Verification of M.1 + M.4 (and possible additional detail on M.3/M.5/M.6/M.7) would require Think & Trade Like a Champion, which is NOT available to operator.
- The 3e.8 investigation's "M.x" attributions appear to have conflated TLSMW + likely Think & Trade and possibly community paraphrase. The disposition above represents the maximum verification possible from sources currently available.
- **Operationally-significant disposition reinforcements** from this round:
  - **§4.A trail-tightening doctrine anchor STRENGTHENED** — M.2's quantitative R-multiple-of-stop-loss anchor ("once gain is a multiple of stop loss, never let position turn into a loss; move stop to breakeven OR trail") is a doctrine basis for §4.A. The 3e.8 framing of §4.A as "trail-MA SUPPRESSION based on maturity_stage" is operationally equivalent to M.2 only via project-policy interpretation; a more doctrine-faithful framing would be "tighten stop (breakeven or trail) when r_so_far reaches a configurable R-multiple threshold." Worth re-thinking §4.A's mechanism.
  - **§4.B trim doctrine anchor REMAINS DST-only** — M.2 articulates the principle qualitatively but its recommended action is stop-tightening, NOT trim. DST D.2 (50% on Day 3-5) is the sole quantitative trim anchor. The 3e.8 §4.B's R-multiple-trigger + 25%-trim default is operator-policy hybrid; consider switching to DST D.2-faithful Day-3-5 50% trigger OR keeping the 3e.8 hybrid but acknowledging it's not directly doctrine-anchored.
  - **§4.C / §4.C.bis time-stop deferral REINFORCED** — TLSMW has no time-stop; DST has no time-stop; M.4 7-week unverifiable. Only Q.1 (3-5 day, AGGRESSIVE) remains as anchor. If operator wants to commission a default change, the Q.1 anchor would TIGHTEN the default (e.g., from 10-day to 5-day), not loosen it. Worth re-thinking the 3e.8 §3.C "framework default 10/0.5 may be too aggressive" framing — with M.4 NOT-PRESENT, the doctrine landscape suggests the OPPOSITE direction.
  - **§4.D parabolic detector defaults** — Minervini provides no quantitative anchor; DST D.7 (>7x ADR above 50SMA per Realsimpleariel) becomes the sole doctrine anchor. Worth re-anchoring §4.D defaults in implementation brief from arbitrary 25%/5d/15% to D.7's >7x ADR above 50SMA framework.
  - **§4.I volume-confirmed exit gate-trichotomy resolves to OUTCOME 2** — M.6 qualitative without threshold → escalate to second-source gate. §4.I now in same bucket as §4.H + §4.J.
- Status flips from `~ PARTIAL` to `✓ COMPLETE` only if operator extends transcription to other Minervini works (or explicitly closes the M-rule set with TLSMW-only as the ground-truth surface).
- Rule labels (M.1-M.7) are project-internal taxonomy from the 3e.8 investigation, not Minervini's own numbering.
