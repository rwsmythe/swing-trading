"""Arc 22-B (Demand A) -- the evidence-bearing assignment of `unintended_execution`.

`unintended_execution` is an execution nobody decided to make (clause (4) of
`docs/training-epoch-intent-contract.md`). It is never inferred from text; it
is assigned ONLY here, with its evidence recorded in `entry_intent_attestations`
under the admissibility test: evidence is admissible iff it was recorded
BEFORE the outcome was known AND is immutable since, verified against the audit
trail. The row's schema is the evidence rule: every predicate `preflight`
checks has an SQL twin trigger in migration 0040 (AUTHORIZE-THEN-ABORT: the
trigger predicate set is a subset of this module's), so a row this module
admits passes SQL, and a row it refuses never reaches SQL.

F4 (CHARC): `preflight` reads only; `assign` REJECTS a caller-held
transaction, opens ONE `BEGIN IMMEDIATE`, establishes the stored envelope
readings FIRST (RULING G1b, below), re-runs `preflight` inside it, INSERTs the
attestation row THEN updates `trades.entry_intent`. Both rows or neither. The
schema enforces that order in both directions (`trg_eia_trade_binding`
requires `trades.entry_intent IS NULL` at the attestation insert; the
unattested twin requires the row at the `trades` update). This module holds NO
attestation-table SQL (CHARC-S3 condition 1): it goes through
`swing.data.repos.entry_intent_attestations`.

The tier is DETECTED, never chosen (F3 + census N1/N5, RD):
  * the fill's order has a `latch_order_mandate_links` row -> `structural`,
    admitted only on a PROVEN death strictly before the fill session
    (`mandate_alive_at`, never a second comparison -- gotcha #31);
  * an order-naming intent with no link -> REFUSE (N5 (b));
  * otherwise tier 2 (`contemporaneous_record`) by the N1 legs: leg 1, the
    telemetry recorded under the actionability instrument; leg 2, the
    placement strictly before the instrument's deployment session.

RULING G1b (CHARC, 2026-09-23; 22-A PERSIST-CANONICAL): ZERO SQL reads of a
fill envelope, no exemption. The order id is the AUTHORITY's STORED reading
(`fill_envelope_identity`), established by `ensure_entry_fill_identities`
inside the write reservation before any read -- rung 6's idiom -- and its
state is the refuse-first. `entry_date` is read ONCE, in Python, from a
document whose stored reading is canonical, and persisted; SQL stores and
bounds that value but never re-reads the envelope. `drift_report` (vi) is the
replay.

Every message is ASCII (the CLI prints it on a cp1252 console).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from swing.data.models import (
    UNINTENDED_EXECUTION,
    EntryIntentAttestation,
    _attestation_date_ok,
    _attestation_iso_seconds_ok,
)
from swing.data.repos.entry_intent_attestations import (
    get_attestation,
    insert_attestation,
)
from swing.data.repos.fill_envelope_identity import (
    EnvelopeIdentityDriftError,
    ensure_entry_fill_identities,
    stored_identity,
)
from swing.data.repos.fills import get_authoritative_entry_fill

CITABLE_FIELDS: tuple[str, ...] = (
    "notes", "why_now", "thesis", "emotional_state_pre_trade")
DESCRIPTIVE_FIELDS: tuple[str, ...] = ("notes", "why_now")
# The `clear_reason` tokens of `swing/latches/service.py` `_STATE_BY_CLEAR_REASON`
# that are DEATHS; the non-death members are `fill` and `superseded`.
# `criteria_lapsed` is unreachable through `mandate_alive_at` (it forces the
# lapse rule OFF) and stays a member as ruled.
DEATH_RUNGS: tuple[str, ...] = (
    "invalidation", "criteria_lapsed", "horizon", "declined")
INSTRUMENT_DEPLOYMENT_SESSION = "2026-08-03"
"""The 21-B prepared-order instrument's deployment SESSION (census N1, RD).

