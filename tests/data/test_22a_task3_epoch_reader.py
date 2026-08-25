"""22-A Task 3 -- the Python that READS what migration 0037 wrote.

The models, the link repo, and THE ONE EPOCH READER with its body-comparison
barrier-integrity check.  Nothing here is versioned, which is exactly why it is
a separate task from the migration: reading is freely splittable, a versioned
migration file is not.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, open_connection, run_migrations
from swing.data.models import (
    FREEZE_TIER_LIVE_AT_ACCEPTANCE,
    FREEZE_TIER_PRE_BARRIER,
    LATCH_FREEZE_TIERS,
    PROVENANCE_LATCH_CITATION_FIELDS,
    LatchOrderMandateLink,
    ProvenanceCorrection,
)
from swing.data.repos.candidates_immutability_epoch import (
    _CANDIDATES_BARRIER_DDL,
    BARRIER_TRIGGER_NAMES,
    barrier_installed,
    epoch_boundary,
    freeze_tier_for_candidate,
    normalize_trigger_sql,
)
from swing.data.repos.latch_order_mandate_links import (
    get_link,
    list_links_for_broker_order,
    list_links_for_ticker,
)
from swing.trades.latched_origin import LATCH_PROBE_EVIDENCE_VERSION
from tests._latch_link_fixtures_22a import (
    BROKER_ORDER_ID,
    INITIAL_STOP,
    PIVOT,
    accept_order,
    seed_fire,
)

SWING = Path(__file__).resolve().parents[2] / "swing"
MIGRATION = SWING / "data" / "migrations" / "0037_latch_order_mandate_links.sql"


@pytest.fixture()
def conn(tmp_path: Path):
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _sql_twin_tier(conn: sqlite3.Connection, candidate_id: int) -> str:
    """The MINTING TRIGGER's own CASE, run standalone.

    Lifted from migration 0037 by SHAPE, not by re-derivation: if the two ever
    disagree the drift test below is what says so, and a twin that re-derived
    the rule from the plan rather than from the SQL would agree with the
    Python by construction and prove nothing.
    """
    return conn.execute(
        "SELECT CASE WHEN ? > (SELECT max_candidate_id_at_barrier "
        "FROM candidates_immutability_epoch WHERE epoch_id = 1) "
        "THEN 'live_at_acceptance' ELSE 'pre_barrier_reconstructed' END",
        (candidate_id,),
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# The epoch reader
# ---------------------------------------------------------------------------
def test_the_boundary_is_read_from_the_epoch_row(conn) -> None:
    assert epoch_boundary(conn) == 0  # a fresh DB has no candidates


def test_a_pre_0037_database_has_no_boundary_and_nothing_is_post_barrier(
        tmp_path: Path) -> None:
    c = open_connection(tmp_path / "v36.db")
    try:
        run_migrations(c, target_version=36)
        assert epoch_boundary(c) is None
        tier, installed = freeze_tier_for_candidate(c, 99999)
        assert tier == FREEZE_TIER_PRE_BARRIER
        assert installed is False
    finally:
        c.close()


def test_the_sql_twin_and_the_python_reader_agree_at_below_equal_above_case_38(
        conn) -> None:
    """Case 38 -- TWO SPELLINGS, ONE RULE, over SINGLE-STATE fixtures.

    AND IT ASSERTS THE EXPECTED TIER AT EACH POSITION, NOT MERELY THAT THE TWO
    AGREE (inherited finding 22A-R9-02).  S2.4d says at-or-below the boundary
    is PRE-barrier while S4.5C's lifted quote says "rows at or after it do
    [admit]" -- and an agreement-only test cannot separate them, because TWO
    IDENTICALLY-WRONG ``>=`` implementations agree.  The boundary row already
    existed when the barrier was installed, so it is PRE-barrier and the
    comparison is STRICTLY GREATER THAN.
    """
    seed_fire(conn, candidate_id=500)
    conn.commit()
    boundary = 500
    conn.execute("DROP TRIGGER trg_candidates_epoch_no_update")
    conn.execute(
        "UPDATE candidates_immutability_epoch SET max_candidate_id_at_barrier = ?",
        (boundary,))
    expected = {
        boundary - 1: FREEZE_TIER_PRE_BARRIER,   # below
        boundary: FREEZE_TIER_PRE_BARRIER,       # EQUAL -- the discriminator
        boundary + 1: FREEZE_TIER_LIVE_AT_ACCEPTANCE,  # above
    }
    for candidate_id, want in expected.items():
        python_tier, _ = freeze_tier_for_candidate(conn, candidate_id)
        sql_tier = _sql_twin_tier(conn, candidate_id)
        assert python_tier == want, f"python reader at {candidate_id}"
        assert sql_tier == want, f"sql twin at {candidate_id}"


def test_the_python_freeze_tiers_are_the_two_valued_set() -> None:
    assert LATCH_FREEZE_TIERS == {
        FREEZE_TIER_LIVE_AT_ACCEPTANCE, FREEZE_TIER_PRE_BARRIER}


# ---------------------------------------------------------------------------
# The barrier-integrity check -- CHARC's requirement, as AMENDED by 22A-R9-01
# ---------------------------------------------------------------------------
def test_a_post_barrier_fire_reads_live_with_the_barrier_intact_case_50a(
        conn) -> None:
    """Case 50a -- both barriers canonical, post-barrier fire."""
    tier, installed = freeze_tier_for_candidate(conn, epoch_boundary(conn) + 1)
    assert (tier, installed) == (FREEZE_TIER_LIVE_AT_ACCEPTANCE, True)


def test_a_dropped_update_barrier_refuses_even_a_post_barrier_fire_case_50b(
        conn) -> None:
    """Case 50b -- ``trg_candidates_no_update`` DROPPED.

    An implementation reading only the stored tier passes 50a and fails this:
    the fire is genuinely post-barrier, and the refusal is about whether the
    guarantee is STILL STANDING, not about which side of the boundary the fire
    fell on.
    """
    conn.execute("DROP TRIGGER trg_candidates_no_update")
    tier, installed = freeze_tier_for_candidate(conn, epoch_boundary(conn) + 1)
    assert tier == FREEZE_TIER_LIVE_AT_ACCEPTANCE
    assert installed is False


def test_both_barriers_dropped_refuses_case_50c(conn) -> None:
    """Case 50c -- both DROPPED."""
    conn.execute("DROP TRIGGER trg_candidates_no_update")
    conn.execute("DROP TRIGGER trg_candidates_no_delete")
    assert barrier_installed(conn) is False


def test_a_same_name_no_op_trigger_does_not_satisfy_the_check_case_50d(
        conn) -> None:
    """Case 50d -- THE RULED DISCRIMINATOR (22A-R9-01, CHARC).

    *A body check never exercised against a wrong body is the existence check
    wearing better clothes.*  A NAME-ONLY implementation COUNTS TWO here and
    ADMITS, while ``candidates`` is fully mutable -- and it passes 50a, 50b and
    50c, every one of which only ever REMOVED names.
    """
    conn.execute("DROP TRIGGER trg_candidates_no_update")
    conn.execute(
        "CREATE TRIGGER trg_candidates_no_update BEFORE UPDATE ON candidates "
        "BEGIN SELECT 1; END")
    # the name is present and the count is right...
    present = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' AND name IN "
        "('trg_candidates_no_update', 'trg_candidates_no_delete')").fetchone()[0]
    assert present == 2
    # ...and candidates is FULLY MUTABLE, which is the point
    cid = seed_fire(conn)
    conn.execute("UPDATE candidates SET pivot = 1.0 WHERE id = ?", (cid,))
    assert conn.execute(
        "SELECT pivot FROM candidates WHERE id = ?", (cid,)).fetchone()[0] == 1.0
    assert barrier_installed(conn) is False


def test_the_normalization_bound_holds_in_both_directions_case_50e(
        conn) -> None:
    """Case 50e -- the wrong TABLE refuses; whitespace-only ADMITS.

    Both halves are required.  A stricter BYTE-equality implementation fails
    the whitespace half; a semantic comparator is not needed to pass it -- and
    a comparator that judged equivalence would be a NEW FREE DIMENSION doing
    silent work, which is the defect class this arc spent nine rounds on.
    """
    canonical = _CANDIDATES_BARRIER_DDL["trg_candidates_no_update"]

    # (a) same name, same body, WRONG TABLE -> REFUSE
    conn.execute("DROP TRIGGER trg_candidates_no_update")
    conn.execute(canonical.replace(
        "BEFORE UPDATE ON candidates", "BEFORE UPDATE ON candidate_criteria"))
    assert barrier_installed(conn) is False

    # (b) body differing ONLY by added whitespace/newlines -> ADMIT
    conn.execute("DROP TRIGGER trg_candidates_no_update")
    conn.execute(canonical.replace("BEGIN SELECT", "BEGIN\n\n    SELECT"))
    live = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'trg_candidates_no_update'"
    ).fetchone()[0]
    assert live != canonical, "the whitespace variant must differ BYTEWISE"
    assert normalize_trigger_sql(live) == normalize_trigger_sql(canonical)
    assert barrier_installed(conn) is True


def test_a_dropped_replace_barrier_also_refuses(conn) -> None:
    """THE THIRD BARRIER IS PINNED TOO, AND THAT EXCEEDS THE RULING'S LETTER.

    CHARC's requirement named the barrier when it was UPDATE + DELETE; his own
    later generalisation added ``trg_candidates_no_replace``, and that is the
    trigger closing the MEASURED bypass -- with it gone, ``INSERT OR REPLACE``
    rewrites a fire's pivot and stop while both other triggers sit present and
    unfired.  A body check omitting it would certify a barrier that can be
    walked around.  Strengthening in the fail-CLOSED direction, declared.
    """
    conn.execute("DROP TRIGGER trg_candidates_no_replace")
    assert barrier_installed(conn) is False


def test_the_pinned_ddl_matches_the_migration_verbatim(conn) -> None:
    """THE PIN IS COMPARED AGAINST THE LIVE SCHEMA, not against the file.

    A pinned copy that had drifted from the migration would make every
    admission refuse ``barrier_not_installed`` -- a fail-closed break, but a
    total one, and nothing else in the arc would say why.
    """
    for name, pinned in _CANDIDATES_BARRIER_DDL.items():
        live = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()
        assert live is not None, name
        assert normalize_trigger_sql(live[0]) == normalize_trigger_sql(pinned), (
            f"{name}: the pinned copy has drifted from migration 0037")


def test_normalization_is_whitespace_only() -> None:
    """It does NOT lower-case, re-order or parse.  The bound is the ruling's."""
    assert normalize_trigger_sql("a\n\t b  c ") == "a b c"
    assert normalize_trigger_sql("SELECT") != normalize_trigger_sql("select")


