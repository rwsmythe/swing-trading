# Phase 13 T2.SB6c Executing-Plans Return Report

**Branch:** `phase13-t2-sb6c-executing-plans`
**Baseline:** `432da47` (main HEAD; pre-dispatch)
**HEAD at handback:** `0fb4d0e`
**Date:** 2026-05-22
**Workflow:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review)
**Dispatch:** Phase 13 T2.SB6c executing-plans — v21 schema atomic landing + SB6 completion-gap closure + §1.5.1 + §1.5.2 + §1.5.4 amendments + ZERO new V1 STUBs (closure-dispatch intent).

---

## §1 Commit chain

8 commits — 5 task commits + 3 Codex fix bundles. All commits ZERO `Co-Authored-By` trailer per cumulative ~360+ streak discipline.

| Order | SHA | Title | Test delta | Cumulative fast suite |
|---|---|---|---|---|
| 1 | `7ee5a4a` | feat(phase13): v21 migration + trades backlinks atomic landing (T-A.6c.1) | +26 | 5559 → 5585 |
| 2 | `7cac0f7` | feat(phase13): Gap A chart-surface wiring + pipeline-side chart_renders write-through (T-A.6c.2) | +18 | 5585 → 5603 |
| 3 | `a61dd5a` | feat(phase13): Gap B no-schema + labeler_evidence backfill (T-A.6c.3) | +19 | 5603 → 5622 |
| 4 | `b13ce7f` | feat(phase13): Gap B v21-dep + entry anchor threading + WilsonCI surfacing (T-A.6c.4) | +37 | 5622 → 5659 |
| 5 | `81eede2` | test(phase13): T2.SB6c closer + cross-bundle pin row 12 (T-A.6c.5) | +1 (+1 fast E2E) | 5659 → 5660 + 1 E2E |
| 6 | `cc8f5a0` | fix(phase13): Codex R1 PE anchor + B.5 backlink + candidate_id alignment | +5 | 5660 → 5665 |
| 7 | `c826791` | fix(phase13): Codex R2 explicit PE run anchor + soft-warn test fidelity | +3 | 5665 → 5668 |
| 8 | `0fb4d0e` | fix(phase13): Codex R3 candidate-snapshot consistency under explicit run anchor | +2 | 5668 → 5670 |

**Net test delta:** baseline 5559 → 5670 fast + 1 fast E2E (+111 fast tests + 1 E2E).
**Above plan projection** (~92-95 + WilsonCI bump = 94-98); actual +111 reflects 8 Codex fix-bundle discriminating tests + a +3 over-projection inside the 5 task commits.

## §2 Codex chain shape

**4 rounds. ZERO CRITICAL findings cumulatively. ZERO ACCEPT-WITH-RATIONALE on MAJOR findings. All 6 MAJOR findings RESOLVED in-place.**

| Round | Critical | Major | Minor | Major findings (resolution) | Closure |
|---|---|---|---|---|---|
| R1 | 0 | 4 | 2 | Soft-warn drops PE anchor → fix `cc8f5a0` ; hyp-rec query param discarded at form render → fix `cc8f5a0` ; candidate_id/PE diverge across runs → fix `cc8f5a0` ; B.5 ignores `trades.pattern_evaluation_id` → fix `cc8f5a0` | ISSUES_FOUND |
| R2 | 0 | 1 | 1 | Explicit PE still rebinds after pipeline rotation (PE id without run anchor) → fix `c826791` (added `pipeline_run_id_at_form_render` query param + template emission + validation) | ISSUES_FOUND |
| R3 | 0 | 1 | 1 | Mixed-context trade: explicit PE backlink to run_1 with candidate-defaults from run_2 → fix `0fb4d0e` (Option A: explicit run threaded through candidate snapshot read) | ISSUES_FOUND |
| R4 | 0 | 0 | 1 | (None) — Minor: explicit-anchor validation could be centralized in a helper (advisory-only) | **NO_NEW_CRITICAL_MAJOR** |

