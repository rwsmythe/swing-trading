"""22-A2 R2-01 -- the session token class is bounded by the HYPHEN too.

RD's ruling A-R2 item 1 (option a), CHARC's `.5` shape review: the session
token class gains the hyphen (``_TOKEN_CLASS["session"] = "0-9.-"``), so both
the ISO search and F13's MM-DD fallback are bounded by non-``[0-9.-]`` on BOTH
sides.  Before, the MM-DD fallback matched the TAIL of a wrong-year ISO date
(``08-10`` inside ``2025-08-10``) and the year rule then borrowed the author's
year over the record's own -- a record dated to a different session admitted.

The five discriminators are RD's, verbatim (temp-repo fixture, 2026 author,
cited session 2026-08-10, whole-line quotes per A-R1 item 2), run end to end
through the correction service on trade 25's REAL row shape:

(i)   ``OII 2025-08-10 53.98 41.42``            -> REFUSE ``action_session``
(ii)  ``OII 08-10 53.98 41.42``                 -> ADMIT (the year rule borrows)
(iii) ``OII 2026-08-10T10:03:33Z 53.98 41.42``  -> ADMIT (the bound is the hyphen,
                                                   not every non-digit)
(iv)  ``OII 08-10-2026 53.98 41.42``            -> REFUSE ``action_session``
(v)   line 57                                    -> ADMIT unchanged (A2-98..104)

Pre-fix arithmetic: (i) and (iv) ADMIT under the ``0-9.`` class (the MM-DD
fallback finds ``08-10`` bounded by ``-`` / ``-``, which that class does not
contain); (iii) REFUSES under any class that also contains letters (``T``
follows the ISO date), which is the over-wide mutation this file must catch.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from swing.trades import cohort_provenance_correction as cpc
from swing.trades import frozen_value_evidence as fve
from tests.trades.test_22a2_correction_service import (  # noqa: F401 -- fixture
    LINE57,
    _apply,
    _count,
    _evidence,
    _row,
    _t25,
    ticking_clock,
)

SESSION = "2026-08-10"
LINE_I = b"OII 2025-08-10 53.98 41.42"
LINE_II = b"OII 08-10 53.98 41.42"
LINE_III = b"OII 2026-08-10T10:03:33Z 53.98 41.42"
LINE_IV = b"OII 08-10-2026 53.98 41.42"


def _session_found(line: bytes) -> str | None:
    """``_criterion3``'s two session calls, in its order (ISO, then MM-DD
    under the year rule -- the 2026 author equals the session year)."""
    text = line.decode("utf-8")
    found = fve.find_token(text, SESSION, kind="session")
    if found is None:
        found = fve.find_token(text, SESSION[5:], kind="session")
    return found


def _refuses_naming_action_session(tmp_path: Path, line: bytes) -> None:
    repo, evidence = _evidence(tmp_path, line57=line)
    conn, cfg = _t25(tmp_path)
    try:
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as exc:
            _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        message = str(exc.value)
        assert "tier2_evidence_refused" in message
        assert "criterion 3: action_session" in message
        assert _count(conn) == 0
    finally:
        conn.close()


def _admits(tmp_path: Path, line: bytes, *, session_text: str) -> None:
    repo, evidence = _evidence(tmp_path, line57=line)
    conn, cfg = _t25(tmp_path)
    try:
        _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert _count(conn) == 1
        row = _row(conn)
        assert row["admission_tier"] == "latch_ladder_tier2"
        blob = json.loads(row["cited_frozen_value_evidence_json"])
        assert blob["quoted_text"] == line.decode("utf-8")
        assert blob["quoted_action_session_text"] == session_text
    finally:
        conn.close()
    assert _session_found(line) == session_text


# --------------------------------------------------------------------------- (i)

@pytest.mark.usefixtures("ticking_clock")
def test_r2_01_i_a_wrong_year_iso_date_refuses_naming_action_session(
    tmp_path: Path,
) -> None:
    """The R2-01 case.  Pre-fix: ``08-10`` is found as the tail of
    ``2025-08-10`` (``-`` is outside ``0-9.``) and the year rule borrows 2026
    over the record's own 2025 -> ADMIT."""
    _refuses_naming_action_session(tmp_path, LINE_I)
    assert _session_found(LINE_I) is None


# --------------------------------------------------------------------------- (ii)

@pytest.mark.usefixtures("ticking_clock")
def test_r2_01_ii_a_bare_mm_dd_still_borrows_the_author_year(tmp_path: Path) -> None:
    _admits(tmp_path, LINE_II, session_text="08-10")


# --------------------------------------------------------------------------- (iii)

@pytest.mark.usefixtures("ticking_clock")
def test_r2_01_iii_an_iso_date_with_a_time_suffix_admits(tmp_path: Path) -> None:
    """Pins that the bound is the HYPHEN, not every non-digit: ``T`` follows
    the ISO date, so a class that also contains letters REFUSES here."""
    _admits(tmp_path, LINE_III, session_text=SESSION)


# --------------------------------------------------------------------------- (iv)

@pytest.mark.usefixtures("ticking_clock")
def test_r2_01_iv_a_year_bearing_non_f13_form_refuses_naming_action_session(
    tmp_path: Path,
) -> None:
    """F13 admits ISO or MM-DD and nothing else; ``08-10-2026`` carries a year
    in neither form, so it fails closed.  Pre-fix: ``08-10`` is found bounded
    by `` `` and ``-`` -> ADMIT."""
    _refuses_naming_action_session(tmp_path, LINE_IV)
    assert _session_found(LINE_IV) is None


# --------------------------------------------------------------------------- (v)

@pytest.mark.usefixtures("ticking_clock")
def test_r2_01_v_line_57_admits_unchanged(tmp_path: Path) -> None:
    _admits(tmp_path, LINE57, session_text=SESSION)


# --------------------------------------------------------------------------- the class

def test_r2_01_the_session_class_is_the_numeral_class_plus_the_hyphen_only() -> None:
    """ONE character (CHARC's shape): the ticker and numeral classes are
    untouched."""
    assert fve._TOKEN_CLASS == {"ticker": "A-Za-z0-9", "session": "0-9.-",
                                "numeral": "0-9."}
