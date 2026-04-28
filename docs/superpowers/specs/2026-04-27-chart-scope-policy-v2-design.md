# Chart-Scope Policy v2 — Design Spec

**Date:** 2026-04-27
**Author:** Reid Smythe (operator) + orchestrator
**Status:** DRAFT — pending operator review + adversarial Codex review
**Skill posture:** Output of `copowers:brainstorming` (wraps `superpowers:brainstorming` with adversarial Codex review). Next phase: `copowers:writing-plans` to translate this spec into a per-task implementation plan.

---

## Mission

Replace the existing chart-scope policy (A+ candidates + top-N near-trigger watchlist by proximity-only sort) with a three-tier policy that aligns chart-scope selection with the dashboard's Phase 4 tag-aware watchlist sort AND unconditionally includes open positions, AND simultaneously close the cross-surface drift race in `swing/web/chart_scope.resolve_chart_scope` (R2 Major from chart-pattern flag-v1 chart-access UX dispatch, 2026-04-27, commit `f0d13e8`).

## Audience

Implementer-instance (writing-plans phase next, then executing-plans). This spec governs the implementation; downstream documents (plan, briefs) reference this spec for design rationale + binding decisions.

## Background and motivation

Two concurrent symptoms surfaced in 2026-04-27 manual verification round 1 of chart-pattern flag-v1 V1 build:

1. **UX gap.** After the operator entered the DHC trade during the walkthrough, the ticker moved from active watchlist to open positions. The chart-view path disappeared because open positions are not in chart-scope (charts are only generated for chart-scope tickers). The new `#3` open-positions row HTMX expand surface (commit `f0d13e8`) shows "Chart unavailable" for any ticker that's rotated out of chart-scope — which is the COMMON case for held positions.

2. **Algorithmic-coverage gap.** Empirical evidence from the same walkthrough: dashboard top-5 watchlist (Phase 4 tag-aware composite sort) only overlapped chart-scope set on 1 of 5 tickers (DHC). Other 4 watchlist top-5 (TWST/GFS/ALTO/RNG) got NO classification. The mismatch is hypothesized to be partly responsible for zero flag detections in the cache.

3. **Drift race (coupled scope).** `resolve_chart_scope` independently re-reads "latest completed pipeline_run" inside the resolver, while each caller does its own SELECT for `data_asof_date` first. A new run completing between caller's read + resolver's read produces a torn read. Caller A sees runN's date paired with runN+1's chart_targets. Surfaced as R2 Major during the chart-access UX dispatch's adversarial Codex review; brief excluded modifications to the resolver, so it remained an open follow-up.

This spec addresses all three concurrently because they share infrastructure (`_step_charts`, `chart_scope.py`, `pipeline_chart_targets` table, the 3 caller sites).

## Operator decisions captured

| # | Question | Decision |
|---|---|---|
| 1 | Primary motivation: UX-only / coverage-only / both | **Both** — share infrastructure; design once for both |
| 2 | Watchlist-side selection criterion: proximity-only / tag-aware composite / hybrid | **Tag-aware composite** (mirror Phase 4 dashboard sort exactly) |
| 3 | Held-position policy: always include / pin-N-sessions / conditional | **Always include** all open positions as a third explicit tier |
| 4 | Approach for dispatch scope: policy-only / coupled with drift-race / comprehensive | **Coupled** (Approach 2): policy redesign + drift-race tightening in same dispatch |

Five sub-confirmations during section presentation:
- Precedence order: `aplus > open_position > tag_aware_top_n` (A+ wins on overlap; reasoning: A+ is the most informative system-generated signal)
- N for tag-aware top-N: 10 (was 5)
- Pivot for open-position tier: `trades.entry_price` (no recommendation-table linkage; simple)
- Migration: heavyweight CREATE-COPY-DROP-RENAME pattern (do it now; avoid leaving a CHECK-constraint gap)
- Legacy `'near_proximity'` source value: retained for pre-migration rows; no backfill (audit-trail integrity)
- `binding: PipelineRunBinding` is required (no `None` default); caller MUST handle no-completed-run case before calling resolver

---

## §A — Chart-scope tier model + selection criteria

Three tiers compose the chart-scope set per pipeline run, with deduplication precedence.

