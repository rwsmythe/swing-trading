# phase3e-todo Phase-14-close Scrub -- Audit Record (2026-06-02)

**What this is:** the durable record of the Phase-14-close scrub of `docs/phase3e-todo.md`
+ `docs/phase3e-todo-archive.md`, performed 2026-06-02 at HEAD `420b0ff` (operator-requested,
"very thorough scrub of both the live file and the archive"). Supersedes the earlier
`phase3e-todo-scrub-inventory-20260530.md` (an untracked pre-scrub open-list that was swept
in the Phase-14-close branch/scratch cleanup). This file is git-tracked.

---

## Outcome

| File | Before | After |
|---|---|---|
| `docs/phase3e-todo.md` (live) | 6050 lines | 126 lines |
| `docs/phase3e-todo-archive.md` | 1371 lines | 7355 lines |

The live file was scrubbed to a **forward-looking shape**: header + 3 archive-companion notes
+ a curated **"Standing Open Backlog"** + the `#19` PHASE 14 CLOSED record + the `#5`
Phase-15/close-out punch-list. Every other dated SHIPPED section (Phase 14 per-cycle records
`#1`-`#4` / `#6`-`#18` + every pre-Phase-14 section back to the oldest 2026-04 backlog)
migrated **byte-exact** to the archive's "Appended 2026-06-02 Phase 14-close scrub" section.
5,976 lines migrated; ZERO content reproduced by hand (sliced via a one-shot script with
anchor-asserts).

## Method

1. Re-anchored to current reality (the prior inventory was 3 days + several merges stale):
   read the new top entries (`#19` close record + `#5` punch-list), the documented retention
   discipline (`orchestrator-context.md` Sec "Maintenance: retention discipline"), and the
   archive structure.
2. Read every open-item-bearing section in the bottom ~3000 lines verbatim (backlog sections
   + research next-arc clusters + the V2.G / P14.N / T4.SB scope sections).
3. **Verify-then-close straggler sweep** against the actual codebase (see below).
4. Byte-exact migration: KEEP = header + `#19` + `#5`; ARCHIVE = everything else.
5. Authored the curated Standing Open Backlog from the surviving-open set.
6. Verified: line counts, `## ` header inventory, ASCII-clean new content (gotcha #32; the
   only non-ASCII in the live file is in preserved companion notes + the `#19`/`#5` blocks),
   sentinel removed, archive seam intact.

## Straggler verifications (CLOSED -- shipped without being marked)

The thorough sweep confirmed several long-standing "open" items had actually shipped. Each
checked against the codebase at `420b0ff`; all CLOSED (NOT carried into the Standing Open Backlog):

| Item | Evidence |
|---|---|
| `warnings_json` silent-skip visibility (gotcha #27) | SHIPPED SB2 FB-N6 -- `runner.py:1541-1544` emits the empty-pool audit entry |
| sector/industry tamper hardening | SHIPPED Phase 9 -- `trades.py` cached_sector/industry + `sector_tamper` discrepancy on reject |
| `_bulz_*` -> general rename (A-4) | SHIPPED -- `_rr_target_price` / `_draw_risk_reward_zones` in `charts.py:638,731` (no `_bulz_` left) |
| 3e.9 market-weather chart | SHIPPED -- `render_market_weather_svg` (`charts.py:783`) |
| cleanup-script `-DeregisterFirst` | SHIPPED -- `cleanup-locked-scratch-dirs.ps1` |
| pytest-xdist baseline | SHIPPED -- `pyproject.toml` `addopts = "... -n auto"` |
| E501 ruff residual | CLOSED -- `ruff check swing/` = "All checks passed!" |
| trade-exit "Phase 7 will auto-derive" promise | FULFILLED -- now real display-only auto-derivation (`trade_entry_form.html.j2:151-156`) |

## Surviving open backlog (now in the live file's "Standing Open Backlog")

Organized A-E in the live file. Headline: **A = Phase 15** (schwabdev v3+Fernet, B-7, process-grade
chart redesign, Sec 9.1 Q6 integration review, B-1..B-8 applied-research set). **B = older standalone**
(Schwab Phase B/C, Sec 8.4 Corporate_Actions, inception-CSV ingestion, equity-snapshot semantics,
Minervini review, chart-scope v3, earnings-proximity study, chart-pattern-detection-v2). **C = gated**
(fractional-share, entry_date datetime). **D = low-priority cleanups** (TOS-recon-depth [mostly subsumed],
Tranche B-ops/C residuals, 2026-04 follow-up clusters, flag-v1 V2+ ideas, misc). **E = process/hygiene
debt** (27 Sec VII.F amendments, exec-mode policy, ruff-baseline doc refresh, `reference/Books/` tracking,
3e.8 gated advisories + V2 composer extraction).

## Notes for the next scrub

- The retention discipline's one-phase-cooldown rule says don't archive the just-shipped phase;
  operator chose to compact Phase 14 now anyway (the `#19` record summarizes `#1`-`#18`, and full
  history is in git + the archive). Phase 15's per-cycle records will accrue at the top again;
  re-scrub at Phase 15 close.
- Archive is 7355 lines. The Sec "Archive-split trigger" reconsiders hierarchical decomposition
  at ~80k tokens/file; not yet hit, but trending. Watch at the next close.
- Line numbers in the Standing Open Backlog's archive pointers are intentionally absent (they
  drift); grep the archive by section title / date instead.
