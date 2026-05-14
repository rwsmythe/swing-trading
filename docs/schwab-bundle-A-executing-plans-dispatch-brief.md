# Schwab API Sub-bundle A — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance dispatched as the Schwab API Sub-bundle A executing-plans implementer. No prior conversation context.

**Mission:** Execute Sub-bundle A of the Schwab API integration plan via `copowers:executing-plans` (which wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review after task commits land). Sub-bundle A is **foundational** for the entire Schwab API arc — schwabdev wrap + auth + migration 0018 + `schwab_api_calls` audit infrastructure + CLI `schwab setup/refresh/logout/status` (skeleton; full status in Sub-bundle D). Lands on a worktree branch; orchestrator owns integration merge to main post-operator-witnessed-gate.

**Expected duration:** ~6-12 hr including ~4-5 Codex rounds. Per plan §0.4 Sub-bundle A round estimate (4-5 axes of attack: schwabdev wrapping discipline + per-env config + audit lifecycle + migration). 11 tasks (T-A.0..T-A.10); +126 fast tests projected (range +100..+135).

---

## §0 Inputs

### §0.1 Plan (canonical scope source)

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- **SUB_BUNDLE:** `A` (Tasks T-A.0..T-A.10 inclusive of T-A.0.b operator-paired verification).
- **Plan status:** 11 Codex rounds → NO_NEW_CRITICAL_MAJOR (most in project history). 1 ACCEPT-WITH-RATIONALE banked (R3 Major #4 same-day-UPSERT provenance asymmetry; explicit T-B.3 same-day-replay test covers).
- **Plan Sub-bundle A section:** §Tasks-A at line 1913+ (per-task scope + acceptance criteria + discriminating-test patterns + commit message stems).

### §0.2 Spec + brainstorm dispatch brief (background)

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`; 939 lines).
- **Brainstorm dispatch brief:** `docs/schwab-api-brainstorm-dispatch-brief.md` (`c4252d3`).
- **Writing-plans dispatch brief:** `docs/schwab-api-writing-plans-dispatch-brief.md` (`5bf425d` + `9fd50e6` Q18 COA B amendment).

### §0.3 Operator-provided distilled Schwab API references (BINDING §0 reads — per phase3e-todo orchestrator-action item)

`reference/schwab-api/` contains 4 distilled markdown files derived from saved Schwab Developer Portal HTML pages (raw HTML at `reference/SchwabAPI/`, gitignored). These are HIGHER-FIDELITY than the spec/plan §E synthesized endpoint catalog because they're derived directly from Schwab's published documentation:

- `reference/schwab-api/account-documentation.md` — Trader API account/order/transaction docs.
- `reference/schwab-api/account-specification.md` — Trader API OpenAPI / response shapes.
- `reference/schwab-api/market-data-documentation.md` — Market Data API quotes/pricehistory docs.
- `reference/schwab-api/market-data-specification.md` — Market Data API OpenAPI / response shapes.

**For Sub-bundle A specifically:** the account-documentation + account-specification refs may pre-answer parts of T-A.0.b operator-paired live verification (Q14 OAuth scope-string composition, Q8 base-URL, Q15 refresh-token rotation observations). Implementer consults these FIRST during T-A.0.b — only items NOT covered need live API verification with operator-paired session. Reduces operator-paired Task 0.b session burden.

### §0.4 Project state at dispatch time

- **HEAD on `main`:** `abb6177` (post-writing-plans-SHIPPED housekeeping + reference/schwab-api/ orchestrator-action note).
- **Test count baseline:** ~3287 fast passing on main (1 skipped — Task 7.3 operator-only flag-classifier fixture; 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions). Worktree-side likely 3283-3287 depending on real-world fixtures.
- **Test runtime:** ~63s wall-clock at `-n auto` default. Operator override: `pytest -n 0` for debug.
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v17 (Sub-bundle A T-A.7 lands v18).
- **`reference/schwab-api/` is tracked**; `reference/SchwabAPI/` + `reference/Books/` + `reference/minervini/` are gitignored.

### §0.5 Q1-Q18 dispositions wired through plan §A.1 + §A.2 (BINDING — DO NOT re-litigate)

All 18 operator-confirmed dispositions are LOCKED in plan acceptance criteria. Highlights for Sub-bundle A:

- **Q1 production-tier:** operator confirmed; default cfg cascade `environment='production'`; T-A.4 setup runs against production-tier credentials.
- **Q2 token encryption:** V1 plaintext per Finviz precedent; V2 keyring/DPAPI banked.
- **Q11 V1 INCLUDE market-data ladder:** Sub-bundle C scope; Sub-bundle A foundational only.
- **Q13 OAuth callback:** paste-only V1 (schwabdev constraint per COA B); T-A.4 implements paste-back flow.
- **Q16 `schwab_account_hash` column V1 ADD:** T-A.7 migration ALTERs `account_equity_snapshots` with NULL-permissible column.
- **Q18 COA B (`schwabdev`):** Sub-bundle A is the FIRST consumer of schwabdev — wraps `schwabdev.auth.manual_flow()` + `Tokens(tokens_db=...)` + `RLock` + SQLite `BEGIN EXCLUSIVE`. NO from-scratch OAuth; NO custom file-lock shim.

### §0.6 Two Critical-class fixes from writing-plans Codex chain (BINDING)

Both R1 + R7 Critical fixes from the writing-plans chain are encoded in plan §C + §H + §Tasks-A:

1. **R1 Critical #1 — migration atomicity.** Plan author misread CLAUDE.md's `executescript() implicit COMMIT` gotcha + assumed `_apply_migration` issues explicit BEGIN. It does not. **T-A.7 migration 0018 SQL file MUST open with `BEGIN;` + close with `COMMIT;`** to compensate (file-level discipline). Discriminating tests in T-A.7 enforce this with a counter-example test (canonical-minus-BEGIN-fixture FAILS rollback).
2. **R7 Critical #1 — token-redaction filter design based on FALSE Python logging assumption.** Plan author's Layer 2 redactor used `logging.Filter` on root logger; `Logger.callHandlers()` does NOT re-apply ancestor filters during propagation. **T-A.10 redactor MUST use `logging.setLogRecordFactory()` approach** (catches records at creation time regardless of which logger emits or which handler captures). R7-R10 chain hardened against factory-chaining recursion + reset-fixture contamination + LogRecord direct-call fallback. Discriminating tests in T-A.10 cover ALL R7-R10 surfaces.

### §0.7 Phase 9 + Phase 10 + Finviz forward-binding lessons (BINDING for Sub-bundle A)

The 11 lessons enumerated in writing-plans dispatch brief §0.5 + plan §A.9 all apply. Of particular relevance:

1. **`__post_init__` validator pattern on all new dataclasses** — `SchwabApiCall` per T-A.8 + `SchwabConfig` per T-A.2 reject NaN/inf/out-of-range at construction.
2. **Service-layer transaction discipline** — T-A.9 audit service functions OWN BEGIN IMMEDIATE / COMMIT / ROLLBACK + REJECT caller-held tx (raise `CallerHeldTransactionError`).
3. **NO `INSERT OR REPLACE` on FK-referenced tables** — T-A.8 repo `update_call_outcome` is SELECT-then-UPDATE-or-INSERT (NOT REPLACE); discriminating test asserts PK preserved across update.
4. **Server-stamping discipline** — T-A.4 setup + T-A.5 refresh server-stamp `recorded_at` timestamps at handler entry.
5. **Composition-surface enumeration via `^def` grep** — when wiring CLI subcommands, grep ALL invocation surfaces.
6. **Test fixtures USERPROFILE+HOME monkeypatch** — T-A.3 + T-A.4 + T-A.5 tests that exercise tokens DB path resolution OR cfg user-config write monkeypatch BOTH env vars (per CLAUDE.md gotcha).

### §0.8 Sub-bundle A scope-summary (per plan §0.1 + §Tasks-A)

11 tasks; +126 fast tests projected. **Per-task summary** (full per-task content in plan §Tasks-A line 1913+):

| Task | Scope | Tests | Files touched |
|---|---|---:|---|
| **T-A.0** | `.gitignore` patterns for tokens DBs + audit backups | +2 | `.gitignore` |
| **T-A.0.b** | **Operator-paired live verification (BLOCKING — see §2 below)** | 0 | recon doc |
| **T-A.1** | Pin `schwabdev>=2.4.0,<3.0.0` runtime dep | +1 | `pyproject.toml` |
| **T-A.2** | `cfg.integrations.schwab` sub-dataclass cascade | +10 | `swing/config.py` + `swing.config.toml` + `config_show.py` |
| **T-A.3** | Sub-package skeleton + exception hierarchy + `SchwabClient.__init__` + transport-debug-log suppression | +12 | `swing/integrations/schwab/{__init__,client,auth}.py` |
| **T-A.4** | OAuth paste-back setup flow + `swing schwab setup` CLI | +15 | `auth.py` + `swing/cli/schwab.py` (NEW) + `cli/__init__.py` |
| **T-A.5** | Force-refresh + logout + revocation CLI (`swing schwab refresh` + `swing schwab logout`) | +10 | `auth.py` + `cli/schwab.py` |
| **T-A.6** | `swing schwab status` skeleton (full surface in Bundle D) | +8 | `cli/schwab.py` |
| **T-A.7** | Migration 0018 (`schwab_api_calls` + 2 ALTERs + version 17→18) with explicit `BEGIN;`/`COMMIT;` discipline | +10 | `0018_schwab_integration.sql` (NEW) + `db.py` |
| **T-A.8** | Repo + `SchwabApiCall` dataclass | +18 | `repos/schwab_api_calls.py` (NEW) + `models.py` |
| **T-A.9** | Audit service-layer wrappers + combined `link_snapshot_and_stamp_account_hash` tx2 | +16 | `integrations/schwab/audit_service.py` (NEW) |
| **T-A.10** | Three-layer token redactor + sentinel-leak audit + cassette filter config | +24 | `tests/integrations/test_schwab_token_redaction_audit.py` (NEW) + `tests/conftest.py` + `client.py` + `auth.py` |

**Inter-bundle dependencies for Sub-bundle B + C:** the `schwab_api_calls` audit-row INSERT/UPDATE contract (T-A.8 + T-A.9) is what Sub-bundle B's `_step_schwab_*` calls + Sub-bundle C's market-data fetches consume. Cross-bundle pins added in T-A.10 mark `@pytest.mark.skip(reason='Cross-bundle pin: un-skip at T-B.8 + T-C.7')` for the B/C surfaces (Trader API + Market Data API).

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `schwab-bundle-A-foundational`
- **Worktree directory:** `.worktrees/schwab-bundle-A-foundational/`
- **BASELINE_SHA:** `abb6177` (current main HEAD; post-writing-plans-SHIPPED housekeeping + reference/schwab-api/ orchestrator-action note).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the brief commit SHA after this brief lands).

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes per plan §Tasks-A suggested commit shapes (`feat(schwab): ...`, `chore(schwab): ...`, `docs(schwab-api): ...`).
- One commit per task per plan §Tasks-A pattern; Codex-fix commits as `fix(schwab-bundle-A): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **Defer the FINAL return-report commit until adversarial Codex review converges to NO_NEW_CRITICAL_MAJOR.** Per writing-plans dispatch brief §4 commit-timing clarification — work through ALL Codex rounds in working tree, commit return-report ONCE after convergence.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → operator-paired T-A.0.b coordination → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Sub-bundle B dispatch commissioning post-A-ship.
- **Operator owns:** T-A.0.b operator-paired live verification (provides production-tier credentials + runs paste-back + observes refresh-token rotation behavior).

### §1.5 Verify command (basic; copowers:executing-plans handles full task execution + Codex review)

```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~15..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; assert EXPECTED_SCHEMA_VERSION == 18"
```

---

## §2 Operator-paired T-A.0.b verification gate (HARD BLOCKER for cassette recording)

Per plan §G.1 + §G.5 + §K.A. T-A.0.b is the ONLY task in Sub-bundle A that requires operator participation. **Implementer MUST pause after T-A.0 (`.gitignore`) lands + before T-A.1 (dependency pin) lands + coordinate with operator.**

**T-A.0.b requires:**
1. Operator's Schwab Developer Portal production-tier `client_id` + `client_secret`.
2. Operator runs `swing schwab setup` paste-back flow against operator's actual Schwab account.
3. Implementer + operator together observe + record:
   - `schwabdev.auth.manual_flow` exact signature (Q14 scope-string default observation).
   - Tokens DB schema (verifies §F.1 plan assumption).
   - `Client.account_linked()` response shape (Q3 single-vs-multi-account hash count).
   - Refresh-token rotation behavior (Q15 observation: rotate-every / rotate-near-expiry / never).
   - HTTP-layer base URL (Q8 observation against `reference/schwab-api/account-specification.md` distilled doc — many of these may already be answered).

**Output of T-A.0.b:** recon doc at `docs/schwab-bundle-A-task-A0b-recon.md` (mirroring Phase 9 Sub-bundle E recon doc shape) + commit `docs(schwab-api): T-A.0.b recon doc with operator-paired live verification observations`.

**If operator not immediately available:** implementer can proceed with T-A.1 (dependency pin) since it's `pyproject.toml` only + has zero runtime dependency on Schwab. T-A.2-T-A.10 then proceed using stubbed schwabdev calls (cassette recording deferred until operator-paired session). All cassette-dependent acceptance criteria DEFERRED until T-A.0.b completes; implementer notes deferred items in return report for orchestrator triage.

**`reference/schwab-api/` distilled refs pre-check:** before scheduling operator-paired session, implementer consults the 4 tracked refs at `reference/schwab-api/{account,market-data}-{documentation,specification}.md` to determine which T-A.0.b observations are already documented (e.g., scope-string default may be in account-specification.md). Reduces operator-paired session burden by skipping observations already covered.

---

## §3 Operator-witnessed verification gate (Sub-bundle A integration)

Per plan §K.A + dispatch brief §0.4. Surfaces enumerated below; orchestrator drives operator-witnessed gate post-Codex-convergence + pre-merge-to-main.

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3387..3422 fast tests (worktree-side); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged (NOT regressions). |
| **S2** | Migration 0018 lands cleanly | **Operator-driven (PowerShell)** | Operator runs `swing db-migrate` against production swing.db **AFTER manual backup** (no auto-gate fires per plan §C.5). Verify: `swing db-status` reports v18; `schwab_api_calls` table exists; `account_equity_snapshots.schwab_account_hash` column added (NULL); `reconciliation_runs.schwab_api_call_id` column added (NULL); FK constraint active. |
| **S3** | `swing schwab setup` paste-back | **Operator-driven (CLI; production credentials)** | Operator runs `swing schwab setup` against operator's actual Schwab Developer Portal app. Verify: paste-back flow completes; tokens DB created at `%USERPROFILE%/swing-data/schwab-tokens.production.db`; `schwab_api_calls` audit row INSERTED with `status='success'`; cfg-cascade write of `account_hash` to user-config.toml; success advisory printed. |
| **S4** | `swing schwab refresh` | **Operator-driven (CLI)** | Operator runs `swing schwab refresh` post-S3. Verify: tokens DB updated (new access_token); audit row INSERTED with `status='success'`; if Schwab rotated refresh_token, schwabdev persists the new token + audit captures. |
| **S5** | `swing schwab status` skeleton | **Operator-driven (CLI)** | Operator runs `swing schwab status`. Verify: env active line; tokens DB present; client_id MASKED (e.g., `1A2***9F`); account_hash MASKED; access_token validity time-remaining displayed; refresh_token validity displayed; **NO token bytes anywhere in output (sentinel-leak grep clean)**. |
| **S6** | `swing schwab logout` | **Operator-driven (CLI)** | Operator runs `swing schwab logout`. Verify: revocation HTTP call attempted (audit row INSERTED with `status='success'` or graceful network-failure tolerated); tokens DB renamed to `*.deleted-<ts>` then unlinked; subsequent `swing schwab status` reports tokens absent. |
| **S7** | Sentinel-token-leak audit | Inline | `pytest tests/integrations/test_schwab_token_redaction_audit.py -v` GREEN — all 24 assertions per T-A.10 pass (Layer 0 + Layer 1 + Layer 2 redaction + cassette filter + audit error_message + status output + cross-bundle pins). |
| **S8** | ruff baseline | Inline | `ruff check swing/ --statistics` reports 18 E501 unchanged. |

**Gate session ≤ 6 surfaces budget (Phase 10 dispatch brief §1.3 precedent):** S1+S7+S8 are inline (implementer-runs-immediately; operator sees pass-confirmation). S2+S3+S4+S5+S6 are operator-driven CLI (5 surfaces). **Total operator-driven: 5 — within 6-surface budget.** Operator pre-S2 manual DB backup is itself a step in the operator-witnessed gate (plan §I.1 cycle-checklist update).

**Production state post-gate (revertible):** S3-S6 leave operator's production tokens DB intact (operator can keep + use immediately for Sub-bundle B Trader API consumption). If operator wants to back out, run `swing schwab logout` post-gate to wipe the tokens DB.

---

## §4 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** (NOT `superpowers:executing-plans` or `superpowers:subagent-driven-development` directly — the copowers wrapper handles Codex review automatically after task commits land).
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md`
  - `SUB_BUNDLE=A` (Tasks T-A.0..T-A.10 inclusive of T-A.0.b)
  - `BASELINE_SHA=abb6177`
- **Expected Codex chain:** 4-5 rounds (per plan §0.4 estimate; schwabdev wrapping + per-env config + audit lifecycle + migration are 4 axes of attack).
- Iterate per-round fixes as `fix(schwab-bundle-A): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §4.1 Codex value-add concentration (Sub-bundle A specific)

Adversarial review for Sub-bundle A typically catches:

- **Migration atomicity counter-example** — Codex will check the canonical-minus-BEGIN-fixture test ACTUALLY catches the discipline (counter-example FAILS rollback). Pre-empt by writing the counter-example test FIRST + asserting failure, then writing the canonical test.
- **`SchwabApiCall.__post_init__` validator gaps** — each of the 14 columns + 4 CHECK enums + status enum needs validator coverage. Pre-empt by enumerating every field + asserting NaN/inf/out-of-range/invalid-enum rejection.
- **`record_call_start` / `update_call_outcome` PK preservation** — Codex will check the SELECT-then-UPDATE pattern is enforced + INSERT OR REPLACE prohibited. Pre-empt by writing the PK-preservation discriminating test FIRST.
- **Sentinel-token-leak audit completeness** — Codex will verify ALL 24 T-A.10 assertions land + cross-bundle pins exist. Pre-empt by enumerating every redaction surface (Layer 0 + Layer 1 + Layer 2 factory + cassette filter + audit error_message + status output) + writing the discriminating test for each.
- **Caller-held tx rejection** — Codex will check `CallerHeldTransactionError` raised + tested per Phase 9 lesson. Pre-empt by writing the explicit `conn.execute("BEGIN")` + invoke-service + assert-error test.
- **`__post_init__` validator on `SchwabConfig` cascade** — Codex will check each of the 5 cfg fields rejects invalid values. Pre-empt by enumerating + asserting per-field.
- **USERPROFILE+HOME monkeypatch on cfg + tokens DB path tests** — Codex will check the gotcha is honored. Pre-empt by setting BOTH env vars in test fixtures.
- **Three-layer redactor recursion-guard** — Codex will check the L2 recursion-guard fallback returns `logging.LogRecord` instance directly (NOT routed through `_ORIGINAL_RECORD_FACTORY` per R10 Major #1 fix). Pre-empt by writing the explicit mock + call-count assertion.

### §4.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-A.0 | None expected (pure scaffolding) | `git check-ignore` exit 0 + non-empty stdout for all 5 sample paths. |
| T-A.0.b | None (verification only); recon doc must include all 5 observations | Operator-paired session checklist; recon doc template. |
| T-A.1 | Version pin range syntax error | Use `>=2.4.0,<3.0.0` quoted in pyproject.toml; pip install verifies. |
| T-A.2 | `__post_init__` validator gaps; FIELD_REGISTRY 3-part-path support | Per-field validator test; FIELD_REGISTRY masked entry for `account_hash` (last-N-chars-visible). |
| T-A.3 | Exception `__str__` leaks token bytes; transport-debug-log suppression incomplete | Sentinel-in-URL test for each exception; mute schwabdev's loggers PLUS urllib3 PLUS requests-bundled-urllib3. |
| T-A.4 | Server-stamping discipline missing on `recorded_at`; cfg-cascade write race | Server-stamp at handler entry; serialize via Phase 9 lesson. |
| T-A.5 | `SchwabPipelineActiveError` discrimination between subcommands (refresh OK, logout/setup blocked) | Discriminating test per Codex R1 Minor #3 — refresh has NO `--force` flag. |
| T-A.6 | Status output leaks unredacted bytes | Plant sentinel + grep stdout per T-A.10 sentinel discipline. |
| T-A.7 | Migration without explicit BEGIN/COMMIT; backup-gate-fires false positive | Counter-example test asserts NO backup file written for 17→18; canonical-minus-BEGIN test asserts persistence-on-autocommit. |
| T-A.8 | INSERT OR REPLACE accidentally introduced; PK reissued | PK-preservation discriminating test; SELECT-then-UPDATE-or-INSERT discipline. |
| T-A.9 | Combined-tx2 not atomic across both tables; caller-held tx auto-detected | `link_snapshot_and_stamp_account_hash` single tx covers BOTH; CallerHeldTransactionError raised. |
| T-A.10 | L2 recursion under factory-chaining; reset-fixture contamination across tests | R8 Major #1 reset fixture restores factory + clears `_GLOBAL_KNOWN_SECRETS`; R10 Major #1 recursion-guard returns LogRecord directly. |

---

## §5 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/schwab-bundle-A-return-report.md` (mirroring `docs/phase10-bundle-A-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (task-impl + Codex-fix + return-report).
2. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
3. Test count delta + ruff baseline delta + schema version delta (17→18).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1+S7+S8 inline OK; S2-S6 PENDING operator-driven CLI session).
5. Per-task deviations from the plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (cross-bundle pins; un-skip-at-T-B.8 + T-C.7 reminders; any V2 candidates banked).
8. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8/9/10 pattern; will be the Nth husk pending operator cleanup-script — operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` post-merge).
9. Sub-bundle B forward-binding lessons (if any new ones surfaced during executing-plans).
10. Composition-surface verification via `^def` grep (per Phase 9 forward-binding lesson §0.5 #5).
11. T-A.0.b operator-paired session observations (recon doc summary + which §D items got pre-answered + which still need operator-paired live verification at Sub-bundle B + C dispatch).
12. `reference/schwab-api/` distilled refs consumed during T-A.0.b (which observations were already documented + which weren't).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed: Skill, Bash for git + worktree, MCP for Codex, Read/Edit/Write for code + tests).
- **Foreground vs background:** foreground (default). Sub-bundle output dictates next-step decisions (operator-witnessed gate triage + Sub-bundle B dispatch commissioning); parallelism gives little value.
- **Worktree:** YES — per §1.1. Branch + worktree dir specified.
- **Model:** defer to harness default. Sub-bundle A is implementation-heavy (migration + audit + redactor); strong reasoning depth helps but no need to pin Opus explicitly unless harness defaults differ.
- **Expected duration:** 6-12 hr including 4-5 Codex rounds.

---

## §7 Watch items for orchestrator (post-Sub-bundle-A-ship)

1. **Operator-witnessed gate driving** — orchestrator drives S2-S6 via Chrome MCP NOT applicable (CLI-driven; orchestrator drives via PowerShell + observes operator running CLI in their elevated session). Operator-paired discipline.
2. **Production swing.db backup recommendation** — operator runs `Copy-Item ~/swing-data/swing.db ~/swing-data/swing-pre-schwab-migration-<ts>.db` BEFORE S2 migration runs (plan §I.1 cycle-checklist update; T-A.7 discriminating test asserts no auto-gate fires).
3. **Sub-bundle B dispatch readiness** — post-A-ship, B is unblocked. Brief drafting includes `reference/schwab-api/` in §0 reads + checks T-A.0.b recon doc for pre-answered §D items.
4. **Sub-bundle D review-form polish threading** — when D dispatch brief gets drafted, include the polish task (drop stale "(Phase 7 will auto-derive this from Fills.)" parenthetical at `swing/web/templates/partials/review_form.html.j2:66-67`) per phase3e-todo entry.
5. **Migration 0018 forward-binding** — future migrations 0019+ MUST mirror the explicit `BEGIN;`/`COMMIT;` discipline until the runner is updated. Banked at CLAUDE.md gotcha promotion in Bundle D T-D.4.
6. **Token-redaction Layer 2 forward-binding** — `logging.setLogRecordFactory()` pattern is reusable for any future external library integration that has its own loggers. Banked at CLAUDE.md gotcha promotion in Bundle D T-D.4.

---

## §8 Dispatch order — UNCHANGED from plan §0.3

A → B → C → D (strict). A is BLOCKING for B+C (audit infra + auth + migration). D is BLOCKING on all three (E2E + handoff).

Sub-bundle B dispatch UNBLOCKED post-Sub-bundle-A-ship. Operator-paced.
