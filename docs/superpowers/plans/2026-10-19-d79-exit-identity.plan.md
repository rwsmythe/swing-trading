# D79 -- the exit form records the SELECTED broker order's fill, once -- implementation plan

**Ledger (rulings, reasoning, review history):** `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan-ledger.md`. This plan cites ledger sections by name and restates none of their reasoning. **Brief:** `docs/d79-plan-dispatch-brief.md`. **Base:** `main` @ `ed3d4f08`.

**Citation correction carried from the ledger:** the exit candidate hash is `swing/trades/exit_auto_fill.py:_compute_signature_hash` (:1652, called at :1234). It is NOT `swing/integrations/schwab/trader.py:_compute_signature_hash` (:195), which is an API drift fingerprint with the same name.

## Header

### Declared envelope

**IN**
- `swing/web/routes/trades.py`: `exit_post`, `_rerender_exit_form_with_error`, `_exit_candidates_maps_equal` (docstring only, K7.4).
- `swing/trades/exit_auto_fill.py`: `PossibleDuplicateFill.reason`, `_undecidable_duplicates` (reason labels + K7.2 partials), the new flag model, the flag-text constants, and the new pure / read-only flag helpers.
- `swing/web/view_models/trades.py`: `build_exit_form_vm`'s exclusion block (:1037-1225), plus new `TradeExitFormVM` fields with defaults.
- `swing/web/templates/partials/trade_exit_form.html.j2`.
- `swing/trades/exit.py:record_exit`, EXACTLY the CHARC K1 carve-out (ledger "CHARC rulings"):
  - (1) the transaction shape;
  - (2) the identity lookup;
  - (3) the typed refusals.
  - The FORK 2 ruling adds the pre-BEGIN refusal of a submitted envelope the authority refuses. That refusal is part of (2)/(3).
- `swing/cli.py:trade_exit_cmd`: the `--confirm-duplicate` option and its (c) check. The `ValueError -> ClickException` wrap ALREADY exists at `cli.py:1496-1499` and is pinned, not built (ledger "Plan intake").

**OUT**
- Anything under `swing/data/`, and `insert_fill_with_event`.
- `_handle_split_into_partials` (`reconciliation_auto_correct.py:3097`; its insert is at :3325).
- The ENTRY path.
- ANY schema or migration (CHARC K6).
- A standing duplicate-id or refused-envelope monitor (CHARC K6, FORK 2).
- A JS refill, an `hx-get` re-render, or a "use these values" button (orchestrator K4).
- Backfilling 22-A readings on exit fills.
- `swing/trades/latched_origin.py`: consumed, never changed.

### Accepted limitations (each WITH its reason; challenge invited)

- **AL-1, no schema backstop.** There is no `schwab_order_id` column. An expression index would use `json_extract`, which is a different reader from the authority. Split partials legitimately share an id (CHARC K6 (1)-(3)).
- **AL-2, F1 is checked in the route, not the service.** The service never sees what the form showed (CHARC K1, second paragraph: "the F1 value-contradiction check stays in the ROUTE").
- **AL-3, no client-side refill on radio change.** There is no JS harness, and the server check is the barrier (orchestrator K4).
- **AL-4, 13 of the 19 exit fills have no stored 22-A reading.** The guard reads the RAW envelope through `canonical_envelope_identity` and never reads the stored table (RD K2; round 0 item 5).
- **AL-5, the identity read is the authority's TOP-LEVEL id only.** A pre-arc row whose only id is `selected_candidate_order_id` is anonymous: it reaches the (c) / K7.2 flag channel, not the (a) refusal. RD's FORK 1 ruling covers this. Live incidence is 0 of 19, and after K7.3 nothing produces the shape.
- **AL-6, the K7.2 POSSIBLE-PARTIAL flags are client-trusted on the FIRST POST. The (c) value-tuple flags and the refused-envelope scan are NOT** (RD P2, correction 2).
  - **Why the partial flags are trusted:** a possible partial needs the order's entered date, which lives only in the submitted map entry. The first POST does NOT re-fetch Schwab; `test_d_post_does_not_emit_new_schwab_api_call_audit_row` (`tests/web/test_routes/test_exit_post_audit_columns.py:313`) pins this. So a client that deletes a map entry's `possible_partial` items gets no partial ask.
  - **Why (c) is not trusted:** the DB-side check runs on the TYPED tuple at every POST (T7 step 2), and an unedited submission's typed tuple IS the candidate's values. A client that strips the map's `value_tuple_match` flags still gets the ask.
  - **Why the refused scan is not trusted:** it is re-run from the DB at every POST.
  - The envelope is client-editable by design. It is unsigned, and that is banked at `exit_auto_fill.py:937-945`.
  - The confirm POST re-fetches (K5).
- **AL-7, the (c) and K7.2 confirm channels are not serialized under a lock.** Two identical anonymous exits are legal (RD K5c). Only the (a) id guard is a lock-held barrier (CHARC K1).
- **AL-9, the identity reader is linear in fills, with no cache and no index** (CHARC P1, the noted cost). `recorded_exit_identities` runs the authority over EVERY non-entry envelope on every exit POST, every form GET (T3) and every confirm (T7).
  - At 59 fills the cost is nothing. By K6's own reasoning there is no index to lean on.
  - Trigger to revisit: non-entry fills reaching the low thousands. Until then, do NOT build a cache or an index reflexively.
- **AL-8, the CLI carries no Schwab envelope.** So CHARC's K1 test (v) ("CLI with a replayed id") is driven by planting the typed refusal at the service seam. The CLI cannot submit an id at all, which is also why only (c) applies there (RD K5c).

### Executing posture

- **Cell:** `implementer-opus-high`. The reason: a money-bearing write path's transaction shape, plus a two-POST confirm protocol with a re-fetch.
- **TDD per task:** RED, then GREEN, then a commit carrying the task id (`feat(...)`/`fix(...)`/`test(...): T<n> -- ...`).
- **The FULL fast suite** (`python -m pytest -m "not slow" -q`) runs to green BEFORE the executing review AND again on the final head after it. `ruff check swing/` must be clean.
- **Executing review:** the `strong` profile, with REPO ACCESS (production code). Read access to the worktree, or a stdin bundle carrying `exit.py`, `routes/trades.py:2413-3420`, `exit_auto_fill.py`, `view_models/trades.py:994-1300`, the template, `latched_origin.py:662-915` and `cli.py:1450-1520`.
- **The arc ends in an OPERATOR-WITNESSED browser check on a scratch DB copy (T9).** It is binding for HTMX form work.
- **Supersession is by REPLACEMENT.** Prose this arc makes false is rewritten in the task that makes the new text true. The named sites are below (T3, T6). Quote nothing from the old text, and re-verify every claim against the symbols.

### Naming used below

- **"The authority":** `swing.trades.latched_origin.canonical_envelope_identity`.
- **"(a)":** a submitted order id that is already recorded. It is REFUSED in the service.
- **"(c)":** an anonymous value-tuple match (trade, date, price at 2 dp, quantity) at the `_derives_from` grain (`routes/trades.py:3209-3221`).
- **"F1":** the typed values contradict the SELECTED candidate's own map entry.
- **"Flag identity":** `"<kind>|<subject>"` (ledger "Plan intake", the accepted encoding). The subject is:
  - for F1: `"<selected_order_id>|<date>|<price:.2f>|<qty>"` of the TYPED values;
  - for (c): `"<fill_id>"`;
  - for K7.2 and the refused envelope: `"<order key>|<fill_id>"`, where the order key is the selected order id, or the selected candidate's signature hash when the entry has no usable id (exec ledger, "FORK D79-A2", branch B). For the refused envelope the selected id is the linked order id.
- **The `world` fixture:** `tests/web/test_routes/test_exit_rerender_anchor.py:99`.
  - o1 = 2026-05-20, 130.00 x 4.
  - o2 = 2026-05-21, 131.00 x 3; o2 is the default, at index 1.
  - The trade holds 10 shares.
  - Its helpers `_browser_form`, `_post` and `_exit_fills` are reused. The round-0 probes (`~/swing-data/review-transcripts/d79-exit-identity/round0/test_d79_round0_probe.py`) use exactly this shape.

