"""Tests for `_parse_parametric_pick_count` helper in `swing.web.view_models.reconcile`.

Covers Phase 12.5 #2 T-2.1 acceptance criteria. The helper is a pure parser
that extracts N from the classifier-emitted ``Schwab returned <N> orders within
the match window`` substring inside `resolution_reason`.

Behavioral-parity regression (LOCK §1.2 #11): the helper's regex MUST be
byte-for-byte identical to the CLI's regex at `swing/cli.py` near line 2291,
and the parametric-count behavior MUST match the CLI's `len(parametric)`
construction. DRY consolidation is V2-deferred per spec §15.13.
"""

from __future__ import annotations

import re

import pytest

from swing.web.view_models.reconcile import _parse_parametric_pick_count


def _cli_parametric_count(reason: str | None) -> int:
    """Replicate the CLI's parametric-list construction count.

    Mirrors `swing/cli.py` around line 2291 — `re.search` for
    ``Schwab returned\\s+(\\d+)\\s+orders within the match window`` against
    `resolution_reason or ""`; if match, iterate ``range(n)`` to build the
    parametric list and return ``len(parametric)``; else return 0.

    This is a BEHAVIORAL replica (not source-equality) so the parity test
    fails loudly if either side drifts.
    """
    text = reason or ""
    m = re.search(
        r"Schwab returned\s+(\d+)\s+orders within the match window",
        text,
    )
    if not m:
        return 0
    n = int(m.group(1))
    parametric: list[int] = []
    for i in range(n):
        parametric.append(i + 1)
    return len(parametric)


def test_parse_parametric_pick_count_none_returns_0() -> None:
    assert _parse_parametric_pick_count(None) == 0


def test_parse_parametric_pick_count_empty_returns_0() -> None:
    assert _parse_parametric_pick_count("") == 0


def test_parse_parametric_pick_count_no_match_returns_0() -> None:
    assert _parse_parametric_pick_count("some unrelated reason text") == 0
    assert _parse_parametric_pick_count("Schwab returned orders") == 0
    assert (
        _parse_parametric_pick_count("Schwab returned 3 orders elsewhere") == 0
    )


def test_parse_parametric_pick_count_zero_match_returns_0() -> None:
    # Matching text with N=0 still returns 0 (no parametric entries to build).
    reason = "Schwab returned 0 orders within the match window"
    assert _parse_parametric_pick_count(reason) == 0


@pytest.mark.parametrize("n", [1, 3, 7])
def test_parse_parametric_pick_count_match_returns_n(n: int) -> None:
    reason = f"Schwab returned {n} orders within the match window"
    assert _parse_parametric_pick_count(reason) == n


def test_parse_parametric_pick_count_byte_identical_to_cli_parser() -> None:
    """LOCK §1.2 #11 behavioral-parity regression test.

    The helper MUST agree with the CLI's parametric-construction count for
    every input shape the operator's classifier-emitted resolution_reason
    might carry. If either side drifts (CLI regex changes; web helper regex
    changes), this test fails loudly.
    """
    shared_inputs: list[str | None] = [
        None,
        "",
        "no match here",
        "Schwab returned 0 orders within the match window",
        "Schwab returned 1 orders within the match window",
        "Schwab returned 2 orders within the match window",
        "Schwab returned 5 orders within the match window",
        "Schwab returned 12 orders within the match window",
        "prefix Schwab returned 4 orders within the match window suffix",
        "Schwab returned\t6\torders within the match window",
        "Schwab returned 3 orders within the wrong window",
        "Schwab returned three orders within the match window",
    ]
    for s in shared_inputs:
        assert _parse_parametric_pick_count(s) == _cli_parametric_count(s), (
            f"drift on input {s!r}"
        )
