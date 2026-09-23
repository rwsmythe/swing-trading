# Orchestrator handoff — 2026-09-23 — 22-A2 REVIEWER A: three counted rounds done, round 3 NOT clean; the A-R3 packet is with the directors

**Supersedes** `orchestrator-handoff-2026-09-23-22a2-tasks-done-pre-review.md`.
**From:** the generation launched 2026-09-23 ~06:43Z (session `7a4e5079`, Opus 5.5, build 2.1.280).
**Rolled at:** ~340K (`cell_depth.py --sessions --live 1` read 335,881 before the last gate), under the 400K trigger, at a clean boundary: no cell in flight (cells 14, 15, 16 all returned, each gate QA'd and committed), and one packet out whose rulings land with you.

**Re-derive every fact below; do not carry the numbers.**

---

## 1. STATE

- **`main` @ `19cd5c89`**, 4 ahead of origin (CHARC's D65 commits `18b1c650` / `19cd5c89`, the prior handoff `65c0601a`, `fcc9f3b2`) plus this handoff. The auto-mode classifier blocks `git push` from this seat; hand the operator `! git push origin main`.
- **22-A2 branch `22-a2-exec` @ `da87480b`** (worktree `.worktrees/22-a2-exec`). Code head **`a305fa4c`**. The review DIFF BASE is **`05702929`** (the branch's merge-base with main; the prior handoff said `c212238a`, which differs only by plan/ledger docs -- corrected and told to the directors).
- **Derivation digest `.5` = `ab5ede88...5c88`**, 100 members, history `.2/.3/.4/.5` (orchestrator recomputed via `frozen_value_evidence_digest()`). `.4` (`0b00974d...`) was A-R1 item 2; `.5` was A-R2 R2-01. Grammar version `.1`, no new migration, schema manifest clean.
- **Last full fast suite:** on `d154584e` `-n 4`, 12909 passed / 13 skipped / 0 failed (cell-read). `a305fa4c` is test-only after it. The merged-head suite is still owed and binding.
- Live DB **v38**, untouched. Worktrees: `.worktrees/22-a2-exec` (THE ARC) and `.worktrees/22-a2-plan` (keep until merge; tear down with sha256 reconciliation). Stash: the one 2026-05-31 quarantine entry; never pop.

## 2. WHAT THIS GENERATION DID (exec ledger gate rows A-R1, A-R2, A-R3 + four ruling sections)

| Gate | Cell | Commits | Result |
|---|---|---|---|
| A-R1 | 14 | `b6063d40` R1-04, `c65266ff` R1-02 | round 1 counted, 726,472 tokens; R1-01 + OBS-1 routed |
| — | — | ledger `168428a5` (RD A-R1), `b9780bd8` (CHARC A-R1-SHAPE) | R1-01 (a) derived segments + prose compared; OBS-1 (b) whole line, `.4` |
| A-R2 | 15 | `b171f1bb` item 1, `994658fc` item 2 (`.4`), `a234902d` R2-03 | round 2 counted, 648,131; R2-01..04 routed |
| — | — | ledger `9391ecfa` (RD A-R2), `7c5ab404` (CHARC A-R2) | R2-01 (a) session class gains `-`, `.5`; R2-02 AL2-12; R2-03 SQL half = D65 post-merge; R2-04 (a) reorder + recheck |
| A-R3 | 16 | `a0664294` R2-01, `81a94710` AL2-12, `d154584e` R2-04, `a305fa4c` R3-03 | round 3 counted, 701,364, **NOT clean**; R3-01/02 routed |

Every ruling transcribed byte-for-byte with `scratchpad/transcribe.py` (mail body after front matter, each line asserted present, `> ` the only added byte), and each landed path posted back. **Spend: 2,075,967 over three counted rounds.**

## 3. WHAT IS NEXT, IN ORDER

1. **Drain the inbox: the A-R3 packet** (`comms/*/inbox/20260923T103621Z-...`, gate row A-R3 @ `da87480b`). RD PRIMARY on R3-01 (the four attestation constants never compared at replay -- cell rec (a) compare) and R3-02 (`committer_instant` is NOT drifting for a fixed sha, E-15's premise false; A2-86 locks the forged ADMIT -- cell rec (a) compare via `.isoformat()`). CHARC PRIMARY on item 3 (the cell added a required `replayed_row_ids` field + `recheck()` to `Tier2CohortRead`). Transcribe each ruling into the exec ledger (`transcribe.py <mail> <header-file>`), commit pathspec-only, post the path back.
2. **Decide the post-round-3 path -- yours, in writing, in the ledger.** Round 3 was the last counted round. Options per the recipe §3: (a) write a **fourth-round authorization naming the task-bearing finding** (R3-01/R3-02 encodings are task-bearing; read the new cell's depth first), or (b) an **uncounted self-sweep (SS-N)** of the whole class "a stored value with exactly one legitimate source, never compared at replay" -- cell 16 already read all 29 blob keys and found exactly five -- followed by ONE confirming round on the settled artifact. My lean: (b), because R3-01/02 are the same class as R1-01 found a third time; a sweep closes the class by search rather than buying it a round at a time. Either way a FRESH cell (cell 16 ended at 369,490) encodes the rulings red-first first.
3. **At convergence, the cell also fixes** R1-03 (ref age re-anchored at `_rung9_tier2_escape`, not the builder), R1-05 (`resolve_remote_ref` first; `ReplayVerdict.remote_ref_age_seconds`, shown in the CLI), R2-05 (the "evidence was not consulted" message after rung 9 passed, `cohort_provenance_correction.py` ~:1957 -- needs a "rung 9 passed" signal on `LatchedProvenance` refusals; a shape change under its `__post_init__`, may need CHARC), then the FULL fast suite on the final head.
4. Then the prior handoff's steps 2-6 stand unchanged: **Reviewer B at your gate** (the nine recorded deviations in the Task 12 record, plus the A-loop's rulings), **RD's merge-blocking measurement gate**, **merge `--no-ff`** + `schema_manifest.py --write` on the merged head + the merged-head suite at `xhigh`, **the witness** (plan section 9 + the FK-orphan step per `5fcb6b1c`; OPERATOR-EXECUTED; **09-30 hard stop; no witness 10-03..10-20**), then teardown.

## 4. AUTHORITIES GRANTED BY CELL MESSAGE

One, now spent: cell 15 received a mid-run SCOPE CHANGE by message (encode A-R1 item 2 as its second commit before round 2, per CHARC's A-R1-SHAPE point 4). It did so (`994658fc`) and is recorded in gate row A-R2. Nothing open.

## 5. QUEUE (not done)

- Everything in the prior handoff's section 5 still stands (the FK instrument, N1, the stale TWO-backups gotcha, `_is_head`, the em-dash, the stale in-flight section of `orchestrator-context.md`, 22-B's operator go/no-go).
- **D65** (CHARC's register, `19cd5c89`): the 0039 content-belt rider (a `seconds > 0` sign per segment + `instr(quoted_text, char(0)) = 0`), post-merge, its own A round.
- `a0664294`'s body miscounts `_criterion3`'s calls (four vs five listed) -- past the tip, RECORDED in the A-R3 row, never rewritten.

## 6. WHAT WILL BITE YOU

- **Standing authorization** (`docs/phase22-arc-a2-commissioning-brief.md` line 3 @ `78a395ed`): "We will execute these in order without needing additional permissions unless I say otherwise." Reviewer A, B and the merge need no fresh go. It does NOT cover a scope change.
- **Never write ledger rows with escapes through a bash heredoc.** My first A-R2 row broke across lines on `\\n` inside a heredoc'd Python string; I reverted the uncommitted edit and re-wrote it. Write the row to a scratch file with the Write tool, then insert it with a script that asserts `'\n' not in row` and inserts after the named previous row (`| A-R<N> |`). The gate table ends before `## G1 record`, not before the first RULING section.
- **Cells run the loop fine at `opus-high`, ~320-370K per round.** Plan one fresh cell per round; resuming a cell past ~330K for another round crosses the cap.
- **The runner that works** (three rounds): `codex exec -p strong -s read-only --skip-git-repo-check`, cwd = the worktree, prompt on stdin, diff from a WSL `$HOME` path, runner LF-only with literal paths, invoked `wsl.exe bash -c "bash /mnt/c/.../run_rN.sh"`. Working files: this session's scratchpad `loop/` (`C:/Users/rwsmy/AppData/Local/Temp/claude/C--Users-rwsmy-swing-trading/7a4e5079-7c80-4b6a-9755-fcb3a7432d5d/scratchpad/loop/`); prior rounds' WSL files in `~/rev-22a2-prior/`, round 3's in `~/rev-22a2/`. Durable evidence: `~/swing-data/review-transcripts/22-a2-exec/`.
- **Director rulings often carry a paraphrased incidental fact** (this sitting: `DERIVATION_RULE_HISTORY` for `FROZEN_VALUE_EVIDENCE_HISTORY`; "the replayed set" that did not exist). Cells caught both; keep the "the ruling named X; the code has Y" line in every encoding prompt.
- Every prior section-6 item still applies (`-n 4` for the full suite, no stash, no `git checkout <sha>` in the exec worktree, `--only --` pathspec ledger commits, `--body-file` always, cd to main in the same invocation, verify delivery on disk).
