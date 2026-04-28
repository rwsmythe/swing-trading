# Chart-Scope Policy v2 — Design Spec

**Date:** 2026-04-27
**Author:** Reid Smythe (operator) + orchestrator
**Status:** Approved by adversarial Codex review (4 rounds → NO_NEW_CRITICAL_MAJOR); pending operator final approval + writing-plans dispatch. Codex-resolved findings tagged inline (R1 Major 1-6 + Minor 1-5; R2 Major 1-3 + Minor 1-2; R3 Major 1-2 + Minor 1-2; R4 Minor 1-2). All majors addressed via spec edits; minors either resolved or accepted-with-rationale per V1 scope discipline.
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
| 2 | Open positions | `'open_position'` | All currently-open trades from `list_open_trades(conn)`. **NEW** — replaces today's "open positions are never charted" gap. **Batch-scope note:** charts are generated during the scheduled pipeline run; a position opened AFTER the latest completed run will remain unchartable until the next pipeline run. On-demand chart generation is out-of-scope per §F. |
| 3 | Tag-aware watchlist top-N | `'tag_aware_top_n'` | Top-N from `list_active_watchlist(conn)` ranked by Phase 4 4-key composite. N = `cfg.pipeline.chart_top_n_watch`, default raised 5 → 10. Replaces today's `'near_proximity'` selection. **Data-eligible scope note:** alignment to the dashboard's tag-aware ordering is defined over data-eligible watchlist rows only (entries with both `entry_target` and `last_close` populated). |

### Deduplication

A ticker that appears in multiple tiers is recorded ONCE in `pipeline_chart_targets` under the highest-precedence source value. Implementation: linear pass through tiers in precedence order with a `seen: set[str]`, mirroring the existing dedup pattern in `_step_charts:568-582`.

**Ticker canonicalization before dedup** (Codex R1 Minor 3): all tickers normalized to upper-case before being added to `seen`. Watchlist + candidates + trades all currently emit upper-case tickers in production, so this is defensive — but mismatched casing across tiers would silently produce duplicate `pipeline_chart_targets` rows under different sources, breaking the UNIQUE `(pipeline_run_id, ticker)` constraint. Normalize at tier-source extraction.

Edge case: ticker in all three tiers → recorded as `'aplus'`. In practice, A+ ∩ open_position is rare (A+ implies fresh near-pivot setup; held positions have moved past pivot). The dedup precedence rule covers the rare overlap defensively.

### Open-position tier snapshot semantics (Codex R1 Major 2)

The `open_position` tier is sourced from `list_open_trades(conn)` at the moment `_step_charts` executes (mid-pipeline, after `_step_evaluate`). The resulting set is a **snapshot** taken during run N's chart step and persisted to `pipeline_chart_targets` immutably. Subsequent runs re-snapshot independently.

Implication: chart-scope is "as-of pipeline run N" by virtue of the snapshot being persisted at run N. The web layer's `resolve_chart_scope` reads `pipeline_chart_targets` rows for the binding's `run_id` — those rows reflect run N's snapshot. **There is NO race between web-layer "binding" and "currently open trades"** — the binding indirects through the persisted snapshot, not through a live trades query.

Edge case: a trade opened AFTER run N's chart step started but BEFORE run N completes — included in run N's open_position tier. A trade opened AFTER run N completes — not in run N's snapshot; appears in run N+1's snapshot. Acceptable (snapshot semantics; operator entering trade between runs sees chart access via `/charts/<ticker>.png` after next run completes).

