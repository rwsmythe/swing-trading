# Orchestrator handoff — 2026-09-14 — 22-A4 fully closed out; no active arc; queue is housekeeping

**Supersedes** `orchestrator-handoff-2026-09-09-22a4-merged-migration-pending.md`.
**From:** the generation that witnessed the 0038 migration, tore down the 22-A4 worktrees, rewrote the
section-of-record, trimmed `orchestrator-context.md` under its cap, and ran the `_is_head` rider.
**Rolled at:** 530,443 tokens (`cell_depth --sessions --live`) — past the 400K trigger, which this
generation missed; rolled on the operator's word at a clean boundary.
**Precondition met: NO CELL IN FLIGHT.** This generation dispatched no cells.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact below was re-derived from disk at write time. Re-derive; do not carry these numbers.**

---

## 1. STATE

- **`main` @ `4cbba60b`, 15 commits AHEAD of origin, UNPUSHED.** The last push was `e54fa8b0`. The
  range is docs + harness + one tests-only commit (`e8a4d54e`, the rider). **Push is NOT authorized
  by this generation — ask the operator.** Before any push: confirm no `swing/` files in the range,
  and run the trailer audit filtered on the KEY
  (`git log --format='%(trailers:key=Co-Authored-By,valueonly)' origin/main..HEAD` → 0 lines).
- Tree clean except **`docs/cli-autoupdate-run-poisoning-finding-coa.md`** (untracked, a coa-chess
  CHARC delivery, never committed by cross-project convention — not yours to touch).
- One worktree (main). No branches but `main`.
- **Live DB: schema v38**, 28 trades, `attempt_id` non-null **0** — no entry since the migration; the
  first post-migration ENTRY mints the first token.
- **Open trades:** 23 CADL (partial_exited), 24 RHI, 25 OII, 26 NRIX, 28 PBF. Real money.
- **Pipeline:** runs 173 (09-09), 174 (09-10), 175 (09-11) all `complete`; `export_status=failed` on
  every run is **D42**, pre-existing since run 160 — never read it as a regression.
- **No active arc.** The next arc is the operator's to commission.

## 2. WHAT THIS GENERATION DID — all committed

- **0038 live migration, operator-witnessed** in one contiguous attended sitting (W0 · W1 · W1.5 · W2 ·
  W3 · W4 · W5). Run 172 and run 173 both zero new warning classes against the run-171 baseline.
  Both v37 pre-images verified RESTORABLE, not merely present. Recorded in the section-of-record.
- **Four director rulings transcribed** into the 22-A4 ledger (`a3b037a2`), containment-verified.
- **Three gotchas** in CLAUDE.md (`626eba83`): the live-DB-unrunnable-between-merge-and-migration rule
  (an AMENDMENT to the pre-image bullet); prove no DB holder by ACQUIRING THE EXCLUSIVE LOCK;
  `swing db-migrate` writes TWO backups.
- **Worktrees torn down** (both 22-A4 roots and branches), evidence reconciled BY SHA256 against
  `~/swing-data/review-transcripts/` — two real gaps found and copied in before removal.
- **Section-of-record rewritten** (`dbbf52c9`) — it still described 22-A as paused at v36.
- **`orchestrator-context.md` trimmed twice** under the 120,000 probe cap: `c54c865c` (superseded
  phase sections + the 5,298-char line-5 wall) and `f2b58728` (CHARC-ruled, 21 of 25 decision entries
  archived BY OWNER). **Now 112,438 chars, ~7,500 headroom.** The discriminator CHARC ruled — owner or
  completed action archives; reopenable, forward-force, or unowned finding stays — is harness text at
  `aafacbde`.
- **`_is_head` rename rider** (`e8a4d54e`): 20 version-mirror tests → `test_expected_schema_version_is_head`
  / `test_schema_version_row_is_head`. Fast suite on that tree **12,314 passed / 13 skipped / 0 failed
  at `-n 4`** (this seat's evidence, not the operator's binding `-n auto`). Collection IDs verified
  before/after (160→160, 39→39) so no test was shadowed away.

## 3. AUTHORITIES GRANTED BY CELL MESSAGE

**None.** No cells were dispatched, so no envelopes, scope grants, fix authorizations, or round
authorizations exist to inherit.

## 4. QUEUE — owners named

- **CHARC's register, D54:** the stale-name class outside the rider, banked as one sweep —
  `test_account_equity_snapshots_table_exists_with_8_columns` (asserts 10), the `tmp_db_v22` FIXTURE
  (103 references across 9 files), and `test_migration_0019_applies_against_v18_baseline` (no v18
  baseline is ever built). Not yours unless commissioned.
- **CHARC's: the Gotchas cap.** §Gotchas sits ~363 chars under its ~55,000 soft cap; **the next
  gotcha commit carries a compression pass, never a bare append.** It also still says the version-mirror
  class was "~16 such" — the true count was 20. Leave that correction to the compression commit.
- **CHARC's:** D32 pre-images in the swing-data root; the charter §4.2 two-cap-sets reconciliation;
  D53 (the double-bottom-W detector is structurally unfireable in production — awaiting commissioning).
- **B-2** (single-field corrections discard every payload key after the first), `ReservedJournalFieldError`'s
  bare-`Exception` base, D42, then D46, D45, D44/D47, the D39 sweep.

## 5. WHAT WILL BITE YOU

- **The installed `bash.exe` is slow on this box (60–900 ms per open).** A session launched through
  `scripts/start_directors.ps1` gets `CLAUDE_CODE_GIT_BASH_PATH` pointed at a fast copy; prefer
  PowerShell for shell work if you find yourself on the slow path. **Arm wake-on-mail with the glob
  form in your bootstrap** (sleep 10), not the old `ls | wc` form.
- **Rollover act 3 is scoped to YOUR OWN process tree** (`9d01c077`): walk each match's parent chain
  to your own `claude.exe` (found from `$PID`). A match that does not descend from you is not your
  stop failure — report it, never kill it.
- **Watch your own depth.** This generation ran 130K past the 400K trigger without reading it. Read
  `python scripts/cell_depth.py --sessions --live 3` at every clean boundary, not only at dispatch.
- **`role_mail.py` refuses subjects over 80 chars** (nothing written). `--body-file` always; `cd` the
  MAIN repo in the same invocation; verify delivery ON DISK.
- **A heredoc containing prose, or PowerShell quoting inside `python -c`, breaks.** Write the script
  with the Write tool and run the file.
- **cp1252 bites on both sides:** `print()` of a heading containing `→` CRASHES; `text=True` with no
  `encoding=` DECODES as mojibake. Print ASCII-safe; pass `encoding='utf-8'`.
- **`-n auto` is memory-killed in this seat** — use `-n 4`; the binding `-n auto` is the operator's.
- **Bounded searches reported as totals, three times this generation:** a `22.?a4` pattern that cannot
  span `phase22-arc-a4`; bare-number greps (`18.6`, `2.39`) matching Tiingo price CSVs; an anchored
  name regex (`_is_\d+$`) that found 17 of 20. **Sweep by what the code ASSERTS, not by what it is
  NAMED**, and anchor greps over large transcripts.
- **All Codex artifacts are DOTFILES** — `ls -a`, or you will conclude they are missing.

**The admitting gate stays open. Re-derive the post-barrier candidate and A+ counts before quoting them.**
