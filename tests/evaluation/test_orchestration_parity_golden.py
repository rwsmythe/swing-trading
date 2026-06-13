"""Phase-0 golden-parity harness for Arc 17-A.

Drives IDENTICAL pinned inputs through BOTH production evaluation paths
(`swing eval` via CliRunner, and `_step_evaluate` via a fake lease) and diffs
the persisted `candidates` rows column-by-column. Divergences are pinned AS
divergences (DIVERGENCE-n) -- the Task-C checkpoint routes them to the operator.

Production-derivation discipline (byte-parity-insufficient gotcha): the network
boundary is pinned by SEEDING the on-disk OHLCV archive; the REAL PriceFetcher /
read_or_fetch_archive serves it. NO fetcher object is stubbed.

Frozen-clock convention (R2/D9): run_now is pinned; datetime.now is monkeypatched
in EVERY module that captures it (swing.cli, swing.pipeline.runner [as `_dt`],
swing.data.ohlcv_archive, swing.prices) so action_session/data_asof are
deterministic AND the archive freshness gate passes (the seeded archive's latest
bar == _last_completed_session_today(), so read_or_fetch_archive serves from disk
with ZERO network).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import swing.cli as cli_mod
import swing.config as swing_config
import swing.data.ohlcv_archive as archive_mod
import swing.pipeline.runner as runner_mod
import swing.prices as prices_mod
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.evaluation.rs import load_universe, universe_version_hash

# Frozen clock: 18:30 HST on Thu 2026-06-11. Converted to ET this is 00:30 Fri
# 2026-06-12 (before Friday's close), so last_completed_session == 2026-06-11
# (Thursday's completed session) and action_session_for_run == 2026-06-12.
RUN_NOW = datetime(2026, 6, 11, 18, 30, 0)
SESSION = date(2026, 6, 11)

SCREEN_TICKERS = ["AAA", "BBB", "CCC"]      # finviz screen
UNIVERSE_TICKERS = ["AAA", "UUU"]           # RS universe
HELD_TICKER = "HHH"                          # open position, OFF-screen
PINNED_TICKER = "PPP"                        # Arc-7 pin, OFF-screen, not held
BLOCKLIST_FAIL = "ZZZ"                       # blocklisted AND fetch fails (D-ERROR-DEDUP)
SPY = "SPY"

# Tickers seeded into the offline archive (everything except BLOCKLIST_FAIL).
_SEEDED_TICKERS = sorted(
    set(SCREEN_TICKERS) | set(UNIVERSE_TICKERS) | {HELD_TICKER, PINNED_TICKER, SPY}
)


def _uptrend_frame(n: int = 420, end: date = SESSION) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    closes = [10.0 + i * 0.06 for i in range(n)]
    return pd.DataFrame(
        {"Open": closes, "High": [c * 1.02 for c in closes],
         "Low": [c * 0.98 for c in closes], "Close": closes,
         "Volume": [1_000_000] * n},
        index=idx,
    )


def _seed_archive(cache_dir: Path, ticker: str, frame: pd.DataFrame) -> None:
    """Write a FRESH per-ticker legacy archive so read_or_fetch_archive serves it
    with zero network.

    The legacy reader (`read_or_fetch_archive`) consumes a DatetimeIndex'd frame
    (`archive.index.max().date()`, `archive.index.date <= end_date`). pandas
    `to_parquet` (index=True default) preserves the DatetimeIndex via pandas
    metadata, so `pd.read_parquet` restores it. (The plan's first-draft
    `reset_index().to_parquet(index=False)` would yield a RangeIndex + `date`
    COLUMN -- wrong shape for the legacy reader -- so we preserve the index.)
    Meta marks a full refresh at SESSION so the freshness gate sees no staleness.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    out.index.name = "date"
    out.to_parquet(cache_dir / f"{ticker}.parquet")
    (cache_dir / f"{ticker}.meta.json").write_text(
        json.dumps({"last_full_refresh_date": SESSION.isoformat()})
    )


def _build_inputs(
    tmp_path: Path, *, seed_spy: bool = True, include_blocklist_fail: bool = False
) -> SimpleNamespace:
    """Materialize the shared offline fixture set under tmp_path.

    Writes: a real finviz CSV (No.,Ticker,Sector,Industry,Price), a real RS
    universe file, and a seeded archive dir with an uptrend frame for every
    seeded ticker (BLOCKLIST_FAIL is left UNSEEDED so its fetch reaches the
    pinned downloader -> deterministic offline raise -> exercises error path).
    SPY is seeded unless seed_spy=False.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    cache_dir = tmp_path / "prices-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # finviz CSV
    csv_tickers = list(SCREEN_TICKERS)
    if include_blocklist_fail:
        csv_tickers.append(BLOCKLIST_FAIL)
    csv_path = tmp_path / "finviz.csv"
    rows = ["No.,Ticker,Sector,Industry,Price"]
    for i, t in enumerate(csv_tickers, start=1):
        rows.append(f"{i},{t},Technology,Software,{200.0 - i}")
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    # RS universe file (the `# version:` / `# columns: ticker` header shape).
    universe_path = tmp_path / "rs-universe.csv"
    universe_path.write_text(
        "# version: test-v1\n# source: test\n# columns: ticker\nticker\n"
        + "\n".join(UNIVERSE_TICKERS) + "\n",
        encoding="utf-8",
    )

    # Seeded archive (offline).
    for t in _SEEDED_TICKERS:
        if t == SPY and not seed_spy:
            continue
        _seed_archive(cache_dir, t, _uptrend_frame())

    db_path = tmp_path / "swing.db"
    return SimpleNamespace(
        csv_path=csv_path,
        universe_path=universe_path,
        cache_dir=cache_dir,
        db_path=db_path,
    )


def _make_config(tmp_path: Path, inputs: SimpleNamespace):
    """Real Config from a temp TOML: ABSOLUTE db_path + prices_cache_dir (the
    seeded archive) + rs_universe_path (the seeded universe), manual_block=['ZZZ']
    so BLOCKLIST_FAIL is on the ETF blocklist. Returns the config object."""
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(
        f"""[paths]