---

## Task ladder

Order matters: T1-T2 build the service barrier that T6-T7 rely on, and T4 builds the flag vocabulary that T6-T8 consume.

### T1 -- `record_exit` owns ONE `BEGIN IMMEDIATE` and rejects a caller-held transaction (CHARC K1 (1))

**Files / symbols**
- `swing/trades/exit.py`: `record_exit`; a new `CallerHeldTransactionError(RuntimeError)`; a new module-level `_rollback_or_raise(conn, op, original)` copied in shape from `swing/trades/account_equity_snapshots.py:69-86` (the 22-A / S-D39 template); a module `log`.
- The module docstring's "Both are wrapped in the SAME `with conn:`" (`exit.py:13-14`) is rewritten by replacement to describe the owned transaction.

**Shape**
1. `if conn.in_transaction: raise CallerHeldTransactionError(...)`. This is the FIRST statement, before any read and before argument validation of the trade.
2. The pure argument checks (reason, shares, price, `_normalize_trade_event_date_to_iso`) stay before BEGIN. They read nothing.
3. `try: conn.execute("BEGIN IMMEDIATE")`, then `get_trade` and the state and size checks. They move INSIDE the lock, which also closes the size-check-outside-the-transaction race. Then the T2 lookup, the insert, the note and the state transitions, then `conn.commit()`.
4. `except BaseException as exc: _rollback_or_raise(conn, "record_exit", exc); raise`.
   - A rollback failure is logged via `log_contained_note`. The message reads: "this connection MUST BE DISCARDED".
   - **The D73 shape (2026-10-18; CHARC P1).** Inside the helper's `except BaseException as cleanup_error`:
     - `if not isinstance(original, Exception): raise original from cleanup_error`, so the INTERRUPT propagates and the cleanup failure is its explicit cause;
     - otherwise `raise cleanup_error from original`, unchanged.
     - Neither error is ever swallowed. The helper's docstring names "the D73 shape (2026-10-18)".
5. A `ValueError` raised inside the lock (not found, not active, exceeds) still propagates as a `ValueError` after a clean rollback, so both callers' `except ValueError` delivery is unchanged.

**RED tests** (`tests/trades/test_d79_record_exit_txn.py`)
- **T1-a (CHARC K1 (iii)):** open `conn.execute("BEGIN")` plus a probe `SELECT`, then call `record_exit` -> it raises `CallerHeldTransactionError`. A `get_trade` spy (monkeypatched at `swing.trades.exit.get_trade`) records ZERO calls.
  - Pre-fix: no raise. The inner `with conn:` COMMITS the caller's transaction and a fill is written, so `pytest.raises` FAILS.
  - Post-fix: it raises with 0 spy calls.
  - Null implementation killed: a guard placed after `get_trade`, which fails the 0-calls assertion.
- **T1-b (CHARC K1 (iv), the both-verbs-fail proxy):** wrap the connection in a proxy whose `insert_fill_with_event` path raises `RuntimeError("insert")` (monkeypatched at `swing.trades.exit.insert_fill_with_event`) and whose `rollback()` raises `RuntimeError("rollback")`.
  - Assert the raised exception is the ROLLBACK error, with `__cause__` being the insert error.
  - Assert `caplog` has one ERROR record containing "MUST BE DISCARDED".
  - Pre-fix: `with conn:` swallows nothing, but the error raised is the INSERT error with no chaining and no log, so the test fails on both type and log.
  - Null implementations killed: a bare `conn.rollback()` with no try (which loses the original), and a try/except that swallows the rollback error.
- **T1-e (D73; CHARC P1):** `KeyboardInterrupt` is raised at the insert seam, and the rollback raises `sqlite3.OperationalError`.
  - Expected: the raised object IS the `KeyboardInterrupt`, and its `__cause__` is the `OperationalError`. `caplog` has ONE ERROR record naming both errors and "MUST BE DISCARDED".
  - Expected: the same call wrapped in an outer `try: ... except Exception: pass` is NOT caught, so `pytest.raises(KeyboardInterrupt)` surrounds that wrapper.
  - Pre-fix, with the copied pre-D73 template: the `OperationalError` propagates, and the outer `except Exception` swallows it. That is RED on both assertions.
  - Null implementation killed: the pre-D73 template, the 13-copy shape.
- **T1-c (the precondition both callers satisfy):** two tests, each spying on `record_exit` AT THE CALLER'S BOUND NAME and recording `conn.in_transaction` at entry before delegating to the real function.
  - Route: monkeypatch `swing.web.routes.trades.record_exit`, then a real `world` POST of the default, unedited.
  - CLI: monkeypatch `swing.trades.exit.record_exit`, since `cli.py:1476` imports it locally at call time, then `CliRunner` `trade exit`.
  - Both assert the recorded value is `False` and that the exit is recorded.
  - It is a pin, not a discriminator of T1. It is green pre-fix and stays green, and it exists so a future caller-side `with conn:` fails here, not in production (CHARC K1 (1) "the arc PROVES with a test").
- **T1-d (the race the lock closes, size half):** a trade with `current_size` 10, and two `record_exit` calls for 10 shares on two connections over one WAL file DB, with `busy_timeout` 5000. It uses THE BARRIER HARNESS, shared with T2-a as a fixture in this test module. There is no sleep-based ordering.
  - **Call 1's hook:** `insert_fill_with_event`, monkeypatched at `swing.trades.exit.insert_fill_with_event`. It runs the REAL insert first, so call 1 now holds a write lock under BOTH the pre-fix and the post-fix shape. Then it starts call 2 on a thread and `wait`s on `threading.Event` `read_done` with a 2.0 s timeout, then returns, so call 1 commits.
  - **Call 2's signal:** a spy on `swing.trades.exit.get_trade` (and, from T2 on, on `swing.trades.exit.recorded_exit_identities`). On call 2's FIRST invocation of either, it appends `"read"` to a shared `events` list, sets `read_done`, then delegates. Call 1's commit appends `"commit1"`, via a wrapper on its connection's `commit`.
  - **Pre-fix, deterministically:** call 2's `get_trade` runs OUTSIDE any transaction, so the read does not block. `read_done` fires BEFORE `commit1`, and call 2 reads size 10 from a stale row. What happens next depends on `state_transition`'s own check of the stale state: either 2 fills, or a rollback raising a transition error that is not the size refusal. Both outcomes FAIL the test, on the `events` order and on the message, so the discriminator does not depend on which one occurs.
  - **Post-fix, deterministically:** call 2 blocks at `BEGIN IMMEDIATE`, so `read_done` does NOT fire during the hold. The wait times out, call 1 commits, call 2 acquires, reads size 0 / state closed, and raises. Result: 1 fill, `events == ["commit1", "read"]`.
  - **The test asserts all three:** 1 fill; the second raises `ValueError` matching "not active" or "exceeds"; and `events == ["commit1", "read"]`. That last assertion PROVES the read happened after the commit, rather than inferring it from the outcome.
  - Null implementation killed: "BEGIN IMMEDIATE but get_trade still before BEGIN" (its events read `["read", "commit1"]` and it gives 2 fills).
- **Existing tests:** `tests/trades/test_exit.py` (19 calls), `tests/trades/test_22f_exit_price_guard.py` and `tests/cli/test_22f_cli_typed_refusals.py` stay green unchanged. Where a refusal now comes from inside the lock, its message text is unchanged.

### T2 -- the identity lookup and the typed refusals inside the lock (CHARC K1 (2)(3); RD K2 + FORK 1; CHARC FORK 2's submitted-envelope half)

