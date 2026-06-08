# research/scripts/materialize_vicr_yfinance.py
"""One-off: materialize VICR daily bars from yfinance into Tiingo CSV format.

NOT part of the minervini_exemplar_recall harness import graph (L2 LOCK). Run as a
standalone process:  python -m research.scripts.materialize_vicr_yfinance
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_DEFAULT_OUT = Path("research/data/tiingo/VICR.csv")


def materialize(*, out_csv: Path = _DEFAULT_OUT, start: str = "1990-01-01") -> Path:
    import yfinance  # local import: keeps yfinance OUT of any module the harness imports

    raw = yfinance.download("VICR", start=start, auto_adjust=True, progress=False)
    if raw is None or len(raw) == 0:
        raise RuntimeError("yfinance returned no VICR bars; refusing to write an empty archive")

    # yfinance can return MultiIndex columns (Price x Ticker) even for a single ticker (CLAUDE.md
    # gotcha) -> flatten to the OHLCV level first.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    # yfinance auto_adjust=True gives split/dividend-adjusted OHLCV. Emit BOTH raw-named and
    # adj*-named columns so the Tiingo reader (which consumes adj*) works unchanged.
    df = raw.reset_index()
    # The first column after reset_index is the datetime index (named 'Date', or 'index' if unnamed)
    # -> force it to 'date' positionally so we never KeyError on the index label.
    df = df.rename(columns={df.columns[0]: "date"})
    df.columns = ["date" if c == "date" else str(c).lower() for c in df.columns]
    out = pd.DataFrame({
        "date": pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"),
        "close": df["close"], "high": df["high"], "low": df["low"], "open": df["open"], "volume": df["volume"],
        "adjClose": df["close"], "adjHigh": df["high"], "adjLow": df["low"],
        "adjOpen": df["open"], "adjVolume": df["volume"],
    })
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_csv.write_text(out.to_csv(index=False, lineterminator="\n"), encoding="utf-8")

    provenance = (
        f"VICR.csv materialized from yfinance (auto_adjust=True) start={start}\n"
        f"generated_utc={datetime.now(timezone.utc).isoformat()}\n"
        f"rows={len(out)} first={out['date'].iloc[0]} last={out['date'].iloc[-1]}\n"
        "Source: Yahoo Finance via yfinance. Replaces the shallow 1991-11 Tiingo pull.\n"
    )
    (out_csv.parent / "VICR.provenance.txt").write_text(provenance, encoding="utf-8")
    return out_csv


if __name__ == "__main__":
    path = materialize()
    print(f"wrote {path}")
