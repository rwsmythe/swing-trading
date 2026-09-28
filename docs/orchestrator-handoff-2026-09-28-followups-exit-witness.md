# Orchestrator handoff -- 2026-09-28 -- 22-F merged; follow-ups done; exit re-render fix awaiting the operator's browser witness

**Supersedes:** `orchestrator-handoff-2026-09-26-22f-cell16-queued.md`.
**From:** the generation bootstrapped 2026-09-26 (session `808f802f`, Opus 5.5). It rolled at ~423K self-read on a clean boundary.
**No cell is in flight.** Every cell has returned and been QA'd. **Re-derive every fact below.**

## 1. STATE

- **`main` @ this handoff's commit**, on `4e412db9`. It is NOT pushed; the push is the operator's.
  - Merged this generation:
    - **22-F** (`58368c86`, `--no-ff`; merged-head 15328/13/0);
    - the **follow-up riders R-1..R-4** (`4e412db9`, fast-forward; merged-head 15347/13/0).
  - Plus the context update `dcb39030` and the briefs and recipe addition `eefbde21`.
- **Schema v41 LIVE, unchanged.** Nothing this generation touched the schema.
- **Worktrees:** ONE. `.worktrees/exit-rerender-anchor`, branch `exit-rerender-anchor` @ `551fa05a`, clean.
  - The 22-F worktrees are removed.
  - Branches `22-f-exec` and `22-f-plan` are KEPT, because the ledgers cite them.
  - Branch `followups-riders` is deleted: it was merged by fast-forward and nothing cited it.
- **Directors:** CHARC `swing-charc-20260925-1726` (the successor seat; its predecessor rolled at 605K); RD `swing-rd-20260924-2100`. Trust the `ping ->` line.

## 2. IN FLIGHT, owner = you: the exit re-render anchor fix (RD 1(iii) / 22-F AL-6)

- **The record:** `docs/superpowers/plans/2026-09-28-exit-rerender-anchor.ledger.md` on the branch. It holds, in order: the round-0 summary; my rulings (d2-strict, a2 by hash under the gate, b2, c2, typed values in scope with typed shares kept); the executing cell's section; and my QA (depth 307,264; R1 valid and clean at `strong`, 178,835 tokens).
- **Brief:** `docs/exit-rerender-anchor-brief.md`. Evidence: `~/swing-data/review-transcripts/exit-rerender-anchor/`.
- **What it fixes:**
  - a refused exit POST (shares > remaining, price 0, and so on) re-rendered a FRESH form. It lost every typed value, and the reason `<select>` fell back to `stop-hit`, so a corrected resubmit recorded `action='stop'` with a wrong date;
  - it re-derived the Schwab anchor instead of carrying the submitted one.
  - Now the typed values are kept on both re-render paths, and the submitted anchor is restored only when the fresh Schwab list is proven unchanged.
- **NEXT, in order:**
  1. **The OPERATOR-WITNESSED BROWSER CHECK (binding for HTMX form work).** Run it STEP BY STEP: one step, wait for his result, then the next (memory `feedback_witness_step_by_step`).
     - Start the worktree's code with `$env:PYTHONPATH="."; python -m swing.cli web --port <free port>` from `.worktrees/exit-rerender-anchor`. The editable install would serve MAIN, not the branch.
     - Verify the port is free first. Stop the server and VERIFY it is gone at teardown (memory `feedback_taskstop_does_not_kill_detached_server`).
     - **The book is flat** (no open trade), so the witness needs a trade to exit. Plan that WITH the operator: a seeded copy of the DB via a `cfg` that points at a scratch DB, never the live DB. Decide it with him; do not improvise.
     - Surfaces to witness:
       - a refused exit (shares > remaining) shows the typed date, price, shares, notes AND the chosen reason still selected;
       - a corrected resubmit records the chosen reason, not `stop`;
       - where Schwab candidates exist, the pick survives.
  2. Merge `git merge --no-ff exit-rerender-anchor`. **Never rebase:** the ledger cites branch SHAs, and two commits below the tip carry a parsed `GREEN:` trailer, recorded in the ledger, not rewritten. Check `git log -1 --format='%(trailers)'` = `[]` on the merge commit.
  3. Run the merged-head fast suite and READ it. **If `tests/data/test_migration_0039_provenance_corrections_tier2.py::test_uncovered_barrier_absent_terminal_is_accepted_both_shapes[...before_barrier-4]` reds, reproduce it `-n 0` FIRST.** It flaked once on the branch's first post-Codex run, its mechanism is NOT established, and it is NOT a banked red.
  4. Post the result to the directors. Remove the worktree only after reconciling its gitignored dotfiles against the evidence directory (see section 4).

## 3. AUTHORITIES (a grant is STATE)

- **Operator, 2026-09-28, verbatim:** "perform the followups and the cell_depth --live chabnge". This covers the orchestrator queue as it stood: the recipe TestClient entry, R-1..R-4, and the exit re-render item THROUGH its merge after the browser witness. It does NOT cover the double-record fix below.
- **Operator grant `d4f2cbed`:** SPENT at the 22-F merge.
- **My written rulings:** the exit round-0 rulings in the branch ledger. RD said "CC there; no dissent -- d2-strict keeps the fetch, which is the conservative reading".

## 4. OPEN / OWED

- **OPERATOR DECISION PENDING: the exit DOUBLE-RECORD defect.**
  - The exit POST has no duplicate-order check: a two-tab or back-and-resubmit replay recorded Schwab order o2 twice (measured in round 0; `record_exit` has no guard, by read).
  - **RD's position** (`comms/orchestrator/read/20260928T163958Z-rd-rd-position-exit-double-record-zero-live.md`):
    - ZERO live incidence (33 order ids on 33 fills; CHARC's query agrees).
    - The identity semantics are stated: an exact replay (order id + signature) is REFUSED; the same order with a different signature is FLAGGED and needs operator confirmation; anonymous matches are FLAGGED only.
    - Verify first whether one order can arrive as two candidates over time.
    - The guard lands in `swing/trades`, so it is a CHARC carve-out.
    - Timing: after the pause (~10-03..10-20) and before the first live exit.
  - The operator was asked whether to commission it now for post-pause or decide near 10-20. **No answer yet.**
  - RD's position is NOT yet transcribed into the exit ledger. It belongs in the double-record arc's record when commissioned, and it is not part of the anchor fix.
- **Recipe addition landed** (`eefbde21`, section 5): an interrupt under TestClient hangs the run.
- **Queued, unowned by me:** CHARC's register items from the 22-F rulings (the D39 facets, including B2-01's `:2944`; the S-D39 template question); RD's October-read caveat on the exit-reason mix.
- **Process slip, owned:** at the riders teardown I removed the worktree BEFORE reconciling its three gitignored dotfiles (`.codex-diff.txt`, `.codex-prompt-r1.md`, `.copowers-findings.md`). The evidence directory held complete copies, so nothing was lost. **Reconcile first.** The exit worktree has the same kind of dotfiles at its root.

## 5. WHAT WILL BITE YOU

- **`cell_depth --live` now lists PARKED cells** (flag `parked`): a cell whose parent session is live is listed at any age. The rollover precondition asks for a cell "still being written to"; a `parked` row is resumable, not written-to. Read the age column.
- **Every ledger or doc write** goes through a temp file with `wc -c` and `git diff --stat`. A Python heredoc in Git Bash collapsed `\\` in a Windows path, which mangled one line; build backslashes with `chr(92)`.
- **Do not write into a worktree while its cell is working.**
- **`role_mail` subjects cap at 80 characters.** Post from the MAIN repo cwd, and verify delivery on disk.
