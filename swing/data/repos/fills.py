"""Fills repo — canonical execution log replacing exits.

Phase 7 introduces fills as the single source of truth for trade
execution events. Every insert recomputes the trade's aggregate denorm
columns (current_size, current_avg_cost, last_fill_at) in the same
transaction; the caller wraps with `with conn:`.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime as _datetime

from swing.data.models import Fill


def insert_fill_with_event(
    conn: sqlite3.Connection, fill: Fill, *,
    event_ts: str, rationale: str | None = None,
    emit_event: bool = True,
) -> int:
    """Insert a fill, recompute trade aggregates, write a trade_events row.

    All in caller's transaction. Returns the new fill_id.

    Hotfix 2026-05-05: ``emit_event`` flag added to suppress the trade_events
    row for callers that already emitted one. ``record_entry`` calls both
    ``insert_trade_with_event`` (writes 'entry' event) AND this function
    (would also write 'entry' event since fill.action=='entry'); operator-
    witnessed verification gate caught the duplicate ('entry' rows id=12 +
    id=13 for GPRE entry on 2026-05-05). Pass ``emit_event=False`` from the
    record_entry atomic flow to suppress the second emission. Other callers
    (record_exit, etc.) keep the default (True) since their fills are the
    only event-emitters in their atomic flow.
    """
    # Phase 13 T2.SB1 (migration 0020) + T-B.1.4 — auto-fill provenance
    # audit columns. Per spec §6.4 + plan §G.2 T-B.1.4 + CLAUDE.md
    # "Schema-CHECK + Python-constant + dataclass-validator paired"
    # gotcha — the Fill dataclass __post_init__ validates fill_origin
    # against ``_FILL_ORIGIN_VALUES`` BEFORE this INSERT fires, so a
    # tampered value is rejected up-stack.
    #
    # Schema-version compatibility: pre-v20 fixtures (tests using
    # ``run_migrations(target_version<20)``) lack the 4 new fills
    # columns. Detect via ``PRAGMA table_info`` and emit the legacy
    # 11-column INSERT path so existing pre-v20 fixtures keep working.
    # The schema CHECK on fill_origin is only present at v20+, so the
    # legacy path simply omits the columns + the DB schema defaults
    # them (NULL for the 3 JSON cols; no DEFAULT for fill_origin on
    # pre-v20 schemas — it doesn't exist as a column).
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(fills)").fetchall()
    }
    if "fill_origin" in cols:
        cur = conn.execute(
            """
            INSERT INTO fills
                (trade_id, fill_datetime, action, quantity, price, reason,
                 rule_based, fees, manual_entry_confidence,
                 reconciliation_status, tos_match_id,
                 fill_origin, schwab_source_value_json,
                 operator_corrected_value_json, auto_fill_audit_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fill.trade_id, fill.fill_datetime, fill.action,
                fill.quantity, fill.price, fill.reason, fill.rule_based,
                fill.fees, fill.manual_entry_confidence,
                fill.reconciliation_status, fill.tos_match_id,
                fill.fill_origin, fill.schwab_source_value_json,
                fill.operator_corrected_value_json,
                fill.auto_fill_audit_at,
            ),
        )
    else:
        cur = conn.execute(
            """
            INSERT INTO fills
                (trade_id, fill_datetime, action, quantity, price, reason,
                 rule_based, fees, manual_entry_confidence,
                 reconciliation_status, tos_match_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fill.trade_id, fill.fill_datetime, fill.action,
                fill.quantity, fill.price, fill.reason, fill.rule_based,
                fill.fees, fill.manual_entry_confidence,
                fill.reconciliation_status, fill.tos_match_id,
            ),
        )
    fill_id = int(cur.lastrowid)

    _recompute_aggregates(conn, fill.trade_id)

    if emit_event:
        payload = {
            "action": fill.action,
            "quantity": fill.quantity,
            "price": fill.price,
            "fill_datetime": fill.fill_datetime,
        }
        # Map fill action to trade_events.event_type ('entry'/'exit' for now;
        # 'trim' and 'stop' co-opt 'exit' on the audit row since the existing
        # trade_events enum doesn't have separate trim/stop values, and we're
        # not expanding it in 0014 beyond pre_trade_edit).
        audit_event_type = "entry" if fill.action == "entry" else "exit"
        conn.execute(
            """
            INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                fill.trade_id, event_ts, audit_event_type,
                json.dumps(payload, sort_keys=True), rationale,
            ),
        )
    return fill_id


