# Orchestrator handoff — 2026-09-22 (evening) — D51 and the cell_depth rider merged; 22-A2's round-0 packet fully ruled; the 22-A2 PLAN CELL is your first dispatch

**Supersedes** `orchestrator-handoff-2026-09-22-d56-merged-opus-55-rider-owed.md`.
**From:** the generation launched 2026-09-22 12:27 HST (session `4a938de4`, map name `swing-orchestrator-20260922-1227`, Opus 5.5 on build 2.1.280).
**Rolled at:** ~315K (`cell_depth.py --sessions --live 1`), under the 400K trigger. I rolled BEFORE dispatching the 22-A2 plan cell on purpose. A cell dies with the session that spawned it, and an xhigh plan cell with up to three rounds would have taken this seat past the cap before its QA.
**Precondition met:** no cell in flight, no grant open, no ruling outstanding.

**Re-derive every fact below; do not carry the numbers.**

---

## 1. STATE

- **`main` @ `91ef1684` (the D51 merge), 17+ commits AHEAD of origin, UNPUSHED.** The operator authorized one push this sitting (`a031795d`), not standing pushes. Ask before pushing.
- Merged-head suites:
  - Rider merge `3b98ca55`: **12,475 passed / 13 skipped / 0 failed** (`-n 4`).
  - D51 merge `91ef1684`: **12,489 passed / 13 skipped / 0 failed** (`-n 4`, read off the merged head).
- Live DB **v38**. Pipeline run **181** complete, `export_status=ok`. **Zero open trades (the book is flat).**
- Worktrees:
  - `.worktrees/22-a2-plan` @ `95bbe700` (the ruled ledger; KEEP).
  - `d51-schema-manifest`: torn down (containment proved; evidence reconciled by sha256, 4/4 MATCH against `~/swing-data/review-transcripts/d51-schema-manifest/`). `cell-depth-model`: torn down.
- The stash still holds exactly one entry (`435a4d1c`, 2026-05-31 quarantine). **A cell popped it by accident this sitting** and restored its worktree; the entry is intact. Never pop it.

## 2. WHAT THIS GENERATION DID

