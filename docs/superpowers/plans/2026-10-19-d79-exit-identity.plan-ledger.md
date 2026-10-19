# D79 -- the exit form records the selected broker order's fill, once -- plan ledger

**Arc:** D79, the post-pause exit arc. It covers two defects: F2, a recorded order re-offered and double-recorded, and F1, a non-default candidate pick that does not refill the date and price.
**Operator words, verbatim:** 2026-09-28 "exit double-record defect will be after the pause." / 2026-09-28 "Concur with RDs recommendation.  Let's plan it to dothose two fixes post-pause." / 2026-10-18 "draft the brief", then "go on round 0".
**Authority held:** round 0 ONLY. The plan dispatch and the executing dispatch each need the operator's word.
**Brief:** `docs/d79-exit-order-identity-brief.md` @ `072c5844`. **Known orchestrator error:** it cites `swing/integrations/schwab/trader.py:_compute_signature_hash` (:195), which is an API drift fingerprint. The exit candidate hash is in `swing/trades/exit_auto_fill.py` (the hash function at :1652-1691, and the call that hashes order_id/date/price/quantity/enter_time at :1234). The plan dispatch corrects the citation.
**Round-0 record:** `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\round0\return-report.md`. It is re-set from the cell's chat return and labelled not-verbatim; its probes and query outputs are beside it.
**Ruling packet:** orchestrator query `20261019T011352Z`. Each item has ONE ruler: CHARC rules K1 and K6; RD rules K2, K3, K5c, K7.1 and K7.2; the orchestrator rules K4, K5, K7.3, K7.4 and K7.5 after the directors' rulings land.

## Packet status

| item | ruler | status |
|---|---|---|
| K1 | CHARC | RULED, 2026-10-19 (below) |
| K6 | CHARC | RULED AGAINST, 2026-10-19 (below) |
| K2 | RD | RULED, 2026-10-19 (below) |
| K3 | RD | RULED, 2026-10-19 (below) |
| K5c | RD | RULED, 2026-10-19 (below) |
| K7.1 | RD | RULED, 2026-10-19 (below) |
| K7.2 | RD | RULED, 2026-10-19 (below) |
| K4, K5, K7.3, K7.4, K7.5 | orchestrator | RULED, 2026-10-19 (below) |

## RD rulings -- author: RD; courier: orchestrator

Transcribed as a literal block quote of the message body in `comms/orchestrator/read/20261019T011549Z-rd-d79-rd-rulings-k2-id-alone-k3-iv-link-ke.md` (posted 2026-10-19T01:15:49Z). The body was copied mechanically from the file, so the courier re-typed nothing.

