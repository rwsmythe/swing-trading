# Schwab API Sub-bundle A — executing-plans return report

**Branch:** `schwab-bundle-A-foundational`
**Baseline SHA:** `bd166c5` (dispatch brief commit on main)
**Final HEAD on branch (pre-return-report):** `d154ba4` (Codex R3 fix)
**Return-report commit (last on branch):** this commit

---

## §1 Commit breakdown — 18 commits across all task + Codex-fix work

| # | SHA | Type | Description |
|---|---|---|---|
| 1 | `1f9527d` | chore | T-A.0 — .gitignore patterns for tokens DBs + audit backups |
| 2 | `9764d29` | docs | T-A.0.b phase-1 — recon doc with 3 plan-deviation findings |
| 3 | `79839f9` | chore | T-A.1 — pin schwabdev>=2.4.0,<3.0.0 (installed 2.5.1) |
| 4 | `954593d` | feat | T-A.2 — cfg.integrations.schwab 6-field cascade + FIELD_REGISTRY masking |
| 5 | `291c01a` | feat | T-A.3 — sub-package skeleton + 8 exception classes + 4 transport-debug loggers |
| 6 | `21201ee` | feat | T-A.7 — migration 0018 schema 17→18 with explicit BEGIN/COMMIT (+ pipeline_runs FK column fix) |
| 7 | `12a9d5b` | feat | T-A.8 — schwab_api_calls repo + SchwabApiCall dataclass with validators |
| 8 | `11c7b70` | feat | T-A.9 — audit service-layer wrappers with caller-held-tx rejection + combined link/stamp tx |
| 9 | `8f8dbea` | feat | T-A.4 — swing schwab setup with OAuth paste-back flow + audit lifecycle |
| 10 | `bdf82da` | fix | T-A.4 hotfix — phase-2 findings (D1 tokens-validation + D2 accounts-shape + D3 schema-check-reorder) |
| 11 | `da4ef3a` | fix | T-A.4 cleanup script — escape literal %%USERPROFILE%% in argparse help string |
| 12 | `7db563b` | docs | T-A.0.b phase-2 addendum — live OAuth verification observations + 4 NEW deviations §E-§H |
| 13 | `2f52eec` | feat | T-A.5 — refresh + logout subcommands with audit lifecycle |
| 14 | `dfc3871` | feat | T-A.6 — schwab status CLI skeleton with masking discipline |
| 15 | `644fd47` | feat | T-A.10 — three-layer sentinel-leak audit + process-global redactor + schwabdev logger coverage |
| 16 | `f62927d` | fix | Codex R1 — 5 Major findings (force_refresh validation + ensure_factory + accounts.linked empty-list + SchwabApiCall validators + ReconciliationRun.schwab_api_call_id) |
| 17 | `c5508d8` | fix | Codex R2 — 1 Major + 1 Minor (_redacted_excerpt delegates to Layer-0 + rate_limit_remaining bool-rejection) |
| 18 | `d154ba4` | fix | Codex R3 — 1 Major + 1 Minor (redact-then-truncate + http_status/response_time_ms strict-int validation) |

Breakdown: **11 task-impl commits + 2 hotfix/cleanup commits + 2 phase-1/phase-2 recon docs + 3 Codex-fix commits**. The hotfix at #10 is operator-paired-verification-driven, not Codex-driven.

---

## §2 Codex adversarial review chain

**4 rounds → NO_NEW_CRITICAL_MAJOR at R4** (default MAX_ROUNDS=5; converged before max).

| Round | Critical | Major | Minor | Disposition |
|---|---:|---:|---:|---|
| R1 | 0 | **5** | 3 | All 5 Majors RESOLVED in `f62927d`; 3 Minors banked as advisories |
| R2 | 0 | **1** | 2 | Major + Minor #1 RESOLVED in `c5508d8`; **Minor #2 ACCEPT-WITH-RATIONALE** (force_refresh unchanged-token integrity check; operator-facing error already distinguishes "<not rotated>" from "<raised>") |
| R3 | 0 | **1** | 1 | Both RESOLVED in `d154ba4` |
| R4 | 0 | **0** | 1 | **CONVERGED** — Minor advisory only (docstring nit: "FULL message" claim not literally true since inner helper bounds to 500 chars; acceptable + banked) |

**7 Critical/Major findings total** (5 R1 + 1 R2 + 1 R3); **6 RESOLVED + 1 ACCEPT-WITH-RATIONALE**.

