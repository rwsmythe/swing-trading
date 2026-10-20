"""D90: observe's populate never reaches the Schwab ladder (RD Branch A; plan
AL-4).

T-NS is the discriminating test and the REPLACEMENT for the superseded
`test_observe_remediation.py::test_success_path_overwrites_contaminated_before_lock`
(plan AL-8). It drives the REAL `_step_pattern_observe` over a FRESH real
`OhlcvCache` with a recording ladder hook installed; the store is asserted empty
before the drive, because a store miss is the only road to the hook (CHARC's
anti-vacuity, ledger 1.3).

T-stub pins the shared `_StubOhlcvCache` (S1): the keyword REACHES it and the
populate reports ok (a swallowed `TypeError` would un-memoize D89).

T-D4 is the static closure: of every `.get_or_fetch(` call under `swing/`, only
`_bar_for_date`'s carries `use_ladder`, and it is the literal False.
"""
from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import swing.data.ohlcv_archive as arch
import swing.pipeline.runner as rmod
from swing.data.ohlcv_archive import write_window
from tests.pipeline import conftest_temporal as _ct
from tests.pipeline.conftest_temporal import (
    _build_bars,
    _cfg,
    _FakeLease,
    _plant_detection,
    _StubOhlcvCache,
    _stub_window,
)

tmp_db_at_head = _ct.tmp_db_at_head  # the shared fixture (conftest_temporal)

_OBS = "2026-05-29"
_S = date(2026, 5, 29)
_COLS = ["asof_date", "open", "high", "low", "close", "volume"]


def _test_cfg(tmp_path, db_path):
    # cfg.web / cfg.archive are attached BEFORE OhlcvCache(cfg) is built.
    cfg = _cfg(tmp_path, db_path)
    cfg.web = SimpleNamespace(ohlcv_cache_ttl_seconds=3600,
                              max_concurrent_ohlcv_fetches=4)
    cfg.archive = SimpleNamespace(archive_history_days=1260)
    return cfg


def load(w):
    return next(e for e in w if e.get("metric") == "observe_load")


def test_observe_populate_never_reaches_the_ladder_hook(
        tmp_db_at_head, tmp_path, monkeypatch):
    from swing.web.ohlcv_cache import OhlcvCache

    conn, db_path = tmp_db_at_head
    _plant_detection(conn, ticker="OOT", data_asof_date="2026-05-25",
                     detection_date="2026-05-26")
    cfg = _test_cfg(tmp_path, db_path)
    cache_dir = cfg.paths.prices_cache_dir

    monkeypatch.setattr(arch, "_last_completed_session_today", lambda: _S)
    monkeypatch.setattr("swing.web.ohlcv_cache.last_completed_session",
                        lambda *_a, **_k: _S)
    monkeypatch.setattr(rmod, "last_completed_session", lambda *_a, **_k: _S)
    monkeypatch.setattr(arch, "_load_archive_config_for_stagger", lambda: False)
    arch._full_refresh_stagger_enabled.cache_clear()
    try:
        # A CURRENT legacy archive (no refresh due): the populate downloads
        # nothing, and the legacy rows reach resolve as `yfinance`.
        idx = pd.to_datetime([date(2026, 5, 27), date(2026, 5, 28), _S])
        legacy = pd.DataFrame(
            {c: [8.7, 8.8, 9.0] for c in ("Open", "High", "Low", "Close")},
            index=idx)
        legacy["Volume"] = 1e6
        arch._write_archive_atomic(cache_dir / "OOT.parquet", legacy)
        arch._write_meta_atomic(cache_dir / "OOT.meta.json",
                                {"last_full_refresh_date": "2026-05-29"})
        downloads: list = []
        monkeypatch.setattr(
            arch.yf, "download",
            lambda *a, **k: downloads.append((a, k)) or pd.DataFrame())

        cache = OhlcvCache(cfg)
        hook_calls: list[str] = []

        def hook(t):
            # What the ladder would do on a carry night: persist a schwab_api
            # row for the observation date (it outranks yfinance on read).
            hook_calls.append(t)
            write_window(t, pd.DataFrame(
                [["2026-05-29", 9.5, 9.5, 9.5, 9.5, 1e6]], columns=_COLS),
                "schwab_api", cache_dir=cache_dir)
            return (_build_bars(), "yfinance")

        cache.set_ladder_bars_fetcher(hook)
        real = cache._fetch_bars_window
        seen: list[dict] = []

        def spy(**k):
            seen.append(dict(k))
            return real(**k)

        monkeypatch.setattr(cache, "_fetch_bars_window", spy)

        # Anti-vacuity (CHARC 1.3): a store miss is the only road to the hook.
        assert cache._bars_store == {}
        w: list[dict] = []
        with patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS):
            rmod._step_pattern_observe(
                cfg=cfg, lease=_FakeLease(db_path, 1, _OBS),
                ohlcv_cache=cache, run_warnings=w)
    finally:
        arch._full_refresh_stagger_enabled.cache_clear()

    assert hook_calls == []
    assert seen == [{"ticker": "OOT", "window_days": 400, "use_ladder": False}]
    (row,) = [json.loads(r[0]) for r in conn.execute(
        "SELECT ohlc_today_json FROM pattern_forward_observations")]
    assert row["close"] == 9.0
    assert row["provider"] == "yfinance"
    assert load(w)["fetch_window"] == 1  # the miss happened
    assert not (cache_dir / "OOT.schwab_api.parquet").exists()
    assert downloads == []


def test_shared_stub_records_use_ladder_false_and_the_populate_reports_ok(
        tmp_db_at_head, tmp_path):
    conn, db_path = tmp_db_at_head
    for det_date in ("2026-05-26", "2026-05-27"):
        _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-25",
                         detection_date=det_date)
    cfg = _cfg(tmp_path, db_path)
    cache = _StubOhlcvCache({"AAA": _build_bars()})
    w: list[dict] = []
    with (
        patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
              return_value=_stub_window(9.0, date_=_OBS)),
        patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS),
    ):
        rmod._step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 1, _OBS),
                                   ohlcv_cache=cache, run_warnings=w)
    # The populate runs on every call (D89 D1), each with the literal False.
    assert [c["use_ladder"] for c in cache.calls] == [False, False]
    # The first populate did not raise, so the memo stored its read: a
    # swallowed TypeError would leave populate_ok False and read twice.
    assert load(w)["resolve_reads"] == 1


def _outermost_def(tree):
    for top in tree.body:
        yield getattr(top, "name", "<module>"), top


def test_only_observes_populate_passes_use_ladder():
    root = Path(__file__).resolve().parents[2]
    calls: list[tuple] = []
    for p in sorted((root / "swing").rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        rel = p.relative_to(root).as_posix()
        for name, top in _outermost_def(tree):
            for node in ast.walk(top):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get_or_fetch"):
                    kw = {k.arg: k.value for k in node.keywords}
                    value = kw.get("use_ladder")
                    calls.append((rel, name, None if value is None
                                  else ast.literal_eval(value)))
    # A broken walk must fail, not pass empty (p22: 10 call sites).
    assert len(calls) >= 10
    carrying = [c for c in calls if c[2] is not None]
    assert carrying == [("swing/pipeline/runner.py", "_bar_for_date", False)]