| Precedence | Tier | Source value | Selection |
|---|---|---|---|
| 1 (highest) | A+ candidates | `'aplus'` | All candidates with `bucket = 'aplus'` from the run's evaluation. Unchanged from current behavior. |
| 2 | Open positions | `'open_position'` | All currently-open trades from `list_open_trades(conn)`. **NEW** — replaces today's "open positions are never charted" gap. |
| 3 | Tag-aware watchlist top-N | `'tag_aware_top_n'` | Top-N from `list_active_watchlist(conn)` ranked by Phase 4 4-key composite. N = `cfg.pipeline.chart_top_n_watch`, default raised 5 → 10. Replaces today's `'near_proximity'` selection. |

### Deduplication

A ticker that appears in multiple tiers is recorded ONCE in `pipeline_chart_targets` under the highest-precedence source value. Implementation: linear pass through tiers in precedence order with a `seen: set[str]`, mirroring the existing dedup pattern in `_step_charts:568-582`.

Edge case: ticker in all three tiers → recorded as `'aplus'`. In practice, A+ ∩ open_position is rare (A+ implies fresh near-pivot setup; held positions have moved past pivot). The dedup precedence rule covers the rare overlap defensively.

### Tag-aware composite definition

Mirrors the Phase 4 watchlist sort exactly (per `swing/web/view_models/watchlist.py` `_sort_watchlist`):

1. **Tag count DESC** — more A+/VCP✓/TT✓ tags → higher rank.
2. **Tag precedence DESC** — sum of weights: A+=4, VCP✓=2, TT✓=1.
3. **Proximity to pivot ASC** — `abs((last_close - entry_target) / entry_target)`.
4. **Ticker ASC** — deterministic tiebreaker.

Filter: only watchlist entries with both `entry_target` AND `last_close` populated (matches existing filter in `_step_charts:559-562`). Ticker selected if rank ≤ N AND not already covered by a higher-precedence tier (post-dedup).

Tag set definition: must MATCH `_sort_watchlist`'s tag derivation byte-for-byte **on the same filtered input set** (entries with both `entry_target` and `last_close` populated). If `_sort_watchlist` applies a wider/narrower filter, the spec's chart-scope sort applies the same `_step_charts:559-562`-style filter first and the byte-identity claim is over the intersection. If `_sort_watchlist` is refactored or tag taxonomy widens (e.g., `flag` tag becoming sort-participating in V2), `_step_charts` must follow to maintain alignment. **Implementation note:** the writing-plans phase should consider extracting a shared `_tag_aware_sort_key(watchlist)` helper to ensure both call sites stay aligned by construction; otherwise document the byte-identity invariant explicitly with a test pin.

### Pivot/stop sourcing for chart rendering

The chart `<img>` shows pivot and stop horizontal lines (`hlines`):

| Tier | Pivot source | Stop source |
|---|---|---|
| A+ | `candidates.pivot` | `candidates.initial_stop` |
| Open position | `trades.entry_price` (as pivot proxy) | `trades.current_stop` |
| Tag-aware | `watchlist.entry_target` | `watchlist.initial_stop_target` |

Rationale for open-position tier: at-pivot entry discipline (per `docs/orchestrator-context.md` 2026-04-25 decision) means `entry_price ≈ recommendation-time pivot` for hypothesis-tagged trades. For trades without a recommendation linkage, entry_price is the closest reasonable signal. **Current** stop is what the operator wants to see during trade management (not the initial stop, which may have been adjusted via `trade_events`).

Recommendation-table linkage for open-position pivot was considered and rejected per Q3-confirmed simplicity preference: the 1-cent-or-so difference between `entry_price` and recommendation-time pivot doesn't materially affect the chart's hline position.

### Budget validation

Per pipeline run:

| Tier | Typical | Maximum |
|---|---|---|
| A+ | 0-2 | unbounded (rare to exceed 5 on Finviz pool) |
| open_position | 0-2 | 6 (hard cap per CLAUDE.md) |
| tag_aware_top_n | 10 | 10 (config-bounded) |
| **Total per run** | **~10-13** | **~21** |

Current chart-scope: ~5-7 per run. New chart-scope: typical 10-13, max ~21.

yfinance fetch cost: ~10-13 sequential fetches at ~1s each = 10-13s extra latency per pipeline run. Well below the rate-limit threshold (yfinance daily quota is per-key per-day; current usage is well under 1% of quota). Per CLAUDE.md gotchas: rate-limit issues arise from `yf.download(threads=True)` (forbidden) and concurrency on `Ticker.history()` (bounded by app-level executor); sequential-fetch latency is the only observable cost. Acceptable.

