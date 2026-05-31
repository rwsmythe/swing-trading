# Phase 14 Sub-bundle 4 -- Review + Journal UX -- Gate-Fix Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the SB4 executing-plans **gate-fix** implementer. No prior conversation context. This is a CONTINUATION of the SB4 executing-plans on the SAME branch, resolving operator-witnessed-gate findings before the gate passes + merge.

**Mission:** Fix the journal-surface defects + add the operator-requested listing columns surfaced at the SB4 operator-witnessed gate (2026-05-30), then re-run the single Codex chain to convergence + hand back for re-gate. The SB4 implementation SHIPPED (32 commits at branch HEAD `f320ea7`; QA-passed) and the gate PASSED S3 (mechanical + via S7), S4 (BULZ row-expand), S7-chart, S7-404. The gate FOUND defects on the **journal listing (S5 additions), sort/filter (S6), and chronology verbiage (S7)** -- this dispatch fixes them.

**Brief:** `docs/phase14-sub-bundle-4-review-journal-ux-gate-fix-dispatch-brief.md` (this file).

**Context:** SB4 brainstorm SHIPPED `2cf30f9`; writing-plans `573bcb3`; executing-plans branch `phase14-sub-bundle-4-review-journal-ux-executing-plans` at `f320ea7` (NOT yet merged -- the gate gates the merge). Plan: `docs/superpowers/plans/2026-05-30-phase14-sub-bundle-4-review-journal-ux-plan.md`. Executing-plans brief: `docs/phase14-sub-bundle-4-review-journal-ux-executing-plans-dispatch-brief.md` (the 9 OQ LOCKs + L1-L8 still BINDING).

**Cumulative discipline:** ~660+ ZERO Co-Authored-By; **NO schema change (v23 held; add NO migration)**; **read-mostly (NO new trade/fill/review/chart_renders write)**; L2 Schwab LOCK; ASCII; matplotlib/HTMX disciplines. ALL still BINDING.

**Skill posture:** invoke `copowers:executing-plans` (or continue the TDD loop directly). **ONE Codex chain, run to CONVERGENCE** (zero new crit/major; cap suspended per `feedback_codex_round_limit_suspended`). **Codex transport:** MCP dead in the VS Code extension; the WSL Codex fallback reads the worktree from disk (copowers v2.0.2; auto-routes; findings -> `.copowers-findings.md`). Output: the fixes + an updated/appended return report.

---

## §0 Read first
1. THIS BRIEF.
2. The SB4 executing-plans dispatch brief §1.3 (the 9 OQ LOCKs) + §1.2 (L1-L8). Still BINDING -- esp. **L2 read-mostly / L3 no-schema / OQ-6 dollar total_risk / OQ-9 whole-`<table>` outerHTML swap / L4 HTMX trinity / L5 matplotlib ASCII**.
3. The plan §G Slice 2 (listing) + Slice 3 (sort/filter) + Slice 5 (chronology) -- the surfaces you are fixing.
4. CLAUDE.md HTMX gotchas (the `<tr>`/`<thead>` synthetic-table-wrap one is exactly what EP-R1 caught; keep fragments well-formed) + matplotlib mathtext (ASCII).
5. `feedback_verify_regression_test_arithmetic` (days-open + any new derived column: test the arithmetic).

---

## §1 Gate findings -> fixes (BINDING scope; do NOT widen beyond these)

