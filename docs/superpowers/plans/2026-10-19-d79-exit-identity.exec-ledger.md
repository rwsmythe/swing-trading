# D79 exit identity -- EXECUTING ledger

Plan: `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md` (531 lines, cleared at `618d7b04`). Rulings for the plan stage live in the plan ledger beside this file; this ledger holds the executing record only. Brief: `docs/d79-exec-dispatch-brief.md` (main `6aef92a4`).

## Cell 1 (implementer-opus-high, agent `adab4bc099f5442db`)

Returned at a FORK before T6, not at a round gate. No counted review round has run.

| Commit | Task | Note |
|---|---|---|
| `1b470e99` | T1 | `record_exit` owns one BEGIN IMMEDIATE; `CallerHeldTransactionError`; `_rollback_or_raise` in the D73 shape (`swing/trades/exit.py:337-347`) |
| `62cbcc1d` | T2 | `recorded_exit_identities`; `ExitEnvelopeUnreadableError` before BEGIN, `ExitOrderAlreadyRecordedError` under the lock; `derives_from` lands early in `exit_auto_fill` |
| `bb26bfad` | T3 | global offer-list exclusion through the one reader |
| `4b12f8f3` | T4 | flag vocabulary, K7.2 possible partials, ASCII templates, `anonymous_fill_matches`; 4 tests superseded (named in the commit body) |
| `417b4674` | T5 | single-candidate shape stamps `selected_*`; 2 tests superseded (named in the commit body) |

- Baseline fast suite on the untouched base: 15380 passed, 13 skipped, 0 failed (709.96 s). The full suite has NOT been re-run after T5.
- Left untracked on disk: `tests/cli/test_d79_cli_exit_confirm.py` (the T8 tests, red until T8 lands).
- Depth at return: **457,214, over the 400K cap.** Cell 1 is not resumed; a fresh cell continues off the commits above.

**Orchestrator QA (against disk, `417b4674`):** `%(trailers)` empty on all five commits; `git diff --diff-filter=A 618d7b04..HEAD -- swing/` empty (no added file); the diff under `swing/` touches only `trades/exit.py`, `trades/exit_auto_fill.py`, `web/routes/trades.py`, the exit form template and `web/view_models/trades.py`; the D73 branch is present at `exit.py:337-347`. Fork 1's facts verified: `test_exit_rerender_anchor.py` asserts `"exceeds"` at :242 (unclaimed), :315, :401 and :459 (claimed, through `_refused` at :291-300 with shares=50, or shares=9 at :399).

