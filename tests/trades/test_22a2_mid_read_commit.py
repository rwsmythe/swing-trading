"""22-A2 R2-04 -- a tier-2 row committed MID-READ is never counted unreplayed.

CHARC's ruling A-R2 item 4 (option a, two tiers).  The four cohort readers
took their tier-2 replay read BEFORE the trade query they count from, so a
correction committed between the two (its relabel and its provenance row
commit together) was counted with no read-time verdict -- silently, which is
F10 not implemented: the row class R1-01 exists for (a raw insert that passed
NO evaluation) reaches the N.

(1) ORDERING: where a reader's counting queries run at the top level, the read
is taken AFTER the last trade query it counts from, so the replayed set is a
superset of the counted set by construction.  The breakdown, the tier
comparison, the card and a direct ``compute_tripwire_status`` call (no read
supplied) reorder.

(2) THE RE-CHECK, only where ordering cannot: ``compute_tripwire_status``
given the breakdown's read runs its own trade query structurally AFTER that
read, so it re-SELECTs the tier-2 row ids after its queries and excludes and
NAMES every row the read did not replay, as ``tier2_unverifiable`` /
``tier2_row_committed_mid_read`` (a reason, not a verdict: ``REPLAY_VERDICTS``
is unchanged).

Every discriminator commits the row in the REAL shape (the service's own
three-key relabel plus a RAW-INSERTED provenance row, one transaction on a
second connection -- the 18-B.1 technique) on the trade-25 world, from inside
the reader's counting query on its first call.  The planted row is a forgery
the service could never write (a negated segment duration), so a replayed
read excludes it: "counted" can only mean "counted unreplayed".
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import open_connection
from swing.data.repos.provenance_corrections import list_provenance_corrections
from swing.trades import frozen_value_evidence as fve
from tests._tier2_world_22a2 import T25_TRADE_ID, insert_payload
from tests.trades.test_22a2_cohort_readers import H1, H1_ID, _seed_cohort
from tests.trades.test_22a2_correction_service import (  # noqa: F401 -- fixture
    _row,
    _trade_keys,
    ticking_clock,
)
from tests.trades.test_22a2_replay import _tier2_world

STALE = (T25_TRADE_ID, "tier2_evidence_stale", "interval.segments_mismatch")
MID_READ = (T25_TRADE_ID, "tier2_unverifiable", "tier2_row_committed_mid_read")


class _MidRead:
    """Trade 25 uncorrected in a byte copy of the world taken before the
    correction; ``commit()`` lands the correction's REAL write shape there."""

    def __init__(self, tmp_path: Path, monkeypatch) -> None:
        pristine = tmp_path / "t25-mid" / "swing.db"
        w = _tier2_world(tmp_path, pristine_copy=pristine)
        payload = _row(w.conn)
        keys = _trade_keys(w.conn)
        w.conn.close()
        blob = json.loads(payload["cited_frozen_value_evidence_json"])
        seg = blob["interval"]["segments"][1]
        assert seg["kind"] == "writer_absence_only" and seg["seconds"] > 0
        seg["seconds"] = -seg["seconds"]
        payload["cited_frozen_value_evidence_json"] = json.dumps(blob)
        self._payload = payload
        self._keys = keys
        self._path = pristine
        self.committed = 0
        monkeypatch.setattr(fve, "EVIDENCE_REPO_DIR", w.git.work)
        self.conn = open_connection(pristine)
        _seed_cohort(self.conn)
        assert list_provenance_corrections(self.conn) == []
        assert _trade_keys(self.conn) != keys

    def commit(self) -> None:
        """The correction's write, committed on ANOTHER connection."""
        from swing.data.repos.trades import update_cohort_provenance

        label, candidate_id, origin = self._keys
        other = open_connection(self._path)
        try:
            with other:
                update_cohort_provenance(
                    other, trade_id=T25_TRADE_ID, hypothesis_label=label,
                    candidate_id=candidate_id, trade_origin=origin)
                insert_payload(other, self._payload)
        finally:
            other.close()
        self.committed += 1

    def on_first_call(self, monkeypatch, target, name: str) -> None:
        """``target.name`` commits the correction on its FIRST call, before it
        runs its own query."""
        real = getattr(target, name)

        def wrapped(*a, **kw):
            if not self.committed:
                self.commit()
            return real(*a, **kw)

        monkeypatch.setattr(target, name, wrapped)

    def on_first_call_after_the_read(self, monkeypatch, target, name: str) -> None:
        """``target.name`` commits on its first call AFTER a tier-2 read."""
        real = getattr(target, name)
        real_read = fve.tier2_cohort_exclusions
        state = {"read": False}

        def reading(*a, **kw):
            state["read"] = True
            return real_read(*a, **kw)

        def wrapped(*a, **kw):
            if state["read"] and not self.committed:
                self.commit()
            return real(*a, **kw)

        monkeypatch.setattr(fve, "tier2_cohort_exclusions", reading)
        monkeypatch.setattr(target, name, wrapped)


