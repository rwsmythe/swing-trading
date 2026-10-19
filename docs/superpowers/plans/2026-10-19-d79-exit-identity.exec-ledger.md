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

### FORK 1 -- flag-before-record vs T7-k (PENDING: CHARC)

Once F1 is a flag, a claimed POST whose typed values do not derive from the selected entry is answered "Confirm or retype before recording" before `record_exit` runs, so an over-size `shares` never reaches the service's "exceeds" refusal. T7-k says `test_exit_rerender_anchor.py` stays green unchanged; three of its tests (:315, :401, :459) assert "exceeds" on such a POST.
- **A1:** one read-only precondition helper in `exit.py` (trade found, active, shares within `current_size`, the pure argument checks), called by `record_exit` inside the lock and by the route before flags; a refusal takes the existing `ValueError` re-render with no flags. Widens CHARC K1 (1)-(3) by one public read-only symbol.
- **A2:** the same skip as a route-side predicate over `get_trade`; no `exit.py` change; a second spelling of the predicate.
- **B:** amend T7-k; the three tests are superseded and reach the refusal through the confirm path (two round trips; the parity test needs an unclaimed path).

Cell lean: A1. Orchestrator recommendation: A1. Routed to CHARC (the K1 carve-out is CHARC's ruling). Ruling to be block-quoted here.

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
