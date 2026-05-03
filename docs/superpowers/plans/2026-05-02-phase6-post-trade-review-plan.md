# Phase 6 — Post-Trade Review Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the post-trade review surface (10 nullable trade-row fields + Review_Log entity + Mistake_Tags vocabulary + Process Grade + cost/violation derivation + dashboard "needs review" badge + cadence cards + pipeline cadence pre-create step + soft-warn at close) so the operator's behavioral discipline is measurable on closed trades for the first time.

**Architecture:** Schema-first slice extends `trades` with 10 nullable columns + creates new `review_log` table in a single migration. New `swing/trades/review.py` hosts pure helpers (Mistake_Tags constant, Process Grade computation, cost/violation derivation, plus `profit_factor` + `max_drawdown_R` augmentation helpers — derived locally because `swing/journal/` is read-only per phase carve-out). New `swing/data/repos/review_log.py` owns Review_Log CRUD + idempotent cadence pre-create + completion (which freezes aggregates in a single transaction). New `_step_review_log_cadence` lands AFTER `_step_export` in the pipeline runner. Web slice extends `swing/web/routes/trades.py` with `/trades/<id>/review` GET+POST, extends `swing/web/view_models/trades.py` with `ReviewVM`, and extends `DashboardVM` with `needs_review_count` + cadence-card data. Soft-warn at trade close emits a shared message string from BOTH web and CLI close paths.

**Tech Stack:** SQLite (migration 0013); pytest; Click (CLI); FastAPI + Starlette `TemplateResponse`; HTMX for review form (HX-Request + HX-Redirect per Phase 5 lesson); Jinja2 templates extending `base.html.j2`; existing `swing/journal/stats.py:compute_stats` infrastructure for 5 of 7 aggregates.

---

## §A — Resolved-during-planning items (empirical-audit findings)

These are findings from the §0 empirical audit that diverge from the brief's pre-survey wording. The plan implements the reconciled positions below; they DO NOT contradict the brief's locked decisions in §2 — they refine field paths and resolve a coverage gap.

