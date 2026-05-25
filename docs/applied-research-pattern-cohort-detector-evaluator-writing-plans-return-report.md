# Pattern Cohort Detector Evaluator Research Harness -- Writing-Plans Return Report

**Status:** Phase 2 (writing-plans) COMPLETE. Ready for operator QA + plan review + Phase 3 (executing-plans) commission.

**Branch:** `applied-research-pattern-cohort-detector-evaluator-writing-plans` (branched from main HEAD `16f9efc`).

**Worktree HEAD at handback:** see commit list at §1 below.

**Deliverable:** [`docs/superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md`](superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md) -- 2948 lines; 15 sections §A-§O including self-review per superpowers:writing-plans final step gate.

**Workflow:** `superpowers:writing-plans` (NOT `copowers:writing-plans`); operator-paired discretion per dispatch brief §0 + §2.3 "OPTIONAL via copowers:writing-plans wrapper". Operator chose to run writing-plans-phase WITHOUT adversarial Codex MCP review (mirrors brainstorming-phase choice 2026-05-24); 38th cumulative C.C lesson #6 validation slot REMAINS RESERVED for executing-plans phase OR retroactive Codex review at operator's discretion.

---

## §1 Commit chain shape

2 commits in this dispatch arc (excluding the return-report commit which is THIS commit):

| # | Commit | Phase | Summary |
|---|--------|-------|---------|
| 1 | (pending) | Initial plan | docs(applied-research): pattern cohort detector evaluator harness writing-plans plan (2948 lines; 15 sections §A-§O; 13 OQ dispositions LOCKED verbatim from brainstorming spec) |
| 2 | THIS COMMIT | Return report | docs(applied-research): pattern cohort detector evaluator writing-plans return report |

ALL commits authored WITHOUT `Co-Authored-By` trailer per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15). Cumulative ~519+ ZERO `Co-Authored-By` footer streak preserved through this dispatch.

---

## §2 Plan section inventory

The plan has 15 sections §A-§O per V2 OHLCV writing-plans precedent structural template:

| § | Section | Line range (approx) | Content |
|---|---------|---------------------|---------|
| A | Status + scope (binding context) | 18-72 | Lineage + research question addressed + production read-only invariant + 13 OQ dispositions LOCKED + schema discipline + V1 persisted state read-only + streaks preserved |
| B | Per-sub-bundle file map + dependency graph | 74-130 | 13-row file map table (NEW + MODIFIED surfaces) + 7-row test path table + sequential dependency graph |
| C | Module function signatures + class shapes (BINDING) | 132-823 | 6 modules' Python signatures verbatim: exceptions.py + ohlcv_reader.py (re-export) + cohort_reader.py + detector_invoker.py + output.py + run.py |
| D | SQL skeleton verification | 826-878 | Mode (c) SQL deferred V2.5+ disposition; production-helper SQL consumed transitively via current_stage + list_exemplars; empty-input handling per cumulative gotcha #20 |
| E | Production function signature verification (Expansion #2 refinement BINDING) | 880-1058 | 8 production functions verified (6 invocations + 1 NEGATIVE-verification + 1 Config); cascade-call-graph audit per cumulative gotcha #19 |
| F | L2 LOCK reinforcement (5 BINDING discriminating tests) | 1060-1230 | 5 BINDING tests: re-export identity + file-open boundary mock + import-graph mock + byte-checksum + production signature locks |
| G | Per-task acceptance criteria + bite-sized step structure | 1232-2128 | 5 sub-bundles decomposed into 6 tasks (T-PC.1.1 + T-PC.1.2 + T-PC.2 + T-PC.3 + T-PC.4 + T-PC.5); commit-cadence preface; bite-sized TDD slices with verbatim test + impl code |
| H | Test scope per-task budget | 2130-2150 | ~61 NEW fast tests per-test enumeration (parametrize-consolidated bound ~50-55) |
| I | Plan-phase OQ work-items resolved | 2152-2188 | Codex round-budget at §N + CLI flag tuning + test-budget refinement RESOLVED; --max-runtime-seconds V1 DEFERRED disposition |
| J | Forward-binding lessons inherited | 2190-2245 | 27-row cumulative gotcha disposition table (1-27); per-gotcha plan application; process discipline citations |
| K | L2 LOCK reinforcement (5 BINDING tests; cross-reference §F) | 2247-2272 | Summary cross-reference to §F.1-§F.5 |
| L | Research-branch coordination | 2274-2330 | NEW method-record + first study writeup + phase-0-tasks.md "Next" refresh + first-cohort substrate CSV + operator smoke run capture |
| M | Closure procedure | 2332-2365 | 8-step T-PC.5 closer checklist + post-closer orchestrator housekeeping |
| N | Per-sub-bundle Codex MCP round-budget expectation | 2367-2387 | 5-sub-bundle Codex round estimate (8-14 cumulative); 2-5 rounds for writing-plans phase if commissioned |
| O | Self-review (BINDING per superpowers:writing-plans final step) | 2389-2454 | §O.1 spec coverage check + §O.2 placeholder scan + §O.3 type consistency + §O.4 per-cumulative-gotcha disposition check |

---

## §3 Per-OQ verification (all 13 LOCKED + carried forward)

All 13 brainstorming-phase OQ dispositions LOCKED at operator triage 2026-05-24 PM (per dispatch brief §1 + brainstorming return report §2). This plan carries them forward VERBATIM with ZERO amendments (mirrors V2 OHLCV 18-OQ-LOCKED precedent through 3 phases).

| OQ | LOCKED disposition (verbatim) | Plan section binding |
|---|-------|-----------|
| OQ-1 | Direct production detector function invocation (re-import `_pattern_detect_registry`) | §A.4 + §C.4 `get_detector_registry()` + §E.1 + §F.5 |
| OQ-2 | V1 = Mode (b) CSV primary + Mode (a) inline fallback; Mode (c) SQL deferred V2.5+ | §A.4 + §C.3 + §D.1 |
| OQ-3 | Re-export V2 OHLCV evaluator's `ohlcv_reader.py` VERBATIM | §A.4 + §B.1 + §C.2 + §F.1 |
| OQ-4 | Mirror production `zigzag_pivot` only; multi-mode deferred V2.5+ | §A.4 + §C.4 invoke_cohort step 2 + §E.2 |
| OQ-5 | Per-entry CSV column + CLI global; per-entry takes precedence | §A.4 + §C.3 + §C.4 + §G T-PC.2 step 13 |
| OQ-6 | Default `--template-match=on` (production-parity) | §A.4 + §C.4 + §C.6 + §G T-PC.2 step 15 |
| OQ-7 | Default `--window-mode=per-window` (NON-production-default; deliberate per analytical purpose) | §A.4 + §C.6 + §G T-PC.2 step 14 |
| OQ-8 | Default production `current_stage`; per-entry `stage_override` deferred V2.5+ | §A.4 + §C.4 + §E.3 + §G T-PC.2 step 16 |
| OQ-9 | First-cohort = +67 watch→aplus flips at `vcp.tightness_range_factor=1.005` (15 unique tickers) | §A.4 + §L.4 + §G T-PC.5 step 5 |
| OQ-10 | CLI subcommand = `swing diagnose pattern-cohort-detect` | §A.4 + §C.6 + §G T-PC.4 step 8 |
| OQ-11 | Inherit V2 OHLCV evaluator's `BothExistDiagnostic` surface | §A.4 + §C.2 + §C.4 + §C.5 manifest schema |
| OQ-12 | Uniform empty-state per T3.SB3 LOCK: `(none)` markdown / `null` CSV / `None` JSON | §A.4 + §C.5 + §G T-PC.3 |
| OQ-13 | CLI subcommand registration = sole production-`swing/`-write carve-out per OQ-17 V2 OHLCV precedent | §A.3 + §A.4 + §B.1 + §G T-PC.4 step 8 |

ZERO amendments to LOCKED OQs. Plan-phase secondary OQs (if any surfaced) covered in §I:
- §I.1 Per-sub-bundle Codex round-budget RESOLVED at §N.
- §I.2 Module function signatures + class shapes RESOLVED at §C BINDING.
- §I.3 CLI flag naming + default value tuning RESOLVED at §C.6.
- §I.4 Per-task test-budget refinement RESOLVED at §H.

NEW disposition decision (plan-phase): `--max-runtime-seconds N` proposed in spec §C.5 but DEFERRED V1 per §I.3 with V2.5 banking justification — harness has simpler runtime profile (no sweep loop multiplying work); first-cohort target is small (67 entries); runtime budget < 5 min projected; operator may revisit if larger cohorts surface.

---

## §4 Cumulative C.C lesson #6 validation status

Writing-plans phase = NO Codex MCP review fired per operator-paired discretion (dispatch brief §0 + §2.3 OPTIONAL). The 38th cumulative C.C lesson #6 validation slot REMAINS RESERVED for the executing-plans phase OR a retroactive Codex chain on the plan at Turn D.

Pre-Codex 7-expansion + 5 NEW candidate refinements DISCIPLINE applied at plan-write time (orchestrator-side review; per the discipline established at V2 OHLCV evaluator writing-plans):

| # | Expansion | Writing-plans-phase pre-Codex disposition |
|---|-----------|------------------------------------------|
| 1 | Hardcoded-duplicate audit | APPLIED at §J.1 row #15 (Expansion #11): `_SKIP_REASONS` + `_ALLOWED_PATTERN_CLASSES` enumerated as module-level frozensets at single source-of-truth + propagated through dataclass + CSV header + test fixtures (NO hardcoded duplicates). |
| 2 | Brief-vs-spec + brief-vs-actual-production-function-signature verification | APPLIED at §E (6 production functions verified via inspect.signature + typing.get_type_hints + cascade-call-graph audit; 1 NEGATIVE verification at §E.7). Plan body verified against spec §B.1 + §C + §D + §E + §F + §I.2-§I.4 verbatim. |
| 3 | Schema-CHECK vs semantic-contract gap | N/A this dispatch (no schema change; production `_step_pattern_detect` STAYS aplus-only per spec §A.4). |
| 4 | Specific-scenario gotcha trace + SQL skeleton column verification | APPLIED at §D (no Mode (c) SQL in V1; transitive SQL through current_stage + list_exemplars enumerated). |
| 5 | Cross-section spec inventory grep | APPLIED at §O.1 spec coverage check (14 spec sections §A-§N each mapped to plan section). |
| 6 | Content-completeness audit | APPLIED at §O — every spec data-surface enumeration checked against plan rendering disposition. |
| 7 | Cross-row semantic SCOPE audit | N/A this dispatch (no operator-input POST handler; pure CLI invocation). |
| 8 (BINDING via #22) | Per-aggregation-function UNIT audit (Expansion #8 promotion: per-counter accumulation) | APPLIED at §J.1 row #22 + §C.4 `CohortRunResult` per-counter unit enumeration + §G T-PC.2 step 18 (detector_error_all fires ONLY when ALL attempted detectors raise; per-counter-accumulation discriminating test). |
| 9 (cand) | Form-render anchor lifecycle 4-dimension audit | N/A (no forms / web routes). |
| 10 (BINDING via #14) | Architecture-location audit + 5 sub-disciplines | APPLIED at §B.1 + spec §B.1 dependency surface table inherited + §J.1 row #14. Sub-discipline (e) orphan-label preservation mapped to per-skip-reason counters at §C.4. |
| 11 (BINDING via #15 + #23) | Taxonomy propagation audit + dataclass attribution metadata audit | APPLIED at §J.1 rows #15 + #23 + §C.4 `_SKIP_REASONS` + §C.3 `_ALLOWED_PATTERN_CLASSES` + §C.5 `_CSV_HEADERS` 24-tuple — each enum value propagated through dataclass __post_init__ + CSV header + markdown rendering + test fixtures + discriminating tests at §G T-PC.1.2 step 7 + §G T-PC.2 step 7. |
| 12 (cand) | Sibling-route audit when introducing single-anchor-binding discipline | N/A (no route handlers; no single-anchor invariant). |
| 13 (cand) | Cumulative regression cascade audit | Banked for executing-plans phase post-Codex-fix discipline. |
| 14 (BINDING via #17) | Expansion #2 refinement (signature) | APPLIED at §E + §F.5 + §J.1 row #17. |
| 15 (BINDING via #18) | Expansion #4 refinement (JOIN-cardinality) | APPLIED at §D + §J.1 row #18 (production-helper SQL consumed transitively; cardinality verified). |
| 16 (BINDING via #19) | Expansion #2 sub-refinement (cascade-call-graph) | APPLIED at §E.1-§E.6 — for each production function, cascade behavior verified explicitly + §F.5 discriminating test asserts registry length + tuple equality. |
| 17 (BINDING via #20) | Expansion #4 sub-refinement (runtime-binding-shape + empty-result-set) | APPLIED at §D.3 + §G T-PC.1.2 step 7 + §G T-PC.2 step 18 (3 empty-input cases enumerated + discriminating tests). |

Note: per the dispatch brief BINDING (38th cumulative C.C lesson #6 validation across the 3 phases IF Codex invoked), the orchestrator-side pre-Codex review applied is documented above for the writing-plans phase. Executing-plans phase inherits; Codex invocation operator-paired per phase.

---

## §5 V1 simplifications + V2/V3 candidates banked

9 V2/V3-dependency-cited candidates banked per cumulative discipline (every V1 simplification cites its V2/V3 dependency). Inherited from brainstorming return report §5 + 1 NEW writing-plans-phase candidate:

| # | V1 simplification | V2/V3 dependency citation |
|---|-------------------|---------------------------|
| 1 | V1 ships Mode (a) inline + Mode (b) CSV cohort input only | V2.5+ candidate: Mode (c) SQL query per dispatch brief §1.6 + OQ-2 + plan §D.1 |
| 2 | V1 mirrors production `zigzag_pivot` anchor mode only | V2.5+ candidate: multi-mode per OQ-4 + plan §E.2 |
| 3 | V1 OHLCV reader re-exports V2 OHLCV evaluator's reader (per OQ-3 (a)) | V2.5+ ALTERNATIVE: separate minimal reader (operator-paired triage if cross-research-module dependency becomes undesirable) |
| 4 | V1 `current_stage` lookup uses production semantics | V2.5+ candidate: per-entry `stage_override` per OQ-8 + plan §E.3 |
| 5 | V1 invokes ALL 5 detectors per cohort entry (unless per-entry filter set) | NONE -- permanent V1 design |
| 6 | V1 reads CURRENT `pattern_exemplars` corpus at invocation time | V2.5+ candidate: pinned-corpus snapshot per spec §D.4 corpus drift caveat |
| 7 | V1 reads CURRENT OHLCV archive at invocation time | V2.5+ candidate: immutable archive snapshot per cumulative gotcha #26 family |
| 8 | V1 first-cohort target = 67 watch→aplus flips at vcp.tightness_range_factor=1.005 | NEXT-cohort candidates banked: +16 `vcp.tightness_days_required`; +11 `vcp.adr_min_pct`; +5 `vcp.proximity_max_pct`; +1 `vcp.orderliness_max_bar_ratio` (V2 OHLCV sensitivity full-reproduction binding variables) |
| **9 NEW** (writing-plans) | **V1 omits `--max-runtime-seconds N` CLI flag** (proposed in spec §C.5 but harness runtime profile is small) | V2.5+ candidate: add `--max-runtime-seconds` IF operator finds the harness becomes long-running on larger cohorts; mirrors V2 OHLCV evaluator OQ-9 implementation per plan §I.3. |

---

## §6 Banked patterns for executing-plans phase

5 NEW writing-plans-phase patterns banked at this plan (per V2 OHLCV writing-plans return report §4 precedent):

1. **Identity-preserving re-export verification via `is` operator** — when one research-branch harness re-exports another's L2-LOCK-preserving infrastructure, the discriminating test must assert IDENTITY (`is` operator) not equality (`==`). Identity verification catches accidental shadow re-implementation that would bypass the source-of-truth tests. Pattern at plan §F.1; first canonical application post-V2 OHLCV evaluator (which had no re-export pattern; this harness ESTABLISHES the pattern for future re-exports).

2. **Production-parity invariant at per-verdict level (not per-bucket)** — V2 OHLCV evaluator's invariant operates at the BUCKET level (sentinel-bucket filtering per gotcha #25); this harness's invariant operates at the per-(geometric_score, composite_score, structural_evidence_json) verdict level. Both are valid; the per-verdict invariant is finer-grained but requires bit-identical OHLCV archive + pattern_exemplars corpus per spec §E.1 scoping (5 conditions). Pattern banked for future research-branch harnesses that consume per-row production output (NOT per-cohort bucket aggregates).

3. **Re-import-cascade-call-graph audit pattern for production registries** — per cumulative gotcha #19 (BINDING): when a harness re-imports a production registry function (e.g., `_pattern_detect_registry`), the discriminating test MUST assert (a) function body returns expected tuple length; (b) tuple-element pattern_classes match expected set; (c) `inspect.signature` parameter set unchanged. Pattern at plan §E.1 + §F.5. Banked for future research-branch harnesses that re-import production registries (e.g., a hypothetical V2.G dispatch that re-imports production cfg registry).

4. **Per-counter-accumulation unit discriminator for entry-level vs verdict-level skip semantics** — per cumulative gotcha #22 (BINDING + V2 OHLCV evaluator R1.M2 inflation-by-N direct evidence): when a harness emits BOTH entry-level skip rows AND per-(entry, pattern_class, window) non-skip verdict rows, the per-skip-reason counter MUST accumulate at the entry level NOT per-row. Plan enforces via §C.4 `CohortRunResult.skipped_entries` (entry-level) vs `verdicts_emitted` (row-level) + §G T-PC.2 step 18 discriminating test. The `detector_error_all` skip reason has its own discipline (fires ONLY when ALL attempted detectors raise; partial detector failures yield per-row skip-flag NOT entry-level skip). Pattern banked for future harnesses with mixed entry-level + row-level emission.

5. **Production-helper SQL transitively-consumed audit pattern** — per cumulative gotcha #18 (BINDING): when a harness consumes production SQL transitively (via production helper invocation, e.g., `current_stage`, `list_exemplars`), the SQL skeleton verification surface is at the PRODUCTION FUNCTION boundary not the harness boundary. Plan §D.2 enumerates JOIN-cardinality + downstream-sufficiency for `current_stage` (1:1 JOIN) + `list_exemplars` (no-JOIN); no harness-side SQL skeleton verification needed because transitive SQL is owned by the production function's own test surface. Pattern banked for future harnesses that consume production helpers rather than authoring SQL directly.

---

## §7 Cumulative streaks preserved

- **ZERO `Co-Authored-By` footer trailer**: ~519+ commits cumulative through this dispatch (2 commits added in this writing-plans phase; ZERO with co-author trailer).
- **Schema v21 UNCHANGED**: writing-plans docs-only; no migration files touched. Verified via `grep -h "UPDATE schema_version SET version" swing/data/migrations/*.sql` → latest is `version = 21`.
- **Baseline ~5893 fast tests UNCHANGED**: writing-plans docs-only; no test files touched. Executing-plans phase will land +55-61 fast tests (~5944-5954 total post-harness-ship per plan §H + §J.3).
- **ZERO new Schwab API calls (L2 LOCK preserved)**: harness design re-exports V2 OHLCV evaluator's L2-LOCK-preserving reader per OQ-3 (a); 5 BINDING discriminating tests at plan §F + §K verify at harness ship time. Writing-plans phase ZERO new Schwab API calls (docs-only).
- **ZERO production code changes**: only `docs/superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md` + `docs/applied-research-pattern-cohort-detector-evaluator-writing-plans-return-report.md` touched in this dispatch arc. The CLI subcommand registration in `swing/cli.py` is BANKED for executing-plans phase per OQ-13 explicit carve-out (NOT shipped in writing-plans).
- **V1 persisted state untouched**: ZERO modification of `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / `pattern_evaluations` / V1 persisted state per dispatch brief §3.5 BINDING.

---

## §8 Inline self-verification (per dispatch brief §6 Phase 2 handback discipline)

### §8.1 Schema unchanged at v21

Verified — ZERO migration files added in this dispatch arc. Writing-plans docs-only. Latest schema per `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql` → `UPDATE schema_version SET version = 21`.

### §8.2 Test baseline matches pre-writing-plans

Writing-plans docs-only; ZERO test files touched. Baseline ~5893 fast tests UNCHANGED through this dispatch phase. Executing-plans phase will land +55-61 fast tests per plan §H.

### §8.3 ZERO new Schwab API calls

Harness design preserves L2 LOCK via OQ-3 (a) re-export. 5 BINDING discriminating tests at plan §F + §K verify at harness ship time. Writing-plans phase ZERO new Schwab API calls (no Python code touched).

### §8.4 ZERO Co-Authored-By footer

The 2 commits in this dispatch arc (plan + this return report) authored WITHOUT `Co-Authored-By` trailer. Cumulative ~519+ ZERO-streak preserved.

### §8.5 ASCII vs cp1252 discipline

Plan body uses `§` (section sign) glyph (U+00A7) extensively per V2 OHLCV evaluator plan precedent. Per cumulative Windows PowerShell stdout safety gotcha: `§` is cp1252-decodable AND markdown does NOT go through stdout (only `click.echo()` / `print()` paths matter). Plan body is safe per the gotcha's allow-in-markdown-disallow-on-stdout discipline. No other non-ASCII glyphs introduced.

The runtime CLI paths (Python source code shown in §C + §G) use ASCII-only per `output.py` `body.encode('cp1252')` sanity check at `write_summary_markdown` + cumulative gotcha discipline.

### §8.6 LOCKED OQs preserved

All 13 brainstorming-phase OQ dispositions LOCKED + carried forward verbatim per §3 above. ZERO amendments. Mirrors V2 OHLCV 18-OQ-LOCKED 3-phase precedent.

### §8.7 OQ-13 production-`swing/` carve-out scope respected

Plan §A.3 + §B.1 + §G T-PC.4 step 8 BIND the OQ-13 carve-out scope to `swing/cli.py` only (35-60 lines mirror V2 OHLCV evaluator's `aplus-sensitivity-v2` precedent at `swing/cli.py:4791-4859`). Discriminating gate at T-PC.4 ship: `git diff swing/ --stat` shows ONLY `swing/cli.py` modified (per V2 OHLCV plan §A.3 precedent).

---

## §9 Discipline deviations (if any)

ZERO discipline deviations surfaced during this writing-plans phase.

Per V2 OHLCV writing-plans return report §3 precedent (which had ZERO deviations at writing-plans phase + multiple deviations BANKED at executing-plans phase via Codex chain), this writing-plans phase is CLEAN. Any deviations surfaced in executing-plans phase will be BANKED in the executing-plans return report per cumulative discipline.

---

## §10 Forward-binding lessons banked

1. **Re-export pattern formalization for shared L2 LOCK infrastructure** — per OQ-3 (a) LOCK: if two research-branch harnesses both need L2-LOCK-preserving OHLCV reads, the second harness re-exports the first's reader rather than duplicate the L2 LOCK 5 BINDING discriminating test surface. Pattern at plan §C.2 + §F.1. Banked for future research-branch arcs.

2. **Production-parity invariant at per-verdict level (per §6 pattern #2)** — banked for any harness whose output joins by per-row identity NOT bucket aggregate.

3. **Architectural answer to gotcha #27 modeled in harness's own audit-row discipline** — gotcha #27's silent-skip-without-audit pattern motivates THIS harness AND the harness models the discipline via per-skip-reason counters + per-entry skip-row CSV emission at plan §C.4 + §G T-PC.2 + §C.5 markdown skip-reason summary. The harness's existence is gotcha #27's architectural answer; the harness itself models the audit-row discipline per the gotcha banking.

4. **Detector registry re-import + cascade-call-graph audit pattern** — per OQ-1 + plan §D.2 + §E.1, the harness re-imports `_pattern_detect_registry()` from production rather than re-derive. Pattern banked: future research-branch harnesses that consume a stable production function set should re-import rather than re-derive (zero-drift discipline; cascade-call-graph audit per cumulative gotcha #19 BINDING).

5. **Two-phase Applied Research arc precedent established** — V2 OHLCV evaluator was the first arc post-Phase-13-FULLY-CLOSED (`362fe18` → `34f177c` → `a43a921`); pattern cohort detector evaluator is the SECOND arc (brainstorming `18cb49e` → writing-plans THIS commit → executing-plans pending). Both arcs are 3-phase: brainstorming → writing-plans → executing-plans. Future applied-research arcs inherit this pattern. The architectural template lives in `research/harness/` + `docs/superpowers/specs/` + `docs/superpowers/plans/` + `research/method-records/` + `research/studies/` per V2.1 §V.

---

## §11 Handback to operator

Pattern cohort detector evaluator research harness writing-plans phase SHIPPED. Plan self-reviewed per superpowers:writing-plans §O gate; ALL placeholder + type-consistency + spec-coverage + per-cumulative-gotcha disposition checks passed.

### §11.1 Orchestrator next-steps (per dispatch brief §6 Phase 2 handback sequence)

- **QA implementer product** per `feedback_orchestrator_qa_implementer_product` BINDING (verify file:line + plan §C signatures + 13-OQ LOCKED dispositions + brief-framing accuracy verification + cumulative gotcha citations against reality on disk).
- **Merge `applied-research-pattern-cohort-detector-evaluator-writing-plans` `--no-ff` to `main`**; push.
- **Post-merge housekeeping** bundle if needed (CLAUDE.md line 3 refresh — second Applied Research arc writing-plans SHIPPED; phase3e-todo.md NEW top entry; orchestrator-context.md current state refresh; Prior demote + archive-split per size-check trigger).
- **Operator-paired plan review** — default expectation: ZERO amendments to LOCKED brainstorming OQs (per V2 OHLCV writing-plans precedent). Plan-phase OQs (per plan §I) RESOLVED in this dispatch.
- **Draft executing-plans dispatch brief** consuming the operator-affirmed writing-plans plan.
- **Provide inline implementer dispatch prompt** for executing-plans phase (per `feedback_always_provide_inline_dispatch_prompt`).

### §11.2 Summary

Pattern cohort detector evaluator research harness writing-plans plan is the SECOND applied-research arc post-Phase-13-FULLY-CLOSED Phase 2 deliverable, following the V2 OHLCV criterion-evaluator arc precedent. Plan covers all 15 sections §A-§O per V2 OHLCV writing-plans structural template + superpowers:writing-plans §O self-review gate. ALL 13 brainstorming-phase OQ dispositions LOCKED + carried forward verbatim with ZERO amendments. NEW plan-phase disposition: `--max-runtime-seconds N` V1 DEFERRED per §I.3 (V2.5+ candidate banked).

Writing-plans-phase Codex MCP review was OPTIONAL per dispatch brief §2.3; operator-paired discretion = NOT commissioned this phase. Pre-Codex 7-expansion + 5 NEW candidate refinements discipline applied at plan-write time per §4 disposition table. 38th cumulative C.C lesson #6 validation slot REMAINS RESERVED for executing-plans phase.

Schema v21 UNCHANGED; baseline ~5893 fast tests UNCHANGED; ZERO new Schwab API calls; ZERO Co-Authored-By footer; ZERO production code changes (CLI subcommand registration BANKED for executing-plans per OQ-13). 5-sub-bundle decomposition at plan §B.2 + §G (~56-67 commits projected; ~61 fast tests at parametrize-consolidated bound). NEW method-record at plan §L.1 (key `pattern-cohort-detection`; version 0.1.0; status `research`). Study writeup template at plan §L.2.

5 BINDING L2 LOCK discriminating tests enumerated at plan §F + §K (re-export identity + file-open boundary mock + import-graph mock + byte-checksum + production signature locks per cumulative gotcha #17 + #19); operator-witnessed-gate blocking per V2 OHLCV evaluator L2 LOCK precedent.

Ready for operator-paired plan review + executing-plans dispatch brief drafting.

---

*End of pattern cohort detector evaluator research harness writing-plans return report. Plan at [`docs/superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md`](superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md) (2948 lines; 15 sections §A-§O; ALL 13 brainstorming-phase OQ dispositions LOCKED + carried forward verbatim with ZERO amendments). SECOND applied-research arc post-Phase-13-FULLY-CLOSED Phase 2 deliverable, following V2 OHLCV criterion-evaluator arc precedent. Writing-plans-phase Codex MCP review OPTIONAL per dispatch brief §2.3 + operator-paired discretion; NOT fired this phase. ~519+ ZERO Co-Authored-By footer streak preserved.*
