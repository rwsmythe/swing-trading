# Phase 12 Sub-bundle B — executing-plans return report

**Branch:** `phase12-bundle-B-schwab-web-ui-friendliness`
**Baseline SHA:** `4ed1892` (post-Phase-12-Sub-bundle-A handoff doc on main)
**Branch tip SHA (pre return-report commit):** `ce7fb62` + this report commit
**Dispatch brief:** `docs/phase12-bundle-B-schwab-web-ui-friendliness-executing-plans-dispatch-brief.md` (plays plan-role per operator scope decision; no separate writing-plans dispatch)

---

## §1 Final HEAD + commit breakdown

15 commits + this return report on top of `4ed1892`:

| SHA | Type | Subject |
|---|---|---|
| `26e960f` | docs | dispatch brief (plays plan-role) |
| `0336811` | task-impl T-B.2 | `feat(config): SchwabIntegrationConfig.client_id + client_secret fields + FIELD_REGISTRY masked entries` |
| `af10a37` | task-impl T-B.1 | `feat(schwab): user-config.toml cfg-tier joins SCHWAB credential cascade (env > cfg > prompt)` |
| `4014498` | code-review | `fix(schwab): rephrase T-B.1 partial-env error hint to mention cfg-tier fallback` |
| `043da03` | task-impl T-B.3 | `feat(cli): swing config set integrations.schwab.client_id + client_secret writes to user-config.toml` |
| `7ed9e1e` | task-impl T-B.4 | `feat(schwab): setup_paste_flow_with_callback_url manual token exchange + refactor setup_paste_flow shared audit/picker helper` |
| `302f324` | task-impl T-B.4 | `feat(web): GET/POST /schwab/setup route + template + SchwabSetupVM (web OAuth paste-back form)` |
| `e7cdc27` | code-review | `docs(schwab): align T-B.4 service-helper docstrings with surface='cli' v18 LOCK` |
| `0d4cb7b` | code-review | `fix(phase12-bundle-B): Codex review-fix — populate unresolved_material_discrepancies_count + USERPROFILE+HOME monkeypatch on /schwab/setup tests` |
| `ed92912` | task-impl T-B.6 | `test(schwab): sentinel-leak audit covers cfg-cascade-sourced credentials` |
| `4e0b712` | task-impl T-B.5 | `docs(cycle-checklist+CLAUDE): Phase 12 Sub-bundle B web OAuth + cfg-cascade documentation` |
| `e418d56` | Codex R1 fix | `fix(phase12-bundle-B): Codex R1 fixes — apply_overrides at Schwab CLI/web entry points (Critical #1) + 5 Major + 2 Minor` |
| `b6b4375` | Codex R2 fix | `fix(phase12-bundle-B): Codex R2 fixes — schwabdev compat test invokes real Tokens loader (Major #1) + fsync discipline on tokens-file write (Minor #1) + docstring step-order alignment (Minor #2)` |
| `5ee36ba` | Codex R3 fix | `fix(phase12-bundle-B): Codex R3 fixes — preserve literal '+' in OAuth code via unquote not parse_qs (Major #1) + best-effort parent-dir fsync after os.replace (Minor #1)` |
| `ce7fb62` | Codex R4 polish | `fix(phase12-bundle-B): Codex R4 Minor — align fsync suppress list with comment (add NotImplementedError)` |

**Breakdown:**
- 1 dispatch brief
- 6 task-impl commits (T-B.1 cascade, T-B.2 cfg + FIELD_REGISTRY, T-B.3 CLI, T-B.4 service-helper, T-B.4 web routes, T-B.5 docs, T-B.6 sentinel-leak — note T-B.4 lands as 2 logically-separated commits per CLAUDE.md staging convention)
- 4 Codex/code-review fix commits (R1 Critical+Major+Minor batch, R2, R3, R4)
- 2 polish commits (T-B.1 error hint, T-B.4 docstring drift)
- 1 mid-cycle code-review fix (T-B.4 discrepancy count + USERPROFILE+HOME)

T-B.7 (`GET /schwab/status` web counterpart) **DEFERRED** to follow-up dispatch per Outcome B decision rule.

---

## §2 Codex round chain

**4 Codex rounds → NO_NEW_CRITICAL_MAJOR** (convergent tapering matches Phase 11 + Phase 12 Sub-bundle A precedent):

