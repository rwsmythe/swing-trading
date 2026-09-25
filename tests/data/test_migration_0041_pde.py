"""22-I T4 -- `pattern_detection_events`: the (a) triple whose `no_update` is
the a17 twin (plan sections 1.2, 1.5, 4.3; CHARC a17 + the parent-gone
clause @ 7e0463ed / 732c5c21).

`trg_pde_no_update` admits exactly ONE kind of UPDATE: `chart_render_id` or
`pipeline_run_id` going value -> NULL while its parent row is GONE (the
engine's ON DELETE SET NULL action), every other column unchanged. Anything
else -- a payload column, an FK NULLed with its parent present, an FK NULLed
together with another column, NULL -> value, a no-op -- aborts.

    chart_render_id  -> chart_renders   REACHABLE (the prune + refresh deletes)
    pipeline_run_id  -> pipeline_runs   DELETABLE-NO-PRODUCTION-DELETER
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.models import ChartRender
from tests._22b_fixtures import insert_row
from tests.data._22i_seed import TS, migrated, open_plain, outcome

NO_UPDATE = "TRIGGER:trg_pde_no_update"
PAIR = pytest.mark.parametrize("version", [40, 41])


def _world(tmp_path: Path, version: int):
    c = migrated(tmp_path, version, world=True)
    # detection 2 hangs off the BARE pipeline run 2 (no pattern_evaluations /
    # chart_renders children) with NO chart render: the P2 and P5 subjects.
    insert_row(c, "pattern_detection_events", dict(
        detection_id=2, ticker="BBB", detection_date="2026-08-10",
        data_asof_date="2026-08-07", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=0.7, detector_version="v1",
        finviz_screen_state=None, source="pipeline",
        per_pattern_metadata_json="{}", pipeline_run_id=2, chart_render_id=None,
        created_at=TS))
    return c


def _pde(c, detection_id: int) -> tuple:
    return c.execute("SELECT chart_render_id, pipeline_run_id FROM "
                     "pattern_detection_events WHERE detection_id = ?",
                     (detection_id,)).fetchone()


@PAIR
def test_p1_the_production_chart_prune_is_admitted(tmp_path: Path, version: int) -> None:
    """P1: `prune_chart_renders_older_than` (FKs ON) deletes the render; the
    SET NULL action's UPDATE on detection 1 is admitted (the a17 control)."""
    from swing.diagnostics.prune_chart_cache import prune_chart_renders_older_than

    c = _world(tmp_path, version)
    try:
        verdict, seen = outcome(
            c, lambda k: prune_chart_renders_older_than(k, older_than_days=0),
            post=lambda k: (k.execute("SELECT COUNT(*) FROM chart_renders").fetchone()[0],
                            _pde(k, 1)))
    finally:
        c.close()
    assert verdict == "OK"
    assert seen == (0, (None, 1))


@PAIR
def test_p1b_refresh_chart_render_delete_path_is_admitted(tmp_path: Path,
                                                         version: int) -> None:
    from swing.data.repos.chart_renders import refresh_chart_render

    c = _world(tmp_path, version)
    try:
        render = ChartRender(id=None, ticker="AMN", surface="watchlist_row",
                             chart_svg_bytes=b"<svg2/>", source_data_hash="h2",
                             rendered_at=TS, data_asof_date="2026-08-07",
                             pipeline_run_id=1)
        verdict, seen = outcome(
            c, lambda k: refresh_chart_render(k, render), post=lambda k: _pde(k, 1))
    finally:
        c.close()
    assert (verdict, seen) == ("OK", (None, 1))


@PAIR
def test_p2_a_pipeline_run_delete_nulls_the_run_link(tmp_path: Path, version: int) -> None:
    """P2: DELETABLE-NO-PRODUCTION-DELETER -- a PROBE delete of the bare run 2
    (no production deleter exists; `DELETE FROM pipeline_runs` greps empty)."""
    c = _world(tmp_path, version)
    try:
        verdict, seen = outcome(c, "DELETE FROM pipeline_runs WHERE id = 2",
                                post=lambda k: _pde(k, 2))
    finally:
        c.close()
    assert (verdict, seen) == ("OK", (None, None))


def _exposed_or_refused(verdict: str, version: int) -> None:
    if version == 40:
        assert verdict == "OK", verdict
    else:
        assert verdict == NO_UPDATE, verdict


@PAIR
@pytest.mark.parametrize("col", ["chart_render_id", "pipeline_run_id"])
def test_p3_fk_to_null_with_the_parent_present_aborts(tmp_path: Path, col: str,
                                                      version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(
            c, f"UPDATE pattern_detection_events SET {col} = NULL WHERE detection_id = 1")
    finally:
        c.close()
    _exposed_or_refused(verdict, version)


@PAIR
def test_p4_fk_to_null_together_with_a_payload_column_aborts(tmp_path: Path,
                                                             version: int) -> None:
    """The parent is GONE (deleted with FKs OFF, so no cascade ran): the FK half
    alone would be admitted (the control), but WITH `composite_score` it aborts."""
    path = tmp_path / "p4"
    path.mkdir()
    c0 = _world(path, version)
    db = Path(c0.execute("PRAGMA database_list").fetchone()[2])
    c0.close()
    c = open_plain(db, fk=False)
    try:
        gone = [("DELETE FROM chart_renders WHERE id = 1",)]
        control = outcome(c, "UPDATE pattern_detection_events SET chart_render_id = NULL "
                             "WHERE detection_id = 1", setup=gone)
        verdict = outcome(c, "UPDATE pattern_detection_events SET chart_render_id = NULL, "
                             "composite_score = 0.1 WHERE detection_id = 1", setup=gone)
    finally:
        c.close()
    assert control == "OK"
    _exposed_or_refused(verdict, version)


@PAIR
def test_p5_null_to_value_aborts(tmp_path: Path, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, "UPDATE pattern_detection_events SET chart_render_id = 1 "
                             "WHERE detection_id = 2")
    finally:
        c.close()
    _exposed_or_refused(verdict, version)


@PAIR
def test_p6_a_payload_column_alone_aborts(tmp_path: Path, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, "UPDATE pattern_detection_events SET composite_score = 0.2 "
                             "WHERE detection_id = 1")
    finally:
        c.close()
    _exposed_or_refused(verdict, version)


@PAIR
def test_p7_a_no_op_update_aborts(tmp_path: Path, version: int) -> None:
    """The third conjunct (an FK must actually change) makes a no-op abort --
    the v40 `trg_eia_no_update` shape."""
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, "UPDATE pattern_detection_events SET ticker = ticker "
                             "WHERE detection_id = 1")
    finally:
        c.close()
    _exposed_or_refused(verdict, version)


@pytest.mark.parametrize("col", [
    "detection_id", "ticker", "detection_date", "data_asof_date", "pattern_class",
    "structural_anchors_json", "composite_score", "detector_version",
    "finviz_screen_state", "source", "per_pattern_metadata_json", "created_at"])
def test_every_immutable_column_aborts(tmp_path: Path, col: str) -> None:
    from tests.data._22i_seed import different_value, row_of

    c = _world(tmp_path, 41)
    try:
        v = different_value(c, "pattern_detection_events", col,
                            row_of(c, "pattern_detection_events")[col])
        verdict = outcome(c, f"UPDATE pattern_detection_events SET {col} = ? "
                             "WHERE detection_id = 1", (v,))
    finally:
        c.close()
    assert verdict == NO_UPDATE
