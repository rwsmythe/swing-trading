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
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from click.testing import CliRunner

import swing.cli as cli_mod
import swing.config as swing_config
import swing.data.ohlcv_archive as archive_mod
import swing.pipeline.runner as runner_mod
import swing.prices as prices_mod
from swing.cli import main
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
# Path drivers + row readers
# --------------------------------------------------------------------------- #
class _FakeLease:
    """Minimal Lease: run_id + verify_held()/step() no-ops + a fenced_write()
    yielding a BEGIN IMMEDIATE conn to the same file DB. Cribbed verbatim from
    tests/pipeline/test_step_evaluate_pin_injection.py."""

    def __init__(self, db_path, run_id: int):
        self.db_path = db_path
        self.run_id = run_id

    def verify_held(self) -> None:
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


def _seed_running_run(db_path: Path, run_id: int) -> None:
    """Seed the pipeline_runs row matching the lease run_id so
    set_evaluation_run_id has a row to UPDATE."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
            "action_session_date, lease_token, state) VALUES "
            "(?, '2026-06-11T18:00:00', 'manual', '2026-06-11', '2026-06-12', 'tok', 'running')",
            (run_id,),
        )
        conn.commit()
    finally:
        conn.close()


# Full persisted candidate-column set (every column the orchestration writes).
_CAND_COLS = (
    "ticker", "bucket", "close", "pivot", "initial_stop", "adr_pct",
    "tight_streak", "pullback_pct", "prior_trend_pct", "rs_rank",
    "rs_return_12w_vs_spy", "rs_method", "pattern_tag", "notes", "sector", "industry",
)


def _read_candidates(db_path: Path) -> list[dict]:
    """All candidate columns for the LATEST evaluation_runs.id, ONE dict per row
    (a LIST, order-stable by (ticker, bucket)). A LIST (not a ticker-keyed dict)
    so duplicate rows per ticker stay observable (Codex R1 C1)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rid = conn.execute("SELECT MAX(id) FROM evaluation_runs").fetchone()[0]
        if rid is None:
            return []
        sql = (
            "SELECT " + ", ".join(_CAND_COLS) + " FROM candidates "
            "WHERE evaluation_run_id = ? ORDER BY ticker, bucket"
        )
        return [dict(r) for r in conn.execute(sql, (rid,)).fetchall()]
    finally:
        conn.close()


def _rows_by_ticker(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["ticker"], []).append(r)
    return out


def _one(rows: list[dict], ticker: str) -> dict:
    matches = [r for r in rows if r["ticker"] == ticker]
    assert len(matches) == 1, f"expected exactly one {ticker} row, got {len(matches)}"
    return matches[0]


def _invoke_cli(inputs: SimpleNamespace, cfg_dir: Path, *, catch: bool = True):
    """Invoke `swing eval` via CliRunner against a fresh migrated + seeded DB.
    Returns the raw click Result (so error/exit-code paths stay observable)."""
    runner = CliRunner()
    cfg_arg = str(cfg_dir / "swing.config.toml")
    runner.invoke(main, ["--config", cfg_arg, "db-migrate"])
    _seed_open_and_pins(inputs.db_path)
    return runner.invoke(
        main, ["--config", cfg_arg, "eval", "--csv", str(inputs.csv_path)],
        catch_exceptions=catch,
    )


def _run_cli_path(cfg_dir: Path, inputs: SimpleNamespace) -> list[dict]:
    """Drive the CLI path to completion and return persisted candidate rows."""
    result = _invoke_cli(inputs, cfg_dir)
    assert result.exit_code == 0, (result.output, repr(result.exception))
    return _read_candidates(inputs.db_path)


