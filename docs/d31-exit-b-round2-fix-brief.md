# D31-exit — the B-round-2 fix arc

**Audience:** a fresh Claude Code implementer, no prior conversation context.
**Phase:** executing (single dispatch). **FIX-ONLY. No schema, no migration, no data correction.**
**Base:** branch `d31-exit` @ `0ce45b3c` in the EXISTING worktree `.worktrees/d31-exit`. Do NOT create
a new worktree. Do NOT rebase. Suite off that head: 10805 passed / 7 skipped / 1 known
load-sensitive ladder-lock failure (see §6).

> **ONE of these five is a behaviour change. The other four are comments and a docstring — and they
> are not filler: three of them exist to stop a future reader from "fixing" something that is
> deliberately correct.**

---

## §0 Read first

1. **`docs/d31-exit-orchestrator-b-review-round2-findings.md`** — the findings and my adjudication.
2. **`docs/d31-exit-b-review-fix-brief.md`** — the previous fix arc's brief; its scope and conventions
   still bind you.
3. `docs/implementer-dispatch-recipe.md` — the protocol. The gate list changed on 2026-08-11.
4. `swing/trades/exit_auto_fill.py:431-465` and `swing/web/routes/trades.py:2520-2527` — the ruling
   and the stated semantics as this tree already encodes them.

---

## §1 MAJOR B (the only behaviour change) — a fourth refusal reason, NOT the type migration

**The defect:** a sub-1-share execution takes the trade-detail page down with a `ValueError`.
`int(0.9)` is `0`; `ExitAutoFillCandidate.__post_init__:300` rejects `quantity <= 0`;
`_build_candidate`'s three refusal reasons (`no_execution_price`, `no_quantity`, `no_usable_date`) do
not catch a cleanly-resolved `0.9`; the build loop at `:775` has no `try/except`; and the caller at
`view_models/trades.py:1131` wraps the call in `try/FINALLY`, not `try/except`. So it propagates to
the route. Fractional quantities are permitted by `fills.quantity REAL` (migration 0014) and by the
Schwab model — **this is not schema-prevented.**

**RD's ruling (he REVERSED his earlier banking on this information):** the remedy is a **FOURTH
REFUSAL REASON**. A quantity that cannot be represented as an `int > 0` candidate is REFUSED by
`_build_candidate` with its own stated reason, and the surface renders it as not-offerable.
**Visible degradation instead of a crash** — the same standard as every other ruling on this surface.
The operator records such a fill by hand rather than losing the page.

**The dataclass `int`→`float` migration REMAINS BANKED** — do not start it. **But name the
sub-1-share limitation IN the banked item** (the `_build_candidate` docstring note that records the
banking) so the next scoping sees the whole cost rather than rediscovering it.

**Wire the reason into the ANNOUNCEMENT, not just the refusal.** The loop at `:774-796` accumulates
`omitted[outcome]` and the surface announces omissions by reason. A new reason that reaches that dict
but not the operator-facing text is a silent omission wearing a counter — the exact class this arc
built that mechanism to prevent. Verify the rendered text names it, and say in your report how you
verified it.

**Tests:** a sub-1-share execution (a) must NOT raise, (b) must be announced as omitted with the new
reason, and (c) must not suppress the OTHER candidates in the same response. A test asserting only
"no exception" is non-discriminating against a fix that swallows it silently.

## §2 MAJOR A — comment-scope ONLY, and the comment exists to prevent a "fix"

**Do not change behaviour here. The finding is real and the remedy was REJECTED by RD after a live
query, which I reproduced independently:** 11 non-entry fills carry an envelope; exactly one row's
current values no longer derive from its named candidate — **fill 40, order `1007444179553`, current
`('2026-08-04', 18.4, 10.0)` vs candidate `('2026-08-03', 18.4, 10)`.** That is FTRE's exit fill, the
row this whole D31 programme was built around, and **its id is CORRECT**: the operator hand-corrected
the exit date toward the truth. A read-path re-derivation would demote it to anonymous and re-offer
its order — the double-record the ruling exists to prevent.

**RD's CORRECTED semantics — he is correcting his own earlier wording, which described a TEST as if
it were an INVARIANT:**

> A top-level `schwab_order_id` asserts a HISTORICAL FACT: at recording time the operator linked this
> row to that broker order. **Value-derivation was the EVIDENCE that established the link; it is not a
> property the row must preserve.** A later correction moves the row toward being a MORE accurate
> record of the SAME order — it does not unmake the link. **The id names WHICH order; the values
> describe HOW it executed. Drift between them is a data-quality question, never an identity question.**

