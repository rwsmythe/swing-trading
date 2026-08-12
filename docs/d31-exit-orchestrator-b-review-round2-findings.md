# D31-exit — the orchestrator's B review, round 2 (the FIXED tree), and the adjudication

**Reviewed tree:** branch `d31-exit` @ `0ce45b3c` (the fix arc's final head).
**Verdict: `NEW_CRITICAL_MAJOR_FOUND`** — 2 MAJOR, 2 MINOR.
**Transcript:** `.codex-b-review-orch-2b.txt` (1,191,188 bytes) in the worktree root.
**Assertions:** banner `gpt-5.6-sol` / `reasoning effort: high` / anchored `^ERROR` **0** / anchored
`^tokens used` **1** / `EXIT=0` captured in-file / sandbox `read-only`.

**A first attempt DIED mid-file-read** and is preserved as
`.codex-b-review-orch-2-DIED-INCOMPLETE-no-footer-no-verdict.txt` (500,008 bytes, banner present,
**no footer, no verdict**). It was not treated as a result. That artifact is the concrete case for
CHARC's queued verdict-line anchor: absence of a verdict cannot distinguish "found majors" from "the
process died" — only the `^tokens used` footer separated them here.

**Prompt:** `scratchpad/orch-b-review-prompt-2.md`, written by the orchestrator. Same file set as
round 1, deliberately NOT trimmed after the first attempt died — narrowing B's input to make it
finish is indistinguishable in the transcript from a legitimately scoped review.

---

## MAJOR A — the write-boundary invariant decays, and the read path trusts it unconditionally

`swing/web/view_models/trades.py:1057`.

The fix arc established, at the POST boundary, that a top-level `schwab_order_id` is retained only
when the persisted values derive from that id's own candidate. **The read path then accepts any
non-blank id as an affirmed link without ever rechecking that the fill's CURRENT date, price and
quantity still derive from it.** That is safe only if nothing can change a fill's values after the
id was affirmed. Two writers can, and one population never had the guarantee at all:

- **`swing/trades/reconciliation_auto_correct.py:2057`** issues
  `UPDATE fills SET {field_name} = ? WHERE fill_id = ?` — a single-column update. **The file never
  writes `schwab_source_value_json` at all** (verified: zero occurrences). So a correction to
  `fill_datetime`, `price` or `quantity` moves the persisted values away from the id's candidate and
  leaves the id standing.
- ~~**`swing/trades/reconciliation_classifier.py:1902`** — close-price corrections target
  `fills.price`, same shape.~~ **WRONG, corrected 2026-08-12 by the fix-arc implementer, which
  checked it instead of repeating it.** That file contains **zero** `conn.execute`/`UPDATE`
  statements; `:1902` returns a `ClassificationResult` carrying `correction_target={"price": ...}`.
  **It PROPOSES; the corrector WRITES.** I cited a caller of the writer as if it were a second
  writer. The finding is unaffected — `reconciliation_auto_correct.py:2058` is a real single-column
  writer and one is enough to make the point — but the claim as published was false, and it was
  published to RD.
- **Pre-fix rows** carry ids affirmed under the OLD, weaker rule and were never re-examined.

**Consequence:** on the next render that stale id enters `existing_fill_order_ids` and **silently
suppresses the broker candidate** — the exact behaviour the 2026-08-11 ruling forbids, reached by a
different road than the one the arc closed.

**This is the arc's own original defect wearing a new coat.** D31 began because a *stamp* was trusted
in place of a derived value; the fix replaced token-trust with values-derive-from-order at the write
boundary, and the read boundary still trusts the token. **The guarantee is only as durable as the
weakest writer that can move a fill's values, and that writer does not know the envelope exists.**

## MAJOR B — the banked truncation has a consequence that was not on the record when it was banked

`swing/trades/exit_auto_fill.py:1068`.

RD banked the `ExitAutoFillCandidate.quantity` `int`→`float` migration and ruled the in-scope fix to
be the comparison alone. That was decided knowing the display/envelope would keep the truncated
value. **Two consequences were not in front of him:**

1. **A sub-1-share execution takes the whole trade-detail page down.** `int(0.9)` is `0`;
   `ExitAutoFillCandidate.__post_init__:300` raises `ValueError` on `quantity <= 0`; `_build_candidate`
   has no refusal path for it (its three reasons are `no_execution_price`, `no_quantity`,
   `no_usable_date` — a resolved 0.9 is none of them); the build loop at `:775` has no `try/except`;
   and the caller at `view_models/trades.py:1131` wraps the call in `try/finally`, **not**
   `try/except`. So the `ValueError` propagates to the route. **Loud, not silent — which is the
   better failure — but it is a hard 500 on a reachable input.**
2. **The value hashed, the value compared, and the value persisted disagree** for any fractional
   quantity ≥ 1: a 10.9-share execution is hashed and duplicate-compared as 10.9 while being
   displayed, submitted and persisted as 10 — and linked to that order's id.

**Reachability:** RD's own live query found 43 fills, ZERO fractional, so there is no live instance.
Fractional quantities are permitted by `fills.quantity REAL` (migration 0014) and by the Schwab
model, so this is **not** schema-prevented — the citation discipline requires saying so plainly
rather than dismissing it.

**This does not overturn the banking; it re-opens the INPUT to it.** The banking was a reasonable
call on the record as it stood. A 500 on a reachable input is a different question from a display
mismatch, and it belongs back with the person who banked it.

## MINOR C — a tolerance justified by a grain nothing enforces

`swing/trades/exit_auto_fill.py:1217`. The `abs_tol=1e-9` comment justifies itself as "five orders of
magnitude below the smallest meaningful share difference," asserting a 1e-4 grain that no Schwab
model, schema or writer enforces. The tolerance itself is defensible and errs toward the alarm; the
JUSTIFICATION is a claim the code does not support — the same class this arc has now corrected at
seven-plus sites. Minor-scope: the comment is wrong, the behaviour is not.

## MINOR D — a test whose opening contradicts its own assertions

`tests/trades/test_exit_auto_fill.py:1835`. The docstring opens by saying the same-session alarm must
NOT fire and describes an unflagged result; the test's name, its later paragraph and its assertions
all require the candidate to be FLAGGED. The assertions pin the correct current behaviour, so the
test is not vacuous — but a future reader reconciling the contradiction in the wrong direction would
restore precisely the behaviour the rewrite rejected. This is the load-bearing-comment class in a
test docstring.

---

## Disposition

**MERGE REMAINS BLOCKED.**

- **MAJOR A** is behaviour-bearing, major-scope, and reaches beyond this arc's diff into the
  reconciliation writers and the existing ledger population. It is **RD's**: it is his ruling's
  guarantee failing at a second boundary, the fix implies a read-side re-derivation with real cost,
  and it raises a data question — whether rows on the live ledger already carry residual ids that
  should be demoted to anonymous.
- **MAJOR B** returns to RD as a **re-decision on new information**, not as a challenge to his ruling.
- **MINORS C and D** are minor-scope and correctable without a round, by whichever hands take the next
  pass.

**Not recommended: a third fix dispatch before RD answers.** MAJOR A's fix shape is a design question
about where the values-derive-from-order check lives, and MAJOR B may or may not reopen the banked
migration. Dispatching now would be guessing at both.

**Also still owed from the previous round: RD's Q1 ruling** on whether the MAJOR-1 semantics correctly
extend to the default-radio override case (a second shipped-contract supersession, already encoded on
this tree). **Q1 and MAJOR A are the same subject** — what an order id asserts, and when it stops
asserting it — which is why they go to him together.
