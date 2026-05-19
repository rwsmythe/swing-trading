"""Pipeline runner — Tranche C T2: evaluation_run_id FK + pipeline_chart_targets.

These integration tests exercise the runner end-to-end against the real DB
schema with monkeypatched yfinance. They assert:

- After `_step_evaluate` runs, `pipeline_runs.evaluation_run_id` is populated.
- After `_step_charts` runs, `pipeline_chart_targets` has one row per ticker
  in scope, with `chart_status` reflecting the per-ticker outcome.
- Fetcher exception → `chart_status='fetcher_failed'`.
- `len(df) < MIN_BARS` (rendering returns None) → `chart_status='too_few_bars'`.
- Successful PNG write → `chart_status='ok'`.
- Source field encodes provenance.

Task 5 (chart-scope policy v2) extends this file with direct `_step_charts`
invocations under a synthetic `_StepChartsCtx` so the 3-tier composition
(aplus / open_position / tag_aware_top_n), precedence-ordered dedup, ticker
canonicalization, and per-tier pivot/stop sourcing can be exercised without
relying on the evaluator's bucket assignment for a synthetic OHLCV ramp
(the evaluator excludes open-trade tickers from candidate buckets, so a
mocked end-to-end `run_pipeline_internal` cannot stage all three tiers).

Mid-run lease revocation behavior is already covered by
`test_runner_detects_mid_run_lease_revocation` — these tests focus on the
new persistence semantics added by Tranche C.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd

from swing.data.db import connect, ensure_schema
from swing.data.models import (
    Candidate,
    CriterionResult,
    EvaluationRun,
    Trade,
    WatchlistEntry,
)
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.pipeline import (
    find_run,
    list_chart_targets,
    set_evaluation_run_id,
)
from swing.data.repos.trades import insert_trade_with_event
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.pipeline.lease import Lease, acquire_lease
from swing.pipeline.runner import _step_charts, run_pipeline_internal


def _ohlcv(closes=None, end="2026-04-15"):
    closes = closes or [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def _csv(inbox: Path) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = (
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    )
    csv.write_text(
        cols + "\n"
        "1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n"
        "2,MSFT,T,S,USA,420.0,1.5%,250000,1.2,4.5,440.0,330.0,3.5e9\n",
        encoding="utf-8",
    )
    return csv


def _seed_active_watchlist_entry(
    db_path: Path, *, ticker: str, entry_target: float, last_close: float,
) -> None:
    """Pre-seed a watchlist entry so the chart step's near-by-proximity
    selector picks it up. The pipeline's _step_watchlist may also add or
    requalify rows — this fixture only guarantees one known row exists."""
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO watchlist
                   (ticker, added_date, last_qualified_date, status,
                    qualification_count, not_qualified_streak,
                    last_data_asof_date, entry_target, initial_stop_target,
                    last_close)
                   VALUES (?, '2026-04-15', '2026-04-15', 'watch', 1, 0,
                           '2026-04-15', ?, NULL, ?)""",
                (ticker, entry_target, last_close),
            )
    finally:
        conn.close()


def _make_cfg(tmp_path: Path):
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def test_step_evaluate_populates_evaluation_run_id(tmp_path: Path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.evaluation_run_id is not None, (
            "pipeline_runs.evaluation_run_id must be populated after "
            "_step_evaluate so the chart-scope resolver can bind structurally"
        )
        # And that FK references a real evaluation_runs row. (We do NOT
        # assert data_asof_date equality with pipeline_runs.data_asof_date —
        # the lease records last_completed_session(now) while the eval
        # records the actual OHLCV max-date, which can legitimately differ
        # in mocked-fetcher tests and in real weekend-edge cases.)
        eval_row = conn.execute(
            "SELECT id FROM evaluation_runs WHERE id = ?",
            (run.evaluation_run_id,),
        ).fetchone()
        assert eval_row is not None
    finally:
        conn.close()


def test_step_charts_writes_chart_targets_with_ok_status(
    tmp_path: Path, monkeypatch,
):
    """Watchlist ticker that gets a PNG written → chart_status='ok',
    source='tag_aware_top_n' (Task 5: legacy 'near_proximity' retired)."""
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL",
        entry_target=180.0, last_close=180.0,
    )

    # Avoid mplfinance dependency in the test env: render_chart returns the
    # path on success, but we monkeypatch it to write a stub PNG so we can
    # test the success branch without mplfinance installed. Phase 3 added a
    # `pattern_overlay` kwarg the runner now passes through; accept and
    # discard.
    def fake_render(
        *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None,
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"stub-png")
        return output_path

    monkeypatch.setattr("swing.pipeline.runner.render_chart", fake_render)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        targets = list_chart_targets(conn, pipeline_run_id=result.run_id)
        assert len(targets) > 0, (
            "chart step must persist at least one pipeline_chart_targets row "
            "when the watchlist near-by-proximity set is non-empty"
        )
        aapl = next(t for t in targets if t.ticker == "AAPL")
        assert aapl.chart_status == "ok"
        assert aapl.source == "tag_aware_top_n"
    finally:
        conn.close()


