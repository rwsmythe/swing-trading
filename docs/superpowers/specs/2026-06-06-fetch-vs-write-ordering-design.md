# Fetch-vs-Write-Ordering Fix — Design Spec

**Date:** 2026-06-06
**Phase:** 15 (B-family / operational hardening) — bug-fix arc, NO schema change (v24 holds)
**Status:** LOCKED (Codex-converged) — ready for `copowers:writing-plans`
**Branch (brainstorm):** `fetch-vs-write-ordering-arc-brainstorm` from main HEAD `cadbff61`
**Commission brief:** [`docs/fetch-vs-write-ordering-arc-brainstorming-dispatch-brief.md`](../../fetch-vs-write-ordering-arc-brainstorming-dispatch-brief.md)

---

## 1. Problem statement (CONFIRMED root cause — grounded, not re-derived)

The just-merged SQLite-lock-contention arc (busy_timeout=30000 + a single serialized
audit-writer connection, merged `ffb5fdc6`) did **not** collapse the `database is locked`
yfinance-degrade fallback at the Run-92 live gate (operator-witnessed 2026-06-06 +
orchestrator-verified). Its G2′ telemetry surfaced the TRUE cause:

```
audit record_call_start: BEGIN IMMEDIATE FAILED (database is locked) after ~33s (busy_timeout=30000ms)
```

**Mechanism.** The nightly pipeline opens a `lease.fenced_write()` write transaction
(`BEGIN IMMEDIATE` on the lease connection `conn`) and, *inside that still-held transaction*,
calls an OHLCV fetch (`ohlcv_cache.get_or_fetch(...)`). On a cache **miss** that call drops
through the Schwab market-data ladder hook (`_bars_hook`,
[runner.py:434](../../../swing/pipeline/runner.py)), which audits the call on a **separate**
shared connection `audit_conn` ([runner.py:372](../../../swing/pipeline/runner.py)) via
`record_call_start` → `BEGIN IMMEDIATE`. SQLite permits a single writer per database file, so
`audit_conn`'s `BEGIN IMMEDIATE` blocks on the write lock held by the `fenced_write` `conn`,
waits the full `busy_timeout`, fails `database is locked`, and the ladder falls back to
yfinance → **silent provider degrade for ~13–22 tickers/run**.

`busy_timeout` and the serialized audit writer **cannot** fix this: the lock is held by a
*different connection in the same process*, and that connection does not release until the
`fenced_write` context manager commits — which only happens *after* the fetch returns. The
fix is **ordering**, not timeout tuning: perform the network fetch **before** opening the
write transaction; keep only the consistency-critical SQLite reads and the persist inside the
fence.

**Why cache-miss tickers specifically.** `OhlcvCache.get_or_fetch` has its own TTL store
(`_bars_store`, keyed `(ticker.upper(), window_days)`,
[ohlcv_cache.py:175-244](../../../swing/web/ohlcv_cache.py)). A cache **hit** within TTL
returns a copy with **no** network call and **no** ladder/audit write — so a hit inside a held
fence is harmless. Only a **miss** fires the ladder and deadlocks. The runner shares ONE
`OhlcvCache` across detect / observe / charts ([runner.py:2621-2624](../../../swing/pipeline/runner.py)),
so a ticker fetched lock-free in an earlier step is a warm hit later. This is why the
degrade count tracks the *forward-walk detection population not in today's detect pool* (the
#23-widened ~83× watch population) rather than every ticker.

---

## 2. STEP-0 audit — the COMPLETE `lease.fenced_write()` locus list (core deliverable)

Every `lease.fenced_write()` block in [`swing/pipeline/runner.py`](../../../swing/pipeline/runner.py)
(HEAD `cadbff61`), classified by whether the **held** transaction wraps an **audit-writing
fetch** (`ohlcv_cache.get_or_fetch` / `price_cache.get` / any ladder /
`fetch_window_via_ladder` / `fetch_quote_via_ladder` / `get_price_history` / `get_quotes_batch`).
A missed locus = a residual deadlock, so this enumerates **all 18**.

