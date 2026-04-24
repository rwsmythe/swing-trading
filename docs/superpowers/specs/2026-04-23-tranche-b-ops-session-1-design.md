# Tranche B-ops session 1 — design

**Date:** 2026-04-23
**Status:** reviewed (adversarial review complete; awaiting user approval)
**Brief:** `docs/tranche-b-ops-brief.md`
**Audience:** subsequent Tranche B-ops implementer sessions (2+) and the developer

---

## Mission

Absorb Bugs 3a / 4 / 5 / 6 from `docs/Bugs.txt` plus one newly-flagged stop-form field-preservation gap into a bounded, commit-level implementation plan for the Operational Trader-Facing branch. This session is design only — no `swing/` code changes. Downstream sessions execute the seven tasks in §7.

## Context

- **Governing strategy:** `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`, §VI (Operational Trader-Facing). Near-term priority stack: this spec touches B2 (trigger/setup completeness — Bug 5), B3 (risk display — Bug 6), B4 (journaling-input schema — Bug 3a), B7 (chart-unavailable UX — Bug 4).
- **Binding clarifications:** `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` §1 (minimum viable governance) and the Anti-patterns list — "registry maximalism," "strategy inflation," "infrastructure displacement" all applicable as guardrails against over-abstracting the rationale taxonomy into a framework.
- **Tranche A flags carried over:** Bug 3 was split into 3a (this session, rationale taxonomy) and 3b (shipped Tranche A, `StopAdjustRequest.notes`). The stop-form field-preservation gap was surfaced during Tranche A work and folded into this session since the stop-adjust form was already in scope.
- **Bugs covered:** `docs/Bugs.txt` items 3, 4, 5, 6. Items 1 and 2 shipped in Tranche A.

---

## 1. Bug 5 — A+ "Stop Limit" label (trigger/setup completeness, V2.1 §VI.B.B2)

### Problem

