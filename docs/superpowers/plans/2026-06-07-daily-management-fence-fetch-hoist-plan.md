# Daily-Management Network-Under-Fence (#16) Fetch-Hoist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `_step_daily_management` from performing yfinance network I/O while holding the per-trade SQLite write lock, by making `compute_daily_approximate_snapshot` a pure compute that consumes a pre-warmed DataFrame and hoisting the archive warm OUTSIDE the per-trade `lease.fenced_write`.

**Architecture:** The runner warms the archive per-open-trade-ticker just before that trade's write fence (yfinance runs lock-free); the fence then wraps only the fast `get_trade` SQLite read + the persist. `compute_daily_approximate_snapshot` drops its fetch import/call, consumes `archive_df`, enforces an `expected_ticker` identity guard (the bars were warmed for the `list_open_trades` snapshot ticker; reject — skip, never re-fetch — if the in-fence trade row's ticker changed), and returns a typed `SnapshotComputeResult(fields, miss_reason)`. All miss causes funnel to ONE `run_warnings` (#27) skip branch; the `miss_reason` tag is sourced from `compute_*` for the in-fence cause **when the warm succeeded**, and from the warm layer (`warm_raised`/`warm_empty_or_stale`) when the warm itself failed (root-cause-wins — see Task 2).

**Tech Stack:** Python 3.14, SQLite (WAL), pandas, pytest (`-m "not slow"` fast suite), ruff. No schema change (v24 holds). The shared `read_or_fetch_archive` API is byte-identical (all 9 consumers untouched).

---

## Source-of-truth + scope

- **Spec (LOCKED, Codex-converged):** [`docs/superpowers/specs/2026-06-07-daily-management-fence-archive-api-split-design.md`](../specs/2026-06-07-daily-management-fence-archive-api-split-design.md). This plan IMPLEMENTS that spec; it does not re-litigate the design.
- **Commission brief:** [`docs/daily-management-fence-arc-writing-plans-dispatch-brief.md`](../../daily-management-fence-arc-writing-plans-dispatch-brief.md).
- **Branch-from:** main HEAD `0b1c46cc` (worktree `dm-fence-fetch-hoist-plan`).
- **Schema:** NONE — v24 holds. Zero migrations, zero CHECK changes, zero column adds.

### Two writing-plans decisions (brief §3) — RESOLVED

1. **Miss-reason mechanism (spec §3.1/§4.2 deferred → operator-resolved 2026-06-07):** the function returns a **typed result dataclass** `SnapshotComputeResult(fields: dict[str, Any] | None, miss_reason: str | None)`. This is the spec-recommended "authoritative typed return" (the function sources the tag from the branch that fired; an external `_classify_infence_miss` labeler could not reliably distinguish the four internal `None` paths). **It is a SECOND, small `§6.6` signature-lock amendment beyond the §3.2-enumerated drop/add — the return contract changes `dict | None` → `SnapshotComputeResult`.** §3.2's literal "return contract is unchanged" note is superseded by §4.2's RECOMMENDED typed return (operator-confirmed). Consequence: the runner unpacks `res.fields`/`res.miss_reason`; the 6 service-test callers consume `res.fields`; the 2 step-test `compute_*` stubs return `SnapshotComputeResult(...)`. The function emits `warm_empty_or_stale` / `ticker_changed` / `no_eligible_window`; the runner sets `warm_raised` (only the runner knows the warm threw). All four tokens funnel to the one #27 branch.
2. **Warm vs `list_open_trades`-snapshot ticker (spec §4.1):** the plan threads `expected_ticker=trade.ticker` — the `trade.ticker` from the up-front `list_open_trades` snapshot the bars were warmed for — **NOT** a re-read. The in-fence `get_trade` re-reads fresh; the guard compares the two so a mid-step `trades.ticker` mutation (rare; tier-3 reconciliation override) is *caught* (skip + `ticker_changed` #27) rather than silently masked. Task 1 makes this explicit so an executor cannot accidentally re-read.

### Locks / invariants (propagate; do not regress)

- **Lease-fencing contract:** every write stays inside `fenced_write` + the in-tx lease check; ONLY the warm (fetch) moves out. `LeaseRevokedError` MUST still re-raise from the per-trade loop (the warm cannot raise it — `read_or_fetch_archive` is lease-free; the fence/`upsert_snapshot`/`state_transition` can, and the outer `except LeaseRevokedError` re-raises before the catch-all).
- **§6.6 signature amendment (this arc, operator-sanctioned):** `compute_daily_approximate_snapshot` drops `ohlcv_archive_dir: Path` + `archive_history_days: int`, adds `archive_df: pd.DataFrame | None` + `expected_ticker: str`, and changes its return type to `SnapshotComputeResult`. No other §6.6-locked signature touched; `trail_MA_period_days_default` name + `# noqa: N803` preserved; `# noqa: PLR0913` stays (still 9 params).
- **`read_or_fetch_archive` byte-identical** — neither signature nor behavior changes; its F6 transient-empty defense (ohlcv_archive.py:263) is preserved by reuse. All 9 consumers untouched by construction. **No new public symbol** is added to `swing.data.ohlcv_archive` (`SnapshotComputeResult` lives in `swing.trades.daily_management`).
- **Session-anchor:** `asof_session = last_completed_session(run_now)` (BACKWARD-looking) computed once, passed to BOTH the warm (`end_date=asof_session`) and the compute (`asof_session=…`). Not moved.
- **#27 silent-skip-audit:** the `fields is None` skip emits a `warnings_json` entry (`step="daily_management"`, `ticker`, `reason`, `miss_reason`); `run_warnings is None` defensive guard mirrors detect/observe.
- **Idempotency:** `upsert_snapshot` SELECT-then-UPDATE/INSERT (same-session re-run preserves `management_record_id`); `entered → managing` stays in-fence after the snapshot lands.
- **Keepers (untouched):** completed-day write barrier, `busy_timeout=30000`, serialized `audit_conn`, G2′ telemetry, `_step_charts` ordering, detect Pass-2 + observe (already reordered by `4f0b4010`).

### Out of scope / banked (do NOT do here)

- **NOT reconciliation hardening.** The tier-3 reconciliation override CAN mutate `trades.ticker` (`validate_trade_correction` at `swing/trades/reconciliation_validators.py:190,217` allowlists only `current_stop`/`state`; `_update_journal_field` at `swing/trades/reconciliation_auto_correct.py:1215` issues a generic `UPDATE trades SET {field}`). This arc only DEFENDS daily-management against it via the `expected_ticker` guard (skip + #27). Allowlisting trade-correction fields is a **separate, banked reconciliation arc** — the orchestrator is tracking it. Do not touch reconciliation here.
- NO schema change. NO new archive-API function / read-only sibling (OQ-2 = pass-bars-in). Do not touch `_step_charts`, detect Pass-2, or observe. NOT the Schwab deadlock (`4f0b4010`), NOT Issue #3, NOT Gate 4, NOT the bad-bar issue.

### Verification commands (used throughout)

```bash
# Single test (fast):
python -m pytest tests/trades/test_daily_management_service.py::test_NAME -v
# Targeted file:
python -m pytest tests/pipeline/test_daily_management_step.py -q
# Full fast suite (baseline ≈ 7223; re-confirm on the branch):
python -m pytest -m "not slow" -q
# Lint:
ruff check swing/
```

### Pre-flight: re-confirm anchors (STEP 0)

Before Task 1, confirm these line anchors on the worktree HEAD (they were grounded on `a460961c`; only doc commits landed since, so they should be unchanged — re-verify, do not assume):

- `compute_daily_approximate_snapshot` @ [`swing/trades/daily_management.py:465`](../../../swing/trades/daily_management.py); lazy `read_or_fetch_archive` import @503; call @510-515; internal `None` paths: `df is None or df.empty` @516, empty anchor window @524, absent asof row @529; return `fields` @654.
- `_step_daily_management` @ [`swing/pipeline/runner.py:3774`](../../../swing/pipeline/runner.py); per-trade fence @3810; `compute_…` call @3811-3827; plain `log.warning` skip @3829-3834; `except LeaseRevokedError: raise` @3844.
- module-level `from swing.data.ohlcv_archive import read_or_fetch_archive` @runner.py:25.
- `run_warnings` accumulator created @runner.py:815; serialized to `warnings_json` @runner.py:1022; param-precedent `_step_pattern_observe(*, …, run_warnings)` @runner.py:2663.
- the REAL `_step_daily_management(...)` call site @runner.py:837-841 (currently does NOT pass `run_warnings`).
- 6 service callers @ `tests/trades/test_daily_management_service.py:131/204/237/272/295/332`; the step fixture monkeypatch @ `tests/pipeline/test_daily_management_step.py:109` + the 2 `compute_*` stubs @302/337; the walkthrough monkeypatch @ `tests/integration/test_phase8_pipeline_walkthrough.py:198`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `swing/trades/daily_management.py` | the `SnapshotComputeResult` dataclass + the pure `compute_daily_approximate_snapshot` | Modify (signature, return type, body: remove fetch, add guard, consume `archive_df`) |
| `swing/pipeline/runner.py` | `_step_daily_management` warm-hoist + `run_warnings` + #27 skip; the call site @837 | Modify |
| `tests/trades/test_daily_management_service.py` | the 6 service-level callers + new guard/miss-reason unit tests | Modify |
| `tests/pipeline/test_daily_management_step.py` | the step fixture patch-target + the 2 `compute_*` stubs + new #27/parity/lease-revoke step tests | Modify |
| `tests/pipeline/test_daily_management_fence_hoist.py` | the gold-standard real-DB lock-hold + ordering regression | **Create** |
| `tests/integration/test_phase8_pipeline_walkthrough.py` | the walkthrough warm patch-target | Modify |
| `tests/data/test_ohlcv_archive_nonbreakage.py` | non-breakage assertion of `read_or_fetch_archive` signature + no new public symbol | **Create** |

---

## Task 1: `compute_daily_approximate_snapshot` → pure compute (atomic refactor; behavior-preserving)

**Why atomic:** changing the function's signature breaks its sole production caller (`_step_daily_management`), so the function change AND the runner call-site change AND all affected test migrations must land in ONE commit to keep every commit green. This task does NOT yet add `run_warnings`/#27 (that is Task 2) — the runner keeps its existing plain `log.warning` skip, so behavior is preserved.

**Files:**
- Modify: `swing/trades/daily_management.py:465-476` (signature + return type) and `:502-517` (body)
- Modify: `swing/pipeline/runner.py:3805-3843` (warm-hoist + call-site args) — NOT the @837 call site yet
- Test (migrate): `tests/trades/test_daily_management_service.py:105-348`
- Test (migrate): `tests/pipeline/test_daily_management_step.py:58-132` (fixture) + `:280-305`/`:335-340` (the 2 `compute_*` stubs)
- Test (migrate): `tests/integration/test_phase8_pipeline_walkthrough.py:194-199`

- [ ] **Step 1: Write/migrate the failing tests**

In `tests/trades/test_daily_management_service.py`, migrate all 6 callers and add the new guard/miss-reason unit tests. The migration drops the `read_or_fetch_archive` monkeypatch + the removed `ohlcv_archive_dir`/`archive_history_days` args, and passes `archive_df=<the frame they already build>` + `expected_ticker=<the seeded ticker>`, consuming `res.fields`.

Migrated `test_compute_daily_approximate_snapshot_full_path` (was @105) — the `df` and `_seed_trade` are unchanged; replace the monkeypatch + call:

```python
    # (df + _seed_trade above are unchanged)
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=df,
        expected_ticker="DHC",
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    fields = res.fields
    assert res.miss_reason is None
    assert fields is not None
    # ... all existing field assertions unchanged (current_price == 108.0, MFE 1.5, etc.)
```

Migrate `test_…_canonicalizes_aware_run_now_to_naive_UTC` (was @172) identically (drop the monkeypatch + removed args; add `archive_df=df, expected_ticker="DHC"`; read `res.fields`; the `created_at == "2026-05-08T04:00:00"` assertion is unchanged).

Migrate `test_…_returns_None_on_empty_archive` (was @222) — pass the frame-less case directly and assert the typed token:

```python
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=None,
        expected_ticker="ZZZZ",
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert res.fields is None
    assert res.miss_reason == "warm_empty_or_stale"
```

Migrate `test_…_returns_None_on_no_asof_row` (was @250) — the `df` (rows 05-05, 05-06; no 05-07) is unchanged; pass `archive_df=df, expected_ticker="DHC"`; assert:

```python
    assert res.fields is None
    assert res.miss_reason == "no_eligible_window"
```

Migrate `test_…_unknown_trade_raises_ValueError` (was @285) — drop the monkeypatch + removed args; `get_trade` runs (and raises) BEFORE the archive/guard is consulted, so the `ValueError` still fires:

```python
    with pytest.raises(ValueError, match="trade 999 not found"):
        compute_daily_approximate_snapshot(
            conn, trade_id=999,
            asof_session=date(2026, 5, 7),
            run_now=datetime(2026, 5, 7, 18, 0, 0),
            archive_df=None,
            expected_ticker="DHC",
            pipeline_run_id=1,
        )
```

Migrate `test_…_stamps_trail_MA_period_days_when_window_sufficient` (was @305) — the 25-session `df` is unchanged; pass `archive_df=df, expected_ticker="DHC"`; read `res.fields`; the `trail_MA_period_days == 21` / `trail_MA_candidate_price == pytest.approx(101.4)` assertions are unchanged.

Add TWO new unit tests:

```python
def test_compute_daily_approximate_snapshot_ticker_guard_skips_on_mismatch(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Identity guard (spec §4.1 / Codex R1 MAJOR #1): bars warmed for
    expected_ticker but the in-fence trade row reports a different ticker ->
    skip (never combine old-ticker bars with the newly read trade row).

    EXACT pre-fix (no guard, if the param existed): a fully-populated field
    dict computed from DHC's bars (res.fields is a dict).
    EXACT post-fix: res.fields is None, res.miss_reason == 'ticker_changed'."""
    _seed_trade(
        conn, trade_id=1, ticker="DHC", entry_price=100.0,
        initial_stop=90.0, initial_shares=50,
        current_avg_cost=100.0, current_size=50.0,
        current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00",
    )
    df = pd.DataFrame({
        "High":  [105.0, 115.0, 110.0],
        "Low":   [98.0,  102.0, 100.0],
        "Close": [104.0, 113.0, 108.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]))
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=df,
        expected_ticker="OLDTICKER",   # != the seeded "DHC"
        pipeline_run_id=1,
    )
    assert res.fields is None
    assert res.miss_reason == "ticker_changed"


def test_compute_daily_approximate_snapshot_empty_anchor_window_miss_reason(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """no_eligible_window sub-case B (Codex R3): frame has rows but NONE in
    [anchor, asof_session] (all rows predate the anchor) -> empty anchor window
    @daily_management.py:524.

    EXACT pre-fix: res is None (no reason).
    EXACT post-fix: res.fields is None, res.miss_reason == 'no_eligible_window'."""
    _seed_trade(
        conn, trade_id=1, ticker="DHC", entry_price=100.0,
        initial_stop=90.0, initial_shares=50,
        current_avg_cost=100.0, current_size=50.0,
        current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00",
    )
    # All rows < anchor (2026-05-01) -> window_mask selects nothing:
    df = pd.DataFrame({
        "High":  [105.0, 115.0],
        "Low":   [98.0,  102.0],
        "Close": [104.0, 113.0],
    }, index=pd.to_datetime(["2026-04-25", "2026-04-28"]))
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=df,
        expected_ticker="DHC",
        pipeline_run_id=1,
    )
    assert res.fields is None
    assert res.miss_reason == "no_eligible_window"
```

In `tests/pipeline/test_daily_management_step.py`, migrate the fixture's monkeypatch target (the warm now resolves via the runner module symbol — `compute_*` no longer imports `read_or_fetch_archive`):

```python
    # Patch the runner's module-level binding (the warm), NOT the source
    # module: compute_daily_approximate_snapshot no longer fetches; the warm
    # at swing.pipeline.runner.read_or_fetch_archive is the only fetch now.
    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive",
        lambda *a, **kw: df,
    )
```

Migrate the `compute_*` stub in `test_step_failure_does_not_abort_pipeline` (was @280-301) to return a `SnapshotComputeResult` (import it at the top of the file: `from swing.trades.daily_management import SnapshotComputeResult`):

```python
    def fail_for_trade_1(conn_inner, *, trade_id, **kwargs):
        if trade_id == 1:
            raise RuntimeError("synthetic-trade-1-failure")
        return SnapshotComputeResult(
            fields={
                "review_date": "2026-05-07", "data_asof_session": "2026-05-07",
                "created_at": "2026-05-07T18:00:00",
                "mfe_mae_precision_level": "daily_approximate",
                "pipeline_run_id": kwargs.get("pipeline_run_id"),
                "current_price": 50.0, "current_stop": 45.0,
                "current_size": 100.0, "current_avg_cost": 50.0,
                "open_R_effective": 0.0, "open_MFE_R_to_date": 0.0,
                "open_MAE_R_to_date": 0.0, "intraday_high": 51.0,
                "intraday_low": 49.0,
                "position_capital_utilization_pct": 0.667,
                "position_capital_denominator_dollars": 7500.0,
                "position_portfolio_heat_contribution_dollars": 500.0,
                "maturity_stage": "pre_+1.5R",
                "trail_MA_candidate_price": None,
                "trail_MA_period_days": None,
                "trail_MA_eligibility_flag": None,
            },
            miss_reason=None,
        )
    monkeypatch.setattr(
        "swing.trades.daily_management.compute_daily_approximate_snapshot",
        fail_for_trade_1,
    )
```

The `raise_revoked` stub in `test_step_re_raises_LeaseRevoked` (was @335) raises before returning, so it needs no shape change (leave it; it stays valid).

In `tests/integration/test_phase8_pipeline_walkthrough.py`, migrate the warm patch-target @198 from `swing.data.ohlcv_archive.read_or_fetch_archive` to `swing.pipeline.runner.read_or_fetch_archive` (the walkthrough drives the step, which now warms via the runner symbol).

- [ ] **Step 2: Run the migrated/new tests to verify they fail**

```bash
python -m pytest tests/trades/test_daily_management_service.py -q
```
Expected: FAIL — `TypeError: compute_daily_approximate_snapshot() got an unexpected keyword argument 'archive_df'` (pre-fix signature rejects the new kwargs) and `AttributeError`/`NameError` for `SnapshotComputeResult` / `res.fields` (the dataclass + typed return don't exist yet).

- [ ] **Step 3: Add the dataclass + amend the function (minimal implementation)**

In `swing/trades/daily_management.py`, add the result dataclass near the module's other dataclasses (ensure `from dataclasses import dataclass` is imported — it is already used in the module):

```python
@dataclass(frozen=True)
class SnapshotComputeResult:
    """Typed return for ``compute_daily_approximate_snapshot`` (spec §4.2,
    operator-resolved 2026-06-07). ``fields`` is the upsert-ready dict, OR
    ``None`` on a skip; ``miss_reason`` is the authoritative skip cause when
    ``fields is None`` (one of ``warm_empty_or_stale`` / ``ticker_changed`` /
    ``no_eligible_window`` from this function; the runner additionally sets
    ``warm_raised`` for a warm that threw). ``miss_reason`` is ``None`` on
    success."""

    fields: dict[str, Any] | None
    miss_reason: str | None
```

Amend the signature (drop `ohlcv_archive_dir`/`archive_history_days`; add `archive_df`/`expected_ticker`; change the return type) — keep the `# noqa: PLR0913` and the `trail_MA_period_days_default` `# noqa: N803`:

```python
def compute_daily_approximate_snapshot(  # noqa: PLR0913  -- spec-locked signature (§6.6, amended 2026-06-07)
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    asof_session: date,
    run_now: datetime,
    archive_df: pd.DataFrame | None,         # NEW — pre-warmed bars (rows <= asof_session)
    expected_ticker: str,                    # NEW — identity guard (spec §4.1)
    pipeline_run_id: int | None,
    capital_floor_dollars: float = 7500.0,
    trail_MA_period_days_default: int = 21,  # noqa: N803  -- name locked by spec §6.6
) -> SnapshotComputeResult:
```

Replace the body lines @502-517 (remove the lazy `read_or_fetch_archive` import; keep the `get_trade` import; add the guard; consume `archive_df`):

```python
    # Lazy import to avoid circular references at module load time:
    from swing.data.repos.trades import get_trade

    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")

    # Identity guard (spec §4.1 / Codex R1 MAJOR #1): the bars were warmed for
    # ``expected_ticker`` OUTSIDE the fence; the trade row is re-read fresh
    # in-fence here. Skip (never re-fetch) if the trade's ticker changed between
    # warm and fence so old-ticker bars are never combined with a newly read
    # trade row. ``trades.ticker`` IS live-mutable (rarely) via a concurrent
    # tier-3 reconciliation override (reconciliation_auto_correct.py:1215;
    # validate_trade_correction gates only current_stop/state). The pipeline
    # lease blocks concurrent *pipeline* runs but NOT CLI/web reconciliation, so
    # this is a REAL (if uncommon) audited skip.
    if trade.ticker != expected_ticker:
        return SnapshotComputeResult(fields=None, miss_reason="ticker_changed")

    df = archive_df
    if df is None or df.empty:
        return SnapshotComputeResult(fields=None, miss_reason="warm_empty_or_stale")
```

Change the two remaining `return None` skip paths (the empty anchor window @524 and the absent asof row @529) to return the typed result:

```python
    window = df.loc[window_mask]
    if window.empty:
        return SnapshotComputeResult(fields=None, miss_reason="no_eligible_window")

    asof_mask = df.index.date == asof_session
    asof_rows = df.loc[asof_mask]
    if asof_rows.empty:
        return SnapshotComputeResult(fields=None, miss_reason="no_eligible_window")
```

Change the success return @654 from `return fields` to:

```python
    return SnapshotComputeResult(fields=fields, miss_reason=None)
```

(Everything between the `df` assignment and the success return — the anchor slice, `asof` extraction, MFE/MAE, cap-util/heat/maturity, the 21-day SMA tail, `created_at` canonicalization, the field dict, and the defensive validator — is byte-unchanged.)

In `swing/pipeline/runner.py`, update `_step_daily_management`'s body @3805-3843 to warm OUTSIDE the fence and pass the new args. (This task keeps the existing plain-`log.warning` skip; Task 2 replaces it with the #27 funnel.)

```python
    asof_session = last_completed_session(run_now)
    with lease.fenced_write() as conn:
        trades = list_open_trades(conn)
    for trade in trades:
        try:
            # --- WARM, OUTSIDE the fence (yfinance I/O here, lock-free) ---
            archive_df = read_or_fetch_archive(
                trade.ticker, end_date=asof_session,
                cache_dir=ohlcv_archive_dir,
                archive_history_days=archive_history_days,
            )
            # --- FENCE: fast SQLite read + compute + persist (no network) ---
            with lease.fenced_write() as conn:
                res = _dm.compute_daily_approximate_snapshot(
                    conn, trade_id=trade.id,
                    asof_session=asof_session,
                    run_now=run_now,
                    archive_df=archive_df,
                    expected_ticker=trade.ticker,   # the snapshot ticker, NOT a re-read
                    pipeline_run_id=lease.run_id,
                    capital_floor_dollars=capital_floor_dollars,
                    trail_MA_period_days_default=trail_MA_period_days_default,
                )
                if res.fields is None:
                    log.warning(
                        "daily_management snapshot skipped for trade %s "
                        "(ticker=%s): %s",
                        trade.id, trade.ticker, res.miss_reason,
                    )
                    continue
                upsert_snapshot(
                    conn, trade_id=trade.id, snapshot_fields=res.fields,
                )
                if trade.state == "entered":
                    state_transition(
                        conn, trade_id=trade.id, new_state="managing",
                        event_ts=res.fields["created_at"],
                        rationale="first_daily_management_record",
                    )
        except LeaseRevokedError:
            # Force-clear authoritative — propagate immediately. Codex R2 M5.
            raise
        except Exception as exc:
            log.warning(
                "daily_management step failed for trade %s: %s",
                trade.id, exc,
            )
```

Note: `cfg.paths.prices_cache_dir` (passed as `ohlcv_archive_dir`) and `archive_history_days` stay on the step signature; they are now consumed by the warm at the runner level. The `# Codex R1 Critical 1` `pipeline_run_id=lease.run_id` rationale comment is preserved.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/trades/test_daily_management_service.py tests/pipeline/test_daily_management_step.py tests/integration/test_phase8_pipeline_walkthrough.py -q
```
Expected: PASS (all migrated callers + the 2 new unit tests + the step/walkthrough suites green).

- [ ] **Step 5: Lint + commit**

```bash
ruff check swing/trades/daily_management.py swing/pipeline/runner.py
git add swing/trades/daily_management.py swing/pipeline/runner.py \
        tests/trades/test_daily_management_service.py \
        tests/pipeline/test_daily_management_step.py \
        tests/integration/test_phase8_pipeline_walkthrough.py
git commit -m "refactor(trades): hoist daily-management archive warm out of the per-trade fence

Make compute_daily_approximate_snapshot a pure compute that consumes a pre-warmed archive_df and returns a typed SnapshotComputeResult, and move the read_or_fetch_archive warm to _step_daily_management outside the per-trade write fence. The in-fence phase is now incapable of network IO; an expected_ticker identity guard skips on a mid-step ticker mutation."
```

---

## Task 2: `_step_daily_management` `run_warnings` + #27 audited skip

**Files:**
- Modify: `swing/pipeline/runner.py:3774-3779` (step signature: add `run_warnings`), `:3808-3843` (warm miss pre-set + #27 funnel), `:837-841` (call site passes `run_warnings`)
- Test: `tests/pipeline/test_daily_management_step.py` (new #27 test)

- [ ] **Step 1: Write the failing test**

Add to `tests/pipeline/test_daily_management_step.py`:

```python
def test_step_emits_27_audit_on_warm_empty(synthetic_lease_and_trades, monkeypatch):
    """#27 silent-skip-audit: when the warm returns None/empty, every open trade
    is skipped with a run_warnings entry carrying miss_reason='warm_empty_or_stale'
    -- no in-fence fetch.

    EXACT pre-fix (Task 1 state: plain log.warning, no run_warnings param):
    _step_daily_management(run_warnings=[...]) raises TypeError (no such param);
    even called without it, run_warnings stays empty (0 entries).
    EXACT post-fix: run_warnings gains one entry per open trade (2: DHC, ZZ),
    each {step:'daily_management', miss_reason:'warm_empty_or_stale'}."""
    lease, conn = synthetic_lease_and_trades
    # Override the fixture's frame-returning warm with a None-returning one:
    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive",
        lambda *a, **kw: None,
    )
    run_warnings: list[dict] = []
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        run_warnings=run_warnings,
    )
    assert len(run_warnings) == 2
    for entry in run_warnings:
        assert entry["step"] == "daily_management"
        assert entry["miss_reason"] == "warm_empty_or_stale"
        assert entry["ticker"] in {"DHC", "ZZ"}
        assert "reason" in entry
    # No snapshot persisted (skip path):
    rows = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot'"
    ).fetchone()[0]
    assert rows == 0
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest tests/pipeline/test_daily_management_step.py::test_step_emits_27_audit_on_warm_empty -v
```
Expected: FAIL — `TypeError: _step_daily_management() got an unexpected keyword argument 'run_warnings'`.

- [ ] **Step 3: Add `run_warnings` + the #27 funnel (minimal implementation)**

In `swing/pipeline/runner.py`, add `run_warnings` to the step signature (mirrors `_step_pattern_observe` @2663):

```python
def _step_daily_management(
    *, lease, run_now: _dt, eval_run_id: int,
    archive_history_days: int, ohlcv_archive_dir,
    capital_floor_dollars: float = 7500.0,
    trail_MA_period_days_default: int = 21,  # noqa: N803  -- name locked by spec §6.6
    run_warnings: list[dict] | None = None,
) -> None:
```

Wrap the warm in a best-effort try/except that pre-sets `miss_reason`, and replace the plain skip log with the #27 funnel. The body becomes:

```python
    for trade in trades:
        try:
            # --- WARM, OUTSIDE the fence (yfinance I/O here, lock-free) ---
            # read_or_fetch_archive is lease-free (touches no lease/lock), so it
            # cannot raise LeaseRevokedError; a warm error degrades to
            # archive_df=None -> the single #27 skip branch below.
            miss_reason: str | None = None
            try:
                archive_df = read_or_fetch_archive(
                    trade.ticker, end_date=asof_session,
                    cache_dir=ohlcv_archive_dir,
                    archive_history_days=archive_history_days,
                )
                if archive_df is None or archive_df.empty:
                    miss_reason = "warm_empty_or_stale"
            except Exception as warm_exc:  # noqa: BLE001 -- best-effort warm; miss funnels to #27
                log.warning(
                    "daily_management warm fetch failed for trade %s "
                    "(ticker=%s): %s -- proceeding to skip path",
                    trade.id, trade.ticker, warm_exc,
                )
                archive_df = None
                miss_reason = "warm_raised"

            # --- FENCE: fast SQLite read + compute + persist (no network) ---
            with lease.fenced_write() as conn:
                res = _dm.compute_daily_approximate_snapshot(
                    conn, trade_id=trade.id,
                    asof_session=asof_session,
                    run_now=run_now,
                    archive_df=archive_df,
                    expected_ticker=trade.ticker,
                    pipeline_run_id=lease.run_id,
                    capital_floor_dollars=capital_floor_dollars,
                    trail_MA_period_days_default=trail_MA_period_days_default,
                )
                if res.fields is None:
                    # All miss causes funnel here. The warm pre-set miss_reason
                    # (warm_raised / warm_empty_or_stale) wins when set; otherwise
                    # the warm succeeded and the typed return is authoritative for
                    # the in-fence cause (ticker_changed / no_eligible_window).
                    if miss_reason is None:
                        miss_reason = res.miss_reason
                    log.warning(
                        "daily_management snapshot skipped for trade %s "
                        "(ticker=%s): %s", trade.id, trade.ticker, miss_reason,
                    )
                    if run_warnings is not None:   # #27 audit (gotcha #27)
                        run_warnings.append({
                            "step": "daily_management",
                            "ticker": trade.ticker,
                            "reason": "archive unavailable for asof_session",
                            "miss_reason": miss_reason,
                        })
                    continue
                upsert_snapshot(
                    conn, trade_id=trade.id, snapshot_fields=res.fields,
                )
                if trade.state == "entered":
                    state_transition(
                        conn, trade_id=trade.id, new_state="managing",
                        event_ts=res.fields["created_at"],
                        rationale="first_daily_management_record",
                    )
        except LeaseRevokedError:
            raise
        except Exception as exc:
            log.warning(
                "daily_management step failed for trade %s: %s",
                trade.id, exc,
            )
```

Update the call site @837-841 to pass `run_warnings`:

```python
                _step_daily_management(
                    lease=lease, run_now=run_now, eval_run_id=eval_run_id,
                    archive_history_days=cfg.archive.archive_history_days,
                    ohlcv_archive_dir=cfg.paths.prices_cache_dir,
                    run_warnings=run_warnings,
                )
```

> **`miss_reason` precedence — intentional, root-cause-wins (Codex R1 MAJOR #3).** When the warm pre-set a reason (`warm_raised`/`warm_empty_or_stale`), the runner keeps it and does NOT overwrite it with `res.miss_reason`, even though `compute_*` evaluates the `ticker_changed` guard FIRST and could return `ticker_changed` on an overlap (warm empty/raised AND the in-fence ticker also changed). This is deliberate: when the warm itself failed, there are **no usable bars for the snapshot ticker regardless of identity**, so `warm_*` is the actionable ROOT cause (ticker delisted/invalid/transient-empty); the `ticker_changed` signal is only meaningful when bars WERE available but the identity didn't match. The typed `res.miss_reason` is therefore authoritative for the IN-FENCE cause **only when the warm succeeded** (`miss_reason is None`). This honors the spec §4.2 single-funnel structure (compute is ALWAYS called; one `res.fields is None` branch) rather than splitting into a separate pre-compute skip — we are not "discarding an authoritative result," we are layering two distinct root-cause domains (warm-layer vs compute-layer). Task 4 adds an explicit overlap test that LOCKS this precedence (`warm_empty_or_stale` wins over a concurrent ticker change).

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest tests/pipeline/test_daily_management_step.py -q
```
Expected: PASS (the new #27 test + all existing step tests green).

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_daily_management_step.py
git commit -m "feat(pipeline): audit daily-management archive-miss skips via run_warnings (#27)

Thread run_warnings into _step_daily_management and funnel every archive-miss cause (warm_raised, warm_empty_or_stale, ticker_changed, no_eligible_window) to a single gotcha-27 warnings_json entry. The warm pre-sets the warm-derived cause; the typed SnapshotComputeResult supplies the in-fence cause."
```

---

## Task 3: gold-standard lock-hold + ordering regression (real file-backed DB)

This is the binding regression (post-fix regression-locking coverage, NOT red→green TDD — it lands after the fix in Tasks 1-2): it proves the warm no longer runs under the fence. It drives the public `_step_daily_management` (stable interface), so the SAME test discriminates pre-fix (lock observed, via a temporary hoist-revert) vs post-fix (no lock).

**Files:**
- Create: `tests/pipeline/test_daily_management_fence_hoist.py`

- [ ] **Step 1: Write the gold-standard regression-locking test**

```python
"""Gold-standard regression: the daily-management archive warm must NOT run
inside a held per-trade fenced_write (spec §7.1-§7.2)."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.pipeline.runner import _step_daily_management
# _seed_trade is a module-level helper in the step-test file (verified
# tests/pipeline/test_daily_management_step.py:15); reuse it directly so this
# file does not duplicate the seeding shape.
from tests.pipeline.test_daily_management_step import _seed_trade


def _make_lease_with_fence_flag(conn_factory):
    """A lease whose fenced_write opens a REAL BEGIN IMMEDIATE write txn on a
    dedicated connection and exposes an in_fenced_write flag (True while held)."""
    state = {"in_fenced_write": False}

    class _RealFenceLease:
        run_id = 99

        def fenced_write(self):
            from contextlib import contextmanager

            @contextmanager
            def _cm():
                conn = conn_factory()
                conn.execute("PRAGMA busy_timeout=200")
                conn.execute("BEGIN IMMEDIATE")
                state["in_fenced_write"] = True
                try:
                    yield conn
                    conn.execute("COMMIT")
                finally:
                    state["in_fenced_write"] = False
                    conn.close()
            return _cm()

    return _RealFenceLease(), state


def test_warm_never_runs_under_a_held_fence(tmp_path: Path, monkeypatch):
    """EXACT pre-fix: read_or_fetch_archive runs inside compute_* under the held
    fence -> a 2nd-connection BEGIN IMMEDIATE on the same DB times out ->
    lock_observed=True -> assert FAILS.
    EXACT post-fix: the warm runs with no held fence -> 2nd-conn BEGIN IMMEDIATE
    succeeds -> lock_observed=False -> assert PASSES.
    Anti-false-pass: the stale/missing archive forces the warm; assert the spy
    fired >= 1 (so 'no lock' can't pass vacuously on a fixture that never fetched)."""
    db_path = tmp_path / "fence.db"
    base = ensure_schema(db_path)
    base.execute("PRAGMA journal_mode=WAL")
    base.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token) "
        "VALUES (99, '2026-05-07T18:00:00', '2026-05-07T18:30:00', 'manual', "
        "'2026-05-07', '2026-05-08', 'complete', 'tok')"
    )
    _seed_trade(base, trade_id=1, ticker="DHC", state="managing",
                entry_price=100.0, initial_stop=90.0, initial_shares=50.0,
                current_avg_cost=100.0, current_size=50.0, current_stop=92.0,
                pre_trade_locked_at="2026-05-01T09:30:00")
    base.commit()

    df = pd.DataFrame({
        "High":  [105.0, 115.0, 110.0],
        "Low":   [98.0,  102.0, 100.0],
        "Close": [104.0, 113.0, 108.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]))

    spy = {"calls": 0, "lock_observed": False, "in_fence_at_call": []}

    def spying_warm(*args, **kwargs):
        spy["calls"] += 1
        spy["in_fence_at_call"].append(fence_state["in_fenced_write"])
        probe = sqlite3.connect(db_path, timeout=0.2)
        probe.execute("PRAGMA busy_timeout=200")
        try:
            probe.execute("BEGIN IMMEDIATE")
            probe.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                spy["lock_observed"] = True
            else:
                raise
        finally:
            probe.close()
        return df

    # Patch BOTH namespaces with the SAME spy (Codex R1 MAJOR #3): the pre-fix
    # in-fence fetch resolves via compute_*'s lazy import (the source module);
    # the post-fix warm calls the runner's module-level binding. Patching only
    # one would make the pre-fix test fail because the spy was never reached
    # (a false reproduction).
    monkeypatch.setattr("swing.data.ohlcv_archive.read_or_fetch_archive", spying_warm)
    monkeypatch.setattr("swing.pipeline.runner.read_or_fetch_archive", spying_warm)

    lease, fence_state = _make_lease_with_fence_flag(lambda: sqlite3.connect(db_path, timeout=0.5))

    # NOTE: do NOT pass run_warnings here. run_warnings is an OPTIONAL param
    # added in Task 2; omitting it keeps this test body valid against BOTH the
    # pre-fix interface (to witness red via a temporary hoist-revert) and the
    # post-fix tree, so the ONLY variable that flips lock_observed is the hoist.
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=tmp_path / "ohlcv",
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )

    assert spy["calls"] >= 1, "warm never fired -- fixture did not exercise the fetch"
    assert spy["lock_observed"] is False, "archive warm ran under a held write lock"
    # Ordering (spec §7.2): every warm observed no held fence.
    assert all(flag is False for flag in spy["in_fence_at_call"])