Determined, not estimated: the lower bound is the merge `d5d03bb9`, COMMITTER
date 2026-08-03 01:04 HST; the upper bound is the weekly image
`backups/swing-202632.db` (mtime 2026-08-03 17:30 HST) at schema v33 with
`latch_order_intents` present and 0 rows. Both bounds fall on one calendar
day. The same literal is migration 0040's leg-2 bind and leg-1 window, and
`swing.data.models.ATTESTATION_DEPLOYMENT_SESSION_BOUND`.
"""
ASSIGNMENT_APPLIED_BY = "operator"

# The canonical state token of `fill_envelope_identity.envelope_state`
# (0037's CHECK; `swing.trades.latched_origin.ENVELOPE_CANONICAL`).
_CANONICAL = "canonical"
_TRADE_COLUMNS = ("id", "ticker", "entry_date", "entry_intent", "notes",
                  "why_now", "thesis", "emotional_state_pre_trade")


@dataclass(frozen=True)
class AssignmentResult:
    """The structured answer of `preflight` / `assign`. Never printed here."""

    admitted: bool
    refusal_code: str | None
    message: str | None
    tier: str | None = None
    admitted_leg: str | None = None
    leg_evidence: dict[str, Any] | None = None
    placement_session: str | None = None
    corrections_by_table: dict[str, int] = field(default_factory=dict)
    outcome_known_at: str | None = None
    attestation_id: int | None = None
    attestation: EntryIntentAttestation | None = None


AssignmentVerdict = AssignmentResult


class EnvelopeReadingMissingError(RuntimeError):
    """An envelope-bearing entry fill has NO stored reading after
    `ensure_entry_fill_identities` ran: an invariant breach, never a refusal
    (RULING G1b). `assign` rolls back and re-raises it."""


class _RefusalError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _object_keys(conn: sqlite3.Connection, raw: str | None) -> set[str]:
    """Top-level keys of a JSON object, read the way the trigger reads them."""
    rows = conn.execute(
        "SELECT key FROM json_each(CASE WHEN json_valid(?1) AND "
        "json_type(?1) = 'object' THEN ?1 ELSE '{}' END)", (raw,)).fetchall()
    return {r[0] for r in rows}


def _array_texts(conn: sqlite3.Connection, raw: str | None) -> set[str]:
    rows = conn.execute(
        "SELECT value FROM json_each(CASE WHEN json_valid(?1) "
        "THEN ?1 ELSE '[]' END)", (raw,)).fetchall()
    return {r[0] for r in rows if isinstance(r[0], str)}


def _envelope_absent(raw: object) -> bool:
    """NULL or blank (whitespace-only): no envelope, so no reading is expected."""
    return raw is None or (isinstance(raw, str) and not raw.strip())


def _fill_envelope(conn: sqlite3.Connection, fill_id: int) -> object:
    """The envelope COLUMN of one fill -- its value, never a json_* of it."""
    return conn.execute("SELECT schwab_source_value_json FROM fills "
                        "WHERE fill_id = ?", (fill_id,)).fetchone()[0]


def _envelope_entry_date(raw: str) -> tuple[object, int]:
    """``($.entry_date, how many ROOT entry_date keys)``, read in PYTHON -- the
    one engine that reads the envelope (RULING G1b). Called only on a document
    whose stored reading is canonical, which the canonicaliser decoded with
    this same `json.loads`. The ROOT is the LAST object the hook sees (the
    decoder builds inside-out), the canonicaliser's own idiom."""
    objects: list[list[tuple[str, Any]]] = []

    def _hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        objects.append(list(pairs))
        return dict(pairs)

    payload = json.loads(raw, object_pairs_hook=_hook)
    if not isinstance(payload, dict) or not objects:
        return None, 0
    return (payload.get("entry_date"),
            sum(1 for key, _value in objects[-1] if key == "entry_date"))


# --------------------------------------------------------------------------
# preflight steps, in order; each raises _RefusalError on its first failure
# --------------------------------------------------------------------------
def _source_date_malformed(column: str, where: str, value: object,
                           shape: str) -> _RefusalError:
    return _RefusalError(
        "source_date_malformed",
        f"{column} of {where} is {ascii(value)}, not a {shape} value; the "
        "service compares dates as text, which is sound only over canonical "
        "shapes, so nothing is assigned -- correct the stored value first")


