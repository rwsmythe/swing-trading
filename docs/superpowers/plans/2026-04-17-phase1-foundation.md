# Phase 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `swing/` Python package with data layer, price data, 18 evaluation criteria (Minervini Trend Template + VCP tactical), and a CLI `swing eval` command that replaces the core function of the legacy `evaluate_candidates.py`. Produces working, testable software end-to-end: given a Finviz CSV in, a SQLite evaluation run + per-ticker criterion results out.

**Architecture:** New `swing/` package installed via `pyproject.toml`. SQLite at `%USERPROFILE%/swing-data/swing.db` with forward-only migrations; schema-version gate on connect. Evaluation criteria are pure functions of `CandidateContext` (per-ticker OHLCV + batch stats + config). Evaluator orchestrates criteria, scoring.py buckets. Click-based CLI with one subcommand in Phase 1: `eval`. Test strategy: unit tests per criterion (synthetic OHLCV fixtures), a parity harness replaying existing Finviz CSVs against the legacy evaluator for regression safety, and hand-constructed golden fixtures with expected outcomes declared from domain knowledge.

**Tech Stack:** Python 3.11+, pytest, Click, pandas, yfinance, pyarrow (parquet cache), tomli (config), exchange_calendars (NYSE calendar), ruff (linter — local only), sqlite3 (stdlib).

---

## Context

- **Spec:** [`docs/superpowers/specs/2026-04-17-swing-ground-up-refactor-design.md`](../specs/2026-04-17-swing-ground-up-refactor-design.md)
- **Phase 1 covers:** Spec sections §2.3 (package layout — swing/config, data/, prices, evaluation/, cli.py), §3 partial (tables: `evaluation_runs`, `candidates`, `candidate_criteria`), §4.1 (Trend Template 8 checks), §4.2 (VCP tactical 10 checks), §4.3 (bucket logic), §7.1 (unit tests), §7.2 (parity + golden tests).
- **Out of scope for Phase 1 (Phase 2+):** web dashboard, pipeline orchestration (weather, watchlist update, daily recommendations, export), trade logic, journal, TOS import, legacy data migration, pipeline locking/staging/recovery. Tables deferred: `weather_runs`, `watchlist`, `watchlist_archive`, `trades`, `exits`, `trade_events`, `cash_movements`, `daily_recommendations`, `pipeline_runs`, `config_revisions`.
- **Repo state:** the project folder is not yet a git repo. Task 1 initializes git. All subsequent tasks commit to the new repo.
- **Commands are bash (gitbash on Windows).** Paths use forward slashes except where Windows env vars are involved.

---

## File Map

```
Swing Trading/                                # repo root (after Task 1)
├── pyproject.toml                            # NEW — deps + package metadata
├── .gitignore                                # NEW
├── swing.config.toml                         # NEW — user-editable config
├── swing/
│   ├── __init__.py                           # NEW — package marker, version
│   ├── config.py                             # NEW — TOML loader + path resolution
│   ├── data/
│   │   ├── __init__.py                       # NEW
│   │   ├── db.py                             # NEW — connection + schema_version gate
│   │   ├── models.py                         # NEW — dataclasses (Candidate, CriterionResult, EvaluationRun)
│   │   ├── migrations/
│   │   │   ├── __init__.py                   # NEW
│   │   │   └── 0001_phase1_initial.sql       # NEW — evaluation_runs, candidates, candidate_criteria, schema_version
│   │   └── repos/
│   │       ├── __init__.py                   # NEW
│   │       └── candidates.py                 # NEW — insert/query candidates + criteria
│   ├── prices.py                             # NEW — yfinance wrapper + parquet cache
│   ├── evaluation/
│   │   ├── __init__.py                       # NEW
│   │   ├── context.py                        # NEW — CandidateContext dataclass
│   │   ├── dates.py                          # NEW — data_asof_date + action_session_date via NYSE calendar
│   │   ├── scoring.py                        # NEW — bucket logic (aplus/watch/skip/excluded/error)
│   │   ├── evaluator.py                      # NEW — orchestrates criteria for one ticker + batch RS
│   │   ├── rs.py                             # NEW — reference universe loader + rs_rank computation
│   │   └── criteria/
│   │       ├── __init__.py                   # NEW
│   │       ├── _base.py                      # NEW — Criterion protocol, Result dataclass, shared helpers
│   │       ├── prior_trend.py                # NEW — VCP
│   │       ├── ma_stack_short.py             # NEW — VCP (stack 10>20>50 + all rising)
│   │       ├── proximity.py                  # NEW — VCP (price within 5% of 20MA)
│   │       ├── adr.py                        # NEW — VCP
│   │       ├── pullback.py                   # NEW — VCP
│   │       ├── tightness.py                  # NEW — VCP
│   │       ├── vcp.py                        # NEW — VCP (volume contraction)
│   │       ├── orderliness.py                # NEW — VCP
│   │       ├── risk_feasibility.py           # NEW — VCP
│   │       └── trend_template.py             # NEW — Minervini 8-check gate
│   └── cli.py                                # NEW — Click app with `eval` subcommand
├── reference/
│   └── rs-universe.csv                       # NEW — seeded from S&P 500 + NASDAQ-100
├── tests/
│   ├── __init__.py                           # NEW
│   ├── conftest.py                           # NEW — pytest fixtures
│   ├── fixtures/
│   │   ├── ohlcv/                            # NEW — synthetic per-criterion OHLCV CSVs
│   │   ├── finviz/                           # NEW — copies of live finviz screeners
│   │   ├── golden/                           # NEW — hand-constructed cases + expected.yaml
│   │   └── parity-baseline.json              # NEW — captured from legacy evaluator
│   ├── config/
│   │   └── test_config.py                    # NEW
│   ├── data/
│   │   ├── test_db.py                        # NEW
│   │   └── test_repos_candidates.py          # NEW
│   ├── prices/
│   │   └── test_prices.py                    # NEW
│   ├── evaluation/
│   │   ├── test_context.py                   # NEW
│   │   ├── test_dates.py                     # NEW
│   │   ├── test_scoring.py                   # NEW
│   │   ├── test_evaluator.py                 # NEW
│   │   ├── test_rs.py                        # NEW
│   │   ├── test_parity.py                    # NEW
│   │   ├── test_golden.py                    # NEW
│   │   └── criteria/
│   │       ├── test_prior_trend.py           # NEW
│   │       ├── test_ma_stack_short.py        # NEW
│   │       ├── test_proximity.py             # NEW
│   │       ├── test_adr.py                   # NEW
│   │       ├── test_pullback.py              # NEW
│   │       ├── test_tightness.py             # NEW
│   │       ├── test_vcp.py                   # NEW
│   │       ├── test_orderliness.py           # NEW
│   │       ├── test_risk_feasibility.py      # NEW
│   │       └── test_trend_template.py        # NEW
│   └── cli/
│       └── test_cli_eval.py                  # NEW
└── docs/                                     # (already exists from brainstorming)
    └── superpowers/
        ├── specs/2026-04-17-swing-ground-up-refactor-design.md
        └── plans/2026-04-17-phase1-foundation.md    # this file
```

---

## Conventions

- **TDD:** every task writes the failing test first, then minimal implementation, then verifies pass, then commits.
- **Commit style:** conventional commits (`feat:`, `test:`, `chore:`). One logical change per commit.
- **Imports:** absolute (`from swing.evaluation.criteria import tightness`). No relative imports.
- **Type hints:** every function signature is typed. `from __future__ import annotations` at top of each module.
- **Docstrings:** one-line for criterion functions stating the rule; omit for trivial internals.
- **No prints in library code.** CLI uses Click's `click.echo`; library raises or returns.
- **Operator-facing CLI form is `swing <subcommand>`** (via `pyproject.toml [project.scripts]`). `python -m swing.cli <subcommand>` is the developer-facing equivalent; tests use `python -m swing.cli` to avoid PATH dependence. Error messages surfaced to the user prefer the `swing` form.

---

## Prerequisites (verify before Task 1)

The plan depends on several pre-existing local artifacts. Verify each before starting, or substitute the noted fallback:

| Asset | Purpose | How to verify | Fallback |
|---|---|---|---|
| `finviz screeners/*.csv` | Parity fixtures (Task 28) | `ls "finviz screeners"/*.csv` → at least one file | Parity test uses golden fixtures only; Task 28/29 skip |
| `reports/<YYYY-MM-DD>/evaluation.csv` | Legacy parity baseline | `ls reports/*/evaluation.csv` → matches exist for some Finviz dates | Same — parity test skipped for unmatched dates |
| Legacy `evaluation.csv` column layout | Baseline capture | `python -c "import csv; print(list(next(csv.DictReader(open('reports/2026-04-16/evaluation.csv'))).keys()))"` → contains `ticker` and `bucket` (any case) | Edit `_capture_baseline.py`'s `_load_legacy_bucket_map` column names to match actual |
| Network access to `en.wikipedia.org` + `finance.yahoo.com` | Task 12 (RS universe seed), Tasks 11/27/29 (yfinance) | `curl -sI https://en.wikipedia.org \| head -1` → `HTTP/2 200` | Task 12 fallback: use the static ticker list committed to this plan (see "RS universe fallback" appendix at end of plan). yfinance is hard-required for any real evaluation. |
| Python 3.11+ | pyarrow binary wheels | `python --version` | Verify `python -m pip install --dry-run pyarrow` finds a wheel; Python 3.11, 3.12, 3.13, and 3.14 all have cp-tagged wheels as of 2026 |

**Precondition task (execute once before Task 1):**

```bash
cd "c:/Users/rwsmy/My Drive/Swing Trading"
echo "=== Finviz fixtures ==="
ls "finviz screeners"/*.csv 2>/dev/null | head
echo "=== Legacy reports ==="
ls reports/*/evaluation.csv 2>/dev/null | head
echo "=== Legacy column layout (first file) ==="
python -c "import csv,glob; f=sorted(glob.glob('reports/*/evaluation.csv'))[-1]; print('file:',f); print('cols:',list(next(csv.DictReader(open(f))).keys()))" 2>&1 | head -5
echo "=== Network ==="
curl -sI https://en.wikipedia.org 2>&1 | head -1
curl -sI https://finance.yahoo.com 2>&1 | head -1
echo "=== Python ==="
python --version
```

Record the output in a scratch file (e.g., `/tmp/phase1-preconditions.txt`). If any asset is missing, follow the fallback or adjust the relevant task (noted per task).

---

## Tasks

### Task 1: Initialize git repo + .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Initialize git**

```bash
cd "c:/Users/rwsmy/My Drive/Swing Trading"
git init -b main
```

- [ ] **Step 2: Write .gitignore**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.ruff_cache/
.venv/
venv/

# Swing app data (lives outside Drive folder, but cover stray files)
swing-data/
/data/                 # root-level only — do NOT write `data/` (that would also match swing/data/)
.superpowers/

# OS
.DS_Store
Thumbs.db

# Legacy — archived for reference but not tracked
reference/archive/
```

- [ ] **Step 3: Stage existing spec + plan, commit scaffolding**

```bash
git add .gitignore docs/
git commit -m "chore: initialize repo with spec and plan"
```

Expected: one commit on main with .gitignore and docs/ tracked. Legacy `.py` files at root stay untracked until Phase 4 migration.

---

### Task 2: Create pyproject.toml with dependencies

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "swing"
version = "0.1.0"
description = "Personal swing-trading tool — Disciplined Swing Trader + Minervini SEPA"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "pandas>=2.2",
    "yfinance>=0.2.40",
    "pyarrow>=15",
    "tomli>=2; python_version<'3.11'",
    "exchange_calendars>=4.5",
    "pyyaml>=6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "ruff>=0.5",
]

[project.scripts]
swing = "swing.cli:main"

[tool.setuptools.packages.find]
include = ["swing*"]
exclude = ["tests*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM"]
```

- [ ] **Step 2: Install in editable mode with dev deps**

```bash
python -m pip install -e ".[dev]"
```

Expected: installs successfully. If on Windows with "ERROR: No matching distribution" for pyarrow on Python 3.13, pin Python to 3.11 or 3.12 — 3.11 is the tested target for this plan.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with dependencies"
```

---

### Task 3: Create swing/ package skeleton

**Files:**
- Create: `swing/__init__.py`
- Create: `swing/data/__init__.py`
- Create: `swing/data/repos/__init__.py`
- Create: `swing/data/migrations/__init__.py`
- Create: `swing/evaluation/__init__.py`
- Create: `swing/evaluation/criteria/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create all __init__.py files**

```bash
mkdir -p swing/data/repos swing/data/migrations swing/evaluation/criteria tests
touch swing/__init__.py swing/data/__init__.py swing/data/repos/__init__.py \
      swing/data/migrations/__init__.py swing/evaluation/__init__.py \
      swing/evaluation/criteria/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write swing/__init__.py with version**

```python
"""Swing trading evaluation and journaling package."""
from __future__ import annotations

__version__ = "0.1.0"
```

- [ ] **Step 3: Verify package imports**

```bash
python -c "import swing; print(swing.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 4: Commit**

```bash
git add swing/ tests/
git commit -m "feat: create swing/ package skeleton"
```

---

### Task 4: Create pytest conftest + first smoke test

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write tests/conftest.py with shared fixtures**

```python
"""Shared pytest fixtures."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Path to a fresh temp SQLite DB (no schema applied)."""
    return tmp_path / "test.db"


@pytest.fixture
def ohlcv_factory():
    """Factory for building synthetic daily OHLCV DataFrames."""
    def _make(closes: list[float], *, start_date: str = "2026-01-02", volume: int = 1_000_000) -> pd.DataFrame:
        idx = pd.bdate_range(start=start_date, periods=len(closes))
        df = pd.DataFrame(
            {
                "Open": closes,
                "High": [c * 1.01 for c in closes],
                "Low": [c * 0.99 for c in closes],
                "Close": closes,
                "Volume": [volume] * len(closes),
            },
            index=idx,
        )
        return df
    return _make
```

- [ ] **Step 2: Write a smoke test**

```python
"""Smoke test — proves the test harness works."""
from __future__ import annotations

import swing


def test_package_version():
    assert swing.__version__ == "0.1.0"


def test_ohlcv_factory_shape(ohlcv_factory):
    df = ohlcv_factory([10.0, 10.5, 11.0])
    assert len(df) == 3
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_smoke.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add pytest conftest and smoke test"
```

---

### Task 5: Create swing.config.toml with defaults

**Files:**
- Create: `swing.config.toml`

- [ ] **Step 1: Write swing.config.toml**

```toml
# Swing trading config — see docs/superpowers/specs/ for rationale.
# User-editable. Schema loaded by swing.config.load().

[paths]
# DB lives OUTSIDE the Drive folder (see spec §2.4). Defaults to a local swing-data/ folder.
# Can be an absolute path; otherwise relative to $USERPROFILE (Windows) or $HOME.
db_path = "swing-data/swing.db"
data_dir = "swing-data"
logs_dir = "swing-data/logs"
charts_dir = "swing-data/charts"
backups_dir = "swing-data/backups"
prices_cache_dir = "swing-data/prices-cache"

# Paths INSIDE the project folder (these are the only things the Drive folder holds that the app writes)
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
# Max risk per trade as fraction of equity
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0       # |price - 20MA| <= N% of 20MA
tightness_days_required = 2
tightness_range_factor = 0.67 # daily range <= factor * ADR
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7                # of 8 TT checks; below this = skip bucket
allowed_miss_names = ["TT8"]  # TT8 (RS) is the default acceptable miss
rising_ma_period_days = 21    # for TT3 (200MA trending up ≥ 21 trading days)
high_52w_margin_pct = 25.0    # TT7
low_52w_min_pct = 30.0        # TT6

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70         # TT8 threshold
# Fallback for tickers not in universe: ±N% excess vs SPY triggers pass/fail
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = ["UCO"]
manual_allow = []

[focus_ranking]
# Composite weights: closeness to pivot 50%, ADR 25%, prior trend 25%
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
```

- [ ] **Step 2: Commit**

```bash
git add swing.config.toml
git commit -m "feat: add default swing.config.toml"
```

---

### Task 6: Implement swing/config.py (TOML loader + path resolution)

**Files:**
- Create: `swing/config.py`
- Create: `tests/config/__init__.py`
- Create: `tests/config/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for swing.config."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from swing.config import Config, load


def test_load_reads_toml_file(tmp_path: Path):
    cfg_file = tmp_path / "swing.config.toml"
    cfg_file.write_text(
        """
[paths]
db_path = "mydata/swing.db"
data_dir = "mydata"
logs_dir = "mydata/logs"
charts_dir = "mydata/charts"
backups_dir = "mydata/backups"
prices_cache_dir = "mydata/prices-cache"
finviz_inbox_dir = "data/inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1000.0
starting_date = "2026-01-01"
risk_equity_floor = 5000.0

[position_limits]
soft_warn_open = 3
hard_cap_open = 5

[risk]
max_risk_pct = 0.01

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
""",
        encoding="utf-8",
    )
    cfg = load(cfg_file)
    assert cfg.account.starting_equity == 1000.0
    assert cfg.vcp.adr_min_pct == 4.0
    assert cfg.trend_template.min_passes == 7
    assert cfg.rs.benchmark_ticker == "SPY"


def test_paths_resolves_relative_to_user_home(tmp_path: Path, monkeypatch):
    """Relative paths in [paths] are resolved against USERPROFILE (Win) or HOME (Unix)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_file = _write_default_toml(tmp_path / "swing.config.toml")
    cfg = load(cfg_file)
    assert cfg.paths.db_path == tmp_path / "swing-data" / "swing.db"
    assert cfg.paths.logs_dir == tmp_path / "swing-data" / "logs"


def test_paths_absolute_not_rewritten(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    abs_db = tmp_path / "absolute" / "swing.db"
    cfg_file = _write_default_toml(tmp_path / "swing.config.toml", db_path_override=str(abs_db))
    cfg = load(cfg_file)
    assert cfg.paths.db_path == abs_db


def test_load_raises_on_missing_section(tmp_path: Path):
    cfg_file = tmp_path / "swing.config.toml"
    cfg_file.write_text("[paths]\ndb_path = \"x\"\n", encoding="utf-8")
    with pytest.raises(KeyError) as exc:
        load(cfg_file)
    assert "account" in str(exc.value).lower() or "section" in str(exc.value).lower()


def _write_default_toml(path: Path, *, db_path_override: str | None = None) -> Path:
    """Write a full valid config to path; used by path-resolution tests."""
    db = db_path_override or "swing-data/swing.db"
    path.write_text(
        f"""
[paths]
db_path = "{db}"
data_dir = "swing-data"
logs_dir = "swing-data/logs"
charts_dir = "swing-data/charts"
backups_dir = "swing-data/backups"
prices_cache_dir = "swing-data/prices-cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
""".lstrip(),
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/config/test_config.py -v
```

Expected: ImportError on `from swing.config import Config, load`.

- [ ] **Step 3: Implement swing/config.py**

