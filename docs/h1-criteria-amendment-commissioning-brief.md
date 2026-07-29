# Commissioning Brief — H1 decision-criteria amendment (registry id 1)

**From:** RD (Research Director). **To:** CHARC → the Phase-21 orchestrator.
**Authorized:** operator, in-session 2026-07-29 (criterion text signed off verbatim).
**Governance path:** V2.1 §VII.F source-of-truth amendment via a registry migration — the same route hypothesis 5 took at migration `0026`.
**§3 tripwire:** CROSSES (new migration) → CHARC architecture pass required before dispatch.

---

## §1 What changes — the exact texts

**`hypothesis_registry` id 1 (`A+ baseline`), `decision_criteria`.**

**ORIGINAL (must remain readable in the record — see §3.1):**

```
Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%
```

**AMENDED (operator-approved verbatim 2026-07-29, COHORT clause added at the operator's explicit instruction same day; do not reword):**

```
Mean R-multiple > 0 across the 20 closed labeled trades, AND no single trade
contributes 50% or more of gross profit (gross profit = sum of positive
R-multiples). COHORT: the 20 are STANDARD-intent trades only, per the
2026-06-10 training-epoch declaration; pre-epoch hypothesis_test_by_design
trades are settled tuition and do NOT count toward the 20. If the cohort has
no winners, the mean-R criterion fails and the decision is negative. Win rate
and its Wilson lower bound are REPORTED as diagnostics alongside median R and
top-3 concentration, but do not gate the decision.
```

**The line wrapping above is markdown presentation, NOT part of the criterion** (RD ruling 2026-07-29, answering CHARC's authoring question). The criterion is STORED AS A SINGLE LINE — wrap points become single spaces — matching the form of the `0008` value it replaces and the `0026` house style; no `decision_criteria` value in the registry has ever carried an embedded newline. The canonical stored bytes are pinned in §5.1.

Nothing else on the row changes — not `statement`, not `target_sample_size` (stays 20), not `status`.

## §2 Why, and why NOW rather than later

**The frozen win-rate leg is mis-calibrated for this style of system.** Wilson-LB > 30% at n=20 requires **11 wins of 20 — a 55% raw win rate**. 10/20 (50%) yields a 29.9% lower bound and fails by 0.1 points. Nothing this program has measured approaches 55%: broad-watch runs 22.1% (n=312), the A+ shadow closed cohort is 0/2, the live A+ cohort is 2/2 at n=2 (both scratches, statistically meaningless). Typical breakout/trend systems run 35–50%. **As written, H1 would likely REJECT a genuinely profitable trend-following system** — the criterion's failure mode is a false negative on success.

**Win rate is also the wrong instrument on its own terms:** it is manipulable by exit policy (move the target nearer, the stop further, and win rate rises while expectancy falls), whereas mean R prices both legs and cannot be gamed that way. Win rate can therefore move *opposite* to edge.

**But the win-rate floor was doing a real job** — guarding the mean-R claim against a single outlier at small n. That job is retained, not removed: the concentration cap replaces a mis-calibrated guard with a better-calibrated one. **This is not a loosening.**

**The guard was chosen by stress test, not intuition.** RD's first proposal (leave-one-out: "mean R stays > 0 with the largest winner removed") was tested and REJECTED — it fails a genuinely profitable trend shape (30% win rate, +0.45 mean R, one 10R winner → LOO-mean −0.05), reproducing the exact fat-tail penalty that disqualifies the Wilson floor. The concentration cap passes every test case correctly:

| 20-trade shape | Mean R | Leave-one-out | Top-1 share (adopted) |
|---|---|---|---|
| One lucky trade (must catch) | +0.30 | FAIL ✓ | 100% → FAIL ✓ |
| Distributed edge, 40% win | +0.35 | PASS ✓ | 21% → PASS ✓ |
| Real trend shape, fat tail | +0.45 | **FAIL ✗** | 43% → PASS ✓ |
| Marginal, one 8R carrying it | +0.05 | FAIL ✓ | 50% → FAIL ✓ |

**WHY NOW IS THE ONLY CLEAN WINDOW.** The honest test for criterion-shopping is whether a change is motivated by the outcome. **H1 currently has 2 closed standard-epoch trades and no signal.** The motivation here is the criterion's own arithmetic — equally true whether H1 is destined to pass or fail. That is unimpeachable today and indefensible in six months with 20 trades on the table, regardless of how good the reasoning is. The window is open *because* nobody knows the answer, and it closes as the data arrives.

## §3 Binding requirements

### §3.1 NON-NEGOTIABLE — the original criterion must remain readable in the record
Overwriting `decision_criteria` in place without preserving the original would destroy the evidence of what was pre-registered, defeating the entire purpose of pre-registration. **Mechanism is CHARC's call.** Any mechanism that preserves the original verbatim and machine-readably is acceptable. Preservation itself is not optional.

**SHIPPING MECHANISM (CHARC §3 pass, `d2412651` — binding mechanics live in [`docs/h1-criteria-amendment-charc-section3-pass.md`](h1-criteria-amendment-charc-section3-pass.md), not here):** one additive nullable column `preregistered_decision_criteria` holds the `0008` line-52 original verbatim on the `A+ baseline` row only; NULL on ids 2–5, with NULL DEFINED in the migration header as *never-amended* rather than *unknown*. The original also remains unconditionally preserved at `0008` line 52, which no runtime path can touch.

### §3.2 Its OWN migration, not bundled
The amendment takes its own migration number (**next free at authoring time** — do NOT assume; `0032` is taken by 21-A and 21-B carries one of its own). Rationale: a governance amendment to a pre-registered decision rule must be independently auditable in migration history, not buried inside a feature migration.

### §3.3 Additive only — no destructive change
A registry-row UPDATE in the shape of `0026` (which INSERTed hypothesis 5), **plus the one additive `ALTER TABLE ADD COLUMN` the §3.1 preservation mechanism requires**. Nothing is dropped, narrowed, or rewritten in place. The standard backup gate and version-bump discipline apply as for any migration. **Same-commit consequence (CHARC §3 pass):** `tests/data/test_db_v8.py` asserts the `hypothesis_registry` column set with EXACT set equality and fails on any added column — it is updated in the same commit.

## §4 Scope bounds — what this does NOT touch

- **H2, H3, H4** — none gate on Wilson; unchanged.
- **H5 (broad-watch)** — REPORTS Wilson LB across censoring scenarios; it is a reported statistic there, not a gate. Unchanged.
- **`target_sample_size`** stays 20. Whether n=20 is large enough is a SEPARATE question, flagged not bundled (§6).
- **The training-epoch contract** is untouched — the COHORT clause CITES it as the governing doctrine, it does not modify it (§6).
- No change to how R is computed, to the shadow engine, or to any measurement path.

## §5 Verification / acceptance

1. `hypothesis_registry` id 1 `decision_criteria` reads the §1 amended text **as a single line** (wrap points → single spaces), INCLUDING the COHORT clause. **Canonical referent, so the test is falsifiable: length 577, `sha256 = 6bdd723ce8a8ea1d00b8dbcfa7b50ec056a6282ee3a5110990b2f0894b7b3e73`.** Assert the digest or exact-string equality — NOT "matches §1", which is a wrapped rendering and cannot adjudicate whitespace.
2. The ORIGINAL text is recoverable verbatim from the row via `preregistered_decision_criteria` (§3.1).
3. `statement`, `target_sample_size`, `status` unchanged; ids 2–5 untouched (their `preregistered_decision_criteria` is NULL = never-amended, per the migration header definition).
4. Migration is ADDITIVE only — the single new nullable column and nothing else; no table dropped, no column narrowed or rewritten; backup gate fired; `tests/data/test_db_v8.py` updated in the same commit.
5. RD merge-blocking QA: RD reads the live row post-migration and confirms 1–3 himself.
6. **D29 (CARRIED, not closed by this migration):** the cohort READERS omit the `entry_intent` filter the amended criterion names — `swing/metrics/cohort.py:37`/`:105` carry the predicate; `swing/metrics/tier.py:616` and `swing/web/view_models/metrics/hypothesis_progress_card.py:317` call without it, so the tool counts 3 where the criterion counts 2. RD-verified on disk 2026-07-29. It is a measurement-path change, excluded from §4 scope, and does NOT ride this migration (§3.2's independent-auditability rule). RD's QA records it CARRIED with a named owner — silence is not an option.

## §6 What this amendment does NOT establish — stated in advance, deliberately

**It does not make H1 statistically conclusive.** At n=20 with fat-tailed returns, **no** criterion can establish confident positive expectancy — the Wilson floor could not either; it merely failed differently. The amended criterion establishes the *direction* of expectancy on 20 real trades with a guard against one-trade dominance. That is a weaker claim than statistical confidence, and it is stated here so a future reader (including a future RD) does not over-read a pass.

Levers for a genuinely confident H1 claim, **flagged not bundled**: a larger `target_sample_size`, or corroboration from the A+ shadow cohort, which accrues at signal-pace rather than trade-pace. Both are separate operator decisions.

**COHORT QUESTION — RESOLVED by the operator 2026-07-29: the clarifying clause is IN (see §1).** The criterion previously said "20 closed labeled trades" without pinning the cohort; the 2026-06-10 training-epoch declaration settles it (pre-epoch trades are tuition, never re-read as practice; the `standard` cohort starts empty at the epoch) but the criterion text was silent. The operator instructed the clause be added while the row is open.

**Verified live 2026-07-29 — the clause changes a real count, it is not decorative.** Three trades carry the `A+ baseline (aplus)` label: **YOU** (2026-05-04, `hypothesis_test_by_design`, pre-epoch → EXCLUDED), **VSTS** (2026-06-25, `standard`), **AMN** (2026-07-01, `standard`). Without the clause a reader could count 3/20; with it, **H1 stands at 2/20**. The acceptance check in §5 must confirm the clause is present byte-for-byte.
