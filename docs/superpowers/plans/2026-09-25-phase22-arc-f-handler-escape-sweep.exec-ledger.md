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
| T-A2 | -- | -- | **STOP-1 (below)** |

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

## Findings for CHARC's register (FND-1..FND-4)

(Filled as the executing tasks reach them.)

## Reviewer A round table

| round | verdict | crit | major | minor | new/reopened | tokens used | DEPTH (orchestrator) |
|---|---|---|---|---|---|---|---|

**Summed Codex `tokens used`:** 0 (no round yet).
