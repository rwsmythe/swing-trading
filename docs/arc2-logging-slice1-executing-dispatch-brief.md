# Executing Dispatch Brief — Phase 16 / Arc 2 / SLICE 1: Logging disk-pain + safety core

**Arc:** Phase 16 (Observability & Logging) / **Arc 2** / **SLICE 1 of 2**. THIRD + final copowers stage of this slice.
**Cycle stage:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`; adversarial Codex review after ALL tasks land, run to convergence).
**Authoritative script (LOCKED, merged):** [`docs/superpowers/plans/2026-06-09-logging-slice1-plan.md`](superpowers/plans/2026-06-09-logging-slice1-plan.md) — **EXECUTE IT TASK-BY-TASK** (7 tasks; every code block, test, and commit message is in it). Spec: [`docs/superpowers/specs/2026-06-09-logging-overhaul-design.md`](superpowers/specs/2026-06-09-logging-overhaul-design.md).
**Branch-from:** main HEAD at worktree creation (currently `826a5243`; **re-verify with `git log --oneline -3`** — the operator commits research to main in parallel; only docs since the plan merged, so source anchors should hold — re-confirm at STEP 0).
**Schema:** **NONE — v25 holds.** Zero migrations.
**No isolated venv needed** — touches `swing/logging_config.py`, new `swing/logging_setup.py` + `swing/logs_maintenance.py`, `swing/web/middleware/request_id.py`, `swing/web/app.py`, `swing/cli.py`, `swing/config.py` + tests/conftest; no shared user-site dependency re-pin.

---

## 1. Mandate (one line)

Execute the 7-task Slice-1 plan: the size-based `RotatingFileHandler` seam + the `install_logging` composition root (redaction by construction) + the `[logging]` config core + the test-leak fix + the operator-gated content-preserving `swing logs cleanup` command — TDD, green-per-commit, Codex-converged. The plan is the script; do NOT redesign (if the plan is wrong, STOP and flag).

---

## 2. STEP 0 — re-ground + re-confirm flagged anchors (the plan's STEP-0)

The plan grounded on `88e8a0e1`; only docs since — re-confirm at your HEAD:
- The Arc-1 seam `swing/logging_config.py:configure_logging` (Slice 1 switches `TimedRotatingFileHandler`→`RotatingFileHandler`); `configure_web_logging` @[middleware/request_id.py] (RETAINED shim); `app.py:441`; the Belt-A factory + Belt-B `RedactingFormatter` in [client.py]; `pipeline_run_cmd` in [cli.py].
- **`swing.config._user_home` @[config.py:451]** (the D1 fixture monkeypatches it + `USERPROFILE`/`HOME`) — confirm it's the home used to resolve a relative `logs_dir`.
- The `Config` dataclass + `load()`/`apply_overrides()` cascade where `[logging]`/`LoggingConfig` lands.

---

## 3. Execution disciplines (binding)

- **Task-by-task, TDD, green-per-commit.** Each task: write the failing test → run + SEE it fail → minimal impl → run + SEE it pass → `ruff` → commit (conventional, NO `Co-Authored-By`, NO `--no-verify`, final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]` each commit). The plan gives each task's exact commit message.
- **Task 1 is the load-bearing atomic one:** the `TimedRotatingFileHandler`→`RotatingFileHandler` switch + EVERY pinned test-assertion flip (in `test_logging_config.py`, `test_pipeline_log_redaction.py`, `test_error_handling.py`) land in ONE commit (behavior contract, not class name, is the lock). The single-surface §3.4 enforcement (tag `_swing_surface`, remove+close prior SWING handler, NEVER touch foreign handlers) is built here.
- **The redaction belts stay correct + ADDITIVE:** `install_logging` (NEW `swing/logging_setup.py`) is the ONLY Schwab-aware site — it injects Belt A (factory) + Belt B (`RedactingFormatter`); `configure_logging` imports nothing from `swing.integrations.schwab`. web.log is NEWLY redaction-covered (Task 3/4) — strictly additive, never narrowing Arc-1's pipeline.log coverage; no unredacted window (formatter before add-to-root).
- **`configure_web_logging` is RETAINED** (Arc-1 lock) — back-compat shim with the optional `cfg=None`; app.py migrates to `install_logging(cfg, surface="web")`. `pipeline_run_cmd` routes through `install_logging(cfg, surface="pipeline")` preserving Arc-1's two-belt behavior.
- **The `swing logs cleanup` command (Task 6) is OPERATOR-GATED — BUILD + UNIT-TEST it (against tmp dirs), do NOT run it on the operator's real `~/swing-data/logs`.** Running it to reclaim the real 225MB is a SEPARATE operator action post-merge (see §6). Honor: known-swing-surfaces-only selection, verify-`.gz`-before-unlink (streamed SHA-256), `os.replace` temp in `logs_dir`, ASCII stdout (cp1252 gotcha + a PowerShell-stdout test), fail-closed pipeline-running refusal, single-instance lock, never auto-runs.
- **WATCH-ITEMS (carried from the writing-plans return):**
  1. **Single-surface enforcement is a behavior change vs Arc 1** (a new-surface install removes+closes prior swing handlers) — forward-safe + spec §3.4, but **watch the Task-7 full suite for any latent test coupling on multiple root handlers**.
  2. **The D1 home-redirect fixture is suite-wide** — Task 5 Step 5 runs a broad slice to catch blast radius before the full suite; confirm absolute-path `_minimal_config` tests are unaffected + production wiring not masked.
  3. **`test_cleanup_fail_closed_on_db_unavailable`** carries an executor note — use the directory-at-`db_path` variant if `unlink()` gets silently recreated; confirm during execution.
  4. **Web honors `[logging]` from the `cfg` `create_app` was given** (process-start read, spec §3.1); the user-config logging overlay flows through the pipeline via `apply_overrides`.
