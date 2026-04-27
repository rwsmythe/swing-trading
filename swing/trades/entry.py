"""Trade entry service — wraps repo with cap enforcement + watchlist archival."""
from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass
from enum import Enum

from swing.data.models import Trade, WatchlistArchiveEntry
from swing.data.repos.trades import insert_trade_with_event, list_open_trades
from swing.data.repos.watchlist import (
    archive_watchlist_entry, get_watchlist_entry,
)


class EntryRationale(str, Enum):  # noqa: UP042  (match ExitReason's (str, Enum) pattern)
    """Closed taxonomy for trade-entry rationale (Tranche B-ops Bug 3a, spec §3).

    Values are persisted as plain strings in ``trade_events.rationale``;
    ``EntryRequest.rationale`` stays typed as ``str`` and route/CLI layers
    convert via ``EntryRationale(value)`` before constructing the request.

    Provenance — each value maps either to a concrete repo string or to a
    deliberate operator-vocabulary expansion (spec §3 table):

    * ``aplus-setup`` — repo: ``candidate.bucket == 'aplus'`` +
      ``recommendation == 'today_decision'``.
    * ``near-trigger-breakout`` — repo: ``recommendation == 'near_trigger'``
      combined with a breakout verb.
    * ``vcp-breakout`` — repo: ``candidate.criteria`` contains layer ``'vcp'``.
    * ``pivot-breakout`` — DELIBERATE EXPANSION. Minervini/operator
      base-breakout concept not currently a repo string.
    * ``post-earnings-continuation`` — DELIBERATE EXPANSION.
      Operator-vocabulary gap-up-on-earnings, not a repo string.
    * ``relative-strength`` — DELIBERATE EXPANSION. Minervini/IBD RS-rank
      concept, documented in ``reference/methodology/`` but not a repo string.
    * ``other`` — standard escape hatch; route/CLI require ``notes`` when selected.
    """

    APLUS_SETUP = "aplus-setup"
    NEAR_TRIGGER_BREAKOUT = "near-trigger-breakout"
    VCP_BREAKOUT = "vcp-breakout"
    PIVOT_BREAKOUT = "pivot-breakout"
    POST_EARNINGS_CONTINUATION = "post-earnings-continuation"
    RELATIVE_STRENGTH = "relative-strength"
    OTHER = "other"


_ENTRY_RATIONALE_LABELS: dict[EntryRationale, str] = {
    EntryRationale.APLUS_SETUP: "A+ setup (today's decision)",
    EntryRationale.NEAR_TRIGGER_BREAKOUT: "Near-trigger breakout",
    EntryRationale.VCP_BREAKOUT: "VCP breakout",
    EntryRationale.PIVOT_BREAKOUT: "Pivot breakout (non-VCP)",
    EntryRationale.POST_EARNINGS_CONTINUATION: "Post-earnings gap continuation",
    EntryRationale.RELATIVE_STRENGTH: "Relative strength leadership",
    EntryRationale.OTHER: "Other (see notes)",
}


def entry_rationale_options() -> tuple[tuple[str, str], ...]:
    """Return ``(value, display_label)`` pairs in spec-declared order.

    Template layer consumes this to render the ``<select>`` options.
    """
    return tuple((r.value, _ENTRY_RATIONALE_LABELS[r]) for r in EntryRationale)


class SoftWarnException(Exception):
    """Open count >= soft_warn_open without force=True."""


class HardCapException(Exception):
    """Open count >= hard_cap_open — never bypassable."""


class DuplicateOpenPositionException(Exception):
    """Already an open trade for this ticker."""


@dataclass(frozen=True)
class EntryRequest:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    initial_stop: float
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    rationale: str
    event_ts: str
    # Operator-frozen pre-trade hypothesis (free-text, optional). Default None
    # preserves existing call sites and persists NULL on the trades row.
    hypothesis_label: str | None = None
    # Operator-override label for the chart-pattern flag (free-text,
    # canonicalized at record_entry boundary the same way as
    # hypothesis_label). Default None preserves existing call sites and
    # persists NULL.
    chart_pattern_operator: str | None = None
    # Resolved-at-entry-surface classification snapshot — persisted
    # AS-IS by record_entry (no re-lookup at submit). ToCToU fix per
    # spec §3.6 (R2 M3 + R3 M1): cache resolution happens once at
    # form/CLI render; the resolved values flow through the request and
    # the persisted trade row reflects the operator's view at submit
    # time, not whatever a fresh re-lookup would return.
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None


@dataclass(frozen=True)
class EntryResult:
    trade_id: int
    warning: str | None
    watchlist_archived: bool


