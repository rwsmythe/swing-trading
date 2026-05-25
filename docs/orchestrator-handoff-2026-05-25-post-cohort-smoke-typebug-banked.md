# Orchestrator handoff — 2026-05-25 (post-cohort-smoke + gotcha #28 banked + type-bug newly exposed; pre-A+B+D1 sequence)

You are taking over as orchestrator (**Turn F**) for the Swing Trading project at the **post-pattern-cohort-smoke + gotcha #28 banked + V2-reader-type-bug newly-exposed** breakpoint.

**Context**: Turn E drove the Option D 3-phase arc (brainstorming + writing-plans + executing-plans) for the pattern_cohort_evaluator harness to completion AND ran the first-cohort smoke twice (20260525T164425Z initially; 20260525T175553Z post-exemplar-OHLCV-fetch); both smoke runs exposed sequential bugs in the template-match Pass 2 pathway. Authored this handoff at ~22% context remaining, below the 30% threshold per `feedback_handoff_briefs_only_when_context_actually_exhausting` BINDING memory.

**main HEAD AT HANDOFF**: `d0dad8e` (gotcha #28 banking commit). This handoff commit becomes new HEAD before Turn F reads.

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

---

## §0 Critical bootstrap framing (all BINDING memories)

- `feedback_pause_means_pause`
- `feedback_worktree_cli_invocation` — `python -m swing.cli` (NOT bare `swing`)
- `feedback_orchestrator_qa_implementer_product` — QA against reality on disk BEFORE merge
- `feedback_orchestrator_performs_merge` — merge + push + housekeeping = orchestrator action
- `feedback_orchestrator_vs_implementer_execution` — default to implementer-dispatch
- `feedback_always_provide_inline_dispatch_prompt` — every brief gets inline prompt
- `feedback_commit_brief_before_inline_prompt` — commit BEFORE inline prompt
- `feedback_handoff_briefs_only_when_context_actually_exhausting` — only author when <30% remaining

**NO Claude co-author footer**. Cumulative streak **~530+ commits ZERO trailer drift** through this handoff brief commit.

---

## §1 Cumulative state at handoff

- **~5973 fast tests broader project estimate** (baseline ~5893 + 80 NEW pattern_cohort_evaluator tests at executing-plans ship)
- **Schema v21 LOCKED** through V2 OHLCV arc + 3 investigations + Option A fix + D.3 + Option D 3-phase arc + gotcha #28
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED via 5 BINDING reader tests at both V2 OHLCV evaluator + pattern_cohort_evaluator)
- **28 cumulative CLAUDE.md gotchas** (1-28); #28 banked this session 2026-05-25
- **~530+ cumulative ZERO Co-Authored-By trailer drift**
- **Method-records**: V2 OHLCV criterion-evaluator v0.3.0 SHADOW (Tier-1 paths) + pattern-cohort-detection v0.1.0 RESEARCH

### Recent commits on main (last 10)

| SHA | Purpose |
|---|---|
| `d0dad8e` | NEW gotcha #28 banked (exemplar OHLCV cache discipline) |
| `71e59f5` | Cohort CSV substrate + gitignore exception for exports/research/cohorts/ |
| `7b204b5` | Phase 3 executing-plans [x] mark + THREE-IN-A-ROW OQ-LOCKED signal |
| `eddeb73` | Merge Option D Phase 3 executing-plans — pattern_cohort_evaluator harness shipped |
| `0059bd6` | Option D Phase 3 dispatch brief |
| `0963ac8` | Option D Phase 2 [x] mark |
| `4d8b35e` | Merge Option D Phase 2 writing-plans |
| `16f9efc` | Option D Phase 2 dispatch brief + Phase 1 [x] mark |
| `18cb49e` | Merge Option D Phase 1 brainstorming |
| `8ba87cd` | Option D Phase 1 dispatch brief |

---

## §2 What just shipped (Turn E extended session 2026-05-24 → 2026-05-25)

### §2.1 Option D 3-phase arc COMPLETE end-to-end

