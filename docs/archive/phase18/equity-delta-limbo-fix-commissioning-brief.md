# CHARC commissioning + architecture brief — `equity_delta` limbo-routing fix (the 18-H.6.1 pattern)

**Author:** CHARC. **Date:** 2026-06-18. **Lane:** CHARC (the reconciliation classify/dispatch — a `swing/trades` carve-out). **Origin:** the swing-NLV §2.4 live-witness — the swing-scoped `equity_delta` (run 59, **id 71**) landed in `pending_ambiguity_resolution` (the tier-2 limbo): uncleanable + the wrong state. RD + the orchestrator concurred + flagged it MATTERS — a real swing-scoped `equity_delta` WILL fire (that is the point of §2.4) and must be cleanable, not uncleanable.
**Tripwire:** a `swing/trades` carve-out (the classify/dispatch pivot) → **this brief IS the CHARC §3 architecture pass** (CARVE-OUT-EXTENDED, exactly like 18-H.6.1). NO schema, NO new module.
**RD:** disposition-routing of a coherence discrepancy — NOT a measurement change; RD placed no L2 block. A courtesy `fyi` to RD at the executing return.

---

## 1. Problem (grounded on disk)

`_pivot_classify_and_dispatch_for_run` (`swing/trades/schwab_reconciliation.py:550`) loops the run's `unresolved` discrepancies; one with NO sub-classifier → `classify_discrepancy` returns tier-2 `unsupported` → the else-branch stamps **`pending_ambiguity_resolution`** (the tier-2 fill-matching-ambiguity limbo, `:793`). 18-H.6.1 Part 3 added a `continue` skip for `untracked_broker_position` (`:586-599`) so it stays `unresolved` (a real finding that banners + is cleared via the manual resolver). **`equity_delta` (an account-level ledger-vs-NLV coherence discrepancy) has NO sub-classifier either → it is stamped `pending_ambiguity_resolution`** — where the §2.4 run-59 id 71 landed. That is semantically wrong (an `equity_delta` is NOT a broker-vs-journal fill RECORD to disposition; RD) AND operationally broken (uncleanable limbo — the exact failure 18-H.6.1 fixed for the orphan).

## 2. Settled design (the 18-H.6.1 pattern, applied to `equity_delta`)

Extend the `:598` pivot skip to include `equity_delta`:

```python
if disc.discrepancy_type in ("untracked_broker_position", "equity_delta"):
    continue
```

→ a fired `equity_delta` (legacy both-flat OR swing-scoped) stays **`unresolved`** — a real unaddressed coherence finding that banners + is cleared via the manual resolver (`swing/trades/reconciliation.py:resolve_discrepancy` → `acknowledged_immaterial`), NOT routed to the tier-2 limbo. (An `equity_delta` is account-level coherence; the tier-2 fill-matching classify/dispatch never legitimately applied to it — the skip is the correct fix, not a workaround.) **NO schema** (reuse the existing `unresolved` state + the existing manual resolver). The executing implementer re-grounds the `:598` anchor against live code before editing (line numbers drift).

**The existing stuck id 71** (run-59, pre-fix): primarily the operator's in-progress web-resolve → `acknowledged_immaterial` (the 18-H.6.1 no-FK-safe resolver auto-clears `ambiguity_kind` on the terminal transition, satisfying the 0031 cross-column CHECK). The pivot skip prevents FUTURE limbo-stamping; if id 71 is genuinely stuck (the resolver path does not clear a `pending_ambiguity_resolution` `equity_delta`), the executing implementer surfaces it + the resolver gains the same terminal path the orphan got. Confirm on disk which case holds.

## 3. Binding conditions

- **C1** — extend the skip to `equity_delta` ONLY; EVERY other discrepancy type's classify/dispatch behavior stays byte-identical (mirror the 18-H.6.1 C1 lock; a test asserts an unrelated type still tier-classifies).
- **C2** — a fired `equity_delta` ends `unresolved` (banners + is cleanable), NEVER `pending_ambiguity_resolution`.
- **C3** — a `pending_ambiguity_resolution` `equity_delta` (id 71 and any pre-existing) is clearable to `acknowledged_immaterial` via the manual resolver (auto-clearing `ambiguity_kind` if set).
- **C4** — NO schema, NO migration, NO new module; the only production touch is `_pivot_classify_and_dispatch_for_run` in `schwab_reconciliation.py` (+ tests). If C3 needs a resolver tweak, it stays within the existing `reconciliation.py:resolve_discrepancy` (no new schema).
- **L-locks** — L1/L2/L4 unaffected: this is disposition-ROUTING of an already-correctly-emitted coherence discrepancy; no measurement-chain touch, and the `equity_delta`'s L2-soundness (from §2.4) is unchanged — it just stays cleanable.

## 4. Tripwire disposition — the CHARC §3 pass: **GO**