```

> **Discrimination check (feedback_regression_test_arithmetic) — Codex R1 MAJOR #1:** this test lands in Task 3 (AFTER the fix in Tasks 1-2), so it is GREEN on the committed tree. It genuinely DISCRIMINATES the hoist: with the in-fence fetch restored (the pre-fix behavior — `compute_*` calls `read_or_fetch_archive` under the held fence), the spy's 2nd-connection `BEGIN IMMEDIATE` contends with the held `BEGIN IMMEDIATE` → `OperationalError: database is locked` within 200 ms → `lock_observed=True` and `in_fence_at_call==[True]` → BOTH asserts FAIL. With the hoist (post-fix), the warm fires before the fence → the probe acquires + commits → `lock_observed=False`, `in_fence_at_call==[False]` → asserts PASS. `spy["calls"]==1` in both, so the anti-false-pass guard holds. **The test body deliberately omits `run_warnings`** (optional, added in Task 2) so it is callable against the pre-fix `_step_daily_management` signature too — the executor witnesses red by temporarily restoring the in-fence fetch (reverting only the Task-1 hoist) and re-running; `lock_observed` flips to `True`. The discriminator is the fetch ordering, NOT a signature `TypeError`.

- [ ] **Step 2: Run to verify it passes on the fixed tree (and reason about red)**

```bash
python -m pytest tests/pipeline/test_daily_management_fence_hoist.py -v
```
Expected: PASS on the post-Task-2 tree. (The discrimination is argued above + optionally witnessed by a temporary revert; the test is genuinely red on pre-fix code because it drives the stable `_step_daily_management` interface that existed pre-fix.)

- [ ] **Step 3: (no production change)** — Task 3 is a regression-test-only task; the fix already landed in Tasks 1-2.

- [ ] **Step 4: Re-run to confirm green**

```bash
python -m pytest tests/pipeline/test_daily_management_fence_hoist.py -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/pipeline/test_daily_management_fence_hoist.py
git commit -m "test(pipeline): gold-standard lock-hold regression for daily-management warm-hoist

