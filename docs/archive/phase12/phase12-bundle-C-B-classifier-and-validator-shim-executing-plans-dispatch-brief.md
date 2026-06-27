# Phase 12 Sub-sub-bundle C.B (Classifier + validator shim) — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-sub-bundle C.B (pure-logic classifier + validator-shim modules; ZERO journal mutations; ZERO Schwab API calls; ZERO transaction management) of the Phase 12 Sub-bundle C implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` §C (C.B scope; 14 tasks T-B.1 … T-B.14). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration:** ~8-12 hr implementation + ~2-4 hr Codex convergence. Total ~10-16 hr. C.B is pure logic on top of C.A's schema foundation; consumes spec §4 + §5.5 + §10 + Phase 9 dataclasses + Phase 11 mapper outputs.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-sub-bundle C.B (`PLAN_PATH=docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`, `SCOPE=Sub-sub-bundle C.B (T-B.1..T-B.14 only)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 14 tasks land. Expected 3-5 Codex rounds (matches Phase 9 Sub-bundle B 5 rounds + Phase 12 Sub-bundle A 3 rounds for similar pure-logic scope; Phase 12 Sub-sub-bundle C.A had 2 rounds for schema foundation — execution rounds typically taper after foundation lands).

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (3621 lines; Codex R6 confirmation NO_NEW_CRITICAL_MAJOR; LOCKED at `008dfe4`).
- **Sub-sub-bundle C.B section** is plan §C (lines 1068-1601). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §F cross-bundle pin matrix:** F-3 + F-4 + F-5 are the C.B pins. F-3 (C.A→C.B) is already consumed via the `ReconciliationDiscrepancy.ambiguity_kind` field shipped in C.A T-A.5; F-4 (C.B→C.C) ships at T-B.1; F-5 (C.B→C.C) ships at T-B.13. T-B.14 un-skips the two T-A.7 cross-bundle pin tests at `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py`.
- **Plan §G.2 C.B operator-witnessed gate** (3 surfaces; see §3 below).

### §0.2 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (1444 lines; Codex R9 confirmation NO_NEW_CRITICAL_MAJOR; LOCKED at `d682c25`).
- **Read for §4 classifier design (BINDING — public interface locked at §4.2; per-discrepancy-type sub-classifier logic at §4.3; determinism principle at §4.4; failure-mode contract at §4.5; validator chain integration at §4.6).**
- **Read §5.5 validator-shim composition** (BINDING — 4 dry-run validator signatures; `ValidatorChainCallable` 2-tuple return shape).
- **Read §10 three discriminating-example walkthroughs:** §10.1 CVGI 41 (tier-1 path) + §10.2 DHC 39 + §10.3 VSAT 40 (tier-2 path; Pass-2-tier-1-FORBIDDEN). Each walkthrough's "Classifier OUTPUT" block is the BINDING expected `ClassificationResult` for that fixture.
- **Read §1.3 four operator-locked architectural constraints** + **§8.4 Pass-2-tier-1-FORBIDDEN LOCK** (BINDING; T-B.4 enforcement).
- **§14 open questions all triaged** per writing-plans return-report disposition table.

### §0.3 Project state at dispatch time

- **HEAD on `main`:** `e52dda7` (post-C.A-merge `354b6c0` + status-line refresh `b24e9e2` + phase3e-todo SHIPPED entry `4a390a4` + handoff `1156202` + 3-lessons fold `e52dda7`). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **3966 fast passing on main** + 3 pre-existing failures (`tests/integration/test_phase8_pipeline_walkthrough.py`) + 3 skipped (Task 7.3 flag-classifier operator-only + 2 C.A cross-bundle pin tests waiting on C.B T-B.1+T-B.2 landing). Verified inline at handoff bootstrap.
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 11 + Phase 12 A+B+C.A).
- **Schema version:** **v19** (C.A T-A.1 shipped 2026-05-15; production-migrated 2026-05-15T18:52:43 with backup `swing-20260515T185243.db`).
- **Production discrepancy state:** 3 unresolved-material (39 DHC + 40 VSAT + 41 CVGI) + 30+ resolved historical. **LEFT UNRESOLVED BY DESIGN** pending Sub-sub-bundle C.D ship. C.B is pure logic; does NOT touch existing discrepancy rows. The three discrepancies are the BINDING fixtures for §10 discriminating walkthroughs.
- **Production refresh-token clock:** expires 2026-05-22T17:05:00+00:00 (~6 days remaining at handoff). C.B does NOT exercise Schwab API; refresh clock irrelevant to C.B gate.