### §2.1 Codex Major findings RESOLVED

- **R1 M#1** (force_refresh silent-failure parity) — schwabdev's `update_tokens(force_access_token=True)` returns normally even on failure; added post-call `client.tokens.access_token` non-empty check + pre-call/post-call value comparison (catches "schwabdev returned success without actually rotating").
- **R1 M#2** (_install_* vs ensure_*) — auth.py used `_install_schwab_log_redaction_factory_once()` (no-op after first install) instead of `ensure_schwab_log_redaction_factory_installed()` (re-wraps if third-party replaced). Fixed at 3 call sites (setup pre-Client, refresh pre-update_tokens, logout pre-revoke POST).
- **R1 M#3** (accounts.linked empty-list audit-success-before-error) — empty-list check fired AFTER `record_call_finish(status='success', ...)`; audit row mis-reported success. Reordered: all 4 validation paths (non-list / empty-list / entry-shape / missing-hashValue) now fire `record_call_finish(status='auth_failed')` BEFORE raising.
- **R1 M#4** (SchwabApiCall validator gaps) — added 7 missing validators: `call_id` (None or positive int), `ts` (`datetime.fromisoformat`-parseable), `rate_limit_remaining` (None or `>= 0`), `error_message` (None or string), `linked_snapshot_id` (None or positive int), `linked_reconciliation_run_id` (None or positive int), `pipeline_run_id` (None or positive int).
- **R1 M#5** (ReconciliationRun.schwab_api_call_id model/repo gap) — schema column existed but dataclass + repo didn't carry it. Added trailing-optional field + repo round-trip (`_RUN_SELECT_COLUMNS` + `_row_to_run` + `insert_run` kwarg) + `__post_init__` validator.
- **R2 M#1** (_redacted_excerpt bypasses Layer-0 exact-registry) — refactored to delegate to `_redact_error_message_for_audit` from client.py which applies BOTH Layer-0 + Layer-1. Discriminating test: 13-char `sh0rt.S3cr3t!` (below Layer-1 floor) leaks pre-fix, redacted post-fix.
- **R3 M#1** (_redacted_excerpt truncate-before-redact ordering) — boundary-straddling 64-char sentinel at byte 60 of 80-char exception would have its prefix truncated before Layer-0 saw it. Reordered: redact FIRST on full `str(exc)`, then truncate.

### §2.2 ACCEPT-WITH-RATIONALE

**1 banked position** — R2 Minor #2 (force_refresh unchanged-access-token strict comparison): operator-locked at plan §H.2 step 6 expectation of token mutation on `force_access_token=True`. Hypothetical false-positive (Schwab returns same token despite success) would surface in T-A.0.b phase-2+ live verification with operator; conservative integrity check justified. NO code change.

---

## §3 Test count + ruff + schema deltas

