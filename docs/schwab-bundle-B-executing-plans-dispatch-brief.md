# Schwab API Sub-bundle B — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance dispatched as the Schwab API Sub-bundle B executing-plans implementer. No prior conversation context.

**Mission:** Execute Sub-bundle B of the Schwab API integration plan via `copowers:executing-plans`. Sub-bundle B wires **Trader API consumption** + `_step_schwab_snapshot` + `_step_schwab_orders` pipeline steps + new `run_schwab_reconciliation` service + sandbox-gating discipline + CLI `swing schwab fetch` subcommands + `SchwabPipelineActiveError` cross-surface exclusion. Lands on a worktree branch; orchestrator owns integration merge to main post-operator-witnessed-gate.

**Expected duration:** ~6-10 hr including ~3-4 Codex rounds. Per plan §0.4 Sub-bundle B round estimate (Trader API endpoint wiring is well-understood; sandbox-gating discipline is well-trodden post-spec). 9 tasks (T-B.0.b..T-B.8); +80 fast tests projected (range +75..+95).

---

## §0 Inputs

### §0.1 Plan (canonical scope source)

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- **SUB_BUNDLE:** `B` (Tasks T-B.0.b..T-B.8 inclusive).
- **Plan Sub-bundle B section:** §Tasks-B at line 2048+ (per-task scope + acceptance criteria + discriminating-test patterns + commit message stems).

### §0.2 Sub-bundle A SHIPPED context (BINDING)

