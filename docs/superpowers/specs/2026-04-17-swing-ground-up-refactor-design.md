# Swing Trading Ground-Up Refactor — Design

**Date:** 2026-04-17
**Status:** Draft for review
**Scope:** Redesign the swing-trading personal tool as a cohesive Python package with a FastAPI+HTMX dashboard, SQLite state, and Minervini-aligned evaluation criteria. Existing ad-hoc scripts (`evaluate_candidates.py`, `trade.py`, `market_weather.py`) are replaced end-to-end.

---

## 1. Why

The current system grew organically into ~250KB of Python spread across three monolithic scripts, with state scattered across CSVs and markdown files intermixed with reference PDFs and worksheets in the project root. It works, but:

- **Reports are unreadable in the CLI.** Tables are markdown (not fixed-width), so columns don't line up when read in a terminal. Today's `report.md` is 55KB with one full criterion table per ticker (91 tables) — the actionable answer is buried.
- **The "what should I do today?" answer isn't front-and-center.** Morning briefing mixes a 25-row watchlist with a single near-trigger name; no explicit action statement ("buy-stop at X for Y shares, risk $Z").
- **Charts exist but aren't embedded.** `evaluate_candidates.py` generates chart PNGs for top A+ names; the briefing links nothing.
- **No narrative.** Criterion pass/fail is mechanical; no 1-2 sentence explanation of why each setup is interesting (VCP stage, base depth, distance to pivot).
- **Monolithic code.** `evaluate_candidates.py` is 110KB, `trade.py` is 121KB. Criteria, price fetching, chart rendering, CSV I/O, and the CLI menu all live in one file each. Changing one rule risks breaking unrelated things. No tests.
- **Ambiguous Minervini alignment.** User treats "Trade Like a Stock Market Wizard" as a reference, but current criteria blend short-MA VCP-style checks without the structural Trend Template filter. A ticker can pass today's criteria while not actually being in a Stage-2 uptrend.
- **Ad-hoc file layout.** Root directory mixes reference PDFs, worksheets, chart PNGs, Python scripts, config, and daily markdown outputs. Duplicate files (`market_weather.md` at root + `weather/<date>.md`).

### Goals (user-prioritized)

1. **Workflow smoothness.** One command starts the dashboard; one page shows today's decisions, watchlist, and open positions; pipeline runs nightly automatically.
2. **Maintainability.** Small focused modules; clear contracts; no single file over ~300 lines; each criterion is independently testable.
3. **Correctness.** Every criterion has a unit test with synthetic fixtures; a golden-file test replays existing Finviz CSVs to lock in behavior during the rewrite; Minervini Trend Template added as an explicit pre-filter.
4. **Data integrity.** SQLite single source of truth. Watchlist, trades, cash, evaluations are tables, not scattered CSVs. Briefings and reports are derived views, not primary state.
5. **Extensibility.** New criteria slot in as new files; new views slot in as new routes/templates; future backtesting layer can read the same SQLite schema.

### Non-goals

- Not a trading-system redesign. Core rules from "The Disciplined Swing Trader" stay; Minervini's Trend Template is added as a pre-filter, not a replacement for VCP tactical criteria.
- Not a multi-broker or real-money automation project. Still EOD, still Thinkorswim manual fills, still Finviz CSV as the universe source.
- Not a backtesting framework. Schema is designed not to preclude one later, but no backtesting code in this refactor.
- Not a mobile app. Desktop browser only.
- Not a public / multi-user service. Localhost only, single user.

---

## 2. Architecture

### 2.1 High-level

```
                 ┌──────────────────────────────────┐
                 │   User's browser (localhost)     │
                 └───────────────▲──────────────────┘
                                 │ HTMX + server-rendered HTML
                 ┌───────────────┴──────────────────┐
                 │     FastAPI app (swing.web)      │
                 │  routes: dashboard, watchlist,   │
                 │  trades, journal, pipeline       │
                 └───┬───────────────────────────┬──┘
                     │ calls                     │ triggers
                     ▼                           ▼
        ┌────────────────────────┐    ┌─────────────────────┐
        │  Business logic        │    │  Pipeline (nightly) │
        │  swing.evaluation,     │    │  swing.pipeline     │
        │  swing.trades,         │    │  weather → evaluate │
        │  swing.journal,        │    │  → watchlist update │
        │  swing.rendering       │    │  → charts           │
        └──────┬─────────────────┘    └──────────┬──────────┘
               │                                 │
               └──────────────┬──────────────────┘
                              ▼
                   ┌──────────────────────┐
                   │  swing.data (repos)  │
                   └──────────┬───────────┘
                              ▼
                   ┌──────────────────────┐
                   │     swing.db         │
                   │  (SQLite, on disk)   │
                   └──────────────────────┘

   Windows Task Scheduler ──► scripts/run-pipeline.bat ──► swing.pipeline
```

### 2.2 Stack

| Layer | Choice | Why |
|---|---|---|
| Web framework | FastAPI | Async-ready, form handling, clean route → function mapping, easy to unit-test routes |
| UI | HTMX + Jinja2 | Server-rendered HTML with targeted DOM swaps for filter/expand/submit. No JS build step. |
| Persistence | SQLite (single `swing.db` file) | Transactional, queryable, schema-enforced, small enough to fit the whole app in one file |
| Price data | yfinance (existing) | No change; wrapped behind `swing.prices` with on-disk cache |
| Charts | matplotlib (existing) | No change; wrapped behind `swing.rendering.charts` |
| CLI | Click | Narrow CLI for rare ops: setup, tos-import, db-migrate |
| Scheduling | Windows Task Scheduler (existing) | No change; triggers a batch file that runs `python -m swing.pipeline` |
| Tests | pytest | Unit + golden-file; fixtures for synthetic OHLCV |

### 2.3 Package layout

