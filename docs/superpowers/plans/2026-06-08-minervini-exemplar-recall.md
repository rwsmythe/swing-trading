# Minervini Correct-Entry Exemplar-Recall Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research harness that answers, for each of Minervini's documented correct-entry exemplars, whether our screening pipeline would have surfaced it (H1: `bucket_for` -> aplus/watch) and whether any of the 5 V1 detectors would have fired (H2: geometric_score > 0, class-matched), evaluated strictly point-in-time around the locked entry session.

**Architecture:** Approach A — thin harness modules over frozen pure-leaf imports (`evaluate_one`, `compute_rs`, `generate_candidate_windows`, `current_stage`, `_pattern_detect_registry`). The harness opens NO production `swing.db` (H1 is pure on `CandidateContext`; equity = $7500 floor surrogate; the detector Stage-2 gate is satisfied by TWO physically separate synthetic SQLite DBs built via the production migration runner). OHLCV comes from local Tiingo CSVs. Exactly ONE `swing/cli.py` registration (`swing diagnose minervini-recall`). L2 LOCK: the harness import graph imports none of yfinance / schwabdev / `swing.integrations.schwab` / `swing.data.ohlcv_archive`.

**Tech Stack:** Python 3.14, pandas, sqlite3 (stdlib), click (CLI), argparse (harness entry), pytest (`tests/research/minervini_exemplar_recall/`), stdlib `random`/`statistics`/`csv`/`json`. Source-of-truth leaf imports from `swing.evaluation.*`, `swing.patterns.foundation`, `swing.pipeline.runner`, `swing.data.repos.candidates`, `swing.data.db`, `swing.data.models`, `swing.config`.

---

## Binding disciplines (apply to EVERY task)

- **Research carve-out:** all new code lives under `research/harness/minervini_exemplar_recall/` and the one-off `research/scripts/materialize_vicr_yfinance.py`. The ONLY `swing/` edit in this whole plan is the single CLI registration in `swing/cli.py` (Task 12). No other `swing/` change.
- **TDD per task:** write the failing test, run it and SEE it fail with the expected message, write the minimal implementation, run it and SEE it pass, commit. Never write implementation before its failing test.
- **Regression-test-arithmetic:** every discriminating test names the value the assertion would take under the WRONG (pre-fix) path AND under the correct (post-fix) path, so the test genuinely distinguishes them. These are called out inline as `WRONG-PATH:` / `RIGHT-PATH:`.
- **ASCII-only output:** every string written to a file or printed to stdout must be cp1252-encodable (no section-sign, arrows, em-dash, smart quotes, fractions). Use `-` for dashes, `->` for arrows, `vs` not the times-sign. The output writers assert `text.encode("cp1252")` before writing.
- **Commits:** conventional (`feat(research):`, `test(research):`, `docs(research):`, `chore(research):`). NO `Co-Authored-By` footer. NO `--no-verify`. Keep the final `-m` paragraph plain prose (no leading `Word:` token that git parses as a trailer). After each commit run `git log -1 --format='%(trailers)'` and confirm the output is empty.
- **No deferred placeholders:** every step below contains the real code/command the engineer runs.

---

## File Structure

All paths relative to repo root `c:\Users\rwsmy\swing-trading`.

### New harness package — `research/harness/minervini_exemplar_recall/`
(already contains `__init__.py`, `tiingo_pull.py`, `qa_compare.py`, `qa_montage.py`; this plan ADDS the evaluator modules)

| File | Responsibility |
|---|---|
| `__init__.py` | Package docstring + `__version__` bump to `"0.1.0"` (currently a data-acq-only package). |
| `constants.py` | `H2_MIN_BARS = 60`, `CONTROL_GAP_BARS = 120`, `DEFAULT_CONTROL_SEED = 20260608`, `EQUITY_FLOOR_SURROGATE = 7500.0`, `screenable_floor(config)` helper. |
| `exceptions.py` | `MinerviniRecallError` base + `TiingoArchiveMissingError`, `TiingoCoverageError`, `MalformedExemplarRowError`, `MalformedAsofDateError`. |
| `ohlcv_reader.py` | Tiingo CSV -> capitalized adjusted OHLCV on a `DatetimeIndex`; `SYMBOL_OVERRIDE` + `tiingo_symbol`; `read_full` / `slice_to` / `read_sliced(min_bars=...)`. |
| `exemplar_reader.py` | `ExemplarRow` dataclass; parse CSV; filter `curated == "yes"`; `entry_anchor` + `date_precision`; resolve `tiingo_symbol`. |
| `rs_proxy.py` | `RsProxyOutcome`; build `BatchContext` — P0 `fallback_spy`, P1 TT8-NA degenerate; per-exemplar path flag. |
| `screen_eval.py` | H1 core: `ScreenResult`, `GateAttribution`; `classify_h1_outcome`, `attribute_first_rejecting_gate`, `evaluate_h1`. |
| `stage_db.py` | Throwaway SQLite (schema via production migration runner); `build_stage_db`, `seed_session` (faithful/isolated), `stage_at`. |
| `detector_eval.py` | H2 core: `DetectorVerdict`; `select_window` (`windows[-1]`); `run_detectors`, `evaluate_h2`; skip taxonomy; anchor-mode-limited flag. |
| `timing.py` | `SessionEval`, `ExemplarTimingResult`; `sweep_sessions` (positional); `evaluate_exemplar` (single-session + window-sweep best-of; orchestrates H1 -> stage seed -> H2). |
| `control_cohort.py` | `ControlAnchor`; `sample_control_anchors` (same-ticker, >=120bd from entry, deterministic); `evaluate_control` (both modes, mode-to-mode). |
| `scorecard.py` | `wilson_interval`, `_clustered_resample` + `ticker_clustered_bootstrap`, `Scorecard`, `build_scorecard`. |
| `output.py` | `write_results_csv`, `write_per_session_csv`, `write_summary_md`, `write_manifest_json`, `write_h2_all_windows_csv`; ASCII guard. |
| `run.py` | `run_harness(...)` + argparse `main`; delegated to by the single CLI registration. |

### Out-of-harness one-off
| File | Responsibility |
|---|---|
| `research/scripts/materialize_vicr_yfinance.py` | Imports yfinance; pulls VICR >= 1990; writes `research/data/tiingo/VICR.csv` in Tiingo column format + a `VICR.provenance.txt` sidecar. NEVER imported by the harness. |

### One `swing/` edit
| File | Responsibility |
|---|---|
| `swing/cli.py` | Add `diagnose minervini-recall` command (mirrors `aplus-sensitivity-v2`; deferred import; `ValueError -> click.ClickException`; NO `--db`). |

### Tests — `tests/research/minervini_exemplar_recall/`
`__init__.py` + `test_ohlcv_reader.py`, `test_exemplar_reader.py`, `test_rs_proxy.py`, `test_screen_eval.py`, `test_stage_db.py`, `test_detector_eval.py`, `test_timing.py`, `test_control_cohort.py`, `test_scorecard.py`, `test_output.py`, `test_run_cli.py`, `test_l2_lock.py`, `test_tiingo_pull_spy.py`, `test_materialize_vicr.py`, `test_integration.py` (slow).

### Config / docs
- `.gitignore` — add a negation block allowlisting `exports/research/minervini-exemplar-recall-*/` small artifacts.
- `research/method-records/minervini-exemplar-recall.md` (Task 17).
- `research/studies/2026-06-08-minervini-exemplar-recall.md` (Task 18).

---

## Key interface facts (verified against the codebase 2026-06-08)

These were confirmed by reading the source; the plan's code depends on them.

- `evaluate_one(ctx: CandidateContext) -> Candidate` (`swing/evaluation/evaluator.py:35`). `Candidate.bucket: str` in `{"aplus","watch","skip"}` (bucket_for never emits error/excluded). `Candidate.criteria: tuple[CriterionResult, ...]` — 18 items (8 `layer="trend_template"`, 9 `layer="vcp"`, 1 `layer="risk"`).
- `CriterionResult(criterion_name, layer, result, value=None, rule=None)` (`swing/data/models.py:127`). `result` in `{"pass","fail","na"}`.
- Contexts (`swing/evaluation/context.py`, all frozen, NO defaults):
  - `BatchContext(returns_12w_by_ticker: dict[str,float], universe_tickers: tuple[str,...], universe_version: str, universe_hash: str, spy_return_12w: float)`.
  - `MarketContext()` (empty).
  - `CandidateContext(ticker: str, ohlcv: pd.DataFrame, config: Config, batch: BatchContext, market: MarketContext, current_equity: float)`. `ohlcv` columns capitalized `Open/High/Low/Close/Volume`, ascending `DatetimeIndex`.
- `bucket_for` order (`swing/evaluation/scoring.py:19-39`): risk any non-pass -> skip; then `tt_passes < min_passes` -> skip; then any TT fail name not in `allowed_miss_names` -> skip; then `vcp_fails` (count of vcp `result in ("fail","na")`): 0 -> aplus, 1-2 -> watch, >2 -> skip.
- `compute_rs(ticker, returns_12w_by_ticker, universe_tickers, *, spy_return) -> RSResult` (`swing/evaluation/rs.py:52`). Returns `method="unavailable"` FIRST (`rs.py:65`) when `ticker not in returns_12w_by_ticker` — before touching spy_return. `RSResult(method, rank, return_vs_spy)`. TT8 fallback (`trend_template.py`): pass if `return_vs_spy >= fallback_extreme_pct/100`, fail if `<= -fallback_extreme_pct/100`, else na.
- Config defaults (`Config.from_defaults()` loads `swing.config.toml`): `trend_template.min_passes=7`, `trend_template.allowed_miss_names=("TT8_rs_rank",)`, `trend_template.rising_ma_period_days=21`, `rs.horizon_weeks=12`, `rs.rs_rank_min_pass=70`, `rs.fallback_extreme_pct=20.0`. So `screenable_floor = 200 + 21 = 221`.
- `generate_candidate_windows(bars, "zigzag_pivot", *, ticker, timeframe="daily") -> list[CandidateWindow]` (`swing/patterns/foundation.py:426`). `zigzag_pivot` emits one window per qualifying down-swing; `anchor_date == start_date == swing-low (base start)`. Empty/None bars -> `[]`; non-monotonic index / NaN Close -> raises.
- `current_stage(conn, ticker, asof_date) -> "stage_2"|"undefined"` (`foundation.py:745`). Picks the latest candidate with `evaluation_runs.action_session_date <= asof_date` (ORDER BY `er.action_session_date DESC, er.run_ts DESC, er.id DESC`), then returns `"stage_2"` iff that candidate has exactly 8 `candidate_criteria` rows with `layer='trend_template' AND result='pass'`.
- `_pattern_detect_registry()` (`swing/pipeline/runner.py:1338`) returns a 5-tuple `((detector_fn, pattern_class, version), ...)` for classes `vcp, flat_base, cup_with_handle, high_tight_flag, double_bottom_w`. Production dispatch (`runner.py:1776,1799`): `window = windows[-1]`, then `detector_fn(bars, window, conn=, ticker=, asof_date=).geometric_score`.
- `insert_evaluation_run(conn, EvaluationRun) -> int` and `insert_candidates(conn, run_id, Sequence[Candidate])` (`swing/data/repos/candidates.py:11,41`) — neither commits; wrap in `with conn:`. `EvaluationRun` required fields: `id, run_ts, data_asof_date, action_session_date, finviz_csv_path, tickers_evaluated, aplus_count, watch_count, skip_count, excluded_count, error_count`.
- `ensure_schema(db_path: Path) -> sqlite3.Connection` (`swing/data/db.py:1170`) builds a fresh v24 schema-correct DB and returns the open connection — the canonical throwaway-DB builder.

---

## Task 1: Package scaffold — constants + exceptions

**Files:**
- Modify: `research/harness/minervini_exemplar_recall/__init__.py`
- Create: `research/harness/minervini_exemplar_recall/constants.py`
- Create: `research/harness/minervini_exemplar_recall/exceptions.py`
- Create: `tests/research/minervini_exemplar_recall/__init__.py` (empty)
- Test: `tests/research/minervini_exemplar_recall/test_constants.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_constants.py
from __future__ import annotations


def test_screenable_floor_is_221_for_default_config():
    from swing.config import Config
    from research.harness.minervini_exemplar_recall.constants import screenable_floor

    cfg = Config.from_defaults()
    # 200 + rising_ma_period_days (=21) -> 221. This is the full-TT-evaluability
    # floor: below it TT3 (200MA rising) is an UNALLOWED na and forces skip.
    assert screenable_floor(cfg) == 221


def test_module_constants_present():
    from research.harness.minervini_exemplar_recall import constants

    assert constants.H2_MIN_BARS == 60
    assert constants.CONTROL_GAP_BARS == 120
    assert constants.EQUITY_FLOOR_SURROGATE == 7500.0
    assert isinstance(constants.DEFAULT_CONTROL_SEED, int)


def test_exceptions_subclass_base():
    from research.harness.minervini_exemplar_recall import exceptions as exc

    for name in (
        "TiingoArchiveMissingError",
        "TiingoCoverageError",
        "MalformedExemplarRowError",
        "MalformedAsofDateError",
    ):
        cls = getattr(exc, name)
        assert issubclass(cls, exc.MinerviniRecallError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_constants.py -q`
Expected: FAIL — `ModuleNotFoundError: research.harness.minervini_exemplar_recall.constants`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/exceptions.py
from __future__ import annotations


class MinerviniRecallError(Exception):
    """Base class for all minervini_exemplar_recall harness errors."""


class TiingoArchiveMissingError(MinerviniRecallError):
    """The Tiingo CSV for a symbol does not exist on disk."""


class TiingoCoverageError(MinerviniRecallError):
    """The Tiingo CSV exists but has fewer than min_bars bars <= asof_date."""


class MalformedExemplarRowError(MinerviniRecallError):
    """An exemplar CSV row is missing a required field or has a bad value."""


class MalformedAsofDateError(MinerviniRecallError):
    """An asof_date string could not be parsed to a date."""
```

```python
# research/harness/minervini_exemplar_recall/constants.py
from __future__ import annotations

from swing.config import Config

H2_MIN_BARS = 60  # detector floor: enough bars for zigzag to emit >=1 down-swing.
CONTROL_GAP_BARS = 120  # min |session_pos - entry_pos| for a negative-control anchor.
DEFAULT_CONTROL_SEED = 20260608  # deterministic control-sampling base seed.
EQUITY_FLOOR_SURROGATE = 7500.0  # flagged surrogate; H1 risk gate uses this, not a real account.


def screenable_floor(config: Config) -> int:
    """200 + rising_ma_period_days. Below this TT3 (200MA rising) is an UNALLOWED
    na -> bucket_for forces skip regardless of merit, so we classify such names
    skip_insufficient_history (not a gate rejection)."""
    return 200 + config.trend_template.rising_ma_period_days
```

Bump `__init__.py`:

```python
# research/harness/minervini_exemplar_recall/__init__.py  (set/replace the version line)
__version__ = "0.1.0"
```

Create empty `tests/research/minervini_exemplar_recall/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_constants.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/__init__.py research/harness/minervini_exemplar_recall/constants.py research/harness/minervini_exemplar_recall/exceptions.py tests/research/minervini_exemplar_recall/__init__.py tests/research/minervini_exemplar_recall/test_constants.py
git commit -m "feat(research): scaffold minervini-recall harness constants and exceptions"
git log -1 --format='%(trailers)'   # must print nothing
```

---

## Task 2: Tiingo OHLCV reader

**Files:**
- Create: `research/harness/minervini_exemplar_recall/ohlcv_reader.py`
- Test: `tests/research/minervini_exemplar_recall/test_ohlcv_reader.py`

Contract (mirrors the V2 reader's backward-looking `<=asof` slice): map `adjOpen/adjHigh/adjLow/adjClose/adjVolume` -> capitalized `Open/High/Low/Close/Volume`; ascending tz-naive `DatetimeIndex`; `read_sliced` raises `TiingoArchiveMissingError` when the file is absent and `TiingoCoverageError` when `len(sliced) < min_bars`.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_ohlcv_reader.py
from __future__ import annotations

from datetime import date

import pytest


def _write_tiingo_csv(path, dates, base=100.0):
    # Tiingo's real header includes raw + adj columns; the reader only consumes adj* + date.
    lines = ["date,close,high,low,open,volume,adjClose,adjHigh,adjLow,adjOpen,adjVolume"]
    for i, d in enumerate(dates):
        c = base + i
        lines.append(f"{d},{c},{c+1},{c-1},{c},{1000+i},{c},{c+1},{c-1},{c},{1000+i}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_read_full_maps_adj_columns_capitalized(tmp_path):
    from research.harness.minervini_exemplar_recall.ohlcv_reader import read_full

    _write_tiingo_csv(tmp_path / "ZZTOP.csv", ["2010-01-04", "2010-01-05", "2010-01-06"])
    df = read_full("ZZTOP", tiingo_dir=tmp_path)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert str(df.index.dtype).startswith("datetime64")
    assert df.index.is_monotonic_increasing
    # adjClose for the 2nd bar was 101.0
    assert df["Close"].iloc[1] == pytest.approx(101.0)


def test_slice_to_is_inclusive_backward(tmp_path):
    from research.harness.minervini_exemplar_recall.ohlcv_reader import read_full, slice_to

    _write_tiingo_csv(tmp_path / "ZZTOP.csv", ["2010-01-04", "2010-01-05", "2010-01-06"])
    df = read_full("ZZTOP", tiingo_dir=tmp_path)
    sliced = slice_to(df, date(2010, 1, 5))
    # <= 2010-01-05 inclusive -> 2 bars (the 01-05 bar is RETAINED).
    # WRONG-PATH (strict <): 1 bar.  RIGHT-PATH (<=): 2 bars.
    assert len(sliced) == 2
    assert sliced.index[-1].date() == date(2010, 1, 5)


def test_symbol_override(tmp_path):
    from research.harness.minervini_exemplar_recall.ohlcv_reader import tiingo_symbol

    assert tiingo_symbol("EMEX") == "ELX"
    assert tiingo_symbol("HOOK") == "BREW"
    assert tiingo_symbol("CRUS") == "CRUS"
    assert tiingo_symbol("crus") == "CRUS"  # upper-cased


def test_read_sliced_raises_archive_missing(tmp_path):
    from research.harness.minervini_exemplar_recall.exceptions import TiingoArchiveMissingError
    from research.harness.minervini_exemplar_recall.ohlcv_reader import read_sliced

    with pytest.raises(TiingoArchiveMissingError, match="NOPE"):
        read_sliced("NOPE", date(2010, 1, 5), tiingo_dir=tmp_path, min_bars=1)


def test_read_sliced_raises_coverage_below_min_bars(tmp_path):
    from research.harness.minervini_exemplar_recall.exceptions import TiingoCoverageError
    from research.harness.minervini_exemplar_recall.ohlcv_reader import read_sliced

    _write_tiingo_csv(tmp_path / "ZZTOP.csv", ["2010-01-04", "2010-01-05"])
    # 2 bars <= asof, min_bars=5 -> coverage error.
    with pytest.raises(TiingoCoverageError, match="sliced=2"):
        read_sliced("ZZTOP", date(2010, 1, 6), tiingo_dir=tmp_path, min_bars=5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_ohlcv_reader.py -q`
Expected: FAIL — `ModuleNotFoundError: ...ohlcv_reader`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/ohlcv_reader.py
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .exceptions import TiingoArchiveMissingError, TiingoCoverageError

SYMBOL_OVERRIDE = {"EMEX": "ELX", "HOOK": "BREW"}

_ADJ_TO_CAPITAL = {
    "adjOpen": "Open",
    "adjHigh": "High",
    "adjLow": "Low",
    "adjClose": "Close",
    "adjVolume": "Volume",
}


def tiingo_symbol(book_ticker: str) -> str:
    up = book_ticker.upper()
    return SYMBOL_OVERRIDE.get(up, up)


