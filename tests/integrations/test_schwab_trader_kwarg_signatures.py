"""Discriminating tests pinning trader.py kwarg names against live schwabdev signatures.

Defect surfaced 2026-05-14 during Sub-bundle B operator-paired live verification:
trader.py:362 passed `max_results=max_results` (snake_case) but schwabdev 2.5.1's
`Client.account_orders` signature uses `maxResults=` (camelCase). TypeError raised
at runtime; cassette tests didn't catch because they stub the entire schwabdev call
(any kwargs accepted).

These tests pin every trader.py wrapper's kwarg-passing against live
`inspect.signature(schwabdev.Client.X)` so future schwabdev upgrades OR future
trader.py wrappers cannot regress on camelCase-vs-snake_case mismatch.

NEW gotcha family promoted to CLAUDE.md (Sub-bundle B return-report follow-up):
schwabdev uses camelCase parameter names (accountHash, fromEnteredTime,
toEnteredTime, maxResults, startDate, endDate, etc.) which DIVERGE from project
snake_case convention. Wrapper kwargs MUST match schwabdev's camelCase exactly.
"""
from __future__ import annotations

import inspect

import schwabdev


def _kwarg_names(method) -> set[str]:
    """Return the set of parameter names accepted as kwargs (excluding `self`)."""
    sig = inspect.signature(method)
    return {name for name in sig.parameters if name != "self"}


def test_account_linked_no_kwargs_required() -> None:
    """`Client.account_linked()` takes no parameters beyond self.

    Wrapper at swing/integrations/schwab/trader.py:270 invokes as
    `client.account_linked()` — no kwargs to validate.
    """
    sig = inspect.signature(schwabdev.Client.account_linked)
    params = [p for p in sig.parameters if p != "self"]
    assert params == [], (
        f"Schwabdev account_linked signature changed; expected no params, got {params}. "
        "Update trader.py:get_accounts_linked if so."
    )


def test_account_details_kwargs_match_schwabdev() -> None:
    """`Client.account_details(accountHash, fields=None)` — wrapper passes
    `fields=fields` which matches schwabdev's snake-style `fields`. Pin in case
    schwabdev renames.
    """
    expected = {"accountHash", "fields"}
    actual = _kwarg_names(schwabdev.Client.account_details)
    assert actual == expected, (
        f"Schwabdev account_details signature changed: expected {expected}, "
        f"got {actual}. Update swing/integrations/schwab/trader.py:get_account_details "
        "kwarg names to match."
    )


def test_account_orders_kwargs_match_schwabdev() -> None:
    """`Client.account_orders(accountHash, fromEnteredTime, toEnteredTime,
    maxResults=None, status=None)` — wrapper passes `maxResults=max_results`
    + `status=status`. **CamelCase `maxResults` is the post-2026-05-14 fix.**

    Sub-bundle B operator-paired gate caught the snake_case `max_results`
    defect; this test prevents regression.
    """
    expected = {"accountHash", "fromEnteredTime", "toEnteredTime", "maxResults", "status"}
    actual = _kwarg_names(schwabdev.Client.account_orders)
    assert actual == expected, (
        f"Schwabdev account_orders signature changed: expected {expected}, "
        f"got {actual}. Update swing/integrations/schwab/trader.py:get_account_orders "
        "kwarg names to match. CamelCase discipline per 2026-05-14 gate-caught defect."
    )


def test_transactions_kwargs_match_schwabdev() -> None:
    """`Client.transactions(accountHash, startDate, endDate, types, symbol=None)`
    — wrapper passes positional + `symbol=symbol`. Pin in case schwabdev renames.
    """
    expected = {"accountHash", "startDate", "endDate", "types", "symbol"}
    actual = _kwarg_names(schwabdev.Client.transactions)
    assert actual == expected, (
        f"Schwabdev transactions signature changed: expected {expected}, "
        f"got {actual}. Update swing/integrations/schwab/trader.py:get_account_transactions "
        "kwarg names to match."
    )


def test_no_snake_case_kwarg_in_trader_calls() -> None:
    """Source-level grep: trader.py MUST NOT pass `max_results=` (snake_case)
    to schwabdev.Client.account_orders. Defense against a future regression
    where someone renames the wrapper-level parameter back to snake_case kwarg.

    Discriminating test pattern: read trader.py source as text, grep for the
    exact failing-pre-2026-05-14 substring.
    """
    from pathlib import Path

    trader_src = Path(__file__).resolve().parents[2] / "swing" / "integrations" / "schwab" / "trader.py"
    src_text = trader_src.read_text(encoding="utf-8")
    # The failing-pre-fix pattern: max_results= passed to client.account_orders
    # within a contiguous client_method=lambda block.
    assert "max_results=max_results" not in src_text, (
        "trader.py contains the pre-fix snake_case `max_results=` kwarg pattern. "
        "Schwabdev 2.5.1 uses camelCase `maxResults=`. See 2026-05-14 gate-caught "
        "defect + this test file's docstring."
    )