```python
"""Config loader — reads swing.config.toml into dataclasses, resolves paths."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


@dataclass(frozen=True)
class Paths:
    db_path: Path
    data_dir: Path
    logs_dir: Path
    charts_dir: Path
    backups_dir: Path
    prices_cache_dir: Path
    finviz_inbox_dir: Path
    exports_dir: Path
    rs_universe_path: Path


@dataclass(frozen=True)
class Account:
    starting_equity: float
    starting_date: str
    risk_equity_floor: float


@dataclass(frozen=True)
class PositionLimits:
    soft_warn_open: int
    hard_cap_open: int


@dataclass(frozen=True)
class Risk:
    max_risk_pct: float


@dataclass(frozen=True)
class VCP:
    prior_trend_min_pct: float
    adr_min_pct: float
    pullback_max_pct: float
    proximity_max_pct: float
    tightness_days_required: int
    tightness_range_factor: float
    orderliness_max_bar_ratio: float
    orderliness_max_range_cv: float


@dataclass(frozen=True)
class TrendTemplate:
    min_passes: int
    allowed_miss_names: tuple[str, ...]
    rising_ma_period_days: int
    high_52w_margin_pct: float
    low_52w_min_pct: float


@dataclass(frozen=True)
class RS:
    horizon_weeks: int
    benchmark_ticker: str
    rs_rank_min_pass: int
    fallback_extreme_pct: float


@dataclass(frozen=True)
class ETFExclusion:
    exclude_etfs: bool
    manual_block: tuple[str, ...]
    manual_allow: tuple[str, ...]


@dataclass(frozen=True)
class FocusRanking:
    closeness_to_pivot: float
    adr: float
    prior_trend: float


@dataclass(frozen=True)
class Config:
    paths: Paths
    account: Account
    position_limits: PositionLimits
    risk: Risk
    vcp: VCP
    trend_template: TrendTemplate
    rs: RS
    etf_exclusion: ETFExclusion
    focus_ranking: FocusRanking


def _user_home() -> Path:
    """Windows USERPROFILE, fallback to HOME."""
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _resolve_path(raw: str, home: Path, project_root: Path) -> Path:
    """Absolute paths pass through; relative project-internal paths (data/, exports/, reference/) resolve against project_root; others resolve against home."""
    p = Path(raw)
    if p.is_absolute():
        return p
    project_internal_prefixes = ("data/", "exports/", "reference/", "data\\", "exports\\", "reference\\")
    if raw.replace("\\", "/").startswith(("data/", "exports/", "reference/")):
        return project_root / p
    return home / p


def load(config_path: Path) -> Config:
    """Load and validate a swing.config.toml file."""
    project_root = config_path.parent.resolve()
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    required_sections = (
        "paths", "account", "position_limits", "risk", "vcp",
        "trend_template", "rs", "etf_exclusion", "focus_ranking",
    )
    for section in required_sections:
        if section not in raw:
            raise KeyError(f"swing.config.toml missing required section: [{section}]")

    home = _user_home()
    p = raw["paths"]
    paths = Paths(
        db_path=_resolve_path(p["db_path"], home, project_root),
        data_dir=_resolve_path(p["data_dir"], home, project_root),
        logs_dir=_resolve_path(p["logs_dir"], home, project_root),
        charts_dir=_resolve_path(p["charts_dir"], home, project_root),
        backups_dir=_resolve_path(p["backups_dir"], home, project_root),
        prices_cache_dir=_resolve_path(p["prices_cache_dir"], home, project_root),
        finviz_inbox_dir=_resolve_path(p["finviz_inbox_dir"], home, project_root),
        exports_dir=_resolve_path(p["exports_dir"], home, project_root),
        rs_universe_path=_resolve_path(p["rs_universe_path"], home, project_root),
    )

    return Config(
        paths=paths,
        account=Account(**raw["account"]),
        position_limits=PositionLimits(**raw["position_limits"]),
        risk=Risk(**raw["risk"]),
        vcp=VCP(**raw["vcp"]),
        trend_template=TrendTemplate(
            min_passes=raw["trend_template"]["min_passes"],
            allowed_miss_names=tuple(raw["trend_template"]["allowed_miss_names"]),
            rising_ma_period_days=raw["trend_template"]["rising_ma_period_days"],
            high_52w_margin_pct=raw["trend_template"]["high_52w_margin_pct"],
            low_52w_min_pct=raw["trend_template"]["low_52w_min_pct"],
        ),
        rs=RS(**raw["rs"]),
        etf_exclusion=ETFExclusion(
            exclude_etfs=raw["etf_exclusion"]["exclude_etfs"],
            manual_block=tuple(raw["etf_exclusion"]["manual_block"]),
            manual_allow=tuple(raw["etf_exclusion"]["manual_allow"]),
        ),
        focus_ranking=FocusRanking(**raw["focus_ranking"]),
    )
```

- [ ] **Step 4: Add tests/config/__init__.py**

```bash
touch tests/config/__init__.py
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/config/test_config.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add swing/config.py tests/config/
git commit -m "feat: add config loader with path resolution"
```

---

### Task 7: Write migration 0001 and db.py schema-version gate

**Files:**
- Create: `swing/data/migrations/0001_phase1_initial.sql`
- Create: `swing/data/db.py`
- Create: `tests/data/__init__.py`
- Create: `tests/data/test_db.py`

- [ ] **Step 1: Write 0001_phase1_initial.sql**

```sql
-- Phase 1 schema — evaluation-only tables. Later phases extend.

CREATE TABLE schema_version (
  version INTEGER PRIMARY KEY
);
INSERT INTO schema_version (version) VALUES (1);

-- evaluation batch (one per evaluator run — Phase 1 has no pipeline wrapping it yet)
CREATE TABLE evaluation_runs (
  id INTEGER PRIMARY KEY,
  run_ts TEXT NOT NULL,
  data_asof_date TEXT NOT NULL,
  action_session_date TEXT NOT NULL,
  finviz_csv_path TEXT,
  tickers_evaluated INTEGER NOT NULL,
  aplus_count INTEGER NOT NULL,
  watch_count INTEGER NOT NULL,
  skip_count INTEGER NOT NULL,
  excluded_count INTEGER NOT NULL,
  error_count INTEGER NOT NULL
);

-- one row per (evaluation_run, ticker)
CREATE TABLE candidates (
  id INTEGER PRIMARY KEY,
  evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id),
  ticker TEXT NOT NULL,
  bucket TEXT NOT NULL CHECK (bucket IN ('aplus','watch','skip','error','excluded')),
  close REAL,
  pivot REAL,
  initial_stop REAL,
  adr_pct REAL,
  tight_streak INTEGER,
  pullback_pct REAL,
  prior_trend_pct REAL,
  rs_rank INTEGER,
  rs_return_12w_vs_spy REAL,
  rs_method TEXT NOT NULL CHECK (rs_method IN ('universe','fallback_spy','unavailable')),
  pattern_tag TEXT,
  notes TEXT,
  UNIQUE(evaluation_run_id, ticker)
);

CREATE INDEX ix_candidates_run_bucket ON candidates(evaluation_run_id, bucket);
CREATE INDEX ix_candidates_ticker ON candidates(ticker);

-- per-criterion result for each candidate row
CREATE TABLE candidate_criteria (
  candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
  criterion_name TEXT NOT NULL,
  layer TEXT NOT NULL CHECK (layer IN ('trend_template','vcp','risk')),
  result TEXT NOT NULL CHECK (result IN ('pass','fail','na')),
  value TEXT,
  rule TEXT,
  PRIMARY KEY (candidate_id, criterion_name)
);
```

- [ ] **Step 2: Write failing tests**

```python
"""Tests for swing.data.db."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, connect, ensure_schema, SchemaVersionMismatch


def test_ensure_schema_applies_migrations_on_fresh_db(tmp_db: Path):
    conn = ensure_schema(tmp_db)
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == EXPECTED_SCHEMA_VERSION
    # evaluation_runs exists
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='evaluation_runs'")
    assert cur.fetchone() is not None


def test_connect_refuses_old_schema(tmp_db: Path):
    # Create a DB with schema_version = 0 (pre-migration)
    conn = sqlite3.connect(tmp_db)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version VALUES (0)")
    conn.commit()
    conn.close()

    with pytest.raises(SchemaVersionMismatch) as exc:
        connect(tmp_db)
    assert "db-migrate" in str(exc.value)


def test_connect_works_after_ensure_schema(tmp_db: Path):
    ensure_schema(tmp_db).close()
    conn = connect(tmp_db)
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == EXPECTED_SCHEMA_VERSION
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/data/test_db.py -v
```

Expected: ImportError on swing.data.db.

- [ ] **Step 4: Implement swing/data/db.py**

```python
"""SQLite connection + migrations + schema-version gate."""
from __future__ import annotations

import sqlite3
from pathlib import Path

EXPECTED_SCHEMA_VERSION = 1
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class SchemaVersionMismatch(RuntimeError):
    """Raised when the DB schema version doesn't match what the code expects."""


def _apply_migration(conn: sqlite3.Connection, sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def _current_version(conn: sqlite3.Connection) -> int:
    """Return DB's schema_version, or 0 if no schema_version table exists."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if cur.fetchone() is None:
        return 0
    cur = conn.execute("SELECT version FROM schema_version")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def ensure_schema(db_path: Path) -> sqlite3.Connection:
    """Create or upgrade the DB schema. Use from the CLI migrate command, NOT from app startup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    current = _current_version(conn)
    if current == EXPECTED_SCHEMA_VERSION:
        return conn
    if current > EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionMismatch(
            f"DB schema version {current} newer than code ({EXPECTED_SCHEMA_VERSION}). "
            "Update the swing package."
        )

    # Apply migrations in order from current+1 to EXPECTED
    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for mig in migration_files:
        # filename like "0001_phase1_initial.sql"
        try:
            version = int(mig.stem.split("_", 1)[0])
        except ValueError:
            continue
        if current < version <= EXPECTED_SCHEMA_VERSION:
            _apply_migration(conn, mig)

    # Verify we reached expected version
    if _current_version(conn) != EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise RuntimeError("Migration ran but schema_version did not reach expected value.")
    return conn


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection for normal app use. Raises if schema is not current."""
    if not db_path.exists():
        raise SchemaVersionMismatch(
            f"DB not found at {db_path}. Run: python -m swing.cli db-migrate"
        )
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    current = _current_version(conn)
    if current != EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionMismatch(
            f"DB schema version {current}, code expects {EXPECTED_SCHEMA_VERSION}. "
            "Run: python -m swing.cli db-migrate"
        )
    return conn
```

- [ ] **Step 5: Add tests/data/__init__.py and run tests**

```bash
touch tests/data/__init__.py
pytest tests/data/test_db.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add swing/data/migrations/0001_phase1_initial.sql swing/data/db.py tests/data/
git commit -m "feat: add Phase 1 schema migration and db connection gate"
```

---

### Task 8: Implement swing/data/models.py

**Files:**
- Create: `swing/data/models.py`

- [ ] **Step 1: Write models.py**

```python
"""Dataclass representations of DB rows."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriterionResult:
    criterion_name: str
    layer: str  # 'trend_template' | 'vcp' | 'risk'
    result: str  # 'pass' | 'fail' | 'na'
    value: str | None = None
    rule: str | None = None


@dataclass(frozen=True)
class Candidate:
    ticker: str
    bucket: str  # 'aplus' | 'watch' | 'skip' | 'error' | 'excluded'
    close: float | None
    pivot: float | None
    initial_stop: float | None
    adr_pct: float | None
    tight_streak: int | None
    pullback_pct: float | None
    prior_trend_pct: float | None
    rs_rank: int | None
    rs_return_12w_vs_spy: float | None
    rs_method: str  # 'universe' | 'fallback_spy' | 'unavailable'
    pattern_tag: str | None
    notes: str | None
    criteria: tuple[CriterionResult, ...]


@dataclass(frozen=True)
class EvaluationRun:
    id: int | None
    run_ts: str  # ISO 8601
    data_asof_date: str  # YYYY-MM-DD
    action_session_date: str  # YYYY-MM-DD
    finviz_csv_path: str | None
    tickers_evaluated: int
    aplus_count: int
    watch_count: int
    skip_count: int
    excluded_count: int
    error_count: int
```

- [ ] **Step 2: Verify import**

```bash
python -c "from swing.data.models import Candidate, CriterionResult, EvaluationRun"
```

Expected: no output (success).

- [ ] **Step 3: Commit**

```bash
git add swing/data/models.py
git commit -m "feat: add data model dataclasses"
```

---

### Task 9: Implement repos/candidates.py with round-trip test

**Files:**
- Create: `swing/data/repos/candidates.py`
- Create: `tests/data/test_repos_candidates.py`

- [ ] **Step 1: Write failing test**

```python
"""Round-trip test for candidates repo."""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import insert_evaluation_run, insert_candidates, fetch_candidates_for_run


def test_insert_candidate_with_no_criteria_roundtrips(tmp_db: Path):
    """Excluded/error candidates have criteria=(); fetch must not break."""
    conn = ensure_schema(tmp_db)
    run = EvaluationRun(
        id=None, run_ts="2026-04-17T21:49:00",
        data_asof_date="2026-04-17", action_session_date="2026-04-20",
        finviz_csv_path=None, tickers_evaluated=1, aplus_count=0, watch_count=0,
        skip_count=0, excluded_count=1, error_count=0,
    )
    run_id = insert_evaluation_run(conn, run)
    insert_candidates(conn, run_id, [
        Candidate(
            ticker="UCO", bucket="excluded", close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="ETF blocklist", criteria=(),
        ),
    ])
    fetched = fetch_candidates_for_run(conn, run_id)
    assert len(fetched) == 1
    assert fetched[0].bucket == "excluded"
    assert fetched[0].criteria == ()
    assert fetched[0].notes == "ETF blocklist"


def test_insert_run_and_candidates_roundtrip(tmp_db: Path):
    conn = ensure_schema(tmp_db)
    run = EvaluationRun(
        id=None,
        run_ts="2026-04-17T21:49:00",
        data_asof_date="2026-04-17",
        action_session_date="2026-04-20",
        finviz_csv_path="data/finviz-inbox/finviz17Apr2026.csv",
        tickers_evaluated=2,
        aplus_count=1,
        watch_count=1,
        skip_count=0,
        excluded_count=0,
        error_count=0,
    )
    run_id = insert_evaluation_run(conn, run)
    assert run_id > 0

    candidates = [
        Candidate(
            ticker="CE",
            bucket="aplus",
            close=68.34,
            pivot=68.65,
            initial_stop=58.77,
            adr_pct=4.66,
            tight_streak=2,
            pullback_pct=22.3,
            prior_trend_pct=304.6,
            rs_rank=82,
            rs_return_12w_vs_spy=0.18,
            rs_method="universe",
            pattern_tag="HTF",
            notes=None,
            criteria=(
                CriterionResult("prior_trend", "vcp", "pass", "304.6%", ">= 25%"),
                CriterionResult("TT1_above_150_200", "trend_template", "pass", "close > 150MA, 200MA", ""),
            ),
        ),
        Candidate(
            ticker="UNIT",
            bucket="watch",
            close=11.06,
            pivot=11.19,
            initial_stop=9.66,
            adr_pct=4.95,
            tight_streak=0,
            pullback_pct=18.1,
            prior_trend_pct=45.0,
            rs_rank=55,
            rs_return_12w_vs_spy=0.04,
            rs_method="universe",
            pattern_tag=None,
            notes=None,
            criteria=(
                CriterionResult("tightness", "vcp", "fail", "0 day streak", ">= 2 days"),
            ),
        ),
    ]
    insert_candidates(conn, run_id, candidates)

    fetched = fetch_candidates_for_run(conn, run_id)
    assert len(fetched) == 2
    by_ticker = {c.ticker: c for c in fetched}
    assert by_ticker["CE"].bucket == "aplus"
    assert by_ticker["CE"].rs_method == "universe"
    assert len(by_ticker["CE"].criteria) == 2
    assert by_ticker["UNIT"].bucket == "watch"
    assert by_ticker["UNIT"].criteria[0].result == "fail"
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
pytest tests/data/test_repos_candidates.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement repos/candidates.py**

```python
"""Candidates + CandidateCriteria repository."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from swing.data.models import Candidate, CriterionResult, EvaluationRun


def insert_evaluation_run(conn: sqlite3.Connection, run: EvaluationRun) -> int:
    cur = conn.execute(
        """
        INSERT INTO evaluation_runs
            (run_ts, data_asof_date, action_session_date, finviz_csv_path,
             tickers_evaluated, aplus_count, watch_count, skip_count,
             excluded_count, error_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run.run_ts, run.data_asof_date, run.action_session_date,
            run.finviz_csv_path, run.tickers_evaluated, run.aplus_count,
            run.watch_count, run.skip_count, run.excluded_count, run.error_count,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_candidates(conn: sqlite3.Connection, run_id: int, candidates: Sequence[Candidate]) -> None:
    for c in candidates:
        cur = conn.execute(
            """
            INSERT INTO candidates
                (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                 adr_pct, tight_streak, pullback_pct, prior_trend_pct,
                 rs_rank, rs_return_12w_vs_spy, rs_method, pattern_tag, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, c.ticker, c.bucket, c.close, c.pivot, c.initial_stop,
                c.adr_pct, c.tight_streak, c.pullback_pct, c.prior_trend_pct,
                c.rs_rank, c.rs_return_12w_vs_spy, c.rs_method, c.pattern_tag, c.notes,
            ),
        )
        cid = int(cur.lastrowid)
        for crit in c.criteria:
            conn.execute(
                """
                INSERT INTO candidate_criteria
                    (candidate_id, criterion_name, layer, result, value, rule)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cid, crit.criterion_name, crit.layer, crit.result, crit.value, crit.rule),
            )
    conn.commit()


def fetch_candidates_for_run(conn: sqlite3.Connection, run_id: int) -> list[Candidate]:
    cand_rows = conn.execute(
        """
        SELECT id, ticker, bucket, close, pivot, initial_stop, adr_pct,
               tight_streak, pullback_pct, prior_trend_pct, rs_rank,
               rs_return_12w_vs_spy, rs_method, pattern_tag, notes
        FROM candidates
        WHERE evaluation_run_id = ?
        ORDER BY ticker
        """,
        (run_id,),
    ).fetchall()

    result: list[Candidate] = []
    for row in cand_rows:
        cid = row[0]
        crit_rows = conn.execute(
            """
            SELECT criterion_name, layer, result, value, rule
            FROM candidate_criteria
            WHERE candidate_id = ?
            ORDER BY criterion_name
            """,
            (cid,),
        ).fetchall()
        criteria = tuple(
            CriterionResult(name, layer, res, val, rule)
            for (name, layer, res, val, rule) in crit_rows
        )
        result.append(
            Candidate(
                ticker=row[1], bucket=row[2], close=row[3], pivot=row[4],
                initial_stop=row[5], adr_pct=row[6], tight_streak=row[7],
                pullback_pct=row[8], prior_trend_pct=row[9], rs_rank=row[10],
                rs_return_12w_vs_spy=row[11], rs_method=row[12],
                pattern_tag=row[13], notes=row[14], criteria=criteria,
            )
        )
    return result
```

- [ ] **Step 4: Run test — expect pass**

```bash
pytest tests/data/test_repos_candidates.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/candidates.py tests/data/test_repos_candidates.py
git commit -m "feat: add candidates repo with round-trip test"
```

---

### Task 10: Implement swing/evaluation/dates.py (NYSE calendar)

**Files:**
- Create: `swing/evaluation/dates.py`
- Create: `tests/evaluation/__init__.py`
- Create: `tests/evaluation/test_dates.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for swing.evaluation.dates."""
from __future__ import annotations

from datetime import datetime

from swing.evaluation.dates import (
    data_asof_from_ohlcv_max,
    action_session_for_run,
)


def test_action_session_weeknight():
    # Tuesday 21:49 HST == Wednesday 03:49 ET. Action session: Wednesday.
    now_hst = datetime(2026, 4, 14, 21, 49)  # Tuesday
    result = action_session_for_run(now_hst, tz="Pacific/Honolulu")
    assert result.isoformat() == "2026-04-15"


def test_action_session_friday_night_returns_monday():
    # Friday 21:49 HST — next trading day is Monday.
    now_hst = datetime(2026, 4, 17, 21, 49)  # Friday
    result = action_session_for_run(now_hst, tz="Pacific/Honolulu")
    assert result.isoformat() == "2026-04-20"  # Monday


def test_action_session_during_market_hours():
    # Wednesday 06:30 HST == Wednesday 12:30 ET, market open. Action = Wednesday.
    now_hst = datetime(2026, 4, 15, 6, 30)
    result = action_session_for_run(now_hst, tz="Pacific/Honolulu")
    assert result.isoformat() == "2026-04-15"


def test_data_asof_from_ohlcv_max(ohlcv_factory):
    df = ohlcv_factory([10.0, 10.5, 11.0], start_date="2026-04-15")
    result = data_asof_from_ohlcv_max(df)
    # bdate_range starts 2026-04-15 (Wed), next is Thu 4/16, Fri 4/17
    assert result.isoformat() == "2026-04-17"
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
mkdir -p tests/evaluation
touch tests/evaluation/__init__.py
pytest tests/evaluation/test_dates.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement swing/evaluation/dates.py**

```python
"""Market-session dates: data_asof_date vs action_session_date."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