Disk space: each PNG is ~50-200 KB. Doubling chart count adds ~5-10 MB per pipeline session. Negligible vs `exports/` retention budget (90 days × 1 run/day × ~10 MB ≈ 900 MB; retention sweep already exists).

---

## §B — Schema + persistence taxonomy

### Migration `0011_pipeline_chart_targets_source_taxonomy.sql`

Uses SQLite's CREATE-COPY-DROP-RENAME pattern (the only way to modify a CHECK constraint in SQLite, per CLAUDE.md note + chart-pattern flag-v1 lesson "Schema-layer guarantees beat repo-layer guarantees on every dimension except backward-compat migration cost").

```sql
-- Migration 0011: chart_targets source taxonomy expansion for chart-scope policy v2.
--
-- Adds 'open_position' and 'tag_aware_top_n' to the source CHECK constraint.
-- Retains 'near_proximity' for legacy rows from pipeline runs prior to this
-- migration (no backfill — historical accuracy preserved per audit-trail discipline).
--
-- After this migration, _step_charts writes 'tag_aware_top_n' for the watchlist
-- tier (never 'near_proximity'). The 'near_proximity' value is read-only legacy.

CREATE TABLE pipeline_chart_targets_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
    ticker TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN (
        'aplus',
        'near_proximity',
        'open_position',
        'tag_aware_top_n'
    )),
    chart_status TEXT NOT NULL CHECK (chart_status IN ('ok', 'fetcher_failed', 'too_few_bars', 'pending')),
    UNIQUE (pipeline_run_id, ticker)
);

INSERT INTO pipeline_chart_targets_new (id, pipeline_run_id, ticker, source, chart_status)
SELECT id, pipeline_run_id, ticker, source, chart_status
FROM pipeline_chart_targets;

DROP TABLE pipeline_chart_targets;
ALTER TABLE pipeline_chart_targets_new RENAME TO pipeline_chart_targets;

CREATE INDEX idx_pipeline_chart_targets_run ON pipeline_chart_targets(pipeline_run_id);

UPDATE schema_version SET version = 11;
```

Forward-only; no down-migration. `chart_status` enum unchanged.

### Source value taxonomy

| Source value | Operator meaning | Emitted by |
|---|---|---|
| `aplus` | Today's A+ signal from latest evaluation | `_step_charts` (unchanged) |
| `open_position` | Currently-open trade | `_step_charts` (NEW) |
| `tag_aware_top_n` | Watchlist top-10 by tag-aware composite | `_step_charts` (NEW) |
| `near_proximity` | LEGACY: chart-scope from pre-2026-04-27 pipeline runs | NOT emitted post-0011 |

### Code semantics (resolver)

`resolve_chart_scope` and consumers treat `'near_proximity'` and `'tag_aware_top_n'` IDENTICALLY for the in-scope/out-of-scope question. The source distinction is for audit/observability only. Existing consumer code paths (`_resolve_via_chart_targets`) continue to work without modification — they query by `(pipeline_run_id, ticker)` and don't filter on source.

### Backward-compatibility

Existing rows preserved bit-identically (count, ticker, source, chart_status, pipeline_run_id all intact post-migration). Legacy `'near_proximity'` rows continue to resolve as in-scope. Verification queries in `docs/chart-pattern-flag-v1-manual-verification.md` §0 continue to work; no SQL changes needed for legacy data inspection.

---

## §C — Resolver signature change + drift-race tightening

### `PipelineRunBinding` dataclass

```python
@dataclass(frozen=True)
class PipelineRunBinding:
    """Pinned pipeline_run state for race-free chart-scope resolution.

    Computed once at request entry by `latest_completed_pipeline_run(conn)`
    and passed to `resolve_chart_scope` so all downstream reads bind to the
    SAME run, even if a new run completes mid-request. Closes the R2 Major
    drift race surfaced in chart-access UX dispatch (commit `f0d13e8`,
    2026-04-27).
    """
    run_id: int
    finished_ts: str
    data_asof_date: str
    charts_status: str | None
    evaluation_run_id: int | None
```

### `latest_completed_pipeline_run` helper

