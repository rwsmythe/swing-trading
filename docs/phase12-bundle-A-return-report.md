# Phase 12 Sub-bundle A — executing-plans return report

**Branch:** `phase12-bundle-A-schwab-operational-pain`
**Baseline SHA:** `892e3e3` (post-Phase-11 + dispatch-brief landing on main)
**Branch tip SHA (pre return-report commit):** `f560167` + this report commit
**Dispatch brief:** `docs/phase12-bundle-A-schwab-operational-pain-executing-plans-dispatch-brief.md`

---

## §1 Final HEAD + commit breakdown

10 commits + 1 inline docstring touch + this return report on top of `892e3e3`:

| SHA | Type | Subject |
|---|---|---|
| `74d3fea` | task-impl | `feat(schwab): SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET env vars supersede interactive prompt` (T-A.1) |
| `832e1a3` | code-review | `fix(schwab): code-review cleanups on T-A.1 — public helper name + CLI wrapper + Test 10 discrimination + import + sentinel strengthening` |
| `424b0fc` | task-impl | `feat(schwab): swing schwab setup auto-detects + renames stale tokens DB before paste-back` (T-A.2) |
| `cecc7d7` | code-review | `fix(schwab): code-review cleanups on T-A.2 — two-phase audit ordering + bounded idempotency + UTC docstring` |
| `44c2e20` | task-impl | `feat(schwab): pipeline _construct_pipeline_schwab_client reads SCHWAB_CLIENT_ID/SECRET env vars` (T-A.3) |
| `fb4186d` | style | `style(tests): ruff --fix import-sort on T-A.3 test file` |
| `064daa6` | task-impl | `fix(scripts): widen cleanup-locked-scratch-dirs.ps1 -DeregisterFirst regex to match schwab-bundle-*` (T-A.4) |
| `7e44f29` | Codex R1 fix | `fix(phase12-bundle-A): Codex R1 Critical+Major — regex tightening + broad except + O_EXCL TOCTOU defense` |
| `9588b32` | style | `style(tests): UP017 on new Test 9 — use datetime.UTC alias` |
| `f560167` | Codex R2 fix | `fix(phase12-bundle-A): Codex R2 — audit row opens before O_EXCL claim + prose comment refresh` |
| (next) | return-report | `docs(phase12-bundle-A): return report + Codex R3 minor docstring polish` |

**Aggregate:** 4 task-impl commits + 2 code-review-cleanup commits + 2 Codex-fix commits + 2 ruff-style commits + 1 return-report commit = **11 commits** on branch.

---

## §2 Codex round chain

| Round | Critical | Major | Minor | Verdict | Resolution |
|---:|---:|---:|---:|---|---|
| R1 | 1 | 2 | 0 | ISSUES_FOUND | All 3 resolved in `7e44f29` (regex tightening; broad except; O_EXCL TOCTOU defense + 5 discriminating tests) |
| R2 | 0 | 1 | 1 | ISSUES_FOUND | Major resolved in `f560167` (audit-row OPEN moved before O_EXCL claim + new Test 10 for PermissionError-path audit trail). Minor (stale prose) resolved in same commit. |
| R3 | 0 | 0 | 1 | NO_NEW_CRITICAL_MAJOR | Advisory docstring drift; resolved inline in this return-report commit. |

**Total:** 3 Codex rounds. Convergent tapering: R1 1C/2M → R2 0C/1M → R3 0C/0M. **ZERO ACCEPT-WITH-RATIONALE positions banked.** Faster convergence than Phase 11 Sub-bundle D's 3-round arc-closer.

---

## §3 Test count + ruff + schema deltas

| Metric | Baseline (`892e3e3`) | Final | Delta |
|---|---:|---:|---:|
| Fast tests passing | 3752 | 3786 | **+34** |
| Pre-existing phase8 failures | 3 | 3 | 0 |
| Skipped | 5 | 5 | 0 |
| Fast-suite wall-clock (`-n auto`) | ~70s | ~70s | unchanged |
| Ruff baseline (E501) | 18 | 18 | unchanged |
| `EXPECTED_SCHEMA_VERSION` | 18 | 18 | unchanged (consumer-side only) |

