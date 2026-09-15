"""D53.1 F1 -- the double_bottom_w review guard on an exemplar's start_date.

After D53 a DBW verdict is produced on the trough-2-anchored window, so the
generator start persisted as ``window_start_date`` is trough 2, never the
pattern start. The review route seeds ``pattern_exemplars`` (a measurement
input), so for a DBW evaluation and every decision whose exemplar is READ as
a pattern instance (confirm, watch, pattern_present_outside_window,
multiple_overlapping_patterns) CHARC's ruling orders the route:

  (i)   a submitted corrected start EQUAL to ``window_start_date`` is not a
        correction (rule (i)'s comparison target, unwidened by D56 C3 --
        the form's actual pre-fill differs from ``window_start_date`` for
        a parseable non-zero row post-D56, see
        test_dbw_c3_prefill_differs_from_pre_c3_on_the_parseable_nonzero_row);
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
from swing.web.routes.patterns import _dbw_recovery_text

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
    """D56 F-B amendment: the RELOAD step is dropped -- the D56 E1 error
    region means the refusal fragment no longer replaces the review form,
    so "reload" is no longer part of the contract. The message must say,
    IN ORDER, choose pattern_present_outside_window, type the first-trough
    start date. It keeps the evaluation id and the zero score, is
    ASCII-only, and does NOT mention reload."""
    assert body.isascii()
    assert f"evaluation {eval_id}" in body
    assert "geometric_score is 0" in body
    low = body.lower()
    assert "reload" not in low
    i_decision = low.find("pattern_present_outside_window")
    i_type = low.find("first-trough start date")
    assert -1 < i_decision < i_type, (i_decision, i_type)


@pytest.mark.parametrize(
    "decision",
    ["confirm", "watch", "pattern_present_outside_window",
     "multiple_overlapping_patterns"],
)
def test_dbw_untouched_submit_nonzero_row_takes_trough_1(seeded_db, decision):
    """(i)+(iii): a non-zero row's untouched submit takes evidence trough 1.

    D56 C3 amendment: pre-D56 the review form pre-filled the generator
    anchor (trough 2 / window_start_date) on every DBW row, so this test's
    ``prefill == TROUGH_2`` line pinned THAT. Post-D56 the form pre-fills
    trough 1 for a parseable non-zero row (the ``dbw_corrected_start_date_
    prefill`` helper); the untouched-submit path still reaches rule (ii)
    (the pre-fill differs from ``window_start_date``, rule (i)'s unwidened
    comparison target) and lands on the SAME trough-1 answer -- the
    assertion is amended to pin the NEW pre-fill value, and the outcome
    assertion below (stored start == trough 1) is UNCHANGED."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _nonzero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        prefill = _rendered_prefill_start(client, eval_id)
        assert prefill == TROUGH_1.isoformat()
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
    the same way (no derived start exists), with no write.

    D56 F-B amendment: the "reload" assertion is dropped -- the D56 E1
    error region means the refusal fragment no longer replaces the review
    form, so step (1) RELOAD is gone from the text (see
    test_dbw_refusal_text_has_no_reload_step_and_steps_are_contiguous)."""
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
    assert "reload" not in r.text.lower()
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


# ---------------------------------------------------------------------------
# D56 C3/E3 -- the trough-1 pre-fill helper. Rule (i) keeps comparing to
# window_start_date (CHARC F-C, unwidened); ONE helper feeds both the form's
# pre-fill and step (iii)'s extraction, so the pre-fill and the stored start
# cannot diverge, on all three DBW row kinds.
# ---------------------------------------------------------------------------


def test_dbw_c3_prefill_differs_from_pre_c3_on_the_parseable_nonzero_row(
    seeded_db,
):
    """T3 arithmetic: pre-C3 the form pre-filled window_start_date
    (TROUGH_2, the generator/trough-2 anchor) on EVERY DBW row. Post-C3 a
    parseable non-zero row pre-fills trough 1 instead -- the two dates are
    different constants in this fixture (2026-03-02 vs 2026-04-08), so this
    assertion distinguishes pre- from post-fix."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _nonzero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        prefill = _rendered_prefill_start(client, eval_id)
    assert prefill == TROUGH_1.isoformat()
    assert prefill != TROUGH_2.isoformat()