def _run_pipeline_path(inputs: SimpleNamespace, cfg) -> tuple[list[dict], list[dict]]:
    """Drive the REAL _step_evaluate (fresh migrated + seeded DB, real
    PriceFetcher on the seeded archive, _FakeLease). Returns (rows, run_warnings)."""
    from swing.prices import PriceFetcher
    _seed_open_and_pins(inputs.db_path)
    _seed_running_run(inputs.db_path, 1)
    universe = load_universe(cfg.paths.rs_universe_path)
    universe_hash = universe_version_hash(cfg.paths.rs_universe_path)
    fetcher = PriceFetcher(
        cache_dir=inputs.cache_dir, archive_history_days=cfg.archive.archive_history_days
    )
    run_warnings: list[dict] = []
    runner_mod._step_evaluate(
        cfg=cfg, fetcher=fetcher, csv_path=inputs.csv_path, universe=universe,
        universe_hash=universe_hash, run_now=RUN_NOW, action_session=SESSION,
        lease=_FakeLease(inputs.db_path, 1), price_cache=None, run_warnings=run_warnings,
    )
    return _read_candidates(inputs.db_path), run_warnings


# --------------------------------------------------------------------------- #
# Task 0.1 smoke test: fixtures load, archive serves offline.
# --------------------------------------------------------------------------- #
def test_seeded_archive_serves_without_network(tmp_path, frozen_clock, pin_network):
    inputs = _build_inputs(tmp_path)
    from swing.prices import PriceFetcher
    f = PriceFetcher(cache_dir=inputs.cache_dir, archive_history_days=1260)
    # Served from disk; pin_network proves no network egress.
    df = f.get("AAA", lookback_days=400, as_of_date=None)
    assert not df.empty
    assert df.index.max().date() == SESSION


def test_frozen_clock_session_anchors(frozen_clock):
    """Pin the deterministic date semantics the harness relies on."""
    from swing.evaluation.dates import action_session_for_run, last_completed_session
    assert last_completed_session(RUN_NOW) == SESSION
    assert action_session_for_run(RUN_NOW) == date(2026, 6, 12)


# --------------------------------------------------------------------------- #
# Task 0.2: pin the standalone `swing eval` persisted row-set.
# --------------------------------------------------------------------------- #
def test_cli_path_persists_screen_rows(tmp_path, frozen_clock, pin_network):
    inputs = _build_inputs(tmp_path)
    _make_config(tmp_path, inputs)
    rows = _run_cli_path(tmp_path, inputs)
    by_t = _rows_by_ticker(rows)

    # CLI evaluates the finviz screen ONLY -- HELD/PINNED are absent (DIVERGENCE-1/2).
    assert set(by_t) == set(SCREEN_TICKERS)
    assert HELD_TICKER not in by_t
    assert PINNED_TICKER not in by_t
    # Every screen ticker -> exactly one 'watch' row (observed); close preserved.
    for t in SCREEN_TICKERS:
        row = _one(rows, t)
        assert row["bucket"] == "watch"
        assert row["close"] == pytest.approx(35.14)
        assert row["sector"] == "Technology" and row["industry"] == "Software"
    # AAA is in the RS universe -> rs_method 'universe' with a rank; BBB/CCC fall back.
    assert _one(rows, "AAA")["rs_method"] == "universe"
    assert _one(rows, "AAA")["rs_rank"] == 99
    assert _one(rows, "BBB")["rs_method"] == "fallback_spy"