```
Swing Trading/
├── swing/                          # the Python package
│   ├── config.py                   # paths, thresholds, weights (loads swing.config.toml)
│   ├── data/
│   │   ├── db.py                   # sqlite3 connection, migrations runner
│   │   ├── models.py               # dataclasses: Trade, Exit, Candidate, Watch, Weather, Cash
│   │   ├── migrations/             # .sql files, run in order
│   │   └── repos/
│   │       ├── trades.py
│   │       ├── exits.py
│   │       ├── watchlist.py
│   │       ├── candidates.py
│   │       ├── cash.py
│   │       └── weather.py
│   ├── prices.py                   # yfinance wrapper + on-disk parquet cache
│   ├── weather.py                  # QQQ → Bullish/Caution/Bearish classifier
│   ├── evaluation/
│   │   ├── evaluator.py            # orchestrates criteria for one ticker
│   │   ├── scoring.py              # bucket into A+ / Watch / Skip
│   │   └── criteria/               # one file per rule
│   │       ├── _base.py            # Criterion protocol + shared helpers
│   │       ├── prior_trend.py
│   │       ├── trend_template.py   # NEW: Minervini 8-point structural gate
│   │       ├── proximity.py        # price within 5% of 20MA
│   │       ├── adr.py
│   │       ├── pullback.py
│   │       ├── tightness.py
│   │       ├── vcp.py              # volume contraction (Minervini-labeled)
│   │       ├── orderliness.py
│   │       └── risk_feasibility.py
│   ├── trades/
│   │   ├── entry.py                # create trade, size, persist
│   │   ├── exit.py                 # partial/full exit, realized P&L, R-multiple
│   │   ├── equity.py               # starting_equity + cash + realized P&L
│   │   └── advisory.py             # 7 stop-advisory rules
│   ├── journal/
│   │   ├── stats.py                # win rate, expectancy, avg W/L in R, streak
│   │   ├── flags.py                # behavioral flags (caution-market trades, etc.)
│   │   └── tos_import.py           # thinkorswim reconciliation
│   ├── rendering/
│   │   ├── briefing.py             # builds BriefingViewModel from state
│   │   ├── report.py               # builds ReportViewModel (eval summary)
│   │   └── charts.py               # matplotlib price chart → PNG bytes
│   ├── pipeline.py                 # nightly orchestrator; CLI entry: python -m swing.pipeline
│   ├── cli.py                      # Click app: setup, tos-import, db-migrate
│   └── web/
│       ├── app.py                  # FastAPI app factory + HTMX static mount
│       ├── routes/
│       │   ├── dashboard.py        # GET /
│       │   ├── watchlist.py        # GET /watchlist, GET /watchlist/{ticker}
│       │   ├── trades.py           # POST /trades/entry, POST /trades/exit
│       │   ├── journal.py          # GET /journal
│       │   └── pipeline.py         # POST /pipeline/run, POST /pipeline/upload-csv
│       ├── templates/              # Jinja2 .html.j2
│       │   ├── base.html.j2
│       │   ├── dashboard.html.j2
│       │   └── partials/           # HTMX swap targets
│       └── static/
│           ├── htmx.min.js
│           └── app.css
├── tests/                          # pytest; mirrors swing/ layout
│   ├── fixtures/
│   │   ├── ohlcv/                  # synthetic OHLCV CSVs for criterion tests
│   │   └── finviz/                 # captured real Finviz CSVs for golden tests
│   ├── evaluation/
│   │   ├── criteria/               # one test_*.py per criterion
│   │   ├── test_evaluator.py
│   │   └── test_golden.py          # replays tests/fixtures/finviz/*.csv vs captured baseline
│   └── ...
├── data/
│   └── finviz-inbox/               # drop Finviz CSVs here; pipeline ingests newest
│       └── rejected/               # schema-failed CSVs quarantined here
├── exports/                        # pipeline-written archival HTML snapshots per date
├── reference/                      # static reference material (moved out of root)
│   ├── books/                      # PDFs: Disciplined Swing Trader, (future) Minervini
│   ├── worksheets/                 # .docx/.xlsx
│   ├── patterns/                   # flag, pennant, tight-channel PNGs
│   └── archive/                    # frozen snapshot of old folders
│       ├── briefings/              # from current briefings/
│       ├── reports/                # from current reports/
│       ├── finviz-screeners/       # from current "finviz screeners/"
│       └── watchlist-snapshots/    # from current watchlist/
├── scripts/
│   ├── run-pipeline.bat            # Windows Task Scheduler target
│   └── run-web.bat                 # double-click to start the dashboard
├── swing.config.toml               # user-editable config (replaces trade_config.json)
├── pyproject.toml                  # deps + package metadata
├── .gitignore                      # if/when git is introduced
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-17-swing-ground-up-refactor-design.md    # this file
```

### 2.4 Architectural invariants

- `swing.web` is the only package that imports FastAPI / Jinja / HTMX concerns.
- `swing.data.repos` is the only package that imports `sqlite3`. All other modules go through repos.
- `swing.evaluation.criteria.*` files are pure functions of a `CandidateContext` (per-ticker `PriceHistory` + batch stats + market context + config); no I/O, no DB access, no network. Cross-sectional concerns (RS rank, ETF exclusion, market weather) reach criteria via `CandidateContext`, not by criteria calling the outside world.
- `swing.rendering.*` builds view models from inputs passed in; it does no I/O. Routes fetch data, call a renderer, render the template. Templates may do presentational formatting (date formats, currency, conditional class names) but no business logic.
- `swing.pipeline` is the only orchestrator — nothing else chains weather→evaluate→watchlist.
- **`swing.db` lives outside the Google Drive folder** — default path `%USERPROFILE%/swing-data/swing.db` (Windows) or `~/swing-data/swing.db` (Unix). The Drive-synced project folder holds code + reference material + exports, never the primary DB. This is a hard constraint, not a preference — Google Drive sync mid-write corrupts SQLite regardless of WAL mode.
- Module size is a guideline (~300 lines). Clear single-purpose modules can exceed it; the trigger to split is multiple responsibilities, not line count.

---

## 3. Data model (SQLite schema)

One DB file at the OS-local path `%USERPROFILE%/swing-data/swing.db` (resolved by `swing.config`; configurable via `swing.config.toml`). **Not inside the Google Drive folder** — see §2.4 invariant.

Schemas applied via forward-only migrations in `swing/data/migrations/*.sql`. **Migrations do not run automatically at app startup.** The app reads the DB's `schema_version` row; if it doesn't match the embedded expected version, the app refuses to start and prints `Run: python -m swing.cli db-migrate`. The CLI `db-migrate` command takes an automatic backup (`swing-data/backups/swing-<timestamp>.db`) before running any migration.

