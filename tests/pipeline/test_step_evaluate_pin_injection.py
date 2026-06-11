"""Arc 7 Task 4 — _step_evaluate pinned-universe injection + error/excluded dedup.

Three behaviors driven through the REAL _step_evaluate:

1. A pinned, OFF-SCREEN, NOT-HELD ticker is unioned into the fetch+eval set so
   it gets a REAL (non-excluded) bucket every night, and a ``pin_injection``
   run-warning records the injection.
2. A pinned ticker that is ALSO held stays ``excluded`` (close-only) — it is
   already in ``seen`` via the held-tickers union, so it is NOT re-injected.
3. A held ticker whose OHLCV fetch ALSO fails yields EXACTLY ONE candidate
   (the ``excluded`` row), not a duplicate ``error`` row — the error_tickers
   list is de-duped against ``excluded`` (Codex R1-Major).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import swing.config as swing_config
import swing.pipeline.runner as rmod
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.data.models import WatchlistEntry
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.watchlist import upsert_watchlist_entry

RUN_ID = 1
DATA_ASOF = "2026-06-10"
ACTION_SESSION = date(2026, 6, 11)
RUN_NOW = datetime(2026, 6, 11, 18, 0, 0)


# --------------------------------------------------------------------------- #
# Harness scaffolding
# --------------------------------------------------------------------------- #
class _FakeLease:
    """Minimal Lease: run_id + verify_held() no-op + step() no-op + a
    fenced_write() yielding a conn to the same file DB."""

    def __init__(self, db_path, run_id: int):
        self.db_path = db_path
        self.run_id = run_id

    def verify_held(self) -> None:  # _step_evaluate calls this first
        pass

    def step(self, name: str) -> None:
        pass

    @contextmanager
    def fenced_write(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class _StubFetcher:
    """get(ticker, lookback_days, *, as_of_date=None) -> a valid ~400-bar
    uptrend frame for any ticker NOT in fail_set; raises for fail_set tickers."""

    def __init__(self, fail_set: set[str]):
        self._fail = {t.upper() for t in fail_set}

    def get(self, ticker, lookback_days, *, as_of_date=None) -> pd.DataFrame:
        if ticker.upper() in self._fail:
            raise RuntimeError(f"synthetic fetch failure for {ticker}")
        n = 400
        idx = pd.bdate_range(end="2026-06-10", periods=n)
        closes = [10.0 + i * 0.05 for i in range(n)]
        return pd.DataFrame(
            {"Open": closes, "High": [c * 1.01 for c in closes],
             "Low": [c * 0.99 for c in closes], "Close": closes,
             "Volume": [1_000_000] * n},
            index=idx,
        )


def _make_config(tmp_path):
    """Real Config from a temp TOML mirroring sample_config but with an
    ABSOLUTE db_path pointing at the seeded DB (so connect(cfg.paths.db_path)
    hits it)."""
    db_path = tmp_path / "swing.db"
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(
        f"""[paths]
db_path = "{db_path.as_posix()}"
data_dir = "{tmp_path.as_posix()}/swing-data"
logs_dir = "{tmp_path.as_posix()}/swing-data/logs"
charts_dir = "{tmp_path.as_posix()}/swing-data/charts"
backups_dir = "{tmp_path.as_posix()}/swing-data/backups"
prices_cache_dir = "{tmp_path.as_posix()}/swing-data/prices-cache"
finviz_inbox_dir = "{tmp_path.as_posix()}/finviz-inbox"
exports_dir = "{tmp_path.as_posix()}/exports"
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
    cfg = swing_config.load(cfg_path)
    return cfg, db_path


def _migrate_to_head(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION,
                   backup_dir=db_path.parent)
    return conn


def _seed_running_run(conn) -> None:
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(?, '2026-06-11T18:00:00', 'manual', ?, ?, 'tok', 'running')",
        (RUN_ID, DATA_ASOF, ACTION_SESSION.isoformat()),
    )
    conn.commit()


def _seed_pinned_watchlist(conn, ticker: str) -> None:
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


def _seed_open_trade(conn, ticker: str) -> None:
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
    tid = conn.execute(
        "SELECT id FROM trades WHERE ticker = ?", (ticker,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json) "
        "VALUES (?, '2026-05-01T09:30:00', 'entry', '{}')",
        (tid,),
    )
    conn.commit()