**Test breakdown by task:**
- T-A.1: +11 (10 original + 1 sentinel-discriminator added during code-review cleanup).
- T-A.2: +10 (7 original + 1 Test 8 audit-row-on-failure + 1 Test 9 TOCTOU race + 1 Test 10 claim-step PermissionError).
- T-A.3: +6 (5 original + 1 broad-Exception OSError test added during Codex R1 fix).
- T-A.4: +11 (8 original + 3 rejection tests for non-bundle Schwab paths added during Codex R1 fix).
- Test amendment: 1-line `monkeypatch.delenv` addition to `tests/integration/test_pipeline_marketdata_ladder_integration.py:test_construct_pipeline_schwab_client_returns_none_by_default` for determinism (preserves original assertion semantics).

Brief projected +25 fast tests; actual +34. Overshoot consistent with Phase 9/10 patterns (Codex chain forces additional discriminating tests).

---

## §4 Operator-witnessed verification surfaces (PENDING orchestrator-driven gate)

Per dispatch brief §4. Gate session ≤ 6 surfaces budget — at upper limit.

| # | Surface | Type | Status |
|---|---|---|---|
| **S1** | `python -m pytest -m "not slow" -q` | Inline | **PASS** — 3786/3786 + 3 pre-existing + 5 skipped. |
| **S2** | `swing schwab status --environment production` with env vars set | Operator-driven (CLI) | PENDING |
| **S3** | `swing schwab fetch --verify-marketdata` with env vars set | Operator-driven (CLI) | PENDING |
| **S4** | `swing schwab setup` against existing tokens DB | Operator-driven (CLI; destructive — drives re-auth) | PENDING — operator should be ready to paste-back |
| **S5** | `swing pipeline run` with env vars set | Operator-driven (CLI) | PENDING |
| **S6** | `swing pipeline run` WITHOUT env vars (regression) | Operator-driven (CLI) | PENDING |
| **S7** | `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` | Operator-driven (PowerShell elevated) | PENDING |
| **S8** | `ruff check swing/ --statistics` | Inline | **PASS** — 18 E501 unchanged. |
| **S9** | Sentinel-leak audit (T-A.1 + T-A.3 paths) | Inline | **PASS** — covered by `test_env_var_values_registered_for_redaction` + `test_env_var_values_redacted_when_short_and_layer1_skips`. |

---

## §5 Per-task deviations from brief

### T-A.1 deviations (1 minor)

**Mask helper:** chose to add a private `_mask_credential` helper in `auth.py` rather than reuse `swing.config_validation.mask_sensitive_value` because the brief AC2 example error message ("CLIENT_ID=<masked> CLIENT_SECRET=<absent>") explicitly required `<absent>` + `<too_short>` markers. The existing `mask_sensitive_value` produces `"(not set)"` for None which would have diverged from the brief's locked example wording.

### T-A.2 deviations (2 — both banked V2.1 §VII.F amendment candidates)

1. **Audit endpoint name:** brief AC3 example specified `endpoint='oauth.tokens_db_rename'` but the v18 schema CHECK enum on `schwab_api_calls.endpoint` does NOT include that value (brief §6 locks `EXPECTED_SCHEMA_VERSION = 18` with "DO NOT MODIFY"). **Disposition LOCKED:** reuse existing `oauth.code_exchange` enum value + rely on the distinctive `error_message` substring ("auto-detected" + "renamed before paste-back") for operator discoverability. Test 7 pins this disposition with real DB-query assertions on both endpoint AND error_message substrings. **V2.1 §VII.F amendment candidate banked:** extend CHECK enum to include `oauth.tokens_db_rename` (a dedicated endpoint name makes audit log self-documenting; would require a schema v18→v19 migration; out-of-scope for this operational-pain mini-bundle).

