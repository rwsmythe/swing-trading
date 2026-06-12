# Executing Dispatch Brief — Phase 16 / Arc 2 / SLICE 2: CLI surface + correlation + overrides

**Arc:** Phase 16 / **Arc 2 Slice 2**. The final implementation phase of the Arc-2 logging overhaul.
**Cycle stage:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`; adversarial Codex after ALL tasks, run to convergence).
**Authoritative script (LOCKED, merged):** [`docs/superpowers/plans/2026-06-11-logging-slice2-plan.md`](superpowers/plans/2026-06-11-logging-slice2-plan.md) — **EXECUTE IT TASK-BY-TASK** (9 tasks). Spec: [`docs/superpowers/specs/2026-06-09-logging-overhaul-design.md`](superpowers/specs/2026-06-09-logging-overhaul-design.md) §5 (+ §3.1/§3.4/§4.5). If plan or spec is wrong, STOP and flag.
**Branch-from:** main HEAD at worktree creation (currently `95867f37`; re-verify — the operator commits in parallel).
**Schema:** **NONE — v28 holds.** `[logging.loggers]` ships EMPTY (Callout B).
**No isolated venv needed.** Suite baseline: **7777**.

---

## 1. Mandate (one line)

Execute the 9-task plan: the `swing/log_correlation.py` carrier (lock-guarded process-globals, strict env validation, reset-at-install, `CorrelationFilter`); the shared-format `defaults=` change across the four enumerated formatter sites; the `install_logging` wiring (`record_filter` + `logger_levels`); the env-only Popen touch + the spawn-time request_id line; `set_pipeline_run_id` at lease acquisition; the E2E subprocess transport proof; `cli.log` with the TWO-LEVEL skip-install routing; the override table + diagnostics; the suite-wide logging-state isolation fixture — TDD, green-per-commit, Codex-converged.

---

## 2. STEP 0 — live re-checks (the plan's flagged items; MANDATORY before the affected tasks)

1. **Re-anchor the runner.py monkeypatch targets** (Task 5): `runner.acquire_lease` / `Heartbeat` / the `set_pipeline_run_id` insertion point — the plan's anchors were verified at `6f9db3c9`; Arcs 6/7/8 shifted lines. The contract: `set_pipeline_run_id(run_id)` immediately after the lease row is inserted, with `Heartbeat()` as the first call after the set, OUTSIDE the post-lease try.
2. **Re-verify the four formatter sites** (`logging_config.py:122`, `logging_setup.py:30`, `request_id.py:56`, the `pipeline_logging` fixture @test_pipeline_log_redaction.py:38) — all four get `defaults=CORRELATION_LOG_DEFAULTS` (the R4 catch: the fixture too, or its records KeyError-drop silently).
3. **The routing invariant** (the R1-major-1 fix, NOT the old rely-on-replacement): `main` group installs `cli.log` only when `ctx.invoked_subcommand != "pipeline"`; the `pipeline_group` callback (new body) installs it only when `ctx.invoked_subcommand != "run"`; `pipeline_run_cmd` stays the sole `pipeline.log` installer. The invariant to test: **a `pipeline run` process emits ONLY pipeline.log — even with a malformed `[logging]` value** (the diagnostics-replay case that killed rely-on-replacement).
4. **The blast-radius fixture** (Task 7/plan §autouse): ~373 `invoke(main)` tests now trigger the group install — the autouse root-logging-state snapshot/restore fixture in `tests/conftest.py` contains it. **Triage discipline: run failures `-n0` deterministically BEFORE `-n auto`** (the plan mandates it; xdist ordering will otherwise mask root causes).

---

## 3. Execution disciplines (binding)

- **Task-by-task, TDD, green-per-commit** (failing test → SEE fail → minimal impl → SEE pass → ruff → commit; conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; trailers `[]` each commit; the plan gives the messages).
- **The binding test shapes** (spec §5.2/§6 + the plan): the E2E subprocess-with-`SWING_WEB_REQUEST_ID=<sentinel>` proof; forged/malformed env → `-`; reset-at-install (no stale run-id bleed); **worker-thread records carry the ids** (the discriminator a contextvars impl would FAIL); no-context records render `-`/`-` with NO KeyError (the tail-marker redaction test is the genuine drop-detector); the cli.log sentinel-leak audit; the malformed-override skip + diagnostic replay; the pipeline-run-emits-only-pipeline.log invariant incl. the malformed-config case.
- **Locks:** the Popen touch is env-ONLY (DEVNULL + `start_new_session` stay); the finviz `_suppress_transport_debug_logs` security belt STAYS; Slice-1/Arc-1 non-regression (pipeline.log + two belts; redaction-by-construction extends to cli.log, never narrows; `logging_setup` stays the sole schwab importer; `configure_web_logging` retained); NO schema; `swing/trades/` + `swing/data/` untouched (the set-call lives in `swing/pipeline/`).
- **Full fast suite + ruff at the end ON YOUR FINAL HEAD** (actual count; the 3 known xdist flakes isolate `-n0` if they appear).
- **Degraded-harness guard:** on mid-batch tool cancellations → single sequential calls, re-Read before each Edit, verify each commit.

---

## 4. copowers Codex review (after ALL tasks land)

- Adversarial loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED) over the full diff vs plan + spec. Ask Codex to probe: the routing invariant under malformed config, the worker-thread correlation path, the formatter `defaults=` completeness (any missed construction site), and the autouse fixture's interaction with the logging tests' own snapshot/restore patterns.
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`); tell Codex not to run git. **Capture Codex output to FILES, not `head`-truncated pipes** (the writing-plans R5 loss). Persist BOTH prompts AND responses every round to gitignored `.copowers-findings.md`. Scrutinize any rebuttal against disk.

---

## 5. Return report (then STOP — do NOT merge)

The task commit SHAs + messages; the full fast-suite result ON YOUR FINAL HEAD (actual count); `ruff` clean; the STEP-0 re-anchor resolutions; confirmation of the locks (env-only Popen, finviz belt, Slice-1 non-regression, NO schema); the Codex verdict (rounds + final line); any deviation with justification. Then STOP — merge is the orchestrator's action after QA.

**Operator-gate note (surface in the return):** the live proof is light — after merge, the orchestrator verifies (1) a normal CLI command writes `cli.log` (redacted, rotated); (2) a web-triggered pipeline run's `pipeline.log` records carry the spawning request's id (the correlation join: web.log ↔ pipeline.log ↔ `pipeline_runs`); (3) `pipeline.log` content is otherwise unchanged. These ride the next nightly + one CLI invocation — no dedicated browser gate (no HTMX surfaces in this slice).