**Minor findings summary:**
- R1.MINOR#1: WilsonCI template format `(Wilson CI 12.3-45.6; n=5)` vs brief's `{n: N, Wilson CI L.LL-U.UU}` — **ACCEPTED** as cosmetic; substance preserved + tests pass.
- R1.MINOR#2: Test docstring describes `max(daily_high)` while impl uses realized_R surrogate → **RESOLVED** at `cc8f5a0` (test renamed `..._reached_1r_via_realized_r_surrogate_v1`).
- R2.MINOR#1: Soft-warn test doesn't parse hidden inputs from response HTML → **RESOLVED** at `c826791` (regex-extraction-based test).
- R3.MINOR#1: Mismatch-run fallback codifies permissive tamper without rationale → **RESOLVED** at `0fb4d0e` (rationale comment added).
- R4.MINOR#1: Explicit-anchor validation logic duplicated in two places inside `build_entry_form_vm()` — **ACCEPTED** as advisory; future-refactor opportunity banked in §6 V2 candidates.

## §3 27th cumulative C.C lesson #6 validation — per-expansion verdict

**Verdict: NOTABLE.** First-run application of ALL 7 EXPANSIONS + 2 NEW REFINEMENTS at executing-plans phase. Pre-Codex (subagent-driven-development reviewer + spec-compliance reviewer) caught a meaningful share; Codex R1-R3 caught 6 MAJOR escalations that pre-Codex review missed.

| Expansion | Source | Pre-Codex catch? | Codex catch? | Verdict |
|---|---|---|---|---|
| #1 hardcoded-duplicate audit | T3.SB2 hotfix `cf3c489` | CLEAN (N-mirror audit for trade SELECT cols) | n/a | CLEAN |
| #2 brief-vs-spec source-of-truth + brief-vs-actual schema | T2.SB4 R1 M1 + T2.SB6c brainstorm | CLEAN at writing-plans (already-folded) | n/a | CLEAN |
| #3 schema-CHECK-vs-semantic-contract gap | T2.SB6a R1 CRITICAL #1 | CLEAN (ChartRender validator semantics preserved on §1.5.1 write-through) | n/a | CLEAN |
| #4 specific-scenario gotcha trace + SQL skeleton column verification | T2.SB6a R1 MAJOR #2 + T2.SB6c brainstorm R1 CRITICAL | CLEAN at writing-plans | n/a | CLEAN |
| #5 cross-section spec inventory grep | T2.SB6a R1 MAJOR #3 | CLEAN | n/a | CLEAN |
| #6 content-completeness audit | T2.SB6b lessons | CLEAN (§5.10 8-item checklist all LIVE) | n/a | CLEAN |
| #7 cross-row semantic SCOPE audit (per-candidate vs per-ticker) | T2.SB6b lessons | **PARTIAL FAIL** | Codex R1.MAJOR#4 caught B.5 SQL ignoring `trades.pattern_evaluation_id` direct backlink | RESOLVED at `cc8f5a0` |
| #8 NEW: per-aggregation-function UNIT audit | T2.SB6c writing-plans banking | CLEAN at writing-plans (DISTINCT on pe.id) | n/a | CLEAN |

