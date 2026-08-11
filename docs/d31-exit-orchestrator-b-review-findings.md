# D31-exit — the orchestrator's B review, and the adjudication

**Reviewed tree:** branch `d31-exit` @ `0a84ac82` (27 arc commits + the orchestrator's comment
corrections). **Verdict: `NEW_CRITICAL_MAJOR_FOUND`** — 3 MAJOR, 2 MINOR.
**Transcript:** `.codex-b-review-orch.txt` in the worktree root (1,456,568 bytes).
**Assertions:** banner `gpt-5.6-sol` / `reasoning effort: high` / anchored `^ERROR` **0** /
anchored `^tokens used` **1** / sandbox `read-only`.

**Prompt provenance:** written by the orchestrator from RD's ruling and my own reading of the
tree, at `scratchpad/orch-b-review-prompt.md`. The implementer's offered focus areas were NOT
used — that coupling is what the reassignment removes. Neutral framing on purpose (adversarial
wording trips a provider content filter).

**This is the second consecutive arc-tree where the reassigned B found majors after A converged
clean.** A ran 23 rounds to `NO_NEW_CRITICAL_MAJOR`; B read the finished artifact fresh and
found three. Both instances are delta-blindness: every finding below sits on a line no late
round changed.

---

## MAJOR 1 — the corrected branch keeps an order id that no longer proves anything

`swing/web/routes/trades.py:2448` (the guard at `:2459`).

Top-level `schwab_order_id` is rewritten ONLY when `resolved_fill_origin == "schwab_auto"`. The
`schwab_auto_then_operator_corrected` branch deliberately keeps the form-render default's order
id, and the comment at `:2451-2457` justifies that by enumerating **two** sub-cases — operator
over-rode the default with custom values, or picked a non-default candidate without rebinding
the visible inputs — and concludes *"in both sub-cases the persisted values trace back to the
default's source candidate."*

**There is a reachable third case the enumeration omits:** the operator picks a NON-DEFAULT
candidate by radio AND edits the visible inputs to values matching NEITHER that candidate nor
the default. Origin resolves to `schwab_auto_then_operator_corrected`, so the branch keeps the
DEFAULT's order id — while the persisted values trace back to no candidate at all.

**Why this is a MAJOR and not a comment defect.** On the next render
`view_models/trades.py:1051` reads that order id as PROVEN IDENTITY, which under RD's ruling is
the one and only evidence state permitted to suppress a candidate. Two failures compound:
the default's Schwab order — never recorded — is **silently suppressed**; and the fill that WAS
recorded never enters the anonymous flagging channel, because `order_id_found` is already true.
**A silent exclusion resting on an order id that does not describe the persisted values is
precisely what the 2026-08-11 ruling forbids outright.** The arc encodes that ruling elsewhere
and violates it here.

The false-exhaustive comment is the aggravating factor, not the defect: a reader checking
whether the branch is safe is told the case space is closed when it is not.

## MAJOR 2 — a whitespace order id counts as proof of identity

`swing/web/view_models/trades.py:1051` — `if isinstance(v, str) and v:`.

A whitespace-only `" "` is truthy, so such a row is added to `existing_fill_order_ids`, sets
`order_id_found = True`, and is thereby EXCLUDED from `existing_anonymous_fills`. A recorded
fill that is anonymous in substance is treated as identified: a matching candidate reaches the
operator with no flag, and a candidate carrying the same whitespace id is suppressed outright.

**Reachability, stated honestly.** `SchwabOrderResponse.__post_init__`
(`swing/integrations/schwab/models.py:300`) also checks non-emptiness without `strip()`, so it
would not reject a whitespace id either — but Schwab emitting one is implausible. The realistic
vector is the client-editable auto-fill envelope, which is a **banked, cited-not-fixed item that
this brief explicitly placed out of scope** (§5, carried from item 5). So: real code defect,
low live probability, and the fix is one `.strip()`. I rate it **MAJOR-as-written, minor in
practice** — worth closing because it is the boundary of the ruling's own guarantee, not
because it is likely.

## MAJOR 3 — the flag compares a truncated integer against a fractional ledger value

`swing/trades/exit_auto_fill.py:1043` — `quantity=int(quantity)`.

**The arc already adjudicated this exact class and fixed only one side of the comparison.**
`PossibleDuplicateFill.quantity` is a `float` with an explicit Codex-R16 rationale at
`:199-204`: *"truncating a stored 5.9 to 5 would make it falsely equal a 5-share candidate and
name the wrong row."* That reasoning condemns `:1043` verbatim, and `:1043` still truncates.

The matcher at `:1157-1173` does `quantity = float(candidate.quantity)` — but
`candidate.quantity` was already truncated at construction. So:

- a 10.9-share execution against a recorded 10.9 row → `10.0 != 10.9` → **no flag fires**, the
  silent miss the whole ruling exists to prevent;
- the same execution against a recorded 10.0 row → `10.0 == 10.0` → **a false flag naming the
  wrong row**.

The signature hash is computed from the untruncated 10.9 immediately before the envelope records
10, so the provenance record disagrees with itself.

**Pre-existing vs introduced:** `int(quantity)` is on `main` (`:709` there) and
`ExitAutoFillCandidate.quantity` has always been typed `int`. What this arc introduced is the
float-precise comparison built on top of it. The defect is old; the flag it now breaks is new,
which is what puts it in scope.

## MINOR 1 — a fourth site asserting a guarantee that does not exist

`swing/web/view_models/trades.py:1064` cites `assert_canonical_fill_datetime` as the reason the
first ten characters of `fill_datetime` are its date. The general insert path
(`swing/data/repos/fills.py:17,:149`) never calls that assertion and the column is only
`TEXT NOT NULL`, so a schema-legal `2026-08-04garbage` slices to `2026-08-04` and can falsely
flag. **This is the same class as commit `83c76ec4` ("the last three sites asserting a
`__post_init__` guarantee that does not exist") — a fourth site, found one commit after the
sweep that was supposed to be exhaustive.** The arc separately cites the unwired assertion as
needing a `swing/data` carve-out; the COMMENT, however, is fixable here and now.

## MINOR 2 — a test docstring describing retired behaviour, with assertions that cannot fail for
its stated reason

`tests/web/test_routes/test_exit_post_audit_columns.py:1632` still describes value-tuple
dedupe/fallback and claims a MARKET candidate can originate with `order_id=None`, which the
production Schwab constructor forbids. Its assertions only prove the top-level key is removed —
they would stay green if the VM path then dropped the row or failed to flag it.

---

## Disposition

**MERGE IS BLOCKED.** MAJOR 1 and MAJOR 3 are behaviour-bearing and each defeats, in a reachable
way, the ruling this arc exists to encode. Under the termination rule as the operator refined it
on 2026-08-11, a post-verdict change of major scope re-opens the loop — so these are **not**
mine to patch at the gate, unlike the comment residuals I closed at `0a84ac82`.

**Recommended:** one fix dispatch covering all five findings, A re-run to a single clean verdict
(the first clean verdict now ends the loop), full suite off the final head, then I re-run B on
the fixed tree. MAJOR 3 is the one carrying design weight — moving the candidate quantity to
float touches the dataclass contract, the persisted envelope, the signature input and the form,
so it is not a one-token change and should not be treated as one. MAJOR 1 needs a stated answer
to what the top-level order id MEANS in the corrected branch, not just a widened condition.

**Not recommended: patching MAJOR 2 and the two MINORs at the gate while sending the rest back.**
Splitting one finding set across two pairs of hands is how a fix and its test end up owned by
different people.