- **A merged at `5b6e5ba`** (2026-05-14; --no-ff preserved Codex-fix chain). 4 Codex rounds → NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked (R2 Minor #2 force_refresh unchanged-token integrity).
- **Sub-bundle A return report at `docs/schwab-bundle-A-return-report.md`** (`6550494`; on main post-merge) — READ §6 (watch items) + §8 (5 forward-binding lessons) + §12 (Sub-bundle B dispatch checklist) END-TO-END.
- **Sub-bundle A T-A.0.b recon doc at `docs/schwab-bundle-A-task-A0b-recon.md`** — READ §6 + §6.bis as LOCKED inputs (operator-paired live verification observations).

### §0.3 BINDING distilled references (orchestrator-action items per phase3e-todo)

Both reference dirs are BINDING §0 reads:

- `reference/schwab-api/{account,market-data}-{documentation,specification}.md` — Schwab Developer Portal canonical docs (4 distilled MDs).
- `reference/schwabdev/{setup-guide,examples,client,api-calls,streaming,orders,troubleshooting}.md` — schwabdev library docs (7 distilled MDs).

**For Sub-bundle B specifically — pre-check FIRST before scheduling any operator-paired Task 0.b session:**

1. **`reference/schwabdev/api-calls.md`** (25 KB) — 23 wrapper methods → 23 Schwab REST endpoints with verbatim mapping. The 3 accounts + 7 orders + 2 transactions endpoints Sub-bundle B consumes are documented HERE. May pre-answer most Q14 scope-string + Q8 base-URL items already.
2. **`reference/schwabdev/client.md`** (14 KB) — `Client`/`ClientAsync` constructor (8 params verified at A T-A.0.b); rate limits **120 req/min + 4000 orders/day**; 30-min access + 7-day refresh lifecycle. Pre-answers Q17 (Market Data API rate limits TBD; Trader API limits documented).
3. **`reference/schwab-api/account-documentation.md` + account-specification.md** — Schwab's published Trader API docs. Higher-fidelity than synthesized §E.2.
4. **`reference/schwabdev/troubleshooting.md`** (8 KB) — `unsupported_token_type` → `update_tokens(force_refresh_token=True)`; trailing-slash callback fix. **Threading reminder for Sub-bundle D status alerts.**

### §0.4 Sub-bundle A 5 forward-binding lessons (BINDING for Sub-bundle B)

Per Sub-bundle A return report §8 — Sub-bundle B implementer MUST honor these:

1. **schwabdev silent-failure-mode discipline.** `Client.__init__` + `update_tokens()` do NOT raise on auth failure; they print + retry + return silently. Wrappers MUST verify post-call state (`client.tokens.access_token` populated + rotated). **Discriminating-test pattern:** stub schwabdev call to NOT mutate `tokens.access_token`; assert wrapper raises `SchwabAuthError` + audit row `status='auth_failed'`.
2. **Audit-success-fire ordering.** `record_call_finish(status='success', ...)` MUST fire ONLY after all validation passes. Pattern: validate response shape → validate response content → validate operator-pickable state → fire success audit. Each pre-success rejection path fires `record_call_finish(status='auth_failed')` with redacted `error_message` + raises.
3. **Pre-call factory-replacement defense.** `ensure_schwab_log_redaction_factory_installed()` (NOT `_install_*`) before every schwabdev API call. **Discriminating-test pattern:** install third-party factory between two schwab calls; assert second call re-wraps the factory before invoking schwabdev.
4. **Redact-then-truncate audit-error ordering.** `_redacted_excerpt` MUST redact on FULL `str(exc)` THEN truncate to audit-column-budget. **Discriminating-test pattern:** register a sentinel that straddles the truncation boundary; assert no partial-prefix survives.
5. **schwabdev 2.5.1 actual surfaces** (banked from A phase-2 live verification):
   - `Client` ctor: 8 params (`app_key, app_secret, callback_url='https://127.0.0.1', tokens_file='tokens.json', timeout=10, capture_callback=False, use_session=True, call_on_notify=None`).
   - Tokens DB content: **JSON (NOT SQLite)**; content shape `{access_token_issued, refresh_token_issued, token_dictionary: {access_token, refresh_token, id_token, expires_in: 1800, token_type, scope}}`.
   - `client.account_linked()` success: list of dicts `[{accountNumber, hashValue}, ...]`.
   - `client.account_linked()` failure: dict error envelope (NOT a list).
   - Force-refresh kwarg: `client.update_tokens(force_access_token=True)` (NOT `force_refresh_token=True` which triggers full OAuth dance).
   - Schwab `code` expiry window: ~30 seconds from redirect.
   - **Logger name: `"Schwabdev"` (capital S — live deviation from plan §H.8 lowercase).**
   - NO `revoke()` method exposed; use manual `POST /v1/oauth/revoke`.

### §0.5 Codex chain pre-emption table (per Sub-bundle A return report §12 #6)

Sub-bundle A's 4 Codex rounds caught these patterns; pre-empt in Sub-bundle B implementation BEFORE writing tests:

| Pattern family | Sub-bundle A surface | Sub-bundle B applicability |
|---|---|---|
| **Silent-failure post-call validation** (M#1 family) | `setup` + `force_refresh` + `accounts.linked` empty-list ordering | EVERY schwabdev call in `trader.py` (account_details, account_orders, transactions) — wrap + verify post-call state. |
| **Audit-success-fire ordering** (M#3 family) | `accounts.linked` empty-list logged success-then-error | EVERY `record_call_finish('success', ...)` MUST follow ALL validation passes. |
| **Factory-replacement defense** (M#2 family) | `ensure_*` (not `_install_*`) on hot paths | EVERY schwabdev API call in `trader.py` calls `ensure_schwab_log_redaction_factory_installed()` first. |
| **Redact-then-truncate audit-error** (R3 M#1 family) | `_redacted_excerpt` boundary-straddle leak | `_redacted_excerpt` (already shipped in A) is consumed VERBATIM; do NOT re-implement. |

### §0.6 Inter-bundle dependencies (verify before commit)

- **`SchwabClient` instance:** Sub-bundle B's `trader.py` MUST consume the SAME `SchwabClient` instance constructed in `swing/integrations/schwab/client.py` (per multi-Client-instance gotcha from schwabdev distillation Finding 2). Discriminating test pattern: `grep schwabdev.Client swing/integrations/schwab/ | wc -l == 1` (only `client.py:SchwabClient.__init__` invokes the library directly).
- **`ReconciliationRun.schwab_api_call_id` field already exists** at branch-tip (A R1 M#5 landed it: `_RUN_SELECT_COLUMNS` + `_row_to_run` + `insert_run` + `get_run` + `list_recent_runs` round-trip; `ReconciliationRun` dataclass field at end of field ordering). **DO NOT re-implement.** B's `run_schwab_reconciliation` populates it via existing `insert_run(..., schwab_api_call_id=<int>)` kwarg.
- **Audit service-layer wrappers already exist** at `swing/integrations/schwab/audit_service.py`: `record_call_start`, `record_call_finish`, `link_snapshot_and_stamp_account_hash` (combined-tx2), `link_reconciliation_run`. Sub-bundle B consumes these verbatim; OWNS BEGIN IMMEDIATE / COMMIT / ROLLBACK + REJECTS caller-held tx (raises `CallerHeldTransactionError`).
- **Source-ladder write path:** consume `record_snapshot(source='schwab_api', source_artifact_path='schwab_api:call/<call_id>', recorded_by='schwab_api', ...)` per Phase 9 Sub-bundle C verbatim (NO re-design); reconciliation INSERT uses `source='schwab_api'` per existing CHECK enum.

### §0.7 Project state at dispatch time

- **HEAD on `main`:** `4efc059` (post-Sub-bundle-A-merge housekeeping + pip-framing correction).
- **Test count baseline:** ~3496 fast passing on main (+209 net from pre-A baseline 3287; per Sub-bundle A integration merge). 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures (NOT regressions). 2 cross-bundle pins SKIPPED (un-skip targets: T-B.8 + T-C.7).
- **Test runtime:** ~72s wall-clock at `-n auto` default.
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v18 (Sub-bundle A T-A.7 landed).
- **Production tokens DB:** `~/swing-data/schwab-tokens.production.db` exists with valid 30-min access + 7-day refresh tokens. **7-day refresh-token clock started 2026-05-14** — Sub-bundle B work should complete + integrate before ~2026-05-21 OR operator re-runs `swing schwab setup` paste-back to extend.

### §0.8 Q1-Q18 dispositions still LOCKED (DO NOT re-litigate)

Per writing-plans dispatch brief §0.3 + §0.3a + Sub-bundle A return report. All Q-dispositions remain BINDING for Sub-bundle B:

- Q1 production-tier (Schwab Developer Portal app already approved + tokens persisted via A).
- Q3 V1 single-primary-account.
- Q11 V1 INCLUDE market-data ladder (Sub-bundle C scope; not B).
- Q18 COA B (`schwabdev` library).
- Q8/Q12/Q13-residual/Q14/Q15/Q17 deferred to Task 0.b (some pre-answered by `reference/schwab-api/` + `reference/schwabdev/api-calls.md` — implementer pre-checks).

### §0.9 Sub-bundle B scope-summary (per plan §Tasks-B)

9 tasks; +80 fast tests projected. **Per-task summary** (full per-task content in plan §Tasks-B line 2050+):

| Task | Scope | Tests | Files touched |
|---|---|---:|---|
| **T-B.0.b** | **Operator-paired live verification (BLOCKING — see §2 below)** | 0 | recon doc |
| **T-B.1** | Trader API endpoint methods + mappers (`get_accounts_linked`, `get_account_details`, `get_account_orders`, `get_account_transactions`) | +16 | `trader.py` (NEW) + `mappers.py` (extend) |
| **T-B.2** | Sandbox-gating discriminating tests (cross-cutting) | +6 | `tests/integrations/test_schwab_sandbox_gating.py` (NEW) |
| **T-B.3** | `_step_schwab_snapshot` pipeline step + same-day-replay-provenance test | +13 | `pipeline_steps.py` (NEW) + `pipeline/runner.py` (extend) |
| **T-B.4** | `_step_schwab_orders` + `run_schwab_reconciliation` service (8 discrepancy types reused from Phase 9) | +20 | `pipeline_steps.py` (extend) + `swing/trades/schwab_reconciliation.py` (NEW) |
| **T-B.5** | CLI `swing schwab fetch [--snapshot|--orders|--all]` | +10 | `cli/schwab.py` (extend) |
| **T-B.6** | `SchwabPipelineActiveError` cross-surface tests (5 protected + 3 safe surfaces) | +10 | `tests/integrations/test_schwab_pipeline_active_exclusion.py` (NEW) |
| **T-B.7** | Production-only domain writes integration test (cassette-driven; both envs) | +4 | `tests/integration/test_schwab_pipeline_production_only_gate.py` (NEW) |
| **T-B.8** | Un-skip sentinel-leak audit Bundle B coverage cross-bundle pin | +4 | `tests/integrations/test_schwab_token_redaction_audit.py` (un-skip) |

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `schwab-bundle-B-trader-and-snapshot`
- **Worktree directory:** `.worktrees/schwab-bundle-B-trader-and-snapshot/`
- **BASELINE_SHA:** `4efc059` (current main HEAD).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`).

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes per plan §Tasks-B suggested commit shapes (`feat(schwab): ...`, `test(schwab): ...`, `docs(schwab-api): ...`).
- One commit per task per plan §Tasks-B pattern; Codex-fix commits as `fix(schwab-bundle-B): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **DEFER the FINAL return-report commit until adversarial Codex review converges to NO_NEW_CRITICAL_MAJOR** (per writing-plans dispatch brief §4 commit-timing clarification + Sub-bundle A precedent).

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → operator-paired T-B.0.b coordination → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Sub-bundle C dispatch commissioning post-B-ship.
- **Operator owns:** T-B.0.b operator-paired live verification (provides production-tier credentials already persisted; runs paired Trader API cassette recording).

### §1.5 Verify command (basic; copowers:executing-plans handles full task execution + Codex review)

```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~12..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; assert EXPECTED_SCHEMA_VERSION == 18"
```

---

## §2 Operator-paired T-B.0.b verification gate (HARD BLOCKER for cassette recording)

Per plan §G.2 + §E.2 + §K.6. T-B.0.b requires operator participation for Trader API cassette recording (mirrors Sub-bundle A T-A.0.b pattern).

**T-B.0.b requires:**
1. Operator's existing production-tier Schwab credentials (already persisted at `~/swing-data/schwab-tokens.production.db` from Sub-bundle A phase-2).
2. Operator runs `swing schwab fetch --snapshot` + `--orders` + `--all` (or implementer triggers per cassette-recording flow) against operator's actual Schwab account.
3. Implementer + operator together observe + record:
   - `accounts.details` response shape vs `reference/schwab-api/account-specification.md` synthesized shape.
   - `accounts.orders.list` response shape (replaces TOS Account Order History parser per spec §1.9).
   - `accounts.transactions.list` response shape (cash_movements + fills source).
   - Q8 base-URL verification (production: `https://api.schwabapi.com/trader/v1/`).
   - Q17 Trader API rate-limit headroom observation (120 req/min documented; verify behavior under back-to-back calls).

**Output of T-B.0.b:** recon doc at `docs/schwab-bundle-B-task-B0b-recon.md` (mirroring Sub-bundle A recon doc shape) + commit `docs(schwab-api): T-B.0.b recon doc with Trader API operator-paired observations`.

**Pre-check `reference/schwabdev/api-calls.md` + `reference/schwab-api/account-{documentation,specification}.md` FIRST** to determine which T-B.0.b observations are already documented vs still need live API verification. Reduces operator-paired session burden.

**If operator not immediately available:** implementer can proceed with T-B.1 + T-B.2 + T-B.6 + T-B.8 using stubbed schwabdev calls (cassette-dependent acceptance criteria for T-B.3 + T-B.4 + T-B.5 + T-B.7 DEFERRED until T-B.0.b completes; document deferred items in return report for orchestrator triage).

---

## §3 Operator-witnessed verification gate (Sub-bundle B integration)

Per plan §K.B. Surfaces enumerated below; orchestrator drives operator-witnessed gate post-Codex-convergence + pre-merge-to-main.

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3580..3596 fast tests (worktree-side); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; 1 cross-bundle pin remaining (T-C.7). |
| **S2** | `swing schwab fetch --snapshot` against production | **Operator-driven (CLI)** | Verify: pipeline-active check passes (no concurrent run); `_step_schwab_snapshot` algorithm runs; `account_equity_snapshots` row INSERTED via `record_snapshot(source='schwab_api', ...)` with NLV from Schwab; `schwab_api_calls` audit row INSERTED with `linked_snapshot_id` populated via `link_snapshot_and_stamp_account_hash` combined-tx2; `schwab_account_hash` populated on snapshot row. |
| **S3** | `swing schwab fetch --orders` against production | **Operator-driven (CLI)** | Verify: `_step_schwab_orders` algorithm runs; `reconciliation_runs` row INSERTED with `source='schwab_api'` + `schwab_api_call_id` populated; per-discrepancy emit machinery (8 types from Phase 9 Sub-bundle B) reused verbatim; discrepancies table populated correctly OR no-discrepancies-emitted-because-clean. |
| **S4** | `swing schwab fetch --all` | **Operator-driven (CLI)** | Verify: invokes both snapshot + orders sequentially; both audit rows + domain rows correct. |
| **S5** | Sandbox-gating verification | **Operator-driven (CLI; switch env to sandbox)** | Verify: `swing schwab fetch --snapshot --environment sandbox` writes audit row with `status='success'` BUT ZERO rows added to `account_equity_snapshots` for that snapshot_date. (Production-only domain writes per spec §3.6.3.) |
| **S6** | `SchwabPipelineActiveError` exclusion | Inline | `pytest tests/integrations/test_schwab_pipeline_active_exclusion.py -v` GREEN — 5 protected + 3 safe surfaces tested. |
| **S7** | Sentinel-token-leak audit Bundle B coverage | Inline | `pytest tests/integrations/test_schwab_token_redaction_audit.py -v` GREEN — un-skipped Trader API portions covered. |
| **S8** | E2E production-only gate | Inline | `pytest tests/integration/test_schwab_pipeline_production_only_gate.py -v` GREEN. |
| **S9** | ruff baseline | Inline | `ruff check swing/ --statistics` reports 18 E501 unchanged. |

**Gate session ≤ 6 surfaces budget:** S1+S6+S7+S8+S9 are inline (5 surfaces). S2+S3+S4+S5 are operator-driven CLI (4 surfaces). **Total operator-driven: 4 — within 6-surface budget.**

**Production state post-gate:** S2-S5 leave operator's production state with new snapshot rows + reconciliation_run rows. If operator wants to back out: `swing journal discrepancy resolve <id> --reason="post-Sub-bundle-B-gate cleanup"` for any discrepancies emitted.

---

## §4 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** via the Skill tool. The copowers wrapper handles Codex review automatically after task commits land.
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md`
  - `SUB_BUNDLE=B` (Tasks T-B.0.b..T-B.8)
  - `BASELINE_SHA=4efc059`
- **Expected Codex chain:** 3-4 rounds (per plan §0.4 estimate; Trader API endpoint wiring is well-understood + sandbox-gating discipline is well-trodden post-spec).
- Iterate per-round fixes as `fix(schwab-bundle-B): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §4.1 Codex value-add concentration (Sub-bundle B specific)

Adversarial review for Sub-bundle B typically catches:

- **Silent-failure post-call validation** (Sub-bundle A M#1 family). EVERY trader.py wrapper around schwabdev call MUST verify post-call state. Pre-empt by writing the silent-failure-shaped discriminating test FIRST per task.
- **Audit-success-fire ordering** (Sub-bundle A M#3 family). EVERY `record_call_finish('success')` follows ALL validation. Pre-empt by writing the success-fire-too-early discriminating test FIRST per task.
- **Factory-replacement defense** (Sub-bundle A M#2 family). EVERY trader.py call invokes `ensure_schwab_log_redaction_factory_installed()` first. Pre-empt by writing the factory-replacement-mid-test discriminating test.
- **Same-day-replay-provenance asymmetry** (per plan T-B.3 + R4 Minor #2). Two distinct cassettes for the same `snapshot_date` → ONE `account_equity_snapshots` row (UPSERT) + TWO `schwab_api_calls` rows BOTH linked to the snapshot; `source_artifact_path` reflects LATEST writer.
- **Reconciliation `MATERIAL_BY_TYPE` lookup at INSERT time** (per Phase 9 Sub-bundle B Codex R1 M#2 lesson). DO NOT pass material hint from caller; consume `MATERIAL_BY_TYPE` lookup at INSERT time inside `run_schwab_reconciliation`.
- **`run_schwab_reconciliation` failure-path PRESERVES run row** (per plan §H.5 + spec §3.3.3). Mid-emit failure: UPDATE `state='failed'` (NOT rollback the run row).
- **`SchwabPipelineActiveError` count discipline** (per plan T-B.6 + R2 Minor #2 fix). 5 protected (setup-without-force / logout-without-force / fetch --snapshot / fetch --orders / fetch --all) + 2 force-override (setup --force / logout --force) + 3 safe (status / refresh / fetch --verify-marketdata). NO test attempts to verify `refresh` as protected.
- **Sandbox-gating precedence:** `cfg.integrations.schwab.environment != 'production'` short-circuits domain writes BEFORE any source-ladder write attempt. Audit row STILL writes (with `linked_snapshot_id=NULL`).
- **`Schwabdev` capital-S logger prefix** (per Sub-bundle A T-A.10 D1). Any new logger filtering/inspection in trader.py MUST use the live capital-S form.
- **Single-Client-instance discipline.** `grep schwabdev.Client swing/integrations/schwab/` returns ONLY `client.py:SchwabClient.__init__` (1 invocation). New trader.py methods consume `self._client` (passed at SchwabClient init) NOT instantiate fresh `schwabdev.Client(...)`.

### §4.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-B.0.b | None expected (verification-only); recon doc must include all observations | Operator-paired session checklist; recon doc template; pre-check distilled refs FIRST. |
| T-B.1 | Silent-failure on each of 4 trader methods; `Schwabdev` logger filter wrong-case; missing `ensure_*` pre-call | Per-method discriminating test; capital-S logger; `ensure_*` first line of every wrapper. |
| T-B.2 | Sandbox-gating precedence wrong (write-then-rollback vs short-circuit-before-write) | Discriminating test asserts `account_equity_snapshots` count UNCHANGED post-call when env='sandbox' (NOT INSERT-then-DELETE). |
| T-B.3 | Same-day-replay-provenance test missing OR wrong | Plan §H.4.1.bis mandates the test; copy verbatim. UPSERT preserves snapshot_id; LATEST `source_artifact_path` wins. |
| T-B.4 | `MATERIAL_BY_TYPE` lookup at write-time; mid-emit failure rolls back run; ON_DELETE_SET_NULL on schwab_api_call_id missing test | Reuse Phase 9 Sub-bundle B `run_tos_reconciliation` shape verbatim; failure-path PRESERVES run with `state='failed'`. |
| T-B.5 | `SchwabPipelineActiveError` exclusion missing per subcommand | All 3 fetch subcommands MUST raise; test discriminates. |
| T-B.6 | Test count drift (was +9 in R1; corrected to +10 in R2 Minor #2) | Acceptance criteria locked at +10 (5+2+3); count test groups. |
| T-B.7 | Cassette under sandbox vs production yields different signature_hash (production response stripped vs sandbox synthesized) | Use IDENTICAL cassette under both envs; assert audit-row `signature_hash` matches across envs. |
| T-B.8 | Un-skip leaves test broken because trader.py loggers don't propagate sentinel | Trader API cassettes drive sentinel through schwabdev's `Schwabdev` logger; assert sentinel absent from caplog + audit error_message. |

---

## §5 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/schwab-bundle-B-return-report.md` (mirroring `docs/schwab-bundle-A-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (task-impl + Codex-fix + return-report).
2. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
3. Test count delta + ruff baseline delta + schema version delta (unchanged at v18; consumer-side only).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1+S6-S9 inline OK; S2-S5 PENDING operator-driven CLI session).
5. Per-task deviations from the plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (cross-bundle pins; un-skip-at-T-C.7 remaining; any V2 candidates banked).
8. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8/9/10/Sub-A precedent).
9. Sub-bundle C forward-binding lessons (if any new ones surfaced during executing-plans).
10. Composition-surface verification via `^def` grep (per Phase 9 forward-binding lesson §0.5 #5).
11. T-B.0.b operator-paired session observations (recon doc summary + which §D items got pre-answered + which still need operator-paired live verification at Sub-bundle C dispatch).
12. `reference/schwab-api/` + `reference/schwabdev/` distilled refs consumed during T-B.0.b.
13. Single-Client-instance discipline verification (`grep schwabdev.Client swing/integrations/schwab/` count).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed: Skill, Bash for git + worktree, MCP for Codex, Read/Edit/Write for code + tests).
- **Foreground vs background:** foreground (default). Sub-bundle output dictates next-step decisions; parallelism gives little value.
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 6-10 hr including 3-4 Codex rounds.

---

## §7 Watch items for orchestrator (post-Sub-bundle-B-ship)

1. **Operator-witnessed gate driving** — orchestrator drives S2-S5 via operator-paired CLI session (production-tier credentials already persisted at `~/swing-data/schwab-tokens.production.db` from Sub-bundle A phase-2; **7-day refresh-token clock started 2026-05-14, expires ~2026-05-21** — operator may need to re-run `swing schwab setup` paste-back if Sub-bundle B integration runs past 2026-05-21).
2. **Sub-bundle C dispatch readiness** — post-B-ship, C is unblocked. Brief drafting includes `reference/schwabdev/api-calls.md` for `marketdata.quotes` + `marketdata.pricehistory` pre-checks + `reference/schwab-api/market-data-{documentation,specification}.md`.
3. **Sub-bundle D review-form polish threading** — when D dispatch brief gets drafted, include the polish task (drop stale "(Phase 7 will auto-derive this from Fills.)" parenthetical at `swing/web/templates/partials/review_form.html.j2:66-67`) per phase3e-todo entry.
4. **Sub-bundle D 7-day refresh expiry alert design** — Sub-bundle D `swing schwab status` full surface MUST surface days-remaining alert (≤24hr WARN; ≤2hr ERROR + bold red); briefing banner; cycle-checklist weekly re-auth reminder; CLAUDE.md gotcha promotion at T-D.4.
5. **Cross-bundle pin un-skip cascade:** T-A.10 cross-bundle pins now reduced to 1 (T-C.7) post-B-ship.

---

## §8 Dispatch order — UNCHANGED from plan §0.3

A → **B** → C → D (strict). A SHIPPED at `5b6e5ba`. B in flight. C is BLOCKED on A; functionally independent of B but shares files (`cli/schwab.py` + `mappers.py`). Sequential B→C avoids merge conflicts trivially. D is BLOCKING on all three (E2E + handoff).

Sub-bundle C dispatch UNBLOCKED post-Sub-bundle-B-ship. Operator-paced.
