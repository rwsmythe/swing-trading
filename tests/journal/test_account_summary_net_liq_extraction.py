"""Phase 9 Sub-bundle C T-C.6 — Account Summary net-liq extraction parser.

Per dispatch brief §0.5 #5 + spec §3.5 + §3.3.1 equity_delta JSON shape.

Coverage:
  - Real-world Schwab/TOS Account Summary section format
    (`Net Liquidating Value,"$2,015.01"`).
  - Missing section returns None.
  - Missing Net Liquidating Value row returns None.
  - Numeric format variants: with/without thousand separator;
    parenthetical negative; unquoted dollar form.
  - Verified against all 4 sanitized real-world fixture exports at
    ``tests/fixtures/tos/schwab-real-world-2026-*.csv`` (Phase 9 Sub-bundle
    E sanitization preserves Net Liquidating Value section; Phase 12.5 #3
    Q3 disposition switched from gitignored ``thinkorswim/`` originals).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.journal.tos_import import extract_account_summary_net_liq


# ============================================================================
# §1 — Real-world fixture exports
# ============================================================================


# Sanitized fixtures at tests/fixtures/tos/schwab-real-world-<date>.csv
# (account number 27097300SCHW -> <account> per Phase 9 Sub-bundle E ship;
# Net Liquidating Value section untouched by sanitization).
# Phase 12.5 #3 Q3 disposition (2026-05-18): switched from gitignored
# thinkorswim/ originals to tracked sanitized fixtures so these 4 cases
# run in CI / fresh checkouts.
FIXTURE_DIR = Path(__file__).parents[2] / "tests" / "fixtures" / "tos"


@pytest.mark.parametrize("filename, expected", [
    ("schwab-real-world-2026-04-15.csv", 1300.00),
    ("schwab-real-world-2026-04-30.csv", 1396.35),
    ("schwab-real-world-2026-05-08.csv", 1420.60),
    ("schwab-real-world-2026-05-12.csv", 2015.01),
])
def test_extracts_net_liq_from_real_world_export(
    filename: str, expected: float,
) -> None:
    path = FIXTURE_DIR / filename
    if not path.exists():
        pytest.skip(f"{filename} not present in this checkout")
    text = path.read_text(encoding="utf-8", errors="replace")
    result = extract_account_summary_net_liq(text)
    assert result == pytest.approx(expected, abs=0.01), (
        f"{filename}: expected ~${expected}, got {result}"
    )


# ============================================================================
# §2 — Synthetic minimal section
# ============================================================================


def test_extracts_quoted_dollar_with_thousand_separator() -> None:
    csv_text = (
        "Account Summary\n"
        'Net Liquidating Value,"$1,300.00"\n'
        'Stock Buying Power,"$1,300.00"\n'
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result == 1300.00


def test_extracts_unquoted_dollar_value() -> None:
    csv_text = (
        "Account Summary\n"
        "Net Liquidating Value,$1234.56\n"
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result == 1234.56


def test_handles_negative_parenthetical() -> None:
    """Defensive: parenthetical-negative form (unlikely for net-liq but
    the underlying ``_parse_tos_amount`` honors it; we verify the parser
    doesn't lose the sign en route).
    """
    csv_text = (
        "Account Summary\n"
        'Net Liquidating Value,"($1,234.56)"\n'
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result == -1234.56


def test_handles_zero_value() -> None:
    csv_text = (
        "Account Summary\n"
        "Net Liquidating Value,$0.00\n"
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result == 0.0


def test_returns_none_when_account_summary_section_missing() -> None:
    """Per T-C.6 contract: None signals 'source-side equity unavailable'."""
    csv_text = (
        "Account Trade History\n"
        "Date,Symbol\n2026-05-12,ABC\n"
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result is None


def test_returns_none_when_section_present_but_net_liq_row_missing() -> None:
    csv_text = (
        "Account Summary\n"
        "Stock Buying Power,$1234.56\n"
        "Option Buying Power,$895.38\n"
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result is None


def test_returns_none_when_value_unparsable() -> None:
    """Codex Round 1 Major #2 fix: unparsable values now return None.

    Previously the parser delegated to ``_parse_tos_amount``, which
    returns 0.0 for unparsable input — that would surface as a false-
    positive equity_delta discrepancy emit (delta = journal_equity - 0).
    The strict parse path returns None so the caller treats it as
    'source-side equity unavailable' + skips the emit (T-C.6 contract).
    """
    csv_text = (
        "Account Summary\n"
        "Net Liquidating Value,not-a-number\n"
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result is None


def test_returns_none_when_value_is_dash_placeholder() -> None:
    """`--` is the TOS placeholder for missing/inactive metrics."""
    csv_text = (
        "Account Summary\n"
        "Net Liquidating Value,--\n"
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result is None


def test_returns_none_when_value_is_na() -> None:
    csv_text = (
        "Account Summary\n"
        'Net Liquidating Value,"N/A"\n'
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result is None


def test_returns_none_for_nan_literal() -> None:
    """Codex R2 Major #1: ``float('nan')`` parses; we must reject."""
    for spelling in ("nan", "NaN", "NAN"):
        csv_text = f"Account Summary\nNet Liquidating Value,{spelling}\n"
        result = extract_account_summary_net_liq(csv_text)
        assert result is None, f"non-finite {spelling!r} must be rejected"


def test_returns_none_for_inf_literal() -> None:
    """Codex R2 Major #1: ``float('inf')`` / ``float('-inf')`` parse; reject."""
    for spelling in ("inf", "-inf", "infinity", "Infinity"):
        csv_text = f"Account Summary\nNet Liquidating Value,{spelling}\n"
        result = extract_account_summary_net_liq(csv_text)
        assert result is None, f"non-finite {spelling!r} must be rejected"


def test_scans_only_the_account_summary_section() -> None:
    """A `Net Liquidating Value` row in a different section is ignored.

    Defensive: should the operator's CSV have a similarly-named field in
    another section, we MUST scope to Account Summary only.
    """
    csv_text = (
        "Some Other Section\n"
        "Net Liquidating Value,$99.99\n"
        "Account Summary\n"
        'Net Liquidating Value,"$1,300.00"\n'
    )
    result = extract_account_summary_net_liq(csv_text)
    assert result == 1300.00