def read_full(symbol: str, *, tiingo_dir: Path) -> pd.DataFrame:
    """Read research/data/tiingo/<symbol>.csv -> capitalized adjusted OHLCV,
    ascending DatetimeIndex (tz-naive)."""
    path = Path(tiingo_dir) / f"{symbol}.csv"
    if not path.exists():
        raise TiingoArchiveMissingError(f"Tiingo archive missing for symbol={symbol!r} at {path}")
    raw = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    df = pd.DataFrame({cap: raw[adj] for adj, cap in _ADJ_TO_CAPITAL.items()})
    df.index = df.index.tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def slice_to(bars: pd.DataFrame, asof_date: date) -> pd.DataFrame:
    """In-memory <= asof inclusive slice (backward-looking anchor)."""
    return bars.loc[bars.index.date <= asof_date]


def read_sliced(symbol: str, asof_date: date, *, tiingo_dir: Path, min_bars: int) -> pd.DataFrame:
    sliced = slice_to(read_full(symbol, tiingo_dir=tiingo_dir), asof_date)
    if len(sliced) < min_bars:
        raise TiingoCoverageError(
            f"Tiingo insufficient for symbol={symbol!r} at asof={asof_date}: "
            f"sliced={len(sliced)} < min_bars={min_bars}"
        )
    return sliced
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_ohlcv_reader.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/ohlcv_reader.py tests/research/minervini_exemplar_recall/test_ohlcv_reader.py
git commit -m "feat(research): add Tiingo OHLCV reader for minervini-recall harness"
git log -1 --format='%(trailers)'
```

---

## Task 3: Exemplar CSV reader

**Files:**
- Create: `research/harness/minervini_exemplar_recall/exemplar_reader.py`
- Test: `tests/research/minervini_exemplar_recall/test_exemplar_reader.py`

`ExemplarRow` carries the book ticker, resolved `tiingo_symbol`, parsed `entry_anchor: date`, `date_precision` (from the CSV column), `detector_class` (incl. `unmapped`), and `buy_point_price | None`. `read_exemplars` filters `curated == "yes"` (the clean inclusion filter — 27 of 34 rows).

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_exemplar_reader.py
from __future__ import annotations

from datetime import date

import pytest

_HEADER = (
    "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
    "stop_price,base_start_date,base_end_date,date_precision,source,page,"
    "extracted_by,curated,notes"
)


def _write(path, rows):
    path.write_text(_HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_filters_curated_yes_only(tmp_path):
    from research.harness.minervini_exemplar_recall.exemplar_reader import read_exemplars

    csv = tmp_path / "ex.csv"
    _write(
        csv,
        [
            "id-a,CRUS,VCP,vcp,2010-03-30,8.09,,,,exact,TWoSMW,Fig 10.34,claude,yes,n",
            "id-b,FSII,cup,cup_with_handle,1995-02,,,,,month,TWoSMW,Fig 10.3,claude,no,excluded",
        ],
    )
    rows = read_exemplars(csv)
    # WRONG-PATH (no filter): 2 rows.  RIGHT-PATH (curated==yes): 1 row.
    assert len(rows) == 1
    assert rows[0].exemplar_id == "id-a"


def test_parses_entry_anchor_all_three_precisions(tmp_path):
    from research.harness.minervini_exemplar_recall.exemplar_reader import read_exemplars

    csv = tmp_path / "ex.csv"
    _write(
        csv,
        [
            "id-day,AAA,VCP,vcp,2010-03-30,,,,,day,S,P,claude,yes,n",
            "id-mon,BBB,VCP,vcp,1995-02,,,,,month,S,P,claude,yes,n",
            "id-yr,CCC,VCP,vcp,2001,,,,,year,S,P,claude,yes,n",
        ],
    )
    by_id = {r.exemplar_id: r for r in read_exemplars(csv)}
    assert by_id["id-day"].entry_anchor == date(2010, 3, 30)
    # missing day -> 1st; missing month -> July (mid-period defaults from tiingo_pull.entry_anchor)
    assert by_id["id-mon"].entry_anchor == date(1995, 2, 1)
    assert by_id["id-yr"].entry_anchor == date(2001, 7, 1)
    assert by_id["id-mon"].date_precision == "month"


def test_resolves_tiingo_symbol_and_price(tmp_path):
    from research.harness.minervini_exemplar_recall.exemplar_reader import read_exemplars

    csv = tmp_path / "ex.csv"
    _write(
        csv,
        [
            "id-emex,EMEX,HTF,high_tight_flag,2001,,,,,year,S,P,claude,yes,n",
            "id-crus,CRUS,VCP,vcp,2010-03-30,8.09,,,,exact,S,P,claude,yes,n",
        ],
    )
    by_id = {r.exemplar_id: r for r in read_exemplars(csv)}
    assert by_id["id-emex"].tiingo_symbol == "ELX"  # SYMBOL_OVERRIDE applied
    assert by_id["id-crus"].buy_point_price == pytest.approx(8.09)
    assert by_id["id-emex"].buy_point_price is None  # empty -> None


def test_malformed_entry_date_raises(tmp_path):
    from research.harness.minervini_exemplar_recall.exceptions import MalformedExemplarRowError
    from research.harness.minervini_exemplar_recall.exemplar_reader import read_exemplars

    csv = tmp_path / "ex.csv"
    _write(csv, ["id-bad,AAA,VCP,vcp,not-a-date,,,,,day,S,P,claude,yes,n"])
    with pytest.raises(MalformedExemplarRowError, match="id-bad"):
        read_exemplars(csv)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_exemplar_reader.py -q`
Expected: FAIL — `ModuleNotFoundError: ...exemplar_reader`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/exemplar_reader.py
from __future__ import annotations

import csv as _csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .exceptions import MalformedExemplarRowError
from .ohlcv_reader import tiingo_symbol


@dataclass(frozen=True)
class ExemplarRow:
    exemplar_id: str
    ticker: str
    tiingo_symbol: str
    setup_label: str
    detector_class: str
    entry_anchor: date
    date_precision: str
    buy_point_price: float | None
    source: str
    page: str
    notes: str


def _parse_entry_anchor(entry: str) -> date:
    # Mid-period defaults, identical to tiingo_pull.entry_anchor: missing month -> July,
    # missing day -> 1st.
    parts = entry.split("-")
    y = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 7
    d = int(parts[2]) if len(parts) > 2 else 1
    return date(y, m, d)


def _parse_price(raw: str) -> float | None:
    raw = (raw or "").strip()
    return float(raw) if raw else None


