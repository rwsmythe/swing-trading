# Minervini primary-base (young-name) screen recall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research-branch recall/precision harness that tests whether a point-in-time Minervini Ch.11 *primary-base* screen surfaces the documented young-name primary-base emergences (AMZN-1997, BODY, DKS; YHOO positive control; JNPR history-excluded) while staying selective against random young-window same-ticker controls.

**Architecture:** Approach A -- a new sibling harness package `research/harness/minervini_primary_base_recall/` over the FROZEN `minervini_exemplar_recall` leaves (`ohlcv_reader`, `exemplar_reader`, `scorecard`, `ControlAnchor`) + `swing.patterns.foundation.{extract_zigzag_swings, Swing}`. Pure-on-bars (no production DB, no equity, no stage). L2 LOCK held: the evaluator import graph imports none of yfinance / schwabdev / `swing.integrations.schwab` / `swing.data.ohlcv_archive`. The only `swing/` change is exactly ONE CLI registration (`swing diagnose primary-base-recall`).

**Tech Stack:** Python 3.14, pandas, numpy, click (CLI), pytest (TDD, `-m "not slow"`), ruff. Source-of-truth spec: [`docs/superpowers/specs/2026-06-09-primary-base-recall-design.md`](../specs/2026-06-09-primary-base-recall-design.md) (commit `92230055`).

---

## Binding disciplines (apply to EVERY task)

- **Research carve-out.** All new code lives under `research/harness/minervini_primary_base_recall/` and `tests/research/minervini_primary_base_recall/`. **EXACTLY ONE** `swing/` edit: the CLI registration in `swing/cli.py` (Task 12). No other `swing/` change. **No `--db` flag** (the screen is pure on bars).
- **Reuse frozen leaves only.** Import `read_full`, `slice_to` from `minervini_exemplar_recall.ohlcv_reader`; `read_exemplars`, `ExemplarRow` from `minervini_exemplar_recall.exemplar_reader`; `ControlAnchor` from `minervini_exemplar_recall.control_cohort`; `wilson_interval`, `ticker_clustered_bootstrap`, `WilsonInterval`, `BootstrapInterval` from `minervini_exemplar_recall.scorecard`; `CONTROL_GAP_BARS`, `DEFAULT_CONTROL_SEED` from `minervini_exemplar_recall.constants`; `extract_zigzag_swings`, `Swing` from `swing.patterns.foundation`. **Do NOT reuse `sample_control_anchors`** -- write the own pre-filtered young-window sampler (Task 6). **Do NOT import `tiingo_symbol`** -- `ExemplarRow.tiingo_symbol` is already populated by `read_exemplars`, so use `row.tiingo_symbol` (avoids an extra frozen-leaf dependency; Codex WP-R1 M5).
- **TDD per task.** Write the failing test -> run it, see it FAIL for the stated reason -> minimal implementation -> run it, see PASS -> commit. Every discriminating test carries an explicit `WRONG-PATH` value (what a plausible-but-wrong implementation returns) and a `RIGHT-PATH` value (what the spec-correct code returns), so the test actually distinguishes the two.
- **ASCII-only** in every output path and source string (spec section 8). The `_assert_ascii` guard enforces `text.encode("ascii")` -- STRICTER than cp1252 (cp1252 would silently allow em dashes / curly quotes / accented chars). ASCII is a subset of cp1252, so an ASCII-clean file is also safe on Windows cp1252 stdout.
- **Commits:** conventional (`feat(research):`, `test(research):`); NO `Co-Authored-By` footer; NO `--no-verify`; keep the final `-m` paragraph PLAIN PROSE (no `Word:` leading line -> git parses it as a trailer). After EACH commit run `git log -1 --format='%(trailers)'` and confirm it prints an EMPTY line.
- **Fixtures from real reader output.** Synthetic OHLCV must match `read_full`'s shape: a `pd.DataFrame` with capitalized columns `["Open","High","Low","Close","Volume"]`, a tz-naive ascending `DatetimeIndex`. `extract_zigzag_swings` REQUIRES a monotonic-increasing index and NaN-free `Close` (it raises otherwise) -- build clean fixtures.
- **Codex transport (orchestrator, post-plan):** WSL CLI fallback `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex ...'`; liveness `codex --version` -> `codex-cli 0.135.0`. Persist every Codex round's full RESPONSE (incl. the final `NO_NEW_CRITICAL_MAJOR` line) to the gitignored `.copowers-findings.md`.

---

## File Structure

New package `research/harness/minervini_primary_base_recall/`:

| File | Responsibility |
|---|---|
| `__init__.py` | Package marker (empty). |
| `constants.py` | Documented module constants citing TWoSMW Ch.11: `MIN_HISTORY_BARS=40`, `MIN_BASE_BARS=15`, `ZIGZAG_THRESHOLD_PCT=3.0`, `DEPTH_LADDER` (graduated caps), `MAX_CONTROL_AGE_BARS=504`, `YOUNG_NAME_CEILING_BARS=221`, `CONTROL_K=5`, `WINDOW_BACK=60`, `WINDOW_FWD=5`; re-exports `CONTROL_GAP_BARS`, `DEFAULT_CONTROL_SEED` from the frozen constants. `depth_cap(duration_bars)` helper. |
| `exceptions.py` | `PrimaryBaseRecallError` base + `UnknownExemplarIdError`. |
| `primary_base_screen.py` | `PrimaryBaseVerdict` + `screen_at(bars, asof_date)` -- the Ch.11 criteria 1-6 over `extract_zigzag_swings`, with the calendar->bar mapping. |
| `cohort.py` | The curated documented-primary-base `exemplar_id` list (+ per-id role + book citation); resolves rows via `exemplar_reader`; rejects unknown ids. |
| `timing.py` | Single-session (day/exact-precision only) + window-sweep best-of over `screen_at`; day/exact uses `[entry-60bd, entry+5bd]`; month uses the full documented calendar month + slack. |
| `precision_control.py` | OWN young-window control sampler (pre-filters to `[MIN_HISTORY_BARS-1, MAX_CONTROL_AGE_BARS-1]` BEFORE sampling) + runs `screen_at` at control anchors (single-session primary estimand + window best-of). |
| `scorecard.py` | Recall (raw fractions first) + precision + Wilson + ticker-clustered bootstrap + per-criterion first-rejection histogram, both timing modes; reuses frozen `wilson_interval` / `ticker_clustered_bootstrap`. |
| `output.py` | `results.csv` / `per_session.csv` / `summary.md` / `manifest.json` writers (ASCII guard). |
| `run.py` | `run_harness(...)` orchestrator + `argparse` `main`. |

New tests `tests/research/minervini_primary_base_recall/` (one file per module) + `test_l2_lock.py`.

Touched `swing/` (ONE file): `swing/cli.py` -- one new `diagnose` subcommand.

Touched repo metadata: `.gitignore` (allowlist the new outputs), `research/method-records/minervini-primary-base-recall.md` (new), `research/studies/2026-06-09-minervini-primary-base-recall.md` (new).

---

## Pinned frozen-leaf signatures (verified on disk -- do NOT re-discover)

```python
# minervini_exemplar_recall.ohlcv_reader  (use ONLY read_full + slice_to; NOT tiingo_symbol -- WP-R1 M5)
def read_full(symbol: str, *, tiingo_dir: Path) -> pd.DataFrame   # caps OHLCV, tz-naive ascending index
def slice_to(bars: pd.DataFrame, asof_date: date) -> pd.DataFrame  # bars.index.date <= asof_date

# minervini_exemplar_recall.exemplar_reader
@dataclass(frozen=True)
class ExemplarRow:
    exemplar_id: str; ticker: str; tiingo_symbol: str; setup_label: str; detector_class: str
    entry_anchor: date; date_precision: str; buy_point_price: float | None
    source: str; page: str; notes: str
def read_exemplars(csv_path: Path) -> list[ExemplarRow]   # ONLY curated == "yes" rows

# minervini_exemplar_recall.control_cohort
@dataclass(frozen=True)
class ControlAnchor:
    session: date; session_pos: int

# minervini_exemplar_recall.scorecard
@dataclass(frozen=True)
class WilsonInterval: lower: float; upper: float; p_hat: float; n: int
@dataclass(frozen=True)
class BootstrapInterval: lower: float; upper: float; b: int
def wilson_interval(successes: int, n: int, z: float = 1.96) -> WilsonInterval
def ticker_clustered_bootstrap(rows: Sequence[tuple], value_fn, *, b: int, base_seed: int) -> BootstrapInterval
    # rows are tuples; row[0] MUST be the ticker cluster key

# minervini_exemplar_recall.constants
CONTROL_GAP_BARS = 120
DEFAULT_CONTROL_SEED = 20260608

# swing.patterns.foundation
@dataclass(frozen=True)
class Swing:
    start_date: date; end_date: date; start_price: float; end_price: float
    direction: Literal["up", "down"]; depth_pct: float; duration_days: int   # duration_days is CALENDAR
def extract_zigzag_swings(bars, initial_threshold_pct: float, monotonic_narrow: bool = False) -> list[Swing]
    # operates on Close; requires monotonic-increasing index + NaN-free Close (else raises);
    # returns CLOSED swings only (the developing final leg is NOT emitted).
```

**Cohort rows in `research/data/minervini-exemplars.csv` (all `curated=yes`, verified):**

| exemplar_id | ticker | entry_date | date_precision | role | bars-thru-anchor |
|---|---|---|---|---|---|
| `twosmw-fig11-1-amzn` | AMZN | `1997-09` | month | sub_floor | 75 |
| `ttlc-fig10-1-body` | BODY | `2011-01-05` | day | sub_floor | 57 |
| `twosmw-fig11-6-dks` | DKS | `2003-04` | month | sub_floor | 115 |
| `twosmw-fig11-7-jnpr` | JNPR | `1999-07-30` | day | sub_floor (history-excluded at runtime, 25 < 40) | 25 |
| `twosmw-fig11-3-yhoo` | YHOO | `1997-06-20` | day | positive_control | 302 |

`_parse_entry_anchor` maps a `YYYY-MM` (month-precision) entry to `date(Y, M, 1)` (the 1st). Note: AMZN's CSV row maps to `twosmw-fig11-1-amzn` (the 1997 primary base) -- NOT `ttlc-fig7-3-amzn` (the 2002 cup). MELI is deliberately NOT in the cohort (it is a young-VCP, R1.M4).

---

## The screen algorithm (reference -- Tasks 2-3 implement this exactly)

`screen_at(bars, asof_date)` slices `bars` to `<= asof_date` (via `slice_to`), then evaluates Ch.11 criteria. "Fired" = a buyable primary-base emergence with ALL six criteria holding. `first_rejecting_criterion` is reported in this fixed order:

1. **History** -- `len(sliced) >= MIN_HISTORY_BARS` (=40). Below -> `history`.
2. **Base identification** -- `swings = extract_zigzag_swings(sliced, 3.0)`. Build `pos_by_date = {ts.date(): i for i, ts in enumerate(sliced.index)}` (the **calendar->bar mapping**). A *swing-high pivot with a down-swing after it* is an up-swing immediately followed (in the alternating closed-swing list) by a down-swing. `base_high` = the **highest** such up-swing's `end_price`; `base_start_pos` = `pos_by_date[that up-swing's end_date]`. `base_low` = the lowest `Close` in `sliced.iloc[base_start_pos:]` (covers single- or multi-contraction bases). If NO qualifying up-swing (or all are trailing/developing) -> `no_base`.
3. **Duration** -- `base_duration_bars = asof_pos - base_start_pos` (in BARS, never `Swing.duration_days`), where `asof_pos = len(sliced) - 1`. `base_duration_bars >= MIN_BASE_BARS` (=15) else -> `duration`.
4. **Depth** -- `correction_depth_pct = (base_high - base_low) / base_high`. `<= depth_cap(base_duration_bars)` where the ladder is: `<=25 bars -> 0.25`; `26..200 bars -> 0.35`; `>200 bars -> 0.50`. Over the cap -> `depth`.
5. **Emergence (fresh cross, not recross)** -- with `close = sliced["Close"].to_numpy()`: `close[asof_pos - 1] <= base_high < close[asof_pos]` **AND** `max(close[base_start_pos:asof_pos]) <= base_high` (the half-open `[base_start_pos, asof_pos)` slice; the peak bar's close == base_high so equality holds). Either clause failing -> `no_emergence`.
6. **Primary = first base (first-fire)** -- for every prior `s_pos` in `range(MIN_HISTORY_BARS - 1, asof_pos)`, re-run criteria 1-5 on `sliced.iloc[:s_pos + 1]`; if ANY earlier prefix fires 1-5, reject `asof` as `not_primary` (early-exit on the first hit). No lookahead (each replay reads only bars `<= s`). Criterion 6 is NOT recursive (it replays only 1-5), so cost is O(N^2), bounded by young-name length.

`PrimaryBaseVerdict` (frozen dataclass): `fired: bool`, `first_rejecting_criterion: str | None` (one of `history|no_base|duration|depth|no_emergence|not_primary`, or `None` when fired), plus diagnostics `base_start_date: date | None`, `base_high: float | None`, `correction_depth_pct: float | None`, `base_duration_bars: int | None`, `emergence_close: float | None`.

---

## Task 1: Package scaffold + constants + exceptions

**Files:**
- Create: `research/harness/minervini_primary_base_recall/__init__.py`
- Create: `research/harness/minervini_primary_base_recall/constants.py`
- Create: `research/harness/minervini_primary_base_recall/exceptions.py`
- Create: `tests/research/minervini_primary_base_recall/__init__.py`
- Test: `tests/research/minervini_primary_base_recall/test_constants.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_constants.py
from __future__ import annotations

from research.harness.minervini_primary_base_recall import constants as c


def test_scalar_constants_match_spec():
    assert c.MIN_HISTORY_BARS == 40
    assert c.MIN_BASE_BARS == 15
    assert c.ZIGZAG_THRESHOLD_PCT == 3.0
    assert c.MAX_CONTROL_AGE_BARS == 504
    assert c.YOUNG_NAME_CEILING_BARS == 221
    assert c.CONTROL_K == 5
    assert c.WINDOW_BACK == 60
    assert c.WINDOW_FWD == 5
    # Re-exported from the FROZEN harness (reuse, not redefine).
    assert c.CONTROL_GAP_BARS == 120
    assert c.DEFAULT_CONTROL_SEED == 20260608