- **Degraded-harness guard** ([[feedback_degraded_harness_sequential_tool_calls]]): on mid-batch tool cancellations, drop to single sequential tool calls + re-Read before each Edit + verify each commit.

---

## 4. copowers Codex review (after ALL 7 tasks land)

- **Run the adversarial Codex loop to convergence** (`NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED). Review the FULL diff of all task commits against the plan + spec.
- **Codex transport (WSL CLI; the MCP `codex` tool is DEAD in the VS Code extension):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`) + tell Codex not to run git.
- **Persist BOTH prompts AND responses** of every round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md`.
- If Codex surfaces a real crit/major, fix it (new TDD commit), re-run the suite, re-review. Scrutinize any REBUTTAL of a Codex finding against disk before standing on it.

---

## 5. Locks / invariants (do not regress — full list in plan §"Locks" + spec §8)

Schema NONE (v25); `configure_logging` stays the low-level Schwab-AGNOSTIC seam (belts injected via `install_logging`); `configure_web_logging` RETAINED (external signature preserved); `pipeline.log` + the two-belt pipeline redaction + `pipeline_step_timings` all stay working; redaction strictly ADDITIVE (sentinel-leak audit extended to web.log, never narrowed; no unredacted window); single-surface enforcement only removes SWING-tagged handlers (foreign handlers untouched); the cleanup is operator-gated + content-preserving (verify-before-unlink, never auto-runs, writes nothing outside `logs_dir`, honors the `os.replace` same-fs + cp1252 gotchas); `swing/trades/` + `swing/data/` read-only; DB-outside-Drive.

---

## 6. Return report (then STOP — do NOT merge)

Return to the orchestrator: the 7 task commit SHAs + messages; the **full fast-suite result run ON YOUR FINAL HEAD** (`python -m pytest -m "not slow" -q` — ACTUAL pass count, baseline ≈7408+ pre-this-slice; **the pre-existing `tests/research/minervini_primary_base_recall/test_study_doc.py` em-dash `UnicodeEncodeError` is the OPERATOR's research-doc, NOT this arc — call it out as pre-existing, do NOT chase it**; isolate the 3 known xdist co-residency flakes with `-n0` if they appear); `ruff check swing/` clean; confirmation the **test-leak fix actually stops writes to the real `~/swing-data/logs`** (the guard test); which WATCH-ITEM paths you took; the Codex convergence verdict (round count + final `NO_NEW_CRITICAL_MAJOR` line); any plan deviation with justification. Then STOP — do NOT merge/push.

**Operator follow-ups to surface to the orchestrator (post-merge, operator-gated):**
1. **(optional) Production-path gate** — restart `swing web`; confirm the live `web.log` now rotates by SIZE (`RotatingFileHandler`, ≤ ~10MB×6) and is REDACTION-covered (no token/accountHash). Lower-stakes than Arc 1 (no schema/broker), but it's the only path that exercises the real long-running web process's rotation.
2. **(the disk-pain payoff) Run `swing logs cleanup`** on the real `~/swing-data/logs` to reclaim the ~225MB (the 83+97MB legacy dated `web.log.*` → content-preserving `.gz`) — operator-gated, explicit confirm. This is THE reason Slice 1 shipped first; surface it as the recommended post-merge operator action.
