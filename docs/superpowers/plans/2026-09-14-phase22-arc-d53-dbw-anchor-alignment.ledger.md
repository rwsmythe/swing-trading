# Phase 22 arc D53 -- DBW anchor alignment -- Reviewer A ledger (executing)

Brief: `docs/phase22-arc-d53-dbw-anchor-alignment-dispatch-brief.md`. Branch `22-d53-exec`, base `6eee4f34`.
Rules read from the MAIN repo (`docs/implementer-dispatch-recipe.md`, `docs/harness-architecture.md` §5.1) at main SHA `6eee4f34c6b554711b20ed4118bf9bcb9783d181`.
Stage: executing (no plan loop, per brief). Tier: `strong`. Reviewer B is the orchestrator's and is not recorded here.

## Round table

| Round | Reviewed head | Crit | Major | Minor | New / reopened | Reverts | Verdict | Context depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|
| 1 | `75a608b3` | 0 | 0 | 3 | 3 new / 0 reopened | 0 | NO_NEW_CRITICAL_MAJOR (loop ends) | |

## Round 1 -- mechanical assertions

- Invocation: `MSYS_NO_PATHCONV=1 wsl.exe bash <scratchpad>/loop/run_r1.sh` (runner: `cat prompt diff | codex exec -p strong -s read-only --skip-git-repo-check -`, cwd = the worktree, so Codex had repo read access). A first launch without `MSYS_NO_PATHCONV=1` was mangled by MSYS (`bash: C:/Program Files/Git/mnt/c/...: No such file or directory`, rc 127, empty transcript) -- not a round, not counted.
- Exit code MEASURED: `0` (written by the runner to `codex-exit-r1.txt`).
- Transcript non-empty: 895,927 bytes.
- Banner: `model: gpt-5.6-sol`, `reasoning effort: high`.
- `grep -c '^ERROR'` = 0.
- `grep -c '^tokens used'` = 1; value **187,591**.
- Verdict tokens: `^NO_NEW_CRITICAL_MAJOR` = 2 (codex-cli 0.152.1 emits the final message twice), `^NEW_CRITICAL_MAJOR_FOUND` = 0 -- exactly one distinct token.
- Process exited before the transcript was read (the background wrapper's `wsl rc=0` line was awaited).
- Scratch-in-input check: the review scratch lived in the session scratchpad, not the worktree; the prompt forbade reading `.codex*`/`.copowers*`; the only transcript command naming them was a `find ... -not -path './.codex*' -not -path './.copowers*'` exclusion (line 6887). No prior-round findings existed.
- Content filter: none reported by the reviewer; none observed.

## Round 1 -- evidence (four artifacts, durable copy)

`~/swing-data/review-transcripts/22-d53-exec/`:
- `codex-prompt-r1.md` (6,617 bytes)
- `codex-diff-r1.txt` (24,840 bytes; `git diff -U8 6eee4f34..75a608b3`)
- `codex-review-r1.txt` (895,927 bytes)
- `codex-exit-r1.txt` (2 bytes, `0`)
- `run_r1.sh` (804 bytes)
- this ledger (copied alongside)

## Round 1 -- findings and adjudication

Reviewer's own summary of the change: the predicate correctly implements the OR with the inclusive one-day boundary; no production-generated configuration found where a W lacking the anchor is selected; the new tests distinguish trough-1-only, no-alignment, trough-2-only and two-day-tolerance mutations; the composition helper calls the detector as the runner does; the version test compares against the real registry; runner idempotency, persistence, temporal metadata and composite clamping unaffected.

1. **minor** -- `tests/patterns/test_double_bottom_w.py:714`, the test NAME `test_dbw_zigzag_pivot_anchor_misaligned_with_trough_1_rejects` now overstates (an anchor on trough 2 is misaligned with trough 1 and scores). **Disposition: NOT renamed, flagged to the orchestrator.** The brief §3.3 names this test by its current name as one of the four that "stay green unchanged"; a rename would contradict the brief's roster. Its docstring was already rewritten in `75a608b3` to state "aligns with NEITHER trough_1 NOR trough_2". A rename is the orchestrator's call.
2. **minor** -- `tests/patterns/test_double_bottom_w.py:577`, the clipping test's docstring said "DBW's swing-LOW anchor for trough_1". **Disposition: FIXED (wording only, no re-round)** -- now "a would-be W trough". Post-convergence minor; verified by the final-head suite.
3. **minor** -- `tests/patterns/test_double_bottom_w.py:573`, `test_dbw_bar_clipping_future_bar_leak_rejected` is false-green: its anchor is the last in-window bar (2026-03-09), aligned with neither trough (deltas 44 and 6 days), so the zero envelope stamps every landmark at `window_end` and the assertions pass even with clipping removed. **Disposition: BANKED as PRE-EXISTING, not fixed.** Provenance: `git log -S "test_dbw_bar_clipping_future_bar_leak_rejected"` -> `f3c21073 2026-05-20 feat(phase13): double-bottom-W detector + undercut bonus (T-A.4.2)`; the arc's diff does not touch the test body; and the path is identical under both predicates (the anchor aligns with neither trough, so trough-1-only refused it too). Owner: orchestrator to route (CHARC, `swing/patterns/` test debt); trigger: any future DBW detector change or a patterns test-hygiene pass. Fix shape: anchor the window on a real trough (or use an `ma_crossover` window) so the slice runs over the clipped bars, and verify RED with the clip removed.

## Convergence

Loop ended at round 1 (first clean verdict). Summed `tokens used` across counted rounds: **187,591**.
