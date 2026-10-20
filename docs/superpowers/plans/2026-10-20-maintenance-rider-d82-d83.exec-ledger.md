# Maintenance rider (D82 + D83 + shadow 900 s) -- EXECUTING ledger

**Plan:** `docs/superpowers/plans/2026-10-20-maintenance-rider-d82-d83.plan.md` (cleared at `maint-rider` `f70640ed`).
**Plan ledger (rulings, intake, plan rounds):** `docs/superpowers/plans/2026-10-20-maintenance-rider-d82-d83.plan.ledger.md`.
**Brief:** `docs/maintenance-rider-d82-d83-exec-dispatch-brief.md` (main `e35bb1d6`).
**Cell:** `implementer-opus-high`. Worktree `.worktrees/maint-rider`, branch `maint-rider`, starting head `8a275a3a`.
**Why a separate file:** the executing record (clearances, task results, mutation checks, Reviewer A rounds) is kept apart from the plan ledger, so a reviewer can be handed the plan ledger's rulings without this cell's round history.
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\exec\`.

## Clearances (transcribed mechanically: front matter stripped, each line prefixed)

### CHARC -- author: CHARC; courier: orchestrator

From `comms/orchestrator/read/20261020T014312Z-charc-maint-rider-plan-charc-clears-al-10-reas.md` (posted 2026-10-20T01:43:12Z). The whole body, which carries items 1-8.

> CHARC PLAN-STAGE READ, maintenance rider plan @ maint-rider f70640ed (ledger 8a275a3a; request 20261020T014105Z). PRIMARY: CHARC on the form (F6-F12, the six D83 conditions, tripwires, the instrument). Read at this seat: the plan in full (327 lines); `ohlcv_archive.py:666` (`deduped = sorted({t.upper() for t in tickers})`); `ohlcv_cache.py:270-282` (the ladder-first read); `pattern_detection_events.py:116-156` (the selector's strict `<`); round 3's `transcript-r3.txt` (6,990 lines, `^ERROR` 0, `NO_NEW_CRITICAL_MAJOR` x2 at :6957/:6990, NEW token 0, footer 117,908 at :6959, `gpt-5.6-luna` / medium, `prompt-r3.md` carries zero line-initial verdict tokens, exit 0). Transcribe as block quotes with CHARC as author.
>
> GATE SENTENCE: CHARC CLEARS THE PLAN FOR EXECUTING, with the four words below (no change to the plan's tasks; two reasons restated, two rules for the merge report). None of the five tripwires: no schema, no module, no dependency, no standing process, nothing under `swing/data` or `swing/trades` (the OUT list and T6 step 2's empty-diff check hold it). The envelope is the ruled one plus the three widenings already ruled (the caller line, the three literal sites, the two docstring parentheticals) and one more I accept here: the `config.py:284` comment line (prose, no rename, no value).
>
> 1. AL-10, THE REASON RESTATED (my words were false by mechanism; the encoding stands). `warm_archives_batch` sorts and dedupes its input (`:666`), so the ORDER of `warm_set` has no effect on chunking, on cohorts, or on any write. The reason the base expression stays byte-identical and the open set is APPENDED is diff-locality and readability: the existing cohort's definition at `:1473` remains one unchanged line, the golden warm-scope tests keep reading as a prefix, and the change is ONE appended term a reviewer can see. That is a property of the DIFF, not of the warm. W2 stays as encoded, with one sentence in its docstring: "the warm sorts and dedupes this list itself (`ohlcv_archive.py:666`); the prefix shape pins the composition of the cohort, not an order the warm honours" -- so no one later "fixes" the warm to preserve an order nothing depends on. Intake I-2 was right.
>
> 2. AL-6 / AL-12: ACCEPT as planned. The reader's try precedes and is separate from the wholesale try; W3's in-wholesale-try mutant is the right kill. AL-7 (the inside-function import fixing the monkeypatch target) and AL-8 are correct; AL-9's three facts (asof written once at lease acquisition; detect's rows excluded by the strict `<`; observations written only later) are the facts that make the set at evaluate time THE set observe reads -- that is condition (i) at its true width, and I adopt the AL-9 paragraph as its statement.
>
> 3. AL-15: ACCEPT the declared limitation. The exemplar site (:2398) is held by the closure grep (zero `window_days=400` under `swing/`, code and comments) plus D4's value pin; a runtime pin there would need a seeded exemplar corpus for a one-token change. Not out of proportion to skip.
>
> 4. CONDITION (v), N-V: SATISFIED, as planned, on these terms. (v) asks for observation rows byte-equal with and without the warm, QUOTED. N-V asserts exactly that (assertion 1) on two worlds that run the REAL `warm_archives_batch`, the real archive write and the real observe read, with a fake download that honours `start`/`end` (so the archive's content is what the paths produce, not what the fixture hands them). Assertion 1 is an invariant pre and post -- it has to be; it pins a property, not a change -- and the T6 step 4 mutation (the BATCH path returns `close + 0.01`, assertion 1 goes red, revert) is what shows the pin has teeth: it fails the moment the warm's write path and observe's read disagree by a cent. Assertion 2 (zero single fetches in observe with the warm, one without) is the RED that proves the warm reached observe. Both quoted in the merge report, with the mutation. One rule: the mutation touches the batch (`list`) branch ONLY, as written, so the single path remains the reference the rows are compared against.
>
> 5. L-1, THE CONTEXT LINE: NOT STRUCK -- promoted to a rule. With the Schwab ladder installed, observe reads through the ladder and never touches the archive (`ohlcv_cache.py:270-282`), so on a ladder-ON night the F8 witness measures nothing about the warm. The merge report quotes the ladder state for each witnessed night; if the first post-merge night is ladder-ON, the report says the observe witness is INCONCLUSIVE for that night and the witness is taken on the first ladder-OFF night instead. Not a merge condition; a reading rule.
>
> 6. F8 witness: as defined, items (a)-(d), the baseline reproduced by w01 (216 / 229 / 1,300,128 ms / fetch_window 239). ACCEPT. Condition (vi) by the T6 step 3 mutation plus the empty `swing/data` diff: ACCEPT.
>
> 7. D82 half: AL-1..AL-5, N1/N1b/N2/N3 -- form read only (the bands are RD's): the derived display thresholds and the three-pin comparator are the mirror-family discipline done right; N3's fixture copied from the live manifest is the live-shape rule honoured. L-3 is true and correctly held by read; L-4's "band word is the authority" is the 21-B rule stated. No form objection. AL-16's literal 900 is right (a constant-equality pin is tautological).
>
> 8. Executing posture: `implementer-opus-high` is the orchestrator's call; I concur with the reason given (the warm writes the archive observe measures).
>
> OWNER DOCS: mine (`tool-director-context.md` D82/D83 rows, `charc-state.md`) close at the merge gate, not before.
>
> Nothing blocks. Dispatch on RD's clearance of the F5 encoding.

### RD -- author: RD; courier: orchestrator

From `comms/orchestrator/read/20261020T014211Z-rd-maint-rider-plan-rd-clears-the-f5-encodi.md` (posted 2026-10-20T01:42:11Z). The whole body, which carries the verdict and the L-3 and L-4 paragraphs.

> RD PLAN-STAGE READ, MAINTENANCE RIDER (orchestrator query 20261020T014105Z; plan f70640ed, 327 lines, read via `git show`). PRIMARY: RD on the F5 encoding and on L-3 / L-4. CHARC's items are CHARC's; no dissent to state.
>
> VERDICT: CLEARED. The F5 encoding is my ruling to the letter, and both limitations are accepted at the width stated. The clearance attaches to T1 as written at f70640ed (AL-1 through AL-5, the N1/N1b/N2/N3 pins, the three kept tests, the six superseded by name); a code-bearing change to T1 beyond that re-opens it.
>
> Verified at this seat:
> 1. AL-1: green iff `count * 20 <= us`, red iff `count * 10 > us`, else yellow; divisors named; the display thresholds DERIVED from the divisors (`100 / 20`, `100 / 10`), so the text cannot drift from the comparison. Matches my bands and the boundary table (76 green, 77 yellow, 153 yellow, 154 red at 1,535).
> 2. AL-2's lossless cast: `_is_nonneg_count` (:783-800) admits int or integer-valued finite float only, rejects bool/NaN/inf/negative/fractional -> `int(unique_signals)` cannot truncate. Confirmed by read.
> 3. `pct` is computed above the replaced block (`pct = 100.0 * count / unique_signals`) and is used for DISPLAY only; the comparison never touches it. Confirmed.
> 4. The pins: N1[77] is the rounding-mutant killer I required; N1b (10/100 -> yellow) kills `>=` on red, and the kept 5/100 test kills `<` on green, so both boundaries are inclusive on the side I ruled. N3 is the live manifest's funnel (71/1535 GREEN, "baseline" absent) -- the real emitter's shape, which is what the live-witness family demands.
> 5. The zero-signal, no-hypothesis and corrupt branches stay byte-identical; the 10/25 floors govern only the other two reasons (AL-5 rewrites the comment, values unchanged).
>
> L-3 -- ACCEPTED, and its width is exactly right. On this domain the integer form and the UNROUNDED float form are the same function, not merely untested apart: at a boundary `c*20 == u`, `100.0*c/u` is a correctly-rounded division of exact integers whose true quotient is 5.0, so it is exactly 5.0; there is no case to distinguish. The ruling's target was the ROUNDED comparison and the compare-the-display class; N1[77] and N1[154] kill those. The integer form is a single-rounding-authority discipline (the 22-A family), held by read; it is not a behaviour the suite can see because there is no behaviour to see. State it so in the merge report, not as "untested".
>
> L-4 -- ACCEPTED. Band word is the authority; the display never feeds the comparison (verified, item 3); the case needs >= 20,001 unique signals, thirteen times today's population. No change.
>
> MY OWNER DOCS at the rider's MERGE, not before: watch-standard :168-169 (#2 "baselined at 23" -> the rate rule) and rd-state.md:80 ("the stoplight cannot escalate it -- CALIBRATION B" -> retired). Both describe live code today and would be false for the interval.
>
> POST-MERGE READ (unchanged obligation): the live artifact's `excluded_reason_breakdown` detail after the first nightly on the merged code must read `invalid_ohlc=<n> (<x.xx>%, green; yellow above 5.00%, red above 10.00%)` with the band matching the integer rule on the manifest's own counts. I read it before anyone quotes "D82 green".
>
> Executing tier: `implementer-opus-high` over sonnet-high, concur -- condition (v) is a measurement-neutrality obligation on an archive observe reads, and that is where a wrong call is expensive.
>
> TRANSCRIPTION: block-quote into the plan ledger with RD as author; landed when the path is posted back.

## Brief additions carried (no task changes)

- W2's docstring carries CHARC item 1's sentence verbatim. AL-10's reason is diff-locality; any comment that cites a reason uses that one.
- Condition (v): the T6 step 4 mutation touches the batch (`list`) branch ONLY; both N-V assertions and the mutation result are quoted below.
- L-3 for the merge-report draft, as RD worded it: on this domain the integer form and the unrounded float form are the same function, so there is NO behaviour to test.
- L-1 is a reading rule (CHARC item 5), the orchestrator's at merge; kept in the merge-report checklist.

## Task results

Every RED and GREEN below is read off saved output in the evidence folder (file named per line). All runs from the worktree with `PYTHONPATH=.`, `-p no:cacheprovider`.

| task | commit | RED (saved output) | GREEN (saved output) |
|---|---|---|---|
| ledger | `521f7f22` | -- | -- |
| T1 (D82) | `b83a343b` | `t1-red.txt`: `5 failed, 25 passed, 123 deselected` -- N1[76], N1[154], N1b, N2, N3 FAIL; N1[77] and N1[153] pass (pre equals post), exactly as the plan tabulates | `t1-green.txt`: `tests/monitoring/` `337 passed, 1 skipped` |
| T2 (F14, I-1) | `98bc1582` | prose, no test | `tests/latches/test_criteria_lapse.py` `39 passed` (sanity) |
| T3 (shadow 900) | `17113d97` | `t3-red.txt`: `1 failed, 16 passed` (`assert 300 == 900`) | `t3-green.txt`: `17 passed` |
| T4 (F12, I-4) | `1d575229` | `t4-red.txt`: `4 failed` (D1-D4, each `AttributeError ... DETECT_OBSERVE_WINDOW_DAYS`) | `t4-green.txt`: `4 passed`; `t4-pipeline-dir.txt`: `tests/pipeline/` `434 passed` |
| T5 (D83) | `2fb1e31a` | `t5-red.txt`: `8 failed, 7 errors` -- W1, W2, W3 x2, W4, N-V `TypeError ... unexpected keyword argument 'lease'`; W5 `KeyError: 'lease'`; W6 no reader-failure entry (only the pin_injection warning); W7's seven tests error at setup (`AttributeError ... _open_detection_warm_tickers`) | `t5-green.txt`: `15 passed` |

**T5, one choice inside AL-12 (no task change):** the `log.warning` text is `open-detection cohort read failed (evaluate warm proceeds with base cohort): <Type>: <exc>`. A first GREEN prefixed it `evaluate warm:`, which collided with the cohort line's own prefix (W3's one-cohort-line assertion counted two). The run-warning `reason` is AL-12's text exactly.

## T6 gates (before Reviewer A)

- **Full fast suite** (`python -m pytest -m "not slow" -q -n auto -p no:cacheprovider`, head `2fb1e31a`), `t6-full-suite-pre-review.txt`: `15510 passed, 13 skipped, 1322 warnings in 886.27s (0:14:46)`, `exit=0`. No red.
- **Closure greps** (`t6-closure-greps.txt`), every one ZERO: `_INVALID_OHLC_BASELINE_COUNT`, `excess_pct`, `CALIBRATION B`, `baseline 23`, ``baselines `invalid_ohlc` ``, `23 of 77` (each `grep -rn --include=*.py ... swing/ tests/`); `grep -n "23 of 77" swing/latches/service.py`; `grep -rn --include=*.py "window_days=400" swing/`.
- **`git diff --stat 033d1053..HEAD -- swing/data swing/trades`:** EMPTY.
- **Ruff** (`t6-ruff.txt`): `ruff check swing/` -- All checks passed. The three NEW test files are clean. Three TOUCHED test files carry 34 violations, every one present at base `033d1053` (same codes, same sites; line numbers in `test_criteria_lapse.py` shifted by one): `test_criteria_lapse.py` 29 (28 N802 + 1 SIM300), `test_research_health_checks.py` 4 E702 (:2373-2379), `test_step_evaluate_warm.py` 1 I001. Zero introduced. **OPEN for the orchestrator** (see the return report): the brief's gate reads "ruff clean on the touched test files", and plan T2 step 2 says "Change nothing else in that docstring or file" for `test_criteria_lapse.py`.
- **Condition (vi) mutation** (`t6-mutation-vi.txt`, scratch): `threads=False` -> `threads=True` in `_yf_download_window` only; `test_new_ticker_triggers_full_history_fetch` and `test_single_success_records` BOTH red (`2 failed`; `helper did not pass threads=False to yf.download; got {... 'threads': True}`); reverted with `git checkout -- swing/data/ohlcv_archive.py`; `git diff --exit-code swing/data -> 0`; both pins `2 passed` after.
- **Condition (v) mutation** (`t6-mutation-v.txt`, scratch): N-V's fake, BATCH (`list`) branch ONLY, returns `Close + 0.01`; the single (`str`) branch untouched. Assertion (1) red: `At index 0 diff: (... "close": 14.5 ...) != (... "close": 14.51 ...)`, `1 failed`. Reverted with `git checkout`; `git diff --exit-code` on the file `-> 0`; N-V `1 passed` after.
- **Condition (v), N-V's two row sets** (merge-report item 4; `nv_rows_quote.py` -> `nv_rows_quote.out.txt`, calling `run_world` twice):
  - world A (no warm): 1 row `(1, '2026-06-10', '{"open": 14.0, "high": 15.0, "low": 13.0, "close": 14.5, "volume": 1004.0, "provider": "yfinance"}', 'triggered_open', 'entry_fired', 3)`; observe single-ticker downloads 1; calls `[('observe', 'str')]`.
  - world B (warm): the identical row; observe single-ticker downloads 0; calls `[('warm', 'list'), ('warm', 'list')]` (ROT's gap band and the benchmark's full refresh).
  - rows equal: True.
- **Trailers:** `git log 8a275a3a..HEAD --format='%(trailers)'` empty on all six commits; no `Co-Authored-By` anywhere in their bodies.

## Merge-report checklist additions carried from the clearances

- L-1 is a reading rule (CHARC item 5): quote the ladder state per witnessed night; a ladder-ON first post-merge night makes the observe witness INCONCLUSIVE for that night, and the witness is taken on the first ladder-OFF night.
- L-3 in RD's words: on this domain the integer form and the unrounded float form are the same function, so there is NO behaviour to test (not "untested").
- RD's post-merge read: the live `excluded_reason_breakdown` detail after the first nightly reads `invalid_ohlc=<n> (<x.xx>%, green; yellow above 5.00%, red above 10.00%)` with the band matching the integer rule on the manifest's own counts.

## Orchestrator rulings, cell 2 -- author: orchestrator

Transcribed from `docs/maintenance-rider-d82-d83-exec-continuation-brief-cell2.md` (main `2c50be4a`) section 1.

> RUFF GATE -- RULED (a). The gate reads "zero NEW findings on the touched files". `ruff check swing/` is clean, and so are the three new test files. The 34 findings in `test_criteria_lapse.py` (29), `test_research_health_checks.py` (4 E702) and `test_step_evaluate_warm.py` (1 I001) are all present at base `033d1053` at the same codes and sites (`exec/t6-ruff.txt`). They are not this rider's, and are not fixed here. `test_criteria_lapse.py`'s 28 N802 would be a rename sweep, which T2 step 2 forbids.

> STALE-BY-CONTRAST COMMENT -- FIX, comment only. `research_health.py:994` reads "the other two reasons keep their existing RAW-count pct thresholds (NOT baselined)". After T1 nothing is baselined, so the parenthetical contrasts with a rule that no longer exists. Replace the parenthetical so the comment says the other two reasons are judged by the `_EXCL_*_PCT` floors, and that invalid_ohlc is the rate rule above. Comment only; no code change. That keeps it inside CHARC's clearance, which re-opens only on a code-bearing change.

**Encoded (cell 2):** `28442bf0` replaces the two comment lines at `research_health.py:993-994` with "SCOPE LOCK: the other two reasons are judged by the _EXCL_*_PCT floors; invalid_ohlc is the rate rule above." Diff: 2 lines changed, both comments. `ruff check swing/` passed; `tests/monitoring/` `337 passed, 1 skipped` (`cell2-monitoring-28442bf0.txt`). Full fast suite on `28442bf0` (`python -m pytest -m "not slow" -q -n auto -p no:cacheprovider`), `cell2-full-suite-28442bf0.txt`: `15510 passed, 13 skipped, 1322 warnings in 816.35s (0:13:36)`, `exit=0`.

## Reviewer A (executing, `strong`)

Run by cell 2. Prompt built by `exec\build\build_prompt.py` from cell 1's `round1\prompt-head.md` (re-verified: the D83 conditions byte-equal to the register row, `docs/tool-director-context.md:147`, by `diff`; the envelope and AL list match plan lines 10-87 by read) plus both clearances (the block quotes above), the cell-2 rulings, and the plan ledger CUT before its `## Round ledger` heading. Runner `exec\build\run_round.sh` (LF, literal paths), Codex cwd = the worktree, `-p strong -s read-only --skip-git-repo-check`.

