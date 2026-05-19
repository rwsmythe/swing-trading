# Return report — Phase 13 writing-plans

## Plan location

`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` (~2810 lines)

Commits on `phase13-writing-plans` worktree branch (branched from main HEAD `304715c`):

- `134b718` `docs(phase13): Phase 13 charts + patterns + auto-fill + usability writing-plans output` (initial; 2711 lines)
- `25ac9bd` `docs(phase13): writing-plans pre-Codex C.C lesson #6 absorption - OQ-7 spec >> brief reconciliation` (pre-Codex orchestrator-side review; 1 Critical absorbed)
- `614b246` `docs(phase13): writing-plans Codex R1 fixes - 5 Major + 2 Minor absorbed`
- `f50d677` `docs(phase13): writing-plans Codex R2 fixes - 3 Major + 4 Minor absorbed`
- `1df5a96` `docs(phase13): writing-plans Codex R3 fixes - 1 Major + 3 Minor absorbed`
- `faa5c72` `docs(phase13): writing-plans Codex R4 fixes - 2 Major + 2 Minor absorbed`

## Codex review history

- **Pre-Codex (orchestrator-side review per C.C lesson #6 BINDING)**: 1 Critical + 1 Major + 1 Minor surfaced. **Critical** absorbed inline: OQ-7 `fill_origin` enum + backfill values diverged between dispatch brief §1.3 (paraphrase) and spec §3.4 + §6.4 (authoritative); plan reconciles spec >> brief; brief amendment recommended at integration triage. **10th cumulative validation of C.C lesson #6** (BINDING per project precedent; 9x cumulative across Phase 12 + 12.5 + 13 brainstorms + writing-plans).
- **R1**: 0 Critical / 5 Major / 3 Minor. All 5 Major + 2 Minor RESOLVED; 1 Minor DEFERRED to T-D.7 closer (cp1252 subprocess validation consolidated there). Verdict: ISSUES_FOUND.
- **R2**: 0 Critical / 3 Major / 4 Minor. All 3 Major + 4 Minor RESOLVED. Verdict: ISSUES_FOUND.
- **R3**: 0 Critical / 1 Major / 3 Minor. All 1 Major + 3 Minor RESOLVED. Verdict: ISSUES_FOUND.
- **R4**: 0 Critical / 2 Major / 2 Minor. All 2 Major + 2 Minor RESOLVED. Verdict: ISSUES_FOUND.
- **R5**: 0 Critical / 0 Major / 0 Minor. **Final verdict: NO_NEW_CRITICAL_MAJOR**.

**Cumulative Codex chain shape**: 5-round convergent (per dispatch brief §1 projection of 3-5 rounds). Findings taper: R1 (5M/3m) → R2 (3M/4m) → R3 (1M/3m) → R4 (2M/2m) → R5 (0M/0m). Convergent non-strictly-monotonic at R3→R4 (Major count rebounded from 1 to 2 due to R3 fix-bundle introducing the `PHASE13_TEST_MOCK_SUBAGENT` env gate which itself surfaced a footgun; R4 collapsed by removing the gate entirely).

**ZERO ACCEPT-WITH-RATIONALE banked** across all 11 Major + 12 Minor findings — clean-record streak preserved (continues Phase 12.5 #1 + #2 + #3 brainstorms + Phase 13 brainstorm clean-record streak; ZERO banks across cumulative arc).

**ZERO Co-Authored-By footer drift** across all 6 plan commits (continues project ~187+ cumulative ZERO-drift streak).

## Three highest-leverage plan decisions

### 1. OQ-12 Option E migration landing timing encoded via T-A.1.1 + T-A.1.1b split (Codex R1 Major #1 + R2 Major #2 closure)

The brainstorm spec §8.3 recommended Option E (v20 lands as T2.SB1 task 1; T3.SB1 worktree branches off T2.SB1's first-commit SHA). Plan §B.2 + §G.1 T-A.1.1 encode this verbatim — BUT initial draft included NEW repo CRUD modules in T-A.1.1's file list, violating the "migration-only commit" boundary that the OQ-12 mechanic depends on. Codex R1 Major #1 caught this; R2 Major #2 caught the §B.4 contradiction. Resolution: split T-A.1.1 (strict migration-only: SQL + db.py version bump + Python constants + dataclass validators + schwab audit-service widening) + NEW T-A.1.1b (NEW repo CRUD modules land separately AFTER T-A.1.1). T3.SB1 worktree branches off T-A.1.1's SHA (NOT T-A.1.1b's). This preserves the operator-locked concurrency at scope-brainstorm §0.5.2 + closes the duplicate-write-set conflict that Option C (T-V20.PRELIM at head of both branches) would have created.

### 2. Constant-placement LOCK at §A.14 (Codex R2 Major #1 closure)

Initial draft scattered v20 enum constants across modules — including `_CHART_SURFACE_VALUES` in `swing/web/charts.py` (which lands at T2.SB6) and `_FLAG_SURFACE_VALUES` in `swing/trades/watchlist_close_track.py` (which lands at T4.SB). This violated the Phase 12 C.A T-A.2 paired-atomic-landing LOCK (forward-binding lesson #1): atomic-landing requires ALL constants to exist at the SAME commit as the schema CHECK + dataclass validator. But T-A.1.1 can't create `swing/web/charts.py` or `swing/trades/watchlist_close_track.py` because those modules belong to T2.SB6 + T4.SB respectively. Resolution: ALL v20 enum constants live in `swing/data/models.py` (file already exists pre-Phase-13 + houses the dataclass `__post_init__` validators); `swing/patterns/__init__.py` re-exports `DETECTOR_PATTERN_CLASSES` for namespace convenience; later modules IMPORT from `swing/data/models.py` — they do NOT redefine constants. §A.14 table updated with primary-location + re-export columns. This preserves atomic landing without requiring T-A.1.1 to prematurely create modules whose designs belong to later sub-bundles.

### 3. Hermetic subprocess cp1252 validation strategy (Codex R3 Major #1 + R4 Major #1 + #2 closure)

Initial draft at T-A.1.5 used `capfd` for ASCII-only CLI output validation. §A.8 LOCK + Phase 12 C.D gate-fix #3 BINDING require subprocess + stderr-encoding validation because pytest `capfd` captures via Python-level pipes that bypass the Windows cp1252 encoder. Codex R2 Minor #1 caught the gap. R3 Major #1 caught a deeper risk: subprocess tests that invoke real `swing patterns label-exemplars` would dispatch actual subagent + write to operator DB. R4 Major #1 caught the proposed `PHASE13_TEST_MOCK_SUBAGENT` env-gate fix as a production data-integrity footgun (env var leakage into operator shell would silently fabricate `pattern_exemplars` rows). Final resolution: subprocess tests are `--help`-only — they exercise click output rendering hermetically (no subagent dispatch, no DB writes, no credentials) but still surface static-string CLI surface violations which is the typical cp1252 gotcha emit path. Deeper runtime cp1252 coverage (when fire_claude_silver_label / clear_flag / set_flag actually run) uses in-process pytest with `monkeypatch` + `capfd` at T-A.1.5 + T-D.3 — those tests catch what they catch, but the subprocess `--help` tests catch the most common gotcha shape without test-infrastructure footguns.

## Per-sub-bundle task counts + projections

| Sub-bundle | Task count | Test delta projection (fast) | Test delta (slow) | LOC projection (prod + test) |
|---|---|---|---|---|
| T1.SB0 | 4 | +20-40 | 0 | +50-100 prod / +200-350 test |
| T2.SB1 | 9 (T-A.1.1 + T-A.1.1b + T-A.1.2..T-A.1.8) | +50-90 | 0 (cassette-mode) | +500-800 prod / +600-900 test |
| T3.SB1 | 6 | +40-70 | +1 (Schwab E2E) | +200-300 prod / +300-500 test |
| T2.SB2 | 6 | +60-100 | 0 | +400-600 prod / +500-800 test |
| T2.SB3 | 9 | +90-150 | +1 (operator-fixture detector) | +800-1200 prod / +1000-1500 test |
| T3.SB2 | 5 | +40-70 | +1 (Schwab E2E) | +200-300 prod / +300-500 test |
| T2.SB4 | 7 | +70-120 | 0 | +500-800 prod / +700-1100 test |
| T2.SB5 | 6 | +60-100 | +1 (pytest-benchmark) | +400-600 prod / +500-800 test |
| T3.SB3 | 5 | +50-90 | 0 | +200-400 prod / +400-700 test |
| T2.SB6 | 7 | +70-120 | +1 (full closed-loop E2E) | +700-1100 prod / +900-1400 test |
| T4.SB | 7 | +40-70 | 0 | +250-400 prod / +400-700 test |
| **Cumulative** | **71 tasks** | **+590-1020 fast** | **+4 slow E2E** | **+4200-6600 prod LOC / +5800-9250 test LOC** |

**Baseline at Phase 13 start**: ~4924 fast tests (HEAD `b5e62c5`).

**Phase 13 close projection**: ~5500-5940 fast tests + 4 new slow E2E tests.

## Cross-bundle dependencies confirmed

```
T1.SB0 → T2.SB1 ∥ T3.SB1 (concurrent off T2.SB1's first-commit SHA per OQ-12 Option E)
              → [operator-paired pause at T-A.1.7]
       → T2.SB2 → T2.SB3 → T3.SB2 → T2.SB4 → T2.SB5 → T3.SB3 → T2.SB6 → T4.SB → CLOSED
```

OQ-12 Option E coordination:
1. T2.SB1 worktree branches from main HEAD.
2. T-A.1.1 commit lands; SHA recorded.
3. T3.SB1 worktree branches FROM that SHA (NOT main HEAD).
4. Both proceed in parallel.
5. Merge ordering: T2.SB1 first; T3.SB1 second.

11 cross-bundle pins enumerated at §H.3 with planted-at + un-skipped-at + verifies columns.

## 12 OQ dispositions encoded verbatim

- **OQ-1** (11 sub-bundles per scope-brainstorm §0.5.2) — §A.1 + §G dispatch sequence diagram. BINDING.
- **OQ-2** (matplotlib SVG inline + new `chart_renders` cache table) — §C.1 + §C.2 + §B.3 + §G T1.SB0/T2.SB6. BINDING V1.
- **OQ-3** (new `pattern_evaluations` table; 5 V1 values; no sell-side reservation) — §B.3 + §D.1 + §G T-A.1.1. BINDING.
- **OQ-4** (DTW Sakoe-Chiba band; window=0.1 × series_length; 120s benchmark gate) — §D.5 + §G T-A.5.5. BINDING V1; SBD V2 fallback.
- **OQ-5** (phased Codex SELECTIVE policy; T2.SB1 15% random only; T2.SB3+/SB4 high-stakes activation) — §A.6 + §D.6 + §G T-A.1.3 + T-A.3.7 + T-A.4.5. BINDING.
- **OQ-6** (Sub-bundle 1 cassette session precedent for operator-paired pause) — §G T-A.1.7. BINDING.
- **OQ-7** (V1 5-value enum: `operator_typed`/`schwab_auto`/`schwab_auto_then_operator_corrected`/`tos_import`/`imported_legacy`; backfill to `operator_typed`) — §B.5 + §E.1 + §G T-A.1.1. BINDING V1 per spec §3.4 + §6.4 (reconciliation footnote at §0.2 documents spec >> brief drift; brief amendment recommended at integration triage).
- **OQ-8** (OhlcvCache post-T1.SB0 for MFE/MAE; yfinance V2-fallback) — §E.3 + §G T-B.3.2. BINDING.
- **OQ-9** (V1 JSON column `pattern_evaluations.feature_distribution_log_json`) — §B.3 + §D.7 + §G T-A.3.5. BINDING V1.
- **OQ-10** (BOTH `/patterns/{candidate_id}/review` AND `/metrics/pattern-outcomes` 9th metric tile) — §D.8 + §G T-A.6.3 + T-A.6.5. BINDING.
- **OQ-11** (`.claude/agents/pattern-labeler.md` Claude Code project-local subagent) — §A.7 + §G T-A.1.2. CONFIRMED.
- **OQ-12** (Option E — v20 lands as T-A.1.1 migration-only commit; T3.SB1 branches off T-A.1.1's SHA; merge order T2.SB1 first) — §B.2 + §G.1 T-A.1.1 + §G.2 T-B.1.1. BINDING.

## V2.1 §VII.F amendment candidates banked

7 WP-N banks introduced during writing-plans authoring (§J.2) + 22 V2 candidates inherited from spec §13 V2-1..V2-22:

| ID | Candidate | Disposition |
|---|---|---|
| WP-1 | `swing/patterns/template_matching.py` standalone benchmark profiling helper | V2 — add when corpus reaches ~150 exemplars per pattern |
| WP-2 | Backfill historical `reconciliation_corrections` chains into `fills.schwab_source_value_json` | V2 dispatch candidate |
| WP-3 | `review_log.fields_auto_populated_count` + `auto_fill_disagreement_count` aggregate columns | V2 when query overhead becomes material |
| WP-4 | `chart_renders` cache TTL invalidation helper | V2 if disk usage becomes operator-noticeable |
| WP-5 | Q4 close-tracking flag auto-expire after N days configurable per-flag | V2 |
| WP-6 | Codex MCP invocation rate-limiter | V2 — monitor at first 100 fires |
| WP-7 | Active-learning prioritization weight tuning | V2 — tune after 1 month of queue-triage data |

**Brief vs spec OQ-7 reconciliation**: dispatch brief §1.3 OQ-7 paraphrase listed enum values + backfill target that diverged from spec §3.4 + §6.4 authoritative values. Plan reconciles spec >> brief (semantically correct: `'operator_typed'` faithfully labels existing journal-typed-from-memory entries). Brief amendment recommended at integration triage.

## Forward-binding lessons for executing-plans dispatches

30 lessons enumerated at §L (20 inherited from spec §11 + 10 Phase 13-specific surfaced during writing-plans authoring; see §L.1 + §L.2).

Most-load-bearing for executing-plans dispatches:

1. **Schema-CHECK + Python-constant + dataclass-validator paired atomic landing** (§A.14 + §B.4 — Phase 12 C.A T-A.2 LOCK) — applied in T-A.1.1.
2. **OQ-12 Option E migration mechanics** (§B.2 — T2.SB1 task 1 = migration-only commit; T3.SB1 branches off SHA).
3. **Reject-caller-held-tx contract on transactional services** (§A.12 + T-D.1 — Phase 8 + Phase 12 C.C lesson family).
4. **HTMX gotcha trinity** (§A.4 — Phase 5 R1 M1+M2 + Phase 6 I3) — applied per form-driven route.
5. **Base-layout VM banner pin** (§A.3 — Phase 10 T-E.3 + Phase 12.5 #2 13-VM retrofit) — every new VM extending base.html.j2.
6. **Hermetic subprocess cp1252 validation** (T-D.7 + Codex R3 + R4 closure) — `--help`-only at subprocess level; deeper coverage via in-process monkeypatch.
7. **Constant-placement LOCK** (§A.14 + Codex R2 Major #1 closure) — primary constant definitions live in modules that exist at T-A.1.1 commit time.
8. **Operator-paired pause** (§G T-A.1.7 + OQ-6) — mirrors post-Phase-12 Sub-bundle 1 cassette session precedent.

## Capture-needs for executing-plans dispatches

Per-sub-bundle dispatch-brief considerations:

- **T1.SB0 dispatch brief**: enumerate Phase 11 Sub-bundle C R1 M#5 V1 deferral context; cite operator-witnessed `python -m swing.cli pipeline run` gate.
- **T2.SB1 dispatch brief**: BINDING — enumerate operator-paired pause at T-A.1.7 + OQ-6 cassette session precedent + 30-80 silver-tier exemplar target; record T-A.1.1's first-commit SHA explicitly for T3.SB1 brief.
- **T3.SB1 dispatch brief**: BINDING — enumerate T2.SB1's first-commit SHA as worktree branch base (NOT main HEAD); enumerate schema-version-20 prerequisite assert at T-B.1.1.
- **T2.SB2 dispatch brief**: enumerate foundation primitives' downstream consumers (T2.SB3 + T2.SB4 detectors + T3.SB3 review auto-fill MFE/MAE).
- **T2.SB3 dispatch brief**: enumerate detector batch 1 + drift-logging substrate emit per OQ-9 + selective Codex retroactive evaluation activation at T-A.3.7.
- **T3.SB2 dispatch brief**: enumerate Schwab Trader API consumer merge-conflict avoidance ordering (AFTER T2.SB3).
- **T2.SB4 dispatch brief**: enumerate detector batch 2 + retroactive Codex coverage of HTF + DBW corpus.
- **T2.SB5 dispatch brief**: enumerate pytest-benchmark 120s gate + OQ-4 SBD V2 fallback if gate fails.
- **T3.SB3 dispatch brief**: enumerate OhlcvCache post-T1.SB0 substrate consumption per OQ-8.
- **T2.SB6 dispatch brief**: enumerate Theme 1 + Theme 2 coupling at annotated chart renderer (§C.4); enumerate 9th metric tile composition with Phase 10 architecture.
- **T4.SB dispatch brief**: enumerate Q4-only scope (no additional usability items per L11 + operator-pre-writing-plans elicitation 2026-05-18 PM); enumerate Q4 transactional discipline LOCK per §A.12 + §F.4 (sandbox short-circuit EXPLICITLY OMITTED — no Schwab dependency).

## Outstanding capture-needs that DEFER to Phase 13.5 / Phase 14

Per §L.3 + dispatch brief §6 done criterion 11:

- **Drift monitoring/dashboard side** (4 surfaces) → Phase 13.5 (LOCKed at L5).
- **Sell-side detector module** → Phase 14 (LOCKed at L3).
- **ML re-ranker** → indefinitely deferred (LOCKed at L4).
- **Matrix Profile + Shapelet** → Phase 14+.
- **Z-score normalization for template matching** → Phase 14+.
- **Composite_score calibration** → V2 (gated on v2 brief §16.5 G2 200 confirmed positives per pattern).
- **SBD or feature-vector template-matching** → V1 fallback if DTW 120s gate fails; otherwise Phase 14+.
- **WP-1..WP-7 banks** → V2 (see §J.2 above).
- **Backfill `reconciliation_corrections` chains into `fills.schwab_source_value_json`** → V2.
- **Q4 auto-expire / bulk-flag CLI / per-ticker annotation / hyp-rec elevation** → V2.
- **Multi-cohort architectural deepening / intraday / tax-lot / Branch A research-branch** → Phase 14+.
- **Interactive client-side JS chart library** → Phase 14+ (V1 SVG inline locked).
- **Operator-elicited usability list beyond Q4** → operator confirmed empty at 2026-05-18 PM elicitation; future surfacing routes to Phase 13.5 / Phase 14.

## Operator-paired next steps

Per BINDING memory `feedback_orchestrator_qa_implementer_product.md` (9x cumulative validated):

1. **Orchestrator drives post-writing-plans QA review** of plan + return report (cite file:line evidence per forward-binding lesson #17).
2. **Operator approval to merge `phase13-writing-plans` worktree branch into `main`**.
3. **Post-merge housekeeping** per `docs/phase3e-todo.md` retention discipline.
4. **Begin 11-sub-bundle executing-plans dispatch loop** per §H.1 dispatch sequence (T1.SB0 first; T2.SB1 ∥ T3.SB1 concurrent off T2.SB1's first-commit SHA per OQ-12 Option E).

---

*End of Phase 13 writing-plans return report. 5-round convergent Codex chain reaching NO_NEW_CRITICAL_MAJOR. 11 Major + 12 Minor + 1 pre-Codex Critical all RESOLVED; ZERO ACCEPT-WITH-RATIONALE banks. ZERO Co-Authored-By footer drift across 6 commits. Plan substrate ready for 11-sub-bundle executing-plans dispatch loop. C.C lesson #6 10th cumulative validation cited.*
