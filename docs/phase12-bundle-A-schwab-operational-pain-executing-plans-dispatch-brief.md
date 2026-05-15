# Phase 12 Sub-bundle A — executing-plans dispatch brief (Schwab API operational-pain mini-bundle)

**Audience:** Fresh Claude Code instance dispatched as the Phase 12 Sub-bundle A executing-plans implementer. No prior conversation context.

**Mission:** Execute Phase 12 Sub-bundle A via `copowers:executing-plans`. Sub-bundle A addresses the **3 operator-blocking V1 limitations from the Schwab API arc** (Phase 11) — credential entry friction (every CLI invocation prompts) + `swing schwab setup` clean-state requirement (auto-refresh fires on stale tokens DB and bails before paste-back) + pipeline cannot construct schwab_client (cfg lacks credentials → snapshot/orders/ladder all silent-skip in pipeline runs) — plus 1 ancillary fix to the cleanup-script regex that was caught during Sub-bundle D's worktree husk pass. Lands on a worktree branch; orchestrator owns integration merge to main post-operator-witnessed-gate.

**Why no brainstorm + no writing-plans:** Per orchestrator-paired scope decision 2026-05-15, the V2 candidates are well-defined (banked from Sub-bundle B + C return reports; operator stated the credential-entry-UX pain point directly). This bundle goes straight to executing-plans dispatch as a focused operational-pain mini-bundle.

**Expected duration:** ~1-2 days including ~2-3 Codex rounds. 4 tasks (T-A.1..T-A.4); +25 fast tests projected.

---

## §0 Inputs

### §0.1 No plan; per-task scope LOCKED in this brief §3 (per operator scope decision)

This brief plays the role of BOTH spec + plan + dispatch brief for the mini-bundle. Per-task scope, acceptance criteria, and discriminating-test patterns are spec'd verbatim in §3 below.

### §0.2 Phase 11 Schwab API arc SHIPPED context (BINDING)

- **Phase 11 CLOSED 2026-05-14** at `e51e6eb` (Sub-bundle D arc closer). Arc aggregate: 4 sub-bundles A+B+C+D / ~85 commits / ~17 Codex rounds / +447 fast tests / ZERO Critical findings / 5 ACCEPT-WITH-RATIONALE banked / 12 NEW CLAUDE.md gotchas / schema v17→v18.
- **Phase 11 SHIPPED entry:** `docs/phase3e-todo.md` line 9 region (`9028ab6` + post-merge addendum `6066ae9`).
- **Sub-bundle A return report:** `docs/schwab-bundle-A-return-report.md` (`6550494`) — READ §6 + §8 (5 forward-binding lessons).
- **Sub-bundle B return report:** `docs/schwab-bundle-B-return-report.md` (`0124a76`) — READ §7 + §9 (7 forward-binding lessons).
- **Sub-bundle C return report:** `docs/schwab-bundle-C-return-report.md` (`88267fd`) — READ §6 (ACCEPT-WITH-RATIONALE) + §7 (V2 candidates source) + §9 (5 forward-binding lessons).
- **Sub-bundle D return report:** `docs/schwab-bundle-D-return-report.md` (`6f943db`).
- **CLAUDE.md status line** (latest at `4834c42`) — Schwab arc closure narrative + 12 NEW gotchas in `## Gotchas` section.
- **`reference/schwabdev/{setup-guide,examples,client,api-calls,streaming,orders,troubleshooting}.md`** + **`reference/schwab-api/{account,market-data}-{documentation,specification}.md`** — distilled refs already comprehensively pre-checked across the Phase 11 arc; consult only if T-A.1-T-A.3 implementation surfaces a question.

### §0.3 BINDING distilled references

No new schwabdev call surfaces in this bundle (no new wrappers around schwabdev methods). All schwabdev surface understanding inherited from Phase 11. Specifically:

- **`reference/schwabdev/client.md`** L255-265 — confirms `Client(app_key, app_secret, ...)` constructor accepts string credentials directly. T-A.1 + T-A.3 use this directly.
- **`reference/schwabdev/setup-guide.md`** — paste-back flow assumptions; T-A.2 self-healing logic targets the `Client.__init__` auto-refresh-on-existing-tokens-DB behavior documented here.

### §0.4 Phase 11 Schwab arc cumulative forward-binding lessons (BINDING for Phase 12)

All 17 cumulative forward-binding lessons from A (5) + B (7) + C (5) remain BINDING. Plus 5 NEW from D (per `docs/schwab-bundle-D-return-report.md` §9 if any surfaced — read the return report). Especially:

1. **schwabdev silent-failure-mode discipline** (A lesson #1) — `Client.__init__` + `update_tokens()` print + return silently on auth failure. Wrappers MUST verify post-call state. **Critical for T-A.1**: if env-vars supply bogus credentials, the wrapper MUST detect the silent failure + fall back to interactive prompt OR raise with actionable error.
2. **Pre-call factory-replacement defense** (A lesson #3) — `ensure_schwab_log_redaction_factory_installed()` before every schwabdev call. **Critical for T-A.1 + T-A.3**: any new code path that constructs a `schwabdev.Client(...)` MUST call this first.
3. **Single-Client-instance discipline** (B forward-binding lesson #3) — `swing/integrations/schwab/auth.py:construct_authenticated_client(cfg, environment)` is the SOLE site that instantiates `schwabdev.Client(...)`. T-A.1 + T-A.3 extend `construct_authenticated_client` to accept env-var-sourced credentials; do NOT introduce a parallel `schwabdev.Client(...)` instantiation site.
4. **Surface-aware advisory audit** (B lesson #2) — `surface='pipeline'` silent-skip; `surface='cli'` advisory audit row. T-A.3 pipeline env-var path: when env vars provide credentials, pipeline constructs Client + calls succeed (no silent-skip needed); when env vars MISSING, the existing silent-skip behavior is preserved (NO regression — pipeline still silent-skips with log warning).
5. **`Schwabdev` capital-S logger prefix** (A lesson #5 + T-A.10 D1) — any logger filtering preserves capital-S form. T-A.2 self-healing may emit log lines; use `Schwabdev` if filtering schwabdev-emitted logs (likely N/A here).
6. **`swing schwab setup` requires clean tokens DB state** (Sub-bundle C SHIPPED gotcha + T-D.4 CLAUDE.md addition) — the gotcha being addressed by T-A.2 self-healing.

### §0.5 Codex chain pre-emption table (Phase 12 Sub-bundle A specific)

| Pattern family | Phase 11 surface | Sub-bundle A applicability + pre-emption |
|---|---|---|
| **Silent-failure post-call validation** (A M#1 family) | `Client.__init__` silent-fail | T-A.1: env-var-sourced credentials may be bogus; post-`Client.__init__` validation MUST verify `client.tokens.access_token` populated + rotated as before. T-A.3: pipeline env-var construction MUST verify the same. |
| **Audit-success-fire ordering** (A M#3 family) | All schwabdev calls | T-A.1 prompt-vs-env-var resolution happens BEFORE `record_call_start`; no audit rows from credential resolution itself (it's pre-flight). |
| **Factory-replacement defense** (A M#2 family) | All schwabdev calls | T-A.1 + T-A.3: any `Client(...)` construction call site invokes `ensure_schwab_log_redaction_factory_installed()` first. |
| **`__post_init__` validators on dataclasses** (Phase 9-10 inherited) | New dataclass | T-A.2 may introduce a `RenameRecoveryRecord` dataclass (or similar) with validators; or skip dataclass entirely if a tuple/dict suffices. |
| **Server-stamping at handler entry** (Phase 8 lesson) | All form-driven routes | N/A — no form-driven routes in this bundle. |
| **Sub-bundle C-D operator-paired-gate findings** | Stale tokens DB | T-A.2 self-healing closes the operator-pain. Discriminating test: plant a tokens DB with mtime > 7d (or with bogus refresh_token); invoke `setup`; assert dir is renamed to `*.deleted-<ts>` + setup proceeds with paste-back successfully. |
| **Cleanup-script regex too narrow** (2026-05-15 phase3e-todo entry) | `phase\d+-*` doesn't match `schwab-bundle-*` | T-A.4 widens regex (or adds `-BranchPattern` parameter). Discriminating test: plant a worktree with `schwab-bundle-X-...` name; invoke `-DeregisterFirst`; assert it's picked up. |

### §0.6 Inter-bundle dependencies (verify before commit)

- **`construct_authenticated_client(cfg, environment, client_id, client_secret)`** at `swing/integrations/schwab/auth.py` is the LOCKED single Client-instantiation site. T-A.1 extends its signature OR adds a sibling helper that resolves credentials BEFORE invoking it. Most likely shape: a new `_resolve_credentials(cfg, environment) -> tuple[str, str]` helper that consults (a) env vars `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` first; (b) interactive prompt fallback (existing behavior); raises `SchwabConfigMissingError` if neither available AND non-interactive mode (e.g., from pipeline).
- **`_construct_pipeline_schwab_client(cfg)`** at `swing/pipeline/runner.py:161` currently returns `None` because cfg lacks credentials (T-C.6 D1 ACCEPT). T-A.3 extends it to read env vars. If env vars present → construct + return Client. If absent → return None as today (preserves V1 graceful-degradation contract).
- **`schwab_api_calls` audit table** — no schema changes. T-A.1 / T-A.3 don't introduce new audit rows beyond what existing CLI/pipeline paths already write.
- **`~/swing-data/schwab-tokens.{environment}.db`** — T-A.2 reads + renames. Per A T-A.5 logout pattern, atomic rename to `*.deleted-<ts>` (24h recovery window).
- **`cleanup-locked-scratch-dirs.ps1`** — T-A.4 modifies. Existing behavior + tests inherited.
- **No schema changes; `EXPECTED_SCHEMA_VERSION` stays at 18.**

### §0.7 Project state at dispatch time

- **HEAD on `main`:** `4834c42` (post-Phase-11-arc-close + framing-cleanup commits).
- **Test count baseline:** **3752 fast passing on main** (verified post-Phase-11). 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures (NOT regressions). 1 SKIPPED (only `test_flag_classifier_integration.py`; no cross-bundle pins remain post-Phase-11).
- **Test runtime:** ~70-80s wall-clock at `-n auto` default.
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v18 (Phase 11 Sub-bundle A T-A.7 landed; B + C + D consumer-side; this bundle also consumer-side).
- **Production tokens DB:** `~/swing-data/schwab-tokens.production.db` clock started 2026-05-15T03:59:25+00:00; expires ~2026-05-22.
- **Sandbox tokens DB:** `~/swing-data/schwab-tokens.sandbox.db` clock started 2026-05-14T20:30:55+00:00; expires ~2026-05-21.
- **Production discrepancy state:** 30 `acknowledged_immaterial` + 8 `journal_corrected` + 0 `unresolved` (post-#2 cleanup at `4834c42`).

### §0.8 Out of scope

- Tier 2 items (lease status fields; sandbox status display semantics; per-row `recorded_at` column; `_step_charts` ladder wiring) — banked for a future Phase 12 sub-bundle.
- Tier 3 items (defense-in-depth + cleanup) — banked for orchestrator-paced future dispatches.
- Tier 4 new capabilities (Q2 token encryption; Q3 multi-account; Q4 streaming; Q5 web UI; Q6 inception-CSV ingestion; Q7 TOS deprecation) — separate brainstorm + writing-plans + executing-plans cycles when commissioned.
- Schema changes — `EXPECTED_SCHEMA_VERSION` stays at 18.
- New schwabdev call surfaces — none in this scope.

### §0.9 Sub-bundle A scope-summary

4 tasks; **+25 fast tests projected** (range +20..+40). **Per-task summary** (full per-task content in §3 below):

| Task | Scope | Tests | Files touched |
|---|---|---:|---|
| **T-A.1** | Credential entry UX — env vars `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` consumed by `construct_authenticated_client` (CLI surface) + interactive-prompt fallback preserved | +10 | `swing/integrations/schwab/auth.py` (extend) + `swing/cli_schwab.py` (extend prompt resolver) |
| **T-A.2** | `swing schwab setup` self-healing — auto-detect+rename stale tokens DB before invoking schwabdev (mirrors A T-A.5 logout atomic-rename pattern with 24h recovery window) | +6 | `swing/integrations/schwab/auth.py:setup_paste_flow` (extend) |
| **T-A.3** | Pipeline `client_id`/`client_secret` env-var path — `_construct_pipeline_schwab_client(cfg)` reads env vars; returns Client if both present; returns None if either absent (preserves V1 graceful-degradation) | +5 | `swing/pipeline/runner.py:_construct_pipeline_schwab_client` (extend) |
| **T-A.4** | `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` regex extension — match `(phase\d+|schwab(?:-\w+)?)-bundle-` OR introduce `-BranchPattern` parameter (default preserves existing `phase\d+-*` behavior; opt-in widening) | +4 | `cleanup-locked-scratch-dirs.ps1` + Python-side regression test (`tests/scripts/test_cleanup_script_regex.py` NEW) |

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-bundle-A-schwab-operational-pain`
- **Worktree directory:** `.worktrees/phase12-bundle-A-schwab-operational-pain/`
- **BASELINE_SHA:** `4834c42` (current main HEAD).
- **Branch naming intent:** `phase12-bundle-A-*` matches the existing cleanup-script `phase\d+-*` regex by design — sidesteps the Sub-bundle C/D husk-cleanup gap until T-A.4 closes it for future-arc breakages.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes (`feat(schwab): ...`, `fix(schwab): ...`, `test(schwab): ...`, `docs(schwab): ...`, `refactor(scripts): ...`).
- One commit per task; Codex-fix commits as `fix(phase12-bundle-A): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **DEFER the FINAL return-report commit until Codex chain converges to NO_NEW_CRITICAL_MAJOR.**

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Phase 12 Sub-bundle B (or follow-up arc) commissioning post-A-ship.
- **Operator owns:** operator-witnessed gate driving (per §4 below).

### §1.5 Verify command

```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~6..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; assert EXPECTED_SCHEMA_VERSION == 18"
# Verify env-var path:
$env:SCHWAB_CLIENT_ID = "<test_id>"; $env:SCHWAB_CLIENT_SECRET = "<test_secret>"
python -m swing.cli schwab status --environment production  # should NOT prompt
Remove-Item env:SCHWAB_CLIENT_ID, env:SCHWAB_CLIENT_SECRET
```

---

## §2 No operator-paired Task 0.b session required

This bundle introduces NO new schwabdev call surfaces. All credential UX changes are pre-flight wrapper logic. The setup self-healing is filesystem manipulation (atomic rename) before invoking schwabdev. Pipeline env-var path is pre-flight credential resolution. Cleanup-script is pure scripting + Python test infrastructure.

**Cassette tests stay synthetic-fixture-driven** — inherited from Phase 11 cassettes. No new cassettes recorded.

---

## §3 Per-task scope (BINDING; this brief plays plan-role)

### T-A.1 Credential entry UX — env vars + prompt fallback

**Problem:** Currently `swing schwab setup`, `swing schwab refresh`, `swing schwab logout`, `swing schwab status`, `swing schwab fetch *` ALL prompt for `Schwab app client_id:` + `Schwab app client_secret:` per Sub-bundle A T-A.2 security posture. Operator runs ~10+ Schwab CLI commands per gate session = ~20+ credential entries. Friction-heavy for operational use.

**Acceptance criteria:**

1. **Env-var resolution priority:** `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` env vars consulted FIRST. If BOTH set + non-empty → use them; SKIP interactive prompt.
2. **Partial-env-var rejection:** if ONLY ONE of the two env vars is set → raise `SchwabConfigMissingError` with actionable error message ("Both `SCHWAB_CLIENT_ID` and `SCHWAB_CLIENT_SECRET` must be set together; got CLIENT_ID=<masked> CLIENT_SECRET=<absent>"). Do NOT silently fall back to prompting only the missing one — partial-env-var is almost certainly an operator typo + leaving it ambiguous causes confusion.
3. **Empty-env-var rejection:** env var present but empty string treated as ABSENT (per partial rule); same error.
4. **Prompt fallback:** if BOTH env vars absent → existing `click.prompt(...)` behavior (current V1; no regression).
5. **Sentinel-leak guarantee:** env-var contents NEVER appear in audit `error_message` excerpts, log lines, or any diagnostic output. Runtime values flow into the existing 3-layer redactor's known-secret registry.
6. **Status surface inheritance:** `swing schwab status` (read-only path; should NOT prompt at all per Sub-bundle D forward-binding lesson #5) is unaffected — it reads filesystem only.

**Discriminating-test patterns (per acceptance items):**

- Test (1): set both env vars to test values + invoke `construct_authenticated_client(...)` + assert NO prompt (mock click.prompt to raise) + assert credentials passed through to schwabdev mock = test values.
- Test (2): set only `SCHWAB_CLIENT_ID` + invoke + assert raises `SchwabConfigMissingError` with message containing "both" or "together"; CLIENT_SECRET name appears in message; CLIENT_ID value is masked (first-3 + *** + last-2 per FIELD_REGISTRY pattern).
- Test (3): set both env vars to empty strings + invoke + assert same error as test (2).
- Test (4): unset both env vars + mock click.prompt to return ("p_id", "p_secret") + invoke + assert prompt fired + credentials = ("p_id", "p_secret").
- Test (5): set both env vars to a known-secret sentinel + invoke + grep audit error_message + log capture — assert sentinel absent from both.
- Test (6): invoke `swing schwab status --environment production` + assert NO prompt (regression test for D forward-binding lesson #5).

**Files touched:** `swing/integrations/schwab/auth.py` (add `_resolve_credentials_env_or_prompt(cfg, environment, *, allow_prompt: bool = True) -> tuple[str, str]` helper; extend `construct_authenticated_client` to use it; extend setup/refresh/logout/fetch entry points). `swing/cli_schwab.py` (extend prompt-collection callsites to delegate). `tests/integrations/test_schwab_credential_env_vars.py` (NEW).

**Tests added:** +10 (6 above + 4 parametrize/edge: env-var precedence over cfg fields if cfg ever gains them; whitespace-only env var; very-long env var; per-environment-namespaced env vars are NOT supported V1 — `SCHWAB_CLIENT_ID` works for both production + sandbox; if operator has separate sandbox app, V2 candidate).

**Commit message stem:** `feat(schwab): SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET env vars supersede interactive prompt`.

### T-A.2 `swing schwab setup` self-healing — auto-detect+rename stale tokens DB

**Problem:** When `~/swing-data/schwab-tokens.{env}.db` exists from a prior session AND the refresh_token has expired (or any auto-refresh failure), schwabdev's `Client.__init__` auto-attempts a refresh + bails out hard with `unsupported_token_type`. The setup paste-back code never runs. Per CLAUDE.md gotcha (T-D.4 addition), recovery sequence is `logout → setup`. Operator-pain from 2026-05-14 gate.

**Acceptance criteria:**

1. **Detect-and-rename:** `setup_paste_flow(cfg, environment, ...)` checks for existing tokens DB at `~/swing-data/schwab-tokens.{environment}.db` BEFORE invoking schwabdev. If present, atomically rename to `~/swing-data/schwab-tokens.{environment}.db.deleted-<timestamp>` (mirrors A T-A.5 logout pattern; 24h recovery window).
2. **Cross-device-link safety:** rename uses `os.replace` per CLAUDE.md gotcha; tokens DB and rename target share same volume (both in `~/swing-data/`) so no cross-device-link risk.
3. **Audit row:** the rename action MAY emit a single audit row (`endpoint='oauth.tokens_db_rename'`, `status='success'`, `surface='cli'`, `environment=<env>`, `error_message="auto-detected stale tokens DB; renamed before paste-back"`) for operator-visibility — OR may skip audit emission since the rename is operator-initiated as part of `setup`. **Pick one disposition + lock at T-A.2 acceptance + return report.**
4. **No-existing-tokens-DB path:** if no existing tokens DB present, paste-back proceeds as today (no rename; no audit row from this code path).
5. **Operator-visible message:** CLI prints "Auto-detected existing tokens DB at <path>; renamed to <renamed_path> (24h recovery window) before paste-back." BEFORE invoking schwabdev. Operator knows what just happened.
6. **Idempotency:** if `~/swing-data/schwab-tokens.{environment}.db.deleted-<exact_timestamp>` already exists (highly improbable race), append `-1`, `-2`, etc. to disambiguate — NEVER overwrite a prior renamed file.

**Discriminating-test patterns:**

- Test (1): plant existing tokens DB at the canonical path + invoke `setup_paste_flow` (mock schwabdev paste-back to succeed) + assert tokens DB exists at `<path>.deleted-<ts>` post-call AND new tokens DB present at canonical path.
- Test (2): no existing tokens DB + invoke setup + assert no rename happens; new tokens DB created at canonical path.
- Test (3): plant existing tokens DB + plant collision file at expected `<path>.deleted-<ts>` (force timestamp via mocked `datetime.now`) + invoke + assert disambiguation suffix `-1` applied to NEW renamed file (collision file unchanged).
- Test (4): mock schwabdev to raise on Client.__init__ (simulates the original failure mode that motivated this fix) + invoke setup with EXISTING stale tokens DB + assert: rename DOES happen pre-schwabdev-call, schwabdev's failure is then a real failure (not blocked by stale tokens), error surfaces correctly.
- Test (5): assert CLI output contains "Auto-detected existing tokens DB" + "renamed to" + "24h recovery window" substrings when rename fires.
- Test (6): assert `os.replace` (not `shutil.move` or other unsafe-on-Windows variants) used per CLAUDE.md gotcha — grep test source.

**Files touched:** `swing/integrations/schwab/auth.py:setup_paste_flow` (extend with pre-flight rename block). `tests/integrations/test_schwab_setup_self_healing.py` (NEW).

**Tests added:** +6 (mirrors acceptance criteria 1-6).

**Commit message stem:** `feat(schwab): swing schwab setup auto-detects + renames stale tokens DB before paste-back`.

### T-A.3 Pipeline `client_id`/`client_secret` env-var path

**Problem:** `_construct_pipeline_schwab_client(cfg)` at `swing/pipeline/runner.py:161` returns `None` because cfg has no `client_id` / `client_secret` (Sub-bundle A T-A.2 security posture). Pipeline then silent-skips Sub-bundle B's snapshot/orders steps + Sub-bundle C's market-data ladder warming. Per Sub-bundle C return report §7.3 + T-C.6 D1 ACCEPT-WITH-RATIONALE — V2 enhancement banked.

**Acceptance criteria:**

1. **Env-var read:** `_construct_pipeline_schwab_client(cfg)` reads `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` env vars via the SAME `_resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` helper introduced in T-A.1.
2. **Both-or-neither:** if BOTH env vars present → construct + return Client via `construct_authenticated_client(cfg, environment, client_id=<env>, client_secret=<env>)`. If EITHER absent → return None (preserves V1 graceful-degradation contract).
3. **`allow_prompt=False` discipline:** pipeline cannot prompt; partial env vars MUST NOT raise `SchwabConfigMissingError` here (that would crash the entire pipeline run). Instead, return None + log a single WARNING line: "Pipeline schwab_client construction skipped: env-var credentials incomplete (CLIENT_ID=<present|absent>; CLIENT_SECRET=<present|absent>). Pipeline will silent-skip Schwab steps." Helps operators diagnose why Schwab steps aren't firing.
4. **Successful-construction path:** when both env vars present + Client constructs successfully → Sub-bundle B's `_step_schwab_snapshot` + `_step_schwab_orders` + Sub-bundle C's market-data ladder all run; audit rows accumulate with `surface='pipeline'`.
5. **Construction-failure path:** if env vars present but `construct_authenticated_client` raises (e.g., schwabdev silent-fail; token rotation failure) → catch + log WARNING + return None. Pipeline does NOT crash on Schwab construction errors per V1 graceful-degradation contract.
6. **No regression:** existing pipeline tests that DON'T set env vars continue to pass (silent-skip path preserved).

**Discriminating-test patterns:**

- Test (1): set both env vars + monkeypatch `construct_authenticated_client` to return a mock client + invoke `_construct_pipeline_schwab_client(cfg)` + assert mock client returned (not None).
- Test (2): unset both env vars + invoke + assert None returned (current behavior preserved).
- Test (3): set only `SCHWAB_CLIENT_ID` + invoke + assert None returned (NOT raised) AND log capture contains "incomplete" + "CLIENT_ID=present" + "CLIENT_SECRET=absent".
- Test (4): set both env vars + monkeypatch `construct_authenticated_client` to raise `SchwabAuthError` + invoke + assert None returned (NOT propagated) AND log capture contains "construction failed".
- Test (5): full pipeline integration test mirroring Phase 9 Sub-bundle E happy-path shape — set env vars + run pipeline + assert `schwab_api_calls` rows accumulate with `surface='pipeline'` + assert `account_equity_snapshots` and `reconciliation_runs` get new entries (production-only contract holds; sandbox stays silent).

**Files touched:** `swing/pipeline/runner.py:_construct_pipeline_schwab_client` (extend per acceptance). `tests/pipeline/test_pipeline_schwab_client_env_vars.py` (NEW).

**Tests added:** +5.

**Commit message stem:** `feat(schwab): pipeline _construct_pipeline_schwab_client reads SCHWAB_CLIENT_ID/SECRET env vars`.

### T-A.4 `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` regex extension

**Problem:** Script's safety-filter regex `phase\d+-*` does NOT match `schwab-bundle-*` worktree naming convention (Sub-bundle B/C/D husks were skipped during 2026-05-15 cleanup pass; operator + orchestrator manually invoked `git worktree remove --force` for each). Banked at phase3e-todo 2026-05-15 entry.

**Acceptance criteria:**

1. **Widen regex with backwards compatibility:** change the safety-filter regex from `phase\d+-*` to `(phase\d+|schwab(?:-\w+)?)-bundle-` (matches both existing `phase{NN}-bundle-*` AND `schwab-bundle-*` patterns). OR introduce a `-BranchPattern <regex>` PowerShell parameter (default `phase\d+-*` for backward compat; operator passes `-BranchPattern '(phase\d+|schwab(?:-\w+)?)-bundle-'` to opt in). **Pick one disposition + lock at T-A.4 acceptance + return report.** Recommendation: widen the default regex (Option A) since Schwab arc is shipped + future arcs may also break the convention; backward compat preserved by the alternation.
2. **Defense-in-depth filter still rejects own-worktree:** the `-DeregisterFirst` mode still refuses to deregister the script's currently-checked-out worktree (existing `test_safety_filter_rejects_own_worktree_explicitly` regression preserved).
3. **Discriminating regression test:** plant a fake `git worktree list` output containing both `phase8-bundle-V`-style + `schwab-bundle-X`-style + `unrelated-branch`-style entries; assert script's regex matches the first two + skips the third.

**Discriminating-test patterns:**

- Test (1): mock `git worktree list` output with `phase9-bundle-A-foo` + `schwab-bundle-X-foo` + `random-branch` + `main` → invoke regex match → assert matches first two; rejects last two.
- Test (2): existing `test_safety_filter_rejects_own_worktree_explicitly` continues to pass.
- Test (3): backward-compat — `phase10-bundle-E-process-grade-trend-and-polish` (existing post-Phase-10 husk pattern) still matches.
- Test (4): edge case — `schwab-bundle-A-foundational` (Sub-bundle A's actual name) matches.

**Files touched:** `cleanup-locked-scratch-dirs.ps1` (regex update). `tests/scripts/test_cleanup_script_regex.py` (NEW; Python-side test reading the `.ps1` source per Phase 10 infra-bundle precedent).

**Tests added:** +4.

**Commit message stem:** `fix(scripts): widen cleanup-locked-scratch-dirs.ps1 -DeregisterFirst regex to match schwab-bundle-*`.

---

## §4 Operator-witnessed verification gate (Sub-bundle A integration)

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3777 fast tests (worktree-side; +25 net); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; 1 skipped (flag-classifier only). |
| **S2** | `swing schwab status --environment production` with env vars set | **Operator-driven (CLI)** | Set `$env:SCHWAB_CLIENT_ID` + `$env:SCHWAB_CLIENT_SECRET` to operator's actual credentials; invoke `swing schwab status --environment production`; assert NO prompt fired; status renders LIVE indicator (or current actual state). |
| **S3** | `swing schwab fetch --verify-marketdata` with env vars set | **Operator-driven (CLI)** | Same env-var setup; invoke `--verify-marketdata`; assert NO prompt; calls succeed; fresh audit rows in `schwab_api_calls`. |
| **S4** | `swing schwab setup` against existing tokens DB | **Operator-driven (CLI; destructive — drives a real re-auth)** | Operator's current tokens DB exists; invoke `swing schwab setup` (will trigger T-A.2 rename) WITHOUT first running `logout`; verify: previous tokens DB renamed to `*.deleted-<ts>`; CLI prints rename message; paste-back URL printed; operator completes paste-back; new tokens DB written; fresh 7-day clock starts. **NOTE: this consumes a re-auth cycle; operator should be ready to paste-back.** |
| **S5** | `swing pipeline run` with env vars set (production env) | **Operator-driven (CLI)** | Set env vars + invoke pipeline run; verify Schwab steps now FIRE (no longer silent-skip): new `schwab_api_calls` rows with `surface='pipeline'`; new `account_equity_snapshots` row from `_step_schwab_snapshot`; possibly new `reconciliation_runs` row if `_step_schwab_orders` runs. |
| **S6** | `swing pipeline run` WITHOUT env vars (regression) | **Operator-driven (CLI)** | Unset env vars + invoke pipeline run; verify behavior matches V1 silent-skip (NO new `schwab_api_calls` rows from pipeline; pipeline run still completes; log shows graceful-degradation WARNING). |
| **S7** | `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` | **Operator-driven (PowerShell elevated)** | Plant a fake `schwab-bundle-test` worktree (or use the still-pending Sub-bundle D husk if it survived reboot); invoke script with `-DeregisterFirst`; verify script picks up the schwab-pattern worktree (no longer skipped). |
| **S8** | ruff baseline | Inline | `ruff check swing/ --statistics` reports 18 E501 unchanged. |
| **S9** | Sentinel-leak audit | Inline | New T-A.1 + T-A.3 paths exercised under `tests/integrations/test_schwab_token_redaction_audit.py` patterns; assert env-var values absent from audit + caplog. |

**Gate session ≤ 6 surfaces budget:** S1+S8+S9 inline (3). S2+S3+S4+S5+S6+S7 operator-driven (6 — at upper limit). Operator may bundle adjacent surfaces (e.g., S2+S3 same env-var setup; S5+S6 set/unset env vars sequentially) to streamline.

**Production state post-gate:** S4 destructively re-auths operator's production tokens DB (fresh 7-day clock starts at gate time). S5 adds fresh schwab_api_calls + possibly new account_equity_snapshots / reconciliation_runs rows from pipeline-driven Schwab calls (now fires per T-A.3 fix). S6 verifies no-regression silent-skip path. S7 cleans up any planted test-husks.

**Production-write classifier soft-block awareness:** S5 writes audit + possibly domain rows from pipeline; operator pre-authorizes via gate-path.

---

## §5 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** via the Skill tool. The copowers wrapper handles Codex review automatically.
- Skill inputs:
  - `PLAN_PATH=docs/phase12-bundle-A-schwab-operational-pain-executing-plans-dispatch-brief.md` (this brief plays plan-role).
  - `SUB_BUNDLE=A` (Tasks T-A.1..T-A.4).
  - `BASELINE_SHA=4834c42`.
- **Expected Codex chain:** 2-3 rounds (small, focused mini-bundle).

### §5.1 Codex value-add concentration (Sub-bundle A specific)

Adversarial review for this bundle typically catches:

- **T-A.1 partial-env-var behavior** — Codex will probe edge cases (CLIENT_ID set + CLIENT_SECRET empty; both empty; whitespace-only; case-insensitive env-var lookup on Windows). Pre-empt by writing all 4 edge-case tests FIRST.
- **T-A.1 sentinel-leak** — env-var values must be registered in the 3-layer redactor BEFORE any schwabdev call fires. Codex will probe by registering a test sentinel as env var + asserting absent from caplog.
- **T-A.2 idempotency** — Codex will probe: invoke setup twice in quick succession; both rename calls must complete without overwriting the first renamed file. Pre-empt with a discriminating test.
- **T-A.2 audit-row disposition decision** — Codex will probe whichever disposition is locked (with-audit-row vs without-audit-row). Lock + document in the return report.
- **T-A.3 graceful-degradation contract preservation** — pipeline must NOT crash on env-var or schwabdev failures; existing silent-skip path must stay green. Codex will probe with monkeypatched `construct_authenticated_client` raising various exception types.
- **T-A.4 backward-compat** — existing `phase\d+-*` matches must continue. Codex will probe with `phase10-bundle-E-...` style names.
- **No-prompt-from-status regression** — D forward-binding lesson #5 says status surface should NOT prompt. T-A.1 changes might inadvertently re-introduce a prompt path. Pre-empt with discriminating test.

---

## §6 Watch items for Sub-bundle A implementer

1. **DO NOT add new schwabdev call surfaces** — this bundle is wrapper + config + script changes only.
2. **DO NOT introduce new schema** — `EXPECTED_SCHEMA_VERSION` stays at 18.
3. **Preserve existing test fixtures** — T-A.1 + T-A.3 changes must not regress any existing test that relies on prompt-mode behavior.
4. **USERPROFILE+HOME monkeypatch discipline** per CLAUDE.md gotcha — T-A.2 self-healing tests touch `~/swing-data/` paths; MUST monkeypatch both env vars to tmp_path.
5. **`os.replace` discipline** per CLAUDE.md gotcha — T-A.2 atomic rename uses `os.replace` only when source + destination share volume.
6. **Single-Client-instance discipline** — T-A.1 + T-A.3 do NOT introduce new `schwabdev.Client(...)` instantiation sites; route through `construct_authenticated_client` exclusively.
7. **`Schwabdev` capital-S logger prefix** preserved if any logger filtering touched.
8. **Sentinel-leak audit** — new env-var path exercised under existing `tests/integrations/test_schwab_token_redaction_audit.py` pattern OR a new dedicated test file.
9. **Phase 12 scope LOCK** — Tier 2/3/4 items explicitly OUT-OF-SCOPE per §0.8; do NOT scope-creep into them.
10. **`copowers-watchdog`** may flag this brief as needing review — orchestrator pre-cleared this brief via the scope-decision question at dispatch time; implementer can proceed without separate review.

---

## §7 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-bundle-A-return-report.md` (mirroring `docs/schwab-bundle-{A,B,C,D}-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain.
3. Test count delta + ruff baseline delta + schema version delta (unchanged at v18).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate).
5. Per-task deviations from this brief (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (any V2 candidates surfaced; Tier 2 dispatch-readiness if Sub-bundle B is to be commissioned next).
8. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8/9/10/11 precedent — **but** this branch matches `phase\d+-*` regex so cleanup-script `-DeregisterFirst` should pick it up cleanly; **post-T-A.4 the regex also matches `schwab-bundle-*` for any future Schwab bundles**).
9. Per-task disposition LOCKS (T-A.2 audit-row decision; T-A.4 regex-vs-parameter decision).
10. Forward-binding lessons for Phase 12 Sub-bundle B (if commissioned).
11. Composition-surface verification via `^def` grep for new helpers (`_resolve_credentials_env_or_prompt` etc.).
12. Sentinel-leak audit verification (env-var contents absent from audit + caplog).

---

## §8 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 1-2 days including 2-3 Codex rounds.

---

## §9 Watch items for orchestrator (post-Sub-bundle-A-ship)

1. **Operator-witnessed gate driving** — orchestrator drives S2-S7 via operator-paired CLI/PowerShell session.
2. **Phase 12 Sub-bundle B (Tier 2 hardening) commissioning unblocked post-A-ship** if operator chooses to continue. Tier 2 candidates per phase3e-todo + return reports: lease status fields + sandbox status display semantics + per-row `recorded_at` column + `_step_charts` ladder wiring. Likely needs writing-plans for that bundle (more cross-cutting than Tier 1).
3. **Operator daily-use unblock** — post-A-ship, operator can `set $env:SCHWAB_CLIENT_ID = ...; $env:SCHWAB_CLIENT_SECRET = ...` once per shell session (or in PowerShell profile) + every Schwab CLI invocation runs without prompts. Pipeline `swing pipeline run` actually fires Schwab steps end-to-end.
4. **Tier 3 + Tier 4 candidates** banked for orchestrator-paced future dispatches.
5. **Phase 11 forward-binding lessons remain authoritative** — A's 5 + B's 7 + C's 5 + D's lessons all still BINDING for any future Schwab work.
6. **Token clock awareness** — Sub-bundle A's gate (S4) will reset operator's production tokens DB clock to a fresh 7-day from gate-time.

---

## §10 Dispatch order

A is the only Sub-bundle currently scoped for Phase 12. Sub-bundles B/C/etc. will be commissioned (or not) based on operator's post-A-ship triage. No multi-bundle dispatch ordering required for this dispatch.
