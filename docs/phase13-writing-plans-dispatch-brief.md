# Phase 13 — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 13 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan that decomposes the Phase 13 4-theme architectural arc (charts + pattern recognition + auto-fill + usability) into 11 sub-bundles with per-task acceptance criteria. Consumes the operator-confirmed brainstorm spec at `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` (1483 lines; 7 Codex rounds; ZERO ACCEPT-WITH-RATIONALE) + the 12 OQ dispositions operator-confirmed at orchestrator-pre-writing-plans triage (2026-05-18 PM).

**Brief:** `docs/phase13-writing-plans-dispatch-brief.md` (this file).

**Brainstorm spec:** `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` (1483 lines; PRIMARY substrate).

**Sequencing:** Phase 13 brainstorm SHIPPED 2026-05-18 PM at `b5e62c5`. This writing-plans dispatch is the next step. Output feeds 11 executing-plans dispatches (one per sub-bundle; T1.SB0 first per OQ-1 + OQ-12 ordering).

**Expected duration:** ~3-5 substantive Codex rounds (Phase 13 is largest scope arc to date; brainstorm absorbed substantial design surface so writing-plans focuses on per-task decomposition). Plan line target: ~2000-3000 lines (per Phase 10 writing-plans precedent: 2008 lines for 5 sub-bundles / 33 tasks; Phase 13 has 11 sub-bundles).

---

## §0 Read first

In this order:

1. **`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`** — operator-confirmed brainstorm spec (1483 lines; 7 Codex rounds; ZERO ACCEPT-WITH-RATIONALE). **THIS IS THE PRIMARY SUBSTRATE.** Read end-to-end. §1 has 11 operator-locked decisions L1-L11 (Q4 amendment absorbed into L11). §3 has v19→v20 schema delta with §3.0 `DETECTOR_PATTERN_CLASSES` enum LOCK + §3.1 pattern_exemplars 3-column refactor with 5 numbered cross-column CHECK invariants. §4-§7 cover Theme 1/2/3/4. §8 has 11-sub-bundle decomposition refinement. §9 has 12 OQs with brainstorm-recommendations + dispositions (ALL operator-confirmed BINDING at 2026-05-18 PM triage). §10 has 5-pattern discriminating walkthroughs + §10.6 + §10.7 LOCKs. §11 has forward-binding lessons inherited.

2. **`docs/phase13-writing-plans-dispatch-brief.md`** (this file).

3. **§9 OQ-confirmed dispositions** (verbatim from orchestrator-pre-writing-plans triage 2026-05-18 PM; ALL 12 OQs confirmed at brainstorm-recommended dispositions — see §1.3 below).

4. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" + "Lessons captured" + "Maintenance: retention discipline" (especially the §"Size-check trigger at housekeeping-commit time" subsection added 2026-05-18 PM).

