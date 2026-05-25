# Pattern Cohort Detector Evaluator — Phase 2 Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the pattern cohort detector evaluator harness **writing-plans phase** implementer. No prior conversation context.

**Mission:** Convert the brainstorming-phase spec (996 lines; 14 sections; 13 OQs all LOCKED per operator-paired Turn D triage 2026-05-24 PM with ZERO amendments) into an executable implementation plan with TDD-sliced task graph, commit cadence preface, test budget, and dependency ordering. Phase 2 of 3-phase arc (Phase 1 brainstorming SHIPPED at merge `18cb49e`; this dispatch is Phase 2; Phase 3 executing-plans follows).

**Workflow:** `superpowers:writing-plans` skill. Adversarial Codex MCP review OPTIONAL via `copowers:writing-plans` wrapper — operator-paired discretion. The brainstorming phase deliberately deferred Codex; writing-plans is the natural slot for 38th cumulative C.C lesson #6 validation if operator chooses (mirrors V2 OHLCV writing-plans precedent at Codex R6 NO_NEW_CRITICAL_MAJOR).

**Branch:** `applied-research-pattern-cohort-detector-evaluator-writing-plans` — branches from main HEAD `18cb49e` (or later).

**Worktree:** `git worktree add .worktrees/applied-research-pattern-cohort-detector-evaluator-writing-plans applied-research-pattern-cohort-detector-evaluator-writing-plans`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~5-8 hours operator-paced (mirrors V2 OHLCV writing-plans phase timing).

---

## §0 Read first (BINDING substrate)

