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
| 1 | `c55b55b8` | `gpt-5.6-sol` / `high` (= `strong.config.toml`) | 0 | 1 (403,744) | `NEW_CRITICAL_MAJOR_FOUND` (x2, the CLI's double emission); other token 0 | 0 | 2 | 1 | 3 new / 0 reopened | 0 | |

Evidence: `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\review-r1.txt` (1,547,419 bytes), `prompt-r1.md` (367,520 bytes), `copowers-findings.md`. Exit file 0; the process exited before the transcript was read. Prior-findings reach: none (round 1).

### Round 1 adjudication

- **D79-A1 (major): ACCEPTED, to fix.** `derives_from` truncates the quantity with `int()`, so a stored anonymous 5.9-share fill "matches" a typed 5-share exit. Verified by execution (`derives_from({..., 'quantity': 5.9}, shares=5)` is `True`). The truncation came over from the pre-arc route comparator, where map quantities are ints by tier (d); the arc newly applies the grain to STORED fills (`fills.quantity REAL NOT NULL CHECK (quantity > 0)`, migration 0014:13) in `anonymous_fill_matches` (route and CLI) and in the service's anomaly sentence. Fix: compare the quantity as a float at the resolver's established `isclose` grain inside `derives_from` and `_differing_fields`, and add a literal 5.9-vs-5 discriminator (T4-f's expected value is computed through `derives_from` itself, so it cannot see this).
- **D79-A2 (major, tagged [AGAINST-RULING]): ROUTED AS A FORK, not fixed.** The possible-partial and unreadable-envelope identities are `"<kind>|<fill_id>"`, while their texts name the SELECTED order. On a multi-candidate form where two candidates both list fill #F (a possible partial), an operator shown the o1 question can switch the radio and values to o2 and press Confirm; the map is unchanged so d2 passes, and o2's identical `possible_partial|F` is satisfied by the o1 acknowledgement. The same holds for `unreadable_envelope|F` across linked orders. Verified by read (`exit_record_flags` subjects). The fill-id-only subject is the orchestrator-accepted plan-intake encoding ("the partial's fill id"), so changing it is not the cell's call.
- **D79-A3 (minor): ACCEPTED, to fix without a round.** Supersession residue in `exit_auto_fill.py`: the `PossibleDuplicateFill` docstring and `resolve_exit_auto_fill`'s docs still describe value-tuple-only matching and per-trade recorded ids.