2. **Timestamp anchor asymmetry:** self-heal uses UTC-aware `_utc_now()` (matching modern convention); logout's `revoke_and_delete` continues to use naïve `datetime.now()` (local time). FORMAT (`%Y%m%dT%H%M%S`) consistent across both; SEMANTIC anchor diverges. Docstring at `_rename_stale_tokens_db` is honest about this. **V2.1 §VII.F amendment candidate banked:** unify logout to UTC; brief §6 explicitly put logout out-of-scope, so deferred to a future polish dispatch.

### T-A.3 deviations (1 minor)

**Test 5 (full-pipeline integration) is narrower than brief intent:** Test 5's module docstring explicitly acknowledges it stops at the helper's return-value contract rather than exercising downstream `_step_schwab_snapshot` audit-row writes. The existing `tests/integration/test_pipeline_marketdata_ladder_integration.py` suite (still passing with the 1-line determinism amendment) provides the broader integration coverage; layering full happy-path schema setup on top of the unit-test scope of `test_pipeline_schwab_client_env_vars.py` would conflict.

### T-A.4 disposition LOCKS (per brief AC1 + AC3)

1. **Regex widening: Option A LOCKED** — widened default regex (not `-BranchPattern` parameter). Code comment + commit message document this disposition. Post-Codex R1 the regex was tightened from the implementer's initial too-broad `(phase\d+|schwab(?:-\w+)?)[-_]` to `(phase\d+[-_]|schwab(?:-\w+)?-bundle-)` requiring the literal `-bundle-` segment for Schwab paths.

2. **No `-BranchPattern` parameter introduced** per LOCK.

---

## §6 Codex Major findings ACCEPTED with rationale

**ZERO ACCEPT-WITH-RATIONALE positions banked.** All 1 Critical + 3 Major findings across R1 + R2 + the 1 advisory R3 Minor were resolved with code-content fixes + discriminating regression tests.

This matches the Phase 9 Sub-bundle D + E + Phase 10 Sub-bundles A-E + Phase 11 Sub-bundle D cleanest-arc precedent.

---

## §7 Watch items for orchestrator (post-Sub-bundle-A-ship)

1. **Operator-witnessed gate driving** — orchestrator drives S2-S7 per brief §4. S4 destructively re-auths operator's production tokens DB (fresh 7-day clock starts). S5 adds fresh `schwab_api_calls` rows + possibly new domain rows from pipeline-driven Schwab calls.

