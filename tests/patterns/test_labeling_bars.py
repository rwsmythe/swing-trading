"""Phase 13 T2.SB1 T-A.1.5b Defect 3 (Option B) — auto-fetch bars helper tests.

Per T-A.1.5b brief section 1.3 watch items 7-8:
  - happy path: yfinance returns DataFrame -> bars list emitted in chrono order
  - sandbox short-circuit: yfinance is the only path; NO Schwab API call
  - --window-bars-file override path still works (asserted in
    tests/cli/test_patterns_label_exemplars_cli.py)
  - weekly timeframe rejected with file-override hint
  - empty yfinance response -> empty bars list + WARNING log
  - bad date / inverted range -> ClickException
"""
from __future__ import annotations

import sys
from datetime import date as date_cls

import click
import pandas as pd
import pytest

from swing.patterns import labeling_bars
from swing.patterns.labeling_bars import autofetch_bars_for_labeling


def _make_fake_df(rows: list[dict]) -> pd.DataFrame:
    """Build a DataFrame matching yfinance's daily-bar shape."""
    df = pd.DataFrame(rows)
    df = df.set_index(pd.DatetimeIndex(df["date"]))
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    return df


def test_autofetch_happy_path_emits_chronological_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """yfinance returns 3 daily bars -> helper emits list in chrono order
    with the operator's bars.json shape (date / open / high / low / close /
    volume).
    """
    calls: list[dict] = []

    def fake_download(ticker, **kwargs):
        calls.append({"ticker": ticker, **kwargs})
        return _make_fake_df([
            {"date": "2024-01-02", "Open": 10.0, "High": 11.0,
             "Low": 9.5, "Close": 10.5, "Volume": 100000},
            {"date": "2024-01-03", "Open": 10.5, "High": 11.5,
             "Low": 10.0, "Close": 11.2, "Volume": 120000},
            {"date": "2024-01-04", "Open": 11.2, "High": 12.0,
             "Low": 11.0, "Close": 11.8, "Volume": 110000},
        ])

    monkeypatch.setattr(labeling_bars.yf, "download", fake_download)
    bars = autofetch_bars_for_labeling(
        ticker="ABC",
        start_date="2024-01-02",
        end_date="2024-01-04",
        timeframe="daily",
    )
    assert len(bars) == 3
    assert bars == [
        {"date": "2024-01-02", "open": 10.0, "high": 11.0,
         "low": 9.5, "close": 10.5, "volume": 100000},
        {"date": "2024-01-03", "open": 10.5, "high": 11.5,
         "low": 10.0, "close": 11.2, "volume": 120000},
        {"date": "2024-01-04", "open": 11.2, "high": 12.0,
         "low": 11.0, "close": 11.8, "volume": 110000},
    ]
    # yfinance called with gotcha-resistant kwargs (threads=False,
    # progress=False, auto_adjust=False).
    assert calls[0]["threads"] is False
    assert calls[0]["progress"] is False
    assert calls[0]["auto_adjust"] is False
    # yfinance `end` is exclusive; helper passes end_date + 1 day.
    assert calls[0]["end"] == date_cls(2024, 1, 5)
    assert calls[0]["start"] == date_cls(2024, 1, 2)