The orchestrator diagnosed root causes at branch HEAD `f320ea7`; **re-grep at STEP 0** (#2/#4) before editing.

### FIX-1 (S5 enhancement) -- two new journal-listing columns
- Add an **Exit / closed-date** column, positioned **BEFORE** the "Closing price" column.
- Add a **Days-open** column (closed trades: `exit_date - entry_date`; open trades shown in the listing: `today - entry_date`).
- Surfaces: `JournalRowVM` (`swing/web/view_models/journal.py:~153` -- add `exit_date` + `days_open` fields) + `_build_journal_rows`/`build_journal` (populate them; exit date from the reducing-fill / final exit; days-open arithmetic) + `journal.html.j2` listing template (insert the columns; Exit before Closing price). **Make BOTH new columns sortable** (see FIX-2: add their keys to `_SORT_KEYS`).
- Tests: row VM has exit_date + days_open; multi-leg + single-leg exit-date selection (last exit); open-trade days-open uses today; column order (Exit before Closing price) asserted.

### FIX-2 (S6 DEFECT) -- sort broken on 6 columns
- **Root cause:** `_SORT_KEYS` (`swing/web/view_models/journal.py:42`) = `{entry_date, ticker, final_r, total_risk_dollars, state}` -- it is MISSING the 6 columns the operator cannot sort: **open_price, shares, closing_price, chart_pattern, aplus_bucket, hypothesis_label** (+ the 2 NEW FIX-1 columns exit_date, days_open).
- Fix: add those keys to `_SORT_KEYS`, implement the sort comparison for each (the `JournalRowVM` fields already exist: `open_price`/`shares`/`closing_price`/`chart_pattern`/`aplus_bucket`/`hypothesis_label`), and ensure the **column headers emit the matching sort key**. **None-handling:** `closing_price`/`final_r`/`exit_date`/`days_open` are `None` for open trades -- sort None-last (or None-first) deterministically in BOTH `dir` values; do NOT crash on mixed None.
- Tests: each newly-sortable column sorts ascending + descending; None-trades sort deterministically; the sort link preserves active filters (WP-R2 M#5 `query_state`).

### FIX-3 (S6 DEFECT) -- filter "Invalid filter, showing all" + 'Open' shows nothing
- **Root cause:** the filter `<select>` (added late) emits option VALUES that do not match the backend allowlists `_FILTER_STATES` / `_FILTER_PATTERNS` / `_FILTER_APLUS` (`swing/web/view_models/journal.py:47/57/62`) -> every selection trips `invalid_filter=True` -> "showing all". AND the listing's row scope must INCLUDE open trades so the **'Open' virtual state group** actually returns them.
- Fix (two parts):
  1. **Align the `<select>` option values to the canonical allowlist tokens** (state/pattern/aplus) so a valid selection is never flagged invalid. Verify each `<select>`'s emitted value is in the corresponding frozenset; the 'Open' virtual group must expand to the concrete open state(s) (`_FILTER_STATES` virtual-group map at `:51-56`).
  2. **Confirm the journal listing row scope includes open trades** (the `JournalRowVM` already handles open-trade `None` columns at `:295-298`). If `build_journal`'s row list is closed-only / period-excludes open, widen it so an 'Open' (or 'all') filter shows open positions. Per P14.N6 "browse the database", open trades belong in the listing.
- **HOLD THE LINE:** OQ-9 whole-`<table>` `outerHTML` swap stays; the HTMX trinity applies (the swap fragment must stay well-formed -- keep the `<thead>`/`<tr>` intact, the exact EP-R1 failure mode).
- Tests: every `<select>` option value is in its allowlist (a discriminating test that enumerates the template's option values vs the frozensets -- this is the byte-level contract that was broken); 'Open' returns open trades; an invalid value still falls back gracefully (no 422, `invalid_filter=True`); a valid value never sets `invalid_filter`.

### FIX-4 (S7 DEFECT, cosmetic) -- chronology verbiage duplicated
- **Root cause:** `ChronologyEntry` `kind` + `summary` + `detail` OVERLAP and the template prints all three (`swing/web/view_models/trade_chronology.py:63-173`): `kind="event:stop_adjust"` + `summary="stop_adjust"` (type twice); `kind="fill:entry"` + `summary="entry 39.0 @ 7.58"` (action twice); snapshot has MFE/MAE in BOTH `summary` and `detail`; review has the lesson text in BOTH `summary` and `detail` + `kind="review"` + `summary="review ..."`.
- Fix: make `kind`/`summary`/`detail` non-overlapping so each entry renders the **type once** and **values once**. Recommended: a clean `kind` (e.g. `entry`/`stop_adjust`/`trim`/`exit`/`snapshot`/`review`/`note`), a `summary` that does NOT repeat the kind word, and a `detail` that does NOT repeat the summary's values (drop the duplicate MFE/MAE; drop the duplicate review lesson). Keep it ASCII (no mathtext metachars). Do NOT change the chronology SEMANTICS (sources, order, precedence `fill < daily_management < trade_event < review`, the `review_log`-excluded rule) -- this is presentation-only.
- Tests: a representative entry of each source renders with NO repeated type token + NO duplicated value substring (assert the rendered/summary text does not contain its kind token twice, and snapshot/review don't double-print MFE/MAE/lesson).

### FIX-5 (OPTIONAL; operator-gated) -- styled full-page 404
- Current: the full-page drill-down (`GET /journal/trades/{id}`) 404s with raw JSON `{"detail":"Trade #N not found"}` -- a CORRECT 404 (requirement met), but unstyled. **Only implement if the orchestrator confirms the operator wants it** (consistency with the app's `PageErrorVM` HTML error convention). If included: render a styled full-page 404 for the full-page route while the HTMX fragment path keeps its 200+unavailable contract (Codex M#6). Default: SKIP (banked).

---

## §2 Disciplines (BINDING)
- **NO schema** (v23 held; add NO migration). **Read-mostly** (NO new trade/fill/review/`chart_renders` write -- these are all read/display fixes). L2 Schwab LOCK (no new `schwabdev.Client.*`). If any fix appears to need a write or a migration, STOP + escalate (none should).
- TDD per fix (red -> green -> commit; 3-5 commits/fix area). Trust pytest counts (#1).
- HTMX trinity (L4) for the sort/filter swap; keep the swapped `<table>` fragment well-formed (EP-R1 lesson). matplotlib ASCII (L5) for the chronology text.
- ZERO Co-Authored-By; final `-m` paragraph plain prose; verify `%(trailers)` `[]` per commit; NO `--no-verify`.
- `python -m swing.cli` in the worktree.

## §3 Codex chain (ONE; run to convergence)
After all fixes land + green, run ONE Codex chain to `NO_NEW_CRITICAL_MAJOR` (cap suspended; may exceed 5 rounds). Lens: the filter value-contract (template option values vs allowlist frozensets), sort None-handling, chronology non-overlap, the new-column arithmetic (days-open, exit-date selection single/multi-leg), read-mostly + no-schema preserved, HTMX swap fragment well-formed. WSL fallback (reads the worktree from disk). EVIDENCE the chain ran genuinely in the return report (`.copowers-findings.md` rounds).

## §4 Done criteria
1. FIX-1..FIX-4 shipped (FIX-5 only if operator-confirmed); each TDD-tested.
2. Sort works on ALL listing columns; filter never falsely "invalid" on a valid selection; 'Open' shows open trades; chronology reads cleanly (no duplicated type/values); Exit + Days-open columns present (Exit before Closing price).
3. Codex chain CONVERGED; fast suite green on branch + ruff clean; NO migration; read-mostly preserved; ZERO Co-Authored-By.
4. Return report appended/added; branch pushed for orchestrator QA + operator re-gate (S5/S6/S7).

## §5 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Branch/worktree:** CONTINUE on the EXISTING `phase14-sub-bundle-4-review-journal-ux-executing-plans` in the retained worktree `.worktrees/phase14-sub-bundle-4-review-journal-ux-executing-plans/` (do NOT cut a new branch; do NOT re-do shipped work). Base = `f320ea7`.
- **CLI:** `python -m swing.cli` in the worktree.
- **Re-gate:** after push, the orchestrator relaunches the 8081 server on the fixed code; the operator re-walks S5 (columns + sort + thumbnails), S6 (sort all columns + filter incl. 'Open'), S7 (chronology readability). Gate-pass -> orchestrator merges + re-runs the suite on the merged HEAD (`feedback_no_false_green_claim`).

---

*End of brief. SB4 gate-fix dispatch -- resolve the operator-witnessed-gate journal findings (FIX-1 Exit+Days-open columns; FIX-2 sort 6 missing columns; FIX-3 filter value-contract + open-trade scope; FIX-4 chronology verbiage de-dup; FIX-5 optional styled 404) on the existing executing-plans branch; ONE Codex chain to convergence; NO schema, read-mostly. Hand back for operator re-gate of S5/S6/S7. The 9 OQ LOCKs + L1-L8 remain BINDING.*