Phase 1 brainstorming SHIPPED at merge `18cb49e` 2026-05-24 (996-line spec + 13 OQs).
Phase 2 writing-plans SHIPPED at merge `4d8b35e` 2026-05-24 (2948-line plan; 13 OQs LOCKED).
Phase 3 executing-plans SHIPPED at merge `eddeb73` 2026-05-25 (6 sub-bundles; 80 tests; 6 NEW research modules + 1 MODIFIED swing/cli.py OQ-13 carve-out +84 lines).

**THREE-IN-A-ROW OQ-LOCKED-with-ZERO-amendments cumulative discipline signal** preserved across all 3 phases.

### §2.2 First-cohort smoke runs (2026-05-25)

Two smoke runs against +67 watch→aplus flips at vcp.tightness_range_factor=1.005:

- **20260525T164425Z** (initial; 8.6 min runtime; 43,370 verdicts): all template_match_score=(none) due to **cache miss on 13 exemplar tickers** (SNAP, AMD, TGT, NVDA, AAPL, MSFT, NFLX, COST, CRWD, NIO, PLTR, TWLO, BLNK — all OUTSIDE candidate universe so never fetched).
- **20260525T175553Z** (post-exemplar-fetch; 8.4 min runtime; 43,370 verdicts): STILL all template_match_score=(none) — second bug exposed.

### §2.3 Substantive smoke findings (independent of template-match bug)

Geometric-score-based per-class breakdown reveals **the +67 cohort is primarily DOUBLE-BOTTOM-W, not VCP**:

| pattern_class | composite≥0.5 (of 8674 windows) | max |
|---|---|---|
| double_bottom_w | 2659 (30.7%) | 0.933 |
| cup_with_handle | 1221 (14.1%) | 0.875 |
| flat_base | 1053 (12.1%) | 0.714 |
| vcp | **128 (1.5%)** | 0.857 |
| high_tight_flag | 40 (0.5%) | 0.667 |

**Operator hypothesis FALSIFIED in instructive way**: Phase 13 detectors do NOT over-filter; they correctly identify the loosened-A+ cohort as the WRONG SHAPE for VCP analysis. Loosening `vcp.tightness_range_factor=1.005` admits double-bottom-w patterns into the numerically-A+ bucket. This explains the V2 OHLCV backtest's 29% breakout rate — wrong entry rules (close > pivot) for the underlying chart shape (W-bottom recovery).

### §2.4 Two bugs uncovered

