# Orchestrator handoff — 2026-05-24 (post-Option-A-dispatch + pre-implementer-handback)

You are taking over as orchestrator (Turn E) for the Swing Trading project at the **post-Option-A-fix-dispatch + pre-implementer-handback** breakpoint.

**Context**: Turn D drove the full V2 OHLCV arc (brainstorming → writing-plans → executing-plans → DK:62 investigation → D.1 Shape A refresh → D.2 V2 smoke re-run → DHC/UCO/VSAT investigation → Option A fix dispatch) and authored this handoff at ~18% context remaining (after Option A inline prompt provided), below the 30% threshold per `feedback_handoff_briefs_only_when_context_actually_exhausting` BINDING memory.

**main HEAD AT HANDOFF**: `ffd10d8` (Option A fix dispatch brief commit). This handoff commit becomes new HEAD before Turn E reads.

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
- `feedback_handoff_briefs_only_when_context_actually_exhausting` — only author when <30% remaining OR session-terminating

**NO Claude co-author footer**. Cumulative streak **~500+ commits ZERO trailer drift** through dispatch brief `ffd10d8`.

---

## §1 Cumulative state at handoff

- **5778 fast tests** baseline + **115 NEW V2 fast tests** post-V2-arc = ~5893 broader estimate; Option A fix will add **3-4 NEW discriminating tests**
- **Schema v21 LOCKED** (NO migrations through V2 arc + DK:62 + DHC/UCO/VSAT + Option A fix)
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED via 5 BINDING discriminating tests)
- **25 cumulative CLAUDE.md gotchas** (1-25); 34th cumulative C.C lesson #6 validation expected at Option A handback if Codex invoked
- **~500+ cumulative ZERO Co-Authored-By trailer drift**

### Recent commits on main (last 10)

