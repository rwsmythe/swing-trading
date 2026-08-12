# D31-exit — the orchestrator's B review, round 5: THE GATE IS SATISFIED

**Reviewed tree:** `d31-exit` @ `3cb2fdd7` (comment-scope minors closed after, at `77336f65`).
**Verdict: `NEW_CRITICAL_MAJOR_FOUND`** — 2 MAJOR, 3 MINOR.
**Transcript:** `.codex-b-review-orch-5.txt` (1,666,139 bytes). **Assertions:** `gpt-5.6-sol` / `high` /
anchored `^ERROR` **0** / anchored `^tokens used` **1** / `EXIT=0`.

**Under the gate adopted by RD and ratified by CHARC (`0470737e`) — *B is clean for merge when it
returns no unbanked CRITICAL or MAJOR that this arc INTRODUCED* — THIS TREE PASSES.** Both majors are
evidentially pre-existing and are banked below.

**Accepted-limitations declaration, fourth consecutive confirmation:** all SEVEN carried with their
reasons and an invitation to challenge the reasons. **None re-raised. No reason challenged.** Findings
still returned, so the practice continues to suppress re-litigation without suppressing review.

---

## PROVENANCE — established against `main`, quoted, not asserted

Per RD's binding evidential standard (burden of proof on whoever claims PRE-EXISTING; `git log -S` or
`git diff --stat` **quoted**; contested → INTRODUCED):

```
git show main:swing/trades/exit_auto_fill.py | grep -n "quantity=int(quantity)"   -> :709
git show main:swing/trades/exit_auto_fill.py | grep -c "isfinite\|math.isinf"     -> 0
git show main:swing/trades/exit_auto_fill.py | grep -n "price <= 0"               -> :183
```

**`main` has zero finiteness checks in this module**, truncates the same way at `:709`, and its
`__post_init__` already accepts `inf` by testing only `price <= 0`. **Both defects behave identically
without this arc.** Not contested, so default-to-introduced does not engage.

## BANK-3 — a non-finite quantity crashes the page (`exit_auto_fill.py:1213`)

Execution legs may carry any finite positive float (`integrations/schwab/models.py:216`) and
`_resolve_match_quantity` sums them unchecked (`trades/schwab_reconciliation.py:541`), so several
large finite legs sum to `inf`. **`int(inf)` raises `OverflowError`**, which neither the candidate loop
nor the GET route catches → **500 instead of a stated refusal.** The mapper permits execution legs
when `filledQuantity` is absent, so no coherence check prevents the shape.
*Provenance:* **PRE-EXISTING** (evidence above). *Class:* **crash from broker-permitted input — the
same class as BANK-1 and the banked `SchwabSchemaParityError`.** Third instance; the register should
scope them as one problem.

## BANK-4 — a non-finite price reaches the operator as `value="inf"` (`exit_auto_fill.py:1200`)

The derived price is refused only when `None`, never when non-finite; a multi-leg VWAP can overflow
from finite legs (two at `1e308`, quantity 1). `ExitAutoFillCandidate.__post_init__` accepts it
(`:387` tests only `price <= 0`), so the template renders `value="inf"` into a required number input
(`trade_exit_form.html.j2:139`), **the browser refuses the submit, and no refusal reason or advisory
explains it.**
*Provenance:* **PRE-EXISTING.** *Class:* **a surface presenting what the operator cannot act on —
the same class as BANK-2 and the advisory that instructed an impossible action.** Third instance.

**The two classes now have three instances each, from independent findings.** That is the argument for
scoping the follow-on by CLASS rather than by site, exactly as RD scoped the parity gap.

## BANK-5 — a duplicate-warning test that cannot fail for its stated reason

`tests/web/test_routes/test_exit_form_auto_fill.py:850` claims the advisory is the only warning surface
for a SINGLE candidate, while its fixture always supplies TWO. It would stay green if the banner became
gated on the multi-candidate branch, leaving a single flagged candidate operator-invisible. Production
is correct today; the claimed regression protection is not.
*Not closed at the gate* because making it discriminating requires changing the fixture to one
candidate — a test behaviour change, not a comment fix.

## CLOSED AT THE ORCHESTRATOR'S GATE (`77336f65`) — comment-scope, suite-verified

- `tests/trades/test_exit_auto_fill.py:2372` — the docstring said the operator *"records such a fill by
  hand"*, **contradicting the advisory the previous pass had just written** (which says he cannot, and
  points him to Daily-management notes) **and this same test's own assertion.** The load-bearing-comment
  class inside the arc's own new material.
- `tests/web/test_routes/test_exit_form_auto_fill.py:1331` — claimed `_compute_execution_price` and
  `_resolve_match_quantity` read `order_activity_collection`; both read `so.executions`. Corrected, and
  now names which tests actually cover the production derivation.

Suite after: **10814 passed / 7 skipped / 1 failed** — identical to before, confirming comment-only.
The one failure is `test_run_stub_skip_exits_zero`, **which fails on `main` itself** (verified by
running it there); it is not this arc's and not a regression.