Drive the real _step_daily_management against a file-backed WAL DB with one open trade and spy on read_or_fetch_archive in both namespaces; a second-connection BEGIN IMMEDIATE during the warm proves no held fence post-fix. Anti-false-pass asserts the spy fired and every warm observed in_fenced_write False."
```

---

## Task 4: parity + all-four-`miss_reason` + lease-revoke (step-level)

> **Framing (Codex R1 MINOR #3):** Task 4 is **post-fix REGRESSION-LOCKING coverage**, not red→green TDD — the behaviors it asserts already exist after Tasks 1-2. Each test still DISCRIMINATES against the pre-fix tree via its documented EXACT values (e.g. the parity test's persisted fields, the precedence test's `warm_empty_or_stale`), but it is added AFTER the production change deliberately, to lock the wired behavior. If any test here is RED on the post-Task-2 tree, that signals a real wiring gap from Tasks 1-2 — stop and fix the production code, do not weaken the test.

**Files:**
- Test: `tests/pipeline/test_daily_management_step.py` (parity + the remaining miss_reasons; the existing `test_step_re_raises_LeaseRevoked` already covers lease-revoke — re-confirm it stays green)

- [ ] **Step 1: Write the regression-locking tests**

Add a deterministic fixed-frame parity test (the compute is behavior-preserving through the new wiring — spec §7.3) and the remaining `miss_reason` sub-cases (`warm_raised`, `ticker_changed`, and the `no_eligible_window` absent-asof-row sub-case via the step):

```python
def test_step_parity_persists_expected_fields_from_fixed_frame(synthetic_lease_and_trades):
    """Deterministic parity (spec §7.3): a fixed warmed frame -> the persisted
    snapshot fields are exactly the documented compute outputs. Isolates the
    compute from any live-archive timing.

    EXACT post-fix (DHC, asof 2026-05-07, the fixture's frame): current_price
    108.0, intraday_high 110.0, intraday_low 100.0, open_MFE_R_to_date 1.5,
    open_MAE_R_to_date 0.2, maturity_stage '+1.5R_to_+2R',
    position_capital_utilization_pct 0.72,
    position_portfolio_heat_contribution_dollars 400.0,
    trail_MA_candidate_price NULL (only 6 sessions < 21)."""
    lease, conn = synthetic_lease_and_trades   # fixture warm returns the fixed df
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        run_warnings=[],
    )
    row = conn.execute(
        "SELECT current_price, intraday_high, intraday_low, open_MFE_R_to_date, "
        "open_MAE_R_to_date, maturity_stage, position_capital_utilization_pct, "
        "position_portfolio_heat_contribution_dollars, trail_MA_candidate_price "
        "FROM daily_management_records WHERE trade_id = 1 "
        "AND record_type = 'daily_snapshot'"
    ).fetchone()
    assert row[0] == 108.0
    assert row[1] == 110.0
    assert row[2] == 100.0
    assert row[3] == 1.5
    assert row[4] == 0.2
    assert row[5] == "+1.5R_to_+2R"
    assert row[6] == pytest.approx(0.72)
    assert row[7] == 400.0
    assert row[8] is None