5. **`CLAUDE.md`** at repo root — project conventions + gotchas. ESPECIALLY:
   - HTMX gotcha trinity (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted) for every new form-driven route.
   - Matplotlib mathtext gotcha (Phase 10 §A.10 inline-SVG LOCK precedent for Theme 1 chart rendering).
   - `base.html.j2` shared-field discipline (every new VM extending base.html.j2 must populate `unresolved_material_discrepancies_count` + `banner_resolve_link` per Phase 10 T-E.3 + Phase 12.5 #2 13-VM standalone retrofit precedent).
   - Session-anchor read/write mismatch family (forward-looking `action_session_for_run` vs backward-looking `last_completed_session`).
   - SQLite `INSERT OR REPLACE` cascade-wipe gotcha.
   - `executescript()` implicit-COMMIT gotcha (Phase 7 Sub-A R1 Major 3; Phase 8 plan-template defect; binding for any new migration).
   - Schema-CHECK + Python-constant + dataclass-validator paired discipline (Phase 12 C.A T-A.2 LOCK).
   - Migration backup-gate strict equality (`pre_version == 19`, NOT `<=`).
   - Windows cp1252 stdout gotcha (ASCII-only on runtime CLI paths).
   - `construct_authenticated_client` 4-arg signature discipline + `apply_overrides(cfg)` cascade at every Schwab entry point + `resolve_credentials_env_or_prompt(allow_prompt=False)` discipline.
   - In-tree reject-caller-held-tx contract for transactional services (Phase 8 R3→R4 cascade + Phase 12 C.C lesson #2 + #3).
   - The full Gotchas section is ~35+ entries; treat ALL as forward-binding lessons for Phase 13 writing-plans.

6. **Precedent plan docs** (format reference):
   - `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (2008 lines; 5 sub-bundles; 33 tasks; closest scope-precedent).
   - `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` (1215 lines; post-Phase-12 1-sub-bundle plan).
   - `docs/superpowers/plans/2026-05-18-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` (1230 lines; Phase 12.5 #1 1-sub-bundle plan; convergent shape precedent).
   - `docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md` (1082 lines; Phase 12.5 #2 1-sub-bundle plan).
   - `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (1101 lines; Phase 12.5 #3 1-sub-bundle plan).

7. **`docs/phase3e-todo.md`** top entries 2026-05-18 in TOP-DOWN order: Phase 13 brainstorm SHIPPED entry; Phase 12.5 #3 SHIPPED entry; queued cleanup items entries.

8. **`reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md`** (901 lines; AI-ingestion-ready) — operator-authored chart pattern detection brief. The brainstorm spec absorbs this; read selectively for context on Theme 2 detector criteria (especially §5.1 illustrative VCP precedent + §6.4 label schema + §9.2 evidence-to-show-reviewer checklist).

---

## §0.5 Skill posture

- Invoke **`copowers:writing-plans`** (wraps `superpowers:writing-plans` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:brainstorming` — brainstorm is complete (spec at `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`).
- DO NOT invoke `superpowers:executing-plans` — writing-plans output only; per-sub-bundle executing-plans dispatches come later.
- DO NOT invoke `superpowers:test-driven-development` — no code changes.
- DO NOT invoke `superpowers:using-git-worktrees` — plan doc commit only.

---

## §1 Strategic context — operator-locked + OQ-confirmed (do NOT re-litigate)

### §1.1 11 operator-locked binding decisions L1-L11 (inherited verbatim from brainstorm spec §1)

Per brainstorm spec §1 (locked 2026-05-17 via operator-orchestrator scope conversation; Q4 amendment 2026-05-18 absorbed into L11):

- **L1** — Algorithm posture: rule-based geometric PRIMARY; template matching SECONDARY; **NO run-time AI inferencing** (Claude API in pipeline runtime FORBIDDEN; dev-time Claude Code subagent dispatch for labeling per v2 brief §8.2 IS allowed).
- **L2** — V1 pattern set: 5 buy-side patterns (`vcp` + `flat_base` + `cup_with_handle` + `high_tight_flag` + `double_bottom_w`).
- **L3** — Sell-side detector module: BANKED to Phase 14 (H&S top / climax run / Stage 4 breakdown / MA50/MA200 violations all OUT).
- **L4** — ML re-ranker: DEFERRED indefinitely (12-18 months minimum per v2 brief §16.6; 7 gates G1-G7 not yet met).
- **L5** — Drift detection monitoring side: SPLIT to Phase 13.5 (4 surfaces feature/pattern frequency/outcome/self-drift). Phase 13 BAKES IN the LOGGING side ONLY.
- **L6** — Schema appetite: v19 → v20 single migration; v21+ possible per theme. **Q4 schema FOLDS INTO v20** per spec §7.2 v20-folds-in LOCK (preserves L6 single-migration discipline).
- **L7** — Strategic posture: 100% operational (Branch B priority-stack continuation; research-branch Phase 0 activation NOT in Phase 13 scope).
- **L8** — Single-strategy focus: SEPA + DST.
- **L9** — Codex as second reviewer: SELECTIVE (NOT blanket) per OQ-5 disposition.
- **L10** — Theme 3 absorbs original Phase 12.5 #2 fill auto-population at trade-entry (entries + exits + reviews + period reviews owned coherently by Theme 3).
- **L11** — Theme 4 elicitation absorbed Q4 close-tracking flag at brainstorm-output time (operator-pre-writing-plans elicitation closed 2026-05-18 PM: **no additional usability items**; T4.SB ships Q4 D-Q4.1..D-Q4.7 baseline lock only).

### §1.2 11-sub-bundle decomposition (per spec §8 + OQ-1 confirmed)

Dispatch sequence (per OQ-12 Option E v20 migration landing timing):

```
T1.SB0 (OhlcvCache → _step_charts wiring; prerequisite)
    -> T2.SB1 (dev-time labeling infra) || T3.SB1 (entry auto-fill; concurrent off T2.SB1's first-commit SHA per OQ-12)
        -> [operator-paired exemplar bootstrap pause per OQ-6]
    -> T2.SB2 (foundation primitives)
    -> T2.SB3 (detectors batch 1: VCP + flat base + cup-with-handle)
    -> T3.SB2 (exit auto-fill)
    -> T2.SB4 (detectors batch 2: high-tight-flag + double-bottom-W)
    -> T2.SB5 (template matching)
    -> T3.SB3 (review auto-fill)
    -> T2.SB6 (closed-loop surface + Theme 1 annotated charts)
    -> T4.SB (usability triage + Q4 close-tracking flag)
    -> Phase 13 CLOSED
```

Cumulative test delta projection (per brainstorm spec §8.2): +590-1020 fast tests + 4 slow E2E across Phase 13 arc. Phase 13 close projection: ~5500-5940 fast (from current 4924 baseline).

### §1.3 12 OQ dispositions (operator-confirmed 2026-05-18 PM at orchestrator-pre-writing-plans triage)

ALL 12 OQs confirmed at brainstorm-recommended dispositions. Writing-plans phase encodes these verbatim as locked decisions; each Sub-bundle's writing-plans section reflects the relevant OQ disposition.

| OQ | Topic | Confirmed disposition |
|---|---|---|
| OQ-1 | Sub-bundle count drift | BINDING: 11 sub-bundles per scope-brainstorm §0.5.2 LOCK; T1.SB0 first |
| OQ-2 | Chart rendering tech + cache | BINDING V1: matplotlib SVG inline + NEW `chart_renders` cache table |
| OQ-3 | `pattern_class` enum + table location | BINDING: Option (b) new `pattern_evaluations` table; 5 V1 values; no sell-side reservation |
| OQ-4 | Template matching distance | BINDING V1: DTW with Sakoe-Chiba band (window=0.1 × series_length); 120s benchmark gate; SBD V2 fallback |
| OQ-5 | Codex SELECTIVE policy | BINDING: phased 15% random + high-stakes disagreement (confidence==high + geometric<0.5 OR confidence==low + geometric≥0.8); retroactive evaluation at T2.SB3+/SB4 |
| OQ-6 | Exemplar bootstrap workflow | BINDING: mirror Sub-bundle 1 cassette session precedent (operator-paired mid-dispatch pause) |
| OQ-7 | `fill_origin` enum + backfill | BINDING V1: 5-value enum (operator_typed / schwab_auto / schwab_auto_then_operator_corrected / migration_backfill / import_csv); simple backfill to 'migration_backfill' |
| OQ-8 | Review auto-fill MFE/MAE source | BINDING: OhlcvCache (post-T1.SB0); yfinance V2-fallback only |
| OQ-9 | Drift logging shape | BINDING V1: JSON column `pattern_evaluations.feature_distribution_log_json`; promote to dedicated table V2 only if Phase 13.5 demands |
| OQ-10 | T2.SB6 route location | BINDING: BOTH NEW `/patterns/{candidate_id}/review` route AND NEW `/metrics/pattern-outcomes` 9th metric tile |
| OQ-11 | T2.SB1 subagent location | CONFIRMED: `.claude/agents/pattern-labeler.md` (Claude Code project-local) |
| OQ-12 | v20 migration landing timing | BINDING: Option E (v20 lands as T2.SB1 task 1; T3.SB1 branches off T2.SB1's first-commit SHA; concurrent on bulk; merge order T2.SB1 first) |

### §1.4 Inherited DROP rules

- No magnitude-based threshold (v2 brief §5.1 weakness; mitigated via tolerance bands per spec §10.6 LOCK).
- No retroactive audit-row rewriting (Phase 12 Sub-bundle C inheritance).
- No re-litigating §1 + §0.5 + OQ dispositions (operator-locked; OQ-confirmed).
- No run-time AI inferencing (L1).
- No sell-side detector (L3; Phase 14 banked).
- No ML re-ranker (L4; indefinitely deferred).
- No drift monitoring/dashboard side (L5; Phase 13.5 banked; ONLY logging-side baseline).
- No multi-cohort architectural deepening (Phase 14+; L8).
- No image-based CV / sequence transformers / harmonic-candlestick-intraday patterns / fixed-window pattern detection.

### §1.5 Forward-binding lessons inherited (per brainstorm spec §11)

~60 cumulative lessons inherited from Phase 11 + 12 + 12.5 arcs. Writing-plans phase encodes the most-load-bearing as binding contracts in §F (invariants) of the plan:

**Most load-bearing for Phase 13 writing-plans + executing-plans:**
1. Schema-CHECK + Python-constant + dataclass-validator paired atomic landing (Phase 12 C.A T-A.2). Applies to every CHECK enum + cross-column CHECK in v20.
2. Migration backup-gate strict equality form (`pre_version == 19`, NOT `<=`).
3. `executescript()` implicit-COMMIT — migration runner uses explicit BEGIN/COMMIT/ROLLBACK; foreign_keys=OFF discipline.
4. Repo-level function from inside outer `with conn:`, NOT service-level wrapper (Phase 8 transactional discipline).
5. Reject-caller-held-tx contract on transactional services (Phase 8 R3→R4 + Phase 12 C.C lessons #2 + #3).
6. Sandbox short-circuit ALWAYS lives in inner function, NOT outer (Phase 12 C.C lesson #2).
7. SELECT-first idempotency precedes payload validation (Phase 12 C.C lesson #3).
8. Counter staleness after inline state mutation — recompute via SELECT COUNT(*) post-loop (Phase 12 C.C R1 M#3 fix pattern).
9. Cassette URI/path + body sanitization filter installation for ALL new cassette infrastructure (post-Phase-12 forward-binding lesson #2).
10. `construct_authenticated_client` 4-arg signature discipline + `resolve_credentials_env_or_prompt(allow_prompt=False)` + `apply_overrides(cfg)` at every Schwab entry point.
11. HTMX gotcha trinity: HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted (Phase 5 R1 M1 + M2 + Phase 6 I3).
12. Base-layout VM banner pin (Phase 10 T-E.3 + Phase 12.5 #2 13-VM standalone retrofit) — every new VM extending base.html.j2 populates `unresolved_material_discrepancies_count` + `banner_resolve_link`.
13. Form-render hidden anchors driving POST-time validation MUST round-trip through soft-warn confirm `form_values` dict (Phase 9 Sub-bundle D R3 Critical #1).
14. Server-stamping at handler entry for hidden audit fields; display-only `<span class="muted">` for visibility (Phase 8 + Phase 9 + Phase 12 form-driven-route discipline).
15. Session-anchor read/write mismatch family (forward-looking `action_session_for_run` vs backward-looking `last_completed_session`).
16. Python `... or ""` collides with SQL CHECK-constraint nullability (use `... or None` for nullable enum-CHECK columns).
17. Windows cp1252 stdout — ASCII-only on runtime CLI paths.
18. `INSERT OR REPLACE` cascade-wipe — SELECT-then-UPDATE-or-INSERT for UPSERT patterns.
19. Synthetic-fixture-vs-production-emitter shape drift (Phase 12 C.D + Phase 12.5 #2 + Phase 12.5 Q2 family — discriminating regression tests use production-emitter shape).
20. matplotlib mathtext gotcha — inline SVG avoids entirely (Phase 10 §A.10 LOCK).

---

## §2 Writing-plans scope (in scope)

Produce a plan at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` covering §2.1-§2.13 below.

### §2.1 Plan structure (mirror Phase 10 plan precedent for multi-sub-bundle)

Plan section structure (mirror `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`):
- §0 Top-matter: spec reference + brainstorm dispatch + OQ dispositions verbatim.
- §A General architectural decisions inherited from brainstorm spec (L1-L11 + OQ dispositions).
- §B v20 migration mechanics (per OQ-12 Option E + spec §3.5).
- §C Theme 1 architectural decisions (per spec §4 + OQ-2).
- §D Theme 2 architectural decisions (per spec §5 + OQ-3/4/5/9/10).
- §E Theme 3 architectural decisions (per spec §6 + OQ-7/8).
- §F Theme 4 architectural decisions (per spec §7 + Q4 D-Q4.1..D-Q4.7).
- §G Per-sub-bundle task decomposition (T1.SB0 through T4.SB; ~30-50 tasks total).
- §H Cross-bundle dependencies + un-skip pin schedule.
- §I Discriminating examples + watch items.
- §J V2.1 §VII.F amendment candidates banked.
- §K Test + LOC projections per Sub-bundle.
- §L Forward-binding lessons for executing-plans inheritance.

### §2.2 Per-task acceptance criteria

For each task in §G:
- Task ID (e.g., T-A.0.1, T-A.0.2 for T1.SB0; T-A.1.1, ..., T-A.1.N for T2.SB1; etc.)
- Scope (1-3 sentences)
- File path(s) touched (use grep at writing-plans time to verify file existence; flag discrepancies)
- Function / class / route / template signatures (Python type signatures; SQL schema; Jinja template `{% extends %}` parents)
- Discriminating test pattern (per Phase 12 C.A schema-CHECK + Phase 12 C.C SELECT-first + Phase 9 Sub-bundle D form-render-hidden-anchor + relevant family pattern)
- Cross-references to brainstorm spec §X.Y / OQ disposition / forward-binding lesson #N
- Test delta projection (e.g., "+5-8 fast" per task)
- LOC projection (e.g., "+50-80 production LOC + +80-120 test LOC")

### §2.3 v20 migration mechanics (per spec §3.5 + OQ-12 Option E)

Per OQ-12 Option E LOCK:

1. **T2.SB1 task T-A.1.1 = migration-only commit on T2.SB1 worktree branch**:
   - File: `swing/data/migrations/0020_phase13_charts_patterns_autofill.sql` (or similar).
   - Backup-gate: `pre_version == 19` (strict equality).
   - Migration mechanics: explicit BEGIN / COMMIT / ROLLBACK per Phase 12 C.A T-A.2 LOCK; foreign_keys=OFF discipline.
   - Schema deltas per spec §3 (NEW `pattern_exemplars` 3-column refactor + NEW `chart_renders` + NEW `pattern_evaluations` + widening `fills.fill_origin` NOT NULL with backfill + widening `schwab_api_calls.surface` enum + Q4 `watchlist_close_track_flags` + `watchlist_close_track_flag_events` tables).
   - `EXPECTED_SCHEMA_VERSION` bump 19 → 20 in `swing/data/db.py`.
   - Python-side constants + dataclass validators paired (`DETECTOR_PATTERN_CLASSES` + `_FILL_ORIGIN_VALUES` + `_FINAL_DECISION_VALUES` + `_LABEL_SOURCE_VALUES` + others per spec §3.1 cross-column CHECKs).

2. **T3.SB1 worktree branches off T2.SB1's first-commit SHA explicitly (NOT off main)**:
   - Implementer-dispatch coordination at T3.SB1 brief enumerates the first-commit SHA as the branch base.
   - T3.SB1 task T-B.1.1 (or equivalent) verifies schema_version == 20 at startup (no-op assert if migration is already applied via T2.SB1 task 1).

3. **Merge ordering**: T2.SB1 merges first (closes v20 atomic landing); T3.SB1 merges second (consumer-side widening).

4. **Cross-bundle pin**: T-A.1.1 plants `test_schema_version_v20_invariant` cross-bundle pin that un-skips at T3.SB1 merge.

### §2.4 Theme 1 — Chart rendering deepening (per spec §4 + OQ-2)

T1.SB0 + T2.SB6 + the `chart_renders` cache architecture per spec §4.4. Per-task decomposition:

- **T1.SB0** (~3-5 tasks): OhlcvCache wiring into `_step_charts` per spec §4.1; shape reconciliation; per-cache locking.
- **T2.SB6** (~6-8 tasks): closed-loop review surface (`/patterns/{candidate_id}/review` route) + annotated chart rendering (Theme 1 + Theme 2 coupling at T2.SB6) + 9th metric tile `/metrics/pattern-outcomes`.

Cache architecture per OQ-2:
- New `chart_renders` SQLite table (3 partial unique indexes per surface class + 1 cross-column CHECK per spec §3.2).
- matplotlib SVG inline rendering (Phase 10 §A.10 LOCK precedent).
- Cache invalidation via `source_data_hash` change on OHLCV cache mtime.

### §2.5 Theme 2 — Pattern recognition deepening (per spec §5 + OQ-3/4/5/9/10)

Per spec §5.1-§5.11 + 5-pattern walkthroughs at §10.1-§10.5. Per-task decomposition:

- **T2.SB1** (~6-9 tasks; CONCURRENT with T3.SB1 per OQ-12 Option E):
  - Migration-only commit task 1 (per §2.3 above).
  - Dev-time labeling infra: `swing patterns label-exemplars` CLI + `.claude/agents/pattern-labeler.md` subagent definition (per OQ-11).
  - Selective Codex policy (T2.SB1 phase: random 15% only; per OQ-5 phased rollout).
  - Operator-paired exemplar bootstrap pause (per OQ-6 Sub-bundle 1 cassette session precedent).
  - Cross-bundle pin tests for `pattern_exemplars` schema invariants.

- **T2.SB2** (~6-8 tasks): foundation primitives (EMA smoothing + kernel regression secondary + zigzag adaptive-threshold extrema + variable-window candidate generator).

- **T2.SB3** (~9-12 tasks): VCP + flat base + cup-with-handle rule-based detectors per spec §5.2 + §5.3 + §5.4 + §10.6 + §10.7 LOCKs.

- **T2.SB4** (~7-10 tasks): high-tight-flag + double-bottom-W detectors per spec §5.5 + §5.6.

- **T2.SB5** (~6-8 tasks): DTW template matching layer per spec §5.7 + OQ-4 (DTW with Sakoe-Chiba band; window=0.1 × series_length; 120s pytest-benchmark gate; SBD V2 fallback).

- **T2.SB6** (~6-8 tasks): closed-loop surface + Theme 1 annotated charts (shared with §2.4 T2.SB6 above).

Drift logging baseline substrate per OQ-9 + spec §5.11: `pattern_evaluations.feature_distribution_log_json` per detector run; JSON envelope shape per §5.11 (smoothing params + extrema density + contraction depths / center-trough retracement + volume aggregates + composite_score histogram bin count).

### §2.6 Theme 3 — Auto-fill deepening (per spec §6 + OQ-7/8)

Per spec §6.1-§6.6. Per-task decomposition:

- **T3.SB1** (~5-7 tasks; CONCURRENT with T2.SB1 per OQ-12 Option E):
  - Entry auto-fill at `GET /trades/entry/form`; Schwab Trader API `account_orders` + `account_details` consumption.
  - `construct_authenticated_client` 4-arg signature + `resolve_credentials_env_or_prompt(allow_prompt=False)` + `apply_overrides(cfg)` at handler entry per forward-binding lesson #10.
  - `fill_origin` enum widening per OQ-7 (5-value enum; migration_backfill simple V1 backfill).
  - Hidden audit anchors: `schwab_source_value_json` + `auto_fill_audit_at`; server-stamping discipline per Phase 8 R2-R5 family.
  - HTMX gotcha trinity discipline per forward-binding lesson #11.

- **T3.SB2** (~4-6 tasks): exit auto-fill mirroring T3.SB1 architecture.

- **T3.SB3** (~5-7 tasks; sequenced after T2.SB5): review auto-fill (priors + MFE/MAE from OhlcvCache per OQ-8); period-review section-text auto-fill.

### §2.7 Theme 4 — Usability triage + Q4 close-tracking flag (per spec §7 + L11)

T4.SB scope per spec §7.1 LOCK + Q4 §7.2 D-Q4.1..D-Q4.7 (operator-elicited usability list confirmed empty at orchestrator-pre-writing-plans 2026-05-18 PM; T4.SB ships Q4 only).

Per-task decomposition:

- **T4.SB** (~6-9 tasks): Q4 close-tracking flag implementation per spec §7.2 D-Q4.1..D-Q4.7:
  - NEW `watchlist_close_track_flags` table (D-Q4.1 Option B; per spec §3 schema sketch + PARTIAL UNIQUE INDEX on active flags only per Codex R1 M#9).
  - NEW `watchlist_close_track_flag_events` audit table (D-Q4.7).
  - Web toggle + CLI subcommands (D-Q4.2): `POST /watchlist/{ticker}/flag` route + `swing watchlist flag <ticker> --close-track` + `swing watchlist unflag <ticker>` CLI.
  - Persistence semantics per D-Q4.3: persistent-until-cleared OR auto-clear-on-position-open (transactional discipline LOCK per Phase 8 + Phase 12 C.C lesson #2 + #3 inheritance; reject-caller-held-tx + BEGIN IMMEDIATE uniform-regardless-of-env + sandbox short-circuit in inner + audit-row append-only).
  - Badge inline on watchlist row + sort-priority-first (D-Q4.4); ASCII-only per Windows cp1252 stdout safety.
  - UNION'd watchlist surface (D-Q4.5) — false-negative guard mechanism.
  - Watchlist-surface-only (D-Q4.6) — no hyp-rec elevation V1.

### §2.8 Cross-bundle pin discipline (per spec §8.4)

Per Phase 10 T-A.7 + T-E.3 + Phase 12 C.A T-A.7 + Phase 12.5 #2 cross-bundle-pin precedent:
- T1.SB0 plants OhlcvCache wiring invariant pin; un-skips at T2.SB2 + T2.SB3 + T3.SB3 (consumers).
- T2.SB1 task 1 (migration) plants `test_schema_version_v20_invariant` pin; un-skips at T3.SB1 merge.
- T2.SB1 plants `test_pattern_exemplars_schema_shape_invariant` pin; un-skips at T2.SB3 + T2.SB5 (consumers).
- T3.SB1 plants `test_fill_origin_enum_complete_after_v20` pin; un-skips at T3.SB2.
- T2.SB6 closes Theme 1 + Theme 2 cross-bundle pin: shared annotated chart renderer rendering across all 5 V1 patterns.

### §2.9 Schema sketches consumed verbatim (per spec §3)

The brainstorm spec §3 provides schema sketches for v20. Writing-plans transcribes these into per-task migration content:

- §3.0 `DETECTOR_PATTERN_CLASSES` enum LOCK (5 V1 values).
- §3.1 NEW `pattern_exemplars` 17-20 column table with 3-column labeling refactor + 5 numbered cross-column CHECK invariants.
- §3.2 NEW `chart_renders` cache table with 3 partial unique indexes + 1 cross-column CHECK.
- §3.3 NEW `pattern_evaluations` detector run output cache.
- §3.4 widenings: `fills.fill_origin` (NOT NULL with backfill); `schwab_api_calls.surface` enum widening (`'trade_entry'` + `'trade_exit'` per spec §6 + Phase 12 Sub-bundle B precedent).
- §7.2 Q4 schema additions (folds into v20 per L6).

### §2.10 Operator-paired pause point (per OQ-6)

T2.SB1 includes a mid-dispatch operator-paired pause (per OQ-6 Sub-bundle 1 cassette session precedent). Writing-plans encodes this explicitly:

- T2.SB1 task list includes the pause point as a distinct task (e.g., T-A.1.7 "Mid-dispatch operator-paired exemplar bootstrap session").
- Pre-pause: implementer ships labeling infra + recording-script + sanitization filter; commits to worktree branch.
- During pause: operator runs labeling against historical universe; spot-checks; commits exemplar corpus to worktree branch.
- Post-pause: implementer resumes T2.SB1 dispatch; selective Codex 15% random firing; audit row writes.
- T2.SB1's executing-plans dispatch brief specifies the pause point + operator handoff.

### §2.11 §7.1 LOCK — no additional usability items

Per orchestrator-pre-writing-plans elicitation closed 2026-05-18 PM: operator confirmed no unreported usability items. T4.SB ships Q4 close-tracking flag only per spec §7.1 baseline lock. Writing-plans §F (Theme 4 architectural decisions) encodes this LOCK + cites operator decision date.

### §2.12 V2.1 §VII.F amendment candidates banked

Writing-plans phase may surface ~5-15 V2.1 §VII.F amendment candidates (operator-pre-Codex review surfacing inconsistencies between brainstorm spec + plan structure + shipped code intent). Per Phase 12.5 #1 + #2 writing-plans precedent. Banked at §J of plan + return report §6.

### §2.13 Per-task projections

Test deltas + LOC projections per task per Phase 10 plan precedent. Total projection per spec §8.2: +590-1020 fast tests + 4 slow E2E + ~5500-10000 production LOC + ~7000-13000 test LOC.

---

## §3 OUT OF SCOPE (do not do)

- **Code drafting** — service modules, view-models, query implementations, Jinja templates, route handlers, repo functions, CLI command bodies. Plan is design-only at task-grain.
- **Migration SQL drafting** beyond the schema sketches at brainstorm spec §3. Plan transcribes the sketches into per-task migration content (NEW table CREATE statements with full DDL), but does NOT write the Python migration loader code.
- **Sub-bundle task decomposition into per-step pseudocode** — per-task acceptance criteria are in scope; per-step pseudocode is executing-plans implementer's territory.
- **Re-litigating §1 LOCKS + §1.3 OQ dispositions** — accepted as given; operator-confirmed.
- **Sell-side detector** (§1.4 L3; Phase 14).
- **ML re-ranker** (§1.4 L4; indefinitely deferred).
- **Drift monitoring side** (§1.4 L5; Phase 13.5).
- **Operator-elicited usability list** beyond Q4 (operator confirmed no additional items at orchestrator-pre-writing-plans 2026-05-18 PM).

---

## §4 Binding conventions

- **Branch:** `main` direct OR worktree (`phase13-writing-plans` per recent Phase 12.5 #1/#2/#3 worktree-isolation precedent). Single commit OR landing+fixes split per Phase 9/10/12 writing-plans precedent if Codex surfaces substantive issues.
- **Commit message:** `docs(phase13): Phase 13 charts + patterns + auto-fill + usability writing-plans output` (initial); optional `docs(phase13): writing-plans — Codex R1-R<N> fixes` (post-review).
- **NO Claude co-author footer.** CLAUDE.md binding convention. Cumulative streak ~186+ commits ZERO drift across Phase 11/12/12.5/13 brainstorm chains (verified at every merge). DO NOT regress. Explicit citation in commit messages required.
- **No `--no-verify`. No amending.**
- **Plan format:** mirror `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (2008 lines; 5 sub-bundles; 33 tasks; closest scope-precedent). Section-numbered; locked decisions called out explicitly with rationale; per-task acceptance criteria; invariants banked at §F.
- **Plan line target:** ~2000-3000 lines (per Phase 10 precedent: 2008 lines for 5 sub-bundles; Phase 13 has 11 sub-bundles; linear scaling → ~3000-4000, but per-sub-bundle scope may be tighter; pragmatic target ~2500-3500).
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Budget **3-5 substantive rounds** (brainstorm absorbed substantial design surface; writing-plans focuses on per-task decomposition; expected convergent shape).
- **Pre-Codex orchestrator-side review** per NEW C.C lesson #6 BINDING — before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with §1 LOCKS + §2 scope + §5 watch items as anchors. Validated 9x cumulatively across Phase 12/12.5/13 brainstorms + writing-plans.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **§1 11 LOCKS + §1.3 OQ-confirmed dispositions integrity.** Plan respects all 11 LOCKS + 12 OQ dispositions verbatim. If plan recommendation appears to weaken these, flag for orchestrator — do NOT relax in plan.
2. **OQ-12 Option E migration landing timing accuracy.** T2.SB1 task 1 = migration-only commit; T3.SB1 worktree branches off T2.SB1's first-commit SHA explicitly (NOT off main). Merge ordering T2.SB1 first then T3.SB1. Encode in T3.SB1 dispatch brief prerequisites.
3. **`DETECTOR_PATTERN_CLASSES` enum + cross-column CHECK invariants integrity** (per spec §3.0 + §3.1). All 4 referencing columns (`pattern_exemplars.proposed_pattern_class` + `pattern_exemplars.final_pattern_class` + `pattern_evaluations.pattern_class` + `chart_renders.pattern_class`) reference the same enum; 5 numbered cross-column CHECK invariants schema-defended.
4. **Schema-CHECK + Python-constant + dataclass-validator paired atomic landing** (forward-binding lesson #1; Phase 12 C.A T-A.2 LOCK). For EVERY CHECK enum widening + cross-column CHECK invariant in v20: schema + Python constant + dataclass validator MUST land in same task/commit.
5. **`construct_authenticated_client` 4-arg signature discipline** (forward-binding lesson #10). T3.SB1 + T3.SB2 entry/exit auto-fill paths use the discipline; plan §G tasks cite explicitly.
6. **HTMX gotcha trinity preservation** (forward-binding lesson #11). T2.SB6 review form + T3.SB1/SB2/SB3 forms + T4.SB Q4 toggle button: HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted disciplines.
7. **Base-layout VM banner pin** (forward-binding lesson #12; Phase 10 T-E.3 + Phase 12.5 #2 13-VM retrofit). New VMs introduced in Theme 1 + Theme 2 + Theme 3 + Theme 4 populate `unresolved_material_discrepancies_count` + `banner_resolve_link`.
8. **5 cross-column CHECK invariants on `pattern_exemplars`** schema-defended (per spec §3.1; relabel-vs-non-relabel coherence + source-vs-decision matrix + parent_exemplar_id linkage + geometric_score_json nullability + labeler_evidence_json source coherence).
9. **Q4 schema folds into v20** per L6 single-migration LOCK (per spec §7.2). Plan §B + §F encode this LOCK explicitly.
10. **OQ-5 phased Codex SELECTIVE policy** — T2.SB1 random 15% only; T2.SB3+/SB4 adds high-stakes disagreement clause + retroactive evaluation. Plan §G tasks for T2.SB1 + T2.SB3 + T2.SB4 enumerate the phase-specific behavior.
11. **OQ-12 Option E migration mechanics — T2.SB1 task 1 is migration-only commit** (NOT bundled with subsequent T2.SB1 tasks). Plan §G T2.SB1 task ordering enforces.
12. **Mid-dispatch operator-paired pause for T2.SB1 exemplar bootstrap** (per OQ-6 Sub-bundle 1 cassette session precedent). Plan §G T2.SB1 task list includes the pause point as a distinct task.
13. **Theme 1 + Theme 2 coupling at T2.SB6** — annotated chart renderer IS the Theme 1 deliverable AND the Theme 2 §9.2 evidence-display deliverable. Plan §G T2.SB6 tasks address shared rendering path explicitly.
14. **Session-anchor read/write mismatch family** (forward-binding lesson #15). Any new session-keyed surface (chart cache staleness; auto-fill data-source freshness; Q4 flag persistence) — plan §G tasks cross-reference the writer's session-anchor function as binding contract.
15. **Reject-caller-held-tx contract on new transactional services** (forward-binding lessons #5 + #6). Plan §G Q4 close-tracking flag service (auto-clear-on-position-open transactional discipline) follows the discipline.
16. **Cassette URI/path + body sanitization filter installation** (forward-binding lesson #9). T2.SB1 dev-time labeling infra OR T3.SB1/SB2 Schwab consumer paths may need new cassette infrastructure; plan §G tasks specify the sanitization filter setup.
17. **Plan-author schema additions escalation rule** (Phase 12 C.A R3-surfaced lesson family). If writing-plans surfaces schema additions beyond what brainstorm spec §3 specifies, STOP + escalate to orchestrator + amend spec (NOT silent absorption).
18. **CLAUDE.md size-check trigger discipline** (per orchestrator-context.md §"Size-check trigger at housekeeping-commit time"). Plan §K test + LOC projections inform when the post-merge housekeeping commit may trip the line-3 cap; pre-empt via compact-summary style at planning time.

---

## §6 Done criteria

1. Plan at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` covering §2.1-§2.13.
2. Writing-plans went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Plan section structure mirrors `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` format (closest scope-precedent).
4. 11-sub-bundle decomposition refined at §G with per-task acceptance criteria (~30-50 tasks total).
5. v20 migration landing timing per OQ-12 Option E encoded explicitly at §B + §G T-A.1.1 (migration-only first commit on T2.SB1; T3.SB1 branches off T2.SB1's first-commit SHA).
6. 12 OQ dispositions cross-referenced at §A (general architectural inheritance) + §G (per-task application).
7. 5 cross-column CHECK invariants on `pattern_exemplars` schema-defended + Python-constant + dataclass-validator paired (per Phase 12 C.A T-A.2 LOCK).
8. `DETECTOR_PATTERN_CLASSES` enum LOCK encoded at §A + §G T-A.1.1 (cross-table CHECK references for all 4 columns).
9. T2.SB1 mid-dispatch operator-paired pause point encoded as distinct task at §G T2.SB1 task list.
10. T4.SB ships Q4 close-tracking flag only (per §7.1 LOCK; no additional usability items confirmed empty at orchestrator-pre-writing-plans 2026-05-18 PM).
11. Forward-binding lessons inherited at §L (cite Phase 10 + Phase 11 + Phase 12 + Phase 12.5 + post-Phase-12 lessons by number).
12. Cross-bundle pin discipline encoded at §H (T1.SB0 + T2.SB1 + T3.SB1 + T2.SB3 + T2.SB5 + T3.SB2 + T3.SB3 + T2.SB6).
13. Single commit OR landing+fixes split per Phase 12.5 #1/#2/#3 writing-plans precedent.
14. Return report at `docs/phase13-writing-plans-return-report.md` per §7.

---

## §7 Return report format

```
## Return report — Phase 13 writing-plans

### Plan location
`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` ({line count} lines)
Commits on {branch}:
- {sha} `docs(phase13): Phase 13 charts + patterns + auto-fill + usability writing-plans output` (initial)
- (optional) {sha} `docs(phase13): writing-plans — Codex R1-R<N> fixes` (post-review)

### Codex review history
- Pre-Codex (orchestrator-side review): {N findings absorbed; C.C lesson #6 BINDING validated Xth cumulative time}
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage plan decisions
1. ...
2. ...
3. ...

### Per-sub-bundle task counts + projections
| Sub-bundle | Task count | Test delta projection | LOC projection (prod + test) |
|---|---|---|---|
| T1.SB0 | N | +X-Y fast | +Z prod / +W test |
| T2.SB1 | N | +X-Y fast | +Z prod / +W test |
| ... | ... | ... | ... |
| T4.SB | N | +X-Y fast | +Z prod / +W test |
| **Cumulative** | **N total** | **+X-Y fast + 4 slow** | **+Z prod / +W test** |

### Cross-bundle dependencies confirmed
[T1.SB0 → T2.SB1 ∥ T3.SB1 (concurrent off T2.SB1's first-commit SHA per OQ-12) → ...]

### 12 OQ dispositions encoded verbatim
[Per OQ: where in plan; confirmation that disposition is BINDING-encoded at §X]

### V2.1 §VII.F amendment candidates banked
[Per amendment: §X reference; spec divergence rationale]

### Forward-binding lessons for executing-plans dispatches
[Per lesson: prior arc + load-bearing for which Sub-bundles]

### Capture-needs for executing-plans dispatches
[Per Sub-bundle: dispatch-brief considerations; operator-paired pause points; cross-bundle pin discipline]

### Outstanding capture-needs that DEFER to Phase 13.5 / Phase 14
[Per item: target phase; rationale]
```

---

## §8 If you get stuck

- If §1 LOCKS + §1.3 OQ dispositions conflict with Codex finding, §1 + §1.3 win; flag as open question.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly + return report.
- If plan exceeds ~3500 lines, re-scope (Phase 13 is large but not infinite; per-sub-bundle scope should be ~150-300 lines).
- DO NOT propose new schema beyond brainstorm spec §3. If you find yourself drafting `CREATE TABLE foo_new` that's not in spec §3, STOP + escalate to orchestrator + amend spec (lesson #17 BINDING).
- If you encounter a Phase 7/8/9/10/11/12/12.5 lesson that conflicts with a Phase 13 plan proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a design constraint.
- If you find yourself proposing sell-side patterns OR ML re-ranker OR drift monitoring OR multi-cohort architectural deepening, STOP — §1.4 LOCK violated.
- If you find yourself proposing run-time AI inferencing (Claude API at pipeline run-time), STOP — L1 LOCK violated.
- If the v20 migration mechanics need adjustment beyond Option E's "T2.SB1 task 1 + T3.SB1 first-commit-SHA branch base" approach, STOP — OQ-12 LOCK violated.
- If Theme 4 scope needs to expand beyond Q4 close-tracking flag (e.g., operator-elicited usability items discovered mid-writing-plans), STOP — §7.1 LOCK violated.
- If you find yourself re-litigating any of the 12 OQ dispositions, STOP — operator confirmed all 12 at 2026-05-18 PM triage.

---

*End of brief. Phase 13 writing-plans dispatch — 11 sub-bundles + ~30-50 tasks + v20 single migration via OQ-12 Option E + 12 OQ dispositions BINDING-encoded. Plan output target: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`. Expected 3-5 Codex rounds + convergent shape. ZERO ACCEPT-WITH-RATIONALE preferred. Pre-Codex orchestrator-side review BINDING per C.C lesson #6 (validated 9x cumulatively).*
