# B-7 Operator Failure-Mode Classification -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the B-7 executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed, Codex-converged implementation plan -- add a capture-only `failure_mode` field to the CR.1 post-trade review surface -- via `copowers:executing-plans` (wraps `subagent-driven-development`). TDD task-by-task (failing test -> minimal impl -> see pass -> commit), strictly Slice A then Slice B. This is the SECOND commissioned **Phase 15** arc. It carries the **first v24 migration** since the schwabdev arc. NO Schwab/L2-lock surface, NO live cutover, NO isolated venv -- but it DOES add a swing-DB migration, so see §1 (the live-DB discipline).

**Plan (AUTHORITATIVE -- the task contract):** `docs/superpowers/plans/2026-06-03-b7-operator-failure-mode-plan.md` (1601 lines; 8 tasks [A1 + B1-B7] across 2 slices; merged to main `855d187a`; single WSL Codex chain CONVERGED R4 `NO_NEW_CRITICAL_MAJOR`). Execute its tasks verbatim; **re-grep every cited file:line at task start** (the plan cites the dispatch HEAD; line numbers shift -- discipline #2).

**Spec (design rationale):** `docs/superpowers/specs/2026-06-03-b7-operator-failure-mode-design.md` (619 lines) -- consult for the WHY (esp. §4 the three-era read + both write paths, §6 the orthogonality contract).

**Brief:** `docs/b7-operator-failure-mode-executing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; the schwabdev-v3 arc CLOSED; B-7 brainstorm + writing-plans SHIPPED+merged (`0e8018f2`/`855d187a`); main HEAD at this dispatch: see §9 (branch from it). ~7053 fast tests green on main (the BASELINE to preserve, +/- B-7's own test deltas). The operator's live DB is at v23.

**Cumulative discipline:** the CLAUDE.md **Gotchas** block is BINDING (esp. **SQLite/migrations/schema** + **Web/HTMX/forms** + the Windows **ASCII #16/#32** for the CLI `--failure-mode`); ~700+ cumulative ZERO Co-Authored-By; **Schema v23 -> v24**.

**Expected duration:** multi-session possible (~13 commits + a Codex chain). One executing-plans cycle, single Codex chain at end.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief + the plan.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP `codex`/`codex-reply` PERMANENTLY DEAD -- do NOT attempt them).** VERIFIED-WORKING (USE EXACTLY):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  The PATH prefix is REQUIRED (a bare `command -v codex` resolves to the DEAD Windows shim `/mnt/c/Users/rwsmy/AppData/Roaming/npm/codex`). PROVE liveness with `codex --version` -> `codex-cli 0.135.0`. R1: `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < <prompt>`; R2+: `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -`. Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. **PERSIST each round's PROMPT AND RESPONSE (incl. `### Verdict`) to `.copowers-findings.md`**.

---

## §1 The live-DB discipline (BINDING -- the B-7 analog of "don't mutate the operator's live state")
B-7 adds migration `0024`. The migration runs AUTOMATICALLY on `run_migrations` the first time any process connects to a v23 DB. The operator's LIVE DB is `~/swing-data/swing.db` (the hard-invariant path). **Therefore:**
- **pytest is SAFE** -- the test harness builds fresh temp DBs (`run_migrations(target_version=...)` on tmp paths); run the suite freely.
- **Do NOT run `python -m swing.cli web` / any `swing` CLI command that CONNECTS against the DEFAULT db_path from the branch** -- it would migrate the operator's live v23 DB to v24 BEFORE merge (backup-gated, but a live mutation the operator has not consented to yet). If you need to MANUALLY exercise the web review form, point the app at a TEMP/COPY DB (a config override / a throwaway db_path with a seeded closed-unreviewed trade) -- NEVER the operator's `~/swing-data/swing.db`.
- **The operator's live-DB migration is a POST-MERGE step** (their conscious first `swing` run after merge; `_b7_backup_gate` snapshots it automatically). See §3.
- Do NOT delete or rewrite the operator's live DB; do NOT run the migration against it. If a task seems to require the live DB, STOP + escalate.

---

## §2 LOCKed OQ resolutions + L1-L6 (BINDING; full detail in the plan §2 / the writing-plans brief §1)
- **OQ-1** new nullable `failure_mode` CHECK column -> migration 0024 / v24 (strict `_b7_backup_gate` `current==23 AND target>=24`; `EXPECTED_SCHEMA_VERSION` 24; gotcha-#11 atomic). **OQ-2/7** always-shown, OPTIONAL, nullable, NO sentinel. **OQ-3** single-select. **OQ-4** the 7-value vocab (`thesis_invalidated`, `normal_volatility_stop`, `market_regime_shift`, `adverse_event_shock`, `execution_error`, `failed_to_advance`, `other`; NULL = no attribution). **OQ-5** capture-only (NO analysis surface). **OQ-6** forward-only. **OQ-8** CLI `--failure-mode` IN V1.
- **L1** capture-only. **L2** ORTHOGONAL -- `failure_mode` not a `compute_process_grade` param, not in `MISTAKE_TAGS`, excluded from the mistake-tag frequency metric (Task B7 guard proves COMPUTATIONAL separation, NOT zero correlation). **L3** carve-out (`swing/trades/review.py` + `swing/data/` + `swing/cli.py` + web). **L4** the #11 atomic schema task (Slice A, ONE commit). **L5** `... or None` for the nullable CHECK column. **L6** every review-form gotcha (hx-headers HX-Request; 204+HX-Redirect [assert `HX-Redirect == /reviews/pending`]; 400+re-render); the binding operator BROWSER gate incl. the UNSEEDED-blank witness.

---

## §3 The operator browser gate + the live-DB cutover (§3 of the writing-plans flow)
1. **Implementer (pre-return):** all TDD via temp DBs. OPTIONALLY validate the render/persist path manually against a TEMP/COPY DB (NOT the live DB, §1). DOCUMENT the exact gate steps for the operator.
2. **Return + orchestrator QA + MERGE.** You return when: all 8 tasks done; the fast suite GREEN (cite the count; run via pytest on temp DBs); the Codex chain CONVERGED (`.copowers-findings.md`); the browser-gate runbook documented. The orchestrator QAs + merges. **You do NOT merge.**
3. **Operator browser gate (POST-MERGE; BINDING -- L6).** After merge, the operator runs `swing web` against their LIVE DB (which migrates v23 -> v24 on first connect; `_b7_backup_gate` snapshots `swing-pre-b7-migration-<ISO>.db` first). Then: open a real closed-unreviewed trade's `/trades/{id}/review`; (a) ATTRIBUTED -- select a failure mode, submit -> browser navigates to `/reviews/pending` (HX-Redirect, not a swap); the DB shows the token; the chronology shows the label; (b) UNSEEDED-blank (memory `feedback_seeded_gate_masks_default_state`) -- leave the control blank, submit -> `NULL` persists AND the chronology shows NO failure-mode line. If the gate fails, rollback = revert the merge (the nullable column is harmless even if left on the live DB; the backup exists). The operator does NOT need a re-auth or any external step -- this is far lower-stakes than the schwabdev cutover.

---

## §4 Slice execution order (STRICT A -> B; plan Slice A / Slice B)
- **Slice A -- the #11 ATOMIC task (A1; ONE commit, ~12 TDD steps).** Migration 0024 (the 7-token CHECK) + `_b7_backup_gate` + `EXPECTED_SCHEMA_VERSION` 24 + `FAILURE_MODES` (in `swing/data/models.py` -- the import-cycle fix) + `Trade.failure_mode` + `__post_init__` validator + the THREE-ERA `_trade_select_cols`/`_row_to_trade` (v24 / v21-v23 [PRESERVE real `candidate_id`/`pattern_evaluation_id` backlinks] / pre-v21) + the PRAGMA-aware `update_trade_review_fields` (None=no-op on pre-v24; non-None-on-pre-v24 raises a clean `ValueError`) + `complete_trade_review` keyword-only param. `insert_trade_with_event` needs NO column change (failure_mode always NULL at entry; guard test only). The legacy `run_migrations(target_version=16)` review fixtures (`tests/trades/test_review.py:31-36`) MUST stay green. **This is ONE commit (gotcha #11) -- do not split it.**
- **Slice B -- the capture surfaces (B1-B7; ~6 commits + a sanity sweep).** The review-form fieldset (after Mistake-tags, before Counterfactual) using the ORDERED `FAILURE_MODE_DISPLAY` (never iterate the unordered frozenset) + `ReviewVM.failure_mode_choices` (safe default; verify no base-layout deref) + the POST validate/thread (`... or None`; invalid -> 400 + re-render; success asserts `204` + `HX-Redirect == /reviews/pending`) + the PRAGMA-aware `_review_entry` chronology read-back + the CLI `--failure-mode` option (validate against `FAILURE_MODES`; wrap `ValueError` as `click.ClickException`; ASCII help/echo) + the B7 orthogonality guard test. Gated by §3 (the post-merge operator browser gate).

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. Slice A landed as ONE commit (#11); no partial schema/model mismatch; `EXPECTED_SCHEMA_VERSION == 24`; the strict backup-gate fires on `current==23` only; run-migrate-twice no-op.
2. The three-era read preserves real v21-v23 backlinks (the naive-two-era trap is a discriminating test); pre-v21 + v21-v23 + v24 all covered.
3. The PRAGMA-aware `update_trade_review_fields` keeps the legacy pre-v24 review fixtures green; non-None-on-pre-v24 raises a clean `ValueError` (not a leaked `OperationalError`).
4. Orthogonality (L2): the guard proves COMPUTATIONAL separation (grade has no `failure_mode` param; failure_mode absent from MISTAKE_TAGS + the frequency metric), NOT zero correlation.
5. Form: `... or None` (empty -> NULL test); 400+re-render on invalid; the success path asserts the `HX-Redirect`; the audit envelope untouched; the browser gate incl. the unseeded-blank witness is documented for the operator.
6. CLI: invalid token -> clean `click.ClickException` (exit 1 + exact message); ASCII; the service `ValueError` wrapped at the CLI boundary.
7. The live-DB discipline (§1) was honored -- no `swing` command migrated the operator's live DB. ASCII (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]`).

---

## §6 TDD + commit discipline
- Per task: failing test FIRST (with the pre-fix-vs-post-fix value check so it actually distinguishes -- memory `feedback_regression_test_arithmetic`); see it fail; minimal impl; see it pass; commit. Slice A is the exception -- ONE commit after all its TDD steps (gotcha #11). Conventional messages (`feat(trades):`/`feat(web):`/`feat(data):`/`test(...)`).
- NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph PLAIN PROSE; verify `git log -1 --format='%(trailers)'` is `[]` before any push.
- Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit.
- If mid-batch tool cancellations recur, switch to single sequential tool calls + re-Read before each Edit (memory `feedback_degraded_harness_sequential_tool_calls`).

---

## §7 If you get stuck
- Plan file:line no longer matches the tree -> TRUST the tree + re-grep.
- The three-era read seems reducible to two -> it is NOT (v24 / v21-v23 / pre-v21; v21-v23 preserves real backlinks).
- `failure_mode` seems to want to feed the grade or the mistake-tags -> STOP (violates L2).
- A task seems to require the operator's LIVE DB -> STOP + escalate (§1; use a temp DB).
- HOLD THE LINE: Slice A is ONE atomic commit; both write paths + the read-back are PRAGMA-aware; capture-only; the operator browser gate is the post-merge binding gate.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix form (verify `codex --version`).
- DO NOT merge (orchestrator) and DO NOT run the migration against the operator's live DB (operator's post-merge step).

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `b7-operator-failure-mode-executing`. Dir `.worktrees/b7-operator-failure-mode-executing/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of `855d187a`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief + the merged plan). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). NO isolated venv needed (B-7 changes no shared dependency). BUT see §1 -- do NOT run a connecting `swing` command against the operator's live DB.
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §9 Return report shape
Mirror the prior executing-plans return reports: final HEAD + per-slice commit breakdown (Slice A = ONE commit); the fast-suite result (count; cite it; note any baseline delta from B-7's own tests); the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); per-task completion; the OQ resolutions reflected (all 8); L1-L6 verification; Codex Majors accepted (ZERO preferred); the operator browser-gate runbook (documented for the operator; the live-DB migrates v23->v24 post-merge, backup-gated); schema verdict (v23 -> v24; the #11 atomic task; the strict backup-gate; the three-era read); the §1 live-DB discipline confirmation (no `swing` command migrated the live DB); ZERO Co-Authored-By confirmation; worktree teardown status; merge-readiness.

---

*End of brief. B-7 operator failure-mode classification executing-plans dispatch (the SECOND Phase-15 arc) -- execute the merged Codex-converged plan task-by-task: Slice A the #11 atomic schema task (the 7-token CHECK column -> the first v24 migration + the three-era read + the PRAGMA-aware write path + the strict backup-gate, ONE commit), Slice B the capture surfaces (the review-form control + the chronology read-back + the CLI --failure-mode parity + the orthogonality guard). Kept ORTHOGONAL to process-grade and mistake-tags. All TDD on temp DBs -- do NOT migrate the operator's live DB (that is their post-merge step). The binding gate is the operator-witnessed POST-MERGE browser submit (incl. the unseeded-blank witness) on the live DB, which migrates v23->v24 on first connect (auto-backup-gated). OUTPUT: the merged-ready capture feature, suite-green + Codex-converged.*
