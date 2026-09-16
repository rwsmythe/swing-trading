"""Phase 22 D56 -- E1/E2: the pattern-review form and the exemplars page's
four inline forms get a sibling error region via ``hx-target``.

The PRODUCTION mechanism this fixes is status-agnostic by construction:
``hx-target`` does not inspect the response status, so BEFORE this fix any
error response on these two routes -- 400, 404, 422, or 500 -- replaced
the form's controls with the error fragment (``app.py``'s dispatch is one
shared code path per status FAMILY, not per code). THIS FILE's own tests
exercise the two statuses these two routes actually raise via
``HTTPException`` -- 400 (decision/action validation) and 404 (missing
candidate/exemplar) -- read straight from real responses; they do not
independently re-prove the 422 (``RequestValidationError``, a DIFFERENT
FastAPI exception handler, not exercised by any input these two routes'
tests construct) or 500 path. A 500 IS reachable on the exemplars route
(the promote_to_gold corrupt-``labeler_evidence_json`` raise,
``routes/patterns.py:264,273``) but grepping ``tests/`` for that raise's
message text found NO existing test exercising it -- an open gap, not a
covered one; not this file's scope to close.

CHARC's D56 round-0 ruling (docs/phase22-arc-d56-ledger.md) F-A: the
exemplars page gets exactly ONE page-level error region (never per-row --
that reintroduces the ``<tr>``-fragment-wrap gotcha and the colspan path
for no gain), and nothing else on that page changes.

Seeding here is LOCAL (not cross-module fixture reuse): the two other
pattern-route test modules -- found by grepping
``tests/web/test_routes/test_patterns_*.py`` for ``@pytest.fixture`` --
are ``test_patterns_review.py`` (``seeded_db_with_evaluation``, a vcp
candidate) and ``test_patterns_exemplars.py`` (``seeded_db_with_exemplars``,
2 silver + 1 gold row); importing a pytest fixture across modules and also
using it as a same-named test parameter false-positives ruff F811
(verified), so the minimal seeding shapes are reproduced here instead.
"""
from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import PatternEvaluation, PatternExemplar
from swing.data.repos import pattern_evaluations as evals_repo
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.web.app import create_app


def _seed_pipeline_run(conn) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, finished_ts, trigger, data_asof_date,
             action_session_date, state, lease_token)
        VALUES ('2026-05-20T09:00:00', '2026-05-20T09:05:00',
                'manual', '2026-05-19', '2026-05-20',
                'complete', 't-x')
        """
    )
    return int(cur.lastrowid)


@pytest.fixture
def review_eval_id(seeded_db):
    """Mirrors test_patterns_review.py's seeded_db_with_evaluation shape
    (a vcp pattern_evaluations row) -- see module docstring for the search
    that found it."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            ev = PatternEvaluation(
                id=None, pipeline_run_id=run_id, ticker="ABC",
                pattern_class="vcp", detector_version="v1",
                geometric_score=0.55,
                geometric_score_json=json.dumps({"criteria": []}),
                composite_score=0.62,
                structural_evidence_json=json.dumps({
                    "criteria_pass": {}, "pivot_price": 120.5,
                }),
                feature_distribution_log_json="{}",
                window_start_date="2026-04-01",
                window_end_date="2026-05-15",
                created_at="2026-05-20T09:01:00",
            )
            eval_id = evals_repo.insert_evaluation(conn, ev)
    finally:
        conn.close()
    return cfg, cfg_path, eval_id


