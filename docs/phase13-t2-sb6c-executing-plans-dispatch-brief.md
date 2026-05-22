# Phase 13 T2.SB6c — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the T2.SB6c executing-plans implementer. No prior conversation context.

**Mission:** Execute the T2.SB6c plan's 5-task decomposition (v21 schema atomic landing + SB6 completion-gap closure + amendments per §1.5 below) end-to-end via `copowers:executing-plans` skill (wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review after all tasks complete).

**Plan (PRIMARY SUBSTRATE — read end-to-end):** [`docs/superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md`](superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md) at HEAD `e26bb0a` (1820 lines; covers §A-§J done criteria; 5-task decomposition T-A.6c.1..T-A.6c.5 with bite-sized step structure + per-task acceptance criteria + commit message templates; encodes §1.5.1 chart_renders write-through + §1.5.2 labeler backfill amendments at plan §C.3 + §C.4 + §G.2 + §G.3 — DO NOT re-derive; the plan is BINDING substrate).

**Brief:** `docs/phase13-t2-sb6c-executing-plans-dispatch-brief.md` (this file).

**Sequencing:** T2.SB6c writing-plans SHIPPED 2026-05-22 AM at `e26bb0a` + housekeeping at `e7d0cce` + brief committed at the SHA captured in §0 below. Output is the final SB6c artifact set (5 task commits + 0-3 Codex fix bundles + 1 return report) followed by orchestrator-side merge + post-merge housekeeping + **[PAUSE FOR OPERATOR LIST ADDITIONS]** per `project_phase13_t4_sb_pause_for_list_additions` memory.

