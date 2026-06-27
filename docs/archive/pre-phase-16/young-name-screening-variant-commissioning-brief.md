# Young-name (sub-221-bar) screening variant — commissioning / scoping brief

> **STATUS: PREPARATION / SCOPING — operator-agreed (2026-06-09), not yet commissioned.** This brief
> scopes the arc so a future copowers cycle (brainstorm -> writing-plans -> executing-plans) starts
> clean. Research-branch arc (artifacts under `research/`; deployable findings route through the
> source-of-truth correction protocol, NOT a direct patch).

**Motivating finding:** the Minervini correct-entry exemplar-recall study
([`research/studies/2026-06-08-minervini-exemplar-recall.md`](../research/studies/2026-06-08-minervini-exemplar-recall.md);
run `exports/research/minervini-exemplar-recall-20260609T021301Z/`). **7 of 27** curated exemplars
are `skip_insufficient_history` in BOTH timing modes — structurally un-screenable because they had
**< ~221 trading days** of history at entry (`SCREENABLE_FLOOR = 200 + rising_ma_period_days`). They
were **newly public**: QSII, JNPR, AMZN-1997, MELI, BODY (+2). No data source or threshold tuning
closes this — the Trend Template needs SMA200 + a 200MA-rising window, which a young stock simply
does not have. **Minervini explicitly buys young post-IPO leaders** (TWoSMW Ch.11 "primary base" /
"IPO base"); three of our `unmapped` exemplars (AMZN-1997, JNPR, YHOO) are exactly these. So this is
a real, irreducible gap in the codified screen, not a data artifact.

---

## 1. The question

Can we define a **young-name screening variant** — an alternative gate applied to sub-`SCREENABLE_FLOOR`
names that the Trend Template cannot evaluate — that **surfaces these documented young-leader entries
(recall)** WITHOUT firing indiscriminately (precision/specificity)? A pass = a young-name gate that
catches the 7 (+ the young `unmapped` names) while staying selective against random young-name
windows.

This is **recall-motivated** (the recall study localized the exact gap) and **complementary** to the
expectancy track. Any gate that emerges is a candidate **new production screening path** for young
names — routed through V2.1 §VII.F, not patched directly.

---

## 2. Decomposition

| Piece | Content |
|---|---|
| **Cohort** | The sub-floor exemplars (the 7 `skip_insufficient_history` + the young `unmapped` names). The recall harness ALREADY isolates them via the `skip_insufficient_history` taxonomy. Consider extracting more young-name Minervini examples from the corpus to grow n past ~7-10 (n is the binding constraint on any claim). |
| **Gate candidate(s)** | The brainstorm's core. Options to weigh: (a) **scaled-MA Trend Template** — SMA20/50/100 in place of 150/200, gated on available history; (b) **Minervini's documented young-name methodology** — IPO-base / first-base / primary-base structure (TWoSMW Ch.11, in the transcribed corpus); (c) a **since-IPO-high / % above the post-IPO base** criterion; (d) RS via the SPY-relative `fallback_spy` proxy (already built in the recall harness). A shorter-window **structural-stage** definition is needed too (`structural_stage` also needs 200 bars). |
| **Recall measurement** | Reuse the recall harness; add a young-name screen path for sub-floor names; measure whether it surfaces the cohort, in both timing modes. |
| **Precision/specificity** | Reuse the same-ticker negative-control machinery (random young-name / sub-floor windows): does the gate fire everywhere? A young-name gate that admits everything is worthless. |

---

## 3. Reuse

- **Recall harness** `research/harness/minervini_exemplar_recall/` — the `skip_insufficient_history`
  taxonomy, the Tiingo reader, the SPY-relative RS proxy, the same-ticker control cohort, the Wilson/
  stratified scorecard, the dual-timing orchestration are all directly reusable. The new work is the
  **young-name gate definition** + a scorecard surface for it.
- The transcribed book corpus (`reference/books-corpus-index.md`) for Minervini's young-name
  methodology (the design input for the gate candidates).

---

## 4. Open questions for the brainstorm

1. **Gate definition** — which of the §2 candidates (or a composite)? Grounded in Minervini's own
   young-name framing, not invented.
2. **The young-name structural-stage** — `structural_stage`/`current_stage` need 200 bars; define a
   shorter-window Stage-2 analogue for young names (and decide whether H2 detectors should consume it).
3. **Cohort size** — ship at n≈7-10 (descriptive/exploratory) or first extract more young-name
   exemplars from the corpus to firm up the claim?
4. **Deployment shape** — is the young-name gate a *parallel* screen (a separate bucket path for
   sub-floor names) or a *modification* of the existing TT path? (Affects the §VII.F change surface.)
5. **Precision bar** — what control false-fire rate makes a young-name gate "selective enough"?

---

## 5. Disciplines

- Research carve-out (V2.1 §IV.D/§VII.C): artifacts under `research/`; ≤1 CLI registration if any.
- Strict point-in-time / no-lookahead (the recall harness's `<=asof_date` slice contract).
- **Source-of-truth correction protocol (V2.1 §VII.F)** — any deployable young-name screen routes
  through it.
- Small-n honesty: descriptive + Wilson, no inferential claim (mirror the recall study).
- #29 historical depth (the cohort is precisely the shallow-history names).

---

## 6. Status / dependencies

- **Gating:** none beyond operator scheduling (not temporal-log-gated; uses Minervini ground truth).
- **Inputs ready:** the recall harness + the isolated young-name cohort + the corpus.
- **Prep before commissioning (optional):** extract additional young-name exemplars to grow n.
