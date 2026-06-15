# 18-D FIX 1 — check #1 finiteness baseline (dispatch brief)

**Audience:** a dispatched implementer (sub-agent via a `.claude/agents/implementer-*` cell), NO prior context.
**Phase:** copowers executing — a small, RD-decided LOGIC REFINEMENT on the already-converged 18-D monitor, into the EXISTING worktree. **RD-decided + operator-confirmed; it resolves RD's held merge-block.** Measurement-core (RD merge-blocking).
**Expected duration:** short (one function + a both-ways test + the review loop).

## §0 Read first
1. `docs/implementer-dispatch-recipe.md` — the protocol (worktree, TDD, the WSL-Codex loop, return-to-orchestrator). 2. The repo `CLAUDE.md` (gotchas). 3. `swing/monitoring/research_health.py` — `_check_temporal_log_finiteness` (the ONLY function you change; `observation_date` is already SELECTed in its query — verify on disk) + the plan Task 2 for context (`docs/superpowers/plans/2026-06-15-phase18-arc-d-research-health-monitor-plan.md`). 4. This brief.

## §0 Skill posture
TDD the change (failing both-ways test → minimal impl → pass → commit). Hand-run the WSL-Codex review at the **`review-strong`** tier to convergence; persist every round to `.copowers-findings.md`. The bounded-scope adjudication STILL applies (memory `feedback_schema_boundary_defensive_scope` / discipline #39): a finding premised SOLELY on a schema-prevented value is NOT a blocking major (adjudicate out-of-scope WITH the cited constraint). Return your report to the ORCHESTRATOR only — no mailbox.

## §1 The change (swing/monitoring/research_health.py ONLY — `_check_temporal_log_finiteness`)
- Add a **named module constant** = the finiteness baseline cutoff, on the **18-A writer-fix boundary**: `date(2026, 6, 13)` (the 18-A merge — any non-finite *written after* that barrier shipped is a genuine regression). Give it a clear name + a comment citing the 18-A boundary. **Ground/confirm against live data:** the full 1287-row scan shows ALL known non-finite is the single **2026-06-10** session, so the accepted set is exactly that cohort and any cutoff in `(06-10, 06-13]` isolates it.
- **#1 reds ONLY on non-finite obs whose `observation_date` is STRICTLY AFTER the cutoff** (`observation_date > cutoff`). A new non-finite past the barrier → **RED**, named distinctly in the detail.
- The accepted **`<= cutoff`** non-finite cohort is **SURFACED in the detail** (e.g. `accepted historical: N non-finite @ <=cutoff, withdrawn-backfill`) but does **NOT** drive red. With only `<= cutoff` non-finite present, #1 is **GREEN** (with the accepted-historical note in detail).
- Use the `observation_date` already selected in the query; parse it as a `date` for the comparison (mind the existing malformed-date handling — a malformed date stays in its existing path).

## §2 Scope / fence
- Touch **ONLY** `swing/monitoring/research_health.py` (the `_check_temporal_log_finiteness` red-logic + the new constant) + `tests/`. **NO** `swing/data`, NO schema, NO new dependency, **NO `__post_init__` change**.
- Leave the **other 6 checks** + the envelope + read-only + no-funnel-fork + transport (#7 detail-only) + the atomic `latest.json` write **UNCHANGED**.
- **No new tripwire → NO fresh CHARC pass** (this is a logic refinement on the already-sec-3-passed monitor; `0881ca42` already holds the CHARC C-pass).

## §3 Required distinguishing test (both-ways — `tests/`)
A single test (or pair) that distinguishes pre-fix from post-fix (memory `feedback_regression_test_arithmetic`):
- Seed a `<= cutoff` non-finite obs (the historical shape: `observation_date = 2026-06-10`, `close=NaN`) AND a `> cutoff` non-finite obs (`observation_date` after `2026-06-13`, `close=NaN`).
- **Post-fix assertions:** #1 status == **RED** (driven by the post-cutoff obs); the detail NAMES the post-cutoff obs as the red driver AND SURFACES the `<= cutoff` accepted-historical cohort (count). Remove the post-cutoff obs → with only the `<= cutoff` non-finite, #1 == **GREEN** + the accepted-historical detail note.
- **The discriminator:** the "`<= cutoff` non-finite alone → GREEN" assertion FAILS the pre-fix code (which reds on ANY non-finite) and PASSES post-fix. State the pre-fix vs post-fix value in the test docstring. (Volume-exempt + the empty/missing-table degradation paths stay as-is — do not regress them.)

## §4 Dispatch metadata
- **Worktree:** REUSE the EXISTING `.worktrees/phase18-arc-d-exec` (branch `phase18-arc-d-exec` @ **`0881ca42`**). Do NOT create a new worktree, do NOT use Agent isolation, do NOT rebase/unwind. Commit FIX 1 on top.
- **Review diff base = `0881ca42`** (review ONLY the FIX 1 change; the rest of 18-D already converged R1–R15 + holds the CHARC C-pass). Generate `git diff -U8 0881ca42..HEAD` for Codex.
- **Codex tier:** `review-strong`. Run to `NO_NEW_CRITICAL_MAJOR`. Do NOT run `codex exec review` / the codex-auto-review A/B (orchestrator-owned). Leave the worktree intact (orchestrator rebases + ff-merges).

## §5 Verification
- Run the FULL fast suite `python -m pytest -m "not slow" -q` to GREEN BEFORE the Codex review AND again on the final post-convergence HEAD (the no-false-green gate). `ruff check swing/` clean. Confirm the diff fence: only `swing/monitoring/research_health.py` + `tests/` touched.

## §6 Expected new state (so it's not a surprise)
Against the LIVE DB, #1 flips **RED→GREEN** on the baselined 103 (detail still lists them as accepted-historical). `#2 excluded_reason_breakdown` likely stays **YELLOW** on the ~30% invalid_ohlc rate (same 06-10 root cause; a self-healing RATE that dilutes as `unique_signals` grows) → **overall likely YELLOW, not green — which is HONEST.** A green overall is NOT expected and would be suspicious.

## §7 Return report (to the ORCHESTRATOR — final chat message; recipe §4)
The commit(s) (SHA + the change); the both-ways test (pre-fix vs post-fix arithmetic); the constant name + value + the live-data grounding (cite the scan); Codex `review-strong` rounds + verdict + `.copowers-findings.md` path; any bounded-scope out-of-scope adjudications WITH the cited constraint; final-head suite count + ruff; the fence stated honored-on-disk; deviations/flags.