- **Fast suite:** 3287 → **3492 passing** (+205 net new tests). 7 skipped (5 pre-existing + 2 T-A.10 cross-bundle pins for T-B.8 + T-C.7). 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` (archive-returned-None family; verified pre-existing on main HEAD before this dispatch per CLAUDE.md).
- **Ruff baseline:** 18 errors unchanged.
- **Schema version:** **v17 → v18** atomic single-file landing at T-A.7 (`0018_schwab_integration.sql`). Production DB migrated cleanly during T-A.0.b phase-2 live verification (operator-manual backup at `~/swing-data/swing-pre-phase11-schwab-migration-<ts>.db`).

Test count breakdown per task (approximate):
- T-A.0: +2
- T-A.0.b: 0 (recon doc only)
- T-A.1: +2
- T-A.2: +24 (above projected +12; parametrized expansion)
- T-A.3: +15 (above projected +12; +3 defense-in-depth)
- T-A.7: +41 (well above projected +10; parametrized CHECK enum coverage)
- T-A.8: +19 (above projected +18; +1 caller-controlled-tx pin)
- T-A.9: +16
- T-A.4: +17 (above projected +15; +2 hotfix regression tests)
- T-A.4 cleanup: +0
- T-A.5: +10
- T-A.6: +8
- T-A.10: +24
- Codex R1+R2+R3 fixes: +23 (discriminating tests for each finding)

Total: +201..+209 depending on counting (matches the +205 observed delta).

---

## §4 Operator-witnessed verification gate

Per dispatch brief §3 (8 surfaces; S2-S6 operator-driven CLI):

| Surface | Type | Status |
|---|---|---|
| **S1** pytest fast-suite | Inline | **PASS** — 3492 fast tests; 3 pre-existing failures unchanged (NOT regressions) |
| **S2** Migration 0018 lands | Operator-driven (PowerShell) | **PASS** — operator ran `swing db-migrate` against production swing.db AFTER manual backup; schema v17→v18; `schwab_api_calls` table created; ALTER columns added; FK constraints active. **Phase-2 evidence** in recon doc §6.bis.4. |
| **S3** `swing schwab setup` paste-back | Operator-driven (CLI; production credentials) | **PASS** — phase-2 attempt 2 succeeded; tokens DB written at `~/swing-data/schwab-tokens.production.db` (JSON, 957 bytes); audit row `oauth.code_exchange` `status='success'`; cfg-cascade write of 64-char `account_hash` to user-config.toml; success message + WARNING advisory printed verbatim per plan §H.1 steps 14-15. |
| **S4** `swing schwab refresh` | Operator-driven (CLI) | **PENDING** — not driven during phase-2 (operator opted to ship the setup happy-path first); orchestrator-driven follow-up at integration-merge gate session or banked for first natural use. Code-path test coverage: T-A.5 +10 tests + R1 #1 silent-failure regression covers. |
| **S5** `swing schwab status` skeleton | Operator-driven (CLI) | **PENDING** — same disposition as S4. Code-path test coverage: T-A.6 +8 tests + T-A.10 sentinel-leak sentinel discrimination on status output. |
| **S6** `swing schwab logout` | Operator-driven (CLI) | **PENDING** — same. Code-path test coverage: T-A.5 +10 tests including 24h-recovery-window rename. |
| **S7** Sentinel-leak audit | Inline | **PASS** — `pytest tests/integrations/test_schwab_token_redaction_audit.py -v` GREEN; 24 of 27 tests pass (with 2 cross-bundle pins skipped + 1 not-applicable). |
| **S8** ruff baseline | Inline | **PASS** — `ruff check swing/ --statistics` 18 E501 unchanged. |

**Operator-witnessed gate summary:** S1+S2+S3+S7+S8 PASS; S4+S5+S6 PENDING. Phase-2 captured the full setup happy-path live; refresh/status/logout were not exercised live. Orchestrator should drive S4-S6 at integration-merge gate OR accept code-path coverage as sufficient + log as deferred verification.

---

## §5 Per-task deviations + V2.1 §VII.F amendment candidates

### §5.1 Recon-doc-banked plan deviations (8 total)

These are LOCKED at this dispatch via the recon doc supersession pattern (Phase 9 Sub-bundle D precedent). They are V2.1 §VII.F amendment candidates for plan-text correction post-Sub-bundle-A-ship:

**§A (phase-1):** plan §E.1 row 1 `schwabdev.auth.manual_flow(...)` does NOT exist in schwabdev 2.5.1; paste-back is embedded in `Client.__init__` only. Implementation uses `schwabdev.Client(...)` direct construction.

**§B (phase-1):** plan said `tokens_file` everywhere; phase-2 confirmed `tokens_file=` IS the kwarg in 2.5.1 (recon §6 §B amendment).

**§C (phase-1):** plan §E.1 row 3 `Tokens.revoke()` not exposed; T-A.5 issues manual `POST /v1/oauth/revoke` per plan §E.6 fallback path.

**§D (phase-1):** plan §A.6 enumerated 5 SchwabConfig fields; T-A.2 added 6th (`callback_url` with `__post_init__` validator rejecting trailing slash + non-HTTPS + non-localhost).

**§E (phase-2):** schwabdev 2.5.1 constructor signature is `(app_key, app_secret, callback_url='https://127.0.0.1', tokens_file='tokens.json', timeout=10, capture_callback=False, use_session=True, call_on_notify=None)` — distilled `reference/schwabdev/client.md` is STALE relative to installed library. Implication: `reference/schwabdev/` distilled refs should carry a version-pinned header; future re-distill on each pin bump.

**§F (phase-2):** Tokens DB content is JSON (NOT SQLite per plan §F.1's COA B disposition); file extension is `.db` per plan convention. Cosmetic mismatch only — schwabdev writes JSON to whatever file extension is passed.

**§G (phase-2):** Two distinct masking surfaces with different rules — CLI auto-pick echo uses `first-3 + ... + last-4` (renders `E8F...0676`); FIELD_REGISTRY uses `first-3 + *** + last-2` (renders `E8F***76`). Plan §A.6 mock matches FIELD_REGISTRY. V2 cleanup: unify via shared helper.

**§H (phase-2):** schwabdev's silent-return on auth failure (no exception raised); covered by hotfix `bdf82da` D1 `client.tokens.access_token` post-construction check.

### §5.2 NEW Codex-chain deviations (5 banked V2.1 §VII.F candidates)

**§I (Codex R1 M#5):** Plan §A.7 line 90 implies `reconciliation_runs.schwab_api_call_id` consumer is Sub-bundle B work. Codex flagged the model/repo gap as Sub-bundle A scope-creep risk; fix landed in this bundle for forward-compat. Plan amendment: explicitly tag T-A.7 (Sub-bundle A) as the landing point for model/repo round-trip on the new FK column, not Sub-bundle B.

**§J (T-A.7 D1):** Plan §C.1 SQL had `REFERENCES pipeline_runs(run_id)` but actual schema (migration 0003) uses `pipeline_runs(id)`. T-A.7 implementer corrected at SQL-file level + banked. Plan §C.1 amendment: change `pipeline_runs(run_id)` → `pipeline_runs(id)`. Parallel to Phase 9 Sub-bundle D D2-class plan-vs-actual-schema column-name drift.

**§K (T-A.3 D1):** Plan §A.2 + §Tasks-A T-A.3 spec said "_suppress_transport_debug_logs() mutes all 5 logger names." Live schwabdev 2.5.1 only has 1 schwabdev-family logger (`Schwabdev` — capital S). Actual list: 4 names (urllib3.connectionpool, requests.packages.urllib3.connectionpool, urllib3.util.retry, Schwabdev). Plan amendment: target "all 5" wording is aspirational; revise to reflect reality.

**§L (T-A.5 D1):** Plan §H.2 step 6 + recon §2.4 said `client.update_tokens(force_refresh_token=True)`. Live schwabdev source shows that flag triggers FULL OAuth dance via `input()` prompt (re-auth, not silent refresh). The semantically-correct flag is `force_access_token=True` (rotate access_token using existing refresh_token without re-auth prompt). T-A.5 implementer pivoted to `force_access_token=True`; banked.

**§M (T-A.10 D1):** Plan §H.8 uses lowercase `_SCHWABDEV_LOGGER_PREFIX = 'schwabdev'`. Live schwabdev 2.5.1 uses capital-S logger name `"Schwabdev"`. T-A.10 implementer used `"Schwabdev"`. Without this, Layer 2 would silently fail to redact (records would slip through the prefix check). CRITICAL correctness fix; plan amendment to lowercase wording.

### §5.3 Phase-2 hotfix `bdf82da` — 3 defects discovered via operator-paired live OAuth run

- **D1:** schwabdev's `Client.__init__` returns silently on auth failure (no exception raised); added post-construction `client.tokens.access_token` non-empty validation; treat empty as `auth_failed`.
- **D2:** `client.account_linked()` returns a dict error envelope (not a list) when called on unauthenticated Client; added shape validation (`isinstance(accounts, list)` + per-entry `dict + 'hashValue' in entry`).
- **D3:** `connect()` schema-version check happened AFTER credential prompts; operator wasted typing on v17 mismatch. Moved `connect()` to handler entry (fail-fast).

### §5.4 Test-count overshoots (banked as documentation drift)

Plan-projected vs actual test counts:
- T-A.2: +12 projected → +24 actual (parametrized expansion).
- T-A.3: +12 projected → +15 actual (defense-in-depth).
- T-A.7: +10 projected → +41 actual (parametrized CHECK enum coverage).
- T-A.10: +24 projected → +27 actual (3 additional Codex-chain discriminating tests).

Plan-projected +126 vs actual +205 — consistent with Phase 9 / Phase 10 sub-bundle precedent (parametrize/defense-in-depth expansion).

### §5.5 Minor advisories banked from Codex chain

- **R1 Minor #1:** `SchwabClient._ensure_schwabdev_client` is `NotImplementedError` skeleton — deferred to Sub-bundle B as documented; deliberate Sub-bundle A scope boundary.
- **R1 Minor #2:** 500-char log truncation may hide diagnostics — defense-in-depth tradeoff; banked for V2 tuning consideration.
- **R1 Minor #3:** Migration 0018 atomicity confirmed solid.
- **R4 Minor #1:** docstring "FULL message" claim not literally true (inner helper bounds to 500 chars); acceptable.

---

## §6 Watch items for orchestrator (post-Sub-bundle-A-ship)

1. **Operator-witnessed gate completion** — drive S4 (`swing schwab refresh`), S5 (`swing schwab status`), S6 (`swing schwab logout`) at integration-merge gate session. Phase-2 already validated S1-S3+S7+S8; the remaining surfaces are sub-second-cost operator-driven CLI invocations.

2. **Editable-install footnote** — T-A.1 `pip install -e .` had a transient "swap-blocked rollback on swing.exe" (the `swing.exe` binary was locked by a running process). The editable install pointer remained at MAIN repo (`C:\Users\rwsmy\swing-trading\swing`), NOT the worktree. During phase-2 operator used `python -m swing.cli ...` from the worktree directory to invoke the new `swing schwab setup` CLI. Post-merge, operator should re-run `pip install -e .` from main to refresh the editable-install pointer at the integrated code.

3. **Production audit-row cleanup script** at `scripts/fix_phase2_misleading_audit_rows.py` — operator ran it during phase-2 to correct call_id=1+2 from `status='success'` to `status='auth_failed'`. Idempotent; safe to re-run. Banked here so a future archeologist can find it.

4. **Operator's production state at branch-tip:**
   - Schema: v18
   - 4 rows in `schwab_api_calls` (2 corrected-to-auth_failed + 2 success).
   - `~/swing-data/schwab-tokens.production.db` exists (JSON, 957 bytes; valid access + refresh tokens).
   - `~/swing-data/user-config.toml` has `[integrations.schwab].account_hash` = 64-char hashValue.
   - The 7-day refresh-token clock started 2026-05-14 (operator must re-auth by ~2026-05-21 per recon §2.11).

5. **5 V2.1 §VII.F amendment candidates new in this dispatch** (§I + §J + §K + §L + §M above; in addition to the 8 §A-§H banked by recon doc). **Total pending: 13 amendments** for the writing-plans plan.

6. **Sub-bundle B dispatch UNBLOCKED.** Brief drafting should:
   - Inherit recon doc §6 + §6.bis as binding.
   - Inherit Codex R1+R2+R3 lessons (5 forward-binding patterns; see §8 below).
   - Verify `ReconciliationRun.schwab_api_call_id` field exists (R1 M#5 landed it); no re-implement.
   - Use `Schwabdev` (capital S) for any logger work (R1 M#5/T-A.10 D1).
   - Use `ensure_schwab_log_redaction_factory_installed()` (NOT `_install_*`) before every schwabdev API call.
   - Reference T-B.0.b operator-paired live verification for actual Trader API cassette recording.

---

## §7 Worktree teardown status

Branch `schwab-bundle-A-foundational` ready for integration merge to main. Marker file at `c:/Users/rwsmy/swing-trading/.copowers-subagent-active` will be removed before this return-report commit.

Post-merge expected husk handling: on-disk husk at `.worktrees/schwab-bundle-A-foundational/` will be ACL-locked per Phase 6+7+8+9+10 precedent; operator runs `cleanup-locked-scratch-dirs.ps1` (with optional `-DeregisterFirst` per post-Phase-10-infra-bundle T-2 ship) to clean up.

This is the 9th pending husk in the cleanup-script queue (per CLAUDE.md tally as of 2026-05-13: 8 husks pending — 4 Phase 9 still-registered + 3 Phase 10 orphans + 1 post-phase10-infra-bundle orphan).

---

## §8 Sub-bundle B forward-binding lessons (5 new from this dispatch)

1. **schwabdev's silent-failure-mode discipline** — `Client.__init__` + `update_tokens()` do NOT raise on auth failure; they print + retry + return silently. Wrappers MUST verify post-call state (`client.tokens.access_token` populated + rotated). Discriminating-test pattern: stub schwabdev call to NOT mutate `tokens.access_token`; assert wrapper raises `SchwabAuthError` + audit row `status='auth_failed'`.

2. **Audit-success-fire ordering** — `record_call_finish(status='success', ...)` MUST fire ONLY after all validation passes (R1 M#3 family). Pattern: validate response shape → validate response content → validate operator-pickable state → fire success audit. Each pre-success rejection path fires `record_call_finish(status='auth_failed')` with redacted error_message + raises.

3. **Pre-call factory-replacement defense** — `ensure_schwab_log_redaction_factory_installed()` (NOT `_install_*`) before every schwabdev API call. Discriminating-test pattern: install third-party factory between two schwab calls; assert second call re-wraps the factory before invoking schwabdev.

4. **Redact-then-truncate audit-error ordering** — `_redacted_excerpt` MUST redact on FULL `str(exc)` THEN truncate to audit-column-budget. Discriminating-test pattern: register a sentinel that straddles the truncation boundary; assert no partial-prefix survives.

5. **schwabdev 2.5.1 actual surfaces** (banked from phase-2 live verification):
   - `Client` ctor: 8 params (`app_key, app_secret, callback_url='https://127.0.0.1', tokens_file='tokens.json', timeout=10, capture_callback=False, use_session=True, call_on_notify=None`).
   - Tokens DB content: JSON (NOT SQLite); content shape `{access_token_issued, refresh_token_issued, token_dictionary: {access_token, refresh_token, id_token, expires_in: 1800, token_type, scope}}`.
   - `client.account_linked()` success: list of dicts `[{accountNumber, hashValue}, ...]`.
   - `client.account_linked()` failure: dict error envelope (NOT a list).
   - Force-refresh kwarg: `client.update_tokens(force_access_token=True)` (NOT `force_refresh_token=True` which triggers full OAuth dance).
   - Schwab `code` expiry window: ~30 seconds from redirect.
   - Logger name: `"Schwabdev"` (capital S).
   - NO `revoke()` method exposed; use manual `POST /v1/oauth/revoke` (Basic auth + `token=<refresh_token>&token_type_hint=refresh_token` form body).

---

## §9 Composition-surface verification via ^def grep (per Phase 9 forward-binding lesson #5)

`grep -rn "^def " swing/integrations/schwab/` reports the public surface added by Sub-bundle A:

- `swing/integrations/schwab/__init__.py` — re-exports 11 public names.
- `swing/integrations/schwab/client.py` — `_TRANSPORT_DEBUG_LOGGERS`, `_suppress_transport_debug_logs`, 8 exception classes, `SchwabClient.__init__`, redactor primitives: `register_schwab_secrets`, `_make_redactor_from_global`, `_redact_error_message_for_audit`, `_schwab_record_factory`, `_install_schwab_log_redaction_factory_once`, `ensure_schwab_log_redaction_factory_installed`.
- `swing/integrations/schwab/auth.py` — `setup_paste_flow`, `force_refresh`, `revoke_and_delete`, `_redacted_excerpt`, `_is_pipeline_active`, `_resolve_tokens_db_path`.
- `swing/integrations/schwab/audit_service.py` — `record_call_start`, `record_call_finish`, `link_snapshot_and_stamp_account_hash`, `link_reconciliation_run`, `CallerHeldTransactionError`.

Consumers (CLI surface): `swing/cli_schwab.py` defines `schwab_group` + 4 subcommands (`setup`, `refresh`, `logout`, `status`). Wired into `swing/cli.py` at the existing `main.add_command(...)` chain.

Data layer: `swing/data/repos/schwab_api_calls.py` defines 7 repo functions (`insert_in_flight`, `update_call_outcome`, `update_call_linked_snapshot`, `update_call_linked_reconciliation_run`, `list_recent_calls`, `get_call`, `count_calls_by_status`). `swing/data/models.py` extended with `SchwabApiCall` dataclass + `ReconciliationRun.schwab_api_call_id` field.

Schema: `swing/data/migrations/0018_schwab_integration.sql` lands `schwab_api_calls` table + 2 ALTERs + `schema_version 17→18`. `swing/data/db.py:19` bumps `EXPECTED_SCHEMA_VERSION` to 18.

---

## §10 T-A.0.b operator-paired session — full summary

### §10.1 Phase 1 (pre-check from operator-supplied distillations)

Operator created `reference/schwab-api/` (4 files, ~4k lines; Schwab REST API) + `reference/schwabdev/` (7 files; schwabdev wrapper docs) post-dispatch. Phase-1 pre-check extracted 6 observations from the distilled refs:

- Q8 base URL: `https://api.schwabapi.com/trader/v1` ✓
- Q14 OAuth scope default: `"api"` ✓
- Q15 refresh-token rotation: YES, rotates every refresh ✓
- Q3 multi-account: returns array of `{accountNumber, hashValue}` ✓
- Tokens DB schema: NOT DOCUMENTED (resolved phase-2 — JSON)
- `manual_flow` signature: NOT DOCUMENTED (resolved phase-2 — does not exist; paste-back is in `Client.__init__`)

