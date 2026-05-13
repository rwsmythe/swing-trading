# Phase 10 Metrics Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Phase 10 metrics dashboard per spec `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` — 8 metric categories (§3.1–§3.8) consumed by 8 dashboard surfaces (§4.1–§4.8) under one shared low-sample-size honesty policy (§5), with ZERO new schema (all metric inputs derivable from shipped v17).

**Architecture:** New module `swing/metrics/` (parallel to `swing/recommendations/` + `swing/evaluation/`) holds the shared honesty-policy utility + metric-aggregation helpers + per-cohort filter helper. New view-models in `swing/web/view_models/metrics/` (one file per surface, mirroring spec §4 surface boundaries). New routes in `swing/web/routes/metrics.py` (one router; 9 GET endpoints in V1 = 8 surface endpoints + 1 umbrella `/metrics` index navigator; 0 POST endpoints). Templates in `swing/web/templates/metrics/`. Risk_policy reads split: LIVE policy (`is_active=1`) for statistical thresholds + bootstrap config + process-grade weights; AT-TRADE-TIME policy (`trades.risk_policy_id_at_lock` JOIN) for `capital_floor_constant_dollars` + `scratch_epsilon_R`. PROVISIONAL badge contract is dynamic per `account_equity_snapshots.get_latest_snapshot_on_or_before(asof_date)`: PROVISIONAL when no snapshot exists; LIVE when snapshot covers asof_date.

**Tech Stack:** Python 3.11+ / FastAPI / Starlette 1.0 / Jinja2 / HTMX 2.x / SQLite 3 (no schema change in V1) / pytest / ruff. Statistical primitives: pure-Python Wilson CI (no scipy dep) + percentile bootstrap (1000 resamples default; configurable per `risk_policy.bootstrap_resample_count`). NO matplotlib in V1 surfaces (§4.8 line chart rendered as inline SVG via Jinja or plain CSS-styled `<table>` per Sub-bundle E orchestrator-decision; defers matplotlib mathtext gotcha entirely).

---

## §A — Resolved-during-planning items (empirical-audit findings)

### §A.0 Schema posture — ZERO new tables, ZERO ALTERs (locked)

Pre-plan grep of `swing/data/migrations/0001_*.sql` through `0017_*.sql` + `swing/data/models.py` + `swing/trades/derived_metrics.py` + `swing/trades/equity.py` + `swing/trades/review.py` confirms every spec §3 metric input is either (a) a stored column in the v17 schema OR (b) derivable from a shipped helper. No `0018_*.sql` migration in Phase 10 V1. `EXPECTED_SCHEMA_VERSION` stays at 17.

**Per-metric-input verification matrix** (per dispatch brief §0.6):

| Spec §3 input | Status | Source |
|---|---|---|
| `trades.realized_R_if_plan_followed` | column | migration 0013, models.py:103 |
| `trades.mistake_tags` | column | 0013 |
| `trades.entry_grade` / `management_grade` / `exit_grade` / `process_grade` | columns | 0013 |
| `trades.disqualifying_process_violation` | column | 0013 |
| `trades.last_fill_at` / `pre_trade_locked_at` | columns | 0014 |
| `trades.hypothesis_label` / `trade_origin` / `state` | columns | 0007 / 0014 |
| `trades.entry_price` / `initial_stop` / `initial_shares` / `current_stop` / `current_size` / `current_avg_cost` | columns | 0001 / 0014 |
| `trades.planned_target_R` | column | 0016 |
| `trades.risk_policy_id_at_lock` | column | 0017 |
| `review_log.total_mistake_cost_R` / `total_lucky_violation_R` / `expectancy_R_effective` / `win_rate` / `avg_win_R` / `avg_loss_R` / `profit_factor` / `max_drawdown_R` / `net_R_effective` | columns | 0013 |
| `review_log.risk_policy_id_at_review_completion` | column | 0017 |
| `fills.action` / `quantity` / `price` / `fill_datetime` / `fees` | columns | 0014 |
| `daily_management_records.maturity_stage` / `open_MFE_R_to_date` / `open_MAE_R_to_date` / `position_capital_utilization_pct` / `position_portfolio_heat_contribution_dollars` / `trail_MA_candidate_price` | columns | 0016 |
| `hypothesis_registry.*` (10 cols incl. statement / decision_criteria / target_sample_size / consecutive_loss_tripwire / absolute_loss_tripwire_pct / status / status_changed_at / status_change_reason) | columns | 0008 |
| `hypothesis_status_history` (id / hypothesis_id / status / effective_from / effective_to / change_reason / recorded_at / created_at) | table | 0017 (Phase 9 Sub-bundle C) |
| `risk_policy` (34 cols incl. is_active / capital_floor_constant_dollars / scratch_epsilon_R / global_confidence_floor_n / bootstrap_resample_count / process_grade_weight_*) | table | 0017 (Phase 9 Sub-bundle A) |
| `account_equity_snapshots` (snapshot_date / equity_dollars / source / is_back_recorded) | table | 0017 (Phase 9 Sub-bundle C) |
| `reconciliation_runs` / `reconciliation_discrepancies` (incl. `material_to_review` + `resolution`) | tables | 0017 (Phase 9 Sub-bundle B) |
| `candidates` + `criterion_results.criterion_name='risk_feasibility'` | tables | 0001 |
| `pipeline_runs.started_ts` / `finished_ts` / `evaluation_run_id` | columns | 0003 / 0006 |
| `net_pnl_dollars` / `gross_pnl_dollars` / `planned_risk_budget_dollars` / `vwap_entry` / `risk_per_share` / `actual_realized_R_effective` | DERIVED | helpers below |

**Derivation helpers shipped (Phase 10 consumes; does NOT add new):**
- `swing/trades/derived_metrics.py:initial_risk_per_share(entry_price, initial_stop)` → `risk_per_share` per spec §2.
- `swing/trades/derived_metrics.py:realized_pnl(entry_price, exit_price, quantity)` → per-fill component for `net_pnl_dollars`.
- `swing/trades/derived_metrics.py:r_multiple(...)` → per-fill R contribution.
- `swing/trades/equity.py:risk_per_share(trade)` → trade-level risk_per_share.
- `swing/trades/review.py:compute_actual_realized_R_effective(trade, exits)` → `actual_realized_R_effective`.
- `swing/trades/review.py:compute_mistake_cost_R(...)` / `compute_lucky_violation_R(...)` → §3.1 mistake/lucky aggregates (also persisted on review_log).
- `swing/trades/review.py:compute_profit_factor(...)` / `compute_max_drawdown_R(...)` → cohort-level aggregates.

**`planned_risk_budget_dollars` derivation** (spec §2 names it the single denominator post §1.3 DROP-rule collapse): `(trade.entry_price - trade.initial_stop) * trade.initial_shares` for long; absolute-value the bracket. **Edge case:** if `initial_stop > entry_price` (data-entry inversion), the derivation yields a negative; Phase 10 helper MUST clamp to 0 → emits `Insufficient: invalid stop` placeholder (NOT a CHECK enforcement; respects historical data integrity).

**`net_pnl_dollars` derivation:** `sum(exit_action.price * exit_action.quantity) - sum(entry_action.price * entry_action.quantity) - sum(fills.fees)` (entry includes `action='entry'`; exit includes `action ∈ {trim, exit, stop}` per Phase 7 fills enum).

**`gross_pnl_dollars` derivation:** Same as net minus the `- sum(fills.fees)` term.

**`vwap_entry` derivation:** `sum(price * quantity) / sum(quantity)` over `fills.action='entry'`. Single-fill entries reduce to that fill's price.

### §A.0.1 Phase 10 V1 capture-need shortfalls (from spec §6.3) + historical-reconstruction limitation (Codex R1 Major #5 fix)

Two §6.3 capture-needs are NOT shipped + are NOT closed by Phase 10 V1:

1. **Per-pipeline-run capital-utilization aggregate** (spec §6.3 (a)): the spec proposed either a `pipeline_runs_metrics_capital_aggregate` table OR `pipeline_runs` ALTERs. **Phase 10 V1 derives on-the-fly via JOIN** of `pipeline_runs.started_ts` → `account_equity_snapshots.get_latest_snapshot_on_or_before(started_ts.date())` + `trades` open-at-timestamp. NO new columns. Defer aggregation table to V2 if multi-run trend queries become slow (>500ms p95 on dashboard). Lock in §I.7.

2. **Per-pipeline-run identification-vs-trade-funnel snapshot** (spec §6.3 (b)): same on-the-fly JOIN against `candidates` + `pipeline_runs` + `trades.trade_origin`. NO new columns. Lock in §I.7.

**Historical-reconstruction limitation (binding for Tasks D.1 + D.2 + D.5 + D.6):**

For HISTORICAL multi-run trends (e.g., `risk_feasibility_blocked_rate` over the last 30 runs; `aplus_take_rate_per_run` over rolling 30-trading-day window), the on-the-fly JOIN consumes the CURRENT state of `trades` (current_size, current_avg_cost, current_stop, current_state). It DOES NOT reconstruct the historical state of those columns at the time of the run. Specifically:

- A trade opened at run N's session date with size=100; size changed to 200 via a fill at run N+5's session date → query for run N's `current_capital_utilization_pct` uses size=200 (NOT size=100).
- A trade with stop adjusted from $50 to $45 between runs N and N+1 → query for run N's portfolio-heat aggregate uses stop=$45 (NOT stop=$50).
- A trade closed between runs N and N+1 → query for run N's `concurrent_open_positions` count EXCLUDES the trade (since `state='closed'` filter applies to current state).

**V1 lock:** historical multi-run trends are computed BEST-EFFORT against current trade state. The TODAY's-run point-in-time gauge is fully accurate; historical trend points are approximate. Render trends with a disclosure footnote: `"Trend computed from current trade state; historical points approximate where state has changed since the run."`

**Discriminating tests** (binding in Task D.5):
- `test_historical_funnel_uses_current_trade_state`: seed run R1 + trade T1 at R1's session with origin='pipeline_aplus'; advance to run R2; query for R1's `aplus_trades_taken_per_run` → assert T1 counted (uses CURRENT trade state — `pre_trade_locked_at` matches R1.session even though state may have evolved).
- `test_historical_capital_friction_disclaimer_renders`: trend section renders the footnote text.
- `test_historical_capital_friction_concurrent_open_at_run_uses_open_at_pre_trade_locked_at_only`: count trades with `pre_trade_locked_at <= run.started_ts AND (last_fill_at IS NULL OR last_fill_at >= run.started_ts)` — best-effort proxy for "open at run time".

**True historical reconstruction is V2 scope** — would require either (a) a `pipeline_runs_open_trade_snapshot` table written by `_step_evaluate` per-run, OR (b) per-run replay of fills + stop_adjust events up to `run.started_ts`. Both are non-trivial; defer until trend-accuracy becomes operator-relevant.

Items §6.3 (c) (corporate actions) + (d) (daily account equity capture) are each their own orchestrator-decision pending per §A.4 below; both default to OUT of Phase 10 V1.

### §A.1 Module placement — `swing/metrics/`

New top-level module mirrors `swing/recommendations/` + `swing/evaluation/` precedent. Layout:

```
swing/metrics/
  __init__.py                      # public re-exports
  honesty.py                       # spec §5 — Wilson CI + bootstrap CI + suppression text + Class A/B/C/D dispatcher
  policy.py                        # risk_policy resolver (LIVE-policy vs AT-TRADE-TIME-policy split)
  equity_resolver.py               # live_capital_denominator_dollars resolver (PROVISIONAL fallback contract)
  cohort.py                        # per-hypothesis-cohort filter + aggregation helper
  rolling.py                       # rolling-N window helper (spec §3.8 Class D)
  funnel.py                        # per-pipeline-run identification-funnel helper
  process.py                       # trade-process metrics (§3.1) computation entry-point
  capital.py                       # capital-friction metrics (§3.4) computation entry-point
  maturity.py                      # maturity-stage metrics (§3.5) computation entry-point
  tier.py                          # tier-comparison + deviation-outcome metrics (§3.3 + §3.7)
  process_grade_trend.py           # §3.8 rolling-grade trend metrics
```

Rationale: each per-surface metrics helper is a thin orchestrator over the shared `honesty.py` + `cohort.py` + repo reads. Per-file responsibility maps 1:1 onto spec §3 categories. Keeps each file <300 LOC + reviewable.

### §A.2 View-model placement — `swing/web/view_models/metrics/`

New sub-package mirrors the metric module split. One VM file per dashboard surface (spec §4):

```
swing/web/view_models/metrics/
  __init__.py
  trade_process_card.py            # spec §4.1
  hypothesis_progress_card.py      # spec §4.2 — extends existing hyp-recs progress section
  tier_comparison.py               # spec §4.3
  capital_friction.py              # spec §4.4
  maturity_stage.py                # spec §4.5
  identification_funnel.py         # spec §4.6
  deviation_outcome.py             # spec §4.7
  process_grade_trend.py           # spec §4.8
  shared.py                        # shared VM shapes — confidence-badge + provisional-badge + suppression-row dataclasses
```

Each VM dataclass is `@dataclass(frozen=True)` + carries the base-layout fields (`session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded`) per the CLAUDE.md `base.html.j2` gotcha.

### §A.3 Route placement — single `swing/web/routes/metrics.py`

8 GET endpoints + 0 POST endpoints in V1 (Phase 10 is read-side dominant; no manual snapshot capture form per §A.4 default). Endpoint paths:

| Surface (spec §4) | Path | Renders |
|---|---|---|
| §4.1 Trade-process card | `GET /metrics/trade-process` | full page; per-cohort tabs default |
| §4.2 Hypothesis-progress card | `GET /metrics/hypothesis-progress` | full page; 4-cohort row layout |
| §4.3 Tier-comparison | `GET /metrics/tier-comparison` | full page; 4-cohort side-by-side |
| §4.4 Capital-friction | `GET /metrics/capital-friction` | full page; point-in-time + multi-run trend |
| §4.5 Maturity-stage | `GET /metrics/maturity-stage` | full page; per-open-position table |
| §4.6 Identification-funnel | `GET /metrics/identification-funnel` | full page; per-run stacked + 30-trading-day trend |
| §4.7 Deviation-outcome | `GET /metrics/deviation-outcome` | full page; per-cohort table |
| §4.8 Process-grade-trend | `GET /metrics/process-grade-trend` | full page; rolling-N line + per-trade markers |

Plus one umbrella index: `GET /metrics` → renders an 8-tile navigator card linking to each surface (gives operator a single entry-point + a place to render the global "PROVISIONAL fallback in effect" banner once per session). Index route counts as the 9th endpoint.

### §A.4 Open-question disposition (spec §8 + dispatch brief §0.4 + §0.5)

Each spec §8 + §0.4 / §0.5 OPEN question gets a default-disposition lock + an orchestrator-decision-pending tag where applicable. Operator may revise at integration triage of this plan; the executing-plans dispatch will inherit the locked default unless overridden.

| Question | Default-disposition | Orchestrator-decision-pending? |
|---|---|---|
| §8.1 `fills.action='add'` enum gap | DEFER (capital-floor convention) | NO — settled. |
| §8.2 web-form manual snapshot capture in V1 | NO — CLI-only (`swing account snapshot record` shipped Phase 9 Sub-bundle C) | YES — operator may elect. Cost: +1 task in Sub-bundle E, +1 HTMX gate-surface, ~30min impl. If elected: server-stamp `snapshot_date` + `recorded_at` at handler entry per Phase 8 R2/R3/R4 lock; reject caller-held tx in service per Phase 9 arc lock. |
| §8.3 benchmark series capture location | DEFER (n<60 trading days) | NO — settled. |
| §8.4 Corporate_Actions MVP | DEFER to Phase 10+ follow-up | YES — operator may elect. Cost: +1 table (`corporate_actions`), +1 CLI surface, +1 manual-reconcile flow, ~3-6hr impl. If elected: bundles into a NEW Sub-bundle F. |
| §8.5 `process_grade_rolling_N` window size | HARDCODE N=10 (spec lock) | NO — settled. Externalization is V2 risk_policy work. |
| §8.6 surface `lucky_violation_R` on Phase 6 review form | DEFER to standalone follow-up dispatch | YES — operator may elect to roll into Sub-bundle B (the §4.1 trade-process card sub-bundle). Cost: +1 task (~1hr impl). |
| §8.7 hypothesis-cohort decision-criteria automation | MANUAL text-rendering only (`cohort_decision_criterion_evaluation_text` per spec §3.7 R1 M4) | NO — settled. |
| §0.5 §11.2 (a) reconciliation "N unresolved material" badge on dashboard | YES in Sub-bundle E (polish) | NO — accepted default. |
| §0.5 §11.2 (b) per-trade discrepancy indicator | DEFER to Phase 10+ follow-up | YES — operator may elect (+1 surface in Sub-bundle E). |
| §0.5 §11.2 (c) per-cohort "exclude trades with unresolved discrepancies" filter | DEFER to Phase 10+ follow-up | YES — operator may elect (+1 toggle helper in Sub-bundle C). |
| §0.5 §11.3 V1 supersession — full hypothesis transition history on hypothesis-progress card | YES — Phase 9 Sub-bundle C closed the gap; supersede spec §3.2 "single most-recent transition only" V1-limitation | NO — accepted default per dispatch brief. |
| §0.5 §11.4 dynamic PROVISIONAL badge contract | LOCK as "PROVISIONAL when fallback hit; LIVE when snapshot covers asof_date" | NO — accepted default. |

### §A.5 Risk_policy read split — LIVE vs AT-TRADE-TIME (spec §0.5 §11.1 lock)

Phase 10 dashboard reads risk_policy at TWO different scopes per metric. The split is binding + Codex-checkable:

**LIVE policy (`risk_policy.is_active=1` via `swing.data.repos.risk_policy.get_active_policy(conn)`):**
- `low_sample_size_threshold_class_a_n` / `_class_b_n` / `_class_c_n` / `_class_d_n` (suppression at render).
- `global_confidence_floor_n` (spec §5 lock; default 20).
- `bootstrap_resample_count` (spec §5.2 default 1000).
- `process_grade_weight_entry` / `_management` / `_exit` (current weight reconstitution if a legacy review_log row's stamp is absent).
- `target_sample_size` per cohort — read from `hypothesis_registry`, NOT `risk_policy` (cohort governance is migration-locked per spec §1.3, NOT settable risk-policy-mirrored).

**AT-TRADE-TIME policy (`trades.risk_policy_id_at_lock` JOIN to `risk_policy.policy_id` via `swing.data.repos.risk_policy.get_policy_by_id(conn, policy_id)`):**
- `capital_floor_constant_dollars` — preserves historical-trade interpretation under capital-floor change.
- `scratch_epsilon_R` — preserves win/loss/scratch classification under threshold change.
- Trade-grain metrics needing policy-as-of-trade-time semantics (e.g., a trade closed under policy_id=2 with scratch_epsilon=0.10 must NOT be re-classified if the operator later supersedes to a policy with scratch_epsilon=0.20).

**Cohort-grain aggregation rule** (per spec §5 R3 M2 decoupling): cohort-level rate metrics (win_rate, scratch_rate) iterate per-trade and apply the per-trade scratch_epsilon (AT-TRADE-TIME policy); the aggregate is then suppressed per LIVE policy's class-A threshold. This means a cohort's win_rate denominator can mix trades classified under different scratch_epsilon values — that is correct behavior (each trade's classification is preserved).

**Edge case: legacy trade with `risk_policy_id_at_lock IS NULL`** (pre-Phase-9 trades). Per Phase 9 Sub-bundle A migration 0017, the ALTER added the column NULLABLE; legacy rows have NULL. For these, AT-TRADE-TIME policy resolution falls back to LIVE policy with a `[legacy: pre-Phase-9 trade]` annotation rendered alongside the metric value. Lock in §I.3.

### §A.5.1 Cohort-aggregate `cumulative_R_pct_of_capital` semantics (Codex R1 Major #2 fix)

Spec §3.2 governance metric `cumulative_R_pct_of_capital` is a COHORT-AGGREGATE — sum over all closed trades in the cohort. Trades in the cohort may have been stamped under DIFFERENT `risk_policy_id_at_lock` values (operator may have superseded the policy between trades).

**Locked formula** (binding for Task B.4):

```
cumulative_R_pct_of_capital(cohort) =
    sum over trades t in cohort of:
        ( t.realized_pnl_dollars / at_trade_time_policy(t).capital_floor_constant_dollars )
```

Per-trade contribution is divided by ITS at-trade-time floor; contributions then summed. Preserves historical-trade interpretation under capital-floor supersession (per spec §1.3 pre-registration discipline + §A.5 split-policy lock).

**REJECTED alternatives** (would silently re-classify historical state):
- Naive sum-then-divide using LIVE policy: `sum(realized_pnl_dollars) / live_policy.capital_floor` — re-classifies every prior trade's contribution if operator supersedes policy.
- Average policies across trades + single-divide: `sum(realized_pnl_dollars) / mean(at_trade_time_floors)` — algebraic identity broken; result depends on trade ordering at boundary epsilons.

`distance_to_absolute_loss_tripwire` inherits the same lock since it directly references `cumulative_R_pct_of_capital`. Per spec §3.2: `distance_to_absolute_loss_tripwire = absolute_loss_tripwire_pct - abs(min(0, cumulative_R_pct_of_capital))` — `absolute_loss_tripwire_pct` is migration-locked on `hypothesis_registry`, NOT settable; only the `cumulative_R_pct_of_capital` denominator semantics are at issue.

**Discriminating test** (binding in Task B.4): see `test_vm_cumulative_R_uses_per_trade_at_trade_time_capital_floor` for the multi-policy fixture pattern.

### §A.6 Dynamic PROVISIONAL badge contract (spec §0.5 §11.4 lock)

Per spec §2 split-policy + Phase 9 Sub-bundle C `account_equity_snapshots`, the PROVISIONAL badge on §3.4 + §3.5 operational metrics is DYNAMIC, not static.

**Resolution function** (lives in `swing/metrics/equity_resolver.py`):

```python
def resolve_live_capital_denominator_dollars(
    conn: sqlite3.Connection, *, asof_date: date, at_trade_time_policy: RiskPolicy
) -> tuple[float, Literal["LIVE", "PROVISIONAL"]]:
    snapshot = get_latest_snapshot_on_or_before(conn, asof_date=asof_date)
    if snapshot is not None:
        return (float(snapshot.equity_dollars), "LIVE")
    return (float(at_trade_time_policy.capital_floor_constant_dollars), "PROVISIONAL")
```

`get_latest_snapshot_on_or_before` is `swing/data/repos/account_equity_snapshots.py:130` (shipped Phase 9 Sub-bundle C). The source-ladder (`schwab_api > tos_csv > manual`) is internal to that helper.

**Per-surface application** (Codex R1 Major #3 fix — backward-looking anchor everywhere snapshot-related per §A.15 to avoid session-anchor read/write mismatch gotcha):

- §4.4 capital-friction: apply per `asof_date = swing.evaluation.last_completed_session(datetime.now())` (BACKWARD-looking; aligns with snapshot writer's anchor per Phase 9 Sub-bundle C spec §A.9). The "point-in-time" gauge then reflects "the most recent completed session for which a snapshot could exist." Forward-looking `action_session_for_run` is REJECTED here because it would silently miss snapshots recorded on the most-recently-closed session during pre-market hours.
- §4.5 maturity-stage: apply per `asof_date = last_completed_session(datetime.now())` for the ROW-LEVEL fallback denominator IF the trade has no `daily_management_records.review_date` snapshot yet; OTHERWISE use the trade's most recent `daily_management_records.review_date` (which is itself written via `last_completed_session` per Phase 8 spec §4.5 — same anchor family).
- §4.6 identification-funnel: per-run capital aggregate uses `asof_date = pipeline_run.started_ts.date()` — exception case where the asof_date is the run's actual start timestamp, NOT a session helper. The snapshot lookup `get_latest_snapshot_on_or_before(asof_date)` then naturally returns the latest snapshot ≤ that timestamp's date. No session-anchor mismatch since asof_date IS the timestamp itself.

**Badge-render rule** (per spec §4.9): the PROVISIONAL badge is a TEXT badge inline alongside the metric value, never color-only. Suppression text format for the provisional case: `"PROVISIONAL: $7,500 floor used as live-capital fallback (no snapshot ≤ {asof_date})"`. Lock in §I.4.

### §A.7 Honesty utility module interface (binding for Sub-bundles B–E)

`swing/metrics/honesty.py` exposes the SHARED utility surface that Sub-bundles B+C+D+E consume. Locked interface (subagents may NOT diverge without §A amendment):

```python
@dataclass(frozen=True)
class WilsonCI:
    point: float
    lower: float
    upper: float

@dataclass(frozen=True)
class BootstrapCI:
    point: float
    lower: float
    upper: float
    resample_count: int

@dataclass(frozen=True)
class SuppressedMetric:
    metric_name: str
    n: int
    n_required: int
    placeholder_text: str  # spec §5.6 format

@dataclass(frozen=True)
class HonestyBadges:
    confidence_floor_warning: bool   # spec §5 — visible when n < global_confidence_floor_n
    low_confidence_warning: bool     # spec §5 — visible when 3 ≤ n < 5
    # Sub-bundle A amendment (R1 Major #1 fix): added to convey the spec §5.4
    # "rolling window not yet at N" cadence badge. True when Class D's
    # effective_n is in the partial-window band (5 ≤ effective_n < N).
    # Defaults False so Class A/B/C call sites stay backward compatible.
    window_not_full_warning: bool = False

class HonestyClass(StrEnum):
    A = "rate"           # Wilson CI; spec §5.1
    B = "mean"           # bootstrap CI; spec §5.2
    C = "ratio"          # point estimate (no CI in V1); spec §5.3
    D = "trend"          # rolling-window line; spec §5.4

def wilson_ci(*, k: int, n: int, alpha: float = 0.05) -> WilsonCI: ...
def bootstrap_ci_mean(
    *, samples: list[float], resample_count: int, alpha: float = 0.05, rng_seed: int | None = None,
) -> BootstrapCI: ...
def suppress_for_n(*, metric_name: str, n: int, klass: HonestyClass, policy: RiskPolicy) -> SuppressedMetric | None: ...
def render_class_a(*, k: int, n: int, policy: RiskPolicy, metric_name: str) -> WilsonCI | SuppressedMetric: ...
def render_class_b(*, samples: list[float], policy: RiskPolicy, metric_name: str) -> BootstrapCI | SuppressedMetric: ...
def render_class_c(
    *, value: float | None, n: int, n_wins: int, n_losses: int, policy: RiskPolicy, metric_name: str
) -> tuple[float | None, HonestyBadges] | SuppressedMetric: ...
def render_class_d(
    *,
    samples_in_window: list[float],
    window_n: int,
    policy: RiskPolicy,
    metric_name: str,
    underlying_class: Literal["A", "B", "C", "point"],
    events_in_window: int | None = None,   # required when underlying_class == "A" — generic k-of-n count (Codex R2 Minor #1: not "wins"; e.g., disqualifying_violation count)
    n_wins: int | None = None,             # required when underlying_class == "C" — payoff-ratio numerator-side count
    n_losses: int | None = None,           # required when underlying_class == "C" — payoff-ratio denominator-side count
) -> tuple[WilsonCI | BootstrapCI | float | None, HonestyBadges, str] | SuppressedMetric:
    """Per §A.21: VALUE slot shape depends on underlying_class:
       - "A" → WilsonCI (rate metric in window; events_in_window is the generic k count, e.g., disqualifying_violation_rate_rolling_N count)
       - "B" → BootstrapCI (mean metric in window, e.g., process_grade_rolling_N)
       - "C" → float | None (ratio metric; suppress without diversity)
       - "point" → float | None (sum-only metric, e.g., mistake_cost_R_rolling_N_total)
       Third str = "rolling line drawable" once the line CAN be drawn
       (effective_n >= 5) — Sub-bundle A R1 Major #1 corrected the prior
       wording that allowed "show points only" in the partial-window band.
       The partial-window cadence signal (5 <= effective_n < N) is now
       conveyed via ``HonestyBadges.window_not_full_warning`` instead. The
       SuppressedMetric return covers the effective_n<5 line-absent case;
       the 3-tuple branch always returns drawability_text="rolling line
       drawable".
    """
    ...
```

**Dataclass `__post_init__` validators** (per Phase 9 forward-binding lesson §0.3 #1): `WilsonCI.__post_init__` rejects NaN/inf on point/lower/upper + asserts `lower ≤ point ≤ upper`. `BootstrapCI.__post_init__` same + asserts `resample_count ≥ 1`. `SuppressedMetric.__post_init__` asserts `n ≥ 0` AND `n_required ≥ 1`.

**Wilson CI implementation:** pure-Python per Wikipedia formula (no scipy dep). For `k=0, n=0` → returns `WilsonCI(point=0.0, lower=0.0, upper=0.0)` AND callers must check via `suppress_for_n` first (so n=0 is normally suppressed before reaching `wilson_ci`). For `n>0, k=0` or `k=n` → returns the asymmetric Wilson bounds (one-sided collapses to 0 or 1).

**Bootstrap implementation:** `random.Random(rng_seed)` for determinism in tests; default `rng_seed=None` (non-deterministic in production). Percentile method: sort the resampled means + take `[α/2 * R, (1-α/2) * R]` indices. R from `policy.bootstrap_resample_count`.

**Decoupling discipline (spec §5 R3 M2 + R4 M1):** `suppress_for_n` reads `policy.global_confidence_floor_n` to decide BADGE visibility, NOT cohort target_sample_size. Class-D `render_class_d` returns a 3-tuple that decouples WINDOW-FULLNESS (effective_n vs N) from CONFIDENCE-FLOOR (effective_n vs global_confidence_floor_n) — they are SEPARATE badges per spec §5.4.

### §A.8 Composition surfaces for new fields on base-layout VMs (CLAUDE.md gotcha defense)

Phase 10 introduces 9 new view-model classes. Each MUST carry the base-layout VM fields `session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded` to avoid the `base.html.j2`-shared-fields gotcha (CLAUDE.md "new `vm.foo` field requires adding to EVERY base-layout VM").

**Cross-bundle invariant** (locked at §I.5): all 9 new metrics-page VMs subclass-or-mirror the existing `DashboardVM` field set. Either via Python dataclass inheritance (`@dataclass(frozen=True) class TradeProcessCardVM(BaseLayoutVM): ...`) OR via field duplication with a discriminating regression test pinning every base-layout dereference. Recommended: extract a `BaseLayoutVM` mixin shared via `swing/web/view_models/metrics/shared.py:BaseLayoutVM` that the 9 surface VMs include.

**Discriminating regression test** (binding for Sub-bundle A): `tests/web/test_view_models/test_base_layout_vm_coverage.py::test_all_metrics_vms_have_base_layout_fields` enumerates `swing/web/view_models/metrics/*.py` via importlib + asserts every `@dataclass`-decorated class with a name ending in `VM` has the 5 base-layout field names.

### §A.9 HTMX failure-surface budget (CLAUDE.md gotcha family)

Phase 10 V1 ships 9 GET endpoints + 0 POST endpoints (per §A.3). The known HTMX browser-only failure surfaces (spec §0.3 #10/#11; CLAUDE.md cumulative gotcha catalog) apply IFF a surface returns OOB-swap fragments. Phase 10 surfaces are STATIC-RENDERED full pages per spec §4.9 ("No client-side compute"; static-rendered HTML).

**Posture** (locked at §I.6): Phase 10 V1 surfaces use NO HTMX OOB-swap, NO HX-Redirect, NO embedded forms, NO `<tr>`-leading fragment responses. They are plain server-rendered HTML pages. The only HTMX usage is the global page-refresh anchor (re-using existing `partials/prices_refresh_container.html.j2` triggers IF the operator navigates from dashboard) — Phase 10 surfaces themselves do not inject OOB swaps.

**If a surface gains HTMX interactivity in V2** (e.g., per-cohort tab swap without full-page reload), the V2 dispatch MUST enumerate the three known browser-only failure surfaces explicitly per Phase 5 R1 M1+M2 + Phase 6 I3 + Phase 9 Sub-bundle D R3.

**Operator-witnessed verification gate** (spec §4.9 BINDING): each new surface, on first deploy, requires operator-witnessed browser verification — TestClient passes are necessary but not sufficient. Even a static-rendered HTML page must be loaded in a real browser to verify Jinja template rendering + UTF-8 + base-layout integration. Per-bundle surface budget enumerated at §C.

### §A.10 §4.8 process-grade-trend line chart rendering decision (matplotlib gotcha avoidance)

Spec §4.8 surface composition: "line chart of `process_grade_rolling_N`; per-stage breakdown lines (entry / management / exit); `disqualifying_violation_rate_rolling_N` separate annotation; `mistake_cost_R_rolling_N_total` paired secondary axis."

Two rendering options:

| Option | Pros | Cons |
|---|---|---|
| **(α) Inline SVG via Jinja** | NO matplotlib dep; NO mathtext gotcha; spec §4.9 "No client-side compute" honored; testable via TestClient | Custom SVG generation logic; more LOC for axes/labels |
| **(β) Matplotlib-rendered PNG** | Reuses existing chart sub-skill; faster impl | Inherits the matplotlib mathtext gotcha (CLAUDE.md) — `$ ^ _ \` chars in titles/labels silently corrupt rendering; visual-verification non-optional; PNG cache invalidation surface |

**Default-disposition: (α) inline SVG.** Phase 10 V1 surfaces are HTML-static per spec §4.9; SVG is just markup. `swing/metrics/process_grade_trend.py` produces a list of `(x_index, y_value)` points + the Jinja template emits `<svg>` + `<polyline>` + `<text>` elements. Avoids the matplotlib gotcha entirely. Trade-off: ~80 LOC of SVG generation in the template vs ~30 LOC of matplotlib calls. Acceptable.

**Operator-decision-pending tag:** if operator prefers PNG rendering for the secondary-axis line, plan §A may revise to (β); the executing-plans dispatch for Sub-bundle E inherits whichever default is locked at integration triage.

### §A.11 §3.2 cohort metrics — full hypothesis transition history (per §0.5 §11.3)

Spec §3.2 currently surfaces `latest_status_change_metadata` as "single most-recent transition only" (V1-limitation note: "Migration 0008 stores ONLY the latest `status_changed_at` + `status_change_reason`"). Phase 9 Sub-bundle C closed that gap by adding `hypothesis_status_history` audit table + `swing/data/repos/hypothesis_status_history.py:list_history_for_hypothesis(conn, hypothesis_id)`.

**Phase 10 V1 SUPERSEDES the spec §3.2 V1-limitation** per dispatch brief §0.5 §11.3 default. Surface §4.2 hypothesis-progress card renders FULL transition timeline as a small inline `<ol>` ordered by `effective_from DESC`, capped at the last 5 transitions per cohort (V1 cap; UI brevity). Prior transitions accessible via a per-cohort drill-down `GET /metrics/hypothesis-progress/{hypothesis_id}/history` (V2 candidate; defer if not needed at gate time).

**Spec amendment pending V2.1 §VII.F routing:** banked at return report §6 — the spec text needs an amendment removing the V1-limitation note since the consumer-side gap is closed. Same supersession-recon pattern as Phase 9 Sub-bundle D §7 (sector_industry anchor) + Sub-bundle E §6.2 (multi-line parser).

### §A.11.1 Cohort-temporal-filter inclusion policy for paused intervals (Codex R1 Major #4 fix)

`hypothesis_status_history` (Phase 9 Sub-bundle C) records cohort transitions through `active → paused → active → closed-escaped/closed-target-met`. Phase 10 cohort metrics aggregate trades labeled with the cohort's name regardless of when the cohort was paused. Spec §3.2 + §4.2 + §3.3 + §3.7 are SILENT on whether trades stamped during a paused interval should count toward cohort metrics.

**Locked V1 policy** (binding for Tasks B.1 + B.4 + C.1 + C.2 + C.3): include ALL trades labeled with the cohort regardless of cohort status at trade-time. Rationale:

1. The trade carries the operator's INTENT-at-entry — by stamping the cohort on `trades.hypothesis_label`, the operator declared "this trade belongs to this cohort." Pausing the cohort thereafter does not retroactively un-classify trades.
2. The status-change event is a GOVERNANCE signal (operator's decision to pause investigation) — it is NOT a measurement-validity signal.
3. Excluding paused-period trades would silently shrink cohort sample sizes + change CI computations + change tripwire-distance + create an attack surface for cohort-game-by-pausing.

**V2 candidate** (banked, NOT V1 scope): operator-elective per-cohort filter "Exclude trades stamped during paused intervals" — useful for the §0.4 §11.2 (c) "exclude unresolved discrepancies" filter family. Both filters share the same UI shape: a per-cohort toggle on the §4.1 trade-process card surface. Defer.

**Discriminating tests** (binding in Task B.1):
- `test_cohort_metrics_include_trades_during_paused_interval`: seed cohort with status history active@t0 → paused@t1 → active@t2; seed trade stamped at `pre_trade_locked_at=t1.5` (during paused interval); assert trade IS in cohort_n_closed + contributes to expectancy_R + counts toward consecutive_loss_run.
- `test_hypothesis_progress_card_renders_paused_status_history_alongside_metrics`: timeline shows the active→paused→active transitions; metric cells reflect ALL trades.

**Spec lock**: this is an EXPLICIT V1 policy choice, NOT a spec amendment — spec §3.2 + §3.3 + §3.7 are silent on the question. Document in plan §A as the locked V1 disposition; if operator at integration triage prefers paused-period exclusion, plan §A revises before Sub-bundle B dispatch.

### §A.12 Test fixture USERPROFILE+HOME monkeypatch — applies IFF write-side scope added

Per Phase 9 Sub-bundle A R1 incident (CLAUDE.md gotcha + dispatch brief §0.3 #9), tests touching `swing/config_user.py:write_user_overrides` MUST monkeypatch both `USERPROFILE` AND `HOME` env vars. **Phase 10 V1 is read-side dominant** — no expected new tests touch user-config writes. The §A.4 §8.2 OPEN question (manual snapshot capture web form) is the one path that could introduce the requirement; if elected, the new test fixture in Sub-bundle E MUST monkeypatch both env vars per the locked pattern. Lock as §I.10.

### §A.13 Service-layer transaction discipline — applies IFF new write paths added

Per Phase 8 + Phase 9 arc lock (dispatch brief §0.3 #2 + §7 row 4): caller MUST NOT hold open transaction; service owns BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject-don't-auto-detect. Phase 10 V1 has 0 new write paths. The §A.4 §8.2 OPEN question (manual snapshot capture) is the one path that could introduce the requirement; if elected, the new service in Sub-bundle E MUST mirror Phase 9 Sub-bundle A's `supersede_active_policy` contract. Lock as §I.11.

### §A.14 Form-render hidden-anchor round-trip discipline — applies IFF new POST forms added

Per Phase 9 Sub-bundle D R3 lock (CLAUDE.md gotcha + dispatch brief §0.3 #7+#8): every form-render hidden anchor driving POST-time validation MUST round-trip through soft-warn confirm `form_values` dict. Phase 10 V1 has 0 new POST forms (per §A.3 + §A.9 default). If §8.2 manual snapshot capture is elected, the new form in Sub-bundle E inherits this discipline. Lock as §I.12.

### §A.15 Session-anchor read/write predicate alignment (CLAUDE.md gotcha)

Per CLAUDE.md "Session-anchor read/write mismatch" + Phase 9 polish bundle 2026-05-09 fix family: writer uses backward-looking `last_completed_session(now())` to stamp `review_date` / `data_asof_date` / similar; reader on dashboard / VM / route MUST NOT use forward-looking `action_session_for_run(now())` for the same query. Phase 10 dashboard surfaces query session-keyed columns (e.g., `daily_management_records.review_date`, `account_equity_snapshots.snapshot_date`).

**Per-query session-anchor matrix** (binding):

| Query target | Anchor type | Helper |
|---|---|---|
| `daily_management_records.review_date` | backward-looking | `last_completed_session(datetime.now())` |
| `account_equity_snapshots.snapshot_date` | backward-looking | `last_completed_session(datetime.now())` |
| `pipeline_runs.started_ts` for "today's run" | backward-looking | `last_completed_session(datetime.now())` |
| `daily_management_records.action_session_for_run` (writer-side) | forward-looking | already correctly used by writer; readers query backward |

**Discriminating round-trip integration test pattern** (per CLAUDE.md gotcha): for each session-keyed read predicate added by Phase 10, write a test that (a) calls the writer to insert a row, (b) immediately invokes the reader, (c) asserts the row is visible. This pins read/write alignment + catches future writer-side anchor refactors. Lock as §I.13.

### §A.16 Empty-cohort + zero-trade edge-case rendering (spec §3 + §5 universal)

Phase 10's current production data state per CLAUDE.md status: **n=2 closed + n=3 open = 5 trades total; 4 hypothesis cohorts, all below per-cohort suppression threshold n<3**. The dashboard MUST render gracefully at this state — every spec §4 surface MUST be operator-readable when cohort sample sizes are 0/1/2.

**Lock per surface:**
- §4.1 trade-process card: each per-cohort tab renders the suppression placeholder (spec §5.6 format) for every metric; the "all closed trades" toggle renders n=2 metrics under the 3≤n<5 point-estimate-with-warning policy.
- §4.2 hypothesis-progress card: ALWAYS shown (governance surface); progress bars at 0/target; tripwire indicator at 0 streaks; transition history shows the seed-row entries only.
- §4.3 tier-comparison: ALL CIs suppressed; placeholder "Insufficient cohort samples (need ≥5 per cohort for CI; current: A+: 0, Sub-A+: 0, ...)" per spec §4.3.
- §4.4 capital-friction: point-in-time gauges always shown (with PROVISIONAL badge); multi-run trends suppressed (need ≥5 runs).
- §4.5 maturity-stage: per-position table; for n=0 open positions, render "No open positions to manage" placeholder.
- §4.6 identification-funnel: per-run bar always shown for runs that exist; trend suppressed (need ≥10 runs).
- §4.7 deviation-outcome: each cohort row suppressed at n<5; renders "n too low" per row.
- §4.8 process-grade-trend: per-trade markers always shown; rolling line suppressed (effective_n<5); confidence-floor badge always visible at our n.

**Discriminating regression test** (per surface in Sub-bundles B–E): instantiate each VM with empty / minimal data + assert no AttributeError / TypeError / ZeroDivisionError + assert suppression placeholders render. Lock as §I.14.

### §A.17 Capital-floor convention vs `risk_policy.capital_floor_constant_dollars` (CLAUDE.md memory + spec §2)

CLAUDE.md user-memory `project_capital_risk_floor.md` records the operator's mental sizing model: `max($7,500, actual_account_balance)`. Spec §2 split-policy SUPERSEDES this for governance metrics: governance reads `capital_floor_constant_dollars = $7,500` LITERAL constant from at-trade-time `risk_policy`, NOT `max($7,500, actual)`.

**Per Phase 9 Sub-bundle A**: `risk_policy.capital_floor_constant_dollars` IS shipped at $7,500 (the seed value); `ratify_seed_from_cfg_on_v17_landing` ratified it from `swing.config.toml` at v16→v17 landing.

**Phase 10 lock:** governance metrics (§3.2 `cumulative_R_pct_of_capital`, `distance_to_absolute_loss_tripwire`) read `capital_floor_constant_dollars` from AT-TRADE-TIME risk_policy (per §A.5). Operational metrics (§3.4 + §3.5) use the dynamic PROVISIONAL/LIVE resolver (per §A.6) which falls back to `capital_floor_constant_dollars` (NOT `max($7,500, actual)`) when no snapshot exists — the user-memory `max(...)` semantic is the operator's mental model, NOT a system-computed value. Operator may record snapshots at any cadence to flip PROVISIONAL → LIVE per their own `actual_account_balance` mental model.

### §A.18 Reconciliation-discrepancy badge composition path (per §0.5 §11.2 (a)) — Codex R2 Major #6 restructured

Phase 10 adds a global "N unresolved material discrepancies" badge surfaced in `base.html.j2` (rendered alongside the `vm.stale_banner` block — same precedent). Codex R2 Major #6 catch: prior plan placed `swing/metrics/discrepancies.py` + the helper in Sub-bundle E, BUT each metrics VM in Sub-bundles B/C/D landed BEFORE E and would have to be retrofitted. Restructured composition:

1. **Sub-bundle A** lands `swing/metrics/discrepancies.py:count_unresolved_material(conn) -> int` (helper) + `BaseLayoutVM.unresolved_material_discrepancies_count: int = 0` field. The helper wraps `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + `list_unresolved_material_for_closed_trades` and returns `len(...)` summed.
2. **Sub-bundles B + C + D** — each new metrics VM constructor populates the field via the helper FROM THE START (`unresolved_material_discrepancies_count=count_unresolved_material(conn)` in every `build_*_vm` and `MetricsIndexVM` constructor). NO retrofit required in E.
3. **Sub-bundle E** lands the `base.html.j2` banner block + updates the 6 EXISTING base-layout VM constructors (`build_dashboard`, `build_pipeline`, `build_journal`, `build_watchlist`, `build_config_vm`, `PageErrorVM`) to populate the field. Cross-bundle pin via the discriminating regression test in Task A.7 (un-skipped at E.3).

`base.html.j2` rendering (Sub-bundle E):

```jinja2
{% if vm.unresolved_material_discrepancies_count > 0 %}
<div class="banner">⚠ {{ vm.unresolved_material_discrepancies_count }} unresolved material reconciliation discrepancies — <a href="/journal/discrepancies">review</a></div>
{% endif %}
```

**Note on (b) + (c) per §A.4 default-disposition: DEFER** — the per-trade indicator + per-cohort filter are NOT in V1.

### §A.19 Spec §3.4 `risk_feasibility_blocked_rate` computation (criterion-table query)

Spec §3.4 metric definition: `count(candidates with risk_feasibility=False) / count(candidates with all_other_criteria=True) per pipeline run`. The metric measures "of the candidates that would have qualified except for risk_feasibility, what fraction were blocked by risk_feasibility?" — both numerator AND denominator MUST share the "all OTHER criteria pass" predicate; otherwise candidates failing risk_feasibility AND additional criteria inflate the numerator + the rate exceeds 100%.

**Locked Codex R1 Major #1 fix:** numerator restricted to "fails risk_feasibility AND all other criteria pass" — matches spec semantics + bounds the rate to [0, 1].

**Implementation pattern** (locked in `swing/metrics/capital.py`):

The `criterion_results.result` enum is `('pass', 'fail', 'na')` per `swing/data/migrations/0001_phase1_initial.sql:52`. Spec §3.4 reads "all_other_criteria=True" — only `result='pass'` qualifies. Both `'fail'` and `'na'` disqualify a candidate from the would-have-qualified denominator (Codex R2 Major #3 lock).

**Codex R4 Major #3 lock — `risk_feasibility='na'` is "not assessed", excluded from BOTH sides:** a candidate with `risk_feasibility` result `'na'` is NOT a subject of the BLOCKED rate (the criterion was not evaluated, so we cannot say it was "blocked"). Filter denominator to candidates with `risk_feasibility` result in `('pass', 'fail')` ONLY.

```sql
-- denominator: candidates per run where (a) ALL non-risk_feasibility criteria PASS,
-- AND (b) risk_feasibility itself is either 'pass' or 'fail' (NOT 'na' — Codex R4 Major #3).
WITH would_have_qualified_except_risk AS (
  SELECT c.id AS candidate_id
  FROM candidates c
  WHERE c.evaluation_run_id = :run_id
    AND NOT EXISTS (
      SELECT 1 FROM criterion_results cr2
      WHERE cr2.candidate_id = c.id
        AND cr2.criterion_name <> :risk_feasibility_name
        AND cr2.result <> 'pass'
    )
    AND EXISTS (
      SELECT 1 FROM criterion_results cr3
      WHERE cr3.candidate_id = c.id
        AND cr3.criterion_name = :risk_feasibility_name
        AND cr3.result IN ('pass', 'fail')
    )
)
-- numerator: candidates in the would-have-qualified-AND-risk-was-assessed set
-- that fail risk_feasibility.
SELECT
  (SELECT COUNT(*) FROM would_have_qualified_except_risk w
     JOIN criterion_results cr ON cr.candidate_id = w.candidate_id
     WHERE cr.criterion_name = :risk_feasibility_name AND cr.result = 'fail') AS numerator,
  (SELECT COUNT(*) FROM would_have_qualified_except_risk) AS denominator
```

`:risk_feasibility_name` parameter sourced from `from swing.evaluation.criteria.risk_feasibility import NAME` to avoid string-literal drift.

**Completeness assumption** (Codex R3 Major #3): the `NOT EXISTS ... result <> 'pass'` predicate treats a MISSING criterion row (no row at all in `criterion_results` for a given candidate × criterion_name) as IMPLICIT pass. That is correct ONLY when `criterion_results` is fully materialized by `_step_evaluate` (the canonical pipeline writer) for every candidate. Production pipeline writes ALL criteria for every candidate per current evaluation logic; partial materialization can only happen via:
- Custom-inserted candidate rows bypassing `_step_evaluate` (operator-supplied; should never happen in V1).
- Database corruption / partial restore.
- Future `_step_evaluate` refactor that introduces lazy-materialization (V2 risk).

**Defensive guard** (binding in `swing/metrics/capital.py`; Codex R4 Major #1+#2 fix — set-membership comparison + correct enumeration):

The helper exposes a `EXPECTED_CRITERIA_NAMES: frozenset[str]` constant. The shipped evaluators emit names via mixed conventions (per `swing/evaluation/criteria/*.py` recon):

```python
# swing/metrics/capital.py
from swing.evaluation.criteria import (
    adr, ma_stack_short, orderliness, prior_trend, proximity, pullback,
    risk_feasibility, tightness, trend_template, vcp,
)

EXPECTED_CRITERIA_NAMES: frozenset[str] = frozenset({
    adr.NAME,                       # "adr"
    ma_stack_short.STACK_NAME,      # "ma_stack_10_20_50"
    ma_stack_short.RISING_NAME,     # "ma_short_rising"
    orderliness.NAME,               # "orderliness"
    prior_trend.NAME,               # "prior_trend"
    proximity.NAME,                 # "proximity_20ma"
    pullback.NAME,                  # "pullback"
    risk_feasibility.NAME,          # "risk_feasibility"
    tightness.NAME,                 # "tightness"
    vcp.NAME,                       # "vcp_volume_contraction"
    *trend_template.CHECK_NAMES,    # 8 entries TT1_..._above_150_200 through TT8_rs_rank
})
# Total: 18 expected criterion_name values.
```

**Set-membership guard** (Codex R4 Major #2): the helper computes `actual_names_for_candidate = {row.criterion_name for row in criterion_results WHERE candidate_id=c.id}`. Candidates with `not EXPECTED_CRITERIA_NAMES.issubset(actual_names_for_candidate)` are EXCLUDED from BOTH numerator AND denominator + `WARNING` log emitted: `"risk_feasibility_blocked_rate: candidate_id=X missing expected criteria {missing_set}; excluding from rate computation"`.

This catches BOTH (a) "missing required criterion" AND (b) "extra unknown criterion in the row but missing one of the expected" — the count-only check would have been fooled by case (b).

**Unexpected-name advisory** (Codex R4 Major #2 follow-up): when `actual_names_for_candidate - EXPECTED_CRITERIA_NAMES` is non-empty (extra unknown criteria present), emit a SEPARATE INFO log: `"risk_feasibility_blocked_rate: candidate_id=X has unexpected criterion names {extra_set}; included anyway"`. Does NOT exclude the candidate (extras don't change the rate semantics; only missing required names do). V2 candidate: tighten to exclude on extras when criterion-set is locked.

**Discriminating tests** (binding in Task D.1):
- `test_risk_feasibility_blocked_rate_excludes_candidates_failing_other_criteria`: seed candidate that fails risk_feasibility AND fails MA-stack → NOT in numerator; rate stays bounded.
- `test_risk_feasibility_blocked_rate_excludes_candidates_with_na_on_other_criteria` (Codex R2 Major #3): seed candidate that fails risk_feasibility AND has another criterion `result='na'` → NOT in denominator (since `na` is not `pass`); assert rate excludes it.
- `test_risk_feasibility_blocked_rate_excludes_candidates_with_na_on_risk_feasibility` (Codex R4 Major #3): seed candidate with all-other-criteria=pass AND `risk_feasibility` result `'na'` → excluded from BOTH numerator AND denominator (na on risk_feasibility = "not assessed" ≠ blocked).
- `test_risk_feasibility_blocked_rate_excludes_candidates_with_partial_criteria_rows` (Codex R3 Major #3 + R4 Major #2): seed candidate with only 3 of 18 EXPECTED_CRITERIA_NAMES rows → excluded from BOTH numerator AND denominator; assert WARNING log line emitted naming candidate_id + missing_set.
- `test_risk_feasibility_blocked_rate_set_membership_guard_catches_missing_plus_extra` (Codex R4 Major #2): seed candidate with 18 criterion_results rows where 1 expected name is missing AND 1 unknown name is present (counts match expected count = 18, but membership is wrong) → excluded from numerator AND denominator + WARNING log emitted. Discriminates set-membership guard against count-only guard.
- `test_risk_feasibility_blocked_rate_extra_names_logs_info_not_excluded` (Codex R4 Major #2): seed candidate with all 18 expected names present + 1 extra unknown name → INCLUDED in computation + INFO log emitted naming the extra.
- `test_risk_feasibility_blocked_rate_expected_criteria_names_set_matches_pipeline_writer` (Codex R4 Major #1): assert `EXPECTED_CRITERIA_NAMES == {names actually written by _step_evaluate when given a synthetic candidate that exercises all evaluators}` — pins the constant against the pipeline. Discriminates against `*.NAME` undercount (Codex R4 Major #1 catch).
- `test_risk_feasibility_blocked_rate_at_most_1`: every candidate either fails risk_feasibility (and others pass) or passes risk_feasibility (and others pass) → rate ∈ [0, 1].
- `test_risk_feasibility_blocked_rate_at_zero_qualifying_returns_suppressed`: zero candidates would-have-qualified → return suppressed text "N/A — 0 would-have-qualified candidates this run" (NOT 0/0 = NaN).

### §A.20 Spec §3.6 `aplus_take_rate_per_run` denominator (zero-A+ runs)

Spec §3.6 `aplus_take_rate_per_run = aplus_trades_taken_per_run / aplus_identifications_per_run`. When a run has 0 A+ identifications, the denominator is 0. Per spec §5.5 per-pipeline-run special case: rendered as a per-run point estimate (Class A applies to the trend-window-n; the per-run snapshot itself is rate-class but not subject to standard suppression). Codex R3 Minor #1 citation fix: spec classifies aplus_take_rate_per_run as Class A (rate metric) per spec §5.1 + the §5.5 per-run special case — NOT spec §5.3 (ratio class with win-loss diversity, which applies to profit_factor / payoff_ratio). The zero-denominator behavior remains: render suppressed `"N/A — 0 A+ identifications this run"` (NOT 0.0, NOT NaN, NOT +inf).

No `watch_take_rate_per_run` in V1 (Codex R2 Major #2 fix; spec §3.6 does not define it; banked as V2 candidate per Codex R1 Minor #2 + Task D.5 acceptance).

### §A.21 Spec §3.8 rolling metric Class assignments (Codex R1 Major #6 fix — match spec §5.2 verbatim)

Spec §3.8 lists 7 rolling metrics; spec §5.4 Class D applies to "rolling-window metrics" (window-fullness badge + per-trade-points-always). Spec §5.2 Class B explicitly lists `mistake_cost_R_rolling_N_per_trade` in its applies-to roster ("mean / sum-over-fixed-denominator metrics"). The two classes are NOT mutually exclusive — Class D governs LINE rendering (drawability gating on window-fullness); Class B governs VALUE CI rendering (bootstrap CI on the window's samples for the per-window mean value).

**Phase 10 lock — spec-conformant (NOT spec-amendment):**

| §3.8 metric | Class D rendering (line) | Class B CI rendering (value) |
|---|---|---|
| `process_grade_rolling_N` | rolling line + window-fullness/confidence-floor badges per §5.4 | bootstrap CI on the per-window mean per §5.2 |
| `entry_grade_rolling_N` | same | bootstrap CI on per-window mean |
| `management_grade_rolling_N` | same | bootstrap CI on per-window mean |
| `exit_grade_rolling_N` | same | bootstrap CI on per-window mean |
| `disqualifying_violation_rate_rolling_N` | rolling line per §5.4 | Wilson CI on window's k/n per §5.1 Class A (rate metric, not mean) |
| `mistake_cost_R_rolling_N_total` | rolling line per §5.4 | point estimate ONLY (sum, not mean — §5.2 framing of "sum-over-fixed-denominator" doesn't yield a bootstrap CI on a window sum; alternative point estimate is the V1 honest rendering) — this is the ONE deliberate spec-conformance deviation, banked as a V2.1 §VII.F amendment candidate at return report §6 |
| `mistake_cost_R_rolling_N_per_trade` | rolling line per §5.4 | bootstrap CI on per-window mean per §5.2 |

**Bootstrap on small windows (N=10) yields wide intervals — that is the HONEST signal.** Spec §5 R3 M2 lock decouples window-fullness from confidence-floor for exactly this reason: a 10-trade window CAN draw a line (cadence signal); the confidence-floor warning persists until effective_n ≥ 20 (statistical signal); the bootstrap CI conveys interval width at the current effective_n.

**`honesty.py:render_class_d` extension** (binding for Task A.1 + Task E.1): the 3-tuple return shape (value, badges, drawability_text) per §A.7 is preserved; the VALUE field carries either `BootstrapCI` (when Class B CI applies) OR `WilsonCI` (when Class A applies) OR `float | None` (when only point estimate per `mistake_cost_R_rolling_N_total` exception). Updated `render_class_d` signature per §A.7:

```python
# Codex R3 Major #1: §A.21 signature MUST match §A.7 exactly. See §A.7 for canonical
# `render_class_d(...)` with `events_in_window` (Class A) + `n_wins` / `n_losses` (Class C)
# parameters. The §A.7 definition is binding; this snippet exists only as a reference
# pointer.
```

**Discriminating tests** (binding in Task A.1 + Task E.1):
- `test_render_class_d_with_underlying_b_returns_bootstrap_ci_in_value_slot`.
- `test_render_class_d_with_underlying_a_returns_wilson_ci_in_value_slot`.
- `test_render_class_d_with_underlying_point_returns_float_in_value_slot`.
- `test_mistake_cost_R_rolling_N_per_trade_renders_with_bootstrap_ci`: assert BootstrapCI returned in value slot.
- `test_mistake_cost_R_rolling_N_total_renders_point_only`: assert float returned (no CI).

**Banked as V2.1 §VII.F amendment candidate at return report §6:** the spec §3.8 + §5.2 mapping for `mistake_cost_R_rolling_N_total` (sum-class with bootstrap CI) is ambiguous — V1 renders as point-only; operator may revise.

### §A.22 Test count + ruff baseline (worktree-side)

Worktree baseline at branch creation: **2767 fast passing + 5 skipped (4 thinkorswim/*.csv fixture-absent + 1 Task 7.3 operator-only)**. 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions; carry through Phase 10 unchanged. Ruff baseline: **18** (E501 only). EXPECTED_SCHEMA_VERSION: **17**.

**Per-bundle test projection** (§J.3 totals):
- Sub-bundle A: +35..+55 (honesty utility + cohort + rolling + equity_resolver + module-skeleton tests + base-layout-coverage regression).
- Sub-bundle B: +40..+65 (trade-process card + hypothesis-progress card; per-cohort + empty-state + base-layout-VM tests).
- Sub-bundle C: +30..+45 (tier-comparison + deviation-outcome; CI suppression + cohort-comparison rendering).
- Sub-bundle D: +50..+75 (capital-friction + maturity-stage + identification-funnel; PROVISIONAL/LIVE flip + per-position rendering + per-run aggregation).
- Sub-bundle E: +25..+45 (process-grade-trend + reconciliation badge + Phase 11 hand-off).

**Cumulative arc projection: +180..+285 fast tests** (final ~2947..~3052). Below Phase 9's +503 because Phase 10 has no schema and no migration runner work.

### §A.23 Suggested dispatch order — A → B → C → D → E

Locked rationale:
- **A first**: shared honesty utility + module skeleton + base-layout-VM coverage regression. Sub-bundles B/C/D/E mock-against-A's interface where helpful (per §A.7 locked interface).
- **B next**: trade-process card + hypothesis-progress card consume A's `render_class_a` + `render_class_b` + `cohort.py` filter; exercise the LIVE policy + AT-TRADE-TIME policy split (per §A.5). Most operator-visible cohort surfaces.
- **C next**: tier-comparison + deviation-outcome reuse B's per-cohort scaffolding; add 4-cohort side-by-side comparison + `cohort_ci_overlap_descriptor` text.
- **D next**: operational/live-state surfaces (capital-friction + maturity-stage + identification-funnel). Exercises PROVISIONAL/LIVE dynamic badge (per §A.6) + per-pipeline-run on-the-fly aggregation (per §A.0.1). Highest schema-coverage bundle.
- **E last**: process-grade-trend + reconciliation badge + Phase 11 hand-off prep. Smallest scope but locks the cross-bundle base-layout banner integration (per §A.18).

**Cross-bundle dependency graph** (Codex R4 Minor #1 update — reflects §A.18 restructure):
- A → {B, C, D, E} (honesty utility module is binding interface).
- A → {B, C, D, E} (`BaseLayoutVM` mixin is binding base-class).
- A → {B, C, D, E} (`swing/metrics/discrepancies.py:count_unresolved_material` from Task A.7.1 is consumed by every metrics-VM constructor for `unresolved_material_discrepancies_count` field population).
- B → C (cohort scaffolding reuse; non-binding but recommended).
- B → D (per-cohort filter helper reuse).
- D → E (PROVISIONAL/LIVE resolver pattern reuse for per-run aggregation).
- §A.18 reconciliation badge — TWO populating paths (Codex R2 Major #6 restructure):
  - **Metrics VMs (A index, B trade-process + hyp-progress, C tier + deviation, D capital + maturity + funnel, E process-grade-trend)**: each metrics-VM constructor populates `vm.unresolved_material_discrepancies_count = count_unresolved_material(conn)` FROM ITS SUB-BUNDLE LANDING — NO retrofit in E.
  - **Existing 6 base-layout VMs (Dashboard, Pipeline, Journal, Watchlist, Config, PageError)**: field added + populated in Sub-bundle E Task E.3 (the ONLY retrofit step). The cross-bundle pin is the un-skipped `test_existing_dashboard_vm_has_unresolved_material_field` from T-A.7.

### §A.24 Operator-paced action items (NOT writing-plans blockers)

1. **Operator may record fresh `account_equity_snapshots` rows before Sub-bundle D operator-witnessed gate** so the PROVISIONAL → LIVE flip is visible during the gate. Per CLI shipped Phase 9 Sub-bundle C: `swing account snapshot record --equity-dollars <amt> --source manual`. Production state at writing-plans time: 2 snapshots (id=1 $2000 at 2026-05-11; id=2 $1800 at 2026-04-01 back-recorded). Operator-paced; NOT plan-blocking.

2. **Operator may opt-in to the §0.4 §8.2 web-form manual snapshot capture surface at integration triage of this plan.** Default is CLI-only. If elected, Sub-bundle E gains +1 task (manual_snapshot_form route + handler + template + test).

3. **Operator may opt-in to §0.4 §8.4 Corporate_Actions MVP at integration triage.** Default is DEFER. If elected, the plan gains a new Sub-bundle F (~3-6hr scope; +1 table + +1 CLI + +1 manual-reconcile flow).

4. **Operator may opt-in to §0.4 §8.6 lucky_violation_R surface on review form at integration triage.** Default is DEFER (separate small follow-up dispatch). If elected, Sub-bundle B gains +1 task.

---

## §B — File map

### Files to CREATE

**Module:**
- `swing/metrics/__init__.py` — public re-exports.
- `swing/metrics/honesty.py` — spec §5 implementation per §A.7 interface.
- `swing/metrics/policy.py` — risk_policy LIVE/AT-TRADE-TIME split helpers.
- `swing/metrics/equity_resolver.py` — `resolve_live_capital_denominator_dollars` per §A.6.
- `swing/metrics/cohort.py` — per-hypothesis-cohort filter + aggregation.
- `swing/metrics/rolling.py` — rolling-N window helper.
- `swing/metrics/funnel.py` — identification-vs-trade-funnel helper.
- `swing/metrics/process.py` — §3.1 trade-process metric computations.
- `swing/metrics/capital.py` — §3.4 capital-friction metric computations (incl. §A.19 risk_feasibility_blocked_rate).
- `swing/metrics/maturity.py` — §3.5 maturity-stage metric computations.
- `swing/metrics/tier.py` — §3.3 + §3.7 tier-comparison + deviation-outcome.
- `swing/metrics/process_grade_trend.py` — §3.8 rolling-grade trend.
- `swing/metrics/discrepancies.py` — `count_unresolved_material` (Sub-bundle E).

**View-models:**
- `swing/web/view_models/metrics/__init__.py` — public re-exports.
- `swing/web/view_models/metrics/shared.py` — `BaseLayoutVM` mixin + shared `ConfidenceBadgeVM` + `ProvisionalBadgeVM` + `SuppressionRowVM` dataclasses.
- `swing/web/view_models/metrics/index.py` — `MetricsIndexVM` for `GET /metrics`.
- `swing/web/view_models/metrics/trade_process_card.py` — `TradeProcessCardVM`.
- `swing/web/view_models/metrics/hypothesis_progress_card.py` — `HypothesisProgressCardVM`.
- `swing/web/view_models/metrics/tier_comparison.py` — `TierComparisonVM`.
- `swing/web/view_models/metrics/capital_friction.py` — `CapitalFrictionVM`.
- `swing/web/view_models/metrics/maturity_stage.py` — `MaturityStageVM`.
- `swing/web/view_models/metrics/identification_funnel.py` — `IdentificationFunnelVM`.
- `swing/web/view_models/metrics/deviation_outcome.py` — `DeviationOutcomeVM`.
- `swing/web/view_models/metrics/process_grade_trend.py` — `ProcessGradeTrendVM`.

**Routes:**
- `swing/web/routes/metrics.py` — single FastAPI router with 9 GET endpoints per §A.3.

**Templates:**
- `swing/web/templates/metrics/index.html.j2`
- `swing/web/templates/metrics/trade_process_card.html.j2`
- `swing/web/templates/metrics/hypothesis_progress_card.html.j2`
- `swing/web/templates/metrics/tier_comparison.html.j2`
- `swing/web/templates/metrics/capital_friction.html.j2`
- `swing/web/templates/metrics/maturity_stage.html.j2`
- `swing/web/templates/metrics/identification_funnel.html.j2`
- `swing/web/templates/metrics/deviation_outcome.html.j2`
- `swing/web/templates/metrics/process_grade_trend.html.j2`
- `swing/web/templates/metrics/partials/honesty_badges.html.j2` — shared rendering of confidence/PROVISIONAL/suppression badges.
- `swing/web/templates/metrics/partials/cohort_tabs.html.j2` — shared per-cohort tab navigation.

**Tests:**
- `tests/metrics/__init__.py`
- `tests/metrics/test_honesty.py`
- `tests/metrics/test_policy.py`
- `tests/metrics/test_equity_resolver.py`
- `tests/metrics/test_cohort.py`
- `tests/metrics/test_rolling.py`
- `tests/metrics/test_funnel.py`
- `tests/metrics/test_process.py`
- `tests/metrics/test_capital.py`
- `tests/metrics/test_maturity.py`
- `tests/metrics/test_tier.py`
- `tests/metrics/test_process_grade_trend.py`
- `tests/metrics/test_discrepancies.py`
- `tests/web/test_view_models/test_metrics_vms.py` — per-VM construction + base-layout-fields coverage + empty-cohort rendering.
- `tests/web/test_view_models/test_base_layout_vm_coverage.py` — discriminating regression per §A.8.
- `tests/web/test_routes/test_metrics_routes.py` — TestClient per-endpoint smoke + 200 + base-layout-render verification.
- `tests/integration/test_phase10_metrics_e2e.py` — end-to-end happy path (Sub-bundle E task).

**Verification script** (Codex R2 Major #5):
- `verify_phase10.py` — worktree-root cross-platform verification suite per §J.2 (Sub-bundle A T-A.9 lands; subsequent sub-bundles inherit + invoke at end of dispatch).

### Files to MODIFY

- `swing/web/app.py` — register `metrics.router` (one-liner add).
- `swing/web/view_models/dashboard.py` (`DashboardVM`) — add `unresolved_material_discrepancies_count: int = 0` field per §A.18.
- `swing/web/view_models/pipeline.py` (`PipelineVM`) — same field add.
- `swing/web/view_models/journal.py` (`JournalVM`) — same field add.
- `swing/web/view_models/watchlist.py` (`WatchlistVM`) — same field add.
- `swing/web/view_models/config.py` (`ConfigVM`) — same field add.
- `swing/web/view_models/error.py` (`PageErrorVM`) — same field add.
- `swing/web/templates/base.html.j2` — render the unresolved-material banner block per §A.18 step 4.
- `swing/web/view_models/dashboard.py` (`build_dashboard`) — populate `unresolved_material_discrepancies_count` from `count_unresolved_material(conn)`.
- `swing/web/view_models/pipeline.py` (`build_pipeline`) — same populate.
- `swing/web/view_models/journal.py` (`build_journal`) — same populate.
- `swing/web/view_models/watchlist.py` (`build_watchlist`) — same populate.
- `swing/web/view_models/config.py` (`build_config_vm`) — same populate.
- (every metrics VM constructor populates inline; no separate `build_*` since instantiated per-route.)
- `swing/web/templates/dashboard.html.j2` (or wherever the top nav is rendered) — add `<a href="/metrics">Metrics</a>` link.

### Files NOT modified (explicit phase isolation)

- `swing/data/migrations/*.sql` — no new migration; v17 is current.
- `swing/data/models.py` — no new dataclasses (Phase 9's `RiskPolicy`, `AccountEquitySnapshot`, `HypothesisStatusHistory`, etc. are consumed read-only).
- `swing/data/repos/*.py` — no new repo functions; Phase 10 reads via shipped helpers (`get_active_policy`, `get_policy_by_id`, `get_latest_snapshot_on_or_before`, `list_history_for_hypothesis`, `list_unresolved_material_for_*`, `list_classifications_for_run`, etc.).
- `swing/trades/*.py` — no new services. Phase 10 consumes shipped derivation helpers (`derived_metrics`, `equity`, `review`).
- `swing/cli.py` — no new CLI groups. (V2 may add `swing metrics show <surface>` for headless rendering; out of V1 scope.)
- `swing/data/db.py` — `EXPECTED_SCHEMA_VERSION` stays at 17.
- `swing/pipeline/runner.py` — Phase 10 consumes pipeline_runs read-only.

---

## §C — Sub-bundle decomposition + dispatch ordering

5 sub-bundles, dispatched A → B → C → D → E per §A.23. Each sub-bundle is a single executing-plans dispatch on its own worktree branch (`phase10-bundle-{A,B,C,D,E}-<topic>`).

### Per-bundle scope summary + operator-witnessed gate-surface count

| Bundle | Scope | Gate surfaces | Estimated dispatch time |
|---|---|---|---|
| A | Shared utility + infra + base-layout-VM coverage | 0 surfaces (foundation; tests-only gate) | ~6-9 hr |
| B | §4.1 trade-process card + §4.2 hypothesis-progress card | 2 surfaces + 1 fixture-state | ~8-12 hr |
| C | §4.3 tier-comparison + §4.7 deviation-outcome | 2 surfaces | ~6-10 hr |
| D | §4.4 capital-friction + §4.5 maturity-stage + §4.6 identification-funnel | 3 surfaces + 1 PROVISIONAL/LIVE flip | ~8-12 hr |
| E | §4.8 process-grade-trend + reconciliation badge + Phase 11 hand-off | 1 surface + 1 banner integration + global metrics index | ~6-9 hr |

**Per-bundle gate session ≤ 6 surfaces** (per dispatch brief §1.3 budget); all 5 bundles fit within one operator session each.

**Cross-bundle dependencies (binding):**
- A is a prerequisite for B/C/D/E (interface contract per §A.7).
- E integrates the reconciliation badge across ALL prior surfaces — must run last.
- B's per-cohort scaffolding is reused (non-binding) by C + D.

---

## §D — Sub-bundle A: Shared honesty utility + metric infrastructure

**Goal:** Land `swing/metrics/` module skeleton + the §5 honesty utility module + the per-cohort filter + rolling-window helper + equity resolver + base-layout-VM coverage regression. ZERO new dashboard surfaces in this bundle. All Sub-bundles B–E consume this bundle's interface.

**Branch:** `phase10-bundle-A-shared-honesty-utility`. Worktree branching point: current `main` HEAD at sub-bundle A dispatch time.

**Files in scope (per §B):** all `swing/metrics/*.py` (honesty + policy + equity_resolver + cohort + rolling) + `swing/web/view_models/metrics/__init__.py` + `swing/web/view_models/metrics/shared.py` + `tests/metrics/test_{honesty,policy,equity_resolver,cohort,rolling}.py` + `tests/web/test_view_models/test_base_layout_vm_coverage.py`.

### Task A.0: Module skeleton — `swing/metrics/__init__.py` + empty submodules

**Files:**
- Create: `swing/metrics/__init__.py` (re-export placeholder; will fill in per task).
- Create: `swing/metrics/honesty.py` (empty module placeholder for the import surface).
- Create: `swing/metrics/policy.py`, `equity_resolver.py`, `cohort.py`, `rolling.py`, `funnel.py`, `process.py`, `capital.py`, `maturity.py`, `tier.py`, `process_grade_trend.py`, `discrepancies.py` (empty modules — will fill in subsequent tasks; Sub-bundles D+E land funnel/process/capital/maturity/tier/process_grade_trend/discrepancies).
- Create: `swing/web/view_models/metrics/__init__.py`.
- Create: `swing/web/view_models/metrics/shared.py` (will fill in Task A.6).

- [ ] **Step 1: Create empty modules**

```bash
mkdir -p swing/metrics swing/web/view_models/metrics tests/metrics
```

Create `swing/metrics/__init__.py` with content:

```python
"""Phase 10 metrics dashboard utility module.

Public surface:
- honesty.py: spec §5 low-sample-size honesty policy.
- policy.py: risk_policy LIVE vs AT-TRADE-TIME read split (spec §0.5 §11.1).
- equity_resolver.py: live_capital_denominator_dollars resolver (spec §0.5 §11.4).
- cohort.py: per-hypothesis-cohort filter + aggregation.
- rolling.py: rolling-N window helper (spec §3.8 Class D).
- funnel.py: identification-vs-trade-funnel helper.
- process.py: §3.1 trade-process metric computations.
- capital.py: §3.4 capital-friction metric computations.
- maturity.py: §3.5 maturity-stage metric computations.
- tier.py: §3.3 + §3.7 tier-comparison + deviation-outcome.
- process_grade_trend.py: §3.8 rolling-grade trend.
- discrepancies.py: §0.5 §11.2(a) reconciliation badge count.
"""
```

Create empty placeholder modules with single docstring line each.

- [ ] **Step 2: Skeleton import test passes**

```bash
python -c "from swing import metrics; from swing.metrics import honesty, policy, equity_resolver, cohort, rolling, funnel, process, capital, maturity, tier, process_grade_trend, discrepancies"
```

Expected: clean import; no errors.

- [ ] **Step 3: Commit**

```bash
git add swing/metrics/ swing/web/view_models/metrics/
git commit -m "feat(metrics): scaffold swing/metrics module skeleton (Phase 10 Sub-bundle A T-A.0)"
```

### Task A.1: Honesty utility — Wilson CI + bootstrap CI + suppression dispatcher

**Files:**
- Modify: `swing/metrics/honesty.py` (full implementation).
- Create: `tests/metrics/test_honesty.py`.

**Acceptance criteria:**
- Implements §A.7 interface verbatim (dataclass shapes + function signatures).
- `WilsonCI`, `BootstrapCI`, `SuppressedMetric` carry `__post_init__` validators per §A.7 (NaN/inf rejection + invariant assertions).
- Wilson CI computed pure-Python (no scipy); matches reference values for k=2,n=4 → [0.094, 0.901] (within 1e-3); k=0,n=20 → [0.000, 0.161]; k=20,n=20 → [0.839, 1.000].
- Bootstrap CI uses `random.Random(rng_seed)` for determinism. Test asserts deterministic output for seeded run.
- `suppress_for_n` reads `policy.global_confidence_floor_n` for badge visibility, NOT cohort target.
- `render_class_d` returns 3-tuple (value, badges, drawability_text) per §A.7.

**Discriminating tests:**
- `test_wilson_ci_known_values`: hardcoded triplets per acceptance.
- `test_wilson_ci_rejects_invalid_n_or_k`: `n=-1`, `k>n`, `k<0` raise.
- `test_bootstrap_ci_deterministic_with_seed`: same seed → same bounds.
- `test_bootstrap_ci_resample_count_from_policy`: Mock policy.bootstrap_resample_count=500; assert resample_count==500 in returned BootstrapCI.
- `test_suppress_for_n_below_3`: returns SuppressedMetric with placeholder per spec §5.6 format.
- `test_suppress_for_n_at_or_above_floor`: returns None.
- `test_render_class_a_n_5_returns_wilson_ci_with_warning`: HonestyBadges.confidence_floor_warning=True.
- `test_render_class_a_n_20_returns_wilson_ci_no_warning`: confidence_floor_warning=False.
- `test_render_class_b_bootstrap_with_warning_below_floor`: same.
- `test_render_class_c_no_wins_returns_suppressed`: spec §5.3 "Insufficient outcome diversity".
- `test_render_class_c_no_losses_returns_suppressed`: same.
- `test_render_class_d_window_full_below_floor`: line drawable +
  confidence_floor_warning (effective_n=N=10 → window_not_full=False).
- `test_render_class_d_partial_window`: line drawable
  (5 <= effective_n < N) + window_not_full_warning=True +
  confidence_floor_warning=True per spec §5.4 second band. Sub-bundle A
  R1 Major #1 amended the prior "line not drawable" wording to match the
  spec — line IS drawable from effective_n>=5; the partial-window state
  is conveyed via the new ``HonestyBadges.window_not_full_warning`` field.
- `test_post_init_rejects_nan_inf`: WilsonCI(point=float('nan'), ...) raises; same for inf.
- `test_post_init_rejects_lower_above_point`: assertion error.

**Suggested commit shape:** `feat(metrics): honesty utility — Wilson CI + bootstrap CI + suppression dispatcher (T-A.1)`

**Watch items:**
- Use a fixed RiskPolicy fixture (`policy.global_confidence_floor_n=20`, `bootstrap_resample_count=1000`, all class thresholds at spec defaults) constructed via `swing.data.models.RiskPolicy(...)` — DO NOT instantiate via `get_active_policy(conn)` in unit tests; pass policy as a parameter. Decoupling per §A.5.
- Test fixture MUST construct `RiskPolicy` with all 34 fields (use `dataclasses.fields(RiskPolicy)` + dict comprehension to default all unrelated fields to safe values). Phase 9 Sub-bundle A locked this dataclass; spec §A.7 does not redefine.

### Task A.2: Risk_policy resolver — LIVE vs AT-TRADE-TIME split

**Files:**
- Modify: `swing/metrics/policy.py`.
- Create: `tests/metrics/test_policy.py`.

**Acceptance criteria:**
- Function `read_live_policy(conn) -> RiskPolicy` thin wrapper over `swing.data.repos.risk_policy.get_active_policy`.
- Function `read_at_trade_time_policy(conn, *, trade: Trade) -> RiskPolicy` resolves `trade.risk_policy_id_at_lock`; falls back to `read_live_policy(conn)` with a `[legacy: pre-Phase-9 trade]` annotation flag returned alongside via tuple `(RiskPolicy, bool)` where bool=True means "fallback applied".
- Function `read_at_review_time_policy(conn, *, review_log: ReviewLog) -> tuple[RiskPolicy, bool]` mirrors for review_log.risk_policy_id_at_review_completion.

**Discriminating tests:**
- `test_read_live_policy_returns_active`: seed 2 policies (active + superseded); assert returns active.
- `test_read_at_trade_time_uses_stamp`: seed trade with risk_policy_id_at_lock=2; assert returns policy 2 (NOT active).
- `test_read_at_trade_time_falls_back_for_null`: seed legacy trade with stamp=NULL; assert returns active + bool=True.
- `test_read_at_trade_time_falls_back_for_orphaned_id`: seed trade with stamp=999 (nonexistent); assert returns active + bool=True (defensive; FK SHOULD prevent this but production data integrity edge).

**Suggested commit shape:** `feat(metrics): risk_policy LIVE vs AT-TRADE-TIME resolver split (T-A.2)`

**Watch items:**
- Tests USE in-memory SQLite + the migration runner from `swing/data/db.py:ensure_schema` for fresh policy table. NO writes to operator's real `~/swing-data/` per Phase 9 Sub-bundle A R1 incident (CLAUDE.md gotcha; fixture pattern: monkeypatch USERPROFILE+HOME at test setup IF the test invokes any write_user_overrides path; this test does not).

### Task A.3: Equity resolver — PROVISIONAL/LIVE dynamic badge contract

**Files:**
- Modify: `swing/metrics/equity_resolver.py`.
- Create: `tests/metrics/test_equity_resolver.py`.

**Acceptance criteria:**
- Function `resolve_live_capital_denominator_dollars(conn, *, asof_date: date, at_trade_time_policy: RiskPolicy) -> tuple[float, Literal["LIVE", "PROVISIONAL"]]` per §A.6.
- Snapshot present at-or-before asof_date → returns (snapshot.equity_dollars, "LIVE").
- No snapshot ≤ asof_date → returns (policy.capital_floor_constant_dollars, "PROVISIONAL").
- Source-ladder is internal to `get_latest_snapshot_on_or_before` (Phase 10 does not re-implement).

**Discriminating tests:**
- `test_resolver_no_snapshots_returns_provisional`: empty table; assert ($7500, "PROVISIONAL").
- `test_resolver_with_snapshot_returns_live`: seed snapshot $2000 at 2026-05-11; query asof_date=2026-05-12 → ($2000, "LIVE").
- `test_resolver_with_back_recorded_snapshot`: seed back-recorded snapshot at 2026-04-01; query asof_date=2026-05-12 → ($1800 if it's the latest) "LIVE".
- `test_resolver_query_before_first_snapshot`: snapshot at 2026-05-11; query asof_date=2026-04-30 → ("PROVISIONAL").
- `test_resolver_uses_at_trade_time_capital_floor`: pass policy with capital_floor_constant_dollars=10000; empty snapshots → ($10000, "PROVISIONAL").

**Suggested commit shape:** `feat(metrics): live_capital_denominator_dollars resolver — PROVISIONAL/LIVE contract (T-A.3)`

**Watch items:**
- §A.15 session-anchor read predicate — asof_date is the CALLER's responsibility; helper is anchor-agnostic. Callers in Sub-bundle D (capital-friction VM) MUST use `last_completed_session(now)` per §A.15 matrix. Add a discriminating round-trip test in Sub-bundle D, NOT here.

### Task A.4: Cohort filter + aggregation helper

**Files:**
- Modify: `swing/metrics/cohort.py`.
- Create: `tests/metrics/test_cohort.py`.

**Acceptance criteria:**
- Function `list_trades_for_cohort(conn, *, hypothesis_label: str | None, state_filter: tuple[str, ...] | None = None) -> list[Trade]`.
- Function `list_closed_trades_for_cohort(conn, *, hypothesis_label: str | None) -> list[Trade]` shorthand for state_filter=('closed', 'reviewed').
- Function `count_per_cohort(conn) -> dict[str, int]` returns {cohort_name: closed_trade_count} for all 4 hypothesis_registry rows.
- `hypothesis_label=None` returns the "all closed trades" view (no cohort filter).

**Discriminating tests:**
- `test_list_trades_filters_by_hypothesis_label`: seed 5 trades with mixed labels; assert filter returns only matching.
- `test_list_trades_state_filter`: seed mixed-state trades; assert state_filter narrows.
- `test_list_closed_trades_returns_closed_and_reviewed`: state ∈ {'closed', 'reviewed'} both included.
- `test_list_trades_label_none_returns_all`: hypothesis_label=None returns all.
- `test_count_per_cohort_returns_all_4_cohorts_even_when_zero`: empty trades table + 4 hypothesis_registry rows → returns {name: 0} for all 4.
- `test_list_trades_canonicalizes_label`: hypothesis_label "A+ baseline (target 20)" matches both stored "a+ baseline" and "A+ Baseline" via `swing.trades.entry.canonicalize_hypothesis_label` (already shipped helper).

**Suggested commit shape:** `feat(metrics): per-hypothesis-cohort filter + aggregation helper (T-A.4)`

**Watch items:**
- Per §A.5 cohort-grain rule, the aggregation iterates per-trade BEFORE applying scratch_epsilon; the CLASSIFICATION (win/loss/scratch) happens at the per-trade level using AT-TRADE-TIME policy. The helper here is purely a row-fetch; classification happens in `swing/metrics/process.py` (Sub-bundle B).

### Task A.5: Rolling-N window helper (spec §3.8 Class D foundation)

**Files:**
- Modify: `swing/metrics/rolling.py`.
- Create: `tests/metrics/test_rolling.py`.

**Acceptance criteria:**
- Function `rolling_window_samples(*, samples: list[float], window_size: int, step: int = 1) -> list[list[float]]` returns a list of windows; each window is the last `window_size` samples up to the position.
- Function `rolling_mean_series(*, samples: list[float], window_size: int) -> list[tuple[int, float | None]]` returns [(i, mean of samples[max(0,i-window_size+1):i+1])] with None for windows below `min_n_for_mean=3` (per spec §5.4 effective_n<5 suppression handled by render-layer; this is the raw series).
- HARDCODED `window_size = 10` is NOT enforced here (the helper is generic); the §3.8 callsites in Sub-bundle E pass 10. Keeps generic for future use.

**Discriminating tests:**
- `test_rolling_window_basic`: samples=[1,2,3,4,5], window_size=3 → windows=[[1],[1,2],[1,2,3],[2,3,4],[3,4,5]].
- `test_rolling_mean_series_basic`: samples=[1,2,3,4,5], window_size=3 → [(0,None),(1,None),(2,2.0),(3,3.0),(4,4.0)] (None for n<3).
- `test_rolling_mean_empty`: samples=[] → [].
- `test_rolling_mean_window_larger_than_samples`: samples=[1,2], window_size=10 → [(0,None),(1,None)] (effective_n always <3).

**Suggested commit shape:** `feat(metrics): rolling-N window helper (Class D foundation; T-A.5)`

**Watch items:**
- This helper is intentionally PRESENTATION-AGNOSTIC. The `render_class_d` from `honesty.py` consumes the OUTPUT of this helper + applies the spec §5.4 4-band rendering policy. Sub-bundle E's process_grade_trend.py wires them together.

### Task A.6: BaseLayoutVM mixin + shared metric VM dataclasses

**Files:**
- Modify: `swing/web/view_models/metrics/shared.py`.
- Create: `tests/web/test_view_models/test_metrics_shared_vms.py`.

**Acceptance criteria:**
- `BaseLayoutVM` `@dataclass(frozen=True)` mixin with all 5 base-layout fields (`session_date: str`, `stale_banner: bool = False`, `price_source_degraded: bool = False`, `price_source_degraded_until: str | None = None`, `ohlcv_source_degraded: bool = False`) + the new Phase 10 field `unresolved_material_discrepancies_count: int = 0` (per §A.18 Codex R2 Major #6 restructure; populated by every metrics-VM constructor from Sub-bundle A onward via `swing/metrics/discrepancies.py:count_unresolved_material(conn)`; existing 6 base-layout VMs get the field add + populate in Sub-bundle E Task E.3).
- `ConfidenceBadgeVM` dataclass with `low_confidence: bool`, `confidence_floor_warning: bool`, `text: str` (rendered text for the badge).
- `ProvisionalBadgeVM` dataclass with `is_provisional: bool`, `text: str` (rendered text per §A.6).
- `SuppressionRowVM` dataclass with `metric_name: str`, `placeholder_text: str` (per spec §5.6 format).
- `__post_init__` validators per Phase 9 forward-binding lesson — reject NaN/inf where applicable (none of these have float fields besides None-sentinel cases; lock asserts session_date is non-empty).

**Discriminating tests:**
- `test_base_layout_vm_default_values`: BaseLayoutVM(session_date='2026-05-13') has all defaults.
- `test_confidence_badge_text_format`: ConfidenceBadgeVM(low_confidence=True, ..., text="low confidence (n=4)") renders.
- `test_provisional_badge_text_format`: ProvisionalBadgeVM(is_provisional=True, text="PROVISIONAL: $7,500 floor used as live-capital fallback (no snapshot ≤ 2026-05-13)").
- `test_suppression_row_format`: SuppressionRowVM matches spec §5.6 italic format.

**Suggested commit shape:** `feat(metrics): BaseLayoutVM mixin + shared badge dataclasses (T-A.6)`

**Watch items:**
- Per §A.8 + §I.5: every Phase 10 metrics-page VM in Sub-bundles B–E MUST extend BaseLayoutVM. Discriminating regression test in Task A.7 enforces.

### Task A.7: Discriminating regression — base-layout VM coverage

**Files:**
- Create: `tests/web/test_view_models/test_base_layout_vm_coverage.py`.

**Acceptance criteria:**
- Test `test_all_metrics_vms_have_base_layout_fields` enumerates `swing/web/view_models/metrics/*.py` via `pkgutil.iter_modules` + asserts every `@dataclass`-decorated class with name ending in `VM` (exclusion list: `ConfidenceBadgeVM`, `ProvisionalBadgeVM`, `SuppressionRowVM` — these are SUB-VMs, not page VMs) has the 5 required base-layout field names defined.
- The test passes at end of Sub-bundle A (only `MetricsIndexVM` exists; gets added in Task A.8 below). Will also pass after Sub-bundles B–E land their VMs.

**Discriminating tests:**
- `test_all_metrics_vms_have_base_layout_fields`: imports module + iterates classes; asserts presence.
- `test_existing_dashboard_vm_has_unresolved_material_field`: asserts `DashboardVM` has the new field per §A.18 — this WILL FAIL until Sub-bundle E lands the field add. Mark as `@pytest.mark.skip(reason="Sub-bundle E adds DashboardVM field per §A.18")` in Sub-bundle A; un-skip in Sub-bundle E.

**Suggested commit shape:** `test(metrics): base-layout VM coverage regression — Phase 10 §A.8 + §I.5 lock (T-A.7)`

**Watch items:**
- The skipped `test_existing_dashboard_vm_has_unresolved_material_field` is the cross-bundle pin for Sub-bundle E's integration step. Sub-bundle E un-skips + verifies pass.

### Task A.7.1: Discrepancies helper — `swing/metrics/discrepancies.py:count_unresolved_material` (Codex R2 Major #6 restructure)

**Files:**
- Modify: `swing/metrics/discrepancies.py` (full implementation; was empty placeholder from T-A.0).
- Create: `tests/metrics/test_discrepancies.py`.

**Acceptance criteria:**
- Function `count_unresolved_material(conn) -> int` returns `len(list_unresolved_material_for_active_trades(conn)) + len(list_unresolved_material_for_closed_trades(conn))`.
- Reads ONLY; no writes; no transaction owned.
- Returns 0 when both lists empty.

**Discriminating tests:**
- `test_count_unresolved_material_zero_when_no_discrepancies`.
- `test_count_unresolved_material_returns_sum_of_active_plus_closed`: seed 2 unresolved-material on active trades + 1 unresolved-material on closed trades → returns 3.
- `test_count_unresolved_material_excludes_resolved`: seed `resolution='acknowledged_immaterial'` → not counted.
- `test_count_unresolved_material_excludes_immaterial`: seed `material_to_review=0` → not counted.

**Suggested commit shape:** `feat(metrics): discrepancies helper — count_unresolved_material (T-A.7.1)`

**Watch items:**
- Helper performance: invoked on EVERY base-layout page load (per §A.18 + §I.5). Bench at Sub-bundle E gate; if >50ms p95, V2 candidate to add lightweight cache via `app.state` with 30s TTL. NOT a V1 lock.
- Cross-bundle dependency: every metrics VM constructor in Sub-bundles A (index VM in T-A.8) + B + C + D + E populates `unresolved_material_discrepancies_count=count_unresolved_material(conn)` from the start (Codex R2 Major #6 restructure — eliminates per-metrics-VM retrofit in E).

### Task A.8: Metrics index page — `GET /metrics`

**Files:**
- Create: `swing/web/view_models/metrics/index.py`.
- Create: `swing/web/routes/metrics.py` (router skeleton + `/metrics` index endpoint only; per-surface endpoints land in subsequent bundles).
- Create: `swing/web/templates/metrics/index.html.j2`.
- Modify: `swing/web/app.py` (register `metrics.router`).
- Create: `tests/web/test_routes/test_metrics_routes.py` (smoke for `/metrics` only; per-surface tests added in B/C/D/E).

**Acceptance criteria:**
- `MetricsIndexVM` extends `BaseLayoutVM`; carries `surfaces: list[tuple[str, str, str]]` of (path, label, description) tuples for the 8 surfaces. Constructor populates `unresolved_material_discrepancies_count=count_unresolved_material(conn)` per §A.18 Codex R2 Major #6 restructure.
- Route `GET /metrics` returns 200 + HTML; renders 8 navigator tiles + the "Currently in: PROVISIONAL fallback" banner when applicable (delegated to base.html.j2's existing banner block).
- Template extends `base.html.j2`.
- TestClient smoke: `client.get("/metrics")` returns 200; body contains all 8 surface labels.

**Discriminating tests:**
- `test_metrics_index_returns_200`.
- `test_metrics_index_renders_all_8_surface_links`.
- `test_metrics_index_extends_base_layout`: response body contains the base-layout `<header>` element.

**Suggested commit shape:** `feat(metrics): metrics index page — GET /metrics navigator (T-A.8)`

**Watch items:**
- Per §A.9: NO HTMX OOB-swap on this surface; pure server-rendered HTML.
- Per spec §4.9 BINDING: operator-witnessed verification gate — Sub-bundle A has 0 surfaces by default per §C; Task A.8 introduces 1 (the index) so add it to Sub-bundle A's gate.

### Task A.9: Sub-bundle A integration test + verify_phase10.py + ruff sweep

**Files:**
- Create: `verify_phase10.py` at worktree root (Codex R2 Major #5; see §J.2 for full script body).
- Modify: existing `tests/metrics/*` collection to assert all helpers cleanly importable + composable.
- Run ruff sweep + fix any new issues.

**Acceptance criteria:**
- `python verify_phase10.py` exits 0 (the cross-platform verification suite).
- `python -m pytest -m "not slow" -q` passes — projected baseline 2767 + ~35..55 new = ~2802..2822 fast tests.
- `ruff check swing/` baseline UNCHANGED at 18.
- All `swing/metrics/*.py` files pass ruff.

**Suggested commit shape:** `chore(metrics): Sub-bundle A integration sweep + verify_phase10.py (T-A.9)`

**Operator-witnessed gate (Sub-bundle A):**
- S1 (inline): pytest fast-tests pass; ruff baseline 18.
- S2 (inline): import smoke `python -c "from swing import metrics; ..."` passes.
- S3 (browser): `swing web` → navigate to `/metrics` → confirm 8-tile navigator renders + base-layout integration intact.

---

## §E — Sub-bundle B: Trade-process card (§4.1) + Hypothesis-progress card (§4.2)

**Goal:** First two operator-visible dashboard surfaces. Exercises the LIVE policy + AT-TRADE-TIME policy split (per §A.5), per-cohort scaffolding, full hypothesis transition history (per §A.11), and the §3.1 + §3.2 metric inventory.

**Branch:** `phase10-bundle-B-trade-process-and-hypothesis-progress`. Worktree branching from main HEAD post-Sub-bundle-A integration merge.

**Files in scope (per §B):** `swing/metrics/process.py` + `swing/web/view_models/metrics/{trade_process_card,hypothesis_progress_card}.py` + `swing/web/templates/metrics/{trade_process_card,hypothesis_progress_card,partials/cohort_tabs,partials/honesty_badges}.html.j2` + corresponding tests.

### Task B.0: Recon — verify Sub-bundle A interface intact + cohort_decision_criterion_evaluation_text seed

**Files:** read-only.

**Acceptance criteria:**
- `python -c "from swing.metrics.honesty import render_class_a, render_class_b, render_class_c; from swing.metrics.cohort import list_closed_trades_for_cohort; from swing.metrics.policy import read_at_trade_time_policy"` passes.
- Read `swing/data/migrations/0008_hypothesis_registry.sql` — verify the 4 cohort `decision_criteria` text values are the seed text Phase 10's §3.7 `cohort_decision_criterion_evaluation_text` will render. Document the verbatim values in this task's recon notes.

**Suggested commit shape:** none — pure recon. Document inline in PR description / executing-plans return-report.

### Task B.1: §3.1 trade-process metric computations — `swing/metrics/process.py`

**Files:**
- Modify: `swing/metrics/process.py`.
- Create: `tests/metrics/test_process.py`.

**Acceptance criteria:**
- Function `compute_trade_process_metrics(conn, *, hypothesis_label: str | None) -> TradeProcessMetricsResult` returns a frozen-dataclass aggregate with all 22 §3.1 metric values + their honesty-class rendering.
- Internally uses `read_at_trade_time_policy` per-trade (to apply scratch_epsilon classification under at-trade-time semantics per §A.5).
- Suppression applied via `render_class_a/b/c/d` per metric (see metric-to-class matrix below).
- Returns NaN-free + inf-free floats only; uses `None` sentinel for "not computable" + suppressed values.

**Per-metric class matrix (binding for §3.1):**

| Metric | Class | Renderer |
|---|---|---|
| realized_R | B (cohort mean) | render_class_b |
| gross_realized_R | B | render_class_b |
| expectancy_R | B | render_class_b |
| win_rate | A | render_class_a |
| loss_rate | A | render_class_a |
| scratch_rate | A | render_class_a |
| avg_win_R | B (winners mean) | render_class_b |
| avg_loss_R | B (losers mean) | render_class_b |
| profit_factor | C | render_class_c |
| payoff_ratio | C | render_class_c |
| MFE_R (closed) | B | render_class_b |
| MAE_R (closed) | B | render_class_b |
| capture_ratio | B (winners only) | render_class_b |
| giveback_R_winner | B | render_class_b |
| giveback_R_winner_to_loser | B (subset) | render_class_b |
| entry_adverse_slippage_R | B | render_class_b |
| mistake_cost_R (cohort sum) | B (treated as cohort sum) | render_class_b |
| lucky_violation_R (cohort sum) | B | render_class_b |
| process_grade | A (distribution) | per-grade render_class_a (5 rates: A/B/C/D/F counts/n) |
| disqualifying_process_violation_rate | A | render_class_a |
| holding_period_days | B (cohort mean) | render_class_b |
| mistake_tag_frequency | A (per-tag rate) | render_class_a per tag |

**Discriminating tests:**
- `test_compute_metrics_empty_cohort_returns_all_suppressed`: hypothesis_label="A+ baseline (target 20)" with 0 trades → every metric returns SuppressedMetric.
- `test_compute_metrics_n_3_renders_point_estimates_with_warning`: seed 3 trades; assert HonestyBadges.low_confidence_warning=True for Class B metrics; suppression for n<3 metrics ABSENT.
- `test_compute_metrics_n_5_renders_wilson_ci`: seed 5 closed trades; assert WilsonCI returned for Class A metrics; confidence_floor_warning=True (n<20).
- `test_compute_metrics_n_20_drops_confidence_floor_warning`: seed 20 closed trades; assert confidence_floor_warning=False.
- `test_at_trade_time_policy_classification_preserves_under_supersession`: seed 3 trades classified under policy_id=1 (scratch_epsilon=0.10); supersede to policy_id=2 (scratch_epsilon=0.20); assert win/loss/scratch classification UNCHANGED on stamped trades.
- `test_legacy_trade_with_null_stamp_uses_live_policy_with_annotation`: seed legacy trade (risk_policy_id_at_lock=NULL); assert policy_used = LIVE policy + annotation flag.
- `test_capture_ratio_winners_only`: mix winners + losers; assert capture_ratio computed only over winners.
- `test_payoff_ratio_zero_losses_returns_suppressed`: all winners; assert returns SuppressedMetric "Insufficient outcome diversity".
- `test_profit_factor_zero_losses_returns_suppressed`: same.
- `test_mistake_cost_R_uses_review_log_aggregate_when_present`: prefer `review_log.total_mistake_cost_R` over recomputing per-trade.
- `test_mistake_cost_R_falls_back_to_per_trade_compute_when_review_log_absent`: trade closed but not reviewed; recompute via `swing/trades/review.py:compute_mistake_cost_R` per spec §7.

**Suggested commit shape:** `feat(metrics): §3.1 trade-process metric computations (T-B.1)`

**Watch items:**
- AT-TRADE-TIME policy resolution per trade can be expensive in a tight loop — use `risk_policy_id_at_lock` GROUP BY pattern to fetch policies in batches IFF profiling shows >100ms p95 on a 50-trade cohort. V1 default: per-trade lookup is fine at our scale.
- Per spec §A.16 + §I.14: empty cohort regression test is binding.

### Task B.2: TradeProcessCardVM — assemble per-cohort tabs

**Files:**
- Modify: `swing/web/view_models/metrics/trade_process_card.py`.
- Create: `tests/web/test_view_models/test_trade_process_card_vm.py`.

**Acceptance criteria:**
- `TradeProcessCardVM` extends `BaseLayoutVM`; carries `cohort_tabs: list[CohortTabVM]` where each tab represents a cohort + the "all closed trades" toggle.
- Constructor `build_trade_process_card_vm(*, cfg, conn) -> TradeProcessCardVM` wires `compute_trade_process_metrics` per cohort + per "all".
- Default-active tab: per-cohort (the spec §4.1 binding "primary axis: per-hypothesis-cohort, with 'all closed trades' as default toggle; never a non-cohort default" — interpret as: default-rendered view is the FIRST cohort tab; "all" is one of the toggles, not the default).
- Per spec §4.1 sample-size threshold: cohort with n<3 → render the SUPPRESSION placeholder for the entire tab; n=3..4 → point-estimate-with-warning; n≥5 CI.

**Discriminating tests:**
- `test_vm_renders_4_cohort_tabs_plus_all_toggle`: assert 5 tabs total.
- `test_vm_default_active_tab_is_first_cohort`: the A+ baseline tab is active; "all" is non-default.
- `test_vm_empty_cohorts_render_suppression`: per spec §4.1; all 4 cohorts have 0 trades → each tab shows suppression placeholder.
- `test_vm_carries_base_layout_fields`: BaseLayoutVM coverage regression passes.

**Suggested commit shape:** `feat(metrics): trade-process card VM (T-B.2)`

### Task B.3: Trade-process card route + template

**Files:**
- Modify: `swing/web/routes/metrics.py` (add `GET /metrics/trade-process` endpoint).
- Create: `swing/web/templates/metrics/trade_process_card.html.j2`.
- Create: `swing/web/templates/metrics/partials/cohort_tabs.html.j2`.
- Create: `swing/web/templates/metrics/partials/honesty_badges.html.j2`.
- Modify: `tests/web/test_routes/test_metrics_routes.py`.

**Acceptance criteria:**
- `GET /metrics/trade-process` returns 200 + HTML.
- Template extends `base.html.j2`.
- Renders 5 tabs (4 cohorts + all); default-active per VM.
- Per-tab metric grid renders each metric with: name + value + CI (when present) + ConfidenceBadgeVM badges (when present) + SuppressionRowVM placeholder (when suppressed).
- Per spec §4.9: NO color-only badges; reliability flags + PROVISIONAL badges render as TEXT inline.
- TestClient smoke + base-layout integration assertion + per-cohort-tab visibility assertion.

**Discriminating tests:**
- `test_trade_process_endpoint_returns_200`.
- `test_trade_process_renders_all_5_tabs_in_html_body`.
- `test_trade_process_at_zero_trades_renders_suppression_placeholders_in_html`.
- `test_trade_process_extends_base_layout`: presence of header element.

**Suggested commit shape:** `feat(metrics): trade-process card route + template — GET /metrics/trade-process (T-B.3)`

**Watch items:**
- §A.9 lock: NO HTMX OOB-swap; pure server-render. Per-tab navigation uses simple `<a>` anchors with query-string `?cohort=A+ baseline (target 20)` for the active-tab selection.
- §I.6 lock: this is the FIRST operator-visible Phase 10 surface — gate readiness binds.

### Task B.4: §3.2 hypothesis-progress card — per-cohort governance metrics

**Files:**
- Modify: `swing/web/view_models/metrics/hypothesis_progress_card.py`.
- Create: `tests/web/test_view_models/test_hypothesis_progress_card_vm.py`.

**Acceptance criteria:**
- `HypothesisProgressCardVM` extends `BaseLayoutVM`; carries `cohorts: list[CohortProgressVM]` where each carries: cohort name, status, target_sample_size, n_closed, progress_pct, consecutive_loss_run, distance_to_loss_tripwire, cumulative_R_pct_of_capital (per spec §3.2 with $7,500 constant denominator from AT-TRADE-TIME policy), distance_to_absolute_loss_tripwire, decision_criteria text, latest_status_change_metadata, transition_timeline (full history from `hypothesis_status_history` per §A.11; capped at last 5 entries).
- Constructor `build_hypothesis_progress_card_vm(*, cfg, conn) -> HypothesisProgressCardVM`.
- ALWAYS shown (governance surface; no n<3 suppression; per spec §4.2).
- Tripwire indicator present from n=1.
- Transition timeline reads via `swing.data.repos.hypothesis_status_history.list_history_for_hypothesis(conn, hypothesis_id)` ordered by `effective_from DESC`.

**Discriminating tests:**
- `test_vm_renders_4_cohorts_always`: even with 0 trades.
- `test_vm_progress_pct_at_zero_trades_is_0_pct`.
- `test_vm_consecutive_loss_run_at_zero_trades_is_0`.
- `test_vm_cumulative_R_uses_per_trade_at_trade_time_capital_floor`: seed 2 trades — trade A stamped under policy_id=1 (capital_floor=$7500) with realized P&L -$50; trade B stamped under policy_id=2 (capital_floor=$10000) with realized P&L -$100. Supersede to active policy_id=3 (capital_floor=$5000). Assert cumulative_R_pct_of_capital = -50/7500 + -100/10000 = -0.667% + -1.000% = -1.667% (NOT -150/5000 = -3.000% from naive live-policy aggregation, NOT -150/8750 = -1.714% from average-policy aggregation). Discriminating against both alternative implementations.
- `test_vm_cumulative_R_pre_phase9_legacy_trade_uses_live_floor_with_annotation`: seed trade with risk_policy_id_at_lock=NULL; assert per-trade contribution uses LIVE policy floor + annotation flag is set (per §A.5 fallback rule).
- `test_vm_distance_to_loss_tripwire_decrements_per_loss`: seed cohort with consecutive_loss_tripwire=3 + 2 consecutive losses; assert distance=1.
- `test_vm_transition_timeline_renders_full_history_capped_5`: seed 7 history rows; assert returns latest 5.
- `test_vm_decision_criteria_renders_seed_text_verbatim`: per Task B.0 recon doc.

**Suggested commit shape:** `feat(metrics): §3.2 hypothesis-progress card VM (T-B.4)`

**Watch items:**
- Per §A.5 + §A.5.1 (Codex R1 Major #2 fix): governance metrics use AT-TRADE-TIME `capital_floor_constant_dollars`. For cohort-aggregate `cumulative_R_pct_of_capital`, compute as `sum(per_trade.realized_pnl_dollars / per_trade.at_trade_time_capital_floor)` — per-trade contribution divided by ITS at-trade-time floor, then summed. NEVER average policies across trades + NEVER pin to LIVE policy. This preserves historical-trade interpretation under capital-floor supersession (per spec §1.3 pre-registration discipline). Discriminating test required — see §A.5.1 lock + Task B.4 acceptance below.
- Per §A.11: full transition history supersedes spec §3.2 V1-limitation note. Spec amendment pending V2.1 §VII.F.

### Task B.5: Hypothesis-progress card route + template

**Files:**
- Modify: `swing/web/routes/metrics.py` (add `GET /metrics/hypothesis-progress`).
- Create: `swing/web/templates/metrics/hypothesis_progress_card.html.j2`.
- Modify: `tests/web/test_routes/test_metrics_routes.py`.

**Acceptance criteria:**
- `GET /metrics/hypothesis-progress` returns 200 + HTML.
- Template extends `base.html.j2`.
- Renders 4 cohorts in a row layout (per spec §4.2).
- Each cohort cell shows: progress bar, status badge, tripwire indicator, decision_criteria text, transition timeline `<ol>`.

**Discriminating tests:**
- `test_hypothesis_progress_endpoint_returns_200`.
- `test_hypothesis_progress_renders_all_4_cohorts`.
- `test_hypothesis_progress_renders_decision_criteria_text`.

**Suggested commit shape:** `feat(metrics): hypothesis-progress card route + template — GET /metrics/hypothesis-progress (T-B.5)`

### Task B.6: Sub-bundle B integration test + ruff sweep

**Files:**
- Create: `tests/integration/test_phase10_bundle_b_e2e.py` — E2E happy path: seed 4 cohorts + 6 trades (mixed states + cohorts) + verify both surfaces render coherently.
- Run ruff sweep.

**Acceptance criteria:**
- E2E test seeds realistic data + asserts both `/metrics/trade-process` + `/metrics/hypothesis-progress` render with expected metric values.
- `python -m pytest -m "not slow" -q` passes — projected baseline + ~40..65 new tests.
- Ruff baseline UNCHANGED.

**Suggested commit shape:** `chore(metrics): Sub-bundle B integration sweep (T-B.6)`

**Operator-witnessed gate (Sub-bundle B):**
- S1 (inline): pytest fast-tests pass; ruff baseline 18.
- S2 (browser): `swing web` → `/metrics/trade-process` → confirm 5 tabs render + per-cohort metric grid + suppression placeholders for n<3.
- S3 (browser): `/metrics/hypothesis-progress` → confirm 4-cohort row + transition timeline.

---

## §F — Sub-bundle C: Tier-comparison view (§4.3) + Deviation-outcome view (§4.7)

**Goal:** Two cohort-comparison surfaces. Exercises the §3.3 + §3.7 metric inventory + the `cohort_ci_overlap_descriptor` text-only rendering (per spec §3.3 R1 M3 lock).

**Branch:** `phase10-bundle-C-tier-and-deviation`. Worktree branching from main HEAD post-Sub-bundle-B integration merge.

**Files in scope (per §B):** `swing/metrics/tier.py` + `swing/web/view_models/metrics/{tier_comparison,deviation_outcome}.py` + `swing/web/templates/metrics/{tier_comparison,deviation_outcome}.html.j2` + corresponding tests.

### Task C.0: Recon — confirm Sub-bundle B interface intact

Read-only verification of `swing/metrics/process.py` aggregator + cohort scaffolding from Sub-bundle B.

### Task C.1: §3.3 + §3.7 tier-comparison + deviation-outcome computations — `swing/metrics/tier.py`

**Files:**
- Modify: `swing/metrics/tier.py`.
- Create: `tests/metrics/test_tier.py`.

**Acceptance criteria:**
- Function `compute_tier_comparison(conn) -> TierComparisonResult` returns dataclass with: per-cohort `cohort_win_rate_with_CI` (WilsonCI per §3.3); per-cohort `cohort_expectancy_with_CI` (BootstrapCI); per-non-A+-cohort `cohort_relative_to_aplus`; `cohort_ci_overlap_descriptor` (text per §3.3 R1 M3).
- Function `compute_deviation_outcome(conn) -> DeviationOutcomeResult` returns per-cohort: `cohort_doctrine_deviation_class` text + `cohort_expectancy_relative_to_aplus_pct` (when both cohorts have n≥5) + `cohort_decision_criterion_evaluation_text` (per spec §3.7 R1 M4).
- Suppression: per spec §4.3 + §4.7 thresholds (cohort n<5 → individual cohort suppressed; descriptor suppressed until BOTH A+ AND Sub-A+ have n≥5).
- `cohort_ci_overlap_descriptor` is RENDERED AS TEXT, NOT a boolean (spec §3.3 R1 M3 binding lock).

**Discriminating tests:**
- `test_compute_tier_comparison_empty_data_all_suppressed`.
- `test_compute_tier_comparison_with_5_trades_per_cohort_renders_descriptor`.
- `test_cohort_ci_overlap_descriptor_text_format`: matches "A+ CI [0.10, 0.50] vs Sub-A+ CI [0.05, 0.40] — overlap: yes" format (or analogous).
- `test_cohort_relative_to_aplus_when_aplus_has_zero_trades_returns_suppressed`: division-by-zero defense.
- `test_deviation_outcome_decision_criterion_text_renders_seed_text`.
- `test_deviation_outcome_cohort_n_too_low_renders_n_too_low_placeholder_per_row`.

**Suggested commit shape:** `feat(metrics): §3.3 + §3.7 tier-comparison + deviation-outcome computations (T-C.1)`

**Watch items:**
- Per spec §3.3 R1 M3: NO boolean significance flag. Text-only descriptor at our sample size. Codex check expected.
- Per §A.4 §0.5 §11.2(c): per-cohort "exclude trades with unresolved discrepancies" filter is DEFER. Document the helper signature in the docstring as a V2 plug-point but do NOT implement.

### Task C.2: TierComparisonVM + route + template

**Files:**
- Modify: `swing/web/view_models/metrics/tier_comparison.py`.
- Modify: `swing/web/routes/metrics.py` (add `GET /metrics/tier-comparison`).
- Create: `swing/web/templates/metrics/tier_comparison.html.j2`.
- Create: `tests/web/test_view_models/test_tier_comparison_vm.py`.

**Acceptance criteria:**
- `TierComparisonVM` extends `BaseLayoutVM`; carries 4-cohort side-by-side table.
- Per-cohort cells render: win_rate WilsonCI, expectancy bootstrap CI, relative-to-A+ (when both have n≥5).
- `cohort_ci_overlap_descriptor` text rendered separately (single text block, not per-cohort).
- Template extends base.html.j2.

**Discriminating tests:**
- `test_tier_comparison_endpoint_returns_200`.
- `test_tier_comparison_renders_4_cohort_columns`.
- `test_tier_comparison_at_zero_trades_renders_descriptor_suppression_text`: per spec §4.3 worked example.

**Suggested commit shape:** `feat(metrics): tier-comparison VM + route + template (T-C.2)`

### Task C.3: DeviationOutcomeVM + route + template

**Files:**
- Modify: `swing/web/view_models/metrics/deviation_outcome.py`.
- Modify: `swing/web/routes/metrics.py` (add `GET /metrics/deviation-outcome`).
- Create: `swing/web/templates/metrics/deviation_outcome.html.j2`.
- Create: `tests/web/test_view_models/test_deviation_outcome_vm.py`.

**Acceptance criteria:**
- `DeviationOutcomeVM` extends `BaseLayoutVM`; per-cohort table.
- Each cohort row shows: doctrine_deviation_class, expectancy_relative_to_aplus_pct (when n≥5 both), decision_criterion_evaluation_text.
- Per spec §4.7: cohort row suppressed until n≥5; "n too low" placeholder.

**Discriminating tests:**
- `test_deviation_outcome_endpoint_returns_200`.
- `test_deviation_outcome_renders_4_cohort_rows_or_placeholders`.

**Suggested commit shape:** `feat(metrics): deviation-outcome VM + route + template (T-C.3)`

### Task C.4: Sub-bundle C integration test + ruff sweep

**Files:**
- Create: `tests/integration/test_phase10_bundle_c_e2e.py` — seed varied per-cohort sample sizes; verify suppression ↔ rendering transitions.
- Ruff sweep.

**Acceptance criteria:**
- `python -m pytest -m "not slow" -q` passes.
- Ruff baseline UNCHANGED.

**Suggested commit shape:** `chore(metrics): Sub-bundle C integration sweep (T-C.4)`

**Operator-witnessed gate (Sub-bundle C):**
- S1 (inline): pytest fast-tests + ruff.
- S2 (browser): `/metrics/tier-comparison` → confirm 4-cohort columns + descriptor placeholder at zero data.
- S3 (browser): `/metrics/deviation-outcome` → confirm 4-cohort rows with suppression.

---

## §G — Sub-bundle D: Capital-friction (§4.4) + Maturity-stage (§4.5) + Identification-vs-trade-funnel (§4.6)

**Goal:** Three operational/live-state surfaces. Exercises PROVISIONAL/LIVE dynamic badge contract (per §A.6), per-pipeline-run on-the-fly aggregation (per §A.0.1), and per-position rendering for open trades.

**Branch:** `phase10-bundle-D-capital-maturity-funnel`. Worktree branching from main HEAD post-Sub-bundle-C integration merge.

**Files in scope (per §B):** `swing/metrics/{capital,maturity,funnel}.py` + `swing/web/view_models/metrics/{capital_friction,maturity_stage,identification_funnel}.py` + corresponding templates + tests.

### Task D.0: Recon — verify Phase 9 helpers + dynamic PROVISIONAL contract

Read-only verification of:
- `swing/data/repos/account_equity_snapshots.py:get_latest_snapshot_on_or_before` signature + return shape.
- `swing/data/repos/risk_policy.py:get_active_policy` signature.
- `swing/evaluation/criteria/risk_feasibility.py:NAME` constant.
- Production `account_equity_snapshots` rows (operator-side: `swing account snapshot list`).

Document findings in recon notes.

### Task D.1: §3.4 capital-friction computations — `swing/metrics/capital.py`

**Files:**
- Modify: `swing/metrics/capital.py`.
- Create: `tests/metrics/test_capital.py`.

**Acceptance criteria:**
- Function `compute_capital_friction(conn, *, asof_date: date) -> CapitalFrictionResult` returns dataclass with all 6 §3.4 metrics + PROVISIONAL/LIVE badge state.
- `risk_feasibility_blocked_rate` per spec §A.19 SQL pattern (uses `risk_feasibility.NAME` constant, NOT string literal).
- `current_capital_utilization_pct`, `current_portfolio_heat_pct` use `resolve_live_capital_denominator_dollars` per §A.6.
- `capital_cycle_time_days` cohort mean over closed trades.
- `concurrent_open_positions` count.
- `capital_feasibility_pressure_index` composite; inherits PROVISIONAL badge from utilization input.

**Discriminating tests** (Codex R5 Major #1 — full §A.19 test list mirrored here):
- `test_compute_capital_friction_no_snapshot_returns_provisional_badge`: empty `account_equity_snapshots` → all live-capital-dependent metrics carry PROVISIONAL badge.
- `test_compute_capital_friction_with_snapshot_returns_live_badge`: seed snapshot $2000 ≤ asof_date → LIVE badge.
- `test_risk_feasibility_blocked_rate_uses_constant_not_string_literal`: assert `from swing.evaluation.criteria.risk_feasibility import NAME` import is present.
- `test_risk_feasibility_blocked_rate_excludes_candidates_failing_other_criteria` (per §A.19): seed candidate that fails risk_feasibility AND fails MA-stack → NOT in numerator; rate stays bounded.
- `test_risk_feasibility_blocked_rate_excludes_candidates_with_na_on_other_criteria` (per §A.19 Codex R2 Major #3): seed candidate with `result='na'` on a non-risk criterion → excluded from denominator.
- `test_risk_feasibility_blocked_rate_excludes_candidates_with_na_on_risk_feasibility` (per §A.19 Codex R4 Major #3): seed candidate with all-other-criteria=pass AND `risk_feasibility` result `'na'` → excluded from BOTH numerator AND denominator.
- `test_risk_feasibility_blocked_rate_excludes_candidates_with_partial_criteria_rows` (per §A.19 Codex R3 Major #3 + R4 Major #2): seed candidate with only 3 of 18 EXPECTED_CRITERIA_NAMES rows → excluded from BOTH numerator AND denominator + WARNING log emitted naming candidate_id + missing_set.
- `test_risk_feasibility_blocked_rate_set_membership_guard_catches_missing_plus_extra` (per §A.19 Codex R4 Major #2): seed candidate with 18 criterion_results rows where 1 expected name is missing AND 1 unknown name is present (count matches expected = 18, but membership wrong) → excluded + WARNING log emitted. Discriminates set-membership guard against count-only guard.
- `test_risk_feasibility_blocked_rate_extra_names_logs_info_not_excluded` (per §A.19 Codex R4 Major #2): seed candidate with all 18 expected names + 1 extra unknown name → INCLUDED in computation + INFO log emitted.
- `test_risk_feasibility_blocked_rate_expected_criteria_names_set_matches_pipeline_writer` (per §A.19 Codex R4 Major #1): assert `EXPECTED_CRITERIA_NAMES` set matches names actually written by `_step_evaluate` for a synthetic candidate. Discriminates against `*.NAME`-only undercount.
- `test_risk_feasibility_blocked_rate_at_most_1` (per §A.19): rate bounded to [0, 1].
- `test_risk_feasibility_blocked_rate_at_zero_qualifying_returns_suppressed` (per §A.19): zero would-have-qualified → suppressed text "N/A — 0 would-have-qualified candidates this run".
- `test_concurrent_open_positions_counts_entered_managing_partial_exited`: 3 states summed.
- `test_capital_cycle_time_days_zero_closed_returns_none`: edge case.
- `test_compute_capital_friction_historical_trend_uses_current_trade_state` (Codex R2 Major #4): seed trade T1 opened at run R1 with size=100; advance to R2 + change size to 200 via fill; query for R1 → assert utilization computed against size=200 (CURRENT state, NOT R1-time historical).
- `test_concurrent_open_positions_at_historical_run_uses_open_at_pre_trade_locked_at_only` (Codex R3 Major #2 / §A.0.1; relocated from Task D.5): count trades with `pre_trade_locked_at <= run.started_ts AND (last_fill_at IS NULL OR last_fill_at >= run.started_ts)`; best-effort proxy for "open at run time".
- (Codex R3 Minor #2 fix: `test_capital_friction_vm_renders_historical_disclosure_footnote` MOVED to Task D.2 — VM/template behavior belongs there, not in compute-layer Task D.1.)

**Suggested commit shape:** `feat(metrics): §3.4 capital-friction computations + dynamic PROVISIONAL contract (T-D.1)`

**Watch items:**
- §A.15 session-anchor: caller passes asof_date = `last_completed_session(now)` (backward-looking). Lock in this task.
- §I.13 round-trip integration test: write snapshot at session N + immediately invoke compute_capital_friction(asof_date=N) + assert LIVE badge returned.

### Task D.2: CapitalFrictionVM + route + template

**Files:**
- Modify: `swing/web/view_models/metrics/capital_friction.py`.
- Modify: `swing/web/routes/metrics.py` (add `GET /metrics/capital-friction`).
- Create: `swing/web/templates/metrics/capital_friction.html.j2`.
- Create: `tests/web/test_view_models/test_capital_friction_vm.py`.

**Acceptance criteria:**
- `CapitalFrictionVM` extends `BaseLayoutVM`.
- Renders point-in-time gauges + multi-run trend (suppressed at <5 runs per spec §4.4).
- PROVISIONAL badges as TEXT inline per §A.6 + spec §4.9.
- Renders historical-reconstruction disclosure footnote in trend section per §A.0.1 (Codex R2 Major #4): "Trend computed from current trade state; historical points approximate where state has changed since the run."

**Discriminating tests:**
- `test_capital_friction_endpoint_returns_200`.
- `test_capital_friction_renders_provisional_text_when_no_snapshot`.
- `test_capital_friction_renders_live_when_snapshot_present`.
- `test_capital_friction_renders_historical_disclosure_footnote_in_trend_section` (Codex R2 Major #4).

**Suggested commit shape:** `feat(metrics): capital-friction VM + route + template (T-D.2)`

### Task D.3: §3.5 maturity-stage computations — `swing/metrics/maturity.py`

**Files:**
- Modify: `swing/metrics/maturity.py`.
- Create: `tests/metrics/test_maturity.py`.

**Acceptance criteria:**
- Function `compute_maturity_stage(conn) -> MaturityStageResult` returns per-position list with: maturity_stage, open_MFE_R_to_date, open_MAE_R_to_date, current_stop, planned_target_R, trail_MA_eligibility_flag, position_capital_utilization_pct (with PROVISIONAL/LIVE per §A.6), position_portfolio_heat_contribution_dollars.
- Reads from `daily_management_records` via `swing.data.repos.daily_management.list_open_position_active_snapshots` (Phase 8 shipped helper).
- Per spec §3.5 R1 M5 + §6.1: `trail_MA_candidate_price` and `planned_target_R` shipped at Phase 8; if NULL on a row (legacy / non-target trade), render placeholder "—" for that cell, NOT a hard error.

**Discriminating tests:**
- `test_compute_maturity_stage_zero_open_returns_empty_list`.
- `test_compute_maturity_stage_per_position_groups`.
- `test_compute_maturity_stage_handles_null_planned_target_r`: render placeholder.
- `test_compute_maturity_stage_handles_null_trail_ma_candidate_price`: trail_MA_eligibility_flag returns None (NOT False).
- `test_compute_maturity_stage_aggregates_count_by_stage`.

**Suggested commit shape:** `feat(metrics): §3.5 maturity-stage computations (T-D.3)`

### Task D.4: MaturityStageVM + route + template

**Files:**
- Modify: `swing/web/view_models/metrics/maturity_stage.py`.
- Modify: `swing/web/routes/metrics.py` (add `GET /metrics/maturity-stage`).
- Create: `swing/web/templates/metrics/maturity_stage.html.j2`.
- Create: `tests/web/test_view_models/test_maturity_stage_vm.py`.

**Acceptance criteria:**
- `MaturityStageVM` extends `BaseLayoutVM`.
- Renders per-position table sorted by maturity_stage; aggregate count by stage.
- Per spec §4.5: per-row cells with NULL Phase-8-capture-need columns render "—" (not "[Phase 8 capture pending]" since Phase 8 IS shipped — null is data-state not capture-state).
- N/A for sample-size threshold (per-position).
- Empty-state placeholder: "No open positions to manage."

**Discriminating tests:**
- `test_maturity_stage_endpoint_returns_200`.
- `test_maturity_stage_zero_open_renders_placeholder`.
- `test_maturity_stage_with_open_positions_renders_per_row`.

**Suggested commit shape:** `feat(metrics): maturity-stage VM + route + template (T-D.4)`

### Task D.5: §3.6 identification-vs-trade-funnel computations — `swing/metrics/funnel.py`

**Files:**
- Modify: `swing/metrics/funnel.py`.
- Create: `tests/metrics/test_funnel.py`.

**Acceptance criteria:**
- Function `compute_identification_funnel(conn, *, run_window: int = 30) -> IdentificationFunnelResult` returns per-run aggregates + 30-day rolling trend.
- Per-run (spec §3.6 verbatim): aplus_identifications_per_run / aplus_trades_taken_per_run / aplus_take_rate_per_run / watch_identifications_per_run / watch_trades_taken_per_run.
- Codex R1 Minor #2 lock: spec §3.6 does NOT define `watch_take_rate_per_run`. V1 surfaces watch identifications + watch taken counts ONLY; NO derived watch_take_rate. If operator wants symmetric watch take-rate at integration triage, plan §A revises before Sub-bundle D dispatch. (Banked as V2 candidate at return report §6.)
- aplus_take_rate_per_run zero-denominator handling per §A.20 (suppressed text "N/A — 0 A+ identifications this run").
- 30-trading-day trend (Codex R4 Minor #2 + R5 Minor #1 specificity): the trend WINDOW spans the LAST 30 NYSE TRADING SESSIONS ending at `end = last_completed_session(datetime.now())` (inclusive of `end`; backward-looking per §A.15). Window derivation:
  ```python
  cal = exchange_calendars.get_calendar('XNYS')
  end = swing.evaluation.last_completed_session(datetime.now())  # date
  # Walk BACKWARD from `end` collecting up to 30 sessions inclusive of `end`.
  # Off-by-one defense: use sessions_window(end, count=-30) which returns the
  # 30 most-recent sessions ending at `end` (inclusive), or fewer when calendar
  # history is shorter. Fallback: cal.sessions_in_range(cal.minus_session_label(end, 29), end)
  # which returns sessions in [end - 29 sessions, end] inclusive.
  sessions = cal.sessions_window(pd.Timestamp(end), -30)
  TRADING_DAYS_WINDOW = 30
  ```
  Per-run aggregation uses `pipeline_runs.started_ts.date()` matched against the session list; runs whose `started_ts.date()` falls outside the 30-session window are excluded. NO use of forward-looking `action_session_for_run` for the trend window — that would shift the boundary on session transition + create the read/write anchor mismatch family (§A.15 binding). Discriminating test: `test_funnel_trend_30_sessions_inclusive_of_end` seeds 31 sessions of runs + asserts only the most-recent 30 are in the trend.
- Per spec §4.6: trend suppressed at <10 runs.

**Discriminating tests:**
- `test_compute_funnel_zero_runs_returns_empty_with_trend_suppressed`.
- `test_compute_funnel_per_run_aggregation`.
- `test_compute_funnel_zero_aplus_identifications_returns_suppressed_take_rate`.
- `test_compute_funnel_trend_at_5_runs_suppressed`.
- `test_compute_funnel_trend_at_10_runs_renders`.
- `test_funnel_trend_30_sessions_inclusive_of_end` (Codex R5 Minor #1 / R6 Minor #1 list-mirror): seed 31 sessions of runs ending at `last_completed_session(now)`; assert the trend window contains only the most-recent 30 sessions (off-by-one defense).
- `test_historical_funnel_uses_current_trade_state` (Codex R2 Major #4 / §A.0.1): seed run R1 + trade T1 with origin='pipeline_aplus' at R1's session; advance to R2; query for R1's `aplus_trades_taken_per_run` → assert T1 counted via current trade state (`pre_trade_locked_at` matches R1.session) NOT historical reconstruction.
- (Codex R3 Major #2 fix: `test_historical_funnel_concurrent_open_at_run_uses_open_at_pre_trade_locked_at_only` MOVED to Task D.1 since `concurrent_open_positions` is a capital-friction metric, NOT a funnel metric.)

**Suggested commit shape:** `feat(metrics): §3.6 identification-vs-trade-funnel computations (T-D.5)`

**Watch items:**
- Trade-to-run-session match per spec §3.6: `trade.pre_trade_locked_at` falls in run's session date. Use `pre_trade_locked_at::date == pipeline_runs.started_ts::date` JOIN; verify with discriminating test.

### Task D.6: IdentificationFunnelVM + route + template

**Files:**
- Modify: `swing/web/view_models/metrics/identification_funnel.py`.
- Modify: `swing/web/routes/metrics.py` (add `GET /metrics/identification-funnel`).
- Create: `swing/web/templates/metrics/identification_funnel.html.j2`.
- Create: `tests/web/test_view_models/test_identification_funnel_vm.py`.

**Acceptance criteria:**
- `IdentificationFunnelVM` extends `BaseLayoutVM`.
- Renders per-run stacked bar (count of A+ identified vs taken; ratio = take rate) + 30-day rolling trend line (suppressed when <10 runs).
- Renders historical-reconstruction disclosure footnote in trend section per §A.0.1 (Codex R2 Major #4) — same footnote text as CapitalFrictionVM.

**Discriminating tests:**
- `test_identification_funnel_endpoint_returns_200`.
- `test_identification_funnel_renders_per_run_bars`.
- `test_identification_funnel_trend_suppressed_below_10_runs`.
- `test_identification_funnel_renders_historical_disclosure_footnote_in_trend_section` (Codex R2 Major #4).

**Suggested commit shape:** `feat(metrics): identification-funnel VM + route + template (T-D.6)`

### Task D.7: Sub-bundle D integration test + ruff sweep

**Files:**
- Create: `tests/integration/test_phase10_bundle_d_e2e.py` — seed snapshot + open positions + pipeline_runs + verify all 3 surfaces render with correct PROVISIONAL/LIVE flips.
- Ruff sweep.

**Operator-witnessed gate (Sub-bundle D):**
- S1 (inline): pytest fast-tests + ruff.
- S2 (browser): `/metrics/capital-friction` → confirm PROVISIONAL badge present (then operator records snapshot via `swing account snapshot record` → re-load → confirm LIVE badge).
- S3 (browser): `/metrics/maturity-stage` → confirm per-position table or "no open positions" placeholder.
- S4 (browser): `/metrics/identification-funnel` → confirm per-run bars + trend-suppressed message.
- S5 (round-trip): record snapshot via CLI; immediately reload `/metrics/capital-friction`; assert badge flipped LIVE.

---

## §H — Sub-bundle E: Process-grade-trend (§4.8) + Reconciliation badge + Phase 11 hand-off

**Goal:** Final surface + cross-bundle reconciliation banner integration + Phase 11 hand-off documentation. Closes Phase 10.

**Branch:** `phase10-bundle-E-process-grade-trend-and-polish`. Worktree branching from main HEAD post-Sub-bundle-D integration merge.

**Files in scope (per §B):** `swing/metrics/{process_grade_trend,discrepancies}.py` + `swing/web/view_models/metrics/process_grade_trend.py` + `swing/web/templates/metrics/process_grade_trend.html.j2` + base.html.j2 modifications + every existing base-layout VM constructor update (per §A.18).

### Task E.0: Recon — verify discrepancy helpers + DashboardVM signature

Read-only verification of:
- `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` signature.
- `swing/data/repos/reconciliation.py:list_unresolved_material_for_closed_trades` signature.
- All 6 existing base-layout VM constructor signatures (Codex R3 Minor #3 count fix): `build_dashboard`, `build_pipeline`, `build_journal`, `build_watchlist`, `build_config_vm`, `PageErrorVM`.

### Task E.1: §3.8 process-grade-trend computations — `swing/metrics/process_grade_trend.py`

**Files:**
- Modify: `swing/metrics/process_grade_trend.py`.
- Create: `tests/metrics/test_process_grade_trend.py`.

**Acceptance criteria:**
- Function `compute_process_grade_trend(conn, *, window_size: int = 10) -> ProcessGradeTrendResult` returns dataclass with: per-trade markers (one per closed-and-reviewed trade ordered by review date) + rolling lines for process_grade / entry_grade / management_grade / exit_grade / disqualifying_violation_rate / mistake_cost_R_total / mistake_cost_R_per_trade.
- N=10 HARDCODED (per spec §8.5 lock + §A.4); reads from caller-passed `window_size` for testability but production callsite passes 10.
- Numeric grade encoding: A=4, B=3, C=2, D=1, F=0.
- Per spec §5.4 Class D rendering applied via `render_class_d` from honesty.py with `underlying_class` parameter per §A.21 (Codex R2 Major #1 fix). Per-metric mapping per §A.21 matrix:
  - `process_grade_rolling_N`, `entry_grade_rolling_N`, `management_grade_rolling_N`, `exit_grade_rolling_N`, `mistake_cost_R_rolling_N_per_trade` → `underlying_class="B"` (BootstrapCI on window samples).
  - `disqualifying_violation_rate_rolling_N` → `underlying_class="A"` (WilsonCI on window k/n; pass `events_in_window=count(disqualifying=1)` per Codex R2 Minor #1 fix).
  - `mistake_cost_R_rolling_N_total` → `underlying_class="point"` (point estimate only; spec-conformance deviation banked at return report §6 as V2.1 §VII.F amendment candidate).

**Discriminating tests:**
- `test_compute_process_grade_trend_zero_trades_returns_all_suppressed`.
- `test_compute_process_grade_trend_5_trades_window_10_partial_window_render`: per spec §5.4 5≤effective_n<N → line drawable + window-narrowing badge + confidence-floor warning.
- `test_compute_process_grade_trend_10_trades_window_10_full_window_below_floor`: full window + confidence-floor warning persists.
- `test_compute_process_grade_trend_20_trades_drops_confidence_floor_warning`.
- `test_grade_letter_to_numeric_encoding`: A=4, F=0, etc.
- `test_process_grade_rolling_N_value_slot_carries_BootstrapCI`: assert `render_class_d(..., underlying_class="B")` returns `BootstrapCI` in value slot (Codex R2 Major #1).
- `test_disqualifying_violation_rate_rolling_N_value_slot_carries_WilsonCI`: assert `underlying_class="A"` + `events_in_window=k` → `WilsonCI` in value slot.
- `test_mistake_cost_R_rolling_N_total_value_slot_carries_float_only`: assert `underlying_class="point"` → bare float in value slot (no CI; per §A.21 spec-conformance deviation).
- `test_mistake_cost_R_rolling_N_per_trade_value_slot_carries_BootstrapCI`: assert spec §5.2 Class B rendering applied per §A.21.

**Suggested commit shape:** `feat(metrics): §3.8 process-grade-trend computations (T-E.1)`

### Task E.2: ProcessGradeTrendVM + route + template (inline SVG line chart)

**Files:**
- Modify: `swing/web/view_models/metrics/process_grade_trend.py`.
- Modify: `swing/web/routes/metrics.py` (add `GET /metrics/process-grade-trend`).
- Create: `swing/web/templates/metrics/process_grade_trend.html.j2`.
- Create: `tests/web/test_view_models/test_process_grade_trend_vm.py`.

**Acceptance criteria:**
- `ProcessGradeTrendVM` extends `BaseLayoutVM`; carries x/y point series + rolling line series + badges per series.
- Template renders inline SVG per §A.10 default-disposition (α): `<svg viewBox="..."><polyline points="..."/></svg>` for each line; per-trade markers as `<circle>`s.
- NO matplotlib dependency in V1 (avoids the gotcha entirely).
- Per spec §4.9: badges are TEXT inline.

**Discriminating tests:**
- `test_process_grade_trend_endpoint_returns_200`.
- `test_process_grade_trend_renders_svg_polyline_when_window_full`.
- `test_process_grade_trend_renders_per_trade_circles_always`.
- `test_process_grade_trend_renders_confidence_floor_warning_text`.

**Suggested commit shape:** `feat(metrics): process-grade-trend VM + route + template — inline SVG (T-E.2)`

**Watch items:**
- §A.10 lock: NO matplotlib in V1. If operator at integration triage prefers matplotlib PNG, plan §A revises to (β) and Sub-bundle E gains a chart-rendering task that inherits the matplotlib mathtext gotcha (CLAUDE.md) — visual verification non-optional.

### Task E.3: Reconciliation discrepancy badge integration — base.html.j2 + 6 EXISTING base-layout VMs (Codex R2 Major #6 restructured)

**Files:**
- Modify: `swing/web/templates/base.html.j2` (add the unresolved-material banner block per §A.18 rendering snippet).
- Modify: `swing/web/view_models/dashboard.py` (`DashboardVM` field add + `build_dashboard` populate via `count_unresolved_material(conn)`).
- Modify: `swing/web/view_models/pipeline.py` (`PipelineVM` + `build_pipeline`).
- Modify: `swing/web/view_models/journal.py` (`JournalVM` + `build_journal`).
- Modify: `swing/web/view_models/watchlist.py` (`WatchlistVM` + `build_watchlist`).
- Modify: `swing/web/view_models/config.py` (`ConfigVM` + `build_config_vm`).
- Modify: `swing/web/view_models/error.py` (`PageErrorVM`).
- Modify: `tests/web/test_view_models/test_base_layout_vm_coverage.py` (un-skip the cross-bundle pin from Task A.7 — `test_existing_dashboard_vm_has_unresolved_material_field`).
- Modify: `tests/web/test_routes/test_metrics_routes.py` (assert all 9 metrics surfaces render with the banner field present + banner-fires-when-count>0 / banner-absent-when-count=0).

**NOT modified at this task** (Codex R2 Major #6 — restructure eliminated):
- `swing/metrics/discrepancies.py` — helper LANDED in Sub-bundle A T-A.7.1 (NOT this task).
- `tests/metrics/test_discrepancies.py` — LANDED in T-A.7.1.
- `swing/web/view_models/metrics/*.py` — each metrics VM ALREADY populates the field from its Sub-bundle landing (A index in T-A.8; B trade-process + hypothesis-progress in T-B.2 + T-B.4; C tier + deviation in T-C.2 + T-C.3; D capital + maturity + funnel in T-D.2 + T-D.4 + T-D.6; E process-grade-trend in T-E.2). This task only retrofits the 6 EXISTING base-layout VMs.

**Acceptance criteria:**
- `BaseLayoutVM.unresolved_material_discrepancies_count` field already in place since Sub-bundle A T-A.6; this task adds it to the 6 EXISTING base-layout VM dataclasses + populates via the helper from T-A.7.1.
- `base.html.j2` renders banner block per §A.18 rendering snippet.
- Cross-bundle regression test (un-skipped from Task A.7) passes.
- TestClient assertions verify banner renders when N>0; absent when N=0.

**Discriminating tests** (banked-in or new):
- `test_dashboard_vm_carries_unresolved_material_count` (NEW).
- `test_pipeline_vm_carries_unresolved_material_count` (NEW).
- `test_journal_vm_carries_unresolved_material_count` (NEW).
- `test_watchlist_vm_carries_unresolved_material_count` (NEW).
- `test_config_vm_carries_unresolved_material_count` (NEW).
- `test_error_vm_carries_unresolved_material_count` (NEW).
- `test_base_layout_renders_banner_when_count_gt_0` (NEW): TestClient + seed discrepancy + assert banner string in response body across all 6 + 9 = 15 base-layout pages.
- `test_base_layout_omits_banner_when_count_eq_0` (NEW): assert banner absent.
- `test_existing_dashboard_vm_has_unresolved_material_field` (un-skip from T-A.7).

**Suggested commit shape:** `feat(metrics): unresolved-material discrepancy banner — base.html.j2 + 6 existing base-layout VMs (T-E.3)`

**Watch items:**
- §A.18 Codex R2 Major #6 restructure means the metrics VMs from Sub-bundles A/B/C/D/E ALREADY populate the field at landing. This task closes the 6 existing base-layout VMs only. Cross-bundle integration risk reduced from "15 retrofits in E" to "6 retrofits in E + 9 land-ready in A/B/C/D/E"; the Task A.7 regression test is the catch.

### Task E.4: Phase 11 hand-off note + final integration test + ruff sweep

**Files:**
- Modify: `docs/phase3e-todo.md` (add "Phase 10 closer" section with capture-needs feedback for Phase 11; mirror Phase 9 Sub-bundle E pattern).
- Create: `tests/integration/test_phase10_metrics_e2e.py` — single combined E2E exercising A+B+C+D+E surfaces in one happy path.
- Run final ruff sweep.

**Acceptance criteria:**
- E2E test seeds full happy-path data (4 cohorts, 6+ trades across cohorts/states, 1 snapshot, 1 unresolved discrepancy) + verifies all 9 metrics surfaces render coherently + banner renders.
- `python -m pytest -m "not slow" -q` passes — projected baseline + ~25..45 new tests in Sub-bundle E.
- Ruff baseline UNCHANGED at 18.
- `docs/phase3e-todo.md` Phase 11 hand-off section enumerates: (a) any capture-needs surfaced during Phase 10 implementation; (b) operator-decision items pending (CorporateActions MVP / web-form snapshot capture / lucky_violation_R surface); (c) Schwab API Phase A coordination notes from Sub-bundle D operational metrics; (d) the 2 spec amendments pending V2.1 §VII.F (Phase 9 Sub-bundle D §7 anchor + Sub-bundle E §6.2 parser) UNCHANGED — Phase 10 doesn't add to that list unless implementation surfaces a new amendment.

**Suggested commit shape:** `docs(phase10): Phase 10 closer — Phase 11 hand-off + final integration sweep (T-E.4)`

**Operator-witnessed gate (Sub-bundle E):**
- S1 (inline): pytest fast-tests + ruff.
- S2 (browser): `/metrics/process-grade-trend` → confirm SVG line chart renders (or per-trade markers + suppression at low n).
- S3 (browser): seed an unresolved-material discrepancy → load any base-layout page → confirm banner appears.
- S4 (browser): resolve the discrepancy via CLI → reload → confirm banner gone.
- S5 (browser): navigate `/metrics` (umbrella index) → click each surface tile → confirm each renders.

---

## §I — Cross-bundle invariants (carry forward through dispatch)

### §I.1 Schema posture LOCK (per §A.0)

Phase 10 V1 introduces ZERO new tables + ZERO ALTERs. `EXPECTED_SCHEMA_VERSION` stays at 17. Any sub-bundle dispatch that proposes schema changes MUST surface explicitly in plan §A revision OR be rejected at executing-plans review.

### §I.2 Module placement LOCK (per §A.1 + §A.2)

`swing/metrics/` + `swing/web/view_models/metrics/` are the canonical locations. NO scattering of metric helpers into `swing/web/view_models/dashboard.py` or other existing files (read-only consumption only).

### §I.3 Risk_policy split LOCK (per §A.5)

LIVE-policy reads via `read_live_policy(conn)`; AT-TRADE-TIME reads via `read_at_trade_time_policy(conn, trade=trade)`. Per-metric-class assignment in §A.5 is binding; sub-bundles MUST NOT swap a metric across the split without §A revision.

### §I.4 PROVISIONAL/LIVE dynamic badge LOCK (per §A.6)

`resolve_live_capital_denominator_dollars` is the canonical resolver. Spec §3.4 + §3.5 operational metrics MUST use it; governance metrics in §3.2 MUST NOT (they use AT-TRADE-TIME `capital_floor_constant_dollars` directly per §A.5).

### §I.5 BaseLayoutVM mixin LOCK (per §A.8 + §A.18)

Every Phase 10 metrics-page VM extends `BaseLayoutVM`. Every existing base-layout VM gains `unresolved_material_discrepancies_count` field in Sub-bundle E. The Task A.7 regression test enforces; un-skip in Task E.3.

### §I.6 HTMX failure-surface budget LOCK (per §A.9)

Phase 10 V1 surfaces are pure server-rendered HTML; NO HTMX OOB-swap, NO HX-Redirect, NO embedded forms. If a V2 surface adds HTMX interactivity, the V2 dispatch enumerates the three known browser-only failure surfaces.

### §I.7 Per-pipeline-run aggregation LOCK (per §A.0.1)

Capital-friction + identification-funnel surfaces compute per-run aggregates VIA on-the-fly JOIN, NOT new schema columns. If multi-run trend queries exceed 500ms p95 at gate, raise as V2 candidate; do NOT add columns in V1.

### §I.8 Decoupling discipline LOCK (per spec §5 R3 M2 + R4 M1)

Statistical-confidence threshold (`global_confidence_floor_n=20`) is DECOUPLED from cohort governance threshold (`hypothesis_registry.target_sample_size`). `honesty.py:render_class_d` returns 3-tuple decoupling window-fullness from confidence-floor; sub-bundles render BOTH badges separately per spec §5.4.

### §I.9 No `INSERT OR REPLACE` (per CLAUDE.md gotcha + Phase 9 forward-binding)

Phase 10 V1 has 0 new write paths so this is by-construction satisfied. If §0.4 §8.2 manual-snapshot-capture web form is elected at integration triage, the new POST handler MUST use SELECT-then-UPDATE-or-INSERT semantics + the Phase 9 single-write-path discipline.

### §I.10 Test fixture USERPROFILE+HOME monkeypatch (per §A.12)

Every test fixture exercising `swing/config_user.py:write_user_overrides` MUST monkeypatch BOTH env vars. By-construction satisfied at V1 (no write_user_overrides paths). Lock applies to any future opt-in additions.

### §I.11 Service-layer transaction discipline (per §A.13)

Caller MUST NOT hold open transaction; service owns BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject-don't-auto-detect. By-construction satisfied at V1 (no new write services).

### §I.12 Form-render hidden-anchor round-trip (per §A.14)

Every form-render hidden anchor driving POST-time validation MUST round-trip through soft-warn confirm `form_values` dict. By-construction satisfied at V1 (no new forms).

### §I.13 Session-anchor read/write predicate alignment (per §A.15)

Per-query session-anchor matrix is binding. Discriminating round-trip integration test required for any session-keyed read predicate added in Sub-bundles D + E (capital-friction asof_date; maturity-stage review_date; identification-funnel started_ts).

### §I.14 Empty-cohort + zero-trade rendering (per §A.16)

Every spec §4 surface MUST render gracefully at n=0 / 1 / 2. Discriminating regression test per surface in Sub-bundles B–E.

### §I.15 Operator-witnessed verification gate per surface (per spec §4.9 BINDING + §A.9)

Each new surface, on first deploy, requires operator-witnessed browser verification. TestClient passes are necessary but not sufficient. Per-bundle gate-surface count enumerated at §C; all bundles ≤6 surfaces fits one operator session.

---

## §J — Cross-references + grep verifications + test count summary

### §J.1 Spec coverage matrix

Every spec §3 metric + §4 surface + §5 honesty class + §6 capture-need is mapped to a Phase 10 task or explicit defer-to-V2 disposition. Below: per-spec-section coverage.

| Spec section | Coverage |
|---|---|
| §1.1–§1.4 binding constraints | Accepted as given (per dispatch brief §0.3 #6 + spec §1.2). |
| §2 vocabulary + denominator split-policy | Locked in §A.5 + §A.6. |
| §3.1 trade-process metrics | Task B.1 (compute) + Task B.2 (VM) + Task B.3 (route+template). |
| §3.2 per-cohort governance | Task B.4 (VM) + Task B.5 (route+template); §A.11 supersedes V1-limitation note. |
| §3.3 tier-comparison | Task C.1 + C.2. |
| §3.4 capital-friction | Task D.1 + D.2 + §A.6 PROVISIONAL contract + §A.19 risk_feasibility query. |
| §3.5 maturity-stage | Task D.3 + D.4. |
| §3.6 identification-vs-trade-funnel | Task D.5 + D.6 + §A.20 zero-A+ run handling. |
| §3.7 deviation-outcome | Task C.1 + C.3. |
| §3.8 process-grade-trend | Task E.1 + E.2 + §A.10 SVG rendering + §A.21 Class D + B hybrid. |
| §3.9 deferred metrics | Documented as DEFER per spec §3.9; not in V1 scope. |
| §3.10 operator-actionability | Surfaced per surface in templates per spec §3.10. |
| §4.1 trade-process card | Task B.3. |
| §4.2 hypothesis-progress card | Task B.5. |
| §4.3 tier-comparison view | Task C.2. |
| §4.4 capital-friction view | Task D.2. |
| §4.5 maturity-stage view | Task D.4. |
| §4.6 identification-vs-trade-funnel view | Task D.6. |
| §4.7 deviation-outcome view | Task C.3. |
| §4.8 process-grade-trend view | Task E.2. |
| §4.9 cross-cutting surface conventions | Locked in §A.9 + §I.6 + §I.15. |
| §5 honesty policy | Task A.1 (interface) + applied across B–E. |
| §6.1 Phase 8 capture-needs | Phase 8 SHIPPED (verified §A.0); Phase 10 consumes. |
| §6.2 Phase 9 capture-needs | Phase 9 SHIPPED (verified §A.0); Phase 10 consumes per §A.5 + §A.6 + §A.11. |
| §6.3 Phase 10+ capture-needs | (a) on-the-fly JOIN per §A.0.1; (b) same; (c) DEFER per §A.4; (d) DEFER per §A.4. |
| §7 mistake-cost formula | Affirmed; Phase 6 ships. Phase 10 consumes via Task B.1 + §A.4 §8.6 surface decision. |
| §8 open questions | Disposed per §A.4. |
| §9 phasing | Phase 10 consumes Phase 8 + Phase 9 capture; locked per §A.0. |

### §J.1.1 Per-metric coverage matrix (Codex R1 Minor #1 fix)

The §J.1 section-level matrix above is supplemented here with a per-metric mapping. Catches missed individual metrics like `giveback_R_winner_to_loser` or `latest_status_change_metadata`.

**§3.1 trade-process (22 metrics):**

| Metric | Honesty class (per Task B.1 matrix) | Surface | Task |
|---|---|---|---|
| realized_R | B | §4.1 | B.1+B.2+B.3 |
| gross_realized_R | B | §4.1 | B.1+B.2+B.3 |
| expectancy_R | B | §4.1 | B.1+B.2+B.3 |
| win_rate | A | §4.1 | B.1+B.2+B.3 |
| loss_rate | A | §4.1 | B.1+B.2+B.3 |
| scratch_rate | A | §4.1 | B.1+B.2+B.3 |
| avg_win_R | B | §4.1 | B.1+B.2+B.3 |
| avg_loss_R | B | §4.1 | B.1+B.2+B.3 |
| profit_factor | C | §4.1 | B.1+B.2+B.3 |
| payoff_ratio | C | §4.1 | B.1+B.2+B.3 |
| MFE_R (closed) | B | §4.1 | B.1+B.2+B.3 |
| MAE_R (closed) | B | §4.1 | B.1+B.2+B.3 |
| capture_ratio | B | §4.1 | B.1+B.2+B.3 |
| giveback_R_winner | B | §4.1 | B.1+B.2+B.3 |
| giveback_R_winner_to_loser | B | §4.1 | B.1+B.2+B.3 |
| entry_adverse_slippage_R | B | §4.1 | B.1+B.2+B.3 |
| mistake_cost_R (cohort sum) | B | §4.1 | B.1+B.2+B.3 |
| lucky_violation_R (cohort sum) | B | §4.1 | B.1+B.2+B.3 |
| process_grade (distribution) | A per-grade | §4.1 | B.1+B.2+B.3 |
| disqualifying_process_violation_rate | A | §4.1 | B.1+B.2+B.3 |
| holding_period_days | B | §4.1 | B.1+B.2+B.3 |
| mistake_tag_frequency | A per-tag | §4.1 | B.1+B.2+B.3 |

**§3.2 per-cohort governance (10 metrics):**

| Metric | Class | Surface | Task |
|---|---|---|---|
| cohort_n_closed | (governance — no class) | §4.2 | B.4+B.5 |
| cohort_progress_pct | (governance) | §4.2 | B.4+B.5 |
| cohort_expectancy_R | B | §4.1 + §4.2 | B.1+B.4 |
| consecutive_loss_run | (governance) | §4.2 | B.4+B.5 |
| distance_to_loss_tripwire | (governance) | §4.2 | B.4+B.5 |
| cumulative_R_pct_of_capital | (governance — per §A.5.1 lock) | §4.2 | B.4+B.5 |
| distance_to_absolute_loss_tripwire | (governance — inherits §A.5.1 lock) | §4.2 | B.4+B.5 |
| cohort_status | (passthrough) | §4.2 | B.4+B.5 |
| decision_criteria_evaluation | (rendered text) | §4.2 + §4.7 | B.4+B.5+C.1 |
| latest_status_change_metadata | (rendered timeline per §A.11) | §4.2 | B.4+B.5 |

**§3.3 tier-comparison (4 metrics):**

| Metric | Class | Surface | Task |
|---|---|---|---|
| cohort_win_rate_with_CI | A | §4.3 | C.1+C.2 |
| cohort_expectancy_with_CI | B | §4.3 | C.1+C.2 |
| cohort_relative_to_aplus | B (relative) | §4.3 | C.1+C.2 |
| cohort_ci_overlap_descriptor | TEXT (no class; per spec §3.3 R1 M3) | §4.3 | C.1+C.2 |

**§3.4 capital-friction (6 metrics):**

| Metric | Class | Surface | Task |
|---|---|---|---|
| risk_feasibility_blocked_rate | A (per spec §A.19 fix) | §4.4 | D.1+D.2 |
| current_capital_utilization_pct | (PROVISIONAL/LIVE point-in-time per §A.6) | §4.4 | D.1+D.2 |
| current_portfolio_heat_pct | (PROVISIONAL/LIVE) | §4.4 | D.1+D.2 |
| capital_cycle_time_days | B | §4.4 | D.1+D.2 |
| concurrent_open_positions | (count; no class) | §4.4 | D.1+D.2 |
| capital_feasibility_pressure_index | (composite; inherits PROVISIONAL) | §4.4 | D.1+D.2 |

**§3.5 maturity-stage (6 metrics):**

| Metric | Class | Surface | Task |
|---|---|---|---|
| maturity_stage | (per-position enum; no class) | §4.5 | D.3+D.4 |
| open_MFE_R_to_date | (per-position; no class) | §4.5 | D.3+D.4 |
| open_MAE_R_to_date | (per-position; no class) | §4.5 | D.3+D.4 |
| trail_MA_eligibility_flag | (per-position boolean; no class) | §4.5 | D.3+D.4 |
| position_capital_utilization_pct | (PROVISIONAL/LIVE per-position) | §4.5 | D.3+D.4 |
| position_portfolio_heat_contribution_dollars | (per-position; no class) | §4.5 | D.3+D.4 |

**§3.6 identification-vs-trade-funnel (6 metrics):**

| Metric | Class | Surface | Task |
|---|---|---|---|
| aplus_identifications_per_run | (per-run count; spec §5.5 special case) | §4.6 | D.5+D.6 |
| aplus_trades_taken_per_run | (per-run count) | §4.6 | D.5+D.6 |
| aplus_take_rate_per_run | A on trend; per-run as point | §4.6 | D.5+D.6 |
| watch_identifications_per_run | (per-run count) | §4.6 | D.5+D.6 |
| watch_trades_taken_per_run | (per-run count) | §4.6 | D.5+D.6 |
| aplus_funnel_30d_trend | A on trend window | §4.6 | D.5+D.6 |

**§3.7 deviation-outcome (3 metrics):**

| Metric | Class | Surface | Task |
|---|---|---|---|
| cohort_doctrine_deviation_class | (rendered enum; no class) | §4.7 | C.1+C.3 |
| cohort_expectancy_relative_to_aplus_pct | B | §4.7 | C.1+C.3 |
| cohort_decision_criterion_evaluation_text | TEXT (per spec §3.7 R1 M4) | §4.7 | C.1+C.3 |

**§3.8 process-grade-trend (7 metrics; per §A.21 Class assignments):**

| Metric | Class D drawability | Underlying class | Surface | Task |
|---|---|---|---|---|
| process_grade_rolling_N | D | B (bootstrap CI) | §4.8 | E.1+E.2 |
| entry_grade_rolling_N | D | B | §4.8 | E.1+E.2 |
| management_grade_rolling_N | D | B | §4.8 | E.1+E.2 |
| exit_grade_rolling_N | D | B | §4.8 | E.1+E.2 |
| disqualifying_violation_rate_rolling_N | D | A (Wilson CI) | §4.8 | E.1+E.2 |
| mistake_cost_R_rolling_N_total | D | point (per §A.21 V2.1 §VII.F amendment candidate) | §4.8 | E.1+E.2 |
| mistake_cost_R_rolling_N_per_trade | D | B | §4.8 | E.1+E.2 |

**Total: 64 individual metrics across §3.1–§3.8.** Every metric mapped to a class assignment + a surface + a task. §3.9 deferred metrics (9 entries) are NOT in V1 scope per spec §3.9.

### §J.2 Verification suite (cross-platform; executing-plans dispatch acceptance gate)

Codex R1 Major #7 fix: prior version was Bash-only with `/dev/null`, `tail -1`, and narrow grep scope. Rewritten as Python invocations + project's standard tools (ruff, pytest) which are cross-platform native. Run from worktree root.

```python
# verify_phase10.py — runnable on Windows PowerShell, gitbash, or POSIX shell
import pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent

# 1. ZERO new migration
unexpected = list((ROOT / "swing/data/migrations").glob("0018_*.sql"))
assert not unexpected, f"FAIL: unexpected migration {unexpected}"

# 2. EXPECTED_SCHEMA_VERSION still 17
sys.path.insert(0, str(ROOT))
from swing.data.db import EXPECTED_SCHEMA_VERSION
assert EXPECTED_SCHEMA_VERSION == 17, EXPECTED_SCHEMA_VERSION

# 3. Module placement
required = [
    "swing/metrics/__init__.py",
    "swing/web/view_models/metrics/__init__.py",
    "swing/web/routes/metrics.py",
    "swing/web/templates/metrics/index.html.j2",
]
for p in required:
    assert (ROOT / p).exists(), f"FAIL: missing {p}"

# 4. NO INSERT OR REPLACE — broad scope across ALL Phase 10 modified + created files
PHASE10_SCOPE = [
    "swing/metrics",
    "swing/web/view_models/metrics",
    "swing/web/routes/metrics.py",
    "swing/web/templates/metrics",
    # MODIFIED shared files per §B (broaden per Codex R1 Major #7):
    "swing/web/view_models/dashboard.py",
    "swing/web/view_models/pipeline.py",
    "swing/web/view_models/journal.py",
    "swing/web/view_models/watchlist.py",
    "swing/web/view_models/config.py",
    "swing/web/view_models/error.py",
    "swing/web/templates/base.html.j2",
]
pattern = re.compile(r"INSERT\s+OR\s+REPLACE|\bREPLACE\s+INTO\b", re.IGNORECASE)
violations = []
for scope in PHASE10_SCOPE:
    target = ROOT / scope
    paths = [target] if target.is_file() else target.rglob("*")
    for p in paths:
        if not p.is_file() or p.suffix not in (".py", ".sql", ".j2"):
            continue
        text = p.read_text(encoding="utf-8")
        if pattern.search(text):
            violations.append(str(p.relative_to(ROOT)))
assert not violations, f"FAIL: INSERT OR REPLACE found in: {violations}"

# 5. base-layout VM coverage regression test
result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "tests/web/test_view_models/test_base_layout_vm_coverage.py", "-v", "--tb=short"],
    cwd=ROOT, capture_output=True, text=True,
)
assert result.returncode == 0, f"FAIL: base-layout VM coverage regression\n{result.stdout}\n{result.stderr}"

# 6. Per-bundle integration tests
for bundle in ("a", "b", "c", "d", "e"):
    test_file = ROOT / f"tests/integration/test_phase10_bundle_{bundle}_e2e.py"
    if test_file.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, f"FAIL: bundle {bundle} E2E\n{result.stdout}\n{result.stderr}"

# 7. Combined Phase 10 E2E
combined = ROOT / "tests/integration/test_phase10_metrics_e2e.py"
if combined.exists():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(combined), "-v", "--tb=short"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"FAIL: combined E2E\n{result.stdout}\n{result.stderr}"

# 8. Ruff baseline still 18 (E501 only)
result = subprocess.run(
    ["ruff", "check", "swing/"], cwd=ROOT, capture_output=True, text=True,
)
# ruff exits 1 when issues found; that's expected at baseline 18
match = re.search(r"Found (\d+) errors?\.", result.stdout + result.stderr)
assert match is not None, f"FAIL: ruff output not parseable: {result.stdout}\n{result.stderr}"
count = int(match.group(1))
assert count == 18, f"FAIL: ruff baseline drift {count} != 18"

print("OK: Phase 10 verification suite passed")
```

Save as `verify_phase10.py` at worktree root + invoke `python verify_phase10.py` at end of each sub-bundle dispatch as the executing-plans inline gate. The Phase 10 SUB-BUNDLE-A integration sweep task (T-A.9) lands this script; subsequent sub-bundles inherit it unchanged.

Why not native PowerShell or Bash: pytest + ruff + the schema-version Python import are the cross-platform load-bearing checks; wrapping them in a single Python script avoids shell-syntax-divergence + allows the `INSERT OR REPLACE` regex to span all Phase 10 scope files (including SHARED files modified per §B which Bash-grep with hardcoded `swing/metrics/` paths would miss — Codex R1 Major #7 specific catch).

### §J.3 Test count projection

| Bundle | New fast tests | Cumulative |
|---|---|---|
| Worktree baseline | — | 2767 |
| Sub-bundle A | +35..+55 | ~2802..2822 |
| Sub-bundle B | +40..+65 | ~2842..2887 |
| Sub-bundle C | +30..+45 | ~2872..2932 |
| Sub-bundle D | +50..+75 | ~2922..3007 |
| Sub-bundle E | +25..+45 | ~2947..3052 |

**Total +180..+285 across the arc.** Trends below Phase 9's +503 because Phase 10 has no schema and no migration runner work. 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures persist UNCHANGED through the arc.

### §J.4 References

- Spec: `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` (commit `fe6cb45`).
- Phase 9 plan: `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (format precedent).
- Phase 9 arc return reports: `docs/phase9-bundle-{A,B,C,D,E}-return-report.md`.
- Phase 8 daily-management plan: `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md`.
- Risk_policy helpers: `swing/data/repos/risk_policy.py` + `swing/trades/risk_policy.py`.
- Account-equity helpers: `swing/data/repos/account_equity_snapshots.py` + `swing/trades/account_equity_snapshots.py`.
- Hypothesis-status-history helpers: `swing/data/repos/hypothesis_status_history.py` + `swing/trades/hypothesis.py`.
- Reconciliation helpers: `swing/data/repos/reconciliation.py` + `swing/trades/reconciliation.py`.
- Daily-management helpers: `swing/data/repos/daily_management.py` + `swing/trades/daily_management.py`.
- Review/process-grade helpers: `swing/trades/review.py` + `swing/data/repos/review_log.py`.
- Derived metrics helpers: `swing/trades/derived_metrics.py` + `swing/trades/equity.py`.
- Honesty + statistical references: Wilson, E. B. (1927); standard percentile bootstrap (Efron 1979).
- CLAUDE.md gotchas: `CLAUDE.md` "Gotchas" section (cumulative gotcha catalog through Phase 9 close).

---

*End of Phase 10 implementation plan. Adversarial Codex review pending per copowers:writing-plans wrapper.*