Edge case: a trade closed BETWEEN run N and the operator's web request that hits run N's binding — chart still appears (run N's snapshot included it; rows immutable). Operator may see a chart for a now-closed trade until next pipeline run completes. Consistent with binding's "pinned to run N" semantics; not a defect.

### Tag-aware composite definition

Mirrors the Phase 4 watchlist sort exactly (per `swing/web/view_models/watchlist.py` `_sort_watchlist`):

1. **Tag count DESC** — more A+/VCP✓/TT✓ tags → higher rank.
2. **Tag precedence DESC** — sum of weights: A+=4, VCP✓=2, TT✓=1.
3. **Proximity to pivot ASC** — `abs((last_close - entry_target) / entry_target)`.
4. **Ticker ASC** — deterministic tiebreaker.

Filter: only watchlist entries with both `entry_target` AND `last_close` populated (matches existing filter in `_step_charts:559-562`). Ticker selected if rank ≤ N AND not already covered by a higher-precedence tier (post-dedup). **Note:** the watchlist UI surfaces all watchlist rows including data-ineligible ones (via `inf` proximity fallback); the chart-scope alignment claim is bounded to data-eligible rows only. Data-ineligible rows (missing pivot/price) remain without charts by design.

Tag set definition: must MATCH `_sort_watchlist`'s tag derivation byte-for-byte **on the same filtered input set** (entries with both `entry_target` and `last_close` populated). If `_sort_watchlist` applies a wider/narrower filter, the spec's chart-scope sort applies the same `_step_charts:559-562`-style filter first and the byte-identity claim is over the intersection. If `_sort_watchlist` is refactored or tag taxonomy widens (e.g., `flag` tag becoming sort-participating in V2), `_step_charts` must follow to maintain alignment. **Implementation note:** the writing-plans phase should consider extracting a shared `_tag_aware_sort_key(watchlist)` helper to ensure both call sites stay aligned by construction; otherwise document the byte-identity invariant explicitly with a test pin.

**Residual filter-intersection limitation (Codex R1 Major 3 — accepted with rationale):** `_sort_watchlist` (web) sorts the full active watchlist for dashboard display, including rows missing `entry_target` or `last_close`. `_step_charts` (pipeline) filters those rows out because the tag-aware composite sort's proximity tiebreaker requires both fields. **Net effect:** a watchlist row visible on the dashboard top-N but missing `entry_target` or `last_close` will NOT enter chart-scope. The byte-identity claim therefore covers the *intersection* (rows passing the chart-scope filter), not the dashboard's full top-N. **Quantified impact:** in practice, watchlist rows without `entry_target` are tickers without a recommended pivot (typically not actionable); rows without `last_close` are price-cache misses (transient). Both are unusual states; the residual gap is small but real. **Future work:** aligning the two filters (either by widening `_step_charts` to include rows with proximity-undefined fallback OR by narrowing `_sort_watchlist` to only show fully-qualified rows) is a separate dispatch; not in this spec's scope. The writing-plans phase MUST add a test that explicitly demonstrates the intersection limit (e.g., a watchlist with one fully-qualified row + one partially-qualified row, asserting only the qualified row enters chart-scope) so the limitation is documented in code.

### Pivot/stop sourcing for chart rendering

The chart `<img>` shows pivot and stop horizontal lines (`hlines`):

| Tier | Pivot source | Stop source |
|---|---|---|
| A+ | `candidates.pivot` | `candidates.initial_stop` |
| Open position | `trades.entry_price` (as pivot proxy) | `trades.current_stop` |
| Tag-aware | `watchlist.entry_target` | `watchlist.initial_stop_target` |

Rationale for open-position tier: at-pivot entry discipline (per `docs/orchestrator-context.md` 2026-04-25 decision) means `entry_price ≈ recommendation-time pivot` for hypothesis-tagged trades. For trades without a recommendation linkage, entry_price is the closest reasonable signal. **Current** stop is what the operator wants to see during trade management (not the initial stop, which may have been adjusted via `trade_events`).

Recommendation-table linkage for open-position pivot was considered and rejected per Q3-confirmed simplicity preference: the 1-cent-or-so difference between `entry_price` and recommendation-time pivot doesn't materially affect the chart's hline position.

**Edge cases for open-position pivot/stop sourcing (Codex R1 Minor 5):**

- **Partial exits:** `trades.entry_price` is the original entry price; partial exits do NOT modify it. Chart pivot remains the original entry. Acceptable — the pivot represents the trade thesis's anchor point, not the position's current cost basis.
- **Position adds (averaged entries):** the project's current trade model does NOT support averaged entries (each entry creates a separate trade row; cf. `swing/trades/entry.py` + the `one_open_trade_per_ticker` constraint from migration 0004). So averaged-entry behavior is N/A in V1. If V2 introduces averaged entries, chart pivot semantics need re-design.
- **Stop-less trades** (`trades.current_stop IS NULL` or 0): operator-discipline violation; should not occur in production trades. **Render behavior:** OMIT the stop hline entirely (Codex R2 Major 3). Plotting `stop=0.0` would auto-scale the y-axis to include zero, compressing price action and implying false catastrophic downside. The rendering layer accepts a sentinel `stop is None or stop <= 0.0` and renders the chart with NO stop line; the title format also omits the `stop X.XX` segment in this case. Implementation: `render_chart` (or its overlay-aware caller) gains a conditional skip on the stop hline; tests pin this behavior.
- **Stop adjusted via `trade_events`:** `trades.current_stop` reflects the latest stop after all `trade_events` of `kind='stop_adjust'` have been applied. Chart shows the current value, NOT the initial. Consistent with operator's "what's my current stop?" mental model.

### Budget validation (Codex R1 Major 4 + Major 5)

Per pipeline run:

| Tier | Typical | Maximum |
|---|---|---|
| A+ | 0-2 | UNBOUNDED by policy (every A+ is operator-actionable; never silently dropped) |
| open_position | 0-2 | 6 (hard cap per CLAUDE.md `concurrent_cap` config) |
| tag_aware_top_n | 10 | 10 (config-bounded) |
| **Total per run** | **~10-13** | **~21 under typical A+ conditions; potentially higher** |

**A+ tier is intentionally unbounded** (Codex R2 Major 1). A+ classifications are the framework's most-actionable signal; silently dropping them would violate the "operator drives, agent serves" discipline. The "~21 max" estimate is anchored to TYPICAL A+ counts (0-2 per day on the operator's Finviz pool). If a future regime produces sustained A+ spikes (e.g., 20+ per day), the budget is breached: detection happens via the wall-time monitoring logged for each pipeline run (see "Budget overrun behavior" below); a follow-up dispatch can then tune `chart_top_n_watch` down OR introduce A+-tier prioritization.