def _recompute_aggregates(conn: sqlite3.Connection, trade_id: int) -> None:
    """Update trades.current_size + current_avg_cost + last_fill_at from fills.

    Single write path; consistency invariant: current_size = sum(entry qty)
    - sum(trim/exit/stop qty).
    V1: current_avg_cost == entry_price (single entry-fill per trade);
    formula reads the authoritative entry-fill price.
    """
    conn.execute(
        """
        UPDATE trades SET
          current_size = COALESCE((
            SELECT SUM(CASE WHEN action = 'entry' THEN quantity ELSE -quantity END)
            FROM fills WHERE fills.trade_id = ?
          ), 0),
          current_avg_cost = (
            SELECT price FROM fills
            WHERE fills.trade_id = ? AND action = 'entry'
            ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1
          ),
          last_fill_at = (
            SELECT MAX(fill_datetime) FROM fills WHERE fills.trade_id = ?
          )
        WHERE id = ?
        """,
        (trade_id, trade_id, trade_id, trade_id),
    )


def update_fill_datetime(
    conn: sqlite3.Connection, *, fill_id: int, fill_datetime: str,
) -> None:
    """UPDATE fills.fill_datetime ONLY, for ONE fill. Caller owns the tx.

    Item-5 T2 -- the entry-date correction surface's only `fills` writer.
    Narrow + literal SQL (no interpolated identifier): the operator supplies a
    DATE, never a field name.

    The caller MUST call `_recompute_aggregates` afterwards. Moving a fill's
    datetime can move `trades.last_fill_at` (MAX over fills) and
    `trades.current_avg_cost` (the entry fill ORDER BY fill_datetime ASC
    re-sort), and this writer deliberately does neither so the caller can read
    pre-values, recompute, and read post-values in one auditable order.

    A missing fill_id raises ValueError -- silence here would let a correction
    report success having written nothing.
    """
    if not isinstance(fill_datetime, str) or not fill_datetime.strip():
        raise ValueError("fill_datetime must be a non-empty ISO string")
    candidate = fill_datetime.strip()
    # The COLUMN is a bare `TEXT NOT NULL`, so a malformed value is
    # schema-legal, and downstream readers slice `[:10]` and compare
    # LEXICALLY. Enforce a real ISO datetime whose first ten characters ARE
    # its calendar date, independently of any service-layer check -- a write
    # boundary that trusts its caller is not a boundary.
    try:
        _parsed = _datetime.fromisoformat(candidate)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"fill_datetime must be a parseable ISO datetime; got "
            f"{candidate!r}") from exc
    if candidate[:10] != _parsed.date().isoformat():
        raise ValueError(
            f"fill_datetime must be EXTENDED-format YYYY-MM-DD...; got "
            f"{candidate!r}")
    cur = conn.execute(
        "UPDATE fills SET fill_datetime = ? WHERE fill_id = ?",
        (fill_datetime.strip(), fill_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"fill {fill_id} not found")


def get_authoritative_entry_fill(
    conn: sqlite3.Connection, trade_id: int,
) -> Fill | None:
    """Per spec §4.3.1: first entry-fill by (fill_datetime ASC, fill_id ASC)."""
    row = conn.execute(
        """
        SELECT fill_id, trade_id, fill_datetime, action, quantity, price,
               reason, rule_based, fees, manual_entry_confidence,
               reconciliation_status, tos_match_id
        FROM fills
        WHERE trade_id = ? AND action = 'entry'
        ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1
        """,
        (trade_id,),
    ).fetchone()
    if row is None:
        return None
    return Fill(*row)


def list_fills_for_trade(
    conn: sqlite3.Connection, trade_id: int,
) -> list[Fill]:
    rows = conn.execute(
        """
        SELECT fill_id, trade_id, fill_datetime, action, quantity, price,
               reason, rule_based, fees, manual_entry_confidence,
               reconciliation_status, tos_match_id
        FROM fills
        WHERE trade_id = ?
        ORDER BY fill_datetime ASC, fill_id ASC
        """,
        (trade_id,),
    ).fetchall()
    return [Fill(*r) for r in rows]


def list_all_fills(conn: sqlite3.Connection) -> list[Fill]:
    """All fills across all trades, sorted by (fill_datetime ASC, fill_id ASC).

    Phase 7 Sub-C T1: introduced for web view-model consumers migrating
    away from the legacy ``list_all_exits`` shim in
    ``swing.data.repos.trades``. Cross-trade ordering uses the same
    (fill_datetime, fill_id) key as ``list_fills_for_trade`` for
    consistency.
    """
    rows = conn.execute(
        """
        SELECT fill_id, trade_id, fill_datetime, action, quantity, price,
               reason, rule_based, fees, manual_entry_confidence,
               reconciliation_status, tos_match_id
        FROM fills
        ORDER BY fill_datetime ASC, fill_id ASC
        """,
    ).fetchall()
    return [Fill(*r) for r in rows]
