# 22-F EXECUTING ledger

**Plan:** `2026-09-25-phase22-arc-f-handler-escape-sweep.md` (accepted @ `23b2dd18`; on main at `8bfca5a4`).
**Branch:** `22-f-exec`, worktree `.worktrees/22-f-exec`. **Base SHA for every gate check:** `704ac133` (per the dispatch; code-identical to the plan's `79035d59`: `git diff 79035d59 704ac133 -- swing/ tests/ pyproject.toml` is empty).
**Executing cell:** dispatched per `C:\Users\rwsmy\swing-data\review-transcripts\22-f-exec\dispatch-prompt-exec.md`.
**RED evidence:** each task's RED run is pasted in its commit body; the raw RED output is also kept at `C:\Users\rwsmy\swing-data\review-transcripts\22-f-exec\red\<task>.txt`.

---

## Suite gates

| gate | head | result | RESOLVER line | ruff `swing/` |
|---|---|---|---|---|
| G1 | `704ac133` | `1 failed, 14856 passed, 13 skipped, 1163 warnings in 607.71s` -- the one red is `tests/trades/test_22a2_cohort_readers.py::test_a2_94_the_card_page_renders_the_line_and_zero_data_renders_none[moved]` (an `assert OBSERVED_LINE in html` miss) on the UNMODIFIED base; reproduced isolated with `-n 0`: the test (5/5 params) PASSES, and the whole file PASSES (`83 passed in 165.31s`). Recorded as an xdist-load red on the base, NOT fixed (no code of this arc involved); watched at G2/G3. Transcript: `review-transcripts\22-f-exec\g1-suite.txt` | `C:\Users\rwsmy\swing-trading\.worktrees\22-f-exec\swing\__init__.py` (the worktree; no `PYTHONPATH` needed) | `All checks passed!` |
| G2 | -- | -- | -- | -- |
| G3 | -- | -- | -- | -- |

## Pre-flight checks

- **T-D0 input hash (CHARC condition 3), checked FIRST:** `sha256sum C:/Users/rwsmy/swing-data/review-transcripts/22-f-plan/r0-measurements/triage.json` -> `b18eb936b1ffe4bb81595aa16768351449915295ecc7f7f78c9158fde955cb13` (bytes). MATCHES the pinned value. No STOP.

## Task table

| task | commit | RED evidence | deviations |
|---|---|---|---|
| T-A1 | `1961f0ad` | commit body; `red/T-A1.txt` (6 failed, 2 passed = the two controls) | **D-1 (instrument):** the ROUTE tests plant the parity error at the MAPPER (`swing.integrations.schwab.trader.map_orders_to_fill_candidates`, a counting wrapper, did-it-fire asserted) rather than at `trader.get_account_orders` as the plan names: A1-d requires the REAL `schwab_api_calls` row that `_call_endpoint` writes and closes before re-raising, which a patched `get_account_orders` never writes. The service tests A1-a/A1-b patch `get_account_orders` as written. **D-2 (fact):** `schwab_api_calls` has no `finished_ts` column (`PRAGMA table_info` read); A1-d's "closed" discriminator reads `status != 'in_flight'` and `response_time_ms IS NOT NULL`, both set by `record_call_finish`. **D-3 (fact):** A1-f -- a degraded form renders the three hidden auto-fill anchors NOT AT ALL (`trade_entry_form.html.j2:74-81`, gated on `vm.auto_fill_schwab_source_value_json`), so the assertion is "absent" (the POST then infers `operator_typed`, NULL audit columns), not "present and empty". |
| T-A2 | `6bae812f` | commit body (A2-b / A2-c RED quoted per RD's re-clearance); `red/T-A2.txt` (6 failed, 4 passed = A1-a + the controls A2-b', A2-c', A2-f) | Executed AS RULED at STOP-1 (A2-b one leg 0.5; A2-c resolver plant 0.0; A2-b'/A2-c' required controls). **D-4 (fact):** A2-a' builds the order by hand: `SchwabOrderResponse.quantity` must be finite (`models.py:336`), so the sibling `_make_multileg_buy_order` (order quantity = leg sum = inf) cannot construct it; the order carries `quantity=1e308`, which the resolver never reads when legs are present. **D-5 (instrument):** A2-e reuses T-A1's route world (REAL `get_account_orders`, the MAPPER planted to return the A2-a' order, counting wrapper asserted); its pre-fix "500" is observed as the `OverflowError` re-raised by TestClient (server exceptions re-raised), which in production is the app-wide 500 page. New module `tests/web/test_routes/test_22f_quantity_guard_routes.py` (A2-e now; A3-e lands there in T-A3). |
| T-A3 | `74ffc752` | commit body; `red/T-A3.txt` (5 failed, 4 passed = A1-b + controls A3-c, A3-d) | **RD Minor 1: the DOCSTRING LINE** (not the reorder) -- the orders differ only on `-inf`, which no validated order carries; the existing `None or <= 0` line stays byte-unchanged (pure insertion). A3-a' built by hand like A2-a' (D-4). A3-a' is driven both at `_build_candidate` and through `resolve_exit_auto_fill`. A3-e in `test_22f_quantity_guard_routes.py` (T-A1's route world, mapper planted). |
| T-A4 | `6187e008` | commit body; `red/T-A4.txt` (5 failed, 1 passed = the StopRegressionError control) | **D-6 (fact):** the commands take `--trade-id`, not a positional id (the plan's "`trade exit 9999 ...`" is illustrative); `StopRegressionError` is `Exception`, not `ValueError` (`stop_adjust.py:72`), so clause order is immaterial -- kept first as the plan asks. A4-c's fresh read covers `trades`/`fills`/`trade_events`. New module `tests/cli/test_22f_cli_typed_refusals.py`. |
| T-A5 | `c18890ef` | commit body; `red/T-A5.txt` (3 failed, 1 passed = the A5-e control) | **Web READ:** both types caught by `routes/reconcile.py:1753` `except Exception` (defense-in-depth, 500 `service_error` fragment, class name logged) -> A5-e is a CONTROL pinned via the logged class name. A5-a drives the reserved field `trades.entry_date` (the preflight raise); A5-b the same field through tier-3 override; A5-c a seeded `correct_entry_date` head. **Observation (not fixed, out of the census's escape set):** on the web the operator sees "Unexpected internal error" for these two refusals, not their text. |
| T-A6 | `00941c98` | commit body; `red/T-A6.txt` (7 failed, 2 passed = A6-e, A6-f controls) | **D-7 (fact):** the plan's `req.price` is `req.exit_price` (`ExitRequest`, `exit.py:55`); encoded as the code has it. The open-trade world is `tests/trades/test_exit.py:_seed_active_trade` (trade + entry fill, so `current_size` is real -- T-A1's `_seed_open_trade` carries no fill, `current_size` 0). A6-d asserts the type by NAME so the pre-fix tree reports the INSERT attempt rather than an ImportError. **RD Minor 2 honored:** A6-f's docstring names it a BOUND pin 22-G is expected to invert under BANK-4. |
| T-A7 | `b3226b51` | commit body; `red/T-A7.txt` (2 failed, 2 passed = A7-c, A7-d controls) | A7-b uses a FULL close (100/100) so `exit_post` opens exactly one `trades.connect` connection (a partial also opens `conn2`). The close-path log failure is RAISED into the outer guard (degraded fragment) rather than dropped -- the S-CONTAIN "surface the secondary diagnostic" rule; the degraded fragment carries a log-sink failure the same way. The fragment is a `<tr id="open-position-N">` literal (the form's `closest tr` target), not an OOB notice: the exit form has no notice container of its own. |
| T-A8 | `1f8dffe2` | commit body (every row's first step, method named) | No row decided "fix". C1-07 DECLARED unreachable (constant recipe triple; the RED attempt "with the override combination" is not constructible at the CLI -- no option carries an override); C1-08 DECLARED caller-prevented (CLI passes no override); C1-09 CONFIRMED-HANDLED (`routes/reconcile.py:1670`) + CONTROL; C1-16 read half RED ATTEMPT run, NOT RED at `/latches/view`, `/latches/intent`, CLI `latches parity` (only strict caller `latched_origin.py:2452` catches at `:2454`), attempts pinned as tests; C1-18 DECLARED caller-prevented (`cli.py:6245`, `:6680`; `retroactive_codex_evaluation_against_corpus` has no swing/ caller). |

## STOPS

### STOP-1 -- T-A2's A2-b / A2-c drive does not reach the site it tests (a ruling fact that reads against the code; RD's table rows)

**What the plan says.** T-A2 A2-b: "FILLED, `price=10.0`, `executions=None`, `quantity=0.5`" -> pre-fix `kind="populated"`, `shares == 0`. A2-c: the same with `quantity=0.0` ("admitted at `models.py:336`"). RD's supersession (ledger, R1 gate): "[0,1) IS reachable, via the so.quantity fallback (0 is admitted at :336) and via fractional legs."

**What the code does (by read AND by execution on the unmodified tree).** At the entry site, `_compute_execution_price(chosen)` (`schwab_reconciliation.py:464-466`) returns `None` whenever `executions` is `None` or empty -- which is EXACTLY when `_resolve_match_quantity` falls back to `so.quantity` (`:539-542`). `entry_auto_fill.py:431-444` returns `kind="empty"` ("lacks execution-grain price") on a `None` price BEFORE `:445-446` is reached. So the `so.quantity` fallback path NEVER reaches `int(quantity)` at the entry site. Probe (scratch script, the real resolver, the three Schwab seams stubbed as the sibling test module stubs them):

```
plan drive executions=None quantity 0.5 -> ('empty', None, 'Schwab BUY fill for AAPL lacks execution-grain price; please enter manually.')
plan drive executions=None quantity 0.0 -> ('empty', None, 'Schwab BUY fill for AAPL lacks execution-grain price; please enter manually.')
fractional LEG 0.5 -> ('populated', 0, None)
```

**Consequence.** As written, A2-b and A2-c pass on BOTH trees (the price branch pre-empts the guard) -- non-discriminating, a defect by the plan's own rule. At the entry site `[0,1)` is reachable ONLY through fractional LEGS (sum of legs each `> 0`, `models.py:216`); a sum of positive legs can never be `0.0`, so A2-c's `0.0` is unreachable at the entry site by any validated path.

**Why this is a STOP and not an encoded correction.** The dispatch: "A change to any T-A1, T-A2 or T-A3 table row DOES re-open [RD's read], so make none." Correcting the drive IS a table-row change.

**Both branches, ruler RD:**
- **(a) CORRECT THE DRIVE:** A2-b drives ONE execution leg of `quantity=0.5`, `price=10.0` (pre-fix, measured: `populated`, `shares == 0`; post-fix: `empty`, the sub-one-share advisory). A2-c becomes a GUARD TEST planted at the resolver's return (`_resolve_match_quantity` -> `0.0`, counting wrapper asserted >= 1; labelled unreachable on validated models, like A2-a/A2-d), pre-fix `populated`/`shares==0`, post-fix `empty`/sub-one-share. Optionally keep the plan's `executions=None` drives as CONTROLS pinning that the price branch pre-empts (pass on both trees, labelled so). The fix code is unchanged.
- **(b) KEEP THE ROWS AS WRITTEN** and relabel A2-b/A2-c as controls (they pass on both trees); the `[0,1)` refusal at the entry site would then have NO discriminator in this arc. Not recommended: C1-27's real content (RD's own words) would ship untested.

The exit side (T-A3) is NOT affected: `_build_candidate` collects every reason, and T-A3's rows do not prescribe `executions=None` (A3-d's `0.9` is driven by one fractional leg, so the reasons are `("sub_one_share_quantity",)` alone).

**State at the stop:** T-A1 committed (`1961f0ad`); T-A2 not started in code; nothing uncommitted.

#### STOP-1 -- RULED by RD (2026-09-25 15:08Z): (a) CORRECT THE DRIVE; A2-b one leg, A2-c guard, A2-b'/A2-c' controls REQUIRED; T-A2 RE-CLEARED

Author: RD (seat `swing-rd-20260924-2100`). Courier: the orchestrator. Text of record: role-mail `20260925T150827Z-rd-stop-1-ruling-a-correct-the-drive-a2-b-o.md`. The literal block quote follows, the message body verbatim:

> STOP-1 RULING (RD, sole ruler): (a) -- CORRECT THE DRIVE, NOT THE FIX -- with the controls made REQUIRED, not optional. The fact is verified at this seat before ruling: _compute_execution_price returns None when executions is None or empty (schwab_reconciliation.py:446-453, the docstring's own first bullet), and entry_auto_fill.py:431-444 returns kind="empty" on a None price BEFORE :445-446 is reached. So the A2-b/A2-c drives as I cleared them never reach the guard: they pass on both trees. The cell's measurement is the instrument; my clearance of those two rows rested on a drive I did not compute under the naive substitute, which is the rule I wrote on 2026-09-08 and did not apply here.
>
> THE CORRECTION TO MY OWN SUPERSESSION (item 3, R1 gate), stated so the ledger carries it beside the original: "[0,1) IS reachable via the so.quantity fallback" is FALSE AT THE ENTRY SITE. The fallback is only taken when executions is None or empty, and on that same condition the price branch pre-empts the quantity guard. At the entry site [0,1) is reachable ONLY through fractional legs (each leg > 0 and finite, models.py:216, so a leg sum is > 0 and can sit in (0,1)); exact 0.0 is reachable by NO validated path. At the EXIT site the fallback half still holds: _build_candidate derives price and quantity independently and collects every reason (exit_auto_fill.py:1192-1200 on this tree), so executions=None with so.quantity in [0,1) yields ("no_execution_price", "sub_one_share_quantity") there. Two sites, two reachability statements; I had written one for both.
>
> THE ROWS AS RULED:
> - A2-b: ONE execution leg, quantity=0.5, price=10.0 (a valid SchwabExecutionLeg). Pre-fix: populated, shares == 0 (the cell's measured ('populated', 0, None) IS the C1-27 defect, on the real path). Post-fix: kind="empty", advisory contains "below one whole share", NOT "non-finite".
> - A2-c: a GUARD TEST planted at swing.trades.entry_auto_fill._resolve_match_quantity returning 0.0, counting wrapper asserted called >= 1 (R4-01), labelled "unreachable on validated models" exactly as A2-a and A2-d are. Pre-fix: populated, shares == 0. Post-fix: empty, sub-one-share advisory.
> - A2-b' and A2-c' (REQUIRED, the former drives kept as CONTROLS): executions=None with quantity=0.5 and with quantity=0.0 -> kind="empty" with the "lacks execution-grain price" advisory on BOTH trees, and the advisory does NOT contain "below one whole share". These pin the pre-emption ORDER that made the original rows vacuous: if a later arc moves the price branch below the quantity guard, the control goes red and says why. A control that pins the ordering is what turns this STOP into a test instead of a memory.
> - A2-a, A2-a', A2-d, A2-e, A2-f: UNCHANGED.
>
> WHY (a) AND NOT (b): (b) leaves C1-27's real content with no discriminator in the arc that fixes it -- a fix with no RED is a fix nobody can tell is present, and the whole 22-F plan rests on RED-first. The fix code is unaffected, so (a) costs two drives and two controls.
>
> RE-OPEN AND RE-CLEARANCE, by my own terms: a table-row change re-opens my item-2 read. It is RE-CLEARED HERE on T-A2 as ruled above; the clearance attaches to the ledger transcription of these rows and to the RED output of A2-b and A2-c quoted in the T-A2 commit body (the plan's own RED-first rule, which is what this STOP was). T-A1, T-A3 and A6-f are untouched and their clearance stands. Nothing else re-opens.
>
> For the phase record: this is the third correction of one sentence of mine in one arc (the citation, the reachability, now the drive), each caught by a seat that RAN the thing -- the census's grep, the orchestrator's read, the cell's measurement. Rulings stated as semantics survived every time; every stated fact about a path I had not executed did not.

**Encoding obligations (orchestrator, no ruling of its own):** the T-A2 rows are executed AS RULED above; the plan's T-A2 table is superseded for A2-b/A2-c by this block, and A2-b'/A2-c' are added. The T-A2 commit body quotes the RED output of A2-b and A2-c (RD's re-clearance attaches to it). A2-a, A2-a', A2-d, A2-e, A2-f, T-A1, T-A3 and A6-f are unchanged.

## Findings for CHARC's register (FND-1..FND-4)

(Filled as the executing tasks reach them.)

- **FND-2 (INSTALL-STATE)** -- `DecisionIntentsUnavailableError`'s IMPORT half, `swing/latches/reader.py:273-279` (`from swing.data.repos.latch_order_intents import list_intents_for_latch` inside `load_decision_intents`, raising the type in strict mode when the import fails). Search that found it: plan section 1.2 row 1 (a read of `reader.py:262-292`), re-read at T-A8 on this tree; the READ half was driven at T-A8 and is not an escape (see T-A8 row).

## Reviewer A round table

| round | verdict | crit | major | minor | new/reopened | tokens used | DEPTH (orchestrator) |
|---|---|---|---|---|---|---|---|

**Summed Codex `tokens used`:** 0 (no round yet).