>
> RD RULINGS, D79 round-0 packet (orchestrator query 20261019T011352Z). ONE packet, all RD items. Each ruling states its reason and the preconditions that exist today; a fact I did not execute is marked as such. Read at this seat before ruling: the return report sections 2-4 and the fork list; `_is_execution_bearing_candidate` (schwab_reconciliation.py:475-518); `_resolve_match_quantity` (:521) and `_compute_execution_price` (:446); the exit candidate hash call (exit_auto_fill.py:1234, fields order_id/date/price/quantity/enter_time); the retention rule and its rationale block (routes/trades.py:3150-3270); `canonical_envelope_identity` (latched_origin.py:891); the F1 comparison site (:2945-2962).
>
> K2 -- IDENTITY KEY: THE SCHWAB ORDER ID ALONE. The signature is AUDIT, never a key.
> - Reason: case (b) is UNREACHABLE on the real path and I verified the mechanism myself, not from the census: a candidate's quantity is the SUM of execution legs and its price their VWAP, so a growing fill WOULD change the signature -- but admission requires a TERMINAL status (FILLED; CANCELED/REPLACED with executions) and a terminal order's leg set never grows; a replace is a new orderId; the mapper emits one candidate per orderId. One id -> one frozen signature. (b) collapses into (a).
> - The residual same-id/different-signature event (a hash code change, or a broker revision of a terminal order -- the second UNDETERMINED from code, as the cell says) is an INSTRUMENT anomaly, not a trading case: it is REFUSED under (a) with the reason naming the anomaly ("order N is already recorded as fill F; the broker's values differ from the record -- correct fill F, do not record again"). No confirm path admits it.
> - Read through ONE authority: `canonical_envelope_identity` on the RAW envelope of every non-entry fill in scope. NOT the stored 22-A reading (13 of 19 missing, measured by the cell) and NOT a bespoke json_extract (persist-canonical, 2026-08-26).
> - Multiplicity: a match on N rows is ONE order already recorded N times (the split-into-partials shape); refuse naming all N. The split handler is a CORRECTION path (DELETE + INSERT N under one correction_set_id), not the exit form; it is the one legitimate writer of N rows with one id. Forwarded to CHARC for K1, not ruled here: the service-level refusal must not fire inside that handler -- the cell verifies whether it calls record_exit; if it does, the correction path carries its correction_set_id as the bypass provenance, never a flag.
> - Pre-key rows: a fill whose envelope carries the id (top-level or as the map's selected entry) matches by id regardless of hash vintage; a row with no id is case (c). Preconditions existing today: the authority function; the id on 19/19 linked fills (cell-measured). Missing: none.
>
> K3 -- A CONFIRMED F1 CONTRADICTION: OPTION (iv). The explicit confirmation IS the affirmative link act; `schwab_order_id` STAYS.
> - What is recorded: `schwab_source_value_json` carries the SELECTED order's own values (date/price/quantity from ITS map entry -- never the default's), `operator_corrected_value_json` carries the typed values, `fill_origin` = operator-corrected, truthfully. This is fill 40's shape and the reason fill 40 is the best-evidenced row on the ledger: the id names WHICH order, the correction says HOW it executed, drift between them is data quality, never identity (my 2026-08-11 rule, in the code at :3150-3208 -- the orchestrator's reading of it is accurate).
> - Why (iv) and not (ii): a second "excluding-not-asserting" key splits one claim into two instruments; the id already asserts only the LINK, so a weaker twin adds a state with no evidence of its own (the same-mandate collapse rule). Not (i): fails ENTRY-vs-LABEL -- the request carries an explicit claim (this order, these values, confirmed) and NULL silently discards it; and (i) is what MANUFACTURES F2-B. Not (iii): traps fill-40-class corrections with no honest escape.
> - Preconditions, each required: (1) the confirmation is a distinct POST-time act (soft-warn + force) whose anchor round-trips the selected id, the selected hash, the typed values and `candidate_index`; (2) it is RE-CHECKED at the confirm POST against the fresh map under d2-strict -- a stale confirmation is void and re-asks; (3) a confirmation NEVER waives (a); (4) the single-candidate shape MUST stamp `selected_*` (the cell found it stamps none) -- a confirmation with no selected id is anonymous and cannot keep an id; fix the stamp in this arc. (1)-(3) are the entry SoftWarnError shape and exist; (4) is a defect this arc closes.
> - The retention rule's drop branch then covers only an UNCONFIRMED divergence, which the F1 flag makes unreachable through the form. The rule STAYS as the backstop; its rationale block's "third case" paragraph (:3186-3197) names the state this arc closes and is rewritten BY REPLACEMENT in the same commit (discharged-deferral rule; quote nothing, re-verify every claim it makes against the symbols).
>
> K5c -- ANONYMOUS (c) MATCH: CONFIRM-BEFORE-RECORD, one confirm shape with F1, on BOTH surfaces.
> - Reason: two identical manual exits are legal, so refusal is never allowed; a warn-AFTER on a written row is a message nobody acts on (recording-vs-alarming are different functions; the alarm must precede the irreversible one). On the web it is the same soft-warn + force the F1 flow uses -- ONE confirm shape, not two. On the CLI (no Schwab path, operator-typed only, so only (c) applies there) the command prints the matching fill(s) and requires an explicit confirm flag; the implementer names it. The (c) tuple is (trade, date, price at 2dp, quantity) -- the `_derives_from` grain, one grain in both places.
>
> K7.1 -- GUARD SCOPE: GLOBAL for the id, PER-TRADE for (c).
> - An order id is global at the broker; a same-id match on ANOTHER trade is an (a) refusal naming that trade, and the offer list excludes a globally-recorded id (the same-day close-and-re-enter case: the old SELL in the new trade's lookback is already recorded, globally). The anonymous (c) tuple stays per-trade + ticker, because an identical manual exit on a different trade is exactly the legal case. Live incidence zero -- no read caveat.
>
> K7.2 -- A TYPED PARTIAL OF A WORKING ORDER: FLAG, labelled, never exclude.
> - The hand-typed partial is anonymous; the later FILLED candidate has a larger quantity so the (c) tuple cannot match; today it is offered clean and a confirmation double-records. Identity is never asserted from a date alone, in either direction, so the fix is a FLAG with its own label: the candidate's `possible_duplicates` include anonymous same-trade, same-ticker fills dated within the order's execution window whose quantity <= the candidate's, as "possible partial of this order" -- the operator adjudicates. Precondition: `possible_duplicates` must carry a REASON label distinguishing "value-tuple match" from "possible partial" (this is K7.5's sibling and one change). Precondition existing today: the possible_duplicates machinery (:344, :890, :975-1036).
>
> NOT RULED HERE: K1/K6 (CHARC); K4/K5/K7.3-5 (orchestrator, after these land). K1 note forwarded above (the split handler bypass). The brief's trader.py:195 citation error: noted; the exit hash is exit_auto_fill.py:1652 -- my own first grep in this session hit the same wrong function, which is why the fields above were read at :1234.
>
> TRANSCRIPTION: block-quote this packet into the D79 plan ledger with RD as author; it is landed when the path is posted back.

## CHARC rulings -- author: CHARC; courier: orchestrator

Transcribed as a literal block quote of the message body in `comms/orchestrator/read/20261019T011817Z-charc-d79-charc-rulings-k1-guard-in-record-exi.md` (posted 2026-10-19T01:18:17Z). The body was copied mechanically from the file, so the courier re-typed nothing. CHARC read RD's packet before ruling, so this packet is consistent with it rather than crossing it. In particular, RD's forwarded K1 note (the split-handler bypass) is SETTLED BY GREP: the handler never calls `record_exit`, so no bypass is built, and a test pins that.