```sql
-- config snapshots (audit trail of threshold changes)
CREATE TABLE config_revisions (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

-- market weather, one row per classifier run (usually nightly)
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
CREATE UNIQUE INDEX ux_weather_asof ON weather_runs(asof_date);

-- evaluation batch (one per pipeline run)
CREATE TABLE evaluation_runs (
  id INTEGER PRIMARY KEY,
  run_ts TEXT NOT NULL,
  data_asof_date TEXT NOT NULL,        -- date of OHLCV bars evaluated
  action_session_date TEXT NOT NULL,   -- session recommendations apply to
  finviz_csv_path TEXT,                -- path to the source Finviz CSV, nullable if re-run
  tickers_evaluated INTEGER NOT NULL,
  aplus_count INTEGER NOT NULL,
  watch_count INTEGER NOT NULL,
  skip_count INTEGER NOT NULL
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
  rs_rank INTEGER,                -- 0-99 when rs_method='universe'; NULL when rs_method='fallback_spy'
  rs_return_12w_vs_spy REAL,      -- raw excess return vs SPY, always populated
  rs_method TEXT NOT NULL CHECK (rs_method IN ('universe','fallback_spy','unavailable')),
  pattern_tag TEXT,               -- e.g., 'HTF', 'VCP-3C', etc.
  notes TEXT,
  UNIQUE(evaluation_run_id, ticker)
);

-- per-criterion result for each candidate row
CREATE TABLE candidate_criteria (
  candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
  criterion_name TEXT NOT NULL,   -- 'prior_trend', 'trend_template', 'tightness', ...
  layer TEXT NOT NULL CHECK (layer IN ('trend_template','vcp','risk')),
  result TEXT NOT NULL CHECK (result IN ('pass','fail','na')),
  value TEXT,                     -- human-readable value
  rule TEXT,                      -- human-readable rule text
  PRIMARY KEY (candidate_id, criterion_name)
);

-- active watchlist — distinct from evaluation history
-- a ticker is on the watchlist until it entered, was archived, or expired
CREATE TABLE watchlist (
  ticker TEXT PRIMARY KEY,
  added_date TEXT NOT NULL,
  last_qualified_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('watch','skip','near_trigger')),
  qualification_count INTEGER NOT NULL DEFAULT 1,
  not_qualified_streak INTEGER NOT NULL DEFAULT 0  -- consecutive runs evaluated but not qualifying; aging trigger (§5.4)
);

-- archive of removed watchlist rows (audit trail)
CREATE TABLE watchlist_archive (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  added_date TEXT NOT NULL,
  removed_date TEXT NOT NULL,
  reason TEXT NOT NULL  -- 'entered', 'expired', 'manual'
);

-- trades
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

-- exits (partials supported)
CREATE TABLE exits (
  id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id),
  exit_date TEXT NOT NULL,
  exit_price REAL NOT NULL,
  shares INTEGER NOT NULL,
  reason TEXT NOT NULL,
  realized_pnl REAL NOT NULL,
  r_multiple REAL NOT NULL,
  notes TEXT
);

-- cash deposits / withdrawals
CREATE TABLE cash_movements (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('deposit','withdraw')),
  amount REAL NOT NULL,
  ref TEXT,
  note TEXT
);

-- trade events (immutable audit log: stop adjustments, note updates, partial info)
-- Supports journaling/provenance; complements the mutable `trades` current-state row.
CREATE TABLE trade_events (
  id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id),
  ts TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('entry','stop_adjust','note','exit','flag')),
  payload_json TEXT NOT NULL,   -- e.g., {"old_stop": 58.77, "new_stop": 62.50, "rationale": "10MA trail"}
  rationale TEXT                -- free-text user rationale, denormalized for easy journal queries
);
CREATE INDEX ix_trade_events_trade ON trade_events(trade_id, ts);

-- daily recommendations (immutable snapshot of what the system said for a given session)
-- Enables reproducibility: even if config changes or logic evolves, history is preserved.
CREATE TABLE daily_recommendations (
  id INTEGER PRIMARY KEY,
  evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id),
  data_asof_date TEXT NOT NULL,        -- data used to generate this recommendation
  action_session_date TEXT NOT NULL,   -- session this recommendation applies to
  ticker TEXT NOT NULL,
  recommendation TEXT NOT NULL,   -- 'today_decision','watchlist_watch','watchlist_skip','near_trigger'
  action_text TEXT,               -- rendered line, e.g. "Buy-stop limit $68.65 · 3 sh · $30 risk"
  entry_target REAL,
  stop_target REAL,
  shares INTEGER,
  risk_dollars REAL,
  risk_pct REAL,
  rationale TEXT,                 -- 1-sentence narrative snapshot
  UNIQUE(action_session_date, ticker, recommendation)
);

-- pipeline runs (run-level audit with state, for concurrency control and observability)
CREATE TABLE pipeline_runs (
  id INTEGER PRIMARY KEY,
  started_ts TEXT NOT NULL,
  finished_ts TEXT,
  trigger TEXT NOT NULL CHECK (trigger IN ('scheduled','manual')),
  data_asof_date TEXT NOT NULL,        -- date of most recent OHLCV bars used (§5.5)
  action_session_date TEXT NOT NULL,   -- next trading session where recommendations apply (§5.5)
  state TEXT NOT NULL CHECK (state IN ('running','complete','failed','blocked','force_cleared')),
  lease_token TEXT NOT NULL,            -- opaque uuid; every write by this run must match the current lease
  lease_heartbeat_ts TEXT,              -- updated every 30s by background thread
  last_step_progress_ts TEXT,           -- updated on every step start/finish by main loop
  current_step TEXT,                    -- one of: lock, validate_csv, weather, evaluate, watchlist, recommendations, charts, export, complete
  weather_status TEXT CHECK (weather_status IN ('ok','failed','skipped')),
  evaluation_status TEXT CHECK (evaluation_status IN ('ok','failed','skipped')),
  watchlist_status TEXT CHECK (watchlist_status IN ('ok','failed','skipped')),
  charts_status TEXT CHECK (charts_status IN ('ok','failed','skipped')),
  rs_universe_version TEXT,          -- hash of reference/rs-universe.csv used this run (§4.1)
  error_message TEXT
);
CREATE INDEX ix_pipeline_runs_state ON pipeline_runs(state);
```