def _check_source_dates(conn: sqlite3.Connection, trade: dict[str, Any]) -> None:
    """RULING G4 (CHARC 2026-09-24): every SOURCE date this service copies or
    compares is shape-checked HERE, in step 1, before any lexical comparison
    and before `EntryIntentAttestation.__post_init__`. Both columns are bare
    `TEXT NOT NULL` at v40 (no shape CHECK), and every comparison downstream is
    bytewise, which is sound only over canonical shapes -- a non-canonical value
    would otherwise yield a MISLABELED refusal or an untyped raise.

    The set, by read: `trades.entry_date` (copied to `trade_entry_date` and the
    fallback placement; compared in `_check_outcome`, `_structural`, E9 and the
    deployment bound) and `fills.fill_datetime` of EVERY fill of the trade --
    the entry fills (`get_authoritative_entry_fill` picks by ORDER BY
    fill_datetime) and the trim/exit/stop fills (`_check_outcome`'s MIN, copied
    to `outcome_known_at`); the fills action CHECK has exactly those four
    values. The shape authority is the attestation's own (`_attestation_date_ok`
    / `_attestation_iso_seconds_ok`): exact length AND a real calendar
    date/time round-trip, so '2026-02-31' is refused as a pattern alone would
    not."""
    entry = trade["entry_date"]
    if not _attestation_date_ok(entry):
        raise _source_date_malformed("trades.entry_date", f"trade {trade['id']}",
                                     entry, "YYYY-MM-DD")
    for fill_id, fill_dt in conn.execute(
            "SELECT fill_id, fill_datetime FROM fills WHERE trade_id = ? "
            "ORDER BY fill_id", (trade["id"],)).fetchall():
        if not _attestation_iso_seconds_ok(fill_dt):
            raise _source_date_malformed(
                "fills.fill_datetime", f"fill {fill_id} (trade {trade['id']})",
                fill_dt, "YYYY-MM-DDTHH:MM:SS")


def _check_trade(conn: sqlite3.Connection, trade_id: int) -> dict[str, Any]:
    from swing.trades.voided_trades import voided_trade_ids

    row = conn.execute(
        f"SELECT {', '.join(_TRADE_COLUMNS)} FROM trades WHERE id = ?",
        (trade_id,)).fetchone()
    if row is None:
        raise _RefusalError("no_trade", f"trade {trade_id} not found")
    trade = dict(zip(_TRADE_COLUMNS, row, strict=True))
    if trade_id in voided_trade_ids(conn):
        raise _RefusalError("voided", f"trade {trade_id} is voided; nothing is "
                       "assigned to a voided trade")
    if trade["entry_intent"] is not None:
        raise _RefusalError(
            "already_set",
            f"trade {trade_id} already carries entry_intent "
            f"'{trade['entry_intent']}'; there is no relabel path -- a "
            "non-empty relabel is a new evidence class with its own record")
    _check_source_dates(conn, trade)
    fill = get_authoritative_entry_fill(conn, trade_id)
    if fill is None:
        raise _RefusalError(
            "no_entry_fill",
            f"trade {trade_id} has no entry fill, so no order can be tied to "
            "it; record the entry fill first")
    trade["entry_fill_id"] = int(fill.fill_id)
    return trade


def _check_citation(trade: dict[str, Any], cite: list[str], reason: str) -> list[str]:
    allowed = ", ".join(CITABLE_FIELDS)
    if not cite:
        raise _RefusalError("not_citable", f"cite at least one of: {allowed}")
    for name in cite:
        if name not in CITABLE_FIELDS:
            raise _RefusalError("not_citable",
                           f"'{name}' is not citable; cite one or more of: {allowed}")
    if len(set(cite)) != len(cite):
        raise _RefusalError("not_citable", "a cited field is named twice")
    if not set(cite) & set(DESCRIPTIVE_FIELDS):
        raise _RefusalError(
            "no_descriptive_field",
            "cite at least one DESCRIPTIVE field (notes or why_now): a tag list "
            "can corroborate an unintended execution but cannot assert one")
    for name in cite:
        text = trade[name]
        if text is None or not str(text).strip():
            raise _RefusalError("empty_cited_field",
                           f"the cited field '{name}' is empty on trade "
                           f"{trade['id']}; cite a field that says something")
    if not isinstance(reason, str) or not reason.strip():
        raise _RefusalError("blank_reason", "the reason is blank; say why this "
                       "execution was one nobody decided to make")
    return sorted(cite)