def test_cli_path_dedups_blocklist_and_fetch_fail(tmp_path, frozen_clock, pin_network):
    """DIVERGENCE-ERROR-DEDUP, CLI side -- POST-Task-C ruling: UNIFY on dedup.

    MIGRATED from the pre-extraction characterization (which pinned the CLI CRASH:
    a blocklisted-AND-fetch-failing ticker produced excluded+error rows that hit
    the candidates UNIQUE(evaluation_run_id, ticker) constraint -> IntegrityError
    -> the whole eval rolled back, exit 1). The operator ruled this UNIFY, so the
    shared orchestrator de-dupes unconditionally and the CLI now matches the
    pipeline: ONE excluded row, exit 0, no crash (compare
    test_pipeline_path_dedups_blocklist_and_fetch_fail -- a parity assertion)."""
    inputs = _build_inputs(tmp_path, include_blocklist_fail=True)
    _make_config(tmp_path, inputs)
    result = _invoke_cli(inputs, tmp_path)
    assert result.exit_code == 0, (result.output, repr(result.exception))
    rows = _read_candidates(inputs.db_path)
    zzz = [r for r in rows if r["ticker"] == BLOCKLIST_FAIL]
    assert len(zzz) == 1
    assert zzz[0]["bucket"] == "excluded"
    assert zzz[0]["close"] is None
    assert zzz[0]["notes"] == "ETF/fund blocklist"


# --------------------------------------------------------------------------- #
# Task 0.3: pin the pipeline _step_evaluate persisted row-set + pin_injection.
# --------------------------------------------------------------------------- #
def test_pipeline_path_persists_screen_plus_augmentation(tmp_path, frozen_clock, pin_network):
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    rows, warnings = _run_pipeline_path(inputs, cfg)
    by_t = _rows_by_ticker(rows)

    # Screen rows present (same three as the CLI).
    assert set(SCREEN_TICKERS).issubset(set(by_t))

    # DIVERGENCE-1: held ticker present as an excluded close-only row.
    held = _one(rows, HELD_TICKER)
    assert held["bucket"] == "excluded"
    assert held["notes"] == "open position"
    # DIVERGENCE-EXCLUDED-CLOSE: held excluded row PRESERVES its fetched close.
    assert held["close"] == pytest.approx(35.14)

    # DIVERGENCE-2: pinned off-screen ticker is FULLY evaluated (not excluded).
    pinned = _one(rows, PINNED_TICKER)
    assert pinned["bucket"] in {"aplus", "watch", "skip"}
    # ... and the pin_injection run-warning fires once with the exact dict shape.
    pin_lines = [w for w in warnings if w.get("kind") == "pin_injection"]
    assert len(pin_lines) == 1
    assert pin_lines[0] == {
        "step": "evaluate", "kind": "pin_injection", "count": 1, "tickers": [PINNED_TICKER],
    }


def test_pipeline_path_dedups_blocklist_and_fetch_fail(tmp_path, frozen_clock, pin_network):
    """DIVERGENCE-ERROR-DEDUP, pipeline side. The pipeline de-dupes error vs
    excluded, so a blocklisted-AND-fetch-failing ticker yields EXACTLY ONE row
    (excluded), close=None -- no IntegrityError (contrast the CLI crash)."""
    inputs = _build_inputs(tmp_path, include_blocklist_fail=True)
    cfg = _make_config(tmp_path, inputs)
    rows, _warnings = _run_pipeline_path(inputs, cfg)
    zzz = [r for r in rows if r["ticker"] == BLOCKLIST_FAIL]
    assert len(zzz) == 1
    assert zzz[0]["bucket"] == "excluded"
    assert zzz[0]["close"] is None
    assert zzz[0]["notes"] == "ETF/fund blocklist"


# --------------------------------------------------------------------------- #
# Task 0.4: single-source divergence inventory + column-by-column parity diff.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Divergence:
    tag: str
    summary: str
    pipeline_side: str
    cli_side: str
    persisted_effect: str
    operator_question: str