def read_exemplars(csv_path: Path) -> list[ExemplarRow]:
    out: list[ExemplarRow] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            if (row.get("curated") or "").strip().lower() != "yes":
                continue
            eid = (row.get("exemplar_id") or "").strip()
            try:
                anchor = _parse_entry_anchor((row.get("entry_date") or "").strip())
                price = _parse_price(row.get("buy_point_price", ""))
            except (ValueError, IndexError) as exc:
                raise MalformedExemplarRowError(
                    f"exemplar_id={eid!r}: bad entry_date/buy_point_price: {exc}"
                ) from exc
            book = (row.get("ticker") or "").strip()
            out.append(
                ExemplarRow(
                    exemplar_id=eid,
                    ticker=book,
                    tiingo_symbol=tiingo_symbol(book),
                    setup_label=(row.get("setup_label") or "").strip(),
                    detector_class=(row.get("detector_class") or "").strip(),
                    entry_anchor=anchor,
                    date_precision=(row.get("date_precision") or "").strip(),
                    buy_point_price=price,
                    source=(row.get("source") or "").strip(),
                    page=(row.get("page") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_exemplar_reader.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/exemplar_reader.py tests/research/minervini_exemplar_recall/test_exemplar_reader.py
git commit -m "feat(research): add exemplar CSV reader with curated filter and entry-anchor parsing"
git log -1 --format='%(trailers)'
```

---

## Task 4: RS proxy (BatchContext builder, P0 / P1)

**Files:**
- Create: `research/harness/minervini_exemplar_recall/rs_proxy.py`
- Test: `tests/research/minervini_exemplar_recall/test_rs_proxy.py`

P0 `fallback_spy` (default) applies ONLY when both the exemplar and SPY have `horizon_weeks*5 + 1` bars `<=` session (= 61 for default config). Then `returns_12w_by_ticker = {ticker: r_exemplar}`, `spy_return_12w = r_spy`, `universe_tickers = ()`. P1 (degenerate) fires otherwise: `returns_12w_by_ticker = {}` (empty — no ticker key, so `compute_rs` returns `unavailable` BEFORE touching spy_return -> TT8 genuinely na), `spy_return_12w = 0.0`. **Invariant:** P1 never inserts a ticker return, so a stray SPY value can never promote TT8.

The trailing return is the simple `horizon_weeks*5`-bar return: `r = close.iloc[-1] / close.iloc[-(H+1)] - 1` where `H = horizon_weeks*5`.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_rs_proxy.py
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing.config import Config
from swing.evaluation.rs import compute_rs


def _bars(closes, start="2009-01-02"):
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [1_000] * len(closes)},
        index=idx,
    )


def test_p0_excess_pass_boundary(tmp_path):
    from research.harness.minervini_exemplar_recall.rs_proxy import build_batch

    cfg = Config.from_defaults()  # horizon_weeks=12 -> H=60; need 61 bars; fallback_extreme_pct=20.0
    # 70 bars; exemplar rises so trailing-60 return = 125/100 - 1 = 0.25; SPY flat (return 0).
    ex_closes = [100.0] * 10 + list(_lin(100.0, 125.0, 60))
    spy_closes = [100.0] * 70
    ex = _bars(ex_closes)
    spy = _bars(spy_closes)
    session = ex.index[-1].date()
    out = build_batch(ticker="AAA", exemplar_sliced=ex, spy_full=spy, session=session, config=cfg)
    assert out.rs_path == "P0"
    assert out.excess == pytest.approx(0.25, abs=1e-6)
    # Drive it through compute_rs to confirm TT8 would PASS (excess 0.25 >= 0.20).
    rs = compute_rs("AAA", out.batch.returns_12w_by_ticker, out.batch.universe_tickers,
                    spy_return=out.batch.spy_return_12w)
    assert rs.method == "fallback_spy"
    assert rs.return_vs_spy == pytest.approx(0.25, abs=1e-6)


def test_p0_na_band(tmp_path):
    from research.harness.minervini_exemplar_recall.rs_proxy import build_batch

    cfg = Config.from_defaults()
    ex = _bars([100.0] * 10 + list(_lin(100.0, 115.0, 60)))  # trailing-60 return 0.15 -> na band
    spy = _bars([100.0] * 70)
    out = build_batch(ticker="AAA", exemplar_sliced=ex, spy_full=spy, session=ex.index[-1].date(), config=cfg)
    assert out.excess == pytest.approx(0.15, abs=1e-6)  # in [-0.20, 0.20) -> TT8 na


def test_p1_when_spy_too_short_yields_unavailable(tmp_path):
    from research.harness.minervini_exemplar_recall.rs_proxy import build_batch

    cfg = Config.from_defaults()
    ex = _bars([100.0 + i for i in range(70)])
    spy = _bars([100.0] * 30)  # < 61 bars -> P0 precondition fails -> P1
    out = build_batch(ticker="AAA", exemplar_sliced=ex, spy_full=spy, session=ex.index[-1].date(), config=cfg)
    assert out.rs_path == "P1"
    assert out.excess is None
    # INVARIANT: empty returns dict -> compute_rs returns 'unavailable' before touching spy_return.
    assert out.batch.returns_12w_by_ticker == {}
    rs = compute_rs("AAA", out.batch.returns_12w_by_ticker, out.batch.universe_tickers,
                    spy_return=out.batch.spy_return_12w)
    assert rs.method == "unavailable"  # WRONG-PATH (P1 inserts a ticker key): 'fallback_spy'.


def _lin(a, b, n):
    step = (b - a) / (n - 1)
    return [a + step * i for i in range(n)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_rs_proxy.py -q`
Expected: FAIL — `ModuleNotFoundError: ...rs_proxy`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/rs_proxy.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from swing.config import Config
from swing.evaluation.context import BatchContext

from .ohlcv_reader import slice_to


@dataclass(frozen=True)
class RsProxyOutcome:
    batch: BatchContext
    rs_path: str  # "P0" | "P1"
    excess: float | None  # exemplar trailing-H return minus SPY's; None under P1


def _trailing_return(bars: pd.DataFrame, horizon_bars: int) -> float:
    close = bars["Close"]
    return float(close.iloc[-1]) / float(close.iloc[-(horizon_bars + 1)]) - 1.0


def build_batch(
    *,
    ticker: str,
    exemplar_sliced: pd.DataFrame,
    spy_full: pd.DataFrame,
    session: date,
    config: Config,
) -> RsProxyOutcome:
    horizon = config.rs.horizon_weeks * 5  # 60 for default config
    need = horizon + 1  # 61 bars to compute a trailing-60 return
    spy_sliced = slice_to(spy_full, session) if spy_full is not None else None

    p0_ok = (
        len(exemplar_sliced) >= need
        and spy_sliced is not None
        and len(spy_sliced) >= need
    )

    if p0_ok:
        r_ex = _trailing_return(exemplar_sliced, horizon)
        r_spy = _trailing_return(spy_sliced, horizon)
        batch = BatchContext(
            returns_12w_by_ticker={ticker: r_ex},
            universe_tickers=(),  # empty -> ticker outside universe -> compute_rs uses fallback_spy
            universe_version="minervini-recall-p0",
            universe_hash="",
            spy_return_12w=r_spy,
        )
        return RsProxyOutcome(batch=batch, rs_path="P0", excess=r_ex - r_spy)

    # P1 degenerate: empty returns dict (NO ticker key) -> compute_rs returns 'unavailable'
    # before it ever reads spy_return. A stray SPY value can never promote TT8.
    batch = BatchContext(
        returns_12w_by_ticker={},
        universe_tickers=(),
        universe_version="minervini-recall-p1",
        universe_hash="",
        spy_return_12w=0.0,
    )
    return RsProxyOutcome(batch=batch, rs_path="P1", excess=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_rs_proxy.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/rs_proxy.py tests/research/minervini_exemplar_recall/test_rs_proxy.py
git commit -m "feat(research): add RS proxy BatchContext builder with P0/P1 fallback paths"
git log -1 --format='%(trailers)'
```

---

## Task 5: H1 screen evaluation (taxonomy + gate attribution)

**Files:**
- Create: `research/harness/minervini_exemplar_recall/screen_eval.py`
- Test: `tests/research/minervini_exemplar_recall/test_screen_eval.py`

Two pure functions (fully testable with hand-built criteria — this is where the regression-arithmetic discipline bites) plus a thin wiring function:
- `classify_h1_outcome(*, has_bars, n_sliced, bucket, floor) -> str` in `{no_data, skip_insufficient_history, surfaced_aplus, surfaced_watch, skip_gate_rejection}`. Order: no bars -> `no_data`; `n_sliced < floor` -> `skip_insufficient_history` (BEFORE consulting bucket — the 200-220 band is forced-skip by an UNALLOWED TT3 na, not a merit rejection); else bucket maps surfaced/gate-rejection.
- `attribute_first_rejecting_gate(criteria, config) -> GateAttribution` replays `bucket_for`'s exact order over the `CriterionResult` tuple: risk non-pass -> `risk_feasibility`; else `tt_passes < min_passes` -> `trend_template_min_passes`; else any TT fail not in `allowed_miss_names` -> `trend_template`; else `vcp_fails > 2` -> `vcp`.
- `evaluate_h1(*, ticker, exemplar_full, spy_full, session, config) -> ScreenResult` slices in-memory, builds the BatchContext via `rs_proxy`, calls `evaluate_one`, classifies, and (only for `skip_gate_rejection`) attributes. It ALWAYS returns the 8 `trend_template` criteria (`tt_criteria`) so `stage_db` can seed the faithful variant — even for `skip_insufficient_history` (where they include nas).

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_screen_eval.py
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing.config import Config
from swing.data.models import CriterionResult

TT_NAMES = ["TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
            "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
            "TT7_within_52w_high_25pct", "TT8_rs_rank"]


def _tt(passes: dict[str, str]) -> list[CriterionResult]:
    # passes maps name -> result; default 'pass'.
    return [CriterionResult(n, "trend_template", passes.get(n, "pass")) for n in TT_NAMES]


def _vcp(n_fail: int) -> list[CriterionResult]:
    out = []
    for i in range(9):
        res = "fail" if i < n_fail else "pass"
        out.append(CriterionResult(f"VCP{i}", "vcp", res))
    return out


def _risk(result: str) -> list[CriterionResult]:
    return [CriterionResult("RISK_feasible", "risk", result)]


def test_classify_insufficient_history_below_floor():
    from research.harness.minervini_exemplar_recall.screen_eval import classify_h1_outcome

    # bucket would be 'skip' but n_sliced < 221 -> insufficient (NOT gate_rejection).
    # WRONG-PATH (bucket-first): skip_gate_rejection.  RIGHT-PATH (floor-first): skip_insufficient_history.
    assert classify_h1_outcome(has_bars=True, n_sliced=210, bucket="skip", floor=221) == "skip_insufficient_history"
    assert classify_h1_outcome(has_bars=False, n_sliced=0, bucket=None, floor=221) == "no_data"
    assert classify_h1_outcome(has_bars=True, n_sliced=250, bucket="aplus", floor=221) == "surfaced_aplus"
    assert classify_h1_outcome(has_bars=True, n_sliced=250, bucket="watch", floor=221) == "surfaced_watch"
    assert classify_h1_outcome(has_bars=True, n_sliced=250, bucket="skip", floor=221) == "skip_gate_rejection"


def test_attribute_risk_wins_even_when_tt_also_fails():
    from research.harness.minervini_exemplar_recall.screen_eval import attribute_first_rejecting_gate

    cfg = Config.from_defaults()
    criteria = _tt({"TT1_above_150_200": "fail", "TT2_150_above_200": "fail"}) + _vcp(0) + _risk("fail")
    attrib = attribute_first_rejecting_gate(criteria, cfg)
    # risk is the hard filter checked FIRST. WRONG-PATH (TT-first): trend_template.
    # RIGHT-PATH (risk-first): risk_feasibility.
    assert attrib.first_rejecting_gate == "risk_feasibility"


def test_attribute_unallowed_tt_miss_when_passes_met():
    from research.harness.minervini_exemplar_recall.screen_eval import attribute_first_rejecting_gate

    cfg = Config.from_defaults()  # min_passes=7, allowed={TT8_rs_rank}
    # 7 passes (TT2 is the single fail) -> min_passes met, but TT2 is NOT allowed -> trend_template.
    criteria = _tt({"TT2_150_above_200": "fail"}) + _vcp(0) + _risk("pass")
    attrib = attribute_first_rejecting_gate(criteria, cfg)
    # WRONG-PATH (min_passes-only check passes -> falls through to vcp): vcp.
    # RIGHT-PATH (unallowed-miss check): trend_template.
    assert attrib.first_rejecting_gate == "trend_template"
    assert "TT2_150_above_200" in attrib.failing_gates


def test_attribute_min_passes_shortfall():
    from research.harness.minervini_exemplar_recall.screen_eval import attribute_first_rejecting_gate

    cfg = Config.from_defaults()
    # 5 passes (3 fails) -> below min_passes 7.
    criteria = _tt({"TT1_above_150_200": "fail", "TT3_200_rising": "fail", "TT4_50_above_150_200": "fail"}) + _vcp(0) + _risk("pass")
    attrib = attribute_first_rejecting_gate(criteria, cfg)
    assert attrib.first_rejecting_gate == "trend_template_min_passes"


def test_attribute_vcp_when_tt_clean():
    from research.harness.minervini_exemplar_recall.screen_eval import attribute_first_rejecting_gate

    cfg = Config.from_defaults()
    # all TT pass, 3 vcp fails (>2) -> vcp.  (2 vcp fails would be 'watch', not a skip at all.)
    criteria = _tt({}) + _vcp(3) + _risk("pass")
    attrib = attribute_first_rejecting_gate(criteria, cfg)
    assert attrib.first_rejecting_gate == "vcp"


def test_tt_names_match_production():
    # _TT_NAMES (used to synthesize NA rows for tiny slices) must match the real CHECK_NAMES
    # or faithful-stage seeding drifts.
    from swing.evaluation.criteria.trend_template import CHECK_NAMES
    from research.harness.minervini_exemplar_recall.screen_eval import _TT_NAMES

    assert tuple(_TT_NAMES) == tuple(CHECK_NAMES)


def test_compute_gate_passes_distinguishes_each_layer():
    from research.harness.minervini_exemplar_recall.screen_eval import compute_gate_passes

    cfg = Config.from_defaults()
    # risk fail -> risk gate False; everything else passing.
    g = compute_gate_passes(_tt({}) + _vcp(0) + _risk("fail"), cfg)
    assert g == {"risk_feasibility": False, "trend_template": True, "vcp": True}
    # TT2 unallowed fail -> trend_template gate False (WRONG-PATH min_passes-only: True).
    g2 = compute_gate_passes(_tt({"TT2_150_above_200": "fail"}) + _vcp(0) + _risk("pass"), cfg)
    assert g2["trend_template"] is False and g2["risk_feasibility"] is True
    # 3 vcp fails -> vcp gate False; 2 would be True.
    assert compute_gate_passes(_tt({}) + _vcp(3) + _risk("pass"), cfg)["vcp"] is False
    assert compute_gate_passes(_tt({}) + _vcp(2) + _risk("pass"), cfg)["vcp"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_screen_eval.py -q`
Expected: FAIL — `ModuleNotFoundError: ...screen_eval`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/screen_eval.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from swing.config import Config
from swing.data.models import CriterionResult
from swing.evaluation.context import CandidateContext, MarketContext
from swing.evaluation.evaluator import evaluate_one

from . import rs_proxy
from .constants import EQUITY_FLOOR_SURROGATE, screenable_floor
from .ohlcv_reader import slice_to

H1_OUTCOMES = (
    "no_data",
    "skip_insufficient_history",
    "surfaced_aplus",
    "surfaced_watch",
    "skip_gate_rejection",
)


@dataclass(frozen=True)
class GateAttribution:
    first_rejecting_gate: str  # risk_feasibility|trend_template_min_passes|trend_template|vcp
    failing_gates: tuple[str, ...]


@dataclass(frozen=True)
class ScreenResult:
    outcome: str
    bucket: str | None
    n_sliced: int
    rs_path: str | None
    tt_criteria: tuple[CriterionResult, ...]  # the 8 trend_template results (for stage seeding)
    gate_attribution: GateAttribution | None
    gate_passes: dict[str, bool] | None = None  # per-gate pass over the SCREENABLE subset (else None)


# The 8 trend_template criterion names (mirrors swing.evaluation.criteria.trend_template.CHECK_NAMES).
# A test (test_screen_eval.py::test_tt_names_match_production) asserts parity so this never drifts.
_TT_NAMES = (
    "TT1_above_150_200",
    "TT2_150_above_200",
    "TT3_200_rising",
    "TT4_50_above_150_200",
    "TT5_above_50",
    "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct",
    "TT8_rs_rank",
)


def _na_tt_criteria() -> tuple[CriterionResult, ...]:
    """8 distinct trend_template NA rows -> faithful stage seeds to pass_count 0 -> undefined
    stage (NOT coverage_skip). Used when evaluate_one raises on a tiny below-floor slice so H1
    ALWAYS yields 8 TT rows (spec section 5)."""
    return tuple(CriterionResult(n, "trend_template", "na") for n in _TT_NAMES)


def compute_gate_passes(
    criteria: tuple[CriterionResult, ...] | list[CriterionResult], config: Config
) -> dict[str, bool]:
    """Per-gate pass status mirroring bucket_for's layer gates (spec section 9 per-gate pass rate).
    risk: all risk pass. trend_template: tt_passes >= min_passes AND every TT fail in allowed.
    vcp: vcp_fails (fail|na) <= 2 (i.e. watch-or-better)."""
    tt = [c for c in criteria if c.layer == "trend_template"]
    vcp = [c for c in criteria if c.layer == "vcp"]
    risk = [c for c in criteria if c.layer == "risk"]
    risk_pass = all(c.result == "pass" for c in risk)
    tt_passes = sum(1 for c in tt if c.result == "pass")
    tt_fails = [c.criterion_name for c in tt if c.result != "pass"]
    allowed = set(config.trend_template.allowed_miss_names)
    tt_gate = tt_passes >= config.trend_template.min_passes and all(n in allowed for n in tt_fails)
    vcp_gate = sum(1 for c in vcp if c.result in ("fail", "na")) <= 2
    return {"risk_feasibility": risk_pass, "trend_template": tt_gate, "vcp": vcp_gate}


def classify_h1_outcome(*, has_bars: bool, n_sliced: int, bucket: str | None, floor: int) -> str:
    if not has_bars or n_sliced == 0:
        return "no_data"
    if n_sliced < floor:
        return "skip_insufficient_history"
    if bucket == "aplus":
        return "surfaced_aplus"
    if bucket == "watch":
        return "surfaced_watch"
    return "skip_gate_rejection"


def attribute_first_rejecting_gate(
    criteria: tuple[CriterionResult, ...] | list[CriterionResult], config: Config
) -> GateAttribution:
    tt = [c for c in criteria if c.layer == "trend_template"]
    vcp = [c for c in criteria if c.layer == "vcp"]
    risk = [c for c in criteria if c.layer == "risk"]

    risk_fails = [c.criterion_name for c in risk if c.result != "pass"]
    if risk_fails:
        return GateAttribution("risk_feasibility", tuple(risk_fails))

    tt_passes = sum(1 for c in tt if c.result == "pass")
    tt_fails = [c.criterion_name for c in tt if c.result != "pass"]
    allowed = set(config.trend_template.allowed_miss_names)

    if tt_passes < config.trend_template.min_passes:
        return GateAttribution("trend_template_min_passes", tuple(tt_fails))
    unallowed = [n for n in tt_fails if n not in allowed]
    if unallowed:
        return GateAttribution("trend_template", tuple(tt_fails))

    vcp_fails = [c.criterion_name for c in vcp if c.result in ("fail", "na")]
    if len(vcp_fails) > 2:
        return GateAttribution("vcp", tuple(vcp_fails))

    # Reached only if the caller mis-routed a non-skip candidate; name it explicitly.
    return GateAttribution("none", ())


def evaluate_h1(
    *,
    ticker: str,
    exemplar_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
    session: date,
    config: Config,
) -> ScreenResult:
    floor = screenable_floor(config)
    sliced = slice_to(exemplar_full, session)
    n = len(sliced)
    if n == 0:
        return ScreenResult("no_data", None, 0, None, (), None)

    proxy = rs_proxy.build_batch(
        ticker=ticker, exemplar_sliced=sliced, spy_full=spy_full, session=session, config=config
    )
    ctx = CandidateContext(
        ticker=ticker,
        ohlcv=sliced,
        config=config,
        batch=proxy.batch,
        market=MarketContext(),
        current_equity=EQUITY_FLOOR_SURROGATE,
    )
    try:
        candidate = evaluate_one(ctx)
    except Exception:  # noqa: BLE001
        # The youngest names' earliest sweep sessions slice to a handful of bars; evaluate_one is
        # hardened for liquid finviz candidates, not 1-bar input. Below the screenable floor an
        # exception is invariably too-few-bars -> classify insufficient_history, but STILL return 8
        # synthetic NA TT rows so the faithful H2 stage seeds to undefined (not coverage_skip), per
        # spec section 5 ("ALWAYS returns the 8 trend_template criteria"). At/above the floor a raise
        # is a genuine bug and must NOT be swallowed.
        if n < floor:
            return ScreenResult(
                "skip_insufficient_history", None, n, proxy.rs_path, _na_tt_criteria(), None, None
            )
        raise
    tt = tuple(c for c in candidate.criteria if c.layer == "trend_template")
    outcome = classify_h1_outcome(has_bars=True, n_sliced=n, bucket=candidate.bucket, floor=floor)
    attrib = (
        attribute_first_rejecting_gate(candidate.criteria, config)
        if outcome == "skip_gate_rejection"
        else None
    )
    gate_passes = (
        compute_gate_passes(candidate.criteria, config)
        if outcome in ("surfaced_aplus", "surfaced_watch", "skip_gate_rejection")
        else None
    )
    return ScreenResult(outcome, candidate.bucket, n, proxy.rs_path, tt, attrib, gate_passes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_screen_eval.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/screen_eval.py tests/research/minervini_exemplar_recall/test_screen_eval.py
git commit -m "feat(research): add H1 screen-eval taxonomy and load-bearing-gate attribution"
git log -1 --format='%(trailers)'
```

---

## Task 6: Synthetic stage DB (faithful + isolated)

**Files:**
- Create: `research/harness/minervini_exemplar_recall/stage_db.py`
- Test: `tests/research/minervini_exemplar_recall/test_stage_db.py`

Build a throwaway SQLite via the production migration runner (`ensure_schema` -> v24, zero DDL drift). Seed via the production repo functions (`insert_evaluation_run` / `insert_candidates`) with minimal valid models and exactly 8 `trend_template` criterion rows per candidate — never hand-authored INSERTs. `current_stage` returns `stage_2` iff 8/8 of those rows are `pass`. The two variants live in PHYSICALLY SEPARATE DB files (Codex R1.M1: `current_stage` has no variant discriminator, so a shared DB would let one variant contaminate the other).

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_stage_db.py
from __future__ import annotations

from datetime import date

import pytest

from swing.data.models import CriterionResult

TT_NAMES = ["TT1", "TT2", "TT3", "TT4", "TT5", "TT6", "TT7", "TT8"]


def _tt(results):  # list of 8 result strings
    return tuple(CriterionResult(TT_NAMES[i], "trend_template", results[i]) for i in range(8))


def test_faithful_stage2_iff_eight_passes(tmp_path):
    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db, seed_session, stage_at

    conn = build_stage_db(tmp_path / "faithful.db")
    session = date(2010, 3, 30)
    # 8/8 pass -> stage_2.
    seed_session(conn, ticker="AAA", session=session, tt_results=_tt(["pass"] * 8), mode="faithful")
    assert stage_at(conn, "AAA", session) == "stage_2"


def test_faithful_seven_passes_is_not_stage2(tmp_path):
    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db, seed_session, stage_at

    conn = build_stage_db(tmp_path / "faithful.db")
    session = date(2010, 3, 30)
    # 7 pass + 1 fail -> pass_count 7 != 8 -> undefined.
    # WRONG-PATH (count any rows): stage_2.  RIGHT-PATH (count result='pass' == 8): undefined.
    seed_session(conn, ticker="BBB", session=session, tt_results=_tt(["pass"] * 7 + ["fail"]), mode="faithful")
    assert stage_at(conn, "BBB", session) == "undefined"


def test_isolated_always_stage2(tmp_path):
    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db, seed_session, stage_at

    conn = build_stage_db(tmp_path / "isolated.db")
    session = date(2010, 3, 30)
    # isolated ignores tt_results and forces 8 pass.
    seed_session(conn, ticker="CCC", session=session, tt_results=_tt(["fail"] * 8), mode="isolated")
    assert stage_at(conn, "CCC", session) == "stage_2"


def test_schema_built_at_expected_version(tmp_path):
    from swing.data.db import EXPECTED_SCHEMA_VERSION
    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db

    conn = build_stage_db(tmp_path / "x.db")
    # swing tracks schema version in the schema_version TABLE, not PRAGMA user_version.
    # WRONG-PATH (PRAGMA user_version): returns 0 -> test fails on a correctly-built v24 DB.
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row[0] == EXPECTED_SCHEMA_VERSION


def test_faithful_rejects_wrong_count_or_duplicate_tt_rows(tmp_path):
    import pytest

    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db, seed_session

    conn = build_stage_db(tmp_path / "faithful.db")
    session = date(2010, 3, 30)
    # 7 rows -> rejected.
    with pytest.raises(ValueError, match="8"):
        seed_session(conn, ticker="AAA", session=session,
                     tt_results=tuple(CriterionResult(TT_NAMES[i], "trend_template", "pass") for i in range(7)),
                     mode="faithful")
    # 8 rows but a DUPLICATE name (TT1 twice, TT8 missing) -> rejected, because current_stage counts
    # result='pass' rows blindly and 8 duplicate passes would falsely seed stage_2 (spec section 6.1).
    dup = tuple(CriterionResult("TT1", "trend_template", "pass") for _ in range(8))
    with pytest.raises(ValueError, match="UNIQUE"):
        seed_session(conn, ticker="BBB", session=session, tt_results=dup, mode="faithful")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_stage_db.py -q`
Expected: FAIL — `ModuleNotFoundError: ...stage_db`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/stage_db.py
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.patterns.foundation import current_stage

_FORCED_TT = tuple(
    CriterionResult(f"TT{i + 1}", "trend_template", "pass") for i in range(8)
)


def build_stage_db(path: Path) -> sqlite3.Connection:
    """Fresh v24 schema-correct scratch DB (writable research scratch, not production)."""
    return ensure_schema(Path(path))


def _minimal_candidate(ticker: str, tt_results: tuple[CriterionResult, ...]) -> Candidate:
    return Candidate(
        ticker=ticker,
        bucket="aplus",  # bucket is irrelevant to current_stage; any value is fine.
        close=None,
        pivot=None,
        initial_stop=None,
        adr_pct=None,
        tight_streak=None,
        pullback_pct=None,
        prior_trend_pct=None,
        rs_rank=None,
        rs_return_12w_vs_spy=None,
        rs_method="unavailable",
        pattern_tag=None,
        notes=None,
        criteria=tuple(tt_results),
    )


def seed_session(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    session: date,
    tt_results: tuple[CriterionResult, ...],
    mode: str,
) -> None:
    """Insert one evaluation_run + candidate keyed at action_session_date=session.

    mode='faithful' -> seed the session's actual 8 trend_template results (stage_2 iff 8/8 pass).
    mode='isolated' -> 8 forced 'pass' rows (always stage_2)."""
    if mode == "isolated":
        criteria = _FORCED_TT
    elif mode == "faithful":
        criteria = tuple(c for c in tt_results if c.layer == "trend_template")
        names = {c.criterion_name for c in criteria}
        # Exactly 8 UNIQUE TT names: current_stage counts result='pass' rows blindly, so 8
        # duplicate passes would falsely seed stage_2 (spec section 6.1 missing/duplicate guard).
        if len(criteria) != 8 or len(names) != 8:
            raise ValueError(
                f"faithful seed needs exactly 8 UNIQUE trend_template rows, "
                f"got {len(criteria)} rows / {len(names)} distinct names"
            )
    else:
        raise ValueError(f"unknown stage mode: {mode!r}")

    iso = session.isoformat()
    run = EvaluationRun(
        id=None,
        run_ts=f"{iso}T00:00:00+00:00",
        data_asof_date=iso,
        action_session_date=iso,
        finviz_csv_path=None,
        tickers_evaluated=1,
        aplus_count=1,
        watch_count=0,
        skip_count=0,
        excluded_count=0,
        error_count=0,
    )
    with conn:
        run_id = insert_evaluation_run(conn, run)
        insert_candidates(conn, run_id, [_minimal_candidate(ticker, criteria)])


def stage_at(conn: sqlite3.Connection, ticker: str, session: date) -> str:
    return current_stage(conn, ticker, session)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_stage_db.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/stage_db.py tests/research/minervini_exemplar_recall/test_stage_db.py
git commit -m "feat(research): add synthetic stage DB with faithful and isolated variants"
git log -1 --format='%(trailers)'
```

---

## Task 7: H2 detector evaluation

**Files:**
- Create: `research/harness/minervini_exemplar_recall/detector_eval.py`
- Test: `tests/research/minervini_exemplar_recall/test_detector_eval.py`

For one `(exemplar, session, stage_conn)`: slice bars `<= session` (`min_bars=H2_MIN_BARS`), `generate_candidate_windows(..., "zigzag_pivot", ...)`, select `window = windows[-1]` (production-faithful — NOT all windows), run all 5 detectors via `_pattern_detect_registry()` against `stage_conn`, `fired = geometric_score > 0`. Skip taxonomy mirrors the cohort harness (never silent, gotcha #27). A mapped `cup_with_handle`/`high_tight_flag` MISS sets `h2_anchor_mode_limited_possible=True` (the V1 zigzag-only anchor confound, spec §12.9). `unmapped` exemplars have no expected class -> `fired_expected_class=None`.

The registry symbol is module-level (`_REGISTRY = _pattern_detect_registry`) so a test can monkeypatch it with a fake whose score depends only on `current_stage` — this exercises the harness's stage wiring deterministically without depending on real detector geometry (the real detectors are covered by `swing/patterns` tests + the slow integration test in Task 16).

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_detector_eval.py
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing.patterns.foundation import current_stage


def _uptrend_bars(n=300, start="2009-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    closes = []
    price = 50.0
    for i in range(n):
        # gentle zig-zag uptrend so generate_candidate_windows emits down-swings.
        price *= 1.004 if (i // 7) % 2 == 0 else 0.996
        closes.append(price)
    return pd.DataFrame(
        {"Open": closes, "High": [c * 1.01 for c in closes], "Low": [c * 0.99 for c in closes],
         "Close": closes, "Volume": [1_000_000] * n},
        index=idx,
    )


def _fake_registry_stage_gated():
    # A fake "vcp" detector: geometric_score = 1.0 iff Stage 2, else 0.0.
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Ev:
        geometric_score: float

    def _fake_vcp(bars, window, *, conn=None, ticker=None, asof_date=None):
        score = 1.0 if current_stage(conn, ticker, asof_date) == "stage_2" else 0.0
        return _Ev(geometric_score=score)

    return ((_fake_vcp, "vcp", "fake@v1"),)


def test_selects_last_window(monkeypatch):
    from research.harness.minervini_exemplar_recall import detector_eval

    bars = _uptrend_bars()
    from swing.patterns.foundation import generate_candidate_windows
    windows = generate_candidate_windows(bars, "zigzag_pivot", ticker="AAA", timeframe="daily")
    assert len(windows) >= 2  # fixture must yield multiple windows for this to discriminate
    selected = detector_eval.select_window(windows)
    # WRONG-PATH (windows[0] / all windows): a different anchor.  RIGHT-PATH (windows[-1]).
    assert selected.anchor_date == windows[-1].anchor_date


def test_stage_gate_isolation(monkeypatch, tmp_path):
    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    monkeypatch.setattr(detector_eval, "_REGISTRY", _fake_registry_stage_gated())
    bars = _uptrend_bars()
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "VCP", "vcp", session, "day", None, "S", "P", "n")

    iso_conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(iso_conn, ticker="AAA", session=session,
                          tt_results=_forced_fail_tt(), mode="isolated")
    v_iso = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=iso_conn)
    assert v_iso.fired_expected_class is True  # isolated -> stage_2 -> fires

    faith_conn = stage_db.build_stage_db(tmp_path / "faith.db")
    stage_db.seed_session(faith_conn, ticker="AAA", session=session,
                          tt_results=_seven_pass_tt(), mode="faithful")
    v_faith = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=faith_conn)
    # 7/8 TT -> undefined stage -> the Stage-2 hard gate zeros the score.
    assert v_faith.fired_expected_class is False


def test_unmapped_has_no_expected_class(monkeypatch, tmp_path):
    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    monkeypatch.setattr(detector_eval, "_REGISTRY", _fake_registry_stage_gated())
    bars = _uptrend_bars()
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "primary base", "unmapped", session, "day", None, "S", "P", "n")
    conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(conn, ticker="AAA", session=session, tt_results=_forced_fail_tt(), mode="isolated")
    v = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=conn)
    assert v.fired_expected_class is None  # unmapped -> excluded from per-detector recall


def test_anchor_mode_limited_flag_for_cup_miss(monkeypatch, tmp_path):
    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    # Fake registry where the cup detector never fires.
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Ev:
        geometric_score: float

    def _never(bars, window, *, conn=None, ticker=None, asof_date=None):
        return _Ev(0.0)

    monkeypatch.setattr(detector_eval, "_REGISTRY", ((_never, "cup_with_handle", "fake@v1"),))
    bars = _uptrend_bars()
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "cup", "cup_with_handle", session, "day", None, "S", "P", "n")
    conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(conn, ticker="AAA", session=session, tt_results=_forced_fail_tt(), mode="isolated")
    v = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=conn)
    assert v.fired_expected_class is False
    assert v.h2_anchor_mode_limited_possible is True
    assert "zigzag" in v.h2_anchor_mode_limited_reason.lower()


def test_no_windows_skip_is_not_silent(monkeypatch, tmp_path):
    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    monkeypatch.setattr(detector_eval, "_REGISTRY", _fake_registry_stage_gated())
    # Strictly monotonic up with no down-swing >=3% -> zigzag emits no windows.
    idx = pd.bdate_range(start="2009-01-02", periods=120)
    closes = [100.0 + i for i in range(120)]
    bars = pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes,
                         "Volume": [1_000] * 120}, index=idx)
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "VCP", "vcp", session, "day", None, "S", "P", "n")
    conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(conn, ticker="AAA", session=session, tt_results=_forced_fail_tt(), mode="isolated")
    v = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=conn)
    assert v.skip_reason == "no_windows"
    assert v.fired_expected_class is False


# --- helpers ---
def _forced_fail_tt():
    from swing.data.models import CriterionResult
    return tuple(CriterionResult(f"TT{i+1}", "trend_template", "fail") for i in range(8))


def _seven_pass_tt():
    from swing.data.models import CriterionResult
    res = ["pass"] * 7 + ["fail"]
    return tuple(CriterionResult(f"TT{i+1}", "trend_template", res[i]) for i in range(8))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_detector_eval.py -q`
Expected: FAIL — `ModuleNotFoundError: ...detector_eval` (or `AttributeError: _REGISTRY`).

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/detector_eval.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

import pandas as pd

from swing.patterns.foundation import CandidateWindow, generate_candidate_windows
from swing.pipeline.runner import _pattern_detect_registry

from .constants import H2_MIN_BARS
from .exemplar_reader import ExemplarRow
from .ohlcv_reader import slice_to

# Module-level so tests can monkeypatch with a fake registry. The production path
# resolves the real 5 detectors lazily on first call.
_REGISTRY = _pattern_detect_registry

_ANCHOR_MODE_LIMITED_CLASSES = frozenset({"cup_with_handle", "high_tight_flag"})
_SKIP_REASONS = frozenset(
    {"coverage_skip", "window_generation_error", "no_windows", "detector_error_all"}
)


@dataclass(frozen=True)
class DetectorVerdict:
    skip_reason: str | None
    fired_classes: tuple[str, ...]
    fired_any_class: bool
    fired_expected_class: bool | None  # None for unmapped
    geometric_by_class: dict[str, float]
    h2_anchor_mode_limited_possible: bool
    h2_anchor_mode_limited_reason: str | None


def select_window(windows: list[CandidateWindow]) -> CandidateWindow:
    """Production-faithful: the LAST (most-recent-anchor) window (runner.py:1776)."""
    return windows[-1]


def _resolve_registry():
    reg = _REGISTRY
    return reg() if callable(reg) else reg


def _skip_verdict(reason: str, expected_class: str | None) -> DetectorVerdict:
    anchor_limited = expected_class in _ANCHOR_MODE_LIMITED_CLASSES
    return DetectorVerdict(
        skip_reason=reason,
        fired_classes=(),
        fired_any_class=False,
        fired_expected_class=(None if expected_class == "unmapped" else False),
        geometric_by_class={},
        h2_anchor_mode_limited_possible=anchor_limited,
        h2_anchor_mode_limited_reason=(
            "V1 zigzag_pivot anchors swing-lows; swing-high-anchored "
            f"{expected_class} may be under-anchored (spec 12.9)"
            if anchor_limited
            else None
        ),
    )


def evaluate_h2(
    *,
    exemplar: ExemplarRow,
    session: date,
    exemplar_full: pd.DataFrame,
    stage_conn: sqlite3.Connection,
) -> DetectorVerdict:
    expected = exemplar.detector_class
    sliced = slice_to(exemplar_full, session)
    if len(sliced) < H2_MIN_BARS:
        return _skip_verdict("coverage_skip", expected)

    try:
        windows = generate_candidate_windows(
            sliced, "zigzag_pivot", ticker=exemplar.tiingo_symbol, timeframe="daily"
        )
    except Exception:  # noqa: BLE001 - window generation raised (non-monotonic / NaN)
        return _skip_verdict("window_generation_error", expected)
    if not windows:
        return _skip_verdict("no_windows", expected)

    window = select_window(windows)
    geometric_by_class: dict[str, float] = {}
    attempts = 0
    failures = 0
    for detector_fn, pattern_class, _version in _resolve_registry():
        attempts += 1
        try:
            evidence = detector_fn(
                sliced, window, conn=stage_conn, ticker=exemplar.tiingo_symbol, asof_date=session
            )
            geometric_by_class[pattern_class] = float(getattr(evidence, "geometric_score", 0.0))
        except Exception:  # noqa: BLE001 - isolate one bad detector, continue the others
            failures += 1
            continue

    if attempts > 0 and failures == attempts:
        return _skip_verdict("detector_error_all", expected)

    fired_classes = tuple(sorted(c for c, s in geometric_by_class.items() if s > 0.0))
    fired_any = len(fired_classes) > 0
    if expected == "unmapped":
        fired_expected: bool | None = None
    else:
        fired_expected = expected in fired_classes

    anchor_limited = (
        expected in _ANCHOR_MODE_LIMITED_CLASSES and fired_expected is False
    )
    return DetectorVerdict(
        skip_reason=None,
        fired_classes=fired_classes,
        fired_any_class=fired_any,
        fired_expected_class=fired_expected,
        geometric_by_class=geometric_by_class,
        h2_anchor_mode_limited_possible=anchor_limited,
        h2_anchor_mode_limited_reason=(
            "V1 zigzag_pivot anchors swing-lows; swing-high-anchored "
            f"{expected} may be under-anchored (spec 12.9)"
            if anchor_limited
            else None
        ),
    )


def evaluate_h2_all_windows(
    *,
    exemplar: ExemplarRow,
    session: date,
    exemplar_full: pd.DataFrame,
    stage_conn: sqlite3.Connection,
) -> list[dict]:
    """NON-PRODUCTION diagnostic (--h2-all-windows): run the 5 detectors against EVERY window,
    not just windows[-1]. Production uses windows[-1] only (runner.py:1776); this scan can turn a
    deployed miss into a harness hit on an older anchor, so it is written to a SEPARATE file clearly
    labeled non-production and never feeds results.csv (spec section 6 / 10.2)."""
    sliced = slice_to(exemplar_full, session)
    if len(sliced) < H2_MIN_BARS:
        return []
    try:
        windows = generate_candidate_windows(
            sliced, "zigzag_pivot", ticker=exemplar.tiingo_symbol, timeframe="daily"
        )
    except Exception:  # noqa: BLE001
        return []
    rows: list[dict] = []
    for wi, window in enumerate(windows):
        fired: list[str] = []
        for detector_fn, pattern_class, _v in _resolve_registry():
            try:
                ev = detector_fn(
                    sliced, window, conn=stage_conn, ticker=exemplar.tiingo_symbol, asof_date=session
                )
                if float(getattr(ev, "geometric_score", 0.0)) > 0.0:
                    fired.append(pattern_class)
            except Exception:  # noqa: BLE001
                continue
        rows.append({
            "exemplar_id": exemplar.exemplar_id,
            "ticker": exemplar.ticker,
            "session": session.isoformat(),
            "window_index": str(wi),
            "anchor_date": window.anchor_date.isoformat(),
            "fired_classes": ";".join(sorted(fired)),
        })
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_detector_eval.py -q`
Expected: PASS (6 tests). (`evaluate_h2_all_windows` is exercised by the Task 12 `--h2-all-windows` test and the slow integration test.) If the `test_selects_last_window` fixture yields <2 windows, tune `_uptrend_bars` (more zig-zag cycles) until `len(windows) >= 2` — do NOT weaken the assertion.

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/detector_eval.py tests/research/minervini_exemplar_recall/test_detector_eval.py
git commit -m "feat(research): add H2 detector-eval with windows[-1] selection and skip taxonomy"
git log -1 --format='%(trailers)'
```

---

## Task 8: Timing modes (single-session + window-sweep orchestration)

**Files:**
- Create: `research/harness/minervini_exemplar_recall/timing.py`
- Test: `tests/research/minervini_exemplar_recall/test_timing.py`

`sweep_sessions` computes POSITIONAL offsets in the full Tiingo history: `entry_pos` = first bar with `date >= entry_anchor`; window = `bars[max(0, entry_pos - window_back) : entry_pos + window_fwd + 1]`. The start clamps to 0 (a negative start would Python-wrap to the tail — the young-name failure mode). `evaluate_exemplar` orchestrates per mode per session: H1 -> seed BOTH stage DBs at that session from H1's `tt_criteria` (faithful) / forced (isolated) -> H2 both variants -> aggregate best-of (`aplus(2) > watch(1) > skip(0)`; H2 fired if it fired at ANY session). Each exemplar gets its own pair of physically separate scratch DBs.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_timing.py
from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow


def _bars(n=400, start="2009-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    closes = [100.0 + i for i in range(n)]
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes,
                         "Volume": [1_000] * n}, index=idx)


def test_sweep_window_positional_and_inclusive():
    from research.harness.minervini_exemplar_recall.timing import sweep_sessions

    bars = _bars()
    entry_anchor = bars.index[100].date()  # entry_pos == 100
    sessions = sweep_sessions(bars, entry_anchor, window_back=60, window_fwd=5)
    # bars[40:106] -> 66 sessions (60 back + entry + 5 fwd).
    # WRONG-PATH (off-by-one / calendar-day window): not 66.  RIGHT-PATH: 66.
    assert len(sessions) == 66
    assert sessions[0] == bars.index[40].date()
    assert sessions[-1] == bars.index[105].date()


def test_sweep_clamps_start_for_young_name():
    from research.harness.minervini_exemplar_recall.timing import sweep_sessions

    bars = _bars()
    entry_anchor = bars.index[20].date()  # entry_pos 20 < window_back 60
    sessions = sweep_sessions(bars, entry_anchor, window_back=60, window_fwd=5)
    # max(0, 20-60)=0 -> bars[0:26]; NOT a tail-wrap.
    assert sessions[0] == bars.index[0].date()
    assert sessions[-1] == bars.index[25].date()
    assert len(sessions) == 26


def test_entry_anchor_beyond_last_bar_yields_empty():
    from research.harness.minervini_exemplar_recall.timing import sweep_sessions

    bars = _bars()
    sessions = sweep_sessions(bars, date(2099, 1, 1), window_back=60, window_fwd=5)
    assert sessions == []


def test_best_bucket_ordering():
    from research.harness.minervini_exemplar_recall.timing import best_bucket_of

    # aplus(2) > watch(1) > skip(0); no_data/insufficient map to skip-rank 0.
    assert best_bucket_of(["skip", "watch", "skip"]) == "watch"
    assert best_bucket_of(["watch", "aplus", "skip"]) == "aplus"
    assert best_bucket_of(["skip", "skip"]) == "skip"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_timing.py -q`
Expected: FAIL — `ModuleNotFoundError: ...timing`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/timing.py
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from swing.config import Config

from . import detector_eval, screen_eval, stage_db
from .detector_eval import DetectorVerdict
from .exemplar_reader import ExemplarRow
from .screen_eval import ScreenResult

_BUCKET_RANK = {"aplus": 2, "watch": 1, "skip": 0}
_OUTCOME_RANK = {
    "surfaced_aplus": 4,
    "surfaced_watch": 3,
    "skip_gate_rejection": 2,
    "skip_insufficient_history": 1,
    "no_data": 0,
}


@dataclass(frozen=True)
class SessionEval:
    session: date
    screen: ScreenResult
    h2_faithful: DetectorVerdict
    h2_isolated: DetectorVerdict


@dataclass(frozen=True)
class ExemplarTimingResult:
    mode: str  # "single_session" | "window_sweep"
    sessions: tuple[SessionEval, ...]
    best_bucket: str
    best_h1_outcome: str
    h2_faithful_fired_expected: bool
    h2_isolated_fired_expected: bool
    firing_sessions_faithful: tuple[date, ...]
    firing_sessions_isolated: tuple[date, ...]


def _entry_pos(bars: pd.DataFrame, entry_anchor: date) -> int | None:
    mask = bars.index.date >= entry_anchor
    if not mask.any():
        return None
    return int(mask.argmax())


def sweep_sessions(
    bars: pd.DataFrame, entry_anchor: date, *, window_back: int, window_fwd: int
) -> list[date]:
    pos = _entry_pos(bars, entry_anchor)
    if pos is None:
        return []
    start = max(0, pos - window_back)
    end = pos + window_fwd + 1  # inclusive of the +window_fwd bar; truncates at len naturally
    return [d.date() for d in bars.index[start:end]]


def single_session(bars: pd.DataFrame, entry_anchor: date) -> list[date]:
    pos = _entry_pos(bars, entry_anchor)
    return [] if pos is None else [bars.index[pos].date()]


def best_bucket_of(buckets) -> str:
    best = "skip"
    for b in buckets:
        if _BUCKET_RANK.get(b, 0) > _BUCKET_RANK.get(best, 0):
            best = b
    return best


def _eval_one_session(
    *,
    exemplar: ExemplarRow,
    session: date,
    exemplar_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
    config: Config,
    faith_conn,
    iso_conn,
) -> SessionEval:
    screen = screen_eval.evaluate_h1(
        ticker=exemplar.tiingo_symbol,
        exemplar_full=exemplar_full,
        spy_full=spy_full,
        session=session,
        config=config,
    )
    # Seed isolated (always); seed faithful only when we have the 8 TT (no_data has none).
    stage_db.seed_session(
        iso_conn, ticker=exemplar.tiingo_symbol, session=session, tt_results=(), mode="isolated"
    )
    if len(screen.tt_criteria) == 8:
        stage_db.seed_session(
            faith_conn,
            ticker=exemplar.tiingo_symbol,
            session=session,
            tt_results=screen.tt_criteria,
            mode="faithful",
        )
        h2_faith = detector_eval.evaluate_h2(
            exemplar=exemplar, session=session, exemplar_full=exemplar_full, stage_conn=faith_conn
        )
    else:
        h2_faith = detector_eval._skip_verdict("coverage_skip", exemplar.detector_class)
    h2_iso = detector_eval.evaluate_h2(
        exemplar=exemplar, session=session, exemplar_full=exemplar_full, stage_conn=iso_conn
    )
    return SessionEval(session=session, screen=screen, h2_faithful=h2_faith, h2_isolated=h2_iso)


def _aggregate(mode: str, evals: list[SessionEval]) -> ExemplarTimingResult:
    if not evals:
        return ExemplarTimingResult(mode, (), "skip", "no_data", False, False, (), ())
    best_bucket = best_bucket_of([e.screen.bucket or "skip" for e in evals])
    best_outcome = max((e.screen.outcome for e in evals), key=lambda o: _OUTCOME_RANK.get(o, 0))
    fire_faith = tuple(e.session for e in evals if e.h2_faithful.fired_expected_class is True)
    fire_iso = tuple(e.session for e in evals if e.h2_isolated.fired_expected_class is True)
    return ExemplarTimingResult(
        mode=mode,
        sessions=tuple(evals),
        best_bucket=best_bucket,
        best_h1_outcome=best_outcome,
        h2_faithful_fired_expected=len(fire_faith) > 0,
        h2_isolated_fired_expected=len(fire_iso) > 0,
        firing_sessions_faithful=fire_faith,
        firing_sessions_isolated=fire_iso,
    )


def evaluate_exemplar(
    exemplar: ExemplarRow,
    *,
    exemplar_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
    config: Config,
    window_back: int = 60,
    window_fwd: int = 5,
) -> dict[str, ExemplarTimingResult]:
    out: dict[str, ExemplarTimingResult] = {}
    modes = {
        "single_session": single_session(exemplar_full, exemplar.entry_anchor),
        "window_sweep": sweep_sessions(
            exemplar_full, exemplar.entry_anchor, window_back=window_back, window_fwd=window_fwd
        ),
    }
    for mode, sessions in modes.items():
        with tempfile.TemporaryDirectory() as td:
            faith_conn = stage_db.build_stage_db(Path(td) / "faithful.db")
            iso_conn = stage_db.build_stage_db(Path(td) / "isolated.db")
            try:
                evals = [
                    _eval_one_session(
                        exemplar=exemplar,
                        session=s,
                        exemplar_full=exemplar_full,
                        spy_full=spy_full,
                        config=config,
                        faith_conn=faith_conn,
                        iso_conn=iso_conn,
                    )
                    for s in sessions
                ]
            finally:
                faith_conn.close()
                iso_conn.close()
        out[mode] = _aggregate(mode, evals)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_timing.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/timing.py tests/research/minervini_exemplar_recall/test_timing.py
git commit -m "feat(research): add timing-mode orchestration with positional window sweep"
git log -1 --format='%(trailers)'
```

---

## Task 9: Negative-control cohort

**Files:**
- Create: `research/harness/minervini_exemplar_recall/control_cohort.py`
- Test: `tests/research/minervini_exemplar_recall/test_control_cohort.py`

For each exemplar ticker, sample K (default 5) random sessions from its Tiingo history with: `|session_pos - entry_pos| >= 120`, outside the sweep window `[entry_pos - window_back, entry_pos + window_fwd]`, and `>= screenable_floor` preceding bars (so H1 can run fairly). Deterministic: `random.Random(base_seed + exemplar_index)`. Each control anchor is evaluated in BOTH timing modes with identical aggregation (Codex R1.M4: a single-day control vs a 66-session best-of exemplar would understate firing -> mode-to-mode comparison). This is a SAME-TICKER temporal-specificity contrast, NOT a population base rate.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_control_cohort.py
from __future__ import annotations

import pandas as pd


def _bars(n=800, start="2007-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    closes = [100.0 + i for i in range(n)]
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes,
                         "Volume": [1_000] * n}, index=idx)


def test_sample_respects_gap_and_floor_and_window():
    from research.harness.minervini_exemplar_recall.control_cohort import sample_control_anchors

    bars = _bars()
    entry_pos = 500
    entry_anchor = bars.index[entry_pos].date()
    anchors = sample_control_anchors(
        bars, entry_anchor, k=5, window_back=60, window_fwd=5, screenable_floor=221,
        base_seed=20260608, exemplar_index=3,
    )
    assert len(anchors) == 5
    for a in anchors:
        # >=120bd gap from entry
        assert abs(a.session_pos - entry_pos) >= 120
        # >= screenable_floor preceding bars (so position index >= 220)
        assert a.session_pos >= 220
        # outside the sweep window
        assert not (entry_pos - 60 <= a.session_pos <= entry_pos + 5)


def test_sampling_is_deterministic():
    from research.harness.minervini_exemplar_recall.control_cohort import sample_control_anchors

    bars = _bars()
    entry_anchor = bars.index[500].date()
    kw = dict(k=5, window_back=60, window_fwd=5, screenable_floor=221, base_seed=20260608, exemplar_index=3)
    a1 = sample_control_anchors(bars, entry_anchor, **kw)
    a2 = sample_control_anchors(bars, entry_anchor, **kw)
    # WRONG-PATH (Random() unseeded): different sessions.  RIGHT-PATH: identical.
    assert [x.session_pos for x in a1] == [x.session_pos for x in a2]


def test_distinct_exemplar_index_changes_sample():
    from research.harness.minervini_exemplar_recall.control_cohort import sample_control_anchors

    bars = _bars()
    entry_anchor = bars.index[500].date()
    base = dict(k=5, window_back=60, window_fwd=5, screenable_floor=221, base_seed=20260608)
    a3 = sample_control_anchors(bars, entry_anchor, exemplar_index=3, **base)
    a4 = sample_control_anchors(bars, entry_anchor, exemplar_index=4, **base)
    assert [x.session_pos for x in a3] != [x.session_pos for x in a4]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_control_cohort.py -q`
Expected: FAIL — `ModuleNotFoundError: ...control_cohort`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/control_cohort.py
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

import pandas as pd

from swing.config import Config

from . import timing
from .constants import CONTROL_GAP_BARS
from .exemplar_reader import ExemplarRow
from .timing import ExemplarTimingResult


@dataclass(frozen=True)
class ControlAnchor:
    session: date
    session_pos: int


def _entry_pos(bars: pd.DataFrame, entry_anchor: date) -> int | None:
    mask = bars.index.date >= entry_anchor
    return int(mask.argmax()) if mask.any() else None


def sample_control_anchors(
    bars: pd.DataFrame,
    entry_anchor: date,
    *,
    k: int,
    window_back: int,
    window_fwd: int,
    screenable_floor: int,
    base_seed: int,
    exemplar_index: int,
) -> list[ControlAnchor]:
    pos = _entry_pos(bars, entry_anchor)
    if pos is None:
        return []
    n = len(bars)
    candidates = [
        p
        for p in range(n)
        if p >= screenable_floor - 1  # >= screenable_floor preceding bars (inclusive of p)
        and abs(p - pos) >= CONTROL_GAP_BARS
        and not (pos - window_back <= p <= pos + window_fwd)
    ]
    rng = random.Random(base_seed + exemplar_index)
    chosen = sorted(rng.sample(candidates, min(k, len(candidates))))
    return [ControlAnchor(session=bars.index[p].date(), session_pos=p) for p in chosen]


def evaluate_control(
    exemplar: ExemplarRow,
    anchor: ControlAnchor,
    *,
    exemplar_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
    config: Config,
    window_back: int = 60,
    window_fwd: int = 5,
) -> dict[str, ExemplarTimingResult]:
    # Evaluate the control anchor with the SAME orchestration as an exemplar (both modes,
    # mode-to-mode) by treating the control date as the anchor and reusing the parent's class.
    control_ex = ExemplarRow(
        exemplar_id=f"{exemplar.exemplar_id}__control@{anchor.session.isoformat()}",
        ticker=exemplar.ticker,
        tiingo_symbol=exemplar.tiingo_symbol,
        setup_label=exemplar.setup_label,
        detector_class=exemplar.detector_class,
        entry_anchor=anchor.session,
        date_precision="day",
        buy_point_price=None,
        source=exemplar.source,
        page=exemplar.page,
        notes="negative-control",
    )
    return timing.evaluate_exemplar(
        control_ex,
        exemplar_full=exemplar_full,
        spy_full=spy_full,
        config=config,
        window_back=window_back,
        window_fwd=window_fwd,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_control_cohort.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/control_cohort.py tests/research/minervini_exemplar_recall/test_control_cohort.py
git commit -m "feat(research): add same-ticker negative-control cohort sampling"
git log -1 --format='%(trailers)'
```

---

## Task 10: Recall scorecard (Wilson + ticker-clustered bootstrap)

**Files:**
- Create: `research/harness/minervini_exemplar_recall/scorecard.py`
- Test: `tests/research/minervini_exemplar_recall/test_scorecard.py`

Wilson score interval is PRIMARY (exact for a proportion at small n; computed on the screenable subset, full-set reported alongside). The ticker-clustered bootstrap (EXPLORATORY, B=2000) resamples TICKERS not rows, so AMZN's two rows move together (Codex R1.M5). Both are descriptive; no inferential test claimed.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_scorecard.py
from __future__ import annotations

import pytest


def test_wilson_interval_known_value():
    from research.harness.minervini_exemplar_recall.scorecard import wilson_interval

    ci = wilson_interval(8, 10, z=1.96)
    # Wilson 95% CI for 8/10 at z=1.96:
    #   center = (0.8 + 1.96^2/20)/(1 + 1.96^2/10) = 0.716738
    #   half   = 1.96*sqrt(0.8*0.2/10 + 1.96^2/400)/(1 + 1.96^2/10) = 0.226582
    # WRONG-PATH (normal/Wald): lower = 0.8 - 0.2479 = 0.5521.  RIGHT-PATH (Wilson): 0.4902.
    assert ci.lower == pytest.approx(0.4902, abs=1e-3)
    assert ci.upper == pytest.approx(0.9433, abs=1e-3)
    assert ci.p_hat == pytest.approx(0.8)
    assert ci.n == 10


def test_wilson_interval_n_zero_is_uninformative():
    from research.harness.minervini_exemplar_recall.scorecard import wilson_interval

    ci = wilson_interval(0, 0)
    assert ci.lower == 0.0 and ci.upper == 1.0 and ci.n == 0


def test_clustered_resample_keeps_amzn_rows_together():
    import random

    from research.harness.minervini_exemplar_recall.scorecard import _clustered_resample

    by_ticker = {"AMZN": [("AMZN", True), ("AMZN", False)], "MSFT": [("MSFT", True)], "CSCO": [("CSCO", True)]}
    rng = random.Random(123)
    for _ in range(500):
        rows = _clustered_resample(rng, by_ticker)
        amzn = sum(1 for r in rows if r[0] == "AMZN")
        # WRONG-PATH (IID row bootstrap): AMZN count can be odd.
        # RIGHT-PATH (cluster on ticker): AMZN's two rows always move together -> even.
        assert amzn % 2 == 0


def test_bootstrap_is_deterministic():
    from research.harness.minervini_exemplar_recall.scorecard import ticker_clustered_bootstrap

    rows = [("AMZN", True), ("AMZN", False), ("MSFT", True), ("CSCO", True), ("INTC", False)]
    val = lambda rs: sum(1 for _, ok in rs if ok) / len(rs) if rs else 0.0
    a = ticker_clustered_bootstrap(rows, val, b=200, base_seed=7)
    b = ticker_clustered_bootstrap(rows, val, b=200, base_seed=7)
    assert (a.lower, a.upper) == (b.lower, b.upper)
    assert a.b == 200


def test_screening_recall_stratified_excludes_attrition():
    from research.harness.minervini_exemplar_recall.scorecard import screening_recall

    # 10 total: 4 surfaced, 2 gate-skip, 3 insufficient, 1 no_data.
    outcomes = (["surfaced_aplus"] * 2 + ["surfaced_watch"] * 2 + ["skip_gate_rejection"] * 2
                + ["skip_insufficient_history"] * 3 + ["no_data"])
    full, screenable = screening_recall(outcomes)
    # full = 4/10 = 0.4 ; screenable denom excludes insufficient+no_data -> 4/6.
    assert full == pytest.approx(0.4)
    assert screenable == pytest.approx(4 / 6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_scorecard.py -q`
Expected: FAIL — `ModuleNotFoundError: ...scorecard`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/scorecard.py
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Sequence

_SURFACED = {"surfaced_aplus", "surfaced_watch"}
_ATTRITION = {"skip_insufficient_history", "no_data"}


@dataclass(frozen=True)
class WilsonInterval:
    lower: float
    upper: float
    p_hat: float
    n: int


@dataclass(frozen=True)
class BootstrapInterval:
    lower: float
    upper: float
    b: int


def wilson_interval(successes: int, n: int, z: float = 1.96) -> WilsonInterval:
    if n == 0:
        return WilsonInterval(0.0, 1.0, 0.0, 0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return WilsonInterval(lower=center - half, upper=center + half, p_hat=p, n=n)


def _clustered_resample(rng: random.Random, by_ticker: dict[str, list]) -> list:
    tickers = sorted(by_ticker)
    drawn = [rng.choice(tickers) for _ in tickers]
    rows: list = []
    for t in drawn:
        rows.extend(by_ticker[t])  # whole ticker's rows move together
    return rows


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = q / 100.0 * (len(s) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def ticker_clustered_bootstrap(
    rows: Sequence[tuple], value_fn: Callable[[Sequence[tuple]], float], *, b: int, base_seed: int
) -> BootstrapInterval:
    by_ticker: dict[str, list] = {}
    for row in rows:
        by_ticker.setdefault(row[0], []).append(row)
    rng = random.Random(base_seed)
    stats = [value_fn(_clustered_resample(rng, by_ticker)) for _ in range(b)]
    return BootstrapInterval(lower=_percentile(stats, 2.5), upper=_percentile(stats, 97.5), b=b)


def screening_recall(outcomes: Sequence[str]) -> tuple[float, float]:
    """Returns (full_set_recall, screenable_subset_recall)."""
    n_total = len(outcomes)
    surfaced = sum(1 for o in outcomes if o in _SURFACED)
    screenable = sum(1 for o in outcomes if o not in _ATTRITION)
    full = surfaced / n_total if n_total else 0.0
    sub = surfaced / screenable if screenable else 0.0
    return full, sub
```

This task delivers the load-bearing statistical primitives + their discriminating tests. The `Scorecard` aggregate dataclass + `build_scorecard` (which stitches bucket-distribution, the per-gate attribution histogram, per-detector recall with the isolated-minus-faithful Stage-2 delta, and the same-ticker specificity contrast) are added to this same `scorecard.py` file in Task 11 with concrete code, since they consume the `ExemplarSummary` records that `run.py` (Task 12) builds.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_scorecard.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/scorecard.py tests/research/minervini_exemplar_recall/test_scorecard.py
git commit -m "feat(research): add Wilson interval and ticker-clustered bootstrap primitives"
git log -1 --format='%(trailers)'
```

---

## Task 11: Scorecard aggregate + output writers

**Files:**
- Modify: `research/harness/minervini_exemplar_recall/scorecard.py` (add `ExemplarSummary`, `ControlSummary`, `DetectorRecall`, `Scorecard`, `build_scorecard`)
- Create: `research/harness/minervini_exemplar_recall/output.py`
- Test: `tests/research/minervini_exemplar_recall/test_scorecard_aggregate.py`
- Test: `tests/research/minervini_exemplar_recall/test_output.py`

`build_scorecard` is a pure function over simple `ExemplarSummary` records (one per exemplar, for ONE timing mode) + `ControlSummary` records. Per-detector recall denominators count only MAPPED exemplars of that class (`unmapped` excluded — `fired_expected` is `None`). The Stage-2 delta = isolated_rate - faithful_rate per class. Output writers emit the `results.csv` / `per_session.csv` / `summary.md` / `manifest.json` quartet (mirroring `pattern_cohort_evaluator/output.py`), ASCII-only (`text.encode("cp1252")` guard), with `l2_lock_preserved: True` in the manifest.

- [ ] **Step 1: Write the failing tests**

```python
# tests/research/minervini_exemplar_recall/test_scorecard_aggregate.py
from __future__ import annotations

import pytest

from research.harness.minervini_exemplar_recall.scorecard import (
    ControlSummary,
    ExemplarSummary,
    build_scorecard,
)


_ALL_PASS = {"risk_feasibility": True, "trend_template": True, "vcp": True}


def _ex(eid, ticker, cls, outcome, gate=None, faith=None, iso=None, gate_passes="auto"):
    # Default: screenable outcomes get an all-pass gate_passes (so they don't trip the
    # build_scorecard missing-threading guard); attrition outcomes get None.
    if gate_passes == "auto":
        gate_passes = None if outcome in ("skip_insufficient_history", "no_data") else _ALL_PASS
    return ExemplarSummary(eid, ticker, cls, outcome, gate, faith, iso, gate_passes)


def test_build_scorecard_detector_recall_excludes_unmapped():
    exemplars = [
        _ex("a", "CRUS", "vcp", "surfaced_aplus", None, True, True),
        _ex("b", "ANSS", "vcp", "surfaced_watch", None, False, True),
        _ex("c", "GRA", "unmapped", "surfaced_aplus", None, None, None),
    ]
    sc = build_scorecard("window_sweep", exemplars, [], bootstrap_b=50, base_seed=1)
    fired, denom = sc.detector_recall.per_class_faithful["vcp"]
    # 2 mapped vcp exemplars; 1 fired faithful. unmapped 'c' is NOT in the denom.
    # WRONG-PATH (counts unmapped): denom 3.  RIGHT-PATH: denom 2.
    assert (fired, denom) == (1, 2)
    # isolated: both vcp fired -> 2/2. delta = 2/2 - 1/2 = 0.5.
    assert sc.detector_recall.per_class_isolated["vcp"] == (2, 2)
    assert sc.detector_recall.stage2_delta["vcp"] == pytest.approx(0.5)


def test_build_scorecard_gate_histogram_over_skip_gate_rejection():
    exemplars = [
        _ex("a", "T1", "vcp", "skip_gate_rejection", "risk_feasibility"),
        _ex("b", "T2", "vcp", "skip_gate_rejection", "vcp"),
        _ex("c", "T3", "vcp", "skip_gate_rejection", "risk_feasibility"),
        _ex("d", "T4", "vcp", "skip_insufficient_history", None),  # excluded from histogram
    ]
    sc = build_scorecard("window_sweep", exemplars, [], bootstrap_b=50, base_seed=1)
    assert sc.gate_attribution_hist == {"risk_feasibility": 2, "vcp": 1}


def test_build_scorecard_specificity_contrast_from_controls():
    exemplars = [_ex("a", "CRUS", "vcp", "surfaced_aplus", None, True, True)]
    controls = [
        ControlSummary("CRUS", "vcp", surfaced=False, fired_faithful=False, fired_isolated=True),
        ControlSummary("CRUS", "vcp", surfaced=True, fired_faithful=False, fired_isolated=False),
    ]
    sc = build_scorecard("window_sweep", exemplars, controls, bootstrap_b=50, base_seed=1)
    # control surfaced rate 1/2; isolated-fire rate 1/2 -> labeled temporal-specificity contrast.
    assert sc.specificity_contrast["control_surfaced_rate"] == pytest.approx(0.5)
    assert sc.specificity_contrast["control_fired_isolated_rate"] == pytest.approx(0.5)


def test_build_scorecard_per_gate_pass_rate_over_screenable():
    exemplars = [
        _ex("a", "T1", "vcp", "surfaced_aplus", gate_passes={"risk_feasibility": True, "trend_template": True, "vcp": True}),
        _ex("b", "T2", "vcp", "skip_gate_rejection", "vcp", gate_passes={"risk_feasibility": True, "trend_template": True, "vcp": False}),
        # insufficient-history exemplar -> EXCLUDED from the per-gate denominator (gate_passes None).
        _ex("c", "T3", "vcp", "skip_insufficient_history", None, gate_passes=None),
    ]
    sc = build_scorecard("window_sweep", exemplars, [], bootstrap_b=50, base_seed=1)
    # denom = 2 screenable; vcp gate passed 1/2; risk + tt passed 2/2.
    # WRONG-PATH (denom includes insufficient): /3.  RIGHT-PATH: /2.
    assert sc.per_gate_pass_rate_screenable["vcp"] == pytest.approx(0.5)
    assert sc.per_gate_pass_rate_screenable["risk_feasibility"] == pytest.approx(1.0)
    assert sc.per_gate_pass_rate_screenable["trend_template"] == pytest.approx(1.0)


def test_build_scorecard_raises_on_screenable_missing_gate_passes():
    # A screenable exemplar with gate_passes None is a threading bug -> raise loudly (not silently
    # shrink the denominator). WRONG-PATH (filter-and-continue): rates silently overstated.
    bad = [_ex("a", "T1", "vcp", "surfaced_aplus", None, True, True, gate_passes=None)]
    with pytest.raises(ValueError, match="threading bug"):
        build_scorecard("window_sweep", bad, [], bootstrap_b=10, base_seed=1)
```

```python
# tests/research/minervini_exemplar_recall/test_output.py
from __future__ import annotations

import csv
import json

from research.harness.minervini_exemplar_recall.output import (
    RESULTS_HEADER,
    write_manifest_json,
    write_results_csv,
)


def _row(**kw):
    base = {
        "exemplar_id": "a", "ticker": "CRUS", "timing_mode": "window_sweep",
        "h1_outcome": "surfaced_aplus", "best_bucket": "aplus", "first_rejecting_gate": "",
        "h2_fired_faithful": "True", "h2_fired_isolated": "True",
        "fired_classes_faithful": "vcp", "fired_classes_isolated": "vcp",
        "rs_path": "P0", "data_source": "tiingo", "n_bars": "250", "screenable": "True",
        "h2_anchor_mode_limited_possible": "False", "h2_anchor_mode_limited_reason": "",
    }
    base.update(kw)
    return base


def test_results_csv_header_and_ascii(tmp_path):
    path = tmp_path / "results.csv"
    write_results_csv([_row()], path)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
    assert header == list(RESULTS_HEADER)
    # ASCII / cp1252 round-trip must not raise.
    path.read_text(encoding="utf-8").encode("cp1252")


def test_manifest_has_l2_lock_and_config_snapshot(tmp_path):
    path = tmp_path / "manifest.json"
    write_manifest_json({"harness_version": "0.1.0", "config_snapshot": {"min_passes": 7}}, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True
    assert data["config_snapshot"]["min_passes"] == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_scorecard_aggregate.py tests/research/minervini_exemplar_recall/test_output.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_scorecard'` / `ModuleNotFoundError: ...output`.

- [ ] **Step 3: Write minimal implementation**

Append to `scorecard.py`:

```python
# --- aggregate (appended to research/harness/minervini_exemplar_recall/scorecard.py) ---
from collections import Counter


@dataclass(frozen=True)
class ExemplarSummary:
    exemplar_id: str
    ticker: str
    detector_class: str
    h1_outcome: str
    first_rejecting_gate: str | None
    h2_faithful_fired_expected: bool | None  # None for unmapped
    h2_isolated_fired_expected: bool | None
    gate_passes: dict[str, bool] | None = None  # per-gate pass at the representative screenable session


@dataclass(frozen=True)
class ControlSummary:
    ticker: str
    detector_class: str
    surfaced: bool
    fired_faithful: bool
    fired_isolated: bool


@dataclass(frozen=True)
class DetectorRecall:
    per_class_faithful: dict[str, tuple[int, int]]
    per_class_isolated: dict[str, tuple[int, int]]
    overall_faithful: tuple[int, int]
    overall_isolated: tuple[int, int]
    stage2_delta: dict[str, float]


@dataclass(frozen=True)
class Scorecard:
    mode: str
    bucket_distribution: dict[str, int]
    screening_recall_full: float
    screening_recall_screenable: float
    screening_wilson_screenable: WilsonInterval
    screening_bootstrap_screenable: BootstrapInterval
    gate_attribution_hist: dict[str, int]
    per_gate_pass_rate_screenable: dict[str, float]
    detector_recall: DetectorRecall
    specificity_contrast: dict[str, float]


def _rate(num: int, den: int) -> float:
    return num / den if den else 0.0


def _detector_recall(exemplars: list[ExemplarSummary]) -> DetectorRecall:
    classes = sorted({e.detector_class for e in exemplars if e.detector_class != "unmapped"})
    per_f: dict[str, tuple[int, int]] = {}
    per_i: dict[str, tuple[int, int]] = {}
    delta: dict[str, float] = {}
    of_f = oi_f = of_i = oi_i = 0
    for cls in classes:
        mapped = [e for e in exemplars if e.detector_class == cls and e.h2_faithful_fired_expected is not None]
        denom = len(mapped)
        fired_f = sum(1 for e in mapped if e.h2_faithful_fired_expected)
        fired_i = sum(1 for e in mapped if e.h2_isolated_fired_expected)
        per_f[cls] = (fired_f, denom)
        per_i[cls] = (fired_i, denom)
        delta[cls] = _rate(fired_i, denom) - _rate(fired_f, denom)
        of_f += fired_f; oi_f += denom; of_i += fired_i; oi_i += denom
    return DetectorRecall(per_f, per_i, (of_f, oi_f), (of_i, oi_i), delta)


def build_scorecard(
    mode: str,
    exemplars: list[ExemplarSummary],
    controls: list[ControlSummary],
    *,
    bootstrap_b: int,
    base_seed: int,
) -> Scorecard:
    outcomes = [e.h1_outcome for e in exemplars]
    full, screenable = screening_recall(outcomes)
    screenable_rows = [
        (e.ticker, e.h1_outcome in _SURFACED) for e in exemplars if e.h1_outcome not in _ATTRITION
    ]
    successes = sum(1 for _, ok in screenable_rows if ok)
    wilson = wilson_interval(successes, len(screenable_rows))
    boot = ticker_clustered_bootstrap(
        screenable_rows,
        lambda rs: _rate(sum(1 for _, ok in rs if ok), len(rs)),
        b=bootstrap_b,
        base_seed=base_seed,
    )
    gate_hist = dict(
        Counter(
            e.first_rejecting_gate
            for e in exemplars
            if e.h1_outcome == "skip_gate_rejection" and e.first_rejecting_gate
        )
    )
    # Per-gate pass rate over the FULL screenable subset (spec section 9 -> histogram AND pass rate).
    # Denominator = every screenable exemplar; a screenable row missing gate_passes is a threading
    # bug (evaluate_h1 ALWAYS sets gate_passes for surfaced/gate_rejection outcomes) -> raise loudly
    # rather than silently shrink the denominator and overstate pass rates (Codex R2).
    screenable_ex = [e for e in exemplars if e.h1_outcome not in _ATTRITION]
    missing_gp = [e.exemplar_id for e in screenable_ex if e.gate_passes is None]
    if missing_gp:
        raise ValueError(
            f"per-gate pass rate: {len(missing_gp)} screenable exemplar(s) missing gate_passes "
            f"(threading bug): {missing_gp}"
        )
    per_gate_pass = {
        g: _rate(sum(1 for e in screenable_ex if e.gate_passes.get(g)), len(screenable_ex))
        for g in ("risk_feasibility", "trend_template", "vcp")
    }
    # Spec section 8: unmapped exemplars contribute SCREENING (H1) controls only -> the H2
    # fired-rate denominators exclude unmapped controls (they have no expected class to fire).
    mapped_controls = [c for c in controls if c.detector_class != "unmapped"]
    spec = {
        "control_surfaced_rate": _rate(sum(1 for c in controls if c.surfaced), len(controls)),
        "control_fired_faithful_rate": _rate(sum(1 for c in mapped_controls if c.fired_faithful), len(mapped_controls)),
        "control_fired_isolated_rate": _rate(sum(1 for c in mapped_controls if c.fired_isolated), len(mapped_controls)),
        "control_n": float(len(controls)),
        "control_n_mapped": float(len(mapped_controls)),
    }
    return Scorecard(
        mode=mode,
        bucket_distribution=dict(Counter(outcomes)),
        screening_recall_full=full,
        screening_recall_screenable=screenable,
        screening_wilson_screenable=wilson,
        screening_bootstrap_screenable=boot,
        gate_attribution_hist=gate_hist,
        per_gate_pass_rate_screenable=per_gate_pass,
        detector_recall=_detector_recall(exemplars),
        specificity_contrast=spec,
    )
```

Create `output.py`:

```python
# research/harness/minervini_exemplar_recall/output.py
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

RESULTS_HEADER = (
    "exemplar_id",
    "ticker",
    "timing_mode",
    "h1_outcome",
    "best_bucket",
    "first_rejecting_gate",
    "h2_fired_faithful",
    "h2_fired_isolated",
    "fired_classes_faithful",
    "fired_classes_isolated",
    "rs_path",
    "data_source",
    "n_bars",
    "screenable",
    "h2_anchor_mode_limited_possible",
    "h2_anchor_mode_limited_reason",
)

PER_SESSION_HEADER = (
    "exemplar_id",
    "ticker",
    "timing_mode",
    "session",
    "h1_outcome",
    "bucket",
    "fired_faithful_expected",
    "fired_isolated_expected",
    "fired_classes",
)

H2_ALL_WINDOWS_HEADER = (
    "exemplar_id",
    "ticker",
    "timing_mode",
    "session",
    "window_index",
    "anchor_date",
    "fired_classes",
)


def _assert_ascii(text: str) -> str:
    text.encode("cp1252")  # raises if a non-cp1252 glyph slipped in
    return text


def _write_csv(header, rows, path: Path) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    Path(path).write_text(_assert_ascii(buf.getvalue()), encoding="utf-8")


def write_results_csv(rows, path: Path) -> None:
    _write_csv(RESULTS_HEADER, rows, path)


def write_per_session_csv(rows, path: Path) -> None:
    _write_csv(PER_SESSION_HEADER, rows, path)


def write_h2_all_windows_csv(rows, path: Path) -> None:
    _write_csv(H2_ALL_WINDOWS_HEADER, rows, path)


def write_manifest_json(manifest: dict, path: Path) -> None:
    payload = dict(manifest)
    payload.setdefault("l2_lock_preserved", True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(_assert_ascii(text), encoding="utf-8")


def write_summary_md(lines: list[str], path: Path) -> None:
    body = "\n".join(lines) + "\n"
    Path(path).write_text(_assert_ascii(body), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_scorecard_aggregate.py tests/research/minervini_exemplar_recall/test_output.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/scorecard.py research/harness/minervini_exemplar_recall/output.py tests/research/minervini_exemplar_recall/test_scorecard_aggregate.py tests/research/minervini_exemplar_recall/test_output.py
git commit -m "feat(research): add scorecard aggregate and ASCII-guarded output writers"
git log -1 --format='%(trailers)'
```

---

## Task 12: Harness entry (`run_harness`) + CLI registration

**Files:**
- Create: `research/harness/minervini_exemplar_recall/run.py`
- Modify: `swing/cli.py` (add the `diagnose minervini-recall` command — the ONLY `swing/` edit in this plan)
- Test: `tests/research/minervini_exemplar_recall/test_run_cli.py`

`run_harness` reads exemplars + SPY once, loops exemplars (single-session + window-sweep via `timing.evaluate_exemplar`), samples + evaluates controls, builds the per-mode scorecards, and writes the quartet into `output_dir / f"minervini-exemplar-recall-{iso}"`. The CLI command mirrors `aplus-sensitivity-v2` (deferred import, `ValueError -> click.ClickException`) but has NO `--db` (H1 is pure, equity is the floor surrogate, stage is synthetic). `--h2-all-windows` (default off) writes a SEPARATE `h2_all_windows_diagnostic.csv` labeled non-production.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_run_cli.py
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main


def _make_exemplar_csv(path: Path) -> None:
    header = (
        "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
        "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes"
    )
    path.write_text(header + "\nid-a,AAA,VCP,vcp,2010-03-30,,,,,day,S,P,claude,yes,n\n", encoding="utf-8")


def test_value_error_becomes_click_exception(tmp_path):
    runner = CliRunner()
    # Nonexistent exemplars CSV -> run_harness raises ValueError -> ClickException (exit 1, no traceback).
    result = runner.invoke(
        main,
        ["diagnose", "minervini-recall", "--exemplars-csv", str(tmp_path / "nope.csv"),
         "--tiingo-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code != 0
    assert "Error:" in result.output  # ClickException renders as 'Error: ...'
    assert "Traceback" not in result.output


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="powershell.exe not available")
def test_cli_stdout_is_ascii_through_powershell(tmp_path):
    # Exercise the REAL OS encoder (capsys bypasses cp1252; this is the gotcha guard).
    ex = tmp_path / "ex.csv"
    _make_exemplar_csv(ex)
    out = tmp_path / "out"
    # No Tiingo data present -> every exemplar is no_data, but the run still completes and prints ASCII.
    cmd = (
        f"{sys.executable} -m research.harness.minervini_exemplar_recall.run "
        f"--exemplars-csv {ex} --tiingo-dir {tmp_path} --output-dir {out}"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[3]),
    )
    # Must not crash with UnicodeEncodeError on cp1252 stdout.
    assert "UnicodeEncodeError" not in proc.stderr
    assert proc.returncode == 0, proc.stderr


def test_h2_all_windows_writes_separate_file_only_when_flagged(tmp_path):
    from research.harness.minervini_exemplar_recall.run import run_harness

    ex = tmp_path / "ex.csv"
    _make_exemplar_csv(ex)
    # Flag OFF -> no diagnostic file (results.csv stays production-faithful windows[-1]).
    r_off, _p, _s, _m = run_harness(exemplars_csv=ex, tiingo_dir=tmp_path, output_dir=tmp_path / "off", bootstrap_b=10)
    assert not (r_off.parent / "h2_all_windows_diagnostic.csv").exists()
    # Flag ON -> a SEPARATE non-production file is written (even if empty under no_data).
    r_on, _p2, _s2, _m2 = run_harness(exemplars_csv=ex, tiingo_dir=tmp_path, output_dir=tmp_path / "on",
                                      h2_all_windows=True, bootstrap_b=10)
    diag = r_on.parent / "h2_all_windows_diagnostic.csv"
    assert diag.exists()
    # The diagnostic carries timing_mode (covers both single_session + sweep, not just entry).
    assert "timing_mode" in diag.read_text(encoding="utf-8").splitlines()[0].split(",")


def test_manifest_has_spec_required_fields(tmp_path):
    from research.harness.minervini_exemplar_recall.run import run_harness

    ex = tmp_path / "ex.csv"
    _make_exemplar_csv(ex)
    _r, _p, _s, manifest = run_harness(exemplars_csv=ex, tiingo_dir=tmp_path, output_dir=tmp_path / "out", bootstrap_b=10)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for key in ("n_total", "n_screenable", "n_excluded", "finished_iso_utc",
                "skip_reason_counts", "per_exemplar_provenance", "config_snapshot", "l2_lock_preserved"):
        assert key in data, f"manifest missing {key}"
    # CSV with 1 curated row, 0 non-curated -> n_excluded 0.
    assert data["n_excluded"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_run_cli.py::test_value_error_becomes_click_exception -q`
Expected: FAIL — `no such command 'minervini-recall'` (the diagnose subcommand is not registered yet).

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_exemplar_recall/run.py
from __future__ import annotations

import argparse
import hashlib
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from swing.config import Config

from . import control_cohort, detector_eval, output, scorecard, stage_db, timing
from .constants import DEFAULT_CONTROL_SEED, screenable_floor
from .exceptions import TiingoArchiveMissingError
from .exemplar_reader import read_exemplars
from .ohlcv_reader import read_full
from .scorecard import ControlSummary, ExemplarSummary

_SURFACED = {"surfaced_aplus", "surfaced_watch"}
_ATTRITION = {"skip_insufficient_history", "no_data"}


def _load_full_safe(symbol: str, tiingo_dir: Path):
    # ONLY a missing archive maps to no_data. A malformed CSV / parser error must SURFACE
    # (do not swallow data-quality failures as no_data) -- Codex R1 minor.
    try:
        return read_full(symbol, tiingo_dir=tiingo_dir)
    except TiingoArchiveMissingError:
        return None


def _first_gate(mode_result) -> str | None:
    for se in mode_result.sessions:
        if se.screen.outcome == "skip_gate_rejection" and se.screen.gate_attribution:
            return se.screen.gate_attribution.first_rejecting_gate
    return None


_OUTCOME_RANK = {
    "surfaced_aplus": 4, "surfaced_watch": 3, "skip_gate_rejection": 2,
    "skip_insufficient_history": 1, "no_data": 0,
}


def _best_session(mode_result):
    """The highest-outcome (most representative) session, or None."""
    best = None
    for se in mode_result.sessions:
        if best is None or _OUTCOME_RANK.get(se.screen.outcome, 0) > _OUTCOME_RANK.get(best.screen.outcome, 0):
            best = se
    return best


def _rep_gate_passes(mode_result) -> dict | None:
    """gate_passes from the highest-outcome (most representative) screenable session."""
    se = _best_session(mode_result)
    return se.screen.gate_passes if se else None


def _rep_rs_path(mode_result) -> str:
    """rs_path of the representative (highest-outcome) session, not sessions[0] -- in a sweep
    sessions[0] is usually entry-60bd and can report P1 even when the best/firing session used
    P0 (Codex R2)."""
    se = _best_session(mode_result)
    return (se.screen.rs_path if se and se.screen.rs_path else "")


def run_harness(
    *,
    exemplars_csv: Path,
    tiingo_dir: Path,
    output_dir: Path,
    window_back: int = 60,
    window_fwd: int = 5,
    control_k: int = 5,
    bootstrap_b: int = 2000,
    h2_all_windows: bool = False,
    only: tuple[str, ...] | None = None,
) -> tuple[Path, Path, Path, Path]:
    exemplars_csv = Path(exemplars_csv)
    if not exemplars_csv.exists():
        raise ValueError(f"exemplars CSV not found: {exemplars_csv}")
    config = Config.from_defaults()
    exemplars_all = read_exemplars(exemplars_csv)
    n_curated_all = len(exemplars_all)
    raw_total = max(0, len(exemplars_csv.read_text(encoding="utf-8").splitlines()) - 1)
    n_excluded = max(0, raw_total - n_curated_all)  # curated=no rows (spec section 10.1)
    exemplars = exemplars_all
    if only:
        wanted = set(only)
        exemplars = [e for e in exemplars_all if e.exemplar_id in wanted]
    spy_full = _load_full_safe("SPY", Path(tiingo_dir))

    iso = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_dir) / f"minervini-exemplar-recall-{iso}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results_rows: list[dict] = []
    per_session_rows: list[dict] = []
    summaries: dict[str, list[ExemplarSummary]] = {"single_session": [], "window_sweep": []}
    control_summaries: dict[str, list[ControlSummary]] = {"single_session": [], "window_sweep": []}
    skip_reason_counts: Counter = Counter()  # coverage/skip-reason counters (spec 10.1, gotcha #27)
    per_exemplar_provenance: list[dict] = []
    all_windows_rows: list[dict] = []

    for idx, ex in enumerate(exemplars):
        full = _load_full_safe(ex.tiingo_symbol, Path(tiingo_dir))
        if full is None:
            # No sessions are produced for a missing archive, so the per-session skip counters
            # below never fire -> count it explicitly here (Codex R2 minor; never silent).
            skip_reason_counts["archive_missing"] += 1
            modes = {
                m: timing.ExemplarTimingResult(m, (), "skip", "no_data", False, False, (), ())
                for m in ("single_session", "window_sweep")
            }
        else:
            modes = timing.evaluate_exemplar(
                ex, exemplar_full=full, spy_full=spy_full, config=config,
                window_back=window_back, window_fwd=window_fwd,
            )
        data_source = "vicr_yfinance" if ex.tiingo_symbol == "VICR" else "tiingo"
        for mode, res in modes.items():
            faith = res.h2_faithful_fired_expected if ex.detector_class != "unmapped" else None
            isod = res.h2_isolated_fired_expected if ex.detector_class != "unmapped" else None
            fired_faithful = ";".join(sorted({c for se in res.sessions for c in se.h2_faithful.fired_classes}))
            fired_isolated = ";".join(sorted({c for se in res.sessions for c in se.h2_isolated.fired_classes}))
            anchor_limited = any(se.h2_isolated.h2_anchor_mode_limited_possible for se in res.sessions)
            rs_path = _rep_rs_path(res)  # representative (best-outcome) session, not sessions[0]
            for se in res.sessions:  # coverage/skip-reason counters across BOTH variants (never silent)
                for verdict in (se.h2_faithful, se.h2_isolated):
                    if verdict.skip_reason:
                        skip_reason_counts[verdict.skip_reason] += 1
            results_rows.append({
                "exemplar_id": ex.exemplar_id, "ticker": ex.ticker, "timing_mode": mode,
                "h1_outcome": res.best_h1_outcome, "best_bucket": res.best_bucket,
                "first_rejecting_gate": _first_gate(res) or "",
                "h2_fired_faithful": str(faith), "h2_fired_isolated": str(isod),
                "fired_classes_faithful": fired_faithful, "fired_classes_isolated": fired_isolated,
                "rs_path": rs_path,
                "data_source": data_source,
                "n_bars": str(res.sessions[-1].screen.n_sliced if res.sessions else 0),
                "screenable": str(res.best_h1_outcome not in _ATTRITION),
                "h2_anchor_mode_limited_possible": str(anchor_limited),
                "h2_anchor_mode_limited_reason": (
                    next((se.h2_isolated.h2_anchor_mode_limited_reason for se in res.sessions
                          if se.h2_isolated.h2_anchor_mode_limited_reason), "") or ""
                ),
            })
            for se in res.sessions:
                per_session_rows.append({
                    "exemplar_id": ex.exemplar_id, "ticker": ex.ticker, "timing_mode": mode,
                    "session": se.session.isoformat(), "h1_outcome": se.screen.outcome,
                    "bucket": se.screen.bucket or "",
                    "fired_faithful_expected": str(se.h2_faithful.fired_expected_class),
                    "fired_isolated_expected": str(se.h2_isolated.fired_expected_class),
                    "fired_classes": ";".join(se.h2_isolated.fired_classes),
                })
            if mode == "window_sweep":
                per_exemplar_provenance.append({
                    "exemplar_id": ex.exemplar_id, "data_source": data_source,
                    "rs_path": rs_path,  # representative session
                    "rs_paths_all": sorted({se.screen.rs_path for se in res.sessions if se.screen.rs_path}),
                })
            summaries[mode].append(ExemplarSummary(
                ex.exemplar_id, ex.ticker, ex.detector_class, res.best_h1_outcome,
                _first_gate(res), faith, isod, _rep_gate_passes(res),
            ))

        if h2_all_windows and full is not None:
            all_windows_rows.extend(
                _h2_all_windows_rows(ex, full, window_back=window_back, window_fwd=window_fwd)
            )

        # controls (only when we have the ticker's bars)
        if full is not None:
            anchors = control_cohort.sample_control_anchors(
                full, ex.entry_anchor, k=control_k, window_back=window_back, window_fwd=window_fwd,
                screenable_floor=screenable_floor(config), base_seed=DEFAULT_CONTROL_SEED, exemplar_index=idx,
            )
            for anchor in anchors:
                cmodes = control_cohort.evaluate_control(
                    ex, anchor, exemplar_full=full, spy_full=spy_full, config=config,
                    window_back=window_back, window_fwd=window_fwd,
                )
                for mode, cres in cmodes.items():
                    control_summaries[mode].append(ControlSummary(
                        ticker=ex.ticker, detector_class=ex.detector_class,
                        surfaced=cres.best_h1_outcome in _SURFACED,
                        fired_faithful=cres.h2_faithful_fired_expected,
                        fired_isolated=cres.h2_isolated_fired_expected,
                    ))

    cards = {
        m: scorecard.build_scorecard(m, summaries[m], control_summaries[m],
                                     bootstrap_b=bootstrap_b, base_seed=DEFAULT_CONTROL_SEED)
        for m in ("single_session", "window_sweep")
    }

    n_screenable = sum(1 for e in summaries["window_sweep"] if e.h1_outcome not in _ATTRITION)
    finished_iso = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    results_path = run_dir / "results.csv"
    per_session_path = run_dir / "per_session.csv"
    summary_path = run_dir / "summary.md"
    manifest_path = run_dir / "manifest.json"
    output.write_results_csv(results_rows, results_path)
    output.write_per_session_csv(per_session_rows, per_session_path)
    output.write_summary_md(_summary_lines(cards, exemplars), summary_path)
    output.write_manifest_json(
        _manifest(
            exemplars_csv=exemplars_csv, exemplars=exemplars, config=config,
            window_back=window_back, window_fwd=window_fwd, control_k=control_k,
            bootstrap_b=bootstrap_b, started_iso=iso, finished_iso=finished_iso,
            n_excluded=n_excluded, n_screenable=n_screenable, only=only,
            per_exemplar_provenance=per_exemplar_provenance,
            skip_reason_counts=dict(skip_reason_counts),
        ),
        manifest_path,
    )
    if h2_all_windows:
        output.write_h2_all_windows_csv(all_windows_rows, run_dir / "h2_all_windows_diagnostic.csv")
    return results_path, per_session_path, summary_path, manifest_path


def _summary_lines(cards, exemplars) -> list[str]:
    lines = ["# Minervini Exemplar Recall - summary", ""]
    lines.append(f"Exemplars evaluated (curated=yes): {len(exemplars)}")
    lines.append("")
    lines.append("NOTE: the negative-control cohort is a SAME-TICKER temporal-specificity contrast,")
    lines.append("NOT a population false-fire base rate (spec section 8/12.10).")
    lines.append("")
    for mode, card in cards.items():
        lines.append(f"## {mode}")
        lines.append(f"- screening recall (full set): {card.screening_recall_full:.3f}")
        lines.append(f"- screening recall (screenable): {card.screening_recall_screenable:.3f}")
        w = card.screening_wilson_screenable
        lines.append(f"- Wilson 95pct (screenable, PRIMARY): [{w.lower:.3f}, {w.upper:.3f}] n={w.n}")
        b = card.screening_bootstrap_screenable
        lines.append(f"- ticker-clustered bootstrap 95pct (EXPLORATORY): [{b.lower:.3f}, {b.upper:.3f}]")
        lines.append(f"- bucket distribution: {card.bucket_distribution}")
        lines.append(f"- first-rejecting-gate histogram: {card.gate_attribution_hist}")
        lines.append(f"- per-gate pass rate (screenable): {card.per_gate_pass_rate_screenable}")
        lines.append(f"- per-detector recall faithful: {card.detector_recall.per_class_faithful}")
        lines.append(f"- per-detector recall isolated: {card.detector_recall.per_class_isolated}")
        lines.append(f"- Stage-2 delta (isolated - faithful): {card.detector_recall.stage2_delta}")
        lines.append(f"- specificity contrast (control): {card.specificity_contrast}")
        lines.append("")
    return lines


def _h2_all_windows_rows(ex, full, *, window_back, window_fwd) -> list[dict]:
    """Diagnostic: scan ALL windows under an ISOLATED stage (past the Stage-2 gate) at EVERY
    session of BOTH timing modes (Codex R2: cover the sweep sessions that drive best-of H2 recall,
    not just the entry anchor). Each row is tagged timing_mode + session. Non-production, separate
    file only, off by default (it is the most expensive path in the harness)."""
    modes = {
        "single_session": timing.single_session(full, ex.entry_anchor),
        "window_sweep": timing.sweep_sessions(
            full, ex.entry_anchor, window_back=window_back, window_fwd=window_fwd
        ),
    }
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        conn = stage_db.build_stage_db(Path(td) / "iso.db")
        try:
            for mode, sessions in modes.items():
                for session in sessions:
                    stage_db.seed_session(
                        conn, ticker=ex.tiingo_symbol, session=session, tt_results=(), mode="isolated"
                    )
                    for row in detector_eval.evaluate_h2_all_windows(
                        exemplar=ex, session=session, exemplar_full=full, stage_conn=conn
                    ):
                        row["timing_mode"] = mode
                        rows.append(row)
        finally:
            conn.close()
    return rows


def _manifest(
    *, exemplars_csv, exemplars, config, window_back, window_fwd, control_k, bootstrap_b,
    started_iso, finished_iso, n_excluded, n_screenable, only, per_exemplar_provenance,
    skip_reason_counts,
) -> dict:
    raw = Path(exemplars_csv).read_bytes()
    return {
        "harness_version": "0.1.0",
        "exemplar_set_sha256": hashlib.sha256(raw).hexdigest(),
        "n_total": len(exemplars),
        "n_screenable": n_screenable,
        "n_excluded": n_excluded,
        "n_unmapped": sum(1 for e in exemplars if e.detector_class == "unmapped"),
        "only_filter": list(only) if only else None,
        "window_back": window_back,
        "window_fwd": window_fwd,
        "control_k": control_k,
        "control_seed": DEFAULT_CONTROL_SEED,
        "bootstrap_b": bootstrap_b,
        "started_iso_utc": started_iso,
        "finished_iso_utc": finished_iso,
        "per_exemplar_provenance": per_exemplar_provenance,
        "skip_reason_counts": skip_reason_counts,
        "config_snapshot": {
            "min_passes": config.trend_template.min_passes,
            "allowed_miss_names": list(config.trend_template.allowed_miss_names),
            "rs_rank_min_pass": config.rs.rs_rank_min_pass,
            "fallback_extreme_pct": config.rs.fallback_extreme_pct,
            "horizon_weeks": config.rs.horizon_weeks,
            "rising_ma_period_days": config.trend_template.rising_ma_period_days,
            "screenable_floor": screenable_floor(config),
        },
        "l2_lock_preserved": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="minervini-recall")
    p.add_argument("--exemplars-csv", type=Path, required=True)
    p.add_argument("--tiingo-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("exports/research"))
    p.add_argument("--window-back", type=int, default=60)
    p.add_argument("--window-fwd", type=int, default=5)
    p.add_argument("--control-k", type=int, default=5)
    p.add_argument("--bootstrap-b", type=int, default=2000)
    p.add_argument("--h2-all-windows", action="store_true")
    p.add_argument("--only", type=str, default=None)
    args = p.parse_args(argv)
    only = tuple(s.strip() for s in args.only.split(",") if s.strip()) if args.only else None
    try:
        results, per_session, summary, manifest = run_harness(
            exemplars_csv=args.exemplars_csv, tiingo_dir=args.tiingo_dir, output_dir=args.output_dir,
            window_back=args.window_back, window_fwd=args.window_fwd, control_k=args.control_k,
            bootstrap_b=args.bootstrap_b, h2_all_windows=args.h2_all_windows, only=only,
        )
    except ValueError as exc:
        p.error(str(exc))
        return 2
    print(f"results.csv:     {results}")
    print(f"per_session.csv: {per_session}")
    print(f"summary.md:      {summary}")
    print(f"manifest.json:   {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Add to `swing/cli.py` (inside the existing `diagnose_group`, mirroring `aplus-sensitivity-v2`):

```python
@diagnose_group.command("minervini-recall")
@click.option("--exemplars-csv", "exemplars_csv", type=click.Path(path_type=Path),
              default=Path("research/data/minervini-exemplars.csv"), show_default=True)
@click.option("--tiingo-dir", "tiingo_dir", type=click.Path(path_type=Path),
              default=Path("research/data/tiingo"), show_default=True)
@click.option("--output-dir", "output_dir", type=click.Path(path_type=Path),
              default=Path("exports/research"), show_default=True)
@click.option("--window-back", type=int, default=60, show_default=True)
@click.option("--window-fwd", type=int, default=5, show_default=True)
@click.option("--control-k", type=int, default=5, show_default=True)
@click.option("--bootstrap-b", type=int, default=2000, show_default=True)
@click.option("--h2-all-windows", is_flag=True, default=False,
              help="Off by default. Writes a separate non-production diagnostic CSV.")
@click.option("--only", type=str, default=None, help="Comma-separated exemplar_id filter.")
def diagnose_minervini_recall(exemplars_csv, tiingo_dir, output_dir, window_back, window_fwd,
                              control_k, bootstrap_b, h2_all_windows, only):
    """Minervini correct-entry exemplar-recall harness (H1 screen + H2 detector recall).

    No --db: H1 is pure, equity is the $7500 floor surrogate, stage is synthetic."""
    from research.harness.minervini_exemplar_recall.run import run_harness  # deferred import

    only_tuple = tuple(s.strip() for s in only.split(",") if s.strip()) if only else None
    try:
        results, per_session, summary, manifest = run_harness(
            exemplars_csv=exemplars_csv, tiingo_dir=tiingo_dir, output_dir=output_dir,
            window_back=window_back, window_fwd=window_fwd, control_k=control_k,
            bootstrap_b=bootstrap_b, h2_all_windows=h2_all_windows, only=only_tuple,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"results.csv:     {results}")
    click.echo(f"summary.md:      {summary}")
    click.echo(f"manifest.json:   {manifest}")
```

Confirm `from pathlib import Path` is already imported at the top of `swing/cli.py` (it is — used by `aplus-sensitivity-v2`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_run_cli.py::test_value_error_becomes_click_exception -q`
Expected: PASS. Then run the PowerShell stdout test: `python -m pytest tests/research/minervini_exemplar_recall/test_run_cli.py -q` (expect PASS; it completes with all-`no_data` since `tmp_path` has no Tiingo CSVs).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/run.py swing/cli.py tests/research/minervini_exemplar_recall/test_run_cli.py
git commit -m "feat(research): wire minervini-recall harness entry and single CLI registration"
git log -1 --format='%(trailers)'
```

---

## Task 13: L2 LOCK test (static grep + sys.modules import-smoke)

**Files:**
- Test: `tests/research/minervini_exemplar_recall/test_l2_lock.py`

Mirror `tests/research/test_aplus_v2_ohlcv_reader.py::test_v2_module_set_does_NOT_import_schwab_or_yfinance` (the strongest precedent — its forbidden set INCLUDES `swing.data.ohlcv_archive`, banned because it imports yfinance at module load). Two defenses: (a) a `sys.modules` sentinel that raises on any attribute access if a forbidden module is really imported; (b) a static source grep over the harness package's `*.py`. The `research/scripts/materialize_vicr_yfinance.py` one-off is OUTSIDE the harness package and is therefore NOT in the grepped/imported set.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_l2_lock.py
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import research.harness.minervini_exemplar_recall as pkg

_FORBIDDEN = (
    "yfinance",
    "schwabdev",
    "swing.integrations.schwab",
    "swing.data.ohlcv_archive",
)

# tiingo_pull / qa_compare / qa_montage are data-acq scripts that MAY import yfinance/mpl;
# the L2 LOCK governs the EVALUATOR import graph, so we test exactly the evaluator modules.
_EVALUATOR_MODULES = (
    "constants", "exceptions", "ohlcv_reader", "exemplar_reader", "rs_proxy",
    "screen_eval", "stage_db", "detector_eval", "timing", "control_cohort",
    "scorecard", "output", "run",
)


class _NoImportSentinel:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, item):
        raise AssertionError(f"L2 LOCK violated: forbidden module {self._name!r} was imported")


def test_evaluator_modules_do_not_import_forbidden(monkeypatch):
    for name in list(sys.modules):
        if name.startswith("research.harness.minervini_exemplar_recall") or name in _FORBIDDEN:
            monkeypatch.delitem(sys.modules, name, raising=False)
    for forbidden in _FORBIDDEN:
        monkeypatch.setitem(sys.modules, forbidden, _NoImportSentinel(forbidden))
    for mod in _EVALUATOR_MODULES:
        importlib.import_module(f"research.harness.minervini_exemplar_recall.{mod}")
    for forbidden in _FORBIDDEN:
        loaded = sys.modules.get(forbidden)
        assert isinstance(loaded, _NoImportSentinel), (
            f"L2 LOCK: {forbidden} was replaced by a real import"
        )


def test_evaluator_sources_contain_no_forbidden_import_lines():
    pkg_dir = Path(pkg.__file__).parent
    banned = (
        "import yfinance", "from yfinance",
        "import schwabdev", "from schwabdev",
        "from swing.integrations.schwab", "swing.integrations.schwab.",
        "from swing.data.ohlcv_archive", "swing.data.ohlcv_archive.", "import swing.data.ohlcv_archive",
    )
    for mod in _EVALUATOR_MODULES:
        src = (pkg_dir / f"{mod}.py").read_text(encoding="utf-8")
        for line in src.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            for token in banned:
                assert token not in stripped, f"{mod}.py imports forbidden: {stripped!r}"
```

- [ ] **Step 2: Run test to verify it fails (then passes)**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_l2_lock.py -q`
Expected: This test should PASS immediately if Tasks 1-12 honored the lock. To prove it DISCRIMINATES, temporarily add `import yfinance  # noqa` to `scorecard.py`, re-run, and SEE both tests fail (`L2 LOCK violated` / `imports forbidden`). Then REMOVE the line and confirm PASS. (Document this two-step in the commit body's first line only — keep it plain prose.)

- [ ] **Step 3: (implementation already exists — the lock is upheld by Tasks 1-12)**

No new harness code. If either test fails for real, the offending module must drop the forbidden import (route OHLCV through `ohlcv_reader`, never `swing.data.ohlcv_archive`).

- [ ] **Step 4: Run the full harness suite**

Run: `python -m pytest tests/research/minervini_exemplar_recall/ -q`
Expected: PASS (all harness tests green).

- [ ] **Step 5: Commit**

```bash
git add tests/research/minervini_exemplar_recall/test_l2_lock.py
git commit -m "test(research): add L2 LOCK import-smoke and source-grep for minervini-recall harness"
git log -1 --format='%(trailers)'
```

---

## Task 14: Extend `tiingo_pull.py` to always fetch SPY

**Files:**
- Modify: `research/harness/minervini_exemplar_recall/tiingo_pull.py` (inject `"SPY"` into the unique-symbol set)
- Test: `tests/research/minervini_exemplar_recall/test_tiingo_pull_spy.py`

The RS proxy P0 path needs SPY bars. SPY carries no exemplar row, so `tiingo_pull` must add it to the deduped fetch set (one deep pull). This is a data-acquisition script (not part of the L2-locked evaluator graph), so it MAY import network libs — but the change here is a 1-line set insertion, tested without network by asserting the planned symbol set.

- [ ] **Step 1: Read the current symbol-set construction**

The current code (around `tiingo_pull.py:115-117`) is:
```python
plan = [(r["exemplar_id"], r["ticker"], tiingo_symbol(r["ticker"]), r["entry_date"]) for r in rows]
uniq = sorted({sym for _, _, sym, _ in plan})
```
Refactor the symbol-set derivation into a tiny pure helper so it is unit-testable.

- [ ] **Step 2: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_tiingo_pull_spy.py
from __future__ import annotations

from research.harness.minervini_exemplar_recall.tiingo_pull import unique_symbols


def test_spy_always_included_even_when_no_exemplar_carries_it():
    rows = [
        {"exemplar_id": "a", "ticker": "CRUS", "entry_date": "2010-03-30"},
        {"exemplar_id": "b", "ticker": "EMEX", "entry_date": "2001"},  # -> ELX
    ]
    syms = unique_symbols(rows)
    # WRONG-PATH (no SPY injection): {'CRUS', 'ELX'}.  RIGHT-PATH: SPY present.
    assert "SPY" in syms
    assert "CRUS" in syms and "ELX" in syms
    assert syms == sorted(syms)  # stable deterministic ordering
```

- [ ] **Step 3: Write minimal implementation**

Add a helper and use it in the fetch path:
```python
def unique_symbols(rows) -> list[str]:
    """Deduped, sorted Tiingo symbol set for the fetch loop. ALWAYS includes SPY
    (the fallback_spy RS benchmark) even though no exemplar row carries it."""
    syms = {tiingo_symbol(r["ticker"]) for r in rows}
    syms.add("SPY")
    return sorted(syms)
```
Replace the inline `uniq = sorted({...})` with `uniq = unique_symbols(rows)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_tiingo_pull_spy.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_exemplar_recall/tiingo_pull.py tests/research/minervini_exemplar_recall/test_tiingo_pull_spy.py
git commit -m "feat(research): always include SPY in the tiingo_pull symbol set for the RS proxy"
git log -1 --format='%(trailers)'
```

---

## Task 15: VICR yfinance materializer (out-of-harness one-off)

**Files:**
- Create: `research/scripts/materialize_vicr_yfinance.py`
- Test: `tests/research/minervini_exemplar_recall/test_materialize_vicr.py`

VICR's Feb-1991 entry predates the shallow 1991-11 Tiingo pull. This one-off imports yfinance, pulls VICR `>= 1990`, and writes `research/data/tiingo/VICR.csv` in TIINGO COLUMN FORMAT (so `ohlcv_reader.read_full` consumes it identically). **No `#`-comment provenance line in the CSV** (Codex R1.M8: Tiingo readers do `read_csv(parse_dates=["date"])` and expect a clean header) — provenance goes to a sibling `VICR.provenance.txt` + the run manifest. This file lives under `research/scripts/`, is NEVER imported by the harness, and is invoked only as a standalone process.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_exemplar_recall/test_materialize_vicr.py
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd


def _flat_frame():
    idx = pd.bdate_range("1990-01-02", periods=5)
    idx.name = "Date"  # mirror real yfinance: the index is named 'Date'.
    return pd.DataFrame(
        {"Open": [1.0, 2, 3, 4, 5], "High": [1.0, 2, 3, 4, 5], "Low": [1.0, 2, 3, 4, 5],
         "Close": [1.0, 2, 3, 4, 5], "Volume": [10, 20, 30, 40, 50]},
        index=idx,
    )


def _multiindex_frame():
    # Recent yfinance returns MultiIndex (Price x Ticker) even for one ticker.
    frame = _flat_frame()
    frame.columns = pd.MultiIndex.from_product([list(frame.columns), ["VICR"]])
    return frame


def _install_fake_yfinance(monkeypatch, frame):
    fake = types.ModuleType("yfinance")
    fake.download = lambda *a, **k: frame
    monkeypatch.setitem(sys.modules, "yfinance", fake)


def _materialize_with(monkeypatch, frame, csv_path):
    _install_fake_yfinance(monkeypatch, frame)
    import importlib
    mod = importlib.import_module("research.scripts.materialize_vicr_yfinance")
    importlib.reload(mod)
    mod.materialize(out_csv=csv_path)


def test_writes_tiingo_columns_no_comment_header(tmp_path, monkeypatch):
    csv_path = tmp_path / "VICR.csv"
    _materialize_with(monkeypatch, _flat_frame(), csv_path)

    text = csv_path.read_text(encoding="utf-8")
    # No '#'-comment line (Codex R1.M8): a clean header row Tiingo readers can parse.
    assert not text.lstrip().startswith("#")
    df = pd.read_csv(csv_path, parse_dates=["date"])
    for col in ("date", "adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume"):
        assert col in df.columns
    # provenance is a SIBLING sidecar, not inside the CSV.
    assert (csv_path.parent / "VICR.provenance.txt").exists()


def test_handles_multiindex_columns(tmp_path, monkeypatch):
    # WRONG-PATH (no flatten): KeyError 'close' on MultiIndex columns.
    # RIGHT-PATH (flatten to level 0): adj* columns written.
    csv_path = tmp_path / "VICR.csv"
    _materialize_with(monkeypatch, _multiindex_frame(), csv_path)
    df = pd.read_csv(csv_path, parse_dates=["date"])
    assert "adjClose" in df.columns and len(df) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_materialize_vicr.py -q`
Expected: FAIL — `ModuleNotFoundError: research.scripts.materialize_vicr_yfinance`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/scripts/materialize_vicr_yfinance.py
"""One-off: materialize VICR daily bars from yfinance into Tiingo CSV format.

NOT part of the minervini_exemplar_recall harness import graph (L2 LOCK). Run as a
standalone process:  python -m research.scripts.materialize_vicr_yfinance
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_DEFAULT_OUT = Path("research/data/tiingo/VICR.csv")


def materialize(*, out_csv: Path = _DEFAULT_OUT, start: str = "1990-01-01") -> Path:
    import yfinance  # local import: keeps yfinance OUT of any module the harness imports

    raw = yfinance.download("VICR", start=start, auto_adjust=True, progress=False)
    if raw is None or len(raw) == 0:
        raise RuntimeError("yfinance returned no VICR bars; refusing to write an empty archive")

    # yfinance can return MultiIndex columns (Price x Ticker) even for a single ticker (CLAUDE.md
    # gotcha) -> flatten to the OHLCV level first.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    # yfinance auto_adjust=True gives split/dividend-adjusted OHLCV. Emit BOTH raw-named and
    # adj*-named columns so the Tiingo reader (which consumes adj*) works unchanged.
    df = raw.reset_index()
    # The first column after reset_index is the datetime index (named 'Date', or 'index' if unnamed)
    # -> force it to 'date' positionally so we never KeyError on the index label.
    df = df.rename(columns={df.columns[0]: "date"})
    df.columns = ["date" if c == "date" else str(c).lower() for c in df.columns]
    out = pd.DataFrame({
        "date": pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"),
        "close": df["close"], "high": df["high"], "low": df["low"], "open": df["open"], "volume": df["volume"],
        "adjClose": df["close"], "adjHigh": df["high"], "adjLow": df["low"],
        "adjOpen": df["open"], "adjVolume": df["volume"],
    })
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_csv.write_text(out.to_csv(index=False, lineterminator="\n"), encoding="utf-8")

    provenance = (
        f"VICR.csv materialized from yfinance (auto_adjust=True) start={start}\n"
        f"generated_utc={datetime.now(timezone.utc).isoformat()}\n"
        f"rows={len(out)} first={out['date'].iloc[0]} last={out['date'].iloc[-1]}\n"
        "Source: Yahoo Finance via yfinance. Replaces the shallow 1991-11 Tiingo pull.\n"
    )
    (out_csv.parent / "VICR.provenance.txt").write_text(provenance, encoding="utf-8")
    return out_csv


if __name__ == "__main__":
    path = materialize()
    print(f"wrote {path}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_materialize_vicr.py -q`
Expected: PASS. Also confirm the L2 test still passes (the materializer is excluded from `_EVALUATOR_MODULES`).

- [ ] **Step 5: Commit**

```bash
git add research/scripts/materialize_vicr_yfinance.py tests/research/minervini_exemplar_recall/test_materialize_vicr.py
git commit -m "feat(research): add out-of-harness VICR yfinance materializer in Tiingo format"
git log -1 --format='%(trailers)'
```

---

## Task 16: `.gitignore` allowlist + slow end-to-end integration test

**Files:**
- Modify: `.gitignore` (allowlist the harness's small output artifacts)
- Test: `tests/research/minervini_exemplar_recall/test_integration.py` (slow)

`exports/*` is gitignored with per-harness negation allowlists. Add a block for the new harness so its small `summary.md` / `manifest.json` (and the small `results.csv` / `per_session.csv` — ~27 rows x 2 modes) are committable. The slow integration test exercises the REAL detectors end-to-end on a planted synthetic Tiingo archive (no network) and asserts the quartet is written + the manifest carries `l2_lock_preserved`.

- [ ] **Step 1: Add the `.gitignore` allowlist block**

Append near the other `exports/research/*` negation rules:
```gitignore
# Minervini exemplar-recall harness outputs: keep the small summary/manifest/results.
!exports/research/minervini-exemplar-recall-*/
!exports/research/minervini-exemplar-recall-*/summary.md
!exports/research/minervini-exemplar-recall-*/manifest.json
!exports/research/minervini-exemplar-recall-*/results.csv
!exports/research/minervini-exemplar-recall-*/per_session.csv
```
Verify the allowlist works:
```bash
git check-ignore -v "exports/research/minervini-exemplar-recall-20260608T000000Z/summary.md"
# Expected: NO output (exit 1) -> the path is NOT ignored (allowlisted).
git check-ignore -v "exports/research/minervini-exemplar-recall-20260608T000000Z/h2_all_windows_diagnostic.csv"
# Expected: matched by exports/* (still ignored) -> the large/diagnostic file stays untracked.
```

- [ ] **Step 2: Write the failing (slow) integration test**

```python
# tests/research/minervini_exemplar_recall/test_integration.py
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.slow


def _plant_tiingo(tiingo_dir: Path, symbol: str, n=400, start="2008-01-02", seed=0.0):
    idx = pd.bdate_range(start=start, periods=n)
    closes = []
    price = 20.0 + seed
    for i in range(n):
        price *= 1.005 if (i // 9) % 2 == 0 else 0.997
        closes.append(round(price, 4))
    lines = ["date,close,high,low,open,volume,adjClose,adjHigh,adjLow,adjOpen,adjVolume"]
    for d, c in zip(idx, closes):
        lines.append(f"{d.date()},{c},{c*1.01:.4f},{c*0.99:.4f},{c:.4f},1000000,"
                     f"{c},{c*1.01:.4f},{c*0.99:.4f},{c:.4f},1000000")
    (tiingo_dir / f"{symbol}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_end_to_end_real_detectors_writes_quartet(tmp_path):
    from research.harness.minervini_exemplar_recall.run import run_harness

    tiingo = tmp_path / "tiingo"
    tiingo.mkdir()
    _plant_tiingo(tiingo, "AAA")
    _plant_tiingo(tiingo, "SPY", seed=5.0)

    ex = tmp_path / "ex.csv"
    header = ("exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
              "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes")
    ex.write_text(header + "\nid-a,AAA,VCP,vcp,2009-06-01,,,,,day,S,P,claude,yes,n\n", encoding="utf-8")

    results, per_session, summary, manifest = run_harness(
        exemplars_csv=ex, tiingo_dir=tiingo, output_dir=tmp_path / "out",
        bootstrap_b=50,  # keep the slow test fast
        h2_all_windows=True,  # also exercise the diagnostic over real windows
    )
    assert results.exists() and per_session.exists() and summary.exists() and manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True
    assert data["n_total"] == 1
    # The run drove the REAL 5 detectors against a synthetic stage DB (production-path coverage,
    # not a stubbed registry) -> the results.csv has both timing-mode rows.
    body = results.read_text(encoding="utf-8")
    assert "single_session" in body and "window_sweep" in body
    # The all-windows diagnostic covers BOTH timing modes (Codex R2/R3 -> not just the entry anchor).
    diag = (results.parent / "h2_all_windows_diagnostic.csv").read_text(encoding="utf-8")
    assert "single_session" in diag and "window_sweep" in diag
```

- [ ] **Step 3: Run the slow test**

Run: `python -m pytest tests/research/minervini_exemplar_recall/test_integration.py -q -m slow`
Expected: PASS. (No network — the Tiingo archive is planted on disk; the real detectors run against the synthetic stage DB.)

- [ ] **Step 4: Run the FULL fast suite on the harness + confirm no regressions**

Run: `python -m pytest tests/research/minervini_exemplar_recall/ -q` then `python -m pytest -m "not slow" -q` (full repo fast suite).
Expected: all green; the repo fast-suite count increases by the harness test count with zero pre-existing failures.

- [ ] **Step 5: Commit**

```bash
git add .gitignore tests/research/minervini_exemplar_recall/test_integration.py
git commit -m "test(research): add slow end-to-end integration and gitignore allowlist for outputs"
git log -1 --format='%(trailers)'
```

---

## Task 17: Method-record stub

**Files:**
- Create: `research/method-records/minervini-exemplar-recall.md`

Per `research/method-records/_template.md` (V2.1 §IV.B minimum viable field list) + the harness expansions from `research/method-records/pattern-cohort-detection.md` (Promotion criteria / Limitations / Notes). This is a documentation task — verification is a structural check, not a pytest run.

- [ ] **Step 1: Write the method record**

Create `research/method-records/minervini-exemplar-recall.md` with this exact skeleton (fill the prose; keep ASCII):

```markdown
---
key: minervini-exemplar-recall
name: Minervini correct-entry exemplar recall
layer: monitoring
status: research
baseline_or_predecessor: none
version: 0.1.0
last_updated: 2026-06-08
---

# Minervini correct-entry exemplar recall

## Definition
Point-in-time true-positive recall test (entry side): for each curated Minervini correct-entry
exemplar, does our screen surface it (H1: bucket_for -> aplus/watch) and would any of the 5 V1
detectors fire (H2: geometric_score > 0, class-matched), evaluated strictly <= the locked
entry-crossing session. A miss localizes the silently-rejecting gate. internal.

## Inputs
- Curated exemplar CSV (research/data/minervini-exemplars.csv, curated=yes; 27 of 34).
- Tiingo adjusted daily OHLCV (research/data/tiingo/<symbol>.csv), backward-looking <= asof slice.
- SPY (fallback_spy RS benchmark); VICR via the out-of-harness yfinance materializer.

## Parameters
- window_back=60, window_fwd=5 (positional sweep); control_k=5; bootstrap_b=2000.
- SCREENABLE_FLOOR = 200 + rising_ma_period_days (=221). H2_MIN_BARS=60. CONTROL_GAP_BARS=120.

## Outputs
- results.csv / per_session.csv / summary.md / manifest.json under
  exports/research/minervini-exemplar-recall-<ISO>/. Per-mode recall (full + screenable),
  per-gate first-rejection histogram, per-detector recall (faithful + isolated) + Stage-2 delta,
  Wilson intervals (primary) + ticker-clustered bootstrap (exploratory), same-ticker specificity.

## Operator explainability
- One-sentence rationale: confirms our gates would have caught known-good Minervini setups, and
  localizes which gate silently rejects the misses.
- One-paragraph explanation: [fill]
- FAQ: [fill: why same-ticker control is not a base rate; why faithful needs 8/8 TT; why P1 NA]

## Promotion criteria
### Research -> shadow
1. [fill]
### Shadow -> production
1. [fill]
### Anti-promotion guards
1. L2 LOCK upheld (manifest l2_lock_preserved == true; no yfinance/schwabdev/schwab/ohlcv_archive
   in the evaluator import graph).
2. ZERO production swing/ writes beyond the single CLI registration.
3. Any deployable finding (gate re-tune / young-name screen) routes through the V2.1 SVII.F
   source-of-truth correction protocol, never a direct patch.

## Limitations
L1..Ln per spec section 12 (archive temporal mutation #24/#26; SPY-1993 inception; faithful 8/8 TT
quirk; irreducible insufficient-history young names; V1 zigzag-only anchor; small n descriptive).

## Validation notes
[grows as status advances]

## Changelog
- 2026-06-08 - v0.1.0 - initial record.
```

- [ ] **Step 2: Verify structure**

Run: `python -c "import pathlib,sys; t=pathlib.Path('research/method-records/minervini-exemplar-recall.md').read_text(encoding='utf-8'); req=['## Definition','## Inputs','## Parameters','## Outputs','## Operator explainability','## Changelog','key: minervini-exemplar-recall']; missing=[s for s in req if s not in t]; sys.exit('MISSING: '+str(missing) if missing else 0)"`
Expected: exit 0 (no missing sections). Confirm cp1252: `python -c "print(open('research/method-records/minervini-exemplar-recall.md',encoding='utf-8').read().encode('cp1252') and 'ascii-ok')"`.

- [ ] **Step 3: Commit**

```bash
git add research/method-records/minervini-exemplar-recall.md
git commit -m "docs(research): add minervini-exemplar-recall method-record stub"
git log -1 --format='%(trailers)'
```

---

## Task 18: Study-design document

**Files:**
- Create: `research/studies/2026-06-08-minervini-exemplar-recall.md`

Run-writeup (B) shape of `research/studies/2026-05-24-pattern-cohort-detection.md`: Question / Null hypothesis / Baseline / Methodology fillable now; Results / Interpretation / Conclusion as placeholders to be populated at the operator smoke gate. Cross-link the method record via a `**Method record:**` line.

- [ ] **Step 1: Write the study doc**

Create `research/studies/2026-06-08-minervini-exemplar-recall.md` (ASCII; placeholders for run-time results):

```markdown
# Minervini correct-entry exemplar recall (2026-06-08)

**Method record:** ../method-records/minervini-exemplar-recall.md
**Status:** designed; awaiting the operator smoke run.
**Target duration:** per V2.1 SIII.7 time budget.

## Question
Given Minervini's documented correct-entry exemplars, would our screen have surfaced each
(H1) and would any of the 5 V1 detectors have fired (H2), evaluated strictly point-in-time at/
around the locked entry-crossing session? A pass = our gates would have caught a known-good
setup; a miss localizes the silently-rejecting gate.

## Null hypothesis
H0: detector firing at the documented pivot is no more frequent than at random same-ticker
non-entry dates (the temporal-specificity contrast); and the screen surfaces no more than the
screenable-subset base would by construction. (Descriptive; no inferential test claimed.)

## Baseline
Descriptive recall + per-gate first-rejection attribution + same-ticker negative-control cohort
(temporal-specificity contrast, NOT a population base rate).

## Methodology
- Harness: research/harness/minervini_exemplar_recall/ (Approach A thin modules over pure leaves).
- CLI: swing diagnose minervini-recall (no --db; equity = 7500 floor; synthetic stage DB).
- H1: evaluate_one -> bucket; taxonomy {no_data, skip_insufficient_history, surfaced_aplus,
  surfaced_watch, skip_gate_rejection}; load-bearing-gate attribution replays bucket_for order.
- H2: generate_candidate_windows zigzag_pivot -> windows[-1] -> 5 detectors geometric-only,
  both stage variants (production-faithful 8/8-TT vs stage-isolated forced); Stage-2 delta.
- Timing: single-session + [entry-60bd, entry+5bd] positional sweep best-of.
- Uncertainty: Wilson (primary, screenable subset) + ticker-clustered bootstrap (exploratory).

## Results
[PLACEHOLDER - populate from exports/research/minervini-exemplar-recall-<ISO>/summary.md at the
operator smoke gate. Include: bucket distribution, screening recall (full + screenable), per-gate
histogram, per-detector recall (faithful + isolated) + Stage-2 delta, specificity contrast.]

## Interpretation
[PLACEHOLDER - a-priori scenarios S1..Sn vs the actual result; implications for cfg-policy
direction; which gate(s) localize the misses.]

## Limitations
L1..Ln per the method record / spec section 12 (archive temporal mutation; SPY-1993; faithful
8/8 TT quirk; irreducible young-name insufficient-history; V1 zigzag-only anchor confound for
cup/HTF; small n -> descriptive only).

## Conclusion
[PLACEHOLDER - verdict + forward directions + V2.1 SIV.D promotion-gate checklist SATISFIED/PENDING.]

## Amendments
- 2026-06-08: shipped with placeholder Results/Interpretation/Conclusion pending the operator run.
```

- [ ] **Step 2: Verify structure + ASCII**

Run: `python -c "import pathlib,sys; t=pathlib.Path('research/studies/2026-06-08-minervini-exemplar-recall.md').read_text(encoding='utf-8'); req=['## Question','## Null hypothesis','## Methodology','## Results','## Limitations','## Conclusion','Method record:']; missing=[s for s in req if s not in t]; t.encode('cp1252'); sys.exit('MISSING: '+str(missing) if missing else 0)"`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add research/studies/2026-06-08-minervini-exemplar-recall.md
git commit -m "docs(research): add minervini-exemplar-recall study-design document"
git log -1 --format='%(trailers)'
```

---

## Final verification (after all tasks)

- [ ] Run the full harness suite + a slow pass:
  `python -m pytest tests/research/minervini_exemplar_recall/ -q` (all green)
  `python -m pytest tests/research/minervini_exemplar_recall/ -q -m slow` (integration green)
- [ ] Run the repo fast suite on the merged head and READ the count:
  `python -m pytest -m "not slow" -q` (no new failures vs the ~7265 baseline; never carry a branch count forward as the main result).
- [ ] `ruff check research/harness/minervini_exemplar_recall/ research/scripts/materialize_vicr_yfinance.py swing/cli.py` (clean).
- [ ] Confirm the ONLY `swing/` change is the CLI registration: `git diff --stat <base>..HEAD -- swing/` shows only `swing/cli.py`.
- [ ] Confirm ZERO `Co-Authored-By` across the arc: `git log <base>..HEAD --format='%(trailers)'` prints nothing for every commit.
- [ ] Operator smoke run (separate, post-merge): materialize VICR (`python -m research.scripts.materialize_vicr_yfinance`), pull Tiingo + SPY, then `swing diagnose minervini-recall` -> populate the study doc's Results/Interpretation/Conclusion.

---

## Appendix A: Spec-coverage map (self-review)

| Spec section | Covered by |
|---|---|
| 3.1 module layout | Tasks 1-12 (one module per table row) |
| 4.1 Tiingo reader | Task 2 |
| 4.2 SPY + VICR | Tasks 14 (SPY) + 15 (VICR) |
| 4.3 exemplar reader | Task 3 |
| 5 H1 taxonomy + gate attribution | Task 5 |
| 5.1 RS proxy P0/P1 + invariant | Task 4 |
| 6 / 6.1 / 6.2 H2 + stage DB + detector loop | Tasks 6 (stage_db) + 7 (detector_eval) |
| 7 timing modes | Task 8 |
| 8 negative control | Task 9 |
| 9 scorecard (Wilson + bootstrap + strata + specificity) | Tasks 10 (primitives) + 11 (aggregate) |
| 10.1 outputs | Task 11 |
| 10.2 CLI (`minervini-recall`, no --db, --h2-all-windows) | Task 12 |
| 11 testing strategy (incl. L2 test) | Tasks 2-16 (per-module) + 13 (L2) |
| 12 limitations | Tasks 17 (method record) + 18 (study) |
| 13 deliverables (method record, study, harness, CLI, materializer) | Tasks 1-18 |
| 14 resolved questions (all 9) | Honored, not re-litigated |

## Appendix B: Type-consistency ledger (self-review)

- `ExemplarRow` (Task 3) — 11 fields; consumed unchanged by Tasks 7/8/9/12.
- `ScreenResult` (Task 5) — `.outcome/.bucket/.n_sliced/.rs_path/.tt_criteria/.gate_attribution/.gate_passes` (`gate_passes` defaults `None`, set only for screenable outcomes via `compute_gate_passes`); `tt_criteria` is ALWAYS an 8-tuple except `no_data` (8 NA rows synthesized by `_na_tt_criteria` on the below-floor exception), seeded by `stage_db.seed_session(mode="faithful")` (Task 6) via `timing._eval_one_session` (Task 8). `gate_passes` flows to `ExemplarSummary.gate_passes` (via `run._rep_gate_passes`) -> `Scorecard.per_gate_pass_rate_screenable` (Task 11, which RAISES if a screenable row's `gate_passes` is missing).
- `DetectorVerdict` (Task 7) — `.skip_reason/.fired_classes/.fired_any_class/.fired_expected_class/.geometric_by_class/.h2_anchor_mode_limited_possible/.h2_anchor_mode_limited_reason`; aggregated by `timing._aggregate` (Task 8); `_skip_verdict` reused by `timing` for the faithful no-TT path.
- `ExemplarTimingResult` (Task 8) — `.best_bucket/.best_h1_outcome/.h2_faithful_fired_expected/.h2_isolated_fired_expected/.sessions`; consumed by `run.py` (Task 12) to build `ExemplarSummary`/`ControlSummary` (Task 11) -> `build_scorecard`. `run._best_session` (highest `_OUTCOME_RANK` session) backs both `_rep_gate_passes` and `_rep_rs_path`; empty `.sessions` (no_data) -> both return `None`/`""` without error.
- `ExemplarSummary` (Task 11) — gains `.gate_passes` (8th field, default `None`); the test `_ex` helper auto-fills an all-pass dict for screenable outcomes. `manifest.per_exemplar_provenance` rows carry `exemplar_id/data_source/rs_path/rs_paths_all`; `manifest.skip_reason_counts` includes `archive_missing` for absent archives.
- `WilsonInterval`/`BootstrapInterval` (Task 10) carried inside `Scorecard` (Task 11), alongside `per_gate_pass_rate_screenable`.
- `H2_ALL_WINDOWS_HEADER` (Task 11) — `exemplar_id/ticker/timing_mode/session/window_index/anchor_date/fired_classes`; `run._h2_all_windows_rows` (Task 12) stamps `timing_mode` on every row of both modes so the `DictWriter` never KeyErrors.
- Registry monkeypatch point: `detector_eval._REGISTRY` (Task 7), referenced by `_resolve_registry()`; `select_window` name is stable across Tasks 7-8-13.

