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

## Execution (executing cell; TDD, then Reviewer A at `strong`)

Commits on `exit-rerender-anchor` (base `75de0ac8`), each with its RED in the body:

| commit | ruling | tests added |
|---|---|---|
| `4bcda3a2` | (e) typed values kept on the `ValueError` branch and `_reject_anchor` (`_rerender_exit_form_with_error`) | typed values x1, `_reject_anchor` x2 (malformed; valid dict + bad index) |
| `ccc4bd83` | (b)(c)(d) the d2-strict restore + the refresh notice | unchanged-list restore, blank stamp verbatim, E2E-2 two-tab control, advisory control, parity re-fetch, unclaimed control x2, round trip |
| `ec0929c3` | (a) candidate pick by hash, under the gate only | pick restored, pick-not-carried control |
| `7311a0af` | Codex R1 minor: frozen resolver clock in the tests | -- |

Against the base code (`75de0ac8` `swing/web`) the 13 tests fail 11 and pass the 2 unclaimed controls; the round trip fails `assert 'stop' == 'trim'` there (the live mis-recording path). Controls mutation-checked on `ccc4bd83`: a d3 port (gate always true) fails the two-tab and parity tests; a b1 port (advisory cleared on restore) fails the advisory test; a restore-unclaimed port fails both unclaimed tests.

Suite before review (`ec0929c3`): `15341 passed, 13 skipped` (`suite-pre-codex.txt`).

### Reviewer A rounds

Evidence: `C:\Users\rwsmy\swing-data\review-transcripts\exit-rerender-anchor\r1\` (`codex-review.txt` 730,669 bytes, `prompt.md`, `diff.txt`, `run.sh`, `.copowers-findings.md`).

| round | reviewed head | model / effort | `^ERROR` | footer | verdict | crit | major | minor | tokens used | depth (orchestrator) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `ec0929c3` | gpt-5.6-sol / high | 0 | present | clean | 0 | 0 | 1 | 178,835 | |

R1-minor (live clock in the new tests): accepted, fixed in `7311a0af` without a round. The loop ended at round 1.

## Orchestrator QA of the executing cell (2026-09-28, read on disk at `b8dde1eb`)

- **Depth:** `cell_depth --agent` measured 307,264 (the Agent usage figure was 310,648). This fills the round table's DEPTH column for R1.
- **Scope:** `git diff --stat 75de0ac8..HEAD` shows `swing/web/routes/trades.py`, `swing/web/view_models/trades.py`, `swing/web/templates/partials/trade_exit_form.html.j2`, the new `tests/web/test_routes/test_exit_rerender_anchor.py`, and this ledger. There is nothing in `swing/trades/` or `swing/data/`, and no schema change.
- **R1 validity, read at this seat:**
  - banner `gpt-5.6-sol`, reasoning effort `high`;
  - `^ERROR` count 0;
  - the anchored `NO_NEW_CRITICAL_MAJOR` at `codex-review.txt:6985`, directly above the footer `tokens used` / `178,835` at `:6986-6987`; `:6992` is the CLI's echo;
  - `exit.txt` reads `0`.
  - **VALID. Converged in one counted round.**
- **Suite, final head `b8dde1eb`:** the rerun reads `15341 passed, 13 skipped` with the worktree as resolver. The first post-Codex run had ONE failure, `tests/data/test_migration_0039_provenance_corrections_tier2.py::test_uncovered_barrier_absent_terminal_is_accepted_both_shapes[2026-08-10T12:41:34Z-before_barrier-4]`. It passed isolated with `-n 0` and under xdist over `tests/data`. Its mechanism is NOT established, and its traceback was lost. **It must be reproduced `-n 0` FIRST at the merged head. It is not a known banked red.**
- **Trailers:** zero `Co-Authored-By`. `ccc4bd83` and `ec0929c3` each carry a parsed `GREEN: ...` trailer: the `Word:` final-paragraph hazard. Both sit below the tip, and this ledger cites branch SHAs, so they are RECORDED here and NOT rewritten. **The merge form is `git merge --no-ff`, never a rebase.**
- **Flags carried:**
  - The d2 gate compares `candidates_map` only, as ruled. A tampered envelope with an equal map echoes its top-level fields on restore; the POST's rejection ladder still governs the resubmit. This goes to CHARC/RD as information.
  - The `TradeExitFormVM` comment ("always 'schwab_auto' on populated") is stale under a restore of a tampered claim. It is minor and NOT changed.
- **Verdict:** QA PASS. **REMAINING before merge:**
  1. the OPERATOR-WITNESSED browser check, step by step, against the worktree (`PYTHONPATH=. python -m swing.cli web` from this worktree, on a port other than any running `swing web`);
  2. then `git merge --no-ff`, the merged-head fast suite read, and the 0039 test reproduced `-n 0` if it reds.
