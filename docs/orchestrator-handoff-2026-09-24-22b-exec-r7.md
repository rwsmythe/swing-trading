# Orchestrator handoff — 2026-09-24 — 22-B EXECUTING: Reviewer A through round 7; four CHARC items pending; round 8 NEXT

**Supersedes** `orchestrator-handoff-2026-09-24-22b-exec-r1.md`.
**From:** the generation bootstrapped 2026-09-24 ~07:32Z (session `12fd8fa1`, Opus 5.5, build 2.1.280).
**Rolled at:** ~334K self-read (`cell_depth.py --sessions`), on a CLEAN boundary. **No cell is in flight.** Cells 14, 15, 16 and 17 have all returned; none is to be resumed (each is near or past the depth budget, and every loop step goes to a fresh cell).
**Why here:** a ruling round trip followed by a dispatch and a QA costs this seat ~40K, and round 8 cannot be QA'd inside the remaining budget. By the MIRROR rule, round 8 is the successor's to dispatch.

**Re-derive every fact below. Do not carry the numbers forward.**

## 1. STATE

- **Standing grant, unchanged:** the operator's *"We have 7 days before 9-30, plenty of time. Let's go for 22-B"* (the header of `docs/phase22-arc-b-rd-rulings-f1-f3.md`, `e0a75a67`; CHARC's brief `9d89e304`). It covers executing, so **dispatch round 8 without a fresh go.**
- **Stop line:** Reviewer B (THIS SEAT's cold audit) must be clean on the finished executed tree by **2026-09-29 EOD HST**, or the arc PARKS.
- **`main`** carries this handoff; the push is the operator's. CHARC committed brief updates to main during this sitting (`e74513db`, `874a3277`, `e2f85d22`, `9de59e84`, `7f30347b`, `af8c8ebc`); each was merged into `22-b-exec` `--no-ff` when it carried a ruling's text of record.
- **Exec branch `22-b-exec`** (`.worktrees/22-b-exec`): HEAD **`57f05260`** (a ledger commit), tree clean.
  - Code HEAD: **`9add7097`**.
  - **Last full fast suite: `13387 passed, 13 skipped, 0 failed` on `9add7097`** (`~/swing-data/review-transcripts/22-b-exec/cell17-r7fix-full-suite.txt`, SHA on line 1). This is cell 17's run; I verified the file and its SHA at this seat.
  - Trailers empty over `e61dad27..HEAD`.
- **The exec ledger** `docs/superpowers/plans/2026-09-23-phase22-arc-b-unintended-execution.exec-ledger.md` is the record:
  - gate rows through G7g;
  - the Reviewer A round table R1–R7 (each row's assertions re-read by the orchestrator from the transcript);
  - FORK sections R2-2, R3-1, R5-1 and R6-1, all CLOSED;
  - RULING sections R2-2, R3-1, R4-1-TEXT, R5-1, R6-1a (RD) and R6-1b (CHARC), each a literal block quote with every line script-asserted present.
- **Spend line:** 5,349,438 (rounds R1–R7). Report it in the merge request (recipe §4).
- **Directors:** CHARC `swing-charc-20260923-1857`, RD `swing-rd-20260923-1851`. Trust the `ping ->` line that `role_mail post` prints.

## 2. WHAT THIS GENERATION DID (the ledger is authoritative)

| round / gate | reviewed / code HEAD | verdict | outcome |
|---|---|---|---|
| R2 | `c182b7b2` | 0/2/0 | R2-1 confirmed not a defect; R2-2 FORK → RULING R2-2 (B): the exit route's dead handler retired, b22_237 moved onto the real builder path (G7d `f60973b8`) |
| R3 | `f60973b8` | 0/1/0 | R3-1 FORK (AL-6 challenge accepted on the message) → RULING R3-1: both review surfaces name the committed review first (G7e `7d258390`) |
| R4 | `7d258390` | 0/1/2 | R4-1 fixed `6f099bcc` (the recorded echo moved between two writes → the 22-A3 sink); RULING R4-1-TEXT: the existing echo stands |
| R5 | `6f099bcc` | 1/0/0 | round-5 check-in; R5-1 FORK → RULING R5-1: the `trg_eia_tier2` member type guard plus a 22-site sweep (G7f `f9410643`) |
| R6 | `f9410643` | 1/0/1 | "one confirming round", NOT clean; R6-1 FORK (the placement date is not bounded by the entry date; live incidence 0 of 14, measured `mode=ro`) → RULING R6-1a (RD: refuse with `placement_after_entry`) + R6-1b (CHARC: four places) |
| G7g + R7 | `502b9b0f` | 0/2/0 | R6-1 and R6-2 encoded (`e2f4babb`, `502b9b0f`); R7-1 fixed `2e5104b8`, R7-2 fixed `560e944e`, roster re-anchor `9add7097` |

The shape of the loop: **0 reopened in 7 rounds.** Most later findings have been residuals of the loop's own fixes (R4-1, R7-1, R7-2). R5-1 and R6-1 are the two original-code finds.

## 3. WHAT IS NEXT, IN ORDER

1. **Drain the inbox:** CHARC's reply to the packet `20260924T121545Z-orchestrator-22-b-r7-...` (four items).
   - **Item 1:** three differences from R6-1b's text, all already encoded: the NOT NULL citation, the extended RAISE text, and the named recovery command.
   - **Item 2:** R7-1's sink on the DRY-RUN path.
   - **Item 3:** encode or bank the `conn.close()` sibling (a close raising after the commit).
   - **Item 4:** the pre-existing backfill prompt's raw ticker, for the register.

   Transcribe any ruling into the exec ledger as a literal block quote (the script pattern this generation used: read the mail from `comms/orchestrator/read/`, assert every quoted line present). If item 3 is ruled "encode", dispatch the encoding with round 8 in the same fresh cell.
2. **Round 8**, as the next confirming round, in a FRESH `implementer-opus-high` cell. Target `git diff -U8 e61dad27 <code HEAD> -- swing tests scripts` (~793 KB at `502b9b0f`, under the stdin cap).
   - Template: cell 17's `reviewer-a-r7-{prompt,run,exit}` in `~/swing-data/review-transcripts/22-b-exec/`.
   - Add every new ruling to the settled list.
   - The cell returns after the round whatever the verdict.
   - Re-read all five assertions from the transcript yourself.
   - The cell-17 dispatch prompt (in this session's transcript) is the model: encode then round, and a FORK stops the cell.
3. **At convergence**, the cell runs: the full suite on the final head, ruff, `schema_manifest.py --check`, the trailer audit, and the spend line.
4. **Reviewer B:** THIS SEAT's cold audit, CLAIMS_FIRST, every finding defaulted to INTRODUCED. The runner model is `~/swing-data/review-transcripts/22-a2-exec/run_b.sh`.
5. **CHARC's merge gate** (CHARC-S3.2):
   - B's transcript on the tree being merged;
   - the merged-head suite line with its SHA;
   - the D51 diff on the merged checkout. `trg_eia_tier2` is the one trigger whose pin moved this sitting (R5-1, then R6-1); CHARC reads it as one changed object;
   - the runtime composition: `swing web` stopped; a `BEGIN EXCLUSIVE; ROLLBACK` result stated; merge + `db-migrate` in ONE sitting; `schema_manifest.py --db` clean at v40; `foreign_key_check` = [].

   Then the operator's witness, one step per result, before 09-30.
6. **Merge form:** `git merge --no-ff`, never rebase.
7. **RD's successor owes:** the executing-return gate, witness step 5, the §7 pointer line AT the merge, and the October read.

## 4. AUTHORITIES GRANTED BY CELL MESSAGE (a grant is STATE)

- **Cell 14:** Reviewer A from R2 to convergence. Resumed once to encode RULING R2-2 (stop at the encoding gate). Retired at 342K.
- **Cell 15:** R3 onward. Resumed three times:
  - to encode R3-1 and run R4 without returning in between;
  - to run R5 (the check-in);
  - to encode R5-1 plus the uncounted 22-site sweep (encoding only).
  Retired.
- **Cell 16:** R6, ruled as ONE confirming round; told to return whatever the verdict.
- **Cell 17:** to encode R6-1a/b plus R6-2 and then run R7 in the same cell; told to return after R7.
- **Loop decision at the round-5 check-in (this seat's, CHARC-concurred):** continue; fix plus an uncounted self-sweep as one unit; then confirming rounds, each in a fresh cell.
- **No round 8 has been authorized or run.**

## 5. WHAT WILL BITE YOU

- **A ruling that orders I/O between two durable writes must name the post-durability sink.** This produced R4-1 and again R7-1. Put it in the encode prompt.
- **A per-class fix without a module sweep leaves the next round a residual.** R6-2 → R7-2. Tell the encoding cell to sweep the whole module for the class it is fixing.
- **The R1-3-SURFACES census roster keys `cli.py` by line number.** Every CLI edit moves it, and cells re-anchored it three times. Expect it.
- **Codex prints the verdict line twice.** The anchored count is 2 for the one token; the assertion is *one DISTINCT token*, with the other token at 0.
- **Plan text edited by the courier beyond a ruling's literal text must be flagged in the post** (the AL-6 "No window test" sentence — flagged, CHARC concurred). Never edit a ledger block quote after the fact.
- **`role_mail` subjects are capped at 80 chars.** Post from the MAIN repo cwd in the same invocation.
- **D67** (`test_trade_entry_sector_industry_tamper.py` fails 3/15 in isolation) is pre-existing and registered by CHARC. It is a post-merge rider, not 22-B's.
- **Scratch to delete after the merge:** the predecessor's migrated live copy plus gate image (~3.3 GB) at `C:/Users/rwsmy/AppData/Local/Temp/claude/C--Users-rwsmy-swing-trading/c36c1abd-a707-4dc7-a93e-deff586eb351/scratchpad/g6/`, kept for Reviewer B; and `%TEMP%/pytest-of-rwsmy`.

## 6. QUEUE, owners named

- **Orchestrator:**
  - the `_is_head` rename rider;
  - `cell_depth --sessions` printing the build;
  - `cell_depth --live` showing more than the newest cell;
  - the stale §"Currently in-flight work" in `docs/orchestrator-context.md` (still 2026-09-15; the handoffs are the current record);
  - D67 as a post-merge rider, per CHARC's shape (a `**kwargs` wrapper, with the masking mechanism stated first).
- **CHARC:**
  - the Gotchas compression pass;
  - the D38 sweep;
  - the exit rebuild being uncontained for any exception (banked);
  - the four R7 packet items;
  - the register entry for the pre-existing backfill prompt's raw ticker.
- **RD/operator:** the post-merge display gap (RULING G3a (i)).