def test_step_charts_records_fetcher_failed(tmp_path: Path, monkeypatch):
    """Fetcher raising for a chart-step ticker → chart_status='fetcher_failed'.

    The eval step uses lookback_days∈{120,180,365,400}; the chart step uses
    200. We branch on lookback_days so eval still completes but the chart
    fetch raises for AAPL.
    """
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL",
        entry_target=180.0, last_close=180.0,
    )

    def selective_fetcher(self, ticker, lookback_days, *, as_of_date=None):
        if lookback_days == 200 and ticker == "AAPL":
            raise RuntimeError("simulated yfinance outage for chart fetch")
        return _ohlcv()

    monkeypatch.setattr("swing.prices.PriceFetcher.get", selective_fetcher)

    # Phase 13 T1.SB0: `_step_charts` consumes OHLCV via
    # `OhlcvCache.get_or_fetch` (NOT `PriceFetcher.get`). Mirror the
    # selective-raise behavior on the new chart-OHLCV path so this test's
    # AAPL chart fetch still raises while non-AAPL still resolves.
    def selective_cache_fetch(self, *, ticker, window_days):
        if window_days == 200 and ticker == "AAPL":
            raise RuntimeError("simulated yfinance outage for chart fetch")
        return _ohlcv()

    monkeypatch.setattr(
        "swing.web.ohlcv_cache.OhlcvCache.get_or_fetch", selective_cache_fetch,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.render_chart",
        lambda *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None: (
            output_path.parent.mkdir(parents=True, exist_ok=True)
            or output_path.write_bytes(b"stub")
            or output_path
        ),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        targets = list_chart_targets(conn, pipeline_run_id=result.run_id)
        aapl = next(t for t in targets if t.ticker == "AAPL")
        assert aapl.chart_status == "fetcher_failed", (
            f"expected fetcher_failed for AAPL, got {aapl.chart_status!r}"
        )
    finally:
        conn.close()


def test_step_charts_records_too_few_bars(tmp_path: Path, monkeypatch):
    """render_chart returns None when len(df) < MIN_BARS → chart_status='too_few_bars'."""
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL",
        entry_target=180.0, last_close=180.0,
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    def short_render(
        *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None,
    ):
        # Simulate the MIN_BARS short-circuit for AAPL specifically.
        if ticker == "AAPL":
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"stub")
        return output_path

    monkeypatch.setattr("swing.pipeline.runner.render_chart", short_render)

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        targets = list_chart_targets(conn, pipeline_run_id=result.run_id)
        aapl = next(t for t in targets if t.ticker == "AAPL")
        assert aapl.chart_status == "too_few_bars"
    finally:
        conn.close()


def test_step_charts_dedupes_aplus_then_tag_aware(
    tmp_path: Path, monkeypatch,
):
    """If a ticker is both A+ and on the watchlist, only one chart_targets
    row is written; provenance prefers A+ (the chart's primary justification).
    Validates the runner's dedupe policy that protects the (run_id, ticker)
    UNIQUE constraint.

    Task 5: under the 3-tier policy, the watchlist tier emits source
    'tag_aware_top_n' (not the legacy 'near_proximity'). Either provenance is
    legitimate when AAPL doesn't actually pass A+ in the synthetic ramp;
    assert the source is from the post-Task-5 taxonomy."""
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    # Seed AAPL on the watchlist; the fetcher returns long OHLCV so the
    # evaluator may also bucket AAPL as A+. Either way, dedupe must keep one
    # row only.
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL",
        entry_target=180.0, last_close=180.0,
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.render_chart",
        lambda *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None: (
            output_path.parent.mkdir(parents=True, exist_ok=True)
            or output_path.write_bytes(b"stub")
            or output_path
        ),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        targets = list_chart_targets(conn, pipeline_run_id=result.run_id)
        aapl_rows = [t for t in targets if t.ticker == "AAPL"]
        assert len(aapl_rows) == 1, (
            f"dedupe must collapse aplus + tag_aware for the same ticker, "
            f"got {len(aapl_rows)} rows for AAPL"
        )
        # If AAPL was A+, source must be 'aplus' (preferred); otherwise
        # the watchlist tag-aware tier path. Either is fine — assert it's a
        # valid value from the post-Task-5 taxonomy.
        assert aapl_rows[0].source in ("aplus", "tag_aware_top_n")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Task 5 — chart-scope policy v2 — direct `_step_charts` invocation context.
