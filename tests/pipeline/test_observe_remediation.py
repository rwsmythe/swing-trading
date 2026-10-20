# tests/pipeline/test_observe_remediation.py
from datetime import date

import pandas as pd

import swing.data.ohlcv_archive as arch
import swing.pipeline.runner as runner
from swing.data.ohlcv_archive import (
    _shape_a_path,
    _write_archive_atomic,
    write_window,
)
from tests.pipeline.conftest_temporal import _cfg

COLS = ["asof_date", "open", "high", "low", "close", "volume"]


def runner_cfg_stub(tmp_path):
    return _cfg(tmp_path, tmp_path / "swing.db")


def _seed_contaminated_schwab(tmp_path):
    # a pre-fix ext-hours-inflated (high=99) schwab_api row for the obs date.
    _write_archive_atomic(_shape_a_path(tmp_path, "AAPL", "schwab_api"),
                          pd.DataFrame([["2026-06-04", 10, 99, 9, 10.5, 100]],
                                       columns=COLS))


def _cfg_for(tmp_path):
    return runner_cfg_stub(tmp_path)  # supplies paths.prices_cache_dir = tmp_path/ohlcv


# SUPERSEDED BY NAME (D90; RD ruling 20261020T072525Z, CHARC 20261020T072626Z):
# test_success_path_overwrites_contaminated_before_lock pinned observe's populate
# re-fetching a clean schwab_api row for the observation date through the Schwab
# ladder, healing a contaminated one (the seeded case is an ext-hours-inflated
# high). D90 detaches the ladder from observe's populate, so that path is gone.
# The hazard, and what closes it now: (i) the ladder cannot write a NEW
# contaminated schwab_api row -- it requests regular-session candles only
# (needExtendedHoursData=False in swing/integrations/schwab/marketdata.py), and
# every Schwab bar passes OhlcvBar's finite-OHLC check
# (swing/integrations/schwab/models.py) before it reaches the archive;
# (ii) an observe-only ticker gets no schwab_api row from observe after the
# boundary;
# (iii) a detect-pool ticker's row is refetched by detect's own ladder call on
# the next run;
# (iv) a schwab_api row for the CURRENT observation date can predate observe
# only on a carry night, and then only from the same-night ladder writer (RD,
# 20261020T090553Z, B-01 accepted). Replacement: tests/pipeline/test_observe_ladder_detach.py::
# test_observe_populate_never_reaches_the_ladder_hook.


def test_failure_path_then_purge_falls_to_clean_yfinance(tmp_path, monkeypatch):
    """The populate does NOT overwrite the schwab_api row (D90: observe never
    reaches the ladder); the stale contaminated row wins on precedence ->
    _bar_for_date returns it (the residual gap). After the C8 purge removes
    *.schwab_api.parquet, _bar_for_date falls to the clean yfinance row."""
    cfg = _cfg_for(tmp_path)
    cache = cfg.paths.prices_cache_dir
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))
    _seed_contaminated_schwab(cache)
    # a clean yfinance row also exists (lower precedence).
    write_window("AAPL", pd.DataFrame([["2026-06-04", 10, 11, 9, 10.5, 100]],
                                      columns=COLS), "yfinance", cache_dir=cache)

    seen: list[bool] = []

    class _NoOpCache:
        def get_or_fetch(self, *, ticker, window_days, use_ladder):
            seen.append(use_ladder)
            # observe's populate never writes schwab_api (D90) -> no overwrite
            return pd.DataFrame()
    # BEFORE purge: contaminated schwab_api wins.
    bar = runner._bar_for_date(cfg, _NoOpCache(), "AAPL", "2026-06-04")
    assert bar["high"] == 99   # documents the residual gap
    # purge (the C8 belt) -> schwab_api gone -> clean yfinance wins.
    _shape_a_path(cache, "AAPL", "schwab_api").unlink()
    bar2 = runner._bar_for_date(cfg, _NoOpCache(), "AAPL", "2026-06-04")
    assert bar2["high"] == 11 and bar2["provider"] == "yfinance"
    assert seen == [False, False]
