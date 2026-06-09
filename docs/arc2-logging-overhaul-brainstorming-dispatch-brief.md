# Brainstorming Dispatch Brief — Phase 16 / Arc 2: Logging-System Overhaul

**Arc:** Phase 16 (Observability & Logging) / **Arc 2** — one coherent, configurable, redaction-safe, retention-bounded logging system across web + CLI + pipeline, replacing today's per-surface ad-hoc setup. Builds directly on the `configure_logging` seam Arc 1 shipped.
**Cycle stage:** `copowers:brainstorming` (produce a LOCKED design spec, Codex-converged). FULL copowers cycle (brainstorm → writing-plans → executing). **The brainstorm covers all 6 sub-items (2a-2f) as one system design, and MUST recommend an implementation-sequencing** — the resulting spec may split into more than one writing-plans/executing cycle if large (flag that in the return).
**Branch-from:** main HEAD at worktree creation (currently `e51c734f`; **re-verify with `git log --oneline -3`** — the operator commits research to main in parallel).
**Schema:** **NONE expected — v25 holds.** Arc 2 is runtime/logging + config only; no DB schema touch. If your design concludes a table is warranted (it should not — `pipeline_step_timings` already covers per-step timing), STOP and flag it as a pivotal OQ.
**Deliverable:** a locked design spec at `docs/superpowers/specs/2026-06-09-logging-overhaul-design.md` + Codex convergence (`NO_NEW_CRITICAL_MAJOR`) + `.copowers-findings.md` (prompts AND responses).

---

## 1. Mandate (one line)

Design the unified logging system: one centralized `configure_logging` that web/CLI/pipeline all route through (consistent format, rotation, a **config-driven level knob**, per-surface file routing), with **rotation+RETENTION** that bounds the 225MB logs dir, **redaction guaranteed by construction** on every surface, **web↔subprocess run correlation**, and **log-volume right-sizing** — then recommend how to sequence the build.

The design is the deliverable; do NOT implement. Settle the §6 OQs WITH the operator, Codex-converge, return.

---

## 2. Grounded current state (Arc 1 left a precise map — verify on HEAD)

- **The seam Arc 1 shipped:** `swing/logging_config.py:configure_logging(logs_dir, *, surface, level=INFO, formatter=None)` — attaches a `TimedRotatingFileHandler` writing `{surface}.log` to root, idempotent by `baseFilename`, Schwab-agnostic. `surface in {'web','pipeline'}` TODAY. **`level` already exists as a param but is NOT wired to any config knob** (2f wires it). `configure_web_logging` ([middleware/request_id.py:32](../swing/web/middleware/request_id.py)) is now a thin shim over it; `app.py:441` calls it. `pipeline_run_cmd` ([cli.py:~3220](../swing/cli.py)) installs Belt A (`ensure_schwab_log_redaction_factory_installed`) + Belt B (`RedactingFormatter`, [client.py](../swing/integrations/schwab/client.py)) then calls `configure_logging(surface="pipeline", formatter=RedactingFormatter(...))`.
- **Rotation TODAY:** `TimedRotatingFileHandler(when="D", interval=1, backupCount=7, encoding="utf-8")` — DATED rotation. `backupCount=7` SHOULD cap daily files at 7 — **but the logs dir holds dated files far older than 7 days** (`web.log.2026-04-20`, `2026-05-06` [83MB], `2026-05-23` [97MB]) — so either rotation wasn't always configured, or these predate the handler / were written by a differently-named handler. **Investigate why backupCount=7 did not bound them** (a real OQ — the retention design must actually work).
- **Disk state (orchestrator-measured 2026-06-09):** `~/swing-data/logs/` ≈ **225MB**: `web.log` **58MB** (current) + `web.log.2026-05-06` **83MB** + `web.log.2026-05-23` **97MB** + several small dated files. **NO `cli.log`.** `pipeline.log` now exists (Arc 1, small).
- **Redaction TODAY:** process-global `setLogRecordFactory` (`ensure_schwab_log_redaction_factory_installed`, Schwabdev-prefix records) + Arc-1's `RedactingFormatter` (full-line, on the pipeline.log handler only). **Installed per-call-site/defensively, NOT by the centralized config** — so a NEW surface (e.g. `cli.log`) is NOT redaction-covered unless it explicitly wires the belts.
- **Level control TODAY:** none centralized. `swing/integrations/finviz/finviz_api.py` does ad-hoc per-logger level juggling (`_TRANSPORT_DEBUG_LOGGERS`). Root is set to `INFO` by `configure_logging`.
- **Correlation TODAY:** the web has `request_id` middleware ([middleware/request_id.py](../swing/web/middleware/request_id.py)); the pipeline subprocess is a SEPARATE process (spawned by `web/routes/pipeline.py`) with NO correlation id threaded back to the triggering request or the `pipeline_runs.id`. (Arc 1 persists `pipeline_step_timings` keyed by `run_id` — a correlation anchor already exists in the DB.)