| Round | Critical | Major | Minor | Resolution Commit | Notes |
|---|---:|---:|---:|---|---|
| R1 | 1 | 5 | 3 | `e418d56` | Critical: cfg-stored creds not consumed by main web/CLI entry points (apply_overrides missing). 5 Major: audit ordering, schwabdev compat test, tmp concurrency, error msg, URL parsing. 2 Minor RESOLVED (a11y + docstring drift), 1 ACCEPTED (surface='cli' V2 banked). |
| R2 | 0 | 1 | 2 | `b6b4375` | Major: schwabdev compat test reimplemented load logic instead of invoking real `Tokens(...)`. 2 Minor: fsync discipline + docstring step-order. |
| R3 | 0 | 1 | 1 | `5ee36ba` | Major: `parse_qs` decodes `+` as space — OAuth code corruption risk. 1 Minor: parent-dir fsync. |
| R4 | 0 | 0 | 1 | `ce7fb62` | NO_NEW_CRITICAL_MAJOR convergence. 1 Minor (suppress list inconsistency) polished inline. |

**Aggregate:**
- 1 Critical (resolved in R1)
- 7 Major (all resolved across R1+R2+R3)
- 7 Minor (5 resolved, 2 accepted/banked as V2 amendment candidates)
- ZERO ACCEPT-WITH-RATIONALE on Critical+Major — every Critical+Major finding had a code-content resolution

Thread continuity via `threadId=019e2bcc-4b3d-79d3-aec2-e681eb0d1abb` preserved across all 4 rounds.

---

## §3 Test count + ruff + schema deltas