Derived state (equity, open-positions list, journal stats) is computed on demand by SQL queries or small Python helpers; never persisted.

### 3.1 Immutability and audit

- `trades` holds **current state** (mutable: `current_stop`, `status`). Every mutation writes a `trade_events` row first in the same transaction — the row is the audit trail, `trades` is the convenience view.
- `daily_recommendations` is append-only. The dashboard's "Today's decisions" renders from today's rows; history is preserved even if thresholds or criteria change later.
- `candidates` + `candidate_criteria` stay tied to `evaluation_runs` for pipeline-level reproducibility; `daily_recommendations` is the user-facing, stable projection.

---

## 4. Evaluation criteria (Minervini M2)

Two evaluation layers run per ticker. The **Trend Template** layer is the structural gate — a ticker that fails Trend Template cannot be A+ no matter how tight its consolidation. The **VCP** layer is the tactical check — it confirms the pivot is a real coil.

### 4.1 Trend Template layer (8 checks — new)

Sourced from Mark Minervini, "Trade Like a Stock Market Wizard" (public spec; re-verified against the book when the user adds it to `reference/books/`).

| # | Criterion | Rule | File |
|---|---|---|---|
| TT1 | Price above 150MA and 200MA | `close > sma150 and close > sma200` | `criteria/trend_template.py` |
| TT2 | 150MA above 200MA | `sma150 > sma200` | same |
| TT3 | 200MA trending up (≥1 month) | `sma200.iloc[-1] > sma200.iloc[-21]` | same |
| TT4 | 50MA above 150 and 200 | `sma50 > sma150 and sma50 > sma200` | same |
| TT5 | Price above 50MA | `close > sma50` | same |
| TT6 | Price ≥30% above 52-week low | `(close - low_52w) / low_52w >= 0.30` | same |
| TT7 | Price within 25% of 52-week high | `(high_52w - close) / high_52w <= 0.25` | same |
| TT8 | RS rank ≥70 (prefer ≥80) | rank across Finviz batch by 12-week return vs SPY, percentile | `criteria/trend_template.py` + batch pass in evaluator |

All 8 checks compile into a single `TrendTemplateResult` with per-check pass/fail and a combined `passed_count`. A ticker needs at least 7/8 to advance to the VCP layer; the one allowed fail should be configurable, and **TT8 is explicitly an acceptable miss by default** because it's an approximation (see below).

**Relative Strength — approximation, not IBD RS.** We don't subscribe to IBD. Batch-local percentile (rank across the Finviz CSV by 12-week return vs SPY) is unstable: change the screener universe and the rank changes for the same ticker. So:

- **TT8 is a soft component of the gate, not a hard filter.** A ticker can pass with TT8 failed if the other 7 pass.
- **RS computation uses a versioned stable reference universe**, not just the current Finviz batch:
  - Default universe: the union of (a) current Finviz CSV + (b) a curated reference list of ~500 liquid US equities stored in `reference/rs-universe.csv` (one-time seed from S&P 500 + NASDAQ-100).
  - 12-week trailing total return computed per ticker, ranked against the full reference universe, percentile 0–99.
  - This makes RS rank comparable across runs even when the Finviz CSV changes.
- **Universe versioning.** `reference/rs-universe.csv` has a required header row `# version: YYYY-MM-DD-<n>` (e.g., `# version: 2026-04-17-1`). Every `pipeline_runs` row records the SHA256 hash of the universe file used (`rs_universe_version` column). Historical RS ranks in `candidates.rs_rank` are **frozen** — never retroactively recomputed when the universe file changes. This means past recommendations remain reproducible even after reconstitutions, delistings, or ticker changes.
- **Universe refresh cadence.** Manual, quarterly. A CLI command `python -m swing.cli rs-universe refresh` regenerates the file from a configurable source (e.g., current S&P 500 membership via an explicit download step — not automated, to keep survivorship-bias tradeoffs visible to the user). The refresh writes a new version header and preserves the prior file at `reference/rs-universe-<prior-version>.csv` for reference.
- **Fallback for tickers outside the universe.** When a Finviz ticker isn't in the reference universe (new listing, recent IPO, etc.), the evaluator stores `rs_method='fallback_spy'` and computes `rs_return_12w_vs_spy` (raw excess return vs SPY). `rs_rank` is NULL. The two RS methods are NOT comparable; any sort/filter/bucket logic that uses RS must branch on `rs_method`. `scoring.py` treats fallback-method tickers as RS-neutral for TT8 (neither pass nor fail unless excess return is exceptionally high or low — +20% or −20% vs SPY respectively). All UI surfaces (list views, summary tables, expanded detail) show a distinct badge for fallback-method tickers: "RS: fallback" instead of "RS: 82."
- **Survivorship bias is accepted and documented** — in §4.1 methodology note here, in `swing/evaluation/criteria/trend_template.py` docstring, and in the per-ticker expanded view tooltip ("RS rank 82 · universe v2026-04-17-1 · 500 tickers · note: excludes recently delisted names").
- The rank method, horizon, and universe are documented in `swing/evaluation/criteria/trend_template.py` docstring.
- When the user confirms Minervini's preferred horizon from the book, adjust.

### 4.2 VCP / tactical layer (current 10 criteria, retained)

| Criterion | File | Notes |
|---|---|---|
| Prior trend ≥25% | `prior_trend.py` | Kept as-is |
| MA Stack 10>20>50 | `ma_stack_short.py` | Kept separate from Trend Template's 50/150/200 stack; short horizon is complementary |
| All short MAs rising | `ma_stack_short.py` | Bundled with the stack check above in the same file |
| Price within 5% of 20MA | `proximity.py` | Unchanged |
| ADR ≥4% | `adr.py` | Unchanged |
| Pullback <25% | `pullback.py` | Unchanged |
| Tightness (range ≤ 2/3 ADR, ≥2 days) | `tightness.py` | Unchanged |
| Volume contraction | `vcp.py` | Renamed; same rule |
| Orderliness | `orderliness.py` | Unchanged |
| Risk feasibility | `risk_feasibility.py` | Unchanged |

