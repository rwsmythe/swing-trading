# D31-exit — the orchestrator's B review, round 4, and a proposed STOPPING RULE

**Reviewed tree:** `d31-exit` @ `14568739`. **Verdict: `NEW_CRITICAL_MAJOR_FOUND`** — 3 MAJOR, 1 MINOR.
**Transcript:** `.codex-b-review-orch-4.txt` (1,748,610 bytes). **Assertions:** `gpt-5.6-sol` / `high` /
anchored `^ERROR` **0** / anchored `^tokens used` **1** / `EXIT=0`.

**The accepted-limitations declaration worked.** This prompt carried all five accepted items WITH
their reasons and an explicit invitation to challenge the reasons. **Not one was re-raised**, and the
reviewer still returned three majors. Second confirmation of the round-2/round-3 result, now at full
list length.

---

## The boundary decides each finding, and it splits them cleanly

RD's rule, applied by me without needing to ask again — which is the point of him having stated the
RULE rather than only the ruling: **INTRODUCED → fix. PRE-EXISTING → bank.** Severity does not
override it.

### MAJOR 3 — the duplicate-flag tolerance. **INTRODUCED BY THIS ARC → IN SCOPE.**

`swing/trades/exit_auto_fill.py:1418`. `git log -S "abs_tol"` names exactly one commit: **`5203caa9`,
this arc's own B-round-1 fix.** The arc introduced `math.isclose(rel_tol=0.0, abs_tol=1e-9)` to close
an exact-float-equality silent miss, and the chosen tolerance has its own.

**B's arithmetic, verified by me rather than accepted:**

| case | residual | `abs_tol=1e-9` result | consequence |
|---|---|---|---|
| `10000000.1 + 0.2` vs `10000000.3` | **1.86e-9** | **False** | a genuine duplicate is offered **CLEAN** — the silent miss Rule 1 forbids |
| `10.0` vs `10.0000000005` | 5.0e-10 | **True** | two distinct quantities **falsely flagged** as one row |

An absolute tolerance against a relative error bounds nothing over an unbounded domain, and neither
`fills.quantity REAL` nor `SchwabExecutionLeg.quantity` imposes a maximum or a quantization. **The
code already admits the second half at `:1392-1404`** — this arc documented the limitation instead of
closing it, and I accepted that in the round-3 adjudication on the ground that "the tolerance is fine;
only its justification is wrong." **That adjudication was mine and it was wrong.** The justification
was wrong AND the tolerance is wrong.

**Fix:** a rel+abs hybrid. Verified: `math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)` returns True on
the large-quantity case, closing the silent-miss half, while `rel_tol` at 1e-9 stays far below any
meaningful share difference. Live reachability is nil today (ledger max 39 shares), which bears on
urgency and not on scope — the arc introduced it, so the arc owns it.

### MAJOR 1 — a sub-half-cent price becomes `0.00`, then violates a CHECK. **PRE-EXISTING → BANK.**

`trade_exit_form.html.j2:139`. A valid execution price below half a cent renders `0.00` through
`%.2f`; the POST comparison at `routes/trades.py:2360` compares ROUNDED values so it reads as
unchanged; persistence then violates `fills.price CHECK(price > 0)`, and the resulting
`sqlite3.IntegrityError` is **not** caught by the `ValueError` handler at `:2680` → 500.

**Pre-existing:** the price input dates to `33e48c00` (`feat(web): exit form VM + GET
/trades/{id}/exit/form`), and **this arc's entire template diff is 7 insertions / 2 deletions**, all
in the advisory clause. Reachability for this operator is effectively nil (a sub-$0.005 fill).

### MAJOR 2 — a candidate the form cannot accept, with no advisory. **PRE-EXISTING → BANK.**

`trade_exit_form.html.j2:143`. Candidate quantity is rendered as the input value without being checked
against `remaining_shares`, while the same control sets `max` to that remaining amount — so a 10-share
candidate on a trade with 4 remaining renders `max="4" value="10"`. The browser blocks submission and
**nothing explains why or offers a recovery.** The resolver filters by ticker, side, execution-bearing
state and recorded ids — never by quantity — and the VM computes remaining only after resolving
(`view_models/trades.py:1185`).

**This is the same CLASS RD just ruled on** — a surface presenting something the operator cannot act
on — which is exactly why it must be banked rather than absorbed: the class is now known, and the
banked item names it. Template untouched by this arc.

### MINOR — `tests/web/test_routes/test_exit_form_auto_fill.py:805`. **IN SCOPE (this arc's own retired wording).**

The section still claims "fallback dedupe" and its fixture injects "recorded under the OLD date
convention" — wording **this arc's production code explicitly retired**. The assertions check only
generic duplicate markers, so the test would stay green if that false operator-facing text were
restored.

---

## THE STOPPING RULE — proposed, because "B returns clean" is not reachable on this file

**Four B rounds have found 3, 2, 3 and 3 majors. The count is not converging, and the composition
explains why:** round 4's majors are *all* pre-existing surface defects or a defect introduced by an
earlier fix in this same arc. **B is a whole-artifact reviewer pointed at a file carrying real
pre-existing debt, so it will keep finding real defects for as long as it is run.** That is the
instrument working correctly, not failing.

**So "merge when B returns an empty verdict" is an unreachable gate on any file with pre-existing
debt, and adopting it would mean this arc never merges — or merges only after absorbing the whole
surface, which is the unbounded-arc failure RD's boundary exists to prevent.**

**Proposed gate, which follows from the boundary already ruled:**

> **B is clean for merge when it returns no unbanked CRITICAL or MAJOR that this arc INTRODUCED.**
> Pre-existing findings are banked — named, with file:line, mechanism, and reachability evidence — not
> fixed, and the banking is what keeps them from being forgotten.

Under that rule this arc needs **one more small pass** (MAJOR 3, which it introduced, plus the MINOR,
which is its own retired wording), after which the two pre-existing majors are banked and the merge
gate is reachable.

**This is a harness-architecture proposal (CHARC's lane) and it changes a merge criterion, so it is
not mine to adopt.** I am stating it because four rounds of evidence now say the current criterion has
no stopping condition on a file like this one.