def test_the_epoch_is_read_in_exactly_one_place() -> None:
    """S4.5C: ONE reader, no boundary arithmetic scattered through call sites.

    Method: a text scan of every ``.py`` and ``.sql`` under ``swing/`` for the
    boundary column name, and for each barrier trigger NAME.  Both are bounded
    from BELOW by a grep, which is why the assertion is an EXACT SET rather
    than a count -- a new site shows up as a named file, not as a number that
    moved.

    ``sqlite_master`` itself is NOT asserted to be unique: three PRE-EXISTING
    and unrelated sites query it (``swing/cli.py``, ``swing/data/db.py``,
    ``swing/trades/risk_policy.py``), measured, and pretending otherwise would
    make this test fail for reasons that have nothing to do with the barrier.
    What must be unique is the BARRIER query, and the trigger names are what
    identify it.
    """
    reader = "data/repos/candidates_immutability_epoch.py"
    migration = "data/migrations/0037_latch_order_mandate_links.sql"

    def _sites(needle: str) -> set[str]:
        hits = set()
        for path in list(SWING.rglob("*.py")) + list(SWING.rglob("*.sql")):
            if "__pycache__" in path.parts:
                continue
            if needle in path.read_text(encoding="utf-8"):
                hits.add(path.relative_to(SWING).as_posix())
        return hits

    assert _sites("max_candidate_id_at_barrier") == {reader, migration}
    for name in BARRIER_TRIGGER_NAMES:
        assert _sites(name) == {reader, migration}, name