**Two comments to write:**

1. **At the read path (`swing/web/view_models/trades.py:1057`)** — state that the id is a historical
   link and is deliberately NOT re-derived against current values, and **name fill 40 as the concrete
   reason**. The hazard this comment closes is a future reader — or a future review round — seeing the
   drift and "fixing" it into the re-derivation.
2. **At the stated semantics (`swing/web/routes/trades.py:2520-2527`)** — **this is mine, not RD's,
   and it is the load-bearing half.** The site currently states what an id asserts in terms of values
   deriving from the candidate. That is the test AT POST, where the question is link-versus-residue.
   As written it reads as a permanent invariant, and **a reader who believes that is exactly the
   reader who adds the re-derivation the ruling forbids.** Refine it to distinguish the establishing
   test from the historical assertion. Do not weaken the POST-time rule itself — the code is correct.

**Standing constraint (CLAUDE.md #31):** a comment may describe what the code does TODAY. It may NOT
promise what a future arc will do to it.

## §3 MINOR C — a tolerance defended by a grain nothing enforces

`swing/trades/exit_auto_fill.py:1217`. The `abs_tol=1e-9` comment justifies itself as "five orders of
magnitude below the smallest meaningful share difference," asserting a 1e-4 quantity grain that no
Schwab model, schema or writer enforces. **The tolerance is fine; the justification is a claim the
code does not support.** Correct it to state what the tolerance is actually for — absorbing
floating-point summation error across execution legs — rather than appealing to a grain that does not
exist.

## §4 MINOR D — a test docstring that contradicts its own assertions

`tests/trades/test_exit_auto_fill.py:1835`. The docstring OPENS by saying the same-session alarm must
NOT fire and describes an unflagged result; the test's name, its later paragraph and its assertions
all require the candidate to be FLAGGED. The assertions pin the correct behaviour, so the test is not
vacuous — but a reader reconciling the contradiction in the wrong direction restores exactly the
behaviour the rewrite rejected. Correct the opening to match what the test actually pins.

## §5 Scope

**In:** `swing/trades/exit_auto_fill.py`, `swing/web/routes/trades.py`,
`swing/web/view_models/trades.py`, the exit-form template if and only if the §1 announcement requires
it, and the tests for these. The `swing/trades/` carve-out carries.

**Out — flag, never fix:** no schema, no migration, no data correction. The
`ExitAutoFillCandidate.quantity` type migration (§1). Any read-path or writer-side re-derivation or
id-drop (§2 — **explicitly ruled out; adding one is the failure this arc is preventing**). The
client-editable envelope. `swing/integrations/schwab/models.py`. The entry side.

## §6 Conventions and gates

Conventional commits; **no `Co-Authored-By`, no `--no-verify`, no amending**; quoted heredoc for
multi-line messages with the last paragraph plain prose. Frozen-clock for any new date-touching test.
**Verify every claim against the code, including this brief's, and report every count with the method
that produced it.**

1. Full fast suite **BEFORE** the Codex loop.
2. Codex §3 at the **`strong`** tier, all four per-round assertions including the anchored
   `grep -c '^tokens used'`. **`NO_NEW_CRITICAL_MAJOR` IS THE END** — the loop terminates at the FIRST
   clean verdict; post-convergence minors are corrected without another round and verified by the
   suite; only a post-verdict change of critical/major SCOPE re-opens it.
3. **DO NOT RUN `codex-auto-review`, and do not offer focus areas for it.** That second eye is the
   orchestrator's, who writes his own prompt.
4. Full fast suite **AFTER** convergence off the final head, plus the trailer audit on the trailer
   **KEY**.
5. Append your rounds to the existing `.copowers-findings.md`; leave the scratch at the worktree root.
6. **`tests/integrations/schwab/test_ladder_stress_production_path.py::test_forced_finish_lock_leaves_in_flight_row`
   is a known load-sensitive flake** — `busy_timeout_ms=1` racing a background `BEGIN IMMEDIATE`
   holder thread on a `sleep(0.05)`, with no reference to any surface this arc touches. If it fails,
   confirm the mechanism and re-run it isolated; do NOT chase it as a regression and do NOT "fix" it.

## §7 Return report

Final chat message. **Do NOT run `scripts/role_mail.py`; do not post to any inbox; never
`--from orchestrator`.**

Include: per-finding disposition with file:line as shipped; how you verified the §1 announcement
reaches the operator-facing text; commits; test counts off the FINAL head with the command that
produced them; Codex rounds with per-round assertions and the findings path; the trailer-audit
result; and everything flagged-not-fixed.
