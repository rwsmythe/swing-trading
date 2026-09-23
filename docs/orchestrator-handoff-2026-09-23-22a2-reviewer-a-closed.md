# Orchestrator handoff — 2026-09-23 — 22-A2: REVIEWER A CLOSED at round 5; Reviewer B is next

**Supersedes** `orchestrator-handoff-2026-09-23-22a2-reviewer-a-r3.md`.
**From:** the generation launched 2026-09-23 ~10:37Z (session `2d6bbb15`, Opus 5.5, build 2.1.280).
**Rolled at:** ~320K, self-read by `cell_depth.py --sessions --live 1` at 315,053 before the last gate. That is under the 400K trigger. I rolled early because the next step is to design Reviewer B's prompt and then QA its return, and I could not finish both inside 400K. The boundary is clean: no cell is in flight (cells 17, 18 and 19 have all returned and been QA'd, each gate row committed), and nothing is open with either director.

**Re-derive every fact below. Do not carry the numbers forward.**

---

## 1. STATE

- **`main` @ `1280aaa0`** (CHARC's D66), plus this handoff. At my last check `main` was **9 ahead of origin**. The auto-mode classifier blocks `git push` from this seat, so hand the operator `! git push origin main`; I asked for it several times this sitting, and it had not been done by the time I rolled.
- **22-A2 branch `22-a2-exec` @ `cd06c7ac`** (worktree `.worktrees/22-a2-exec`).
  - **Production head `7e8bfb84`.** Since then only `tests/data/` and plan/ledger docs have changed: `git diff --stat 7e8bfb84..HEAD -- swing scripts` is EMPTY.
  - The review diff base is **`05702929`**.
- **Digest `.6` = `9d426fd5...1ab0`**: 100 members, history `.2`–`.6`. Grammar is still `.1`, there is no new migration, and the schema manifest is clean.
- **Last full fast suite:** `14ee17d7`, `-n 4`, **12956 passed / 13 skipped / 0 failed** (cell-read; ruff and manifest clean). The merged-head suite is still owed and binding.
- Live DB is **v38**, untouched. Worktrees: `.worktrees/22-a2-exec` (THE ARC) and `.worktrees/22-a2-plan` (keep until the merge, then tear down with sha256 reconciliation of the evidence). Stash: the one 2026-05-31 quarantine entry; never pop it.
- **Directors:** both rolled this sitting. The current seats are `swing-charc-20260923-0045` and `swing-rd-20260923-0048`, but trust the `ping ->` line `role_mail post` prints, not these names.

## 2. WHAT THIS GENERATION DID (exec ledger: gate rows A-R4, A-R5, C-19, plus ruling sections and three orchestrator decisions)

| Step | Where | Result |
|---|---|---|
| A-R3 rulings transcribed | `d4d55cde` CHARC, `44e0a3f3` RD | R3-01 → AL2-13 (the SQL half goes to CHARC's D65); R3-02 (a) compare |
| Decision: 4th counted round | `ace016f1` | authorized for R3-02 |
| R2-05 ruling (CHARC (a)) | `da304c5d` | relayed to cell 17 by message; recorded in the A-R4 row |
| **A-R4**, cell 17 | row `78a33e9e` | round 4 NOT clean (467,559). R4-01 CRITICAL: a `git replace` ref or poisoned `GIT_*` env forges facts |
| A-R4 rulings | `cc98d81e` RD, `c6f30113` CHARC, `021e0166` RD (AL2-14) | R4-01 fixed as `.6`; R4-07 folded in; R4-02 fixed; R4-03 rejected → AL2-14 |
| Decision: 5th counted round | `0397c083` | authorized for R4-01 |
| **A-R5**, cell 18 | row `d1065369` | round 5 NOT clean (892,205). The clock time bomb was pinned (test seam). R5-01 grafts, R5-02 separators, R5-03 scanner |
| A-R5 rulings | `ae27b56f` CHARC, `29885f55` RD (items + a **gate supersession**), `8cfecb84` CHARC concurs | R5-01 → **AL2-16** (the local-clone class, ruled once, discharged OFF-BOX at witness step 6); R5-02 → AL2-15; R5-03 test-only; the `.7` belts are BANKED as **D66** |
| Decision: A loop CLOSED | `4207d2b2` | no sixth round, under RD's dispositioned-verdict gate |
| **C-19**, cell 19 (no Codex) | row `cd06c7ac` | R5-03 `8379d1e5`, AL2-15/16 + AL2-4 widened `14ee17d7`; suite green |

Every ruling was transcribed byte-for-byte with `scratchpad/transcribe.py`: the mail body after the front matter, each line asserted present, and `> ` the only added byte. **Supersessions are declared in the NEW block's header; old blocks stay byte-identical (RD confirmed this form at 14:24:40Z).** Counted-round spend: **3,435,731** over five rounds.

## 3. WHAT IS NEXT, IN ORDER (the standing authorization covers every step through the merge)

1. **REVIEWER B on the tree being merged (`cd06c7ac`, production `7e8bfb84`).** B is the **codex-auto-review pass defined in charter §2.9**, NOT a hand review. Read `docs/harness-architecture.md` "THE B GATE'S ABSENCE IS NOW BLOCKING" (:184), "THE B GATE'S STOPPING CONDITION" (:196), and the pointer-not-paraphrase rule (:214) BEFORE writing its prompt. Its transcript, five mechanical assertions and verdict are named in the merge request. B is NOT required to be clean: every finding must be DISPOSITIONED (introduced vs banked).
   - **The B prompt carries:** AL2-1 through AL2-16 with their reasons, and the standing invitation to challenge them. AL2-15 and AL2-16 are named explicitly (CHARC's concurrence). It also carries the nine recorded deviations in the Task 12 record (per the prior handoff) and the A-loop's rulings.
   - **Cell choice:** I would use `implementer-opus-high` (critical instrument). Every B cell before this ran past ~400K; plan one fresh cell.
2. **RD's merge-blocking measurement gate.** It now reads a Reviewer A verdict in which every critical/major is DISPOSITIONED, with no later production change of critical/major scope (RD's supersession, `29885f55`). On top of that, RD's gate still requires:
   - B's transcript on the merge tree, with its findings dispositioned;
   - every AL2-1..16 on the list with its reason;
   - the `.6` fixture diff = `derivation_version` only;
   - the four cohort readers' markers rendered;
   - A2-98..104 on the shipping tree;
   - the H1 count quoted from the reader.
3. **CHARC's merge gate**, then **merge `--no-ff`** (ledgers cite branch SHAs, so never rebase). Then run `schema_manifest.py --write` on the merged head, the merged-head suite at `xhigh`, and the merge-composition read.
4. **THE WITNESS**, OPERATOR-EXECUTED, one step per operator result (memory `feedback_witness_step_by_step`). It covers plan section 9 + the FK-orphan step per `5fcb6b1c` + CHARC's D32 production proof. **Step 6 now includes AL2-16's discharge:** the OFF-BOX ancestry-and-content check of trade 25's cited sha on a FRESH clone of the true remote. **09-30 hard stop; no witness 10-03..10-20.**
5. Teardown: both worktrees, with sha256 evidence reconciliation into `~/swing-data/review-transcripts/22-a2-{exec,plan}/`. Evidence files are DOTFILES.

## 4. AUTHORITIES GRANTED BY CELL MESSAGE

One, now spent: cell 17 received CHARC's R2-05 ruling by message (~10:45Z, citing `da304c5d`) as its authority for item 6. It is recorded in the A-R4 row. Nothing is open.

## 5. QUEUE (not done)

- Everything in the prior handoffs' section 5 still stands: the FK instrument, N1, the stale TWO-backups gotcha, the `_is_head` rename rider, the em-dash, the stale in-flight section of `orchestrator-context.md` (still describes 2026-09-15; rewrite it at a close-of-sitting), and 22-B's operator go/no-go.
- CHARC's post-merge queue: **D65** (the 0039 content belts incl. the four attestation literals), **D66** (the future `.7` pair), an off-box verifier primitive, D61/D62/D64, 22-A2i.
- Recorded, not rewritten (past the tip): `a403fabc`'s final paragraph `Discriminators:` parses as a non-CA trailer; `8379d1e5`'s second paragraph opens `R5-03:` (trailers empty).

## 6. WHAT WILL BITE YOU

- **Standing authorization** (`docs/phase22-arc-a2-commissioning-brief.md` line 3 @ `78a395ed`): "We will execute these in order without needing additional permissions unless I say otherwise." It covers B, the gates and the merge. It does NOT cover a scope change, 22-B's go/no-go, or the witness (the operator executes it).
- **Fixture clock literals.** The 22-A2 worlds are now pinned by `pinned_migration_clock` (`tests/_tier2_world_22a2.py`) to `2026-09-22T12:00:00Z`. Any new world must use it, or it becomes a time bomb again.
- **Cells run past the cap.** Cells 17 and 18 returned at 423K and 406K. One fresh cell per round/gate, never resumed.
- **Runner:** my scratchpad `loop/` (`C:/Users/rwsmy/AppData/Local/Temp/claude/C--Users-rwsmy-swing-trading/2d6bbb15-b41e-4978-963c-d38aada43b0b/scratchpad/loop/`) holds `run_r5.sh`, `assert.sh`, `preserve_r5.sh`, the prompts and the diffs. `assert.sh <N>` gates a transcript; a capacity abort (footer, no verdict) is NOT a round. Durable evidence: `~/swing-data/review-transcripts/22-a2-exec/` (r1..r5 + `cell18-probes/`). The dispatch files for cells 17/18/19 are in that scratchpad too, and are useful templates.
- **Ledger edits:** write rows to a scratch file with the Write tool, then insert with a script that asserts `'\n' not in row` and inserts after the named previous row (`| C-19 |` is last). Never run escapes through a bash heredoc. Always use pathspec `--only` commits.
- **Commit messages:** no paragraph may begin `Word:`; state that in every dispatch.
- Every prior section-6 item still applies: `-n 4` for the full suite, no stash, no `git checkout <sha>` in the exec worktree, `--body-file` always, `cd` to main in the same invocation as the post, verify delivery on disk, and ping after every post.
