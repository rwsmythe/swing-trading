# Dispatch brief — Minervini primary-base recall: executing-plans phase

**Phase:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` + adversarial
Codex review to convergence). **Predecessor:** the Codex-converged plan, orchestrator-QA'd PASS.
**Drafted:** 2026-06-09 (orchestrator). **Baseline SHA:** `4925e0d8`.

## Your task

Execute the implementation plan task-by-task (all 14 tasks + the final-verification checklist):

- **Plan (your task list, READ FIRST, in full):**
  [`docs/superpowers/plans/2026-06-09-primary-base-recall.md`](superpowers/plans/2026-06-09-primary-base-recall.md)
  (commit `4925e0d8`). Self-contained: each task has the real failing test (with `WRONG-PATH`/
  `RIGHT-PATH` values), the minimal impl, run commands, and a commit. Findings transcript: gitignored
  `.copowers-findings.md`.
- **Spec (the why):**
  [`docs/superpowers/specs/2026-06-09-primary-base-recall-design.md`](superpowers/specs/2026-06-09-primary-base-recall-design.md).

Run the full `copowers:executing-plans` flow: implement each task TDD-style, then the adversarial Codex
critic over the diff **to convergence** (zero new critical/major). Work on `main` (or an isolated
worktree branching from `4925e0d8` that merges to main).

## Binding disciplines

- **Research carve-out:** the ONLY `swing/` change in the arc is the single
  `swing diagnose primary-base-recall` registration. Everything else under
  `research/harness/minervini_primary_base_recall/` + `tests/research/minervini_primary_base_recall/`.
  **No `--db`.** Final-verification asserts `git diff --stat 4925e0d8..HEAD -- swing/` = only `swing/cli.py`.
- **L2 LOCK:** the HARDENED test pattern — **monkeypatch-restored `sys.modules`, NEVER raw `del`**
  (the 2026-06-09 xdist gotcha in CLAUDE.md); reproduce isolation issues with `-n 0`, not `-n auto`.
- **Reuse frozen leaves only:** `minervini_exemplar_recall.{ohlcv_reader, exemplar_reader, scorecard}`
  + `ControlAnchor`; `swing.patterns.foundation.{extract_zigzag_swings, Swing}`. **Do NOT reuse
  `sample_control_anchors`** — the plan's own pre-filtered young-window sampler is correct; keep it.
- **TDD, literally** (failing test → see fail → minimal impl → see pass → commit); preserve the
  `WRONG-PATH`/`RIGHT-PATH` discriminators (esp. the fresh-cross-not-recross + first-fire fixtures).
- **ASCII-only** (`encode("ascii")`, not cp1252; no literal em dash/curly quotes in source or tests);
  **no `Co-Authored-By`**, no `--no-verify`, plain final `-m` paragraph; verify
  `git log -1 --format='%(trailers)'` empty after each commit.
- **NO false-green:** the final fast-suite run is on the MERGED head — RUN `python -m pytest -m "not slow" -q`
  and READ the real count; never carry a branch count forward. The 2026-06-09 baseline was 7331 fast.
- **Codex transport + persistence:** WSL CLI fallback (liveness `codex --version` → `codex-cli 0.135.0`);
  the executing-plans review diffs against **BASELINE_SHA `4925e0d8`**; **persist every Codex round's
  full RESPONSE** (incl. `NO_NEW_CRITICAL_MAJOR`) to the gitignored findings file for orchestrator QA.
- **Degraded-harness caution:** mid-batch tool cancellations → single sequential calls + re-Read before
  each Edit + verify each commit landed.

## Watch-items (the load-bearing mechanics — verify they ship intact)

- The **C1 precision wiring** — control results PERSISTED → per-exemplar `precision_contrast`
  (single-session per-anchor PRIMARY, window best-of SEPARATE, NA-not-zero) → a `## Precision`
  section in `summary.md`. (This was the writing-plans critical; don't let it regress.)
- **Screen:** `MIN_HISTORY_BARS=40`; explicit swing→base algorithm with **calendar→bar mapping**
  (never `Swing.duration_days`); trading-week depth ladder (`≤25→0.25`/`26-200→0.35`/`>200→0.50`);
  **fresh-cross-not-recross** emergence; **primary=first-base first-fire** replay (non-recursive, O(N²)).
- **Cohort:** {AMZN-1997, BODY, DKS} evaluable sub-floor + YHOO positive control + JNPR
  `history`-excluded; **MELI absent**; AMZN → `twosmw-fig11-1-amzn` (not the 2002 cup).
- **Timing:** day/exact `[entry−60bd, entry+5bd]`; month-precision **full documented month**;
  single-session **day-only (BODY, n=1)**.
- **Precision:** own pre-filtered sampler (`[39,503]` BEFORE sampling); manifest
  `eligible_control_count_before_sampling` + exact bar counts.
- **Study-doc Conclusion (Task 13):** in addition to the spec's framing, add a one-line note that per
  the **Research-Director charter (`docs/research-director-context.md`, P2)** this screen's output is
  **unvalidated until a P1 shadow-expectancy engine can price its expectancy** — so the deployable
  recommendation is "expand the corpus + price via P1," not "deploy."

## Scope boundary (do NOT cross)

**Stop after the harness is built + tests green + Codex-converged + the final-verification checklist
is complete.** Do NOT run the operator smoke run (materialize/pull data, run `swing diagnose
primary-base-recall`, populate the study Results/Interpretation/Conclusion) — that needs the local
Tiingo archive + is the operator's post-merge gate. Leave the Task-13 study Results as a documented
placeholder. The slow integration test runs only if the archive is present; otherwise note it deferred.

## Deliverable / return report

All tasks committed; harness fast suite green; repo fast suite green on the merged head (report the
real count); ruff clean; the findings file with every executing-plans Codex round's verbatim response
+ final verdict. Return: tasks completed, harness test count, **merged-head fast-suite count read
LIVE**, Codex rounds + final verdict, findings-file path, `git diff --stat 4925e0d8..HEAD -- swing/`
(must be only `swing/cli.py`), any deviations, and confirmation the operator smoke run was left untouched.
