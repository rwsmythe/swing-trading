# Writing-Plans Dispatch Brief — Phase 16 / Arc 2 / SLICE 2: CLI surface + correlation + overrides

**Arc:** Phase 16 / **Arc 2** (logging-system overhaul) / **SLICE 2 of 2** — the second of the two slices the Arc-2 brainstorm locked (OQ-1). Slice 1 (disk-pain + safety core) SHIPPED + gated 2026-06-09.
**Cycle stage:** `copowers:writing-plans` (produce an executing-ready plan, Codex-converged). **No brainstorm — the design is already locked** in the merged Arc-2 spec; Slice 2 implements its §5 (+ the §3.1 seam contract + the §4.5 `LoggingConfig` carrier it builds on).
**Source of truth (LOCKED, merged):** [`docs/superpowers/specs/2026-06-09-logging-overhaul-design.md`](superpowers/specs/2026-06-09-logging-overhaul-design.md) **§5** (5.1 `cli.log` centralization · 5.2 run/request correlation · 5.3 the per-logger override table) — READ the whole spec; §5's correlation design is fully converged (the R1-major-5/R2-major-3/R3-minor-2/3 chain: env-var transport, STRICT token validation `^[A-Za-z0-9-]{1,64}$` → fallback `-`, a **thread-safe process-global** carrier [NOT contextvars — worker threads], reset-at-install, per-record `CorrelationFilter`, `Formatter(defaults=)` always-present fields). Do NOT re-litigate; STOP and flag if wrong.
**Branch-from:** main HEAD at worktree creation (currently `ccb93966`; re-verify — the operator commits in parallel).
**Schema:** **NONE — v28 holds.** Config additions only (`[logging.loggers]`, shipped EMPTY per Callout B).
**Deliverable:** an executing-ready plan at `docs/superpowers/plans/2026-06-11-logging-slice2-plan.md` + Codex convergence (`NO_NEW_CRITICAL_MAJOR`) + `.copowers-findings.md` (prompts AND responses). Commit ONLY the plan doc.

---

## 1. Mandate (one line)

Turn spec §5 into an ordered, TDD-structured plan: `cli.log` via `install_logging(cfg, surface="cli")` at CLI entry (redaction + rotation by construction; sentinel audit extended); the correlation chain (`SWING_WEB_REQUEST_ID` env on the web's Popen → the validated process-global → `set_pipeline_run_id(run_id)` at lease acquisition → `CorrelationFilter` stamping every record → `web.log`(request_id) ↔ `pipeline.log`(web_request_id + run_id) ↔ `pipeline_runs`/`pipeline_step_timings`); and `[logging.loggers]` → `resolved_logger_levels()` with malformed-entry diagnostics through the §4.5 warnings carrier.

---

## 2. STEP 0 — re-ground (Slice 1 left landing pads; Arcs 6/7/8 shifted runner.py — verify everything at YOUR HEAD)

- **The seam (post-Slice-1):** `configure_logging` @[logging_config.py:41-66](../swing/logging_config.py) — already admits `surface ∈ {'web','pipeline','cli'}` and the §3.4 single-surface-per-process semantics (`_swing_surface` tag; a NEW surface removes+closes the prior swing handler). `install_logging` @[logging_setup.py:19-36](../swing/logging_setup.py) — carries the placeholder comment for `record_filter=_correlation_filter(surface)`; the seam already accepts `record_filter` + `logger_levels`.
- **`LoggingConfig`** @[config.py:432-440](../swing/config.py) — `level`/`max_bytes`/`backup_count`/`warnings` (the deferred-diagnostics carrier install_logging replays). Slice 2 adds the `[logging.loggers]` parse + `resolved_logger_levels()`.
- **The Popen site** @[web/routes/pipeline.py:127](../swing/web/routes/pipeline.py) — currently passes NO `env=` (child inherits). The spec's ONE justified touch: add `env={**os.environ, "SWING_WEB_REQUEST_ID": request_id}` (DEVNULL/`start_new_session` stay) + log the request_id at spawn in web.log.
- **The lease-acquisition call site** for `set_pipeline_run_id(run_id)` — `acquire_lease` @[lease.py:242](../swing/pipeline/lease.py); the runner's acquisition in `run_pipeline_internal` (the outer try; Arc-6/7 shifted lines — re-anchor). The spec: call it immediately after the lease row is inserted (`swing/pipeline/` is the allowed area).
- **The CLI entry** — `cli.py`'s click group callback (where `install_logging(cfg, surface="cli")` goes) AND the existing `pipeline_run_cmd` `install_logging(..., surface="pipeline")` call: under §3.4, `swing pipeline run` would install `cli.log` at group entry then REPLACE it with `pipeline.log` at the subcommand — **resolve the exact routing mechanics in the plan** (rely on §3.4 replacement [lean — it exists for exactly this] vs skip-install for the pipeline subcommand; either way pipeline.log's content must be unchanged vs today).
- **The finviz security suppression** (`_suppress_transport_debug_logs` in finviz_api.py) — STAYS as-is (spec §5.1: the auth-token-in-URL belt is not removed; the override table is the *general* lever).
- **The format-string change** — the correlation fields join the shared format via `defaults=` on the `RedactingFormatter`; the spec flags that existing web.log line-shape assertions change → **update those tests in the SAME task** (enumerate them at STEP 0: grep the web.log format assertions).
- Suite baseline: **7777** on main.