# SINGLE SOURCE OF TRUTH (Codex R1 M2): every divergence the harness asserts is
# enumerated here; the Task-C operator checkpoint + the return report consume it.
# The persisted_effect strings are the HARNESS-OBSERVED reality (not code-read).
DIVERGENCES: list[Divergence] = [
    Divergence(
        "DIVERGENCE-1", "open-trades (held) union",
        "held tickers added as excluded close-only rows (HHH observed)",
        "omitted (no held union)",
        "held ticker is pipeline-only in the persisted row-set",
        "Should standalone eval include held tickers (unify) or stay pipeline-only (intentional)?",
    ),
    Divergence(
        "DIVERGENCE-2", "Arc-7 pin injection",
        "pinned off-screen tickers fully evaluated (PPP watch) + pin_injection warning",
        "omitted (predates Arc-7)",
        "pinned ticker is pipeline-only in the persisted row-set",
        "Unify (CLI gains pin injection) or intentional pipeline-only?",
    ),
    Divergence(
        "DIVERGENCE-EQUITY", "current_equity source",
        "sizing_equity(real_equity=current_equity(...), floor) == 7500.0 in fixture",
        "cfg.account.starting_equity == 1200.0",
        "NONE -- shared screen rows are column-identical (equity feeds position "
        "sizing only, which is not a persisted candidate column)",
        "Unify on real-equity sizing, or keep CLI on starting_equity? "
        "(no persisted effect either way)",
    ),
    Divergence(
        "DIVERGENCE-ERROR-DEDUP", "error vs excluded dedup",
        "de-dupes -> ONE excluded row for a blocklisted-AND-failing ticker (ZZZ)",
        "no dedup -> excluded + error rows -> UNIQUE-constraint IntegrityError -> "
        "whole eval rolls back (exit 1, nothing persisted)",
        "ZZZ: pipeline=1 excluded row; CLI=crash. The pipeline dedup PREVENTS the crash.",
        "Unify on dedup? (the CLI's non-dedup is a latent crash, not just extra rows)",
    ),
    Divergence(
        "DIVERGENCE-EXCLUDED-CLOSE", "held excluded-row close",
        "preserves the fetched close on a held excluded row (HHH close=35.14)",
        "always close=None on excluded rows",
        "follows DIVERGENCE-1: held rows are pipeline-only, so the CLI has no held "
        "row to compare; blocklist excluded rows are close=None on BOTH sides",
        "If held rows are unified into the CLI, preserve fetched close or write None?",
    ),
    Divergence(
        "DIVERGENCE-SPY-GUARD", "SPY fetch failure handling",
        "runs SPY fetch straight-line -> a fetch exception RAISES and fails the step",
        "wraps SPY fetch in try/except -> warns + spy_return=0.0, continues (exit 0)",
        "error-path only (success-path spy_return is identical)",
        "Unify on the guarded path, or keep the pipeline hard-failing (intentional)?",
    ),
]

# Pinned from the actual run (characterization, not aspiration).
EXPECTED_PIPE_ONLY = {HELD_TICKER, PINNED_TICKER}
EXPECTED_SHARED_COLUMN_DIVERGENCES: dict[str, set[str]] = {}  # equity is sizing-only


def test_golden_parity_divergences_are_pinned(tmp_path, frozen_clock, pin_network):
    """Run BOTH paths on TWO INDEPENDENT freshly-migrated DBs with IDENTICAL seeds
    + IDENTICAL fixture contents (Codex R1 M1) and compute the row-set + per-column
    delta. Uses the CLEAN fixture (no ZZZ): the blocklist-AND-fail collision is
    characterized separately (it crashes the CLI), so it cannot share a diff run."""
    cli_in = _build_inputs(tmp_path / "cli")
    pipe_in = _build_inputs(tmp_path / "pipe")
    _make_config(tmp_path / "cli", cli_in)
    pipe_cfg = _make_config(tmp_path / "pipe", pipe_in)

    cli_rows = _run_cli_path(tmp_path / "cli", cli_in)
    pipe_rows, _warnings = _run_pipeline_path(pipe_in, pipe_cfg)

    cli_by, pipe_by = _rows_by_ticker(cli_rows), _rows_by_ticker(pipe_rows)
    pipe_only = set(pipe_by) - set(cli_by)
    shared = set(cli_by) & set(pipe_by)

    # DIVERGENCE-1/2: held + pinned are pipeline-only.
    assert pipe_only == EXPECTED_PIPE_ONLY
    assert HELD_TICKER in pipe_only
    assert PINNED_TICKER in pipe_only

    # DIVERGENCE-EQUITY: shared single-row tickers must be column-identical except
    # the pinned expected set (which is empty -> equity has no persisted effect).
    differing: dict[str, set[str]] = {}
    for t in sorted(shared):
        if len(cli_by[t]) != 1 or len(pipe_by[t]) != 1:
            continue
        c, p = cli_by[t][0], pipe_by[t][0]
        for col in c:
            if c[col] != p[col]:
                differing.setdefault(t, set()).add(col)
    assert differing == EXPECTED_SHARED_COLUMN_DIVERGENCES


