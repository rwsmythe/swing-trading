# Phase 12 Sub-sub-bundle C.C (Auto-correction service + reconciliation flow pivot) — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-sub-bundle C.C (auto-correction service + reconciliation flow pivot + savepoint discipline + briefing.md extension + E2E integration test) of the Phase 12 Sub-bundle C implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` §D (C.C scope; 12 tasks T-C.1 … T-C.11 + T-C.3.1). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration:** ~12-18 hr implementation + ~3-6 hr Codex convergence. Total ~15-24 hr. C.C is the substantial service-layer + flow-pivot sub-sub-bundle; introduces 3 outer/inner service function pairs + per-(ambiguity_kind, choice_code) handlers + savepoint-per-discrepancy dispatcher loop at TWO reconciliation entry points + idempotency contract + briefing.md extension + slow-marked E2E integration test exercising CVGI 41 through the full pipeline.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-sub-bundle C.C (`PLAN_PATH=docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`, `SCOPE=Sub-sub-bundle C.C (T-C.1..T-C.11 + T-C.3.1 only)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 12 tasks land. Expected 4-6 Codex rounds (matches Phase 9 Sub-bundle B 5 rounds + Phase 12 Sub-sub-bundle C.B 5 rounds for service-layer-with-multi-entry-point scope). Plan §J + spec §7.1 savepoint discipline have already absorbed 1 Critical + 1 Minor from the writing-plans chain; execution rounds should taper faster.

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (3621 lines; Codex R6 confirmation NO_NEW_CRITICAL_MAJOR; LOCKED at `008dfe4`).
- **Sub-sub-bundle C.C section** is plan §D (lines 1604-2569). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §F cross-bundle pin matrix:** F-2 (C.A repo → C.C T-C.2/3/4), F-4 (C.B classifier → C.C T-C.5/6 pivot), F-5 (C.B validator dispatcher → C.C T-C.2/3/4), F-6 (C.C T-C.2 outer → C.C T-C.5/6 pivot — INTRA-C.C pin). F-2/F-4/F-5 already shipped + tests live; this dispatch consumes them. F-6 is exercised by T-C.5/T-C.6 discriminating tests.
- **Plan §G.3 C.C operator-witnessed gate** (4 surfaces; see §3 below).
- **Plan §A pre-verification:** writing-plans return report verified ZERO divergences between spec §3/§5 and shipped state on CHECK enums, repo signatures, transactional patterns; C.C inherits the empirical verification — do NOT re-grep at C.C dispatch time.

### §0.2 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (1444 lines; Codex R9 confirmation NO_NEW_CRITICAL_MAJOR; LOCKED at `d682c25`).
- **Read for §5 service architecture (BINDING — §5.1 module placement; §5.2 public interface; §5.3 transactional discipline + idempotency; §5.4 atomic flow for `apply_tier1_correction` 11-step sequence; §5.5 validator chain composition; §5.6 atomic flow for `apply_tier2_resolution`; §5.7 atomic flow for `apply_tier3_override`; §5.8 surface awareness; §5.9 sandbox short-circuit).**
- **Read §7 reconciliation flow pivot (BINDING — §7.1 pivot at `run_schwab_reconciliation` with savepoint-per-discrepancy LOCK; §7.2 OQ-2 PIVOT BOTH; §7.3 transaction nesting concern; §7.4 failure-mode contract; §7.5 operator-visible CLI output).**
- **Read §10 three discriminating-example walkthroughs:** §10.1 CVGI 41 (tier-1 path end-to-end through service); §10.2 DHC 39 (tier-2 pending ambiguity end-to-end); §10.3 VSAT 40 (classifier-data-dependent path).
- **Read §1.3 four operator-locked architectural constraints** + **§3 schema** (especially §3.1 `reconciliation_corrections` 20-column shape + §3.1.1 `correction_set_id` multi-column atomic correction + §3.5 `trade_events.event_type='reconciliation_auto_correct'`).

### §0.3 Project state at dispatch time

- **HEAD on `main`:** `d818219` (post-C.B-merge `aacd1cd` + post-merge housekeeping `d818219`). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **~4105 fast passing on main** + 3 pre-existing failures (`tests/integration/test_phase8_pipeline_walkthrough.py`) + skipped count includes 4 Schwab-fixture-not-present + 1 Task 7.3 flag-classifier (C.A's 2 cross-bundle pin tests un-skipped at C.B T-B.14 + now passing).
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 11 + Phase 12 A+B+C.A+C.B).
- **Schema version:** **v19** (C.A T-A.1 shipped 2026-05-15; production-migrated 2026-05-15T18:52:43; C.B consumer-side only).
- **Production discrepancy state:** 3 unresolved-material (39 DHC + 40 VSAT + 41 CVGI) + 30+ resolved historical. **LEFT UNRESOLVED BY DESIGN** pending Sub-sub-bundle C.D ship — C.C is service-layer + flow-pivot work; production discrepancies remain untouched until C.D backfill operation. C.C verifies the auto-correction flow end-to-end via planted-fixture E2E test, NOT against production rows.
- **Production refresh-token clock:** expires 2026-05-22T17:05:00+00:00 (~5 days remaining at dispatch). C.C does NOT exercise live Schwab API (E2E test mocks `_construct_pipeline_schwab_client`); refresh clock relevant only to C.D dispatch session.