| # | Line | Enclosing function | What the fence wraps | Audit-writing fetch INSIDE? | Verdict |
|---|------|--------------------|----------------------|-----------------------------|---------|
| 1 | 736 | `run_pipeline_internal` (weather) | `upsert_weather_run` | No — `fetcher.get` @728 is OUTSIDE | ✅ safe |
| 2 | 1245 | `_step_evaluate` | `insert_evaluation_run` + `insert_candidates` + `set_evaluation_run_id` | No — `fetcher.get` @1115/1128/1139 + `_warm_pipeline_marketdata` (`price_cache.get`) @1110 all OUTSIDE | ✅ safe |
| 3 | 1274 | `_step_watchlist` | watchlist upserts/archives | No — reads on a separate `read_conn` OUTSIDE | ✅ safe |
| 4 | 1316 | `_step_recommendations` | `upsert_recommendation` | No — reads OUTSIDE; `build_recommendations` is pure | ✅ safe |
| 5 | 1422 | `_resolve_eval_run_action_session_date` | a single `SELECT` (defensive no-cfg/no-shared-conn path) | No | ✅ safe |
| 6 | 1541 | `_step_pattern_detect` (defensive read-via-lease) | a read | No | ✅ safe |
| 7 | 1654 | `_step_pattern_detect` (defensive seed) | a seed write | No | ✅ safe |
| **8** | **1898** | **`_step_pattern_detect` Pass-2** | reconcile re-read + `list_exemplars` + **exemplar bar fetch** + composite + INSERT loop | **YES — `ohlcv_cache.get_or_fetch` @1994** (exemplar bars, in the `for ex_row in exemplar_rows` loop) | 🔴 **DEADLOCK #1** |
| **9** | **2628** | **`_step_pattern_observe`** | per-detection idempotency/shed + **bar fetch** + `insert_observation` loop | **YES — `_bar_for_date(...)` @2662 → `ohlcv_cache.get_or_fetch` @2525** (detection-ticker bars) | 🔴 **DEADLOCK #2** |
| 10 | 2826 | `_step_charts` | `insert_chart_target` batch | No — fetch happens later in a separate loop | ✅ safe |
| 11 | 2855 | `_step_charts` | `update_chart_target_status='fetcher_failed'` | No — `get_or_fetch` @2851 is OUTSIDE (the fence is in the `except`) | ✅ safe |
| 12 | 2895 | `_step_charts` | `update_chart_target_status` + `insert_classification` | No — `get_or_fetch` @2851 ran OUTSIDE before render | ✅ safe |
| 13 | 2954 | `_step_charts` (`_refresh_one`) | `refresh_chart_render` | No — `_bars_or_none`→`get_or_fetch` @2922 + @3054 ran OUTSIDE before `_refresh_one` | ✅ safe |
| 14 | 3661 | `_step_review_log_cadence` | `insert_pre_create` × cadences | No | ✅ safe |
| 15 | 3705 | `_step_daily_management` | `list_open_trades(conn)` | No — a read | ✅ safe |
| 16 | 3709 | `_step_daily_management` (per-trade) | `compute_daily_approximate_snapshot` + `upsert_snapshot` + `state_transition` | No — `compute_*` reads the OHLCV **archive file** (`ohlcv_archive_dir`), NOT the audit-writing ladder (`swing/trades/daily_management.py` has zero `get_or_fetch`/ladder calls) | ✅ safe |
| 17 | 4024 | `_step_finviz_fetch` | `get_latest_signature_hash` read + CSV shadow/promote (filesystem) | No — the Finviz network fetch (`_finviz_fetch_core`) ran @4015 OUTSIDE | ✅ safe |
| 18 | 4054 | `_step_finviz_fetch` | `insert_call` (finviz audit row) | No — fetch already done | ✅ safe |