- **Fast suite pre-bundle (main HEAD `4ed1892`):** 3791 passing + 4 pre-existing failures (NOT 3 as brief §0.7 listed — see §7 Watch item #2 below) + 5 skipped
- **Fast suite post-bundle (worktree HEAD `ce7fb62`):** 3857 passing + 4 pre-existing failures unchanged + 5 skipped
- **Test count delta:** **+66 fast tests** (above brief projection +18-28; matches Sub-bundle A overshoot precedent +35 from projected +4)
- **Slow suite delta:** +1 (real schwabdev `Tokens(...)` compat regression test in T-B.4)
- **Ruff baseline:** 18 E501 in `swing/` unchanged
- **Schema version:** v18 unchanged (consumer-side only)

---

## §4 Operator-witnessed verification surfaces

Status: **PENDING orchestrator-driven gate** post-merge. Brief §4 enumerates 9 gate surfaces (S1-S9). All inline-verifiable surfaces (S1 pytest, S7 ruff, S8 sentinel-leak, S9 mask rendering) PASS during the dispatch.

Operator-driven surfaces pending:
- **S2** `swing config set` cfg-cascade write path (set test creds + verify masked render + verify user-config.toml content)
- **S3** CLI cascade resolution with env vars cleared (`swing schwab status --environment production` with no env vars + cfg set → no prompt fires)
- **S4** Web GET /schwab/setup (Chrome MCP browser render verification)
- **S5** Web POST /schwab/setup completion (operator pastes real Schwab callback URL; HX-Redirect to `/config?schwab_setup=ok`; tokens DB written; fresh 7-day clock starts; `swing schwab status` shows LIVE)
- **S6** (optional) cleanup-script `-DeregisterFirst` regex regression (orchestrator may skip if Sub-bundle A T-A.4 gate already validated)

S5 destructively re-auths operator's production tokens DB. Production-write classifier soft-block awareness: orchestrator pre-authorizes via gate-path.

---

## §5 Per-task deviations from brief

### T-B.2 deviations

1. **+9 tests vs projected +4** — natural splits (happy/default distinct; per-field non-str rejection; FIELD_REGISTRY-shape vs CLI-output-masking). Matches Sub-bundle A overshoot precedent.
2. **`swing/config_overrides.py` extension required** — added `integrations.schwab.client_id` + `client_secret` to `_V1_PATHS` tuple + `apply_overrides` cascade. Brief enumerated 2 production files; this is a 3rd. Necessary because `get_field_source` raises `ValueError` for paths not in `_V1_PATHS`, and `swing config show` invokes it per-path. Spirit-of-spec; mirrors Sub-bundle A T-A.2 `account_hash` precedent.
3. **2 fixture-test updates required** — `test_registry_has_expected_v1_fields` (set-equality on FIELD_REGISTRY paths) + `test_vm_has_expected_rows` (row count + path list). Mechanical updates.

### T-B.1 deviations

1. **+9 tests vs projected +5-7** — natural splits (env wins precedence, cfg-tier resolution, partial-cfg fall-through, allow_prompt=False discipline, sentinel leak, whitespace handling).
2. **Private helper `_safe_cfg_attr` added** — duck-typed cfg attr access required for backwards-compat with Sub-bundle A test fixtures using minimal `SimpleNamespace` stubs without `integrations.schwab.client_id`/`client_secret` sub-attrs. 3-line helper; scope-bounded; private.
3. **`del cfg, environment` line removed** — cfg now consumed by Tier-2; environment is reserved for future per-env credential resolution (V2 candidate).

### T-B.3 deviations

1. **Decision B (code changes required) vs brief-hint of "possibly no code changes"** — existing `swing config set` infrastructure did NOT auto-handle masked FIELD_REGISTRY entries:
   - `_EDITABLE_SPECS` filter excluded ALL masked specs (`if not s.masked`)
   - `config_set` used 2-part `section, key = field_path.split(".")` — crashes on 3-part `integrations.schwab.client_id`
   - `delete_user_override` raised ValueError for non-2-part paths
2. **New `_MASKED_WRITEABLE_PATHS` frozenset allowlist** — narrow (client_id + client_secret only; account_hash EXCLUDED preserving Sub-bundle A T-A.2 design intent). 2-element primitive; V2-scaling candidate banked.
3. **New `_write_override_nested` helper** for N-part FIELD_REGISTRY paths in `swing/cli_config.py`.
4. **`delete_user_override` generalized** to N-part paths with bottom-up empty-parent prune in `swing/config_user.py`. 2-part backwards-compat preserved.
5. **+8 tests vs projected +2** — split per-field accept/reject pairs + reset path + empty-parent prune + allowlist regression pin + end-to-end cascade integration.
6. **T-B.2 stale comments** at `swing/config_validation.py:91-93` + `swing/config_overrides.py:25-26` saying client_id/client_secret are "NOT editable via `swing config set`" now factually incorrect post-T-B.3. Banked as V2.1 §VII.F doc-amendment candidate; not corrected inline to minimize cross-task churn.

### T-B.4 deviations (largest)

1. **Outcome B (manual token exchange) LOCKED** per operator-paired investigation — schwabdev's `Client.__init__` calls `input()` blocking on stdin for paste-back; no programmatic kwarg ingestion. New service helper `setup_paste_flow_with_callback_url` mirrors schwabdev's `Tokens._post_oauth_token` HTTP shape + `Tokens._set_tokens` JSON file format byte-for-byte. **BINDING ARCHITECTURE DECISION** for any future broker integration that wraps stdin-blocking SDK behavior.
2. **T-B.7 DEFERRED** to follow-up dispatch per Outcome-B decision rule. HX-Redirect target = `/config?schwab_setup=ok` until T-B.7 lands `/schwab/status`.
3. **`surface='cli'` for web audit rows** — v18 CHECK enum is `('pipeline', 'cli')` only; schema migrations out-of-scope for B. Banked as **V2.1 §VII.F amendment candidate** — widen enum to `('pipeline', 'cli', 'web')` via `0019_*.sql` migration in a future dispatch.
4. **2 commits instead of 1** — auth.py service refactor (`7ed9e1e`) + web routes (`302f324`). Per CLAUDE.md staging convention; clearer review.
5. **+22 tests vs projected +7** — 10 service-helper + 12 route. Plus +3 from review-fix (banner-rendering tests + USERPROFILE+HOME determinism).
6. **`SchwabSetupVM.unresolved_material_discrepancies_count` populated** via review-fix at `0d4cb7b` after CQ review caught the cross-bundle Phase 10 T-E.3 base-layout pin gap (every base-layout VM populates this for global discrepancy banner).
7. **USERPROFILE+HOME monkeypatch** added to all 12 web route tests at `0d4cb7b` per CLAUDE.md gotcha discipline.

### T-B.5 deviations

1. **2 new CLAUDE.md gotchas** appended at end of Gotchas section (matches Finviz token + Schwab gotcha precedent shapes). Status-line top-of-file paragraph LEFT untouched per brief §3 T-B.5 — orchestrator owns at integration-merge time.
2. **Cycle-checklist restructured** — initial-setup section expanded from 5 → 7 steps to add web-as-primary + CLI-as-fallback. Weekly re-auth section reframed to lead with web URL.

### T-B.6 deviations

1. **Used direct `resolve_credentials_env_or_prompt` invocation** instead of CliRunner-mediated `swing schwab status` invocation. Brief listed this as one of three options ("focused mock that triggers the redactor"). Mirrors T-B.1's `test_schwab_credential_cascade.py` `_cfg_with` precedent.
2. **+2 tests matches projection exactly.**

---

## §6 Codex Major findings ACCEPTED with rationale

**ZERO ACCEPT-WITH-RATIONALE on Critical+Major** across all 4 rounds — every finding had a code-content resolution.

Minor items accepted/banked:
- **R1 Minor #1** (`surface='cli'` operationally ambiguous) → ACCEPTED + banked as V2.1 §VII.F amendment candidate (schema v18 → v19 to widen CHECK enum)
- **R4 Minor #1** (suppress list incomplete) → RESOLVED inline at `ce7fb62` (added `NotImplementedError`)

---

## §7 Watch items for orchestrator

1. **Operator-witnessed gate driving** — orchestrator drives S2-S5 via operator-paired CLI/browser session. S5 destructively re-auths operator's production tokens DB (fresh 7-day clock starts at gate time; current tokens DB clock expires ~2026-05-22). S2-S3 use TEST credential values; cleanup post-gate via `swing config reset` to restore env-var-only or prompt-only path.

2. **Brief §0.7 baseline statement was off by one** — listed 3 pre-existing Phase 8 walkthrough failures; actual baseline includes a 4th pre-existing failure at `tests/integrations/test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction`. Sentinel `AUTH_BYTES_DO_NOT_LEAK_ABCDEF0123456789012345` leaks into audit `error_message` because the RuntimeError message text is constructed by test code itself (not registered with the redactor). Verified pre-existing on `4ed1892` via `git stash` round-trip. NOT a B-introduced regression. Banked as follow-up triage candidate: register `_access_token` sentinel via `register_schwab_secrets` proactively in `setup_paste_flow` before schwabdev construction, OR adjust the test to use a hex/base64-shaped sentinel.

3. **V2 candidates banked** (see §10 forward-binding lessons + below):
   - **T-B.7 `/schwab/status` web counterpart** — HX-Redirect target retargets from `/config?schwab_setup=ok` to `/schwab/status` when T-B.7 ships
   - **`surface='web'` CHECK enum widening** (v18 → v19 schema migration; resolves audit-row ambiguity)
   - **Option B HTTPS callback handler** (eliminates paste-back entirely; substantial complexity)
   - **Per-environment-namespaced credentials** (separate `[integrations.schwab.sandbox]` / `[integrations.schwab.production]` tables)
   - **Web multi-account picker** (V1 raises; banked V2 picker)
   - **Token encryption-at-rest** via schwabdev's optional `encryption=<key>` Fernet wrapper
   - **Promote `masked_writeable` to FieldSpec attribute** so FIELD_REGISTRY is single source of truth for writeability (replaces `_MASKED_WRITEABLE_PATHS` frozenset allowlist as the catalog grows)
   - **`/config?schwab_setup=ok` query-param consumer** — currently dead query param; future enhancement could surface "Schwab setup successful" toast on `/config`
   - **schwabdev version pin + extended compat test** — Outcome B mirrors schwabdev's private API; defensive version pin in pyproject.toml + extended regression test that constructs a real schwabdev.Client (not just `Tokens`) against the written file
   - **T-B.2 stale-comment cleanup** at `swing/config_validation.py:91-93` + `swing/config_overrides.py:25-26` (factually wrong post-T-B.3; left in place for cross-task churn discipline)

4. **Operator daily-use UX further unblock — DELIVERED on Sub-bundle B ship:**
   - Credentials persist across shells (cfg-cascade path via `swing config set integrations.schwab.client_id`)
   - Web OAuth setup eliminates PowerShell drop-out for weekly re-auth (Option A paste-back form; Option B HTTPS handler banked V2)

5. **Phase 12 Sub-bundle C (auto-correct reconciliation service) commissioning UNBLOCKED** post-B-ship. Per phase3e-todo "ARCHITECTURAL: reconciliation must auto-correct journal-from-Schwab" entry: substantial brainstorm + writing-plans + multi-bundle executing-plans cycle expected. Operator-paced.

6. **3 unresolved material discrepancies (39/40/41)** in production STILL LEFT UNRESOLVED by design pending Sub-bundle C. Phase 10 dashboard banner continues to show "3 unresolved" — accurate state.

7. **Phase 11 + 12-A forward-binding lessons (22 cumulative) remain authoritative** for any future Schwab work.

---

## §8 Worktree teardown status

Branch `phase12-bundle-B-schwab-web-ui-friendliness` will be deleted post-integration-merge per orchestrator workflow. On-disk husk at `.worktrees/phase12-bundle-B-schwab-web-ui-friendliness/` ACL-locked per Phase precedent. Branch name matches the cleanup-script regex `phase\d+[-_]` (per Sub-bundle A T-A.4 tightening) → operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass should pick up the husk cleanly.

Marker file `c:\Users\rwsmy\swing-trading\.copowers-subagent-active` will be removed by the orchestrator at integration-merge time.

---

## §9 Per-task disposition LOCKS

| Task | Disposition | Rationale |
|---|---|---|
| T-B.1 | SHIPPED | 3-tier cascade with intentional Tier-1 raises / Tier-2 falls-through asymmetry |
| T-B.2 | SHIPPED | cfg dataclass + FIELD_REGISTRY masked entries; defensive drop from tracked TOML |
| T-B.3 | SHIPPED | Decision B (code changes required); narrow `_MASKED_WRITEABLE_PATHS` allowlist preserves account_hash V1 design intent |
| T-B.4 | SHIPPED | **Outcome B (manual token exchange) LOCKED** — schwabdev's stdin-blocking `Client.__init__` rules out Outcome A. Web V1 LOCK: singleton account auto-pick; multi-account raises. `surface='cli'` per v18 CHECK constraint. Audit row closes `success` AFTER schwabdev load-back verification (post-R1 reorder). |
| T-B.5 | SHIPPED | docs (cycle-checklist + 2 CLAUDE.md gotchas); status-line top-of-file untouched per orchestrator-owned scope |
| T-B.6 | SHIPPED | Sentinel-leak audit extension matches Sub-bundle A precedent shape exactly |
| T-B.7 | **DEFERRED** | Outcome B decision rule; HX-Redirect target = `/config?schwab_setup=ok` until follow-up dispatch lands `/schwab/status` |

---

## §10 Forward-binding lessons for Phase 12 Sub-bundle C (if commissioned)

1. **Three-tier credential cascade asymmetry pattern** — env partial RAISES (operator-typo signal); cfg partial FALLS THROUGH (file-tier operator-friendly). Lock asymmetry in code + tests + CLAUDE.md when introducing analogous cascade designs.

2. **Outcome A vs Outcome B disposition rule** for any future schwabdev or external-SDK web-wrapping work — pattern is "manual token-exchange byte-for-byte mirroring SDK's private API + atomic tokens-file write + SDK construction reads back". Reusable recipe documented in T-B.4 audit + tokens-file write helpers.

3. **`surface='X'` CHECK constraint workaround pattern** — when an enum surface needs to widen for new functionality at v_N but schema migrations are out of scope, document the deviation in code comment + bank as V2.1 §VII.F amendment + ship the V_N+1 migration in a future dispatch. Pattern matches Phase 9 D §7 sector_industry anchor amendment precedent.

4. **`_MASKED_WRITEABLE_PATHS` allowlist + `_FIELD_PATHS` filter pattern** — canonical way to gate masked CLI fields. V2-scaling option: promote to `FieldSpec.writeable: bool = True` per-entry attribute when the catalog grows beyond 2-3 entries.

5. **N-part dotted-path generalization at write/read/delete** — when introducing nested cfg sub-namespaces, all three call sites (`config_user.py:delete_user_override`, `cli_config.py:_write_override_nested`, `config_overrides.py:get_field_source`) must be touched together. Discriminating tests at each layer.

6. **`apply_overrides()` discipline at Schwab entry points** — Codex R1 Critical surfaced that `swing/web/routes/schwab.py` + `swing/cli_schwab.py:setup,refresh,logout` were using raw `request.app.state.cfg` / `ctx.obj["config"]` without `apply_overrides`. Existing precedent at `cli_schwab.py:982-985, 1266-1269, 1430-1431` already applies overrides on OTHER subcommands. **Forward-binding lesson:** ANY new Schwab CLI subcommand or web route handler that reads cfg credentials MUST call `apply_overrides(cfg)` at entry; the cfg-cascade is invisible otherwise. Bank as project-wide invariant: consider moving `apply_overrides` into `load_config` itself OR into the FastAPI lifespan hook so it's not per-handler concern.

7. **`parse_qs` vs `unquote` for OAuth code parsing** — `parse_qs` applies `application/x-www-form-urlencoded` semantics (decodes `+` as space). OAuth codes are opaque; use raw query-string split + `urllib.parse.unquote` (NOT `unquote_plus` or `parse_qs`). Discriminating test pattern: callback URL `?code=ABC+DEF%40SESSION` must preserve `ABC+DEF@` exactly.

8. **Atomic file-write fsync discipline** — match `swing/config_user.py:write_user_overrides` pattern: tempfile in same dir → write → `f.flush()` → `os.fsync(f.fileno())` → `os.replace()` → best-effort parent-dir fsync (POSIX) with `contextlib.suppress(OSError, AttributeError, NotImplementedError)`.

9. **Real-SDK compat regression test pattern** — when mirroring an external SDK's private API byte-for-byte, the regression test MUST invoke the real SDK's loader (not reimplement the load logic in test code). For schwabdev's `Tokens`: construct `schwabdev.tokens.Tokens(...)` with fresh `issued_at=now()` so the auto-refresh `at_delta`/`rt_delta` thresholds aren't crossed; defensive `monkeypatch(requests.post, side_effect=AssertionError)` catches future refresh-threshold drift.

10. **Cross-bundle base-layout VM pin discipline** — every new VM extending `base.html.j2` MUST populate `unresolved_material_discrepancies_count` via `count_unresolved_material(conn)` (Phase 10 T-E.3 cross-bundle pin). Discriminating test: plant unresolved discrepancy → request page → assert banner rendered. Bundle T-B.4 review-fix at `0d4cb7b` is the canonical pattern.

11. **HTMX gotcha trinity preserved** for any new form-driven route: (a) `hx-headers='{"HX-Request": "true"}'` propagation; (b) 204 + `HX-Redirect` (NOT 303 swap); (c) HX-Redirect target route exists (TestClient route-table assertion). T-B.4 ships all three with discriminating tests.

12. **Sub-bundle A T-A.3 implementer gap pre-emption discipline** — for any new entry point that threads credentials through multiple call sites, the route-level integration test MUST mock the service function + assert the EXACT cascade-resolved credential values were threaded through (not just that the function was called). T-B.4 `test_post_invokes_service_with_credentials_from_cascade` is the canonical pattern.

---

## §11 CLAUDE.md status-line refresh draft text (for orchestrator paste-in at integration-merge)

```
**Phase 12 Sub-bundle B (Schwab web-UI-friendliness — credentials-in-file + web OAuth paste-back form) SHIPPED 2026-05-15** at `<MERGE_SHA>` (integration merge of `phase12-bundle-B-schwab-web-ui-friendliness` via `--no-ff`; 15 commits = 6 task-impl (T-B.1 cfg-cascade + T-B.2 cfg dataclass+FIELD_REGISTRY + T-B.3 CLI smoke tests + T-B.4 web routes+VM+template+service-helper [×2 commits] + T-B.5 docs + T-B.6 sentinel-leak audit) + 4 Codex-fix (R1+R2+R3+R4) + 3 polish (T-B.1 error hint + T-B.4 docstring drift + T-B.4 review-fix banner+monkeypatch) + 1 dispatch brief + 1 return-report; **4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/5M/3m → R2 0C/1M/2m → R3 0C/1M/1m → R4 0C/0M/1m); **ZERO Critical findings post-resolution**; **ZERO ACCEPT-WITH-RATIONALE banked** (all 1 Critical + 7 Major resolved with code-content fixes); +66 fast tests (3791 → 3857 worktree-side; above projection +18-28; matches A overshoot precedent) + 1 slow real-schwabdev-Tokens compat test; ruff 18 unchanged; schema v18 unchanged consumer-side; **Tier-2 + Tier-3 operational-pain mini-bundle** addressing Sub-bundle A V2 candidates banked at `db55e39` + `b13fcc5` — `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` join the cfg-cascade as middle tier between env vars and prompt (T-B.1 LOCK: partial env-tier RAISES preserved from Sub-bundle A; partial cfg-tier FALLS THROUGH to next tier — file-tier is operator-friendly per phase3e-todo "Cascade design" intent) + new `SchwabIntegrationConfig.client_id` + `.client_secret` cfg dataclass fields with `FIELD_REGISTRY` `masked=True` entries + defensive drop from tracked `swing.config.toml` + `_V1_PATHS` cascade extension (T-B.2) + new `swing config set integrations.schwab.client_id|client_secret` CLI surface via narrow `_MASKED_WRITEABLE_PATHS` frozenset allowlist (T-B.3 Decision B; preserves Sub-bundle A T-A.2 `account_hash` write-protection design intent; N-part dotted-path generalization at `delete_user_override` + new `_write_override_nested` helper; +8 tests) + new web `GET/POST /schwab/setup` route (T-B.4 **Outcome B locked** — manual token exchange because schwabdev's `Client.__init__` blocks on stdin paste-back; new `setup_paste_flow_with_callback_url` service helper mirrors schwabdev's `Tokens._post_oauth_token` HTTP shape + `Tokens._set_tokens` JSON file format byte-for-byte; atomic `os.replace` to unique-tmp sibling in same dir + `f.flush()` + `os.fsync()` + best-effort parent-dir fsync per Codex R2+R3 hardening; HTMX form with `hx-headers='{"HX-Request": "true"}'` + 204 + `HX-Redirect: /config?schwab_setup=ok` on success; 5 distinct error paths surfaced as user-visible templates 400/409/502/500; **web V1 LOCK**: auto-pick singleton account; multi-account raises; **`surface='cli'` at v18 per CHECK constraint** — V2.1 §VII.F amendment banked to widen enum to `('pipeline', 'cli', 'web')` via 0019_*.sql migration; SchwabSetupVM populates `unresolved_material_discrepancies_count` per Phase 10 T-E.3 base-layout pin; +22 + 3 review-fix tests) + sentinel-leak audit extension (T-B.6 mirrors Sub-bundle A precedent verbatim; long ALL-CAPS + 16-char hyphenated bypass sentinels both discriminating; +2 tests) + cycle-checklist + CLAUDE.md gotcha additions (T-B.5; web URL as PRIMARY weekly re-auth path + CLI fallback). **Codex chain convergence**: R1 Critical surfaced `cfg = request.app.state.cfg` and `cfg = ctx.obj["config"]` patterns at Schwab CLI/web entry points (`swing/web/routes/schwab.py:195,243` + `swing/cli_schwab.py:setup/refresh/logout`) bypassed `apply_overrides` — the cfg-cascade would NOT have been consumed end-to-end without R1 fix at `e418d56` (add `apply_overrides` at all 5 entry points + 5 discriminating regression tests). R3 Major surfaced `parse_qs` decodes `+` as space — OAuth code with literal `+` would have been corrupted as `<space>`; resolved by raw-`&`-split + `unquote` (not `unquote_plus`) at `5ee36ba`. **T-B.7 DEFERRED** to follow-up dispatch (Outcome B decision rule; HX-Redirect target retargets from `/config?schwab_setup=ok` to `/schwab/status` when T-B.7 ships). Eliminates PowerShell drop-out for weekly Schwab OAuth re-auth — operator's normal web-UI workflow now covers credentials persistence + OAuth setup + token refresh end-to-end. ZERO new schwabdev call surfaces; ZERO new schema. Brief baseline §0.7 was off by 1 (4 pre-existing failures, not 3 — the 4th at `test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction` pre-exists on `4ed1892`; banked for separate triage). **N-surface operator-witnessed gate PENDING** (S2 cfg-set + S3 cascade resolution + S4 web GET + S5 web POST destructive re-auth + S7+S8+S9 inline). **V2 candidates banked** (return report §7+§10): T-B.7 `/schwab/status` web counterpart + `surface='web'` CHECK enum widening (v18→v19 schema migration) + Option B HTTPS callback handler + per-environment-namespaced credentials + web multi-account picker + token encryption-at-rest via schwabdev `encryption=<key>` + promote `masked_writeable` to `FieldSpec` attribute + `/config?schwab_setup=ok` query-param consumer + schwabdev version pin + extended compat test + T-B.2 stale-comment cleanup. **12 forward-binding lessons** for Sub-bundle C dispatch (return report §10): three-tier cascade asymmetry pattern; Outcome A vs B SDK-wrapping recipe; `surface='X'` CHECK workaround pattern; `_MASKED_WRITEABLE_PATHS` V2-scaling; N-part dotted-path discipline; `apply_overrides` discipline at Schwab entry points (project-wide invariant candidate); `parse_qs` vs `unquote` OAuth code parsing; atomic file-write fsync trinity; real-SDK compat regression test pattern; cross-bundle base-layout VM pin discipline; HTMX gotcha trinity; Sub-bundle A T-A.3 gap pre-emption pattern. Phase 11 + Phase 12 Sub-bundle A 22 cumulative forward-binding lessons remain authoritative. **Sub-bundle C executing-plans dispatch UNBLOCKED** (Phase 12 Sub-bundle A V2 architectural-pivot reconciliation auto-correct candidate; closes the 3 fresh unreconciled discrepancies + future categorical fiction-vs-truth divergences). Worktree teardown: branch `phase12-bundle-B-schwab-web-ui-friendliness` deleted; on-disk husk ACL-locked (Nth pending cleanup-script pass).
```

*(Orchestrator fills in: `<MERGE_SHA>`, exact final fast-test count post-merge, Nth husk count, N-surface gate count.)*

---

## §12 Composition-surface verification via `^def` grep

New helpers introduced + their composition surfaces:

| Helper | Definition | Callers |
|---|---|---|
| `setup_paste_flow_with_callback_url` | `swing/integrations/schwab/auth.py:1485` | `swing/web/routes/schwab.py:setup_paste_flow_post_callsite` (1 callsite) |
| `_finalize_setup_account_linked` | `swing/integrations/schwab/auth.py:1018` | `setup_paste_flow` + `setup_paste_flow_with_callback_url` (2 callsites; refactor target) |
| `_exchange_code_for_tokens` | `swing/integrations/schwab/auth.py:1208` | `setup_paste_flow_with_callback_url` (1 callsite) |
| `_write_schwabdev_tokens_file` | `swing/integrations/schwab/auth.py:1349` | `setup_paste_flow_with_callback_url` (1 callsite) |
| `_safe_cfg_attr` | `swing/integrations/schwab/auth.py:96` | `resolve_credentials_env_or_prompt` (2 callsites for client_id + client_secret) |
| `_write_override_nested` | `swing/cli_config.py:55` | `config_set` (1 callsite) |
| `_fetch_unresolved_material_count` | `swing/web/routes/schwab.py:~30` | GET + POST handlers (2 callsites) |

All callsites threaded through CLI + web entry points per Codex R1 Critical resolution.

---

## §13 Sentinel-leak audit verification

Cfg-cascade-sourced credentials verified absent from:
- caplog records (via `Schwabdev.test_t_b_6_cfg_*` logger emission tests in `tests/integrations/test_schwab_token_redaction_audit.py:test_29 + test_30`)
- Audit `error_message` columns (via `_redact_error_message_for_audit` standalone redactor invocation in both tests)

Discriminating sentinel patterns:
- **Test 29:** long ALL-CAPS `CFG_CASCADE_LONG_CLIENT_ID_SENTINEL_<8hex>` — both Layer-1 heuristic + Layer-0 registry catch
- **Test 30:** 16-17-char hyphenated `cfg-short-id-<4hex>` — BYPASSES Layer-1 regex `[a-fA-F0-9]{32+}` + `[A-Za-z0-9+/=]{24+}`; ONLY Layer-0 registry can scrub (proves `register_schwab_secrets` fires on cfg-tier path)

USERPROFILE+HOME monkeypatch present at fixture entry. `Schwabdev.` capital-S logger names used per CLAUDE.md gotcha.

---

## §14 T-B.4 route-table assertion verification (HX-Redirect target)

Per Phase 6 I3 gotcha (HX-Redirect target must exist):

`tests/web/test_routes/test_schwab_setup_route.py:test_redirect_target_route_exists_in_app_routes` asserts both:
- `/schwab/setup` (POST handler) — registered ✓
- `/config` (HX-Redirect target; until T-B.7 ships `/schwab/status`) — registered ✓

If T-B.7 follow-up dispatch lands `/schwab/status`, the HX-Redirect target retargets + the route-table assertion is updated accordingly.

---

*End of Phase 12 Sub-bundle B executing-plans return report. 4 Codex rounds → NO_NEW_CRITICAL_MAJOR. ZERO ACCEPT-WITH-RATIONALE on Critical+Major. T-B.7 deferred. Sub-bundle C dispatch UNBLOCKED.*