def _check_audit_trail(conn: sqlite3.Connection, trade_id: int, cite: list[str],
                       counts: dict[str, int]) -> None:
    """P2 over BOTH audit tables (F2 S2 + P2-b). Fills ``counts`` in place so a
    refusal still reports what it found."""
    names = set(cite) | {f"trades.{f}" for f in cite}
    rc_hits: list[tuple[int, str]] = []
    for cid, fname, pre, applied in conn.execute(
            "SELECT correction_id, field_name, pre_correction_value_json, "
            "applied_value_json FROM reconciliation_corrections "
            "WHERE affected_table = 'trades' AND affected_row_id = ? "
            "ORDER BY correction_id", (trade_id,)).fetchall():
        touched = ({fname} | _object_keys(conn, pre)
                   | _object_keys(conn, applied)) & names
        if touched:
            rc_hits.append((int(cid), sorted(touched)[0]))
    pc_hits: list[tuple[int, str]] = []
    for pid, fields in conn.execute(
            "SELECT provenance_correction_id, corrected_fields_json "
            "FROM provenance_corrections WHERE trade_id = ? "
            "ORDER BY provenance_correction_id", (trade_id,)).fetchall():
        touched = _array_texts(conn, fields) & {f"trades.{f}" for f in cite}
        if touched:
            pc_hits.append((int(pid), sorted(touched)[0]))
    counts["reconciliation_corrections"] = len(rc_hits)
    counts["provenance_corrections"] = len(pc_hits)
    for table, hits in (("reconciliation_corrections", rc_hits),
                        ("provenance_corrections", pc_hits)):
        if hits:
            row_id, fname = hits[0]
            raise _RefusalError(
                "cited_field_corrected",
                f"{table} row {row_id} touched {fname}; that text is not "
                "immutable since it was recorded, so it cannot be cited")


def _check_outcome(conn: sqlite3.Connection, trade: dict[str, Any]) -> str | None:
    """P3: the earliest non-entry fill (E2), or None for an open trade."""
    outcome = conn.execute(
        "SELECT MIN(fill_datetime) FROM fills WHERE trade_id = ? "
        "AND action IN ('trim','exit','stop')", (trade["id"],)).fetchone()[0]
    if outcome is not None and not trade["entry_date"] < str(outcome)[:10]:
        raise _RefusalError(
            "outcome_not_after_record",
            f"the outcome (first non-entry fill, {str(outcome)[:10]}) is on the "
            f"entry session {trade['entry_date']}; the record cannot be shown to "
            "pre-date it")
    return outcome


def _structural(conn: sqlite3.Connection, cfg, trade: dict[str, Any],
                order) -> dict[str, Any]:
    """Map `mandate_alive_at`'s verdict by its REAL shape (SS-1). A proven
    death is itself a probe REFUSAL (`mandate_not_alive`); `admitted=True`
    means the mandate was ALIVE at the fill."""
    from swing.trades.latched_origin import mandate_alive_at

    entry = trade["entry_date"]
    verdict = mandate_alive_at(
        conn, cfg, order=order, fill_session=date.fromisoformat(entry),
        exclude_trade_ids=frozenset({int(trade["id"])}))
    rung = verdict.clear_reason
    session = (verdict.clear_session.isoformat()
               if verdict.clear_session is not None else None)
    dates = f"(terminal {rung} on {session}, fill session {entry})"
    if verdict.decline_reason == "mandate_not_alive":
        if rung in DEATH_RUNGS and session is not None and session < entry:
            probe = {
                "decline_reason": verdict.decline_reason,
                "clear_reason": rung,
                "clear_session": session,
                "horizon_session": (verdict.horizon_session.isoformat()
                                    if verdict.horizon_session else None),
                "bars_through": (verdict.bars_through.isoformat()
                                 if verdict.bars_through else None),
                "freeze_tier": verdict.freeze_tier,
                "link_id": int(order.link_id),
                "fire_candidate_id": int(order.candidate_id),
            }
            return {"tier": "structural", "link_id": int(order.link_id),
                    "rung": rung, "session": session, "probe": probe}
        if rung in DEATH_RUNGS:
            raise _RefusalError(
                "death_not_before_fill",
                f"the mandate's death is not strictly before the fill {dates}; "
                "a mandate fill is 'standard' under clause (1)")
        raise _RefusalError(
            "not_a_death_rung",
            f"the cited latch's terminal is not a death rung {dates}: the "
            "mandate was consumed or re-based, not killed, so this fill cannot "
            "be shown to be one nobody decided to make")
    if verdict.admitted:
        if rung in DEATH_RUNGS:
            raise _RefusalError(
                "death_not_before_fill",
                f"the mandate's death is not strictly before the fill {dates}; "
                "a mandate fill is 'standard' under clause (1)")
        raise _RefusalError(
            "mandate_fill",
            f"the mandate was ALIVE at the fill session {entry}; a mandate fill "
            "is 'standard' under clause (1)")
    raise _RefusalError(
        "structural_unprovable",
        f"the structural record cannot prove death-before-fill "
        f"({verdict.decline_reason}); nothing is assigned")


