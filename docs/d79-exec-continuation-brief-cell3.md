# D79 executing -- CONTINUATION brief (cell 3)

**Audience:** a fresh implementer cell with no prior conversation context. Cells 1 and 2 committed T1-T6 and T7a, and each returned at a fork. You continue from their committed work. Do not redo it.

**Binding, in this order:**
1. `C:\Users\rwsmy\swing-trading\docs\d79-exec-dispatch-brief.md` (main `6aef92a4`). Every section binds: TDD; commits; the envelope; Reviewer A at `strong` with repo access and the five per-round assertions; return at EVERY counted-round gate; the merge-gate list; the return report goes to chat only, and you NEVER post to a mailbox or run role_mail.py.
2. `C:\Users\rwsmy\swing-trading\docs\d79-exec-continuation-brief.md` (main `f86be3df`), the cell-2 continuation. Its sections 2-4 still bind wherever this file does not supersede them.
3. **The exec ledger, IN FULL:** `docs/superpowers/plans/2026-10-19-d79-exit-identity.exec-ledger.md` in your worktree. It holds four rulings, block-quoted:
   - Fork 1 (CHARC, the pure `check_exit_preconditions`);
   - Fork 2 (synthesized selection, plus T6-h with its REQUIRED confirm leg);
   - Fork 3 (G1);
   - the T7 read-connection ruling.
   It also holds the accepted choices 1-4 and 6-11. Never edit the block-quoted sections or the orchestrator's sections. You append `## Review (Reviewer A)` rows.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d79-exec`, branch `d79-exec`, HEAD `6f7ebade`. Your diff base is still `618d7b04`. Cell: `implementer-opus-high`.

## 1. State you inherit (orchestrator-QA'd against disk)

| Commit | What it holds |
|---|---|
| `1b470e99`..`417b4674` | T1-T5 (cell 1) |
| `04f74a1a` | the INV-MODEL roster classification of `ExitRecordFlag.__post_init__` |
| `6a6e987a` | T6. **RED BY DESIGN.** Its commit body names every red: the 3 over-size tests in `test_exit_rerender_anchor.py` and 8 record-on-first-POST tests in `test_exit_post_audit_columns.py`. T7 turns all of them green: the first 3 UNCHANGED, the 8 by named supersession. |
| `512ed9ca` | T7a, the pure helper and test (iv) |

- **Untracked:** `tests/cli/test_d79_cli_exit_confirm.py`, cell 1's T8 tests. It has a known seeding bug: after the planted 3-share fill, the 3-share exit exceeds the 2 shares left. Fix it in T8, then commit it with T8.
- **The last full suite** ran on `efd3a80f`: 4 failed (3 untracked T8 tests; 1 INV-MODEL regression, since fixed), 15418 passed, 13 skipped. You do not re-run it before T7. The working tree is red by design until T7 lands.
- **T6-g's legs** must match the Fork 3 ruling. Check what `6a6e987a` committed for T6-g; any leg written to the old text is rewritten by replacement in T7 and named.

## 2. What the two newest rulings change in T7 (full text in the ledger)

**Fork 3 (G1):**
- When the claimed anchor is not restorable (a map-less legacy envelope, or a fresh fetch that is not `populated`), the flags are dropped and the refresh notice shows.
- The legacy first POST returns 400 with no fill, no flag text and the fresh anchor. Its message says nothing was recorded because the list must be re-confirmed.
- Sandbox tests that need F1 to render are rewritten with `_exit_candidates_maps_equal` stubbed True. Each is named SUPERSEDED.

**The T7 read connection (supersedes plan T7 step 2's "own short connection", and cell 2's choices 5 and 8):**
- There is NO second connection.
- The precheck's `get_trade`, `anonymous_fill_matches` and `recorded_exit_identities(...).unreadable` all run on the route's one connection (`routes/trades.py:3353`), after it opens and before `record_exit`. They run inside the existing `try` whose `except ValueError` drives the re-render.
- Required tests:
  - the 22-F tests in `tests/web/test_routes/test_22f_exit_post.py` stay green UNCHANGED (a red there is a regression);
  - a NEW test: an accepted claimed POST opens exactly ONE connection through `swing.web.routes.trades.connect`;
  - T7-a's confirm leg proves `record_exit` is entered with no caller-held transaction.

## 3. Remaining ladder

1. **T7:**
   - plan T7, with Fork 1's route precheck and its discriminators (ii) and (iii), Fork 3, and the connection ruling;
   - the 8 superseded `test_exit_post_audit_columns.py` tests, rewritten by replacement and named;
   - `test_exit_rerender_anchor.py` green UNCHANGED.
2. **T8:** the CLI. Fix and commit cell 1's untracked tests.
3. **The supersession classification:** run all of `tests/web/test_routes/` and classify EVERY red as SUPERSEDED (named) or REGRESSION (fixed).
4. **T9 step 1 and the census commands:** column names checked against the live DDL (`mode=ro`, schema only); both commands written into the exec ledger.
5. **The full fast suite GREEN** (backgrounded, read off the saved output).
6. **Reviewer A** at `strong`. Its prompt carries, besides the brief's list:
   - all four rulings, as rulings: findings against them are TAGGED, not suppressed;
   - choices 1-4 and 6-11, with challenge invited;
   - AL-1..AL-9 with their reasons.

   Return at EVERY counted-round gate, with that round's ledger row as your final message. After convergence, run the full suite again on the final head.

## 4. If a fork appears

STOP and return it with both branches specified. Do not choose for yourself.