#
# The end-to-end `run_pipeline_internal` flow used by the four tests above
# cannot stage the 3-tier composition discriminating cases: the evaluator
# locally-excludes open-trade tickers from candidate buckets (so an open
# trade ticker can never be 'aplus' via the synthetic OHLCV ramp), and the
# evaluator's bucket logic depends on real Trend Template + VCP passes that
# are non-trivial to coax out of a constant-slope close series. The Task 5
# tests therefore set up a Lease + EvaluationRun + candidates/trades/watchlist
# directly and call `_step_charts` in isolation.
# ---------------------------------------------------------------------------


def _make_aplus_candidate(ticker: str, *, pivot: float, initial_stop: float) -> Candidate:
    """Bucket='aplus' candidate with criteria that produce flag tags
    'A+' + 'TT✓' + 'VCP✓' (sufficient for `_flag_tags` to register the
    full tag tuple). 7+ trend_template passes; all VCP layer rows pass.
    """
    tt_criteria = tuple(
        CriterionResult(
            criterion_name=f"TT{i}",
            layer="trend_template",
            result="pass",
        )
        for i in range(1, 9)  # 8 passes — exceeds the 7-pass threshold
    )
    vcp_criteria = (
        CriterionResult(criterion_name="vcp_prior_trend", layer="vcp", result="pass"),
        CriterionResult(criterion_name="vcp_pullback", layer="vcp", result="pass"),
        CriterionResult(criterion_name="vcp_tightness", layer="vcp", result="pass"),
    )
    return Candidate(
        ticker=ticker, bucket="aplus",
        close=pivot * 0.99, pivot=pivot, initial_stop=initial_stop,
        adr_pct=4.5, tight_streak=3, pullback_pct=10.0, prior_trend_pct=30.0,
        rs_rank=85, rs_return_12w_vs_spy=0.15, rs_method="universe",
        pattern_tag=None, notes=None,
        criteria=tt_criteria + vcp_criteria,
    )


def _make_watch_candidate(ticker: str) -> Candidate:
    """Bucket='watch' candidate with full TT+VCP criteria so it gets the
    'TT✓' + 'VCP✓' flag tags (no 'A+' since bucket != 'aplus'). Used to
    populate `_flag_tags(by_ticker)` when the test wants the watchlist row's
    tag-aware sort key to be non-trivial."""
    tt_criteria = tuple(
        CriterionResult(
            criterion_name=f"TT{i}", layer="trend_template", result="pass",
        )
        for i in range(1, 9)
    )
    vcp_criteria = (
        CriterionResult(criterion_name="vcp_prior_trend", layer="vcp", result="pass"),
        CriterionResult(criterion_name="vcp_pullback", layer="vcp", result="pass"),
        CriterionResult(criterion_name="vcp_tightness", layer="vcp", result="pass"),
    )
    return Candidate(
        ticker=ticker, bucket="watch",
        close=100.0, pivot=None, initial_stop=None,
        adr_pct=4.0, tight_streak=2, pullback_pct=12.0, prior_trend_pct=28.0,
        rs_rank=72, rs_return_12w_vs_spy=0.10, rs_method="universe",
        pattern_tag=None, notes=None,
        criteria=tt_criteria + vcp_criteria,
    )


def _make_untagged_candidate(ticker: str, *, bucket: str = "watch") -> Candidate:
    """Candidate that produces NO flag tags (no TT pass count >= 7, no VCP
    full-pass)."""
    return Candidate(
        ticker=ticker, bucket=bucket,
        close=50.0, pivot=None, initial_stop=None,
        adr_pct=3.0, tight_streak=0, pullback_pct=20.0, prior_trend_pct=20.0,
        rs_rank=50, rs_return_12w_vs_spy=0.0, rs_method="universe",
        pattern_tag=None, notes=None, criteria=(),
    )


def _seed_watchlist_row(
    conn: sqlite3.Connection, *, ticker: str,
    entry_target: float | None, last_close: float | None,
    initial_stop_target: float | None = None,
) -> None:
    entry = WatchlistEntry(
        ticker=ticker, added_date="2026-04-15",
        last_qualified_date="2026-04-15", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-15",
        entry_target=entry_target,
        initial_stop_target=initial_stop_target,
        last_close=last_close, last_pivot=None, last_stop=None,
        last_adr_pct=None, missing_criteria=None, notes=None,
    )
    with conn:
        upsert_watchlist_entry(conn, entry)


def _seed_open_trade(
    conn: sqlite3.Connection, *, ticker: str, entry_price: float,
    current_stop: float,
) -> int:
    trade = Trade(
        id=None, ticker=ticker, entry_date="2026-04-15",
        entry_price=entry_price, initial_shares=10,
        initial_stop=current_stop, current_stop=current_stop,
        state="entered", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )
    with conn:
        return insert_trade_with_event(
            conn, trade, event_ts="2026-04-15T09:30:00",
        )


