# D67 + D69 riders — executing dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Mission:** land two small, witness-free post-merge riders from CHARC's register (`docs/tool-director-context.md`, rows D67 and D69), TDD, one worktree, one Codex `strong` loop to convergence.
**Commissioned by:** the operator, 2026-09-24 ("Fix the remaining 6 items on your list"), orchestrator-dispatched.
**Expected size:** D67 is tests-only, a few lines plus a mechanism note. D69 is one CLI command (`swing trade backfill-intent`) plus its tests.

## 0. Read first

1. `docs/implementer-dispatch-recipe.md`, in full. It is the protocol: worktree, TDD, commits, the WSL-Codex loop and its five per-round assertions, copy-per-round preservation, the return report.
2. `CLAUDE.md`, the gotchas especially: cp1252 (encode crashes, decode lies); the xdist/order flakes; the release-test "full reference graph" gotcha.
3. CHARC's register rows **D67** and **D69** in `docs/tool-director-context.md`. Those rows state the fix; this brief pins the shape.
4. The code cited below. **Re-ground every anchor against the live code before editing: a fact belongs to the CODE, not to this brief.**

**Skill posture:** do not invoke brainstorming or writing-plans; this is a locked-fix executing dispatch. Hand-run the Codex loop per recipe §3 (the copowers Skill may be absent in a sub-agent).

## 1. Worktree and base