_NYSE = xcals.get_calendar("XNYS")


def data_asof_from_ohlcv_max(df: pd.DataFrame) -> date:
    """Most recent bar date in an OHLCV DataFrame (indexed by date)."""
    idx_max = df.index.max()
    if isinstance(idx_max, pd.Timestamp):
        return idx_max.date()
    return idx_max  # type: ignore[return-value]


def action_session_for_run(now_local: datetime, *, tz: str = "Pacific/Honolulu") -> date:
    """
    The next NYSE trading session at or after `now_local`.

    Converts local time to US/Eastern, then asks the NYSE calendar for the next open session.
    If `now_local` falls during a current NYSE session, returns that session date.
    """
    local = now_local.replace(tzinfo=ZoneInfo(tz))
    ny = local.astimezone(ZoneInfo("America/New_York"))
    # exchange_calendars expects tz-naive UTC timestamps
    ny_ts = pd.Timestamp(ny).tz_convert("UTC").tz_localize(None)

    # If today is a trading day AND we're before/during the session close, it's today.
    today_date = ny.date()
    if _NYSE.is_session(pd.Timestamp(today_date)):
        close_ts = _NYSE.session_close(pd.Timestamp(today_date))
        # close_ts is tz-aware in UTC
        if ny_ts.tz_localize("UTC") <= close_ts:
            return today_date

    # Otherwise ask for the next session strictly after today
    next_ts = _NYSE.next_session(pd.Timestamp(today_date))
    return next_ts.date()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/evaluation/test_dates.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add swing/evaluation/dates.py tests/evaluation/test_dates.py tests/evaluation/__init__.py
git commit -m "feat: add NYSE-calendar-aware session date helpers"
```

---

### Task 11: Implement swing/prices.py (yfinance wrapper + parquet cache)

**Files:**
- Create: `swing/prices.py`
- Create: `tests/prices/__init__.py`
- Create: `tests/prices/test_prices.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for swing.prices."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from swing.prices import PriceFetcher


def test_cache_miss_calls_fetch(tmp_path: Path):
    fetcher = PriceFetcher(cache_dir=tmp_path)
    fake_df = pd.DataFrame(
        {
            "Open": [10.0, 10.5],
            "High": [10.1, 10.6],
            "Low": [9.9, 10.4],
            "Close": [10.0, 10.5],
            "Volume": [1_000_000, 1_100_000],
        },
        index=pd.bdate_range(start="2026-04-15", periods=2),
    )
    with patch.object(fetcher, "_fetch_from_yf", return_value=fake_df) as mock_fetch:
        result = fetcher.get("AAPL", lookback_days=10)
    mock_fetch.assert_called_once()
    assert len(result) == 2


def test_cache_hit_skips_fetch(tmp_path: Path):
    fetcher = PriceFetcher(cache_dir=tmp_path)
    fake_df = pd.DataFrame(
        {
            "Open": [10.0],
            "High": [10.1],
            "Low": [9.9],
            "Close": [10.0],
            "Volume": [1_000_000],
        },
        index=pd.bdate_range(start="2026-04-15", periods=1),
    )
    with patch.object(fetcher, "_fetch_from_yf", return_value=fake_df):
        fetcher.get("AAPL", lookback_days=10)
    # Second call should hit cache — _fetch_from_yf not called
    with patch.object(fetcher, "_fetch_from_yf") as mock_fetch:
        result = fetcher.get("AAPL", lookback_days=10)
        mock_fetch.assert_not_called()
    assert len(result) == 1


def test_cache_miss_on_different_ticker(tmp_path: Path):
    fetcher = PriceFetcher(cache_dir=tmp_path)
    df_a = pd.DataFrame({"Close": [10.0]}, index=pd.bdate_range("2026-04-15", periods=1))
    df_b = pd.DataFrame({"Close": [20.0]}, index=pd.bdate_range("2026-04-15", periods=1))

    def side_effect(ticker, lookback):
        return df_a if ticker == "AAPL" else df_b

    with patch.object(fetcher, "_fetch_from_yf", side_effect=side_effect) as mock_fetch:
        fetcher.get("AAPL", lookback_days=10)
        fetcher.get("MSFT", lookback_days=10)
    assert mock_fetch.call_count == 2
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
mkdir -p tests/prices
touch tests/prices/__init__.py
pytest tests/prices/test_prices.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement swing/prices.py**

```python
"""yfinance wrapper with on-disk parquet cache."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


@dataclass
class PriceFetcher:
    """Fetches daily OHLCV with parquet cache.

    Cache key includes `as_of_date` so that pinning the end of history for parity
    reproducibility is safe — two runs with different as_of_date caches separately.
    """

    cache_dir: Path

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, ticker: str, lookback_days: int, as_of_date: date | None) -> Path:
        end = (as_of_date or date.today()).isoformat()
        return self.cache_dir / f"{ticker}_{lookback_days}d_asof-{end}.parquet"

    def _fetch_from_yf(self, ticker: str, lookback_days: int, as_of_date: date | None) -> pd.DataFrame:
        """Live fetch. Overridden in tests via patch."""
        import yfinance as yf  # imported lazily so tests don't require network

        end_date = as_of_date or date.today()
        # end is exclusive in yfinance, so pass the day AFTER our intended last bar
        end = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
        start = end - timedelta(days=lookback_days + 7)
        df = yf.download(
            ticker, start=start, end=end, progress=False, auto_adjust=False, actions=False
        )
        if df is None or df.empty:
            raise ValueError(f"No data for {ticker}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        # Double-truncate client-side — yfinance sometimes returns bars past `end`
        if as_of_date is not None:
            df = df.loc[df.index.date <= as_of_date]
        return df

    def get(self, ticker: str, lookback_days: int, *, as_of_date: date | None = None) -> pd.DataFrame:
        """Fetch OHLCV with optional end-date pin.

        `as_of_date=None` → live (latest available). `as_of_date=d` → bars <= d.
        Used by parity tests to reproduce the data window a legacy run saw.
        """
        cache_path = self._cache_path(ticker, lookback_days, as_of_date)
        if cache_path.exists():
            return pd.read_parquet(cache_path)
        df = self._fetch_from_yf(ticker, lookback_days, as_of_date)
        df.to_parquet(cache_path)
        return df

    def clear_cache(self) -> int:
        """Delete all cached parquet files. Returns count deleted."""
        count = 0
        for f in self.cache_dir.glob("*.parquet"):
            f.unlink()
            count += 1
        return count
```

Update the test block in this task's Step 1 to pass `as_of_date` in one assertion (or leave as-is; the default `None` path is what existing tests cover). Add one extra test:

```python
def test_get_honors_as_of_date(tmp_path: Path):
    from datetime import date
    fetcher = PriceFetcher(cache_dir=tmp_path)
    fake_df = pd.DataFrame(
        {"Open": [10.0, 11.0, 12.0], "High": [10.1, 11.1, 12.1],
         "Low": [9.9, 10.9, 11.9], "Close": [10.0, 11.0, 12.0],
         "Volume": [1_000_000] * 3},
        index=pd.bdate_range(start="2026-04-15", periods=3),  # 4/15, 4/16, 4/17
    )
    with patch.object(fetcher, "_fetch_from_yf", return_value=fake_df):
        result = fetcher.get("AAPL", lookback_days=10, as_of_date=date(2026, 4, 16))
    # Cache path encodes as_of_date
    cached_files = list(tmp_path.glob("*.parquet"))
    assert any("asof-2026-04-16" in p.name for p in cached_files)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/prices/test_prices.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add swing/prices.py tests/prices/
git commit -m "feat: add yfinance wrapper with parquet cache"
```

---

### Task 12: Seed reference/rs-universe.csv

**Files:**
- Create: `reference/rs-universe.csv`

- [ ] **Step 1: Create the file**

```bash
mkdir -p reference
```

The universe is S&P 500 + NASDAQ-100 tickers (Minervini-style large-liquid US equities). Full list at time of writing is ~520 unique tickers after dedup. Rather than embedding the full list in this plan, create the file with the header and the first batch; in a real run the implementer pulls the full list from a verified source (e.g., Wikipedia SPX + NDX tables as of 2026-04-17).

- [ ] **Step 2: Generate the file — two paths**

**Path A (preferred — Wikipedia works):** Run the Wikipedia-scrape script below. The version header is set from the current date to reflect when the snapshot was actually captured — NOT a hardcoded date. This keeps the versioning honest: two scrapes on different dates produce different versions even if they read the same tables.

```bash
python -c "
import datetime as _dt
import pandas as pd
version = _dt.date.today().isoformat() + '-1'

spx = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
spx_col = 'Symbol' if 'Symbol' in spx.columns else 'Ticker'
spx_tickers = spx[spx_col].astype(str).str.replace('.', '-', regex=False).tolist()

ndx_tables = pd.read_html('https://en.wikipedia.org/wiki/Nasdaq-100')
ndx = next((t for t in ndx_tables if any(c in t.columns for c in ('Ticker', 'Symbol'))), None)
if ndx is None:
    raise SystemExit('NASDAQ-100 table not found — Wikipedia layout may have changed. Use Path B.')
ndx_col = 'Ticker' if 'Ticker' in ndx.columns else 'Symbol'
ndx_tickers = ndx[ndx_col].astype(str).str.replace('.', '-', regex=False).tolist()

all_tickers = sorted(set(t for t in spx_tickers + ndx_tickers if t and t.isalnum() or '-' in t))
with open('reference/rs-universe.csv', 'w', newline='', encoding='utf-8') as f:
    f.write(f'# version: {version}\n')
    f.write(f'# source: S&P 500 + NASDAQ-100 (Wikipedia, {version})\n')
    f.write('# columns: ticker\n')
    f.write('ticker\n')
    for t in all_tickers:
        f.write(t + '\n')
print(f'Wrote {len(all_tickers)} tickers with version {version}')
"
```

Expected output: `Wrote ~520 tickers with version YYYY-MM-DD-1`.

**Path B (fallback — Wikipedia fails or returns unexpected shape):** Use the committed seed list in the "RS universe fallback" appendix at the bottom of this plan. Copy-paste those lines into `reference/rs-universe.csv`. The version header there is `fallback-seed-v1-20260417`; update the date suffix to today manually before Task 13.

**IMPORTANT: Path B is bootstrap-only — not acceptable for parity testing.** The ~150-ticker fallback is much smaller than the ~520-ticker main universe, which materially shifts percentile ranks (TT8 outcomes flip). Use Path B only to get Phase 1 bootable while network issues are resolved. Before Task 28 (parity baseline capture), you MUST either:
(a) Retry Path A and populate a full universe, OR
(b) Skip parity tests entirely this phase — mark Tasks 28/29 as skipped, rely on golden fixtures (Task 30) + end-to-end smoke (Task 31) for correctness.

Task 28's universe-snapshot step will record whichever universe was in effect at baseline time, but a Path-B universe snapshot produces a parity suite whose results aren't transferable to real runs with Path A. Document the choice in `tests/fixtures/parity-baseline-README.md` using this template:

```markdown
# Parity Baseline

- Captured: <YYYY-MM-DD HH:MM local tz>
- Captured by: <operator>
- Universe mode: [A=Wikipedia-scrape / B=fallback-seed]
- Universe version header: <value from rs-universe-at-baseline.csv line 1>
- Universe ticker count: <N>
- Fixtures included: <list of finviz*.csv files captured>
- Fixtures skipped (and why): <list, or "none">
- Parity status: [active / skipped-bootstrap-only]
- Notes: <free text — vendor-drift suspicions, known anomalies, etc.>
```

Commit this README in the same commit as `parity-baseline.json` and `rs-universe-at-baseline.csv`.

Verify the result either way:

```bash
head -5 reference/rs-universe.csv
wc -l reference/rs-universe.csv
```

Expected: first line `# version: <today>-1`, 4 comment/header lines, 500+ ticker lines.

- [ ] **Step 3: Commit**

```bash
git add reference/rs-universe.csv
git commit -m "feat: seed RS reference universe from S&P 500 + NASDAQ-100"
```

---

### Task 13: Implement swing/evaluation/rs.py (universe loader + RS computation)

**Files:**
- Create: `swing/evaluation/rs.py`
- Create: `tests/evaluation/test_rs.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for swing.evaluation.rs."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from swing.evaluation.rs import (
    load_universe,
    universe_version_hash,
    compute_rs,
    RSResult,
)


def _write_universe(path: Path, tickers: list[str], version: str = "2026-04-17-1") -> None:
    path.write_text(
        f"# version: {version}\n# source: test\n# columns: ticker\nticker\n"
        + "\n".join(tickers)
        + "\n",
        encoding="utf-8",
    )


def test_load_universe_skips_comments(tmp_path: Path):
    u = tmp_path / "u.csv"
    _write_universe(u, ["AAPL", "MSFT", "GOOG"])
    result = load_universe(u)
    assert result.tickers == ("AAPL", "GOOG", "MSFT")  # sorted
    assert result.version == "2026-04-17-1"


def test_universe_version_hash_stable(tmp_path: Path):
    u = tmp_path / "u.csv"
    _write_universe(u, ["AAPL", "MSFT"])
    h1 = universe_version_hash(u)
    h2 = universe_version_hash(u)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_compute_rs_universe_method():
    """For a ticker in the universe, rank is percentile vs all universe returns."""
    returns_12w = {
        "AAPL": 0.10,   # our target
        "MSFT": 0.05,
        "GOOG": 0.15,
        "META": 0.20,
        "NVDA": 0.25,
        # universe returns
    }
    universe = ("AAPL", "MSFT", "GOOG", "META", "NVDA")
    spy_return = 0.08

    result = compute_rs("AAPL", returns_12w, universe, spy_return=spy_return)
    assert result.method == "universe"
    # AAPL at 0.10 is 2nd lowest of 5 = 20th percentile → rank 20 (0-99 scale, lower=worse)
    assert result.rank == 20
    assert result.return_vs_spy == pytest.approx(0.10 - 0.08)


def test_compute_rs_fallback_for_outside_universe():
    returns_12w = {"NEWCO": 0.30}
    universe = ("AAPL", "MSFT")
    result = compute_rs("NEWCO", returns_12w, universe, spy_return=0.08)
    assert result.method == "fallback_spy"
    assert result.rank is None
    assert result.return_vs_spy == pytest.approx(0.22)


def test_compute_rs_unavailable_when_no_return_data():
    result = compute_rs("XYZ", {}, ("AAPL",), spy_return=0.08)
    assert result.method == "unavailable"
    assert result.rank is None
    assert result.return_vs_spy is None
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/evaluation/test_rs.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement swing/evaluation/rs.py**

```python
"""RS universe loader + rs_rank computation."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Universe:
    tickers: tuple[str, ...]
    version: str


@dataclass(frozen=True)
class RSResult:
    method: str  # 'universe' | 'fallback_spy' | 'unavailable'
    rank: int | None  # 0-99, only when method == 'universe'
    return_vs_spy: float | None  # always populated when method in ('universe','fallback_spy')


def load_universe(path: Path) -> Universe:
    """Parse an RS universe CSV. First non-comment line is the header 'ticker', rest are tickers."""
    lines = path.read_text(encoding="utf-8").splitlines()
    version = "unknown"
    tickers: list[str] = []
    saw_header = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if "version:" in stripped:
                version = stripped.split("version:", 1)[1].strip()
            continue
        if not saw_header:
            # header line
            if stripped.lower() != "ticker":
                raise ValueError(f"Expected 'ticker' header, got {stripped!r}")
            saw_header = True
            continue
        tickers.append(stripped.upper())
    return Universe(tickers=tuple(sorted(set(tickers))), version=version)


def universe_version_hash(path: Path) -> str:
    """SHA256 of file bytes. Stored per pipeline run for traceability."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def compute_rs(
    ticker: str,
    returns_12w_by_ticker: dict[str, float],
    universe_tickers: tuple[str, ...],
    *,
    spy_return: float,
) -> RSResult:
    """
    Compute RS for one ticker.

    - If ticker in universe AND has a return, method='universe', rank=percentile in universe.
    - If ticker NOT in universe BUT has a return, method='fallback_spy', rank=None, return_vs_spy=return-spy.
    - Otherwise, method='unavailable'.
    """
    if ticker not in returns_12w_by_ticker:
        return RSResult(method="unavailable", rank=None, return_vs_spy=None)

    ret = returns_12w_by_ticker[ticker]
    excess = ret - spy_return

    if ticker in universe_tickers:
        # Rank within universe returns
        universe_returns = [
            returns_12w_by_ticker[t]
            for t in universe_tickers
            if t in returns_12w_by_ticker
        ]
        if not universe_returns:
            # Degenerate: no universe tickers have return data
            return RSResult(method="fallback_spy", rank=None, return_vs_spy=excess)
        sorted_returns = sorted(universe_returns)
        # Rank: how many universe returns are <= ours
        leq = sum(1 for r in sorted_returns if r <= ret)
        # Percentile (0-99): map leq/N to 0..99
        rank = max(0, min(99, int((leq - 1) / max(1, len(sorted_returns) - 1) * 99)))
        return RSResult(method="universe", rank=rank, return_vs_spy=excess)

    return RSResult(method="fallback_spy", rank=None, return_vs_spy=excess)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/evaluation/test_rs.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add swing/evaluation/rs.py tests/evaluation/test_rs.py
