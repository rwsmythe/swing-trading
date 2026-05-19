"""Tests for swing/trades/reconciliation_render.py.

Task: Phase 12.5 Q2 T-Q2.1 — ASCII table renderer for journal/Schwab comparison.
All tests verify the ASCII-only invariant and pure-function discipline.
"""

from __future__ import annotations

from swing.trades.reconciliation_render import (
    _sanitize,
    render_journal_schwab_comparison_table_ascii,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ascii_only(s: str) -> bool:
    """Return True iff every character in s has ordinal < 128."""
    return all(ord(c) < 128 for c in s)


# ---------------------------------------------------------------------------
# Test 0 — _sanitize control-char handling (Codex R1 Minor #1)
# ---------------------------------------------------------------------------


def test_sanitize_replaces_control_chars() -> None:
    """_sanitize replaces ASCII control chars (< 0x20 + 0x7F) with space,
    non-ASCII (>= 128) with '?', and leaves printable ASCII unchanged.

    Discriminating: a string with embedded newline + tab + DEL + non-ASCII
    must produce only printable ASCII (no ord < 0x20, no ord == 0x7F,
    no ord >= 128) in the sanitized output.
    """
    # Input with control chars that would corrupt table alignment.
    raw = "a\nb\tc\x7fd\xe9"  # LF, TAB, DEL, e-with-acute
    result = _sanitize(raw)
    # All output chars must be printable ASCII.
    for i, c in enumerate(result):
        assert ord(c) < 128, f"Non-ASCII at position {i}: ord={ord(c)}"
        assert ord(c) >= 0x20, f"Control char at position {i}: ord={ord(c)}"
    # Control chars replaced with space; non-ASCII replaced with '?'.
    assert result == "a b c d?"
    # Verify via full render — embedded newline in a pair label must not
    # break row alignment.
    table = render_journal_schwab_comparison_table_ascii(
        pairs=[("a\nb", 1.0, 2.0)]
    )
    assert _ascii_only(table)
    # No literal newlines inside a cell (the embedded '\n' becomes a space).
    lines = table.splitlines()
    # Exactly 3 lines: header, rule, data row.
    assert len(lines) == 3, f"Expected 3 lines; got {len(lines)}: {lines}"


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
    """Verify swing.trades.reconciliation_render has zero third-party deps
    by AST-walking its source code for import statements.

    Earlier draft of this test checked sys.modules globally, but that path
    fails under pytest-xdist (-n auto) when sibling workers transitively
    pull in rich via pytest-rich / click. The contract we actually care
    about is that THIS module's source code names only stdlib imports --
    not the global runtime state of the test session.
    """
    import ast
    import pathlib

    src_path = (
        pathlib.Path(__file__).parent.parent.parent
        / "swing"
        / "trades"
        / "reconciliation_render.py"
    )
    tree = ast.parse(src_path.read_text(encoding="utf-8"))

    forbidden_prefixes = {"rich", "tabulate", "prettytable", "texttable"}
    bad_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden_prefixes:
                    bad_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in forbidden_prefixes:
                bad_imports.append(node.module or "")
    assert not bad_imports, (
        f"Third-party render libraries imported in reconciliation_render.py: "
        f"{bad_imports}"
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


# ===========================================================================
# Part A — build_compared_pairs dispatch tests (T-Q2.2)
# ===========================================================================

from swing.trades.reconciliation_render import build_compared_pairs  # noqa: E402


class TestBuildComparedPairsEntryPriceMismatch:
    """Happy path and edge cases for entry_price_mismatch."""

    def test_canonical_price_pair_present(self) -> None:
        pairs = build_compared_pairs(
            "entry_price_mismatch",
            {"price": 5.30},
            {"price": 5.23},
        )
        assert pairs is not None
        assert len(pairs) >= 1
        labels = [p[0] for p in pairs]
        assert "entry price" in labels
        idx = labels.index("entry price")
        assert pairs[idx][1] == 5.30
        assert pairs[idx][2] == 5.23

    def test_optional_pairs_skipped_when_both_sides_missing(self) -> None:
        """Only price on both sides — quantity and fill_datetime absent."""
        pairs = build_compared_pairs(
            "entry_price_mismatch",
            {"price": 5.30},
            {"price": 5.23},
        )
        assert pairs is not None
        # Only the price pair — NO quantity or fill_datetime pair.
        assert len(pairs) == 1

    def test_optional_pair_kept_when_one_side_present(self) -> None:
        """quantity on journal side but not schwab → pair IS included."""
        pairs = build_compared_pairs(
            "entry_price_mismatch",
            {"price": 5.30, "quantity": 100},
            {"price": 5.23},
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "quantity" in labels
        qty_idx = labels.index("quantity")
        assert pairs[qty_idx][1] == 100
        assert pairs[qty_idx][2] is None  # Schwab side absent

    def test_optional_pair_kept_when_both_sides_present(self) -> None:
        """quantity on both sides → pair IS included."""
        pairs = build_compared_pairs(
            "entry_price_mismatch",
            {"price": 5.30, "quantity": 100, "fill_datetime": "2026-05-15"},
            {"price": 5.23, "quantity": 100, "fill_datetime": "2026-05-15"},
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "quantity" in labels
        assert "fill datetime" in labels

    def test_missing_required_key_raises_keyerror(self) -> None:
        """Empty expected dict → KeyError on 'price'."""
        import pytest
        with pytest.raises(KeyError):
            build_compared_pairs("entry_price_mismatch", {}, {})


class TestBuildComparedPairsClosePriceMismatch:
    """Happy path for close_price_mismatch."""

    def test_canonical_price_pair_present(self) -> None:
        pairs = build_compared_pairs(
            "close_price_mismatch",
            {"price": 12.75},
            {"price": 12.70},
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "close price" in labels
        idx = labels.index("close price")
        assert pairs[idx][1] == 12.75
        assert pairs[idx][2] == 12.70

    def test_optional_pairs_skipped_when_both_absent(self) -> None:
        pairs = build_compared_pairs(
            "close_price_mismatch",
            {"price": 12.75},
            {"price": 12.70},
        )
        assert pairs is not None
        assert len(pairs) == 1


class TestBuildComparedPairsStopMismatch:
    """Happy path for stop_mismatch.

    Production emitter (schwab_reconciliation.py:837,840) uses ASYMMETRIC keys:
      expected_value_json = {"current_stop": <journal_stop>}
      actual_value_json   = {"stop_price":   <schwab_stop>}
    """

    def test_stop_pair_uses_production_emitter_shape(self) -> None:
        """Journal side reads expected["current_stop"]; Schwab side reads actual["stop_price"]."""
        pairs = build_compared_pairs(
            "stop_mismatch",
            {"current_stop": 10.00},
            {"stop_price": 9.90},
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "stop" in labels
        idx = labels.index("stop")
        assert pairs[idx][1] == 10.00
        assert pairs[idx][2] == 9.90

    def test_schwab_stop_absent_yields_none(self) -> None:
        """Schwab side uses .get() — absent stop_price yields None."""
        pairs = build_compared_pairs(
            "stop_mismatch",
            {"current_stop": 10.00},
            {},
        )
        assert pairs is not None
        assert pairs[0][2] is None

    def test_missing_required_current_stop_raises(self) -> None:
        """Empty expected dict -> KeyError on 'current_stop'."""
        import pytest
        with pytest.raises(KeyError):
            build_compared_pairs("stop_mismatch", {}, {})


class TestBuildComparedPairsPositionQtyMismatch:
    """Happy path for position_qty_mismatch.

    Production emitter (schwab_reconciliation.py:870,873) uses "qty" for BOTH sides:
      expected_value_json = {"qty": <journal_qty>}
      actual_value_json   = {"qty": <schwab_qty>}
    """

    def test_quantity_pair_uses_production_emitter_shape(self) -> None:
        """Both sides read the 'qty' key (NOT 'quantity')."""
        pairs = build_compared_pairs(
            "position_qty_mismatch",
            {"qty": 100},
            {"qty": 90},
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "position quantity" in labels
        idx = labels.index("position quantity")
        assert pairs[idx][1] == 100
        assert pairs[idx][2] == 90

    def test_schwab_qty_absent_yields_none(self) -> None:
        """Schwab side uses .get() — absent qty yields None."""
        pairs = build_compared_pairs(
            "position_qty_mismatch",
            {"qty": 100},
            {},
        )
        assert pairs is not None
        assert pairs[0][2] is None

    def test_missing_required_qty_raises(self) -> None:
        """Empty expected dict -> KeyError on 'qty'."""
        import pytest
        with pytest.raises(KeyError):
            build_compared_pairs("position_qty_mismatch", {}, {})


class TestBuildComparedPairsCashMovementMismatch:
    """Happy path for cash_movement_mismatch."""

    def test_amount_pair(self) -> None:
        pairs = build_compared_pairs(
            "cash_movement_mismatch",
            {"amount": 1000.00},
            {"amount": 999.50},
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "amount" in labels
        idx = labels.index("amount")
        assert pairs[idx][1] == 1000.00
        assert pairs[idx][2] == 999.50


class TestBuildComparedPairsSnapshotMismatch:
    """Happy path for snapshot_mismatch."""

    def test_equity_pair(self) -> None:
        pairs = build_compared_pairs(
            "snapshot_mismatch",
            {"equity_dollars": 2000.00},
            {"equity_dollars": 2034.78},
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "equity dollars" in labels
        idx = labels.index("equity dollars")
        assert pairs[idx][1] == 2000.00
        assert pairs[idx][2] == 2034.78


class TestBuildComparedPairsUnmatchedFills:
    """unmatched_open_fill and unmatched_close_fill return None."""

    def test_unmatched_open_fill_returns_none(self) -> None:
        result = build_compared_pairs(
            "unmatched_open_fill",
            {"quantity": 100, "price": 5.30, "fill_datetime": "2026-05-15"},
            {"matched": None},
        )
        assert result is None

    def test_unmatched_close_fill_returns_none(self) -> None:
        result = build_compared_pairs(
            "unmatched_close_fill",
            {"quantity": 50, "price": 12.75, "fill_datetime": "2026-05-16"},
            {"matched": None},
        )
        assert result is None


class TestBuildComparedPairsEquityDelta:
    """equity_delta — production emitter shape: equity_dollars in BOTH envelopes.

    Production emitters (reconciliation.py:453-457 and
    schwab_reconciliation.py:1119-1122) write:
      expected_value_json = {"equity_dollars": journal_equity}
      actual_value_json   = {"equity_dollars": source_nlv}
    The earlier draft incorrectly wrote both values into the expected envelope
    only, with keys "journal" / "source" / "delta".  This test pins the
    correct production shape so fixture drift is caught immediately.
    """

    def test_equity_delta_uses_production_emitter_shape(self) -> None:
        """Journal NLV in expected["equity_dollars"]; Schwab NLV in actual["equity_dollars"]."""
        pairs = build_compared_pairs(
            "equity_delta",
            {"equity_dollars": 2000.00},  # expected = journal side
            {"equity_dollars": 2034.78},  # actual   = Schwab side
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "equity dollars" in labels
        idx = labels.index("equity dollars")
        # journal side = expected["equity_dollars"]
        assert pairs[idx][1] == 2000.00
        # Schwab side  = actual["equity_dollars"]
        assert pairs[idx][2] == 2034.78

    def test_equity_delta_actual_absent_yields_none_schwab_side(self) -> None:
        """If actual envelope has no equity_dollars key, Schwab side is None."""
        pairs = build_compared_pairs(
            "equity_delta",
            {"equity_dollars": 2000.00},
            {},  # missing key
        )
        assert pairs is not None
        assert pairs[0][2] is None


class TestBuildComparedPairsSectorTamper:
    """sector_tamper — sector + industry pairs."""

    def test_sector_and_industry_pairs(self) -> None:
        pairs = build_compared_pairs(
            "sector_tamper",
            {"sector": "Technology", "industry": "Software"},
            {"sector": "Technology", "industry": "Hardware"},
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        assert "sector" in labels
        assert "industry" in labels
        sector_idx = labels.index("sector")
        industry_idx = labels.index("industry")
        assert pairs[sector_idx][1] == "Technology"
        assert pairs[sector_idx][2] == "Technology"
        assert pairs[industry_idx][1] == "Software"
        assert pairs[industry_idx][2] == "Hardware"


class TestBuildComparedPairsGracefulDegradation:
    """Unknown types return None; caller-catches KeyError for missing required."""

    def test_unknown_type_returns_none(self) -> None:
        result = build_compared_pairs("bogus_discrepancy_type", {}, {})
        assert result is None

    def test_returns_list_not_none_for_known_types(self) -> None:
        result = build_compared_pairs(
            "stop_mismatch",
            {"current_stop": 10.0},
            {"stop_price": 9.9},
        )
        assert result is not None
        assert isinstance(result, list)

    def test_schwab_side_none_when_key_absent_in_actual(self) -> None:
        """Schwab side uses .get() — absent key yields None (renders as '-')."""
        pairs = build_compared_pairs(
            "snapshot_mismatch",
            {"equity_dollars": 2000.00},
            {},  # no equity_dollars on Schwab side
        )
        assert pairs is not None
        labels = [p[0] for p in pairs]
        idx = labels.index("equity dollars")
        assert pairs[idx][2] is None