### §0.4 Sub-sub-bundle C.C scope (12 tasks per plan §D)

| Task | Title | Files (illustrative; plan §D locks) |
|---|---|---|
| **T-C.1** | Service module skeleton + 3 exceptions (`CallerHeldTransactionError` / `ValidatorRejectedError` / `AlreadySupersededError`) + `CorrectionResult` dataclass + 3 outer/inner function pairs + transactional discipline scaffolding (reject caller-held; BEGIN IMMEDIATE; idempotency via SELECT-first) | NEW `swing/trades/reconciliation_auto_correct.py` + `tests/trades/test_reconciliation_auto_correct_transactional_discipline.py` |
| **T-C.2** | `_apply_tier1_correction_inner` body (CVGI 41 path; 11-step atomic flow per spec §5.4 — SELECT discrepancy; re-validate; UPDATE journal; `_recompute_aggregates`; INSERT `reconciliation_corrections`; UPDATE discrepancy resolution; UPDATE `review_log.superseded_by_correction_id` for closed-reviewed trade fills; emit `trade_events`) | MODIFY auto-correct module + NEW `tests/trades/test_apply_tier1_correction.py` |
| **T-C.3** | `_apply_tier2_resolution_inner` body + per-(ambiguity_kind, choice_code) handlers (multi_partial_vs_consolidated split-into-partials with `__delete__`/`__insert__` sentinels per spec §3.1.1 + §5.6; per-choice operator-payload validation per spec §6.2.1 + fresh forward-binding lesson #5 shape predicate tightening) | MODIFY auto-correct module + NEW `tests/trades/test_apply_tier2_resolution.py` |
| **T-C.3.1** | `stamp_pending_ambiguity` service helper (Codex R2 Major #1 fix at writing-plans time; idempotent stamp of `(resolution='pending_ambiguity_resolution', ambiguity_kind=..., resolution_reason=...)` on a discrepancy when classifier emits tier-2; used by T-C.5/T-C.6 dispatcher loops + T-D backfill) | MODIFY auto-correct module + NEW `tests/trades/test_stamp_pending_ambiguity.py` |
| **T-C.4** | `_apply_tier3_override_inner` body (operator-initiated post-tier-1 override; SELECT prior correction; verify current; INSERT new correction row with `correction_action='operator_overridden'`; UPDATE prior `superseded_by_correction_id`; UPDATE journal table to operator-truth; `_recompute_aggregates`; UPDATE discrepancy resolution; UPDATE `review_log.superseded_by_correction_id`; emit `trade_events`; raise `AlreadySupersededError` per OQ-15 disposition) | MODIFY auto-correct module + NEW `tests/trades/test_apply_tier3_override.py` |
| **T-C.5** | Reconciliation flow pivot at `run_schwab_reconciliation` Step 2 classify+dispatch loop with savepoint-per-discrepancy discipline (spec §7.1 LOCK; Codex R1 Critical #3 fix; R2 Minor #1 comment fix); fresh-savepoint fallback for tier-2 stamp on validator-rejection path; `summary_json` counters (`tier1_applied_count` / `tier2_pending_count` / `tier3_overridden_count`); sandbox short-circuit (apply returns no-op; counters reflect classification) | MODIFY `swing/trades/schwab_reconciliation.py` + MODIFY `tests/trades/test_run_schwab_reconciliation.py` + NEW `tests/trades/test_run_schwab_reconciliation_pivot.py` |
| **T-C.6** | Reconciliation flow pivot at `run_tos_reconciliation` (mirror of T-C.5 per OQ-2 PIVOT BOTH; same savepoint discipline + counters; TOS-CSV source semantics preserved) | MODIFY `swing/trades/reconciliation.py` + NEW `tests/trades/test_run_tos_reconciliation_pivot.py` |
| **T-C.7** | Savepoint discipline regression suite (savepoint isolation under partial UPDATE failure; outer-tx survives per-discrepancy savepoint rollback; SAVEPOINT name uniqueness; per-iteration RELEASE always fires; runs against BOTH Schwab + TOS pivots) | NEW `tests/trades/test_savepoint_discipline_reconciliation_pivot.py` |
| **T-C.8** | `BriefingInputs` extension (+`reconciliation_pending_count: int = 0` + `reconciliation_tier1_recent_count: int = 0`; back-compat preserved via defaults) | MODIFY `swing/rendering/briefing.py` + NEW `tests/rendering/test_briefing_inputs_reconciliation_extension.py` |
| **T-C.9** | `briefing_md.py` "Reconciliation status" section (rendered only when counters > 0 per spec §7.5; emit `swing journal discrepancy list-pending-ambiguities` + `resolve-ambiguity` CLI hints) | MODIFY `swing/rendering/briefing_md.py` + NEW `tests/rendering/test_briefing_md_reconciliation_section.py` |
| **T-C.10** | Wire `_step_export` to populate `BriefingInputs.reconciliation_*` (queries `reconciliation_corrections` + `reconciliation_discrepancies` for the 2 counters) | MODIFY `swing/pipeline/runner.py` + NEW `tests/pipeline/test_step_export_briefing_reconciliation_fields.py` |
| **T-C.11** | E2E integration test (CVGI 41 via full pipeline run; slow-marked; mirrors Phase 11 Sub-bundle D full-happy-path structure; plants CVGI-shaped trade + mocked Schwab orders; invokes pipeline; asserts reconciliation_run dispositioned tier-1 + `fills.price=$5.30` + `reconciliation_corrections` row + `trade_events` row + briefing.md "Reconciliation status" section emitted) | NEW `tests/integration/test_phase12_bundle_c_cvgi_41_full_pipeline.py` |

**Cross-bundle dependencies:** C.C CONSUMES C.A schema (`reconciliation_corrections` table; `ambiguity_kind` column; CHECK enum widenings) + C.B `classify_discrepancy` + C.B `default_validator_chain` + C.A `insert_correction` repo helper. C.D will CONSUME C.C `apply_tier2_resolution` (Tier-2 CLI) + `apply_tier3_override` (Tier-3 override CLI) + `stamp_pending_ambiguity` (backfill).

**Module boundaries (BINDING — preserve discipline):**
- `swing/trades/reconciliation_auto_correct.py`: SERVICE LAYER. Owns transactions (BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject caller-held). Composes over C.B classifier + validator chain + C.A repo. The 11-step atomic flow (spec §5.4) is the canonical sequence.
- Flow pivots at `run_schwab_reconciliation` + `run_tos_reconciliation`: ALREADY-OPEN transaction context. Use savepoint-per-discrepancy discipline (`SAVEPOINT correction_sp_<discrepancy_id>` → inner-function call → `RELEASE` on success / `ROLLBACK TO ... + RELEASE` on failure). Outer tx is the reconciliation_run row commit boundary; inner savepoints isolate per-discrepancy work without breaking the outer commit.
- `BriefingInputs` extension: dataclass-level only; not a base-layout VM (per §A.8) — no cross-bundle VM pin discipline impact.

### §0.5 BINDING contracts from plan §D + spec §5 + §7 (DO NOT re-litigate)

Per writing-plans return report + plan §D + spec §5/§7:

1. **Spec §5.3 transactional discipline LOCKED** — reject caller-held; BEGIN IMMEDIATE; `conn.commit()` at single happy-path COMMIT; `conn.rollback()` on any exception with `contextlib.suppress(sqlite3.Error)` defensive guard; idempotency contract via SELECT-first (terminal-state resolution returns existing correction_id WITHOUT new audit row).
2. **Spec §5.4 atomic flow for `apply_tier1_correction` LOCKED at 11 steps** — order matters; do not re-order. Step 4 validator re-invocation is defense-in-depth per fresh forward-binding lesson #2; Step 9 review_log cadence-period derivation is the Codex R1 Major #1 fix LOCKED (review_log is cadence-grain with NO trade_id column; mirror `complete_review_atomic` derivation pattern).
3. **Spec §5.5 validator chain composition LOCKED** — `functools.partial(default_validator_chain(conn), affected_table=..., affected_row_id=...)` is the canonical bridge between C.B `default_validator_chain` signature `(correction_target, *, affected_table, affected_row_id)` and dispatcher's single-arg invocation `validator_chain(correction_target)`. Apply at T-C.2 step 4 + T-C.5 pivot loop classifier-call.
4. **Spec §5.6 atomic flow for `apply_tier2_resolution` LOCKED** — per-(ambiguity_kind, choice_code) handler dispatch; `multi_partial_vs_consolidated` split-into-partials uses `__delete__`/`__insert__` sentinels per spec §3.1.1 + plan §I.20 (V1 audit-only narrowing); `correction_set_id` bundles N+1 rows.
5. **Spec §5.7 atomic flow for `apply_tier3_override` LOCKED** — raise `AlreadySupersededError` when target correction_id has non-NULL `superseded_by_correction_id` (per OQ-15 disposition); operator-truth value supersedes auto-applied via NEW correction row + UPDATE prior `superseded_by_correction_id`.
6. **Spec §5.8 surface awareness** — `surface='pipeline'` from `_step_schwab_orders` pivot path; `surface='cli'` from CLI invocations (C.D scope). C.C inherits caller's surface; does NOT widen the enum.
7. **Spec §5.9 sandbox short-circuit LOCKED** — under `environment='sandbox'`, returns `CorrectionResult(correction_id=None, notes='sandbox: domain write short-circuited')`; discrepancy stays `unresolved`; pivot counters reflect classification (tier1/tier2) but `tier1_applied_count` STAYS 0 because the inner short-circuits. Audit rows in `schwab_api_calls` ARE written per shipped gating.
8. **Spec §7.1 savepoint-per-discrepancy discipline LOCKED** — `SAVEPOINT correction_sp_<discrepancy_id>` per iteration; RELEASE on success; ROLLBACK TO + RELEASE on failure; validator-rejection fallback path uses a FRESH `correction_fallback_sp_<discrepancy_id>` (do NOT reuse the already-released sp_name; Codex R2 Minor #1 comment fix). Outer reconciliation_run tx survives per-discrepancy failures.
9. **Spec §7.2 OQ-2 PIVOT BOTH LOCKED** — both `run_schwab_reconciliation` AND `run_tos_reconciliation` get the pivot; TOS-CSV source semantics differ from Schwab API trust premise but pivot logic is identical (per-discrepancy-type sub-classifier handles source-specific nuance internally).
10. **Spec §7.4 graceful degradation contract LOCKED** — pipeline NEVER raises out of pivot loop; classifier/apply exceptions caught + logged WARNING + savepoint rolled back; outer tx continues; counters reflect dispositioned vs errored.
11. **CVGI 41 + DHC 39 + VSAT 40 discriminating fixtures** — spec §10 walkthroughs are BINDING for the T-C.5 pivot tests + T-C.11 E2E test. CVGI 41 = tier-1 entry_price_mismatch end-to-end; DHC 39 = tier-2 pending ambiguity (Pass-2 required signal in correction_reason); VSAT 40 = mirror of DHC 39.

### §0.6 Forward-binding lessons inherited (BINDING for C.C)

**51 cumulative lessons** through C.B (Phase 11 17 + Phase 12 A 5 + B 12 + C brainstorm 5 + C writing-plans 2 + C.A 3 + C.B 7 = 51).

Particularly load-bearing for C.C service-layer + flow-pivot work (see CLAUDE.md gotchas + `docs/orchestrator-context.md` §"Lessons captured" updated 2026-05-15 with the 7 C.B lessons):

1. **Classifier output is C.B → service-layer enforcement is C.C boundary (NEW C.B lesson #1).** Pinned at §0.5 #2 above. Lifecycle invariants on `reconciliation_corrections` rows (`correction_action='auto_applied'` implies `applied_by='auto'`; tier-3 override requires non-null `operator_truth_value_json`; tier-1 cannot land with non-NULL `ambiguity_kind`) MUST be enforced at C.C `apply_tier1_correction` INSERT time, NOT at classifier-output time. Push back on Codex framings that ask the classifier to do C.C's enforcement work.
2. **Validator chain MUST re-invoke at C.C apply time (NEW C.B lesson #2).** Pinned at §0.5 #2 above (step 4). Defense-in-depth: schema state may shift between classifier run + service apply (backfill scenario; concurrent state mutation by another surface; FK shift via DELETE elsewhere). Pre-empt false-economy "we already validated, skip the service-side check" anti-pattern via discriminating test (inject state-shift between classifier + apply + assert service rejects).
3. **`functools.partial` composition between `default_validator_chain` + `classify_discrepancy` (NEW C.B lesson #3).** Pinned at §0.5 #3 above. Add integration test at T-C.5 Step 5 that exercises end-to-end composition + asserts the validator_chain partial correctly receives `affected_table` + `affected_row_id` at the right callsite.
4. **`_pass_2_required=True` free-form-string convention in `correction_reason` (NEW C.B lesson #4).** C.C does NOT consume this signal directly (it's the C.D backfill's concern); but C.C tier-2 stamp via T-C.3.1 `stamp_pending_ambiguity` should preserve the classifier's `correction_reason` verbatim so C.D substring match works post-stamp. Discriminating test at T-C.3.1: stamp tier-2 discrepancy with `_pass_2_required=True` in classifier-output reason + assert post-stamp `resolution_reason` contains the substring.
5. **Shape predicate tightening discipline (NEW C.B lesson #5).** Applies to operator-supplied `--custom-value` payloads in T-C.3 §5.6 handlers. Implement explicit input-shape checks at handler entry: reject unrecognized key sets; reject contradictory evidence within the payload. Discriminating test pattern: per-handler, 4-case parametrize (correct-shape happy / unrecognized-key reject / contradictory-field reject / missing-required-field reject).
6. **Same-source-keys-on-source-and-journal evidence convergence (NEW C.B lesson #6).** Relevant to T-C.3 multi-field tier-2 resolutions where the operator-payload mirrors source-side keys. If a payload field has redundant representations (e.g., `qty` + `quantity`; `date` + `fill_datetime`), require internal-consistency check.
7. **Co-Authored-By footer drift requires EXPLICIT suppression in dispatch prompts (NEW C.B lesson #7).** Carry-forward to C.C: this dispatch's inline prompt MUST explicitly cite the "No Claude co-author footer" CLAUDE.md binding convention. Per fresh lesson, passive CLAUDE.md inheritance is insufficient because subagents have isolated context. See §1.3 below for binding language.
8. **`apply_overrides` discipline at Schwab entry points (Sub-bundle B lesson #6).** Relevant to T-C.5 — `run_schwab_reconciliation` composes over `_construct_pipeline_schwab_client`. Verify cascade-resolved Schwab credentials are threaded through the pivot loop end-to-end via mock-based integration test (per Sub-bundle A T-A.3 implementer-gap pre-emption pattern + Sub-bundle B lesson #12). T-C.5 Step 5 already specifies this; do NOT skip.
9. **Per-row policy stamping (Phase 8 R1 M5).** `reconciliation_corrections.risk_policy_id_at_correction` populated at INSERT time via `_get_active_risk_policy_id(conn)` helper. C.C T-C.2 step 7 INSERT signature accepts policy_id; T-C.5 dispatcher pivot supplies it.
10. **`INSERT OR REPLACE` prohibition (CLAUDE.md gotcha).** Step 5 of T-C.2 atomic flow is `UPDATE` only on affected journal tables. `_recompute_aggregates` at step 6 mirrors Phase 7 `insert_fill_with_event` pattern; NO `INSERT OR REPLACE` on `fills` or any FK-referenced table.
11. **SQLite `executescript()` implicit COMMIT (CLAUDE.md gotcha).** Not directly C.C-load-bearing (no migrations in C.C scope); but if any test fixture uses `executescript` to plant multi-statement schema state, the same discipline applies — avoid bare `executescript()`; use explicit `BEGIN`+statements+`COMMIT` envelope.
12. **USERPROFILE+HOME monkeypatch discipline (Phase 9 Sub-bundle A gotcha).** C.C test fixtures touching `~/swing-data/` paths MUST monkeypatch both env vars to tmp_path. T-C.11 slow-marked E2E test exercises a full pipeline run + likely touches the user-config cascade; preserve the discipline.
13. **HTMX gotcha trinity (Sub-bundle B lesson #11).** N/A for C.C scope — no web routes; banked for C.D inheritance.

### §0.7 Sub-sub-bundle C.C test projection

Per plan §H.1: **+65-115 fast tests projected** (plus 1 slow-marked E2E integration test at T-C.11). Per Phase 9/10/12 overshoot precedent (A overshoot +35→actual; A+B+C cumulative +315 vs projected +220-380), C.B actual +139 vs projected +85-130 — **actual likely +95-160 fast tests** for C.C.

Final main HEAD post-C.C-merge: ~4200-4265 fast tests (was ~4105 + +95-160).

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-bundle-C-C-auto-correction-service-and-flow-pivot`
- **Worktree directory:** `.worktrees/phase12-bundle-C-C-auto-correction-service-and-flow-pivot/`
- **BASELINE_SHA:** `d818219` (current main HEAD pre-brief-commit; resolve via `git rev-parse main` at worktree-creation time after this brief lands).
- **Branch naming intent:** `phase12-bundle-C-C-*` matches the cleanup-script `phase\d+[-_]` regex; operator's `-DeregisterFirst` pass cleans cleanly post-merge.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 12 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes:
  - `feat(phase12-bundle-c-T-C.1): <description>` for service module skeleton + exceptions
  - `feat(phase12-bundle-c-T-C.2..4): <description>` for inner-function bodies + handlers
  - `feat(phase12-bundle-c-T-C.3.1): <description>` for `stamp_pending_ambiguity` helper
  - `feat(phase12-bundle-c-T-C.5..6): <description>` for flow pivots
  - `test(phase12-bundle-c-T-C.7): <description>` for savepoint regression suite
  - `feat(phase12-bundle-c-T-C.8..10): <description>` for briefing extension + wire
  - `test(phase12-bundle-c-T-C.11): <description>` for E2E integration test (slow-marked)
  - `fix(phase12-bundle-c-C): Codex RN <severity> #N — <description>` for Codex-driven fixes
- **NO Claude co-author footer.** This is a CLAUDE.md binding convention. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) — do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message. Subagent context starts isolated; the Bash tool's default footer template is NOT authoritative for this project — CLAUDE.md is. C.B R1 fix-bundle 4 commits carried the footer accidentally + required orchestrator-side rebase-strip pre-merge; this dispatch MUST NOT repeat the pattern.
- **NO `--no-verify`**, **NO `--amend`** (per CLAUDE.md binding conventions: prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §D mark per-step boundaries.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree until C.C integration commit (T-C.11 worktree push).
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-sub-bundle C.D dispatch commissioning.

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~15..HEAD
python -m pytest -m "not slow" -q
python -m pytest -m slow tests/integration/test_phase12_bundle_c_cvgi_41_full_pipeline.py -v   # T-C.11 E2E
ruff check swing/ --statistics
python -c "from swing.trades.reconciliation_auto_correct import apply_tier1_correction, apply_tier2_resolution, apply_tier3_override, stamp_pending_ambiguity, CallerHeldTransactionError, ValidatorRejectedError, AlreadySupersededError, CorrectionResult; print('auto_correct OK')"
```

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 12 tasks land + tests GREEN.

**Expected chain shape:** 4-6 substantive Codex rounds (matches Phase 9 Sub-bundle B 5 rounds + Phase 12 Sub-sub-bundle C.B 5 rounds for similar service-layer scope). Plan §J + spec §7.1 absorbed 1 Critical + 1 Minor at writing-plans time — execution rounds should taper faster. Convergent tapering per Phase 8 R2-R5 + Phase 9/10/11/12 lesson family.

**Adversarial review watch items (C.C-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **Transactional discipline LOCK** (spec §5.3). All 3 public outer functions reject caller-held tx; BEGIN IMMEDIATE; happy-path COMMIT; exception-path ROLLBACK with `contextlib.suppress(sqlite3.Error)` guard; re-raise. Discriminating test at T-C.1 covers all 3 functions.
2. **Idempotency contract LOCK** (spec §5.3). Inner functions begin with SELECT discrepancy resolution; terminal-state → return existing correction_id WITHOUT new audit row. Discriminating test plants a terminal-state discrepancy + invokes apply + asserts no new audit row written.
3. **11-step atomic flow LOCK at T-C.2** (spec §5.4). Order matters; do NOT re-order. Step 4 validator re-invocation defense-in-depth + Step 9 review_log cadence-period derivation (mirror `complete_review_atomic` pattern; cadence-grain table has NO trade_id; derive via close-date + period boundary join).
4. **Validator-respecting downgrade at T-C.5 pivot** (spec §5.4 step 4 + §7.1). `_apply_tier1_correction_inner` raises `ValidatorRejectedError` on validator False; outer pivot catches + falls through to tier-2 stamp via FRESH savepoint (do NOT reuse already-released sp_name; Codex R2 Minor #1 fix).
5. **Savepoint-per-discrepancy discipline LOCK** (spec §7.1). Each iteration: `SAVEPOINT correction_sp_<discrepancy_id>` → call inner → `RELEASE` on success / `ROLLBACK TO + RELEASE` on failure. Discriminating test: rig 1 of 3 discrepancies to raise + assert other 2 land normally + outer tx commits + no leaked savepoints.
6. **OQ-2 PIVOT BOTH** (spec §7.2). T-C.6 mirrors T-C.5 verbatim for TOS-CSV; pivot logic identical. Discriminating test plants TOS CSV with 1 entry_price_mismatch + 1 unmatched_open_fill + asserts both dispositioned correctly.
7. **Sandbox short-circuit LOCK** (spec §5.9). Under `environment='sandbox'`, inner returns `CorrectionResult(correction_id=None, notes='sandbox: ...')`; discrepancy stays `unresolved`; pivot `tier1_applied_count` STAYS 0. Discriminating test plants tier-1 candidate under sandbox + asserts no journal mutation + no `reconciliation_corrections` INSERT + counters reflect classification-only.
8. **Sub-bundle A T-A.3 implementer-gap pre-emption at T-C.5** (Sub-bundle B forward-binding lesson #12). Mock `_construct_pipeline_schwab_client` + assert cascade-resolved Schwab credentials threaded through the pivot end-to-end. Verify `apply_overrides(cfg)` is consumed at the Schwab entry point per Sub-bundle B lesson #6 invariant.
9. **`functools.partial` composition LOCK** (NEW C.B forward-binding lesson #3). T-C.5 pivot loop invokes classifier with `validator_chain=functools.partial(default_validator_chain(conn), affected_table=..., affected_row_id=...)`. Verify the partial-application is correct (affected_table + affected_row_id derived from discrepancy's FK; not hardcoded).
10. **Review_log cadence-period derivation LOCK at T-C.2 step 9** (Codex R1 Major #1 fix; spec §5.4). review_log is cadence-grain with NO trade_id column. Derive via close-date + period boundary join. Discriminating test plants a closed-reviewed trade's fill + applies tier-1 correction + asserts matching review_log row's `superseded_by_correction_id` gets stamped.
11. **`__delete__` + `__insert__` sentinels at T-C.3** (spec §3.1.1 + §5.6). multi_partial_vs_consolidated split-into-partials handler writes N+1 audit rows bundled under one `correction_set_id`; sentinel rows preserve forensic trail.
12. **`AlreadySupersededError` at T-C.4** (spec §5.7 + OQ-15). Raised when target correction has non-NULL `superseded_by_correction_id`. Discriminating test plants a superseded chain + invokes tier-3 override + asserts exception raised + no new audit row.
13. **20-column LOCK preservation at C.A schema** (C.A return report lesson #5). C.C INSERTs into `reconciliation_corrections` MUST use the 20-column shape; do NOT add columns inline. If Codex surfaces a need for a new audit column, STOP + escalate.
14. **Schema-CHECK + Python-validator paired work (C.A return report lesson #1).** C.C INSERTs `correction_action` values from the 4-value enum (`auto_applied` / `operator_resolved_ambiguity` / `operator_overridden` / `manual_override`). Verify the values match the shipped `_CORRECTION_ACTION_VALUES` tuple in `swing/data/models.py` verbatim.
15. **NO behavioral changes to NON-pivot existing surfaces.** C.C modifies `swing/trades/schwab_reconciliation.py` (pivot Step 2) + `swing/trades/reconciliation.py` (pivot Step 2 mirror) + `swing/rendering/briefing.py` + `swing/rendering/briefing_md.py` + `swing/pipeline/runner.py:_step_export`. NO other production files should change. Codex SHOULD verify the touch surface is bounded.
16. **Plan-author schema additions during executing-plans cycle (C.A return report lesson #7).** If Codex surfaces a need for a schema element NOT in plan §D + spec §3 (e.g., new audit column; new CHECK enum value; new FK relationship), the implementer MUST STOP + escalate to orchestrator BEFORE adding inline. Cost of bank-after-write: 2-3 cascade-cleanup rounds.

---

## §3 Operator-witnessed verification gate (Sub-sub-bundle C.C integration)

Per plan §G.3 (4 surfaces) + spec §15.5:

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q` | GREEN at ~4200-4265 fast tests (worktree-side; +95-160 net from ~4105 baseline; upper-half overshoot precedent); 3 pre-existing phase8 walkthrough failures unchanged; skipped count unchanged. T-C.11 slow-marked E2E test PASSES under `-m slow`. |
| **S2** | Simulated reconciliation run end-to-end with planted tier-1 + tier-2 discrepancies (`environment='production'`) | Operator-driven walkthrough OR test-coverage-equivalent. Create fresh tmp DB; plant CVGI-shaped trade + 1 DHC-shaped trade; plant mocked Schwab orders responses with divergent prices; invoke `run_schwab_reconciliation(...)` end-to-end. Assert: CVGI discrepancy → `resolution='auto_corrected_from_schwab'`; `fills.price=$5.30`; `reconciliation_corrections` row exists; `trade_events` row exists. DHC discrepancy → `resolution='pending_ambiguity_resolution'`, `ambiguity_kind` populated. `reconciliation_runs.state='completed'`; `summary_json` includes `tier1_applied_count: 1, tier2_pending_count: 1`. Operator deliberately rigs a validator failure (e.g., poison proposed CVGI price to negative via test monkeypatch); re-runs; asserts CVGI falls through to tier-2 with `ambiguity_kind='validator_rejected'`. |
| **S3** | Sandbox short-circuit test (same scenario as S2 with `environment='sandbox'`) | CVGI discrepancy emitted BUT NOT auto-corrected; `resolution='unresolved'`; `fills.price` unchanged. DHC discrepancy emitted; `resolution='unresolved'` (NOT `pending_ambiguity_resolution` because sandbox short-circuits classifier output → audit-only state). `summary_json.tier1_applied_count == 0`. WARNING log lines emitted citing "sandbox: ..." per `apply_tier1_correction` sandbox branch. |
| **S4** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged. |

**Gate session ≤ 4 surfaces budget:** all 4 inline-or-script-driven. S1+S4 inline (2). S2+S3 operator-driven via test harness OR SKIPPED-with-test-coverage if T-C.5/T-C.6 + sandbox unit tests provide equivalent coverage (matches polish-bundle-2026-05-10 + Phase 9 Sub-bundle A precedent). No browser-driven surfaces in C.C scope (no HTMX form work; no web routes). No production-write surfaces (C.C exercises planted-fixture DBs only; production reconciliation runs not exercised at C.C gate — that's C.D backfill operation).

**Production state post-gate:** ZERO behavioral changes to existing production discrepancies (39 / 40 / 41). C.C ships service + flow-pivot infrastructure consumed by C.D backfill; production reconciliation flow at `run_schwab_reconciliation` + `run_tos_reconciliation` is pivoted but next pipeline run + manual `swing journal reconcile-*` CLI invocation will exercise the new pivot — operator should expect new tier-1/tier-2 dispositions IF a new reconciliation_run is triggered post-merge with the 3 stale discrepancies STILL queued. **Recommendation: do NOT trigger a new reconciliation_run between C.C merge + C.D ship**; let C.D backfill operation be the canonical first exercise against production discrepancies.

**Production-write classifier soft-block awareness:** N/A — C.C has no production writes at gate time (gate uses tmp-DB fixtures). No AskUserQuestion surfaces needed at gate.

---

## §4 OUT OF SCOPE (do not do)

- **C.D Tier-2 CLI surface scope** — `swing journal discrepancy show-ambiguity|resolve-ambiguity|override-correction` + `swing journal reconcile-backfill` CLIs + Phase 10 dashboard banner predicate widening + production backfill of 39/40/41. Ships in Sub-sub-bundle C.D.
- **Web Tier-2 surface** — spec §6.1 LOCK V1 CLI-only; web is V2 candidate (banked at plan §I.3). NOT C.C scope.
- **Schema additions or migrations** — per C.A return report lesson #7 + NEW lesson 2026-05-15 at `657b8a0`. If C.C implementer encounters a need for a schema element NOT in plan §D + spec §3, STOP + escalate to orchestrator BEFORE adding inline. Do NOT bank-after-write.
- **V2 mapper widening + auto-VWAP classifier path** — operator-locked next-architectural-dispatch slot (post-C.D ship). Banked at plan §I.1. NOT C.C scope.
- **New classifier sub-classifiers** — C.B already shipped 10 sub-classifiers for the 10 discrepancy_type enum values. C.C composes over the classifier as a consumer; do NOT add new sub-classifiers.
- **New validator predicates** — C.B already shipped 4 dry-run validators + `default_validator_chain` dispatcher. C.C composes via `functools.partial`; do NOT add new validators.
- **Behavioral changes to existing surfaces beyond the locked touch list** — C.C touches: `swing/trades/reconciliation_auto_correct.py` (NEW); `swing/trades/schwab_reconciliation.py` (pivot Step 2); `swing/trades/reconciliation.py` (pivot Step 2 mirror); `swing/rendering/briefing.py` (BriefingInputs extension); `swing/rendering/briefing_md.py` (Reconciliation status section); `swing/pipeline/runner.py:_step_export` (counters wire). NO other production files should change.
- **Re-litigating spec §1.3 four operator-locked architectural constraints** — accepted as given.
- **Re-litigating §5.3/5.4/5.5/5.6/5.7/5.8/5.9 service-layer LOCKS, §7.1/7.2/7.3/7.4/7.5 flow-pivot LOCKS** — all spec LOCKS via Codex R9 convergence; do NOT re-open.

---

## §5 Return report shape

After all 12 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-bundle-C-C-return-report.md` (mirroring `docs/phase12-bundle-C-B-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (12 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Test count delta + ruff baseline delta + schema version delta (v19 unchanged — C.C touches no schema).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 4 surfaces).
5. Per-task deviations from plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (V2 candidates surfaced; Sub-sub-bundle C.D dispatch-readiness).
8. Worktree teardown status.
9. Per-task disposition LOCKS (any task-level decisions worth banking).
10. Forward-binding lessons for Sub-sub-bundle C.D (if commissioned).
11. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time.
12. Composition-surface verification: `^def` grep on `swing/trades/reconciliation_auto_correct.py` confirming public surface matches plan §D acceptance criteria.
13. Transactional-discipline verification evidence (T-C.1 reject-caller-held + idempotency tests confirmed GREEN against all 3 outer functions).
14. Savepoint-discipline verification evidence (T-C.7 regression suite confirmed GREEN against both Schwab + TOS pivots).
15. Sandbox short-circuit verification evidence (sandbox tests confirmed GREEN — no journal mutation; counters reflect classification-only).
16. E2E integration test verification evidence (T-C.11 slow-marked test confirmed GREEN; CVGI 41 full pipeline run dispositions tier-1 + emits briefing.md "Reconciliation status" section).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 12-18 hr implementation + 3-6 hr Codex; total ~15-24 hr.

---

## §7 If you get stuck

- If plan §D binding contracts conflict with what spec §5/§7 says, **plan wins** (writing-plans Codex chain ratified plan §D; spec is upstream input).
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in plan's "open questions" + return report.
- If you need a schema element NOT in plan §D + spec §3, **STOP + escalate** (C.A return report lesson #7 + NEW lesson 2026-05-15 at `657b8a0`; bank-after-write costs 2-3 cascade-cleanup rounds).
- If a per-(ambiguity_kind, choice_code) handler at T-C.3 needs an enumeration NOT in spec §6.2.1, STOP + escalate (spec §6.2.1 is LOCKED post-Codex chain; new ambiguity_kind or choice_code values require spec amendment).
- If T-C.2 step 9 review_log cadence-period derivation surfaces edge cases not covered by `complete_review_atomic` precedent, log as deviation in return report §9 (per-task disposition LOCKS) for orchestrator review.
- DO NOT propose new classifier sub-classifiers or new validators within C.C scope (§4 lock).
- DO NOT propose web Tier-2 surface within C.C scope (§4 lock; V2 candidate at plan §I.3).
- DO NOT propose schema additions within C.C scope (§4 lock; lesson #7 family).
- DO NOT add `Co-Authored-By` footer to any commit message (per §1.3 + fresh forward-binding lesson #7; C.B R1 fix-bundle precedent of accidental drift required orchestrator-side rebase-strip pre-merge — do NOT repeat).
- If you encounter a Phase 7/8/9/10/11/12-A/12-B/12-C-A/12-C-B brainstorm or return-report lesson that conflicts with a C.C implementation proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a constraint.
- If Codex pushes back on the savepoint discipline at T-C.5 / T-C.6 (e.g., "but a single tx is simpler..."), HOLD THE LINE — the LOCK is spec §7.1 + Codex R1 Critical #3 fix at writing-plans time; savepoint isolation is what allows the outer reconciliation_run tx to survive per-discrepancy failures with graceful degradation per spec §7.4.
- If Codex pushes back on the cadence-period review_log derivation at T-C.2 step 9 (e.g., "just JOIN on trade_id..."), HOLD THE LINE — review_log shipped at Phase 6 + migration 0013 + `complete_review_atomic` derivation pattern verified empirically at writing-plans time (Codex R1 Major #1 fix; spec §5.4 step 9 LOCK).
