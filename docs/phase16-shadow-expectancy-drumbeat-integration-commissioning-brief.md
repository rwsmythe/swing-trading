# Phase 16 — Shadow-Expectancy Drumbeat Integration — Arc Commissioning Brief

**Audience:** The Phase 16 orchestrator instance (manages `docs/phase16-todo.md`; runs copowers cycles).
**Mission:** Commission a new Phase 16 arc (**Arc 5** — Arcs 1–4 + the perf follow-on are taken): make the shadow-expectancy engine run **automatically as part of the nightly pipeline drumbeat**, so shadow-expectancy evidence accrues every session without the operator remembering to invoke it.
**Prepared:** 2026-06-09 by the research-director/evaluator instance (operator-commissioned).
**Division of responsibility (operator-set):** the research-director arc finishes TOOL development (the broad-watch-baseline hypothesis amendment, a separate parallel arc — `docs/broad-watch-baseline-hypothesis-brainstorming-dispatch-brief.md`); the placement recommendation below is the research-director's call; **Phase 16 owns the operational-integration implementation** (its own brainstorm → writing-plans → executing-plans cycle, scoped as small as the orchestrator judges right).

---

## 0. Read first

1. `CLAUDE.md` — conventions + gotchas (esp. #27 silent-skip-without-audit; the `database is locked` deadlock history; the cp1252 console-encoding gotcha; the lease/fence hygiene entries).
2. `docs/phase16-todo.md` — add this as Arc 5 when you accept the commission.
3. The engine's CLI surface — `swing/cli.py` `diagnose shadow-expectancy` (~L5087): `--db` (required), `--output-dir` (default `exports/research`), plus tuning flags (defaults are the spec'd ruleset — do not override them in the drumbeat). Read-only over the DB; writes a timestamped artifact dir (`exports/research/shadow-expectancy-<UTC>/` with results.csv / per_session.csv / summary.md / manifest.json). Turnkey from the installed entry point since `31e7441c`.
4. The pipeline step sequence — `swing/pipeline/runner.py` ~L817–1024: `evaluate → daily_management → watchlist → recommendations → pattern_detect → pattern_observe → schwab_snapshot → schwab_orders → charts → export → complete`, with the `run_warnings` accumulator (~L815) and `flush_step_timings()` in the finally (~L1037).
5. Context (why this matters): `docs/research-director-context.md` §6 P1/P1-NOW. One paragraph version: the engine is the instrument that answers the pre-registered hypothesis program at signal-pace instead of trade-pace; it is read-only, honest (a zero-priced run is valid output), and its evidence only accrues if it actually runs every session. Manual invocation will be forgotten; the drumbeat is the fix.

---

## 1. The research-director placement recommendation (binding direction; implementation detail is yours)

**Insert a new best-effort pipeline step `shadow_expectancy` AFTER `_step_export`, BEFORE the `complete` release** (i.e. the last functional step of the nightly run). Rationale:

1. **Data dependencies are final after `pattern_observe`** (~L904): `_step_evaluate` writes the `candidates` rows the engine joins; `pattern_detect`/`pattern_observe` write the temporal-log detections + today's forward observations. Running after them means each nightly run prices the just-completed session ("after a process run" in the operator's framing — the trading day is over when the pipeline runs).
2. **Last-slot placement protects operator-facing outputs**: a slow or failed shadow run cannot delay or damage the briefing/charts/export chain.
3. **Inside the lease = serialized with all writers + free observability**: `lease.step("shadow_expectancy")` breadcrumb, a row in the Arc-1 `pipeline_step_timings` ledger, and `pipeline.log` lines — no new observability plumbing.

**Rejected alternatives (state them in your spec so they stay rejected for reasons, not by accident):**
- *Before the pipeline run* — prices data one session stale, forever.
- *External scheduler (Windows Task Scheduler / separate cron)* — a second moving part with no lease coordination (could read mid-write without the serialization the step slot gives), no step-timing/pipeline.log integration, and silent-drift risk when the operator's run time shifts.

