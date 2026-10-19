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

## Cell 2 (implementer-opus-high, dispatched off `efd3a80f`)

Returned at FORK 3, before T7. No counted review round has run. Depth at return: **377,631**. Not resumed (T7, T8, the classification and the review cannot fit under the cap); cell 3 continues.

| Commit | Task | Note |
|---|---|---|
| `04f74a1a` | T4 follow-up | the 22-F INV-MODEL closure went red on `ExitRecordFlag.__post_init__`; classified `computed` in a new `LATER_ARC_ROSTER` map (ROSTER stays the pinned 118) |
| `6a6e987a` | T6 | selection rewrite, F1 as a flag (Fork 2 synthesis), retention rule rewritten, padded-id `_reject_anchor`, T6-a/d/e/f/h green. **Red by design**, every red named in the body: the 3 T7-k over-size tests (greened by T7's Fork 1 precheck) and 8 record-on-first-POST tests in `test_exit_post_audit_columns.py` (the plan's 6 plus `test_g_multi_partial_selects_non_default_candidate_and_preserves_others` and `test_h_major2_authoritative_selected_candidate_order_id_from_envelope`), rewritten in T7 |
| `512ed9ca` | T7a | the pure `check_exit_preconditions(trade, req)`, called after BEGIN IMMEDIATE and `get_trade`; the pre-BEGIN argument checks removed; test (iv) green; the order-change grep found no old-order pin (only T2-e, which has valid arguments) |

- Suite on `efd3a80f`, read off the output: 4 failed, 15418 passed, 13 skipped (628.02 s). Three were the untracked T8 tests (expected). One was the INV-MODEL closure, a regression from cell 1's T4, fixed at `04f74a1a`.
- **Orchestrator QA (against disk, `512ed9ca`):** trailers empty on all three; no added file under `swing/`; the INV-MODEL diff read in full; Fork 3's premise verified (`_exit_candidates_maps_equal` returns False for a map-less envelope, `routes/trades.py:2445`); `swing.data.db.connect` (`db.py:155-162`) opens in the default isolation mode, and a SELECT there leaves `in_transaction` False (executed); the 22-F tests at `test_22f_exit_post.py:107-133` and `:214-250` patch `swing.web.routes.trades.connect`, and R3-04 asserts `len(built) == 1`.
- **To CHARC for ratification at the merge gate (not blocking):** `04f74a1a` changes the shape of a 22-F instrument (a second roster map, read in union). The classification is plain; the structure is CHARC's to accept.

### FORK 3 -- T6-g's first leg vs T7 step 3's flag-drop rule (RULED: orchestrator, G1)

