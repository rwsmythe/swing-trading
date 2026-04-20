# Phase 2: Pipeline + Trades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the Phase 1 evaluator in a fully orchestrated nightly pipeline (weather → evaluate → watchlist → recommendations → charts → export) with lease-fenced concurrency, port the trade lifecycle (entry/exit/equity/advisory/journal/TOS) off the legacy `trade.py`, and produce a self-contained HTML briefing per session. Phase 2 ends with a CLI-driven, headless system that reproduces every trading decision the legacy tool makes today, with a SQLite single source of truth and crash-safe staged writes. The web dashboard layered on top is Phase 3.

**Architecture:** A new `swing.pipeline` package (split into focused modules: `lease`, `heartbeat`, `staging`, `recovery`, `runner`) is the only orchestrator — every other Phase 2 module (`weather`, `watchlist`, `recommendations`, `trades`, `journal`, `rendering`) is a pure-logic library called by the runner. Lease-token fencing on every DB write makes a force-cleared stale process unable to corrupt a fresh run; manifest-driven staged promotion does the equivalent for filesystem outputs (charts, exports). Trade mutations always write a `trade_events` audit row in the same transaction as the `trades` row so the audit log is the source of truth and `trades` is a convenience projection. Briefing rendering is a view-model + Jinja2 template pattern so Phase 3's FastAPI routes can re-use the same view models for live HTMX-rendered partials.

**Tech Stack:** All Phase 1 deps + `jinja2>=3.1` (HTML templating, also used by Phase 3), `mplfinance>=0.12` (chart rendering, optional — pipeline degrades gracefully if not installed). All CLI subcommands stay on Click. No new test deps.

---

## Context

- **Spec:** [`docs/superpowers/specs/2026-04-17-swing-ground-up-refactor-design.md`](../specs/2026-04-17-swing-ground-up-refactor-design.md)
- **Phase 1 plan (predecessor):** [`docs/superpowers/plans/2026-04-17-phase1-foundation.md`](2026-04-17-phase1-foundation.md)
- **Phase 2 covers:** Spec sections §3 (remaining tables: `weather_runs`, `watchlist`, `watchlist_archive`, `trades`, `exits`, `cash_movements`, `trade_events`, `daily_recommendations`, `pipeline_runs`, `config_revisions`), §3.1 (immutability/audit), §4.1 final paragraph (RS universe refresh CLI), §5.1 (entire nightly pipeline lifecycle, 9 steps), §5.3 (failure behavior + freshness invariants), §5.4 (watchlist aging), §5.6 (force-clear stale lease — Phase 2 owns the CLI; Phase 3 owns the dashboard button), §5.7 (fenced filesystem writes — staging + manifest + recovery), §6.4 (archival HTML exports + retention + transition .md), §7.1 (unit tests for trades/journal/advisory), §7.2b (golden tests already present — extended for new pure-logic modules).
- **Out of scope for Phase 2 (Phase 3+):** FastAPI app, HTMX partials, Jinja2 dashboard templates, web routes, route tests, dashboard force-clear button. Phase 4 covers: legacy data migration script (`db-migrate --from-legacy`), folder archival to `reference/archive/`, deletion of legacy `.py` files, Windows `.bat` scripts.
- **Repo state:** continues from Phase 1 HEAD (`6800f38` on main). Schema is at version 2 (Phase 1 migrations 0001 + 0002). All Phase 1 tests pass.
- **Commands are bash (gitbash on Windows).** Paths use forward slashes except where Windows env vars are involved (e.g. `%USERPROFILE%`).

---

## File Map

```
Swing Trading/                                # repo root
├── pyproject.toml                            # MODIFY — add jinja2, mplfinance deps
├── swing.config.toml                         # MODIFY — add [pipeline], [stop_advisory], [export], [watchlist], [near_trigger] sections
├── swing/
│   ├── config.py                             # MODIFY — load Phase 2 config sections
│   ├── data/
│   │   ├── migrations/
│   │   │   └── 0003_phase2_pipeline_trades.sql   # NEW — all Phase 2 tables, schema_version=3
│   │   ├── db.py                             # MODIFY — bump EXPECTED_SCHEMA_VERSION to 3
│   │   ├── models.py                         # MODIFY — add Trade, Exit, CashMovement, TradeEvent, WatchlistEntry, WatchlistArchiveEntry, WeatherRun, DailyRecommendation, PipelineRun, ConfigRevision
│   │   └── repos/
│   │       ├── weather.py                    # NEW
│   │       ├── watchlist.py                  # NEW — watchlist + watchlist_archive
│   │       ├── trades.py                     # NEW — trades + exits + trade_events (atomic)
│   │       ├── cash.py                       # NEW — cash_movements
│   │       ├── recommendations.py            # NEW — daily_recommendations
│   │       └── pipeline.py                   # NEW — pipeline_runs (lease-fenced)
│   ├── weather/
│   │   ├── __init__.py                       # NEW
│   │   ├── classifier.py                     # NEW — pure: OHLCV → WeatherClassification
│   │   └── runner.py                         # NEW — fetch + classify + persist
│   ├── watchlist/
│   │   ├── __init__.py                       # NEW
│   │   └── service.py                        # NEW — pure: compute_watchlist_changes(prior, eval_run, data_asof)
│   ├── recommendations/
│   │   ├── __init__.py                       # NEW
│   │   ├── near_trigger.py                   # NEW — pure boolean rule
│   │   ├── sizing.py                         # NEW — pure: compute_shares + risk math
│   │   ├── focus_ranking.py                  # NEW — pure: composite weighted A+ ordering
│   │   └── build.py                          # NEW — assembles DailyRecommendation rows
│   ├── trades/
│   │   ├── __init__.py                       # NEW
│   │   ├── equity.py                         # NEW — pure: current_equity, sizing_equity, R math
│   │   ├── entry.py                          # NEW — record_entry (with cap enforcement + watchlist auto-archive)
│   │   ├── exit.py                           # NEW — record_exit (with status flip + R-multiple)
│   │   ├── stop_adjust.py                    # NEW — update_stop (with trade_events audit)
│   │   └── advisory.py                       # NEW — 7 stop-advisory rules (pure)
│   ├── journal/
│   │   ├── __init__.py                       # NEW
│   │   ├── stats.py                          # NEW — pure: compute_stats(period)
│   │   ├── flags.py                          # NEW — pure: compute_flags (3 behavioral rules)
│   │   └── tos_import.py                     # NEW — TOS CSV parser + reconciliation
│   ├── rendering/
│   │   ├── __init__.py                       # NEW
│   │   ├── view_models.py                    # NEW — BriefingViewModel + sub-models
│   │   ├── briefing.py                       # NEW — build_briefing_view_model
│   │   ├── briefing_md.py                    # NEW — render_briefing_md (transition output)
│   │   ├── exporter.py                       # NEW — export_briefing (HTML+MD+charts; size cap enforcement)
│   │   ├── retention.py                      # NEW — archive_old_exports (90-day → monthly ZIP, spec §6.4)
│   │   ├── charts.py                         # NEW — render_chart (mplfinance, optional)
│   │   └── templates/
│   │       └── briefing.html.j2              # NEW — single self-contained template
│   ├── pipeline/
│   │   ├── __init__.py                       # NEW — public entry: run_pipeline()
│   │   ├── finviz_schema.py                  # NEW — declared schema + validate_csv + reject_csv
│   │   ├── finviz_select.py                  # NEW — date-from-filename → mtime fallback
│   │   ├── lease.py                          # NEW — Lease class + acquire_lease + LeaseRevoked
│   │   ├── heartbeat.py                      # NEW — background thread (30s cadence)
│   │   ├── staging.py                        # NEW — StagingDir context manager + atomic promote
│   │   ├── recovery.py                       # NEW — sweep_stale_artifacts (startup sweep)
│   │   └── runner.py                         # NEW — orchestrates the 9 spec §5.1 steps
│   └── cli.py                                # MODIFY — add pipeline, weather, trade, journal, tos-import, rs-universe subcommands
├── tests/
│   ├── data/
│   │   ├── test_db_v3.py                     # NEW — schema migration 0003 round-trip
│   │   ├── test_repos_weather.py             # NEW
│   │   ├── test_repos_watchlist.py           # NEW
│   │   ├── test_repos_trades.py              # NEW
│   │   ├── test_repos_cash.py                # NEW
│   │   ├── test_repos_recommendations.py     # NEW
│   │   └── test_repos_pipeline.py            # NEW
│   ├── weather/
│   │   ├── __init__.py                       # NEW
│   │   ├── test_classifier.py                # NEW
│   │   └── test_runner.py                    # NEW
│   ├── watchlist/
│   │   ├── __init__.py                       # NEW
│   │   └── test_service.py                   # NEW
│   ├── recommendations/
│   │   ├── __init__.py                       # NEW
│   │   ├── test_near_trigger.py              # NEW
│   │   ├── test_sizing.py                    # NEW
│   │   ├── test_focus_ranking.py             # NEW
│   │   └── test_build.py                     # NEW
│   ├── trades/
│   │   ├── __init__.py                       # NEW
│   │   ├── test_equity.py                    # NEW
│   │   ├── test_entry.py                     # NEW
│   │   ├── test_exit.py                      # NEW
│   │   ├── test_stop_adjust.py               # NEW
│   │   └── test_advisory.py                  # NEW
│   ├── journal/
│   │   ├── __init__.py                       # NEW
│   │   ├── test_stats.py                     # NEW
│   │   ├── test_flags.py                     # NEW
│   │   └── test_tos_import.py                # NEW
│   ├── rendering/
│   │   ├── __init__.py                       # NEW
│   │   ├── test_view_models.py               # NEW
│   │   ├── test_briefing.py                  # NEW
│   │   ├── test_briefing_md.py               # NEW
│   │   ├── test_exporter.py                  # NEW
│   │   ├── test_retention.py                 # NEW
│   │   └── test_charts.py                    # NEW (slow-marked)
│   ├── pipeline/
│   │   ├── __init__.py                       # NEW
│   │   ├── test_finviz_schema.py             # NEW
│   │   ├── test_finviz_select.py             # NEW
│   │   ├── test_lease.py                     # NEW
│   │   ├── test_heartbeat.py                 # NEW
│   │   ├── test_staging.py                   # NEW
│   │   ├── test_recovery.py                  # NEW
│   │   ├── test_runner.py                    # NEW
│   │   └── test_e2e.py                       # NEW (slow-marked, real Finviz CSV + real yfinance)
│   ├── cli/
│   │   ├── test_cli_pipeline.py              # NEW
│   │   ├── test_cli_weather.py               # NEW
│   │   ├── test_cli_trade.py                 # NEW
│   │   ├── test_cli_journal.py               # NEW
│   │   ├── test_cli_tos.py                   # NEW
│   │   └── test_cli_rs_universe.py           # NEW
│   └── fixtures/
│       ├── tos/2026-04-15-AccountStatement.csv   # NEW — copied from legacy thinkorswim/
│       ├── briefings/golden-empty.html       # NEW — reference output for empty state
│       └── briefings/golden-typical.html     # NEW — reference output for one A+ + 3 watch
└── docs/superpowers/plans/
    └── 2026-04-17-phase2-pipeline-trades.md  # this file
```

**Spec-vs-plan deviation:** Spec §2.3 illustrates `swing/pipeline.py` as a single file. This plan splits it into a package (`swing/pipeline/{__init__,lease,heartbeat,staging,recovery,runner,finviz_schema,finviz_select}.py`) because the pipeline genuinely has multiple separable responsibilities (lease management, file validation, step orchestration, staging, recovery), and spec §2.4 invariants explicitly allow exceeding the ~300-line guideline when justified by responsibility separation. The CLI entry point (`python -m swing.pipeline`) and the public API (`swing.pipeline.run_pipeline`) match the spec.

---

## Conventions

(All Phase 1 conventions carry forward. Additions for Phase 2:)

- **Lease fencing:** every Phase 2 repo method that mutates `pipeline_runs`-related rows takes a `lease_token: str` argument and rejects writes whose token doesn't match the current `state='running'` row. Mismatch raises `swing.pipeline.lease.LeaseRevoked`.
- **Trade events are mandatory:** every mutation of `trades` (entry, exit-completion, stop adjust, manual flag, note) writes a `trade_events` row in the same transaction. The repo enforces this — there is no public method on `swing.data.repos.trades` that mutates `trades` without also writing a `trade_events` row. Writing only a `trade_events` row (e.g., a free-text note that doesn't change `trades` state) is allowed.
- **Daily recommendations are append-only via UPSERT:** writes use `INSERT ... ON CONFLICT(action_session_date, ticker, recommendation) DO UPDATE` so re-running the pipeline for the same session is idempotent without inflating row counts.
- **Pure-logic modules return result dataclasses, not side effects.** `swing.watchlist.service.compute_watchlist_changes` returns a `WatchlistDelta` (lists of adds/requalifies/streak_increments/removes); the caller (`pipeline.runner`) applies it via the watchlist repo. Same pattern for `recommendations.build`, `trades.advisory`, `journal.stats`, `journal.flags`.
- **All side-effecting CLI commands take `--config PATH` (inherited from Phase 1).** Pipeline-related commands additionally accept `--db PATH` to override; this is for tests and recovery scenarios only.
- **Config defaults live in `swing/config.py` `_defaults()` not in TOML.** TOML overrides defaults; missing keys fall back. This keeps the example TOML readable while hardening against accidental key removal.

---

## Prerequisites (verify before Task 1)

| Asset | Purpose | How to verify | Fallback |
|---|---|---|---|
| Phase 1 HEAD on main | Builds on Phase 1 schema + criteria | `git log --oneline -1` shows `6800f38` or descendant | Stop — Phase 2 cannot start before Phase 1 |
| `swing-data/swing.db` at schema v2 | Migration 0003 starts from v2 | `sqlite3 "$USERPROFILE/swing-data/swing.db" "SELECT version FROM schema_version"` → `2` | Run `python -m swing.cli db-migrate` first |
| `EvaluationRun` has Phase 2-required fields | Runner `_step_evaluate` + recommendations tests assume Phase 1 extended the dataclass + schema with `excluded_count`, `error_count`, `rs_universe_version`, `rs_universe_hash` (added in Phase 1 migrations 0001 + 0002) | `python -c "from swing.data.models import EvaluationRun; import dataclasses; print([f.name for f in dataclasses.fields(EvaluationRun)])"` must include all four | If missing, revisit Phase 1 Tasks 7 + 27 before starting Phase 2 |
| `pyproject.toml` already has Phase 1 deps | jinja2, mplfinance are Phase 2 additions on top | `python -m pip show pandas yfinance pyarrow exchange_calendars` all installed | Re-run Phase 1 Task 2 before Phase 2 |
| `thinkorswim/2026-04-15-AccountStatement.csv` | TOS reconciliation fixture (sub-phase F) | `ls thinkorswim/*.csv` → at least one file | Sub-phase F task F3 falls back to a hand-built minimal TOS CSV stored in `tests/fixtures/tos/synthetic-tos.csv` |
| `journal/{trades,exits,cash_movements}.csv` | Reference for legacy CSV column names — Phase 4 will migrate them; Phase 2 only uses them as schema source for repos | `ls journal/*.csv` → 3 files | If missing, take column names from this plan's sub-phase A (canonical) |
| `weather/history.csv` | Behavioral-flags lookup pattern reference | `head -1 weather/history.csv` → header row exists | Plan task F2 uses `weather_runs` repo, not legacy CSV — fallback is no-op |
| `mplfinance` installable | Chart rendering | `python -m pip install --dry-run mplfinance` | Charts skipped at runtime if import fails (graceful degradation already designed in) |

**Precondition task (run once before Task A1):**

```bash
cd "c:/Users/rwsmy/My Drive/Swing Trading"
echo "=== Phase 1 HEAD ===" && git log --oneline -1
echo "=== Schema version ===" && python -c "import sqlite3, os; p=os.path.expandvars('%USERPROFILE%/swing-data/swing.db'); print(sqlite3.connect(p).execute('SELECT version FROM schema_version').fetchone())"
echo "=== Phase 1 deps ===" && python -m pip show pandas yfinance pyarrow exchange_calendars 2>&1 | grep -E '^(Name|Version):' | head -8
echo "=== TOS fixture ===" && ls thinkorswim/*.csv 2>&1 | head -3
echo "=== Legacy journal CSVs ===" && ls journal/*.csv 2>&1 | head -3
echo "=== mplfinance availability ===" && python -m pip install --dry-run mplfinance 2>&1 | tail -3
```

Record the output (e.g. paste into the commit message of Task A1). Any FAIL → resolve before starting.

---

## Sub-Phase Roadmap

| Sub-phase | Tasks | Deliverable | Depends on |
|---|---|---|---|
| **A.** Schema + Models + Repos | A1–A7 (7) | Migration 0003 applied; all Phase 2 repos round-trip | Phase 1 |
| **B.** Weather classifier | B1–B3 (3) | `swing weather` CLI prints status; weather_runs row written | A |
| **C.** Watchlist + Recommendations | C1–C6 (6) | Pure-logic libraries with golden tests | A |
| **D.** Chart + Briefing rendering | D1–D7 (7) | `briefing.html` snapshot reproduces target view-model golden; 90-day ZIP retention | A, C |
| **E.** Trade lifecycle + advisory | E1–E6 (6) | `swing trade entry/exit/list/stop-adjust/advisory` work end-to-end | A |
| **F.** Journal + TOS reconciliation | F1–F4 (4) | `swing journal review` + `swing tos-import` produce expected output | A, E |
| **G.** Pipeline orchestrator | G1–G9 (9) | `swing pipeline run --csv X` runs all 9 spec §5.1 steps with lease + staging + recovery | A, B, C, D, E |
| **H.** RS universe refresh + E2E + concurrency | H1–H4 (4) | `swing rs-universe refresh` works; full E2E smoke + concurrent-run test pass | All |

**Recommended batching (matching Phase 1's "by sub-phase, with user review between batches" rhythm):**

1. Batch 1: A (schema is the foundation — review schema before building on it)
2. Batch 2: B + C + D (classifier + watchlist + rendering — three independent pure-logic stacks)
3. Batch 3: E + F (trade + journal — touches mutation-heavy repos, deserves its own review)
4. Batch 4: G (pipeline orchestrator — the integration point; review the lease/staging design before wiring all upstream pieces)
5. Batch 5: H (CLI polish + E2E — final acceptance)

---

## Tasks

---

## Sub-Phase A — Schema, Models, Repos

The foundation everything else builds on. Migration 0003 adds all remaining Phase 2 tables in a single forward-only migration. Models are dataclasses mirroring the column layout. Repos are thin functions over `sqlite3` that **never auto-commit** (caller wraps in `with conn:`) — the same convention Phase 1 settled on after the round-1 adversarial review.

### Task A1: Migration 0003 — Phase 2 tables

**Files:**
- Create: `swing/data/migrations/0003_phase2_pipeline_trades.sql`
- Create: `tests/data/test_db_v3.py`
- Modify: `swing/data/db.py` — bump `EXPECTED_SCHEMA_VERSION` from `2` to `3`

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_db_v3.py
"""Schema migration 0003 round-trip — verifies all Phase 2 tables exist with expected columns."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def test_migration_0003_creates_all_phase2_tables(tmp_path: Path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == EXPECTED_SCHEMA_VERSION == 3

        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        for t in (
            "weather_runs", "watchlist", "watchlist_archive",
            "trades", "exits", "cash_movements", "trade_events",
            "daily_recommendations", "pipeline_runs", "config_revisions",
        ):
            assert t in tables, f"missing table: {t}"

        # Spot-check column shapes (full set checked via INSERT below)
        assert "lease_token" in _columns(conn, "pipeline_runs")
        assert "lease_heartbeat_ts" in _columns(conn, "pipeline_runs")
        assert "last_step_progress_ts" in _columns(conn, "pipeline_runs")
        assert "rs_universe_version" in _columns(conn, "pipeline_runs")
        assert "not_qualified_streak" in _columns(conn, "watchlist")
        assert "current_stop" in _columns(conn, "trades")
        assert "r_multiple" in _columns(conn, "exits")
        assert "payload_json" in _columns(conn, "trade_events")

        # CHECK constraint on bucket already exists from 0001 — verify not regressed
        cur = conn.execute("PRAGMA foreign_key_check")
        assert cur.fetchall() == []

        # UNIQUE on daily_recommendations matches spec §3
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='daily_recommendations'"
        ).fetchall()
        assert any("action_session_date" in r[0] for r in rows) or \
            any("daily_recommendations" in r[0] and "ticker" in r[0] for r in rows), \
            "daily_recommendations needs UNIQUE on (action_session_date, ticker, recommendation)"
    finally:
        conn.close()


def test_migration_0003_idempotent(tmp_path: Path):
    """Running ensure_schema twice on a fresh DB ends at version 3, no errors."""
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = ensure_schema(db)
    try:
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 3
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/data/test_db_v3.py -v`
Expected: FAIL — version is 2, tables don't exist.

- [ ] **Step 3: Write the migration**

Create `swing/data/migrations/0003_phase2_pipeline_trades.sql`:

```sql
-- Phase 2 schema additions: weather, watchlist, trades, exits, cash, audit, recommendations, pipeline runs, config revisions.

-- Market weather (one row per classifier run)
CREATE TABLE weather_runs (
  id INTEGER PRIMARY KEY,
  run_ts TEXT NOT NULL,
  asof_date TEXT NOT NULL,
  ticker TEXT NOT NULL DEFAULT 'QQQ',
  status TEXT NOT NULL CHECK (status IN ('Bullish','Caution','Bearish')),
  close REAL NOT NULL,
  sma10 REAL, sma20 REAL, sma50 REAL,
  slope20_5bar REAL, slope10_5bar REAL,
  rationale TEXT
);
CREATE UNIQUE INDEX ux_weather_asof_ticker ON weather_runs(asof_date, ticker);

-- Active watchlist
CREATE TABLE watchlist (
  ticker TEXT PRIMARY KEY,
  added_date TEXT NOT NULL,
  last_qualified_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('watch','skip','near_trigger')),
  qualification_count INTEGER NOT NULL DEFAULT 1,
  not_qualified_streak INTEGER NOT NULL DEFAULT 0,
  last_data_asof_date TEXT NOT NULL,                 -- last data date the streak was evaluated against (idempotency key for §5.4)
  entry_target REAL,                                 -- frozen at first add (legacy parity)
  initial_stop_target REAL,                          -- frozen at first add
  last_close REAL, last_pivot REAL, last_stop REAL, last_adr_pct REAL,
  missing_criteria TEXT,                             -- semicolon-joined names of dynamic criteria failing today
  notes TEXT
);

-- Watchlist archive (audit trail of removed tickers)
CREATE TABLE watchlist_archive (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  added_date TEXT NOT NULL,
  removed_date TEXT NOT NULL,
  reason TEXT NOT NULL,
  qualification_count INTEGER,
  last_data_asof_date TEXT,
  notes TEXT
);
CREATE INDEX ix_watchlist_archive_ticker ON watchlist_archive(ticker);

-- Trades (current state — mutable; audit trail in trade_events)
CREATE TABLE trades (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  entry_date TEXT NOT NULL,
  entry_price REAL NOT NULL,
  initial_shares INTEGER NOT NULL,
  initial_stop REAL NOT NULL,
  current_stop REAL NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','closed')),
  watchlist_entry_target REAL,
  watchlist_initial_stop REAL,
  notes TEXT
);
CREATE INDEX ix_trades_ticker_status ON trades(ticker, status);

-- Exits (partials supported; sum to <= initial_shares enforced at app layer)
CREATE TABLE exits (
  id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  exit_date TEXT NOT NULL,
  exit_price REAL NOT NULL,
  shares INTEGER NOT NULL CHECK (shares > 0),
  reason TEXT NOT NULL,
  realized_pnl REAL NOT NULL,
  r_multiple REAL NOT NULL,
  notes TEXT
);
CREATE INDEX ix_exits_trade ON exits(trade_id);

-- Cash deposits / withdrawals
CREATE TABLE cash_movements (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('deposit','withdraw')),
  amount REAL NOT NULL CHECK (amount >= 0),
  ref TEXT,
  note TEXT
);
CREATE UNIQUE INDEX ux_cash_ref ON cash_movements(ref) WHERE ref IS NOT NULL;

-- Trade events (immutable audit log; required for every trades mutation)
CREATE TABLE trade_events (
  id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  ts TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('entry','stop_adjust','note','exit','flag')),
  payload_json TEXT NOT NULL,
  rationale TEXT
);
CREATE INDEX ix_trade_events_trade ON trade_events(trade_id, ts);

-- Daily recommendations (immutable session snapshot)
CREATE TABLE daily_recommendations (
  id INTEGER PRIMARY KEY,
  evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id),
  data_asof_date TEXT NOT NULL,
  action_session_date TEXT NOT NULL,
  ticker TEXT NOT NULL,
  recommendation TEXT NOT NULL CHECK (recommendation IN
      ('today_decision','watchlist_watch','watchlist_skip','near_trigger')),
  action_text TEXT,
  entry_target REAL,
  stop_target REAL,
  shares INTEGER,
  risk_dollars REAL,
  risk_pct REAL,
  rationale TEXT,
  UNIQUE(action_session_date, ticker, recommendation)
);
CREATE INDEX ix_daily_recs_session ON daily_recommendations(action_session_date);

-- Pipeline runs (lease-fenced)
CREATE TABLE pipeline_runs (
  id INTEGER PRIMARY KEY,
  started_ts TEXT NOT NULL,
  finished_ts TEXT,
  trigger TEXT NOT NULL CHECK (trigger IN ('scheduled','manual')),
  data_asof_date TEXT NOT NULL,
  action_session_date TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('running','complete','failed','blocked','force_cleared')),
  lease_token TEXT NOT NULL,
  lease_heartbeat_ts TEXT,
  last_step_progress_ts TEXT,
  current_step TEXT,
  weather_status TEXT CHECK (weather_status IN ('ok','failed','skipped')),
  evaluation_status TEXT CHECK (evaluation_status IN ('ok','failed','skipped')),
  watchlist_status TEXT CHECK (watchlist_status IN ('ok','failed','skipped')),
  recommendations_status TEXT CHECK (recommendations_status IN ('ok','failed','skipped')),
  charts_status TEXT CHECK (charts_status IN ('ok','failed','skipped')),
  export_status TEXT CHECK (export_status IN ('ok','failed','skipped')),
  rs_universe_version TEXT,
  rs_universe_hash TEXT,
  finviz_csv_path TEXT,
  error_message TEXT,
  warnings_json TEXT  -- export size warnings, stale-lease nags, etc.
);
CREATE INDEX ix_pipeline_runs_state ON pipeline_runs(state);
CREATE INDEX ix_pipeline_runs_session ON pipeline_runs(action_session_date);

-- At most one pipeline_runs row can be 'running' at a time. Critical for the
-- lease contract: without this, two processes doing SELECT-then-INSERT can
-- both observe "no active run" and both INSERT. The partial unique index
-- makes the second INSERT fail with IntegrityError even under concurrency.
CREATE UNIQUE INDEX ux_pipeline_one_running ON pipeline_runs(state) WHERE state = 'running';

-- Config audit trail (every /settings save writes a row)
CREATE TABLE config_revisions (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'cli'  -- 'cli' or 'web' (Phase 3)
);

-- Bump schema version
UPDATE schema_version SET version = 3;
```

- [ ] **Step 4: Bump EXPECTED_SCHEMA_VERSION**

In `swing/data/db.py`:

```python
EXPECTED_SCHEMA_VERSION = 3  # was 2
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/data/test_db_v3.py -v`
Expected: 2 tests PASS.

- [ ] **Step 6: Run full Phase 1 + Phase 2 test suite to verify no regression**

Run: `python -m pytest -m "not slow" -v`
Expected: all Phase 1 tests still pass + 2 new tests pass.

- [ ] **Step 7: Commit**

```bash
git add swing/data/migrations/0003_phase2_pipeline_trades.sql swing/data/db.py tests/data/test_db_v3.py
git commit -m "feat(schema): add Phase 2 tables (migration 0003)"
```

---

### Task A2: Phase 2 dataclasses

**Files:**
- Modify: `swing/data/models.py` — add 10 new dataclasses

- [ ] **Step 1: Write the failing test**

Append to `tests/data/test_repos_pipeline.py` (or create a new `tests/data/test_models.py`):

```python
"""Phase 2 model dataclass smoke test — instantiation + equality."""
from __future__ import annotations

from swing.data.models import (
    Trade, Exit, CashMovement, TradeEvent, WatchlistEntry,
    WatchlistArchiveEntry, WeatherRun, DailyRecommendation,
    PipelineRun, ConfigRevision,
)


def test_models_instantiate():
    t = Trade(id=None, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
              initial_shares=10, initial_stop=170.0, current_stop=170.0,
              status="open", watchlist_entry_target=181.0,
              watchlist_initial_stop=170.0, notes=None)
    assert t.ticker == "AAPL" and t.status == "open"

    e = Exit(id=None, trade_id=1, exit_date="2026-04-20", exit_price=190.0,
             shares=10, reason="target", realized_pnl=100.0, r_multiple=1.0, notes=None)
    assert e.r_multiple == 1.0

    cm = CashMovement(id=None, date="2026-04-01", kind="deposit",
                      amount=500.0, ref="DEP-001", note="initial funding")
    assert cm.kind == "deposit"

    te = TradeEvent(id=None, trade_id=1, ts="2026-04-15T09:30:00",
                    event_type="entry", payload_json='{"shares":10}',
                    rationale="VCP breakout")
    assert te.event_type == "entry"

    we = WatchlistEntry(ticker="MSFT", added_date="2026-04-10",
                        last_qualified_date="2026-04-15", status="watch",
                        qualification_count=3, not_qualified_streak=0,
                        last_data_asof_date="2026-04-15",
                        entry_target=420.0, initial_stop_target=410.0,
                        last_close=418.0, last_pivot=420.0, last_stop=410.0,
                        last_adr_pct=2.5, missing_criteria=None, notes=None)
    assert we.qualification_count == 3

    wa = WatchlistArchiveEntry(id=None, ticker="MSFT", added_date="2026-04-10",
                               removed_date="2026-04-20", reason="entered",
                               qualification_count=4, last_data_asof_date="2026-04-19",
                               notes=None)
    assert wa.reason == "entered"

    wr = WeatherRun(id=None, run_ts="2026-04-15T21:49:00",
                    asof_date="2026-04-15", ticker="QQQ", status="Bullish",
                    close=480.0, sma10=475.0, sma20=470.0, sma50=460.0,
                    slope20_5bar=0.5, slope10_5bar=0.7, rationale="all bullish")
    assert wr.status == "Bullish"

    dr = DailyRecommendation(id=None, evaluation_run_id=1,
                             data_asof_date="2026-04-15",
                             action_session_date="2026-04-16",
                             ticker="NVDA", recommendation="today_decision",
                             action_text="Buy-stop $850", entry_target=850.0,
                             stop_target=820.0, shares=2, risk_dollars=60.0,
                             risk_pct=0.5, rationale="VCP coil at 12-week base")
    assert dr.recommendation == "today_decision"

    pr = PipelineRun(id=None, started_ts="2026-04-15T21:49:00", finished_ts=None,
                     trigger="scheduled", data_asof_date="2026-04-15",
                     action_session_date="2026-04-16", state="running",
                     lease_token="abc-123", lease_heartbeat_ts="2026-04-15T21:49:30",
                     last_step_progress_ts="2026-04-15T21:50:00",
                     current_step="evaluate",
                     weather_status="ok", evaluation_status=None,
                     watchlist_status=None, recommendations_status=None,
                     charts_status=None, export_status=None,
                     rs_universe_version="2026-04-17-1",
                     rs_universe_hash="abcd",
                     finviz_csv_path="data/finviz-inbox/finviz15Apr2026.csv",
                     error_message=None, warnings_json=None)
    assert pr.state == "running"

    cr = ConfigRevision(id=None, ts="2026-04-15T22:00:00",
                        payload_json='{"vcp":{"adr_min_pct":4.5}}', source="cli")
    assert cr.source == "cli"
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/data/test_models.py -v`
Expected: FAIL — ImportError (classes don't exist).

- [ ] **Step 3: Add the dataclasses to `swing/data/models.py`**

Append to `swing/data/models.py` (preserve Phase 1 content):

```python
@dataclass(frozen=True)
class Trade:
    id: int | None
    ticker: str
    entry_date: str
    entry_price: float
    initial_shares: int
    initial_stop: float
    current_stop: float
    status: str  # 'open' | 'closed'
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None


@dataclass(frozen=True)
class Exit:
    id: int | None
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str
    realized_pnl: float
    r_multiple: float
    notes: str | None


@dataclass(frozen=True)
class CashMovement:
    id: int | None
    date: str
    kind: str  # 'deposit' | 'withdraw'
    amount: float
    ref: str | None
    note: str | None


@dataclass(frozen=True)
class TradeEvent:
    id: int | None
    trade_id: int
    ts: str
    event_type: str  # 'entry' | 'stop_adjust' | 'note' | 'exit' | 'flag'
    payload_json: str
    rationale: str | None


@dataclass(frozen=True)
class WatchlistEntry:
    ticker: str
    added_date: str
    last_qualified_date: str
    status: str  # 'watch' | 'skip' | 'near_trigger'
    qualification_count: int
    not_qualified_streak: int
    last_data_asof_date: str
    entry_target: float | None
    initial_stop_target: float | None
    last_close: float | None
    last_pivot: float | None
    last_stop: float | None
    last_adr_pct: float | None
    missing_criteria: str | None
    notes: str | None


@dataclass(frozen=True)
class WatchlistArchiveEntry:
    id: int | None
    ticker: str
    added_date: str
    removed_date: str
    reason: str
    qualification_count: int | None
    last_data_asof_date: str | None
    notes: str | None


@dataclass(frozen=True)
class WeatherRun:
    id: int | None
    run_ts: str
    asof_date: str
    ticker: str
    status: str  # 'Bullish' | 'Caution' | 'Bearish'
    close: float
    sma10: float | None
    sma20: float | None
    sma50: float | None
    slope20_5bar: float | None
    slope10_5bar: float | None
    rationale: str | None


@dataclass(frozen=True)
class DailyRecommendation:
    id: int | None
    evaluation_run_id: int
    data_asof_date: str
    action_session_date: str
    ticker: str
    recommendation: str  # 'today_decision' | 'watchlist_watch' | 'watchlist_skip' | 'near_trigger'
    action_text: str | None
    entry_target: float | None
    stop_target: float | None
    shares: int | None
    risk_dollars: float | None
    risk_pct: float | None
    rationale: str | None


@dataclass(frozen=True)
class PipelineRun:
    id: int | None
    started_ts: str
    finished_ts: str | None
    trigger: str  # 'scheduled' | 'manual'
    data_asof_date: str
    action_session_date: str
    state: str  # 'running' | 'complete' | 'failed' | 'blocked' | 'force_cleared'
    lease_token: str
    lease_heartbeat_ts: str | None
    last_step_progress_ts: str | None
    current_step: str | None
    weather_status: str | None
    evaluation_status: str | None
    watchlist_status: str | None
    recommendations_status: str | None
    charts_status: str | None
    export_status: str | None
    rs_universe_version: str | None
    rs_universe_hash: str | None
    finviz_csv_path: str | None
    error_message: str | None
    warnings_json: str | None


@dataclass(frozen=True)
class ConfigRevision:
    id: int | None
    ts: str
    payload_json: str
    source: str  # 'cli' | 'web'
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/data/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/models.py tests/data/test_models.py
git commit -m "feat(models): add Phase 2 dataclasses"
```

---

### Task A3: Weather repo

**Files:**
- Create: `swing/data/repos/weather.py`
- Create: `tests/data/test_repos_weather.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_repos_weather.py
"""Weather repo round-trip — insert + get_latest_for + upsert by (date, ticker)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import WeatherRun
from swing.data.repos.weather import insert_weather_run, get_latest_for_date, upsert_weather_run


def _wr(asof: str, status: str = "Bullish", close: float = 480.0) -> WeatherRun:
    return WeatherRun(
        id=None, run_ts=f"{asof}T21:49:00", asof_date=asof, ticker="QQQ",
        status=status, close=close, sma10=475.0, sma20=470.0, sma50=460.0,
        slope20_5bar=0.5, slope10_5bar=0.7, rationale="bullish setup",
    )


def test_insert_and_get_latest_for_date(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            wid = insert_weather_run(conn, _wr("2026-04-15"))
        assert wid > 0

        got = get_latest_for_date(conn, "2026-04-15", ticker="QQQ")
        assert got is not None
        assert got.status == "Bullish"
        assert got.id == wid

        assert get_latest_for_date(conn, "2026-04-16", ticker="QQQ") is None
    finally:
        conn.close()


def test_upsert_replaces_same_date(tmp_path: Path):
    """Re-running the classifier for the same (asof_date, ticker) updates in place — spec §3 ux_weather_asof_ticker."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_weather_run(conn, _wr("2026-04-15", status="Caution"))
        with conn:
            upsert_weather_run(conn, _wr("2026-04-15", status="Bullish"))

        rows = conn.execute("SELECT status FROM weather_runs WHERE asof_date='2026-04-15'").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Bullish"
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails** (`ImportError`).

- [ ] **Step 3: Implement `swing/data/repos/weather.py`**

```python
"""Weather repo — insert/upsert/get_latest. Caller wraps in `with conn:`."""
from __future__ import annotations

import sqlite3

from swing.data.models import WeatherRun

_INSERT_SQL = """
INSERT INTO weather_runs
    (run_ts, asof_date, ticker, status, close, sma10, sma20, sma50,
     slope20_5bar, slope10_5bar, rationale)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPSERT_SQL = _INSERT_SQL + """
ON CONFLICT(asof_date, ticker) DO UPDATE SET
    run_ts = excluded.run_ts,
    status = excluded.status,
    close = excluded.close,
    sma10 = excluded.sma10,
    sma20 = excluded.sma20,
    sma50 = excluded.sma50,
    slope20_5bar = excluded.slope20_5bar,
    slope10_5bar = excluded.slope10_5bar,
    rationale = excluded.rationale
"""


def _params(w: WeatherRun) -> tuple:
    return (w.run_ts, w.asof_date, w.ticker, w.status, w.close,
            w.sma10, w.sma20, w.sma50, w.slope20_5bar, w.slope10_5bar, w.rationale)


def insert_weather_run(conn: sqlite3.Connection, w: WeatherRun) -> int:
    cur = conn.execute(_INSERT_SQL, _params(w))
    return int(cur.lastrowid)


def upsert_weather_run(conn: sqlite3.Connection, w: WeatherRun) -> int:
    cur = conn.execute(_UPSERT_SQL, _params(w))
    return int(cur.lastrowid)


def get_latest_for_date(
    conn: sqlite3.Connection, asof_date: str, *, ticker: str = "QQQ"
) -> WeatherRun | None:
    row = conn.execute(
        """
        SELECT id, run_ts, asof_date, ticker, status, close, sma10, sma20, sma50,
               slope20_5bar, slope10_5bar, rationale
        FROM weather_runs
        WHERE asof_date = ? AND ticker = ?
        """,
        (asof_date, ticker),
    ).fetchone()
    if row is None:
        return None
    return WeatherRun(
        id=row[0], run_ts=row[1], asof_date=row[2], ticker=row[3], status=row[4],
        close=row[5], sma10=row[6], sma20=row[7], sma50=row[8],
        slope20_5bar=row[9], slope10_5bar=row[10], rationale=row[11],
    )
```

- [ ] **Step 4: Verify** — `python -m pytest tests/data/test_repos_weather.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/weather.py tests/data/test_repos_weather.py
git commit -m "feat(repos): add weather_runs repo"
```

---

### Task A4: Watchlist repo (active + archive)

**Files:**
- Create: `swing/data/repos/watchlist.py`
- Create: `tests/data/test_repos_watchlist.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_repos_watchlist.py
"""Watchlist repo round-trip — upsert / get / list_active / archive_entry."""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import WatchlistEntry, WatchlistArchiveEntry
from swing.data.repos.watchlist import (
    upsert_watchlist_entry, get_watchlist_entry, list_active_watchlist,
    archive_watchlist_entry, list_archive,
)


def _wl(t: str, asof: str = "2026-04-15", count: int = 1) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=t, added_date=asof, last_qualified_date=asof, status="watch",
        qualification_count=count, not_qualified_streak=0,
        last_data_asof_date=asof, entry_target=420.0, initial_stop_target=410.0,
        last_close=418.0, last_pivot=420.0, last_stop=410.0, last_adr_pct=2.5,
        missing_criteria=None, notes=None,
    )


def test_upsert_and_get(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_watchlist_entry(conn, _wl("MSFT"))
        got = get_watchlist_entry(conn, "MSFT")
        assert got is not None and got.qualification_count == 1

        # Update via upsert
        with conn:
            upsert_watchlist_entry(conn, _wl("MSFT", asof="2026-04-16", count=2))
        got2 = get_watchlist_entry(conn, "MSFT")
        assert got2.qualification_count == 2
        assert got2.last_qualified_date == "2026-04-16"
    finally:
        conn.close()


def test_list_active(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_watchlist_entry(conn, _wl("AAPL"))
            upsert_watchlist_entry(conn, _wl("MSFT"))
            upsert_watchlist_entry(conn, _wl("NVDA"))
        rows = list_active_watchlist(conn)
        tickers = {r.ticker for r in rows}
        assert tickers == {"AAPL", "MSFT", "NVDA"}
    finally:
        conn.close()


def test_archive_removes_from_active(tmp_path: Path):
    """archive_watchlist_entry must delete from watchlist + insert into archive in one transaction."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_watchlist_entry(conn, _wl("AAPL"))
        wa = WatchlistArchiveEntry(
            id=None, ticker="AAPL", added_date="2026-04-15",
            removed_date="2026-04-20", reason="entered",
            qualification_count=1, last_data_asof_date="2026-04-19", notes=None,
        )
        with conn:
            archive_watchlist_entry(conn, wa)

        assert get_watchlist_entry(conn, "AAPL") is None
        archived = list_archive(conn, ticker="AAPL")
        assert len(archived) == 1
        assert archived[0].reason == "entered"
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails** (ImportError).

- [ ] **Step 3: Implement `swing/data/repos/watchlist.py`**

```python
"""Watchlist + watchlist_archive repo. Caller wraps writes in `with conn:`."""
from __future__ import annotations

import sqlite3

from swing.data.models import WatchlistEntry, WatchlistArchiveEntry


def upsert_watchlist_entry(conn: sqlite3.Connection, e: WatchlistEntry) -> None:
    conn.execute(
        """
        INSERT INTO watchlist
            (ticker, added_date, last_qualified_date, status, qualification_count,
             not_qualified_streak, last_data_asof_date, entry_target,
             initial_stop_target, last_close, last_pivot, last_stop, last_adr_pct,
             missing_criteria, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            last_qualified_date = excluded.last_qualified_date,
            status = excluded.status,
            qualification_count = excluded.qualification_count,
            not_qualified_streak = excluded.not_qualified_streak,
            last_data_asof_date = excluded.last_data_asof_date,
            last_close = excluded.last_close,
            last_pivot = excluded.last_pivot,
            last_stop = excluded.last_stop,
            last_adr_pct = excluded.last_adr_pct,
            missing_criteria = excluded.missing_criteria,
            notes = excluded.notes
            -- entry_target / initial_stop_target are FROZEN — never overwritten
        """,
        (e.ticker, e.added_date, e.last_qualified_date, e.status,
         e.qualification_count, e.not_qualified_streak, e.last_data_asof_date,
         e.entry_target, e.initial_stop_target, e.last_close, e.last_pivot,
         e.last_stop, e.last_adr_pct, e.missing_criteria, e.notes),
    )


def get_watchlist_entry(conn: sqlite3.Connection, ticker: str) -> WatchlistEntry | None:
    row = conn.execute(
        """
        SELECT ticker, added_date, last_qualified_date, status, qualification_count,
               not_qualified_streak, last_data_asof_date, entry_target,
               initial_stop_target, last_close, last_pivot, last_stop, last_adr_pct,
               missing_criteria, notes
        FROM watchlist WHERE ticker = ?
        """,
        (ticker,),
    ).fetchone()
    return _row_to_entry(row) if row else None


def list_active_watchlist(conn: sqlite3.Connection) -> list[WatchlistEntry]:
    rows = conn.execute(
        """
        SELECT ticker, added_date, last_qualified_date, status, qualification_count,
               not_qualified_streak, last_data_asof_date, entry_target,
               initial_stop_target, last_close, last_pivot, last_stop, last_adr_pct,
               missing_criteria, notes
        FROM watchlist
        ORDER BY ticker
        """,
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


def archive_watchlist_entry(conn: sqlite3.Connection, a: WatchlistArchiveEntry) -> int:
    """Delete from `watchlist` and insert into `watchlist_archive` atomically.
    Caller's `with conn:` wraps both statements in one transaction."""
    cur = conn.execute(
        """
        INSERT INTO watchlist_archive
            (ticker, added_date, removed_date, reason, qualification_count,
             last_data_asof_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (a.ticker, a.added_date, a.removed_date, a.reason,
         a.qualification_count, a.last_data_asof_date, a.notes),
    )
    archive_id = int(cur.lastrowid)
    conn.execute("DELETE FROM watchlist WHERE ticker = ?", (a.ticker,))
    return archive_id


def list_archive(
    conn: sqlite3.Connection, *, ticker: str | None = None, limit: int = 100
) -> list[WatchlistArchiveEntry]:
    if ticker:
        rows = conn.execute(
            """
            SELECT id, ticker, added_date, removed_date, reason,
                   qualification_count, last_data_asof_date, notes
            FROM watchlist_archive WHERE ticker = ?
            ORDER BY removed_date DESC LIMIT ?
            """,
            (ticker, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, ticker, added_date, removed_date, reason,
                   qualification_count, last_data_asof_date, notes
            FROM watchlist_archive ORDER BY removed_date DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        WatchlistArchiveEntry(
            id=r[0], ticker=r[1], added_date=r[2], removed_date=r[3],
            reason=r[4], qualification_count=r[5],
            last_data_asof_date=r[6], notes=r[7],
        )
        for r in rows
    ]


def _row_to_entry(row: tuple) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=row[0], added_date=row[1], last_qualified_date=row[2],
        status=row[3], qualification_count=row[4], not_qualified_streak=row[5],
        last_data_asof_date=row[6], entry_target=row[7],
        initial_stop_target=row[8], last_close=row[9], last_pivot=row[10],
        last_stop=row[11], last_adr_pct=row[12], missing_criteria=row[13],
        notes=row[14],
    )
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/watchlist.py tests/data/test_repos_watchlist.py
git commit -m "feat(repos): add watchlist + watchlist_archive repo"
```

---

### Task A5: Trades + exits + trade_events repo (atomic)

**Files:**
- Create: `swing/data/repos/trades.py`
- Create: `tests/data/test_repos_trades.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_repos_trades.py
"""Trades repo round-trip. Every trades mutation must also write a trade_events row in same txn."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Trade, Exit, TradeEvent
from swing.data.repos.trades import (
    insert_trade_with_event, insert_exit_with_event, update_stop_with_event,
    list_open_trades, list_exits_for_trade, list_events_for_trade,
    get_trade,
)


def _trade(ticker: str = "AAPL") -> Trade:
    return Trade(
        id=None, ticker=ticker, entry_date="2026-04-15", entry_price=180.0,
        initial_shares=10, initial_stop=170.0, current_stop=170.0,
        status="open", watchlist_entry_target=181.0,
        watchlist_initial_stop=170.0, notes="VCP entry",
    )


def test_insert_trade_writes_entry_event(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn, _trade(),
                event_ts="2026-04-15T09:30:00",
                rationale="VCP breakout"
            )
        got = get_trade(conn, tid)
        assert got is not None and got.ticker == "AAPL"

        events = list_events_for_trade(conn, tid)
        assert len(events) == 1
        assert events[0].event_type == "entry"
        payload = json.loads(events[0].payload_json)
        assert payload["initial_shares"] == 10
        assert payload["entry_price"] == 180.0
    finally:
        conn.close()


def test_insert_exit_writes_event_and_flips_status_when_full(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        # Partial first
        with conn:
            insert_exit_with_event(
                conn, Exit(id=None, trade_id=tid, exit_date="2026-04-18",
                           exit_price=185.0, shares=5, reason="partial",
                           realized_pnl=25.0, r_multiple=0.5, notes=None),
                event_ts="2026-04-18T15:00:00", rationale="trim half",
            )
        assert get_trade(conn, tid).status == "open"  # still open

        # Remainder closes
        with conn:
            insert_exit_with_event(
                conn, Exit(id=None, trade_id=tid, exit_date="2026-04-22",
                           exit_price=190.0, shares=5, reason="target",
                           realized_pnl=50.0, r_multiple=1.0, notes=None),
                event_ts="2026-04-22T15:30:00", rationale="hit pivot+10%",
            )
        assert get_trade(conn, tid).status == "closed"

        events = list_events_for_trade(conn, tid)
        assert [e.event_type for e in events] == ["entry", "exit", "exit"]
    finally:
        conn.close()


def test_update_stop_writes_event_with_old_and_new(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        with conn:
            update_stop_with_event(
                conn, trade_id=tid, new_stop=175.0,
                event_ts="2026-04-17T15:00:00", rationale="trail to breakeven+",
            )
        assert get_trade(conn, tid).current_stop == 175.0

        events = list_events_for_trade(conn, tid)
        adj = next(e for e in events if e.event_type == "stop_adjust")
        payload = json.loads(adj.payload_json)
        assert payload == {"old_stop": 170.0, "new_stop": 175.0}
    finally:
        conn.close()


def test_overfill_exit_raises(tmp_path: Path):
    """Trying to exit more shares than remain raises before any write."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        with pytest.raises(ValueError, match="exceeds remaining"):
            with conn:
                insert_exit_with_event(
                    conn, Exit(id=None, trade_id=tid, exit_date="2026-04-18",
                               exit_price=185.0, shares=100, reason="manual",
                               realized_pnl=500.0, r_multiple=5.0, notes=None),
                    event_ts="2026-04-18T15:00:00",
                )
    finally:
        conn.close()


def test_list_open_trades(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_trade_with_event(conn, _trade("AAPL"), event_ts="2026-04-15T09:30:00")
            insert_trade_with_event(conn, _trade("MSFT"), event_ts="2026-04-15T09:31:00")
        opens = list_open_trades(conn)
        assert {t.ticker for t in opens} == {"AAPL", "MSFT"}
    finally:
        conn.close()


def test_trade_event_atomicity_rolls_back_on_failure(tmp_path: Path, monkeypatch):
    """If the trade_events INSERT fails mid-transaction, the trades INSERT must
    also roll back — no orphaned trades row without its paired 'entry' event."""
    import sqlite3
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        # Monkeypatch sqlite3.Connection.execute to raise only on trade_events INSERT
        orig_execute = conn.execute

        def boom_execute(sql, *args, **kwargs):
            if "INSERT INTO trade_events" in sql:
                raise sqlite3.OperationalError("simulated failure")
            return orig_execute(sql, *args, **kwargs)

        monkeypatch.setattr(conn, "execute", boom_execute)

        with pytest.raises(sqlite3.OperationalError):
            with conn:
                insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")

        # Undo monkeypatch before inspecting
        monkeypatch.setattr(conn, "execute", orig_execute)
        # No trades rows should exist — rollback must have reverted the trades INSERT
        count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert count == 0, "trades row leaked past a failed trade_events INSERT"
        event_count = conn.execute("SELECT COUNT(*) FROM trade_events").fetchone()[0]
        assert event_count == 0
    finally:
        conn.close()


def test_exit_atomicity_rolls_back_on_failure(tmp_path: Path, monkeypatch):
    """Same invariant for exits: failure in the 'exit' event insert must roll
    back the exits INSERT + the trades status update."""
    import sqlite3
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        # Seed a trade first (normal flow)
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        # Now simulate event-write failure on the exit event
        orig_execute = conn.execute

        def boom_on_exit_event(sql, *args, **kwargs):
            if "INSERT INTO trade_events" in sql and "'exit'" in sql:
                raise sqlite3.OperationalError("simulated exit-event failure")
            return orig_execute(sql, *args, **kwargs)

        monkeypatch.setattr(conn, "execute", boom_on_exit_event)
        with pytest.raises(sqlite3.OperationalError):
            with conn:
                insert_exit_with_event(
                    conn, Exit(id=None, trade_id=tid, exit_date="2026-04-18",
                               exit_price=185.0, shares=5, reason="partial",
                               realized_pnl=25.0, r_multiple=0.5, notes=None),
                    event_ts="2026-04-18T15:00:00",
                )
        monkeypatch.setattr(conn, "execute", orig_execute)
        # Trade remains open, no exit row, no exit event
        assert get_trade(conn, tid).status == "open"
        assert list_exits_for_trade(conn, tid) == []
        events = list_events_for_trade(conn, tid)
        # Only the original 'entry' event, no 'exit' event
        assert [e.event_type for e in events] == ["entry"]
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails** (ImportError).

- [ ] **Step 3: Implement `swing/data/repos/trades.py`**

```python
"""Trades + exits + trade_events repo.

Every mutation of `trades` writes a `trade_events` row in the same transaction.
This is enforced by exposing only `*_with_event` mutation functions; there is no
`insert_trade` without `_with_event` companion.
"""
from __future__ import annotations

import json
import sqlite3

from swing.data.models import Exit, Trade, TradeEvent


def insert_trade_with_event(
    conn: sqlite3.Connection, trade: Trade, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    """Insert a trade and an 'entry' trade_event in the same transaction.
    Caller wraps in `with conn:`. Returns the new trade id.
    """
    cur = conn.execute(
        """
        INSERT INTO trades
            (ticker, entry_date, entry_price, initial_shares, initial_stop,
             current_stop, status, watchlist_entry_target,
             watchlist_initial_stop, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (trade.ticker, trade.entry_date, trade.entry_price, trade.initial_shares,
         trade.initial_stop, trade.current_stop, trade.status,
         trade.watchlist_entry_target, trade.watchlist_initial_stop, trade.notes),
    )
    trade_id = int(cur.lastrowid)
    payload = {
        "ticker": trade.ticker,
        "entry_date": trade.entry_date,
        "entry_price": trade.entry_price,
        "initial_shares": trade.initial_shares,
        "initial_stop": trade.initial_stop,
    }
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'entry', ?, ?)
        """,
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )
    return trade_id


def insert_exit_with_event(
    conn: sqlite3.Connection, exit_row: Exit, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    """Insert an exit + 'exit' trade_event. Flips trade.status to 'closed' if
    cumulative exits == initial_shares. All in caller's transaction.
    Raises ValueError if shares exceeds remaining."""
    trade = get_trade(conn, exit_row.trade_id)
    if trade is None:
        raise ValueError(f"trade {exit_row.trade_id} not found")
    if trade.status != "open":
        raise ValueError(f"trade {exit_row.trade_id} is already closed")

    sold = conn.execute(
        "SELECT COALESCE(SUM(shares), 0) FROM exits WHERE trade_id = ?",
        (exit_row.trade_id,),
    ).fetchone()[0]
    remaining = trade.initial_shares - sold
    if exit_row.shares > remaining:
        raise ValueError(f"exit shares {exit_row.shares} exceeds remaining {remaining}")

    cur = conn.execute(
        """
        INSERT INTO exits
            (trade_id, exit_date, exit_price, shares, reason,
             realized_pnl, r_multiple, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (exit_row.trade_id, exit_row.exit_date, exit_row.exit_price,
         exit_row.shares, exit_row.reason, exit_row.realized_pnl,
         exit_row.r_multiple, exit_row.notes),
    )
    exit_id = int(cur.lastrowid)
    payload = {
        "exit_date": exit_row.exit_date,
        "exit_price": exit_row.exit_price,
        "shares": exit_row.shares,
        "reason": exit_row.reason,
        "realized_pnl": exit_row.realized_pnl,
        "r_multiple": exit_row.r_multiple,
    }
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'exit', ?, ?)
        """,
        (exit_row.trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )
    if exit_row.shares == remaining:
        conn.execute(
            "UPDATE trades SET status='closed' WHERE id = ?",
            (exit_row.trade_id,),
        )
    return exit_id


def update_stop_with_event(
    conn: sqlite3.Connection, *, trade_id: int, new_stop: float,
    event_ts: str, rationale: str | None = None,
) -> None:
    """Update trades.current_stop + write 'stop_adjust' event in same txn."""
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")
    if trade.current_stop == new_stop:
        return  # no-op
    payload = {"old_stop": trade.current_stop, "new_stop": new_stop}
    conn.execute(
        "UPDATE trades SET current_stop = ? WHERE id = ?",
        (new_stop, trade_id),
    )
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'stop_adjust', ?, ?)
        """,
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )


def add_note_event(
    conn: sqlite3.Connection, *, trade_id: int, event_ts: str,
    note: str, rationale: str | None = None,
) -> None:
    """Free-text 'note' event — does NOT mutate trades, just adds an audit row."""
    payload = {"note": note}
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'note', ?, ?)
        """,
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )


def get_trade(conn: sqlite3.Connection, trade_id: int) -> Trade | None:
    row = conn.execute(
        """
        SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
               current_stop, status, watchlist_entry_target,
               watchlist_initial_stop, notes
        FROM trades WHERE id = ?
        """,
        (trade_id,),
    ).fetchone()
    return _row_to_trade(row) if row else None


def list_open_trades(conn: sqlite3.Connection) -> list[Trade]:
    rows = conn.execute(
        """
        SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
               current_stop, status, watchlist_entry_target,
               watchlist_initial_stop, notes
        FROM trades WHERE status='open' ORDER BY entry_date, ticker
        """,
    ).fetchall()
    return [_row_to_trade(r) for r in rows]


def list_closed_trades(
    conn: sqlite3.Connection, *, since_date: str | None = None
) -> list[Trade]:
    if since_date:
        rows = conn.execute(
            """
            SELECT t.id, t.ticker, t.entry_date, t.entry_price, t.initial_shares,
                   t.initial_stop, t.current_stop, t.status, t.watchlist_entry_target,
                   t.watchlist_initial_stop, t.notes
            FROM trades t
            WHERE t.status='closed'
              AND EXISTS (SELECT 1 FROM exits e WHERE e.trade_id=t.id AND e.exit_date >= ?)
            ORDER BY t.entry_date DESC, t.ticker
            """,
            (since_date,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
                   current_stop, status, watchlist_entry_target,
                   watchlist_initial_stop, notes
            FROM trades WHERE status='closed' ORDER BY entry_date DESC, ticker
            """,
        ).fetchall()
    return [_row_to_trade(r) for r in rows]


def list_exits_for_trade(conn: sqlite3.Connection, trade_id: int) -> list[Exit]:
    rows = conn.execute(
        """
        SELECT id, trade_id, exit_date, exit_price, shares, reason,
               realized_pnl, r_multiple, notes
        FROM exits WHERE trade_id = ? ORDER BY exit_date, id
        """,
        (trade_id,),
    ).fetchall()
    return [
        Exit(id=r[0], trade_id=r[1], exit_date=r[2], exit_price=r[3],
             shares=r[4], reason=r[5], realized_pnl=r[6], r_multiple=r[7], notes=r[8])
        for r in rows
    ]


def list_all_exits(conn: sqlite3.Connection) -> list[Exit]:
    rows = conn.execute(
        """
        SELECT id, trade_id, exit_date, exit_price, shares, reason,
               realized_pnl, r_multiple, notes
        FROM exits ORDER BY exit_date, id
        """,
    ).fetchall()
    return [
        Exit(id=r[0], trade_id=r[1], exit_date=r[2], exit_price=r[3],
             shares=r[4], reason=r[5], realized_pnl=r[6], r_multiple=r[7], notes=r[8])
        for r in rows
    ]


def list_events_for_trade(conn: sqlite3.Connection, trade_id: int) -> list[TradeEvent]:
    rows = conn.execute(
        """
        SELECT id, trade_id, ts, event_type, payload_json, rationale
        FROM trade_events WHERE trade_id = ? ORDER BY ts, id
        """,
        (trade_id,),
    ).fetchall()
    return [
        TradeEvent(id=r[0], trade_id=r[1], ts=r[2], event_type=r[3],
                   payload_json=r[4], rationale=r[5])
        for r in rows
    ]


def find_any_open_trade(
    conn: sqlite3.Connection, *, ticker: str,
) -> Trade | None:
    """For TOS CLOSE-fill reconciliation.

    Returns the OLDEST open trade for the ticker (FIFO policy, matching US tax-lot
    convention for long positions without explicit lot designation). Under the
    Phase 2 entry invariant (swing.trades.entry raises DuplicateOpenPositionException
    if a ticker already has an open position), there is at most one open trade
    per ticker — so FIFO here is the same as "the one".

    Phase 4 legacy import may theoretically violate this invariant if the legacy
    data has concurrent open positions. In that case, FIFO yields deterministic
    behavior; the caller should review the reconciliation report and use
    `swing trade exit --trade-id ...` with an explicit ID rather than auto-match.
    """
    row = conn.execute(
        """
        SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
               current_stop, status, watchlist_entry_target,
               watchlist_initial_stop, notes
        FROM trades WHERE ticker=? AND status='open'
        ORDER BY entry_date ASC LIMIT 1
        """,
        (ticker,),
    ).fetchone()
    return _row_to_trade(row) if row else None


def find_open_trade_by_match(
    conn: sqlite3.Connection, *, ticker: str, entry_date: str,
    initial_shares: int | None = None,
) -> Trade | None:
    """For TOS reconciliation. Strict match on (ticker, entry_date, shares); fuzzy on (ticker, entry_date) if shares is None."""
    if initial_shares is not None:
        row = conn.execute(
            """
            SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
                   current_stop, status, watchlist_entry_target,
                   watchlist_initial_stop, notes
            FROM trades WHERE ticker=? AND entry_date=? AND initial_shares=? AND status='open'
            LIMIT 1
            """,
            (ticker, entry_date, initial_shares),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
                   current_stop, status, watchlist_entry_target,
                   watchlist_initial_stop, notes
            FROM trades WHERE ticker=? AND entry_date=? AND status='open'
            LIMIT 1
            """,
            (ticker, entry_date),
        ).fetchone()
    return _row_to_trade(row) if row else None


def _row_to_trade(row: tuple) -> Trade:
    return Trade(
        id=row[0], ticker=row[1], entry_date=row[2], entry_price=row[3],
        initial_shares=row[4], initial_stop=row[5], current_stop=row[6],
        status=row[7], watchlist_entry_target=row[8],
        watchlist_initial_stop=row[9], notes=row[10],
    )
```

- [ ] **Step 4: Verify** — `python -m pytest tests/data/test_repos_trades.py -v` → 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/trades.py tests/data/test_repos_trades.py
git commit -m "feat(repos): add trades + exits + trade_events repo (atomic mutations)"
```

---

### Task A6: Cash + recommendations repos

**Files:**
- Create: `swing/data/repos/cash.py`
- Create: `swing/data/repos/recommendations.py`
- Create: `tests/data/test_repos_cash.py`
- Create: `tests/data/test_repos_recommendations.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_repos_cash.py
"""Cash repo round-trip + ref-based dedup."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import CashMovement
from swing.data.repos.cash import insert_cash, list_cash, find_by_ref


def test_insert_and_list(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-01", kind="deposit",
                amount=500.0, ref="DEP-001", note=None,
            ))
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-15", kind="withdraw",
                amount=100.0, ref="WD-001", note="margin call",
            ))
        rows = list_cash(conn)
        assert len(rows) == 2
        assert sum(1 for r in rows if r.kind == "deposit") == 1
    finally:
        conn.close()


def test_ref_dedup(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-01", kind="deposit",
                amount=500.0, ref="DEP-001", note=None,
            ))
        # Re-insert same ref must fail (UNIQUE INDEX)
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                insert_cash(conn, CashMovement(
                    id=None, date="2026-04-01", kind="deposit",
                    amount=500.0, ref="DEP-001", note=None,
                ))
        # find_by_ref returns the existing
        existing = find_by_ref(conn, "DEP-001")
        assert existing is not None and existing.amount == 500.0
    finally:
        conn.close()


def test_null_ref_allowed_multiple(tmp_path: Path):
    """Manual entries (no ref) can be duplicated."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-01", kind="deposit",
                amount=10.0, ref=None, note="cash"
            ))
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-01", kind="deposit",
                amount=10.0, ref=None, note="cash"
            ))
        assert len(list_cash(conn)) == 2
    finally:
        conn.close()
```

```python
# tests/data/test_repos_recommendations.py
"""Daily recommendations repo: upsert + get_for_session."""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import DailyRecommendation, EvaluationRun
from swing.data.repos.candidates import insert_evaluation_run
from swing.data.repos.recommendations import upsert_recommendation, list_for_session


def _seed_run(conn) -> int:
    er = EvaluationRun(
        id=None, run_ts="2026-04-15T21:49:00",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        finviz_csv_path="x.csv", tickers_evaluated=1,
        aplus_count=1, watch_count=0, skip_count=0,
        excluded_count=0, error_count=0,
        rs_universe_version="2026-04-17-1", rs_universe_hash="abcd",
    )
    with conn:
        return insert_evaluation_run(conn, er)


def _rec(eval_id: int, ticker: str = "NVDA", reco: str = "today_decision") -> DailyRecommendation:
    return DailyRecommendation(
        id=None, evaluation_run_id=eval_id, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", ticker=ticker,
        recommendation=reco, action_text=f"Buy-stop $850 · 2 sh",
        entry_target=850.0, stop_target=820.0, shares=2,
        risk_dollars=60.0, risk_pct=0.5, rationale="VCP coil",
    )


def test_upsert_and_list(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        eid = _seed_run(conn)
        with conn:
            upsert_recommendation(conn, _rec(eid, "NVDA"))
            upsert_recommendation(conn, _rec(eid, "AAPL"))

        rows = list_for_session(conn, "2026-04-16")
        assert {r.ticker for r in rows} == {"NVDA", "AAPL"}
    finally:
        conn.close()


def test_upsert_replaces_on_conflict(tmp_path: Path):
    """Re-running pipeline for same session must update in place, not duplicate."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        eid = _seed_run(conn)
        with conn:
            upsert_recommendation(conn, _rec(eid))

        # Update entry_target — same key triple
        updated = DailyRecommendation(
            id=None, evaluation_run_id=eid, data_asof_date="2026-04-15",
            action_session_date="2026-04-16", ticker="NVDA",
            recommendation="today_decision", action_text="Buy-stop $852 · 2 sh",
            entry_target=852.0, stop_target=820.0, shares=2,
            risk_dollars=64.0, risk_pct=0.53, rationale="updated pivot",
        )
        with conn:
            upsert_recommendation(conn, updated)

        rows = list_for_session(conn, "2026-04-16")
        assert len(rows) == 1
        assert rows[0].entry_target == 852.0
        assert rows[0].action_text == "Buy-stop $852 · 2 sh"
    finally:
        conn.close()
```

- [ ] **Step 2: Verify both fail.**

- [ ] **Step 3: Implement `swing/data/repos/cash.py`**

```python
"""Cash movements repo. Caller wraps in `with conn:`."""
from __future__ import annotations

import sqlite3

from swing.data.models import CashMovement


def insert_cash(conn: sqlite3.Connection, m: CashMovement) -> int:
    cur = conn.execute(
        """
        INSERT INTO cash_movements (date, kind, amount, ref, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (m.date, m.kind, m.amount, m.ref, m.note),
    )
    return int(cur.lastrowid)


def list_cash(conn: sqlite3.Connection) -> list[CashMovement]:
    rows = conn.execute(
        "SELECT id, date, kind, amount, ref, note FROM cash_movements ORDER BY date, id"
    ).fetchall()
    return [
        CashMovement(id=r[0], date=r[1], kind=r[2], amount=r[3], ref=r[4], note=r[5])
        for r in rows
    ]


def find_by_ref(conn: sqlite3.Connection, ref: str) -> CashMovement | None:
    row = conn.execute(
        "SELECT id, date, kind, amount, ref, note FROM cash_movements WHERE ref = ?",
        (ref,),
    ).fetchone()
    if row is None:
        return None
    return CashMovement(id=row[0], date=row[1], kind=row[2], amount=row[3], ref=row[4], note=row[5])
```

- [ ] **Step 4: Implement `swing/data/repos/recommendations.py`**

```python
"""Daily recommendations repo. Caller wraps in `with conn:`."""
from __future__ import annotations

import sqlite3

from swing.data.models import DailyRecommendation


def upsert_recommendation(conn: sqlite3.Connection, r: DailyRecommendation) -> int:
    """Idempotent — re-running pipeline for same session updates in place via UNIQUE constraint."""
    cur = conn.execute(
        """
        INSERT INTO daily_recommendations
            (evaluation_run_id, data_asof_date, action_session_date, ticker,
             recommendation, action_text, entry_target, stop_target, shares,
             risk_dollars, risk_pct, rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(action_session_date, ticker, recommendation) DO UPDATE SET
            evaluation_run_id = excluded.evaluation_run_id,
            data_asof_date = excluded.data_asof_date,
            action_text = excluded.action_text,
            entry_target = excluded.entry_target,
            stop_target = excluded.stop_target,
            shares = excluded.shares,
            risk_dollars = excluded.risk_dollars,
            risk_pct = excluded.risk_pct,
            rationale = excluded.rationale
        """,
        (r.evaluation_run_id, r.data_asof_date, r.action_session_date, r.ticker,
         r.recommendation, r.action_text, r.entry_target, r.stop_target, r.shares,
         r.risk_dollars, r.risk_pct, r.rationale),
    )
    return int(cur.lastrowid)


def list_for_session(
    conn: sqlite3.Connection, action_session_date: str
) -> list[DailyRecommendation]:
    rows = conn.execute(
        """
        SELECT id, evaluation_run_id, data_asof_date, action_session_date, ticker,
               recommendation, action_text, entry_target, stop_target, shares,
               risk_dollars, risk_pct, rationale
        FROM daily_recommendations WHERE action_session_date = ?
        ORDER BY recommendation, ticker
        """,
        (action_session_date,),
    ).fetchall()
    return [_row(r) for r in rows]


def _row(r: tuple) -> DailyRecommendation:
    return DailyRecommendation(
        id=r[0], evaluation_run_id=r[1], data_asof_date=r[2],
        action_session_date=r[3], ticker=r[4], recommendation=r[5],
        action_text=r[6], entry_target=r[7], stop_target=r[8], shares=r[9],
        risk_dollars=r[10], risk_pct=r[11], rationale=r[12],
    )
```

- [ ] **Step 5: Verify** — `python -m pytest tests/data/test_repos_cash.py tests/data/test_repos_recommendations.py -v` → all PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/data/repos/cash.py swing/data/repos/recommendations.py tests/data/test_repos_cash.py tests/data/test_repos_recommendations.py
git commit -m "feat(repos): add cash_movements and daily_recommendations repos"
```

---

### Task A7: Pipeline runs repo (lease-fenced)

**Files:**
- Create: `swing/data/repos/pipeline.py`
- Create: `tests/data/test_repos_pipeline.py`

The pipeline_runs repo is special: every mutation past the initial INSERT enforces lease-token matching. A repo function that should mutate the row but finds the lease has been revoked raises `LeaseRevoked` instead of silently writing.

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_repos_pipeline.py
"""Pipeline runs repo + lease enforcement."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import (
    LeaseRevoked, insert_pipeline_run, update_step, update_status_columns,
    finalize_run, force_clear, find_active_run, find_run, list_recent_runs,
)


def _ts(n: int = 0) -> str:
    return f"2026-04-15T21:49:{n:02d}"


def test_insert_and_find_active(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts=_ts(0), trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=_ts(1),
            )
        active = find_active_run(conn)
        assert active is not None
        assert active.id == rid
        assert active.lease_token == token
        assert active.state == "running"
    finally:
        conn.close()


def test_lease_fenced_step_update(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts=_ts(0), trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=_ts(1),
            )
        with conn:
            update_step(conn, run_id=rid, lease_token=token,
                        step="weather", progress_ts=_ts(2))
        run = find_run(conn, rid)
        assert run.current_step == "weather"
        assert run.last_step_progress_ts == _ts(2)

        # Wrong token must raise
        with pytest.raises(LeaseRevoked):
            with conn:
                update_step(conn, run_id=rid, lease_token="wrong-token",
                            step="evaluate", progress_ts=_ts(3))
    finally:
        conn.close()


def test_force_clear_revokes_lease(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts=_ts(0), trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=_ts(1),
            )
        with conn:
            force_clear(conn, run_id=rid, error_message="admin force at 22:00")

        # Original holder cannot continue
        with pytest.raises(LeaseRevoked):
            with conn:
                update_step(conn, run_id=rid, lease_token=token,
                            step="evaluate", progress_ts=_ts(5))

        run = find_run(conn, rid)
        assert run.state == "force_cleared"
        assert "admin" in (run.error_message or "")
    finally:
        conn.close()


def test_finalize_run_sets_finished(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts=_ts(0), trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=_ts(1),
            )
        with conn:
            finalize_run(conn, run_id=rid, lease_token=token,
                         state="complete", finished_ts=_ts(30))
        run = find_run(conn, rid)
        assert run.state == "complete"
        assert run.finished_ts == _ts(30)
    finally:
        conn.close()


def test_list_recent_returns_descending(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        ids = []
        for i in range(3):
            with conn:
                rid, _ = insert_pipeline_run(
                    conn, started_ts=f"2026-04-1{i+1}T21:49:00",
                    trigger="scheduled",
                    data_asof_date=f"2026-04-1{i+1}",
                    action_session_date=f"2026-04-1{i+2}",
                    lease_heartbeat_ts=f"2026-04-1{i+1}T21:49:30",
                )
            ids.append(rid)
        recent = list_recent_runs(conn, limit=10)
        assert [r.id for r in recent] == list(reversed(ids))
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/data/repos/pipeline.py`**

```python
"""Pipeline runs repo with lease-token fencing.

Every mutation function takes lease_token and raises LeaseRevoked if it doesn't
match the row's current value (or if the row's state is no longer 'running').
This is the only enforcement layer — the application can't bypass it.
"""
from __future__ import annotations

import sqlite3
import uuid

from swing.data.models import PipelineRun


class LeaseRevoked(Exception):
    """Raised when a write is attempted with a stale or wrong lease_token."""


def insert_pipeline_run(
    conn: sqlite3.Connection, *, started_ts: str, trigger: str,
    data_asof_date: str, action_session_date: str,
    lease_heartbeat_ts: str, finviz_csv_path: str | None = None,
    rs_universe_version: str | None = None, rs_universe_hash: str | None = None,
) -> tuple[int, str]:
    """Insert a fresh 'running' run row. Returns (run_id, lease_token).
    Caller should hold the new lease for all subsequent writes."""
    token = str(uuid.uuid4())
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, trigger, data_asof_date, action_session_date, state,
             lease_token, lease_heartbeat_ts, last_step_progress_ts,
             current_step, finviz_csv_path,
             rs_universe_version, rs_universe_hash)
        VALUES (?, ?, ?, ?, 'running', ?, ?, ?, 'lock', ?, ?, ?)
        """,
        (started_ts, trigger, data_asof_date, action_session_date, token,
         lease_heartbeat_ts, lease_heartbeat_ts, finviz_csv_path,
         rs_universe_version, rs_universe_hash),
    )
    return int(cur.lastrowid), token


def _check_lease(conn: sqlite3.Connection, run_id: int, lease_token: str) -> None:
    row = conn.execute(
        "SELECT lease_token, state FROM pipeline_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise LeaseRevoked(f"run {run_id} not found")
    if row[0] != lease_token or row[1] != "running":
        raise LeaseRevoked(
            f"run {run_id} lease revoked or state changed (state={row[1]})"
        )


def update_heartbeat(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str, heartbeat_ts: str
) -> None:
    _check_lease(conn, run_id, lease_token)
    conn.execute(
        "UPDATE pipeline_runs SET lease_heartbeat_ts = ? WHERE id = ?",
        (heartbeat_ts, run_id),
    )


def update_step(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str,
    step: str, progress_ts: str,
) -> None:
    _check_lease(conn, run_id, lease_token)
    conn.execute(
        "UPDATE pipeline_runs SET current_step = ?, last_step_progress_ts = ? WHERE id = ?",
        (step, progress_ts, run_id),
    )


def update_status_columns(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str, **status_cols: str
) -> None:
    """Update one or more *_status columns. Allowed keys: weather_status,
    evaluation_status, watchlist_status, recommendations_status,
    charts_status, export_status."""
    _check_lease(conn, run_id, lease_token)
    allowed = {
        "weather_status", "evaluation_status", "watchlist_status",
        "recommendations_status", "charts_status", "export_status",
    }
    bad = set(status_cols) - allowed
    if bad:
        raise ValueError(f"unknown status columns: {bad}")
    if not status_cols:
        return
    set_clause = ", ".join(f"{k} = ?" for k in status_cols)
    conn.execute(
        f"UPDATE pipeline_runs SET {set_clause} WHERE id = ?",
        (*status_cols.values(), run_id),
    )


def finalize_run(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str,
    state: str, finished_ts: str, error_message: str | None = None,
    warnings_json: str | None = None,
) -> None:
    """Move state to complete/failed and stamp finished_ts. Lease still required."""
    if state not in ("complete", "failed"):
        raise ValueError(f"invalid finalize state: {state}")
    _check_lease(conn, run_id, lease_token)
    conn.execute(
        """
        UPDATE pipeline_runs SET state = ?, finished_ts = ?,
               error_message = COALESCE(?, error_message),
               warnings_json = COALESCE(?, warnings_json)
        WHERE id = ?
        """,
        (state, finished_ts, error_message, warnings_json, run_id),
    )


def force_clear(
    conn: sqlite3.Connection, *, run_id: int, error_message: str
) -> None:
    """Admin recovery — does NOT take lease_token because lease is being revoked.
    Subsequent writes by the original holder will raise LeaseRevoked."""
    conn.execute(
        """
        UPDATE pipeline_runs SET state = 'force_cleared',
               error_message = ?
        WHERE id = ? AND state = 'running'
        """,
        (error_message, run_id),
    )


def find_active_run(conn: sqlite3.Connection) -> PipelineRun | None:
    """Returns any row with state='running'. Spec assumes one at a time."""
    row = conn.execute(
        f"SELECT {_PR_COLS} FROM pipeline_runs WHERE state='running' LIMIT 1"
    ).fetchone()
    return _row_to_run(row) if row else None


def find_run(conn: sqlite3.Connection, run_id: int) -> PipelineRun | None:
    row = conn.execute(
        f"SELECT {_PR_COLS} FROM pipeline_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    return _row_to_run(row) if row else None


def list_recent_runs(conn: sqlite3.Connection, *, limit: int = 20) -> list[PipelineRun]:
    rows = conn.execute(
        f"SELECT {_PR_COLS} FROM pipeline_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_run(r) for r in rows]


_PR_COLS = """id, started_ts, finished_ts, trigger, data_asof_date, action_session_date,
              state, lease_token, lease_heartbeat_ts, last_step_progress_ts,
              current_step, weather_status, evaluation_status, watchlist_status,
              recommendations_status, charts_status, export_status,
              rs_universe_version, rs_universe_hash, finviz_csv_path,
              error_message, warnings_json"""


def _row_to_run(row: tuple) -> PipelineRun:
    return PipelineRun(
        id=row[0], started_ts=row[1], finished_ts=row[2], trigger=row[3],
        data_asof_date=row[4], action_session_date=row[5], state=row[6],
        lease_token=row[7], lease_heartbeat_ts=row[8],
        last_step_progress_ts=row[9], current_step=row[10],
        weather_status=row[11], evaluation_status=row[12],
        watchlist_status=row[13], recommendations_status=row[14],
        charts_status=row[15], export_status=row[16],
        rs_universe_version=row[17], rs_universe_hash=row[18],
        finviz_csv_path=row[19], error_message=row[20], warnings_json=row[21],
    )
```

- [ ] **Step 4: Verify** — `python -m pytest tests/data/test_repos_pipeline.py -v` → 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/pipeline.py tests/data/test_repos_pipeline.py
git commit -m "feat(repos): add pipeline_runs repo with lease-token fencing"
```

---

## Sub-Phase B — Weather Classifier

Pure-function classifier (`swing/weather/classifier.py`) + IO-bearing runner (`swing/weather/runner.py`) + CLI subcommand. Behaviorally identical to legacy `market_weather.py` — same priority-ordered Bullish/Caution/Bearish rule, same FLAT_MARGIN, same 5-bar slope.

### Task B1: Pure classifier

**Files:**
- Create: `swing/weather/__init__.py` (empty)
- Create: `swing/weather/classifier.py`
- Create: `tests/weather/__init__.py` (empty)
- Create: `tests/weather/test_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/weather/test_classifier.py
"""Weather classifier — pure-function rule from legacy market_weather.py."""
from __future__ import annotations

import pandas as pd

from swing.weather.classifier import classify_weather, WeatherClassification, FLAT_MARGIN_PCT


def _ohlcv(closes: list[float]) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-04-15", periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [10_000_000] * len(closes),
    }, index=idx)


def test_bullish_when_close_above_rising_20ma_and_10_above_20():
    # Steady uptrend over 60 bars
    closes = [100.0 + i * 0.5 for i in range(60)]
    result = classify_weather(_ohlcv(closes))
    assert result.status == "Bullish"
    assert result.sma10 > result.sma20
    assert result.slope20_5bar > FLAT_MARGIN_PCT


def test_bearish_when_close_below_declining_20ma():
    # Downtrend
    closes = [200.0 - i * 0.5 for i in range(60)]
    result = classify_weather(_ohlcv(closes))
    assert result.status == "Bearish"
    assert result.slope20_5bar < -FLAT_MARGIN_PCT


def test_caution_when_close_below_20ma_but_20ma_not_declining():
    # Flat MA, close just dipped — Caution per priority rule
    closes = [100.0] * 50 + [99.0] * 6 + [98.5] * 4
    result = classify_weather(_ohlcv(closes))
    assert result.status == "Caution"
    assert "20MA" in result.rationale or "ambiguous" in result.rationale


def test_caution_when_close_above_20ma_but_10ma_not_above_20ma():
    # Trend just turning — close > 20MA but 10MA hasn't crossed yet
    closes = [100.0] * 50 + [99.5, 100.0, 100.5, 101.0, 102.0, 102.5, 103.0]
    result = classify_weather(_ohlcv(closes))
    assert result.status in ("Bullish", "Caution")  # accept either depending on exact slope


def test_classification_carries_metrics():
    closes = [100.0 + i * 0.5 for i in range(60)]
    result = classify_weather(_ohlcv(closes))
    assert isinstance(result, WeatherClassification)
    assert result.close > 0
    assert result.sma10 is not None
    assert result.sma20 is not None
    assert result.sma50 is not None


def test_insufficient_bars_raises():
    """Need at least 56 bars (50MA + 5 slope + 1)."""
    closes = [100.0] * 30
    import pytest
    with pytest.raises(ValueError, match="insufficient bars"):
        classify_weather(_ohlcv(closes))
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/weather/classifier.py`**

```python
"""Pure-function classifier ported from legacy market_weather.py.

Priority-ordered rule (first match wins):
  1. Bearish: close < 20MA AND 20MA declining (slope < -FLAT_MARGIN_PCT)
  2. Bullish: close > 20MA AND 20MA rising AND 10MA > 20MA
  3. Caution: anything else, with rationale enumerating which Bullish clause(s) missed
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FLAT_MARGIN_PCT = 0.1
SLOPE_LOOKBACK = 5
MA_SHORT = 10
MA_MID = 20
MA_LONG = 50
MIN_BARS = MA_LONG + SLOPE_LOOKBACK + 1  # 56


@dataclass(frozen=True)
class WeatherClassification:
    asof_date: str
    close: float
    sma10: float | None
    sma20: float | None
    sma50: float | None
    slope10_5bar: float
    slope20_5bar: float
    status: str  # 'Bullish' | 'Caution' | 'Bearish'
    rationale: str


def _slope_pct(series: pd.Series, lookback: int = SLOPE_LOOKBACK) -> float:
    if len(series) <= lookback:
        return 0.0
    now = series.iloc[-1]
    then = series.iloc[-lookback - 1]
    if pd.isna(now) or pd.isna(then) or then <= 0:
        return 0.0
    return float((now - then) / then * 100)


def _classify_slope(slope: float) -> str:
    if slope > FLAT_MARGIN_PCT:
        return "rising"
    if slope < -FLAT_MARGIN_PCT:
        return "declining"
    return "flat"


def classify_weather(ohlcv: pd.DataFrame) -> WeatherClassification:
    if len(ohlcv) < MIN_BARS:
        raise ValueError(
            f"insufficient bars for weather classifier: have {len(ohlcv)}, need {MIN_BARS}"
        )

    closes = ohlcv["Close"]
    sma10 = closes.rolling(MA_SHORT, min_periods=MA_SHORT).mean()
    sma20 = closes.rolling(MA_MID, min_periods=MA_MID).mean()
    sma50 = closes.rolling(MA_LONG, min_periods=MA_LONG).mean()

    last_close = float(closes.iloc[-1])
    s10 = float(sma10.iloc[-1])
    s20 = float(sma20.iloc[-1])
    s50 = float(sma50.iloc[-1])
    slope20 = _slope_pct(sma20)
    slope10 = _slope_pct(sma10)
    slope20_state = _classify_slope(slope20)

    # Priority-ordered rule
    if last_close < s20 and slope20_state == "declining":
        status = "Bearish"
        rationale = (
            f"Close ${last_close:.2f} below 20MA ${s20:.2f}; "
            f"20MA declining ({slope20:+.2f}%/5bars)."
        )
    elif last_close > s20 and slope20_state == "rising" and s10 > s20:
        status = "Bullish"
        rationale = (
            f"Close ${last_close:.2f} above 20MA ${s20:.2f}; "
            f"20MA rising ({slope20:+.2f}%/5bars); 10MA above 20MA."
        )
    else:
        status = "Caution"
        misses: list[str] = []
        if last_close <= s20:
            misses.append(f"close at/below 20MA")
        if slope20_state == "flat":
            misses.append("20MA is flat")
        elif slope20_state == "declining":
            misses.append("20MA is declining")
        if s10 <= s20:
            misses.append("10MA <= 20MA")
        rationale = (
            "Caution: " + "; ".join(misses)
            if misses
            else "Caution: ambiguous middle state."
        )

    asof = pd.Timestamp(ohlcv.index[-1]).date().isoformat()
    return WeatherClassification(
        asof_date=asof, close=last_close,
        sma10=s10, sma20=s20, sma50=s50,
        slope10_5bar=slope10, slope20_5bar=slope20,
        status=status, rationale=rationale,
    )
```

- [ ] **Step 4: Verify** — `python -m pytest tests/weather/test_classifier.py -v` → 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/weather/__init__.py swing/weather/classifier.py tests/weather/__init__.py tests/weather/test_classifier.py
git commit -m "feat(weather): port classifier from legacy market_weather.py"
```

---

### Task B2: Weather runner

**Files:**
- Create: `swing/weather/runner.py`
- Create: `tests/weather/test_runner.py`

The runner glues classifier ↔ PriceFetcher ↔ weather repo. Caller passes a `PriceFetcher` (so tests can inject a mock).

- [ ] **Step 1: Write the failing test**

```python
# tests/weather/test_runner.py
"""Weather runner — integrates classifier + price fetch + repo write."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from swing.data.db import ensure_schema
from swing.data.repos.weather import get_latest_for_date
from swing.weather.runner import run_weather


def _ohlcv():
    closes = [100.0 + i * 0.5 for i in range(60)]
    idx = pd.bdate_range(end="2026-04-15", periods=60)
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 60,
    }, index=idx)


def test_run_weather_writes_row(tmp_path: Path):
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()

    fake_fetcher = MagicMock()
    fake_fetcher.get.return_value = _ohlcv()

    result = run_weather(
        db_path=db_path, fetcher=fake_fetcher,
        ticker="QQQ", as_of_date=None, run_ts="2026-04-15T21:49:00",
    )
    assert result.status == "Bullish"

    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        row = get_latest_for_date(conn, "2026-04-15", ticker="QQQ")
        assert row is not None
        assert row.status == "Bullish"
        assert row.run_ts == "2026-04-15T21:49:00"
    finally:
        conn.close()
    fake_fetcher.get.assert_called_once_with("QQQ", lookback_days=180, as_of_date=None)


def test_run_weather_upserts_on_repeat(tmp_path: Path):
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()

    fake_fetcher = MagicMock()
    fake_fetcher.get.return_value = _ohlcv()

    run_weather(db_path=db_path, fetcher=fake_fetcher, ticker="QQQ",
                as_of_date=None, run_ts="2026-04-15T21:49:00")
    run_weather(db_path=db_path, fetcher=fake_fetcher, ticker="QQQ",
                as_of_date=None, run_ts="2026-04-15T22:00:00")

    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM weather_runs WHERE asof_date='2026-04-15' AND ticker='QQQ'"
        ).fetchone()
        assert rows[0] == 1
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/weather/runner.py`**

```python
"""Weather runner — fetch QQQ OHLCV, classify, persist."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from swing.data.db import connect
from swing.data.models import WeatherRun
from swing.data.repos.weather import upsert_weather_run
from swing.prices import PriceFetcher
from swing.weather.classifier import classify_weather, WeatherClassification


def run_weather(
    *, db_path: Path, fetcher: PriceFetcher, ticker: str = "QQQ",
    as_of_date: date | None = None, run_ts: str,
    lookback_days: int = 180,
) -> WeatherClassification:
    """Fetch OHLCV, classify, persist. Returns the classification.
    Caller is responsible for failure handling — exceptions propagate."""
    ohlcv = fetcher.get(ticker, lookback_days=lookback_days, as_of_date=as_of_date)
    classification = classify_weather(ohlcv)

    conn = connect(db_path)
    try:
        with conn:
            upsert_weather_run(conn, WeatherRun(
                id=None, run_ts=run_ts, asof_date=classification.asof_date,
                ticker=ticker, status=classification.status,
                close=classification.close,
                sma10=classification.sma10, sma20=classification.sma20,
                sma50=classification.sma50,
                slope20_5bar=classification.slope20_5bar,
                slope10_5bar=classification.slope10_5bar,
                rationale=classification.rationale,
            ))
    finally:
        conn.close()
    return classification
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/weather/runner.py tests/weather/test_runner.py
git commit -m "feat(weather): runner integrates classifier + price fetch + repo"
```

---

### Task B3: `swing weather` CLI subcommand

**Files:**
- Modify: `swing/cli.py` — add `weather` subcommand
- Create: `tests/cli/test_cli_weather.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_cli_weather.py
"""CLI weather subcommand — runs classifier + writes row + prints status line."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def test_cli_weather_prints_status(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "project"; project_dir.mkdir()
    home_dir = tmp_path / "home"; home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)

    closes = [100.0 + i * 0.5 for i in range(60)]
    idx = pd.bdate_range(end="2026-04-15", periods=60)
    df = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 60,
    }, index=idx)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: df,
    )

    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    result = runner.invoke(main, ["--config", str(cfg_path), "weather"])

    assert result.exit_code == 0, result.output
    assert "Status:" in result.output
    assert "Bullish" in result.output
```

- [ ] **Step 2: Verify it fails** (subcommand doesn't exist).

- [ ] **Step 3: Add `weather` subcommand to `swing/cli.py`**

Add after the existing `eval_cmd`:

```python
@main.command("weather")
@click.option("--ticker", default="QQQ", help="Benchmark to classify (default: QQQ)")
@click.option("--as-of-date", "as_of_date_str", default=None,
              help="YYYY-MM-DD - cap OHLCV to bars <= this date (parity).")
@click.pass_context
def weather_cmd(ctx: click.Context, ticker: str, as_of_date_str: str | None) -> None:
    """Classify market weather and persist to weather_runs."""
    from datetime import date as _date, datetime as _dt
    from swing.prices import PriceFetcher
    from swing.weather.runner import run_weather

    cfg = ctx.obj["config"]
    fetcher = PriceFetcher(cache_dir=cfg.paths.prices_cache_dir)
    run_ts = _dt.now().isoformat(timespec="seconds")
    as_of = _date.fromisoformat(as_of_date_str) if as_of_date_str else None

    result = run_weather(
        db_path=cfg.paths.db_path, fetcher=fetcher,
        ticker=ticker, as_of_date=as_of, run_ts=run_ts,
    )
    click.echo(f"Status: {result.status}  Close: ${result.close:.2f}  "
               f"20MA slope: {result.slope20_5bar:+.2f}%/5b")
    click.echo(result.rationale)
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/cli/test_cli_weather.py
git commit -m "feat(cli): add `swing weather` subcommand"
```

---

## Sub-Phase C — Watchlist + Recommendations (pure logic)

This sub-phase ports the legacy watchlist update + briefing logic into pure functions that operate on data structures. The pipeline runner (sub-phase G) calls these and persists results via repos.

### Task C1: Watchlist service — partition + delta

**Files:**
- Create: `swing/watchlist/__init__.py` (empty)
- Create: `swing/watchlist/service.py`
- Create: `tests/watchlist/__init__.py` (empty)
- Create: `tests/watchlist/test_service.py`

The legacy code splits criteria into "stable" (gates membership) and "dynamic" (informational). Phase 1 already has the per-criterion Result records; sub-phase C just inspects them.

- [ ] **Step 1: Write the failing test**

```python
# tests/watchlist/test_service.py
"""Watchlist service: partition today's evaluation against prior watchlist."""
from __future__ import annotations

from swing.data.models import Candidate, CriterionResult, WatchlistEntry
from swing.watchlist.service import (
    compute_watchlist_changes, WatchlistDelta,
    STABLE_CRITERION_NAMES, DYNAMIC_CRITERION_NAMES,
    AGING_STREAK_THRESHOLD,
)


def _candidate(
    ticker: str, *, all_stable_pass: bool = True, missing_dynamic: tuple[str, ...] = (),
    bucket: str = "watch",
) -> Candidate:
    crits = []
    for name in STABLE_CRITERION_NAMES:
        crits.append(CriterionResult(
            criterion_name=name, layer="vcp",
            result="pass" if all_stable_pass else "fail",
            value=None, rule=None,
        ))
    for name in DYNAMIC_CRITERION_NAMES:
        crits.append(CriterionResult(
            criterion_name=name, layer="vcp",
            result="fail" if name in missing_dynamic else "pass",
            value=None, rule=None,
        ))
    return Candidate(
        ticker=ticker, bucket=bucket, close=100.0, pivot=102.0,
        initial_stop=98.0, adr_pct=4.5, tight_streak=3, pullback_pct=10.0,
        prior_trend_pct=30.0, rs_rank=80, rs_return_12w_vs_spy=0.15,
        rs_method="universe", pattern_tag=None, notes=None,
        criteria=tuple(crits),
    )


def test_new_qualifier_is_added():
    delta = compute_watchlist_changes(
        prior=[], today_candidates=[_candidate("AAPL")],
        data_asof_date="2026-04-15",
    )
    assert len(delta.adds) == 1
    add = delta.adds[0]
    assert add.ticker == "AAPL"
    assert add.added_date == "2026-04-15"
    assert add.qualification_count == 1
    assert add.entry_target == 102.0
    assert add.initial_stop_target == 98.0


def test_existing_requalifier_increments_count_keeps_targets():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-04-12",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=[_candidate("AAPL")],
        data_asof_date="2026-04-15",
    )
    assert len(delta.requalifies) == 1
    rq = delta.requalifies[0]
    assert rq.qualification_count == 3
    # Targets stay frozen — different from today's pivot/stop
    assert rq.entry_target == 99.0
    assert rq.initial_stop_target == 95.0


def test_failing_stable_increments_streak():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-04-12",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior,
        today_candidates=[_candidate("AAPL", all_stable_pass=False)],
        data_asof_date="2026-04-15",
    )
    assert len(delta.streak_increments) == 1
    inc = delta.streak_increments[0]
    assert inc.not_qualified_streak == 1
    assert inc.last_data_asof_date == "2026-04-15"


def test_streak_at_threshold_archives():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2,
        not_qualified_streak=AGING_STREAK_THRESHOLD - 1,  # one more fail tips it
        last_data_asof_date="2026-04-14",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior,
        today_candidates=[_candidate("AAPL", all_stable_pass=False)],
        data_asof_date="2026-04-15",
    )
    assert delta.streak_increments == []
    assert len(delta.removes) == 1
    arch = delta.removes[0]
    assert arch.ticker == "AAPL"
    assert arch.removed_date == "2026-04-15"
    assert "stable" in arch.reason.lower() or "aged" in arch.reason.lower()


def test_absence_from_batch_does_not_count():
    """Per spec §5.4: only runs where ticker is IN the batch but didn't qualify count."""
    prior = [WatchlistEntry(
        ticker="OBSCURE", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=2,
        last_data_asof_date="2026-04-14",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=[],  # OBSCURE absent
        data_asof_date="2026-04-15",
    )
    assert delta.streak_increments == []
    assert delta.removes == []
    assert delta.adds == []
    assert delta.requalifies == []


def test_duplicate_data_asof_does_not_double_increment_streak():
    """Per spec §5.4: re-running pipeline for same data_asof must not double-
    increment the streak. Narrow idempotency: other reconciliation still runs."""
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=1,
        last_data_asof_date="2026-04-15",  # streak already counted today
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior,
        today_candidates=[_candidate("AAPL", all_stable_pass=False)],
        data_asof_date="2026-04-15",
    )
    # Streak already counted → no new increment or archive
    assert delta.streak_increments == []
    assert delta.removes == []


def test_corrected_rerun_can_requalify_previously_failing_ticker():
    """A corrected CSV for the same data_asof_date (after fixing a bad first run)
    must be able to re-qualify a ticker, not be frozen out by idempotency."""
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=1,
        last_data_asof_date="2026-04-15",  # first run counted as failure
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    # Corrected CSV now shows AAPL as qualifying
    delta = compute_watchlist_changes(
        prior=prior,
        today_candidates=[_candidate("AAPL", bucket="watch")],
        data_asof_date="2026-04-15",
    )
    assert len(delta.requalifies) == 1
    assert delta.requalifies[0].not_qualified_streak == 0  # reset
    assert delta.requalifies[0].qualification_count == 3


def test_dynamic_misses_recorded_in_missing_criteria():
    delta = compute_watchlist_changes(
        prior=[],
        today_candidates=[_candidate("AAPL", missing_dynamic=("tightness", "vcp"))],
        data_asof_date="2026-04-15",
    )
    assert len(delta.adds) == 1
    add = delta.adds[0]
    assert add.missing_criteria is not None
    assert "tightness" in add.missing_criteria
    assert "vcp" in add.missing_criteria


def test_skip_bucket_does_not_qualify():
    """Spec §5.4: qualifying rule keys on bucket (watch/aplus), not just stable-pass.
    A candidate with all stable passes but 3+ dynamic misses falls to `skip` and
    MUST NOT be added to the watchlist."""
    cand = _candidate("SKIP1", missing_dynamic=("proximity", "tightness", "vcp"),
                      bucket="skip")
    delta = compute_watchlist_changes(
        prior=[], today_candidates=[cand], data_asof_date="2026-04-15",
    )
    assert delta.adds == []
    assert delta.requalifies == []


def test_skip_bucket_for_existing_counts_as_fail():
    """Existing watchlist row whose today-bucket is `skip` must increment streak."""
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-04-12",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    cand = _candidate("AAPL", missing_dynamic=("proximity", "tightness", "vcp"),
                      bucket="skip")
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=[cand], data_asof_date="2026-04-15",
    )
    assert len(delta.streak_increments) == 1
    assert delta.streak_increments[0].not_qualified_streak == 1
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/watchlist/service.py`**

```python
"""Watchlist update — partitions today's evaluation into adds/requalifies/streak/removes.

Stable criteria gate watchlist membership (matching legacy STABLE_CRITERIA_NAMES).
Dynamic criteria are informational (populate `missing_criteria`).

Idempotency (spec §5.4): if a ticker's last_data_asof_date == today's data_asof_date,
streak/qualify operations are no-ops — re-running pipeline for the same session must
not double-count.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from swing.data.models import Candidate, WatchlistArchiveEntry, WatchlistEntry

# Names match swing/evaluation/criteria/*.py module names. STABLE = gates entry.
STABLE_CRITERION_NAMES: tuple[str, ...] = (
    "prior_trend",
    "ma_stack_short_stack",   # the "stack 10>20>50" half of ma_stack_short
    "ma_stack_short_rising",  # the "all rising" half
    "adr",
    "pullback",
    "orderliness",
    "risk_feasibility",
)
DYNAMIC_CRITERION_NAMES: tuple[str, ...] = (
    "proximity",
    "tightness",
    "vcp",  # volume contraction
)
AGING_STREAK_THRESHOLD = 3  # spec §5.4: 3 consecutive evaluated-but-not-qualifying runs


@dataclass(frozen=True)
class WatchlistDelta:
    adds: list[WatchlistEntry] = field(default_factory=list)
    requalifies: list[WatchlistEntry] = field(default_factory=list)
    streak_increments: list[WatchlistEntry] = field(default_factory=list)
    removes: list[WatchlistArchiveEntry] = field(default_factory=list)


def _stable_passes(c: Candidate) -> bool:
    by_name = {cr.criterion_name: cr.result for cr in c.criteria}
    return all(by_name.get(n) == "pass" for n in STABLE_CRITERION_NAMES)


def _missing_dynamic(c: Candidate) -> str | None:
    by_name = {cr.criterion_name: cr.result for cr in c.criteria}
    misses = [n for n in DYNAMIC_CRITERION_NAMES if by_name.get(n) != "pass"]
    return ";".join(misses) if misses else None


def compute_watchlist_changes(
    *, prior: Iterable[WatchlistEntry], today_candidates: Iterable[Candidate],
    data_asof_date: str,
) -> WatchlistDelta:
    prior_by_ticker = {e.ticker: e for e in prior}
    today_by_ticker = {c.ticker: c for c in today_candidates}
    delta = WatchlistDelta()

    # Process every ticker that's either prior-on-list or today-evaluated
    all_tickers = set(prior_by_ticker) | set(today_by_ticker)

    for ticker in sorted(all_tickers):
        existing = prior_by_ticker.get(ticker)
        candidate = today_by_ticker.get(ticker)

        if candidate is None:
            # Ticker on list but absent from today's batch — no-op (spec §5.4)
            continue

        # Idempotency guard (narrow): if we've already counted a streak event for
        # this exact (ticker, data_asof_date), a re-run must not double-increment.
        # BUT a corrected re-run may legitimately flip the decision (e.g. the first
        # CSV was bad; the corrected CSV re-qualifies). So we skip the streak
        # mutation path only, not the add/requalify path. Implementation below
        # checks this flag where streak_increments would be appended.
        already_counted_streak_today = (
            existing is not None and existing.last_data_asof_date == data_asof_date
        )

        # Spec §5.4 qualifying rule: "reached watch/A+ bucket", NOT merely
        # stable-criteria-passing. A bucket classified `skip` (too many dynamic
        # misses) must count as not-qualified for aging purposes.
        qualifies = _stable_passes(candidate) and candidate.bucket in ("watch", "aplus")
        if qualifies:
            # Guard: excluded/error candidates can have None pivot/initial_stop.
            # Watchlist targets require both; skip if missing.
            if candidate.pivot is None or candidate.initial_stop is None:
                continue
            missing_dyn = _missing_dynamic(candidate)
            if existing is None:
                # NEW QUALIFIER — add
                delta.adds.append(WatchlistEntry(
                    ticker=ticker, added_date=data_asof_date,
                    last_qualified_date=data_asof_date,
                    status=candidate.bucket if candidate.bucket in ("watch", "skip") else "watch",
                    qualification_count=1, not_qualified_streak=0,
                    last_data_asof_date=data_asof_date,
                    entry_target=candidate.pivot,
                    initial_stop_target=candidate.initial_stop,
                    last_close=candidate.close, last_pivot=candidate.pivot,
                    last_stop=candidate.initial_stop,
                    last_adr_pct=candidate.adr_pct,
                    missing_criteria=missing_dyn, notes=None,
                ))
            else:
                # RE-QUALIFY — bump count, refresh dynamic fields, FREEZE targets
                delta.requalifies.append(WatchlistEntry(
                    ticker=ticker, added_date=existing.added_date,
                    last_qualified_date=data_asof_date,
                    status=existing.status,
                    qualification_count=existing.qualification_count + 1,
                    not_qualified_streak=0,  # reset streak on requalify
                    last_data_asof_date=data_asof_date,
                    entry_target=existing.entry_target,
                    initial_stop_target=existing.initial_stop_target,
                    last_close=candidate.close, last_pivot=candidate.pivot,
                    last_stop=candidate.initial_stop,
                    last_adr_pct=candidate.adr_pct,
                    missing_criteria=missing_dyn, notes=existing.notes,
                ))
        else:
            # In batch but failed (not in watch/aplus bucket, or stable criterion failed).
            if existing is None:
                continue  # never on list, never qualified — ignore
            if already_counted_streak_today:
                # Re-run for same data date that already incremented streak — don't
                # double-count, and don't re-emit the archive row (would duplicate).
                continue
            new_streak = existing.not_qualified_streak + 1
            if new_streak >= AGING_STREAK_THRESHOLD:
                delta.removes.append(WatchlistArchiveEntry(
                    id=None, ticker=ticker, added_date=existing.added_date,
                    removed_date=data_asof_date,
                    reason=f"aged out (failed stable {new_streak} consecutive runs)",
                    qualification_count=existing.qualification_count,
                    last_data_asof_date=data_asof_date,
                    notes=existing.notes,
                ))
            else:
                delta.streak_increments.append(WatchlistEntry(
                    ticker=ticker, added_date=existing.added_date,
                    last_qualified_date=existing.last_qualified_date,
                    status=existing.status,
                    qualification_count=existing.qualification_count,
                    not_qualified_streak=new_streak,
                    last_data_asof_date=data_asof_date,
                    entry_target=existing.entry_target,
                    initial_stop_target=existing.initial_stop_target,
                    last_close=candidate.close, last_pivot=candidate.pivot,
                    last_stop=candidate.initial_stop,
                    last_adr_pct=candidate.adr_pct,
                    missing_criteria=_missing_dynamic(candidate), notes=existing.notes,
                ))
    return delta
```

**Note on stable criterion names:** Phase 1 implements `ma_stack_short` as a single module returning two `Result`s — `ma_stack_short_stack` and `ma_stack_short_rising` (per the criterion module's pattern). If Phase 1 uses different names, update `STABLE_CRITERION_NAMES` to match. Run `python -c "from swing.evaluation.criteria.ma_stack_short import evaluate; from inspect import getsource; print(getsource(evaluate))"` to confirm before this task.

- [ ] **Step 4: Verify** — `python -m pytest tests/watchlist/test_service.py -v` → 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/watchlist/__init__.py swing/watchlist/service.py tests/watchlist/__init__.py tests/watchlist/test_service.py
git commit -m "feat(watchlist): pure-logic partition (adds/requalifies/streak/removes) with idempotent aging"
```

---

### Task C2: Near-trigger pure rule

**Files:**
- Create: `swing/recommendations/__init__.py` (empty)
- Create: `swing/recommendations/near_trigger.py`
- Create: `tests/recommendations/__init__.py` (empty)
- Create: `tests/recommendations/test_near_trigger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/recommendations/test_near_trigger.py
"""Near-trigger detection rule (asymmetric window from legacy briefing)."""
from __future__ import annotations

from swing.recommendations.near_trigger import is_near_trigger, pct_from_pivot


def test_within_below_window():
    # 0.5% below pivot — inside default below=1.0
    assert is_near_trigger(price=99.5, entry_target=100.0)


def test_within_above_window():
    # 0.3% above pivot — inside default above=0.5
    assert is_near_trigger(price=100.3, entry_target=100.0)


def test_outside_above_window():
    # 0.7% above — extended/chase territory
    assert not is_near_trigger(price=100.7, entry_target=100.0)


def test_outside_below_window():
    # 1.2% below
    assert not is_near_trigger(price=98.8, entry_target=100.0)


def test_custom_thresholds():
    assert is_near_trigger(price=100.4, entry_target=100.0, above_pct=0.5, below_pct=2.0)
    assert not is_near_trigger(price=100.6, entry_target=100.0, above_pct=0.5, below_pct=2.0)


def test_pct_from_pivot_signed():
    assert pct_from_pivot(price=99.0, entry_target=100.0) == -1.0
    assert pct_from_pivot(price=101.0, entry_target=100.0) == 1.0
    assert pct_from_pivot(price=100.0, entry_target=100.0) == 0.0


def test_zero_target_raises():
    import pytest
    with pytest.raises(ValueError):
        pct_from_pivot(price=10.0, entry_target=0.0)
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/recommendations/near_trigger.py`**

```python
"""Near-trigger detection — asymmetric window from legacy briefing rule.

Default window: -1.0% to +0.5% from pivot. Asymmetric because >0.5% above pivot
is already extended/chase territory (entry there means worse R:R).
"""
from __future__ import annotations


def pct_from_pivot(*, price: float, entry_target: float) -> float:
    if entry_target <= 0:
        raise ValueError(f"entry_target must be > 0, got {entry_target}")
    return (price - entry_target) / entry_target * 100


def is_near_trigger(
    *, price: float, entry_target: float,
    above_pct: float = 0.5, below_pct: float = 1.0,
) -> bool:
    pct = pct_from_pivot(price=price, entry_target=entry_target)
    return -below_pct <= pct <= above_pct
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/recommendations/__init__.py swing/recommendations/near_trigger.py tests/recommendations/__init__.py tests/recommendations/test_near_trigger.py
git commit -m "feat(recommendations): asymmetric near-trigger window (pure)"
```

---

### Task C3: Position sizing

**Files:**
- Create: `swing/recommendations/sizing.py`
- Create: `tests/recommendations/test_sizing.py`

Ports legacy `compute_shares_from_stop()` math. The result includes `feasible: bool` so the consumer can flag impossible sizings (e.g., risk-per-share so high that even 1 share exceeds max_risk_pct).

- [ ] **Step 1: Write the failing test**

```python
# tests/recommendations/test_sizing.py
"""Position sizing — risk-based + position-cap dual constraint, with feasibility."""
from __future__ import annotations

import pytest

from swing.recommendations.sizing import compute_shares, SizingResult


def test_basic_sizing_constrained_by_risk():
    # entry=100, stop=98, equity=1200, max_risk=0.5% → $6 risk → 3 shares (rps=$2)
    r = compute_shares(entry=100.0, stop=98.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.shares == 3
    assert r.risk_dollars == pytest.approx(6.0)
    assert r.feasible is True
    assert r.constraint == "risk"


def test_sizing_constrained_by_position_cap():
    # 15% position cap on $1200 = $180 / $100 = 1 share (vs risk allows 3)
    r = compute_shares(entry=100.0, stop=99.5, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    # $180 / $100 = 1 share max
    assert r.shares == 1
    assert r.constraint == "position_cap"


def test_infeasible_when_rps_exceeds_max_risk():
    # 1 share would risk $50; max risk is $6 → infeasible
    r = compute_shares(entry=100.0, stop=50.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.shares == 0
    assert r.feasible is False
    assert r.constraint == "infeasible"


def test_invalid_stop_above_entry_raises():
    with pytest.raises(ValueError, match="stop must be < entry"):
        compute_shares(entry=100.0, stop=105.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)


def test_zero_equity_returns_zero_shares():
    r = compute_shares(entry=100.0, stop=98.0, equity=0.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.shares == 0
    assert r.feasible is False


def test_result_carries_metrics():
    r = compute_shares(entry=100.0, stop=98.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.notional == 300.0
    assert r.notional_pct == pytest.approx(25.0)
    assert r.risk_pct == pytest.approx(0.5)
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/recommendations/sizing.py`**

```python
"""Risk-based + position-cap position sizing.

Two constraints (binding constraint reported in `constraint`):
  - Risk: shares <= max_risk_dollars / risk_per_share
  - Position cap: shares <= (equity * position_pct_cap) / entry_price

Floor of zero shares with feasible=False if even 1 share exceeds max risk.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SizingResult:
    shares: int
    risk_dollars: float       # actual risk at chosen size
    risk_pct: float           # actual risk % at chosen size
    notional: float           # entry * shares
    notional_pct: float       # notional / equity * 100
    feasible: bool
    constraint: str           # 'risk' | 'position_cap' | 'infeasible' | 'no_equity'


def compute_shares(
    *, entry: float, stop: float, equity: float,
    max_risk_pct: float, position_pct_cap: float,
) -> SizingResult:
    if stop >= entry:
        raise ValueError(f"stop must be < entry; got entry={entry}, stop={stop}")

    if equity <= 0:
        return SizingResult(
            shares=0, risk_dollars=0.0, risk_pct=0.0,
            notional=0.0, notional_pct=0.0,
            feasible=False, constraint="no_equity",
        )

    rps = entry - stop
    max_risk_dollars = equity * max_risk_pct
    shares_by_risk = math.floor(max_risk_dollars / rps) if rps > 0 else 0
    shares_by_cap = math.floor((equity * position_pct_cap) / entry) if entry > 0 else 0
    shares = min(shares_by_risk, shares_by_cap)

    if shares <= 0:
        return SizingResult(
            shares=0, risk_dollars=0.0, risk_pct=0.0,
            notional=0.0, notional_pct=0.0,
            feasible=False, constraint="infeasible",
        )

    risk_dollars = shares * rps
    notional = shares * entry
    constraint = "risk" if shares_by_risk <= shares_by_cap else "position_cap"
    return SizingResult(
        shares=shares,
        risk_dollars=risk_dollars,
        risk_pct=risk_dollars / equity * 100,
        notional=notional,
        notional_pct=notional / equity * 100,
        feasible=True,
        constraint=constraint,
    )
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/recommendations/sizing.py tests/recommendations/test_sizing.py
git commit -m "feat(recommendations): risk + position-cap dual-constraint sizing"
```

---

### Task C4: Focus ranking

**Files:**
- Create: `swing/recommendations/focus_ranking.py`
- Create: `tests/recommendations/test_focus_ranking.py`

Composite score = normalized closeness_to_pivot * w1 + normalized adr * w2 + normalized prior_trend * w3 (each normalized 0-1 across the input set; ties broken by ticker alpha).

- [ ] **Step 1: Write the failing test**

```python
# tests/recommendations/test_focus_ranking.py
from __future__ import annotations

from swing.data.models import Candidate
from swing.recommendations.focus_ranking import rank_focus, FocusWeights


def _c(t: str, *, close: float, pivot: float, adr: float, trend: float) -> Candidate:
    return Candidate(
        ticker=t, bucket="aplus", close=close, pivot=pivot,
        initial_stop=close * 0.95, adr_pct=adr, tight_streak=3,
        pullback_pct=10.0, prior_trend_pct=trend, rs_rank=80,
        rs_return_12w_vs_spy=0.15, rs_method="universe",
        pattern_tag=None, notes=None, criteria=(),
    )


def test_ranking_orders_by_composite():
    # Three A+ names: closer-to-pivot + higher ADR + higher trend should rank first
    cands = [
        _c("BEST", close=100.5, pivot=101.0, adr=6.0, trend=50.0),  # 0.5% from pivot, hot
        _c("MID",  close=100.0, pivot=102.0, adr=5.0, trend=40.0),  # 2% from pivot
        _c("LOW",  close=98.0,  pivot=104.0, adr=4.0, trend=30.0),  # 5.8% from pivot
    ]
    ranked = rank_focus(cands, weights=FocusWeights(
        closeness_to_pivot=0.5, adr=0.25, prior_trend=0.25,
    ))
    assert [c.ticker for c in ranked] == ["BEST", "MID", "LOW"]


def test_ranking_breaks_ties_by_ticker():
    cands = [
        _c("MSFT", close=100.0, pivot=101.0, adr=5.0, trend=40.0),
        _c("AAPL", close=100.0, pivot=101.0, adr=5.0, trend=40.0),
    ]
    ranked = rank_focus(cands, weights=FocusWeights(0.5, 0.25, 0.25))
    assert [c.ticker for c in ranked] == ["AAPL", "MSFT"]


def test_empty_input_returns_empty():
    assert rank_focus([], weights=FocusWeights(0.5, 0.25, 0.25)) == []


def test_single_input_unchanged():
    c = _c("AAPL", close=100.0, pivot=101.0, adr=5.0, trend=40.0)
    assert rank_focus([c], weights=FocusWeights(0.5, 0.25, 0.25)) == [c]
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/recommendations/focus_ranking.py`**

```python
"""Composite weighted focus ranking for A+ candidates (legacy parity).

Inputs normalized to [0, 1] across the set:
  closeness_to_pivot = 1 - clamp(|close - pivot| / pivot)
  adr_norm = adr / max_adr
  trend_norm = trend / max_trend
Score = sum(w * normalized).
Ties broken by ticker alpha (deterministic).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from swing.data.models import Candidate


@dataclass(frozen=True)
class FocusWeights:
    closeness_to_pivot: float
    adr: float
    prior_trend: float


def _safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def rank_focus(candidates: Iterable[Candidate], *, weights: FocusWeights) -> list[Candidate]:
    cands = list(candidates)
    if not cands:
        return []

    # Normalize per dimension across the set
    closenesses = []
    adrs = []
    trends = []
    for c in cands:
        if c.pivot and c.pivot > 0 and c.close is not None:
            dist = abs(c.close - c.pivot) / c.pivot
            closenesses.append(max(0.0, 1.0 - dist))
        else:
            closenesses.append(0.0)
        adrs.append(c.adr_pct or 0.0)
        trends.append(c.prior_trend_pct or 0.0)

    max_adr = max(adrs) if adrs else 0.0
    max_trend = max(trends) if trends else 0.0

    scored: list[tuple[float, str, Candidate]] = []
    for c, cl, a, t in zip(cands, closenesses, adrs, trends):
        score = (
            weights.closeness_to_pivot * cl
            + weights.adr * _safe_div(a, max_adr)
            + weights.prior_trend * _safe_div(t, max_trend)
        )
        scored.append((score, c.ticker, c))

    scored.sort(key=lambda x: (-x[0], x[1]))  # desc score, asc ticker
    return [c for _, _, c in scored]
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/recommendations/focus_ranking.py tests/recommendations/test_focus_ranking.py
git commit -m "feat(recommendations): composite focus ranking (closeness/adr/trend)"
```

---

### Task C5: Build daily recommendations

**Files:**
- Create: `swing/recommendations/build.py`
- Create: `tests/recommendations/test_build.py`

Combines bucket assignments + watchlist + sizing + near-trigger into the immutable per-session snapshot. The `pipeline.runner` calls this and persists via `recommendations` repo.

- [ ] **Step 1: Write the failing test**

```python
# tests/recommendations/test_build.py
"""Recommendation builder: combines candidates + watchlist + equity → DailyRecommendation list."""
from __future__ import annotations

from swing.data.models import Candidate, DailyRecommendation, WatchlistEntry
from swing.recommendations.build import build_recommendations, BuildContext
from swing.recommendations.sizing import SizingResult


def _candidate(ticker: str, bucket: str = "aplus", *, close: float = 100.0,
               pivot: float = 100.5, stop: float = 95.0) -> Candidate:
    return Candidate(
        ticker=ticker, bucket=bucket, close=close, pivot=pivot,
        initial_stop=stop, adr_pct=5.0, tight_streak=3, pullback_pct=10.0,
        prior_trend_pct=30.0, rs_rank=85, rs_return_12w_vs_spy=0.20,
        rs_method="universe", pattern_tag=None, notes=None, criteria=(),
    )


def _wl(ticker: str, target: float = 100.5, last_close: float = 100.0) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=ticker, added_date="2026-04-12", last_qualified_date="2026-04-15",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-04-15", entry_target=target,
        initial_stop_target=95.0, last_close=last_close, last_pivot=target,
        last_stop=95.0, last_adr_pct=5.0, missing_criteria=None, notes=None,
    )


def test_aplus_becomes_today_decision():
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    recs = build_recommendations(
        ctx=ctx,
        today_aplus=[_candidate("NVDA", "aplus")],
        prior_watchlist=[],
    )
    assert len(recs) == 1
    rec = recs[0]
    assert rec.ticker == "NVDA"
    assert rec.recommendation == "today_decision"
    assert rec.shares is not None and rec.shares > 0
    assert rec.action_text and "Buy-stop" in rec.action_text
    assert rec.entry_target == 100.5


def test_watchlist_near_trigger_recommended():
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    # MSFT on watchlist, last close very close to target
    recs = build_recommendations(
        ctx=ctx, today_aplus=[],
        prior_watchlist=[_wl("MSFT", target=100.0, last_close=99.7)],
    )
    near = [r for r in recs if r.recommendation == "near_trigger"]
    assert len(near) == 1
    assert near[0].ticker == "MSFT"


def test_aplus_already_on_watchlist_yields_only_today_decision_not_double():
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    recs = build_recommendations(
        ctx=ctx,
        today_aplus=[_candidate("NVDA", "aplus", close=99.7, pivot=100.0)],
        prior_watchlist=[_wl("NVDA", target=100.0, last_close=99.7)],
    )
    nvda_recs = [r for r in recs if r.ticker == "NVDA"]
    types = {r.recommendation for r in nvda_recs}
    assert types == {"today_decision"}  # not also near_trigger — A+ wins precedence


def test_infeasible_sizing_still_produces_today_decision_with_zero_shares():
    """Spec says today_decision is the immutable snapshot — even infeasible names get listed."""
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    # Wide stop on cheap stock — risk too high
    recs = build_recommendations(
        ctx=ctx,
        today_aplus=[_candidate("WIDE", "aplus", close=100.0, pivot=100.0, stop=50.0)],
        prior_watchlist=[],
    )
    assert len(recs) == 1
    assert recs[0].shares == 0
    assert "infeasible" in (recs[0].action_text or "").lower() or recs[0].risk_dollars == 0.0
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/recommendations/build.py`**

```python
"""Build the immutable per-session DailyRecommendation snapshot.

Precedence: ticker classified as A+ today wins → today_decision (skip near_trigger to avoid double).
Watchlist tickers near pivot → near_trigger.
Watchlist tickers in watch state → watchlist_watch (informational).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from swing.data.models import Candidate, DailyRecommendation, WatchlistEntry
from swing.recommendations.near_trigger import is_near_trigger
from swing.recommendations.sizing import compute_shares


@dataclass(frozen=True)
class BuildContext:
    evaluation_run_id: int
    data_asof_date: str
    action_session_date: str
    current_equity: float
    max_risk_pct: float
    position_pct_cap: float
    near_trigger_above_pct: float = 0.5
    near_trigger_below_pct: float = 1.0


def _format_action(shares: int, entry: float, risk_dollars: float, infeasible: bool) -> str:
    if infeasible:
        return "Risk infeasible at current sizing — skip or wait for tighter setup"
    return f"Buy-stop limit ${entry:.2f} · {shares} sh · ${risk_dollars:.0f} risk"


def build_recommendations(
    *, ctx: BuildContext,
    today_aplus: Iterable[Candidate],
    prior_watchlist: Iterable[WatchlistEntry],
) -> list[DailyRecommendation]:
    aplus_list = list(today_aplus)
    aplus_tickers = {c.ticker for c in aplus_list}

    recs: list[DailyRecommendation] = []

    # 1. A+ names → today_decision (with sizing)
    for c in aplus_list:
        sizing = compute_shares(
            entry=c.pivot, stop=c.initial_stop, equity=ctx.current_equity,
            max_risk_pct=ctx.max_risk_pct, position_pct_cap=ctx.position_pct_cap,
        )
        infeasible = not sizing.feasible
        recs.append(DailyRecommendation(
            id=None, evaluation_run_id=ctx.evaluation_run_id,
            data_asof_date=ctx.data_asof_date,
            action_session_date=ctx.action_session_date,
            ticker=c.ticker, recommendation="today_decision",
            action_text=_format_action(sizing.shares, c.pivot, sizing.risk_dollars, infeasible),
            entry_target=c.pivot, stop_target=c.initial_stop,
            shares=sizing.shares,
            risk_dollars=sizing.risk_dollars, risk_pct=sizing.risk_pct,
            rationale=f"A+ setup, {c.adr_pct:.1f}% ADR, {c.prior_trend_pct:.0f}% prior trend",
        ))

    # 2. Watchlist near-trigger → near_trigger (skip if already in today_decision)
    for w in prior_watchlist:
        if w.ticker in aplus_tickers:
            continue
        if w.last_close is None or w.entry_target is None:
            continue
        if not is_near_trigger(
            price=w.last_close, entry_target=w.entry_target,
            above_pct=ctx.near_trigger_above_pct,
            below_pct=ctx.near_trigger_below_pct,
        ):
            continue
        sizing = compute_shares(
            entry=w.entry_target, stop=w.initial_stop_target or 0.0,
            equity=ctx.current_equity, max_risk_pct=ctx.max_risk_pct,
            position_pct_cap=ctx.position_pct_cap,
        ) if w.initial_stop_target else None
        recs.append(DailyRecommendation(
            id=None, evaluation_run_id=ctx.evaluation_run_id,
            data_asof_date=ctx.data_asof_date,
            action_session_date=ctx.action_session_date,
            ticker=w.ticker, recommendation="near_trigger",
            action_text=(
                _format_action(sizing.shares, w.entry_target, sizing.risk_dollars, not sizing.feasible)
                if sizing else "Pivot reached — review setup"
            ),
            entry_target=w.entry_target, stop_target=w.initial_stop_target,
            shares=sizing.shares if sizing else None,
            risk_dollars=sizing.risk_dollars if sizing else None,
            risk_pct=sizing.risk_pct if sizing else None,
            rationale=f"Watchlist · {w.qualification_count} qualifies",
        ))

    return recs
```

- [ ] **Step 4: Verify** — `python -m pytest tests/recommendations/test_build.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/recommendations/build.py tests/recommendations/test_build.py
git commit -m "feat(recommendations): build per-session snapshot from candidates + watchlist"
```

---

### Task C6: Config additions for sub-phase C/D/G

**Files:**
- Modify: `swing.config.toml` — add `[near_trigger]`, `[stop_advisory]`, `[pipeline]`, `[export]` sections
- Modify: `swing/config.py` — load + dataclass
- Create/extend: `tests/config/test_config_phase2.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/config/test_config_phase2.py
"""Phase 2 config sections load with defaults + overrides."""
from __future__ import annotations

from pathlib import Path

from swing.config import load


def test_phase2_defaults_load_when_sections_absent(tmp_path: Path):
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(
        """[paths]
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
allowed_miss_names = ["TT8_rs_rank"]
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
    cfg = load(cfg_path)

    # Phase 2 defaults populated even though TOML has no [near_trigger] etc.
    assert cfg.near_trigger.above_pct == 0.5
    assert cfg.near_trigger.below_pct == 1.0
    assert cfg.stop_advisory.breakeven_r_trigger == 1.0
    assert cfg.stop_advisory.trail_10ma_buffer_pct == 0.3
    assert cfg.stop_advisory.trail_20ma_buffer_pct == 0.3
    assert cfg.stop_advisory.time_stop_days == 10
    assert cfg.sizing.position_pct_cap == 0.15
    assert cfg.pipeline.stale_lease_threshold_seconds == 300
    assert cfg.pipeline.stale_step_threshold_seconds == 900
    assert cfg.pipeline.heartbeat_interval_seconds == 30
    assert cfg.export.size_cap_kb == 500
    assert cfg.export.retain_markdown_sibling is True
    assert cfg.export.retention_days == 90


def test_phase2_overrides_apply(tmp_path: Path):
    base = (tmp_path / "swing.config.toml")
    base.write_text(
        # Minimal Phase 1 config + override
        """[paths]
db_path = "x.db"
data_dir = "x"
logs_dir = "x/logs"
charts_dir = "x/charts"
backups_dir = "x/backups"
prices_cache_dir = "x/cache"
finviz_inbox_dir = "x/inbox"
exports_dir = "x/exports"
rs_universe_path = "x/rs.csv"

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
allowed_miss_names = ["TT8_rs_rank"]
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

[near_trigger]
above_pct = 0.7
below_pct = 1.5

[pipeline]
heartbeat_interval_seconds = 60
""",
        encoding="utf-8",
    )
    cfg = load(base)
    assert cfg.near_trigger.above_pct == 0.7
    assert cfg.near_trigger.below_pct == 1.5
    assert cfg.pipeline.heartbeat_interval_seconds == 60
    # Other defaults still in place
    assert cfg.stop_advisory.breakeven_r_trigger == 1.0
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Modify `swing/config.py`** — add new dataclasses + defaults

Add the following frozen dataclasses (alongside existing Phase 1 ones):

```python
@dataclass(frozen=True)
class NearTriggerConfig:
    above_pct: float = 0.5
    below_pct: float = 1.0


@dataclass(frozen=True)
class StopAdvisoryConfig:
    breakeven_r_trigger: float = 1.0
    trail_10ma_buffer_pct: float = 0.3
    trail_20ma_buffer_pct: float = 0.3
    time_stop_days: int = 10
    time_stop_min_r: float = 0.5


@dataclass(frozen=True)
class SizingConfig:
    """Position-sizing caps (spec §4, legacy parity)."""
    position_pct_cap: float = 0.15        # max notional as fraction of sizing equity


@dataclass(frozen=True)
class PipelineConfig:
    stale_lease_threshold_seconds: int = 300       # spec §5.6
    stale_step_threshold_seconds: int = 900         # spec §5.6
    heartbeat_interval_seconds: int = 30            # spec §5.6
    block_if_running_within_seconds: int = 120      # spec §5.1.1
    staging_orphan_age_seconds: int = 3600          # spec §5.7 (1h for manifest-less staging)
    prev_dir_retention_days: int = 7                 # spec §5.7
    chart_top_n_watch: int = 5                       # legacy parity


@dataclass(frozen=True)
class ExportConfig:
    size_cap_kb: int = 500
    retain_markdown_sibling: bool = True            # spec §6.4 transition flag
    retention_days: int = 90
    archive_compression_format: str = "zip"
```

Add fields to the top-level `Config` dataclass:

```python
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
    # Phase 2 additions (all default-able)
    near_trigger: NearTriggerConfig
    stop_advisory: StopAdvisoryConfig
    sizing: SizingConfig
    pipeline: PipelineConfig
    export: ExportConfig
```

In `load()`, after existing parses, add:

```python
near_trigger = NearTriggerConfig(**raw.get("near_trigger", {}))
stop_advisory = StopAdvisoryConfig(**raw.get("stop_advisory", {}))
sizing = SizingConfig(**raw.get("sizing", {}))
pipeline = PipelineConfig(**raw.get("pipeline", {}))
export = ExportConfig(**raw.get("export", {}))
```

And include them in the `Config(...)` constructor call.

- [ ] **Step 4: Modify `swing.config.toml`** — append documented Phase 2 sections (visible to user but optional)

```toml
[near_trigger]
# Asymmetric window for "watchlist near pivot" detection (spec §6.1, legacy briefing)
above_pct = 0.5
below_pct = 1.0

[stop_advisory]
# Stop-management suggestion thresholds (spec §6.1 Open Positions; legacy trade.py)
breakeven_r_trigger = 1.0      # advise breakeven when gain >= 1R
trail_10ma_buffer_pct = 0.3    # trail stop to 10MA - N%
trail_20ma_buffer_pct = 0.3
time_stop_days = 10            # advise time-stop after N days
time_stop_min_r = 0.5          # ... if gain still below this R

[sizing]
# Position-sizing constraint (legacy parity). Risk cap is in [risk] section above.
position_pct_cap = 0.15        # max notional as fraction of sizing equity

[pipeline]
# Lease + heartbeat + staging (spec §5.6, §5.7)
stale_lease_threshold_seconds = 300       # 5 min
stale_step_threshold_seconds = 900         # 15 min
heartbeat_interval_seconds = 30
block_if_running_within_seconds = 120     # concurrent-run rejection window
staging_orphan_age_seconds = 3600          # delete .staging/ without manifest after 1h
prev_dir_retention_days = 7                # delete .prev/ after N days
chart_top_n_watch = 5                       # render charts for top-N near-trigger watchlist

[export]
# Briefing export (spec §6.4)
size_cap_kb = 500
retain_markdown_sibling = true              # set false after 20 clean runs + sign-off
retention_days = 90
archive_compression_format = "zip"
```

- [ ] **Step 5: Verify** — `python -m pytest tests/config/ -v` → all PASS (existing + new).

- [ ] **Step 6: Commit**

```bash
git add swing/config.py swing.config.toml tests/config/test_config_phase2.py
git commit -m "feat(config): add Phase 2 sections (near_trigger, stop_advisory, pipeline, export) with defaults"
```

---

## Sub-Phase D — Chart + Briefing Rendering

The pipeline produces a self-contained `briefing.html` per session (spec §6.4) plus per-ticker chart PNGs and a transitional `briefing.md`. Phase 3 will reuse the same view models for live HTMX-rendered partials.

### Task D1: View models

**Files:**
- Create: `swing/rendering/__init__.py` (empty)
- Create: `swing/rendering/view_models.py`
- Create: `tests/rendering/__init__.py` (empty)
- Create: `tests/rendering/test_view_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/rendering/test_view_models.py
"""View model dataclasses — instantiation + sub-component shape."""
from __future__ import annotations

from swing.rendering.view_models import (
    BriefingViewModel, StatusStripVM, WeatherTileVM, AccountTileVM,
    PipelineTileVM, TodaysDecisionVM, OpenPositionVM, AdvisorySuggestionVM,
    WatchlistRowVM, TickerExpansionVM, CriterionVM,
)


def test_briefing_viewmodel_instantiates():
    vm = BriefingViewModel(
        action_session_date="2026-04-16",
        data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="20MA rising; 10>20.",
                                   sizing_implication="Full sizing OK"),
            account=AccountTileVM(equity=1284.50, open_count=1, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="2026-04-15T21:49:00",
                                    is_stale=False, current_session_match=True),
        ),
        todays_decisions=[
            TodaysDecisionVM(ticker="NVDA", action_text="Buy-stop $850 · 2 sh",
                             entry_target=850.0, stop_target=820.0,
                             shares=2, risk_dollars=60.0, risk_pct=4.7,
                             rationale="VCP coil at 12-week base",
                             tt_score="7/8", vcp_score="10/10",
                             chart_b64=None),
        ],
        open_positions=[],
        watchlist=[],
        expansions=[],
    )
    assert vm.action_session_date == "2026-04-16"
    assert vm.status_strip.weather.status == "Bullish"
    assert vm.todays_decisions[0].shares == 2


def test_open_position_with_advisory():
    op = OpenPositionVM(
        ticker="AAPL", entry_price=180.0, current_stop=185.0, last_close=192.0,
        shares=10, unrealized_pnl=120.0, dist_to_stop_pct=3.6, r_so_far=1.2,
        days_open=8,
        advisory=[
            AdvisorySuggestionVM(rule="breakeven", message="Move stop to breakeven ($180)"),
            AdvisorySuggestionVM(rule="trail_10ma", message="Trail to $189.50 (-0.3% below 10MA)"),
        ],
    )
    assert len(op.advisory) == 2
    assert op.r_so_far == 1.2


def test_watchlist_row_with_near_trigger_flag():
    row = WatchlistRowVM(
        ticker="MSFT", entry_target=420.0, current_close=419.0,
        pct_to_pivot=-0.24, adr_pct=2.5, current_stop=410.0,
        is_near_trigger=True, status="watch",
        flag_tags=["TT✓", "VCP✓"], qualification_count=3,
    )
    assert row.is_near_trigger is True
    assert "TT✓" in row.flag_tags


def test_ticker_expansion():
    exp = TickerExpansionVM(
        ticker="NVDA", narrative="VCP coil; 12-week base; 65% prior trend.",
        trend_template_grid=[CriterionVM(name="TT1", result="pass", value="close>150MA AND close>200MA", rule="...")],
        vcp_grid=[CriterionVM(name="prior_trend", result="pass", value="65%", rule=">=25%")],
        chart_b64="data:image/png;base64,iVBOR...",
    )
    assert exp.ticker == "NVDA"
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/rendering/view_models.py`**

```python
"""View models for briefing rendering.

Frozen dataclasses — Jinja templates do presentation only, no computation.
Reused by Phase 3 for HTMX partials.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WeatherTileVM:
    status: str  # 'Bullish' | 'Caution' | 'Bearish'
    rationale: str
    sizing_implication: str


@dataclass(frozen=True)
class AccountTileVM:
    equity: float
    open_count: int
    soft_warn: int
    hard_cap: int


@dataclass(frozen=True)
class PipelineTileVM:
    last_run_ts: str
    is_stale: bool
    current_session_match: bool


@dataclass(frozen=True)
class StatusStripVM:
    weather: WeatherTileVM
    account: AccountTileVM
    pipeline: PipelineTileVM


@dataclass(frozen=True)
class TodaysDecisionVM:
    ticker: str
    action_text: str
    entry_target: float
    stop_target: float
    shares: int
    risk_dollars: float
    risk_pct: float
    rationale: str
    tt_score: str
    vcp_score: str
    chart_b64: str | None        # inline data URL, or None if using file link
    chart_href: str | None = None  # relative file link (spec §6.4 over-cap fallback)


@dataclass(frozen=True)
class AdvisorySuggestionVM:
    rule: str
    message: str


@dataclass(frozen=True)
class OpenPositionVM:
    ticker: str
    entry_price: float
    current_stop: float
    last_close: float
    shares: int
    unrealized_pnl: float
    dist_to_stop_pct: float
    r_so_far: float
    days_open: int
    advisory: list[AdvisorySuggestionVM] = field(default_factory=list)


@dataclass(frozen=True)
class WatchlistRowVM:
    ticker: str
    entry_target: float
    current_close: float
    pct_to_pivot: float
    adr_pct: float | None
    current_stop: float
    is_near_trigger: bool
    status: str
    flag_tags: list[str] = field(default_factory=list)
    qualification_count: int = 0


@dataclass(frozen=True)
class CriterionVM:
    name: str
    result: str  # 'pass' | 'fail' | 'na'
    value: str | None
    rule: str | None


@dataclass(frozen=True)
class TickerExpansionVM:
    ticker: str
    narrative: str
    trend_template_grid: list[CriterionVM] = field(default_factory=list)
    vcp_grid: list[CriterionVM] = field(default_factory=list)
    chart_b64: str | None = None
    chart_href: str | None = None  # relative file link fallback (spec §6.4)


@dataclass(frozen=True)
class BriefingViewModel:
    action_session_date: str
    data_asof_date: str
    generated_at: str
    status_strip: StatusStripVM
    todays_decisions: list[TodaysDecisionVM] = field(default_factory=list)
    open_positions: list[OpenPositionVM] = field(default_factory=list)
    watchlist: list[WatchlistRowVM] = field(default_factory=list)
    expansions: list[TickerExpansionVM] = field(default_factory=list)
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/rendering/__init__.py swing/rendering/view_models.py tests/rendering/__init__.py tests/rendering/test_view_models.py
git commit -m "feat(rendering): view model dataclasses for briefing"
```

---

### Task D2: Chart rendering (mplfinance, optional)

**Files:**
- Modify: `pyproject.toml` — add `mplfinance>=0.12` to `[project.optional-dependencies] charts`
- Create: `swing/rendering/charts.py`
- Create: `tests/rendering/test_charts.py`

Charts are an **optional** dep — pipeline degrades gracefully if not installed (`charts_status='skipped'` + dashboard placeholder).

- [ ] **Step 1: Add optional dep**

In `pyproject.toml` add (or extend):

```toml
[project.optional-dependencies]
charts = ["mplfinance>=0.12"]
```

Install: `python -m pip install -e ".[charts]"` (record this in commit message).

- [ ] **Step 2: Write the failing test**

```python
# tests/rendering/test_charts.py
"""Chart rendering — slow-marked because it requires matplotlib + mplfinance."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from swing.rendering.charts import render_chart, ChartingUnavailable


pytestmark = pytest.mark.slow  # heavy dep


def _ohlcv(n: int = 120):
    closes = [100.0 + i * 0.5 for i in range(n)]
    idx = pd.bdate_range(end="2026-04-15", periods=n)
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [10_000_000] * n,
    }, index=idx)


def test_render_chart_writes_png(tmp_path: Path):
    out = tmp_path / "AAPL.png"
    result = render_chart(
        ticker="AAPL", ohlcv=_ohlcv(),
        pivot=160.0, stop=150.0, output_path=out,
    )
    assert result == out
    assert out.exists() and out.stat().st_size > 1000  # non-empty PNG


def test_too_few_bars_returns_none(tmp_path: Path):
    out = tmp_path / "X.png"
    result = render_chart(
        ticker="X", ohlcv=_ohlcv(n=5),
        pivot=100.0, stop=95.0, output_path=out,
    )
    assert result is None  # silently skipped, not a failure
    assert not out.exists()
```

- [ ] **Step 3: Implement `swing/rendering/charts.py`**

```python
"""Chart rendering — mplfinance, optional. Pipeline degrades gracefully."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CHART_LOOKBACK_DAYS = 120
CONSOLIDATION_DAYS = 10
MIN_BARS = CONSOLIDATION_DAYS + 1


class ChartingUnavailable(RuntimeError):
    """mplfinance not installed — pipeline should set charts_status='skipped'."""


def render_chart(
    *, ticker: str, ohlcv: pd.DataFrame, pivot: float, stop: float,
    output_path: Path,
) -> Path | None:
    """Render a daily chart with SMAs 10/20/50 + pivot/stop hlines + consolidation marker.

    Returns the output path on success, None if data is too short.
    Raises ChartingUnavailable if mplfinance isn't installed (caller handles).
    """
    try:
        import mplfinance as mpf
    except ImportError as exc:
        raise ChartingUnavailable("mplfinance not installed") from exc

    df = ohlcv.tail(CHART_LOOKBACK_DAYS).copy()
    if len(df) < MIN_BARS:
        return None

    addplots = []
    closes = df["Close"]
    for window, color in ((10, "blue"), (20, "orange"), (50, "red")):
        sma = closes.rolling(window).mean()
        if not sma.isna().all():
            addplots.append(mpf.make_addplot(sma, color=color, width=1.0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mpf.plot(
        df, type="candle", volume=True, style="yahoo",
        figsize=(11, 6),
        title=f"{ticker} | pivot ${pivot:.2f} stop ${stop:.2f} | last {len(df)} bars",
        ylabel_lower="Volume",
        addplot=addplots,
        hlines=dict(hlines=[pivot, stop], colors=["green", "red"], linestyle="--"),
        vlines=dict(vlines=[df.index[-CONSOLIDATION_DAYS]], colors=["purple"], linestyle=":", alpha=0.5),
        savefig=dict(fname=str(output_path), dpi=100, bbox_inches="tight"),
    )
    return output_path
```

- [ ] **Step 4: Verify** — `python -m pytest tests/rendering/test_charts.py -v` (slow). If mplfinance not installed: skip is fine; flag for manual install.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml swing/rendering/charts.py tests/rendering/test_charts.py
git commit -m "feat(rendering): chart renderer (mplfinance optional dep)"
```

---

### Task D3: Briefing builder (view model construction)

**Files:**
- Create: `swing/rendering/briefing.py`
- Create: `tests/rendering/test_briefing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/rendering/test_briefing.py
"""build_briefing_view_model: assembles BriefingViewModel from primitive inputs."""
from __future__ import annotations

from datetime import date

from swing.data.models import (
    Candidate, DailyRecommendation, Trade, WatchlistEntry, WeatherRun,
)
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model


def _wr() -> WeatherRun:
    return WeatherRun(id=1, run_ts="2026-04-15T21:49:00", asof_date="2026-04-15",
                      ticker="QQQ", status="Bullish", close=480.0,
                      sma10=475.0, sma20=470.0, sma50=460.0,
                      slope20_5bar=0.5, slope10_5bar=0.7,
                      rationale="20MA rising; 10>20.")


def _rec(ticker: str = "NVDA") -> DailyRecommendation:
    return DailyRecommendation(
        id=1, evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", ticker=ticker,
        recommendation="today_decision",
        action_text="Buy-stop $850 · 2 sh · $60 risk",
        entry_target=850.0, stop_target=820.0, shares=2,
        risk_dollars=60.0, risk_pct=5.0,
        rationale="VCP coil at 12-week base",
    )


def test_minimal_briefing():
    vm = build_briefing_view_model(BriefingInputs(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        weather=_wr(),
        weather_is_stale=False,
        equity=1284.50, open_count=1, soft_warn=4, hard_cap=6,
        last_pipeline_ts="2026-04-15T21:49:00",
        pipeline_is_stale=False, current_session_match=True,
        recommendations=[_rec()],
        open_trades=[], open_trade_advisories={},
        open_trade_last_prices={},
        watchlist=[], watchlist_last_prices={},
        candidates_by_ticker={},
        chart_b64s={},
    ))
    assert vm.action_session_date == "2026-04-16"
    assert vm.status_strip.weather.status == "Bullish"
    assert vm.status_strip.weather.sizing_implication.lower().startswith("full")
    assert len(vm.todays_decisions) == 1
    assert vm.todays_decisions[0].ticker == "NVDA"


def test_caution_weather_changes_sizing_implication():
    wr = _wr()
    cautious_wr = WeatherRun(
        id=wr.id, run_ts=wr.run_ts, asof_date=wr.asof_date, ticker=wr.ticker,
        status="Caution", close=wr.close, sma10=wr.sma10, sma20=wr.sma20,
        sma50=wr.sma50, slope20_5bar=wr.slope20_5bar, slope10_5bar=wr.slope10_5bar,
        rationale="20MA flat",
    )
    vm = build_briefing_view_model(BriefingInputs(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        weather=cautious_wr, weather_is_stale=False,
        equity=1284.50, open_count=1, soft_warn=4, hard_cap=6,
        last_pipeline_ts="2026-04-15T21:49:00",
        pipeline_is_stale=False, current_session_match=True,
        recommendations=[_rec()],
        open_trades=[], open_trade_advisories={},
        open_trade_last_prices={},
        watchlist=[], watchlist_last_prices={},
        candidates_by_ticker={},
        chart_b64s={},
    ))
    assert "half" in vm.status_strip.weather.sizing_implication.lower() \
        or "tighten" in vm.status_strip.weather.sizing_implication.lower()


def test_stale_weather_marker():
    vm = build_briefing_view_model(BriefingInputs(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        weather=None, weather_is_stale=True,
        equity=1200.0, open_count=0, soft_warn=4, hard_cap=6,
        last_pipeline_ts="2026-04-15T21:49:00",
        pipeline_is_stale=False, current_session_match=True,
        recommendations=[], open_trades=[], open_trade_advisories={},
        open_trade_last_prices={},
        watchlist=[], watchlist_last_prices={},
        candidates_by_ticker={},
        chart_b64s={},
    ))
    assert vm.status_strip.weather.status == "STALE" or "stale" in vm.status_strip.weather.rationale.lower()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/rendering/briefing.py`**

```python
"""Build BriefingViewModel from primitive inputs (DB rows + computed values).

Caller (pipeline.runner or CLI) does the queries; this module is pure-logic
view-model construction with no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from swing.data.models import (
    Candidate, DailyRecommendation, Trade, WatchlistEntry, WeatherRun,
)
from swing.rendering.view_models import (
    AccountTileVM, AdvisorySuggestionVM, BriefingViewModel, CriterionVM,
    OpenPositionVM, PipelineTileVM, StatusStripVM, TickerExpansionVM,
    TodaysDecisionVM, WatchlistRowVM, WeatherTileVM,
)


@dataclass(frozen=True)
class BriefingInputs:
    action_session_date: str
    data_asof_date: str
    generated_at: str
    weather: WeatherRun | None
    weather_is_stale: bool
    equity: float
    open_count: int
    soft_warn: int
    hard_cap: int
    last_pipeline_ts: str
    pipeline_is_stale: bool
    current_session_match: bool
    recommendations: list[DailyRecommendation]
    open_trades: list[Trade]
    open_trade_advisories: Mapping[int, list[AdvisorySuggestionVM]] = field(default_factory=dict)
    open_trade_last_prices: Mapping[str, float] = field(default_factory=dict)
    watchlist: list[WatchlistEntry] = field(default_factory=list)
    watchlist_last_prices: Mapping[str, float] = field(default_factory=dict)
    candidates_by_ticker: Mapping[str, Candidate] = field(default_factory=dict)
    chart_b64s: Mapping[str, str] = field(default_factory=dict)
    near_trigger_above_pct: float = 0.5
    near_trigger_below_pct: float = 1.0


def _sizing_implication(status: str) -> str:
    return {
        "Bullish": "Full sizing OK",
        "Caution": "Tighten stops; consider half sizing on new entries",
        "Bearish": "Avoid new longs; tighten stops on opens",
    }.get(status, "Sizing implication unknown")


def _weather_tile(inputs: BriefingInputs) -> WeatherTileVM:
    if inputs.weather is None or inputs.weather_is_stale:
        return WeatherTileVM(
            status="STALE", rationale="Weather data unavailable — verify before sizing",
            sizing_implication="Caution: verify weather before sizing",
        )
    return WeatherTileVM(
        status=inputs.weather.status,
        rationale=inputs.weather.rationale or "",
        sizing_implication=_sizing_implication(inputs.weather.status),
    )


def _decisions(inputs: BriefingInputs) -> list[TodaysDecisionVM]:
    out: list[TodaysDecisionVM] = []
    for r in inputs.recommendations:
        if r.recommendation != "today_decision":
            continue
        c = inputs.candidates_by_ticker.get(r.ticker)
        tt_score = ""
        vcp_score = ""
        if c is not None:
            tt_pass = sum(1 for cr in c.criteria if cr.layer == "trend_template" and cr.result == "pass")
            tt_total = sum(1 for cr in c.criteria if cr.layer == "trend_template")
            vcp_pass = sum(1 for cr in c.criteria if cr.layer == "vcp" and cr.result == "pass")
            vcp_total = sum(1 for cr in c.criteria if cr.layer == "vcp")
            tt_score = f"{tt_pass}/{tt_total}"
            vcp_score = f"{vcp_pass}/{vcp_total}"
        out.append(TodaysDecisionVM(
            ticker=r.ticker,
            action_text=r.action_text or "",
            entry_target=r.entry_target or 0.0,
            stop_target=r.stop_target or 0.0,
            shares=r.shares or 0,
            risk_dollars=r.risk_dollars or 0.0,
            risk_pct=r.risk_pct or 0.0,
            rationale=r.rationale or "",
            tt_score=tt_score, vcp_score=vcp_score,
            chart_b64=inputs.chart_b64s.get(r.ticker),
        ))
    return out


def _open_positions(inputs: BriefingInputs) -> list[OpenPositionVM]:
    from datetime import date as _date
    today = _date.fromisoformat(inputs.data_asof_date)
    out: list[OpenPositionVM] = []
    for t in inputs.open_trades:
        last = inputs.open_trade_last_prices.get(t.ticker, t.entry_price)
        rps = t.entry_price - t.initial_stop
        r_so_far = (last - t.entry_price) / rps if rps > 0 else 0.0
        unrl = (last - t.entry_price) * t.initial_shares
        dist_to_stop_pct = (last - t.current_stop) / last * 100 if last > 0 else 0.0
        days_open = (today - _date.fromisoformat(t.entry_date)).days
        out.append(OpenPositionVM(
            ticker=t.ticker, entry_price=t.entry_price, current_stop=t.current_stop,
            last_close=last, shares=t.initial_shares, unrealized_pnl=unrl,
            dist_to_stop_pct=dist_to_stop_pct, r_so_far=r_so_far,
            days_open=days_open,
            advisory=list(inputs.open_trade_advisories.get(t.id or 0, [])),
        ))
    return out


def _watchlist_rows(inputs: BriefingInputs) -> list[WatchlistRowVM]:
    out: list[WatchlistRowVM] = []
    for w in inputs.watchlist:
        last = inputs.watchlist_last_prices.get(w.ticker, w.last_close or 0.0)
        target = w.entry_target or 0.0
        if target > 0:
            pct = (last - target) / target * 100
            near = -inputs.near_trigger_below_pct <= pct <= inputs.near_trigger_above_pct
        else:
            pct = 0.0
            near = False
        out.append(WatchlistRowVM(
            ticker=w.ticker, entry_target=target, current_close=last,
            pct_to_pivot=pct, adr_pct=w.last_adr_pct,
            current_stop=w.initial_stop_target or 0.0,
            is_near_trigger=near, status=w.status,
            flag_tags=[],  # populated upstream
            qualification_count=w.qualification_count,
        ))
    # near-trigger first, then by abs distance
    out.sort(key=lambda r: (not r.is_near_trigger, abs(r.pct_to_pivot)))
    return out


def _expansions(inputs: BriefingInputs) -> list[TickerExpansionVM]:
    out: list[TickerExpansionVM] = []
    for r in inputs.recommendations:
        if r.recommendation != "today_decision":
            continue
        c = inputs.candidates_by_ticker.get(r.ticker)
        if c is None:
            continue
        tt = [
            CriterionVM(name=cr.criterion_name, result=cr.result,
                        value=cr.value, rule=cr.rule)
            for cr in c.criteria if cr.layer == "trend_template"
        ]
        vcp = [
            CriterionVM(name=cr.criterion_name, result=cr.result,
                        value=cr.value, rule=cr.rule)
            for cr in c.criteria if cr.layer == "vcp"
        ]
        out.append(TickerExpansionVM(
            ticker=r.ticker,
            narrative=r.rationale or "",
            trend_template_grid=tt,
            vcp_grid=vcp,
            chart_b64=inputs.chart_b64s.get(r.ticker),
        ))
    return out


def build_briefing_view_model(inputs: BriefingInputs) -> BriefingViewModel:
    return BriefingViewModel(
        action_session_date=inputs.action_session_date,
        data_asof_date=inputs.data_asof_date,
        generated_at=inputs.generated_at,
        status_strip=StatusStripVM(
            weather=_weather_tile(inputs),
            account=AccountTileVM(
                equity=inputs.equity, open_count=inputs.open_count,
                soft_warn=inputs.soft_warn, hard_cap=inputs.hard_cap,
            ),
            pipeline=PipelineTileVM(
                last_run_ts=inputs.last_pipeline_ts,
                is_stale=inputs.pipeline_is_stale,
                current_session_match=inputs.current_session_match,
            ),
        ),
        todays_decisions=_decisions(inputs),
        open_positions=_open_positions(inputs),
        watchlist=_watchlist_rows(inputs),
        expansions=_expansions(inputs),
    )
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/rendering/briefing.py tests/rendering/test_briefing.py
git commit -m "feat(rendering): build_briefing_view_model — pure assembler"
```

---

### Task D4: Jinja template + HTML renderer

**Files:**
- Modify: `pyproject.toml` — add `jinja2>=3.1` to main `[project] dependencies`
- Create: `swing/rendering/templates/briefing.html.j2`
- Create: `swing/rendering/html_renderer.py`
- Create: `tests/rendering/test_html_renderer.py`

The template is single-file, all CSS inline, no external assets — so the resulting `briefing.html` is a portable disaster-recovery artifact (spec §6.4).

- [ ] **Step 1: Add jinja2 to pyproject.toml main deps**

```toml
dependencies = [
    # ... existing Phase 1 deps ...
    "jinja2>=3.1",
]
```

Install: `python -m pip install -e .`

- [ ] **Step 2: Write the failing test**

```python
# tests/rendering/test_html_renderer.py
"""HTML renderer — produces self-contained briefing.html from a view model."""
from __future__ import annotations

from swing.rendering.html_renderer import render_briefing_html
from swing.rendering.view_models import (
    AccountTileVM, BriefingViewModel, PipelineTileVM, StatusStripVM,
    TodaysDecisionVM, WeatherTileVM,
)


def _vm(decisions=None, status="Bullish") -> BriefingViewModel:
    return BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status=status, rationale="r", sizing_implication="OK"),
            account=AccountTileVM(equity=1284.50, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="2026-04-15T21:49:00",
                                    is_stale=False, current_session_match=True),
        ),
        todays_decisions=decisions or [],
        open_positions=[], watchlist=[], expansions=[],
    )


def test_empty_renders():
    html = render_briefing_html(_vm())
    assert "<html" in html.lower()
    assert "Bullish" in html
    assert "No decisions today" in html


def test_with_decision_renders_action_text():
    vm = _vm(decisions=[
        TodaysDecisionVM(
            ticker="NVDA", action_text="Buy-stop $850 · 2 sh",
            entry_target=850.0, stop_target=820.0, shares=2,
            risk_dollars=60.0, risk_pct=4.7, rationale="VCP coil",
            tt_score="7/8", vcp_score="10/10", chart_b64=None,
        ),
    ])
    html = render_briefing_html(vm)
    assert "NVDA" in html
    assert "Buy-stop $850" in html


def test_self_contained_no_external_links():
    """Spec §6.4: HTML is portable, all CSS inline, no external <link> or <script src>."""
    vm = _vm()
    html = render_briefing_html(vm)
    assert "<link" not in html.lower() or "rel=\"stylesheet\"" not in html.lower()
    assert "<script src" not in html.lower()


def test_action_session_date_in_title():
    html = render_briefing_html(_vm())
    assert "2026-04-16" in html
```

- [ ] **Step 3: Implement template** `swing/rendering/templates/briefing.html.j2`

```jinja
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Swing Briefing — {{ vm.action_session_date }}</title>
  <style>
    body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 900px; margin: 1em auto; padding: 0 1em; color: #222; }
    .strip { display: flex; gap: 1em; margin-bottom: 1.5em; }
    .tile { flex: 1; padding: 0.75em; border: 1px solid #ddd; border-radius: 6px; }
    .tile h3 { margin: 0 0 0.25em; font-size: 0.85em; color: #666; text-transform: uppercase; }
    .status-Bullish { background: #e6f4ea; }
    .status-Caution { background: #fff3cd; }
    .status-Bearish { background: #f8d7da; }
    .status-STALE { background: #e9ecef; }
    .panel { border: 1px solid #ddd; border-radius: 6px; padding: 1em; margin-bottom: 1em; }
    .panel.amber { background: #fff8e1; border-color: #ffd54f; }
    table { width: 100%; border-collapse: collapse; font-size: 0.92em; }
    th, td { text-align: left; padding: 0.4em 0.6em; border-bottom: 1px solid #eee; }
    .near { background: #fff8c4; }
    .pass { color: #28a745; }
    .fail { color: #dc3545; }
    .na { color: #6c757d; }
    .chart { max-width: 100%; margin: 0.5em 0; }
    .meta { font-size: 0.85em; color: #666; }
  </style>
</head>
<body>
  <h1>Swing Briefing — {{ vm.action_session_date }}</h1>
  <p class="meta">Data as of {{ vm.data_asof_date }} · Generated {{ vm.generated_at }}</p>

  <div class="strip">
    <div class="tile status-{{ vm.status_strip.weather.status }}">
      <h3>Market Weather</h3>
      <strong>{{ vm.status_strip.weather.status }}</strong><br>
      <small>{{ vm.status_strip.weather.rationale }}</small><br>
      <em>{{ vm.status_strip.weather.sizing_implication }}</em>
    </div>
    <div class="tile">
      <h3>Account</h3>
      Equity ${{ "%.2f"|format(vm.status_strip.account.equity) }}<br>
      Positions {{ vm.status_strip.account.open_count }} / {{ vm.status_strip.account.soft_warn }} (warn) / {{ vm.status_strip.account.hard_cap }} (cap)
    </div>
    <div class="tile">
      <h3>Last Pipeline</h3>
      {{ vm.status_strip.pipeline.last_run_ts }}{% if vm.status_strip.pipeline.is_stale %} <strong style="color:#dc3545">STALE</strong>{% endif %}
    </div>
  </div>

  <div class="panel amber">
    <h2>Today's Decisions</h2>
    {% if not vm.todays_decisions %}
      <em>No decisions today — watchlist below.</em>
    {% else %}
      {% for d in vm.todays_decisions %}
        <div style="margin-bottom: 1em;">
          <strong>{{ d.ticker }}</strong> — {{ d.action_text }}<br>
          <small>Risk ${{ "%.0f"|format(d.risk_dollars) }} ({{ "%.2f"|format(d.risk_pct) }}%) · TT {{ d.tt_score }} · VCP {{ d.vcp_score }}</small><br>
          <em>{{ d.rationale }}</em>
          {% if d.chart_b64 %}<img class="chart" src="{{ d.chart_b64 }}" alt="{{ d.ticker }} chart">
          {% elif d.chart_href %}<a class="chart-link" href="{{ d.chart_href }}">{{ d.ticker }} chart (linked)</a>
          {% endif %}
        </div>
      {% endfor %}
    {% endif %}
  </div>

  {% if vm.open_positions %}
  <div class="panel">
    <h2>Open Positions</h2>
    <table>
      <tr><th>Ticker</th><th>Shares</th><th>Entry</th><th>Stop</th><th>Last</th><th>Unrl P&L</th><th>R</th><th>Days</th></tr>
      {% for p in vm.open_positions %}
      <tr>
        <td>{{ p.ticker }}</td><td>{{ p.shares }}</td>
        <td>${{ "%.2f"|format(p.entry_price) }}</td>
        <td>${{ "%.2f"|format(p.current_stop) }}</td>
        <td>${{ "%.2f"|format(p.last_close) }}</td>
        <td>${{ "%.2f"|format(p.unrealized_pnl) }}</td>
        <td>{{ "%.2f"|format(p.r_so_far) }}R</td>
        <td>{{ p.days_open }}</td>
      </tr>
      {% if p.advisory %}
      <tr><td colspan="8" style="background:#f8f9fa;"><small>
        {% for s in p.advisory %}<strong>{{ s.rule }}:</strong> {{ s.message }}<br>{% endfor %}
      </small></td></tr>
      {% endif %}
      {% endfor %}
    </table>
  </div>
  {% endif %}

  {% if vm.watchlist %}
  <div class="panel">
    <h2>Watchlist</h2>
    <table>
      <tr><th></th><th>Ticker</th><th>Last</th><th>Pivot</th><th>%→</th><th>ADR</th><th>Stop</th><th>Status</th></tr>
      {% for w in vm.watchlist %}
      <tr class="{% if w.is_near_trigger %}near{% endif %}">
        <td>{% if w.is_near_trigger %}⚡{% endif %}</td>
        <td>{{ w.ticker }}</td>
        <td>${{ "%.2f"|format(w.current_close) }}</td>
        <td>${{ "%.2f"|format(w.entry_target) }}</td>
        <td>{{ "%+.2f"|format(w.pct_to_pivot) }}%</td>
        <td>{% if w.adr_pct %}{{ "%.1f"|format(w.adr_pct) }}%{% endif %}</td>
        <td>${{ "%.2f"|format(w.current_stop) }}</td>
        <td>{{ w.status }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  {% endif %}

  {% if vm.expansions %}
  <div class="panel">
    <h2>A+ Detail</h2>
    {% for x in vm.expansions %}
    <div style="margin-bottom: 1.5em;">
      <h3>{{ x.ticker }}</h3>
      <p>{{ x.narrative }}</p>
      <h4>Trend Template</h4>
      <table>
        {% for c in x.trend_template_grid %}
        <tr><td>{{ c.name }}</td><td class="{{ c.result }}">{{ c.result|upper }}</td><td>{{ c.value or "" }}</td><td><small>{{ c.rule or "" }}</small></td></tr>
        {% endfor %}
      </table>
      <h4>VCP</h4>
      <table>
        {% for c in x.vcp_grid %}
        <tr><td>{{ c.name }}</td><td class="{{ c.result }}">{{ c.result|upper }}</td><td>{{ c.value or "" }}</td><td><small>{{ c.rule or "" }}</small></td></tr>
        {% endfor %}
      </table>
      {% if x.chart_b64 %}<img class="chart" src="{{ x.chart_b64 }}" alt="{{ x.ticker }} chart">
      {% elif x.chart_href %}<a class="chart-link" href="{{ x.chart_href }}">{{ x.ticker }} chart (linked)</a>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  {% endif %}

</body>
</html>
```

- [ ] **Step 4: Implement `swing/rendering/html_renderer.py`**

```python
"""Render BriefingViewModel → self-contained HTML string."""
from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment, FileSystemLoader, select_autoescape

from swing.rendering.view_models import BriefingViewModel

_TEMPLATES_DIR = files("swing.rendering").joinpath("templates")
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "html.j2"]),
    trim_blocks=True, lstrip_blocks=True,
)


def render_briefing_html(vm: BriefingViewModel) -> str:
    template = _env.get_template("briefing.html.j2")
    return template.render(vm=vm)
```

- [ ] **Step 5: Verify** — `python -m pytest tests/rendering/test_html_renderer.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml swing/rendering/templates/briefing.html.j2 swing/rendering/html_renderer.py tests/rendering/test_html_renderer.py
git commit -m "feat(rendering): self-contained Jinja2 briefing.html template + renderer"
```

---

### Task D5: Briefing markdown (transition output)

**Files:**
- Create: `swing/rendering/briefing_md.py`
- Create: `tests/rendering/test_briefing_md.py`

Per spec §6.4, markdown is generated alongside HTML during transition (until 20 clean runs + user signoff). Renders the same view model.

- [ ] **Step 1: Write the failing test**

```python
# tests/rendering/test_briefing_md.py
"""Markdown briefing renderer (transition output)."""
from __future__ import annotations

from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.view_models import (
    AccountTileVM, BriefingViewModel, PipelineTileVM, StatusStripVM,
    TodaysDecisionVM, WeatherTileVM,
)


def _vm(decisions=None) -> BriefingViewModel:
    return BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="r", sizing_implication="OK"),
            account=AccountTileVM(equity=1284.50, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="2026-04-15T21:49:00",
                                    is_stale=False, current_session_match=True),
        ),
        todays_decisions=decisions or [],
        open_positions=[], watchlist=[], expansions=[],
    )


def test_empty_md():
    md = render_briefing_md(_vm())
    assert "# Swing Briefing — 2026-04-16" in md
    assert "**Status:** Bullish" in md
    assert "No decisions" in md


def test_md_with_decision():
    vm = _vm(decisions=[
        TodaysDecisionVM(
            ticker="NVDA", action_text="Buy-stop $850 · 2 sh",
            entry_target=850.0, stop_target=820.0, shares=2,
            risk_dollars=60.0, risk_pct=4.7, rationale="VCP coil",
            tt_score="7/8", vcp_score="10/10", chart_b64=None,
        ),
    ])
    md = render_briefing_md(vm)
    assert "NVDA" in md
    assert "Buy-stop $850" in md
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/rendering/briefing_md.py`**

```python
"""Markdown briefing renderer — transition output (spec §6.4)."""
from __future__ import annotations

from swing.rendering.view_models import BriefingViewModel


def render_briefing_md(vm: BriefingViewModel) -> str:
    parts: list[str] = []
    parts.append(f"# Swing Briefing — {vm.action_session_date}")
    parts.append(f"_Data as of {vm.data_asof_date} · Generated {vm.generated_at}_\n")

    parts.append("## Market Weather")
    parts.append(f"**Status:** {vm.status_strip.weather.status}")
    parts.append(f"_{vm.status_strip.weather.rationale}_")
    parts.append(f"Implication: {vm.status_strip.weather.sizing_implication}\n")

    parts.append("## Account")
    a = vm.status_strip.account
    parts.append(f"Equity ${a.equity:.2f} · Positions {a.open_count} / {a.soft_warn} warn / {a.hard_cap} cap\n")

    parts.append("## Today's Decisions")
    if not vm.todays_decisions:
        parts.append("_No decisions today — watchlist below._\n")
    else:
        for d in vm.todays_decisions:
            parts.append(f"### {d.ticker} — {d.action_text}")
            parts.append(f"Risk ${d.risk_dollars:.0f} ({d.risk_pct:.2f}%) · TT {d.tt_score} · VCP {d.vcp_score}")
            parts.append(f"_{d.rationale}_\n")

    if vm.open_positions:
        parts.append("## Open Positions")
        parts.append("| Ticker | Shares | Entry | Stop | Last | Unrl | R | Days |")
        parts.append("|---|---|---|---|---|---|---|---|")
        for p in vm.open_positions:
            parts.append(
                f"| {p.ticker} | {p.shares} | ${p.entry_price:.2f} | ${p.current_stop:.2f} | "
                f"${p.last_close:.2f} | ${p.unrealized_pnl:.2f} | {p.r_so_far:.2f}R | {p.days_open} |"
            )
        for p in vm.open_positions:
            for s in p.advisory:
                parts.append(f"- **{p.ticker} · {s.rule}:** {s.message}")
        parts.append("")

    if vm.watchlist:
        parts.append("## Watchlist")
        parts.append("| Flag | Ticker | Last | Pivot | %→ | ADR | Stop | Status |")
        parts.append("|---|---|---|---|---|---|---|---|")
        for w in vm.watchlist:
            flag = "⚡" if w.is_near_trigger else ""
            adr = f"{w.adr_pct:.1f}%" if w.adr_pct is not None else ""
            parts.append(
                f"| {flag} | {w.ticker} | ${w.current_close:.2f} | ${w.entry_target:.2f} | "
                f"{w.pct_to_pivot:+.2f}% | {adr} | ${w.current_stop:.2f} | {w.status} |"
            )
        parts.append("")

    return "\n".join(parts)
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/rendering/briefing_md.py tests/rendering/test_briefing_md.py
git commit -m "feat(rendering): briefing markdown renderer (transition output)"
```

---

### Task D6: Exporter — write briefing artifacts

**Files:**
- Create: `swing/rendering/exporter.py`
- Create: `tests/rendering/test_exporter.py`

Wraps HTML/MD renderers + chart copying + size-cap enforcement (delink charts if HTML > cap). Caller (pipeline) supplies the destination directory and chart paths.

- [ ] **Step 1: Write the failing test**

```python
# tests/rendering/test_exporter.py
"""Exporter writes briefing.html (+ briefing.md transition) + per-ticker chart copies."""
from __future__ import annotations

from pathlib import Path

from swing.rendering.exporter import export_briefing, ExportResult
from swing.rendering.view_models import (
    AccountTileVM, BriefingViewModel, PipelineTileVM, StatusStripVM,
    TodaysDecisionVM, WeatherTileVM,
)


def _vm(*, with_inline_chart: bool = False) -> BriefingViewModel:
    chart = "data:image/png;base64,iVBORw0KGgo=" if with_inline_chart else None
    return BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="r", sizing_implication="OK"),
            account=AccountTileVM(equity=1284.50, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="2026-04-15T21:49:00",
                                    is_stale=False, current_session_match=True),
        ),
        todays_decisions=[
            TodaysDecisionVM(ticker="NVDA", action_text="Buy-stop $850 · 2 sh",
                             entry_target=850.0, stop_target=820.0, shares=2,
                             risk_dollars=60.0, risk_pct=4.7, rationale="r",
                             tt_score="7/8", vcp_score="10/10", chart_b64=chart),
        ],
        open_positions=[], watchlist=[], expansions=[],
    )


def test_writes_html_and_md(tmp_path: Path):
    out = tmp_path / "exports" / "2026-04-16"
    result = export_briefing(
        vm=_vm(), out_dir=out,
        chart_files={"NVDA": tmp_path / "missing.png"},  # nonexistent — exporter handles
        size_cap_kb=500, retain_markdown_sibling=True,
    )
    assert (out / "briefing.html").exists()
    assert (out / "briefing.md").exists()
    assert result.html_size_kb < 500


def test_size_cap_delinks_charts(tmp_path: Path, monkeypatch):
    """If HTML exceeds cap (because of huge inlined charts), exporter rebuilds without inline."""
    big_b64 = "data:image/png;base64," + ("A" * 800_000)  # ~800 KB
    out = tmp_path / "exports" / "2026-04-16"
    vm = BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="t",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="r", sizing_implication="OK"),
            account=AccountTileVM(equity=1.0, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="t", is_stale=False, current_session_match=True),
        ),
        todays_decisions=[TodaysDecisionVM(
            ticker="X", action_text="t", entry_target=1.0, stop_target=1.0,
            shares=1, risk_dollars=1.0, risk_pct=1.0, rationale="r",
            tt_score="", vcp_score="", chart_b64=big_b64)],
        open_positions=[], watchlist=[], expansions=[],
    )
    result = export_briefing(
        vm=vm, out_dir=out, chart_files={},
        size_cap_kb=500, retain_markdown_sibling=False,
    )
    html = (out / "briefing.html").read_text(encoding="utf-8")
    assert big_b64 not in html  # delinked
    assert result.charts_delinked is True
    # Spec §6.4: charts referenced as file links when over cap
    assert 'href="charts/X.png"' in html or "charts/X.png" in html
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/rendering/exporter.py`**

```python
"""Briefing exporter — writes HTML (+ optional MD) + chart files; enforces size cap."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.html_renderer import render_briefing_html
from swing.rendering.view_models import BriefingViewModel, TodaysDecisionVM, TickerExpansionVM


@dataclass(frozen=True)
class ExportResult:
    html_path: Path
    md_path: Path | None
    chart_paths: list[Path]
    html_size_kb: float
    charts_delinked: bool


def _delink_charts(vm: BriefingViewModel) -> BriefingViewModel:
    """Replace inline chart_b64 with file-path href (spec §6.4).
    Assumes each ticker has a sibling `charts/<ticker>.png` that the exporter
    also copies into the out_dir — so the link resolves when the briefing.html
    is opened from its export folder."""
    new_decisions = [
        replace(d, chart_b64=None,
                chart_href=f"charts/{d.ticker}.png" if d.chart_b64 else d.chart_href)
        for d in vm.todays_decisions
    ]
    new_expansions = [
        replace(x, chart_b64=None,
                chart_href=f"charts/{x.ticker}.png" if x.chart_b64 else x.chart_href)
        for x in vm.expansions
    ]
    return replace(vm, todays_decisions=new_decisions, expansions=new_expansions)


def export_briefing(
    *, vm: BriefingViewModel, out_dir: Path,
    chart_files: Mapping[str, Path],  # ticker → source PNG path
    size_cap_kb: int = 500,
    retain_markdown_sibling: bool = True,
) -> ExportResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    html = render_briefing_html(vm)
    delinked = False
    if len(html.encode("utf-8")) / 1024 > size_cap_kb:
        # Re-render with file-link fallback (spec §6.4: charts referenced as file
        # links under charts/<ticker>.png, not silently removed).
        html = render_briefing_html(_delink_charts(vm))
        delinked = True

    html_path = out_dir / "briefing.html"
    html_path.write_text(html, encoding="utf-8")

    md_path: Path | None = None
    if retain_markdown_sibling:
        md_path = out_dir / "briefing.md"
        md_path.write_text(render_briefing_md(vm), encoding="utf-8")

    # Always copy chart PNG files (used as fallback when delinked, or just for archival)
    chart_dest_dir = out_dir / "charts"
    chart_dest_dir.mkdir(exist_ok=True)
    written: list[Path] = []
    for ticker, src in chart_files.items():
        if src.exists():
            dst = chart_dest_dir / f"{ticker}.png"
            shutil.copy2(src, dst)
            written.append(dst)

    return ExportResult(
        html_path=html_path, md_path=md_path,
        chart_paths=written,
        html_size_kb=html_path.stat().st_size / 1024,
        charts_delinked=delinked,
    )
```

- [ ] **Step 4: Verify** — `python -m pytest tests/rendering/test_exporter.py -v` → 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/rendering/exporter.py tests/rendering/test_exporter.py
git commit -m "feat(rendering): exporter writes briefing.html + chart PNGs; size-cap delinking"
```

---

### Task D7: Export retention — compress folders older than 90 days

**Files:**
- Create: `swing/rendering/retention.py`
- Create: `tests/rendering/test_retention.py`

Spec §6.4 retention policy: rolling 90 days of `exports/<date>/` folders, older ones automatically compressed to `exports/archive/<YYYY-MM>.zip` by a pipeline post-step. Archives themselves kept 3 years (manual pruning via `/settings` notice — Phase 3). This task implements the compression helper; the runner's `_step_export` invokes it at the end.

- [ ] **Step 1: Write the failing test**

```python
# tests/rendering/test_retention.py
"""Retention: compress exports/<date>/ older than N days into exports/archive/<YYYY-MM>.zip."""
from __future__ import annotations

import os
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

from swing.rendering.retention import archive_old_exports, RetentionResult


def _make_export(root: Path, dt: date) -> Path:
    d = root / dt.isoformat()
    d.mkdir(parents=True)
    (d / "briefing.html").write_text("<html></html>", encoding="utf-8")
    (d / "briefing.md").write_text("# x", encoding="utf-8")
    # Backdate mtime to simulate age
    ts = time.mktime(dt.timetuple())
    os.utime(d, (ts, ts))
    for f in d.iterdir():
        os.utime(f, (ts, ts))
    return d


def test_recent_exports_untouched(tmp_path: Path):
    root = tmp_path / "exports"
    fresh = _make_export(root, date.today())
    result = archive_old_exports(exports_dir=root, retention_days=90, today=date.today())
    assert fresh.exists()
    assert result.archived_paths == []


def test_old_exports_compressed(tmp_path: Path):
    root = tmp_path / "exports"
    today = date.today()
    old = _make_export(root, today - timedelta(days=120))
    kept = _make_export(root, today - timedelta(days=30))
    result = archive_old_exports(exports_dir=root, retention_days=90, today=today)

    assert not old.exists()
    assert kept.exists()
    assert len(result.archived_paths) == 1

    month_str = (today - timedelta(days=120)).strftime("%Y-%m")
    archive = root / "archive" / f"{month_str}.zip"
    assert archive.exists()
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        assert any("briefing.html" in n for n in names)


def test_multiple_old_same_month_into_same_zip(tmp_path: Path):
    root = tmp_path / "exports"
    today = date.today()
    month_start = (today - timedelta(days=120)).replace(day=1)
    _make_export(root, month_start)
    _make_export(root, month_start + timedelta(days=3))
    archive_old_exports(exports_dir=root, retention_days=90, today=today)

    archive = root / "archive" / f"{month_start.strftime('%Y-%m')}.zip"
    assert archive.exists()
    with zipfile.ZipFile(archive) as z:
        dates = {name.split("/")[0] for name in z.namelist() if "/" in name}
        assert len(dates) == 2
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/rendering/retention.py`**

```python
"""Export retention — compress exports/<date>/ folders older than N days."""
from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class RetentionResult:
    archived_paths: list[Path] = field(default_factory=list)
    zip_paths: list[Path] = field(default_factory=list)


def archive_old_exports(
    *, exports_dir: Path, retention_days: int = 90,
    today: date | None = None,
) -> RetentionResult:
    """Walk exports_dir for date-named folders older than retention_days;
    compress each into exports/archive/<YYYY-MM>.zip, then delete the folder.
    Skips `archive/` itself and any non-date-named dirs."""
    today = today or date.today()
    if not exports_dir.exists():
        return RetentionResult()

    result = RetentionResult([], [])
    archive_root = exports_dir / "archive"
    archive_root.mkdir(exist_ok=True)

    # Group folders by calendar month
    by_month: dict[str, list[tuple[date, Path]]] = {}
    for d in exports_dir.iterdir():
        if not d.is_dir() or d.name == "archive" or d.name.startswith("."):
            continue
        try:
            dt = date.fromisoformat(d.name)
        except ValueError:
            continue
        if (today - dt).days <= retention_days:
            continue
        month_key = dt.strftime("%Y-%m")
        by_month.setdefault(month_key, []).append((dt, d))

    for month_key, entries in by_month.items():
        zip_path = archive_root / f"{month_key}.zip"
        mode = "a" if zip_path.exists() else "w"
        with zipfile.ZipFile(zip_path, mode, zipfile.ZIP_DEFLATED) as z:
            for dt, d in entries:
                for f in d.rglob("*"):
                    if f.is_file():
                        arcname = f"{dt.isoformat()}/{f.relative_to(d).as_posix()}"
                        # If appending, skip if arcname already exists
                        if mode == "a" and arcname in z.namelist():
                            continue
                        z.write(f, arcname=arcname)
                shutil.rmtree(d)
                result.archived_paths.append(d)
        result.zip_paths.append(zip_path)
    return result
```

- [ ] **Step 4: Wire into pipeline runner `_step_export`**

At the end of `_step_export` in `swing/pipeline/runner.py`, after the `promote_staging(...)` call, add:

```python
    # Retention: compress exports older than N days
    from swing.rendering.retention import archive_old_exports
    archive_old_exports(
        exports_dir=cfg.paths.exports_dir,
        retention_days=cfg.export.retention_days,
    )
```

- [ ] **Step 5: Verify** — `python -m pytest tests/rendering/test_retention.py -v` → 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/rendering/retention.py tests/rendering/test_retention.py
# Also commit the runner wiring if separate file
git commit -m "feat(rendering): 90-day export retention with monthly ZIP archive (spec §6.4)"
```

---

## Sub-Phase E — Trade Lifecycle + Advisory

Pure-function math (`equity.py`) + repo-driven mutation services (`entry.py`, `exit.py`, `stop_adjust.py`) + 7 stop-advisory rules (`advisory.py`) + CLI subcommands. The repo's atomic `*_with_event` enforcement (sub-phase A5) is inherited.

### Task E1: Equity / R-multiple math

**Files:**
- Create: `swing/trades/__init__.py` (empty)
- Create: `swing/trades/equity.py`
- Create: `tests/trades/__init__.py` (empty)
- Create: `tests/trades/test_equity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/trades/test_equity.py
"""Equity / R / shares-remaining pure functions (legacy parity)."""
from __future__ import annotations

import pytest

from swing.data.models import CashMovement, Exit, Trade
from swing.trades.equity import (
    current_equity, sizing_equity, shares_remaining,
    risk_per_share, r_so_far, net_cash_movements,
)


def _trade(initial_shares: int = 10) -> Trade:
    return Trade(
        id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
        initial_shares=initial_shares, initial_stop=170.0, current_stop=170.0,
        status="open", watchlist_entry_target=181.0,
        watchlist_initial_stop=170.0, notes=None,
    )


def test_current_equity_starting_only():
    assert current_equity(starting_equity=1000.0, exits=[], cash_movements=[]) == 1000.0


def test_current_equity_includes_realized():
    exits = [Exit(id=1, trade_id=1, exit_date="2026-04-20", exit_price=190.0,
                  shares=5, reason="partial", realized_pnl=50.0, r_multiple=0.5, notes=None)]
    assert current_equity(starting_equity=1000.0, exits=exits, cash_movements=[]) == 1050.0


def test_current_equity_includes_cash_movements():
    cm = [
        CashMovement(id=1, date="2026-04-01", kind="deposit", amount=200.0, ref=None, note=None),
        CashMovement(id=2, date="2026-04-15", kind="withdraw", amount=50.0, ref=None, note=None),
    ]
    assert current_equity(starting_equity=1000.0, exits=[], cash_movements=cm) == 1150.0


def test_current_equity_excludes_unrealized():
    """Open trades don't count toward equity. Only realized exits + cash."""
    # No exits → no contribution
    assert current_equity(starting_equity=1000.0, exits=[], cash_movements=[]) == 1000.0


def test_sizing_equity_uses_floor_when_below():
    # Real $1200 < floor $7500 → use floor
    assert sizing_equity(real_equity=1200.0, floor=7500.0) == 7500.0


def test_sizing_equity_uses_real_when_above():
    assert sizing_equity(real_equity=10_000.0, floor=7500.0) == 10_000.0


def test_sizing_equity_no_floor():
    assert sizing_equity(real_equity=1200.0, floor=0.0) == 1200.0


def test_shares_remaining():
    exits = [Exit(id=1, trade_id=1, exit_date="2026-04-18", exit_price=185.0,
                  shares=3, reason="trim", realized_pnl=15.0, r_multiple=0.3, notes=None)]
    t = _trade(initial_shares=10)
    assert shares_remaining(t, exits) == 7


def test_risk_per_share():
    t = _trade()
    assert risk_per_share(t) == 10.0


def test_risk_per_share_zero_when_stop_above_entry():
    t = Trade(id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
              initial_shares=10, initial_stop=200.0, current_stop=200.0,
              status="open", watchlist_entry_target=None,
              watchlist_initial_stop=None, notes=None)
    assert risk_per_share(t) == 0.0


def test_r_so_far_at_entry():
    assert r_so_far(_trade(), current_price=180.0) == 0.0


def test_r_so_far_at_2r():
    # Entry 180, stop 170 → rps 10. At 200 → +20 → +2R
    assert r_so_far(_trade(), current_price=200.0) == 2.0


def test_r_so_far_zero_rps_returns_zero():
    t = Trade(id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
              initial_shares=10, initial_stop=180.0, current_stop=180.0,
              status="open", watchlist_entry_target=None,
              watchlist_initial_stop=None, notes=None)
    assert r_so_far(t, current_price=200.0) == 0.0


def test_net_cash_movements_unknown_kind_ignored():
    cm = [
        CashMovement(id=1, date="2026-04-01", kind="deposit", amount=100.0, ref=None, note=None),
        CashMovement(id=2, date="2026-04-02", kind="weird", amount=50.0, ref=None, note=None),
    ]
    # weird is not a CHECK violation here because we're testing the pure func; in the DB layer
    # the CHECK constraint prevents insertion. Pure function should ignore unknown kinds.
    assert net_cash_movements(cm) == 100.0
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/trades/equity.py`**

```python
"""Pure functions: equity, R-multiple, position sizing helpers (legacy parity)."""
from __future__ import annotations

from typing import Iterable

from swing.data.models import CashMovement, Exit, Trade


def net_cash_movements(cash_movements: Iterable[CashMovement]) -> float:
    total = 0.0
    for c in cash_movements:
        if c.kind == "deposit":
            total += c.amount
        elif c.kind == "withdraw":
            total -= c.amount
        # unknown kinds ignored (legacy parity)
    return total


def current_equity(
    *, starting_equity: float, exits: Iterable[Exit],
    cash_movements: Iterable[CashMovement],
) -> float:
    """starting + realized P&L + net cash. Excludes unrealized P&L."""
    realized = sum(e.realized_pnl for e in exits)
    return starting_equity + realized + net_cash_movements(cash_movements)


def sizing_equity(*, real_equity: float, floor: float) -> float:
    """Sizing uses max(real, floor) so a $1.2k account sizes against
    a wider risk aperture; broker cash still caps actual fills."""
    if floor > 0 and real_equity < floor:
        return floor
    return real_equity


def shares_remaining(trade: Trade, exits: Iterable[Exit]) -> int:
    sold = sum(e.shares for e in exits if e.trade_id == trade.id)
    return trade.initial_shares - sold


def risk_per_share(trade: Trade) -> float:
    rps = trade.entry_price - trade.initial_stop
    return rps if rps > 0 else 0.0


def r_so_far(trade: Trade, current_price: float) -> float:
    rps = risk_per_share(trade)
    if rps <= 0:
        return 0.0
    return (current_price - trade.entry_price) / rps
```

- [ ] **Step 4: Verify** — `python -m pytest tests/trades/test_equity.py -v` → 14 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/__init__.py swing/trades/equity.py tests/trades/__init__.py tests/trades/test_equity.py
git commit -m "feat(trades): pure equity / R-multiple / sizing math (legacy parity)"
```

---

### Task E2: Trade entry service (with cap enforcement + watchlist auto-archive)

**Files:**
- Create: `swing/trades/entry.py`
- Create: `tests/trades/test_entry.py`

The service wraps the repo's `insert_trade_with_event` with business rules: position-count gate (soft warn / hard cap), one-position-per-ticker check, optional watchlist auto-archive with reason `'entered'`. Returns a result dataclass so the CLI can decide messaging.

- [ ] **Step 1: Write the failing test**

```python
# tests/trades/test_entry.py
"""Trade entry service: caps + per-ticker check + watchlist archival."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Trade, WatchlistEntry
from swing.data.repos.trades import get_trade, list_open_trades
from swing.data.repos.watchlist import get_watchlist_entry, upsert_watchlist_entry
from swing.trades.entry import (
    EntryRequest, EntryResult, record_entry,
    SoftWarnException, HardCapException, DuplicateOpenPositionException,
)


def _req(ticker: str = "AAPL") -> EntryRequest:
    return EntryRequest(
        ticker=ticker, entry_date="2026-04-15", entry_price=180.0,
        shares=5, initial_stop=170.0, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        rationale="VCP entry", event_ts="2026-04-15T09:30:00",
    )


def test_basic_entry(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        result = record_entry(conn, _req(), soft_warn=4, hard_cap=6, force=False)
        assert isinstance(result, EntryResult)
        assert result.trade_id > 0
        assert result.warning is None
        t = get_trade(conn, result.trade_id)
        assert t.ticker == "AAPL"
    finally:
        conn.close()


def test_soft_warn_returns_warning_but_succeeds(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        # Open 4 positions to hit soft_warn=4
        for i, t in enumerate(["AAPL", "MSFT", "NVDA", "META"]):
            record_entry(conn, _req(t), soft_warn=10, hard_cap=10, force=False)
        # 5th should warn
        result = record_entry(conn, _req("GOOG"), soft_warn=4, hard_cap=10, force=True)
        assert result.warning is not None
        assert "soft warn" in result.warning.lower()
    finally:
        conn.close()


def test_soft_warn_blocks_unless_forced(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        for t in ["AAPL", "MSFT", "NVDA", "META"]:
            record_entry(conn, _req(t), soft_warn=10, hard_cap=10, force=False)
        with pytest.raises(SoftWarnException):
            record_entry(conn, _req("GOOG"), soft_warn=4, hard_cap=10, force=False)
    finally:
        conn.close()


def test_hard_cap_blocks_even_with_force(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        for t in ["AAPL", "MSFT", "NVDA", "META", "GOOG", "TSLA"]:
            record_entry(conn, _req(t), soft_warn=10, hard_cap=10, force=False)
        with pytest.raises(HardCapException):
            record_entry(conn, _req("AMZN"), soft_warn=2, hard_cap=6, force=True)
    finally:
        conn.close()


def test_duplicate_open_position_blocked(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        record_entry(conn, _req("AAPL"), soft_warn=4, hard_cap=6, force=False)
        with pytest.raises(DuplicateOpenPositionException):
            record_entry(conn, _req("AAPL"), soft_warn=4, hard_cap=6, force=False)
    finally:
        conn.close()


def test_invalid_stop_above_entry_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        bad = EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=185.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None,
            rationale="bad stop", event_ts="2026-04-15T09:30:00",
        )
        with pytest.raises(ValueError, match="stop must be < entry"):
            record_entry(conn, bad, soft_warn=4, hard_cap=6, force=False)
    finally:
        conn.close()


def test_watchlist_entry_auto_archived(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-14",
                status="watch", qualification_count=3, not_qualified_streak=0,
                last_data_asof_date="2026-04-14",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=178.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
        result = record_entry(conn, _req("AAPL"), soft_warn=4, hard_cap=6, force=False)
        assert result.watchlist_archived is True
        assert get_watchlist_entry(conn, "AAPL") is None
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/trades/entry.py`**

```python
"""Trade entry service — wraps repo with cap enforcement + watchlist archival."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from swing.data.models import Trade, WatchlistArchiveEntry
from swing.data.repos.trades import insert_trade_with_event, list_open_trades
from swing.data.repos.watchlist import (
    archive_watchlist_entry, get_watchlist_entry,
)


class SoftWarnException(Exception):
    """Open count >= soft_warn_open without force=True."""


class HardCapException(Exception):
    """Open count >= hard_cap_open — never bypassable."""


class DuplicateOpenPositionException(Exception):
    """Already an open trade for this ticker."""


@dataclass(frozen=True)
class EntryRequest:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    initial_stop: float
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    rationale: str
    event_ts: str


@dataclass(frozen=True)
class EntryResult:
    trade_id: int
    warning: str | None
    watchlist_archived: bool


def record_entry(
    conn: sqlite3.Connection, req: EntryRequest, *,
    soft_warn: int, hard_cap: int, force: bool,
) -> EntryResult:
    if req.initial_stop >= req.entry_price:
        raise ValueError(
            f"stop must be < entry; got entry={req.entry_price}, stop={req.initial_stop}"
        )

    open_trades = list_open_trades(conn)
    if any(t.ticker == req.ticker for t in open_trades):
        raise DuplicateOpenPositionException(
            f"Already an open position in {req.ticker}"
        )

    open_count = len(open_trades)
    if open_count >= hard_cap:
        raise HardCapException(
            f"Hard cap reached: {open_count} >= {hard_cap}"
        )
    warning: str | None = None
    if open_count >= soft_warn:
        if not force:
            raise SoftWarnException(
                f"Open count {open_count} >= soft warn {soft_warn}; use --force"
            )
        warning = f"Soft warn exceeded: {open_count} open positions (soft={soft_warn})"

    trade = Trade(
        id=None, ticker=req.ticker, entry_date=req.entry_date,
        entry_price=req.entry_price, initial_shares=req.shares,
        initial_stop=req.initial_stop, current_stop=req.initial_stop,
        status="open",
        watchlist_entry_target=req.watchlist_entry_target,
        watchlist_initial_stop=req.watchlist_initial_stop,
        notes=req.notes,
    )

    archived = False
    with conn:
        trade_id = insert_trade_with_event(
            conn, trade, event_ts=req.event_ts, rationale=req.rationale,
        )
        wl = get_watchlist_entry(conn, req.ticker)
        if wl is not None:
            archive_watchlist_entry(conn, WatchlistArchiveEntry(
                id=None, ticker=req.ticker, added_date=wl.added_date,
                removed_date=req.entry_date, reason="entered",
                qualification_count=wl.qualification_count,
                last_data_asof_date=wl.last_data_asof_date,
                notes=wl.notes,
            ))
            archived = True

    return EntryResult(trade_id=trade_id, warning=warning, watchlist_archived=archived)
```

- [ ] **Step 4: Verify** — `python -m pytest tests/trades/test_entry.py -v` → 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/entry.py tests/trades/test_entry.py
git commit -m "feat(trades): record_entry with cap enforcement + watchlist auto-archive"
```

---

### Task E3: Trade exit service

**Files:**
- Create: `swing/trades/exit.py`
- Create: `tests/trades/test_exit.py`

Computes `realized_pnl` and `r_multiple` (using INITIAL stop, not current — legacy parity), delegates to repo's `insert_exit_with_event` for the actual write + status flip.

- [ ] **Step 1: Write the failing test**

```python
# tests/trades/test_exit.py
"""Trade exit service — computes pnl + R then writes via repo."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.trades import (
    get_trade, list_exits_for_trade, list_events_for_trade,
)
from swing.trades.entry import EntryRequest, record_entry
from swing.trades.exit import ExitRequest, record_exit, ExitReason


def _seed(conn, ticker: str = "AAPL") -> int:
    req = EntryRequest(
        ticker=ticker, entry_date="2026-04-15", entry_price=180.0,
        shares=10, initial_stop=170.0, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None, rationale="entry",
        event_ts="2026-04-15T09:30:00",
    )
    return record_entry(conn, req, soft_warn=10, hard_cap=10, force=False).trade_id


def test_full_exit_flips_status_and_computes_r(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        result = record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-22", exit_price=200.0,
            shares=10, reason=ExitReason.TARGET, notes=None,
            rationale="target hit", event_ts="2026-04-22T15:30:00",
        ))
        assert result.realized_pnl == pytest.approx(200.0)  # 10 * (200-180)
        assert result.r_multiple == pytest.approx(2.0)      # (200-180) / (180-170)
        assert result.fully_closed is True
        assert get_trade(conn, tid).status == "closed"
    finally:
        conn.close()


def test_partial_exit_keeps_open(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        result = record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-18", exit_price=185.0,
            shares=5, reason=ExitReason.MANUAL, notes=None,
            rationale="trim", event_ts="2026-04-18T15:00:00",
        ))
        assert result.fully_closed is False
        assert get_trade(conn, tid).status == "open"
        assert result.r_multiple == pytest.approx(0.5)  # (185-180)/10
        assert result.realized_pnl == pytest.approx(25.0)
    finally:
        conn.close()


def test_exit_loss(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        result = record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-18", exit_price=170.0,
            shares=10, reason=ExitReason.STOP_HIT, notes=None,
            rationale="stopped", event_ts="2026-04-18T15:00:00",
        ))
        assert result.realized_pnl == pytest.approx(-100.0)
        assert result.r_multiple == pytest.approx(-1.0)
    finally:
        conn.close()


def test_overfill_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        with pytest.raises(ValueError, match="exceeds remaining"):
            record_exit(conn, ExitRequest(
                trade_id=tid, exit_date="2026-04-18", exit_price=185.0,
                shares=11, reason=ExitReason.MANUAL, notes=None,
                rationale="overfill", event_ts="2026-04-18T15:00:00",
            ))
    finally:
        conn.close()


def test_invalid_reason_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        with pytest.raises(ValueError):
            record_exit(conn, ExitRequest(
                trade_id=tid, exit_date="2026-04-18", exit_price=185.0,
                shares=5, reason="invalid_reason",  # type: ignore[arg-type]
                notes=None, rationale="x", event_ts="2026-04-18T15:00:00",
            ))
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/trades/exit.py`**

```python
"""Trade exit service — computes pnl + R, delegates to repo for atomic write."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum

from swing.data.models import Exit
from swing.data.repos.trades import (
    get_trade, insert_exit_with_event, list_exits_for_trade,
)


class ExitReason(str, Enum):
    STOP_HIT = "stop-hit"
    TARGET = "target"
    MANUAL = "manual"
    TIME_STOP = "time-stop"
    WEATHER = "weather"
    PARTIAL = "partial"
    OTHER = "other"


@dataclass(frozen=True)
class ExitRequest:
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: ExitReason
    notes: str | None
    rationale: str
    event_ts: str


@dataclass(frozen=True)
class ExitResult:
    exit_id: int
    realized_pnl: float
    r_multiple: float
    fully_closed: bool


def record_exit(conn: sqlite3.Connection, req: ExitRequest) -> ExitResult:
    if not isinstance(req.reason, ExitReason):
        raise ValueError(f"invalid exit reason: {req.reason}")
    if req.shares <= 0:
        raise ValueError(f"shares must be > 0; got {req.shares}")

    trade = get_trade(conn, req.trade_id)
    if trade is None:
        raise ValueError(f"trade {req.trade_id} not found")

    pnl_per_share = req.exit_price - trade.entry_price
    realized_pnl = pnl_per_share * req.shares
    rps = trade.entry_price - trade.initial_stop
    r_multiple = pnl_per_share / rps if rps > 0 else 0.0

    exit_row = Exit(
        id=None, trade_id=req.trade_id, exit_date=req.exit_date,
        exit_price=req.exit_price, shares=req.shares,
        reason=req.reason.value, realized_pnl=realized_pnl,
        r_multiple=r_multiple, notes=req.notes,
    )

    sold_before = sum(e.shares for e in list_exits_for_trade(conn, req.trade_id))
    fully_closed = (sold_before + req.shares) == trade.initial_shares

    with conn:
        exit_id = insert_exit_with_event(
            conn, exit_row, event_ts=req.event_ts, rationale=req.rationale,
        )

    return ExitResult(
        exit_id=exit_id, realized_pnl=realized_pnl,
        r_multiple=r_multiple, fully_closed=fully_closed,
    )
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/exit.py tests/trades/test_exit.py
git commit -m "feat(trades): record_exit computes pnl + R; atomic via repo"
```

---

### Task E4: Stop adjust service

**Files:**
- Create: `swing/trades/stop_adjust.py`
- Create: `tests/trades/test_stop_adjust.py`

Thin service over `update_stop_with_event` — adds optional invariant check (new stop should be > current stop for trail-up; raises if violated unless `force=True`).

- [ ] **Step 1: Write the failing test**

```python
# tests/trades/test_stop_adjust.py
"""Stop adjust service: trail-up invariant + audit event."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.trades import get_trade, list_events_for_trade
from swing.trades.entry import EntryRequest, record_entry
from swing.trades.stop_adjust import StopAdjustRequest, adjust_stop, StopRegressionError


def _seed(conn) -> int:
    req = EntryRequest(
        ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
        shares=10, initial_stop=170.0, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        rationale="entry", event_ts="2026-04-15T09:30:00",
    )
    return record_entry(conn, req, soft_warn=10, hard_cap=10, force=False).trade_id


def test_trail_up_writes_event(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=175.0, rationale="breakeven+",
            event_ts="2026-04-17T15:00:00", force=False,
        ))
        assert get_trade(conn, tid).current_stop == 175.0
        events = list_events_for_trade(conn, tid)
        assert any(e.event_type == "stop_adjust" for e in events)
    finally:
        conn.close()


def test_trail_down_blocked_without_force(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        with pytest.raises(StopRegressionError):
            adjust_stop(conn, StopAdjustRequest(
                trade_id=tid, new_stop=165.0, rationale="loosen",
                event_ts="2026-04-17T15:00:00", force=False,
            ))
    finally:
        conn.close()


def test_trail_down_allowed_with_force(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=165.0, rationale="config change override",
            event_ts="2026-04-17T15:00:00", force=True,
        ))
        assert get_trade(conn, tid).current_stop == 165.0
    finally:
        conn.close()


def test_no_op_same_stop(tmp_path: Path):
    """Setting stop to current value is a no-op (no audit row)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=170.0, rationale="no-op",
            event_ts="2026-04-17T15:00:00", force=False,
        ))
        events = list_events_for_trade(conn, tid)
        assert sum(1 for e in events if e.event_type == "stop_adjust") == 0
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/trades/stop_adjust.py`**

```python
"""Stop adjust service — enforces trail-up invariant unless force=True."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from swing.data.repos.trades import get_trade, update_stop_with_event


class StopRegressionError(Exception):
    """Attempted to lower the stop without force=True."""


@dataclass(frozen=True)
class StopAdjustRequest:
    trade_id: int
    new_stop: float
    rationale: str
    event_ts: str
    force: bool = False


def adjust_stop(conn: sqlite3.Connection, req: StopAdjustRequest) -> None:
    trade = get_trade(conn, req.trade_id)
    if trade is None:
        raise ValueError(f"trade {req.trade_id} not found")
    if req.new_stop < trade.current_stop and not req.force:
        raise StopRegressionError(
            f"new stop ${req.new_stop:.2f} < current ${trade.current_stop:.2f}; use force=True"
        )
    if req.new_stop == trade.current_stop:
        return  # no-op (matches repo behavior)
    with conn:
        update_stop_with_event(
            conn, trade_id=req.trade_id, new_stop=req.new_stop,
            event_ts=req.event_ts, rationale=req.rationale,
        )
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/stop_adjust.py tests/trades/test_stop_adjust.py
git commit -m "feat(trades): adjust_stop with trail-up invariant + force override"
```

---

### Task E5: Stop-advisory rules (7 rules, pure)

**Files:**
- Create: `swing/trades/advisory.py`
- Create: `tests/trades/test_advisory.py`

Each of the 7 rules is a pure function `Trade + context → AdvisorySuggestion | None`. The aggregator returns the non-None list. Ports legacy `compute_all_suggestions`.

- [ ] **Step 1: Write the failing test**

```python
# tests/trades/test_advisory.py
"""Stop-advisory rules — 7 functions + aggregator."""
from __future__ import annotations

import pandas as pd

from swing.config import StopAdvisoryConfig
from swing.data.models import Trade
from swing.trades.advisory import (
    AdvisoryContext, AdvisorySuggestion, compute_all_suggestions,
    suggest_breakeven, suggest_trail_ma, suggest_exit_close_below_ma,
    suggest_weather_action, suggest_time_stop,
)


def _trade(*, current_stop: float = 170.0, entry: float = 180.0, days: int = 0) -> Trade:
    from datetime import date, timedelta
    entry_date = (date.fromisoformat("2026-04-15") - timedelta(days=days)).isoformat()
    return Trade(
        id=1, ticker="AAPL", entry_date=entry_date, entry_price=entry,
        initial_shares=10, initial_stop=170.0, current_stop=current_stop,
        status="open", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )


def _ohlcv_with_mas(close: float, ma10: float, ma20: float):
    """Synthesize OHLCV that yields target MAs at last bar."""
    bars = 25
    closes = [ma20] * 20 + [ma10] * 4 + [close]  # crude but produces approx target
    idx = pd.bdate_range(end="2026-04-15", periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def _ctx(close: float = 195.0, ma10: float = 190.0, ma20: float = 185.0,
         weather: str = "Bullish") -> AdvisoryContext:
    return AdvisoryContext(
        as_of_date="2026-04-15", current_price=close,
        sma10=ma10, sma20=ma20, weather_status=weather,
        config=StopAdvisoryConfig(),
    )


def test_breakeven_suggested_at_1r():
    # Entry 180, stop 170, rps 10. At 190 → +1R → breakeven trigger
    s = suggest_breakeven(_trade(), _ctx(close=190.0))
    assert s is not None
    assert "breakeven" in s.message.lower()
    assert "180" in s.message  # entry price


def test_breakeven_not_suggested_when_already_at_or_above_entry():
    # current_stop already at 180 → no advisory
    s = suggest_breakeven(_trade(current_stop=180.0), _ctx(close=200.0))
    assert s is None


def test_breakeven_not_suggested_below_1r():
    s = suggest_breakeven(_trade(), _ctx(close=185.0))  # +0.5R
    assert s is None


def test_trail_10ma_suggested():
    # close=195, 10MA=190, buf 0.3% → suggested stop 190 * 0.997 = 189.43, > current 170
    s = suggest_trail_ma(_trade(), _ctx(close=195.0, ma10=190.0),
                         ma_value=190.0, ma_label="10MA",
                         buffer_pct=0.3)
    assert s is not None
    assert "10MA" in s.message
    assert "189.43" in s.message or "189.4" in s.message


def test_trail_ma_no_op_when_below_ma():
    s = suggest_trail_ma(_trade(), _ctx(close=185.0, ma10=190.0),
                         ma_value=190.0, ma_label="10MA",
                         buffer_pct=0.3)
    assert s is None


def test_exit_close_below_ma():
    s = suggest_exit_close_below_ma(_trade(), _ctx(close=185.0, ma10=190.0),
                                    ma_value=190.0, ma_label="10MA")
    assert s is not None
    assert "EXIT" in s.message
    assert "10MA" in s.message


def test_weather_caution_action():
    s = suggest_weather_action(_trade(), _ctx(weather="Caution"))
    assert s is not None
    assert "caution" in s.message.lower() or "tighten" in s.message.lower()


def test_weather_bearish_action():
    s = suggest_weather_action(_trade(), _ctx(weather="Bearish"))
    assert s is not None
    assert "bearish" in s.message.lower() or "exit" in s.message.lower()


def test_weather_bullish_no_action():
    assert suggest_weather_action(_trade(), _ctx(weather="Bullish")) is None


def test_time_stop_triggers_after_n_days_with_low_r():
    # Default: 10 days, 0.5R minimum. Open 11 days at +0.3R → triggers
    t = _trade(days=11)
    s = suggest_time_stop(t, _ctx(close=183.0))  # +0.3R
    assert s is not None
    assert "time" in s.message.lower()


def test_time_stop_not_triggered_when_r_high_enough():
    t = _trade(days=11)
    # +1.5R → don't suggest time stop
    assert suggest_time_stop(t, _ctx(close=195.0)) is None


def test_compute_all_suggestions_aggregates_non_none():
    # Conditions chosen to fire: breakeven, trail_10ma
    sugs = compute_all_suggestions(_trade(), _ctx(close=190.0, ma10=185.0, ma20=180.0))
    rules = {s.rule for s in sugs}
    assert "breakeven" in rules
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/trades/advisory.py`**

```python
"""Seven stop-advisory rules (legacy parity).

Each rule is pure: (Trade, AdvisoryContext) → AdvisorySuggestion | None.
Aggregator returns the non-None list, ordered for display.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from swing.config import StopAdvisoryConfig
from swing.data.models import Trade
from swing.trades.equity import r_so_far


@dataclass(frozen=True)
class AdvisoryContext:
    as_of_date: str
    current_price: float
    sma10: float | None
    sma20: float | None
    weather_status: str  # 'Bullish' | 'Caution' | 'Bearish'
    config: StopAdvisoryConfig


@dataclass(frozen=True)
class AdvisorySuggestion:
    rule: str
    message: str


def suggest_breakeven(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    if r_so_far(trade, ctx.current_price) < ctx.config.breakeven_r_trigger:
        return None
    if trade.current_stop >= trade.entry_price:
        return None
    return AdvisorySuggestion(
        rule="breakeven",
        message=f"Move stop to breakeven (${trade.entry_price:.2f})",
    )


def suggest_trail_ma(
    trade: Trade, ctx: AdvisoryContext, *,
    ma_value: float | None, ma_label: str, buffer_pct: float,
) -> AdvisorySuggestion | None:
    if ma_value is None or ctx.current_price < ma_value:
        return None
    proposed = ma_value * (1 - buffer_pct / 100)
    if proposed <= trade.current_stop:
        return None
    return AdvisorySuggestion(
        rule=f"trail_{ma_label.lower()}",
        message=f"Trail stop up to ${proposed:.2f} — {buffer_pct}% below {ma_label} (${ma_value:.2f})",
    )


def suggest_exit_close_below_ma(
    trade: Trade, ctx: AdvisoryContext, *,
    ma_value: float | None, ma_label: str,
) -> AdvisorySuggestion | None:
    if ma_value is None or ctx.current_price >= ma_value:
        return None
    return AdvisorySuggestion(
        rule=f"exit_below_{ma_label.lower()}",
        message=f"EXIT — close ${ctx.current_price:.2f} is below {ma_label} (${ma_value:.2f})",
    )


def suggest_weather_action(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    s = (ctx.weather_status or "").lower()
    if s.startswith("bearish"):
        return AdvisorySuggestion(
            rule="weather",
            message="Bearish weather — tighten stops or exit longs",
        )
    if s.startswith("caution"):
        return AdvisorySuggestion(
            rule="weather",
            message="Caution weather — tighten stops; consider half sizing",
        )
    return None


def suggest_time_stop(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    days_open = (date.fromisoformat(ctx.as_of_date) - date.fromisoformat(trade.entry_date)).days
    if days_open <= ctx.config.time_stop_days:
        return None
    if r_so_far(trade, ctx.current_price) >= ctx.config.time_stop_min_r:
        return None
    return AdvisorySuggestion(
        rule="time_stop",
        message=f"Time stop — {days_open} days open with only "
                f"+{r_so_far(trade, ctx.current_price):.2f}R; consider exit",
    )


def compute_all_suggestions(trade: Trade, ctx: AdvisoryContext) -> list[AdvisorySuggestion]:
    sugs: list[AdvisorySuggestion | None] = []
    sugs.append(suggest_breakeven(trade, ctx))
    sugs.append(suggest_trail_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA",
                                  buffer_pct=ctx.config.trail_10ma_buffer_pct))
    sugs.append(suggest_trail_ma(trade, ctx, ma_value=ctx.sma20, ma_label="20MA",
                                  buffer_pct=ctx.config.trail_20ma_buffer_pct))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA"))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma20, ma_label="20MA"))
    sugs.append(suggest_weather_action(trade, ctx))
    sugs.append(suggest_time_stop(trade, ctx))
    return [s for s in sugs if s is not None]
```

- [ ] **Step 4: Verify** — `python -m pytest tests/trades/test_advisory.py -v` → 12 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/advisory.py tests/trades/test_advisory.py
git commit -m "feat(trades): 7 stop-advisory rules + aggregator (legacy parity)"
```

---

### Task E6: CLI subcommands — trade entry/exit/list/stop-adjust/advisory

**Files:**
- Modify: `swing/cli.py` — add `trade` group with 5 subcommands
- Create: `tests/cli/test_cli_trade.py`

CLI is a thin wrapper around the services. Interactive prompts (legacy) are replaced with explicit options for scriptability — but `--interactive` flag launches Click prompts for the morning workflow.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_cli_trade.py
"""CLI: swing trade entry / exit / list / stop-adjust / advisory."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def test_trade_entry_then_list(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "VCP",
    ])
    assert result.exit_code == 0, result.output
    assert "trade id" in result.output.lower() or "entered" in result.output.lower()

    result2 = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert result2.exit_code == 0
    assert "AAPL" in result2.output


def test_trade_exit(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "x",
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-22",
        "--exit-price", "200.0", "--shares", "5",
        "--reason", "target", "--rationale", "hit",
    ])
    assert result.exit_code == 0, result.output
    assert "R" in result.output  # mentions R-multiple


def test_trade_stop_adjust_blocked_when_lowering(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "x",
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "165.0", "--rationale", "loosen",
    ])
    assert result.exit_code != 0
    assert "regression" in result.output.lower() or "force" in result.output.lower()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Add `trade` Click group to `swing/cli.py`**

```python
@main.group("trade")
def trade_group() -> None:
    """Trade lifecycle: entry, exit, list, stop adjust, advisory."""


@trade_group.command("entry")
@click.option("--ticker", required=True)
@click.option("--entry-date", required=True, help="YYYY-MM-DD")
@click.option("--entry-price", type=float, required=True)
@click.option("--shares", type=int, required=True)
@click.option("--initial-stop", type=float, required=True)
@click.option("--watchlist-target", type=float, default=None)
@click.option("--watchlist-stop", type=float, default=None)
@click.option("--rationale", required=True)
@click.option("--notes", default=None)
@click.option("--force", is_flag=True, help="Bypass soft-warn cap (still subject to hard cap)")
@click.pass_context
def trade_entry_cmd(ctx, ticker, entry_date, entry_price, shares, initial_stop,
                    watchlist_target, watchlist_stop, rationale, notes, force):
    """Record a trade entry."""
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.trades.entry import (
        EntryRequest, record_entry,
        SoftWarnException, HardCapException, DuplicateOpenPositionException,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        req = EntryRequest(
            ticker=ticker.upper(), entry_date=entry_date, entry_price=entry_price,
            shares=shares, initial_stop=initial_stop,
            watchlist_entry_target=watchlist_target,
            watchlist_initial_stop=watchlist_stop,
            notes=notes, rationale=rationale,
            event_ts=_dt.now().isoformat(timespec="seconds"),
        )
        try:
            result = record_entry(
                conn, req,
                soft_warn=cfg.position_limits.soft_warn_open,
                hard_cap=cfg.position_limits.hard_cap_open,
                force=force,
            )
        except (SoftWarnException, HardCapException, DuplicateOpenPositionException) as exc:
            raise click.ClickException(str(exc))
    finally:
        conn.close()

    if result.warning:
        click.echo(f"WARN: {result.warning}", err=True)
    if result.watchlist_archived:
        click.echo(f"Watchlist row for {ticker} archived (reason: entered)")
    click.echo(f"Trade id {result.trade_id}: {ticker} {shares} sh @ ${entry_price:.2f}, stop ${initial_stop:.2f}")


@trade_group.command("exit")
@click.option("--trade-id", type=int, required=True)
@click.option("--exit-date", required=True)
@click.option("--exit-price", type=float, required=True)
@click.option("--shares", type=int, required=True)
@click.option("--reason", type=click.Choice(
    ["stop-hit", "target", "manual", "time-stop", "weather", "partial", "other"]
), required=True)
@click.option("--notes", default=None)
@click.option("--rationale", required=True)
@click.pass_context
def trade_exit_cmd(ctx, trade_id, exit_date, exit_price, shares, reason, notes, rationale):
    """Record a trade exit (full or partial)."""
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        req = ExitRequest(
            trade_id=trade_id, exit_date=exit_date, exit_price=exit_price,
            shares=shares, reason=ExitReason(reason),
            notes=notes, rationale=rationale,
            event_ts=_dt.now().isoformat(timespec="seconds"),
        )
        result = record_exit(conn, req)
    finally:
        conn.close()
    closed = " (FULL CLOSE)" if result.fully_closed else ""
    click.echo(f"Exit {result.exit_id}: ${result.realized_pnl:+.2f} ({result.r_multiple:+.2f}R){closed}")


@trade_group.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include closed trades")
@click.pass_context
def trade_list_cmd(ctx, show_all):
    """List open (or all) trades."""
    from swing.data.db import connect
    from swing.data.repos.trades import list_open_trades, list_closed_trades

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        trades = list_open_trades(conn)
        if show_all:
            trades = trades + list_closed_trades(conn)
    finally:
        conn.close()
    if not trades:
        click.echo("(no trades)")
        return
    click.echo(f"{'ID':>4} {'Ticker':<6} {'Date':<10} {'Entry':>8} {'Stop':>8} {'Sh':>4} {'Status':<8}")
    for t in trades:
        click.echo(
            f"{t.id or 0:>4} {t.ticker:<6} {t.entry_date:<10} "
            f"${t.entry_price:>6.2f} ${t.current_stop:>6.2f} {t.initial_shares:>4} {t.status:<8}"
        )


@trade_group.command("stop-adjust")
@click.option("--trade-id", type=int, required=True)
@click.option("--new-stop", type=float, required=True)
@click.option("--rationale", required=True)
@click.option("--force", is_flag=True, help="Allow lowering the stop")
@click.pass_context
def trade_stop_adjust_cmd(ctx, trade_id, new_stop, rationale, force):
    """Adjust the stop on an open trade. Refuses to lower without --force."""
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.trades.stop_adjust import StopAdjustRequest, adjust_stop, StopRegressionError

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        try:
            adjust_stop(conn, StopAdjustRequest(
                trade_id=trade_id, new_stop=new_stop, rationale=rationale,
                event_ts=_dt.now().isoformat(timespec="seconds"), force=force,
            ))
        except StopRegressionError as exc:
            raise click.ClickException(str(exc))
    finally:
        conn.close()
    click.echo(f"Trade {trade_id} stop -> ${new_stop:.2f}")


@trade_group.command("advisory")
@click.option("--trade-id", type=int, required=True)
@click.option("--current-price", type=float, required=True)
@click.option("--sma10", type=float, default=None)
@click.option("--sma20", type=float, default=None)
@click.option("--weather", default="Bullish")
@click.option("--as-of-date", default=None, help="default: today")
@click.pass_context
def trade_advisory_cmd(ctx, trade_id, current_price, sma10, sma20, weather, as_of_date):
    """Print stop-advisory suggestions for an open trade."""
    from datetime import date as _date
    from swing.data.db import connect
    from swing.data.repos.trades import get_trade
    from swing.trades.advisory import AdvisoryContext, compute_all_suggestions

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
        if trade is None:
            raise click.ClickException(f"trade {trade_id} not found")
    finally:
        conn.close()
    asof = as_of_date or _date.today().isoformat()
    ctx_a = AdvisoryContext(
        as_of_date=asof, current_price=current_price,
        sma10=sma10, sma20=sma20, weather_status=weather,
        config=cfg.stop_advisory,
    )
    sugs = compute_all_suggestions(trade, ctx_a)
    if not sugs:
        click.echo("(no advisories)")
        return
    for s in sugs:
        click.echo(f"  [{s.rule}] {s.message}")
```

- [ ] **Step 4: Verify** — `python -m pytest tests/cli/test_cli_trade.py -v` → 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/cli/test_cli_trade.py
git commit -m "feat(cli): add `swing trade` group (entry/exit/list/stop-adjust/advisory)"
```

---

## Sub-Phase F — Journal + TOS Reconciliation

Stats + behavioral flags (pure functions over closed trades) and TOS reconciliation (CSV parser + matching). All CLI-driven; pipeline does not invoke these (they're user-initiated).

### Task F1: Journal stats

**Files:**
- Create: `swing/journal/__init__.py` (empty)
- Create: `swing/journal/stats.py`
- Create: `tests/journal/__init__.py` (empty)
- Create: `tests/journal/test_stats.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/journal/test_stats.py
"""Journal stats — share-weighted R, win rate, expectancy, streak."""
from __future__ import annotations

import pytest

from swing.data.models import Exit, Trade
from swing.journal.stats import (
    JournalStats, compute_stats, period_filter, _trade_closed_date,
)


def _trade(tid: int, ticker: str, entry: float = 100.0, stop: float = 95.0,
           shares: int = 10, status: str = "closed") -> Trade:
    return Trade(
        id=tid, ticker=ticker, entry_date="2026-04-15", entry_price=entry,
        initial_shares=shares, initial_stop=stop, current_stop=stop,
        status=status, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )


def _exit(tid: int, *, exit_date: str, price: float, shares: int,
          rps: float, reason: str = "target") -> Exit:
    pnl = shares * (price - 100.0)
    r = (price - 100.0) / rps if rps > 0 else 0.0
    return Exit(id=None, trade_id=tid, exit_date=exit_date, exit_price=price,
                shares=shares, reason=reason, realized_pnl=pnl,
                r_multiple=r, notes=None)


def test_empty_returns_zeros():
    s = compute_stats(trades=[], exits=[], cash_movements=[])
    assert s.n_trades == 0
    assert s.win_rate == 0.0
    assert s.expectancy_r == 0.0
    assert s.current_streak == 0


def test_single_winner():
    t = _trade(1, "AAPL")
    e = _exit(1, exit_date="2026-04-20", price=110.0, shares=10, rps=5.0)  # +2R
    s = compute_stats(trades=[t], exits=[e], cash_movements=[])
    assert s.n_trades == 1
    assert s.win_rate == 1.0
    assert s.avg_win_r == 2.0
    assert s.avg_loss_r == 0.0
    assert s.total_r == 2.0
    assert s.current_streak_kind == "W"


def test_share_weighted_r_for_partials():
    """If a trade exits 5 sh at +1R and 5 sh at +3R (same trade), the trade R is 2.0."""
    t = _trade(1, "AAPL", shares=10)
    e1 = _exit(1, exit_date="2026-04-18", price=105.0, shares=5, rps=5.0)  # +1R
    e2 = _exit(1, exit_date="2026-04-22", price=115.0, shares=5, rps=5.0)  # +3R
    s = compute_stats(trades=[t], exits=[e1, e2], cash_movements=[])
    assert s.n_trades == 1
    # 5/10 * 1.0 + 5/10 * 3.0 = 2.0
    assert s.total_r == pytest.approx(2.0)


def test_loser_trade():
    t = _trade(1, "AAPL")
    e = _exit(1, exit_date="2026-04-20", price=95.0, shares=10, rps=5.0,
              reason="stop-hit")
    s = compute_stats(trades=[t], exits=[e], cash_movements=[])
    assert s.win_rate == 0.0
    assert s.avg_loss_r == -1.0
    assert s.current_streak_kind == "L"


def test_streak_walks_back():
    """Most recent two are W,W → streak 2W. Then earlier L doesn't count."""
    trades = [_trade(i, f"T{i}") for i in (1, 2, 3)]
    exits = [
        _exit(1, exit_date="2026-04-10", price=95.0, shares=10, rps=5.0),  # L
        _exit(2, exit_date="2026-04-12", price=105.0, shares=10, rps=5.0), # W
        _exit(3, exit_date="2026-04-15", price=110.0, shares=10, rps=5.0), # W
    ]
    s = compute_stats(trades=trades, exits=exits, cash_movements=[])
    assert s.current_streak == 2
    assert s.current_streak_kind == "W"


def test_period_filter_week():
    trades = [_trade(1, "OLD"), _trade(2, "NEW")]
    exits = [
        _exit(1, exit_date="2026-03-01", price=110.0, shares=10, rps=5.0),
        _exit(2, exit_date="2026-04-12", price=110.0, shares=10, rps=5.0),
    ]
    today = "2026-04-15"
    week_trades = period_filter(trades, exits, period="week", today=today)
    assert {t.ticker for t in week_trades} == {"NEW"}


def test_expectancy_r():
    trades = [_trade(i, f"T{i}") for i in (1, 2, 3, 4)]
    # 3 winners @ +2R, 1 loser @ -1R → E = 0.75*2 + 0.25*(-1) = 1.25
    exits = [
        _exit(1, exit_date="2026-04-10", price=110.0, shares=10, rps=5.0),
        _exit(2, exit_date="2026-04-11", price=110.0, shares=10, rps=5.0),
        _exit(3, exit_date="2026-04-12", price=110.0, shares=10, rps=5.0),
        _exit(4, exit_date="2026-04-13", price=95.0,  shares=10, rps=5.0),
    ]
    s = compute_stats(trades=trades, exits=exits, cash_movements=[])
    assert s.expectancy_r == pytest.approx(1.25)
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/journal/stats.py`**

```python
"""Journal stats — share-weighted R per trade + win rate + expectancy + streak."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Literal

from swing.data.models import CashMovement, Exit, Trade

Period = Literal["week", "month", "quarter", "ytd", "all"]


@dataclass(frozen=True)
class JournalStats:
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float
    largest_win_r: float
    largest_loss_r: float
    total_r: float
    total_pnl: float
    current_streak: int
    current_streak_kind: str  # 'W' | 'L' | ''


def _trade_closed_date(trade: Trade, exits: list[Exit]) -> date | None:
    if trade.status != "closed":
        return None
    relevant = [e.exit_date for e in exits if e.trade_id == trade.id]
    return max(date.fromisoformat(d) for d in relevant) if relevant else None


def _trade_r(trade: Trade, exits: list[Exit]) -> float:
    """Share-weighted R across all exits for this trade."""
    total = 0.0
    for e in exits:
        if e.trade_id != trade.id:
            continue
        total += e.r_multiple * (e.shares / trade.initial_shares)
    return total


def _trade_pnl(trade: Trade, exits: list[Exit]) -> float:
    return sum(e.realized_pnl for e in exits if e.trade_id == trade.id)


def period_filter(
    trades: Iterable[Trade], exits: Iterable[Exit], *,
    period: Period, today: str,
) -> list[Trade]:
    if period == "all":
        return list(trades)
    today_d = date.fromisoformat(today)
    cutoff = {
        "week": today_d - timedelta(days=7),
        "month": today_d - timedelta(days=30),
        "quarter": today_d - timedelta(days=90),
        "ytd": date(today_d.year, 1, 1),
    }[period]
    exits_list = list(exits)
    out: list[Trade] = []
    for t in trades:
        cd = _trade_closed_date(t, exits_list)
        if cd is None:
            continue
        if cd >= cutoff:
            out.append(t)
    return out


def compute_stats(
    *, trades: Iterable[Trade], exits: Iterable[Exit],
    cash_movements: Iterable[CashMovement] = (),
) -> JournalStats:
    trades_list = list(trades)
    exits_list = list(exits)
    closed = [t for t in trades_list if t.status == "closed"]

    if not closed:
        return JournalStats(
            n_trades=0, n_wins=0, n_losses=0, win_rate=0.0,
            avg_win_r=0.0, avg_loss_r=0.0, expectancy_r=0.0,
            largest_win_r=0.0, largest_loss_r=0.0,
            total_r=0.0, total_pnl=0.0,
            current_streak=0, current_streak_kind="",
        )

    decorated = sorted(
        ((t, _trade_r(t, exits_list), _trade_pnl(t, exits_list),
          _trade_closed_date(t, exits_list)) for t in closed),
        key=lambda x: x[3] or date.min,
    )
    n = len(decorated)
    rs = [r for _, r, _, _ in decorated]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = n_wins / n if n > 0 else 0.0
    avg_win = sum(wins) / n_wins if wins else 0.0
    avg_loss = sum(losses) / n_losses if losses else 0.0
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    # Streak: walk decorated in reverse; consecutive same-sign
    streak = 0
    kind = ""
    if rs:
        first = rs[-1]
        if first > 0:
            kind = "W"
            for r in reversed(rs):
                if r > 0:
                    streak += 1
                else:
                    break
        elif first < 0:
            kind = "L"
            for r in reversed(rs):
                if r < 0:
                    streak += 1
                else:
                    break

    return JournalStats(
        n_trades=n, n_wins=n_wins, n_losses=n_losses,
        win_rate=win_rate, avg_win_r=avg_win, avg_loss_r=avg_loss,
        expectancy_r=expectancy,
        largest_win_r=max(wins) if wins else 0.0,
        largest_loss_r=min(losses) if losses else 0.0,
        total_r=sum(rs),
        total_pnl=sum(p for _, _, p, _ in decorated),
        current_streak=streak, current_streak_kind=kind,
    )
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/journal/__init__.py swing/journal/stats.py tests/journal/__init__.py tests/journal/test_stats.py
git commit -m "feat(journal): stats (share-weighted R, win rate, expectancy, streak)"
```

---

### Task F2: Behavioral flags

**Files:**
- Create: `swing/journal/flags.py`
- Create: `tests/journal/test_flags.py`

Three rules from legacy: caution-market entries, losers-held-too-long, cutting-winners-short. All take closed trades + exits + weather history (read from `weather_runs` repo).

- [ ] **Step 1: Write the failing test**

```python
# tests/journal/test_flags.py
"""Behavioral flags: caution-market, losers-held-too-long, cutting-winners-short."""
from __future__ import annotations

from swing.data.models import Exit, Trade, WeatherRun
from swing.journal.flags import compute_flags, BehavioralFlag


def _trade(tid: int, ticker: str, entry_date: str, exit_date: str,
           pnl: float = 0.0, r: float = 0.0) -> tuple[Trade, Exit]:
    t = Trade(id=tid, ticker=ticker, entry_date=entry_date,
              entry_price=100.0, initial_shares=10, initial_stop=95.0,
              current_stop=95.0, status="closed",
              watchlist_entry_target=None, watchlist_initial_stop=None, notes=None)
    e = Exit(id=tid, trade_id=tid, exit_date=exit_date, exit_price=100.0 + pnl/10,
             shares=10, reason="target", realized_pnl=pnl, r_multiple=r, notes=None)
    return t, e


def _wr(date: str, status: str) -> WeatherRun:
    return WeatherRun(id=None, run_ts=f"{date}T21:49:00", asof_date=date,
                      ticker="QQQ", status=status, close=480.0,
                      sma10=475.0, sma20=470.0, sma50=460.0,
                      slope20_5bar=0.5, slope10_5bar=0.7, rationale="r")


def test_no_flags_when_clean():
    flags = compute_flags(trades=[], exits=[], weather_runs=[])
    assert flags == []


def test_caution_market_entries_flagged():
    """2+ trades entered while weather was Caution/Bearish triggers flag."""
    t1, e1 = _trade(1, "AAPL", "2026-04-10", "2026-04-15", pnl=20, r=2)
    t2, e2 = _trade(2, "MSFT", "2026-04-11", "2026-04-16", pnl=-10, r=-1)
    weather = [
        _wr("2026-04-10", "Caution"),
        _wr("2026-04-11", "Bearish"),
    ]
    flags = compute_flags(trades=[t1, t2], exits=[e1, e2], weather_runs=weather)
    assert any(f.code == "caution_market_entries" for f in flags)


def test_losers_held_longer_than_winners_flagged():
    # winners: 3 days avg; losers: 10 days → 10/3 > 1.2 → flag
    winners = []
    losers = []
    for i in range(3):
        winners.append(_trade(100 + i, f"W{i}", "2026-04-10",
                              "2026-04-13", pnl=20, r=2))
    for i in range(3):
        losers.append(_trade(200 + i, f"L{i}", "2026-04-01",
                             "2026-04-11", pnl=-10, r=-1))
    trades = [t for t, _ in winners + losers]
    exits = [e for _, e in winners + losers]
    flags = compute_flags(trades=trades, exits=exits, weather_runs=[])
    assert any(f.code == "losers_held_too_long" for f in flags)


def test_cutting_winners_short_flagged():
    """50%+ of winning trades closed below +1R → flag."""
    cases = []
    for i in range(4):
        cases.append(_trade(i, f"X{i}", "2026-04-10", "2026-04-15", pnl=5, r=0.5))
    for i in range(4, 6):
        cases.append(_trade(i, f"X{i}", "2026-04-10", "2026-04-15", pnl=20, r=2.0))
    trades = [t for t, _ in cases]
    exits = [e for _, e in cases]
    flags = compute_flags(trades=trades, exits=exits, weather_runs=[])
    assert any(f.code == "cutting_winners_short" for f in flags)
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/journal/flags.py`**

```python
"""Behavioral flags — three pure rules from legacy trade.py.

Each rule returns a BehavioralFlag if it triggers, else None. The aggregator
returns the non-None list.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from swing.data.models import Exit, Trade, WeatherRun


@dataclass(frozen=True)
class BehavioralFlag:
    code: str
    title: str
    detail: str
    examples: list[str]


def _trade_r_share_weighted(trade: Trade, exits: list[Exit]) -> float:
    return sum(
        e.r_multiple * (e.shares / trade.initial_shares)
        for e in exits if e.trade_id == trade.id
    )


def _hold_days(trade: Trade, exits: list[Exit]) -> int | None:
    closes = [e.exit_date for e in exits if e.trade_id == trade.id]
    if not closes:
        return None
    last = max(date.fromisoformat(d) for d in closes)
    return (last - date.fromisoformat(trade.entry_date)).days


def _caution_market_entries(
    trades: list[Trade], exits: list[Exit], weather_by_date: dict[str, str],
) -> BehavioralFlag | None:
    bad: list[str] = []
    for t in trades:
        if t.status != "closed":
            continue
        status = weather_by_date.get(t.entry_date, "")
        if status in ("Caution", "Bearish"):
            bad.append(f"{t.ticker} ({t.entry_date}: {status})")
    if len(bad) < 2:
        return None
    return BehavioralFlag(
        code="caution_market_entries",
        title="Trades entered during Caution/Bearish weather",
        detail=f"{len(bad)} trades entered when weather was Caution or Bearish — "
               "review whether these were necessary",
        examples=bad[:5],
    )


def _losers_held_too_long(trades: list[Trade], exits: list[Exit]) -> BehavioralFlag | None:
    winners_days: list[int] = []
    losers_days: list[int] = []
    for t in trades:
        if t.status != "closed":
            continue
        d = _hold_days(t, exits)
        if d is None:
            continue
        r = _trade_r_share_weighted(t, exits)
        if r > 0:
            winners_days.append(d)
        elif r < 0:
            losers_days.append(d)
    if not winners_days or not losers_days:
        return None
    avg_w = sum(winners_days) / len(winners_days)
    avg_l = sum(losers_days) / len(losers_days)
    if avg_l > avg_w * 1.2:
        return BehavioralFlag(
            code="losers_held_too_long",
            title="Losers held longer than winners",
            detail=f"Avg loser hold {avg_l:.1f}d vs avg winner {avg_w:.1f}d "
                   f"({avg_l/avg_w:.1f}× ratio)",
            examples=[],
        )
    return None


def _cutting_winners_short(trades: list[Trade], exits: list[Exit]) -> BehavioralFlag | None:
    winners = [
        t for t in trades
        if t.status == "closed" and _trade_r_share_weighted(t, exits) > 0
    ]
    if len(winners) < 3:
        return None
    below_1r = [t for t in winners if _trade_r_share_weighted(t, exits) < 1.0]
    if len(below_1r) / len(winners) >= 0.5:
        return BehavioralFlag(
            code="cutting_winners_short",
            title="Cutting winners short",
            detail=f"{len(below_1r)} of {len(winners)} winners closed below +1R "
                   "— consider letting winners run",
            examples=[t.ticker for t in below_1r[:5]],
        )
    return None


def compute_flags(
    *, trades: Iterable[Trade], exits: Iterable[Exit],
    weather_runs: Iterable[WeatherRun],
) -> list[BehavioralFlag]:
    trades_list = list(trades)
    exits_list = list(exits)
    weather_by_date = {w.asof_date: w.status for w in weather_runs}

    candidates = [
        _caution_market_entries(trades_list, exits_list, weather_by_date),
        _losers_held_too_long(trades_list, exits_list),
        _cutting_winners_short(trades_list, exits_list),
    ]
    return [f for f in candidates if f is not None]
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/journal/flags.py tests/journal/test_flags.py
git commit -m "feat(journal): 3 behavioral-flag rules (legacy parity)"
```

---

### Task F3: TOS reconciliation

**Files:**
- Create: `swing/journal/tos_import.py`
- Create: `tests/fixtures/tos/synthetic-tos.csv`
- Create: `tests/journal/test_tos_import.py`

Parses TOS Account Statement CSV (multi-section) and produces a `ReconciliationReport` listing matched / unmatched / price-mismatch fills + new cash movements. Caller (CLI) decides what to commit.

- [ ] **Step 1: Create the synthetic TOS fixture**

```csv
# tests/fixtures/tos/synthetic-tos.csv

Cash Balance

DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE
2026-04-01,09:00:00,DEP,DEP-001,"WIRE DEPOSIT",$500.00,$1500.00
2026-04-15,11:30:00,WD,WD-001,"WIRE WITHDRAWAL",($100.00),$1400.00

Account Trade History

Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME
STOCK,BUY,5,TO OPEN,AAPL,--,--,--,$180.00,--,LMT,2026-04-15,09:30:00
STOCK,SELL,5,TO CLOSE,AAPL,--,--,--,$190.00,--,LMT,2026-04-22,15:30:00

Account Order History

(no relevant fills)

Account Summary

Net Liq,$1700.00
```

- [ ] **Step 2: Write the failing test**

```python
# tests/journal/test_tos_import.py
"""TOS reconciliation parser + matcher."""
from __future__ import annotations

from pathlib import Path

from swing.journal.tos_import import (
    parse_tos_export, reconcile_tos, ReconciliationReport,
    extract_cash_movements, extract_stock_fills,
)


FIXTURE = Path(__file__).parent.parent / "fixtures" / "tos" / "synthetic-tos.csv"


def test_parse_extracts_cash_section():
    sections = parse_tos_export(FIXTURE.read_text(encoding="utf-8"))
    assert "Cash Balance" in sections
    cash_rows = sections["Cash Balance"]
    assert len(cash_rows) == 2


def test_extract_cash_movements_handles_amount_formats():
    text = FIXTURE.read_text(encoding="utf-8")
    sections = parse_tos_export(text)
    movements = list(extract_cash_movements(sections["Cash Balance"]))
    assert len(movements) == 2
    by_kind = {m.kind for m in movements}
    assert by_kind == {"deposit", "withdraw"}
    deposit = next(m for m in movements if m.kind == "deposit")
    assert deposit.amount == 500.0
    assert deposit.ref == "DEP-001"
    withdraw = next(m for m in movements if m.kind == "withdraw")
    assert withdraw.amount == 100.0


def test_extract_stock_fills_filters_options():
    text = FIXTURE.read_text(encoding="utf-8")
    sections = parse_tos_export(text)
    fills = list(extract_stock_fills(sections["Account Trade History"]))
    # Both rows are stock; both included
    assert len(fills) == 2
    assert all(f.ticker == "AAPL" for f in fills)
    assert {f.open_close for f in fills} == {"OPEN", "CLOSE"}


def test_reconcile_reports_mismatched_and_dedup(tmp_path: Path):
    """End-to-end: parse fixture, reconcile against empty DB → report shows new cash + 1 unmatched fill."""
    from swing.data.db import ensure_schema
    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    assert isinstance(report, ReconciliationReport)
    assert len(report.new_cash_movements) == 2
    assert len(report.unmatched_open_fills) == 1   # AAPL BUY
    assert len(report.unmatched_close_fills) == 1  # AAPL SELL (no matching open trade in DB)
    assert report.matched_fills == []


def test_reconcile_matches_close_to_prior_open_trade(tmp_path: Path):
    """A CLOSE fill on 2026-04-22 must match an open trade opened 2026-04-15
    (same ticker, different date). Previously the fill was wrongly unmatched."""
    from swing.data.db import ensure_schema
    from swing.trades.entry import EntryRequest, record_entry

    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    # Pre-seed an open AAPL trade that the fixture CLOSE should match
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="seed",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False)
    finally:
        conn.close()

    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    # OPEN fill is strict-matched (same ticker+date+qty=5 @ $180)
    # CLOSE fill should now match via find_any_open_trade, not be unmatched
    assert len(report.matched_fills) == 2
    assert len(report.unmatched_close_fills) == 0


def test_reconcile_within_batch_cumulative_overfill(tmp_path: Path):
    """Two CLOSE fills for the same trade in ONE TOS statement must not both
    match if their cumulative shares exceed remaining (within-batch allocation
    guard — Codex Round 2 Major 2)."""
    from swing.data.db import ensure_schema
    from swing.trades.entry import EntryRequest, record_entry

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="seed",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False)
    finally:
        conn.close()

    # Synthesize a TOS text with TWO close fills that cumulatively exceed 5
    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,SELL,3,TO CLOSE,AAPL,--,--,--,$190.00,--,LMT,2026-04-22,15:30:00\n"
        "STOCK,SELL,3,TO CLOSE,AAPL,--,--,--,$191.00,--,LMT,2026-04-23,15:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    # First 3 match; second 3 would cumulatively = 6 > 5 → flagged unmatched
    assert len(report.matched_fills) == 1
    assert len(report.unmatched_close_fills) == 1


def test_reconcile_close_overfill_flagged(tmp_path: Path):
    """A CLOSE fill that would overfill (shares exceeding remaining) must be
    flagged as unmatched — not silently matched."""
    from swing.data.db import ensure_schema
    from swing.trades.entry import EntryRequest, record_entry

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        # Open a trade with 3 shares — the fixture's CLOSE is 5 shares → overfill
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=3, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="seed",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False)
    finally:
        conn.close()
    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    # OPEN is strict-matched only if qty=3, but fixture has qty=5 → unmatched OPEN
    assert len(report.unmatched_open_fills) == 1
    # CLOSE overfill → flagged unmatched for operator
    assert len(report.unmatched_close_fills) == 1
```

- [ ] **Step 3: Implement `swing/journal/tos_import.py`**

```python
"""TOS Account Statement reconciliation.

Parser splits the multi-section export by labels (`Cash Balance`,
`Account Trade History`, etc.). Extractors consume normalized columns and
yield CashMovement / TosFill records. `reconcile_tos` returns a
ReconciliationReport — caller (CLI) decides what to commit.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Iterable

from swing.data.db import connect
from swing.data.models import CashMovement
from swing.data.repos.cash import find_by_ref
from swing.data.repos.trades import find_any_open_trade, find_open_trade_by_match


_SECTION_LABELS = (
    "Cash Balance",
    "Account Trade History",
    "Account Order History",
    "Futures Statements",
    "Forex Statements",
    "Account Summary",
)


@dataclass(frozen=True)
class TosFill:
    date: str
    side: str        # 'BUY' | 'SELL'
    open_close: str  # 'OPEN' | 'CLOSE'
    ticker: str
    qty: int
    price: float


@dataclass(frozen=True)
class ReconciliationReport:
    matched_fills: list[TosFill] = field(default_factory=list)
    unmatched_open_fills: list[TosFill] = field(default_factory=list)
    unmatched_close_fills: list[TosFill] = field(default_factory=list)
    price_mismatch_fills: list[TosFill] = field(default_factory=list)
    new_cash_movements: list[CashMovement] = field(default_factory=list)
    duplicate_cash_movements: list[CashMovement] = field(default_factory=list)


def parse_tos_export(text: str) -> dict[str, list[dict]]:
    """Split the multi-section TOS export into a dict of section -> list-of-row-dicts.
    Each row dict uses the section's first non-empty CSV row as the header.
    """
    lines = text.splitlines()
    sections: dict[str, list[dict]] = {}
    cur_label: str | None = None
    cur_buf: list[str] = []

    def flush():
        if cur_label is None or not cur_buf:
            return
        # Skip blank lines and parse remaining as CSV
        clean = [l for l in cur_buf if l.strip()]
        if not clean:
            return
        reader = csv.DictReader(StringIO("\n".join(clean)))
        sections[cur_label] = [dict(r) for r in reader]

    for line in lines:
        stripped = line.strip()
        if stripped in _SECTION_LABELS:
            flush()
            cur_label = stripped
            cur_buf = []
        elif stripped.startswith("#"):
            continue  # comment
        else:
            cur_buf.append(line)
    flush()
    return sections


def _parse_tos_amount(raw: str) -> float:
    """Handle '$', commas, '($x)' negatives, '--' / 'N/A' → 0.0."""
    s = (raw or "").strip()
    if s in ("", "--", "N/A"):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").strip()
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def extract_cash_movements(rows: Iterable[dict]) -> list[CashMovement]:
    out: list[CashMovement] = []
    for row in rows:
        ttype = (row.get("TYPE") or "").strip()
        if ttype in ("", "BAL"):
            continue
        amount = _parse_tos_amount(row.get("AMOUNT", ""))
        if amount == 0.0:
            continue
        ref_raw = (row.get("REF #") or "").strip().strip('"').replace("=", "")
        ref = ref_raw or None
        kind = "deposit" if amount > 0 else "withdraw"
        out.append(CashMovement(
            id=None, date=(row.get("DATE") or "").strip(),
            kind=kind, amount=abs(amount), ref=ref,
            note=(row.get("DESCRIPTION") or "").strip() or None,
        ))
    return out


def extract_stock_fills(rows: Iterable[dict]) -> list[TosFill]:
    out: list[TosFill] = []
    for row in rows:
        spread = (row.get("Spread") or "").strip().upper()
        if spread not in ("", "STOCK"):
            continue
        exp = (row.get("Exp") or "").strip()
        if exp and exp != "--":
            continue  # skip options
        ticker = (row.get("Symbol") or "").strip().upper()
        if not ticker:
            continue
        side = (row.get("Side") or "").strip().upper()
        pos = (row.get("Pos Effect") or "").strip().upper()
        if "OPEN" in pos:
            oc = "OPEN"
        elif "CLOSE" in pos:
            oc = "CLOSE"
        else:
            oc = "OPEN" if side == "BUY" else "CLOSE"
        try:
            qty = int(row.get("Qty") or row.get("QTY") or 0)
        except ValueError:
            continue
        price = _parse_tos_amount(row.get("Price") or row.get("PRICE") or "")
        date_str = (row.get("Date") or row.get("DATE") or "").strip()
        if qty <= 0 or not date_str:
            continue
        out.append(TosFill(
            date=date_str, side=side, open_close=oc,
            ticker=ticker, qty=qty, price=price,
        ))
    return out


def reconcile_tos(
    *, db_path: Path, tos_text: str, price_tolerance: float = 0.01,
) -> ReconciliationReport:
    sections = parse_tos_export(tos_text)
    cash_rows = sections.get("Cash Balance", [])
    fills_rows = sections.get("Account Trade History", [])

    cash_candidates = extract_cash_movements(cash_rows)
    fills = extract_stock_fills(fills_rows)

    report = ReconciliationReport()
    conn = connect(db_path)
    try:
        # Cash dedup by ref
        for c in cash_candidates:
            if c.ref and find_by_ref(conn, c.ref) is not None:
                report.duplicate_cash_movements.append(c)
            else:
                report.new_cash_movements.append(c)

        # Fill matching.
        # OPEN fills: strict match on (ticker, entry_date, initial_shares), then
        #   fuzzy on (ticker, entry_date). Price tolerance applied to a strict match.
        # CLOSE fills: look up any OPEN trade for the ticker (not the same date as
        #   the exit — legit sells may close a position opened days earlier). If no
        #   open trade exists OR the cumulative close (including earlier fills in
        #   THIS batch) would exceed remaining shares, flag as unmatched for
        #   operator review.
        # `within_batch_alloc[trade_id] = shares already matched in this reconciliation`
        # prevents double-matching multiple CLOSE fills for the same trade within
        # a single TOS statement.
        within_batch_alloc: dict[int, int] = {}
        for f in fills:
            if f.open_close == "OPEN":
                t = find_open_trade_by_match(
                    conn, ticker=f.ticker, entry_date=f.date,
                    initial_shares=f.qty,
                )
                if t is not None:
                    if abs(t.entry_price - f.price) > price_tolerance:
                        report.price_mismatch_fills.append(f)
                    else:
                        report.matched_fills.append(f)
                else:
                    report.unmatched_open_fills.append(f)
            else:  # CLOSE
                t = find_any_open_trade(conn, ticker=f.ticker)
                if t is None:
                    report.unmatched_close_fills.append(f)
                    continue
                sold_in_db = conn.execute(
                    "SELECT COALESCE(SUM(shares), 0) FROM exits WHERE trade_id = ?",
                    (t.id,),
                ).fetchone()[0]
                already_allocated = within_batch_alloc.get(t.id or 0, 0)
                cumulative = sold_in_db + already_allocated + f.qty
                if cumulative > t.initial_shares:
                    # Overfill considering BOTH persisted exits AND earlier matches
                    # in this reconciliation batch — flag for operator.
                    report.unmatched_close_fills.append(f)
                else:
                    report.matched_fills.append(f)
                    within_batch_alloc[t.id or 0] = already_allocated + f.qty
    finally:
        conn.close()
    return report
```

- [ ] **Step 4: Verify** — `python -m pytest tests/journal/test_tos_import.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/journal/tos_import.py tests/journal/test_tos_import.py tests/fixtures/tos/synthetic-tos.csv
git commit -m "feat(journal): TOS Account Statement reconciliation parser + matcher"
```

---

### Task F4: CLI subcommands — journal review / cash / tos-import

**Files:**
- Modify: `swing/cli.py` — add `journal` group
- Create: `tests/cli/test_cli_journal.py`
- Create: `tests/cli/test_cli_tos.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/cli/test_cli_journal.py
"""CLI: swing journal review / cash."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def test_journal_review_empty(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "journal", "review"])
    assert r.exit_code == 0
    assert "0 trades" in r.output or "no trades" in r.output.lower()


def test_journal_cash_deposit(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        "--deposit", "200.0", "--date", "2026-04-01",
        "--ref", "DEP-X", "--note", "test deposit",
    ])
    assert r.exit_code == 0, r.output
    assert "DEP-X" in r.output or "deposit" in r.output.lower()
```

```python
# tests/cli/test_cli_tos.py
"""CLI: swing tos-import."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def test_tos_import_dry_run(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    fixture = Path(__file__).parent.parent / "fixtures" / "tos" / "synthetic-tos.csv"
    r = runner.invoke(main, [
        "--config", str(cfg), "tos-import",
        "--csv", str(fixture), "--dry-run",
    ])
    assert r.exit_code == 0, r.output
    assert "deposit" in r.output.lower() or "DEP-001" in r.output
    assert "unmatched" in r.output.lower()
```

- [ ] **Step 2: Verify both fail.**

- [ ] **Step 3: Add `journal` group + `tos-import` cmd to `swing/cli.py`**

```python
@main.group("journal")
def journal_group() -> None:
    """Review stats + record cash movements."""


@journal_group.command("review")
@click.option("--period", type=click.Choice(["week", "month", "quarter", "ytd", "all"]),
              default="all")
@click.option("--today", default=None, help="YYYY-MM-DD; defaults to today")
@click.pass_context
def journal_review_cmd(ctx, period, today):
    """Compute and print journal stats + behavioral flags."""
    from datetime import date as _date
    from swing.data.db import connect
    from swing.data.repos.cash import list_cash
    from swing.data.repos.trades import list_closed_trades, list_open_trades, list_all_exits
    from swing.journal.flags import compute_flags
    from swing.journal.stats import compute_stats, period_filter
    # Weather repo — we'll need it for behavioral flags
    cfg = ctx.obj["config"]
    today = today or _date.today().isoformat()
    conn = connect(cfg.paths.db_path)
    try:
        all_trades = list_open_trades(conn) + list_closed_trades(conn)
        all_exits = list_all_exits(conn)
        cash = list_cash(conn)
        # Weather rows (for flags)
        weather_rows = conn.execute(
            "SELECT id, run_ts, asof_date, ticker, status, close, sma10, sma20, sma50, "
            "slope20_5bar, slope10_5bar, rationale FROM weather_runs"
        ).fetchall()
    finally:
        conn.close()

    from swing.data.models import WeatherRun
    weather_runs = [
        WeatherRun(*row) for row in weather_rows
    ]
    filtered = period_filter(all_trades, all_exits, period=period, today=today)
    stats = compute_stats(trades=filtered, exits=all_exits, cash_movements=cash)
    flags = compute_flags(trades=filtered, exits=all_exits, weather_runs=weather_runs)

    click.echo(f"=== Journal Review ({period}) — {today} ===")
    click.echo(f"{stats.n_trades} trades · {stats.n_wins}W / {stats.n_losses}L")
    click.echo(f"Win rate {stats.win_rate*100:.1f}%  Expectancy {stats.expectancy_r:+.2f}R")
    click.echo(f"Avg win {stats.avg_win_r:+.2f}R · avg loss {stats.avg_loss_r:+.2f}R")
    click.echo(f"Total {stats.total_r:+.2f}R · ${stats.total_pnl:+.2f}")
    click.echo(f"Streak: {stats.current_streak}{stats.current_streak_kind}")
    if flags:
        click.echo("\nBehavioral flags:")
        for f in flags:
            click.echo(f"  • {f.title} — {f.detail}")


@journal_group.command("cash")
@click.option("--deposit", "deposit", type=float, default=None)
@click.option("--withdraw", "withdraw", type=float, default=None)
@click.option("--date", "date_str", required=True, help="YYYY-MM-DD")
@click.option("--ref", default=None)
@click.option("--note", default=None)
@click.pass_context
def journal_cash_cmd(ctx, deposit, withdraw, date_str, ref, note):
    """Log a cash movement."""
    from swing.data.db import connect
    from swing.data.models import CashMovement
    from swing.data.repos.cash import insert_cash

    if (deposit is None) == (withdraw is None):
        raise click.ClickException("Specify exactly one of --deposit or --withdraw")
    kind = "deposit" if deposit is not None else "withdraw"
    amount = deposit if deposit is not None else withdraw

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cid = insert_cash(conn, CashMovement(
                id=None, date=date_str, kind=kind, amount=amount, ref=ref, note=note,
            ))
    finally:
        conn.close()
    click.echo(f"Cash {kind} #{cid}: ${amount:.2f}{f' ref={ref}' if ref else ''}")


@main.command("tos-import")
@click.option("--csv", "csv_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--dry-run", is_flag=True, help="Print report without committing anything")
@click.option("--auto-confirm", is_flag=True, help="Commit new cash movements without prompting")
@click.pass_context
def tos_import_cmd(ctx, csv_path, dry_run, auto_confirm):
    """Reconcile a TOS Account Statement CSV against the journal."""
    from pathlib import Path as _Path
    from swing.data.db import connect
    from swing.data.repos.cash import insert_cash
    from swing.journal.tos_import import reconcile_tos

    cfg = ctx.obj["config"]
    text = _Path(csv_path).read_text(encoding="utf-8")
    report = reconcile_tos(db_path=cfg.paths.db_path, tos_text=text)

    click.echo(f"Cash: {len(report.new_cash_movements)} new, "
               f"{len(report.duplicate_cash_movements)} duplicate")
    for c in report.new_cash_movements:
        click.echo(f"  + {c.kind} ${c.amount:.2f} on {c.date} (ref={c.ref})")
    click.echo(f"Fills: matched={len(report.matched_fills)}, "
               f"price-mismatch={len(report.price_mismatch_fills)}, "
               f"unmatched OPEN={len(report.unmatched_open_fills)}, "
               f"unmatched CLOSE={len(report.unmatched_close_fills)}")
    for f in report.price_mismatch_fills:
        click.echo(f"  ! PRICE MISMATCH: {f.ticker} {f.date} qty={f.qty} TOS=${f.price:.2f}")
    for f in report.unmatched_open_fills:
        click.echo(f"  ? unmatched OPEN: {f.ticker} {f.date} qty={f.qty} @ ${f.price:.2f}")

    if dry_run:
        click.echo("Dry run — no changes committed.")
        return

    if report.new_cash_movements and (auto_confirm or click.confirm(
            f"Commit {len(report.new_cash_movements)} new cash movements?", default=True)):
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                for c in report.new_cash_movements:
                    insert_cash(conn, c)
        finally:
            conn.close()
        click.echo("Cash movements committed.")

    if report.unmatched_open_fills and not auto_confirm:
        click.echo(
            "Unmatched OPEN fills require manual entry via `swing trade entry`. "
            "Listing only — no auto-creation."
        )
```

- [ ] **Step 4: Verify** — `python -m pytest tests/cli/test_cli_journal.py tests/cli/test_cli_tos.py -v` → 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/cli/test_cli_journal.py tests/cli/test_cli_tos.py
git commit -m "feat(cli): add `swing journal review|cash` and `swing tos-import`"
```

---

## Sub-Phase G — Pipeline Orchestrator

The integration point. Wires together everything from sub-phases A–F into the 9-step nightly pipeline (spec §5.1) with lease/heartbeat fencing, manifest-driven staged file writes, and startup recovery.

### Task G1: Finviz schema validation

**Files:**
- Create: `swing/pipeline/__init__.py` (initially empty; populated in Task G8)
- Create: `swing/pipeline/finviz_schema.py`
- Create: `tests/pipeline/__init__.py` (empty)
- Create: `tests/pipeline/test_finviz_schema.py`

The schema declares the required Finviz columns. Validation returns a `ValidationResult`; the rejector moves the file to `data/finviz-inbox/rejected/` with a sidecar JSON describing why.

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_finviz_schema.py
"""Finviz CSV schema validation + rejection."""
from __future__ import annotations

import json
from pathlib import Path

from swing.pipeline.finviz_schema import (
    REQUIRED_COLUMNS, validate_csv, reject_csv, ValidationResult,
)


def _good_csv(path: Path):
    cols = ",".join(REQUIRED_COLUMNS)
    rows = ["1,AAPL,Tech,Hardware,USA,180.0,2.5%,2.0,1.5,5.0,200.0,150.0,200000000,Computer Hardware",
            "2,MSFT,Tech,Software,USA,420.0,1.5%,1.0,0.8,4.5,440.0,330.0,300000000,Software"]
    path.write_text(cols + "\n" + "\n".join(rows), encoding="utf-8")


def test_valid_csv_passes(tmp_path: Path):
    p = tmp_path / "good.csv"
    _good_csv(p)
    result = validate_csv(p)
    assert result.is_valid
    assert result.row_count == 2


def test_missing_required_column_fails(tmp_path: Path):
    p = tmp_path / "bad.csv"
    cols = [c for c in REQUIRED_COLUMNS if c != "Ticker"]
    p.write_text(",".join(cols) + "\nA,B,C", encoding="utf-8")
    result = validate_csv(p)
    assert not result.is_valid
    assert any("Ticker" in r for r in result.reasons)


def test_empty_csv_fails(tmp_path: Path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    result = validate_csv(p)
    assert not result.is_valid


def test_reject_moves_with_sidecar(tmp_path: Path):
    inbox = tmp_path / "inbox"
    rejected = inbox / "rejected"
    inbox.mkdir()
    bad = inbox / "bad.csv"
    bad.write_text("just,bad\n", encoding="utf-8")

    result = ValidationResult(is_valid=False, reasons=["bad columns"], row_count=0)
    reject_csv(bad, result, rejected_dir=rejected)

    assert not bad.exists()
    moved = list(rejected.glob("*.csv"))
    assert len(moved) == 1
    sidecar = moved[0].with_suffix(moved[0].suffix + ".rejected-reasons.json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert "bad columns" in data["reasons"]
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/pipeline/finviz_schema.py`**

```python
"""Finviz CSV schema declaration + validator + rejector."""
from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Minimum columns from a Finviz Elite export needed for evaluation.
# Columns are listed in legacy `evaluate_candidates.py` Finviz parsing.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "No.", "Ticker", "Sector", "Industry", "Country", "Price",
    "Change", "Average Volume", "Relative Volume",
    "Average True Range", "52-Week High", "52-Week Low",
    "Market Cap",
)


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    reasons: list[str]
    row_count: int


def validate_csv(path: Path) -> ValidationResult:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return ValidationResult(is_valid=False, reasons=["empty file"], row_count=0)

    reader = csv.reader(text.splitlines())
    try:
        header = next(reader)
    except StopIteration:
        return ValidationResult(is_valid=False, reasons=["no header row"], row_count=0)

    header_set = set(h.strip() for h in header)
    missing = [c for c in REQUIRED_COLUMNS if c not in header_set]
    reasons: list[str] = []
    if missing:
        reasons.append(f"missing columns: {missing}")

    rows = list(reader)
    if not rows:
        reasons.append("no data rows")
    return ValidationResult(
        is_valid=not reasons, reasons=reasons, row_count=len(rows),
    )


def reject_csv(
    path: Path, result: ValidationResult, *, rejected_dir: Path,
) -> Path:
    """Move file to rejected/ + write .rejected-reasons.json sidecar.
    Returns the new path."""
    rejected_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    new_name = f"{path.stem}.rejected-{ts}{path.suffix}"
    dst = rejected_dir / new_name
    shutil.move(str(path), str(dst))
    sidecar = dst.with_suffix(dst.suffix + ".rejected-reasons.json")
    sidecar.write_text(
        json.dumps({
            "rejected_at": datetime.now().isoformat(timespec="seconds"),
            "original_path": str(path),
            "reasons": result.reasons,
            "row_count": result.row_count,
        }, indent=2),
        encoding="utf-8",
    )
    return dst
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/__init__.py swing/pipeline/finviz_schema.py tests/pipeline/__init__.py tests/pipeline/test_finviz_schema.py
git commit -m "feat(pipeline): Finviz CSV schema validator + rejector"
```

---

### Task G2: Finviz inbox selector

**Files:**
- Create: `swing/pipeline/finviz_select.py`
- Create: `tests/pipeline/test_finviz_select.py`

Selection rule: **by filename date if parseable** (regex `(\d{1,2})([A-Za-z]{3})(\d{4})` matching `finviz17Apr2026.csv`), else **by mtime, newest wins**. Multiple files with same date → abort with `AmbiguousInboxError`. Empty inbox → `NoFilesError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_finviz_select.py
"""Finviz inbox selector — date-from-filename → mtime fallback → ambiguity detection."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from swing.pipeline.finviz_select import (
    select_csv, NoFilesError, AmbiguousInboxError,
)


def test_no_files_raises(tmp_path: Path):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    with pytest.raises(NoFilesError):
        select_csv(inbox)


def test_single_dated_file(tmp_path: Path):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    f = inbox / "finviz17Apr2026.csv"
    f.write_text("x", encoding="utf-8")
    selected = select_csv(inbox)
    assert selected == f


def test_picks_newest_by_filename_date(tmp_path: Path):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    older = inbox / "finviz14Apr2026.csv"
    newer = inbox / "finviz17Apr2026.csv"
    older.write_text("a", encoding="utf-8")
    newer.write_text("b", encoding="utf-8")
    assert select_csv(inbox) == newer


def test_falls_back_to_mtime_when_no_date(tmp_path: Path):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    a = inbox / "screener.csv"
    b = inbox / "screen2.csv"
    a.write_text("x", encoding="utf-8")
    time.sleep(0.05)
    b.write_text("x", encoding="utf-8")
    assert select_csv(inbox) == b


def test_ambiguous_same_date_raises(tmp_path: Path):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    (inbox / "finviz17Apr2026-a.csv").write_text("a", encoding="utf-8")
    (inbox / "finviz17Apr2026-b.csv").write_text("b", encoding="utf-8")
    with pytest.raises(AmbiguousInboxError, match="2026-04-17"):
        select_csv(inbox)


def test_skips_rejected_subdir(tmp_path: Path):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    rejected = inbox / "rejected"; rejected.mkdir()
    (rejected / "finviz17Apr2026.csv").write_text("x", encoding="utf-8")
    with pytest.raises(NoFilesError):
        select_csv(inbox)
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/pipeline/finviz_select.py`**

```python
"""Finviz inbox CSV selection with date-from-filename + ambiguity check."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

_FILENAME_DATE_RE = re.compile(r"(\d{1,2})([A-Za-z]{3})(\d{4})")
_MONTHS = {
    m: i + 1 for i, m in enumerate([
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    ])
}


class NoFilesError(Exception):
    """Inbox is empty (excluding rejected/)."""


class AmbiguousInboxError(Exception):
    """Multiple files share the same date stamp."""


def _parse_filename_date(name: str) -> date | None:
    m = _FILENAME_DATE_RE.search(name)
    if not m:
        return None
    day, mon_str, year = m.group(1), m.group(2).lower(), m.group(3)
    if mon_str not in _MONTHS:
        return None
    try:
        return date(int(year), _MONTHS[mon_str], int(day))
    except ValueError:
        return None


def select_csv(inbox_dir: Path) -> Path:
    candidates = [
        f for f in inbox_dir.glob("*.csv")
        if f.is_file() and "rejected" not in f.parts
    ]
    if not candidates:
        raise NoFilesError(f"No CSV files in {inbox_dir}")

    # Group by parsed filename date
    by_date: dict[date | None, list[Path]] = {}
    for f in candidates:
        d = _parse_filename_date(f.name)
        by_date.setdefault(d, []).append(f)

    dated = {d: files for d, files in by_date.items() if d is not None}
    if dated:
        newest_date = max(dated.keys())
        files = dated[newest_date]
        if len(files) > 1:
            raise AmbiguousInboxError(
                f"Multiple files for date {newest_date}: {sorted(f.name for f in files)}"
            )
        return files[0]

    # No dated files — fall back to mtime
    return max(candidates, key=lambda p: p.stat().st_mtime)
```

- [ ] **Step 4: Verify** — `python -m pytest tests/pipeline/test_finviz_select.py -v` → 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/finviz_select.py tests/pipeline/test_finviz_select.py
git commit -m "feat(pipeline): Finviz inbox selector (date-from-filename, mtime fallback)"
```

---

### Task G3: Lease class

**Files:**
- Create: `swing/pipeline/lease.py`
- Create: `tests/pipeline/test_lease.py`

Wraps the lease repo into a context-managerial object. `acquire_lease()` checks for active runs, inserts a fresh row, returns a `Lease` whose methods all use the captured token.

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_lease.py
"""Lease acquire/release + concurrent-rejection."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import LeaseRevoked, find_run
from swing.pipeline.lease import (
    acquire_lease, ConcurrentRunBlocked, Lease,
)


def test_acquire_inserts_and_returns_lease(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    assert isinstance(lease, Lease)
    assert lease.run_id > 0
    assert lease.token

    # Cleanup
    lease.release(state="complete")


def test_concurrent_blocked_within_threshold(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    first = acquire_lease(
        db_path=db, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    with pytest.raises(ConcurrentRunBlocked):
        acquire_lease(
            db_path=db, trigger="manual",
            data_asof_date="2026-04-15", action_session_date="2026-04-16",
            block_threshold_seconds=120,
        )
    first.release(state="complete")


def test_release_marks_complete(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    lease.release(state="complete")
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        run = find_run(conn, lease.run_id)
    finally:
        conn.close()
    assert run.state == "complete"
    assert run.finished_ts is not None


def test_release_failed_with_error(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    lease.release(state="failed", error_message="boom")
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        run = find_run(conn, lease.run_id)
    finally:
        conn.close()
    assert run.state == "failed"
    assert run.error_message == "boom"
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/pipeline/lease.py`**

```python
"""Lease — wraps pipeline_runs repo with token-bound mutations."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from swing.data.db import connect
from swing.data.repos.pipeline import (
    LeaseRevoked, find_active_run, finalize_run, insert_pipeline_run,
    update_heartbeat, update_status_columns, update_step,
)


class ConcurrentRunBlocked(Exception):
    """Another pipeline_runs row has state='running' with a fresh heartbeat."""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _heartbeat_age_seconds(now: datetime, ts: str) -> float:
    return (now - datetime.fromisoformat(ts)).total_seconds()


@dataclass
class Lease:
    db_path: Path
    run_id: int
    token: str

    def heartbeat(self) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                update_heartbeat(
                    conn, run_id=self.run_id, lease_token=self.token,
                    heartbeat_ts=_now_iso(),
                )
        finally:
            conn.close()

    def step(self, name: str) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                update_step(
                    conn, run_id=self.run_id, lease_token=self.token,
                    step=name, progress_ts=_now_iso(),
                )
        finally:
            conn.close()

    def status(self, **cols: str) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                update_status_columns(
                    conn, run_id=self.run_id, lease_token=self.token, **cols,
                )
        finally:
            conn.close()

    def release(
        self, *, state: str, error_message: str | None = None,
        warnings_json: str | None = None,
    ) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                finalize_run(
                    conn, run_id=self.run_id, lease_token=self.token,
                    state=state, finished_ts=_now_iso(),
                    error_message=error_message, warnings_json=warnings_json,
                )
        finally:
            conn.close()


def acquire_lease(
    *, db_path: Path, trigger: str, data_asof_date: str,
    action_session_date: str, block_threshold_seconds: int = 120,
    finviz_csv_path: str | None = None,
    rs_universe_version: str | None = None,
    rs_universe_hash: str | None = None,
) -> Lease:
    """Insert a fresh pipeline_runs row + return Lease.

    Race-safe: uses BEGIN IMMEDIATE to acquire a write transaction before the
    check-and-insert, and relies on the partial unique index ux_pipeline_one_running
    (see migration 0003) as a second line of defense. Any race-winner gets the
    lease; every loser gets ConcurrentRunBlocked.
    """
    import sqlite3

    conn = connect(db_path)
    try:
        # BEGIN IMMEDIATE acquires the SQLite reserved lock up front; only one writer
        # can hold it at a time. Python's default isolation_level is "" (deferred) so
        # we have to issue the BEGIN explicitly.
        conn.execute("BEGIN IMMEDIATE")
        try:
            active = find_active_run(conn)
            if active is not None and active.lease_heartbeat_ts is not None:
                age = _heartbeat_age_seconds(datetime.now(), active.lease_heartbeat_ts)
                if age <= block_threshold_seconds:
                    conn.execute("ROLLBACK")
                    raise ConcurrentRunBlocked(
                        f"run {active.id} state=running, heartbeat {age:.0f}s ago"
                    )
            try:
                run_id, token = insert_pipeline_run(
                    conn, started_ts=_now_iso(), trigger=trigger,
                    data_asof_date=data_asof_date,
                    action_session_date=action_session_date,
                    lease_heartbeat_ts=_now_iso(),
                    finviz_csv_path=finviz_csv_path,
                    rs_universe_version=rs_universe_version,
                    rs_universe_hash=rs_universe_hash,
                )
            except sqlite3.IntegrityError as exc:
                # ux_pipeline_one_running partial index triggered — another writer
                # beat us into the 'running' slot. Map to ConcurrentRunBlocked.
                conn.execute("ROLLBACK")
                raise ConcurrentRunBlocked(
                    f"another run inserted concurrently: {exc}"
                ) from exc
            conn.execute("COMMIT")
        except ConcurrentRunBlocked:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return Lease(db_path=db_path, run_id=run_id, token=token)
```

- [ ] **Step 4: Verify** — `python -m pytest tests/pipeline/test_lease.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/lease.py tests/pipeline/test_lease.py
git commit -m "feat(pipeline): Lease acquire + concurrent-rejection"
```

---

### Task G4: Heartbeat thread

**Files:**
- Create: `swing/pipeline/heartbeat.py`
- Create: `tests/pipeline/test_heartbeat.py`

Background thread emits `lease.heartbeat()` every N seconds. Stops cleanly via `threading.Event`. Critical: thread uses its own connection (sqlite3 disallows cross-thread by default).

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_heartbeat.py
"""Heartbeat thread — emits at interval, stops cleanly."""
from __future__ import annotations

import time
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import find_run
from swing.pipeline.heartbeat import Heartbeat
from swing.pipeline.lease import acquire_lease


def test_heartbeat_updates_at_interval(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    hb = Heartbeat(lease=lease, interval_seconds=0.2)
    hb.start()
    try:
        time.sleep(0.5)  # at least 2 ticks
    finally:
        hb.stop()

    import sqlite3
    conn = sqlite3.connect(db)
    try:
        run = find_run(conn, lease.run_id)
    finally:
        conn.close()
    assert run.lease_heartbeat_ts is not None
    lease.release(state="complete")


def test_heartbeat_stops_on_event(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    hb = Heartbeat(lease=lease, interval_seconds=0.1)
    hb.start()
    hb.stop()
    assert not hb.is_alive()
    lease.release(state="complete")
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/pipeline/heartbeat.py`**

```python
"""Background thread emitting lease heartbeats. Stops cleanly via Event."""
from __future__ import annotations

import threading

from swing.data.repos.pipeline import LeaseRevoked
from swing.pipeline.lease import Lease


class Heartbeat:
    def __init__(self, *, lease: Lease, interval_seconds: float = 30.0):
        self.lease = lease
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.lease.heartbeat()
            except LeaseRevoked:
                # Force-cleared mid-run — exit thread; main loop will see it next step.
                return
            except Exception:
                # Don't crash the heartbeat thread on transient DB errors;
                # let the main loop's lease-token check decide.
                pass
            self._stop.wait(self.interval)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="heartbeat")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/heartbeat.py tests/pipeline/test_heartbeat.py
git commit -m "feat(pipeline): heartbeat thread with clean shutdown"
```

---

### Task G5: Staging dir + atomic promote

**Files:**
- Create: `swing/pipeline/staging.py`
- Create: `tests/pipeline/test_staging.py`

`StagingDir` writes to `<base>/.staging/<run_id>/`. After all artifacts are written, `promote()` writes a manifest, re-checks the lease, then atomically renames to the target path (with a `.prev/` backup).

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_staging.py
"""StagingDir + atomic promote with manifest + .prev backup."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from swing.pipeline.staging import StagingDir, promote_staging


def test_writes_to_staging(tmp_path: Path):
    staging = StagingDir(base=tmp_path / "charts", run_id=1, artifact_type="charts")
    staging.path.parent.mkdir(parents=True, exist_ok=True)
    staging.create()
    (staging.path / "AAPL.png").write_bytes(b"png-data")
    assert (tmp_path / "charts" / ".staging" / "1" / "AAPL.png").exists()


def _seed_running_run(db_path: Path, *, run_id_target: int = 1) -> str:
    """Helper: ensure schema + insert a running pipeline_runs row. Returns lease_token."""
    from swing.data.db import ensure_schema
    from swing.data.repos.pipeline import insert_pipeline_run
    ensure_schema(db_path).close()
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts="2026-04-15T21:49:00", trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts="2026-04-15T21:49:30",
            )
        assert rid == run_id_target
    finally:
        conn.close()
    return token


def test_promote_to_canonical(tmp_path: Path):
    db = tmp_path / "swing.db"
    token = _seed_running_run(db)
    base = tmp_path / "charts"
    staging = StagingDir(base=base, run_id=1, artifact_type="charts")
    staging.create()
    (staging.path / "AAPL.png").write_bytes(b"x")

    target = base / "2026-04-15"
    result = promote_staging(
        staging=staging, target=target, lease_token=token, db_path=db,
        manifest_extras={"data_asof_date": "2026-04-15"},
    )
    assert result.target_path == target
    assert (target / "AAPL.png").exists()
    assert (target / "MANIFEST.json").exists()
    manifest = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["lease_token"] == token
    assert manifest["run_id"] == 1
    assert manifest["data_asof_date"] == "2026-04-15"


def test_promote_backs_up_previous(tmp_path: Path):
    db = tmp_path / "swing.db"
    token = _seed_running_run(db)
    base = tmp_path / "charts"
    target = base / "2026-04-15"
    target.mkdir(parents=True)
    (target / "OLD.png").write_bytes(b"old")

    staging = StagingDir(base=base, run_id=1, artifact_type="charts")
    staging.create()
    (staging.path / "NEW.png").write_bytes(b"new")
    promote_staging(
        staging=staging, target=target, lease_token=token, db_path=db,
    )
    assert (target / "NEW.png").exists()
    prev = base / ".prev"
    assert prev.exists()
    assert any("2026-04-15" in p.name for p in prev.iterdir())


def test_promote_aborts_when_lease_revoked(tmp_path: Path):
    """Spec §5.7: if the owning run's lease was force-cleared mid-work,
    promote_staging must refuse to rename and leave staging for sweep."""
    from swing.data.repos.pipeline import LeaseRevoked, force_clear
    import pytest

    db = tmp_path / "swing.db"
    token = _seed_running_run(db)
    base = tmp_path / "charts"
    staging = StagingDir(base=base, run_id=1, artifact_type="charts")
    staging.create()
    (staging.path / "AAPL.png").write_bytes(b"x")

    # Force-clear before the worker tries to promote
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        with conn:
            force_clear(conn, run_id=1, error_message="admin cleared")
    finally:
        conn.close()

    target = base / "2026-04-15"
    with pytest.raises(LeaseRevoked):
        promote_staging(
            staging=staging, target=target, lease_token=token, db_path=db,
        )
    # Staging still exists (for recovery sweep); target never created
    assert staging.path.exists()
    assert not target.exists()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/pipeline/staging.py`**

```python
"""Manifest-driven staged promotion (spec §5.7)."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class StagingDir:
    base: Path                # e.g. <charts_dir> or <exports_dir>
    run_id: int
    artifact_type: str        # 'charts' | 'exports'

    @property
    def staging_root(self) -> Path:
        return self.base / ".staging"

    @property
    def path(self) -> Path:
        return self.staging_root / str(self.run_id)

    def create(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path


@dataclass(frozen=True)
class PromoteResult:
    target_path: Path
    manifest_path: Path
    backup_path: Path | None


def promote_staging(
    *, staging: StagingDir, target: Path, lease_token: str, db_path: Path,
    manifest_extras: dict[str, Any] | None = None,
) -> PromoteResult:
    """Atomic swap with manifest + .prev/ backup + in-line lease re-check (spec §5.7).

    Steps:
      1. Write MANIFEST.json into staging
      2. Re-read pipeline_runs for the owning run; if lease_token doesn't match
         OR state != 'running', abort WITHOUT promoting (staging stays for sweep)
      3. If target exists, mv to .prev/<name>-<ts>/
      4. Rename staging dir → target

    This prevents a force-cleared stale worker from overwriting canonical
    artifacts written by the new run.
    """
    from swing.data.db import connect
    from swing.data.repos.pipeline import LeaseRevoked, find_run

    if not staging.path.exists():
        raise RuntimeError(f"staging dir does not exist: {staging.path}")

    manifest = {
        "run_id": staging.run_id,
        "lease_token": lease_token,
        "artifact_type": staging.artifact_type,
        "target_path": str(target),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "artifact_count": sum(1 for _ in staging.path.rglob("*") if _.is_file()),
        **(manifest_extras or {}),
    }
    manifest_path = staging.path / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Lease re-check (spec §5.7 step 2): verify this run still owns the lease
    # IMMEDIATELY before the irreversible rename. A stale worker whose lease was
    # force-cleared aborts here and leaves staging for the recovery sweep.
    conn = connect(db_path)
    try:
        run = find_run(conn, staging.run_id)
        if run is None or run.lease_token != lease_token or run.state != "running":
            raise LeaseRevoked(
                f"run {staging.run_id} lease revoked or state changed "
                f"(state={run.state if run else 'missing'}); aborting promote"
            )
    finally:
        conn.close()

    backup_path: Path | None = None
    if target.exists():
        prev_root = staging.base / ".prev"
        prev_root.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup_path = prev_root / f"{target.name}-{ts}"
        shutil.move(str(target), str(backup_path))

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staging.path), str(target))

    return PromoteResult(
        target_path=target,
        manifest_path=target / "MANIFEST.json",
        backup_path=backup_path,
    )
```

- [ ] **Step 4: Verify** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/staging.py tests/pipeline/test_staging.py
git commit -m "feat(pipeline): manifest-driven staged promotion (spec §5.7)"
```

---

### Task G6: Startup recovery sweep

**Files:**
- Create: `swing/pipeline/recovery.py`
- Create: `tests/pipeline/test_recovery.py`

Run on every pipeline startup before acquiring lease. Reads `.staging/*/MANIFEST.json`, cross-references with `pipeline_runs`, deletes orphans.

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_recovery.py
"""Startup recovery sweep."""
from __future__ import annotations

import json
import time
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import insert_pipeline_run
from swing.pipeline.recovery import sweep_stale_artifacts


def test_deletes_staging_for_dead_run(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    # Insert a pipeline run + finalize it as failed
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts="2026-04-15T10:00:00", trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts="2026-04-15T10:00:00",
            )
            conn.execute("UPDATE pipeline_runs SET state='failed' WHERE id=?", (rid,))
    finally:
        conn.close()

    base = tmp_path / "charts"
    staging = base / ".staging" / str(rid)
    staging.mkdir(parents=True)
    (staging / "MANIFEST.json").write_text(json.dumps({"run_id": rid}), encoding="utf-8")

    result = sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
    )
    assert not staging.exists()
    assert rid in result.deleted_staging_run_ids


def test_keeps_staging_for_active_run(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts="2026-04-15T10:00:00", trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts="2026-04-15T10:00:00",
            )
    finally:
        conn.close()
    base = tmp_path / "charts"
    staging = base / ".staging" / str(rid)
    staging.mkdir(parents=True)
    (staging / "MANIFEST.json").write_text(json.dumps({"run_id": rid}), encoding="utf-8")

    sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
    )
    assert staging.exists()


def test_deletes_old_prev(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    base = tmp_path / "charts"
    prev = base / ".prev" / "2026-01-01-000000"
    prev.mkdir(parents=True)
    # Backdate
    old_ts = time.time() - 8 * 86400
    import os
    os.utime(prev, (old_ts, old_ts))

    sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
    )
    assert not prev.exists()


def test_deletes_manifestless_staging_when_old(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    base = tmp_path / "charts"
    staging = base / ".staging" / "999"  # no DB row, no manifest
    staging.mkdir(parents=True)
    import os
    old_ts = time.time() - 7200  # 2h old
    os.utime(staging, (old_ts, old_ts))

    sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
    )
    assert not staging.exists()


def test_flags_stale_running_heartbeat(tmp_path: Path):
    """Spec §5.6: running runs with old heartbeats must be FLAGGED for operator
    review (not auto-deleted — only force-clear can revoke a lease)."""
    from datetime import datetime, timedelta
    import json
    from swing.data.repos.pipeline import insert_pipeline_run

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        with conn:
            rid, _ = insert_pipeline_run(
                conn, started_ts="2026-04-15T10:00:00", trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=(datetime.now() - timedelta(seconds=600)).isoformat(
                    timespec="seconds"
                ),  # 10 min ago
            )
    finally:
        conn.close()
    base = tmp_path / "charts"
    staging = base / ".staging" / str(rid)
    staging.mkdir(parents=True)
    (staging / "MANIFEST.json").write_text(json.dumps({"run_id": rid}), encoding="utf-8")

    result = sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
        stale_heartbeat_seconds=300,
    )
    assert staging.exists()  # NOT deleted — deletion requires force-clear first
    assert rid in result.flagged_stale_running_runs
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/pipeline/recovery.py`**

```python
"""Startup recovery sweep (spec §5.7)."""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from swing.data.db import connect
from swing.data.repos.pipeline import find_run


@dataclass(frozen=True)
class SweepResult:
    deleted_staging_run_ids: list[int] = field(default_factory=list)
    deleted_prev_paths: list[Path] = field(default_factory=list)
    deleted_orphan_staging_paths: list[Path] = field(default_factory=list)
    flagged_stale_running_runs: list[int] = field(default_factory=list)


def sweep_stale_artifacts(
    *, db_path: Path, artifact_dirs: list[Path],
    prev_retention_days: int = 7, orphan_age_seconds: int = 3600,
    stale_heartbeat_seconds: int = 300,
) -> SweepResult:
    """For each base dir in artifact_dirs, sweep .staging/ and .prev/.

    For .staging/<id>/ with MANIFEST.json:
      - If the owning run is missing or no longer 'running': delete the staging dir.
      - If the owning run is 'running' but heartbeat is older than
        stale_heartbeat_seconds: flag (don't delete — deletion is only safe once
        the run has moved out of 'running' via force-clear; spec §5.6 makes this
        an operator decision).
    For .staging/<id>/ without MANIFEST.json: if older than orphan_age_seconds, delete.
    For .prev/<...>/ older than prev_retention_days: delete.
    """
    result = SweepResult([], [], [], [])
    conn = connect(db_path)
    try:
        for base in artifact_dirs:
            staging_root = base / ".staging"
            if staging_root.exists():
                for d in staging_root.iterdir():
                    if not d.is_dir():
                        continue
                    manifest = d / "MANIFEST.json"
                    if manifest.exists():
                        try:
                            data = json.loads(manifest.read_text(encoding="utf-8"))
                            rid = int(data.get("run_id", 0))
                        except (ValueError, OSError):
                            rid = 0
                        run = find_run(conn, rid) if rid else None
                        if run is None or run.state != "running":
                            shutil.rmtree(d, ignore_errors=True)
                            result.deleted_staging_run_ids.append(rid)
                        else:
                            # Run still 'running' — check heartbeat age
                            hb = run.lease_heartbeat_ts
                            if hb is None:
                                result.flagged_stale_running_runs.append(rid)
                            else:
                                age = (datetime.now() - datetime.fromisoformat(hb)).total_seconds()
                                if age > stale_heartbeat_seconds:
                                    result.flagged_stale_running_runs.append(rid)
                    else:
                        age = time.time() - d.stat().st_mtime
                        if age > orphan_age_seconds:
                            shutil.rmtree(d, ignore_errors=True)
                            result.deleted_orphan_staging_paths.append(d)

            prev_root = base / ".prev"
            if prev_root.exists():
                cutoff = time.time() - prev_retention_days * 86400
                for d in prev_root.iterdir():
                    if d.is_dir() and d.stat().st_mtime < cutoff:
                        shutil.rmtree(d, ignore_errors=True)
                        result.deleted_prev_paths.append(d)
    finally:
        conn.close()
    return result
```

- [ ] **Step 4: Verify** — `python -m pytest tests/pipeline/test_recovery.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/recovery.py tests/pipeline/test_recovery.py
git commit -m "feat(pipeline): startup recovery sweep (.staging + .prev)"
```

---

### Task G7: Pipeline runner (orchestrates 9 spec §5.1 steps)

**Files:**
- Create: `swing/pipeline/runner.py`
- Create: `tests/pipeline/test_runner.py`

The runner is the single function that walks all 9 steps. Each step wraps in `lease.step()` for progress tracking + `lease.status()` to record the per-step outcome. Failures decide what to abort vs continue.

- [ ] **Step 1: Write the failing test**

The runner test is the most integration-heavy in Phase 2. We use heavy monkeypatching to keep it fast.

```python
# tests/pipeline/test_runner.py
"""Pipeline runner: orchestrates 9 steps, records per-step status, aborts on evaluation fail."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import find_run, list_recent_runs
from swing.pipeline.runner import run_pipeline_internal, RunResult
from swing.pipeline.lease import acquire_lease


def _ohlcv(closes=None, end="2026-04-15"):
    closes = closes or [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def test_runner_completes_all_steps(tmp_path: Path, monkeypatch):
    """End-to-end happy path with mocked PriceFetcher + finviz CSV."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = ["No.", "Ticker", "Sector", "Industry", "Country", "Price", "Change",
            "Average Volume", "Relative Volume", "Average True Range",
            "52-Week High", "52-Week Low", "Market Cap"]
    csv.write_text(
        ",".join(cols) + "\n"
        "1,AAPL,Tech,Hardware,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3000000000\n"
        "2,MSFT,Tech,Software,USA,420.0,1.5%,250000,1.2,4.5,440.0,330.0,3500000000\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert isinstance(result, RunResult)
    assert result.state == "complete"

    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.state == "complete"
        assert run.weather_status == "ok"
        assert run.evaluation_status == "ok"
        assert run.watchlist_status == "ok"
        assert run.recommendations_status == "ok"
        assert run.export_status == "ok"
    finally:
        conn.close()


def test_runner_aborts_on_evaluation_fail(tmp_path: Path, monkeypatch):
    """Spec §5.3: evaluation failure => abort. Watchlist/recommendations/charts/export skipped."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    csv = cfg.paths.finviz_inbox_dir / "finviz15Apr2026.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    cols = "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    csv.write_text(cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
                   encoding="utf-8")

    def fail_get(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "QQQ":
            return _ohlcv()
        raise RuntimeError("simulated yfinance outage")

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fail_get)

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "failed"

    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.state == "failed"
        assert run.evaluation_status == "failed"
        assert run.watchlist_status in (None, "skipped")
        assert run.recommendations_status in (None, "skipped")
        assert run.export_status in (None, "skipped")
    finally:
        conn.close()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/pipeline/runner.py`**

This is the largest single file in Phase 2. Implementer should keep each `_step_*` function under ~50 lines and route side effects through repos + Lease.

```python
"""Pipeline runner — orchestrates 9 spec §5.1 steps with lease + staging + recovery."""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from datetime import date as _date, datetime as _dt
from pathlib import Path

from swing.config import Config
from swing.data.db import connect
from swing.data.models import (
    Candidate, EvaluationRun, WatchlistArchiveEntry,
)
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.recommendations import upsert_recommendation
from swing.data.repos.trades import list_open_trades, list_all_exits
from swing.data.repos.cash import list_cash
from swing.data.repos.watchlist import (
    archive_watchlist_entry, list_active_watchlist, upsert_watchlist_entry,
)
from swing.data.repos.weather import get_latest_for_date
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.dates import action_session_for_run, last_completed_session
from swing.evaluation.evaluator import evaluate_batch
from swing.evaluation.rs import load_universe, universe_version_hash
from swing.pipeline.finviz_schema import reject_csv, validate_csv
from swing.pipeline.finviz_select import select_csv, NoFilesError, AmbiguousInboxError
from swing.pipeline.heartbeat import Heartbeat
from swing.pipeline.lease import (
    Lease, acquire_lease, ConcurrentRunBlocked,
)
from swing.pipeline.recovery import sweep_stale_artifacts
from swing.pipeline.staging import StagingDir, promote_staging
from swing.prices import PriceFetcher
from swing.recommendations.build import BuildContext, build_recommendations
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.charts import render_chart, ChartingUnavailable
from swing.rendering.exporter import export_briefing
from swing.trades.equity import current_equity, sizing_equity
from swing.watchlist.service import compute_watchlist_changes

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    run_id: int
    state: str  # 'complete' | 'failed' | 'blocked'
    error_message: str | None


def _b64_chart(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def run_pipeline_internal(*, cfg: Config, trigger: str) -> RunResult:
    """Synchronous pipeline run. Caller owns the process — heartbeat is in this thread."""
    # Step 0: startup recovery sweep
    sweep = sweep_stale_artifacts(
        db_path=cfg.paths.db_path,
        artifact_dirs=[cfg.paths.charts_dir, cfg.paths.exports_dir],
        prev_retention_days=cfg.pipeline.prev_dir_retention_days,
        orphan_age_seconds=cfg.pipeline.staging_orphan_age_seconds,
        stale_heartbeat_seconds=cfg.pipeline.stale_lease_threshold_seconds,
    )
    if sweep.flagged_stale_running_runs:
        # Heartbeat age alone is a suspicion signal, not confirmed staleness.
        # Spec §5.6 requires BOTH heartbeat-stale AND step-progress-stale to
        # warrant force-clear. This log line is informational; operators decide.
        log.warning(
            "sweep: running runs %s have heartbeats older than %ss — "
            "inspect via `swing pipeline list` and consider force-clear "
            "if step-progress is also stale (spec §5.6 two-signal check).",
            sweep.flagged_stale_running_runs,
            cfg.pipeline.stale_lease_threshold_seconds,
        )

    # Step 1a: select Finviz CSV
    try:
        csv_path = select_csv(cfg.paths.finviz_inbox_dir)
    except (NoFilesError, AmbiguousInboxError) as exc:
        log.error("Finviz inbox: %s", exc)
        # Insert a failed run for visibility
        lease_dummy = acquire_lease(
            db_path=cfg.paths.db_path, trigger=trigger,
            data_asof_date=_date.today().isoformat(),
            action_session_date=_date.today().isoformat(),
            block_threshold_seconds=cfg.pipeline.block_if_running_within_seconds,
        )
        lease_dummy.release(state="failed", error_message=str(exc))
        return RunResult(run_id=lease_dummy.run_id, state="failed", error_message=str(exc))

    # Step 1b: validate CSV
    val = validate_csv(csv_path)
    if not val.is_valid:
        rejected_dir = cfg.paths.finviz_inbox_dir / "rejected"
        reject_csv(csv_path, val, rejected_dir=rejected_dir)
        msg = f"Finviz CSV rejected: {val.reasons}"
        lease_dummy = acquire_lease(
            db_path=cfg.paths.db_path, trigger=trigger,
            data_asof_date=_date.today().isoformat(),
            action_session_date=_date.today().isoformat(),
            block_threshold_seconds=cfg.pipeline.block_if_running_within_seconds,
        )
        lease_dummy.release(state="failed", error_message=msg)
        return RunResult(run_id=lease_dummy.run_id, state="failed", error_message=msg)

    # Resolve dates
    run_now = _dt.now()
    action_session = action_session_for_run(run_now)
    universe = load_universe(cfg.paths.rs_universe_path)
    universe_hash = universe_version_hash(cfg.paths.rs_universe_path)

    # Step 1c: acquire lease
    try:
        lease = acquire_lease(
            db_path=cfg.paths.db_path, trigger=trigger,
            data_asof_date=last_completed_session(run_now).isoformat(),
            action_session_date=action_session.isoformat(),
            block_threshold_seconds=cfg.pipeline.block_if_running_within_seconds,
            finviz_csv_path=str(csv_path),
            rs_universe_version=universe.version,
            rs_universe_hash=universe_hash,
        )
    except ConcurrentRunBlocked as exc:
        log.warning("blocked: %s", exc)
        return RunResult(run_id=0, state="blocked", error_message=str(exc))

    hb = Heartbeat(lease=lease, interval_seconds=cfg.pipeline.heartbeat_interval_seconds)
    hb.start()

    # Each step is wrapped in try/except to record per-step status.
    fetcher = PriceFetcher(cache_dir=cfg.paths.prices_cache_dir)
    eval_run_id = 0
    try:
        # Step 2: weather
        lease.step("weather")
        try:
            from swing.weather.runner import run_weather
            run_weather(
                db_path=cfg.paths.db_path, fetcher=fetcher,
                ticker=cfg.rs.benchmark_ticker, as_of_date=None,
                run_ts=_dt.now().isoformat(timespec="seconds"),
            )
            lease.status(weather_status="ok")
        except Exception as exc:
            log.warning("weather failed: %s", exc)
            lease.status(weather_status="failed")
            # Non-fatal — continue

        # Step 3: evaluate (port from cli.py eval_cmd, simplified)
        lease.step("evaluate")
        try:
            eval_run_id = _step_evaluate(
                cfg=cfg, fetcher=fetcher, csv_path=csv_path,
                universe=universe, universe_hash=universe_hash,
                run_now=run_now, action_session=action_session,
            )
            lease.status(evaluation_status="ok")
        except Exception as exc:
            log.error("evaluation failed: %s", exc)
            lease.status(evaluation_status="failed")
            lease.release(state="failed", error_message=str(exc))
            hb.stop()
            return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))

        # Step 4: watchlist
        lease.step("watchlist")
        try:
            _step_watchlist(cfg=cfg, eval_run_id=eval_run_id,
                            data_asof_date=lease_data_asof(cfg, lease))
            lease.status(watchlist_status="ok")
        except Exception as exc:
            log.warning("watchlist failed: %s", exc)
            lease.status(watchlist_status="failed")

        # Step 5: recommendations
        lease.step("recommendations")
        try:
            _step_recommendations(cfg=cfg, eval_run_id=eval_run_id,
                                   action_session=action_session,
                                   data_asof=lease_data_asof(cfg, lease))
            lease.status(recommendations_status="ok")
        except Exception as exc:
            log.warning("recommendations failed: %s", exc)
            lease.status(recommendations_status="failed")

        # Step 6: charts
        lease.step("charts")
        chart_paths: dict[str, Path] = {}
        try:
            chart_paths = _step_charts(
                cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                data_asof=lease_data_asof(cfg, lease), fetcher=fetcher,
            )
            lease.status(charts_status="ok")
        except ChartingUnavailable:
            lease.status(charts_status="skipped")
        except Exception as exc:
            log.warning("charts failed: %s", exc)
            lease.status(charts_status="failed")

        # Step 7: export
        lease.step("export")
        try:
            _step_export(cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                         action_session=action_session,
                         data_asof=lease_data_asof(cfg, lease),
                         chart_paths=chart_paths)
            lease.status(export_status="ok")
        except Exception as exc:
            log.warning("export failed: %s", exc)
            lease.status(export_status="failed")

        # Step 8: complete
        lease.step("complete")
        lease.release(state="complete")
    finally:
        hb.stop()

    return RunResult(run_id=lease.run_id, state="complete", error_message=None)


def lease_data_asof(cfg: Config, lease: Lease) -> str:
    """Read back data_asof_date from the pipeline_runs row (single source of truth)."""
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT data_asof_date FROM pipeline_runs WHERE id=?", (lease.run_id,)
        ).fetchone()
        return row[0]
    finally:
        conn.close()


def _step_evaluate(
    *, cfg, fetcher, csv_path: Path, universe, universe_hash: str,
    run_now: _dt, action_session: _date,
) -> int:
    """Port of cli.py eval_cmd minus argparse — returns evaluation_run_id."""
    import pandas as pd
    finviz_df = pd.read_csv(csv_path)
    if "Ticker" not in finviz_df.columns:
        raise ValueError(f"finviz CSV missing 'Ticker' column: {list(finviz_df.columns)}")
    tickers = finviz_df["Ticker"].dropna().astype(str).str.upper().tolist()

    # SPY benchmark
    spy_return = 0.0
    spy_df = fetcher.get(cfg.rs.benchmark_ticker, lookback_days=365, as_of_date=None)
    spy_closes = spy_df["Close"]
    weeks = cfg.rs.horizon_weeks
    if len(spy_closes) > weeks * 5:
        bars = weeks * 5
        spy_return = float((spy_closes.iloc[-1] / spy_closes.iloc[-bars - 1]) - 1)

    returns_12w: dict[str, float] = {}
    ohlcv_by_ticker: dict[str, "pd.DataFrame"] = {}
    error_tickers: list[str] = []
    bars_needed = cfg.rs.horizon_weeks * 5
    for t in tickers:
        try:
            df = fetcher.get(t, lookback_days=400, as_of_date=None)
            ohlcv_by_ticker[t] = df
            closes = df["Close"]
            if len(closes) > bars_needed:
                returns_12w[t] = float((closes.iloc[-1] / closes.iloc[-bars_needed - 1]) - 1)
        except Exception:
            error_tickers.append(t)
    for t in universe.tickers:
        if t in returns_12w:
            continue
        try:
            df = fetcher.get(t, lookback_days=120, as_of_date=None)
            closes = df["Close"]
            if len(closes) > bars_needed:
                returns_12w[t] = float((closes.iloc[-1] / closes.iloc[-bars_needed - 1]) - 1)
        except Exception:
            pass

    batch = BatchContext(
        returns_12w_by_ticker=returns_12w,
        universe_tickers=universe.tickers,
        universe_version=universe.version,
        universe_hash=universe_hash,
        spy_return_12w=spy_return,
    )

    max_dates = [df.index.max() for df in ohlcv_by_ticker.values() if not df.empty]
    if max_dates:
        data_asof = max(max_dates).date()
    else:
        data_asof = last_completed_session(run_now)

    # Compute sizing-basis equity so risk_feasibility (evaluation) and
    # recommendations sizing agree. Using realized equity + sizing floor matches legacy.
    eq_conn = connect(cfg.paths.db_path)
    try:
        sizing_eq = sizing_equity(
            real_equity=current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=list_all_exits(eq_conn),
                cash_movements=list_cash(eq_conn),
            ),
            floor=cfg.account.risk_equity_floor,
        )
    finally:
        eq_conn.close()

    excluded = set(cfg.etf_exclusion.manual_block)
    excluded_tickers: list[str] = []
    contexts: list[CandidateContext] = []
    for t in tickers:
        if t in excluded:
            excluded_tickers.append(t)
            continue
        if t not in ohlcv_by_ticker:
            continue
        contexts.append(CandidateContext(
            ticker=t, ohlcv=ohlcv_by_ticker[t], config=cfg,
            batch=batch, market=MarketContext(),
            current_equity=sizing_eq,
        ))

    candidates = evaluate_batch(contexts)
    for t in excluded_tickers:
        candidates.append(Candidate(
            ticker=t, bucket="excluded",
            close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="ETF/fund blocklist", criteria=(),
        ))
    for t in error_tickers:
        candidates.append(Candidate(
            ticker=t, bucket="error",
            close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="OHLCV fetch failed", criteria=(),
        ))

    conn = connect(cfg.paths.db_path)
    run = EvaluationRun(
        id=None, run_ts=run_now.isoformat(timespec="seconds"),
        data_asof_date=data_asof.isoformat(),
        action_session_date=action_session.isoformat(),
        finviz_csv_path=str(csv_path),
        tickers_evaluated=len(candidates),
        aplus_count=sum(1 for c in candidates if c.bucket == "aplus"),
        watch_count=sum(1 for c in candidates if c.bucket == "watch"),
        skip_count=sum(1 for c in candidates if c.bucket == "skip"),
        excluded_count=len(excluded_tickers), error_count=len(error_tickers),
        rs_universe_version=universe.version, rs_universe_hash=universe_hash,
    )
    try:
        with conn:
            run_id = insert_evaluation_run(conn, run)
            insert_candidates(conn, run_id, candidates)
    finally:
        conn.close()
    return run_id


def _step_watchlist(*, cfg, eval_run_id: int, data_asof_date: str) -> None:
    from swing.data.repos.candidates import fetch_candidates_for_run
    conn = connect(cfg.paths.db_path)
    try:
        prior = list_active_watchlist(conn)
        candidates = fetch_candidates_for_run(conn, eval_run_id)
        delta = compute_watchlist_changes(
            prior=prior, today_candidates=candidates,
            data_asof_date=data_asof_date,
        )
        with conn:
            for entry in delta.adds:
                upsert_watchlist_entry(conn, entry)
            for entry in delta.requalifies:
                upsert_watchlist_entry(conn, entry)
            for entry in delta.streak_increments:
                upsert_watchlist_entry(conn, entry)
            for archive in delta.removes:
                archive_watchlist_entry(conn, archive)
    finally:
        conn.close()


def _step_recommendations(*, cfg, eval_run_id: int,
                           action_session, data_asof: str) -> None:
    from swing.data.repos.candidates import fetch_candidates_for_run
    conn = connect(cfg.paths.db_path)
    try:
        candidates = fetch_candidates_for_run(conn, eval_run_id)
        watchlist = list_active_watchlist(conn)
        equity = current_equity(
            starting_equity=cfg.account.starting_equity,
            exits=list_all_exits(conn), cash_movements=list_cash(conn),
        )
        sized_eq = sizing_equity(real_equity=equity, floor=cfg.account.risk_equity_floor)
        ctx = BuildContext(
            evaluation_run_id=eval_run_id, data_asof_date=data_asof,
            action_session_date=action_session.isoformat(),
            current_equity=sized_eq,
            max_risk_pct=cfg.risk.max_risk_pct,
            position_pct_cap=cfg.sizing.position_pct_cap,
            near_trigger_above_pct=cfg.near_trigger.above_pct,
            near_trigger_below_pct=cfg.near_trigger.below_pct,
        )
        recs = build_recommendations(
            ctx=ctx,
            today_aplus=[c for c in candidates if c.bucket == "aplus"],
            prior_watchlist=watchlist,
        )
        with conn:
            for r in recs:
                upsert_recommendation(conn, r)
    finally:
        conn.close()


def _step_charts(*, cfg, lease: Lease, eval_run_id: int, data_asof: str,
                  fetcher: PriceFetcher) -> dict[str, Path]:
    """Render charts for A+ + top-N near-trigger watchlist via staging."""
    from swing.data.repos.candidates import fetch_candidates_for_run
    conn = connect(cfg.paths.db_path)
    try:
        candidates = fetch_candidates_for_run(conn, eval_run_id)
        watchlist = list_active_watchlist(conn)
    finally:
        conn.close()

    aplus = [c for c in candidates if c.bucket == "aplus"]
    near_watch = sorted(
        [w for w in watchlist if w.entry_target and w.last_close],
        key=lambda w: abs((w.last_close - w.entry_target) / w.entry_target),
    )[:cfg.pipeline.chart_top_n_watch]

    targets = [(c.ticker, c.pivot or 0.0, c.initial_stop or 0.0) for c in aplus]
    targets.extend([(w.ticker, w.entry_target, w.initial_stop_target or 0.0) for w in near_watch])

    base = cfg.paths.charts_dir
    staging = StagingDir(base=base, run_id=lease.run_id, artifact_type="charts")
    staging.create()
    out_paths: dict[str, Path] = {}
    for ticker, pivot, stop in targets:
        try:
            ohlcv = fetcher.get(ticker, lookback_days=200, as_of_date=None)
        except Exception:
            continue
        path = render_chart(
            ticker=ticker, ohlcv=ohlcv, pivot=pivot, stop=stop,
            output_path=staging.path / f"{ticker}.png",
        )
        if path is not None:
            out_paths[ticker] = path
    promote = promote_staging(
        staging=staging, target=base / data_asof,
        lease_token=lease.token, db_path=cfg.paths.db_path,
        manifest_extras={"data_asof_date": data_asof},
    )
    # Re-resolve paths to canonical
    return {t: promote.target_path / f"{t}.png" for t in out_paths}


def _step_export(*, cfg, lease: Lease, eval_run_id: int, action_session,
                  data_asof: str, chart_paths: dict[str, Path]) -> None:
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.recommendations import list_for_session
    conn = connect(cfg.paths.db_path)
    try:
        candidates = fetch_candidates_for_run(conn, eval_run_id)
        recs = list_for_session(conn, action_session.isoformat())
        watchlist = list_active_watchlist(conn)
        weather = get_latest_for_date(conn, data_asof, ticker=cfg.rs.benchmark_ticker)
        trades = list_open_trades(conn)
        equity = current_equity(
            starting_equity=cfg.account.starting_equity,
            exits=list_all_exits(conn), cash_movements=list_cash(conn),
        )
    finally:
        conn.close()

    inputs = BriefingInputs(
        action_session_date=action_session.isoformat(),
        data_asof_date=data_asof,
        generated_at=_dt.now().isoformat(timespec="seconds"),
        weather=weather, weather_is_stale=(weather is None),
        equity=equity, open_count=len(trades),
        soft_warn=cfg.position_limits.soft_warn_open,
        hard_cap=cfg.position_limits.hard_cap_open,
        last_pipeline_ts=_dt.now().isoformat(timespec="seconds"),
        pipeline_is_stale=False, current_session_match=True,
        recommendations=recs, open_trades=trades,
        open_trade_advisories={}, open_trade_last_prices={},
        watchlist=watchlist, watchlist_last_prices={},
        candidates_by_ticker={c.ticker: c for c in candidates},
        chart_b64s={t: _b64_chart(p) for t, p in chart_paths.items()},
        near_trigger_above_pct=cfg.near_trigger.above_pct,
        near_trigger_below_pct=cfg.near_trigger.below_pct,
    )
    vm = build_briefing_view_model(inputs)

    # Stage export then promote
    base = cfg.paths.exports_dir
    staging = StagingDir(base=base, run_id=lease.run_id, artifact_type="exports")
    staging.create()
    export_briefing(
        vm=vm, out_dir=staging.path,
        chart_files=chart_paths,
        size_cap_kb=cfg.export.size_cap_kb,
        retain_markdown_sibling=cfg.export.retain_markdown_sibling,
    )
    promote_staging(
        staging=staging, target=base / action_session.isoformat(),
        lease_token=lease.token, db_path=cfg.paths.db_path,
        manifest_extras={
            "data_asof_date": data_asof,
            "action_session_date": action_session.isoformat(),
        },
    )

    # Retention post-step (spec §6.4): compress exports older than N days.
    # Intentionally NOT lease-fenced — retention is idempotent (zipping a
    # folder into <YYYY-MM>.zip and deleting the folder is the same operation
    # regardless of which worker runs it; subsequent workers see the already-
    # archived state and become no-ops). A force-cleared worker running this
    # step just does the housekeeping the next worker would have done.
    from swing.rendering.retention import archive_old_exports
    archive_old_exports(
        exports_dir=cfg.paths.exports_dir,
        retention_days=cfg.export.retention_days,
    )
```

- [ ] **Step 4: Verify** — `python -m pytest tests/pipeline/test_runner.py -v` → 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_runner.py
git commit -m "feat(pipeline): runner orchestrates 9 spec §5.1 steps"
```

---

### Task G8: Public entry point

**Files:**
- Modify: `swing/pipeline/__init__.py` — expose `run_pipeline`

- [ ] **Step 1: Update `swing/pipeline/__init__.py`**

```python
"""Public entry point for the nightly pipeline.

Usage from CLI: `python -m swing.cli pipeline run`
Usage from code: `from swing.pipeline import run_pipeline; run_pipeline(cfg=...)`
"""
from __future__ import annotations

from swing.pipeline.runner import RunResult, run_pipeline_internal

__all__ = ["RunResult", "run_pipeline"]


def run_pipeline(*, cfg, trigger: str = "manual") -> RunResult:
    return run_pipeline_internal(cfg=cfg, trigger=trigger)
```

- [ ] **Step 2: Commit**

```bash
git add swing/pipeline/__init__.py
git commit -m "feat(pipeline): expose run_pipeline as the package public entry"
```

---

### Task G9: CLI subcommands — pipeline run/list/force-clear

**Files:**
- Modify: `swing/cli.py` — add `pipeline` Click group
- Create: `tests/cli/test_cli_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_cli_pipeline.py
"""CLI: swing pipeline run / list / force-clear."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    return runner, cfg_path, project


def test_pipeline_run_with_csv_arg(tmp_path: Path, monkeypatch):
    runner, cfg, project = _setup(tmp_path)
    csv = project / "data" / "finviz-inbox" / "finviz15Apr2026.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    cols = "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    csv.write_text(cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
                   encoding="utf-8")

    closes = [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end="2026-04-15", periods=260)
    df = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 260,
    }, index=idx)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: df,
    )

    r = runner.invoke(main, ["--config", str(cfg), "pipeline", "run"])
    assert r.exit_code == 0, r.output
    assert "complete" in r.output.lower() or "run id" in r.output.lower()


def test_pipeline_list_shows_recent_runs(tmp_path: Path):
    runner, cfg, _ = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "pipeline", "list"])
    assert r.exit_code == 0
    # Empty list → no error
    assert "no runs" in r.output.lower() or "id" in r.output.lower()


def test_force_clear_rejects_fresh_run(tmp_path: Path):
    """Spec §5.6: force-clear must refuse when run is not two-signal-stale."""
    from swing.data.db import ensure_schema
    from swing.pipeline.lease import acquire_lease

    runner, cfg_path, _ = _setup(tmp_path)
    from swing.config import load
    cfg = load(cfg_path)
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    try:
        r = runner.invoke(main, [
            "--config", str(cfg_path), "pipeline", "force-clear", str(lease.run_id),
        ], input="y\n")
        assert r.exit_code != 0
        assert "staleness" in r.output.lower()
    finally:
        lease.release(state="complete")


def test_force_clear_bypass_works(tmp_path: Path):
    """--bypass-staleness-check allows clearing fresh run."""
    from swing.config import load
    from swing.pipeline.lease import acquire_lease

    runner, cfg_path, _ = _setup(tmp_path)
    cfg = load(cfg_path)
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    r = runner.invoke(main, [
        "--config", str(cfg_path), "pipeline", "force-clear",
        str(lease.run_id), "--bypass-staleness-check",
    ], input="y\n")
    assert r.exit_code == 0, r.output
    assert "force-cleared" in r.output.lower()
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Add `pipeline` Click group to `swing/cli.py`**

```python
@main.group("pipeline")
def pipeline_group() -> None:
    """Nightly orchestrator: run, list, force-clear."""


@pipeline_group.command("run")
@click.option("--manual", is_flag=True, help="Mark as a manual (vs scheduled) run")
@click.pass_context
def pipeline_run_cmd(ctx, manual):
    """Run the nightly pipeline."""
    from swing.pipeline import run_pipeline
    cfg = ctx.obj["config"]
    result = run_pipeline(cfg=cfg, trigger="manual" if manual else "scheduled")
    click.echo(f"Run id {result.run_id}: state={result.state}")
    if result.error_message:
        click.echo(f"Error: {result.error_message}", err=True)
    if result.state == "blocked":
        ctx.exit(2)
    if result.state == "failed":
        ctx.exit(1)


@pipeline_group.command("list")
@click.option("--limit", type=int, default=10)
@click.pass_context
def pipeline_list_cmd(ctx, limit):
    """List recent pipeline runs."""
    from swing.data.db import connect
    from swing.data.repos.pipeline import list_recent_runs
    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        runs = list_recent_runs(conn, limit=limit)
    finally:
        conn.close()
    if not runs:
        click.echo("(no runs)")
        return
    click.echo(f"{'ID':>4} {'State':<14} {'Started':<19} {'Session':<10} {'Step':<14}")
    for r in runs:
        click.echo(
            f"{r.id:>4} {r.state:<14} {r.started_ts:<19} "
            f"{r.action_session_date:<10} {(r.current_step or ''):<14}"
        )


@pipeline_group.command("force-clear")
@click.argument("run_id", type=int)
@click.option("--reason", default="admin force clear")
@click.option("--bypass-staleness-check", is_flag=True,
              help="Skip the two-signal staleness check (use with care)")
@click.pass_context
def pipeline_force_clear_cmd(ctx, run_id, reason, bypass_staleness_check):
    """Force-clear a stuck pipeline run (revokes its lease).

    Spec §5.6 requires TWO signals for staleness: heartbeat age AND step-progress
    age must BOTH exceed their thresholds. Only then is force-clear allowed.
    Use --bypass-staleness-check to override (e.g. to clear a crashed run whose
    heartbeat thread outlived the main loop).
    """
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.data.repos.pipeline import find_run, force_clear

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
        if run is None:
            raise click.ClickException(f"run {run_id} not found")
        if run.state != "running":
            raise click.ClickException(
                f"run {run_id} not in 'running' state (currently {run.state})"
            )

        # Two-signal staleness check (spec §5.6)
        now = _dt.now()
        heartbeat_age = float("inf")
        step_age = float("inf")
        if run.lease_heartbeat_ts:
            heartbeat_age = (now - _dt.fromisoformat(run.lease_heartbeat_ts)).total_seconds()
        if run.last_step_progress_ts:
            step_age = (now - _dt.fromisoformat(run.last_step_progress_ts)).total_seconds()
        hb_stale = heartbeat_age > cfg.pipeline.stale_lease_threshold_seconds
        step_stale = step_age > cfg.pipeline.stale_step_threshold_seconds
        is_stale = hb_stale and step_stale

        if not is_stale and not bypass_staleness_check:
            raise click.ClickException(
                f"Run {run_id} does not meet staleness threshold "
                f"(heartbeat age {heartbeat_age:.0f}s vs "
                f"{cfg.pipeline.stale_lease_threshold_seconds}s; "
                f"step-progress age {step_age:.0f}s vs "
                f"{cfg.pipeline.stale_step_threshold_seconds}s). "
                "Spec §5.6 requires BOTH signals to be stale. "
                "Use --bypass-staleness-check to override."
            )

        click.confirm(
            f"Force-clear run {run_id} (state={run.state}, "
            f"heartbeat_age={heartbeat_age:.0f}s, step_age={step_age:.0f}s)? "
            "Any still-live worker loses its lease and cannot commit further writes.",
            abort=True,
        )
        with conn:
            force_clear(conn, run_id=run_id,
                        error_message=f"{reason} at {now.isoformat(timespec='seconds')}")
    finally:
        conn.close()
    click.echo(f"Run {run_id} force-cleared.")
```

- [ ] **Step 4: Verify** — `python -m pytest tests/cli/test_cli_pipeline.py -v` → 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/cli/test_cli_pipeline.py
git commit -m "feat(cli): add `swing pipeline run|list|force-clear`"
```

---

## Sub-Phase H — RS Universe Refresh + E2E + Concurrency

### Task H1: `swing rs-universe refresh` CLI

**Files:**
- Create: `swing/evaluation/rs_refresh.py` — fetch source membership, write versioned file, snapshot prior
- Modify: `swing/cli.py` — add `rs-universe refresh`
- Create: `tests/cli/test_cli_rs_universe.py`

Manual quarterly refresh per spec §4.1. Source defaults to "spx_ndx" (S&P 500 + NASDAQ-100 union, deduped). Always writes a new version header `# version: YYYY-MM-DD-N` and snapshots the previous file.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_cli_rs_universe.py
"""CLI: swing rs-universe refresh — versioned regen + prior snapshot."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def test_refresh_creates_versioned_file(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    # Stub the source fetch
    monkeypatch.setattr(
        "swing.evaluation.rs_refresh.fetch_source_tickers",
        lambda source: ["AAPL", "MSFT", "NVDA", "GOOG"],
    )

    r = runner.invoke(main, [
        "--config", str(cfg), "rs-universe", "refresh", "--source", "spx_ndx",
    ])
    assert r.exit_code == 0, r.output

    universe_path = project / "reference" / "rs-universe.csv"
    assert universe_path.exists()
    content = universe_path.read_text(encoding="utf-8")
    assert "# version: 2026-04-17-" in content  # current date prefix
    assert "AAPL" in content


def test_refresh_snapshots_prior(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)  # creates initial rs-universe.csv

    monkeypatch.setattr(
        "swing.evaluation.rs_refresh.fetch_source_tickers",
        lambda source: ["AAPL", "MSFT"],
    )
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    # Run refresh
    runner.invoke(main, ["--config", str(cfg), "rs-universe", "refresh", "--source", "spx_ndx"])

    # Prior snapshot present
    snapshots = list((project / "reference").glob("rs-universe-*.csv"))
    assert len(snapshots) >= 1
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Implement `swing/evaluation/rs_refresh.py`**

```python
"""Manual quarterly RS universe refresh (spec §4.1)."""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pandas as pd


def fetch_source_tickers(source: str) -> list[str]:
    """Default source: 'spx_ndx' = union of S&P 500 + NASDAQ-100 from Wikipedia."""
    if source == "spx_ndx":
        return _fetch_spx_ndx()
    raise ValueError(f"unknown source: {source}")


def _fetch_spx_ndx() -> list[str]:
    """Fetch S&P 500 + NASDAQ-100 from Wikipedia (mimics Phase 1 task 12)."""
    import urllib.request
    from io import StringIO

    headers = {"User-Agent": "Mozilla/5.0"}
    spx_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    ndx_url = "https://en.wikipedia.org/wiki/Nasdaq-100"

    req = urllib.request.Request(spx_url, headers=headers)
    with urllib.request.urlopen(req) as r:
        spx_html = r.read().decode("utf-8")
    spx_tables = pd.read_html(StringIO(spx_html))
    spx = spx_tables[0]["Symbol"].astype(str).str.replace(".", "-").tolist()

    req = urllib.request.Request(ndx_url, headers=headers)
    with urllib.request.urlopen(req) as r:
        ndx_html = r.read().decode("utf-8")
    ndx_tables = pd.read_html(StringIO(ndx_html))
    ndx_table = next(
        t for t in ndx_tables if "Ticker" in t.columns or "Symbol" in t.columns
    )
    col = "Ticker" if "Ticker" in ndx_table.columns else "Symbol"
    ndx = ndx_table[col].astype(str).str.replace(".", "-").tolist()

    return sorted(set(spx) | set(ndx))


def _next_version_for(today: date, dest: Path) -> str:
    """Date-based version with -N suffix incremented if today already exists."""
    n = 1
    if dest.exists():
        head = dest.read_text(encoding="utf-8").splitlines()[0]
        if head.startswith("# version:") and today.isoformat() in head:
            try:
                old_n = int(head.rsplit("-", 1)[-1])
                n = old_n + 1
            except ValueError:
                n = 2
    return f"{today.isoformat()}-{n}"


def refresh_rs_universe(
    *, dest: Path, source: str = "spx_ndx", today: date | None = None,
) -> str:
    """Regenerate dest from source. Snapshots prior file. Returns the new version string."""
    today = today or date.today()
    tickers = fetch_source_tickers(source)
    new_version = _next_version_for(today, dest)

    # Snapshot prior
    if dest.exists():
        prior_head = dest.read_text(encoding="utf-8").splitlines()[0]
        if prior_head.startswith("# version: "):
            prior_version = prior_head.split(":", 1)[1].strip()
            snapshot = dest.parent / f"rs-universe-{prior_version}.csv"
            shutil.copy2(dest, snapshot)

    dest.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join([
        f"# version: {new_version}",
        f"# source: {source}",
        "# columns: ticker",
        "ticker",
        *tickers,
        "",
    ])
    dest.write_text(body, encoding="utf-8")
    return new_version
```

- [ ] **Step 4: Add `rs-universe` Click group to `swing/cli.py`**

```python
@main.group("rs-universe")
def rs_universe_group() -> None:
    """RS reference universe management."""


@rs_universe_group.command("refresh")
@click.option("--source", default="spx_ndx",
              help="Source identifier (default: spx_ndx = SPX + NASDAQ-100)")
@click.pass_context
def rs_universe_refresh_cmd(ctx, source):
    """Regenerate the RS reference universe from source. Snapshots the prior file."""
    from swing.evaluation.rs_refresh import refresh_rs_universe
    cfg = ctx.obj["config"]
    new_version = refresh_rs_universe(dest=cfg.paths.rs_universe_path, source=source)
    click.echo(f"RS universe refreshed: version {new_version}")
    click.echo(f"  Path: {cfg.paths.rs_universe_path}")
    click.echo(f"  Prior snapshot saved alongside")
```

- [ ] **Step 5: Verify** — `python -m pytest tests/cli/test_cli_rs_universe.py -v` → 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/evaluation/rs_refresh.py swing/cli.py tests/cli/test_cli_rs_universe.py
git commit -m "feat(cli): add `swing rs-universe refresh` (manual quarterly regen)"
```

---

### Task H2: End-to-end smoke test against real Finviz CSV

**Files:**
- Create: `tests/pipeline/test_e2e.py`

Slow-marked; uses one of the real Finviz CSVs from `tests/fixtures/finviz/`. Stubs PriceFetcher with synthetic OHLCV (so test runs fast) but exercises the full 9-step pipeline end-to-end and verifies all expected DB rows + filesystem outputs.

- [ ] **Step 1: Write the test**

```python
# tests/pipeline/test_e2e.py
"""End-to-end pipeline smoke test (slow-marked)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from swing.config import load
from swing.data.db import ensure_schema
from swing.data.repos.pipeline import find_run
from swing.pipeline import run_pipeline
from tests.cli.test_cli_eval import _minimal_config


pytestmark = pytest.mark.slow


@pytest.fixture
def real_finviz_csv():
    """Use the smallest real Finviz fixture (14Apr2026: 62 tickers)."""
    src = Path(__file__).parent.parent / "fixtures" / "finviz" / "finviz14Apr2026.csv"
    if not src.exists():
        pytest.skip(f"fixture not found: {src}")
    return src


def test_pipeline_e2e_smoke(tmp_path: Path, real_finviz_csv, monkeypatch):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    # Place finviz fixture in inbox
    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(real_finviz_csv, inbox / real_finviz_csv.name)

    # Synthetic OHLCV for every ticker
    closes = [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end="2026-04-14", periods=260)
    df = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 260,
    }, index=idx)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: df,
    )

    result = run_pipeline(cfg=cfg, trigger="manual")
    assert result.state == "complete", result.error_message

    # Verify DB rows
    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.weather_status == "ok"
        assert run.evaluation_status == "ok"
        assert run.watchlist_status == "ok"
        assert run.recommendations_status == "ok"
        assert run.export_status == "ok"

        eval_rows = conn.execute("SELECT COUNT(*) FROM evaluation_runs").fetchone()[0]
        assert eval_rows == 1
        cand_rows = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        assert cand_rows >= 60  # ~62 tickers in the fixture
        weather_rows = conn.execute("SELECT COUNT(*) FROM weather_runs").fetchone()[0]
        assert weather_rows == 1
    finally:
        conn.close()

    # Verify filesystem outputs
    assert (cfg.paths.exports_dir / run.action_session_date / "briefing.html").exists()
```

- [ ] **Step 2: Verify** — `python -m pytest tests/pipeline/test_e2e.py -v -m slow` → PASS (or `SKIPPED` if fixture missing — but we know fixtures from Phase 1 are present).

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_e2e.py
git commit -m "test(pipeline): E2E smoke against real Finviz CSV (slow)"
```

---

### Task H3: Concurrent-run rejection test

**Files:**
- Create: `tests/pipeline/test_concurrent.py`

Simulates a second `run_pipeline` call while the first holds an active lease (no real concurrency — just acquire two leases against the same DB).

- [ ] **Step 1: Write the test**

```python
# tests/pipeline/test_concurrent.py
"""Concurrent run rejection."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.pipeline.lease import ConcurrentRunBlocked, acquire_lease


def test_second_acquire_blocked(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    first = acquire_lease(
        db_path=db, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    try:
        with pytest.raises(ConcurrentRunBlocked):
            acquire_lease(
                db_path=db, trigger="manual",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                block_threshold_seconds=120,
            )
    finally:
        first.release(state="complete")


def test_acquire_succeeds_after_release(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    first = acquire_lease(
        db_path=db, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    first.release(state="complete")
    second = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    second.release(state="complete")


def test_concurrent_acquire_exactly_one_wins(tmp_path: Path):
    """True-contention test: N threads racing acquire_lease against the same DB.
    Each thread HOLDS the lease (doesn't release) so the invariant "exactly one
    winner among simultaneous attempters" can actually be observed. Validates
    BEGIN IMMEDIATE + ux_pipeline_one_running partial unique index (migration 0003)."""
    import threading

    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    winners: list = []
    blocked_count = [0]
    results_lock = threading.Lock()
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()  # maximize contention
        try:
            lease = acquire_lease(
                db_path=db, trigger="manual",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
            )
            with results_lock:
                winners.append(lease)
            # HOLD — do not release here, so other threads see contention
        except ConcurrentRunBlocked:
            with results_lock:
                blocked_count[0] += 1

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(winners) == 1, (
        f"expected exactly one winner, got {len(winners)}"
    )
    assert blocked_count[0] == 7, (
        f"expected 7 blocked, got {blocked_count[0]}"
    )
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs WHERE state='running'"
        ).fetchone()[0]
        assert rows == 1
    finally:
        conn.close()
    winners[0].release(state="complete")
```

- [ ] **Step 2: Verify** — `python -m pytest tests/pipeline/test_concurrent.py -v` → 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_concurrent.py
git commit -m "test(pipeline): concurrent-run rejection"
```

---

### Task H4: Final regression sweep + Phase 2 acceptance gate

**Files:** none — this is a verification-only task.

- [ ] **Step 1: Run full Phase 1 + Phase 2 fast suite**

```bash
python -m pytest -m "not slow" -v
```

Expected: every test listed in the file map green. Roughly:

- Phase 1 baseline: ~71 tests
- Sub-phase A: ~12 new (db_v3 + 6 repos)
- Sub-phase B: ~9 new (classifier + runner + CLI)
- Sub-phase C: ~21 new (watchlist service + 4 recommendation modules + config)
- Sub-phase D: ~14 new (view models + briefing builder + HTML + MD + exporter; chart test is slow)
- Sub-phase E: ~28 new (equity + entry + exit + stop_adjust + advisory + CLI)
- Sub-phase F: ~14 new (stats + flags + tos + CLI)
- Sub-phase G: ~16 new (finviz schema/select + lease + heartbeat + staging + recovery + runner + CLI)
- Sub-phase H: ~6 new (rs-universe + concurrent)

Total Phase 2 fast tests: ~120 new. Combined: ~191 fast tests, all green.

- [ ] **Step 2: Run slow tests** (one round, ok if mplfinance/network not present → SKIPPED counts toward acceptance)

```bash
python -m pytest -m slow -v
```

- [ ] **Step 3: Smoke the pipeline against today's real Finviz CSV (manual)**

```bash
# Drop today's CSV into data/finviz-inbox/
swing pipeline run --manual
swing pipeline list --limit 5
```

Expected: a `complete` row + `briefing.html` written to `exports/<action-session>/briefing.html`.

- [ ] **Step 4: Commit acceptance log**

Optional — paste the test output into a commit message:

```bash
git commit --allow-empty -m "chore(phase2): acceptance — full suite green, E2E pipeline verified"
```

---

## Phase 2 Success Criteria

- [ ] Migration 0003 brings DB to `EXPECTED_SCHEMA_VERSION = 3` with all 10 new tables.
- [ ] `swing pipeline run` executes all 9 spec §5.1 steps and writes `pipeline_runs.state='complete'`.
- [ ] `briefing.html` is portable (open in a browser without the server running, all CSS inline).
- [ ] Lease enforcement blocks concurrent runs (test G3 / H3); force-clear revokes the lease (CLI G9, repo A7).
- [ ] Trade entry / exit / stop adjust flow through CLI; every mutation writes a `trade_events` row in the same transaction.
- [ ] 7 stop-advisory rules behave like legacy (test E5).
- [ ] Journal stats: share-weighted R, expectancy, streak match legacy outputs (test F1).
- [ ] TOS reconciliation parses the legacy `2026-04-15-AccountStatement.csv` and reports new cash + unmatched fills (test F3).
- [ ] Watchlist aging is idempotent across re-runs of the same `data_asof_date` (test C1).
- [ ] Startup recovery sweep deletes orphaned `.staging/` and aged `.prev/` (test G6).

---

## Appendix A — Out-of-Plan but Already Done

Checklist of items the spec mentions that are **NOT** Phase 2 work — keep them visible to avoid confusion:

| Item | Where it lives | Phase |
|---|---|---|
| FastAPI app, HTMX routes, dashboard templates | `swing/web/` | 3 |
| Dashboard force-clear button | route + partial in `swing/web/routes/pipeline.py` | 3 |
| Live data refresh (current price for open positions) | route handler caches via PriceFetcher | 3 |
| Legacy data import (`db-migrate --from-legacy`) | one-shot script | 4 |
| Folder archival to `reference/archive/` | one-shot script | 4 |
| Delete legacy `.py` files | scripted final cleanup | 4 |
| Windows `.bat` scripts (`run-pipeline.bat`, `run-web.bat`) | `scripts/` | 4 |
| 20-clean-runs gate to drop `briefing.md` | manual config flip; not a code task | post-Phase 4 |
| `config_revisions` repo + write-site | Used by `/settings` save flow | 3 (Phase 2 creates the table in migration 0003 so Phase 3 isn't schema-blocked, but no repo or writer yet) |
| Live current price for open positions | re-fetched via PriceFetcher on dashboard render | 3 |
| Per-trade advisory inline in briefing.html | requires current price; uses view_model advisory field already present | 3 |
| Populated `watchlist_last_prices` / `flag_tags` | requires live fetch; static export uses last-known | 3 |

**Phase 1 config fixture compat note:** `tests.cli.test_cli_eval._minimal_config` was written in Phase 1 and omits the new Phase 2 sections (`[near_trigger]`, `[stop_advisory]`, `[sizing]`, `[pipeline]`, `[export]`). Phase 2's `load()` fills these via dataclass defaults (Task C6's `test_phase2_defaults_load_when_sections_absent` verifies this). Phase 2 tests can continue to reuse `_minimal_config` unchanged. If a test needs non-default Phase 2 config, it should write its own config inline rather than modify the Phase 1 helper.

---

## Appendix B — Decisions Locked During Planning

1. **Pipeline as a package, not a single file.** Spec §2.3 illustrates `pipeline.py`; this plan splits into `swing/pipeline/{__init__, lease, heartbeat, staging, recovery, runner, finviz_schema, finviz_select}.py`. Justified by spec §2.4: "split when responsibilities multiply."

2. **Watchlist `entry_target` and `initial_stop_target` are FROZEN at first add.** Re-qualify never overwrites. Matches legacy parity (the watchlist is the user's declared trigger, not today's recomputed setup).

3. **`trade_events` is the audit source of truth; `trades` is a convenience projection.** The repo enforces this — there is no public method to mutate `trades` without writing a `trade_events` row in the same transaction.

4. **`daily_recommendations` is idempotent via UPSERT.** Re-running pipeline for the same session updates rows in place; UNIQUE(action_session_date, ticker, recommendation) prevents inflation.

5. **`rs-universe refresh` is manual, not pipeline-triggered.** Survivorship-bias decisions stay visible to the user.

6. **Charts are an optional dep (`pip install -e ".[charts]"`).** Pipeline degrades gracefully (`charts_status='skipped'` + dashboard placeholder).

7. **Briefing markdown lives until 20 clean runs + user signoff.** Post-Phase 4, drop via `[export] retain_markdown_sibling = false` config flip.

8. **CLI subcommands replace the legacy interactive `trade.py` menu.** Each subcommand takes explicit options for scriptability. The legacy interactive flow can be reconstructed in Phase 3 with HTMX.

9. **Pipeline runner is synchronous** — single-threaded for the 9 steps; only the heartbeat is on a background thread. Phase 3's FastAPI route runs `run_pipeline` in a thread pool.

10. **Empty Finviz inbox / ambiguous inbox are HARD failures.** No silent fallback to "yesterday's CSV." The user must fix the inbox or the pipeline doesn't run.

---

## Appendix C — Known Gaps Deferred to Phase 3+

- **Live current price for open positions.** Phase 2 briefing uses `last_close` from the latest evaluation; Phase 3 dashboard re-fetches via PriceFetcher on render. The static `briefing.html` snapshot is "as of pipeline run."
- **`open_trade_advisories` in BriefingInputs is empty.** Phase 2 leaves the per-trade advisory population to Phase 3 (the dashboard will re-call `compute_all_suggestions()` per render with current price). The briefing.html will show open positions without inline advisories — this is a known acceptable gap.
- **`watchlist_last_prices` falls back to `last_close` from prior evaluation.** Live refresh is Phase 3.
- **Per-trade `flag_tags` (TT✓ VCP✓) on watchlist rows.** Computed on demand in Phase 3 from joining the latest candidate row.
- **Behavioral flag examples in briefing.** Currently only journal-review CLI surfaces flags; embedding in briefing.html is Phase 3.

These gaps are intentional — Phase 2 is "headless system parity"; Phase 3 adds live UX.

---
