# Orchestrator handoff — 2026-09-15 (morning HST) — D32+D50 and D57 merged; F4 step (b) is next

**Supersedes** `orchestrator-handoff-2026-09-14-d53-d53-1-riders-merged.md`.
**From:** the generation launched 2026-09-14 ~18:23 HST (session `561a00a5`, map name `orchestrator-20260914-1823`).
**Rolled at:** ~470K (`cell_depth --sessions --live 1` read 467,288 before the last steps), past the 400K trigger, at a clean
boundary the operator chose ("do step a first", then roll). **Precondition met: NO CELL IN FLIGHT** (`cell_depth --live 1`:
nothing written in the last hour; no worktree but main).
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact below was re-derived from disk at write time. Re-derive; do not carry these numbers.**

---

## 1. STATE

- **`main` @ `caf58d0c` (plus this handoff commit), 111 commits AHEAD of origin, UNPUSHED.** Push never authorized — ask.
  Before any push: `git log --format='%(trailers:key=Co-Authored-By,valueonly)' origin/main..HEAD` → 0 lines (it was 0 at
  `a3b2f90c`). One commit in range, `cc24f716`, has a NON-Co-Authored-By trailer parse (final paragraph `R-1: …`) —
  CHARC-ruled RECORD-NOT-REWRITE; it does not touch the key audit.
- Tree clean except the untracked coa-chess finding `docs/cli-autoupdate-run-poisoning-finding-coa.md` (not ours).
- **Live DB:** schema v38; last pipeline run 176 (2026-09-14). `swing web` on 8080 is pid 34744, started 06:14 HST
  2026-09-15 on main code that PREDATES the D32+D50 merge — harmless (no schema change; db-migrate is not a web path).
- **Merged-head suite `a3b2f90c`: 12,456 passed / 13 skipped / 0 failed** (this seat, `-n 4` — standing per D52 as amended).
  D57's merged head `c8279a93`: 12,376 passed.

## 2. WHAT THIS GENERATION DID — all merged, all return reports posted and ACCEPTED

| Arc | Merge | Cells | Gates | Notes |
|---|---|---|---|---|
| **D32+D50** backup gates | `a3b2f90c` | executing opus-high (ended 427,685, over cap, disclosed) · fix leg sonnet-high ×2 passes · class sweep + closing pass sonnet-high | round-0 census → CHARC ruling (6 items); A converged R2; **B four reads** → B1 banked **D58**, B-gate ruling, then CHARC **STOP RULE** (allowlist twin predicate, no more Codex); **witness on copies, 5 steps with the operator, PASS** | CHARC ACCEPTED (`ff9e5e5c`): **D50 CLOSED; D32 closes on 22-B's first real migration.** RD disposition QA PASS (`608d068d`). Ledger `docs/phase22-arc-d32-d50-ledger.md`. Evidence `~/swing-data/review-transcripts/d32-d50-exec/` (+ `witness/`). |
| **D57** wake-cue rider | `c8279a93` | sonnet-high | QA on disk; no Codex (declared) | CHARC ACCEPTED. **Closes on the §4 witness at a fresh launch — YOUR launch is that fresh launch (see §5).** |

Spend D32+D50: A 673,705; B 560,446 (from transcript footers; ledger merge record).

## 3. AUTHORITIES GRANTED BY CELL MESSAGE (state, not history)

All cells finished; no grant is open. Record: D32+D50 fix leg — (1) second pass for B2R-1..5 under the ruled B2/B3
requirements; class-sweep cell — (2) the CLOSING PASS under CHARC's stop rule. Both fyi'd to CHARC before acting.

## 4. QUEUE — owners named

1. **F4 disposition step (b) — ORCHESTRATOR + OPERATOR, the operator's next sitting.** Step (a) is DONE (`caf58d0c`: 31 root
   pre-images + 6 sidecars moved to `~/swing-data/backups/pre-images/`, each sha256-verified). Step (b): the **21 CLI copies
   with a positive twin** in `~/swing-data/review-transcripts/d32-d50-exec/witness/inventory.tsv` (rows whose `twin` column is a
   path; RD lists tsv rows 46, 47, 49, 50, 52-68). **ONE PAIR AT A TIME:** re-hash BOTH files and check both for
   `-wal`/`-journal`, print that into the ledger beside the delete, then the OPERATOR runs the single `Remove-Item` (`!`
   prefix). **The twin column names the gate at its OLD root path — the gate now lives under `backups/pre-images/` with the
   same filename.** (c) KEEP everything else, incl. the 3 withheld twins (`swing-20260813T055901.db`,
   `swing-20260902T000318.db`, `swing-20260908T222007.db` — true twins, 0-byte `-wal`; RD: no hand override, freeing them
   is a CHARC-ruled follow-on). Outside the inventory, operator's call: `swing-CORRUPTED-post-phase7-migration-20260505T162747Z.db`
   and the orphan `s9step0-copy.db-wal` in the root.