@dataclass
class _StepChartsCtx:
    cfg: object
    lease: Lease
    eval_run_id: int
    data_asof: str
    fetcher: object
    db_path: Path
    # Helper handles for synthetic-fixture mapping assertions.
    candidates: list[Candidate] = field(default_factory=list)
    open_trade_tickers: list[str] = field(default_factory=list)
    watchlist_data_eligible_only: list[WatchlistEntry] = field(default_factory=list)
    flag_tags: dict = field(default_factory=dict)


def _make_step_charts_ctx(
    tmp_path: Path,
    *,
    candidates: list[Candidate] | None = None,
    open_trades: list[tuple[str, float, float]] | None = None,
    watchlist: list[dict] | None = None,
    chart_top_n_watch: int = 5,  # Pin test default independently of production default (Codex R3 Minor 1)
) -> _StepChartsCtx:
    """Set up the minimum DB state for a direct `_step_charts` invocation:
      - a fresh schema'd DB
      - one running pipeline_runs row (Lease) bound to a fresh evaluation_runs
      - candidates inserted under that eval_run_id
      - trades + watchlist rows seeded as requested
    Returns a context the caller can pass to `_step_charts(...)`.
    """
    cfg = _make_cfg(tmp_path)
    # Pin chart_top_n_watch independently of production default.
    cfg = replace(cfg, pipeline=replace(cfg.pipeline, chart_top_n_watch=chart_top_n_watch))
    data_asof = "2026-04-15"
    action_session = "2026-04-16"
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date=data_asof, action_session_date=action_session,
    )
    candidates = candidates or []
    conn = connect(cfg.paths.db_path)
    try:
        # Insert eval row + candidates inside a lease-fenced write so
        # set_evaluation_run_id can bind atomically.
        with lease.fenced_write() as wconn:
            run = EvaluationRun(
                id=None, run_ts="2026-04-15T21:00:00",
                data_asof_date=data_asof, action_session_date=action_session,
                finviz_csv_path=None,
                tickers_evaluated=len(candidates),
                aplus_count=sum(1 for c in candidates if c.bucket == "aplus"),
                watch_count=sum(1 for c in candidates if c.bucket == "watch"),
                skip_count=0, excluded_count=0, error_count=0,
                rs_universe_version=None, rs_universe_hash=None,
            )
            eval_run_id = insert_evaluation_run(wconn, run)
            if candidates:
                insert_candidates(wconn, eval_run_id, candidates)
            set_evaluation_run_id(
                wconn, pipeline_run_id=lease.run_id,
                evaluation_run_id=eval_run_id,
            )
        # Trades + watchlist outside the fenced write (helpers manage their
        # own `with conn:` transactions).
        trade_tickers: list[str] = []
        for ticker, entry_price, current_stop in (open_trades or []):
            _seed_open_trade(
                conn, ticker=ticker, entry_price=entry_price,
                current_stop=current_stop,
            )
            trade_tickers.append(ticker)
        for w in (watchlist or []):
            _seed_watchlist_row(conn, **w)
    finally:
        conn.close()

    # Build a stub for any ticker so _step_charts doesn't fetcher_fail before
    # reaching the classifier. Phase 13 T1.SB0: _step_charts now consumes
    # OHLCV via ``ohlcv_cache.get_or_fetch``; the stub exposes that surface
    # alongside the legacy ``.get`` for any pre-Phase-13 callers.
    class _StubFetcher:
        def get(self, ticker, lookback_days, *, as_of_date=None):
            return _ohlcv()

        def get_or_fetch(self, *, ticker, window_days):
            return _ohlcv()

    # Compute the data-eligible watchlist + flag_tags so test #8 can recompute
    # expected order against the same shared helper.
    from swing.data.repos.watchlist import list_active_watchlist
    from swing.web.view_models.dashboard import _flag_tags
    conn = connect(cfg.paths.db_path)
    try:
        wl = list_active_watchlist(conn)
    finally:
        conn.close()
    data_eligible = [w for w in wl if w.entry_target and w.last_close]
    by_ticker = {c.ticker: c for c in candidates}
    return _StepChartsCtx(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id, data_asof=data_asof,
        fetcher=_StubFetcher(), db_path=cfg.paths.db_path,
        candidates=list(candidates),
        open_trade_tickers=trade_tickers,
        watchlist_data_eligible_only=data_eligible,
        flag_tags=dict(_flag_tags(by_ticker)),
    )


def _stub_render(monkeypatch, recorder=None):
    """Patch `swing.pipeline.runner.render_chart` to avoid mplfinance and
    optionally record per-call (ticker, pivot, stop)."""
    def fake_render(
        *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None,
    ):
        if recorder is not None:
            recorder.append((ticker, pivot, stop))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png-stub")
        return output_path
    monkeypatch.setattr("swing.pipeline.runner.render_chart", fake_render)


