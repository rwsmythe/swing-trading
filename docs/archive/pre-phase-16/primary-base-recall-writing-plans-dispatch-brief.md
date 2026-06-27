# Dispatch brief — Minervini primary-base recall: writing-plans phase

**Phase:** `copowers:writing-plans` (wraps `superpowers:writing-plans` + adversarial Codex review to
convergence). **Predecessor:** the brainstorm spec, converged through 4 Codex rounds (0 crit / 13
major / 9 minor, all resolved). **Drafted:** 2026-06-09 (orchestrator).

## Your task

Turn the **approved + Codex-converged design spec** into a task-by-task implementation plan:

- **Spec (source of truth, READ FIRST, in full):**
  [`docs/superpowers/specs/2026-06-09-primary-base-recall-design.md`](superpowers/specs/2026-06-09-primary-base-recall-design.md)
  (commit `92230055`). Comprehensive; the §12 decisions table + the inline `R1/R2/R3/R4` tags mark
  what is settled. **Do not re-litigate settled decisions.** Findings transcript: gitignored
  `.copowers-findings.md`.

Run the full `copowers:writing-plans` flow: `superpowers:writing-plans`, write the plan doc, then the
adversarial Codex critic **to convergence** (zero new critical/major).

## Binding disciplines (the plan must honor + encode these)

- **Research carve-out:** all new code under `research/harness/minervini_primary_base_recall/`;
  **exactly ONE** `swing/cli.py` registration (`swing diagnose primary-base-recall`, mirror
  `minervini-recall`). No other `swing/` change. **No production DB** (screen is pure on bars).
- **L2 LOCK:** the harness imports none of yfinance / schwabdev / `swing.integrations.schwab` /
  `swing.data.ohlcv_archive`. Plan the L2 test — **use the HARDENED pattern: monkeypatch-restored
  `sys.modules`, NEVER raw `del sys.modules`** (per the 2026-06-09 xdist module-identity gotcha now in
  CLAUDE.md; reproduce isolation issues with `-n 0`, not `-n auto`).
- **Reuse (frozen leaves only):** `minervini_exemplar_recall.{ohlcv_reader, exemplar_reader, scorecard}`
  + `ControlAnchor`; `swing.patterns.foundation.{extract_zigzag_swings, Swing}`. **Do NOT reuse
  `sample_control_anchors`** — write the own pre-filtered young-window sampler (spec §4/§6, R2.M1).
- **TDD per task** with the **regression-arithmetic discipline** (`WRONG-PATH`/`RIGHT-PATH` values on
  every discriminating test — the spec §9 already enumerates them).
- **ASCII-only** output (cp1252 guard); **no `Co-Authored-By`**, no `--no-verify`, plain final `-m`
  paragraph; verify `git log -1 --format='%(trailers)'` empty after each commit.
- **Codex transport:** WSL CLI fallback (`wsl bash -lc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'`,
  liveness `codex --version` → `codex-cli 0.135.0`). **Persist every Codex round's full RESPONSE** (incl.
  the `NO_NEW_CRITICAL_MAJOR` line) to the gitignored findings file for orchestrator QA.

## Watch-items the plan must encode (the load-bearing spec mechanics)

- **n≈3 proof-of-concept** — cohort = {AMZN-1997, BODY, DKS} (evaluable sub-floor) + YHOO (sufficient-
  history positive control) + JNPR (reported `history`-excluded, below Minervini's ≥2mo minimum). The
  study's conclusion is explicitly "do the mechanics fire + is corpus expansion warranted (yes)."
  Raw fractions first; Wilson labeled mechanical at n≈3.
- **The screen (§5):** history gate (`MIN_HISTORY_BARS=40`); explicit swing→base algorithm via
  `extract_zigzag_swings` (base_high = highest swing-high pivot with a down-swing after; base_low =
  lowest Close in `[base_start,asof]`; **calendar→bar position mapping** — all duration/depth in
  *bars*, never `Swing.duration_days`); `MIN_BASE_BARS=15`; trading-week depth ladder (`≤25→0.25`,
  `26-200→0.35`, `>200→0.50`); **fresh-cross-not-recross emergence** (`close[asof-1]<=base_high<close[asof]`
  AND `max(close[base_start:asof-1])<=base_high`); **primary=first-base via the first-fire test**
  (replay criteria 1-5 over priors, reject `not_primary` if any earlier fired); fallbacks → `no_base`.
- **Timing:** window-sweep reliable for all; **day/exact** uses `[entry−60bd, entry+5bd]`,
  **month-precision** uses the **full documented month** `[first_trading_day_of_month−60bd,
  last_trading_day_of_month+5bd]`; single-session reported **day-precision only (BODY-only, n=1)`.
- **Precision:** the own young-window sampler (pre-filter `[39,503]` BEFORE sampling); single-session
  per-anchor fire rate is the PRIMARY estimand; window best-of reported separately, never conflated;
  manifest emits per-exemplar `eligible_control_count_before_sampling` + exact bar counts.

## Deliverable

A Codex-converged plan doc (`superpowers:writing-plans` default location) with ordered,
independently-testable tasks; the spec §11 deliverables (method-record stub
`research/method-records/minervini-primary-base-recall.md`, study-design doc
`research/studies/2026-06-09-minervini-primary-base-recall.md`) scheduled as tasks; the findings file
retained. **Stop at plan convergence** — do not begin executing-plans (the next dispatch).
