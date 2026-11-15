# Orchestrator handoff -- 2026-11-15 -- SG closed live; Codex lane witnessed; the entry-form rider MERGED, its browser witness owed

**Supersedes:** `orchestrator-handoff-2026-11-12-sg-round2.md`.

**From:** session `c3c14ea5` (Opus 5.5), online 2026-11-12 01:01Z, rolling past 400K self-read. **Re-derive every fact below at HEAD and on disk before acting on it.**

## 1. STANDING GRANT (STATE, unchanged)

- **Operator, 2026-11-11, verbatim:** "Execute the work you have been authorized to perform by CHARC, including pushing, send CHARC your recommended items that do not yet have authorization." It covers dispatch, merge and push on CHARC's dispatches and gates. NOT operator config. NOT a live migration (his witnessed step).
- **CHARC dispatch `20261115T023210Z` (msg-id `97b3fbd92a407e92`), on the operator's own words in CHARC's pane, verbatim:** "Entry-form rider: commission the rider; a2_77 rename: proceed; it was acceptable for CHARC to authorize the launcher rider; perform the register touch as briefed". The entry-form rider runs under it (brief `docs/phase22-rider-entry-form-dispatch-brief.md` @ `2f185264`).

**Authorities I granted by cell message (STATE):** the entry-form rider cell was told three counted Reviewer A rounds is the default and a fourth needs my written authorization naming the task-bearing finding. It converged at round 1; nothing else was granted.

## 2. DONE THIS GENERATION

