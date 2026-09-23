# Orchestrator handoff — 2026-09-23 — 22-A2 EXECUTING through G-T9F (Tasks 7-9 + four ruling units done); Task 10 is the successor's first dispatch

**Supersedes** `orchestrator-handoff-2026-09-23-22a2-exec-mid-flight.md`.
**From:** the generation launched 2026-09-23 ~02:14Z (session `4b561058`, Opus 5.5, build 2.1.280, seat `swing-orchestrator-20260922-1614`).
**Rolled at:** 341,135 (`cell_depth.py --sessions --live 1`), under the 400K trigger, at a clean gate. The next task (~130K cell + QA) would have crossed it.
**Precondition met:** no cell in flight. Cells 5-9 have all returned and die with this session; nothing of theirs is uncommitted (each gate verified `git status` clean).

**Re-derive every fact below; do not carry the numbers.**

---

## 1. STATE

- **`main` @ `3d657bd4`** (my context-doc fix) on top of CHARC's `c2ba1cd6` (D60). **Origin is at `6e87ad37`**: the operator pushed through the rider and CHARC's state row. Everything after that is unpushed. The auto-mode classifier blocks `git push` from this seat; hand the operator `! git push origin main`.
- Last merged-head suite on main: **`d7b93e5a` (the launcher rider), 12,493 passed / 13 skipped / 0 failed** (`-n 4`, read from the tail by me). Everything on main since is docs-only.
- Live DB **v38**, untouched this sitting.
- **Worktrees:** `.worktrees/22-a2-exec` (THE LIVE ARC, branch head `b6903a0a`) and `.worktrees/22-a2-plan` (KEEP until 22-A2 merges; then tear down with the sha256 reconciliation against `~/swing-data/review-transcripts/22-a2-plan/`). I tore down `launcher-color-scrub` and `d51b-comment-norm`, each after `merge-base --is-ancestor` proved containment.
- The stash holds exactly one entry (`435a4d1c`, 2026-05-31 quarantine). Never pop it.

## 2. WHAT THIS GENERATION DID

| Item | Result |
|---|---|
| Launcher color-scrub rider (CHARC brief `274255c0`) | sonnet-high cell, red-first; ff-merged `d7b93e5a`; merged-head 12,493/13/0; CHARC QA PASSED by execution; worktree torn down. **Closes on the §3 witness at the first post-rider rollover — THIS ONE.** The successor's pane should render colors, and `! $env:NO_COLOR` should print empty. Report it to CHARC. |
| 22-A2 Task 7 (service wiring) | cell 5, `91b3f194`, 5076/9/0 |
| 22-A2 Task 8 (CLI) | cell 6, `2f4b47f0`, 5082/9/0 |
| G-T7 follow-on (CHARC Q1 + Q2) | cell 6, `ee157a28`, 5088/9/0. **I reworded the tip** (`889e5e72` had a parsed `Q1:` trailer; nothing cited it; tree byte-identical). `889e5e72` is unreachable; never cite it. |
| 22-A2 Task 9 (replay) | cell 7, `9f175d2e`, 5106/9/0 |
| G-T7F + AMEND encoding | cell 8, `abcbd632`, 5127/9/0; fixture still 4/4 pairs, zero deletions |
| G-T9 item 2 + G-T7FE-B pins | cell 9, `112202cb`, 5135/9/0; derivation version `.3` APPENDED |
| Context doc | `3d657bd4`: directors start at Fable 5.1 / **medium** (ruled 09-13), not high |