db_path = "{inputs.db_path.as_posix()}"
data_dir = "{tmp_path.as_posix()}/swing-data"
logs_dir = "{tmp_path.as_posix()}/swing-data/logs"
charts_dir = "{tmp_path.as_posix()}/swing-data/charts"
backups_dir = "{tmp_path.as_posix()}/swing-data/backups"
prices_cache_dir = "{inputs.cache_dir.as_posix()}"
finviz_inbox_dir = "{tmp_path.as_posix()}/finviz-inbox"
exports_dir = "{tmp_path.as_posix()}/exports"
rs_universe_path = "{inputs.universe_path.as_posix()}"

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
manual_block = ["ZZZ"]
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
""",
        encoding="utf-8",
    )
    return swing_config.load(cfg_path)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def frozen_clock(monkeypatch):
    """Pin datetime.now() to RUN_NOW in EVERY module that captures it for this
    arc's date semantics + archive-freshness gate."""
    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return RUN_NOW

    monkeypatch.setattr(cli_mod, "datetime", _Clock)
    monkeypatch.setattr(runner_mod, "_dt", _Clock)        # runner imports datetime as _dt
    monkeypatch.setattr(archive_mod, "datetime", _Clock)  # _last_completed_session_today()
    monkeypatch.setattr(prices_mod, "datetime", _Clock)   # PriceFetcher._resolve_asof()
    return RUN_NOW


@pytest.fixture
def pin_network(monkeypatch):
    """Make ALL network egress deterministic+offline. Seeded-fresh archives serve
    from disk (downloader never called); unseeded tickers reach here and raise."""
    def _raise(*a, **k):
        raise RuntimeError("network pinned offline in Phase-0 harness")

    monkeypatch.setattr(archive_mod, "_yf_download_window", _raise, raising=False)
    monkeypatch.setattr(archive_mod, "_fetch_chunk", _raise, raising=False)
    return _raise


# --------------------------------------------------------------------------- #
# DB seed helpers (IDENTICAL for both paths so the diff reveals only path-
# divergent handling). Cribbed from tests/pipeline/test_step_evaluate_pin_injection.py
# --------------------------------------------------------------------------- #
def _migrate(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=db_path.parent)
    return conn


def _seed_pinned_watchlist(conn: sqlite3.Connection, ticker: str) -> None:
    with conn:
        upsert_watchlist_entry(conn, WatchlistEntry(
            ticker=ticker, added_date="2026-06-01",
            last_qualified_date="2026-06-01", status="watch",
            qualification_count=1, not_qualified_streak=0,
            last_data_asof_date="2026-06-09", entry_target=13.0,
            initial_stop_target=11.0, last_close=12.0, last_pivot=13.0,
            last_stop=11.0, last_adr_pct=2.0, missing_criteria=None, notes=None,
            pinned=True, pin_note="tracking", pinned_at="2026-06-01T00:00:00Z",
        ))


def _seed_open_trade(conn: sqlite3.Connection, ticker: str) -> None:
    conn.execute(
        """
        INSERT INTO trades
            (ticker, entry_date, entry_price, initial_shares,
             initial_stop, current_stop, state,
             trade_origin, pre_trade_locked_at,
             current_size, current_avg_cost)
        VALUES (?, '2026-05-01', 100.0, 50, 90.0, 92.0, 'managing',
                'manual_off_pipeline', '2026-05-01T09:30:00', 50, 100.0)
        """,
        (ticker,),
    )
    tid = conn.execute("SELECT id FROM trades WHERE ticker = ?", (ticker,)).fetchone()[0]
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json) "
        "VALUES (?, '2026-05-01T09:30:00', 'entry', '{}')",
        (tid,),
    )
    conn.commit()


def _seed_open_and_pins(db_path: Path) -> None:
    """Seed one open trade (HHH) + one pinned watchlist entry (PPP). IDENTICAL for
    both paths so the diff reveals only path-divergent handling of them."""
    conn = _migrate(db_path)
    try:
        _seed_open_trade(conn, HELD_TICKER)
        _seed_pinned_watchlist(conn, PINNED_TICKER)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Task 0.1 smoke test: fixtures load, archive serves offline.
# --------------------------------------------------------------------------- #
def test_seeded_archive_serves_without_network(tmp_path, frozen_clock, pin_network):
    inputs = _build_inputs(tmp_path)
    from swing.prices import PriceFetcher
    f = PriceFetcher(cache_dir=inputs.cache_dir, archive_history_days=1260)
    df = f.get("AAA", lookback_days=400, as_of_date=None)  # served from disk; pin_network proves no egress
    assert not df.empty
    assert df.index.max().date() == SESSION


def test_frozen_clock_session_anchors(frozen_clock):
    """Pin the deterministic date semantics the harness relies on."""
    from swing.evaluation.dates import action_session_for_run, last_completed_session
    assert last_completed_session(RUN_NOW) == SESSION
    assert action_session_for_run(RUN_NOW) == date(2026, 6, 12)