**Encodings cell 1 made without a fork (accepted; Reviewer A's prompt carries each, challenge invited):**
1. The K7.2 window is bounded by canonical dates only; an entered date that is not a calendar date shrinks the window to the execution day; bounds sorted low-to-high. (Fail direction: fewer possible-partial flags.)
2. A map duplicate entry with no `reason` key reads as `value_tuple_match` (its only historical meaning) and flags; a present-but-unknown reason is ignored.
3. All flag text passes through `ascii_safe` before the `ExitRecordFlag` is built (typed date and map entries are client-supplied).
4. `derives_from` also catches `OverflowError` (an infinite map quantity no longer 500s).

## Executing forks

### FORK 1 -- flag-before-record vs T7-k (RULED: CHARC, A1, the helper PURE)

Once F1 is a flag, a claimed POST whose typed values do not derive from the selected entry is answered "Confirm or retype before recording" before `record_exit` runs, so an over-size `shares` never reaches the service's "exceeds" refusal. T7-k says `test_exit_rerender_anchor.py` stays green unchanged; three of its tests (:315, :401, :459) assert "exceeds" on such a POST.
- **A1:** one read-only precondition helper in `exit.py` (trade found, active, shares within `current_size`, the pure argument checks), called by `record_exit` inside the lock and by the route before flags; a refusal takes the existing `ValueError` re-render with no flags. Widens CHARC K1 (1)-(3) by one public read-only symbol.
- **A2:** the same skip as a route-side predicate over `get_trade`; no `exit.py` change; a second spelling of the predicate.
- **B:** amend T7-k; the three tests are superseded and reach the refusal through the confirm path (two round trips; the parity test needs an unclaimed path).

Cell lean: A1. Orchestrator recommendation: A1. Routed to CHARC (the K1 carve-out is CHARC's ruling).

**CHARC ruling (2026-10-19T03:37:38Z; CHARC author, orchestrator courier):**

> RULING: A1 -- with ONE shape constraint: the helper is PURE. It takes the trade ROW (`Trade | None`) and the request's values; it takes NO connection and performs NO read. Call it `check_exit_preconditions`. It raises, in this order and with the EXISTING texts, exactly the six refusals record_exit raises today: invalid reason, shares <= 0, ExitPriceRefusedError, "not found", "not active", "exceeds". Nothing else moves into it (the identity guard and the envelope read stay where K1 (2) and F2-(iii) put them).
>
> WHY A1 AND NOT THE OTHERS:
> - A2 is the two-path-divergence class on the project's own evidence: the 21-B live catch was a panel that spelled the mandate's rounding a second time and disagreed by a cent. A route-side copy of a service predicate is that defect waiting for the first edit to one spelling. Out.
> - B asks the operator to CONFIRM an exit the service will then REFUSE regardless of the answer. The ordering principle is the one CLAUDE.md already fixes for SELECT-first idempotency: a refusal that does not depend on the operator's answer precedes the question. Two round trips to learn an exit is impossible is a UX regression wearing a test amendment. Out.
> - A1 widens K1 by one public PURE symbol in exit.py. That is item (3), the typed refusals, made importable so the route can ORDER them before the F1 question. No new read, no schema, no new module, no dependency: no tripwire. I rule it in.
>
> WHY PURE, NOT "READ-ONLY WITH A CONNECTION": the orchestrator's A1 said "read-only helper". A helper that takes a connection raises the question of WHICH read it performs and under WHICH lock, and the route's advisory call would then be a second read site inside the carve-out. Pure over the row, the read stays exactly where K1 (1) put it: record_exit's own get_trade AFTER BEGIN IMMEDIATE is the barrier, and the route hands the helper the row it already holds for the re-render. The helper cannot be the barrier and cannot drift from it, because it has nothing to read.
>
> CALL SITES:
> - record_exit: CallerHeld check -> BEGIN IMMEDIATE -> get_trade -> check_exit_preconditions(trade, ...) -> the identity guard -> the writes. The six checks now run under the lock; the pre-BEGIN copies of reason/shares/price are REMOVED, not duplicated (one spelling). ACCEPTED COST, named in the docstring: a request refused on its arguments takes one BEGIN/ROLLBACK first. On a single-operator DB that is nothing; a second spelling is not. The transaction paragraph of the record_exit docstring is rewritten by replacement (its "pure checks run before BEGIN" sentence becomes false). F2-(iii)'s envelope read stays BEFORE BEGIN as ruled; it is not one of the six.
> - the route: inside the EXISTING `try` whose `except ValueError` drives the d2-strict re-render, AFTER the anchor ladder and BEFORE any flag is computed (F1 and the F2 unreadable flag alike): `check_exit_preconditions(trade, ...)` on the trade row the route already read. A refusal there takes the same re-render the service refusal takes today -- that is what keeps the restore assertions in :315/:401/:459 true byte-for-byte. The route's comment names the window (the row was read outside the lock; the in-lock call in record_exit is the barrier; this call only orders the refusal before the question). T1-d already pins the barrier against a concurrent writer; no new barrier test is owed for the route call.
>
> DISCRIMINATORS (RED first):
> (i) T7-k's three tests, green UNCHANGED -- the fork's own witness, already named by the plan. No edit to that file.
> (ii) NEW, test_d79_exit_identity.py: a claimed POST with shares over current_size AND a price edited away from the selected entry (an F1 trigger and a refusal at once). Expected: 400, "exceeds" in the body, NO confirm prompt text and NO acknowledged-flag identity input in the body, no fill. Pre-fix (flags computed first): the confirm prompt renders and "exceeds" is absent -> RED. Null implementation killed: ordering flags before the precheck.
> (iii) NEW, the one-spelling pin: a spy on check_exit_preconditions sees it called from BOTH sites on one accepted POST (route, then record_exit under the lock) and from the ROUTE ONLY on a refused one (record_exit never entered). Patch the name where each site resolves it (a module-level `from ... import` in the route will not see a patch on swing.trades.exit; the cell makes the pin see both). Null implementation killed: A2, and any later route-side inline comparison against current_size.
> (iv) NEW, unit: check_exit_preconditions over a synthetic Trade row raises each of the six with the existing message text, and `inspect.signature` shows no `conn` parameter. Null implementation killed: a helper that reads.
>
> MERGE GATE: unchanged from the brief's section 4, plus the (ii)-(iv) tests visible in the diff and the record_exit docstring's transaction paragraph rewritten.

**Orchestrator intake check on the ruling (2026-10-19), code facts only; the reasoning binds as written:**
1. *The ruling names "the trade row the route already read"; the code has none.* `exit_post` (`swing/web/routes/trades.py:2576-3498`) does not call `get_trade` before `record_exit` (:3351); its only `get_trade` (:3449) runs after the record. **Encoded:** the route reads the row with `get_trade` (already imported at `routes/trades.py:19`) on the SHORT read-only connection T7 step 2 opens for the flag reads, closed before `record_exit`'s connection opens. That read is in the route, outside the carve-out, so CHARC's purity reason (no read inside `exit.py`, the in-lock `get_trade` the only barrier) is untouched. The route comment names this window.
2. *Order change the cell must check:* today the three argument refusals run before the F2-(iii) envelope read (`exit.py:379-383`, then the read). Under the ruling the envelope read stays before BEGIN and the argument checks move under the lock, so a request with BOTH a bad argument and an unreadable envelope now raises `ExitEnvelopeUnreadableError` first. Not a fork: at the route, the precheck runs first and still refuses on the argument. The cell greps for any existing test pinning the old service-level order and classifies a red there as SUPERSEDED (named) only if it pins exactly that order.

Author of this intake check: orchestrator.

### FORK 2 -- who gets a synthesized `selected_entry` (RULED: orchestrator)

T6 item 2 synthesizes `selected_entry` from the top-level quartet only for a legacy no-map envelope. A claimed envelope with a multi-entry map and no candidate inputs (after T5, only multi-entry maps can arrive bare) has `authoritative_selected is None`, so F1 cannot fire and an edited value records as corrected with no confirm.

> **Orchestrator ruling, D79 executing Fork 2 (2026-10-19).** Encode the cell's proposal: the route synthesizes `selected_entry` from the envelope's top-level quartet whenever the claim is a dict and `authoritative_selected is None`, map or no map. It stays the ONE synthesis site, and its comment names both shapes. Reason: K7.3 makes the top-level values the selected candidate's, and with no selection sent the top-level quartet is the default candidate the form showed, so the synthesized entry is K7.3's selected entry for this shape; K5 binds every corrected record to an acknowledged flag, so any shape that reaches the corrected branch without F1 is a hole, however rarely the form produces it. For the multi-entry shape `OTHER_ORDER` becomes reachable (the typed values derive from exactly one other map entry); the legacy no-map shape stays `NO_CANDIDATE`-only. Required RED test **T6-h**: a claimed multi-entry envelope with top-level o2 and no candidate inputs -- (i) price edited -> 400, F1 `NO_CANDIDATE` naming "price", no fill; (ii) typed values equal to o1's map entry -> 400, F1 `OTHER_ORDER` naming o1, no fill; (iii) unedited -> `schwab_auto`, one fill, 200. Pre-fix arithmetic, against the plan as written (legacy-only synthesis): (i) records `schwab_auto_then_operator_corrected` on the first POST, so the test is red; (iii) passes both ways and is the control. Declined alternative: a 400 on a missing selection through the anchor ladder; it adds a rung that would red bare-form tests across the suite to close a hole synthesis already closes, and it is a different shape from the one confirm protocol.

Author: orchestrator. Recorded by the orchestrator.

**RD on Fork 2 (2026-10-19T03:37:09Z, fyi; RD author, orchestrator courier):**

> NO MEASUREMENT PROBLEM. Concur. The synthesized entry IS the entry the form showed checked: both the default radio and the top-level quartet are "last candidate", one rule, one source, so the imputed selection is the operator's visible default, not a guess. Identity is still never asserted from the synthesis alone: the id survives only through the retention rule (derives, or an acknowledged F1), which is K3 (iv) unchanged. The confirm leg is sound as planned: a first POST with no selection carries no selected hash, the flagged re-render therefore checks the default (the same entry), and the confirm POST arrives with an explicit candidate_index -- one synthesis, never two; T7-c voids it if the fresh map moved (K3 precondition 2).
>
> ONE TEST-SCOPE SUGGESTION for T6-h (no mechanism change; the cell's call): add a confirm leg to (i) or (ii) -- the flagged re-render's checked radio is o2 (`_checked_radios(body) == [<o2 index>]`) and after confirm the persisted `selected_candidate_signature_hash` is o2's. Today the default-radio/top-level coupling is a fact I verified by READ at two sites; that assertion makes it a fact the suite holds, so a future reordering of either site cannot silently make the synthesized entry and the checked radio different orders.

RD's read sites: `view_models/trades.py:987-991` (the default radio is the LAST candidate), `exit_auto_fill.py:954` (`chosen = candidates[-1]`) and `:1186-1188`, `routes/trades.py:2524-2536` (restore by hash).

> **Orchestrator addendum to the Fork 2 ruling (2026-10-19).** RD's suggestion is ADOPTED as a REQUIRED assertion of T6-h, not left to the cell. Leg (i) gains a confirm step: in the flagged re-render, `_checked_radios(body) == [<o2's index>]`; after the confirm POST, the persisted `selected_candidate_signature_hash` equals o2's hash and the top-level `schwab_order_id == "o2"`. The reason is RD's: the coupling between the default radio and the top-level quartet is today a fact verified by reading two sites, and the assertion makes the suite hold it.

Author: orchestrator. Recorded by the orchestrator.
