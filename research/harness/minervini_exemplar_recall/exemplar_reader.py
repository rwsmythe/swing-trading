# research/harness/minervini_exemplar_recall/exemplar_reader.py
from __future__ import annotations

import csv as _csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .exceptions import MalformedExemplarRowError
from .ohlcv_reader import tiingo_symbol


@dataclass(frozen=True)
class ExemplarRow:
    exemplar_id: str
    ticker: str
    tiingo_symbol: str
    setup_label: str
    detector_class: str
    entry_anchor: date
    date_precision: str
    buy_point_price: float | None
    source: str
    page: str
    notes: str


def _parse_entry_anchor(entry: str) -> date:
    # Mid-period defaults, identical to tiingo_pull.entry_anchor: missing month -> July,
    # missing day -> 1st.
    parts = entry.split("-")
    y = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 7
    d = int(parts[2]) if len(parts) > 2 else 1
    return date(y, m, d)


def _parse_price(raw: str) -> float | None:
    raw = (raw or "").strip()
    return float(raw) if raw else None


def read_exemplars(csv_path: Path) -> list[ExemplarRow]:
    out: list[ExemplarRow] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            if (row.get("curated") or "").strip().lower() != "yes":
                continue
            eid = (row.get("exemplar_id") or "").strip()
            try:
                anchor = _parse_entry_anchor((row.get("entry_date") or "").strip())
                price = _parse_price(row.get("buy_point_price", ""))
            except (ValueError, IndexError) as exc:
                raise MalformedExemplarRowError(
                    f"exemplar_id={eid!r}: bad entry_date/buy_point_price: {exc}"
                ) from exc
            book = (row.get("ticker") or "").strip()
            out.append(
                ExemplarRow(
                    exemplar_id=eid,
                    ticker=book,
                    tiingo_symbol=tiingo_symbol(book),
                    setup_label=(row.get("setup_label") or "").strip(),
                    detector_class=(row.get("detector_class") or "").strip(),
                    entry_anchor=anchor,
                    date_precision=(row.get("date_precision") or "").strip(),
                    buy_point_price=price,
                    source=(row.get("source") or "").strip(),
                    page=(row.get("page") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return out