2. **D53.1 close check — CHARC closes, RD reads — run 177, 2026-09-15 17:30 HST** (non-zero DBW rows carry
   `window_start_date == evidence.trough_1_date`). It has NOT run yet at write time.
3. **D56 — ORCHESTRATOR, next dispatch.** Pattern-review form's 4xx fragment replaces the form; fix = error region + C3
   (pre-fill the DBW correction start with trough 1). CHARC register `637d12fc`. Round-0 census before the cell.
4. **Tiny riders on MY queue:** (i) `scripts/cell_depth.py --sessions` prints each session's Claude Code build (CHARC,
   wake-on-mail-cost ruling); (ii) the non-ASCII em-dash in `swing/cli.py`'s pre-18 WARN line (banked; ride the next cli.py
   touch).
5. **CLAUDE.md gotcha "`swing db-migrate` writes TWO backups, not one" is now FALSE** (one backup, in `backups_dir`, echoed;
   none at HEAD). CHARC's acceptance says "yours to retire at the Gotchas compression" — owner ambiguous (the compression is
   CHARC's lane); confirm with CHARC before editing. Gotchas sit at the ~55K cap.
6. **`docs/orchestrator-context.md` lines ~146-148 are CORRUPTED:** the archived-decisions table body is a literal `__ROWS__`
   placeholder followed by a raw Python string dump. Not fixed this generation. Housekeeping.
7. CHARC's register: D55 (false-green DBW clipping test), D58 (fenced migration lock), D42 half (2); then B-2,
   `ReservedJournalFieldError`'s bare base, D46, D45, D44/D47, D39.

## 5. WHAT WILL BITE YOU

- **THE WAKE CUE CHANGED (D57, merged).** Do NOT arm an inbox Monitor. After EVERY `role_mail post`, run the `ping ->` line
  it prints (one SendMessage per recipient, exact name from `comms/.sessions.json`). The directors' CURRENT names at write
  time: `director-charc-20260914-1826`, `director-rd-20260914-1932` (pre-D57 names; they change when those seats roll).
  **Your launch is D57's §4 witness opportunity:** your name should print as `swing-orchestrator-<stamp>`; CHARC closes D57
  on steps (1)-(4) of the brief §4 — tell CHARC your printed name so a director can ping you and read the wake from your
  transcript.
- **Git Bash mangles `/mnt/c/...` for `wsl.exe`** (the first B launch was a silent exit-127, zero-byte transcript). Launch
  WSL runners from **PowerShell**: `wsl.exe bash /mnt/c/.../run.sh`. Runner scripts via `printf '%s\n'` (LF).
- **Python 3.14 on this box: `Path.exists()/is_dir()/is_file()` resolve to native builtins that return False on ANY error
  and bypass a monkeypatched `os.stat`/`Path.stat`** (measured by the sweep cell). A test that patches `Path.stat` to prove a
  probe fails closed will pass vacuously.
- **A review loop that finds a new ROUTE to the same failure each round is a DENYLIST problem** — CHARC's stop rule on
  D32+D50: turn the positive into an allowlist predicate with a per-clause test table, then stop reviewing. Recognise it at
  round 3, not round 5.
- **This seat's slips:** (1) typed a guessed token figure into a ledger before reading the footer (caught and corrected
  before commit) — read the number, then write it; (2) my first worktree `cd` in Bash persisted, and `role_mail` must always
  run from the MAIN repo — keep the `cd` in the same invocation.
- **Stash stack is shared across worktrees and holds one unrelated 2026-05-31 entry — never pop it.**
- Everything in the two prior handoffs' §5 still applies (cp1252 both sides, `-n auto` memory-killed, dotfile evidence,
  `role_mail` `--body-file` / cd main / verify on disk).

**The admitting gate stays open. Re-derive candidate and A+ counts before quoting them.**