def canonicalize_hypothesis_label(raw: str | None) -> str | None:
    """Canonicalize the operator-frozen hypothesis label at the persistence
    boundary so journal-review grouping is invariant to input whitespace,
    embedded control bytes, invisible Unicode format characters, and
    NFC/NFD encoding differences (adversarial review rounds 1 + 2).

    Steps:
      1. Apply Unicode NFC normalization so canonically-equivalent text
         (composed `é` vs decomposed `e + ̀`) yields one stored form.
      2. Drop any character in Unicode category ``Cf`` (format) — zero-width
         space U+200B, ZWJ U+200D, bidi overrides U+202E/U+2066+, etc. —
         which would otherwise let two visually-identical labels group as
         distinct buckets (R2 M1 spoofing concern).
      3. Replace any character in Unicode category ``Cc`` (control: `\\n`,
         `\\r`, `\\t`, NUL, …) with a single space.
      4. Collapse all whitespace runs to a single space.
      5. Strip leading/trailing whitespace.
      6. Empty result → ``None`` (so an all-whitespace input persists as
         NULL, not as an unnamed labeled bucket).

    Operator-typed semantic spacing inside a label is preserved (single
    spaces between words); only artifacts that would split otherwise-
    identical labels into distinct grouping keys are removed.
    """
    if raw is None:
        return None
    nfc = unicodedata.normalize("NFC", raw)
    cleaned_chars = []
    for c in nfc:
        cat = unicodedata.category(c)
        if cat == "Cf":
            continue  # invisible format chars: drop entirely
        if cat == "Cc":
            cleaned_chars.append(" ")  # control bytes: replace with space
        else:
            cleaned_chars.append(c)
    canonical = " ".join("".join(cleaned_chars).split())
    return canonical or None


def record_entry(
    conn: sqlite3.Connection, req: EntryRequest, *,
    soft_warn: int, hard_cap: int, force: bool,
) -> EntryResult:
    if req.initial_stop >= req.entry_price:
        raise ValueError(
            f"stop must be < entry; got entry={req.entry_price}, stop={req.initial_stop}"
        )

    open_trades = list_open_trades(conn)
    if any(t.ticker == req.ticker for t in open_trades):
        raise DuplicateOpenPositionException(
            f"Already an open position in {req.ticker}"
        )

    open_count = len(open_trades)
    if open_count >= hard_cap:
        raise HardCapException(
            f"Hard cap reached: {open_count} >= {hard_cap}"
        )
    warning: str | None = None
    if open_count >= soft_warn:
        if not force:
            raise SoftWarnException(
                f"Open count {open_count} >= soft warn {soft_warn}; use --force"
            )
        warning = f"Soft warn exceeded: {open_count} open positions (soft={soft_warn})"

    trade = Trade(
        id=None, ticker=req.ticker, entry_date=req.entry_date,
        entry_price=req.entry_price, initial_shares=req.shares,
        initial_stop=req.initial_stop, current_stop=req.initial_stop,
        status="open",
        watchlist_entry_target=req.watchlist_entry_target,
        watchlist_initial_stop=req.watchlist_initial_stop,
        notes=req.notes,
        hypothesis_label=canonicalize_hypothesis_label(req.hypothesis_label),
        # Snapshot AS-IS — no re-resolve here (spec §3.6 ToCToU fix).
        # The operator override re-uses canonicalize_hypothesis_label
        # because spec §3.6 specifies identical NFC + control-byte rules
        # for both free-text labels.
        chart_pattern_algo=req.chart_pattern_algo,
        chart_pattern_algo_confidence=req.chart_pattern_algo_confidence,
        chart_pattern_operator=canonicalize_hypothesis_label(req.chart_pattern_operator),
        chart_pattern_classification_pipeline_run_id=req.chart_pattern_classification_pipeline_run_id,
    )

    archived = False
    try:
        with conn:
            trade_id = insert_trade_with_event(
                conn, trade, event_ts=req.event_ts, rationale=req.rationale,
            )
            wl = get_watchlist_entry(conn, req.ticker)
            if wl is not None:
                archive_watchlist_entry(conn, WatchlistArchiveEntry(
                    id=None, ticker=req.ticker, added_date=wl.added_date,
                    removed_date=req.entry_date, reason="entered",
                    qualification_count=wl.qualification_count,
                    last_data_asof_date=wl.last_data_asof_date,
                    notes=wl.notes,
                ))
                archived = True
    except sqlite3.IntegrityError as exc:
        # Schema-level safety net (ux_trades_one_open_per_ticker, migration 0004):
        # two concurrent record_entry calls raced past the app-layer list_open_trades
        # check; the partial unique index rejected the second INSERT. Map to the same
        # DuplicateOpenPositionException callers already handle.
        if "UNIQUE" in str(exc) and "trades" in str(exc):
            raise DuplicateOpenPositionException(
                f"Already an open position in {req.ticker} (race-detected)"
            ) from exc
        raise

    return EntryResult(trade_id=trade_id, warning=warning, watchlist_archived=archived)
