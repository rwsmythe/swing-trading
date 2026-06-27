# Dispatch brief — Minervini exemplar-recall: writing-plans phase

**Phase:** `copowers:writing-plans` (wraps `superpowers:writing-plans` + adversarial Codex review to
convergence). **Predecessor:** the brainstorm spec, converged through 3 Codex rounds.
**Drafted:** 2026-06-08 (orchestrator).

## Your task

Turn the **approved + Codex-converged design spec** into a task-by-task implementation plan:

- **Spec (source of truth, READ FIRST, in full):**
  [`docs/superpowers/specs/2026-06-08-minervini-exemplar-recall-design.md`](superpowers/specs/2026-06-08-minervini-exemplar-recall-design.md)
  (commit `8efb33ce`). It is comprehensive: 14 sections, all 9 operator decisions + every Codex
  round-1/2/3 resolution baked in. **Do not re-litigate settled decisions** (§14 table). Brainstorm
  findings transcript: gitignored `.copowers-findings.md`.

Run the full `copowers:writing-plans` flow: invoke `superpowers:writing-plans`, write the plan doc,
then run the adversarial Codex critic **to convergence** (zero new critical/major).

## Binding disciplines (project-wide; the plan must honor + encode these)

- **Research carve-out (V2.1 §IV.D/§VII.C):** all new code under
  `research/harness/minervini_exemplar_recall/` + the one-off `research/scripts/materialize_vicr_yfinance.py`;
  **exactly ONE** CLI registration in `swing/cli.py` (`swing diagnose minervini-recall`, mirror
  `aplus-sensitivity-v2`). No other `swing/` changes.
- **L2 LOCK:** the harness import graph imports NONE of yfinance / schwabdev /
  `swing.integrations.schwab` / `swing.data.ohlcv_archive`. The VICR materializer (which DOES import
  yfinance) lives outside the harness package + is never imported/shelled-from it. Plan a task for
  the L2 test (static grep + `sys.modules` import-smoke) — spec §11.
- **TDD per task:** failing test → see fail → minimal impl → see pass → commit. Each spec module in
  §3.1 maps naturally to one or a few tasks; sequence so leaf modules (`ohlcv_reader`, `rs_proxy`,
  `exemplar_reader`, `stage_db`) land before the cores (`screen_eval`, `detector_eval`), then
  `timing`/`control_cohort`/`scorecard`/`output`/`run`. `tiingo_pull` SPY extension + the VICR
  materializer are their own small tasks.
- **Regression-test-arithmetic discipline:** for each H1-taxonomy + RS-proxy + stage-DB test, the
  plan must specify values computed under BOTH the pre-fix and post-fix paths so the test genuinely
  distinguishes (memory `feedback_regression_test_arithmetic`).
- **Discriminating tests over byte-parity:** exercise the real derivation path; derive fixtures from
  real reader output (synthetic-fixture-vs-production shape-drift gotcha). Small real-Tiingo slices
  for a couple of exemplars + synthetic for edge cases.
- **Windows gotchas:** ASCII-only in every printed/written string (cp1252); add a
  subprocess-through-PowerShell stdout-encoding test for the CLI. No matplotlib mathtext metachars
  (no plots expected here; `qa_compare` handles plots separately).
- **Commits:** conventional (`feat(research):`, `test(research):`, etc.); **no `Co-Authored-By`
  footer, no `--no-verify`**; keep the final `-m` paragraph plain prose (trailer-parse hazard);
  verify `git log -1 --format='%(trailers)'` is empty before pushing.
- **Codex transport:** MCP `codex` tools are dead in the VS Code extension → the copowers chain
  auto-routes to the WSL Codex CLI fallback (`wsl bash -lc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex ...'`,
  liveness `codex --version` → `codex-cli 0.135.0`). **Persist each Codex round's full RESPONSE**
  (verdicts + the final `NO_NEW_CRITICAL_MAJOR` line), not just prompts, to a gitignored findings
  file so the orchestrator can independently confirm convergence at QA
  (memory `feedback_implementer_persist_codex_responses`).

## Watch-items the plan should make explicit (from the converged spec)

- **No production `--db`** — H1 is pure, equity = $7500 floor surrogate, stage is synthetic.
- **Two physically separate synthetic stage DBs** (faithful vs isolated), seeded via
  `insert_evaluation_run`/`insert_candidates` with minimal valid models + exactly 8 TT rows.
- **H2 selects `windows[-1]`** (production-faithful); `--h2-all-windows` is an off-by-default
  non-production diagnostic writing a separate file.
- **RS proxy P1 sets an EMPTY returns dict** (cannot fabricate `fallback_spy`); P0 requires
  `horizon_weeks*5+1` bars for exemplar AND SPY.
- **`SCREENABLE_FLOOR = 200 + rising_ma_period_days` (=221)**; the 200–220 band skips via
  TT3-unallowed-NA.
- **Wilson intervals primary** (screenable subset) + exploratory ticker-clustered bootstrap; control
  = same-ticker temporal-specificity contrast (NOT a base rate), run in both timing modes.
- **`h2_anchor_mode_limited_*`** flags for mapped cup/HTF misses.

## Deliverable

A plan doc (follow the `superpowers:writing-plans` default location — `docs/superpowers/plans/` or
`plans/`, matching repo precedent) with ordered, independently-testable tasks; Codex-converged; the
findings file retained for orchestrator QA. The plan should also schedule the spec §13 deliverables
(method-record stub, study-design doc) as tasks. **Stop at plan convergence** — do not begin
executing-plans (that is the next dispatch).