Current chart-scope: ~5-7 per run. New chart-scope: typical 10-13, max ~21.

**Per-ticker cost breakdown** (sequential, post-fetch):

| Component | Per-ticker cost | Source |
|---|---|---|
| yfinance `Ticker.history()` fetch | ~1.0s (cached: ~0.1s) | network-bound; rate-limit per `yf.download(threads=True)` gotcha |
| `classify_flag` on 60-bar slice | ~10ms | CPU-bound; cheap (per Phase 1 measurements in chart-pattern flag-v1 phase notes) |
| `render_chart` (mplfinance + overlay) | ~150-200ms | CPU+IO-bound; PNG write to staging dir |
| **Total per ticker** | **~1.2s typical, ~0.3s cached** | |

**Total wall-time budget:**

| Scope size | Cold-fetch wall time | Warm-cache wall time |
|---|---|---|
| 5 tickers (current) | ~6s | ~1.5s |
| 10 tickers (typical post-V2) | ~12s | ~3s |
| 13 tickers (typical post-V2) | ~16s | ~4s |
| 21 tickers (max post-V2) | ~25s | ~6s |

**Acceptance threshold (Codex R2 Major 2 — operational response defined):** total chart-step wall time targets are 60s typical / 120s maximum. The estimated max (25s for 21 tickers cold-fetch) is well under. **Behavior on threshold exceed:**

- Wall time > 60s → `_step_charts` emits a WARNING log line: `chart-step wall-time exceeded soft budget: <actual>s > 60s; scope=<count> tickers; consider reducing chart_top_n_watch`. Pipeline continues normally. Monitoring surface for operator (visible in pipeline-run logs).
- Wall time > 120s → `_step_charts` emits an ERROR log line: `chart-step wall-time exceeded hard budget: <actual>s > 120s; scope=<count> tickers`. Pipeline continues normally (does NOT fail; the work is already done). Operator-actionable signal (visible in pipeline-run logs); implies a tuning dispatch is needed.
- The existing `pipeline_runs.charts_status` field is unchanged — `'ok'` regardless of wall-time overrun. Time overrun is a soft signal, not a chart-step failure.

**Test instrumentation (Codex R2 Minor 1):** wall-time assertions in unit tests are flaky across machines / network states. The integration test instead asserts on:

- A *log capture* test that `_step_charts` emits the WARNING/ERROR log line when given a synthetic-slow stub of `fetcher.get` that exceeds the threshold (deterministic; no real timing dependency).
- A separate benchmark-only test (skipped in `-m "not slow"` fast suite; runs on demand via `-m slow` or a dedicated benchmark CI job) that measures real wall time on a representative scope and asserts the typical case is under 60s. This is the actual regression-detection mechanism for performance.