# ---------------------------------------------------------------------------
# The minting behaviour, observed through the repo
# ---------------------------------------------------------------------------
def test_a_pre_migration_fire_accepted_after_0037_mints_pre_barrier_case_25(
        tmp_path: Path) -> None:
    """Case 25 -- ``freeze_tier`` describes the CANDIDATE, not the acceptance.

    The RHI shape: a fire created BEFORE the barrier whose FIRST broker
    acceptance arrives AFTER it.  An implementation that stamped the tier from
    the ACCEPTANCE time -- or hard-coded ``'live_at_acceptance'`` in the
    minting trigger, which is what the plan's own S4.2 text once said -- gives
    it a FALSE structural-proof label, and that is the exact defect the epoch
    exists to prevent.
    """
    c = open_connection(tmp_path / "v36.db")
    try:
        run_migrations(c, target_version=36)
        cid = seed_fire(c)
        c.commit()
        run_migrations(c, target_version=37, backup_dir=tmp_path / "bak")
        assert list_links_for_ticker(c, "FTRE") == []  # nothing to backfill
        accept_order(c, cid)
        [link] = list_links_for_ticker(c, "FTRE")
        assert link.freeze_tier == FREEZE_TIER_PRE_BARRIER
        assert link.candidate_id == cid
        tier, installed = freeze_tier_for_candidate(c, cid)
        assert tier == FREEZE_TIER_PRE_BARRIER
        assert installed is True
    finally:
        c.close()


