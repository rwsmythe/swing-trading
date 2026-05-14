"""Discriminating tests pinning marketdata.py kwarg names against live schwabdev signatures.

Same defect family as Sub-bundle B's `account_orders(maxResults=...)` gate-caught
defect (2026-05-14, fix `34be84e`). Per `reference/schwabdev/api-calls.md` L296-440:

- `Client.quotes(symbols=None, fields=None, indicative=False)` — ALL snake_case.
- `Client.price_history(symbol, periodType=None, period=None, frequencyType=None,
  frequency=None, startDate=None, endDate=None, needExtendedHoursData=None,
  needPreviousClose=None)` — 8 of 9 kwargs are camelCase; only `symbol` positional.

These tests pin both surfaces via `inspect.signature(schwabdev.Client.X)` so a
future schwabdev upgrade OR a future marketdata.py wrapper cannot regress on
camelCase-vs-snake_case mismatch.

Mirrors `tests/integrations/test_schwab_trader_kwarg_signatures.py` pattern.
T-C.0.b recon doc §3.1 + dispatch brief §0.5 #1 binding.
"""
from __future__ import annotations

import inspect
from inspect import Parameter
from pathlib import Path

import schwabdev


def _kwarg_names(method) -> set[str]:
    """Return the set of parameter names accepted as kwargs (excluding `self`).

    Codex R1 Minor #1: pin Parameter.kind explicitly so that future schwabdev
    upgrades that add `**kwargs` (VAR_KEYWORD) or make a param positional-only
    (POSITIONAL_ONLY) cannot mask the camelCase/snake_case kwarg set this test
    is meant to assert on.

    Only ``POSITIONAL_OR_KEYWORD`` and ``KEYWORD_ONLY`` parameters are
    addressable by keyword name from the caller; ``VAR_POSITIONAL`` (*args)
    and ``VAR_KEYWORD`` (**kwargs) are NOT included in the returned set —
    the companion ``_assert_no_var_keyword`` guards against the latter.
    """
    sig = inspect.signature(method)
    return {
        name for name, param in sig.parameters.items()
        if name != "self" and param.kind in (
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
        )
    }


def _assert_no_var_keyword(method, *, name: str) -> None:
    """Codex R1 Minor #1: a future schwabdev signature with ``**kwargs`` would
    silently accept ANY kwarg name, masking a kwarg-name regression. Assert
    no ``VAR_KEYWORD`` parameter is present on the schwabdev methods we pin.
    """
    sig = inspect.signature(method)
    var_keyword_params = [
        p.name for p in sig.parameters.values()
        if p.kind == Parameter.VAR_KEYWORD
    ]
    assert not var_keyword_params, (
        f"schwabdev.Client.{name} has VAR_KEYWORD parameter(s) "
        f"{var_keyword_params!r} — a **kwargs sink would mask kwarg-name "
        "regressions. Pin against this drift."
    )


def test_quotes_kwargs_snake_case() -> None:
    """`Client.quotes(symbols=None, fields=None, indicative=False)` — all snake_case.

    Pinned per `api-calls.md` L298. SAFE from the Sub-bundle-B camelCase trap
    family — but pin anyway so a future schwabdev change is caught before any
    runtime TypeError.
    """
    expected = {"symbols", "fields", "indicative"}
    actual = _kwarg_names(schwabdev.Client.quotes)
    assert actual == expected, (
        f"Schwabdev quotes signature changed: expected {expected}, got {actual}. "
        "Update swing/integrations/schwab/marketdata.py:get_quotes_batch kwarg "
        "names to match."
    )
    _assert_no_var_keyword(schwabdev.Client.quotes, name="quotes")


def test_price_history_kwargs_camel_case() -> None:
    """`Client.price_history(symbol, periodType, period, frequencyType, frequency,
    startDate, endDate, needExtendedHoursData, needPreviousClose)` — 8 of 9 kwargs
    are CAMELCASE; only `symbol` positional snake_case.

    Pinned per `api-calls.md` L407-423. **Same defect family as Sub-bundle B's
    `account_orders(maxResults=...)` gate-caught defect.** Any future schwabdev
    rename OR future marketdata.py wrapper using `period_type=` / `start_date=`
    would TypeError at runtime; this test fires first.
    """
    expected = {
        "symbol",
        "periodType",
        "period",
        "frequencyType",
        "frequency",
        "startDate",
        "endDate",
        "needExtendedHoursData",
        "needPreviousClose",
    }
    actual = _kwarg_names(schwabdev.Client.price_history)
    assert actual == expected, (
        f"Schwabdev price_history signature changed: expected {expected}, "
        f"got {actual}. Update swing/integrations/schwab/marketdata.py:"
        "get_price_history kwarg names to match. CamelCase discipline per "
        "Sub-bundle B 2026-05-14 gate-caught defect."
    )
    _assert_no_var_keyword(schwabdev.Client.price_history, name="price_history")


def test_no_snake_case_price_history_kwargs_in_marketdata_calls() -> None:
    """Source-level grep: marketdata.py MUST NOT pass `period_type=` / `frequency_type=`
    / `start_date=` / `end_date=` / `need_extended_hours_data=` / `need_previous_close=`
    (snake_case) to schwabdev.Client.price_history.

    Defense against a future regression where someone renames the wrapper-level
    parameters back to snake_case kwargs. Mirrors trader.py:test_no_snake_case_kwarg_in_trader_calls.
    """
    marketdata_src = (
        Path(__file__).resolve().parents[2]
        / "swing" / "integrations" / "schwab" / "marketdata.py"
    )
    src_text = marketdata_src.read_text(encoding="utf-8")
    forbidden = (
        "period_type=period_type",
        "frequency_type=frequency_type",
        "start_date=start_date",
        "end_date=end_date",
        "need_extended_hours_data=",
        "need_previous_close=",
    )
    for pattern in forbidden:
        assert pattern not in src_text, (
            f"marketdata.py contains the pre-fix snake_case `{pattern}` kwarg "
            "pattern. Schwabdev 2.5.1 uses camelCase. See this test file's "
            "docstring + T-C.0.b recon doc §5.A."
        )