[swing/recommendations/build.py:32](../../../swing/recommendations/build.py#L32) formats `DailyRecommendation.action_text` as:

```python
f"Buy-stop limit ${entry:.2f} · {shares} sh · ${risk_dollars:.0f} risk"
```

A "buy-stop limit" order at any real broker takes *two* prices — the stop (trigger) and the limit (max-fill). This system persists only one price (`entry_target` / `pivot`). The label is therefore literally wrong: it's a *buy-stop* (market-on-stop), and the operator supplies a broker-side limit offset themselves at order-entry time.

### Decision

Rename the label. Drop the word `limit`.

```python
f"Buy-stop ${entry:.2f} · {shares} sh · ${risk_dollars:.0f} risk"
```

### Rationale

- The system does not own the limit price; the operator does, at the broker.
- Adding a `limit_offset_bps` config to synthesize a second price would bake a broker-workflow assumption into persisted recommendation data. Rejected as unneeded abstraction.
- The `Buy-stop` string matches what the tool is actually telling the operator to do: set a stop order at the pivot; limit handling is out-of-band.

### Scope

- One edit in `_format_action()`.
- Snapshot-matching updates in tests that assert substrings like `"Buy-stop limit"`. Per current grep: 6 files under `tests/` assert variations; four of those already use the shorter `"Buy-stop"` form and pass under either label.

---

## 2. Bug 6 — Total risk exposure display (risk support, V2.1 §VI.B.B3)

### Problem

No UI surface shows the sum of in-flight risk across open positions. The operator has to mentally add per-position risk from the open-positions table to know current book exposure.

### Decision

**Definition** — a single number, computed at render time:

```
total_current_risk_dollars = Σ max(0, shares_remaining × (entry_price − current_stop))
total_current_risk_pct     = total_current_risk_dollars / realized_equity  (if realized_equity > 0)
```

- `shares_remaining` (post-partials), not `initial_shares`. Partials have already realized their P&L on the sold portion; remaining shares are what the stop still protects.
- `max(0, ...)` per-trade: positions whose stop has trailed at-or-above entry contribute $0. They represent locked-in non-loss, not risk.
- No per-trade flooring on the `shares_remaining` multiplication (all trades in `list_open_trades` have `shares_remaining > 0` by invariant; if they didn't, they'd be closed).

**Denominator — deliberate choice of realized equity.** `realized_equity` here is `current_equity(...)` from `swing/trades/equity.py` = `starting_equity + Σ realized_pnl + net_cash_movements`. It **excludes unrealized P&L from open positions**. This matches the project's existing convention: the per-trade entry-form sizing hint ("~$60 risk = 1.20%") uses the same `current_equity` denominator, so Open-risk's percent is directly comparable to the per-trade sizing percent. Known limitation: when open positions have significant unrealized gains, true *book* equity is higher, and Open-risk-pct will over-state risk against true book size. This is accepted for this session to preserve one-number-one-meaning cross-UI consistency. A future session may introduce a book-equity helper (requires live prices in the risk math) and add a second "book %" reading; §8 flags this as a follow-up if operator analytics demands it.

**Display** — new tile in the existing status strip. Label: `Open risk`. Value: `$XXX (X.XX%)`. Rationale line: `N positions`. Tile order: Weather → Account → **Open risk** → Last pipeline.

**Edge cases:**
- Zero open trades: `$0 (0.00%)`, rationale `0 positions`.
- Equity ≤ 0 (starting over after drawdown): display `$XXX` only, percent shown as `—`.
- All open positions trailed past breakeven: `$0 (0.00%)`, rationale `N positions (all above breakeven)`.

### Rationale

- **Why one number not two:** initial-risk-sum is historical — it was fixed at entry time and doesn't change. It belongs in the trade record, not in a live-decision surface. Current-risk-to-stop is the actionable number; it answers "if every stop fires tomorrow, how much book equity do I give back from here?" Minimum-viable governance (rebuttal-response §1) argues against forcing two numbers onto the operator when one drives decisions.
- **Why a new tile, not extending Account:** Open-risk is a distinct decision axis from account size. Mixing them into one tile makes both harder to scan.
- **Why no cap-comparison styling in this session:** `cfg.risk.max_risk_pct` is per-trade only; no book-level cap exists. Adding one requires a new config field + threshold choice — scope-expansion. Flagged as follow-up in §8.

### Scope

- `swing/trades/equity.py` gains pure helper `total_current_risk(trades, exits) -> (dollars: float, contributing_count: int, all_above_breakeven: bool)`. The helper does NOT compute percent — it has no access to equity. Percent is computed in `build_dashboard` where `current_equity` is already in scope.
- `swing/web/view_models/dashboard.py` `StatusStripVM` gains four fields: `open_risk_dollars: float`, `open_risk_pct: float | None`, `open_risk_position_count: int`, `open_risk_all_above_breakeven: bool`.
- `swing/web/templates/partials/status_strip.html.j2` adds the tile between `#account-tile` and `#pipeline-tile`.
- `build_dashboard` computes risk using already-loaded `open_trades` + `exits_for_trade` data (no new I/O); computes percent as `dollars / realized_equity if realized_equity > 0 else None`.

---

## 3. Bug 3a — Rationale taxonomy (journaling input, V2.1 §VI.B.B4)

### Problem

Entry, stop-adjust, and exit trade-action forms accept `rationale` as free text. Free-text rationale is:
- unsearchable in downstream journaling queries;
- unanalyzable for future operator-behavior research (V2.1 §V.D candidate study: "validate one operator-facing ranking rationale field against actual recommendation quality");
- asymmetric with the existing structured `ExitReason` enum, which suggests closed-list was always the intent but hadn't been extended to the other two actions.

Bug 3 was originally reported as "Rationale boxes should be drop-downs with defined statements"; this spec is the design response.

### Decision — framing

Each trade-action carries two fields now: **`rationale`** (structured, closed list) and **`notes`** (free-form context). Database columns stay `TEXT`; the enum is a Python-side constraint enforced at the service, form, and CLI layers. **No migration.**

Existing `trade_events.rationale` rows containing free-text continue to render as-is in the journal. New events write canonical enum values. The display layer shows a friendly label when the stored string matches an enum value and renders the raw string otherwise. This is an explicit non-migration; §8 records the deferral of backfill.

### Decision — entry rationale

New Python enum `EntryRationale` in `swing/trades/entry.py`:

| Value | Display label | When to use | Provenance |
|---|---|---|---|
| `aplus-setup` | A+ setup (today's decision) | Ticker was in today's `today_decision` recommendations | Repo: `candidate.bucket == 'aplus'`, `recommendation == 'today_decision'` |
| `near-trigger-breakout` | Near-trigger breakout | Watchlist ticker crossed pivot this session | Repo: `recommendation == 'near_trigger'` + breakout verb |
| `vcp-breakout` | VCP breakout | Stage-2 VCP pattern triggered (operator judgment) | Repo: `candidate.criteria` layer `'vcp'` |
| `pivot-breakout` | Pivot breakout (non-VCP) | Base breakout without VCP qualification | Deliberate expansion: base-breakout is a Minervini/operator concept not currently enumerated in the repo's string set |
| `post-earnings-continuation` | Post-earnings gap continuation | Gap-up on earnings, trend-template intact | Deliberate expansion: operator-vocabulary expansion, not currently in repo strings |
| `relative-strength` | Relative strength leadership | RS-rank driven, weaker setup tolerated | Deliberate expansion: Minervini/IBD concept in `reference/methodology/`, not currently in repo strings |
| `other` | Other (see notes) | Anything not captured above | Standard escape-hatch |

6 options + `other`. The `aplus-setup` value is distinct from the pattern labels because it describes system-provenance, not what the operator saw on the chart — an operator can click A+ without independently judging VCP-ness.

**On "draw from existing repo vocabulary"** — the brief's phrasing (§2 item 1) is "Draw options from existing repo vocabulary." The first three entries (`aplus-setup`, `near-trigger-breakout`, `vcp-breakout`) map to concrete repo strings. The remaining three (`pivot-breakout`, `post-earnings-continuation`, `relative-strength`) are deliberate expansions — operator trigger vocabulary that is *not* currently a repo string but is the actual way the operator describes their decision. Collapsing these to `other` would force every post-earnings and RS-driven entry to be `other`, defeating the taxonomy's analytic value. The expansion is minimum-viable (six concrete options, not a generic framework) and operator-explainable (each label is meaningful on first read). Each expansion is explicitly labeled "Deliberate expansion" in the table above so a future audit can distinguish repo-literal values from the operator-vocabulary expansions.

### Decision — stop-adjust rationale

New Python enum `StopAdjustRationale` in `swing/trades/stop_adjust.py`:

| Value | Display label | When to use | Provenance |
|---|---|---|---|
| `breakeven` | Move to breakeven (system advisory) | Follows `suggest_breakeven` | Repo: `AdvisorySuggestion.rule == 'breakeven'` |
| `trail-10ma` | Trail to 10MA (system advisory) | Follows `suggest_trail_ma(10MA)` | Repo: `AdvisorySuggestion.rule == 'trail_10ma'` |
| `trail-20ma` | Trail to 20MA (system advisory) | Follows `suggest_trail_ma(20MA)` | Repo: `AdvisorySuggestion.rule == 'trail_20ma'` |
| `weather-tighten` | Tighten on weather | Follows `suggest_weather_action` caution/bearish | Repo: `AdvisorySuggestion.rule == 'weather'` + tighten verb |
| `manual-trail` | Manual trail (operator judgment) | Operator-driven, no system advisory | Deliberate expansion: covers the "operator-led, no advisory fired" case |
| `news` | News-driven tighten | Company/sector news prompted the tighten | Deliberate expansion: operator-vocabulary concept, not currently a repo string |
| `other` | Other (see notes) | Anything not captured above | Standard escape-hatch |

6 options + `other`. The first four values are direct rewrites of advisory rule names; `manual-trail` and `news` are deliberate operator-vocabulary expansions for cases where no system advisory drives the adjustment. `time-stop` is omitted — it's an *exit* signal in the advisory engine, not a stop-adjust signal. `trail-50ma` is also omitted since the 50MA advisory (`suggest_exit_close_below_ma(50MA)`) is an exit signal per Minervini — if an operator chooses to merely tighten a stop near the 50MA instead of exiting, `manual-trail` captures that judgment call.

### Decision — exit rationale: reuse `ExitReason`

Exit already has a required structured dropdown (`ExitReason`). A parallel rationale taxonomy would be redundant.

- **Drop** the separate `rationale` input from `trade_exit_form.html.j2` and from `trade exit` CLI.
- **In the exit route handler and CLI command**, write `req.reason.value` into `trade_events.rationale` automatically.
- **Keep** `notes` for free-form context.

This simplifies the exit form — one less required field — and removes an ergonomic foot-gun (two required "why" fields, one structured, one free-text, confusing to fill).

**Known limitation (flagged for later revisit in §8):** `ExitReason` is semantically "exit-event shape" (stop-hit / target / manual / time-stop / weather / partial / other), not "operator's decision rationale." Writing `req.reason.value` into `trade_events.rationale` means values like `partial` (which describes partial-size, not *why*) and `manual` (which is a null-value rationale — "I exited because I exited") will appear as rationale rows. This is an accepted cost of not designing a separate exit-rationale taxonomy in minimum-viable scope. The alternative — a third enum `ExitRationale` distinct from `ExitReason` (e.g., `target-reached`, `setup-broken`, `weather-deteriorating`, `gap-risk`) — is tabled in §8 "items flagged but not scoped" until journaling analysis produces evidence that the `reason=partial|manual` rows materially corrupt downstream queries. If that evidence emerges, a future session designs the exit-rationale enum and backfills if warranted.

### Decision — `other` ergonomics

On all three forms, selecting `other` as the rationale makes `notes` a required (form-level validated) field. Rationale: a structured dropdown loses its data value if `other` can be clicked without any explanation. The validation lives in the route handler, not in the dataclass — `notes` remains `Optional` at the data-model layer to preserve compatibility with CLI paths that set the enum to a non-`other` value without notes.

### Rationale — taxonomy sizing

Seven options per taxonomy (6 canonical + `other`). Rebuttal-response §1 warns against registry maximalism; seven is deliberately under the cognitive threshold where a dropdown becomes a scrolling list, while covering the operator's actual trigger vocabulary drawn from Minervini Trend-Template + VCP + the system's own advisory engine. Adding an eighth or ninth value requires evidence from journal data that current values over-collapse meaningful distinctions.

### Non-migration statement

No SQL migration is added in the Bug 3a tasks. Existing `trade_events.rationale` rows stay as stored. Queries that group by rationale will see both old free-text values and new enum values coexisting; this is accepted cost for avoiding a backfill + data-reinterpretation exercise. A future session may backfill if journaling analysis demands it; that decision is out of scope here.

---

## 4. Bug 4 — Chart-unavailable reason (error/degradation UX, V2.1 §VI.B.B7)

### Problem

`swing/web/templates/partials/watchlist_expanded.html.j2` uses `<img onerror>` JS to hide the chart image and show a static "Chart unavailable." div when the PNG 404s. The placeholder gives no reason, and the client-side `onerror` fires on any image-load failure — including transient static-mount issues that should be distinguishable from an intentional absence.

### Decision — enumerate reasons server-side

Six possible chart-availability states, all resolvable at VM-build time:

| `chart_reason` value | Condition | Rendered message |
|---|---|---|
| `None` | PNG exists at `{charts_dir}/{data_asof}/{ticker}.png` | (no placeholder — render `<img>`) |
| `no-run` | No completed pipeline run exists whose chart step wrote a PNG for this session | `Chart unavailable — no pipeline run yet for this session.` |
| `engine-missing` | Latest completed `pipeline_runs.charts_status == 'skipped'` | `Chart unavailable — charting engine (mplfinance) not installed on this host.` |
| `pipeline-failed` | Latest completed `pipeline_runs.charts_status == 'failed'` | `Chart unavailable — last pipeline run's chart step failed. Re-run when ready.` |
| `out-of-scope` | Ticker not in this run's chart scope (not A+ and not in `chart_top_n_watch` nearest-pivot watchlist) | `Chart unavailable — this ticker isn't in today's charting scope (A+ names + top near-trigger watchlist).` |
| `insufficient-data` | In scope, but the PNG was not produced (fetcher error or `<MIN_BARS` bars) | `Chart unavailable — data too thin or fetch error for this ticker at last pipeline run.` |

### Decision — server-authoritative render

- `WatchlistExpandedVM` gains `chart_reason: str | None` and `chart_reason_message: str | None`.
- `build_watchlist_expanded` resolves the state by reading the latest completed `pipeline_runs` row (`charts_status`, `run_id`, `data_asof_date`), determining scope against **persisted run artifacts** (see "Scope drift note" below), and probing for the PNG file.
- `watchlist_expanded.html.j2` drops the `<img onerror>` JS and renders *either* `<img>` (if `chart_reason is None`) *or* `<div class="chart-unavailable">{{ chart_reason_message }}</div>` — not both.

### Scope resolver — approximate match to `_step_charts`, with documented drift

The pipeline's actual chart-step target set at run time T1 (per `swing/pipeline/runner.py:_step_charts`) is:

- **A+ set:** `fetch_candidates_for_run(conn, eval_run_id)` filtered by `bucket == 'aplus'`. Persisted per run, deterministic to reconstruct later.
- **Near-by-proximity set:** `list_active_watchlist(conn)` at T1, filtered to rows with both `entry_target` and `last_close`, sorted by `abs((last_close − entry_target) / entry_target)`, truncated to `cfg.pipeline.chart_top_n_watch`. **This set is not persisted** — `daily_recommendations` stores `entry_target` but not the run-time `last_close`, so proximity ordering cannot be reconstructed from recommendation rows alone.

**Resolver implementation (mirrors `_step_charts` exactly, but against live state):**

```python
# A+ set: from persisted run artifacts (deterministic).
aplus_tickers = {c.ticker for c in fetch_candidates_for_run(conn, eval_run_id) if c.bucket == 'aplus'}

# Top-N near-by-proximity set: from LIVE watchlist state — approximate reconstruction.
watchlist = list_active_watchlist(conn)
near_by_proximity = sorted(
    [w for w in watchlist if w.entry_target and w.last_close],
    key=lambda w: abs((w.last_close - w.entry_target) / w.entry_target),
)[:cfg.pipeline.chart_top_n_watch]
top_n_tickers = {w.ticker for w in near_by_proximity}

ticker_in_scope = ticker in (aplus_tickers | top_n_tickers)
```

**Linking `eval_run_id` to the pipeline run — best-effort heuristic.** `pipeline_runs` does not store `eval_run_id`; there is no direct foreign key. The resolver uses this heuristic:

```sql
SELECT id FROM evaluation_runs
WHERE data_asof_date = :pipeline.data_asof_date
  AND run_ts <= :pipeline.finished_ts
ORDER BY run_ts DESC
LIMIT 1
```

This is *best-effort*, not authoritative. It identifies "the most recent evaluation for the pipeline's session date that existed at or before the pipeline's finish time." Why best-effort:

- `swing eval` (standalone CLI at `swing/cli.py:64`) writes to `evaluation_runs` without lease fencing. The pipeline's lease protects `pipeline_runs` mutations only.
- An operator can therefore run `swing eval` mid-pipeline — after the pipeline's own `_step_evaluate` completed but before `_step_charts` runs, OR after `_step_charts` but before `pipeline_runs.finished_ts` is written. In those edge cases the heuristic picks the standalone eval, not the pipeline's own eval, and the A+ set is wrong.
- In normal operation (one operator, one pipeline trigger per session, no mid-run CLI evals), the heuristic reliably returns the pipeline's own eval because the pipeline's `_step_evaluate` creates the most recent eval row for that `data_asof_date` before its chart step fires.

**Why not build a real linkage.** Adding `evaluation_run_id` as a column on `pipeline_runs` and wiring the pipeline orchestrator to write it would eliminate the race. That's a schema change (migration) plus pipeline-layer work; out of scope for Tranche B-ops session 1. §8 flags it as a follow-up alongside the per-run chart-target list item — both would land in the same future pipeline-linkage session.

If the heuristic query returns no row (migration anomaly, or pipeline completed without an eval step), the resolver falls back to `chart_reason='insufficient-data'` for all probed tickers — collapsing toward the data-quality bucket, not operator-misleading labels. The race case (standalone eval mid-pipeline) does NOT fall back this way — it silently picks the wrong eval. Recorded in the drift acknowledgment below.

Replacing the round-2 draft's naive `SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1` (which would pick a post-pipeline standalone eval — a different correctness bug found in round 3).

**Drift acknowledgment.** Scope resolution is *best-effort*, not deterministic. Two distinct sources of drift:

**A. A+ set — standalone-eval race.** If an operator runs `swing eval` between the pipeline's `_step_evaluate` and `pipeline.finished_ts` (a real possibility — `evaluation_runs` is not lease-fenced), the eval-linkage heuristic picks the standalone eval instead of the pipeline's own eval. The resolver's A+ set then differs from what `_step_charts` charted. Affects *any* A+ ticker, not just boundary cases. Mitigations: (a) operators running one pipeline per session in normal flow do not hit this; (b) the wrong-but-plausible A+ set still produces operator-safe messaging (worst case: `out-of-scope` when it should be `insufficient-data`, or vice-versa — both communicate "no chart here"); (c) durably fixed by persisting `evaluation_run_id` on `pipeline_runs` in a future pipeline-linkage session (§8).

**B. Near-by-proximity set — watchlist churn + price movement.** Because the top-N set is recomputed from live watchlist state at render time:

- **Watchlist row added after T1**: resolver sees it at T2, may compute it in top-N; pipeline never charted it. Bounded to the top-N boundary.
- **Price movement between T1 and T2 flips the top-N boundary**: bounded to tickers near the `chart_top_n_watch` rank threshold.
- **Watchlist row removed after T1**: the expand action can't be triggered (no active watchlist row to click), so this drift mode is not observable.

Both drift sources produce bounded, non-dangerous mislabels — the operator message is still informational-only and the next step (read an external chart, re-run the pipeline) is unchanged. The `insufficient-data` message text ("data too thin or fetch error at last pipeline run") intentionally reads reasonably for either the genuine data-thin case or a drift-induced mislabel. The spec accepts this rather than scope-expand into a pipeline-schema fix; §8 "Pipeline-linkage bundle" records the deferred pipeline-layer work that would eliminate both drift sources.

### Rationale

- Server-side resolution gives an accurate, specific message; client-side `onerror` is a silent blanket over any failure.
- The five non-`None` states are all derivable from data the VM already has or can cheaply read (one indexed SQL lookup against `pipeline_runs` + a filesystem stat).
- Removing the `onerror` handler closes a small lying-surface: transient static-mount permission errors (which should page someone) currently look identical to intentional absence.

### Deferred resolution — §8

Splitting `insufficient-data` into `fetcher-failed` vs `too-few-bars` would require pipeline-layer per-ticker chart-status persistence (today `_step_charts` silently `continue`s on fetcher error and silently skips on `len(df) < MIN_BARS`). That's a pipeline-structural change; collapsing the two here keeps the session's scope in the web layer.

---

## 5. Stop-form field preservation

### Problem

`TradeEntryFormVM` preserves typed `rationale`, `notes`, `input_shares`, and `force` across the soft-warn/duplicate/drift re-render path. `TradeStopFormVM` has no equivalent preservation. On `StopRegressionError` 400, the user loses their typed `new_stop`, `rationale`, and `notes`. Additionally, the web stop form has no `force` control — the only way to submit a regression-intentional stop (e.g., fixing an over-tight initial stop) is to drop to CLI.

### Decision

Mirror the `TradeEntryFormVM` preservation pattern exactly — no new abstraction.

```python
@dataclass(frozen=True)
class TradeStopFormVM:
    trade: Trade
    current_stop: float
    suggested_stops: tuple[tuple[str, float], ...]
    # Preservation fields — populated from request on error re-render; defaults are the "clean form" case
    new_stop_input: float | None = None
    rationale: str = ""
    notes: str = ""
    force: bool = False
```

- The web stop-adjust POST route catches `StopRegressionError`, builds the VM populating preservation fields from the submitted form, and re-renders `trade_stop_form.html.j2` with the error banner.
- `trade_stop_form.html.j2` gains a `Force (override regression check)` checkbox. The operator tick-and-resubmit flow is: (1) submit without force → `StopRegressionError` → re-render with preserved values + banner; (2) operator ticks Force checkbox and submits again → route builds `StopAdjustRequest(force=True)` → `adjust_stop` no longer raises → success path runs as normal. Force is not auto-ticked by the re-render.
- Template preservation: `<input name="new_stop" value="{{ vm.new_stop_input if vm.new_stop_input is not none else vm.current_stop }}">`. Once T5 ships (stop-adjust rationale enum), the rationale `<select>` uses `{% if opt.value == vm.rationale %}selected{% endif %}`.

### Rationale

- Two VMs with similar preservation fields is not enough evidence for a shared `FormStatePreservation` helper. A shared abstraction at N=2 is premature; field sets differ subtly per action (entry has `input_shares`, stop has `new_stop_input`, exit would have `exit_price_input`). Rebuttal-response anti-pattern #3 (infrastructure displacement) applicable.
- Exposing `force` on the web form closes the "CLI-only for legitimate stop-regression" ergonomic gap that currently exists. Force is a deliberate operator choice; a checkbox surfaces it without making the default path less safe.
- **Scope clarification** — this is minimum-viable web parity with the existing CLI `--force` on `trade stop-adjust`, not the start of a generalized override-UX workstream (V2.1 §VI.B.B8, which is explicitly out of scope per the brief §2). No other force/override controls are introduced; no configuration of bypass thresholds; no audit-logging of override events beyond what `trade_events` already records.

### Out of scope for this session

`TradeExitFormVM` has the same latent preservation gap. No live bug report exists for it; the brief scopes preservation specifically to the stop form. §8 records exit-form parity as deferred.

---

## 6. Schema, template, VM, and CLI impact summary

### Schema impacts

**None.** No migrations in any task. The rationale enum is enforced Python-side; `trade_events.rationale` remains `TEXT`. Historical rows are left as stored.

### Template impacts

| Template | Change | Introduced in task |
|---|---|---|
| `partials/status_strip.html.j2` | Insert Open-risk tile between `#account-tile` and `#pipeline-tile` | T2 |
| `partials/watchlist_expanded.html.j2` | Drop `<img onerror>` JS; branch on `chart_reason` | T3 |
| `partials/trade_entry_form.html.j2` | `<textarea name="rationale">` → `<select name="rationale">`; `other` toggles `notes required` | T4 |
| `partials/trade_stop_form.html.j2` | Same textarea→select swap for `rationale`; add `<input type="checkbox" name="force">` | T5 (rationale), T7 (force + preservation bindings) |
| `partials/trade_exit_form.html.j2` | Remove `rationale` textarea row | T6 |

### VM impacts

| VM | Change | Task |
|---|---|---|
| `StatusStripVM` | +`open_risk_dollars`, `open_risk_pct`, `open_risk_position_count`, `open_risk_all_above_breakeven` | T2 |
| `WatchlistExpandedVM` | +`chart_reason`, `chart_reason_message` | T3 |
| `TradeEntryFormVM` | +`rationale_options: tuple[tuple[str, str], ...]` (enum value + display label pairs) | T4 |
| `TradeStopFormVM` | +`rationale_options`, `new_stop_input`, `rationale`, `notes`, `force` | T5 + T7 |
| `TradeExitFormVM` | Existing field removal documented in T6 (no field removal from the dataclass itself — the rationale was never a dataclass field; only the form input is dropped) | T6 |

### CLI impacts

| Command | Change | Task |
|---|---|---|
| `swing trade entry` | `--rationale` becomes `click.Choice(EntryRationale.values())`; `--rationale other` requires `--notes` | T4 |
| `swing trade stop-adjust` | `--rationale` becomes `click.Choice(StopAdjustRationale.values())`; `--rationale other` requires `--notes` | T5 |
| `swing trade exit` | `--rationale` **removed**; `--reason` (existing, already `click.Choice(ExitReason)`) is the structured cause; `--notes` (existing) is free-form | T6 |
| `swing trade advisory` | No change | — |

### Service-layer impacts

- `EntryRequest.rationale: str`, `StopAdjustRequest.rationale: str` stay typed as `str` (the enum's `.value`). A route/CLI-layer validator converts the input to an enum and back to `str` — the service sees clean strings. Avoids importing enum types into the dataclass.
- `record_exit`: when writing `trade_events.rationale`, replace the caller-supplied `rationale` with `req.reason.value`. This is a route-layer concern; it doesn't change `record_exit`'s signature.

---

## 7. Implementation task list

Seven commits, sized for single-session execution each. Conventional-commit messages shown.

### T1 — `fix(recommendations): rename "Buy-stop limit" to "Buy-stop"`

**Files:** `swing/recommendations/build.py`; any tests asserting `"Buy-stop limit"` substring.
**Acceptance:** grep finds no `"Buy-stop limit"` or `"Stop Limit"` in `swing/` except in a CHANGELOG-style note. Fast-suite green.
**Dependencies:** none.
**Est.:** 30 min.

### T2 — `feat(web): add Open-risk tile to status strip`

**Files:** `swing/trades/equity.py` (+`total_current_risk`); `swing/web/view_models/dashboard.py` (+4 `StatusStripVM` fields, compute in `build_dashboard`); `swing/web/templates/partials/status_strip.html.j2` (+tile); tests under `tests/trades/test_equity.py` and `tests/web/test_view_models/test_dashboard.py`.
**Acceptance:**
- Helper: `total_current_risk([], []) == (0.0, None_or_0_pct, 0, False)` for empty input.
- Helper: positions with `current_stop >= entry_price` contribute $0.
- Helper: `shares_remaining` respects partial exits.
- VM: `open_risk_pct` is `None` when `current_equity <= 0`.
- Template: tile renders order = Weather → Account → Open risk → Last pipeline.
- `—` displayed in percent slot when `open_risk_pct is None`.
**Dependencies:** none.
**Est.:** 1–2 hours.

### T3 — `feat(web): surface chart-unavailable reason server-side`

**Files:** `swing/web/view_models/watchlist.py` (+2 VM fields; +reason-resolver helper); `swing/web/templates/partials/watchlist_expanded.html.j2` (drop `onerror`; branch on reason); `swing/data/repos/pipeline.py` (verify/extend — surface `charts_status` on the latest-completed-run query; `run_id` and `data_asof_date` may already be exposed, check first); `swing/data/repos/candidates.py` (read-only use of `fetch_candidates_for_run`); `swing/data/repos/watchlist.py` (read-only use of `list_active_watchlist`); tests under `tests/web/test_view_models/test_watchlist.py` (+ `tests/data/test_repos_pipeline.py` only if a new query is added).

T3 is **not** a pure-web-template change — it couples (a) the VM layer, (b) the `pipeline_runs` repo (reading `charts_status`), and (c) scope reconstruction that mirrors `_step_charts` logic (A+ from persisted candidates; top-N-by-proximity from live watchlist state, documented as approximate). `eval_run_id` is derived via a constrained query — `SELECT id FROM evaluation_runs WHERE data_asof_date = :pipeline.data_asof_date AND run_ts <= :pipeline.finished_ts ORDER BY run_ts DESC LIMIT 1` — not the naive "latest evaluation_runs row" (which could pick a post-pipeline standalone eval, producing incorrect A+ context). See §4 "Linking eval_run_id to the pipeline run." Reviewers should expect three conceptual changes, not one.

**Acceptance:**
- Each of the 6 reason states renders the correct message when triggered by a fixture representing that condition.
- PNG exists + `pipeline_runs.charts_status == 'ok'` → `chart_reason is None`, `<img>` rendered.
- `<img onerror>` attribute is no longer present in the template.
- Scope-resolver computes `aplus_tickers ∪ top_n_near_by_proximity_tickers` exactly as `_step_charts` does: A+ from `fetch_candidates_for_run(conn, eval_run_id)` filtered by `bucket=='aplus'` where `eval_run_id` is resolved by the constrained query in §4 ("Linking `eval_run_id` to the pipeline run"); top-N from `list_active_watchlist(conn)` filtered to rows with `entry_target` and `last_close`, sorted by `abs((last_close - entry_target) / entry_target)`, truncated to `cfg.pipeline.chart_top_n_watch`.
- Fixture test for `eval_run_id` linkage: create pipeline run P1 with eval E1; create a later standalone eval E2 for the same `data_asof_date` after P1 finished; assert the resolver picks E1, not E2, and the A+ set matches E1's bucket.
- Resolver does NOT read `daily_recommendations` for scope (the near-by-proximity set cannot be reconstructed from persisted rec rows alone — they don't store `last_close`).
- Drift fixture test: construct a watchlist where rank at run-time would differ from rank at render-time (e.g., a row moves into top-N between renders). Assert the resolver returns the render-time answer and the test-doc comment names this as "approximate, bounded drift per §4."
- Commit-body note: "scope resolver mirrors `_step_charts`; approximate against live watchlist; drift bounded per spec §4."

**Dependencies:** none.
**Est.:** 3–4 hours (revised up from 2–3h for the resolver + drift test + the check/extend of `pipeline.py` repo).

### T4 — `feat(trades): constrain entry rationale to closed taxonomy`

**Files:** `swing/trades/entry.py` (+`EntryRationale` enum); `swing/web/view_models/trades.py` (`TradeEntryFormVM.rationale_options`, populate in `build_entry_form_vm`); `swing/web/templates/partials/trade_entry_form.html.j2` (textarea→select, `other` JS/HTML toggle); `swing/web/routes/trades.py` (validate enum, require notes when `other`); `swing/cli.py` (`click.Choice`, require `--notes` when `other`); tests across `tests/trades/`, `tests/web/`, `tests/cli/`.
**Acceptance:**
- Submitting any non-enum rationale value via route or CLI → 4xx / CLI error. No exceptions leak.
- `rationale=other` without notes → form-level 400 with "notes required when rationale=other".
- Seven options rendered in the dropdown, in spec order, with the display labels from §3.
- Existing historical rows with free-text rationale still render in the journal without raising.
**Dependencies:** none (independent of T5/T6/T7 for correctness, but ships coherently with T5+T6).
**Est.:** 2–3 hours.

### T5 — `feat(trades): constrain stop-adjust rationale to closed taxonomy`

**Files:** `swing/trades/stop_adjust.py` (+`StopAdjustRationale` enum); `swing/web/view_models/trades.py` (`TradeStopFormVM.rationale_options`); `swing/web/templates/partials/trade_stop_form.html.j2` (textarea→select); `swing/web/routes/trades.py`; `swing/cli.py`; tests mirrored from T4.
**Acceptance:** same shape as T4.
**Dependencies:** none (but T7 depends on T5 shipping).
**Est.:** 2–3 hours.

### T6 — `refactor(trades): derive exit rationale from reason; drop separate field`

**Files:** `swing/web/templates/partials/trade_exit_form.html.j2` (remove rationale textarea); `swing/web/routes/trades.py` (on exit POST, set rationale = `req.reason.value` before the service call); `swing/cli.py` (`trade exit`: remove `--rationale` option); any tests that submit `rationale=` to exit.
**Acceptance:**
- Exit form renders without a rationale input.
- `trade_events.rationale` after a successful exit equals `ExitReason` value (e.g., `"stop-hit"`).
- CLI `trade exit --rationale foo` → unrecognized option error.
**Dependencies:** conceptually coherent with T4+T5 but technically independent.
**Est.:** 1–2 hours.

### T7 — `feat(web): preserve stop-form fields on regression error; expose force`

**Files:** `swing/web/view_models/trades.py` (`TradeStopFormVM` +4 preservation fields); `swing/web/routes/trades.py` (catch `StopRegressionError`, rebuild VM with form values, re-render; plumb `force` from form to `StopAdjustRequest`); `swing/web/templates/partials/trade_stop_form.html.j2` (Force checkbox; value bindings on inputs; preserved selection on rationale `<select>`); tests under `tests/web/test_routes/test_trades.py`.
**Acceptance:**
- On `StopRegressionError` re-render: typed `new_stop`, selected `rationale`, typed `notes` all retained in the returned HTML.
- Ticking Force + resubmitting with same values succeeds.
- Non-error path: Force unchecked by default; unchecked Force is preserved across error re-render (not auto-ticked).
**Dependencies:** **requires T5** for the rationale-select preservation semantics; otherwise the preserved rationale is a textarea string and the template does `{{ vm.rationale }}` directly.
**Est.:** 1–2 hours.

### Recommended cadence

- **Session 2:** T1 + T2 + T3 (three independent tasks). ~4–6 hours. All three are non-blocking on each other and on the Bug 3a cluster.
- **Session 3:** T4 → T5 → T6 → T7, in that order. ~6–10 hours. Coherent "rationale is now structured" shipment; T7 follows T5 for the rationale-select preservation wiring.

Alternative for shorter sessions: session 2 = T1+T2 (~2h), session 3 = T3 (~3h), session 4 = T4+T5 (~5h), session 5 = T6+T7 (~3h).

### Binding rules across all seven tasks

- Conventional-commits (`feat(...)`, `fix(...)`, `refactor(...)`). No Claude co-author footer. No `--no-verify`. No amending.
- TDD per task: failing test → minimal impl → passing test → commit.
- Fast suite green after each commit. Ruff: no new violations.

### Phase-isolation carve-out declaration

CLAUDE.md's Phase-isolation rule treats `swing/trades/` and `swing/data/` as read-only during Phase 3 work unless a current-phase spec explicitly scopes a carve-out. This spec carves out the following for Tranche B-ops sessions 2+:

- `swing/trades/entry.py` (T4: `EntryRationale` enum).
- `swing/trades/stop_adjust.py` (T5: `StopAdjustRationale` enum).
- `swing/trades/equity.py` (T2: `total_current_risk` helper).
- No `swing/data/` changes in this spec. No migrations.

Carve-out justification: Bug 3a rationale taxonomy + Bug 6 total-risk helper are operator-facing feature work blocked by the enums/helpers only being expressible in these modules. Each task commit body must repeat the one-line carve-out justification so the isolation rule remains auditable.

---

## 8. Items flagged but not scoped

Recorded in the return report and for future orchestrator sessions:

- **Exit-form field preservation.** Same latent pattern as the stop-form gap fixed in T7. No live bug report. Deferred; pick up when a user-reported exit-form re-render loss surfaces, or bundle opportunistically into a future session touching the exit form.
- **Total-book risk cap config.** `cfg.risk.max_total_risk_pct` + warn-coloring on the Open-risk tile when exceeded. T2 displays the raw number only. Adding a cap + threshold styling is a session 2+ follow-up; deferred until there's evidence about the right default value.
- **Book-equity-based Open-risk percent.** §2 uses realized equity as the percent denominator for cross-UI consistency with the entry-form sizing hint. A future session may add a second "book %" reading that includes unrealized P&L (requires live prices in the risk math). Deferred until operator analytics demands it.
- **Exit-rationale taxonomy distinct from `ExitReason`.** §3 collapses exit rationale into `ExitReason` for minimum-viable scope, acknowledging the semantic mismatch for `partial` and `manual` values. A future session may introduce a third `ExitRationale` enum (e.g., `target-reached`, `setup-broken`, `weather-deteriorating`, `gap-risk`, `stop-triggered`, `time-decay`, `other`) if journaling analysis shows the collapsed values materially corrupt downstream queries. Flagged as a follow-up, not a present defect.
- **Chart-reason split:** `insufficient-data` subdivided into `fetcher-failed` vs `too-few-bars`. Needs pipeline-layer per-ticker chart-status persistence (today `_step_charts` silently `continue`s on fetcher exceptions and silently returns on short-bar fixtures). Deferred as a pipeline-structural task outside the web-layer scope of T3. The T3 message text ("data too thin or fetch error...") acknowledges both causes without claiming to distinguish.
- **Pipeline-linkage bundle (§4 drift elimination).** §4's scope resolver is best-effort because two pipeline-layer linkages are missing: (a) `pipeline_runs` does not record its own `evaluation_run_id`, so the resolver falls back to a `data_asof_date` + `run_ts <= finished_ts` heuristic that can race against mid-pipeline standalone `swing eval` calls; (b) the chart step's actual per-ticker target list and outcome (rendered / fetch-failed / too-few-bars / out-of-scope) are not persisted, so the VM reconstructs scope heuristically and message text collapses fetcher-failure + too-few-bars into one bucket. A future pipeline-layer session would address both together by: (1) adding `evaluation_run_id` as a FK column on `pipeline_runs`, populated by the pipeline orchestrator; (2) adding a `pipeline_chart_targets` table keyed on `run_id` + `ticker` with per-ticker outcome. Deferred as pipeline-structural; estimated 1 session when picked up.
- **Backfill migration for `trade_events.rationale` free-text rows.** Explicitly rejected as a minimum-viable violation: the cost of re-interpreting N months of pre-taxonomy rows is high, and the display layer gracefully degrades to "render raw string." Flagged so a future session doesn't treat the coexistence of old + new values as oversight.

---

## 9. Open questions for orchestrator

None blocking for implementation. Two minor judgment calls that the implementer can resolve in-flight:

- **T4/T5 empty-notes-on-`other` validation layer.** Spec says "route-layer validation." Implementer may choose to move it to the form-VM builder if a cleaner shape emerges — either works; the test assertion is the same.
- **T3 scope-resolver placement.** The chart-scope logic that `_step_charts` uses (A+ ∪ top-N near-trigger) is currently inline in the pipeline step. T3 needs the same logic in the VM layer. Two options: (a) extract a pure helper in `swing/pipeline/ohlcv.py` or a new `swing/pipeline/chart_scope.py`, or (b) duplicate the small logic in the VM with a clear comment. Implementer choice.

---

## 10. Adversarial review summary

**Rounds:** 5 (terminated on `NO_NEW_CRITICAL_MAJOR` verdict with all prior findings resolved; thread ID `019dbec5-9028-7c93-b45c-12ca12e7cb09`).

### Round 1 — 4 major + 3 minor, all resolved

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | Major | Entry/stop-adjust taxonomies not drawn exclusively from existing repo vocabulary (brief §2 constraint) | §3 both tables gained a `Provenance` column mapping each value to a repo symbol or "Deliberate expansion" label; added paragraph under entry-rationale explaining the brief's "draw from" language and listing each expansion explicitly |
| 2 | Major | Exit rationale collapse into `ExitReason` loses information; `partial` + `manual` are semantically thin as rationale values | Kept user-approved collapse; added "Known limitation" paragraph to §3 exit; §8 gains tabled `ExitRationale` enum proposal for revisit when journaling shows corruption |
| 3 | Major | Open-risk denominator labeled `current_equity` but project's `current_equity()` excludes unrealized P&L | §2 relabeled denominator as `realized_equity`; added "Denominator — deliberate choice of realized equity" paragraph explaining cross-UI consistency with entry-form sizing hint; §8 gains book-equity-pct follow-up |
| 4 | Major | Chart-unavailable collapses `fetcher-failed` + `too-few-bars` into misleading `insufficient-data`; scope resolver recomputes from live watchlist → drift | Message text revised to acknowledge both causes honestly; §4 initial attempt to use persisted `daily_recommendations` for scope (later superseded by round 2/3/4 resolutions) |
| 5 | Minor | `total_current_risk` signature claims to return pct but lacks equity input | §2 Scope: helper signature fixed to return `(dollars, contributing_count, all_above_breakeven)`; pct computed in `build_dashboard` |
| 6 | Minor | `force` checkbox adjacent to explicitly-out-of-scope V2.1 §VI.B.B8 override UX | §5 Rationale gains "Scope clarification" bullet stating minimum-viable CLI parity, not a generalized override workstream |
| 7 | Minor | T3 task coupling understated | §7 T3 files list + acceptance criteria expanded; est. revised 2–3h → 3–4h |

### Round 2 — 2 major + 1 minor, all resolved (Codex read repo source)

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 8 | Major | Round 1's "use persisted `daily_recommendations`" approach doesn't match `_step_charts` (which uses live `list_active_watchlist`, not filtered to `near_trigger` recs) | §4 rewritten: resolver mirrors `_step_charts` exactly — A+ from persisted candidates + top-N from live `list_active_watchlist()` sorted by proximity. Labeled "approximate, not deterministic." |
| 9 | Major | `daily_recommendations` doesn't persist `last_close`, so proximity ranking can't be reconstructed from rec rows | Resolver no longer attempts to use rec rows for proximity; documented explicitly |
| 10 | Minor | Round 1 T3 implied `eval_run_id` is a field on `pipeline_runs`; it isn't | §7 T3 corrected: `eval_run_id` is fetched from `evaluation_runs` independently |

### Round 3 — 1 major + 1 minor, all resolved

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 11 | Major | Round 2's `SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1` can pick an unrelated standalone `swing eval` that ran after the pipeline completed | §4 adds "Linking `eval_run_id` to the pipeline run" subsection with constrained query: `data_asof_date = :pipeline.data_asof_date AND run_ts <= :pipeline.finished_ts ORDER BY run_ts DESC LIMIT 1` |
| 12 | Minor | Drift acknowledgment understated the failure envelope by localizing it to top-N boundary | Drift section rewritten to enumerate both A+ divergence and near-by-proximity divergence as distinct modes |

### Round 4 — 1 major, resolved

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 13 | Major | Round 3's constrained query still relies on a false claim that the pipeline's lease prevents interleaved `swing eval`; in fact `evaluation_runs` is not lease-fenced | §4 rewritten again: query is now explicitly labeled "best-effort heuristic, not authoritative"; "Why best-effort" subsection documents the race window; "Why not build a real linkage" paragraph explains deferral to pipeline-schema session |

### Round 5 — 0 issues; terminated

Verdict `NO_NEW_CRITICAL_MAJOR`. All 13 findings resolved; no accepted-with-rationale entries.

### Minor issues remaining

None. All three round-1 minors were resolved.

### What changed from the pre-review draft

The spec's bones are intact — the taxonomy decisions, the Open-risk tile shape, the stop-form preservation pattern, and the seven-task decomposition all survived the review unchanged. The material changes are:

- **Provenance columns + expansion justification** on both enum tables (§3).
- **Known-limitation block** on exit-rationale collapse (§3) with follow-up in §8.
- **Realized-equity denominator** explicit labeling + cross-UI consistency argument (§2).
- **Chart-unavailable scope resolver** rewritten three times (rounds 1→2→3→4) to arrive at an honest "best-effort heuristic" framing, with documented drift modes and a consolidated §8 follow-up for the pipeline-layer fix.
- **Helper signature fix** (Minor 1), **force-checkbox scope clarification** (Minor 2), **T3 coupling / eval-linkage / churn fixture tests** (Minor 3 + Round 3 Minor).

The chart-scope design absorbed most of the adversarial pressure — four of the thirteen findings were against it. The final form is less ambitious than round 1's "deterministic reconstruction" but more honest about what the current schema supports.
