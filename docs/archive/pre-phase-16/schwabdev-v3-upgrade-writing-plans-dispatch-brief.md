# schwabdev v2.5.1 -> 3.0.5 Upgrade -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the schwabdev-v3-upgrade writing-plans implementer. No prior conversation context.

**Mission:** Turn the LOCKed, Codex-converged brainstorm spec into an executing-plans-ready, TDD-task-decomposed implementation plan for migrating the project off **schwabdev 2.5.1** to **3.0.5**. This is the FIRST commissioned **Phase 15** arc (Phase 14 CLOSED 2026-06-02 at schema v23). It is a dependency migration on the **L2-LOCKED Schwab surface** -- NOT a new-feature arc -- and it carries the **FIRST-EVER L2-LOCK baseline re-anchor**.

**Spec (AUTHORITATIVE for implementation):** `docs/superpowers/specs/2026-06-02-schwabdev-v3-upgrade-design.md` (486 lines; merged to main `f7e15b9`; genuine single WSL Codex chain CONVERGED at R5 `NO_NEW_CRITICAL_MAJOR`). The spec's §3 module touch-list, §4 migration strategy, §5 token-storage rewrite + preflight + logout/revoke, §6 Fernet, §7 L2 re-anchor, §9 4-slice decomposition, §10 test strategy + the live-OAuth gate, §13 OQ table are the substrate. **Re-grep every file:line the spec cites (it cites `f1b008d` + installed-3.0.5; line numbers shift) at writing-plans STEP 0 per discipline #2.**