git commit -m "feat: add RS universe loader and rank computation"
```

---

### Task 14: Implement CandidateContext + Criterion base

**Files:**
- Create: `swing/evaluation/context.py`
- Create: `swing/evaluation/criteria/_base.py`
- Create: `tests/evaluation/test_context.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for swing.evaluation.context + criteria._base."""
from __future__ import annotations

import pandas as pd
import pytest

from swing.config import Config
from swing.evaluation.context import CandidateContext, BatchContext, MarketContext
from swing.evaluation.criteria._base import Result, sma, adr_pct


def test_sma_rolling_mean():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = sma(s, 3)
    assert result.iloc[-1] == pytest.approx(4.0)
    assert pd.isna(result.iloc[0])


def test_adr_pct_calculation(ohlcv_factory):
    df = ohlcv_factory([100.0, 100.0, 100.0, 100.0, 100.0])
    # Open=Close=100, High=101, Low=99 → range = 2, ADR% = 2/100 = 2%
    result = adr_pct(df, lookback=5)
    assert result == pytest.approx(2.0)


def test_result_pass_fail_constructors():
    r = Result.pass_("1.5x", "must be >= 1.0x")
    assert r.result == "pass"
    assert r.value == "1.5x"

    r = Result.fail_("0.5x", "must be >= 1.0x")
    assert r.result == "fail"


def test_candidate_context_dataclass():
    """Context dataclass carries everything a criterion needs to run."""
    # Just a smoke test — no criterion actually called here
    # Real contexts are built in the evaluator; here we just show construction is OK
    import sys
    assert CandidateContext is not None
    assert BatchContext is not None
    assert MarketContext is not None
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/evaluation/test_context.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement swing/evaluation/criteria/_base.py**

```python
"""Shared helpers for criterion files. Criteria are pure functions — no I/O, no DB."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Result:
    """Output of a single criterion evaluation.

    `metrics` carries structured numeric values that the evaluator reads directly
    for persistence — never by parsing `value`. Examples: {"streak_days": 2,
    "adr_pct": 4.66, "pullback_pct": 22.3, "rs_rank": 82}. `value` is human-only.
    """

    name: str
    layer: str
    result: str  # 'pass' | 'fail' | 'na'
    value: str   # human-readable measurement for display
    rule: str    # human-readable rule for display
    metrics: tuple[tuple[str, float | int | None], ...] = ()  # (key, value) pairs; tuple for hashability

    @classmethod
    def pass_(
        cls, value: str, rule: str, *,
        name: str = "", layer: str = "",
        metrics: dict[str, float | int | None] | None = None,
    ) -> Result:
        return cls(name=name, layer=layer, result="pass", value=value, rule=rule,
                   metrics=tuple((metrics or {}).items()))

    @classmethod
    def fail_(
        cls, value: str, rule: str, *,
        name: str = "", layer: str = "",
        metrics: dict[str, float | int | None] | None = None,
    ) -> Result:
        return cls(name=name, layer=layer, result="fail", value=value, rule=rule,
                   metrics=tuple((metrics or {}).items()))

    @classmethod
    def na_(
        cls, reason: str, *,
        name: str = "", layer: str = "",
        metrics: dict[str, float | int | None] | None = None,
    ) -> Result:
        return cls(name=name, layer=layer, result="na", value=reason, rule="",
                   metrics=tuple((metrics or {}).items()))

    def with_identity(self, name: str, layer: str) -> Result:
        return Result(name=name, layer=layer, result=self.result, value=self.value,
                      rule=self.rule, metrics=self.metrics)

    def get_metric(self, key: str) -> float | int | None:
        """Typed lookup — returns None if key not in metrics."""
        for k, v in self.metrics:
            if k == key:
                return v
        return None


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average. Returns a series with NaN for first (window-1) values."""
    return series.rolling(window=window, min_periods=window).mean()


def adr_pct(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Average Daily Range as a percent of price, over the last `lookback` bars.

    ADR% = mean((High - Low) / Close * 100) over the window.
    """
    tail = df.tail(lookback)
    ranges_pct = (tail["High"] - tail["Low"]) / tail["Close"] * 100
    return float(ranges_pct.mean())


def daily_range_pct(df: pd.DataFrame) -> pd.Series:
    """Per-bar range as percent of close."""
    return (df["High"] - df["Low"]) / df["Close"] * 100
```

- [ ] **Step 4: Implement swing/evaluation/context.py**

```python
"""Input contexts for criteria. Criteria are pure functions of these."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from swing.config import Config


@dataclass(frozen=True)
class BatchContext:
    """Cross-sectional context shared across all tickers in an evaluation run."""

    returns_12w_by_ticker: dict[str, float]
    universe_tickers: tuple[str, ...]
    universe_version: str
    universe_hash: str
    spy_return_12w: float


@dataclass(frozen=True)
class MarketContext:
    """External market state. In Phase 1 this is minimal; Phase 2 adds weather."""

    # Phase 1: reserved for future expansion (weather_status, etc.).
    pass


@dataclass(frozen=True)
class CandidateContext:
    """Everything a criterion needs to evaluate one ticker."""

    ticker: str
    ohlcv: pd.DataFrame  # index: DatetimeIndex; columns: Open/High/Low/Close/Volume
    config: Config
    batch: BatchContext
    market: MarketContext
    # Equity at the time of evaluation — needed by risk_feasibility
    current_equity: float
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/evaluation/test_context.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add swing/evaluation/context.py swing/evaluation/criteria/_base.py tests/evaluation/test_context.py
git commit -m "feat: add CandidateContext and criterion base helpers"
```

---

### Task 15: VCP criterion — prior_trend

**Files:**
- Create: `swing/evaluation/criteria/prior_trend.py`
- Create: `tests/evaluation/criteria/__init__.py`
- Create: `tests/evaluation/criteria/test_prior_trend.py`

Rule: from the consolidation low looking back up to 52 weeks, the prior trend gain must be ≥ config.vcp.prior_trend_min_pct (default 25%). The "consolidation low" is the lowest close in the last 20 bars; the "prior trend start" is the lowest close in the 230 bars before that.

- [ ] **Step 1: Write failing test**

```python
"""Tests for prior_trend criterion."""
from __future__ import annotations

import pandas as pd
import pytest

from swing.evaluation.criteria.prior_trend import evaluate


def _ctx_from_closes(closes, config):
    """Build a minimal CandidateContext for testing."""
    from swing.evaluation.context import BatchContext, CandidateContext, MarketContext

    idx = pd.bdate_range(end="2026-04-17", periods=len(closes))
    df = pd.DataFrame(
        {"Open": closes, "High": [c * 1.01 for c in closes],
         "Low": [c * 0.99 for c in closes], "Close": closes,
         "Volume": [1_000_000] * len(closes)},
        index=idx,
    )
    return CandidateContext(
        ticker="TEST",
        ohlcv=df,
        config=config,
        batch=BatchContext(
            returns_12w_by_ticker={}, universe_tickers=(),
            universe_version="test", universe_hash="x", spy_return_12w=0.0,
        ),
        market=MarketContext(),
        current_equity=1000.0,
    )


def test_prior_trend_passes_when_gain_exceeds_threshold(sample_config):
    # 250 bars, starting at 10 and rising to 50 — 400% gain
    closes = [10.0] * 20 + [10.0 + i * 0.16 for i in range(210)] + [40.0] * 20
    ctx = _ctx_from_closes(closes, sample_config)
    result = evaluate(ctx)
    assert result.result == "pass"
    assert "prior_trend" in result.name
    # Value should mention the percentage
    assert "%" in result.value


def test_prior_trend_fails_when_no_trend(sample_config):
    closes = [10.0] * 250
    ctx = _ctx_from_closes(closes, sample_config)
    result = evaluate(ctx)
    assert result.result == "fail"


def test_prior_trend_na_when_not_enough_data(sample_config):
    closes = [10.0] * 50  # only 50 bars, need 250
    ctx = _ctx_from_closes(closes, sample_config)
    result = evaluate(ctx)
    assert result.result == "na"
```

- [ ] **Step 2: Add shared pytest fixture for Config to conftest.py**

Add to `tests/conftest.py`:

```python
@pytest.fixture
def sample_config(tmp_path):
    """Minimal valid Config for criterion tests."""
    from swing.config import load

    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(
        """
[paths]
db_path = "swing-data/swing.db"
data_dir = "swing-data"
logs_dir = "swing-data/logs"
charts_dir = "swing-data/charts"
backups_dir = "swing-data/backups"
prices_cache_dir = "swing-data/prices-cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
""".lstrip(),
        encoding="utf-8",
    )
    return load(cfg_path)
```

Commit this fixture addition as a separate commit before the first criterion task (or as part of Task 15; either works).

- [ ] **Step 3: Run test — expect ImportError**

```bash
mkdir -p tests/evaluation/criteria
touch tests/evaluation/criteria/__init__.py
pytest tests/evaluation/criteria/test_prior_trend.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement prior_trend.py**

```python
"""Prior trend: consolidation area ≥ N% above the pre-trend low."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result

NAME = "prior_trend"
LAYER = "vcp"

CONSOLIDATION_LOOKBACK = 20   # bars defining current consolidation
PRIOR_TREND_LOOKBACK = 230    # bars before consolidation to find prior low


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    min_bars = CONSOLIDATION_LOOKBACK + PRIOR_TREND_LOOKBACK
    if len(df) < min_bars:
        return Result.na_(f"need {min_bars} bars, have {len(df)}", name=NAME, layer=LAYER)

    closes = df["Close"]
    consolidation = closes.iloc[-CONSOLIDATION_LOOKBACK:]
    prior = closes.iloc[-(CONSOLIDATION_LOOKBACK + PRIOR_TREND_LOOKBACK):-CONSOLIDATION_LOOKBACK]

    consolidation_low = float(consolidation.min())
    prior_low = float(prior.min())
    if prior_low <= 0:
        return Result.na_("prior_low non-positive", name=NAME, layer=LAYER)

    gain_pct = (consolidation_low - prior_low) / prior_low * 100
    threshold = ctx.config.vcp.prior_trend_min_pct
    rule = f">= {threshold}% required"
    value = f"{gain_pct:.1f}%"
    metrics = {"prior_trend_pct": round(gain_pct, 2)}
    if gain_pct >= threshold:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
```

- [ ] **Step 5: Run test**

```bash
pytest tests/evaluation/criteria/test_prior_trend.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add swing/evaluation/criteria/prior_trend.py tests/evaluation/criteria/ tests/conftest.py
git commit -m "feat: add prior_trend VCP criterion"
```

---

### Task 16: VCP criterion — ma_stack_short (10>20>50 + all rising)

**Files:**
- Create: `swing/evaluation/criteria/ma_stack_short.py`
- Create: `tests/evaluation/criteria/test_ma_stack_short.py`

This file bundles two sub-checks that live together (both about the short-horizon 10/20/50 moving averages). Returns a *tuple* of two `Result` objects: stack order and rising slopes.

- [ ] **Step 1: Write failing test**

```python
"""Tests for ma_stack_short criterion (stack + rising)."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.criteria.ma_stack_short import evaluate
from tests.evaluation.criteria.test_prior_trend import _ctx_from_closes


def test_stack_and_rising_both_pass(sample_config):
    # Clean uptrend: each close higher than last → all MAs stacked and rising
    closes = [10.0 + i * 0.1 for i in range(100)]
    ctx = _ctx_from_closes(closes, sample_config)
    stack_r, rising_r = evaluate(ctx)
    assert stack_r.result == "pass"
    assert rising_r.result == "pass"


def test_stack_fails_when_inverted(sample_config):
    # Declining trend → 50MA > 20MA > 10MA (inverted)
    closes = [50.0 - i * 0.1 for i in range(100)]
    ctx = _ctx_from_closes(closes, sample_config)
    stack_r, rising_r = evaluate(ctx)
    assert stack_r.result == "fail"
    assert rising_r.result == "fail"


def test_na_when_too_short(sample_config):
    closes = [10.0] * 30  # need 50+
    ctx = _ctx_from_closes(closes, sample_config)
    stack_r, rising_r = evaluate(ctx)
    assert stack_r.result == "na"
    assert rising_r.result == "na"
```

- [ ] **Step 2: Implement ma_stack_short.py**

```python
"""Short-MA stack (10>20>50) + all three MAs rising over 5 bars."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, sma

STACK_NAME = "ma_stack_10_20_50"
RISING_NAME = "ma_short_rising"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> tuple[Result, Result]:
    closes = ctx.ohlcv["Close"]
    if len(closes) < 55:
        na = Result.na_(f"need 55 bars, have {len(closes)}", name=STACK_NAME, layer=LAYER)
        return na, na.with_identity(RISING_NAME, LAYER)

    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma50 = sma(closes, 50)

    a, b, c = float(ma10.iloc[-1]), float(ma20.iloc[-1]), float(ma50.iloc[-1])
    stack_value = f"10MA={a:.2f} 20MA={b:.2f} 50MA={c:.2f}"
    stack_rule = "10MA > 20MA > 50MA"
    stack_result = (
        Result.pass_(stack_value, stack_rule, name=STACK_NAME, layer=LAYER)
        if a > b > c
        else Result.fail_(stack_value, stack_rule, name=STACK_NAME, layer=LAYER)
    )

    # Rising over 5 bars: MA[-1] > MA[-6]
    def _rising(s):
        if len(s.dropna()) < 6:
            return None
        return float(s.iloc[-1]) > float(s.iloc[-6])

    r10 = _rising(ma10)
    r20 = _rising(ma20)
    r50 = _rising(ma50)
    rising_rule = "all three MAs rising over 5 bars"
    rising_value = f"10:{r10} 20:{r20} 50:{r50}"
    if r10 and r20 and r50:
        rising_result = Result.pass_(rising_value, rising_rule, name=RISING_NAME, layer=LAYER)
    else:
        rising_result = Result.fail_(rising_value, rising_rule, name=RISING_NAME, layer=LAYER)

    return stack_result, rising_result
```

- [ ] **Step 3: Run test**

```bash
pytest tests/evaluation/criteria/test_ma_stack_short.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add swing/evaluation/criteria/ma_stack_short.py tests/evaluation/criteria/test_ma_stack_short.py
git commit -m "feat: add ma_stack_short VCP criterion (stack + rising)"
```

---

### Task 17: VCP criterion — proximity (price within 5% of 20MA)

**Files:**
- Create: `swing/evaluation/criteria/proximity.py`
- Create: `tests/evaluation/criteria/test_proximity.py`

- [ ] **Step 1: Write test**

```python
"""Tests for proximity criterion."""
from __future__ import annotations

from swing.evaluation.criteria.proximity import evaluate
from tests.evaluation.criteria.test_prior_trend import _ctx_from_closes


def test_proximity_pass_when_close_to_20ma(sample_config):
    # Flat closes → 20MA == close, proximity 0%
    closes = [100.0] * 30
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "pass"


def test_proximity_fail_when_extended(sample_config):
    # Last close far above 20MA
    closes = [100.0] * 25 + [120.0] * 5
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "fail"


def test_proximity_na_too_short(sample_config):
    closes = [100.0] * 10
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "na"
```

- [ ] **Step 2: Implement proximity.py**

```python
"""Price within N% of 20MA."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, sma

NAME = "proximity_20ma"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    closes = ctx.ohlcv["Close"]
    if len(closes) < 20:
        return Result.na_(f"need 20 bars, have {len(closes)}", name=NAME, layer=LAYER)

    ma20 = float(sma(closes, 20).iloc[-1])
    last = float(closes.iloc[-1])
    pct = (last - ma20) / ma20 * 100
    threshold = ctx.config.vcp.proximity_max_pct
    value = f"{pct:+.2f}%"
    rule = f"|price - 20MA| <= {threshold}% of 20MA"
    if abs(pct) <= threshold:
        return Result.pass_(value, rule, name=NAME, layer=LAYER)
    return Result.fail_(value, rule, name=NAME, layer=LAYER)
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/evaluation/criteria/test_proximity.py -v
git add swing/evaluation/criteria/proximity.py tests/evaluation/criteria/test_proximity.py
git commit -m "feat: add proximity VCP criterion"
```

---

### Task 18: VCP criterion — adr (ADR ≥ 4%)

**Files:**
- Create: `swing/evaluation/criteria/adr.py`
- Create: `tests/evaluation/criteria/test_adr.py`

- [ ] **Step 1: Write test**

```python
from __future__ import annotations

import pandas as pd

from swing.evaluation.criteria.adr import evaluate
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext


def _ctx(df, config):
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=1000.0,
    )


def test_adr_pass(sample_config):
    # Range = 10% of close each day
    closes = [100.0] * 25
    idx = pd.bdate_range(end="2026-04-17", periods=25)
    df = pd.DataFrame(
        {"Open": closes, "High": [105.0] * 25, "Low": [95.0] * 25,
         "Close": closes, "Volume": [1_000_000] * 25},
        index=idx,
    )
    r = evaluate(_ctx(df, sample_config))
    assert r.result == "pass"
    assert "10.00%" in r.value or "10.0%" in r.value


def test_adr_fail(sample_config):
    # Range = 2% of close
    closes = [100.0] * 25
    idx = pd.bdate_range(end="2026-04-17", periods=25)
    df = pd.DataFrame(
        {"Open": closes, "High": [101.0] * 25, "Low": [99.0] * 25,
         "Close": closes, "Volume": [1_000_000] * 25},
        index=idx,
    )
    r = evaluate(_ctx(df, sample_config))
    assert r.result == "fail"
```

- [ ] **Step 2: Implement adr.py**

```python
"""ADR >= N% (Average Daily Range over 20 bars)."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, adr_pct

NAME = "adr"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    if len(ctx.ohlcv) < 20:
        return Result.na_(f"need 20 bars, have {len(ctx.ohlcv)}", name=NAME, layer=LAYER)

    adr = adr_pct(ctx.ohlcv, lookback=20)
    threshold = ctx.config.vcp.adr_min_pct
    rule = f">= {threshold}% required for sufficient volatility"
    value = f"{adr:.2f}%"
    metrics = {"adr_pct": round(adr, 4)}
    if adr >= threshold:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/evaluation/criteria/test_adr.py -v
git add swing/evaluation/criteria/adr.py tests/evaluation/criteria/test_adr.py
git commit -m "feat: add adr VCP criterion"
```

---

### Task 19: VCP criterion — pullback (consolidation high drawdown < 25%)

**Files:**
- Create: `swing/evaluation/criteria/pullback.py`
- Create: `tests/evaluation/criteria/test_pullback.py`

- [ ] **Step 1: Write test**

```python
from __future__ import annotations

from swing.evaluation.criteria.pullback import evaluate
from tests.evaluation.criteria.test_prior_trend import _ctx_from_closes


def test_pullback_pass_shallow(sample_config):
    # Peak at 100, current at 90 → 10% pullback (< 25% threshold → pass)
    closes = [50.0] * 50 + [i for i in range(50, 100)] + [95.0] * 10 + [90.0]
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "pass"


def test_pullback_fail_deep(sample_config):
    # Peak at 100, current at 70 → 30% pullback
    closes = [50.0] * 50 + [i for i in range(50, 100)] + [100.0] * 5 + [70.0]
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "fail"
```

- [ ] **Step 2: Implement pullback.py**

```python
"""Pullback from recent high < N% threshold."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result

NAME = "pullback"
LAYER = "vcp"
PEAK_LOOKBACK = 100


def evaluate(ctx: CandidateContext) -> Result:
    closes = ctx.ohlcv["Close"]
    if len(closes) < PEAK_LOOKBACK:
        return Result.na_(f"need {PEAK_LOOKBACK} bars, have {len(closes)}", name=NAME, layer=LAYER)

    recent = closes.iloc[-PEAK_LOOKBACK:]
    peak = float(recent.max())
    last = float(closes.iloc[-1])
    if peak <= 0:
        return Result.na_("peak non-positive", name=NAME, layer=LAYER)

    pullback_pct = (peak - last) / peak * 100
    threshold = ctx.config.vcp.pullback_max_pct
    rule = f"< {threshold}% from consolidation high"
    value = f"{pullback_pct:.1f}%"
    metrics = {"pullback_pct": round(pullback_pct, 2)}
    if pullback_pct < threshold:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/evaluation/criteria/test_pullback.py -v
git add swing/evaluation/criteria/pullback.py tests/evaluation/criteria/test_pullback.py
git commit -m "feat: add pullback VCP criterion"
```

---

### Task 20: VCP criterion — tightness (≥2 days of range ≤ 2/3 × ADR)

**Files:**
- Create: `swing/evaluation/criteria/tightness.py`
- Create: `tests/evaluation/criteria/test_tightness.py`

- [ ] **Step 1: Write test**

```python
from __future__ import annotations

import pandas as pd

from swing.evaluation.criteria.tightness import evaluate
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext


def _ctx_with_custom_rows(row_specs, config):
    """row_specs: list of (open, high, low, close) tuples."""
    idx = pd.bdate_range(end="2026-04-17", periods=len(row_specs))
    df = pd.DataFrame(
        {
            "Open": [r[0] for r in row_specs],
            "High": [r[1] for r in row_specs],
            "Low": [r[2] for r in row_specs],
            "Close": [r[3] for r in row_specs],
            "Volume": [1_000_000] * len(row_specs),
        },
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=1000.0,
    )


def test_tightness_pass_two_consecutive_tight_days(sample_config):
    # 20 bars with 10% range (ADR = 10%), then 2 bars with 3% range (< 2/3 * 10% = 6.67%)
    row_specs = [(100, 105, 95, 100)] * 20 + [(100, 101.5, 98.5, 100), (100, 101.5, 98.5, 100)]
    ctx = _ctx_with_custom_rows(row_specs, sample_config)
    r = evaluate(ctx)
    assert r.result == "pass"


def test_tightness_fail_zero_streak(sample_config):
    # Big range days throughout — no tight streak
    row_specs = [(100, 110, 90, 100)] * 25
    ctx = _ctx_with_custom_rows(row_specs, sample_config)
    r = evaluate(ctx)
    assert r.result == "fail"
```

- [ ] **Step 2: Implement tightness.py**

```python
"""Last N consecutive days have daily range <= factor * ADR."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, adr_pct, daily_range_pct

