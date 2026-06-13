# Phase 17 Arc 17-B — runner.py Step-Wrapper Extraction (commissioning brief)

**Authored:** 2026-06-13 by CHARC. **Register item:** D1 (runner.py navigability + dispatch-collision cost). **Roadmap:** [`docs/phase17-todo.md`](phase17-todo.md) §17-B.
**§3 tripwire (new module under `swing/`):** satisfied by construction — CHARC authors this brief and settles the module + abstraction shape in §3. The plan routes BACK through CHARC only if executing discovers a need for a different shape, a schema touch, a new dependency, or a §3 departure.
**Cycle shape:** writing-plans → executing (NO brainstorm — this brief is the locked design). Codex adversarial review to convergence at each phase; every round's RESPONSE persisted to a gitignored on-disk file. **The implementer reports to its ORCHESTRATOR; the ORCHESTRATOR posts the return report to charc,operator AFTER QA** (§8; CHARC charter §5.6 — the implementer never posts to a director inbox).

## 1. Mandate

Collapse the ~10× repeated per-step wrapper boilerplate in `swing/pipeline/runner.py` (the `lease.step(name)` + `try/except LeaseRevokedError/except Exception` block around each `_step_*` call) into ONE tested abstraction. This is the D1 debt's actionable core: navigability + dispatch-collision cost on the hottest, largest pipeline module (4,529 lines post-17-A). Behavior-preserving — zero change to what the pipeline DOES; only how the orchestration body reads.

**This is a pure refactor.** No behavior change, no schema, no new dependency, no phase-isolation carve-out (pipeline-internal).

## 2. Grounding (verified on disk 2026-06-13 post-17-A; the writing-plans engineer re-verifies at branch start — line numbers WILL drift)

The repeated shape, per step, in the `run_pipeline` body (the dominant region ~L735–1065):

```
lease.step("<name>")          # the Arc-1/#25 per-step timing breadcrumb — ALWAYS first
try:
    _step_<name>(... kwargs ...)
    lease.status(<key>_status="ok")        # PRESENT for some steps, ABSENT for others
except LeaseRevokedError:
    raise                                  # revoke ALWAYS propagates
except Exception as exc:
    <failure handler — one of three shapes below>
```

**Three failure-handler shapes (the full variant set, confirmed across the body):**
- **(F) FATAL** — `_step_evaluate` ONLY: `log.error(...)` → `lease.status(evaluation_status="failed")` → `lease.release(state="failed", error_message=str(exc))` → `return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))`. Aborts the whole run.
- **(BS) BEST-EFFORT + STATUS** — weather, watchlist, recommendations (and any sibling with a `*_status` field): `log.warning(...)` → `lease.status(<key>_status="failed")` → continue.
- **(B) BEST-EFFORT, NO STATUS** — daily_management, finviz_fetch, pattern_detect (and siblings without a status field): `log.warning(...)` → continue. Some carry a step-specific multi-line comment + custom log text; behavior is identical (warn + continue).

The Task-0 characterization (§4) MUST enumerate EVERY `lease.step(...)`-guarded site in the body and tag each (F | BS+key | B), including the steps not hand-listed here (schwab_snapshot, schwab_orders, charts, export, pattern_observe, shadow_expectancy, review_log_cadence, complete). The abstraction is validated against the FULL enumerated set, not this sample.

## 3. Architecture (settled — the tripwire content)