def _query_targets(db_path: Path, run_id: int) -> list[tuple[int, str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        return list(conn.execute(
            """SELECT id, ticker, source FROM pipeline_chart_targets
               WHERE pipeline_run_id = ? ORDER BY id""",
            (run_id,),
        ))
    finally:
        conn.close()


def test_step_charts_emits_three_tier_targets_with_correct_sources(
    tmp_path: Path, monkeypatch,
):
    """A+ candidate (T_APLUS), open trade (T_OPEN), watchlist row tagged for
    top-N (T_WATCH). All three appear in pipeline_chart_targets with distinct
    sources.

    Synthetic-fixture mapping check: candidates contains exactly one 'aplus'
    bucket; list_open_trades returns exactly one trade; watchlist contains
    exactly one tagged-and-data-eligible row. Discriminating verification:
    pre-Task-5 code emits at most A+ + watchlist via 'near_proximity'; T_OPEN
    is missing entirely.
    """
    candidates = [
        _make_aplus_candidate("APLA", pivot=110.0, initial_stop=100.0),
        # Watchlist ticker also gets a candidate row so its flag tags compute.
        _make_watch_candidate("WATC"),
    ]
    ctx = _make_step_charts_ctx(
        tmp_path,
        candidates=candidates,
        open_trades=[("OPEN", 50.0, 45.0)],
        watchlist=[
            dict(ticker="WATC", entry_target=200.0, last_close=199.0,
                 initial_stop_target=190.0),
        ],
    )
    # Synthetic-fixture mapping assertions (per plan discipline).
    assert sum(1 for c in ctx.candidates if c.bucket == "aplus") == 1
    assert ctx.open_trade_tickers == ["OPEN"]
    assert len(ctx.watchlist_data_eligible_only) == 1
    assert ctx.watchlist_data_eligible_only[0].ticker == "WATC"
    assert "WATC" in ctx.flag_tags  # row is tagged

    _stub_render(monkeypatch)
    _step_charts(
        cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
        data_asof=ctx.data_asof, ohlcv_cache=ctx.fetcher,
    )

    rows = _query_targets(ctx.db_path, ctx.lease.run_id)
    by_ticker = {ticker: source for (_id, ticker, source) in rows}
    assert by_ticker == {
        "APLA": "aplus",
        "OPEN": "open_position",
        "WATC": "tag_aware_top_n",
    }, f"got rows={rows}"


def test_step_charts_dedup_precedence_aplus_wins_over_open_position(
    tmp_path: Path, monkeypatch,
):
    """Ticker 'MMMM' (mid-alphabet, defeats compounding-confound) is BOTH an
    A+ candidate AND an open trade. Result: ONE row, source='aplus'.
    """
    candidates = [
        _make_aplus_candidate("MMMM", pivot=80.0, initial_stop=72.0),
    ]
    ctx = _make_step_charts_ctx(
        tmp_path, candidates=candidates,
        open_trades=[("MMMM", 75.0, 70.0)],
    )
    _stub_render(monkeypatch)
    _step_charts(
        cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
        data_asof=ctx.data_asof, ohlcv_cache=ctx.fetcher,
    )
    rows = [r for r in _query_targets(ctx.db_path, ctx.lease.run_id)
            if r[1] == "MMMM"]
    assert len(rows) == 1, f"expected ONE row for MMMM, got {len(rows)}: {rows}"
    assert rows[0][2] == "aplus"


def test_step_charts_dedup_precedence_open_position_wins_over_tag_aware(
    tmp_path: Path, monkeypatch,
):
    """Ticker 'MMMM' is in open_position AND tag_aware_top_n tiers. Result:
    ONE row, source='open_position'."""
    # Only a watch candidate (so flag tags compute) — no A+ for MMMM.
    candidates = [_make_watch_candidate("MMMM")]
    ctx = _make_step_charts_ctx(
        tmp_path, candidates=candidates,
        open_trades=[("MMMM", 60.0, 55.0)],
        watchlist=[
            dict(ticker="MMMM", entry_target=65.0, last_close=64.0,
                 initial_stop_target=58.0),
        ],
    )
    _stub_render(monkeypatch)
    _step_charts(
        cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
        data_asof=ctx.data_asof, ohlcv_cache=ctx.fetcher,
    )
    rows = [r for r in _query_targets(ctx.db_path, ctx.lease.run_id)
            if r[1] == "MMMM"]
    assert len(rows) == 1
    assert rows[0][2] == "open_position"


def test_step_charts_dedup_ticker_in_all_three_tiers_records_aplus(
    tmp_path: Path, monkeypatch,
):
    """Ticker 'MMMM' in all three tiers. Result: ONE row, source='aplus'.
    Spec §A "Edge case: ticker in all three tiers."
    """
    candidates = [_make_aplus_candidate("MMMM", pivot=90.0, initial_stop=82.0)]
    ctx = _make_step_charts_ctx(
        tmp_path, candidates=candidates,
        open_trades=[("MMMM", 85.0, 80.0)],
        watchlist=[
            dict(ticker="MMMM", entry_target=92.0, last_close=91.0,
                 initial_stop_target=84.0),
        ],
    )
    _stub_render(monkeypatch)
    _step_charts(
        cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
        data_asof=ctx.data_asof, ohlcv_cache=ctx.fetcher,
    )
    rows = [r for r in _query_targets(ctx.db_path, ctx.lease.run_id)
            if r[1] == "MMMM"]
    assert len(rows) == 1
    assert rows[0][2] == "aplus"


def test_step_charts_canonicalizes_ticker_case_before_dedup(
    tmp_path: Path, monkeypatch,
):
    """Candidate emits 'AAPL' (upper); trade emits 'aapl' (lower). Both
    should normalize to 'AAPL'. Result: ONE row at upper-case.

    Discriminating verification: pre-canonicalization code adds 'AAPL' and
    'aapl' as DIFFERENT entries in `seen`, producing TWO rows that violate
    the UNIQUE (pipeline_run_id, ticker) constraint and raise IntegrityError.
    """
    candidates = [_make_aplus_candidate("AAPL", pivot=180.0, initial_stop=170.0)]
    ctx = _make_step_charts_ctx(
        tmp_path, candidates=candidates,
        open_trades=[("aapl", 175.0, 168.0)],
    )
    _stub_render(monkeypatch)
    _step_charts(
        cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
        data_asof=ctx.data_asof, ohlcv_cache=ctx.fetcher,
    )
    rows = _query_targets(ctx.db_path, ctx.lease.run_id)
    assert len(rows) == 1, f"expected ONE row after canonical dedup, got {rows}"
    _id, ticker, source = rows[0]
    assert ticker == "AAPL"
    assert source == "aplus"


def test_step_charts_open_position_pivot_from_trades_entry_price(
    tmp_path: Path, monkeypatch,
):
    """Open-position tier sources pivot from `trades.entry_price` and stop
    from `trades.current_stop` (NOT from any watchlist join).

    Synthetic-fixture mapping: seed a trade with entry_price=42.50,
    current_stop=40.00. Watchlist row for MMMM sets entry_target=999.00 as a
    red-herring. Run _step_charts; capture pivot/stop passed to render_chart.
    Pre-fix: ticker enters scope only via the watchlist tier with
    pivot=999.00. Post-fix: open_position tier emits pivot=42.50.
    """
    candidates = [_make_watch_candidate("MMMM")]
    ctx = _make_step_charts_ctx(
        tmp_path, candidates=candidates,
        open_trades=[("MMMM", 42.50, 40.00)],
        watchlist=[
            dict(ticker="MMMM", entry_target=999.00, last_close=950.0,
                 initial_stop_target=900.0),
        ],
    )
    captured: list[tuple[str, float, float]] = []
    _stub_render(monkeypatch, recorder=captured)
    _step_charts(
        cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
        data_asof=ctx.data_asof, ohlcv_cache=ctx.fetcher,
    )
    mmmm_calls = [c for c in captured if c[0] == "MMMM"]
    assert len(mmmm_calls) == 1, f"expected ONE render for MMMM, got {mmmm_calls}"
    _, pivot, stop = mmmm_calls[0]
    assert pivot == 42.50, f"expected entry_price=42.50, got pivot={pivot}"
    assert stop == 40.00, f"expected current_stop=40.00, got stop={stop}"


def test_step_charts_tag_aware_filter_intersection_limit(
    tmp_path: Path, monkeypatch,
):
    """Two watchlist rows: 'GOOD' with entry_target+last_close populated,
    'GAPS' with entry_target=None. Both equally tagged.

    Asserts BOTH 'GAPS not in chart-scope' AND 'GOOD in chart-scope'
    (verified-empirically pin per spec §A R1 Major 3 — proves the tier ran
    and isn't always-empty).
    """
    candidates = [
        _make_watch_candidate("GOOD"),
        _make_watch_candidate("GAPS"),
    ]
    ctx = _make_step_charts_ctx(
        tmp_path, candidates=candidates,
        watchlist=[
            dict(ticker="GOOD", entry_target=100.0, last_close=99.0,
                 initial_stop_target=92.0),
            # GAPS: entry_target missing → must be filtered out by the
            # data-eligible intersection.
            dict(ticker="GAPS", entry_target=None, last_close=99.0,
                 initial_stop_target=None),
        ],
    )
    _stub_render(monkeypatch)
    _step_charts(
        cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
        data_asof=ctx.data_asof, ohlcv_cache=ctx.fetcher,
    )
    tickers = {
        ticker for (_id, ticker, source) in
        _query_targets(ctx.db_path, ctx.lease.run_id)
        if source == "tag_aware_top_n"
    }
    assert "GAPS" not in tickers, (
        "GAPS (entry_target=None) entered chart-scope; "
        "regression: filter-intersection limit not enforced"
    )
    assert "GOOD" in tickers, (
        "GOOD (data-eligible) NOT in chart-scope; "
        "regression: tag-aware tier returned empty (vacuous)"
    )


def _csv_inverted(inbox: Path) -> Path:
    """Inversion-against-alphabetical: AAPL -> Healthcare / Pharmaceuticals;
    ZZZB -> Energy / Oil & Gas E&P. Guards against row-index-vs-ticker
    binding bug (Phase 4 R2 ticker-symmetry class).
    """
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = (
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    )
    csv.write_text(
        cols + "\n"
        "1,AAPL,Healthcare,Pharmaceuticals,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n"
        "2,ZZZB,Energy,Oil & Gas E&P,USA,420.0,1.5%,250000,1.2,4.5,440.0,330.0,3.5e9\n",
        encoding="utf-8",
    )
    return csv


def test_step_evaluate_persists_sector_industry_from_finviz_csv(
    tmp_path: Path, monkeypatch,
):
    """_step_evaluate plumbs Sector + Industry from the Finviz CSV into the
    candidate row. AAPL -> Healthcare / Pharmaceuticals; ZZZB -> Energy /
    Oil & Gas E&P. Inversion-against-alphabetical: a row-index binding bug
    would yield AAPL -> Energy / Oil & Gas E&P (alphabetical-first row
    bound to alphabetical-first ticker).
    """
    cfg = _make_cfg(tmp_path)
    _csv_inverted(cfg.paths.finviz_inbox_dir)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        cands = conn.execute(
            "SELECT ticker, sector, industry FROM candidates "
            "WHERE evaluation_run_id = ? ORDER BY ticker",
            (run.evaluation_run_id,),
        ).fetchall()
        assert (
            "AAPL", "Healthcare", "Pharmaceuticals",
        ) in cands, f"AAPL -> Healthcare/Pharmaceuticals expected, got: {cands}"
        assert (
            "ZZZB", "Energy", "Oil & Gas E&P",
        ) in cands, f"ZZZB -> Energy/Oil & Gas E&P expected, got: {cands}"
    finally:
        conn.close()


def test_step_evaluate_held_position_not_in_csv_persists_empty_sector_industry(
    tmp_path: Path, monkeypatch,
):
    """Held-trade tickers that aren't in the finviz CSV (rotated out of
    screener) get appended to the candidate set via _step_evaluate's
    held_tickers loop with bucket='excluded'. Sector/industry default to
    empty strings (the dict.get(t, ('','')) lookup misses)."""
    cfg = _make_cfg(tmp_path)
    _csv_inverted(cfg.paths.finviz_inbox_dir)
    # Seed an open trade for a ticker NOT in the CSV - appears via held_tickers.
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="HELD", entry_date="2026-04-10",
                entry_price=50.0, initial_shares=10, initial_stop=45.0,
                current_stop=45.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-10T09:30:00")
    finally:
        conn.close()
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        held_row = conn.execute(
            "SELECT bucket, sector, industry FROM candidates "
            "WHERE evaluation_run_id = ? AND ticker = 'HELD'",
            (run.evaluation_run_id,),
        ).fetchone()
        assert held_row is not None, "held-position ticker missing from candidates"
        assert held_row == ("excluded", "", ""), (
            f"held-position ticker should be excluded with empty sector/industry; got {held_row}"
        )
    finally:
        conn.close()


def test_step_evaluate_csv_ticker_with_fetch_failure_keeps_sector_industry(
    tmp_path: Path, monkeypatch,
):
    """A ticker that's in the finviz CSV AND has its OHLCV fetch fail lands
    as bucket='error' - but its sector/industry come from the CSV (the
    post-evaluate_batch dict.get() lookup hits)."""
    cfg = _make_cfg(tmp_path)
    _csv_inverted(cfg.paths.finviz_inbox_dir)

    def selective_fetcher(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "AAPL":
            raise RuntimeError("simulated yfinance outage for AAPL")
        return _ohlcv()

    monkeypatch.setattr("swing.prices.PriceFetcher.get", selective_fetcher)
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        aapl = conn.execute(
            "SELECT bucket, sector, industry FROM candidates "
            "WHERE evaluation_run_id = ? AND ticker='AAPL'",
            (run.evaluation_run_id,),
        ).fetchone()
        assert aapl is not None
        assert aapl[0] == "error"
        # Sector/industry STILL persist from CSV even though OHLCV failed.
        assert aapl[1] == "Healthcare"
        assert aapl[2] == "Pharmaceuticals"
    finally:
        conn.close()


def test_step_charts_tag_aware_uses_shared_sort_key(
    tmp_path: Path, monkeypatch,
):
    """6-row watchlist with diverse tags. Compute expected order via
    `_tag_aware_sort_key` directly. Assert `_step_charts` writes
    'tag_aware_top_n' rows in the EXACT same order (insertion order = sort
    order; `ORDER BY id` retrieves them).

    Discriminating verification: pre-fix code sorted by proximity-only;
    post-fix uses the 4-key composite. With this fixture the proximity-only
    order differs from the tag-aware order, so a regression that drops the
    helper import would fail the order check. Asserts the chart_top_n_watch
    cap is applied (we seed 6 rows; fixture pins cap=5 independently of the
    production default per Codex R3 Minor 1).
    """
    # Seed 6 watchlist rows. Mixed tag profiles: some get full TT+VCP,
    # one gets only TT, one gets nothing.
    candidates = [
        _make_aplus_candidate("AAA", pivot=110.0, initial_stop=100.0),
        _make_watch_candidate("BBB"),  # TT+VCP, no A+
        _make_watch_candidate("CCC"),  # TT+VCP, no A+
        # DDD has only TT pass (1 untagged candidate equivalent —
        # no VCP layer rows means VCP fails the `vcp_total > 0 and pass==total`
        # check, so only TT✓ tag).
    ]
    # Hand-craft a TT-only candidate (8 TT passes, no VCP rows).
    tt_only_criteria = tuple(
        CriterionResult(
            criterion_name=f"TT{i}", layer="trend_template", result="pass",
        )
        for i in range(1, 9)
    )
    candidates.append(Candidate(
        ticker="DDD", bucket="watch", close=100.0, pivot=None,
        initial_stop=None, adr_pct=4.0, tight_streak=2, pullback_pct=12.0,
        prior_trend_pct=28.0, rs_rank=72, rs_return_12w_vs_spy=0.10,
        rs_method="universe", pattern_tag=None, notes=None,
        criteria=tt_only_criteria,
    ))
    candidates.append(_make_untagged_candidate("EEE", bucket="watch"))
    candidates.append(_make_untagged_candidate("FFF", bucket="watch"))

    # Watchlist rows for BBB..FFF (NOT AAA — AAA enters via the aplus tier,
    # so it shouldn't be counted in tag_aware_top_n). Spread proximities so
    # proximity-only sort would produce a different order than the tag-aware
    # composite.
    watchlist = [
        # ticker, entry_target, last_close → proximity = |last-entry|/entry
        dict(ticker="BBB", entry_target=100.0, last_close=99.5),  # 0.005 (TT+VCP)
        dict(ticker="CCC", entry_target=100.0, last_close=98.0),  # 0.020 (TT+VCP)
        dict(ticker="DDD", entry_target=100.0, last_close=99.9),  # 0.001 (TT only)
        dict(ticker="EEE", entry_target=100.0, last_close=99.99), # 0.0001 (no tags)
        dict(ticker="FFF", entry_target=100.0, last_close=99.95), # 0.0005 (no tags)
        # Sixth row: extra TT+VCP at moderate proximity to validate the cap.
        dict(ticker="GGG", entry_target=100.0, last_close=97.0),  # 0.030 (no tags)
    ]
    candidates.append(_make_untagged_candidate("GGG", bucket="watch"))
    ctx = _make_step_charts_ctx(
        tmp_path, candidates=candidates, watchlist=watchlist,
        chart_top_n_watch=5,
    )
    _stub_render(monkeypatch)
    _step_charts(
        cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
        data_asof=ctx.data_asof, ohlcv_cache=ctx.fetcher,
    )

    # Actual order via `ORDER BY id` (insertion order = sort order).
    actual_order = [
        ticker for (_id, ticker, source) in
        _query_targets(ctx.db_path, ctx.lease.run_id)
        if source == "tag_aware_top_n"
    ]
    # Compute expected via the shared helper directly.
    from swing.web.view_models.dashboard import _tag_aware_sort_key
    expected_order_full = [
        w.ticker for w in sorted(
            ctx.watchlist_data_eligible_only,
            key=lambda w: _tag_aware_sort_key(w, ctx.flag_tags),
        )
    ]
    expected_order = expected_order_full[:ctx.cfg.pipeline.chart_top_n_watch]

    assert actual_order == expected_order, (
        f"chart-scope tag_aware order != _tag_aware_sort_key order; "
        f"actual={actual_order} expected={expected_order}"
    )
    # Cap discriminator: test fixture pins chart_top_n_watch=5 (independent of
    # production default per Codex R3 Minor 1); with 6 data-eligible rows,
    # exactly 5 should be written.
    assert len(actual_order) == ctx.cfg.pipeline.chart_top_n_watch
    # Also verify the tag-aware order differs from a proximity-only sort
    # (proves the test would discriminate against a proximity-only regression).
    proximity_only = [
        w.ticker for w in sorted(
            ctx.watchlist_data_eligible_only,
            key=lambda w: abs((w.last_close - w.entry_target) / w.entry_target),
        )
    ][:ctx.cfg.pipeline.chart_top_n_watch]
    assert actual_order != proximity_only, (
        "tag-aware order coincidentally matches proximity-only order — "
        "test does not discriminate. Adjust fixture proximities."
    )