def test_step_warm_raised_miss_reason(synthetic_lease_and_trades, monkeypatch):
    """Warm raises -> archive_df=None -> miss_reason='warm_raised', skipped, #27.

    EXACT post-fix: run_warnings has 2 entries, each miss_reason='warm_raised';
    0 snapshots persisted."""
    lease, conn = synthetic_lease_and_trades

    def boom(*a, **kw):
        raise RuntimeError("synthetic-yf-network-error")
    monkeypatch.setattr("swing.pipeline.runner.read_or_fetch_archive", boom)

    run_warnings: list[dict] = []
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        run_warnings=run_warnings,
    )
    assert len(run_warnings) == 2
    assert all(e["miss_reason"] == "warm_raised" for e in run_warnings)
    assert conn.execute(
        "SELECT COUNT(*) FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot'"
    ).fetchone()[0] == 0


def test_step_ticker_changed_miss_reason(synthetic_lease_and_trades, monkeypatch):
    """The warm succeeds for the snapshot ticker, but the in-fence trade row's
    ticker was mutated (simulating a concurrent tier-3 reconciliation override)
    -> ticker guard fires -> miss_reason='ticker_changed', skipped, #27.

    EXACT post-fix: trade 1's run_warnings entry has miss_reason='ticker_changed';
    no snapshot for trade 1."""
    lease, conn = synthetic_lease_and_trades
    # The warm captures trade.ticker ("DHC") from the up-front list_open_trades
    # snapshot and warms bars for it; expected_ticker="DHC" is threaded in. We
    # make the in-fence get_trade report a DIFFERENT ticker so the guard fires
    # (simulating a concurrent tier-3 reconciliation override). compute_* imports
    # get_trade LAZILY from swing.data.repos.trades (daily_management.py:503-504),
    # so the patch target is the SOURCE module the lazy import binds at call time
    # -- NOT a swing.trades.daily_management attribute.
    import dataclasses

    import swing.data.repos.trades as trades_repo
    real_get_trade = trades_repo.get_trade

    def get_trade_with_renamed_t1(conn_inner, trade_id):
        t = real_get_trade(conn_inner, trade_id)
        if trade_id == 1 and t is not None:
            return dataclasses.replace(t, ticker="RENAMED")
        return t
    monkeypatch.setattr(
        "swing.data.repos.trades.get_trade", get_trade_with_renamed_t1,
    )

    run_warnings: list[dict] = []
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        run_warnings=run_warnings,
    )
    t1 = [e for e in run_warnings if e["ticker"] == "DHC"]
    assert t1 and t1[0]["miss_reason"] == "ticker_changed"
    assert conn.execute(
        "SELECT COUNT(*) FROM daily_management_records WHERE trade_id = 1 "
        "AND record_type = 'daily_snapshot'"
    ).fetchone()[0] == 0