>
> CHARC RULING PACKET, D79 round 0 -- K1 and K6, ONE pass. PRIMARY: CHARC on both. RD's K2/K3 are not touched here; K1 is parameterized on K2's key. Depth ~300K at post. Transcribe as a block quote into the arc ledger with CHARC as author; it is IN FLIGHT until that path is posted back.
>
> FACTS I RE-READ (the ruling rests on these, not on the return report):
> - Live `fills` DDL (v41, mode=ro): NO `schwab_order_id` column. The broker id lives INSIDE `schwab_source_value_json` (TEXT). Indexes: `ix_fills_trade(trade_id, fill_datetime)`, `ix_fills_action(trade_id, action)`. 59 fills.
> - `swing/trades/exit.py:148` `record_exit`; `:228` `with conn:` (a DEFERRED transaction) wrapping `insert_fill_with_event` -- the sole `INSERT INTO fills` is `swing/data/repos/fills.py:60/:81`.
> - `routes/trades.py:2953-2956`: the comparison against the SELECTED candidate exists and feeds only `fill_origin`.
> - `schwab_reconciliation.py:475-518` `_is_execution_bearing_candidate`: FILLED, or CANCELED/REPLACED with executions -- terminal only. The cell's (b)-collapse reading is consistent with the code I read; the replace-mints-a-new-id half I take from the report (mappers.py:290-395) as the cell's measurement, labelled.
> - Writer 3, `_handle_split_into_partials` (`reconciliation_auto_correct.py:3218-3330`), deletes one fill and inserts N partials EACH carrying the same envelope and id -- a LEGITIMATE multi-row id.
>
> K1 -- WHERE THE GUARD LIVES: RULED. In the SERVICE, `record_exit`, under ONE `BEGIN IMMEDIATE` that holds BOTH the identity lookup and the INSERT. The route check alone is REFUSED as the barrier: a route SELECT followed by the service's own transaction is two transactions; two tabs (F2-A, reproduced) both read "absent" and both write, and nothing in HTMX serializes them. The F1 value-contradiction check stays in the ROUTE (a presentation-layer comparison against the selected candidate; the service never sees "what the form showed").
>
> The `swing/trades/exit.py` CARVE-OUT IS AUTHORIZED, scoped to exactly:
>  (1) `record_exit`'s transaction shape: the deferred `with conn:` becomes an owned `BEGIN IMMEDIATE` ... COMMIT / ROLLBACK, written in the D39-correct shape from the first line (BEGIN inside the try; a rollback failure logged, the connection marked discard, and RAISED CHAINED from the original -- never swallowed; a both-verbs-fail proxy test). The single-transaction contract REJECTS a caller-held transaction (`conn.in_transaction` -> typed error), never auto-detects and joins it (CLAUDE.md gotcha: the auto-detect guard re-introduces the race the lock closed). Precondition the arc PROVES with a test, not assumes: both production callers (`routes/trades.py:3331`, `cli.py:1495`) enter with no open transaction.
>  (2) the identity lookup inside that transaction, keyed on K2's key as RD rules it, read through the ONE authority the cell named (`canonical_envelope_identity` over the raw envelope, never the stored 22-A table, which misses 13 of 19 exit fills, and never SQL `json_extract`, which reads duplicates differently -- three readings exist today and the guard uses the Python one). The lookup returns a SET (writer 3 makes multiplicity legitimate); any member -> refuse.
>  (3) the typed refusal: a `ValueError` subclass beside `ExitPriceRefusedError` (`exit.py:136`), message naming the recovery ("already recorded as fill N on trade T"); the CLI wraps it per the standing `ValueError -> ClickException` rule.
> NOT authorized: any change to `insert_fill_with_event` or anything under `swing/data/` (a guard there blocks writer 3 and is the wrong layer); any change to the split handler; any change to the ENTRY path.
>
> ADMISSIBILITY PRECONDITIONS OF THE GUARD'S EVIDENCE, stated because my 2026-09-02 ruling omitted its own: VISIBILITY -- the lookup is a read on the writer's own connection, admissible ONLY because it runs AFTER `BEGIN IMMEDIATE` has acquired the write lock (SQLite gives a write transaction the current snapshot or refuses it with BUSY_SNAPSHOT), so no concurrent writer can commit between the read and the INSERT; the same read BEFORE the BEGIN, or on another connection, proves nothing. IDENTITY -- the key is the broker's order id (K2), which exists in the envelope today; a rowid or a value tuple is not an identity (the rolled-back-rowid gotcha). Both preconditions exist today; nothing needs building first.
>
> SCOPE QUESTION K7.1 (global vs per-trade) is RD's/the orchestrator's; K1 is indifferent to it -- the lookup's WHERE clause takes the ruled scope. I note only that a per-trade scope leaves the cross-trade same-day re-entry case open with zero live instances, and a global scope is one less predicate, not more code.
>
> K6 -- SCHEMA BACKSTOP INDEX: RULED AGAINST. Three independent reasons, any one sufficient:
>  (1) There is no column to index. The id is inside a JSON TEXT envelope, so the only index is an EXPRESSION index on `json_extract(schwab_source_value_json, '$...')`, and `json_extract` is a DIFFERENT reader from the Python authority (first-duplicate-wins vs the VM's verbatim vs the latch's whitespace-strict -- the cell counted three). A barrier that re-derives the identity by a different rule than the service is the persist-canonical / authorize-then-abort class (harness-architecture 5.1): the service admits, SQL aborts, the operator gets a raw IntegrityError. The trigger-subset rule forbids it.
>  (2) It is FALSE on legitimate data: writer 3 (split into partials) copies one id onto N rows by design. A UNIQUE index breaks a shipped correction path; a partial index that exempts partials needs a predicate the envelope does not carry.
>  (3) It is new schema (a `fills` rebuild or an expression index + migration) for a property the service now CHECKS on the write path under a lock -- the D36 remedy ("make the property a check the code performs") is satisfied by K1 itself.
> No read-only monitor is commissioned in this arc either. The WITNESS runs the census query once (linked exit fills grouped by extracted id with count > 1, excluding split-partial provenance) and expects the known partial sets only; a standing check is BANKED as a D44-family item (holds-both-facts-compares-neither), not built here.
>
> TEST SHAPE I REQUIRE FOR K1 (the discriminators, each fails the null implementation of one clause): (i) two `record_exit` calls with the same id on two connections, the second started before the first commits -> exactly one fill, the second raises the typed refusal naming fill N (fails a route-only guard: both succeed); (ii) the same id on a split-partial trade (N existing partials) -> refused, the message names one of them; (iii) a caller-held open transaction -> typed rejection BEFORE any read; (iv) both-verbs-fail proxy (INSERT raises, ROLLBACK raises) -> the cleanup error propagates CHAINED from the original and the log names the discard; (v) CLI `trade exit` with a replayed id -> ClickException text, no traceback.
>
> OWNED CORRECTIONS I CARRY (register, at this charter touch): D79's `trader.py:_compute_signature_hash` anchor -> `exit_auto_fill.py:1652-1691` (the orchestrator's catch); D79 gains the round-0 facts (both F2 mechanisms reproduced; (b) unreachable by fill growth; reconciliation is not a backstop; 13 of 19 exit fills have no 22-A reading).
>
> READ AFTER RD's PACKET LANDED (20261019T011549Z), so this is consistent with it, not a crossing: K2 = id alone -> the K1 lookup key is the order id through `canonical_envelope_identity`; K7.1 = GLOBAL for the id -> the lookup's WHERE clause drops `trade_id` for the id match and the refusal names the OTHER trade when it hits one. RD's forwarded K1 item (the split handler bypass) is SETTLED BY GREP, not by provenance plumbing: `record_exit(` has exactly TWO callers in `swing/` (`cli.py:1495`, `routes/trades.py:3331`); `_handle_split_into_partials` writes through `insert_fill_with_event` directly (`reconciliation_auto_correct.py` block :3218-3330, call at its line 108) and never enters `record_exit`, so the service refusal cannot fire inside the correction path and NO correction_set_id bypass is built. The arc pins this with a test that the split handler still succeeds on a trade whose exit carries a linked id (the cell's test 11) -- and the pin is what keeps it true if a future refactor routes the handler through the service.
>
> Nothing else is open on my seat for round 0. Both items ruled in this one packet.

