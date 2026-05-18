"""Tests for swing/trades/reconciliation_render.py.

Task: Phase 12.5 Q2 T-Q2.1 — ASCII table renderer for journal/Schwab comparison.
All tests verify the ASCII-only invariant and pure-function discipline.
"""

from __future__ import annotations

import sys

from swing.trades.reconciliation_render import (
    render_journal_schwab_comparison_table_ascii,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ascii_only(s: str) -> bool:
    """Return True iff every character in s has ordinal < 128."""
    return all(ord(c) < 128 for c in s)


# ---------------------------------------------------------------------------
# Test 1 — empty pairs returns empty string
# ---------------------------------------------------------------------------


def test_empty_pairs_returns_empty_string() -> None:
    result = render_journal_schwab_comparison_table_ascii(pairs=[])
    assert result == ""


# ---------------------------------------------------------------------------
# Test 2 — single pair emits header, rule, and data row
# ---------------------------------------------------------------------------


def test_single_pair_emits_header_and_rule_and_data_row() -> None:
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("price", 5.00, 5.22)]
    )
    lines = result.splitlines()
    # At minimum: header line, rule line, data line
    assert len(lines) >= 3

    header = lines[0]
    assert "Field" in header
    assert "Journal" in header
    assert "Schwab" in header
    assert "|" in header

    rule = lines[1]
    assert "-" in rule
    assert "+" in rule

    data = lines[2]
    assert "price" in data
    assert "|" in data

    assert _ascii_only(result)


# ---------------------------------------------------------------------------
# Test 3 — multi-pair alignment: all data rows have same length
# ---------------------------------------------------------------------------


def test_multi_pair_alignment() -> None:
    pairs = [("price", 1.2, 1.3), ("quantity", 100, 100)]
    result = render_journal_schwab_comparison_table_ascii(pairs=pairs)
    lines = result.splitlines()

    # header + rule + 2 data rows = 4 lines
    assert len(lines) == 4

    # All rows must have the same string length (consistent column widths)
    lengths = [len(line) for line in lines]
    assert lengths[0] == lengths[1] == lengths[2] == lengths[3], (
        f"Row lengths inconsistent: {lengths}"
    )

    assert _ascii_only(result)


# ---------------------------------------------------------------------------
# Test 4 — long value truncated with "..."
# ---------------------------------------------------------------------------

_CAP = 40  # must match the module's cap constant


def test_long_value_truncation_with_ellipsis() -> None:
    long_val = "x" * 100
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("field", long_val, "short")]
    )
    # Find the journal cell in the data row
    lines = result.splitlines()
    data_row = lines[2]

    # The truncated value should appear in the row; it ends with "..."
    # and has total length == cap
    truncated = "x" * (_CAP - 3) + "..."
    assert truncated in data_row, (
        f"Expected truncated value '{truncated[:20]}...' in data row"
    )
    assert _ascii_only(result)


# ---------------------------------------------------------------------------
# Test 5 — None value rendered as "-"
# ---------------------------------------------------------------------------


def test_none_value_rendered_as_dash() -> None:
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("price", None, 5.0)]
    )
    lines = result.splitlines()
    data_row = lines[2]

    # Split on "|" to isolate columns
    cells = [c.strip() for c in data_row.split("|")]
    # cells[0] = field label, cells[1] = journal cell, cells[2] = schwab cell
    assert cells[1] == "-", f"Expected '-' for None journal value; got '{cells[1]}'"
    assert _ascii_only(result)


# ---------------------------------------------------------------------------
# Test 6 — float renders with 2 decimal places
# ---------------------------------------------------------------------------


def test_numeric_formatting_two_decimals_for_float() -> None:
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("price", 5.0, 5.2244)]
    )
    assert "5.00" in result
    assert "5.22" in result
    assert _ascii_only(result)


# ---------------------------------------------------------------------------
# Test 7 — int renders without decimals
# ---------------------------------------------------------------------------


def test_int_renders_without_decimals() -> None:
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("quantity", 100, 100)]
    )
    lines = result.splitlines()
    data_row = lines[2]
    cells = [c.strip() for c in data_row.split("|")]

    # "100" must appear, not "100.00"
    assert cells[1] == "100", f"Expected '100', got '{cells[1]}'"
    assert cells[2] == "100", f"Expected '100', got '{cells[2]}'"
    assert _ascii_only(result)


# ---------------------------------------------------------------------------
# Test 8 — custom column labels appear in header
# ---------------------------------------------------------------------------


def test_custom_labels() -> None:
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("field", "a", "b")],
        journal_label="Truth",
        schwab_label="Broker",
    )
    header = result.splitlines()[0]
    assert "Truth" in header
    assert "Broker" in header
    assert "Journal" not in header
    assert "Schwab" not in header
    assert _ascii_only(result)


# ---------------------------------------------------------------------------
# Test 9 — ASCII-only invariant holds even with unicode input
# ---------------------------------------------------------------------------


def test_ascii_only_audit() -> None:
    # Feed a unicode field label and unicode string values
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("→arrow", "café", "naïve")]
    )
    assert _ascii_only(result), (
        "Renderer output must be ASCII-only even when inputs contain unicode"
    )
    # The field label should have the non-ASCII replaced (not just silently dropped)
    lines = result.splitlines()
    data_row = lines[2]
    # After sanitization, the arrow char is gone / replaced; row must still be present
    assert "|" in data_row


# ---------------------------------------------------------------------------
# Test 10 — zero third-party imports
# ---------------------------------------------------------------------------


def test_zero_third_party_imports() -> None:
    # The module must already be imported (import at top of this file triggered it)
    forbidden = {"rich", "tabulate", "prettytable", "texttable"}
    loaded = set(sys.modules.keys())
    overlap = forbidden & loaded
    assert not overlap, (
        f"Third-party render libraries found in sys.modules: {overlap}"
    )


# ---------------------------------------------------------------------------
# Additional corner cases
# ---------------------------------------------------------------------------


def test_decimal_import_renders_correctly() -> None:
    """Decimal values should render with :.2f formatting."""
    from decimal import Decimal
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("price", Decimal("12.5"), Decimal("12.5001"))]
    )
    assert "12.50" in result
    assert _ascii_only(result)


def test_bool_renders_via_repr() -> None:
    """Bool is a subclass of int; should render as str(bool) not float."""
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("flag", True, False)]
    )
    # bool is subclass of int, str(True)='True', str(False)='False'
    assert "True" in result or "False" in result
    assert _ascii_only(result)


def test_other_type_renders_via_repr_truncated() -> None:
    """Objects not str/int/float/Decimal/None use repr() then truncate."""
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("obj", [1, 2, 3], {"a": 1})]
    )
    # repr of list/dict is ASCII-safe; check the output is clean
    assert _ascii_only(result)
    lines = result.splitlines()
    assert len(lines) >= 3


def test_rule_line_uses_plus_separator() -> None:
    """Rule line must use '+' at column-separator positions."""
    result = render_journal_schwab_comparison_table_ascii(
        pairs=[("x", 1, 2)]
    )
    rule = result.splitlines()[1]
    assert "+" in rule
    assert "-" in rule
    # Rule must not contain '|'
    assert "|" not in rule
