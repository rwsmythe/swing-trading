# Data-Integrity Arc -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the data-integrity-arc writing-plans implementer. No prior conversation context.

**Mission:** Turn the LOCKed, Codex-converged brainstorm spec into an executing-plans-ready, TDD-task-decomposed implementation plan for the regular-session + completed-day data-integrity arc.

**Spec (AUTHORITATIVE for implementation):** `docs/superpowers/specs/2026-06-05-data-integrity-regular-session-completed-day-design.md` (465 lines; merged to main `d3c21e31`; Codex-converged R1[2crit+5maj]->R4 NO_NEW_CRITICAL_MAJOR). Execute its design verbatim; **re-grep every cited file:line at writing-plans STEP 0** (discipline #2). The spec is complete -- the §2 AUDIT spine, §4 ext-hours fix, §5 completed-day enforcement, §6 lock-guard, §7 topbar policy, §9 OhlcvBar/error taxonomy, §10 tests/gate, §12 slices, §13 OQs.

**Brief:** `docs/data-integrity-arc-writing-plans-dispatch-brief.md` (this file). Brainstorm dispatch: `docs/data-integrity-arc-brainstorming-dispatch-brief.md`.

**Context:** main HEAD at this dispatch: see §6 (branch from it). ~7130 fast tests green; schema v24 (this arc adds NO schema -- spec §11). The operator is doing PARALLEL Minervini research-branch work on main (untracked `research/`/`reference/` + a `.gitignore` mod) -- DISJOINT from this arc; do NOT touch it.

**Cumulative discipline (BINDING):** the **session-anchor read/write mismatch** family (Issue #5 is the instance); the **yfinance partial-bar strip** + **OHLCV-fetch-scope** + **F6 write-through-archive empty-result** rule (spec §14 -- the F6 vs filtered-union interaction is binding); the **Schwab camelCase signature-pin** (re-validate `needExtendedHoursData` on 3.0.5); the **append-only / lock-at-observation** invariant (L3); `feedback_verify_regression_test_arithmetic` (each value under BOTH the ext-hours/current-day AND regular-session/completed-day path). ZERO `Co-Authored-By`; ASCII.

**Skill posture:** `copowers:writing-plans`. **SINGLE Codex chain** to convergence (`NO_NEW_CRITICAL_MAJOR`; ~5-round cap suspended). **Codex transport (MCP DEAD):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'` (PATH prefix REQUIRED; `codex --version` -> codex-cli 0.135.0; prompt via STDIN `cat prompt.txt | codex exec -s read-only --skip-git-repo-check -`; pre-gen the diff on Windows; tell Codex NOT to run git; persist prompts+responses incl. `### Verdict` to `.copowers-findings.md`). Output: plan at `docs/superpowers/plans/2026-06-05-data-integrity-regular-session-completed-day-plan.md`.

---

## §1 LOCKed scope (spec §3 -- propagate, do NOT re-open)
- **L1** no ext-hours on ANY Schwab call (`price_history needExtendedHoursData=False` + `quotes` require `regularMarket*`, NO `lastPrice`/ext-hours bid/ask). **L2** completed-day only (discount the in-progress day; cutoff = `last_completed_session`). **L3** the lock is sacred (guard adds rejection, never re-fetch/regeneration). **L4** harden the existing date helpers, don't rebuild. **L5** Schwab L2 LOCK preserved (param on the existing endpoint; signature-pin). **L6** uniform `topbar_session_date(PageKind)` across an authoritative base-layout VM registry.

## §2 The 4 slices (spec §12 -- dependency order)
- **Slice A** -- ext-hours pull fix: `price_history needExtendedHoursData=False` + `needPreviousClose=False` + the signature-pin + the typed `SchwabBarConsistencyError` + the **mapper float-normalization** (round o/h/l/c to a sub-tick precision BEFORE `OhlcvBar`; the model stays strict -- spec §9.3, NO global epsilon). Highest value; kills the ~16% error rate.
- **Slice C** -- completed-day write-barrier + lock-guard + remediation (the keystone; DEPENDS on A): the `write_window` cutoff strip on the merged frame (the single chokepoint -- audit every archive write funnels through it); the `_bar_for_date` + `build_ohlc_today_json` **date-only** guards; the §5.4 pre-fix archive refetch-overwrite; the anchor regression tests. **The guard is date-only -- it does NOT validate ext-hours (the C2 boundary; include the guard-boundary proof-test).**
- **Slice B** -- quotes regular-session (after OQ-3 re-validation): require `regularMarket*`, drop-to-yfinance when absent.
- **Slice D** -- uniform topbar (parallelizable): `topbar_session_date` helper + a REQUIRED `PageKind` on the base-layout VM mixin (so a VM can't render without declaring it) + route every base-layout VM + the registry-parameterized cross-VM test (freeze `now` post-close so the 3 families diverge).

## §3 Operator-triage AT writing-plans (spec §13 -- pair these; resolutions LOCK into the plan)
- **OQ-1b** the §5.4 remediation mechanism (`get_or_fetch` freshness -- does the observe-path need a `force_refresh`/`min_asof` to overwrite a pre-fix contaminated archive row before `_bar_for_date` reads it?).
- **OQ-3** quote regular-session field availability (re-validate `regularMarketLastPrice`/`TradeTime` + regular bid/ask under the project's `fields=`; if regular bid/ask absent, widen `fields=` OR accept Schwab-quote->yfinance during ext-hours -- NO lastPrice fallback).
- **OQ-4** `SchwabBarConsistencyError` hierarchy placement (subclass `SchwabApiError` -> caught by the ladder's existing clause; confirm `_classify_schwab_error`).
- **OQ-5** Issue #3 (the `_count_open_at_run` metrics predicate bug; root cause pinned in spec §8) -- open the separate small metrics-fix brief now or bank.
- **OQ-7** accept already-LOCKED ext-hours observations as an L6-limitation (V1 forward-only; the lock is append-only).

## §4 Gate (spec §10) -- the binding pre-merge + post-merge gates
1. fast suite green on the MERGED HEAD (isolate the known xdist date-flakes per `feedback_no_false_green_claim`). 2. operator browser gate -- topbar consistency across pages (the §10.5 cross-VM test backs it). 3. **operator-witnessed LIVE Schwab re-fetch** (post-merge; like the schwabdev GATE-B): after Slice A, confirm on `/schwab/status` the `OhlcvBar invariant violated` rate collapses from ~16% toward ~0%, AND witness the UNSEEDED normal pipeline run (`feedback_seeded_gate_masks_default_state`). The brainstorm/writing-plans/executing do NOT run the live fetch against the operator's DB -- it is the operator's gate.

## §5 OUT OF SCOPE (spec §15)
Schwab Phase B/C; a date-system rewrite (L4); Issue #2/#4 (the polish batch); Issue #3's FIX (the `_count_open_at_run` predicate -- its own brief, OQ-5); historical re-locking of already-locked observations; intraday precision; schema provenance (it's an invariant, not data -- v24 holds).

## §6 Dispatch metadata
- **Subagent:** `general-purpose`, foreground, harness-default model. **Worktree:** branch `data-integrity-arc-writing-plans` from main HEAD = the commit that ADDS this brief (the orchestrator states the SHA in the inline prompt). `python -m swing.cli`; `cd <worktree> &&`; re-check `git branch --show-current` before each commit. NO live-DB touch (writing-plans writes a PLAN); you MAY read live tables `mode=ro` to ground anchors. SINGLE Codex chain to convergence.

## §7 Return report
Mirror prior writing-plans returns: final HEAD + commits; Codex convergent verdict (cite `.copowers-findings.md`); plan line/task count per slice; the slice dependency order (A->C; B after OQ-3; D parallel); the 5 OQ resolutions; L1-L6 verification; the schema verdict (NONE); the gate enumerated (incl. the live re-fetch); test-arithmetic per-axis; ZERO Co-Authored-By; worktree teardown; executing-plans dispatch-readiness.

---

*End of brief. Data-integrity writing-plans dispatch -- turn the merged 465-line spec into a 4-slice TDD plan (A ext-hours pull -> C write-barrier+lock-guard+remediation -> B quotes -> D uniform topbar), resolving OQ-1b/3/4/5/7 operator-paired. The lock-guard is date-only (the C2 boundary); the mapper normalizes floats (no global epsilon); NO schema. The binding gate is the operator-witnessed live Schwab re-fetch confirming the ~16% error rate collapses. OUTPUT: a plan executing-plans can drive to a shipped arc.*
