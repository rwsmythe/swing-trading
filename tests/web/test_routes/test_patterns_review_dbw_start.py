"""D53.1 F1 -- the double_bottom_w review guard on an exemplar's start_date.

After D53 a DBW verdict is produced on the trough-2-anchored window, so the
generator start persisted as ``window_start_date`` is trough 2, never the
pattern start. The review route seeds ``pattern_exemplars`` (a measurement
input), so for a DBW evaluation and every decision whose exemplar is READ as
a pattern instance (confirm, watch, pattern_present_outside_window,
multiple_overlapping_patterns) CHARC's ruling orders the route:

  (i)   a submitted corrected start EQUAL to ``window_start_date`` is not a
        correction (the form pre-fills it);
  (ii)  a typed start that DIFFERS wins;
  (iii) a non-zero ``geometric_score`` takes ``evidence.trough_1_date``;
  (iv)  a zero ``geometric_score`` REFUSES before any write, naming the
        recovery (a typed start via pattern_present_outside_window).

reject and relabel are unchanged. The untouched-submit case is built from
the value the review template actually renders, not a bare POST.

Evidence JSON is serialized exactly as the runner does
(``json.dumps(dataclasses.asdict(evidence), default=str)``) from the real
dataclass and the real zero-envelope builder.
"""
from __future__ import annotations

import dataclasses
import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import PatternEvaluation
from swing.data.repos import pattern_evaluations as evals_repo
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.patterns.double_bottom_w import (
    DoubleBottomWEvidence,
    _build_zero_evidence,
)
from swing.web.app import create_app

TROUGH_1 = date(2026, 3, 2)
CENTER = date(2026, 3, 20)
TROUGH_2 = date(2026, 4, 8)
WINDOW_END = date(2026, 4, 24)


def _nonzero_evidence() -> DoubleBottomWEvidence:
    flags = {f"criterion_{i}": True for i in range(1, 9)}
    flags["criterion_7"] = False
    return DoubleBottomWEvidence(
        stage="stage_2", recent_stage="undefined",
        trough_1_date=TROUGH_1, trough_1_price=80.0,
        trough_1_drawdown_pct=0.2, trough_1_avg_volume=1000.0,
        center_peak_date=CENTER, center_peak_price=95.0,
        center_peak_retracement_pct=0.75,
        trough_2_date=TROUGH_2, trough_2_price=79.0,
        trough_2_avg_volume=900.0, undercut=True,
        trough_1_to_center_duration_days=18,
        center_to_trough_2_duration_days=19,
        pivot_price=95.0, criteria_pass=flags, geometric_score=1.10,
    )


def _zero_evidence() -> DoubleBottomWEvidence:
    # The real zero envelope stamps trough_1_date = the window END.
    return _build_zero_evidence(
        stage="stage_2", anchor_date=WINDOW_END,
        criteria_pass={"criterion_1": True},
    )


def _seed_dbw(cfg, evidence, *, evidence_json: str | None = None) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = int(conn.execute(
                """
                INSERT INTO pipeline_runs
                    (started_ts, finished_ts, trigger, data_asof_date,
                     action_session_date, state, lease_token)
                VALUES ('2026-04-24T09:00:00', '2026-04-24T09:05:00',
                        'manual', '2026-04-24', '2026-04-27',
                        'complete', 't-x')
                """
            ).lastrowid)
            ev = PatternEvaluation(
                id=None, pipeline_run_id=run_id, ticker="DBW",
                pattern_class="double_bottom_w",
                detector_version="double_bottom_w@v1.1.0",
                geometric_score=float(evidence.geometric_score),
                geometric_score_json=json.dumps(evidence.criteria_pass),
                composite_score=min(1.0, float(evidence.geometric_score)),
                structural_evidence_json=(
                    evidence_json if evidence_json is not None
                    else json.dumps(dataclasses.asdict(evidence), default=str)
                ),
                feature_distribution_log_json="{}",
                # The generator start under v1.1.0 = the trough-2 anchor.
                window_start_date=TROUGH_2.isoformat(),
                window_end_date=WINDOW_END.isoformat(),
                created_at="2026-04-24T09:01:00",
            )
            return evals_repo.insert_evaluation(conn, ev)
    finally:
        conn.close()