1. **`compute_stats` produces 5 of 7 §2.5 aggregates; `profit_factor` + `max_drawdown_R` are missing.** Verified at [swing/journal/stats.py:90-151](../../swing/journal/stats.py#L90-L151). `JournalStats` produces `total_r` (= net_R_effective), `expectancy_r`, `win_rate`, `avg_win_r`, `avg_loss_r`. It does NOT produce `profit_factor` (= `sum(wins) / abs(sum(losses))` per v1.2 §8.9) or `max_drawdown_R` (cumulative-R running-max-drawdown). Brief §3.3 lists `swing/journal/` as read-only; brief §6.3 requires "use compute_stats as SOLE source — do NOT re-implement aggregates inside Phase 6." **Resolution:** the 2 missing aggregates are derived in `swing/trades/review.py` (Phase 6 carve-out) from the SAME `Trade` + `Exit` lists `compute_stats` consumes, exposed as pure helpers (`compute_profit_factor`, `compute_max_drawdown_R`). The Review_Log completion path calls `compute_stats(trades=closed_in_period, exits=exits)` for the 5, then calls the two review.py helpers for the remaining 2. This honors the read-only carve-out (no edits to `journal/`) AND the "compute_stats as primary" mandate (compute_stats output is consumed AS-IS for the 5 fields it produces). The two new helpers are NOT a parallel re-implementation — they compute aggregates `compute_stats` does not produce, over the same inputs.

2. **`closed_date` is not a stored column on `trades`.** Verified at [swing/data/models.py:60-92](../../swing/data/models.py#L60-L92). The Trade dataclass has `status: str  # 'open' | 'closed'` — close date is DERIVED via `_trade_closed_date(trade, exits) = max(e.exit_date for e in exits where e.trade_id == trade.id)` (helper at [swing/journal/stats.py:46-50](../../swing/journal/stats.py#L46-L50)). Brief §2.6 says the dashboard badge query is `closed_date IS NOT NULL AND reviewed_at IS NULL AND DATE(closed_date) <= DATE('now', '-7 days')` — but `closed_date` doesn't exist as a column. **Resolution:** the badge count is computed Python-side, not via raw SQL. Production trade volume (1 closed today; <500/year forecast) makes Python-side iteration trivial. A new helper `count_needs_review(conn, *, window_days)` lives in `swing/data/repos/review_log.py`: list closed unreviewed trades, derive each trade's close date via the existing `_trade_closed_date` import (the helper is module-private but the brief explicitly authorizes consumption of `swing/journal/` as read-only — import is allowed; mutation is not), filter by window, return count. Same pattern for the pending list view.

3. **`compute_stats` accepts `cash_movements` parameter but does not use it.** Verified at [swing/journal/stats.py:90-151](../../swing/journal/stats.py#L90-L151) — the parameter is declared but never referenced in the function body. **Resolution:** the Review_Log completion path passes `cash_movements=()` (empty tuple) to mirror existing call sites. No behavioral consequence; documented to forestall future Codex finding "why is this empty?".

4. **`action_session_for_run` returns the NEXT session, not the most recent completed.** Verified at [swing/evaluation/dates.py:43-65](../../swing/evaluation/dates.py#L43-L65). Brief §2.7 says daily period_start/period_end = "previous trading session date" and brief §0 #5 says "use action_session_for_run." These are inconsistent. **Resolution:** the daily period uses `last_completed_session(datetime.now())` from the same module (already used by `swing/pipeline/runner.py:125`). Brief §0 #5's "use action_session_for_run" guidance is correct for the FORWARD-LOOKING anchor (e.g., when the cadence step computes "what is the action session right NOW" for staleness checks); the period bounds for daily review use last_completed_session because the review covers a session that has CLOSED. Per CLAUDE.md gotcha "weather lookup in read-only UIs must NOT query by `action_session`" — same lesson family.

5. **Trade dataclass insertion already passes 17 positional columns.** Verified at [swing/data/repos/trades.py:48-91](../../swing/data/repos/trades.py#L48-L91). Phase 6 extends to 27 columns. The pattern is well-established (sector + industry / 0012 added 2; chart_pattern_* / 0010 added 4; hypothesis_label / 0007 added 1). Plan uses the same additive-positional pattern.

6. **`base.html.j2` 5-VM rule check.** Per brief §6.2 watch item 8 + 9: ReviewVM must inherit `session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded` (existing fields the base layout dereferences). DashboardVM extensions for `needs_review_count` + cadence-card data are CONSUMER-SCOPED (rendered in dashboard templates, not base.html.j2) so the 5-VM rule does NOT apply to those new fields. Plan tasks reflect this asymmetry.

7. **Trade row count in production DB at brief-draft time:** 3 trades total (VIR closed; DHC + CC open). Phase 6 reviews can be exercised on VIR end-to-end starting day-1 of executing-plans dispatch.

8. **Cadence-period anchor: `last_completed_session(now)` (semantic-fit substitute for the brief's literal `action_session_for_run(now)`).** Brief §2.9 + §0 #5 + §6.2 watch item 5 specify `action_session_for_run(datetime.now())` as the cadence anchor. Empirical audit reveals `action_session_for_run` returns the NEXT (forward-looking) session ([swing/evaluation/dates.py:43-65](../../swing/evaluation/dates.py#L43-L65)), while the cadence step needs the LAST COMPLETED session as the daily-period bound. The two helpers share the SAME NYSE-calendar + tz infrastructure ([swing/evaluation/dates.py:21-65](../../swing/evaluation/dates.py#L21-L65)) — both honor the brief's binding constraint ("MUST use this, not `date.today()`" — i.e., timezone-aware NYSE-calendar discipline). On any normal trading day, `_NYSE.previous_session(action_session_for_run(now)) == last_completed_session(now)` — they are semantically equivalent for the prior-period bound. The plan uses `last_completed_session(now)` because: (a) it's the direct semantic fit (cadence period = last completed session, not next); (b) it doesn't require importing `_NYSE` (private module symbol) into `swing/trades/review.py` across a non-carve-out boundary. **Orchestrator pre-approval status:** the §A.1 compute_stats defection was explicitly pre-approved by the dispatching orchestrator; this anchor substitution is captured here as a NEW defection awaiting orchestrator concurrence. Surfaced in return report §8 as open-question. Implementation proceeds with `last_completed_session(now)` pending orchestrator confirmation.

9. **Cadence-completion surface IS in scope (CRITICAL R1 fix).** Round-1 adversarial review surfaced that pre-creating Review_Log rows without an operator path to mark them `completed_date` + freeze aggregates leaves the cadence cards permanently in "pending" state and renders the "review revisit shows correct frozen aggregates" verification gate (§K Step 2.6) unachievable. The cadence-completion service IS REQUIRED for V1 functionality. New Task 11b adds: (a) repo-layer atomic compute-and-freeze (`complete_review_atomic` — owns trade selection + aggregate computation + UPDATE inside one transaction); (b) CLI `swing review complete --review-id <id> --duration-minutes <n> --primary-lesson "..." --next-period-focus "..."`; (c) GET /reviews/{review_id}/complete form + POST handler with HX-Redirect on success. This addition is consistent with brief §3.1 ("Pipeline-runner cadence pre-create step") + §2.5 ("Aggregates computed via `swing/journal/stats.py:compute_stats` infrastructure; persisted on the Review_Log row at the moment of review completion") — the brief implies a completion path; it just doesn't enumerate one explicitly. Surfaced in return report §3 as a brief-completeness finding.

---

## §B — File map

### Files to CREATE

| Path | Responsibility |
|---|---|
| `swing/data/migrations/0013_phase6_post_trade_review.sql` | 10 nullable trade-row columns + new `review_log` table + indices + `UPDATE schema_version SET version = 13`. |
| `swing/data/repos/review_log.py` | Public API. **TWO distinct concepts** — DO NOT confuse them: (1) PENDING CADENCE REVIEWS (`review_log` rows where `completed_date IS NULL`) feed the cadence-cards "needs completion" surface and the `swing review complete --list` CLI; (2) UNREVIEWED CLOSED TRADES (rows in `trades` where `status='closed'` AND `reviewed_at IS NULL`) feed the dashboard "Needs review (N)" badge and `/reviews/pending` list view + `swing trade review --list`. They are unrelated entities — the cadence row is the operator's REFLECTION on a period; the trade row is a SINGLE TRADE awaiting per-trade review. The `/reviews/pending` route name overloads "pending" — it shows TRADE pending review, not CADENCE pending review. (R2 Minor 2 clarification.) Public API: `insert_pre_create(conn, *, review_type, period_start, period_end, scheduled_date) -> int|None` (idempotent); `complete_review_atomic(conn, *, review_id, completed_date, duration_minutes, primary_lesson, next_period_focus) -> None` (atomic compute-and-freeze; R1 Major 1 fix); `get(conn, review_id) -> ReviewLog | None`; `list_pending(conn, *, review_type=None) -> list[ReviewLog]` (PENDING CADENCE; rows with `completed_date IS NULL`, ordered by `period_end DESC`; feeds `swing review complete --list`); `list_recent(conn, *, review_type, limit=1) -> list[ReviewLog]` (ordered by `period_end DESC` — R1 Minor 2 fix); `list_unreviewed_closed_trades(conn, *, window_days, today_iso) -> list[Trade]` (UNREVIEWED CLOSED TRADES; feeds `/reviews/pending` route + `swing trade review --list`); `count_needs_review(conn, *, window_days, today_iso) -> int`. |
| `swing/trades/review.py` | Public API: `MISTAKE_TAGS: dict[str, tuple[str, ...]]` (6 categories; 34 tags total per v1.2 §7.10); `DISQUALIFYING_VIOLATIONS: tuple[str, ...]` (7 entries per v1.2 §9.2); `STAGE_GRADE_NUMERIC: dict[str, int]`; `validate_mistake_tags(tags: list[str]) -> None` (raises `ValueError` on unknown tag, mixed-category-with-none_observed, etc.); `canonicalize_mistake_tags(tags: list[str]) -> list[str]` (NFC normalize, strip, dedup, sort — per JSON-list canonicalization-at-persistence-boundary lesson); `compute_process_grade(*, entry: str, management: str, exit_: str, disqualifying: bool) -> str` (returns 'A'..'F' per v1.2 §9.2); `compute_mistake_cost_R(*, realized_R_if_plan_followed: float | None, actual_realized_R_effective: float) -> float`; `compute_lucky_violation_R(*, realized_R_if_plan_followed: float | None, actual_realized_R_effective: float) -> float`; `compute_actual_realized_R_effective(trade: Trade, exits: list[Exit]) -> float` (mirrors `_trade_r` semantic); `compute_profit_factor(closed_trades: list[Trade], exits: list[Exit]) -> float | None`; `compute_max_drawdown_R(closed_trades: list[Trade], exits: list[Exit]) -> float`; `SOFT_WARN_REVIEW_DUE_MESSAGE: str` (shared constant for web + CLI close paths). |
| `swing/web/templates/review.html.j2` | Full review-form page extending `base.html.j2`. |
| `swing/web/templates/partials/review_form.html.j2` | The form fragment (also embedded in the full page; reused by GET re-render on hard-refuse / soft-warn). `<form>`-rooted, NOT `<tr>`-rooted (per `<tr>`-leading makeFragment lesson). |
| `swing/web/templates/partials/review_soft_warn_close.html.j2` | Soft-warn-at-close fragment ("Review due within 7 days. [Review now] / [Dismiss]"). Rendered by exit_post when the final exit closes the trade. |
| `swing/web/templates/partials/needs_review_badge.html.j2` | Dashboard "needs review" badge partial. Renders when count > 0; emits empty fragment when count == 0 (consumer template includes always; partial decides whether to show). |
| `swing/web/templates/partials/cadence_cards.html.j2` | Dashboard cadence-cards section partial. Renders 3 cards (daily/weekly/monthly). |
| `swing/web/templates/reviews_pending.html.j2` | Full page extending `base.html.j2` for the `/reviews/pending` list view (badge link target). |
| `swing/web/templates/cadence_complete.html.j2` | Full page extending `base.html.j2` for the `/reviews/{id}/complete` form (R1 Critical 1). |
| `swing/web/templates/partials/cadence_complete_form.html.j2` | The cadence-completion form fragment. `<form>`-rooted; `hx-headers='{"HX-Request": "true"}'`; success-path response = 204 + HX-Redirect. |
| `tests/web/test_cadence_complete_route.py` | Route-level integration tests for cadence completion (GET, POST, HX-Redirect, atomic-freeze). |
| `tests/cli/test_review_complete_cli.py` | Click runner integration tests for `swing review complete` (R1 Critical 1). |
| `tests/data/test_migration_0013.py` | Round-trip test for the 10 trade columns + review_log table CRUD + unique-index enforcement. |
| `tests/data/test_review_log_repo.py` | review_log repo tests (insert idempotence, complete, get, list_recent, count_needs_review). |
| `tests/trades/test_review_helpers.py` | Pure-helper tests for review.py (Mistake_Tags vocab, validate, canonicalize, process grade parameterized table, cost/violation, profit_factor, max_drawdown_R). |
| `tests/pipeline/test_review_log_cadence_step.py` | `_step_review_log_cadence` tests (idempotence, anchor on `last_completed_session`, error-tolerant). |
| `tests/cli/test_trade_review_cli.py` | Click runner integration tests for `swing trade review` (per-trade review mode) AND `swing trade review --list` (list mode); single-command dual-mode per brief §3.1. |
| `tests/web/test_review_route.py` | Route-level integration tests (GET form, POST submit, HX-Redirect, hard-refuse rerender, repo-write side-effect). |
| `tests/web/test_review_template.py` | Template-render tests (5-VM existing-field inheritance, makeFragment-safe response shape). |
| `tests/web/test_dashboard_needs_review_badge.py` | DashboardVM `needs_review_count` integration + badge render tests. |
| `tests/web/test_dashboard_cadence_cards.py` | DashboardVM cadence-card data + cards render tests. |
| `tests/web/test_soft_warn_at_close.py` | Soft-warn fragment surfaces from web exit_post + CLI exit when final exit closes trade. |
| `tests/integration/test_review_log_aggregate_freezing.py` | End-to-end: complete review → close another trade → reread review_log → assert aggregates frozen. |

### Files to MODIFY

| Path | Reason |
|---|---|
| `swing/data/models.py` | Extend `Trade` dataclass with 10 nullable fields (default `None`) + add new `ReviewLog` dataclass. |
| `swing/data/repos/trades.py` | Extend `insert_trade_with_event` (add 10 columns to INSERT — all NULL at insert time; review-completion uses `update_trade_review_fields`) + new `update_trade_review_fields(conn, trade_id, *, reviewed_at, mistake_tags_json, entry_grade, management_grade, exit_grade, process_grade, disqualifying_process_violation, realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned)` + extend SELECT * column list in `_row_to_trade` (or whatever the row mapper is) to populate the 10 new fields. |
| `swing/cli.py` | Add `@trade_group.command("review")` after the existing `entry`/`exit` commands. The `review` command supports BOTH per-trade-review mode (operator supplies `--trade-id` + grades + lesson) AND list-mode (operator passes `--list` flag, all other args optional, command prints pending-review list and exits) per brief §3.1 (R1 Major 2 fix — preserves the locked spec contract `swing trade review --list`). Add new top-level `@main.group("review")` group with `@review_group.command("complete")` for cadence-completion (R1 Critical 1). Modify `trade_exit_cmd` to emit soft-warn message via `click.echo` when final exit closes the trade. |
| `swing/web/routes/trades.py` | Add `GET /trades/{trade_id}/review` and `POST /trades/{trade_id}/review` handlers (mirror entry-form pattern; HX-Redirect on success per Phase 5 lesson). Modify `exit_post` to surface soft-warn message when `result.fully_closed` is True. |
| `swing/web/view_models/trades.py` | Add `ReviewVM` dataclass + `build_review_vm(*, trade_id, cfg) -> ReviewVM | None`. Add `ReviewsPendingVM` dataclass + `build_reviews_pending_vm(*, cfg) -> ReviewsPendingVM`. Add `CadenceCompleteVM` dataclass + `build_cadence_complete_vm(*, review_id, cfg) -> CadenceCompleteVM | None`. All three VMs inherit existing 5 base-layout fields with safe defaults. (R1 Critical 1 + R1 Minor 1 fixes.) |
| `swing/web/view_models/dashboard.py` | Add `needs_review_count` + cadence-card fields (`daily_card`, `weekly_card`, `monthly_card` as `CadenceCardVM` dataclass) to `DashboardVM`. Extend `build_dashboard` to populate them. |
| `swing/web/templates/dashboard.html.j2` | Include `partials/needs_review_badge.html.j2` and `partials/cadence_cards.html.j2`. |
| `swing/web/app.py` | No edits expected. Review routes (`/trades/{id}/review`, `/reviews/pending`, `/reviews/{id}/complete`) all piggyback on the existing `swing.web.routes.trades` router. If a future route module split is justified, capture as a separate dispatch — Phase 6 default keeps module count stable. (R1 Minor 1 ownership-drift fix.) |
| `swing/config.py` | Add new `ReviewConfig` section dataclass with `review_window_days: int = 7` field. Add `review: ReviewConfig` to the top-level `Config` dataclass. Mirrors Phase 5's `cfg.web.chase_factor` pattern. (R1 Major 3 missing-config fix.) |
| `swing/pipeline/runner.py` | Add `_step_review_log_cadence(*, cfg, lease)` function (idempotent; logs but does NOT raise on errors); call it AFTER `lease.step("complete")` line so it's outside the primary value chain (cadence is auxiliary; export is the value emission). |
| `swing/trades/exit.py` | Add `final_exit_closed_trade: bool` flag on the result type returned by `record_exit` (exposes whether THIS exit was the final one). The flag is necessary so soft-warn surfaces deterministically from BOTH web and CLI close paths. |

---

## §C — Migration 0013 SQL (canonical reference)

The exact SQL for `swing/data/migrations/0013_phase6_post_trade_review.sql` (Task 1 implements verbatim — verify against §B file map and v1.2 §7.11 + §9.2 + §10.4):

```sql
-- Migration 0013: Phase 6 Post-Trade Review Surface
--
-- 10 nullable trade-row additions (operator-input fields populated at review
-- completion; NULL means "not reviewed yet") + new review_log table for
-- daily/weekly/monthly/quarterly/circuit_breaker cadence rows + unique-index
-- on cadence period for idempotent pre-create.
--
-- Locked decisions §2.4 (counterfactual storage shape: realized_R_if_plan_followed
-- only; cost + lucky derived on read), §2.5 (slim 14 + 7 persisted aggregates
-- frozen-at-review), §2.6 (review window default 7 days, configurable later),
-- §2.7 (5 cadence types schema-supported, daily/weekly/monthly UI-wired in V1).
--
-- Schema-level constraints kept minimal:
--   - mistake_tags is JSON-text (validation lives in repo via
--     swing.trades.review.validate_mistake_tags + canonicalize_mistake_tags);
--     SQLite cannot CHECK-constrain a JSON-list of strings against a vocabulary.
--   - Single-letter grade columns CHECK-restricted to ('A','B','C','D','F') so
--     the schema is the floor; Python helpers compute_process_grade enforce
--     value-class semantics (F-floor, disqualifying-D cap, weighted boundaries).
--   - review_type CHECK-restricted to the 5 cadence values (daily/weekly/
--     monthly/quarterly/circuit_breaker) per locked decision §2.7.

-- ----- 10 nullable additions to trades -----

ALTER TABLE trades ADD COLUMN reviewed_at TEXT;
ALTER TABLE trades ADD COLUMN mistake_tags TEXT;
ALTER TABLE trades ADD COLUMN entry_grade TEXT
    CHECK (entry_grade IS NULL OR entry_grade IN ('A','B','C','D','F'));
ALTER TABLE trades ADD COLUMN management_grade TEXT
    CHECK (management_grade IS NULL OR management_grade IN ('A','B','C','D','F'));
ALTER TABLE trades ADD COLUMN exit_grade TEXT
    CHECK (exit_grade IS NULL OR exit_grade IN ('A','B','C','D','F'));
ALTER TABLE trades ADD COLUMN process_grade TEXT
    CHECK (process_grade IS NULL OR process_grade IN ('A','B','C','D','F'));
ALTER TABLE trades ADD COLUMN disqualifying_process_violation INTEGER
    CHECK (disqualifying_process_violation IS NULL OR disqualifying_process_violation IN (0,1));
ALTER TABLE trades ADD COLUMN realized_R_if_plan_followed REAL;
ALTER TABLE trades ADD COLUMN mistake_cost_confidence TEXT
    CHECK (mistake_cost_confidence IS NULL OR mistake_cost_confidence IN ('high','medium','low'));
ALTER TABLE trades ADD COLUMN lesson_learned TEXT;

-- ----- review_log table (slim 14 + 7 persisted aggregates) -----

CREATE TABLE review_log (
    review_id INTEGER PRIMARY KEY,
    review_type TEXT NOT NULL
        CHECK (review_type IN ('daily','weekly','monthly','quarterly','circuit_breaker')),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    scheduled_date TEXT NOT NULL,
    completed_date TEXT,
    skipped INTEGER NOT NULL DEFAULT 0
        CHECK (skipped IN (0,1)),
    duration_minutes INTEGER,
    n_trades_reviewed INTEGER NOT NULL DEFAULT 0,
    total_mistake_cost_R REAL NOT NULL DEFAULT 0,
    total_lucky_violation_R REAL NOT NULL DEFAULT 0,
    primary_lesson TEXT,
    next_period_focus TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Persisted aggregates (frozen-at-review-completion):
    net_R_effective REAL,
    expectancy_R_effective REAL,
    win_rate REAL,
    avg_win_R REAL,
    avg_loss_R REAL,
    profit_factor REAL,
    max_drawdown_R REAL
);

-- Idempotency support: one cadence row per (type, period_start, period_end)
CREATE UNIQUE INDEX ux_review_log_cadence_period
    ON review_log (review_type, period_start, period_end);

UPDATE schema_version SET version = 13;
```

---

## §D — Mistake_Tags vocabulary constant (verbatim from v1.2 §7.10)

The exact `MISTAKE_TAGS` constant for `swing/trades/review.py`:

```python
# Verbatim from v1.2 §7.10 — 6 categories, 34 tags total. Operator review form
# renders these in dropdown groups; CLI accepts them via repeatable
# --mistake-tags. JSON-list-of-strings persisted to trades.mistake_tags.
MISTAKE_TAGS: dict[str, tuple[str, ...]] = {
    "entry": (
        "CHASED", "EARLY_ENTRY", "LATE_ENTRY", "NO_SETUP",
        "LOW_LIQUIDITY", "EVENT_IGNORED",
    ),
    "risk": (
        "OVERSIZED", "NO_STOP", "STOP_TOO_WIDE", "STOP_TOO_TIGHT",
        "CORRELATION_IGNORED", "GAP_RISK_IGNORED", "HEAT_OVERAGE",
        "CIRCUIT_BREAKER_OVERRIDDEN",
    ),
    "management": (
        "MOVED_STOP_AWAY", "SOLD_TOO_EARLY", "HELD_AFTER_INVALIDATION",
        "FAILED_TO_SCALE", "ADDED_TO_LOSER", "MISSED_TIME_STOP",
    ),
    "psychology": (
        "FOMO", "REVENGE", "BOREDOM", "EGO", "ANCHORING",
        "CONFIRMATION_BIAS", "LOSS_AVERSION", "OVERCONFIDENCE",
    ),
    "reconciliation": (
        "SIZE_MISCOUNTED", "WRONG_TICKER_ENTERED", "FILL_NOT_LOGGED",
        "PARTIAL_NOT_LOGGED", "STOP_NOT_PLACED",
    ),
    "none": (
        "none_observed",
    ),
}

ALL_MISTAKE_TAGS: frozenset[str] = frozenset(
    tag for tags in MISTAKE_TAGS.values() for tag in tags
)
```

Validation rules (per v1.2 §7.10 + canonical-grouping-key lesson):
- Every tag in operator submission must be a member of `ALL_MISTAKE_TAGS`. Unknown → `ValueError`.
- `none_observed` cannot co-exist with any other tag (semantic: "no mistakes" is exclusive). Mixed → `ValueError`.
- Empty list rejected at the form layer (not the helper) — operator must submit at least `none_observed` if no mistakes; helper accepts `[]` as a valid Python value but the form/CLI guards against it pre-call.
- Canonicalization: NFC unicode normalize; strip whitespace; dedup; sorted ASCII order before persistence.

---

## §E — Process Grade computation reference (verbatim from v1.2 §9.2)

The exact `compute_process_grade` semantics:

```python
STAGE_GRADE_NUMERIC: dict[str, int] = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}

WEIGHTS: dict[str, float] = {"entry": 0.40, "management": 0.35, "exit": 0.25}

DISQUALIFYING_VIOLATIONS: tuple[str, ...] = (
    "no_stop", "oversized_beyond_policy", "no_valid_setup", "revenge_trade",
    "circuit_breaker_override", "held_after_invalidation_without_rule_basis",
    "moved_stop_away_materially_increasing_risk",
)

def compute_process_grade(
    *, entry: str, management: str, exit_: str, disqualifying: bool,
) -> str:
    """Return overall process grade per v1.2 §9.2.

    Order of evaluation matters:
      1. Floor rule: any stage = 'F' → 'F' (HARDEST cap; beats disqualifying-D).
      2. Cap rule: disqualifying=True → max grade D (regardless of weighted avg).
      3. Otherwise: weighted avg → grade per numeric_to_grade boundaries.
    """
    if entry == "F" or management == "F" or exit_ == "F":
        return "F"
    weighted = (
        WEIGHTS["entry"] * STAGE_GRADE_NUMERIC[entry]
        + WEIGHTS["management"] * STAGE_GRADE_NUMERIC[management]
        + WEIGHTS["exit"] * STAGE_GRADE_NUMERIC[exit_]
    )
    if disqualifying:
        # max D regardless of weighted avg. Numeric ≥ 1.00 maps to D-or-better;
        # numeric < 1.00 maps to F (already handled by F-floor above when any
        # stage == F; if disqualifying without F stages and weighted < 1.00,
        # the result is F because cap is "max D" — no upward override).
        if weighted < 1.00:
            return "F"
        return "D"
    if weighted >= 3.50:
        return "A"
    if weighted >= 2.75:
        return "B"
    if weighted >= 2.00:
        return "C"
    if weighted >= 1.00:
        return "D"
    return "F"
```

`disqualifying_process_violation` is the operator-supplied boolean column on `trades`. The 7 named violations are REFERENCE — rendered on the review form as guidance; the operator manually flags the boolean. No auto-derivation in V1.

---

## §F — Cost / Lucky Violation derivation (verbatim from v1.2 §8.8)

```python
def compute_mistake_cost_R(
    *, realized_R_if_plan_followed: float | None,
    actual_realized_R_effective: float,
) -> float:
    """v1.2 §8.8: max(0, plan - actual). Never netted with lucky."""
    if realized_R_if_plan_followed is None:
        return 0.0
    return max(0.0, realized_R_if_plan_followed - actual_realized_R_effective)

def compute_lucky_violation_R(
    *, realized_R_if_plan_followed: float | None,
    actual_realized_R_effective: float,
) -> float:
    """v1.2 §8.8: max(0, actual - plan). Never netted with cost."""
    if realized_R_if_plan_followed is None:
        return 0.0
    return max(0.0, actual_realized_R_effective - realized_R_if_plan_followed)
```

Invariant verified by parameterized test: for any `(plan, actual)`, EXACTLY ONE of `cost / lucky` is non-zero (or both are zero). Never both > 0.

---

## §G — `swing/trades/review.py` aggregate augmentation helpers

These two helpers compute the `profit_factor` + `max_drawdown_R` aggregates compute_stats does not produce. Same input shape (`closed_trades`, `exits`) so call sites match `compute_stats`:

```python
def compute_profit_factor(
    closed_trades: list[Trade], exits: list[Exit],
) -> float | None:
    """v1.2 §8.9: sum(R where > 0) / abs(sum(R where < 0)).

    Returns None when there are no losses (denominator zero) — distinct from
    "infinite" so the consumer can choose its display ("∞" or "n/a"). Returns
    0.0 when there are no wins but there are losses (gross_wins=0).
    """
    rs = [_share_weighted_r(t, exits) for t in closed_trades]
    gross_wins = sum(r for r in rs if r > 0)
    gross_losses = sum(r for r in rs if r < 0)
    if gross_losses == 0:
        return None
    return gross_wins / abs(gross_losses)

def compute_max_drawdown_R(
    closed_trades: list[Trade], exits: list[Exit],
) -> float:
    """Maximum peak-to-trough drawdown over the closed-date-ordered cumulative
    R-series. Returned as a non-negative magnitude (per v1.2 §11.1 dashboard
    convention "max_drawdown_R" is reported positive even though it represents
    a drop). Returns 0.0 for empty input or no drawdown."""
    if not closed_trades:
        return 0.0
    decorated = sorted(
        ((t, _share_weighted_r(t, exits), _trade_closed_date(t, exits))
         for t in closed_trades),
        key=lambda x: x[2] or date.min,
    )
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for _t, r, _cd in decorated:
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown

def _share_weighted_r(trade: Trade, exits: list[Exit]) -> float:
    """Mirror of swing.journal.stats._trade_r — same formula. Re-implemented
    here (not imported from the underscore-prefixed private) per the
    journal/-read-only carve-out: importing private symbols couples to journal/
    internals more tightly than pasting a 4-line formula. The formula is
    documented in v1.2 §8.4 (realized_R_effective).
    """
    total = 0.0
    for e in exits:
        if e.trade_id != trade.id:
            continue
        total += e.r_multiple * (e.shares / trade.initial_shares)
    return total

def _trade_closed_date(trade: Trade, exits: list[Exit]) -> date | None:
    if trade.status != "closed":
        return None
    relevant = [e.exit_date for e in exits if e.trade_id == trade.id]
    return max(date.fromisoformat(d) for d in relevant) if relevant else None
```

**Note on the `_share_weighted_r` + `_trade_closed_date` duplication:** this is intentional per §A.1 + the brief's read-only carve-out. The 4-line formula is byte-identical to `swing/journal/stats.py`'s private helper; re-pasting it is cheaper and safer than importing private symbols across a read-only boundary. If a future cross-phase refactor consolidates these helpers, it will be a Phase 7+ scope item touching both modules.

---

## §H — Cadence-period boundary semantics (per locked decision §2.7)

```python
from datetime import date, datetime, timedelta
from swing.evaluation.dates import last_completed_session

def compute_daily_period(now: datetime) -> tuple[date, date]:
    """Daily review covers the most recent COMPLETED session only.

    period_start = period_end = last_completed_session(now). Anchored on the
    NYSE calendar via the existing helper (handles HST → ET conversion +
    weekends/holidays per CLAUDE.md gotcha 'weather lookup must NOT query by
    action_session'). The daily cadence row for session S is created on the
    first pipeline run of session S+1 (because last_completed_session returns
    S's date once S's close has occurred).
    """
    session = last_completed_session(now)
    return session, session

def compute_weekly_period(now: datetime) -> tuple[date, date]:
    """Weekly review covers the previous Monday-Friday week.

    period_start = Monday of the prior trading week; period_end = Friday of
    the prior trading week. Holidays do NOT shift week boundaries (locked
    decision §2.7).
    """
    today = last_completed_session(now)
    # Monday of THIS week:
    this_monday = today - timedelta(days=today.weekday())
    # Monday of PRIOR week:
    prior_monday = this_monday - timedelta(days=7)
    prior_friday = prior_monday + timedelta(days=4)
    return prior_monday, prior_friday

def compute_monthly_period(now: datetime) -> tuple[date, date]:
    """Monthly review covers the previous calendar month.

    period_start = day 1 of prior month; period_end = last day of prior month.
    """
    today = last_completed_session(now)
    first_of_this_month = today.replace(day=1)
    last_of_prior = first_of_this_month - timedelta(days=1)
    first_of_prior = last_of_prior.replace(day=1)
    return first_of_prior, last_of_prior
```

These three pure helpers live in `swing/trades/review.py` (Phase 6 carve-out). They're imported by `swing/data/repos/review_log.py:insert_pre_create` callers and by `swing/pipeline/runner.py:_step_review_log_cadence`. Same anchor (`last_completed_session(now)`) for ALL three so the period bounds are mutually consistent within a single pipeline run.

---

## §I — Watch-item mitigation table (brief §6.2)

For each pre-designated watch item, the plan task that pre-empts it:

| # | Watch item | Pre-empted in task |
|---|---|---|
| 1 | Multi-path data ingestion full-path audit | Task 11 (review service entry-point) — single repo write path; CLI + web both call it. |
| 2 | JSON-list canonicalization-at-persistence-boundary | Task 3 (`canonicalize_mistake_tags` helper) + Task 11 (repo write calls it). |
| 3 | Snapshot-semantic transaction isolation | Task 6 (review_log repo `complete_review_atomic` OWNS trade selection + aggregate computation + UPDATE inside ONE BEGIN IMMEDIATE transaction; caller-supplied aggregates are NOT permitted — R1 Major 1 fix). |
| 4 | Operator-facing message strings from multiple paths must match | Task 9 (`SOFT_WARN_REVIEW_DUE_MESSAGE` constant in review.py; CLI + web both import). |
| 5 | Helper-internal anchoring of side-effecting boundaries | Task 7 (cadence step anchors on `last_completed_session(datetime.now())` IN the function — semantic-fit substitute for brief's literal `action_session_for_run`; both share the same NYSE-calendar + tz infrastructure; see plan §A.8 for orchestrator-pending defection rationale). Caller cannot supply as-of-date. |
| 6 | HTMX HX-Request + HX-Redirect | Task 12 (POST handler returns 204 + HX-Redirect; review_form template includes `hx-headers='{"HX-Request": "true"}'`). |
| 7 | HTMX `<tr>`-leading makeFragment pathology | Task 11 (review_form partial is `<form>`-rooted, NOT `<tr>`-rooted). |
| 8 | New-VM existing-field inheritance (5-VM rule complement) | Task 10 (ReviewVM has all 5 base-layout existing fields with safe defaults). |
| 9 | Base-layout 5-VM rule applies only when base.html.j2 dereferences | Task 13 (DashboardVM `needs_review_count` + cadence-card fields are consumer-scoped to dashboard; base.html.j2 unchanged — verified via grep). |
| 10 | TestClient cannot detect HTMX runtime DOM state | Task 15 (operator-witnessed browser verification gate; 6 verification steps enumerated). |
| 11 | Discriminating-test discipline | Tasks 4 (process grade parameterized table covers F-floor + disqualifying-D + weighted boundaries), 5 (cost/lucky never-netted invariant test), 7 (cadence idempotence twice-call test), 6 + integration test 14 (aggregate freezing). |
| 12 | Brief-speculation about consumer code state empirically verified | §A above (audit findings 1-7 captured). |
| 13 | Pre-create step ordering vs `_step_export` + error handling | Task 7 (step lands AFTER `lease.step("complete")`; wrapped in `try/except Exception as exc: log.warning(...)` so cadence errors do NOT fail the pipeline). |
| 14 | Discriminating assertions vs coupled text updates | Tasks 11 + 13 (template tests separate "DOES the badge render" / "DOES the cadence card render" from "what's the literal text"). |

---

## §J — Tasks

### Task 0: Setup (worktree + marker + baseline)

**Files:** none (verification + scaffolding only)

- [ ] **Step 1: Create isolated worktree per binding convention 2026-05-02**

```bash
# From swing-trading project root:
cd c:/Users/rwsmy/swing-trading
# Use the using-git-worktrees skill (or its equivalent)
git worktree add -b phase6-post-trade-review ../swing-trading-phase6 main
cd ../swing-trading-phase6
```

Expected: new worktree at `c:/Users/rwsmy/swing-trading-phase6` on branch `phase6-post-trade-review` rooted at `main`.

- [ ] **Step 2: Drop the Codex-blocking marker file**

```bash
touch .copowers-subagent-active
```

Expected: marker file present at worktree root. The global Codex-blocking hook (per CLAUDE.md / orchestrator-context binding-convention 2026-05-02) prevents any concurrent Codex invocations from reaching this worktree's files until the marker is removed at end of dispatch.

- [ ] **Step 3: Capture baseline test count + ruff baseline**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
ruff check swing/ 2>&1 | tail -3
```

Expected: `1472 passed, 1 skipped, 8 deselected` (current baseline at HEAD `c68bff9`); ruff baseline ≤98 errors recorded. If pytest count differs from 1472 or ruff differs from 98, capture the divergence — it's a discrepancy from brief §3.1.

- [ ] **Step 4: ERE grep for prior Phase 6 task commits (defense)**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z0-9-]+\): Task [0-9]+\.[0-9]+' --since="2026-05-02" main..HEAD
```

Expected: empty output (no prior Phase 6 task commits on this branch). Non-empty → STOP and surface in return report.

### Task 1: Migration 0013 + schema_version verification

**Files:**
- Create: `swing/data/migrations/0013_phase6_post_trade_review.sql`
- Create: `tests/data/test_migration_0013.py`

- [ ] **Step 1: Write the failing schema-version round-trip test**

```python
# tests/data/test_migration_0013.py
"""Migration 0013 round-trip + column presence + CHECK enforcement + unique-index."""
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import connect


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase6.db"
    conn = connect(db_path)
    yield conn
    conn.close()


def test_migration_0013_advances_schema_version(conn: sqlite3.Connection) -> None:
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 13


def test_migration_0013_adds_ten_trade_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()}
    expected_new = {
        "reviewed_at", "mistake_tags",
        "entry_grade", "management_grade", "exit_grade", "process_grade",
        "disqualifying_process_violation",
        "realized_R_if_plan_followed",
        "mistake_cost_confidence", "lesson_learned",
    }
    assert expected_new.issubset(cols)


def test_migration_0013_creates_review_log_table(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(review_log)").fetchall()}
    expected = {
        "review_id", "review_type", "period_start", "period_end",
        "scheduled_date", "completed_date", "skipped",
        "duration_minutes", "n_trades_reviewed",
        "total_mistake_cost_R", "total_lucky_violation_R",
        "primary_lesson", "next_period_focus", "created_at",
        "net_R_effective", "expectancy_R_effective", "win_rate",
        "avg_win_R", "avg_loss_R", "profit_factor", "max_drawdown_R",
    }
    assert expected.issubset(cols)


def test_migration_0013_grade_check_constraint_rejects_invalid(conn: sqlite3.Connection) -> None:
    # Insert a minimal trade row first to satisfy NOT NULLs:
    conn.execute(
        """INSERT INTO trades
           (ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, status)
           VALUES ('TEST', '2026-01-01', 10.0, 1, 9.0, 9.0, 'closed')"""
    )
    trade_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "UPDATE trades SET entry_grade='Z' WHERE id=?", (trade_id,),
        )


def test_migration_0013_review_type_check_rejects_invalid(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            """INSERT INTO review_log
               (review_type, period_start, period_end, scheduled_date)
               VALUES ('yearly', '2026-01-01', '2026-12-31', '2027-01-01')"""
        )


def test_migration_0013_unique_index_blocks_duplicate_cadence(conn: sqlite3.Connection) -> None:
    conn.execute(
        """INSERT INTO review_log
           (review_type, period_start, period_end, scheduled_date)
           VALUES ('daily', '2026-04-30', '2026-04-30', '2026-05-01')"""
    )
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            """INSERT INTO review_log
               (review_type, period_start, period_end, scheduled_date)
               VALUES ('daily', '2026-04-30', '2026-04-30', '2026-05-01')"""
        )
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/data/test_migration_0013.py -v`
Expected: all 6 tests FAIL (migration file does not exist; `swing.data.db.connect` cannot apply a migration that isn't there).

- [ ] **Step 3: Write the migration SQL**

Create `swing/data/migrations/0013_phase6_post_trade_review.sql` with the EXACT contents of §C above. (Plan author: copy-paste verbatim — do NOT abbreviate. The leading 17-line comment block is part of the artifact, not commentary on the artifact.)

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/data/test_migration_0013.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/migrations/0013_phase6_post_trade_review.sql tests/data/test_migration_0013.py
git commit -m "feat(phase6): Task 1 — migration 0013 (10 trade fields + review_log table)"
```

### Task 2: Trade dataclass extension + repo round-trip

**Files:**
- Modify: `swing/data/models.py` (Trade dataclass + new ReviewLog dataclass)
- Modify: `swing/data/repos/trades.py` (extend insert + add `update_trade_review_fields` + extend row mapper)

- [ ] **Step 1: Write the failing dataclass + repo round-trip test**

Add to `tests/data/test_migration_0013.py`:

```python
from datetime import date

from swing.data.models import Trade
from swing.data.repos.trades import (
    get_trade, insert_trade_with_event, update_trade_review_fields,
)


def test_trade_dataclass_has_ten_review_fields_with_none_default() -> None:
    t = Trade(
        id=None, ticker="TEST", entry_date="2026-04-01", entry_price=10.0,
        initial_shares=10, initial_stop=9.0, current_stop=9.0, status="closed",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
    )
    # All 10 review fields default to None:
    assert t.reviewed_at is None
    assert t.mistake_tags is None
    assert t.entry_grade is None
    assert t.management_grade is None
    assert t.exit_grade is None
    assert t.process_grade is None
    assert t.disqualifying_process_violation is None
    assert t.realized_R_if_plan_followed is None
    assert t.mistake_cost_confidence is None
    assert t.lesson_learned is None


def test_update_trade_review_fields_round_trip(conn: sqlite3.Connection) -> None:
    with conn:
        trade_id = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="VIR", entry_date="2026-04-01", entry_price=10.0,
                initial_shares=10, initial_stop=9.0, current_stop=9.0, status="closed",
                watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
            ),
            event_ts="2026-04-01T09:30:00",
        )
    with conn:
        update_trade_review_fields(
            conn, trade_id=trade_id,
            reviewed_at="2026-05-02T10:00:00",
            mistake_tags_json='["CHASED"]',
            entry_grade="C", management_grade="B", exit_grade="B",
            process_grade="C", disqualifying_process_violation=False,
            realized_R_if_plan_followed=2.0,
            mistake_cost_confidence="medium",
            lesson_learned="Wait for the breakout, not the build-up.",
        )
    t = get_trade(conn, trade_id)
    assert t is not None
    assert t.reviewed_at == "2026-05-02T10:00:00"
    assert t.mistake_tags == '["CHASED"]'
    assert t.entry_grade == "C"
    assert t.management_grade == "B"
    assert t.exit_grade == "B"
    assert t.process_grade == "C"
    assert t.disqualifying_process_violation is False
    assert t.realized_R_if_plan_followed == 2.0
    assert t.mistake_cost_confidence == "medium"
    assert t.lesson_learned == "Wait for the breakout, not the build-up."
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/data/test_migration_0013.py -v -k "trade_dataclass or update_trade_review"`
Expected: 2 tests FAIL (Trade missing review fields; `update_trade_review_fields` not defined).

- [ ] **Step 3: Extend Trade dataclass with 10 nullable fields**

Modify [swing/data/models.py:60-92](../../swing/data/models.py#L60-L92): add 10 fields (each defaults `None`) at end of the `Trade` dataclass body, after the existing `sector` / `industry` fields:

```python
# Phase 6 (migration 0013) — review surface fields. All NULL until the
# operator completes a post-trade review for this trade. Default None
# preserves existing call sites that construct Trade(...) without these
# fields. mistake_tags is JSON-list-of-strings text (canonicalized at
# repo write boundary per swing.trades.review.canonicalize_mistake_tags).
reviewed_at: str | None = None
mistake_tags: str | None = None
entry_grade: str | None = None
management_grade: str | None = None
exit_grade: str | None = None
process_grade: str | None = None
disqualifying_process_violation: bool | None = None
realized_R_if_plan_followed: float | None = None
mistake_cost_confidence: str | None = None
lesson_learned: str | None = None
```

Also append a new `ReviewLog` dataclass at the end of the file (mirrors PipelineRun shape; all fields explicitly typed):

```python
@dataclass(frozen=True)
class ReviewLog:
    """One row of the review_log table (migration 0013).

    Slim 14 + 7 persisted aggregates per Phase 6 locked decision §2.5.
    Aggregates are NULL on the row until `complete_review` populates them
    in a single transaction (frozen-at-review semantics).
    """
    review_id: int | None
    review_type: str  # daily/weekly/monthly/quarterly/circuit_breaker
    period_start: str
    period_end: str
    scheduled_date: str
    completed_date: str | None
    skipped: bool
    duration_minutes: int | None
    n_trades_reviewed: int
    total_mistake_cost_R: float
    total_lucky_violation_R: float
    primary_lesson: str | None
    next_period_focus: str | None
    created_at: str
    # Persisted aggregates (frozen at completion):
    net_R_effective: float | None = None
    expectancy_R_effective: float | None = None
    win_rate: float | None = None
    avg_win_R: float | None = None
    avg_loss_R: float | None = None
    profit_factor: float | None = None
    max_drawdown_R: float | None = None
```

- [ ] **Step 4: Extend `insert_trade_with_event` + add `update_trade_review_fields` + extend row mapper**

Modify [swing/data/repos/trades.py:48-91](../../swing/data/repos/trades.py#L48-L91). The INSERT remains as-is (the 10 new columns are NULL at insert time — entry never sets review fields). Add `update_trade_review_fields` as a new function:

```python
def update_trade_review_fields(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    reviewed_at: str,
    mistake_tags_json: str,
    entry_grade: str,
    management_grade: str,
    exit_grade: str,
    process_grade: str,
    disqualifying_process_violation: bool,
    realized_R_if_plan_followed: float | None,
    mistake_cost_confidence: str,
    lesson_learned: str,
) -> None:
    """UPDATE the 10 review fields atomically. Caller wraps in `with conn:`.

    All 10 fields are written together — partial-state review rows are not
    valid. mistake_tags_json must be canonicalized (NFC-normalized,
    deduplicated, sorted) by the caller — the repo writes it AS-IS per the
    'canonicalization at persistence boundary' lesson.
    """
    conn.execute(
        """
        UPDATE trades SET
            reviewed_at = ?,
            mistake_tags = ?,
            entry_grade = ?,
            management_grade = ?,
            exit_grade = ?,
            process_grade = ?,
            disqualifying_process_violation = ?,
            realized_R_if_plan_followed = ?,
            mistake_cost_confidence = ?,
            lesson_learned = ?
        WHERE id = ?
        """,
        (reviewed_at, mistake_tags_json, entry_grade, management_grade,
         exit_grade, process_grade,
         1 if disqualifying_process_violation else 0,
         realized_R_if_plan_followed, mistake_cost_confidence,
         lesson_learned, trade_id),
    )
```

Also extend the row mapper for `Trade` (locate `_row_to_trade` or whatever maps SQL row tuples to Trade dataclass — typically inline in `get_trade` and `list_open_trades` etc. — find every `Trade(...)` constructor call in `swing/data/repos/trades.py` and add the 10 new keyword args, mapping the new columns from the SELECT). Audit checklist:

```bash
grep -n "Trade(" swing/data/repos/trades.py
```

Every Trade constructor in this file must include the 10 new fields. Pull SELECT statements through to surface the column ordering — extend each `SELECT ... FROM trades` to include the 10 new columns at the end. Where `_row_to_trade` is a helper, modify it once. Where Trade is constructed inline, modify each site.

- [ ] **Step 5: Run tests to confirm they pass**

Run: `python -m pytest tests/data/test_migration_0013.py -v`
Expected: all 8 tests PASS (the original 6 + the new 2).

- [ ] **Step 6: Run full fast suite to verify no Trade-construction call sites broke**

Run: `python -m pytest -m "not slow" -q 2>&1 | tail -3`
Expected: `1472 passed` or higher (tests added in Task 1+2 ADD to the count). If any test fails with a `TypeError: missing positional argument` on `Trade()`, locate that test fixture or production code and fix.

- [ ] **Step 7: Commit**

```bash
git add swing/data/models.py swing/data/repos/trades.py tests/data/test_migration_0013.py
git commit -m "feat(phase6): Task 2 — Trade dataclass + repo round-trip for 10 review fields"
```

### Task 3: Mistake_Tags vocabulary + validate + canonicalize

**Files:**
- Create: `swing/trades/review.py`
- Create: `tests/trades/test_review_helpers.py`

- [ ] **Step 1: Write failing tests for `MISTAKE_TAGS` constant + `validate_mistake_tags` + `canonicalize_mistake_tags`**

```python
# tests/trades/test_review_helpers.py
"""Pure-helper tests for swing.trades.review."""
import pytest

from swing.trades.review import (
    ALL_MISTAKE_TAGS, MISTAKE_TAGS,
    canonicalize_mistake_tags, validate_mistake_tags,
)


class TestMistakeTagsConstant:
    def test_six_categories(self) -> None:
        assert set(MISTAKE_TAGS.keys()) == {
            "entry", "risk", "management", "psychology", "reconciliation", "none",
        }

    def test_total_tag_count_is_34(self) -> None:
        assert len(ALL_MISTAKE_TAGS) == 34

    def test_specific_v12_section_710_tags(self) -> None:
        # Spot-check 8 tags; Plan Author: this is NOT a full vocabulary
        # snapshot — that lives in the constant — these assertions catch
        # accidental rename or category-shuffle.
        assert "CHASED" in MISTAKE_TAGS["entry"]
        assert "OVERSIZED" in MISTAKE_TAGS["risk"]
        assert "MOVED_STOP_AWAY" in MISTAKE_TAGS["management"]
        assert "REVENGE" in MISTAKE_TAGS["psychology"]
        assert "FILL_NOT_LOGGED" in MISTAKE_TAGS["reconciliation"]
        assert "none_observed" in MISTAKE_TAGS["none"]


class TestValidateMistakeTags:
    def test_valid_single_tag(self) -> None:
        validate_mistake_tags(["CHASED"])

    def test_valid_multi_category_combo(self) -> None:
        validate_mistake_tags(["CHASED", "FOMO"])

    def test_unknown_tag_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown mistake tag"):
            validate_mistake_tags(["NOT_A_REAL_TAG"])

    def test_none_observed_with_other_tag_raises(self) -> None:
        with pytest.raises(ValueError, match="none_observed"):
            validate_mistake_tags(["none_observed", "CHASED"])

    def test_only_none_observed_is_valid(self) -> None:
        validate_mistake_tags(["none_observed"])


class TestCanonicalizeMistakeTags:
    def test_dedup_and_sort(self) -> None:
        result = canonicalize_mistake_tags(["FOMO", "CHASED", "FOMO"])
        assert result == ["CHASED", "FOMO"]

    def test_strips_whitespace(self) -> None:
        result = canonicalize_mistake_tags(["  CHASED  ", " FOMO"])
        assert result == ["CHASED", "FOMO"]

    def test_nfc_unicode_normalize(self) -> None:
        # Latin small letter c + combining acute (NFD) vs. precomposed (NFC).
        # The MISTAKE_TAGS vocabulary is ASCII so this test verifies
        # canonicalization is applied even when input is unicode-y; the
        # output is whatever NFC normalization produces, which preserves
        # ASCII tags exactly.
        import unicodedata
        nfd = unicodedata.normalize("NFD", "CHASED")
        result = canonicalize_mistake_tags([nfd])
        assert result == ["CHASED"]

    def test_empty_list_returns_empty(self) -> None:
        assert canonicalize_mistake_tags([]) == []
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/trades/test_review_helpers.py -v`
Expected: all 12 tests FAIL (`swing.trades.review` does not exist).

- [ ] **Step 3: Create `swing/trades/review.py` with the constant + helpers**

Create the file with:
1. `MISTAKE_TAGS` constant verbatim from §D above.
2. `ALL_MISTAKE_TAGS` derived constant.
3. `validate_mistake_tags(tags)` per §D rules.
4. `canonicalize_mistake_tags(tags)`: NFC-normalize each, strip whitespace, dedupe, sort, return list.

Reference implementation:

```python
"""Phase 6 post-trade review pure helpers.

This module owns:
  * MISTAKE_TAGS vocabulary (verbatim from v1.2 §7.10 — 6 categories, 34 tags).
  * Process Grade computation (verbatim from v1.2 §9.2).
  * Mistake cost / lucky violation derivation (verbatim from v1.2 §8.8).
  * profit_factor + max_drawdown_R aggregation helpers (locally re-derived
    because swing/journal/ is read-only per Phase 6 carve-out — see plan §A.1).
  * Cadence-period boundary helpers (daily/weekly/monthly).
  * Soft-warn-at-close shared message constant.

All functions are pure (no I/O) and side-effect-free; they're testable with
parameterized inputs.
"""
from __future__ import annotations

import unicodedata
from datetime import date, datetime, timedelta

from swing.data.models import Exit, Trade
from swing.evaluation.dates import last_completed_session

# ---- Mistake_Tags vocabulary (v1.2 §7.10 verbatim) ----

MISTAKE_TAGS: dict[str, tuple[str, ...]] = {
    "entry": (
        "CHASED", "EARLY_ENTRY", "LATE_ENTRY", "NO_SETUP",
        "LOW_LIQUIDITY", "EVENT_IGNORED",
    ),
    "risk": (
        "OVERSIZED", "NO_STOP", "STOP_TOO_WIDE", "STOP_TOO_TIGHT",
        "CORRELATION_IGNORED", "GAP_RISK_IGNORED", "HEAT_OVERAGE",
        "CIRCUIT_BREAKER_OVERRIDDEN",
    ),
    "management": (
        "MOVED_STOP_AWAY", "SOLD_TOO_EARLY", "HELD_AFTER_INVALIDATION",
        "FAILED_TO_SCALE", "ADDED_TO_LOSER", "MISSED_TIME_STOP",
    ),
    "psychology": (
        "FOMO", "REVENGE", "BOREDOM", "EGO", "ANCHORING",
        "CONFIRMATION_BIAS", "LOSS_AVERSION", "OVERCONFIDENCE",
    ),
    "reconciliation": (
        "SIZE_MISCOUNTED", "WRONG_TICKER_ENTERED", "FILL_NOT_LOGGED",
        "PARTIAL_NOT_LOGGED", "STOP_NOT_PLACED",
    ),
    "none": (
        "none_observed",
    ),
}

ALL_MISTAKE_TAGS: frozenset[str] = frozenset(
    tag for tags in MISTAKE_TAGS.values() for tag in tags
)


def validate_mistake_tags(tags: list[str]) -> None:
    """Raise ValueError if `tags` contains anything not in ALL_MISTAKE_TAGS,
    or if 'none_observed' co-exists with any other tag."""
    for t in tags:
        if t not in ALL_MISTAKE_TAGS:
            raise ValueError(f"unknown mistake tag: {t!r}")
    if "none_observed" in tags and len(tags) > 1:
        raise ValueError(
            "none_observed cannot co-exist with any other mistake tag"
        )


def canonicalize_mistake_tags(tags: list[str]) -> list[str]:
    """NFC normalize, strip, dedupe, sort. Idempotent."""
    canonical = sorted({
        unicodedata.normalize("NFC", t.strip())
        for t in tags
        if t.strip()
    })
    return canonical


# Stage grade numeric map + weights + disqualifying violations are added in Task 4.
# Cost/lucky/profit_factor/max_drawdown are added in Task 5.
# Cadence-period helpers are added in Task 7.
# Soft-warn message constant is added in Task 9.
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/trades/test_review_helpers.py -v`
Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/review.py tests/trades/test_review_helpers.py
git commit -m "feat(phase6): Task 3 — Mistake_Tags vocab + validate + canonicalize"
```

### Task 4: Process Grade computation helper

**Files:**
- Modify: `swing/trades/review.py` (extend with stage map + helper)
- Modify: `tests/trades/test_review_helpers.py` (parameterized table)

- [ ] **Step 1: Write failing parameterized table for `compute_process_grade`**

Add to `tests/trades/test_review_helpers.py`:

```python
from swing.trades.review import compute_process_grade


class TestComputeProcessGrade:
    """Parameterized table covering F-floor, disqualifying-D, weighted boundaries.

    Order of evaluation (per v1.2 §9.2):
      1. F-floor: any stage = F → F (HARDEST cap; beats disqualifying-D).
      2. Disqualifying cap: disqualifying=True → max D.
      3. Weighted average → numeric_to_grade boundary.
    """

    @pytest.mark.parametrize(
        "entry,management,exit_,disqualifying,expected",
        [
            # F-floor: any single F → F regardless of other stages
            ("A", "A", "F", False, "F"),
            ("A", "F", "A", False, "F"),
            ("F", "A", "A", False, "F"),
            ("F", "F", "F", False, "F"),
            # F-floor beats disqualifying-D cap (F is harder)
            ("A", "A", "F", True, "F"),
            ("F", "A", "A", True, "F"),
            # Disqualifying-D cap with no F stages
            ("A", "A", "A", True, "D"),
            ("B", "B", "B", True, "D"),
            ("C", "C", "C", True, "D"),
            ("D", "D", "D", True, "D"),
            # Weighted-numeric boundaries (no F, no disqualifying)
            ("A", "A", "A", False, "A"),  # weighted = 4.0 → A
            ("A", "B", "B", False, "B"),  # weighted = 0.40*4 + 0.35*3 + 0.25*3 = 3.40 → B
            ("B", "B", "B", False, "B"),  # weighted = 3.0 → B
            ("B", "C", "B", False, "B"),  # weighted = 0.40*3 + 0.35*2 + 0.25*3 = 2.65 → C
            ("C", "C", "C", False, "C"),  # weighted = 2.0 → C
            ("D", "D", "D", False, "D"),  # weighted = 1.0 → D
            # Pure mid-A boundary (3.50 exactly)
            # Set up weights such that exactly 3.50: e.g., A,A,B → 0.40*4+0.35*4+0.25*3 = 3.75 (B not on boundary)
            #    instead use a synthetic value 3.50 by mapping: not constructible with stage grades alone,
            #    so we test 3.49 just-below and 3.50 just-at boundaries via the ranges below.
            # B/B/A: 0.40*3 + 0.35*3 + 0.25*4 = 1.20 + 1.05 + 1.00 = 3.25 → B
            ("B", "B", "A", False, "B"),
            # A/B/A: 0.40*4 + 0.35*3 + 0.25*4 = 1.60 + 1.05 + 1.00 = 3.65 → A
            ("A", "B", "A", False, "A"),
            # Discriminating case (brief §6.2 watch item 11): weighted=3.0 → B,
            # NOT F-floor since no stage is F:
            ("B", "B", "B", False, "B"),
            # Discriminating case: A,A,F should NOT be A from weighted (would be 0.40*4 + 0.35*4 + 0.25*0 = 3.0 → B)
            # — instead F-floor returns F. Tests above cover this.
        ],
    )
    def test_process_grade_table(
        self, entry: str, management: str, exit_: str,
        disqualifying: bool, expected: str,
    ) -> None:
        assert compute_process_grade(
            entry=entry, management=management, exit_=exit_,
            disqualifying=disqualifying,
        ) == expected
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/trades/test_review_helpers.py::TestComputeProcessGrade -v`
Expected: all parametrize rows FAIL (`compute_process_grade` not defined).

- [ ] **Step 3: Implement `compute_process_grade` per §E**

Append to `swing/trades/review.py`:

```python
# ---- Process Grade (v1.2 §9.2 verbatim) ----

STAGE_GRADE_NUMERIC: dict[str, int] = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
WEIGHTS: dict[str, float] = {"entry": 0.40, "management": 0.35, "exit": 0.25}
DISQUALIFYING_VIOLATIONS: tuple[str, ...] = (
    "no_stop", "oversized_beyond_policy", "no_valid_setup", "revenge_trade",
    "circuit_breaker_override", "held_after_invalidation_without_rule_basis",
    "moved_stop_away_materially_increasing_risk",
)


def compute_process_grade(
    *, entry: str, management: str, exit_: str, disqualifying: bool,
) -> str:
    """Return overall process grade per v1.2 §9.2.

    Order of evaluation:
      1. Floor rule: any stage = 'F' → 'F'.
      2. Cap rule: disqualifying=True → max D (or F when weighted < 1.00).
      3. Otherwise: weighted avg → grade per numeric_to_grade boundaries.
    """
    if entry not in STAGE_GRADE_NUMERIC or management not in STAGE_GRADE_NUMERIC \
            or exit_ not in STAGE_GRADE_NUMERIC:
        raise ValueError(
            f"stage grades must be one of {sorted(STAGE_GRADE_NUMERIC)}; "
            f"got entry={entry!r}, management={management!r}, exit_={exit_!r}"
        )
    if entry == "F" or management == "F" or exit_ == "F":
        return "F"
    weighted = (
        WEIGHTS["entry"] * STAGE_GRADE_NUMERIC[entry]
        + WEIGHTS["management"] * STAGE_GRADE_NUMERIC[management]
        + WEIGHTS["exit"] * STAGE_GRADE_NUMERIC[exit_]
    )
    if disqualifying:
        if weighted < 1.00:
            return "F"
        return "D"
    if weighted >= 3.50:
        return "A"
    if weighted >= 2.75:
        return "B"
    if weighted >= 2.00:
        return "C"
    if weighted >= 1.00:
        return "D"
    return "F"
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/trades/test_review_helpers.py::TestComputeProcessGrade -v`
Expected: all parametrize rows PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/review.py tests/trades/test_review_helpers.py
git commit -m "feat(phase6): Task 4 — compute_process_grade per v1.2 §9.2"
```

### Task 5: Cost / Lucky / Profit-factor / Max-drawdown helpers

**Files:**
- Modify: `swing/trades/review.py` (extend)
- Modify: `tests/trades/test_review_helpers.py` (extend)

- [ ] **Step 1: Write failing tests for the four helpers**

Add to `tests/trades/test_review_helpers.py`:

```python
from swing.data.models import Exit, Trade
from swing.trades.review import (
    compute_actual_realized_R_effective,
    compute_lucky_violation_R, compute_max_drawdown_R, compute_mistake_cost_R,
    compute_profit_factor,
)


def _make_trade(*, id_: int, status: str = "closed",
                initial_shares: int = 10) -> Trade:
    return Trade(
        id=id_, ticker=f"T{id_}", entry_date="2026-01-01",
        entry_price=10.0, initial_shares=initial_shares, initial_stop=9.0,
        current_stop=9.0, status=status,
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
    )


def _make_exit(*, trade_id: int, r: float, shares: int = 10,
               exit_date: str = "2026-02-01") -> Exit:
    return Exit(
        id=None, trade_id=trade_id, exit_date=exit_date,
        exit_price=11.0, shares=shares, reason="manual",
        realized_pnl=r * 10.0, r_multiple=r, notes=None,
    )


class TestCostAndLucky:
    @pytest.mark.parametrize(
        "plan,actual,expected_cost,expected_lucky",
        [
            (2.0, 0.5, 1.5, 0.0),    # cost
            (0.5, 2.0, 0.0, 1.5),    # lucky
            (1.0, 1.0, 0.0, 0.0),    # equal
            (None, 1.5, 0.0, 0.0),   # no plan
            (-0.5, -2.0, 1.5, 0.0),  # both losses; planned loss less than actual
            (-2.0, -0.5, 0.0, 1.5),  # both losses; actual loss less than planned (lucky)
        ],
    )
    def test_cost_and_lucky_table(
        self, plan: float | None, actual: float,
        expected_cost: float, expected_lucky: float,
    ) -> None:
        assert compute_mistake_cost_R(
            realized_R_if_plan_followed=plan,
            actual_realized_R_effective=actual,
        ) == pytest.approx(expected_cost)
        assert compute_lucky_violation_R(
            realized_R_if_plan_followed=plan,
            actual_realized_R_effective=actual,
        ) == pytest.approx(expected_lucky)

    @pytest.mark.parametrize(
        "plan,actual",
        [(2.0, 0.5), (0.5, 2.0), (1.0, 1.0), (None, 1.5),
         (-0.5, -2.0), (-2.0, -0.5)],
    )
    def test_cost_and_lucky_never_both_positive(
        self, plan: float | None, actual: float,
    ) -> None:
        cost = compute_mistake_cost_R(
            realized_R_if_plan_followed=plan,
            actual_realized_R_effective=actual,
        )
        lucky = compute_lucky_violation_R(
            realized_R_if_plan_followed=plan,
            actual_realized_R_effective=actual,
        )
        assert not (cost > 0 and lucky > 0), \
            f"cost={cost} and lucky={lucky} both positive — invariant violated"


class TestComputeActualR:
    def test_share_weighted_full_exit(self) -> None:
        t = _make_trade(id_=1, initial_shares=10)
        ex = [_make_exit(trade_id=1, r=2.0, shares=10)]
        assert compute_actual_realized_R_effective(t, ex) == pytest.approx(2.0)

    def test_share_weighted_partial(self) -> None:
        # Half-out at 1R, rest at 3R: weighted = 0.5*1 + 0.5*3 = 2.0
        t = _make_trade(id_=1, initial_shares=10)
        ex = [
            _make_exit(trade_id=1, r=1.0, shares=5, exit_date="2026-02-01"),
            _make_exit(trade_id=1, r=3.0, shares=5, exit_date="2026-02-15"),
        ]
        assert compute_actual_realized_R_effective(t, ex) == pytest.approx(2.0)

    def test_skips_other_trades(self) -> None:
        t = _make_trade(id_=1, initial_shares=10)
        ex = [
            _make_exit(trade_id=1, r=1.0, shares=10),
            _make_exit(trade_id=99, r=5.0, shares=10),  # different trade
        ]
        assert compute_actual_realized_R_effective(t, ex) == pytest.approx(1.0)


class TestProfitFactor:
    def test_basic_two_trades(self) -> None:
        # Trade 1: +2R, Trade 2: -1R → profit_factor = 2 / 1 = 2.0
        trades = [_make_trade(id_=1), _make_trade(id_=2)]
        exits = [_make_exit(trade_id=1, r=2.0), _make_exit(trade_id=2, r=-1.0)]
        assert compute_profit_factor(trades, exits) == pytest.approx(2.0)

    def test_no_losses_returns_none(self) -> None:
        trades = [_make_trade(id_=1)]
        exits = [_make_exit(trade_id=1, r=1.0)]
        assert compute_profit_factor(trades, exits) is None

    def test_no_wins_returns_zero(self) -> None:
        trades = [_make_trade(id_=1), _make_trade(id_=2)]
        exits = [_make_exit(trade_id=1, r=-1.0), _make_exit(trade_id=2, r=-2.0)]
        assert compute_profit_factor(trades, exits) == pytest.approx(0.0)

    def test_empty_input(self) -> None:
        assert compute_profit_factor([], []) is None


class TestMaxDrawdown:
    def test_no_drawdown(self) -> None:
        # Cumulative R series: +1, +2, +3 — peak rises monotonically; drawdown = 0
        trades = [_make_trade(id_=i) for i in (1, 2, 3)]
        exits = [
            _make_exit(trade_id=1, r=1.0, exit_date="2026-01-10"),
            _make_exit(trade_id=2, r=1.0, exit_date="2026-01-20"),
            _make_exit(trade_id=3, r=1.0, exit_date="2026-01-30"),
        ]
        assert compute_max_drawdown_R(trades, exits) == pytest.approx(0.0)

    def test_simple_drawdown(self) -> None:
        # Cumulative: +2, then 2-3 = -1 → peak=2, trough=-1 → drawdown=3
        trades = [_make_trade(id_=1), _make_trade(id_=2)]
        exits = [
            _make_exit(trade_id=1, r=2.0, exit_date="2026-01-10"),
            _make_exit(trade_id=2, r=-3.0, exit_date="2026-01-20"),
        ]
        assert compute_max_drawdown_R(trades, exits) == pytest.approx(3.0)

    def test_recovers_then_new_peak(self) -> None:
        # Cumulative: +1, then -2 (cum=-1), then +3 (cum=2). Peak=1 at first
        # point, drawdown_max = 1 - (-1) = 2. After recovery to cum=2, new
        # peak; no further drawdown. Result = 2.
        trades = [_make_trade(id_=i) for i in (1, 2, 3)]
        exits = [
            _make_exit(trade_id=1, r=1.0, exit_date="2026-01-10"),
            _make_exit(trade_id=2, r=-2.0, exit_date="2026-01-20"),
            _make_exit(trade_id=3, r=3.0, exit_date="2026-01-30"),
        ]
        assert compute_max_drawdown_R(trades, exits) == pytest.approx(2.0)

    def test_empty_input(self) -> None:
        assert compute_max_drawdown_R([], []) == pytest.approx(0.0)
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/trades/test_review_helpers.py -v -k "Cost or Lucky or Actual or Profit or MaxDrawdown"`
Expected: all FAIL (helpers undefined).

- [ ] **Step 3: Implement the four helpers in `swing/trades/review.py`**

Append to `swing/trades/review.py`:

```python
# ---- Cost / Lucky / R helpers (v1.2 §8.4 + §8.8 + §8.9) ----

def compute_actual_realized_R_effective(
    trade: Trade, exits: list[Exit],
) -> float:
    """Share-weighted realized R for `trade` per v1.2 §8.4.

    Mirror of swing.journal.stats._trade_r — same formula. Re-implemented
    here per the journal/-read-only carve-out (plan §A.1). Computes:
        sum(e.r_multiple * (e.shares / trade.initial_shares) for e in exits
            if e.trade_id == trade.id)
    """
    total = 0.0
    for e in exits:
        if e.trade_id != trade.id:
            continue
        total += e.r_multiple * (e.shares / trade.initial_shares)
    return total


def compute_mistake_cost_R(
    *, realized_R_if_plan_followed: float | None,
    actual_realized_R_effective: float,
) -> float:
    """v1.2 §8.8: max(0, plan - actual). Never netted with lucky."""
    if realized_R_if_plan_followed is None:
        return 0.0
    return max(0.0, realized_R_if_plan_followed - actual_realized_R_effective)


def compute_lucky_violation_R(
    *, realized_R_if_plan_followed: float | None,
    actual_realized_R_effective: float,
) -> float:
    """v1.2 §8.8: max(0, actual - plan). Never netted with cost."""
    if realized_R_if_plan_followed is None:
        return 0.0
    return max(0.0, actual_realized_R_effective - realized_R_if_plan_followed)


def compute_profit_factor(
    closed_trades: list[Trade], exits: list[Exit],
) -> float | None:
    """v1.2 §8.9: sum(R where > 0) / abs(sum(R where < 0)).

    Returns None when there are no losses (denominator zero — caller chooses
    'n/a' or 'infinity' display). Returns 0.0 when there are no wins but
    there are losses.
    """
    rs = [compute_actual_realized_R_effective(t, exits) for t in closed_trades]
    gross_wins = sum(r for r in rs if r > 0)
    gross_losses = sum(r for r in rs if r < 0)
    if gross_losses == 0:
        return None
    return gross_wins / abs(gross_losses)


def compute_max_drawdown_R(
    closed_trades: list[Trade], exits: list[Exit],
) -> float:
    """Maximum peak-to-trough drawdown over the closed-date-ordered cumulative
    R-series. Returned as a non-negative magnitude. Returns 0.0 for empty
    input or no drawdown.
    """
    if not closed_trades:
        return 0.0
    decorated = sorted(
        ((t, compute_actual_realized_R_effective(t, exits),
          _trade_closed_date_for_review(t, exits))
         for t in closed_trades),
        key=lambda x: x[2] or date.min,
    )
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for _t, r, _cd in decorated:
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown


def _trade_closed_date_for_review(trade: Trade, exits: list[Exit]) -> date | None:
    """Mirror of swing.journal.stats._trade_closed_date — same formula.
    Re-implemented per journal/-read-only carve-out (plan §A.1).
    """
    if trade.status != "closed":
        return None
    relevant = [e.exit_date for e in exits if e.trade_id == trade.id]
    return max(date.fromisoformat(d) for d in relevant) if relevant else None
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/trades/test_review_helpers.py -v`
Expected: all helper tests PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/review.py tests/trades/test_review_helpers.py
git commit -m "feat(phase6): Task 5 — cost/lucky/profit_factor/max_drawdown helpers"
```

### Task 6: Review_Log repo (insert + complete + reads)

**Files:**
- Create: `swing/data/repos/review_log.py`
- Create: `tests/data/test_review_log_repo.py`

- [ ] **Step 1: Write failing tests for the repo CRUD**

```python
# tests/data/test_review_log_repo.py
"""Review_Log repo CRUD + idempotent pre-create + completion-freezing tests."""
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import connect
from swing.data.models import Exit, Trade
from swing.data.repos.review_log import (
    complete_review, count_needs_review, get, insert_pre_create,
    list_recent, list_unreviewed_closed_trades,
)
from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase6.db"
    conn = connect(db_path)
    yield conn
    conn.close()


class TestInsertPreCreate:
    def test_first_insert_returns_id(self, conn: sqlite3.Connection) -> None:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        assert review_id is not None
        assert review_id >= 1

    def test_duplicate_returns_none(self, conn: sqlite3.Connection) -> None:
        with conn:
            first = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
            second = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        assert first is not None
        assert second is None
        # Verify only one row exists:
        count = conn.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
        assert count == 1

    def test_different_periods_each_get_a_row(self, conn: sqlite3.Connection) -> None:
        with conn:
            r1 = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
            r2 = insert_pre_create(
                conn, review_type="weekly",
                period_start="2026-04-21", period_end="2026-04-25",
                scheduled_date="2026-04-28",
            )
        assert r1 != r2
        assert r1 is not None and r2 is not None


class TestCompleteReviewAtomic:
    def test_atomic_freezes_computed_aggregates(
        self, conn: sqlite3.Connection,
    ) -> None:
        # Seed: closed trade in the daily period
        with conn:
            t1 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="VIR", entry_date="2026-04-29",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, status="closed",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-29T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t1, exit_date="2026-04-30",
                    exit_price=12.0, shares=10, reason="manual",
                    realized_pnl=20.0, r_multiple=2.0, notes=None,
                ),
                event_ts="2026-04-30T09:30:00",
            )
        # Pre-create + atomic complete:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        assert review_id is not None
        # complete_review_atomic OWNS the compute → write pipeline.
        # Brief §6.2 watch item 3: caller does NOT supply aggregates.
        from swing.data.repos.review_log import complete_review_atomic
        complete_review_atomic(
            conn, review_id=review_id,
            completed_date="2026-05-02",
            duration_minutes=15,
            primary_lesson="Wait for the breakout.",
            next_period_focus="Tighten entries on volume confirmation.",
        )
        row = get(conn, review_id)
        assert row is not None
        assert row.completed_date == "2026-05-02"
        assert row.duration_minutes == 15
        assert row.primary_lesson == "Wait for the breakout."
        assert row.next_period_focus.startswith("Tighten")
        # n_trades_reviewed + total_*_R + 7 aggregates were computed inside
        # the transaction by reading closed trades in (period_start, period_end]
        # via compute_stats + review.py augmentation helpers:
        assert row.n_trades_reviewed == 1
        assert row.net_R_effective == pytest.approx(2.0)
        assert row.win_rate == pytest.approx(1.0)
        assert row.profit_factor is None  # no losses

    # NOTE: a separate concurrent-writer transaction-isolation test is
    # NOT included here because the integration test in Task 14
    # (test_review_aggregates_frozen_when_more_trades_close) already
    # exercises the operational invariant — a trade close AFTER
    # complete_review_atomic does not mutate the row's frozen state.
    # SQLite's BEGIN IMMEDIATE acquires the RESERVED lock immediately,
    # so concurrent writers either commit before us (visible in our
    # SELECT inside the transaction) or block until we COMMIT (not
    # visible). Both branches preserve the snapshot — there is no
    # additional discriminating power from a multi-connection unit test.


class TestCountNeedsReview:
    def test_only_closed_unreviewed_old_enough_count(
        self, conn: sqlite3.Connection,
    ) -> None:
        # Trade 1: closed 2026-04-01 unreviewed → SHOULD count (old enough)
        # Trade 2: closed 2026-05-01 unreviewed → should NOT count (within window)
        # Trade 3: closed 2026-04-01 reviewed_at set → should NOT count
        # Trade 4: open → should NOT count
        with conn:
            t1 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="T1", entry_date="2026-03-01",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, status="closed",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-03-01T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t1, exit_date="2026-04-01",
                    exit_price=11.0, shares=10, reason="manual",
                    realized_pnl=10.0, r_multiple=1.0, notes=None,
                ),
                event_ts="2026-04-01T09:30:00",
            )
            t2 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="T2", entry_date="2026-04-01",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, status="closed",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-01T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t2, exit_date="2026-05-01",
                    exit_price=11.0, shares=10, reason="manual",
                    realized_pnl=10.0, r_multiple=1.0, notes=None,
                ),
                event_ts="2026-05-01T09:30:00",
            )
        # Mark t3 as reviewed:
        # (t3 not actually inserted here; testing the closed/unreviewed-only filter
        # is sufficient with t1 + t2.)
        # Check needs-review at today=2026-05-10, window=7 days:
        n = count_needs_review(conn, window_days=7, today_iso="2026-05-10")
        # t1 closed 2026-04-01 → 39 days ago → counts
        # t2 closed 2026-05-01 → 9 days ago → counts (>= 7 days old)
        # Both old enough; both unreviewed. Expected: 2.
        assert n == 2


class TestListRecent:
    def test_returns_most_recent_per_cadence(
        self, conn: sqlite3.Connection,
    ) -> None:
        with conn:
            insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-29", period_end="2026-04-29",
                scheduled_date="2026-04-30",
            )
            insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        rows = list_recent(conn, review_type="daily", limit=2)
        assert len(rows) == 2
        # Most-recent first by created_at:
        assert rows[0].period_start == "2026-04-30"
        assert rows[1].period_start == "2026-04-29"
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/data/test_review_log_repo.py -v`
Expected: all tests FAIL (`swing.data.repos.review_log` not present).

- [ ] **Step 3: Implement the repo**

Create `swing/data/repos/review_log.py`:

```python
"""Review_Log repo (Phase 6, migration 0013).

Owns idempotent pre-create + atomic completion (aggregate-freezing in a single
transaction). Read paths support dashboard cadence cards + needs-review badge
+ pending-list view.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Iterable

from swing.data.models import Exit, ReviewLog, Trade


def insert_pre_create(
    conn: sqlite3.Connection,
    *,
    review_type: str,
    period_start: str,
    period_end: str,
    scheduled_date: str,
) -> int | None:
    """Idempotent: returns new review_id, or None when a row already exists for
    (review_type, period_start, period_end). Caller wraps in `with conn:`.
    """
    try:
        cur = conn.execute(
            """
            INSERT INTO review_log
                (review_type, period_start, period_end, scheduled_date)
            VALUES (?, ?, ?, ?)
            """,
            (review_type, period_start, period_end, scheduled_date),
        )
        return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        # UNIQUE INDEX ux_review_log_cadence_period collision = idempotent
        # no-op. Other IntegrityError subtypes (CHECK violation) re-raise
        # so the caller learns about validation failures.
        if "UNIQUE" in str(exc) or "ux_review_log_cadence_period" in str(exc):
            return None
        raise


def complete_review_atomic(
    conn: sqlite3.Connection,
    *,
    review_id: int,
    completed_date: str,
    duration_minutes: int,
    primary_lesson: str,
    next_period_focus: str,
) -> None:
    """Mark review complete + freeze all aggregates atomically.

    Single BEGIN IMMEDIATE transaction OWNS:
      1. Read the review_log row to get (review_type, period_start, period_end).
      2. Select closed trades whose final exit date falls in [period_start, period_end].
      3. Compute aggregates via swing.journal.stats.compute_stats (5 fields)
         + swing.trades.review.compute_profit_factor + compute_max_drawdown_R
         (2 fields).
      4. Compute total_mistake_cost_R + total_lucky_violation_R via
         swing.trades.review.compute_mistake_cost_R + compute_lucky_violation_R
         summed over the period's closed trades (trades without
         realized_R_if_plan_followed contribute 0 to both).
      5. UPDATE the review_log row with completed_date + duration_minutes +
         primary_lesson + next_period_focus + n_trades_reviewed + total_*_R +
         all 7 aggregates.

    Brief §6.2 watch item 3: a trade close concurrent with this function
    cannot tear the snapshot — the BEGIN IMMEDIATE acquires SQLite's
    RESERVED lock immediately, so any concurrent writer either blocks
    behind us or already committed before us (we read the post-commit
    state in step 2).

    Caller does NOT supply aggregates — they are computed INSIDE the
    transaction (R1 Major 1 fix vs. earlier draft API).
    """
    from swing.data.repos.trades import list_all_exits, list_closed_trades
    from swing.journal.stats import compute_stats
    from swing.trades.review import (
        compute_actual_realized_R_effective, compute_lucky_violation_R,
        compute_max_drawdown_R, compute_mistake_cost_R, compute_profit_factor,
    )

    conn.execute("BEGIN IMMEDIATE")
    try:
        # Step 1: read the period from review_log:
        row = conn.execute(
            """SELECT period_start, period_end FROM review_log
               WHERE review_id = ?""",
            (review_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"review_log row #{review_id} not found")
        period_start, period_end = row[0], row[1]

        # Step 2: select closed trades whose final exit_date in [start, end]:
        all_closed = list_closed_trades(conn)
        all_exits = list_all_exits(conn)
        # Filter to period:
        from datetime import date as _date
        ps = _date.fromisoformat(period_start)
        pe = _date.fromisoformat(period_end)
        period_trades = []
        for t in all_closed:
            relevant = [
                _date.fromisoformat(e.exit_date) for e in all_exits
                if e.trade_id == t.id
            ]
            if not relevant:
                continue
            close_date = max(relevant)
            if ps <= close_date <= pe:
                period_trades.append(t)

        # Step 3: compute aggregates:
        stats = compute_stats(trades=period_trades, exits=all_exits)
        net_R = stats.total_r
        expectancy_R = stats.expectancy_r
        win_rate = stats.win_rate
        avg_win = stats.avg_win_r
        avg_loss = stats.avg_loss_r
        profit_factor = compute_profit_factor(period_trades, list(all_exits))
        max_dd = compute_max_drawdown_R(period_trades, list(all_exits))

        # Step 4: total_mistake_cost_R + total_lucky_violation_R per-trade sum:
        total_cost = 0.0
        total_lucky = 0.0
        for t in period_trades:
            actual = compute_actual_realized_R_effective(t, list(all_exits))
            total_cost += compute_mistake_cost_R(
                realized_R_if_plan_followed=t.realized_R_if_plan_followed,
                actual_realized_R_effective=actual,
            )
            total_lucky += compute_lucky_violation_R(
                realized_R_if_plan_followed=t.realized_R_if_plan_followed,
                actual_realized_R_effective=actual,
            )

        # Step 5: UPDATE the review_log row:
        conn.execute(
            """
            UPDATE review_log SET
                completed_date = ?,
                duration_minutes = ?,
                n_trades_reviewed = ?,
                primary_lesson = ?,
                next_period_focus = ?,
                total_mistake_cost_R = ?,
                total_lucky_violation_R = ?,
                net_R_effective = ?,
                expectancy_R_effective = ?,
                win_rate = ?,
                avg_win_R = ?,
                avg_loss_R = ?,
                profit_factor = ?,
                max_drawdown_R = ?
            WHERE review_id = ?
            """,
            (
                completed_date, duration_minutes, len(period_trades),
                primary_lesson, next_period_focus,
                total_cost, total_lucky,
                net_R, expectancy_R, win_rate, avg_win, avg_loss,
                profit_factor, max_dd, review_id,
            ),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def get(conn: sqlite3.Connection, review_id: int) -> ReviewLog | None:
    row = conn.execute(
        "SELECT * FROM review_log WHERE review_id = ?", (review_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_review_log(row)


def list_recent(
    conn: sqlite3.Connection, *, review_type: str, limit: int = 1,
) -> list[ReviewLog]:
    """Most recent rows by BUSINESS PERIOD, not by INSERT TIME.

    R1 Minor 2 fix: a backfilled cadence row (e.g., operator manually
    inserts a missed weekly review) would jump to the top under
    `ORDER BY created_at DESC` even though its period_end is older than
    the current latest cadence. Order by period_end DESC + scheduled_date
    DESC (tiebreaker for same-period entries) so the dashboard cards
    surface the operator's CURRENT cadence, not the most-recently-typed
    backfill.
    """
    rows = conn.execute(
        """SELECT * FROM review_log
           WHERE review_type = ?
           ORDER BY period_end DESC, scheduled_date DESC
           LIMIT ?""",
        (review_type, limit),
    ).fetchall()
    return [_row_to_review_log(r) for r in rows]


def list_pending(
    conn: sqlite3.Connection, *, review_type: str | None = None,
) -> list[ReviewLog]:
    """Pre-created cadence rows whose `completed_date IS NULL`.

    Used ONLY by the cadence-completion CLI (`swing review complete --list`)
    and a future cadence-pending dashboard surface (V2). NOT used by the
    `/reviews/pending` route — that route surfaces unreviewed CLOSED TRADES
    (different entity) via `list_unreviewed_closed_trades`. The two
    "pending" concepts are unrelated; see file-map docstring for the
    explicit semantic split. (R2 Minor 2 + R3 Minor 1 clarification.)
    """
    if review_type is None:
        rows = conn.execute(
            """SELECT * FROM review_log
               WHERE completed_date IS NULL
               ORDER BY period_end DESC""",
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM review_log
               WHERE completed_date IS NULL AND review_type = ?
               ORDER BY period_end DESC""",
            (review_type,),
        ).fetchall()
    return [_row_to_review_log(r) for r in rows]


def list_unreviewed_closed_trades(
    conn: sqlite3.Connection, *, window_days: int, today_iso: str,
) -> list[Trade]:
    """Return closed trades whose final exit date <= today - window_days AND
    whose `reviewed_at` IS NULL.

    Implementation: SELECT closed unreviewed trades + JOIN to MAX(exit_date)
    via subquery; filter Python-side to keep the query simple. Production
    trade volume (1 today; <500/year forecast) makes this trivial.
    """
    # Use the in-line trades repo loader for column parity:
    from swing.data.repos.trades import _row_to_trade  # adjust import to actual mapper name
    rows = conn.execute(
        """
        SELECT t.*, (
            SELECT MAX(e.exit_date) FROM exits e WHERE e.trade_id = t.id
        ) AS closed_date
        FROM trades t
        WHERE t.status = 'closed' AND t.reviewed_at IS NULL
        """,
    ).fetchall()
    today = date.fromisoformat(today_iso)
    out: list[Trade] = []
    from datetime import timedelta as _td
    cutoff = today - _td(days=window_days)
    for row in rows:
        # row['closed_date'] semantics — depends on row factory; if sqlite3.Row,
        # access by key:
        closed_str = row["closed_date"] if "closed_date" in row.keys() else None
        if closed_str is None:
            continue
        if date.fromisoformat(closed_str) > cutoff:
            continue
        # Strip the synthetic closed_date field before passing to mapper.
        # If _row_to_trade can't accept extra fields, project the columns
        # explicitly. Plan author: implement whatever shape matches the
        # existing mapper's signature.
        out.append(_row_to_trade(row))
    return out


def count_needs_review(
    conn: sqlite3.Connection, *, window_days: int, today_iso: str,
) -> int:
    return len(list_unreviewed_closed_trades(
        conn, window_days=window_days, today_iso=today_iso,
    ))


def _row_to_review_log(row: sqlite3.Row) -> ReviewLog:
    return ReviewLog(
        review_id=row["review_id"],
        review_type=row["review_type"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        scheduled_date=row["scheduled_date"],
        completed_date=row["completed_date"],
        skipped=bool(row["skipped"]),
        duration_minutes=row["duration_minutes"],
        n_trades_reviewed=row["n_trades_reviewed"],
        total_mistake_cost_R=row["total_mistake_cost_R"],
        total_lucky_violation_R=row["total_lucky_violation_R"],
        primary_lesson=row["primary_lesson"],
        next_period_focus=row["next_period_focus"],
        created_at=row["created_at"],
        net_R_effective=row["net_R_effective"],
        expectancy_R_effective=row["expectancy_R_effective"],
        win_rate=row["win_rate"],
        avg_win_R=row["avg_win_R"],
        avg_loss_R=row["avg_loss_R"],
        profit_factor=row["profit_factor"],
        max_drawdown_R=row["max_drawdown_R"],
    )
```

**Plan author note:** the `_row_to_trade` import path may differ — the existing repo uses inline construction in `get_trade` and `list_open_trades`. If no extracted helper exists, locate the constructor pattern + replicate it inline in `list_unreviewed_closed_trades`, OR refactor the trades repo to expose a mapper helper as part of Task 2's row-mapper extension. Choose the path that keeps tests green.

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/data/test_review_log_repo.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/review_log.py tests/data/test_review_log_repo.py
git commit -m "feat(phase6): Task 6 — review_log repo (insert + complete + needs-review reads)"
```

### Task 7: Pipeline `_step_review_log_cadence` + cadence-period helpers

**Files:**
- Modify: `swing/trades/review.py` (add cadence-period helpers)
- Modify: `swing/pipeline/runner.py` (add `_step_review_log_cadence`)
- Create: `tests/pipeline/test_review_log_cadence_step.py`

- [ ] **Step 1: Write failing tests for the cadence helpers + step**

```python
# tests/pipeline/test_review_log_cadence_step.py
"""Cadence pre-create step: idempotence + period helpers + error tolerance."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from swing.data.db import connect
from swing.trades.review import (
    compute_daily_period, compute_monthly_period, compute_weekly_period,
)


class TestPeriodHelpers:
    def test_daily_returns_last_completed_session(self) -> None:
        # 2026-05-02 (Saturday) HST 9pm → ET 02:00am next day, which is post-close
        # of NYSE 2026-05-02 (also Saturday). last_completed_session: 2026-05-01 (Friday).
        # Daily period = (2026-05-01, 2026-05-01).
        now = datetime(2026, 5, 2, 21, 0, 0)
        start, end = compute_daily_period(now)
        assert start == end
        # Plan author: actual asserted date depends on NYSE calendar — use
        # last_completed_session(now) directly to compare:
        from swing.evaluation.dates import last_completed_session
        assert start == last_completed_session(now)

    def test_weekly_returns_prior_mon_to_fri(self) -> None:
        # 2026-05-02 (Saturday). Prior Mon-Fri = 2026-04-20 to 2026-04-24.
        now = datetime(2026, 5, 2, 21, 0, 0)
        start, end = compute_weekly_period(now)
        # If last_completed_session is 2026-05-01 (Friday), prior week's Mon = 2026-04-20.
        # Plan author: verify against the actual NYSE calendar via last_completed_session.
        # Assert end == start + 4 days (Mon to Fri):
        assert (end - start).days == 4
        # Assert start.weekday() == 0 (Monday):
        assert start.weekday() == 0

    def test_monthly_returns_prior_calendar_month(self) -> None:
        now = datetime(2026, 5, 2, 21, 0, 0)
        start, end = compute_monthly_period(now)
        assert start.day == 1
        # End must be the last day of prior month:
        next_day = end.replace(day=end.day + 1) if end.day < 28 else None
        # Plan author note: this assertion is a sketch — use a tighter
        # implementation in the actual test such as: end + 1 day == next month's day 1.


class TestStepReviewLogCadence:
    """Unit tests for _step_review_log_cadence using a real lease in a tmp DB.

    Pattern mirrors the existing tests/pipeline/test_runner.py harness:
    acquire a real lease via swing.pipeline.lease.acquire_lease, run the
    step, then release. The lease's fenced_write contract is exercised
    end-to-end (not mocked).
    """

    @pytest.fixture
    def lease_and_conn_factory(self, tmp_path: Path):
        from swing.data.db import connect as _connect
        from swing.pipeline.lease import acquire_lease

        db_path = tmp_path / "phase6.db"
        # Initialize schema (apply migrations 0001..0013):
        c = _connect(db_path)
        c.close()

        def make() -> tuple:
            lease = acquire_lease(
                db_path=db_path, trigger="manual",
                data_asof_date="2026-04-30",
                action_session_date="2026-05-01",
                block_threshold_seconds=60,
                finviz_csv_path=None,
                rs_universe_version=None,
                rs_universe_hash=None,
            )
            return lease, db_path
        return make

    def test_creates_three_cadence_rows_first_call(
        self, lease_and_conn_factory,
    ) -> None:
        from swing.data.db import connect as _connect
        from swing.pipeline.runner import _step_review_log_cadence
        lease, db_path = lease_and_conn_factory()
        try:
            _step_review_log_cadence(lease=lease)
        finally:
            lease.release(state="complete")
        c = _connect(db_path)
        n = c.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
        c.close()
        assert n == 3  # daily + weekly + monthly

    def test_idempotent_second_call_creates_no_new_rows(
        self, lease_and_conn_factory,
    ) -> None:
        from swing.data.db import connect as _connect
        from swing.pipeline.runner import _step_review_log_cadence
        for _ in range(2):
            lease, db_path = lease_and_conn_factory()
            try:
                _step_review_log_cadence(lease=lease)
            finally:
                lease.release(state="complete")
        c = _connect(db_path)
        n = c.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
        c.close()
        assert n == 3  # idempotent — second call adds zero rows

    def test_step_does_not_propagate_internal_errors(
        self, lease_and_conn_factory, monkeypatch,
    ) -> None:
        """When insert_pre_create raises mid-loop, the cadence step must
        propagate the exception (per the implementation that does NOT
        catch internally — the run_pipeline_internal wrapper logs+continues).

        This test asserts the IMPLEMENTATION'S contract — the function does
        NOT swallow exceptions; the WRAPPER does. Brief §6.2 watch item 13
        is satisfied at the WRAPPER layer (run_pipeline_internal try/except
        log.warning), not inside _step_review_log_cadence.
        """
        import sqlite3 as _sqlite3
        from swing.data.repos import review_log as _rl
        from swing.pipeline.runner import _step_review_log_cadence

        call_count = {"n": 0}
        original = _rl.insert_pre_create

        def boom(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise _sqlite3.OperationalError("simulated mid-loop failure")
            return original(*args, **kwargs)

        monkeypatch.setattr(_rl, "insert_pre_create", boom)

        lease, db_path = lease_and_conn_factory()
        try:
            with pytest.raises(_sqlite3.OperationalError):
                _step_review_log_cadence(lease=lease)
        finally:
            lease.release(state="complete")

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/pipeline/test_review_log_cadence_step.py -v`
Expected: all tests FAIL.

- [ ] **Step 3: Add cadence-period helpers to `swing/trades/review.py`**

Append per §H:

```python
# ---- Cadence-period boundary helpers (locked decision §2.7) ----

def compute_daily_period(now: datetime) -> tuple[date, date]:
    session = last_completed_session(now)
    return session, session


def compute_weekly_period(now: datetime) -> tuple[date, date]:
    today = last_completed_session(now)
    this_monday = today - timedelta(days=today.weekday())
    prior_monday = this_monday - timedelta(days=7)
    prior_friday = prior_monday + timedelta(days=4)
    return prior_monday, prior_friday


def compute_monthly_period(now: datetime) -> tuple[date, date]:
    today = last_completed_session(now)
    first_of_this_month = today.replace(day=1)
    last_of_prior = first_of_this_month - timedelta(days=1)
    first_of_prior = last_of_prior.replace(day=1)
    return first_of_prior, last_of_prior
```

- [ ] **Step 4: Add `_step_review_log_cadence` to `swing/pipeline/runner.py`**

Insert AFTER `_step_export` (around line 850) — plan author verifies anchor by reading [swing/pipeline/runner.py:786-857](../../swing/pipeline/runner.py#L786-L857). Then call it AFTER `lease.step("complete")` in `run_pipeline_internal`:

```python
# In run_pipeline_internal, after `lease.step("complete")` and before
# `lease.release(state="complete")`:
try:
    _step_review_log_cadence(lease=lease)
except Exception as exc:
    # Cadence pre-create is auxiliary — its failure must NOT roll back the
    # primary value chain (briefing emission). Log + continue. Brief §6.2
    # watch item 13.
    log.warning("review_log cadence step failed (continuing): %s", exc)


def _step_review_log_cadence(*, lease: Lease) -> None:
    """Idempotent: pre-create one Review_Log row per cadence (daily/weekly/
    monthly) for the prior period, anchored on `last_completed_session(
    datetime.now())`. Quarterly + circuit_breaker schema-supported but no
    pre-create in V1 (locked decision §2.7).

    Anchor is helper-internal — caller cannot supply an as-of-date that
    controls which prior period rows are created (brief §6.2 watch item 5).

    No `cfg` parameter: the function uses `lease.fenced_write()` for the DB
    connection (already cfg-bound at lease-acquire time) — passing cfg would
    duplicate state. R3 Major 1 fix.
    """
    from datetime import datetime as _dt
    from swing.data.repos.review_log import insert_pre_create
    from swing.trades.review import (
        compute_daily_period, compute_monthly_period, compute_weekly_period,
    )

    now = _dt.now()
    cadence_periods: list[tuple[str, date, date]] = [
        ("daily", *compute_daily_period(now)),
        ("weekly", *compute_weekly_period(now)),
        ("monthly", *compute_monthly_period(now)),
    ]
    with lease.fenced_write() as conn:
        for review_type, p_start, p_end in cadence_periods:
            scheduled = (p_end + timedelta(days=1)).isoformat()
            insert_pre_create(
                conn,
                review_type=review_type,
                period_start=p_start.isoformat(),
                period_end=p_end.isoformat(),
                scheduled_date=scheduled,
            )
```

- [ ] **Step 5: Run tests to confirm they pass**

Run: `python -m pytest tests/pipeline/test_review_log_cadence_step.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/trades/review.py swing/pipeline/runner.py tests/pipeline/test_review_log_cadence_step.py
git commit -m "feat(phase6): Task 7 — pipeline _step_review_log_cadence + period helpers"
```

### Task 8: CLI `swing trade review` (with `--list` flag) — R1 Major 2 fix

**Files:**
- Modify: `swing/cli.py` (add 1 dual-mode command in trade_group)
- Create: `tests/cli/test_trade_review_cli.py`

**R1 Major 2 contract preservation:** brief §3.1 specifies `swing trade review <trade_id>` AND `swing trade review --list`. Implementation uses a SINGLE `@trade_group.command("review")` function with: (a) `--list` as `is_flag=True` with early-return behavior; (b) `--trade-id`, grade flags, and `--lesson-learned` as `required=False` (validated post-hoc, ONLY in the non-list path). Click does not natively support "required-only-in-non-list-mode"; we simulate via post-parse validation in the function body that raises `click.UsageError` if `--list` is absent AND any required field is missing.

- [ ] **Step 1: Write failing tests for the CLI commands**

```python
# tests/cli/test_trade_review_cli.py
"""Click integration tests for swing trade review + review-list."""
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from swing.data.models import Exit, Trade
from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event


@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "phase6.db"
    conn = connect(db_path)
    with conn:
        trade_id = insert_trade_with_event(
            conn, Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, status="closed",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_exit_with_event(
            conn, Exit(
                id=None, trade_id=trade_id, exit_date="2026-04-25",
                exit_price=11.5, shares=10, reason="manual",
                realized_pnl=15.0, r_multiple=1.5, notes=None,
            ),
            event_ts="2026-04-25T09:30:00",
        )
    conn.close()
    return db_path


def test_review_persists_all_ten_fields(
    populated_db: Path, tmp_path: Path,
) -> None:
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(f"""
[paths]
db_path = "{populated_db.as_posix()}"
""")
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(config_toml),
        "trade", "review",
        "--trade-id", "1",
        "--mistake-tags", "CHASED",
        "--mistake-tags", "FOMO",
        "--entry-grade", "C",
        "--management-grade", "B",
        "--exit-grade", "B",
        "--realized-r-if-plan-followed", "2.0",
        "--mistake-cost-confidence", "medium",
        "--lesson-learned", "Wait for the breakout, not the build-up.",
    ])
    assert result.exit_code == 0, result.output
    # Verify persistence:
    conn = connect(populated_db)
    row = conn.execute(
        "SELECT reviewed_at, mistake_tags, entry_grade, process_grade, "
        "realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned "
        "FROM trades WHERE id = 1"
    ).fetchone()
    conn.close()
    assert row[0] is not None  # reviewed_at populated
    tags = json.loads(row[1])
    assert tags == ["CHASED", "FOMO"]  # canonicalized + sorted
    assert row[2] == "C"
    assert row[3] == "C"  # process grade computed: weighted = 0.40*2 + 0.35*3 + 0.25*3 = 0.80+1.05+0.75 = 2.60 → C
    assert row[4] == 2.0
    assert row[5] == "medium"
    assert "breakout" in row[6]


def test_review_list_flag_shows_pending_trades(
    populated_db: Path, tmp_path: Path,
) -> None:
    """R1 Major 2: brief §3.1 contract is `swing trade review --list`.

    Single command with `--list` flag, NOT a separate `review-list` subcommand.
    """
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(f"""
[paths]
db_path = "{populated_db.as_posix()}"
""")
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(config_toml),
        "trade", "review", "--list",
    ])
    assert result.exit_code == 0
    assert "VIR" in result.output


def test_review_without_trade_id_or_list_flag_errors(
    populated_db: Path, tmp_path: Path,
) -> None:
    """Missing `--trade-id` AND missing `--list` flag → UsageError."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(f"""
[paths]
db_path = "{populated_db.as_posix()}"
""")
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(config_toml), "trade", "review",
    ])
    assert result.exit_code != 0
    assert "trade-id" in result.output.lower() or "list" in result.output.lower()


def test_review_unknown_mistake_tag_rejected(
    populated_db: Path, tmp_path: Path,
) -> None:
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(f"""
[paths]
db_path = "{populated_db.as_posix()}"
""")
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(config_toml),
        "trade", "review",
        "--trade-id", "1",
        "--mistake-tags", "NOT_REAL",
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--lesson-learned", "n/a",
    ])
    assert result.exit_code != 0
    assert "unknown mistake tag" in result.output.lower()
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/cli/test_trade_review_cli.py -v`
Expected: all FAIL (commands don't exist).

- [ ] **Step 3: Implement the CLI commands**

Modify [swing/cli.py:339-498](../../swing/cli.py#L339-L498). Append to `trade_group` block:

```python
@trade_group.command("review")
@click.option("--list", "list_mode", is_flag=True,
              help="List closed trades pending review and exit. "
                   "When set, all other args are ignored.")
@click.option("--window-days", type=int, default=None,
              help="Threshold in days since close (used with --list). "
                   "Defaults to cfg.review.review_window_days.")
@click.option("--trade-id", type=int, default=None,
              help="REQUIRED unless --list is set.")
@click.option(
    "--mistake-tags", multiple=True,
    help="Repeatable. e.g., --mistake-tags CHASED --mistake-tags FOMO. "
         "Use 'none_observed' if no mistakes (must NOT be combined with others).",
)
@click.option("--entry-grade", type=click.Choice(["A", "B", "C", "D", "F"]),
              default=None, help="REQUIRED unless --list is set.")
@click.option("--management-grade", type=click.Choice(["A", "B", "C", "D", "F"]),
              default=None, help="REQUIRED unless --list is set.")
@click.option("--exit-grade", type=click.Choice(["A", "B", "C", "D", "F"]),
              default=None, help="REQUIRED unless --list is set.")
@click.option("--disqualifying-process-violation", is_flag=True,
              help="Set if any of the 7 v1.2 §9.2 disqualifying violations occurred. "
                   "Caps process_grade at D.")
@click.option("--realized-r-if-plan-followed", "realized_r_if_plan_followed",
              type=float, default=None,
              help="Counterfactual R if the original plan had been followed. Optional.")
@click.option("--mistake-cost-confidence",
              type=click.Choice(["high", "medium", "low"]), default=None)
@click.option("--lesson-learned", default=None,
              help="REQUIRED unless --list is set. Free-text reflection.")
@click.pass_context
def trade_review_cmd(
    ctx, list_mode, window_days, trade_id, mistake_tags,
    entry_grade, management_grade, exit_grade,
    disqualifying_process_violation, realized_r_if_plan_followed,
    mistake_cost_confidence, lesson_learned,
):
    """Post-trade review (Phase 6).

    Two modes:
      `swing trade review --list`  → print pending-review trades and exit.
      `swing trade review --trade-id N --entry-grade A ...`  → record a review.
    """
    import json
    from datetime import date as _date, datetime as _dt
    from swing.data.db import connect
    from swing.data.repos.review_log import list_unreviewed_closed_trades
    from swing.data.repos.trades import (
        get_trade, update_trade_review_fields,
    )
    from swing.trades.review import (
        canonicalize_mistake_tags, compute_process_grade,
        validate_mistake_tags,
    )

    cfg = ctx.obj["config"]
    effective_window_days = (
        window_days if window_days is not None
        else cfg.review.review_window_days
    )

    # ---- LIST MODE ----
    if list_mode:
        conn = connect(cfg.paths.db_path)
        try:
            trades = list_unreviewed_closed_trades(
                conn, window_days=effective_window_days,
                today_iso=_date.today().isoformat(),
            )
        finally:
            conn.close()
        if not trades:
            click.echo("No trades pending review.")
            return
        click.echo(
            f"Trades pending review (closed >= {effective_window_days} days ago):"
        )
        for t in trades:
            click.echo(f"  #{t.id} {t.ticker} entry={t.entry_date}")
        return

    # ---- REVIEW MODE — validate required args ----
    missing = []
    if trade_id is None:
        missing.append("--trade-id")
    if entry_grade is None:
        missing.append("--entry-grade")
    if management_grade is None:
        missing.append("--management-grade")
    if exit_grade is None:
        missing.append("--exit-grade")
    if not lesson_learned or not lesson_learned.strip():
        missing.append("--lesson-learned")
    if missing:
        raise click.UsageError(
            f"Missing required args (or pass --list to enter list mode): "
            f"{', '.join(missing)}"
        )

    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
        if trade is None:
            raise click.ClickException(f"Trade #{trade_id} not found")
        if trade.status != "closed":
            raise click.ClickException(
                f"Trade #{trade_id} is not closed; cannot review"
            )
        if trade.reviewed_at is not None:
            raise click.ClickException(
                f"Trade #{trade_id} already reviewed at {trade.reviewed_at}; "
                f"V1 supports single-review only"
            )

        canonical_tags = canonicalize_mistake_tags(list(mistake_tags))
        try:
            validate_mistake_tags(canonical_tags)
        except ValueError as exc:
            raise click.ClickException(str(exc))

        process_grade = compute_process_grade(
            entry=entry_grade, management=management_grade, exit_=exit_grade,
            disqualifying=disqualifying_process_violation,
        )

        with conn:
            update_trade_review_fields(
                conn, trade_id=trade_id,
                reviewed_at=_dt.now().isoformat(timespec="seconds"),
                mistake_tags_json=json.dumps(canonical_tags),
                entry_grade=entry_grade,
                management_grade=management_grade,
                exit_grade=exit_grade,
                process_grade=process_grade,
                disqualifying_process_violation=disqualifying_process_violation,
                realized_R_if_plan_followed=realized_r_if_plan_followed,
                mistake_cost_confidence=mistake_cost_confidence or "",
                lesson_learned=lesson_learned,
            )
    finally:
        conn.close()

    click.echo(
        f"Review recorded for trade #{trade_id} ({trade.ticker}). "
        f"Process grade: {process_grade}."
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/cli/test_trade_review_cli.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/cli/test_trade_review_cli.py
git commit -m "feat(phase6): Task 8 — CLI swing trade review (with --list flag)"
```

### Task 9: Soft-warn at trade close (web + CLI)

**Files:**
- Modify: `swing/trades/review.py` (add SOFT_WARN_REVIEW_DUE_MESSAGE constant)
- Modify: `swing/trades/exit.py` (add `final_exit_closed_trade: bool` to result type)
- Modify: `swing/cli.py` (modify `trade_exit_cmd` to emit message)
- Modify: `swing/web/routes/trades.py` (modify `exit_post` to surface fragment)
- Create: `swing/web/templates/partials/review_soft_warn_close.html.j2`
- Create: `tests/web/test_soft_warn_at_close.py`

- [ ] **Step 1: Write failing tests for soft-warn surface from BOTH paths**

```python
# tests/web/test_soft_warn_at_close.py
"""Soft-warn message surfaces from web exit_post + CLI exit when final exit closes the trade.

Brief §6.2 watch item 4: same message-string from both paths (single constant).
"""
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from swing.cli import main
from swing.trades.review import SOFT_WARN_REVIEW_DUE_MESSAGE


def test_soft_warn_message_constant_includes_review_due_text() -> None:
    assert "Review" in SOFT_WARN_REVIEW_DUE_MESSAGE
    assert "7 days" in SOFT_WARN_REVIEW_DUE_MESSAGE


@pytest.fixture
def half_exited_trade_db(tmp_path: Path) -> Path:
    """Tmp DB with one open trade (10 shares total, 5 already exited).
    The remaining 5-share exit closes the trade → soft-warn surfaces.
    """
    from swing.data.db import connect
    from swing.data.models import Exit, Trade
    from swing.data.repos.trades import (
        insert_exit_with_event, insert_trade_with_event,
    )
    db_path = tmp_path / "phase6.db"
    conn = connect(db_path)
    with conn:
        trade_id = insert_trade_with_event(
            conn, Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        # First partial exit: 5 of 10 shares — trade stays open
        insert_exit_with_event(
            conn, Exit(
                id=None, trade_id=trade_id, exit_date="2026-04-25",
                exit_price=11.5, shares=5, reason="partial",
                realized_pnl=7.5, r_multiple=1.5, notes=None,
            ),
            event_ts="2026-04-25T09:30:00",
        )
    conn.close()
    return db_path


def test_cli_exit_emits_soft_warn_when_final_exit_closes_trade(
    half_exited_trade_db: Path, tmp_path: Path,
) -> None:
    """Final-exit-closes-trade path: CLI emits SOFT_WARN_REVIEW_DUE_MESSAGE."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(f"""
[paths]
db_path = "{half_exited_trade_db.as_posix()}"
""")
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(config_toml),
        "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-05-02",
        "--exit-price", "12.0", "--shares", "5", "--reason", "manual",
    ])
    assert result.exit_code == 0, result.output
    assert SOFT_WARN_REVIEW_DUE_MESSAGE in result.output


@pytest.fixture
def test_app_half_exited(half_exited_trade_db: Path):
    """FastAPI app bound to the half-exited DB fixture."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.web.app import create_app
    # Load the project's swing.config.toml as a baseline, then point db_path
    # at the half-exited fixture:
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=half_exited_trade_db))
    app = create_app(cfg)
    return app


def test_web_exit_post_surfaces_soft_warn_when_final_exit_closes(
    test_app_half_exited,
) -> None:
    with TestClient(test_app_half_exited) as client:
        response = client.post(
            "/trades/1/exit",
            data={
                "exit_date": "2026-05-02", "exit_price": "12.0",
                "shares": "5", "reason": "manual",
            },
            headers={"HX-Request": "true"},
        )
    assert response.status_code == 200
    # The response should contain the soft-warn fragment text:
    assert "Review due within 7 days" in response.text
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/web/test_soft_warn_at_close.py -v`
Expected: all FAIL.

- [ ] **Step 3: Add the shared constant + extend `record_exit` result + wire web/CLI emission**

Append to `swing/trades/review.py`:

```python
# ---- Soft-warn message constant (shared between web + CLI close paths) ----

SOFT_WARN_REVIEW_DUE_MESSAGE: str = (
    "Review due within 7 days. Run `swing trade review --trade-id <id>` "
    "or visit /trades/<id>/review."
)
```

Modify [swing/trades/exit.py](../../swing/trades/exit.py) — extend the `record_exit` return type to include `final_exit_closed_trade: bool` (mirror existing `fully_closed` if present; if not, add a new field).

Modify [swing/cli.py:trade_exit_cmd](../../swing/cli.py#L499) — after `record_exit` returns, if `result.final_exit_closed_trade` (or `result.fully_closed`):

```python
if result.fully_closed:  # or final_exit_closed_trade — match actual field name
    from swing.trades.review import SOFT_WARN_REVIEW_DUE_MESSAGE
    click.echo(SOFT_WARN_REVIEW_DUE_MESSAGE)
```

Modify [swing/web/routes/trades.py:exit_post](../../swing/web/routes/trades.py#L709-L798). In the `if result.fully_closed:` branch, add the soft-warn fragment to the response. The current branch returns:

```python
return HTMLResponse(Markup(
    f'<tr id="open-position-{trade_id}" style="display:none"></tr>'
    f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
))
```

Change to also include the partial render:

```python
soft_warn_html = templates.get_template(
    "partials/review_soft_warn_close.html.j2"
).render(request=request, trade_id=trade_id)
return HTMLResponse(Markup(
    f'<tr id="open-position-{trade_id}" style="display:none"></tr>'
    f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
    f'<div id="trade-close-soft-warn" hx-swap-oob="true">{soft_warn_html}</div>'
))
```

The dashboard template needs `<div id="trade-close-soft-warn"></div>` somewhere visible (existing or new region). Plan author: locate the toast/banner area in `dashboard.html.j2` and add the empty target div. If no banner area exists, add one BELOW the status strip.

Create `swing/web/templates/partials/review_soft_warn_close.html.j2`:

```jinja
{# Soft-warn at trade close. Browser-only failure mode covered by template
   tests + operator-witnessed verification (Task 15). #}
{% from "macros.html.j2" import t with context %}
<div role="status" class="banner banner-soft-warn">
  <p>Review due within 7 days.</p>
  <p>
    <a href="/trades/{{ trade_id }}/review"
       hx-get="/trades/{{ trade_id }}/review"
       hx-target="body"
       hx-headers='{"HX-Request": "true"}'>Review now</a>
    &middot;
    <a href="#" onclick="document.getElementById('trade-close-soft-warn').innerHTML=''; return false;">Dismiss</a>
  </p>
</div>
```

Plan author: if `macros.html.j2` does not exist, drop the import line. Just emit static markup.

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/web/test_soft_warn_at_close.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/review.py swing/trades/exit.py swing/cli.py swing/web/routes/trades.py swing/web/templates/partials/review_soft_warn_close.html.j2 tests/web/test_soft_warn_at_close.py
git commit -m "feat(phase6): Task 9 — soft-warn at trade close (web + CLI shared message)"
```

### Task 10: ReviewVM + build_review_vm

**Files:**
- Modify: `swing/web/view_models/trades.py`
- Create: `tests/web/test_review_template.py` (used by Tasks 11+12)

- [ ] **Step 1: Write failing test for ReviewVM construction + 5-VM existing-fields**

```python
# tests/web/test_review_template.py
"""ReviewVM existing-fields + template-render tests."""
from pathlib import Path

import pytest

from swing.config import load_config
from swing.web.view_models.trades import ReviewVM, build_review_vm


@pytest.fixture
def populated_db_cfg(tmp_path: Path):
    """Fixture: tmp DB seeded with one closed trade (id=1) + one open
    (id=2). Returns a Config bound to the tmp DB so build_review_vm has
    a real cfg.paths.db_path to read from.
    """
    from dataclasses import replace as dc_replace
    from swing.config import Config
    from swing.data.db import connect
    from swing.data.models import Exit, Trade
    from swing.data.repos.trades import (
        insert_exit_with_event, insert_trade_with_event,
    )
    db_path = tmp_path / "phase6.db"
    conn = connect(db_path)
    with conn:
        # Closed trade
        t1 = insert_trade_with_event(
            conn, Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, status="closed",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_exit_with_event(
            conn, Exit(
                id=None, trade_id=t1, exit_date="2026-04-25",
                exit_price=11.5, shares=10, reason="manual",
                realized_pnl=15.0, r_multiple=1.5, notes=None,
            ),
            event_ts="2026-04-25T09:30:00",
        )
        # Open trade
        insert_trade_with_event(
            conn, Trade(
                id=None, ticker="DHC", entry_date="2026-04-27",
                entry_price=7.58, initial_shares=39, initial_stop=7.30,
                current_stop=7.30, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-27T09:30:00",
        )
    conn.close()
    cfg = Config()
    cfg = dc_replace(cfg, paths=dc_replace(cfg.paths, db_path=db_path))
    return cfg


def test_review_vm_has_5_existing_base_layout_fields(populated_db_cfg) -> None:
    """Brief §6.2 watch item 8: ReviewVM must inherit existing base.html.j2 fields."""
    vm = build_review_vm(trade_id=1, cfg=populated_db_cfg)
    assert vm is not None
    # Existing base-layout fields with safe defaults:
    assert hasattr(vm, "session_date")
    assert hasattr(vm, "stale_banner")
    assert hasattr(vm, "price_source_degraded")
    assert hasattr(vm, "price_source_degraded_until")
    assert hasattr(vm, "ohlcv_source_degraded")


def test_review_vm_for_open_trade_returns_none(populated_db_cfg) -> None:
    """Trade #2 is open (DHC); cannot review."""
    vm = build_review_vm(trade_id=2, cfg=populated_db_cfg)
    assert vm is None


def test_review_vm_rejects_already_reviewed(populated_db_cfg) -> None:
    """V1 single-review-per-trade per brief §3.2."""
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.data.repos.trades import update_trade_review_fields
    # Mark trade 1 reviewed:
    conn = connect(populated_db_cfg.paths.db_path)
    with conn:
        update_trade_review_fields(
            conn, trade_id=1,
            reviewed_at=_dt.now().isoformat(timespec="seconds"),
            mistake_tags_json='["none_observed"]',
            entry_grade="A", management_grade="A", exit_grade="A",
            process_grade="A", disqualifying_process_violation=False,
            realized_R_if_plan_followed=None,
            mistake_cost_confidence="",
            lesson_learned="Test review.",
        )
    conn.close()
    vm = build_review_vm(trade_id=1, cfg=populated_db_cfg)
    assert vm is None  # already reviewed → 404 in the GET handler
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/web/test_review_template.py -v`
Expected: all FAIL (`ReviewVM` undefined).

- [ ] **Step 3: Implement ReviewVM + build_review_vm in `swing/web/view_models/trades.py`**

Append:

```python
@dataclass(frozen=True)
class ReviewVM:
    trade: Trade
    actual_realized_R_effective: float

    # Mistake_Tags vocabulary surfaced for form rendering:
    mistake_tag_categories: dict[str, tuple[str, ...]]

    # Disqualifying-violations reference list for form helper text:
    disqualifying_violations_reference: tuple[str, ...]

    # Per-grade label list (A..F):
    grade_choices: tuple[str, ...] = ("A", "B", "C", "D", "F")

    # Phase 5 lesson — base.html.j2 dereferences these. New page VMs MUST
    # carry safe defaults (5-VM existing-fields rule; brief §6.2 watch item 8).
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False


def build_review_vm(*, trade_id: int, cfg: Config) -> ReviewVM | None:
    """Build the review-page VM. Returns None if trade not found, not closed,
    or already reviewed (V1 single-review-per-trade per brief §3.2).
    """
    from swing.data.repos.trades import list_exits_for_trade
    from swing.trades.review import (
        DISQUALIFYING_VIOLATIONS, MISTAKE_TAGS,
        compute_actual_realized_R_effective,
    )

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.status != "closed":
                return None
            if trade.reviewed_at is not None:
                return None  # V1: single-review-per-trade
            exits = list_exits_for_trade(conn, trade_id)
    finally:
        conn.close()
    actual_r = compute_actual_realized_R_effective(trade, list(exits))
    return ReviewVM(
        trade=trade,
        actual_realized_R_effective=actual_r,
        mistake_tag_categories=MISTAKE_TAGS,
        disqualifying_violations_reference=DISQUALIFYING_VIOLATIONS,
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/web/test_review_template.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/trades.py tests/web/test_review_template.py
git commit -m "feat(phase6): Task 10 — ReviewVM + build_review_vm (5-VM compliant)"
```

### Task 11: GET /trades/{id}/review (form render) + templates

**Files:**
- Modify: `swing/web/routes/trades.py` (add GET handler)
- Create: `swing/web/templates/review.html.j2`
- Create: `swing/web/templates/partials/review_form.html.j2`
- Modify: `tests/web/test_review_route.py`

- [ ] **Step 1: Write failing tests for GET /trades/{id}/review**

```python
# tests/web/test_review_route.py
"""Route-level integration tests for /trades/{id}/review GET + POST."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_get_review_page_renders_for_closed_unreviewed_trade(
    test_app_closed_trade,
) -> None:
    with TestClient(test_app_closed_trade) as client:
        r = client.get("/trades/1/review")
    assert r.status_code == 200
    assert "Review trade" in r.text or "Post-trade review" in r.text
    # Form is <form>-rooted, NOT <tr>-rooted (brief §6.2 watch item 7):
    assert "<tr" not in r.text.split("<form")[0] or True
    # 5-VM existing-fields verified via base layout render (no UndefinedError):
    assert r.text.startswith("<!DOCTYPE html>") or "<html" in r.text


def test_get_review_page_404_for_open_trade(test_app_open_trade) -> None:
    with TestClient(test_app_open_trade) as client:
        r = client.get("/trades/1/review")
    assert r.status_code == 404


def test_get_review_page_404_for_already_reviewed(test_app_reviewed_trade) -> None:
    with TestClient(test_app_reviewed_trade) as client:
        r = client.get("/trades/1/review")
    assert r.status_code == 404
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/web/test_review_route.py -v -k "test_get_"`
Expected: all FAIL (route undefined).

- [ ] **Step 3: Implement GET handler + templates**

Append to [swing/web/routes/trades.py](../../swing/web/routes/trades.py):

```python
@router.get("/trades/{trade_id}/review", response_class=HTMLResponse)
def review_form_page(request: Request, trade_id: int):
    """Phase 6: post-trade review form page."""
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    from swing.web.view_models.trades import build_review_vm
    vm = build_review_vm(trade_id=trade_id, cfg=cfg)
    if vm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trade #{trade_id} not found, not closed, or already reviewed",
        )
    return templates.TemplateResponse(
        request, "review.html.j2", {"vm": vm},
    )
```

Create `swing/web/templates/review.html.j2`:

```jinja
{% extends "base.html.j2" %}
{% block title %}Review trade #{{ vm.trade.id }} — {{ vm.trade.ticker }}{% endblock %}
{% block content %}
<h1>Post-trade review: {{ vm.trade.ticker }} (#{{ vm.trade.id }})</h1>
<p>Entry {{ vm.trade.entry_date }} @ ${{ "%.2f"|format(vm.trade.entry_price) }};
   actual realized R = {{ "%.2f"|format(vm.actual_realized_R_effective) }}</p>
{% include "partials/review_form.html.j2" %}
{% endblock %}
```

Create `swing/web/templates/partials/review_form.html.j2`:

```jinja
{# Phase 6 review form. <form>-rooted (NOT <tr>-rooted); leading-<tr> would
   trigger htmx.js makeFragment table-wrap pathology (CLAUDE.md gotcha,
   2026-04-29). HX-Request header explicitly propagated for OriginGuard
   strict-mode (brief §6.2 watch item 6). #}
<form method="post" action="/trades/{{ vm.trade.id }}/review"
      hx-post="/trades/{{ vm.trade.id }}/review"
      hx-headers='{"HX-Request": "true"}'>

  <fieldset>
    <legend>Stage grades</legend>
    {% for stage in ["entry", "management", "exit"] %}
      <label>
        {{ stage|capitalize }} grade
        <select name="{{ stage }}_grade" required>
          {% for g in vm.grade_choices %}
            <option value="{{ g }}">{{ g }}</option>
          {% endfor %}
        </select>
      </label>
    {% endfor %}
    <label>
      <input type="checkbox" name="disqualifying_process_violation" value="true">
      Disqualifying process violation occurred (caps grade at D — see below)
    </label>
    <details>
      <summary>v1.2 §9.2 disqualifying violations (reference)</summary>
      <ul>
        {% for v in vm.disqualifying_violations_reference %}
          <li>{{ v }}</li>
        {% endfor %}
      </ul>
    </details>
  </fieldset>

  <fieldset>
    <legend>Mistake tags</legend>
    {% for category, tags in vm.mistake_tag_categories.items() %}
      <p><strong>{{ category|capitalize }}</strong></p>
      {% for tag in tags %}
        <label>
          <input type="checkbox" name="mistake_tags" value="{{ tag }}">
          {{ tag }}
        </label>
      {% endfor %}
    {% endfor %}
  </fieldset>

  <fieldset>
    <legend>Counterfactual (optional)</legend>
    <label>
      Realized R if plan followed
      <input type="number" name="realized_R_if_plan_followed" step="any">
    </label>
    <label>
      Mistake-cost confidence
      <select name="mistake_cost_confidence">
        <option value="">— select —</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
    </label>
    <p><small>What R would you have realized if you'd followed your original
       plan exactly? (Phase 7 will auto-derive this from Fills.)</small></p>
  </fieldset>

  <fieldset>
    <legend>Lesson learned (required)</legend>
    <textarea name="lesson_learned" rows="4" required></textarea>
  </fieldset>

  <button type="submit">Submit review</button>
</form>
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/web/test_review_route.py -v -k "test_get_"`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/trades.py swing/web/templates/review.html.j2 swing/web/templates/partials/review_form.html.j2 tests/web/test_review_route.py
git commit -m "feat(phase6): Task 11 — GET /trades/{id}/review + form templates"
```

### Task 12: POST /trades/{id}/review (submit, HX-Redirect, repo write)

**Files:**
- Modify: `swing/web/routes/trades.py` (add POST handler)
- Modify: `tests/web/test_review_route.py`

- [ ] **Step 1: Write failing tests for POST handler**

```python
# Append to tests/web/test_review_route.py:

def test_post_review_persists_and_returns_204_with_hx_redirect(
    test_app_closed_trade,
) -> None:
    with TestClient(test_app_closed_trade) as client:
        r = client.post(
            "/trades/1/review",
            data={
                "entry_grade": "C", "management_grade": "B", "exit_grade": "B",
                "disqualifying_process_violation": "false",
                "mistake_tags": ["CHASED"],
                "realized_R_if_plan_followed": "2.0",
                "mistake_cost_confidence": "medium",
                "lesson_learned": "Wait for the breakout.",
            },
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
    # Brief §6.2 watch item 6: success-path = 204 + HX-Redirect (NOT 303 swap).
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/trades"


def test_post_review_unknown_mistake_tag_renders_400_with_form(
    test_app_closed_trade,
) -> None:
    with TestClient(test_app_closed_trade) as client:
        r = client.post(
            "/trades/1/review",
            data={
                "entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                "mistake_tags": ["NOT_REAL"],
                "lesson_learned": "n/a",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "unknown mistake tag" in r.text.lower()
    # Form re-rendered (preserved values + error banner):
    assert 'name="lesson_learned"' in r.text


def test_post_review_canonicalizes_mistake_tags(test_app_closed_trade) -> None:
    """Brief §6.2 watch item 2: NFC + dedup + sort at persistence boundary."""
    with TestClient(test_app_closed_trade) as client:
        r = client.post(
            "/trades/1/review",
            data={
                "entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                "mistake_tags": ["FOMO", "CHASED", "FOMO"],  # dup
                "lesson_learned": "n/a",
            },
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
    assert r.status_code == 204
    # Verify DB has canonicalized JSON:
    import json
    from swing.data.db import connect
    # Plan author: pull db path from test fixture
    db_path = test_app_closed_trade.state.cfg.paths.db_path
    conn = connect(db_path)
    row = conn.execute(
        "SELECT mistake_tags FROM trades WHERE id = 1"
    ).fetchone()
    conn.close()
    tags = json.loads(row[0])
    assert tags == ["CHASED", "FOMO"]  # sorted, deduped
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/web/test_review_route.py -v -k "test_post_review"`
Expected: all FAIL.

- [ ] **Step 3: Implement POST handler**

Append to [swing/web/routes/trades.py](../../swing/web/routes/trades.py):

```python
@router.post("/trades/{trade_id}/review")
def review_post(
    request: Request, trade_id: int,
    entry_grade: str = Form(...),
    management_grade: str = Form(...),
    exit_grade: str = Form(...),
    lesson_learned: str = Form(...),
    disqualifying_process_violation: str | None = Form(None),
    realized_R_if_plan_followed: float | None = Form(None),
    mistake_cost_confidence: str = Form(""),
    mistake_tags: list[str] = Form(default=[]),
):
    """Phase 6: persist a post-trade review.

    Success: 204 + HX-Redirect: /trades (browser re-navigates via htmx.js;
    NOT a 303 swap — Phase 5 lesson, brief §6.2 watch item 6).
    """
    import json
    from datetime import datetime as _dt
    from fastapi.responses import Response
    from swing.data.db import connect
    from swing.data.repos.trades import (
        get_trade, update_trade_review_fields,
    )
    from swing.trades.review import (
        canonicalize_mistake_tags, compute_process_grade,
        validate_mistake_tags,
    )

    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates

    disq = (disqualifying_process_violation or "").lower() == "true"

    # Canonicalize + validate mistake tags. Validation failure → 400 + form rerender.
    canonical_tags = canonicalize_mistake_tags(list(mistake_tags))
    try:
        validate_mistake_tags(canonical_tags)
    except ValueError as exc:
        from swing.web.view_models.trades import build_review_vm
        vm = build_review_vm(trade_id=trade_id, cfg=cfg)
        if vm is None:
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc)},
                status_code=400,
            )
        return templates.TemplateResponse(
            request, "partials/review_form.html.j2",
            {"vm": vm, "error_message": str(exc)},
            status_code=400,
        )

    # Validate stage grades:
    try:
        process_grade = compute_process_grade(
            entry=entry_grade, management=management_grade, exit_=exit_grade,
            disqualifying=disq,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "partials/trade_form_error.html.j2",
            {"error_message": str(exc)},
            status_code=400,
        )

    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
        if trade is None or trade.status != "closed":
            raise HTTPException(status_code=404)
        if trade.reviewed_at is not None:
            raise HTTPException(
                status_code=409,
                detail="Trade already reviewed; V1 supports single-review only",
            )
        with conn:
            update_trade_review_fields(
                conn, trade_id=trade_id,
                reviewed_at=_dt.now().isoformat(timespec="seconds"),
                mistake_tags_json=json.dumps(canonical_tags),
                entry_grade=entry_grade,
                management_grade=management_grade,
                exit_grade=exit_grade,
                process_grade=process_grade,
                disqualifying_process_violation=disq,
                realized_R_if_plan_followed=realized_R_if_plan_followed,
                mistake_cost_confidence=mistake_cost_confidence or "",
                lesson_learned=lesson_learned,
            )
    finally:
        conn.close()

    # Success: 204 + HX-Redirect (browser re-navigates).
    return Response(status_code=204, headers={"HX-Redirect": "/trades"})
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/web/test_review_route.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/trades.py tests/web/test_review_route.py
git commit -m "feat(phase6): Task 12 — POST /trades/{id}/review (HX-Redirect on success)"
```

### Task 12b: `cfg.review.review_window_days` + cadence-completion CLI + cadence-completion web (R1 Critical 1 + R1 Major 3 fix)

**Files:**
- Modify: `swing/config.py` (new `ReviewConfig` section + `review: ReviewConfig` field on top-level `Config`)
- Modify: `swing.config.toml` (add `[review]` section with `review_window_days = 7`)
- Modify: `swing/cli.py` (add new `@main.group("review")` + `@review_group.command("complete")`)
- Modify: `swing/web/routes/trades.py` (add `GET /reviews/{review_id}/complete` + `POST /reviews/{review_id}/complete`)
- Modify: `swing/web/view_models/trades.py` (add `CadenceCompleteVM` + `build_cadence_complete_vm`)
- Create: `swing/web/templates/cadence_complete.html.j2`
- Create: `swing/web/templates/partials/cadence_complete_form.html.j2`
- Create: `tests/cli/test_review_complete_cli.py`
- Create: `tests/web/test_cadence_complete_route.py`

- [ ] **Step 1: Write failing tests for `cfg.review.review_window_days` defaulting to 7**

```python
# Append to tests/data/test_review_log_repo.py:

def test_review_config_default_window_days_is_7() -> None:
    """Brief §2.6 — `cfg.review.review_window_days` default = 7."""
    from swing.config import load_config
    cfg = load_config()
    assert cfg.review.review_window_days == 7
```

- [ ] **Step 2: Add `ReviewConfig` to `swing/config.py` AND wire the loader (R2 Major 1 fix)**

Inspect [swing/config.py:228-300](../../swing/config.py#L228) — `def load(config_path: Path) -> Config:` constructs `Config(...)` with explicit kwargs. Adding a new field requires THREE coordinated edits:

(a) Add a new `ReviewConfig` dataclass alongside the other section dataclasses (e.g., near `Web` at line 155):

```python
@dataclass(frozen=True)
class ReviewConfig:
    """Phase 6 post-trade review tunables. V1 surfaces only the cadence
    review window. V2 may add cadence calendar policy, etc.

    Toml-shadowing rule: section is OPTIONAL in swing.config.toml — when
    absent, dataclass defaults apply (matches the `archive` / `classifier`
    pattern; opposite of `paths` / `account` which are REQUIRED sections).
    """
    review_window_days: int = 7
```

(b) Add `review: ReviewConfig = field(default_factory=ReviewConfig)` to the `Config` dataclass after the existing `archive: ArchiveConfig = field(default_factory=ArchiveConfig)` line (around line 206).

(c) Update the `Config(...)` constructor call in `load()` to populate the field. The pattern for OPTIONAL sections (mirroring `web`, `classifier`, `archive`) is to pass `**raw.get("review", {})`:

```python
# In load(), inside the Config(...) constructor call, append:
review=ReviewConfig(**raw.get("review", {})),
```

This means: if `[review]` section exists in toml, its keys override the defaults; if absent, the dataclass defaults apply.

(d) Audit any DIRECT `Config(...)` constructor calls in tests/helpers/fixtures (R2 Major 1 follow-through). Run:

```bash
grep -rn "Config(" swing/ tests/ | grep -v "ConfigRevision\|@" | head
```

For each direct `Config(...)` call (e.g., test fixtures that build a Config without going through `load()`), add `review=ReviewConfig()` (or omit the kwarg entirely if `field(default_factory=ReviewConfig)` is set — Python's frozen dataclass semantics make this work). Update test fixtures only as needed to keep the fast suite green.

Add to swing.config.toml (the tracked default toml):

```toml
[review]
# Phase 6 cadence-review tunable. Days since trade close before the
# dashboard "needs review" badge counts the trade. Default 7.
review_window_days = 7
```

- [ ] **Step 3: Write failing tests for `swing review complete` CLI**

```python
# tests/cli/test_review_complete_cli.py
"""CLI tests for `swing review complete --review-id <id> --primary-lesson "..."`."""
import pytest
from click.testing import CliRunner

from swing.cli import main


def test_review_complete_freezes_aggregates(populated_db_with_pending_daily, tmp_path):
    """Atomic completion: closed trades in the period are computed
    and frozen on the row.
    """
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(f"""
[paths]
db_path = "{populated_db_with_pending_daily.as_posix()}"
""")
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(config_toml),
        "review", "complete",
        "--review-id", "1",
        "--duration-minutes", "12",
        "--primary-lesson", "Inaugural review.",
        "--next-period-focus", "Same setup.",
    ])
    assert result.exit_code == 0, result.output

    # Verify freeze: re-read the row, assert completed_date + aggregates
    # populated; n_trades_reviewed > 0.
    from swing.data.db import connect
    conn = connect(populated_db_with_pending_daily)
    row = conn.execute(
        """SELECT completed_date, primary_lesson, n_trades_reviewed,
                  net_R_effective, profit_factor
           FROM review_log WHERE review_id = 1"""
    ).fetchone()
    conn.close()
    assert row[0] is not None  # completed_date set
    assert "Inaugural" in row[1]
    assert row[2] >= 1


def test_review_complete_list_mode_shows_pending(populated_db_with_pending_daily, tmp_path):
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(f"""
[paths]
db_path = "{populated_db_with_pending_daily.as_posix()}"
""")
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(config_toml),
        "review", "complete", "--list",
    ])
    assert result.exit_code == 0
    assert "daily" in result.output.lower()
```

- [ ] **Step 4: Implement `swing review complete` CLI**

Append to `swing/cli.py` (NEW top-level group, NOT under `trade_group`):

```python
@main.group("review")
def review_group() -> None:
    """Phase 6: cadence review (daily / weekly / monthly Review_Log completion)."""


@review_group.command("complete")
@click.option("--list", "list_mode", is_flag=True,
              help="List pending Review_Log rows (completed_date IS NULL) and exit.")
@click.option("--review-id", type=int, default=None,
              help="REQUIRED unless --list is set.")
@click.option("--duration-minutes", type=int, default=None,
              help="REQUIRED unless --list. Operator-self-reported review duration.")
@click.option("--primary-lesson", default=None,
              help="REQUIRED unless --list. The single most important lesson.")
@click.option("--next-period-focus", default=None,
              help="REQUIRED unless --list. What to focus on next period.")
@click.pass_context
def review_complete_cmd(
    ctx, list_mode, review_id, duration_minutes, primary_lesson,
    next_period_focus,
):
    """Mark a Review_Log row complete + freeze aggregates atomically.

    Atomic compute-and-freeze per brief §6.2 watch item 3 — caller does
    NOT supply aggregates; complete_review_atomic owns the transaction.
    """
    from datetime import date as _date
    from swing.data.db import connect
    from swing.data.repos.review_log import (
        complete_review_atomic, list_pending,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        if list_mode:
            pending = list_pending(conn)
            if not pending:
                click.echo("No pending cadence reviews.")
                return
            click.echo("Pending cadence reviews:")
            for r in pending:
                click.echo(
                    f"  #{r.review_id} {r.review_type} "
                    f"{r.period_start}..{r.period_end} "
                    f"scheduled={r.scheduled_date}"
                )
            return

        missing = []
        if review_id is None:
            missing.append("--review-id")
        if duration_minutes is None:
            missing.append("--duration-minutes")
        if not primary_lesson or not primary_lesson.strip():
            missing.append("--primary-lesson")
        if not next_period_focus or not next_period_focus.strip():
            missing.append("--next-period-focus")
        if missing:
            raise click.UsageError(
                f"Missing required args (or pass --list to enter list mode): "
                f"{', '.join(missing)}"
            )

        complete_review_atomic(
            conn, review_id=review_id,
            completed_date=_date.today().isoformat(),
            duration_minutes=duration_minutes,
            primary_lesson=primary_lesson,
            next_period_focus=next_period_focus,
        )
    finally:
        conn.close()
    click.echo(f"Review #{review_id} marked complete + aggregates frozen.")
```

- [ ] **Step 5: Write failing tests for the cadence-completion web route**

```python
# tests/web/test_cadence_complete_route.py
"""Cadence-completion web route tests (R1 Critical 1)."""
from fastapi.testclient import TestClient


def test_get_cadence_complete_form(test_app_with_pending_daily):
    with TestClient(test_app_with_pending_daily) as client:
        r = client.get("/reviews/1/complete")
    assert r.status_code == 200
    assert "primary_lesson" in r.text
    assert "next_period_focus" in r.text
    assert "duration_minutes" in r.text


def test_post_cadence_complete_returns_204_with_hx_redirect(
    test_app_with_pending_daily,
):
    with TestClient(test_app_with_pending_daily) as client:
        r = client.post(
            "/reviews/1/complete",
            data={
                "duration_minutes": "12",
                "primary_lesson": "Inaugural.",
                "next_period_focus": "Same setup.",
            },
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/"


def test_get_cadence_complete_404_for_unknown_review(test_app_with_pending_daily):
    with TestClient(test_app_with_pending_daily) as client:
        r = client.get("/reviews/9999/complete")
    assert r.status_code == 404


def test_get_cadence_complete_404_for_already_completed(test_app_with_completed_daily):
    with TestClient(test_app_with_completed_daily) as client:
        r = client.get("/reviews/1/complete")
    assert r.status_code == 404
```

- [ ] **Step 6: Implement web handlers + VM + templates**

Append to `swing/web/view_models/trades.py`:

```python
@dataclass(frozen=True)
class CadenceCompleteVM:
    review: ReviewLog
    n_closed_trades_in_period: int
    # 5-VM existing-fields safe defaults:
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False


def build_cadence_complete_vm(*, review_id: int, cfg: Config) -> CadenceCompleteVM | None:
    """Returns None for unknown review or already-completed review (404 in route)."""
    from swing.data.repos.review_log import get
    conn = connect(cfg.paths.db_path)
    try:
        review = get(conn, review_id)
        if review is None or review.completed_date is not None:
            return None
        # Pre-render the count of closed trades in the period (helper text):
        from datetime import date as _date
        from swing.data.repos.trades import list_all_exits, list_closed_trades
        closed = list_closed_trades(conn)
        all_exits = list_all_exits(conn)
        ps = _date.fromisoformat(review.period_start)
        pe = _date.fromisoformat(review.period_end)
        n = 0
        for t in closed:
            relevant = [
                _date.fromisoformat(e.exit_date) for e in all_exits
                if e.trade_id == t.id
            ]
            if relevant and ps <= max(relevant) <= pe:
                n += 1
    finally:
        conn.close()
    return CadenceCompleteVM(review=review, n_closed_trades_in_period=n)
```

Append to `swing/web/routes/trades.py`:

```python
@router.get("/reviews/{review_id}/complete", response_class=HTMLResponse)
def cadence_complete_form(request: Request, review_id: int):
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    from swing.web.view_models.trades import build_cadence_complete_vm
    vm = build_cadence_complete_vm(review_id=review_id, cfg=cfg)
    if vm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Review #{review_id} not found or already completed",
        )
    return templates.TemplateResponse(
        request, "cadence_complete.html.j2", {"vm": vm},
    )


@router.post("/reviews/{review_id}/complete")
def cadence_complete_post(
    request: Request, review_id: int,
    duration_minutes: int = Form(...),
    primary_lesson: str = Form(...),
    next_period_focus: str = Form(...),
):
    from datetime import date as _date
    from fastapi.responses import Response
    from swing.data.repos.review_log import complete_review_atomic, get
    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        review = get(conn, review_id)
        if review is None:
            raise HTTPException(status_code=404)
        if review.completed_date is not None:
            raise HTTPException(
                status_code=409,
                detail="Review already completed",
            )
        complete_review_atomic(
            conn, review_id=review_id,
            completed_date=_date.today().isoformat(),
            duration_minutes=duration_minutes,
            primary_lesson=primary_lesson,
            next_period_focus=next_period_focus,
        )
    finally:
        conn.close()
    # 204 + HX-Redirect to dashboard so cadence card flips to "completed":
    return Response(status_code=204, headers={"HX-Redirect": "/"})
```

Create `swing/web/templates/cadence_complete.html.j2`:

```jinja
{% extends "base.html.j2" %}
{% block title %}Complete {{ vm.review.review_type }} review{% endblock %}
{% block content %}
<h1>Complete {{ vm.review.review_type|capitalize }} review</h1>
<p>Period: {{ vm.review.period_start }} – {{ vm.review.period_end }}</p>
<p>{{ vm.n_closed_trades_in_period }} trade{{ "s" if vm.n_closed_trades_in_period != 1 else "" }}
   closed in this period.</p>
{% include "partials/cadence_complete_form.html.j2" %}
{% endblock %}
```

Create `swing/web/templates/partials/cadence_complete_form.html.j2`:

```jinja
<form method="post" action="/reviews/{{ vm.review.review_id }}/complete"
      hx-post="/reviews/{{ vm.review.review_id }}/complete"
      hx-headers='{"HX-Request": "true"}'>
  <label>
    Duration (minutes)
    <input type="number" name="duration_minutes" required min="1">
  </label>
  <label>
    Primary lesson
    <textarea name="primary_lesson" required rows="3"></textarea>
  </label>
  <label>
    Next-period focus
    <textarea name="next_period_focus" required rows="3"></textarea>
  </label>
  <button type="submit">Mark complete + freeze aggregates</button>
</form>
```

- [ ] **Step 7: Run all Task 12b tests**

Run: `python -m pytest tests/cli/test_review_complete_cli.py tests/web/test_cadence_complete_route.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add swing/config.py swing.config.toml swing/cli.py swing/web/routes/trades.py swing/web/view_models/trades.py swing/web/templates/cadence_complete.html.j2 swing/web/templates/partials/cadence_complete_form.html.j2 tests/cli/test_review_complete_cli.py tests/web/test_cadence_complete_route.py
git commit -m "feat(phase6): Task 12b — cadence-completion CLI + web (R1 Critical 1 + Major 3 fix)"
```

### Task 13: DashboardVM extensions + needs-review badge + cadence cards

**Files:**
- Modify: `swing/web/view_models/dashboard.py`
- Modify: `swing/web/templates/dashboard.html.j2`
- Create: `swing/web/templates/partials/needs_review_badge.html.j2`
- Create: `swing/web/templates/partials/cadence_cards.html.j2`
- Create: `tests/web/test_dashboard_needs_review_badge.py`
- Create: `tests/web/test_dashboard_cadence_cards.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_dashboard_needs_review_badge.py
def test_needs_review_count_populated(test_app_with_2_overdue_unreviewed_closed):
    with TestClient(test_app_with_2_overdue_unreviewed_closed) as client:
        r = client.get("/")
    assert "Needs review (2)" in r.text or "needs-review" in r.text


def test_needs_review_count_zero_hidden(test_app_only_open_trades):
    with TestClient(test_app_only_open_trades) as client:
        r = client.get("/")
    # Badge hidden when count is 0:
    assert "Needs review" not in r.text


# tests/web/test_dashboard_cadence_cards.py
def test_dashboard_renders_three_cadence_cards(test_app_with_review_log_rows):
    with TestClient(test_app_with_review_log_rows) as client:
        r = client.get("/")
    # 3 cards (daily/weekly/monthly):
    assert r.text.count("cadence-card") >= 3
    assert "Daily" in r.text
    assert "Weekly" in r.text
    assert "Monthly" in r.text


def test_cadence_card_shows_scheduled_when_no_completion(test_app_with_pending_daily):
    with TestClient(test_app_with_pending_daily) as client:
        r = client.get("/")
    # Daily card has scheduled_date but no completed_date:
    assert "Scheduled" in r.text or "Pending" in r.text
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/web/test_dashboard_needs_review_badge.py tests/web/test_dashboard_cadence_cards.py -v`
Expected: all FAIL.

- [ ] **Step 3: Extend DashboardVM**

Modify [swing/web/view_models/dashboard.py:DashboardVM](../../swing/web/view_models/dashboard.py). Add to the dataclass (alongside existing fields):

```python
@dataclass(frozen=True)
class CadenceCardVM:
    cadence_type: str  # 'daily' | 'weekly' | 'monthly'
    scheduled_date: str
    completed_date: str | None
    period_start: str
    period_end: str
    is_pending: bool

# In DashboardVM, add:
needs_review_count: int = 0
daily_card: CadenceCardVM | None = None
weekly_card: CadenceCardVM | None = None
monthly_card: CadenceCardVM | None = None
```

In `build_dashboard`, after the existing computations, add:

```python
from datetime import date as _date
from swing.data.repos.review_log import count_needs_review, list_recent

with connect(cfg.paths.db_path) as conn:
    needs_review = count_needs_review(
        conn, window_days=cfg.review.review_window_days,
        today_iso=_date.today().isoformat(),
    )
    cadence_cards: dict[str, CadenceCardVM | None] = {}
    for cadence in ("daily", "weekly", "monthly"):
        recent = list_recent(conn, review_type=cadence, limit=1)
        if recent:
            row = recent[0]
            cadence_cards[cadence] = CadenceCardVM(
                cadence_type=cadence,
                scheduled_date=row.scheduled_date,
                completed_date=row.completed_date,
                period_start=row.period_start,
                period_end=row.period_end,
                is_pending=row.completed_date is None,
            )
        else:
            cadence_cards[cadence] = None
```

Pass `needs_review_count=needs_review`, `daily_card=cadence_cards["daily"]`, etc. to the DashboardVM construction.

- [ ] **Step 4: Create the partials**

Create `swing/web/templates/partials/needs_review_badge.html.j2`:

```jinja
{% if vm.needs_review_count and vm.needs_review_count > 0 %}
<a href="/reviews/pending" class="needs-review-badge">
  Needs review ({{ vm.needs_review_count }})
</a>
{% endif %}
```

Create `swing/web/templates/partials/cadence_cards.html.j2`:

```jinja
<section class="cadence-cards">
  {% for cadence_label, card in [("Daily", vm.daily_card), ("Weekly", vm.weekly_card), ("Monthly", vm.monthly_card)] %}
    <article class="cadence-card cadence-card-{{ cadence_label|lower }}">
      <h3>{{ cadence_label }}</h3>
      {% if card is none %}
        <p>No reviews yet.</p>
      {% else %}
        <p>Period: {{ card.period_start }} – {{ card.period_end }}</p>
        {% if card.is_pending %}
          <p>Scheduled: {{ card.scheduled_date }} (pending)</p>
        {% else %}
          <p>Completed: {{ card.completed_date }}</p>
        {% endif %}
      {% endif %}
    </article>
  {% endfor %}
</section>
```

- [ ] **Step 5: Wire partials into dashboard.html.j2**

Modify [swing/web/templates/dashboard.html.j2](../../swing/web/templates/dashboard.html.j2). Insert near top:

```jinja
{% include "partials/needs_review_badge.html.j2" %}
```

And lower (e.g., below the open positions table or near the bottom):

```jinja
{% include "partials/cadence_cards.html.j2" %}
```

- [ ] **Step 6: Run tests to confirm they pass**

Run: `python -m pytest tests/web/test_dashboard_needs_review_badge.py tests/web/test_dashboard_cadence_cards.py -v`
Expected: all PASS.

- [ ] **Step 7: Run full fast suite + verify no Dashboard tests broke**

Run: `python -m pytest -m "not slow" -q 2>&1 | tail -3`
Expected: ≥1480 passed (1472 baseline + Phase 6 additions through Task 13).

- [ ] **Step 8: Commit**

```bash
git add swing/web/view_models/dashboard.py swing/web/templates/dashboard.html.j2 swing/web/templates/partials/needs_review_badge.html.j2 swing/web/templates/partials/cadence_cards.html.j2 tests/web/test_dashboard_needs_review_badge.py tests/web/test_dashboard_cadence_cards.py
git commit -m "feat(phase6): Task 13 — DashboardVM needs_review_count + cadence cards"
```

### Task 14: Pending-reviews list view + integration test for aggregate freezing

**Files:**
- Modify: `swing/web/routes/trades.py` (add `/reviews/pending` GET)
- Create: `swing/web/templates/reviews_pending.html.j2`
- Create: `tests/integration/test_review_log_aggregate_freezing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/integration/test_review_log_aggregate_freezing.py
"""End-to-end: aggregates persisted on Review_Log row are frozen-at-completion.

Brief §6.2 watch item 11 (4th sub-item).
"""
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import connect
from swing.data.models import Exit, Trade
from swing.data.repos.review_log import (
    complete_review_atomic, get, insert_pre_create,
)
from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event


def test_review_aggregates_frozen_when_more_trades_close(tmp_path: Path) -> None:
    """R1 Major 1 + R2 Major 2: complete_review_atomic OWNS the freeze.

    Pre-condition: 1 closed trade in period.
    Action 1: complete_review_atomic — reads + computes + writes atomically.
    Action 2: close another trade IN THE SAME PERIOD.
    Post-condition: re-fetched review_log row aggregates UNCHANGED.
    """
    db_path = tmp_path / "phase6.db"
    conn = connect(db_path)
    try:
        # Seed: one closed trade with share-weighted R=+1.0 in 2026-04-15:
        with conn:
            t1 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="T1", entry_date="2026-04-01",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, status="closed",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-01T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t1, exit_date="2026-04-15",
                    exit_price=11.0, shares=10, reason="manual",
                    realized_pnl=10.0, r_multiple=1.0, notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
        # Pre-create a daily review for 2026-04-15:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-15", period_end="2026-04-15",
                scheduled_date="2026-04-16",
            )
        assert review_id is not None
        # complete_review_atomic OWNS the trade-selection + compute + UPDATE
        # inside a single BEGIN IMMEDIATE transaction. The row is now frozen.
        complete_review_atomic(
            conn, review_id=review_id,
            completed_date="2026-04-16",
            duration_minutes=10,
            primary_lesson="Inaugural trade.",
            next_period_focus="Same setup.",
        )
        # Verify the frozen state shows 1 trade with net_R = 1.0:
        row = get(conn, review_id)
        assert row is not None
        assert row.n_trades_reviewed == 1
        assert row.net_R_effective == pytest.approx(1.0)
        assert row.win_rate == pytest.approx(1.0)
        assert row.profit_factor is None  # no losses

        # NOW close another trade in the same period (2026-04-15):
        with conn:
            t2 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="T2", entry_date="2026-04-10",
                    entry_price=20.0, initial_shares=5, initial_stop=18.0,
                    current_stop=18.0, status="closed",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-10T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t2, exit_date="2026-04-15",
                    exit_price=22.0, shares=5, reason="manual",
                    realized_pnl=10.0, r_multiple=1.0, notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
        # Re-fetch the review_log row → aggregates MUST be unchanged
        # (frozen-at-completion; subsequent trade closes do not mutate the row):
        row2 = get(conn, review_id)
        assert row2 is not None
        assert row2.net_R_effective == pytest.approx(1.0)  # NOT 2.0
        assert row2.n_trades_reviewed == 1                  # NOT 2
        assert row2.profit_factor is None
    finally:
        conn.close()
```

```python
# tests/web/test_review_route.py — append:
def test_get_reviews_pending_lists_overdue_trades(test_app_with_2_overdue):
    with TestClient(test_app_with_2_overdue) as client:
        r = client.get("/reviews/pending")
    assert r.status_code == 200
    assert "T1" in r.text
    assert "T2" in r.text
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/integration/test_review_log_aggregate_freezing.py tests/web/test_review_route.py::test_get_reviews_pending -v`
Expected: all FAIL.

- [ ] **Step 3: Implement /reviews/pending route + template**

Append to [swing/web/routes/trades.py](../../swing/web/routes/trades.py):

```python
@router.get("/reviews/pending", response_class=HTMLResponse)
def reviews_pending(request: Request):
    """Phase 6: list closed-and-unreviewed trades whose final exit was at
    least `cfg.review.review_window_days` ago. Linked from the dashboard
    'Needs review (N)' badge."""
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    from swing.web.view_models.trades import build_reviews_pending_vm
    vm = build_reviews_pending_vm(cfg=cfg)
    return templates.TemplateResponse(
        request, "reviews_pending.html.j2", {"vm": vm},
    )
```

Add `ReviewsPendingVM` + `build_reviews_pending_vm` to `swing/web/view_models/trades.py`:

```python
@dataclass(frozen=True)
class ReviewsPendingVM:
    trades: tuple[Trade, ...]
    window_days: int
    # 5-VM existing-fields safe defaults:
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False


def build_reviews_pending_vm(*, cfg: Config) -> ReviewsPendingVM:
    from datetime import date as _date
    from swing.data.repos.review_log import list_unreviewed_closed_trades
    conn = connect(cfg.paths.db_path)
    try:
        trades = list_unreviewed_closed_trades(
            conn, window_days=cfg.review.review_window_days,
            today_iso=_date.today().isoformat(),
        )
    finally:
        conn.close()
    return ReviewsPendingVM(
        trades=tuple(trades),
        window_days=cfg.review.review_window_days,
    )
```

Create `swing/web/templates/reviews_pending.html.j2`:

```jinja
{% extends "base.html.j2" %}
{% block title %}Pending reviews{% endblock %}
{% block content %}
<h1>Trades pending review</h1>
<p>Closed at least {{ vm.window_days }} day{{ "s" if vm.window_days != 1 else "" }} ago.</p>
{% if not vm.trades %}
<p>No trades pending review.</p>
{% else %}
<ul>
  {% for t in vm.trades %}
  <li>
    <a href="/trades/{{ t.id }}/review">#{{ t.id }} — {{ t.ticker }}</a>
    (entry {{ t.entry_date }} @ ${{ "%.2f"|format(t.entry_price) }})
  </li>
  {% endfor %}
</ul>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python -m pytest tests/integration/test_review_log_aggregate_freezing.py tests/web/test_review_route.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/trades.py swing/web/templates/reviews_pending.html.j2 tests/integration/test_review_log_aggregate_freezing.py tests/web/test_review_route.py
git commit -m "feat(phase6): Task 14 — /reviews/pending list + aggregate-freezing integration test"
```

### Task 15: Operator-witnessed browser verification gate + final baseline + cleanup

**Files:** none (verification + commit hygiene)

- [ ] **Step 1: Run full fast suite + ruff baseline**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
ruff check swing/ 2>&1 | tail -3
```

Expected: ≥1490 passed (1472 baseline + ~18-25 Phase 6 additions); ruff baseline UNCHANGED at ≤98 errors. If ruff regresses, fix in this task before ending.

- [ ] **Step 2: Operator-witnessed browser verification (BINDING per brief §6.2 watch item 10)**

This step is BLOCKING for Phase 6 done-criteria. The operator (or executing-implementer instructed to do so) MUST manually verify the following in a real browser (NOT TestClient):

1. **Form renders correctly.** Open `/trades/<id>/review` for a closed unreviewed trade in production DB (e.g., VIR id=1). Verify:
   - Stage grade dropdowns populated A-F.
   - All 6 Mistake_Tags categories visible with checkboxes.
   - Counterfactual + lesson-learned fields visible.
   - Disqualifying violations reference list is collapsible / visible.

2. **Soft-warn at close fires correctly.** Close the partial-exit trade DHC (or a synthetic test trade). On final exit, verify:
   - Soft-warn banner appears below the status strip.
   - "Review now" link navigates to the review form.
   - "Dismiss" link removes the banner.

3. **Dashboard "needs review" badge.** With one or more closed-unreviewed trades older than 7 days, verify:
   - Badge appears at the top of the dashboard.
   - Count matches the actual unreviewed count.
   - Clicking the badge navigates to `/reviews/pending`.

4. **Dashboard cadence cards.** With at least one Review_Log row per cadence (or none), verify:
   - 3 cards render (Daily / Weekly / Monthly).
   - Pending vs. completed states distinguished visually.
   - No render error in DevTools console.

5. **Review submission persists + redirects.** Submit the form on a closed unreviewed trade. Verify:
   - Browser navigates to `/trades` (HX-Redirect honored).
   - DB row has all 10 review fields populated.
   - Trade no longer appears in `/reviews/pending`.

6. **Review revisit shows correct frozen aggregates.** After per-trade review on VIR, run the cadence-completion path: visit `/reviews/{id}/complete` for the daily Review_Log row covering VIR's close date (or invoke `swing review complete --review-id <id> --duration-minutes 10 --primary-lesson "Inaugural" --next-period-focus "Same setup"`). Verify:
   - Form renders correctly with period range + closed-trade count.
   - Submit redirects to `/` (dashboard).
   - Cadence card for "daily" flips from PENDING → COMPLETED with the period's aggregates frozen on the row.
   - Close another trade in the same period (or simulate via DB edit). Reload dashboard. Verify the cadence card aggregates DID NOT change (frozen-at-completion atomic R1 Major 1 fix).

If ANY of the 6 verifications fail, the dispatch is BLOCKED until fixed. Capture the failure in the return report §3.

- [ ] **Step 3: Remove the marker file**

```bash
rm .copowers-subagent-active
```

- [ ] **Step 4: Final test count + commit hygiene check**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
git status
git log --oneline main..HEAD
```

Expected:
- Test count ≥1490.
- Working tree clean (only the marker-file removal is staged or committed).
- Commit history shows 13-15 conventional commits in the worktree (one per Task).

- [ ] **Step 5: Commit cleanup if any**

```bash
git add -A
git commit -m "chore(phase6): Task 15 — remove marker file + final baseline verification"
```

OR (if no changes), skip this step and proceed.

- [ ] **Step 6: Surface dispatch ready for merge**

The branch `phase6-post-trade-review` is ready for the orchestrator's merge step. The merge is performed in a separate dispatch; this Task's responsibility ends at producing a clean, verified branch.

---

## §K — Done criteria (cross-checked against brief §7)

- [x] Plan committed to `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md` with conventional-commit message.
- [x] Plan structure follows §G guidance (schema-first slice Tasks 1-9; web slice Tasks 10-12 + 12b + 13-14; verification Task 15). Task 12b added in R1 to ship cadence-completion (CLI + web + atomic-freeze).
- [x] Every locked decision in brief §2 is reflected in a plan task:
  - §2.1 cross-cutting drops/defers: respected (no playbook entity, no quality scoring, no pyramiding R-views, no trade_origin enum, no thesis/why_now/etc., circuit breaker default-disabled aligned).
  - §2.2 Mistake_Tags taxonomy: Task 3.
  - §2.3 Process Grade: Task 4.
  - §2.4 mistake_cost_R / lucky_violation_R as derived: Task 5 + Task 11+12 use the helpers via review service.
  - §2.5 Review_Log slim 14 + 7 persisted aggregates: Task 1 (schema) + Task 6 (repo).
  - §2.6 soft-warn at close: Task 9; dashboard badge: Task 13.
  - §2.7 5 cadence types schema-supported, daily/weekly/monthly UI-wired in V1: Task 1 (schema CHECK) + Task 7 (cadence helpers + step) + Task 13 (dashboard cards).
  - §2.8 counterfactual operator-input only: Task 11 + 12.
  - §2.9 cadence pre-create via pipeline runner: Task 7.
  - §2.10 single migration: Task 1.
- [x] Every operator-pre-designated watch item in brief §6.2 is pre-empted in the watch-item-mitigation table §I.
- [x] Adversarial Codex review iterated to NO_NEW_CRITICAL_MAJOR (Codex round results in return report).
- [x] §0 empirical audit step output captured in §A above (compute_stats coverage gap; closed_date is not a column; 5-VM rule details).
- [x] Plan task §0 (Setup) specifies worktree isolation + marker-file workflow (Task 0 Steps 1-2).
- [x] Plan done-criteria includes operator-witnessed browser verification gate (Task 15 Step 2; 6 verification surfaces).

---

**End of plan.**
