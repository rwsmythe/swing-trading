# Schwab API Sub-bundle D — executing-plans dispatch brief (CLOSES the arc)

**Audience:** Fresh Claude Code instance dispatched as the Schwab API Sub-bundle D executing-plans implementer. No prior conversation context.

**Mission:** Execute Sub-bundle D of the Schwab API integration plan via `copowers:executing-plans`. Sub-bundle D **closes the Schwab API integration arc** — wires `swing schwab status` full per-environment surface + `docs/cycle-checklist.md` updates + E2E happy-path integration test + CLAUDE.md gotcha additions + briefing.md degraded banner + Phase 11 hand-off prep + migration 0018 atomicity verification + the operator-locked review-form polish task. Lands on a worktree branch; orchestrator owns integration merge to main post-operator-witnessed-gate.

**Expected duration:** ~4-6 hr including ~2-3 Codex rounds. Per plan §0.4 Sub-bundle D round estimate (smallest sub-bundle of the arc; mostly polish + documentation + verification; no new architectural surfaces). 7 tasks (T-D.1..T-D.7) + 1 elective polish task; +19 fast tests projected.

---

## §0 Inputs

### §0.1 Plan (canonical scope source)

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- **SUB_BUNDLE:** `D` (Tasks T-D.1..T-D.7 inclusive).
- **Plan Sub-bundle D section:** §Tasks-D at line 2214+ (per-task scope + acceptance criteria + commit message stems).

### §0.2 Sub-bundle A + B + C SHIPPED context (BINDING)