```python
def latest_completed_pipeline_run(conn) -> PipelineRunBinding | None:
    """Single-read source of truth for 'which pipeline_run does this request bind to?'.

    Returns None when no completed runs exist. Caller MUST handle the None
    case before calling resolve_chart_scope.
    """
    row = conn.execute(
        """SELECT id, finished_ts, data_asof_date, charts_status, evaluation_run_id
           FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC LIMIT 1"""
    ).fetchone()
    return PipelineRunBinding(*row) if row else None
```

### New `resolve_chart_scope` signature

```python
def resolve_chart_scope(
    conn,
    *,
    binding: PipelineRunBinding,    # REQUIRED; no None default
    ticker: str,
    charts_dir: Path,
    chart_top_n_watch: int,
) -> tuple[str | None, str | None]:
    """Race-free chart-scope resolver. Caller MUST pin the binding at request
    entry via `latest_completed_pipeline_run`. Resolver does NOT re-read
    pipeline_runs internally."""
```

The resolver:
- Uses `binding.run_id`, `binding.charts_status`, `binding.data_asof_date`, `binding.evaluation_run_id` directly.
- Does NOT execute any `SELECT ... FROM pipeline_runs` of its own.
- Returns the same `(chart_reason, chart_reason_message)` tuple shape (`(None, None)` for available; otherwise reason + operator-facing message).
- Branches identical to current: charts_status check → FK-backed path (when `evaluation_run_id` is non-null) → heuristic fallback (legacy NULL path).

The `chart_top_n_watch` parameter is retained because the legacy heuristic fallback path (`_resolve_via_heuristic`) still uses it. Even though new pipeline runs don't traverse the heuristic path, legacy `pipeline_runs` rows with `evaluation_run_id IS NULL` from before migration 0006 still trigger the heuristic; preserving the parameter avoids a parallel signature change there.

### Caller updates (3 sites)

All three call sites pin the binding at request entry:

```python
# Pattern (apply at each site):
binding = latest_completed_pipeline_run(conn)
if binding is None:
    return <404 / VM-with-chart_reason='no-run' / etc.>
reason, message = resolve_chart_scope(
    conn, binding=binding, ticker=ticker.upper(),
    charts_dir=cfg.paths.charts_dir,
    chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
)
# binding.data_asof_date now bound to the SAME run that produced `reason`.
```

| Site | File | Current behavior | Updated behavior |
|---|---|---|---|
| #2 chart route | `swing/web/routes/charts.py:39-83` | Reads `pipeline_runs.data_asof_date` independently, then calls resolver (which re-reads) | Pins binding at top of route handler; passes binding to resolver |
| #3 open-positions builder | `swing/web/view_models/open_positions_row.py:187` | Reads latest pipeline run for `data_asof_date`, then calls resolver | Pins binding at top of `build_open_positions_expanded`; passes binding to resolver |
| Watchlist expand builder | `swing/web/view_models/watchlist.py:284` | Reads latest pipeline run independently, then calls resolver | Pins binding at top of `build_watchlist_expanded`; passes binding to resolver |

### No backward-compat shim

The signature change is breaking. All 3 callers migrate in the same dispatch. There are no third-party consumers of `chart_scope.py` outside the project (verified via repo-wide grep at brief-drafting time).

---

## §D — Configuration, migration, rollout

### Config knob change

`swing/config.py:118`:

```python
@dataclass(frozen=True)
class PipelineConfig:
    ...
    chart_top_n_watch: int = 10  # was 5; raised in chart-scope policy v2 (2026-04-27)
```

Single-line default change. Operator can override via `swing.config.toml` if they want to tune up/down. No new knobs.

### Migration logistics

- `swing/data/migrations/0011_pipeline_chart_targets_source_taxonomy.sql` runs as part of `swing db-migrate` per project convention. Forward-only; no down-migration.
- CREATE-COPY-DROP-RENAME preserves all existing rows including legacy `'near_proximity'` source values.
- `schema_version` advances 10 → 11.
- `swing db-migrate` is auto-run by `swing` CLI on first launch post-update per existing operator workflow.

### Code-roll dependency