### 4.3 Bucket logic (`evaluation/scoring.py`)

| Bucket | Condition |
|---|---|
| `aplus` | Trend Template ≥7/8 AND VCP all 10 pass |
| `watch` | Trend Template ≥7/8 AND VCP has 1–2 fails |
| `skip` | Trend Template <7/8 OR VCP has 3+ fails |
| `excluded` | ETF/fund blocklist |
| `error` | Data fetch or computation error |

---

## 5. Pipeline lifecycle

### 5.1 Nightly run (scheduled)

Windows Task Scheduler runs `scripts/run-pipeline.bat` at the user's configured time (default matches current 21:49 HST). That script runs `python -m swing.pipeline --csv <selected-in-inbox>`.

Steps (each writes a `pipeline_runs` status column):

1. **Acquire run lock with lease.** Resolve `market_session_date` via §5.5. Generate a `lease_token` (uuid). Insert a `pipeline_runs` row with `state='running'`, `lease_token`, and `lease_heartbeat_ts=now`. If another `state='running'` row exists with a heartbeat within the last 2 minutes, exit with `state='blocked'`. If the other row's heartbeat is older than 2 minutes it's eligible for admin force-clear (§5.6) but not automatic takeover. Every subsequent write in this run's steps takes `lease_token` as a fencing argument; repos reject writes whose token doesn't match the current running row — a force-cleared old process cannot continue committing.
2. **Select + validate Finviz CSV.** Scan `data/finviz-inbox/` for files (non-recursive, excluding `rejected/`). Selection rule: **by filename date if parseable (e.g., `finviz17Apr2026.csv`) else by mtime, newest wins.** If multiple files share the same date stamp, abort with `state='failed'` and "Ambiguous inbox: N files for <date>" — never silently pick one. Validate the selected file's required columns (Ticker, Price, Volume, Country, Industry, Average Volume, 52-Week High/Low, etc.) against a declared schema in `swing.pipeline.finviz_schema`. On schema mismatch: move file to `data/finviz-inbox/rejected/` with a `.rejected-reasons.json` sidecar and abort the run with `state='failed'`. **Invalid newer files never mask an older valid file** — after rejection, the selector does NOT fall back to the next file; the user is expected to fix the newer file explicitly.
3. **Weather.** Fetch QQQ daily OHLCV, classify, write a `weather_runs` row. On failure → `weather_status='failed'`.
4. **Evaluate.** For each ticker: fetch OHLCV (cached), run Trend Template + VCP layers, write `candidates` + `candidate_criteria` rows. Compute RS ranks using the reference universe (see §4.1). On failure → `evaluation_status='failed'`; abort pipeline (downstream depends on this).
5. **Update watchlist.** Upsert `watchlist` — add newly qualifying tickers, refresh `last_qualified_date` for re-qualifiers, archive tickers that didn't qualify (see §5.4 aging rule).
6. **Write daily recommendations.** Build `daily_recommendations` rows from today's A+ names + near-trigger watchlist — immutable snapshot for audit/reproducibility.
7. **Render charts.** For A+ and top-N near-trigger watchlist tickers, render daily chart PNGs into `%USERPROFILE%/swing-data/charts/<asof_date>/<ticker>.png` (served via FastAPI static mount). Chart render failures are non-fatal — `charts_status='failed'` but run still completes.
8. **Write export snapshot.** Render today's briefing as `<project>/exports/<asof_date>/briefing.html` — a static, self-contained HTML snapshot (inline CSS, inline chart images as base64). Disaster-recovery / archival. Written inside the Drive folder on purpose (read-only output; Drive sync is safe for files the app doesn't write concurrently).
9. **Mark complete.** Update `pipeline_runs` with `state='complete'` and `finished_ts`.

### 5.2 On-demand run (dashboard)

`POST /pipeline/run` triggers the same entry point in a background task. `POST /pipeline/upload-csv` accepts a multipart form, writes the file to `data/finviz-inbox/`, and kicks `/pipeline/run`. Dashboard polls for completion via HTMX (server-sent progress partial, 1s interval).

If a manual run is triggered while a scheduled run has an active lease (heartbeat within 2 min), the new row is recorded with `state='blocked'` and the dashboard shows "Pipeline already running — started HH:MM." See §5.6 for admin recovery from stale leases.

### 5.3 Failure behavior and freshness

Failures are logged to stderr and to a rotating file under `%USERPROFILE%/swing-data/logs/pipeline.log`.

Hard rules:
- **Evaluation failure = abort.** Watchlist update, daily recommendations, chart render, and export cannot run with stale evaluation data. `pipeline_runs.state='failed'`.
- **Weather failure = non-fatal but gates decisions.** Weather is informational for sizing. If today's `weather_runs` row for the current `market_session_date` is missing, the dashboard status strip shows `Weather: STALE` and the "Today's decisions" panel prepends a banner: "Weather unavailable — verify before sizing."
- **Chart render failure = non-fatal.** Dashboard shows "chart unavailable" placeholder in expanded rows.

Freshness invariant enforced in the dashboard: the "Today's decisions" panel only renders `daily_recommendations` rows whose `action_session_date` equals the current market session (§5.5). If the most recent `pipeline_runs.state='complete'` run's `action_session_date` is older than the current session, the panel prepends a banner: "Last pipeline: <data_asof> — decisions below are for session <prior-session>. Run pipeline for <current-session>." Never silently show stale decisions as current.

### 5.4 Watchlist aging

Tickers drop from `watchlist` after **3 consecutive pipeline runs where the ticker was present in the Finviz batch but did not reach watch/A+ bucket**. Runs where the ticker was absent from the batch don't count — missed pipeline nights or screener universe changes don't prematurely evict.

Implementation: `watchlist.not_qualified_streak` is **write-once operational state**, incremented by the watchlist-update step once per distinct `data_asof_date`. If a run is re-done (e.g., the user uploads a corrected Finviz CSV for the same `data_asof_date`), the watchlist-update step detects the duplicate via `pipeline_runs.data_asof_date` and skips the streak mutation — ensuring re-running a session's analysis doesn't double-count. Streak is never recomputed from history (fragile across config changes).

