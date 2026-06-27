# Dispatch brief — Minervini exemplar-recall: executing-plans phase

**Phase:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` +
adversarial Codex review to convergence). **Predecessor:** the Codex-converged implementation plan,
orchestrator-QA'd PASS. **Drafted:** 2026-06-08 (orchestrator). **Baseline SHA:** `292fff17`.

## Your task

Execute the implementation plan task-by-task (Tasks 1-18 + the final-verification checklist):

- **Plan (your task list, READ FIRST, in full):**
  [`docs/superpowers/plans/2026-06-08-minervini-exemplar-recall.md`](superpowers/plans/2026-06-08-minervini-exemplar-recall.md)
  (commit `292fff17`). It is self-contained: every task has the real failing test, the minimal
  implementation, the run commands, and a commit. Appendix A (spec-coverage) + Appendix B
  (type-consistency ledger) are your cross-task contracts — honor them.
- **Spec (the why, for context):**
  [`docs/superpowers/specs/2026-06-08-minervini-exemplar-recall-design.md`](superpowers/specs/2026-06-08-minervini-exemplar-recall-design.md).

Run the full `copowers:executing-plans` flow: implement each task TDD-style, then run the adversarial
Codex critic over the diff **to convergence** (zero new critical/major). Work on `main` per the
project convention (or an isolated worktree that merges to main — your choice; the orchestrator does
the final merged-head QA either way).

## Binding disciplines

- **TDD, literally:** for each task write the failing test, RUN it and SEE the expected failure,
  write the minimal impl, RUN it and SEE it pass, commit. The plan's `WRONG-PATH`/`RIGHT-PATH`
  annotations are the discriminating-test contract — preserve them.
- **Research carve-out + the one `swing/` edit:** the ONLY `swing/` change in the entire arc is the
  single `swing diagnose minervini-recall` registration in `swing/cli.py` (Task 12). Everything else
  is under `research/harness/minervini_exemplar_recall/` + `research/scripts/materialize_vicr_yfinance.py`
  + `tests/research/minervini_exemplar_recall/`. The final-verification step asserts
  `git diff --stat 292fff17..HEAD -- swing/` shows only `swing/cli.py`.
- **L2 LOCK:** Task 13 enforces it (static grep + `sys.modules` import-smoke). The harness import
  graph imports none of yfinance / schwabdev / `swing.integrations.schwab` / `swing.data.ohlcv_archive`;
  the VICR materializer (which imports yfinance) is a separate process, never imported by the harness.
- **Commits:** conventional; **NO `Co-Authored-By`**, **no `--no-verify`**; plain final `-m`
  paragraph (no leading `Word:` trailer-parse hazard); after each commit confirm
  `git log -1 --format='%(trailers)'` is empty.
- **NO false-green (memory `feedback_no_false_green_claim`):** the final-verification suite run must
  be on the MERGED head; RUN `python -m pytest -m "not slow" -q` and READ the actual count — never
  carry a branch/older count forward. Baseline is ~7265 fast tests; report the real post-arc number
  + zero new failures.
- **Codex transport + persistence:** MCP `codex` tools are dead in the VS Code extension → the
  copowers chain auto-routes to the WSL Codex CLI fallback
  (`wsl bash -lc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex ...'`; liveness `codex --version`
  -> `codex-cli 0.135.0`). The Codex executing-plans review diffs against **BASELINE_SHA `292fff17`**.
  **Persist each Codex round's full RESPONSE** (verdicts + the final `NO_NEW_CRITICAL_MAJOR` line) to
  the gitignored `.copowers-findings.md` so the orchestrator can confirm convergence at QA
  (memory `feedback_implementer_persist_codex_responses`).
- **Degraded-harness caution (memory `feedback_degraded_harness_sequential_tool_calls`):** if you hit
  mid-batch tool cancellations, drop to single sequential tool calls + re-Read before each Edit +
  verify each commit landed — a corrupted read-state silently breaks Edits and produces broken
  commits / false-converged claims.
- **Windows gotchas:** ASCII-only in every printed/written string (the output writers assert
  `text.encode("cp1252")`); the PowerShell stdout test is `skipif(powershell.exe absent)`.

## Scope boundary (do NOT cross)

- **Stop after the harness is built + tests green + Codex-converged + the final-verification checklist
  is complete.** Do NOT perform the **operator smoke run** (plan final-verification last bullet:
  materialize VICR, pull Tiingo + SPY, `swing diagnose minervini-recall`, populate the study doc's
  Results/Interpretation/Conclusion) — that needs the live Tiingo archive + network and is the
  operator's post-merge gate. Leave the Task-18 study doc with its Results section as a documented
  placeholder for that run.
- The integration test (Task 16) is `slow` + needs the local Tiingo archive; run it if the archive is
  present, otherwise note it as deferred to the operator smoke run (do not fake the data).

## Deliverable / return report

All 18 tasks committed; the harness fast suite green; the repo fast suite green on the merged head
(report the real count); ruff clean; the findings file with every executing-plans Codex round's
verbatim response + final verdict. Return a report: tasks completed, harness test count, **merged-head
fast-suite count read live**, Codex rounds + final verdict, findings-file path, the
`git diff --stat 292fff17..HEAD -- swing/` output (must be only `swing/cli.py`), any plan
ambiguities or deviations you had to make, and confirmation the operator smoke run was left untouched.