- `git worktree add -b d67-d69-riders .worktrees/d67-d69-riders <BASE>` from the MAIN repo, where **`<BASE>` = the main SHA the orchestrator names in the dispatch prompt**. The path `.worktrees/d67-d69-riders` is binding.
- The recipe rules this dispatch relies on (the plan-stage protocol's round-0 intake check, return at every round gate, copy-per-round preservation, the five assertions) are all in the recipe copy at that base.
- **Durable evidence path:** `~/swing-data/review-transcripts/d67-d69-riders/`.
- **No `git stash`, ever.** Leave the worktree intact; the orchestrator merges.

## 2. D67 — the `tests/web/conftest.py` `insert_trade_with_event` wrapper (tests only)

**Premise (orchestrator-reproduced on main `53143892`):**
- `python -m pytest tests/web/test_routes/test_trade_entry_sector_industry_tamper.py -n 0` → **3 failed / 12 passed**, with `wrapped() got an unexpected keyword argument 'attempt_id'`.
- The autouse wrapper at `tests/web/conftest.py` (~:125, `def wrapped(conn, trade, *, event_ts, rationale=None)`) predates 22-A4's `attempt_id` keyword on `swing/data/repos/trades.py:insert_trade_with_event`.
- The file passes inside the full suite run.

**Step 1 — STATE THE MASKING MECHANISM BEFORE THE FIX, as a measured fact, not a guess.** Establish why the full run passes.
- **Hypothesis to TEST, not to adopt:** `swing/trades/entry.py` imports `insert_trade_with_event` BY NAME (`entry.py:~20`). The fixture's `monkeypatch.setattr(trades_repo, ...)` replaces only the module attribute. So whichever test first imports `swing.trades.entry` decides whether `entry.py` binds the real function or the wrapper.
- If the hypothesis holds, the wrapper is silently bypassed in the full run, and its auto-entry-fill never happens for those tests. That would be a second finding. Measure which way it goes and report it; do not fix beyond this brief's scope.
- Write the measured mechanism into the fix commit's message body and a short comment at the wrapper.

**Step 2 — the fix (per the register):**
- The wrapper takes `**kwargs` and forwards them to the real function. It must never hold a second hand-copied roster of keywords.
- It keeps reading only what it needs (`event_ts`) for its own fill write.

**Discriminator:**
- The tamper file at `-n 0` goes **15/15** (red before the fix, green after — run both and record them).
- Also run every test file that uses this conftest's wrapper in isolation (`-n 0`, `tests/web/` scope) and report the counts. The register's method note: a fixture is verified by an ISOLATED run of the files it serves.

**Out of scope:** changing `entry.py`'s import form; repairing the bypass itself, if that is what you find. Report it. The orchestrator routes it to CHARC.

## 3. D69 — `swing trade backfill-intent` (`swing/cli.py`, command at ~:2040)

**The two defects (the register row; three prior sightings, never fixed):**
1. **The per-row header echo (~:2103) prints the RAW `ticker` / `hypothesis_label` / `mistake_tags` without `ascii_safe`.** A non-ASCII value crashes the command with a cp1252 `UnicodeEncodeError` mid-loop, AFTER earlier rows have COMMITTED. The terminal-value branch at ~:2098 already coerces its line whole (Codex R7-2); this line does not.
2. **After a per-row COMMIT (`with conn: update_entry_intent(...)`, ~:2113), output and `conn.close()` in the `finally` are uncontained.** A close that raises after N durable rows exits nonzero on a run whose writes happened.

**The shape (pinned; mirror `trade assign-intent` at ~:1895-2037, the 22-A3 idiom):**
- **(a) ASCII:** every line this command prints that interpolates stored or free text goes through `ascii_safe(...)` WHOLE. That covers the per-row header, the `EntryIntentSeamError` line (~:2118) and the summary. `swing.trades.entry.ascii_safe` is the helper.
- **(b) THE DURABILITY BOUNDARY = "at least one row committed in THIS invocation"** (`n_set > 0`).
  - Re-evaluate it at each handler; never cache it in a separate flag that could drift from the counter.
  - `n_set` is incremented only after the commit returns (~:2123). Verify there is no instruction between the commit returning and the increment that can raise. If there is one, report it: that window is the AL-7 shape, and the declaration is CHARC's to make.
- **(c) Before the boundary, every path is BYTE-UNCHANGED.** Same output, same exceptions, same exit codes.
- **(d) After the boundary:**
  - Output lines go through `_echo_either_sink(ascii_safe(line))` (cli.py ~:1094).
  - A `conn.close()` that raises becomes a `WARN (post-commit): ...` line on the contained sink with `prefer_err=True`. The line names the number of rows durably set. The failure is also recorded through `log_contained`, as `assign-intent` does. The command then exits **0**.
- **(e) D39's template:** if an exception is ALREADY IN FLIGHT when the close raises (a prompt failure, `click.Abort`/Ctrl-C, a `ClickException` from the `ValueError` branch), the ORIGINAL exception propagates. The close error is NAMED/CHAINED, never raised instead of it. This matches RULING R8's shape.
- **(f) Everything else keeps today's behaviour:**
  - `click.Abort` after N rows still aborts.
  - A `ValueError` still becomes a `ClickException`.
  - The idempotent re-run semantics are unchanged.
  - This rider is exactly the register's two items.

**Discriminators** (compute each under the pre-fix AND post-fix code; each must fail pre-fix):
- A seeded trade whose `ticker` (or `hypothesis_label`) carries a non-ASCII glyph, run through a **real cp1252 stdout encoder**:
  - Pre-fix, the header raises `UnicodeEncodeError`; post-fix, it prints the coerced line.
  - `capsys` hides this failure (CLAUDE.md). Use a subprocess, or a `CliRunner` with an explicit cp1252 stream that encodes strictly. State which you used and why it discriminates.
- **`close()` raising AFTER a real commit:**
  - The row is durable, read back on a FRESH connection.
  - The WARN line is present and names the count.
  - The exit code is 0.
- **The same close raise with ZERO rows committed** (every row skipped): the byte-unchanged path, which raises as today.
- **Close raising while `click.Abort` is in flight after one committed row:** the abort propagates, and the close error is named, not substituted.
- Existing `tests/cli/test_backfill_intent_cli.py`, `tests/trades/test_22b_seam.py` and `tests/trades/test_22b_terminal.py` stay green unmodified. If one must change, STOP and report why.

## 4. Round 0 (no Codex) and forks

Before coding, re-derive every premise above against the code at your base.
- If a premise is false, or a design fork appears that this brief does not settle, **STOP and return the packet to the orchestrator** as your final message. List every item at once, each fork with both branches specified.
- Do not encode a guess. The orchestrator routes the rulings (CHARC owns D67/D69's shape).
- If nothing is open, say so in one line and proceed.

## 5. Review

**Suite and Reviewer A:**
- Run the FULL fast suite green BEFORE the review. Then run Reviewer A, the `strong` tier, to `NO_NEW_CRITICAL_MAJOR`, under recipe §3's five assertions, copy-per-round.
- **Review input is the diff PLUS the surrounding reference graph:** the whole `trade_backfill_intent_cmd`, `trade assign-intent`'s handler (the idiom being mirrored), `_echo_either_sink`, `ascii_safe`, `log_contained`, the D67 wrapper, and `insert_trade_with_event`.

**The review prompt carries:**
- **The declared envelope:** single operator, local CLI, a cp1252 Windows console. Tag findings reachable only outside it; never suppress them.
- **The accepted limitations, each with its reason and the challenge invited:**
  - **L1:** the bypass, if Step 1 finds `entry.py`'s by-name import defeats the wrapper in the full run. It is reported, not fixed here: the fix is an import-form or fixture-design change outside a tests-only rider.
  - **L2:** a `backfill-intent` retry cannot duplicate (a re-run skips already-set rows and re-prompts only NULL ones). So the post-boundary exit-0 is a convenience, not a double-write guard. That is why the scope stops at output and close.
- **The two-token verdict requirement.** Describe the tokens; never write either one line-initially in the prompt.

**Round gates:** **STOP and return at each round gate** with the round's ledger row as your final message. The orchestrator fills the depth column and resumes you.

The orchestrator runs Reviewer B, the cold audit, at QA. You do not.

## 6. Done criteria

- D67 commit(s) + D69 commit(s), conventional, trailer-clean (`git log <BASE>..HEAD --format='%H%n%(trailers)'` all empty).
- The full fast suite green on the final head, READ from the tail.
- `ruff check swing/` introduces no new violations.
- Reviewer A converged, with `.copowers-findings.md` restored to the worktree root and the durable copies in place.

## 7. Return report (final chat message; NEVER `role_mail`)

- Per-task commits in order.
- The D67 masking mechanism as measured, and the isolated-run counts.
- The D69 discriminators with their pre-fix and post-fix results.
- The final suite tail.
- The Codex round ledger, each round with model, effort, footer and verdict token, plus the spend line (the summed `tokens used`).
- Every brief condition stated as honored-on-disk (file:line).
- Deviations and flagged-not-fixed items, each with a proposed disposition.

## 8. If you get stuck

Stop and return the state, the blocker and what you tried. A stopped loop is a reportable outcome, never relabelled as convergence.