> **Orchestrator ruling, D79 executing Fork 3 (2026-10-19).** **G1.** T7 step 3 stands: when the claimed anchor is not restorable (a map-less legacy envelope, or any claim whose fresh fetch is not `populated`), the flags are DROPPED and the refresh notice shows. T6-g's first leg is amended by replacement: the legacy first POST returns 400, writes no fill, shows the refresh notice and NO flag text, carries the FRESH map-bearing anchor, and keeps the typed values; its message says nothing was recorded because the order list must be re-confirmed, not "Confirm or retype". A plain resubmit on that fresh anchor is then asked F1 against the fresh selection. T6-g's confirm leg re-posts the ORIGINAL legacy submission with `force` and a test-built identity and is VOID under d2, as planned; `test_g_multi_partial...` takes the same shape. Reason: K5 asks a question only about a selection the operator can still see. A flag about a selection the rendered form no longer carries cannot be answered truthfully; under G2 the browser's Confirm would carry the fresh anchor and record a correction the operator was never shown, which breaks the plan's "a legacy envelope never records a correction" on the one path that matters. In sandbox or an outage the claimed POST therefore degrades to the existing d2 recovery, ending in an `operator_typed` record; that is the honest provenance when the broker cannot be re-read. The sandbox tests in `test_exit_post_audit_columns.py` that need F1 to render are rewritten with `_exit_candidates_maps_equal` stubbed True (T7-f's technique), each named as SUPERSEDED.

### Connection shape for the T7 reads (RULED: orchestrator; overrides cell 2's choices 5 and 8)

Cell 2 proposed opening the plan's short read connection through `swing.data.db.connect`, resolved at call time, so that the 22-F tests patching `swing.web.routes.trades.connect` keep seeing one connection, and placing the precheck in its own `try`.

> **Orchestrator ruling, D79 executing, T7 read connection (2026-10-19).** NO second connection. The T7 reads -- the precheck's `get_trade`, `anonymous_fill_matches`, `recorded_exit_identities(...).unreadable` -- run on the route's ONE connection (`routes/trades.py:3353`), after it opens and BEFORE `record_exit`, inside the existing `try` whose `except ValueError` drives the re-render, exactly where CHARC's Fork 1 ruling placed the precheck. The plan's "a fresh read on its own short connection" (T7 step 2) is superseded by this text. Reasons: (1) the proposed route would make a 22-F instrument's claim false while it stayed green -- A7-b's docstring says the route opens exactly one connection through `swing.web.routes.trades.connect`, and a second connection opened under another name is invisible to every patch at that point, which is the guard-present-but-unreachable class; (2) the second connection existed only to be closed before `record_exit`'s opened, and nothing needs that: `connect` opens in the default isolation mode, where a SELECT leaves `in_transaction` False (verified by execution), so `record_exit`'s caller-held check sees no transaction; (3) with the reads inside the existing `try`, a flag or precheck re-render takes the same close guard the service `ValueError` re-render takes today, so the 22-F close semantics cover it unchanged. The reads stay advisory: the identity guard (a) and the six refusals are re-run by `record_exit` under its own lock. Discriminators: the 22-F tests in `test_22f_exit_post.py` stay green UNCHANGED (any red is a regression); a new test asserts an accepted claimed POST opens exactly ONE connection through `swing.web.routes.trades.connect` (killing the two-connection shape); T7-a's confirm leg recording proves `record_exit` is entered with no caller-held transaction.

### Cell 2's other choices (accepted; Reviewer A's prompt carries each, challenge invited)

6. The selected entry is shape-checked with tier (d)'s predicate, now one `_exit_values_well_formed`, before it is copied to the top level; a failure goes to `_reject_anchor`.
7. `exit_date_source` is set from the selected entry when it carries `date_source`, and popped otherwise.
9. A d2-VOID confirm reuses the confirm's `fresh_vm`; there is no second Schwab fetch.
10. `acknowledged_flag` is read with `getattr(form_data, "getlist", ...)`, because the 22-F direct-drive test stubs the form as a plain dict. (A production accommodation of a test stub; Reviewer A weighs it.)
11. T7-f: the base variant is voided by d2 (400, refresh notice, one o1 row); the variant with `_exit_candidates_maps_equal` stubbed True gets "already recorded as fill(s) #A" (400, one o1 row); tab B's acknowledgements are test-built because its first response drops its flags.

Author of the sections above: orchestrator.

## Cell 3 (implementer-opus-high, dispatched off `6f7ebade`)

Author of this section: cell 3.

| Commit | Task | Note |
|---|---|---|
| `67c4573e` | 22-F roster message | the unclassified-failure text points a later validator to `LATER_ARC_ROSTER`, never `ROSTER` (CHARC ratification 2026-10-19, relayed by the orchestrator) |
| `606a25fb` | T7 | the confirm shape; FORK 1 precheck, FORK 3 flag drop, one connection; T6-b/c/g, the T6-h confirm leg, FORK 1 (ii)/(iii), T7-a..j, the one-connection test; 8 + 2 tests superseded (named in the body) |
| `867dfb67` | T8 | `--confirm-duplicate`; cell 1's draft committed with its seeding bug fixed (a 10-share entry) |

**Encodings cell 3 made without a fork (Reviewer A's prompt carries each, challenge invited):**
12. The d2 check of a `force` POST runs BEFORE the route connection opens (it is a Schwab fetch, not one of the ruled advisory reads); the FORK 1 precheck therefore follows it. Either order records nothing; a void confirm that is also over-size shows the void text, not "exceeds".
13. A `force` POST whose fresh VM is `None` (trade gone) is treated as VOID.
14. `anonymous_fill_matches` on the route is given the typed `exit_date` as typed (the same string F1 and the retention rule compare), not `[:10]`; the CLI passes `[:10]` because the CLI accepts a datetime.
15. The unreadable reader runs only for a LINKED exit (its flag needs `linked`); `anonymous_fill_matches` calls the one reader internally, so a linked POST reads it twice (AL-9's cost, doubled; no cache built).
16. An unclaimed submission's flagged re-render carries the FRESH anchor (as the `ValueError` re-render already does), so its Confirm arrives as a CLAIMED POST and may be asked F1 against the fresh default. Pre-existing re-render behaviour, not new.

**T6 supersession classification** (all of `tests/web/test_routes/`, run against the T7 code with the OLD test texts restored, then with the rewritten ones):
- SUPERSEDED (9 red, all rewritten by replacement, named in `606a25fb`): `test_exit_post_audit_columns.py` -- the plan's six plus `test_g_multi_partial_selects_non_default_candidate_and_preserves_others` and `test_h_major2_authoritative_selected_candidate_order_id_from_envelope`; `test_exit_form_auto_fill.py::test_r2_minor1_operator_instruction_text_present_in_multi_partial_fieldset` (the template text T7 rewrites). Its negative twin `test_r2_minor1_no_instruction_text_on_single_fill_case` was green both ways and was moved to the new sentence so its negative stays meaningful.
- REGRESSION: none. T7-k's file and the 22-F exit tests green unchanged.
- Read off the output: old texts 9 failed / 1171 passed; rewritten 1180 passed, 0 failed.

### T9 census commands (column names checked against the live DDL, `mode=ro`, schema only)

Live DDL read 2026-10-18 by `PRAGMA table_info` on `~/swing-data/swing.db` (`mode=ro`): `fills` has `fill_id`, `action`, `schwab_source_value_json`; `reconciliation_corrections` has `affected_table`, `affected_row_id`, `field_name`. All names in both commands exist.

**PLAN CORRECTION (measured by execution, not a fork): the plan's census 4 SQL is VACUOUS as written.** It aliases the extracted id `oid`, and `oid` is one of SQLite's ROWID aliases: in `WHERE oid IS NOT NULL` and `GROUP BY oid` it resolves to the table's rowid (`fill_id`, an `INTEGER PRIMARY KEY`), not to the alias, so every group has one row and `HAVING COUNT(*) > 1` returns nothing on any data. On a synthetic DB with two non-entry fills sharing id `a`: the plan's text returned `[]`; the same query with the alias renamed `linked_id` returned `[('a', 2, '1,2')]`; `SELECT oid, fill_id` returned equal pairs. Encoded with the alias `linked_id`; nothing else changed.

Both run against the scratch COPY (never the live DB), from the worktree, through plain `sqlite3` with `mode=ro`; `PYTHONPATH=.` so the authority is the worktree's. Replace `<COPY>` with the copy's absolute path. Dry-run on a synthetic DB: census 4 printed `[('a', 2, '1,3')]`, census 5 printed `3 non-entry envelopes; 1 refused: [2]`.

```bash
cd C:/Users/rwsmy/swing-trading/.worktrees/d79-exec && PYTHONPATH=. python - "<COPY>" <<'PY'
import sqlite3, sys
from swing.trades.latched_origin import ENVELOPE_REFUSED, canonical_envelope_identity
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
# Census 4 (CHARC K6): linked exit fills sharing an extracted id, split partials excluded.
# Expected: only known partial sets.
print("census 4:", c.execute("""SELECT json_extract(schwab_source_value_json,'$.schwab_order_id') AS linked_id,
       COUNT(*), group_concat(fill_id)
FROM fills
WHERE action != 'entry' AND json_valid(schwab_source_value_json)
  AND fill_id NOT IN (SELECT affected_row_id FROM reconciliation_corrections
                      WHERE affected_table = 'fills' AND field_name = '__insert__')
  AND linked_id IS NOT NULL
GROUP BY linked_id HAVING COUNT(*) > 1""").fetchall())
# Census 5 (CHARC FORK 2): the authority over every non-NULL non-entry envelope.
# Expected: 0 refused (0 of 33 at intake). A non-zero count is a finding.
rows = c.execute("SELECT fill_id, schwab_source_value_json FROM fills "
                 "WHERE action != 'entry' AND schwab_source_value_json IS NOT NULL "
                 "ORDER BY fill_id").fetchall()
refused = [f for f, e in rows if canonical_envelope_identity(e).state == ENVELOPE_REFUSED]
print("census 5:", len(rows), "non-entry envelopes;", len(refused), "refused:", refused)
c.close()
PY
```

Note on census 4 as a reader: `json_extract` is a different reader from the authority (AL-1's reason), so a padded id groups under its padded text there; census 5 is the authority's count.

## Review (Reviewer A)

Author of this section: cell 3. Tier `strong`, cold-audit form with repo access: `codex exec -p strong -s read-only --skip-git-repo-check -` run from the worktree (`/mnt/c/.../.worktrees/d79-exec`), the prompt (brief list + envelope + AL-1..AL-9 with reasons + the four rulings and choices 1-4, 6-16 via this ledger + the `618d7b04..HEAD` diff) on stdin, output to WSL `$HOME/d79r/` (scratch kept OUT of the worktree). Pre-review full fast suite on `c55b55b8`, read off the saved output: **15455 passed, 13 skipped, 0 failed** (945.11 s); `ruff check swing/` clean.

| Round | Head reviewed | Model / effort (asserted) | `^ERROR` | Footer (`tokens used`) | Verdict token | Crit | Major | Minor | New / reopened | Reverts | Depth (orchestrator) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `c55b55b8` | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (403,744) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 2 | 1 | 3 new / 0 reopened | 0 | 378,356 (cell 3 at return; retired) |
| 2 | `cb452050` | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (954,070) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 3 | 5 | 8 new / 0 reopened | 0 | 301,169 (cell 4 at return; resumed) |
| 3 | `084c9a3a` | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (629,503) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 3 | 2 | 5 new / 0 reopened | 0 | 371,037 (cell 4 at return; retired) |
| 4 | `33a3bfa2` | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (440,564) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 1 | 3 | 4 new / 0 reopened | 0 |  |

Evidence: `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\review-r1.txt` (1,547,419 bytes), `prompt-r1.md` (367,520 bytes), `copowers-findings.md`. Exit file 0; the process exited before the transcript was read. Prior-findings reach: none (round 1).

### Round 1 adjudication

- **D79-A1 (major): ACCEPTED, to fix.** `derives_from` truncates the quantity with `int()`, so a stored anonymous 5.9-share fill "matches" a typed 5-share exit. Verified by execution (`derives_from({..., 'quantity': 5.9}, shares=5)` is `True`). The truncation came over from the pre-arc route comparator, where map quantities are ints by tier (d); the arc newly applies the grain to STORED fills (`fills.quantity REAL NOT NULL CHECK (quantity > 0)`, migration 0014:13) in `anonymous_fill_matches` (route and CLI) and in the service's anomaly sentence. Fix: compare the quantity as a float at the resolver's established `isclose` grain inside `derives_from` and `_differing_fields`, and add a literal 5.9-vs-5 discriminator (T4-f's expected value is computed through `derives_from` itself, so it cannot see this).
- **D79-A2 (major, tagged [AGAINST-RULING]): ROUTED AS A FORK, not fixed.** The possible-partial and unreadable-envelope identities are `"<kind>|<fill_id>"`, while their texts name the SELECTED order. On a multi-candidate form where two candidates both list fill #F (a possible partial), an operator shown the o1 question can switch the radio and values to o2 and press Confirm; the map is unchanged so d2 passes, and o2's identical `possible_partial|F` is satisfied by the o1 acknowledgement. The same holds for `unreadable_envelope|F` across linked orders. Verified by read (`exit_record_flags` subjects). The fill-id-only subject is the orchestrator-accepted plan-intake encoding ("the partial's fill id"), so changing it is not the cell's call.
- **D79-A3 (minor): ACCEPTED, to fix without a round.** Supersession residue in `exit_auto_fill.py`: the `PossibleDuplicateFill` docstring and `resolve_exit_auto_fill`'s docs still describe value-tuple-only matching and per-trade recorded ids.

### Orchestrator QA of round 1 and of cell 3 (against disk, `2c6f2466`)

- The transcript's assertions were re-read independently from `review-r1.txt`: banner `model: gpt-5.6-sol`, `reasoning effort: high` (equal to `~/.codex/strong.config.toml`); `^ERROR` 0; `^tokens used` present, 403,744; the anchored verdict tokens are `NEW_CRITICAL_MAJOR_FOUND` x2 and the other token 0. **Round 1 COUNTS.**
- Trailers are empty across `618d7b04..HEAD`; no added file under `swing/`; no migration; `git status` clean. The shared stash stack holds only the pre-existing SB5.5 entry (the cell's red-first stash was cleaned up).
- D79-A1's premise was verified at `exit_auto_fill.py:1814` (`entry_shares = int(entry.get("quantity"))`).
- The census-4 `oid` alias correction is accepted. SQLite resolves `oid` to the rowid, so the plan's query could never return a group with count > 1; the cell recorded the correction with execution evidence.

### CHARC ratification of the 22-F roster shape (2026-10-19T04:10:09Z; CHARC author, orchestrator courier)

> RULING: a SECOND MAP, not a moved count. ROSTER's identity is "the 118 distinct origin functions of the PINNED triage.json" -- the docstring's own first sentence. Moving the 118 to 119 would dissolve the pin into a running list and lose the one fact the number records: what the 22-F census measured, on which commit. A later arc cannot be in triage.json, so it cannot be in ROSTER; LATER_ARC_ROSTER with the arc and the constructing site in a comment is the honest attribution. The structure is sound because the closure, the resolution and the well-formedness checks all read the UNION (verified at :292-294, :303, :312-313); the later map is held STRICTER than the pin (pattern-only, no NAME_LISTED exemption, disjoint from both lists). A validator reaches the union or the test is red, which is the whole instrument. `len(UNREACHED) == 53` standing is correct: no reason was retired.
>
> THE ONE CORRECTION (text, cell 3, before T7 lands or with it): the unclassified-failure message at :315-317 still reads "classify ... into ROSTER ... or UNREACHED with the census reason". The next author who follows that instruction moves the pinned count, which is exactly what the new docstring forbids. The message names LATER_ARC_ROSTER as the destination for a post-pin validator, ROSTER never. A message that contradicts the docstring is a D21-class decay seed; fix the text, nothing else.
>
> MERGE GATE: unchanged, plus the roster message text corrected and the 04f74a1a diff cited in the merge report as the 22-F instrument touch.

The correction landed at `67c4573e`.

### FORK D79-A2 -- the possible-partial and unreadable flag identities are not scoped to an order (RULED: orchestrator, branch B)

> **Orchestrator ruling, D79 executing Fork A2 (2026-10-19).** **Branch B: scope the identity to the order the question is about.** The possible-partial identity becomes `possible_partial|<selected order id, or the selected candidate signature hash when the entry has no usable id>|<fill_id>`. The unreadable identity becomes `unreadable_envelope|<linked order id>|<fill_id>`. The change is in `exit_record_flags` only. The F1 identity (selected id plus typed tuple) and the (c) value-tuple identity (matched fill ids) are unchanged: the (c) question is about the typed exit against an anonymous fill, which a radio switch does not change. This supersedes, by replacement, the partial and unreadable subjects in the plan-intake encoding I accepted (plan ledger, "Plan intake": "the partial's fill id") and the plan's "Naming used below" line. Reason: K5 binds a confirmation to the question that was ASKED. The finding shows an acknowledgement given to o1's question discharging o2's, on a path d2 cannot see because the map is unchanged; that is the "force as a blanket waiver" null implementation in a narrower costume. The on-screen per-candidate marker (template :139-143) is information, not an acknowledgement, so Branch A's accepted limitation would have recorded a hole that is closable in one function. Required RED test: the browser shape. First, a two-candidate form where both candidates list fill #F as a possible partial; o1 is picked, and its flag is rendered. The operator then switches the radio and values to o2 and presses Confirm with o1's acknowledgements. The expected result is 400, re-asked, no fill. Pre-fix arithmetic: the identity `possible_partial|F` is equal for both orders, so the confirm records o2 (red). Post-fix: the identity carries o1 and so does not satisfy o2's question (green). T7-h/i's asserted identity strings are updated by replacement and named.

Author of the sections above: orchestrator.

## Cell 4 (implementer-opus-high, dispatched off `ac9467a7`)

Author of this section and of the round-2 records below: cell 4.

| Commit | Item | Note |
|---|---|---|
| `3b850877` | D79-A1 | one `_quantities_equal` (`math.isclose`, rel and abs 1e-9), called by `derives_from`, `_differing_fields` and the resolver's `_undecidable_duplicates`; RED: a stored 5.9-share fill no longer matches a typed 5, a 5.9 map entry is asked F1 naming quantity; nothing superseded |
| `f3923680` | D79-A2 | Fork A2 branch B in `exit_record_flags` only: `possible_partial\|<order key>\|<fill_id>`, `unreadable_envelope\|<order key>\|<fill_id>`; RED: the browser shape (o1 flagged, radio and values switched to o2, Confirm with o1's acks) went 200 pre-fix, now 400 and re-asked; 3 tests superseded by replacement (named in the body); the plan's "Naming used below" line replaced |
| `cb452050` | D79-A3 | docstrings rewritten by replacement (`PossibleDuplicateFill`, `resolve_exit_auto_fill`'s evidence states and two argument docs) plus one more site the class re-grep found (`build_exit_form_vm`'s comparison comment) |

- Full fast suite on `cb452050`, read off the saved output: **15460 passed, 13 skipped, 0 failed** (589.28 s). That is 15455 + the 5 new tests. `ruff check swing/` is clean, `%(trailers)` is empty across `618d7b04..HEAD`, and no file was added under `swing/` (`git diff --diff-filter=A`, empty).

### Round 2

Run with the cold-audit form and repo access: `codex exec -p strong -s read-only --skip-git-repo-check -`, from the worktree. The runner is `~/d79r2/run_r2.sh` in WSL (literal paths, LF, checked with `file`); output went to WSL `$HOME/d79r2/`. The prompt was rebuilt on `cb452050` and carries:
- the envelope, with the 22-F roster test added;
- AL-1..AL-9, each with its reason;
- the five rulings and CHARC's 22-F roster ratification, as excerpts (exec ledger lines 1-179 and 204-218);
- choices 1-4 and 6-16, with challenge invited;
- the `618d7b04..HEAD` diff with this ledger EXCLUDED.

It forbids opening this ledger on disk and any prior-round file. It carries no round-1 finding text. The only round-1 traces are code comments in the diff naming the fixes (`D79-A1`, `D79-A2`).

- **Assertions** (literal-path greps of `review-r2.txt`):
  - banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `~/.codex/strong.config.toml`;
  - `^ERROR` 0; `^tokens used` 1 (954,070);
  - `^NEW_CRITICAL_MAJOR_FOUND` 2 (the CLI's double emission) and `^NO_NEW_CRITICAL_MAJOR` 0;
  - exit file `0`, written by the runner after codex returned, so the process had exited before the transcript was read.
  - **Round 2 COUNTS.**
- **Prior-findings reach: none.** The hits for `d79r/`, `review-transcripts`, `copowers-findings`, `exec-ledger.md`, `review-r1` and `prompt-r1` are all prose: the prompt echo, a plan line naming the round-0 probe path, one diff line, and docs text Codex read. The response says no prior review or exec-ledger file was opened.
- **Content-filter events:** none reported.
- **Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\` holds `review-r2.txt` (1,590,650 bytes), `prompt-r2.md` (365,026 bytes) and `exit-r2.txt`, copied once the assertions passed.
- **Spend:** round 1 403,744 + round 2 954,070 = **1,357,814** tokens.

### Round 2 adjudication

Every premise below was re-checked against the code at `cb452050` before it was classified.

- **RA-01 (major): ACCEPTED, to fix. It is NOT schema-prevented (verified by execution).**
  - The defect: `recorded_exit_identities` (`swing/trades/exit.py:264`) builds `RecordedExitFill(price=float(price), quantity=float(quantity))` BEFORE it reads the envelope, with no guard.
  - Why the schema allows it: `fills.price` and `fills.quantity` are `REAL NOT NULL CHECK (> 0)` (migration 0014:13-14). An in-memory probe inserted `'abc'` and `'xyz'` into a table with those constraints, and they were stored with `typeof` `text`. Migration 0037 (`:1053-1103`) already branches on `typeof(f.quantity) = 'text'`, so the project's own SQL treats this shape as possible.
  - The blast radius: the reader is GLOBAL and runs on every exit-form GET, every exit POST and every confirm. So one such row on any trade raises `ValueError` there. Before the arc, the view model's per-trade read converted inside a `try` (`view_models/trades.py`, the anonymous loop).
  - Live incidence: NOT measured. A data read is outside this cell's authorization (`mode=ro` schema reads only). The orchestrator can count it read-only with `SELECT typeof(price), typeof(quantity), COUNT(*) FROM fills WHERE action != 'entry' GROUP BY 1, 2`.
  - The fix stays inside the K1 (2) carve-out. Read the identity first; keep a malformed linked row in `by_order_id`, so it still triggers the (a) refusal; carry values that will not convert as raw or `None`, which `derives_from` already treats as not deriving.
- **RA-02 (major): ROUTED AS A FORK, not fixed. It meets Fork 2's literal scope.**
  - The scenario, read in code: a map-less (legacy) claimed envelope with top-level o2, plus an explicit `candidate_index=0` and the inputs `candidate_signature_hash_0` and `candidate_order_id_0=o1`, with the typed values left at o2's.
  - What the route does: `authoritative_selected` is `None` (the map is empty, `:3047`). The entry is synthesized from top-level o2 (`:3085-3093`), so F1 does not fire. `selected_candidate_order_id` takes the client's `o1` through the legacy fallback (`:3157-3160`). The retention rule keeps top-level o2. The POST then records on the first try.
  - This is PRE-ARC behaviour, unchanged by the arc (`618d7b04:2875` and `:3033-3042` read the same). It is reachable only through an envelope with no `candidates_map`. The resolver has emitted a map for every populated render since Codex R1 Critical #1, so in practice that means a tampered envelope or a stale pre-map tab.
  - **Branch A (the reviewer's fix):** an explicit selection (`selected_index is not None`) on a claim whose envelope carries no `candidates_map` cannot be resolved, so it does NOT take the Fork 2 synthesis. It gets the Fork 3 G1 response: 400, the refresh notice, the fresh map-bearing anchor, the typed values kept, nothing recorded. This holds even when the typed values derive from the top-level quartet. Synthesis remains for the no-selection shape only. RED test: the scenario above; before the fix it returns 200 with `selected_candidate_order_id` o1 and top-level o2, after it 400 with no fill. Cost: any existing test that records from a map-less envelope carrying candidate inputs becomes SUPERSEDED and must be found by a run.
  - **Branch B (accept as a limitation, AL-10):** the reason is that this shape is pre-arc, is not produced by the current form, and records no correction. Its top-level link is backed by values that derive from the top-level quartet. `selected_candidate_order_id` is an audit trail, not an identity (CLAUDE.md, "`selected_X_audit_id` is an AUDIT TRAIL"). Optional rider within B: drop the `candidate_orders` fallback (`:3157-3160`), so the audit field records `None` rather than a pick the server cannot resolve. That is a one-line change and red-first testable.
  - The cell does not choose.
- **RA-03 (major): ACCEPTED, to fix. It is consistent with Fork 2. It is not a fork, but it touches the same code as RA-02.**
  - The defect: `selected_index = 0 if 0 in candidate_sigs` (`:2967-2972`) predates the arc (`618d7b04:2875`). Since T6 item 1 rewrites the top level to the selected entry, omitting only the radio now relinks the row to candidate 0 rather than to the visible default (the last candidate). It is silent when two orders share (date, price, qty); otherwise F1 asks about candidate 0.
  - Browser reachability: none found. The template always checks one radio (`trade_exit_form.html.j2:117-118`: the last one, or the restored index), so only a non-browser client omits it.
  - The fix: infer index 0 only for a one-entry map (or a map-less legacy single). A multi-entry map with no `candidate_index` stays unselected and takes Fork 2's synthesis. That is Fork 2's own rationale ("with no selection sent the top-level quartet is the default candidate"). RED test: remove only `candidate_index` from a two-candidate form and expect the default's (o2's) link.
  - If RA-02 is ruled Branch A, both edits land in the same block.
- **RA-04 (minor): ACCEPTED, to fix without a round.** `_rerender_exit_form_with_error` (`:2579`) rebuilds the VM when `fresh_vm is None`, so a VOID confirm whose prefetch returned `None` (choice 13) builds a second time. The fix is a sentinel that tells "not prefetched" apart from "prefetched `None`".
- **RA-05 (minor): ACCEPTED, test to add.** No route test carries two flags at once, so an "any acknowledgement" null implementation passes them. Add a two-flag POST, for example (c) plus unreadable: acknowledge one and get 400 with no fill, acknowledge both and it records.
- **RA-06 (minor): ACCEPTED, test to add.** T8-b plants one match. Plant two: confirming one id refuses, confirming both records.
- **RA-07 (minor, [OUT-OF-ENVELOPE]): NOT fixed. Proposed disposition BANKED.** The module docstring of `swing/data/repos/fills.py:6` prescribes `with conn:`, and `record_exit` now owns `BEGIN IMMEDIATE`. The envelope forbids any edit under `swing/data/`. Proposed owner: the orchestrator. Proposed trigger: the next arc with a `swing/data/repos/fills.py` carve-out, or a docs rider.
- **RA-08 (minor, [OUT-OF-ENVELOPE] as tagged; it is plan text in this arc): ACCEPTED, to fix without a round, by replacement in the plan.** The census-4 SQL at plan `:454-461` still aliases `oid`; cell 3's correction lives only in this ledger. The fix renames the alias to `linked_id`. Plan `:526` says "the six superseded route tests" where cell 3's record is nine; the fix names the nine.

Round 2 has 3 majors (RA-01, RA-02, RA-03), all new, none reopened, no reverts. The loop has not converged.

### Orchestrator QA of round 2 (against disk, `8130a16b`)

- I re-read the assertions from `review-r2.txt`: banner `model: gpt-5.6-sol`, `reasoning effort: high`; `^ERROR` 0; `^tokens used` present, 954,070; anchored verdict tokens `NEW_CRITICAL_MAJOR_FOUND` x2, the other token 0. **Round 2 COUNTS.** Spend to date: 1,357,814.
- Trailers empty across `618d7b04..HEAD`; no added file under `swing/`; nothing under `swing/data/`; tree clean; the stash stack holds only the pre-existing entry.
- **RA-01, live incidence (orchestrator, `mode=ro`, 2026-10-19):** `SELECT typeof(price), typeof(quantity), COUNT(*) FROM fills ... GROUP BY 1,2` returns `[('real','real',31)]` for non-entry fills and `[('real','real',59)]` for all fills. The failure is LATENT on live, not present. The fix stands on the reader's new GLOBAL reach: one text-typed row anywhere would break every exit form.
- **RA-07: BANKED.** Owner: orchestrator. Trigger: the next arc with a `swing/data/repos/fills.py` carve-out, or a docs rider. Ground: the envelope forbids `swing/data/`, and the docstring is guidance, not behaviour.

### FORK RA-02 -- an explicit selection on a claim whose envelope has no map (RULED: orchestrator, branch A)

> **Orchestrator ruling, D79 executing Fork RA-02 (2026-10-19).** **Branch A.** A claimed envelope with NO `candidates_map` that carries an explicit selection (`candidate_index` with any per-candidate input) is not given the Fork 2 synthesis. It gets the Fork 3 G1 response: 400, the refresh notice, the fresh map-bearing anchor, the typed values kept, nothing recorded, even when the typed values derive from the top-level quartet. The Fork 2 synthesis remains for the NO-selection shape only, and the code comment at the one synthesis site says so. This narrows my Fork 2 ruling by replacement: its "map or no map" covered the absence of a selection, never a selection the server cannot resolve. Reason: the request names an order (o1) the server cannot verify against any list. Recording it links the top-level order (o2) while the audit trail claims o1, which is the arc's own defect: a recorded link that is not the operator's pick. Branch B would keep that record and document it, and its rider would only blank the audit field while still recording an o2 link the operator did not pick. A selection the server cannot resolve is a question the operator must re-answer on a list the server can see, which is exactly G1. Required RED test: the reviewer's case (map-less claim, top-level o2, `candidate_index=0` naming o1, typed values at o2's). Before the fix: 200 and one fill. After: 400, the refresh notice, no fill. Any existing test that records from a map-less envelope carrying candidate inputs is found by a run and classified SUPERSEDED (named) or REGRESSION.

RA-03 (accepted by the cell) lands in the same block: index 0 is inferred only for a ONE-entry map; a multi-entry map with no radio takes the Fork 2 synthesis.

Author of the sections above: orchestrator.

## Cell 4, resumed off `770f9105`

Author of this section and of the round-3 records below: cell 4.

| Commit | Item | Note |
|---|---|---|
| `270587c6` | RA-01 | the identity is read before any value; `RecordedExitFill.price` / `quantity` are float or `None` (`_stored_number`); RED: two tests raised `ValueError` before the fix; live incidence zero (orchestrator) |
| `fcf4d001` | RA-02 | branch A: an explicit selection on a map-less claim gets the G1 re-confirm before anything else; the synthesis-site comment narrowed; RED 200 -> 400; 1 SUPERSEDED: `test_exit_post_audit_columns.py::test_g_multi_partial_legacy_envelope_non_default_pick_records_nothing_and_its_confirm_is_void` (its force leg now reaches the re-confirm before d2); no regression |
| `11a828a8` | RA-03 | index 0 inferred only for a one-entry map; RED 400 -> 200 (o2, `schwab_auto`); no red in `tests/web/test_routes` |
| `10e7e6c1` | RA-04 | `_EXIT_VM_NOT_PREFETCHED` sentinel; RED two builds -> one |
| `24c16829` | RA-05 | two-flag test; discrimination measured by mutation (the intersect null fails it alone) |
| `853d7bd0` | RA-06 | two-id CLI test; discrimination measured by mutation (the any-one null fails it alone) |
| `084c9a3a` | RA-08 | plan census alias `linked_id` and the nine superseded tests, by replacement |

- Full fast suite on `084c9a3a`, read off the saved output: **15467 passed, 13 skipped, 0 failed** (591.51 s) = 15460 + the 7 new tests. `ruff check swing/` clean; `%(trailers)` empty across `618d7b04..HEAD`; no added file under `swing/`; nothing under `swing/data/`.

### Round 3

Same form, runner `~/d79r3/run_r3.sh`. The prompt was rebuilt on `084c9a3a`: the six rulings (exec ledger lines 1-179, 204-218 and 292-294), encoding choice 17 (RA-03) added, the claim list extended (the no-selection / re-confirm rule; the reader's identity-first read), the ledger diff cut out, no prior finding text.

- **Two attempts DID NOT COUNT (capacity aborts):** attempt 1 (exit 1, 387,932 bytes, two `^ERROR: Selected model is at capacity`, no footer, no verdict) and attempt 2 (exit 1, 964,222 bytes, two capacity `^ERROR` lines, footer 205,483, NO verdict token -- the 2026-09-06 shape). Both are preserved as `review-r3-attempt1-capacity.txt` / `review-r3-attempt2-capacity.txt` with their exit files.
- **Attempt 3 COUNTS:** banner `gpt-5.6-sol` / `high` (= `strong.config.toml`); `^ERROR` 0; `^tokens used` 1 (629,503); `^NEW_CRITICAL_MAJOR_FOUND` 2, `^NO_NEW_CRITICAL_MAJOR` 0; exit file 0, written after codex returned. Prior-findings reach: none (hits are prose: a plan line, CLAUDE.md and docs text). No content-filter event.
- **Evidence:** `review-r3.txt` (1,583,336 bytes), `prompt-r3.md` (387,519 bytes), `exit-r3.txt`, and the two disqualified attempts, in `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\`.
- **Spend:** counted rounds 403,744 + 954,070 + 629,503 = **1,987,317**; the disqualified attempt 2 burned a further 205,483 (attempt 1 printed no footer).

### Round 3 adjudication (premises re-checked at `084c9a3a`)

- **D79-A-01 (major): ACCEPTED as real; ROUTED for a ruling on the shape, because the fix changes what Fork 2's synthesized entry is.** The synthesized entry (`routes/trades.py:3134` region) carries only the top-level quartet and order id, so a no-selection submission on a multi-entry map drops the default candidate's map `possible_duplicates`: a K7.2 possible partial of the default order (o2) is never asked, and the DB-derived (c) scan does not recover a partial or an entered-date value-tuple match. RA-03 widened the shape (an omitted radio is now no selection), but the bare Fork 2 shape (T6-h, no candidate inputs) had the same gap. **Branch A:** keep the synthesis, and give the synthesized entry the `possible_duplicates` of the UNIQUE map entry whose `order_id` equals the top-level `schwab_order_id` and whose values equal the top-level quartet; with zero or several such entries, take the G1 re-confirm. **Branch B:** with a map present and no selection, there is no synthesis at all: the selected entry IS that unique map entry (by order id and values), so every map-side flag applies as for a picked candidate; zero or several -> G1 re-confirm. Synthesis then stays for the map-less no-selection shape only. RED test either way: a default o2 carrying a possible partial, submitted with the radio omitted -> 400, the partial asked, no fill.
- **D79-A-02 (major): ACCEPTED, to fix.** `_exit_values_well_formed` (`:2483`) calls `float(price_value)` on a JSON int; a 401-digit int parses (verified: `json.loads` returns an `int`) and `float()` raises `OverflowError` (verified), so tier (d) and the selected-entry check 500 instead of 400. Catch `OverflowError` -> not well formed.
- **D79-A-03 (major): ACCEPTED, to fix.** `check_exit_preconditions` (`exit.py:407`) computes `float(trade.current_size) - float(req.shares)`, which raises `OverflowError` for a huge int, so the sixth refusal ("exceeds") is not the raised error. The pre-arc `record_exit` had the same subtraction (`618d7b04:182`), so this is pre-existing, carried into the pure helper whose contract is "exactly the six refusals". Fix: compare without float conversion of `req.shares` (or translate the overflow into the existing "exceeds" text); helper test plus one caller test.
- **D79-A-04 (minor): ACCEPTED, to fix without a round.** `routes/trades.py:3154` still says "quantity as an int"; a residual of D79-A1 that the A1 class re-grep missed (it searched for `int(`, not the prose).
- **D79-A-05 (minor): ACCEPTED, to fix without a round.** The `candidate_orders` legacy fallback (`:3196` region) and the retention-rule coverage list (`:3274` region) describe a map-less selected envelope that RA-02's early return makes unreachable; remove the fallback and rewrite the list by replacement.

Round 3: 3 majors, all new, none reopened, no reverts. Not converged.

### Orchestrator QA of round 3 (against disk, `350496db`)

- I re-read the assertions from `review-r3.txt`: banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `strong.config.toml`; `^ERROR` 0; `^tokens used` present, 629,503; anchored verdict tokens `NEW_CRITICAL_MAJOR_FOUND` x2, the other token 0; `exit-r3.txt` reads 0. **Round 3 COUNTS.** The two capacity-aborted attempts do not count, and their transcripts are preserved. Counted spend to date: 1,987,317.
- Eight commits `270587c6`..`350496db`. Trailers are empty across `618d7b04..HEAD`. No file was added under `swing/`, and nothing under `swing/data/` changed. The tree is clean, and the stash stack holds only the pre-existing entry.
- D79-A-02, A-03, A-04 and A-05 are accepted as the cell adjudicated them. A-03 is pre-existing (`618d7b04:182`), but it is in scope because the helper's contract is "exactly the six refusals".

### FORK D79-A-01 -- the no-selection shape on a map-bearing claim drops the default candidate's flags (RULED: orchestrator, branch B)

> **Orchestrator ruling, D79 executing Fork D79-A-01 (2026-10-19).** **Branch B.** A claimed envelope that carries a `candidates_map` and no selection is NOT synthesized. Its selected entry IS the unique map entry whose `order_id` equals the top-level `schwab_order_id` and whose values derive from the top-level quartet at the ONE grain (`derives_from`; no second comparator). That entry is then treated exactly as a picked candidate: its map-side flags (`possible_duplicates`) are asked; its order id scopes the flag identities; and the persisted envelope stamps its map key as `selected_candidate_signature_hash`, its order id as `selected_candidate_order_id`, and the other keys as `other_candidate_signature_hashes`. With zero or several such entries, the POST gets the Fork 3 G1 response: 400, the refresh notice, the fresh anchor, the typed values kept, nothing recorded. The Fork 2 synthesis remains ONLY for the map-less, no-selection shape, and the comment at the one synthesis site says so. This narrows Fork 2 by replacement a second time, after Fork RA-02. Reason: branch A builds one entry from two sources, values from the top level and flags from the map, which must then be kept in agreement; branch B reads one source, the map entry. That is the direction the route already took for the order id (Codex R2 Major #2: "Reading ONE source") and the direction of RD's K3 precondition (4): a confirmation with no selected id is anonymous. Under branch A, the no-radio multi-entry confirm would still persist no selected hash. Under branch B it persists the default it showed. Required RED test, the cell's: a default o2 carrying a possible partial, submitted with the radio omitted, returns 400 with the partial asked and no fill. Also required: T6-h, the bare multi-entry shape, is re-run. Its three legs and its confirm leg are expected green unchanged, because the resolved entry equals the quartet it used to synthesize. A red there is classified SUPERSEDED (named) or REGRESSION. Any other red from the change is found by a run of `tests/web/test_routes/` and classified the same way.

Author of the sections above: orchestrator.

## Cell 5 (implementer-opus-high, dispatched off `df7a74e7`)

Author of this section and of the round-4 records below: cell 5.

| Commit | Item | Note |
|---|---|---|
| `38dfca51` | D79-A-01 | Fork D79-A-01 branch B: a map-bearing claim with no selection resolves to the unique map entry whose `order_id` equals the top-level id and whose values the top-level quartet derives from; it is a picked candidate (flags asked, identities scoped, hashes stamped, the re-render checks its radio); zero or several -> the G1 re-confirm; synthesis only for the map-less no-selection shape, its comment rewritten by replacement. RED, all four red before: the ruled partial case (radio omitted, and again with no candidate inputs: 200 -> 400 asking `possible_partial\|o2\|F`, its confirm stamping o2), the unedited radio-omitted stamping, zero matches (top-level o9), several matches (a client-edited map with two keys carrying o2's identical entry; the POST never recomputes a key, so the map CAN carry them). T6-h and its confirm leg green UNCHANGED. 1 SUPERSEDED (named in the body), no regression |
| `9e83c421` | D79-A-02 | `_exit_values_well_formed` catches `OverflowError` -> not well formed; RED at both callers (tier (d), the selected-entry check), each a 500 before |
| `cbb44c82` | D79-A-03 | the "exceeds" bound is `req.shares > trade.current_size` (no `float(req.shares)`), same text; RED: a helper test and a route caller test, both `OverflowError` before |
| `6268fabd` | D79-A-04 | the F1 comparator comment names the `isclose` grain; the prose re-grep's hits are listed in the body |
| `33a3bfa2` | D79-A-05 | the `candidate_orders` fallback and its write-only collection removed; the retention drop's coverage paragraph and the presence comment rewritten by replacement; two more stale `candidate_order_id_<i>` comments fixed (the route signature comment, `build_exit_form_vm`) |

- **A-01 supersession** (`tests/web/test_routes/` in full, 1189 passed after the rewrite): SUPERSEDED, rewritten by replacement: `test_exit_post_audit_columns.py::test_b_review_major1_present_but_empty_candidates_map_drops_the_order_id`, now `..._is_reconfirmed`. Encoding 18 below is why. REGRESSION: none.
- **Encodings cell 5 made without a fork** (round 4's prompt carried each, challenge invited; round 4 raised none of them):
  18. "Carries a `candidates_map`" is KEY PRESENCE (the retention rule's own test), so a no-selection claim with an EMPTY map resolves to zero entries and re-confirms instead of recording with the id dropped.
  19. The resolved entry's `other_candidate_signature_hashes` are the other MAP keys (the bare shape sends no per-candidate inputs); a picked candidate's stay the other submitted hashes.
  20. The resolution compares the top-level id with `==` after `.get`, so a null or absent top-level id matches an entry with no order id. `resolve_exit_auto_fill` writes both from the same chosen candidate, and such an entry links nothing (a non-string or blank selected id pops the top-level id).
  21. The POST no longer collects `candidate_order_id_<i>` (its only reader was the removed fallback); the template still emits the inputs.
- Full fast suite on `33a3bfa2`, read off the saved output: **15475 passed, 13 skipped, 0 failed** (1019.20 s) = 15467 + the 8 new tests. `ruff check swing/` clean; `%(trailers)` empty across `618d7b04..HEAD`; no added file under `swing/`; nothing under `swing/data/`.

### Round 4

Same form: `codex exec -p strong -s read-only --skip-git-repo-check -` from the worktree, runner `~/d79r4/run_r4.sh` (literal paths; `file` reports ASCII; the output and exit files pre-created). The prompt was rebuilt on `33a3bfa2`:
- the claim list rewritten for D79-A-01 (item 3), A-02 (item 8) and A-03 (item 1);
- the envelope; AL-1..AL-9 with their reasons;
- SEVEN rulings (exec ledger lines 1-179, 206-218, 293-295 and 344; the D79-A-01 ruling under a neutral heading);
- choices 1-4 and 6-21, challenge invited;
- the `618d7b04..HEAD` diff with this ledger excluded, and no prior finding text.

- **Attempt 1 DID NOT COUNT (capacity abort):** exit 1, 1,037,635 bytes, two `^ERROR: Selected model is at capacity`, footer 229,482, NO verdict token. Preserved as `review-r4-attempt1-capacity.txt` with `exit-r4-attempt1.txt`. Re-run after a five-minute wait.
- **Attempt 2 COUNTS:**
  - banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `~/.codex/strong.config.toml` (`model = "gpt-5.6-sol"`, effort `high`);
  - `^ERROR` 0; `^tokens used` 1 (440,564);
  - `^NEW_CRITICAL_MAJOR_FOUND` 2 (the CLI's double emission), `^NO_NEW_CRITICAL_MAJOR` 0;
  - exit file 0, written after codex returned, and no `codex exec` process alive when the transcript was read.
- **Prior-findings reach: none.** The hits for the forbidden names are prose: the prompt echo, one diff line, and `docs/orchestrator-context.md` text Codex read. Its one search command excluded the `*review*` and `*findings*` globs. The response says no prohibited artifact and not the ledger was opened. **Content-filter events:** none ("The prompt was not rewritten or refused").
- **Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\` holds `review-r4.txt` (1,474,226 bytes), `prompt-r4.md` (417,985 bytes), `exit-r4.txt`, and the disqualified attempt, copied once the assertions passed.
- **Spend:** counted rounds 403,744 + 954,070 + 629,503 + 440,564 = **2,427,881**. Disqualified attempts burned a further 205,483 (round 3) and 229,482 (round 4).

### Round 4 adjudication (premises re-checked at `33a3bfa2`)

- **A-F01 (major, tagged [OUT-OF-ENVELOPE] by the reviewer): ACCEPTED as real; ROUTED for a scope ruling, not fixed.**
  - The defect, verified by read: `record_exit` COMMITs (`swing/trades/exit.py:583`) and only then computes `compute_realized_pnl`, `compute_initial_risk_per_share` and `compute_r_multiple` (`:588-605`). `get_trade`'s mapper (`swing/data/repos/trades.py:827-855`) passes `entry_price` and `initial_stop` through unconverted. Both columns are `REAL NOT NULL` with no type CHECK, so a TEXT value is storable (SQLite keeps an unconvertible string in a REAL column as TEXT; RA-01 measured the same for `fills`). The math then raises `TypeError` AFTER the exit is durable. The route's 22-F guard sees `result is None` and re-raises, and the CLI likewise reports failure: the operator is told a durable exit failed, which is the double-exit direction. `r_multiple`'s own `ValueError` is unreachable (`rps > 0` and `shares >= 1`).
  - **Pre-arc:** `618d7b04:281-298` carries the identical post-commit math. The arc rewrote the transaction around it and left it after `commit`.
  - **Envelope:** the reviewer tags it out of envelope, but the code a fix would change is `record_exit`'s transaction shape, inside CHARC's K1 carve-out.
  - **Branch A (fix in the carve-out):** compute the three metrics inside the `try`, before `conn.commit()`, so a raise there takes `_rollback_or_raise` like any other in-transaction failure; only the `ExitResult` construction stays after the commit. RED: plant `trades.entry_price = 'bad'` by raw UPDATE and call `record_exit`. Before the fix it raises after COMMIT with one exit fill; after it, it raises with zero. Cost: about ten moved lines and no new read. The "post-commit; pure math" comment is rewritten by replacement.
  - **Branch B (BANK):** the defect predates the arc and is premised on a TEXT value in a REAL column. A service-prevention citation needs the writer enumeration WITH its search, plus the live incidence, and this cell cannot complete either:
    - the static writers include two dynamic-SQL updaters whose value types must be read: `swing/data/repos/trades.py:965` (a `set_clauses` builder) and `swing/trades/reconciliation_auto_correct.py:2350` (the PRAGMA-allowlist corrector);
    - the incidence is a data read outside this cell's authorization: `SELECT typeof(entry_price), typeof(initial_stop), COUNT(*) FROM trades GROUP BY 1, 2`, `mode=ro`.
    - Proposed owner: the orchestrator. Proposed trigger: the next arc with a `record_exit` carve-out.
  - The cell does not choose. Its lean, for the record: A. The 22-F guard's contract ("once `record_exit` RETURNS the exit is DURABLE") assumes the converse as well, and a raise after COMMIT breaks it on a path the arc's own transaction rewrite owns.
- **A-F02 (minor): ACCEPTED, to fix without a round.** Verified: `_exit_values_well_formed` (`routes/trades.py:2493-2495`) checks only `isinstance(shares_value, int)`, so a `closed_shares` or a selected entry's `quantity` of `10**400` is well formed. That contradicts the predicate's new docstring sentence and round 4's claim 8 (the cell wrote claim 8 too broadly). Downstream it reaches a different 400 (the resolution's zero-match re-confirm, or F1 through `derives_from`'s caught overflow), never a 500. But a tampered selected entry could persist a huge `closed_shares` in the audit envelope after a confirmed F1. Fix: the quantity gets the same `float()` / `OverflowError` / finiteness test; RED at both callers.
- **A-F03 (minor): ACCEPTED, to fix without a round.** Every site verified:
  - `routes/trades.py:2991-2992` (the reviewer cited `:2986`, the start of the block): the omitted-radio comment still says "takes the Fork 2 synthesis". This cell's A-01 re-grep searched the route for the fallback prose, not for "synthesis".
  - `tests/web/test_routes/test_d79_exit_identity.py`: T6-h's name and docstring and its confirm leg's name ("synthesizes the default"), and RA-03's docstring (`:514`).
  - plan `:335`: T6-g's first leg still says it returns the F1 flag, superseded by Fork 3 (G1).
  - `trade_exit_form.html.j2:102-106`: the comment still says `candidate_order_id_<i>` lets the POST check the selection. This cell's A-05 re-grep covered the route and the view model, not the template.
  - The test renames are a naming change only, to land apart from any behaviour change.
- **A-F04 (minor): ACCEPTED, test to add.** Verified: T1-a (`tests/trades/test_d79_record_exit_txn.py:170`) spies only `get_trade` and passes no envelope. A caller-held check moved after `_normalize_trade_event_date_to_iso` and `canonical_envelope_identity` (`exit.py:464-475`) but before `get_trade` would still pass it. Add a caller-held call carrying an envelope, with the authority spied, asserting `CallerHeldTransactionError` and zero authority calls.

Round 4: 1 major (A-F01, routed), 3 minors, all new, none reopened, no reverts. Not converged. Per the brief this is the last round before the round-5 check-in, so no round 5 is started.