@pytest.fixture
def exemplars_two_silver(seeded_db):
    """Mirrors test_patterns_exemplars.py's seeded_db_with_exemplars shape
    (2 silver + 1 gold row) -- see module docstring for the search that
    found it."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            exemplars_repo.insert_exemplar(conn, PatternExemplar(
                id=None, ticker="ABC", timeframe="daily",
                start_date="2024-01-01", end_date="2024-02-01",
                proposed_pattern_class="vcp", final_decision="confirmed",
                label_source="claude_silver", structural_evidence_json="{}",
                created_at="2024-02-02T00:00:00.000",
                created_by="claude_dispatch", labeler_evidence_json="{}",
                geometric_score_json=None,
            ))
            exemplars_repo.insert_exemplar(conn, PatternExemplar(
                id=None, ticker="XYZ", timeframe="daily",
                start_date="2024-01-01", end_date="2024-02-01",
                proposed_pattern_class="flat_base",
                final_decision="confirmed", label_source="claude_silver",
                structural_evidence_json="{}",
                created_at="2024-02-02T00:00:00.000",
                created_by="claude_dispatch", labeler_evidence_json="{}",
                geometric_score_json=None,
            ))
            exemplars_repo.insert_exemplar(conn, PatternExemplar(
                id=None, ticker="MMM", timeframe="daily",
                start_date="2024-01-01", end_date="2024-02-01",
                proposed_pattern_class="cup_with_handle",
                final_decision="confirmed", label_source="curated_gold",
                structural_evidence_json="{}",
                created_at="2024-02-02T00:00:00.000",
                created_by="operator", geometric_score_json="{\"score\": 0.95}",
                labeler_evidence_json="{}",
                gold_validated_at="2024-02-03T00:00:00.000",
            ))
    finally:
        conn.close()
    return cfg, cfg_path


# ---------------------------------------------------------------------------
# T1 -- review form error region.
# ---------------------------------------------------------------------------


def test_review_form_carries_hx_target_to_a_sibling_error_region_outside_form(
    review_eval_id,
):
    cfg, cfg_path, eval_id = review_eval_id
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    body = r.text

    # The form carries hx-target naming the region.
    m = re.search(r'<form\b[^>]*\bhx-target="#([\w-]+)"', body, re.S)
    assert m is not None, "review <form> does not carry hx-target"
    region_id = m.group(1)

    # The region id exists EXACTLY ONCE in the whole page.
    assert body.count(f'id="{region_id}"') == 1

    # The region is a SIBLING -- outside the <form>...</form> block, not
    # inside it.
    form_match = re.search(r"<form\b.*?</form>", body, re.S)
    assert form_match is not None
    assert f'id="{region_id}"' not in form_match.group(0)


def test_review_form_success_path_unaffected_by_the_error_region(
    review_eval_id,
):
    cfg, cfg_path, eval_id = review_eval_id
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "watch"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/patterns/queue"


# ---------------------------------------------------------------------------
# T2 -- exemplars page error region (bounded: region + hx-target ONLY).
# ---------------------------------------------------------------------------


def test_exemplars_page_has_exactly_one_page_level_error_region(
    exemplars_two_silver,
):
    cfg, cfg_path = exemplars_two_silver
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    body = r.text

    # Locate the region by its hx-target reference (robust to whichever
    # empty-tag element shape is used).
    target_match = re.search(r'hx-target="#([\w-]+)"', body)
    assert target_match is not None, (
        "no inline exemplars form carries hx-target"
    )
    region_id = target_match.group(1)

    # Exactly one region with this id -- never per-row.
    assert body.count(f'id="{region_id}"') == 1

    # The region sits BEFORE any table -- never inside a <table>/<tr>.
    region_idx = body.index(f'id="{region_id}"')
    table_idx = body.index("<table")
    assert region_idx < table_idx, (
        "error region must be page-level, not nested inside a table"
    )


def test_exemplars_all_four_inline_forms_per_row_target_the_same_region(
    exemplars_two_silver,
):
    cfg, cfg_path = exemplars_two_silver
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    body = r.text

    target_match = re.search(r'hx-target="#([\w-]+)"', body)
    assert target_match is not None
    region_id = target_match.group(1)

    # exemplars_two_silver seeds exactly 2 silver rows (ABC vcp, XYZ
    # flat_base); each row renders 4 inline forms (promote_to_gold, watch,
    # reject, relabel) -- 8 total hx-target attributes.
    expected = 4 * 2
    got = body.count(f'hx-target="#{region_id}"')
    assert got == expected, (
        f"expected {expected} hx-target attributes (4 forms x 2 silver "
        f"rows); got {got}"
    )


def test_exemplars_page_otherwise_renders_the_same_rows_and_controls(
    exemplars_two_silver,
):
    """Discriminate against an over-wide change: CHARC's F-A bound is the
    region + hx-target ONLY -- every row/action-button that rendered before
    D56 still renders, unchanged."""
    cfg, cfg_path = exemplars_two_silver
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    body = r.text

    assert 'data-exemplar-id="' in body
    for ticker in ("ABC", "XYZ", "MMM"):
        assert ticker in body
    for action in ("promote_to_gold", "watch", "reject", "relabel"):
        assert f'data-action="{action}"' in body
    # Two silver rows -> two relabel <select> dropdowns.
    assert body.count("(pick relabel class)") == 2


def test_exemplars_success_path_unaffected_by_the_error_region(
    exemplars_two_silver,
):
    cfg, cfg_path = exemplars_two_silver
    app = create_app(cfg, cfg_path)
    conn = connect(cfg.paths.db_path)
    silver_id = exemplars_repo.list_exemplars(conn)[0].id
    conn.close()
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "watch"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/patterns/exemplars"


# ---------------------------------------------------------------------------
# F-D companion (TestClient side): an error response on both routes still
# lands the http_error_fragment's <div> (never a bare <tr>) so the swap into
# the sibling region is HTML5-safe. Codex R1 minor: send the ACTUAL
# HX-Target header a browser would send (the resolved region id) -- the
# app's _is_row_swap_target dispatch reads that header, not just HX-Request
# -- and cover both the 400 (validation-shaped HTTPException) and 404
# (StarletteHTTPException) paths, not 400 alone.
# ---------------------------------------------------------------------------


def _region_id(body: str) -> str:
    m = re.search(r'hx-target="#([\w-]+)"', body)
    assert m is not None
    return m.group(1)


def test_review_error_response_body_is_a_div_not_a_bare_row(review_eval_id):
    cfg, cfg_path, eval_id = review_eval_id
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        get_body = client.get(f"/patterns/{eval_id}/review").text
        region = _region_id(get_body)

        r400 = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "bogus"},
            headers={"HX-Request": "true", "HX-Target": region},
        )
        assert r400.status_code == 400
        assert r400.text.strip().startswith("<div")

        r404 = client.post(
            "/patterns/999999/review",
            data={"decision": "watch"},
            headers={"HX-Request": "true", "HX-Target": region},
        )
        assert r404.status_code == 404
        assert r404.text.strip().startswith("<div")


def test_exemplars_error_response_body_is_a_div_not_a_bare_row(
    exemplars_two_silver,
):
    cfg, cfg_path = exemplars_two_silver
    app = create_app(cfg, cfg_path)
    conn = connect(cfg.paths.db_path)
    silver_id = exemplars_repo.list_exemplars(conn)[0].id
    conn.close()
    with TestClient(app) as client:
        get_body = client.get("/patterns/exemplars").text
        region = _region_id(get_body)

        r400 = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "bogus_action_not_allowed"},
            headers={"HX-Request": "true", "HX-Target": region},
        )
        assert r400.status_code == 400
        assert r400.text.strip().startswith("<div")

        r404 = client.post(
            "/patterns/exemplars/999999/action",
            data={"action": "watch"},
            headers={"HX-Request": "true", "HX-Target": region},
        )
        assert r404.status_code == 404
        assert r404.text.strip().startswith("<div")