@pytest.fixture
def mid(tmp_path: Path, ticking_clock, monkeypatch):  # noqa: F811
    m = _MidRead(tmp_path, monkeypatch)
    try:
        yield m
    finally:
        m.conn.close()


# --------------------------------------------------------------------------- the unchanged case

def test_the_unchanged_case_the_row_committed_before_the_read_is_replayed(mid) -> None:
    """No mid-read commit: the row is there before the reader starts, and every
    reader replays it (excluded, stale, named) -- the ordering changes nothing
    here."""
    from swing.journal.stats import compute_hypothesis_progress_breakdown
    from swing.recommendations.hypothesis import compute_tripwire_status

    mid.commit()
    tw = compute_tripwire_status(mid.conn, hypothesis_id=H1_ID, starting_equity=1200.0)
    assert (tw.current_sample, tw.tier2_excluded) == (1, (STALE,))
    rows = {r.hypothesis_id: r for r in compute_hypothesis_progress_breakdown(
        mid.conn, starting_equity=1200.0)}
    assert (rows[H1_ID].current_sample, rows[H1_ID].tier2_excluded) == (1, (STALE,))


# --------------------------------------------------------------------------- tier (1): ordering

def test_tripwire_status_without_a_read_replays_after_its_trade_query(
    mid, monkeypatch,
) -> None:
    """PRE: the read ran first (no tier-2 row), then the trade query saw trade
    25 relabelled into H1 -> N 2, nothing named.  POST: the read follows the
    query, replays the row, excludes it."""
    import swing.data.repos.trades as trades_repo
    from swing.recommendations.hypothesis import compute_tripwire_status

    mid.on_first_call(monkeypatch, trades_repo, "list_closed_trades")
    tw = compute_tripwire_status(mid.conn, hypothesis_id=H1_ID, starting_equity=1200.0)
    assert mid.committed == 1
    assert (tw.current_sample, tw.tier2_excluded) == (1, (STALE,))


def test_journal_breakdown_replays_after_its_trade_queries(mid, monkeypatch) -> None:
    import swing.data.repos.trades as trades_repo
    from swing.journal.stats import compute_hypothesis_progress_breakdown

    mid.on_first_call(monkeypatch, trades_repo, "list_closed_trades")
    rows = {r.hypothesis_id: r for r in compute_hypothesis_progress_breakdown(
        mid.conn, starting_equity=1200.0)}
    assert mid.committed == 1
    assert (rows[H1_ID].current_sample, rows[H1_ID].tier2_excluded) == (1, (STALE,))


def test_tier_comparison_replays_after_its_cohort_loads(mid, monkeypatch) -> None:
    import swing.metrics.tier as tier_mod

    mid.on_first_call(monkeypatch, tier_mod, "list_closed_trades_for_cohort")
    result = tier_mod.compute_tier_comparison(mid.conn)
    assert mid.committed == 1
    h1 = {c.cohort_name: c for c in result.cohorts}[H1]
    assert (h1.n_closed, h1.tier2_excluded) == (1, (STALE,))


