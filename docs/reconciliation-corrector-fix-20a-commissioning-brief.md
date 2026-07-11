# Commissioning Brief — 20-A: fix the tier-1 corrector, then correct the data (D25)

**From:** CHARC. **To:** the Phase-20 orchestrator. **Arc:** 20-A ([`phase20-scope-charc.md`](phase20-scope-charc.md), the opener). **Committed:** 2026-07-11 (evening HST 07-10). **Deadline: COMPLETE before Monday's open (operator)**; the corrected values must exist before RD's August monthly read.
**§3 verdict: CARVE-OUT tripwire (`swing/trades/` — `reconciliation_classifier.py` + `reconciliation_auto_correct.py`, + the void mechanism's touchpoints) → this brief embeds the CHARC architecture pass; conditions A1–A5 + the SCHEMA-STOP are BINDING.** NO new module/dependency/standing process expected; **NO schema (v31) — see the STOP clause.**

## §0 References (the evidence base — all broker-verified 2026-07-10/11)

- **[`broker-ledger-forensic-reconciliation-2026-07-10.md`](broker-ledger-forensic-reconciliation-2026-07-10.md)** — the complete to-the-cent reconciliation, the three corrupted fills, the PINNED mechanism, the safeguard fix-list. THE founding artifact; read in full.
- **The corrector's confession rows** (`reconciliation_corrections`): #28 (05-21, PTEN entry fill 17: `13.00→12.305` auto — overwrote a CORRECT price with the exit leg's) · #30 (06-03, DFTX entry fill 28: `24.53→22.16` auto — same) · #33 (07-08, AMN trim fill 37: `35.75→35.65` auto — CORRECT) · **#34 (07-10, fill 37: `35.65→32.06` auto — RE-FIRED over its own correct fix with the 07-09 stop leg's price)**. The precedent rows #3/#4/#6 (05-17) are the operator manually overriding this same matcher class before tier-1 removed the human.
- **Code loci:** `swing/trades/reconciliation_classifier.py` (`_classify_entry_price_mismatch` :348; `_compute_execution_price` ~:100; the tier-1 multi-leg resolution :309-328 — pure function, no I/O) · `swing/trades/reconciliation_auto_correct.py` (the tier-1 apply service; sandbox-gated; SAVEPOINT-per-discrepancy discipline per CLAUDE.md) · the append-only `reconciliation_corrections` contract (INSERT + supersede-chain, never UPDATE-in-place).
- **Broker-true values:** PTEN entry 15@13.00 (−195.00) · DFTX entry 7@24.53 (−171.71) · AMN 07-07 trim 3@35.65 (+106.95). AMN true realized +$1.17 (recorded −$9.60). SATL trade 11 = phantom (no broker execution).
- **Trade-state CHECK enum** (`0014_…​.sql:139` + `state.py:136`): `('entered','managing','partial_exited','closed','reviewed')` — **no 'voided'**.
- RD's rulings (thread `phase20-scoping` 09:12Z + 09:18Z): the SATL void SEMANTIC; the ordering constraint; the witnessed re-derivation.

## §1 The pinned failure (what Half A must make impossible)

The fill→execution matcher, facing **two same-ticker SAME-QUANTITY executions** (every normal single-entry/single-exit round trip produces exactly this), selects the wrong leg — with **no side discrimination** (SELL executions corrected BUY entry fills), **no date-proximity check** (the AMN 07-07 fill matched the 07-09 execution), and **tier-1 auto-apply on what is actually an ambiguous match**. Once corrupted, later runs compare against the same mis-match → self-sealing. #34 proves it re-fires over correct values.

## §2 Requirements

### Half A — the corrector (MERGES FIRST — see the ORDER constraint)
1. **A1 — Ambiguity demotion:** ≥2 candidate executions matching a fill (same ticker + qty within the compare window) = AMBIGUITY → tier-2 (the existing choice-menu machinery), NEVER tier-1 auto-apply. This is the classifier's own stated philosophy applied to the matcher.
2. **A2 — Plausibility guards** on any tier-1 fill-price auto-correction (each independently sufficient to demote to tier-2): execution SIDE must match the fill's action (buy↔entry; sell↔exit/trim/stop) · execution date within 1 session of the fill's date · overwrite magnitude ≤ a % band (plan proposes the band from the live fill distribution; RD rules).
3. **A3 — Re-correction alarm:** a tier-1 auto-correction targeting a fill that ALREADY has an `auto_applied` correction, proposing a DIFFERENT value, is BLOCKED → emitted as a material tier-2 discrepancy ("canonical value changed — contradiction"). Makes #34 structurally impossible.
4. **A4 — fills↔trades consistency invariant:** a recon check that the entry-fill price agrees with `trades.entry_price` (tolerance = display precision); divergence emits a material discrepancy. (The corrector itself created this divergence on PTEN/DFTX and nothing noticed for six weeks.)

