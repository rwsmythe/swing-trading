# CHARC commissioning + architecture brief — swing-NLV coherence refinement (SPCX §2.4 fast-follow)

**Author:** CHARC (tool-development director). **Date:** 2026-06-17.
**Lane:** CHARC (equity-machinery — RD itself placed §2.4 mechanics in this lane at SPCX commissioning §4 Q2). **RD merge-blocking on L2.**
**Origin:** the deferred §2.4 from the SPCX out-of-framework carve-out (path B) — registered fast-follow at SPCX close (`docs/phase18-todo.md` riders); operator-commissioned 2026-06-17.
**Tripwire:** crosses the `swing/trades` carve-out (the reconciliation service) → **this brief IS the CHARC §3 architecture pass** (no separate pass doc). NO schema, NO new module.
**Design status:** SETTLED with the operator (design dialogue 2026-06-17 — **drift-only** chosen). Writing-plans implements exactly this; it does NOT re-open the design.

---

## 1. Problem

Step 8 of `run_schwab_reconciliation` (`swing/trades/schwab_reconciliation.py:1804-1853`) emits an `equity_delta` discrepancy (the swing-ledger vs broker-NLV coherence check) ONLY when `journal_flat AND broker_flat`, where `broker_flat = len(schwab_positions) == 0` (`:1829`). With the operator holding the declared out-of-framework SPCX position, `broker_flat = False`, so the check is **suppressed entirely** — a real swing-ledger-vs-broker drift (an unrecorded fill, a cash-movement mismatch) goes **undetected** for as long as SPCX is held. (This is the tradeoff CHARC Ruling 2 put on record at SPCX close.)

§2.4 restores drift-detection by reconciling the swing ledger against a **swing-scoped NLV** (broker NLV minus declared out-of-framework market value), so the check fires when swing is flat-for-swing even while a declared holding is open.

## 2. Settled design (drift-only)

Generalize the both-flat gate to "flat for swing":

- **`broker_flat_swing` := `(schwab_positions − declared out-of-framework set) is empty`** — reuse the `out_of_framework_set` the SPCX carve-out already builds at `:1237`.
- **`swing_nlv` := `source_nlv − Σ(marketValue of the declared positions)`** — the declared MV taken from the **same** broker payload as the NLV.
- Fire `equity_delta` on `journal_flat AND broker_flat_swing AND swing_nlv computable AND |ledger_equity − swing_nlv| > _cash_coherence_tolerance(swing_nlv)`.
- **Drift-only (operator decision):** NO positive "flat + coherent" surface. The check fires only on a real drift — consistent with today's drift-only check. (The operator infers coherence from the absence of a discrepancy + the equity tile.)
- **Reuse the `equity_delta` discrepancy type** (no new type). Record the swing-scoping in the emitted `actual_value_json` (e.g. `swing_nlv`, `source_nlv`, `declared_oof_mv`, `basis="net_liq_minus_declared_oof"`) so the basis is explicit + auditable.
- **Math sanity:** subtracting the declared MV from NLV strips the out-of-framework value, leaving swing-relevant cash, which matches the realized-only ledger (`current_equity`) when swing is flat. Live numbers from the SPCX live-witness: NLV − SPCX $392.51 = cash ≈ ledger.

**Run-row recording (design point for writing-plans).** Today completion stamps `account_equity_source_dollars=source_nlv` + `equity_delta_dollars=coherence_delta` (always). §2.4 must record the **swing-scoped evaluation** when swing-flat (so the operator live-witness can SEE the swing-scoped delta and test (a) is distinguishable): record `source_nlv` (raw broker NLV) **and** `swing_nlv` **and** `Σ declared MV`, with `equity_delta_dollars` reflecting the delta the check actually evaluated (`ledger − swing_nlv` when swing-flat-computable, else `ledger − source_nlv` as today). **Writing-plans settles the exact column/JSON layout and MUST cross-check the `account_equity_*` / `equity_delta_dollars` dashboard consumers** (the equity tile reads these — do not misreport the raw broker NLV elsewhere).

## 3. Binding conditions (carry into writing-plans)

- **C1 (L2 — same-snapshot consistency):** the subtracted declared MV MUST come from the same Schwab account payload as `source_nlv`. The implementer **verifies on disk** that `schwab_account.net_liquidating_value` and `schwab_positions[].marketValue` originate from one account-details call (one snapshot). A cross-snapshot or separately-fetched MV is the canonical false-coherence vector — forbidden.
- **C2 (L2 — suppress on missing):** if ANY declared position's `marketValue` is `None`/unavailable, the swing-scoped check does NOT fire (cannot compute `swing_nlv` reliably). Suppression is always L2-safe; a false green is the cardinal sin. (Mirror the existing `source_nlv is not None` guard.)
- **C3 (byte-identical when nothing declared/held):** when the declared set is empty OR no declared position is held, `broker_flat_swing == broker_flat` and `swing_nlv == source_nlv` → ZERO behavior change vs today. Regression-locked by a test.
- **C4 (no schema / no new module / reuse `equity_delta`):** config-driven (the declared registry already exists from SPCX); NO migration; the ONLY production touch is `schwab_reconciliation.py` step 8 (the gate condition + the `broker_flat_swing`/`swing_nlv` computation + the run-row recording).
- **C5 (drift-only):** no positive "flat + coherent" confirmation surface (operator decision).