**Files / symbols** (`swing/trades/exit.py`)
- A new frozen dataclass `RecordedExitIdentities(by_order_id: Mapping[str, tuple[RecordedExitFill, ...]], unreadable: tuple[RecordedExitFill, ...])`.
- `RecordedExitFill(fill_id: int, trade_id: int, date: str, price: float, quantity: float)` is frozen. `date` is `str(fill_datetime)[:10]`. It carries the stored values T2-d's anomaly comparison needs, so nothing issues a second query.
- `def recorded_exit_identities(conn) -> RecordedExitIdentities`:
  - one `SELECT fill_id, trade_id, fill_datetime, price, quantity, schwab_source_value_json FROM fills WHERE action != 'entry' AND schwab_source_value_json IS NOT NULL ORDER BY fill_id`, with NO `trade_id` predicate (RD K7.1 global);
  - each envelope goes through the authority;
  - `state == refused` -> `unreadable`; a canonical id -> `by_order_id[id]`; a canonical no-id row -> neither.
  - It is THE ONE reader. T3 (the VM) and T7 (the route's refused-envelope flag) import it; nothing re-reads the envelope id anywhere else.
  - **Its docstring states the NULL case** (CHARC P1, text correction (a)). A NULL-envelope row is neither linked nor unreadable, so the `IS NOT NULL` filter excludes it. T4's `anonymous_fill_matches` treats the same NULL as anonymous. The two readers agree: a NULL envelope names no order.
- `class ExitOrderAlreadyRecordedError(ValueError)` and `class ExitEnvelopeUnreadableError(ValueError)`, both beside `ExitPriceRefusedError` (`exit.py:136`).

**In `record_exit`**
- **BEFORE BEGIN:** if `req.schwab_source_value_json is not None`, compute `ident = canonical_envelope_identity(req.schwab_source_value_json)`. If `ident.state == refused`, raise `ExitEnvelopeUnreadableError`. The message names the recovery: "re-open the exit form to get a fresh Schwab auto-fill" (FORK 2 F2-(iii)).
- **AFTER `BEGIN IMMEDIATE` and BEFORE the insert:**
  - if `ident.broker_order_id` is set, `hits = recorded_exit_identities(conn).by_order_id.get(id, ())`;
  - if `hits` is non-empty, raise `ExitOrderAlreadyRecordedError`;
  - multiplicity is legitimate (split partials), and ANY member refuses (CHARC K1 (2); RD K2 "refuse naming all N").
- **The message (an ASCII constant template):** "Order {N} is already recorded as fill(s) #{F...} on trade #{T}; it cannot be recorded again."
  - When the trade differs from `req.trade_id`, it names THAT trade (RD K7.1).
  - When the request's (date, price at 2 dp, quantity) differ from EVERY hit's `RecordedExitFill` values at the `_derives_from` grain, it appends: " The submitted values differ from that record -- correct fill #{F} instead of recording again." This is RD K2's instrument anomaly, refused with no confirm path.
- **No override parameter** is added to `record_exit` or `ExitRequest` (orchestrator K5: `force` never reaches the service).

**RED tests** (`tests/trades/test_d79_record_exit_identity.py`; envelopes built with `json.dumps({..., "schwab_order_id": "o2"}, sort_keys=True)`)
- **T2-a (CHARC K1 (i)):** two connections and the same id "o2". The trade starts in state `partial_exited` with `current_size` 10, and each call exits 3 shares. So the size check passes for both, `partial_exited -> partial_exited` makes no transition (`exit.py:279`), and only the identity guard can refuse. The second call is started while the first holds its transaction, through T1-d's barrier harness.
  - Expected: exactly ONE fill row with id o2; the second raises `ExitOrderAlreadyRecordedError` whose message contains `#<first fill_id>`; and `events == ["commit1", "read"]`.
  - Pre-fix: both succeed, giving 2 fills and `events == ["read", "commit1"]` (the round-0 F2-A shape, at the service). A route-only guard also gives 2 fills, because the test calls the service directly.
  - Null implementation killed, "identity lookup before BEGIN": the `recorded_exit_identities` spy fires before the lock, call 2 reads "absent", its insert lands after call 1's commit, giving 2 fills.
- **T2-b (CHARC K1 (ii)):** a trade with N=3 partial rows planted RAW, each carrying the same envelope with id "o9" (the split shape, `reconciliation_auto_correct.py:3315-3330`). `record_exit` with id "o9" -> refused, the message names all three fill ids, and the fill count is unchanged.
  - Pre-fix: recorded, giving 4 rows.
  - Null implementation killed: a lookup using `fetchone`, which names one of the three and fails the "all three" assertion.
- **T2-c (cell list 12, RD K7.1 global):** id "o2" recorded on trade A, then `record_exit` on trade B with "o2" -> refused, and the message contains "trade #<A>".
  - Pre-fix: recorded.
  - Null implementation killed: a per-trade `WHERE trade_id = ?`.
- **T2-d (cell list 4, RD K2 anomaly):** fill F recorded for "o2" at 2026-05-21 / 131.00 / 3, then a request "o2" at 2026-05-21 / 131.50 / 3 -> refused, and the message contains "differ" and "correct fill".
  - The same request with equal values -> refused WITHOUT "differ".
  - Pre-fix: both recorded.
  - Null implementation killed: a refusal that ignores values, which fails the "differ" assertion.
- **T2-e (F2-(iii)):** the submitted envelope is `'{bad'`, or `{"schwab_order_id": " 123"}`, or carries a duplicate key `{"schwab_order_id":"a","schwab_order_id":"b"}` (hand-written JSON).
  - Expected: `ExitEnvelopeUnreadableError`, zero fills, and a `conn.execute` spy shows no `BEGIN` was issued (spy via a proxy connection that records statement text).
  - Pre-fix: recorded.
  - Null implementation killed: the check placed after BEGIN, which fails the no-BEGIN assertion.
- **T2-f (FORK 1 / AL-5):** an existing fill whose envelope carries ONLY `selected_candidate_order_id: "o2"` (planted raw), then a request for "o2" -> RECORDED, giving 2 rows.
  - This pins that the service does not read the selected entry.
  - Null implementation killed: a fourth reader. Branch B of FORK 1 would refuse, and this test fails it.
- **T2-g (split-handler pin, cell list 11; CHARC "settled by grep"):**
  - Arrange: a linked exit fill with id "o9" recorded through `record_exit`, plus a `split_into_partials` tier-2 resolution driven exactly as the existing test in `tests/trades/test_apply_tier2_handlers.py` drives it.
  - Expected: the split SUCCEEDS, N partials each carry "o9", and a subsequent `record_exit` "o9" is refused (composes with T2-b).
  - It is green pre-fix on the split half and stays green. It is the pin that fails if a refactor routes the handler through `record_exit`. The refusal half is RED pre-fix.
- **T2-h:** a canonical envelope naming no order (`{"exit_date": ...}` without `schwab_order_id`) -> recorded.
  - It is the control that the guard is scoped to an id: a "refuse when the envelope is non-null" null implementation fails it.

### T3 -- the offer list excludes a GLOBALLY recorded id through the same reader (RD K7.1; orchestrator K7.4)

**Files / symbols**
- `swing/web/view_models/trades.py:1037-1225`:
  - replace the per-trade, verbatim id collection (`:1087-1169`) with `ident = recorded_exit_identities(conn)`, so `existing_fill_order_ids = set(ident.by_order_id)` comes from all trades;
  - the per-trade anonymous query stays, scoped `WHERE trade_id = ?` (RD K7.1: the (c) tuple stays per-trade), and a row is anonymous when the authority reads no id from its envelope (`refused` included; FORK 2: a refused row is never an exclusion);
  - the comment block `:1037-1066` and `:1115-1177` is rewritten BY REPLACEMENT to state the global-id / per-trade-anonymous split and the one reader;
  - the fill-40 paragraph (`:1119-1152`) stays in substance, because that reasoning is unchanged and K3 reaffirms it.
- `swing/web/routes/trades.py:_exit_candidates_maps_equal`: the docstring sentence at `:2435-2437` is rewritten BY REPLACEMENT (K7.4) in THIS commit. It states that the fresh map comes from a fetch that excludes every order id the authority reads from ANY recorded non-entry fill, so equality means the restored envelope offers exactly the fresh list.

**RED tests** (`tests/web/test_routes/test_d79_exit_offer_list.py`, `world`)
- **T3-a (RD K7.1, same-day close-and-re-enter):**
  - Arrange: trade A records o1 (raw fill, envelope id "o1"); trade B is the `world` trade on the same ticker; the stub still returns o1 and o2.
  - Expected: B's form offers ONLY o2.
  - Pre-fix: it offers o1 and o2, because the per-trade query at `:1092` misses A.
  - Null implementation killed: the per-trade scope.
- **T3-b (FORK 2 consistency):** a raw fill on the `world` trade with envelope id " o1" (padded) plus values equal to o1's -> o1 is OFFERED, and its `possible_duplicates` names that fill with reason `value_tuple_match`.
  - Pre-fix: verbatim `" o1"` goes into the exclusion set, matches nothing, and the row is NOT anonymous, so o1 is offered with NO flag. The test fails on the flag.
  - Null implementation killed: a reader that strips (it would exclude o1).
- **T3-c (control):** an id recorded on the same trade is excluded, as before (a regression pin, green pre-fix).

### T4 -- the flag vocabulary: reason labels, K7.2 partials, the flag model, ASCII text (RD K7.2; orchestrator K7.5; CHARC F2-(v))

**Files / symbols** (`swing/trades/exit_auto_fill.py`)
- **Constants:**
  - `DUP_REASON_VALUE_TUPLE = "value_tuple_match"`, `DUP_REASON_POSSIBLE_PARTIAL = "possible_partial"`, `_DUP_REASON_VALUES` (a frozenset);
  - `FLAG_F1_OTHER_ORDER = "f1_matches_other_order"`, `FLAG_F1_NO_CANDIDATE = "f1_matches_no_candidate"`, `FLAG_VALUE_TUPLE = "value_tuple_match"`, `FLAG_POSSIBLE_PARTIAL = "possible_partial"`, `FLAG_UNREADABLE_ENVELOPE = "unreadable_envelope"`, `_FLAG_KINDS` (a frozenset).
- **`PossibleDuplicateFill`:** gains `reason: str = DUP_REASON_VALUE_TUPLE`, validated in `__post_init__` against `_DUP_REASON_VALUES` (`isinstance` before membership, the `:372-376` precedent).
- **`_undecidable_duplicates(order, candidate, anonymous_fills, *, match_quantity)`:**
  - keeps its value-tuple matches, labelled `value_tuple_match`;
  - ADDS K7.2 partials: an anonymous row on the same trade (the input list is already per-trade) whose `date` is in `[entered_date, candidate.date]` inclusive (ledger "Plan intake": RD's no-objection), with `row.quantity <= match_quantity` (RD K7.2, verbatim: "quantity <= the candidate's"), and NOT already a value-tuple match (that row keeps the value-tuple label alone);
  - labelled `possible_partial`;
  - `entered_date` comes from `_extract_iso_date(order.enter_time)`, as `:1375` does;
  - when `entered_date` is empty, the window is `[candidate.date, candidate.date]`;
  - price is not compared for partials, because a partial's price is a leg price, not the VWAP.
- **The `candidates_map` entries' `possible_duplicates` dicts (`:975-983`) gain `"reason"`.** The advisory text (`:1031-1054`) names each row with its reason ("possible partial of this order: fill #F" for partials). The partial and value-tuple sentences are separate.
- **`@dataclass(frozen=True) class ExitRecordFlag(kind: str, subject: str, text: str)`,** with `identity` property `f"{kind}|{subject}"`, and `__post_init__` validating `kind in _FLAG_KINDS` plus `text.encode("ascii")`.
- **Text templates, module constants, ASCII-only** (orchestrator K7.5 wording):
  - `_F1_OTHER_TEXT`: "These values ({typed}) match order {other}, not the selected order {selected} ({sel_values}). Retype them, or confirm to record them as a correction of order {selected}."
  - `_F1_NONE_TEXT`: "These values ({typed}) differ from order {selected}'s ({sel_values}) in {fields}. Confirm to record them as a correction of order {selected}." Here `{fields}` is "date / price / quantity" restricted to those that differ.
  - `_VALUE_TUPLE_TEXT`: "These values match recorded fill #{fill_id} ({date} at {price:.2f} x {qty:g}), which carries no broker order id. Confirm only if this is a different fill."
  - `_PARTIAL_TEXT`: "Possible partial of this order: fill #{fill_id} ({date} at {price:.2f} x {qty:g}). Confirm only if fill #{fill_id} is not part of order {order}."
  - `_UNREADABLE_TEXT` (CHARC FORK 2 wording): "Fill #{fill_id}'s envelope cannot be read, so the framework cannot prove order {order} is not already recorded; correct fill #{fill_id}, or confirm to record."
  - Typed and selected values are rendered `{date}, {price:.2f} x {qty}`. This is K4's "the selected order's own date, price and quantity beside the typed values".
- **`def anonymous_fill_matches(conn, *, trade_id, exit_date, exit_price, shares) -> tuple[PossibleDuplicateFill, ...]`:**
  - a read-only query of that trade's non-entry fills; a row is anonymous when the authority reads no id from it (`None` envelope included);
  - match: through `derives_from` (below), ONE grain in both places (RD K5c; RD P2, correction 1). The row's (`str(fill_datetime)[:10]`, `price`, `quantity`) is presented as an entry, and `derives_from(entry, exit_date=..., exit_price=..., shares=...)` decides. The function carries NO comparison of its own;
  - reason `value_tuple_match`; `ORDER BY fill_id`.
  - Shared by the route (T7) and the CLI (T8) (ledger "Plan intake": shared helpers).
- **`def exit_record_flags(*, typed: tuple[str, float, int], selected_entry: dict | None, selected_order_id: str | None, candidates_map: Mapping[str, Any] | None, anonymous_matches, unreadable_fills: tuple[RecordedExitFill, ...], linked: bool) -> tuple[ExitRecordFlag, ...]`:**
  - PURE; deduplicated by identity; order: F1, then (c), then partial, then unreadable.
  - **F1** fires when `selected_entry is not None` (for a legacy no-map envelope the route synthesizes it, see T6 item 2) and the typed values do NOT derive from it at the `_derives_from` grain. It is `OTHER_ORDER` if they derive from exactly one OTHER map entry, else `NO_CANDIDATE`.
  - **(c) / partial** come from `anonymous_matches` and from the selected entry's map `possible_duplicates`. Only dict items with an int `fill_id` and a known `reason` are used; others are ignored (AL-6).
  - **Unreadable** flags fire only when `linked`, one per unreadable row, on any trade (CHARC FORK 2: a global scan).
  - `_derives_from` is lifted out of `exit_post` into this module as `derives_from(entry, *, exit_date, exit_price, shares)`, so the route's retention rule (T6) and F1 use ONE comparison. That keeps "derives from" meaning the same thing in both places, the rationale of `routes/trades.py:3204-3208`.

**RED tests** (`tests/trades/test_d79_exit_flags.py`)
- **T4-a (K7.2):** a candidate o3 (entered 2026-05-18, executed 2026-05-21, 6 shares at VWAP 131.10) against seven anonymous rows on its trade. Expected labels:

  | row | date | price x qty | expected | null implementation it kills |
  |---|---|---|---|---|
  | r1 | 2026-05-19 | 131.00 x 2 | `possible_partial` | no partial channel (pre-fix: absent) |
  | r2 | 2026-05-21 | 130.90 x 2 | `possible_partial` | a window ending at the entered date |
  | r3 | 2026-05-21 | 131.10 x 6 | `value_tuple_match` only | a partial check that also fires on the exact tuple |
  | r4 | 2026-05-17 | 131.00 x 2 | absent | a window with no lower bound |
  | r5 | 2026-05-22 | 131.00 x 2 | absent | a window with no upper bound |
  | r6 | 2026-05-19 | 131.00 x 6 | `possible_partial` | `<` on quantity (equal quantity, different date and price, is not a value-tuple match) |
  | r7 | 2026-05-20 | 131.00 x 7 | absent | no quantity bound |

  - Pre-fix: only r3 is returned, and it carries no `reason` field (`AttributeError` on `.reason`, RED).
- **T4-b (labels distinct; F2-(v)):** build one flag of each of the five kinds -> five distinct `kind` values and five distinct identities. `ExitRecordFlag(kind="bogus", ...)` raises `ValueError`.
  - Null implementation killed: a shared label for the refused-envelope and value-tuple flags.
- **T4-c (K7.5 ASCII):** every text constant above, formatted with representative values, passes `.encode("ascii")`, and so does `ExitRecordFlag.__post_init__`.
  - Iterate over the constants by NAME via a module-level tuple `FLAG_TEXT_TEMPLATES`. A closure-check test asserts every module-level `_*_TEXT` name is in that tuple (a static walk with `dir()`, not a hand list).
- **T4-d (F1 against the SELECTED entry, cell list 6):**
  - Map {o1, o2}, selected o1, typed = o2's values -> one `FLAG_F1_OTHER_ORDER` whose text contains "match order o2, not the selected order o1".
  - Typed 2026-05-20 / 129.50 / 4 -> `FLAG_F1_NO_CANDIDATE` naming the field "price" only.
  - Pre-fix: no function exists (ImportError, RED).
- **T4-e (cell list 7, VWAP at 2 dp):** selected entry price 120.505, typed 120.5 or 120.51 -> no F1 when `round(120.505, 2)` equals the typed price at 2 dp.
  - Arithmetic, MEASURED on this interpreter at plan time: `round(120.505, 2) == 120.5`, because of the binary representation. So typed 120.50 -> no flag, and typed 120.51 -> an F1 flag naming "price". The test asserts BOTH.
  - The template renders `'%.2f' % 120.505`, which the test also asserts equals `"120.50"`, so the unedited render is the no-flag case.
  - Null implementation killed: comparing raw floats (120.505 != 120.5 would flag the unedited render).
- **T4-f:** `anonymous_fill_matches` excludes a row whose envelope carries a canonical id; includes a `None`-envelope row and a padded-id row; and excludes another trade's equal row (per-trade).
  - The expected match is computed by `derives_from` on a row built from the same helper, NOT asserted from a literal comparison (RD P2, correction 1).
  - A monkeypatched `derives_from` that returns False makes `anonymous_fill_matches` return nothing. That proves there is no second spelling of the grain.
- **T4-g:** `exit_record_flags(linked=False, unreadable_fills=(RecordedExitFill(9, 1, "2026-05-01", 10.0, 1.0),))` -> no unreadable flag; with `linked=True` -> one.
- **Existing tests** constructing `PossibleDuplicateFill` positionally stay green (the new field is last and defaulted). Those asserting the exact `candidates_map` JSON or the advisory string are updated in this commit, each named in the commit body. The executing cell finds them by running `tests/trades/test_exit_auto_fill*.py tests/web/test_routes/test_exit_form_auto_fill.py` after the change and reading every red.

### T5 -- the single-candidate shape stamps `selected_*` (RD K3 precondition (4))

**Files / symbols**
- `swing/web/routes/trades.py:2839-2875`: when the claimed envelope's `candidates_map` is a dict with EXACTLY ONE entry and `candidate_sigs` is empty, treat that entry as selected:
  - `selected_index = 0`;
  - `candidate_sigs[0]` = its key;
  - `candidate_orders[0]` = its `order_id` or "".
- This is a server-side fix, so a bare or legacy submission stamps too.
- The template ALSO emits `candidate_signature_hash_0` / `candidate_order_id_0` for a one-candidate list (`trade_exit_form.html.j2:99`), so the browser submission carries what the server would infer.

**RED tests** (`tests/web/test_routes/test_d79_exit_identity.py`, a single-candidate `world` variant where the stub returns o2 only)
- **T5-a:** unedited POST -> the persisted envelope has `selected_candidate_signature_hash` = o2's hash, `selected_candidate_order_id == "o2"` and `other_candidate_signature_hashes == []`.
  - Pre-fix: none of these keys (round-0 `probe_f2b_single.json`).
- **T5-b:** a POST with the template's index-0 inputs STRIPPED (a bare submission) -> the same stamps.
  - Null implementation killed: a template-only fix.
- **T5-c:** the single-candidate F2-A replay (two GETs, two unedited POSTs) -> the second is refused at the service, and exactly one fill exists.
  - Pre-fix: 2 fills.
  - This composes T2 through the real route (cell list 1, single).

### T6 -- the route writes the SELECTED order's link and values, and F1 becomes a flag (orchestrator K4, K7.3; RD K3 (iv); CHARC FORK 2's producer close)

**Files / symbols** (`swing/web/routes/trades.py:exit_post`, block `:2877-3275`)

1. **Selection rewrite (K7.3; RD K3).** When `authoritative_selected is not None`, set the persisted envelope's top-level fields from the selected entry, unconditionally (no longer only on `schwab_auto`):
   - `exit_date`, `exit_price`, `closed_shares`, `exit_date_source` (when present) = the SELECTED entry's `date` / `price` / `quantity` / `date_source`;
   - `schwab_order_id` = its `order_id` when it is a non-blank string, else popped.
   - This replaces `:3090-3145`. The R4-M1 pop is kept in substance; its comment is rewritten to the new condition.
2. **The comparator** (`:2947-3006`) is reduced to `derives_from(...)` (T4). It sets `resolved_fill_origin` and `resolved_operator_corrected_value_json` exactly as today, but the corrected branch is reachable ONLY through a confirmed F1 (T7). **The legacy no-map envelope gets F1 too.** A legacy envelope is a claimed dict with no `candidates_map`. For it, the route passes `exit_record_flags` a SYNTHESIZED `selected_entry`: `{date: exit_date, price: exit_price, quantity: closed_shares, order_id: schwab_order_id}`, built from the envelope's top level. `selected_order_id` is that `schwab_order_id`.
   - A mismatch therefore raises `FLAG_F1_NO_CANDIDATE`. It can never be `OTHER_ORDER`, because there are no other entries.
   - No path reaches the corrected branch without a validated F1 acknowledgement.
   - This is the only call site that synthesizes an entry, and that is stated in the code comment.
3. **The retention rule** (`:3232-3270`): the id is kept iff it is usable AND exactly one map entry names it (for a legacy no-map envelope, the top-level quartet stands as that entry, the existing branch at `:3255-3264`) AND (the typed values derive from that entry, OR the request carries an acknowledged F1 flag identity for that order, a flag T7 has validated).
   - Its rationale block (`:3147-3208`) is rewritten BY REPLACEMENT IN THIS COMMIT (RD K3 last paragraph). It states:
     - what a top-level id asserts, unchanged (the link, a historical fact; the fill-40 reasoning);
     - that the link is established by selection plus either value-derivation or an explicit confirmation (RD K3 (iv));
     - that the drop branch now covers only an UNCONFIRMED divergence, which the F1 flag makes unreachable through the form, so the rule is the backstop for tampered maps (zero or several entries naming the id, or an unusable id).
   - Every claim is re-verified against the symbols; nothing is quoted from the old text. The paragraph `:3184-3194` describing the "third case" is deleted, not edited, because the state it names is closed.
4. **The writer predicate (CHARC FORK 2, the producer).** Immediately after `resolved_schwab_source_value_json` is built, if `canonical_envelope_identity(resolved_schwab_source_value_json).state == refused`, call `_reject_anchor(...)`. The message: "the auto-fill envelope's order id is malformed (padded or blank) and cannot be recorded; the form has been regenerated."
   - There is NO normalisation on write.
   - The `usable` predicate at `:3234-3236` is left in place. It is now dominated by the authority read, and its comment says so.
5. **F1 does not record on the first POST:** see T7 for the flag dispatch. T6 lands the data shapes and the tests that need only "no confirm yet -> no row".

**RED tests** (`tests/web/test_routes/test_d79_exit_identity.py`, `world`)
- **T6-a (orchestrator K7.3, the label):** pick o1 (index 0) and leave the inputs at o2's values; no force.
  - Expected: NO fill is written, the status is 400, and the body contains "match order o2, not the selected order o1".
  - Pre-fix: a fill `schwab_auto_then_operator_corrected` with top-level id o2 (round-0 Item 2).
- **T6-b (orchestrator K7.3, the link; RD K3):** the same pick, confirmed (the T7 confirm protocol, driven by a helper `_confirm(tc, tid, body)` that re-posts the re-rendered form with `force=true` and its rendered `acknowledged_flag` values). The persisted envelope has:
  - top-level `schwab_order_id == "o1"` (equal to `selected_candidate_order_id`);
  - top-level `exit_date`, `exit_price` and `closed_shares` equal to o1's map entry (2026-05-20, 130.0, 4), not o2's;
  - `operator_corrected_value_json` holding o2's typed values;
  - `fill_origin == "schwab_auto_then_operator_corrected"`;
  - and the next GET offers ONLY o2.
  - Pre-fix: no confirm exists; the first POST writes top-level o2 with o2's values.
- **T6-c (cell list 3, F2-B closed):** pick o1, date 2026-05-21, price 129.50, shares 4; confirm.
  - Expected: the id o1 is KEPT, and the next form does NOT offer o1.
  - The stale-form replay: the test keeps the FIRST GET's form, picks o1, and RETYPES o1's exact values (2026-05-20 / 130.00 / 4). It posts with NO `force`, so no flag fires and no fresh fetch runs. That request reaches `record_exit`, which refuses it with `ExitOrderAlreadyRecordedError`, and there is still one o1 row.
  - A stale CONFIRM, by contrast, is voided at the route by d2 before it reaches the service. T7-c and T7-f cover that path; this test does not combine the two.
  - Pre-fix: the id is dropped, o1 is re-offered unflagged, and the re-record succeeds (round-0 `probe_f2b.json`).
- **T6-d (F2-(iv)):** a POST whose envelope top-level and map entry carry order id " o2" (padded, hand-built consistent anchor) -> 400 from `_reject_anchor`, zero fills, and a `record_exit` spy shows zero calls. The same POST with "o2" -> recorded.
  - Pre-fix: " o2" is persisted (the `usable` check passes).
  - Null implementation killed: the check placed in the service only, which fails the zero-calls assertion. That is the writer-side half, distinct from T2-e.
- **T6-e (the default included, K4):** default o2 with price edited 131.00 -> 131.40, unconfirmed -> no fill, 400, `FLAG_F1_NO_CANDIDATE` naming "price".
  - Pre-fix: corrected and recorded.
- **T6-f (control):** default unedited -> `schwab_auto`, top-level o2, one fill, 200 (`test_a_unchanged_auto_fill_persists_schwab_auto` stays green).
- **T6-g (legacy no-map envelope; Codex R3-01):** a claimed envelope carrying only the top-level quartet for o2, with no `candidates_map`, and the price edited 131.00 -> 131.40.
  - First POST -> 400 with `FLAG_F1_NO_CANDIDATE` naming "price", and no fill.
  - Confirm -> VOID. `_exit_candidates_maps_equal` returns False for an envelope with no `candidates_map` (`routes/trades.py:2443-2444`), so d2 cannot prove the list is unchanged.
    - The re-render shows the refresh notice and a FRESH anchor, with no fill written.
    - The fresh anchor carries a map, because the resolver always emits one (`exit_auto_fill.py:964-999`), so the operator re-picks on the current shape.
    - A legacy envelope therefore never records a correction. That is the safe direction for a shape the current resolver does not produce.
  - Pre-fix: recorded corrected on the first POST.
  - Null implementation killed: F1 gated on a map entry (`selected_entry is not None` with no synthesis), which records on the first POST.
- **Existing tests SUPERSEDED in this commit, by replacement.** Each is rewritten to the ruled shape: the unconfirmed POST writes nothing; the confirmed POST records the selected link. Each is named in the commit body:
  - `test_exit_post_audit_columns.py::test_b_edited_price_flips_to_then_operator_corrected` (:210);
  - `::test_h_critical1_non_default_radio_without_visible_edits_flips_corrected` (:927);
  - `::test_h_r3m1_regression_non_default_radio_no_edit_top_level_unchanged` (:1501);
  - `::test_h_r3m1_regression_default_radio_manual_edit_top_level_unchanged` (:1579);
  - `::test_b_review_major1_non_default_radio_plus_edits_drops_the_order_id` (:1664; it becomes "...confirmed_keeps_the_selected_order_id");
  - `::test_h_r4m2_real_operator_edit_at_1_cent_flips_to_corrected` (:2124).
  - **How the list was produced:** names read from `grep -n "^def test"` over the file plus each test's docstring. It is a lower bound. After T6-T7 land, the executing cell runs the whole file and the whole `tests/web/test_routes/` directory, and classifies EVERY red as superseded (rewritten, named) or regression (fixed in code). The two lists go in the return report.

### T7 -- the ONE confirm shape: flag dispatch, flag-bound acknowledgement, the d2-strict fresh map (orchestrator K5; RD K3 (1)-(3), K5c; CHARC FORK 2)

**Files / symbols**
- `swing/web/routes/trades.py:exit_post`: new reads of `force` (`form_data.get("force") == "true"`) and `acknowledged = set(form_data.getlist("acknowledged_flag"))`, honoured ONLY when `force` is set.
- `_rerender_exit_form_with_error`: gains `flags: tuple[ExitRecordFlag, ...] = ()`.
- `TradeExitFormVM`: gains `exit_flags: tuple = ()` (a row partial, not a base-layout VM, so there is no cross-VM field obligation).
- The template gains a flag block above the form inputs:
  - each flag's `text`;
  - one `<input type="hidden" name="acknowledged_flag" value="{{ flag.identity }}">` per flag;
  - a `<button type="submit" name="force" value="true">Confirm and record</button>` beside the existing Submit;
  - plain Submit carries no `force`, so a retype is re-checked from scratch.

**POST order (after the ladder and T6's envelope build, before `record_exit`)**
1. **If `force` and the claim is an auto-fill claim (K5, RD K3 (2)):** `fresh_vm = build_exit_form_vm(...)` (one Schwab fetch). If `not _exit_candidates_maps_equal(fresh_vm, anchor_envelope)`, the confirmation is VOID:
   - re-render via `_rerender_exit_form_with_error(..., submitted_*=None)`;
   - the refresh notice is shown, no flags are shown, there is no restore, and nothing is recorded.
2. **Compute flags** with `exit_record_flags(...)`:
   - `typed` = the submitted tuple;
   - `selected_entry` / `selected_order_id` from T6;
   - `candidates_map` = the submitted map;
   - `anonymous_matches = anonymous_fill_matches(conn_ro, ...)`, a fresh read on its own short connection, closed before `record_exit`'s connection opens;
   - `unreadable_fills = recorded_exit_identities(conn_ro).unreadable`;
   - `linked` = the persisted envelope carries an authority-read id.
3. `unacked = [f for f in flags if not (force and f.identity in acknowledged)]`. If it is non-empty, re-render via `_rerender_exit_form_with_error(...)` with the submitted anchor (offered for restore under ruling (d), exactly as the `ValueError` path does at `:3340-3366`) and `flags=flags`, error message "Confirm or retype before recording." Nothing is recorded.
   - In the helper: when the claimed anchor is NOT restorable (its map differs from the fresh one), the flags are DROPPED and the refresh notice shows, because a flag about a selection the fresh list no longer offers is void.
   - An unclaimed submission's flags ((c) only) always render.
4. **Otherwise, `record_exit`.** The confirmed F1 identity feeds T6's retention rule. `force` is never passed to the service (K5). An (a) refusal arrives as `ExitOrderAlreadyRecordedError` through the existing `except ValueError` re-render (`:3332`).
5. **The confirm form's round trip** (orchestrator K5) uses the existing restore path:
   - `candidate_index` is restored by hash (ruling (a));
   - the per-candidate hashes and ids, the anchor triple, and the typed date, price, shares, reason and notes are laid over the VM (ruling (e));
   - the `acknowledged_flag` inputs are added.

**RED tests** (`tests/web/test_routes/test_d79_exit_confirm.py`, `world`)
- **T7-a (cell list 5, (c) confirm-before-record):**
  - Arrange: an anonymous `operator_typed` fill on the trade, planted raw, at 2026-05-21 / 131.00 x 3.
  - First unedited o2 POST -> 400, no new fill, and the body names the fill with the value-tuple text. Confirm -> recorded, giving 2 rows.
  - Pre-fix: the first POST records immediately, giving 2 rows after ONE POST.
  - Never refused: the confirm path exists.
- **T7-b (K5: an unacknowledged flag re-asks):** the T7-a first response's ack set is mutated to drop the one identity, then posted with `force=true` -> 400 and still one recorded row.
  - Null implementation killed: `force` as a blanket waiver.
- **T7-c (K5: a d2 world change voids the confirmation):** after the T7-a flag render, the stub's order list gains o3 (so the fresh map differs), then the confirm POST -> 400 with the refresh notice, NO flags, and no new fill.
  - Pre-fix: no confirm protocol.
  - Null implementation killed: confirm checked against the SUBMITTED map, which records.
- **T7-d (K5: the anchor round-trip incl. `candidate_index`; cell list 9):** pick o1 (non-default), F1 flagged. In the flagged re-render:
  - assert `_checked_radios(body) == ["0"]`;
  - assert the hidden `candidate_signature_hash_0` equals o1's hash;
  - assert typed values and reason are preserved.
  - Confirm -> the persisted `selected_candidate_signature_hash` is o1's hash.
  - Null implementation killed: a re-render that drops `candidate_index` re-targets the default o2, so the persisted selected hash is o2's.
- **T7-e (flag identity binds the typed tuple; ledger "Plan intake"):** after an F1 flag on typed price 129.50, the operator retypes 129.60 and presses Confirm (the ack carries the old identity) -> 400, re-asked, and the new text contains "129.60".
  - Null implementation killed: acknowledgement by kind only.
- **T7-f (RD K3 (3) + cell list 10: a confirmation cannot waive (a)):**
  - Arrange: tab A and tab B GET; tab A records o1 via pick and confirm.
  - Tab B: pick o1, F1 flagged, then confirm with tab B's own acks.
  - Expected: 400, the message "already recorded as fill(s) #<A's fill>", and exactly one o1 row.
  - The d2 check voids it first (the fresh map no longer offers o1), so the test also plants a variant where the fresh map is stubbed EQUAL (by monkeypatching `_exit_candidates_maps_equal` to `True`), which proves the SERVICE refuses even a d2-passing confirm.
  - Pre-fix: two o1 rows.
- **T7-g (cell list 1, F2-A multi-candidate through the route):** two GETs, both tabs POST o2 unedited -> the first gives 200 and one fill; the second gives 400 with "already recorded" and one fill total.
  - Pre-fix: both 200 and 2 fills (round-0 `probe_f2a.json`).
- **T7-h (F2-(i)):**
  - Arrange: a raw fill F on the `world` trade with envelope `{"schwab_order_id": " 123", ...}` (planted RAW; the T6-d route can no longer produce it, the 18-B.1 technique).
  - First unedited o2 POST -> 400 with the unreadable text naming F and "correct fill #F"; confirm -> recorded, one new row.
  - Null implementations killed: 2a (refuses, with no confirm path; this test's confirm step fails) and 2b (records on the first POST).
- **T7-i (F2-(ii)):** the same with F on ANOTHER trade -> the same flag.
  - Null implementation killed: a per-trade scan.
- **T7-j (control, the CLI-absent shape):** an unclaimed `operator_typed` POST with no anonymous match and an unreadable row elsewhere -> recorded on the first POST (an unreadable flag needs `linked`).
- **T7-k (d2-strict intact; cell list 8):** `tests/web/test_routes/test_exit_rerender_anchor.py` stays green, in full, unchanged. The executing cell runs it after T7 and names any red as a regression, not a supersession, because ruling (d) is unchanged.

### T8 -- the CLI: `--confirm-duplicate` and the pinned typed-refusal wrap (RD K5c; orchestrator K5; CHARC K1 (v))

**Files / symbols** (`swing/cli.py:trade_exit_cmd`, `:1454-1513`)
- A new option `@click.option("--confirm-duplicate", "confirm_duplicate", type=int, multiple=True, help="Record even though these anonymous recorded fill ids match the exit's date, price and shares.")`. It binds the confirmation to the fill IDS printed, the CLI form of flag identity.
- Inside the existing `try`, before `record_exit`: `matches = anonymous_fill_matches(conn, trade_id=..., exit_date=req.exit_date[:10], exit_price=..., shares=...)`. This is a read on the same connection with no transaction open; T1-c pins `in_transaction` at the call.
- If `{m.fill_id for m in matches} - set(confirm_duplicate)` is non-empty:
  - `click.echo` each match as `ascii_safe(_VALUE_TUPLE_TEXT.format(...))`;
  - then `raise click.ClickException("possible duplicate of the recorded fill(s) above; nothing was recorded. Re-run with --confirm-duplicate <id> for each id to record it anyway.")`.
  - It reaches `pending_refusal` through the existing `except click.ClickException` (`:1500-1502`), so the 22-F close discipline is unchanged.

**RED tests** (`tests/cli/test_d79_cli_exit_confirm.py`, `CliRunner` over a tmp DB, the `test_cli_trade.py` seeding helpers)
- **T8-a (cell list 13):** an anonymous fill at 2026-05-21 / 131.00 x 3, then `trade exit --exit-date 2026-05-21 --exit-price 131 --shares 3` -> exit code 1, the output names `#<fill_id>`, and the fill count is unchanged.
  - Pre-fix: exit code 0, and a duplicate is recorded.
- **T8-b:** the same with `--confirm-duplicate <fill_id>` -> exit code 0 and recorded. With `--confirm-duplicate <other id>` -> exit code 1.
  - Null implementation killed: a boolean flag.
- **T8-c (CHARC K1 (v)):** monkeypatch `swing.trades.exit.record_exit` to raise `ExitOrderAlreadyRecordedError("Order o2 is already recorded as fill(s) #7 on trade #1; ...")` -> exit code 1, the output contains "already recorded as fill(s) #7", and `"Traceback" not in result.output` (AL-8 states why it is planted at the seam).
  - It is a pin: green pre-fix once T2 defines the class, because the wrap exists at `cli.py:1496-1499`.
- **T8-d (ASCII on the real encoder):** a subprocess run of `python -m swing.cli trade exit ...` (T8-a's flagged case) under `PYTHONIOENCODING=cp1252` -> no `UnicodeEncodeError` in stderr, exit code 1. This is the CLAUDE.md cp1252 encode gotcha; `capsys` cannot see it.

### T9 -- the executing gates and the OPERATOR-WITNESSED browser check (binding for HTMX form work)

No production code. The executing cell PREPARES and the operator DRIVES, step by step, one step at a time (no batched runbook).

1. **Suite and lint.** The full fast suite is green on the final head; `ruff check swing/` is clean; the trailer audit over `<base>..HEAD` is empty.
2. **The scratch DB.** COPY `~/swing-data/swing.db` to a scratch path with plain file copy, never opened through `connect`. Run the worktree's server with `PYTHONPATH=. python -m swing.cli web` against a config whose `paths.db_path` is the copy, on a port that is not the operator's live one. Prove the worktree code is the one running (the editable-install gotcha) by a grep of a T4 constant in the served page.
3. **Live-witness steps** (the operator drives a real browser; Schwab production fetch, read-only):
   - (a) open an exit form on a trade with recorded exits, if any is open; otherwise skip to the census steps and record "no open trade, exit witness deferred to the next live exit". The round-0 measurement had 0 open trades, and a witness on a synthetic seeded trade (see the seeded-gate memory) validates the render path only, so it is labelled so;
   - (b) a non-default pick with untouched inputs -> the F1 flag text, nothing recorded;
   - (c) Confirm -> recorded, and the next form omits that order;
   - (d) a two-tab replay -> the second tab is refused with "already recorded";
   - (e) the (c) flag on a hand-typed duplicate -> the ask, then Confirm.
   - HTMX specifics to watch: the Confirm button's `name="force"` reaches the POST (htmx includes the submitter's name/value); the 400 flag fragment SWAPS (the `responseHandling` 4xx override in `base.html.j2`); `hx-headers` HX-Request on the form.
4. **Census, CHARC K6** (on the COPY, `mode=ro`): linked exit fills grouped by extracted id with count > 1, excluding split-partial provenance. Expected: only known partial sets.
   ```sql
   SELECT json_extract(schwab_source_value_json,'$.schwab_order_id') AS oid,
          COUNT(*), group_concat(fill_id)
   FROM fills
   WHERE action != 'entry' AND json_valid(schwab_source_value_json)
     AND fill_id NOT IN (SELECT affected_row_id FROM reconciliation_corrections
                         WHERE affected_table = 'fills' AND field_name = '__insert__')
     AND oid IS NOT NULL
   GROUP BY oid HAVING COUNT(*) > 1;
   ```
   The executing cell verifies the column names against the live DDL before the witness. They come from `reconciliation_auto_correct.py:3255-3360` (`affected_table=_AFFECTED_TABLE_FILLS`, `field_name="__insert__"`).
5. **Census, CHARC FORK 2:** the authority over every non-entry envelope on the copy. Expected: 0 `refused` (measured 0 of 33 at intake). A non-zero count is a finding, not a check to silence.

---

## Test roster

| # | Test | Task | Source requirement |
|---|---|---|---|
| 1 | T1-a caller-held tx rejected before any read | T1 | CHARC K1 (iii) |
| 2 | T1-b both verbs fail: chained + discard log | T1 | CHARC K1 (iv) |
| 3 | T1-c route + CLI enter with no open tx | T1 | CHARC K1 (1) precondition |
| 4 | T1-d concurrent size check under the lock | T1 | K1 (1) (transaction shape) |
| 4a | T1-e interrupt in flight + rollback fails -> the interrupt propagates, not contained by `except Exception` | T1 | CHARC P1 (D73 shape) |
| 5 | T2-a same id, two connections -> one fill, typed refusal | T2 | CHARC K1 (i); cell 2 |
| 6 | T2-b split-partial trade refused, names all N | T2 | CHARC K1 (ii); RD K2 multiplicity |
| 7 | T2-c cross-trade refusal names the other trade | T2 | cell 12; RD K7.1 |
| 8 | T2-d same id, different values -> refused, anomaly text | T2 | cell 4 (as ruled); RD K2 |
| 9 | T2-e submitted envelope refused -> typed refusal, no BEGIN | T2 | CHARC F2-(iii) |
| 10 | T2-f selected-only row does not match by id | T2 | RD FORK 1 |
| 11 | T2-g split handler still succeeds on a linked exit | T2 | cell 11; CHARC K1 grep pin |
| 12 | T2-h no-id canonical envelope records | T2 | guard scope control |
| 13 | T3-a globally recorded id excluded from the offer list | T3 | RD K7.1 |
| 14 | T3-b padded stored id -> anonymous flag, not exclusion | T3 | CHARC FORK 2 (reader consistency) |
| 15 | T3-c same-trade exclusion control | T3 | regression pin |
| 16 | T4-a K7.2 possible partial, window bounds | T4 | RD K7.2 + intake window |
| 17 | T4-b five distinct flag labels | T4 | CHARC F2-(v); K7.5 |
| 18 | T4-c ASCII over all flag-text constants (closure-checked) | T4 | orchestrator K7.5 |
| 19 | T4-d F1 against the SELECTED entry (other / none) | T4 | cell 6; K4; K7.5 |
| 20 | T4-e VWAP 120.505 at 2 dp passes silently | T4 | cell 7 |
| 21 | T4-f anonymous match reader, per trade, via the authority | T4 | RD K5c grain; K7.1 |
| 22 | T4-g unreadable flag only on a linked exit | T4 | CHARC FORK 2 |
| 23 | T5-a single candidate stamps `selected_*` | T5 | RD K3 (4) |
| 24 | T5-b bare single-candidate POST stamps too | T5 | RD K3 (4) |
| 25 | T5-c single-candidate F2-A refused | T5 | cell 1 (single) |
| 26 | T6-a unconfirmed contradiction writes nothing | T6 | orchestrator K7.3 |
| 27 | T6-b confirmed: top-level id = selected; values = selected's | T6 | orchestrator K7.3; RD K3 |
| 28 | T6-c F2-B closed: id kept, no re-offer, re-record refused | T6 | cell 3 |
| 29 | T6-d padded id refused before `record_exit` | T6 | CHARC F2-(iv) |
| 30 | T6-e default + edit is flagged | T6 | orchestrator K4 |
| 31 | T6-f default unedited control | T6 | regression pin |
| 31a | T6-g legacy no-map edit is flagged; its confirm is void under d2 | T6 | orchestrator K7.3 / K4 (Codex R3-01) |
| 32 | T7-a (c) flags, confirm records, never refused | T7 | cell 5; RD K5c |
| 33 | T7-b unacknowledged flag re-asks | T7 | orchestrator K5 |
| 34 | T7-c d2 world change voids the confirmation | T7 | orchestrator K5; RD K3 (2) |
| 35 | T7-d anchor round-trip incl. `candidate_index` | T7 | orchestrator K5; cell 9 |
| 36 | T7-e retype after a flag re-asks | T7 | ledger intake (flag identity) |
| 37 | T7-f a confirmation cannot waive (a) | T7 | cell 10; RD K3 (3) |
| 38 | T7-g F2-A multi-candidate through the route | T7 | cell 1 |
| 39 | T7-h unreadable fill, same trade: flag then confirm | T7 | CHARC F2-(i) |
| 40 | T7-i unreadable fill, other trade: same flag | T7 | CHARC F2-(ii) |
| 41 | T7-j unlinked exit not flagged by an unreadable row | T7 | CHARC FORK 2 scope control |
| 42 | T7-k d2-strict suite unchanged | T7 | cell 8 |
| 43 | T8-a CLI (c) asks, nothing recorded | T8 | cell 13; RD K5c |
| 44 | T8-b CLI confirm bound to the printed fill ids | T8 | orchestrator K5 (CLI form) |
| 45 | T8-c CLI typed refusal -> ClickException, no traceback | T8 | CHARC K1 (v) |
| 46 | T8-d CLI flag output under cp1252 | T8 | orchestrator K7.5; CLAUDE.md cp1252 |

**Supersession by replacement, named:**
- the `exit.py` module docstring (T1);
- the `view_models/trades.py:1037-1177` exclusion comment blocks and the `_exit_candidates_maps_equal` docstring (T3, K7.4);
- the retention-rule rationale block `routes/trades.py:3147-3208`, with `:3184-3194` deleted, and the `:2881-2916` and `:3052-3089` comparator/rewrite comments (T6, RD K3);
- the template's `:102-113` "does NOT update" instruction, which becomes an instruction that a mismatch will be flagged for confirmation (T7);
- the six superseded route tests (T6).

**Follow-ons, each disposed:**
- the "use these values" button: BANKED (orchestrator K4; owner: orchestrator; trigger: an operator request after the T9 witness);
- the standing duplicate-id / refused-envelope monitor: BANKED (CHARC K6 + FORK 2, D44 family; owner: CHARC; trigger: a non-zero T9 census);
- the 13 exit fills without a 22-A reading: BANKED as flagged at round 0 (owner: CHARC register; trigger: any reader of `fill_envelope_identity` for exits);
- a signed envelope (AL-6): BANKED where it already sits (`exit_auto_fill.py:937-945`; owner: CHARC register; trigger: a tampering incident or a multi-user surface).
