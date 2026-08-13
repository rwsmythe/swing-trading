"""Task 3 -- the provenance-corrections repo + the readers/writer it needs.

Each reader is tested for the property the SERVICE depends on, not merely for
returning rows: `fetch_candidate_by_id` must carry the id AND the hydrated
criteria (`Candidate` has no `id` field, which is why
`fetch_candidates_for_run` cannot serve); `snapshot_recommendation_row` must
derive its column set from `PRAGMA table_info` so an omission is not
expressible; `evaluation_run_persistence_bound` must refuse zero, two, and
non-complete pipeline rows rather than picking one.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PROVENANCE_CORRECTED_FIELDS, ProvenanceCorrection
from swing.data.repos.candidates import (
    fetch_candidate_by_id,
    get_evaluation_run_by_id,
)
from swing.data.repos.pipeline import evaluation_run_persistence_bound
from swing.data.repos.provenance_corrections import (
    get_correction_for_trade,
    insert_provenance_correction,
    list_provenance_corrections,
)
from swing.data.repos.recommendations import (
    get_daily_recommendation_by_id,
    list_today_decisions_for_run_ticker,
    snapshot_recommendation_row,
)
from swing.data.repos.trades import update_cohort_provenance
from tests.trades._cohort_provenance_fixtures import (
    CADL_ACTION_SESSION,
    CADL_FILL_DATETIME,
    CADL_F,
    CADL_PIPELINE_FINISHED_LOCAL,
    CADL_RUN_TS_LOCAL,
    build_cadl_case,
    seed_pipeline_run,
    seed_recommendation,
)

RUN_TS_UTC = "2026-08-11T03:30:26"
UPPER_UTC = "2026-08-11T03:44:45"


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


# --------------------------------------------------------------------- readers


def test_fetch_candidate_by_id_carries_id_run_and_hydrated_criteria(
    conn,
) -> None:
    ids = build_cadl_case(conn)
    row = fetch_candidate_by_id(conn, ids["candidate_id"])
    assert row is not None
    assert row.candidate_id == ids["candidate_id"]
    assert row.evaluation_run_id == ids["evaluation_run_id"]
    assert row.candidate.ticker == "CADL"
    assert row.candidate.bucket == "aplus"
    # The criteria are what the label derivation reads; an unhydrated
    # Candidate would silently produce the clean sibling string.
    assert len(row.candidate.criteria) == 18
    non_pass = {c.criterion_name for c in row.candidate.criteria
                if c.result != "pass"}
    assert non_pass == {"TT8_rs_rank"}


def test_fetch_candidate_by_id_returns_none_for_a_missing_row(conn) -> None:
    assert fetch_candidate_by_id(conn, 987654) is None


def test_get_evaluation_run_by_id_returns_both_anchors(conn) -> None:
    ids = build_cadl_case(conn)
    run = get_evaluation_run_by_id(conn, ids["evaluation_run_id"])
    assert run is not None
    assert run.id == ids["evaluation_run_id"]
    assert run.run_ts == CADL_RUN_TS_LOCAL
    assert run.data_asof_date == "2026-08-10"
    assert run.action_session_date == CADL_ACTION_SESSION
    assert get_evaluation_run_by_id(conn, 987654) is None


def test_get_daily_recommendation_by_id(conn) -> None:
    ids = build_cadl_case(conn)
    dr = get_daily_recommendation_by_id(conn, ids["daily_recommendation_id"])
    assert dr is not None
    assert dr.id == ids["daily_recommendation_id"]
    assert dr.recommendation == "today_decision"
    assert get_daily_recommendation_by_id(conn, 987654) is None


def test_list_today_decisions_for_run_ticker_returns_ALL_matches(conn) -> None:
    """The unique index is on (action_session_date, ticker, recommendation),
    NOT on (evaluation_run_id, ...), and `upsert_recommendation` rewrites
    `evaluation_run_id` in place -- so two rows CAN share a run. The reader
    must return both and let the caller refuse, never `fetchone()`."""
    ids = build_cadl_case(conn)
    second = seed_recommendation(
        conn, evaluation_run_id=ids["evaluation_run_id"],
        data_asof_date="2026-08-10", action_session_date="2026-08-12",
        ticker="CADL", recommendation="today_decision",
    )
    rows = list_today_decisions_for_run_ticker(
        conn, evaluation_run_id=ids["evaluation_run_id"], ticker="CADL")
    assert sorted(r.id for r in rows) == sorted(
        [ids["daily_recommendation_id"], second])
    # near_trigger rows are NOT today_decision rows.
    seed_recommendation(
        conn, evaluation_run_id=ids["evaluation_run_id"],
        data_asof_date="2026-08-10", action_session_date="2026-08-13",
        ticker="CADL", recommendation="near_trigger",
    )
    rows2 = list_today_decisions_for_run_ticker(
        conn, evaluation_run_id=ids["evaluation_run_id"], ticker="CADL")
    assert len(rows2) == 2


def test_snapshot_recommendation_row_column_set_is_pragma_derived(conn) -> None:
    """A hand-list rots on the next ALTER TABLE, and the first draft's silently
    omitted `action_text` / `risk_dollars` / `risk_pct` while calling itself
    'the full row'. Derived, so an omission is not expressible."""
    ids = build_cadl_case(conn)
    snap = snapshot_recommendation_row(
        conn, ids["daily_recommendation_id"])
    live_cols = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(daily_recommendations)").fetchall()
    }
    assert set(snap) == live_cols
    for must in ("action_text", "risk_dollars", "risk_pct",
                 "evaluation_run_id", "action_session_date", "id"):
        assert must in snap
    assert snap["id"] == ids["daily_recommendation_id"]
    assert json.dumps(snap, sort_keys=True)  # JSON-serializable
    assert snapshot_recommendation_row(conn, 987654) is None


def test_persistence_bound_accepts_exactly_one_complete_row(conn) -> None:
    ids = build_cadl_case(conn)
    bound = evaluation_run_persistence_bound(
        conn, evaluation_run_id=ids["evaluation_run_id"])
    assert bound is not None
    assert bound.pipeline_run_id == ids["pipeline_run_id"]
    assert bound.finished_ts == CADL_PIPELINE_FINISHED_LOCAL
    assert bound.snapshot["state"] == "complete"
    assert bound.snapshot["evaluation_run_id"] == ids["evaluation_run_id"]
    assert bound.snapshot["finished_ts"] == CADL_PIPELINE_FINISHED_LOCAL


def test_persistence_bound_refuses_zero_two_and_incomplete(conn) -> None:
    ids = build_cadl_case(conn, pipeline_rows=0)
    assert evaluation_run_persistence_bound(
        conn, evaluation_run_id=ids["evaluation_run_id"]) is None

    two = build_cadl_case(conn, pipeline_rows=2, ticker="TWO")
    assert evaluation_run_persistence_bound(
        conn, evaluation_run_id=two["evaluation_run_id"]) is None

    running = build_cadl_case(
        conn, ticker="RUN", pipeline_state="running",
        pipeline_finished_ts=None,
    )
    assert evaluation_run_persistence_bound(
        conn, evaluation_run_id=running["evaluation_run_id"]) is None

    # A `complete` row with a NULL finished_ts bounds nothing either.
    nofin = build_cadl_case(
        conn, ticker="NUL", pipeline_rows=0)
    seed_pipeline_run(
        conn, evaluation_run_id=nofin["evaluation_run_id"],
        data_asof_date="2026-08-10", action_session_date=CADL_ACTION_SESSION,
        finished_ts=None, state="complete",
    )
    assert evaluation_run_persistence_bound(
        conn, evaluation_run_id=nofin["evaluation_run_id"]) is None


# --------------------------------------------------------------------- writer


def test_update_cohort_provenance_writes_exactly_three_columns(conn) -> None:
    ids = build_cadl_case(conn)
    before = conn.execute(
        "SELECT * FROM trades WHERE id = ?", (ids["trade_id"],)).fetchone()
    cols = [d[0] for d in conn.execute(
        "SELECT * FROM trades WHERE id = ?", (ids["trade_id"],)).description]
    update_cohort_provenance(
        conn, trade_id=ids["trade_id"],
        hypothesis_label="A+ baseline (aplus)",
        candidate_id=ids["candidate_id"],
        trade_origin="pipeline_aplus",
    )
    after = conn.execute(
        "SELECT * FROM trades WHERE id = ?", (ids["trade_id"],)).fetchone()
    changed = {
        c for c, b, a in zip(cols, before, after, strict=True) if b != a
    }
    assert changed == {"hypothesis_label", "candidate_id", "trade_origin"}


def test_update_cohort_provenance_raises_on_a_missing_trade(conn) -> None:
    with pytest.raises(ValueError):
        update_cohort_provenance(
            conn, trade_id=987654, hypothesis_label="x", candidate_id=1,
            trade_origin="pipeline_aplus")


def test_update_cohort_provenance_refuses_a_non_enum_origin(conn) -> None:
    ids = build_cadl_case(conn)
    with pytest.raises(ValueError):
        update_cohort_provenance(
            conn, trade_id=ids["trade_id"], hypothesis_label="x",
            candidate_id=ids["candidate_id"], trade_origin="nonsense")


# ------------------------------------------------------------- audit-row repo


def _correction(ids: dict, **overrides) -> ProvenanceCorrection:
    """A correction built from the PRODUCTION snapshot writer."""
    base = dict(
        provenance_correction_id=None,
        trade_id=ids["trade_id"],
        entry_fill_id=ids["fill_id"],
        entry_fill_id_at_correction=ids["fill_id"],
        entry_fill_snapshot_json=json.dumps({
            "fill_id": ids["fill_id"], "trade_id": ids["trade_id"],
            "action": "entry", "fill_datetime": CADL_FILL_DATETIME,
        }, sort_keys=True),
        cited_candidate_id=ids["candidate_id"],
        cited_daily_recommendation_id=ids["daily_recommendation_id"],
        cited_evaluation_run_id=ids["evaluation_run_id"],
        cited_hypothesis_id=1,
        cited_hypothesis_status_history_id=1,
        cited_hypothesis_status_at_record="active",
        cited_pipeline_finished_ts_raw=CADL_PIPELINE_FINISHED_LOCAL,
        cited_run_ts_utc=RUN_TS_UTC,
        cited_status_window_upper_utc=UPPER_UTC,
        cited_pipeline_run_id=ids["pipeline_run_id"],
        cited_pipeline_run_snapshot_json=json.dumps({
            "id": ids["pipeline_run_id"],
            "evaluation_run_id": ids["evaluation_run_id"],
            "state": "complete", "started_ts": "2026-08-10T17:30:00",
            "finished_ts": CADL_PIPELINE_FINISHED_LOCAL,
        }, sort_keys=True),
        cited_hypothesis_status_recorded_at="2026-04-25T00:00:00.000",
        cited_hypothesis_status_effective_from="2026-04-25T00:00:00.000",
        cited_hypothesis_status_effective_to=None,
        cited_hypothesis_name_at_correction="A+ baseline",
        cited_candidate_action_session_date=CADL_ACTION_SESSION,
        cited_recommendation_action_session_date=CADL_ACTION_SESSION,
        entry_fill_session_date=CADL_F,
        cited_run_ts_raw=CADL_RUN_TS_LOCAL,
        # THE PRODUCTION SNAPSHOT (Codex R3 Minor 8). A three-field
        # hand-write is emitter-impossible -- production freezes every
        # PRAGMA-derived column -- so a round-trip test built on it would pass
        # against a snapshot implementation that never froze the whole row.
        cited_recommendation_snapshot_json=json.dumps(
            ids["dr_snapshot"], sort_keys=True),
        derivation_rule_version="2026-08-12.1",
        pre_value_json=json.dumps({
            "trades.hypothesis_label": None,
            "trades.candidate_id": None,
            "trades.trade_origin": "manual_off_pipeline",
        }, sort_keys=True),
        applied_value_json=json.dumps({
            "trades.hypothesis_label": "A+ baseline (aplus)",
            "trades.candidate_id": ids["candidate_id"],
            "trades.trade_origin": "pipeline_aplus",
        }, sort_keys=True),
        corrected_fields_json=json.dumps(list(PROVENANCE_CORRECTED_FIELDS)),
        applied_at="2026-08-13T00:00:00.000",
        applied_by="operator",
        correction_reason="the framework's own record",
        risk_policy_id_at_correction=None,
    )
    base.update(overrides)
    return ProvenanceCorrection(**base)


def test_insert_then_read_back_round_trips_every_column(conn) -> None:
    ids = build_cadl_case(conn)
    row = _correction(ids)
    cid = insert_provenance_correction(conn, row)
    assert cid > 0
    back = get_correction_for_trade(conn, ids["trade_id"])
    assert back is not None
    assert back.provenance_correction_id == cid
    for field in row.__dataclass_fields__:
        if field == "provenance_correction_id":
            continue
        assert getattr(back, field) == getattr(row, field), field


def test_get_correction_for_trade_is_none_when_absent(conn) -> None:
    ids = build_cadl_case(conn)
    assert get_correction_for_trade(conn, ids["trade_id"]) is None


def test_list_provenance_corrections_filters_by_trade(conn) -> None:
    a = build_cadl_case(conn)
    b = build_cadl_case(conn, ticker="VSTS")
    insert_provenance_correction(conn, _correction(a))
    insert_provenance_correction(conn, _correction(b))
    assert len(list_provenance_corrections(conn)) == 2
    only = list_provenance_corrections(conn, trade_id=b["trade_id"])
    assert [r.trade_id for r in only] == [b["trade_id"]]


def test_repo_does_not_commit(conn) -> None:
    """Repo functions run inside the CALLER's transaction (the project's
    repo-vs-service asymmetry); a repo that committed would close the
    service's single transaction out from under it."""
    ids = build_cadl_case(conn)
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    insert_provenance_correction(conn, _correction(ids))
    update_cohort_provenance(
        conn, trade_id=ids["trade_id"], hypothesis_label="x",
        candidate_id=ids["candidate_id"], trade_origin="pipeline_aplus")
    assert conn.in_transaction
    conn.rollback()
    assert get_correction_for_trade(conn, ids["trade_id"]) is None
    assert conn.execute(
        "SELECT hypothesis_label FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone()[0] is None


def test_trade_origins_mirror_matches_the_live_check(conn) -> None:
    """#11: the Python frozenset and the SQL CHECK are one fact in two places.

    Read off the LIVE DDL rather than the migration file, so a later rebuild
    that widened the CHECK without widening the mirror fails HERE.
    """
    import re

    from swing.data.repos.trades import TRADE_ORIGINS

    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'trades'").fetchone()[0]
    match = re.search(
        r"trade_origin\s+TEXT\s+NOT NULL\s+CHECK\s*\(\s*trade_origin IN"
        r"\s*\(([^)]*)\)", ddl, re.IGNORECASE | re.DOTALL)
    assert match, "the trades.trade_origin CHECK was not found in the live DDL"
    members = {m.strip().strip("'") for m in match.group(1).split(",")}
    assert members == set(TRADE_ORIGINS)
