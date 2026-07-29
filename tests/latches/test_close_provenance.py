"""Arc 21-G: the close-provenance vocabulary + the PURE provenance ladder.

The one rule the whole arc implements: NEVER ACT ON AN UNDATED PRICE, IN
EITHER DIRECTION. Assert only from a close DATED the derivation session;
alarm only from a close dated `D < S` that is PROVEN to be dated `D`.
"""
from __future__ import annotations

from datetime import date

import pytest

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


# --- Task 3: the pure classifier truth table (plan H.T1) --------------------
def _classify(quote, archive, status=ARCHIVE_STATUS_OK, bars_through=None):
    from swing.latches.orders import classify_close_provenance

    return classify_close_provenance(
        quote=quote, derivation_session=S, bars_through=bars_through,
        archive_closes=archive, archive_status=status)


_D = date(2026, 7, 24)
_D_MINUS_1 = date(2026, 7, 23)


@pytest.mark.parametrize(
    "quote,archive,status,provenance,conflict,dated",
    [
        # rung A: a bar DATED S whose close IS the recorded close.
        ((17.76, "2026-07-24"), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "corroborated", False, True),
        # 2dp tolerance at W(S): a 0.004 difference still corroborates.
        ((17.76, "2026-07-24"), {_D: 17.764}, ARCHIVE_STATUS_OK,
         "corroborated", False, True),
        # ...and a 0.006 difference does NOT -- it is a DATED CONFLICT.
        ((17.76, "2026-07-24"), {_D: 17.766}, ARCHIVE_STATUS_OK,
         "uncorroborated", True, False),
        # Route B: the run stamped S over a close the market had left.
        ((19.52, "2026-07-24"), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "uncorroborated", True, False),
        # The alarm rung condition (1): corroborated AT ITS OWN STAMP.
        ((19.52, "2026-07-23"), {_D_MINUS_1: 19.52}, ARCHIVE_STATUS_OK,
         "uncorroborated", False, True),
        # ...the R6 lagged-inside-the-cohort shape: W(D) DISAGREES.
        ((19.52, "2026-07-23"), {_D_MINUS_1: 18.10}, ARCHIVE_STATUS_OK,
         "uncorroborated", False, False),
        # 2dp tolerance at W(D) too, both sides of the boundary.
        ((19.52, "2026-07-23"), {_D_MINUS_1: 19.524}, ARCHIVE_STATUS_OK,
         "uncorroborated", False, True),
        ((19.52, "2026-07-23"), {_D_MINUS_1: 19.526}, ARCHIVE_STATUS_OK,
         "uncorroborated", False, False),
        # No witness at all.
        ((19.52, "2026-07-23"), {}, ARCHIVE_STATUS_OK,
         "uncorroborated", False, False),
        # ...and the SAME empty map when the read RAISED.
        ((19.52, "2026-07-23"), {}, ARCHIVE_STATUS_UNAVAILABLE,
         "uncorroborated", False, False),
        # rung F PRE-EMPTS rung A: a stamp AFTER the page horizon.
        ((17.76, "2026-07-27"), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "future_stamp", False, False),
        # ...an UNPLACEABLE stamp lands here for the same reason.
        ((17.76, "not-a-date"), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "future_stamp", False, False),
        # ...including the shipped empty-stamp shape (load_last_closes).
        ((17.76, ""), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "future_stamp", False, False),
        # rung C: no price at all.
        (None, {_D: 17.76}, ARCHIVE_STATUS_OK, "absent", False, False),
        ((float("nan"), "2026-07-24"), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "absent", False, False),
        ((float("inf"), "2026-07-24"), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "absent", False, False),
        (("nope", "2026-07-24"), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "absent", False, False),
        ((True, "2026-07-24"), {_D: 17.76}, ARCHIVE_STATUS_OK,
         "absent", False, False),
    ],
)
def test_the_close_provenance_truth_table(
        quote, archive, status, provenance, conflict, dated):
    prov = _classify(quote, archive, status)
    assert prov.provenance == provenance
    assert prov.has_dated_conflict is conflict
    assert prov.dated_at_stamp is dated
    assert prov.may_assert is (provenance == CLOSE_PROVENANCE_CORROBORATED)
    assert prov.provenance in CLOSE_PROVENANCES


def test_a_non_finite_archive_bar_cannot_corroborate_anything():
    """The archive is the WITNESS; an unusable witness proves nothing. A bar
    that survived to the map as NaN must not be compared into a match."""
    prov = _classify((17.76, "2026-07-24"), {_D: float("nan")})
    assert prov.provenance == CLOSE_PROVENANCE_UNCORROBORATED
    assert prov.session_close is None
    # ...and it is NOT reported as a dated CONFLICT either: we hold no dated
    # evidence, so there is nothing to contradict.
    assert prov.has_dated_conflict is False


def test_archive_unavailable_is_driven_by_the_status_never_by_an_empty_map():
    """Codex R5 MAJOR 2. `load_bars` swallows every archive exception and
    returns [], so "the archive says there is no such bar" and "the archive
    could not be read" collapse into the same ABSENCE. Authorizing an alarm in
    the second case would be asserting from a stale price precisely when we
    could not check the one thing that would have settled it."""
    readable = _classify((19.52, "2026-07-23"), {}, ARCHIVE_STATUS_OK)
    unreadable = _classify((19.52, "2026-07-23"), {}, ARCHIVE_STATUS_UNAVAILABLE)
    assert readable.archive_unavailable is False
    assert unreadable.archive_unavailable is True
    # ...and both carry the SAME (empty) witness, which is the point.
    assert readable.session_close is None and unreadable.session_close is None


def test_the_classifier_carries_the_stamp_as_an_upper_bound_not_as_a_date():
    """The stamp is preserved for LABELLING, never consulted as proof."""
    prov = _classify((19.52, "2026-07-23"), {_D_MINUS_1: 19.52})
    assert prov.stamp_session == "2026-07-23"
    assert prov.stamp_date == date(2026, 7, 23)
    assert prov.stamp_session_close == 19.52
    assert prov.session_close is None
    assert prov.derivation_session == S
    assert prov.price == 19.52


def test_an_unparseable_stamp_carries_no_stamp_date():
    prov = _classify((17.76, "not-a-date"), {})
    assert prov.stamp_session == "not-a-date"
    assert prov.stamp_date is None


def test_bars_through_is_label_context_only_and_is_never_the_witness():
    """The witness is the per-ticker {session -> close} map, which is
    anchor-INDEPENDENT. `bars_through` comes from the invalidation walk's
    ELIGIBLE set and is empty for the freshest latch in the system, so a
    classifier that consulted it could never corroborate that latch."""
    prov = _classify((17.76, "2026-07-24"), {_D: 17.76}, bars_through=None)
    assert prov.may_assert is True
    assert prov.bars_through is None


def test_the_classifier_is_pure_and_does_no_io():
    """The Phase-12 classifier convention: no DB, no network, no transaction
    management. Everything arrives pre-fetched."""
    import inspect

    from swing.latches.orders import classify_close_provenance
    src = inspect.getsource(classify_close_provenance)
    for forbidden in ("conn", "execute", "requests", "open("):
        assert forbidden not in src