def test_a_post_migration_fire_mints_live_at_acceptance(conn) -> None:
    cid = seed_fire(conn)
    assert cid > epoch_boundary(conn)
    accept_order(conn, cid)
    [link] = list_links_for_ticker(conn, "FTRE")
    assert link.freeze_tier == FREEZE_TIER_LIVE_AT_ACCEPTANCE


def test_the_lookup_returns_a_list_so_cardinality_is_the_readers(conn) -> None:
    """TWO links may share one broker order id -- there is deliberately no
    UNIQUE on it, because a duplicate would abort the LEDGER write.  The
    signature says so."""
    first = seed_fire(conn)
    second = seed_fire(conn, run_id=131, ticker="FTRE",
                       action_session_date="2026-07-20")
    accept_order(conn, first, key="v1", place_key="p1")
    accept_order(conn, second, key="v2", place_key="p2", run_id=131)
    links = list_links_for_broker_order(conn, BROKER_ORDER_ID)
    assert len(links) == 2
    assert [link.candidate_id for link in links] == [first, second]
    assert list_links_for_broker_order(conn, "no-such-order") == []


def test_the_repo_round_trips_the_minted_row(conn) -> None:
    cid = seed_fire(conn)
    accept_order(conn, cid)
    [link] = list_links_for_ticker(conn, "FTRE")
    assert isinstance(link, LatchOrderMandateLink)
    assert get_link(conn, link.link_id) == link
    assert get_link(conn, 99999) is None
    assert (link.frozen_pivot, link.frozen_invalidation) == (PIVOT, INITIAL_STOP)