**Brief:** `docs/schwabdev-v3-upgrade-writing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; brainstorm SHIPPED + merged `f7e15b9`; main HEAD at this dispatch: see §8 (branch from it). The investigation findings (`docs/schwabdev-v3-upgrade-investigation-findings.md`, `9d4f6a4`) + the brainstorming dispatch brief (`docs/schwabdev-v3-upgrade-brainstorming-dispatch-brief.md`) are the upstream context.

**Cumulative discipline:** the entire CLAUDE.md **Schwab / schwabdev** gotcha block is the implementation checklist (38+ gotchas BINDING); ~700+ cumulative ZERO Co-Authored-By; **Schema v23 LOCKED (NO migration -- the tokens DB is schwabdev-internal SQLite); L2 LOCK is RE-ANCHORED by this arc** (the first-ever baseline move; operator pre-approved the §7 design in principle, final sign-off at the executing-plans gate -- see §1.1 OQ-4).

**Expected duration:** ~3-5 hours writing-plans + a Codex chain to convergence. Plan line target **~900-1400 lines** (4 slices; Slice 2 is the risk-concentrated core).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief + the spec.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension -- do NOT attempt them).** VERIFIED-WORKING invocation (orchestrator-confirmed 2026-06-02, USE THIS EXACT FORM):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  **The PATH prefix is REQUIRED.** A bare `command -v codex` under `bash -ilc` resolves to the DEAD Windows shim `/mnt/c/Users/rwsmy/AppData/Roaming/npm/codex` (fails `node: not found`) -- the `-ilc` login shell ALONE does NOT pick up node22. The native binary is `/home/rwsmythe/.local/node22/bin/codex`. **PROVE liveness with `codex --version` -> `codex-cli 0.135.0`** (NOT `command -v codex`, which is misleading here) BEFORE the chain. R1: `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < <prompt>`; R2+: `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (`resume` REJECTS `-s`/`-C`). Pre-generate the diff/plan ON WINDOWS; tell Codex NOT to run git (the worktree `.git` points to a Windows path WSL cannot resolve). **PERSIST each round's PROMPT AND RESPONSE (incl. the literal `### Verdict`) to `.copowers-findings.md`** (v2.0.3 does this; the final verdict must be readable on disk for orchestrator QA). Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.
- Output: plan at `docs/superpowers/plans/2026-06-02-schwabdev-v3-upgrade-plan.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end.**
2. **The SPEC** (`...2026-06-02-schwabdev-v3-upgrade-design.md`, 486 lines) -- AUTHORITATIVE. Especially §3 (module touch list, grounded in installed-3.0.5), §4 (migration strategy + the NON-INTERACTIVE construction guard), §5 (§5.1 writer / §5.2 reader / §5.3 P14.N7+F-1 reconciliation / §5.4 comprehensive preflight / §5.5 logout-revoke rewrite), §6 (Fernet), §7 (the L2 re-anchor + the endpoint diff), §9 (the 4 slices), §10 (G1-G6 gotcha re-validation + T1-T9 token tests + G7 live-OAuth gate), §13 (the OQ table).
3. **CLAUDE.md -- the Schwab / schwabdev gotcha block** (the implementation checklist) + `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (esp. #2 anchor re-grep, #11 atomic-consistency, #15 production-path tests, the shared-`base.html.j2` VM-field-default gotcha for the badge DELETION).
4. **The investigation findings** (`9d4f6a4`) §4 (the breaking-change x our-usage matrix) + §6 (the LOC estimate) -- the substrate the spec builds on.
5. **Memory:** the WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + visual-gate (here: live-OAuth smoke) + seeded-gate-masks-default-state entries.

---

## §1 LOCKed OQ dispositions (operator 2026-06-02; BINDING -- DO NOT re-litigate)

### §1.1 The OQ resolutions
| OQ | LOCKed |
|---|---|
| **OQ-1 Fernet** | **INCLUDE in this arc** (Slice 4). Retires the CLAUDE.md "plaintext OAuth at rest (V1)" gotcha. Key in `~/swing-data/user-config.toml` `[integrations.schwab]` `encryption_key`, masked by `swing config show`, gitignored, ACL'd; key-loss recovery = re-setup. The writer `enc:`-wraps (§5.1); logout/revoke DECRYPTS (§5.5); the preflight checks decryptability by the column `enc:` prefix, NOT the config flag (§5.4 (4)); status reads presence-only (no key). |
| **OQ-2 re-setup UX** | **U-A force re-setup** (default; not auto-migrate secret bytes). `status` detects old-format/absent DB -> actionable "run logout then setup" message (§5.4). |
| **OQ-3 pin** | **`>=3.0.5,<4.0.0` -- ONLY WITH the T1b DDL-drift guard test** (§5.1 / §10 T1b). The floored range and the guard are COUPLED: we copy schwabdev's PRIVATE 8-column table DDL (W-A writer), so the guard (introspect the live `schwabdev` table via `PRAGMA table_info` vs our pinned copy; fail loudly on drift) is what makes the range safe. The plan MUST land T1b in the SAME slice as the writer; if T1b is descoped, fall back to the conservative `<3.1.0`. |
| **OQ-4 L2 re-anchor** | **APPROVED IN PRINCIPLE** (the §7 design: bump `L2_LOCK_BASELINE_SHA`, audited rationale block, the manual endpoint-set diff proving ZERO new endpoints, grep-still-functions health test). **The FINAL operator sign-off happens at the EXECUTING-PLANS gate on the REAL post-migration HEAD SHA** -- the plan designs the re-anchor as a discrete task PLUS an explicit operator-sign-off GATE checkpoint; it does NOT silently move the baseline. The escalation rule BINDS: if the re-anchor would ever hide a genuinely-NEW endpoint, STOP + escalate (the endpoint diff proves it does not). |
| **OQ-5 badge** | **DELETE the F-1 topbar checker-liveness badge** + its full blast radius (the VM module, the two `build_schwab_checker_badge(cfg)` call sites, the `schwab_checker_badge` field across ALL base-layout VMs, the `base.html.j2` topbar block, the 6 checker tests, the `app.py` install/seed, the CLI liveness block, `checker_resilience.py`) -- ONE atomic task (gotcha #11 + the shared-`base.html.j2` gotcha). **The `/schwab/status` web PAGE is PRESERVED and is NOT the badge** -- see §1.2. |
| **OQ-6 cutover** | re-setup at merge time, before the first v3 `swing web`/pipeline run (§11). |
| **OQ-7 Codex chains** | SINGLE chain per phase (writing-plans + executing-plans each one chain to convergence). |

### §1.2 The `/schwab/status` PAGE is preserved (operator-clarified 2026-06-02 -- BINDING design note)
The OQ-5 DELETE removes the **topbar badge** (`build_schwab_checker_badge`, the daemon-alive chip), which is a SEPARATE surface from the dedicated **`/schwab/status` web page** (`build_schwab_status_vm`, `swing/web/view_models/schwab.py:365`). Orchestrator-verified against disk:
- The status PAGE renders `vm.state`/`vm.state_reason`/`degraded_banner_active`, `vm.refresh_token_days_remaining`/`severity`/`expires_at`, **`vm.last_success_at`/`vm.last_failure_at`**, `vm.recent_calls`, env, masked DB path -- composed from `_compute_degraded_state` + `_read_tokens_metadata` + `list_recent_calls` (the `schwab_api_calls` audit table). **NONE of it is checker-liveness sidecar data.**
- **Therefore: the plan MUST keep `/schwab/status` fully working post-migration by re-sourcing `_read_tokens_metadata` (JSON->v3 SQLite, §5.2)** -- which the status VM consumes transitively. The `schwab_api_calls`-fed fields (`last_success_at`/`last_failure_at`/`recent_calls`) are UNCHANGED by the migration.
- **No new health surface is needed:** `last_success_at`/`last_failure_at` (did a real Schwab call just work + when) + the refresh-token days-remaining countdown ARE the post-v3 at-a-glance health signals, and they become MORE authoritative under v3's per-request sync refresh than the deleted daemon-alive chip ever was. The badge was the least-informative signal; its deletion loses nothing of value. **Do NOT add a new "last successful call" widget -- it already exists; just keep it fed.**
- A regression test MUST assert `/schwab/status` renders the token-health fields off the v3 reader (production-path, gotcha #15) -- not a stub.

### §1.3 Inherited LOCKs (from the spec §2 / L1-L7; BINDING)
- **L1** scope = the 2.5.1 -> 3.0.5 migration ONLY (re-pin; renames; constructor kwargs; token-storage rewrite; preflight; logout/revoke fix; P14.N7 wrapper REMOVAL + F-1 badge DELETE; signature-pin tests; the L2 re-anchor; the operator re-setup UX; Fernet). NO new Schwab endpoints/features; do NOT re-touch A-3/SB5.5 (shipped) EXCEPT the F-1 badge deletion + the `/schwab/status` re-source.
- **L2** RE-ANCHORED by this arc (the first-ever baseline move; §7; OQ-4 sign-off at the executing gate). The lock's SPIRIT = ZERO new Schwab REST ENDPOINTS; the endpoint diff (§7) is the proof.
- **L3** NO swing-DB schema change (v23 held; `EXPECTED_SCHEMA_VERSION` stays 23; no `00NN` migration). The plan verifies it adds no file under `swing/data/migrations/` and does not touch `EXPECTED_SCHEMA_VERSION`.
- **L4** preserve EVERY Schwab gotcha post-upgrade -- §10 G1-G6 give one re-validation test each (logger redaction, `update_tokens` post-state, sandbox `env=='production'` gate, `price_history` daily discipline, typed-error audit close, source-artifact shape) + the `setup`-clean-DB gotcha (re-validated for `.db` semantics) + the plaintext-tokens gotcha (retired by Fernet).
- **L5** EXACT-3.0.5 grounding -- the spec already verified the installed surface; the plan re-grounds any NEW file:line it introduces against the installed 3.0.5 source (re-use the spec's throwaway venv approach if needed; do NOT alter the project's installed 2.5.1 env until the cutover slice).
- **L6** P14.N7 wrapper REMOVAL + F-1 badge DELETE (§5.3 / §1.1 OQ-5 / §1.2).
- **L7** the binding gate is the operator LIVE-OAuth re-setup smoke (`logout` -> `setup` on v3 -> `status` -> `fetch` -> witness the UNSEEDED topbar-has-no-badge default). Mock tests necessary but INSUFFICIENT for the auth/token path.

---

## §2 Production corrections + anchors (BINDING; re-grep at writing-plans STEP 0 per #2)
The spec embeds these; re-confirm against the live tree (line numbers shift):
- Pin: `pyproject.toml:20` = `schwabdev>=2.4.0,<3.0.0` (re-pin target per OQ-3).
- 4 `tokens_file=` construction sites in `auth.py` (~`:762`/`:897`/`:1680`/`:1860`) + `pipeline_steps.py` + `runner.py` + `cli.py`; `_write_schwabdev_tokens_file:1335`; `_stub_call_account_linked:638/653`; `revoke_and_delete` (the `swing schwab logout` path -- `_json.load` at ~`:2118`, orchestrator-verified REAL); `_rename_stale_tokens_db:299`.
- `trader.py:270` `account_linked()` -> `linked_accounts()`.
- `cli_schwab.py` `_read_tokens_metadata:469`, the status/health JSON-key logic `:611-725`, `_REFRESH_TOKEN_TTL_SECONDS:46`, the checker-liveness block (~`:837-842`).
- L2 test `tests/integration/test_l2_lock_source_grep.py:26` (`L2_LOCK_BASELINE_SHA = "bf7e071"`; pattern `schwabdev.Client.`; Counter-subset).
- Signature pin `tests/integrations/test_schwab_trader_kwarg_signatures.py:37` (`account_linked` -> AttributeError on v3; rename to `linked_accounts`).
- `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`).
- Installed-3.0.5 facts (re-confirm if you re-stand the venv): constructor `Client(app_key, app_secret, callback_url, tokens_db, encryption, timeout, call_on_auth, open_browser_for_auth)`; the 8-col `schwabdev` table DDL; logger `"Schwabdev"` (capital-S); `update_tokens(force_access_token, force_refresh_token) -> bool` retained; `__version__` reads `3.0.4` inside the 3.0.5 dist (assert `importlib.metadata.version("schwabdev")`, NOT `__version__` -- spec Note A).

---

## §3 Slice structure (from the spec §9; the plan decomposes these into TDD tasks)
Decompose into TDD tasks (failing test -> minimal impl -> pass -> commit), one Codex chain at end:
- **Slice 1 -- Re-pin + mechanical renames + signature pins** (low risk, fully test-coverable). `pyproject.toml` (OQ-3 floored range); `account_linked->linked_accounts` (2 sites); `tokens_file->tokens_db` (all construction sites); the signature-pin test rename; the `importlib.metadata.version` test (Note A). NOTE: the floored pin (OQ-3) is only SAFE once Slice 2 lands T1b -- sequence T1b accordingly or land the pin + T1b together.
- **Slice 2 -- Token-storage rewrite (the risk-concentrated core; §5.1 + §5.2 + §5.4 + §5.5).** The v3-SQLite writer (W-A, atomic `os.replace` from a same-dir temp; `_V3_SCHWABDEV_DDL` pinned to installed-3.0.5) + the T1 load-back regression + the T1b DDL-drift guard (NON-INTERACTIVE + deterministic lock release via `del`+`gc.collect()`); the v3-SQLite status reader (presence-only, `mode=ro` URI, locked-DB tolerance) + the health-signal re-map (keeps `/schwab/status` fed, §1.2); the COMPREHENSIVE non-setup preflight `_assert_v3_tokens_db_loadable_or_raise` (table+row+freshness+`enc:`-prefix decryptability) as the PRIMARY defense; the §4 non-interactive construction guard (`call_on_auth=_raise_on_auth` + `open_browser_for_auth=False`) as defense-in-depth; the `revoke_and_delete` logout rewrite + the delete-without-revoke fallback (§5.5/C1 -- logout is step 1 of the live gate, so it MUST land here). Tests T1-T9 (§10).
- **Slice 3 -- P14.N7 + F-1 reconciliation** (§5.3; ONE atomic task; OQ-5 DELETE). Delete the wrapper (`checker_resilience.py`) + the `app.py` install/seed/readback + the CLI liveness block + the badge VM + the two call sites + the `schwab_checker_badge` field across ALL base-layout VMs + the `base.html.j2` topbar block + the 6 checker tests. **The `/schwab/status` page is NOT touched except to confirm it still renders (the re-source is Slice 2's `_read_tokens_metadata` change).** Witness the UNSEEDED no-badge default at the gate.
- **Slice 4 -- Fernet (OQ-1=include) + the L2 re-anchor + the live-OAuth gate + CLAUDE.md refresh.** Fernet wiring (key storage/generation/masking; writer enc-wrap; revoke decrypt; preflight decryptability); the L2 baseline bump + the endpoint-diff artifact + the grep-still-functions health test + the **operator-sign-off GATE checkpoint** (OQ-4); the binding operator LIVE-OAuth re-setup smoke (G7); the CLAUDE.md Schwab-block + status-line refresh (plaintext-tokens gotcha retired, daemon-checker note, `.db` setup semantics, the L2 re-anchor record).

---

## §4 OUT OF SCOPE (do not plan into V1)
- Any NEW Schwab endpoint / feature / market-data source (the lock's spirit holds through the re-anchor).
- A swing-DB schema change / migration (L3; the tokens DB is schwabdev-internal).
- A-3 web market-data wiring / SB5.5 re-work (shipped; leave it) -- EXCEPT the F-1 badge deletion + the `/schwab/status` re-source.
- D5-REWIRE the badge (rejected; OQ-5 = DELETE); a NEW `/schwab/status` widget (§1.2 -- the signals already exist).
- `ClientAsync` adoption; Schwab auth/token cassettes (V2 PLANNED); OS-keyring Fernet-key storage (V2).
- A schwabdev 4.x jump.

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **Slice completeness vs the spec** -- every §3/§5 design item maps to a TDD task; no orphaned 2.x token path; the logout/revoke fix is in Slice 2 (not deferred).
2. **The preflight is the PRIMARY defense, the guard is belt-and-suspenders** -- the plan does NOT rely on `call_on_auth` raising alone (the open-tx hazard, spec §5.4); the deterministic `del`+`gc.collect()` lock-release is planned where construction can fire the auth path (T1b, T9c).
3. **OQ-3 coupling** -- the floored pin task is sequenced WITH the T1b DDL-drift guard (the pin is unsafe without it).
4. **L2 re-anchor rigor (OQ-4)** -- the plan designs the baseline bump + the endpoint-diff artifact + the operator-sign-off GATE; it does NOT auto-move the baseline; the endpoint diff proves zero new endpoints.
5. **Every Schwab gotcha re-validated (L4)** -- G1-G6 tasks present.
6. **Fernet completeness (OQ-1)** -- writer enc-wrap + revoke decrypt + preflight decryptability + key masking + key-loss recovery; status stays presence-only (no key).
7. **`/schwab/status` preserved (§1.2)** -- a production-path regression asserts the page renders token-health off the v3 reader; no new widget added.
8. **L3 no swing schema** -- the plan verifies zero migration files + `EXPECTED_SCHEMA_VERSION` untouched.
9. **Badge DELETE atomicity (gotcha #11 + shared-`base.html.j2`)** -- the field is removed from EVERY base-layout VM in ONE task; no Jinja `UndefinedError` on unrelated routes.
10. **The gate is the live-OAuth smoke (L7)** + the UNSEEDED-default witness (seeded-gate lesson); mock tests declared insufficient for the auth/token path.
11. **ASCII (#16/#32)** -- new CLI status strings + the L2 test module stay ASCII; **Co-Authored-By suppression + trailer-parse hazard** (final `-m` paragraph plain prose; `%(trailers)` `[]`).

---

## §6 Deliverable shape
**Plan at `docs/superpowers/plans/2026-06-02-schwabdev-v3-upgrade-plan.md`** (mirror the prior plan format -- the SB5.5 plan `docs/superpowers/plans/2026-05-31-phase14-sub-bundle-5-5-...-plan.md` is the closest analog): a slice-ordered TDD task list, each task with (a) the failing test (file + assertion + the pre-fix-vs-post-fix value check per memory `feedback_regression_test_arithmetic`), (b) the minimal implementation, (c) the commit message stem, (d) the locks/gotchas it touches. Include the per-slice Codex-convergence expectation, the operator gates (the L2 sign-off GATE in Slice 4; the live-OAuth smoke G7), and a task-count + line estimate. **Target ~900-1400 lines.** Commit stem: `docs(schwabdev-v3-plan): writing-plans <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If a spec file:line no longer matches the live tree, TRUST the live tree + re-grep (the spec cites `f1b008d`; main is now `f7e15b9`+); flag any material divergence.
- If the installed-3.0.5 surface contradicts the spec, TRUST the install + ESCALATE (the spec verified 3.0.5; a re-check should agree).
- If the L2 re-anchor seems to hide a genuinely-NEW endpoint, STOP + escalate -- the spirit (zero new endpoints) is the real lock.
- If the migration appears to need a swing-DB schema change, ESCALATE -- the tokens DB is schwabdev-internal (L3).
- HOLD THE LINE: the preflight is primary; logout/revoke lands in Slice 2; the floored pin needs T1b; the badge DELETE is atomic; the gate is the live-OAuth smoke witnessed at the UNSEEDED default.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix form (verify with `codex --version`; v2.0.3 writes `.copowers-findings.md`).
- This is WRITING-PLANS ONLY -- produce the plan; do NOT write migration code, do NOT enter executing-plans.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `schwabdev-v3-upgrade-writing-plans`. Dir `.worktrees/schwabdev-v3-upgrade-writing-plans/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of the merged brainstorm spec `f7e15b9`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit (the foreground cwd can silently revert to the primary repo on main).
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix form (verify `codex --version` first; transcript -> `.copowers-findings.md`).
- **Expected duration:** ~3-5 hours writing-plans + a Codex chain to convergence.

---

## §9 Return report shape
Mirror the prior writing-plans return reports: final HEAD + commit breakdown; the Codex round chain + convergent verdict (cite `.copowers-findings.md` rounds incl. the final `### Verdict`); plan line count + task count per slice; the OQ resolutions reflected (OQ-1 Fernet in Slice 4; OQ-3 floored pin coupled to T1b; OQ-4 L2 re-anchor as a task + the sign-off GATE; OQ-5 badge DELETE atomic + `/schwab/status` re-source); L1-L7 verification; Codex Majors accepted (ZERO preferred); the operator gates enumerated (the L2 sign-off GATE + the live-OAuth smoke G7); schema verdict (NO swing change); ZERO Co-Authored-By confirmation; worktree teardown status; executing-plans dispatch-readiness + the slice sequencing recommendation.

---

*End of brief. schwabdev v2.5.1 -> 3.0.5 upgrade writing-plans dispatch (the FIRST Phase-15 arc) -- turn the merged, Codex-converged brainstorm spec into a TDD-task-decomposed implementation plan across 4 slices (re-pin+renames; the token-storage rewrite core; the P14.N7+F-1 badge reconciliation; Fernet + the first-ever L2 re-anchor + the live-OAuth gate). All seven OQs are LOCKed (Fernet IN; floored pin + T1b guard; L2 re-anchor approved in principle with the final sign-off at the executing gate; badge DELETE with the /schwab/status page preserved). NO swing schema change (v23 held). The binding gate is the operator LIVE-OAuth re-setup smoke witnessed at the UNSEEDED default. OUTPUT: a plan the executing-plans phase can drive to a shipped migration.*