**Branch:** `phase13-t2-sb6c-executing-plans` — branches from main HEAD `e7d0cce` (post-T2.SB6c-writing-plans housekeeping).

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb6c-executing-plans phase13-t2-sb6c-executing-plans`. Work runs from that worktree's cwd.

**Workflow:** `copowers:executing-plans` skill (wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review after all tasks complete). Expected 2-5 Codex rounds — schema work + pre-Codex discipline now mature at 26 cumulative validations; T-A.6c.1 atomic-landing complexity is the most likely source of Codex findings.

**Expected duration:** ~6-12 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x). Test count delta projected ~+92-95 fast tests + 1 fast E2E per plan §F + §1.5.1/§1.5.2 amendments + further ~+2-3 per §1.5.4 WilsonCI amendment below → ~94-98 fast + 1 fast E2E final.

---

## §0 Read first (in this order)

1. **`docs/superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md`** at HEAD `e26bb0a` — PRIMARY SUBSTRATE. Read end-to-end:
   - §A Status + scope
   - §B Schema deltas (Delta A `trades.candidate_id` + Delta B `trades.pattern_evaluation_id`)
   - §C Atomic-landing strategy (§A.14 paired discipline)
   - §C.3 + §C.4 — chart_renders write-through + labeler backfill amendments (§1.5.1 + §1.5.2 folded into plan)
   - §C.5 anchor-threading 4-layer scope
   - §D Closure consumer mapping (Gap A.1-A.4 + Gap B.1-B.6)
   - §D.3 cross-row lookup discipline with column-verified SQL skeletons
   - §D.4 content-completeness audit table
   - §E Cross-bundle pin updates (row 12 PLANTED at T-A.6c.1; un-skip at T-A.6c.5)
   - §F Test scope projection
   - §G Per-task decomposition T-A.6c.1..T-A.6c.5 with bite-sized step structure
   - §G.2 + §G.3 — §1.5.1 + §1.5.2 amendments encoded in task steps
   - §H Dispatch sequence (concurrent T-A.6c.1+2+3; sequential T-A.6c.4 + T-A.6c.5)
   - §I Forward-binding lessons inherited
   - §J References

2. **`docs/phase13-t2-sb6c-writing-plans-return-report.md`** (197 lines) — writing-plans return report:
   - §4 Codex chain shape (6 rounds; 1 CRITICAL + 16 MAJOR + 4 MINOR all RESOLVED; ZERO ACCEPT-WITH-RATIONALE)
   - §5 Per-expansion verdict (26th C.C lesson #6 = NOTABLE; Expansion #4 + #7 PARTIAL FAIL — what to watch for at executing-plans phase)
   - §6 V1 simplifications + V2 candidates
   - §7 4 NEW forward-binding lessons banked (SQL aggregation UNIT audit Expansion #8 candidate; existing-field reuse audit; template-rendering surface audit; date.fromisoformat discipline)

3. **`docs/phase13-t2-sb6c-writing-plans-dispatch-brief.md`** at HEAD `c9bd715` (the AMENDED brief) — predecessor brief that drove the writing-plans dispatch. The §1.5.1 chart_renders write-through + §1.5.2 labeler backfill amendments are already encoded in the plan at §C.3 + §C.4 + §G.2 + §G.3; this brief is the source-of-truth for the amendment intent.

4. **`docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md`** (659 lines) — brainstorm spec; PRIMARY SUBSTRATE for the writing-plans plan. Read sections referenced by the plan as you execute each task.

5. **`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`** §G.9 + §H.3 — Phase 13 main plan; T2.SB6c plan is a v21 extension and references this main plan in §-section cross-refs.

6. **`CLAUDE.md`** at repo root — project conventions + cumulative gotchas. ESPECIALLY relevant for T2.SB6c executing-plans phase:
   - **NEW from T2.SB6c writing-plans housekeeping (BINDING for 27th validation)**:
     - SQL aggregation UNIT audit (NEW Expansion #8 candidate)
     - Existing-field reuse audit before claiming new dataclass fields
     - Template-rendering surface audit before claiming "no template edit needed"
     - `date.fromisoformat()` discipline for cross-type-boundary calls
   - Inherited from T2.SB6c brainstorming: Brief-vs-actual schema reality check + SQL skeleton column verification (Expansion #4 refinement)
   - Schema-CHECK widening MUST audit ALL Python-side surface guards (T3.SB2 hotfix `cf3c489`)
   - Schema-CHECK + Python-constant + dataclass-validator MUST land in same task (Phase 12 C.A T-A.2)
   - Read-path mapping must keep pace with write-path on widened columns (T3.SB3 R1 M#1)
   - Migration runner backup-gate strict equality `pre_version == 20 AND target >= 21` (Phase 12 C.A §0.5)
   - `executescript()` implicit-COMMIT (Phase 7 Sub-A R1 M3)
   - `INSERT OR REPLACE` cascade-wipe (Phase 8 daily-management spec §4.2)
   - Schema-CHECK + Python-constant + dataclass-validator EXTENDS to semantic contracts (T2.SB6a R1 CRITICAL #1)
   - F6 transient-empty at construction barrier when helper accepts dataclass parameter (T2.SB6a R1 MAJOR #2)
   - Schema-version-aware INSERT for newly-widened columns (T3.SB1 precedent at `swing/data/repos/fills.py:51-53`)
   - Hidden anchor 4-tier rejection ladder (T3.SB1) — extends to 5-tier for `claimed_pattern_evaluation_anchor` per spec §2.2 OQ-12 disposition
   - Recovery form anchor-clear discipline (T3.SB1 R3 M#2)
   - "Server-stamped" hidden form inputs are STILL tampering surfaces unless POST RECOMPUTES (T3.SB3 R1 M#2)

7. **`docs/orchestrator-context.md`** "Currently in-flight work" + "Recent decisions and framings" + "Maintenance: retention discipline" — current state reflects T2.SB6c writing-plans SHIPPED + 4 NEW gotchas banked + operator's 2026-05-22 AM WilsonCI surfacing decision.

---

## §1 OQ affirmations (BINDING for executing-plans phase)

**Per operator-paired triage 2026-05-21 PM #5** (post-housekeeping; in-chat affirmation): ALL 14 OQ dispositions from brainstorm spec §7 are AFFIRMED VERBATIM. Plan §A encodes spec §7 dispositions BINDING. The 14 OQs:

- **OQ-1**: NULL backfill for existing `trades.candidate_id` (no heuristic match).
- **OQ-2**: SB6c does NOT include Q4 surfaces (T4.SB owns; schema already in v20).
- **OQ-3**: `pre_version == 20 AND target >= 21` strict-equality backup-gate.
- **OQ-4** + OQ-5: N/A (Q4 schema already in v20).
- **OQ-6**: `reached_1r` = `max(daily_high since entry_date) >= entry_price + (entry_price - initial_stop)`; `hit_stop` = ANY fill at `<= initial_stop` OR `trade.state IN ('closed', 'reviewed') AND realized_R_if_plan_followed < 0`. Suppression at n<5 per Phase 10 honesty.suppress_for_n.
- **OQ-7**: N/A for SB6c (T4.SB owns Q4 surface dispositions).
- **OQ-8**: `swing-pre-phase13-sb6c-migration-<ISO>.db` backup file naming.
- **OQ-9**: row[52] = candidate_id; row[53] = pattern_evaluation_id (after `planned_target_R` at row[51] from migration 0016).
- **OQ-10**: 5-task decomposition T-A.6c.1..T-A.6c.5; **concurrent dispatch T-A.6c.1 + T-A.6c.2 + T-A.6c.3 recommended**; sequential T-A.6c.4 after T-A.6c.1; T-A.6c.5 closer.
- **OQ-11**: `trades.candidate_id` populated at trade-entry-form lock time inside `with conn:` block IF `trade_origin IN pipeline-origins` AND candidates lookup returns row; ELSE NULL.
- **OQ-12** (CLOSURE-COMMITTED at T-A.6c.4): `trades.pattern_evaluation_id` threaded via hidden form input + 5-tier rejection ladder + `claimed_pattern_evaluation_anchor` consistency-check gate; manual-off-pipeline persists NULL.
- **OQ-13**: Metric tile cohort denominator = LEFT JOIN from confirmed `pattern_evaluations` (via `pattern_exemplars.final_decision='confirmed'`); numerator subset with `trades.candidate_id` AND outcome bucket met; suppression at denominator<5.
- **OQ-14**: Volume profile via `swing.web.ohlcv_cache.get_or_fetch(ticker, window_days=80)` with fetch-on-cache-miss ACCEPTED.

---

## §1.5 Amendments (BINDING; executed alongside plan-encoded scope)

### §1.5.1 + §1.5.2 — INHERITED from writing-plans dispatch brief (REFERENCE; no re-encoding needed)

The §1.5.1 chart_renders cache write-through scope (pipeline-side `_step_charts` writes for 4 surfaces) + §1.5.2 labeler_evidence_json one-shot backfill script scope (Path C synthesis for existing 34 exemplars) from the writing-plans dispatch brief at `c9bd715` are **ALREADY ENCODED in the plan** at §C.3 + §C.4 + §G.2 + §G.3 — execute per plan; do NOT re-derive.

### §1.5.3 Test count impact (inherited from writing-plans brief §1.5.3; superseded by §1.5.4 below)

Plan §F baseline projection was ~92-95 fast tests + 1 fast E2E (post-§1.5.1 + §1.5.2 amendment bump from ~81 original). §1.5.4 below bumps further to **~94-98 fast + 1 fast E2E**.

### §1.5.4 NEW — Gap B.5 WilsonCI surfacing CLOSURE-COMMITTED at T-A.6c.4 (operator decision 2026-05-22 AM)

**Source:** AskUserQuestion 2026-05-22 AM by prior orchestrator post-merge of T2.SB6c writing-plans (handoff brief §3.2 captured the decision verbatim).

**Background:** Codex R5 MAJOR #2 during writing-plans caught a rendering-surface gap — `PatternOutcomeRow._ci` fields are populated by the service layer but NOT rendered by the template at `swing/web/templates/metrics/pattern_outcomes.html.j2:35-45` (only the ratio renders). The writing-plans plan §G.5 + return report §6 banked this as the 8th V1 simplification with a V2 dependency (template extension for WilsonCI surfacing per Phase 10 honesty.wilson_ci convention). **Operator decision overrides the V2 deferral**: CLOSE the V1 simplification entirely at T-A.6c.4 via in-scope template extension.

**Amendment scope (folded into T-A.6c.4):**
- **Extend** `swing/web/templates/metrics/pattern_outcomes.html.j2:35-45` to render `{n: N, Wilson CI L.LL-U.UU}` alongside the existing ratio, matching Phase 10 honesty.wilson_ci convention. Format string mirrors Phase 10's existing surfaces (grep `pattern_outcomes.html.j2` is the template; cross-reference Phase 10 honesty-surface templates for format-string fidelity — they live at `swing/web/templates/metrics/`).
- **~2-3 additional tests at T-A.6c.4**:
  1. Template render test — `_ci` fields with non-None values appear in the rendered HTML output (test pattern: render the template fragment with a populated `PatternOutcomeRow` + assert `Wilson CI` substring appears + assert numeric bounds appear).
  2. Format-string test — values format per Phase 10 convention (e.g., `0.43-0.91` not `0.43 - 0.91` or `0.430-0.910`); align with the format string used by existing Phase 10 honesty surfaces.
  3. Suppression-at-n<5 test — when `n < 5`, the suppression marker still fires (existing behavior preserved); WilsonCI does NOT render in the suppressed cell.
- **Closes the V1 simplification entirely**; ZERO V2 banking for the WilsonCI row in plan §G.5 + return report §6.
- **Test count bump**: ~92-95 → **~94-98 fast tests** at T-A.6c.4 + 1 fast E2E.
- **Cumulative process gotcha banking**: this closure is itself a manifestation of NEW gotcha #11 (template-rendering surface audit; CLAUDE.md gotchas as updated by post-writing-plans housekeeping at `e7d0cce`). Codex R5 MAJOR #2 caught the rendering gap during writing-plans; operator-paired triage decided to CLOSE it at executing-plans rather than V2-bank it. The return report should enumerate this in the V1-simplifications-with-V2-dependency table (§6) as a CLOSED row (with the V2 dependency citation marked "CLOSURE-COMMITTED at T-A.6c.4 per operator decision 2026-05-22 AM").

**Implementer note:** the amendment is structural (template extension + test additions) and does NOT change the schema/dataclass/service-layer plumbing — `PatternOutcomeRow._ci` fields are already populated correctly per writing-plans plan §G.4 (Codex R5 MAJOR #2 closure at `3644d55`). The amendment ONLY extends the consumer surface (template) + adds discriminating tests.

---

## §2 Scope inheritance from plan (concurrent dispatch + sequential pin)

The plan §G is the BINDING substrate for the 5-task decomposition. Reference the plan in execution; do NOT re-derive the task structure here.

### §2.1 5-task summary

| Task | Plan §G ref | Tests | Dependencies | Dispatch |
|---|---|---|---|---|
| T-A.6c.1 v21 migration atomic landing | §G.1 | ~17 paired + 4 backup-gate + 2 pin | None (foundation) | Concurrent |
| T-A.6c.2 Gap A chart-surface wiring + §1.5.1 chart_renders write-through | §G.2 | ~17-19 (~11 wiring + ~6-8 write-through) | None | Concurrent |
| T-A.6c.3 Gap B no-schema + §1.5.2 labeler backfill | §G.3 | ~18 (~13 review form + ~5 backfill) | None | Concurrent |
| T-A.6c.4 Gap B v21-dependent + entry-form anchor threading + entry-path mapping fix + VM/builder extensions + §1.5.4 WilsonCI surfacing | §G.4 + this brief §1.5.4 | 31 + 2-3 WilsonCI | T-A.6c.1 | Sequential |
| T-A.6c.5 Closer E2E + ruff sweep + cross-bundle pin row 12 promote | §G.5 | 1 fast E2E | All | Sequential (last) |

**Total test forecast: ~94-98 fast tests + 1 fast E2E** (was ~92-95 pre-§1.5.4 bump). Baseline 5559 → **~5653-5657 fast** post-T2.SB6c executing-plans.

### §2.2 Concurrent dispatch (recommended per OQ-10 LOCK)

Three subagents dispatched in parallel for T-A.6c.1 + T-A.6c.2 + T-A.6c.3 (no schema dependencies between them; T-A.6c.2 + T-A.6c.3 don't consume v21 schema). One subagent per task; agents may execute multiple tasks but task sets must be DISJOINT (per orchestrator-context "parallel-implementers-in-same-working-tree cross-contamination" precedent + Phase 2 `superpowers:subagent-driven-development` self-collision lesson). T-A.6c.4 dispatched sequentially after T-A.6c.1 lands (consumes Delta A + B). T-A.6c.5 dispatched sequentially after all four land.

Expected wall-clock savings: ~30-40% vs fully-sequential dispatch.

### §2.3 Schema v20 LOCKED streak ENDS at T-A.6c.1 landing

v20 has been LOCKED for 12+ sub-bundles since T-A.1.1 landed v20 atomically at T2.SB1. T-A.6c.1 lands v21 (Delta A + Delta B). Migration runner backup-gate strict equality `pre_version == 20 AND target >= 21` per OQ-3 + Phase 9 Sub-bundle A precedent.

---

## §3 Watch items + cumulative discipline (BINDING for executing-plans phase)

### §3.1 Pre-Codex 7-expansion discipline + 2 NEW refinements (27th cumulative validation expected)

Executing-plans phase pre-Codex review applies ALL 7 expansions PLUS 2 NEW refinements banked at T2.SB6c writing-plans for the 27th validation:

1. **Expansion #1** — hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`). Grep `swing/` for redundant copies of any constant introduced; add discriminating tests exercising EACH downstream consumer through production code path.
2. **Expansion #2** — brief-vs-spec source-of-truth (T2.SB4 R1 M1) + brief-vs-actual-schema reality check (T2.SB6c brainstorm Expansion #2 catch; NEW refinement). Verify the amendment §1.5.4 WilsonCI format string against actual Phase 10 honesty.wilson_ci-surfacing templates (do NOT paraphrase — read the canonical format string).
3. **Expansion #3** — schema-CHECK-vs-semantic-contract gap audit (T2.SB6a R1 CRITICAL #1). Dataclass `__post_init__` MUST mirror ALL semantic invariants (cache key shapes, partial-index existence, cross-column uniqueness via partial UNIQUE only) — NOT just schema CHECK.
4. **Expansion #4** — CLAUDE.md gotcha specific-scenario trace (T2.SB6a R1 MAJOR #2) **PLUS NEW REFINEMENT (T2.SB6c R1 banking; CONTINUED BINDING at writing-plans-phase PARTIAL FAIL)**: every SQL skeleton's columns MUST be verified against actual `swing/data/migrations/*.sql` files. Pre-Codex MUST grep `swing/data/migrations/*.sql` for every column reference in every SQL skeleton.
5. **Expansion #5** — cross-section spec inventory grep (T2.SB6a R1 MAJOR #3).
6. **Expansion #6** — content-completeness audit (T2.SB6b lessons). For T2.SB6c executing-plans: every spec data-surface item the implementation ships MUST have per-field disposition LIVE/V1-PARTIAL/V1-STUB; closure dispatch intent honored; no new V1 STUBs introduced.
7. **Expansion #7** — cross-row semantic audit on operator-input flows (T2.SB6b lessons) **PLUS NEW BOUNDARY CLARIFICATION (T2.SB6c brainstorm banking; CONTINUED BINDING at writing-plans-phase PARTIAL FAIL)**: cross-row semantic SCOPE audit (per-candidate vs per-ticker) does NOT subsume column/JOIN correctness — that's Expansion #4 territory.