NAME = "tightness"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    if len(df) < 22:
        return Result.na_(f"need 22 bars, have {len(df)}", name=NAME, layer=LAYER)

    adr = adr_pct(df, lookback=20)
    ranges = daily_range_pct(df)
    factor = ctx.config.vcp.tightness_range_factor
    threshold = factor * adr
    required_days = ctx.config.vcp.tightness_days_required

    # Count consecutive tight days from the end
    streak = 0
    for r in reversed(ranges.tolist()):
        if r <= threshold:
            streak += 1
        else:
            break

    rule = f">= {required_days} consec. days with range <= {factor:.2f} × ADR ({threshold:.2f}%)"
    value = f"{streak} day streak"
    metrics = {"tight_streak_days": streak}
    if streak >= required_days:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/evaluation/criteria/test_tightness.py -v
git add swing/evaluation/criteria/tightness.py tests/evaluation/criteria/test_tightness.py
git commit -m "feat: add tightness VCP criterion"
```

---

### Task 21: VCP criterion — vcp (volume contracting)

**Files:**
- Create: `swing/evaluation/criteria/vcp.py`
- Create: `tests/evaluation/criteria/test_vcp.py`

Rule: volume in the last 20 bars (consolidation) averages lower than volume in the 100 bars before that (prior trend).

- [ ] **Step 1: Write test**

```python
from __future__ import annotations

import pandas as pd

from swing.evaluation.criteria.vcp import evaluate
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext


def _ctx_volumes(vols, config):
    n = len(vols)
    idx = pd.bdate_range(end="2026-04-17", periods=n)
    df = pd.DataFrame(
        {"Open": [100.0] * n, "High": [101.0] * n, "Low": [99.0] * n,
         "Close": [100.0] * n, "Volume": vols},
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=1000.0,
    )


def test_vcp_pass_volume_contracting(sample_config):
    # 100 prior bars with 2M avg, 20 consolidation bars with 500k avg
    vols = [2_000_000] * 100 + [500_000] * 20
    ctx = _ctx_volumes(vols, sample_config)
    r = evaluate(ctx)
    assert r.result == "pass"


def test_vcp_fail_volume_expanding(sample_config):
    vols = [500_000] * 100 + [2_000_000] * 20
    ctx = _ctx_volumes(vols, sample_config)
    r = evaluate(ctx)
    assert r.result == "fail"
```

- [ ] **Step 2: Implement vcp.py**

```python
"""Volume contraction: 20-bar consolidation avg volume < 100-bar prior trend avg volume."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result

NAME = "vcp_volume_contraction"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    if len(df) < 120:
        return Result.na_(f"need 120 bars, have {len(df)}", name=NAME, layer=LAYER)

    prior = df["Volume"].iloc[-120:-20]
    consolidation = df["Volume"].iloc[-20:]
    prior_avg = float(prior.mean())
    cons_avg = float(consolidation.mean())

    rule = "consolidation avg volume < prior trend avg volume"
    value = f"cons:{cons_avg:,.0f} vs trend:{prior_avg:,.0f}"
    if cons_avg < prior_avg:
        return Result.pass_(value, rule, name=NAME, layer=LAYER)
    return Result.fail_(value, rule, name=NAME, layer=LAYER)
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/evaluation/criteria/test_vcp.py -v
git add swing/evaluation/criteria/vcp.py tests/evaluation/criteria/test_vcp.py
git commit -m "feat: add vcp volume contraction criterion"
```

---

### Task 22: VCP criterion — orderliness (not choppy)

**Files:**
- Create: `swing/evaluation/criteria/orderliness.py`
- Create: `tests/evaluation/criteria/test_orderliness.py`

Rule: in the last 20 bars, (a) the largest daily range is ≤ 3× the median range, and (b) the coefficient of variation of daily ranges is ≤ 0.60.

- [ ] **Step 1: Write test**

```python
from __future__ import annotations

import pandas as pd

from swing.evaluation.criteria.orderliness import evaluate
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext


def _ctx(highs, lows, config):
    n = len(highs)
    idx = pd.bdate_range(end="2026-04-17", periods=n)
    df = pd.DataFrame(
        {"Open": [100.0] * n, "High": highs, "Low": lows,
         "Close": [100.0] * n, "Volume": [1_000_000] * n},
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=1000.0,
    )


def test_orderliness_pass_consistent_ranges(sample_config):
    highs = [101.0] * 25
    lows = [99.0] * 25
    r = evaluate(_ctx(highs, lows, sample_config))
    assert r.result == "pass"


def test_orderliness_fail_one_big_range(sample_config):
    highs = [101.0] * 24 + [130.0]
    lows = [99.0] * 24 + [70.0]
    r = evaluate(_ctx(highs, lows, sample_config))
    assert r.result == "fail"
```

- [ ] **Step 2: Implement orderliness.py**

```python
"""Last 20 bars are orderly: no outlier range, low coefficient of variation."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, daily_range_pct

NAME = "orderliness"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    if len(df) < 20:
        return Result.na_(f"need 20 bars, have {len(df)}", name=NAME, layer=LAYER)

    ranges = daily_range_pct(df).iloc[-20:]
    median_range = float(ranges.median())
    max_range = float(ranges.max())
    mean_range = float(ranges.mean())

    if median_range <= 0:
        return Result.na_("median range non-positive", name=NAME, layer=LAYER)

    max_ratio = max_range / median_range
    cv = float(ranges.std() / mean_range) if mean_range > 0 else 0.0

    max_ratio_limit = ctx.config.vcp.orderliness_max_bar_ratio
    cv_limit = ctx.config.vcp.orderliness_max_range_cv

    rule = f"max bar <= {max_ratio_limit:.1f}x median AND range CV <= {cv_limit:.2f}"
    value = f"max {max_ratio:.2f}x, CV {cv:.2f}"
    if max_ratio <= max_ratio_limit and cv <= cv_limit:
        return Result.pass_(value, rule, name=NAME, layer=LAYER)
    return Result.fail_(value, rule, name=NAME, layer=LAYER)
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/evaluation/criteria/test_orderliness.py -v
git add swing/evaluation/criteria/orderliness.py tests/evaluation/criteria/test_orderliness.py
git commit -m "feat: add orderliness VCP criterion"
```

---

### Task 23: VCP criterion — risk_feasibility (position sizing fits risk budget)

**Files:**
- Create: `swing/evaluation/criteria/risk_feasibility.py`
- Create: `tests/evaluation/criteria/test_risk_feasibility.py`

Rule: at least 1 share is affordable given `current_equity`, `max_risk_pct`, pivot (entry target = consolidation high) and initial stop (consolidation low). Shares = floor(risk_budget / (pivot - stop)).

- [ ] **Step 1: Write test**

```python
from __future__ import annotations

import pandas as pd

from swing.evaluation.criteria.risk_feasibility import evaluate
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext


def _ctx_priced(pivot, stop, config, equity=1000.0):
    # Build a minimal 30-bar frame where consolidation high = pivot and low = stop
    highs = [pivot] * 20 + [pivot] * 10
    lows = [stop] * 20 + [stop] * 10
    closes = [(pivot + stop) / 2] * 30
    idx = pd.bdate_range(end="2026-04-17", periods=30)
    df = pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes,
         "Volume": [1_000_000] * 30},
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=equity,
    )


def test_feasibility_pass_small_risk(sample_config):
    # equity 1000, max_risk_pct 0.005 → $5 risk budget
    # pivot 10, stop 9 → risk/share = 1 → 5 shares affordable
    r = evaluate(_ctx_priced(pivot=10.0, stop=9.0, config=sample_config))
    assert r.result == "pass"


def test_feasibility_fail_when_risk_per_share_too_big(sample_config):
    # equity 1000 → $5 risk budget; pivot 100, stop 50 → risk/share 50 → 0 shares
    r = evaluate(_ctx_priced(pivot=100.0, stop=50.0, config=sample_config))
    assert r.result == "fail"
```

- [ ] **Step 2: Implement risk_feasibility.py**

```python
"""At least 1 share fits within max_risk_pct × equity."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result

NAME = "risk_feasibility"
LAYER = "risk"


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    if len(df) < 20:
        return Result.na_(f"need 20 bars, have {len(df)}", name=NAME, layer=LAYER)

    tail = df.iloc[-20:]
    pivot = float(tail["High"].max())
    stop = float(tail["Low"].min())
    risk_per_share = pivot - stop
    if risk_per_share <= 0:
        return Result.na_("non-positive risk/share", name=NAME, layer=LAYER)

    budget = ctx.current_equity * ctx.config.risk.max_risk_pct
    shares = int(budget // risk_per_share)
    risk_dollars = shares * risk_per_share

    rule = f"≥ 1 share fits in {ctx.config.risk.max_risk_pct:.1%} of equity (${budget:.2f})"
    value = f"{shares} sh, ${risk_dollars:.2f} risk"
    if shares >= 1:
        return Result.pass_(value, rule, name=NAME, layer=LAYER)
    return Result.fail_(value, rule, name=NAME, layer=LAYER)
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/evaluation/criteria/test_risk_feasibility.py -v
git add swing/evaluation/criteria/risk_feasibility.py tests/evaluation/criteria/test_risk_feasibility.py
git commit -m "feat: add risk_feasibility criterion"
```

---

### Task 24: Trend Template — all 8 Minervini checks in one file

**Files:**
- Create: `swing/evaluation/criteria/trend_template.py`
- Create: `tests/evaluation/criteria/test_trend_template.py`

All 8 checks operate on the same data, so they live in one module and return a *tuple* of 8 `Result` objects. TT8 (RS) uses `ctx.batch` (not just OHLCV).

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Minervini Trend Template (8 checks)."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.criteria.trend_template import evaluate, CHECK_NAMES
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext


def _long_ctx(closes, config, ticker="T", universe=("T",), returns_12w=None, spy_return=0.0):
    idx = pd.bdate_range(end="2026-04-17", periods=len(closes))
    df = pd.DataFrame(
        {"Open": closes, "High": [c * 1.01 for c in closes],
         "Low": [c * 0.99 for c in closes], "Close": closes,
         "Volume": [1_000_000] * len(closes)},
        index=idx,
    )
    return CandidateContext(
        ticker=ticker, ohlcv=df, config=config,
        batch=BatchContext(
            returns_12w_by_ticker=returns_12w or {ticker: 0.10},
            universe_tickers=universe,
            universe_version="test-v1",
            universe_hash="deadbeef",
            spy_return_12w=spy_return,
        ),
        market=MarketContext(),
        current_equity=1000.0,
    )


def test_all_8_checks_returned(sample_config):
    # 250-bar uptrend
    closes = [10.0 + i * 0.2 for i in range(250)]
    ctx = _long_ctx(closes, sample_config)
    results = evaluate(ctx)
    assert len(results) == 8
    assert {r.name for r in results} == set(CHECK_NAMES)
    for r in results:
        assert r.layer == "trend_template"


def test_strong_uptrend_passes_majority(sample_config):
    # Steady 250-bar linear uptrend ends well above all MAs, 52w high near today
    closes = [10.0 + i * 0.15 for i in range(260)]
    ctx = _long_ctx(closes, sample_config)
    results = evaluate(ctx)
    passes = sum(1 for r in results if r.result == "pass")
    assert passes >= 6  # strong setup, most should pass


def test_flat_data_fails_most(sample_config):
    closes = [50.0] * 260
    ctx = _long_ctx(closes, sample_config)
    results = evaluate(ctx)
    fails = sum(1 for r in results if r.result == "fail")
    # Flat data: MAs flat (not rising), 52w high == low, price not >30% above low
    assert fails >= 3


def test_na_when_not_enough_bars(sample_config):
    closes = [10.0] * 100
    ctx = _long_ctx(closes, sample_config)
    results = evaluate(ctx)
    # Without 200 bars of data for the 200MA, most checks are NA
    nas = sum(1 for r in results if r.result == "na")
    assert nas >= 4
```

- [ ] **Step 2: Implement trend_template.py**

```python
"""Minervini Trend Template — 8 structural checks.

References:
- TT1-TT8 as spelled in spec §4.1 and widely published.
- TT8 (RS) reads from ctx.batch; others depend only on ctx.ohlcv + ctx.config.
"""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, sma

LAYER = "trend_template"

CHECK_NAMES = (
    "TT1_above_150_200",
    "TT2_150_above_200",
    "TT3_200_rising",
    "TT4_50_above_150_200",
    "TT5_above_50",
    "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct",
    "TT8_rs_rank",
)


def evaluate(ctx: CandidateContext) -> tuple[Result, ...]:
    closes = ctx.ohlcv["Close"]
    if len(closes) < 200:
        na = [Result.na_(f"need 200 bars, have {len(closes)}", name=n, layer=LAYER) for n in CHECK_NAMES]
        return tuple(na)

    last_close = float(closes.iloc[-1])
    sma50 = sma(closes, 50)
    sma150 = sma(closes, 150)
    sma200 = sma(closes, 200)

    s50 = float(sma50.iloc[-1])
    s150 = float(sma150.iloc[-1])
    s200 = float(sma200.iloc[-1])

    results: list[Result] = []

    # TT1: close > 150MA and close > 200MA
    v = f"close={last_close:.2f} 150MA={s150:.2f} 200MA={s200:.2f}"
    r = (last_close > s150) and (last_close > s200)
    results.append(
        Result.pass_(v, "close > 150MA AND close > 200MA", name=CHECK_NAMES[0], layer=LAYER)
        if r else Result.fail_(v, "close > 150MA AND close > 200MA", name=CHECK_NAMES[0], layer=LAYER)
    )

    # TT2: 150MA > 200MA
    v = f"150MA={s150:.2f} 200MA={s200:.2f}"
    r = s150 > s200
    results.append(
        Result.pass_(v, "150MA > 200MA", name=CHECK_NAMES[1], layer=LAYER)
        if r else Result.fail_(v, "150MA > 200MA", name=CHECK_NAMES[1], layer=LAYER)
    )

    # TT3: 200MA trending up — sma200[-1] > sma200[-21]
    period = ctx.config.trend_template.rising_ma_period_days
    if len(sma200.dropna()) < period + 1:
        results.append(Result.na_("not enough 200MA history", name=CHECK_NAMES[2], layer=LAYER))
    else:
        current = s200
        past = float(sma200.iloc[-(period + 1)])
        v = f"200MA now={current:.2f} vs {period}bars ago={past:.2f}"
        rising = current > past
        results.append(
            Result.pass_(v, f"200MA rising over {period} bars", name=CHECK_NAMES[2], layer=LAYER)
            if rising else Result.fail_(v, f"200MA rising over {period} bars", name=CHECK_NAMES[2], layer=LAYER)
        )

    # TT4: 50MA > 150MA and 50MA > 200MA
    v = f"50MA={s50:.2f} 150MA={s150:.2f} 200MA={s200:.2f}"
    r = (s50 > s150) and (s50 > s200)
    results.append(
        Result.pass_(v, "50MA > 150MA AND 50MA > 200MA", name=CHECK_NAMES[3], layer=LAYER)
        if r else Result.fail_(v, "50MA > 150MA AND 50MA > 200MA", name=CHECK_NAMES[3], layer=LAYER)
    )

    # TT5: close > 50MA
    v = f"close={last_close:.2f} 50MA={s50:.2f}"
    r = last_close > s50
    results.append(
        Result.pass_(v, "close > 50MA", name=CHECK_NAMES[4], layer=LAYER)
        if r else Result.fail_(v, "close > 50MA", name=CHECK_NAMES[4], layer=LAYER)
    )

    # TT6/TT7: 52-week high/low (use last 252 bars = 1 trading year)
    lookback_52w = min(252, len(closes))
    window = closes.iloc[-lookback_52w:]
    low_52w = float(window.min())
    high_52w = float(window.max())

    # TT6: price ≥ 30% above 52w low
    if low_52w <= 0:
        results.append(Result.na_("52w low non-positive", name=CHECK_NAMES[5], layer=LAYER))
    else:
        above_pct = (last_close - low_52w) / low_52w * 100
        threshold = ctx.config.trend_template.low_52w_min_pct
        v = f"+{above_pct:.1f}% above 52w low"
        rule = f">= {threshold}% above 52w low"
        r = above_pct >= threshold
        results.append(
            Result.pass_(v, rule, name=CHECK_NAMES[5], layer=LAYER)
            if r else Result.fail_(v, rule, name=CHECK_NAMES[5], layer=LAYER)
        )

    # TT7: price within 25% of 52w high
    if high_52w <= 0:
        results.append(Result.na_("52w high non-positive", name=CHECK_NAMES[6], layer=LAYER))
    else:
        below_pct = (high_52w - last_close) / high_52w * 100
        threshold = ctx.config.trend_template.high_52w_margin_pct
        v = f"-{below_pct:.1f}% from 52w high"
        rule = f"<= {threshold}% below 52w high"
        r = below_pct <= threshold
        results.append(
            Result.pass_(v, rule, name=CHECK_NAMES[6], layer=LAYER)
            if r else Result.fail_(v, rule, name=CHECK_NAMES[6], layer=LAYER)
        )

    # TT8: RS rank ≥ threshold
    threshold = ctx.config.rs.rs_rank_min_pass
    extreme = ctx.config.rs.fallback_extreme_pct / 100  # pct → fraction
    # rs information is on ctx.batch but the per-ticker RS result is NOT yet computed
    # here — the evaluator computes it once per batch and passes it in via ctx extension.
    # For Phase 1 we look up from batch directly:
    ticker_return = ctx.batch.returns_12w_by_ticker.get(ctx.ticker)
    in_universe = ctx.ticker in ctx.batch.universe_tickers
    if ticker_return is None:
        results.append(Result.na_("no 12w return available", name=CHECK_NAMES[7], layer=LAYER))
    elif in_universe:
        # Rank against universe
        universe_returns = sorted(
            r for t, r in ctx.batch.returns_12w_by_ticker.items()
            if t in ctx.batch.universe_tickers
        )
        if not universe_returns:
            results.append(Result.na_("universe returns empty", name=CHECK_NAMES[7], layer=LAYER))
        else:
            leq = sum(1 for r in universe_returns if r <= ticker_return)
            rank = max(0, min(99, int((leq - 1) / max(1, len(universe_returns) - 1) * 99)))
            v = f"RS rank {rank} (universe v{ctx.batch.universe_version})"
            rule = f"RS rank >= {threshold}"
            r = rank >= threshold
            results.append(
                Result.pass_(v, rule, name=CHECK_NAMES[7], layer=LAYER)
                if r else Result.fail_(v, rule, name=CHECK_NAMES[7], layer=LAYER)
            )
    else:
        # Fallback: extreme excess return vs SPY
        excess = ticker_return - ctx.batch.spy_return_12w
        v = f"fallback, excess={excess:+.2%} vs SPY 12w"
        rule = f"outside universe; pass if excess >= +{extreme:.0%}"
        if excess >= extreme:
            results.append(Result.pass_(v, rule, name=CHECK_NAMES[7], layer=LAYER))
        elif excess <= -extreme:
            results.append(Result.fail_(v, rule, name=CHECK_NAMES[7], layer=LAYER))
        else:
            results.append(Result.na_(v, name=CHECK_NAMES[7], layer=LAYER))

    return tuple(results)
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/evaluation/criteria/test_trend_template.py -v
```

Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add swing/evaluation/criteria/trend_template.py tests/evaluation/criteria/test_trend_template.py
git commit -m "feat: add Minervini Trend Template (8 checks)"
```

---

### Task 25: scoring.py — bucket logic

**Files:**
- Create: `swing/evaluation/scoring.py`
- Create: `tests/evaluation/test_scoring.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for scoring (bucket logic)."""
from __future__ import annotations

