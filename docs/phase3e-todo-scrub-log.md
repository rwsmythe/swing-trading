# phase3e-todo Scrub Log -- Audit Record

**What this is:** the durable, cumulative record of the phase-close scrubs of
`docs/phase3e-todo.md` + `docs/phase3e-todo-archive.md`. One entry per scrub, newest first.
The repeatable process (operator-requested at each phase close): re-anchor to current HEAD,
read every open-bearing section, **verify-then-close stragglers against the codebase** (close
items that shipped without being marked), byte-exact migrate the dated SHIPPED records to the
archive, rewrite the Standing Open Backlog to a forward-looking shape, preserve any inline
arc narrative that lacks a dated record, ASCII-clean new content (gotcha #32), verify
(counts / content-preservation / seam), commit on main. Git-tracked.

---

## Entry 2 -- Phase-15-close scrub (2026-06-08, HEAD `f892199b`)

**Trigger:** operator "Phase 15 has been closed out ... repeat the same process in anticipation
of commissioning phase 16."

| File | Before | After |
|---|---|---|
| `docs/phase3e-todo.md` (live) | 193 lines | 68 lines |
| `docs/phase3e-todo-archive.md` | 7354 lines | 7508 lines |

**What moved:** all dated records -- the Phase-15 per-arc records `#20`-`#23` + the Phase-14
`#19` CLOSED record + the `#5` close-out punch-list -- migrated byte-exact to the archive's
"Appended 2026-06-08 Phase 15-close scrub" section. The pre-scrub Section A had narrated the
data-integrity arc + its spin-outs (SQLite-lock / fetch-vs-write / daily-mgmt #16 / Issue #3 /
Gate-4 quote cassette / bad-bar accept-and-document) INLINE with no dated `##` record;
that 24-line block was preserved verbatim to the archive ("Phase-15 inline-arc narrative" sub-section)
so the forensic detail stays grep-able.

**Section A rewritten** to a compact Phase-15-CLOSED / Phase-16-ACTIVE pointer + the two
genuinely-new items banked during Phase 15 (see below). Sections B-E carried forward unchanged
from the 2026-06-02 scrub.

**Straggler sweep (CLOSED -- Phase 15 shipped these):** schwabdev v3+Fernet (`#20`, schema
re-anchor `9d05a8f`, the FIRST L2-LOCK re-anchor); B-7 `failure_mode` (`#21`, migration `0024`,
schema v24, `FAILURE_MODES` frozenset present); PGT small-multiples redesign + reviews nav-date
(`#22`); pattern-observation pool widening (`#23`); the whole data-integrity arc + spin-outs
(ext-hours `needExtendedHoursData=False` @marketdata.py:390; busy_timeout=30000 @db.py:54;
fetch-vs-write reorder; #16 fetch-hoist; Issue #3; Gate-4 cassette `56e14988`, Schwab LIVE for
quotes). All verified against the codebase at `f892199b`.

**Surviving Section-A open items (the genuinely-new bankings):**
- **Reconciliation trade-field allowlist** -- `validate_trade_correction` gates only
  `current_stop`/`state`; a tier-3 override can mutate any `trades` column. Own future arc; low priority.
- **Reconciliation/legacy `fill_datetime` normalization gap** -- correction-path fills not
  re-normalized; defended by Issue-#3 test E11, not fixed. `swing/trades/` data-hygiene candidate.

**Where the rest went:** the active phase moved to its own tracker
[`docs/phase16-todo.md`](phase16-todo.md) (Arcs 1-4; opened 2026-06-08); the applied-research
set (B-1..B-8 + the SHIPPED+CLOSED Minervini recall + banked VCP calibration) lives in
`research/phase-0-tasks.md`. Neither is duplicated into phase3e-todo.md -- Section A just points.

**Notes for the next scrub:**
- Sections B-E are now 2 scrubs stale (unchanged since 2026-06-02) -- at the next pass, spot-check
  a few against the codebase in case Phase 16 incidentally closed any (e.g. the logging overhaul
  could touch the ruff-baseline doc-staleness item, or the `cash_movements` work could touch the
  account-equity formalization).
- Archive is 7508 lines. The "Archive-split trigger" reconsiders hierarchical decomposition at
  ~80k tokens/file -- getting closer; evaluate at the Phase-16 close.

---

## Entry 1 -- Phase-14-close scrub (2026-06-02, HEAD `420b0ff`)

**What this was:** the durable record of the Phase-14-close scrub of `docs/phase3e-todo.md`
+ `docs/phase3e-todo-archive.md`, performed 2026-06-02 at HEAD `420b0ff` (operator-requested,
"very thorough scrub of both the live file and the archive"). Superseded the earlier
`phase3e-todo-scrub-inventory-20260530.md` (an untracked pre-scrub open-list that was swept
in the Phase-14-close branch/scratch cleanup). Git-tracked.

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