### 2.1 Findings

- **Exactly TWO deadlock loci:** `_step_pattern_detect` Pass-2 (#8, exemplar bars) and
  `_step_pattern_observe` (#9, detection-ticker bars).
- **`_step_charts` is NOT a locus** — a refinement of the commission brief's hypothesis. Every
  `get_or_fetch` in charts already runs *outside* the fence (fetch-first, then a short
  status/render write inside the fence). This is the exact target shape; the two real loci
  must be reordered to match it.
- **Ticker attribution.** Detect Pass-2's deadlock degrades **exemplar** tickers (outside the
  candidate universe; never warmed by Pass-1). Observe's deadlock degrades **detection**
  tickers on cache-miss — chiefly forward-walk detections *not* in today's detect pool
  (today's candidates are warm from Pass-1's lock-free fetch). The widened #23 observe pool is
  the dominant miss source, matching the 13–22/run magnitude.
- **Scope is `runner.py`.** Web routes use a different (non-pipeline-lease) write model and are
  out of scope; the pipeline lease + shared `audit_conn` pattern is unique to the nightly
  runner.

---

## 3. Decisions (operator-resolved 2026-06-06)

- **OQ-A — pre-fetch strategy: PER-LOCUS, just-before-its-own-write.** Each step pre-fetches
  only the bars it needs immediately before opening its fence. No bulk up-front pass (which
  would couple steps, duplicate detect Pass-1's candidate fetch, and hold the full widened
  population's bars in memory at once). Mirrors the already-correct charts shape.
- **OQ-B — stopgap revert: IN this arc's executing phase.** Revert
  `swing.config.toml [web] db_busy_timeout_ms` from the `5000` stopgap to `30000` (or delete
  the key → `db.py DEFAULT_BUSY_TIMEOUT_MS = 30000`) as a task in the executing phase, once
  both loci are reordered. The deadlock is structurally removed, so 30s is again the correct
  safe value, and config stays truthful with code.
- **OQ-C — exemplar corpus consistency (spec §5.7): KEEP `list_exemplars(conn)` in-fence;
  pre-fetch bars; skip-on-miss.** Corpus *membership* consistency is the **row** read, which
  stays inside the fence. Exemplar **bar** data is immutable historical OHLCV — fetching it
  outside the fence cannot violate membership semantics. Any exemplar present in the in-fence
  row read but absent from the pre-fetched bar dict (a rare row-list race) is **audit-skipped
  (#27)**, never fetched in-fence.

---

## 4. Fix design — per-locus reorder

The universal rule: **fetch (network/ladder/audit-writing) happens with NO held
`fenced_write`; the fence wraps only fast SQLite reads + the persist.** A pre-warmed/-collected
bar value reached inside the fence MUST be served from memory (cache hit or a passed-in dict);
on a miss it MUST be audit-skipped (#27), never fetched.

### 4.1 Locus #1 — `_step_pattern_detect` Pass-2 ([runner.py:1898-2024](../../../swing/pipeline/runner.py))

**Stays inside the fence (consistency-critical — do NOT move):**
- `canonical_existing` re-read @1920 — the Pass-2 reconcile-before-serialize re-read (Codex R4
  architecture); MUST observe in-flight commits.
- `list_exemplars(conn)` @1977 — corpus **membership** read (spec §5.7); OQ-C keeps it in-fence.
- `match_forward` composite derivation + the `insert_evaluation` / detection-event-append
  INSERT loop (@2036-end).

**Moves OUT (before `with lease.fenced_write()` @1898):**
- The exemplar **bar fetch** currently at @1994 (`ohlcv_cache.get_or_fetch(ticker=ex_row.ticker,
  window_days=400)`).

**Reorder:**
1. **Before** the fence, read exemplar rows read-only (a fresh `connect(cfg.paths.db_path)` in
   the cfg path; the cfg=None test-stub path reuses `getattr(lease, "_conn", None)` WITHOUT
   entering `fenced_write` — mirroring the existing `detector_read_conn` discipline at
   [runner.py:1714-1723](../../../swing/pipeline/runner.py)). Filter to the
   `("confirmed","watch")` decisions (same filter as @1989). For each surviving ticker, call
   `ohlcv_cache.get_or_fetch(ticker=..., window_days=400)` — **identical** params to the
   current in-fence call so #28/#29 historical depth is byte-for-byte preserved — and collect
   results into `exemplar_bars_by_ticker: dict[str, pd.DataFrame]`. Per-exemplar failure is
   isolated (try/except → skip that ticker, continue), exactly as the current @2013 isolation.
2. **Inside** the fence, keep `list_exemplars(conn)` @1977 (membership). Replace the @1994
   `get_or_fetch` with `ex_bars = exemplar_bars_by_ticker.get(ex_row.ticker)`. If `ex_bars is
   None` (not pre-fetched — failed fetch OR row-list race), **audit-skip**: `continue` + append
   a `run_warnings` / `warnings_json` entry (#27) recording `step=pattern_detect`,
   `exemplar_ticker`, `reason="exemplar bars unavailable (pre-fetch miss/skip)"`. **No fetch
   in-fence.**

**Invariants preserved:** #5 (Pass-1 `bars_by_ticker` candidate bars still reused unchanged;
exemplars fetched once, outside the fence, never re-fetched); #28/#29 (same `window_days=400`);
spec §5.7 (membership row read in-fence); reconcile-before-serialize architecture (untouched);
audit single-tx (the in-fence transaction now does zero competing-connection work).

### 4.2 Locus #2 — `_step_pattern_observe` ([runner.py:2628-2685](../../../swing/pipeline/runner.py))

**Observation:** the ENTIRE per-detection loop body is fence-independent *except*
`insert_observation` @2675. `prev` comes from `latest` (loaded outside the fence @2603); the
shed test reads `det.finviz_screen_state` (in-memory); `_bar_for_date` is a fetch (`get_or_fetch`
populate) + archive **file** read (`resolve_ohlcv_window`); `_advance_status` is pure. Only the
insert needs the fence.

**Reorder (split compute-pass / write-pass — mirrors charts):**
1. **Before** the fence, iterate `open_dets` exactly as today: apply the same-day idempotency
   skip (@2631), the watch-shed skip (@2642-2661, `_shed_count`++ and `continue` preserved),
   then `_bar_for_date(...)` (@2662 — this is where `get_or_fetch` fires, now lock-free). On
   `bar is None`, emit the existing no-bar `run_warnings` entry (#27) + `continue`. Compute
   `sessions` + `_advance_status`. Build the `PatternForwardObservation` row (including
   `build_ohlc_today_json` with the L3 completed-day guard) and collect `(row)` into a
   `to_insert: list[PatternForwardObservation]`.
2. **Inside** a single `with lease.fenced_write() as conn:` at the end, loop `to_insert` and
   `insert_observation(conn, row)`; `_observed_count`++ per insert.

**Pre-fetch respects shed (OQ-A):** because the shed decision is evaluated in the same compute
pass *before* `_bar_for_date`, shed tickers are never fetched — no wasted Schwab quota, identical
to today.

**Invariants preserved:** idempotency (reads the same outside-loaded `latest`); watch-shed +
its #27 audit (`_shed_count`); no-bar #27 audit; the observe-load telemetry
(`drain_telemetry()` @2701 still counts the same `get_or_fetch` calls — now in the compute pass;
reset at entry @2626 unchanged); the append-only log's completed-day guard; single-writer
discipline (one short fence around the inserts instead of a long fence across all fetches —
strictly less lock contention).

### 4.3 Stopgap revert (OQ-B — executing phase, after both loci land)

In [`swing.config.toml`](../../../swing.config.toml) `[web]`, restore the safe value:
either set `db_busy_timeout_ms = 30000` or delete the key (falls back to
`db.py DEFAULT_BUSY_TIMEOUT_MS = 30000`, [db.py:54](../../../swing/data/db.py)). Remove the
`TEMPORARY STOPGAP (2026-06-06, Run-92 live gate)` comment block @129-136. **Recommendation:**
delete the key (single source of truth = the `db.py` default), and replace the stopgap comment
with a one-line pointer noting the deadlock was structurally removed by this arc.

---

## 5. What this arc deliberately does NOT change (keepers)

- The lock-contention arc's keepers stay: `busy_timeout` (restored to 30000), the single
  serialized `audit_conn` + `_AUDIT_WRITE_LOCK`, the G2′ telemetry, the catch-all
  observability. This arc *removes the held lock* so that telemetry will show the deadlocks
  collapse — it does not remove the telemetry.
- The lease-fencing contract: every write still happens inside `fenced_write` with the in-tx
  lease check; only the FETCH moves out.
- `_step_charts` is left as-is (already correctly ordered).
- The shared `OhlcvCache` TTL/breaker/telemetry design is untouched; we only change *when*
  `get_or_fetch` is called relative to the fence.

---

## 6. Locks / invariants (propagate to writing-plans)

- **Schema: NONE** — v24 holds. Zero migrations, zero CHECK changes, zero column adds.
- DB-outside-Drive (`%USERPROFILE%/swing-data/swing.db`).
- Lease-fencing contract (write stays in `fenced_write` + in-tx lease check).
- Audit single-tx discipline (audit rows on `audit_conn`, serialized by `_AUDIT_WRITE_LOCK`).
- **#5 no-re-fetch / L2 LOCK:** Pass-1 `bars_by_ticker` reused; exemplar bars fetched exactly
  once (now outside the fence); no new re-fetch introduced.
- **#27 silent-skip-audit:** every new early-return / skip path (exemplar pre-fetch miss;
  unchanged observe no-bar + shed) emits a `warnings_json` entry.
- **#28/#29 exemplar OHLCV depth:** preserved by reusing the identical
  `get_or_fetch(window_days=400)` call params at the moved-out site.
- The data-integrity arc barriers + the just-merged lock-contention arc keepers remain intact.

---

## 7. Test strategy (TDD — discriminating, pre-fix-fails / post-fix-passes)

Per `feedback_regression_test_arithmetic`: each test below is constructed so it **fails on the
pre-fix code and passes on the post-fix code**.

1. **Gold-standard deadlock-reproduction (both loci).** Drive the real step against a real
   SQLite DB with a spy `ohlcv_cache` whose `get_or_fetch` attempts a `BEGIN IMMEDIATE` on a
   **second** connection to the same DB (short busy_timeout, e.g. 200ms) and records whether it
   **succeeded**.
   - Pre-fix: `get_or_fetch` is invoked while the step's `fenced_write` is held → the
     second-connection `BEGIN IMMEDIATE` times out (`database is locked`) → spy records
     `deadlock_observed=True` → **assert fails**.
   - Post-fix: `get_or_fetch` runs with no held fence → second-conn `BEGIN IMMEDIATE` succeeds
     → `deadlock_observed=False` → **assert passes**.
   - One test for `_step_pattern_detect` Pass-2 (exemplar fetch), one for
     `_step_pattern_observe` (detection fetch). This is the binding regression — it reproduces
     the Run-92 mechanism in-process, not a proxy.
2. **Ordering assertion (lighter, complements #1).** Spy records, per `get_or_fetch` call,
   whether the lease is mid-transaction (e.g. the spy lease exposes an `in_fenced_write` flag
   set on `__enter__` / cleared on `__exit__`). Assert every `get_or_fetch` observed
   `in_fenced_write is False`.
3. **#5 no-re-fetch preserved (detect Pass-2).** Assert candidate tickers fetched in Pass-1 are
   NOT re-fetched in Pass-2 (the Pass-2 reorder only adds exemplar pre-fetch); assert each
   exemplar ticker's `get_or_fetch` is called exactly once.
4. **#27 audit on exemplar pre-fetch miss (detect Pass-2).** Inject an exemplar row whose bars
   fail to pre-fetch (or appear only in the in-fence `list_exemplars` row read, not the
   pre-fetch dict); assert the verdict is skipped AND a `warnings_json` entry is emitted; assert
   **no** in-fence fetch was attempted for it.
5. **Observe parity.** With a seeded mix of (a) same-day-already-observed (idempotent skip), (b)
   watch-shed, (c) no-bar, (d) normal detections: assert `_observed_count`, `_shed_count`, the
   shed #27 audit, the no-bar #27 audit, and `observe_load` telemetry
   (`fetch_window`/`in_memory_hit`) are **identical** to the pre-fix step for the same inputs
   (behavior-preserving reorder), while #1/#2 above prove the fetch moved out of the fence.
6. **Stopgap revert.** Assert `cfg.web.db_busy_timeout_ms == 30000` (or, if the key is deleted,
   that the resolved default is 30000 via `DEFAULT_BUSY_TIMEOUT_MS`) and that the `audit_conn`
   is opened with 30000.
7. **Full fast suite** green (~7128 baseline) + `ruff check swing/`.

---

## 8. Out of scope (explicit)

- The `OhlcvBar` bad-bar issue (its own queued arc).
- The banked non-audit-writer telemetry extension (revisit post-fix if any residual contention
  shows).
- Issue #3 metrics fix.
- The banked Schwab market-data ladder T-C.1 per-ticker wrapper error → yfinance fallback
  investigation (a *separate* provider-degrade cause from this deadlock; this arc does not
  address it). Note: it is plausible some Run-92 candidate-ticker yfinance tags came from that
  banked cause rather than the deadlock — this arc fixes the deadlock and the two can be
  disambiguated at the live gate by the absence of `BEGIN IMMEDIATE ... database is locked`
  audit telemetry.
- Any schema change.
- `_step_charts` reordering (already correct).

---

## 9. Acceptance criteria (executing-ready)

- [ ] `_step_pattern_detect` Pass-2: exemplar bars pre-fetched before the fence; in-fence
      `get_or_fetch` @1994 replaced by a dict lookup; skip-on-miss with #27 audit;
      `list_exemplars(conn)` + `canonical_existing` re-read remain in-fence.
- [ ] `_step_pattern_observe`: compute pass (idempotency/shed/`_bar_for_date`/`_advance_status`/
      row-build) outside the fence; single fence wraps only the `insert_observation` loop;
      idempotency + shed #27 + no-bar #27 + telemetry preserved.
- [ ] No `get_or_fetch` / `price_cache.get` / ladder call executes inside ANY held
      `fenced_write` in `runner.py` (re-run the §2 audit on the post-fix tree; the table must be
      all-✅).
- [ ] `swing.config.toml [web] db_busy_timeout_ms` reverted to 30000 (or key deleted) + stopgap
      comment removed.
- [ ] Tests §7.1–§7.6 land TDD (fail→pass) + full fast suite green + ruff clean.
- [ ] Schema unchanged (v24); ZERO `Co-Authored-By`; conventional commits.

---

## 10. Section map (for the orchestrator's QA)

| § | Contents |
|---|----------|
| 1 | Confirmed root cause + deadlock mechanism + cache-miss explanation |
| 2 | **Complete 18-block `fenced_write` audit table** + findings (2 loci; charts already safe) |
| 3 | OQ-A/B/C decisions (operator-resolved) |
| 4 | Per-locus reorder design (detect Pass-2; observe) + stopgap revert |
| 5 | Keepers (what stays) |
| 6 | Locks/invariants (schema NONE) |
| 7 | Discriminating TDD test strategy |
| 8 | Out of scope |
| 9 | Acceptance criteria |
| 10 | This map |