2. **Phase 12 Sub-bundle B (Tier 2 hardening) commissioning UNBLOCKED** post-A-ship if operator chooses to continue. Tier 2 candidates per phase3e-todo + Phase 11 return reports:
   - Lease status fields (Phase 11 B+C R2/R3 ACCEPT-WITH-RATIONALE family).
   - Sandbox status display semantics (Phase 11 D banked V2).
   - Per-row `recorded_at` column for ohlcv archive (Phase 11 C R4 M#1 V1 best-effort).
   - `_step_charts` ladder wiring (Phase 11 C R1 M#5 V2).
   - V2.1 §VII.F amendments banked this bundle: `oauth.tokens_db_rename` dedicated endpoint name (schema v18→v19); logout timestamp UTC unification.

3. **Operator daily-use unblock — DELIVERED.** Post-A-ship, operator can `$env:SCHWAB_CLIENT_ID = ...; $env:SCHWAB_CLIENT_SECRET = ...` once per shell session (or in PowerShell profile) + every Schwab CLI invocation runs without prompts. Pipeline `swing pipeline run` actually fires Schwab steps end-to-end when env vars are set.

4. **Token clock awareness** — S4 gate will reset operator's production tokens DB clock to fresh 7-day from gate-time. Sandbox tokens DB clock (`~2026-05-21`) unaffected.

5. **Phase 11 forward-binding lessons (5 A + 7 B + 5 C + D's lessons) remain authoritative** for any future Schwab work.

---

## §8 Worktree teardown status

**Expected ACL-locked husk** per Phase 6/7/8/9/10/11 precedent. **Post-T-A.4 the cleanup-script regex now matches `phase\d+-*` AND `schwab[-arc?]-bundle-*` AND the current branch `phase12-bundle-A-schwab-operational-pain` (matches the `phase\d+[-_]` alternation by design — sidesteps the prior cleanup-script-gap for this very dispatch).**

After orchestrator merge to main + worktree branch deletion, the `-DeregisterFirst` pass should pick up the husk cleanly.

---

## §9 Per-task disposition LOCKS

| Task | Decision | Lock |
|---|---|---|
| T-A.1 | Mask helper: private `_mask_credential` in `auth.py` (not reuse `mask_sensitive_value`) | Locked per brief AC2 example |
| T-A.2 | Audit endpoint: reuse `oauth.code_exchange` (not new `oauth.tokens_db_rename`) | Locked per brief §6 schema-frozen-at-v18; V2.1 §VII.F amendment banked |
| T-A.2 | Audit row emission: emit single row per AC3 with locked grep substrings | Locked + pinned by Test 7 (success) + Test 8 (replace-failure) + Test 10 (claim-failure) |
| T-A.2 | Timestamp anchor: UTC-aware self-heal; logout naïve unchanged | Locked per brief §6 out-of-scope on logout; V2.1 §VII.F amendment banked |
| T-A.4 | Regex widening: Option A (widen default; no `-BranchPattern` parameter) | Locked per brief AC1; tightened to require `-bundle-` segment post-Codex R1 |

---

## §10 Forward-binding lessons for Phase 12 Sub-bundle B (if commissioned)

1. **`os.replace` is overwrite-by-design.** ANY future code that uses `os.replace` for atomic-rename-with-no-overwrite semantics MUST claim the destination via `O_EXCL` BEFORE replacing. Pattern locked at `_rename_stale_tokens_db` (Codex R1 M2 fix). Pattern complement to the Phase 4 `os.replace` cross-device-link gotcha — both about the rename primitive's semantic-vs-intent gap.

2. **Pipeline boundary except-clause MUST be the broadest applicable.** The pipeline runner's `_construct_pipeline_schwab_client` widened from `(SchwabApiError, SchwabConfigMissingError)` to `Exception` with `# noqa: BLE001` + multi-line rationale (Codex R1 M1 fix). Reason: pipeline V1 graceful-degradation contract demands never crashing; library exceptions (schwabdev internal validation, OSError, sqlite3.DatabaseError, RuntimeError, ConnectionError) can ALL emanate from a single `Client.__init__` call. Discriminating-test pattern: monkeypatch `construct_authenticated_client` to raise `OSError` (or other non-typed-error class); assert None returned + WARNING logged + class name in log message. Any future pipeline-boundary code path that wraps a third-party library call follows the same broaden-the-catch pattern.

3. **Cleanup-script regex tightening lesson: `[-_]` separator alone is NOT a discriminator for arc-bundle prefixes.** Codex R1 C1 caught that `(phase\d+|schwab(?:-\w+)?)[-_]` admits `.worktrees/schwab-feature-foo` because `schwab` + `-` + anything matches. Future cleanup-script regex extensions for new arc names (e.g., a future `qullamaggie-bundle-A`) MUST require the literal `-bundle-` segment in the safety filter. Discriminating-test pattern: write rejection tests for `<arc>-feature-foo`, `<arc>-test-branch`, `<arc>by-bundle-A` (boundary defense).

4. **Two-phase audit ordering applies to ANY filesystem-modifying helper — not just OSError on `os.replace`.** Codex R2 M1 caught that the implementer's first attempt at the O_EXCL claim path moved the audit-OPEN AFTER the claim loop, so non-collision OSError from `os.open` (PermissionError, ENOSPC, etc.) propagated before `record_call_start` ran. Future helpers that wrap a filesystem operation MUST open the audit row BEFORE the FIRST side-effect — even if that side-effect is a "pre-flight claim" rather than the main operation. Discriminating-test pattern: monkeypatch the first filesystem call (not just the "main" rename/write) to raise a non-collision OSError; assert audit row is closed with `status='error'` before the exception propagates.

5. **Env-var-driven credential paths require sentinel-leak discrimination strong enough to BYPASS Layer-1 heuristic redaction.** T-A.1 code-review caught that long ALL-CAPS sentinels (47 chars) trigger Layer-1's `[A-Za-z]{24+}` heuristic, so the discrimination "did the registry registration actually fire?" was muddied. Phase 11 sentinel-leak tests should pair Layer-1-bypassing short sentinels (16 chars with hyphens) with Layer-1-triggering long ones, OR drop to Layer-1-bypassing only. Pattern complement to the Phase 11 Sub-bundle A sentinel-leak audit test.

---

## §11 Composition-surface verification

`^def` grep for new public helpers + their CLI/pipeline callers:

| Helper | Definition | Callers |
|---|---|---|
| `resolve_credentials_env_or_prompt` (T-A.1) | `swing/integrations/schwab/auth.py:80` | `swing/cli_schwab.py:118` (CLI wrapper) + `swing/pipeline/runner.py:226` |
| `_resolve_credentials_for_cli` (T-A.1 wrapper) | `swing/cli_schwab.py:113` | 5 CLI callsites at `:185, :277, :346, :994, :1320` |
| `_rename_stale_tokens_db` (T-A.2) | `swing/integrations/schwab/auth.py:218` | `setup_paste_flow` at `auth.py:586` (sole caller) |
| `_construct_pipeline_schwab_client` (T-A.3 modified) | `swing/pipeline/runner.py:217` | `swing/pipeline/runner.py:556` (pre-existing call site; behaviour widened by T-A.3) |
| `_close_audit_error` (T-A.2 Codex R2 inner closure) | `swing/integrations/schwab/auth.py:_rename_stale_tokens_db` local | Same-function 3 callsites (claim OSError, replace OSError, exhaustion RuntimeError) |

All callers verified post-grep — no orphan definitions, no missing-callsite drift.

---

## §12 Sentinel-leak audit verification

Per brief S9 + §0.5 #2 pre-emption.

**T-A.1 paths:**
- `test_env_var_values_registered_for_redaction` (long ALL-CAPS sentinels; passes via both Layer-1 heuristic + registry).
- `test_env_var_values_redacted_when_short_and_layer1_skips` (16-char hyphenated sentinels that BYPASS Layer-1; only registry registration scrubs them).
- Both pass — registry registration verified to fire BEFORE any schwabdev log emission could leak the env-var values.

**T-A.3 paths:**
- `_construct_pipeline_schwab_client` calls `resolve_credentials_env_or_prompt(...)` which delegates secret-registration to the same registry as T-A.1 — coverage inherits transitively.
- `test_broad_construction_exception_returns_none_with_redacted_warning` (Codex R1 M1 fix) monkeypatches `construct_authenticated_client` to raise `OSError("tokens DB read failed: permission denied")`; asserts the WARNING message length is bounded (≤400 chars) so over-long credential-shaped substrings would be truncated by `_redacted_excerpt`.

**Audit-row paths (T-A.2):**
- All 3 audit-row failure paths (claim OSError, replace OSError, RuntimeError exhaustion) close the row with `error_message=<redacted excerpt of failure>` via the existing `_redacted_excerpt` helper. The locked grep substrings ("auto-detected" + "renamed") prefix the redacted excerpt, ensuring operator discoverability without compromising redaction discipline.

No env-var contents leaked in any caplog or audit-row text across the full fast suite.

---

## §13 Marker file teardown

`.copowers-subagent-active` will be removed BEFORE the final return-report commit per dispatch brief §1.2.