def _pre_rows(conn: sqlite3.Connection, ticker: str,
              placement: str) -> list[dict[str, Any]]:
    """Leg 1's PRE set (R0.H): the ticker's rows recorded under the
    actionability instrument (`date(first_viewed_ts) >= 2026-08-03`) and first
    viewed on or before the placement session. Evaluated in SQL -- the
    trigger's own predicate, one authority."""
    rows = conn.execute(
        "SELECT view_event_id, actionable_ever_viewed, first_viewed_ts, "
        "view_session_date FROM latch_view_events WHERE ticker = ? "
        "AND date(first_viewed_ts) >= ? AND date(first_viewed_ts) <= ? "
        "ORDER BY view_event_id",
        (ticker, INSTRUMENT_DEPLOYMENT_SESSION, placement)).fetchall()
    return [{"view_event_id": int(r[0]), "actionable_ever_viewed": int(r[1]),
             "first_viewed_ts": r[2], "view_session_date": r[3]} for r in rows]


def _detect_tier(conn: sqlite3.Connection, cfg,
                 trade: dict[str, Any]) -> dict[str, Any]:
    from swing.trades.latched_origin import find_accepted_latch_order

    fill_id = trade["entry_fill_id"]
    # Identity came from get_authoritative_entry_fill, which does NOT hydrate
    # the envelope; the envelope is a SEPARATE read of the column.
    raw = _fill_envelope(conn, fill_id)
    order_id = None
    if not _envelope_absent(raw):
        # RULING G1b: the STORED reading of THIS document is the order id and
        # its state is the refuse-first (same authority as
        # envelope_is_canonical, persisted). `assign` ran ensure first.
        reading = stored_identity(conn, fill_id, raw)
        if reading is None:
            raise EnvelopeReadingMissingError(
                f"fill {fill_id} carries a Schwab envelope with no stored "
                "reading after ensure_entry_fill_identities; the order id "
                "cannot be established and nothing is assigned")
        state, order_id, _symbol = reading
        if state != _CANONICAL:
            raise _RefusalError(
                "envelope_refused",
                f"fill {fill_id}'s Schwab envelope is one the authority REFUSED "
                "to read (fill_envelope_identity state "
                f"{str(state)!r}); nothing is assigned on an order identity "
                "that cannot be established")
    ticker, entry = trade["ticker"], trade["entry_date"]
    if order_id is not None:
        links = find_accepted_latch_order(conn, broker_order_id=order_id)
        if len(links) > 1:
            raise _RefusalError("ambiguous_links",
                           f"order {order_id} is named by {len(links)} latch "
                           "links; one order cannot descend from two mandates")
        if links:
            out = _structural(conn, cfg, trade, links[0])
            out["order_id"] = order_id
            return out
        intent = conn.execute(
            "SELECT intent_id FROM latch_order_intents "
            "WHERE actual_broker_order_id = ? ORDER BY intent_id LIMIT 1",
            (order_id,)).fetchone()
        if intent is not None:
            raise _RefusalError(
                "unlinked_intent",
                f"latch intent {intent[0]} names order {order_id} without an "
                "accepted-order link, so it cannot tie this fill to a mandate; "
                "tier 2 cannot apply because the instrument recorded it; the "
                "recovery is a link backfilled under 22-A's rules")
        # ONE engine (RULING G1b): the entry_date is read in Python, from a
        # document whose stored reading is canonical, and persisted.
        placement, keys = _envelope_entry_date(raw)
        if keys > 1:
            # RULING G1d (a): the stored reading does NOT refuse a duplicated
            # entry_date -- the canonicaliser checks duplicates only for the
            # order id and the symbol -- so this read refuses it itself,
            # before json.loads' last-key rule can choose one. Its own code:
            # `envelope_refused` means only "the stored reading is refused".
            raise _RefusalError(
                "entry_date_ambiguous",
                "the record's entered date cannot be read: fill "
                f"{fill_id}'s Schwab envelope carries entry_date {keys} times, "
                "so the placement session is not one value and nothing is "
                "assigned")
        if placement is None:
            placement, source = entry, "entry_date_fallback"
        elif _is_iso_date(placement):
            source = "schwab_envelope"
        else:
            raise _RefusalError(
                "unprovable",
                f"fill {fill_id}'s envelope entry_date {placement!r} is not a "
                "YYYY-MM-DD session, so the placement session is underivable")
    else:
        # E9, fail-closed: with no order id the fill cannot be untied from a
        # recorded order for its ticker.
        recorded = conn.execute(
            "SELECT 1 FROM latch_order_mandate_links WHERE ticker = ?1 "
            "AND detection_date <= ?2 UNION ALL SELECT 1 FROM latch_order_intents "
            "WHERE actual_broker_order_id IS NOT NULL AND ticker = ?1 "
            "AND detection_date <= ?2 LIMIT 1", (ticker, entry)).fetchone()
        if recorded is not None:
            raise _RefusalError(
                "unprovable",
                f"fill {fill_id} carries no broker order id and a recorded order "
                f"for {ticker} exists at or before {entry}; the fill can be "
                "neither tied to it nor untied from it")
        placement, source = entry, "entry_date_fallback"
    pre = _pre_rows(conn, ticker, placement)
    offered = [r for r in pre if r["actionable_ever_viewed"] == 1]
    if offered:
        raise _RefusalError(
            "instrument_offered",
            f"latch_view_events row {offered[0]['view_event_id']} (viewed on or "
            f"before the placement session {placement}): the instrument offered "
            "the order and did not fire; this is not an unintended execution the "
            "record can prove")
    base = {"tier": "contemporaneous_record", "order_id": order_id,
            "placement": placement, "source": source}
    if pre:
        return {**base, "leg": "telemetry", "evidence": {"telemetry_rows": pre}}
    if placement < INSTRUMENT_DEPLOYMENT_SESSION:
        return {**base, "leg": "deployment",
                "evidence": {"deployment_session": INSTRUMENT_DEPLOYMENT_SESSION,
                             "placement_session": placement}}
    raise _RefusalError(
        "instrument_existed",
        f"the placement session {placement} is on or after the instrument's "
        f"deployment session {INSTRUMENT_DEPLOYMENT_SESSION} and no telemetry "
        "speaks: the instrument existed and nothing says it was not offered")