`_step_charts` writes `'open_position'` and `'tag_aware_top_n'` source values; both are CHECK-constrained additions in 0011. **The migration MUST apply BEFORE `_step_charts` runs, OR the pipeline run fails the integrity check on insert.** Fast-suite tests use ephemeral DBs that auto-migrate to latest; production deployment requires `swing db-migrate` to run before next pipeline (handled automatically by CLI).

### Rollout behavior (first post-migration pipeline run)

- Chart-scope set grows from ~5-7 → ~10-13 typical (max ~21). Per-run yfinance latency: +10-15s.
- Open-position tickers (e.g., DHC) start appearing in `pipeline_chart_targets` with source `'open_position'`. Their `/charts/<ticker>.png` standalone URLs (#2) start returning 303 redirects instead of 404s.
- Open-positions row #3 expand starts rendering charts inline instead of "Chart unavailable" for currently-held positions.
- Watchlist tickers ranked by Phase 4 tag-aware sort enter chart-scope; tickers ranked only by proximity (without TT✓/VCP✓/A+ tags) drop out of top-10 if tagged tickers fill the slots.
- Flag classifier runs against the broader pool; may surface detections previously masked by chart-scope misalignment. **No correctness regression** — `'none'` classifications remain dominant regardless of chart-scope; calibration via Task 7.3/7.4 is unaffected.

### No historical backfill

Existing pipeline runs keep their `'near_proximity'` rows. Operator inspecting old runs sees historical chart-scope semantics accurately preserved.

---

## §E — Test plan

Coverage areas and key invariants. Specific test cases are the writing-plans phase's responsibility; this section enumerates what must be verified.

### Migration `0011`

- Schema_version advances 10 → 11.
- New CHECK constraint accepts all 4 source values; rejects unknown values (e.g., a hypothetical `'random_source'` insert raises `IntegrityError`).
- Existing rows preserved bit-identically (count, ticker, source, chart_status, pipeline_run_id all intact post-migration).
- Index `idx_pipeline_chart_targets_run` re-created on the new table.

### `_step_charts` policy (`tests/pipeline/test_runner_chart_targets.py`, extended)

- Three-tier composition with deduplication precedence (`aplus` > `open_position` > `tag_aware_top_n`).
- Tag-aware composite sort produces correct ordering on watchlists with diverse tag profiles (count + precedence + proximity + ticker tiebreaker).
- Open-position tier sources pivot/stop from `trades.entry_price` + `trades.current_stop`, NOT from any watchlist join.
- N=10 default; configurable via `cfg.pipeline.chart_top_n_watch`.
- Edge cases: empty watchlist, zero open positions, ticker present in all three tiers (records once with `aplus`), tag-aware top-N has fewer than N qualifying tickers, watchlist with no entry_target/last_close (filtered out).

### Resolver signature change (`tests/web/test_chart_scope.py`, updated)

- `latest_completed_pipeline_run(conn)` returns `PipelineRunBinding` with all 5 fields populated.
- `latest_completed_pipeline_run(conn)` returns `None` when no completed runs exist.
- `resolve_chart_scope(conn, binding=..., ...)` uses the binding's `pipeline_run_id` directly; does NOT re-SELECT from `pipeline_runs`.
- **Race-tightening contract pin:** passing a deliberately-stale binding (from runN) while runN+1 has completed; resolver still returns runN's chart_targets answer (proves binding is authoritative, not the latest-row SELECT).
- All existing test cases in `test_chart_scope.py` pass under the new signature (existing scenarios continue to work; new fixtures construct binding explicitly).

### Caller migration (3 sites)

- `swing/web/routes/charts.py` — existing tests in `tests/web/test_routes/test_charts_route.py` continue to pass; binding pinned at request entry; redirect URL constructed from `binding.data_asof_date` (proves caller uses pinned date, not a re-read).
- `swing/web/view_models/open_positions_row.py` — existing tests in `tests/web/test_routes/test_open_positions_expand.py` continue to pass; binding pinned at builder entry.
- `swing/web/view_models/watchlist.py` — existing watchlist-expand tests continue to pass.

### Tag-aware-sort byte-identity invariant

Either:
- (a) Extract shared `_tag_aware_sort_key(watchlist)` helper used by both `_sort_watchlist` (web view-model) and `_step_charts` (pipeline) — invariant verified by construction.
- (b) Document the byte-identity requirement explicitly with a parametrized test that asserts both sort outputs are identical for a fixture set of watchlists.

Writing-plans phase chooses approach.

### Fast suite floor

**1163 + N** new tests (N estimated 15-25; trust pytest output over this estimate per project test-count-drift gotcha).

---

## §F — Out-of-scope / deferred

Items intentionally excluded from this dispatch:

### From #2/#3 dispatch's 7 open follow-ups

- Holdings-aware `CHART_REASON_MESSAGES` variant — open-position tier inclusion (this dispatch) mostly closes the underlying pain; specialized messaging deferred indefinitely.
- Section-level OOB-refresh-on-stale recovery — cross-cutting project-wide row-recovery proposal; orthogonal to chart-scope policy.
- Defense-in-depth ticker-format regex on `/charts/{ticker}.png` — independent of chart-scope; not blocking.
- Lowercase + dotted-symbol canonicalization tests — independent.
- V1 expanded-row content scope-limit (chart only) — different scope (UX content, not chart access).
- Test pin for "no completed pipeline run" branch on open-positions expand — covered organically by §E "latest_completed_pipeline_run returns None" test.

### Operational / orthogonal

- Today's `fetcher_failed` chart_targets investigation (yfinance / network operational issue) — not chart-scope policy.
- Task 7.3 / 7.4 classifier calibration — operator-paced; orthogonal.
- CLI / journal / advisories / Phase 2 (`swing/trades/`, `swing/data/` repos) code paths — untouched.

### Source-taxonomy add-ons (kept lean)

- Operator-facing chart-scope-source UI badges ("(open position)", "(A+)") — documented as informational; not implemented in this dispatch.
- Recommendation-table linkage for richer open-position pivot sourcing — kept simple per Q3-confirmed approach.
- Backfill of historical `'near_proximity'` rows to `'tag_aware_top_n'` — none. Audit-trail integrity preserved.

### Future tuning (post-ship knob territory)

- Per-tier N knobs (e.g., separate `chart_top_n_aplus_padding`, `chart_top_n_watch_tier`) — defer until evidence justifies the complexity.
- Open-position pin-duration / conditional-inclusion logic — kept always-on per Q3 recommendation.

### Schema

- Only migration `0011`. No additional migrations in this dispatch.

---

## References

**Spec governance:** This spec is the design source-of-truth for chart-scope policy v2. Subsequent documents (implementation plan + dispatch brief + adversarial review) reference this spec for design rationale + binding decisions. Changes to this spec post-approval require explicit operator sign-off + a re-run of the spec-review loop.

**Related work:**

- `docs/chart-pattern-flag-v1-manual-verification-results.md` §"#4 — Chart-scope set selection misaligned with Phase 4 watchlist sort" — verification round 1 evidence motivating this spec.
- `docs/chart-pattern-flag-v1-chart-access-ux-brief.md` — chart-access UX dispatch (#2 + #3) immediate predecessor; surfaced the R2 Major drift race.
- `swing/web/chart_scope.py` — current resolver implementation; this spec rewrites the signature.
- `swing/pipeline/runner.py:541-582` — current `_step_charts` policy; this spec rewrites the tier composition.
- `swing/web/view_models/watchlist.py` — `_sort_watchlist` Phase 4 composite sort; this spec mirrors the composite definition.
- `swing/data/migrations/0006_pipeline_chart_linkage.sql` — original `pipeline_chart_targets` schema; migration 0011 amends the source CHECK.
- `docs/orchestrator-context.md` §"Lessons captured" — chart-pattern flag-v1 phase lessons applied throughout (single-subagent dispatch, observable verification, manual visual verification, etc.).
- `docs/orchestrator-context.md` §"Binding conventions" — 4-tier commit-message convention, ERE grep, no-amend rules.
- `CLAUDE.md` gotchas — yfinance rate-limit (binding constraint for budget validation), HTMX OOB-swap drift (preserved by single-include guarantee), base-layout 5-VM rule (not applicable; no new VM consumed by base.html.j2).

**Skill flow:**

- Output of `copowers:brainstorming` (this spec).
- Pending: `copowers:adversarial-critic` review (next step in copowers wrapper).
- Pending: `copowers:writing-plans` to translate this spec into per-task plan.
- Pending: `copowers:executing-plans` to dispatch the implementation.

**Operator signing:** orchestrator drafted; operator approved each design section (§A through §F); spec-review loop pending; adversarial Codex review pending; writing-plans dispatch pending.
