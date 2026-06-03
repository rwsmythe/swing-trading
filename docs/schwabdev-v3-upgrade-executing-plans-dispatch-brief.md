# schwabdev v2.5.1 -> 3.0.5 Upgrade -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the schwabdev-v3-upgrade executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed, Codex-converged implementation plan -- migrate the project off **schwabdev 2.5.1** to **3.0.5** -- via `copowers:executing-plans` (wraps `subagent-driven-development`). TDD task-by-task (failing test -> minimal impl -> see pass -> commit), strictly in slice order. This is the FIRST commissioned **Phase 15** arc, on the **L2-LOCKED Schwab surface**, and carries the **FIRST-EVER L2-LOCK baseline re-anchor**. It modifies a LIVE brokerage dependency -- the **isolated-venv mandate (§1) is BINDING** so the operator's live Schwab stays intact until a conscious post-merge cutover.

**Plan (AUTHORITATIVE -- the implementation contract):** `docs/superpowers/plans/2026-06-02-schwabdev-v3-upgrade-plan.md` (1835 lines; 20 TDD tasks + 2 operator GATEs across 4 slices; merged to main `333367f`; single WSL Codex chain CONVERGED R3 `NO_NEW_CRITICAL_MAJOR`). Execute its tasks verbatim; **re-grep every cited file:line at task start** (the plan cites the dispatch HEAD; line numbers shift -- discipline #2).

**Spec (design rationale):** `docs/superpowers/specs/2026-06-02-schwabdev-v3-upgrade-design.md` (486 lines) -- consult for the WHY behind a task (esp. §5.4 preflight, §5.5 logout, §7 L2 re-anchor).

**Brief:** `docs/schwabdev-v3-upgrade-executing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; brainstorm SHIPPED+merged `f7e15b9`; writing-plans SHIPPED+merged `333367f`; main HEAD at this dispatch: see §9 (branch from it). ~7038 fast tests green on main (the BASELINE to preserve, +/- the migration's own test deltas).

**Cumulative discipline:** the entire CLAUDE.md **Schwab / schwabdev** gotcha block is the implementation checklist (38+ gotchas BINDING); ~700+ cumulative ZERO Co-Authored-By; **Schema v23 LOCKED (NO migration -- the tokens DB is schwabdev-internal); L2 LOCK is RE-ANCHORED by this arc** (the first-ever baseline move; operator approved the design in principle; the FINAL sign-off is the §3 pre-merge doc gate on the real HEAD).

**Expected duration:** multi-session likely (~20 tasks + a Codex chain). One executing-plans cycle, single Codex chain at end (OQ-7).

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief + the plan.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP `codex`/`codex-reply` PERMANENTLY DEAD in the VS Code extension -- do NOT attempt them).** VERIFIED-WORKING (orchestrator-confirmed 2026-06-02, USE THIS EXACT FORM):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  The PATH prefix is REQUIRED -- a bare `command -v codex` resolves to the DEAD Windows shim `/mnt/c/Users/rwsmy/AppData/Roaming/npm/codex` (`node: not found`). PROVE liveness with `codex --version` -> `codex-cli 0.135.0` BEFORE the chain. R1: `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < <prompt>`; R2+: `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -`. Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. **PERSIST each round's PROMPT AND RESPONSE (incl. the literal `### Verdict`) to `.copowers-findings.md`** (v2.0.3 does this; readable on disk for orchestrator QA).
- Output: the migration code + tests across `swing/` + `tests/`, committed task-by-task on the worktree branch.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end** -- esp. §1 (isolated venv) + §3 (the gate sequencing).
2. **The PLAN** (`...2026-06-02-schwabdev-v3-upgrade-plan.md`) -- the task-by-task contract. §A-§G are the slices; §C.1 (the floored-pin/T1b coupling), §C.4 (the badge blast radius -- 8 call sites + the field across all base-layout VMs), §C.5 (`/schwab/status` preserved), §H.1 (L2 sign-off GATE), §H.2 (live-OAuth smoke G7), §H.3 (cutover) are the load-bearing sections.
3. **The SPEC** (`...design.md`) for design rationale.
4. **CLAUDE.md -- the Schwab / schwabdev gotcha block** (the checklist) + `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (#2 re-grep, #11 atomic-consistency, #15 production-path tests, the shared-`base.html.j2` gotcha).
5. **Memory:** WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + seeded-gate-masks-default-state + degraded-harness-sequential (if mid-batch cancellations recur, switch to single sequential tool calls).

---

## §1 The ISOLATED-VENV mandate (operator-decided 2026-06-02 -- BINDING)
On this machine `schwabdev` is a SHARED user-site install (`~/AppData/Roaming/Python/Python314/site-packages`) and editable `swing` points at the PRIMARY repo. A bare `pip install -e` from the worktree would (a) bump the operator's live `schwabdev` to v3 globally AND (b) repoint `swing` to the worktree -- breaking the operator's primary-repo Schwab (2.x code + v3 lib) for the WHOLE dev window. **FORBIDDEN.** Instead:

- **Create a DEDICATED venv OUTSIDE the worktree tree:** `python -m venv "$HOME/schwab-v3-exec-venv"` (home dir, NOT inside `.worktrees/...` -- so pytest never collects it and git never sees it).
- **Install the WORKTREE editable into that venv ONLY:** `"$HOME/schwab-v3-exec-venv/Scripts/python.exe" -m pip install -e ".[dev,web]"` run from the worktree dir (the venv's `swing` -> the worktree; the venv's `schwabdev` -> v3 per the worktree's re-pinned `pyproject.toml`). This is the isolated analog of the plan's Slice-1 Task-1.1 "install 3.0.5".
- **Run ALL tests + CLI through the venv python:** `"$HOME/schwab-v3-exec-venv/Scripts/python.exe" -m pytest -m "not slow" -q` and `... -m swing.cli ...`. **NEVER bare `python`/`pip`/`swing`** in the worktree (those hit the shared 2.5.1 user-site). Define a shell alias/var for the venv python at the top of your session and use it everywhere.
- **NEVER `pip install` into the shared user env. NEVER run a LIVE Schwab command** (`swing schwab logout`/`setup`/`fetch` against the real account) -- that re-auths the operator's real account on v3 and touches `~/swing-data/schwab-tokens.*.db`. The operator's 2.5.1 env + real token DB stay untouched throughout. Live validation is the operator's POST-MERGE cutover (§3), NOT yours.
- **Tear down the venv at the end** (`rm -rf "$HOME/schwab-v3-exec-venv"`) after the orchestrator QA.
- Confirm isolation at setup: `"$HOME/schwab-v3-exec-venv/Scripts/python.exe" -c "import schwabdev,importlib.metadata as m;print(m.version('schwabdev'))"` -> `3.0.5`, AND a SEPARATE bare `python -c "import importlib.metadata as m;print(m.version('schwabdev'))"` -> still `2.5.1` (proves the shared env is untouched).

---

## §2 Locked OQ resolutions + L1-L7 (BINDING; full detail in the plan §C / the writing-plans brief §1)
- **OQ-1** Fernet IN (Slice 4; key in `user-config.toml`, masked, generated at setup, writer enc-wraps, logout decrypts, preflight checks the `enc:` prefix not the config flag). **OQ-2** U-A force re-setup. **OQ-3** floored pin `>=3.0.5,<4.0.0` -- **T1b DDL-drift guard is the FIRST Slice-2 task; do NOT consider the arc merge-ready until T1b is green** (else fall back to `<3.1.0`). **OQ-4** L2 re-anchor = a designed task + the §3 pre-merge sign-off GATE (the SHA is filled on the REAL pre-merge HEAD; NOT auto-moved). **OQ-5** badge DELETE atomic (the FULL §C.4 blast radius -- 8 call sites + the `schwab_checker_badge` field across EVERY base-layout VM + `base.html.j2` + 6 checker tests + `checker_resilience.py` + the `app.py` install + the CLI liveness block) -- the `/schwab/status` PAGE is PRESERVED (re-sourced via the Slice-2 v3 reader; add NO new widget). **OQ-6** cutover at merge. **OQ-7** single Codex chain.
- **L1** scope = migration only. **L2** RE-ANCHORED (§3 gate; spirit = ZERO new endpoints; the endpoint diff proves it). **L3** NO swing schema (`EXPECTED_SCHEMA_VERSION` stays 23; no `00NN` file; `tests/data/test_no_schema_change_v3.py` enforces it). **L4** every Schwab gotcha re-validated (G1-G6). **L5** v3-grounded (your isolated venv IS 3.0.5 -- cite it). **L6** P14.N7 wrapper + F-1 badge DELETE. **L7** the binding gate is the operator LIVE-OAuth smoke (the §3 cutover; mock tests insufficient for the auth/token path).

---

## §3 The two operator GATES + the cutover sequencing (CRITICAL -- read carefully)
The isolated-venv decision (§1) clarifies WHERE each gate runs:

1. **Isolated-venv development (Slices 1-4 code + ALL mock tests).** Operator's live env fully intact. You execute every task here.
2. **GATE A -- the L2 sign-off (pre-merge DOC gate; plan §H.1 / OQ-4).** AFTER Slice 3 (the churn is final) and Slice 4 Task 4.4: produce `docs/schwab-v3-endpoint-diff.md` (the manual endpoint-set diff proving ZERO new endpoints) + the audited rationale block. **STOP and surface it to the orchestrator/operator.** No live Schwab needed -- it is a doc/test review. ONLY after the operator signs off do you set `L2_LOCK_BASELINE_SHA = <the real pre-merge HEAD>` + commit. If the diff ever shows a genuinely-NEW endpoint, STOP + escalate.
3. **Return + orchestrator QA + MERGE.** You return when: all slices coded; the isolated-venv fast suite is GREEN (cite the count); the Codex chain CONVERGED (`.copowers-findings.md`); the L2 endpoint diff is signed-off + the baseline set; the cutover runbook (below) is documented. The orchestrator QAs + merges to main. **You do NOT merge.**
4. **GATE B -- the live-OAuth smoke (POST-MERGE cutover; plan §H.2 G7 / §H.3 / OQ-6).** This is OPERATOR-DRIVEN, performed AFTER merge, because it bumps the global env to v3 + re-auths the real account + touches `~/swing-data`. **You do NOT perform it.** You DOCUMENT the exact runbook for the orchestrator/operator: `git pull` (main now has v3 code) -> global `pip install -e ".[dev,web]"` (pulls v3 + `cryptography`/`aiohttp`) -> `swing schwab logout` -> `swing schwab setup` (real OAuth; v3 SQLite DB; Fernet-wrapped) -> `swing schwab status` (valid token + days-remaining; no DEGRADED) -> a live `swing schwab fetch` / `swing web` Schwab render -> **witness the UNSEEDED topbar-has-no-badge default** (memory `feedback_seeded_gate_masks_default_state`). If the smoke FAILS, the rollback is: revert the pin to `<3.0.0` -> global `pip install -e` -> `swing schwab logout` -> `setup` (re-creates the 2.x DB). Low blast radius (no swing.db change).

**Net:** you own the code + mock tests + the L2 doc gate (in the isolated venv). The orchestrator owns the merge. The operator owns the live cutover smoke. Do NOT collapse these.

---

## §4 Slice execution order (STRICT 1 -> 2 -> 3 -> 4; plan §A-§G)
- **Slice 1** (plan §D): re-pin (isolated venv) + `account_linked->linked_accounts` + `tokens_file->tokens_db` + signature-pin rename + the `importlib.metadata.version` test + G1-G6 re-validation + the legacy-rename test migration (Task 1.5).
- **Slice 2** (plan §E; the risk core): **T1b DDL-drift guard FIRST** (makes the floored pin merge-safe) -> the W-A v3-SQLite writer + T1 load-back -> the presence-only reader + health re-map (keeps `/schwab/status` fed) -> the COMPREHENSIVE preflight (PRIMARY defense) -> the non-interactive construction guard (defense-in-depth; deterministic `del`+`gc.collect()` lock release) -> the `revoke_and_delete` logout rewrite + delete-without-revoke fallback (C1) -> the legacy-storage test migration (Task 2.8). Tests T1-T9.
- **Slice 3** (plan §F; ONE atomic task): the badge DELETE -- the full §C.4 blast radius in a SINGLE commit; assert zero deleted-symbol references remain in `swing/`, EVERY base-layout route still renders, and `/schwab/status` still renders off the Slice-2 reader (no Jinja `UndefinedError`).
- **Slice 4** (plan §G): Fernet on (key gen at setup + the merge-write that must NOT clobber `client_id`/`client_secret` -- the R2 finding) -> L3 verify -> **GATE A (L2 sign-off)** -> the CLAUDE.md Schwab-block + status-line refresh (retire the plaintext-tokens gotcha, the daemon-checker note, the `.db` setup semantics, the L2 re-anchor record). Document the GATE B cutover runbook.

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. Every plan task landed as specced; the preflight is the PRIMARY defense (not the `call_on_auth` guard alone -- the open-tx hazard); the deterministic lock-release is wired where construction can fire the auth path.
2. The floored pin did not merge ahead of T1b; the badge DELETE is truly atomic (no orphaned field on ANY base-layout VM); `/schwab/status` renders off the v3 reader (production-path test, gotcha #15).
3. Fernet: writer enc-wrap + logout decrypt + preflight `enc:`-prefix check + key masking + key-loss recovery; the setup-time key write does not clobber other user-config keys; status stays presence-only.
4. The L2 baseline was set on the real pre-merge HEAD AFTER the operator sign-off (NOT auto-moved); the endpoint-diff artifact + the grep-still-functions test are present.
5. NO swing schema change (`test_no_schema_change_v3.py` green; zero migration files). Every Schwab gotcha re-validated (G1-G6).
6. ASCII (#16/#32) on new CLI strings + the L2 test module. Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]`).
7. The isolated venv was used throughout (the shared 2.5.1 env was never bumped; no live Schwab command was run).