def preflight(
    conn: sqlite3.Connection, cfg, *, trade_id: int, cite: list[str],
    reason: str, now: datetime | None = None,
    applied_by: str = ASSIGNMENT_APPLIED_BY,
) -> AssignmentResult:
    """Decide the assignment of `unintended_execution` to ``trade_id``. READS ONLY.

    The FIRST failing step returns a typed refusal (``refusal_code`` + an ASCII
    ``message`` naming the recovery); an admission carries the built
    attestation row. ``LatchProbeInvariantError`` propagates (an invariant
    breach, never a refusal), as does ``EnvelopeReadingMissingError``: the
    order id is the STORED envelope reading, which ``assign`` establishes
    inside its transaction before calling this (RULING G1b).
    """
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    counts: dict[str, int] = {}
    outcome = None
    try:
        trade = _check_trade(conn, trade_id)
        cited = _check_citation(trade, list(cite), reason)
        _check_audit_trail(conn, trade_id, cited, counts)
        outcome = _check_outcome(conn, trade)
        tier = _detect_tier(conn, cfg, trade)
    except _RefusalError as refusal:
        return AssignmentResult(False, refusal.code, refusal.message,
                                corrections_by_table=counts,
                                outcome_known_at=outcome)
    structural = tier["tier"] == "structural"
    attestation = EntryIntentAttestation(
        attestation_id=None, trade_id=int(trade_id),
        assigned_value=UNINTENDED_EXECUTION, admission_tier=tier["tier"],
        trade_entry_date=trade["entry_date"],
        entry_fill_id=trade["entry_fill_id"],
        entry_fill_id_at_assignment=trade["entry_fill_id"],
        entry_broker_order_id=tier["order_id"],
        placement_session=None if structural else tier["placement"],
        placement_session_source=None if structural else tier["source"],
        admitted_leg=None if structural else tier["leg"],
        leg_evidence_json=None if structural else _dumps(tier["evidence"]),
        cited_latch_link_id=tier["link_id"] if structural else None,
        cited_latch_terminal_rung=tier["rung"] if structural else None,
        cited_latch_terminal_session=tier["session"] if structural else None,
        cited_latch_probe_json=_dumps(tier["probe"]) if structural else None,
        # sorted, default separators -> '["notes", "why_now"]'; the CLI's
        # --cite order never reaches storage
        cited_fields_json=json.dumps(cited),
        cited_text_snapshot_json=_dumps({f: trade[f] for f in cited}),
        audit_trail_checked_at=stamp,
        corrections_touching_cited_fields=0,
        outcome_known_at=outcome,
        reason=reason, applied_at=stamp, applied_by=applied_by,
    )
    return AssignmentResult(
        True, None, None, tier=tier["tier"],
        admitted_leg=None if structural else tier["leg"],
        leg_evidence=tier["probe"] if structural else tier["evidence"],
        placement_session=None if structural else tier["placement"],
        corrections_by_table=counts, outcome_known_at=outcome,
        attestation=attestation)