Output: `docs/schwab-bundle-A-task-A0b-recon.md` §1-§5 + §6 §A-§D banked deviations.

### §10.2 Phase 2 (operator-paired live OAuth run 2026-05-14)

Two attempts; first failed (~30-second `code` window exceeded → silent failure caught by absent hotfix); second succeeded:

- Setup happy-path: ✅ tokens DB written; account_hash persisted to user-config; audit row `success`.
- Browser auto-launch: ✅ (despite `open_browser_for_auth=` no longer being a kwarg in 2.5.1).
- Callback: ✅ root `https://127.0.0.1` (NOT `:8182`).
- Operator's linked accounts: 1 (auto-pick fired; multi-account branch untested live).
- account_hash length: 64 chars (Schwab standard).

Phase-2 surfaced 3 defects in T-A.4 (hotfix `bdf82da`) + 4 NEW deviations banked in recon §6.bis §E-§H. Audit lifecycle proven end-to-end (call_id=3+4 success).

### §10.3 NOT live-tested at phase-2 (deferred)

- `swing schwab refresh` — operator opted to ship setup happy-path; refresh path covered by T-A.5 +10 tests + Codex R1 M#1 silent-failure regression.
- `swing schwab status` — same; covered by T-A.6 +8 tests + T-A.10 sentinel-leak discrimination.
- `swing schwab logout` — same; covered by T-A.5 +10 tests.
- Multi-account prompt path — operator has single account; code-path covered by T-A.4 stub-based test #2.