### Round ledger

The depth column is the orchestrator's (`scripts/cell_depth.py --agent <id>`); this cell leaves it empty.

| round | head reviewed | model / effort (banner = profile) | `^ERROR` | footer (`tokens used`) | verdict (model region) | crit / major / minor | NEW / REOPENED | reverts | depth |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `28442bf0` | `gpt-5.6-sol` / `high` (equal) | 0 | 219,461 | clean token x2, findings token 0 | 0 / 0 / 0 | 0 / 0 | 0 | |

**Round 1 evidence** (`exec\round1\`): `prompt-r1.md` 123,884 B (zero line-initial verdict tokens), `diff.txt` 66,421 B, `transcript-r1.txt` 869,329 B, `exit.txt` (`exit=0`, finished 16:44:34 after start 16:40:03; no live codex process after), `findings-r1.md`. No-prior-read grep over all Codex command blocks: 0 hits. One timestamp-prefixed `ERROR codex_core::session: failed to record rollout items` diagnostic sits after the verdict (:10232); it is not line-initial, so the anchored count stays 0. The reviewer could not run pytest from WSL (static read and closure searches only). Content filter: none.

**Loop status:** CONVERGED at round 1, the first clean verdict. No post-convergence minors. Spend (A rounds): 219,461 tokens.


## Reviewer B (charter section 2.9), run by the orchestrator on the tree being merged

- Tree: `maint-rider` `0ccce801`, whose production code is identical to `28442bf0` (Reviewer A's tree).
- Transcript: `C:/Users/rwsmy/swing-data/review-transcripts/maint-rider/exec/reviewer-b/b-review.txt`.
- Assertions: banner `gpt-5.6-sol` / `high`; `^ERROR` 0; footer 255,957; exit 0. `NO_NEW_CRITICAL_MAJOR` appears at :11113 and :11122, read from the model's region (the last `codex` marker is at :11106).
- The prompt carries zero verdict tokens. A's audit copies were moved out of the worktree for the run and then restored. B's commands contain no read of a ledger, of the transcripts tree, or of swing-data.
- Findings: 0 critical / 0 major / 1 minor.
  - **B-01, minor, [AGAINST-L-1].** On a Schwab-ladder-ON night the warm is NOT moot. After a Schwab fetch, `resolve_full_archive_bars` (runner.py:481-506) reaches `read_or_fetch_archive` through `_yf_window_fallback`, so the warm still removes the serial yfinance single. It does not remove the per-ticker Schwab call.
  - **Disposition:** ACCEPTED as a correction of L-1's REASON, with no code change.
  - **L-1, restated (orchestrator's words):** the warm removes the yfinance single but not the per-ticker Schwab call.
  - CHARC's item-5 reading rule is restated in its merge gate, quoted below.

**Outcome: CONVERGED at round 1.** Reviewer A was clean, and Reviewer B was clean with one minor, dispositioned.

## Merge clearances

RD (author), `20261020T025707Z`:

> RD MERGE CLEARANCE, MAINTENANCE RIDER (return report 20261020T025617Z). PRIMARY: RD on the D82 half (the F5 bands) and the measurement-integrity read. CHARC holds the gate on the form.
>
> GATE SENTENCE: RD CLEARS the maintenance rider for merge at maint-rider 0ccce801 (production code identical to the reviewed 28442bf0).
>
> Verified at this seat on the branch, via `git show` / `git grep maint-rider` (no cd):
> 1. The shipped block (research_health.py:976-991) IS the cleared plan block: `_INVALID_OHLC_GREEN_DIVISOR = 20`, `_INVALID_OHLC_RED_DIVISOR = 10`; `us = int(unique_signals)`; green iff `count * 20 <= us`; red iff `count * 10 > us`; the display thresholds DERIVED from the divisors; `pct` at 2 dp for display only.
> 2. The four pins exist with their arithmetic in the comments (test_research_health_checks.py:428-431: 76 green / 77 yellow / 153 yellow / 154 red at 1,535), the display pin reads `invalid_ohlc=77 (5.02%, yellow; ...)` (:466), the live-shape pin reads `invalid_ohlc=71 (4.63%, green; ...)` (:490), and the exactly-10% test exists (:446).
> 3. Closure greps on the branch, mine: `_INVALID_OHLC_BASELINE_COUNT`, `excess_pct`, `CALIBRATION B`, `baseline 23` -- zero hits each under swing/ and tests/.
> 4. `%(trailers)` empty across 033d1053..0ccce801.
> 5. The saved suite output `cell2-full-suite-28442bf0.txt` ends "15510 passed, 13 skipped, 0 failed, exit=0". Read, not quoted.
> 6. Condition (v), the measurement-integrity obligation on the archive observe reads: the quoted N-V rows are identical with and without the warm, and the batch-path mutation (close + 0.01) turned assertion (1) red and was reverted. That is the discriminator I wanted; the archive observe measures is not altered by the warm.
>
> B-01 (L-1's reason): CC, no ruling; the correction is right by read (`resolve_full_archive_bars` reaches the archive after a Schwab fetch), and it does not touch the D82 half. CHARC restates the reading rule.
>
> The ' aapl ' observation: noted, pre-existing, not dispositioned here; live tickers carry no whitespace. If the widening rider's selector ever ingests a hand-typed ticker, it becomes a strip-at-ingest item; not now.
>
> POST-MERGE, ON MY SEAT (unchanged): (a) read the live artifact's `excluded_reason_breakdown` detail after the first nightly on the merged code -- it must read `invalid_ohlc=<n> (<x.xx>%, <band>; yellow above 5.00%, red above 10.00%)` with the band matching the integer rule on the manifest's own counts, BEFORE anyone quotes "D82 green"; (b) my owner docs at the merge: watch-standard :168-169 (#2) and rd-state.md:80 (CALIBRATION B retired) -- I edit both once the merge commit exists on main.
>
> TRANSCRIPTION: block-quote into the exec ledger with RD as author; landed when the path is posted back.

CHARC (author), `20261020T025921Z`:

> CHARC MERGE GATE, maintenance rider (return 20261020T025617Z; RD's clearance 20261020T025707Z read). THIS SEAT HOLDS THE GATE: depth 309,021 at the read. PRIMARY: CHARC on the form, the six D83 conditions and the B-01 reading rule. Every item below was re-run or re-read here.
>
> GATE SENTENCE: CHARC CLEARS THE MAINTENANCE RIDER FOR MERGE at maint-rider 0ccce801, outcome CONVERGED at round 1 (Reviewer A 0/0/0 on 28442bf0; Reviewer B on the tree being merged, 0/0/1 minor, B-01 dispositioned below). `git merge --no-ff maint-rider`; the merged-head suite read before any "green on main"; the owner-doc edits; the merge report with the items in section 6 plus the two words below. Two conditions on the REPORT and the LEDGER, none on the merge.
>
> VERIFIED AT THIS SEAT:
> 1. Envelope: `--name-status 033d1053..maint-rider` = four `swing/` files M (config.py, latches/service.py, monitoring/research_health.py, pipeline/runner.py), four test files M, four new test files, three plan/ledger docs; `-- swing/data swing/trades scripts research` EMPTY; no migration, no module, no dependency. 21 commits, `%(trailers)` empty on each. `git diff --stat 28442bf0 0ccce801 -- swing/` EMPTY: the production tree B read is the tree A read.
> 2. Composition: `git log 033d1053..main -- swing/ tests/ scripts/` EMPTY; `git merge-tree --write-tree main maint-rider` = fbf2e0f6, clean.
> 3. The six conditions in the code (branch): (i) `_open_detection_warm_tickers` (:1461) calls `list_observable_detections(conn, source="pipeline", observation_date=lease_data_asof(cfg, lease))`, its own `connect`, `finally: conn.close()`, `return sorted({d.ticker.upper() ...})`; (ii) `DETECT_OBSERVE_WINDOW_DAYS = 400` (:1129) at all three sites (:2192, :2454, :3110), `window_days=400` ZERO under `swing/` (the one remaining hit is `tests/pipeline/test_detect_observe_window.py:5`, a docstring naming the grep -- outside the plan's `swing/` scope, not a literal in code); D1 reads the LIVE config; (iii) the reader's try is SEPARATE and BEFORE the wholesale try, `except Exception`, the #27 `evaluate_warm` entry, `n/a` fields, the warm proceeds with `base`; (iv) `open_det=%s open_det_added=%s` appended to the cohort line; (v) N-V present with the rows quoted (`close 14.5`), the batch-path mutation RED (`14.5` vs `14.51`) and reverted, `git diff --exit-code` 0; (vi) the `threads=True` mutation reds both pins, reverted, `swing/data` diff 0. `warm_set = [*base, *added]` (:1526), the caller passes `lease=lease` (:1654). `SHADOW_EXPECTANCY_TIMEOUT_S = 900`.
> 4. D82 half (form only; RD cleared the bands): `_INVALID_OHLC_GREEN_DIVISOR = 20` / `_RED_DIVISOR = 10`, `us = int(unique_signals)`, the integer cross-multiplication, the display derived from the constants at 2 dp; closure greps ZERO under `swing/` and `tests/` for `_INVALID_OHLC_BASELINE_COUNT`, `excess_pct`, `baseline 23`, `23 of 77`, `CALIBRATION B`; the `config.py:284` comment and the `latches/service.py:393-395` parenthetical landed as planned.
> 5. Every planned test exists by name on the branch: N1, N1b, N2, N3, D1-D4, W1-W4, W6, N-V (14 of 14 by `git grep "def <name>"`).
> 6. Transcripts: A `transcript-r1.txt` 10,243 lines, `^ERROR` 0, `NO_NEW_CRITICAL_MAJOR` x2, NEW 0, footer 219,461 at :10234, `gpt-5.6-sol`; `prompt-r1.md` carries zero LINE-INITIAL verdict tokens (its one mention at :77 is inside my own inlined plan-stage read, mid-line -- the instrument is clean, and that is why the anchored grep is line-initial). B `b-review.txt` 11,122 lines, `^ERROR` 0, `NO_NEW_CRITICAL_MAJOR` x2, NEW 0, footer 255,957 at :11115, `gpt-5.6-sol`; `prompt-head.md` zero tokens.
> 7. Suite: `cell2-full-suite-28442bf0.txt` ends `15510 passed, 13 skipped, 1322 warnings in 816.35s` / `exit=0`; the pre-review run `exit=0`.
>
> B-01 -- ACCEPTED as a correction of L-1's REASON, and MY ITEM-5 RULE RESTATED. Verified on main: the ladder's success path passes `yfinance_window_fn=_yf_window_fallback` (runner.py:481-506), and `_yf_window_fallback` (:433-439) reaches `read_or_fetch_archive`, the archive the warm fills. So on a ladder-ON night the warm still removes the serial yfinance single for a stale open-detection ticker; what it cannot remove is the per-ticker Schwab call. THE RULE: on a ladder-ON night, witness (a) -- `download_single` rows inside the observe step -- is INFORMATIVE and is quoted and read (expected near zero with the warm); witness (b) -- the observe step wall -- is INCONCLUSIVE for the warm, because the Schwab per-ticker term dominates it, and the wall witness moves to the first ladder-OFF night; (c) and (d) are read as before. The report quotes the ladder state per night as the count of `schwab_api_calls` rows for the run, beside (a) and (b), so the reader can tell which rule applied. L-1 is restated in the ledger in the orchestrator's words ("the warm removes the yfinance single but not the per-ticker Schwab call").
>
> TWO CONDITIONS ON THE REPORT / LEDGER:
> (1) THE OUTCOME WORD. The exec ledger's round ledger says "ENDED at round 1, the first clean verdict" (:133) and the word "converged" appears nowhere in it. The rule's vocabulary is CONVERGED (branch 1) or STOPPED-AND-ROUTED; the ledger and the merge report state "CONVERGED at round 1" in those words, with Reviewer B's record (0/0/1, B-01 accepted as a reason correction, no code change) appended to the ledger as a post-head doc commit before the report.
> (2) The F7 sentence verbatim and the F8 witness two nights with the B-01 rule applied, as section 6 already lists.
>
> NOTED, NOT RULED: B's observation that the selector returns tickers verbatim (no strip) -- pre-existing, schema-allowed, live data carries no whitespace; it belongs with D86's input-domain family if it ever bites, and the D86 row gets one clause at my next charter touch. The orchestrator's two gate rulings ((a) "zero NEW ruff findings" on touched test files with 28 pre-existing N802s; (b) the comment fix at research_health.py:993-994) are within its brief; no objection.
>
> OWNER DOCS: mine close at the merge report -- the D82 and D83 rows to their merged dispositions, `charc-state.md`. D89 opens as the next rider on the orchestrator's sequence, BEFORE the widening.
>
> Nothing else open on my seat.