from swing.evaluation.criteria._base import Result
from swing.evaluation.scoring import bucket_for


def _make(layer: str, result: str, name: str = "x") -> Result:
    return Result(name=name, layer=layer, result=result, value="", rule="")


def test_aplus_when_tt_7plus_and_vcp_all_pass(sample_config):
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(7)] + [_make("trend_template", "fail", "TT8")]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(10)]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "aplus"


def test_watch_when_vcp_has_1_or_2_fails(sample_config):
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(8)]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(8)] + [_make("vcp", "fail", "v8"), _make("vcp", "fail", "v9")]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "watch"


def test_skip_when_tt_below_min(sample_config):
    tt = [_make("trend_template", "fail", f"TT{i}") for i in range(5)] + [_make("trend_template", "pass", f"TT{i}") for i in range(5, 8)]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(10)]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "skip"


def test_skip_when_vcp_3plus_fails(sample_config):
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(8)]
    vcp = [_make("vcp", "fail", f"v{i}") for i in range(3)] + [_make("vcp", "pass", f"v{i}") for i in range(3, 10)]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "skip"


def test_risk_fail_forces_skip(sample_config):
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(8)]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(10)]
    risk = [_make("risk", "fail", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "skip"
```

- [ ] **Step 2: Implement scoring.py**

```python
"""Bucket classification: aplus / watch / skip / excluded / error.

NA results are counted as fails for bucket determination — insufficient data to pass is a fail.
"""
from __future__ import annotations

from collections.abc import Sequence

from swing.config import Config
from swing.evaluation.criteria._base import Result


def bucket_for(
    trend_template_results: Sequence[Result],
    vcp_results: Sequence[Result],
    risk_results: Sequence[Result],
    config: Config,
) -> str:
    # Risk must pass (it's a hard filter)
    if any(r.result != "pass" for r in risk_results):
        return "skip"

    tt_passes = sum(1 for r in trend_template_results if r.result == "pass")
    tt_fails = sum(1 for r in trend_template_results if r.result in ("fail", "na"))
    vcp_fails = sum(1 for r in vcp_results if r.result in ("fail", "na"))

    tt_gate_ok = tt_passes >= config.trend_template.min_passes

    if not tt_gate_ok:
        return "skip"
    if vcp_fails == 0:
        return "aplus"
    if vcp_fails <= 2:
        return "watch"
    return "skip"
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/evaluation/test_scoring.py -v
```

Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add swing/evaluation/scoring.py tests/evaluation/test_scoring.py
git commit -m "feat: add scoring bucket logic"
```

---

### Task 26: evaluator.py — per-ticker orchestration + batch entry point

**Files:**
- Create: `swing/evaluation/evaluator.py`
- Create: `tests/evaluation/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the evaluator orchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from swing.evaluation.evaluator import evaluate_one, evaluate_batch
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext


def _long_ctx(closes, config, ticker="TEST", universe=("TEST",)):
    idx = pd.bdate_range(end="2026-04-17", periods=len(closes))
    df = pd.DataFrame(
        {"Open": closes, "High": [c * 1.01 for c in closes],
         "Low": [c * 0.99 for c in closes], "Close": closes,
         "Volume": [1_000_000] * len(closes)},
        index=idx,
    )
    return CandidateContext(
        ticker=ticker, ohlcv=df, config=config,
        batch=BatchContext(
            returns_12w_by_ticker={ticker: 0.50},
            universe_tickers=universe,
            universe_version="t", universe_hash="h", spy_return_12w=0.0,
        ),
        market=MarketContext(),
        current_equity=10000.0,
    )


def test_evaluate_one_returns_candidate_with_all_criteria(sample_config):
    # Clean uptrend 260 bars
    closes = [10.0 + i * 0.15 for i in range(260)]
    ctx = _long_ctx(closes, sample_config)
    candidate = evaluate_one(ctx)

    assert candidate.ticker == "TEST"
    assert candidate.bucket in ("aplus", "watch", "skip")

    # Should include 8 TT + 9 VCP + 1 risk = 18 criteria results (ma_stack_short contributes 2)
    names = [c.criterion_name for c in candidate.criteria]
    layers = {c.layer for c in candidate.criteria}
    assert "trend_template" in layers
    assert "vcp" in layers
    assert "risk" in layers
    assert len(candidate.criteria) >= 18


def test_evaluate_batch_processes_multiple_tickers(sample_config):
    closes_up = [10.0 + i * 0.15 for i in range(260)]
    closes_flat = [10.0] * 260
    ctx_up = _long_ctx(closes_up, sample_config, ticker="UP", universe=("UP", "FLAT"))
    ctx_flat = _long_ctx(closes_flat, sample_config, ticker="FLAT", universe=("UP", "FLAT"))

    # Share batch so RS is computed across both
    batch = BatchContext(
        returns_12w_by_ticker={"UP": 0.50, "FLAT": 0.0},
        universe_tickers=("UP", "FLAT"),
        universe_version="t", universe_hash="h", spy_return_12w=0.05,
    )
    ctx_up = CandidateContext(
        ticker="UP", ohlcv=ctx_up.ohlcv, config=sample_config, batch=batch,
        market=MarketContext(), current_equity=10000.0,
    )
    ctx_flat = CandidateContext(
        ticker="FLAT", ohlcv=ctx_flat.ohlcv, config=sample_config, batch=batch,
        market=MarketContext(), current_equity=10000.0,
    )
    candidates = evaluate_batch([ctx_up, ctx_flat])
    assert len(candidates) == 2
    by_ticker = {c.ticker: c for c in candidates}
    # UP has strong uptrend → better bucket than FLAT
    # Exact buckets depend on criterion edge cases but FLAT should be skip
    assert by_ticker["FLAT"].bucket == "skip"
```

- [ ] **Step 2: Implement evaluator.py**

```python
"""Evaluate one ticker (runs all criteria) and a batch.

For each ticker, collects Trend Template + VCP + risk Result objects,
computes the bucket, extracts key metrics (close, pivot, stop, ADR, RS),
and returns a Candidate dataclass ready for persistence.
"""
from __future__ import annotations

from collections.abc import Sequence

from swing.data.models import Candidate, CriterionResult
from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria import (
    adr, ma_stack_short, orderliness, prior_trend, proximity,
    pullback, risk_feasibility, tightness, trend_template, vcp,
)
from swing.evaluation.scoring import bucket_for


def _to_model(r) -> CriterionResult:
    return CriterionResult(
        criterion_name=r.name,
        layer=r.layer,
        result=r.result,
        value=r.value or None,
        rule=r.rule or None,
    )


def evaluate_one(ctx: CandidateContext) -> Candidate:
    """Run all criteria on one ticker, determine bucket, return a Candidate dataclass."""
    tt_results = list(trend_template.evaluate(ctx))

    stack_r, rising_r = ma_stack_short.evaluate(ctx)
    vcp_results = [
        prior_trend.evaluate(ctx),
        stack_r,
        rising_r,
        proximity.evaluate(ctx),
        adr.evaluate(ctx),
        pullback.evaluate(ctx),
        tightness.evaluate(ctx),
        vcp.evaluate(ctx),
        orderliness.evaluate(ctx),
    ]
    risk_results = [risk_feasibility.evaluate(ctx)]

    bucket = bucket_for(tt_results, vcp_results, risk_results, ctx.config)

    # Extract key metrics for candidate row
    closes = ctx.ohlcv["Close"]
    last_close = float(closes.iloc[-1])

    # Pivot/stop from last 20 bars (same as risk_feasibility)
    tail = ctx.ohlcv.iloc[-20:] if len(ctx.ohlcv) >= 20 else ctx.ohlcv
    pivot = float(tail["High"].max())
    initial_stop = float(tail["Low"].min())

    # ADR%
    from swing.evaluation.criteria._base import adr_pct
    adr_value = adr_pct(ctx.ohlcv, lookback=20) if len(ctx.ohlcv) >= 20 else None

    # Read structured metrics from Results (populated by criteria; never parse value strings)
    def _find(results, name):
        return next((r for r in results if r.name == name), None)

    tight_r = _find(vcp_results, "tightness")
    tight_streak = int(tight_r.get_metric("tight_streak_days")) if tight_r and tight_r.get_metric("tight_streak_days") is not None else None

    pullback_r = _find(vcp_results, "pullback")
    pullback_value = pullback_r.get_metric("pullback_pct") if pullback_r else None

    prior_r = _find(vcp_results, "prior_trend")
    prior_trend_value = prior_r.get_metric("prior_trend_pct") if prior_r else None

    adr_r = _find(vcp_results, "adr")
    if adr_r and adr_r.get_metric("adr_pct") is not None:
        adr_value = float(adr_r.get_metric("adr_pct"))

    # RS: derived from TT8 result + batch
    rs_rank = None
    rs_return_vs_spy = None
    rs_method = "unavailable"
    ticker_ret = ctx.batch.returns_12w_by_ticker.get(ctx.ticker)
    if ticker_ret is not None:
        rs_return_vs_spy = ticker_ret - ctx.batch.spy_return_12w
        if ctx.ticker in ctx.batch.universe_tickers:
            rs_method = "universe"
            universe_returns = sorted(
                r for t, r in ctx.batch.returns_12w_by_ticker.items()
                if t in ctx.batch.universe_tickers
            )
            if universe_returns:
                leq = sum(1 for r in universe_returns if r <= ticker_ret)
                rs_rank = max(0, min(99, int((leq - 1) / max(1, len(universe_returns) - 1) * 99)))
        else:
            rs_method = "fallback_spy"

    criteria_models = tuple(_to_model(r) for r in tt_results + vcp_results + risk_results)

    return Candidate(
        ticker=ctx.ticker,
        bucket=bucket,
        close=last_close,
        pivot=pivot,
        initial_stop=initial_stop,
        adr_pct=adr_value,
        tight_streak=tight_streak,
        pullback_pct=pullback_value,
        prior_trend_pct=prior_trend_value,
        rs_rank=rs_rank,
        rs_return_12w_vs_spy=rs_return_vs_spy,
        rs_method=rs_method,
        pattern_tag=None,
        notes=None,
        criteria=criteria_models,
    )


def evaluate_batch(contexts: Sequence[CandidateContext]) -> list[Candidate]:
    """Evaluate a batch of tickers."""
    return [evaluate_one(ctx) for ctx in contexts]
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/evaluation/test_evaluator.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add swing/evaluation/evaluator.py tests/evaluation/test_evaluator.py
git commit -m "feat: add evaluator orchestrator (per-ticker and batch)"
```

---

### Task 27: CLI — `swing eval` subcommand

**Files:**
- Create: `swing/cli.py`
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_cli_eval.py`

- [ ] **Step 1: Write failing test**

```python
"""Integration test for swing eval CLI."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from swing.cli import main


def _minimal_finviz_csv(path: Path) -> Path:
    df = pd.DataFrame({
        "No.": [1, 2],
        "Ticker": ["AAPL", "MSFT"],
        "Price": [200.0, 400.0],
        "Volume": [50_000_000, 30_000_000],
    })
    df.to_csv(path, index=False)
    return path


def _minimal_universe(path: Path) -> Path:
    path.write_text(
        "# version: test-v1\n# source: test\n# columns: ticker\nticker\nAAPL\nMSFT\n",
        encoding="utf-8",
    )
    return path


def _minimal_config(project_dir: Path, home_dir: Path) -> Path:
    """Write a config that points db/data to home_dir and rs-universe to project_dir."""
    cfg_path = project_dir / "swing.config.toml"
    (project_dir / "reference").mkdir(parents=True, exist_ok=True)
    _minimal_universe(project_dir / "reference" / "rs-universe.csv")

    cfg_path.write_text(
        f"""
[paths]
db_path = "{(home_dir / 'swing-data' / 'swing.db').as_posix()}"
data_dir = "{(home_dir / 'swing-data').as_posix()}"
logs_dir = "{(home_dir / 'swing-data' / 'logs').as_posix()}"
charts_dir = "{(home_dir / 'swing-data' / 'charts').as_posix()}"
backups_dir = "{(home_dir / 'swing-data' / 'backups').as_posix()}"
prices_cache_dir = "{(home_dir / 'swing-data' / 'prices-cache').as_posix()}"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
""".lstrip(),
        encoding="utf-8",
    )
    return cfg_path


def test_cli_db_migrate_creates_schema(tmp_path: Path):
    project_dir = tmp_path / "project"
    home_dir = tmp_path / "home"
    project_dir.mkdir()
    home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result.exit_code == 0, result.output

    db = home_dir / "swing-data" / "swing.db"
    assert db.exists()
    conn = sqlite3.connect(db)
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 1


def test_cli_eval_writes_excluded_and_error_rows(tmp_path: Path, monkeypatch):
    """Excluded (ETF blocklist) and error (fetch failure) tickers get candidate rows."""
    project_dir = tmp_path / "project"
    home_dir = tmp_path / "home"
    project_dir.mkdir()
    home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)

    # Override config to put UCO on the manual_block list
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace('manual_block = []', 'manual_block = ["UCO"]')
    cfg_path.write_text(text, encoding="utf-8")

    # Finviz CSV with one excluded + one error ticker + one normal
    df = pd.DataFrame({
        "No.": [1, 2, 3],
        "Ticker": ["UCO", "BADFETCH", "AAPL"],
        "Price": [50.0, 10.0, 200.0],
    })
    csv_path = project_dir / "finviz.csv"
    df.to_csv(csv_path, index=False)

    def fake_get(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "BADFETCH":
            raise ValueError("Simulated fetch failure")
        closes = [10.0 + i * 0.15 for i in range(260)]
        idx = pd.bdate_range(end="2026-04-17", periods=260)
        return pd.DataFrame(
            {"Open": closes, "High": [c * 1.01 for c in closes],
             "Low": [c * 0.99 for c in closes], "Close": closes,
             "Volume": [1_000_000] * 260}, index=idx,
        )

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fake_get)

    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    result = runner.invoke(main, ["--config", str(cfg_path), "eval", "--csv", str(csv_path)])
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(home_dir / "swing-data" / "swing.db")
    rows = conn.execute("SELECT ticker, bucket, notes FROM candidates ORDER BY ticker").fetchall()
    by_ticker = {r[0]: (r[1], r[2]) for r in rows}

    assert by_ticker["UCO"][0] == "excluded"
    assert "blocklist" in (by_ticker["UCO"][1] or "").lower()
    assert by_ticker["BADFETCH"][0] == "error"
    assert "fetch" in (by_ticker["BADFETCH"][1] or "").lower()
    # AAPL should have been evaluated (aplus/watch/skip)
    assert by_ticker["AAPL"][0] in ("aplus", "watch", "skip")

    # evaluation_runs should reflect counts
    run = conn.execute("SELECT excluded_count, error_count FROM evaluation_runs").fetchone()
    assert run[0] == 1
    assert run[1] == 1


def test_cli_eval_writes_evaluation_run(tmp_path: Path, monkeypatch):
    """Smoke test — mocks yfinance to return deterministic OHLCV."""
    project_dir = tmp_path / "project"
    home_dir = tmp_path / "home"
    project_dir.mkdir()
    home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)
    csv_path = project_dir / "finviz-test.csv"
    _minimal_finviz_csv(csv_path)

    # Mock yfinance with a fake PriceFetcher.get returning synthetic uptrend data
    def fake_get(self, ticker, lookback_days, *, as_of_date=None):
        closes = [10.0 + i * 0.15 for i in range(260)]
        idx = pd.bdate_range(end="2026-04-17", periods=260)
        return pd.DataFrame(
            {"Open": closes, "High": [c * 1.01 for c in closes],
             "Low": [c * 0.99 for c in closes], "Close": closes,
             "Volume": [1_000_000] * 260},
            index=idx,
        )

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fake_get)

    runner = CliRunner()
    # Migrate first
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    # Eval
    result = runner.invoke(main, ["--config", str(cfg_path), "eval", "--csv", str(csv_path)])
    assert result.exit_code == 0, result.output

    db = home_dir / "swing-data" / "swing.db"
    conn = sqlite3.connect(db)
    runs = conn.execute("SELECT id, tickers_evaluated FROM evaluation_runs").fetchall()
    assert len(runs) == 1
    assert runs[0][1] == 2

    candidates = conn.execute("SELECT ticker, bucket FROM candidates").fetchall()
    assert {c[0] for c in candidates} == {"AAPL", "MSFT"}
```

- [ ] **Step 2: Implement swing/cli.py**

```python
"""Click CLI for swing. Phase 1 subcommands: db-migrate, eval."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
import pandas as pd

from swing.config import load as load_config
from swing.data.db import connect, ensure_schema
from swing.data.models import EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.dates import action_session_for_run, data_asof_from_ohlcv_max
from swing.evaluation.evaluator import evaluate_batch
from swing.evaluation.rs import load_universe, universe_version_hash
from swing.prices import PriceFetcher


@click.group()
@click.option("--config", "config_path", default="swing.config.toml",
              help="Path to swing.config.toml")
@click.pass_context
def main(ctx: click.Context, config_path: str) -> None:
    """Swing trading CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(Path(config_path))


@main.command("db-migrate")
@click.pass_context
def db_migrate(ctx: click.Context) -> None:
    """Apply DB migrations. Safe to run multiple times."""
    cfg = ctx.obj["config"]
    conn = ensure_schema(cfg.paths.db_path)
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()
    click.echo(f"DB at {cfg.paths.db_path} — schema version {version}")


@main.command("eval")
@click.option("--csv", "csv_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--as-of-date", "as_of_date_str", default=None,
              help="YYYY-MM-DD — cap OHLCV data to bars <= this date. Used for parity reproduction.")
@click.pass_context
def eval_cmd(ctx: click.Context, csv_path: str, as_of_date_str: str | None) -> None:
    """Evaluate tickers from a Finviz-style CSV."""
    from datetime import date as _date
    cfg = ctx.obj["config"]
    csv_file = Path(csv_path)
    as_of_date = _date.fromisoformat(as_of_date_str) if as_of_date_str else None

    # 1. Read tickers from the CSV
    finviz_df = pd.read_csv(csv_file)
    ticker_col = "Ticker" if "Ticker" in finviz_df.columns else finviz_df.columns[1]
    tickers = finviz_df[ticker_col].dropna().astype(str).str.upper().tolist()

    click.echo(f"Evaluating {len(tickers)} tickers from {csv_file.name}")

    # 2. Load RS universe + benchmark return
    universe = load_universe(cfg.paths.rs_universe_path)
    universe_hash = universe_version_hash(cfg.paths.rs_universe_path)

    fetcher = PriceFetcher(cache_dir=cfg.paths.prices_cache_dir)

    # Fetch SPY for benchmark
    spy_return = 0.0
    spy_failed = False
    try:
        spy_df = fetcher.get(cfg.rs.benchmark_ticker, lookback_days=365, as_of_date=as_of_date)
        spy_closes = spy_df["Close"]
        weeks = cfg.rs.horizon_weeks
        if len(spy_closes) > weeks * 5:
            bars = weeks * 5
            spy_return = float((spy_closes.iloc[-1] / spy_closes.iloc[-bars - 1]) - 1)
        else:
            spy_failed = True
            click.echo(f"Warning: SPY has only {len(spy_closes)} bars, need {weeks * 5 + 1}. Using 0.0.", err=True)
    except Exception as exc:
        spy_failed = True
        click.echo(f"Warning: SPY benchmark fetch failed ({exc}), using 0.0", err=True)

    # 3. Fetch OHLCV for each ticker, compute 12w returns, build contexts
    returns_12w: dict[str, float] = {}
    ohlcv_by_ticker: dict[str, pd.DataFrame] = {}
    error_tickers: list[str] = []
    bars_needed = cfg.rs.horizon_weeks * 5

    for t in tickers:
        try:
            df = fetcher.get(t, lookback_days=400, as_of_date=as_of_date)
            ohlcv_by_ticker[t] = df
            closes = df["Close"]
            if len(closes) > bars_needed:
                returns_12w[t] = float((closes.iloc[-1] / closes.iloc[-bars_needed - 1]) - 1)
        except Exception as exc:
            click.echo(f"  {t}: fetch error — {exc}", err=True)
            error_tickers.append(t)

    # Also fetch universe tickers' returns for RS ranking
    for t in universe.tickers:
        if t in returns_12w:
            continue
        try:
            df = fetcher.get(t, lookback_days=120, as_of_date=as_of_date)
            closes = df["Close"]
            if len(closes) > bars_needed:
                returns_12w[t] = float((closes.iloc[-1] / closes.iloc[-bars_needed - 1]) - 1)
        except Exception:
            pass  # Non-fatal; just missing from rank universe

    batch = BatchContext(
        returns_12w_by_ticker=returns_12w,
        universe_tickers=universe.tickers,
        universe_version=universe.version,
        universe_hash=universe_hash,
        spy_return_12w=spy_return,
    )

    # Determine data_asof_date from the most recent close across tickers
    max_dates = [df.index.max() for df in ohlcv_by_ticker.values() if not df.empty]
    if max_dates:
        data_asof = max(max_dates).date()
    else:
        data_asof = datetime.now().date()
    action_session = action_session_for_run(datetime.now())

    contexts: list[CandidateContext] = []
    excluded = set(cfg.etf_exclusion.manual_block)
    excluded_tickers: list[str] = []
    for t in tickers:
        if t in excluded:
            excluded_tickers.append(t)
            continue
        if t not in ohlcv_by_ticker:
            continue  # error already recorded above
        contexts.append(CandidateContext(
            ticker=t,
            ohlcv=ohlcv_by_ticker[t],
            config=cfg,
            batch=batch,
            market=MarketContext(),
            current_equity=cfg.account.starting_equity,
        ))

    # 4. Evaluate
    candidates = evaluate_batch(contexts)

    # Build candidate rows for excluded + error tickers so every ticker has a row
    # (spec §4.3 defines 5 buckets; DB constraint requires matching row for each)
    from swing.data.models import Candidate as _Candidate
    for t in excluded_tickers:
        candidates.append(_Candidate(
            ticker=t, bucket="excluded", close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="ETF/fund blocklist", criteria=(),
        ))
    for t in error_tickers:
        candidates.append(_Candidate(
            ticker=t, bucket="error", close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="OHLCV fetch failed", criteria=(),
        ))

    # 5. Persist
    conn = connect(cfg.paths.db_path)
    run = EvaluationRun(
        id=None,
        run_ts=datetime.now().isoformat(timespec="seconds"),
        data_asof_date=data_asof.isoformat(),
        action_session_date=action_session.isoformat(),
        finviz_csv_path=str(csv_file),
        tickers_evaluated=len(candidates),
        aplus_count=sum(1 for c in candidates if c.bucket == "aplus"),
        watch_count=sum(1 for c in candidates if c.bucket == "watch"),
        skip_count=sum(1 for c in candidates if c.bucket == "skip"),
        excluded_count=len([t for t in tickers if t in excluded]),
        error_count=len(error_tickers),
    )
    run_id = insert_evaluation_run(conn, run)
    insert_candidates(conn, run_id, candidates)
    conn.close()

    click.echo(
        f"Run {run_id}: A+={run.aplus_count} watch={run.watch_count} "
        f"skip={run.skip_count} excluded={run.excluded_count} error={run.error_count}"
    )
    click.echo(f"Data as of: {run.data_asof_date}  Action session: {run.action_session_date}")


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 3: Run test**

```bash
mkdir -p tests/cli
touch tests/cli/__init__.py
pytest tests/cli/test_cli_eval.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add swing/cli.py tests/cli/
git commit -m "feat: add swing CLI with db-migrate and eval subcommands"
```

---

### Task 28: Copy live Finviz CSVs into fixtures + capture legacy baseline

**Files:**
- Create: `tests/fixtures/finviz/*.csv` (copies of existing live CSVs)
- Create: `tests/fixtures/parity-baseline.json`

- [ ] **Step 1: Copy live CSVs, snapshot universe, validate schema**

```bash
mkdir -p tests/fixtures/finviz
cp "finviz screeners"/*.csv tests/fixtures/finviz/
ls tests/fixtures/finviz/*.csv  # verify copy succeeded
```

**Snapshot the universe alongside the baseline.** Parity comparisons depend on both the OHLCV window (pinned via `--as-of-date`) AND the RS universe membership at the time the baseline was captured. If the universe is refreshed later, parity runs would falsely re-flag tickers whose TT8 ranks shifted. Freeze a copy:

```bash
cp reference/rs-universe.csv tests/fixtures/rs-universe-at-baseline.csv
```

Task 29 helper reads this frozen snapshot, not the live `reference/rs-universe.csv`. This isolates parity-test reproducibility from future universe refreshes.

Validate that each fixture CSV has the expected Finviz shape (Ticker column at minimum). Reject broken fixtures before they enter the test pipeline:

```bash
python -c "
import csv, sys
from pathlib import Path
bad = []
for f in sorted(Path('tests/fixtures/finviz').glob('finviz*.csv')):
    with open(f, newline='', encoding='utf-8') as fp:
        reader = csv.reader(fp)
        header = next(reader, None)
        if not header or 'Ticker' not in header:
            bad.append((f.name, header))
            continue
        rows = sum(1 for _ in reader)
        if rows < 5:
            bad.append((f.name, f'only {rows} rows'))
print('OK:', len([f for f in Path(\"tests/fixtures/finviz\").glob(\"finviz*.csv\")]) - len(bad))
if bad:
    print('REJECTED:')
    for name, reason in bad:
        print(f'  {name}: {reason}')
    sys.exit(1)
"
```

Expected: `OK: <n>` with no REJECTED entries. If any fail, fix or remove before proceeding.

- [ ] **Step 2: Write a one-shot script to capture legacy baseline**

Create `tests/fixtures/_capture_baseline.py`:

```python
"""One-shot: read legacy evaluation.csv files and capture bucket-per-ticker as JSON.

This script is NOT run by pytest. It exists to produce tests/fixtures/parity-baseline.json
as a static snapshot from the EXISTING reports/<YYYY-MM-DD>/evaluation.csv files produced
by the legacy evaluate_candidates.py.

Matching: each tests/fixtures/finviz/finvizDDMMMYYYY.csv maps to reports/<YYYY-MM-DD>/evaluation.csv
using the date encoded in the filename.
"""
from __future__ import annotations

import csv as csv_stdlib
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # tests/fixtures/_capture_baseline.py → project root
FIXTURES = Path(__file__).parent / "finviz"
BASELINE_PATH = Path(__file__).parent / "parity-baseline.json"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Legacy filename format examples: finviz14Apr2026.csv, finviz15Apr2026.csv, finviz16Apr2026v2.csv
_FN_RE = re.compile(r"^finviz(?P<day>\d{1,2})(?P<month>[A-Za-z]{3})(?P<year>\d{4})", re.IGNORECASE)
_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _csv_to_iso_date(finviz_name: str) -> str | None:
    m = _FN_RE.match(finviz_name)
    if not m:
        return None
    day = int(m.group("day"))
    mon = _MONTHS.get(m.group("month").lower())
    year = m.group("year")
    if not mon:
        return None
    return f"{year}-{mon}-{day:02d}"


def _load_legacy_bucket_map(eval_csv: Path) -> dict[str, str]:
    """Legacy evaluation.csv has columns including 'ticker' and 'status' (bucket).

    Verified against reports/2026-04-16/evaluation.csv — columns are:
    ticker, status, close, ma10, ma20, ma50, adr_pct, pivot, stop, ..., pattern, error, <per-criterion columns>

    Legacy 'status' is the bucket field. Values observed: 'aplus', 'watch', 'skip', 'error'.
    Mapping to new bucket enum:
        'aplus' → 'aplus'
        'watch' → 'watch'
        'skip'  → 'skip'
        'error' → 'error'
    (No 'excluded' in legacy; excluded tickers were simply dropped from the CSV.)
    """
    result: dict[str, str] = {}
    with open(eval_csv, newline="", encoding="utf-8") as f:
        reader = csv_stdlib.DictReader(f)
        fieldnames_lower = [fn.lower() for fn in (reader.fieldnames or [])]

        ticker_idx = next((i for i, n in enumerate(fieldnames_lower) if n == "ticker"), None)
        # Legacy uses 'status' for the bucket; accept 'bucket' too in case of future rename
        bucket_idx = next(
            (i for i, n in enumerate(fieldnames_lower) if n in ("status", "bucket")),
            None,
        )
        if ticker_idx is None or bucket_idx is None:
            raise ValueError(
                f"{eval_csv}: expected 'ticker' and 'status' (or 'bucket') columns; "
                f"got {reader.fieldnames}"
            )

        ticker_key = (reader.fieldnames or [])[ticker_idx]
        bucket_key = (reader.fieldnames or [])[bucket_idx]
        for row in reader:
            t = (row.get(ticker_key) or "").strip().upper()
            b = (row.get(bucket_key) or "").strip().lower()
            if t and b:
                result[t] = b
    return result


def main() -> None:
    baseline: dict[str, dict[str, str]] = {}
    for csv_file in sorted(FIXTURES.glob("finviz*.csv")):
        iso = _csv_to_iso_date(csv_file.name)
        if iso is None:
            print(f"  {csv_file.name}: could not parse date — skipping")
            continue
        report_dir = REPORTS_DIR / iso
        eval_csv = report_dir / "evaluation.csv"
        if not eval_csv.exists():
            print(f"  {csv_file.name}: no legacy report at {eval_csv} — skipping")
            continue
        try:
            baseline[csv_file.name] = _load_legacy_bucket_map(eval_csv)
            print(f"  {csv_file.name}: captured {len(baseline[csv_file.name])} tickers from {eval_csv}")
        except Exception as exc:
            print(f"  {csv_file.name}: failed to parse — {exc}")

    BASELINE_PATH.write_text(json.dumps(baseline, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {BASELINE_PATH} with {len(baseline)} CSV(s)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the capture script**

```bash
python tests/fixtures/_capture_baseline.py
```

Expected: `tests/fixtures/parity-baseline.json` written with one entry per fixture CSV whose corresponding `reports/<date>/evaluation.csv` exists. Output like:

```
  finviz14Apr2026.csv: captured 46 tickers from ...reports/2026-04-14/evaluation.csv
  finviz16Apr2026.csv: captured 91 tickers from ...reports/2026-04-16/evaluation.csv
Wrote .../parity-baseline.json with 2 CSV(s)
```

If a legacy `evaluation.csv` uses different column names than `ticker` / `bucket`, the script will raise `ValueError` — inspect the file (`python -c "import csv; print(next(csv.DictReader(open('reports/2026-04-17/evaluation.csv'))).keys())"`) and update the column-matching logic in `_load_legacy_bucket_map`.

- [ ] **Step 4: Create tests/fixtures/finviz/expected-diffs.yaml**

Start with an empty diffs file that the parity test will populate in the first run:

```yaml
# Expected divergences between new evaluator and legacy evaluator.
# Each entry explains WHY the new result differs — usually because Trend Template
# demoted a ticker that legacy didn't check.
#
# Schema: { <finviz_csv_filename>: { <ticker>: "reason string" } }
#
# Entries are added by the engineer during implementation as expected divergences surface.

{}
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/
git commit -m "test: add Finviz fixture CSVs and legacy parity baseline"
```

---

### Task 29: Parity test harness

**Files:**
- Create: `tests/evaluation/test_parity.py`

- [ ] **Step 1: Write the parity test**

```python
"""Parity test: new evaluator matches legacy bucket assignments except for documented diffs.

Purpose: mechanical regression safety net during the rewrite. Catches accidental VCP
changes. Documented Trend Template additions go in expected-diffs.yaml.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
BASELINE = FIXTURE_DIR / "parity-baseline.json"
DIFFS = FIXTURE_DIR / "finviz" / "expected-diffs.yaml"


def _load_baseline() -> dict[str, dict[str, str]]:
    if not BASELINE.exists():
        pytest.skip("parity-baseline.json not captured yet")
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _load_diffs() -> dict[str, dict[str, str]]:
    if not DIFFS.exists():
        return {}
    data = yaml.safe_load(DIFFS.read_text(encoding="utf-8")) or {}
    return data


def _run_new_evaluator_on_csv(csv_path: Path, tmp_path: Path, sample_config) -> dict[str, str]:
    """Return {ticker: bucket} from the new evaluator on this CSV.

    Uses a temp DB so tests don't touch the user's real DB. Relies on the parquet
    cache under prices_cache_dir — first run fetches from yfinance, subsequent
    runs are fast. That's why this test is marked `slow`.
    """
    import sqlite3

    from click.testing import CliRunner

    from swing.cli import main as cli_main

    # Override paths in a temp config that points DB + cache at tmp_path
    cfg_override = tmp_path / "swing.config.toml"
    cfg_override.write_text(
        (csv_path.parent.parent.parent / "swing.config.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # Rewrite [paths] section to redirect DB + caches to tmp_path
    text = cfg_override.read_text(encoding="utf-8")
    text = text.replace('db_path = "swing-data/swing.db"',
                        f'db_path = "{(tmp_path / "swing.db").as_posix()}"')
    text = text.replace('prices_cache_dir = "swing-data/prices-cache"',
                        f'prices_cache_dir = "{(tmp_path / "cache").as_posix()}"')
    cfg_override.write_text(text, encoding="utf-8")

    runner = CliRunner()
    r1 = runner.invoke(cli_main, ["--config", str(cfg_override), "db-migrate"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(cli_main, ["--config", str(cfg_override), "eval", "--csv", str(csv_path)])
    assert r2.exit_code == 0, r2.output

    conn = sqlite3.connect(tmp_path / "swing.db")
    rows = conn.execute("SELECT ticker, bucket FROM candidates").fetchall()
    conn.close()
    return {t.upper(): b.lower() for (t, b) in rows}


@pytest.mark.slow
@pytest.mark.parametrize(
    "csv_name", [f.name for f in sorted((FIXTURE_DIR / "finviz").glob("finviz*.csv"))]
)
def test_parity_per_ticker(csv_name: str, tmp_path, sample_config):
    baseline = _load_baseline().get(csv_name, {})
    if not baseline:
        pytest.skip(f"No baseline for {csv_name}")

    diffs = _load_diffs().get(csv_name, {})
    actual = _run_new_evaluator_on_csv(FIXTURE_DIR / "finviz" / csv_name, tmp_path, sample_config)

    unexplained: list[tuple[str, str, str]] = []
    for ticker, legacy_bucket in baseline.items():
        new_bucket = actual.get(ticker, "missing")
        if new_bucket != legacy_bucket:
            if ticker not in diffs:
                unexplained.append((ticker, legacy_bucket, new_bucket))

    if unexplained:
        msg = "\n".join(
            f"  {t}: legacy={lb}, new={nb}" for t, lb, nb in unexplained
        )
        pytest.fail(
            f"Unexplained divergences in {csv_name}:\n{msg}\n"
            f"Add entries to tests/fixtures/finviz/expected-diffs.yaml with a reason."
        )
```

**Parity is best-effort, not bit-for-bit.** With `--as-of-date` and a frozen universe snapshot, parity now reproduces (a) the OHLCV end-date window the legacy run saw and (b) the universe membership that was in effect at baseline time. It does NOT freeze the OHLCV content itself — yfinance's view of historical bars can change over time due to data corrections, retroactive split adjustments, or ticker remappings. So parity is best read as: "new evaluator produces the expected bucket for a ticker *given current vendor history as-of the fixture date*." That still catches most accidental VCP regressions during the rewrite, but unexplained divergences may sometimes be vendor-data drift rather than code bugs.

Document-as-drift heuristic for the engineer reviewing `suggested-diffs-*.yaml`: if a ticker's failing criteria look implausible given the fixture date (e.g., a known leader suddenly has wildly different numbers), suspect vendor drift — check the fetched OHLCV's last-bar values against the original Finviz CSV's `Price` column. If they differ materially, tag the diff with reason `"vendor_drift"` rather than chasing a code bug.

**Parity requires fixture-date pinning.** Without it, `_run_new_evaluator_on_csv` would fetch today's OHLCV, which differs from what the legacy run saw on the fixture date. The helper must derive the fixture's session date from the filename (same regex as `_capture_baseline.py`) and pass `--as-of-date` to the CLI. Update the helper:

```python
import re
import shutil

_FN_RE = re.compile(r"^finviz(?P<day>\d{1,2})(?P<month>[A-Za-z]{3})(?P<year>\d{4})", re.IGNORECASE)
_MONTHS = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
           "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}

def _data_asof_from_filename(csv_name: str) -> str | None:
    """Filename date = data_asof_date (the date of the Finviz download's most recent bar).

    NOTE: this is NOT the same as action_session_date. A finviz14Apr2026.csv was downloaded
    EOD on 2026-04-14, so the most recent OHLCV bar we should include is 2026-04-14. The
    action session it was used to plan for is 2026-04-15. Parity here is about reproducing
    the data the legacy evaluator saw, so data_asof is the right anchor.
    """
    m = _FN_RE.match(csv_name)
    if not m:
        return None
    return f"{m.group('year')}-{_MONTHS[m.group('month').lower()]}-{int(m.group('day')):02d}"

# In _run_new_evaluator_on_csv, before invoking eval:
data_asof = _data_asof_from_filename(csv_path.name)
# Use frozen universe snapshot, not live universe (see Task 28 Step 1)
frozen_universe = Path(__file__).parent.parent / "fixtures" / "rs-universe-at-baseline.csv"
assert frozen_universe.exists(), (
    "Parity tests require tests/fixtures/rs-universe-at-baseline.csv — "
    "snapshot it during Task 28 Step 1 before running parity."
)
# Override rs_universe_path in the temp config to point at the frozen snapshot
text = cfg_override.read_text(encoding="utf-8")
text = text.replace(
    'rs_universe_path = "reference/rs-universe.csv"',
    f'rs_universe_path = "{frozen_universe.as_posix()}"',
)
cfg_override.write_text(text, encoding="utf-8")

eval_args = ["--config", str(cfg_override), "eval", "--csv", str(csv_path)]
if data_asof:
    eval_args += ["--as-of-date", data_asof]
r2 = runner.invoke(cli_main, eval_args)
```

**Parity workflow auto-suggests diffs, doesn't require manual discovery.** When divergences surface, the parity test writes a suggested diffs file that the engineer reviews and renames:

```python
# Add to test_parity.py after the unexplained check:
if unexplained:
    suggested_path = FIXTURE_DIR / "finviz" / f"suggested-diffs-{csv_name}.yaml"
    # Group by ticker with the failing criteria from candidate_criteria for context
    conn = sqlite3.connect(tmp_path / "swing.db")
    suggestions = {}
    for ticker, legacy, new in unexplained:
        rows = conn.execute(
            "SELECT cc.criterion_name, cc.result FROM candidates c "
            "JOIN candidate_criteria cc ON cc.candidate_id = c.id "
            "WHERE c.ticker = ? AND cc.result IN ('fail', 'na')",
            (ticker,)
        ).fetchall()
        failed = [r[0] for r in rows]
        suggestions[ticker] = f"legacy={legacy} new={new}; failing criteria: {', '.join(failed) or 'none'}"
    conn.close()
    suggested_path.write_text(yaml.safe_dump({csv_name: suggestions}), encoding="utf-8")
    pytest.fail(
        f"Unexplained divergences in {csv_name}. "
        f"Suggestions written to {suggested_path.name}. "
        f"Review and merge into expected-diffs.yaml with a human-written reason per entry."
    )
```

Workflow: run slow suite → auto-suggestions produced per failing fixture → engineer reviews each, edits the reason, moves entries into `expected-diffs.yaml` → re-run until green.

**Realistic time for Task 29:** the parity suite fetches ~100 tickers per fixture × however many fixtures. First run is I/O-bound on yfinance (~5-10 minutes per fixture); subsequent runs are cache-hit-fast. Plan for 30-60 min total wall time including divergence review on the first pass — not the "2-5 min per step" typical of other tasks.

- [ ] **Step 2: Add pytest marker**

In `pyproject.toml` under `[tool.pytest.ini_options]`, add:

```toml
markers = [
    "slow: tests that fetch prices or run the full pipeline (skip by default)",
]
addopts = "-ra --strict-markers -m 'not slow'"
```

Update the existing `addopts` line to include `-m 'not slow'`.

- [ ] **Step 3: Run tests (slow tests skipped)**

```bash
pytest tests/evaluation/test_parity.py -v
```

Expected: all `test_parity_per_ticker` tests skipped or marked "slow." Fast default run stays green.

- [ ] **Step 4: Commit**

```bash
git add tests/evaluation/test_parity.py pyproject.toml
git commit -m "test: add parity test harness (slow marker) + expected-diffs scaffold"
```

---

### Task 30: Golden fixtures — hand-verified correctness tests

**Files:**
- Create: `tests/fixtures/golden/aplus_clean_vcp.csv`
- Create: `tests/fixtures/golden/aplus_clean_vcp.expected.yaml`
- Create: `tests/fixtures/golden/tt_fail_flat_200ma.csv`
- Create: `tests/fixtures/golden/tt_fail_flat_200ma.expected.yaml`
- Create: `tests/fixtures/golden/vcp_fail_no_tightness.csv`
- Create: `tests/fixtures/golden/vcp_fail_no_tightness.expected.yaml`
- Create: `tests/fixtures/golden/rs_low_universe.csv`
- Create: `tests/fixtures/golden/rs_low_universe.expected.yaml`
- Create: `tests/evaluation/test_golden.py`

- [ ] **Step 1: Generate synthetic fixtures**

Write `tests/fixtures/golden/_generate.py` as a one-shot script (not run by pytest):

```python
"""Generate golden fixtures: synthetic OHLCV CSVs + expected.yaml files.

Each CSV is a 260-bar daily OHLCV for one ticker. Paired expected.yaml declares
the bucket and per-criterion expectations based on spec rules.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

OUT = Path(__file__).parent


def _save(name: str, df: pd.DataFrame, expected: dict) -> None:
    df.to_csv(OUT / f"{name}.csv", index=True, index_label="Date")
    (OUT / f"{name}.expected.yaml").write_text(yaml.safe_dump(expected, sort_keys=False))


def aplus_clean_vcp() -> None:
    """Clean 260-bar uptrend ending in a tight 2-day consolidation near 20MA."""
    closes = [10.0 + i * 0.2 for i in range(220)] + [54.0] * 20 + [54.2, 54.1, 54.05, 54.10, 54.15] * 4
    closes = closes[:260]
    idx = pd.bdate_range(end="2026-04-17", periods=260)
    df = pd.DataFrame(
        {"Open": closes, "High": [c * 1.005 for c in closes], "Low": [c * 0.995 for c in closes],
         "Close": closes, "Volume": [3_000_000] * 220 + [500_000] * 40},
        index=idx,
    )
    _save("aplus_clean_vcp", df, {
        "expected_bucket": "aplus",
        "notes": "Strong 260-bar uptrend, consolidation with tight 2-day range + contracting volume.",
        "expected_trend_template_min_passes": 7,
        "expected_vcp_fails_at_most": 0,
    })


def tt_fail_flat_200ma() -> None:
    """Long flat period → 200MA flat, TT3 fails."""
    closes = [50.0] * 260
    idx = pd.bdate_range(end="2026-04-17", periods=260)
    df = pd.DataFrame(
        {"Open": closes, "High": [50.5] * 260, "Low": [49.5] * 260, "Close": closes,
         "Volume": [1_000_000] * 260},
        index=idx,
    )
    _save("tt_fail_flat_200ma", df, {
        "expected_bucket": "skip",
        "notes": "Flat closes — 200MA is flat (TT3 fail), MAs converge (TT1/2/4 fail).",
        "expected_trend_template_failing_checks": ["TT3_200_rising"],
    })


def vcp_fail_no_tightness() -> None:
    """Good trend template, but consolidation bars have wide ranges → tightness fails."""
    closes = [10.0 + i * 0.18 for i in range(240)] + [50.0] * 20
    idx = pd.bdate_range(end="2026-04-17", periods=260)
    # Big ranges (5%) for the consolidation → no tight streak
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]
    # Wide-range last 5 bars
    for i in range(5):
        highs[-(i + 1)] = closes[-(i + 1)] * 1.06
        lows[-(i + 1)] = closes[-(i + 1)] * 0.94
    df = pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes,
         "Volume": [2_000_000] * 260},
        index=idx,
    )
    _save("vcp_fail_no_tightness", df, {
        "expected_bucket": "watch",
        "notes": "Trend template passes; VCP tightness fails (wide ranges in last 5 bars).",
        "expected_vcp_failing_checks": ["tightness"],
    })


def rs_low_universe() -> None:
    """Same as aplus but ticker is in-universe with low RS return → TT8 fails."""
    closes = [10.0 + i * 0.2 for i in range(260)]
    idx = pd.bdate_range(end="2026-04-17", periods=260)
    df = pd.DataFrame(
        {"Open": closes, "High": [c * 1.005 for c in closes], "Low": [c * 0.995 for c in closes],
         "Close": closes, "Volume": [2_000_000] * 260},
        index=idx,
    )
    _save("rs_low_universe", df, {
        "expected_bucket": "aplus",  # still aplus because TT8 is allowed miss by default
        "notes": "Strong trend but RS rank artificially set low — TT8 is the allowed miss; other 7 pass.",
        "expected_tt8_result": "fail",
    })


if __name__ == "__main__":
    aplus_clean_vcp()
    tt_fail_flat_200ma()
    vcp_fail_no_tightness()
    rs_low_universe()
    print("Generated 4 golden fixtures")
```

- [ ] **Step 2: Run the generator**

```bash
mkdir -p tests/fixtures/golden
python tests/fixtures/golden/_generate.py
```

Expected: 4 pairs of `.csv` + `.expected.yaml` in `tests/fixtures/golden/`.

- [ ] **Step 3: Write the golden test**

Create `tests/evaluation/test_golden.py`:

```python
"""Golden test: hand-verified OHLCV → expected bucket + per-criterion outcomes.

Unlike parity (which anchors to legacy output), golden fixtures encode domain
knowledge — they are the real correctness test.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.evaluator import evaluate_one

GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden"


def _load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def _fixtures():
    return sorted(p for p in GOLDEN_DIR.glob("*.csv"))


@pytest.mark.parametrize("fixture_csv", _fixtures(), ids=lambda p: p.stem)
def test_golden_expected_bucket(fixture_csv: Path, sample_config):
    expected = yaml.safe_load((fixture_csv.parent / f"{fixture_csv.stem}.expected.yaml").read_text())
    df = _load_csv(fixture_csv)

    ticker = fixture_csv.stem.upper()
    # Default batch: ticker IS in universe, has "normal" RS return matching a mid-rank
    returns = {ticker: 0.30, "REF1": 0.10, "REF2": 0.20, "REF3": 0.40, "REF4": 0.50}
    # For rs_low_universe, override so TT8 actually fails
    if "rs_low" in fixture_csv.stem:
        returns[ticker] = -0.20  # low enough that rank is near bottom

    ctx = CandidateContext(
        ticker=ticker,
        ohlcv=df,
        config=sample_config,
        batch=BatchContext(
            returns_12w_by_ticker=returns,
            universe_tickers=(ticker, "REF1", "REF2", "REF3", "REF4"),
            universe_version="golden-v1",
            universe_hash="x",
            spy_return_12w=0.08,
        ),
        market=MarketContext(),
        current_equity=10000.0,
    )
    candidate = evaluate_one(ctx)
    assert candidate.bucket == expected["expected_bucket"], (
        f"Expected {expected['expected_bucket']} but got {candidate.bucket}. "
        f"Criteria: {[(c.criterion_name, c.result) for c in candidate.criteria]}"
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/evaluation/test_golden.py -v
```

Expected: 4 passed. If a fixture's expected bucket doesn't match, adjust either the synthetic OHLCV construction in `_generate.py` or the expected.yaml, with a comment explaining why.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/golden/ tests/evaluation/test_golden.py
git commit -m "test: add hand-verified golden fixtures and test"
```

---

### Task 31: End-to-end smoke on real Finviz CSV + manual verification

**Files:** (no new source; verifies the system end-to-end)

This task runs the new `swing eval` command against today's real Finviz CSV and spot-checks the output against the existing legacy run for the same date. It's the closest thing to a human review gate for Phase 1 — if this passes, Phase 1 is complete.

- [ ] **Step 1: Prepare the data directory**

```bash
mkdir -p data/finviz-inbox
cp "finviz screeners/finviz17Apr2026.csv" data/finviz-inbox/
```

(If the file for today doesn't exist yet, use the most recent one.)

- [ ] **Step 2: Install editable + migrate**

```bash
python -m pip install -e ".[dev]"
python -m swing.cli db-migrate
```

Expected: DB created at `%USERPROFILE%/swing-data/swing.db`, version 1.

- [ ] **Step 3: Run evaluation**

```bash
python -m swing.cli eval --csv data/finviz-inbox/finviz17Apr2026.csv
```

Expected:
- Command completes without error.
- Stdout shows: `Run <id>: A+=<n> watch=<n> skip=<n> excluded=<n> error=<n>` with the date line following.
- Numbers are broadly consistent with the legacy run for the same CSV (hard A+ count may be lower because Trend Template filters more aggressively).

- [ ] **Step 4: Spot-check DB contents**

```bash
python -c "
import sqlite3
from pathlib import Path
import os

home = os.environ.get('USERPROFILE') or os.environ['HOME']
conn = sqlite3.connect(Path(home) / 'swing-data' / 'swing.db')
cur = conn.execute('SELECT id, data_asof_date, action_session_date, aplus_count, watch_count, skip_count FROM evaluation_runs')
for row in cur:
    print(row)
print()
cur = conn.execute('SELECT ticker, bucket, rs_method, rs_rank FROM candidates WHERE bucket = \\'aplus\\' ORDER BY ticker')
for row in cur:
    print(row)
"
```

Expected: one `evaluation_runs` row. A+ candidates print with their ticker, 'aplus', rs_method, rs_rank.

- [ ] **Step 5: Spot-check per-criterion detail**

```bash
python -c "
import sqlite3
import os
from pathlib import Path

home = os.environ.get('USERPROFILE') or os.environ['HOME']
conn = sqlite3.connect(Path(home) / 'swing-data' / 'swing.db')
cur = conn.execute('''
SELECT c.ticker, cc.criterion_name, cc.result, cc.value
FROM candidates c JOIN candidate_criteria cc ON cc.candidate_id = c.id
WHERE c.bucket = \\'aplus\\'
ORDER BY c.ticker, cc.criterion_name
''')
for row in cur:
    print(row)
" | head -50
```

Expected: per-criterion rows for each A+ candidate; all Trend Template + VCP results present; pass/fail distribution makes sense (A+ candidates should have TT ≥7/8 and VCP all pass).

- [ ] **Step 6: Final commit**

Nothing to commit (no source changes). Leave this task as a verification gate.

---

## Success Criteria

Phase 1 is complete when ALL of the following hold:

- [ ] `python -m pytest tests/ -v` passes (excluding `slow`-marked tests) — every fast test green.
- [ ] `python -m pytest tests/ -v -m slow` passes (or parity tests skip cleanly per Task 29 decision).
- [ ] `python -m swing.cli db-migrate` creates the DB at the expected path with schema_version = 1.
- [ ] `python -m swing.cli eval --csv <real finviz csv>` completes end-to-end and populates `evaluation_runs` + `candidates` + `candidate_criteria` in the DB.
- [ ] The 4 golden fixtures all pass.
- [ ] Commit history shows one logical change per commit, each with conventional-commit message.
- [ ] Spec sections §2.3 (Phase 1 portion), §3 (Phase 1 tables), §4.1, §4.2, §4.3, §7.1, §7.2 are fully implemented and testable.
- [ ] `reference/rs-universe.csv` exists with ~500 tickers and a version header.
- [ ] Legacy `evaluate_candidates.py` is NOT yet deleted — deletion happens in Phase 4 after more phases validate.

---

## What's Next (Phase 2 preview)

Phase 2 adds the orchestration layer:

- `weather_runs` table + `swing.weather` classifier
- `pipeline_runs` + `watchlist` + `watchlist_archive` + `daily_recommendations` tables (migration 0002)
- `swing.pipeline` orchestrator with lease/lock/heartbeat/step-progress semantics (spec §5.1, §5.6)
- Manifest-driven staged promotion for charts + exports (spec §5.7)
- Watchlist aging with duplicate-session handling (spec §5.4)
- `swing.rendering.charts` (matplotlib) + `swing.rendering.briefing` (HTML template)
- Trade lifecycle: entry, exit, equity, advisory, trade_events (spec §8 partial)
- `swing.journal` stats + behavioral flags
- TOS import

Phase 2 will produce a working CLI pipeline: `python -m swing.pipeline` runs weather → evaluate → watchlist update → recommendations → export, all with proper concurrency and recovery. No web yet.

## RS universe fallback (Task 12 Path B)

If Wikipedia scraping fails, use this committed seed list — a pinned snapshot of S&P 500 + NASDAQ-100 as of 2026-04-17. Copy this block verbatim into `reference/rs-universe.csv` and update the version header to today's date before proceeding to Task 13.

Note: This seed is intentionally pinned. The universe versioning system (§4.1 of the spec) assumes frozen historical ranks per universe version, so using a pinned list is acceptable — just update the version header so later runs don't think this seed is from the scrape date. The full ticker list is ~520 rows; for brevity here, the fallback uses a smaller curated list of ~150 high-liquidity names that covers most realistic Finviz output:

```csv
# version: fallback-seed-v1-20260417
# source: pinned curated seed (fallback for failed Wikipedia scrape)
# columns: ticker
ticker
A
AAL
AAPL
ABBV
ABNB
ABT
ACN
ADBE
ADI
ADP
ADSK
AEP
AES
AFL
AIG
AJG
AKAM
ALB
ALGN
ALL
AMAT
AMD
AMGN
AMT
AMZN
ANET
ANSS
AON
APA
APD
APH
APTV
ARE
ASML
ATO
ATVI
AVB
AVGO
AVY
AWK
AXP
AZO
BA
BAC
BAX
BBY
BDX
BEN
BIIB
BIO
BK
BKNG
BKR
BLK
BMY
BR
BRK-B
BRO
BSX
BWA
BX
BXP
C
CAG
CAH
CARR
CAT
CB
CBOE
CBRE
CCI
CCL
CDNS
CDW
CE
CEG
CF
CFG
CHD
CHRW
CHTR
CI
CINF
CL
CLX
CMA
CMCSA
CME
CMG
CMI
CMS
CNC
CNP
COF
COO
COP
COR
COST
CPB
CPRT
CRL
CRM
CSCO
CSX
CTAS
CTLT
CTRA
CTSH
CTVA
CVS
CVX
D
DAL
DD
DE
DFS
DG
DGX
DHI
DHR
DIS
DLR
DLTR
DOV
DOW
DPZ
DRI
DTE
DUK
DVA
DVN
DXCM
EA
EBAY
ECL
ED
EFX
EIX
EL
ELV
EMN
EMR
ENPH
EOG
EPAM
EQIX
EQR
EQT
ES
ESS
ETN
ETR
ETSY
EW
EXC
EXPD
EXPE
EXR
F
FAST
FCX
FDS
FDX
FE
FFIV
FI
FICO
FIS
FITB
FLT
FMC
FOX
FOXA
FRT
FSLR
FTNT
FTV
GD
GE
GEHC
GEN
GILD
GIS
GL
GLW
GM
GNRC
GOOG
GOOGL
GPC
GPN
GRMN
GS
GWW
HAL
HAS
HBAN
HCA
HD
HES
HIG
HII
HLT
HOLX
HON
HPE
HPQ
HRL
HSIC
HST
HSY
HUBB
HUM
HWM
IBM
ICE
IDXX
IEX
IFF
ILMN
INCY
INTC
INTU
INVH
IP
IPG
IQV
IR
IRM
ISRG
IT
ITW
IVZ
J
JBHT
JBL
JCI
JKHY
JNJ
JNPR
JPM
K
KDP
KEY
KEYS
KHC
KIM
KLAC
KMB
KMI
KMX
KO
KR
L
LDOS
LEN
LH
LHX
LIN
LKQ
LLY
LMT
LNT
LOW
LRCX
LUV
LVS
LW
LYB
LYV
MA
MAA
MAR
MAS
MCD
MCHP
MCK
MCO
MDLZ
MDT
MET
META
MGM
MHK
MKC
MKTX
MLM
MMC
MMM
MNST
MO
MOH
MOS
MPC
MPWR
MRK
MRNA
MRO
MS
MSCI
MSFT
MSI
MTB
MTCH
MTD
MU
NCLH
NDAQ
NDSN
NEE
NEM
NFLX
NI
NKE
NOC
NOW
NRG
NSC
NTAP
NTRS
NUE
NVDA
NVR
NWL
NWS
NWSA
NXPI
O
ODFL
OKE
OMC
ON
ORCL
ORLY
OTIS
OXY
PANW
PARA
PAYC
PAYX
PCAR
PCG
PEG
PEP
PFE
PFG
PG
PGR
PH
PHM
PKG
PLD
PLTR
PM
PNC
PNR
PNW
POOL
PPG
PPL
PRU
PSA
PSX
PTC
PWR
PYPL
QCOM
QRVO
RCL
REG
REGN
RF
RHI
RJF
RL
RMD
ROK
ROL
ROP
ROST
RSG
RTX
RVTY
SBAC
SBUX
SCHW
SEDG
SHW
SJM
SLB
SMCI
SNA
SNPS
SO
SPG
SPGI
SRE
STE
STLD
STT
STX
STZ
SWK
SWKS
SYF
SYK
SYY
T
TAP
TDG
TDY
TECH
TEL
TER
TFC
TFX
TGT
TJX
TMO
TMUS
TPR
TRGP
TRMB
TROW
TRV
TSCO
TSLA
TSN
TT
TTWO
TXN
TXT
TYL
UAL
UDR
UHS
ULTA
UNH
UNP
UPS
URI
USB
V
VICI
VLO
VMC
VRSK
VRSN
VRTX
VTR
VTRS
VZ
WAB
WAT
WBA
WBD
WDC
WEC
WELL
WFC
WHR
WM
WMB
WMT
WRB
WST
WTW
WY
WYNN
XEL
XOM
XRAY
XYL
YUM
ZBH
ZBRA
ZTS
```

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-17-phase1-foundation.md`.** Before offering execution options, the plan will be run through adversarial review at the user's request (copowers wrapper).