## 4. Tripwire disposition — the CHARC §3 pass: **GO**

- **`swing/trades` carve-out** → AUTHORIZED, scoped to `schwab_reconciliation.py` step 8 (the equity-coherence block + the `broker_flat_swing`/`swing_nlv`/run-row computation). The read-only `swing/trades` default returns after the arc.
- **New schema** → NONE (config-driven; reuse `equity_delta`). No migration.
- **New module / standing process** → NONE.

## 5. RD merge-blocking lock

- **L2 (no false equity signal, EITHER direction):** the refinement must NOT create a **false coherence** (a green that hides a real swing drift — strictly worse than suppression) NOR a **false drift** (firing when actually coherent). C1 + C2 are the L2 guards. **RD QAs L2 against the shipped diff at the executing return; RD's sign-off is merge-blocking.**
- L1 (zero contamination) + L4 (measurement chain untouched) hold trivially — §2.4 journals nothing (no `trades`/`fills` row) and touches no measurement-chain module; the change is the equity-coherence computation only.

## 6. Verification mandates

**Discriminating tests** (each states the pre-fix vs post-fix value so it provably distinguishes — memory `feedback_regression_test_arithmetic`; build fixtures from the REAL Schwab account + positions payload shape, `schwab_account.net_liquidating_value` + `schwab_positions[].marketValue`):

- **(a) coherent-while-holding** — declared SPCX held (its MV present), journal flat, ledger ≈ swing_nlv → NO `equity_delta`. Distinguisher: the run row records the **swing-scoped** delta (`ledger − swing_nlv` ≈ 0). *Pre-fix:* the check is suppressed (broker not flat) and the run row carries the source-based delta ≈ `−Σ declared MV` (large). *Post-fix:* the swing-scoped delta ≈ 0 is recorded + no discrepancy. **Distinguishes** via the recorded swing-scoped delta.
- **(b) drift-while-holding (THE core value)** — declared SPCX held, journal flat, ledger ≠ swing_nlv beyond tolerance → `equity_delta` FIRES. *Pre-fix:* suppressed (broker not flat) → NO fire (the bug — a real drift goes undetected). *Post-fix:* fires. **Distinguishes.**
- **(c) missing declared MV → suppress (C2)** — declared SPCX held with `marketValue=None` → NO fire. *Pre-fix:* suppressed anyway. *Post-fix:* still no fire (C2 guard), proven by asserting the swing-scoped delta was NOT computed/recorded (degrade path ran). **Distinguishes** the suppress-on-missing.
- **(d) nothing declared/held → byte-identical (C3)** — empty declared set, both flat → the existing both-flat check unchanged (a no-regression LOCK, stated as such; pre == post). Value: guards against an over-eager generalization changing the normal case.
- **(e) undeclared position present → suppressed** — a declared SPCX + an UNDECLARED position held → `broker_flat_swing = False` → no fire (swing isn't flat — there's an unaccounted real position). **Distinguishes** the scoping.

**Standing MUST-DOs** (proven on the SPCX arc, now standing for production-code arcs):
1. The convergence transcript persisted to a TRACKED path (`docs/reviews/swing-nlv-coherence-executing-codex-findings.md`) + the final verdict line + round count quoted verbatim in the return (post-merge-verifiable — a director QA cannot see a torn-down worktree).
2. Commit with BARE git from the worktree cwd (NOT `git -C`); if a commit is denied, STOP + report up (do not pre-broaden permissions).

**Operator live-witness (binding — mirrors SPCX §5.10):** on the live DB while holding declared SPCX, a real reconciliation run → the swing-NLV check RUNS (no false `equity_delta` when coherent); the run row carries the swing-scoped delta (≈ 0 when coherent). Optionally inject a known ledger drift to confirm it FIRES (test (b) live).

## 7. Dispatch recommendation

