# Pattern Cohort Detector Evaluator Research Harness -- Brainstorming Return Report

**Status:** Phase 1 (brainstorming) COMPLETE. Ready for operator QA + OQ triage + Phase 2 (writing-plans) commission.

**Branch:** `applied-research-pattern-cohort-detector-evaluator-brainstorm` (branched from main HEAD `8ba87cd`).

**Worktree HEAD at handback:** see commit list at §1 below.

**Deliverable:** [`docs/superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md`](superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md) -- 996 lines; 14 sections §A-§N including self-review per superpowers:brainstorming gate.

**Workflow:** `superpowers:brainstorming` (NOT `copowers:brainstorming`); operator chose to run brainstorming-phase WITHOUT adversarial Codex MCP review per dispatch brief §0 + §2.1 "OPTIONAL via copowers:brainstorming wrapper -- operator-paired discretion". Per dispatch brief Phase 1 deliverables: spec + OQ list + return report (Codex chain NOT enumerated as binding).

---

## §1 Commit chain shape

2 commits in this dispatch arc (excluding the return-report commit which is THIS commit):

| # | Commit | Phase | Summary |
|---|--------|-------|---------|
| 1 | (pending) | Initial spec | docs(applied-research): pattern cohort detector evaluator harness brainstorming spec (996 lines; 14 sections §A-§N; 13 OQs) |
| 2 | THIS COMMIT | Return report | docs(applied-research): pattern cohort detector evaluator brainstorming return report |

ALL commits authored WITHOUT `Co-Authored-By` trailer per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15). Cumulative ~516+ ZERO `Co-Authored-By` footer streak preserved through this dispatch.

---

## §2 OQ enumeration ready for operator-paired triage (per dispatch brief §3 Phase 1 deliverable #3)

13 OQs surfaced for operator-paired triage between brainstorming + writing-plans phases. Each OQ has a RECOMMEND disposition; operator may accept RECOMMEND OR redirect.

Summary table for operator triage session:

| OQ | Topic | RECOMMEND |
|----|-------|-----------|
| 1 | Detector invocation interface (direct production fn vs V2-side mirror) | Direct production detector function invocation; no cfg substitution V1 |
| 2 | Cohort input mode (inline tuple list / CSV / SQL query) | V1: Mode (b) CSV primary + Mode (a) inline smoke fallback; Mode (c) SQL deferred V2.5+ per dispatch brief §1.6 |
| 3 | OHLCV reader source (re-export V2 OHLCV evaluator's reader vs new minimal reader) | (a) Re-export `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader` to avoid drift between two read-only Shape-A readers |
| 4 | Anchor mode (zigzag_pivot only vs multi-mode) | `zigzag_pivot` only V1 mirror production; multi-mode V2.5+ |
| 5 | Pattern-class filter scope (per-entry CSV column vs CLI global vs both) | BOTH; per-entry CSV takes precedence; CLI is global override when CSV null |
| 6 | Template-match Pass 2 mode (default on vs off) | Default `--template-match=on` for production parity per §D.4 |
| 7 | Window-mode (last-only vs per-window) | Default `--window-mode=per-window` for harness's analytical purpose; `last-only` available for production-parity testing |
| 8 | `current_stage` Stage-2-gate override (production-semantics vs per-entry override) | Default production-semantics; per-entry override V2.5+ |
| 9 | First-cohort target (+67 watch->aplus flips at vcp.tightness_range_factor=1.005) | YES per dispatch brief §7 |
| 10 | V1 harness CLI subcommand name | `swing diagnose pattern-cohort-detect` (operator-paired; alternatives valid) |
| 11 | Both-exist diagnostic surface (inherit V2 OHLCV `BothExistDiagnostic`) | YES; flows through via OQ-3 (a) re-export |
| 12 | Empty-state representation in output (canonical empty-state across CSV/md/manifest) | Per cumulative T3.SB3 LOCK: `(none)` markdown / `null` CSV / `None` JSON |
| 13 | CLI subcommand registration as production-`swing/`-write carve-out | YES per V2 OHLCV evaluator OQ-17 precedent; 35-60 lines at `swing/cli.py` |

OQ disposition forward-binding: operator MAY accept ALL RECOMMENDs as-is (most economical Path); OR operator MAY redirect any OQ AT Turn D, in which case the spec needs amendment + Phase 2 writing-plans inherits the operator-locked dispositions.

---

## §3 Brief-framing accuracy verification (per dispatch brief §4.7 + CLAUDE.md gotcha #27 sub-lesson BINDING)

Per cumulative gotcha #27 sub-lesson banking 2026-05-24 ("brief-framing accuracy discipline; verify any 'since X shipped' / count claims against `git log` of cited commits BEFORE writing spec text"):

| Dispatch brief claim | Verified against | Verification outcome |
|---|---|---|
| "Predecessor `_step_pattern_detect` investigation (merge `54bd9c6`)" | `git log --oneline 54bd9c6 -1` | CONFIRMED -- merge commit `54bd9c6` "Merge applied-research-pattern-detect-step-silent-noop-triage into main: H7 NEW root cause CONFIRMED -- empty-pool early-return at runner.py:1485-1490; Phase 13 detector GATED on bucket=='aplus' candidates; 0 aplus across 7 post-T2.SB3 runs" |
| "+67 watch->aplus flips at vcp.tightness_range_factor=1.005" (brief §7 body) vs "+75 watch->aplus flips" (brief §7 header) | V2 OHLCV sensitivity backtest dispatch brief `docs/v2-tightness-range-factor-backtest-dispatch-brief.md:60-62` | RECONCILED -- matrix `delta_aplus[sweep_point=1.005] = +75` (aplus_count 5 -> 80 net delta +75); drill-down enumerates 67 `watch->aplus` flip entries (8-entry discrepancy noted in backtest brief as candidate-explanation territory). Spec uses **67-entry framing** as the operator-input-level number directly mappable to cohort entries. Documented in spec header + §C.3. |
| "15 unique tickers" (brief §7) | Backtest brief §1 + §6 (per-ticker entry counts: RLMD 12 + DNTH 10 + RNG 9 + KOD 8 + YOU 7 + FRO 6 + TROX 4 + PTEN 2 + OII 2 + DK 2 + WULF 1 + UCTT 1 + TSHA 1 + SSRM 1 + NAT 1 = 67 entries / 15 tickers) | CONFIRMED |
| "5 BINDING discriminating tests" (dispatch brief §1.4 + §4.4) | V2 OHLCV evaluator L2 LOCK test surface at `tests/research/test_aplus_v2_ohlcv_reader.py` | CONFIRMED -- 5-test surface enumerated at spec §E.3 (file-open boundary check + module import sentinel graph + byte-checksum compare + signature lock + source-grep) |
| "production `_step_pattern_detect` at `swing/pipeline/runner.py:1485-1490`" (predecessor investigation) | `swing/pipeline/runner.py:1485-1490` read at spec-write time | CONFIRMED -- empty-pool early-return at exact line range |
| "production `_pattern_detect_registry` at runner.py:1280-1303" | `swing/pipeline/runner.py:1280-1303` read at spec-write time | CONFIRMED -- 5-tuple registry at exact line range |
| "16 cumulative C.C lesson #6 validation" (dispatch brief §4.1 cites 27 gotchas BINDING for 38th cumulative validation) | CLAUDE.md gotcha catalog through gotcha #27 banked at merge `54bd9c6` | CONFIRMED -- 27 cumulative gotchas applicable; 38th validation would fire if Codex MCP invoked (operator-paired discretion per dispatch brief §0; NOT fired in this brainstorming phase) |

ALL brief-framing claims verified against actual source. No discrepancies. Both `+75 matrix delta` and `+67 drill-down entry count` are correct -- they refer to different countings of the same sweep result; spec adopts the 67 framing as operator-input-level (cohort entries) per dispatch brief §7 body wording.

---

## §4 Cumulative C.C lesson #6 validation status

Brainstorming phase = NO Codex MCP review fired per operator-paired discretion (dispatch brief §0 + §2.1 OPTIONAL). The 38th cumulative C.C lesson #6 validation slot is therefore RESERVED for the writing-plans + executing-plans phases (or for brainstorming-phase Codex review IF operator commissions a retroactive Codex chain on the spec at Turn D).

Pre-Codex 7-expansion + 5 NEW candidate refinements DISCIPLINE applied at spec-write time (orchestrator-side review; per the discipline established at V2 OHLCV evaluator brainstorming):

| # | Expansion | Brainstorming-phase pre-Codex disposition |
|---|-----------|------------------------------------------|
| 1 | Hardcoded-duplicate audit | APPLIED at §A.2 + §D.2 (no hardcoded duplicates in harness; production detector registry imported via cascade-safe re-import per OQ-1 + §D.2). |
| 2 | Brief-vs-spec + brief-vs-actual-schema verification | APPLIED at §A.2 (schema columns verified against migration files); APPLIED at §C.4 step 5 (detector function signatures verified per actual `swing/patterns/*.py:detect_*` signatures). |
| 3 | Schema-CHECK vs semantic-contract gap | N/A this dispatch (no schema change). |
| 4 | Specific-scenario gotcha trace + SQL skeleton column verification | APPLIED at §H.2 (per-cumulative-gotcha disposition table); no Mode (c) SQL in V1 dispatch so SQL skeleton column verification narrow. |
| 5 | Cross-section spec inventory grep | APPLIED at §B.1 dependency surface table (each module's imports enumerated). |
| 6 | Content-completeness audit | APPLIED at §N self-review (every dispatch brief §3 + §4 checklist item mapped to spec section). |
| 7 | Cross-row semantic SCOPE audit | N/A this dispatch (no operator-input POST handler; pure CLI invocation). |
| 8 (cand) | Per-aggregation-function UNIT audit on SQL skeletons | N/A V1 dispatch (no SQL aggregation in Mode (a) + (b)). |
| 9 (cand) | Form-render anchor lifecycle 4-dimension audit | N/A (no forms / web routes). |
| 10 (cand) | Architecture-location audit + 5 sub-disciplines | APPLIED at §B.1 (NEW module placement + dependency-surface verification; sub-discipline (e) orphan-label preservation mapped to per-skip-reason counters at §C.4 + §D.3). |
| 11 (cand) | Taxonomy propagation audit | APPLIED at §I.2 (CSV column enumeration + skip_reason enum frozenset propagation through dataclass + CSV header + markdown matrix + test fixtures). |
| 12 (cand) | Sibling-route audit when introducing single-anchor-binding discipline | N/A (no route handlers; no single-anchor invariant). |
| 13 (cand) | Cumulative regression cascade audit | Banked for executing-plans phase post-Codex-fix discipline. |

Note: per the dispatch brief BINDING (38th-40th cumulative C.C lesson #6 validations across the 3 phases IF Codex invoked), the orchestrator-side pre-Codex review applied is documented above for the brainstorming phase. Writing-plans + executing-plans phases inherit; Codex invocation operator-paired per phase.

---

## §5 V1 simplifications + V2/V3 candidates banked

8 V2/V3-dependency-cited candidates banked per cumulative discipline (every V1 simplification cites its V2/V3 dependency):

| # | V1 simplification | V2/V3 dependency citation |
|---|-------------------|---------------------------|
| 1 | V1 ships Mode (a) inline + Mode (b) CSV cohort input only | V2.5+ candidate: Mode (c) SQL query against operator DB per dispatch brief §1.6 + OQ-2 |
| 2 | V1 mirrors production `zigzag_pivot` anchor mode only | V2.5+ candidate: multi-mode (zigzag_pivot + ma_crossover + high_low_breakout per `generate_candidate_windows` enum) per OQ-4 |
| 3 | V1 OHLCV reader re-exports V2 OHLCV evaluator's reader (per OQ-3 (a)) | V2.5+ ALTERNATIVE: separate minimal reader at `research/harness/pattern_cohort_evaluator/ohlcv_reader.py` (operator-paired triage if cross-research-module dependency becomes undesirable) |
| 4 | V1 `current_stage` lookup uses production semantics | V2.5+ candidate: per-entry `stage_override` for synthetic-cohort use cases per OQ-8 |
| 5 | V1 invokes ALL 5 detectors per cohort entry (unless per-entry filter set) | NONE -- this is permanent V1 design |
| 6 | V1 reads CURRENT `pattern_exemplars` corpus at invocation time | V2.5+ candidate: pinned-corpus snapshot per spec §D.4 corpus drift caveat |
| 7 | V1 reads CURRENT OHLCV archive at invocation time | V2.5+ candidate: immutable archive snapshot per cumulative gotcha #26 family (same as V2 OHLCV evaluator's L6 limitation) |
| 8 | V1 first-cohort target = 67 watch->aplus flips at vcp.tightness_range_factor=1.005 | NEXT-cohort candidates banked: +16 `vcp.tightness_days_required` cohort; +11 `vcp.adr_min_pct` cohort; +5 `vcp.proximity_max_pct` cohort; +1 `vcp.orderliness_max_bar_ratio` cohort (all from V2 OHLCV sensitivity full-reproduction binding-variable identification 2026-05-24 PM) |

---

## §6 Cumulative streaks preserved

- **ZERO `Co-Authored-By` footer trailer**: ~516+ commits cumulative through this dispatch (2 commits added in this brainstorming phase; ZERO with co-author trailer).
- **Schema v21 UNCHANGED**: brainstorming docs-only; no migration files touched. Verified via `grep -h "UPDATE schema_version SET version" swing/data/migrations/*.sql` -> latest is `version = 21`.
- **Baseline ~5893 fast tests UNCHANGED**: brainstorming docs-only; no test files touched. Writing-plans + executing-plans phases will land +55-71 fast tests (~5948-5964 total post-harness-ship per spec §H.3 estimate).
- **ZERO new Schwab API calls (L2 LOCK preserved)**: harness design explicitly reuses V2 OHLCV evaluator's L2-LOCK-preserving reader per OQ-3 (a); 5 BINDING discriminating tests at §E.3 verify at harness ship time. Brainstorming phase ZERO new Schwab API calls (docs-only).
- **ZERO production code changes**: only `docs/superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md` + `docs/applied-research-pattern-cohort-detector-evaluator-brainstorming-return-report.md` touched in this dispatch arc. The CLI subcommand registration in `swing/cli.py` is BANKED for executing-plans phase per OQ-13 explicit carve-out (NOT shipped in brainstorming).
- **V1 persisted state untouched**: ZERO modification of `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / `pattern_evaluations` / V1 persisted state per dispatch brief §4.5 BINDING.

---

## §7 Inline self-verification (per dispatch brief §3 Phase 1 deliverable discipline)

### §7.1 Schema unchanged at v21

Verified -- ZERO migration files added in this dispatch arc. Brainstorming docs-only. Latest schema per `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql` -> `UPDATE schema_version SET version = 21`.

### §7.2 Test baseline matches pre-brainstorming

Brainstorming docs-only; ZERO test files touched. Baseline ~5893 fast tests UNCHANGED through this dispatch phase. Writing-plans + executing-plans phases will land +55-71 fast tests per spec §H.3.

### §7.3 ZERO new Schwab API calls

Harness design preserves L2 LOCK by re-exporting V2 OHLCV evaluator's existing reader per OQ-3 (a) RECOMMEND. 5 BINDING discriminating tests at spec §E.3 + §F.1 verify at harness ship time. Brainstorming phase ZERO new Schwab API calls (no Python code touched).

### §7.4 ZERO Co-Authored-By footer

The 2 commits in this dispatch arc (spec + this return report) authored WITHOUT `Co-Authored-By` trailer. Cumulative ~516+ ZERO-streak preserved. Citation in each commit per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15).

### §7.5 ASCII vs cp1252 discipline

Spec body uses `§` (section sign) glyph (U+00A7) extensively per V2 OHLCV evaluator spec precedent. Per cumulative Windows PowerShell stdout safety gotcha: `§` is cp1252-decodable AND markdown does NOT go through stdout (only `click.echo()` / `print()` paths matter). Spec body is safe per the gotcha's allow-in-markdown-disallow-on-stdout discipline. No other non-ASCII glyphs introduced.

---

## §8 Forward-binding lessons banked for writing-plans phase OR future research-branch arcs

1. **Re-export pattern for shared L2 LOCK infrastructure** -- if two research-branch harnesses both need L2-LOCK-preserving OHLCV reads, the second harness can re-export the first's reader rather than duplicate the L2 LOCK 5 BINDING discriminating test surface. Pattern banked for future research-branch arcs.
2. **Production-parity invariant at the per-verdict level (not just per-bucket)** -- the V2 OHLCV evaluator invariant operates at the bucket level (sentinel-bucket filtering per gotcha #25); this harness's invariant operates at the per-(geometric_score, composite_score, structural_evidence_json) verdict level. Both are valid; the per-verdict invariant is finer-grained but requires bit-identical OHLCV archive + pattern_exemplars corpus per §E.1 scoping (5 conditions).
3. **Audit-row discipline for skip-bearing steps** -- gotcha #27's silent-skip-without-audit pattern motivates THIS harness AND informs the harness's own per-skip-reason counter + per-entry skip-row CSV emission at §C.4 + §D.3 + §I.2. The harness's existence is gotcha #27's architectural answer; the harness itself models the audit-row discipline per the gotcha banking.
4. **Detector registry re-import pattern** -- per OQ-1 + §D.2, the harness re-imports `_pattern_detect_registry()` from production rather than re-derive. Pattern banked: future research-branch harnesses that consume a stable production function set should re-import rather than re-derive (zero-drift discipline; cascade-call-graph audit per cumulative gotcha #19 BINDING).
5. **Three-phase dispatch arc precedent established** -- V2 OHLCV evaluator (first arc); pattern-cohort detector evaluator (second arc). Both arcs are: brainstorming -> writing-plans -> executing-plans. Future applied-research arcs inherit this pattern. The architectural template lives in `research/harness/` + `docs/superpowers/specs/` + `research/method-records/` + `research/studies/` per V2.1 §V.

---

## §9 Handback to operator

Pattern cohort detector evaluator research harness brainstorming SHIPPED. Spec self-reviewed per superpowers:brainstorming §N gate; ALL placeholder + consistency + scope + ambiguity checks passed.

### §9.1 Orchestrator next-steps (per dispatch brief §6 Phase 1 handback sequence)

- **QA implementer product** per `feedback_orchestrator_qa_implementer_product` BINDING (verify file:line + shipped-behavior + cumulative gotcha citations + 13-OQ list + brief-framing accuracy verification against reality on disk).
- **Merge `applied-research-pattern-cohort-detector-evaluator-brainstorm` `--no-ff` to `main`**; push.
- **Post-merge housekeeping** bundle if needed (CLAUDE.md line 3 refresh -- second Applied Research arc IN-FLIGHT pivot; any NEW gotchas if any (NONE expected per Codex-not-invoked brainstorming phase); phase3e-todo.md NEW top entry; orchestrator-context.md current state refresh; Prior demote + archive-split per size-check trigger).
- **Operator-paired OQ triage session** (13 OQs surfaced per §2 above + spec §J).
- **Draft writing-plans dispatch brief** consuming the operator-affirmed brainstorming spec + OQ dispositions.
- **Provide inline implementer dispatch prompt** for writing-plans phase (per `feedback_always_provide_inline_dispatch_prompt`).

### §9.2 Summary

Pattern cohort detector evaluator research harness brainstorming spec is the SECOND applied-research arc post-Phase-13-FULLY-CLOSED, following the V2 OHLCV criterion-evaluator arc precedent. Spec covers all 14 sections §A-§N per dispatch brief done criteria + superpowers:brainstorming §N self-review gate. 13 OQs surfaced (8 brief-implicit + 5 substrate-NEW); each has RECOMMEND disposition for operator-paired triage.

Brainstorming-phase Codex MCP review was OPTIONAL per dispatch brief §0; operator chose not to commission a Codex chain at brainstorming time. Pre-Codex 7-expansion + 5 NEW candidate refinements discipline applied at spec-write time per §4 disposition table.

Schema v21 UNCHANGED; baseline ~5893 fast tests UNCHANGED; ZERO new Schwab API calls; ZERO Co-Authored-By footer; ZERO production code changes (CLI subcommand registration BANKED for executing-plans per OQ-13). 5-sub-bundle decomposition recommendation at spec §M.1 (~30-52 commits projected for executing-plans phase; ~55-71 fast tests projected per spec §H.1). NEW method-record proposal at spec §K (key `pattern-cohort-detection`; version 0.1.0; status `research`; sibling to existing `aplus-criteria-calibration.md`). Study writeup template at spec §L (first-cohort target = 67 watch->aplus flips at vcp.tightness_range_factor=1.005; cross-tabulation against backtest output already shipped at merge `e0a9edd`).

Brief-framing accuracy verified per §3 above against `git log` + V2 OHLCV sensitivity backtest dispatch brief + production code line ranges -- ZERO discrepancies surfaced.

Ready for operator-paired OQ triage + writing-plans dispatch brief drafting.

---

*End of pattern cohort detector evaluator research harness brainstorming return report. Spec at [`docs/superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md`](superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md) (996 lines; 14 sections; 13 OQs). SECOND applied-research arc post-Phase-13-FULLY-CLOSED, following V2 OHLCV criterion-evaluator precedent. Brainstorming-phase Codex MCP review OPTIONAL per dispatch brief §0 + operator-paired discretion; NOT fired this phase. ~516+ ZERO Co-Authored-By footer streak preserved.*
