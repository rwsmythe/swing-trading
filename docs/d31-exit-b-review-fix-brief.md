# D31-exit — the B-review fix arc

**Audience:** a fresh Claude Code implementer, no prior conversation context.
**Phase:** executing (single dispatch). **FIX-ONLY. No schema, no migration, no data correction.**
**Base:** branch `d31-exit` @ `0a84ac82` in the EXISTING worktree `.worktrees/d31-exit` — do NOT
create a new worktree and do NOT rebase. Suite off that head: **10800 / 7 / 0**, ruff clean.

> **You are fixing five findings from a review you did not run.** The arc converged its own A-loop
> at R23; the orchestrator's independent B review then found three MAJOR and two MINOR on the same
> tree. Every finding sits on a line no late round changed — that is the point, and it is not a
> criticism of the arc.

---

## §0 Read first

1. **`docs/d31-exit-orchestrator-b-review-findings.md`** — the findings with reachability and
   file:line, and the adjudication. This is your primary source.
2. **`docs/d31-exit-side-followon-brief.md`** — the original arc brief. Its §5 scope and §6
   conventions still bind you.
3. `docs/implementer-dispatch-recipe.md` — the protocol. **§3 and the gate list changed on
   2026-08-11; read them, do not run from memory.** Two changes bite you directly: see §4 below.
4. `swing/trades/exit_auto_fill.py:431-465` — the ruling as this module already encodes it. Every
   fix below serves that text.

---

## §1 MAJOR 1 — the corrected branch keeps an order id that proves nothing

**`swing/web/routes/trades.py:2448`**, guard at `:2459`.

The `schwab_auto_then_operator_corrected` branch keeps the form-render default's top-level
`schwab_order_id`. Its comment at `:2451-2457` enumerates two sub-cases and concludes *"in both
sub-cases the persisted values trace back to the default's source candidate."* **A third case
reaches that branch:** the operator picks a NON-DEFAULT candidate by radio AND edits the visible
inputs to values matching neither that candidate nor the default. The retained id then describes no
persisted value, and `swing/web/view_models/trades.py:1051` reads it on the next render as PROVEN
IDENTITY — silently suppressing the never-recorded default order while the fill that WAS recorded
never enters the flag channel.

**RD ruled the semantics; encode them. This is his text, not a paraphrase:**

> A top-level `schwab_order_id` on a fill row asserts: the operator affirmatively LINKED this row to
> that broker order — by selecting it, or by accepting its unedited render. An id that arrived as
> display default and survived edits pointing elsewhere is residue, not a link. Any path where the
> persisted values cease to derive from the id's own candidate DROPS the id — the row becomes
> anonymous-in-substance and enters the flag channel, which is built for exactly this evidence state.

**The evidence hierarchy is VALUES→ORDER, never TOKEN→ORDER.** Dropping the id is not data loss:
the envelope's `selected_candidate_order_id` already preserves what the operator picked, and the
flag channel alarms rather than asserts. The row degrades to the honest evidence state instead of
carrying a counterfeit proof.

**A WIDENED CONDITION IS NOT AN ACCEPTABLE FIX.** RD was explicit: the false-exhaustive comment is
what let this survive 23 rounds, and a widened condition without a stated meaning is the same
comment one case longer, waiting for a fourth case. State the rule where the code enforces it.

**Test:** discriminating, at the route level — non-default radio + edits matching neither candidate
— asserting the id is DROPPED and (in a second assertion or a companion test) that the row
consequently reaches the flag channel on the next render. A test that only asserts the branch
condition widened would pass under a fix that still leaves a fourth case.

## §2 MAJOR 2 — a whitespace order id is accepted as proof

**`swing/web/view_models/trades.py:1051`** — `if isinstance(v, str) and v:` admits `" "`.

Such a row leaves `existing_anonymous_fills` and is treated as identified: a matching candidate
reaches the operator unflagged, and a candidate carrying the same whitespace id is suppressed.

**RD ruled CLOSE, not cite,** and his reason is the load-bearing part: this is not adjacent to the
provenance rule, it **is** that rule's boundary condition failing. The rule reduces to "silent
exclusion requires PROOF"; a whitespace token is not proof of anything. Leaving it cited would
enforce the ruling everywhere except at its own definition of proof.

Fix the truthiness check to require a non-blank id. **Flag, do not fix:**
`swing/integrations/schwab/models.py:300` is no stricter (non-empty, not stripped) — note it in the
return report as a symmetric gap; hardening Schwab's constructor is out of scope here.

## §3 MAJOR 3 — the flag compares a truncated int against a fractional ledger value

**`swing/trades/exit_auto_fill.py:1043`** — `quantity=int(quantity)`.

`PossibleDuplicateFill.quantity` is a `float` by this arc's own R16 fix, whose comment reads:
*"truncating a stored 5.9 to 5 would make it falsely equal a 5-share candidate and name the wrong
row."* That reasoning condemns `:1043`. The matcher at `:1157` does `float(candidate.quantity)` —
already truncated. So a 10.9-share execution **fails to flag** against a recorded 10.9, and
**falsely flags** a recorded 10.0.