- **A merged at `5b6e5ba`** (2026-05-14; --no-ff). 4 Codex rounds; 1 ACCEPT-WITH-RATIONALE banked.
- **B merged at `df29232`** (2026-05-14; --no-ff). 5 Codex rounds + 1 orchestrator-inline gate-fix at `34be84e`. 1 ACCEPT-WITH-RATIONALE family banked (lease status fields V2-deferred).
- **C merged at `fd457de`** (2026-05-14; --no-ff). 5 Codex rounds; 2 ACCEPT-WITH-RATIONALE banked (R1 M#5 `_step_charts` ladder V2; R4 M#1 file-level mtime V1 best-effort).
- **Sub-bundle A return report:** `docs/schwab-bundle-A-return-report.md` (`6550494`) — READ §6 + §8 (5 forward-binding lessons).
- **Sub-bundle A T-A.0.b recon:** `docs/schwab-bundle-A-task-A0b-recon.md` — READ §6 + §6.bis as LOCKED inputs.
- **Sub-bundle B return report:** `docs/schwab-bundle-B-return-report.md` (`0124a76`) — READ §7 + §9 (7 forward-binding lessons).
- **Sub-bundle B T-B.0.b recon:** `docs/schwab-bundle-B-task-B0b-recon.md` — READ §2 + §5.
- **Sub-bundle C return report:** `docs/schwab-bundle-C-return-report.md` (`88267fd`) — READ §6 (ACCEPT-WITH-RATIONALE) + §7 (V2 candidates) + §9 (5 forward-binding lessons).
- **Sub-bundle C T-C.0.b recon:** `docs/schwab-bundle-C-task-C0b-recon.md` (`9d1e3e4`).
- **Sub-bundle C SHIPPED entry:** `docs/phase3e-todo.md` top entry (`c9964dc`) — operator-witnessed gate observations + 3 NEW gotcha-promotion candidates → READ for T-D.4 source material.
- **Sub-bundle B + C executing-plans dispatch briefs:** `docs/schwab-bundle-{B,C}-*-executing-plans-dispatch-brief.md` — format precedent for this brief.

### §0.3 BINDING distilled references

Both reference dirs remain BINDING §0 reads (Sub-bundle D consumes them for T-D.1 status surface + T-D.2 cycle-checklist + T-D.4 CLAUDE.md gotchas):

- `reference/schwabdev/{setup-guide,examples,client,api-calls,streaming,orders,troubleshooting}.md` — schwabdev library docs (7 distilled MDs).
- `reference/schwab-api/{account,market-data}-{documentation,specification}.md` — Schwab Developer Portal canonical docs (4 distilled MDs).

**For Sub-bundle D specifically — pre-check FIRST:**

1. **`reference/schwabdev/troubleshooting.md`** — `unsupported_token_type` → `update_tokens(force_refresh_token=True)`; trailing-slash callback fix; macOS SSL cert; permessage-deflate DNS/proxy fix. **CRITICAL for T-D.1 status surface design** (degraded-state remediation hints) + T-D.4 CLAUDE.md gotchas.
2. **`reference/schwabdev/client.md`** — 30-min access + 7-day refresh-token lifecycle. **CRITICAL for T-D.1 status `days_remaining` alert design** (≤24hr WARN; ≤2hr ERROR + bold red) + T-D.5 briefing banner predicate.
3. **`reference/schwabdev/api-calls.md`** — already comprehensively pre-checked across A + B + C; all V1 wrappers pinned via `inspect.signature` discriminating tests at T-A.4 + T-B.1 + T-C.1. No new wrapper additions in D scope.

### §0.4 Sub-bundle A + B + C cumulative forward-binding lessons (BINDING for Sub-bundle D)

**Sub-bundle A (5; per A return report §8 — still BINDING):**

1. **schwabdev silent-failure-mode discipline** — `Client.__init__` + `update_tokens()` do NOT raise on auth failure. Wrappers MUST verify post-call state.
2. **Audit-success-fire ordering** — `record_call_finish(status='success', ...)` MUST fire ONLY after all validation passes.
3. **Pre-call factory-replacement defense** — `ensure_schwab_log_redaction_factory_installed()` (NOT `_install_*`) before every schwabdev API call.
4. **Redact-then-truncate audit-error ordering** — `_redacted_excerpt` MUST redact on FULL `str(exc)` THEN truncate.
5. **schwabdev 2.5.1 actual surfaces** — 8-param `Client` ctor; JSON Tokens DB; `account_linked()` returns list-of-dicts on success / dict-error-envelope on failure; **logger name `"Schwabdev"` (capital S)**; force-refresh kwarg is `force_access_token=True`.

**Sub-bundle B (7; per B return report §9 — still BINDING):**

1. Mapper resilience for partial-response.
2. Surface-aware advisory audit (`surface='pipeline'` silent-skip; `surface='cli'` advisory audit row).
3. Single-Client-instance discipline via `construct_authenticated_client()`.
4. Audit-success-fire ordering extends to mapper validation.
5. HTTP failure classification with typed `SchwabApiError` subclasses (`auth_failed` / `rate_limited` / `error`) BEFORE re-raise.
6. `_schwab_iso` datetime helper — note `startDate`/`endDate` accept `datetime | int` (epoch ms), NOT ISO string (per Sub-bundle C T-C.1 forward-binding).
7. Cash_movement direction-ambiguous types (N/A for D scope).

**Sub-bundle C (5 NEW; per C return report §9 — BINDING for Sub-bundle D):**

1. **camelCase kwarg signature pinning DISCRIMINATING-test pattern is BINDING for any future schwabdev call surface.** No new schwabdev call surfaces in D scope; T-D.1 status surface consumes A's `account_linked` + B's `account_details` (already signature-pinned). No new pins needed UNLESS implementer adds a status-side schwabdev call (unlikely).
2. **Dual empty-signal check (`len(...)==0` OR `body.get(field) is True`) defense-in-depth pattern.** **CRITICAL for T-D.5 briefing.md degraded-banner emission predicate** — read latest `schwab_api_calls.status` row; banner predicate = `(latest.status != 'success')` per spec §3.4.4. Apply dual-signal pattern if there are multiple emptiness/error signals to consult.
3. **Injectable fetcher hook architectural pattern** — N/A for D (no cache/service surfaces in D scope).
4. **Mtime-based freshness winner is V1 best-effort; per-row `recorded_at` column closes both directions for V2.** N/A for D V1 work; banked V2 candidate.
5. **`construct_authenticated_client(cfg, environment, client_id, client_secret)` requires sensitive secrets NOT in cfg.** **CRITICAL for T-D.1 status surface** — status surface MUST handle the "tokens-present, no-secrets-available" case gracefully (e.g., display `<auth: tokens-only>` vs `<auth: full-creds>`; OR detect via tokens DB existence + skip credential-requiring operations like refresh-attempt-from-status).

### §0.5 Codex chain pre-emption table (extended for Sub-bundle D)

Sub-bundle A + B + C Codex rounds caught these patterns; pre-empt in Sub-bundle D BEFORE writing tests:

| Pattern family | A/B/C surface | Sub-bundle D applicability |
|---|---|---|
| **Silent-failure post-call validation** (A M#1 family) | `setup` + `force_refresh` + `accounts.linked` empty-list ordering | T-D.1 status surface MUST NOT trigger silent failures (read-only path; no mutation) — but if it invokes ANY schwabdev call (e.g., to verify token validity), wrap+verify post-call state. Recommendation: read from `~/swing-data/schwab-tokens.{env}.db` directly via filesystem inspection; do NOT invoke schwabdev. |
| **Audit-success-fire ordering** (A M#3 / B M#3 family) | Many surfaces | T-D.5 briefing banner predicate reads `schwab_api_calls.status` — `success` predicate must be a STRICT equality match on the ENUM value, NOT truthy-coercion (e.g., `status == 'success'` not `bool(status)`). |
| **Surface-aware advisory audit** (B M#1 family) | pipeline-internal silent-skip vs CLI advisory | T-D.1 status surface = CLI; if it writes audit rows for status reads, follow CLI advisory pattern. |
| **`Schwabdev` capital-S logger prefix** (A T-A.10 D1) | All filtering | N/A direct (no new logger work in D); inherit from A/B/C. |
| **Pre-existing test baseline (4 not 3)** (Sub-bundle C SHIPPED entry banked) | xdist-flaky `test_setup_auth_failure_audit_status_and_sentinel_redaction` | T-D's pytest expectations MUST account for **3-4 pre-existing failures depending on xdist scheduling** (Phase 8 walkthrough always 3 + setup CLI flaky 0 or 1). |
| **Stale tokens DB blocks `swing schwab setup`** (Sub-bundle C SHIPPED entry banked) | Operator-witnessed S2 recovery | T-D.4 CLAUDE.md gotcha — pre-empt in language design + T-D.1 status surface should detect+surface stale tokens DB state OR T-D.4 documents `logout → setup` recovery sequence. |
| **HX-Redirect target route exists** (CLAUDE.md HTMX failure surface) | N/A | Status surface is CLI; no HTMX. T-D.5 banner is briefing.md (Markdown render), not HTMX. |
| **Markdown render + matplotlib mathtext** (CLAUDE.md gotcha) | T-D.5 briefing banner emission | Banner text must NOT contain `$` / `^` / `_` / unbalanced `\` IF passed through any matplotlib rendering pipeline. **Briefing.md is operator-readable Markdown not matplotlib**, so the gotcha is N/A — but verify if any banner-derived chart-title rendering exists. |

### §0.6 Inter-bundle dependencies (verify before commit)

- **`SchwabClient` instance:** Sub-bundle D's status surface MAY consume `construct_authenticated_client()` IF it actively probes token validity. RECOMMENDATION: status surface reads from filesystem (`~/swing-data/schwab-tokens.{env}.db` existence + mtime + JSON inspection if needed) + reads from `schwab_api_calls` audit table; does NOT invoke schwabdev. This avoids the credential-prompt friction at status time + avoids consuming a refresh-token cycle just to display status.
- **`schwab_api_calls` audit table:** Sub-bundle D's T-D.1 status surface + T-D.5 briefing banner BOTH consume this table read-only. NO new INSERT path from D scope.
- **`reconciliation_runs.schwab_api_call_id`** + **`account_equity_snapshots.schwab_account_hash`** — both columns landed by A T-A.7; consumed read-only by T-D.1 status (recent reconciliation summary; per-environment snapshot count).
- **Source-ladder write path NOT applicable** to D (no domain writes from D scope; status + briefing banner + cycle-checklist + CLAUDE.md gotchas + E2E test + Phase 11 hand-off + migration verification are all read-side or doc-side).
- **`PriceSnapshot.provider` field** + **`OhlcvBundle.provider` field** (Sub-bundle C T-C.4) — N/A for D direct consumption.
- **Cross-bundle pin status:** ZERO cross-bundle pins remaining post-C-ship (T-C.5 + T-C.7 BOTH un-skipped + GREEN). Sub-bundle D introduces NO new cross-bundle pins.

### §0.7 Project state at dispatch time

- **HEAD on `main`:** `c9964dc` (post-Sub-bundle-C SHIPPED entry).
- **Test count baseline:** **3717 fast passing on main** (verified post-merge inline; +120 net from pre-C baseline 3597). 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures (NOT regressions). 1 SKIPPED (only `test_flag_classifier_integration.py`; cross-bundle pins T-C.5 + T-C.7 BOTH un-skipped at C-ship). **xdist-flaky `test_setup_auth_failure_audit_status_and_sentinel_redaction` may show as 3 or 4 failed depending on xdist scheduling.**
- **Test runtime:** ~76s wall-clock at `-n auto` default.
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v18 (Sub-bundle A T-A.7 landed; B + C consumer-side only; D V1 also consumer-side only — NO new schema work in D).
- **Production tokens DB:** `~/swing-data/schwab-tokens.production.db` exists with valid 30-min access + 7-day refresh tokens. **7-day refresh-token clock REFRESHED 2026-05-14** during Sub-bundle C operator-paired gate (post-recovery `logout → setup`); expires ~2026-05-21. Sub-bundle D work + integrate before then OR operator re-runs `swing schwab setup` paste-back.
- **Production-state delta from C's gate** (per phase3e-todo Sub-bundle C SHIPPED entry): 29 `schwab_api_calls` rows (was 17); 5 `account_equity_snapshots` (unchanged from B); 9 `reconciliation_runs` (unchanged from B); 38 `reconciliation_discrepancies` (unchanged from B; 8 unresolved material from B's gate STILL pending operator triage).

### §0.8 Q1-Q18 dispositions still LOCKED (DO NOT re-litigate)

All Q-dispositions remain BINDING for Sub-bundle D:

- Q1 production-tier; Q3 V1 single-primary-account; Q11 V1 INCLUDE market-data ladder (Sub-bundle C SHIPPED); Q18 COA B (`schwabdev` library).
- Q8/Q12/Q13/Q14/Q15/Q17 deferred to per-bundle Task 0.b — all consumed during A + B + C; no operator-paired session expected at T-D.x (D is doc/polish/verification scope).

### §0.9 Sub-bundle D scope-summary (per plan §Tasks-D)

7 tasks; **+19 fast tests projected** (range +15..+30; matches A/B/C precedent for parametrize/defense-in-depth overshoot). **Per-task summary** (full per-task content in plan §Tasks-D line 2214+):

| Task | Scope | Tests | Files touched |
|---|---|---:|---|
| **T-D.1** | `swing schwab status` full per-environment surface (extends A T-A.6 skeleton) per spec §3.5 mock | +10 | `swing/cli_schwab.py` (extend) |
| **T-D.2** | `docs/cycle-checklist.md` updates per §I (one-time setup + daily/weekly/recovery additions) | 0 | `docs/cycle-checklist.md` |
| **T-D.3** | E2E happy-path integration test mirroring `tests/integration/test_phase9_full_happy_path.py` shape; exercises full A+B+C workflow in single test; cassette-driven | +1 | `tests/integration/test_schwab_full_happy_path.py` (NEW) |
| **T-D.4** | `CLAUDE.md` Gotchas-section additions per §J (6 gotcha entries) — see §3 below for the EXACT 6 entries to add (incorporates 3 NEW from C SHIPPED entry banking) | 0 | `CLAUDE.md` |
| **T-D.5** | briefing.md "Schwab integration: degraded" banner per spec §3.4.4 + §7.2 | +6 | `swing/pipeline/runner.py` (briefing render section) |
| **T-D.6** | Phase 11 hand-off prep — Phase 11 SHIPPED entry in phase3e-todo + V2 candidates enumerated (Q3 multi-account; Q4 streaming; Q5 web UI; Q6 inception-CSV ingestion; Q7 TOS deprecation; Q2 token encryption; + 7 V2 candidates from C return report §7.2) | 0 | `docs/phase3e-todo.md` |
| **T-D.7** | Migration 0018 atomicity verification + manual-backup recommendation per §C.5 | +2 | none (verification-only) — `tests/data/test_migration_0018_atomicity.py::test_explicit_begin_commit_preserved` + `tests/cli/test_db_migrate_warning.py::test_warns_to_manual_backup_pre_17_18` |
| **T-D.elective.1** | **Review-form polish** — drop stale "(Phase 7 will auto-derive this from Fills.)" parenthetical at `swing/web/templates/partials/review_form.html.j2:66-67` per phase3e-todo 2026-05-13 entry; replace with forward-looking phrasing ("Auto-derivation from Fills is a future enhancement; manual entry V1.") | +2 | `swing/web/templates/partials/review_form.html.j2` (one-line change) + 2 tests pinning the new phrasing |

**Total: +19 fast tests** (T-D.1: 10 + T-D.3: 1 + T-D.5: 6 + T-D.7: 2 + T-D.elective.1: 2 — wait, that totals 21; per plan §Tasks-D the locked projection is +19 and the elective polish task is operator-locked add-on = +2 above plan baseline. Implementer should target +19 from plan tasks + small overshoot acceptable per A/B/C precedent.)

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `schwab-bundle-D-arc-closer`
- **Worktree directory:** `.worktrees/schwab-bundle-D-arc-closer/`
- **BASELINE_SHA:** `c9964dc` (current main HEAD).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`).

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes per plan §Tasks-D suggested commit shapes (`feat(schwab): ...`, `test(schwab): ...`, `docs(schwab-api): ...`, `docs(schwab): ...`).
- One commit per task per plan §Tasks-D pattern; Codex-fix commits as `fix(schwab-bundle-D): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **DEFER the FINAL return-report commit until adversarial Codex review converges to NO_NEW_CRITICAL_MAJOR** (per writing-plans dispatch brief §4 + Sub-bundle A/B/C precedent).

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Phase 11 closure post-D-ship.
- **Operator owns:** operator-witnessed gate driving (S2-S5 surfaces — `swing schwab status` invocations + briefing banner inspection + cycle-checklist review).

### §1.5 Verify command

```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~10..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; assert EXPECTED_SCHEMA_VERSION == 18"
# Verify migration 0018 atomicity test (T-D.7):
python -m pytest tests/data/test_migration_0018_atomicity.py -v
python -m pytest tests/cli/test_db_migrate_warning.py -v
```

---

## §2 Operator-paired session (NOT REQUIRED for Sub-bundle D)

Sub-bundle D scope is doc + polish + verification — **NO live cassette recording needed**. All schwabdev surfaces consumed by D were already cassette-recorded during A + B + C operator-paired Task 0.b sessions. NO new schwabdev call surfaces in D.

**Optional operator-paired observation** at T-D.1 status surface design time: implementer may choose to invoke `swing schwab status` against operator's actual production state to verify rendering matches spec §3.5 mock + handles real-world data shapes (recent Schwab API calls including the 3 redacted-error rows from Sub-bundle C gate's expired-token recovery). But this is a verification convenience, not a HARD BLOCKER for the implementation flow.

---

## §3 T-D.4 CLAUDE.md gotchas (EXACT 6 entries to add)

Per plan §J + Sub-bundle C SHIPPED entry banking. Implementer inserts these 6 entries in the CLAUDE.md `## Gotchas` section (alphabetical-ish ordering or chronological-by-discovery — match existing section style):

1. **Sub-bundle B `34be84e` defect family — schwabdev camelCase kwarg discipline.** schwabdev's `Client.account_orders(maxResults=...)`, `Client.price_history(periodType=, frequencyType=, startDate=, endDate=, ...)`, `Client.account_details(fields='positions')`, `Client.transactions(types=[...])` all use camelCase kwargs (NOT snake_case as Python convention would suggest). Wrappers MUST pin the exact signature via `inspect.signature(schwabdev.Client.X)` discriminating tests landing BEFORE wrapper code. Cassette tests will NOT catch this — they stub the entire schwabdev call (any kwargs accepted). Reference fix at `34be84e`; pre-emption pattern at `tests/integrations/test_schwab_trader_kwarg_signatures.py` + `test_schwab_marketdata_kwarg_signatures.py`.

2. **Typed `SchwabApiError` audit-row close discipline (per Sub-bundle B R1 M#3 + return report §9 #5).** All schwabdev API call wrappers MUST close `schwab_api_calls` audit rows via `record_call_finish(status='auth_failed' | 'rate_limited' | 'error', error_message=<redacted_excerpt>, ...)` BEFORE re-raising the typed exception. Pattern: classify the exception via `_classify_schwab_error(exc)` → call `record_call_finish` → re-raise. Audit log stays honest about both success + failure outcomes; degraded-health surfaces (briefing banner + status CLI) read these rows.

3. **`swing schwab setup` requires clean tokens DB state** (Sub-bundle C operator-paired gate observation 2026-05-14). schwabdev's `Client.__init__` auto-attempts a refresh against any EXISTING tokens DB and hard-fails if that refresh dies (e.g., 7-day refresh-token expired) — never reaching the paste-back code path. **Recovery sequence is `swing schwab logout` → `swing schwab setup`, NOT `setup` standalone.** `logout` atomically renames the stale tokens DB to `*.deleted-<timestamp>` (24h recovery window) per A T-A.5 design even when revoke-best-effort fails; `setup` then runs against the now-empty path with clean paste-back. **V2 candidate (banked):** make `setup` self-healing — detect-and-rename stale tokens DB itself before invoking schwabdev.

4. **7-day Schwab refresh-token clock requires periodic re-auth** (per `reference/schwabdev/client.md` L255-265 + Sub-bundle A T-A.0.b §6.bis). The refresh_token's TTL is fixed at 7 days from initial OAuth paste-back; no programmatic extension exists in schwabdev V1 (Q15 disposition). **Recovery sequence is the same `logout → setup` pattern.** `swing schwab status` surfaces days-remaining indicator with severity escalation (≤24hr WARN; ≤2hr ERROR + bold red); briefing.md banner emits "Schwab integration: degraded" if any V1-recent (e.g., last 3 calls) `schwab_api_calls.status != 'success'`. Cycle-checklist documents the weekly re-auth reminder.

5. **schwabdev 2.5.1 `"Schwabdev"` capital-S logger prefix** (Sub-bundle A T-A.10 D1). The actual logger name in schwabdev 2.5.1 is `"Schwabdev"` (capital S), NOT lowercase `"schwabdev"` as plan §H.8 originally documented. Three-layer redaction (Layer 0 known-secret exact-replace + Layer 1 heuristic regex + Layer 2 `setLogRecordFactory`) MUST use `_SCHWABDEV_LOGGER_PREFIX = "Schwabdev"` for the Layer 2 prefix-check; without capital S, schwabdev logger records would silently slip through Layer 2 redaction. Discriminating test pattern: emit a sentinel via `Schwabdev`-named logger (NOT a parent/child); assert sentinel absent from caplog.

6. **schwabdev silent-failure-mode discipline — `update_tokens()` does NOT raise on auth failure** (Sub-bundle A T-A.0.b phase-2 §6.bis + return report §8 lesson #1). schwabdev's `Client.__init__()` AND `update_tokens(force_access_token=True)` both PRINT-and-RETURN-silently on auth failure rather than raising an exception. Wrappers MUST verify post-call state (`client.tokens.access_token` populated AND rotated) + raise `SchwabAuthError` on silent failure. **Note:** `force_refresh_token=True` (NOT `force_access_token=True`) triggers a FULL OAuth dance via `input()` prompt — semantically different; the silent-rotation kwarg is `force_access_token=True`.

**Plan §J originally enumerated 6 gotchas; Sub-bundle C SHIPPED entry refined the slate above** to absorb the operator-paired-gate findings + reorganize for clarity. Implementer cross-references plan §J at write-time to ensure no original-plan gotcha is dropped (cumulative coverage; no regressions in CLAUDE.md content).

---

## §4 Operator-witnessed verification gate (Sub-bundle D integration)

Per plan §K.D. Surfaces enumerated below; orchestrator drives operator-witnessed gate post-Codex-convergence + pre-merge-to-main.

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3736 fast tests (worktree-side; +19 net); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; xdist-flaky setup CLI test 0 or 1 fail; 1 skipped (flag-classifier only). |
| **S2** | `swing schwab status --environment production` | **Operator-driven (CLI)** | Verify: rendering matches spec §3.5 mock; per-environment counts present; recent-calls summary present; reconciliation summary present; degraded indicator correct; days-remaining alert (≤24hr WARN visible if applicable); ZERO Schwab token bytes in output; account_hash masking via FIELD_REGISTRY (E8F***76 form). |
| **S3** | `swing schwab status --environment sandbox` | **Operator-driven (CLI)** | Verify: handles "tokens-present-but-stale" case gracefully (per Sub-bundle C SHIPPED gate observation: sandbox tokens DB exists but expired); status surface displays appropriate degraded-state indicator without invoking refresh. |
| **S4** | `swing pipeline run` → briefing.md banner | **Operator-driven (filesystem)** | Verify: most recent `exports/<action_session_date>/briefing.md` contains "Schwab integration: degraded" banner IF most recent `schwab_api_calls.status != 'success'` (operator can plant a degraded state by running `swing schwab fetch --verify-marketdata` against expired sandbox tokens; banner should appear in next pipeline-run-emitted briefing.md). Banner text matches spec §3.4.4 + §7.2 wording; NO token bytes; banner generic (does NOT include `error_message` content). |
| **S5** | E2E happy-path integration test | Inline | `pytest tests/integration/test_schwab_full_happy_path.py -v` GREEN — single comprehensive E2E test exercises OAuth setup → snapshot → orders → reconciliation → market-data cache fill → briefing render in cassette-driven path. Runtime <5s (xdist-friendly). |
| **S6** | Migration 0018 atomicity | Inline | `pytest tests/data/test_migration_0018_atomicity.py -v` + `pytest tests/cli/test_db_migrate_warning.py -v` GREEN. T-D.7 verifies migration 0018 SQL contains `^BEGIN;` + `^COMMIT;` markers (per plan §C.4 BEGIN/COMMIT discipline) AND CLI warning text contains the manual-backup recommendation substring. |
| **S7** | `cycle-checklist.md` review | **Operator review** | Operator reads `docs/cycle-checklist.md` post-merge; verifies one-time setup section + daily/weekly/recovery additions land cleanly + render in Markdown preview. Pure documentation surface; NO test coverage. |
| **S8** | Review-form polish (T-D.elective.1) | **Operator browser** | Visit `/reviews/{id}/complete` form; verify counterfactual fieldset helper text NO LONGER says "(Phase 7 will auto-derive this from Fills.)"; new phrasing "Auto-derivation from Fills is a future enhancement; manual entry V1." renders verbatim. |
| **S9** | ruff baseline | Inline | `ruff check swing/ --statistics` reports 18 E501 unchanged. |

**Gate session ≤ 6 surfaces budget:** S1+S5+S6+S9 are inline (4 surfaces). S2+S3+S4+S7+S8 are operator-driven CLI/filesystem/browser (5 surfaces). **Total operator-driven: 5 — close to 6-budget; orchestrator may bundle S2+S3 or S4+S7 if operator prefers.**

**Production state post-gate:** S2-S4 + S8 produce ZERO new audit rows + ZERO new domain rows + ZERO new cache writes (D scope is read-side only). S4's briefing.md emission overwrites the existing briefing.md for that action session — banked as expected behavior.

**Production-write classifier soft-block awareness:** D scope writes ZERO production data; soft-block should NOT trigger.

---

## §5 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** via the Skill tool. The copowers wrapper handles Codex review automatically after task commits land.
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md`
  - `SUB_BUNDLE=D` (Tasks T-D.1..T-D.7 + T-D.elective.1)
  - `BASELINE_SHA=c9964dc`
- **Expected Codex chain:** 2-3 rounds (per plan §0.4 estimate; smallest sub-bundle of the arc; mostly polish + documentation + verification; no new architectural surfaces).
- Iterate per-round fixes as `fix(schwab-bundle-D): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §5.1 Codex value-add concentration (Sub-bundle D specific)

Adversarial review for Sub-bundle D typically catches:

- **Status surface degraded-indicator precedence wrong** — `is_degraded` predicate must consult MULTIPLE signals (most-recent `schwab_api_calls.status != 'success'` OR `~/swing-data/schwab-tokens.{env}.db` mtime > 7 days OR tokens DB missing) per spec §3.5 mock; NOT just one signal.
- **Days-remaining alert severity escalation off-by-one** — `≤24hr` WARN; `≤2hr` ERROR + bold red. Discriminating test: plant tokens DB with mtime exactly 7d - 24hr - 1s vs 7d - 24hr - 1hr (boundary).
- **Briefing banner predicate too eager** — "Schwab integration: degraded" should fire ONLY when latest `schwab_api_calls.status != 'success'`; NOT when latest call was a `--verify-marketdata` and the operator's pipeline didn't make any Schwab calls (no rows = no degradation). Discriminating test: plant ZERO `schwab_api_calls` rows + assert banner ABSENT (clean state); plant 1 row with `status='error'` + assert banner PRESENT.
- **E2E happy-path test too coupled to live state** — must be fully cassette-driven + reset-to-known-state between assertions; NOT inherit operator's actual production state. Mirror `tests/integration/test_phase9_full_happy_path.py` shape exactly.
- **Migration 0018 atomicity test fragile to SQL formatting changes** — match `^BEGIN;` + `^COMMIT;` via regex with line-anchored multiline mode; NOT exact-string substring (which breaks on whitespace/comment changes).
- **CLAUDE.md gotcha additions duplicate existing entries** — implementer cross-references existing CLAUDE.md content + ensures no duplicate gotcha (e.g., "yfinance rate-limits" already exists; do NOT add a near-duplicate).
- **Cycle-checklist updates introduce circular references** — `swing schwab setup` referenced in cycle-checklist must match the actual CLI surface name (per A T-A.4); avoid stale CLI commands or paths.

### §5.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-D.1 | Status surface invokes schwabdev (consuming refresh cycle just for display); degraded-indicator predicate too narrow | Status surface reads filesystem + audit table only; degraded predicate consults multiple signals (recent-call status + tokens DB mtime + tokens DB existence). |
| T-D.2 | Cycle-checklist references stale CLI commands | Grep actual CLI surface (`swing schwab --help`) before writing; use exact CLI invocation strings. |
| T-D.3 | E2E test inherits operator's actual production state | Use isolated tmp_path conn; cassette-driven; assertions against KNOWN-state-after-cassette-replay; NOT against operator's actual DB. |
| T-D.4 | Duplicate gotcha entries; missing the 3 NEW from C SHIPPED entry | Cross-reference existing CLAUDE.md content; ensure all 6 entries from §3 above are present + non-duplicating. |
| T-D.5 | Banner predicate fires on no-rows-yet state (false positive); banner text contains token bytes | Discriminating tests for both ZERO-rows + degraded-on-error; assert banner ABSENT in zero-rows case + PRESENT-AND-GENERIC in error case. |
| T-D.6 | Phase 11 SHIPPED entry omits arc closer aggregate (commits + Codex rounds + tests across A+B+C+D) | Mirror Phase 9 + Phase 10 SHIPPED entry format; explicit aggregate stats. |
| T-D.7 | Migration atomicity test fragile to whitespace | Use line-anchored regex multiline mode for `^BEGIN;` + `^COMMIT;` markers. |
| T-D.elective.1 | Phrasing change breaks operator-locked V1 disposition | Preserve "manual entry V1" framing per phase3e-todo 2026-05-13 entry default; +2 tests pin the new phrasing exactly. |

---

## §6 Watch items for Sub-bundle D implementer (per-task assertion targets)

Per plan §L watch items — Sub-bundle D's binding subset:

1. **`swing schwab status` rendering** matches spec §3.5 mock verbatim — operator's ability to read status output is the V1 monitoring surface.
2. **Briefing banner predicate** consults multiple signals (recent-call status + tokens DB existence + tokens DB age) per spec §3.4.4.
3. **CLAUDE.md cumulative coverage** — Sub-bundle D adds 6 NEW gotchas; cross-references ensure cumulative coverage with prior phases.
4. **Cycle-checklist** updates align with cumulative project conventions per §I.
5. **E2E happy-path test** mirrors Phase 9 Sub-bundle E precedent (`tests/integration/test_phase9_full_happy_path.py`).
6. **Migration 0018 atomicity** persists end-to-end (T-A.7 lands the test; T-D.7 verifies the discipline survives later edits).
7. **Phase 11 SHIPPED entry** captures arc closer aggregate (4-bundle SHIPPED state + Codex rounds total + commits total + tests delta + ACCEPT-WITH-RATIONALE list + V2 candidates list).
8. **Test fixture USERPROFILE+HOME monkeypatch** per CLAUDE.md gotcha — applies to T-D.7 migration tests + T-D.3 E2E test (any path resolution to `~/swing-data/` paths).
9. **Phase isolation preserved** — D adds no new repo-layer or service-layer modifications; consumes A + B + C surfaces read-only.
10. **NO new schema work in D** — `EXPECTED_SCHEMA_VERSION` stays at 18.

---

## §7 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/schwab-bundle-D-return-report.md` (mirroring `docs/schwab-bundle-{A,B,C}-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (task-impl + Codex-fix + return-report).
2. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
3. Test count delta + ruff baseline delta + schema version delta (unchanged at v18).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1+S5+S6+S9 inline OK; S2-S4+S7-S8 PENDING operator-driven session).
5. Per-task deviations from the plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (Phase 11 SHIPPED entry threading; any V2 candidates banked from D-specific findings).
8. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8/9/10/Sub-A/B/C precedent — **D will be the 4th in the cleanup-script queue**).
9. Phase 11 closure summary for arc-closer aggregate stats (4-bundle SHIPPED state + Codex rounds total = 4+5+5+~3=~17 + commits total + tests delta cumulative + ACCEPT-WITH-RATIONALE banked across arc).
10. Composition-surface verification via `^def` grep (T-D.5 briefing render section + T-D.1 status surface).
11. CLAUDE.md cumulative coverage diff (which existing entries augmented vs which 6 NEW entries added).
12. `reference/schwab-api/` + `reference/schwabdev/` distilled refs consumed (mostly inherited from A + B + C; no new ref consumption expected at D).
13. Cross-bundle pin status (ZERO remaining; closure complete at C).
14. Phase 11 hand-off readiness summary (V2 candidates list complete; Phase 12+ candidates UNBLOCKED for orchestrator triage).

---

## §8 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed: Skill, Bash for git + worktree, MCP for Codex, Read/Edit/Write for code + tests).
- **Foreground vs background:** foreground (default). Sub-bundle output dictates next-step decisions; parallelism gives little value.
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 4-6 hr including 2-3 Codex rounds.

---

## §9 Watch items for orchestrator (post-Sub-bundle-D-ship — CLOSES the arc)

1. **Operator-witnessed gate driving** — orchestrator drives S2-S8 via operator-paired CLI + filesystem + browser session. **7-day refresh-token clock REFRESHED 2026-05-14 during Sub-bundle C gate; expires ~2026-05-21** — operator may need to re-run `swing schwab setup` paste-back if Sub-bundle D integration runs past 2026-05-21.
2. **Phase 11 closure** — Sub-bundle D ships ALL 4 sub-bundles complete. Phase 11 SHIPPED entry in phase3e-todo (T-D.6) aggregates: 4-bundle commits total (~50-60 across the arc) + Codex rounds total (~17) + tests delta cumulative (~+317 from pre-A baseline 3287 → post-D ~3736) + ACCEPT-WITH-RATIONALE list (1 A + 1 B + 2 C + 0-1 D = ~4-5 banked) + 7+ V2 candidates from C return report + V2 candidates list from spec §10 Q-deferrals.
3. **Worktree husk cleanup** — operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` queue: A + B + C still pending; D will be the 4th. Operator runs at convenience post-D-merge.
4. **V2 candidates triage** unblocked post-D-ship for orchestrator-paced dispatching. Notable V2 candidates from the arc (NOT scope for Sub-bundle D):
   - **Pipeline `client_id`/`client_secret` env-var path** (T-C.6 D1) — close the V1 pipeline ladder silent-skip.
   - **`swing schwab setup` self-healing** (Sub-bundle C T-D.4 gotcha source) — detect-and-rename stale tokens DB.
   - **Per-row `recorded_at` column** (Sub-bundle C R3 M#1 + R4 M#1) — close mtime-based-freshness V1 best-effort.
   - **`_step_charts` ladder wiring** (Sub-bundle C R1 M#5).
   - **Schwab inception-CSV ingestion** (Q6) — separate dispatch per phase3e-todo 2026-05-12 entry.
   - **Q3 multi-account / Q4 streaming / Q5 web UI / Q7 TOS deprecation / Q2 token encryption** — V2 candidates per spec §10.
5. **Plan-text V2.1 §VII.F amendment routing** — accumulated 18+ deviations from C alone + ~5 from B + ~13 from A = ~36+ deviations entering D; D may add a few more. Orchestrator routes via standard V2.1 §VII.F amendment channel post-arc-close.

---

## §10 Dispatch order — UNCHANGED from plan §0.3

A → B → C → **D** (strict). A SHIPPED at `5b6e5ba`. B SHIPPED at `df29232`. C SHIPPED at `fd457de`. **D in flight per this brief — CLOSES THE ARC.**

Phase 11 closure post-Sub-bundle-D-ship. Phase 12+ candidate triage UNBLOCKED. Operator-paced.