### 5.5 Two dates: data_asof vs action_session

"What data did we evaluate?" and "what session do the recommendations apply to?" are distinct concepts; collapsing them into one `asof_date` causes wrong freshness, duplicate detection, and watchlist aging behavior.

Two orthogonal fields, carried on every run-related table:

- **`data_asof_date`** = the date of the most recent daily OHLCV bar included in this run's analysis. For a pipeline run at 21:49 HST Tuesday, this is Tuesday's close (last bar available pre-market-open on the next trading day). For a manual run at 06:00 HST Wednesday (before market open), still Tuesday. For a run during Wednesday market hours (Wed 06:00 HST = Wed 12:00 ET), it's Tuesday's close until the next close prints.
- **`action_session_date`** = the next NYSE trading session at or after the current time where the user can act on the recommendations. Tuesday 21:49 HST run → Wednesday. Friday 21:49 HST → Monday (skipping weekend / any NYSE holiday).

Computation uses the NYSE calendar from `exchange_calendars` or `pandas_market_calendars` (pick one at implementation; both cover holidays through at least 2030).

**Which field to use where:**

| Use case | Field |
|---|---|
| Freshness check on dashboard ("stale banner?") | `action_session_date` — compare to current session |
| Duplicate-run detection (watchlist aging) | `data_asof_date` — one streak-increment per distinct data date |
| Daily recommendation key | `(action_session_date, ticker, recommendation)` |
| Candidate history / evaluation_runs identity | `data_asof_date` (analysis ran against that data) |
| Export folder name (`exports/<date>/`) | `action_session_date` (matches how user thinks of it) |

**Examples:**
- Tuesday 21:49 HST scheduled run → `data_asof=2026-04-14 (Tue close)`, `action_session=2026-04-15 (Wed)`.
- Wednesday 06:30 HST user re-runs after correcting Finviz CSV → same `data_asof=2026-04-14`, same `action_session=2026-04-15`. Watchlist aging recognizes duplicate `data_asof` and decrements-before-incrementing streak.
- Friday 21:49 HST → `data_asof=2026-04-17 (Fri close)`, `action_session=2026-04-20 (Mon)`. Saturday / Sunday dashboard opens: `action_session=2026-04-20` is still the current session (no trading in between), so no STALE banner; recommendations render as fresh.

The dashboard status strip shows both: "Data: Fri Apr 17 · Session: Mon Apr 20."

### 5.6 Admin recovery: force-clear stale lease

Scenario: a pipeline process crashed mid-run without updating its heartbeat or making progress. The `pipeline_runs` row stays `state='running'` forever; subsequent runs are permanently blocked.

**Stale detection uses TWO signals, not heartbeat alone.** A heartbeat-only check is unreliable: on CPython/Windows a background thread can keep emitting heartbeats while the main loop is stuck in a C-extension call (e.g., matplotlib rendering or a frozen yfinance socket), and conversely the heartbeat thread can die from a GIL stall while the main work is progressing.

A run is considered **stale** only if BOTH of the following hold:
- `lease_heartbeat_ts` is older than `stale_lease_threshold_seconds` (default **5 min**, configurable), AND
- `last_step_progress_ts` is older than `stale_step_threshold_seconds` (default **15 min**, configurable).

`last_step_progress_ts` is updated atomically as part of every step transition in `pipeline_runs` (step start and step complete each set it), so it tracks actual forward progress, not just liveness.

If only the heartbeat is stale but step progress is recent (e.g., chart render taking 8 minutes), the run shows "long-running" status on `/pipeline` but is NOT eligible for force-clear. If step progress is stale but heartbeat is fresh, the run shows "wedged" status and IS eligible for force-clear — a clearer signal than heartbeat alone.

Heartbeat is emitted every 30 seconds by a background thread in the pipeline process. Step progress is emitted by the step-runner at start and finish of each pipeline step (§5.1 steps 1-9).

`/pipeline` page shows stale runs with a **Force clear** button. Clicking:
1. Requires explicit confirmation ("This marks run #N as failed. Any still-live worker loses its lease and cannot commit further writes. Proceed?").
2. Updates the row to `state='force_cleared'`, `error_message='admin force clear at <ts>'`.
3. Future writes by the original (possibly still-alive) worker process fail at the repo layer because `lease_token` no longer matches — the repo raises `LeaseRevokedError` and the worker exits.

This is the only way to clear a stuck lock. Restarting the app does not auto-clear.

### 5.7 Fenced writes for filesystem side effects

Database writes are fenced by `lease_token`, but the pipeline also writes files — charts, exports, logs. These need equivalent protection or a force-cleared stale process can overwrite the new run's outputs.

**Pattern: manifest-driven staged promotion.**

For each artifact group (charts, exports), promotion is a three-step atomic sequence guarded by a manifest file and verified on startup:

1. **Write to staging.** Artifacts go to a per-run staging directory, e.g., `charts/.staging/<run_id>/*.png`. When all artifacts for the group are written, a `MANIFEST.json` file is created in the staging directory containing: `run_id`, `lease_token`, `artifact_type`, `target_path`, `data_asof_date`, `action_session_date`, `artifact_count`, `timestamp`. The manifest is the explicit success marker — its presence means the staging directory is ready for promotion.

2. **Lease re-check.** Before promotion, the pipeline re-reads `pipeline_runs` for its own row. If `lease_token` doesn't match, or `state != 'running'`, the process aborts promotion and exits. Staging is left for startup sweep.

3. **Atomic swap with recovery marker.**
   a. If a target exists (`charts/<data_asof_date>/`), rename it to `charts/.prev/<data_asof_date>-<timestamp>/`.
   b. Rename staging directory to the target path (`charts/.staging/<run_id>/` → `charts/<data_asof_date>/`).
   c. Delete `charts/.prev/<data_asof_date>-<timestamp>/` (step commits — prior outputs discarded). If this deletion fails, it's non-fatal; startup sweep cleans later.

If the process dies between step 3a and 3b, a `charts/.prev/...` directory exists without a fresh target. If it dies between 3b and 3c, target exists AND stale .prev exists.

**Startup recovery protocol.** On pipeline startup (before acquiring lease), the recovery routine runs:

1. Scan `charts/`, `exports/` for `.staging/*/MANIFEST.json` files. For each:
   - If the `run_id` in manifest has `pipeline_runs.state IN ('running', with heartbeat <5min old)` — leave alone (active run).
   - Else: the staged outputs belong to a dead/force-cleared run → **delete the staging directory** (its MANIFEST says it was ready but the owning run never completed).
2. Scan `charts/.prev/`, `exports/.prev/`. Any directory older than 7 days is deleted. Anything younger stays (manual recovery window).
3. Scan `charts/.staging/*` and `exports/.staging/*` without a MANIFEST — these are incomplete writes from dead runs. Delete if older than 1 hour (active run would be within heartbeat window).

**Dashboard authority rule.** The dashboard always reads canonical paths (`charts/<data_asof_date>/`, `exports/<action_session_date>/`). If a directory is missing, the dashboard shows a clear "chart unavailable for <date> — last pipeline for this session did not complete" rather than fall back to a `.prev/` or `.staging/`. This makes the authoritative artifact set unambiguous.

**Logs** don't need staging — they're opened append-only and self-identify via `run_id` prefix on each line. A force-cleared process's continued log lines are benign noise.

---

## 6. Output / view design

### 6.1 Main dashboard (`/`)

Hierarchy — most actionable at top, most detailed at bottom:

1. **Top bar.** Date, nav (Dashboard / Journal / Pipeline / Settings).
2. **Status strip** (three tiles):
   - Market weather: status chip + 1-line rationale
   - Account: equity + open-position count vs soft/hard caps
   - Last pipeline run: timestamp + "Run now" button
3. **Today's decisions** (amber panel, always visible):
   - Empty state: "No decisions today — watchlist below."
   - With decisions: one line per actionable name — ticker, entry limit, shares, risk $ and %, inline "Log entry" button; 1-sentence narrative below. Trend-template + VCP score shown compactly.
4. **Open positions** (if any): table with ticker, entry, current stop, R-so-far, and the stop-advisory suggestion ("Move to breakeven," "Trail below 10MA," etc.).
5. **Watchlist**: compact table, default sort by % to pivot. Columns: flag (⚡ near trigger), ticker, last, pivot, % to pivot, ADR, stop, flag tags (TT✓ VCP✓ · A+). Filter input + sort dropdown + "Near trigger only" toggle. Show top 5 expanded, "Show N more" to reveal rest.
6. **Expanded row** (HTMX swap on click): narrative, Trend Template 8-check grid, VCP 10-check grid, inline daily chart, action buttons ("Log entry at $X", "Archive").

### 6.2 Secondary pages