Rulings landed this sitting, all byte-for-byte in the exec ledger, each courier-posted back: **G-T7 Q1+Q2** (CHARC) `535b457f` · **G-T7F** (CHARC) `5d90965a` · **G-T7F-AMEND** (CHARC, superseding on RD's dissent) `4ce42959` · **G-T9** (CHARC) `5c14cbf0` · **G-T7FE-B** (RD) `d3cbef5a` · **G-T7FE-A+C** (CHARC) `29da90db`.

## 3. 22-A2 EXECUTING — WHERE IT STANDS

- **Exec ledger (THE record; read it in full first):** `docs/superpowers/plans/2026-09-22-phase22-arc-a2-proof-machinery.exec-ledger.md` on `22-a2-exec`. The gate table runs G1..G-T9F with every depth reading. Eleven landed rulings sit below it. **Where the plan and a ruling differ, the ruling governs.** Plan sections 1-2 (the 28-key roster, the vocabulary) do NOT yet show the grammar/derivation split; the rulings do.
- **Done:** Tasks 1-9, plus the follow-ons F2.I-NEG/G-NEG/G-U1, G-T7 Q1+Q2, G-T7F+AMEND, and G-T9 item 2 + G-T7FE-B.
- **NEXT: Task 10** (the four cohort readers, A2-91..A2-97c), with **G-T7FE-A+C item C folded in**:
  - `tier2_cohort_exclusions` returns the named frozen dataclass `Tier2CohortRead(exclusions, observations)`.
  - Each reader COUNTS from `exclusions` only and RENDERS both.
  - Per reader, add the two discriminators: an admitted row with a moved derivation version leaves N unchanged and renders the observation line; the zero-data state renders neither line.
  - A2-75 pins `tier2_cohort_exclusions`' callers to exactly the four P35 readers.
  - Dispatch a FRESH `implementer-opus-high` off `b6903a0a`. Use the same dispatch shape as cells 5-9: targeted reading, STRICTLY red-first, one task per unit, STOP at the gate. Include the commit-message trailer hazard paragraph and the digest check.
  - **Digest check for the next cell:** if a change edits the BEHAVIOUR of any of the 100 closure members, the pin test goes red. The ruled response is to APPEND a new `(version, digest)` pair and move `FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION`. Never re-seed or edit an entry. Trade 25's blob literal (`tests/fixtures/tier2/trade25_seventh_blob.json`) moves with it.
- **Then:** Task 11 (acceptance + the live-copy dry run on a `sqlite3.backup()` copy), Task 12 (close-out), G3 (the first full fast suite, `-n 4`), Reviewer A at `strong` to convergence, Reviewer B at your gate, the merged-head suite, then the operator witness.
- **NOTHING is open with the directors.** G-T9F note 1 was RULED (a) by CHARC before I rolled: `resolve_remote_ref` stays outside the digest. I landed it at `b6903a0a` on the branch and posted the path back; no encoding is owed. **Branch head is now `b6903a0a`**, so dispatch Task 10 off it.
- **Recorded deviations for Reviewer B to weigh:**
  - Task 5's tests were written after its code (RD accepted it for that task).
  - One G-T7FE-B pin was written post-implementation (RD accepted it on its mutation check).
  - The six first-run pins at G-T9F were proved by mutation, not by a red run.
- **Encodings owed to Task 12's record:** every gate row's "notes carried" (G1, G-T4..G-T9F).
- **Witness (plan section 9):** OPERATOR-EXECUTED, ORCHESTRATOR-SCRIPTED, one step per result. **09-30 hard stop. No witness 10-03..10-20.**
- **At merge:** `--no-ff` (the ledgers cite branch SHAs). Re-run `python scripts/schema_manifest.py --write` on the merged head; the gate reads four changed pairs, zero deletions.

## 4. AUTHORITIES GRANTED BY CELL MESSAGE

- None open. Every cell grant ended at its gate. Scope changes sent to cells 7, 8 and 9 mid-unit are recorded in the ledger rows they produced.

## 5. QUEUE (mine, not done)

- The D51 paired CLAUDE.md gotcha plus the §Gotchas compression pass. The "`swing db-migrate` writes TWO backups" gotcha is FALSE since D32.
- The `_is_head` rename rider (its own commit); the em-dash in `swing/cli.py`'s pre-18 WARN line.
- `orchestrator-context.md` §"Currently in-flight work" is stale: it still describes D56 as the latest state. Rewrite it at a clean boundary.
- 22-B: CHARC's brief `74c15b77` is NOT dispatched. The go/no-go is the OPERATOR's at 22-A2's landing.

## 6. WHAT WILL BITE YOU

- **Ping names:** CHARC `swing-charc-20260915-1803`, **at 600K (over his cap) at my last reading**, so he may roll; RD `swing-rd-20260922-1232`. Trust the `ping ->` line.
- **`role_mail` subjects cap at 80 chars; there is no `--cc` flag.** For a per-item packet, name each item's PRIMARY in the body and `--to` both seats.
- **A cell's scope change reaches it at its next tool round** (SendMessage). Rulings landing mid-unit happened three times this sitting. Route them to the running cell immediately when they touch its code, or it encodes the superseded text.
- **Rulings compose, and they supersede.** G-T7F-AMEND reversed half of G-T7F within four minutes on RD's dissent. Read the whole ruling tail of the ledger, not only the section whose name you expect.
- **The cell shares your worktree:** `git commit --only -- <ledger>`; never `git add`.
- Every prior section-6 item still applies: `-n 4` for the full suite; `--body-file`, cd to main, verify on disk; byte-for-byte transcription by script; no stash; cp1252 on both the encode and the decode side.
