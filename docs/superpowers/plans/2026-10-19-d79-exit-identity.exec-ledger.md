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
| 4 | `33a3bfa2` | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (440,564) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 1 | 3 | 4 new / 0 reopened | 0 | 345,780 (cell 5 at return; retired) |
| 5 | `f70ebdc8` | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (475,309) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 2 | 4 | 5 new / 1 reopened (R5-06, RA-07's site) | 0 || 282,116 (cell 6 at return; resumed) |
| 6 | `d539d273` | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (430,882) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 2 | 0 | 2 new / 0 reopened | 0 || 374,140 (cell 6 at return; retired) |
| 7 | `c5cb5850` (code `783ec4f9`) | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (459,279) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 2 | 0 | 2 new / 0 reopened | 0 | 396,198 (cell 7 at return; retired) |

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

### Orchestrator QA of round 4 (against disk, `9d1bb48c`)

- I re-read the assertions from `review-r4.txt`: banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `strong.config.toml`; `^ERROR` 0; `^tokens used` present, 440,564; anchored verdict tokens `NEW_CRITICAL_MAJOR_FOUND` x2, the other token 0; `exit-r4.txt` reads 0. **Round 4 COUNTS.** The capacity-aborted attempt 1 does not count, and its transcript is preserved. Counted spend to date: 2,427,881.
- Six commits `38dfca51`..`9d1bb48c`. Trailers are empty across `618d7b04..HEAD`. No file was added under `swing/`, and nothing under `swing/data/` changed. The tree is clean, and the stash stack holds only the pre-existing entry.
- **A-F01, live incidence (orchestrator, `mode=ro`, 2026-10-19):** `SELECT typeof(entry_price), typeof(initial_stop), COUNT(*) FROM trades GROUP BY 1,2` returns `[('real','real',28)]`, and `typeof(current_size)` returns `[('real',28)]`. The failure is LATENT on live, not present.
- I verified the premise at `swing/trades/exit.py`: `conn.commit()` closes the `try`, and the P&L, risk-per-share and R-multiple are computed after it.

### Operator confirmation of the executing go (2026-10-19)

> "I did mean for a go"

Operator author, orchestrator courier. Said in the orchestrator session after the round-3 status, it closes the open question on CHARC's relayed "dispatch D79" (`20261019T022435Z`).

### FORK A-F01 -- the exit metrics are computed after the commit (RULED: orchestrator, branch A)

> **Orchestrator ruling, D79 executing Fork A-F01 (2026-10-19).** **Branch A.** The realized P&L, risk-per-share and R-multiple computations move inside `record_exit`'s `try`, before `conn.commit()`, so a failure there rolls the exit back through `_rollback_or_raise`. Only the `ExitResult` construction stays after the commit. The "post-commit; pure math" comment is rewritten by replacement, and the docstring's transaction paragraph names the change. Reason: this arc's route guard (22-F) and the CLI both read a raise from `record_exit` as "nothing was recorded". Today, a durable exit can be reported as failed, which invites the second exit this arc exists to prevent. The fix is about ten moved lines in a function the arc already owns, adds no read, and costs no extra round, because round 5 runs either way. The live incidence is zero, so this is a latent hazard closed, not a live defect repaired. Banking it (branch B) would leave the arc's own contract ("a refusal records nothing") false on a path it has just rewritten. Required RED test, the cell's: `trades.entry_price` set to TEXT by raw UPDATE, then `record_exit` raises with zero exit fills written (one before the fix). Also required: the existing `record_exit` tests stay green, and any red is classified SUPERSEDED (named) or REGRESSION.

**Encoding 18 confirmed** (orchestrator): an empty `candidates_map` is a map that names no entry, so a no-selection claim carrying one has zero matches and takes the G1 re-confirm under the D79-A-01 ruling. The superseded `..._drops_the_order_id` test, rewritten as `..._is_reconfirmed`, is the ruling's intended effect.

**Round-5 check-in: APPROVED to continue** (orchestrator, per the recipe's round-5 rule and the suspended round cap). The trend is 3, 3, 3, then 1 major. Round 5 runs on the head carrying A-F01 to A-F04.

Author of the sections above: orchestrator.

## Cell 6 (implementer-opus-high, dispatched off `df3cceb1`)

Author of this section and of the round-5 records below: cell 6.

| Commit | Item | Note |
|---|---|---|
| `1d47ec02` | A-F01 | Fork A-F01 branch A: the realized P&L, risk-per-share and R-multiple are computed inside `record_exit`'s `try`, before `conn.commit()`, and only the `ExitResult` construction follows it; the post-commit comment and the docstring's transaction paragraph are replaced. RED: `trades.entry_price` planted as TEXT by raw UPDATE raised `TypeError` with ONE exit fill durable; it now raises the same `TypeError` with ZERO, state and size unchanged, no open transaction. The test asserts the type is exactly `TypeError` and not a `ValueError` (CHARC's 2026-10-19 addition, relayed mid-cell; its transcription is left to the orchestrator). Every test file referencing `record_exit` (20 files) re-run: 656 passed, nothing SUPERSEDED, no REGRESSION |
| `d05266a1` | A-F02 | the quantity is held to the price's finite bound in `_exit_values_well_formed`; both rejection texts now say "a finite integer" (no test pinned the old text). RED at both callers with a 401-digit int. **The measured pre-fix path differs from round 4's adjudication** for the top-level `closed_shares`: 200, not "a different 400". The form's checked radio selected an entry whose values replaced the tampered top level, and the POST recorded; the test docstring states the measured path. `tests/web/test_routes/` in full: 1194 passed, nothing SUPERSEDED, no REGRESSION |
| `7e5723a4` | A-F04 | the caller-held test carrying an envelope with the authority spied: `CallerHeldTransactionError`, zero authority calls. A pin (green both ways); discrimination measured by mutation -- the check moved to just before `BEGIN IMMEDIATE` fails it while T1-a stays green |
| `6f22df7d` | A-F03 | prose by replacement: the omitted-radio comment (`routes/trades.py:2990`), the template's candidate-list comment, plan T6-g's first and confirm legs. The class re-grep (every file in the `618d7b04` diff except the two ledgers, for "synthes" and `candidate_order_id`) and every hit's disposition are listed in the commit body |
| `f70ebdc8` | A-F03 | the naming change in its own commit: `test_t6h_..._synthesizes_the_default` -> `..._resolves_the_default`, `test_t6h_confirm_leg_the_synthesized_default_...` -> `..._the_resolved_default_...`, RA-03's docstring; no assertion changed |

- Full fast suite on `f70ebdc8`, read off the saved output: **15479 passed, 13 skipped, 0 failed** (656.44 s) = 15475 + the 4 new tests. `ruff check swing/` clean; `%(trailers)` empty across `618d7b04..HEAD`; no added file under `swing/`; nothing under `swing/data/`.

### Round 5

Same form: `codex exec -p strong -s read-only --skip-git-repo-check -` from the worktree, runner `~/d79r5/run_r5.sh` (round 4's with `r4` replaced by `r5`; `file` reports ASCII; the output and exit files pre-created). The prompt is round 4's frame rebuilt on `f70ebdc8`:
- claim 1 extended (the metrics before the COMMIT; the math's own error escaping, never a `ValueError`); claim 8 extended (the quantity bound);
- the envelope's K1 carve-out naming Fork A-F01; AL-1..AL-9 with their reasons;
- EIGHT rulings: the seven of round 4, plus FORK A-F01 (its block quote from this ledger). CHARC's A-F01 addition is quoted in the rulings section with its attribution; choices 1-4 and 6-21, challenge invited;
- the `618d7b04..HEAD` diff with this ledger excluded (381,873 bytes), and no prior finding text.

- **Assertions** (run from a script file; a first inline read was discarded because the harness expanded its `$(...)` on the Windows side and the counts were unusable):
  - banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `~/.codex/strong.config.toml`;
  - `^ERROR` 0; `^tokens used` 1 (475,309);
  - `^NEW_CRITICAL_MAJOR_FOUND` 2 (the CLI's double emission), `^NO_NEW_CRITICAL_MAJOR` 0;
  - exit file 0, written by the runner after codex returned. The three `codex exec` processes alive at read time belong to another project's review (`coa-chess-dispatch/v19-reader`), not this round.
  - **Round 5 COUNTS.** One attempt; no capacity abort.
- **Prior-findings reach: none.** Codex's 53 commands read CLAUDE.md, `docs/orchestrator-context.md`, the plan and source. The hits for the forbidden names are the prompt echo, a plan line naming the round-0 probe path, and docs prose. **Content-filter events:** none reported.
- **Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\` holds `review-r5.txt` (1,615,254 bytes), `prompt-r5.md` (433,778 bytes) and `exit-r5.txt`, copied once the assertions passed. `copowers-findings.md` there carries round 5's verbatim final message.
- **Spend:** counted rounds 403,744 + 954,070 + 629,503 + 440,564 + 475,309 = **2,903,190**. Disqualified attempts burned a further 205,483 (round 3) and 229,482 (round 4); there were none this round.

### Round 5 adjudication (premises re-checked at `f70ebdc8`)

The reviewer's ids `D79-A01`..`D79-A06` collide with round 3's `D79-A-01`..`A-05`. They are recorded here as **R5-01..R5-06**, in the reviewer's order.

- **R5-01 (major): ACCEPTED as real; ROUTED as a fork, because it challenges AL-6's reason, which is ruling text.**
  - The defect, verified by read: the resolver labels a VALUE-TUPLE match when an anonymous row's date is the candidate's execution date OR its order's ENTERED date (`exit_auto_fill.py:1471-1474`, `dates = {candidate.date, entered_date}`; tested at `:1580`, `row.date in dates`). The POST's DB-side (c) recheck (`anonymous_fill_matches`, `:1882`, called at `routes/trades.py:3585`) compares the TYPED tuple only, through `derives_from`. Take an order entered May 20 and executed May 21, and an anonymous fill F on May 20 at the same price and quantity. F is a map-side `value_tuple_match` on the unedited form but not a DB-side match. A client that strips F from the submitted entry's `possible_duplicates` suppresses the question, and the first POST records.
  - The server cannot recompute it. The map entry carries `date`, `date_source`, `price`, `quantity`, `order_id` and `possible_duplicates` (`:1012-1033`), and NOT the entered date, which lives only in the GET-time Schwab order. AL-6's sentence "the (c) value-tuple flags ... are NOT client-trusted (re-run from the DB at every POST)" is therefore true for the execution-date grain and false for the entered-date grain.
  - **Branch A (a server-authenticated superset):** the DB-side recheck gains an ALTERNATE-DATE channel. An anonymous non-entry fill on this trade is flagged when the typed values' price and quantity derive from it at the one grain (`derives_from` over the row with its date replaced by the typed date, so there is no second comparator) and it is dated on or BEFORE the typed exit date. An entered date never follows its execution date; the resolver's own window comment says no validated order carries one. The flag carries its own text naming the row's earlier date (R5-03 folds in). Cost: a spurious flag for an older same-trade anonymous fill at an identical price and quantity, which is the alarm direction this surface is built on. RED: the reviewer's case with F stripped from the map expects 400, F named and no fill (200 before the fix).
  - **Branch B (an accepted limitation, by replacement):** AL-6 is amended so the entered-date-grain value-tuple match joins the K7.2 partials as client-trusted on the FIRST POST. The reason is the same: the entered date is not in the envelope, and the first POST does not re-fetch Schwab (pinned by `test_d_post_does_not_emit_new_schwab_api_call_audit_row`). The execution-date grain stays DB-rechecked. There is no code change for R5-01, and R5-03's text fix still lands.
  - The cell does not choose.
- **R5-02 (major, tagged [AGAINST-RULING] against Fork D79-A2): ACCEPTED as real; ROUTED as a fork.**
  - The defect, verified by read: `exit_record_flags` (`exit_auto_fill.py:2153-2181`) gives a DB-derived (c) match and a SELECTED-ENTRY map `value_tuple_match` the same identity, `value_tuple_match|<fill_id>` (`add(FLAG_VALUE_TUPLE, str(fill_id), text)`). Fork D79-A2 kept that subject on the reason "the (c) question is about the typed exit against an anonymous fill, which a radio switch does not change". That holds for the DB-derived source. It does not hold for the map-derived source, which is the selected order's own list. The reviewer's scenario: o1 and o2 share one price and quantity, and F is dated o1's execution date and o2's entered date. With o1 picked, F is asked as `value_tuple_match|F`. The operator then switches the radio and the values to o2 and presses Confirm with o1's acknowledgements. The map is unchanged, so d2 passes. o2's map-side F carries the same identity, so it is discharged by an acknowledgement given to o1's question.
  - **Branch A (scope the map-derived identity):** a map-derived value-tuple item gets `value_tuple_match|<order key>|<fill_id>`, the same order key the partial and unreadable identities use, while a DB-derived match keeps `value_tuple_match|<fill_id>`. When both sources name one fill, ONE flag is emitted under the DB-derived identity, which is order-independent and asks a superset question. RED: the browser switch test, analogous to the D79-A2 partial test (400, re-asked, no fill; 200 before the fix). Any of T7-a's asserted identities that is map-derived is updated by replacement.
  - **Branch B (keep the ruling, with an accepted limitation):** record AL-10: a map-derived value-tuple acknowledgement is fill-scoped, so it carries across a radio switch on an unchanged map. The reason to weigh: the switch shape needs two candidates at an identical price and quantity whose execution and entered dates straddle one anonymous fill.
  - Interaction: under R5-01 branch A, the scenario's o2 confirm would also be asked the new DB-side alternate-date flag (F is dated before o2's typed date, at the same price and quantity), under its own identity. That closes this instance but not the class: the map-side identity stays fill-scoped, and a map-derived match the DB recheck cannot see (outside its date rule) still carries over. R5-02's branch A is independent of R5-01's ruling.
  - The cell does not choose.
- **R5-03 (minor): ACCEPTED, to fix without a round; its shape depends on the R5-01 and R5-02 rulings.** A map-side value-tuple match on the order's ENTERED date renders "These values match recorded fill #F (...)" when the typed date is the execution date, which states a false equality on an unmodified form. Fix: a separate template for an alternate-date match that names the order and says the price and quantity match while F's date is the order's entered or offered date. `FLAG_TEXT_TEMPLATES` and its closure test take the new name.
- **R5-04 (minor): ACCEPTED, to fix without a round.** Verified: `routes/trades.py:3241` tests `flag_selected_signature_hash` by truthiness, so a client-edited map whose unique resolved entry sits under the key `""` records with no `selected_candidate_*` or `other_candidate_signature_hashes` stamp. Fix: `is not None` at :3241 (the restore hand-off at :3517 passes the value through without a truthiness test, so it is unaffected). RED: a map re-keyed to `""`, with the radio omitted, stamps `""` as the selected hash.
- **R5-05 (minor): ACCEPTED, to fix without a round.** Verified: `tests/data/test_22f_inv_model_roster.py:182-184` says `ExitRecordFlag.__post_init__` is reached from the CLI `trade exit`, but the CLI formats `_VALUE_TUPLE_TEXT` directly (`swing/cli.py:1489`, `:1520`) and never constructs the flag. Fix: name only the web exit POST. The classification ("computed") stands.
- **R5-06 (minor, [OUT-OF-ENVELOPE]): NOT fixed; proposed BANKED with RA-07.** `swing/data/repos/fills.py:6` is RA-07's own site (BANKED in round 2; REOPENED here). `swing/trades/state.py:130` ("caller's `with conn:`") is the same class of prose at a new site outside the envelope, because `state.py` is not in the K1 carve-out. Proposed owner and trigger: RA-07's (the orchestrator; the next arc with a `fills.py` carve-out, or a docs rider), widened to name `state.py:130`.

Round 5: 2 majors (R5-01 and R5-02, both routed), 4 minors, 5 new and 1 reopened (R5-06, at RA-07's site), no reverts. Not converged. The minors are not fixed at this gate, because the brief has minors fixed here only on a clean round; they are queued with the fork rulings.

### CHARC on Fork A-F01 (2026-10-19T08:01:18Z; CHARC author, orchestrator courier)

Transcribed from `comms/orchestrator/inbox/20261019T080118Z-charc-d79-exec-a-f01-touches-k1-1-adopted-as-i.md`, the two operative paragraphs:

> CHARC, D79 exec Fork A-F01: it DOES touch the K1 (1) transaction shape, and I ADOPT the orchestrator's branch A as that shape's own consequence. No change to the ruling; no second ruling.

> One thing to keep, stated so the cell does not "improve" it: the raise that escapes is a TypeError (or whatever the math raises), NOT re-dressed as a ValueError. It is a corrupt-row programming fault, not an operator refusal, and the callers' except ValueError must NOT re-render it as a form error; the 22-F guard's "recorded nothing, failed" is the truthful report after the rollback. Same reasoning as CallerHeldTransactionError being a RuntimeError.

Relayed to cell 6 in flight; `1d47ec02`'s RED asserts the type is exactly `TypeError`.

### Orchestrator QA of round 5 (against disk, `6d50efe4`)

- I re-read the assertions from `review-r5.txt`: banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `strong.config.toml`; `^ERROR` 0; `^tokens used` present, 475,309; anchored verdict tokens `NEW_CRITICAL_MAJOR_FOUND` x2, the other token 0; `exit-r5.txt` reads 0. **Round 5 COUNTS.** Counted spend to date: 2,903,190.
- Six commits `1d47ec02`..`6d50efe4`. Trailers are empty across `618d7b04..HEAD`. No file was added under `swing/`, and nothing under `swing/data/` changed. The tree is clean, and the stash stack holds only the pre-existing entry.
- I verified R5-02's premise by read: `exit_record_flags` appends the DB-derived matches and the selected entry's map `value_tuple_match` items into one list, and gives both `add(FLAG_VALUE_TUPLE, str(fill_id), text)`. Only the partials carry `order_key`.
- **R5-06: BANKED with RA-07, widened** (orchestrator). The owner is the orchestrator. The trigger is the next arc with a `swing/data/repos/fills.py` or `swing/trades/state.py` carve-out, or a docs rider. Sites: `fills.py:6` and `state.py:130`.
- **R5-01 is ROUTED to RD**, because it challenges AL-6's width, which is RD's P2 CORRECTION 2 (plan ledger :330). That correction rested on "a client that strips the map's `value_tuple_match` flags still gets the ask", which holds for the execution-date grain and not for the entered-date grain. One ruler per item: RD rules R5-01, and R5-03's text shape follows that ruling.

### FORK R5-02 -- a map-derived value-tuple acknowledgement survives a radio switch (RULED: orchestrator, branch A)

> **Orchestrator ruling, D79 executing Fork R5-02 (2026-10-19).** **Branch A.** A value-tuple item taken from the selected entry's map `possible_duplicates` gets the identity `value_tuple_match|<order key>|<fill_id>`, with the same order key the partial and unreadable identities use. A DB-derived (c) match keeps `value_tuple_match|<fill_id>`. When both sources name one fill, ONE flag is emitted, under the DB-derived identity. This corrects my Fork D79-A2 ruling by replacement, on the reason that ruling gave: "the (c) question is about the typed exit against an anonymous fill, which a radio switch does not change" is true of the DB-derived source and false of the map-derived one, which is the selected order's own list, exactly like the partials D79-A2 scoped. So the rule is now one rule: a question drawn from an order's list is scoped to that order, and a question drawn from the typed values against the DB is not. Branch B would keep an acknowledgement given to o1's question discharging o2's, the same carry-over D79-A2 closed for partials. Required RED test, the cell's: the browser switch shape (o1 and o2 at one price and quantity; F dated o1's execution date and o2's entered date; o1 picked, flagged; radio and values switched to o2; Confirm with o1's acknowledgements) returns 400, re-asked, no fill (200 before the fix). Also required: a dedup test where both sources name F, asserting ONE flag under `value_tuple_match|<F>`. Any of T7's asserted identities that is map-derived is updated by replacement and named; any red elsewhere is classified SUPERSEDED (named) or REGRESSION. This ruling is independent of RD's ruling on R5-01.

Author of the sections above: orchestrator.

## Cell 6, resumed off `d92fce98`

Author of this section and of the round-6 records below: cell 6.

| Commit | Item | Note |
|---|---|---|
| `d5934658` | R5-02 | Fork R5-02 branch A in `exit_record_flags`: a map-derived value-tuple item is `value_tuple_match\|<order key>\|<fill_id>`, a DB-derived match keeps `value_tuple_match\|<fill_id>`, and a fill both sources name is asked ONCE under the DB identity; both docstrings and the plan's identity naming line replaced. RED: the browser switch test (o1 and o2 at 130.00 x 3, F on o1's execution date and o2's entered date; o1 flagged, radio and values switched to o2, confirmed with o1's acknowledgement) recorded o2 before the fix (200), and now 400 asks `value_tuple_match\|o2\|F`; the order-scoped unit test was red (`value_tuple_match\|7`). The dedup test is a PIN against the fix's own no-dedup null (green before, since the two identities were then equal). T7 identities: `tests/web/test_routes`, `tests/trades` and the d79 CLI tests gave 4348 passed, 8 skipped, nothing red. The asserted value-tuple identities at `test_d79_exit_confirm.py:103` and `:423` are DB-derived (or deduplicated into one), and `:400` is a test-built acknowledgement, so nothing is SUPERSEDED |
| `80978d7e` | R5-04 | `is not None` at the resolved-key stamp. RED: o2's entry re-keyed to `""` with no candidate inputs recorded with no `selected_candidate_signature_hash` (KeyError), and now stamps `""`, o2 and o1's key. `tests/web/test_routes`: 1196 passed |
| `a48c189e` | R5-05 | the 22-F roster comment names only the web exit POST (the one caller of `exit_record_flags` under `swing/`, by grep: `routes/trades.py:3593`); comment only, so no RED |
| `2b62f07b` | R5-01 | RD's ruling, branch B: no code. AL-6 restated by replacement in the plan (`:40`) to RD's width, and the (c) bullet of `exit_record_flags`' docstring states it. RD's test condition: `test_al6_first_post_client_trust_width`, parametrized over the partial and the entered-date value-tuple cases, both legs (item present -> 400 asked under o1's order-scoped identity; item stripped -> the unedited first POST records one row). No existing route test documented the partials' first-POST trust (the unit test at `test_d79_exit_flags.py:243` covers malformed items), so the pin is a new test carrying both cases. It is green as written, and the arc that closes the width turns its stripped leg red |
| `d539d273` | R5-03 | `_VALUE_TUPLE_ENTERED_TEXT` for a map value-tuple item dated otherwise than the selected entry's date (the resolver matches only on the execution date or the order's entered date). It says the fill has the order's price and quantity and that its date is the order's ENTERED date, never "These values match"; `FLAG_TEXT_TEMPLATES` takes the name and its closure test passes. RED: a unit test and the width test's entered-date leg, both red on the old text |

- **A process slip, recorded:** while writing R5-03's tests, a helper script imported `edit` from the R5-01 script, and the import re-ran that module's top-level edits (a doubled docstring paragraph and a doubled width test). The run stopped at a failed assertion before anything was committed. Both files were restored with `git checkout --` to their committed `2b62f07b` state, and the R5-03 test edit was re-applied on its own. `d539d273`'s diff is the R5-03 change alone.
- Full fast suite on `d539d273`, read off the saved output: **15486 passed, 13 skipped, 0 failed** (968.34 s) = 15479 + the 7 new tests. `ruff check swing/` clean; `%(trailers)` empty across `618d7b04..HEAD`; no added file under `swing/`; nothing under `swing/data/`; no review scratch in the worktree.

### Round 6

Same form, runner `~/d79r6/run_r6.sh` (round 5's with `r5` replaced by `r6`; ASCII; output and exit files pre-created). The prompt is round 5's frame rebuilt on `d539d273`:
- claim 3 (any string key stamped, the empty one included) and claim 4 (the R5-02 identities, the dedup, the entered-date text) extended;
- AL-6 replaced by RD's width; AL-1..AL-5 and AL-7..AL-9 unchanged;
- NINE ledger rulings: round 5's eight, plus FORK R5-02 (its block quote from this ledger). The TENTH, RD's ruling on Fork R5-01, is quoted verbatim, ruling body only, with RD's attribution (its transcription instruction to the orchestrator is omitted). CHARC's A-F01 addition is carried as in round 5; choices 1-4 and 6-21, challenge invited;
- the `618d7b04..HEAD` diff with this ledger excluded (399,190 bytes), no prior finding text. Prompt 457,486 bytes.

- **Assertions** (script file, output read from a file, because the terminal's screen-size warning overwrote the first lines of the direct output):
  - banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `~/.codex/strong.config.toml`;
  - `^ERROR` 0; `^tokens used` 1 (430,882);
  - `^NEW_CRITICAL_MAJOR_FOUND` 2 (the CLI's double emission), `^NO_NEW_CRITICAL_MAJOR` 0;
  - exit file 0, written after codex returned; no `d79r6` process alive at read time.
  - **Round 6 COUNTS.** One attempt; no capacity abort.
- **Prior-findings reach: none.** None of the 33 commands touches a forbidden path. The name hits are the prompt echo and the same docs prose as round 5. **Content-filter events:** none reported.
- **Evidence:** `review-r6.txt` (1,589,629 bytes), `prompt-r6.md` (457,486 bytes) and `exit-r6.txt` in `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\`, copied once the assertions passed; `copowers-findings.md` there carries round 6's verbatim final message.
- **Spend:** counted rounds 403,744 + 954,070 + 629,503 + 440,564 + 475,309 + 430,882 = **3,334,072**. Disqualified attempts burned a further 434,965 (rounds 3 and 4); none this round.

### Round 6 adjudication (premises re-checked at `d539d273`)

Recorded as **R6-01** (the reviewer's `D79-A-06`) and **R6-02** (`D79-A-07`).

- **R6-01 (major): ACCEPTED as real by read; ROUTED as a fork, because what "the submitted envelope" means in CHARC's FORK 2 is CHARC's to read.**
  - The defect: the route parses the browser's raw anchor with `json.loads` (`routes/trades.py:2823`) and never passes that raw string to the authority. Its two authority reads are over the envelope the route PRODUCES (the T6 item 4 writer predicate at `:3430`, and `linked` at `:3561`), and `record_exit`'s pre-BEGIN read (F2-(iii), plan T2 `:144`) is over `req.schwab_source_value_json`, which is that same produced envelope. A selected entry's order id overwrites the top-level one (`:3311-3314`). So a raw anchor whose top-level id is padded (`" o2"`), or whose root carries duplicate identity keys, is normalized away when the selected map entry is canonical: the single-candidate form (index 0 inferred from the one-entry map) records it. For the map-less shape the padded id survives synthesis, and `:3430` refuses it (400), as designed.
  - What is and is not asserted: the persisted link is the selected map entry's id, which the (a) guard reads under the lock. The refused raw token is discarded, not recorded. The map entry is as client-editable as the top level.
  - **Branch A (a ladder rung on the raw anchor):** before parsing, `canonical_envelope_identity(schwab_source_value_json)` on the raw submitted string. A `refused` reading takes `_reject_anchor` (400, anchor cleared), as a tampered anchor; the producer check stays. RED: the reviewer's two browser-path cases (padded top-level id with a canonical selected entry; duplicate root identity keys), each 400, zero `record_exit` calls, no fill. Any test that submits such a raw anchor and expects a record is found by a run and classified.
  - **Branch B (an accepted encoding, recorded with its reason):** the authority guards what is PERSISTED and what `record_exit` is asked to write (F2-(iii) and the T6 producer check). The browser's anchor is an input whose top-level id the route REPLACES by the selected entry's (Codex R2 Major #2's "one source"), so a refused token in it is discarded and asserts nothing. Challenge stays invited.
  - The cell does not choose. Its lean, for the record: A. The ladder exists to reject tampered anchors, and a refused raw identity is the authority's own definition of one; the rung is one call.
- **R6-02 (major): ACCEPTED as real by read; ROUTED as a fork. It is PRE-ARC in class, and the arc's own retry guards mitigate its stated consequence.**
  - The defect: `record_exit`'s `conn.commit()` (`exit.py:613`) can raise with `in_transaction` already False, either after the commit is durable (an interrupt between the C call's return and Python's) or after SQLite's own rollback (an I/O error). Those two cases are indistinguishable on that connection. `_rollback_or_raise` returns without acting, and the original propagates. The route sees `result is None` and re-raises (`:3610` region); the CLI sees `durable=False`. A durable exit can therefore be reported as failed.
  - **Pre-arc:** `618d7b04:228` wrapped the same writes in `with conn:`, whose commit raise propagates identically. The arc did not create the window; it made the contract "a raise means nothing recorded" explicit (Fork A-F01 and CHARC's addition), and this path is the one case where the contract cannot be honoured without more information.
  - **Mitigation, verified by read:** a retry after such a durable exit is not silent. A LINKED exit's retry is refused by the (a) guard under the lock (and its order is no longer offered, T3). An ANONYMOUS exit's retry with the same typed values is asked the DB-derived (c) question at the route (`anonymous_fill_matches`, every POST) and refused at the CLI without `--confirm-duplicate`. A double exit therefore needs a retry with different values, or a confirmed (c) question.
  - **Branch A (the reviewer's settlement, OUT of this envelope):** a per-attempt, non-reusable token written co-durably with the fill (gotcha: the rolled-back rowid is reusable), and on a lost commit return a settlement on a FRESH connection, reporting degraded success when durability is proven. `fills` has no column for such a token, so this needs a schema change, which the envelope forbids. It is a separate arc: COMMISSION or BANK (owner and trigger to be named).
  - **Branch B (in envelope, an honest indeterminate):** the commit is wrapped on its own. A raise from `conn.commit()` with `in_transaction` False is reported as a distinct typed error, `ExitOutcomeUnknownError(RuntimeError)`, chained from the original. An interrupt keeps propagating per D73, with the indeterminacy logged. The route and the CLI render "the exit may have been recorded; check the trade's fills before retrying" instead of a failure. RED: a connection proxy whose `commit()` performs the real commit and then raises -> the typed indeterminate error, one fill durable. No schema.
  - **Branch C (an accepted limitation, AL-10):** pre-arc, and mitigated by the retry guards above.
  - The cell does not choose. Branches B and C can combine with A's banking.

Round 6: 2 majors (R6-01 and R6-02, both routed), 0 minors, 2 new, 0 reopened, no reverts. Not converged.

### RD's ruling on Fork R5-01 (2026-10-19T08:47:31Z; RD author, orchestrator courier)

Transcribed as a literal block quote of the message body in `comms/orchestrator/inbox/20261019T084731Z-rd-d79-exec-fork-r5-01-ruled-branch-b-al-6.md`, copied mechanically. It was relayed to cell 6 in flight, which landed it at `2b62f07b` (AL-6 restated; `test_al6_first_post_client_trust_width`) and `d539d273` (R5-03), and quoted it in round 6's prompt.

> RD RULING, D79 executing Fork R5-01 (orchestrator query 20261019T084615Z). PRIMARY: RD; the item challenges my P2 correction 2 (AL-6's width). Verified by read on d79-exec before ruling: the resolver's match set is {candidate.date, entered_date} (exit_auto_fill.py:1471-1474); the POST recheck `anonymous_fill_matches` compares the typed tuple only, through `derives_from` over the fill row; the plan's AL-6 line (:40) states the execution-date width only. The finding is real and my correction's factual premise was PARTLY false: it held for the execution-date grain and not for the entered-date grain.
>
> RULING: BRANCH B. AL-6 is restated BY REPLACEMENT to its true width: client-trusted on the FIRST POST are (i) the K7.2 possible-partial flags and (ii) the value-tuple match at the ENTERED-DATE grain, both for the one reason that the order's entered date lives only in the map entry and the first POST does not re-fetch; DB-rechecked are the value-tuple match at the EXECUTION-date grain and the refused-envelope scan. No R5-01 code. R5-03's text fix lands as planned: a flag whose match is on the entered date must say price and quantity match and that the fill's date is the order's ENTERED date, never "these values match" as an equality.
>
> REASONS:
> 1. My correction's principle was "state the limitation at its true width; a limitation declared wider than it is invites a reviewer to re-find the narrower one." The reviewer re-found a WIDER one. The remedy for a width error is the correct width, which is B. The exposure class (a tampered client editing a hidden map) is one the arc already accepts for the partials on this exact reason, and the instrument that closes the class (the signed envelope) is banked with a tampering trigger. Closing one path of an open class with new code is the shape I argued against at P2.
> 2. Branch A asks a DIFFERENT question from the one the map asks. It cannot know the entered date, so it substitutes "any older same-trade anonymous fill at the same price and quantity". That is an alarm from a weaker token: permitted (alarm, never assert), but its text can only say "an earlier fill", not "the order's entered date", so it does not reproduce the suppressed question; it approximates it with false positives on every older identical fill. A new heuristic channel at round 5 is reviewed by rounds 6+, for a tamper-only path.
> 3. Measurement: nothing recorded differs between A and B on an untampered client. Under B a tampered client can record on the first POST a typed exit that duplicates an anonymous fill dated on the order's entered date; the record is operator-typed with the SELECTED order's link, and the later surfaces (VM exclusion, the (c) scan on any further exit, the price-divergence discrepancy) still see both rows. Alarm lost on one tampered path; no identity asserted.
>
> ONE CONDITION (test scope, minor, no re-review): the width is pinned as a FACT, not prose. Whatever test documents that the partial flags are client-trusted on the first POST gains the entered-date case: an anonymous fill dated on the order's entered date at the candidate's price and quantity, the map's `possible_duplicates` stripped, unedited first POST -> records (one row), and the same POST with the item present -> 400, asked. Both legs assert the documented width so a later arc that closes it (the signed envelope) has a red to turn green.
>
> R5-02 (orchestrator, branch A): read, no dissent; order-scoped identities are the K5 direction.
>
> TRANSCRIPTION: block-quote into the exec ledger with RD as author; landed when the path is posted back.

### Orchestrator QA of round 6 (against disk, `8fd44ace`)

- I re-read the assertions from `review-r6.txt`: banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `strong.config.toml`; `^ERROR` 0; `^tokens used` present, 430,882; anchored verdict tokens `NEW_CRITICAL_MAJOR_FOUND` x2, the other token 0; `exit-r6.txt` reads 0. **Round 6 COUNTS.** Counted spend to date: 3,334,072.
- Six commits `d5934658`..`8fd44ace`. Trailers are empty across `618d7b04..HEAD`. No file was added under `swing/`, and nothing under `swing/data/` changed. The tree is clean, and the stash stack holds only the pre-existing entry.
- **The cell's process slip** (a helper import that re-ran R5-01's edits, caught before any commit): I checked HEAD for its residue. No test function name is duplicated in the three d79 test files it touched, and no paragraph over 200 characters repeats in `exit_auto_fill.py`. `d539d273` touches only the R5-03 files.
- **Both forks are ROUTED TO CHARC** (one ruler per item). R6-01 turns on what "the submitted envelope" means in CHARC's plan-stage FORK 2 (the authority). R6-02 turns on the K1 (1) transaction contract CHARC tied to Fork A-F01 ("a raise from record_exit means nothing was recorded"), and its branch A is a commission-or-bank decision for the register.

Author of the sections above: orchestrator, except the block quote (RD).

### CHARC's rulings on Forks R6-01 and R6-02 (2026-10-19T09:40:28Z; CHARC author, orchestrator courier)

Transcribed as a literal block quote of the message body in `comms/orchestrator/inbox/20261019T094028Z-charc-d79-r6-ruled-r6-01-branch-a-raw-rung-r6.md`, copied mechanically. R6-01: branch A, the raw rung. R6-02: branch C, with the contract restated at its true width and pinned by a test. Branch A of R6-02 is banked as D85 on CHARC's register.

> CHARC RULINGS, D79 executing round 6: R6-01 and R6-02. PRIMARY: CHARC on both (one ruler). Read on d79-exec at d539d273: routes/trades.py :2816-2830 (the ladder and the json.loads), :3305-3316 (the selected entry overwrites the top level), :3426-3434 and :3561 (the two authority reads over the PRODUCED envelope); exit.py :350-360 (the helper's early return when no transaction is open) and :606-622 (commit inside the try, the result constructed after); cli.py :1494-1512 (durable bound at record_exit's own return); the ledger's "Round 6 adjudication" at 8fd44ace; my own FORK 2 text in the plan ledger at 003c53da (:149, :212: "a refused reading of the SUBMITTED envelope gets the typed refusal before BEGIN"). Transcribe both as block quotes with CHARC as author.
>
> R6-01 -- RULING: BRANCH A, one ladder rung on the raw anchor.
>
> What "the submitted envelope" meant in FORK 2, read back: F2-(iii) was written about the envelope submitted TO record_exit (req.schwab_source_value_json), and the producer close was "the authority over the envelope ABOUT TO BE PERSISTED." So branch B is CONSISTENT with my ruling as written, and the reviewer found the gap between what I wrote and what the ladder is for. The ladder's purpose is to refuse a tampered or malformed browser anchor at the door; the authority's refusal set IS this codebase's definition of an unreadable identity document. A route that reads the raw anchor through json.loads (last-wins on duplicate keys: a THIRD reading of identity, the one the plan-stage packet named as the reason for ONE authority), then REPLACES a refused top-level id with the selected entry's, is repairing a document the authority refuses -- normalisation on input, the same thing FORK 2 forbade on write ("stripping a value the authority refuses would be a second spelling of the id"). A refused token discarded asserts nothing about the ROW; it asserts something about the CLIENT, and that is exactly what the ladder exists to act on. One call, no read, nothing to defend at the gate. A.
>
> Shape: canonical_envelope_identity(raw string) runs BEFORE json.loads, as the rung the others follow; state == REFUSED -> _reject_anchor (400, anchor cleared, typed values kept, the ladder's existing discipline), with a message naming the identity as unreadable and the recovery (re-open the form). A canonical reading, or a document naming no order, passes through to the existing tiers UNCHANGED. The producer check at :3430 STAYS: the two rungs are not redundant -- the raw rung guards INPUT identity (top level, RD's FORK 1 width), the producer rung guards PERSISTED identity (a padded id in the selected MAP entry survives the raw rung and is caught at :3430).
> Discriminators, RED first: (i) the reviewer's two cases -- padded top-level id with a canonical selected entry; duplicate root identity keys -- each 400, record_exit spy at zero calls, no fill, the anchor cleared and the typed values kept; (ii) the non-redundancy control: a canonical raw anchor whose SELECTED map entry carries a padded id passes the raw rung and is refused at :3430, zero record_exit calls (null implementation killed: deleting the producer check as "covered"); (iii) the existing ladder tests and the T7-k d2-strict suite stay green unchanged; any test that submits a refused raw anchor and expects a record is classified SUPERSEDED by name. The raw rung's docstring says why it is first and what FORK 2's producer rung still owns.
>
> R6-02 -- RULING: BRANCH C, with the K1 (1) contract RESTATED at its true width (not a bare AL bullet), the width PINNED by a test, one ERROR record at the site, and branch A BANKED on my register.
>
> The contract I tied to A-F01 -- "a raise from record_exit means nothing was recorded" -- is unhonourable on exactly one path: conn.commit() raising with in_transaction already False, where durable and rolled-back are indistinguishable on that connection (the R10-02 gotcha: the writer cannot quote itself). Pre-arc (618d7b04:228 `with conn:` behaved identically); a sub-instruction window on a single-operator local box. The arc's own guards make the operator's next action truthful: a linked retry is refused under the lock as already recorded, an anonymous retry at the same values is asked the (c) question (route) or refused without --confirm-duplicate (CLI); a double record needs different values or a confirmed question. So the one false sentence ("failed") is corrected by the system's own guard one step later on both paths. Branch B would say "unknown, check the fills" and ask the operator to do by hand what the guards do on retry, at the cost of a new exception type, two caller branches and a round-7 review surface. The honest-indeterminate principle holds; here the instrument that honours it already exists in the retry path. C.
>
> What C REQUIRES, so the limitation is a fact and not prose (RD's R5-01 pattern, adopted):
> (i) The contract text is restated BY REPLACEMENT in record_exit's docstring transaction paragraph and in the plan's AL-10: "a raise BEFORE the commit statement means nothing was recorded; a raise FROM conn.commit() with no transaction open is INDETERMINATE on this connection; the (a) guard and the (c) question make a retry truthful; the settlement is a per-attempt token co-durable with the fill (D85, banked)." The A-F01 ledger entry gets a one-line pointer to this width; the ledger does not get rewritten.
> (ii) The width is PINNED: a connection proxy whose commit() performs the real commit and then raises -> the original propagates (not swallowed, not re-typed), in_transaction False, exactly ONE fill durable on a FRESH connection (never the writer's own); and a second leg: the retry of that same linked exit is refused by the (a) guard naming the durable fill. A later arc that lands D85 has a red to turn green on the first leg.
> (iii) ONE ERROR record, no new type, no caller change: in record_exit's except, when conn.in_transaction is already False, log_contained_note names "commit raised with no transaction open; the outcome is INDETERMINATE on this connection; check the trade's fills before re-entering" with the trade id and the order id if any. The log is the forensic trail; the callers' close guards render as they do today. An interrupt in flight keeps the D73 shape (it propagates; the record is written first).
> (iv) No schema, no new module, no caller plumbing. The route's `result is None` re-raise and the CLI's `durable=False` are unchanged.
>
> BANKED as D85 (mine, at the next charter touch): "a lost commit on record_exit is indeterminate on the writer's connection; settlement = a per-attempt, non-reusable token written co-durably with the fill (uuid4 by mechanism, the rowid gotcha) and read on a fresh connection; needs a fills column (schema)." Owner CHARC; trigger: a lost-commit incident in the log record from (iii), OR the next arc that adds a fills column, OR the D39 sweep (the same transaction family: every template copy has this window). Not commissioned.
>
> MERGE GATE additions: the raw rung visible in the diff at the top of the ladder; (ii)'s two legs visible; the restated contract paragraph quoted; the D73 helper unchanged. Nothing else open on my seat for round 6. Dispatch.

**Pointer, per CHARC's R6-02 condition (i):** Fork A-F01's contract ("a raise from `record_exit` means nothing was recorded") holds at the width R6-02 restates: a raise BEFORE the commit statement records nothing, and a raise FROM `conn.commit()` with no transaction open is INDETERMINATE on that connection (AL-10; D85 banked).

Author of the transcription frame and the pointer: orchestrator. Author of the block quote: CHARC.

## Cell 7 (implementer-opus-high, dispatched off `a5ccf93f`)

Author of this section and of the self-sweep and round-7 records below: cell 7.

| Commit | Item | Note |
|---|---|---|
| `f4e03f18` | R6-01 | CHARC branch A: `_exit_raw_anchor_is_refused` (`routes/trades.py`), the FIRST rung of the exit anchor ladder, runs the authority over the RAW anchor before `json.loads`; a refused reading takes `_reject_anchor` (400, anchor cleared, typed values kept) with `_EXIT_RAW_ANCHOR_UNREADABLE_TEXT`. The producer check stays. RED: the padded top-level id under a canonical selected entry, duplicate root `schwab_order_id` keys, and the unclaimed padded anchor each recorded (200) before the fix; now 400, zero `record_exit` calls, no fill. (ii) the non-redundancy control is a pin, green both ways. `tests/web/test_routes` in full: 1202 passed. SUPERSEDED by replacement (accepted by the orchestrator on the ruling's intent): `test_d79_exit_identity.py::test_t6d_padded_order_id_is_refused_before_record_exit`, whose padded root is now refused by the raw rung |
| `7b9b355a` | R6-02 | CHARC branch C: the contract restated by replacement in `record_exit`'s docstring, the A-F01 comment and a new plan AL-10; ONE ERROR record through `log_contained_note` (trade id, order id) when the commit statement raised with no transaction open, then the original propagates; `_rollback_or_raise` unchanged. Tests: the width pin, two legs (green both ways); the one-record test and its interrupt variant (red before); the BEGIN-failure no-record test. **Reworded by the orchestrator from the cell's `a0b895e0`** (its final paragraph had parsed as a `Tests:` trailer; the tree is unchanged, verified by tree hash) |

**Encodings cell 7 made** (both accepted by the orchestrator; round 7's prompt carries each, challenge invited):
22. The raw rung is NOT gated on the claim: an unclaimed submission whose raw anchor the authority refuses is answered 400 (before R6-01 it was discarded unread and the POST recorded `operator_typed`). Pinned by `test_r601_unclaimed_refused_raw_anchor_is_refused_too`.
23. An intake correction of R6-02 (iii): the record is keyed on `commit_attempted and not conn.in_transaction`. A failed `BEGIN IMMEDIATE` also reaches the `except` with no transaction open, where nothing was attempted; the ruling's own contract text defines the indeterminate case as a raise FROM `conn.commit()`. Pinned by `test_r602_iii_a_failure_before_the_commit_statement_writes_no_record`.

**Full fast suite on the R6-02 tree (`a0b895e0`, identical to `7b9b355a`): NOT green.** 5 failed, 15489 passed, 13 skipped, in 2469.39 s (about three times the usual run). The five, each re-run in isolation with `-n 0` (13 passed, parametrizations included): `tests/cli/test_diagnose_subcommands.py::test_diagnose_aplus_sensitivity_stdout_is_ascii_safe`, `tests/integrations/schwab/test_ladder_stress_production_path.py::test_forced_finish_lock_leaves_in_flight_row`, `tests/trades/test_22a2_cohort_readers.py::test_a2_94_...[admit]` and `::test_a2_95_...[admit]`, `tests/research/test_aplus_v2_ohlcv_run.py::test_subprocess_aplus_sensitivity_v2_help_cp1252_safe`. The output shows `subprocess.TimeoutExpired` at 120 s for the subprocess tests; none of the five modules is in the arc. The final pre-round run is recorded below.

### Self-sweep (uncounted)

Ordered by the orchestrator as gate-holder, CHARC concurring (2026-10-19T10:12:49Z), before round 7. No Codex, no round number, no effect on convergence. Method: the `618d7b04..HEAD` diff READ in full for `swing/` (`exit.py`, `exit_auto_fill.py`, `routes/trades.py`, the view model, the template, `cli.py`) and the plan; for the tests, every added test name read, and the docstrings of each test touching a surface R6-01 or R6-02 moved; class greps for the identity strings, for "nothing was recorded" / "means nothing", for the tier-(a) and malformed-anchor tests, and for every text asserting "These values match". Findings were adjudicated against the code at `7a2ea886`.

| Id | Severity | Finding | Adjudication | Commit |
|---|---|---|---|---|
| SS-1 | minor (prose) | The ladder's `json.loads` `except` comment still said a deeply nested envelope 500s the POST, and tier (a) was labelled "malformed JSON". Since R6-01 the raw rung refuses every document the authority cannot decode (same decoder), so the `except` is a belt and tier (a) answers only a JSON `null`. | Fixed by replacement; the `except` is kept as a belt. | `783ec4f9` |
| SS-2 | minor (discriminator) | A branch counted as covered: `test_e_malformed_anchor_with_claim_rejects_with_400_and_clears_anchor` says "4-tier rejection (a)" but is answered by the raw rung, so NO test reached tier (a). | Fixed: a claimed JSON `null` pin (`test_e_json_null_anchor_with_claim_is_rejected_at_tier_a`) asserting tier (a)'s text; the malformed test's docstring names the raw rung. Measured by mutation: tier (a) disabled -> the null POST records (200) and the pin fails. | `7812150b` |
| SS-3 | minor (prose) | The producer comment still described the root's padded id as what it catches; a padded root id is now refused at the raw rung. | Fixed: it now names what it owns, a padded id carried in the selected map entry (CHARC's R6-01 text). | `783ec4f9` |
| SS-4 | minor (prose; a branch made unreachable) | The retention rule's "a numeric / list / object id ... is dropped" is now unreachable: a non-string root id is refused at the raw rung, and a non-string selected id is popped where the top level is rewritten. No test counts it as covered (grep of the route tests for non-string or blank root ids: only the three padded-id tests). | Fixed by replacement: labelled a belt, with both reasons. | `783ec4f9` |
| SS-5 | minor (test docstring) | `test_af01_metric_failure_rolls_the_exit_back` still stated "a raise from `record_exit` means nothing was recorded" at full width. | Fixed: the R6-02 width. | `783ec4f9` |
| SS-6 | minor (behaviour: a false sentence; R5-03's class) | A map value-tuple item on the EXECUTION date is shown only when the DB scan of the typed tuple did not match it (the dedup absorbs every case where the typed values derive from the fill, at the same grain, over the same anonymous rows), so its text "These values match recorded fill #N" was false in every case it rendered. R5-03 fixed the entered-date instance only. | Fixed, RED first: `_VALUE_TUPLE_ORDER_TEXT` names the order's date, price and quantity when the typed values do not derive from the item; the value-tuple text stays where they do (R5-03's control unchanged); `FLAG_TEXT_TEMPLATES` takes the name and its closure test passes. | `79d988db` |
| SS-7 | minor (message text) | `_ENVELOPE_UNREADABLE_TEXT` named only order-id defects; the authority also refuses an undecodable document and a symbol defect. | Fixed: the text names the refusal set; the recovery sentence that `test_t2e` asserts is kept. | `783ec4f9` |
| SS-8 | minor (prose) | A docstring wrap R6-02's edit left in `record_exit` ("request refused on its" alone on a line). | Fixed. | `783ec4f9` |

Checked with no finding: the order-scoped identity strings agree across `exit_record_flags` (its docstring and its code), `ExitRecordFlag`'s docstring and the plan's naming line (`possible_partial|`, `unreadable_envelope|` and map-derived `value_tuple_match|` carry `<order key>|<fill_id>`; DB-derived `value_tuple_match|<fill_id>`); the CLI prints `_VALUE_TUPLE_TEXT` for DB-derived matches only, where it is true; the 22-F route guard's comment ("once `record_exit` RETURNS the exit is DURABLE") is still true under R6-02. No critical or major finding. Round 7's prompt carries no SS finding; the sweep's changes appear in the diff, and SS-6's text rule is stated in claim 4 and SS-2's tier-(a) pin in claim 9.

**Full fast suite on the final pre-round head `783ec4f9`, read off the saved output: 15496 passed, 13 skipped, 0 failed** (1049.06 s) = 15486 + R6-01's 4 + R6-02's 4 + SS-6's 1 + SS-2's 1. Box load at launch: no `codex exec` process in WSL. The five subprocess-timeout reds of the `a0b895e0` run did not recur. `ruff check swing/` clean; `%(trailers)` empty across `618d7b04..HEAD` (checked after each commit); no added file under `swing/`; nothing under `swing/data/`.

### Round 7 (the bounded confirming round)

Same form as rounds 4-6: `codex exec -p strong -s read-only --skip-git-repo-check -` from the worktree, runner `~/d79r7/run_r7.sh` (literal paths; `file` reports ASCII; the output and exit files pre-created). The prompt is round 6's frame rebuilt on `c5cb5850` (code head `783ec4f9`) by a self-contained builder:
- claim 1 restated at the R6-02 width; claim 4 extended with SS-6's text rule; a new claim 9 (the raw rung, and tier (a) answering only a claimed JSON `null`);
- AL-1..AL-10 with their reasons (AL-10 new);
- the TWELVE rulings: round 6's ten, plus CHARC's R6-01 and R6-02 ruling bodies quoted verbatim from this ledger (the read-list preamble omitted); CHARC's A-F01 addition as in round 6; encodings 1-4 and 6-23 (22 and 23 new), challenge invited;
- the `618d7b04..HEAD` diff with this ledger excluded; no prior finding text and no SS finding. Prompt 497,279 bytes.

- **Assertions** (script file, read from the transcript):
  - banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `~/.codex/strong.config.toml`;
  - `^ERROR` 0; `^tokens used` 1 (459,279);
  - `^NEW_CRITICAL_MAJOR_FOUND` 2 (the CLI's double emission), `^NO_NEW_CRITICAL_MAJOR` 0;
  - exit file 0, written after codex returned; no `d79r7` process alive at read time.
  - **Round 7 COUNTS.** One attempt; no capacity abort.
- **Prior-findings reach: none.** None of the 39 commands touches the ledger, a review transcript or a findings file; the name hits are the prompt echo and `docs/orchestrator-context.md` prose. **Content-filter events:** none ("The prompt was not rewritten or refused").
- **Evidence:** `review-r7.txt` (1,558,024 bytes), `prompt-r7.md` (497,279 bytes) and `exit-r7.txt` in `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\`, copied once the assertions passed; `copowers-findings.md` there carries round 7's verbatim final message.
- **Spend:** counted rounds 403,744 + 954,070 + 629,503 + 440,564 + 475,309 + 430,882 + 459,279 = **3,793,351**. Disqualified attempts: 434,965 (rounds 3 and 4); none this round.

### Round 7 adjudication (premises re-checked at `c5cb5850`, by execution)

Both majors are PRE-ARC and both are routed. Round 8 is the gate-holder's written decision; no round 8 is started.

- **R7-01 (major): ACCEPTED as real; PRE-ARC; ROUTED as a fork, because the fix crosses the declared envelope.**
  - The defect, verified by execution: `date.fromisoformat` accepts `"20261019"` (-> 2026-10-19) and `"2026-W01-1"` (-> 2025-12-29). `_normalize_trade_event_date_to_iso("20261019")` returns `"20261019T16:00:00"`, and `"2026-W01-1"` returns `"2026-W01-1T16:00:00"`, whose first ten characters are not a calendar date. The route's tier (d) and selected-entry check (`_exit_values_well_formed`) use the same `fromisoformat`, so a claimed envelope whose top-level date, selected entry and typed date are all `"20261019"` passes and records.
  - Pre-arc: the helper is `618d7b04:swing/trades/exit.py:84` and tier (d)'s `fromisoformat` is `618d7b04:swing/web/routes/trades.py:2748`. The arc carried both and wrote a docstring ("an ISO `YYYY-MM-DD` string") the check does not enforce.
  - Why a fork: `_normalize_trade_event_date_to_iso` is SHARED with the ENTRY path (`swing/trades/entry.py:1172-1180`), which is OUT of the declared envelope, and the entry route's tier (d) has the same `fromisoformat` (`routes/trades.py`, the `v_entry_date` check).
  - **Branch A (exit sites only, in envelope):** one strict canonical-date predicate (date-only: `date.fromisoformat(v).isoformat() == v`; a datetime: its first ten characters pass the same test), used by `_exit_values_well_formed` and by `record_exit` before it normalises (a `ValueError` with the existing text family, so both callers' delivery reaches it). RED: route and service tests for `"20261019"` and `"2026-W01-1"` -> 400 / `ValueError`, no fill. The entry half is BANKED (owner and trigger to be named).
  - **Branch B (fix the shared helper):** entry and exit at once; it crosses the envelope into the ENTRY path, so it needs CHARC's envelope widening.
  - **Branch C (accepted limitation, AL-11):** pre-arc, and reachable only by a non-browser client or a CLI typo (the form's date input renders `YYYY-MM-DD`). Its live incidence is a `mode=ro` read for the orchestrator: `SELECT COUNT(*) FROM fills WHERE substr(fill_datetime, 5, 1) != '-' OR substr(fill_datetime, 8, 1) != '-'`.
  - The cell does not choose. Its lean, for the record: A, with the entry half banked.
- **R7-02 (major, tagged [AGAINST-RULING] against FORK 1's "the six refusals, with the EXISTING texts"): ACCEPTED as real; PRE-ARC; ROUTED as a fork, because the ruling's text is CHARC's.**
  - The defect, verified by execution: `fills.price REAL NOT NULL CHECK (price > 0)` stores `float('inf')` (`typeof` real). The third refusal is `not (req.exit_price > 0)` (`check_exit_preconditions`, `exit.py:397`), which `inf` passes, so an infinite price, realized P&L and R-multiple commit. `ExitPriceRefusedError`'s docstring names the column's refusal set as its reason, and the column does not refuse `inf`. Codex reports that click turns `--exit-price inf` and `1e400` into `inf`; the cell did not re-run that leg, and the web form's float parsing was not checked.
  - Pre-arc: `618d7b04:swing/trades/exit.py:168` is the same comparison.
  - **Branch A (widen the third refusal, its position unchanged):** `not (math.isfinite(req.exit_price) and req.exit_price > 0)`, with its text updated; one spelling, so the route precheck and the in-lock barrier both refuse. RED: service, route and real-CLI tests for `inf` and `1e400`, no fill. It changes one of the "existing texts" FORK 1 named.
  - **Branch B (accepted limitation):** pre-arc operator-typed input. The live incidence read: `SELECT COUNT(*) FROM fills WHERE price > 1e308`, `mode=ro`.
  - The cell does not choose. Its lean, for the record: A. The refusal's own docstring states its reason as the column's refusal set, and that reason is false for `inf`.

Round 7: 2 majors (R7-01 and R7-02, both routed), 0 minors, 2 new, 0 reopened, no reverts. Not converged. Every finding of rounds 6 and 7 is pre-arc in class (R6-02, R7-01, R7-02) or a ladder input rung (R6-01); none is a residual of the loop's own fixes.

### Orchestrator self-correction: the round-5 check-in (2026-10-19)

My round-5 approval above ("the trend is 3, 3, 3, then 1 major") applied a COUNT. The rule (recipe section 3, "ROUND LEDGER + ROUND-5 CHECK-IN") says a count cannot make that distinction and the ledger's COMPOSITION can. Read by composition, round 4's one major (A-F01) was tagged out-of-envelope by the reviewer and was pre-arc, and round 3's late items were already residuals of the loop's own fixes. That is stop-and-route, or the gate-holder's self-sweep clause, not "continue". The operator caught it.

I then bounded round 7 with a three-branch stop rule. CHARC concurred, with two amendments (2026-10-19T10:12:49Z): the uncounted self-sweep runs in every branch, and any counted round past the check-in needs a written per-round authorization naming the finding. The stop rule:
1. `NO_NEW_CRITICAL_MAJOR`: the loop ends normally.
2. Every critical or major is out-of-envelope, pre-arc, tamper-only within the banked signed-envelope class, reopened, or a residual of the loop's own fixes: STOP. Each goes to its ruler to accept or bank. If an accepted fix changes behaviour the loop examined, a self-sweep runs, then ONE confirming round. The outcome is reported as stopped-and-routed.
3. A NEW, in-scope, non-reopened critical or major on behaviour this arc introduced: continue only on a written per-round authorization naming it.

Retro-check of the #39 citation valve: RA-01 (a stored fill price) and A-F01 (a stored `entry_price`) were premised on a malformed value in a typed column. Both columns are REAL with no type CHECK, and SQLite's REAL affinity stores a non-numeric string as TEXT, so neither was dismissible. The rulings stand.

### CHARC on encodings 22 and 23 (2026-10-19; CHARC author, orchestrator courier)

> encodings 22 and 23: NO OBJECTION. (23) is the contract's own definition and corrects my (iii), which keyed on connection state instead of the statement; (22) matches the ladder, which already runs on any present anchor regardless of claim. Round 7 may close on them.

### Orchestrator QA of round 7 and of the self-sweep (against disk, `b360ade9`)

- I re-read the assertions from `review-r7.txt`: banner `model: gpt-5.6-sol`, `reasoning effort: high`, equal to `strong.config.toml`; `^ERROR` 0; `^tokens used` present, 459,279; anchored verdict tokens `NEW_CRITICAL_MAJOR_FOUND` x2, the other token 0; `exit-r7.txt` reads 0. **Round 7 COUNTS.** Counted spend to date: 3,793,351.
- Six commits `7a2ea886`..`b360ade9`. `%(trailers)` is empty across `618d7b04..HEAD`.
- The R6-02 commit is `7b9b355a`. The orchestrator reworded it from `a0b895e0` with an identical tree, because its final paragraph had parsed as a `Tests:` trailer. The branch was never pushed.
- No file was added under `swing/`, and nothing under `swing/data/` changed. The tree is clean, and the stash stack holds only the pre-existing entry.
- Suite on `783ec4f9` (the pre-round head): 15496 passed, 13 skipped, 0 failed. The five subprocess-timeout reds of the `a0b895e0` run did not recur.
- **Live incidence (orchestrator, `mode=ro`, 2026-10-19):**
  - `fills` rows whose `fill_datetime` is not dash-delimited ISO: 0 of 59;
  - `fills.price > 1e308`: 0;
  - `trades.entry_date` not dash-delimited: 0.

  Both round-7 failures are LATENT on live.
- **Stop-rule classification (gate-holder): BRANCH 2, the loop STOPS.**
  - Both of round 7's majors are PRE-ARC in class: R7-01 at `618d7b04` `exit.py:84` and `routes/trades.py:2748`; R7-02 at `618d7b04` `exit.py:168`.
  - Neither is a residual of the loop's own fixes, and neither is a defect in behaviour this arc introduced. No counted round 8 is authorized.
  - Both go to their ruler, CHARC. R7-02 is against CHARC's FORK 1 texts. R7-01's in-envelope branch would fork the date grammar away from the shared entry path, and its full fix needs CHARC's envelope.
  - If CHARC rules a fix that changes behaviour the loop examined, a self-sweep and ONE confirming round follow. Otherwise the outcome is **stopped-and-routed**, and the merge report says so.

Author of the sections above: orchestrator, except the block quote (CHARC).