- **New module: `swing/pipeline/step_guard.py`** — a small, independently unit-testable context manager. Sanctioned: control-flow code belongs in its own tested file, not buried in the 4,500-line runner (the whole point of the arc is reducing that file's cognitive load). NOT in `swing/data` or `swing/trades` (no carve-out); pipeline-internal.
- **Shape — a context manager handling the BEST-EFFORT variants (BS + B), the dominant duplication:**
  ```
  with step_guard(lease, "watchlist", status_key="watchlist_status"):   # BS
      _step_watchlist(...)
  with step_guard(lease, "pattern_detect"):                              # B (status_key=None)
      _step_pattern_detect(...)
  ```
  The CM, on `__enter__`: calls `lease.step(name)` (the #25 breadcrumb, same point as today). On clean exit: `lease.status(<key>="ok")` when `status_key` given, else nothing. On `LeaseRevokedError`: re-raise (propagate). On any other `Exception`: `log.warning("%s failed: %s", name, exc)` (or an overridable message to preserve a step's exact current text where it matters) → `lease.status(<key>="failed")` when `status_key` given → SWALLOW (continue). An optional `log_level`/`message` param covers the steps whose current log text differs (e.g. the "programming error (continuing)" wording) so the characterization stays byte-identical on the log surface where a test pins it.
- **The single FATAL step (`_step_evaluate`) stays EXPLICIT — do NOT force it into the guard.** Its control flow returns `RunResult` from the OUTER `run_pipeline` function; a context manager cannot return from its caller, and contorting the guard to signal run-abort (sentinel exceptions, result flags the loop checks) would add complexity and a second code path for ONE site — net-negative against a one-occurrence case. Leave evaluate's wrapper as-is; the win is the ~9–10 best-effort sites. (If the engineer finds a second genuinely-fatal step in the §4 enumeration, STOP and route to CHARC — the variant set would have changed.)
- **No new dependency. No schema. No `swing/data` or `swing/trades` touch. No config/pyproject edit.** Files: new `swing/pipeline/step_guard.py` + `swing/pipeline/runner.py` (the call-site rewrites) + new `tests/pipeline/test_step_guard.py` + whatever existing pipeline tests assert per-step failure behavior (kept green).

## 4. Phase 0 — failure-mode characterization (BINDING PRECONDITION)

Before ANY extraction, a characterization test that pins each guarded step's failure behavior against the CURRENT code and stays green through the refactor:

- For EACH `lease.step`-guarded site: inject a raised `Exception` into the step body (monkeypatch/fixture) and assert the observable contract — does the run ABORT (RunResult state='failed') or CONTINUE; the resulting `*_status` value (or its absence); that `LeaseRevokedError` propagates (a planted `LeaseRevokedError` is NOT swallowed); and that `run_warnings` / `lease.step` breadcrumb behavior is unchanged.
- A single-source enumeration of all guarded sites + a completeness guard (the 17-A `DIVERGENCES`-inventory pattern) so a site added later can't silently escape the matrix.
- The characterization is the permanent regression that proves byte-identical behavior; it lands FIRST (green against un-refactored code), then the extraction keeps it green.

## 5. §3 locks (hold every task; itemize compliance in the return report — the 17-A QA discipline)

1. **#25 per-step timings UNCHANGED** — `lease.step(name)` fires at the same point (CM `__enter__`, before the body) for every step; no step boundary added, moved, or renamed.
2. **#27 run_warnings semantics UNCHANGED** — the accumulator is threaded into step BODIES, never into the guard; the guard does not touch `run_warnings`.
3. **#16 fetch-hoist UNTOUCHED** — the `read_or_fetch_archive` warm hoisted OUTSIDE the per-trade fence is not in the wrapper boilerplate; do not disturb it.
4. **`LeaseRevokedError` ALWAYS propagates** — the guard re-raises it; a planted-revoke test proves it is never swallowed.
5. **Per-step failure shape BYTE-IDENTICAL** — each step keeps its exact (F | BS+key | B) behavior, its `*_status` key, and the log surface any test pins. The FATAL evaluate path is left explicit and unchanged.
6. **`evaluate_batch`, `orchestrate_evaluation` (17-A), and all step BODIES untouched** — this arc rewrites only the wrapper around the calls, never the calls' internals.
7. **NO schema / dependency / `swing/data` / `swing/trades` / config / pyproject.**

## 6. Scope boundary (explicit — what 17-B does NOT do)

**DEFERRED, NOT in 17-B: relocating the non-step infrastructure** (finviz CSV select ~L4264-4576, shadow-expectancy helpers, chart/briefing composers ~L3600-3887) into their own modules. The roadmap listed this as OPTIONAL; CHARC's call is to keep 17-B tight. Rationale: moving ~1,000 lines across module boundaries is a far larger blast radius (import graph, test relocation) than the wrapper extraction, and D1 is downgraded debt (navigability, not rot). It deserves its own operator decision on its own merits AFTER the wrapper extraction lands — if runner.py navigability still bites, it becomes a separate candidate arc (17-B.2 / future). Bundling it here would muddy the clean behavior-preservation argument. The engineer does NOT relocate infrastructure in this arc.

## 7. Operator gate

Lighter than 17-A — this is a behavior-preserving internal refactor with no surface change. The binding evidence is: the §4 characterization matrix green pre- AND post-extraction; the full fast suite green on the merged head (no-false-green re-run); ruff clean. **No new operator-witnessed live gate is required** (no user-facing or persisted-data change). The orchestrator confirms a real pipeline run still completes normally as a smoke check; if the orchestrator's QA finds any per-step behavior it cannot prove identical, it routes back before merge.

## 8. Return report (orchestrator posts AFTER QA — never the implementer)

The ORCHESTRATOR posts to `charc,operator` (`--type return_report`) after its QA gate. Itemize: per-task commits (trailers `[]`); the §4 characterization matrix (every guarded site + its tagged variant + the pinned contract); §5 lock compliance verified on disk; the new `step_guard.py` surface; test counts on the FINAL (merged) head; Codex rounds + verdict; deviations with rationale. Confirm the FATAL evaluate step was left explicit and the infra relocation was NOT performed (§6).