- **`swing/trades` carve-out** → AUTHORIZED, scoped to `_pivot_classify_and_dispatch_for_run` (+ possibly the `resolve_discrepancy` terminal path for C3). Read-only `swing/trades` default returns after.
- **NO schema / NO new module / NO new standing process.** GO.

## 5. Discriminating tests (pre/post arithmetic; raw-insert-seed any pre-existing limbo row — the cross-arc write-barrier lesson)

- A fired swing-scoped `equity_delta` → `resolution == 'unresolved'`. **Pre-fix:** `pending_ambiguity_resolution` (the limbo). **Post-fix:** `unresolved`. **Distinguishes.**
- The `unresolved` `equity_delta` is included in the material banner/count + is clearable via the manual resolver → `acknowledged_immaterial`.
- **C1 lock:** an unrelated discrepancy type (e.g. a `stop_mismatch` / `fill_*` that DOES sub-classify) still tier-classifies exactly as today (pre == post).
- **C3:** a raw-inserted `pending_ambiguity_resolution` `equity_delta` (id-71 shape) → cleared to `acknowledged_immaterial` (the `ambiguity_kind` auto-clear if set; the 0031 CHECK-safe transition).

## 6. Dispatch recommendation

- **Cell:** `implementer-opus-high` — a `swing/trades` carve-out at the reconciliation classify/dispatch; small + well-precedented (the 18-H.6.1 twin), but reconciliation-adjacent.
- **Review:** `review-strong` (binding, repo-access, to `NO_NEW_CRITICAL_MAJOR`, never tier down) + `codex-auto-review` (gating, repo-access). The 2 standing MUST-DOs (convergence transcript → TRACKED `docs/reviews/equity-delta-limbo-fix-executing-codex-findings.md`; bare-git-from-worktree-cwd).
- **Return:** the orchestrator QAs + posts to `charc` (+ a `fyi` to `rd`). CHARC QAs C1–C4. Operator live-witness: a swing-scoped `equity_delta` (or the cleared id 71) ends `unresolved`/clearable — no limbo. **Base** = then-current `main`; rebase + merged-head no-false-green.

## 7. Return report

The **ORCHESTRATOR** posts the executing return to `charc` (+ `rd` fyi) AFTER its QA (the implementer reports up in chat; never posts to a director inbox — comms taxonomy + `feedback_implementer_never_posts_to_directors`).

## 8. Writing-plans grounding corrections + CHARC §0 ruling (2026-06-18) — owned

The writing-plans grounding (plan `3bcc483f`) caught THREE inaccuracies in this brief; all owned, none changes the FIX (the one-line pivot skip), and the plan grounds all three (it is the binding executing spec):
- **(a) Mechanism (§1):** `equity_delta` HAS a sub-classifier (`_classify_equity_delta` → tier-2 `field_shape_incompatible`), NOT "no sub-classifier → unsupported". The outcome (`pending_ambiguity_resolution` limbo) + the fix (skip) are identical.
- **(b) §5 "material banner/count" — a brief-internal contradiction (CHARC error):** `equity_delta` is `MATERIAL_BY_TYPE=0` (`reconciliation.py:109`), so it CANNOT enter the global material banner without a `MATERIAL_BY_TYPE` change — which §2/C4 forbids. The "banner" wording carried over from the 18-H.6.1 twin (where `untracked_broker_position` is `material=1`) without checking `equity_delta` is `material=0`.
- **(c) id-71 (§2):** clearable by the EXISTING resolver (NOT genuinely stuck) → C3 is test-only; the carve-out narrows to `_pivot_classify_and_dispatch_for_run` ONLY (no resolver code).

**CHARC §0 RULING = (A):** the limbo fix's actual ask is CLEANABILITY — route a fired `equity_delta` OUT of the uncleanable `pending_ambiguity_resolution` limbo so it stays `unresolved` + run-level-counted + CLI-clearable. The material-banner exclusion is **correct-by-design** (`equity_delta` has been `material=0` since Phase 9 — acknowledged-not-bannered, like the 4 prior cleared rows). **C2 is satisfied by the run-level unresolved count + the clearable path, NOT the material banner.** No `MATERIAL_BY_TYPE` change; the arc stays the single-line pivot skip. The plan (`3bcc483f`) stands as-merged.

**(B) — the materiality question, surfaced as a SEPARATE deferred decision (NOT this arc):** whether a fired coherence drift SHOULD banner as MATERIAL (`MATERIAL_BY_TYPE["equity_delta"] 0→1`) is a deliberate operator/product decision with real blast radius (it flips ALL `equity_delta`, incl. legacy both-flat, to material alerts; `MATERIAL_BY_TYPE` changes have landed WITH schema/CHECK per #11). Honest visibility note: at `material=0`, a fired swing-scoped `equity_delta` shows in the run-level count + the discrepancy list + the recon log, but NOT the GUI material "needs attention" banner. NOT bundled into the limbo (cleanability) fix; commission separately if wanted.
