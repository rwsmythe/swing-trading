# Phase 22 arc D53 -- DBW anchor alignment -- Reviewer A ledger (executing)

Brief: `docs/phase22-arc-d53-dbw-anchor-alignment-dispatch-brief.md`. Branch `22-d53-exec`, base `6eee4f34`.
Rules read from the MAIN repo (`docs/implementer-dispatch-recipe.md`, `docs/harness-architecture.md` §5.1) at main SHA `6eee4f34c6b554711b20ed4118bf9bcb9783d181`.
Stage: executing (no plan loop, per brief). Tier: `strong`. Reviewer B is the orchestrator's and is not recorded here.

## Round table

| Round | Reviewed head | Crit | Major | Minor | New / reopened | Reverts | Verdict | Context depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|
| 1 | `75a608b3` | 0 | 0 | 3 | 3 new / 0 reopened | 0 | NO_NEW_CRITICAL_MAJOR (loop ends) | cell 268,914 at return of the m2/m3 leg (`cell_depth --live 4`, orchestrator-read); under the 400K cap throughout |

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


## Reviewer B (orchestrator's gate) -- recorded by the orchestrator

- Reviewed head `2968c933` (cold audit, repo read access, cwd = the worktree). Invocation:
  `MSYS_NO_PATHCONV=1 wsl.exe bash .../reviewer-b/run_b.sh` (`codex exec -p strong -s read-only`).
- Mechanical assertions: exit code MEASURED `0`; transcript 1,046,322 bytes; banner `gpt-5.6-sol` /
  reasoning effort `high`; `^ERROR` = 0; `^tokens used` = 1, value **252,113**; verdict token
  `^NEW_CRITICAL_MAJOR_FOUND` present (count 3, the 0.152.1 echo), `^NO_NEW_CRITICAL_MAJOR` = 0.
- Evidence: `~/swing-data/review-transcripts/22-d53-exec/reviewer-b/` -- `prompt-b.md`, `diff-b.txt`
  (`git diff 6eee4f34..2968c933`), `review-b.txt`, `exit-b.txt`, `run_b.sh`.
- Findings: **major #1** -- the runner treats `window.start_date` (= the trough-2 anchor under v1.1.0)
  as the pattern start at four sites (template slice `runner.py:2227-2237`, persisted
  `window_start_date` `runner.py:2722`, chart band `web/charts.py:1029`, review-confirm exemplar
  default `web/routes/patterns.py:523-545`). Confirmed in code by the orchestrator. Live-DB severity
  read (plain sqlite3 `mode=ro`): `template_match_score` NULL on all 1,563 `pattern_evaluations`
  for all five classes -- the template half is latent; the persisted column, chart band and
  exemplar-seeding default are live. **minor m2** -- the composition test helper passes the last bar
  date as `asof_date`, production passes the eval run's `action_session_date`. **minor m3** -- the
  test name `..._misaligned_with_trough_1_rejects` is a false normative claim (also A's minor 1).

## Director ruling on the B-gate -- CHARC is the ruling seat; the orchestrator is courier only

Literal block quote of CHARC's role-mail `20260914T180551Z-charc-ruling-d53-b-gate-c-split-merge-the-verd.md`
(thread `dbw-detector-silence`), body reproduced byte-for-byte from the delivered file:

> RULING (CHARC, the named ruler; RD CC holds and may dissent upward from this once LANDED).
> Courier: the orchestrator transcribes this as a BLOCK QUOTE into the 22-d53 ledger and posts
> the path; until then it is in flight.
>
> B major #1 CONFIRMED by my own read at main: runner.py slices the template series from
> window.start_date and persists it as window_start_date; web/charts.py bands from it;
> web/routes/patterns.py defaults a confirmed exemplar's start_date to it unless the operator
> chose pattern_present_outside_window. For a DBW row under v1.1.0 that start is trough 2.
>
> 1. BRANCH (c) -- SPLIT. Merge the verdict fix now. The defect D53 names (a detector that cannot
>    fire) is closed by the diff; the window-start composition is a SECOND defect the fix made
>    reachable, and widening the arc into runner.py at the B-gate is the unbounded-arc failure
>    the introduced-vs-banked rule exists to stop. CONTESTED PROVENANCE = INTRODUCED applies to
>    the DEFECT, so it is not banked-and-forgotten: it is COMMISSIONED as D53.1, its own brief,
>    dispatched off the merged main, sequenced by you against the riders/D32 queue.
>
> 2. WHY (c) IS SAFE ON THE MEASUREMENT SIDE (RD's lane -- state it so RD can refuse it):
>    structural_evidence_json on every DBW row carries prior_peak_date and trough_1_date, so
>    the true pattern start is RECOVERABLE from every interim row; window_start_date is a
>    framing field, not the sole record. Nothing emitted between the D53 merge and D53.1 is
>    lossy. The D53.1 ledger records the interim span (first v1.1.0 run id .. D53.1 merge run id)
>    so RD can re-derive or exclude it. RD rules whether that span needs any further marker.
>
> 3. THE INTERIM GUARD on the exemplar corpus: a process instruction to the operator (do not
>    CONFIRM a double_bottom_w row in review until D53.1 lands) -- and I say plainly this is
>    the guard class this project keeps losing, which is why D53.1's FIRST commit is the
>    structural one: the review confirm path derives a DBW exemplar's start_date from the
>    evidence (prior_peak/trough_1), never from window_start_date. Guard first, then the runner
>    seam (effective start for the template slice and the persisted window_start_date), then
>    the chart band. One verdict per class stays.
>
> 4. m2: in-envelope test-only fix in the cell -- source asof_date the way the runner does, or
>    narrow the helper's claim to what it does. Not a counted A round (minor scope; the suite
>    on the final head covers it).
> 5. m3: RENAME to ..._misaligned_with_both_troughs_rejects, its own commit. Section 3.3 pinned
>    the name to catch a FLIPPED ASSERTION, and the assertion is unchanged; the name is now a
>    false normative claim, which is the _is_head rule. Reviewer A raised it too.
> 6. A's banked minor (the false-green clipping test, pre-existing since f3c21073): register
>    row, mine; put file:line + mechanism in the return report and I bank it.
> 7. The 22-d53 ledger records B's verdict token, the three dispositions above, the interim
>    span, and D53.1's existence before merge. Merge --no-ff after the m2/m3 commits and the
>    suite on the final head; B does not re-run for minor-scope changes (the stopping rule).
>
> YOUR ASIDE WAS CORRECT and is landed: PRAGMA user_version reads 0 on this project's DBs (I
> verified: pragma 0, schema_version table 38). Brief 4bb2b049 section 4 step (2) and the
> inventory column now read SELECT version FROM schema_version (9e18b642). My premise was
> unverified; owned.
>
> -- CHARC

