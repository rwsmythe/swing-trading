"""Arc 21-G: the close-provenance vocabulary + the PURE provenance ladder.

The one rule the whole arc implements: NEVER ACT ON AN UNDATED PRICE, IN
EITHER DIRECTION. Assert only from a close DATED the derivation session;
alarm only from a close dated `D < S` that is PROVEN to be dated `D`.
"""
from __future__ import annotations

from datetime import date

from swing.latches.constants import (
    ARCHIVE_STATUS_OK,
    ARCHIVE_STATUS_UNAVAILABLE,
    ARCHIVE_STATUSES,
    CLOSE_PROVENANCE_ABSENT,
    CLOSE_PROVENANCE_CORROBORATED,
    CLOSE_PROVENANCE_FUTURE_STAMP,
    CLOSE_PROVENANCE_UNCORROBORATED,
    CLOSE_PROVENANCES,
)

S = date(2026, 7, 24)


def test_the_provenance_vocabulary_is_declared_once_in_constants():
    """The domain owner, single declaration (the 21-A LATCH_STATES precedent /
    the #11 one-commit multi-mirror discipline)."""
    assert CLOSE_PROVENANCES == frozenset({
        "corroborated", "uncorroborated", "future_stamp", "absent"})
    assert CLOSE_PROVENANCE_CORROBORATED == "corroborated"
    assert CLOSE_PROVENANCE_UNCORROBORATED == "uncorroborated"
    assert CLOSE_PROVENANCE_FUTURE_STAMP == "future_stamp"
    assert CLOSE_PROVENANCE_ABSENT == "absent"


def test_the_archive_status_vocabulary_is_declared_once_in_constants():
    """`unavailable` means the archive read RAISED -- our ignorance. `ok` with
    an empty map is a FACT about the data. They must not collapse."""
    assert ARCHIVE_STATUSES == frozenset({"ok", "unavailable"})
    assert ARCHIVE_STATUS_OK == "ok"
    assert ARCHIVE_STATUS_UNAVAILABLE == "unavailable"