def _set_trades_value(conn: sqlite3.Connection, trade_id: int) -> None:
    cur = conn.execute(
        "UPDATE trades SET entry_intent = ? WHERE id = ? AND entry_intent IS NULL",
        (UNINTENDED_EXECUTION, trade_id))
    if cur.rowcount != 1:
        raise RuntimeError(
            f"trade {trade_id}: the entry_intent UPDATE touched {cur.rowcount} "
            "rows (expected 1); nothing is committed")


def _write(conn: sqlite3.Connection, attestation: EntryIntentAttestation) -> int:
    """The two-row write in the ORDER the schema enforces: the attestation row
    FIRST, then the `trades` value."""
    attestation_id = insert_attestation(conn, attestation)
    _set_trades_value(conn, attestation.trade_id)
    return attestation_id


def assign(
    conn: sqlite3.Connection, cfg, *, trade_id: int, cite: list[str],
    reason: str, applied_by: str = ASSIGNMENT_APPLIED_BY, dry_run: bool = False,
) -> AssignmentResult:
    """Assign `unintended_execution` with its evidence: both rows or neither.

    REJECTS a caller-held transaction (never auto-detects). The write is ONE
    ``BEGIN IMMEDIATE``: it establishes the stored envelope readings FIRST
    (``ensure_entry_fill_identities``, before any read -- RULING G1b, rung 6's
    idiom; a drift raise becomes the typed refusal ``identity_drift``,
    fail-closed), then re-runs ``preflight`` inside it, so the verdict and the
    write see one world. ``dry_run`` takes the same path and ROLLBACKs it, the
    readings ``ensure`` appended included, so it writes nothing.
    """
    if conn.in_transaction:
        raise RuntimeError(
            "assign() owns its transaction; the caller holds one open. "
            "Nothing was written.")
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            ensure_entry_fill_identities(conn)
        except EnvelopeIdentityDriftError as exc:
            conn.execute("ROLLBACK")
            detail = str(exc).encode("ascii", "backslashreplace").decode("ascii")
            return AssignmentResult(
                False, "identity_drift",
                "a stored envelope reading disagrees with what the authority "
                f"reads out of the same document today ({detail}); the order "
                "identity cannot be trusted, so nothing is assigned")
        verdict = preflight(conn, cfg, trade_id=trade_id, cite=cite,
                            reason=reason, applied_by=applied_by)
        if dry_run or not verdict.admitted:
            conn.execute("ROLLBACK")
            return verdict
        attestation_id = _write(conn, verdict.attestation)
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return AssignmentResult(
        True, None, None, tier=verdict.tier, admitted_leg=verdict.admitted_leg,
        leg_evidence=verdict.leg_evidence,
        placement_session=verdict.placement_session,
        corrections_by_table=verdict.corrections_by_table,
        outcome_known_at=verdict.outcome_known_at,
        attestation_id=attestation_id,
        attestation=get_attestation(conn, trade_id))


