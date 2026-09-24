# Orchestrator handoff — 2026-09-24 — 22-I plan COMMITTED and awaiting director acceptance; the D67+D69 rider stopped mid-loop

**Supersedes** `orchestrator-handoff-2026-09-24-22b-closed.md`.
**From:** the generation bootstrapped 2026-09-24 ~17:00Z (session `f4bae27a`, Opus 5.5, build 2.1.280). **Rolled at:** ~393K self-read (`cell_depth.py --sessions --live 1`), under the 400K trigger. It rolled by the MIRROR rule: the next packets (the rider's round 3 plus Reviewer B, and the 22-I acceptance QA) do not fit in what remains.
**No cell is in flight.** The D67+D69 cell was STOPPED by this seat (TaskStop) at 422K; see section 2. **Re-derive every fact below.**

## 1. STATE

- **`main` @ `b09bbc02`** plus directors' docs commits since then. **239 ahead of `origin/main`, not pushed; the push is the operator's.** Schema **v40** live. The last pipeline run read was **183**. **The 17:30 HST run of 09-24 is the FIRST on v40.** Compare its per-class warning Counter against run 183 and read `export_status` (it was `ok` on 183). RD's successor owns a T1 check on the same run.
- **Worktrees:** `.worktrees/22-i-plan` (branch `22-i-plan` @ `cd053a06`) and `.worktrees/d67-d69-riders` (branch `d67-d69-riders` @ `fae33471`). Both are clean.
- **Directors:** CHARC `swing-charc-20260924-0726`; RD `swing-rd-20260924-0705`. Both rolled once today. Trust the `ping ->` line that `role_mail post` prints.

## 2. IN FLIGHT, owner = you

### 22-I (the REPLACE-exposure sweep) — the plan is COMMITTED; director acceptance is PENDING

- **Plan:** `docs/superpowers/plans/2026-09-24-phase22-arc-i-replace-exposure-sweep.md` @ `3f813ddb`, 422 lines, sha256 `0863ab71…`.
- **Ledger:** `….ledger.md` @ `cd053a06`. It carries every ruling as a block quote with the author named, the round table with the depth column filled by this seat, the step-3 measurements, the self-sweep, and the spend (407,568 Codex tokens over three `fast` rounds).
- **Census:** `….census.md` alongside it.
- **Evidence:** `~/swing-data/review-transcripts/22-i-plan/`.
- **Probe copy:** `~/swing-data/scratch/22-i-probe/`, about 1.7 GB each plus a copy-of-copy. **Delete it only after 22-I merges.**
- **Rulings are final.** All round-0 and step-3 rulings from CHARC and RD have landed. The text of record is the brief `docs/phase22-arc-i-f-sweeps-commissioning-brief.md` on main, last amended @ `732c5c21`, plus RD's mails (transcribed).
- **Three counted rounds.** Each had one task-bearing finding (R1-1, R2-1, R3-1), and each is fixed. This seat re-asserted every round as valid (the five checks). No fourth round was authorized.
- **Posted 19:18Z** to CHARC (architecture pass, plus the `fills` fact correction — CHARC's a17 line @ `732c5c21` calls `chart_renders` "the only" reachable parent, but `fills` is deleted at `reconciliation_auto_correct.py:3226`) and to RD (plan-stage review).
- **This seat did NOT read the 422-line plan end-to-end.** It said so in the post. **Your plan QA reads it** before acceptance is transcribed.
- **Next:**
  1. Drain the inbox.
  2. Transcribe CHARC's architecture pass and RD's review into the ledger as block quotes.
  3. Once 22-I's plan is ACCEPTED, dispatch the **22-F plan cell** (`implementer-opus-high`; census first, no Codex; the brief is the same file, 22-F sections), then the **22-I executing cell** (`implementer-opus-high`; Reviewer A `strong`; Reviewer B is yours, under DEFAULT TO INTRODUCED).
- **Calendar:** the 22-I witness sitting (W0–W5, brief §5) happens BEFORE 10-02 EOD HST or AFTER 10-20. If Reviewer B is not clean by 10-01 EOD HST, 22-I parks to 10-21; post the park. Never schedule it across the 17:30 HST pipeline. 22-F may merge during the pause.

### D67 + D69 riders — code DONE, review loop INCOMPLETE (the cell was stopped)

- **Brief:** `docs/d67-d69-riders-brief.md` @ `321689e2`.
- **Commits** on `d67-d69-riders`: `ecace254` (D67), `d87cda41` (D69), `c8597298` (R1-3-SURFACES census line re-derivation), `10e30e02` (Codex R1 Majors 1+2), `fae33471` (Codex R2 Major). Trailers are empty.
- **The cell's last message:** full suite green, **13421 passed / 13 skipped / 0 failed** before round 3. That is its claim; **re-run it yourself.**
- **Reviewer A rounds** (`strong`, `gpt-5.6-sol` / `high`):
  - R1 and R2 are complete, each `NEW_CRITICAL_MAJOR_FOUND` with a footer, and each is fixed.
  - **R3 was IN PROGRESS when the cell was stopped.** Its transcript has no footer and no verdict, so it DOES NOT COUNT. No WSL codex process survives.
- **Why stopped:** the cell was at 422K. It never returned at a round gate, although the dispatch said to (it ran R1 → fix → R2 → fix → R3 unbroken). It also kept its whole review record in the session scratchpad only, never copy-per-round.
- **This seat copied the record to `~/swing-data/review-transcripts/d67-d69-riders/`**, sha256-verified against the scratchpad: r1/r2/r3 transcripts, `.copowers-findings.md`, diffs, refs, prompts, and ledgers.
- **Next:**
  1. Dispatch a FRESH `implementer-sonnet-high` cell into `.worktrees/d67-d69-riders`. It re-runs round 3 on the tree at `fae33471` and continues to convergence. **Tell it explicitly: return at EVERY round gate, and copy each round to the durable dir the moment its assertions pass.** Name both failures of the prior cell in the prompt.
  2. Then you run Reviewer B (cold audit, CLAIMS_FIRST).
  3. Then the merge (`--no-ff` if ledgers cite SHAs, otherwise rebase + `--ff-only`), plus the merged-head suite.
- **D67 masking-mechanism finding:** it is in the D67 commit/test; read it at QA. If the wrapper is BYPASSED in the full run (the `entry.py` by-name import hypothesis), route that to CHARC as a second finding.
- **Note for the D67/D69 QA:** the rider touched `tests/metrics/...` R1-3-SURFACES census line numbers (`c8597298`). Check that this is the re-derivation the brief allowed, not a pin moved to make a test pass.

## 3. DONE THIS GENERATION

- **CLAUDE.md** "TWO backups" gotcha retired (`53143892`).
- `_is_head` rider found already landed (`e8a4d54e`).
- `%TEMP%/pytest-of-rwsmy` (6.3 GB) deleted.
- `orchestrator-context` in-flight section rewritten (`b8f80e91`).
- **`cell_depth --agent <id>`** (`b09bbc02`, CHARC ruling (a)). **Use it at every round gate.** CHARC updated the harness sentence at `7e2fdb70`.
- **22-B** RD witness step 5 transcribed (`4b66ccec`).

## 4. AUTHORITIES (a grant is STATE)

- **Operator:** "Fix the remaining 6 items on your list". This covers the D67/D69 riders through merge. Spent on everything else.
- **Operator, via CHARC's dispatch** (`d4f2cbed`, the brief's STATUS line: "Perform the resequencing and kick off the work"): covers **22-I and 22-F in the order 22-I → 22-F**. Plan cells, executing cells and the gates are as the brief states. **The 22-I witness sitting still needs the operator present, step by step.** 22-C/22-D keep their live-case gate; 22-H waits for RD's October read.
- **Cells dispatched this generation:**
  - D67/D69 `implementer-sonnet-high` (STOPPED).
  - 22-I census `implementer-opus-high` (returned, over the cap).
  - 22-I plan writer `implementer-opus-high` (returned after R1, over the cap).
  - 22-I R2/R3 `implementer-opus-high` (returned, done).
  - None needs resuming.

## 5. WHAT WILL BITE YOU

- **A cell told to "STOP and return at each round gate" may not.** The D67/D69 cell ran three rounds straight through to 422K. Read `cell_depth --agent <id>` periodically while a cell runs, not only at returns.
- **A cell's scratch in the SESSION scratchpad dies with the session's findability.** Name the durable dir in the prompt and require the copy per round.
- **The harness moves your cwd into a worktree after git operations there.** Always `cd` to the main repo inside the same `role_mail` invocation (rule 2).
- **Directors' incidental facts are often wrong** (the `pipeline_runs` deleter, the `fills` deleter, the trade-23 replay, the web 409 location). Verify them in code before encoding them. The cells caught four such facts today.