def test_step_warm_empty_wins_over_concurrent_ticker_change(
    synthetic_lease_and_trades, monkeypatch,
):
    """Precedence lock (Codex R1 MAJOR #3): when the warm returns None AND the
    in-fence ticker also changed, the #27 entry reports the ROOT cause
    'warm_empty_or_stale' (warm-layer wins), NOT 'ticker_changed'. compute_*'s
    guard evaluates ticker first and would return ticker_changed, but the runner
    keeps the warm-pre-set reason because there are no usable bars regardless of
    identity.

    EXACT post-fix: trade 1's #27 entry miss_reason == 'warm_empty_or_stale'
    (NOT 'ticker_changed')."""
    import dataclasses

    import swing.data.repos.trades as trades_repo
    lease, conn = synthetic_lease_and_trades

    # Warm returns None (empty) -> runner pre-sets warm_empty_or_stale:
    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive", lambda *a, **kw: None,
    )
    # AND the in-fence ticker also changed (would yield ticker_changed if the
    # typed result were consulted):
    real_get_trade = trades_repo.get_trade

    def renamed_t1(conn_inner, trade_id):
        t = real_get_trade(conn_inner, trade_id)
        if trade_id == 1 and t is not None:
            return dataclasses.replace(t, ticker="RENAMED")
        return t
    monkeypatch.setattr("swing.data.repos.trades.get_trade", renamed_t1)

    run_warnings: list[dict] = []
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        run_warnings=run_warnings,
    )
    t1 = [e for e in run_warnings if e["ticker"] == "DHC"]
    assert t1 and t1[0]["miss_reason"] == "warm_empty_or_stale"