- **Writing-plans:** `implementer-opus-xhigh` (design/plan reasoning density), Codex `review-fast` to convergence.
- **Executing:** `implementer-opus-high` — the design is fully settled here, the change is small + localized to step 8, and the L2-safety is precisely specified (C1–C5); the gate stack is the real net (§5.10). **Review: `review-strong` (binding, repo-access, run to `NO_NEW_CRITICAL_MAJOR`, NEVER tier down) + `codex-auto-review` (gating, repo-access)** + RD L2 QA + the operator live-witness. *(opus-max is a defensible upgrade if you want maximum care on the equity-coherence computation itself — the silent-false-green surface L2 guards; CHARC's call is opus-high given the precise L2-spec + the double review + RD L2 + the live-witness. Orchestrator selects the cell + announces.)*
- **Base** = then-current main; the orchestrator rebases before merge and re-runs the fast suite on the MERGED HEAD (the binding no-false-green).

## 8. Return report

The **ORCHESTRATOR** posts the executing return report to BOTH `charc` and `rd` AFTER its QA (the implementer reports up to the orchestrator in chat; it never posts to a director inbox — comms taxonomy + memory `feedback_implementer_never_posts_to_directors`). RD's L2 sign-off is merge-blocking; CHARC QAs C1–C5; the operator live-witness + authorization gate the `--ff-only` merge.

## 9. RD L2 checklist — folded 2026-06-18 (BUILD TO THIS; refines §2 / C2 / §6)

RD pre-loaded L2 (thread `swing-nlv-coherence`) and **concurred the design is L2-sound on its face** — with drift-only (no positive surface) the only L2 failure mode is a MISSED drift (false coherence = failing to fire); C1 (same-snapshot MV) + C2 (suppress-on-missing) hit the two canonical vectors; no net-new L2 concern. RD front-loaded its executing-return L2 checklist so writing-plans builds to the gate:

1. **C1 read-path (same snapshot):** `source_nlv` AND the subtracted `marketValue`(s) MUST originate from the SAME account-details call/object (one snapshot) — RD verifies the READ PATH, not just the arithmetic. A cross-snapshot/separately-fetched MV is forbidden.
2. **C2 — suppress, NEVER treat-as-0 (sharpens C2):** a declared-and-held position with `marketValue=None` must SUPPRESS. Treating it as 0 → `swing_nlv = full NLV` vs the swing-ledger → a FALSE DRIFT of ~the declared MV (the OTHER L2 direction). Test (c) must prove the degrade path RAN (the swing-scoped delta was NOT computed/recorded).
3. **Σ scope:** `Σ(declared MV)` iterates the positions PRESENT in the payload whose ticker is declared; an un-held declared ticker contributes 0 and must not error.
4. **Run-row recording — RESOLVED (settles the §2 design point):** the dashboard-read columns STAY RAW — `account_equity_source_dollars` = the RAW broker NLV (the equity tile must NOT under-report the operator's TRUE account value by the declared MV) and `equity_delta_dollars` stays raw (`ledger − source_nlv`). The swing-scoped values (`swing_nlv`, `declared_oof_mv`, `source_nlv`, `basis="net_liq_minus_declared_oof"`) ride ADDITIVELY in the `equity_delta` discrepancy's `actual_value_json` WHEN IT FIRES. **NO new run-row column** (a migration would violate C4/C5). When swing-flat-and-coherent (no fire), the check LOGS its swing-scoped evaluation → that log line is **test (a)'s distinguisher** (the coherent case persists NO swing delta — no fire, no new column; supersedes the §6 test-(a) "run-row delta" distinguisher). RD verifies the equity-tile consumers are unaffected at executing.
5. **C3 byte-identical** when nothing declared/held (the regression lock).

L1 (zero contamination) + L4 (measurement chain untouched) hold trivially. RD QAs L2 against the shipped diff at the executing return (this checklist + §3/§5), merge-blocking, alongside CHARC C1–C5 + the operator live-witness. Route L2 questions to RD via the operator.

## 10. Operational practice — record an out-of-framework holding's cash outlay (witness-validated 2026-06-18)

The §5.10 live-witness (run 59) exposed that path B recorded SPCX's market-value side but NOT the swing CASH that funded it → the swing ledger overstated swing capital by the ~$372 outlay → a TRUE drift §2.4 correctly fired (RD L2 + CHARC concur; not a false drift). **Interim operational practice (until the cash-recon ROOT fix automates it):** when a declared out-of-framework holding is bought with swing-account cash, record the cash outlay as a swing cash_movement so the swing ledger stays accurate — it is a withdrawal FROM the swing sleeve (a future sale returning proceeds = a deposit, symmetric):

```
swing journal cash --withdraw <actual purchase cost> --date <purchase date> --ref <stable-ref> --note "<ticker> out-of-framework purchase: swing capital reallocated (path-B cash-side; not a swing trade)"
```

**L1 stays intact** — a cash_movement never enters `compute_stats`/cohort/hypothesis (the holding is still never a trade); only the swing capital LEDGER is corrected (it is read by position-sizing, so the ledger must be accurate). Witness run 60: ledger 2027.26 → 1654.78 ≈ swing_nlv 1654.96, `swing_coherence_delta=-0.18` (coherent), no fire. **Supersession:** the deferred **cash-recon ROOT fix** (auto-treat a declared-OOF Schwab TRADE-type txn as a swing transfer-out — the recon currently SKIPs TRADE-type assuming journaled-via-P&L, false for an OOF buy) will make this automatic; until it ships, follow the manual practice per OOF purchase.
