# Regular-Session + Completed-Day Data Integrity -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce that the tool only ever PULLS + LOCKS regular-session, completed-trading-day market data, closing the two contamination axes (extended-hours + current/partial-day) at the pull stage and the archive write barrier, with a date-only lock-guard backstop and a uniform topbar-date policy.

**Architecture:** Four mergeable slices in dependency order. **A** (ext-hours pull fix) sets `needExtendedHoursData=False` on Schwab `price_history`, normalizes provider float noise in the mapper, and introduces a typed `SchwabBarConsistencyError`. **C** (the keystone, depends on A) adds the completed-day write-barrier strip in `write_window`, the date-only lock-guards at `_bar_for_date` + `build_ohlc_today_json`, the pre-fix archive remediation (automatic ladder refetch-overwrite + a one-time CLI purge belt), and the anchor regression tests. **B** (quotes regular-session, gated on a live-cassette validation) requires `regularMarket*` provenance and drops to yfinance otherwise. **D** (uniform topbar, parallelizable) routes every base-layout VM's `session_date` through a `topbar_session_date(PageKind, now)` helper with a registry-enforced cross-VM test.

**Tech Stack:** Python 3.14, pandas/pyarrow (parquet archive), SQLite, schwabdev 3.0.5, FastAPI + Jinja2 (HTMX), pytest (`python -m pytest -m "not slow"`), `exchange_calendars` (XNYS). No schema change (v24 holds).

---

## Resolved open questions (LOCKED into this plan -- propagate, do not re-open)

