# D94 (a)+(b) EXECUTING ledger -- the latch validity prompt gate + the ledger-keyed cancel affordance

**Plan:** `docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.plan.md` (cleared at `fafb92ac`).
**Plan ledger:** `docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.plan.ledger.md`.
**Brief:** `docs/d94-latch-cancel-affordance-exec-dispatch-brief.md` (main `7b2dca9e`).
**Worktree / branch / diff base:** `.worktrees/d94-cancel`, `d94-cancel`, `8acea975`.
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\` (`tdd-evidence\`, `round<N>\`).

## 1. Rulings received during executing (verbatim, with authors)

### 1.1 Orchestrator -- the Task-3 misfit (T3.2 placement) and the C-1 naming. Author: the orchestrator.

Raised by this cell at the Task-3 boundary: T3.2's assertion (iii) (exactly one `latch-cancel-form`
for 5002) names the LEDGER-KEYED control, which Task 4 renders, so it could not be GREEN at the
Task-3 commit.

> T3.2 placement: OPTION A. T3.2 lands in Task 3 with assertions (i), (ii) and (iv). Assertion (iii), exactly one ledger-keyed `latch-cancel-form` for 5002, is ADDED to the same test function in the Task-4 commit, where the control is wired, and must be RED on the Task-3 tree. This is a test-SEQUENCING correction of the SS-1/SS-2 kind: no code, gate, envelope or assertion content changes, so it does not re-open the directors' clearance. The plan text stays as committed; this ruling and the ledger record the move.
> The naming deviation (`resting_order_ids` for the plan's `book_order_ids`, per CHARC C-1) is ACCEPTED. Use the same name for Task 3's `_displaced_cycle_prompts` keyword.

### 1.2 Round-1 rulings, FORM. Author: CHARC.

Posted 2026-10-26T04:16:55Z, from charc to orchestrator, thread d94, subject "D94 exec R1: CHARC
rules R1-1 = (i) book control stands; R1-2 = A skip stays" (main
`comms/orchestrator/read/20261026T041655Z-charc-d94-exec-r1-charc-rules-r1-1-i-book-cont.md`).
Verbatim, in full:

> CHARC RULINGS, D94 EXECUTING ROUND 1 (your query 20261026T041334Z). PRIMARY: CHARC on the FORM of R1-1 and R1-2; RD on their semantics (his packet governs where it speaks to the same item; mine is written so it can stand beside his). R1-3 and R1-4 are yours and FIX is right. Both rulings are on the D94 row at the commit named in the ping; block-quote from there into the exec ledger with CHARC as author.
>
> READ AT THIS SEAT on d94-cancel c9359ff7: latches.py:3273 (_accepted_row_gate), :3362-3462 (_validity_prompts: the strays/contested set-up, the per-latch loop, the skip `if join is None or join.indeterminate: continue` at :3441 AHEAD of both the displaced and current paths), :2639-2703 (book_controls `for row in attribution`); orders.py:153-166 (indeterminate_order_tickers: BUY orders whose broker status is indeterminate, the SINGLE SOURCE for suppression AND the banner), :831, :874; the test names T2.1-T4.7 at tests/web/test_routes/test_latches_d94_cancel_gate.py.
>
> R1-1 -- (i). G2 suppresses the TESTIMONY controls, never a control keyed on the broker's live book. My ruled text "NO correction control, NO cancel control" was written against the two controls the rider builds from the LEDGER: the correction control (testimony about acceptance) and the ledger-keyed cancel control (testimony about an order the book no longer shows). A fill is evidence that outranks testimony, so both are withdrawn on a fill-settled place. The shipped BOOK control is a different thing: its source is the broker saying, this render, that the order RESTS, and a fill does not retire a resting remainder or a stale status -- the operator can really cancel it, and the control is LOG-ONLY either way. Suppressing it (ii) would make a resting remainder uncancellable from the panel, a new absorbing state built by the fix. The G2 text is AMENDED on the register to: "the read-only fill line; NO correction control and NO LEDGER-keyed cancel control; a BOOK control for that order, if it still rests, stands as shipped." Codex read my words correctly; the words were too wide.
> FORM: no code change beyond the comment that states the two sources (the Task-5 sweep already names them); ONE new discriminator, RED first against an implementation that suppresses every cancel control: fill-cleared latch + accepted validity child on the latest place + the order STILL IN the book -> the fill line, exactly ONE cancel form (source book, no W2), no correction control, no ledger control. Declared limitation, with its reason: a stale FILLED order still reported as resting keeps a cancel control it should not have; the broker's status is what the (c) tier carries past to_resting_orders, and nothing in (a)+(b) can see it.
>
> R1-2 -- A. Keep the skip; declare it, with its reason, in the exec ledger and in a #31-true comment at the skip. The ticker-level indeterminate state is the UNKNOWN book at the resolution of one ticker: the broker has not said whether a BUY on that ticker rests, so "absent from the resting set" cannot be asserted, and G4/G5/G6 all turn on that assertion. Silence on an unknown is RD item 6's own asymmetry, and it is DISCLOSED silence, not a silent all-clear: indeterminate_order_tickers is the single source for both the suppression and the banner (orders.py:156-161), so the panel names the ticker it is not asking about. B is DECLINED on form: it moves code past the cleared plan (re-opening the clearance) and, worse, gives the ONE gate two call shapes -- lines evaluated before the skip, prompts after -- which is the two-spellings risk returning as two orderings. And it would render G5/G6 lines over a resting set the broker has just said is unreliable.
> Reachability, stated: an order the operator has just cancelled is itself indeterminate for a render, sits in the resting set, and gets the shipped book control; the hidden case is an accepted, absent, unexplained order on a ticker with SOME OTHER indeterminate BUY -- the explained line and the ledger control hide for that latch while the state lasts. Trigger to re-open as its own rider: a live instance that persists past one session. MEASUREMENT OWED, since the census ran on an empty book (the token is expired): the merge-gate witness reports the banner's indeterminate tickers that night; if any is a latched ticker with an accepted absent row, the orchestrator says so in the merge report and the row records it.
>
> SEQUENCE: a fresh cell applies (i), A's comment + ledger declaration, the one new test, R1-3, R1-4; round 2. No clearance is re-opened. The suite red you fixed on main (00d2d818, a wall-clock anchor) is outside the arc; the merged-head run reads it in.
>
> RD: your semantics on both; where you rule differently on R1-1's (i)/(ii) or R1-2's A/B, yours governs and I say so on the row.

### 1.3 Round-1 rulings, SEMANTICS (governs). Author: RD.

Posted 2026-10-26T04:17:52Z, from rd to orchestrator, thread d94, subject "D94 exec R1: RD rules
R1-1=(i) book control stands; R1-2=A, reason corrected" (main
`comms/orchestrator/read/20261026T041752Z-rd-d94-exec-r1-rd-rules-r1-1-i-book-control.md`).
Verbatim, in full:

> RD (swing-rd, twenty-first generation) RULES THE SEMANTICS OF D94 EXEC ROUND-1 MAJORS R1-1 AND R1-2 (orchestrator query 20261026T041334Z, thread d94). PRIMARY: RD on semantics; CHARC rules form. Read at this seat before ruling, all at d94-cancel c9359ff7 via `git show` (no cd): `_accepted_row_gate` (latches.py:3273-3311), `_validity_prompts` (:3362-3530, the skip at :3441), `_displaced_cycle_prompts` (:3077-3180), the two control sources (:2604-2690), `to_resting_orders` (orders.py:60-150), `indeterminate_order_tickers` (:153), `join_orders_to_latches` (:825-905), the status partition (constants.py:182-193), the exec ledger's round-1 table, CHARC's 20261022T093007Z form and 20261026T030256Z R0, my predecessor's 030426Z ruling and 031934Z clearance. Both findings are PRE-EXISTING mechanics the arc made visible, not introduced; neither re-opens the clearance.
>
> R1-1 -- (i). G2's "NO cancel control" means NO LEDGER-KEYED cancel control; the shipped BOOK control for an order still resting STANDS. DECLINE the finding as a defect; the plan text stands.
>   Reason 1 (what the ruled text was about): CHARC's R0 sentence was written on the OII shape -- an accepted order that FILLED and is NOT in the book. The cancel control the gate's own branch would otherwise emit on that row is the ledger-keyed one (G6); "NO cancel control" bounds the GATE'S output. The book control is sourced from `attribution`, the resting book, not from the gate; my item 3 ruled the gate's predicate a property of the ROW, and the book control is a property of a LIVE ORDER. Different sources, different questions.
>   Reason 2 (the standing family): recording and alarming are different functions, and the affordance to RECORD is never gated on the framework's state -- here, the latch's clear_reason. A resting remainder of a partial fill is a real order the operator can cancel at the broker; a cancel is an EVENT (item 5) and the ledger exists to record that he did it. Suppressing the book control because the latch cleared on a fill would re-create, on the fill branch, the exact defect D94 closes on the cancel branch: the detector gating the recorder.
>   Reason 3 (no double control): on this shape the gate returns EXPLAINED_FILL before the resting check, so NO ledger control is built, and T4.4 pins exactly one control for a resting accepted order. One order, one control, from the book. Verified in the code order of `_accepted_row_gate`.
>   ACCEPTED LIMITATION, declared with its reason (banked, pre-existing, Reviewer B invited to challenge): a STALE book status (an order the broker reports WORKING after it filled) renders a book cancel control beside the "filled" explained line. The book is the detector; its staleness is a data-quality fact the framework cannot see from inside one render (the stale-data asymmetry). The control records TESTIMONY ("I cancelled it"), it asserts nothing; an operator who did not cancel presses nothing. No wording change owed; the order list on the same fragment shows the status beside the control.
>
> R1-2 -- BRANCH A: keep the ticker-wide indeterminate skip as a DECLARED LIMITATION with the reason below. Branch B is REFUSED for this rider: it is a code change beyond the cleared plan that re-opens both clearances to close a window that is transient and already honestly disclosed.
>   CORRECTION TO THE ORCHESTRATOR'S REASON (the disposition is right; the reason is not): "an indeterminate ticker is the state in which absent cannot be asserted" is FALSE as stated. Under an indeterminate ticker the BOOK IS KNOWN -- `resolution.kind == "ok"`, the fetch succeeded -- and the indeterminate order is PRESENT in it with a known id; what is unknown is that one order's STATUS. Absence of a DIFFERENT id from a known book is as assertable there as on any other ticker. Item 6's UNKNOWN-book rule (SchwabApiError, no book at all) is a different state and does not transfer. Record the limitation on the true ground, or the next reviewer re-derives it correctly and re-opens.
>   THE TRUE GROUND FOR A, four parts:
>   (1) BOUNDED AND SELF-LIMITING. INDETERMINATE_ORDER_STATUSES (constants.py:188) = {AWAITING_MANUAL_REVIEW, PENDING_CANCEL, PENDING_RECALL, PENDING_REPLACE, UNKNOWN}: between-states statuses that resolve to RESTING or TERMINAL within minutes (PENDING_*), hours at worst (manual review), or on the next successful mapping (UNKNOWN). WAIT_TRG and every AWAITING_* condition status the operator's TRG BY chains sit in are RESTING (constants.py:182-187), so a conditional child order does NOT trigger the skip -- I checked this because if it had, A would have hidden the lines for the life of every chain order, and the ruling would be B. The next render after the status resolves shows every line and control; nothing is lost from the ledger, only deferred on screen.
>   (2) THE D94 USE CASE IS SERVED UNDER A. The order the operator has JUST cancelled is PENDING_CANCEL -> indeterminate -> kept by `to_resting_orders` -> in `resting_order_ids` -> G4 -> the shipped book control with its status note (:2645). The recording affordance exists at the moment he needs it. The suppressed set is strictly: a SECOND accepted-absent-unexplained order on the same ticker, or an explained LINE (read-only), while the first order is mid-transition. Two orders on one ticker with one in flight; zero measured incidence (unmeasurable tonight: token expired, empty book -- stated, not assumed).
>   (3) HONEST UNKNOWN, NOT SILENT ALL-CLEAR. The fragment renders the indeterminate note from the SAME predicate over the SAME order set as the suppression (`indeterminate_order_tickers`, orders.py:153-168; the single-source rule that module already states). A suppressed line is replaced by a visible "this ticker's book is in transition" -- the asymmetry is preserved in the right direction.
>   (4) PRE-EXISTING, OUTSIDE THE ARC'S DEFECT. The skip at :3441 and its docstring bullet predate D94; the arc added outputs behind an existing gate and did not move the gate. Under the introduced-vs-banked rule it is BANKED: file:line :3441, mechanism = ticker-wide skip before both cycle paths, reachability = any BUY order on the ticker in one of the five statuses.
>   RE-OPEN TRIGGER (named now so it is not re-litigated): a live render where an indeterminate status PERSISTS across a session boundary on a ticker carrying an accepted-absent-unexplained row (the AWAITING_MANUAL_REVIEW or UNKNOWN case) -- at that point the deferral is no longer bounded and B's form (lines + ledger controls before the skip, prompts still suppressed) is the fix, as its own rider. The (c) broker-history tier, which carries raw status past the boundary, is where this is cheapest.
>
> R1-3 / R1-4: the orchestrator's FIX rulings concur with my items (one spelling; #31). R1-4's corrected wording -- "a fill explains the place whatever its child says; a recorded cancel explains an accepted row whose order is gone" -- is exactly item 2 + item 3 and may be used verbatim.
>
> CHARC'S FORM PACKET 20261026T041655Z WAS READ BEFORE THIS POSTED (the re-list caught it). DISPOSITIONS IDENTICAL on both items: R1-1 = (i), R1-2 = A. His G2 register amendment ("NO correction control and NO LEDGER-keyed cancel control; a BOOK control for that order, if it still rests, stands as shipped") is the semantics above in his words; his one new RED-first discriminator (fill-cleared + accepted child + order STILL in the book -> fill line, exactly ONE cancel form from the book, no correction, no ledger control) is accepted; his two-orderings form argument against B is a second, independent reason and stands beside mine. ONE DIVERGENCE, OF REASON NOT OF RULING, and it is the semantics so this governs: his ground for A -- "the UNKNOWN book at the resolution of one ticker; absent cannot be asserted" -- is the orchestrator's reason and is the one corrected above. The book on an indeterminate ticker is FETCHED and KNOWN; the indeterminate order is listed with its id; only its STATUS is unresolved. The register records A on the four-part ground above (bounded + self-limiting; the use case served via G4; disclosed from the single source; pre-existing and banked), not on the unknown-book analogy -- a limitation recorded on an over-wide ground is re-derived by the next reviewer and re-opened. His MEASUREMENT OWED is adopted as part of my merge gate: the witness night's banner tickers are reported; any latched ticker carrying an accepted-absent row is named in the merge report. Nothing else differs; no dissent goes up.
>
> MERGE GATE unchanged: I read the merged tree ONCE after Reviewer B (final-head suite tail off the file, the live census row by row, T2.1 and T3.4 present and green, trailers empty), then the operator witness step by step. The fresh cell may apply these and run round 2.

### 1.4 The round-1 rulings as applied (cell 2; brief `docs/d94-latch-cancel-affordance-exec-continuation-brief-cell2.md`, main `58872c01`)

Both directors: identical dispositions; RD governs semantics. No clearance re-opened.

- **R1-1 = (i).** G2 withholds the TESTIMONY controls (the correction control and the LEDGER-keyed
  cancel control); the shipped BOOK cancel control for an order still resting stands. No code
  change beyond the comment naming the two control sources (at the book-control source in
  `build_latch_orders_vm`, and at the G2 gate kind). ONE new discriminator, T2.4, RED first
  against a build that suppresses every cancel control on a fill-cleared latch.
- **R1-2 = A.** The ticker-wide indeterminate skip stays, declared on RD's true ground (1.3, the
  four parts), in a #31-true comment AT the skip; the `_validity_prompts` docstring bullet that said
  "the broker's own answer is unknown" is corrected to point there.
- **R1-3 FIX.** `_governing_validity_child(place, intents)`, called from `_displaced_cycle_prompts`
  and `_accepted_row_gate`. No behaviour change.
- **R1-4 FIX.** RD's verbatim wording -- "a fill explains the place whatever its child says; a
  recorded cancel explains an accepted row whose order is gone" -- in the `validity_explained`
  field comment and the template block, and at the two further sites of the same class found by
  re-reading every `explain` mention in the VM (the gate block header; the `_explained_line`
  docstring).

## 1A. Declared limitations (round-1 rulings)

- **DL-1 (R1-1; RD's words).** "a STALE book status (an order the broker reports WORKING after it
  filled) renders a book cancel control beside the "filled" explained line. The book is the
  detector; its staleness is a data-quality fact the framework cannot see from inside one render
  (the stale-data asymmetry). The control records TESTIMONY ("I cancelled it"), it asserts
  nothing; an operator who did not cancel presses nothing. No wording change owed; the order list
  on the same fragment shows the status beside the control." Banked, pre-existing; Reviewer B
  invited to challenge.
- **DL-2 (R1-2 = A; RD's TRUE GROUND, not the orchestrator's corrected reason).** The skip
  `if join is None or join.indeterminate: continue` in `_validity_prompts` runs ahead of both cycle
  paths. Under an indeterminate ticker the BOOK IS KNOWN (`resolution.kind == "ok"`; the in-flight
  order is listed with its id); only that one order's STATUS is unresolved. Kept because:
  (1) bounded and self-limiting -- `INDETERMINATE_ORDER_STATUSES` (`swing/latches/constants.py:188`)
  = AWAITING_MANUAL_REVIEW, PENDING_CANCEL, PENDING_RECALL, PENDING_REPLACE, UNKNOWN; WAIT_TRG and
  every AWAITING_* condition status are RESTING (`:182-187`), so a conditional chain order does not
  trigger it; (2) the just-cancelled order is PENDING_CANCEL, so `to_resting_orders` keeps it
  (`swing/latches/orders.py`, "RESTING or INDETERMINATE"), it is in `resting_order_ids`, G4, and it
  gets the shipped book control with its status note; (3) an honest unknown -- the indeterminate
  note comes from `indeterminate_order_tickers` (`orders.py:153`), the same predicate over the same
  orders as `join.indeterminate` (`orders.py:874`); (4) pre-existing, so BANKED. **Re-open
  trigger:** an indeterminate status persisting across a session boundary on a ticker carrying an
  accepted, absent, unexplained row. Measurement owed (CHARC, adopted by RD): the merge-gate witness
  reports that night's banner indeterminate tickers.

## 2. Deviations from the plan text (each with its authority)

- **D-1 (naming, CHARC C-1; accepted in 1.1).** The gate's keyword and `_displaced_cycle_prompts`'
  keyword are `resting_order_ids` (the plan's code blocks say `book_order_ids`); the same set is
  exposed on `_ValidityRender.resting_order_ids` (C-2).
- **D-2 (test sequencing, ruling 1.1).** T3.2 (iii) lands in the Task-4 commit, RED on the Task-3
  tree.

## 3. Pre-review gates (Task 6), read off saved output

- **Full fast suite** (`-m "not slow" -q -n 8 -p no:cacheprovider`, head `0bda0385`):
  `1 failed, 15556 passed, 13 skipped` in 913.53 s. The one red is OUTSIDE this arc:
  `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py::test_ohlcv_cache_get_or_fetch_invariant`,
  `ValueError: No data for AAPL`. Mechanism: a WALL-CLOCK TIME BOMB. The fixture's bars are dated
  2026-04-01..03 and the cache cuts at `last_completed_session(now) - window_days(200)`
  (`swing/web/ohlcv_cache.py:282-283`), which has passed 2026-04-03 since the session of
  2026-10-21. Reproduced at `-n 0` on this worktree AND on `main` @ `7b2dca9e` (1 failed, both).
  No file of this arc touches `swing/web/ohlcv_cache.py` or `tests/pipeline/`. Not re-run.
- **Ruff:** `ruff check swing/` clean; zero findings on the two new test modules.
- **Envelope:** `git diff --stat 8acea975..HEAD -- swing/data swing/trades swing/web/routes scripts research`
  is EMPTY. The `swing/` files changed: `swing/latches/classification.py`,
  `swing/web/view_models/latches.py`, `swing/web/templates/partials/latch_orders.html.j2`.
- **Live census probe** (plain sqlite3 `mode=ro`, anchor 2026-10-26, derivation session
  2026-10-23, 14 latches, EMPTY book, worktree code): every row matches plan Task 6 step 3 --
  DFTX place 5 and IMNM place 6 the cancel lines (intents 11 and 10); OII place 1 the fill line
  (accepted 2026-08-10, filled 2026-08-17); IMNM place 7 the W1 correction for 1007804578712 plus
  ONE ledger control (source `ledger`, W2); IMNM place 12 and RHI place 4 first-answer absence
  prompts only; CADL nothing. Output: `exec\tdd-evidence\census-probe.txt`.
- **Mutations** (scratch, each reverted, `git diff --exit-code swing/` = 0 after each), all RED:
  M1 the shipped short-circuit (G2 falls through) -> T2.1; M2 latest-wins -> T3.4; M3 2B -> T3.2;
  M4 union without the resting check -> T4.4; M5 the VM re-spells the fill conjunction -> T2.3;
  M6 W1 dropped -> T3.3. Output: `exec\tdd-evidence\mutations.txt`.

## 3A. The round-1 rulings applied, and the gates re-run (cell 2), read off saved output

Evidence: `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\cell2\`.

- **Commits** (pathspec-only, `%(trailers)` empty each): `67f793b8` R1-1 (T2.4 + the two-source
  comment), `5de18347` R1-2 (the comment at the skip + the docstring bullet), `40790a6b` R1-3
  (`_governing_validity_child`), `36e3d670` R1-4 (the explained-line comments). Ledger:
  `0c9f743b` landed sections 1.2-1.4 and 1A only -- its message also names "the cell-2 gates",
  which a failed edit script did not write; this section lands in the commit after it. Recorded,
  not rewritten (no amend).
- **T2.4 RED first** (`t2_4-mutant-RED.txt`), against a scratch build whose book-control
  comprehension also drops every attribution row whose latch has `clear_reason == "fill"`
  (`mutant-R1-1.diff`; reverted, `git diff --exit-code swing/` = 0):
  `assert [f["actual_broker_order_id"] for f in forms] == ["5001"]` ->
  `AssertionError: assert [] == ['5001']`, `1 failed`. GREEN on the shipped code
  (`t2_4-shipped.txt`): `1 passed`. The fill-line assertion ahead of it passed on the mutant, so
  the RED is the control count, not the setup.
- **R1-3** (`r1-3-targeted.txt`): the D94 file, the validity-prompt file and `tests/latches/` at
  `-n 8`: `602 passed`.
- **Full fast suite** (`-m "not slow" -q -n 8 -p no:cacheprovider`, head `36e3d670`,
  `full-suite.txt`): `1 failed, 15557 passed, 13 skipped` in 899.40 s. The one red is the KNOWN
  out-of-arc wall-clock anchor,
  `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py::test_ohlcv_cache_get_or_fetch_invariant`,
  `ValueError: No data for AAPL` (section 3's mechanism; fixed on main at `00d2d818`, test-only;
  NOT fixed on this branch; the merged-head run reads it in). 15557 = cell 1's 15556 + T2.4.
- **Ruff:** `ruff check swing/` clean; zero findings on the two arc test modules.
- **Envelope:** `git diff --stat 8acea975..HEAD -- swing/data swing/trades swing/web/routes scripts research`
  EMPTY. The `swing/` files changed are unchanged in set: `swing/latches/classification.py`,
  `swing/web/view_models/latches.py`, `swing/web/templates/partials/latch_orders.html.j2`.
- **Noted, not changed (outside the ruling's scope):** a grep of `swing/` for
  `validated_place_intent_id ==` (a token grep; it bounds the family from below) finds the
  governing-child selection also spelled in `swing/latches/classification.py:577`,
  `swing/cli_latches.py:467` and `swing/trades/latched_origin.py:1476,1702`. R1-3 named the two VM
  sites; the others are the resolver, the CLI report and `swing/trades`, all outside this rider's
  edit set.

## 4. Reviewer A round table

| round | tier / model / effort (banner) | footer | verdict token | `^ERROR` | crit | major | minor | new / reopened | reverts | tokens used | context depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | strong / `gpt-5.6-sol` / `high` (equal to `~/.codex/strong.config.toml`) | present | the findings token, 2 anchored (double emission); the clean token 0 | 0 | 0 | 2 | 2 | 4 new / 0 reopened | 0 | 287,340 | |
| 2 | strong / `gpt-5.6-sol` / `high` (equal to `~/.codex/strong.config.toml`) | present | the clean token, 2 anchored (double emission); the findings token 0 | 0 | 0 | 0 | 2 | 2 new / 0 reopened | 0 | 273,468 | |

### Round 1

**Invocation.** `wsl.exe bash -lc 'bash .../exec/run_round.sh 1'` (LF runner, checked with `file`).
cwd = the worktree (repo read access, `-s read-only --skip-git-repo-check`); stdin = the prompt,
the plan-ledger CUT (sections 0-5, lines 1-306) and `git diff -U8 8acea975..HEAD -- swing tests`
(generated on Windows). codex-cli 0.162.1. Output and exit files pre-created Windows-side.

**Assertions** (`exec\round1\assertions-r1.txt`): exit code MEASURED 0; transcript 1,269,903 bytes;
`model: gpt-5.6-sol` = the profile's `model`; `reasoning effort: high` = the profile's; `^ERROR` 0;
`^tokens used` 1 (287,340); the findings token anchored 2, the clean token 0; no codex process
left. Prompt grep for either token line-initially: 0. Scratch/ledger reach: the transcript's hits
for `.codex|copowers|ledger.md|review-transcripts` are the prompt echo, the ledger-cut echo and
`CLAUDE.md` / `docs/orchestrator-context.md` prose only; no ledger or prior-output file was read.
Content filter: none ("not a safety-layer refusal or rewrite"). Codex could not run pytest
(no interpreter in WSL); it AST-parsed the four Python files.

**Checklist:** 9 HOLDS, item 2 FAILS (on findings R1-2 and R1-3 below).

**Findings and proposed dispositions** (the orchestrator rules; nothing is fixed yet):

| id | sev | finding | proposed disposition |
|---|---|---|---|
| R1-1 | major | On a fill-cleared latch (G2) whose accepted order STILL rests (a partial-fill remainder, or a stale WORKING/indeterminate status), the fill line renders AND the shipped BOOK cancel control for that order renders; G2 says "no cancel control". | DECLINE, cited. The book source is shipped and unchanged by ruling: CHARC 1.2 (b) "the union of attribution and the unexplained accepted rows" and "the existing resting-book cancel controls unchanged (the union keeps them)"; plan Task 4 step 3 "book_controls is the shipped ... comprehension, unchanged"; T4.4 pins exactly one control for a resting accepted order. G2's "NO cancel control" is the gate's own output (no LEDGER control). A resting remainder is a real, cancellable order, so suppressing its book control would gate the RECORD affordance on the fill -- RD's recording-vs-detecting principle. Changing the book source is outside the plan: a director question if wanted. |
| R1-2 | major | `join.indeterminate` is TICKER-wide (`orders.py:874`); `_validity_prompts` `continue`s before both the displaced and current paths, so one indeterminate same-ticker BUY order suppresses the explained lines AND the ledger-keyed control for an accepted, absent, unexplained order on that latch. | FORK -- route; not mine to choose. The skip is SHIPPED, pre-arc (docstring bullet "the ticker's broker status is not INDETERMINATE ... no prompt"), and plan section 1 is silent on it. Branch A: keep it, declare an accepted limitation (the broker's own answer on that ticker is unknown, the same asymmetry as RD item 6's UNKNOWN book; the order the operator just cancelled is itself indeterminate and so in `B`, i.e. G4, with the shipped book control and its status note). Branch B: run the gate (lines + ledger controls only, prompts still suppressed) before the indeterminate skip -- a code change beyond the plan, re-opening the clearance. Live incidence not measurable here (Schwab token expired; the census probe ran on an empty book). |
| R1-3 | minor | The governing-child selection is spelled twice: `_displaced_cycle_prompts` (`answered = max(children, key=_order_key)`) and `_accepted_row_gate`. | FIX (no behaviour change): one helper `_governing_validity_child(place, intents)` called by both. |
| R1-4 | minor | Comments (`LatchOrdersFragmentVM.validity_explained`, the template block) say an explained line is for an "accepted row whose absence" is explained; G2 fires for ANY validity child, before the accepted / book checks. | FIX the wording (#31): a fill explains the place whatever its child says; a recorded cancel explains an accepted row whose order is gone. |

**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\round1\`:
`codex-review-r1.txt` (1,269,903 bytes), `prompt-r1.md` (9,910), `ledger-cut-r1.md` (38,848),
`diff-r1.txt` (80,652), `codex-exit-r1.txt`, `assertions-r1.txt`, `run_round.sh`, `assert_round.sh`.

### Round 2

**Run by cell 2, after the round-1 rulings (sections 1.2-1.4, 1A, 3A).** Reviewed head
`73487552`; diff `git diff -U8 8acea975..HEAD -- swing tests` generated on Windows.

**Invocation.** `wsl.exe bash -lc 'bash .../exec/round2/run_round.sh 2'` (LF runner, checked with
`file`). cwd = the worktree (repo read access, `-s read-only --skip-git-repo-check`); stdin = the
prompt, the plan-ledger CUT (sections 0-5, lines 1-306, byte-identical to round 1's cut), the
exec-ledger CUT (sections 1-3A, everything before section 4) and the diff. codex-cli 0.162.1. The
output and exit files were pre-created Windows-side. The prompt inlines the round-1 rulings, the
amended G2 row, DL-1 and DL-2, and adds checklist items 11-13 (R1-1, R1-2, R1-3/R1-4 as applied,
challenge invited on the first two).

**Assertions** (`exec\round2\assertions-r2.txt`): exit code MEASURED 0; transcript 1,134,094 bytes;
`model: gpt-5.6-sol` = the profile's `model`; `reasoning effort: high` = the profile's; `^ERROR` 0;
`^tokens used` 1 (273,468); the clean token anchored 2 (double emission), the findings token 0; no
codex process left. Prompt and both cuts grepped for either token anywhere: 0. Scratch/ledger
reach: the transcript's hits for `.codex|copowers|ledger.md|review-transcripts` are the prompt
echo, the two ledger-cut echoes, and `CLAUDE.md` / `docs/orchestrator-context.md` prose read by
its own `sed`/`cat` commands; no command read a ledger, a `.codex*`/`.copowers*` file or the
transcripts directory. No `.codex*` / `.copowers*` file existed in the worktree for the loop (the
working copies live in the evidence directory). Content filter: none ("No safety layer refused or
rewrote the review"). One line after the verdict,
`2026-10-26T04:46:40Z ERROR codex_core::session: failed to record rollout items`, is
timestamp-prefixed, so not line-initial; the anchored assertion reads 0 and the response was
complete before it. Codex could not run pytest (no project environment in WSL); it AST-parsed the
changed Python files.

**Checklist:** items 1-12 HOLD; item 11 AGREES with R1-1 (i) on the merits ("removing the book
control would make a genuinely resting remainder unavailable for cancellation"); item 12 AGREES
with keeping A ("the comment accurately describes the current skip ... without promising future
behavior"); item 13 FAILS on R2-1 and R2-2 only, both comment-only.

**Verdict: the clean token. The loop ENDS at round 2** (recipe section 3: post-convergence minors
are corrected without another round).

**Findings and proposed dispositions** (the orchestrator rules; nothing is fixed yet):

| id | sev | finding | proposed disposition |
|---|---|---|---|
| R2-1 | minor | `_accepted_row_gate` docstring: "so a displaced cycle is explained by a cancel row or not at all" is over-wide. After place -> accepted child -> later decline the place is displaced but still the latch's LATEST place, so a qualifying fill makes `fill_vouches_for` true and renders G2's fill line (I-4). The code is right; `_displaced_cycle_prompts`' docstring already says "while a later place exists". | FIX, comment-only, no new round: qualify the sentence with "while a later place exists". |
| R2-2 | minor | `_explained_line` docstring: "Every date is the validity row's `action_session_date`" is false. Only the accepted date is; the fill date is `latch.clear_session` and the cancel date is `gate.cancel.action_session_date`. The rendered W3 line is right. | FIX, comment-only, no new round: say the ACCEPTED date is the validity row's `action_session_date`, the fill date the latch's `clear_session`, the cancel date the cancel row's. |

**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\round2\`:
`codex-review-r2.txt` (1,134,094 bytes), `prompt-r2.md` (13,889), `plan-ledger-cut-r2.md` (38,848),
`exec-ledger-cut-r2.md` (24,844), `diff-r2.txt` (87,817), `codex-exit-r2.txt`, `assertions-r2.txt`,
`copowers-findings.md` (the verbatim response plus this adjudication), `head-r2.txt`,
`run_round.sh`, `assert_round.sh`.

**Spend (Reviewer A, executing):** round 1 287,340 + round 2 273,468 = **560,808** tokens.
