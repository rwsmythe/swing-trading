# Focused-Executing Dispatch Brief — Phase 16 / Arc 5: Shadow-Expectancy Drumbeat Integration

**Arc:** Phase 16 / **Arc 5** — run the shadow-expectancy engine automatically as the last functional step of the nightly pipeline. Research-director-commissioned (operator-approved): [`docs/phase16-shadow-expectancy-drumbeat-integration-commissioning-brief.md`](phase16-shadow-expectancy-drumbeat-integration-commissioning-brief.md) — **read it end-to-end** (the placement rationale §1, the design questions §2, constraints §3, done criteria §4).
**Cycle stage:** **FOCUSED executing-with-Codex** (single cycle; brainstorm+writing-plans collapsed — sanctioned by the commission §4, the design space is small; the Issue-#3/recorder/A-lite precedent). The design resolutions in §3 below are LOCKED (research-director leans + orchestrator grounding); your job is TDD implementation + Codex convergence. If grounding contradicts a resolution, STOP and flag.
**Branch-from:** main HEAD at worktree creation (re-verify with `git log --oneline -3`; **the Arc-2 Slice-1 logging executing cycle is IN FLIGHT in parallel** — it touches `swing/cli.py` + logging modules, NOT `runner.py`'s step chain; whichever merges second rebases, standard divergence discipline).
**Schema:** **NONE — v25 holds.** The step writes NO DB rows (the engine is read-only; outputs are file artifacts; step timing rides the Arc-1 `pipeline_step_timings` ledger automatically via `lease.step`).
**Deliverable:** the step shipped TDD + Codex-converged + `.copowers-findings.md` (prompts AND responses). Footprint: `swing/pipeline/runner.py` (the new step block) + tests. **NO `research/` changes** (verified unnecessary — see §2); NO config knob.

---

## 1. Mandate (one line)

Insert a best-effort `shadow_expectancy` pipeline step AFTER `_step_export` (`lease.step("export")` @runner.py:999), BEFORE `lease.step("complete")` (@1013): subprocess-invoke the installed shadow-expectancy CLI against `cfg.paths.db_path`, parse the artifact `manifest.json` into a one-line pipeline.log funnel summary, emit a #27 `run_warnings` entry on zero unique signals (and on any failure), with a timeout cap + cp1252-safe capture + keep-last-N artifact retention — so shadow-expectancy evidence accrues every session unattended.

---

## 2. Orchestrator grounding (verified on disk 2026-06-09 — trust but re-confirm at your HEAD)

- **CLI:** `@diagnose_group.command("shadow-expectancy")` @[cli.py:5087](../swing/cli.py); `diagnose_shadow_expectancy(db_path, output_dir, source, partial_session_n, ...)` @5097; deferred `research.harness.shadow_expectancy.run` import @5107 (`_ensure_research_importable` is the sanctioned bridge). `--db` required; `--output-dir` default `exports/research` (**CWD-RELATIVE — see §3.3**); tuning flags default to the spec'd ruleset (do NOT override them in the drumbeat).
- **Turnkey since `31e7441c`** (the entry/join-correction merge — verified).
- **Harness DB posture:** read-only `mode=ro` URI, never writes ([io.py:40-42](../research/harness/shadow_expectancy/io.py)); no explicit busy_timeout (sqlite3's 5s default applies). The production DB runs WAL → a reader doesn't block on the heartbeat writer (checkpoint-instant blocking is covered by the 5s default).
- **Artifact dir:** `exports/research/shadow-expectancy-<UTCts>/` with `manifest.json / per_session.csv / results.csv / summary.md` (verified against the operator's manual-run artifact `shadow-expectancy-20260609T174447Z`).
- **`manifest.json` is machine-readable for the funnel** (verified): top-level `funnel` → `detection_level.{total_detections, unique_signals, collapsed_duplicate_detection}` + `per_hypothesis` (dict) + `unattributed` (dict); also `harness_version`, `source`, `started_iso_utc`. **No engine change needed** — the commission's §3 route-back trigger does not fire.
- **Runner anchors:** `run_warnings` accumulator @815; `lease.step("export")` @999; `lease.step("complete")` @1013; the best-effort step shape = the existing pattern (`try: ... except LeaseRevokedError: raise; except Exception as exc: log.warning(...) + run_warnings.append(...)`) used by weather/finviz/observe.

---

## 3. LOCKED design resolutions (the commission's §2 questions — implement these)

1. **Contention (§2.1): NO retry machinery.** mode=ro + WAL + the 5s default busy timeout make heartbeat contention a non-issue in practice; any residual transient lock surfaces as a nonzero exit → classified as a **warned failure** (the standard best-effort path). Document this in the step's docstring (cite the grounding). Do NOT add retry-once complexity.
2. **Failure + empty semantics (§2.2, gotcha #27):**
   - Subprocess nonzero exit / timeout / spawn exception → `log.warning` + a `run_warnings` entry (`step="shadow_expectancy"`, `reason`, the captured stderr tail [redaction-safe: the engine handles no secrets, but cap the length ~512 + collapse newlines per the existing combined-message pattern]) — **never fails the run**. `LeaseRevokedError` re-raises (standard shape).
   - On success: parse `<artifact>/manifest.json` → emit ONE INFO line to the pipeline logger, e.g. `shadow_expectancy: total_detections=N unique_signals=N attributed=N unattributed=N artifact=<dirname>` (attributed = sum of `per_hypothesis` counts; unattributed = sum of `unattributed` values). Keep it ASCII.
   - **Zero unique signals → a `run_warnings` entry** (expected-vs-actual per #27: the engine ran fine but produced an empty funnel — honest output, surfaced not silent). A zero-priced (but nonzero-signal) run is NOT warned — it's the honest funnel.
   - Manifest missing/unparseable after a zero-exit run → warned failure (the artifact contract broke).
3. **Subprocess hygiene (§2.3):**
   - **Invocation:** `[sys.executable, "-m", "swing.cli", "diagnose", "shadow-expectancy", "--db", str(cfg.paths.db_path), "--output-dir", str(<resolved output root>)]` — the same installed-CLI surface via the interpreter, robust to PATH in the spawned-pipeline context (mirrors the web→pipeline spawn pattern). Do NOT rely on `swing.exe` being on PATH.
   - **Pin `--output-dir` EXPLICITLY** — the CLI default `exports/research` is CWD-relative, and the step must not depend on the pipeline process's CWD. Resolve the project-root `exports/research` deterministically (follow how the pipeline already resolves its `exports/` output root for briefings; reuse that anchor). The artifact must land where the operator's manual runs land.
   - **Timeout:** 300s (generous; the engine is seconds-scale today), `subprocess.run(..., timeout=300)`; on `TimeoutExpired` the child is killed (subprocess.run does this) → warned failure. Capture `stdout/stderr` with `encoding="utf-8", errors="replace"` (cp1252 gotcha — capture defensively even though the CLI is ASCII-safe).
   - Determine the run's artifact dir robustly: prefer parsing it from the CLI stdout if emitted; else newest `shadow-expectancy-*` dir under the output root created after step start. Lock one mechanism in code + test it.
4. **Retention (§2.4): keep-last-N prune, N=90** (generous; ~3 months of nightlies; small files). After a successful run, prune oldest `shadow-expectancy-*` dirs under the output root beyond 90 — best-effort (prune failure → log.warning only, never fails the step), matching ONLY the `shadow-expectancy-*` prefix (never any other research export).
5. **Knob (§2.5): always-on, NO new config surface.**
6. **Operator gate (§2.6):** surfaced in your return report — the orchestrator drives a live run post-merge (the Arc-1 gate pattern).

---

## 4. Execution disciplines (binding)

- **TDD, green-per-commit** (failing test → SEE fail → minimal impl → SEE pass → ruff → commit; conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; trailers `[]` each commit). Likely 2-3 commits (the step + semantics; retention; suite/polish) — your decomposition.
- **Tests exercise the production wiring** (commission §3): a fake/recorded subprocess boundary is fine, but assert the REAL command-line construction (the exact argv incl. `--db`/`--output-dir`), the failure tolerance (nonzero exit / timeout / missing manifest → warned, run completes), the #27 zero-signal warning (build the warning fixture from the REAL manifest shape — the funnel keys in §2; synthetic-fixture-vs-production-emitter drift is a known gotcha family), the retention prune (only `shadow-expectancy-*`, keeps newest 90), and `LeaseRevokedError` propagation. Discriminating assertions per [[feedback_regression_test_arithmetic]].
- **The step block mirrors the existing best-effort shape** in runner.py (read weather/finviz/observe first; match their idiom — comment density, warning-entry shape, LeaseRevokedError handling). `lease.step("shadow_expectancy")` BEFORE the work (the Arc-1 ledger contract: step() at the start of the step's work) — this gives the timing row + breadcrumb for free.
- **NO `research/` changes; NO schema; NO config knob; NO cli.py changes.** If you conclude an engine change is needed, STOP — that routes back to the research director (commission §3).
- **Full fast suite + ruff at the end** ON YOUR FINAL HEAD (actual count; the pre-existing `test_study_doc.py` em-dash failure is the operator's research doc, NOT this arc; isolate the 3 known xdist flakes `-n0` if they appear).
- **Degraded-harness guard:** on mid-batch tool cancellations → single sequential calls, re-Read before each Edit, verify each commit.

---

## 5. copowers Codex review (after all tasks land)

- Adversarial loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED) over the full diff vs this brief + the commission.
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`); tell Codex not to run git.
- Persist BOTH prompts AND responses every round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md`.

---

## 6. Return report (then STOP — do NOT merge)

The commit SHAs + messages; the full fast-suite result on your final HEAD (actual count; pre-existing failure called out); ruff clean; how the artifact-dir determination (§3.3) was locked; confirmation NO research/ + NO schema + NO knob; the Codex convergence verdict (rounds + final line); any deviation with justification; and the operator-gate note (a live nightly run must show the `shadow_expectancy` breadcrumb + the `pipeline_step_timings` row + the pipeline.log summary line + the artifact dir — the orchestrator drives it post-merge). Then STOP. Merge is the orchestrator's action after QA.