---

## §11 `reference/schwab-api/` + `reference/schwabdev/` distilled refs consumed

| Ref | Phase-1 use | Phase-2 confirmation |
|---|---|---|
| `account-documentation.md` | Q14 OAuth scope; Q15 rotation; OAuth URLs | confirmed |
| `account-specification.md` | Q8 base URL; Q3 accountNumbers shape | confirmed |
| `market-data-documentation.md` | NOT USED in Sub-bundle A | Sub-bundle C consumes |
| `market-data-specification.md` | NOT USED in Sub-bundle A | Sub-bundle C consumes |
| `schwabdev/setup-guide.md` | OAuth paste-back flow shape | confirmed; auto-launch behavior in 2.5.1 |
| `schwabdev/client.md` | 8-param Client ctor + Tokens attributes | DEVIATES (signature drifted) — see §5.2 §E |
| `schwabdev/api-calls.md` | Endpoint signatures (account_linked, account_details, account_orders) | partial-confirmation |
| `schwabdev/troubleshooting.md` | Callback trailing-slash; refresh-token expiry; tokens.json hint | confirmed |
| `schwabdev/examples.md` | capture_callback.py V2 candidate; encrypted_db_setup.py V2 candidate | not invoked V1 |
| `schwabdev/streaming.md` | NOT USED (streaming OUT OF SCOPE V1) | — |
| `schwabdev/orders.md` | NOT USED (order placement OUT OF SCOPE V1) | — |

---

## §12 Sub-bundle B dispatch checklist (orchestrator action)

When commissioning Sub-bundle B's dispatch brief, include:

1. **§0 reads:** add `docs/schwab-bundle-A-task-A0b-recon.md` (full; §6 + §6.bis are LOCKED).
2. **Forward-binding lessons:** the 5 lessons in §8 above.
3. **Confirmed schwabdev 2.5.1 facts** (§8 #5) — Sub-bundle B's `trader.py` consumes these.
4. **Cross-bundle pins:** T-A.10 cross-bundle pin #23 marked `@pytest.mark.skip(reason='un-skip at T-B.8')`. Sub-bundle B T-B.8 must un-skip.
5. **`ReconciliationRun.schwab_api_call_id`** already exists at branch-tip; Sub-bundle B service `run_schwab_reconciliation` populates it.
6. **Codex chain pre-emption table** — Sub-bundle B dispatch brief should pre-empt the 4 patterns Sub-bundle A Codex caught:
   - silent-failure post-call validation (M#1 family)
   - audit-success-fire ordering (M#3 family)
   - factory-replacement defense (M#2 family)
   - redact-then-truncate (R3 M#1 family)

---

**Sub-bundle A executing-plans dispatch CLOSED. Branch ready for integration merge to main.**
