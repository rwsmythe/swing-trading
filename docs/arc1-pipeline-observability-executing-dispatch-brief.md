# Executing Dispatch Brief — Phase 16 / Arc 1: Pipeline-Run Observability

**Arc:** Phase 16 (Observability & Logging) / **Arc 1** — pipeline-run observability. THIRD + final copowers stage.
**Cycle stage:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`; adversarial Codex review after ALL tasks land, run to convergence).
**Authoritative script (LOCKED, merged):** [`docs/superpowers/plans/2026-06-08-pipeline-observability-plan.md`](superpowers/plans/2026-06-08-pipeline-observability-plan.md) — **EXECUTE IT TASK-BY-TASK.** The plan has every code block, test, and commit message. Spec (with the ratified §5.3 amendment): [`docs/superpowers/specs/2026-06-08-pipeline-observability-design.md`](superpowers/specs/2026-06-08-pipeline-observability-design.md).
**Branch-from:** main HEAD at worktree creation (currently `e32e374a`; **re-verify with `git log --oneline -3`** — the operator commits research to main in parallel; only docs have landed since the plan merged, so SOURCE line numbers should hold — verify, don't assume).
**Schema:** **v24 → v25** (migration `0025` lands in Task 3). This is the one schema-touching Phase-16 item. `0025` carries explicit `BEGIN; ... COMMIT;` + `UPDATE schema_version SET version = 25;` (gotcha #9 / the `0023`-`0024` convention; per the ratified spec §5.3 amendment — `_apply_migration` runs `executescript` in autocommit and supplies only the FK toggle + `rollback()`).
**No isolated venv needed** — this arc touches `swing/logging_config.py` (new), `swing/cli.py`, `swing/web/middleware/request_id.py`, `swing/integrations/schwab/client.py`, `swing/pipeline/{lease,runner}.py`, `swing/data/{db.py, migrations/0025, repos/pipeline_step_timings.py}` + tests; it does NOT re-pin any shared user-site dependency (the isolated-venv discipline applies only to schwabdev-class shared re-pins). The migration only affects EPHEMERAL test DBs during execution; the operator's LIVE DB migrates post-merge on first run (the `_phase16_backup_gate` snapshots it before crossing v25).

---

## 1. Mandate (one line)

Execute the 7-task plan: the `configure_logging` seam + `RedactingFormatter` two-belt redaction on `pipeline.log` (1a), and the `Lease` monotonic step-timing ledger + single flush-at-finalize + migration `0025` `pipeline_step_timings` + repo + per-step/aggregate log lines (1b) — so the next slow run is per-step attributable. Ship it TDD, green-per-commit, Codex-converged.

The plan is the script. Do not redesign. If you believe the plan or spec is wrong, STOP and flag it (as the writing-plans phase did with the §5.3 migration error — that one is already ratified + fixed); do not silently deviate.

---

## 2. STEP 0 — re-ground + re-confirm the flagged helper names (the plan's STEP-0 list)

The plan grounded anchors on `00d94b2b`; only doc commits landed since, so they should hold — re-confirm at your HEAD before pinning. The orchestrator already disk-verified the load-bearing facts (you can trust these, re-confirm anyway):
- 14 `lease.step()` calls / 13 names: `finviz_fetch`@**634** (inbox-empty branch) + @**758** (unconditional), `weather`@**723** between them, … `complete`@**1013**. `lease.step()`@[lease.py:53-62], `Lease` plain `@dataclass`@[lease.py:36], `_now_iso()`@28-29.
- `run_pipeline_internal` def @[runner.py:531], teardown `finally` @[runner.py:1034] (`hb.stop()`+`audit_conn.close()`); `acquire_lease` outer-try @560-572 (early-return @572 BEFORE the big try @586) → **`lease` always bound at L1034** (orchestrator-verified).
- `pipeline_run_cmd` @[cli.py:3213]; wiring point between `cfg = apply_overrides(...)` (~L3220) and `result = run_pipeline(...)` (~L3221). `sys.stdout/stderr` utf-8 reconfigure @[cli.py:22-23].
- `_apply_migration`@[db.py:252-295] (`executescript` autocommit + `commit`/`rollback`, FK OFF — NO in-runner BEGIN), `_b7_backup_gate`@~1023-1066, `run_migrations`@~1126, `connect`@[db.py:1194]. **Latest migration is `0024` → `0025` is next.**

**Re-confirm these flagged helper names/signatures at your HEAD before relying on them** (the plan pinned them but flagged them for execution-time re-confirm):
- `tests.cli.test_cli_eval._minimal_config(project, home)` (the canonical config helper).
- `force_clear(conn, *, run_id, error_message)` @[`swing/data/repos/pipeline.py:137`] — sets `state='force_cleared'`, no `lease_token`, does NOT self-commit (wrap in `with conn:`).
- `acquire_lease(db_path=, trigger=, data_asof_date=, action_session_date=, block_threshold_seconds=)`.
- The in-`pipeline_run_cmd` patch targets are the **import sources**: `swing.config_overrides.apply_overrides` + `swing.pipeline.run_pipeline` (NOT `swing.cli` attributes) — confirm both are imported inside the function body.
- `swing.prices.PriceFetcher.get` is the runner's fetcher patch target; confirm `cfg.rs.benchmark_ticker` (the runner-shaped failed-path test branches on it).
- `connect()`/`open_connection()` set **no `row_factory`** → rows are tuples; the repo uses **positional** `row[N]` (matches `swing/data/repos/pipeline.py`). Do NOT use `row["col"]`.

---

## 3. Execution disciplines (binding)

- **Task-by-task, TDD, green-per-commit.** Each task: write the failing test → run + SEE it fail → minimal impl → run + SEE it pass → `ruff` → commit (conventional, NO `Co-Authored-By`, NO `--no-verify`, final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]`). The plan gives each task's exact commit message.
- **Task ordering matters for the schema dep:** Task 3 (migration `0025` + `EXPECTED_SCHEMA_VERSION=25`) MUST land before Tasks 4/5/6 (their `ensure_schema` fixtures migrate to v25 + need the `pipeline_step_timings` table). Follow the plan's order.
- **Task 4 atomicity (#11):** `StepTiming` dataclass + `_row_to_step_timing` mapper + the repo write/read functions land in ONE commit (read-path + write-path together).
- **The redaction two-belt is correctness-critical:** Belt A (`ensure_schwab_log_redaction_factory_installed()`) installed FIRST in `pipeline_run_cmd` before any handler attach/emit; Belt B (`RedactingFormatter` using the NEW non-truncating `_make_full_redactor_from_global` — NOT the existing `[:500]`-truncating `_make_redactor_from_global`, which would shred tracebacks) set on the handler BEFORE it joins root. The plan's Task-2 tests (non-Schwabdev logger, traceback, late-registered secret, long-line) are the binding proof — keep all four discriminating.
- **The corrected timing semantic** (the QA-corrected core): `ordinal` unique monotonic; `step_name` NON-unique (`finviz_fetch` yields two rows on the inbox-empty path); consumers `SUM(duration_ms) GROUP BY step_name`. Task 5's `test_inbox_empty_sequence_ordinals_and_aggregation` drives the REAL `finviz_fetch→weather→finviz_fetch` sequence (NOT a synthetic two-in-a-row) — keep it production-shaped.
- **Flush sequence is load-bearing** (Task 6): close final pending → emit per-step line + aggregate summary BEFORE the fallible DB write → one batch txn on a fresh `connect()` → set `_timings_flushed=True` ONLY after commit. The `finally` wrap NEVER re-raises (cannot mask an in-flight exception) + NEVER blocks finalization. Keep BOTH the lease-level AND the runner-level flush-failure tests (the runner-level one catches a missing `try/except` in the `finally`).
- **WATCH-ITEM (carried from QA, the plan flags it):** the end-to-end empty-inbox persistence assertion (two `finviz_fetch` rows at ordinals 0/2 through the REAL runner auto-fetch branch) is best-effort — IF `tests/pipeline/test_run_pipeline_internal_empty_finviz_inbox_auto_fetch.py` drives the run to completion, extend it to assert `list_step_timings(...)` shows the two finviz rows; otherwise the Task-5 Lease-replay + the Task-6 flush round-trip are the binding production-shaped coverage. Note in the return report which path you took.
- **Degraded-harness guard** ([[feedback_degraded_harness_sequential_tool_calls]]): on mid-batch tool cancellations, drop to single sequential tool calls + re-Read before each Edit + verify each commit; a failed call invalidates read-state and silently breaks later Edits → false-green/contaminated commits.

---

## 4. copowers Codex review (after ALL 7 tasks land)

- **Run the adversarial Codex loop to convergence** (`NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED). Review the FULL diff of all task commits against the plan + spec.
- **Codex transport (WSL CLI; the MCP `codex` tool is DEAD in the VS Code extension):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows (e.g. `git diff main...HEAD > .codex-diff.txt`) + tell Codex not to run git.
- **Persist BOTH prompts AND responses** of every round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md` for independent orchestrator convergence-confirmation at QA.
- If Codex surfaces a real crit/major, fix it (new TDD commit), re-run the suite, re-review. Scrutinize any REBUTTAL of a Codex finding against disk before standing on it.

---

## 5. Locks / invariants (do not regress — full list in plan §"Locks / invariants" + spec §8)

Schema v24 → v25 (the single touch; `0025` BEGIN/COMMIT + version bump per the ratified §5.3); `swing/web/routes/pipeline.py` UNCHANGED (DEVNULL kept — the child is self-contained via its own file handler); `swing/trades/` read-only; `configure_logging` imports nothing from `swing.integrations.schwab` (Schwab-agnostic seam; the CLI injects the formatter); `configure_web_logging` becomes a thin shim with the `app.py:441` call + all existing `web.log` tests preserved; NO new per-step lock-contention point (timing persistence is ONE batch txn at finalize on a fresh `connect()` — respects the `database is locked` deadlock scars + the single-transaction contract); the ledger op is in-memory only + runs AFTER `update_step`; `complete` is a real boundary (do NOT drop it); DB-outside-Drive; `busy_timeout` unchanged.

---

## 6. Return report (then STOP — do NOT merge)

Return to the orchestrator: the task commit SHAs + messages; the **full fast-suite result run ON YOUR FINAL HEAD** (`python -m pytest -m "not slow" -q` — the ACTUAL pass count, baseline ≈7268+ given the new tests; isolate the 3 known xdist co-residency flakes if they appear — `test_ohlcv_reader_re_export_identity`, `test_read_cohort_csv_against_committed_v2trf`, `test_prices_refresh_uses_pipeline_eval_anchor` — pass `-n0`); `ruff check swing/` clean; confirmation that migration `0025` round-trips (v24→v25) through the real runner + the backup gate fires strict-on-v24; which path you took for the §3 WATCH-ITEM; the Codex convergence verdict (round count + the final `NO_NEW_CRITICAL_MAJOR` line); and any deviation from the plan (with justification). Then STOP. Merge is the orchestrator's action after QA. Do NOT merge, do NOT push to main.

**Operator production-path gate (surface to the orchestrator — BINDING per [[feedback_byte_parity_insufficient_for_visual_gate]]):** the plan's Task-2 self-containment test uses an IN-PROCESS `CliRunner` (it deliberately does NOT spawn a real OS subprocess in the fast suite), so it proves the wiring LINES but NOT that the real **web-spawned detached subprocess** (`stdout=DEVNULL`) actually writes `pipeline.log`. The binding production-path verification is an operator-witnessed live run after merge: trigger a pipeline (web `POST /pipeline/run` or `swing pipeline run`), then witness (a) `~/swing-data/logs/pipeline.log` is CREATED + populated with per-step `step ordinal=N name=… took … ms` lines + the `step totals:` summary; (b) NO token/accountHash leaks in it (Belt B); (c) the migration applied (DB at v25) + a `swing-pre-phase16-migration-*.db` backup was taken; (d) `pipeline_step_timings` has the run's rows (`step_durations_by_name`). Recommend the orchestrator hold this as the post-merge gate.