| OQ | Resolution (operator-paired 2026-06-05) |
|---|---|
| **OQ-1b** archive remediation freshness | The Schwab ladder has NO archive-coverage short-circuit -- `fetch_window_via_ladder` re-fetches Schwab on every call; in a fresh pipeline process the in-memory TTL is empty, so the detect step (or observe's own populate) re-fetches with the L1 fix and `keep='last'` overwrites the contaminated `schwab_api` row before `resolve_ohlcv_window` reads it. **NO `force_refresh`/`min_asof` parameter is added.** BUT the auto-overwrite only covers the Schwab-SUCCESS observe run; the TTL-hit / ladder-disabled/sandbox / Schwab-failure cases leave the stale contaminated `schwab_api` row, which wins on read-precedence and (being a completed-DATE row) is selected by `_bar_for_date` and locked (the date-only guard cannot catch ext-hours). Therefore the **one-time CLI purge** (`swing schwab purge-marketdata-archive`, Task C8) is **a REQUIRED post-L1 gate step, not an optional belt** (Codex R1 MAJOR #3) -- it deterministically removes the pre-fix contamination so no failure-case observe run can lock a stale ext-hours row. C7 tests `_bar_for_date` across success/failure/post-purge. |
| **OQ-2** write-barrier chokepoint audit | RESOLVED (corrected by Codex R1 CRITICAL #1). The strip lives in **`_write_archive_atomic`** (the single lowest writer ALL four Shape-A write paths funnel through: `write_window`, `read_or_fetch_archive` 235/248, `_backward_compat_rename` 660/737). A `write_window`-only strip is UNSOUND because `resolve_ohlcv_window` runs `_backward_compat_rename` on every read (410) and `read_or_fetch_archive` persists the untrimmed fetched frame -- both would resurrect a `> cutoff` row. `write_window` keeps the F6/M3 merge logic on top of the atomic barrier (Task C1). Tests cover all four write paths. |
| **OQ-3** quote regular-session fields | Implement Slice B, **gated on a live-quote cassette validation** (Task B1, operator-run): widen `fields=` to a selection documented to return `regularMarket*`, record a live cassette, grep-assert `regularMarketLastPrice`/`regularMarketTradeTime`/regular bid/ask appear. If a symbol lacks regular-session provenance it drops to yfinance (L1-clean). No `lastPrice`/ext-hours fallback ever. |
| **OQ-4** `SchwabBarConsistencyError` placement | **Subclass `SchwabApiError`** (Task A3). It is then caught by `_call_endpoint`'s `except SchwabApiError` (marketdata.py:628) -> audit `status="error"` + `_redacted_excerpt(exc)` -> re-raised AS-IS -> the ladder's `except (SchwabAuthError, SchwabRateLimitError, SchwabApiError)` (marketdata_ladder.py:447) catches it -> clean yfinance fallback (NOT the opaque catch-all). Needs a custom `__init__` because `SchwabApiError.__init__(status_code, body_excerpt)` is positional. There is NO global `_classify_schwab_error`; classification is `_classify_http_failure(http_status)` (HTTP-only) + the explicit mapper except-chain -- the typed error needs no change there. |
| **OQ-5** Issue #3 (`_count_open_at_run`) | **OUT of this arc; banked.** Root cause confirmed: `_count_open_at_run` (capital.py:418) keys "still open at run time" on `last_fill_at >= started_ts`, but `last_fill_at` is the most-recent fill of ANY action (entry/trim/exit/stop), so a trade filled before the run but still open is wrongly excluded. The `trades` table has NO exit/terminal timestamp column; the correct fix derives `exited_at` from `fills WHERE action='exit'`. It reads ONLY `trades` (never `account_equity_snapshots` -- the integration-review hypothesis was wrong). Recorded in the OUT-of-scope note; a separate small metrics-fix brief opens AFTER this arc ships. |
| **OQ-6** float-representation noise | **No global epsilon.** `OhlcvBar.__post_init__` stays strict. The mapper rounds `open/high/low/close` to a module constant `_OHLC_ROUND_DP = 4` (finer than any equity tick) BEFORE `OhlcvBar` construction (Task A4). |
| **OQ-7** already-locked ext-hours observations | **Accepted as an L6-style limitation.** V1 is forward-only; the append-only `pattern_forward_observations.ohlc_today_json` rows already written are NOT backfilled/re-locked (L3). Documented in the OUT-of-scope note. The #23 pool-widening only began accumulating the watch population 2026-06-04, so the contaminated locked window is small. |

## Grounding deltas vs the spec (re-grepped on this checkout, HEAD 38e3bc37 -- discipline #2)

- The `price_history` call is at **marketdata.py:426-436** (spec said ~428-436); it currently omits both kwargs. The docstring at **397-402** documents them. **schwabdev 3.0.5 `Client.price_history` signature confirmed to accept `needExtendedHoursData` + `needPreviousClose`** (`inspect.signature` verified).
- The quote mapper is at **mappers.py:704-730** (spec ~706-720); it reads `lastPrice`/`bidPrice`/`askPrice` (snake_case fallbacks), NO `regularMarket*`; drops a symbol when any of last/bid/ask is None at **724/730**.
- The price-history mapper `OhlcvBar` construction is at **mappers.py:835-851**; the per-bar field extraction is wrapped in `try/except SchwabSchemaParityError` (817-841) but the `OhlcvBar(...)` append (844-851) is OUTSIDE that try -- so its `ValueError` currently propagates raw and is wrapped as `SchwabSchemaParityError` by `_call_endpoint`'s `except (ValueError, TypeError, KeyError)` (663) -> the ladder catch-all (456) "unexpected error from T-C.1 wrapper". This is the opaque-logging path the arc fixes.
- `OhlcvBar.__post_init__` invariant is at **models.py:539-551** (`low > min(open,close)` and `high < max(open,close)` raise "OhlcvBar invariant violated").
- The Schwab error taxonomy lives in **client.py:264-393** (`SchwabApiError(RuntimeError)` with `__init__(status_code, body_excerpt)`; `SchwabRateLimitError`/`SchwabAuthError` subclass it). **No global `_classify_schwab_error`** -- only `_classify_http_failure` (marketdata.py:196-209, HTTP-only).
- **The true write barrier is `_write_archive_atomic`, NOT `write_window` (Codex R1 CRITICAL #1).** `write_window` (ohlcv_archive.py:281-370) is only the Schwab-ladder-persist path. THREE OTHER write paths bypass it and call `_write_archive_atomic` (ohlcv_archive.py:99) directly: `read_or_fetch_archive` full-refresh (235) + incremental (248), and `_backward_compat_rename` (660, 737) -- and `_backward_compat_rename` is run by `resolve_ohlcv_window` on EVERY read (line 410), so a write_window-only strip can be undone (clean the yfinance parquet, then a read merges the legacy `{T}.parquet` back into Shape A, reintroducing a partial row). `read_or_fetch_archive` writes the raw `fetched`/`combined` frame WITHOUT trimming the in-progress tail before persist (only its RETURN is sliced). Therefore the hard `> cutoff` strip MUST live in `_write_archive_atomic` -- the literal single lowest writer that ALL four paths funnel through -- so every write inherits it (Task C1). `write_window` keeps the F6/M3 merge logic on top.
- **OhlcvCache freshness (OQ-1b):** `get_or_fetch` (ohlcv_cache.py:175-211) has an in-memory TTL gate only (3600s), NO archive-coverage gate, NO `force_refresh` param. `_fetch_bars_window` (ohlcv_cache.py:253-311) branches: `if self._ladder_bars_fetcher is not None:` -> Schwab ladder (writes `schwab_api.parquet`); `else:` -> `read_or_fetch_archive` (yfinance). The pipeline installs `_ladder_bars_fetcher` (runner.py:468) so detect/observe DO use the ladder. The ladder is active by default (`environment="production"` + `marketdata_ladder_enabled=True`).
- `_SOURCE_PRECEDENCE_MARKET_DATA = {"schwab_api": 0, "yfinance": 1}` (ohlcv_archive.py:56-59) -> schwab_api wins on read.
- **Slice D inventory is 33 VMs**, split into two populations: the metrics family + `AccountSnapshotFormVM` SUBCLASS `BaseLayoutVM` (view_models/metrics/shared.py:28); the rest (Dashboard, Watchlist, Journal+drilldown, Config, Pipeline, PageError, the reviews/reconcile/schwab VMs) each INDEPENDENTLY declare the 8 banner fields. The template renders `{{ vm.session_date }}` (base.html.j2:69). Full inventory in Task D2.

## L1-L6 verification (propagated, not re-opened)

- **L1** -- Slice A (`needExtendedHoursData=False`) + Slice B (`regularMarket*`, no `lastPrice`). Every Schwab market-data call site.
- **L2** -- Slice C write-barrier strip (cutoff `= last_completed_session`) + the consumer slice + the anchor tests.
- **L3** -- the lock-guards ADD rejection only; no re-fetch/regeneration of locked `ohlc_today_json`. The §5.4 remediation overwrites re-fetchable ARCHIVE cache (not locked facts).
- **L4** -- harden the existing `last_completed_session`/`action_session_for_run`/`_slice_to_asof`/`data_asof_date` machinery; no date-system rewrite. The new `topbar_session_date` is a thin classifier over the existing helpers.
- **L5** -- `needExtendedHoursData=False` is a parameter on the EXISTING `price_history` endpoint; signature-pin test (Task A1). ZERO new Schwab REST endpoints.
- **L6** -- uniform topbar policy across the authoritative base-layout VM registry (Slice D).

## Schema verdict

**NONE.** v24 holds. Pure pull/anchor/guard logic + presentation + error taxonomy. No migration.

---

## File map

**Slice A**
- Modify: `swing/integrations/schwab/client.py` (+ `SchwabBarConsistencyError`)
- Modify: `swing/integrations/schwab/marketdata.py:426-436` (the two kwargs)
- Modify: `swing/integrations/schwab/mappers.py:835-851` (round + catch->raise)
- Test: `tests/integrations/schwab/test_price_history_ext_hours.py` (new)
- Test: `tests/integrations/schwab/test_bar_consistency_error.py` (new)
- Test: `tests/integrations/schwab/test_mapper_float_normalization.py` (new)

**Slice C**
- Modify: `swing/data/ohlcv_archive.py` (`_strip_incomplete_sessions` + the strip inside `_write_archive_atomic` [the universal barrier] + `write_window` F6/M3 merge)
- Modify: `swing/pipeline/runner.py:2466` (`_bar_for_date` guard) + `:2641` (observe caller wiring)
- Modify: `swing/pipeline/temporal_metadata.py:149` (`build_ohlc_today_json` signature)
- Modify: `swing/cli_schwab.py` (+ `purge-marketdata-archive` command)
- Test: `tests/data/test_write_window_completed_day.py` (new)
- Test: `tests/data/test_read_or_fetch_archive_completed_day.py` (new)
- Test: `tests/pipeline/test_lock_guard_completed_day.py` (new)
- Test: `tests/pipeline/test_observe_remediation.py` (new)
- Test: `tests/evaluation/test_completed_day_anchors.py` (new)
- Test: `tests/cli/test_purge_marketdata_archive.py` (new)

**Slice B**
- Modify: `swing/integrations/schwab/marketdata.py` (`get_quotes_batch` `fields=` default) + callers
- Modify: `swing/integrations/schwab/mappers.py:704-730` (`map_quotes_to_price_cache_entries`)
- Test: `tests/integrations/schwab/test_quote_regular_session.py` (new)
- Test (operator-run cassette gate): `tests/integrations/schwab/cassettes/` + `test_quote_fields_live.py` (new, slow)

**Slice D**
- Modify: `swing/evaluation/dates.py` (+ `PageKind` + `topbar_session_date`)
- Modify: the 33 base-layout VMs / routes (route `session_date` through the helper)
- Test: `tests/evaluation/test_topbar_session_date.py` (new)
- Test: `tests/web/test_topbar_cross_vm_consistency.py` (new)
- Test: `tests/web/test_topbar_no_naive_anchor_lint.py` (new)

---

# Slice A -- the extended-hours pull fix (L1)

**Depends on:** nothing. Independently shippable. Directly kills the ~16% `OhlcvBar invariant violated` error rate. Gated by the operator-witnessed live re-fetch (§Gate).

### Task A1: Signature-pin the schwabdev `price_history` kwargs (L5)

**Files:**
- Test: `tests/integrations/schwab/test_price_history_ext_hours.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integrations/schwab/test_price_history_ext_hours.py
import inspect
import schwabdev


def test_price_history_signature_accepts_ext_hours_kwargs():
    """L5 signature-pin: schwabdev 3.0.5's price_history MUST accept
    needExtendedHoursData + needPreviousClose, or our wrapper's kwargs would
    raise TypeError at runtime (cassettes stub the call and won't catch it)."""
    sig = inspect.signature(schwabdev.Client.price_history)
    params = set(sig.parameters)
    assert "needExtendedHoursData" in params
    assert "needPreviousClose" in params
```

- [ ] **Step 2: Run test to verify it passes (this is a guard, not red-first)**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_price_history_ext_hours.py::test_price_history_signature_accepts_ext_hours_kwargs -v`
Expected: PASS (schwabdev 3.0.5 confirmed). If it FAILS, schwabdev dropped/renamed the kwarg -> STOP and escalate (do not ship the wrapper change).

- [ ] **Step 3: Commit**

```bash
git add tests/integrations/schwab/test_price_history_ext_hours.py
git commit -m "test(schwab): signature-pin price_history ext-hours kwargs"
```

### Task A2: Pass `needExtendedHoursData=False` + `needPreviousClose=False` on the price_history call

**Files:**
- Modify: `swing/integrations/schwab/marketdata.py:426-436`
- Test: `tests/integrations/schwab/test_price_history_ext_hours.py`

- [ ] **Step 1: Write the failing test** (append to the file from A1)

```python
def test_wrapper_passes_need_extended_hours_false(monkeypatch):
    """The wrapper's _client_method MUST forward needExtendedHoursData=False
    (and needPreviousClose=False). OLD path omitted both -> Schwab server
    default needExtendedHoursData=true folds ext-hours prints. NEW path pins
    them off."""
    import swing.integrations.schwab.marketdata as md

    captured = {}

    class _FakeClient:
        def price_history(self, symbol, **kwargs):
            captured.update(kwargs)
            captured["symbol"] = symbol
            # Return a minimal candle envelope the mapper would accept.
            return type("Resp", (), {"status_code": 200, "json": lambda self: {
                "candles": [{"datetime": 0, "open": 10.0, "high": 11.0,
                             "low": 9.0, "close": 10.5, "volume": 100}],
                "empty": False}})()

    # Drive only the inner _client_method closure: assert the kwargs reach it.
    # (See marketdata.py:_call_endpoint -> _client_method around the
    #  client.price_history call.)
    md_call = md._build_price_history_client_method(  # helper introduced below
        _FakeClient(), "AAPL",
        period_type="year", period=1, frequency_type="daily", frequency=1,
        start_dt=0, end_dt=1,
    )
    md_call()
    assert captured["needExtendedHoursData"] is False
    assert captured["needPreviousClose"] is False
```

> **Note for the implementer:** the current `_client_method` is a local closure inside the price_history wrapper (marketdata.py ~426). To make it unit-testable WITHOUT a full `_call_endpoint` run, extract the closure body into a tiny module-level helper `_build_price_history_client_method(client, symbol, *, period_type, period, frequency_type, frequency, start_dt, end_dt) -> Callable[[], Any]` that returns the thunk, and have the wrapper call it. This is a pure refactor of existing lines; keep the wrapper's behavior identical otherwise. If you prefer not to extract, replace this test with a mock-based assertion that runs the full `get_price_history` wrapper against a fake client and asserts `captured` -- either way the binding assertion is the two kwargs.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_price_history_ext_hours.py::test_wrapper_passes_need_extended_hours_false -v`
Expected: FAIL (`_build_price_history_client_method` not defined, or kwargs absent).

- [ ] **Step 3: Implement -- extract the helper + add the kwargs**

In `swing/integrations/schwab/marketdata.py`, replace the inline closure (current 426-436):

```python
def _build_price_history_client_method(
    client: Any,
    symbol: str,
    *,
    period_type: str | None,
    period: int | None,
    frequency_type: str | None,
    frequency: int | None,
    start_dt: Any,
    end_dt: Any,
) -> Callable[[], Any]:
    """Build the price_history call thunk. **camelCase BINDING -- see module
    docstring + signature-pin test.** needExtendedHoursData=False (L1:
    regular-session candles only); needPreviousClose=False (explicit -- we
    never consume previousClose; flip this kwarg alone if a future consumer
    needs it -- it does not affect candle OHLC)."""
    def _client_method() -> Any:
        return client.price_history(
            symbol,
            periodType=period_type,
            period=period,
            frequencyType=frequency_type,
            frequency=frequency,
            startDate=start_dt,
            endDate=end_dt,
            needExtendedHoursData=False,
            needPreviousClose=False,
        )
    return _client_method
```

And in the wrapper, replace the inline `def _client_method(): ...` with:

```python
    _client_method = _build_price_history_client_method(
        client, symbol,
        period_type=period_type, period=period,
        frequency_type=frequency_type, frequency=frequency,
        start_dt=start_dt, end_dt=end_dt,
    )
```

Ensure `Callable` is imported (`from typing import Any, Callable`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_price_history_ext_hours.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Run the existing marketdata suite for no regression**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/ -q`
Expected: PASS (no regression from the refactor).

- [ ] **Step 6: Commit**

```bash
git add swing/integrations/schwab/marketdata.py tests/integrations/schwab/test_price_history_ext_hours.py
git commit -m "feat(schwab): request regular-session-only price_history candles (needExtendedHoursData=False)"
```

### Task A3: Add the typed `SchwabBarConsistencyError`

**Files:**
- Modify: `swing/integrations/schwab/client.py` (after the existing exception classes, ~393)
- Test: `tests/integrations/schwab/test_bar_consistency_error.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integrations/schwab/test_bar_consistency_error.py
from swing.integrations.schwab.client import (
    SchwabApiError, SchwabBarConsistencyError,
)


def test_bar_consistency_error_is_schwab_api_error():
    """OQ-4: subclass SchwabApiError so the ladder's
    `except (SchwabAuthError, SchwabRateLimitError, SchwabApiError)` catches
    it (clean yfinance fallback, not the opaque catch-all)."""
    exc = SchwabBarConsistencyError("2026-06-04", "low (12.5) must be <= min(...)")
    assert isinstance(exc, SchwabApiError)


def test_bar_consistency_error_carries_readable_message_and_attrs():
    exc = SchwabBarConsistencyError("2026-06-04", "high (12.0) < max(open,close) (12.5)")
    assert exc.asof_date == "2026-06-04"
    # str must be readable for the audit error_message (OHLC detail carries no
    # account_hash, so a readable message is redaction-safe).
    assert "OHLC consistency" in str(exc)
    assert "2026-06-04" in str(exc)
    # SchwabApiError consumers may read these attributes.
    assert exc.status_code == 422
    assert exc.body_excerpt == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_bar_consistency_error.py -v`
Expected: FAIL (`ImportError: cannot import name 'SchwabBarConsistencyError'`).

- [ ] **Step 3: Implement** -- add to `swing/integrations/schwab/client.py` after the existing exception classes:

```python
class SchwabBarConsistencyError(SchwabApiError):
    """Raised when a mapped Schwab daily candle violates the OhlcvBar
    invariant (low/high vs open/close) -- typically an extended-hours print
    folded into a regular-session candle. Subclasses SchwabApiError so the
    market-data ladder's existing `except (SchwabAuthError,
    SchwabRateLimitError, SchwabApiError)` clause catches it and falls back to
    yfinance CLEANLY (not via the opaque catch-all). Carries a readable
    message: OHLC detail (dates + prices) contains no account_hash, so it is
    redaction-safe to echo (unlike the base class, which hides the body)."""

    def __init__(self, asof_date: str, detail: str) -> None:
        self.asof_date = asof_date
        self.detail = detail
        self.status_code = 422  # Unprocessable Entity -- bar failed validation
        self.body_excerpt = ""
        # Bypass SchwabApiError.__init__'s byte-length-only message; build a
        # readable, redaction-safe one directly on RuntimeError.
        RuntimeError.__init__(
            self, f"OHLC consistency: {detail} (date={asof_date})"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_bar_consistency_error.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/client.py tests/integrations/schwab/test_bar_consistency_error.py
git commit -m "feat(schwab): add typed SchwabBarConsistencyError (SchwabApiError subclass)"
```

### Task A4: Normalize provider float noise + raise the typed error in the price-history mapper

**Files:**
- Modify: `swing/integrations/schwab/mappers.py:835-851`
- Test: `tests/integrations/schwab/test_mapper_float_normalization.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integrations/schwab/test_mapper_float_normalization.py
import pytest
from swing.integrations.schwab.client import SchwabBarConsistencyError
from swing.integrations.schwab.mappers import map_price_history_to_window


def _envelope(open_, high, low, close):
    return {"candles": [{"datetime": 1_700_000_000_000, "open": open_,
                         "high": high, "low": low, "close": close,
                         "volume": 1000}], "empty": False, "symbol": "AAPL"}


def test_float_noise_rounds_clean():
    """M5: sub-ulp float noise must round clean (no raise). high=12.34,
    close=12.340000000001 -> post-round 12.34 == 12.34."""
    win = map_price_history_to_window(_envelope(12.30, 12.34, 12.29, 12.340000000001))
    assert win is not None
    bar = win.bars[0]
    assert bar.high == 12.34
    assert bar.close == 12.34


def test_cents_level_inconsistency_still_raises_typed():
    """A genuine ext-hours violation (high below max(open,close) by cents)
    must STILL raise -- as the typed SchwabBarConsistencyError, not a raw
    ValueError or SchwabSchemaParityError."""
    with pytest.raises(SchwabBarConsistencyError) as ei:
        map_price_history_to_window(_envelope(12.00, 12.00, 11.50, 12.50))
    assert ei.value.asof_date  # date populated
    assert "OHLC consistency" in str(ei.value)
```

> **Arithmetic check (feedback_verify_regression_test_arithmetic):** test 1 -- OLD path constructs `OhlcvBar(high=12.34, close=12.340000000001)` -> `high < max(open,close)` i.e. `12.34 < 12.340000000001` is TRUE -> raises (FAIL old). NEW path rounds close to `12.34` -> `12.34 < 12.34` FALSE -> no raise (PASS new). The test distinguishes. Test 2 -- both paths: `high=12.00 < max(12.00,12.50)=12.50` TRUE -> raise; OLD raises bare ValueError (-> wrapped SchwabSchemaParityError by _call_endpoint); NEW raises SchwabBarConsistencyError. The `pytest.raises(SchwabBarConsistencyError)` distinguishes the type.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_mapper_float_normalization.py -v`
Expected: FAIL (test 1: raw ValueError from OhlcvBar; test 2: wrong exception type -- ValueError not SchwabBarConsistencyError).

- [ ] **Step 3: Implement** -- in `swing/integrations/schwab/mappers.py`, add the module constant near the top of the file:

```python
# OQ-6: round provider floats to a fixed sub-tick precision BEFORE OhlcvBar
# construction so float-representation noise (12.34 vs 12.340000000001) never
# trips the strict invariant. 4 dp is finer than any equity tick the tool
# trades; a genuine ext-hours violation differs by cents-to-dollars and
# survives rounding.
_OHLC_ROUND_DP = 4
```

Then update the per-bar construction (current 835-851):

```python
            open_v = round(float(_require(c, "open", ctx=f"candles[{i}]")), _OHLC_ROUND_DP)
            high_v = round(float(_require(c, "high", ctx=f"candles[{i}]")), _OHLC_ROUND_DP)
            low_v = round(float(_require(c, "low", ctx=f"candles[{i}]")), _OHLC_ROUND_DP)
            close_v = round(float(_require(c, "close", ctx=f"candles[{i}]")), _OHLC_ROUND_DP)
            volume_raw = c.get("volume", 0)
            volume_v = int(volume_raw) if volume_raw is not None else 0
        except SchwabSchemaParityError:
            raise

        try:
            bars.append(OhlcvBar(
                asof_date=asof_date,
                open=open_v,
                high=high_v,
                low=low_v,
                close=close_v,
                volume=volume_v,
            ))
        except ValueError as exc:
            # OQ-4: a post-round invariant failure is a genuine bar-consistency
            # problem (typically ext-hours-folded extremes). Re-raise typed so
            # the audit row reads honestly and the ladder falls back cleanly.
            raise SchwabBarConsistencyError(asof_date, str(exc)) from exc
```

Add the import: `from swing.integrations.schwab.client import SchwabBarConsistencyError` (alongside the existing `SchwabApiError`/`SchwabSchemaParityError` imports in mappers.py).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_mapper_float_normalization.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/mappers.py tests/integrations/schwab/test_mapper_float_normalization.py
git commit -m "feat(schwab): normalize mapper float noise + raise typed SchwabBarConsistencyError"
```

### Task A5: Integration -- a contaminated candle drives the REAL wrapper -> typed error + honest audit + clean fallback

**Files:**
- Test: `tests/integrations/schwab/test_bar_consistency_production_path.py` (new)

**Why the real path (Codex R1 MAJOR #4):** the binding behavior is that `_call_endpoint` catches `SchwabApiError` (marketdata.py:628) BEFORE the `except (ValueError, TypeError, KeyError)` clause (663), so the typed error is recorded `status='error'` and re-raised AS-IS (not re-wrapped as `SchwabSchemaParityError`). A test that monkeypatches `get_price_history` to raise directly would bypass `_call_endpoint` entirely and could not detect a future re-wrap regression. So drive the REAL `get_price_history` wrapper with a fake client whose candle is ext-hours-inconsistent.

- [ ] **Step 1: Write the failing test**

```python
# tests/integrations/schwab/test_bar_consistency_production_path.py
"""A genuinely inconsistent candle (high below max(open,close)) fed through the
REAL get_price_history wrapper must: (1) raise SchwabBarConsistencyError (proving
_call_endpoint caught it as SchwabApiError, NOT re-wrapped as
SchwabSchemaParityError); (2) close the schwab_api_calls audit row with
status='error' + a message containing 'OHLC consistency'."""
import pytest

from swing.integrations.schwab.client import (
    SchwabBarConsistencyError, SchwabSchemaParityError,
)
from swing.integrations.schwab.marketdata import get_price_history
from swing.data.db import connect, run_migrations  # project's DB helpers


class _FakeClient:
    """Returns a single ext-hours-inconsistent candle (high 12.00 < close 12.50)."""
    def price_history(self, symbol, **kwargs):
        class _Resp:
            status_code = 200
            def json(self):
                return {"candles": [{"datetime": 1_700_000_000_000,
                                     "open": 12.00, "high": 12.00,
                                     "low": 11.50, "close": 12.50,
                                     "volume": 1000}], "empty": False,
                        "symbol": symbol}
        return _Resp()


def test_contaminated_candle_raises_typed_and_audits(tmp_path):
    db = tmp_path / "swing.db"
    conn = connect(db)
    run_migrations(conn)  # provides schwab_api_calls
    with pytest.raises(SchwabBarConsistencyError) as ei:
        get_price_history(
            _FakeClient(), conn, "AAPL",
            period_type="year", period=1, frequency_type="daily", frequency=1,
            start_dt=None, end_dt=None,
            surface="cli", environment="production", pipeline_run_id=None,
        )
    assert not isinstance(ei.value, SchwabSchemaParityError)  # NOT re-wrapped
    row = conn.execute(
        "SELECT status, error_message FROM schwab_api_calls "
        "ORDER BY id DESC LIMIT 1").fetchone()
    assert row[0] == "error"
    assert "OHLC consistency" in (row[1] or "")
```

> **Implementer note:** match `get_price_history`'s real parameter names + the `connect`/migration helper names (grounded: `get_price_history(client, conn, ticker, *, period_type, period, frequency_type, frequency, start_dt, end_dt, surface, environment, pipeline_run_id)`; DB helpers per `swing/data/db.py`). If the wrapper requires a non-None `start_dt`/`end_dt`, pass valid datetimes. The binding assertions: the raised type is `SchwabBarConsistencyError` and NOT `SchwabSchemaParityError`; the audit row is `status='error'` with an "OHLC consistency" message.

- [ ] **Step 2: Run test to verify it passes** (A4 made the mapper raise the typed error; A3 made it a `SchwabApiError` subclass so `_call_endpoint` catches it first)

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_bar_consistency_production_path.py -v`
Expected: PASS. If it FAILS with `SchwabSchemaParityError`, the except-clause ORDER is wrong -- verify `except SchwabApiError` precedes `except (ValueError, TypeError, KeyError)` and that `SchwabBarConsistencyError` subclasses `SchwabApiError` (A3).

- [ ] **Step 3: (Optional) ladder fallback proof** -- a small separate test asserting that when `get_price_history` raises `SchwabBarConsistencyError`, `fetch_window_via_ladder` returns `provider == "yfinance"` (the ladder's `except (..., SchwabApiError)` at 447 catches it). Match the real `fetch_window_via_ladder` signature; assert `provider == "yfinance"` + the yfinance fn was invoked.

- [ ] **Step 4: Commit**

```bash
git add tests/integrations/schwab/test_bar_consistency_production_path.py
git commit -m "test(schwab): contaminated candle -> typed error + honest audit via the real wrapper"
```

---

# Slice C -- completed-day write-barrier + lock-guard + remediation (L2/L3)

**Depends on:** Slice A (the §5.4 remediation overwrite requires the L1 pull fix live). The keystone.

### Task C1: Completed-day write barrier in `_write_archive_atomic` (the TRUE chokepoint) + `write_window` merge logic

**Files:**
- Modify: `swing/data/ohlcv_archive.py` -- new `_strip_incomplete_sessions` helper; apply it inside `_write_archive_atomic` (the universal barrier); rewrite `write_window` (281-370) with the F6/M3 merge logic on top.
- Test: `tests/data/test_write_window_completed_day.py`

**Design (Codex R1 CRITICAL #1):** the hard `> cutoff` strip lives in `_write_archive_atomic` (ohlcv_archive.py:99) -- the single lowest writer that `write_window`, `read_or_fetch_archive` (235/248), AND `_backward_compat_rename` (660/737) all funnel through. This makes it impossible for ANY write path (including the legacy-rename run on every `resolve_ohlcv_window` read) to persist or resurrect a `> cutoff` row. `write_window` keeps the merge-by-asof_date + F6/M3 logic on TOP of the barrier (it still must rewrite existing on an empty-incoming call so a pre-existing on-disk partial is stripped).

- [ ] **Step 1: Write the failing tests** (cover the barrier across ALL write paths)

```python
# tests/data/test_write_window_completed_day.py
from datetime import date
import pandas as pd
import pytest

import swing.data.ohlcv_archive as arch
from swing.data.ohlcv_archive import (
    write_window, resolve_ohlcv_window, _write_archive_atomic, _shape_a_path,
)


@pytest.fixture
def fixed_cutoff(monkeypatch):
    """Freeze the completed-session cutoff at 2026-06-04 (so 2026-06-05 is the
    'current in-progress' session) for BOTH the helper and any lazy import."""
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    return date(2026, 6, 4)


def _frame(rows):
    return pd.DataFrame(rows, columns=["asof_date", "open", "high", "low",
                                       "close", "volume"])


def test_atomic_writer_strips_after_cutoff_universal(tmp_path, fixed_cutoff):
    """The hard barrier: _write_archive_atomic itself drops > cutoff rows, so
    EVERY write path (write_window, read_or_fetch_archive, _backward_compat_
    rename) inherits it -- a > cutoff row can never land on disk."""
    path = _shape_a_path(tmp_path, "AAPL", "schwab_api")
    _write_archive_atomic(path, _frame([
        ["2026-06-04", 10, 11, 9, 10.5, 100],
        ["2026-06-05", 10, 12, 9, 11.0, 200],  # > cutoff -> stripped
    ]))
    on_disk = pd.read_parquet(path)
    assert list(on_disk["asof_date"]) == ["2026-06-04"]


def test_atomic_writer_strips_date_indexed_frame(tmp_path, fixed_cutoff):
    """Shape-agnostic: a DatetimeIndex frame (the read_or_fetch_archive shape)
    is also stripped on > cutoff."""
    path = _shape_a_path(tmp_path, "AAPL", "yfinance")
    idx = pd.to_datetime(["2026-06-04", "2026-06-05"])
    _write_archive_atomic(path, pd.DataFrame(
        {"open": [10, 10], "high": [11, 12], "low": [9, 9],
         "close": [10.5, 11], "volume": [100, 200]}, index=idx))
    on_disk = pd.read_parquet(path)
    assert on_disk.index.max().date() == date(2026, 6, 4)


def test_incoming_current_day_row_is_stripped(tmp_path, fixed_cutoff):
    win = _frame([
        ["2026-06-04", 10, 11, 9, 10.5, 100],
        ["2026-06-05", 10, 12, 9, 11.0, 200],
    ])
    write_window("AAPL", win, "schwab_api", cache_dir=tmp_path)
    df, _ = resolve_ohlcv_window("AAPL", start="2026-06-01", end="2026-06-30",
                                 cache_dir=tmp_path)
    assert list(df["asof_date"]) == ["2026-06-04"]


def test_preexisting_on_disk_current_day_row_stripped_on_empty_incoming(
        tmp_path, fixed_cutoff, monkeypatch):
    """M3: a > cutoff row already on disk is stripped even when the incoming
    window is empty. (Simulate a pre-fix raw file by writing it with the
    atomic strip DISABLED, then prove write_window cleans it.)"""
    path = _shape_a_path(tmp_path, "AAPL", "schwab_api")
    # Write a raw pre-fix file WITH a partial, bypassing the strip:
    monkeypatch.setattr(arch, "_strip_incomplete_sessions",
                        lambda df, _c: df)  # disable strip for the raw seed
    _write_archive_atomic(path, _frame([
        ["2026-06-04", 10, 11, 9, 10.5, 100],
        ["2026-06-05", 10, 12, 9, 11.0, 200],
    ]))
    monkeypatch.undo()  # re-enable the real strip
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    write_window("AAPL", _frame([]), "schwab_api", cache_dir=tmp_path)
    df, _ = resolve_ohlcv_window("AAPL", start="2026-06-01", end="2026-06-30",
                                 cache_dir=tmp_path)
    assert "2026-06-05" not in list(df["asof_date"])
    assert "2026-06-04" in list(df["asof_date"])


def test_transient_empty_incoming_preserves_valid_history(tmp_path, fixed_cutoff):
    """F6: an empty incoming window must NOT blank valid (<= cutoff) history."""
    seed = _frame([["2026-06-03", 10, 11, 9, 10.5, 100],
                   ["2026-06-04", 10, 11, 9, 10.5, 100]])
    write_window("AAPL", seed, "schwab_api", cache_dir=tmp_path)
    write_window("AAPL", None, "schwab_api", cache_dir=tmp_path)
    df, _ = resolve_ohlcv_window("AAPL", start="2026-06-01", end="2026-06-30",
                                 cache_dir=tmp_path)
    assert list(df["asof_date"]) == ["2026-06-03", "2026-06-04"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/data/test_write_window_completed_day.py -v`
Expected: FAIL (`_write_archive_atomic` does not strip; `write_window` early-returns on empty incoming).

- [ ] **Step 3a: Implement the helper + the atomic barrier** in `swing/data/ohlcv_archive.py`:

```python
def _strip_incomplete_sessions(df: pd.DataFrame, cutoff_iso: str) -> pd.DataFrame:
    """Drop archive rows dated AFTER the last completed session (cutoff_iso =
    ISO YYYY-MM-DD). Shape-agnostic: Shape-A frames carry an `asof_date` string
    column (lexical `<=` is a valid ISO-date comparison); legacy/yfinance
    frames are DatetimeIndex'd (compare `index.date`). Returns a new frame
    (may be empty). A frame with neither shape is returned unchanged."""
    if "asof_date" in df.columns:
        return df[df["asof_date"].astype(str) <= cutoff_iso]
    if isinstance(df.index, pd.DatetimeIndex):
        cutoff = date.fromisoformat(cutoff_iso)
        return df[df.index.date <= cutoff]
    return df
```

Then wrap `_write_archive_atomic` (99-114) so the strip fires on EVERY write:

```python
def _write_archive_atomic(parquet_path: Path, df: pd.DataFrame) -> None:
    # Completed-day write barrier (L2, the single chokepoint): no archive write
    # path may persist a row dated after the last completed session. Applied
    # here -- the one function ALL Shape-A writers funnel through (write_window,
    # read_or_fetch_archive, _backward_compat_rename) -- so none can bypass it.
    df = _strip_incomplete_sessions(df, _last_completed_session_today().isoformat())
    cache_dir = parquet_path.parent
    fd, tmp_name = tempfile.mkstemp(
        dir=str(cache_dir), prefix=f"{parquet_path.stem}.", suffix=".parquet.tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        df.to_parquet(tmp_path)
        os.replace(tmp_path, parquet_path)
    except Exception:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise
```

> `date` is already imported in ohlcv_archive.py (used by `_last_completed_session_today`'s callers). `_last_completed_session_today` is module-level (164-169). Confirm no callsite passes a frame that legitimately needs a future-dated row written (none do -- the archive is strictly historical).

- [ ] **Step 3b: Rewrite `write_window` (281-370)** with the F6/M3 merge logic ON TOP of the barrier:

```python
def write_window(
    ticker: str,
    window: pd.DataFrame | None,
    provider: str,
    *,
    cache_dir: Path,
) -> None:
    """Atomically write a Shape A window, merging with any pre-existing rows by
    `asof_date` (keep='last'). The hard completed-day strip lives in
    `_write_archive_atomic` (every write inherits it); this function adds the
    merge + the M3 guarantee (rewrite existing on an empty incoming so a
    pre-existing on-disk partial is stripped) + F6 (never blank valid history
    on a transient empty fetch)."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _shape_a_path(cache_dir, ticker, provider)
    cutoff_iso = _last_completed_session_today().isoformat()

    # --- normalize incoming to a DataFrame-or-None ---
    incoming: pd.DataFrame | None = window
    if incoming is not None and not isinstance(incoming, pd.DataFrame):
        try:
            is_empty = len(incoming) == 0
        except TypeError:
            raise TypeError(
                f"write_window expects pd.DataFrame, got {type(window).__name__}")
        if is_empty:
            incoming = None
        else:
            raise TypeError(
                f"write_window expects pd.DataFrame, got {type(window).__name__}")
    if isinstance(incoming, pd.DataFrame) and incoming.empty:
        incoming = None

    # --- read existing ---
    existing: pd.DataFrame | None = None
    if path.exists():
        try:
            existing = pd.read_parquet(path)
        except (OSError, ValueError) as exc:  # pragma: no cover - defensive
            log.warning("write_window: failed to read existing %s (%s)", path, exc)
            existing = None

    if incoming is None and existing is None:
        return

    # legacy REPLACE for non-Shape-A incoming (dedup needs the asof_date key);
    # the atomic strip still fires inside _write_archive_atomic.
    if incoming is not None and "asof_date" not in incoming.columns:
        _write_archive_atomic(path, incoming)
        return

    # cheap no-op: empty incoming + existing already has no > cutoff rows.
    if incoming is None and existing is not None and "asof_date" in existing.columns:
        if len(_strip_incomplete_sessions(existing, cutoff_iso)) == len(existing):
            return

    frames = [f for f in (existing, incoming)
              if f is not None and "asof_date" in f.columns]
    if not frames:
        return
    union = pd.concat(frames) if len(frames) > 1 else frames[0]
    merged = union.drop_duplicates(subset=["asof_date"], keep="last")
    merged = merged.sort_values("asof_date").reset_index(drop=True)
    # The atomic writer applies the > cutoff strip; an all-partial union writes
    # clean (no > cutoff survives), a valid union preserves <= cutoff history.
    _write_archive_atomic(path, merged)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/data/test_write_window_completed_day.py -v`
Expected: PASS (all five).

- [ ] **Step 5: Run the existing archive suite for no regression** (the atomic strip now fires on every write -- confirm no existing test seeds a future-dated archive row it then expects back)

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/data/ -q -k "archive or ohlcv or write_window or backward_compat"`
Expected: PASS. If a pre-existing test seeds a `> last_completed_session(now)` row and expects it persisted, it was relying on the (now-closed) hole -- update it to a `<= cutoff` date or `monkeypatch` `_last_completed_session_today` to cover the seeded date.

- [ ] **Step 6: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_write_window_completed_day.py
git commit -m "feat(data): completed-day write barrier in _write_archive_atomic (universal strip)"
```

### Task C2: Prove the barrier covers the yfinance `read_or_fetch_archive` path

**Files:**
- Test: `tests/data/test_read_or_fetch_archive_completed_day.py`

**Why a real regression (Codex R1 MAJOR #2):** `read_or_fetch_archive` writes the raw `fetched`/`combined` frame WITHOUT trimming the in-progress tail (only its RETURN is sliced) -- so before C1 it WOULD persist a current-day yfinance bar. After C1, the atomic-writer strip removes it. This test distinguishes old (partial persisted) from new (stripped).

- [ ] **Step 1: Write the test**

```python
# tests/data/test_read_or_fetch_archive_completed_day.py
from datetime import date
import pandas as pd

import swing.data.ohlcv_archive as arch
from swing.data.ohlcv_archive import read_or_fetch_archive, _shape_a_path


def test_yfinance_fetch_never_persists_after_cutoff(tmp_path, monkeypatch):
    """Even when yfinance returns an in-progress (> cutoff) bar, the atomic
    barrier (Task C1) strips it before persist. OLD: read_or_fetch_archive
    persisted the raw fetched frame incl. the 06-05 bar. NEW: the on-disk
    archive holds no row > cutoff."""
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))

    def _fake_yf(ticker, *, start, end):
        idx = pd.to_datetime(["2026-06-03", "2026-06-04", "2026-06-05"])
        return pd.DataFrame({"open": [10, 10, 10], "high": [11, 11, 12],
                             "low": [9, 9, 9], "close": [10.5, 10.5, 11],
                             "volume": [100, 100, 200]}, index=idx)
    monkeypatch.setattr(arch, "_yf_download_window", _fake_yf)

    read_or_fetch_archive("AAPL", end_date=date(2026, 6, 4),
                          cache_dir=tmp_path, archive_history_days=400)
    on_disk = pd.read_parquet(_shape_a_path(tmp_path, "AAPL", "yfinance"))
    last = (on_disk.index.max().date() if isinstance(on_disk.index, pd.DatetimeIndex)
            else date.fromisoformat(str(on_disk["asof_date"].max())))
    assert last <= date(2026, 6, 4)
```

> **Implementer note:** match `_yf_download_window`'s real keyword signature (grounded: `(ticker, *, start, end)`) and the on-disk shape (DatetimeIndex per grounding). The binding assertion: no on-disk row dated after the cutoff.

- [ ] **Step 2: Run test**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/data/test_read_or_fetch_archive_completed_day.py -v`
Expected: PASS (via the C1 atomic strip).

- [ ] **Step 3: Commit**

```bash
git add tests/data/test_read_or_fetch_archive_completed_day.py
git commit -m "test(data): prove the atomic barrier strips the yfinance fetch path"
```

### Task C3: Date-only lock-guard at `_bar_for_date`

**Files:**
- Modify: `swing/pipeline/runner.py:2466` (top of `_bar_for_date`, before the populate/read)
- Test: `tests/pipeline/test_lock_guard_completed_day.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_lock_guard_completed_day.py
from datetime import date
import pytest

import swing.pipeline.runner as runner


def test_bar_for_date_rejects_current_day(monkeypatch, tmp_path):
    """L3 date-only guard: _bar_for_date must refuse an observation_date that
    is not <= last_completed_session(now). Catches a wiring regression that
    would lock a partial/in-progress bar."""
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))

    class _Cache:
        def get_or_fetch(self, **k):
            raise AssertionError("must raise BEFORE any fetch")

    cfg = runner_cfg_stub(tmp_path)  # minimal cfg with paths.prices_cache_dir
    with pytest.raises(ValueError, match="not a completed session"):
        runner._bar_for_date(cfg, _Cache(), "AAPL", "2026-06-05")


def test_bar_for_date_allows_completed_day(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))
    # A completed-day observation_date passes the guard (then proceeds to the
    # normal archive read, which returns None for an empty cache -> acceptable).
    cfg = runner_cfg_stub(tmp_path)

    class _Cache:
        def get_or_fetch(self, **k):
            return None
    assert runner._bar_for_date(cfg, _Cache(), "AAPL", "2026-06-04") is None
```

> **Implementer note:** `runner_cfg_stub` -- use the project's existing test config factory (search `tests/pipeline/conftest.py` for a `cfg`/`make_cfg` fixture that supplies `paths.prices_cache_dir`); reuse it rather than hand-rolling. The binding assertion is the guard fires for `2026-06-05` and passes for `2026-06-04`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/pipeline/test_lock_guard_completed_day.py -v`
Expected: FAIL (no guard; `_Cache.get_or_fetch` AssertionError or a None return without raising).

- [ ] **Step 3: Implement** -- add at the TOP of `_bar_for_date` (runner.py:2466), before the `get_or_fetch` populate:

```python
    from datetime import date, datetime, timedelta
    # L3 date-only guard: never select a bar for the current in-progress
    # session. observation_date MUST be <= last_completed_session(now). In
    # normal operation observation_date == data_asof_date == the completed
    # session, so this never fires; it catches a wiring regression.
    cutoff = last_completed_session(datetime.now())
    if date.fromisoformat(observation_date) > cutoff:
        raise ValueError(
            f"_bar_for_date: observation_date {observation_date} is not a "
            f"completed session (cutoff {cutoff.isoformat()}); refusing to "
            f"select a partial/in-progress bar for the append-only log"
        )
```

> `last_completed_session` is already module-imported in runner.py (used at line 541). Merge the local `from datetime import ...` with the existing one at the top of `_bar_for_date` (it imports `date, timedelta`; add `datetime`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/pipeline/test_lock_guard_completed_day.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_lock_guard_completed_day.py
git commit -m "feat(pipeline): date-only completed-day lock-guard at _bar_for_date"
```

### Task C4: Date-only lock-guard at `build_ohlc_today_json` + caller wiring

**Files:**
- Modify: `swing/pipeline/temporal_metadata.py:149` (`build_ohlc_today_json` signature)
- Modify: `swing/pipeline/runner.py:2641` (the observe caller passes `observation_date` + `cutoff`)
- Test: `tests/pipeline/test_lock_guard_completed_day.py` (append)

- [ ] **Step 1: Write the failing test** (append)

```python
from datetime import date as _date
from swing.pipeline.temporal_metadata import build_ohlc_today_json


def test_build_ohlc_today_json_rejects_non_completed_day():
    bar = {"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
           "volume": 100.0, "provider": "schwab_api"}
    with pytest.raises(ValueError, match="non-completed-session"):
        build_ohlc_today_json(bar, observation_date="2026-06-05",
                              cutoff=_date(2026, 6, 4))


def test_build_ohlc_today_json_allows_completed_day():
    bar = {"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
           "volume": 100.0, "provider": "schwab_api"}
    out = build_ohlc_today_json(bar, observation_date="2026-06-04",
                                cutoff=_date(2026, 6, 4))
    assert '"open": 10.0' in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/pipeline/test_lock_guard_completed_day.py -k build_ohlc_today_json -v`
Expected: FAIL (`build_ohlc_today_json()` got an unexpected keyword argument 'observation_date').

- [ ] **Step 3: Implement** -- extend the signature in `swing/pipeline/temporal_metadata.py:149`:

```python
def build_ohlc_today_json(
    bar: dict, *, observation_date: str, cutoff: date,
) -> str:
    """Validated serializer for ohlc_today_json. Construction-barrier guard:
    refuses to serialize a bar for a non-completed session (date-only; L3) so
    no partial/in-progress bar enters the append-only log. Then validates the
    key set + provider domain as before."""
    if date.fromisoformat(observation_date) > cutoff:
        raise ValueError(
            f"ohlc_today_json: refusing to lock a non-completed-session bar "
            f"({observation_date} > {cutoff.isoformat()})"
        )
    missing = [k for k in _OHLC_TODAY_KEYS if k not in bar]
    if missing:
        raise ValueError(f"ohlc_today_json missing keys: {missing}")
    if bar["provider"] not in _OHLC_TODAY_PROVIDERS:
        raise ValueError(
            f"ohlc_today_json provider must be one of {_OHLC_TODAY_PROVIDERS}, "
            f"got {bar['provider']!r}"
        )
    return json.dumps({k: bar[k] for k in _OHLC_TODAY_KEYS})
```

`date` is already imported in temporal_metadata.py (used by `_slice_to_asof`).

- [ ] **Step 4: Wire the caller** -- in `swing/pipeline/runner.py:_step_pattern_observe` (~2558 computes `observation_date`; ~2641 calls the serializer). Compute the cutoff once and pass both:

```python
    # near the observation_date computation (~2558):
    cutoff = last_completed_session(datetime.now())
    # ... at the insert_observation call (~2641):
        ohlc_today_json=build_ohlc_today_json(
            bar, observation_date=observation_date, cutoff=cutoff,
        ),
```

- [ ] **Step 5: Run tests + the observe-step suite**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/pipeline/test_lock_guard_completed_day.py -v && python -m pytest tests/pipeline/ -q -k "observe or temporal or ohlc_today"`
Expected: PASS. Fix any existing `build_ohlc_today_json(bar)` callers/tests to the new keyword signature (grep `build_ohlc_today_json(` across `swing/` + `tests/` and update each).

- [ ] **Step 6: Commit**

```bash
git add swing/pipeline/temporal_metadata.py swing/pipeline/runner.py tests/pipeline/test_lock_guard_completed_day.py
git commit -m "feat(pipeline): completed-day construction-barrier guard at build_ohlc_today_json"
```

### Task C5: Guard-boundary proof -- the date-only guard does NOT validate ext-hours (C2 boundary)

**Files:**
- Test: `tests/pipeline/test_lock_guard_completed_day.py` (append)

- [ ] **Step 1: Write the test**

```python
def test_guard_passes_completed_date_ext_hours_contaminated_bar():
    """C2 boundary doc-test: a COMPLETED-DATE bar whose high is an ext-hours
    print (above the regular high but still >= max(open,close)) PASSES both
    lock-guards. The guard is DATE-ONLY -- it cannot and does not validate
    ext-hours provenance (that is owned by the pull stage + archive
    cleanliness). Reviewers must not over-trust the guard."""
    # high=13.0 is an ext-hours-inflated extreme, but the bar is internally
    # consistent (low <= min(o,c) <= max(o,c) <= high) and dated <= cutoff.
    bar = {"open": 10.0, "high": 13.0, "low": 9.0, "close": 10.5,
           "volume": 100.0, "provider": "schwab_api"}
    out = build_ohlc_today_json(bar, observation_date="2026-06-04",
                                cutoff=_date(2026, 6, 4))
    assert '"high": 13.0' in out  # the guard PASSES it (date-only)
```

- [ ] **Step 2: Run test**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/pipeline/test_lock_guard_completed_day.py -k ext_hours_contaminated -v`
Expected: PASS (documents the boundary).

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_lock_guard_completed_day.py
git commit -m "test(pipeline): document the date-only guard boundary (ext-hours not validated)"
```

### Task C6: Completed-day anchor regression tests (representative clocks)

**Files:**
- Test: `tests/evaluation/test_completed_day_anchors.py`

- [ ] **Step 1: Write the tests**

```python
# tests/evaluation/test_completed_day_anchors.py
from datetime import datetime
from swing.evaluation.dates import last_completed_session, action_session_for_run


def _hst(y, m, d, hh, mm):
    # naive local HST datetime as the helpers expect (tz applied internally).
    return datetime(y, m, d, hh, mm)


def test_last_completed_session_never_names_in_progress():
    # 2026-06-04 is a Thursday (NYSE session). HST is ET-6 (DST) / -5; the
    # helper converts internally. Pre-open ET -> prior session; post-close ->
    # today; weekend -> Friday.
    pre_open = last_completed_session(_hst(2026, 6, 4, 2, 0))    # ~08:00 ET (before close)
    assert pre_open.isoformat() < "2026-06-04"
    post_close = last_completed_session(_hst(2026, 6, 4, 12, 0))  # ~18:00 ET (after close)
    assert post_close.isoformat() == "2026-06-04"
    # Saturday -> last completed is Friday 06-05? (06-06 is Sat) -- use a known
    # weekend: 2026-06-06 is Saturday.
    weekend = last_completed_session(_hst(2026, 6, 6, 12, 0))
    assert weekend.isoformat() == "2026-06-05"


def test_action_vs_completed_diverge_post_close():
    """Post-close on a session day, action (forward) names the NEXT session
    while completed (backward) names today -- the divergence Slice D relies
    on."""
    t = _hst(2026, 6, 4, 12, 0)  # post-close ET
    assert action_session_for_run(t) != last_completed_session(t)
```

> **Arithmetic check:** verify each expected date against the XNYS calendar before locking the literals -- run `python -c "import exchange_calendars as x; c=x.get_calendar('XNYS'); print(c.is_session('2026-06-04'), c.is_session('2026-06-06'))"` and adjust the asserted dates to real sessions. The binding property is "last_completed_session never returns the in-progress session; action and completed diverge post-close." If 2026-06-04/05/06 are not the right session/weekend mix, substitute known dates and keep the properties.

- [ ] **Step 2: Run tests**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/evaluation/test_completed_day_anchors.py -v`
Expected: PASS (pins existing helper behavior; no production change).

- [ ] **Step 3: Commit**

```bash
git add tests/evaluation/test_completed_day_anchors.py
git commit -m "test(evaluation): completed-day anchor regression across representative clocks"
```

### Task C7: Pre-fix remediation -- `_bar_for_date` across Schwab success / failure / post-purge (OQ-1b)

**Files:**
- Test: `tests/pipeline/test_observe_remediation.py`

**The honest model (Codex R1 MAJOR #3):** `_bar_for_date` calls `ohlcv_cache.get_or_fetch(...)` (a best-effort populate), then reads the date-anchored bar via `resolve_ohlcv_window`. The remediation has TWO regimes:
- **Schwab-SUCCESS observe run:** the ladder re-fetches Schwab with the L1 fix and `keep='last'` overwrites the contaminated `schwab_api` row BEFORE the read -> clean lock. (Proven by `test_success_path` below.)
- **TTL-hit / ladder-disabled / Schwab-FAILURE run:** no fresh Schwab overwrite happens; the stale contaminated `schwab_api` row remains and wins on read-precedence (schwab_api=0 > yfinance=1) -> `_bar_for_date` returns the CONTAMINATED bar (the date-only guard cannot catch ext-hours). This residual gap is closed deterministically by the one-time purge (Task C8): after purge, `resolve_ohlcv_window` has no `schwab_api` row and falls to the clean yfinance row. (Proven by `test_failure_path_then_purge` below.)

- [ ] **Step 1: Write the tests**

```python
# tests/pipeline/test_observe_remediation.py
from datetime import date
import pandas as pd

import swing.data.ohlcv_archive as arch
from swing.data.ohlcv_archive import (
    write_window, resolve_ohlcv_window, _write_archive_atomic, _shape_a_path,
)
import swing.pipeline.runner as runner

COLS = ["asof_date", "open", "high", "low", "close", "volume"]


def _seed_contaminated_schwab(tmp_path):
    # a pre-fix ext-hours-inflated (high=99) schwab_api row for the obs date.
    _write_archive_atomic(_shape_a_path(tmp_path, "AAPL", "schwab_api"),
                          pd.DataFrame([["2026-06-04", 10, 99, 9, 10.5, 100]],
                                       columns=COLS))


def _cfg(tmp_path):
    return runner_cfg_stub(tmp_path)  # supplies paths.prices_cache_dir = tmp_path


def test_success_path_overwrites_contaminated_before_lock(tmp_path, monkeypatch):
    """Schwab-success: the populate refetches clean (L1) -> keep='last'
    overwrites -> _bar_for_date returns the clean bar."""
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))
    _seed_contaminated_schwab(tmp_path)

    class _Cache:
        def get_or_fetch(self, *, ticker, window_days):
            # emulate the ladder's clean L1 Schwab refetch + persist.
            write_window(ticker, pd.DataFrame(
                [["2026-06-04", 10, 11, 9, 10.5, 100]], columns=COLS),
                "schwab_api", cache_dir=tmp_path)
            return pd.DataFrame()  # return value unused by _bar_for_date's read
    bar = runner._bar_for_date(_cfg(tmp_path), _Cache(), "AAPL", "2026-06-04")
    assert bar is not None and bar["high"] == 11   # clean, not 99
    assert bar["provider"] == "schwab_api"


def test_failure_path_then_purge_falls_to_clean_yfinance(tmp_path, monkeypatch):
    """Schwab-failure/TTL-hit: the populate does NOT overwrite; the stale
    contaminated schwab_api row wins on precedence -> _bar_for_date returns it
    (the residual gap). After the C8 purge removes *.schwab_api.parquet,
    _bar_for_date falls to the clean yfinance row."""
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))
    _seed_contaminated_schwab(tmp_path)
    # a clean yfinance row also exists (lower precedence).
    write_window("AAPL", pd.DataFrame([["2026-06-04", 10, 11, 9, 10.5, 100]],
                                      columns=COLS), "yfinance", cache_dir=tmp_path)

    class _NoOpCache:
        def get_or_fetch(self, *, ticker, window_days):
            return pd.DataFrame()  # Schwab failed / TTL hit -> no overwrite
    # BEFORE purge: contaminated schwab_api wins.
    bar = runner._bar_for_date(_cfg(tmp_path), _NoOpCache(), "AAPL", "2026-06-04")
    assert bar["high"] == 99   # documents the residual gap
    # purge (the C8 belt) -> schwab_api gone -> clean yfinance wins.
    _shape_a_path(tmp_path, "AAPL", "schwab_api").unlink()
    bar2 = runner._bar_for_date(_cfg(tmp_path), _NoOpCache(), "AAPL", "2026-06-04")
    assert bar2["high"] == 11 and bar2["provider"] == "yfinance"
```

> **Implementer note:** reuse the project's `runner_cfg_stub`/`cfg` fixture (Task C3). The two tests pin the BINDING contract: success auto-overwrites; failure leaves the stale row that ONLY the purge clears. This makes the purge (C8) a required remediation step, not cosmetic.

- [ ] **Step 2: Run tests**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/pipeline/test_observe_remediation.py -v`
Expected: PASS (both regimes).

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_observe_remediation.py
git commit -m "test(pipeline): remediation regimes -- success auto-overwrite + failure needs purge"
```

### Task C8: One-time CLI purge -- REQUIRED post-L1 remediation gate (`swing schwab purge-marketdata-archive`)

> **NOT optional** (Codex R1 MAJOR #3): the auto-overwrite (C7) only covers the Schwab-success observe run. The purge is the deterministic remediation for the TTL-hit / ladder-disabled / Schwab-failure cases where a stale contaminated `schwab_api` row would otherwise win on precedence and be locked. It runs ONCE post-L1-ship as a binding gate step (§Gate step 3).

**Files:**
- Modify: `swing/cli_schwab.py` (+ a `purge-marketdata-archive` click command)
- Test: `tests/cli/test_purge_marketdata_archive.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_purge_marketdata_archive.py
from pathlib import Path
from click.testing import CliRunner

from swing.cli import cli  # the root click group


def test_purge_deletes_only_schwab_api_parquets(tmp_path, monkeypatch):
    """Deterministic belt: deletes *.schwab_api.parquet so a later access
    re-fetches clean; leaves yfinance parquets untouched. L3-safe (archive is
    re-fetchable cache, not locked facts)."""
    cache = tmp_path / "prices"
    cache.mkdir()
    (cache / "AAPL.schwab_api.parquet").write_bytes(b"x")
    (cache / "MSFT.schwab_api.parquet").write_bytes(b"x")
    (cache / "AAPL.yfinance.parquet").write_bytes(b"y")
    monkeypatch.setenv("SWING_PRICES_CACHE_DIR_OVERRIDE", str(cache))  # see note

    runner = CliRunner()
    result = runner.invoke(cli, ["schwab", "purge-marketdata-archive", "--yes"])
    assert result.exit_code == 0
    assert not (cache / "AAPL.schwab_api.parquet").exists()
    assert not (cache / "MSFT.schwab_api.parquet").exists()
    assert (cache / "AAPL.yfinance.parquet").exists()  # yfinance preserved
    assert "2" in result.output  # reports the count deleted
```

> **Implementer note:** resolve the cache dir from the loaded `cfg.paths.prices_cache_dir` (the canonical source), NOT a bespoke env var -- the `SWING_PRICES_CACHE_DIR_OVERRIDE` above is a placeholder. Use the project's standard CLI cfg-loading + a test cfg fixture/monkeypatch that points `paths.prices_cache_dir` at `tmp_path/prices` (mirror how other `swing schwab` subcommands obtain `cfg`). Keep the `--yes` flag to skip the interactive confirm in tests; default (no `--yes`) prompts `click.confirm`. The command MUST refuse while a pipeline `state='running'` row exists (mirror `SchwabPipelineActiveError` gating used by other write-ish schwab subcommands) -- it mutates the shared archive.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/cli/test_purge_marketdata_archive.py -v`
Expected: FAIL (no such command).

- [ ] **Step 3: Implement** -- add to `swing/cli_schwab.py` (register under the `schwab` group):

```python
@schwab.command("purge-marketdata-archive")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def purge_marketdata_archive(ctx: click.Context, yes: bool) -> None:
    """One-time belt (OQ-1b): delete every `*.schwab_api.parquet` so the next
    access re-fetches clean (regular-session) Schwab bars. Use ONCE after the
    L1 ext-hours fix ships, to clear pre-fix ext-hours-contaminated archive
    rows that read-precedence would otherwise keep serving. L3-safe: the
    archive is re-fetchable cache, NOT append-only locked facts; the
    pattern_forward_observations log is untouched."""
    cfg = _load_cfg(ctx)  # the module's standard cfg loader
    _refuse_if_pipeline_running(cfg)  # SchwabPipelineActiveError shared helper
    cache_dir = Path(cfg.paths.prices_cache_dir)
    targets = sorted(cache_dir.glob("*.schwab_api.parquet"))
    if not targets:
        click.echo("No *.schwab_api.parquet files to purge.")
        return
    if not yes:
        click.confirm(f"Delete {len(targets)} schwab_api archive file(s)?",
                      abort=True)
    for p in targets:
        p.unlink()
    click.echo(f"Purged {len(targets)} schwab_api archive file(s); next access "
               f"re-fetches clean.")
```

> Use the module's actual cfg loader + pipeline-active guard helpers (search `cli_schwab.py` for the existing `_load_cfg`/`SchwabPipelineActiveError` usage and reuse them; do not invent new names).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/cli/test_purge_marketdata_archive.py -v`
Expected: PASS.

- [ ] **Step 5: Encoding-safety check (Windows cp1252)** -- confirm the command's echo strings are ASCII (no fancy glyphs). Run the CLI help through PowerShell once:

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m swing.cli schwab purge-marketdata-archive --help`
Expected: clean help text, no `UnicodeEncodeError`.

- [ ] **Step 6: Commit**

```bash
git add swing/cli_schwab.py tests/cli/test_purge_marketdata_archive.py
git commit -m "feat(cli): one-time purge-marketdata-archive belt for pre-fix schwab bars"
```

---

# Slice B -- quotes regular-session (L1)

**Depends on:** OQ-3 field-availability re-validation FIRST (Task B1), else the Schwab quote path goes dead. Quotes feed ONLY ephemeral display + CLI `--verify-marketdata` (no locked surface).

### Task B1: Live-quote field validation + widen `fields=` (operator-run gate)

**Files:**
- Modify: `swing/integrations/schwab/marketdata.py` (`get_quotes_batch` `fields=` default + callers)
- Test (slow, operator-run): `tests/integrations/schwab/test_quote_fields_live.py` + a recorded cassette

- [ ] **Step 1: Decide + set the `fields=` selection.** Schwab's `/quotes` returns the `regularMarket*` block in the standard `quote` field group. Set the wrapper default so the regular-session fields are guaranteed returned. In `swing/integrations/schwab/marketdata.py`, change the `get_quotes_batch` default:

```python
def get_quotes_batch(
    client: Any,
    conn: sqlite3.Connection,
    symbols: list[str],
    *,
    surface: str,
    environment: str,
    pipeline_run_id: int | None = None,
    fields: str | None = "quote",   # ensure regularMarket* block is returned
) -> dict[str, SchwabQuoteResponse]:
```

(If grounding the live response shows `regularMarket*` only under `"all"`, use `"all"`; B1's cassette test decides.)

- [ ] **Step 2: Write the operator-run live/cassette test** (marked slow; recorded once against a live quote):

```python
# tests/integrations/schwab/test_quote_fields_live.py
import pytest

pytestmark = pytest.mark.slow


def test_recorded_quote_carries_regular_session_fields():
    """OQ-3 validation: a recorded live quote (cassette) MUST contain
    regularMarketLastPrice + regularMarketTradeTime (+ regular bid/ask). If
    absent under the chosen fields= selection, Slice B's drop-to-yfinance rule
    makes EVERY Schwab quote fall back to yfinance -- widen fields= until they
    appear, or the Schwab quote path is dead."""
    from pathlib import Path
    cassette = Path(__file__).parent / "cassettes" / "quote_regular_fields.yaml"
    assert cassette.exists(), "record the live quote cassette first (runbook)"
    text = cassette.read_text()
    assert "regularMarketLastPrice" in text
    assert "regularMarketTradeTime" in text
```

- [ ] **Step 3: Gate note (operator).** Recording the cassette requires a LIVE Schwab quote (operator's env) -- it is a Slice-B precondition, run like the live re-fetch gate. The implementer does NOT record it against the live env; the operator records it and confirms `regularMarket*` appear, then the cassette is committed. Until the cassette confirms the fields, Slice B's B2/B3 ship behind this validation (B2 is L1-correct either way -- it just drops to yfinance more often if the fields are absent).

- [ ] **Step 4: Commit (the fields= default + the test scaffold)**

```bash
git add swing/integrations/schwab/marketdata.py tests/integrations/schwab/test_quote_fields_live.py
git commit -m "feat(schwab): select quote fields that return regularMarket* (OQ-3 validation gate)"
```

### Task B2: `map_quotes_to_price_cache_entries` -- require regular-session provenance, drop to yfinance

**Files:**
- Modify: `swing/integrations/schwab/mappers.py:704-730`
- Test: `tests/integrations/schwab/test_quote_regular_session.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integrations/schwab/test_quote_regular_session.py
from swing.integrations.schwab.mappers import map_quotes_to_price_cache_entries


def _resp(symbol, body):
    return {symbol: {"symbol": symbol, "quote": body}}  # match the real envelope


def test_only_ext_hours_lastprice_is_dropped():
    """M1: a quote with ONLY lastPrice (no regularMarketLastPrice) is DROPPED
    (yfinance fallback) -- lastPrice is the ext-hours print (L1). A sentinel
    lastPrice that, if surfaced, would fail the assertion."""
    out = map_quotes_to_price_cache_entries(_resp("AAPL", {
        "lastPrice": 999.99,  # ext-hours sentinel -- must NEVER surface
        "bidPrice": 999.0, "askPrice": 1000.0,
    }))
    assert "AAPL" not in out  # dropped


def test_regular_last_with_regular_bid_ask_emits_regular_value():
    out = map_quotes_to_price_cache_entries(_resp("AAPL", {
        "lastPrice": 999.99,  # ext-hours -- must be ignored
        "regularMarketLastPrice": 150.25,
        "regularMarketTradeTime": 1_700_000_000_000,
        "regularMarketBidPrice": 150.20, "regularMarketAskPrice": 150.30,
    }))
    assert "AAPL" in out
    entry = out["AAPL"]
    assert entry.last_price == 150.25     # regular, not 999.99
    assert entry.last_price != 999.99


def test_regular_last_but_ext_hours_bid_ask_is_dropped():
    """A regular last present but NO regular bid/ask provenance -> drop (do not
    surface the extended-book bid/ask). See spec 4.2."""
    out = map_quotes_to_price_cache_entries(_resp("AAPL", {
        "regularMarketLastPrice": 150.25,
        "regularMarketTradeTime": 1_700_000_000_000,
        "bidPrice": 149.0, "askPrice": 151.0,  # ext-hours book only
    }))
    assert "AAPL" not in out  # dropped (no regular bid/ask)
```

> **Implementer note:** match the ACTUAL quote envelope the mapper consumes (grounded at mappers.py:704 -- it reads `body = ...`; confirm whether the regular fields sit under a `"quote"` sub-dict or the top level, and shape `_resp` accordingly). The three binding behaviors: (1) only-`lastPrice` -> drop; (2) `regularMarketLastPrice` + regular bid/ask -> emit the regular last; (3) regular last but ext-hours-only bid/ask -> drop.

> **Arithmetic check:** test 2 -- OLD path reads `lastPrice=999.99` -> emits 999.99; NEW path reads `regularMarketLastPrice=150.25` and never reads lastPrice -> emits 150.25. `assert entry.last_price == 150.25` distinguishes. test 1 -- OLD emits (last/bid/ask all present) -> "AAPL" in out; NEW drops (no regular last) -> "AAPL" not in out. Distinguishes.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_quote_regular_session.py -v`
Expected: FAIL (current mapper reads `lastPrice`/`bidPrice`/`askPrice`).

- [ ] **Step 3: Implement** -- replace the field reads in `map_quotes_to_price_cache_entries` (704-730):

```python
        # L1: require regular-session provenance. NEVER read lastPrice/
        # bidPrice/askPrice -- they carry the ext-hours book during pre/post
        # market. A missing regular field drops the symbol -> yfinance fallback.
        last_price = body.get("regularMarketLastPrice")
        if last_price is None:
            last_price = body.get("regular_market_last_price")  # snake_case fwd-compat
        bid = body.get("regularMarketBidPrice")
        if bid is None:
            bid = body.get("regular_market_bid_price")
        ask = body.get("regularMarketAskPrice")
        if ask is None:
            ask = body.get("regular_market_ask_price")
        mark = body.get("mark")
        quote_time_raw = (
            body.get("regularMarketTradeTime")
            or body.get("regular_market_trade_time")
        )
        delayed_raw = body.get("delayed")

        # Drop the symbol unless full regular-session provenance is present
        # (last AND bid AND ask). No ext-hours value ever surfaces (L1).
        if last_price is None or bid is None or ask is None:
            _log.info(
                "map_quotes_to_price_cache_entries: dropping %s "
                "(missing regular-session last/bid/ask)",
                symbol,
            )
            continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/integrations/schwab/test_quote_regular_session.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/mappers.py tests/integrations/schwab/test_quote_regular_session.py
git commit -m "feat(schwab): require regular-session provenance in quote mapper (drop to yfinance)"
```

### Task B3: CLI `--verify-marketdata` consumes the regular-session mapper (regression)

**Files:**
- Test: `tests/integrations/schwab/test_quote_regular_session.py` (append) OR `tests/cli/test_verify_marketdata_quotes.py`

- [ ] **Step 1: Write the test** -- assert the verify path surfaces only regular-session quotes (a symbol with only ext-hours data is reported as dropped/yfinance, never with the ext-hours last). Mirror the existing `--verify-marketdata` test harness (search `tests/` for it) and feed a quote batch with one regular + one ext-hours-only symbol; assert the regular surfaces and the ext-hours-only one falls back.

- [ ] **Step 2: Run + Commit**

```bash
git add tests/cli/test_verify_marketdata_quotes.py
git commit -m "test(cli): verify-marketdata surfaces only regular-session quotes"
```

---

# Slice D -- uniform topbar-date policy (L6, Issue #5)

**Depends on:** nothing (parallelizable). Presentation-only; operator browser gate.

### Task D1: `PageKind` + `topbar_session_date` helper

**Files:**
- Modify: `swing/evaluation/dates.py`
- Test: `tests/evaluation/test_topbar_session_date.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/evaluation/test_topbar_session_date.py
from datetime import datetime
from swing.evaluation.dates import (
    PageKind, topbar_session_date, action_session_for_run, last_completed_session,
)


def test_forward_planning_uses_action_session():
    now = datetime(2026, 6, 4, 12, 0)  # post-close ET so the families diverge
    assert topbar_session_date(PageKind.FORWARD_PLANNING, now) == \
        action_session_for_run(now)


def test_history_analysis_uses_last_completed_session():
    now = datetime(2026, 6, 4, 12, 0)
    assert topbar_session_date(PageKind.HISTORY_ANALYSIS, now) == \
        last_completed_session(now)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/evaluation/test_topbar_session_date.py -v`
Expected: FAIL (`ImportError: cannot import name 'PageKind'`).

- [ ] **Step 3: Implement** -- add to `swing/evaluation/dates.py`:

```python
from enum import Enum


class PageKind(Enum):
    """Topbar-date intent for a base-layout page."""
    FORWARD_PLANNING = "forward"   # what to do at the next session
    HISTORY_ANALYSIS = "backward"  # what happened through the last completed session


def topbar_session_date(page_kind: PageKind, now_local: datetime) -> date:
    """The single source of truth for a base-layout topbar date (L6/Issue #5).

    FORWARD_PLANNING -> action_session_for_run (the next session).
    HISTORY_ANALYSIS -> last_completed_session (the last closed session).
    Eliminates the naive date.today()/datetime.now().date() third family.
    """
    if page_kind is PageKind.FORWARD_PLANNING:
        return action_session_for_run(now_local)
    return last_completed_session(now_local)
```

- [ ] **Step 4: Run test to verify it passes + Commit**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/evaluation/test_topbar_session_date.py -v`
Expected: PASS.

```bash
git add swing/evaluation/dates.py tests/evaluation/test_topbar_session_date.py
git commit -m "feat(evaluation): topbar_session_date(PageKind) classifier"
```

### Task D2: Route every base-layout VM's `session_date` through the helper

**Files:** the 33 VMs/routes below. **Classification:** FORWARD_PLANNING = `{DashboardVM, WatchlistVM}`; everything else = HISTORY_ANALYSIS ("the page is about the last completed session").

**Authoritative inventory (re-grepped this checkout):**

| VM / route | file:line | current anchor | target PageKind |
|---|---|---|---|
| DashboardVM | view_models/dashboard.py:1534 | action_session_for_run | **FORWARD_PLANNING** (keep) |
| WatchlistVM | view_models/watchlist.py:217 | action_session_for_run | **FORWARD_PLANNING** (keep) |
| JournalVM | view_models/journal.py:252 | `date.today()` | HISTORY_ANALYSIS (fix) |
| JournalVM drill-down | view_models/journal.py:557 (`_base_banner_fields`) | `date.today()` | HISTORY_ANALYSIS (fix) |
| ConfigPageVM | view_models/config.py:170 | `date.today()` | HISTORY_ANALYSIS (fix) |
| PipelineVM | view_models/pipeline.py:71 | `datetime.now().date()` | HISTORY_ANALYSIS (fix) |
| PageErrorVM | app.py:507 | action_session_for_run (fallback "n/a") | HISTORY_ANALYSIS (fix; keep "n/a" fallback) |
| ReviewVM | view_models/trades.py:1351 | last_completed_session | HISTORY_ANALYSIS (keep) |
| ReviewsPendingVM | view_models/trades.py:1523 | last_completed_session | HISTORY_ANALYSIS (keep) |
| CadenceCompleteVM | view_models/trades.py:1387 | last_completed_session | HISTORY_ANALYSIS (keep) |
| ReconcileDiscrepancyResolveVM | view_models/reconcile.py:782 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| ReconcileDiscrepancyErrorVM | routes/reconcile.py:89 | action_session_for_run (fallback "n/a") | HISTORY_ANALYSIS (fix) |
| SchwabSetupVM | routes/schwab.py:224 | action_session_for_run (fallback "n/a") | HISTORY_ANALYSIS (fix) |
| SchwabStatusVM | routes/schwab.py:565 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| SchwabSetupErrorVM | routes/schwab.py:165 | action_session_for_run (fallback "n/a") | HISTORY_ANALYSIS (fix) |
| AccountSnapshotFormVM | routes/account.py:65 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| MetricsIndexVM | view_models/metrics/index.py:437 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| CapitalFrictionVM | view_models/metrics/capital_friction.py:106 | action_session_for_run | HISTORY_ANALYSIS (fix; data already backward) |
| DeviationOutcomeVM | view_models/metrics/deviation_outcome.py:101 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| HypothesisProgressCardVM | view_models/metrics/hypothesis_progress_card.py:430 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| IdentificationFunnelVM | view_models/metrics/identification_funnel.py:84 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| MaturityStageVM | view_models/metrics/maturity_stage.py:80 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| ProcessGradeTrendVM | view_models/metrics/process_grade_trend.py:665 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| TierComparisonVM | view_models/metrics/tier_comparison.py:103 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| TradeProcessCardVM | view_models/metrics/trade_process_card.py:191 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| PatternExemplarsVM | view_models/patterns/exemplars.py:397 | action_session_for_run | HISTORY_ANALYSIS (fix) |
| PatternOutcomesVM | view_models/patterns/outcomes_card.py:45 (via index.py:305) | action_session_for_run | HISTORY_ANALYSIS (fix) |
| PatternQueueVM | routes/patterns.py:117 (`_session_date_str`) | last_completed_session | HISTORY_ANALYSIS (keep) |
| PatternReviewFormVM | routes/patterns.py:385 (`_session_date_str`) | last_completed_session | HISTORY_ANALYSIS (keep) |

> The remaining rows from the 33-count are drill-down/error VMs sharing one of the above setters -- when you touch the setter, they inherit the fix. **Before coding, re-grep `session_date` across `swing/web/` and reconcile against this table** -- Codex flagged a standalone base-layout-fields declaration at `view_models/reconcile.py:100` that must be in the manifest. The D3 completeness test (`MANIFEST ⊇ all BaseLayoutVM subclasses`) + the D4 AST lint enforce that nothing is missed; add any newly-found VM to the D3 MANIFEST and route its setter.

- [ ] **Step 1: For EACH row, replace the anchor expression with the helper.** The mechanical edit, per callsite:

```python
from swing.evaluation.dates import PageKind, topbar_session_date

# FORWARD_PLANNING pages (Dashboard, Watchlist) -- keep forward but via helper:
session_date = topbar_session_date(PageKind.FORWARD_PLANNING, datetime.now()).isoformat()

# HISTORY_ANALYSIS pages (everything else):
session_date = topbar_session_date(PageKind.HISTORY_ANALYSIS, datetime.now()).isoformat()
```

For VMs that currently build the value inline in a dataclass field or a banner dict (e.g. journal's `_base_banner_fields`, the metrics `BaseLayoutVM` subclasses' constructors, the patterns `_session_date_str`), set the same expression at that site. Preserve any existing `try/except -> "n/a"` fallback wrappers (PageErrorVM, the error VMs) -- wrap the helper call, not replace the fallback.

**Intermediate-variable callsites (Codex R1 MAJOR #5):** where a VM computes an anchor into a local var first (e.g. Dashboard `action_session = action_session_for_run(now)` then `session_date=action_session.isoformat()` at dashboard.py:1534), route the LOCAL VAR through the helper: `action_session = topbar_session_date(PageKind.FORWARD_PLANNING, datetime.now())`. This keeps any data-side use of that var consistent AND satisfies the D4 AST provenance lint. Do NOT leave a raw `action_session_for_run(...)`/`last_completed_session(...)` feeding `session_date` even via a variable.

- [ ] **Step 2: Add a `PAGE_KIND` class attribute to each base-layout VM** (for the registry test in D3). Example:

```python
@dataclass(frozen=True)
class JournalVM:
    PAGE_KIND = PageKind.HISTORY_ANALYSIS  # class-level, not a dataclass field
    ...
```

For `BaseLayoutVM` subclasses (metrics + account), add `PAGE_KIND = PageKind.HISTORY_ANALYSIS` on each subclass (Dashboard/Watchlist get `FORWARD_PLANNING`).

- [ ] **Step 3: Run the web suite for no regression after each cluster** (do the edits in clusters -- metrics, patterns, reviews/reconcile/schwab/account, the standalone Dashboard/Watchlist/Journal/Config/Pipeline/PageError -- committing per cluster):

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/web/ -q`
Expected: PASS per cluster.

- [ ] **Step 4: Commit per cluster** (e.g.)

```bash
git add swing/web/view_models/metrics/ tests/web/
git commit -m "refactor(web): route metrics VM topbar dates through topbar_session_date (backward)"
# ... repeat per cluster ...
```

### Task D3: Explicit-manifest cross-VM consistency test (Codex R1 MAJOR #5)

**Files:**
- Test: `tests/web/test_topbar_cross_vm_consistency.py`

**Why a manifest, not `__subclasses__()` alone:** `BaseLayoutVM.__subclasses__()` only sees modules already imported, and the standalone VMs (Dashboard, Journal, reconcile's standalone-banner VM at view_models/reconcile.py:100, etc.) do NOT subclass it. So the test uses an EXPLICIT MANIFEST (the D2 inventory) imported at the top -- which both forces every VM module to load AND lets a completeness assertion verify the manifest covers every discovered `BaseLayoutVM` subclass (a new metrics subclass that is not added to the manifest fails the test).

- [ ] **Step 1: Write the test**

```python
# tests/web/test_topbar_cross_vm_consistency.py
"""Issue #5: at a single frozen `now`, same-kind base-layout pages agree on the
topbar session_date, and the naive date.today()/now().date() family is gone.
NOW is a post-close evening on a session day so forward != backward."""
from datetime import datetime

from swing.evaluation.dates import (
    PageKind, action_session_for_run, last_completed_session,
)
# Force-import EVERY base-layout VM module (also makes __subclasses__ complete):
from swing.web.view_models.metrics.shared import BaseLayoutVM
from swing.web.view_models.dashboard import DashboardVM
from swing.web.view_models.watchlist import WatchlistVM
from swing.web.view_models.journal import JournalVM
from swing.web.view_models.config import ConfigPageVM
from swing.web.view_models.pipeline import PipelineVM
from swing.web.view_models.trades import (
    ReviewVM, ReviewsPendingVM, CadenceCompleteVM,
)
# ... import the remaining standalone + metrics + patterns VMs from D2 ...

NOW = datetime(2026, 6, 4, 20, 0)  # post-close ET evening on a session day

# The AUTHORITATIVE manifest -- every base-layout VM + its declared PageKind.
# Mirror the D2 inventory table EXACTLY (33 entries).
MANIFEST = {
    DashboardVM: PageKind.FORWARD_PLANNING,
    WatchlistVM: PageKind.FORWARD_PLANNING,
    JournalVM: PageKind.HISTORY_ANALYSIS,
    ConfigPageVM: PageKind.HISTORY_ANALYSIS,
    PipelineVM: PageKind.HISTORY_ANALYSIS,
    ReviewVM: PageKind.HISTORY_ANALYSIS,
    ReviewsPendingVM: PageKind.HISTORY_ANALYSIS,
    CadenceCompleteVM: PageKind.HISTORY_ANALYSIS,
    # ... the full 33 from D2 (metrics, patterns, reconcile, schwab, account,
    #     PageErrorVM, journal drill-down if a distinct class) ...
}


def _all_base_layout_subclasses():
    seen, stack = set(), list(BaseLayoutVM.__subclasses__())
    while stack:
        c = stack.pop()
        if c not in seen:
            seen.add(c)
            stack.extend(c.__subclasses__())
    return seen


def test_manifest_covers_every_base_layout_subclass():
    """Completeness: any BaseLayoutVM subclass (post force-import) MUST be in
    the manifest -- a new metrics tile cannot evade the policy."""
    missing = _all_base_layout_subclasses() - set(MANIFEST)
    assert not missing, f"base-layout VMs missing from MANIFEST: {missing}"


def test_every_vm_declares_matching_page_kind():
    for cls, kind in MANIFEST.items():
        assert getattr(cls, "PAGE_KIND", None) is kind, \
            f"{cls.__name__} PAGE_KIND != {kind}"


def test_representative_vms_render_the_right_anchor(monkeypatch):
    """Construct one VM per family at frozen NOW and assert the rendered
    session_date matches the declared kind's anchor (not a naive date)."""
    forward = action_session_for_run(NOW).isoformat()
    backward = last_completed_session(NOW).isoformat()
    assert forward != backward
    # Freeze now in dates.py so topbar_session_date resolves against NOW.
    import swing.evaluation.dates as dates
    monkeypatch.setattr(dates, "datetime",
                        type("D", (), {"now": staticmethod(lambda: NOW)}))
    # Build the representatives via their real constructors/builders (use the
    # project's VM test fixtures). Example shape:
    #   dash = build_dashboard_vm(...);  assert dash.session_date == forward
    #   journ = build_journal_vm(...);   assert journ.session_date == backward
    #   metric = build_metrics_index_vm(...); assert metric.session_date == backward
    # Assert each != datetime.now().date().isoformat() unless it equals an anchor.
    # (Construct at least: Dashboard [forward], Journal + a metrics VM + a
    #  reviews VM + Pipeline [backward].)
```

> **Implementer note:** complete the imports + `MANIFEST` to the full 33 from D2. For `test_representative_vms_render_the_right_anchor`, monkeypatch each VM module's `datetime.now` (or `dates.datetime`) to return `NOW` and build 5-6 representatives via the project's existing VM builders/fixtures (grep `tests/web/` for how each is constructed). The completeness + PAGE_KIND tests run with zero construction; the representative render test is the behavioral proof.

- [ ] **Step 2: Run + Commit**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/web/test_topbar_cross_vm_consistency.py -v`
Expected: PASS.

```bash
git add tests/web/test_topbar_cross_vm_consistency.py
git commit -m "test(web): explicit-manifest topbar cross-VM consistency + completeness"
```

### Task D4: AST provenance lint -- `session_date` must originate from `topbar_session_date`

**Files:**
- Test: `tests/web/test_topbar_provenance_lint.py`

**Why AST, not regex (Codex R1 MAJOR #5):** the regex misses the intermediate-variable pattern that ALREADY exists (Dashboard computes `action_session = action_session_for_run(...)` then `session_date=action_session` at dashboard.py:1534). An AST pass resolves the local-variable provenance of each `session_date` assignment and flags any whose value does not trace to a `topbar_session_date(...)` call.

- [ ] **Step 1: Write the test**

```python
# tests/web/test_topbar_provenance_lint.py
"""Backstop: every `session_date` value assigned in the web layer must trace to
a topbar_session_date(...) call -- directly OR through a local variable bound in
the same function. Catches the intermediate-variable evasion the regex missed."""
import ast
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "swing" / "web"
_BANNED_CALLS = {"action_session_for_run", "last_completed_session"}
_BANNED_NAIVE = {"today"}  # date.today()
_GOOD = "topbar_session_date"


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            return f.attr
    return None


def _provenance_ok(value: ast.AST, local_defs: dict[str, ast.AST]) -> bool:
    """True if `value` (the RHS assigned to session_date, possibly .isoformat()
    chained) traces to topbar_session_date, resolving one level of local var."""
    # unwrap `.isoformat()` / attribute calls to the base call/name
    node = value
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        node = node.func.value
    if _call_name(node) == _GOOD:
        return True
    if isinstance(node, ast.Name):
        bound = local_defs.get(node.id)
        if bound is not None:
            return _provenance_ok(bound, {})  # one resolution hop
    return False


def _offenders_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local_defs = {}
        for stmt in ast.walk(fn):
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        local_defs[t.id] = stmt.value
        for stmt in ast.walk(fn):
            # session_date as a keyword (VM(...session_date=X)) or assignment
            kwvals = []
            if isinstance(stmt, ast.Call):
                kwvals += [kw.value for kw in stmt.keywords
                           if kw.arg == "session_date"]
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id == "session_date":
                        kwvals.append(stmt.value)
            for v in kwvals:
                if not _provenance_ok(v, local_defs):
                    out.append(f"{path.name}:{getattr(v,'lineno','?')}")
    return out


def test_session_date_traces_to_topbar_helper():
    offenders = []
    for path in WEB.rglob("*.py"):
        offenders += _offenders_in(path)
    assert not offenders, (
        "session_date must trace to topbar_session_date(...):\n" + "\n".join(offenders))
```

> **Implementer note:** this AST scan is a heuristic; tune it against the REAL post-D2 callsites until green (the import-time `"n/a"` fallbacks in PageErrorVM/error VMs wrap the helper -- ensure `_provenance_ok` accepts a `topbar_session_date(...)` inside a `try` or a ternary; extend the unwrap to handle those shapes). The intent is binding: no `session_date` value may originate from a raw anchor or naive date. Where a VM has a genuinely non-topbar field literally named `session_date` (none found in the D2 inventory), rename it. Keep the simpler text-regex lint from the prior draft as an ADDITIONAL cheap layer if desired.

- [ ] **Step 2: Run + Commit**

Run: `cd .worktrees/data-integrity-arc-writing-plans && python -m pytest tests/web/test_topbar_provenance_lint.py -v`
Expected: PASS (after D2 routes every site through the helper, including the Dashboard intermediate-variable case -- which D2 changes to `action_session = topbar_session_date(PageKind.FORWARD_PLANNING, now)`).

```bash
git add tests/web/test_topbar_provenance_lint.py
git commit -m "test(web): AST provenance lint -- session_date originates from topbar_session_date"
```

---

## Self-review checklist (run before handing to executing-plans)

**Spec coverage:**
- §2 AUDIT spine -> Slices A (P1/P2), C (P3/L-A/L-B/L-C), D (anchor surfaces). P4/P5 documented (P5 pinned by C2). ✓
- §4 ext-hours fix -> A2 (price_history) + B2 (quotes). ✓
- §5 completed-day -> C1 (write_window strip) + C2 (yfinance safety) + C6 (anchors) + C7/C8 (remediation). ✓
- §6 lock-guard -> C3 (`_bar_for_date`) + C4 (`build_ohlc_today_json`) + C5 (boundary proof). ✓
- §7 topbar -> D1-D4. ✓
- §8 Issue #3 -> OUT (OQ-5 banked, root cause recorded). ✓
- §9 OhlcvBar/error taxonomy -> A3 (typed error) + A4 (float norm) + A5 (fallback proof). ✓
- §10 tests/gate -> per-task tests + §Gate below. ✓
- §11 schema -> NONE. ✓

**Placeholder scan:** no "TBD"/"handle edge cases"/"similar to Task N" -- each step shows code or an exact command. Implementer-notes flag where a callsite shape must be matched to real code (signatures grounded; the notes name the exact functions). ✓

**Type consistency:** `SchwabBarConsistencyError(asof_date, detail)` used identically in A3/A4/A5; `topbar_session_date(PageKind, datetime)` in D1/D2/D3; `build_ohlc_today_json(bar, *, observation_date, cutoff)` in C4/C5; `_strip_incomplete_sessions(df, cutoff_iso)` in C1. ✓

## Gate sequencing (binding -- §10.8)

1. **Fast suite green on the MERGED HEAD** -- re-run on main after merge; isolate the known xdist date-flakes (`feedback_no_false_green_claim`). Never carry a branch pass-count forward.
2. **Operator browser gate (Slice D)** -- topbar consistency across pages, light + dark; the D3 cross-VM test backs it. Witness one page per family agreeing on the date.
3. **Operator-witnessed LIVE Schwab re-fetch (post-merge; like schwabdev GATE-B)** -- after Slice A, confirm on `/schwab/status` the `OhlcvBar invariant violated` / bar-consistency rate collapses from ~16% toward ~0%, AND witness the UNSEEDED normal pipeline run (`feedback_seeded_gate_masks_default_state`). **REQUIRED remediation step:** run `swing schwab purge-marketdata-archive` ONCE (C8) post-L1 to clear pre-fix contaminated `schwab_api` rows the failure-case observe runs would otherwise lock; confirm the next pipeline run repopulates clean. This is binding, not optional (Codex R1 MAJOR #3).
4. **Slice B precondition** -- the operator records the live quote cassette (B1) and confirms `regularMarket*` appear before B2/B3 are trusted in production.

The implementer does NOT run the live fetch against the operator's DB -- it is the operator's gate.

## Out of scope (do NOT build into V1)

- Issue #3's fix (`_count_open_at_run`): a metrics historical-reconstruction predicate bug. Recommended fix recorded (OQ-5): derive `exited_at` from `fills WHERE action='exit'` (the `trades` table has no terminal-timestamp column) and key the "still open at started_ts" clause on it, NOT `last_fill_at`. Separate small brief AFTER this arc.
- Already-LOCKED ext-hours observations (`ohlc_today_json` rows already written): accepted L6-style limitation (OQ-7); V1 forward-only; the lock is append-only (L3).
- Schwab Phase B/C; a date-system rewrite (L4); intraday precision; provenance-as-schema (v24 holds).

---

*End of plan. Four slices in dependency order A -> C -> B -> D: ext-hours pull fix (needExtendedHoursData=False + mapper float-normalization + typed SchwabBarConsistencyError) -> completed-day write-barrier in write_window + date-only lock-guards + the automatic refetch-overwrite remediation and the one-time purge belt -> quotes regular-session (gated on a live cassette) -> uniform topbar_session_date(PageKind) across the 33-VM authoritative registry. The guard is date-only (a proof-test documents the boundary); the mapper normalizes floats with no global epsilon; NO schema. The binding gate is the operator-witnessed live Schwab re-fetch confirming the ~16% error rate collapses.*