def _write_csv(tmp_path, tickers) -> Path:
    csv = tmp_path / "finviz.csv"
    lines = ["Ticker,Sector,Industry"]
    lines += [f"{t},Tech,Software" for t in tickers]
    csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv


def _patch_warms(monkeypatch):
    monkeypatch.setattr(rmod, "_prewarm_evaluate_archives", lambda **k: None)
    monkeypatch.setattr(rmod, "_warm_pipeline_marketdata", lambda **k: None)


def _universe():
    return SimpleNamespace(tickers=["AAAA", "BBBB"], version="v1")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_pinned_offscreen_ticker_is_evaluated_not_excluded(tmp_path, monkeypatch):
    cfg, db_path = _make_config(tmp_path)
    conn = _migrate_to_head(db_path)
    _seed_running_run(conn)
    _seed_pinned_watchlist(conn, "PINX")  # off-screen, not held
    _patch_warms(monkeypatch)

    csv = _write_csv(tmp_path, ["AAAA", "BBBB"])
    fetcher = _StubFetcher(fail_set=set())  # everything fetches, incl. SPY + PINX
    lease = _FakeLease(db_path, RUN_ID)
    run_warnings: list[dict] = []

    run_id = rmod._step_evaluate(
        cfg=cfg, fetcher=fetcher, csv_path=csv, universe=_universe(),
        universe_hash="h", run_now=RUN_NOW, action_session=ACTION_SESSION,
        lease=lease, run_warnings=run_warnings,
    )

    cands = fetch_candidates_for_run(conn, run_id)
    by = {c.ticker: c for c in cands}
    assert "PINX" in by
    assert by["PINX"].bucket != "excluded"  # evaluated, not close-only

    pin_lines = [w for w in run_warnings if w.get("kind") == "pin_injection"]
    assert len(pin_lines) == 1
    assert pin_lines[0]["count"] == 1
    assert "PINX" in pin_lines[0]["tickers"]
    assert pin_lines[0]["step"] == "evaluate"


def test_pinned_held_ticker_stays_excluded(tmp_path, monkeypatch):
    cfg, db_path = _make_config(tmp_path)
    conn = _migrate_to_head(db_path)
    _seed_running_run(conn)
    _seed_open_trade(conn, "HELD")
    _seed_pinned_watchlist(conn, "HELD")  # pinned AND held
    _patch_warms(monkeypatch)

    csv = _write_csv(tmp_path, ["AAAA"])
    fetcher = _StubFetcher(fail_set=set())
    lease = _FakeLease(db_path, RUN_ID)
    run_warnings: list[dict] = []

    run_id = rmod._step_evaluate(
        cfg=cfg, fetcher=fetcher, csv_path=csv, universe=_universe(),
        universe_hash="h", run_now=RUN_NOW, action_session=ACTION_SESSION,
        lease=lease, run_warnings=run_warnings,
    )

    by = {c.ticker: c for c in fetch_candidates_for_run(conn, run_id)}
    assert "HELD" in by
    assert by["HELD"].bucket == "excluded"  # held → close-only, not injected

    pin_lines = [w for w in run_warnings if w.get("kind") == "pin_injection"]
    # HELD is already in `seen` via the held-tickers union → never injected.
    assert all("HELD" not in w["tickers"] for w in pin_lines)


def test_held_and_fetch_failing_ticker_yields_exactly_one_candidate(
    tmp_path, monkeypatch
):
    cfg, db_path = _make_config(tmp_path)
    conn = _migrate_to_head(db_path)
    _seed_running_run(conn)
    _seed_open_trade(conn, "FAILH")
    _patch_warms(monkeypatch)

    csv = _write_csv(tmp_path, ["AAAA"])
    # FAILH fetch raises; AAAA + SPY fetch fine.
    fetcher = _StubFetcher(fail_set={"FAILH"})
    lease = _FakeLease(db_path, RUN_ID)
    run_warnings: list[dict] = []

    run_id = rmod._step_evaluate(
        cfg=cfg, fetcher=fetcher, csv_path=csv, universe=_universe(),
        universe_hash="h", run_now=RUN_NOW, action_session=ACTION_SESSION,
        lease=lease, run_warnings=run_warnings,
    )

    failh = [c for c in fetch_candidates_for_run(conn, run_id)
             if c.ticker == "FAILH"]
    assert len(failh) == 1  # dedup: no duplicate error row
    assert failh[0].bucket == "excluded"
