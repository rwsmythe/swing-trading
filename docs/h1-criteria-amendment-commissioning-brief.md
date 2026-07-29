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

**AMENDED (operator-approved verbatim 2026-07-29; do not reword):**

```
Mean R-multiple > 0 across the 20 closed labeled trades, AND no single trade
contributes 50% or more of gross profit (gross profit = sum of positive
R-multiples). If the cohort has no winners, the mean-R criterion fails and the
decision is negative. Win rate and its Wilson lower bound are REPORTED as
diagnostics alongside median R and top-3 concentration, but do not gate the
decision.
```

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
Overwriting `decision_criteria` in place without preserving the original would destroy the evidence of what was pre-registered, defeating the entire purpose of pre-registration. **Mechanism is CHARC's call**; the cheapest path in the current schema is `status_change_reason` carrying the original text verbatim plus the amendment rationale and date, with `status_changed_at` stamped. Any mechanism that preserves the original verbatim and machine-readably is acceptable. Preservation itself is not optional.

### §3.2 Its OWN migration, not bundled
The amendment takes its own migration number (**next free at authoring time** — do NOT assume; `0032` is taken by 21-A and 21-B carries one of its own). Rationale: a governance amendment to a pre-registered decision rule must be independently auditable in migration history, not buried inside a feature migration.

### §3.3 Data-only, additive
This is a registry-row UPDATE in the shape of `0026` (which INSERTed hypothesis 5). No table/column changes. The standard backup gate and version-bump discipline apply as for any migration.

## §4 Scope bounds — what this does NOT touch

- **H2, H3, H4** — none gate on Wilson; unchanged.
- **H5 (broad-watch)** — REPORTS Wilson LB across censoring scenarios; it is a reported statistic there, not a gate. Unchanged.
- **`target_sample_size`** stays 20. Whether n=20 is large enough is a SEPARATE question (§6).
- **The training-epoch contract** is untouched (see the open question in §6).
- No change to how R is computed, to the shadow engine, or to any measurement path.

## §5 Verification / acceptance

1. `hypothesis_registry` id 1 `decision_criteria` reads the §1 amended text byte-for-byte.
2. The ORIGINAL text is recoverable verbatim from the row (§3.1).
3. `statement`, `target_sample_size`, `status` unchanged; ids 2–5 untouched.
4. Migration is data-only; schema tables/columns unchanged; backup gate fired.
5. RD merge-blocking QA: RD reads the live row post-migration and confirms 1–3 himself.

## §6 What this amendment does NOT establish — stated in advance, deliberately

**It does not make H1 statistically conclusive.** At n=20 with fat-tailed returns, **no** criterion can establish confident positive expectancy — the Wilson floor could not either; it merely failed differently. The amended criterion establishes the *direction* of expectancy on 20 real trades with a guard against one-trade dominance. That is a weaker claim than statistical confidence, and it is stated here so a future reader (including a future RD) does not over-read a pass.

Levers for a genuinely confident H1 claim, **flagged not bundled**: a larger `target_sample_size`, or corroboration from the A+ shadow cohort, which accrues at signal-pace rather than trade-pace. Both are separate operator decisions.

**OPEN QUESTION FOR THE OPERATOR (not in the signed text; do not fold in without his word).** The criterion says "20 closed labeled trades" without pinning the cohort. The 2026-06-10 training-epoch declaration already settles it — the 16 pre-epoch trades are tuition, never re-read as practice, and the `standard` cohort starts empty at the epoch — so H1 should count **standard-epoch closed trades only** (currently 2, plus one pre-epoch `by_design` A+ trade that must NOT count). The doctrine is settled; the criterion text is silent. The operator may wish to add one clarifying clause pinning it while the row is open, or leave it to the epoch contract. **RD flags; the operator decides; this brief does not assume.**
