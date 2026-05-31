"""Read-only per-trade chronology assembly (journal drill-down only).

Merges fills + trade_events + daily_management_records (split by record_type)
+ the trades post-trade-review COLUMNS into one timestamp-sorted stream.
review_log is a CADENCE table with NO trade_id and is EXCLUDED (Codex Re-R1 M#1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime  # WP-R4 M#1: _normalize_ts uses both

from swing.data.repos.fills import list_fills_for_trade

# Tie-break source precedence: lower sorts first on equal timestamps (OQ-5).
_SOURCE_PRECEDENCE = {"fill": 0, "daily_management": 1, "trade_event": 2, "review": 3}


@dataclass(frozen=True)
class ChronologyEntry:
    ts: str                # normalized ISO key (date-only rows -> 'YYYY-MM-DD')
    source: str            # 'fill'|'trade_event'|'daily_management'|'review'
    kind: str
    summary: str
    detail: str | None = None
    ts_malformed: bool = False  # sorts last with a flag, never raises


@dataclass(frozen=True)
class TradeChronology:
    trade_id: int
    entries: tuple[ChronologyEntry, ...] = ()


def _normalize_ts(raw, *, precision: str) -> tuple[str, bool]:
    """Normalize a source timestamp to a sortable ISO key + a malformed flag.

    Codex WP-R3 M#2: missing AND malformed-non-empty timestamps must both be
    handled (the spec sorts them last with a flag). `precision` is 'datetime'
    (fills/events/review) or 'date' (daily_management). Returns
    (iso_key, ts_malformed); a date-only value normalizes to start-of-day so it
    co-sorts with datetimes. Never raises (read-only over operator/legacy data).
    """
    if raw is None or str(raw).strip() == "":
        return ("", True)
    s = str(raw).strip()
    try:
        if precision == "date":
            d = date.fromisoformat(s[:10])
            return (f"{d.isoformat()}T00:00:00", False)
        # datetime: accept ISO 'YYYY-MM-DDTHH:MM:SS' or space-separated
        dt = datetime.fromisoformat(s.replace(" ", "T"))
        return (dt.isoformat(), False)
    except (ValueError, TypeError):
        # Non-empty garbage -> keep the raw for display but flag + sort last.
        return (s, True)


def _fill_entries(conn, trade_id) -> list[ChronologyEntry]:
    out = []
    for f in list_fills_for_trade(conn, trade_id):
        ts_key, malformed = _normalize_ts(f.fill_datetime, precision="datetime")
        out.append(ChronologyEntry(
            ts=ts_key, source="fill", kind=f"fill:{f.action}",
            summary=f"{f.action} {f.quantity} @ {f.price}",
            detail=(f.reason or None), ts_malformed=malformed))
    return out


def _trade_event_entries(conn, trade_id) -> list[ChronologyEntry]:
    # Columns are payload_json + rationale (NO `notes` column) — verified
    # 0003_phase2_pipeline_trades.sql:88-95. event_type CHECK enum:
    # entry/stop_adjust/note/exit/flag.
    rows = conn.execute(
        "SELECT ts, event_type, payload_json, rationale FROM trade_events "
        "WHERE trade_id = ? ORDER BY ts", (trade_id,)).fetchall()
    out = []
    for ts, event_type, payload_json, rationale in rows:
        try:
            payload = json.loads(payload_json) if payload_json else None
        except (ValueError, TypeError):
            payload = None  # best-effort; never raise on operator/legacy data
        detail = rationale or (json.dumps(payload) if payload else None)
        ts_key, malformed = _normalize_ts(ts, precision="datetime")  # WP-R3 M#2
        out.append(ChronologyEntry(
            ts=ts_key, source="trade_event", kind=f"event:{event_type}",
            summary=str(event_type), detail=detail, ts_malformed=malformed))
    return out


def build_trade_chronology(conn, trade_id: int) -> TradeChronology:
    entries: list[ChronologyEntry] = []
    entries += _fill_entries(conn, trade_id)
    entries += _trade_event_entries(conn, trade_id)
    # Task 5.3 adds daily_management + review.
    return TradeChronology(trade_id=trade_id, entries=_sorted(entries))


def _sorted(entries) -> tuple[ChronologyEntry, ...]:
    def key(e):
        # Malformed timestamps sort last; then by ts, then source precedence.
        return (1 if e.ts_malformed else 0, e.ts or "",
                _SOURCE_PRECEDENCE.get(e.source, 99))
    return tuple(sorted(entries, key=key))