### Half B — the data (AFTER Half A is merged, or atomically with it)
5. **B1 — the 3 fill corrections** through the SUPPORTED audited operator-override path (the corrections #3/#4/#6 precedent shape: `operator_overridden`, `operator_truth_value_json`, reason citing the forensic doc + broker statement): fill 17 → 13.00 · fill 28 → 24.53 · fill 37 → 35.65. Append-only chain discipline (supersede, never mutate).
6. **B2 — SATL trade-11 VOID per RD's SEMANTIC:** excluded from ALL cohorts and stats, preserved as an audit-visible voided/test row — **NEVER raw-delete** (the D19 doctrine). Mechanism = the plan's design (**SCHEMA-STOP: the state CHECK enum has no 'voided' — prefer a no-schema mechanism** (e.g. an audited correction-row annotation + a central exclusion predicate all cohort/stat readers use); if the plan concludes a CHECK widening or new column is genuinely required, STOP and route to CHARC — do not self-certify past it). Tuition-cohort count restates 16→15; RD gates the semantic at plan review.
7. **B3 — post-correction verification (RD-WITNESSED):** `current_equity` recomputes (≈ +$10.94 → equity_delta ≈ −$0.17, under the $10 tolerance → the badge SELF-CLEARS with zero tolerance change) · AMN realized flips −$9.60 → +$1.17 · **the H1 epoch standard-cohort ledger re-derivation from corrected fills, Σrealized reconciled to the broker TO THE CENT** (the forensic doc's arithmetic is the fixture). Operator witnesses the badge death; RD witnesses the re-derivation.

### ORDER (RD-BINDING, verified at his plan review)
**Half A merges BEFORE or ATOMICALLY WITH Half B — never data-first.** If the data were corrected while the old matcher ran even once, #34 proves the corruption simply reapplies. Sequence: corrector → corrections → verification.

## §3 CHARC architecture pass — conditions (binding)

- **A5 — scope:** `reconciliation_classifier.py` + `reconciliation_auto_correct.py` + the B2 mechanism's touchpoints + tests. The classifier STAYS a pure function (no I/O — its architecture lock). The corrections table stays APPEND-ONLY. Sandbox gating unchanged. No other `swing/trades` file beyond what B2's designed mechanism requires; enumerate in the plan.
- Tier-2 demotions must flow through the EXISTING ambiguity machinery (`reconciliation_ambiguity_choices.py` / `get_choice_menu` — per-choice `requires_custom_value` contract per CLAUDE.md); no parallel prompt path.
- Fixture discipline (BINDING, the `feedback_adversarial_review_verify_data_shapes` family): regression fixtures are the REAL PTEN/DFTX/AMN geometries from the live DB + the broker-true values — the exact two-candidate same-qty scenarios; never synthetic values built to satisfy the guards. Pre/post arithmetic computed for every discriminator (`feedback_regression_test_arithmetic`).
- Discriminating tests at minimum: the PTEN scenario (two same-qty candidates → tier-2, NOT auto) · the AMN #34 scenario (re-correction → blocked+material) · side-mismatch and date-distance guards each · A4 divergence fires on the current live PTEN/DFTX rows (pre-B1) and goes quiet post-B1 · B3's re-derivation equals the forensic doc's numbers.

## §4 Gates

1. **RD plan-stage review** (the SATL void mechanics, the A2 band, the ordering constraint — he has pre-committed availability this weekend).
2. review-strong to convergence + codex-auto-review (measurement-chain production code).
3. Suite + ruff + merged-head no-false-green, per merge (A and B may be one branch with ordered commits or two arcs — orchestrator's call within the ORDER constraint).
4. **RD merge-blocking QA** + the **RD-witnessed B3 verification** + the **operator witness** (live badge death).
5. The ORCHESTRATOR posts return reports to `charc,rd` after its QA; implementers never post to directors.

## §5 Sizing + dispatch recommendation

Small-medium code, maximum evidence-density (everything is broker-verified; the design space is guards, not algorithms). CHARC recommendation: **writing-plans `implementer-opus-xhigh`** (matcher/guard design + the B2 no-schema void design), **executing `implementer-opus-high`** (locked plan; the corrections are audited + supersede-chain reversible). Orchestrator selects + announces.