1. **`docs/superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md`** — the 996-line brainstorming-phase spec. ALL 13 OQ dispositions are LOCKED per operator triage 2026-05-24 PM (mirrors V2 OHLCV's 18-OQ-LOCKED precedent). Plan consumes spec as BINDING substrate.

2. **`docs/applied-research-pattern-cohort-detector-evaluator-brainstorming-return-report.md`** — Phase 1 return report; surfaces brainstorming-phase observations + V1-simplifications-banked candidates.

3. **`docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md`** — V2 OHLCV writing-plans plan (2602 lines; 15 sections §A-§O). STRUCTURAL TEMPLATE for this plan.

4. **`docs/applied-research-pattern-cohort-detector-evaluator-dispatch-brief.md`** — Phase 1 dispatch brief (parent of this arc); §2.2 writing-plans phase scope description.

5. **`research/harness/aplus_v2_ohlcv_evaluator/`** — V2 OHLCV evaluator implementation; structural reference for the harness modules to-be-built.

6. **`research/method-records/aplus-criteria-calibration.md` v0.3.0** — method-record template; §K.1-§K.4 of the spec proposes the NEW method-record at `research/method-records/pattern-cohort-detection.md`.

7. **CLAUDE.md gotchas #19-27** (cumulative discipline; 27 gotchas BINDING for any 38th cumulative C.C lesson #6 validation if Codex invoked).

---

## §1 LOCKED OQ dispositions (consume verbatim from spec §J)

All 13 OQs LOCKED per operator triage 2026-05-24 PM. Plan MUST NOT amend any disposition; LOCKED dispositions are BINDING substrate for the plan's per-task scope.

| OQ | LOCKED disposition |
|---|---|
| OQ-1 | Direct production detector function invocation (re-import `_pattern_detect_registry`) |
| OQ-2 | V1 = Mode (b) CSV primary + Mode (a) inline fallback; Mode (c) SQL deferred V2.5+ |
| OQ-3 | Re-export V2 OHLCV evaluator's `ohlcv_reader.py` VERBATIM (single source of L2 LOCK truth) |
| OQ-4 | Mirror production `zigzag_pivot` only; multi-mode deferred V2.5+ |
| OQ-5 | Per-entry CSV column + CLI global; per-entry takes precedence |
| OQ-6 | Default `--template-match=on` (production-parity) |
| OQ-7 | Default `--window-mode=per-window` (NON-production-default; deliberate per analytical purpose); operator can force `last-only` for parity testing |
| OQ-8 | Default production `current_stage`; per-entry `stage_override` deferred V2.5+ |
| OQ-9 | First-cohort = +67 watch→aplus flips at `vcp.tightness_range_factor=1.005` (15 unique tickers) |
| OQ-10 | CLI subcommand = `swing diagnose pattern-cohort-detect` |
| OQ-11 | Inherit V2 OHLCV evaluator's `BothExistDiagnostic` surface |
| OQ-12 | Uniform empty-state per T3.SB3 LOCK: `(none)` markdown / `null` CSV / `None` JSON |
| OQ-13 | CLI subcommand registration = sole production-`swing/`-write carve-out per OQ-17 V2 OHLCV precedent (35-60 lines) |

---

## §2 Plan deliverables

Per `superpowers:writing-plans` skill + V2 OHLCV writing-plans precedent:

### §2.1 Plan document

Author plan at `docs/superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md` per V2 OHLCV plan structural template. Sections (per V2 OHLCV plan §A-§O):

- **§A**: Scope summary + dependency graph + dispatch sequencing
- **§B**: File map (per spec §B; ~7 NEW research/ modules + 1 MODIFIED `swing/cli.py` per OQ-13 carve-out + NEW method-record + NEW first-study writeup target)
- **§C**: Per-task decomposition (T-PC.1, T-PC.2, ..., T-PC.N) with TDD slices
- **§D**: Per-task acceptance criteria
- **§E**: Per-task discriminating tests
- **§F**: L2 LOCK reinforcement test inventory (per spec §F.1 + §E.3; minimum 5 BINDING)
- **§G**: Commit cadence preface (per V2 OHLCV plan §G.0 precedent; ~30-50 commits expected for ~5-7 modules + ~50-80 tests)
- **§G.0**: Commit cadence discipline (per-TDD-slice commit; parametrize-consolidation for related discriminating tests)
- **§H**: Test budget (per V2 OHLCV plan §H precedent; project against current ~5893 baseline → ~5943-5973 post-ship estimate at +50-80 new tests)
- **§I**: Integration points (V2 OHLCV evaluator re-export per OQ-3; production `_pattern_detect_registry` re-import per OQ-1)
- **§J**: Risk register + mitigations
- **§K**: Method-record extension (per spec §K NEW method-record at `research/method-records/pattern-cohort-detection.md` v0.1.0)
- **§L**: Study writeup target (first cohort study at `research/studies/2026-MM-DD-pattern-cohort-detection.md`)
- **§M**: Dispatch sequencing for Phase 3 executing-plans
- **§N**: Self-review

### §2.2 Return report

Return report at `docs/applied-research-pattern-cohort-detector-evaluator-writing-plans-return-report.md` covering:

- Plan section inventory
- Per-OQ verification (all 13 LOCKED + carried forward)
- Codex chain shape if invoked (per-round Major counts; cumulative C.C lesson #6 validation result; any NEW gotchas surfaced)
- Banked V1 simplifications (per V2 OHLCV writing-plans precedent §4)
- Banked patterns for executing-plans phase
- Discipline deviations if any

### §2.3 Codex MCP review (optional)

Adversarial Codex MCP review per `copowers:writing-plans` wrapper if operator chooses. 38th cumulative C.C lesson #6 validation slot available; 27 cumulative gotchas (1-27) BINDING. Per V2 OHLCV writing-plans precedent, Codex caught REAL defects (Codex R6 converged at NO_NEW_CRITICAL_MAJOR after 6 rounds; 0 CRITICAL + 16 MAJOR + 13 MINOR ALL RESOLVED in-place).

---

## §3 Watch items + cumulative discipline (BINDING)

### §3.1 Cumulative discipline

27 cumulative CLAUDE.md gotchas (1-27) BINDING for any 38th cumulative C.C lesson #6 validation if Codex invoked. Especially relevant:

- **#27** (silent-skip-without-audit pattern in pipeline steps) — this harness ARCHITECTURALLY answers the question gotcha #27 surfaced; plan should NOT inadvertently reintroduce silent-skip patterns in the new harness
- **#26** (OHLCV archive bar-content TEMPORAL mutation) — plan should document L6 caveat for the harness's baseline-parity invariant (per spec §E.1)
- **#25** (sentinel-bucket parity-comparison discipline) — plan should verify the harness's verdict-comparison surface respects sentinel discipline
- **#24** (parallel-archive freshness desync) — inherited from V2 OHLCV reader re-export
- **#19** (cascade-call-graph verification) — plan should verify `_pattern_detect_registry` cascade through production detector callees
- **#20** (runtime-binding-shape + empty-result-set) — plan should enumerate empty-cohort + empty-OHLCV-cache behavior

### §3.2 Process discipline

- **NO Co-Authored-By footer** — ~518+ cumulative streak through `18cb49e`; preserve
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths + markdown narrative**
- **Edit tool for per-file edits**

### §3.3 Schema discipline (LOCK)

Schema v21 LOCKED. Writing-plans is docs-only.

### §3.4 L2 LOCK preservation (BINDING)

Plan MUST enumerate the 5 BINDING discriminating tests per spec §E.3 (4 file-open boundaries + 4-module import sentinel graph; same structural pattern as V2 OHLCV evaluator's reader tests). Since OHLCV reader is re-exported VERBATIM per OQ-3, the harness's L2 LOCK tests verify re-export integrity (not duplicate the V2 reader's own tests).

### §3.5 V1 persisted state read-only

Plan documents that harness output lives in `exports/research/pattern-cohort-detection-<ISO>/` ONLY. ZERO modification of `pattern_evaluations` / `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / V1 persisted state.

### §3.6 Production swing/ — OQ-17-precedent carve-out only

Plan documents CLI subcommand registration at `swing/cli.py` (mirror V2 OHLCV evaluator OQ-17 precedent; 35-60 lines). ALL other production swing/ stays read-only.

### §3.7 Brief-framing accuracy discipline (per gotcha #27 sub-lesson)

Plan MUST verify any "since X shipped" / "across N runs" / file-line-range citations against `git log` + source code BEFORE inclusion. Banked from `_step_pattern_detect` investigation framing error.

---

## §4 Operator-paired triage gate (post-handback; pre-Phase-3)

Per V2 OHLCV writing-plans precedent: plan handback triggers operator-paired Turn D triage of any plan-phase OQs OR amendments to the LOCKED brainstorming OQs. Default expectation: ZERO amendments to LOCKED OQs (mirrors V2 OHLCV's 18-OQ-LOCKED achievement).

Plan-phase OQs (if any surface) are SECONDARY to brainstorming OQs; they cover plan-level decisions (e.g., commit-cadence preferences, test-budget exceptions, dispatch sequencing for Phase 3) NOT architectural decisions (which are locked at brainstorming).

---

## §5 NON-scope

- ZERO modification of LOCKED brainstorming OQ dispositions
- ZERO implementation work (Phase 3 executing-plans only)
- ZERO new architectural decisions beyond what spec §A-§N already covers
- ZERO Schwab API integration changes
- ZERO new schema migrations
- ZERO modification of V1 persisted state
- ZERO production swing/ writes beyond what OQ-13 banks (executing-plans will land the carve-out)
- ZERO scope creep into Option A (warnings_json visibility fix; SEPARATE dispatch at `e374974`)
- ZERO scope creep into Option C (pool-predicate widening; SEPARATE dispatch banked)

---

## §6 Post-plan handback

When plan + return report + (optional) Codex chain shipped:

1. Inline self-verification: ruff check (if any script lands); schema unchanged; ZERO new Schwab API calls; ZERO Co-Authored-By footer; LOCKED OQs preserved
2. Hand back to operator with: plan section inventory + per-OQ disposition verification + Codex chain shape if invoked + banked V1 simplifications + banked patterns + discipline deviations if any.

Orchestrator-side next steps post-handback:
- QA plan per `feedback_orchestrator_qa_implementer_product`
- Merge plan branch `--no-ff` to main; push
- Post-merge housekeeping (sub-event scale; in-place amendments)
- Phase 3 executing-plans dispatch brief authored
- Phase 3 executing-plans dispatch ships harness + tests + CLI + smoke + method-record + study writeup + return report

---

*End of pattern cohort detector evaluator Phase 2 writing-plans dispatch brief. Consumes 996-line brainstorming-phase spec as BINDING substrate. All 13 OQ dispositions LOCKED per operator triage 2026-05-24 PM with ZERO amendments (mirrors V2 OHLCV 18-OQ-LOCKED precedent). Plan output is the implementation blueprint for Phase 3 executing-plans. ~518+ ZERO Co-Authored-By footer streak preserved through this brief commit.*