def test_depth_cap_ladder_boundaries():
    # WRONG-PATH (a flat single cap, e.g. always 0.35) would return 0.35 at dur=25 and 0.50.
    # RIGHT-PATH (graduated ladder):
    assert c.depth_cap(10) == 0.25
    assert c.depth_cap(25) == 0.25      # boundary: <=25 -> 0.25
    assert c.depth_cap(26) == 0.35      # boundary: 26 -> 0.35
    assert c.depth_cap(200) == 0.35     # boundary: <=200 -> 0.35
    assert c.depth_cap(201) == 0.50     # boundary: >200 -> 0.50
    assert c.depth_cap(999) == 0.50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_constants.py -q`
Expected: FAIL with `ModuleNotFoundError: research.harness.minervini_primary_base_recall`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_primary_base_recall/__init__.py
```
(empty file)

```python
# tests/research/minervini_primary_base_recall/__init__.py
```
(empty file)

```python
# research/harness/minervini_primary_base_recall/constants.py
from __future__ import annotations

# Reuse the FROZEN harness's control-sampling constants (do NOT redefine).
from research.harness.minervini_exemplar_recall.constants import (  # noqa: F401
    CONTROL_GAP_BARS,
    DEFAULT_CONTROL_SEED,
)

# --- Minervini primary base, TWoSMW Ch.11 (quantified per spec section 2/5) ---
# "at least a couple of months of trading activity" -> ~2 months ~= 40 trading days.
MIN_HISTORY_BARS = 40
# "a base of at least three to five weeks" -> >= 3 weeks ~= 15 trading days.
MIN_BASE_BARS = 15
# Zigzag swing threshold for base identification (spec section 5 crit 2; matches the
# foundation generate_candidate_windows zigzag_pivot default).
ZIGZAG_THRESHOLD_PCT = 3.0

# Graduated correction-depth caps keyed on base duration in BARS (spec section 5 crit 4):
#   <=25 bars (~5wk): 0.25 ; 26-200 bars: 0.35 ; >200 bars (~1yr): 0.50.
# (max_inclusive_bars, cap) ordered ascending; a deliberately literal mapping of the Ch.11 prose.
DEPTH_LADDER: tuple[tuple[int, float], ...] = ((25, 0.25), (200, 0.35))
DEPTH_LADDER_TOP_CAP = 0.50


def depth_cap(duration_bars: int) -> float:
    """The graduated max correction depth (fraction) for a base of duration_bars bars."""
    for max_bars, cap in DEPTH_LADDER:
        if duration_bars <= max_bars:
            return cap
    return DEPTH_LADDER_TOP_CAP


# --- Precision control (spec section 4/6) ---
# Young-window control pool ceiling: ~first 2 years post-IPO (504 trading days). The pre-filter
# range is [MIN_HISTORY_BARS-1, MAX_CONTROL_AGE_BARS-1] = [39, 503].
MAX_CONTROL_AGE_BARS = 504
# The ORIGINAL Minervini-recall study's screenable floor (200 + rising_ma_period_days = 221):
# names with fewer bars-through-anchor were un-screenable there (the sub-floor cohort); >= this
# is a "sufficient-history" positive control.
YOUNG_NAME_CEILING_BARS = 221
CONTROL_K = 5

# --- Timing sweep window (positional, spec section 6) ---
WINDOW_BACK = 60
WINDOW_FWD = 5
```

```python
# research/harness/minervini_primary_base_recall/exceptions.py
from __future__ import annotations


class PrimaryBaseRecallError(Exception):
    """Base class for all minervini_primary_base_recall harness errors."""


class UnknownExemplarIdError(PrimaryBaseRecallError):
    """A curated cohort exemplar_id was not found in the exemplar CSV."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_constants.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/__init__.py research/harness/minervini_primary_base_recall/constants.py research/harness/minervini_primary_base_recall/exceptions.py tests/research/minervini_primary_base_recall/__init__.py tests/research/minervini_primary_base_recall/test_constants.py
git commit -m "feat(research): primary-base-recall scaffold (constants + exceptions)"
git log -1 --format='%(trailers)'   # MUST print an empty line
```

---

## Task 2: Screen criteria 1-4 (history, base-id, duration, depth) + calendar->bar mapping

**Files:**
- Create: `research/harness/minervini_primary_base_recall/primary_base_screen.py`
- Test: `tests/research/minervini_primary_base_recall/test_primary_base_screen.py`

This task builds `screen_at` through criterion 4 plus the diagnostics. Criteria 5-6 land in Task 3 (the test file is extended there). To keep the screen testable in isolation now, implement the full `_eval_1_to_5` helper but have it stop at "all 1-5 pass" only via the emergence check added in Task 3; in THIS task `_eval_1_to_5` ends at criterion 4 and a placeholder emergence that always passes is NOT acceptable -- instead, structure the code so Task 2 implements criteria 1-4 and a temporary `screen_at` that returns the diagnostics + first reject among `history|no_base|duration|depth`, and Task 3 inserts criteria 5-6. The tests below assert only criteria 1-4 behavior and pass through Task 3 unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_primary_base_screen.py
from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.minervini_primary_base_recall.primary_base_screen import screen_at