**SCOPE, RULED BY RD AND NARROWER THAN IT LOOKS. Read this before you design.**

- **IN SCOPE:** the duplicate-flag COMPARISON consumes the UNTRUNCATED quantity on both sides.
- **BANKED, NOT YOURS:** the dataclass-wide `ExitAutoFillCandidate.quantity` `int`→`float`
  migration, with its envelope, signature and form implications. Do not start it.

**The untruncated value is already reachable without any contract change** — verified by the
orchestrator, not assumed: `_undecidable_duplicates(order, candidate, anonymous_fills)` at `:1103`
**receives the raw order**, and `_resolve_match_quantity` is the same helper `_build_candidate` uses
at `:1025`. So the comparison can source the exact quantity from the order it already holds.

**One live hazard, and it is why this is posed rather than prescribed:** the comment at `:748-754`
warns against re-invoking `_resolve_match_quantity` against the raw order for the CHOSEN candidate's
values, because it can return `None` for partial-then-canceled MARKET orders. That warning is about
a different consumer, but it is real. **Decide the mechanism — re-invoke with a documented fallback,
or thread the exact value through — and report the reasoning and the alternative you rejected.** If
you conclude the narrow fix is genuinely impossible without the type change, **STOP and report**
rather than growing the arc.

**Severity context, from RD's live query — 43 fills, ZERO fractional quantities.** Even unfixed the
blind spot has no live population today. That is context for urgency, not a reason to defer an
in-scope fix, and it means your test must PLANT a fractional quantity rather than look for one.

**Test:** both directions. A recorded fractional row that must flag and currently does not; a
recorded whole-number row that must NOT flag and currently does. A test asserting only the first is
non-discriminating against a fix that rounds instead of preserving.

## §4 The two minors

- **`swing/web/view_models/trades.py:1064`** — the comment cites `assert_canonical_fill_datetime` as
  the guarantee that `[:10]` yields the date, but the general insert path
  (`swing/data/repos/fills.py:17,:149`) never calls it and the column is only `TEXT NOT NULL`.
  **Correct the comment to state what is actually true.** The unwired assertion itself stays CITED
  for the `swing/data` carve-out arc — not yours. This is the FOURTH site of the class `83c76ec4`
  swept as "the last three," so state in your return report the METHOD by which you satisfied
  yourself there is no fifth.
- **`tests/web/test_routes/test_exit_post_audit_columns.py:1632`** — the docstring describes retired
  value-tuple dedupe and claims a MARKET candidate can originate with `order_id=None`, which the
  production Schwab constructor forbids. Its assertions cannot fail for the reason the docstring
  gives. Correct the docstring AND make the assertions discriminating, or delete the false claim and
  say which you did.

---

## §5 Scope

**In:** `swing/trades/exit_auto_fill.py`, `swing/web/routes/trades.py`,
`swing/web/view_models/trades.py`, and the tests for all three. The `swing/trades/` carve-out from
the original brief carries.

**Out — flag, never fix:** no schema, no migration, no data correction. The
`ExitAutoFillCandidate.quantity` type migration (§3). `swing/integrations/schwab/models.py` (§2).
The unwired `assert_canonical_fill_datetime` (§4). The client-editable auto-fill envelope. The
entry side.

## §6 Conventions

Conventional commits; **no `Co-Authored-By`, no `--no-verify`, no amending**; quoted heredoc
(`<<'EOF'`) for multi-line messages and **keep the last paragraph plain prose** — a `Word:` opener
parses as a git trailer. Frozen-clock for any new date-touching test. **Verify every claim against
the code, including this brief's, and report every count with the method that produced it.**

## §7 Gates — two of these changed on 2026-08-11, read them

1. Full fast suite **BEFORE** the Codex loop.
2. Codex §3 at the **`strong`** tier, all four per-round assertions including the anchored
   `grep -c '^tokens used'`. **`NO_NEW_CRITICAL_MAJOR` IS THE END — the loop terminates at the FIRST
   clean verdict.** Post-convergence MINORS are corrected WITHOUT another round and verified by the
   suite; only a post-verdict change of critical/major SCOPE re-opens the loop. Do not run rounds
   hunting wording.
3. **DO NOT RUN `codex-auto-review`.** The B review moved to the orchestrator (operator ruling,
   `harness-architecture.md` §5.1). Running it yourself is the coupling the ruling removes.
   **Do not offer suggested focus areas for it either** — the orchestrator writes his own prompt.
4. Full fast suite **AFTER** convergence, off the final head. Trailer audit filtered on the trailer
   **KEY**.
5. Leave the review scratch (`.codex-*`, `.copowers-findings.md`) at the worktree root — QA reads it
   there. Append your rounds to the existing findings file rather than replacing it.

## §8 Return report

Final chat message. **Do NOT run `scripts/role_mail.py`; do not post to any inbox; never
`--from orchestrator`.**

Include: per-finding disposition with file:line as shipped; your §3 mechanism decision with the
alternative you rejected; the §4 fifth-site method; commits; test counts off the FINAL head with the
command that produced them; Codex rounds with per-round assertions and the findings path; the
trailer-audit result; and everything flagged-not-fixed.