def test_a_junk_fire_round_trips_as_NULL_frozen_values(conn) -> None:
    """The dataclass must ACCEPT what the trigger can MINT.

    A ``> 0`` NOT-NULL validator here would make the row unreadable in Python
    while remaining perfectly legal in SQL -- the two layers accepting
    different sets, which is the failure #11 exists to prevent.
    """
    cid = seed_fire(conn, pivot=-1.0, initial_stop=None)
    accept_order(conn, cid)
    [link] = list_links_for_ticker(conn, "FTRE")
    assert (link.frozen_pivot, link.frozen_invalidation) == (None, None)


# ---------------------------------------------------------------------------
# The ProvenanceCorrection widening
# ---------------------------------------------------------------------------
def _real_correction(conn) -> ProvenanceCorrection:
    """A correction row written by the PRODUCTION service and read back.

    Hand-building one is a trap: the model requires FULL frozen snapshots of
    the candidate and the recommendation, and a hand-written envelope drifts
    from what the emitter stores -- this project's most-repeated test defect.
    ``dataclasses.replace`` over a real row exercises the SAME validator a real
    row takes, with exactly one dimension varied.
    """
    from swing.data.repos.provenance_corrections import (
        list_provenance_corrections,
    )
    from swing.trades.cohort_provenance_correction import (
        correct_cohort_provenance,
    )
    from tests.trades._cohort_provenance_fixtures import build_cadl_case

    ids = build_cadl_case(conn)
    if conn.in_transaction:
        conn.commit()
    correct_cohort_provenance(
        conn,
        trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason="22-A task 3 validator fixture",
    )
    [row] = list_provenance_corrections(conn, trade_id=ids["trade_id"])
    return row


def test_the_default_tier_is_last_word_and_carries_no_citation(conn) -> None:
    """AND IT ROUND-TRIPS THROUGH THE WIDENED REPO.

    The read path widens in the SAME place as the write path -- they share one
    column tuple -- so a lagging mapper would surface here as a missing field
    rather than as a silently-dropped citation two arcs later.
    """
    row = _real_correction(conn)
    assert row.admission_tier == "last_word"
    assert all(getattr(row, f) is None for f in PROVENANCE_LATCH_CITATION_FIELDS)


def test_a_last_word_row_carrying_a_latch_citation_is_rejected(conn) -> None:
    row = _real_correction(conn)
    with pytest.raises(ValueError, match="may not disagree"):
        replace(row, cited_latch_link_id=7)


def test_a_latch_ladder_row_missing_any_citation_is_rejected(conn) -> None:
    """ALL FIVE or none.  A partial citation is an admission whose evidence
    cannot be produced, which is indistinguishable at audit from an unchecked
    one."""
    row = _real_correction(conn)
    full = dict(
        admission_tier="latch_ladder", cited_latch_link_id=1,
        cited_latch_validity_intent_id=2, cited_latch_place_intent_id=3,
        cited_latch_broker_order_id="X", cited_latch_probe_json="{}",
    )
    replace(row, **full)  # complete: constructs
    for field in PROVENANCE_LATCH_CITATION_FIELDS:
        partial = dict(full)
        partial[field] = None
        with pytest.raises(ValueError, match="is missing"):
            replace(row, **partial)


def test_an_unknown_admission_tier_is_rejected(conn) -> None:
    row = _real_correction(conn)
    with pytest.raises(ValueError, match="admission_tier"):
        replace(row, admission_tier="latch_ladder_tier2")


def test_the_evidence_version_constant_matches_the_migration() -> None:
    """#11 on a VERSION STRING.  The migration pins ``$.evidence_version`` to a
    literal; if the two ever disagree, every truthful correction row ABORTS."""
    text = MIGRATION.read_text(encoding="utf-8")
    found = set(re.findall(
        r"json_extract\(NEW\.cited_latch_probe_json, '\$\.evidence_version'\)\s*"
        r"= '([^']+)'", text))
    assert found == {LATCH_PROBE_EVIDENCE_VERSION}, found