---

## §6 TDD + commit discipline
- Per task: write the failing test FIRST (with the pre-fix-vs-post-fix value check so it actually distinguishes -- memory `feedback_regression_test_arithmetic`); see it fail (via the VENV python); minimal impl; see it pass; commit. Conventional messages (`feat(schwab):`/`fix(schwab):`/`refactor(...)`/`test(...)`).
- NO `Co-Authored-By`; NO `--no-verify`; the final `-m` paragraph PLAIN PROSE; verify `git log -1 --format='%(trailers)'` is `[]` before any push.
- Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit (the foreground cwd can silently revert to the primary repo on main).
- If mid-batch tool cancellations recur, switch to single sequential tool calls + re-Read before each Edit + verify each commit (memory `feedback_degraded_harness_sequential_tool_calls`).

---

## §7 If you get stuck
- Plan file:line no longer matches the live tree -> TRUST the tree + re-grep; flag material divergence.
- The isolated venv's 3.0.5 surface contradicts the plan/spec -> TRUST the install + ESCALATE.
- The L2 re-anchor seems to hide a genuinely-NEW endpoint -> STOP + escalate.
- The migration appears to need a swing-DB schema change -> ESCALATE (L3; the tokens DB is schwabdev-internal).
- HOLD THE LINE: isolated venv ALWAYS; T1b before the floored pin merges; logout in Slice 2; the badge DELETE is atomic; the live smoke is the OPERATOR's post-merge cutover (you document it, you do NOT run it).
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix form (verify `codex --version`).
- DO NOT merge (orchestrator) and DO NOT run the live-OAuth smoke (operator at cutover).

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `schwabdev-v3-upgrade-executing`. Dir `.worktrees/schwabdev-v3-upgrade-executing/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of `333367f`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief + the merged plan). Use the `superpowers:using-git-worktrees` skill.
- **Isolated venv at `$HOME/schwab-v3-exec-venv`** (§1) -- ALL python/pip/pytest/CLI runs go through it; the shared 2.5.1 user-site is NEVER touched.
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §9 Return report shape
Mirror the prior executing-plans return reports: final HEAD + per-slice commit breakdown; the isolated-venv fast-suite result (count; cite it; note any baseline delta from the migration's own test changes) + the isolation proof (shared env still 2.5.1); the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); per-slice task completion; the OQ resolutions reflected; L1-L7 verification; Codex Majors accepted (ZERO preferred); GATE A status (the endpoint diff prepared + the operator sign-off obtained + the baseline SHA set, OR flagged as pending if not yet signed); the GATE B cutover runbook (documented for the operator; NOT executed); schema verdict (NO swing change); ZERO Co-Authored-By confirmation; the isolated-venv teardown status; merge-readiness (orchestrator merges; operator runs the cutover smoke).

---

*End of brief. schwabdev v2.5.1 -> 3.0.5 upgrade executing-plans dispatch (the FIRST Phase-15 arc) -- execute the merged Codex-converged plan task-by-task across 4 slices, ENTIRELY in an isolated venv so the operator's live Schwab on 2.5.1 stays intact until a conscious post-merge cutover. The token-storage rewrite (JSON->v3 SQLite) + the comprehensive preflight + the logout/revoke fix are the risk core (Slice 2); the badge DELETE is one atomic task with the full 8-call-site/all-VM blast radius (Slice 3); Fernet + the first-ever L2 re-anchor land in Slice 4. Two operator gates: GATE A the pre-merge L2 sign-off (doc review), GATE B the post-merge live-OAuth cutover smoke (operator-driven; you document the runbook, you do NOT run it). NO swing schema change (v23 held). OUTPUT: the merged-ready migration code + tests, isolated-venv-green + Codex-converged.*