**Timer-boundary specification (Codex R3 Minor 2):** the writing-plans phase MUST specify the exact timer interval. Recommendation: timer starts at `_step_charts` entry (before any DB read for tier composition); timer ends after the last `lease.fenced_write` for chart_status updates. This boundary covers all chart-step work (tier composition + ticker iteration + per-ticker fetch/classify/render/persist) and excludes pipeline-step machinery outside `_step_charts`. The metric is `chart_step_wall_time_seconds`. Document the boundary in the WARNING/ERROR log line text so log readers know what the number represents.

**Sub-phase timing attribution (Codex R4 Minor 1 — informational; deferred):** the end-to-end metric does NOT distinguish whether overrun cost came from tier composition queries, fetch latency, classifier/render work, or fenced writes. If a future tuning effort requires attribution, sub-phase timers (e.g., `tier_composition_ms`, `fetch_total_ms`, `classify_total_ms`, `render_total_ms`, `persist_total_ms`) can be added in a follow-up. Not in V1 scope — the end-to-end signal is sufficient to detect overrun; per-ticker fetch latency dominates the cost (~80% of expected wall-time per the cost breakdown above), so attribution is unlikely to surprise.

The hard wall-time assertion in standard CI is rejected; instrumentation + log capture is the deterministic substitute.

**Future hardening (deferred to post-V1):** if log-driven monitoring proves insufficient, a follow-up dispatch can introduce TIER-BASED SHEDDING — when wall time is projected to exceed the soft budget mid-step, skip remaining `tag_aware_top_n` tickers (lowest priority); mark them with a new `chart_status='skipped_for_budget'`. Tier-based shedding is NOT in V1 scope (adds complexity, requires forward-projecting wall time mid-step, requires new chart_status enum value).

**V1 trade-off explicitly acknowledged (Codex R3 Major 1):** V1 prioritizes A+/open_position correctness + tag-aware coverage over wall-time CONTROL. The thresholds are MONITORING signals, not control mechanisms. A pathologically slow yfinance state (e.g., rate-limit hold, network outage, per-ticker timeout) can drag chart-step wall time well past 120s while `pipeline_runs.charts_status` still completes as `'ok'`. **This is intentional for V1** — operator scale (1 pipeline/day, ~10-21 tickers) makes the slowdown tolerable, and avoiding tier-shedding preserves the correctness/coverage guarantees that motivated this dispatch. **Operator escalation path:** the ERROR log line on >120s overrun is the trigger. If the operator sees repeated ERROR-level overruns in pipeline-run logs, the response is to dispatch a follow-up: either (a) reduce `chart_top_n_watch` from 10 → 5 to cut the watchlist tier in half, or (b) implement tier-based shedding per the deferred-hardening note above.

**`pipeline_runs.charts_status` observability (Codex R3 Major 2):** the schema-level `charts_status` field continues to mean "chart-step completed without per-ticker rendering failure" (`'ok'`/`'failed'`/`'skipped'`); it does NOT carry budget-compliance state in V1. Downstream consumers querying `charts_status` cannot distinguish "completed in 5s" from "completed in 600s." **This is a deliberate V1 limitation** — adding a persisted budget-status column (e.g., `charts_wall_time_ms` integer or `charts_budget_status` enum) would require schema migration 0012 + write-path threading + consumer audit. For V1 personal-use scale, log-only health is acceptable. **Future V2 hardening:** if the operator builds an alerting layer or external monitoring, a follow-up migration can add `pipeline_runs.charts_wall_time_ms` as a queryable signal. NOT in this spec.

**Per CLAUDE.md gotchas:** rate-limit issues arise from `yf.download(threads=True)` (forbidden) and concurrency on `Ticker.history()` (bounded by app-level executor); sequential-fetch latency is the only observable cost. Acceptable.

**Classifier + PNG cost:** each chart also runs `classify_flag` (heuristic pattern detection; ~0.1-0.5 s/chart, CPU-bound) and saves a PNG (~0.1-0.3 s I/O). Scaling to 10-13 charts adds ~1-8 s beyond yfinance, for a total `_step_charts` wall-time budget of ~15-25 s typical (up from ~7-12 s current). Within single-session pipeline tolerance; no new rate limits apply. Accept.

