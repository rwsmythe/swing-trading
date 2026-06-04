# B-7 Operator Failure-Mode Classification -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the B-7 writing-plans implementer. No prior conversation context.

**Mission:** Turn the LOCKed, Codex-converged brainstorm spec into an executing-plans-ready, TDD-task-decomposed implementation plan for **B-7 operator failure-mode classification** -- a capture-only post-trade `failure_mode` field on the CR.1 review surface. This is the SECOND commissioned **Phase 15** arc (the schwabdev v3 + Fernet arc SHIPPED+CLOSED `77d2747e`). Its center of gravity is the **first v24 migration** + the gotcha-#11 atomic-consistency schema task.

**Spec (AUTHORITATIVE for implementation):** `docs/superpowers/specs/2026-06-03-b7-operator-failure-mode-design.md` (619 lines; merged to main `0e8018f2`; single WSL Codex chain CONVERGED R3 `NO_NEW_CRITICAL_MAJOR`). Execute its design verbatim; **re-grep every cited file:line at writing-plans STEP 0** (the spec cites the dispatch HEAD; line numbers shift -- discipline #2).

**Brief:** `docs/b7-operator-failure-mode-writing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; the schwabdev-v3 arc CLOSED; B-7 brainstorm SHIPPED+merged `0e8018f2`; main HEAD at this dispatch: see §8 (branch from it). ~7053 fast tests green on main (the BASELINE to preserve, +/- B-7's own test deltas). The operator's live DB is at v23 (will migrate to v24 at ship).

**Cumulative discipline:** the CLAUDE.md **Gotchas** block is BINDING (esp. the **SQLite/migrations/schema** block for the v24 work + the **Web/HTMX/forms** block for the review form); ~700+ cumulative ZERO Co-Authored-By; **Schema v23 -> v24** (the FIRST migration since the schwabdev arc; re-exercises the backup-gate machinery dormant since v23).

**Expected duration:** ~2-4 hours writing-plans + a Codex chain to convergence. Plan line target **~600-900 lines** (2 slices; Slice A is the #11 atomic schema task).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief + the spec.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP `codex`/`codex-reply` PERMANENTLY DEAD in the VS Code extension -- do NOT attempt them).** VERIFIED-WORKING form (USE EXACTLY):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  The PATH prefix is REQUIRED -- a bare `command -v codex` resolves to the DEAD Windows shim `/mnt/c/Users/rwsmy/AppData/Roaming/npm/codex` (`node: not found`). PROVE liveness with `codex --version` -> `codex-cli 0.135.0` (NOT `command -v codex`). Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. the literal `### Verdict`) to `.copowers-findings.md`. Memory `feedback_wsl_native_codex_invocation` (+ the 2026-06-03 prefix-required correction) + `feedback_implementer_persist_codex_responses`.
- Output: plan at `docs/superpowers/plans/2026-06-03-b7-operator-failure-mode-plan.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end** -- esp. §1 (the LOCKed OQs) + §3 (slices).
2. **The SPEC** (`...2026-06-03-b7-operator-failure-mode-design.md`, 619 lines) -- AUTHORITATIVE. Especially §3.4 (the `FAILURE_MODES` placement in `models.py` -- the import-cycle fix; the ordered `FAILURE_MODE_DISPLAY` tuple), §4 (the v24 migration + the THREE-ERA read + the TWO write paths + the strict backup-gate -- the #11 task), §5 (the form/POST/VM/read-back wiring incl. §5.6 PRAGMA-aware `_review_entry` + §5.7 CLI parity), §6 (the orthogonality contract), §7 (the 8 tests + the browser gate), §9 (the 2 slices).
3. **CLAUDE.md -- the SQLite/migrations gotchas** (#9 explicit BEGIN/COMMIT; #11 CHECK + Python-constant + dataclass-validator + read-mapper in ONE task; the STRICT `pre_version == target-1` backup-gate; `... or None` for nullable CHECK columns; the `Literal[...]` not-runtime-enforced gotcha) **+ the Web/HTMX/forms gotchas** (hx-headers HX-Request; 204+HX-Redirect; 400+re-render; the shared-`base.html.j2` 5-VM rule) **+ the Windows ASCII gotcha #16/#32** (the CLI `--failure-mode` help/echo is a cp1252 stdout path) **+ the service-layer-ValueError-at-CLI-boundary gotcha**. AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines".
4. **Memory:** the WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + seeded-gate-masks-default-state (the unseeded-blank witness in the browser gate) + regression-test-arithmetic entries.

---

## §1 LOCKed OQ resolutions (operator 2026-06-03; BINDING -- DO NOT re-litigate)

| OQ | LOCKed |
|----|--------|
| **OQ-1 schema** | **New nullable CHECK-constrained `failure_mode` column on `trades` -> migration 0024 / v24** (a single ALTER ADD COLUMN, no table rebuild). The strict `_b7_backup_gate` (`current_version == 23 AND target_version >= 24`, mirror `_phase14_sb3_backup_gate`); `EXPECTED_SCHEMA_VERSION` 23 -> 24; gotcha #11 atomic-consistency (spec §4). |
| **OQ-2/OQ-7 solicitation** | **Always-shown, OPTIONAL, nullable; NO sentinel.** `NULL` = winner OR unclassified-loss, disambiguated at analysis time by realized-R (NOT by the column). No required-on-loss gate; no `not_a_loss` token; no R-derivation/TOCTOU dependency (spec §5.2/§5.3). |
| **OQ-3 cardinality** | **Single-select** (one primary failure mode; single column). |
| **OQ-4 vocabulary** | **The 7-value set (LOCKED):** `thesis_invalidated`, `normal_volatility_stop`, `market_regime_shift`, `adverse_event_shock`, `execution_error`, `failed_to_advance`, `other`. `NULL` = no failure attributed (not a token). Display labels per spec §3.4. |
| **OQ-5 analysis surface** | **OUT of V1 -- capture-only.** The failure-mode distribution tile is the NEXT arc (do not build it here). |
| **OQ-6 backfill** | **Forward-only** -- existing reviewed trades stay `NULL`; no backfill prompt. |
| **OQ-8 CLI parity** | **INCLUDE `--failure-mode` in V1** (Slice B) -- closes the permanent CLI-review capture gap (spec §5.7). Validate against `FAILURE_MODES`; wrap the service `ValueError` as `click.ClickException`; ASCII help/echo. |

### §1.1 Inherited LOCKs (from the spec §2 / L1-L6; BINDING)
- **L1** capture-only V1 -- the column + the form control + persistence + the read-back display. NO analysis surface; NO change to grading or the mistake-tags vocab.
- **L2** failure-mode is ORTHOGONAL to process-grade AND mistake_tags (spec §6). It does NOT feed `compute_process_grade` (do NOT add a param), is NOT in `MISTAKE_TAGS`, is excluded from `validate/canonicalize_mistake_tags` + the mistake-tag frequency metric. A test proves the COMPUTATIONAL separation (not zero correlation -- `execution_error` may correlate with execution mistake-tags, and that is fine).
- **L3 (carve-out -- EXPLICIT in the plan)** B-7 writes into the normally-read-only `swing/trades/review.py` + `swing/data/` (the new column, migration 0024, `Trade.failure_mode` + `FAILURE_MODES` + validator in `models.py`, the `_row_to_trade`/`_trade_select_cols` read path, `update_trade_review_fields`, `complete_trade_review`) + `swing/cli.py` (the `--failure-mode` option) + the web layer. Scope it as Phase 6 did.
- **L4** schema = the #11 atomic task (spec §4.3): migration CHECK + `FAILURE_MODES` frozenset + `Trade.__post_init__` validator + the THREE-ERA read mapper + BOTH write paths -- ALL in ONE task (Slice A).
- **L5** nullable + `... or None` (NOT `... or ""`) for the CHECK column; empty submit -> `NULL` (a test asserts it).
- **L6** preserve every review-form gotcha (hx-headers HX-Request; 204+HX-Redirect; 400+re-render; the audit envelope untouched); the binding gate is an operator-witnessed BROWSER submit incl. the UNSEEDED-blank witness (spec §7.2; memory `feedback_seeded_gate_masks_default_state`).

---

## §2 Production anchors (BINDING; re-grep at writing-plans STEP 0 per #2)
The spec embeds these; re-confirm against the live tree (line numbers shift):
- `swing/data/db.py:51` (`EXPECTED_SCHEMA_VERSION = 23`); the latest migration `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql` (the 0024 template shape); the `_phase14_sb3_backup_gate` (~`db.py:909-950`) to mirror for `_b7_backup_gate`; the gate wiring in `run_migrations` (~`db.py:977-1019`).
- `swing/data/models.py` -- the `Trade` dataclass + the Phase-6 review block (~`:214-265`) + the existing CHECK mirrors (~`:9-20`); `FAILURE_MODES` lands HERE (NOT `review.py` -- import cycle).
- `swing/data/repos/trades.py` -- `_TRADE_SELECT_COLS` / `_TRADE_SELECT_COLS_PRE_V21` + `_trade_select_cols()` (~`:57-119`); `insert_trade_with_event` SVAI branch (~`:155-181`); `_row_to_trade` (~`:478-550`); `update_trade_review_fields` (~`:553-595`).
- `swing/trades/review.py` -- `complete_trade_review` (~`:550-618`); `MISTAKE_TAGS` (~`:37-62`); `compute_process_grade` (~`:102-138`, UNCHANGED -- no `failure_mode` param).
- `swing/web/routes/trades.py:2669-2799` (`review_post`); `swing/web/view_models/trades.py:1139` (`ReviewVM`) + `:1224-1370` (`build_review_vm`); `swing/web/templates/partials/review_form.html.j2`; `swing/web/view_models/trade_chronology.py:157-187` (`_review_entry` -- PRAGMA-aware read-back).
- `swing/cli.py:1400-1483` (the per-trade-review command; the `--failure-mode` option; single-review guard ~`:1434-1438`; the `complete_trade_review` call ~`:1460`).
- Existing review tests that run against a pre-v24 schema: `tests/trades/test_review.py` (~`:31-36`, `:118-133`, `run_migrations(target_version=16)`) -- the PRAGMA-aware UPDATE must keep these green.

---

## §3 Slice structure (from the spec §9; the plan decomposes into TDD tasks)
Two slices; Slice B depends on Slice A. TDD per task (failing test with a pre-fix-vs-post-fix value check per `feedback_regression_test_arithmetic` -> minimal impl -> pass -> commit):
- **Slice A -- schema + model + persistence (the #11 ATOMIC task; spec §4).** Migration 0024 (the 7-token CHECK) + `_b7_backup_gate` + `EXPECTED_SCHEMA_VERSION` 24 + `FAILURE_MODES` (in `models.py`) + `Trade.failure_mode` + `__post_init__` validator + the THREE-ERA `_trade_select_cols`/`_row_to_trade` widening (v24 / v21-v23 [preserve real backlinks!] / pre-v21) + the SVAI `insert_trade_with_event` branch + the PRAGMA-aware `update_trade_review_fields` (None=no-op on pre-v24; non-None-on-pre-v24 raises a clean `ValueError`, NOT a leaked `OperationalError`) + `complete_trade_review` keyword-only param. Tests: spec §7.1 #1-3, #7 (incl. the v21-v23 backlink-survival test + the pre-v24 review-UPDATE test).
- **Slice B -- the capture surfaces (spec §5).** The web form fieldset (placed after Mistake-tags, before Counterfactual) + the ordered `FAILURE_MODE_DISPLAY` choices via `failure_mode_display_choices()` (NOT iterating the unordered frozenset) + `ReviewVM.failure_mode_choices` (safe default; verify no base-layout deref) + the POST validate/thread (`... or None`; invalid -> 400 + re-render) + the PRAGMA-aware `_review_entry` chronology read-back + the CLI `--failure-mode` option (validate; `click.ClickException`; ASCII). Tests: spec §7.1 #4-8; gated by §7.2 (the operator browser submit incl. the UNSEEDED-blank witness).

---

## §4 OUT OF SCOPE (do not plan into V1)
- The failure-mode analysis/distribution surface (OQ-5; the next arc).
- Any change to `compute_process_grade`, `MISTAKE_TAGS`, or the disqualifying-violations set (L2).
- Multi-select / a side-table (OQ-3 = single column); a `not_a_loss` sentinel (OQ-2 = NULL); a required-on-loss gate (OQ-7 = optional); a free-text `failure_mode_note` (deferred).
- A backfill of existing reviewed trades (OQ-6 = forward-only).
- Any Schwab / L2-lock surface (B-7 is review-only -- the L2 baseline is untouched).
- A multi-version schema jump (v24 only; STRICT backup-gate).

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **#11 atomicity** -- the migration CHECK + `FAILURE_MODES` + the `Trade` validator + the THREE-ERA read mapper + BOTH write paths are ALL in Slice A's task(s); no partial landing leaves a schema/model mismatch.
2. **The three-era read** -- the v21-v23 projection PRESERVES real `candidate_id`/`pattern_evaluation_id` backlinks (a naive single-PRE projection nulls them); tests cover pre-v21 AND v21-v23.
3. **Both write paths** -- the SVAI insert branch + the PRAGMA-aware `update_trade_review_fields` (the legacy `run_migrations(target_version=16)` review fixtures stay green; non-None-on-pre-v24 raises a clean ValueError).
4. **Read-back PRAGMA-aware** -- `_review_entry` SELECTs `failure_mode` or `NULL AS failure_mode` by PRAGMA; a pre-v24 chronology fixture renders without `no such column`.
5. **Import-cycle + order** -- `FAILURE_MODES` in `models.py`; the form uses the ordered `FAILURE_MODE_DISPLAY`, not the frozenset; a test asserts `{v for v,_ in DISPLAY} == FAILURE_MODES`.
6. **Orthogonality (L2)** -- the test proves computational separation (grade has no `failure_mode` param; failure_mode absent from MISTAKE_TAGS + the frequency metric); NOT an impossible zero-correlation.
7. **Form + nullable-CHECK + ASCII** -- `... or None`; 400+re-render; the browser gate incl. the unseeded-blank witness; CLI text ASCII; the service ValueError wrapped at the CLI boundary.
8. **Strict backup-gate** -- `current_version == 23` STRICT; run-migrate-twice no-op; `EXPECTED_SCHEMA_VERSION == 24`. Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]`).

