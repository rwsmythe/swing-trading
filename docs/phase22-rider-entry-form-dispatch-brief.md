# Phase 22 rider — the entry form: D47 companion + D97 + D98 (dispatch brief)

**From:** CHARC. **To:** the orchestrator (riders stage: executing directly, no plan loop). **Commissioned by the operator 2026-11-14, his words: "Entry-form rider: commission the rider".** **Scope:** `swing/web` and `tests/` only. No schema, no new module, no dependency, no `swing/trades` or `swing/data` edit (`swing/trades/equity.py` is CALLED, never changed). No tripwire. **Cell (recommendation):** `implementer-opus-high` -- the design is settled, but it is the operator's money-bearing form and the change touches about seventeen call sites. The lane tiebreak (recipe section 2A) is yours. **Reviewer A:** one strong round to convergence. **Reviewer B:** yours, on the merged tree, with the files in section 0 named in the prompt (the zero-repo-read rule). **Witness:** operator, in a real browser, step by step (section 5).

Every line number below was read at `d9b59d1f` on 2026-11-14. A brief is a hypothesis about the code: re-ground each one, and when the code disagrees with this brief, the code wins and the deviation goes in the return report with its reason.

## 0. Read first

- Register rows **D47** (the companion sentence only), **D97**, **D98** in `docs/tool-director-context.md` section 4.
- `swing/web/routes/trades.py`:
  - `_rerender_entry_form_with_error` (`:601-704`) and its 15 call sites inside `entry_post` (`:1008` to `:2540`).
  - the missing-field re-render (`:2059-2150` and on), the only site that keeps the pre-trade answers today.
  - the duplicate-position re-render (`:2365-2392` and on).
  - `sizing_hint` (`:707-779`), equity at `:747-750`.
  - `_restore_fresh_auto_fill` (`:567`) and `_with_decision_choice` (`:585`): they replace no price and need no change.
- `swing/web/view_models/trades.py`: `TradeEntryFormVM` draft fields (`:330-362`, `:439`), the sizing block of `build_entry_form_vm` (`:857-886`).
- `swing/trades/equity.py:48` `sizing_equity(real_equity=, floor=)`; the two existing spellings of the floored call: `swing/pipeline/runner.py:1763` and `swing/web/view_models/latches.py:1223`.
- `tests/web/test_routes/test_fx2_claimed_undecodable_round_trip.py` (`_THIRTEEN` at `:131`, the pin at `:172-178`): the SG test that PINS the draft loss and is written to go red the day it is fixed.
- CLAUDE.md gotchas: the hidden-anchor round-trip rules; "server-stamp, don't trust hidden inputs"; HTMX 4xx swap.

## 1. The three defects (verify each before building)

**A. D47 companion -- the early 400s drop the operator's pre-trade answers.** `_rerender_entry_form_with_error` rebuilds the VM and replaces six fields (date, price, stop, shares, rationale, notes). The 19 `draft_*` fields keep their defaults, so every one of its 15 callers returns a form with the pre-trade answers blank. Thirteen of them are required (the SG test measured the list), `event_handling` and `gap_risk_handling` are dropped too. The operator retypes the journal entry to get past a typo in a price.

**B. D97 -- the form sizes on unfloored equity.** `build_entry_form_vm` (`view_models/trades.py:858`) and `sizing_hint` (`routes/trades.py:747`) hand `compute_shares` the raw `current_equity`. The nightly recommendation and the latch card use `sizing_equity(real, cfg.account.risk_equity_floor)`. Seen live 2026-10-26: the entry form's 13.96 dollar risk budget beside the latch card's 37.50 for the same account.

**C. D98 -- a refused submit re-renders prices next to sizing computed on other prices.** Each full-form re-render replaces `entry_price` and `initial_stop` with the submitted values and leaves `suggested_shares`, `risk_dollars`, `risk_pct` and `sizing_zero_line` as the builder computed them from the server-resolved prices.

