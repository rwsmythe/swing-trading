from __future__ import annotations

import json
from dataclasses import dataclass

_OHLC_KEYS = ("open", "high", "low", "close", "volume", "provider")


@dataclass(frozen=True)
class Bar:
    session: str   # ISO observation_date
    open: float
    high: float
    low: float
    close: float


def parse_bar(ohlc_today_json: str, *, session: str) -> Bar:
    d = json.loads(ohlc_today_json)
    missing = [k for k in _OHLC_KEYS if k not in d]
    if missing:
        raise KeyError(f"ohlc_today_json missing keys: {missing}")
    return Bar(
        session=session,
        open=float(d["open"]), high=float(d["high"]),
        low=float(d["low"]), close=float(d["close"]),
    )