---

## §6 Deliverable shape
**Plan at `docs/superpowers/plans/2026-06-03-b7-operator-failure-mode-plan.md`** (mirror the prior plan format): a 2-slice TDD task list, each task with (a) the failing test (file + assertion + the pre-fix-vs-post-fix value check), (b) the minimal implementation, (c) the commit message stem, (d) the locks/gotchas it touches. Include the operator browser gate (Slice B), the schema-version assertion, and a task-count + line estimate. **Target ~600-900 lines.** Commit stem: `docs(b7-plan): writing-plans <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If a spec file:line no longer matches the live tree, TRUST the tree + re-grep (the spec cites earlier HEADs; main is now `0e8018f2`+).
- If the three-era read seems reducible to two, STOP -- it is NOT (v24 / v21-v23 / pre-v21 are distinct; the v21-v23 era must preserve real backlinks).
- If `failure_mode` appears to want to feed the grade or join the mistake-tags, STOP -- that violates L2.
- If the migration seems to need a table rebuild, re-check -- a nullable ADD COLUMN does not (contrast SB3's enum-rename rebuild).
- HOLD THE LINE: the #11 atomic task is indivisible; both write paths + the read-back are PRAGMA-aware; capture-only V1; the browser gate (incl. the unseeded-blank witness) is binding.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix form (verify `codex --version`).
- This is WRITING-PLANS ONLY -- produce the plan + per-task tests; do NOT write code, do NOT enter executing-plans.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `b7-operator-failure-mode-writing-plans`. Dir `.worktrees/b7-operator-failure-mode-writing-plans/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of `0e8018f2`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief + the merged spec). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit. NOTE: the env is now schwabdev 3.0.5 (post-cutover) -- B-7 does not touch Schwab, so a plain editable install / the existing env is fine (NO isolated venv needed -- B-7 changes no shared dependency).
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §9 Return report shape
Mirror the prior writing-plans return reports: final HEAD + commit breakdown; the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); plan line + task count per slice; the OQ resolutions reflected (all 8 LOCKed); L1-L6 verification; Codex Majors accepted (ZERO preferred); the operator browser gate enumerated; schema verdict (v23 -> v24; the #11 atomic task; the strict backup-gate); ZERO Co-Authored-By confirmation; worktree teardown status; executing-plans dispatch-readiness + the slice sequencing (A before B).

---

*End of brief. B-7 operator failure-mode classification writing-plans dispatch (the SECOND Phase-15 arc) -- turn the merged, Codex-converged brainstorm spec into a TDD-task-decomposed plan across 2 slices: Slice A the #11 atomic schema task (the 7-token CHECK column -> the first v24 + the THREE-ERA read + BOTH write paths + the strict backup-gate), Slice B the capture surfaces (the review-form control + the PRAGMA-aware chronology read-back + the CLI --failure-mode parity). All 8 OQs LOCKed (new v24 column; the 7-value vocab; always-shown/optional/NULL; single-select; capture-only; forward-only; CLI parity IN). Kept ORTHOGONAL to process-grade and mistake-tags. The binding gate is an operator-witnessed browser submit incl. the unseeded-blank witness. OUTPUT: a plan the executing-plans phase can drive to a shipped feature.*