def test_dbw_c3_untouched_submit_same_outcome_all_three_row_kinds(seeded_db):
    """T3 (F-C pin): under pattern_present_outside_window, an untouched
    submit -- corrected_window_start_date set to whatever the GET-rendered
    form ACTUALLY shows -- stores (or refuses on) the SAME outcome C3 was
    ruled to preserve, on all three DBW row kinds. Rule (i)'s comparison
    target (window_start_date, literal) never moves, so:

      (a) parseable non-zero: pre-fill is now trough 1, which differs from
          window_start_date -> rule (ii) takes the typed value -> stores
          trough 1 -- the SAME answer step (iii) gives directly, so the
          form-driven path and the direct-computation path agree.
      (b) unparseable non-zero: pre-fill falls back to window_start_date
          (C3's rule 2) -> rule (i) calls it "not a correction" -> falls to
          (iii) -> no parseable trough 1 -> refuses, same as pre-C3 (which
          always fell back to window_start_date for every row kind).
      (c) zero score: pre-fill stays window_start_date (C3 never pre-fills
          a zero row) -> rule (i) calls it "not a correction" -> refuses on
          the zero-score branch, same as pre-C3.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    # (a) parseable non-zero -> stores trough 1.
    eval_id_a = _seed_dbw(cfg, _nonzero_evidence())
    with TestClient(app) as client:
        prefill_a = _rendered_prefill_start(client, eval_id_a)
    assert prefill_a == TROUGH_1.isoformat()
    before_a = len(_exemplars(cfg))
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id_a}/review",
            data={
                "decision": "pattern_present_outside_window",
                "corrected_window_start_date": prefill_a,
                "corrected_window_end_date": WINDOW_END.isoformat(),
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    after_a = _exemplars(cfg)
    assert len(after_a) == before_a + 1
    assert after_a[-1].start_date == TROUGH_1.isoformat()

    # (b) unparseable non-zero -> refuses, no write.
    ev_b = _nonzero_evidence()
    blob_b = dataclasses.asdict(ev_b)
    blob_b["trough_1_date"] = "not-a-date"
    eval_id_b = _seed_dbw(
        cfg, ev_b, evidence_json=json.dumps(blob_b, default=str),
    )
    with TestClient(app) as client:
        prefill_b = _rendered_prefill_start(client, eval_id_b)
    assert prefill_b == TROUGH_2.isoformat()
    before_b = len(_exemplars(cfg))
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id_b}/review",
            data={
                "decision": "pattern_present_outside_window",
                "corrected_window_start_date": prefill_b,
                "corrected_window_end_date": WINDOW_END.isoformat(),
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert len(_exemplars(cfg)) == before_b

    # (c) zero score -> refuses, no write.
    eval_id_c = _seed_dbw(cfg, _zero_evidence())
    with TestClient(app) as client:
        prefill_c = _rendered_prefill_start(client, eval_id_c)
    assert prefill_c == TROUGH_2.isoformat()
    before_c = len(_exemplars(cfg))
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id_c}/review",
            data={
                "decision": "pattern_present_outside_window",
                "corrected_window_start_date": prefill_c,
                "corrected_window_end_date": WINDOW_END.isoformat(),
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert len(_exemplars(cfg)) == before_c


# ---------------------------------------------------------------------------
# D56 E5/F-B -- the refusal text: drop the RELOAD step (false once E1 lands
# -- the error region means the review form is no longer replaced), and
# derive the named pre-fill from the SAME E3 helper the form uses, never
# from evaluation.window_start_date directly.
# ---------------------------------------------------------------------------


def test_dbw_refusal_text_has_no_reload_step_and_steps_are_contiguous(
    seeded_db,
):
    """T5: once E1 lands the refusal fragment no longer replaces the review
    form (it swaps into the sibling error region), so step (1) RELOAD is
    false and dropped; the remaining two steps renumber to (1) and (2)."""
    cfg, cfg_path = seeded_db
    eval_id = _seed_dbw(cfg, _zero_evidence())
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review", data={"decision": "confirm"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    body = r.text
    assert "reload" not in body.lower()
    assert "(1)" in body
    assert "(2)" in body
    assert "(3)" not in body


def test_dbw_refusal_text_prefill_matches_form_rendered_prefill(seeded_db):
    """T4 (F-B pin): the refusal's named pre-fill X equals the value the
    form's corrected_window_start_date input ACTUALLY renders, read BOTH
    from real responses (GET the form; POST the refusal) -- on ALL THREE
    DBW row kinds (B-1, Reviewer B minor).

    The parseable-non-zero kind never reaches the refusal path THROUGH THE
    ROUTE (rule (iii) always resolves it directly, so an untouched submit
    of that row kind is a 204, not a 400 -- T3 already pins that). The
    route calls ``_dbw_recovery_text`` from exactly two sites in
    ``_dbw_exemplar_window`` (no parseable trough 1; zero score), and a
    malformed end date or a start after the end refuses through
    ``_dbw_refuse`` WITHOUT it, so this row kind cannot reach the text today.
    The pin is on the function's own contract, so a future caller cannot
    make it name a date the form does not show: call it on the same
    evaluation object the form rendered, and
    assert the named date matches. Without this case, reverting
    ``_dbw_recovery_text``'s pre-fill to ``evaluation.window_start_date``
    directly (the pre-D56-E5 code) stays GREEN on this test -- both
    row kinds below coincide with ``window_start_date`` pre- and post-fix,
    so only the parseable-non-zero case (whose pre-fill DIFFERS from
    ``window_start_date``) can catch a regression of the fix itself."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    # Unparseable non-zero.
    ev = _nonzero_evidence()
    blob = dataclasses.asdict(ev)
    blob["trough_1_date"] = "not-a-date"
    eval_id = _seed_dbw(cfg, ev, evidence_json=json.dumps(blob, default=str))
    with TestClient(app) as client:
        prefill = _rendered_prefill_start(client, eval_id)
        r = client.post(
            f"/patterns/{eval_id}/review", data={"decision": "confirm"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert prefill == TROUGH_2.isoformat()
    assert f"pre-filled {prefill}" in r.text

    # Zero score.
    eval_id2 = _seed_dbw(cfg, _zero_evidence())
    with TestClient(app) as client:
        prefill2 = _rendered_prefill_start(client, eval_id2)
        r2 = client.post(
            f"/patterns/{eval_id2}/review", data={"decision": "watch"},
            headers={"HX-Request": "true"},
        )
    assert r2.status_code == 400
    assert prefill2 == TROUGH_2.isoformat()
    assert f"pre-filled {prefill2}" in r2.text

    # Parseable non-zero (B-1): the route never refuses this row kind on an
    # untouched submit, so call _dbw_recovery_text directly on the same
    # evaluation object the form rendered, and pin its named pre-fill
    # against the form's ACTUAL rendered value (trough 1, per T3) -- not
    # window_start_date (trough 2).
    eval_id3 = _seed_dbw(cfg, _nonzero_evidence())
    with TestClient(app) as client:
        prefill3 = _rendered_prefill_start(client, eval_id3)
    assert prefill3 == TROUGH_1.isoformat()
    conn = connect(cfg.paths.db_path)
    try:
        evaluation3 = evals_repo.get_evaluation_by_id(conn, eval_id3)
    finally:
        conn.close()
    text3 = _dbw_recovery_text(evaluation3, "any reason")
    assert f"pre-filled {prefill3}" in text3