**V1 unified scope decision (Codex R1 Major 5 — accepted with rationale):** all three tiers feed BOTH PNG generation AND classifier processing. Held positions get classifier output even though flag patterns rarely apply to already-running setups. Justification: classifier is cheap (~10ms/ticker); produces consistent per-ticker output across the chart-scope set; defensive against future patterns (e.g., breakdown patterns) that ARE applicable to held positions. **V2 may split scopes** (e.g., classifier scope = aplus + tag_aware; chart scope = aplus + open_position + tag_aware) if classifier compute grows or new patterns demand differential treatment. V1 keeps unified scope for simplicity.

**Crowding-out concern (Codex R1 Major 5):** A+ + open_position tiers have unbounded slot allocation (subject to hard caps); tag_aware_top_n has fixed N=10. In high-utilization state (e.g., 6 open positions + 5 A+ candidates) total scope = 21 max, with tag_aware preserved at 10. The discovery tier (tag_aware_top_n) does NOT shrink when other tiers grow; the spec preserves discovery budget by construction. Tradeoff accepted: chart-scope total can grow to 21 max (operator's yfinance cost); discovery coverage stays at 10 regardless.

**Disk space:** each PNG is ~50-200 KB. Doubling chart count adds ~5-10 MB per pipeline session. Negligible vs `exports/` retention budget (90 days × 1 run/day × ~10 MB ≈ 900 MB; retention sweep already exists).

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

**Pre-migration schema inventory (implementer requirement):** Verify `pipeline_chart_targets` has no additional indexes, triggers, or views beyond `idx_pipeline_chart_targets_run` before executing the migration. Run:
```sql
SELECT name, type FROM sqlite_master
WHERE type IN ('index', 'trigger', 'view')
  AND tbl_name = 'pipeline_chart_targets';
```
Expected result: exactly one row — `idx_pipeline_chart_targets_run` / index. Migration 0006 created only that index; no triggers or views were added per repo audit. If unexpected objects are present, recreate them in the migration before the DROP TABLE step.

**Schema-objects inventory verification (Codex R1 Major 6):** before applying the migration, the writing-plans phase MUST verify the current `pipeline_chart_targets` schema state matches the assumed baseline. Specifically:

- Run `SELECT name, sql FROM sqlite_master WHERE tbl_name = 'pipeline_chart_targets'` against a current production-shape DB. Expected output: 1 table definition + 1 index (`idx_pipeline_chart_targets_run`). NO triggers, NO additional indexes, NO views.
- If the inventory diverges from the assumed baseline (e.g., a side-migration added a trigger or another index in 0007-0010 that this spec missed), the migration as drafted would silently lose those objects on DROP TABLE. Before migration runs in production, the writing-plans phase must update the migration SQL to recreate ALL objects discovered in the inventory.
- Verified at brief-drafting time (orchestrator inspection of `swing/data/migrations/0007_*.sql` through `0010_*.sql` shows none touch `pipeline_chart_targets`); but the writing-plans phase MUST reconfirm against the actual production DB schema before approving the migration.
- The migration test (per §E) MUST assert post-migration that the same set of indexes/triggers exists as pre-migration.

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
    # ORDER BY adds `id DESC` tiebreaker (Codex R1 Minor 1) — defends
    # against second-precision finished_ts collisions on rapid runs.
    row = conn.execute(
        """SELECT id, finished_ts, data_asof_date, charts_status, evaluation_run_id
           FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC, id DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        return None
    # Construct by named arg, not positional unpack (Codex R1 Minor 2)
    # — defensive against future SELECT column-order drift.
    run_id, finished_ts, data_asof_date, charts_status, evaluation_run_id = row
    return PipelineRunBinding(
        run_id=run_id,
        finished_ts=finished_ts,
        data_asof_date=data_asof_date,
        charts_status=charts_status,
        evaluation_run_id=evaluation_run_id,
    )
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

### Binding scope definition (Codex R1 Major 1)

**Scope of a single binding: ONE binding per HTTP request handler.** The race the binding closes is the intra-request race between (a) the caller's SELECT for `data_asof_date` (used to construct chart URLs) and (b) the resolver's internal SELECT for the latest run's chart_targets — these were two reads against `pipeline_runs` that could see different runs if a new run completed between them.

**What the binding does NOT close:**

- **Inter-request races** (different HTTP requests fired by the same operator from the same dashboard): a `/watchlist/{ticker}/expand` request at T0 binds to runN; an `/trades/open/{trade_id}/expand` request at T1>T0 may bind to runN+1 if a new pipeline run completed between T0 and T1. The operator may see `data_asof_date` of runN on one expanded row and runN+1 on another — visible only if the operator notices the date in the chart URL or waits for the dashboard's `stale_banner` to update. Acceptable; closing this would require server-side cross-request session pinning (out-of-scope for this dispatch).
- **Intra-request multi-builder races IF a future request handler invokes multiple chart_scope.resolve_chart_scope calls without sharing the binding.** The current 3 caller sites each call resolve_chart_scope at most once per request. If a future surface composes multiple chart-scope resolutions in one request handler (e.g., a future "all open positions chart grid" page that resolves N tickers in one render), it MUST pin the binding ONCE at the top of the handler and pass it down to all resolve_chart_scope invocations. **Writing-plans phase MUST add a docstring/comment on `resolve_chart_scope` explicitly stating the "one binding per request handler" contract**, and reviewers should reject any future caller that violates it.

The current 3 caller sites are leaf surfaces (one resolve_chart_scope call per request); the binding contract is sufficient. Future surfaces that compose multiple resolutions need to honor the contract.

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

**Caller-site contract enforcement (Codex R1 Minor 4 + R2 Minor 2 — refined):** the writing-plans phase MUST:

- Add an explicit docstring on `resolve_chart_scope` stating: "MUST be called with a `binding` pinned at the request handler entry via `latest_completed_pipeline_run`. Multiple calls within the same handler MUST share the same binding instance to honor the race-tightening contract."
- Add the binding-scope contract to project's code-review checklist or `CONTRIBUTING.md` if one exists (per project-context: code review is mandatory; orchestrator-facing).
- The earlier proposal of an automated grep-pin on `resolve_chart_scope(` call sites is REJECTED (Codex R2 Minor 2): such tests are brittle against harmless refactors (e.g., wrapper helpers, code moves, test-only call sites) and fail noisily without catching real contract violations.

The contract is enforceable by docstring + review, not by test count. Code review remains the actual enforcement mechanism (per orchestrator-context: adversarial review on every code-shipping session is mandatory).

**Technical guardrail deferral (Codex R3 Minor 1 — accepted with rationale):** for V1, the binding-scope contract is process-enforced (docstring + review), not technically enforced (e.g., binding sentinel attributes, restrictive caller patterns). All current 3 callers are leaf surfaces with one resolve_chart_scope call per request; there are no multi-surface request patterns to constrain technically. **If a future surface composes multiple resolve_chart_scope calls in one handler**, the writing-plans phase for THAT surface MUST add explicit tests asserting the binding is shared across calls. Until that surface emerges, the technical guardrail is YAGNI. Adding it preemptively would create constraint code without a falsifiable test target.

**Reviewer-checklist hardening (Codex R4 Minor 2):** the writing-plans phase MUST include in its done-criteria checklist an explicit reviewer item: "Inspect all new `resolve_chart_scope` call sites; confirm each calls `latest_completed_pipeline_run` ONCE at request handler entry and passes the resulting binding through any downstream multi-call surface." This converts the social/process enforcement into an explicit code-review checklist line, reducing documentation-to-implementation drift risk on future web-surface changes.

### Operator-facing copy update

`CHART_REASON_MESSAGES["out-of-scope"]` in `swing/web/chart_scope.py` currently reads something like "No chart available — [ticker] is outside the current chart-scope set (A+ names + top near-trigger watchlist)." This copy becomes false after migration 0011 because the scope now also includes open positions and tag-aware top-10. The implementer MUST update this string to reflect the three-tier model, e.g.: "No chart available — [ticker] is outside the current chart-scope set (A+ candidates, open positions, and tag-aware watchlist top-10)." **Test requirement:** add a test assertion on the updated message text in `tests/web/test_chart_scope.py`.

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

**Operator signing:** orchestrator drafted; operator approved each design section (§A through §F); orchestrator self-review pass cleared placeholders, internal consistency, scope, ambiguity; **adversarial Codex review completed in 4 rounds → NO_NEW_CRITICAL_MAJOR** (all 11 majors across R1-R3 resolved via spec edits + 9 minors resolved or accepted-with-rationale per V1 scope); pending operator final approval + writing-plans dispatch.