| Item | Result |
|---|---|
| Push + table fix | `a031795d` pushed. `348f126b` fixed orchestrator-context's archived-decisions table: `f2b58728`'s trim script %-formatted `10% return`, which spliced the 21 rows mid-sentence as a repr and left `__ROWS__` literal. |
| **cell_depth rider** | **MERGED `3b98ca55` (`--no-ff`, `84c4a398`).** Rows print `build` (top-level `version`) and `model` (`message.model`, `<synthetic>` excluded; mixed values shown first-seen, joined `+`). QA reproduced 3 pre-measured live transcripts exactly. No Codex round, declared. Recipe §4 accept-record line: `8d787c5c`. Worktree and branch removed. |
| **D51** | **MERGED `91ef1684` (`--no-ff`), recipe line C4(i) in the merge commit (§2, "EVERY MIGRATION COMMIT REGENERATES THE SCHEMA MANIFEST").** 163 objects at v38 (CHARC's 151 + 12 autoindexes). One A round at `fast`: `gpt-5.6-luna`, effort `medium`, `^ERROR` 0, footer present, `NO_NEW_CRITICAL_MAJOR`. 2 minors fixed. One orchestrator fix leg (the fixture header states `# schema_version 38`), now CLOSED. Evidence: `~/swing-data/review-transcripts/d51-schema-manifest/`. **Brief C3.1's worked example had the bucket backwards** (removing a fixture line reports `unexpected`, not `missing`); the code is right. Merged-head suite **12,489 / 13 / 0**. Return report POSTED to charc (`comms/charc/inbox/20260922T234307Z-...d51-return...`). |
| **22-A2 census** | Opus-xhigh cell, round 0, ledger at `af9651a0`. **The first Opus 5.5 cell:** peaked at **460,189** (over the cap, on census alone), so it is NOT resumed. **Positive control:** 33 `"type":"text"` vs 69 `"type":"thinking"` record lines. Rulings transcribed byte-for-byte (script-verified), author = director, courier = me: **R0.7** CHARC `066cdb52`, **R0.8** RD `08091b2f`, **R0.9** CHARC F10-shape + P28 `95bbe700`. **THE PACKET IS FULLY RULED.** |

**Spend:** rider cell ~230K; D51 cell ~399K incl. fix leg, Codex 43,550; census cell 461,773.

## 3. AUTHORITIES GRANTED BY CELL MESSAGE

One, now CLOSED: the D51 fix leg (the fixture header version, post-convergence, no Codex round), delivered at `a930b5ef`. **No grant is open.**

## 4. QUEUE — in order

1. **Dispatch the 22-A2 PLAN CELL, fresh, first thing.** `implementer-opus-xhigh` (CHARC's stated reason: schema-and-contract design where a wrong answer is confident). Base: the `22-a2-plan` branch at `95bbe700`. Resume the SAME worktree. Its round-0 ledger is the committed packet plus rulings.
   - **Effective scope after the rulings is trade 25 ONLY.** F1.1=b (19/24 named-pending, F1.2 NOT live), F3.1=b (28 named-pending, F3.2 NOT live), **F2=b with F2.T (t1) LIVE** (a suite test importing `BARRIER_TRIGGER_NAMES`, failing on any later migration that drops a barrier trigger without an era record).
   - F2.I = I-1 plus the two named gap kinds. F6 absorbs into the four criteria. F7 compares the author instant in ET, date strictly `<` the fill session. F10 is a read-time `replay_verdict` in the F4 module, no cross-call cache. F8 (a) with the `instr` check. F9 (a): `{artifact_path, artifact_commit_sha, quoted_text}` only, pin 5→6. F11 (b): `escaped_by_tier2`, blob version bump. P28: 0039 carries its own backup-gate row.
   - The plan is a task ladder + test roster ≤ ~1,000 lines, at most three counted rounds at `fast`, then a self-sweep. **Run `cell_depth --live` at every round gate** (it now prints the cell's model).
   - Executing waits for D51, which is DONE. The executing cell is chosen at the plan's return, default `implementer-opus-high` by the recipe's migration exception, **Reviewer B required**.
   - **Calendar:** 22-A2 witnessed by ~09-30 (operator hard stop). No witness 10-03..10-20 (operator travel).
2. **22-B's plan stage** may start once 22-A2's PLAN is committed (CHARC, 23:25Z, superseding his 23:22Z clause). The brief is CHARC's and follows the 22-A2 plan's return. 22-A2 and 22-B are SERIAL at executing/merge (a rule). **The 22-B go/no-go is an OPEN OPERATOR CALL at 22-A2's landing** — do not pre-decide it.
3. **The D51 live-DB probe witness BEFORE 10-03** (CHARC closes D51 on it, not on the merge): with `swing web` stopped, `python scripts/schema_manifest.py --db "$USERPROFILE/swing-data/swing.db"`. Expect `schema_version 38`, clean, exit 0. **A non-clean result is a FINDING for the register, not a D51 failure.** One step, operator-attended.
4. **D51 return: POSTED** (23:43Z). It asks CHARC two things. Await his answers: (a) whether he vetoes my added sentence in the recipe line ("the gate is a READER of the deleted lines, not the test"); (b) whose the Gotchas compression is.
5. **Mine, small:**
   - The D51 paired CLAUDE.md gotcha (C4 ii, under 700 chars, trigger + fix), riding the NEXT gotcha commit. §Gotchas is AT the ~55K soft cap, so that commit carries a compression pass. CHARC's FYI said "beside the gotchas compression you owe", while the prior handoff called the compression CHARC's; **settle whose it is with CHARC before doing it.** The "TWO backups" gotcha is FALSE since D32 (the census re-confirmed one backup at `cli.py:263-360`).
   - The recipe datum CHARC offered: at xhigh on Opus 5.5, census and plan run as TWO cells by default.
   - Record the positive-control numbers on the D57/§2.11 row at the next state write.
   - The `_is_head` rename rider (its own commit).
   - The em-dash in `swing/cli.py`'s pre-18 WARN line.
6. RD's successor owns the 6 open reconciliation discrepancies. RD already recorded the 09-17 liquidation as a deliberate go-flat.

## 5. WHAT WILL BITE YOU

- **Ping names:** CHARC `swing-charc-20260915-1803`; **RD ROLLED — `swing-rd-20260922-1232`.** Always use the `ping ->` line `role_mail post` prints.
- **`role_mail` caps the subject at 80 chars** and refuses the post.
- **A cell can't see its model or depth — you read both** from `cell_depth`. Opus 5.5 at xhigh reached 460K on a census alone.
- **Transcribe rulings byte-for-byte by script and verify the span is present;** the `—` escapes arrive literally from the mailbox. Label honestly.
- **Cells share the stash stack.** Tell executing cells never to `git stash` anything.
- **Every prior §5 still applies:** `-n 4` not `-n auto`; `!` runs in bash; `--body-file` + cd-to-main + verify-on-disk; `--no-ff` once anything cites branch SHAs; cp1252 both sides; dotfile evidence.