## Orchestrator rulings -- author: orchestrator (generation of 2026-10-19)

These were ruled after both directors' packets landed, and each is consistent with them. Evidence: the round-0 record, sections "Item 2" and "Forks"; ruling (e) of the exit re-render anchor ledger (`2026-09-28-exit-rerender-anchor.ledger.md`:52, typed values are never silently overwritten).

**K4 -- THE F1 SURFACE: a SERVER check only.**
- **The barrier.** At POST, the route compares the submitted date, price and quantity against the SELECTED candidate's own map entry, at the `_derives_from` grain (date; price at 2dp; quantity), in Python. The comparison site exists (`routes/trades.py:2953-2956`); today it feeds only `fill_origin`. This arc makes a mismatch a FLAG (K5) instead of a silent label. The check runs for whichever candidate is selected, the default included.
- **On a flag,** the re-render SHOWS the selected order's own date, price and quantity beside the typed values, so the operator can retype or confirm.
- **NOT built: a client-side JS refill on radio change.** There is no JS harness, its behaviour is browser-only, and once the server check is the barrier the refill is convenience, not correctness.
- **NOT built: an HTMX `hx-get` re-render on radio change.** It re-fetches Schwab on every click, and a refill on change overwrites typed values without an explicit act, which is ruling (e)'s class.
- **NOT built: an explicit "use this order's values" button.** It would be compatible with (e), since it is explicit, but it is banked as a follow-up and is not this arc.

**K5 -- THE CONFIRM FLOW: reuse the entry `SoftWarnError` + `force` shape, through `_rerender_exit_form_with_error`. It is ONE confirm shape for the F1 contradiction and the anonymous (c) match (RD K5c).**
- **The anchor round-trip.** Every anchor key round-trips through the confirm `form_values`: `candidate_index`, the per-candidate hashes and ids, the selected id and hash, the typed values, the reason and the notes. Dropping `candidate_index` silently re-targets the default; a test pins it.
- **The confirm is bound to the flags it acknowledges.** The confirm POST carries the set of flag kinds (and, for (c), the matched fill ids) that the operator saw. At the confirm POST every check is re-run against a FRESH map under d2-strict (`c6640faf`). If the map changed, there is no restore: the confirmation is void, and the form re-asks. If any flag is present that was not acknowledged, it re-asks. `force` is never a blanket waiver.
- **`force` never reaches the service as a bypass.** `record_exit` takes no override parameter, so an (a) refusal (CHARC K1) cannot be confirmed past (RD K3 precondition 3).
- **The CLI** follows RD K5c: it prints the matching fill(s), and it requires an explicit confirm flag whose name the plan cell chooses.

**K7.3 -- THE FALSE "operator corrected" LABEL, and the WRONG ORDER LINK beside it.**
- **The label.** It is closed by K4 + K5 + RD K3, with no separate change: an unconfirmed contradiction now writes NOTHING, and a confirmed one is an operator assertion, so `schwab_auto_then_operator_corrected` becomes TRUE (RD K3: fill 40's shape). Test: a non-default pick with the default's values left in, unconfirmed, writes no fill.
- **The link.** Round 0 measured that a non-default pick KEEPS the DEFAULT's id as the top-level `schwab_order_id`, while `selected_candidate_order_id` names the order actually picked (Item 2). The top-level id would therefore assert a link to an order the operator did not pick. Ruling: the top-level `schwab_order_id`, and `schwab_source_value_json`'s values, are the SELECTED candidate's, never the default's. This is in scope, and it is a precondition of RD K3 (the id names WHICH order). Test: non-default pick, confirmed, gives a top-level id equal to the selected id; the default's id is absent from the envelope's top level.

**K7.4 -- THE FALSE `_exit_candidates_maps_equal` DOCSTRING** ("excludes every order already recorded on this trade"). It is rewritten BY REPLACEMENT, in the commit that changes the exclusion to RD K7.1's global-by-id scope, so that it states what the code then does. Re-verify every claim against the symbols, and quote nothing from the old text. This follows the same discharged-deferral rule RD applied to the retention-rule rationale block.

**K7.5 -- THE FLAG TEXT, done as ONE change with RD K7.2's reason labels on `possible_duplicates`.**
- **Each flag names its reason and the recovery.**
  - F1, values equal ANOTHER offered order: name that order, e.g. "these values match order N, not the selected order M".
  - F1, values match NO candidate: "these values differ from order M's (date / price / quantity); confirm to record them as a correction of order M".
  - (c) value-tuple match: name the matching fill(s).
  - K7.2 possible partial: "possible partial of this order: fill F".
- **The text is ASCII-only** (the cp1252 gotcha: it reaches CLI stdout on the (c) path), asserted by `text.encode("ascii")` over the flag-text constants.

**Banked, not this arc:**
- the explicit "use this order's values" button (K4);
- a standing duplicate-id monitor (CHARC K6, the D44 family);
- the 13 exit fills with no 22-A reading (round 0, flagged out of scope).

## Next

- **Plan dispatch:** needs the OPERATOR'S word (no standing grant). Proposed cell: `implementer-opus-high` (the writing-plans default). It runs off a FRESH worktree cut from `main` at or above this ledger's commit; `.worktrees/d79-exit-identity` (@ `072c5844`) is removed and the worktree re-cut. The plan corrects the brief's `trader.py` citation.
- **Executing:** a separate operator word. It needs the CHARC-authorized `swing/trades/exit.py` carve-out exactly as scoped in K1, and the operator's browser witness.

## Plan intake (rule 1) -- the plan cell STOPPED at two forks

The cell is `implementer-opus-high`, on worktree `.worktrees/d79-plan` @ `47b3883c`. Its depth at return was 238,065, read by the orchestrator with `cell_depth.py --agent`. No plan has been written, no round has run, and nothing is committed. The orchestrator verified the forks' code facts by read: `broker_order_id_from_envelope` (`latched_origin.py:662`, reached through `canonical_envelope_identity` :891) reads only the top-level `schwab_order_id`, and `_handle_split_into_partials` is at `reconciliation_auto_correct.py:3097`, with its insert at :3325.

**Routed as ONE packet** (orchestrator query, 2026-10-19), one ruler per item:
- **FORK 1 -- RULER: RD.** K2's parenthetical "(top-level or as the map's selected entry)" cannot be read through the one authority, which reads the top-level id only.
  - **A (the cell recommends it):** read through the authority only. A selected-only pre-arc row goes to the per-trade (c) / K7.2 flag channel. After the arc, K7.3 makes the writer stamp top-level = selected, so no new row has that shape.
  - **B:** add a second reading of the selected entry. That is a fourth id reader, and it would refuse a picked-but-never-recorded order forever on the "non-default pick, no edit" shape.
  - **Live:** 33/33 envelopes are canonical; 0 have a selected id but no top-level id; 0 have the two differing; 0 trades are open.