def drift_report(conn: sqlite3.Connection, trade_id: int) -> list[str]:
    """What has moved since the attestation (E6). A PURE READ that names what
    it finds; an empty list means every check below ran and found nothing.

    (i) a cited field whose live text differs from the snapshot; (ii) the
    live entry_date differing from the frozen trade_entry_date; (iii) the value
    on `trades` with NO attestation row (written outside the seam); (iv) leg-1
    evidence drift: a snapshotted telemetry row gone or its
    actionable_ever_viewed / first_viewed_ts / view_session_date changed, or the
    PRE set re-derived from live rows no longer the snapshotted ids; (v) the
    entry fill deleted (entry_fill_id NULL) or the authoritative entry fill no
    longer the frozen one; (vi) that fill's envelope order id, or (source
    schwab_envelope) its envelope entry_date, changed.
    """
    trade = conn.execute(
        f"SELECT {', '.join(_TRADE_COLUMNS)} FROM trades WHERE id = ?",
        (trade_id,)).fetchone()
    if trade is None:
        return [f"trade {trade_id} not found"]
    live = dict(zip(_TRADE_COLUMNS, trade, strict=True))
    att = get_attestation(conn, trade_id)
    if att is None:
        if live["entry_intent"] == UNINTENDED_EXECUTION:
            return [f"(iii) trade {trade_id} carries {UNINTENDED_EXECUTION} "
                    "with NO attestation row (written outside the seam)"]
        return []
    out: list[str] = []
    snapshot = json.loads(att.cited_text_snapshot_json)
    for name in sorted(snapshot):
        if live.get(name) != snapshot[name]:
            out.append(f"(i) cited field {name} differs from its snapshot")
    if live["entry_date"] != att.trade_entry_date:
        out.append(f"(ii) entry_date is {live['entry_date']}; the attestation "
                   f"froze {att.trade_entry_date}")
    if att.admitted_leg == "telemetry" and att.leg_evidence_json is not None:
        rows = json.loads(att.leg_evidence_json).get("telemetry_rows", [])
        keys = ("actionable_ever_viewed", "first_viewed_ts", "view_session_date")
        for ev in rows:
            now_row = conn.execute(
                f"SELECT {', '.join(keys)} FROM latch_view_events "
                "WHERE view_event_id = ?", (ev["view_event_id"],)).fetchone()
            if now_row is None:
                out.append(f"(iv) telemetry row {ev['view_event_id']} is gone")
                continue
            for key, value in zip(keys, now_row, strict=True):
                if value != ev[key]:
                    out.append(f"(iv) telemetry row {ev['view_event_id']} "
                               f"{key} changed")
        live_ids = {r["view_event_id"]
                    for r in _pre_rows(conn, live["ticker"], att.placement_session)}
        if live_ids != {ev["view_event_id"] for ev in rows}:
            out.append("(iv) the PRE set re-derived from live rows is not the "
                       "snapshotted set")
    fill = get_authoritative_entry_fill(conn, trade_id)
    if att.entry_fill_id is None:
        out.append(f"(v) the attested entry fill {att.entry_fill_id_at_assignment} "
                   "was deleted")
    elif fill is None or int(fill.fill_id) != att.entry_fill_id_at_assignment:
        out.append("(v) the authoritative entry fill is no longer "
                   f"{att.entry_fill_id_at_assignment}")
    if fill is not None:
        out.extend(_drift_vi(conn, int(fill.fill_id), att))
    return out


def _drift_vi(conn: sqlite3.Connection, fill_id: int,
              att: EntryIntentAttestation) -> list[str]:
    """(vi), in Python over STORED values (RULING G1b): the CURRENT
    authoritative fill's CURRENT stored reading against the frozen order id,
    and (source schwab_envelope) the entry_date re-read from that canonical
    document against the persisted placement -- the replay of the
    service-only derivation. A pure read: it never calls ``ensure``, so a
    document never read is named UNVERIFIED rather than assumed."""
    raw = _fill_envelope(conn, fill_id)
    if _envelope_absent(raw):
        order_id, env_date, keys = None, None, 0
    else:
        reading = stored_identity(conn, fill_id, raw)
        if reading is None:
            return ["(vi) the entry fill's current envelope has no stored "
                    "reading; its order id and entry_date are unverified"]
        if reading[0] != _CANONICAL:
            return ["(vi) the entry fill's current envelope reading is "
                    f"{str(reading[0])!r}; its order id is unverifiable"]
        order_id = reading[1]
        env_date, keys = _envelope_entry_date(raw)
    out: list[str] = []
    if order_id != att.entry_broker_order_id:
        out.append("(vi) the entry fill's order id changed")
    if att.placement_session_source == "schwab_envelope":
        if keys > 1:
            out.append("(vi) the entry fill's envelope carries entry_date "
                       f"{keys} times")
        elif env_date != att.placement_session:
            out.append("(vi) the entry fill's envelope entry_date changed")
    return out