## Dispositions executed under the ruling

- **Major #1 -> branch (c):** NOT fixed in this arc. Commissioned as **D53.1**, brief
  `docs/phase22-arc-d53-1-dbw-effective-window-start-dispatch-brief.md` on main at `4a861560`
  (CHARC, 2026-09-14), dispatched off merged main carrying this arc. RD ruled its F2 packet
  2026-09-14 ("no further marker"); that ruling is transcribed into the D53.1 ledger.
- **m2 -> `42595f04`** (cell, test-only, authorized by orchestrator cell message after the ruling):
  helper renamed `_detect_as_runner` -> `_detect_with_stage_2_gate` and its docstring narrowed to
  what it passes; no test body or assertion changed.
- **m3 -> `5ec6f02b`** (cell, own commit): renamed to
  `test_dbw_zigzag_pivot_anchor_misaligned_with_both_troughs_rejects`; body unchanged; zero
  occurrences of the old name under `tests/` or `swing/` after. The brief's section 3.3 still names
  the old symbol -- it is the dispatch record, superseded by the ruling above, not edited.
- **A's banked minor 3 (false-green clipping test, `tests/patterns/test_double_bottom_w.py:573`,
  since `f3c21073`)** -> CHARC register row (CHARC's). Mechanism: the window is anchored on the last
  in-window bar 2026-03-09 (44 days from trough 1, 6 from trough 2), refused by alignment under both
  rules, so the zero envelope stamps every landmark at `window_end` and the three `<= window_end`
  assertions pass with or without clipping.
- **Stopping rule:** no Codex round for m2/m3 (minor scope); B does not re-run.
- **Final head suite (cell seat):** `5ec6f02b` -- `12324 passed, 13 skipped` (`-n 4`), ruff clean.

## Interim span (for D53.1 and RD)

v1.1.0 DBW rows persist `window_start_date` = trough 2 from the FIRST pipeline run executing the
merged main carrying this arc, until the first run executing D53.1's merge. Run ids are recorded when
known: first v1.1.0 run = TBD (expected the 2026-09-14 17:30 HST scheduled run, 176, if merged
before it); last interim run = the run before D53.1's first run. Per RD's F2 ruling, an interim row is
also self-identifying (`window.start_date == evidence.trough_2_date`).

## Tokens

Reviewer A 187,591 + Reviewer B 252,113 = **439,704** summed `tokens used` for this arc.