- **`/watchlist`**: full watchlist table; archive view; manual add.
- **`/journal`**: period selector (week / month / quarter / YTD / all), stats block (win rate, expectancy, avg W/L in R, streak, total R), trade table, behavioral flags panel.
- **`/pipeline`**: upload Finviz CSV; run-now button; run history with per-run summary (tickers evaluated, buckets); link to per-run detail (equivalent of today's `report.md` but HTML and filterable).
- **`/settings`**: edit config values (thresholds, weights, position limits); save writes a new `config_revisions` row.

### 6.3 View-model pattern

Routes fetch raw data via repos, pass it to a `rendering.*` function that returns a dataclass view model, and pass that to the Jinja template. Templates never do computation. This keeps views testable (build view model from fixture data, snapshot it) and keeps the same view model reusable if we later want a CLI-printed briefing or an email digest.

### 6.4 Retained archival outputs

The dashboard is the primary UX, but each pipeline run also writes a **self-contained HTML export** to `<project>/exports/<market_session_date>/briefing.html` (step 5.1.8). This is:

- Static (inline CSS + base64 charts), readable without the server running.
- Safe to live in the Google Drive folder (read-only after pipeline write; no concurrent app writes).
- A disaster-recovery fallback if the dashboard or DB is broken.
- Archival — preserves exactly what was said on a given day, even if the DB is later corrupted or restored.

**Retention and size governance:**
- **Per-file size cap:** 500 KB. If base64-encoded charts push a briefing over the cap, charts are referenced as file links to `<project>/exports/<session>/charts/<ticker>.png` instead of being inlined. The briefing always renders; large ones just delink charts.
- **Retention:** rolling 90 days of `exports/<date>/` folders. Older folders are automatically compressed to `exports/archive/<YYYY-MM>.zip` by a pipeline post-step. Archives themselves are retained 3 years, then prompted for deletion via a `/settings` notice — never auto-deleted.
- **Drive sync footprint:** with 90 days × ~300 KB avg, steady-state disk usage is ~27 MB — negligible. Archives compress ~5x.
- **Size governance is advisory, not blocking.** If `exports/` exceeds 500 MB, the pipeline **logs a warning, writes a `warnings` row on the current `pipeline_runs` record, and surfaces a dashboard banner** — but does NOT fail the run. The trading-decision outputs (DB writes, recommendations, charts) are mission-critical; export housekeeping is not. User fixes via `/settings` prune tooling at their convenience.

**Transition markdown output.** A sibling `briefing.md` is written alongside `briefing.html` until one of these concrete gates is met:
- 20 consecutive complete pipeline runs with no dashboard-blocking defect logged, AND
- User has explicitly reviewed ≥4 dashboard briefings and signed off in `exports/transition-log.md` (a running checklist the app prompts for after each pipeline run for the first month).

After both gates pass, `briefing.md` generation is removed from the pipeline by a one-line config flag (`retain_markdown_sibling = false`). The generated `.md` files from the transition period remain in `exports/` as historical record.

---

## 7. Testing

### 7.1 Unit tests

Every file under `evaluation/criteria/` has a `tests/evaluation/criteria/test_<name>.py`. Each test loads a small synthetic OHLCV fixture from `tests/fixtures/ohlcv/`, calls the criterion, and asserts pass/fail + computed values. Criteria are pure functions — no mocking.

Repos get round-trip tests using a temp SQLite DB. Business logic modules (`trades/`, `journal/`, `trades/advisory.py`) get unit tests with an in-memory DB seeded from fixtures.

### 7.2 Behavioral tests (two tiers)

Two separate test suites with different intents. The split exists because the refactor is partly a correctness improvement — we must not freeze the old evaluator's mistakes into the new system.

**7.2a Parity tests (mechanical regression safety net).** `tests/evaluation/test_parity.py` replays existing `finviz screeners/*.csv` through the new evaluator and compares bucket assignment per ticker against a baseline captured from the current `evaluate_candidates.py`. Divergences are expected (Trend Template additions will demote many tickers); each divergence must be listed in `tests/fixtures/finviz/expected-diffs.yaml` with an explicit reason (`"Trend Template TT3 fail: 200MA flat"`). Any unexplained divergence fails the test. This guards against accidental regressions in the VCP tactical math during the rewrite — not against intentional rule improvements.

**7.2b Golden fixture tests (hand-verified correctness).** `tests/evaluation/test_golden.py` uses a small set of **hand-constructed or hand-reviewed OHLCV fixtures** in `tests/fixtures/golden/` — one per canonical case: clean A+ VCP, Trend Template fail (flat 200MA), VCP fail (no tightness), choppy/disorderly, ETF exclusion, RS-too-low. For each fixture, the expected bucket + per-criterion pass/fail is declared in a sibling `expected.yaml`. These expected outcomes are authored from domain knowledge (Disciplined Swing Trader / Minervini), **not** captured from the current evaluator. This is the real correctness test; parity is the scaffolding.

The parity baseline is discarded once the rewrite is complete and all expected-diffs are explained — golden fixtures take over as the source of truth.

### 7.3 Route tests

`tests/web/test_routes.py` uses FastAPI's `TestClient` with a temp DB. For each route, a seeded state + expected snippet in the rendered HTML. Not exhaustive; high-value flows only (dashboard renders when no data, log-entry form persists, pipeline-run triggers).

### 7.4 No end-to-end browser tests

Out of scope — no Playwright/Selenium. Dashboard is single-user and visually inspected.

---

## 8. Data migration

One-shot script: `python -m swing.cli db-migrate --from-legacy`. Steps:

1. Create `data/swing.db` with all migrations applied.
2. Import `journal/cash_movements.csv` → `cash_movements` table.
3. Import `journal/trades.csv` + `journal/exits.csv` → `trades` + `exits` tables (currently empty, but script handles a non-empty case).
4. Import `weather/history.csv` → `weather_runs` table.
5. Move the following to `reference/archive/` (read-only, never touched by the app):
   - `briefings/` → `reference/archive/briefings/`
   - `reports/` → `reference/archive/reports/`
   - `finviz screeners/` → `reference/archive/finviz-screeners/`
   - `watchlist/` → `reference/archive/watchlist-snapshots/`
   - `thinkorswim/` → `reference/archive/thinkorswim/`
   - `weather/` → `reference/archive/weather/` (after importing `history.csv` in step 4)
6. Move reference material:
   - `*.pdf`, `*.docx`, `*.xlsx` at root → `reference/books/` or `reference/worksheets/`
   - `flag_pattern.png`, `pennant_pattern.png`, `tight_channel_flat_base.png` → `reference/patterns/`
7. Convert `trade_config.json` → `swing.config.toml`, preserving all values.
8. Delete `market_weather.md` (duplicate), `__pycache__/`, `etf_cache.json` (replaced by SQLite row), `run_weather.bat` (replaced by `scripts/run-pipeline.bat`), and the old `.py` files once the new system passes golden tests.

The script is idempotent: re-running on an already-migrated folder is a no-op.

---

## 9. Out of scope / explicitly deferred

- **Backtesting.** Schema is shaped to not preclude it, but no backtesting code.
- **Broker API integration.** Trades still manually entered; TOS reconciliation stays CSV-import.
- **Multi-user / hosted service.** localhost single-user only.
- **Authentication.** localhost binding only; no login.
- **Multiple setup patterns beyond VCP / HTF.** New criteria files can be added later without schema change.
- **Alerting (SMS / email / push).** Deferred; dashboard-only.
- **Cross-machine sync.** Google Drive handles file sync for the db file (which is risky — see open question 1 below).

---

## 10. Open questions / decisions

1. **SQLite DB path.** ✅ Confirmed by user 2026-04-17 — `%USERPROFILE%/swing-data/swing.db`.
2. **RS rank horizon.** 12-week trailing return vs SPY is the approximation (§4.1). Verify against Minervini's book when acquired; may want 13-week, 26-week, or blended.
3. **Reference universe seeding.** ✅ Confirmed by user 2026-04-17 — S&P 500 + NASDAQ-100 initial seed for `reference/rs-universe.csv`.
4. **Watchlist aging.** ✅ Resolved in §5.4 — 3 consecutive evaluated-but-not-qualifying runs; absence-from-batch doesn't count.
5. **Config format.** ✅ Confirmed by user 2026-04-17 — TOML (`swing.config.toml`).

---

## 11. Success criteria

The refactor is done when:

- [ ] All unit tests pass.
- [ ] Golden test passes, with expected diffs file documenting Trend Template additions.
- [ ] `scripts/run-pipeline.bat` runs end-to-end against today's real Finviz CSV and populates `swing.db`.
- [ ] `scripts/run-web.bat` starts the dashboard; user opens it in a browser and sees today's decisions / watchlist / charts.
- [ ] User can log an entry from the dashboard and see it in the open-positions panel.
- [ ] User can run a journal-review period and see stats.
- [ ] Legacy `evaluate_candidates.py`, `trade.py`, `market_weather.py` are deleted.
- [ ] Legacy folders (`briefings/`, `reports/`, `finviz screeners/`, `watchlist/`, `thinkorswim/`, `weather/`) are moved to `reference/archive/` and no longer written by the app.
- [ ] Root directory contains only: `swing/`, `tests/`, `data/`, `exports/`, `reference/`, `scripts/`, `docs/`, `swing.config.toml`, `pyproject.toml`, `README.md`.
- [ ] `swing.db` is verified to live at `%USERPROFILE%/swing-data/swing.db` — not inside the Drive folder.
- [ ] `pipeline_runs` table exists and correctly records locked / blocked / failed states when scheduler and manual runs collide (tested).
- [ ] Dashboard shows STALE banner when last complete pipeline run is older than today.
- [ ] Behavioral tests (7.2a parity + 7.2b hand-verified golden) both pass.