- **FORK 2 -- RULER: CHARC.** What the K1 guard does when the authority returns `refused` for an EXISTING non-entry fill.
  - **2a (the cell recommends it): fail closed, globally.** The refusal names the row and the fix.
  - **2b: alarm only.** A WARNING, plus the per-trade (c) channel.
  - **Either way,** a refused reading of the SUBMITTED envelope gets the typed refusal before BEGIN.
  - **Live:** 0/33. A producer exists: a padded id like `" 123"` passes the retention rule's `usable` check (`routes/trades.py:3234-3236`).

**Ruling facts corrected at intake, encoded as the code has them:**
- the split handler is at :3097 / :3325, not :3218-3330;
- the retention rationale block is at :3147-3270, and its "third case" paragraph at :3184-3194;
- the CLI `ClickException` wrap ALREADY exists (`cli.py:1496-1499`); the new `ValueError` subclass reaches it unchanged, CHARC test (v) pins it, and no new wrap is built.

**Facts that shape the plan (no fork):**
- **RD K3(4):** a single-candidate envelope already carries a one-entry `candidates_map` (`exit_auto_fill.py:964-999`), so K3(4) is the template emitting index-0 inputs for one candidate.
- **K5:** a fresh map at the confirm POST means a Schwab re-fetch there.
- **Existing tests:** about 8 tests in `tests/web/test_routes/test_exit_post_audit_columns.py` pin today's "unconfirmed edit records as corrected" behaviour. Each is named and rewritten in the task that changes that behaviour.

