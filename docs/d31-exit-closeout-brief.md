# D31-exit — the closeout pass

**Audience:** a fresh Claude Code implementer, no prior conversation context.
**Phase:** executing (single dispatch). **FIX-ONLY. No schema, no migration, no data correction.**
**Base:** branch `d31-exit` @ `2b869feb` in the EXISTING worktree `.worktrees/d31-exit`. Do NOT create
a new worktree. Do NOT rebase. Suite off that head: **10811 passed / 7 skipped / 0 failed** (verified
by the orchestrator, not carried from a report).

> **This is the LAST pass on this arc.** Four items: one operator-facing text fix and three
> comment/docstring corrections. **Nothing here is a design question, and nothing here is large.** If
> you find yourself scoping something bigger, that is the signal to STOP and report, not to proceed.

---

## §0 Read first

1. **`docs/d31-exit-orchestrator-b-review-round3-findings.md`** — the findings, the adjudication, and
   the banked item at the end. Your primary source.
2. `docs/d31-exit-b-round2-fix-brief.md` — the previous pass; its scope and conventions still bind.
3. `docs/implementer-dispatch-recipe.md` — the protocol.

**Two things are RULED and OUT OF SCOPE. Do not fix them, do not re-argue them, and do not "improve"
them in passing:**

- **The fractional-quantity (≥ 1) misrepresentation** — the `ExitAutoFillCandidate.quantity`
  `int`→`float` migration is **BANKED TWICE by RD**. The hashed/compared/persisted disagreement is a
  knowingly accepted limitation, already recorded in the `_build_candidate` docstring.
- **`SchwabSchemaParityError` escaping the handler at `:699`** — **RD ruled BANK** on 2026-08-12,
  scoped to the class rather than this line, with zero production incidence in 7,795 calls. It is
  recorded in the §0.1 findings doc. **Pre-existing; this arc did not cause it and does not fix it.**

---

## §1 The operator-facing fix — an advisory that instructs an impossible action

`swing/trades/exit_auto_fill.py` around `:1127` (the refusal-reason precedence) and the advisory text
it feeds.

**The defect, and it is not the precedence itself.** Refusal reasons are first-match. For a `FILLED`
order with `quantity=0.9`, a price present and `executions=None`, the reason resolves to
`no_execution_price` alone — so the sub-one-share note never fires, and **the advisory tells the
operator to record the fill by hand while the form's `min="1"` (`trade_exit_form.html.j2:138`)
forbids exactly that.** The test at `tests/trades/test_exit_auto_fill.py:2134` currently pins that
outcome as correct.

The previous implementer flagged first-match and pinned it deliberately, reasoning that reordering
only relocates the incompleteness. **That reasoning is right in general and wrong for this instance:
the defect is an advisory instructing an impossible action, not a question of which reason wins.**

**RD's ruling — the advisory wording is HIS instrument and he strengthened the requirement beyond
what was scoped:** the sub-one-share case **must say what the operator CAN do, not merely what the
framework will not do.** Draft that wording; he reads it at the merge gate.

**So the fix must, at minimum:** ensure the sub-one-share condition is communicated whenever it holds
(reporting all applicable reasons, or suppressing the manual-entry instruction when it holds — your
call, state your reasoning), and replace the impossible instruction with an actionable one.
**Re-point the `:2134` test at the corrected contract**, with the supersession recorded in its
docstring per this project's convention — it currently pins the defect.

## §2 Three comment / docstring corrections

- **`swing/trades/execution_dates.py:211`** — the docstring claims BOTH auto-fill consumers make the
  entered-date fallback "VISIBLE." **False of the ENTRY side today:** it places `entry_date_source`
  in hidden JSON, returns `advisory_text=None`, and its template renders no provenance marker. State
  what is true of each consumer. Do NOT make the entry side visible — that is a different arc.
- **`tests/trades/test_exit_auto_fill.py:861`** — says all-refused results receive a generic advisory
  and reason-specific text is populated-only. **The previous pass changed exactly that**, and the
  assertions (which only look for "execution-grain") now pass under either behaviour. Correct the
  docstring AND make the assertions protect the distinction the implementation actually makes.
- **`tests/trades/test_exit_auto_fill.py:1742`** — the docstring claims the `abs_tol=1e-9` tolerance
  "cannot conflate" distinct quantities, while its discriminator only checks a 1e-4 difference. The
  production comment at `exit_auto_fill.py:1345` was already corrected to stop claiming a bound;
  **this test docstring still makes the claim the production comment retracted.** Correct it to state
  what the test actually discriminates.

## §3 Scope

**In:** `swing/trades/exit_auto_fill.py`, `swing/trades/execution_dates.py` (docstring only), the
exit-form template if and only if §1's wording requires it, and the tests for these.

**Out — flag, never fix:** the two RULED items in §0. Any change to `swing/integrations/schwab/`. The
entry side's provenance rendering. The client-editable envelope. No schema, no migration.

## §4 Conventions and gates

Conventional commits; **no `Co-Authored-By`, no `--no-verify`, no amending**; quoted heredoc with the
last paragraph plain prose. Frozen-clock for any new date-touching test. **Verify every claim against
the code, including this brief's, and report every count with the method that produced it.**

1. Full fast suite **BEFORE** the Codex loop.
2. Codex §3 at the **`strong`** tier, all four per-round assertions including the anchored
   `grep -c '^tokens used'`. **`NO_NEW_CRITICAL_MAJOR` IS THE END.**
3. **DO NOT RUN `codex-auto-review`, and do not offer focus areas for it.**
4. Full fast suite **AFTER** convergence off the final head, plus the trailer audit on the trailer
   **KEY**.
5. Append rounds to the existing `.copowers-findings.md`; leave the scratch at the worktree root.
6. **The WSL Codex invocation needs the PATH prefix `export PATH="$HOME/.local/node22/bin:$PATH"`,
   and it must be in a SCRIPT FILE**, not inline — this harness expands `$VAR` before the command
   reaches WSL, and without the prefix `codex` resolves to a dead npm shim that fails with
   `exec: node: not found` **and exits 0**. Probe `codex --version` (expect `codex-cli 0.147.0`)
   before spending a review. The orchestrator lost a full round to this; do not repeat it.
7. **`tests/integrations/schwab/test_ladder_stress_production_path.py::test_forced_finish_lock_leaves_in_flight_row`
   is a known load-sensitive flake** (`busy_timeout_ms=1` racing a background `BEGIN IMMEDIATE`
   holder thread on a `sleep(0.05)`, no reference to this arc's surface). Confirm the mechanism and
   re-run isolated if it fires; do NOT chase it and do NOT "fix" it.

## §5 Return report

Final chat message. **Do NOT run `scripts/role_mail.py`; do not post to any inbox; never
`--from orchestrator`.**

Include: per-item disposition with file:line as shipped; the §1 wording you drafted and your
reasoning for how you communicated the compound case; commits; test counts off the FINAL head with
the command that produced them; Codex rounds with per-round assertions and the findings path; the
trailer-audit result; and everything flagged-not-fixed.
