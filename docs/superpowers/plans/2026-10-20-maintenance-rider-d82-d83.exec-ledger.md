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