| Bug | Status | Scope |
|---|---|---|
| 1. Exemplar OHLCV cache miss | **RESOLVED inline** (13 tickers fetched via `read_or_fetch_archive` 2026-05-25) | Research + production architectural gap (gotcha #28 BANKED) |
| 2. V2 reader TypeError: `'<=' not supported between datetime.date and str` | **NEWLY EXPOSED, NOT YET FIXED** | Research-only (shared V2 OHLCV evaluator reader; doesn't affect production swing/data/ohlcv_archive.py) |

**Bug #2 evidence**: `read_yfinance_shape_a_sliced(ex.ticker, cache_dir, asof_date=ex.end_date, ...)` raises TypeError when `ex.end_date` is `datetime.date`. V2 OHLCV evaluator works fine because it passes `data_asof_date` as TEXT-column string; pattern_cohort_evaluator passes `exemplar.end_date` as date via SQLite repo. The reader's internal slicing compares date vs str somewhere.

**Fix scope**: small (~1-5 lines):
- **Caller-side**: `asof_date=ex_row.end_date.isoformat()` at `research/harness/pattern_cohort_evaluator/detector_invoker.py:185`
- **Reader-side** (preferred architecturally): accept both `date` and `str`; normalize internally at `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`

---

## §3 What YOU (Turn F orchestrator) MUST do

### §3.1 Re-engage with operator on next-action sequence (A + B + D1 + bug-#2 fix)

Operator stated at Turn E end: "let's get through the architectural fix, then evaluate shifting to a new orchestrator instance for A+B+D1." The "architectural fix" was originally framed as the operational fix (Option A operator-pre-fetches exemplar OHLCV; done) + the architectural visibility fix (gotcha #28's Option B/C). Then bug #2 surfaced.

**Recommend re-confirming priority order with operator at session start:**
- (i) **Fix bug #2** (V2 reader type-mismatch) — small dispatch (~1-3h); unblocks correct smoke run with template Pass 2 populated
- (ii) **Re-run smoke** post-bug-#2-fix; compare composite_score deltas vs geometric-only run
- (iii) **A**: track smoke outputs (gitignore amendment for `exports/research/<harness-iso>/*.{csv,md,json}` — operator decided YES earlier)
- (iv) **B**: study writeup Results-section amendment with full findings (double_bottom_w dominance + template Pass 2 effect + cfg-policy direction reframed)
- (v) **D1**: double_bottom_w-specific backtest dispatch (mean-reversion entry rules; tests whether dominant detector signal has positive expectancy under appropriate rules)

Operator may also want:
- gotcha #28 Option B architectural fix dispatched (NEW `_step_exemplar_ohlcv` pipeline step) — banked V2 candidate
- Stage 3 AI second-opinion eval (per Turn E earlier banked methodology) — gated on a backtest producing winners; the V2 OHLCV backtest produced 0 closed trades + 5 open positions, so Stage 3 substrate may be too thin without a winning backtest (D1 may produce winners under mean-reversion rules)

### §3.2 V2 reader type-bug fix dispatch — ready substrate

If operator wants to dispatch the bug #2 fix:
- **Failure evidence**: tail of `tmp/<various>` (Turn E's diagnostic script outputs); reproducer one-liner at end of this §
- **Fix sites**: `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` (reader-side, preferred) OR `research/harness/pattern_cohort_evaluator/detector_invoker.py:185` (caller-side fallback)
- **Discriminating test**: pass `asof_date=datetime.date(2026, 5, 22)` to `read_yfinance_shape_a_sliced`; assert returns DataFrame (current: TypeError)
- **Affected callers**: pattern_cohort_evaluator's exemplar load; verify V2 OHLCV evaluator unaffected (passes str)
- **L2 LOCK BINDING preserved**: 5 BINDING reader tests in BOTH harnesses must remain green

**Reproducer command**:
```python
from pathlib import Path
import os
from datetime import date
from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a_sliced, BothExistDiagnostic
cache = Path(os.environ['USERPROFILE']) / 'swing-data' / 'prices-cache'
read_yfinance_shape_a_sliced('AAPL', cache, asof_date=date(2026, 5, 22), min_bars=1, diagnostic=BothExistDiagnostic())
# Raises: TypeError: '<=' not supported between instances of 'datetime.date' and 'str'
```

### §3.3 Smoke output tracking (A)

Operator wants smoke outputs tracked. .gitignore amendment needed:
```
# Add to .gitignore exports section:
!exports/research/pattern-cohort-detection-*
exports/research/pattern-cohort-detection-*/*
!exports/research/pattern-cohort-detection-*/summary.md
!exports/research/pattern-cohort-detection-*/results.csv
!exports/research/pattern-cohort-detection-*/manifest.json
```

Mirrors `exports/diagnostics/` pattern. Apply + commit the 2 prior smoke runs (164425Z + 175553Z) for traceability of the bug-discovery sequence.

### §3.4 Study writeup Results amendment (B)

`research/studies/2026-05-24-pattern-cohort-detection.md` Results section per harness Phase 3 ship. Append:
- Per-class confirmation rate table from smoke
- Substantive finding: cohort is double-bottom-w not VCP
- Implication for cfg-policy direction reframe
- Both bug #1 + bug #2 caveats with current archive caveat (L6 from V2 OHLCV) reference

Small inline edit (~30 min) OR mini dispatch.

### §3.5 Double_bottom_w backtest dispatch (D1)

Substantial dispatch mirroring V2 tightness_range_factor backtest structure but with:
- Entry rule = W right-shoulder break (NOT close > consolidation pivot)
- Cohort = subset of +67 with double_bottom_w composite_score ≥ 0.7 (670 windows; need pattern-level dedup)
- 3 exit rulesets (same as prior backtest dispatch)
- Tests whether dominant detector signal has positive expectancy under mean-reversion-appropriate rules

Brief authoring scope ~1-2h orchestrator-side; implementer dispatch ~4-8h.

### §3.6 Cumulative discipline

- **28 cumulative CLAUDE.md gotchas (1-28) BINDING** for any 38th cumulative C.C lesson #6 validation
- 38th C.C lesson #6 validation slot REMAINS RESERVED (Codex MCP never invoked through Option D 3-phase arc per operator-paired discretion)
- **THREE-IN-A-ROW OQ-LOCKED-with-ZERO-amendments** cumulative discipline signal (Option D arc)

---

## §4 Operator-pending items (NOT orchestrator-blocking)

- **V2.G1-G4 operator gate bug investigations** — STILL DEFERRED
- **Phase 14 commissioning** — DEFERRED until Applied Research arcs yield actionable findings
- **Worktree husks**: `.worktrees/applied-research-pattern-cohort-detector-evaluator-{brainstorm,writing-plans,executing-plans}` — operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` when convenient
- **Schwab refresh-token clock**: renew when ≤24h remaining
- **Periodic V2 OHLCV sensitivity re-run** (quarterly cadence banked; operator can schedule)
- **Architectural fix for gotcha #28 Option B** (NEW `_step_exemplar_ohlcv` pipeline step) — banked V2 candidate

---

## §5 Cumulative streaks to preserve

- **ZERO `Co-Authored-By` footer trailer drift**: ~530+ commits through `d0dad8e`. DO NOT regress.
- **C.C lesson #6 cumulative validations**: 22x CLEAN through T3.SB3 → 23rd-30th NOTABLE through Phase 13 closer arc → 31st-35th NOTABLE/CLEAN V2 arc → 38th SLOT RESERVED.
- **Schema v21 LOCKED** through Option D 3-phase arc + gotcha #28.
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED via 5 BINDING reader tests in BOTH V2 OHLCV + pattern_cohort_evaluator harnesses).
- **Production swing/ READ-ONLY** beyond existing OQ-17 V2 OHLCV evaluator carve-out (+71 lines) + OQ-13 pattern_cohort_evaluator carve-out (+84 lines).
- **V1 persisted state UNCHANGED**.
- **THREE-IN-A-ROW OQ-LOCKED-with-ZERO-amendments** through Option D 3-phase arc (preserves SECOND-IN-A-ROW signal from V2 OHLCV arc; the Option D arc is the SECOND such achievement).

---

## §6 Suggested first session flow (Turn F)

1. Read this brief end-to-end
2. Read `CLAUDE.md` current state + gotcha #28
3. Re-engage operator: A+B+D1 priority order + new bug #2 fix priority + Codex 38th slot if desired
4. Execute per operator decisions; dispatch / inline as appropriate
5. Brief-framing accuracy per gotcha #27 sub-lesson: verify "since X shipped" claims against git log

Estimated wall-clock: 4-8 hours orchestrator-paced for A+B+D1+bug-#2 fix sequence (mostly authoring dispatch briefs + inline housekeeping; substantive work happens at implementer dispatches).

---

## §7 Do NOT

- Re-litigate the LOCKED OQs from any Option D arc phase (28 OQs total carried; ZERO amendments)
- Skip QA against reality on disk per `feedback_orchestrator_qa_implementer_product` BINDING
- Add Co-Authored-By footer to ANY commit
- Modify production swing/ beyond existing OQ-17 + OQ-13 carve-outs
- Modify V1 persisted state
- Trigger Schwab API calls
- Skip cumulative gotcha discipline if Codex review invoked (28 gotchas BINDING)
- Commission Phase 14 prematurely

---

*End of Turn F orchestrator handoff brief. Post-cohort-smoke + gotcha #28 banked + V2-reader-type-bug newly-exposed transition. Turn F executes A+B+D1 + bug-#2 fix sequence per operator priority. ~530+ cumulative ZERO Co-Authored-By trailer drift preserved. Option D 3-phase arc COMPLETE end-to-end; THREE-IN-A-ROW OQ-LOCKED-with-ZERO-amendments cumulative discipline signal preserved.*