**NEW Expansion #8 candidate (BINDING for 27th cumulative validation per writing-plans banking)**: **per-aggregation-function UNIT audit on SQL skeletons** — for any GROUP BY / COUNT / SUM / aggregation function, pre-Codex review MUST enumerate (a) what unit the function is counting (trades / evaluations / candidates / exemplars); (b) whether DISTINCT is needed to prevent JOIN-cardinality inflation (multi-table JOIN with 1:N cardinality MUST have DISTINCT or CTE-then-aggregate); (c) whether LIMIT applies at the correct unit. Discriminating test pattern: cardinality-multiplied row fixtures.

### §3.2 4 NEW gotchas from writing-plans banking BINDING for 27th cumulative validation

Applied verbatim from `CLAUDE.md` gotchas section (updated by post-writing-plans housekeeping at `e7d0cce`):

1. **SQL aggregation UNIT audit (NEW Expansion #8 candidate)**: see §3.1 above.
2. **Existing-field reuse audit before claiming new dataclass fields**: BEFORE claiming new fields on an existing dataclass, run `Grep "_n: int | None\|_ci: " <dataclass module>` against the existing module to find fields matching the planned-new-field shape; verify whether the existing fields are populated-and-rendered, populated-but-not-rendered, or absent. T-A.6c.4 WilsonCI surfacing per §1.5.4 above is itself an EXISTING-FIELD-REUSE flow (the `_ci` fields ALREADY exist; the amendment is template-rendering only).
3. **Template-rendering surface audit before claiming "no template edit needed"**: read the template's render path explicitly + enumerate which dataclass fields are rendered vs persisted-but-not-rendered. The §1.5.4 WilsonCI surfacing is the canonical T2.SB6c executing-plans example of this discipline — DO the template extension; assert via discriminating test that the new field appears in rendered HTML output.
4. **`date.fromisoformat()` discipline for cross-type-boundary calls**: when a SQL TEXT column feeds a Python helper expecting `date`/`datetime`, cite the conversion explicitly at the callsite (`date.fromisoformat(row[N])`) + add malformed-input discriminating test (graceful fallback / typed exception, NOT 500). Plan §G.3 Gap B.1 trend-template state lookup at `current_stage(conn, ticker, asof_date)` MUST cite `date.fromisoformat(pattern_evaluations.window_end_date)` conversion explicitly.

### §3.3 Cumulative schema-CHECK widening discipline (BINDING for T-A.6c.1)

- **§A.14 paired atomic landing** (Phase 12 C.A): schema CHECK widening + Python constant widening + dataclass `__post_init__` validator + read-path mapper extension + ALL discriminating tests land in ONE atomic task. T-A.6c.1 enumerates EACH explicitly per Delta A + Delta B.
- **N-mirror auditing** (T3.SB2 hotfix `cf3c489`): grep ALL `swing/` modules for hardcoded copies of any constant introduced; add discriminating tests exercising EACH downstream consumer through production code path.
- **Schema-CHECK + semantic contract paired discipline** (T2.SB6a R1 CRITICAL #1): dataclass `__post_init__` MUST mirror ALL semantic invariants (cache key shapes, partial-index existence, cross-column uniqueness via partial UNIQUE only) — NOT just schema CHECK.
- **Schema-version-aware INSERT for nullable columns** (T2.SB6c R1 expansion per writing-plans inheritance; T3.SB1 `fills.py:51-53` precedent): even nullable column extensions warrant the `PRAGMA table_info` runtime branch pattern. T-A.6c.1 plan §G.1 watch item.

### §3.4 Migration runner discipline (BINDING for T-A.6c.1)

- **Backup-gate strict equality**: `pre_version == 20 AND target >= 21` (OQ-3 affirmed). Copy Phase 9 Sub-bundle A backup-gate clause VERBATIM; do NOT paraphrase to `<=`.
- **`executescript()` implicit-COMMIT**: migration runner uses explicit `BEGIN`+`executescript`+`COMMIT` with try/except `rollback()` per `swing/data/db.py:_apply_migration` canonical.
- **`INSERT OR REPLACE` cascade-wipe**: NEW v21 INSERT paths use SELECT-then-UPDATE-or-INSERT for any upsert intent against tables with FK references.
- **Backup file naming**: `swing-pre-phase13-sb6c-migration-<ISO>.db` (OQ-8 affirmed).

### §3.5 Read-path mapping + write-path discipline (BINDING for T-A.6c.1)

- **Read-path mapping must keep pace with write-path** (T3.SB3 R1 M#1): T-A.6c.1 plan task extends `_row_to_trade` mapper with `row[52] = candidate_id; row[53] = pattern_evaluation_id` (OQ-9 affirmed) + adds 2 round-trip discriminating tests per Delta (persist via write path + read back via public reader; assert equality NULL + non-NULL).

### §3.6 Form-driven route discipline (BINDING for T-A.6c.4)

- **Server-recompute at POST** (T3.SB3 R1 M#2 LOCK): POST `/trades/entry` MUST re-derive `pattern_evaluation_id` from canonical state at POST time, NOT consume operator-submitted hidden input verbatim. The 5-tier rejection ladder rejects tampered anchors.
- **Hidden anchor 5-tier rejection ladder** (T3.SB1 4-tier extended; per spec §2.2 OQ-12): `claimed_pattern_evaluation_anchor` consistency-check gate validates: (a) malformed JSON → 400 + clear anchor; (b) non-dict JSON → 400 + clear; (c) dict missing required keys → 400 + clear; (d) dict with invalid value shapes → 400 + clear; (e) **NEW tier-5**: claimed_anchor inconsistent with server-derived `derive_trade_origin()` (e.g., entry_path mismatch) → 400 + clear.
- **Recovery form anchor-clear discipline** (T3.SB1 R3 M#2): on anchor-rejection 400, recovery form clears bad anchor (pass `submitted_*=None`, NOT raw rejected anchor).
- **EntryPath mapping fix at `swing/web/routes/trades.py:1095`** (T2.SB6c brainstorm forward-binding lesson #6): `derive_trade_origin(conn, ticker, entry_path: EntryPath)` cannot distinguish `pipeline_watch_hyp_recs` from `pipeline_watch_manual` if all web POSTs hardcode `EntryPath.MANUAL_WEB_FORM`. T-A.6c.4 fixes as side-effect of anchor-threading.
- **VM/builder fields as part of anchor-threading scope** (T2.SB6c brainstorm forward-binding lesson #7): enumerate all 4 layers (VM field + builder population + template emission + POST validation) per anchor; discriminating tests per layer.

### §3.7 Pipeline-side cache write-through discipline (§1.5.1 plan-encoded; BINDING for T-A.6c.2)

Per plan §C.3 + §G.2: `_step_charts` writes for 4 surfaces (watchlist_row + hyprec_detail + position_detail + market_weather; theme2_annotated handled separately at /patterns/exemplars cache-miss read path per existing T2.SB6b shipped behavior). Cache key shape per §C.2 (T2.SB6a substrate ChartRender `__post_init__` validates); F6 transient-empty defense at construction barrier; DELETE-then-INSERT atomic per §A.15 + BEGIN IMMEDIATE / COMMIT per §A.12 substrate contract.

### §3.8 Labeler evidence backfill script discipline (§1.5.2 plan-encoded; BINDING for T-A.6c.3)

Per plan §C.4 + §G.3 Path C: T-A.6c.3 ships one-shot backfill script `swing/cli.py:patterns_exemplars_backfill_labeler_evidence` that augments existing pattern_exemplars rows with `rule_criteria` + `narrative` keys synthesized from existing `geometric_evidence_narrative` + `geometric_score_json`. Idempotency contract + fail-soft per row + ASCII-only output per Windows cp1252 stdout safety. Path A (labeler subagent contract widening) banked V2 for FRESH exemplars labeled post-T2.SB6c (return report §6 row 7; preserves the V2 dependency citation).

### §3.9 V1 simplification banking discipline (T2.SB6c closure-committed + §1.5.4 amendment)

T2.SB6c is a CLOSURE dispatch. Every T2.SB6b §6 V1 simplification targeted by SB6c MUST be RESOLVED in the executing-plans output — NOT bank again. Return report §6 enumerates the 7 RESOLVED V1 simplifications + the 1 NEW closure-committed-via-§1.5.4-amendment (Gap B.5 WilsonCI surfacing; CLOSED at T-A.6c.4 per operator decision 2026-05-22 AM; ZERO V2 banking). NO new V1 STUBs introduced by SB6c.

### §3.10 Cumulative process discipline

- **NO Co-Authored-By footer** — cumulative ~360+ commit streak ZERO trailer drift through T2.SB6c writing-plans housekeeping at `e7d0cce`; do NOT regress. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (per `feedback_worktree_cli_invocation` memory).
- **ASCII-only on runtime CLI paths** + template narrative text (Windows cp1252 stdout safety per existing CLAUDE.md gotcha family; T-A.6c.3 backfill script ASCII-only output).
- **TDD per task** via `superpowers:test-driven-development`.
- **Edit tool for per-file edits**.
- **Cite the discipline in commit messages** per cumulative precedent.

---

## §4 Per-task summary (REFERENCE; plan §G is BINDING substrate)

Do NOT re-encode the plan in this brief. Plan §G covers per-task:
- Bite-sized step structure (Step 1a-1e / Step 1a-1c / Step 1a-1f / Step 1-6).
- Per-task acceptance criteria.
- Commit message templates.
- Test budgets per step.
- Cross-task dependency callouts.

§1.5.4 amendment in this brief extends T-A.6c.4 with WilsonCI surfacing scope (~2-3 additional tests + 1 template extension); fold into plan §G.4 Step 1-6 by adding a Step 7 OR extending an existing step's scope per the implementer's judgment.

---

## §5 Done criteria for executing-plans output

The executing-plans dispatch ships:

- [ ] **5 task commits** matching plan §G.1..§G.5 commit message templates (with §1.5.4 WilsonCI surfacing scope folded into T-A.6c.4's commit). ZERO Co-Authored-By footer trailer on each.
- [ ] **0-3 Codex fix bundle commits** for any adversarial-critic findings (expected 2-5 Codex rounds at executing-plans phase per cumulative precedent; pre-Codex 7-expansion + 2 NEW refinements + 4 NEW gotchas discipline BINDING).
- [ ] **1 return report** at `docs/phase13-t2-sb6c-executing-plans-return-report.md` covering:
  - Commit chain (5 task commits + 0-3 Codex fix bundles)
  - Codex chain shape (per-round verdict; total Critical + Major + Minor findings; resolution disposition; ACCEPT-WITH-RATIONALE banks per cumulative precedent — keep at ZERO if possible; closure-dispatch intent preferred)
  - Per-expansion verdict (27th cumulative C.C lesson #6 validation; ALL 7 expansions + 2 NEW refinements + 4 NEW gotchas BINDING)
  - V1 simplifications + V2 candidates banked per cumulative precedent (Gap B.5 WilsonCI row marked CLOSURE-COMMITTED at T-A.6c.4 per operator decision 2026-05-22 AM; ZERO V2 banking)
  - Forward-binding lessons banked
  - Cumulative streaks preserved (Co-Authored-By; C.C lesson #6; sub-bundle ship count)
  - Test count delta (baseline 5559 → ~5653-5657 fast + 1 fast E2E expected per plan §F.3 + §1.5.4 bump)
  - Schema delta (v20 → v21 LANDED at T-A.6c.1)
  - Cross-bundle pin row 12 PLANTED + un-skipped + GREEN
  - Inline self-verification: `python -m pytest -m "not slow" -q` (fast suite full PASS); `ruff check swing/` (0 E501); `python -c "import sqlite3; conn = sqlite3.connect(':memory:'); ..."` schema migration smoke (v21 LANDED).

---

## §6 References

- **Plan** (BINDING substrate): [`docs/superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md`](superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md) at HEAD `e26bb0a`
- **Writing-plans return report**: [`docs/phase13-t2-sb6c-writing-plans-return-report.md`](phase13-t2-sb6c-writing-plans-return-report.md)
- **Writing-plans dispatch brief (AMENDED)**: [`docs/phase13-t2-sb6c-writing-plans-dispatch-brief.md`](phase13-t2-sb6c-writing-plans-dispatch-brief.md) at commit `c9bd715`
- **Brainstorm spec**: [`docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md`](superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md)
- **Brainstorming return report**: [`docs/phase13-t2-sb6c-brainstorm-return-report.md`](phase13-t2-sb6c-brainstorm-return-report.md)
- **Phase 13 main plan**: [`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`](superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md) §G.9 (original T2.SB6 §) + §H.3 (cross-bundle pin schedule) + §A.14 (atomic-landing discipline)
- **Phase 13 main spec**: [`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`](superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md) §7.2 + §5.10 (BINDING for T2.SB6c content-completeness audit)
- **CLAUDE.md** at repo root — full cumulative gotcha set (updated by housekeeping commit `e7d0cce` with 4 NEW gotchas)
- **Phase 12 Sub-sub-bundle C.A writing-plans dispatch brief + plan**: schema-widening atomic-landing precedent (BINDING for T-A.6c.1)
- **Phase 9 Sub-bundle A writing-plans dispatch brief + plan**: similar-scale schema migration precedent (BINDING for T-A.6c.1 backup-gate)
- **T2.SB6b return report**: [`docs/phase13-t2-sb6b-return-report.md`](phase13-t2-sb6b-return-report.md) §6 V1 simplifications (CLOSURE TARGETS for SB6c)
- **T2.SB6a return report**: [`docs/phase13-t2-sb6a-return-report.md`](phase13-t2-sb6a-return-report.md) (FROZEN substrate API surface BINDING)

---

## §7 NON-scope (V2 / future arc)

- Phase 13.5 drift surfaces (V2).
- ZERO new Schwab API calls (L2 LOCK preserved through this dispatch).
- T4.SB usability triage items (operator-supplied; PAUSE-FOR-LIST-ADDITIONS BINDING per `project_phase13_t4_sb_pause_for_list_additions` memory at T2.SB6c executing-plans SHIPPED + housekeeping boundary).
- Q4 close-tracking flag surfaces — T4.SB owns (schema already in v20 per migration 0020:262-307).
- Many-to-many `trade_pattern_evaluations` link table (V2 schema dispatch; per brainstorm spec §9 V2 candidates).
- `--enforce-stepwise` migration flag (V2 migration-runner enhancement; per brainstorm spec §9).
- Phase 6 chart_pattern_algo enum unification with Phase 13 detector enum (V2 schema dispatch; per brainstorm spec §9).
- Path A labeler subagent emit contract widening for FRESH exemplars (V2; per plan §I + return report §6 row 7 — preserve the V2 dependency citation).
- Full Weinstein 4-stage labeling (V2 trend-template enhancement; per `current_stage` wrapper at `swing/patterns/foundation.py:745` thin-wrapper LOCK).
- `pattern_evaluations.candidate_id` direct column (V2 schema dispatch if Phase 13.5+ surfaces require frequent per-candidate cross-row lookups).
- Multi-pattern_class trade backlink (V2 many-to-many link table per brainstorm spec §9; T2.SB6c persists single-anchor per OQ-1 family).
- V2 candidates from brainstorm spec §9 + writing-plans return report §6 + 4 NEW gotchas Expansion #8 process automation (SQL-skeleton-extraction + sqlite-fixture-compile gate).

---

## §8 Post-executing-plans handback

When executing-plans Codex chain converges to NO_NEW_CRITICAL_MAJOR:

1. Write return report at `docs/phase13-t2-sb6c-executing-plans-return-report.md` per cumulative precedent (commit chain + per-expansion verdict + Codex chain shape + forward-binding lessons + V1 simplifications + V2 candidates + cumulative streaks; Gap B.5 WilsonCI row CLOSURE-COMMITTED entry per §1.5.4 above).
2. Inline self-verification:
   - `python -m pytest -m "not slow" -q` (fast suite full PASS; expected 5559 → ~5653-5657 fast + 1 fast E2E)
   - `ruff check swing/` (0 E501)
   - Schema migration smoke (v21 LANDED)
   - Backup-gate strict equality verified
3. Hand back to operator with summary.

Orchestrator-side next steps post-executing-plans return:
- QA implementer product per `feedback_orchestrator_qa_implementer_product` (verify file:line + shipped-behavior + locks-preserved against reality on disk).
- Merge executing-plans branch `--no-ff` to main; push.
- Post-merge housekeeping bundle (CLAUDE.md line 3 refresh + any NEW gotchas + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote + archive-split per size-check trigger).
- Operator-paired S1-S8 (or relevant subset) browser gates re-run vs T2.SB6c closures (validates §1.5.1 chart_renders write-through + §1.5.2 labeler backfill + §1.5.4 WilsonCI surfacing all land in operator's browser).
- **[PAUSE FOR OPERATOR LIST ADDITIONS]** surface per `project_phase13_t4_sb_pause_for_list_additions` memory — operator-supplied usability triage items required BEFORE T4.SB dispatch brief commissioning per spec §7.3 5-field template.
- T4.SB dispatch brief commissioning (operator-paired session; Theme 4 usability work only — Q4 close-tracking flag schema already in v20).

---

*End of T2.SB6c executing-plans dispatch brief. Plan at `e26bb0a` is BINDING substrate; 14 OQs operator-affirmed VERBATIM per orchestrator-paired triage 2026-05-21 PM #5; §1.5.1 + §1.5.2 amendments inherited via plan; §1.5.4 NEW WilsonCI surfacing operator decision 2026-05-22 AM CLOSURE-COMMITTED at T-A.6c.4; concurrent dispatch T-A.6c.1+2+3 + sequential T-A.6c.4 + T-A.6c.5; ~94-98 fast tests + 1 fast E2E projected; schema v20 → v21 LANDS at T-A.6c.1; ~360+ ZERO Co-Authored-By footer streak preserved through housekeeping at `e7d0cce`; 27th cumulative C.C lesson #6 validation expected with ALL 7 EXPANSIONS + 2 NEW REFINEMENTS (#4 SQL-column verification + #8 candidate SQL aggregation UNIT audit) + 4 NEW gotchas (existing-field reuse audit + template-rendering surface audit + date.fromisoformat discipline + SQL aggregation UNIT audit) BINDING. PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding post-SB6c-executing-plans SHIPPED + housekeeping boundary.*