### §0.4 Sub-sub-bundle C.B scope (14 tasks per plan §C)

| Task | Title | Files (illustrative; plan §C locks) |
|---|---|---|
| **T-B.1** | `classify_discrepancy` public entry + `ClassificationResult` dataclass + dispatch table skeleton + validator-respecting downgrade dispatcher | NEW `swing/trades/reconciliation_classifier.py` + `tests/trades/test_reconciliation_classifier_public_entry.py` |
| **T-B.2** | Validator shim module (4 dry-run validators: `validate_fill_correction` / `validate_trade_correction` / `validate_cash_movement_correction` / `validate_snapshot_correction`) | NEW `swing/trades/reconciliation_validators.py` + `tests/trades/test_reconciliation_validators.py` |
| **T-B.3** | `entry_price_mismatch` sub-classifier (CVGI 41 path — tier-1) | MODIFY classifier + NEW `tests/trades/test_classifier_entry_price_mismatch.py` |
| **T-B.4** | `unmatched_open_fill` sub-classifier (DHC 39 + VSAT 40 path — **tier-2-always V1 per §8.4 LOCK**) | MODIFY classifier + NEW `tests/trades/test_classifier_unmatched_open_fill.py` |
| **T-B.5** | `unmatched_close_fill` sub-classifier (mirrors T-B.4 symmetrically) | MODIFY classifier + NEW `tests/trades/test_classifier_unmatched_close_fill.py` |
| **T-B.6** | `stop_mismatch` sub-classifier (advisory-not-validator preserved per §4.3.4) | MODIFY classifier + NEW `tests/trades/test_classifier_stop_mismatch.py` |
| **T-B.7** | `position_qty_mismatch` sub-classifier (tier-2-always V1) | MODIFY classifier + NEW `tests/trades/test_classifier_position_qty_mismatch.py` |
| **T-B.8** | `close_price_mismatch` sub-classifier (tier-2-always V1; V2 OHLCV re-import banked) | MODIFY classifier + NEW `tests/trades/test_classifier_close_price_mismatch.py` |
| **T-B.9** | `cash_movement_mismatch` sub-classifier (tier-1 single-match + tier-2 otherwise) | MODIFY classifier + NEW `tests/trades/test_classifier_cash_movement_mismatch.py` |
| **T-B.10** | `sector_tamper` sub-classifier (tier-2-always V1; tier-3 path always per §4.3.8) | MODIFY classifier + NEW `tests/trades/test_classifier_sector_tamper.py` |
| **T-B.11** | `snapshot_mismatch` sub-classifier (tier-2-always V1) | MODIFY classifier + NEW `tests/trades/test_classifier_snapshot_mismatch.py` |
| **T-B.12** | `equity_delta` sub-classifier (tier-2-always V1; cash-basis-vs-MTM V2 banked) | MODIFY classifier + NEW `tests/trades/test_classifier_equity_delta.py` |
| **T-B.13** | `default_validator_chain(conn)` dispatcher (composes 4 shim validators via `affected_table` partial-application) | MODIFY validators + NEW `tests/trades/test_default_validator_chain.py` |
| **T-B.14** | Un-skip the two C.A T-A.7 cross-bundle pin tests | MODIFY `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` |

**Cross-bundle dependencies:** C.B CONSUMES C.A's schema (ambiguity_kind column + ReconciliationDiscrepancy dataclass + ReconciliationCorrection dataclass for future C.C use). C.C/C.D CONSUME C.B's `classify_discrepancy` + `default_validator_chain`. C.B does NOT consume C.C/C.D output.

**Module boundaries (BINDING — preserve discipline):**
- `swing/trades/reconciliation_classifier.py`: PURE FUNCTION. NO DB writes, NO Schwab API calls, NO transaction management. `journal_row` + `source_payload` are passed in as already-fetched data. Composition with I/O is C.C scope.
- `swing/trades/reconciliation_validators.py`: SELECT-only against the DB connection passed in. NEVER mutates. Returns `(passes: bool, rejection_reason: str | None)` tuple. Composition with `affected_table` partial-application happens at C.C `apply_tier1_correction` step 4 (not C.B).

