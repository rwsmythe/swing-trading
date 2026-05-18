"""ASCII table renderer for journal-vs-Schwab comparison pairs.

Phase 12.5 Q2 — Task T-Q2.1.

Renders a list of ``(field_label, journal_value, schwab_value)`` tuples as a
compact ASCII-only comparison table suitable for CLI output.

ASCII-only invariant
--------------------
Windows PowerShell defaults to the cp1252 encoding.  Any non-ASCII character
flowing through ``print()`` / ``click.echo()`` raises ``UnicodeEncodeError``
and crashes the CLI (CLAUDE.md gotcha: "Windows PowerShell stdout defaults to
cp1252").  Every character emitted by this module has ``ord(c) < 128``.
Non-ASCII characters in caller-supplied values are replaced with ``?`` before
rendering.

Sibling modules (same package, parallel purpose)
-------------------------------------------------
- ``swing.trades.reconciliation_classifier``   -- classify discrepancy tier
- ``swing.trades.reconciliation_validators``   -- dry-run validators
- ``swing.trades.reconciliation_auto_correct`` -- apply corrections

Pure-function discipline
------------------------
This module contains ZERO database calls, ZERO Schwab API calls, ZERO file I/O,
and ZERO logging calls.  All functions are deterministic given their inputs.
No global mutable state.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

__all__ = [
    "render_journal_schwab_comparison_table_ascii",
    "build_compared_pairs",
]

# Maximum rendered width (chars) of any single cell value before truncation.
_CELL_CAP: int = 40

# Truncation suffix appended when a cell value is clipped.
_ELLIPSIS: str = "..."


def _sanitize(raw: str) -> str:
    """Replace every non-ASCII character in *raw* with ``'?'``.

    Guarantees that the returned string is printable on any cp1252 terminal.
    """
    return "".join(c if ord(c) < 128 else "?" for c in raw)


def _format_value(value: Any) -> str:
    """Convert *value* to an ASCII-safe, human-readable string.

    Formatting rules (applied in order):
    - ``None``                   -> ``"-"``
    - ``float`` / ``Decimal``    -> ``f"{value:.2f}"``
    - ``bool`` (subclass of int) -> ``str(value)``  (must precede int branch)
    - ``int``                    -> ``str(value)``
    - ``str``                    -> the string itself (sanitized separately)
    - anything else              -> ``repr(value)``

    The result is then sanitized (non-ASCII -> ``?``) and truncated to
    ``_CELL_CAP`` characters with ``...`` suffix.
    """
    if value is None:
        return "-"
    if isinstance(value, bool):
        # bool is a subclass of int; handle first so True/False are preserved.
        rendered = str(value)
    elif isinstance(value, (float, Decimal)):
        rendered = f"{value:.2f}"
    elif isinstance(value, int):
        rendered = str(value)
    elif isinstance(value, str):
        rendered = value
    else:
        rendered = repr(value)

    # Sanitize: replace non-ASCII with '?'
    rendered = _sanitize(rendered)

    # Truncate if over the cap
    if len(rendered) > _CELL_CAP:
        rendered = rendered[: _CELL_CAP - len(_ELLIPSIS)] + _ELLIPSIS

    return rendered


def _pad(text: str, width: int) -> str:
    """Left-pad *text* to exactly *width* characters using spaces."""
    return text + " " * (width - len(text))


def render_journal_schwab_comparison_table_ascii(
    pairs: list[tuple[str, Any, Any]],
    *,
    journal_label: str = "Journal",
    schwab_label: str = "Schwab",
) -> str:
    """Render comparison pairs as an ASCII-only table.

    Returns a multi-line string with ``|`` column separators, ``-`` horizontal
    rules, a header row, and N data rows.  Uses ONLY ASCII chars (``|``,
    ``-``, ``+``, space) for Windows cp1252 stdout safety (per CLAUDE.md
    gotcha).  Each cell is rendered via the type-aware ``_format_value``
    helper and truncated to ``_CELL_CAP`` characters.  ZERO third-party
    dependencies (no ``rich``, no ``tabulate``).

    Parameters
    ----------
    pairs:
        Sequence of ``(field_label, journal_value, schwab_value)`` tuples.
        An empty list returns ``""`` (empty string).
    journal_label:
        Column header for the journal-side values.  Defaults to
        ``"Journal"``.
    schwab_label:
        Column header for the Schwab-side values.  Defaults to ``"Schwab"``.

    Returns
    -------
    str
        Multi-line ASCII table, or ``""`` when *pairs* is empty.  The
        returned string contains ONLY characters with ``ord(c) < 128``.
    """
    if not pairs:
        return ""

    # ------------------------------------------------------------------
    # 1. Sanitize column header labels (caller might pass unicode)
    # ------------------------------------------------------------------
    field_header = _sanitize("Field")
    journal_header = _sanitize(journal_label)
    schwab_header = _sanitize(schwab_label)

    # ------------------------------------------------------------------
    # 2. Format all cell values up front so we can compute column widths.
    # ------------------------------------------------------------------
    formatted: list[tuple[str, str, str]] = []
    for label, jval, sval in pairs:
        field_cell = _sanitize(_format_value(label))
        journal_cell = _format_value(jval)
        schwab_cell = _format_value(sval)
        formatted.append((field_cell, journal_cell, schwab_cell))

    # ------------------------------------------------------------------
    # 3. Compute column widths (max of header label width + all data widths).
    # ------------------------------------------------------------------
    col0_w = max(len(field_header), max(len(r[0]) for r in formatted))
    col1_w = max(len(journal_header), max(len(r[1]) for r in formatted))
    col2_w = max(len(schwab_header), max(len(r[2]) for r in formatted))

    # ------------------------------------------------------------------
    # 4. Build the header and rule lines.
    # ------------------------------------------------------------------
    #   Format: "Field     | Journal     | Schwab    "
    #   Rule:   "----------+-------------+-----------"
    # No outer border (brief: "no outer top/bottom rules").
    # ------------------------------------------------------------------
    def _row(c0: str, c1: str, c2: str) -> str:
        return f"{_pad(c0, col0_w)} | {_pad(c1, col1_w)} | {_pad(c2, col2_w)}"

    def _rule() -> str:
        return (
            "-" * col0_w
            + "-+-"
            + "-" * col1_w
            + "-+-"
            + "-" * col2_w
        )

    lines: list[str] = []
    lines.append(_row(field_header, journal_header, schwab_header))
    lines.append(_rule())

    for field_cell, journal_cell, schwab_cell in formatted:
        lines.append(_row(field_cell, journal_cell, schwab_cell))

    result = "\n".join(lines)

    # ------------------------------------------------------------------
    # 5. Final ASCII-only invariant assertion (defence-in-depth).
    # ------------------------------------------------------------------
    assert all(ord(c) < 128 for c in result), (
        "render_journal_schwab_comparison_table_ascii: "
        "output contains non-ASCII characters (internal bug)"
    )

    return result


# ---------------------------------------------------------------------------
# build_compared_pairs — Task T-Q2.2
# ---------------------------------------------------------------------------

def _pairs_entry_price_mismatch(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    pairs: list[tuple[str, Any, Any]] = [
        ("entry price", expected["price"], actual.get("price")),
    ]
    j_qty = expected.get("quantity")
    s_qty = actual.get("quantity")
    if j_qty is not None or s_qty is not None:
        pairs.append(("quantity", j_qty, s_qty))
    j_dt = expected.get("fill_datetime")
    s_dt = actual.get("fill_datetime")
    if j_dt is not None or s_dt is not None:
        pairs.append(("fill datetime", j_dt, s_dt))
    return pairs


def _pairs_close_price_mismatch(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    pairs: list[tuple[str, Any, Any]] = [
        ("close price", expected["price"], actual.get("price")),
    ]
    j_qty = expected.get("quantity")
    s_qty = actual.get("quantity")
    if j_qty is not None or s_qty is not None:
        pairs.append(("quantity", j_qty, s_qty))
    j_dt = expected.get("fill_datetime")
    s_dt = actual.get("fill_datetime")
    if j_dt is not None or s_dt is not None:
        pairs.append(("fill datetime", j_dt, s_dt))
    return pairs


def _pairs_stop_mismatch(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    return [("stop price", expected["stop_price"], actual.get("stop_price"))]


def _pairs_position_qty_mismatch(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    return [("position quantity", expected["quantity"], actual.get("quantity"))]


def _pairs_cash_movement_mismatch(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    return [("amount", expected["amount"], actual.get("amount"))]


def _pairs_snapshot_mismatch(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    return [("equity dollars", expected["equity_dollars"], actual.get("equity_dollars"))]


def _pairs_equity_delta(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    return [("equity dollars", expected["equity_dollars"], actual.get("equity_dollars"))]


def _pairs_sector_tamper(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]]:
    return [
        ("sector", expected["sector"], actual["sector"]),
        ("industry", expected["industry"], actual["industry"]),
    ]


# Dispatch table — maps discrepancy_type to its pair-builder.
# Types that intentionally return None (no tabular comparison possible) are
# absent from this table; the dispatcher below handles the None case.
_PAIRS_BUILDERS: dict[
    str,
    Any,  # Callable[[dict, dict], list[tuple[str, Any, Any]]]
] = {
    "entry_price_mismatch": _pairs_entry_price_mismatch,
    "close_price_mismatch": _pairs_close_price_mismatch,
    "stop_mismatch": _pairs_stop_mismatch,
    "position_qty_mismatch": _pairs_position_qty_mismatch,
    "cash_movement_mismatch": _pairs_cash_movement_mismatch,
    "snapshot_mismatch": _pairs_snapshot_mismatch,
    "equity_delta": _pairs_equity_delta,
    "sector_tamper": _pairs_sector_tamper,
}

# Types for which no tabular side-by-side comparison is meaningful.
_NO_PAIRS_TYPES: frozenset[str] = frozenset(
    {"unmatched_open_fill", "unmatched_close_fill"}
)


def build_compared_pairs(
    discrepancy_type: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[tuple[str, Any, Any]] | None:
    """Build a list of ``(field_label, journal_value, schwab_value)`` tuples.

    Dispatches to a per-discrepancy-type extractor.  Returns ``None`` for
    types where a side-by-side tabular comparison is not meaningful
    (``unmatched_open_fill`` / ``unmatched_close_fill``) and for unknown
    discrepancy types (graceful degradation — does NOT raise).

    Parameters
    ----------
    discrepancy_type:
        One of the ten canonical discrepancy type strings.
    expected:
        The ``expected_value_json`` envelope persisted on the discrepancy row.
    actual:
        The ``actual_value_json`` envelope persisted on the discrepancy row.

    Returns
    -------
    list[tuple[str, Any, Any]] | None
        Pairs suitable for passing to
        ``render_journal_schwab_comparison_table_ascii``, or ``None`` when no
        comparison table is applicable.

    Raises
    ------
    KeyError
        When a required key is missing from *expected* or *actual* for a
        known discrepancy type.  Callers should catch this and fall back to
        a generic display.

    Pure-function discipline
    ------------------------
    ZERO database calls, ZERO Schwab API calls, ZERO file I/O.
    """
    if discrepancy_type in _NO_PAIRS_TYPES:
        return None

    builder = _PAIRS_BUILDERS.get(discrepancy_type)
    if builder is None:
        # Unknown type — graceful degradation per spec.
        return None

    return builder(expected, actual)
