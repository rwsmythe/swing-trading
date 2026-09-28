# Exit POST re-render anchor (RD 1(iii) / 22-F AL-6) -- ledger

Brief: `docs/exit-rerender-anchor-brief.md` (main @ `eefbde21`). Branch `exit-rerender-anchor` @ `eefbde21`. Operator direction 2026-09-28: "perform the followups".

## Round 0 -- the cell's return (implementer-opus-high; no code, no Codex)

**Depth:** 277,132 subagent tokens, from the Agent usage figure in the task notification.
**Scratch evidence** (the measuring test file, deleted from the worktree before return): `C:\Users\rwsmy\AppData\Local\Temp\claude\C--Users-rwsmy-swing-trading\808f802f-a54f-4660-a957-80707a2d30cb\scratchpad\test_zz_round0_scratch.py`, plus `round0_measure.json` and `round0_measure2.json` beside it.

What follows is a summary by the orchestrator, NOT a quote. The full return is in the orchestrator session's transcript, and every fact below was cited there with file:line on `eefbde21`.

### Premise

TRUE as written, but incomplete. Every exit-POST refusal that re-renders the form rebuilds the VM FRESH:
- the `record_exit` `ValueError` branch (`routes/trades.py:3188-3203`);
- the nine `_reject_anchor` call sites. These re-derive DELIBERATELY, which is the clear-the-bad-anchor rule pinned by `test_e_*` in `tests/web/test_routes/test_exit_post_audit_columns.py`.

The invalid-reason path (`:2460-2467`) and the FastAPI parse errors (`app.py:771-801`) are banner-only.

### Measured facts that change the design

1. **World unchanged (E2E-1, real resolver).** The fresh re-render's `schwab_source_value_json` and candidate hashes are BYTE-EQUAL to the submitted ones; only `auto_fill_audit_at` differs. The resolver depends only on the orders, the DB fills and `now`, and `now` touches only the timestamp, the degraded check and the lookback.
2. **World changed (E2E-2, two tabs).** After tab 1 records order `o2`, tab 2's refused re-render correctly offers only `o1`: the `existing_fill_order_ids` exclusion held. A literal entry-precedent restore would re-offer `o2`.
3. **Typed values are ALL lost on every re-render:** date, price, shares, notes and reason. The reason `<select>` never emits `selected` (template `:147-151`), so the browser defaults to the first option, `stop-hit` (`ExitReason`, `exit.py:38`). A corrected resubmit then records `action='stop'` (`exit.py:189-190`, where `STOP_HIT` always wins) with a wrong date. A non-default candidate radio is also lost: `checked` is unconditional on `loop.last`.

### Out of scope, flagged (verified by the orchestrator's read)

- **The exit POST has NO duplicate-order check.** E2E-2 tab 3 replayed an unedited form and recorded order `o2` TWICE, both fills `schwab_auto`. `record_exit` (`swing/trades/exit.py`) carries no guard against a selected candidate's `order_id` that is already on a fill: a grep for `duplicate|order_id|already recorded` in `exit.py` returns nothing. A real-money double-record through a second tab or a back-and-resubmit. Routed separately; see the orchestrator's fyi.
- Entry side, `routes/trades.py:1184-1189`: the pre-ladder re-renders run before the claim strip, so a whitespace-padded claim is restored without its `populated` kind. Cosmetic.
- The A1-e docstring cites `routes/trades.py:487-505`; the code is now at `:512-550`.

## Round 0 gate -- ORCHESTRATOR RULINGS (2026-09-28)

The cell routed d1 and d2-lenient to RD, and ruled everything else rulable at the orchestrator's seat. **Neither RD-routed branch is taken**, so every ruling below is the orchestrator's. RD and CHARC are CC. A dissent from a LANDED ruling goes upward and does not block execution.

- **(d) d2-strict.**
  - Keep the fresh fetch.
  - Restore the SUBMITTED anchor triple ONLY when the fresh result is `populated` AND the fresh `candidates_map` equals the submitted `candidates_map`, compared as parsed JSON. By E2E-1 the two then differ only in `auto_fill_audit_at`.
  - Otherwise, keep the FRESH anchor, keep the typed values, and append one banner notice. The notice says the Schwab fill list changed or could not be re-read, so the auto-fill selection was refreshed.
  - Under a degraded or parity re-fetch: NO restore, and the retry records `operator_typed`.
  - **Reason:** it keeps the ledger-current exclusion and the possible-duplicate advisory. It restores exactly when restoring is safe. It asks no identity question of RD.
  - The asymmetry with entry's A1-e under parity is DELIBERATE and recorded here: entry has no already-recorded-order exclusion to protect.
- **(a) a2's coverage, restored BY SIGNATURE HASH against the FRESH list, and only under the (d) gate.**
  - The selected candidate is re-checked by matching the submitted selected hash in the fresh list; this also restores a non-default radio pick.
  - Under the gate the hashes are identical by construction.
- **(b) b2.**
  - `auto_fill_kind='populated'`;
  - `fill_origin` = the submitted claim, stripped;
  - advisory = the FRESH fetch's advisory, which keeps the D31 notices.
  - b1 (clearing the advisory) is REJECTED, because it would drop the possible-duplicate notice.
- **(c) c2.** A restore is possible only when the claim was made AND the anchor envelope parsed to a dict, the same gate as the stamping branch (`:2737`). An unclaimed anchor is never restored. `_reject_anchor` keeps clearing the anchor (the `test_e_*` pins stand), and it now preserves the typed values.
- **(e) IN SCOPE.** Typed values are preserved on the `ValueError` branch AND on `_reject_anchor`: date, price, shares, notes, the reason, rendered with `selected`, and the candidate pick, rendered with `checked`.
  - Implement this with VM fields and a route helper `_rerender_exit_form_with_error`, modelled on `_rerender_entry_form_with_error` (`:464`).
  - **Sub-fork, shares after an "exceeds remaining" refusal: KEEP the typed value.** This matches entry. The authoritative `max=` from the DB is still rendered, so the browser blocks the resubmit until it is corrected.
  - Reason: a wrong-reason default is a live mis-recording path (`stop-hit` -> `action='stop'`).

**Tests:** the cell's list of nine, with the pre- and post-fix arithmetic it gave, is adopted as the minimum. Test 4 (E2E-2) and tests 5 and 7 are controls that must FAIL a d3, b1 or restore-unclaimed port; state that in their docstrings.

**Envelope:** `swing/web/routes/trades.py`, `swing/web/view_models/trades.py`, `swing/web/templates/partials/trade_exit_form.html.j2`, and tests. `swing/trades/` and `swing/data/` are read-only. There is no schema change.