### §0.5 BINDING contracts from plan §C + spec §4 (DO NOT re-litigate)

Per writing-plans return report + plan §C + spec §4/§5.5/§8.4/§10:

1. **`classify_discrepancy` signature LOCKED verbatim** per spec §4.2 + plan §C.1 acceptance #1. Kwargs-only beyond `discrepancy`; `validator_chain` parameter is optional.
2. **`ClassificationResult` dataclass shape LOCKED** per spec §4.2 + plan §C.1 acceptance #2. `tier ∈ {1, 2}` (classifier NEVER emits tier=3; tier-3 is operator-initiated post-tier-1 in C.C). `correction_target` is `dict | None`; tier-1 always non-None, tier-2 always None. `candidate_choices` is tier-2 only.
3. **Determinism principle (spec §4.4) BINDING.** Classifier defaults to tier-2 when in doubt. False-positive tier-1 silently corrupts journal; false-positive tier-2 just defers to operator (no harm). Discriminating test at T-B.1 invokes classifier 100× with same fixture inputs + asserts byte-for-byte identical result via frozen dataclass equality.
4. **Pass-2-tier-1-FORBIDDEN LOCK at T-B.4 (spec §8.4 + Codex R6 Major #1 fix).** V1 source_payload is ORDER-GRAIN (not execution-grain); `unmatched_open_fill` sub-classifier NEVER emits tier-1 regardless of N orders returned. Every Pass-2 input shape → tier-2 with appropriate `ambiguity_kind`. Discriminating test plants every plausible Pass-2 shape + asserts `result.tier == 2` for all.
5. **Validator-respecting downgrade contract (spec §4.6 + plan §C.1 acceptance #5).** Dispatcher invokes injected `validator_chain(correction_target)` AFTER the sub-classifier returns tier-1; on `(False, reason)`, downgrades to `(tier=2, ambiguity_kind='validator_rejected', correction_reason=<reason>)`. T-B.13 ships the default chain; T-B.1 dispatcher pre-wires the contract.
6. **Validator shim 2-tuple return shape (spec §5.5 wording formalized at plan §C.2 acceptance #2).** Each validator returns `(passes: bool, rejection_reason: str | None)`. Spec's "True/False (plus a rejection reason)" wording is formalized as a tuple at plan time; banked as a V2.1 §VII.F spec-amendment candidate.
7. **`default_validator_chain` dispatch on `affected_table` (plan §C.13).** Returns a callable that, when invoked with `(correction_target, *, affected_table, affected_row_id)`, dispatches to the right validator. Composition with `classify_discrepancy` (which invokes `validator_chain(correction_target)` with a single positional arg) requires partial-application of `affected_table` + `affected_row_id` at C.C construction time.
8. **Cross-column CHECK precedence (C.A return report lesson #2).** When classifier output drives a future C.C `INSERT` of `resolution='pending_ambiguity_resolution'`, the row MUST also carry non-NULL `ambiguity_kind` per the schema cross-column CHECK shipped at C.A T-A.1. Classifier discriminating test at T-B.1 covers BOTH branches: tier-1 emits `ambiguity_kind=None`; tier-2 emits `ambiguity_kind != None`.
9. **Sub-classifier failure-mode contract (spec §4.5).** If a sub-classifier raises an unexpected exception, the dispatcher catches + logs WARNING + emits `(tier=2, ambiguity_kind='unsupported', correction_target=None, correction_reason=f"classifier exception: ...")`. Pipeline / CLI never crashes on classifier errors (graceful degradation per Phase 11 lesson #2).
10. **`candidate_choices` shape (plan §C.4 acceptance #4).** Per-choice dicts include `code`, `description`, AND `requires_custom_value: bool` per spec §6.2.1 LOCKED per-choice `--custom-value` contract (Codex R5 Major #2 fix).

### §0.6 Forward-binding lessons inherited (BINDING for C.B)

**44 cumulative lessons** through C.A (Phase 11 17 + Phase 12 A 5 + B 12 + C brainstorm 5 + C writing-plans 2 + C.A 3 = 44).

Particularly load-bearing for C.B pure-logic work (see CLAUDE.md gotchas + `docs/orchestrator-context.md` §"Lessons captured"):

1. **Schema CHECK + Python validator paired work (C.A return report lesson #1).** Any time C.B classifier output values map to a CHECK enum (e.g., `ambiguity_kind`), the values MUST match the shipped `_VALUES` tuple in `swing/data/models.py` verbatim. If C.B implementer notices a needed enum value not in the shipped tuple, STOP + escalate (lesson #7 below) — do NOT widen the enum inline (that's a schema migration; out of C.B scope).
2. **Cross-column CHECK precedence (C.A return report lesson #2).** Pinned at §0.5 #8 above. Discriminating test at T-B.1 covers both schema-CHECK-rejection branches.
3. **`update_superseded_by` anchor pattern (C.A return report lesson #4).** Not directly C.B-load-bearing (it's an INSERT pattern at C.C T-C.3.4), but C.B classifier's `correction_target` shape MUST be coherent with multi-field tier-1 cases (e.g., `cash_movement_mismatch` per spec §4.4 + plan §C.9). Document atomic-multi-field intent in `correction_reason`.
4. **20-column LOCK on `reconciliation_corrections` (C.A return report lesson #5).** C.B does NOT write to `reconciliation_corrections`. If C.B implementer encounters a need for a new audit column, STOP + escalate.
5. **Lifecycle invariants are C.C service-layer (C.A return report lesson #6).** C.B classifier produces `ClassificationResult`. Lifecycle invariants (correction_action='auto_applied' implies applied_by='auto'; etc.) are enforced at C.C `apply_tier1_correction` INSERT-time, NOT at classifier-output time. If Codex flags "but the classifier should reject X" — push back: classifier produces ground truth for the service to consume; service is the enforcement layer.
6. **Determinism + composition-source empirical verification (Sub-bundle C brainstorm lesson family).** Spec §A.7.4 mapper verification empirically established that V1 `SchwabOrderResponse` exposes ORDER-GRAIN only. Do NOT assume the mapper exposes execution-leg data; build T-B.4 fixtures from the shipped mapper output shape, not from an idealized Schwab API response.
7. **Plan-author schema additions DURING execution cycle need pre-dispatch escalation (C.A return report lesson #7 confirmed by Codex R1 Major #4 + NEW lesson 2026-05-15 `657b8a0`).** If Codex surfaces a need for a schema element NOT in plan §C + spec §4/§5.5, the implementer MUST STOP + escalate to orchestrator BEFORE adding inline. Cost of bank-after-write: 2-3 Codex rounds of cascade cleanup. Cost of escalation: 1 chat round. Apply this to validator-shim invariants too: if a validator needs schema-level support that's missing, STOP + escalate (do NOT widen the schema inline).
8. **USERPROFILE+HOME monkeypatch discipline (Phase 9 Sub-bundle A gotcha).** C.B test fixtures that touch `~/swing-data/` paths MUST monkeypatch both env vars to tmp_path. Most C.B tests are pure-Python (no FS); but any test that exercises the validator shim against a real DB will create a tmp-DB and should still monkeypatch defensively.
9. **`apply_overrides` discipline at Schwab entry points (Sub-bundle B lesson #6).** N/A for C.B scope — no Schwab API calls in the classifier or validator-shim. Banked for C.C/C.D inheritance.
10. **HTMX gotcha trinity (Sub-bundle B lesson #11).** N/A for C.B scope — no web routes.

### §0.7 Sub-sub-bundle C.B test projection

Per plan §H.1: **+55-95 fast tests projected.** Per Phase 12 Sub-bundle A overshoot precedent (actual +35 vs projected +25), C.A overshoot (actual +104 vs projected +40-65), Phase 9 A/B/C overshoots — actual likely **+85-130 fast tests**.

Final main HEAD post-C.B-merge: ~4051-4096 fast tests (was 3966 + +85-130).

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-bundle-C-B-classifier-and-validator-shim`
- **Worktree directory:** `.worktrees/phase12-bundle-C-B-classifier-and-validator-shim/`
- **BASELINE_SHA:** `e52dda7` (current main HEAD pre-brief-commit; resolve via `git rev-parse main` at worktree-creation time after this brief lands).
- **Branch naming intent:** `phase12-bundle-C-B-*` matches the cleanup-script `phase\d+[-_]` regex; operator's `-DeregisterFirst` pass cleans cleanly post-merge.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 14 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes:
  - `feat(phase12-bundle-c-T-B.1): <description>` for classifier skeleton + dispatch table
  - `feat(phase12-bundle-c-T-B.2): <description>` for validator shim
  - `feat(phase12-bundle-c-T-B.3..12): <description>` for per-discrepancy-type sub-classifiers
  - `feat(phase12-bundle-c-T-B.13): <description>` for `default_validator_chain` dispatcher
  - `test(phase12-bundle-c-T-B.14): <description>` for un-skipping cross-bundle pin tests
  - `fix(phase12-bundle-c-B): Codex RN <severity> #N — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`** (per CLAUDE.md staging convention: prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §C mark per-step boundaries.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree until C.B integration commit (T-B.14 worktree push).
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-sub-bundle C.C dispatch commissioning.

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~15..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python -c "from swing.trades.reconciliation_classifier import classify_discrepancy, ClassificationResult; print('classifier OK')"
python -c "from swing.trades.reconciliation_validators import validate_fill_correction, default_validator_chain; print('validators OK')"
```

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 14 tasks land + tests GREEN.

**Expected chain shape:** 3-5 substantive Codex rounds (matches Phase 9 Sub-bundle B 5 rounds + Phase 12 Sub-bundle A 3 rounds + Phase 12 Sub-sub-bundle C.A 2 rounds for similar pure-logic scope). Convergent tapering per Phase 8 R2-R5 + Phase 9/10/11/12 lesson family.

**Adversarial review watch items (C.B-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **Determinism principle enforcement.** Every sub-classifier with multiple plausible target values → tier-2. Discriminating test at T-B.1 invokes classifier 100× with same inputs + asserts byte-for-byte identical result via frozen dataclass equality. Codex SHOULD verify: any branch that could pick between two correction values is tier-2 default.
2. **Pass-2-tier-1-FORBIDDEN at T-B.4 (spec §8.4 LOCK).** `unmatched_open_fill` sub-classifier NEVER emits tier-1 in V1 regardless of Pass-2 input shape (N=0 / N=1 / N≥2 sum-matches / N≥2 sum-mismatches all → tier-2). Discriminating test plants every plausible Pass-2 input shape + asserts `result.tier == 2` for all.
3. **Validator-respecting downgrade contract (spec §4.6).** Dispatcher invokes injected `validator_chain` AFTER sub-classifier returns tier-1; on `(False, reason)`, downgrades to `(tier=2, ambiguity_kind='validator_rejected', correction_reason=<reason>)`. Discriminating test at T-B.3 exercises this via the CVGI 41 fixture + a poisoned validator_chain that returns `(False, "test rejection")`.
4. **Sub-classifier failure-mode contract (spec §4.5).** Unknown `discrepancy_type` OR sub-classifier exception → `(tier=2, ambiguity_kind='unsupported')` with helpful `correction_reason`. Pipeline / CLI never crashes on classifier errors. Discriminating test plants a synthetic `'__unrecognized__'` discrepancy_type + asserts graceful degradation.
5. **20-column LOCK preservation (C.A return report lesson #5).** C.B does NOT write to `reconciliation_corrections` (that's C.C scope). Codex SHOULD verify: no SQL writes in classifier or validator shim modules.
6. **Cross-column CHECK precedence (C.A return report lesson #2).** Tier-1 result emits `ambiguity_kind=None`; tier-2 result emits `ambiguity_kind != None` matching the shipped 7-value enum at migration 0019. Discriminating test at T-B.1 covers both branches.
7. **Validator shim 2-tuple return shape (spec §5.5).** Every validator returns `(passes: bool, rejection_reason: str | None)`. NEVER raises (except on programmer errors like wrong-shaped `proposed_updates`). Discriminating tests cover happy paths + 4-6 reject paths each per plan §C.2.
8. **Aggregate-invariant dry-run on fill corrections.** `validate_fill_correction` simulates `_recompute_aggregates` post-correction via SELECT-based dry-run + rejects `current_size < 0` outcomes. Discriminating test plants trim scenario + asserts rejection.
9. **`candidate_choices` shape (spec §6.2.1).** Per-choice dicts include `code` + `description` + `requires_custom_value: bool`. Codex SHOULD verify menu lengths against spec §6.2.1: `multi_partial_vs_consolidated` → 4 choices; `multi_match_within_window` → N+2 choices; `schwab_returned_no_match` → 2 choices; `unknown_schwab_subtype` → 3 choices.
10. **Plan-author schema additions during executing-plans cycle (C.A return report lesson #7).** If Codex surfaces a need for a schema element NOT in plan §C + spec §4/§5.5, the implementer MUST STOP + escalate to orchestrator BEFORE adding inline. The cost of bank-after-write is 2-3 cascade-cleanup rounds.
11. **Cross-bundle pin tests un-skip at T-B.14.** Both `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` tests un-skip + pass after classifier + validator-shim land. Codex SHOULD verify the un-skip is binding-test-shape-correct (not just decorator removal).
12. **NO journal mutations, NO Schwab API calls, NO transaction management.** Pure-logic boundary enforcement. Codex SHOULD verify: classifier module has zero `INSERT/UPDATE/DELETE`; validator shim has zero `INSERT/UPDATE/DELETE`; no `requests.*` or `schwabdev.*` imports anywhere in C.B scope.

---

## §3 Operator-witnessed verification gate (Sub-sub-bundle C.B integration)

Per plan §G.2 (3 surfaces) + spec §15.5:

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q` | GREEN at ~4051-4096 fast tests (worktree-side; +85-130 net from 3966 baseline; landing in upper-half overshoot precedent); 3 pre-existing failures unchanged (phase8 walkthrough); skipped count drops by 2 (the C.A cross-bundle pin tests un-skipped at T-B.14 now pass). |
| **S2** | Classifier against CVGI 41 + DHC 39 + VSAT 40 fixtures emits expected `ClassificationResult` shapes per spec §10 | Operator-driven walkthrough via dispatched harness OR `python -c`. CVGI 41 (Pass 1 single-fill): `tier=1, ambiguity_kind=None, correction_target={'price': 5.30}`. DHC 39 (Pass 1 only — `actual={"matched": null}`): `tier=2, ambiguity_kind='unsupported', _pass_2_required=True`. VSAT 40 (Pass 1 only): same shape as DHC 39. Pass-2 invocations are NOT in C.B scope (classifier is pure function; Pass-2 re-fetch lives at C.D backfill). |
| **S3** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged. |

**Gate session ≤ 3 surfaces budget:** all 3 inline-or-script-driven. S1+S3 inline (2). S2 operator-driven via tiny harness (1). No browser-driven surfaces in C.B scope (no HTMX form work; no web surfaces). No production-write surfaces (C.B is read-only against any DB; gate fixtures use tmp-DBs).

**Production state post-gate:** NO behavioral changes to existing surfaces. C.B is consumer-side passive at this stage; the new classifier + validator-shim modules are imported only by C.B's own tests (no production callsites until C.C ships). Existing 3 unresolved-material discrepancies (39 + 40 + 41) UNCHANGED — left for C.D backfill.

**Production-write classifier soft-block awareness:** N/A — C.B has no production writes. No AskUserQuestion surfaces needed.

---

## §4 OUT OF SCOPE (do not do)

- **C.C auto-correction service scope** — `swing/trades/reconciliation_auto_correct.py` service module + `run_*_reconciliation` flow pivot + per-(ambiguity_kind, choice_code) handlers + audit row writes. Ships in Sub-sub-bundle C.C.
- **C.D Tier-2 CLI surface scope** — `swing journal discrepancy show-ambiguity|resolve-ambiguity|override-correction` + `swing journal reconcile-backfill` CLIs + Phase 10 dashboard banner predicate widening + production backfill of 39/40/41. Ships in Sub-sub-bundle C.D.
- **Schema additions or migrations** — per C.A return report lesson #7 + NEW lesson 2026-05-15 at `657b8a0`. If C.B implementer encounters a need for a schema element NOT in plan §C + spec §3/§4/§5.5, STOP + escalate to orchestrator BEFORE adding inline. Do NOT bank-after-write.
- **V2 mapper widening + auto-VWAP classifier path** — operator-locked next-architectural-dispatch slot (post-C.D ship). Banked at plan §I.1. NOT C.B scope. T-B.4 LOCKS Pass-2-tier-1-FORBIDDEN under V1 mapper coverage; V2 will revisit when execution-grain mapper data ships.
- **Pass-2 re-fetch logic** — classifier is pure function; Pass-2 invocation lives at C.D backfill. T-B.4 emits the `_pass_2_required=True` signal in `correction_reason`; consuming code at C.D reads it. NOT C.B scope.
- **Journal mutations of any kind** — NO `INSERT/UPDATE/DELETE` to any table from C.B code. Validator shim is SELECT-only.
- **Schwab API calls of any kind** — NO `requests.*` or `schwabdev.*` imports anywhere in C.B scope.
- **Transaction management** — NO `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` / `with conn:` in C.B code. Caller-tx in C.C owns the boundary.
- **Re-litigating spec §1.3 four operator-locked architectural constraints** — accepted as given.
- **Re-litigating §4.4 determinism principle, §5.5 validator-shim composition, §6.1 CLI-first V1, §8.4 Pass-2-tier-1-FORBIDDEN** — all spec LOCKS via Codex R9 convergence; do NOT re-open.
- **Behavioral changes to existing surfaces** — C.B introduces new modules only; no existing code should change behavior in C.B scope.

---

## §5 Return report shape

After all 14 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-bundle-C-B-return-report.md` (mirroring `docs/phase12-bundle-C-A-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (14 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Test count delta + ruff baseline delta + schema version delta (v19 unchanged — C.B touches no schema).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 3 surfaces).
5. Per-task deviations from plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (V2 candidates surfaced; Sub-sub-bundle C.C dispatch-readiness).
8. Worktree teardown status.
9. Per-task disposition LOCKS (any task-level decisions worth banking).
10. Forward-binding lessons for Sub-sub-bundle C.C (if commissioned).
11. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time.
12. Composition-surface verification: `^def` grep on `swing/trades/reconciliation_classifier.py` + `swing/trades/reconciliation_validators.py` confirming public surface matches plan §C acceptance criteria.
13. Determinism-contract verification evidence (T-B.1 100×-invocation test confirmed GREEN).
14. Pass-2-tier-1-FORBIDDEN verification evidence (T-B.4 all-input-shapes-tier-2 test confirmed GREEN against §8.4 LOCK).
15. Validator-respecting downgrade verification evidence (T-B.3 poisoned-validator_chain test confirmed GREEN).
16. Cross-bundle pin un-skip verification (T-B.14 — both pin tests pass post-un-skip).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 8-12 hr implementation + 2-4 hr Codex; total ~10-16 hr.

---

## §7 If you get stuck

- If plan §C binding contracts conflict with what spec §4/§5.5 says, **plan wins** (writing-plans Codex chain ratified plan §C; spec is upstream input).
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in plan's "open questions" + return report.
- If you need a schema element NOT in plan §C + spec §3/§4/§5.5, **STOP + escalate** (C.A return report lesson #7 + NEW lesson 2026-05-15 at `657b8a0`; bank-after-write costs 2-3 cascade-cleanup rounds).
- If a sub-classifier's logic doesn't fit cleanly into the spec §4.3 LOGIC enumeration (e.g., an unanticipated `source_payload` shape), emit `(tier=2, ambiguity_kind='unsupported', correction_reason="...")` and document in return report §9 (per-task disposition LOCKS) for orchestrator review. The dispatcher's failure-mode catch will route correctly; just be honest in `correction_reason`.
- DO NOT propose mapper widening within C.B scope (§4 lock; banked at plan §I.1).
- DO NOT propose journal mutations within C.B scope (§4 lock).
- DO NOT propose Schwab API calls within C.B scope (§4 lock).
- DO NOT add `apply_overrides` calls within C.B — no Schwab entry points in scope (banked for C.C/C.D inheritance).
- If you find a brief-vs-shipped-schema divergence (writing-plans return report §15.3 verified ZERO at plan-drafting time; if state has shifted since), STOP + escalate.
- If you encounter a Phase 7/8/9/10/11/12-A/12-B/12-C-A brainstorm lesson that conflicts with a C.B implementation proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a constraint.
- If Codex pushes back on the Pass-2-tier-1-FORBIDDEN LOCK at T-B.4 (e.g., "but the classifier could check the orders count and decide..."), HOLD THE LINE — the LOCK is spec §8.4 + Codex R6 Major #1 fix; V1 mapper exposes order-grain only, classifier cannot tier-1 from order-grain data, period. V2 mapper widening (plan §I.1) is the operator-locked path forward.
