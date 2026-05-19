# Phase 13 — Charts + Pattern Recognition + Auto-fill + Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Phase 13 is large (11 sub-bundles; per-sub-bundle executing-plans dispatches are the operator-paced unit; this plan is the per-task substrate consumed at each dispatch).

**Goal:** Implement the Phase 13 4-theme architectural arc per spec `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` (1483 lines; 7 Codex rounds; ZERO ACCEPT-WITH-RATIONALE) — Theme 1 chart rendering deepening + Theme 2 pattern recognition deepening (HEADLINE) + Theme 3 auto-fill across entries/exits/reviews + Theme 4 usability triage with Q4 close-tracking flag fold-in — across 11 sub-bundles landing schema v19 → v20 single migration via OQ-12 Option E (T2.SB1 task 1 = migration-only commit; T3.SB1 worktree branches off T2.SB1's first-commit SHA).

**Architecture:** Three new top-level modules — `swing/patterns/` (foundation primitives + 5 detector modules + template matching + composite scoring + closed-loop helpers; mirrors `swing/metrics/` placement precedent), `swing/web/view_models/patterns/` (Theme 2 + Theme 1 annotated VMs), `swing/web/routes/patterns.py` (closed-loop review + queue + label-management surfaces). Theme 1 SVG-inline chart rendering via `swing/web/charts.py` + new `chart_renders` cache table. Theme 3 reuses Phase 11/12 Schwab integration (`construct_authenticated_client` 4-arg + `resolve_credentials_env_or_prompt(allow_prompt=False)` + `apply_overrides(cfg)`). Theme 4 Q4 watchlist-row badge + `swing/trades/watchlist_close_track.py` service with reject-caller-held-tx contract. v20 single migration introduces 3 NEW tables (`pattern_exemplars` + `pattern_evaluations` + `chart_renders` + `watchlist_close_track_flags` + `watchlist_close_track_flag_events` — 5 tables total) + 6 column additions (`fills.fill_origin` + `fills.schwab_source_value_json` + `fills.operator_corrected_value_json` + `fills.auto_fill_audit_at` + `review_log.auto_populated_field_keys_json` + widening `schwab_api_calls.surface` CHECK).

**Tech Stack:** Python 3.11+ / FastAPI / Starlette 1.0 / Jinja2 / HTMX 2.x / SQLite 3 (schema v20) / pytest / ruff / matplotlib SVG-inline (Phase 10 §A.10 LOCK precedent inherited; NO mathtext) / pytest-benchmark (T2.SB5 DTW gate) / NumPy + pandas (foundation primitives) / Claude Code subagent dispatch (`Agent(subagent_type='pattern-labeler', ...)`) for dev-time labeling at T2.SB1 / Codex MCP for selective 2nd-review per L9 + OQ-5. NO scipy / NO scikit-learn / NO image-CV / NO ML re-ranker (per §1.4 LOCK).

---

## §0 Top-matter

### §0.1 Spec reference + brainstorm dispatch lineage

- **Brainstorm spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` (1483 lines; 7 Codex rounds R1-R7; final verdict NO_NEW_CRITICAL_MAJOR with convergent non-strictly-monotonic Major taper; ZERO ACCEPT-WITH-RATIONALE across all 32 Major + 14 Minor findings). PRIMARY SUBSTRATE — this plan references spec §X.Y throughout; do NOT re-state substrate.
- **Brainstorm dispatch brief**: `docs/phase13-brainstorm-dispatch-brief.md` (368 + Q4 amendment lines).
- **Writing-plans dispatch brief**: `docs/phase13-writing-plans-dispatch-brief.md` (consumed by THIS plan).
- **Scope-brainstorm**: `docs/phase13-scope-brainstorm.md` §0.5 (operator-locked 2026-05-17; 4 themes / 11 sub-bundles / 11 design locks). §0.5.2 11-sub-bundle decomposition is binding.
- **v2 brief substrate**: `reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md` (901 lines; operator-authored 2026-05-08; AI-ingestion-ready). Theme 2 PRIMARY substrate; absorbed into spec §2.
- **Phase 10 precedent**: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (2008 lines; 5 sub-bundles; 33 tasks; format mirror).
- **Post-Phase-12 Sub-bundle 1 precedent**: `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` (1215 lines; cassette-session + operator-paired pause precedent for OQ-6 inheritance).
- **Phase 12.5 #1/#2/#3 precedents**: 1230 + 1082 + 1101 lines respectively; convergent-shape worktree-isolation + locks-and-invariants encoding patterns.

### §0.2 12 OQ-confirmed dispositions (verbatim from operator-pre-writing-plans triage 2026-05-18 PM)

All 12 OQs confirmed at brainstorm-recommended dispositions per `docs/phase13-writing-plans-dispatch-brief.md` §1.3:

| OQ | Topic | Confirmed disposition (BINDING) | Plan locus |
|---|---|---|---|
| OQ-1 | Sub-bundle count drift | 11 sub-bundles per scope-brainstorm §0.5.2 LOCK; T1.SB0 first | §G dispatch sequence + §A.1 |
| OQ-2 | Chart rendering tech + cache | V1: matplotlib SVG inline + NEW `chart_renders` cache table | §C + §B.4 + §G T1.SB0/T2.SB6 |
| OQ-3 | `pattern_class` enum + table location | Option (b) new `pattern_evaluations` table; 5 V1 values; no sell-side reservation | §B.3 + §D.1 + §G T2.SB1 task 1 |
| OQ-4 | Template matching distance | V1: DTW with Sakoe-Chiba band (window=0.1 × series_length); 120s benchmark gate; SBD V2 fallback | §D.5 + §G T2.SB5 |
| OQ-5 | Codex SELECTIVE policy | Phased 15% random at T2.SB1; +high-stakes disagreement at T2.SB3+/SB4; retroactive evaluation | §D.6 + §G T2.SB1 + T2.SB3 + T2.SB4 |
| OQ-6 | Exemplar bootstrap workflow | Mirror Sub-bundle 1 cassette session precedent; operator-paired mid-dispatch pause | §G T2.SB1 task 7 |
| OQ-7 | `fill_origin` enum + backfill | V1 5-value enum (`operator_typed`/`schwab_auto`/`schwab_auto_then_operator_corrected`/`tos_import`/`imported_legacy` per spec §3.4 + §6.4); simple backfill to `operator_typed` for all existing rows (faithful to journal-typed-from-memory pre-Phase-13 state) | §B.5 + §E.1 + §G T2.SB1 task 1 |

*Pre-Codex review absorption (C.C lesson #6 10th cumulative validation, 2026-05-18 PM)*: dispatch brief §1.3 OQ-7 table-cell paraphrase listed alternative enum values (`migration_backfill`/`import_csv`) + backfill target. Spec §3.4 + §6.4 (which the operator-pre-writing-plans triage at 2026-05-18 PM marked BINDING-confirmed via the "all 12 OQs confirmed at brainstorm-recommended dispositions" clause) carries the authoritative values reflected here. The spec values are semantically correct: existing rows are journal-typed-from-memory entries, so `'operator_typed'` is the faithful backfill (NOT `'migration_backfill'` which would mislabel the operator's authoring intent). Plan reconciles spec >> brief in case of drift. Brief §1.3 table-cell amendment recommended at integration triage.
| OQ-8 | Review auto-fill MFE/MAE source | OhlcvCache (post-T1.SB0); yfinance V2-fallback only | §E.3 + §G T3.SB3 |
| OQ-9 | Drift logging shape | V1: JSON column `pattern_evaluations.feature_distribution_log_json`; dedicated table V2 only if Phase 13.5 demands | §B.3 + §D.7 + §G T2.SB3 + T2.SB4 |
| OQ-10 | T2.SB6 route location | BOTH NEW `/patterns/{candidate_id}/review` AND NEW `/metrics/pattern-outcomes` 9th metric tile | §D.8 + §G T2.SB6 |
| OQ-11 | T2.SB1 subagent location | `.claude/agents/pattern-labeler.md` (Claude Code project-local) | §G T2.SB1 task 5 |
| OQ-12 | v20 migration landing timing | Option E (v20 lands as T2.SB1 task 1; T3.SB1 branches off T2.SB1's first-commit SHA; concurrent on bulk; merge order T2.SB1 first) | §B + §G T2.SB1 + T3.SB1 |

### §0.3 11 operator-locked binding decisions L1-L11 (inherited verbatim from spec §1)

L1 — Algorithm posture: rule-based geometric PRIMARY; template matching SECONDARY; NO run-time AI inferencing (Claude API in pipeline runtime FORBIDDEN; dev-time subagent dispatch for labeling per v2 brief §8.2 IS allowed).
L2 — V1 pattern set: 5 buy-side patterns (`vcp` + `flat_base` + `cup_with_handle` + `high_tight_flag` + `double_bottom_w`).
L3 — Sell-side detector module: BANKED to Phase 14.
L4 — ML re-ranker: DEFERRED indefinitely.
L5 — Drift detection monitoring side: SPLIT to Phase 13.5. Phase 13 BAKES IN the LOGGING side ONLY.
L6 — Schema appetite: v19 → v20 single migration; v21+ possible per theme. **Q4 schema FOLDS INTO v20** per spec §7.2 LOCK.
L7 — Strategic posture: 100% operational.
L8 — Single-strategy focus: SEPA + DST.
L9 — Codex as second reviewer: SELECTIVE (NOT blanket) per OQ-5.
L10 — Theme 3 absorbs original Phase 12.5 #2 fill auto-population at trade-entry.
L11 — Theme 4 elicitation absorbed Q4 close-tracking flag (operator-pre-writing-plans 2026-05-18 PM: no additional usability items; T4.SB ships Q4 D-Q4.1..D-Q4.7 baseline lock only).

### §0.4 Inherited DROP rules (do not do)

- No magnitude-based threshold (tolerance bands per §10.6 LOCK only).
- No retroactive audit-row rewriting.
- No re-litigating §1 + OQ dispositions.
- No run-time AI inferencing.
- No sell-side detector.
- No ML re-ranker.
- No drift monitoring/dashboard side.
- No multi-cohort architectural deepening.
- No image-based CV / sequence transformers / harmonic-candlestick-intraday / fixed-window pattern detection.

---

## §A — General architectural decisions (inherited from spec §1 + OQ dispositions)

### §A.1 Sub-bundle decomposition + dispatch sequence (§G LOCK)

11 sub-bundles per scope-brainstorm §0.5.2 LOCK (OQ-1 BINDING):

```
T1.SB0 (OhlcvCache -> _step_charts wiring; prerequisite)
    -> T2.SB1 (dev-time labeling infra; migration task 1)
       || T3.SB1 (entry auto-fill; CONCURRENT off T2.SB1's first-commit SHA per OQ-12 Option E)
          -> [operator-paired exemplar bootstrap pause per OQ-6]
    -> T2.SB2 (foundation primitives)
    -> T2.SB3 (detectors batch 1: VCP + flat base + CWH)
    -> T3.SB2 (exit auto-fill)
    -> T2.SB4 (detectors batch 2: HTF + DBW)
    -> T2.SB5 (template matching)
    -> T3.SB3 (review auto-fill)
    -> T2.SB6 (closed-loop surface + Theme 1 annotated charts)
    -> T4.SB (usability triage closer + Q4)
    -> Phase 13 CLOSED
```

One concurrent point: T2.SB1 ∥ T3.SB1 (independent codebase touch; OQ-12 Option E governs migration mechanics).

### §A.2 Module placement LOCK — `swing/patterns/` parallel to `swing/metrics/`

NEW top-level module:

```
swing/patterns/
  __init__.py              # public re-exports (CandidateWindow, Swing, VCPEvidence, ...)
  foundation.py            # T2.SB2 — smoothing + extrema + zigzag + variable-window generator + volume primitives
  vcp.py                   # T2.SB3 — VCP detector
  flat_base.py             # T2.SB3 — flat base detector
  cup_with_handle.py       # T2.SB3 — cup-with-handle detector
  high_tight_flag.py       # T2.SB4 — high-tight-flag detector
  double_bottom_w.py       # T2.SB4 — double-bottom-W detector
  composite.py             # T2.SB5 — composite scoring (geometric + template-match weighted sum)
  template_matching.py     # T2.SB5 — DTW with Sakoe-Chiba band; forward + reverse retrieval
  active_learning.py       # T2.SB6 — prioritization helper for /patterns/queue surface
  labeling.py              # T2.SB1 — dev-time subagent dispatch glue + selective Codex policy
  drift_logging.py         # T2.SB3 + T2.SB4 — feature distribution capture helper (per OQ-9)
```

NEW view-model sub-package:

```
swing/web/view_models/patterns/
  __init__.py
  review_form.py           # T2.SB6 — /patterns/{candidate_id}/review VM
  queue.py                 # T2.SB6 — /patterns/queue VM (active-learning prioritization)
  exemplars.py             # T2.SB1 — /patterns/exemplars VM (operator spot-check surface)
  outcomes_card.py         # T2.SB6 — /metrics/pattern-outcomes 9th metric tile VM
  annotated_chart.py       # T2.SB6 — Theme 1+Theme 2 shared annotated chart VM shape
```

NEW route module: `swing/web/routes/patterns.py` (group all `/patterns/*` routes); EXTEND `swing/web/routes/metrics.py` with `/metrics/pattern-outcomes`; EXTEND `swing/web/routes/watchlist.py` with `POST /watchlist/{ticker}/flag` + `POST /watchlist/{ticker}/unflag` (Theme 4 Q4).

NEW services:

```
swing/trades/watchlist_close_track.py    # T4.SB Q4 — set/clear flag service (reject-caller-held-tx)
```

NEW chart rendering surface: `swing/web/charts.py` (T1.SB0 + T2.SB6 — matplotlib SVG-inline renderer). Rationale: matplotlib coupling is isolated to ONE module; consumed by `chart_renders` cache writer + `swing/pipeline/runner.py:_step_charts`.

Per-file responsibility maps 1:1 onto spec §4 + §5 surface boundaries. Each file < 400 LOC + reviewable.

### §A.3 View-model placement LOCK

Per Phase 10 §A.18 base-layout VM banner pin (forward-binding lesson #12): every NEW VM extending `base.html.j2` MUST populate `unresolved_material_discrepancies_count` + `banner_resolve_link` (+ `recent_multi_leg_auto_correction_count` per Phase 12.5 #2 13-VM retrofit). Plan §C.2 + §D.8 + §E.6 + §F.3 enumerate per-VM coverage.

The `BaseLayoutVM` mixin (`swing/web/view_models/metrics/shared.py:28`) is the canonical inheritance target. All new Phase 13 VMs extend it directly OR via dataclass field re-declaration with safe defaults.

### §A.4 Route placement LOCK — `swing/web/routes/patterns.py` + metrics extension

5 NEW GET endpoints + 4 NEW POST endpoints in V1:

| Surface | Path | Method | Renders / mutates |
|---|---|---|---|
| Patterns review form | `GET /patterns/{candidate_id}/review` | GET | T2.SB6 — review form per v2 brief §9.2 8-item checklist + §9.3 6-decision enum |
| Patterns review submit | `POST /patterns/{candidate_id}/review` | POST | T2.SB6 — emits `pattern_exemplars` row with `label_source='closed_loop_review'` or `'organic_trade_history'` |
| Patterns queue | `GET /patterns/queue` | GET | T2.SB6 — active-learning prioritization per v2 brief §9.4 |
| Patterns exemplars | `GET /patterns/exemplars` | GET | T2.SB1 — operator spot-check surface (silver → gold promotion + final_decision adjustments) |
| Patterns exemplar action | `POST /patterns/exemplars/{id}/action` | POST | T2.SB1 — silver → gold promotion / rejected / relabeled / watch flips |
| Pattern outcomes metric tile | `GET /metrics/pattern-outcomes` | GET | T2.SB6 — 9th metric surface (composes with Phase 10 metrics architecture) |
| Watchlist flag toggle | `POST /watchlist/{ticker}/flag` | POST | T4.SB Q4 — set/clear close-tracking flag |
| Watchlist unflag | `POST /watchlist/{ticker}/unflag` | POST | T4.SB Q4 — explicit unflag (operator-cleared) |
| Dashboard weather chart refresh | `POST /dashboard/weather-chart/refresh` | POST | T2.SB6 / Theme 1 — manual regeneration bypassing cache |

ALL form-driven routes inherit the HTMX gotcha trinity (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted) — forward-binding lesson #11. Per-route discriminating tests enumerated at §G.

### §A.5 OhlcvCache wiring LOCK (T1.SB0)

Per OQ-8 + spec §4.1: T1.SB0 closes Phase 11 Sub-bundle C R1 M#5 V1 deferral by replacing the bare `fetcher.get(ticker, lookback_days=180, as_of_date=None)` at `swing/pipeline/runner.py:_step_charts` with an `OhlcvCache.get_or_fetch(...)` call. Theme 2 detectors at T2.SB2+ consume the same cache for daily + weekly bars; T3.SB3 review auto-fill MFE/MAE consumes for candle-data. yfinance is V2-fallback only.

Per-cache locking: `swing/web/ohlcv_cache.py:OhlcvCache` already has cache discipline (Phase 11 Sub-bundle C) — T1.SB0 verifies the cache survives `_step_charts`'s multi-ticker loop without contention; adds `threading.RLock` if discriminating test surfaces a race.

Shape reconciliation: chart renderers accept the `to_dataframe()` shape (capitalized columns + DatetimeIndex). Discriminating test (T-T1.SB0.3) asserts chart bytes match a known-good fixture rendered from both paths.

### §A.6 Codex SELECTIVE policy LOCK (OQ-5; phased rollout)

Per spec §5.9 step 4 + OQ-5 disposition:

**At T2.SB1** (rule detectors not yet shipped): **random 15% sampling ONLY** of `claude_silver` rows per pattern class. NO rule/silver disagreement clause (geometric_score is unavailable pre-detector). Codex MCP fires on the random-sample subset; updates the SAME `pattern_exemplars` row with `codex_reviewed=1` + `codex_agreement=<bool>`. Disagreement INSERTs a SECOND row with `label_source='codex_silver'` + `parent_exemplar_id` pointing to the Claude parent.

**At T2.SB3+/SB4** (rule detectors shipped): random 15% CONTINUES + high-stakes individual labels — Claude silver confidence == 'high' AND rule-tier `geometric_score < 0.5` (disagreement A direction); OR Claude silver confidence == 'low' AND rule-tier `geometric_score >= 0.8` (disagreement B direction). Retroactive evaluation against the T2.SB1 corpus when T2.SB3+/SB4 evaluators have access to recompute `geometric_score`.

Codex MCP integration: invoke via `mcp__plugin_copowers_codex__codex` per copowers convention. Cassette infrastructure per §A.10.

### §A.7 Pattern labeler subagent location LOCK (OQ-11)

`.claude/agents/pattern-labeler.md` (Claude Code project-local subagent per Claude Code standard convention). Consumed via `Agent(subagent_type='pattern-labeler', ...)` from T2.SB1 implementation code at `swing/patterns/labeling.py`. Definition file is COMMITTED to repo (not gitignored) so labeling sessions are reproducible.

### §A.8 ASCII-only invariant LOCK

Per Windows cp1252 stdout gotcha (CLAUDE.md): all Theme 1 + Theme 2 + Theme 3 + Theme 4 CLI surfaces ASCII-only. Pre-empt in any new `print()` / `click.echo()` / matplotlib chart text. Defense-in-depth: `swing/cli.py` already reconfigures `sys.stdout` + `sys.stderr` to UTF-8 with `errors='replace'` at CLI entry. Discriminating tests use subprocess + stderr-encoding validation per Phase 12 C.D gate-fix #3 precedent.

### §A.9 Matplotlib mathtext LOCK

Per CLAUDE.md "Matplotlib mathtext gotcha" + Phase 10 §A.10 inheritance: ZERO `$` / `^` / `_` / unbalanced `\` in any chart title / axis label / annotation text. `fig.suptitle(..., parse_math=False)` as defense-in-depth where avoiding metacharacters is infeasible. Operator-witnessed browser verification gate BINDING for every new chart rendering surface (Theme 1 + Theme 2 annotated).

### §A.10 Cassette infrastructure LOCK (T2.SB1 + T3.SB1 + T3.SB2)

Per post-Phase-12 forward-binding lesson #2 + #3 (`docs/orchestrator-context.md`):

- T2.SB1 labeler cassettes: NEW `tests/integrations/cassettes/pattern_labeler/` directory. `before_record_request` (URI/path sanitization) + `before_record_response` (body sanitization) filters BOTH installed in the test fixture. Sanitize: Claude API auth headers, dispatch payload PII (none expected; sentinel test asserts).
- T2.SB1 Codex MCP cassettes: NEW `tests/integrations/cassettes/codex_mcp_pattern_review/` directory. Sanitize: model invocation parameters + token usage telemetry.
- T3.SB1 + T3.SB2 Schwab Trader API consumption cassettes: REUSE `tests/integrations/cassettes/schwab/` directory established at post-Phase-12 Sub-bundle 1. New per-test cassette files for `trade_entry` + `trade_exit` surface paths.
- NEW standalone recording scripts: `scripts/record_pattern_labeler_cassettes.py` + `scripts/record_codex_mcp_pattern_review_cassettes.py` per post-Phase-12 lesson #3 (standalone over `@pytest.mark.vcr(record_mode='new_episodes')` for predictable corpus).

### §A.11 Schwab integration discipline LOCK (T3.SB1 + T3.SB2)

Per forward-binding lesson #10 + #11 (spec §11.5 + §11.10):

- At every form-render entry point (`GET /trades/entry/form`, `GET /trades/{id}/exit/form`): call `cfg = apply_overrides(base_cfg)` FIRST to consume cfg-cascade.
- Resolve credentials: `client_id, client_secret = resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` — the `allow_prompt=False` form is REQUIRED to prevent stdin-blocking inside an HTTP handler.
- Construct client: `construct_authenticated_client(cfg, environment, client_id, client_secret)` (4-arg signature per post-Phase-12 Sub-bundle 1).
- Sandbox short-circuit: if `cfg.integrations.schwab.environment == 'sandbox'`, auto-fill SHORT-CIRCUITS (form renders empty auto-fill fields + `fill_origin='operator_typed'`). Audit row STILL written; domain rows NOT.
- DEGRADED-state handling: if Schwab integration banner predicate fires, auto-fill short-circuits + advisory banner.
- Empty-state handling: if Schwab API returns no matching fills within 7-day lookback, form renders empty + advisory text per spec §6.1.

### §A.12 Transactional discipline LOCK (T4.SB Q4 service + any new service)

Per forward-binding lessons #4 + #5 + #6 (Phase 8 R3→R4 + Phase 12 C.C lesson #2 + #3):

- Service-level transactional functions REJECT caller-held transactions (caller MUST NOT hold open tx).
- Service ALWAYS owns `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`.
- Environment-specific short-circuit (sandbox / dry-run) lives in INNER function (NOT outer).
- SELECT-first idempotency PRECEDES payload validation (Phase 12 C.C lesson #3).
- Counter recompute post-mutation via `SELECT COUNT(*)` (Phase 12 C.C lesson #4).
- Audit-row append-only (per `reconciliation_corrections` Phase 12 C.A precedent — `watchlist_close_track_flag_events` gets new `event_type='clear'` row; parent `watchlist_close_track_flags` row gets `cleared_at` + `cleared_reason` UPDATE not DELETE).

### §A.13 Session-anchor read/write predicate alignment LOCK

Per forward-binding lesson #10 (CLAUDE.md "Session-anchor read/write mismatch silently invisibles UI display"):

| Surface | Writer anchor | Reader anchor | Reason |
|---|---|---|---|
| `chart_renders.data_asof_date` | `last_completed_session(now())` (backward-looking) | SAME `last_completed_session(now())` (backward-looking) | Charts reflect "most recent completed session"; weekend/holiday/evening invariance |
| `pattern_evaluations.window_*_date` | Bound to `pipeline_run.started_ts.date()` derivatives | SAME — bound to the pipeline_run row | Per-run anchored; no drift |
| `watchlist_close_track_flags.flagged_at` | server-stamped ISO timestamp | SAME timestamp comparison | Direct timestamp; no session predicate |
| OhlcvCache staleness | `last_completed_session(now())` | SAME | Consistent with Phase 11 Sub-bundle C |
| Theme 3 review auto-fill MFE/MAE date range | open-trade entry date through `last_completed_session(now())` | SAME | Per Phase 8 daily_management_records precedent |

Discriminating round-trip test pattern (per Phase 8 `cfacbc5` precedent CLAUDE.md gotcha): write a row, immediately read via the UI/read predicate, assert visibility flips correctly. Land for each new session-keyed surface in §G.

### §A.14 Schema-CHECK + Python-constant + dataclass-validator paired discipline (forward-binding lesson #1)

Per Phase 12 C.A T-A.2 LOCK + spec §3.5 audit roster: every CHECK enum + cross-column CHECK invariant in v20 MUST land in the SAME task as its Python-side mirror constants + dataclass `__post_init__` validators. v20 atomic-landing roster per spec §3.5:

| CHECK construct | Python constant | Dataclass validator |
|---|---|---|
| `DETECTOR_PATTERN_CLASSES` (5 values) referenced by 4 columns per §3.0 | `swing/patterns/__init__.py:DETECTOR_PATTERN_CLASSES` tuple | `PatternExemplar` / `PatternEvaluation` / `ChartRender` `__post_init__` |
| `pattern_exemplars.label_source` (7 values) | `swing/patterns/__init__.py:_LABEL_SOURCE_VALUES` | `PatternExemplar.__post_init__` |
| `pattern_exemplars.final_decision` (5 values) | `swing/patterns/__init__.py:_FINAL_DECISION_VALUES` | `PatternExemplar.__post_init__` |
| 5 numbered cross-column CHECK invariants on `pattern_exemplars` (per spec §3.1 invariants #1-#5) | mirror predicates in `PatternExemplar.__post_init__` | same |
| `fills.fill_origin` (5 values) | `swing/data/models.py:_FILL_ORIGIN_VALUES` | `Fill.__post_init__` |
| `schwab_api_calls.surface` widening (+`trade_entry`, +`trade_exit`) | `swing/integrations/schwab/audit_service.py:_SCHWAB_API_SURFACE_VALUES` | service-call entry validator |
| `chart_renders.surface` (5 values) | `swing/web/charts.py:_CHART_SURFACE_VALUES` | `ChartRender.__post_init__` |
| `chart_renders` cross-column CHECK per §3.2 | mirror predicate in `ChartRender.__post_init__` | same |
| `watchlist_close_track_flags.flagged_by_surface` (2 values) | `swing/trades/watchlist_close_track.py:_FLAG_SURFACE_VALUES` | `WatchlistCloseTrackFlag.__post_init__` |
| `watchlist_close_track_flags.cleared_reason` (2 values when non-NULL) | `swing/trades/watchlist_close_track.py:_FLAG_CLEARED_REASON_VALUES` | same |
| `watchlist_close_track_flag_events.event_type` (2 values) | `swing/trades/watchlist_close_track.py:_FLAG_EVENT_TYPE_VALUES` | `WatchlistCloseTrackFlagEvent.__post_init__` |
| `watchlist_close_track_flag_events.surface` (2 values) | SAME `_FLAG_SURFACE_VALUES` | same |

All land in T2.SB1 task 1 (migration-only commit per OQ-12 Option E). NO migration-then-Python-then-validator split across multiple commits; the discipline IS atomic.

### §A.15 No `INSERT OR REPLACE` on audit-trail tables (forward-binding lesson #3)

`pattern_exemplars` + `pattern_evaluations` + `chart_renders` + `watchlist_close_track_flags` + `watchlist_close_track_flag_events` all carry audit-trail intent. Use SELECT-then-UPDATE-or-INSERT pattern per CLAUDE.md gotcha. The `chart_renders` cache invalidation pattern (re-render replacing stale cached rows) MUST use DELETE-then-INSERT for atomic refresh, NOT `INSERT OR REPLACE`. Discriminating test: re-render scenario asserts old `id` is gone + new `id` is fresh autoincrement.

### §A.16 Empty-cohort + zero-trade rendering (forward-binding family from Phase 10 §A.16)

Every new view-model + every new metric surface MUST render gracefully at n=0 / n=1 / n=2:

- `/patterns/queue` at zero candidates → renders "No pattern candidates pending review" placeholder.
- `/metrics/pattern-outcomes` at zero pattern_evaluations → renders "Insufficient data; n=0" per Phase 10 honesty.py `SuppressedMetric` shape.
- `/patterns/exemplars` at zero exemplars → renders "Run `swing patterns label-exemplars` to bootstrap" advisory.
- Watchlist at zero flagged tickers → no badge column rendered (no layout shift).

### §A.17 Operator-witnessed verification gates per surface (per Phase 10 §I.15)

Each new surface, on first deploy, requires operator-witnessed browser verification. TestClient passes are necessary but not sufficient. Per-bundle gate-surface count enumerated at §G; all bundles ≤8 surfaces fits one operator session.

### §A.18 Discrepancies helper hand-off LOCK

`swing/metrics/discrepancies.py:count_unresolved_material(conn)` (shipped Phase 10 T-A.7.1) is the canonical helper for `unresolved_material_discrepancies_count` field population. Every new VM extending `BaseLayoutVM` calls this helper at build time. Discriminating test per VM: assert constructor calls helper + populates field.

### §A.19 Pre-Codex orchestrator-side review BINDING (per dispatch brief §4 BINDING)

Per C.C lesson #6 + 9x cumulative validation across Phase 12/12.5/13 brainstorms + writing-plans:

Before invoking `copowers:adversarial-critic` for the FINAL round (NO_NEW_CRITICAL_MAJOR verdict), dispatch a focused reviewer subagent with §0.3 LOCKS (L1-L11) + §0.2 12 OQ-confirmed dispositions + §I 18 watch items as anchors. Ask for deviation list ≤300 words. Absorb findings; cite as C.C lesson #6 10th cumulative validation in return report.

### §A.20 Test fixture USERPROFILE+HOME monkeypatch (forward-binding family)

Per CLAUDE.md "Tests that exercise `swing/config_user.py:write_user_overrides` MUST monkeypatch BOTH USERPROFILE AND HOME env vars". By-construction satisfied at most Phase 13 surfaces (no `write_user_overrides` paths). Lock applies to any T3.SB1/SB2 test fixture that touches user-config.toml (Schwab credential cascade resolution).

---

## §B — v20 migration mechanics (OQ-12 Option E)

### §B.1 Migration file landing LOCK

- **Migration file**: `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql` (single file per L6 LOCK).
- **Schema version bump**: `swing/data/db.py:EXPECTED_SCHEMA_VERSION` 19 → 20 (single-line edit; lands atomically with migration file).
- **Backup-gate**: `pre_version == 19` strict equality (per forward-binding lesson #2 + CLAUDE.md "Migration runner backup-gate equality form: strict equality, NOT `<=`").
- **Migration mechanics**: explicit `BEGIN` / `executescript` / `COMMIT` / `ROLLBACK` per `swing/data/db.py:_apply_migration` canonical implementation (`foreign_keys=OFF` discipline at runner level; per Phase 12 C.A T-A.2 lock).
- **Landing commit**: T2.SB1 task 1 (FIRST commit on T2.SB1 worktree branch). Migration-only commit; NO Python code changes, NO test additions in same commit.

### §B.2 OQ-12 Option E coordination

Per OQ-12 BINDING:

1. T2.SB1 worktree branches from main HEAD at dispatch time.
2. T2.SB1 task 1 commits the migration file + `EXPECTED_SCHEMA_VERSION` bump + Python-side constants + dataclass validators (all atomic per §A.14). Commit message: `feat(phase13): v20 migration — phase13 charts patterns autofill usability schema landing (T-A.1.1)`. Record first-commit SHA.
3. T3.SB1 worktree branches FROM T2.SB1's first-commit SHA (NOT from main HEAD). Dispatch brief for T3.SB1 enumerates the SHA explicitly.
4. T3.SB1 task 1 verifies `EXPECTED_SCHEMA_VERSION == 20` at startup (no-op assert if migration already applied via T2.SB1 task 1).
5. Concurrent dispatch of T2.SB1 (remaining tasks) + T3.SB1 (all tasks) proceeds in parallel worktrees.
6. Merge ordering: T2.SB1 merges first (closes v20 atomic landing); T3.SB1 merges second (consumer-side widening already lands consistent schema).
7. Cross-bundle pin: T-A.1.1 plants `test_schema_version_v20_invariant` cross-bundle pin that un-skips at T3.SB1 merge.

### §B.3 v20 schema deltas (verbatim from spec §3)

**NEW table `pattern_exemplars`** per spec §3.1 — 17-20 columns with 5 numbered cross-column CHECK invariants. Schema sketch verbatim from spec §3.1 (DO NOT re-author).

**NEW table `chart_renders`** per spec §3.2 — 9 columns + 3 partial unique indexes (`idx_chart_renders_run_bound` + `idx_chart_renders_position_detail` + `idx_chart_renders_theme2_annotated`) + 1 cross-column CHECK. Schema sketch verbatim from spec §3.2.

**NEW table `pattern_evaluations`** per spec §3.3 — 14-16 columns + 1 unique index `(pipeline_run_id, ticker, pattern_class)`.

**NEW table `watchlist_close_track_flags`** per spec §7.2 — 7 columns + 1 partial unique index `idx_wclf_active_ticker` (per Codex R1 M#9 closure — UNIQUE on `ticker WHERE cleared_at IS NULL`).

**NEW table `watchlist_close_track_flag_events`** per spec §7.2 — 6 columns + FK to `watchlist_close_track_flags(id)` `ON DELETE CASCADE`.

**Schema widenings per spec §3.4**:

- `fills`: ADD `fill_origin TEXT NOT NULL DEFAULT 'operator_typed'` CHECK `(fill_origin IN ('operator_typed', 'schwab_auto', 'schwab_auto_then_operator_corrected', 'tos_import', 'imported_legacy'))`.
- `fills`: ADD `schwab_source_value_json TEXT NULL` + `operator_corrected_value_json TEXT NULL` + `auto_fill_audit_at TEXT NULL`.
- `review_log`: ADD `auto_populated_field_keys_json TEXT NULL`.
- `schwab_api_calls.surface`: WIDEN CHECK to include `trade_entry` + `trade_exit`.

**FK cascade discipline** per spec §3.5:

- `pattern_evaluations.pipeline_run_id` → `pipeline_runs(id)` `ON DELETE CASCADE`.
- `pattern_exemplars.parent_exemplar_id` → `pattern_exemplars(id)` `ON DELETE RESTRICT` (per Codex R6 M#2 closure — SET NULL would violate codex_silver invariant).
- `chart_renders.pipeline_run_id` → `pipeline_runs(id)` `ON DELETE CASCADE` when non-NULL.
- `watchlist_close_track_flag_events.flag_id` → `watchlist_close_track_flags(id)` `ON DELETE CASCADE`.

### §B.4 v20 atomic-landing roster verbatim

Per spec §3.5 + §A.14 above, the v20 migration commit (T-A.1.1) lands ALL of the following IN ONE COMMIT:

1. Migration SQL file (5 new tables + 6 column adds + 1 CHECK widening + 4 FK declarations + 4 partial unique indexes + cross-column CHECKs).
2. Schema version bump `EXPECTED_SCHEMA_VERSION = 20`.
3. NEW Python constants: `DETECTOR_PATTERN_CLASSES`, `_LABEL_SOURCE_VALUES`, `_FINAL_DECISION_VALUES`, `_FILL_ORIGIN_VALUES`, `_CHART_SURFACE_VALUES`, `_FLAG_SURFACE_VALUES`, `_FLAG_CLEARED_REASON_VALUES`, `_FLAG_EVENT_TYPE_VALUES`.
4. WIDENED Python constant: `_SCHWAB_API_SURFACE_VALUES` (+ `trade_entry` + `trade_exit`).
5. NEW dataclass models: `PatternExemplar`, `PatternEvaluation`, `ChartRender`, `WatchlistCloseTrackFlag`, `WatchlistCloseTrackFlagEvent` (in `swing/data/models.py`).
6. WIDENED dataclass: `Fill` gains `fill_origin` + `schwab_source_value_json` + `operator_corrected_value_json` + `auto_fill_audit_at` fields + `__post_init__` validator extension.
7. WIDENED dataclass: `ReviewLog` gains `auto_populated_field_keys_json` field.
8. NEW repo modules: `swing/data/repos/pattern_exemplars.py`, `swing/data/repos/pattern_evaluations.py`, `swing/data/repos/chart_renders.py`, `swing/data/repos/watchlist_close_track.py` — each with minimum CRUD (`insert_*`, `get_*_by_id`, `list_*`).
9. Discriminating test fixtures + 5 atomic-landing tests:
   - `test_v20_migration_lands_all_tables`: connect post-migration; assert all 5 new tables present + correct columns + indexes.
   - `test_v20_schema_python_constant_parity`: assert each Python constant matches the SQL CHECK enum verbatim (Phase 12 C.A T-A.2 family).
   - `test_v20_dataclass_validator_parity`: instantiate each new dataclass with all 7 cross-column invariant violation cases; assert each raises `ValueError`.
   - `test_v20_migration_backup_gate_fires_at_v19`: invoke `_apply_migration` with `pre_version=19, target_version=20`; assert backup file written.
   - `test_v20_migration_backup_gate_does_not_fire_at_v18`: invoke with `pre_version=18`; assert NO backup file (migration runner refuses multi-version jumps — must be sequential).

### §B.5 fill_origin backfill discipline (OQ-7 V1 simple)

Per OQ-7 BINDING V1 + spec §6.4: all existing `fills` rows get `fill_origin='operator_typed'` via SQL `DEFAULT 'operator_typed'` clause at column-add time. NO row-level rewriting required (DEFAULT applies to existing rows transparently at ALTER TABLE ADD COLUMN time per SQLite semantics).

Discriminating test (T-A.1.1.10): seed 10 fills pre-migration; apply v20; assert all 10 fills have `fill_origin='operator_typed'`.

V2 candidate banked at §J.3: backfill historical `reconciliation_corrections` chains (CVGI fill 9 + LION fill 15 + others) into `fills.schwab_source_value_json` + flip to `fill_origin='schwab_auto_then_operator_corrected'`.

### §B.6 v20 escalation rule (per dispatch brief §5 watch item 17 + §8 BINDING)

Per spec §3 + dispatch brief §5 watch item 17: if writing-plans surfaces schema additions BEYOND what brainstorm spec §3 specifies, STOP + escalate to orchestrator + amend spec (NOT silent absorption).

This plan introduces ZERO additional schema beyond spec §3. The roster at §B.4 above maps 1:1 onto spec §3.0 + §3.1 + §3.2 + §3.3 + §3.4 + §7.2 verbatim. If executing-plans implementer discovers a missing column or table during T2.SB1 task 1, ESCALATE — do not silently add.

---

## §C — Theme 1 architectural decisions (per spec §4 + OQ-2)

### §C.1 Chart rendering technology LOCK (matplotlib SVG inline)

Per spec §4.3 + Phase 10 §A.10 inheritance: all Theme 1 charts render as inline SVG embedded in HTMX partial responses. NO PNG. NO matplotlib mathtext. NO `$` / `^` / `_` / unbalanced `\` in any rendered text. ASCII-only. `parse_math=False` defense-in-depth if avoidance infeasible.

Module: NEW `swing/web/charts.py` (T1.SB0 introduces; T2.SB6 extends with annotated chart deliverable). Public surface:

```python
def render_watchlist_thumbnail_svg(*, ticker: str, bars: pd.DataFrame, ma_lines: list[int]) -> bytes
def render_hyprec_detail_svg(*, ticker: str, bars: pd.DataFrame, pattern_evaluation: PatternEvaluation | None = None) -> bytes
def render_position_detail_svg(*, ticker: str, bars: pd.DataFrame, trade: Trade, fills: list[Fill], current_stop: float | None) -> bytes
def render_market_weather_svg(*, bars: pd.DataFrame, trend_template_state: str) -> bytes
def render_theme2_annotated_svg(*, ticker: str, bars: pd.DataFrame, pattern_evaluation: PatternEvaluation, exemplar_thumbnails: list[bytes] | None = None) -> bytes
```

All return raw SVG bytes (UTF-8 encoded; ASCII-only content). Caller persists to `chart_renders.chart_svg_bytes` BLOB column.

### §C.2 `chart_renders` cache architecture LOCK (per spec §4.4)

Schema sketch is canonical per §B.3 → spec §3.2. Caching semantics per spec §4.4:

- **Run-bound surfaces** (`watchlist_row`, `hyprec_detail`, `market_weather`): regenerated only when `pipeline_runs.state='complete'` writes a new row; cache key `(ticker, surface, pipeline_run_id)`.
- **Position-detail surface**: regenerated on `fills` change events OR when `data_asof_date < last_completed_session(now())`; cache key `(ticker, surface)` with `pipeline_run_id=NULL`.
- **Theme2 annotated surface**: regenerated when `pattern_evaluations` writes a new verdict; cache key `(ticker, surface, pipeline_run_id, pattern_class)`.

**Session-anchor read/write predicate alignment** (per §A.13): writer stamps `data_asof_date = last_completed_session(now())`; reader staleness predicate uses SAME `last_completed_session(now())`. Discriminating round-trip test at T-T1.SB0.4 + T-T2.SB6.6.

**Cache invalidation pattern**: DELETE-then-INSERT atomic refresh (per §A.15 no INSERT OR REPLACE on audit-trail tables). Wrapped in `BEGIN IMMEDIATE` / `COMMIT` per §A.12.

**Storage budget**: ~2.5MB/run write → ~1GB/year. Acceptable for SQLite BLOB cache (per spec §4.4 calculation).

### §C.3 Market weather mini-chart placement LOCK (per spec §4.5)

Placement: TOP of `/dashboard` (above existing Phase 10 metrics tile navigator AND above the Phase 12 reconciliation banner). Operator daily-glance shows weather context BEFORE drilling into specifics.

Trigger: regenerated per-pipeline-run; cached in `chart_renders` table (surface=`market_weather`); rendered inline as part of `DashboardVM`.

**DashboardVM extension** (T2.SB6 task): new field `dashboard_weather_chart_svg_bytes: bytes | None = None` (populated `None` if no recent pipeline run; renders empty placeholder template).

Update cadence: per-pipeline-run + manual refresh via `POST /dashboard/weather-chart/refresh` (HTMX form with HX-Request propagation + HX-Redirect targeting `/dashboard` per §A.4).

### §C.4 Theme 2 annotated chart deliverable LOCK (per spec §4.6)

The annotated chart at T2.SB6 IS the v2 brief §9.2 evidence-to-show-reviewer deliverable AND the Theme 1 deepest-coverage chart. Annotations rendered per the Theme 2 detector's `structural_evidence_json`:

- VCP: contraction sequence markers + pivot price horizontal line + volume profile lower panel + trend-template state badge.
- Flat base: top/bottom horizontal lines + ATR shading + duration label.
- Cup-with-handle: cup left/bottom/right markers + handle entry/bottom + depth ratio label.
- High-tight flag: pole markers + consolidation range box + days-tight count.
- Double-bottom-W: trough_1 + center_peak + trough_2 markers + optional undercut indicator.

PLUS top-3 nearest historical-base overlay (per T2.SB5 template-matching output) rendered as small inline thumbnails (200x100 SVG) in a right-side panel.

Theme 1 + Theme 2 share T2.SB6 implementation: the annotated chart is rendered by `swing/web/charts.py:render_theme2_annotated_svg` (Theme 1) consuming `pattern_evaluations.structural_evidence_json` (Theme 2).

### §C.5 Chart surface inventory (per spec §4.2)

| Surface | Audience | Rendering scope | Performance budget |
|---|---|---|---|
| Watchlist row chart | Operator daily watchlist scan | Daily bars × 90 sessions; MA50/MA150/MA200; volume bars | Inline 200x100 SVG; eager per-run |
| Hyp-rec detail chart | Operator hyp-rec review | Daily bars × 180 sessions; MA50/MA150/MA200; volume; pattern boundaries from T2.SB6 | Full-size 800x500 SVG; eager per-run |
| Active position detail chart | Operator active position monitoring | Daily bars from entry-30 sessions → present; entry/exit fill markers; current stop line; trail-MA; MFE/MAE shading | Full-size 800x500 SVG; eager |
| Market weather mini-chart | Operator dashboard top | S&P 500 daily bars × 90 sessions; MA50/MA200; volume; trend-template state badge | Inline 400x150 SVG |
| Theme 2 annotated detector chart | Operator hyp-rec review for confirmed patterns | Hyp-rec detail + pattern boundaries from structural_evidence_json + top-3 historical thumbnails | Full-size 800x600 SVG with overlay panel |

### §C.6 V2 candidates banked (per spec §4.7)

- Interactive client-side JS chart library (TradingView Lightweight Charts / Plotly / Bokeh) for zoom + pan + drill-down.
- Per-row sparklines in `/trades/` + `/watchlist/` (inline 60x20 SVG).
- Multi-timeframe chart toggle (daily ↔ weekly).
- Annotation editor (operator-drawn boundaries override detector boundaries; closed-loop active learning per v2 brief §9.4).

---

## §D — Theme 2 architectural decisions (per spec §5 + OQ-3/4/5/9/10)

### §D.1 Module placement LOCK — `swing/patterns/` (per §A.2)

See §A.2 for the full module map. Per-file responsibility:

- `foundation.py` (T2.SB2): smoothing (EMA + kernel regression), extrema (zigzag adaptive threshold), variable-window candidate generator, volume primitives, trend-template state wrapper.
- `vcp.py` / `flat_base.py` / `cup_with_handle.py` (T2.SB3): rule-based geometric detectors.
- `high_tight_flag.py` / `double_bottom_w.py` (T2.SB4): rule-based geometric detectors.
- `template_matching.py` (T2.SB5): DTW with Sakoe-Chiba band; forward + reverse retrieval.
- `composite.py` (T2.SB5): geometric + template-match weighted sum per §5.8.
- `labeling.py` (T2.SB1): subagent dispatch glue + Codex selective policy operationalization.
- `drift_logging.py` (T2.SB3 + T2.SB4): feature distribution capture per OQ-9.
- `active_learning.py` (T2.SB6): prioritization helper per v2 brief §9.4.

### §D.2 Foundation primitives API LOCK (per spec §5.1)

`swing/patterns/foundation.py` exposes pure functions consumed by detectors (zero DB writes; zero side-effects):

```python
@dataclass(frozen=True)
class Swing:
    start_date: date
    end_date: date
    start_price: float
    end_price: float
    direction: Literal['up', 'down']
    depth_pct: float
    duration_days: int

@dataclass(frozen=True)
class CandidateWindow:
    ticker: str
    timeframe: Literal['daily', 'weekly']
    start_date: date
    end_date: date
    anchor_date: date
    anchor_reason: str

@dataclass(frozen=True)
class VolumeSegment:
    start_date: date
    end_date: date
    avg_volume: float

def smooth_ema(prices: np.ndarray, window: int) -> np.ndarray
def smooth_kernel_regression(prices: np.ndarray, bandwidth: float) -> np.ndarray
def extract_zigzag_swings(bars: pd.DataFrame, initial_threshold_pct: float, monotonic_narrow: bool = False) -> list[Swing]
def generate_candidate_windows(bars: pd.DataFrame, anchor_search_method: Literal['zigzag_pivot', 'ma_crossover', 'high_low_breakout']) -> list[CandidateWindow]
def volume_trend_through_swings(bars: pd.DataFrame, swings: list[Swing]) -> list[VolumeSegment]
def breakout_volume_ratio(bars: pd.DataFrame, breakout_date: date, baseline_days: int = 50) -> float
def current_stage(conn: sqlite3.Connection, ticker: str, asof_date: date) -> Literal['stage_1', 'stage_2', 'stage_3', 'stage_4', 'undefined']
```

`current_stage` consumes shipped Phase 4 evaluation surface (exact callsite verified at T2.SB2 task 1 by grep). Other primitives are pure-Python pure-functions; no I/O.

### §D.3 Per-detector evidence dataclass LOCK (per spec §5.2-§5.6)

Each detector emits a frozen dataclass serialized to `pattern_evaluations.structural_evidence_json`:

- `swing/patterns/vcp.py:VCPEvidence` per spec §5.2 (8 criteria + Contraction sub-dataclass).
- `swing/patterns/flat_base.py:FlatBaseEvidence` per spec §5.3 (7 criteria).
- `swing/patterns/cup_with_handle.py:CupWithHandleEvidence` per spec §5.4 (8 criteria + rounded-vs-V test per §10.7 LOCK).
- `swing/patterns/high_tight_flag.py:HighTightFlagEvidence` per spec §5.5 (6 criteria).
- `swing/patterns/double_bottom_w.py:DoubleBottomWEvidence` per spec §5.6 (8 criteria + undercut bonus).

Each `*Evidence` dataclass has a `criteria_pass: dict[str, bool]` field + `geometric_score: float` field. Serialization helper `evidence_to_json(ev)` returns JSON-compatible dict; deserialization helper `evidence_from_json(d, klass)` round-trips.

### §D.4 Composite scoring LOCK (per spec §5.8)

Per spec §5.8 LOCK: `composite_score = min(1.0, 0.60 × geometric_score + 0.40 × template_match_score)`.

Edge cases:
- `template_match_score` unavailable (first run; empty exemplar corpus): `composite_score = geometric_score` (per §5.8 LOCK).
- Double-bottom-W undercut bonus: `geometric_score` may be 1.10; composite formula caps via `min(1.0, ...)`.

NO calibration in V1 (per spec §5.8 LOCK; v2 brief §13.1 calibration deferred to gated v2 brief §16.5 G2 threshold).

### §D.5 Template matching LOCK (per spec §5.7 + OQ-4)

V1: DTW with Sakoe-Chiba band; window=0.1 × series_length. Pruning per spec §5.7:

1. Per-pattern exemplar filtering (VCP candidate compares ONLY against VCP exemplars).
2. Geometric-score pre-gate (DTW only fires for `geometric_score >= 0.4`).
3. Max windows per ticker per pattern per run = 3 (top-3 by zigzag-anchor strength).
4. Exemplar corpus subsampling at 100+ exemplars (50 highest-quality_grade subsample).

Normalization: min-max scaling per v2 brief §7 (LOCK; z-score is V2).

Benchmark gate (T2.SB5 task): `pytest-benchmark` discriminating test asserts full DTW pass completes within 120 seconds on operator's hardware (~3GHz CPU baseline). Failure escalates to SBD fallback per OQ-4 V2 disposition.

API:

```python
@dataclass(frozen=True)
class TemplateMatchHit:
    exemplar_id: int  # or candidate_id depending on direction
    distance: float
    similarity_score: float  # normalized 0..1

def match_forward(*, candidate_window: CandidateWindow, exemplar_corpus: list[PatternExemplar], top_k: int = 3) -> list[TemplateMatchHit]
def match_reverse(*, exemplar: PatternExemplar, candidate_corpus: list[CandidateWindow], top_k: int = 10) -> list[TemplateMatchHit]
```

### §D.6 Codex SELECTIVE policy operationalization (per §A.6 + spec §5.9 step 4)

Implemented in `swing/patterns/labeling.py:fire_codex_review_for_silver_row(exemplar_id, *, phase: Literal['t2_sb1', 't2_sb3_or_later'])`.

T2.SB1 phase: random 15% sampling. Implementation: `random.seed(<deterministic_seed>); random.random() < 0.15` per row insert.

T2.SB3+/SB4 phase: random 15% CONTINUES + high-stakes individual labels per spec §5.9 step 4. Implementation:

```python
should_fire = (
    random.random() < 0.15
    OR (silver_confidence == 'high' AND geometric_score < 0.5)
    OR (silver_confidence == 'low' AND geometric_score >= 0.8)
)
```

Retroactive evaluation: T2.SB3 task X (per §G T2.SB3 task list) re-evaluates the T2.SB1 corpus by recomputing geometric_score for each Claude silver row + firing Codex on rows that now match the high-stakes predicate.

Codex MCP invocation: `mcp__plugin_copowers_codex__codex` with `prompt='Review pattern label: ...'` per copowers convention. Response parsed for agreement boolean + alternative decision. Disagreement INSERTs new `codex_silver` row with `parent_exemplar_id` linkage.

### §D.7 Drift logging LOCK (per OQ-9 + spec §5.11)

Per OQ-9 BINDING V1: JSON column `pattern_evaluations.feature_distribution_log_json` per detector run. Substrate captured at T2.SB3 + T2.SB4 detector run-time:

```python
@dataclass(frozen=True)
class FeatureDistributionLog:
    # Per-detector input feature value distributions
    smoothing_params: dict[str, float]
    extrema_density_per_session: float
    contraction_depths: list[float] | None  # VCP-specific
    center_trough_retracement: float | None  # DBW-specific
    volume_aggregates: dict[str, float]
    # Composite layer
    composite_score_histogram_bins: list[int]
    # Universe context
    universe_size: int
    stage_2_pass_rate: float
    rs_rank_distribution: dict[str, float]
    # Verdict counts
    verdict_counts_per_pattern_class: dict[str, int]
```

Serialized to JSON; persisted on every `pattern_evaluations` row. Phase 13.5 monitoring side consumes; V2 dedicated table promotion only if Phase 13.5 demands.

### §D.8 Closed-loop surface architecture LOCK (per OQ-10 + spec §5.10)

Per OQ-10 BINDING: BOTH `/patterns/{candidate_id}/review` (per-candidate review form) AND `/metrics/pattern-outcomes` (9th metric tile).

`/patterns/{candidate_id}/review` page content per v2 brief §9.2 8-item checklist (spec §5.10):
1. Proposed pattern class (labeled tile, color-coded per pattern class).
2. Geometric score breakdown by rule component.
3. Top-3 nearest historical bases (template matches; thumbnails via Theme 1 annotated renderer).
4. Trend-template status for ticker.
5. RS rank.
6. Recent volume profile (last 30 sessions sparkline + 50d avg comparison).
7. Reason for uncertainty in rule evaluation (`structural_evidence_json.criteria_pass` per-criterion text).
8. Outcome distribution from prior similar candidates (composes with Phase 10 metrics cohort architecture).

Form decision enum (per v2 brief §9.3 + spec §5.10): `confirm` / `watch` / `reject` / `relabel` / `pattern_present_outside_window` / `multiple_overlapping_patterns`. POST persistence per §3.1 source-vs-decision matrix CHECK invariant.

`/metrics/pattern-outcomes` 9th metric tile: extends Phase 10 metrics architecture. NEW VM `swing/web/view_models/patterns/outcomes_card.py:PatternOutcomesVM` extends `BaseLayoutVM`. Per-pattern-class outcome distributions: "of the last N similar-score candidates, X% triggered, Y% reached 1R, Z% hit stop." Honesty class A (Wilson CI per Phase 10 honesty.py); suppression at n < 5 per Phase 10 §5.1.

### §D.9 Active learning prioritization LOCK (per spec §5.10 + v2 brief §9.4)

NEW `/patterns/queue` route showing top-K candidates prioritized by:
1. Borderline geometric scores (`abs(geometric_score - 0.5) < 0.1`).
2. Rule/template disagreement (`abs(geometric_score - template_match_score) > 0.3`).
3. Underrepresented regimes (low historical exemplar count for current weather state).
4. Failed-rule near-misses (`geometric_score in [0.55, 0.70]`).

Helper at `swing/patterns/active_learning.py:prioritize_candidates(conn, top_k=20) -> list[CandidatePriority]`.

### §D.10 Tolerance-semantics LOCK (per spec §10.6)

Per spec §10.6 BINDING:
- **"Tolerance band ±X%"** in a criterion table means PASSES if `actual_value` falls within `[bound - X%, bound + X%]`. FAILS if outside. Symmetric.
- **"NONE — hard gate"** means STRICT inequalities with NO tolerance.
- **"NONE — these are bounds, not point thresholds"** means RANGE checks (e.g., depth in [10%, 35%]); failure-on-out-of-range; ZERO tolerance.

Applied verbatim in every per-detector criterion evaluation. Discriminating tests per §G enumerate boundary-case + within-tolerance + outside-tolerance assertions.

### §D.11 Cup curvature LOCK (per spec §10.7)

Per spec §10.7 BINDING: rounded-vs-V test centered on `cup_bottom_date` with ±10-day window:
- Compute `window_lows = bars where bar_date in [cup_bottom_date - 10 days, cup_bottom_date + 10 days]`.
- Compute `bars_within_2pct_of_bottom = bars in window_lows where bar.low <= cup_bottom_price × 1.02`.
- Rounded test: `len(bars_within_2pct_of_bottom) >= 5`.
- V-shape rejection: `len(bars_within_2pct_of_bottom) <= 2` rejects candidate.
- Marginal zone: 3-4 bars within 2% → composite score penalty 0.10.

Implemented in `swing/patterns/cup_with_handle.py:_is_rounded_cup(bars, cup_bottom_date, cup_bottom_price) -> tuple[bool, float]` returning `(is_rounded, penalty)`.

---

## §E — Theme 3 architectural decisions (per spec §6 + OQ-7/8)

### §E.1 fill_origin enum LOCK (per §B.5 + spec §6.4)

5-value CHECK enum: `operator_typed` / `schwab_auto` / `schwab_auto_then_operator_corrected` / `tos_import` / `imported_legacy`. Python constant `_FILL_ORIGIN_VALUES` mirrors. `Fill.__post_init__` validator enforces. Backfill via SQL DEFAULT per §B.5.

State transitions:
- Form-render with Schwab auto-fill populated: server-stamps `schwab_auto`.
- Operator edits a pre-populated field before submit: flips to `schwab_auto_then_operator_corrected`.
- No Schwab auto-fill available (empty / degraded / sandbox): `operator_typed`.
- TOS CSV import path: `tos_import` (future capability; not exercised at Phase 13 V1 V2 candidate).
- Legacy backfill: `imported_legacy` (V2 candidate; not used at V1).

### §E.2 Schwab integration discipline (per §A.11)

Every Schwab API consumer surface in T3.SB1 + T3.SB2 follows the 4-step discipline:
1. `cfg = apply_overrides(base_cfg)`.
2. `client_id, client_secret = resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)`.
3. `client = construct_authenticated_client(cfg, environment, client_id, client_secret)`.
4. Sandbox short-circuit + DEGRADED handling per spec §6.1 + §6.2.

Discriminating tests per §G enumerate the 4-step trace + sandbox short-circuit assertion + DEGRADED banner assertion + empty-response handling.

### §E.3 Review auto-fill data source LOCK (per OQ-8)

Per OQ-8 BINDING: OhlcvCache (post-T1.SB0) for MFE/MAE candle data. yfinance V2-fallback only. No new Schwab API consumption at T3.SB3.

Source ladder:
1. `daily_management_records.open_MFE_R_to_date` / `open_MAE_R_to_date` (Phase 8 daily-management coverage if present).
2. OhlcvCache daily-bar synthesis: `mfe_pct = max(daily highs since entry) / entry_price - 1`; `mae_pct = min(daily lows since entry) / entry_price - 1`.

T3.SB3 implementation: prefer source 1 if `daily_management_records` row exists for the trade; else fall through to source 2.

### §E.4 Priors auto-fill (per spec §6.3)

NEW helper `swing/trades/review.py:get_priors_for_ticker(conn, ticker, n=5) -> ReviewPriors` returning:

```python
@dataclass(frozen=True)
class ReviewPriors:
    mistake_tag_candidates: list[str]  # union of mistake_tags from last N reviews same ticker
    process_grade_baseline: float | None  # mean of recent N grades (numeric encoding A=4..F=0)
    lesson_learned_candidates: list[str]  # LATEST N entries
```

Auto-fill form-render reads + populates as DEFAULT values on form input fields. Operator-editable (operator can confirm/edit/add/clear).

### §E.5 Period review auto-fill (per spec §6.3)

NEW helpers (consumer-side over `review_log`):

```python
def get_period_lessons_summary(conn, *, period_start: date, period_end: date) -> str  # concatenated lessons
def get_period_mistake_tag_aggregate(conn, *, period_start: date, period_end: date) -> dict[str, int]  # tag -> count
def get_period_cohort_health_deltas(conn, *, current_period_start: date, current_period_end: date, prior_period_start: date, prior_period_end: date) -> dict[str, float]  # cohort -> delta
```

Period reviews consume; surfaced as starter text in section fields.

### §E.6 Hidden audit anchor LOCK (per spec §6.1 + Phase 8 R2-R5 family)

Per forward-binding lesson #20 (spec §11.20):

- `schwab_source_value_json` — server-stamped at form-render time to the original Schwab-API-derived values; persisted regardless of operator edits.
- `auto_fill_audit_at` — server-stamped ISO timestamp at form render.

Form rendering: display-only `<span class="muted">` text for `fill_origin` + `auto_fill_audit_at` (operator sees what will be persisted; cannot tamper). Operator-editable input fields ONLY for `entry_date` / `entry_price` / `initial_shares` (and exit-side equivalents).

Soft-warn confirm fragment: if operator edits a pre-populated field, soft-warn renders with `form_values` dict round-tripping the hidden anchors (per Phase 9 Sub-bundle D R3 Critical #1 + forward-binding lesson #13).

### §E.7 review_log.auto_populated_field_keys_json LOCK

NEW column added at v20 (per §B.3). Stores JSON array of field keys auto-populated at form render. Phase 6 review POST handler EXTENDED to persist the JSON envelope on submit.

Discriminating test (per §G T3.SB3): plant review with prior priors; render form; assert hidden field carries `["mistake_tags", "process_grade_baseline"]`; submit; assert `auto_populated_field_keys_json` persisted.

### §E.8 Cross-bundle dependencies (per §A.1 + spec §6.5)

- T3.SB1 dispatches CONCURRENT with T2.SB1 (independent codebase touch; OQ-12 Option E migration coordination).
- T3.SB2 dispatches AFTER T2.SB3 (Schwab Trader API consumer merge-conflict avoidance).
- T3.SB3 dispatches AFTER T2.SB5 (consumes OhlcvCache patterns + candidate-window primitives).

---

## §F — Theme 4 architectural decisions (per spec §7 + L11 + 7 D-Q4 sub-decisions)

### §F.1 Operator-elicited usability list LOCK (per L11 + dispatch brief §1.1)

Per orchestrator-pre-writing-plans elicitation 2026-05-18 PM: operator confirmed NO additional usability items beyond Q4. T4.SB ships Q4 close-tracking flag only per spec §7.1 baseline lock. NO scope expansion at writing-plans time. Brief §2.11 + §6 done criterion 10 BINDING.

If future operator elicitation surfaces additional items (post-Phase-13 dispatch), they route to Phase 13.5 or Phase 14 — NOT a Phase 13 scope expansion.

### §F.2 Q4 close-tracking flag schema LOCK (per spec §7.2 D-Q4.1)

Per D-Q4.1 BINDING (Option B; new table): NEW `watchlist_close_track_flags` table (per §B.3) + audit `watchlist_close_track_flag_events` table.

PARTIAL UNIQUE INDEX `idx_wclf_active_ticker ON watchlist_close_track_flags(ticker) WHERE cleared_at IS NULL` — allows historical cleared-flag rows to persist as audit history while enforcing one ACTIVE flag per ticker. Re-flagging a previously-cleared ticker INSERTs new row (new lifecycle episode) without UNIQUE collision (per Codex R1 M#9 closure).

### §F.3 Q4 surfaces LOCK (per spec §7.2 D-Q4.2 + D-Q4.4 + D-Q4.5 + D-Q4.6)

**Web toggle** (per D-Q4.2): small toggle button on watchlist row (top-right of row). Click sets flag; click again clears. POST routes per §A.4: `POST /watchlist/{ticker}/flag` + `POST /watchlist/{ticker}/unflag`.

**CLI** (per D-Q4.2): NEW `swing watchlist flag <ticker> --close-track [--reason TEXT]` + `swing watchlist unflag <ticker>` subcommands. Both surfaces persist to same table via `swing/trades/watchlist_close_track.py` service.

**Visual rendering** (per D-Q4.4): ASCII-only inline badge `[*]` on flagged watchlist row + sort priority (flagged rows appear FIRST regardless of pipeline algorithm's sort order). NO emoji per Windows cp1252 stdout safety.

**Filtering interaction** (per D-Q4.5): `watchlist` view-model query UNION's pipeline_algorithm_output + flagged_tickers_not_in_algorithm_output. Sort order: flagged-first, then pipeline algorithm order. Flagged-but-not-in-algorithm gets sub-badge `(operator-flagged; algo dropped)`.

**Relation to hyp-rec** (per D-Q4.6): NO — watchlist-surface-only. Conflating dilutes hyp-rec semantic. V2 candidate.

**WatchlistVM extension** (T4.SB task): new fields `flagged_close_track_tickers: tuple[str, ...]` + `flagged_close_track_count: int`. Existing watchlist template extended with badge + sort logic.

### §F.4 Q4 persistence semantics LOCK (per spec §7.2 D-Q4.3)

Per D-Q4.3 BINDING: Persistent until operator clears OR auto-clear on operator opens a position in that ticker. NO auto-expire by date.

**Auto-clear transactional discipline** (per §A.12 + spec §7.2 D-Q4.3 LOCK):

- Fires inside the SAME transaction that INSERTs the `trades` row.
- Service function: `swing/trades/watchlist_close_track.py:auto_clear_on_position_open(conn, ticker)` — caller-tx contract (consumed from inside the trade-entry service's outer `with conn:` block).
- Public companion: `swing/trades/watchlist_close_track.py:clear_flag(conn, ticker, *, source: Literal['web', 'cli'], reason: str | None = None)` — reject-caller-held-tx contract; owns BEGIN IMMEDIATE / COMMIT / ROLLBACK.
- Sandbox short-circuit: inner function checks `cfg.integrations.schwab.environment == 'sandbox'` and returns no-op (NOT outer; per Phase 12 C.C lesson #2).
- Audit-row append-only: emits `watchlist_close_track_flag_events` row with `event_type='clear'`; parent `watchlist_close_track_flags` row gets `cleared_at` + `cleared_reason='auto_cleared_on_position_open'` UPDATE (NOT DELETE).

### §F.5 Q4 audit trail LOCK (per spec §7.2 D-Q4.7)

Per D-Q4.7 BINDING: per-flag-event row with timestamp + ticker + reason text (optional) + flag_source ('web' / 'cli'). Audit table separate from primary table; append-only INSERT discipline (no UPDATE-in-place; per `reconciliation_corrections` Phase 12 C.A precedent).

Event types: `set` (flag created) / `clear` (flag cleared by operator OR auto-cleared on position open).

---

## §G — Per-sub-bundle task decomposition

Each sub-bundle below has per-task acceptance criteria + discriminating test patterns. Tasks number `T-<SB>.<N>` where `<SB>` is short-form sub-bundle code (e.g., `T-T1.SB0.1` = T1.SB0 task 1).

Test delta + LOC projections per §K below; cross-bundle dependencies per §H.

### §G.0 Sub-bundle T1.SB0 — OhlcvCache → `_step_charts` wiring (4 tasks)

**Goal:** Close Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral. Wire OhlcvCache into `swing/pipeline/runner.py:_step_charts`. Substrate for Theme 2 detectors + T3.SB3 review auto-fill.

**Branch:** `phase13-t1-sb0-ohlcv-charts-wiring`. Worktree branches from main HEAD.

**Files in scope:**
- Modify: `swing/pipeline/runner.py` (`_step_charts` function around line 1204).
- Modify: `swing/web/ohlcv_cache.py` (add `get_or_fetch(ticker, window_days)` if not present; verify per-cache locking).
- Modify: `swing/pipeline/ohlcv.py` (`fetch_daily_bars` shape reconciliation; deprecate legacy bare `fetcher.get(...)` path).
- Create: `tests/pipeline/test_step_charts_ohlcv_cache_wiring.py`.
- Create: `tests/pipeline/test_ohlcv_cache_shape_parity.py`.

#### Task T-T1.SB0.1 — Recon + OhlcvCache.get_or_fetch surface verification

**Files:**
- Read-only inventory: `swing/pipeline/runner.py` `_step_charts` body (line 1204); `swing/web/ohlcv_cache.py` public methods.
- Create: `docs/phase13-t1-sb0-recon.md` — recon document enumerating: (a) current `_step_charts` data flow; (b) OhlcvCache public surface; (c) per-cache locking discipline; (d) shape semantics of `to_dataframe()` vs legacy `fetch_daily_bars`; (e) discriminating-test plant for the shape-parity regression.

- [ ] **Step 1: Read `_step_charts` end-to-end**

Run: `Read` `swing/pipeline/runner.py` lines 1204-1350 (or until function end).

- [ ] **Step 2: Read OhlcvCache public surface**

Run: `Read` `swing/web/ohlcv_cache.py` end-to-end.

- [ ] **Step 3: Write recon document at `docs/phase13-t1-sb0-recon.md`**

Document: data flow + surface gap + shape semantics + per-cache locking + test plant proposal.

- [ ] **Step 4: Commit**

```bash
git add docs/phase13-t1-sb0-recon.md
git commit -m "docs(phase13): T1.SB0 recon — OhlcvCache → _step_charts wiring inventory (T-T1.SB0.1)"
```

**Acceptance criteria:**
- Recon doc enumerates every callsite of `fetcher.get` in `_step_charts` body.
- Recon doc identifies whether `OhlcvCache.get_or_fetch` method exists or needs adding.
- Recon doc proposes shape-parity discriminating test.

#### Task T-T1.SB0.2 — Add `OhlcvCache.get_or_fetch` IF MISSING + shape-parity test plant

**Files:**
- Modify (conditional on recon): `swing/web/ohlcv_cache.py`.
- Create: `tests/pipeline/test_ohlcv_cache_shape_parity.py`.

- [ ] **Step 1: Write failing test**

```python
# tests/pipeline/test_ohlcv_cache_shape_parity.py
import pandas as pd
from datetime import date
from swing.web.ohlcv_cache import OhlcvCache
from swing.pipeline.ohlcv import fetch_daily_bars
from swing.config import load_cfg

def test_ohlcv_cache_get_or_fetch_shape_matches_legacy_fetch_daily_bars(tmp_path, monkeypatch):
    # Seed OhlcvCache with known fixture; seed legacy fetcher with same fixture.
    # Call OhlcvCache.get_or_fetch(ticker='AAPL', window_days=180).
    # Call fetch_daily_bars(ticker='AAPL', lookback_days=180, as_of_date=None).
    # Assert both return DataFrames with: same columns (capitalized: Open/High/Low/Close/Volume);
    # same DatetimeIndex; same row count; same values within float tolerance.
    cfg = load_cfg()
    cache = OhlcvCache(cfg=cfg)
    cache_df = cache.get_or_fetch(ticker='AAPL', window_days=180)
    legacy_df = fetch_daily_bars(ticker='AAPL', lookback_days=180, as_of_date=None)
    assert list(cache_df.columns) == list(legacy_df.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
    assert isinstance(cache_df.index, pd.DatetimeIndex)
    pd.testing.assert_frame_equal(cache_df, legacy_df, check_exact=False, rtol=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/pipeline/test_ohlcv_cache_shape_parity.py -v`
Expected: FAIL with `AttributeError: 'OhlcvCache' object has no attribute 'get_or_fetch'` OR shape mismatch.

- [ ] **Step 3: Implement `OhlcvCache.get_or_fetch(ticker, window_days)`**

Add to `swing/web/ohlcv_cache.py`:

```python
def get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame:
    """Return daily bars for ticker over `window_days` lookback.
    
    Cache-checks first; on miss, routes through ohlcv_archive parquet write-through
    cache + yfinance V2 fallback. Returns DataFrame with capitalized columns + DatetimeIndex.
    """
    # Existing OhlcvCache discipline: per-cache locking, sliding-window breaker,
    # in-deadline futures only writes (per Phase 11 lesson).
    return self._get_or_fetch_impl(ticker=ticker, window_days=window_days)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/pipeline/test_ohlcv_cache_shape_parity.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/ohlcv_cache.py tests/pipeline/test_ohlcv_cache_shape_parity.py
git commit -m "feat(phase13): OhlcvCache.get_or_fetch + shape-parity test (T-T1.SB0.2)"
```

**Acceptance criteria:**
- `OhlcvCache.get_or_fetch` exists with documented signature.
- Shape-parity test passes (DataFrames identical between cache + legacy paths).

#### Task T-T1.SB0.3 — Wire `_step_charts` through OhlcvCache + discriminating test

**Files:**
- Modify: `swing/pipeline/runner.py` (`_step_charts` body — replace `fetcher.get(...)` calls with `ohlcv_cache.get_or_fetch(...)`).
- Create: `tests/pipeline/test_step_charts_ohlcv_cache_wiring.py`.

- [ ] **Step 1: Write failing test**

```python
def test_step_charts_uses_ohlcv_cache_not_legacy_fetcher(tmp_path, monkeypatch):
    # Mock OhlcvCache.get_or_fetch to assert it's invoked; mock fetch_daily_bars
    # to FAIL if invoked (verifying _step_charts no longer touches legacy path
    # for daily-bar chart generation).
    from unittest.mock import MagicMock, patch
    from swing.pipeline.runner import _step_charts
    
    mock_cache = MagicMock()
    mock_cache.get_or_fetch.return_value = _build_fixture_daily_bars(...)
    
    with patch('swing.pipeline.ohlcv.fetch_daily_bars', side_effect=AssertionError("legacy path invoked")):
        result = _step_charts(cfg=..., lease=..., eval_run_id=..., data_asof=..., fetcher=mock_cache)
    
    assert mock_cache.get_or_fetch.called
    assert isinstance(result, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/pipeline/test_step_charts_ohlcv_cache_wiring.py -v`
Expected: FAIL (current `_step_charts` still calls legacy `fetcher.get` / `fetch_daily_bars`).

- [ ] **Step 3: Modify `_step_charts` to invoke OhlcvCache**

Replace each `fetcher.get(ticker, lookback_days=180, as_of_date=None)` callsite with `fetcher.get_or_fetch(ticker=ticker, window_days=180)` (assuming `fetcher` is now an OhlcvCache instance — or rename parameter to `ohlcv_cache`).

Update `_step_charts` signature: `def _step_charts(*, cfg, lease, eval_run_id, data_asof, ohlcv_cache: OhlcvCache) -> dict[str, Path]`.

Update the runner's `_step_charts` callsite (search for the call in the runner's outer step loop) to pass `ohlcv_cache=ohlcv_cache` instead of `fetcher=fetcher`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/pipeline/test_step_charts_ohlcv_cache_wiring.py -v`
Expected: PASS.

- [ ] **Step 5: Run full pipeline test suite**

Run: `python -m pytest tests/pipeline/ -v`
Expected: All existing pipeline tests pass.

- [ ] **Step 6: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_step_charts_ohlcv_cache_wiring.py
git commit -m "feat(phase13): wire _step_charts through OhlcvCache.get_or_fetch (T-T1.SB0.3)"
```

**Acceptance criteria:**
- `_step_charts` no longer invokes `fetch_daily_bars` directly.
- All existing pipeline tests continue to pass.

#### Task T-T1.SB0.4 — Per-cache locking + concurrent-fetch discriminating test + chart-bytes parity test + ruff sweep

**Files:**
- Modify (conditional): `swing/web/ohlcv_cache.py` (add `threading.RLock` if concurrent fetch surfaces race).
- Create: `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py`.
- Create: `tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py`.

- [ ] **Step 1: Write concurrent-fetch discriminating test**

```python
def test_ohlcv_cache_concurrent_multi_ticker_no_data_corruption(tmp_path, monkeypatch):
    # Spawn N=5 threads simultaneously calling OhlcvCache.get_or_fetch with
    # 5 different tickers. Assert each thread receives its expected DataFrame
    # (no cross-ticker data leakage) + no exceptions raised.
    import threading
    cache = OhlcvCache(cfg=load_cfg())
    results = {}
    errors = []
    def worker(ticker):
        try:
            results[ticker] = cache.get_or_fetch(ticker=ticker, window_days=180)
        except Exception as e:
            errors.append((ticker, e))
    threads = [threading.Thread(target=worker, args=(t,)) for t in ['AAPL', 'MSFT', 'GOOG', 'TSLA', 'NVDA']]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not errors
    assert len(results) == 5
    for ticker, df in results.items():
        assert df.index.name in (None, 'Date')
        assert (df.index > pd.Timestamp('2024-01-01')).all()
```

- [ ] **Step 2: Run test; verify pass (or fail → add RLock; re-run; pass)**

Run: `python -m pytest tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py -v`

- [ ] **Step 3: Write chart-bytes parity test**

Discriminating test asserting chart bytes match between (a) chart rendered from OhlcvCache.get_or_fetch'd DataFrame and (b) chart rendered from legacy fetch_daily_bars'd DataFrame. Per spec §4.1 step 2 ("chart renderers accept the to_dataframe() shape; assert chart bytes match a known-good fixture rendered from both paths").

- [ ] **Step 4: Run test; verify pass**

Run: `python -m pytest tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py -v`

- [ ] **Step 5: Ruff sweep**

Run: `ruff check swing/`
Expected: baseline 0 E501 maintained.

- [ ] **Step 6: Commit**

```bash
git add swing/web/ohlcv_cache.py tests/pipeline/
git commit -m "feat(phase13): T1.SB0 closer — per-cache locking + chart-bytes parity + ruff (T-T1.SB0.4)"
```

**Acceptance criteria:**
- Concurrent multi-ticker fetch produces no race / no data corruption.
- Chart bytes parity assertion passes between OhlcvCache + legacy paths.
- Ruff baseline 0 E501 maintained.

**Operator-witnessed gate (T1.SB0):**
- S1 (inline): pytest fast-tests + ruff.
- S2 (browser/CLI): `python -m swing.cli pipeline run` against operator's production produces a complete briefing.md with `_step_charts` succeeding through OhlcvCache (cassette-mode acceptable for CI; live-mode under operator-paired session).
- S3 (cross-validation): operator compares chart output PNG/SVG against pre-Phase-13 baseline — visual parity asserted.

**Cross-bundle pin plants (per §H):**
- `test_ohlcv_cache_get_or_fetch_invariant` — un-skips at T2.SB2 + T2.SB3 + T3.SB3 (consumers).

### §G.1 Sub-bundle T2.SB1 — Dev-time labeling infrastructure (8 tasks; migration task 1 per OQ-12 Option E)

**Goal:** Land v20 migration (atomic per §B.4); ship dev-time labeling infrastructure (Claude Code subagent + selective Codex 2nd-reviewer); operator-paired mid-dispatch exemplar bootstrap pause per OQ-6.

**Branch:** `phase13-t2-sb1-dev-time-labeling-infra`. Worktree branches from main HEAD AFTER T1.SB0 merges.

**Files in scope:**
- Create: `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql`.
- Modify: `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION = 20`).
- Modify: `swing/data/models.py` (NEW dataclasses + Fill widening + ReviewLog widening).
- Create: `swing/data/repos/pattern_exemplars.py`, `swing/data/repos/pattern_evaluations.py`, `swing/data/repos/chart_renders.py`, `swing/data/repos/watchlist_close_track.py`.
- Create: `swing/patterns/__init__.py` (DETECTOR_PATTERN_CLASSES constant + enum constants).
- Create: `swing/patterns/labeling.py` (subagent dispatch + selective Codex).
- Create: `.claude/agents/pattern-labeler.md` (Claude Code project-local subagent definition).
- Create: `scripts/record_pattern_labeler_cassettes.py`, `scripts/record_codex_mcp_pattern_review_cassettes.py`.
- Modify: `swing/cli.py` (add `swing patterns` group + `label-exemplars` subcommand).
- Create: `swing/web/routes/patterns.py` (skeleton + `/patterns/exemplars` GET + `/patterns/exemplars/{id}/action` POST).
- Create: `swing/web/view_models/patterns/exemplars.py`.
- Create: `swing/web/templates/patterns/exemplars.html.j2`.
- Create: `tests/integrations/cassettes/pattern_labeler/`, `tests/integrations/cassettes/codex_mcp_pattern_review/`.
- Create: tests under `tests/data/`, `tests/patterns/`, `tests/integrations/`, `tests/web/`, `tests/cli/`.

#### Task T-A.1.1 — v20 migration atomic landing (MIGRATION-ONLY COMMIT per OQ-12 Option E)

**Files:**
- Create: `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql`.
- Modify: `swing/data/db.py` (single-line `EXPECTED_SCHEMA_VERSION = 20`).
- Modify: `swing/data/models.py` (add NEW dataclasses per §B.4 #5; widen Fill + ReviewLog per §B.4 #6-#7).
- Create: `swing/patterns/__init__.py` (DETECTOR_PATTERN_CLASSES + label/decision/etc constants per §B.4 #3).
- Modify: `swing/integrations/schwab/audit_service.py` (widen `_SCHWAB_API_SURFACE_VALUES` per §B.4 #4).
- Create: `swing/data/repos/pattern_exemplars.py`, `pattern_evaluations.py`, `chart_renders.py`, `watchlist_close_track.py` (minimum CRUD per §B.4 #8).
- Create: `tests/data/test_v20_migration.py`.

- [ ] **Step 1: Write 6 discriminating tests per §B.4 #9 atomic-landing roster**

```python
def test_v20_migration_lands_all_tables(): ...
def test_v20_schema_python_constant_parity(): ...
def test_v20_dataclass_validator_parity(): ...
def test_v20_migration_backup_gate_fires_at_v19(): ...
def test_v20_migration_backup_gate_does_not_fire_at_v18(): ...
def test_v20_fill_origin_backfill_to_operator_typed(): ...
```

- [ ] **Step 2: Run tests; verify all 6 FAIL** (migration not yet written).

- [ ] **Step 3: Write migration SQL file** verbatim per spec §3.0-§3.5 + §7.2. Include: 5 NEW tables; 5 cross-column CHECK invariants on `pattern_exemplars`; 3 partial unique indexes on `chart_renders`; 1 partial unique index on `watchlist_close_track_flags`; 6 column adds; 1 CHECK widening on `schwab_api_calls.surface`; 4 FK declarations; 2 indexes on `pattern_exemplars`; 1 unique index on `pattern_evaluations`.

- [ ] **Step 4: Bump `EXPECTED_SCHEMA_VERSION` 19 → 20** at `swing/data/db.py:31`.

- [ ] **Step 5: Add 8 Python constants in `swing/patterns/__init__.py`** per §A.14 + §B.4 #3.

- [ ] **Step 6: Add 5 NEW dataclasses + widen Fill + widen ReviewLog** with `__post_init__` validators enforcing all 7 cross-column invariants per §A.14.

- [ ] **Step 7: Write minimum repo CRUD** for each new table per §B.4 #8 (caller-tx contract; no INSERT OR REPLACE).

- [ ] **Step 8: Run tests; verify all 6 PASS.**

- [ ] **Step 9: Commit ATOMIC migration landing**

```bash
git commit -m "feat(phase13): v20 migration — phase13 charts patterns autofill usability schema landing (T-A.1.1)"
```

- [ ] **Step 10: Record first-commit SHA for OQ-12 Option E coordination** — document for T3.SB1 branch base.

**Acceptance criteria:**
- ALL 6 discriminating tests pass.
- Migration is atomic (single commit; NO Python-then-validator split).
- `EXPECTED_SCHEMA_VERSION == 20`.
- All 8 Python constants + 5 NEW dataclasses + 2 widenings present.
- 4 new repo modules with CRUD ship.
- First-commit SHA recorded for T3.SB1 branch base.

**Watch items:**
- §A.14 Schema-CHECK + Python-constant + dataclass-validator paired atomic landing.
- §A.15 no INSERT OR REPLACE.
- §B.6 escalation rule.

**Cross-bundle pin plants:**
- `test_schema_version_v20_invariant` (un-skips at T3.SB1 merge).
- `test_pattern_exemplars_schema_shape_invariant` (un-skips at T2.SB3 + T2.SB5).
- `test_fill_origin_enum_complete_after_v20` (un-skips at T3.SB2).

#### Task T-A.1.2 — Claude Code subagent `.claude/agents/pattern-labeler.md`

**Files:**
- Create: `.claude/agents/pattern-labeler.md` (project-local subagent per OQ-11).

- [ ] **Step 1: Write subagent definition** with frontmatter `name: pattern-labeler` + `description: ...` + `tools: Read, Glob, Grep`. Body per v2 brief §8.2 + spec §5.9 step 2.

- Input contract: `{window_ohlcv_json, pattern_class, rule_criteria, structural_evidence_schema}`.
- Output contract: `{evaluation: 'confirmed' | 'watch' | 'rejected' | 'relabel:<other_class>', confidence: 'high' | 'medium' | 'low', structural_evidence_json: {...}, geometric_evidence_narrative: '...'}`.
- ASCII-only output (per §A.8).

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(phase13): pattern-labeler Claude Code subagent definition (T-A.1.2)"
```

**Acceptance criteria:**
- Subagent file committed (NOT gitignored).
- Subagent definition follows Claude Code agent frontmatter convention.

#### Task T-A.1.3 — `swing/patterns/labeling.py` subagent dispatch + selective Codex policy

**Files:**
- Create: `swing/patterns/labeling.py`.
- Create: `tests/patterns/test_labeling.py`.

- [ ] **Step 1: Write 4 failing tests** covering `fire_claude_silver_label(window, pattern_class)` + `fire_codex_review_for_silver_row(exemplar_id, phase)` + T2.SB1 phase 15% random + T2.SB3+/SB4 high-stakes clause + disagreement-chain parent_exemplar_id linkage.

- [ ] **Step 2: Implement** both functions per §D.6 phased policy. T2.SB1 phase: `random.random() < 0.15` only. T2.SB3+/SB4 phase: random 15% OR high-stakes clause OR low-confidence-high-geometric inverse. Codex disagreement INSERTs new codex_silver row with parent_exemplar_id linkage.

- [ ] **Step 3: Run tests; verify all PASS.**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(phase13): patterns labeling subagent + selective Codex glue (T-A.1.3)"
```

**Acceptance criteria:**
- Both functions implemented per §A.6 phased policy.
- 4 discriminating tests pass.
- Codex disagreement chain invariant (parent_exemplar_id linkage) preserved.

#### Task T-A.1.4 — Cassette infrastructure + sanitization filters

**Files:**
- Create: `tests/integrations/cassettes/pattern_labeler/` (dir).
- Create: `tests/integrations/cassettes/codex_mcp_pattern_review/` (dir).
- Create: `tests/integrations/test_pattern_labeler_cassette_sanitization.py`.
- Create: `tests/integrations/test_codex_mcp_cassette_sanitization.py`.
- Create: `scripts/record_pattern_labeler_cassettes.py`, `scripts/record_codex_mcp_pattern_review_cassettes.py`.

- [ ] **Step 1: Write sentinel-leak audit tests** per spec §A.10 + post-Phase-12 lesson #2. Plant known sentinel string in request URL + response body; assert sentinel absent from cassette files.

- [ ] **Step 2: Implement `before_record_request` + `before_record_response` filters** per §A.10:
  - URI sanitization: redact Claude API auth headers + MCP endpoint tokens.
  - Body sanitization: redact 32+ hex-char or 24+ base64-char token-shape sequences (defense-in-depth).

- [ ] **Step 3: Implement standalone recording scripts** per post-Phase-12 lesson #3 (over `@pytest.mark.vcr(record_mode='new_episodes')` pattern).

- [ ] **Step 4: Run sentinel tests; verify all PASS.**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(phase13): cassette infrastructure — pattern_labeler + codex_mcp sanitization (T-A.1.4)"
```

**Acceptance criteria:**
- Sanitization sentinel tests pass for both cassette directories.
- Standalone recording scripts present + invocable.

**Watch items:**
- §A.10 cassette infrastructure LOCK — forward-binding lesson #6 + #7.

#### Task T-A.1.5 — `swing patterns label-exemplars` CLI subcommand

**Files:**
- Modify: `swing/cli.py` (add `patterns` group + `label_exemplars_cmd` subcommand).
- Create: `tests/cli/test_patterns_label_exemplars_cli.py`.

- [ ] **Step 1: Write 3 failing tests**: (a) dispatches subagent + persists silver row; (b) rejects invalid pattern-class with click error; (c) ASCII-only output verified via capfd.

- [ ] **Step 2: Implement** `swing patterns label-exemplars --ticker <T> --start <D> --end <D> --pattern-class <C> [--timeframe daily|weekly]` per §A.4 + spec §5.9 step 1. Pattern-class choice constrained to DETECTOR_PATTERN_CLASSES via `click.Choice`.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(phase13): swing patterns label-exemplars CLI subcommand (T-A.1.5)"
```

**Acceptance criteria:**
- CLI dispatches subagent + persists silver row.
- ASCII-only output verified.
- Invalid pattern-class rejected.

#### Task T-A.1.6 — `/patterns/exemplars` web surface — operator spot-check + silver→gold promotion

**Files:**
- Create: `swing/web/routes/patterns.py` (skeleton + `/patterns/exemplars` GET + `/patterns/exemplars/{id}/action` POST).
- Create: `swing/web/view_models/patterns/__init__.py`, `exemplars.py`.
- Create: `swing/web/templates/patterns/exemplars.html.j2`.
- Modify: `swing/web/app.py` (register patterns router).
- Create: `tests/web/test_routes/test_patterns_exemplars.py`.

- [ ] **Step 1: Write 6 failing tests**: (a) GET lists silver rows; (b) POST action promote_to_gold flips row; (c) POST action reject; (d) POST action relabel with corrected_class form field; (e) POST action watch; (f) VM extends BaseLayoutVM + populates banner fields.

- [ ] **Step 2: Implement skeleton + GET/POST handlers**. POST response: `204 No Content` + `HX-Redirect: /patterns/exemplars` per forward-binding lesson #11. Embedded form: `hx-headers='{"HX-Request": "true"}'` per Phase 5 R1 M1.

- [ ] **Step 3: Implement PatternExemplarsVM extending BaseLayoutVM** per §A.3.

- [ ] **Step 4: Implement Jinja template** — ASCII-only per §A.8.

- [ ] **Step 5: Register router in `swing/web/app.py`.**

- [ ] **Step 6: Run tests; verify all PASS.**

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(phase13): /patterns/exemplars web surface — silver→gold spot-check (T-A.1.6)"
```

**Acceptance criteria:**
- GET lists silver rows; POST action persists all 4 final_decision flips correctly.
- VM extends BaseLayoutVM + populates banner fields.
- HTMX gotcha trinity preserved.

**Watch items:**
- §A.4 HTMX gotcha trinity (forward-binding lesson #11).
- §A.3 BaseLayoutVM banner pin (forward-binding lesson #12).

#### Task T-A.1.7 — Operator-paired mid-dispatch exemplar bootstrap pause (per OQ-6)

**This task is OPERATOR-PAIRED — implementer pauses dispatch + operator drives.**

- [ ] **Step 1: Implementer commits pre-pause state + announces pause-ready** (T-A.1.1 through T-A.1.6 committed + pushed).

- [ ] **Step 2: Orchestrator + operator paired session** — operator runs `swing patterns label-exemplars --ticker <T> --start <D> --end <D> --pattern-class <C>` for ~30-80 silver-tier exemplars across operator's historical universe (~2-year history) covering all 5 V1 pattern classes; reviews each silver row via `/patterns/exemplars`; promotes/rejects/relabels; optionally records cassettes via `scripts/record_pattern_labeler_cassettes.py`.

- [ ] **Step 3: Operator commits exemplar corpus + signals resume** to implementer.

- [ ] **Step 4: Implementer resumes** T-A.1.8.

**Acceptance criteria:**
- ~30-80 silver-tier exemplars persisted.
- Operator spot-checked ≥10% of silver rows; promoted ≥5 to gold per pattern class (~25 minimum total).
- Operator signal received before T-A.1.8 dispatch.

**Watch items:**
- §OQ-6 mirrors post-Phase-12 Sub-bundle 1 cassette session precedent.
- Task is NOT failable by the implementer; operator-paced.

#### Task T-A.1.8 — Cassette-mode validation + T2.SB1 closer + ruff sweep

**Files:**
- Create: `tests/integration/test_phase13_t2_sb1_labeling_e2e.py` — cassette-mode E2E.

- [ ] **Step 1: Write E2E test** exercising Claude silver → Codex review T2.SB1 phase (random 15%) → at least 1 disagreement → second codex_silver row inserted with parent linkage.

- [ ] **Step 2: Run E2E; verify PASS.**

- [ ] **Step 3: Run full fast-test suite** (+50-90 fast deltas land).

- [ ] **Step 4: Ruff sweep** — verify 0 E501.

- [ ] **Step 5: Commit**

```bash
git commit -m "test(phase13): T2.SB1 labeling E2E cassette-mode validation + closer (T-A.1.8)"
```

**Acceptance criteria:**
- E2E exercises full silver → Codex review → disagreement-chain path.
- Fast-test baseline maintained + T2.SB1 deltas land.
- Ruff 0 E501.

**Operator-witnessed gate (T2.SB1):**
- S1 (inline): pytest fast-tests + ruff.
- S2 (browser): `/patterns/exemplars` → confirm silver + gold rows; click promote → confirm flip persisted.
- S3 (CLI): operator-paired session per T-A.1.7 (operator-witnessed completion of bootstrap).
- S4 (audit): operator inspects `pattern_exemplars` rows; confirms label_source distribution matches expectation.

---

### §G.2 Sub-bundle T3.SB1 — Entry auto-fill (6 tasks; CONCURRENT with T2.SB1 per OQ-12 Option E)

**Goal:** Pre-populate trade entry form fields from Schwab Trader API at form-render time. fill_origin transitions + audit columns + audit row + soft-warn confirm.

**Branch:** `phase13-t3-sb1-entry-auto-fill`. Worktree branches FROM T2.SB1's first-commit SHA (NOT from main HEAD) per §B.2.

**Files in scope:**
- Modify: `swing/web/routes/trades.py` (`entry_form` at line 343 + `entry_post` at line 358).
- Create: `swing/trades/entry_auto_fill.py`.
- Modify: `swing/web/view_models/trades.py` (EntryFormVM fields).
- Modify: `swing/web/templates/trades/entry_form.html.j2`.
- Modify: `swing/data/repos/fills.py` (persist new audit columns).
- Modify: `swing/integrations/schwab/audit_service.py` (emit `surface='trade_entry'` audit row).
- Create: `tests/trades/test_entry_auto_fill.py`, `tests/web/test_routes/test_entry_form_auto_fill.py`, `tests/web/test_routes/test_entry_post_audit_columns.py`, `tests/integrations/test_schwab_entry_auto_fill_e2e.py` (1 slow E2E).

#### Task T-B.1.1 — Schema-version-20 prerequisite + recon

- [ ] **Step 1: Recon** — verify T3.SB1 worktree branched off T2.SB1's first-commit SHA; `swing/data/db.py:EXPECTED_SCHEMA_VERSION == 20`; `fills.fill_origin` column present; `schwab_api_calls.surface` CHECK widened.

- [ ] **Step 2: Write prerequisite test** + recon doc enumerating Schwab Trader API methods consumed: `account_orders(account_hash, maxResults=...)` + `account_details(account_hash, fields='positions')`. Response shape consumed via `_compute_execution_price` + `_resolve_match_quantity` per `swing/trades/schwab_reconciliation.py:99/174`.

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(phase13): T3.SB1 recon + v20 prerequisite test (T-B.1.1)"
```

**Acceptance criteria:**
- Prerequisite test passes (worktree correctly branched off T2.SB1 first-commit SHA).

#### Task T-B.1.2 — `swing/trades/entry_auto_fill.py` — Schwab fetch + value resolution

**Files:**
- Create: `swing/trades/entry_auto_fill.py`.
- Create: `tests/trades/test_entry_auto_fill.py`.

- [ ] **Step 1: Write 4 failing tests**: (a) matching Schwab BUY fill returns AutoFillResult with populated values + `fill_origin='schwab_auto'`; (b) empty Schwab response → empty result + `fill_origin='operator_typed'`; (c) sandbox short-circuits; (d) DEGRADED short-circuits with advisory.

- [ ] **Step 2: Implement** `EntryAutoFillResult` frozen dataclass + `resolve_entry_auto_fill(*, ticker, cfg, conn)` function per §A.11 4-step Schwab discipline + §E.1 fill_origin state transitions + spec §6.1 empty-state handling.

- [ ] **Step 3: Run tests; verify all PASS.**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(phase13): swing/trades/entry_auto_fill.py — Schwab fetch + value resolution (T-B.1.2)"
```

**Acceptance criteria:**
- 4 discriminating tests pass.
- Schwab discipline 4-step chain followed.
- `allow_prompt=False` REQUIRED (forward-binding lesson #10 + CLAUDE.md gotcha "form-render-time prompts would block HTTP handler").

#### Task T-B.1.3 — `entry_form` handler integration + EntryFormVM extension

**Files:**
- Modify: `swing/web/routes/trades.py:entry_form` at line 343.
- Modify: `swing/web/view_models/trades.py` (EntryFormVM fields).
- Modify: `swing/web/templates/trades/entry_form.html.j2`.
- Create: `tests/web/test_routes/test_entry_form_auto_fill.py`.

- [ ] **Step 1: Write 5 failing tests**: (a) auto-fill populated when Schwab returns BUY fill; (b) advisory when no match; (c) sandbox short-circuits; (d) hidden audit anchors present (`schwab_source_value_json` + `auto_fill_audit_at`); (e) VM extends BaseLayoutVM.

- [ ] **Step 2: Modify entry_form handler** — call `apply_overrides(cfg)` + `resolve_entry_auto_fill(...)` + `build_entry_form_vm(auto_fill=auto_fill)`. Return TemplateResponse.

- [ ] **Step 3: Extend EntryFormVM** — add `auto_fill_*` fields; extend BaseLayoutVM.

- [ ] **Step 4: Modify template** — render `auto_fill_*` as DEFAULT values on input fields; render `fill_origin` + `auto_fill_audit_at` as display-only `<span class="muted">`; render hidden inputs for `schwab_source_value_json` + `auto_fill_audit_at`; render `advisory_text` banner; add `hx-headers='{"HX-Request": "true"}'` per forward-binding lesson #11.

- [ ] **Step 5: Run tests; verify all PASS.**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(phase13): /trades/entry/form auto-fill integration (T-B.1.3)"
```

**Acceptance criteria:**
- 5 discriminating tests pass.
- HTMX gotcha trinity preserved.
- VM extends BaseLayoutVM.

#### Task T-B.1.4 — `entry_post` — fill_origin transition + audit row + soft-warn confirm

**Files:**
- Modify: `swing/web/routes/trades.py:entry_post` at line 358.
- Modify: `swing/trades/entry.py` (or wherever entry service lives).
- Modify: `swing/data/repos/fills.py` (extend insert to persist audit columns).
- Create: `tests/web/test_routes/test_entry_post_audit_columns.py`.

- [ ] **Step 1: Write 6 failing tests**: (a) persists `schwab_auto` when no operator edits; (b) flips to `schwab_auto_then_operator_corrected` when edited; (c) persists `operator_typed` when no auto-fill; (d) emits audit row with `surface='trade_entry'`; (e) soft-warn confirm round-trips hidden anchors via form_values dict; (f) `... or None` (NOT `... or ''`) for nullable audit fields (Phase 6 CLAUDE.md gotcha).

- [ ] **Step 2: Modify entry_post** — resolve fill_origin flip via comparing submitted values vs hidden `schwab_source_value_json` anchor; persist all audit columns; emit `schwab_api_calls.surface='trade_entry'` audit row; soft-warn confirm fragment round-trips hidden anchors via form_values dict per forward-binding lesson #13.

- [ ] **Step 3: Run tests; verify all PASS.**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(phase13): entry_post fill_origin transition + audit columns + soft-warn confirm (T-B.1.4)"
```

**Acceptance criteria:**
- 6 discriminating tests pass.
- fill_origin transitions correctly.
- Audit row + audit columns persisted.
- Soft-warn confirm round-trips hidden anchors.

**Watch items:**
- Forward-binding lesson #13 (form-render hidden anchors round-trip).
- Phase 6 `... or None` not `... or ''`.

#### Task T-B.1.5 — Cassette infrastructure extension + slow E2E

**Files:**
- Extend: `tests/integrations/cassettes/schwab/` (NEW trade_entry cassette files).
- Modify: `scripts/record_schwab_cassettes.py` (trade_entry targets).
- Create: `tests/integrations/test_schwab_entry_auto_fill_e2e.py` (1 slow E2E).

- [ ] **Step 1: Write slow E2E test** — replay cassette; GET `/trades/entry/form?ticker=AAPL`; assert response renders with expected auto_fill values + audit row written with `surface='trade_entry'` + signature_hash matching cassette.

- [ ] **Step 2: Record cassette (if operator-paired session) or replay.**

- [ ] **Step 3: Run E2E; verify PASS.**

- [ ] **Step 4: Commit**

```bash
git commit -m "test(phase13): T3.SB1 trade_entry cassette + slow E2E (T-B.1.5)"
```

**Acceptance criteria:**
- Slow E2E passes via cassette replay.
- Cassette sanitization filters cover trade_entry surface.

#### Task T-B.1.6 — T3.SB1 closer — integration E2E + ruff sweep

**Files:**
- Create: `tests/integration/test_phase13_t3_sb1_entry_auto_fill_e2e.py` (fast E2E).

- [ ] **Step 1: Write E2E** seeding full happy path: Schwab mock returns matching BUY fill; GET → POST; assert end-to-end trade + fill rows created with correct fill_origin + audit columns + audit row.

- [ ] **Step 2: Run E2E + full fast-test suite + ruff sweep.**

- [ ] **Step 3: Commit**

```bash
git commit -m "test(phase13): T3.SB1 closer — entry auto-fill E2E + ruff sweep (T-B.1.6)"
```

**Acceptance criteria:**
- E2E passes.
- Fast-test baseline maintained + T3.SB1 deltas land.
- Ruff 0 E501.

**Operator-witnessed gate (T3.SB1):**
- S1 (inline): pytest + ruff.
- S2 (browser): `/trades/entry/form?ticker=<real-ticker>` against operator's production Schwab → confirm auto-fill values.
- S3 (browser edit): operator edits pre-populated price; submits; confirms `fill_origin='schwab_auto_then_operator_corrected'`.
- S4 (browser sandbox): operator switches to sandbox cfg; confirms short-circuit + advisory.
- S5 (DB audit): operator inspects `schwab_api_calls` for `surface='trade_entry'` rows.

---

### §G.3 Sub-bundle T2.SB2 — Foundation primitives (6 tasks)

**Goal:** Ship pure-logic primitives consumed by T2.SB3 + T2.SB4 detectors. Per spec §5.1. ZERO DB writes.

**Branch:** `phase13-t2-sb2-foundation-primitives`. Branches from main HEAD after T2.SB1 + T3.SB1 merge.

**Files in scope:**
- Create: `swing/patterns/foundation.py` (smoothing + extrema + candidate windows + volume + trend-state).
- Create: `tests/patterns/test_foundation_smoothing.py`, `test_foundation_extrema.py`, `test_foundation_candidate_windows.py`, `test_foundation_volume.py`, `test_foundation_trend_state.py`.

#### Task T-A.2.1 — `smooth_ema` + `smooth_kernel_regression` per §5.1.1

- [ ] **Step 1: Write 4 failing tests**: (a) `smooth_ema` with window=5 matches known-good fixture; (b) EMA lag verified via input-step impulse response; (c) `smooth_kernel_regression` with bandwidth=10 matches known-good fixture; (d) kernel regression non-lag-introducing property (centered on input mean).
- [ ] **Step 2: Implement** both functions per spec §5.1.1 LOCK.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): foundation smoothing primitives (T-A.2.1)`.

**Acceptance criteria:**
- Pure functions; zero side-effects; ZERO DB writes.
- EMA + kernel regression match known-good fixtures.

#### Task T-A.2.2 — `extract_zigzag_swings` with adaptive threshold per §5.1.2

- [ ] **Step 1: Write 5 failing tests**: (a) static threshold 3% on monotonic uptrend → 0 swings; (b) static 3% on alternating ±5% pattern → expected swings; (c) `monotonic_narrow=True` produces decreasing thresholds across swings (VCP-specific); (d) adaptive threshold per `max(3.0, ATR_5d_pct × 1.5)` heuristic; (e) Swing dataclass shape correctness.
- [ ] **Step 2: Implement** `extract_zigzag_swings(bars, initial_threshold_pct, monotonic_narrow=False) -> list[Swing]` per spec §5.1.2 + Swing frozen dataclass per §D.2.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): foundation zigzag extrema with adaptive threshold (T-A.2.2)`.

#### Task T-A.2.3 — `generate_candidate_windows` per §5.1.3

- [ ] **Step 1: Write 4 failing tests**: (a) `zigzag_pivot` anchor produces windows from down-swing endpoints; (b) `ma_crossover` anchor produces windows from MA50/MA150 crossover points; (c) `high_low_breakout` anchor produces windows from 50d high breaches; (d) CandidateWindow dataclass shape + `anchor_reason` text.
- [ ] **Step 2: Implement** per spec §5.1.3 + CandidateWindow per §D.2. Multi-anchor mode optional V2.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): foundation variable-window candidate generator (T-A.2.3)`.

#### Task T-A.2.4 — `volume_trend_through_swings` + `breakout_volume_ratio` per §5.1.4

- [ ] **Step 1: Write 3 failing tests**: (a) `volume_trend_through_swings` returns one VolumeSegment per swing with correct avg_volume; (b) `breakout_volume_ratio` against 50d baseline returns expected ratio; (c) edge case: zero baseline volume → returns 0.0 (NOT NaN; NOT raise).
- [ ] **Step 2: Implement** per spec §5.1.4.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): foundation volume profile primitives (T-A.2.4)`.

#### Task T-A.2.5 — `current_stage` trend-template wrapper per §5.1.5

- [ ] **Step 1: Recon** — grep shipped Phase 4 evaluation surface for trend-template state callsite; verify return shape.
- [ ] **Step 2: Write 2 failing tests**: (a) `current_stage(conn, ticker='AAPL', asof_date=...)` reads from Phase 4 surface; (b) ticker without evaluation returns `'undefined'`.
- [ ] **Step 3: Implement** thin wrapper consuming shipped Phase 4 evaluation surface.
- [ ] **Step 4: Run tests; verify PASS.**
- [ ] **Step 5: Commit** — `feat(phase13): foundation current_stage trend-template wrapper (T-A.2.5)`.

#### Task T-A.2.6 — T2.SB2 closer — integration test + ruff sweep

- [ ] **Step 1: Write end-to-end integration test** chaining all primitives — smoothing → extrema → candidate windows → volume profile → trend state.
- [ ] **Step 2: Run full fast-test suite + ruff sweep.**
- [ ] **Step 3: Commit** — `test(phase13): T2.SB2 closer — foundation primitives integration + ruff (T-A.2.6)`.

**Operator-witnessed gate (T2.SB2):**
- S1 (inline): pytest + ruff.
- S2 (CLI exploratory): operator runs ad-hoc Python REPL invoking primitives against operator's real ticker data; verifies sanity (e.g., zigzag swings on a known VCP base produce plausible contraction sequence).

**Cross-bundle pin plants:**
- `test_foundation_primitives_consumed_by_detectors_invariant` (un-skips at T2.SB3 + T2.SB4).

---

### §G.4 Sub-bundle T2.SB3 — Detectors batch 1 (VCP + flat base + cup-with-handle) (9 tasks)

**Goal:** Ship 3 rule-based geometric detectors per spec §5.2 + §5.3 + §5.4. Each detector writes `pattern_evaluations` rows + emits feature-distribution-log per OQ-9.

**Branch:** `phase13-t2-sb3-detectors-batch1`. Branches from main HEAD after T2.SB2 merge.

**Files in scope:**
- Create: `swing/patterns/vcp.py`, `flat_base.py`, `cup_with_handle.py`, `drift_logging.py`.
- Modify: `swing/pipeline/runner.py` (add `_step_pattern_detect` step OR extend `_step_evaluate` per recon decision).
- Create: `tests/patterns/test_vcp.py`, `test_flat_base.py`, `test_cup_with_handle.py`, `test_drift_logging.py`.
- Create: `tests/integration/test_phase13_t2_sb3_detectors_e2e.py` (1 slow E2E covering all 3 detectors against operator's real ticker fixtures).

#### Task T-A.3.1 — Pipeline integration recon

- [ ] **Step 1: Recon** — review `swing/pipeline/runner.py` for where pattern detection should hook in. Decision: NEW `_step_pattern_detect` step OR extend `_step_evaluate`. Recommendation: NEW step after `_step_evaluate` (preserves separation of concerns; detection consumes Stage 2 + RS-rank-filtered candidate pool).
- [ ] **Step 2: Recon doc** at `docs/phase13-t2-sb3-recon.md` enumerating: (a) pipeline integration point; (b) per-detector evaluation order; (c) `pattern_evaluations` write discipline (caller-tx; no INSERT OR REPLACE).
- [ ] **Step 3: Commit** — `docs(phase13): T2.SB3 pipeline integration recon (T-A.3.1)`.

#### Task T-A.3.2 — VCP detector per spec §5.2

**Files:**
- Create: `swing/patterns/vcp.py`.
- Create: `tests/patterns/test_vcp.py`.

- [ ] **Step 1: Write 10+ failing tests** per spec §5.2 8 criteria × pass/fail boundaries + §10.1 worked example + §10.6 tolerance semantics:
  - `test_vcp_passes_all_criteria_returns_geometric_score_1_0` (per §10.1 CVGI hypothetical).
  - `test_vcp_fails_criterion_1_stage_not_2_returns_geometric_score_0_0`.
  - `test_vcp_fails_criterion_2_uptrend_below_28pct_with_tolerance_rejects` (per §10.6 LOCK: 28% vs 30% bound - 2% tolerance = 28%; boundary case).
  - `test_vcp_passes_criterion_2_uptrend_at_28pct_within_tolerance_band` (28% = 30% - 2%; should PASS as boundary).
  - `test_vcp_fails_criterion_3_non_monotonic_contractions`.
  - `test_vcp_passes_criterion_3_with_0_5pct_tolerance_on_monotonicity`.
  - `test_vcp_fails_criterion_4_T1_depth_below_10pct`.
  - `test_vcp_fails_criterion_5_volume_declining_violation`.
  - `test_vcp_fails_criterion_6_duration_outside_3_12_weeks`.
  - `test_vcp_passes_criterion_7_pivot_within_1pct_of_base_top`.
  - `test_vcp_optional_criterion_8_breakout_observed_increments_evidence`.
  - `test_vcp_structural_evidence_dataclass_shape_correctness`.
  - `test_vcp_evidence_to_json_round_trips`.

- [ ] **Step 2: Implement** `swing/patterns/vcp.py:VCPEvidence` frozen dataclass + `Contraction` sub-dataclass + `detect_vcp(bars, candidate_window) -> VCPEvidence` function per spec §5.2.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): VCP detector (T-A.3.2)`.

**Acceptance criteria:**
- All 12+ discriminating tests pass.
- §10.6 tolerance-semantics LOCK applied verbatim.
- VCPEvidence dataclass serializable to JSON.

#### Task T-A.3.3 — Flat base detector per spec §5.3

**Files:**
- Create: `swing/patterns/flat_base.py`.
- Create: `tests/patterns/test_flat_base.py`.

- [ ] **Step 1: Write 8+ failing tests** per spec §5.3 7 criteria × pass/fail boundaries + §10.2 worked example:
  - `test_flat_base_passes_all_criteria_returns_geometric_score_1_0` (per §10.2 alternative pass scenario; 22% uptrend).
  - `test_flat_base_rejects_14pct_uptrend_outside_2pct_tolerance_band` (per §10.2 errata correction; 14% < 18% relaxed threshold).
  - `test_flat_base_passes_22pct_uptrend_above_tolerance_band`.
  - `test_flat_base_fails_criterion_3_range_too_narrow_or_wide`.
  - `test_flat_base_fails_criterion_4_slope_too_steep`.
  - `test_flat_base_fails_criterion_5_ATR_too_wide`.
  - `test_flat_base_fails_criterion_6_duration_below_5_weeks`.
  - `test_flat_base_passes_criterion_7_pivot_within_1pct_of_range_top`.
  - `test_flat_base_structural_evidence_dataclass_shape`.

- [ ] **Step 2: Implement** `FlatBaseEvidence` + `detect_flat_base(bars, candidate_window) -> FlatBaseEvidence`.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): flat base detector (T-A.3.3)`.

#### Task T-A.3.4 — Cup-with-handle detector per spec §5.4 + rounded-vs-V LOCK per §10.7

**Files:**
- Create: `swing/patterns/cup_with_handle.py`.
- Create: `tests/patterns/test_cup_with_handle.py`.

- [ ] **Step 1: Write 12+ failing tests** per spec §5.4 8 criteria + §10.3 worked example + §10.7 rounded-vs-V LOCK:
  - `test_cwh_passes_all_criteria_with_rounded_cup_returns_1_0` (per §10.3 + §10.7).
  - `test_cwh_fails_criterion_2_cup_depth_below_12pct`.
  - `test_cwh_fails_criterion_2_cup_depth_above_35pct`.
  - `test_cwh_fails_criterion_3_cup_right_edge_below_95pct_cup_left_edge`.
  - `test_cwh_fails_criterion_4_cup_duration_outside_6_26_weeks`.
  - `test_cwh_fails_criterion_5_handle_depth_above_15pct`.
  - `test_cwh_fails_criterion_5_handle_duration_below_5d`.
  - `test_cwh_fails_criterion_6_handle_low_below_cup_midpoint`.
  - `test_cwh_fails_criterion_8_handle_volume_above_85pct_cup_volume`.
  - `test_cwh_rounded_vs_v_test_centered_on_cup_bottom_date_5_bars_pass` (per §10.7 LOCK).
  - `test_cwh_rounded_vs_v_test_2_bars_rejects_as_v_shape`.
  - `test_cwh_rounded_vs_v_test_3_4_bars_marginal_zone_applies_penalty_0_10`.

- [ ] **Step 2: Implement** `CupWithHandleEvidence` + `detect_cup_with_handle(bars, candidate_window) -> CupWithHandleEvidence` + `_is_rounded_cup(bars, cup_bottom_date, cup_bottom_price) -> tuple[bool, float]` per §D.11 LOCK.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): cup-with-handle detector + §10.7 rounded-vs-V LOCK (T-A.3.4)`.

#### Task T-A.3.5 — `swing/patterns/drift_logging.py` per OQ-9

**Files:**
- Create: `swing/patterns/drift_logging.py`.
- Create: `tests/patterns/test_drift_logging.py`.

- [ ] **Step 1: Write 4 failing tests**: (a) `capture_feature_distribution(detector_class, evidence, universe_context)` returns FeatureDistributionLog dataclass; (b) serializable to JSON; (c) all 5 detectors emit consistent schema; (d) histogram bin count for composite_score matches §5.11 specification.

- [ ] **Step 2: Implement** `FeatureDistributionLog` frozen dataclass per §D.7 + `capture_feature_distribution` helper.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): drift_logging.py per OQ-9 (T-A.3.5)`.

**Watch items:**
- §D.7 + OQ-9 LOCK: JSON column on pattern_evaluations; V2 dedicated table only if Phase 13.5 demands.

#### Task T-A.3.6 — Pipeline `_step_pattern_detect` integration

**Files:**
- Modify: `swing/pipeline/runner.py` (add `_step_pattern_detect` step).
- Create: `tests/pipeline/test_step_pattern_detect.py`.

- [ ] **Step 1: Write 4 failing tests**: (a) step invokes 3 detectors against candidate windows; (b) emits 1 pattern_evaluations row per (ticker, pattern_class) tuple; (c) emits feature_distribution_log_json on each row; (d) zero candidate windows → step succeeds without writes.

- [ ] **Step 2: Implement** `_step_pattern_detect(*, cfg, lease, eval_run_id, conn, ohlcv_cache)` per §A.5 + spec §5.1.3 per-pipeline-run scope. Iterate Stage-2-filtered + RS-rank-filtered candidates; generate windows; invoke each detector; write rows.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): _step_pattern_detect pipeline integration (T-A.3.6)`.

#### Task T-A.3.7 — Selective Codex T2.SB3 retroactive evaluation per spec §5.9 step 4

- [ ] **Step 1: Write failing test** — fire `fire_codex_review_for_silver_row` with `phase='t2_sb3_or_later'` against T2.SB1 corpus exemplars NOW that geometric_score is computable; assert random 15% CONTINUES + high-stakes clause activated.

- [ ] **Step 2: Implement** retroactive evaluation helper at `swing/patterns/labeling.py:retroactive_codex_evaluation_against_corpus()` that recomputes geometric_score for each Claude silver row via T2.SB3 detectors + fires Codex on rows now matching high-stakes predicate.

- [ ] **Step 3: Run test; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): T2.SB3 retroactive Codex evaluation (T-A.3.7)`.

#### Task T-A.3.8 — T2.SB3 E2E + slow test

- [ ] **Step 1: Write fast E2E test** seeding 3 candidate windows (one per pattern class); invoking `_step_pattern_detect`; asserting pattern_evaluations rows + feature_distribution_log_json + composite_score = geometric_score (no template-match yet).

- [ ] **Step 2: Write 1 slow E2E test** against operator's real fixture data — VCP detection on CVGI-like fixture asserts geometric_score in [0.9, 1.0] per §10.1 worked example.

- [ ] **Step 3: Run E2E; verify PASS.**

- [ ] **Step 4: Commit** — `test(phase13): T2.SB3 detector E2E + slow validation (T-A.3.8)`.

#### Task T-A.3.9 — T2.SB3 closer — full suite + ruff sweep

- [ ] **Step 1: Run full fast-test suite + ruff sweep.**

- [ ] **Step 2: Commit** — `test(phase13): T2.SB3 closer — full suite + ruff (T-A.3.9)`.

**Operator-witnessed gate (T2.SB3):**
- S1 (inline): pytest + ruff.
- S2 (CLI): `python -m swing.cli pipeline run` against operator's production; verifies `_step_pattern_detect` lands rows; operator inspects `pattern_evaluations` table for plausible verdicts.
- S3 (cross-check): operator visually compares detector output for a known historical VCP setup (e.g., a prior CVGI-style base) against subjective assessment.

---

### §G.5 Sub-bundle T3.SB2 — Exit auto-fill (5 tasks)

**Goal:** Mirror T3.SB1 architecture for exit form. Per spec §6.2.

**Branch:** `phase13-t3-sb2-exit-auto-fill`. Branches from main HEAD AFTER T2.SB3 merge (per §A.1 dispatch sequence + spec §6.5 — Schwab Trader API consumer merge-conflict avoidance).

**Files in scope:**
- Modify: `swing/web/routes/trades.py` (`exit_form` at line 1229 + `exit_post` at line 1243).
- Create: `swing/trades/exit_auto_fill.py` (mirrors entry_auto_fill).
- Modify: `swing/web/view_models/trades.py` (ExitFormVM fields).
- Modify: `swing/web/templates/trades/exit_form.html.j2`.
- Modify: `swing/integrations/schwab/audit_service.py` (audit `surface='trade_exit'`).
- Create: `tests/trades/test_exit_auto_fill.py`, `tests/web/test_routes/test_exit_form_auto_fill.py`, `tests/integrations/test_schwab_exit_auto_fill_e2e.py` (1 slow E2E).

#### Task T-B.2.1 — `swing/trades/exit_auto_fill.py` — Schwab fetch + value resolution

**Files:**
- Create: `swing/trades/exit_auto_fill.py`.
- Create: `tests/trades/test_exit_auto_fill.py`.

- [ ] **Step 1: Write 5 failing tests**: (a) matching Schwab SELL fill returns AutoFillResult with populated values + `fill_origin='schwab_auto'`; (b) empty Schwab response → empty result + `fill_origin='operator_typed'`; (c) sandbox short-circuits per §A.11; (d) DEGRADED short-circuits with advisory per §A.11; (e) **multi-partial-exit handling** — if Schwab returns multiple SELL fills since `entry_date`, returns list of `ExitAutoFillCandidate` for operator selection (per spec §6.2).

- [ ] **Step 2: Implement** `ExitAutoFillResult` frozen dataclass + `resolve_exit_auto_fill(*, trade_id: int, ticker: str, entry_date: str, cfg, conn) -> ExitAutoFillResult` function per §A.11 4-step Schwab discipline. Query Schwab `account_orders(account_hash, maxResults=...)` for SELL fills matching ticker since `entry_date`. Resolve via `_compute_execution_price(SchwabOrderResponse)` + `_resolve_match_quantity(SchwabOrderResponse)` per post-Phase-12 Sub-bundle 1 mapper at `swing/trades/schwab_reconciliation.py:99/174`. Multi-partial: return `candidates: list[ExitAutoFillCandidate]` (each with date / price / quantity / signature_hash); operator picks one OR enters consolidated value at form submit.

- [ ] **Step 3: Run tests; verify all PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): swing/trades/exit_auto_fill.py — Schwab fetch + value resolution (T-B.2.1)`.

**Acceptance criteria:**
- 5 discriminating tests pass (matching fill / no fills / sandbox / degraded / multi-partial list).
- Schwab discipline 4-step chain followed (apply_overrides + resolve_credentials with `allow_prompt=False` + construct_authenticated_client + sandbox/DEGRADED handling).
- Multi-partial returns list of candidates for operator selection.

**Watch items:**
- §A.11 Schwab integration discipline (forward-binding lesson #10).
- `allow_prompt=False` REQUIRED (CLAUDE.md gotcha "form-render-time prompts would block HTTP handler").

#### Task T-B.2.2 — `exit_form` handler + ExitFormVM extension

**Files:**
- Modify: `swing/web/routes/trades.py:exit_form` at line 1229.
- Modify: `swing/web/view_models/trades.py` (ExitFormVM fields).
- Modify: `swing/web/templates/trades/exit_form.html.j2`.
- Create: `tests/web/test_routes/test_exit_form_auto_fill.py`.

- [ ] **Step 1: Write 6 failing tests**: (a) auto-fill populated when Schwab returns SELL fill; (b) advisory when no match; (c) sandbox short-circuits; (d) hidden audit anchors (`schwab_source_value_json` + `auto_fill_audit_at`) present; (e) **multi-partial-exit list rendering** — when multiple SELL fills returned, template renders each as a selectable candidate (radio button OR distinct form section per candidate); (f) ExitFormVM extends BaseLayoutVM per §A.3.

- [ ] **Step 2: Modify exit_form handler** — call `apply_overrides(cfg)` + `resolve_exit_auto_fill(...)` + `build_exit_form_vm(trade_id, auto_fill=auto_fill)`. Return TemplateResponse.

- [ ] **Step 3: Extend ExitFormVM** — add `auto_fill_*` fields including `auto_fill_candidates: list[ExitAutoFillCandidate]` for multi-partial case. Extend BaseLayoutVM per §A.3.

- [ ] **Step 4: Modify template** — render `auto_fill_*` as DEFAULT input values when single-fill case; render candidate list when multi-partial; render `fill_origin` + `auto_fill_audit_at` as display-only `<span class="muted">`; render hidden inputs for `schwab_source_value_json` + `auto_fill_audit_at`; render `advisory_text` banner; add `hx-headers='{"HX-Request": "true"}'` per forward-binding lesson #11.

- [ ] **Step 5: Run tests; verify all PASS.**

- [ ] **Step 6: Commit** — `feat(phase13): /trades/{id}/exit/form auto-fill integration (T-B.2.2)`.

**Acceptance criteria:**
- 6 discriminating tests pass.
- HTMX gotcha trinity preserved (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted).
- VM extends BaseLayoutVM.
- Multi-partial list renders correctly.

#### Task T-B.2.3 — `exit_post` — fill_origin transition + audit row

**Files:**
- Modify: `swing/web/routes/trades.py:exit_post` at line 1243.
- Modify: `swing/trades/exit.py` (or wherever exit service lives) — extend to consume `schwab_source_value_json` + `auto_fill_audit_at` + flip `fill_origin` per §E.1 state transitions.
- Modify: `swing/data/repos/fills.py` (extend insert/update to persist new audit columns).
- Create: `tests/web/test_routes/test_exit_post_audit_columns.py`.

- [ ] **Step 1: Write 7 failing tests**: (a) persists `schwab_auto` when no operator edits; (b) flips to `schwab_auto_then_operator_corrected` when edited; (c) persists `operator_typed` when no auto-fill; (d) emits audit row with `surface='trade_exit'` (CHECK enum widening v20); (e) soft-warn confirm round-trips hidden anchors via form_values dict per forward-binding lesson #13; (f) `... or None` (NOT `... or ''`) for nullable audit fields (Phase 6 CLAUDE.md gotcha); (g) **multi-partial case** — operator selects one candidate; post handler persists that candidate's values + records other candidates' `signature_hash` in `schwab_source_value_json` for audit history.

- [ ] **Step 2: Modify exit_post** — resolve fill_origin flip via comparing submitted values vs hidden `schwab_source_value_json` anchor; persist all audit columns; emit `schwab_api_calls.surface='trade_exit'` audit row; soft-warn confirm fragment round-trips hidden anchors via form_values dict per forward-binding lesson #13. Multi-partial: operator selects via radio; non-selected candidates preserved in `schwab_source_value_json` envelope.

- [ ] **Step 3: Run tests; verify all PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): exit_post fill_origin transition + audit columns + soft-warn confirm (T-B.2.3)`.

**Acceptance criteria:**
- 7 discriminating tests pass.
- fill_origin transitions correctly: `schwab_auto` → `schwab_auto_then_operator_corrected` on edit; `operator_typed` on no-auto-fill.
- Audit row + audit columns persisted correctly.
- Soft-warn confirm round-trips hidden anchors.
- Multi-partial selection persists chosen candidate + preserves other candidates' signature_hash.

**Watch items:**
- Forward-binding lesson #13 (form-render hidden anchors round-trip).
- Phase 6 `... or None` not `... or ''` for nullable enum-CHECK columns.

#### Task T-B.2.4 — Cassette infrastructure extension for trade_exit surface + slow E2E

**Files:**
- Extend: `tests/integrations/cassettes/schwab/` (NEW cassette files for trade_exit surface).
- Modify: `scripts/record_schwab_cassettes.py` (extend with trade_exit recording targets).
- Create: `tests/integrations/test_schwab_exit_auto_fill_e2e.py` (1 slow E2E).

- [ ] **Step 1: Write slow E2E test**

```python
@pytest.mark.slow
def test_schwab_exit_auto_fill_e2e_cassette_mode():
    # Replay cassette; invoke GET /trades/{id}/exit/form against an open trade fixture;
    # assert response renders with expected auto_fill values from cassette response;
    # assert audit row written with surface='trade_exit' + signature_hash matching cassette.
    ...
```

- [ ] **Step 2: Record cassette (if operator-paired session) or replay** — cassette covers both single-fill + multi-partial response variants.

- [ ] **Step 3: Run E2E; verify PASS.**

- [ ] **Step 4: Commit** — `test(phase13): T3.SB2 trade_exit cassette + slow E2E (T-B.2.4)`.

**Acceptance criteria:**
- Slow E2E passes via cassette replay.
- Cassette sanitization filters cover trade_exit surface (URI + body per §A.10).

#### Task T-B.2.5 — T3.SB2 closer — integration E2E + ruff sweep

**Files:**
- Create: `tests/integration/test_phase13_t3_sb2_exit_auto_fill_e2e.py` (fast E2E).

- [ ] **Step 1: Write fast E2E test** seeding full happy path: open trade fixture + Schwab API mock returning matching SELL fill; invoke GET `/trades/{id}/exit/form` → POST `/trades/{id}/exit`; assert end-to-end fill row created with correct `fill_origin` + audit columns + audit row with `surface='trade_exit'`; assert trade state transitioned correctly (closed if quantity matches; reduced if partial).

- [ ] **Step 2: Run E2E + full fast-test suite + ruff sweep.**

- [ ] **Step 3: Commit** — `test(phase13): T3.SB2 closer — exit auto-fill E2E + ruff sweep (T-B.2.5)`.

**Acceptance criteria:**
- E2E test passes.
- Fast-test baseline maintained + T3.SB2 deltas land (+40-70 fast).
- Ruff 0 E501.

**Operator-witnessed gate (T3.SB2):**
- S1 (inline): pytest + ruff.
- S2 (browser): `/trades/{id}/exit/form` against operator's open position → confirm auto-fill values.
- S3 (browser edit): operator edits pre-populated price; submits; confirms `fill_origin='schwab_auto_then_operator_corrected'`.
- S4 (multi-partial): operator triggers a partial-exit scenario; confirms list-of-candidates rendering + operator selects expected one.
- S5 (DB audit): `schwab_api_calls.surface='trade_exit'` rows present.

**Cross-bundle pin:** `test_fill_origin_enum_complete_after_v20` un-skipped here per §H.

---

### §G.6 Sub-bundle T2.SB4 — Detectors batch 2 (HTF + DBW) (7 tasks)

**Goal:** Ship 2 remaining rule-based geometric detectors per spec §5.5 + §5.6. Composes with T2.SB3 + T2.SB2 substrate. Same drift_logging + composite-scoring discipline as T2.SB3.

**Branch:** `phase13-t2-sb4-detectors-batch2`. Branches from main HEAD AFTER T3.SB2 merge.

**Files in scope:**
- Create: `swing/patterns/high_tight_flag.py`, `swing/patterns/double_bottom_w.py`.
- Modify: `swing/pipeline/runner.py:_step_pattern_detect` (extend to call 5 detectors instead of 3).
- Create: `tests/patterns/test_high_tight_flag.py`, `test_double_bottom_w.py`.
- Create: `tests/integration/test_phase13_t2_sb4_detectors_e2e.py`.

#### Task T-A.4.1 — High-tight flag detector per spec §5.5

- [ ] **Step 1: Write 10+ failing tests** per §5.5 6 criteria + §10.4 worked example + §10.6 tolerance semantics:
  - `test_htf_passes_all_criteria_with_14_8pct_consolidation_width_strict_bound` (per §10.4 alternative pass).
  - `test_htf_rejects_15_6pct_consolidation_width_strict_no_tolerance_bound` (per §10.4 errata; §10.6 LOCK STRICT bound NONE).
  - `test_htf_fails_criterion_2_pole_below_90pct`.
  - `test_htf_fails_criterion_2_pole_duration_outside_4_8_weeks`.
  - `test_htf_fails_criterion_3_consolidation_pullback_above_25pct`.
  - `test_htf_fails_criterion_3_consolidation_duration_outside_3_5_weeks`.
  - `test_htf_fails_criterion_5_volume_drop_below_35pct`.
  - `test_htf_passes_criterion_6_pivot_within_1pct_consolidation_top`.
  - `test_htf_structural_evidence_dataclass_shape`.

- [ ] **Step 2: Implement** `HighTightFlagEvidence` + `detect_high_tight_flag(bars, candidate_window) -> HighTightFlagEvidence`.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): high-tight-flag detector (T-A.4.1)`.

#### Task T-A.4.2 — Double-bottom-W detector per spec §5.6

- [ ] **Step 1: Write 12+ failing tests** per §5.6 8 criteria + undercut bonus + §10.5 worked example:
  - `test_dbw_passes_all_criteria_with_undercut_geometric_score_capped_1_0` (per §10.5).
  - `test_dbw_undercut_increments_geometric_score_by_0_10`.
  - `test_dbw_no_undercut_geometric_score_at_1_0_without_bonus`.
  - `test_dbw_fails_criterion_2_trough_1_drawdown_below_15pct`.
  - `test_dbw_fails_criterion_3_center_peak_retracement_below_50pct`.
  - `test_dbw_fails_criterion_4_trough_2_outside_5pct_of_trough_1`.
  - `test_dbw_passes_criterion_4_with_3pct_undercut_within_5pct_bound`.
  - `test_dbw_fails_criterion_5_duration_outside_5_35d`.
  - `test_dbw_passes_criterion_6_pivot_within_1pct_center_peak`.
  - `test_dbw_optional_criterion_7_volume_rises_increments_evidence`.
  - `test_dbw_stage_4_to_stage_2_transition_satisfies_criterion_1`.
  - `test_dbw_structural_evidence_dataclass_shape`.

- [ ] **Step 2: Implement** `DoubleBottomWEvidence` + `detect_double_bottom_w(bars, candidate_window) -> DoubleBottomWEvidence`.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): double-bottom-W detector + undercut bonus (T-A.4.2)`.

#### Task T-A.4.3 — Pipeline `_step_pattern_detect` extension to 5 detectors

- [ ] **Step 1: Write failing test** asserting `_step_pattern_detect` invokes all 5 detectors per candidate window.
- [ ] **Step 2: Modify** `_step_pattern_detect` to invoke HTF + DBW alongside VCP + FB + CWH.
- [ ] **Step 3: Run test; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): _step_pattern_detect extended to 5 detectors (T-A.4.3)`.

#### Task T-A.4.4 — Drift logging extension for HTF + DBW

- [ ] **Step 1: Write tests** asserting `capture_feature_distribution` correctly emits per-detector feature distributions for HTF + DBW.
- [ ] **Step 2: Extend** `swing/patterns/drift_logging.py` per-detector feature shape registry.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): drift_logging extension for HTF + DBW (T-A.4.4)`.

#### Task T-A.4.5 — Selective Codex T2.SB4 high-stakes clause activation

- [ ] **Step 1: Write test** asserting `fire_codex_review_for_silver_row(phase='t2_sb3_or_later')` now uses ALL 5 detectors' geometric_score (T2.SB4 corpus contains HTF + DBW exemplars; high-stakes clause fires correctly).
- [ ] **Step 2: Verify** retroactive evaluation helper updated to invoke 5 detectors.
- [ ] **Step 3: Run test; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): T2.SB4 Codex high-stakes clause activated for HTF + DBW (T-A.4.5)`.

#### Task T-A.4.6 — T2.SB4 integration E2E

- [ ] **Step 1: Write fast E2E test** seeding 5 candidate windows (one per pattern class); invoking `_step_pattern_detect`; asserting 5 `pattern_evaluations` rows per window per applicable pattern.
- [ ] **Step 2: Run E2E; verify PASS.**
- [ ] **Step 3: Commit** — `test(phase13): T2.SB4 integration E2E (T-A.4.6)`.

#### Task T-A.4.7 — T2.SB4 closer — full suite + ruff

- [ ] **Step 1: Run full fast-test suite + ruff sweep.**
- [ ] **Step 2: Commit** — `test(phase13): T2.SB4 closer (T-A.4.7)`.

**Operator-witnessed gate (T2.SB4):**
- S1 (inline): pytest + ruff.
- S2 (CLI): `python -m swing.cli pipeline run`; verifies 5-detector landed rows.
- S3 (cross-check): operator inspects a known historical HTF and DBW setup; verifies detector verdicts match subjective assessment.

---

### §G.7 Sub-bundle T2.SB5 — Template matching (DTW + composite scoring) (6 tasks)

**Goal:** Ship DTW with Sakoe-Chiba band template matching layer per spec §5.7 + OQ-4. Composite scoring formula per spec §5.8. Benchmark gate: 120s/run on operator's hardware.

**Branch:** `phase13-t2-sb5-template-matching`. Branches from main HEAD AFTER T2.SB4 merge.

**Files in scope:**
- Create: `swing/patterns/template_matching.py`, `swing/patterns/composite.py`.
- Modify: `swing/pipeline/runner.py:_step_pattern_detect` (compose template-match score into composite).
- Create: `tests/patterns/test_template_matching.py`, `test_composite.py`.
- Create: `tests/patterns/test_template_matching_benchmark.py` (pytest-benchmark; 120s gate).

#### Task T-A.5.1 — DTW core + Sakoe-Chiba band per spec §5.7 + OQ-4

- [ ] **Step 1: Write 6 failing tests**: (a) DTW distance between two identical series = 0.0; (b) DTW distance between known-similar series matches known-good fixture; (c) Sakoe-Chiba band with `window=0.1 × series_length` prevents over-warping (regression vs unconstrained DTW); (d) similarity_score normalization 0..1 (1=identical); (e) edge case: empty exemplar corpus returns empty list; (f) min-max normalization applied per v2 brief §7 LOCK.
- [ ] **Step 2: Implement** `_dtw_distance(a, b, *, sakoe_chiba_window_ratio=0.1) -> float` pure-Python (NO scipy). NumPy-vectorized inner loop.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): DTW core with Sakoe-Chiba band (T-A.5.1)`.

#### Task T-A.5.2 — `match_forward` + `match_reverse` retrieval per spec §5.7

- [ ] **Step 1: Write 6 failing tests**: (a) `match_forward(candidate_window, exemplar_corpus, top_k=3)` returns 3 hits ordered by similarity; (b) per-pattern filtering (VCP candidate compares ONLY against VCP exemplars per §D.5 pruning #1); (c) geometric_score pre-gate filter (DTW only fires for `geometric_score >= 0.4`); (d) max-windows-per-ticker = 3; (e) exemplar corpus subsampling at 100+ rows (50 highest-quality_grade); (f) `match_reverse(exemplar, candidate_corpus, top_k=10)` returns inverse direction.
- [ ] **Step 2: Implement** both functions + `TemplateMatchHit` frozen dataclass per §D.5.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): template matching retrieval (T-A.5.2)`.

#### Task T-A.5.3 — Composite scoring per spec §5.8

- [ ] **Step 1: Write 4 failing tests**: (a) `compute_composite_score(geometric=0.8, template_match=0.7)` = `min(1.0, 0.60 × 0.8 + 0.40 × 0.7)` = 0.76; (b) double-bottom-W undercut bonus → geometric=1.10 → composite capped at 1.0; (c) template_match_score=None → composite = geometric_score; (d) calibration LOCK: composite_score is 0..1 evidence-strength, NOT probability.
- [ ] **Step 2: Implement** `compute_composite_score(geometric: float, template_match: float | None) -> float` per §D.4.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): composite scoring (T-A.5.3)`.

#### Task T-A.5.4 — Pipeline `_step_pattern_detect` integration with template matching

- [ ] **Step 1: Write failing tests** asserting `_step_pattern_detect` now fires `match_forward` for each detector verdict + persists `template_match_score` + `template_match_nearest_exemplar_ids_json` + recomputes `composite_score` on `pattern_evaluations` rows.
- [ ] **Step 2: Modify** `_step_pattern_detect` to invoke template matching after geometric detection.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): _step_pattern_detect template matching integration (T-A.5.4)`.

#### Task T-A.5.5 — pytest-benchmark 120s gate per OQ-4

- [ ] **Step 1: Write benchmark test**

```python
@pytest.mark.benchmark
def test_dtw_full_pipeline_completes_within_120s_on_baseline_hardware(benchmark, seeded_universe_250_tickers_50_exemplars_per_pattern):
    # Per spec §5.7: 250-name candidate universe × 5 patterns × 50 exemplars = ~62,500 DTW pair-computations.
    # Assert wall-clock < 120s on ~3GHz CPU baseline.
    result = benchmark(lambda: _step_pattern_detect_full_dtw_pass(...))
    assert benchmark.stats['mean'] < 120.0, f"DTW pass exceeded 120s gate: {benchmark.stats['mean']:.2f}s"
```

- [ ] **Step 2: Run benchmark; verify PASS** (if FAIL, escalate to OQ-4 V2 fallback SBD).
- [ ] **Step 3: Commit** — `test(phase13): T2.SB5 pytest-benchmark 120s gate (T-A.5.5)`.

**Watch items:**
- §D.5 pruning LOCK (per-pattern filtering + geometric_score pre-gate + max-windows-per-ticker + exemplar corpus subsampling) MUST be in place before benchmark fires.
- OQ-4 V2 fallback: if benchmark fails, T2.SB5 adopts SBD (Shape-Based Distance) per OQ-4 V2 disposition.

#### Task T-A.5.6 — T2.SB5 closer — integration E2E + ruff sweep

- [ ] **Step 1: Write fast E2E test** seeding 5 pattern_evaluations rows + 25 exemplars; invoking full pipeline; asserting composite_score correctly composed from geometric + template_match per §5.8.
- [ ] **Step 2: Run full fast-test suite + ruff sweep.**
- [ ] **Step 3: Commit** — `test(phase13): T2.SB5 closer — template matching E2E + ruff (T-A.5.6)`.

**Operator-witnessed gate (T2.SB5):**
- S1 (inline): pytest + ruff.
- S2 (benchmark): operator runs pytest-benchmark on their hardware; verifies 120s gate.
- S3 (CLI): `python -m swing.cli pipeline run`; verifies template_match_score + composite_score populated on pattern_evaluations rows.
- S4 (cross-check): operator selects a known historical VCP and verifies `match_forward` returns plausible historical bases as top-3 hits.

**Cross-bundle pin:** `test_pattern_exemplars_schema_shape_invariant` un-skipped here per §H.

---

### §G.8 Sub-bundle T3.SB3 — Review auto-fill (5 tasks)

**Goal:** Pre-populate review form with priors from previous reviews + MFE/MAE from candles per spec §6.3. Period review section text auto-fill. Per OQ-8: OhlcvCache substrate (post-T1.SB0).

**Branch:** `phase13-t3-sb3-review-auto-fill`. Branches from main HEAD AFTER T2.SB5 merge (per §A.1 + spec §6.5 — consumes OhlcvCache patterns + candidate-window primitives).

**Files in scope:**
- Modify: `swing/web/routes/trades.py` (`review_form_page` at line 1508 + POST handler).
- Create: `swing/trades/review_auto_fill.py`.
- Modify: `swing/trades/review.py` (priors helpers per §E.4).
- Modify: `swing/web/templates/trades/review_form.html.j2`.
- Modify: `swing/web/view_models/trades.py` (ReviewFormVM extension).
- Create: `tests/trades/test_review_auto_fill.py`, `tests/web/test_routes/test_review_form_auto_fill.py`.

#### Task T-B.3.1 — Priors helpers per §E.4

- [ ] **Step 1: Write 4 failing tests**: (a) `get_priors_for_ticker(conn, ticker, n=5)` returns ReviewPriors with mistake_tag_candidates + process_grade_baseline + lesson_learned_candidates; (b) edge case: zero prior reviews returns empty priors (no advisory text required; per §A.16 graceful at n=0); (c) numeric grade encoding A=4..F=0 for process_grade_baseline; (d) lesson_learned_candidates ordered most-recent-first.
- [ ] **Step 2: Implement** `get_priors_for_ticker` + `ReviewPriors` frozen dataclass per §E.4.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): review priors helpers (T-B.3.1)`.

#### Task T-B.3.2 — MFE/MAE from OhlcvCache per OQ-8

- [ ] **Step 1: Write 4 failing tests**: (a) when `daily_management_records.open_MFE_R_to_date` exists for trade, prefer Phase 8 source; (b) when Phase 8 record missing, fall through to OhlcvCache daily-bar synthesis; (c) `mfe_pct = max(highs since entry) / entry_price - 1` correct; (d) `mae_pct = min(lows since entry) / entry_price - 1` correct.
- [ ] **Step 2: Implement** `compute_mfe_mae_from_ohlcv_cache(conn, trade, ohlcv_cache) -> tuple[float, float]` with Phase 8 source-ladder per §E.3.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): MFE/MAE from OhlcvCache for review auto-fill (T-B.3.2)`.

#### Task T-B.3.3 — `review_form_page` handler + ReviewFormVM extension

- [ ] **Step 1: Write 6 failing tests**: (a) form renders with priors populated as DEFAULT input values; (b) MFE/MAE auto-populated; (c) hidden `auto_populated_field_keys_json` field present; (d) sessionanchor `last_completed_session(now())` aligned; (e) VM extends BaseLayoutVM; (f) form renders gracefully at zero priors.
- [ ] **Step 2: Modify** `review_form_page` to invoke priors helpers + MFE/MAE helper; populate ReviewFormVM fields.
- [ ] **Step 3: Extend ReviewFormVM** + render template with default values.
- [ ] **Step 4: Run tests; verify PASS.**
- [ ] **Step 5: Commit** — `feat(phase13): /reviews/.../complete auto-fill (T-B.3.3)`.

#### Task T-B.3.4 — `review_post` — persist `auto_populated_field_keys_json` + period review section text

- [ ] **Step 1: Write 5 failing tests**: (a) review POST persists `auto_populated_field_keys_json` correctly; (b) period_lessons_summary auto-extracted from `review_log` rows in prior period; (c) most_common_mistake_tags aggregate over period; (d) cohort_health_summary deltas vs prior period; (e) `... or None` (NOT `... or ''`) for nullable JSON column.
- [ ] **Step 2: Modify review_post** to persist `auto_populated_field_keys_json`. Implement period review helpers per §E.5: `get_period_lessons_summary`, `get_period_mistake_tag_aggregate`, `get_period_cohort_health_deltas`.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): review_post persist auto_populated_field_keys_json + period helpers (T-B.3.4)`.

**Watch items:**
- Phase 6 `... or None` not `... or ''` for nullable enum-CHECK columns.

#### Task T-B.3.5 — T3.SB3 closer — integration E2E + ruff sweep

- [ ] **Step 1: Write fast E2E test** seeding trade + 5 prior reviews + open-trade OhlcvCache fixture; invoke GET /reviews/{id}/complete; assert form renders with priors + MFE/MAE; POST submit; assert `auto_populated_field_keys_json` persisted.
- [ ] **Step 2: Run full fast-test suite + ruff sweep.**
- [ ] **Step 3: Commit** — `test(phase13): T3.SB3 closer — review auto-fill E2E + ruff (T-B.3.5)`.

**Operator-witnessed gate (T3.SB3):**
- S1 (inline): pytest + ruff.
- S2 (browser): `/reviews/{id}/complete` for an open trade → confirm MFE/MAE values match operator's expectation; priors populated.
- S3 (round-trip): operator submits review; confirms `auto_populated_field_keys_json` audit trail persisted.
- S4 (period review): operator triggers period review; confirms section text auto-populated.

---

### §G.9 Sub-bundle T2.SB6 — Closed-loop surface + Theme 1 annotated charts (7 tasks)

**Goal:** Ship `/patterns/{candidate_id}/review` review form + `/patterns/queue` active-learning + `/metrics/pattern-outcomes` 9th metric tile + Theme 2 annotated chart deliverable + Theme 1 chart surfaces (watchlist row + hyp-rec detail + position detail + market weather) consuming `chart_renders` cache.

**Branch:** `phase13-t2-sb6-closed-loop-surface`. Branches from main HEAD AFTER T3.SB3 merge.

**Files in scope:**
- Create: `swing/web/charts.py` (matplotlib SVG-inline renderers per §C.1).
- Create: `swing/patterns/active_learning.py`.
- Modify: `swing/web/routes/patterns.py` (add `/patterns/{candidate_id}/review` GET + POST; `/patterns/queue` GET).
- Modify: `swing/web/routes/metrics.py` (add `/metrics/pattern-outcomes` 9th tile).
- Modify: `swing/web/routes/dashboard.py` (extend DashboardVM with market weather chart field; add `POST /dashboard/weather-chart/refresh`).
- Modify: `swing/pipeline/runner.py:_step_charts` (write `chart_renders` cache rows for watchlist + hyp-rec + position + market weather + theme2-annotated surfaces).
- Modify: `swing/web/view_models/dashboard.py`, `swing/web/view_models/watchlist.py`, `swing/web/view_models/recommendations.py` (consume chart_renders cache).
- Create: `swing/web/view_models/patterns/review_form.py`, `queue.py`, `outcomes_card.py`, `annotated_chart.py`.
- Create: `swing/web/templates/patterns/review.html.j2`, `queue.html.j2`, `outcomes.html.j2`, `annotated_chart_partial.html.j2`.
- Create: `tests/web/test_charts.py`, `tests/web/test_routes/test_patterns_review.py`, `test_patterns_queue.py`, `test_metrics_pattern_outcomes.py`.

#### Task T-A.6.1 — `swing/web/charts.py` SVG-inline renderer per §C.1 LOCK

- [ ] **Step 1: Write 10+ failing tests** covering 5 chart surfaces × known-good fixture bytes parity:
  - `test_render_watchlist_thumbnail_svg_returns_valid_svg_bytes` (200x100 size; MA lines; volume).
  - `test_render_hyprec_detail_svg_with_pattern_evaluation_renders_pattern_boundaries`.
  - `test_render_position_detail_svg_with_fills_renders_fill_markers`.
  - `test_render_market_weather_svg_renders_trend_template_badge`.
  - `test_render_theme2_annotated_svg_per_5_patterns` (5 separate tests covering VCP + flat base + CWH + HTF + DBW annotation shapes).
  - `test_charts_ascii_only_text_no_mathtext_metacharacters` (per §A.9 + §C.1 LOCK).
  - `test_charts_no_dollar_or_caret_or_underscore_in_titles` (defense-in-depth per CLAUDE.md gotcha).

- [ ] **Step 2: Implement** all 5 renderer functions per §C.1 public surface. Use matplotlib Figure + savefig to BytesIO with format='svg'. NO mathtext. `parse_math=False` on `fig.suptitle` defense-in-depth.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): swing/web/charts.py — SVG-inline renderers (T-A.6.1)`.

**Watch items:**
- §A.9 + §C.1 matplotlib mathtext LOCK — operator-witnessed browser verification BINDING per Phase 10 §A.10 inheritance.

#### Task T-A.6.2 — `chart_renders` cache write-through integration

- [ ] **Step 1: Write 5 failing tests** covering cache architecture per §C.2:
  - `test_chart_renders_run_bound_cache_one_row_per_ticker_surface_run`.
  - `test_chart_renders_position_detail_cache_no_pipeline_run_id_unique_per_ticker`.
  - `test_chart_renders_theme2_annotated_cache_unique_per_ticker_surface_run_pattern_class`.
  - `test_chart_renders_session_anchor_read_write_alignment_no_false_miss` (per §A.13 LOCK + Phase 8 `cfacbc5` precedent — round-trip test pattern).
  - `test_chart_renders_cache_invalidation_atomic_delete_then_insert` (per §A.15 no INSERT OR REPLACE).

- [ ] **Step 2: Modify `_step_charts`** to write through `chart_renders` cache for each surface. Wrap atomic refresh in `BEGIN IMMEDIATE` / `COMMIT`.

- [ ] **Step 3: Modify `swing/web/view_models/`** consumers to READ chart_renders cache (`get_cached_chart_svg(conn, ticker, surface, pipeline_run_id=None, pattern_class=None) -> bytes | None`).

- [ ] **Step 4: Run tests; verify PASS.**

- [ ] **Step 5: Commit** — `feat(phase13): chart_renders cache write-through + session-anchor alignment (T-A.6.2)`.

#### Task T-A.6.3 — `/patterns/{candidate_id}/review` review form

- [ ] **Step 1: Write 10+ failing tests** covering v2 brief §9.2 8-item checklist + §9.3 6-decision enum:
  - `test_get_patterns_review_renders_8_item_checklist_per_v2_brief_92`.
  - `test_get_patterns_review_renders_geometric_score_breakdown_per_rule_component`.
  - `test_get_patterns_review_renders_top_3_template_match_thumbnails`.
  - `test_get_patterns_review_renders_trend_template_badge`.
  - `test_get_patterns_review_renders_rs_rank_badge`.
  - `test_get_patterns_review_renders_volume_profile_sparkline`.
  - `test_get_patterns_review_renders_uncertainty_reason_per_criterion`.
  - `test_get_patterns_review_renders_outcome_distribution_from_prior_similar_candidates`.
  - `test_post_patterns_review_decision_confirm_persists_organic_trade_history_if_trade_opened`.
  - `test_post_patterns_review_decision_confirm_persists_closed_loop_review_if_no_trade_opened`.
  - `test_post_patterns_review_decision_watch_persists_watch`.
  - `test_post_patterns_review_decision_reject_persists_rejected`.
  - `test_post_patterns_review_decision_relabel_with_corrected_class_persists_relabeled` (cross-column CHECK invariant #1 enforced).
  - `test_post_patterns_review_decision_pattern_present_outside_window_emits_window_shift_row`.
  - `test_post_patterns_review_decision_multiple_overlapping_patterns_emits_multi_exemplar_rows`.
  - `test_patterns_review_vm_extends_base_layout_vm`.

- [ ] **Step 2: Implement** route handlers + PatternReviewFormVM extending BaseLayoutVM + Jinja template + integration with charts.py annotated renderer.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): /patterns/{id}/review closed-loop form (T-A.6.3)`.

**Watch items:**
- §3.1 source-vs-decision matrix CHECK invariant enforced via dataclass validator.
- HTMX gotcha trinity for review POST: HX-Request + HX-Redirect to `/patterns/queue` + target route registered.
- Cross-column CHECK invariant #1 (relabel-vs-non-relabel coherence) enforced at POST.

#### Task T-A.6.4 — `/patterns/queue` active-learning prioritization

- [ ] **Step 1: Write 5 failing tests**: (a) `prioritize_candidates(conn, top_k=20)` returns candidates ordered by priority per spec §5.10 4-criterion ranking; (b) borderline geometric_score (|score - 0.5| < 0.1) included; (c) rule/template disagreement included; (d) underrepresented regimes; (e) failed-rule near-misses.
- [ ] **Step 2: Implement** `swing/patterns/active_learning.py:prioritize_candidates` + queue VM + template.
- [ ] **Step 3: Run tests; verify PASS.**
- [ ] **Step 4: Commit** — `feat(phase13): /patterns/queue active-learning prioritization (T-A.6.4)`.

#### Task T-A.6.5 — `/metrics/pattern-outcomes` 9th metric tile per OQ-10

- [ ] **Step 1: Write 6 failing tests** per Phase 10 metrics architecture:
  - `test_metrics_pattern_outcomes_renders_per_pattern_class_outcome_distribution`.
  - `test_metrics_pattern_outcomes_honesty_wilson_ci_at_n_geq_5`.
  - `test_metrics_pattern_outcomes_suppressed_at_n_lt_5_per_phase10_5_1`.
  - `test_metrics_pattern_outcomes_renders_x_triggered_y_reached_1R_z_hit_stop`.
  - `test_metrics_pattern_outcomes_vm_extends_base_layout_vm`.
  - `test_metrics_pattern_outcomes_composes_with_phase10_cohort_architecture`.

- [ ] **Step 2: Implement** route + VM consuming Phase 10 `swing/metrics/cohort.py` + `honesty.py` + Phase 10 `BaseLayoutVM`. Compose with `pattern_evaluations` join to `trades.candidate_id` for outcome computation.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): /metrics/pattern-outcomes 9th metric tile (T-A.6.5)`.

#### Task T-A.6.6 — Theme 1 chart surface integration + dashboard market weather

- [ ] **Step 1: Write 5 failing tests**: (a) DashboardVM populates `dashboard_weather_chart_svg_bytes`; (b) watchlist row VM includes inline thumbnail SVG bytes per ticker; (c) hyp-rec detail VM includes 800x500 SVG; (d) position detail VM includes 800x500 SVG with fill markers; (e) `POST /dashboard/weather-chart/refresh` invalidates cache + regenerates.

- [ ] **Step 2: Modify** DashboardVM + WatchlistVM + RecommendationsVM (hyp-rec) + TradesVM (position detail) to populate chart SVG bytes from `chart_renders` cache. Extend dashboard template to render market weather at TOP per §C.3.

- [ ] **Step 3: Implement `POST /dashboard/weather-chart/refresh`** route handler.

- [ ] **Step 4: Run tests; verify PASS.**

- [ ] **Step 5: Commit** — `feat(phase13): Theme 1 chart surfaces + dashboard market weather (T-A.6.6)`.

#### Task T-A.6.7 — T2.SB6 closer — integration E2E + ruff sweep

- [ ] **Step 1: Write fast E2E test** seeding full happy path: pipeline run → pattern_evaluations rows → chart_renders cache → /patterns/queue lists → /patterns/{id}/review renders + POST persists → /metrics/pattern-outcomes renders cohort outcome distributions.

- [ ] **Step 2: Run full fast-test suite + ruff sweep.**

- [ ] **Step 3: Commit** — `test(phase13): T2.SB6 closer — closed-loop E2E + ruff (T-A.6.7)`.

**Operator-witnessed gate (T2.SB6):**
- S1 (inline): pytest + ruff.
- S2 (browser): `/dashboard` → confirm market weather chart at top.
- S3 (browser): `/patterns/queue` → confirm active-learning prioritization.
- S4 (browser): `/patterns/{id}/review` for a real candidate → confirm 8-item checklist renders + decision form submits.
- S5 (browser): `/metrics/pattern-outcomes` → confirm per-pattern-class outcome distributions.
- S6 (browser): hyp-rec detail page → confirm annotated chart renders with pattern boundaries.
- S7 (browser): position detail page → confirm fill markers + current stop line.
- S8 (visual): operator browser-DevTools verification of SVG renderability (no mathtext mishaps per §A.9 LOCK).

**Cross-bundle pin:** Theme 1 + Theme 2 cross-bundle pin CLOSES here. Shared annotated chart renderer verifies all 5 V1 patterns render correctly with structural_evidence_json.

---

### §G.10 Sub-bundle T4.SB — Usability triage + Q4 close-tracking flag (7 tasks)

**Goal:** Ship Q4 close-tracking flag per spec §7.2 D-Q4.1..D-Q4.7. T4.SB ships Q4 ONLY per §F.1 LOCK + operator-pre-writing-plans elicitation (no additional usability items confirmed empty at 2026-05-18 PM).

**Branch:** `phase13-t4-sb-usability-triage-q4`. Branches from main HEAD AFTER T2.SB6 merge.

**Files in scope:**
- Create: `swing/trades/watchlist_close_track.py` (service with reject-caller-held-tx contract per §F.4).
- Modify: `swing/web/routes/watchlist.py` (add `POST /watchlist/{ticker}/flag` + `POST /watchlist/{ticker}/unflag`).
- Modify: `swing/web/templates/watchlist.html.j2` (add badge + sort logic).
- Modify: `swing/web/view_models/watchlist.py` (add flag fields).
- Modify: `swing/cli.py` (add `swing watchlist flag` + `swing watchlist unflag`).
- Modify: `swing/trades/entry.py` (auto-clear flag on position-open per D-Q4.3).
- Create: `tests/trades/test_watchlist_close_track.py`, `tests/web/test_routes/test_watchlist_flag.py`, `tests/cli/test_watchlist_flag_cli.py`.

#### Task T-D.1 — `swing/trades/watchlist_close_track.py` service per §F.4 transactional discipline

- [ ] **Step 1: Write 8+ failing tests** per §A.12 transactional discipline:
  - `test_set_flag_owns_begin_immediate_rejects_caller_held_tx`.
  - `test_set_flag_emits_audit_row_with_event_type_set`.
  - `test_set_flag_re_flagging_cleared_ticker_inserts_new_row_no_unique_collision` (per Codex R1 M#9 closure).
  - `test_clear_flag_with_source_web_emits_audit_row`.
  - `test_clear_flag_with_source_cli_emits_audit_row`.
  - `test_auto_clear_on_position_open_caller_tx_contract` (caller-tx; consumed in trade entry outer with conn block per §F.4).
  - `test_auto_clear_on_position_open_audit_row_with_cleared_reason_auto_cleared_on_position_open`.
  - `test_sandbox_short_circuit_lives_in_inner_function_not_outer` (per Phase 12 C.C lesson #2).
  - `test_select_first_idempotency_no_op_on_already_cleared_flag` (per Phase 12 C.C lesson #3).
  - `test_audit_trail_append_only_no_update_in_place` (per Phase 12 C.A `reconciliation_corrections` precedent).

- [ ] **Step 2: Implement** `swing/trades/watchlist_close_track.py`:

```python
def set_flag(conn, *, ticker: str, source: Literal['web', 'cli'], reason: str | None = None) -> int:
    """Reject-caller-held-tx; owns BEGIN IMMEDIATE / COMMIT / ROLLBACK."""
    if conn.in_transaction:
        raise CallerHeldTransactionError(...)
    conn.execute("BEGIN IMMEDIATE")
    try:
        # SELECT first; idempotent if already active flag.
        existing = conn.execute("SELECT id FROM watchlist_close_track_flags WHERE ticker=? AND cleared_at IS NULL", (ticker,)).fetchone()
        if existing: 
            conn.execute("COMMIT")
            return existing[0]
        # INSERT new flag + audit row.
        ...
        conn.execute("COMMIT")
    except:
        conn.execute("ROLLBACK"); raise

def clear_flag(conn, *, ticker: str, source: Literal['web', 'cli'], reason: str | None = None) -> bool:
    """Reject-caller-held-tx; UPDATEs flag row + INSERTs audit event row."""
    ...

def auto_clear_on_position_open(conn, ticker: str) -> bool:
    """Caller-tx contract — consumed from inside the trade-entry service's outer with conn: block.
    DOES NOT issue BEGIN/COMMIT itself. Per §F.4 transactional LOCK + §A.12."""
    # SELECT-first idempotency
    ...
```

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): watchlist_close_track.py — Q4 service (T-D.1)`.

**Watch items:**
- §A.12 transactional discipline LOCK (forward-binding lessons #4 + #5 + #6).
- §F.4 auto-clear caller-tx contract.

#### Task T-D.2 — Web routes — `POST /watchlist/{ticker}/flag` + `POST /watchlist/{ticker}/unflag`

- [ ] **Step 1: Write 6 failing tests**: (a) POST flag sets flag + emits audit row; (b) POST flag with operator-supplied reason text persists reason; (c) POST unflag clears + emits audit; (d) HX-Request propagation + HX-Redirect target registered; (e) HTMX gotcha trinity preserved; (f) returns 204 + HX-Redirect (NOT 303 swap).

- [ ] **Step 2: Implement** route handlers in `swing/web/routes/watchlist.py`. Both routes consume `set_flag` / `clear_flag` service functions (NOT caller-tx; service owns own tx).

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): Q4 web toggle routes (T-D.2)`.

**Watch items:**
- HTMX gotcha trinity (forward-binding lesson #11).

#### Task T-D.3 — CLI subcommands — `swing watchlist flag` + `swing watchlist unflag`

- [ ] **Step 1: Write 4 failing tests**: (a) CLI flag persists flag + emits audit `surface='cli'`; (b) CLI unflag clears; (c) idempotent re-flag with existing active flag (per §F.4 SELECT-first idempotency); (d) ASCII-only output per §A.8.

- [ ] **Step 2: Implement** `swing watchlist` click group + flag/unflag subcommands. Both consume `set_flag` / `clear_flag` service functions.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): Q4 CLI subcommands (T-D.3)`.

#### Task T-D.4 — Watchlist VM extension + badge + sort priority

- [ ] **Step 1: Write 5 failing tests**: (a) WatchlistVM populates `flagged_close_track_tickers` + `flagged_close_track_count`; (b) flagged rows appear FIRST in watchlist output; (c) ASCII badge `[*]` rendered inline on flagged row; (d) flagged-but-not-in-algorithm sub-badge `(operator-flagged; algo dropped)` rendered; (e) UNION query correctly assembles pipeline_algo + flagged_not_in_algo.

- [ ] **Step 2: Modify** `swing/web/view_models/watchlist.py` + template per §F.3.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): Q4 watchlist VM + badge + sort priority (T-D.4)`.

**Watch items:**
- §F.3 ASCII-only badge per §A.8 Windows cp1252 stdout safety.
- §A.16 graceful at zero flagged tickers (no layout shift).

#### Task T-D.5 — Auto-clear on position-open integration

- [ ] **Step 1: Write 3 failing tests**: (a) opening a position in flagged ticker auto-clears flag inside SAME transaction; (b) trade entry rollback rolls back flag clear; (c) audit row with `cleared_reason='auto_cleared_on_position_open'` written atomically.

- [ ] **Step 2: Modify** `swing/trades/entry.py` (or wherever the trade entry service lives) to invoke `auto_clear_on_position_open(conn, ticker)` inside its outer `with conn:` block — caller-tx contract per §F.4.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `feat(phase13): Q4 auto-clear on position-open integration (T-D.5)`.

**Watch items:**
- §F.4 caller-tx contract — `auto_clear_on_position_open` MUST NOT issue BEGIN/COMMIT; it consumes the trade-entry service's transaction.

#### Task T-D.6 — Session-anchor + base-layout VM banner discriminating round-trip test

- [ ] **Step 1: Write 2 failing tests**: (a) per §A.13 session-anchor read/write alignment: write flag at known timestamp; read via UI predicate; assert visibility; (b) per §A.3 forward-binding lesson #12: every Phase 13 VM extending `base.html.j2` populates banner fields (specifically WatchlistVM after T-D.4 extension).

- [ ] **Step 2: Verify** alignment + populate fields.

- [ ] **Step 3: Run tests; verify PASS.**

- [ ] **Step 4: Commit** — `test(phase13): Q4 session-anchor + base-layout banner alignment (T-D.6)`.

#### Task T-D.7 — T4.SB closer — integration E2E + ruff sweep + Phase 13 close

- [ ] **Step 1: Write Phase 13 cumulative E2E test** seeding: full pipeline run with pattern detection → operator labels exemplars → flags watchlist ticker → opens position → confirms auto-clear → reviews trade → closes Phase 13 arc.

- [ ] **Step 2: Run full fast-test suite + ruff sweep.**

- [ ] **Step 3: Commit** — `test(phase13): T4.SB closer + Phase 13 cumulative E2E + ruff (T-D.7)`.

**Operator-witnessed gate (T4.SB):**
- S1 (inline): pytest + ruff.
- S2 (web): operator clicks flag toggle on PTEN watchlist row; confirms `[*]` badge appears.
- S3 (web): operator unflags; confirms badge gone + sort-priority returns to algorithm order.
- S4 (CLI): operator runs `swing watchlist flag PTEN --close-track --reason "post-pivot breakout"`; confirms flag set.
- S5 (auto-clear): operator opens position on flagged ticker; confirms flag auto-cleared; audit row present.
- S6 (cleared persistence): operator re-flags previously-cleared ticker; confirms new row inserted (per Codex R1 M#9 partial unique index).
- S7 (Phase 13 close): operator runs full pipeline; confirms all 4 themes operational; reviews `docs/phase3e-todo.md` Phase 13 closer entry.

**Cross-bundle pin:** All Phase 13 cross-bundle pins (per §H) un-skipped + verified passing.

---

## §H — Cross-bundle dependencies + un-skip pin schedule

### §H.1 Dispatch sequence + dependency graph

```
main HEAD
    │
    ▼
T1.SB0 ────────────────────────────────────── (4 tasks; OhlcvCache wiring)
    │
    ▼
T2.SB1 ╳══════════════════════════════ T3.SB1 (concurrent off T2.SB1's first-commit SHA per OQ-12 Option E)
    │       (T2.SB1: 8 tasks)            (T3.SB1: 6 tasks)
    │       (operator-paired pause)
    │
    ▼
T2.SB1 merges first; T3.SB1 merges second.
    │
    ▼
T2.SB2 ────────────────────────────────────── (6 tasks; foundation primitives)
    │
    ▼
T2.SB3 ────────────────────────────────────── (9 tasks; detectors batch 1)
    │
    ▼
T3.SB2 ────────────────────────────────────── (5 tasks; exit auto-fill — branches from main post-T2.SB3 merge)
    │
    ▼
T2.SB4 ────────────────────────────────────── (7 tasks; detectors batch 2)
    │
    ▼
T2.SB5 ────────────────────────────────────── (6 tasks; template matching + 120s benchmark gate)
    │
    ▼
T3.SB3 ────────────────────────────────────── (5 tasks; review auto-fill — consumes OhlcvCache patterns)
    │
    ▼
T2.SB6 ────────────────────────────────────── (7 tasks; closed-loop surface + Theme 1 annotated charts)
    │
    ▼
T4.SB ────────────────────────────────────── (7 tasks; usability triage + Q4)
    │
    ▼
Phase 13 CLOSED
```

Total: **11 sub-bundles, 70 tasks**.

One concurrent dispatch point: T2.SB1 ∥ T3.SB1 (per OQ-12 Option E). All other transitions are serial.

### §H.2 OQ-12 Option E coordination at T2.SB1 + T3.SB1 fork

Per §B.2 + OQ-12 BINDING:

1. T2.SB1 worktree branches from main HEAD at dispatch time.
2. T2.SB1 task T-A.1.1 commits the migration file + Python-side atomic landing (per §B.4 roster). RECORD first-commit SHA explicitly.
3. T3.SB1 dispatch brief enumerates T2.SB1's first-commit SHA as the branch base. T3.SB1 worktree branches FROM that SHA (NOT from main HEAD).
4. Both sub-bundles proceed in parallel worktrees.
5. **Merge ordering**: T2.SB1 merges first (closes v20 atomic landing); T3.SB1 merges second (consumer-side widening already lands consistent schema).
6. Cross-bundle pin: `test_schema_version_v20_invariant` planted at T-A.1.1 un-skips at T3.SB1 merge.

### §H.3 Cross-bundle pin schedule (per Phase 10 T-A.7 + T-E.3 + Phase 12 C.A T-A.7 precedent)

| Pin name | Planted at | Un-skipped at | Verifies |
|---|---|---|---|
| `test_ohlcv_cache_get_or_fetch_invariant` | T1.SB0 T-T1.SB0.4 | T2.SB2 + T2.SB3 + T3.SB3 | OhlcvCache.get_or_fetch surface stable across consumers |
| `test_schema_version_v20_invariant` | T2.SB1 T-A.1.1 | T3.SB1 merge | v20 landing atomic + cross-bundle visible |
| `test_pattern_exemplars_schema_shape_invariant` | T2.SB1 T-A.1.1 | T2.SB3 + T2.SB5 | 5 cross-column CHECK invariants enforced by both schema + Python |
| `test_fill_origin_enum_complete_after_v20` | T3.SB1 T-B.1.2 | T3.SB2 | fill_origin transitions consumed correctly by exit-side |
| `test_foundation_primitives_consumed_by_detectors_invariant` | T2.SB2 T-A.2.6 | T2.SB3 + T2.SB4 | foundation API shape stable across detectors |
| `test_pattern_evaluations_template_match_score_persistable` | T2.SB3 T-A.3.6 | T2.SB5 | template_match_score column accepts NULL pre-T2.SB5 + float post |
| `test_drift_logging_5_detector_schema_consistent` | T2.SB3 T-A.3.5 | T2.SB4 + Phase 13.5 | feature_distribution_log_json schema stable across 5 detectors |
| `test_theme1_theme2_shared_renderer_handles_5_v1_patterns` | T2.SB6 T-A.6.1 | T2.SB6 closer (final SB) | annotated chart renderer covers all 5 patterns |
| `test_watchlist_close_track_active_unique_index_per_codex_R1_M9` | T4.SB T-D.1 | T4.SB closer | partial unique index allows re-flag of cleared ticker |
| `test_base_layout_vm_banner_pin_phase13_arc_complete` | T4.SB T-D.6 | T4.SB closer | all Phase 13 VMs extending base.html.j2 populate banner fields |
| `test_v20_atomic_landing_python_constants_validators_paired` | T2.SB1 T-A.1.1 | T4.SB closer | Phase 12 C.A T-A.2 LOCK preserved across Phase 13 arc |

### §H.4 Sub-bundle merge gates

Each sub-bundle's executing-plans dispatch concludes with:

1. **Operator-witnessed gate** (S1-S<N> per sub-bundle per §G).
2. **Implementer return report** with file:line evidence for each acceptance criterion (per forward-binding lesson #17 — implementer self-report accuracy gate).
3. **Orchestrator QA review** (per BINDING memory `feedback_orchestrator_qa_implementer_product.md` 9x cumulatively validated).
4. **Operator approval to merge**.
5. **Orchestrator drives merge + post-merge housekeeping** (per BINDING memory `feedback_orchestrator_performs_merge.md`).
6. **Cross-bundle pin un-skip verification** before next sub-bundle's dispatch.

---

## §I — Discriminating examples + watch items

### §I.1 Watch items inherited from dispatch brief §5 (18 items)

Each watch item is BINDING for adversarial-review rounds; flagged in plan text + acceptance criteria where applicable.

1. **§0.3 11 LOCKS + §0.2 OQ-confirmed dispositions integrity** — accepted as given throughout.
2. **OQ-12 Option E migration landing timing accuracy** — T-A.1.1 = migration-only commit; T3.SB1 branches off T2.SB1's first-commit SHA; merge ordering T2.SB1 first.
3. **DETECTOR_PATTERN_CLASSES enum + cross-column CHECK invariants integrity** — 4 columns referencing same enum; 5 numbered cross-column CHECK invariants schema-defended.
4. **Schema-CHECK + Python-constant + dataclass-validator paired atomic landing** — §A.14 verbatim in T-A.1.1.
5. **construct_authenticated_client 4-arg signature discipline** — §A.11 BINDING at T3.SB1 + T3.SB2.
6. **HTMX gotcha trinity preservation** — §A.4 every new form-driven route.
7. **Base-layout VM banner pin** — §A.3 every new VM extending base.html.j2.
8. **5 cross-column CHECK invariants on pattern_exemplars schema-defended** — §A.14 + §B.4.
9. **Q4 schema folds into v20** — §B.3 single-migration LOCK preserved.
10. **OQ-5 phased Codex SELECTIVE policy** — §A.6 + §D.6 T2.SB1 random 15% only; T2.SB3+/SB4 high-stakes clause activates.
11. **OQ-12 Option E migration mechanics — T2.SB1 task 1 is migration-only commit** — T-A.1.1 NOT bundled.
12. **Mid-dispatch operator-paired pause for T2.SB1 exemplar bootstrap** — T-A.1.7 distinct task.
13. **Theme 1 + Theme 2 coupling at T2.SB6** — §C.4 shared annotated chart renderer.
14. **Session-anchor read/write mismatch family** — §A.13 + T-T1.SB0.4 + T-A.6.2 + T-D.6 discriminating round-trip tests.
15. **Reject-caller-held-tx contract on new transactional services** — §A.12 + T-D.1 Q4 service.
16. **Cassette URI/path + body sanitization filter installation** — §A.10 + T-A.1.4 + T-B.1.5 + T-B.2.4.
17. **Plan-author schema additions escalation rule** — §B.6 BINDING; if discovery surfaces new schema, STOP + escalate.
18. **CLAUDE.md size-check trigger discipline** — Phase 13 close housekeeping must not regress line-3 compact status line.

### §I.2 Discriminating examples — boundary case enumeration

Per spec §10 + §10.6 tolerance-semantics LOCK, the per-pattern detector tests at §G.4 + §G.6 + §G.7 cover:

- **§10.1 VCP CVGI hypothetical** (geometric_score 1.0; composite 0.91 with template-match 0.78).
- **§10.2 Flat base errata** — 14% prior uptrend REJECTS via §10.6 LOCK (within tolerance band: 14% < 18% relaxed threshold).
- **§10.3 Cup-with-handle hypothetical** — rounded-vs-V LOCK per §10.7 + 8 criteria pass.
- **§10.4 HTF errata** — 15.6% consolidation width REJECTS via §10.6 STRICT bound (NONE tolerance).
- **§10.5 DBW hypothetical** — undercut bonus + geometric_score capped at 1.0.

Each example anchors at least 1 discriminating test in T-A.3.2/3.3/3.4 + T-A.4.1/4.2.

### §I.3 v2 brief §9.2 8-item checklist coverage at T2.SB6

Per §D.8 LOCK: every one of the 8 checklist items is rendered on `/patterns/{candidate_id}/review`:

1. Proposed pattern class (labeled tile, color-coded).
2. Geometric score breakdown by rule component.
3. Top-3 nearest historical bases (template matches; thumbnails via Theme 1 annotated renderer).
4. Trend-template status badge.
5. RS rank badge.
6. Recent volume profile sparkline.
7. Reason for uncertainty in rule evaluation.
8. Outcome distribution from prior similar candidates (Phase 10 metrics cohort architecture).

Each is asserted by a discriminating test in T-A.6.3.

### §I.4 v2 brief §9.3 6-decision enum coverage at T2.SB6

Per §D.8 LOCK: every one of the 6 decisions handles POST persistence:

- `confirm` → `final_decision='confirmed'`; if trade opened → `label_source='organic_trade_history'`; else → `label_source='closed_loop_review'`.
- `watch` → `final_decision='watch'`.
- `reject` → `final_decision='rejected'`.
- `relabel` → `final_decision='relabeled'` + `final_pattern_class=<operator-supplied corrected_class>`.
- `pattern_present_outside_window` → window-shift emit (separate row with new window dates).
- `multiple_overlapping_patterns` → multi-exemplar emit (one row per detected pattern).

Each is asserted by a discriminating test in T-A.6.3.

### §I.5 Cross-fixture-shape discriminating tests (synthetic vs production-emitter shape drift)

Per forward-binding lesson #13 (CLAUDE.md "synthetic-fixture-vs-production-emitter shape drift"):

- T-A.1.6 `/patterns/exemplars` web-route tests use REAL `pattern_exemplars` row shape (per spec §3.1 17-20 columns), NOT invented synthetic shape.
- T-B.1.4 `entry_post` audit column tests use REAL Schwab API response shape (per post-Phase-12 Sub-bundle 1 `SchwabOrderResponse` + `SchwabExecutionLeg` dataclass shapes), NOT synthetic.
- T-B.2.3 `exit_post` audit column tests same.
- T-A.3.2-T-A.3.4 detector tests use REAL OhlcvCache `to_dataframe()` shape (capitalized columns + DatetimeIndex), NOT synthetic dict.
- T-D.6 watchlist VM banner test uses REAL `unresolved_material_discrepancies_count` query result (Phase 10 `count_unresolved_material` helper), NOT mocked count.

### §I.6 Negative-path discriminating tests

Each new write-side service has at least one negative-path test per §A.12 transactional discipline:

- T-D.1 `set_flag` rejects caller-held tx → `CallerHeldTransactionError`.
- T-D.1 `clear_flag` rolls back on intermediate failure → no partial state.
- T-B.1.4 entry_post with failing schwab_api_calls audit row → trade row also rolls back (atomic).

### §I.7 Empty-state + zero-cohort discriminating tests (per §A.16)

- `/patterns/queue` at zero candidates → "No pattern candidates pending review" placeholder renders.
- `/metrics/pattern-outcomes` at zero pattern_evaluations → Phase 10 honesty.py SuppressedMetric placeholder renders.
- `/patterns/exemplars` at zero exemplars → "Run `swing patterns label-exemplars` to bootstrap" advisory.
- Watchlist at zero flagged tickers → no badge column rendered (no layout shift).

---

## §J — V2.1 §VII.F amendment candidates banked

Writing-plans phase surfaced these candidate amendments for operator-pre-merge consideration:

### §J.1 Banked at brainstorm spec level (per spec §13 V2 candidates V2-1..V2-22)

Inherited from spec §13. No new banks at writing-plans phase.

### §J.2 Banked during writing-plans authoring

| ID | Candidate | Rationale | Disposition |
|---|---|---|---|
| WP-1 | `swing/patterns/template_matching.py` standalone benchmark profiling helper for ongoing 120s gate monitoring | DTW O(n²) cost may grow as exemplar corpus grows; V2 monitoring helper would emit warning if gate would fail next-run | V2 — add when corpus reaches ~150 exemplars per pattern |
| WP-2 | Backfill historical `reconciliation_corrections` chains into `fills.schwab_source_value_json` | Per OQ-7 V2 — preserves audit-trail history through fill_origin model | V2 dispatch candidate; needs careful semantic mapping (Phase 12 reconciliation_corrections rich audit history not trivially serialized) |
| WP-3 | `review_log.fields_auto_populated_count` + `auto_fill_disagreement_count` aggregate columns | Per spec §3.6 — derived from `auto_populated_field_keys_json` query-time; promote to first-class when query frequency justifies | V2 dispatch when query overhead becomes material |
| WP-4 | `chart_renders` cache TTL invalidation helper (auto-expire stale renders by date threshold) | V1: refresh-on-fills + refresh-on-data_asof_date staleness only. V2 could add scheduled cleanup | V2 — only if disk usage becomes operator-noticeable |
| WP-5 | Q4 close-tracking flag auto-expire after N days configurable per-flag | Per spec §7.5 V2 candidate | V2 — flag inflation only becomes operator-noticeable in months |
| WP-6 | `mcp__plugin_copowers_codex__codex` invocation rate-limiter | If T2.SB3+/SB4 Codex high-stakes clause fires frequently, cumulative cost may need throttling | V2 — monitor at first 100 fires |
| WP-7 | Active-learning prioritization weight tuning | §5.10 4-criterion ranking uses equal weights V1; operator-paired calibration may yield improvements | V2 — tune after 1 month of operator-flagged queue triage data |

### §J.3 Forward-binding lessons NOT regressed

Phase 13 PRESERVES all ~60 cumulative forward-binding lessons inherited per spec §11. Specifically:

- ZERO Co-Authored-By footer drift across Phase 13 commits (target: ~187+ cumulative ZERO-drift streak preserved).
- ZERO ACCEPT-WITH-RATIONALE preferred at brainstorm + writing-plans + executing-plans Codex rounds (Phase 12.5 #1+#2+#3 + Phase 13 brainstorm + Phase 13 writing-plans clean-record streak target).
- Pre-Codex orchestrator-side review BINDING per C.C lesson #6 (validated 9x cumulatively; 10th cumulative validation cited in return report).

---

## §K — Test + LOC projections per Sub-bundle

### §K.1 Per-sub-bundle test delta + LOC projection table

| SB | Task count | Test delta (fast) | Test delta (slow) | Production LOC | Test LOC |
|---|---|---|---|---|---|
| T1.SB0 | 4 | +20-40 | 0 | +50-100 | +200-350 |
| T2.SB1 | 8 | +50-90 | +0 (cassette-mode) | +500-800 | +600-900 |
| T3.SB1 | 6 | +40-70 | +1 (Schwab E2E) | +200-300 | +300-500 |
| T2.SB2 | 6 | +60-100 | 0 | +400-600 | +500-800 |
| T2.SB3 | 9 | +90-150 | +1 (operator-fixture detector) | +800-1200 | +1000-1500 |
| T3.SB2 | 5 | +40-70 | +1 (Schwab E2E) | +200-300 | +300-500 |
| T2.SB4 | 7 | +70-120 | 0 | +500-800 | +700-1100 |
| T2.SB5 | 6 | +60-100 | +1 (pytest-benchmark) | +400-600 | +500-800 |
| T3.SB3 | 5 | +50-90 | 0 | +200-400 | +400-700 |
| T2.SB6 | 7 | +70-120 | +1 (full closed-loop E2E) | +700-1100 | +900-1400 |
| T4.SB | 7 | +40-70 | 0 | +250-400 | +400-700 |
| **Cumulative** | **70 tasks** | **+590-1020 fast** | **+4 slow E2E** | **+4200-6600 prod LOC** | **+5800-9250 test LOC** |

### §K.2 Cumulative baseline + Phase 13 close projection

- **Baseline at Phase 13 start** (post Phase 12.5 #3 ship + Phase 13 brainstorm ship + Phase 13 writing-plans ship): ~4924 fast tests (per HEAD `b5e62c5`).
- **Phase 13 close projection**: ~5500-5940 fast tests + 4 new slow E2E tests (pytest -m slow gate).
- **Production LOC delta**: +4200-6600 LOC (mostly Theme 2 detector LOC).
- **Test LOC delta**: +5800-9250 LOC.

### §K.3 Per-cumulative-week pacing projection

Per `feedback_time_estimates_overstated.md` memory (operator calibration: orchestrator-side estimates overrun by 3-5x; trust operator wall-clock pacing).

Naive estimate per sub-bundle: 3-5 days each at operator-paced rates → ~33-55 days cumulative. Operator-calibrated 3-5x overrun → **~7-18 days actual** for Phase 13 arc close. Wall-clock is operator-paced; this is informational only.

### §K.4 Per-task pacing within a sub-bundle

- Simple tasks (recon / closer / ruff sweep): ~30-60 min.
- Standard tasks (write test + impl + commit): ~1-3 hours.
- Schema-landing task (T-A.1.1): ~2-4 hours (atomic; bigger touch).
- Detector task (T-A.3.2 + similar): ~3-5 hours (~12+ tests + ~200-300 LOC).
- Operator-paired pause (T-A.1.7): undetermined — operator-paced.

---

## §L — Forward-binding lessons for executing-plans dispatches

Each executing-plans implementer dispatch consumes these BINDING lessons (per spec §11):

### §L.1 Inherited verbatim from spec §11 (20 lessons; abridged citation)

1. Schema-CHECK + Python-constant + dataclass-validator paired atomic landing (Phase 12 C.A T-A.2).
2. Migration backup-gate strict equality form (`pre_version == 19`).
3. No INSERT OR REPLACE on audit-trail tables.
4. `executescript()` implicit COMMIT — explicit BEGIN/COMMIT/ROLLBACK in `_apply_migration`.
5. `apply_overrides(cfg)` + `resolve_credentials_env_or_prompt(allow_prompt=False)` + `construct_authenticated_client` 4-arg signature at every new Schwab entry point.
6. Cassette infrastructure URI/path + body sanitization (post-Phase-12 lesson #2).
7. Standalone recording scripts (post-Phase-12 lesson #3).
8. HTMX gotcha trinity (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted).
9. Base-layout VM banner pin — every new VM extending base.html.j2 populates `unresolved_material_discrepancies_count` + `banner_resolve_link`.
10. Session-anchor read/write mismatch family (forward-looking vs backward-looking).
11. OhlcvCache writes from in-deadline futures only (Phase 11 lesson).
12. External-API empty-result transient handling (Phase 11).
13. Synthetic-fixture-vs-production-emitter shape drift.
14. Windows cp1252 stdout safety (ASCII-only on runtime CLI paths).
15. Matplotlib mathtext gotcha (SVG inline + ZERO mathtext metacharacters).
16. Pre-Codex orchestrator-side review BINDING (C.C lesson #6; 10x cumulative validation at Phase 13 writing-plans).
17. Implementer self-report accuracy gate — cite file:line evidence (C.C lesson #7).
18. NO Co-Authored-By footer (C.B lesson #7; 187+ cumulative ZERO-drift streak).
19. Pass-2-tier-1-FORBIDDEN family — execution-grain mapper widening at post-Phase-12 Sub-bundle 1.
20. Hidden audit field server-stamping (Phase 8 R2-R5 family).

### §L.2 Phase 13-specific lessons surfaced during writing-plans authoring

| # | Lesson | Forward-binding source | Apply at |
|---|---|---|---|
| 21 | `DETECTOR_PATTERN_CLASSES` enum referenced by 4 columns is a v21+ widening hotspot — Phase 14 sell-side detectors require widening + paired Python-constant + dataclass-validator + cross-column CHECKs simultaneously per §A.14 | Spec §3.0 + §3.5 | Phase 14 sell-side migration |
| 22 | Operator-paired mid-dispatch pause (T-A.1.7 + future labeling cassette sessions) is the canonical workflow for any Phase 13 corpus bootstrap; mirrors post-Phase-12 Sub-bundle 1 + Phase 12.5 #1 cassette-session precedent | OQ-6 + §G T-A.1.7 | Phase 13.5 monitoring side corpus bootstrap; Phase 14 sell-side corpus bootstrap |
| 23 | DTW O(n²) cost growth — exemplar corpus subsampling + per-pattern filtering + geometric-score pre-gate + max-windows-per-ticker pruning ALL required to hit 120s benchmark gate at 250-name universe scale | OQ-4 + §D.5 pruning LOCK + T-A.5.5 | Phase 14 sell-side template matching reuses |
| 24 | Theme 1 + Theme 2 coupling at T2.SB6 — annotated chart renderer at `swing/web/charts.py:render_theme2_annotated_svg` MUST consume `pattern_evaluations.structural_evidence_json` (Theme 2) verbatim; tight contract preserves operator-interpretability per v2 brief §1 introspection HARD constraint | §C.4 + §D.8 + T-A.6.1 + T-A.6.3 | Phase 13.5 monitoring side chart deepening |
| 25 | Codex SELECTIVE policy phased rollout — T2.SB1 phase fires random 15% ONLY (high-stakes clause defers to T2.SB3+/SB4); rollout pattern lifts cleanly to other phases needing pre-detector-then-post-detector evolution | OQ-5 + §A.6 + §D.6 + T-A.1.3 + T-A.3.7 + T-A.4.5 | Phase 14 sell-side detector labeling + Phase 13.5 drift detector labeling |
| 26 | OQ-12 Option E migration landing timing pattern — T2.SB1 task 1 = migration-only commit; T3.SB1 branches off T2.SB1's first-commit SHA — is the canonical pattern for any future concurrent-sub-bundle dispatch needing shared schema atomic landing | OQ-12 + §B.2 + T-A.1.1 + T-B.1.1 | Future arc concurrent dispatches needing schema fork |
| 27 | Q4 close-tracking flag `auto_cleared_on_position_open` semantics — caller-tx contract (consumed inside trade-entry outer with conn block) + reject-caller-held-tx public companion — is the canonical pattern for any future event-triggered audit-row clear | §F.4 + §A.12 + T-D.1 + T-D.5 | Phase 14+ event-triggered audit-row clear surfaces |
| 28 | `chart_renders` cache session-anchor read/write predicate alignment — writer + reader BOTH use `last_completed_session(now())` — extends the family established at Phase 8 daily_management_records `cfacbc5` precedent | §A.13 + §C.2 + T-A.6.2 | Phase 13.5 monitoring side cache surfaces; any future write-through cache backed by deterministic pure-function rendering |
| 29 | Pattern detector tolerance bands per spec §10.6 LOCK — per-criterion symmetric tolerance "±X%" produces PASS in `[bound - X%, bound + X%]` range; NONE-hard-gate uses STRICT inequality; NONE-bounds-not-thresholds uses RANGE check ZERO-tolerance — uniform across all 5 detectors + §10.1-§10.5 worked examples | §10.6 + §D.10 + T-A.3.2/3.3/3.4 + T-A.4.1/4.2 | Phase 14 sell-side detector criterion specification |
| 30 | Cup curvature rounded-vs-V test centered on `cup_bottom_date` (price extremum) NOT temporal midpoint — closes Codex R1 M#8 incoherence; pattern lifts to any future detector with curvature criterion | §10.7 + §D.11 + T-A.3.4 | Phase 14 sell-side H&S top neckline analysis |

### §L.3 Capture-needs DEFERRED to Phase 13.5 / Phase 14 (per dispatch brief §6 done criterion 11)

Per orchestrator-context.md "Lessons captured" 2026-05-18 PM + this writing-plans' §J banks:

- **Drift monitoring/dashboard side** (4 surfaces: feature drift / pattern frequency drift / outcome drift / self-drift) → **Phase 13.5** (LOCKed at L5; baseline LOGGING side ships in Phase 13 V1).
- **Sell-side detector module** (H&S top + climax run + Stage 4 breakdown + MA50/MA200 violations) → **Phase 14** (LOCKed at L3).
- **ML re-ranker** (Role 2 per v2 brief §16.1) → indefinitely deferred (LOCKed at L4; gated on v2 brief §16.6 7 gates G1-G7).
- **Matrix Profile-based exemplar retrieval at scale** → Phase 14+ (v2 brief §5.8 + §10 Phase 7).
- **Shapelet-based detection** → Phase 14+ (v2 brief §5.9).
- **Z-score normalization** for template-matching (vs V1 min-max) → Phase 14+ (gated on calibration discipline).
- **Calibration of composite_score** (Brier + isotonic regression) → V2 (gated on v2 brief §16.5 G2 200 confirmed positives per pattern).
- **SBD or feature-vector template-matching distance metric** → Phase 14+ (V1 fallback if DTW 120s gate fails).
- **Backfill historical reconciliation_corrections chains** into `fills.schwab_source_value_json` → V2 (per OQ-7 V2 candidate).
- **review_log.fields_auto_populated_count + auto_fill_disagreement_count aggregate columns** → V2 (per spec §3.6).
- **Q4 close-tracking flag auto-expire after N days** → V2 (per spec §7.5 + WP-5).
- **Per-ticker watchlist annotation (free-text notes)** → V2 (per spec §7.5).
- **Bulk-flag CLI for Q4** → V2 (per spec §7.5).
- **"Elevated to hyp-rec" toggle for Q4 flags** → V2 (per spec §7.5 + D-Q4.6).
- **Multi-cohort architectural deepening** → Phase 14+ (LOCKed at L8 single-strategy focus).
- **Intraday / live-trading integration** → Phase 14+.
- **Tax-lot accounting** → Phase 14+.
- **Branch A research-branch Phase 0 activation** → deferred per operator 100% operational decision (LOCKed at L7).
- **Operator-elicited usability list beyond Q4** → operator confirmed no additional items at 2026-05-18 PM elicitation (LOCKed at §F.1 + L11; future surfacing routes to Phase 13.5 / Phase 14).
- **Interactive client-side JS chart library** (TradingView Lightweight Charts / Plotly / Bokeh) → Phase 14+ (V1 SVG inline locked).

### §L.4 Operator-witnessed gate inheritance

Per Phase 10 §I.15 + every sub-bundle's gate section in §G: operator-witnessed browser verification is BINDING for every new surface on first deploy. TestClient passes are necessary but not sufficient — the JS-test-harness gap (CLAUDE.md gotcha family) means operator-witnessed DevTools or Playwright/Selenium harness verification catches what TestClient cannot.

Per-sub-bundle gate-surface count enumerated in §G; all sub-bundles ≤8 surfaces fit one operator session.

---

## §M — Plan completion checklist

The executing-plans dispatch for each sub-bundle consumes this plan as substrate. The orchestrator drives the dispatch sequence per §H.1. This plan is complete when:

- [ ] §0 top-matter + spec lineage cross-referenced.
- [ ] §A general architectural decisions (L1-L11 + 12 OQ dispositions) encoded.
- [ ] §B v20 migration mechanics (OQ-12 Option E) encoded.
- [ ] §C Theme 1 architectural decisions encoded.
- [ ] §D Theme 2 architectural decisions encoded.
- [ ] §E Theme 3 architectural decisions encoded.
- [ ] §F Theme 4 architectural decisions encoded.
- [ ] §G per-sub-bundle task decomposition (11 sub-bundles, 70 tasks) with per-task acceptance criteria + discriminating test patterns.
- [ ] §H cross-bundle dependencies + un-skip pin schedule encoded.
- [ ] §I 18 watch items + discriminating examples encoded.
- [ ] §J V2.1 §VII.F amendment candidates banked (7 WP-N items + 22 V2 candidates inherited from spec §13).
- [ ] §K test + LOC projections per sub-bundle.
- [ ] §L forward-binding lessons for executing-plans inheritance (20 inherited + 10 Phase 13-specific = 30 lessons).
- [ ] Plan went through ≥3 Codex adversarial rounds reaching NO_NEW_CRITICAL_MAJOR.
- [ ] Pre-Codex orchestrator-side review BINDING per C.C lesson #6 (10x cumulative validation in return report).
- [ ] Return report at `docs/phase13-writing-plans-return-report.md`.

---

*End of Phase 13 writing-plans plan. 11 sub-bundles + 70 tasks + v20 single migration via OQ-12 Option E + 12 OQ dispositions BINDING-encoded + Pre-Codex orchestrator-side review BINDING. Expected 3-5 Codex rounds + convergent shape. ZERO ACCEPT-WITH-RATIONALE preferred (continuing Phase 12.5 #1+#2+#3 + Phase 13 brainstorm clean-record streak). NO Co-Authored-By footer (~187+ cumulative ZERO-drift streak preserved).*