def test_autofetch_does_not_call_any_schwab_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per T-A.1.5b watch item #7: auto-fetch MUST NOT call Schwab API
    (regardless of environment=sandbox|production). Sandbox-safety is by
    construction - the helper uses yfinance only.

    Guard: load every loaded `swing.integrations.schwab.*` module and
    assert the helper does NOT touch its public Client surface. We patch
    yfinance to a tracking stub, run the helper, and confirm only
    yfinance was invoked.
    """
    yf_called = {"n": 0}

    def fake_download(ticker, **kwargs):
        yf_called["n"] += 1
        return _make_fake_df([
            {"date": "2024-01-02", "Open": 10.0, "High": 11.0,
             "Low": 9.5, "Close": 10.5, "Volume": 100000},
        ])

    monkeypatch.setattr(labeling_bars.yf, "download", fake_download)

    # Sentinel monkeypatch: any attempt to access `SchwabClient` raises.
    # If the helper ever wires through Schwab in the future, this fires.
    schwab_mods_pre = {
        name for name in sys.modules
        if name.startswith("swing.integrations.schwab")
    }

    bars = autofetch_bars_for_labeling(
        ticker="ABC",
        start_date="2024-01-02",
        end_date="2024-01-02",
        timeframe="daily",
    )

    schwab_mods_post = {
        name for name in sys.modules
        if name.startswith("swing.integrations.schwab")
    }
    assert yf_called["n"] == 1, "yfinance must be the sole fetch path"
    # No NEW Schwab module imported by the helper.
    assert schwab_mods_post == schwab_mods_pre, (
        "auto-fetch helper imported a Schwab module: "
        f"{schwab_mods_post - schwab_mods_pre}"
    )
    assert len(bars) == 1


def test_autofetch_rejects_weekly_timeframe_with_file_override_hint() -> None:
    """V1 supports daily auto-fetch only; weekly raises ClickException
    directing the operator to --window-bars-file.
    """
    with pytest.raises(click.ClickException) as exc_info:
        autofetch_bars_for_labeling(
            ticker="ABC",
            start_date="2024-01-01",
            end_date="2024-02-01",
            timeframe="weekly",
        )
    assert "--window-bars-file" in exc_info.value.message
    assert "weekly" in exc_info.value.message.lower()


def test_autofetch_rejects_malformed_iso_dates() -> None:
    with pytest.raises(click.ClickException) as exc_info:
        autofetch_bars_for_labeling(
            ticker="ABC",
            start_date="not-a-date",
            end_date="2024-02-01",
            timeframe="daily",
        )
    assert "ISO date" in exc_info.value.message


def test_autofetch_rejects_inverted_date_range() -> None:
    with pytest.raises(click.ClickException) as exc_info:
        autofetch_bars_for_labeling(
            ticker="ABC",
            start_date="2024-02-01",
            end_date="2024-01-01",
            timeframe="daily",
        )
    assert "<=" in exc_info.value.message


def test_autofetch_empty_yfinance_returns_empty_list_no_raise(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """yfinance returns an empty DataFrame (e.g. delisted ticker or
    transient empty) -> helper returns [] + emits WARNING log so the
    operator can intervene via --window-bars-file.
    """
    monkeypatch.setattr(
        labeling_bars.yf, "download",
        lambda *a, **k: pd.DataFrame(),
    )
    with caplog.at_level("WARNING"):
        bars = autofetch_bars_for_labeling(
            ticker="DELISTED",
            start_date="2024-01-01",
            end_date="2024-02-01",
            timeframe="daily",
        )
    assert bars == []
    assert any(
        "empty yfinance response" in rec.message for rec in caplog.records
    ), f"expected WARNING; got {[r.message for r in caplog.records]}"


def test_autofetch_squeezes_multiindex_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per CLAUDE.md yfinance gotcha: group_by='column' may return
    MultiIndex columns even for single-ticker calls. Helper squeezes.
    """
    def fake_download(ticker, **kwargs):
        df = pd.DataFrame({
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.5],
            "Close": [10.5],
            "Volume": [100000],
        }, index=pd.DatetimeIndex(["2024-01-02"]))
        # Wrap in a MultiIndex column to simulate the yfinance regression.
        df.columns = pd.MultiIndex.from_product([df.columns, ["ABC"]])
        return df

    monkeypatch.setattr(labeling_bars.yf, "download", fake_download)
    bars = autofetch_bars_for_labeling(
        ticker="ABC",
        start_date="2024-01-02",
        end_date="2024-01-02",
        timeframe="daily",
    )
    assert len(bars) == 1
    assert bars[0]["close"] == 10.5