def _exemplars(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        return exemplars_repo.list_exemplars(conn)
    finally:
        conn.close()


def _rendered_prefill_start(client, eval_id: int) -> str:
    """The corrected-start value the review template actually renders."""
    r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    m = re.search(
        r'name="corrected_window_start_date"\s+value="([^"]*)"', r.text,
    )
    assert m is not None, "review form no longer renders the start pre-fill"
    return m.group(1)


def _assert_recovery_text(body: str, eval_id: int) -> None:
    """CHARC's Reviewer-B-gate ruling: the refusal fragment replaces the
    review form, so the message must say, IN ORDER, reload the page, choose
    pattern_present_outside_window, type the first-trough start date. It
    keeps the evaluation id and the zero score, and is ASCII-only."""
    assert body.isascii()
    assert f"evaluation {eval_id}" in body
    assert "geometric_score is 0" in body
    low = body.lower()
    i_reload = low.find("reload")
    i_decision = low.find("pattern_present_outside_window")
    i_type = low.find("first-trough start date")
    assert -1 < i_reload < i_decision < i_type, (i_reload, i_decision, i_type)


@pytest.mark.parametrize(
    "decision",
    ["confirm", "watch", "pattern_present_outside_window",
     "multiple_overlapping_patterns"],
)
def test_dbw_untouched_submit_nonzero_row_takes_trough_1(seeded_db, decision):
    """(i)+(iii): the pre-filled start (the generator start, trough 2) is NOT
    a correction; a non-zero row takes evidence trough 1."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _nonzero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        prefill = _rendered_prefill_start(client, eval_id)
        assert prefill == TROUGH_2.isoformat()
        data = {
            "decision": decision,
            "corrected_window_start_date": prefill,
            "corrected_window_end_date": WINDOW_END.isoformat(),
        }
        if decision == "multiple_overlapping_patterns":
            data["additional_pattern_classes"] = "flat_base"
        r = client.post(
            f"/patterns/{eval_id}/review", data=data,
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    rows = [x for x in _exemplars(cfg) if x.ticker == "DBW"]
    assert rows
    assert all(x.start_date == TROUGH_1.isoformat() for x in rows), [
        (x.proposed_pattern_class, x.start_date) for x in rows
    ]


def test_dbw_typed_start_that_differs_wins(seeded_db):
    """(ii): a typed start that differs from the pre-fill wins, on a
    non-zero row, over the evidence trough 1."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _nonzero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "pattern_present_outside_window",
                "corrected_window_start_date": "2026-02-20",
                "corrected_window_end_date": WINDOW_END.isoformat(),
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    rows = [x for x in _exemplars(cfg) if x.ticker == "DBW"]
    assert [x.start_date for x in rows] == ["2026-02-20"]


def test_dbw_zero_row_typed_start_is_the_recovery(seeded_db):
    """(ii) on a ZERO row: the typed start via pattern_present_outside_window
    is the honest recovery path, and it writes."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _zero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "pattern_present_outside_window",
                "corrected_window_start_date": "2026-03-02",
                "corrected_window_end_date": WINDOW_END.isoformat(),
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    rows = [x for x in _exemplars(cfg) if x.ticker == "DBW"]
    assert [x.start_date for x in rows] == ["2026-03-02"]


@pytest.mark.parametrize(
    "decision",
    ["confirm", "watch", "pattern_present_outside_window",
     "multiple_overlapping_patterns"],
)
def test_dbw_zero_row_untouched_submit_refuses_before_any_write(
    seeded_db, decision,
):
    """(iv): a zero-score row with no typed start REFUSES with a message
    naming the recovery; no exemplar row is written."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _zero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        prefill = _rendered_prefill_start(client, eval_id)
        data = {
            "decision": decision,
            "corrected_window_start_date": prefill,
            "corrected_window_end_date": WINDOW_END.isoformat(),
        }
        if decision == "multiple_overlapping_patterns":
            data["additional_pattern_classes"] = "flat_base"
        r = client.post(
            f"/patterns/{eval_id}/review", data=data,
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    _assert_recovery_text(r.text, eval_id)
    assert [x for x in _exemplars(cfg) if x.ticker == "DBW"] == []


def test_dbw_nonzero_row_unparseable_trough_1_refuses(seeded_db):
    """A non-zero row whose evidence lacks a parseable trough_1_date refuses
    the same way (no derived start exists), with no write."""
    cfg, cfg_path = seeded_db
    ev = _nonzero_evidence()
    blob = dataclasses.asdict(ev)
    blob["trough_1_date"] = "not-a-date"
    eval_id = _seed_dbw(cfg, ev, evidence_json=json.dumps(blob, default=str))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review", data={"decision": "confirm"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "reload" in r.text.lower()
    assert "first-trough start date" in r.text
    assert [x for x in _exemplars(cfg) if x.ticker == "DBW"] == []


def test_dbw_reject_on_zero_row_still_writes(seeded_db):
    """reject is UNCHANGED: rejecting must always be possible."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _zero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        prefill = _rendered_prefill_start(client, eval_id)
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "reject",
                "corrected_window_start_date": prefill,
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    rows = [x for x in _exemplars(cfg) if x.ticker == "DBW"]
    assert len(rows) == 1
    assert rows[0].final_decision == "rejected"
    assert rows[0].start_date == TROUGH_2.isoformat()


@pytest.mark.parametrize(
    ("typed_start", "typed_end"),
    [
        ("not-a-date", WINDOW_END.isoformat()),   # unparseable start
        ("2026-05-01", WINDOW_END.isoformat()),   # start after the end
        ("2026-03-02", "garbage"),                # unparseable end
    ],
)
def test_dbw_typed_window_is_validated_before_any_write(
    seeded_db, typed_start, typed_end,
):
    """Codex R1 major: a typed correction is a date, not arbitrary text. An
    unparseable start or end, or a start after the end, refuses with a
    typed 400 before any write (else it would bypass the zero-row refusal
    and seed a malformed measurement-input row)."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _zero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "pattern_present_outside_window",
                "corrected_window_start_date": typed_start,
                "corrected_window_end_date": typed_end,
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert [x for x in _exemplars(cfg) if x.ticker == "DBW"] == []


def test_dbw_alternate_spelling_of_prefill_is_not_a_correction(seeded_db):
    """Codex R1 major: equality is compared as DATES. ``20260408`` names the
    pre-filled generator start (2026-04-08), so on a zero row it is not a
    correction and the route refuses."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _zero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "pattern_present_outside_window",
                "corrected_window_start_date": "20260408",
                "corrected_window_end_date": WINDOW_END.isoformat(),
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    _assert_recovery_text(r.text, eval_id)
    assert [x for x in _exemplars(cfg) if x.ticker == "DBW"] == []


@pytest.mark.parametrize(
    "decision", ["confirm", "watch", "multiple_overlapping_patterns"],
)
def test_dbw_typed_start_ignored_outside_pattern_present_outside_window(
    seeded_db, decision,
):
    """Declared limitation 2 pinned: a differing typed start is honoured ONLY
    under pattern_present_outside_window; the other covered decisions still
    take trough 1 on a non-zero row."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _nonzero_evidence())
    app = create_app(cfg, cfg_path)
    data = {
        "decision": decision,
        "corrected_window_start_date": "2026-02-20",
        "corrected_window_end_date": WINDOW_END.isoformat(),
    }
    if decision == "multiple_overlapping_patterns":
        data["additional_pattern_classes"] = "flat_base"
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review", data=data,
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    rows = [x for x in _exemplars(cfg) if x.ticker == "DBW"]
    assert rows
    assert all(x.start_date == TROUGH_1.isoformat() for x in rows)


def test_dbw_relabel_on_zero_row_unchanged(seeded_db):
    """Declared limitation 1 pinned: relabel is outside the guard; on a zero
    row it still writes with the evaluation's window start."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _zero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "relabel", "corrected_pattern_class": "vcp"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    rows = [x for x in _exemplars(cfg) if x.ticker == "DBW"]
    assert len(rows) == 1
    assert rows[0].final_decision == "relabeled"
    assert rows[0].start_date == TROUGH_2.isoformat()