**Invocation: subprocess of the installed CLI** (`swing diagnose shadow-expectancy --db <cfg.paths.db_path>`), NOT an in-process import. `swing/pipeline/` importing `research/` would cross the operational/research bifurcation boundary (research/ is not an installed package; the CLI's `_ensure_research_importable` is the sanctioned bridge) and would let a harness bug crash the pipeline process. Subprocess cost is one Python cold-start (~2–4s on this box, nightly — acceptable). If your brainstorm concludes in-process is genuinely better, that conclusion needs explicit justification against both points.

---

## 2. Design questions your brainstorm must resolve

1. **Reader-vs-heartbeat contention.** The lease heartbeat thread writes `pipeline_runs.heartbeat_ts` while the subprocess reads the same DB read-only. Given this project's `database is locked` history (fixed `ffb5fdc6`+`4f0b4010`), verify the engine's `mode=ro` connection + busy-timeout posture survives a concurrent heartbeat write; decide whether the step needs a retry-once or just classifies a transient lock as a warned failure.
2. **Failure + empty-output semantics (gotcha #27).** Step failure → `log.warning` + a `run_warnings` entry (never fails the run). A zero-priced/zero-signal engine run is NOT a failure (honest funnel) — but the step should parse/relay a one-line summary (e.g. `total_detections / unique_signals / attributed / priced`) into `pipeline.log`, and append a `run_warnings` entry when the engine emits zero unique signals (expected-vs-actual, per the gotcha).
3. **Subprocess hygiene.** Timeout cap (a hung engine must not stall the nightly run — pick a bound and kill semantics); captured stdout/stderr encoding on Windows (cp1252 gotcha — the CLI is ASCII-safe but capture defensively); exit-code contract (the CLI's nonzero modes); working-directory/PATH assumptions (must work from the spawned pipeline subprocess context exactly as from the operator's shell).
4. **Artifact retention.** One `exports/research/shadow-expectancy-<ts>/` dir per nightly run accumulates ~365 dirs/year. Decide V1 posture: unbounded-with-documented-growth vs a prune-keep-last-N in the step. (Small files; my lean is keep-last-N with N generous, but cheap either way — just decide explicitly.)
5. **Config knob vs always-on.** My lean: always-on best-effort V1, no new config surface. If you add a knob, default it ON.
6. **Operator gate.** Mirror the Arc-1 production-path gate: one witnessed live nightly run showing the step's pipeline.log lines + the timing-ledger row + the artifact dir on disk before the arc closes.

---

## 3. Constraints

- **NO schema change.** The step writes no DB rows (the engine is read-only; its outputs are file artifacts). Step timing flows through the existing Arc-1 ledger automatically.
- **Footprint:** `swing/pipeline/runner.py` (the new step block, mirroring the existing best-effort step shape) + tests (+ config only if the knob is chosen). No engine changes — if the integration appears to need an engine change (e.g. a `--quiet`/machine-readable summary flag), route that as an explicit question back to the research director rather than patching `research/` from this arc.
- **Sequencing:** fully independent of the broad-watch-baseline hypothesis arc — land in either order. Until that amendment ships, the nightly artifact will honestly show `matched_no_hypothesis` for everything; that is correct behavior, not a reason to wait.
- **Tests:** the step must be exercised through the production wiring (a fake/recorded subprocess boundary is fine; asserting the real command-line construction + failure tolerance + warning emission). The fast suite stays green; ruff clean; zero co-author trailers.

---

## 4. Done criteria

- The arc lands on `main` via your normal copowers cycle (brainstorm may be light — the design space is small; your call on collapsing phases).
- A live nightly pipeline run produces: the `shadow_expectancy` step breadcrumb, a `pipeline_step_timings` row, pipeline.log summary line(s), and the artifact dir — witnessed by the operator (§2.6).
- `docs/phase16-todo.md` updated (Arc 5 entry + completion state).
- Report back to the operator; the research director QAs the integration's honesty surfaces (the warning/empty-output semantics) at the next evaluation session.