**Orchestrator, on its own K5 / K7.5 items (accepted):**
- the confirm acknowledges flag IDENTITIES (the kind plus its subject: the typed tuple, the matched fill ids, the partial's fill id), not just kinds; a retype after a flag re-asks;
- the CLI flag is `--confirm-duplicate` (RD K5c left the name to the implementer);
- the (c) and partial helpers are shared in `exit_auto_fill.py`.

**Sent to RD as an encoding of RD K7.2, open to objection rather than asked as a ruling:** the possible-partial window is the order's entered date through its execution date, inclusive.

### Plan-intake FORK 1 ruling -- author: RD; courier: orchestrator

Transcribed as a literal block quote of the message body in `comms/orchestrator/read/20261019T015835Z-rd-d79-fork-1-ruled-option-a-authority-top.md` (posted 2026-10-19T01:58:35Z), copied mechanically. **It SUPERSEDES the parenthetical in RD's K2 pre-key clause above**; the original quote stays unedited as the record. The K7.2 window encoding has RD's no-objection.

>
> RD RULING, D79 plan-intake FORK 1 (orchestrator query 20261019T015713Z). PRIMARY: RD. One item ruled here; FORK 2 is CHARC's and I hold. Read at this seat before ruling: `canonical_envelope_identity` (latched_origin.py:891-915) and `broker_order_id_from_envelope` (:662-700), the refused-state rationale (:825-840), the VM's R2-Major-#3 exclusion reasoning (view_models/trades.py:1048-1066), the ledger "Plan intake" section @ ac638e5e.
>
> FORK 1 -- OPTION A. The identity read is the authority's top-level id, and ONLY that. SUPERSEDES the parenthetical in my K2 pre-key clause ("top-level or as the map's selected entry"); the clause now reads: a pre-key fill matches by id when `canonical_envelope_identity` reads one from its envelope; a row from which it reads none is case (c). One supersession, this message.
>
> Reasons:
> 1. The parenthetical was an incidental factual claim inside a ruling about what the authority reads; I verified by read that it reads the top-level key only. A ruling is not a source; its REASONING binds. K2's reasoning is "ONE authority, no bespoke reader, no fourth spelling" -- and option B is a fourth reader with a winner rule, the exact thing K2's third bullet forbids and the persist-canonical rule (2026-08-26) exists to prevent.
> 2. The selected-only shape is not an identity. The VM's own exclusion reasoning (R2 Major #3) states why: on the pre-arc "non-default pick, no edit" shape the RECORDED values are the DEFAULT's; `selected_candidate_order_id` records what the operator picked at form-render, not which order was persisted. Matching that row by its selected id asserts identity from a weaker token than the record carries -- identity is never asserted from a token alone, in either direction. Anonymous (c) + the K7.2 flag channel is the alarm-never-assert disposition, and it is the ONLY disposition that keeps the picked-but-unrecorded order offerable (B refuses it forever although it was never recorded -- a false refusal on a legitimate re-record).
> 3. Preconditions, all existing today: the authority function; 19/19 non-entry envelope fills carry a top-level id (orchestrator-measured, v41 mode=ro, 33/33 canonical, 0 selected-only, 0 differing). After K7.3 the writer stamps top-level = selected, so the shape has no producer going forward. Nothing to build first.
> 4. Read caveat, none: live incidence of the selected-only shape is zero, so no historical row changes channel under A.
>
> FORK 2 (CHARC's): I hold. For the record, read and no dissent to state on the cell's 2a; CHARC rules.
>
> K7.2 WINDOW FYI: no objection. "Entered date through execution date, inclusive" is a correct encoding of "the order's execution window"; a hand-typed partial of a working order carries its own execution date, which lies in that interval by construction.
>
> TRANSCRIPTION: block-quote this into the D79 plan ledger with RD as author; it is landed when the path is posted back.

### Plan-intake FORK 2 ruling -- author: CHARC; courier: orchestrator

Transcribed as a literal block quote of the message body in `comms/orchestrator/read/20261019T015936Z-charc-d79-fork-2-ruled-confirm-before-record-c.md` (posted 2026-10-19T01:59:36Z), copied mechanically. **Neither 2a nor 2b:** an unreadable EXISTING fill routes the linked exit into the confirm-before-record channel, and the producer of padded ids is closed in the route. **Numbering note (courier's, not CHARC's):** this ruling's discriminators reuse the labels (i)-(v), so the plan cites them as **F2-(i)..F2-(v)** to keep them distinct from CHARC's K1 tests (i)-(v).

>
> CHARC RULING, D79 plan-intake FORK 2 (orchestrator query 20261019T015713Z). PRIMARY: CHARC. One item, one ruling. Fork 1 is RD's; I am CC and hold. Depth ~330K at post. Transcribe as a block quote with CHARC as author; in flight until the ledger path is posted back.
>
> RULED: NEITHER 2a NOR 2b AS WRITTEN. An EXISTING non-entry fill whose envelope the authority returns as `refused` routes the submitted linked exit into the CONFIRM-BEFORE-RECORD channel (the K5c shape: soft-warn + force, the same single confirm shape as (c) and F1), with a reason-labelled flag naming the row and the fix: "fill F's envelope cannot be read, so the framework cannot prove order N is not already recorded; correct fill F, or confirm to record." Never a global hard refusal (2a); never a warning after the write (2b). The guard is indifferent to whether the unreadable row is on this trade or another (K7.1 global applies to the SCAN; the channel is the same).
>
> WHY, in the terms the ladder already uses:
> 1. The DIRECTION of fail-closed depends on what the write asserts. 22-A's ignorance-fails-closed (`latched_origin.py:830-836`, read) guards a LABEL -- cohort admission -- where closed = EXCLUDE = the safe side. Here the write is a MONEY-BEARING RECORD of a fill the broker executed. Refusing to record it on the strength of an unreadable OTHER row moves the journal into the untracked-close direction (D40: journal-open, broker-flat -- the one direction nothing belts), which is the WORSE error, not the safer one. Both precedents the cell cited are label-side; neither transfers.
> 2. ENTRY-vs-LABEL (harness-architecture 5.1, RD-ruled 2026-09-02): "Could this row be written honestly with the disputed keys NULL plus a named warning?" YES -- the request's OWN claim (this order, these values) is readable and intact; the unprovable fact concerns a DIFFERENT row. So the guard refuses nothing here; it flags. The NO branch of that test is exactly the SUBMITTED-envelope-refused case, and there both branches already agree: typed refusal BEFORE `BEGIN`, naming the recovery -- CONCURRED.
> 3. Alarm-never-assert at the transaction boundary (2026-09-02, RD's corollary, my own R9-03 lesson): the guard may RAISE the alarm ("cannot prove non-duplicate") but may not ASSERT duplication from evidence that cannot identify the attempt. 2a asserts "possibly duplicate" as "duplicate" and acts on it irreversibly (the operator cannot record).
> 4. The absorbing-state question (the VSTS instance, 5.1): under 2a with K7.1 global, ONE padded id anywhere in 59 rows makes EVERY linked exit in the system unrecordable until a tier-2 correction of that row lands -- a state whose only exit is a correction path on a different surface, reached while the operator is trying to close a position. "Does every reachable state have an exit the operator can take" fails. The confirm channel IS the exit, and it leaves a record (the acknowledged flag) that the census below reads.
>
> THE PRODUCER IS CLOSED IN THIS ARC, in the route change K7.3 already makes (writer side; NOT the exit.py carve-out): the route's usable check (`routes/trades.py:3234-3236`, `isinstance(str) and strip()`) PERSISTS a padded id (" 123") that the authority REFUSES. The reader's refusal set must be a subset of the writer's rejection set (the trigger-subset rule, one layer up: never persist what the one authority cannot read). Encoding, adding NO fourth spelling: before `record_exit`, the route runs `canonical_envelope_identity` over the envelope it is ABOUT TO PERSIST; `refused` -> the typed pre-BEGIN refusal above (it is the submitted-envelope case); `canonical` -> proceed. One body, the persist-canonical rule honoured. No normalization-on-write (stripping a value the authority would refuse is a second spelling).
>
> NOT BUILT: a standing monitor. The WITNESS runs the authority over every non-entry envelope once and expects 0 `refused` (measured 0/33 today); a non-zero count at any later witness is a finding, not a check to silence.
>
> DISCRIMINATORS (each fails the null implementation of one clause; RED first):
>  (i) existing fill F with envelope id " 123" (planted RAW, the 18-B.1 technique -- the fixed route can no longer produce it), new linked exit for order N on the same trade -> FLAGGED into the confirm channel, message names F and the fix; with force -> recorded, one row. A 2a implementation FAILS (refuses); a 2b implementation FAILS (records without the confirm).
>  (ii) the same with F on ANOTHER trade -> the same flag (global scan).
>  (iii) the SUBMITTED envelope undecodable or padded -> typed refusal, no `BEGIN`, no row, message names the recovery.
>  (iv) a route POST whose envelope carries top-level id " 123" -> refused before `record_exit` by the authority read; the same POST with "123" -> proceeds (the writer predicate equals the reader's).
>  (v) the flag's reason label is DISTINCT from the (c) value-tuple label and the K7.2 possible-partial label (composes with K7.5: three reasons, three labels).
>
> INTAKE CORRECTIONS: accepted as the code has them (split handler :3097/:3325; retention block :3147-3270; the CLI wrap exists at cli.py:1496-1499 so test (v) of my K1 packet PINS it rather than builds it).
>
> Fork 1: CC, holding; nothing to add to RD's item.

## Plan review

The plan is `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md`. It is uncommitted until it converges, and is committed ONCE then. It is written on the ruled shape: FORK 1 option A, and FORK 2 as CHARC ruled.
- **Rounds run at the `fast` profile:** `~/.codex/fast.config.toml` sets `model = "gpt-5.6-luna"` and `model_reasoning_effort = "medium"`. codex-cli is 0.162.1 (WSL).
- **Transport:** stdin carries the prompt, the plan and this ledger. Codex's cwd is the worktree with `-s read-only`, so it can read the code to check anchors.
- **Isolation:** the review scratch lives in the session scratchpad, not the worktree.
- **The prompt prohibits** reading `.codex-*`, `.copowers-findings.md`, this section, and git.
- **Evidence path:** `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\plan\`.

| round | model (asserted = profile) | effort (asserted = profile) | `^ERROR` | `^tokens used` footer | verdict (anchored) | findings: reviewer severity / cell class | new / reopened | tokens used | transcript | context depth |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | gpt-5.6-luna = gpt-5.6-luna | medium = medium | 0 | 1 | `NEW_CRITICAL_MAJOR_FOUND` (count 2: codex-cli emits the final message twice); the other token 0 | 2 major / 2 task-bearing; 0 instrument | 2 / 0 | 90,269 | `.codex-review-r1.txt`, 497,877 B; prompt `.codex-prompt-r1.md`, 4,820 B | 317,138 (orchestrator, `cell_depth --agent`, at the round-1 gate) |
| 2 | gpt-5.6-luna = gpt-5.6-luna | medium = medium | 0 | 1 | `NEW_CRITICAL_MAJOR_FOUND` (count 2); the other token 0 | 2 major / 2 task-bearing (R2-02 contested-class rule: it changes a test's specification); 0 instrument | 2 / 0 | 57,131 | `.codex-review-r2.txt`, 248,967 B; prompt `.codex-prompt-r2.md`, 4,820 B | 328,477 (orchestrator, at the round-2 gate) |
| 3 | gpt-5.6-luna = gpt-5.6-luna | medium = medium | 0 | 1 | `NEW_CRITICAL_MAJOR_FOUND` (count 2); the other token 0 | 1 major / 1 task-bearing; 0 instrument | 1 / 0 | 89,143 | `.codex-review-r3.txt`, 468,323 B; prompt `.codex-prompt-r3.md`, 4,820 B; stdin ledger `stdin-ledger-r3.md` | 344,362 (orchestrator-read, `cell_depth --agent`, at return) |

**Round 1, process checks.**
- The codex process exited: the runner's exit file reads `rc=0`, and it is written only after `codex exec` returns.
- The transcript is non-empty.
- A grep for `.codex-`, `.copowers-findings` and "Plan review" hits only the prompt's own echo, plus a project doc Codex read (`orchestrator-context.md`). The round read no prior findings, and none existed.

**Round 1 adjudications**

- **R1-01, major. TASK-BEARING. ACCEPTED, fixed.** The plan encoded K7.2's quantity bound as `<`. RD K7.2 reads "whose quantity <= the candidate's" (ledger, "RD rulings"). An equal-quantity row with a different date or price is not a value-tuple match, so `<` silently dropped it from the partial channel.
  - **Fix:** T4 now encodes `row.quantity <= match_quantity`, still excluding a row that is already a value-tuple match.
  - **T4-a's table:** r6 (equal quantity, a different date and price) now expects `possible_partial`, which kills the `<` implementation. A new row r7 (quantity 7, above 6) expects absent, which kills a missing quantity bound. r3 (the exact tuple) keeps `value_tuple_match` alone.
  - **The cell's own error:** it had narrowed a ruled bound on its own reasoning, and that is the plan's fault, not the ruling's.

- **R1-02, major. TASK-BEARING. ACCEPTED, fixed.** T1-d and T2-a ordered the race with "start the second call on a thread and sleep 0.3 s". If call 2 arrived after call 1's commit, the pre-fix code would refuse in the ordinary way, and the test would pass both before and after the fix. That makes it a vacuous discriminator.
  - **The barrier harness, now a shared fixture:**
    - call 1's hook runs the REAL insert, so it holds the write lock under both shapes;
    - the hook starts call 2 and waits on an Event, with a 2.0 s timeout;
    - call 2's first `get_trade` or `recorded_exit_identities` call records "read" and sets that Event;
    - call 1's commit records "commit1".
  - **Pre-fix:** "read" comes before "commit1".
  - **Post-fix:** call 2 blocks at `BEGIN IMMEDIATE`, the wait times out, and "commit1" comes before "read".
  - **The tests assert the event ORDER as well as the outcome.** The order is load-bearing for T1-d, where a stale-state transition refusal could otherwise make the pre-fix outcome 1 fill.
  - **T2-a now starts the trade in `partial_exited`, exiting 3 of 10 shares.** No state transition fires (`exit.py:279`), so only the identity guard can refuse.
  - **Class re-grep:** a grep of the whole plan for `sleep` returns no other site, and neither does a grep for "T1-d hook" beyond the T2-a reuse.

**Round 2, process checks.**
- The codex process exited (`rc=0`).
- Stdin carried the ledger with this "Plan review" section STRIPPED, so the round could not receive round-1 findings through its input.
- A grep of the transcript for `R1-0` returns 0.

**Round 2 adjudications**

- **R2-01, major. TASK-BEARING. ACCEPTED, fixed.** T2-d's anomaly text compares the request against the stored row's values. T2's lookup returned only `(fill_id, trade_id)`, so a literal implementation would need an unspecified second query.
  - **Fix:** the lookup now returns `RecordedExitFill(fill_id, trade_id, date, price, quantity)`. The one `SELECT` adds `fill_datetime, price, quantity`.
  - **The envelope is still read only through the authority;** the stored values are plain columns.
  - **Residual class re-grep:** a grep for the old pair shape found `exit_record_flags`'s `unreadable_fills` type and T4-g's literal. Both were updated, and no other site remains.
- **R2-02, major. TASK-BEARING by the contested-class rule. ACCEPTED, clarified.** T6-c said "a stale-form attempt is refused by the service", while T7's d2 check voids a stale CONFIRM before the service is reached.
  - **The finding is right about confirms.** Not every stale POST is a confirm, though: an unflagged stale POST carries no `force`, so it triggers no fresh fetch and reaches `record_exit`.
  - **T6-c now specifies that shape:** the first GET's form, o1 picked, o1's exact values retyped, no `force`. The service refuses it, and one o1 row remains.
  - **The d2 void path is assigned explicitly** to T7-c and T7-f. The fix changes a test's specification and no mechanism.

**Round 3, process checks.**
- The codex process exited (`rc=0`).
- Stdin carried the ledger with "Plan review" stripped, regenerated before the round.
- A transcript grep for `R1-0|R2-0` gives 1 hit. It is a code comment from another arc ("CHARC R2-05") that Codex read from source, not a prior-round finding.

**Round 3 adjudication**
- **R3-01, major. TASK-BEARING. ACCEPTED, fixed.** A legacy claimed envelope with no `candidates_map` had no `selected_entry`, so F1 could not fire, and an edited legacy submission still reached the corrected branch without confirmation. That contradicts orchestrator K7.3 ("an unconfirmed contradiction writes NOTHING").
  - **Fix (T6 item 2):** the route synthesizes the `selected_entry` from the top-level quartet, so the mismatch raises `FLAG_F1_NO_CANDIDATE`.
  - **New test T6-g (roster 31a).**

**THE COUNTED LOOP ENDS HERE** (3 of 3; a fourth needs the orchestrator's written authorization). The cell does NOT request a fourth round:
- R3-01 was one omitted SHAPE, fixed with a test;
- the self-sweep below found the one residual of that fix (SS-3) by reading, and it resolves to the ruled d2 behaviour without a new mechanism;
- the executing `strong` review with repo access is the next net.

**Uncounted self-sweep** (no Codex, no effect on convergence):
- **SS-1:** T4's F1 rule now points at the T6 synthesis for legacy envelopes, so T4 does not read as gated on a map entry.
- **SS-2:** T6's retention rule names the legacy top-level quartet as "the entry naming the id" (the existing branch at `routes/trades.py:3255-3264`).
- **SS-3, the R3-01 fix's own residual:** a legacy envelope's CONFIRM can never pass d2, because `_exit_candidates_maps_equal` returns False with no map (`routes/trades.py:2443-2444`). So T6-g's confirm is specified as VOID (refresh notice, a fresh map-bearing anchor, no fill), not as recorded. A legacy envelope never records a correction. That is the safe direction for a shape the current resolver never emits (`exit_auto_fill.py:964-999`).
- **SS-4, residual greps:** `sleep`, `strictly less`, `tuple[int, int]`, "six anonymous" and the R2 pair-shape all return no live site. The roster has 47 rows (1-46 plus 31a), counted by an anchored grep for table rows.

**Plan committed once at convergence of the counted loop.**

### Orchestrator QA of the plan review (2026-10-19)

- **Rounds 1-3 verified from the preserved transcripts** in `~/swing-data/review-transcripts/d79-exit-identity/plan/`. In each round:
  - the banner read `gpt-5.6-luna` / `medium`, matching `~/.codex/fast.config.toml`;
  - `^ERROR` = 0, and the `^tokens used` footer = 1;
  - `^NEW_CRITICAL_MAJOR_FOUND` = 2 (codex-cli emits the final message twice), and `^NO_NEW_CRITICAL_MAJOR` = 0;
  - `tokens used`: 90,269 / 57,131 / 89,143. **Sum: 236,543.**
- **Prior-finding leak check.** Round 2 has 0 hits for `R1-0`. Round 3 has 1 hit for `R1-0|R2-0`, and it is a `latched_origin.py` code comment ("CHARC R2-05", a 22-A item) that the reviewer read from the repo. It is not a D79 finding; the prompt and the stripped stdin ledger carry 0 hits. Every round counts.
- **Depths,** read by the orchestrator with `cell_depth --agent`: 238,065 at intake, then 317,138 / 328,477 / 344,362 at the round gates. The cell is `implementer-opus-high` (build 2.1.300, `claude-opus-5-5`).
- **The loop ended at the three-round cap without a clean round.** Under plan-stage rule 4 this is the default outcome: three counted rounds, then a self-sweep, then execution. No fourth round was authorized or needed. R3-01 was one missing case, fixed with a test, and SS-3 settled its one consequence on the already-ruled d2 behaviour.
- **The plan was read in full** (`7b7718fb`, 515 lines, 9 tasks, 47 roster rows). Every roster row traces to a landed ruling; the envelope matches CHARC's K1 carve-out and FORK 2. Two items go to the plan-stage reviews:
  - T1 moves `get_trade` and the state/size checks INSIDE the lock. This is part of the transaction shape, so it is CHARC's to confirm as within carve-out (1).
  - T7 makes the confirm POST re-fetch Schwab. During a Schwab outage, an auto-fill confirm is therefore void, and the only way to record is an unclaimed typed exit. That is RD's to confirm against K3 (2) / K5.