def _frame(closes: list[float], start: date = date(2010, 1, 4)) -> pd.DataFrame:
    """Build a clean business-day OHLCV frame from a Close list (the shape read_full emits)."""
    idx = pd.bdate_range(start=start, periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame(
        {"Open": c, "High": c * 1.001, "Low": c * 0.999, "Close": c, "Volume": 1_000_000.0},
        index=idx,
    )


def test_history_gate_rejects_short_slice():
    # 30 bars < MIN_HISTORY_BARS (40). WRONG-PATH (no history gate) would attempt base-id and
    # likely return no_base; RIGHT-PATH returns first_rejecting_criterion == "history".
    bars = _frame([10.0 + i * 0.01 for i in range(30)])
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "history"


def test_no_base_when_pure_uptrend_no_downswing():
    # Monotone rise: extract_zigzag_swings emits at most one developing up-swing (never closed by a
    # down-swing). WRONG-PATH (treat any high as base_high) fires; RIGHT-PATH -> "no_base".
    bars = _frame([10.0 + i * 0.05 for i in range(60)])
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "no_base"


def test_depth_gate_rejects_too_deep_correction():
    # A 50-bar history: rise to a peak (~100), then a >25% drop and a long sideways base (so
    # duration passes, depth fails for a <=25-bar... use a SHORT base so cap=0.25 and depth ~0.40).
    # Construct: 18 bars rising 80->100 (peak at pos 17), then 20 bars dropping to 60 and flat at
    # ~62 (depth = (100-60)/100 = 0.40 > 0.25 cap for the >=15-bar but <=25-bar duration).
    rise = [80.0 + (100.0 - 80.0) * i / 17 for i in range(18)]          # peak 100 at idx 17
    drop = [100.0 - (100.0 - 60.0) * (i + 1) / 4 for i in range(4)]     # quick drop to 60
    flat = [61.0, 60.5, 62.0, 61.5, 60.0, 61.0, 60.5, 62.0, 61.5, 60.0, 61.0, 60.5, 62.0, 61.5]
    bars = _frame(rise + drop + flat)  # 18 + 4 + 14 = 36 bars... pad history below
    # Pad 10 quiet leading bars so len >= 40 (history passes) and the peak stays the global high.
    pad = _frame([55.0] * 10, start=date(2009, 11, 2))
    bars = pd.concat([pad, bars])
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "depth"
    assert v.correction_depth_pct is not None and v.correction_depth_pct > 0.25


def test_duration_gate_rejects_too_short_base():
    # A clean peak then only a 10-bar correction-to-asof (< MIN_BASE_BARS=15) -> "duration".
    pad = [50.0] * 40
    rise = [60.0 + (90.0 - 60.0) * i / 9 for i in range(10)]   # peak 90 at end of rise
    short = [88.0, 86.0, 84.0, 85.0, 86.0, 87.0, 88.0, 89.0, 88.5, 87.0]  # 10-bar base
    bars = _frame(pad + rise + short)
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "duration"


def test_calendar_to_bar_mapping_uses_bars_not_calendar_days():
    # Plant a base whose CALENDAR span (Swing.duration_days) >= 21 but whose BAR count is < 15,
    # by inserting weekend/holiday gaps. bdate_range already excludes weekends, so 14 business days
    # span ~20 calendar days. We assert the duration gate uses the 14-bar count (-> "duration"),
    # NOT the ~20 calendar days (which a WRONG-PATH duration_days check would pass).
    pad = [50.0] * 40
    rise = [60.0 + (90.0 - 60.0) * i / 9 for i in range(10)]   # peak 90
    base14 = [88.0, 86.0, 84.0, 85.0, 86.0, 87.0, 88.0, 89.0, 88.5, 87.0, 86.5, 88.0, 89.0, 88.0]
    bars = _frame(pad + rise + base14)   # base = 14 BARS after the peak
    asof = bars.index[-1].date()
    v = screen_at(bars, asof)
    # base_duration_bars == 14 (bars), so it fails MIN_BASE_BARS=15 with "duration".
    # WRONG-PATH (Swing.duration_days, ~20 calendar days) would PASS duration and move on.
    assert v.first_rejecting_criterion == "duration"
    assert v.base_duration_bars == 14
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_primary_base_screen.py -q`
Expected: FAIL with `ImportError: cannot import name 'screen_at'`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_primary_base_recall/primary_base_screen.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from research.harness.minervini_exemplar_recall.ohlcv_reader import slice_to
from swing.patterns.foundation import extract_zigzag_swings

from .constants import MIN_BASE_BARS, MIN_HISTORY_BARS, ZIGZAG_THRESHOLD_PCT, depth_cap


@dataclass(frozen=True)
class PrimaryBaseVerdict:
    fired: bool
    first_rejecting_criterion: str | None  # history|no_base|duration|depth|no_emergence|not_primary
    base_start_date: date | None = None
    base_high: float | None = None
    correction_depth_pct: float | None = None
    base_duration_bars: int | None = None
    emergence_close: float | None = None


@dataclass(frozen=True)
class _BaseId:
    base_start_pos: int
    base_start_date: date
    base_high: float
    base_low: float


def _identify_base(sliced: pd.DataFrame) -> _BaseId | None:
    """The pre-base peak (highest swing-high pivot with a down-swing after it) + base low.

    Calendar->bar mapping: every Swing date is mapped back to an integer bar position in `sliced`.
    """
    swings = extract_zigzag_swings(sliced, initial_threshold_pct=ZIGZAG_THRESHOLD_PCT)
    if not swings:
        return None
    pos_by_date = {ts.date(): i for i, ts in enumerate(sliced.index)}
    closes = sliced["Close"].to_numpy()
    best: _BaseId | None = None
    for i, sw in enumerate(swings):
        # A swing-high pivot WITH a down-swing after it = an up-swing immediately followed by a
        # down-swing in the alternating closed-swing list (the trailing/developing leg is excluded
        # because the next swing must exist and be "down").
        if sw.direction != "up":
            continue
        if i + 1 >= len(swings) or swings[i + 1].direction != "down":
            continue
        peak_pos = pos_by_date[sw.end_date]
        peak_high = float(sw.end_price)
        if best is None or peak_high > best.base_high:
            base_low = float(closes[peak_pos:].min())  # lowest Close in [base_start, asof]
            best = _BaseId(
                base_start_pos=peak_pos,
                base_start_date=sw.end_date,
                base_high=peak_high,
                base_low=base_low,
            )
    return best


def screen_at(bars: pd.DataFrame, asof_date: date) -> PrimaryBaseVerdict:
    """Minervini Ch.11 primary-base screen, point-in-time at asof_date (no lookahead)."""
    sliced = slice_to(bars, asof_date)
    # Criterion 1: history.
    if len(sliced) < MIN_HISTORY_BARS:
        return PrimaryBaseVerdict(False, "history")
    # Criterion 2: base identification.
    base = _identify_base(sliced)
    if base is None:
        return PrimaryBaseVerdict(False, "no_base")
    asof_pos = len(sliced) - 1
    base_duration_bars = asof_pos - base.base_start_pos
    correction_depth_pct = (
        (base.base_high - base.base_low) / base.base_high if base.base_high else 0.0
    )
    diag = dict(
        base_start_date=base.base_start_date,
        base_high=base.base_high,
        correction_depth_pct=correction_depth_pct,
        base_duration_bars=base_duration_bars,
    )
    # Criterion 3: duration (in BARS).
    if base_duration_bars < MIN_BASE_BARS:
        return PrimaryBaseVerdict(False, "duration", **diag)
    # Criterion 4: graduated correction depth.
    if correction_depth_pct > depth_cap(base_duration_bars):
        return PrimaryBaseVerdict(False, "depth", **diag)
    # Criteria 5-6 land in Task 3. Until then this is incomplete; Task 3 replaces the tail.
    return PrimaryBaseVerdict(False, "no_emergence", **diag)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_primary_base_screen.py -q`
Expected: PASS (5 passed). If `no_base`/`depth` fixtures don't behave as expected, print the verdict and the `extract_zigzag_swings(...)` output for the fixture and adjust the planted closes until the zigzag emits the intended peak (the 3% threshold needs each leg to move >= 3%).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/primary_base_screen.py tests/research/minervini_primary_base_recall/test_primary_base_screen.py
git commit -m "feat(research): primary-base screen criteria 1-4 (history/base/duration/depth) with calendar-to-bar mapping"
git log -1 --format='%(trailers)'
```

---

## Task 3: Screen criteria 5 (fresh-cross emergence) + 6 (primary first-fire)

**Files:**
- Modify: `research/harness/minervini_primary_base_recall/primary_base_screen.py`
- Test: `tests/research/minervini_primary_base_recall/test_primary_base_screen.py` (append)

- [ ] **Step 1: Write the failing test (append to the existing test file)**

```python
def test_fires_on_fresh_cross_first_base():
    # A clean primary base that freshly crosses base_high at asof -> FIRES.
    pad = [40.0] * 40
    rise = [50.0 + (100.0 - 50.0) * i / 9 for i in range(10)]   # peak 100
    base = [92.0, 88.0, 90.0, 89.0, 91.0, 93.0, 90.0, 92.0, 94.0, 91.0,
            93.0, 95.0, 92.0, 94.0, 96.0, 95.0]                 # >=15-bar base, depth ~12% (<0.35)
    cross = [99.0, 101.0]   # close[-2]=99 (<=100), close[-1]=101 (>100): fresh cross
    bars = _frame(pad + rise + base + cross)
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is True
    assert v.first_rejecting_criterion is None
    assert v.emergence_close is not None and v.emergence_close > v.base_high


def test_already_above_base_high_is_no_emergence_not_a_state():
    # asof close is above base_high but so was the PRIOR close (no fresh cross at asof).
    pad = [40.0] * 40
    rise = [50.0 + (100.0 - 50.0) * i / 9 for i in range(10)]   # peak 100
    base = [92.0, 88.0, 90.0, 89.0, 91.0, 93.0, 90.0, 92.0, 94.0, 91.0,
            93.0, 95.0, 92.0, 94.0, 96.0, 95.0]
    above = [101.0, 103.0]  # close[-2]=101 already > 100 -> NOT a fresh cross at asof
    bars = _frame(pad + rise + base + above)
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "no_emergence"


def test_failed_breakout_then_reset_recross_does_not_fire():
    # THE first-cross-not-recross discriminator (R1.M6). base_high is the clean CLOSED pivot 101.
    # An earlier close (102 at asof-2) pokes ABOVE 101 inside the DEVELOPING final up-leg (which
    # never closes -> it is NOT a new pivot, so base_high stays 101), then asof-1 dips to 100.5
    # (a <3% pullback, so the leg stays developing), then asof closes 102.5 (a fresh cross of 101).
    # The second clause max(close[base_start:asof]) <= base_high is THE discriminator: 102 > 101
    # already happened inside the base -> this is a recross, not a first emergence.
    # WRONG-PATH (bare one-bar recross close[asof-1] <= base_high < close[asof]): 100.5 <= 101 <
    #   102.5 -> FIRES wrongly. RIGHT-PATH -> "no_emergence".
    # NOTE: criterion 5 is evaluated BEFORE criterion 6 in screen_at; since 1-5 fail at asof
    # (no_emergence), the first-fire replay is never reached -> the result is no_emergence (not
    # not_primary), even though an earlier session (asof-2) would itself fire 1-5.
    pad = [40.0] * 40
    rise = [50.0 + (101.0 - 50.0) * i / 11 for i in range(12)]   # closed up-swing, peak 101 @ pos 51
    drop = [99.0, 97.0, 95.0, 96.0, 95.0, 96.0, 95.0, 96.0]   # -3.96% at 97 closes up-swing; low 95
    # Developing recovery up-leg from the 95 low: monotone up to 102 (asof-2), small dip to 100.5
    # (asof-1, -1.5% -> leg keeps developing), then 102.5 (asof). It never reverses >=3% so it is
    # NOT emitted as a closed swing -> no new pivot above 101 -> base_high stays 101. base_start at
    # pos 51, asof at pos 67 -> base_duration_bars = 16 (>= MIN_BASE_BARS, so duration passes and we
    # reach the emergence check).
    recovery = [97.0, 98.0, 99.0, 100.0, 101.0, 102.0, 100.5, 102.5]
    bars = _frame(pad + rise + drop + recovery)
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "no_emergence"
    assert v.base_high is not None and abs(v.base_high - 101.0) < 0.5  # pivot, NOT the 102 poke


def test_second_base_after_an_earlier_qualifying_base_is_not_primary():
    # Two complete primary-base emergences in one history; screening at the SECOND emergence must
    # return not_primary (criteria 1-5 fired earlier at the first emergence).
    # WRONG-PATH (no first-fire replay) FIRES at the second base; RIGHT-PATH -> "not_primary".
    pad = [40.0] * 40
    # First base + emergence (peak 100, base, fresh cross to 101) ...
    rise1 = [50.0 + (100.0 - 50.0) * i / 9 for i in range(10)]
    base1 = [92.0, 88.0, 90.0, 91.0, 93.0, 90.0, 92.0, 94.0, 91.0, 93.0, 95.0, 92.0, 94.0, 96.0, 95.0]
    cross1 = [99.0, 101.0]
    # ... then a deeper pullback forming a SECOND base (new peak 130) + fresh cross to 131.
    rise2 = [102.0 + (130.0 - 102.0) * i / 9 for i in range(10)]
    base2 = [120.0, 116.0, 118.0, 119.0, 121.0, 118.0, 120.0, 122.0, 119.0, 121.0, 123.0, 120.0, 122.0, 124.0, 123.0]
    cross2 = [129.0, 131.0]
    bars = _frame(pad + rise1 + base1 + cross1 + rise2 + base2 + cross2)
    # Screen at the FINAL session (the second emergence).
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "not_primary"
    # Sanity: screening at the FIRST emergence DOES fire (it is the primary).
    first_emergence_date = bars.index[40 + 10 + 15 + 2 - 1].date()  # last bar of cross1
    v1 = screen_at(bars, first_emergence_date)
    assert v1.fired is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_primary_base_screen.py -q`
Expected: FAIL -- the new `test_fires_*` cases fail because the Task-2 tail always returns `no_emergence`.

- [ ] **Step 3: Write minimal implementation**

Replace the `screen_at` tail (everything from the `# Criteria 5-6 land in Task 3` comment onward) and add the `_eval_1_to_5` refactor. The cleanest structure factors criteria 1-5 into a helper that both `screen_at` (for asof) and the criterion-6 replay reuse:

```python
# --- replace the body of screen_at + add helpers in primary_base_screen.py ---

@dataclass(frozen=True)
class _Partial:
    fired_1_to_5: bool
    first_rejecting: str | None
    base_start_date: date | None = None
    base_high: float | None = None
    correction_depth_pct: float | None = None
    base_duration_bars: int | None = None
    emergence_close: float | None = None


def _eval_1_to_5(sliced: pd.DataFrame) -> _Partial:
    if len(sliced) < MIN_HISTORY_BARS:
        return _Partial(False, "history")
    base = _identify_base(sliced)
    if base is None:
        return _Partial(False, "no_base")
    asof_pos = len(sliced) - 1
    base_duration_bars = asof_pos - base.base_start_pos
    correction_depth_pct = (
        (base.base_high - base.base_low) / base.base_high if base.base_high else 0.0
    )
    diag = dict(
        base_start_date=base.base_start_date,
        base_high=base.base_high,
        correction_depth_pct=correction_depth_pct,
        base_duration_bars=base_duration_bars,
    )
    if base_duration_bars < MIN_BASE_BARS:
        return _Partial(False, "duration", **diag)
    if correction_depth_pct > depth_cap(base_duration_bars):
        return _Partial(False, "depth", **diag)
    closes = sliced["Close"].to_numpy()
    emergence_close = float(closes[asof_pos])
    fresh_cross = closes[asof_pos - 1] <= base.base_high < closes[asof_pos]
    first_cross = closes[base.base_start_pos:asof_pos].max() <= base.base_high
    if not (fresh_cross and first_cross):
        return _Partial(False, "no_emergence", **diag)
    return _Partial(True, None, emergence_close=emergence_close, **diag)


def screen_at(bars: pd.DataFrame, asof_date: date) -> PrimaryBaseVerdict:
    """Minervini Ch.11 primary-base screen, point-in-time at asof_date (no lookahead)."""
    sliced = slice_to(bars, asof_date)
    partial = _eval_1_to_5(sliced)
    diag = dict(
        base_start_date=partial.base_start_date,
        base_high=partial.base_high,
        correction_depth_pct=partial.correction_depth_pct,
        base_duration_bars=partial.base_duration_bars,
        emergence_close=partial.emergence_close,
    )
    if not partial.fired_1_to_5:
        return PrimaryBaseVerdict(False, partial.first_rejecting, **diag)
    # Criterion 6: primary = first base. Replay 1-5 over every prior session; if any earlier
    # session fires, asof is a LATER base -> not_primary. No lookahead (each replay reads <= s).
    asof_pos = len(sliced) - 1
    for s_pos in range(MIN_HISTORY_BARS - 1, asof_pos):
        if _eval_1_to_5(sliced.iloc[: s_pos + 1]).fired_1_to_5:
            return PrimaryBaseVerdict(False, "not_primary", **diag)
    return PrimaryBaseVerdict(True, None, **diag)
```

Delete the now-dead `_BaseId`-only `screen_at` tail from Task 2 (the `# Criteria 5-6 land in Task 3` block). Keep `_identify_base` and `PrimaryBaseVerdict`. Remove the now-unused direct imports if any (none change).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_primary_base_screen.py -q`
Expected: PASS (9 passed). If `not_primary` doesn't trigger, print `screen_at` at each session across the window to confirm the first emergence fires before the second.

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/primary_base_screen.py tests/research/minervini_primary_base_recall/test_primary_base_screen.py
git commit -m "feat(research): primary-base screen emergence (fresh-cross-not-recross) and primary first-fire criteria"
git log -1 --format='%(trailers)'
```

---

## Task 4: Cohort (curated primary-base ids + roles + resolution)

**Files:**
- Create: `research/harness/minervini_primary_base_recall/cohort.py`
- Test: `tests/research/minervini_primary_base_recall/test_cohort.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_cohort.py
from __future__ import annotations

from pathlib import Path

import pytest

from research.harness.minervini_primary_base_recall.cohort import (
    CURATED_COHORT,
    resolve_cohort,
)
from research.harness.minervini_primary_base_recall.exceptions import UnknownExemplarIdError

_REAL_CSV = Path("research/data/minervini-exemplars.csv")


def test_curated_cohort_is_the_five_documented_ids_with_roles():
    by_id = {m.exemplar_id: m for m in CURATED_COHORT}
    assert set(by_id) == {
        "twosmw-fig11-1-amzn", "ttlc-fig10-1-body", "twosmw-fig11-6-dks",
        "twosmw-fig11-7-jnpr", "twosmw-fig11-3-yhoo",
    }
    # MELI is deliberately absent (young-VCP, R1.M4).
    assert "twosmw-fig10-33-meli" not in by_id
    assert by_id["twosmw-fig11-3-yhoo"].role == "positive_control"
    assert by_id["twosmw-fig11-1-amzn"].role == "sub_floor"
    assert by_id["ttlc-fig10-1-body"].role == "sub_floor"
    assert all(m.book_citation for m in CURATED_COHORT)


@pytest.mark.skipif(not _REAL_CSV.exists(), reason="real exemplar CSV not present")
def test_resolve_cohort_pairs_each_member_with_its_exemplar_row():
    resolved = resolve_cohort(_REAL_CSV)
    assert {r.member.exemplar_id for r in resolved} == {m.exemplar_id for m in CURATED_COHORT}
    amzn = next(r for r in resolved if r.member.exemplar_id == "twosmw-fig11-1-amzn")
    assert amzn.row.ticker == "AMZN"
    assert amzn.row.date_precision == "month"   # drives sweep-only timing
    body = next(r for r in resolved if r.member.exemplar_id == "ttlc-fig10-1-body")
    assert body.row.date_precision == "day"


def test_resolve_rejects_unknown_id(tmp_path):
    # A CSV missing one curated id -> UnknownExemplarIdError (not a silent drop).
    csv = tmp_path / "ex.csv"
    header = (
        "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
        "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes"
    )
    # Only one of the five curated ids present.
    csv.write_text(
        header + "\ntwosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n\n",
        encoding="utf-8",
    )
    with pytest.raises(UnknownExemplarIdError):
        resolve_cohort(csv)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_cohort.py -q`
Expected: FAIL with `ModuleNotFoundError`/`ImportError` (cohort module not yet present).

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_primary_base_recall/cohort.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow, read_exemplars

from .exceptions import UnknownExemplarIdError


@dataclass(frozen=True)
class CohortMember:
    exemplar_id: str
    role: str  # "sub_floor" | "positive_control"
    book_citation: str


@dataclass(frozen=True)
class ResolvedMember:
    member: CohortMember
    row: ExemplarRow


# The curated documented-primary-base cohort (spec section 3). Roles: sub_floor names were
# un-screenable by the original Minervini-recall study (< YOUNG_NAME_CEILING_BARS bars at entry);
# the positive_control has sufficient history. JNPR is a sub_floor name that the screen will report
# history-excluded at runtime (25 bars < MIN_HISTORY_BARS). MELI is excluded (young-VCP, R1.M4).
CURATED_COHORT: tuple[CohortMember, ...] = (
    CohortMember("twosmw-fig11-1-amzn", "sub_floor", "TWoSMW Ch.11 Fig 11.1 (AMZN-1997)"),
    CohortMember("ttlc-fig10-1-body", "sub_floor", "TWoSMW Ch.11 Fig 11.5 / TTLC Fig 10-1 (BODY)"),
    CohortMember("twosmw-fig11-6-dks", "sub_floor", "TWoSMW Ch.11 Fig 11.6 (DKS)"),
    CohortMember("twosmw-fig11-7-jnpr", "sub_floor", "TWoSMW Ch.11 Fig 11.7 (JNPR, history-excluded)"),
    CohortMember("twosmw-fig11-3-yhoo", "positive_control", "TWoSMW Ch.11 Fig 11.3 (YHOO)"),
)


def resolve_cohort(csv_path: Path) -> list[ResolvedMember]:
    """Pair each curated cohort member with its ExemplarRow; raise on any missing id."""
    rows_by_id = {r.exemplar_id: r for r in read_exemplars(csv_path)}
    resolved: list[ResolvedMember] = []
    for member in CURATED_COHORT:
        row = rows_by_id.get(member.exemplar_id)
        if row is None:
            raise UnknownExemplarIdError(
                f"curated cohort id {member.exemplar_id!r} not found in {csv_path}"
            )
        resolved.append(ResolvedMember(member=member, row=row))
    return resolved
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_cohort.py -q`
Expected: PASS (3 passed; the real-CSV test runs because the file exists).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/cohort.py tests/research/minervini_primary_base_recall/test_cohort.py
git commit -m "feat(research): primary-base cohort (curated ids, roles, exemplar-row resolution)"
git log -1 --format='%(trailers)'
```

---

## Task 5: Timing (day window + full-documented-month window; single-session day-only)

**Files:**
- Create: `research/harness/minervini_primary_base_recall/timing.py`
- Test: `tests/research/minervini_primary_base_recall/test_timing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_timing.py
from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.minervini_primary_base_recall import timing


def _frame(start: date, periods: int):
    idx = pd.bdate_range(start=start, periods=periods)
    c = pd.Series([10.0 + i * 0.01 for i in range(periods)], index=idx, dtype=float)
    return pd.DataFrame(
        {"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1_000_000.0}, index=idx
    )


def test_day_window_is_entry_minus_back_to_entry_plus_fwd():
    bars = _frame(date(2010, 1, 4), 300)
    entry = bars.index[200].date()
    sessions = timing.sweep_sessions(bars, entry, "day", window_back=60, window_fwd=5)
    # RIGHT-PATH: positions [140, 205] inclusive -> 66 sessions; first == entry-60bd.
    assert sessions[0] == bars.index[140].date()
    assert sessions[-1] == bars.index[205].date()
    assert len(sessions) == 66


def test_month_window_spans_full_documented_month_plus_slack():
    # A frame straddling Sept 1997; month-precision anchor parses to date(1997,9,1).
    bars = _frame(date(1997, 1, 2), 400)
    anchor = date(1997, 9, 1)
    sept = [d for d in bars.index if d.year == 1997 and d.month == 9]
    first_sept_pos = list(bars.index).index(sept[0])
    last_sept_pos = list(bars.index).index(sept[-1])
    sessions = timing.sweep_sessions(bars, anchor, "month", window_back=60, window_fwd=5)
    # RIGHT-PATH (full month): start = first_trading_day_of_month - 60bd ; end = last + 5bd.
    assert sessions[0] == bars.index[max(0, first_sept_pos - 60)].date()
    assert sessions[-1] == bars.index[last_sept_pos + 5].date()
    # WRONG-PATH (parsed-first-of-month [anchor-60, anchor+5]) would END only 5bd after the FIRST
    # trading day of September, never reaching late-September. Assert it is strictly later.
    naive_end_pos = first_sept_pos + 5  # the wrong-path tail
    assert (last_sept_pos + 5) > naive_end_pos
    assert sessions[-1] != bars.index[naive_end_pos].date()


def test_single_session_only_for_day_precision():
    bars = _frame(date(2010, 1, 4), 300)
    entry = bars.index[200].date()
    # day precision -> exactly the entry session.
    assert timing.single_session(bars, entry, "day") == [entry]
    # month precision -> EMPTY (sweep-only; R1.M3).
    assert timing.single_session(bars, date(2010, 1, 1), "month") == []


def test_no_lookahead_every_session_is_le_itself():
    # screen_at must only see bars <= the session; assert the sweep sessions are all in-frame.
    bars = _frame(date(2010, 1, 4), 120)
    entry = bars.index[100].date()
    sessions = timing.sweep_sessions(bars, entry, "day", window_back=60, window_fwd=5)
    assert all(s <= bars.index[-1].date() for s in sessions)
    assert sessions[-1] == bars.index[min(105, len(bars) - 1)].date()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_timing.py -q`
Expected: FAIL with `ImportError`/`AttributeError` (timing module/functions absent).

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_primary_base_recall/timing.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .primary_base_screen import PrimaryBaseVerdict, screen_at

_DAY_PRECISIONS = frozenset({"day", "exact"})


@dataclass(frozen=True)
class SessionEval:
    session: date
    verdict: PrimaryBaseVerdict


@dataclass(frozen=True)
class TimingResult:
    mode: str  # "single_session" | "window_sweep"
    sessions: tuple[SessionEval, ...]
    fired: bool
    firing_sessions: tuple[date, ...]


def _entry_pos(bars: pd.DataFrame, entry_anchor: date) -> int | None:
    mask = bars.index.date >= entry_anchor
    return int(mask.argmax()) if mask.any() else None


def _month_bounds(bars: pd.DataFrame, anchor: date) -> tuple[int, int] | None:
    """Positions of the first and last in-frame trading day of anchor's calendar month."""
    in_month = [i for i, ts in enumerate(bars.index) if ts.year == anchor.year and ts.month == anchor.month]
    if not in_month:
        return None
    return in_month[0], in_month[-1]


def sweep_bounds(
    bars: pd.DataFrame, entry_anchor: date, date_precision: str, *, window_back: int, window_fwd: int
) -> tuple[int, int] | None:
    """The positional [start, end] of the recall sweep window for this exemplar (inclusive)."""
    if date_precision == "month":
        mb = _month_bounds(bars, entry_anchor)
        if mb is None:
            return None
        first_pos, last_pos = mb
        return max(0, first_pos - window_back), min(len(bars) - 1, last_pos + window_fwd)
    pos = _entry_pos(bars, entry_anchor)
    if pos is None:
        return None
    return max(0, pos - window_back), min(len(bars) - 1, pos + window_fwd)


def sweep_sessions(
    bars: pd.DataFrame, entry_anchor: date, date_precision: str, *, window_back: int, window_fwd: int
) -> list[date]:
    bounds = sweep_bounds(
        bars, entry_anchor, date_precision, window_back=window_back, window_fwd=window_fwd
    )
    if bounds is None:
        return []
    start, end = bounds
    return [d.date() for d in bars.index[start : end + 1]]


def single_session(bars: pd.DataFrame, entry_anchor: date, date_precision: str) -> list[date]:
    # Single-session recall is reported ONLY for day/exact precision (R1.M3); month -> [].
    if date_precision not in _DAY_PRECISIONS:
        return []
    pos = _entry_pos(bars, entry_anchor)
    return [] if pos is None else [bars.index[pos].date()]


def _result(mode: str, bars: pd.DataFrame, sessions: list[date]) -> TimingResult:
    evals = tuple(SessionEval(s, screen_at(bars, s)) for s in sessions)
    firing = tuple(e.session for e in evals if e.verdict.fired)
    return TimingResult(mode=mode, sessions=evals, fired=len(firing) > 0, firing_sessions=firing)


def evaluate_exemplar(
    bars: pd.DataFrame, entry_anchor: date, date_precision: str, *, window_back: int, window_fwd: int
) -> dict[str, TimingResult]:
    return {
        "single_session": _result(
            "single_session", bars, single_session(bars, entry_anchor, date_precision)
        ),
        "window_sweep": _result(
            "window_sweep",
            bars,
            sweep_sessions(
                bars, entry_anchor, date_precision, window_back=window_back, window_fwd=window_fwd
            ),
        ),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_timing.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/timing.py tests/research/minervini_primary_base_recall/test_timing.py
git commit -m "feat(research): primary-base timing (day window + full-documented-month sweep; single-session day-only)"
git log -1 --format='%(trailers)'
```

---

## Task 6: Precision control (own pre-filtered young-window sampler)

**Files:**
- Create: `research/harness/minervini_primary_base_recall/precision_control.py`
- Test: `tests/research/minervini_primary_base_recall/test_precision_control.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_precision_control.py
from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.minervini_exemplar_recall.control_cohort import ControlAnchor
from research.harness.minervini_primary_base_recall import precision_control as pc
from research.harness.minervini_primary_base_recall.constants import (
    MAX_CONTROL_AGE_BARS,
    MIN_HISTORY_BARS,
)


def _frame(periods: int):
    idx = pd.bdate_range(start=date(2000, 1, 3), periods=periods)
    c = pd.Series([10.0 + i * 0.01 for i in range(periods)], index=idx, dtype=float)
    return pd.DataFrame(
        {"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1_000_000.0}, index=idx
    )


def test_eligible_pool_is_prefiltered_young_window_minus_gap_and_sweep():
    # 900-bar archive; entry at pos 600; sweep [540, 605]; gap CONTROL_GAP_BARS=120.
    bars = _frame(900)
    entry_pos = 600
    sweep = (540, 605)
    pool = pc.eligible_control_positions(
        bars, entry_pos=entry_pos, sweep_start=sweep[0], sweep_end=sweep[1]
    )
    # RIGHT-PATH: positions are PRE-FILTERED to [39, 503]; then |p-600| >= 120 (all of [39,503]
    # satisfy, since max is 503 and 600-503=97 < 120 EXCLUDES 481..503) and outside [540,605]
    # (no overlap with [39,503]). So the gap band 481..503 is removed.
    assert min(pool) == MIN_HISTORY_BARS - 1            # 39
    assert max(pool) <= MAX_CONTROL_AGE_BARS - 1        # <= 503
    assert all(abs(p - entry_pos) >= 120 for p in pool)
    assert 480 in pool and 481 not in pool             # 600-481=119 < 120 -> excluded
    # WRONG-PATH (post-filter: sample full archive THEN clip to young) would include positions
    # > 503 before clipping and could yield far fewer/none for a deep-history name; assert none
    # exceed the young ceiling.
    assert all(p <= 503 for p in pool)


def test_position_beyond_max_age_is_never_eligible_prefilter_not_postfilter():
    bars = _frame(900)
    # Entry far in the future so the gap never touches the young window.
    pool = pc.eligible_control_positions(bars, entry_pos=850, sweep_start=800, sweep_end=860)
    assert max(pool) <= MAX_CONTROL_AGE_BARS - 1
    assert 504 not in pool and 700 not in pool


def test_sample_is_deterministic_and_capped_at_k():
    bars = _frame(900)
    anchors, eligible_count = pc.sample_young_controls(
        bars, entry_pos=600, sweep_start=540, sweep_end=605, k=5, base_seed=123, exemplar_index=0
    )
    again, _ = pc.sample_young_controls(
        bars, entry_pos=600, sweep_start=540, sweep_end=605, k=5, base_seed=123, exemplar_index=0
    )
    assert [a.session_pos for a in anchors] == [a.session_pos for a in again]  # deterministic
    assert len(anchors) == 5
    assert all(isinstance(a, ControlAnchor) for a in anchors)
    assert eligible_count >= 5  # reported BEFORE the k-cap (manifest field)


def test_single_session_per_anchor_is_the_primary_estimand():
    # screen_control_anchor returns BOTH a single-session fire and a window best-of fire; the
    # single-session per-anchor flag is the documented primary estimand (R1.M9), reported separately.
    bars = _frame(900)
    anchor = ControlAnchor(session=bars.index[300].date(), session_pos=300)
    res = pc.screen_control_anchor(bars, anchor, window_back=60, window_fwd=5)
    assert hasattr(res, "single_session_fired")
    assert hasattr(res, "window_fired")
    # A pure monotone uptrend never forms a primary base -> neither fires (specificity).
    assert res.single_session_fired is False
    assert res.window_fired is False


def test_month_precision_control_exclusion_uses_full_documented_month_window():
    # Codex WP-R1 M7: the control sampler must exclude the FULL documented-month sweep window for a
    # month-precision exemplar, NOT the parsed-first-of-month [entry-60bd, entry+5bd]. This ties the
    # composition run.py uses: timing.sweep_bounds(month) -> precision_control.eligible_control_positions.
    from datetime import date

    from research.harness.minervini_primary_base_recall import timing

    # A frame straddling Sept 1997 (the AMZN-1997 documented month). Entry far enough out that the
    # young pool [39,503] is not fully eaten by the 120-bar gap.
    idx = pd.bdate_range(start=date(1996, 1, 2), periods=900)
    c = pd.Series([10.0 + i * 0.01 for i in range(900)], index=idx, dtype=float)
    bars = pd.DataFrame(
        {"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1_000_000.0}, index=idx
    )
    anchor = date(1997, 9, 1)  # month-precision parsed first-of-month
    bounds = timing.sweep_bounds(bars, anchor, "month", window_back=60, window_fwd=5)
    assert bounds is not None
    sweep_start, sweep_end = bounds
    # A LATE-September-1997 position (the last documented-month trading day) -- this is INSIDE the
    # full-month window but OUTSIDE the WRONG-PATH parsed-first-of-month [first+(-60), first+5] tail.
    sept = [i for i, ts in enumerate(bars.index) if ts.year == 1997 and ts.month == 9]
    last_sept_pos = sept[-1]
    entry_pos = sept[0]  # first trading day of the documented month ~= the parsed-anchor position
    pool = pc.eligible_control_positions(
        bars, entry_pos=entry_pos, sweep_start=sweep_start, sweep_end=sweep_end
    )
    # RIGHT-PATH: last_sept_pos is within the full-month sweep window -> excluded from controls.
    assert last_sept_pos not in pool
    # And the full-month sweep end reaches past the WRONG-PATH parsed-first-of-month +5bd tail.
    assert sweep_end >= last_sept_pos > (entry_pos + 5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_precision_control.py -q`
Expected: FAIL with `ImportError`/`AttributeError`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_primary_base_recall/precision_control.py
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

import pandas as pd

from research.harness.minervini_exemplar_recall.control_cohort import ControlAnchor

from .constants import CONTROL_GAP_BARS, MAX_CONTROL_AGE_BARS, MIN_HISTORY_BARS
from .primary_base_screen import screen_at


def eligible_control_positions(
    bars: pd.DataFrame, *, entry_pos: int, sweep_start: int, sweep_end: int
) -> list[int]:
    """Young-window control candidates: PRE-FILTER to [MIN_HISTORY_BARS-1, MAX_CONTROL_AGE_BARS-1]
    BEFORE applying the gap + sweep-exclusion (the pre-filter, not a post-hoc clip, is what yields
    young controls for deep-history names -- spec section 6, R2.M1/R3.M1)."""
    lo = MIN_HISTORY_BARS - 1
    hi = min(MAX_CONTROL_AGE_BARS - 1, len(bars) - 1)
    return [
        p
        for p in range(lo, hi + 1)
        if abs(p - entry_pos) >= CONTROL_GAP_BARS and not (sweep_start <= p <= sweep_end)
    ]


def sample_young_controls(
    bars: pd.DataFrame,
    *,
    entry_pos: int,
    sweep_start: int,
    sweep_end: int,
    k: int,
    base_seed: int,
    exemplar_index: int,
) -> tuple[list[ControlAnchor], int]:
    """Returns (chosen anchors, eligible_control_count_before_sampling). Deterministic per seed."""
    pool = eligible_control_positions(
        bars, entry_pos=entry_pos, sweep_start=sweep_start, sweep_end=sweep_end
    )
    rng = random.Random(base_seed + exemplar_index)
    chosen = sorted(rng.sample(pool, min(k, len(pool))))
    anchors = [ControlAnchor(session=bars.index[p].date(), session_pos=p) for p in chosen]
    return anchors, len(pool)


@dataclass(frozen=True)
class ControlScreenResult:
    session: date
    single_session_fired: bool
    window_fired: bool


def screen_control_anchor(
    bars: pd.DataFrame, anchor: ControlAnchor, *, window_back: int, window_fwd: int
) -> ControlScreenResult:
    """Single-session per-anchor fire (PRIMARY estimand) + window best-of fire (reported
    separately, never conflated -- R1.M9). Controls are evaluated day-precision (a calendar date)."""
    single = screen_at(bars, anchor.session).fired
    start = max(0, anchor.session_pos - window_back)
    end = min(len(bars) - 1, anchor.session_pos + window_fwd)
    window = any(screen_at(bars, d.date()).fired for d in bars.index[start : end + 1])
    return ControlScreenResult(
        session=anchor.session, single_session_fired=single, window_fired=window
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_precision_control.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/precision_control.py tests/research/minervini_primary_base_recall/test_precision_control.py
git commit -m "feat(research): primary-base precision control (own pre-filtered young-window sampler + per-anchor screen)"
git log -1 --format='%(trailers)'
```

---

## Task 7: Scorecard (raw fractions first, Wilson, bootstrap, criterion histogram)

**Files:**
- Create: `research/harness/minervini_primary_base_recall/scorecard.py`
- Test: `tests/research/minervini_primary_base_recall/test_scorecard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_scorecard.py
from __future__ import annotations

from research.harness.minervini_primary_base_recall import scorecard as sc


def test_raw_recall_fraction_reported_as_explicit_counts():
    # 2 of 3 sub_floor evaluable fired (sweep): raw fraction FIRST (R1.m4).
    rec = sc.recall_fraction([("amzn", True), ("body", True), ("dks", False)])
    assert rec.successes == 2
    assert rec.n == 3
    assert abs(rec.rate - 2 / 3) < 1e-9


def test_wilson_is_a_mechanical_interval_passthrough():
    w = sc.wilson(2, 3)
    # Reuses the frozen wilson_interval; at n=3 it is a wide mechanical interval, labeled as such.
    assert w.n == 3
    assert 0.0 <= w.lower <= w.p_hat <= w.upper <= 1.0


def test_first_rejection_histogram_counts_misses_by_criterion():
    hist = sc.first_rejection_histogram(
        [("amzn", None), ("dks", "depth"), ("body", "no_emergence"), ("x", "depth")]
    )
    # WRONG-PATH (count fired too) would include a None key; RIGHT-PATH counts only misses.
    assert hist == {"depth": 2, "no_emergence": 1}


def test_precision_contrast_single_session_primary_vs_window_separate():
    # Exemplar single fire vs control single fire-rate is the PRIMARY contrast; window reported
    # separately, NEVER conflated (R1.M9).
    contrast = sc.precision_contrast(
        exemplar_single_fired=True,
        exemplar_window_fired=True,
        control_single_flags=[False, False, True, False],   # 1/4
        control_window_flags=[True, False, True, False],     # 2/4
    )
    assert abs(contrast.control_single_rate - 0.25) < 1e-9
    assert abs(contrast.control_window_rate - 0.50) < 1e-9
    assert contrast.exemplar_single_fired is True
    assert contrast.primary_estimand == "single_session_per_anchor"


def test_precision_contrast_no_controls_is_na_not_zero():
    contrast = sc.precision_contrast(
        exemplar_single_fired=False, exemplar_window_fired=True,
        control_single_flags=[], control_window_flags=[],
    )
    assert contrast.control_single_rate is None   # NA, not 0.0 (spec section 6)
    assert contrast.control_window_rate is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_scorecard.py -q`
Expected: FAIL with `ImportError`/`AttributeError`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_primary_base_recall/scorecard.py
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

# Reuse the FROZEN harness's uncertainty primitives.
from research.harness.minervini_exemplar_recall.scorecard import (
    BootstrapInterval,
    WilsonInterval,
    ticker_clustered_bootstrap,
    wilson_interval,
)


@dataclass(frozen=True)
class RecallFraction:
    successes: int
    n: int
    rate: float
    fired_ids: tuple[str, ...]
    missed_ids: tuple[str, ...]


def recall_fraction(rows: Sequence[tuple[str, bool]]) -> RecallFraction:
    """Raw recall as explicit counts FIRST (R1.m4). rows = (exemplar_id, fired)."""
    fired = tuple(eid for eid, ok in rows if ok)
    missed = tuple(eid for eid, ok in rows if not ok)
    n = len(rows)
    return RecallFraction(len(fired), n, (len(fired) / n if n else 0.0), fired, missed)


def wilson(successes: int, n: int) -> WilsonInterval:
    """A MECHANICAL interval at n~3 (NOT evidence of stable performance) -- labeled in summary.md."""
    return wilson_interval(successes, n)


def bootstrap(rows: Sequence[tuple], *, b: int, base_seed: int) -> BootstrapInterval:
    """Exploratory-only ticker-clustered bootstrap; rows[i][0] MUST be the ticker key."""
    return ticker_clustered_bootstrap(
        rows,
        lambda rs: (sum(1 for r in rs if r[1]) / len(rs)) if rs else 0.0,
        b=b,
        base_seed=base_seed,
    )


def first_rejection_histogram(rows: Sequence[tuple[str, str | None]]) -> dict[str, int]:
    """Per-criterion first-rejection counts across MISSES (criterion is None for a fired row)."""
    return dict(Counter(crit for _eid, crit in rows if crit is not None))


@dataclass(frozen=True)
class PrecisionContrast:
    exemplar_single_fired: bool | None  # None for month-precision rows (sweep-only; no single-session)
    exemplar_window_fired: bool
    control_single_rate: float | None
    control_window_rate: float | None
    primary_estimand: str = "single_session_per_anchor"


def _rate_or_none(flags: Sequence[bool]) -> float | None:
    return (sum(1 for f in flags if f) / len(flags)) if flags else None


def precision_contrast(
    *,
    exemplar_single_fired: bool | None,
    exemplar_window_fired: bool,
    control_single_flags: Sequence[bool],
    control_window_flags: Sequence[bool],
) -> PrecisionContrast:
    return PrecisionContrast(
        exemplar_single_fired=exemplar_single_fired,
        exemplar_window_fired=exemplar_window_fired,
        control_single_rate=_rate_or_none(control_single_flags),
        control_window_rate=_rate_or_none(control_window_flags),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_scorecard.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/scorecard.py tests/research/minervini_primary_base_recall/test_scorecard.py
git commit -m "feat(research): primary-base scorecard (raw fractions first, Wilson, bootstrap, criterion histogram, precision contrast)"
git log -1 --format='%(trailers)'
```

---

## Task 8: Output writers (results/per_session CSV, summary.md, manifest.json; ASCII guard)

**Files:**
- Create: `research/harness/minervini_primary_base_recall/output.py`
- Test: `tests/research/minervini_primary_base_recall/test_output.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_output.py
from __future__ import annotations

import json

import pytest

from research.harness.minervini_primary_base_recall import output


def test_results_csv_has_spec_header_and_rows(tmp_path):
    path = tmp_path / "results.csv"
    output.write_results_csv(
        [
            {
                "exemplar_id": "twosmw-fig11-1-amzn", "ticker": "AMZN", "role": "sub_floor",
                "timing_mode": "window_sweep", "fired": "True", "first_rejecting_criterion": "",
                "base_start_date": "1997-07-01", "base_high": "5.1",
                "correction_depth_pct": "0.23", "base_duration_bars": "30",
                "emergence_close": "5.2", "data_source": "tiingo",
                "bars_through_anchor": "75", "date_precision": "month",
            }
        ],
        path,
    )
    head = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head == list(output.RESULTS_HEADER)
    assert "first_rejecting_criterion" in head


def test_manifest_has_spec_required_fields(tmp_path):
    path = tmp_path / "manifest.json"
    output.write_manifest_json(
        {
            "n_evaluable": 3,
            "per_exemplar": [
                {"exemplar_id": "twosmw-fig11-1-amzn", "bars_through_anchor": 75,
                 "date_precision": "month", "role": "sub_floor",
                 "eligible_control_count_before_sampling": 309},
            ],
            "thresholds": {"MIN_HISTORY_BARS": 40},
            "control_params": {"control_k": 5, "control_seed": 20260608, "max_control_age_bars": 504},
            "started_iso_utc": "20260609T000000Z", "finished_iso_utc": "20260609T000100Z",
        },
        path,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True   # write_manifest_json sets the default
    assert data["per_exemplar"][0]["eligible_control_count_before_sampling"] == 309
    assert data["n_evaluable"] == 3


def test_ascii_guard_rejects_non_ascii(tmp_path):
    # spec section 8 is ASCII-only -- STRICTER than cp1252. An em dash (U+2014) is VALID cp1252 but
    # NOT ASCII; the guard MUST reject it. WRONG-PATH (cp1252 guard) would ACCEPT it and write the
    # file; RIGHT-PATH (ascii guard) raises UnicodeEncodeError. The U+2014 char is built via
    # chr(0x2014) so THIS test source stays ASCII-only too (Codex WP-R2 M3) -- do NOT paste a
    # literal em dash here.
    bad_line = "recall " + chr(0x2014) + " ok"  # contains U+2014 at runtime; ASCII in source
    with pytest.raises(UnicodeEncodeError):
        output.write_summary_md([bad_line], tmp_path / "summary.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_output.py -q`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_primary_base_recall/output.py
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

RESULTS_HEADER = (
    "exemplar_id",
    "ticker",
    "role",
    "timing_mode",
    "fired",
    "first_rejecting_criterion",
    "base_start_date",
    "base_high",
    "correction_depth_pct",
    "base_duration_bars",
    "emergence_close",
    "data_source",
    "bars_through_anchor",
    "date_precision",
)

PER_SESSION_HEADER = (
    "exemplar_id",
    "ticker",
    "timing_mode",
    "session",
    "fired",
    "first_rejecting_criterion",
)


def _assert_ascii(text: str) -> str:
    text.encode("ascii")  # spec section 8: ASCII-only (stricter than cp1252; rejects em dash etc.)
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


def write_summary_md(lines: list[str], path: Path) -> None:
    Path(path).write_text(_assert_ascii("\n".join(lines) + "\n"), encoding="utf-8")


def write_manifest_json(manifest: dict, path: Path) -> None:
    payload = dict(manifest)
    payload.setdefault("l2_lock_preserved", True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(_assert_ascii(text), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_output.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/output.py tests/research/minervini_primary_base_recall/test_output.py
git commit -m "feat(research): primary-base output writers (results/per_session csv, summary.md, manifest.json) with ASCII guard"
git log -1 --format='%(trailers)'
```

---

## Task 9: Orchestrator `run.py` (wires cohort -> timing -> control -> scorecard -> output)

**Files:**
- Create: `research/harness/minervini_primary_base_recall/run.py`
- Test: `tests/research/minervini_primary_base_recall/test_run.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_run.py
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from research.harness.minervini_primary_base_recall.run import run_harness


def _body_firing_closes() -> list[float]:
    """A 57-close series that forms ONE clean primary base emerging on the LAST bar (the entry bar):
    rise to peak 100, a base oscillating below 100 (low ~89), then a developing recovery that
    freshly crosses 100 to 101 on the final bar. base_high stays 100 (the recovery never closes as a
    new pivot). Fires single-session at the last bar AND in the window-sweep."""
    rise = [50.0 + (100.0 - 50.0) * i / 11 for i in range(12)]  # 12 bars, peak 100 at idx 11
    pat = [92.0, 90.0, 93.0, 89.0, 94.0, 90.0, 95.0, 91.0]
    base = [pat[i % len(pat)] for i in range(43)]               # 43 bars, all below 100
    cross = [99.0, 101.0]                                       # fresh cross on the final bar
    return rise + base + cross                                  # 57 closes; emergence at idx 56


def _write_tiingo_csv(tiingo_dir: Path, symbol: str, closes: list[float], start: date) -> None:
    idx = pd.bdate_range(start=start, periods=len(closes))
    df = pd.DataFrame(
        {
            "date": idx,
            "adjOpen": closes, "adjHigh": [c * 1.001 for c in closes],
            "adjLow": [c * 0.999 for c in closes], "adjClose": closes,
            "adjVolume": [1_000_000] * len(closes),
        }
    )
    tiingo_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(tiingo_dir / f"{symbol}.csv", index=False)


def _exemplar_csv(path: Path, rows: list[str]) -> None:
    header = (
        "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
        "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes"
    )
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_run_harness_writes_four_artifacts_and_manifest_fields(tmp_path):
    # Minimal real-shaped run with the 5 curated ids present but synthetic Tiingo bars.
    ex = tmp_path / "ex.csv"
    _exemplar_csv(
        ex,
        [
            "twosmw-fig11-1-amzn,AMZN,pb,unmapped,1997-09,,,,,month,T,p,claude,yes,n",
            "ttlc-fig10-1-body,BODY,pb,vcp,2011-01-05,,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-6-dks,DKS,pb,double_bottom_w,2003-04,,,,,month,T,p,claude,yes,n",
            "twosmw-fig11-7-jnpr,JNPR,pb,unmapped,1999-07-30,,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n",
        ],
    )
    tdir = tmp_path / "tiingo"
    _write_tiingo_csv(tdir, "AMZN", [10.0 + i * 0.01 for i in range(800)], date(1997, 1, 2))
    _write_tiingo_csv(tdir, "BODY", [10.0 + i * 0.01 for i in range(1500)], date(2010, 10, 15))
    _write_tiingo_csv(tdir, "DKS", [10.0 + i * 0.01 for i in range(900)], date(2002, 10, 16))
    _write_tiingo_csv(tdir, "JNPR", [10.0 + i * 0.01 for i in range(30)], date(1999, 6, 25))
    _write_tiingo_csv(tdir, "YHOO", [10.0 + i * 0.01 for i in range(900)], date(1996, 4, 12))

    results, per_session, summary, manifest = run_harness(
        exemplars_csv=ex, tiingo_dir=tdir, output_dir=tmp_path / "out", bootstrap_b=10
    )
    for p in (results, per_session, summary, manifest):
        assert Path(p).exists()
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True
    assert "n_evaluable" in data
    ids = {e["exemplar_id"] for e in data["per_exemplar"]}
    assert ids == {
        "twosmw-fig11-1-amzn", "ttlc-fig10-1-body", "twosmw-fig11-6-dks",
        "twosmw-fig11-7-jnpr", "twosmw-fig11-3-yhoo",
    }
    # JNPR is below the history floor -> history-excluded; manifest records its (short) bar count.
    # (Assert the load-bearing property < 40, not an exact count -- bars_through_anchor is the slice
    # <= entry, which is fewer than the 30-bar archive since it extends a few bars past the entry.)
    jnpr = next(e for e in data["per_exemplar"] if e["exemplar_id"] == "twosmw-fig11-7-jnpr")
    assert jnpr["bars_through_anchor"] < 40
    # Every per-exemplar record carries the eligible_control_count_before_sampling field (R3.m1).
    assert all("eligible_control_count_before_sampling" in e for e in data["per_exemplar"])

    # Codex WP-R1 M1: month-precision exemplars are SWEEP-ONLY -> NO single_session results row.
    rows = list(csv.DictReader(Path(results).read_text(encoding="utf-8").splitlines()))
    month_single = [
        r for r in rows
        if r["exemplar_id"] in {"twosmw-fig11-1-amzn", "twosmw-fig11-6-dks"}
        and r["timing_mode"] == "single_session"
    ]
    assert month_single == [], "month rows must not emit a single_session results row"
    # BODY (day) DOES get both modes.
    body_modes = {r["timing_mode"] for r in rows if r["exemplar_id"] == "ttlc-fig10-1-body"}
    assert body_modes == {"single_session", "window_sweep"}

    # Codex WP-R1 C1/M2/M6: summary carries Precision, Positive-control (YHOO), Below-minimum
    # (JNPR), and the EXPLORATORY bootstrap label.
    summary_text = Path(summary).read_text(encoding="utf-8")
    assert "## Precision" in summary_text
    assert "## Positive control" in summary_text and "twosmw-fig11-3-yhoo" in summary_text
    assert "## Below-minimum" in summary_text and "twosmw-fig11-7-jnpr" in summary_text
    assert "EXPLORATORY" in summary_text  # ticker-clustered bootstrap line


def test_run_planted_body_primary_base_fires_and_wires_recall_precision(tmp_path):
    # Codex WP-R1 minor-3: a planted REAL fire (monotone bars cannot fire). BODY forms a primary
    # base emerging on its entry bar -> fires single-session AND window-sweep; recall picks it up.
    body_closes = _body_firing_closes()
    body_start = date(2010, 10, 15)
    body_idx = pd.bdate_range(start=body_start, periods=len(body_closes))
    body_entry = body_idx[-1].date()  # entry == the emergence bar (the last bar of the archive)

    ex = tmp_path / "ex.csv"
    _exemplar_csv(
        ex,
        [
            "twosmw-fig11-1-amzn,AMZN,pb,unmapped,1997-09,,,,,month,T,p,claude,yes,n",
            f"ttlc-fig10-1-body,BODY,pb,vcp,{body_entry.isoformat()},,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-6-dks,DKS,pb,double_bottom_w,2003-04,,,,,month,T,p,claude,yes,n",
            "twosmw-fig11-7-jnpr,JNPR,pb,unmapped,1999-07-30,,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n",
        ],
    )
    tdir = tmp_path / "tiingo"
    _write_tiingo_csv(tdir, "AMZN", [10.0 + i * 0.01 for i in range(800)], date(1997, 1, 2))
    _write_tiingo_csv(tdir, "BODY", body_closes, body_start)
    _write_tiingo_csv(tdir, "DKS", [10.0 + i * 0.01 for i in range(900)], date(2002, 10, 16))
    _write_tiingo_csv(tdir, "JNPR", [10.0 + i * 0.01 for i in range(30)], date(1999, 6, 25))
    _write_tiingo_csv(tdir, "YHOO", [10.0 + i * 0.01 for i in range(900)], date(1996, 4, 12))

    results, _ps, summary, _m = run_harness(
        exemplars_csv=ex, tiingo_dir=tdir, output_dir=tmp_path / "out", bootstrap_b=10
    )
    rows = list(csv.DictReader(Path(results).read_text(encoding="utf-8").splitlines()))
    body = {r["timing_mode"]: r for r in rows if r["exemplar_id"] == "ttlc-fig10-1-body"}
    assert body["window_sweep"]["fired"] == "True"
    assert body["single_session"]["fired"] == "True"
    # BODY shows up in the sub-floor sweep recall fired list.
    assert "ttlc-fig10-1-body" in Path(summary).read_text(encoding="utf-8")


def test_run_harness_raises_value_error_for_missing_csv(tmp_path):
    with pytest.raises(ValueError):
        run_harness(exemplars_csv=tmp_path / "nope.csv", tiingo_dir=tmp_path, output_dir=tmp_path / "o")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_run.py -q`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# research/harness/minervini_primary_base_recall/run.py
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from research.harness.minervini_exemplar_recall.ohlcv_reader import read_full, slice_to
from research.harness.minervini_exemplar_recall.exceptions import TiingoArchiveMissingError

from . import output, precision_control, scorecard, timing
from .cohort import resolve_cohort
from .constants import (
    CONTROL_K,
    DEFAULT_CONTROL_SEED,
    MAX_CONTROL_AGE_BARS,
    MIN_BASE_BARS,
    MIN_HISTORY_BARS,
    WINDOW_BACK,
    WINDOW_FWD,
    YOUNG_NAME_CEILING_BARS,
    ZIGZAG_THRESHOLD_PCT,
    depth_cap,
)


def _load_full_safe(symbol: str, tiingo_dir: Path):
    try:
        return read_full(symbol, tiingo_dir=tiingo_dir)
    except TiingoArchiveMissingError:
        return None


def _entry_pos(bars, entry_anchor) -> int | None:
    mask = bars.index.date >= entry_anchor
    return int(mask.argmax()) if mask.any() else None


def run_harness(
    *,
    exemplars_csv: Path,
    tiingo_dir: Path,
    output_dir: Path,
    window_back: int = WINDOW_BACK,
    window_fwd: int = WINDOW_FWD,
    control_k: int = CONTROL_K,
    bootstrap_b: int = 2000,
    only: tuple[str, ...] | None = None,
) -> tuple[Path, Path, Path, Path]:
    exemplars_csv = Path(exemplars_csv)
    if not exemplars_csv.exists():
        raise ValueError(f"exemplars CSV not found: {exemplars_csv}")
    resolved = resolve_cohort(exemplars_csv)
    if only:
        wanted = set(only)
        resolved = [r for r in resolved if r.member.exemplar_id in wanted]

    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_dir) / f"primary-base-recall-{iso}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results_rows: list[dict] = []
    per_session_rows: list[dict] = []
    per_exemplar: list[dict] = []
    # recall rows: (exemplar_id, fired), only over sub_floor evaluable members (bars >= MIN_HISTORY).
    sweep_recall_rows: list[tuple[str, bool]] = []
    # bootstrap rows are keyed by TICKER (row[0]) per the frozen ticker_clustered_bootstrap contract,
    # kept SEPARATE from the exemplar_id-keyed recall display rows (Codex WP-R2 M2).
    sweep_bootstrap_rows: list[tuple[str, bool]] = []
    single_recall_rows: list[tuple[str, bool]] = []
    sweep_miss_rows: list[tuple[str, str | None]] = []
    # stratified diagnostics + precision (Codex WP-R1 C1/M2/M6).
    precision_rows: list[dict] = []
    positive_control_rows: list[tuple[str, bool, str]] = []  # (exemplar_id, sweep_fired, first_reject)
    history_excluded_rows: list[tuple[str, int]] = []        # (exemplar_id, bars_through_anchor)

    for idx, rm in enumerate(resolved):
        row = rm.row
        symbol = row.tiingo_symbol   # populated by read_exemplars (Codex WP-R1 M5: no tiingo_symbol import)
        full = _load_full_safe(symbol, Path(tiingo_dir))
        data_source = "tiingo" if full is not None else "no_data"
        bars_through_anchor = (
            len(slice_to(full, row.entry_anchor)) if full is not None else 0
        )
        eligible_count = 0

        modes: dict[str, timing.TimingResult] = {}
        if full is not None:
            modes = timing.evaluate_exemplar(
                full, row.entry_anchor, row.date_precision,
                window_back=window_back, window_fwd=window_fwd,
            )

        # Emit single_session rows ONLY for day/exact precision; month rows are SWEEP-ONLY (Codex
        # WP-R1 M1 -- never ship a misleading single_session fired=False row for AMZN/DKS).
        emit_modes = (
            ("single_session", "window_sweep")
            if row.date_precision in ("day", "exact")
            else ("window_sweep",)
        )
        for mode in emit_modes:
            res = modes.get(mode)
            fired = bool(res.fired) if res else False
            # The verdict at the best (firing, else last) session for diagnostics.
            best = None
            if res and res.sessions:
                best = next((s for s in res.sessions if s.verdict.fired), res.sessions[-1])
            v = best.verdict if best else None
            results_rows.append({
                "exemplar_id": row.exemplar_id, "ticker": row.ticker, "role": rm.member.role,
                "timing_mode": mode, "fired": str(fired),
                "first_rejecting_criterion": (v.first_rejecting_criterion if v else "") or "",
                "base_start_date": (v.base_start_date.isoformat() if v and v.base_start_date else ""),
                "base_high": (f"{v.base_high:.4f}" if v and v.base_high is not None else ""),
                "correction_depth_pct": (
                    f"{v.correction_depth_pct:.4f}" if v and v.correction_depth_pct is not None else ""
                ),
                "base_duration_bars": (str(v.base_duration_bars) if v and v.base_duration_bars is not None else ""),
                "emergence_close": (f"{v.emergence_close:.4f}" if v and v.emergence_close is not None else ""),
                "data_source": data_source,
                "bars_through_anchor": str(bars_through_anchor),
                "date_precision": row.date_precision,
            })
            if res:
                for se in res.sessions:
                    per_session_rows.append({
                        "exemplar_id": row.exemplar_id, "ticker": row.ticker, "timing_mode": mode,
                        "session": se.session.isoformat(), "fired": str(se.verdict.fired),
                        "first_rejecting_criterion": se.verdict.first_rejecting_criterion or "",
                    })

        # Recall denominators: sub_floor evaluable (bars >= MIN_HISTORY_BARS) only.
        evaluable = rm.member.role == "sub_floor" and bars_through_anchor >= MIN_HISTORY_BARS
        if evaluable:
            sweep = modes.get("window_sweep")
            sweep_fired = bool(sweep.fired) if sweep else False
            sweep_recall_rows.append((row.exemplar_id, sweep_fired))
            sweep_bootstrap_rows.append((row.ticker, sweep_fired))  # ticker-keyed (WP-R2 M2)
            # first_rejecting at the best sweep session (None if fired).
            if sweep and sweep.sessions:
                best = next((s for s in sweep.sessions if s.verdict.fired), sweep.sessions[-1])
                sweep_miss_rows.append((row.exemplar_id, best.verdict.first_rejecting_criterion))
            # Single-session recall ONLY for day-precision evaluable (BODY-only, n=1).
            if row.date_precision in ("day", "exact"):
                single = modes.get("single_session")
                single_recall_rows.append((row.exemplar_id, bool(single.fired) if single else False))
        # YHOO positive control reported separately (Codex WP-R1 M2).
        if rm.member.role == "positive_control":
            sweep = modes.get("window_sweep")
            pc_fired = bool(sweep.fired) if sweep else False
            pc_reject = ""
            if sweep and sweep.sessions and not pc_fired:
                pc_reject = sweep.sessions[-1].verdict.first_rejecting_criterion or ""
            positive_control_rows.append((row.exemplar_id, pc_fired, pc_reject))
        # JNPR-style history-exclusion reported separately (Codex WP-R1 M2): a sub_floor name below
        # the history floor is NOT a screen miss -- it is below Minervini's own >=2-month minimum.
        if rm.member.role == "sub_floor" and bars_through_anchor < MIN_HISTORY_BARS:
            history_excluded_rows.append((row.exemplar_id, bars_through_anchor))

        # Precision controls (own pre-filtered young-window sampler) -- PERSISTED + scored (C1).
        control_single_flags: list[bool] = []
        control_window_flags: list[bool] = []
        if full is not None:
            entry_pos = _entry_pos(full, row.entry_anchor)
            bounds = timing.sweep_bounds(
                full, row.entry_anchor, row.date_precision,
                window_back=window_back, window_fwd=window_fwd,
            )
            if entry_pos is not None and bounds is not None:
                anchors, eligible_count = precision_control.sample_young_controls(
                    full, entry_pos=entry_pos, sweep_start=bounds[0], sweep_end=bounds[1],
                    k=control_k, base_seed=DEFAULT_CONTROL_SEED, exemplar_index=idx,
                )
                for a in anchors:
                    cres = precision_control.screen_control_anchor(
                        full, a, window_back=window_back, window_fwd=window_fwd
                    )
                    control_single_flags.append(cres.single_session_fired)
                    control_window_flags.append(cres.window_fired)
        # Exemplar side of the contrast: single-session is meaningful ONLY for day/exact rows (None
        # for month -> sweep-only). window best-of applies to all rows.
        ex_single_fired = (
            bool(modes["single_session"].fired)
            if (row.date_precision in ("day", "exact") and "single_session" in modes)
            else None
        )
        ex_window_fired = bool(modes["window_sweep"].fired) if "window_sweep" in modes else False
        precision_rows.append({
            "exemplar_id": row.exemplar_id, "role": rm.member.role,
            "eligible_control_count": eligible_count, "k_controls": len(control_single_flags),
            "contrast": scorecard.precision_contrast(
                exemplar_single_fired=ex_single_fired, exemplar_window_fired=ex_window_fired,
                control_single_flags=control_single_flags, control_window_flags=control_window_flags,
            ),
        })

        per_exemplar.append({
            "exemplar_id": row.exemplar_id, "ticker": row.ticker, "role": rm.member.role,
            "date_precision": row.date_precision, "bars_through_anchor": bars_through_anchor,
            "data_source": data_source,
            "eligible_control_count_before_sampling": eligible_count,
            "book_citation": rm.member.book_citation,
        })

    n_evaluable = sum(
        1 for e in per_exemplar
        if e["role"] == "sub_floor" and e["bars_through_anchor"] >= MIN_HISTORY_BARS
    )
    finished_iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    results_path = run_dir / "results.csv"
    per_session_path = run_dir / "per_session.csv"
    summary_path = run_dir / "summary.md"
    manifest_path = run_dir / "manifest.json"

    output.write_results_csv(results_rows, results_path)
    output.write_per_session_csv(per_session_rows, per_session_path)
    output.write_summary_md(
        _summary_lines(
            sweep_recall_rows, sweep_bootstrap_rows, single_recall_rows, sweep_miss_rows,
            positive_control_rows, history_excluded_rows, precision_rows, bootstrap_b,
        ),
        summary_path,
    )
    output.write_manifest_json(
        {
            "harness_version": "0.1.0",
            "n_total": len(resolved),
            "n_evaluable": n_evaluable,
            "only_filter": list(only) if only else None,
            "per_exemplar": per_exemplar,
            "thresholds": {
                "MIN_HISTORY_BARS": MIN_HISTORY_BARS, "MIN_BASE_BARS": MIN_BASE_BARS,
                "ZIGZAG_THRESHOLD_PCT": ZIGZAG_THRESHOLD_PCT,
                "YOUNG_NAME_CEILING_BARS": YOUNG_NAME_CEILING_BARS,
                "depth_caps": {"<=25": depth_cap(25), "26-200": depth_cap(26), ">200": depth_cap(201)},
            },
            "control_params": {
                "control_k": control_k, "control_seed": DEFAULT_CONTROL_SEED,
                "max_control_age_bars": MAX_CONTROL_AGE_BARS,
                "window_back": window_back, "window_fwd": window_fwd,
            },
            "bootstrap_b": bootstrap_b,
            "started_iso_utc": iso, "finished_iso_utc": finished_iso,
            "l2_lock_preserved": True,
        },
        manifest_path,
    )
    return results_path, per_session_path, summary_path, manifest_path


def _summary_lines(
    sweep_rows, sweep_bootstrap_rows, single_rows, miss_rows, positive_control_rows,
    history_excluded_rows, precision_rows, bootstrap_b,
) -> list[str]:
    lines = ["# Minervini primary-base recall - summary", ""]
    lines.append("NOTE: n~3 proof-of-concept. Raw fractions are PRIMARY; Wilson + bootstrap are")
    lines.append("MECHANICAL/EXPLORATORY at this n, NOT evidence of stable performance. Precision is a")
    lines.append("same-ticker temporal-specificity contrast, NOT a population base rate.")
    lines.append("")
    lines.append("## Recall (sub-floor evaluable {AMZN-1997, BODY, DKS})")
    sweep = scorecard.recall_fraction(sweep_rows)
    lines.append(
        f"sub-floor sweep recall (RAW): {sweep.successes}/{sweep.n} "
        f"(fired: {';'.join(sweep.fired_ids) or '-'}; missed: {';'.join(sweep.missed_ids) or '-'})"
    )
    w = scorecard.wilson(sweep.successes, sweep.n)
    lines.append(f"  Wilson 95pct (MECHANICAL at n={w.n}): [{w.lower:.3f}, {w.upper:.3f}]")
    # Exploratory ticker-clustered bootstrap (Codex WP-R1 M6) over the TICKER-keyed rows (WP-R2 M2).
    # Guard the zero-row case (WP-R2 M1): emit NA rather than a meaningless [0.000, 0.000] interval
    # (the frozen primitive does not crash on empty input -- the resampler's comprehension is empty --
    # but a degenerate interval would mislead). The empty path is exercised by the CLI no-Tiingo test.
    if sweep.n == 0:
        lines.append("  ticker-clustered bootstrap (EXPLORATORY): NA (no evaluable rows)")
    else:
        boot = scorecard.bootstrap(sweep_bootstrap_rows, b=bootstrap_b, base_seed=DEFAULT_CONTROL_SEED)
        lines.append(
            f"  ticker-clustered bootstrap 95pct (EXPLORATORY): [{boot.lower:.3f}, {boot.upper:.3f}]"
        )
    single = scorecard.recall_fraction(single_rows)
    lines.append(
        f"day-precision single-session recall (RAW, BODY-only n={single.n}): "
        f"{single.successes}/{single.n} -- single yes/no, NO interval"
    )
    hist = scorecard.first_rejection_histogram(miss_rows)
    lines.append(f"sweep first-rejecting-criterion histogram: {hist}")
    lines.append("")
    lines.append("## Positive control (YHOO -- sufficient-history documented primary base)")
    if positive_control_rows:
        for eid, fired, reject in positive_control_rows:
            tail = "" if fired else f" (first_rejecting_criterion={reject or '-'})"
            lines.append(f"- {eid}: window-sweep fired={fired}{tail}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Below-minimum (reported, NOT a screen miss -- below Minervini's >=2-month floor)")
    if history_excluded_rows:
        for eid, bars in history_excluded_rows:
            lines.append(f"- {eid}: history-excluded ({bars} bars < MIN_HISTORY_BARS)")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Precision (same-ticker young-window control; single-session per-anchor PRIMARY)")
    for pr in precision_rows:
        c = pr["contrast"]
        single_rate = "NA" if c.control_single_rate is None else f"{c.control_single_rate:.3f}"
        window_rate = "NA" if c.control_window_rate is None else f"{c.control_window_rate:.3f}"
        lines.append(
            f"- {pr['exemplar_id']} ({pr['role']}): control single-session per-anchor fire "
            f"(PRIMARY)={single_rate}; window best-of (SEPARATE)={window_rate}; "
            f"k={pr['k_controls']}, eligible_before_sampling={pr['eligible_control_count']}; "
            f"exemplar single={c.exemplar_single_fired} window={c.exemplar_window_fired}"
        )
    lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="primary-base-recall")
    p.add_argument("--exemplars-csv", type=Path, required=True)
    p.add_argument("--tiingo-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("exports/research"))
    p.add_argument("--window-back", type=int, default=WINDOW_BACK)
    p.add_argument("--window-fwd", type=int, default=WINDOW_FWD)
    p.add_argument("--control-k", type=int, default=CONTROL_K)
    p.add_argument("--bootstrap-b", type=int, default=2000)
    p.add_argument("--only", type=str, default=None)
    args = p.parse_args(argv)
    only = tuple(s.strip() for s in args.only.split(",") if s.strip()) if args.only else None
    try:
        results, per_session, summary, manifest = run_harness(
            exemplars_csv=args.exemplars_csv, tiingo_dir=args.tiingo_dir, output_dir=args.output_dir,
            window_back=args.window_back, window_fwd=args.window_fwd, control_k=args.control_k,
            bootstrap_b=args.bootstrap_b, only=only,
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_run.py -q`
Expected: PASS (3 passed). The first test uses monotone bars (no fire) but asserts artifacts + manifest fields + the month-row single-session omission + the summary's Precision / Positive-control / Below-minimum / EXPLORATORY sections; the second test plants a real BODY fire and asserts the recall+precision wiring carries it; the third asserts the missing-CSV `ValueError`.

- [ ] **Step 5: Commit**

```bash
git add research/harness/minervini_primary_base_recall/run.py tests/research/minervini_primary_base_recall/test_run.py
git commit -m "feat(research): primary-base run orchestrator (cohort -> timing -> control -> scorecard -> output)"
git log -1 --format='%(trailers)'
```

---

## Task 10: L2-LOCK test (hardened, monkeypatch-restored sys.modules) + gitignore allowlist

**Files:**
- Create: `tests/research/minervini_primary_base_recall/test_l2_lock.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_l2_lock.py
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import research.harness.minervini_primary_base_recall as pkg

_FORBIDDEN = (
    "yfinance",
    "schwabdev",
    "swing.integrations.schwab",
    "swing.data.ohlcv_archive",
)

_EVALUATOR_MODULES = (
    "constants", "exceptions", "primary_base_screen", "cohort", "timing",
    "precision_control", "scorecard", "output", "run",
)


class _NoImportSentinel:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, item):
        raise AssertionError(f"L2 LOCK violated: forbidden module {self._name!r} was imported")


def test_evaluator_modules_do_not_import_forbidden(monkeypatch):
    # HARDENED pattern (per the 2026-06-09 xdist module-identity gotcha): use monkeypatch.delitem /
    # setitem so sys.modules is RESTORED at teardown -- NEVER raw `del sys.modules[...]` (which leaks
    # deletions across xdist workers and makes sibling identity tests order-fragile).
    for name in list(sys.modules):
        if name.startswith("research.harness.minervini_primary_base_recall") or name in _FORBIDDEN:
            monkeypatch.delitem(sys.modules, name, raising=False)
    for forbidden in _FORBIDDEN:
        monkeypatch.setitem(sys.modules, forbidden, _NoImportSentinel(forbidden))
    for mod in _EVALUATOR_MODULES:
        importlib.import_module(f"research.harness.minervini_primary_base_recall.{mod}")
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

- [ ] **Step 2: Run test to verify it fails (then passes once isolation is confirmed)**

Run with xdist DISABLED via `-n 0` to reproduce any isolation issue deterministically (per the gotcha: reproduce with `-n 0`, NOT `-n auto`; `-n 0` runs in-process so a `sys.modules` leak is observable, and the hardened monkeypatch-restored pattern keeps it from leaking in the first place):

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_l2_lock.py -q -n 0`
Expected: PASS (2 passed) -- the screen + harness import none of the forbidden modules. If it FAILS, the failure message names the offending module + import line; fix the source so the evaluator graph stays clean (this is the lock doing its job), then re-run.

- [ ] **Step 3: Add the gitignore allowlist (mirror the minervini-exemplar-recall block)**

Add to `.gitignore` immediately after the existing `minervini-exemplar-recall-*` allowlist block:

```gitignore
# Minervini primary-base-recall harness outputs: keep the small summary/manifest/results.
!exports/research/primary-base-recall-*
exports/research/primary-base-recall-*/*
!exports/research/primary-base-recall-*/summary.md
!exports/research/primary-base-recall-*/manifest.json
!exports/research/primary-base-recall-*/results.csv
!exports/research/primary-base-recall-*/per_session.csv
```

- [ ] **Step 4: Run the full new-package suite (with xdist, as CI runs it)**

Run: `python -m pytest tests/research/minervini_primary_base_recall/ -q`
Expected: PASS (all tasks 1-10 green together). If a flake appears ONLY under `-n auto`, reproduce with `-n 0` + explicit ordering (do NOT chase it by re-running `-n auto`).

- [ ] **Step 5: Commit**

```bash
git add tests/research/minervini_primary_base_recall/test_l2_lock.py .gitignore
git commit -m "test(research): primary-base L2 lock (hardened sys.modules) + gitignore output allowlist"
git log -1 --format='%(trailers)'
```

---

## Task 11: CLI registration (`swing diagnose primary-base-recall`) -- the ONE swing/ change

**Files:**
- Modify: `swing/cli.py` (add one `@diagnose_group.command` immediately after `diagnose_minervini_recall`, before `pattern-cohort-detect`)
- Test: `tests/research/minervini_primary_base_recall/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_cli.py
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main


def _exemplar_csv(path: Path) -> None:
    header = (
        "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
        "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes"
    )
    rows = [
        "twosmw-fig11-1-amzn,AMZN,pb,unmapped,1997-09,,,,,month,T,p,claude,yes,n",
        "ttlc-fig10-1-body,BODY,pb,vcp,2011-01-05,,,,,day,T,p,claude,yes,n",
        "twosmw-fig11-6-dks,DKS,pb,double_bottom_w,2003-04,,,,,month,T,p,claude,yes,n",
        "twosmw-fig11-7-jnpr,JNPR,pb,unmapped,1999-07-30,,,,,day,T,p,claude,yes,n",
        "twosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n",
    ]
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_value_error_becomes_click_exception(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["diagnose", "primary-base-recall", "--exemplars-csv", str(tmp_path / "nope.csv"),
         "--tiingo-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "Traceback" not in result.output


def test_command_is_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "primary-base-recall", "--help"])
    assert result.exit_code == 0
    assert "--exemplars-csv" in result.output
    assert "--tiingo-dir" in result.output
    # No --db flag (pure on bars).
    assert "--db" not in result.output


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="powershell.exe not available")
def test_cli_stdout_is_ascii_through_powershell(tmp_path):
    # Exercise the REAL OS encoder (capsys bypasses cp1252; this is the gotcha guard).
    ex = tmp_path / "ex.csv"
    _exemplar_csv(ex)
    out = tmp_path / "out"
    cmd = (
        f"{sys.executable} -m research.harness.minervini_primary_base_recall.run "
        f"--exemplars-csv {ex} --tiingo-dir {tmp_path} --output-dir {out}"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[3]),
    )
    assert "UnicodeEncodeError" not in proc.stderr
    assert proc.returncode == 0, proc.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_cli.py -q`
Expected: FAIL -- `test_command_is_registered` exits non-zero ("No such command 'primary-base-recall'").

- [ ] **Step 3: Write minimal implementation**

In `swing/cli.py`, immediately AFTER the `diagnose_minervini_recall` function (ends at the current line ~4929) and BEFORE `@diagnose_group.command("pattern-cohort-detect")`, add:

```python
@diagnose_group.command("primary-base-recall")
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
@click.option("--only", type=str, default=None, help="Comma-separated exemplar_id filter.")
def diagnose_primary_base_recall(exemplars_csv, tiingo_dir, output_dir, window_back, window_fwd,
                                 control_k, bootstrap_b, only):
    """Minervini Ch.11 primary-base (young-name) screen recall/precision harness.

    No --db: the screen is pure on bars (no equity, no stage)."""
    from research.harness.minervini_primary_base_recall.run import run_harness  # deferred import

    only_tuple = tuple(s.strip() for s in only.split(",") if s.strip()) if only else None
    try:
        results, per_session, summary, manifest = run_harness(
            exemplars_csv=exemplars_csv, tiingo_dir=tiingo_dir, output_dir=output_dir,
            window_back=window_back, window_fwd=window_fwd, control_k=control_k,
            bootstrap_b=bootstrap_b, only=only_tuple,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"results.csv:     {results}")
    click.echo(f"summary.md:      {summary}")
    click.echo(f"manifest.json:   {manifest}")
```

(Confirm `from pathlib import Path` and `import click` are already imported at the top of `swing/cli.py` -- they are, used by `diagnose_minervini_recall`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_cli.py -q`
Expected: PASS (3 passed; powershell test runs on Windows).

- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/research/minervini_primary_base_recall/test_cli.py
git commit -m "feat(cli): register swing diagnose primary-base-recall (the single swing/ change for the arc)"
git log -1 --format='%(trailers)'
```

---

## Task 12: Method-record stub

**Files:**
- Create: `research/method-records/minervini-primary-base-recall.md`
- Test: `tests/research/minervini_primary_base_recall/test_method_record.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_method_record.py
from __future__ import annotations

from pathlib import Path

_MR = Path("research/method-records/minervini-primary-base-recall.md")


def test_method_record_exists_with_required_frontmatter():
    assert _MR.exists()
    text = _MR.read_text(encoding="utf-8")
    for token in (
        "key: minervini-primary-base-recall",
        "name:",
        "layer:",
        "status:",
        "version:",
    ):
        assert token in text, f"method record missing {token!r}"
    # Ch.11 grounding + L2 lock anti-promotion guard must be named.
    assert "Ch.11" in text or "Chapter 11" in text
    assert "l2_lock_preserved" in text or "L2 LOCK" in text
    # ASCII-only (spec section 8; stricter than cp1252 -- Codex WP-R2 minor 2).
    text.encode("ascii")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_method_record.py -q`
Expected: FAIL (file absent).

- [ ] **Step 3: Write minimal implementation**

```markdown
<!-- research/method-records/minervini-primary-base-recall.md -->
---
key: minervini-primary-base-recall
name: Minervini primary-base (young-name) screen recall
layer: monitoring
status: research
baseline_or_predecessor: minervini-exemplar-recall
version: 0.1.0
last_updated: 2026-06-09
---

# Minervini primary-base (young-name) screen recall

## Definition
Point-in-time true-positive recall + same-ticker temporal-specificity precision test for a Minervini
TWoSMW Ch.11 PRIMARY-BASE screen over young (sub-221-bar) post-IPO names that the original
Trend-Template recall study could not evaluate. For each curated documented-primary-base exemplar,
`screen_at(bars, asof)` asks whether all six Ch.11 criteria hold (history >= ~2mo; a >= ~3wk base by
zigzag swing-high pivot; graduated correction-depth cap by base duration in bars; a FRESH cross to new
high ground, not a recross; and primary = the FIRST base via a first-fire replay), strictly
point-in-time (no lookahead). internal (grounded in TWoSMW Ch.11).

## Inputs
- Curated primary-base cohort (5 ids from research/data/minervini-exemplars.csv; AMZN-1997, BODY, DKS,
  JNPR, YHOO). MELI excluded (young-VCP). Roles: sub_floor vs positive_control.
- Tiingo adjusted daily OHLCV (research/data/tiingo/<symbol>.csv), backward-looking <= asof slice.

## Parameters
- MIN_HISTORY_BARS=40; MIN_BASE_BARS=15; ZIGZAG_THRESHOLD_PCT=3.0; graduated depth caps
  (<=25 bars 0.25 / 26-200 0.35 / >200 0.50); window_back=60, window_fwd=5; control_k=5;
  MAX_CONTROL_AGE_BARS=504; CONTROL_GAP_BARS=120; YOUNG_NAME_CEILING_BARS=221; bootstrap_b=2000.

## Outputs
- results.csv / per_session.csv / summary.md / manifest.json under
  exports/research/primary-base-recall-<ISO>/. Raw recall fractions (sub-floor sweep; day-precision
  single-session BODY-only n=1) FIRST; Wilson as a mechanical interval at n~3; per-criterion
  first-rejection histogram; same-ticker young-window precision contrast (single-session per-anchor
  primary estimand, window best-of reported separately, never conflated); per-exemplar bar count,
  date_precision, eligible_control_count_before_sampling.

## Operator explainability
- One-sentence rationale: confirms a Ch.11 primary-base screen would surface Minervini's documented
  young-name entries the Trend-Template screen structurally cannot evaluate, without firing on random
  young-window dates of the same names.
- One-paragraph explanation: The harness replays a point-in-time Ch.11 primary-base screen against
  each documented young-name primary base, both at the single documented session (day-precision only)
  and across a base window (full documented month for month-precision anchors), and contrasts the
  emergence fire against random young-window same-ticker controls drawn from a pre-filtered
  first-~2-years pool. It is a mechanism-validation proof-of-concept (n~3 evaluable), not a powered
  study; raw fractions are primary and intervals are mechanical.
- FAQ: Why n~3? Codex R1 tightened the cohort (MELI removed as a young-VCP; JNPR history-excluded
  below Minervini's own >=2-month floor). Corpus expansion is the strongly-advised sequel.

## Promotion criteria
### Research -> shadow
1. The harness runs end-to-end on the curated cohort with the live Tiingo archive; the manifest
   records l2_lock_preserved == true; the study Results/Interpretation/Conclusion are populated from a
   real run.
2. Recall point estimates are stable across two independent archive pulls (archive-mutation
   sensitivity characterized, #24/#26).
### Shadow -> production
1. Not applicable: this is a monitoring/diagnostic recall test, not a deployable gate. Any deployable
   young-name screen routes through the V2.1 section VII.F source-of-truth correction protocol.
### Anti-promotion guards
1. L2 LOCK upheld (manifest l2_lock_preserved == true; no yfinance/schwabdev/schwab/ohlcv_archive in
   the evaluator import graph).
2. ZERO production swing/ writes beyond the single CLI registration.
3. Any deployable finding routes through V2.1 section VII.F, never a direct patch.

## Limitations
L1..L7 per spec section 10 (tiny n~3 proof-of-concept; thresholds are operationalizations of Ch.11
prose; same-ticker control only; #24/#26 archive temporal mutation; research-only; zigzag
parameterization + constructive-consolidation-near-ATH gap; single-session vs window estimand
separation).

## Validation notes
[grows as status advances]

## Changelog
- 2026-06-09 - v0.1.0 - initial record (harness shipped; awaiting operator smoke run).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_method_record.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add research/method-records/minervini-primary-base-recall.md tests/research/minervini_primary_base_recall/test_method_record.py
git commit -m "docs(research): primary-base-recall method-record stub"
git log -1 --format='%(trailers)'
```

---

## Task 13: Study-design doc (placeholder Results pending operator run)

**Files:**
- Create: `research/studies/2026-06-09-minervini-primary-base-recall.md`
- Test: `tests/research/minervini_primary_base_recall/test_study_doc.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/research/minervini_primary_base_recall/test_study_doc.py
from __future__ import annotations

from pathlib import Path

_STUDY = Path("research/studies/2026-06-09-minervini-primary-base-recall.md")


def test_study_doc_exists_with_required_sections():
    assert _STUDY.exists()
    text = _STUDY.read_text(encoding="utf-8")
    for heading in (
        "## Question",
        "## Null hypothesis",
        "## Methodology",
        "## Results",
        "## Limitations",
        "## Conclusion",
    ):
        assert heading in text, f"study missing {heading!r}"
    assert "../method-records/minervini-primary-base-recall.md" in text
    # n~3 proof-of-concept framing + corpus-expansion-advised must be explicit.
    assert "proof-of-concept" in text
    text.encode("ascii")  # ASCII-only (spec section 8; stricter than cp1252 -- Codex WP-R2 minor 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_study_doc.py -q`
Expected: FAIL (file absent).

- [ ] **Step 3: Write minimal implementation**

```markdown
<!-- research/studies/2026-06-09-minervini-primary-base-recall.md -->
# Minervini primary-base (young-name) screen recall (2026-06-09)

**Method record:** ../method-records/minervini-primary-base-recall.md
**Status:** SHIPPED - awaiting operator smoke run (Results/Interpretation/Conclusion are placeholders).
**Target duration:** per V2.1 SIII.7 time budget.

## Question
Does a point-in-time Minervini Ch.11 PRIMARY-BASE screen surface (recall) the documented young-name
primary-base emergences that the Trend-Template recall study found structurally un-screenable
(< ~221 bars, newly public), while staying selective (precision) against random young-window same-
ticker dates? A pass = the screen catches the documented primary-base emergences without firing
indiscriminately.

## Null hypothesis
H0: the primary-base screen fires at the documented emergence no more frequently than at random
young-window same-ticker control dates (the temporal-specificity contrast). Descriptive; no
inferential test claimed (n~3 proof-of-concept).

## Baseline
Descriptive recall (raw fractions first) + per-criterion first-rejection attribution + same-ticker
young-window precision contrast (single-session per-anchor primary estimand; window best-of separate).

## Methodology
- Harness: research/harness/minervini_primary_base_recall/ (Approach A; new sibling over the FROZEN
  minervini_exemplar_recall leaves + swing.patterns.foundation zigzag).
- CLI: swing diagnose primary-base-recall (no --db; pure on bars).
- Screen (screen_at): Ch.11 criteria 1-6 -- history (>=40 bars); base id via extract_zigzag_swings
  (3% threshold) with calendar->bar mapping; duration (>=15 bars); graduated depth cap by base
  duration in bars; fresh-cross-not-recross emergence; primary = first base via first-fire replay.
- Cohort: {AMZN-1997, BODY, DKS} evaluable sub-floor (n=3) + YHOO positive control + JNPR
  history-excluded (25 bars < 40, below Minervini's own >=2mo floor). MELI excluded (young-VCP).
- Timing: window-sweep reliable for ALL rows (day/exact uses [entry-60bd, entry+5bd]; month uses the
  full documented calendar month + slack); single-session reported ONLY for day-precision (BODY-only,
  n=1).
- Precision: own pre-filtered young-window control sampler ([39,503] BEFORE sampling, then >=120 from
  entry + outside the sweep window + deterministic seed; k=5).
- Uncertainty: raw fractions FIRST; Wilson labeled a mechanical interval at n~3; ticker-clustered
  bootstrap exploratory-only.

## Results
[PLACEHOLDER - populate from exports/research/primary-base-recall-<ISO>/summary.md after the operator
smoke run. Report: sub-floor sweep recall RAW fraction (x/3) + the fired/missed ids; day-precision
single-session BODY-only yes/no; YHOO positive-control fire; JNPR history-exclusion note; per-
criterion first-rejection histogram; same-ticker precision contrast (single-session per-anchor vs
window best-of, never conflated); per-exemplar bar counts + eligible_control_count_before_sampling.]

## Interpretation
[PLACEHOLDER - populate after the run.]

## Limitations
L1..L7 per the method record / spec section 10 (tiny n~3 proof-of-concept; thresholds are
operationalizations of Ch.11 prose; same-ticker control only; #24/#26 archive temporal mutation;
research-only -> V2.1 SVII.F; zigzag parameterization + constructive-consolidation-near-ATH V1 gap;
single-session vs window estimand separation).

## Conclusion
[PLACEHOLDER - populate after the run. Expected framing: mechanism-validation proof-of-concept, NOT a
deployable ruleset change (V2.1 SIV.D promotion gate N/A); corpus expansion
(Google/Starbucks/Reebok/MSFT/Intel/Rambus/RIMM Ch.11 primary bases) is the strongly-advised
immediate sequel.]

## Amendments
- 2026-06-09: shipped with placeholder Results/Interpretation/Conclusion pending the operator run.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/minervini_primary_base_recall/test_study_doc.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add research/studies/2026-06-09-minervini-primary-base-recall.md tests/research/minervini_primary_base_recall/test_study_doc.py
git commit -m "docs(research): primary-base-recall study-design doc (placeholder results pending operator run)"
git log -1 --format='%(trailers)'
```

---

## Task 14: Full-suite verification + ruff

**Files:** none (verification only).

- [ ] **Step 1: Run ruff on the new package + the touched CLI**

Run: `ruff check research/harness/minervini_primary_base_recall/ swing/cli.py tests/research/minervini_primary_base_recall/`
Expected: `All checks passed!` Fix any lint inline (unused imports, line length), re-run, then commit the fix if any was needed.

- [ ] **Step 2: Run the new package suite (xdist, as CI runs)**

Run: `python -m pytest tests/research/minervini_primary_base_recall/ -q`
Expected: ALL PASS. If a flake appears only under `-n auto`, reproduce with `-n 0` (per the gotcha), fix the root cause, never paper over by re-running.

- [ ] **Step 3: Run the FULL fast suite to confirm no regression on the merged head**

Run: `python -m pytest -m "not slow" -q`
Expected: the prior green baseline (~7331+) plus the new tests, ZERO failures. READ the actual final line; do NOT carry forward a branch/older count as the post-merge result.

- [ ] **Step 4: Confirm the trailer audit is clean across the arc's commits**

Run: `git log origin/main..HEAD --format='%h %(trailers)'`
Expected: every line shows the SHA followed by an empty trailers field (no `Co-Authored-By`, no stray `Word:` trailers). If any commit shows a trailer, amend it (`git rebase` is not available interactively here -- fix the offending message with `git commit --amend` if it is HEAD, otherwise flag to the orchestrator).

- [ ] **Step 5: Commit any ruff fixes (if Step 1 required them); otherwise nothing to commit**

```bash
# only if ruff required a fix:
git add -A
git commit -m "style(research): ruff cleanups for primary-base-recall harness"
git log -1 --format='%(trailers)'
```

---

## Self-Review (run after the plan is drafted; fix inline)

**1. Spec coverage.** Every spec section maps to a task:
- S2 Ch.11 quantification -> Task 1 (constants) + Tasks 2-3 (screen criteria).
- S3 cohort (n~3, MELI removed, JNPR excluded) -> Task 4 (cohort) + Task 9 (denominators) + Tasks 12-13 (docs).
- S4 architecture / frozen-leaf reuse / L2 -> all tasks + Task 10 (L2 lock).
- S5 the six criteria (history/base-id+calendar-bar/duration/depth-ladder/fresh-cross/first-fire) -> Tasks 2-3.
- S6 recall+precision measurement (day vs full-month window; single-session day-only; own pre-filtered sampler; single-session-per-anchor primary estimand) -> Tasks 5, 6, 7, 9.
- S7 scorecard (raw fractions first; Wilson mechanical; criterion histogram; precision separate) -> Task 7 + Task 9 summary.
- S8 outputs + CLI (no --db; flags; ValueError->ClickException; manifest fields incl eligible_control_count, bar counts, l2_lock_preserved) -> Tasks 8, 9, 11.
- S9 testing (per-criterion discriminating tests w/ WRONG/RIGHT paths; depth-ladder boundaries; calendar->bar; month-window distinct; pre-filter-not-postfilter; ASCII subprocess; hardened L2) -> Tasks 2,3,5,6,8,10,11.
- S11 deliverables (method record + study doc) -> Tasks 12, 13.

**2. Placeholder scan.** No "TBD"/"handle edge cases"/"similar to Task N"; the study-doc PLACEHOLDER markers are intentional spec deliverables (Results pending the operator run), not plan placeholders.

**3. Type consistency.** `screen_at -> PrimaryBaseVerdict` (Tasks 2/3) is consumed by `timing` (Task 5) and `precision_control` (Task 6); `TimingResult`/`SessionEval`/`sweep_bounds` (Task 5) are consumed by `run.py` (Task 9); `ControlAnchor` (frozen) flows through `precision_control` (Task 6) into `run.py`; `RESULTS_HEADER`/`PER_SESSION_HEADER` (Task 8) match the dict keys emitted by `run.py` (Task 9) -- VERIFY this match during Task 9 (the results-row dict keys must equal `RESULTS_HEADER` exactly, else `csv.DictWriter` raises `ValueError: dict contains fields not in fieldnames`).

---

## Execution Handoff

**Plan complete.** Two execution options:

1. **Subagent-Driven (recommended)** -- a fresh subagent per task, orchestrator review + Codex convergence between/after.
2. **Inline Execution** -- executing-plans in-session with checkpoints.

(Per this arc's dispatch chain, the NEXT phase is a separate `copowers:executing-plans` dispatch; this writing-plans phase STOPS at Codex convergence on THIS plan.)
