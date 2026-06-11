# Executing Dispatch Brief — Phase 16 / Arc 7: Watchlist Pin + Hypothesis-Labeling Effectiveness

**Arc:** Phase 16 / **Arc 7**. THIRD + final copowers stage.
**Cycle stage:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`; adversarial Codex review after ALL tasks land, run to convergence).
**Authoritative script (LOCKED, merged):** [`docs/superpowers/plans/2026-06-10-watchlist-pin-labeling-plan.md`](superpowers/plans/2026-06-10-watchlist-pin-labeling-plan.md) — **EXECUTE IT TASK-BY-TASK** (8 tasks; every code block, test, and commit message is in it). Spec: [`docs/superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md`](superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md); governance context: the AMENDED commission. If plan or spec is wrong, STOP and flag.
**Branch-from:** main HEAD at worktree creation (currently `33b9af0b`; re-verify — the operator commits in parallel).
**Schema:** **v27 → v28**, migration `0028` (additive `watchlist` pin columns; `BEGIN;...COMMIT;` + version bump in-file per #9; `_watchlist_pin_backup_gate` STRICT `current_version == 27 AND target_version >= 28`, mirroring `_entry_intent_backup_gate` @db.py:1264). **The #11 sweep targets v28** — note the plan's nuance: `test_migration_0027_entry_intent.py`'s deliberate `target_version=27` ceiling-walks STAY at 27 (apply-ceiling); only its `EXPECTED_SCHEMA_VERSION == 27` line bumps. The migration touches EPHEMERAL test DBs only during execution; the live DB migrates post-merge at the gate (backup-gated).
**No isolated venv needed** — no shared-dependency re-pin.

---

## 1. Mandate (one line)

Execute the 8-task plan: migration 0028 + the #11 sweep; the pin-preserving repo (ON-CONFLICT exclusion, `set_watchlist_pin` rowcount-authority→404); the pure veto + F6 last-value preservation; the `_step_evaluate`/`_step_watchlist` injection + `pin_injection`/`pin_suppressed_removal` audit lines + held/error dedup; the prefill `include_baseline=True` flip + R5 round-trips + the label-match contract; `cohort_hint_for` + three render sites + behavioral containment + the exactly-3 inventory tripwire; the HTMX pin UI; the 0026 §ADDENDUM — TDD, green-per-commit, Codex-converged.

---

## 2. STEP 0 — live re-checks (the plan's flagged verify-on-disk items; non-blocking but MANDATORY before the affected tasks)

1. **Migration number:** `ls swing/data/migrations/*.sql | tail -2` at YOUR branch time — if another lane took `0028`, shift to `0029` and re-target the gate/sweep (the plan documents the rule).
2. **The matcher match-object attribute** (`.hypothesis_name` vs `.name`) returned by `match_candidate_to_hypotheses` — confirm in `hypothesis.py`; adjust `_hint_label` + the contract test accordingly.
3. **EXTEND the existing test harnesses** (`_step_evaluate`/`_step_watchlist`/prefill/dashboard/entry-form routes) — do NOT build parallel ones; the plan's fixture snippets are placeholders to wire into the closest existing module's setup.
4. **Watchlist POST route style** (`def` vs `async def` form-parse, Task 7) — match the file's existing pattern; factor `watchlist_expand`'s body into the shared `_render_expanded_row(request, cfg, ticker)` helper.

---

## 3. Execution disciplines (binding)

- **Task-by-task, TDD, green-per-commit** (failing test → SEE fail → minimal impl → SEE pass → ruff → commit; conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; trailers `[]` each commit; the plan gives each commit message).
- **Task 1 and Task 2 are each #11-atomic** (schema+sweep together; model+repo read/write together).
- **The discriminating assertions are binding:** the pin-survival upsert FAILS under a naive ON-CONFLICT including pin columns; the veto test computes the streak BOTH ways (FAILS under suppression-that-freezes-streaks); the inventory tripwire asserts exactly 3 literal `include_baseline=True` sites and FAILS on a 4th.
- **The amended-commission riders are non-negotiable:** the `pin_injection` audit line on every pin-injecting run; the F6 delisted-pinned edge (error rows NEVER blank `last_*`/`missing_criteria` — the spec's R1-CRITICAL fix); the §ADDENDUM to the merged 0026 spec is Task 8 (a dated block appended verbatim from spec §13 — the Arc-1 §5.3 precedent for editing a merged spec).
- **HTMX to the gotcha rules** (Task 7): embedded form `hx-headers='{"HX-Request": "true"}'`; no `<tr>`-root fragments; `hx-target="this"` where an ancestor sets `hx-target`; TestClient asserts the rendered attributes (the browser-only failure surfaces get the operator gate).
- **R6 locks:** registry rows; matcher two-phase gate + dashboard call-site `include_baseline=False` defaults; `tier.py` + deviation allowlist; shadow engine + temporal log + measurement chain; the 16 historical labels; `mistake_tags`/`process_grade` — ALL untouched. Labels NEVER pin-driven. Pin columns operator-owned across upserts. #27 lanes are warnings, NOT phantom `watchlist_archive` rows. `swing/trades/` untouched.
- **Full fast suite + ruff at the end ON YOUR FINAL HEAD** (actual count; isolate the 3 known xdist flakes `-n0` if they appear).
- **Degraded-harness guard:** on mid-batch tool cancellations → single sequential calls, re-Read before each Edit, verify each commit.

---

## 4. copowers Codex review (after ALL tasks land)

- Adversarial loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED) over the full diff vs plan + spec + the amended commission.
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`); tell Codex not to run git.
- Persist BOTH prompts AND responses every round to gitignored `.copowers-findings.md`. Scrutinize any rebuttal against disk before standing on it.

---

## 5. Return report (then STOP — do NOT merge)

The task commit SHAs + messages; the full fast-suite result ON YOUR FINAL HEAD (actual count); `ruff` clean; the STEP-0 resolutions (migration number, the match-object attribute, the harnesses extended, the route style); confirmation the locks held (R6 + the NOT-touched list + the migration diff scoped to 0028); the Codex verdict (rounds + final line); any deviation with justification. Then STOP — merge is the orchestrator's action after QA.

**Operator gates (post-merge — surface in the return; the orchestrator drives + the operator witnesses):** (1) `swing db-migrate` on the live DB (v27→v28, `_watchlist_pin_backup_gate` backup); (2) the BINDING browser gate per the plan's script: **A** pin a row → a removing nightly → survival + 📌 badge + the `pin_suppressed_removal`/`pin_injection` audit → unpin → next nightly ages off; **B** a watch ticker's entry form renders the server-stamped `Broad-watch baseline (watch); failed: …`; **C** the broad-watch chip identical at all three render sites. (3) The research director QAs the 0026 §ADDENDUM language at their next read.