def test_divergence_inventory_is_complete():
    """Every divergence the harness asserts is enumerated for Task C (Codex R1 M2)."""
    tags = {d.tag for d in DIVERGENCES}
    assert tags == {
        "DIVERGENCE-1", "DIVERGENCE-2", "DIVERGENCE-EQUITY",
        "DIVERGENCE-ERROR-DEDUP", "DIVERGENCE-EXCLUDED-CLOSE", "DIVERGENCE-SPY-GUARD",
    }


# --------------------------------------------------------------------------- #
# Task 0.5: characterize the SPY-failure divergence through the pinned boundary.
# --------------------------------------------------------------------------- #
def test_spy_failure_divergence_is_characterized(tmp_path, frozen_clock, pin_network):
    """DIVERGENCE-SPY-GUARD is an error-path difference the success-path diff
    cannot observe. With SPY UNSEEDED, fetcher.get('SPY') reaches the pinned
    downloader -> deterministic offline raise.

    CLI: catches it -> warns on stderr + persists a run (spy_return 0.0), exit 0.
    Pipeline: runs SPY straight-line -> the fetch exception propagates -> the step
    RAISES (nothing persisted)."""
    cli_in = _build_inputs(tmp_path / "cli", seed_spy=False)
    _make_config(tmp_path / "cli", cli_in)
    cli_result = _invoke_cli(cli_in, tmp_path / "cli")
    assert cli_result.exit_code == 0
    # Observed warning text (cli.py:426): "Warning: SPY benchmark fetch failed ..."
    assert "SPY" in cli_result.output
    assert "benchmark" in cli_result.output
    # The run still persisted the screen rows (spy_return fell back to 0.0).
    assert set(_rows_by_ticker(_read_candidates(cli_in.db_path))) == set(SCREEN_TICKERS)

    pipe_in = _build_inputs(tmp_path / "pipe", seed_spy=False)
    pipe_cfg = _make_config(tmp_path / "pipe", pipe_in)
    # The pinned downloader raises RuntimeError; the pipeline propagates it
    # (straight-line SPY fetch, no try/except) -> the step fails.
    with pytest.raises(RuntimeError):
        _run_pipeline_path(pipe_in, pipe_cfg)


# --------------------------------------------------------------------------- #
# Task 0.5 Step 3: the human-readable divergence inventory artifact (the input
# to the Task-C operator checkpoint). Rendered from the single-source DIVERGENCES
# list so it cannot drift.
# --------------------------------------------------------------------------- #
def render_divergence_inventory() -> str:
    lines = ["# Arc 17-A divergence inventory (Phase-0, harness-observed)\n"]
    for d in DIVERGENCES:
        lines.append(
            f"## {d.tag} -- {d.summary}\n"
            f"- pipeline: {d.pipeline_side}\n"
            f"- cli: {d.cli_side}\n"
            f"- persisted effect: {d.persisted_effect}\n"
            f"- ruling needed: {d.operator_question}\n"
        )
    return "\n".join(lines)


def test_divergence_inventory_artifact_covers_all_tags():
    text = render_divergence_inventory()
    for d in DIVERGENCES:
        assert d.tag in text
        assert d.operator_question in text