- **SG label arc (D102/D103/D104 + D86): MERGED, LIVE, WITNESSED.** R2-2 fixed service-side (`fc5f8374`), R2-1 banked on D65 (CHARC). Reviewer B: attempt 1 void (no verdict), B1 + B2 clean with repo reads. CHARC's gate PASSED at `7e17a83c` (he rebuilt v42 vs live, ran T5 on a live copy). `git merge --no-ff 7e17a83c` -> `ce7a61a7` (tree `8471fa30`), merged-head 16252/13/0. **Operator sitting 2026-11-14:** lock probe OK -> `swing db-migrate` (backup `swing-pre-sg-label-migration-20261114T233229Z.db`) -> **live schema 42** -> T5 dry run -> **provenance correction 3 on trade 29** (`watch_fire_relabel` / `last_fire`, candidate 15901, eval 193). **RD's witness PASSED** (wording: five trades carry H2; the CLOSED tally stays 4 of 10 until SG closes). Every ruling block-quoted in `docs/superpowers/plans/2026-11-11-sg-label-correction.ledger.md`. CHARC closed the rows at `6b58e980`. Worktree removed; branch `sg-label` kept.
- **Codex-lane operator witness: PASSED** (turn, commit `d9e98547` with the model footer, review `NO_NEW_CRITICAL_MAJOR`, both usage readouts). **CHARC gate item 4 FIRED:** the review tool-set stability test fails in the sandbox (MSYS `grep.exe`, `CreateFileMapping ... Win32 error 5`) and passes at the seat; added to the agent file's residue list (`d9b59d1f`). Record: `~/swing-data/review-transcripts/codex-lane/build-ledger.md` section "Operator witness". Scratch worktree + branch removed.
- **a2_77 rename rider: DONE** `8f35f21c` (own commit; composition pin re-keyed, third reason), suite 16252/13/0, pushed.
- **Pushed through `8f35f21c`** (includes CHARC `8d3a3640`, `6b58e980`, `2f185264` and RD's watch-standard v2.6 `23d85a49`).

## 3. THE ENTRY-FORM RIDER (D47 companion + D97 + D98) -- MERGED `8aa72d1d`, pushed; the operator's browser witness is YOUR FIRST ACT

- Branch `entry-form-rider` @ `49219b63` KEPT; worktree REMOVED. `git merge --no-ff 49219b63` -> `8aa72d1d` (tree `86a93b7c` = the branch tree). Merged-head suite **16284 / 13 / 0, EXIT=0**; the SG route tests explicitly on the merged head 82 passed. Evidence: `~/swing-data/review-transcripts/entry-form-rider/` (incl. `copowers-findings-worktree-final.md`).
- Commits: `04c2d6a8` D97, `e3926c10` D47 companion, `641b372e` D98, `49219b63` R1-1 minor (overflow -> unsized, never a 500).
- **QA'd by me against disk:** scope swing/web + tests only; floor via `sizing_equity(..., floor=cfg.account.risk_equity_floor)` (same spelling as `runner.py:1763`); stash list clean; Reviewer A round 1 five assertions pass (gpt-6.1-sol/high, ERROR 0, footer 187,533, NO_NEW_CRITICAL_MAJOR, prompt tokens 0); depth 334,262 filled; suites 16283/13/0 (pre-review) and 16284/13/0 (final, `49219b63`).
- **Live shape (the cell's read, mode=ro):** floor 7500.0; real equity 2891.25 -> D97 is LIVE (form today states 14.46, floored budget 37.50). Live `trades` count 29 (witness step 4 baseline).
- **Deviations to carry to CHARC with the merge report:** 16 call sites, not 15; `EntryFormSizing` dataclass; finite-geometry + `ArithmeticError` guard; `emo_clean` moved to the top of `entry_post`; three pinned-unfloored tests re-expected with worked values (listed in the cell's report, saved in the ledger copy).
- **Reviewer A R1-3 (minor, PRE-EXISTING, new to the register):** `sizing_hint.html.j2` renders its span without `hx-*` attributes while the form's span swaps `outerHTML`, so the live hint refreshes once then never again. POSTED to CHARC to bank (suggested: the web-surface sweep beside R1-2, the `:98` htmx SyntaxError). His disposition is pending.
- **Reviewer B (mine):** attempt 1 VOID -- the model wrote it could not complete ("the environment is read-only") yet printed the clean token; 3 reads, all succeeded. Attempt 2 (prompt: reads work; an incomplete review emits NO token): gpt-6-luna/medium, ^ERROR 0, footer 59,749, NO_NEW_CRITICAL_MAJOR, 15 exec blocks, final message covers points (1)-(6). Flagged to CHARC as a new failure shape the anchored-token assertion cannot see: READ B's final message, always.
- **Merge report posted** to CHARC + RD (`20261115T040418Z`), with the deviations and R1-3.
- **THE WITNESS (brief section 5), one step per message, unseeded default state:** (1) entry form for a watchlist ticker: its risk figure agrees with the latch card / nightly on the FLOORED budget (37.50 at today's equity); (2) fill the pre-trade answers, blank the rationale, submit: error AND every answer still filled; (3) on that form the suggested max and risk line match the prices shown; (4) cancel; `trades` count still **29** (`mode=ro`). `swing web` was restarted 2026-11-14 BEFORE this merge, so it runs pre-rider code: the operator restarts it first (stop, verify port 8080 free, start).

## 4. QUEUED
- The entry-form rider's browser witness (section 3), then its record in a short ledger note and the close status to CHARC + RD.
- CHARC's banked minor: `cli.py:3671/:3969/:3989/:3629/:3617` compare against string literals, not the models constants (next `cli.py` touch).
- `codex_cell.py`: count only a `succeeded in` line that closes an exec block. `research_health.py` YELLOW tail spacing.

## 5. STATE AT ROLL

- **No cell in flight; no background job.** Worktrees: none besides main. Main = origin at the handoff commit.
- Inbox empty at roll. CHARC's live seat: `swing-charc-20261114-1340`; RD: `swing-rd-20261111-1052` (read `comms/.sessions.json`, never guess).
- Orchestrator depth at roll: ~416K (self-read via the UserPromptSubmit ctx line; `cell_depth.py --sessions --live 1` read 377K before the rider dispatch).
- Lessons this generation, banked here for the next context-doc touch: (a) never pipe `role_mail read --all` through `head` -- it acks what you did not read (recovered from `read/`); (b) a Codex B pass over a 337 KB diff cat-ed whole files and abstained -- split into halves, give slice-reading rules and name the files; (c) a B pass can abstain in words AND print the clean token -- read the final message.

## 6. WATCHES
- The first real auto-filled entry on a flagged ticker (D84 live-emitter watch).
- The first live risk-flagged A+ (RD). SXC was A+ on eval 199 (no trade).
- The first nightly on v42 is Monday 2026-11-16's run.
