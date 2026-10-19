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
| K1 | CHARC | OUTSTANDING |
| K6 | CHARC | OUTSTANDING |
| K2 | RD | RULED, 2026-10-19 (below) |
| K3 | RD | RULED, 2026-10-19 (below) |
| K5c | RD | RULED, 2026-10-19 (below) |
| K7.1 | RD | RULED, 2026-10-19 (below) |
| K7.2 | RD | RULED, 2026-10-19 (below) |
| K4, K5, K7.3, K7.4, K7.5 | orchestrator | HELD until K1/K6 land |

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
