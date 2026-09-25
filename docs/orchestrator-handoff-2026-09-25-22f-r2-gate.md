# Orchestrator handoff — 2026-09-25 — 22-F EXECUTING at the Reviewer A Round 2 gate; the R2 packet is with CHARC

**Supersedes:** `orchestrator-handoff-2026-09-25-22f-plan-submitted.md`.
**From:** the generation bootstrapped 2026-09-25 ~14:45Z (Opus 5.5). It rolled at ~362K self-read, on a clean boundary: the R2 gate was recorded and the packet posted. The operator was told the rollover would happen at this boundary.

**No cell is in flight.** Cells 1-9 have all returned. `cell_depth --live` still lists recently returned cells for a while. **Re-derive every fact below.**

## 1. STATE

- **`main` @ `704ac133`** (my handoff commit sits on top of it). It is NOT pushed; the push is the operator's.
  - `8bfca5a4` is the 22-F plan-accepted `--no-ff` merge.
  - `704ac133` is CHARC's brief section-1 amendment.
- **Schema v41 LIVE.** 22-F has no schema change.
- **Worktrees:**
  - `.worktrees/22-f-exec` (branch `22-f-exec` @ `e6b71243`): ACTIVE, clean, trailer audit empty over `704ac133..HEAD`.
  - `.worktrees/22-f-plan` (branch `22-f-plan` @ `846919c6`): merged. Remove the worktree when convenient and KEEP the branch, because the ledgers cite it.
  - `.worktrees/22-i-exec` was removed this generation; its branch is kept.
- **Directors:** CHARC `swing-charc-20260924-1903`; RD `swing-rd-20260924-2100`. Trust the `ping ->` line.

## 2. IN FLIGHT, owner = you: 22-F EXECUTING

- **The executing ledger is the record:** `docs/superpowers/plans/2026-09-25-phase22-arc-f-handler-escape-sweep.exec-ledger.md` on `22-f-exec`, about 150KB. READ BY SECTION.
  - "Reviewer A round table" to the end: R1, my R1 gate, CHARC's R1 ruling, the consolidated R1 authorization, the R1 fixes, R2, and my R2 gate.
  - "STOPS / Rulings relayed": every director ruling of this arc, block-quoted. RD STOP-1; CHARC D-10, STOP-2, STOP-3 (supersedes STOP-2 item 4), STOP-4, STOP-5, and the R1 gate.
- **Dispatch prompts** are in `~/swing-data/review-transcripts/22-f-exec/`: `dispatch-prompt-exec.md` is the standing orders; `-c2` .. `-c9` are the continuations, and each cites the one before. Codex evidence is in `r1/` and `r2/`. RED outputs are in `red/`.
- **Where it stands:**
  - Every plan task is DONE: A1-A8, B1-B4, C1-C2, D0-D5, E1-E2, F1-F11, G0-G3 (40 converted / 18 declared per STOP-5), and H1.
  - T-Z1 passed, with its output verbatim in the ledger.
  - The pre-R2 suite at `5490a266` was 15269 passed / 13 skipped / 0 failed, with the worktree RESOLVER and ruff clean.
  - **R1:** 9 major and 2 minor. Fixed as ruled.
  - **R2:** 0 critical, 9 major, 1 minor, all NEW; 4 are residuals of the R1 fixes. Nothing from R2 is fixed yet.
  - Spend so far is 1,371,046 Codex tokens.
- **Waiting on:** CHARC's reply to my R2 packet (mail `20260925T215936Z`). It covers:
  1. R2-01/R2-08(b): the C2-21 "runner-wide" scope;
  2. R2-02/03/05: one class ruling on an interrupt at a cleanup statement;
  3. R2-04: declare the race vs `wrote: bool`;
  4. R2-07: name the failed run vs declare it.
- **Next:**
  1. Drain. Block-quote CHARC's R2 ruling into the exec ledger. Post the path back.
  2. Dispatch a FRESH fix cell: `implementer-opus-high`, as all nine cells were, per plan section 0.5. Model its prompt on `dispatch-prompt-exec-c9.md`: tell it to read only the ledger's round-table-to-end section and Suite gates. Its work is:
     - R2-06, which I authorized at my gate;
     - CHARC's R2 items as ruled;
     - then a DEDICATED UNCOUNTED SELF-SWEEP over the R1+R2 fix diffs for two classes: interrupts at cleanup statements, and `durable` bound other than from a writer's report. Use SS-N ids;
     - then ONE confirming **Round 3**, returning at its gate.
     **A fourth counted round needs your WRITTEN authorization naming the task-bearing finding** (recipe; the ROUND-5 check-in also binds).
  3. On convergence: G3 (the full fast suite on the final head) in the cell. Then **Reviewer B is YOURS**: a cold audit, CLAIMS_FIRST, DEFAULT TO INTRODUCED. It checks every proxy test's patch target against the name the code resolves at call time (the did-it-fire class recurred several times). Then the return report to the directors, then CHARC's code-only merge gate (NO witness rung, brief section 2.11), then `--no-ff` (ledgers cite branch SHAs), then the merged-head suite.
