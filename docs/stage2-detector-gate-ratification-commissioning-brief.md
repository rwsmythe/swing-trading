# Stage-2 detector-gate ratification (8/8 vs 7/8 vs none) — commissioning / scoping brief

> **STATUS: PREPARATION / SCOPING — operator-agreed (2026-06-09), not yet commissioned.** Small,
> well-scoped extension of an existing harness + an operator decision. Research-branch arc; any
> production change to the detector gate routes through the source-of-truth correction protocol
> (V2.1 §VII.F), NOT a direct patch.

**Motivating finding:** the Minervini correct-entry exemplar-recall study
([`research/studies/2026-06-08-minervini-exemplar-recall.md`](../research/studies/2026-06-08-minervini-exemplar-recall.md);
run `exports/research/minervini-exemplar-recall-20260609T021301Z/`) surfaced a concrete asymmetry:
**all 5 detectors hard-gate on `current_stage == "stage_2"`, which requires 8/8 trend-template passes**
(`swing/patterns/foundation.py` `_TREND_TEMPLATE_REQUIRED_PASS_COUNT = 8`) — **stricter than the
aplus bucket**, which treats TT8 (RS rank) as an allowed miss (effectively 7/8 + risk + VCP). The
study quantified the cost and benefit of the gate but **did not measure the obvious middle ground**.

---

## 1. The finding the study left open

In the window-sweep, production-faithful (8/8-TT) VCP detection fires **4/12** vs stage-isolated
**9/12** (Stage-2 delta **+0.42**) — so the 8/8 requirement gates off ~half the VCP geometry fires.
The gate also *provides specificity*: faithful fires on **12.6%** of same-ticker control windows vs
the stage-isolated **79%** (non-specific). **But "stage-isolated" forces Stage-2 unconditionally —
it is "no gate," not "7/8."** The natural middle ground — **7/8 = align the detector gate with the
aplus bucket's TT8-allowed-miss** — is unmeasured. So the deployable question ("is 8/8 the right
detector gate, or should it match the bucket at 7/8?") is currently undecidable from the data.

---

## 2. The arc

A small extension of the existing recall harness:

1. **Add a `7/8` stage variant** to `research/harness/minervini_exemplar_recall/stage_db.py` — a third
   `seed_session` mode where `current_stage` returns `stage_2` iff the **seven non-TT8** trend-template
   gates pass (TT8 excused), mirroring `bucket_for`'s `allowed_miss_names=["TT8_rs_rank"]` semantics.
2. **Re-run** the 27 exemplars + the same-ticker control cohort under **{8/8 faithful, 7/8, none}**.
3. **Emit a recall-vs-specificity table** across the three gate settings: per-detector fired rate
   (exemplars) + control fire rate, both timing modes.
4. **Operator decides** 8/8 vs 7/8 (vs none). If the decision is to change the production detector
   gate, that is a source-of-truth change to `current_stage` / `_TREND_TEMPLATE_REQUIRED_PASS_COUNT`,
   routed through V2.1 §VII.F (a method-record + the correction protocol), NOT a patch.

This is mostly a **measurement + a decision**, not a feature build — lighter than a full copowers
cycle, though the brainstorm sets the depth.

---

## 3. Reuse

The existing recall harness end-to-end: `stage_db` (add one seeding mode), `detector_eval` (already
runs both stage variants — extend to three), the control cohort, the scorecard, the dual-timing
orchestration. New work ≈ one stage-seeding mode + one scorecard column + the re-run.

---

## 4. Open questions for the brainstorm

1. **"7/8" semantics** — exactly the aplus-bucket rule (the 7 non-TT8 gates pass, TT8 excused) vs
   "any 7 of 8." **Recommended: match the bucket** (TT8-excused), since the whole point is gate-vs-
   bucket alignment; "any 7" is a different, weaker question.
2. **Scope of the gate change** — the study's evidence is VCP-dominant (cup/HTF are anchor-mode-
   confounded, dbw/flat are n=2). Is the ratification VCP-scoped, or all 5 detectors (they share
   `current_stage`)? They share the gate, so a change is all-or-nothing unless `current_stage` is
   parameterized.
3. **Decision criterion** — what recall gain at what specificity cost justifies moving 8/8 -> 7/8?
   (e.g. "recover >=X detector recall while keeping control fire-rate <=Y".)
4. **Generalization caveat** — n is small and exemplar-specific; is a same-ticker control sufficient,
   or does the gate decision want a broader (non-exemplar) population before any production change?

---

## 5. Disciplines

- Research carve-out (V2.1 §IV.D/§VII.C); no `swing/` change in the research arc itself.
- **Source-of-truth correction protocol (V2.1 §VII.F)** for any production detector-gate change
  (`current_stage` / `_TREND_TEMPLATE_REQUIRED_PASS_COUNT` are production code).
- Small-n honesty (descriptive; the same caveats as the recall study).
- Note the cup/HTF anchor-mode confound (§12.9 of the recall study) when reading per-class deltas.

---

## 6. Status / dependencies

- **Gating:** none beyond operator scheduling. Depends only on the shipped recall harness.
- **Inputs ready:** the harness, the 27 exemplars + controls, the Tiingo/SPY archive.
- **Relationship to #VII.F:** the arc produces evidence; the gate change (if any) is a separate,
  gated decision.
