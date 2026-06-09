from __future__ import annotations

import sqlite3

import pytest

from research.harness.shadow_expectancy import io
from tests.research.shadow_expectancy.testkit import (  # built in this task
    insert_candidate,
    insert_detection,
    insert_observation,
    insert_pipeline_run,
    make_db,
)


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    return make_db(tmp_path)


def test_resolve_candidate_joins_via_pipeline_evaluation_run(conn):
    eval_id = insert_candidate(conn, ticker="AAA", bucket="aplus", pivot=10.0,
                               initial_stop=9.0)
    pr_id = insert_pipeline_run(conn, eval_id)  # testkit INSERTS the pipeline_runs row
    cand = io.resolve_candidate(conn, pipeline_run_id=pr_id, ticker="AAA")
    assert cand is not None and cand.bucket == "aplus" and cand.pivot == 10.0


def test_resolve_candidate_missing_returns_none(conn):
    assert io.resolve_candidate(conn, pipeline_run_id=999, ticker="ZZZ") is None


def test_read_observation_chain_returns_bars_with_status(conn):
    eval_id = insert_candidate(conn, ticker="AAA", bucket="aplus", pivot=10.0, initial_stop=9.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="AAA", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-05-29", o=9, h=9.8, l=8.9, c=9.5,
                       status="pending")
    insert_observation(conn, det_id, "2026-06-01", o=9.6, h=10.2, l=9.5, c=10.1,
                       status="triggered_open", event="entry_fired")
    chain = io.read_observation_chain(conn, det_id)
    assert [o.observation_date for o in chain] == ["2026-05-29", "2026-06-01"]
    assert chain[1].status == "triggered_open" and chain[1].status_change_event == "entry_fired"