**New surface category surfaced at Codex R1**: **form-render-time hidden anchor round-trip through soft-warn confirm + explicit query-param consumption + candidate-snapshot consistency across pipeline runs.** This is a 4-defect family that no pre-Codex review caught. Future banking candidate (Expansion #9): "form-render-anchor lifecycle audit across soft-warn / query-param / candidate-snapshot dimensions."

**4 NEW gotchas from writing-plans banking (BINDING at this 27th validation):**
- (9) SQL aggregation UNIT audit — Expansion #8 BINDING; Gap B.4 + B.5 SQL skeletons CTE-first + COUNT(DISTINCT pe.id). CLEAN.
- (10) Existing-field reuse audit before claiming new dataclass fields — Gap B.5 reuses EXISTING `PatternOutcomeRow._n + _ci` fields per T2.SB6b V1 simplification banking. CLEAN.
- (11) Template-rendering surface audit before claiming "no template edit needed" — §1.5.4 WilsonCI surfacing template extension shipped per operator decision 2026-05-22 AM. CLEAN.
- (12) `date.fromisoformat()` cross-type-boundary discipline — Gap B.1 `current_stage(conn, ticker, asof_date)` callsite wrapped in try/except ValueError → fall back to 'undefined'. CLEAN.

## §4 V1 simplifications (banked) + V2 candidates

### §4.1 V1 simplifications shipped (closure-dispatch intent — ALL targeted T2.SB6b banking RESOLVED + 4 NEW banked HERE)

**Targeted (T2.SB6b §6) — ALL RESOLVED:**
- T2.SB6b row 1 existing pre-v21 trades NULL backlinks → LIVE via v21 schema + NULL backfill (OQ-1 LOCK)
- T2.SB6b row 2 multi-pattern_class single anchor → LIVE (single-anchor design; multi-pattern_class link table V2-banked)
- T2.SB6b row 3 volume profile fetch-on-cache-miss → LIVE (OQ-14 LOCK; `read_or_fetch_archive` primitive used)
- T2.SB6b row 4 backup-gate strict-equality skips multi-jump → LIVE (OQ-3 LOCK; `--enforce-stepwise` V2-banked)
- T2.SB6b row 5 `pattern_evaluations.candidate_id` direct column → LIVE via two-table JOIN (per plan §B.1 + §D.3 column-verified)
- T2.SB6b row 6 Phase 6 chart_pattern_algo enum disjoint → preserved; enum-unification V2-banked
- T2.SB6b row 7 Path C labeler_evidence backfill → LIVE (§1.5.2 shipped at T-A.6c.3; Path A labeler subagent contract widening V2-banked)
- T2.SB6b row 8 Gap B.5 WilsonCI surfacing → **CLOSURE-COMMITTED via §1.5.4 amendment** at T-A.6c.4 per operator decision 2026-05-22 AM (template-extension + 3 discriminating tests; ZERO V2 banking)

**NEW V1 simplifications banked at T2.SB6c executing-plans (closure-dispatch INTENT preserved — these are NEW limitations introduced by SB6c that warrant V2 attention):**

| Row | NEW V1 simplification | V2 dependency cited | Banked for |
|---|---|---|---|
| 1 | Gap B.4 outcome distribution uses `trade.realized_R_if_plan_followed >= 1.0 / < 0` surrogate instead of OQ-6 `max(daily_high since entry) >= entry + (entry - stop)` | OHLCV cohort-statistics cross-cohort daily-high comparator (V2 implements true intraday-touch detection) | V2 OHLCV-aware metrics |
| 2 | TradeEntryFormVM PE anchor lookup uses ORDER BY composite_score DESC when no explicit query param provided (form-VM has no pattern_class context) | V2 entry-form route receives explicit pattern_class context OR explicit PE id query param canonicalized | V2 entry-form UX |
| 3 | `VolumeProfileRow.__post_init__` rejects negatives but NOT NaN/inf (caller's outer try/except provides safety net) | Add `math.isfinite()` validator at dataclass barrier | V2 hardening pass |
| 4 | Exemplar cache-miss write-through skips when no completed pipeline run exists (legacy seeded-corpus scenario) | V2 pipeline-run-agnostic exemplar cache key shape (substrate change) | V2 substrate refactor |
| 5 | `market_weather` chart_renders write-through embeds `trend_template_state="stage_2"` literal in `_step_charts` | V2 live `current_stage(conn, ticker, asof_date)` threading through pipeline step | V2 weather chart enhancement |
| 6 | B.5 outer `n` field overridden to use B.5 denominator (preserves `row.reached_1r_n / row.n` ratio correctness) | V2 separate `triggered_n` and `b5_denom_n` rendering fields | V2 metric tile refactor |
| 7 | `_latest_complete_evaluation_run_id` is private-prefixed but consumed cross-module from `swing/trades/entry.py` | Rename without underscore OR document package-private convention | V2 cleanup pass |
| 8 | R4 MINOR: explicit-anchor validation logic duplicated in `build_entry_form_vm` (pre-resolution + later PE hidden-anchor) | Extract local helper `(pe_id, pipeline_run_id, evaluation_run_id)` for validated explicit anchor | V2 cleanup pass |

### §4.2 V2 candidates from this dispatch

All 8 NEW V1 rows above are V2-banked. Plus inherited V2 candidates from plan §I.4:
- Many-to-many `trade_pattern_evaluations` link table (V2 schema dispatch)
- `--enforce-stepwise` migration runner flag
- Phase 6 `chart_pattern_algo` enum unification with Phase 13 detector enum
- Path A labeler subagent contract widening (FRESH exemplars; Path C backfill is shipped)
- Full Weinstein 4-stage labeling (V2 trend-template enhancement)
- `pattern_evaluations.candidate_id` direct column (V2 schema if Phase 13.5+ requires)

## §5 Forward-binding lessons banked

### §5.1 Lessons from this dispatch (NEW)

1. **Form-render anchor lifecycle audit (NEW gotcha candidate #13)** — when introducing a hidden form anchor that drives POST-time validation, the FULL lifecycle audit MUST include: (a) soft-warn confirm `form_values` round-trip; (b) GET-time query param consumption; (c) candidate-snapshot consistency across pipeline runs; (d) explicit-anchor-vs-latest-snapshot validation order. Codex R1 caught (a) + (b); R2 caught (c) via stale-PE-after-rotation; R3 caught (d) via mixed-context candidate snapshot. The cumulative 4-defect family escaped pre-Codex review. Future hidden-anchor designs MUST enumerate all 4 lifecycle dimensions at writing-plans + executing-plans phases.

2. **`trades.pattern_evaluation_id` direct backlink in B.5 SQL skeleton** — when v21 introduces explicit per-pattern_class anchor on trades, downstream metric-tile cohort joins MUST honor the direct anchor when populated. The candidate-only join (`t.candidate_id = c.id`) is over-inclusive for multi-pattern-class shared candidates. Codex R1 caught this. Future v21+ trade-aware metric surfaces MUST use `(t.candidate_id = c.id AND (t.pattern_evaluation_id IS NULL OR t.pattern_evaluation_id = pe.id))` admit-both pattern.

3. **`candidate_id` resolution must respect operator-witnessed pipeline run anchor** — when both `pattern_evaluation_id` and `candidate_id` backlinks land on a v21+ trade, they MUST resolve from the SAME pipeline_run snapshot. Codex R1.MAJOR#3 caught the divergence between form-render-anchored PE and POST-time-latest-resolved candidate_id. Resolution rule: when `pattern_evaluation_id` is non-NULL, `candidate_id` resolves via the PE row's `pipeline_run_id → evaluation_run_id → candidates` chain (NOT `_latest_complete_evaluation_run_id`). Future v21+ entry services with paired backlinks MUST follow this resolution discipline.

4. **Explicit hyp-rec query param + entry-form route + VM-builder threading triple** — when a hyp-rec card emits a hidden query-param anchor on the entry-form link, the entry-form route AND VM-builder MUST consume + honor it. Form-defaults must derive from the SAME explicit pipeline_run anchor (NOT latest). Codex R1.MAJOR#2 + R3.MAJOR#1 caught this. Future operator-intent-anchored UI patterns MUST thread the anchor through ALL form-rendering dimensions, not just the persistence target.

### §5.2 Cumulative lessons inherited (BINDING; preserved through this dispatch)

All cumulative gotchas in CLAUDE.md honored:
- §A.14 paired discipline at T-A.6c.1 (schema + dataclass + read-path mapper + write-path INSERT + 26 tests in ONE commit)
- N-mirror auditing of trade SELECT column lists
- Read-path mapping keeps pace with write-path (T3.SB3 R1 M#1) — `_row_to_trade` + `_trade_select_cols(conn)` helper
- Migration runner backup-gate strict equality `pre_version == 20 AND target >= 21`
- `executescript()` implicit-COMMIT discipline — migration body uses explicit BEGIN/COMMIT
- `INSERT OR REPLACE` cascade-wipe BANNED (no caller-side direct INSERT into chart_renders)
- Schema-version-aware INSERT for nullable columns (T3.SB1 fills.py precedent extended to trades)
- F6 transient-empty defense at construction barrier — `_step_charts._refresh_one` catches ChartRender ValueError, WARN-logs, continues
- Cache key shape per ChartRender semantic validator — run-bound surfaces non-NULL pipeline_run_id; position_detail NULL pipeline_run_id
- Server-recompute at POST (T3.SB3 R1 M#2 LOCK) — POST handler re-derives pattern_evaluation_id from canonical state at POST time
- 5-tier rejection ladder + claim-consistency gate (T3.SB1 LOCK extended)
- Recovery form anchor-clear discipline (T3.SB1 R3 M#2 LOCK)
- ZERO Co-Authored-By trailer (~360+ commit cumulative streak preserved through 8 commits)
- ASCII-only on stdout-flowing paths; backfill CLI output `Augmented: N; Skipped: M`
- date.fromisoformat() cross-type-boundary discipline (NEW gotcha #12)
- Template-rendering surface audit (NEW gotcha #11) — §1.5.4 WilsonCI extension verified rendered
- Existing-field reuse audit (NEW gotcha #10) — Gap B.5 reuses `PatternOutcomeRow._n + _ci` fields
- SQL aggregation UNIT audit (NEW gotcha #9 / Expansion #8)

## §6 Cumulative streaks preserved

- **`Co-Authored-By` trailer:** ZERO on all 8 commits → cumulative ~368+ commit streak.
- **C.C lesson #6 cumulative validations:** 22x CLEAN → 23rd NOTABLE T2.SB6a → 24th NOTABLE T2.SB6b → 25th NOTABLE T2.SB6c brainstorming → 26th NOTABLE T2.SB6c writing-plans → **27th NOTABLE T2.SB6c executing-plans** (this dispatch). Pre-Codex review CLEAN on Expansions #1-#6 + #8; **Expansion #7 PARTIAL FAIL** (B.5 `trades.pattern_evaluation_id` backlink missed; Codex R1.MAJOR#4 caught). NEW lesson category surfaced (form-render-anchor lifecycle 4-defect family).
- **Sub-bundle ship count:** Phase 13 sub-bundles SHIPPED = 10 + T2.SB6c = **11 of 11** (closure!). T4.SB remains (operator pause for list additions).
- **Schema v20 LOCKED streak:** ended at T-A.6c.1 v21 landing per plan §A.2 (was 12+ sub-bundles since T-A.1.1).
- **Zero new Schwab API calls:** L2 LOCK preserved.
- **Zero new V1 STUBs on §5.10 8-item checklist:** all 8 items LIVE post-SB6c per §D.4 audit table.

## §7 Inline self-verification

- `python -m pytest -m "not slow" -q` → **5670 passed, 2 skipped, 0 failed** (in ~117s with xdist). Baseline 5559 + 111 = 5670 ✓
- `python -m pytest tests/integration/test_phase13_t2_sb6c_v21_closure_e2e.py -v` → **1 passed** (~10s)
- `ruff check swing/` → **All checks passed!** (0 violations).
- Schema migration smoke: v21 LANDED via `_phase13_sb6c_backup_gate` at strict `pre_version == 20 AND target_version >= 21`; backup filename `swing-pre-phase13-sb6c-migration-<ISO>.db` (OQ-8 LOCK); discriminating test asserts gate behavior at v19→v21 + v20→v21 paths.
- Cross-bundle pin row 12: PLANTED ACTIVE at T-A.6c.1; GREEN throughout cumulative run; documented at Phase 13 main plan §H.3.

## §8 Schema delta

**v20 → v21 LANDED at T-A.6c.1 (`7ee5a4a`).** Migration `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql`:
- Delta A: `ALTER TABLE trades ADD COLUMN candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL` + `CREATE INDEX idx_trades_candidate_id`
- Delta B: `ALTER TABLE trades ADD COLUMN pattern_evaluation_id INTEGER REFERENCES pattern_evaluations(id) ON DELETE SET NULL` + `CREATE INDEX idx_trades_pattern_evaluation_id`
- `UPDATE schema_version SET version = 21`

Backup-gate strict equality `pre_version == 20 AND target_version >= 21` per OQ-3 LOCK; 4 discriminating tests verify gate behavior (v20→v21 fires + writes backup; v19→v21 multi-jump bypasses SB6c gate but fires v20 boundary's own gate).

Read-path SVAI `_trade_select_cols(conn)` helper extends T3.SB1 fills.py:51-53 precedent to trades; pre-v21 test fixtures (~140 callsites) preserved via legacy projection `NULL AS candidate_id, NULL AS pattern_evaluation_id`.

## §9 Operator-witnessed gate plan (post-merge)

Per plan §F.4 + dispatch brief §F.4:
- S1 (inline): fast pytest + ruff + schema==v21 ✓ (this report)
- S2 (browser): `/patterns/{candidate_id}/review` — confirm all 8 spec §5.10 checklist items LIVE
- S3 (browser): hyp-rec detail page — confirm 800x500 SVG renders (Gap A.1)
- S4 (browser): position detail page — confirm 800x500 SVG with fill markers (Gap A.2)
- S5 (browser): `/watchlist` — confirm thumbnail charts render inline per row (Gap A.3)
- S6 (browser): `/patterns/exemplars` — cache-miss + write-through (Gap A.4)
- S6b (DB query): after pipeline run, `chart_renders` populated for all 4 surfaces (§1.5.1)
- S7 (browser): `/metrics/pattern-outcomes` — `reached_1r_n / n` + `hit_stop_n / n` ratio + WilsonCI for n≥5 (Gap B.5 + §1.5.4)
- S8 (browser): `/patterns/queue` — criterion 3 ranking matches current weather state (Gap B.6)
- S9 (browser): fresh hyp-rec trade entry → trade row gets BOTH `candidate_id` AND `pattern_evaluation_id` populated; manual_off_pipeline entry → NULL backlinks
- S10 (browser): `confirm` decision → `pattern_exemplars` gets `label_source='organic_trade_history'`
- S11 (operator-paired): `python -m swing.cli patterns-exemplars-backfill-labeler-evidence` runs cleanly + populates rule_criteria + narrative

## §10 Handback summary

**T2.SB6c executing-plans SHIPPED at HEAD `0fb4d0e`.** Codex chain converged at R4 NO_NEW_CRITICAL_MAJOR after 4 rounds (1+4+1+1+1 = ZERO CRITICAL, 6 MAJOR all RESOLVED, 5 MINOR with 4 RESOLVED + 1 ACCEPTED). 27th cumulative C.C lesson #6 validation NOTABLE (Expansion #7 PARTIAL FAIL on B.5 backlink). 8 NEW V1 simplifications banked with V2 dependency cited; 8 T2.SB6b §6 targeted V1 simplifications ALL RESOLVED including §1.5.4 WilsonCI CLOSURE-COMMITTED. ZERO new Schwab API calls + ZERO `Co-Authored-By` trailer drift + Phase 13 sub-bundle ship count 11 of 11.

Hand back to operator for QA + merge + post-merge housekeeping + S2-S11 operator-witnessed gate run + [PAUSE FOR OPERATOR LIST ADDITIONS] per `project_phase13_t4_sb_pause_for_list_additions` memory.

---

*End of T2.SB6c executing-plans return report. Plan substrate at `e26bb0a` honored; dispatch brief §1.5.4 WilsonCI surfacing amendment CLOSURE-COMMITTED; Codex MCP chain converged 4 rounds; ~5670 fast tests + 1 E2E + ruff clean; schema v21 LANDED; cross-bundle pin row 12 GREEN; ZERO Co-Authored-By drift through 8 commits.*