---

## 3. Plan-shape guidance (you own the decomposition; map tasks to the spec's §5 + §6 tests)

A natural ordering: (1) the correlation module (`swing/log_correlation.py`: the lock-guarded globals, `get_/set_` accessors, the strict env validation, reset-at-install semantics, `CorrelationFilter`) — pure-unit testable; (2) the format change (`defaults=` on the shared format + `RedactingFormatter`; wire `record_filter` through `install_logging`; update the web.log line-shape assertions same-task); (3) the Popen env touch + the spawn-time request_id log line + the `set_pipeline_run_id` call at lease acquisition; (4) `cli.log` (the group-callback install + the §3.4 routing resolution + the sentinel-leak audit extended to cli.log); (5) `[logging.loggers]` + `resolved_logger_levels()` (malformed → skip + a `warnings` diagnostic, never crash; shipped empty); (6) full suite + ruff.

**Binding test shapes (spec §5.2/§6):** the subprocess-with-`SWING_WEB_REQUEST_ID=<sentinel>` test (records carry the sentinel; post-`set_pipeline_run_id` records carry the run id; a no-context record renders `-`/`-` with NO KeyError); a FORGED/malformed env value (whitespace/newline/overlong) falls back to `-`; the reset-at-install test (a stale `pipeline_run_id` from a prior run in-process cannot bleed); worker-thread records carry the ids (the process-global rationale — a discriminating test that a contextvars impl would FAIL); the cli.log sentinel-leak audit; the override-table happy path + malformed-entry diagnostic replay. Discriminating per [[feedback_regression_test_arithmetic]] throughout.

---

## 4. Locks / invariants (do not regress)

Slice-1/Arc-1 non-regression: `pipeline.log` + the two belts + redaction-by-construction (cli.log gets ≥ the same coverage); the seam stays Schwab-agnostic (`logging_setup` remains the sole schwab importer); `configure_web_logging` retained; rotation/retention params unchanged. The Popen touch is env-ONLY (DEVNULL + `start_new_session` stay). NO schema (v28). `swing/trades/` + `swing/data/` untouched (the correlation set-call lives in `swing/pipeline/`). The finviz security suppression stays. Zero `Co-Authored-By`.

---

## 5. copowers process (binding)

- **Run `copowers:writing-plans`** → adversarial Codex loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED).
- **Codex transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git.
- Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Commit ONLY the plan doc; conventional; no `Co-Authored-By`; no `--no-verify`; final `-m` paragraph plain prose; trailers `[]`.
- **Return a report:** the plan path; the §2 routing resolution (cli.log vs the pipeline subcommand) + the enumerated web.log assertion updates; the Codex verdict (rounds + final line); flagged items for executing. Then STOP — executing is a separate commission after orchestrator QA.
