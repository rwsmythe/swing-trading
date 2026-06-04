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
        # FIX-4: kind IS the action (no 'fill:' prefix); summary carries only
        # the VALUES (qty @ price), not the action word — type once, value once.
        out.append(ChronologyEntry(
            ts=ts_key, source="fill", kind=str(f.action),
            summary=f"{f.quantity} @ {f.price}",
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
        # FIX-4: kind IS the bare event_type (no 'event:' prefix + no duplicate
        # summary==event_type). The human rationale becomes the summary; the
        # payload (when present) is the detail — type once, no repeated value.
        ts_key, malformed = _normalize_ts(ts, precision="datetime")  # WP-R3 M#2
        out.append(ChronologyEntry(
            ts=ts_key, source="trade_event", kind=str(event_type),
            summary=(rationale or ""),
            detail=(json.dumps(payload) if payload else None),
            ts_malformed=malformed))
    return out


def _daily_management_entries(conn, trade_id) -> list[ChronologyEntry]:
    # Verified columns (0016_phase8_daily_management.sql). Only is_superseded=0
    # rows (V1 DECIDED: superseded rows EXCLUDED outright). The mixed-case
    # column names (open_MFE_R_to_date / trail_MA_eligibility_flag) are REAL —
    # match case exactly. MFE/MAE are R-multiples (NOT percentages).
    rows = conn.execute(
        "SELECT record_type, review_date, open_MFE_R_to_date, open_MAE_R_to_date, "
        "       maturity_stage, trail_MA_eligibility_flag, trail_MA_candidate_price, "
        "       stop_changed, prior_stop, new_stop, stop_change_reason, "
        "       action_taken, action_reason, thesis_status, "
        "       volume_behavior, relative_strength_status, market_regime_change, "
        "       sector_condition_change, news_or_event_update, management_notes "
        "FROM daily_management_records "
        "WHERE trade_id = ? AND is_superseded = 0 ORDER BY review_date",
        (trade_id,)).fetchall()
    out = []
    for r in rows:
        (rtype, rdate, mfe, mae, maturity, trail_elig, trail_price,
         stop_changed, prior_stop, new_stop, stop_reason,
         action_taken, action_reason, thesis_status,
         vol, rs, regime, sector, news, notes) = r
        ts_key, malformed = _normalize_ts(rdate, precision="date")  # WP-R3 M#2
        if rtype == "daily_snapshot":
            # FIX-4: MFE/MAE (R-multiples) live ONLY in the summary; 'snapshot'
            # is the kind (not repeated in summary). detail carries the
            # remaining context (maturity + trail-MA eligibility, WP-R3 M#3) —
            # NOT a duplicate of the MFE/MAE the summary already shows.
            detail = (f"maturity={maturity}; "
                      f"trail_MA_eligible={trail_elig} (cand={trail_price})")
            out.append(ChronologyEntry(
                ts=ts_key, source="daily_management", kind="snapshot",
                summary=f"MFE {mfe}R / MAE {mae}R",
                detail=detail, ts_malformed=malformed))
        else:  # event_log -- kind precedence over the REAL columns
            # FIX-4: summary never repeats the kind word. action summary is the
            # reason only (the action verb is already the kind); the bare
            # management_event has no redundant "management event" summary.
            if stop_changed == 1:
                kind, summary = "stop_adjust", f"{prior_stop}->{new_stop}"
            elif action_taken not in (None, "no_action"):
                kind, summary = (f"action:{action_taken}",
                                 (action_reason or ""))
            elif thesis_status:
                kind, summary = "thesis", str(thesis_status)
            else:
                kind, summary = "management_event", ""
            # WP-R3 M#3: include volume/RS/regime + management notes in detail.
            detail_bits = [b for b in (
                stop_reason, f"vol={vol}" if vol else None,
                f"rs={rs}" if rs else None,
                f"regime_change={regime}" if regime is not None else None,
                f"sector_change={sector}" if sector is not None else None,
                f"news={news}" if news else None, notes) if b]
            out.append(ChronologyEntry(
                ts=ts_key, source="daily_management", kind=kind, summary=summary,
                detail=("; ".join(str(b) for b in detail_bits) or None),
                ts_malformed=malformed))
    return out


def _review_entry(conn, trade_id) -> list[ChronologyEntry]:
    # Verified trades review columns (models.py): reviewed_at, process_grade,
    # lesson_learned, mistake_tags. B-7: failure_mode is PRAGMA-aware so a pre-v24
    # DB / chronology fixture renders without `no such column: failure_mode`.
    from swing.trades.review import failure_mode_label
    has_fm = "failure_mode" in {
        r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    fm_select = "failure_mode" if has_fm else "NULL AS failure_mode"
    row = conn.execute(
        f"SELECT reviewed_at, process_grade, lesson_learned, mistake_tags, "
        f"{fm_select} FROM trades WHERE id = ? AND reviewed_at IS NOT NULL",
        (trade_id,)).fetchone()
    if not row:
        return []
    reviewed_at, grade, lesson, tags, failure_mode = row
    ts_key, malformed = _normalize_ts(reviewed_at, precision="datetime")
    # WP-R3 M#4: detail carries the full lesson AND the mistake tags. Decode
    # the JSON tag list best-effort into a readable form for display.
    tag_display: str | None = None
    if tags:
        try:
            parsed = json.loads(tags)
            if isinstance(parsed, list):
                tag_display = ", ".join(str(t) for t in parsed)
            else:
                tag_display = str(tags)
        except (ValueError, TypeError):
            tag_display = str(tags)
    # FIX-4: 'review' is the kind (shown once); the summary is the process
    # grade only. The full lesson + mistake tags live ONCE in detail (no
    # duplicated one-line lesson in the summary). B-7: the failure-mode label
    # leads the detail when attributed.
    fm_label = failure_mode_label(failure_mode)
    detail = "; ".join(b for b in (fm_label, lesson, tag_display) if b)
    return [ChronologyEntry(
        ts=ts_key, source="review", kind="review",
        summary=(str(grade) if grade else ""),
        detail=(detail or None), ts_malformed=malformed)]


def build_trade_chronology(conn, trade_id: int) -> TradeChronology:
    entries: list[ChronologyEntry] = []
    entries += _fill_entries(conn, trade_id)
    entries += _trade_event_entries(conn, trade_id)
    entries += _daily_management_entries(conn, trade_id)
    entries += _review_entry(conn, trade_id)
    # review_log is EXCLUDED entirely (cadence table, NO trade_id).
    return TradeChronology(trade_id=trade_id, entries=_sorted(entries))


def _sorted(entries) -> tuple[ChronologyEntry, ...]:
    def key(e):
        # Malformed timestamps sort last; then by ts, then source precedence.
        return (1 if e.ts_malformed else 0, e.ts or "",
                _SOURCE_PRECEDENCE.get(e.source, 99))
    return tuple(sorted(entries, key=key))