- **CHARC's merge-gate items, already named:**
  - T-Z1's four checks;
  - the census line-pin test `tests/metrics/test_22b_r1_3_surfaces_census.py`, which MUST be re-measured on the MERGED `cli.py`. It re-pinned twice in this arc and caused the 22-I merge conflict;
  - the non-plain `durable` bindings;
  - `append_close_notice`;
  - the non-constructible controls;
  - D-16, B-04, T-F9, C2-12, D-13, D-14;
  - the A-4 `adjust_stop` bool amendment.
  - **These go to CHARC with the return report.**
- **Banked, order-dependent reds** (CHARC's register; not 22-F's to fix):
  - `test_setup_auth_failure_audit_status_and_sentinel_redaction` fails in isolation on the base.
  - `test_a2_94_...[moved]` goes red under xdist load.
  - At G3 and the merged head, reproduce either one with `-n 0` FIRST. Never wave it through on the strength of the register row.

## 3. DONE THIS GENERATION

- 22-F plan ACCEPTED: RD item 2 (`c4f4b8b1`), CHARC item 1 (`846919c6`). Merged to main at `8bfca5a4`.
- 22-F executing dispatched under `d4f2cbed`. It ran through nine cells. Every cell ended at or near the 400K cap; the arc is large. Each stop was routed, and every ruling was block-quoted in the ledger.
- Tip-only, MESSAGE-ONLY rewrites of two parsed-trailer commits: `0ab81214`→`fe7ee87f` and `13cf8b03`→`17baa97f`, both with an empty tree diff. A wrong SHA in the subject of ledger commit `ba49e13a` (T-B3 cited as `c3c93597`; the real commit is `29b3683a`) is RECORDED, not rewritten.

## 4. AUTHORITIES (a grant is STATE)

- **Operator via CHARC `d4f2cbed`** ("Perform the resequencing and kick off the work"). It covers 22-F's executing cells and gates. It is NOT spent until the 22-F merge.
- **CHARC amendments granted in this arc** (all in the ledger):
  - STOP-2/3: the retype at `risk_policy.py:139-141`;
  - STOP-5: the sharpened DECLARED-ROOT test;
  - R1 gate: A-4, `swing/trades/stop_adjust.py`, bounded to `adjust_stop` returning `bool`.
  - R1-07's amendment was DECLINED.
- **My written authorizations, recorded in the ledger:**
  - R1 gate (`d1f967d5`): FIX R1-02/03/06/09/11; REJECT R1-04; BANK R1-10. Consolidated with CHARC's ruling at `9f8855ed`. SPENT.
  - R2 gate (`e6b71243`): FIX R2-06; REJECT R2-08(a) and R2-09; R2-10 not authorized. UNSPENT; it goes to the next cell.
  - The Part-E-before-T-D5 order deviation. SPENT.
- **No fourth counted round is authorized.**

## 5. WHAT WILL BITE YOU

- **Cells hit the cap after only a handful of tasks.** Continuation prompts must name ledger SECTIONS to read and forbid whole-file reads. The ledger is ~150KB and a Codex transcript is 2MB+.
- **Parsed trailers recurred twice** despite the prompt forbidding them. The cell stops on its own now; fix with a message-only amend at the tip and record it.
- **A cell once committed the ledger EMPTY** (`e76969e1`, restored at `54a810d1`). Every ledger write goes through a temp file with a `wc -c` check.
- **A standing invariant test in `tests/web`** (`test_live_opens_routed.py`) caught a `cli.py` change. Every commit group runs tests/cli + tests/web in FULL.
- **A ruling's discriminator can be written from the case in view** (STOP-3 superseding STOP-2 item 4). Measure against the code's states before encoding it.
- **When a Python heredoc writes a ledger through `write_text`, check the diff stat** before trusting a byte count.

## 6. QUEUED (orchestrator's), not started

- Re-anchor the census test on call TEXT, not line numbers.
- `probe_22i_guard_census.py`'s `#SUMMARY` INFO=140 vs 142.
- RD 1(iii): the exit POST re-render's anchor.
- The D67 L1 follow-on rider: read the grant's scope first.
- The two banked order-dependent tests (CHARC's register; the D67 method note).