```

> **Note for the executor on `get_trade` patching:** the patch target above is `swing.data.repos.trades.get_trade` — the SOURCE module `compute_daily_approximate_snapshot`'s lazy `from swing.data.repos.trades import get_trade` (daily_management.py:503-504) binds at call time — NOT a `swing.trades.daily_management.get_trade` attribute (no such module-level name exists; patching it would silently no-op and the guard would never fire). Before writing the test, confirm `Trade` is a dataclass in `swing/data/models.py` so `dataclasses.replace(t, ticker="RENAMED")` works (it is, as of HEAD); if `get_trade` ever returned a non-dataclass row, reconstruct via its actual constructor instead.

Add the step-level `no_eligible_window` audit test (the warm SUCCEEDS with a non-empty frame that lacks the `asof_session` row, so the miss is in-fence and `res.miss_reason` is authoritative — both unit sub-cases are already covered in Task 1; this asserts the in-fence cause funnels to the #27 entry):

```python
def test_step_no_eligible_window_miss_reason(synthetic_lease_and_trades, monkeypatch):
    """Warm succeeds with a non-empty frame that has NO row for asof_session
    (2026-05-07) -> compute returns no_eligible_window (in-fence, authoritative)
    -> #27 entry. miss_reason is None at the runner pre-set (warm succeeded), so
    res.miss_reason is used.

    EXACT post-fix: run_warnings entries carry miss_reason='no_eligible_window';
    0 snapshots persisted."""
    lease, conn = synthetic_lease_and_trades
    # Frame has rows in [anchor, asof) but NOT the asof_session 2026-05-07:
    df_no_asof = pd.DataFrame({
        "High":  [105.0, 115.0],
        "Low":   [98.0,  102.0],
        "Close": [104.0, 113.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06"]))
    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive", lambda *a, **kw: df_no_asof,
    )
    run_warnings: list[dict] = []
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        run_warnings=run_warnings,
    )
    assert run_warnings, "expected at least one no_eligible_window skip"
    assert all(e["miss_reason"] == "no_eligible_window" for e in run_warnings)
    assert conn.execute(
        "SELECT COUNT(*) FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot'"
    ).fetchone()[0] == 0
```

> Note: DHC's anchor is 2026-05-01 and ZZ's is 2026-05-06 (the fixture's `pre_trade_locked_at` values), so for BOTH the `[anchor, asof]` window is non-empty (DHC: rows 05-05+05-06; ZZ: row 05-06) but the asof row (05-07) is absent → the absent-asof-row sub-case of `no_eligible_window` fires for both. (The empty-anchor-window sub-case is unit-covered in Task 1.)

Re-confirm `test_step_re_raises_LeaseRevoked` (already in the file) stays green — it asserts `LeaseRevokedError` propagates out of `_step_daily_management` (spec §7.5). No change needed beyond the Task-1 stub migration.

- [ ] **Step 2: Run to verify the new tests fail (where applicable) / pass**

```bash
python -m pytest tests/pipeline/test_daily_management_step.py -q
```
Expected: the parity + miss-reason tests are GREEN against the post-Task-2 tree (the behavior they assert already exists). If any fails, the wiring from Tasks 1-2 is wrong — fix before committing. (These tests lock the behavior in; they discriminate against the pre-fix tree per the documented EXACT values.)

- [ ] **Step 3: (no production change expected)** — if a test surfaces a real gap, fix the minimal production code and note it.

- [ ] **Step 4: Re-run to confirm green**

```bash
python -m pytest tests/pipeline/test_daily_management_step.py -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/pipeline/test_daily_management_step.py
git commit -m "test(pipeline): parity + all-four miss_reason + lease-revoke coverage for daily-management

Deterministic fixed-frame parity asserts the compute is behavior-preserving through the warm-hoist wiring; add warm_raised, ticker_changed, and no_eligible_window step-level skip+audit cases. Re-confirm LeaseRevokedError still propagates."
```

---

## Task 5: non-breakage of the shared fetch API + full suite + lint

**Files:**
- Create: `tests/data/test_ohlcv_archive_nonbreakage.py` — a dedicated signature/no-new-symbol assertion module
- Verify: the whole tree

- [ ] **Step 1: Write the locking test**

Create `tests/data/test_ohlcv_archive_nonbreakage.py` (a NEW dedicated module — keeps the Step-2 command unambiguous) with the non-breakage assertions (spec §7.6):

```python
import inspect

import swing.data.ohlcv_archive as archive


def test_read_or_fetch_archive_signature_unchanged():
    """The shared fetch API is byte-identical (spec §5): the daily-management
    fetch-hoist must not change read_or_fetch_archive's parameters."""
    sig = inspect.signature(archive.read_or_fetch_archive)
    params = list(sig.parameters)
    # The 4 call-shape params the warm + all 9 consumers rely on:
    assert params[0] == "ticker"
    assert "end_date" in params
    assert "cache_dir" in params
    assert "archive_history_days" in params


def test_no_new_public_symbol_added_to_ohlcv_archive():
    """OQ-2 pass-bars-in adds NO archive-API surface: SnapshotComputeResult lives
    in swing.trades.daily_management, not here."""
    assert not hasattr(archive, "SnapshotComputeResult")
    # The typed result is exported from the trades module instead:
    from swing.trades.daily_management import SnapshotComputeResult  # noqa: F401
```

> **Discrimination note:** `test_read_or_fetch_archive_signature_unchanged` would fail if a future edit altered the warm's call shape; `test_no_new_public_symbol_added_to_ohlcv_archive` would fail if the dataclass were mistakenly placed in `ohlcv_archive`. Both lock the §5 non-breakage proof. Confirm the real parameter names against `swing/data/ohlcv_archive.py:204` (`read_or_fetch_archive` definition) and adjust the asserted names to match exactly (the spec cites `cache_dir`, `end_date`, `archive_history_days`).

- [ ] **Step 2: Run to verify it passes**

```bash
python -m pytest tests/data/test_ohlcv_archive_nonbreakage.py -v
```
Expected: PASS (the API is unchanged; the dataclass is in `swing.trades.daily_management`).

- [ ] **Step 3: Re-run the §2 in-fence audit on the post-fix tree**

Manually re-confirm no `read_or_fetch_archive` / `get_or_fetch` / ladder (network) call executes inside ANY held `fenced_write` in `runner.py` (spec acceptance criterion; locus #16 flips to ✅):

```bash
grep -nE 'read_or_fetch_archive|get_or_fetch' swing/pipeline/runner.py
```
Verify the `_step_daily_management` `read_or_fetch_archive` call sits BEFORE `with lease.fenced_write()` (the warm), and the in-fence block contains only `compute_…` (no archive dir) + `upsert_snapshot` + `state_transition`.

- [ ] **Step 4: Full fast suite + lint**

```bash
python -m pytest -m "not slow" -q
ruff check swing/
```
Expected: green (baseline ≈ 7223; re-confirm the actual count on the branch — the migrations are net-neutral on count except the new tests added here and in Tasks 1-4) + ruff clean.

- [ ] **Step 5: Commit**

```bash
git add tests/data/test_ohlcv_archive_nonbreakage.py
git commit -m "test(data): lock read_or_fetch_archive non-breakage for the daily-management fetch-hoist

Assert the shared fetch API signature is unchanged and that the pass-bars-in choice added no new public symbol to swing.data.ohlcv_archive (SnapshotComputeResult lives in swing.trades.daily_management). Re-confirm no network call runs inside a held fenced_write in runner.py."
```

---

## Self-Review (run before handoff)

**1. Spec coverage:**
- §3.2 signature amendment (drop/add + return type) → Task 1. ✅
- §4.1 pure compute + `expected_ticker` guard → Task 1. ✅
- §4.2 warm-hoist + `run_warnings` + #27 funnel + typed `miss_reason` → Tasks 1 (hoist) + 2 (#27/typed). ✅
- §5 non-breakage (9 consumers, no new symbol) → Task 5. ✅
- §6 locks (LeaseRevoked re-raise, session-anchor, idempotency, F6) → preserved in Tasks 1-2; lease-revoke re-confirmed Task 4. ✅
- §7.1 lock-hold (patch BOTH namespaces, anti-false-pass) → Task 3. ✅
- §7.2 ordering (`in_fenced_write False`) → Task 3. ✅
- §7.3 deterministic parity → Task 4. ✅
- §7.4 all four `miss_reason` (incl. both `no_eligible_window` sub-cases) → Task 1 (unit, both sub-cases) + Task 4 (step). ✅
- §7.5 lease-revoke → Task 4 (re-confirm existing). ✅
- §7.6 non-breakage API → Task 5. ✅
- §7.7 six service-test migration → Task 1. ✅
- §7.8 full suite + ruff → Task 5. ✅

**2. Placeholder scan:** no "TBD"/"add error handling"/"similar to Task N"; every code step shows the code. ✅

**3. Type consistency:** `SnapshotComputeResult(fields, miss_reason)` used identically in `daily_management.py`, the runner (`res.fields`/`res.miss_reason`), the 6 service tests (`res.fields`), and the step stub (`SnapshotComputeResult(fields=…, miss_reason=None)`). `miss_reason` tokens consistent: `warm_raised` (runner-only) / `warm_empty_or_stale` / `ticker_changed` / `no_eligible_window`. ✅

---

## Acceptance criteria (executing-ready)

- [ ] `compute_daily_approximate_snapshot` signature amended (drop `ohlcv_archive_dir`/`archive_history_days`; add `archive_df`/`expected_ticker`; return `SnapshotComputeResult`); fetch import+call removed; consumes `archive_df`; `expected_ticker` guard skips on mismatch; byte-unchanged downstream of the `df` assignment.
- [ ] `_step_daily_management` warms `read_or_fetch_archive` OUTSIDE the per-trade fence (per-trade, just before its own fence); passes `archive_df` + `expected_ticker=trade.ticker`; the fence wraps only `get_trade` + `upsert_snapshot` + `state_transition`; `LeaseRevokedError` re-raises.
- [ ] `_step_daily_management` gains `run_warnings`; the call site @837 passes it; the `res.fields is None` skip emits a #27 `warnings_json` entry with a `miss_reason` ∈ {`warm_raised`, `warm_empty_or_stale`, `ticker_changed`, `no_eligible_window`}; all miss causes funnel to that one branch; no in-fence fetch on any cause.
- [ ] No `read_or_fetch_archive`/`get_or_fetch`/ladder call executes inside ANY held `fenced_write` in `runner.py` (locus #16 → ✅).
- [ ] `read_or_fetch_archive` unchanged (signature + behavior); all 9 consumers untouched; no new public symbol in `swing.data.ohlcv_archive`.
- [ ] Tasks 1-2 land TDD (test→fail→impl→pass); Tasks 3-4 land post-fix regression-locking coverage; Task 5 lands the non-breakage lock; the migrated service/step/walkthrough tests stay green; full fast suite green + `ruff check swing/` clean.
- [ ] Schema unchanged (v24); ZERO `Co-Authored-By`; conventional commits; final `-m` paragraph plain prose.

---

## Execution Handoff

Plan complete. Two execution options (a SEPARATE commission after the orchestrator QAs this plan):

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks.
2. **Inline Execution** — batch execution with checkpoints via `superpowers:executing-plans`.