def test_progress_card_replays_after_its_cohort_loads(mid, monkeypatch) -> None:
    import swing.web.view_models.metrics.hypothesis_progress_card as card_mod

    mid.on_first_call(monkeypatch, card_mod, "_list_cohort_trades_sorted")
    vm = card_mod.build_hypothesis_progress_card_vm(cfg=None, conn=mid.conn)
    assert mid.committed == 1
    h1 = {c.cohort_name: c for c in vm.cohorts}[H1]
    assert (h1.n_closed, h1.tier2_excluded) == (1, (STALE,))


# --------------------------------------------------------------------------- tier (2): the re-check

def test_tripwire_status_given_a_read_names_a_row_committed_after_it(
    mid, monkeypatch,
) -> None:
    """The caller's read replayed nothing (no tier-2 row yet); the tripwire's
    own trade query, structurally after it, sees trade 25 relabelled.  PRE: N 2,
    nothing named.  POST: excluded and named ``tier2_row_committed_mid_read``
    under the EXISTING unverifiable verdict."""
    import swing.data.repos.trades as trades_repo
    from swing.recommendations.hypothesis import compute_tripwire_status

    read = fve.tier2_cohort_exclusions(mid.conn, now=fve.datetime.now(fve.UTC))
    assert read.exclusions == {}
    mid.on_first_call(monkeypatch, trades_repo, "list_closed_trades")
    tw = compute_tripwire_status(mid.conn, hypothesis_id=H1_ID, starting_equity=1200.0,
                                 cohort_read=read)
    assert mid.committed == 1
    assert (tw.current_sample, tw.tier2_excluded) == (1, (MID_READ,))
    assert tw.tier2_observed == ()


def test_journal_breakdown_names_a_row_committed_inside_its_tripwire_query(
    mid, monkeypatch,
) -> None:
    """The breakdown's own N is taken from its snapshot (trade 25 not yet in
    H1: N 1); the row lands on the tripwire's query after the read, and the
    tripwire's exclusion is NAMED on the H1 row.  PRE: the breakdown's own
    query is the first after the read, so N reads 2 unreplayed."""
    import swing.data.repos.trades as trades_repo
    from swing.journal.stats import compute_hypothesis_progress_breakdown

    mid.on_first_call_after_the_read(monkeypatch, trades_repo, "list_closed_trades")
    rows = {r.hypothesis_id: r for r in compute_hypothesis_progress_breakdown(
        mid.conn, starting_equity=1200.0)}
    assert mid.committed == 1
    assert (rows[H1_ID].current_sample, rows[H1_ID].tier2_excluded) == (1, (MID_READ,))


def test_the_mid_read_reason_is_a_reason_not_a_verdict() -> None:
    assert fve.REASON_TIER2_ROW_COMMITTED_MID_READ == "tier2_row_committed_mid_read"
    assert fve.REPLAY_VERDICTS == ("ADMIT", "tier2_evidence_stale", "tier2_unverifiable")
    specs = {spec for _k, spec, _b in fve.frozen_value_evidence_digest_parts()}
    assert not any(s.endswith(":REASON_TIER2_ROW_COMMITTED_MID_READ") for s in specs)


def test_the_recheck_is_a_select_not_a_second_replay(mid, monkeypatch) -> None:
    """The re-check runs NO replay and NO git: a row the read already replayed
    keeps its own verdict, and nothing new is replayed."""
    mid.commit()
    read = fve.tier2_cohort_exclusions(mid.conn, now=fve.datetime.now(fve.UTC))
    assert read.excluded_among([T25_TRADE_ID]) == (STALE,)
    calls: list = []
    monkeypatch.setattr(fve, "replay_verdict", lambda *a, **kw: calls.append(a))
    rechecked = read.recheck(mid.conn, now=fve.datetime.now(fve.UTC))
    assert calls == []
    assert rechecked == read


def test_a_read_carries_the_rows_it_replayed(mid) -> None:
    empty = fve.tier2_cohort_exclusions(mid.conn, now=fve.datetime.now(fve.UTC))
    assert empty.replayed_row_ids == frozenset()
    mid.commit()
    (row,) = list_provenance_corrections(mid.conn)
    read = fve.tier2_cohort_exclusions(mid.conn, now=fve.datetime.now(fve.UTC))
    assert read.replayed_row_ids == frozenset({row.provenance_correction_id})
    assert isinstance(mid.conn, sqlite3.Connection)