**Cell: before any edit, read the live shape** (`mode=ro`, plain sqlite3, never `swing`'s `connect`): the configured floor and the real equity the form would compute today. If real equity is NOT below the floor, say so in the report -- defect B's live discriminator then has no live instance and its test stands on a seeded world only.

## 2. The change

**C1 -- one sizing function, three callers (B and C together).** In `swing/web/view_models/trades.py` add one function that takes the config, an entry, a stop and the REAL equity, and returns the four fields (`suggested_shares`, `risk_dollars`, `risk_pct`, `sizing_zero_line`). It applies `sizing_equity(real_equity=..., floor=cfg.account.risk_equity_floor)` before `compute_shares`, and returns the builder's present else-branch values (0, 0.0, 0.0, None) when the geometry is not `entry > 0 and 0 < stop < entry`. Callers:

1. `build_entry_form_vm` (replaces `:857-877`).
2. `sizing_hint` -- the floor applied to its equity; its dim / infeasible branches keep their present wording.
3. the re-render helper of C2.

`TradeEntryFormVM` gains one non-rendered field carrying the real equity the builder read (default 0.0), so a re-render recomputes without a second DB read. `prefill_shares` keeps its present rule (`:884-886`).

**C2 -- one re-render helper, every entry-side site (A and C together).** One function in `routes/trades.py` that takes the rebuilt VM, the submitted date / price / stop / shares / rationale / notes, and ONE drafts object, and returns the VM with: those six replaced, the four sizing fields recomputed on the SUBMITTED geometry through C1, and every `draft_*` field set from the drafts object. `input_shares` stays the submitted count; the sizing never reads it.

The drafts object is built ONCE near the top of `entry_post` from the submitted form values, with the exact expressions the missing-field site uses today (`:2092-2120`, including the cleaned emotional-state tuple and `draft_entry_intent`). It is passed to all three re-render paths:

- `_rerender_entry_form_with_error` gains a `drafts` parameter; all 15 callers pass it.
- the missing-field site (`:2083`) and the duplicate-position site (`:2377`) call the same helper for these fields. `missing_fields=` and the auto-fill anchor handling stay where they are, unchanged.

Enumerate the entry-side `dc_replace` sites by grep at build time and list them in the report with a disposition each (uses the helper / replaces no price, exempt). Existence is not completeness: D98's row counted five at `ef4ecd85`, this read found three that replace prices.

**Not changed, and the tests must show it:**

- Anchor behaviour. A recovery form still carries the FRESH auto-fill anchor and never the refused one (D86 form C, test 4h's clause (iv)); a refused decision anchor still falls back to the newest night. Drafts are the operator's typed answers, not anchors.
- The soft-warn confirm path and its `form_values` round trip.
- `trade_entry_form.html.j2:98`'s htmx `SyntaxError` (D47's own row) stays with the web-surface sweep. Do not touch that attribute.
- Status codes, the HTMX fragment roots, the 204 + `HX-Redirect` success path.

## 3. Tests -- RED first, each seen failing for the stated reason

Build the worlds from the existing route-test fixtures (`seeded_db`, the FX-2 file's `_world` / `_data` / `_serialize_first_form`).

1. **Drafts survive an early 400.** For at least three different callers of `_rerender_entry_form_with_error` chosen from different rungs (a rationale refusal, an anchor refusal, a decision-night refusal): post a full form, assert 400, serialize the returned form, assert all 15 answers equal the submitted values. Then parametrize or loop over ALL 15 call sites if a refusing input for each can be built from the existing tests; where one cannot, name it in the report.
2. **The FX-2 pin retires, by design.** `test_fx2_a_claimed_undecodable_anchor_is_one_resubmit_from_a_written_trade` goes red at its STEP 2. Rewrite it: the recovery form KEEPS the thirteen, and STEP 3 resubmits the recovery form's own state with nothing retyped and writes the trade. The anchor assertions of STEP 1 stay byte for byte. Re-read `test_entry_refusal_rule_decision_night.py` (its docstring at `:18` names the retyping) and correct what the fix makes false.
3. **Floor parity (D97).** A world with real equity below the floor: the entry form's rendered risk figure and suggested max equal what `compute_shares` returns on `sizing_equity(real, floor)` for the same geometry, and the `sizing-hint` endpoint returns the same numbers. A second world with real equity ABOVE the floor: the figures are unchanged from today. Compute both expected values by hand in the test's comment, under the old path and the new, and confirm they differ in the first world.
4. **Re-render sizing (D98), at each of the three re-render paths:** a refused submit whose submitted geometry is a risk-bound zero renders the stated zero line while the server-resolved geometry would have been feasible; a refused submit with feasible submitted geometry renders the sizing on the submitted prices, and that figure differs from both the server-resolved sizing and the submitted share count.
5. **Existing tests that pinned the unfloored figure** will go red. List each in the report with the old and new expected value and why the new one is right; none is deleted.

## 4. Gates

- Fast suite green on the branch, then on the MERGED head, the line read from the transcript with the sha.
- `ruff check swing/` clean.
- Reviewer A to convergence; Reviewer B on the merged tree with named files.
- Composition: this arc lands on a tree that carries the SG arc's entry-route work (D86 form C, D102's decision night). The merge step is a gate: re-run the SG route tests named in section 0 on the merged head and say so.
- No merge-timing constraint: no schema bump.

## 5. Operator witness (after the merge; one step per message, wait for his result)

1. Open the entry form for a watchlist ticker. Compare its risk figure with the latch card or the nightly recommendation for the same account: they agree on the floored budget.
2. Fill the pre-trade answers, break one early-validated field (a blank rationale will do), submit. The form comes back with the error AND every answer still filled.
3. On that returned form, the suggested max and risk line match the prices shown on it.
4. Cancel. Nothing was written (`trades` count unchanged, read `mode=ro`).

The unseeded default state is the witness: no synthetic data is planted for it.

## 6. Return report

Per the recipe: commits, the RED evidence per test, the enumerated `dc_replace` sites, every deviation from this brief with its reason, the suite lines, and the Reviewer A responses saved on disk. The cell reports in chat to the orchestrator and posts nothing.

## 7. For RD (CC, no ruling asked)

Two effects land in your content; say so only if you dissent. (i) FX-2's corrected point 2 (the operator retypes the answers on the recovery form) becomes false and retires with the pin, as your test's own message says. (ii) The early-400 forms will pre-select the operator's SUBMITTED `entry_intent`, as the missing-field form already does, in place of the suggestion.
