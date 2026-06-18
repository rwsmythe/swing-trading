# Implementation plan — `equity_delta` limbo-routing fix (the 18-H.6.1 pivot-skip pattern)

**Status:** writing-plans deliverable (PLAN-ONLY). **Spec / settled design:** `docs/equity-delta-limbo-fix-commissioning-brief.md` (the CHARC §3 architecture pass + the SETTLED design; C1-C4 + L-locks). **Lane:** CHARC — a `swing/trades` carve-out scoped to the reconciliation classify/dispatch pivot. **Author:** writing-plans implementer (`implementer-opus-high`). **Date:** 2026-06-17.

The design is SETTLED by the brief — this plan grounds it on disk and lays out the TDD task breakdown + the discriminating tests; it does NOT re-open the design.

---

## 0. BLOCKING OPEN QUESTION for CHARC (must be ruled BEFORE executing) — a confirmed brief-internal contradiction

> **The brief contradicts itself on disk re: C2 "banner/count".** The brief's §5 second discriminating test requires the `unresolved equity_delta` to be "included in the **material banner/count**", but the brief's §2/C4 settled scope is a SINGLE-LINE skip ("the only production touch is `_pivot_classify_and_dispatch_for_run`; NO schema, NO new module"). On disk these are mutually exclusive: a fired `equity_delta` is `material_to_review=0` (`swing/trades/reconciliation.py:109`), and EVERY material-banner surface is gated `material_to_review = 1` (§2.6), so an `equity_delta` cannot enter the material banner WITHOUT a `MATERIAL_BY_TYPE["equity_delta"] 0->1` change — which §2/C4 forbids. The brief's §5-second-test is UNSATISFIABLE under the brief's own §2/C4 scope.
>
> **CHARC must rule between:**
> - **(A) RECOMMENDED — stays in §2/C4 scope:** C2 is satisfied by the RUN-level `unresolved_discrepancies_count` + the CLI-clearable path; the material-banner exclusion is correct-by-design (an immaterial coherence finding, mirroring 18-H.6.1's deliberate scoping at `swing/data/repos/reconciliation.py:524-535`). No `MATERIAL_BY_TYPE` change; the arc stays the single-line skip.
> - **(B) literal §5-second-test:** the `equity_delta` enters the GLOBAL MATERIAL banner -> requires `MATERIAL_BY_TYPE["equity_delta"] 0->1` (a `swing/trades` constant + behavior change, larger blast radius — every fired `equity_delta`, incl. the 4 cleared legacy rows, becomes a material alert). This is OUTSIDE the brief's settled §2/C4 scope and needs CHARC's explicit authorization + its own discriminating test.
>
> **This plan is written to (A)** (so executing can start immediately on a CHARC-confirm-A). If CHARC rules (B), the executing brief gains a `MATERIAL_BY_TYPE` task + test (b) assertion (iii) flips. **Timing: the orchestrator routes this question to CHARC at the WRITING-PLANS QA gate — i.e. as part of approving THIS plan / authorizing the executing dispatch, BEFORE any implementation begins (NOT at executing-QA).** The executing implementer is dispatched only with the ruling already in hand. (This is the headline grounding discrepancy in the return report — recipe §5 STOP-and-report.)

---

## 1. Overview + the settled design (restated)

**Problem.** A fired `equity_delta` (an account-level ledger-vs-NLV coherence discrepancy) flows through the reconciliation classify/dispatch pivot (`_pivot_classify_and_dispatch_for_run`), gets classified tier-2, and the pivot's else-branch stamps it `pending_ambiguity_resolution` (the tier-2 fill-matching-ambiguity limbo). That limbo is the WRONG state for an `equity_delta`: an `equity_delta` is not a broker-vs-journal fill RECORD to disposition, and `pending_ambiguity_resolution` is reached by the operator only via the tier-2 ambiguity-resolve machinery — which does not legitimately apply to a run-grain coherence discrepancy. The live witness is **id 71** (run 59) from the swing-NLV §2.4 work.

**Settled design (the 18-H.6.1 pattern, applied to `equity_delta`).** Extend the pivot's existing `untracked_broker_position` skip to also skip `equity_delta`:

```python
if disc.discrepancy_type in ("untracked_broker_position", "equity_delta"):
    continue
```

→ a fired `equity_delta` (legacy both-flat OR swing-scoped) stays **`unresolved`** — a real unaddressed coherence finding that is cleared via the existing manual resolver (`swing/trades/reconciliation.py:resolve_discrepancy` -> `acknowledged_immaterial`), NOT routed to the tier-2 limbo. **NO schema, NO migration, NO new module.** The only production touch is the one-line skip-set extension in `_pivot_classify_and_dispatch_for_run`.

---

## 2. Grounded code facts (re-grounded on disk 2026-06-17)

All line numbers are from the worktree base (`main` HEAD `3ed47485`). The executing implementer re-grounds before editing (line numbers drift).

### 2.1 The pivot skip (the edit site) — `swing/trades/schwab_reconciliation.py:598`

`_pivot_classify_and_dispatch_for_run` (def at `:550`) loops the run's discrepancies (`:580`). The existing 18-H.6.1 Part-3 skip is at **`:586-599`**:

```python
        # Phase 18 Arc 18-H.6.1 Part 3 — an `untracked_broker_position` ...
        if disc.discrepancy_type == "untracked_broker_position":
            continue
```

This is the ONE line to widen to the two-element tuple membership test. It sits AFTER the `if disc.resolution != "unresolved": continue` guard (`:583-584`) and BEFORE the `SAVEPOINT correction_sp_<id>` open (`:601`), so a skipped `equity_delta` never opens a savepoint, never calls `classify_discrepancy`, and never reaches the tier-2 stamp.

### 2.2 The else-branch that stamps `pending_ambiguity_resolution` — `swing/trades/schwab_reconciliation.py:792-803`

The tier-2 stamp the skip bypasses:

```python
            else:
                # Tier-2 — stamp pending_ambiguity_resolution via the
                # canonical service helper inside the active savepoint.
                _stamp_pending_ambiguity_inner(
                    conn,
                    discrepancy_id=disc.discrepancy_id,
                    ambiguity_kind=classification.ambiguity_kind
                    or "unsupported",
                    resolution_reason=classification.correction_reason,
                )
                conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                counters["tier2_pending_count"] += 1
```

(The brief's `~:793` anchor is correct; the stamp is at `:795`, the else at `:792`.)

### 2.3 GROUNDING CORRECTION — `equity_delta` HAS a sub-classifier (the brief's mechanism claim is wrong; the FIX is unaffected)

The brief (§1) states "`equity_delta` ... has NO sub-classifier either -> ... `unsupported` -> the else-branch stamps `pending_ambiguity_resolution`". **On disk this is INCORRECT about the mechanism.** `equity_delta` DOES have a registered sub-classifier:

- `swing/trades/reconciliation_classifier.py:1773` `_classify_equity_delta`, registered at `:1793` (`_SUB_CLASSIFIERS["equity_delta"] = _classify_equity_delta`).
- It returns `ClassificationResult(tier=2, ambiguity_kind="field_shape_incompatible", ...)` — NOT `unsupported`.

So the real production path is: pivot calls `classify_discrepancy` -> sub-classifier returns `tier=2, field_shape_incompatible` -> the else-branch at `:792` stamps `pending_ambiguity_resolution` with `ambiguity_kind="field_shape_incompatible"`. The OUTCOME the brief describes (`pending_ambiguity_resolution` limbo) is correct; only the *mechanism* (the brief says `unsupported`, reality is `field_shape_incompatible`) differs. **The settled fix (the skip) is identical either way** — the skip makes the pivot never call `classify_discrepancy` for `equity_delta` at all, so neither `unsupported` nor `field_shape_incompatible` is ever stamped.

**Framing (Codex R1 MINOR — ADOPTED).** This is a RETURN-REPORT observation requiring CHARC acknowledgment, NOT a license to weaken any required test. It does NOT re-open the design (the fix is unchanged) and the tests below are made STRONGER, not weaker, on the back of it. The one concrete test consequence: the live limbo `ambiguity_kind` is `field_shape_incompatible` (verified on the live DB id 71, §2.5), so the C3 raw-insert seed uses that value (the migration-0031 ambiguity_kind CHECK lists both `field_shape_incompatible` and `unsupported`, so either is CHECK-valid; using the real one keeps the fixture true-to-production).

### 2.4 The manual resolver — `swing/trades/reconciliation.py:568` `resolve_discrepancy`

Accepted-state logic, grounded:

- Accepts `resolution` in `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` (`:150-156`) = `{journal_corrected, source_treated_canonical, manual_override, unresolved, acknowledged_immaterial}`. `acknowledged_immaterial` IS allowed, and per the §3.3 nullability rule (`:624-632`) it permits a NULL `resolution_reason`.
- It does NOT gate on the row's CURRENT resolution unless the caller passes `require_current_resolution` (default `None`, `:577`) — so it accepts a row CURRENTLY in `pending_ambiguity_resolution`.
- **It already clears `ambiguity_kind` on the terminal transition** (18-H.6.1 Codex R2 Major #1, `:651-672`): `clear_ambiguity_kind = existing.ambiguity_kind is not None`, passed into `repo.update_discrepancy_resolution(..., clear_ambiguity_kind=...)`. That repo function (`swing/data/repos/reconciliation.py:371-421`) sets `ambiguity_kind = NULL` in the SAME UPDATE when `clear_ambiguity_kind=True`, satisfying the migration-0031 cross-column CHECK.
- The migration-0031 cross-column CHECK (`swing/data/migrations/0031_untracked_broker_position.sql:71-83`): `(ambiguity_kind IS NULL AND resolution NOT IN ('pending_ambiguity_resolution','operator_resolved_ambiguity')) OR (ambiguity_kind IS NOT NULL AND resolution IN (...))`. So moving `equity_delta` from `pending_ambiguity_resolution`+`field_shape_incompatible` -> `acknowledged_immaterial`+NULL is CHECK-safe via the existing `clear_ambiguity_kind` path.

CLI clear path (the operator surface for an `unresolved`/`pending` `equity_delta`): `swing journal discrepancy resolve <id> --resolution acknowledged_immaterial` (`swing/cli.py:3070-3119`) -> `resolve_discrepancy`. The CLI `--resolution` Choice already includes `acknowledged_immaterial` (`:3076`).

### 2.5 The id-71 finding (read-only live-DB inspection; NO writes)

Inspected the live DB read-only (`file:...swing.db?immutable=1`):

| field | id 71 |
| --- | --- |
| `discrepancy_type` | `equity_delta` |
| `resolution` | `pending_ambiguity_resolution` |
| `ambiguity_kind` | `field_shape_incompatible` |
| `material_to_review` | `0` |
| `run_id` | `59` |
| `field_name` | `net_liquidating_value` |

It IS in the limbo exactly as the brief describes. Corroborating: the OTHER 4 `equity_delta` rows on the live DB (ids 11/14/18/30) are ALL `acknowledged_immaterial` with `ambiguity_kind=NULL` — i.e. they were successfully cleared via the existing resolver. Schema version on disk = **31** (matches `main`).

**C3 disposition (DECISIVE):** id 71 is **clearable by the EXISTING resolver, NOT genuinely stuck.** `resolve_discrepancy(discrepancy_id=71, resolution="acknowledged_immaterial")` passes every gate: `acknowledged_immaterial` is in the allowlist; null reason is permitted; no `require_current_resolution` gate; `ambiguity_kind` is non-NULL -> `clear_ambiguity_kind=True` -> the CHECK-safe UPDATE. The CLI path `swing journal discrepancy resolve 71 --resolution acknowledged_immaterial` clears it today. **=> C3 = "the existing resolver already handles it, asserted by a test" — NO resolver code change.**

### 2.6 Banner/count surfacing scope (precision for C2)

`equity_delta` is `material_to_review=0` (`swing/trades/reconciliation.py:109` `MATERIAL_BY_TYPE["equity_delta"]=0`). The global MATERIAL banner/count (`swing/metrics/discrepancies.py:count_unresolved_material`) unions the three `material_to_review = 1` readers + the `untracked_broker_position` orphan arm — all gated on `material_to_review = 1`. So an `unresolved` `equity_delta` does **NOT** enter the MATERIAL banner/count. This is INTENTIONAL and is documented in the 18-H.6.1 `list_unresolved_material_orphans` docstring (Codex R1 Major #1, `swing/data/repos/reconciliation.py:524-535`), which explicitly names `equity_delta` as a material-`0`, `trade_id IS NULL` type deliberately scoped OUT of the orphan banner arm.

**Where an `unresolved` `equity_delta` IS surfaced + cleared:** it appears in the per-run discrepancy listing (`list_discrepancies_for_run`, regardless of material flag) and the run's `unresolved_discrepancies_count`, and it is cleared via the CLI manual resolver (`swing journal discrepancy resolve`). It is NOT reached via the web orphan-acknowledge branch (that branch is scoped to `untracked_broker_position` via `_is_orphan_discrepancy`, `swing/web/routes/reconcile.py:157`).

**C2's "banner/count" wording — a CONFIRMED BRIEF-INTERNAL CONTRADICTION -> BLOCKING OPEN QUESTION (see the boxed §0 escalation; Codex R1+R2 MAJOR — ADOPTED).** Grounded on disk: a fired `equity_delta` is `material_to_review=0` (`swing/trades/reconciliation.py:109`). EVERY material-banner surface is gated on `material_to_review = 1`: `count_unresolved_material` (`swing/metrics/discrepancies.py:39-59`, unions active/closed/orphan arms, all `material=1`), `list_pending_ambiguities_in_banner_set` (`:62-106`), `list_unresolved_material_orphans` (scoped to `untracked_broker_position`, `material=1`). Therefore an `unresolved equity_delta` **CANNOT** enter ANY material banner/count UNLESS `MATERIAL_BY_TYPE["equity_delta"]` flips `0->1`.

The brief's §5 SECOND discriminating test ("the unresolved `equity_delta` is included in the **material banner/count**") is thus UNSATISFIABLE under the brief's OWN §2/C4 settled scope ("the only production touch is `_pivot_classify_and_dispatch_for_run`; NO schema, NO new module"). The two brief clauses contradict on disk. Root cause: the brief is the 18-H.6.1 twin, and 18-H.6.1's `untracked_broker_position` is `material=1` (so IT banners); the "banner/count" wording carried over WITHOUT noticing `equity_delta` is `material=0`.

This is NOT a writing-plans implementer's call to default silently. It is escalated as the boxed §0 BLOCKING OPEN QUESTION. The two resolutions:

- **Interpretation A (RECOMMENDED — stays in §2/C4 scope, no extra code):** C2 is satisfied by the RUN-level unresolved count (`run.unresolved_discrepancies_count`, which DOES include it) + the CLI-clearable path. The material-banner exclusion is correct-by-design (an immaterial coherence finding is not a "must-act-now" material alert; this matches the deliberate 18-H.6.1 scoping documented at `swing/data/repos/reconciliation.py:524-535`). Under A, test (b) below asserts the run-level count + the cleanable path AND asserts the material-banner exclusion is correct-by-design.
- **Interpretation B (out of the brief's §2/C4 single-line scope):** if CHARC reads §5 literally as REQUIRING the `equity_delta` in the GLOBAL MATERIAL banner, that requires `MATERIAL_BY_TYPE["equity_delta"] 0->1` (a `swing/trades` constant change, NOT schema but a behavior change with its own blast radius — every fired `equity_delta` incl. the 4 already-cleared legacy ones becomes a material alert). That is a SEPARATE, larger decision the brief's settled scope does not authorize. Under B, test (b) flips its assertion (iii) to require material-banner MEMBERSHIP and Task 1 gains a second production edit + its own discriminating test.

**The plan does NOT authorize the executing implementer to proceed past this question without CHARC's ruling** (the §0 box). The ruling happens at the WRITING-PLANS QA gate (before the executing dispatch), not at executing-QA. The plan is WRITTEN OUT to Interpretation A (recommended) so executing can start immediately if CHARC confirms A; if CHARC rules B, the executing brief must add the `MATERIAL_BY_TYPE` task. Test (b)'s assertion (iii) is the one line that flips between A and B.

---

## 3. Per-task breakdown (TDD-first)

**Task count: 1 production task (the skip extension) + the C3 assertion folded into that task's test module (no resolver code).** C3 needs NO production code (§2.5) -> it is a *test-only* assertion proving the existing resolver clears a raw-inserted limbo `equity_delta`. So the whole change is ONE production edit + one new test module.

### Task 1 — extend the pivot skip to `equity_delta`

**File (production):** `swing/trades/schwab_reconciliation.py` (the skip at `~:598`; re-ground before editing).

**Failing test FIRST** — new module `tests/trades/test_equity_delta_limbo_routing.py` (mirrors `tests/trades/test_untracked_broker_position.py` fixtures: a synthetic `_SchwabAccount`, `run_schwab_reconciliation` end-to-end).

Tests (with pre/post arithmetic):

1. `test_fired_swing_scoped_equity_delta_stays_unresolved_not_pending_ambiguity` (discriminating test (a) — the LOAD-BEARING distinguisher; **REQUIRED to be the SWING-SCOPED §2.4 path** per Codex R1 MAJOR 2 — the live witness id 71 is swing-scoped). Seed the swing-scoped firing fixture via `run_schwab_reconciliation(...)`:
   - `out_of_framework_tickers=("SPCX",)` (an operator-declared out-of-framework ticker — `swing/trades/schwab_reconciliation.py:1186` param).
   - `schwab_account.positions = [{"instrument": {"symbol": "SPCX", "type": "EQUITY"}, "longQuantity": 2.0, "marketValue": 51.40}]` (a HELD declared OOF position -> `swing_scope_active=True`, `declared_held` non-empty, `broker_flat_swing=True` since the only position is declared, `declared_oof_mv=51.40`, `declared_mv_available=True`).
   - no open trades -> `journal_flat=True`.
   - `net_liquidating_value` chosen so `swing_nlv = NLV - 51.40` diverges from `finite_ledger_equity` by MORE than `_cash_coherence_tolerance(swing_nlv)=max(5.00, 0.005*|swing_nlv|)`. With the default test-DB ledger equity `L` (no cash movements -> `L == cfg.account.starting_equity`; the implementer reads the actual `L` from the test config), set NLV `= L + 51.40 + D` where `D` is comfortably above tolerance (e.g. `D=500`) -> `swing_nlv = L + D`, `eval_delta = L - swing_nlv = -D = -500`, tolerance `~max(5, 0.005*|L+500|)` (single-digit-to-low-tens of dollars for a four-figure ledger) -> FIRES. The implementer COMPUTES the exact tolerance from the resolved ledger and asserts `abs(eval_delta) > tol` holds for the chosen NLV (so the fixture provably fires).
   - Assert (1) exactly one `equity_delta` row fired AND its `actual_value_json` carries `"basis": "net_liq_minus_declared_oof"` (PROVES it is the swing-scoped §2.4 path, not the legacy both-flat path — guards against a fixture that accidentally degrades to the legacy basis or to C2-degrade/no-fire); (2) `resolution == 'unresolved'`.
   - **Pre-fix arithmetic:** the pivot calls `classify_discrepancy(equity_delta)` -> `_classify_equity_delta` -> `tier=2, field_shape_incompatible` -> the else-branch stamps `pending_ambiguity_resolution`. Assertion (2) would FAIL (`resolution == 'pending_ambiguity_resolution'`).
   - **Post-fix arithmetic:** the pivot's widened skip-set `continue`s past the `equity_delta` -> it stays `unresolved`. Assertion (2) PASSES.
   - **Distinguishes.** (The arithmetic is computed under BOTH paths and they differ — not a both-paths-pass test.)
   - Build the fixture from the REAL emitter path (`run_schwab_reconciliation`) so it exercises production wiring (the synthetic-fixture-vs-emitter discipline). The basis assertion + the fired-count assertion BEFORE the resolution assertion ensure a non-firing or wrong-basis fixture cannot vacuously pass.

   1b. `test_fired_legacy_both_flat_equity_delta_stays_unresolved` (ADDITIONAL coverage — the legacy both-flat path). Same as (1) but no declared OOF position / no `out_of_framework_tickers` (-> `eval_basis="net_liq"`), no open trades, no broker positions; NLV diverges from the ledger by > tolerance. Assert `basis == "net_liq"` + `resolution == 'unresolved'`. Same pre/post distinguisher. This proves BOTH firing bases route to `unresolved` post-fix (the pivot dispatches on `discrepancy_type`, not basis — but the test pins both rather than assuming).

2. `test_fired_equity_delta_counts_in_run_unresolved_count_and_clearable` (discriminating test (b)). Reuse the swing-scoped fixture from (1). Assert:
   - (i) `run.unresolved_discrepancies_count` includes the `equity_delta` (it stays `unresolved` after the pivot recompute).
   - (ii) `resolve_discrepancy(conn, discrepancy_id=<the row>, resolution="acknowledged_immaterial")` succeeds and `get_discrepancy(...).resolution == "acknowledged_immaterial"`.
   - (iii) **[Interpretation A — the §0 default] the material-banner exclusion is correct-by-design** (§2.6): assert the fired `equity_delta` is ABSENT from `swing/metrics/discrepancies.py:count_unresolved_material` (it does NOT inflate the global material banner because `material_to_review=0`). This pins the on-disk behavior as INTENTIONAL — NOT a missing feature. **NOTE (Codex R3 MINOR 2):** assertion (iii) is a SCOPE LOCK (it pins the on-disk material-banner exclusion as intended), NOT the load-bearing pre/post C2 distinguisher — the distinguisher for C2 is the run-level unresolved-count (i) + the pre/post `resolution` flip in test 1. (iii) does not change pre-vs-post-fix; it locks scope. **If CHARC rules Interpretation B (§0), this single assertion FLIPS** to require material-banner MEMBERSHIP (`count_unresolved_material` increments by one) AND Task 1 gains a `MATERIAL_BY_TYPE["equity_delta"] 0->1` production edit + a discriminating test for it. The executing implementer applies whichever the §0 CHARC ruling selected.

3. `test_unrelated_sub_classified_type_still_dispatches_post_skip` (discriminating test (c) — the C1 LOCK; **tightened per Codex R1 MAJOR 3 — NO vacuous-pass escape hatch**). The lock MUST prove an unrelated, sub-classified type still flows the FULL savepoint+classify+dispatch path AND reaches its REAL (non-vacuous) classification outcome — not merely "stays whatever". Drive a `stop_mismatch` (sub-classifier `_classify_stop_mismatch` at `reconciliation_classifier.py:1323`) through the pivot:
   - Preferred: a focused direct call to `_pivot_classify_and_dispatch_for_run` with a SEEDED `stop_mismatch` discrepancy row (raw-insert, `unresolved`) plus the matching journal row + Schwab order payload the `stop_mismatch` sub-classifier needs, so the classifier reaches a REAL result. (A full end-to-end `run_schwab_reconciliation` stop-mismatch fixture is acceptable if cheaper, but the same non-vacuity assertion applies.)
   - **Non-vacuity assertion (REQUIRED):** assert the `stop_mismatch` resolves to its REAL sub-classified disposition — i.e. NOT `unsupported` and NOT skipped: it must end either tier-1-applied (`auto_corrected_from_schwab` / a `reconciliation_corrections` row) OR a SPECIFIC tier-2 `pending_ambiguity_resolution` whose `ambiguity_kind` is the `_classify_stop_mismatch` value (NOT `unsupported`). The test asserts the EXACT disposition the pre-edit pivot produces for that fixture, captured by RUNNING the assertion against the fixture (the classifier outcome is deterministic for the seeded inputs). A bare "resolution unchanged" or an `unsupported`/skipped result is FORBIDDEN — it would prove the fixture never reached the sub-classifier (the vacuity Codex flagged).
   - **Pre==post (the LOCK):** the skip set never matched `stop_mismatch`; widening it to add `equity_delta` cannot touch the `stop_mismatch` dispatch path. The asserted disposition is IDENTICAL under both the pre-edit and post-edit pivot — that identity, with the non-vacuity assertion proving the sub-classifier actually ran, IS the C1 lock.

4. `test_legacy_pending_ambiguity_equity_delta_clearable_to_acknowledged_immaterial` (discriminating test (d) — the C3 assertion, NO production code). RAW-INSERT a `pending_ambiguity_resolution` `equity_delta` (the id-71 shape) via `conn.execute(...)` — bypassing any write-path, planting `resolution='pending_ambiguity_resolution'`, `ambiguity_kind='field_shape_incompatible'` (CHECK requires `ambiguity_kind IS NOT NULL` for this resolution; raw insert is mandatory per the cross-arc write-barrier lesson AND because the manual resolver REJECTS setting `pending_ambiguity_resolution`). Then call `resolve_discrepancy(conn, discrepancy_id=<id>, resolution="acknowledged_immaterial")`. Assert the row is now `resolution='acknowledged_immaterial'` AND `ambiguity_kind IS NULL` (the cross-column CHECK held — the resolver's `clear_ambiguity_kind` path NULLed it).
   - **Distinguishing:** mirror `tests/trades/test_resolve_orphan_discrepancy.py:test_resolve_legacy_pending_ambiguity_orphan_clears_ambiguity_kind` (the exact twin precedent). Pre-the-18-H.6.1-resolver-work this would have failed the CHECK (ambiguity_kind left non-NULL); on `main` it PASSES — which is the POINT of C3: the existing resolver ALREADY handles the limbo `equity_delta` with no new code. This test pins that the equity_delta variant is covered.

**Minimal implementation (after the failing tests):**

```python
        if disc.discrepancy_type in ("untracked_broker_position", "equity_delta"):
            continue
```

Update the adjacent comment block (`:586-597`) to name `equity_delta` alongside `untracked_broker_position` (an account-level coherence finding, not a fill record to disposition; stays `unresolved`, cleared via the manual resolver). Keep the comment ASCII-only.

**Acceptance:**
- Tests 1, 1b, 2, 3, 4 green; the full fast suite green (`python -m pytest -m "not slow" -q`) BEFORE the Codex review.
- `ruff check swing/` clean.
- C1-C4 + the L-locks honored (§5 traceability table).

---

## 4. The §5 discriminating tests, mapped

| brief §5 test | plan test | how it distinguishes |
| --- | --- | --- |
| fired swing-scoped `equity_delta` -> `unresolved` (pre: `pending_ambiguity_resolution`; post: `unresolved`) | Task 1 test 1 (swing-scoped, REQUIRED) + test 1b (legacy both-flat, additional) | pre-fix the pivot stamps `pending_ambiguity_resolution` (via `field_shape_incompatible`, §2.3); post-fix the widened skip leaves it `unresolved`. Test 1 ASSERTS `basis == "net_liq_minus_declared_oof"` (the real §2.4 path). Computed under both paths; they DIFFER. |
| the `unresolved` `equity_delta` is counted + clearable -> `acknowledged_immaterial` | Task 1 test 2 | run-level `unresolved_discrepancies_count` includes it; `resolve_discrepancy(... acknowledged_immaterial)` clears it; AND material-banner exclusion asserted correct-by-design (§2.6 Interpretation A — a CHARC decision point, NOT a silent narrowing). |
| C1 lock: an unrelated sub-classified type (`stop_mismatch`/`fill_*`) tier-classifies exactly as today (pre==post) | Task 1 test 3 | `stop_mismatch` flows the full classify/dispatch path + reaches its REAL non-`unsupported` disposition (non-vacuity assertion), identical pre==post. |
| C3: a raw-inserted `pending_ambiguity_resolution` `equity_delta` (id-71 shape) -> cleared to `acknowledged_immaterial` (ambiguity_kind auto-clear; 0031-CHECK-safe) | Task 1 test 4 | raw-insert (write-barrier lesson + resolver rejects setting pending); existing resolver clears it + NULLs `ambiguity_kind`; CHECK holds. |

**Note on the brief's "swing-scoped" phrasing for test (a) (Codex R1 MAJOR 2 — ADOPTED):** the brief offers "legacy both-flat OR swing-scoped", and the live witness id 71 is the SWING-SCOPED path. Test 1 is therefore REQUIRED to be the swing-scoped fixture (with a `basis == "net_liq_minus_declared_oof"` assertion proving it) — swing-scoped coverage is NOT optional (an optional treatment risks a false green on the actual §2.4 path). Test 1b adds the legacy both-flat path as well, so BOTH firing bases are pinned to route `unresolved` post-fix.

---

## 5. C1-C4 + L-lock traceability table (the CHARC QA checklist)

| condition | task | test(s) | honored-on-disk note |
| --- | --- | --- | --- |
| **C1** — extend the skip to `equity_delta` ONLY; every other type's classify/dispatch byte-identical | Task 1 | test 3 | the edit is a one-line skip-set membership widen at `:598`; the `stop_mismatch` lock proves an unrelated sub-classified type reaches its REAL non-`unsupported` disposition (non-vacuity) AND is identical pre==post. |
| **C2** — a fired `equity_delta` ends `unresolved` (counted + cleanable), NEVER `pending_ambiguity_resolution` | Task 1 | tests 1, 1b, 2 | the widened skip leaves both firing bases `unresolved`; it counts in the run unresolved count + is CLI-clearable. The "banners" wording is a CHARC DECISION POINT (§2.6): Interpretation A (run-level count; material-banner exclusion correct-by-design) is the plan default + asserted; Interpretation B (`MATERIAL_BY_TYPE` change) is flagged for CHARC, OUT of this arc's scope. |
| **C3** — a `pending_ambiguity_resolution` `equity_delta` (id 71 + any pre-existing) clearable to `acknowledged_immaterial` (auto-clear `ambiguity_kind`) | Task 1 (test-only — NO resolver code) | test 4 | the EXISTING `resolve_discrepancy` already clears it (`clear_ambiguity_kind`, §2.4); id 71 is clearable today (§2.5). |
| **C4** — NO schema/migration/new module; only production touch is `_pivot_classify_and_dispatch_for_run` (+ tests) | Task 1 | n/a (structural) | ONE production edit in `schwab_reconciliation.py`; no `reconciliation.py` change (C3 needs none); no schema, no migration, no module. |
| **L1/L2/L4** — measurement-chain untouched; this is disposition-ROUTING only | Task 1 | n/a | the skip changes only the disposition routing of an already-correctly-EMITTED `equity_delta`; the emit (§2.4 coherence logic) + the `equity_delta_dollars` columns are not touched. No measurement change. |

---

## 6. Tripwire self-certification

- **`swing/trades` carve-out** — AUTHORIZED by the brief's CHARC §3 pass (CARVE-OUT-EXTENDED, the 18-H.6.1 twin), scoped to `_pivot_classify_and_dispatch_for_run` in `swing/trades/schwab_reconciliation.py`. C3 needs NO `reconciliation.py:resolve_discrepancy` change (the existing resolver already handles it, §2.5), so the carve-out narrows to the pivot function only.
- **NO schema, NO migration, NO new module, NO new dependency, NO new standing process.** Reuses the existing `unresolved` state + the existing manual resolver + the existing 0031 cross-column CHECK clearing.
- **File list (production):** `swing/trades/schwab_reconciliation.py` (one-line skip widen + comment). **Tests:** new `tests/trades/test_equity_delta_limbo_routing.py`. No other files.
- **No new tripwire beyond the brief's CHARC §3 pass.** Default `swing/trades` read-only posture returns after this arc.

---

## 7. Executing-phase spec (baked in from brief §6)

- **Cell:** `implementer-opus-high`.
- **Review (executing, BINDING gate):** `review-strong` — repo-access (production-code: the reviewer must read beyond the diff per the recipe's 18-H.4 repo-access note, since the skip's correctness depends on the surrounding pivot dispatch loop + the classifier + the resolver), run to `NO_NEW_CRITICAL_MAJOR`, NEVER tier down. PLUS `codex-auto-review` (gating, repo-access, matched-high effort) as the complementary second eye on production code.
- **The 2 standing MUST-DOs:** (1) the executing convergence transcript -> the TRACKED file `docs/reviews/equity-delta-limbo-fix-executing-codex-findings.md`; (2) commit with BARE git from the worktree cwd (never `git -C`).
- **RD:** `fyi`-only (disposition-routing of a coherence discrepancy is NOT a measurement change; RD placed no L2 block). The orchestrator sends the `fyi` after QA; the implementer never posts.
- **CHARC:** QAs C1-C4 after the orchestrator's QA. **Operator live-witness:** a swing-scoped `equity_delta` (or the cleared id 71) ends `unresolved`/clearable — no limbo.
- **Base:** then-current `main`; the orchestrator rebases + runs the merged-head no-false-green suite.

---

## 8. Explicitly OUT of scope

- Any measurement-chain touch (L4) — the §2.4 coherence/emit logic, the `equity_delta_dollars` / `account_equity_*` run-row columns, the swing-NLV basis derivation. SHIPPED + correct; this arc only re-routes the DISPOSITION.
- Any schema / migration / new module / new dependency (C4).
- Other discrepancy types' classify/dispatch (C1) — only `equity_delta` joins the skip set.
- The web orphan-acknowledge branch (scoped to `untracked_broker_position`); an `unresolved` `equity_delta` is cleared via the CLI manual resolver, not that branch (§2.6). Adding a web surface for clearing an `equity_delta` is NOT in scope.
- Material-banner inclusion for `equity_delta` — it is `material=0` by design (§2.6); changing `MATERIAL_BY_TYPE` is NOT in scope.

---

## Appendix A — grounding discrepancies flagged (do NOT re-open the design)

1. **`equity_delta` HAS a sub-classifier** (`_classify_equity_delta`, returns `tier=2, field_shape_incompatible` — NOT the brief's "no sub-classifier -> `unsupported`"). The OUTCOME (limbo) + the FIX (skip) are unaffected; only the limbo `ambiguity_kind` value differs (`field_shape_incompatible`, verified live on id 71). §2.3.
2. **C3 is "already handled by the existing resolver"** — id 71 is clearable TODAY via the CLI manual resolver; not genuinely stuck. -> NO resolver code change; C3 is a test-only assertion. §2.5.
3. **C2 "banners" — a CHARC decision point, NOT a silent narrowing** — an `equity_delta` is `material_to_review=0` and does NOT enter the global MATERIAL banner/count (by design, per the 18-H.6.1 `list_unresolved_material_orphans` docstring). It counts in the RUN-level unresolved count + is CLI-clearable. The plan defaults to Interpretation A (run-level count + cleanable; material-banner exclusion correct-by-design, asserted by test b-iii) and flags Interpretation B (a `MATERIAL_BY_TYPE` change to put it in the material banner) as a SEPARATE CHARC decision OUT of this arc's single-line scope. CHARC adjudicates at QA. §2.6.

**These observations make the plan's tests STRONGER, not weaker** (swing-scoped now required, the C1 lock non-vacuous, the material-banner exclusion explicitly pinned) — none is used to relax a binding condition.