---

## 3. The sub-items to design (2a-2f — the spec covers all six as one system)

- **2a — Centralized `configure_logging`.** Extend the Arc-1 seam to be THE single entrypoint for web/CLI/pipeline: add `surface="cli"` (+ a `cli.log`), make the CLI (`cli.py`) call it, subsume the `finviz_api` ad-hoc level juggling. Consistent format + rotation across all three. (The seam already exists — this is its completion, not a rewrite.)
- **2b — Rotation + RETENTION.** Bound the logs dir: a retention cap (max files / max age / max total size). Decide the rotation TRIGGER (size-based `RotatingFileHandler` with `maxBytes` vs the current dated `TimedRotatingFileHandler` — given 58-97MB single files, size-based may fit better) and reconcile with `backupCount`. **Plus a ONE-TIME cleanup of the existing oversized rotated files — operator-gated + destructive (their real logs), so design it as a separate approved step, not an auto-delete.**
- **2c — Redaction by construction.** Promote the Schwab redaction (Belt A factory + the Belt B `RedactingFormatter`) INTO `configure_logging` so EVERY surface (web, cli, pipeline) is redaction-covered by construction, not per-call-site. Keep `configure_logging` itself Schwab-agnostic (inject the formatter/factory installer, don't bake the import) — preserve Arc-1's seam-purity. Extend the sentinel-leak audit test to the new surfaces (esp. `cli.log`).
- **2d — Run/request correlation.** Thread a correlation id (the `pipeline_run_id` and/or the web `request_id`) through the spawned pipeline subprocess's log records so `web.log` ↔ `pipeline.log` ↔ `pipeline_runs`/`pipeline_step_timings` line up for a given run. (The subprocess is spawned with `--config <path> pipeline run --manual`; decide the transport — env var, CLI arg, or a `LogRecord` filter/adapter.)
- **2e — Log-volume right-sizing.** Investigate why `web.log` reaches 53-97MB (DEBUG/per-request noise? a chatty dependency? the `finviz_api` transport-debug loggers? access-log lines?). Identify + demote the noise; generalize the dependency-logger control.
- **2f — Verbosity knob.** A `[logging]` section in `swing.config.toml` / user-config (`level` + optional per-logger overrides), wired to the existing `configure_logging(level=...)` param + surfaced consistently — so the operator can dial DEBUG for a diagnosis run without code edits.

---

## 4. Things to nail (each needs a test where applicable)

- **Redaction-by-construction is PROVEN on every surface** — extend the sentinel-leak audit (the `test_schwab_client.py` / Arc-1 `test_pipeline_log_redaction.py` family) to `cli.log` + `web.log`: a planted secret-shaped sentinel through a non-Schwabdev logger is redacted on ALL surfaces. The promotion must not create an unredacted window (formatter set before handler joins root — Arc-1 invariant).
- **Retention actually bounds the dir** — a test that drives N rotations / oversized writes and asserts the cap holds (file count / total size). Explain why today's `backupCount=7` did NOT bound the 83-97MB files (else the new policy may have the same blind spot).
- **The seam stays idempotent + web.log behavior preserved** — all existing `web.log` tests stay green; `configure_web_logging` shim unchanged externally; adding `surface="cli"` doesn't perturb web/pipeline.
- **Correlation id round-trips** — a web-triggered run's `pipeline.log` records carry the correlating id; a test asserts the id appears in the subprocess log records (or the chosen transport delivers it).
- **The level knob is honored** — config `[logging] level=DEBUG` → root/handlers at DEBUG; default INFO; malformed value degrades safely (not a crash).
- **Windows/encoding** (CLAUDE.md §Gotchas/Windows) — utf-8 handlers; ASCII in new operator-facing strings; cp1252 stdout footgun.
- **Discriminating tests** ([[feedback_regression_test_arithmetic]]) — esp. the retention cap (assert the value distinguishes bounded vs unbounded) + redaction (a sentinel that ONLY the promoted coverage catches).

---

## 5. Locks / invariants (do not regress Arc 1)

- **Schema NONE (v25 holds).** DB-outside-Drive.
- **Do NOT regress Arc 1:** the `configure_logging` seam, `pipeline.log`, the two-belt pipeline redaction, the `configure_web_logging` shim, and `pipeline_step_timings` all stay working. `configure_logging` stays Schwab-AGNOSTIC by construction (2c promotes redaction via injection, not by importing schwab into the seam module). `swing/web/routes/pipeline.py` DEVNULL spawn unchanged unless 2d's correlation transport requires a minimal, justified touch (flag it).
- **`swing/trades/` + `swing/data/` read-only** (no schema; logging is cross-cutting infra).
- **The one-time 225MB cleanup is OPERATOR-GATED + destructive** (the operator's real historical logs) — design it as an explicit approved step (archive or delete with confirmation), NEVER an auto-delete baked into normal operation. Surface the proposed disposition (which files, how much reclaimed) for operator sign-off at execution.
- **Redaction is never weakened** — promoting it to the seam must be strictly additive (every surface gets ≥ today's coverage). Sentinel-leak audit extended, never narrowed.

---

## 6. Open questions for the operator (brainstorming surfaces + resolves these)

- **OQ-1 — implementation sequencing:** all 6 in one writing-plans/executing cycle, or ship a fast slice first (e.g. 2b retention — the real disk pain — or 2a+2c the centralized+redaction core), deferring 2d/2e? Recommend a sequencing; flag whether the spec should split into multiple plan/execute cycles.
- **OQ-2 — rotation trigger:** size-based `RotatingFileHandler(maxBytes,backupCount)` vs keep dated `TimedRotatingFileHandler` (+ a size guard). Given 58-97MB single files, which bounds better? And WHY did `backupCount=7` not bound the existing files?
- **OQ-3 — retention policy params:** max total size / max age / max files for the logs dir — pick concrete defaults (config-driven?).
- **OQ-4 — the one-time cleanup:** which existing files to archive vs delete (the 83+97MB rotations), and the operator's preferred disposition. (Gated; design only.)
- **OQ-5 — correlation transport:** env var vs CLI arg vs LogRecord filter for threading the run/request id into the subprocess.
- **OQ-6 — level-knob shape:** `[logging] level` + per-logger overrides table in `swing.config.toml` vs user-config; interaction with the `finviz_api` transport-debug loggers.
- **OQ-7 — volume right-sizing:** what's actually filling web.log (needs a quick investigation of the live 58MB file's line distribution) — surface the dominant noise source.

---

## 7. copowers process (binding)

- Run `copowers:brainstorming` (wraps `superpowers:brainstorming` — explore the §6 OQs WITH the operator — then the adversarial Codex loop **to convergence**, `NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED).
- **Codex transport (WSL CLI; the MCP `codex` tool is DEAD in the VS Code extension):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows + tell Codex not to run git.
- **Persist BOTH prompts AND responses** of every round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md`.
- No `Co-Authored-By`; no `--no-verify`; conventional commits; final `-m` paragraph plain prose (verify `git log -1 --format='%(trailers)'` is `[]`). Commit ONLY the spec doc.
- **Return a report:** the spec path; the resolved §6 OQs (esp. the sequencing recommendation + whether the spec splits into multiple cycles); the Codex convergence verdict (round count + final line); anything flagged for writing-plans. Then STOP — do NOT proceed to writing-plans.

---

## 8. What this arc is NOT

NOT a schema change (v25 holds; `pipeline_step_timings` already covers per-step timing — do NOT add a logging table). NOT a rewrite of the Arc-1 seam (it's the foundation — extend it). NOT the perf follow-on (that consumes `pipeline_step_timings`, separate). NOT Arc 3 (XMAX thumbnail) or Arc 4 (equity reconciliation). NOT an auto-deleting log cleaner (the one-time cleanup is operator-gated). The Schwab redaction mechanism itself (the factory + heuristics) is NOT re-designed — it is PROMOTED to the centralized seam unchanged.
