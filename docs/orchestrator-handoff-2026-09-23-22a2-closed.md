# Orchestrator handoff — 2026-09-23 — 22-A2 MERGED, WITNESSED, CLOSED; the 22-B go/no-go is the operator's

**Supersedes** `orchestrator-handoff-2026-09-23-22a2-reviewer-a-closed.md`.
**From:** the generation launched 2026-09-23 ~14:50Z (session `ea8b1779`, Opus 5.5, build 2.1.280).
**Rolled at:** a self-read of ~370K, under the 400K trigger, on a clean boundary. The arc is closed, no cell is in flight (the only one I dispatched, cell 20, returned and was QA'd), and nothing is open with either director.

**Re-derive every fact below. Do not carry the numbers forward.**

## 1. STATE

- **`main` @ the commit carrying this handoff.** The merge is **`57187164`** (`--no-ff`, parents `b79b1e3a` + `db92d97e`). `origin/main` = `57187164` (the operator pushed). Since then `998cfc37` (the witness record) and this commit are **unpushed**: hand the operator `! git push origin main`, because this seat's push is classifier-blocked.
- **Live DB: schema v39** (migrated at the witness, 16:47Z). Backup: `~/swing-data/backups/swing-pre-22a2-migration-20260923T164738Z.db`, the only one written. Provenance correction **2** is on trade 25 (OII): tier `latch_ladder_tier2`, it replays `ADMIT`, and RD confirmed it off-box. **H1 = 4/20.** Rows 72 and 73 of `reconciliation_discrepancies` have `cash_movement_id` NULLed, and `foreign_key_check` = [].
- **`swing web` was restarted by the operator** on post-merge code; `/` and `/metrics` return 200.
- **No worktrees, no arc branches.** `22-a2-exec` and `22-a2-plan` were removed after a sha256 reconciliation (14/14 SAME); B's evidence lives in `~/swing-data/review-transcripts/22-a2-exec/.reviewer-b-*`. The stash holds the 2026-05-31 quarantine entry; never pop it.
- **Last merged-head suite:** `57187164`, `-n 4`: **12960 passed / 13 skipped / 0 failed**. Ruff is clean, and `schema_manifest.py --check` is clean (and `--db` on live is clean).
- **Directors:** CHARC rolled at 15:32Z; his successor is `swing-charc-20260923-0533`. RD is `swing-rd-20260923-0048`. Trust the `ping ->` line that `role_mail post` prints, never these names.

## 2. WHAT THIS GENERATION DID (the exec ledger now lives on main: `docs/superpowers/plans/2026-09-22-phase22-arc-a2-proof-machinery.exec-ledger.md`, whose last blocks record everything below)

1. **Reviewer B** (charter §2.9; run by THIS seat, not a cell), cold-audit `codex exec -p strong`, cwd = the worktree at `cd06c7ac`. Verdict `NEW_CRITICAL_MAJOR_FOUND`: 3 critical, 2 major, 2 minor.
   - Preparation: A's seven evidence files were moved out of the worktree for the pass, after a sha256 check, and restored afterwards.
   - The prompt, runner and transcript are preserved.
2. **The B ruling packet**, one ruler per item:
   - RD ruled B-01/02/03: AL2-16 was **widened** to "the reader trusts the disk it stands on", which now covers the git executable found on PATH; AL2-15's reason was sharpened; and D65 gains an existing-row audit.
   - CHARC ruled B-04..07: B-04 = D61 post-merge, B-05 declared, B-06 declared under E-7, B-07 banked.
   - No production change resulted.
3. **Cell 20** (`implementer-sonnet-high`) took the H1 reader count on live copies: 3/20 pre-arc and 3/20 on v39. **My brief error, owned:** I put all nine paths in scratch, so the empty prices cache made the trial correction refuse at `aliveness_unverifiable`. The live archives were proven to carry the missing sessions.
4. **RD's measurement gate CLEARED** on `03f9d0e9`, then re-attached to the merged head on three facts. **CHARC's successor cleared the merge gate** after a throwaway merge. The one conflict (`schema_manifest_head.tsv`, the D51b normalization) was resolved by regeneration: 4 rows changed, 0 added, 0 removed.
5. **The merge**, after an exclusive-lock probe at 16:22:58Z. Then **the witness** (W1-W7, operator-executed, one step per result). **RD's step 6 PASSED** off-box, and CHARC **closed 22-A2** at 16:54Z.

## 3. WHAT IS NEXT

1. **The 22-B go/no-go is the OPERATOR's.** On a go, CHARC re-measures the DRAFT brief `docs/phase22-arc-b-commissioning-brief.md` @ `74c15b77` against live v39 and posts the dispatch. Nothing about 22-B is authorized until then. The 22-A2 standing grant is SPENT (its arc is closed).
2. **The post-merge queue** (CHARC's order, for the orchestrator to sequence after 22-B is decided): the D66 `.7` pair (now including the PATH belt and its isolation test), the D65 rider (the four literals plus the existing-row audit), the D62 rider (the FK probe), the D61 unit (the process card's fifth reader), D64, B-07, and 22-A2i.
3. **The orchestrator's own queue (still unlanded):**
   - the **"`swing db-migrate` writes TWO backups" gotcha is FALSE** (third live confirmation today), and belongs in CHARC's Gotchas compression pass;
   - the `_is_head` rename rider;
   - the non-ASCII em-dash in `swing/cli.py`'s WARN line;
   - `cell_depth.py --sessions` printing each session's build;
   - **the stale §"Currently in-flight work" in `docs/orchestrator-context.md`**, which still describes 2026-09-15. Rewrite it at the next close-of-sitting.

## 4. AUTHORITIES GRANTED BY CELL MESSAGE

None. Cell 20 was dispatched with a brief and was not messaged afterwards.

## 5. WHAT WILL BITE YOU

- **Reviewer B is the orchestrator's own Codex run.** The runner shape, with LITERAL paths, LF-only, and run by `wsl.exe bash /mnt/c/...` from PowerShell or with `MSYS_NO_PATHCONV=1` from bash, is in `~/swing-data/review-transcripts/22-a2-exec/run_b.sh`. The prompt splits the verdict tokens so its own echo cannot match.
- **A live-copy cell needs the REAL prices cache** (or a copy of it), not an empty scratch dir. The ladder's aliveness check reads the parquet archive, not `swing.db`.
- **Tier-2 evidence files need the FULL 40-hex sha.** Build them by SELECTION: `~/swing-data/review-transcripts/22-a2-exec/witness_make_evidence.py` is the model.
- **Ledger transcription:** `transcribe.py`-shaped scripts (body after the front matter, each line asserted present, `> ` the only added byte). Post the landed commit back; a ruling is not landed until then.
- All prior section-6 items still apply: `--body-file` always; `cd` to main in the same invocation as a post; verify delivery on disk; ping after every post; `-n 4` for the suite; no paragraph opening with `Word:` in commit messages.