| SHA | Purpose |
|---|---|
| (TBD) | Turn E orchestrator handoff brief (this file) |
| `ffd10d8` | V2 OHLCV baseline-parity excluded-filter fix dispatch brief (165 lines; Option A) |
| `8330e50` | Post-DHC/UCO/VSAT-investigation-merge housekeeping (4 files + post-D.2 smoke; NEW gotcha #25; D.1+D.2 marked [x] inline) |
| `d7cdd51` | Merge applied-research-v2-dhc-uco-vsat-drift-triage (V2 HARNESS FALSE-POSITIVE root-caused; Option A LOCKED) |
| `019dc6e` | V2 OHLCV DHC/UCO/VSAT × 60-64 investigation findings + return report |
| `970ce80` | V2 OHLCV DHC/UCO/VSAT × 60-64 triage dispatch brief |
| `bef2d4e` | Post-DK62-investigation-merge housekeeping (3 files; NEW gotcha #24; sub-event) |
| `4afab36` | Merge applied-research-v2-dk62-criterion-drift-triage (parallel-archive freshness desync; D.1 path identified) |
| `5a43508` | V2 OHLCV DK:62 investigation findings + return report |
| `182aca9` | V2 OHLCV DK:62 triage dispatch brief |

### Option A fix sequence remaining
```
Option A fix dispatch brief (ffd10d8; THIS pass) → operator dispatches implementer →
implementer applies 3-5 commits + 3-6 tests + V2 smoke re-run + return report → Turn E
(YOU): QA + merge --no-ff + post-merge housekeeping → operator-paired D.3 (method-
record v0.2.1 + Limitations L4/L5) + D.4 (V2 candidate banking) → full 63-eval-run
operator reproduction (UNBLOCKED post-Option-A Tier-1 FULL PASS) → research→shadow
promotion gate per OQ-8 ladder → optional next-arc (cfg-policy method-record if binding
thresholds identified; OR market-conditions/other-gates investigation; OR Phase 14
commissioning consideration per Path B sequencing)
```

---

## §2 What just shipped (Turn D extended session 2026-05-23 → 2026-05-24)

### §2.1 V2 OHLCV arc COMPLETE end-to-end + DOUBLE-INVESTIGATED (per Note 2026-05-24 in CLAUDE.md line 7-8):
- (a) DK:62 investigation at `4afab36` — parallel-archive freshness desync; RESOLVED by Turn-D-inline D.1 Shape A refresh 2026-05-24 (DK Shape A mtime May 21 07:39 → May 24 06:06; 2026-05-21 boundary bar present); NEW gotcha #24 banked.
- (b) D.2 V2 smoke re-run at `aplus-sensitivity-v2-20260524T162641Z` confirmed DK:62 RESOLVED ✓ but surfaced 15 NEW tier-1 drift entries (DHC/UCO/VSAT × 60-64) hidden by pre-R3.M1 buggy flip-recording.
- (c) DHC/UCO/VSAT investigation at `d7cdd51` — V2 HARNESS FALSE-POSITIVE (NOT V2 evaluator bug); V1 short-circuits criterion evaluation for excluded-ticker classes (open positions in `held_set`; ETF blocklist in `cfg.etf_exclusion.manual_block`); V2's `_compute_baseline_parity` naively invokes `evaluate_one`; `bucket_for` returns only `{aplus, watch, skip}` not `'excluded'`. Option A LOCKED (1-line research-branch filter; ZERO production swing/ writes); NEW gotcha #25 banked.
- (d) **V2 evaluator confirmed CORRECT** — counter-tests reproduce V1 buckets EXACTLY when given V1's inputs.

### §2.2 Option A fix dispatch brief SHIPPED at `ffd10d8`

- **Brief**: `docs/v2-baseline-parity-excluded-filter-dispatch-brief.md` (165 lines; 7 sections §0-§6)
- **Scope**: 3 fixes (CORE #1 bucket='excluded' filter + DEFENSIVE #2 bucket='error' extension + OPTIONAL #3 drill-down filter) + 3-4 discriminating tests + V2 smoke re-run + return report
- **Workflow**: `superpowers:test-driven-development` (TDD slice discipline; each per-test slice = ONE commit); Codex MCP review OPTIONAL (operator-paired choice)
- **Branch**: `applied-research-v2-baseline-parity-excluded-filter`
- **Expected duration**: ~1-3 hours operator-paced
- **Inline implementer prompt**: provided in Turn D chat at `ffd10d8` commit time (NOT committed; operator copy/pastes into fresh Claude Code session). If lost, regenerate from brief §0 + §1 + §2 content.

---

## §3 What YOU (Turn E orchestrator) MUST do

### §3.1 Wait for Option A fix implementer handback

Typical operator-paced wait ~1-3 hours. If operator opens this session before handback: reassure / offer ad-hoc priorities / revisit when handback arrives.

### §3.2 When implementer hands back: QA per `feedback_orchestrator_qa_implementer_product` BINDING

Verify against reality on disk:
- Branch HEAD + commit chain (~3-5 commits expected per TDD slice discipline)
- ZERO Co-Authored-By trailers across all branch commits
- `git diff main -- swing/` EMPTY (production read-only invariant)
- `git diff main -- swing/data/migrations/` EMPTY (schema v21 LOCKED)
- `git diff main -- research/harness/` shows ONLY `sweep.py` modification (Option A filter + optional drill-down filter)
- 3-4 NEW discriminating tests at `tests/research/test_aplus_v2_ohlcv_sweep.py` (synthetic excluded + synthetic error + negative control + optional drill-down)
- L2 LOCK 5 BINDING discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py` STILL GREEN
- V2 smoke re-run artifact at `exports/diagnostics/aplus-sensitivity-v2-<NEW-timestamp>.{csv,md}` — verify CRITERION DRIFT section DISAPPEARS / Tier-1 FULL PASS
- Return report at `docs/v2-baseline-parity-excluded-filter-return-report.md`
- Codex chain (if invoked): per-round Major counts + 34th cumulative C.C lesson #6 validation result + any NEW gotchas banked

### §3.3 Merge `--no-ff` to main + push (per `feedback_orchestrator_performs_merge` BINDING)

Merge commit message: comprehensive ~30-60 lines covering fix scope + Tier-1 PASS confirmation + Codex chain shape if invoked + streaks preserved.

### §3.4 Post-merge housekeeping (sub-event scale)

Mirror the DK:62 + DHC/UCO/VSAT housekeeping precedent — **sub-event scale** (NOT a full Current state pivot):
- **CLAUDE.md** line 3 in-place amendment: note Option A SHIPPED + Tier-1 FULL PASS confirmed + research→shadow promotion gate UNBLOCKED
- **CLAUDE.md** any NEW gotchas surfaced from Codex chain if invoked (likely 0-1; Option A is a clean implementation of gotcha #25)
- **orchestrator-context.md** in-place amendment
- **phase3e-todo.md** top entry amendment: mark Option A fix [x] + V2 smoke re-run [x] + add NEW [ ] for D.3 + D.4 + full reproduction
- **NO Prior demote**, **NO archive-split** (Option A is a sub-event under V2 arc)

### §3.5 Operator-paired next actions

Post-merge + housekeeping, surface to operator:
- **D.3 (method-record v0.2.1 amendment)** — small inline doc edit OR mini dispatch. Add Limitation L4 (DK:62 parallel-archive freshness desync; per gotcha #24) + Limitation L5 (V2 harness sentinel-bucket filter discipline; per gotcha #25)
- **D.4 (V2 candidate banking documentation)** — same as D.3; small. Bank V2.5/V3 candidates: (a) mtime tiebreaker for Shape A reader; (b) sentinel-bucket parity-comparison discipline as research-branch BINDING template
- **Full 63-eval-run operator reproduction** — UNBLOCKED post-Option-A Tier-1 FULL PASS. Single-command invocation likely; operator-paired execution
- **Research → shadow promotion gate per OQ-8 ladder** — gate conditions: V2 shipped + baseline parity green (NOW SATISFIED post-Option-A) + ≥1 study writeup (SATISFIED at T-V2.5 closer) + ≥1 binding threshold OR all 15 declared non-binding (TBD per full reproduction). Promotion gate can fire once binding-variable identification completes
- **Optional next-arc** — depending on binding-threshold identification outcome: cfg-policy method-record (binding thresholds found) OR market-conditions / other-gates investigation (all 15 non-binding) OR Phase 14 commissioning consideration per Path B sequencing

---

## §4 Operator-pending items (NOT orchestrator-blocking)

- **V2.G1-G4 operator gate bug investigations** — STILL DEFERRED per operator decision 2026-05-23 PM (work AFTER Applied Research tasking completes). Banked at `docs/phase3e-todo.md` §"Post-T4.SB-SHIPPED operator gate feedback (V2 backlog; 2026-05-23)".
- **Phase 14 commissioning** — DEFERRED until V2 OHLCV output informs operational scope. Revisit post §3.5 promotion gate + binding-variable identification.
- **Worktree husks**: `.worktrees/applied-research-v2-{...}` (multiple from V2 arc + investigations + Option A fix). Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` when convenient.
- **Schwab refresh-token clock**: renew via `swing schwab logout` → `swing schwab setup` when ≤24h remaining.

---

## §5 Cumulative streaks to preserve

- **ZERO `Co-Authored-By` footer trailer drift**: ~500+ commits through `ffd10d8`. DO NOT regress.
- **C.C lesson #6 cumulative validations**: 22x CLEAN through T3.SB3 → 23rd-30th NOTABLE Phase 13 closer arc → 31st-33rd NOTABLE V2 arc → 34th expected at Option A handback (if Codex invoked) with all 25 gotchas BINDING.
- **Schema v21 LOCKED** through V2 arc + investigations + Option A fix.
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED via 5 BINDING discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py`).
- **Production swing/ READ-ONLY** beyond existing OQ-17 CLI carve-out (Option A fix in research-branch only).
- **V1 persisted state UNCHANGED** through V2 arc + investigations + Option A fix.

---

## §6 Suggested first session flow (Turn E)

1. Read this brief end-to-end
2. Read `CLAUDE.md` line 3 (current state) + Note line 7-8 (2026-05-24 summary)
3. Check Option A fix implementer status (handback arrived?)
4. If YES: execute §3 sequence (QA → merge → housekeeping → operator-paired D.3/D.4/full-reproduction surface)
5. If NO: pause; offer operator other priorities; revisit when handback arrives

Estimated wall-clock: ~1-2 hours orchestrator-paced for the full Turn E sequence (small fix; clean QA + merge + housekeeping + operator-paired surface).

---

## §7 Do NOT

- Re-litigate Option A fix scope (LOCKED per investigation §5)
- Skip QA against reality on disk per `feedback_orchestrator_qa_implementer_product` BINDING
- Add Co-Authored-By footer to ANY commit
- Modify production swing/ beyond existing OQ-17 carve-out
- Modify V1 persisted state
- Trigger Schwab API calls
- Skip cumulative gotcha discipline if Codex review invoked (25 gotchas BINDING)
- Commission V2.G1-G4 / Phase 14 prematurely
- Promote V2 method-record from research → shadow before binding-threshold identification (or all-15-non-binding sign-off) completes via full 63-eval-run reproduction

---

*End of Turn E orchestrator handoff brief. Post-Option-A-fix-dispatch + pre-implementer-handback transition. Turn E executes QA + merge + housekeeping + operator-paired surface of D.3/D.4/full-reproduction once handback arrives. ~500+ cumulative ZERO Co-Authored-By trailer drift preserved. Applied Research Tranche 1 arc COMPLETE + DOUBLE-INVESTIGATED end-to-end (V2 evaluator confirmed CORRECT); Option A fix dispatch is the final remediation step before research→shadow promotion gate per OQ-8 ladder.*
