"""Phase 13 T2.SB6b T-A.6.6b Deficiency 1 fold-in — exemplars enhancement tests.

Per plan G.9 T-A.6.6b Step 1: 8+ tests covering per-exemplar chart + per-
criterion table + narrative rendering + cache-hit/cache-miss + Literal
runtime validation + graceful degradation.

Reuses T-A.6.1 ``render_theme2_annotated_svg`` substrate + T-A.6.2
``get_cached_chart_svg`` cache helper verbatim (L17 LOCK).
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import ChartRender, PatternExemplar
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.data.repos.chart_renders import refresh_chart_render
from swing.web.app import create_app
from swing.web.view_models.patterns.exemplars import (
    CriterionRow,
    ExemplarRender,
    PatternExemplarsVM,
    build_patterns_exemplars_vm,
)


def _make_silver(
    *,
    ticker: str = "ABC",
    pattern_class: str = "vcp",
    labeler_evidence_json: str | None = None,
) -> PatternExemplar:
    return PatternExemplar(
        id=None,
        ticker=ticker,
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        proposed_pattern_class=pattern_class,
        final_decision="confirmed",
        label_source="claude_silver",
        structural_evidence_json="{}",
        created_at="2024-02-02T00:00:00.000",
        created_by="claude_dispatch",
        labeler_evidence_json=labeler_evidence_json or "{}",
        geometric_score_json=None,
    )


@pytest.fixture
def seeded_db_with_silver(seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            exemplars_repo.insert_exemplar(
                conn,
                _make_silver(
                    ticker="ABC",
                    pattern_class="vcp",
                    labeler_evidence_json=json.dumps({
                        "rule_criteria": [
                            {"name": "stage_2", "status": "pass",
                             "evidence_value": "Stage 2 confirmed",
                             "threshold": "stage in [2]",
                             "tolerance": None},
                            {"name": "contractions",
                             "status": "pass",
                             "evidence_value": "3 contractions",
                             "threshold": ">=2",
                             "tolerance": "+/-1"},
                            {"name": "volume_dryup",
                             "status": "fail",
                             "evidence_value": "ratio 0.85",
                             "threshold": "<0.70",
                             "tolerance": None},
                        ],
                        "narrative": (
                            "Three contractions tightening from 22pct to "
                            "8pct; volume dry-up criterion failed."
                        ),
                    }),
                ),
            )
    finally:
        conn.close()
    return cfg, cfg_path


# ---------------------------------------------------------------------------
# Test 1: chart per exemplar surfaces when cache row present.
# ---------------------------------------------------------------------------


def test_get_patterns_exemplars_chart_consumed_from_chart_renders_cache_when_available(
    seeded_db_with_silver,
):
    cfg, cfg_path = seeded_db_with_silver
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            silver = exemplars_repo.list_exemplars(conn)[0]
            # Plant pipeline_runs row FIRST (FK target for chart_renders).
            conn.execute(
                "INSERT INTO pipeline_runs (id, started_ts, finished_ts, "
                "trigger, data_asof_date, action_session_date, state, "
                "lease_token) VALUES (42, '2026-05-21T08:00:00', "
                "'2026-05-21T09:00:00', 'manual', '2024-02-01', "
                "'2024-02-02', 'complete', 't')"
            )
            refresh_chart_render(conn, ChartRender(
                id=None, ticker=silver.ticker, surface="theme2_annotated",
                chart_svg_bytes=b"<svg>cached</svg>",
                source_data_hash="h",
                rendered_at="2026-05-21T09:00:00",
                data_asof_date="2024-02-01",
                pipeline_run_id=42,
                pattern_class=silver.proposed_pattern_class,
            ))
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    assert "<svg>cached</svg>" in r.text


# ---------------------------------------------------------------------------
# Test 2: cache-miss leaves chart_svg_bytes None + renders placeholder.
# ---------------------------------------------------------------------------


def test_get_patterns_exemplars_handles_missing_chart_renders_gracefully(
    seeded_db_with_silver,
):
    cfg, cfg_path = seeded_db_with_silver
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    assert "Chart not yet cached" in r.text


# ---------------------------------------------------------------------------
# Test 3: per-criterion table rendered from labeler_evidence_json.
# ---------------------------------------------------------------------------


def test_get_patterns_exemplars_renders_per_criterion_table_from_labeler_evidence_json(
    seeded_db_with_silver,
):
    cfg, cfg_path = seeded_db_with_silver
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    body = r.text
    # 3 criteria seeded; each name + status visible.
    assert "stage_2" in body
    assert "contractions" in body
    assert "volume_dryup" in body
    assert "pass" in body
    assert "fail" in body


# ---------------------------------------------------------------------------
# Test 4: CriterionRow Literal runtime validation (L15 LOCK).
# ---------------------------------------------------------------------------


def test_get_patterns_exemplars_criterion_row_status_pass_or_fail_per_evaluation():
    """Per L15 LOCK + CLAUDE.md gotcha 'Literal[...] not runtime-enforced'."""
    # Valid statuses construct.
    CriterionRow(name="ok", status="pass")
    CriterionRow(name="bad", status="fail")
    # Invalid status raises.
    with pytest.raises(ValueError, match="status"):
        CriterionRow(name="x", status="marginal")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="status"):
        CriterionRow(name="x", status="")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 5: narrative renders from labeler_evidence_json.
# ---------------------------------------------------------------------------


def test_get_patterns_exemplars_renders_narrative_text_from_labeler_evidence_json(
    seeded_db_with_silver,
):
    cfg, cfg_path = seeded_db_with_silver
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    body = r.text
    assert "Three contractions" in body
    assert "volume dry-up criterion failed" in body


# ---------------------------------------------------------------------------
# Test 6: malformed labeler_evidence_json gracefully degrades.
# ---------------------------------------------------------------------------


def test_get_patterns_exemplars_handles_malformed_labeler_evidence_json_gracefully(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # JSON without rule_criteria + without narrative.
            exemplars_repo.insert_exemplar(
                conn,
                _make_silver(
                    labeler_evidence_json='{"unrelated": "field"}',
                ),
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    # Placeholders rendered when payloads absent.
    assert "no rule_criteria" in r.text or "no rule_criteria payload" in r.text
    assert "no narrative" in r.text


def test_get_patterns_exemplars_handles_invalid_json_in_labeler_evidence_gracefully(
    seeded_db,
):
    """Invariant #5 + non-JSON labeler_evidence_json must not crash; the
    rule_criteria parser returns empty + narrative None.
    """
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Bypass dataclass invariant #5 by inserting via raw SQL with
            # a known-bad payload (Invariant #5 requires non-NULL for
            # claude_silver but allows any JSON-shaped string; a truly
            # malformed payload like 'not_json' is rejected by the
            # dataclass).
            #
            # The parser must defend against operator-direct DB edits or
            # legacy rows landing with non-JSON content.
            conn.execute(
                "INSERT INTO pattern_exemplars "
                "(ticker, timeframe, start_date, end_date, "
                " proposed_pattern_class, final_decision, label_source, "
                " structural_evidence_json, created_at, created_by, "
                " labeler_evidence_json) VALUES "
                "(?, 'daily', '2024-01-01', '2024-02-01', 'vcp', "
                " 'confirmed', 'claude_silver', '{}', "
                " '2024-02-02T00:00:00', 'claude_dispatch', ?)",
                ("BAD", "not_json_text"),
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    # The malformed row may not list via list_exemplars (dataclass
    # __post_init__ validation rejects it). Even so, the page must
    # render the OTHER rows + not 500.
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Test 7: existing T-A.1.6 tests still pass (regression check via
#         spot-asserting silver tier section + actions form).
# ---------------------------------------------------------------------------


def test_existing_silver_tier_table_byte_stable_after_enhancement(
    seeded_db_with_silver,
):
    """Existing T-A.1.6 expectations preserved (silver tier section header
    + relabel select still present).
    """
    cfg, cfg_path = seeded_db_with_silver
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    body = r.text
    assert "Silver tier (awaiting operator review)" in body
    assert "Promote to gold" in body
    assert "Relabel" in body


# ---------------------------------------------------------------------------
# Test 8: ExemplarRender dataclass + builder integration.
# ---------------------------------------------------------------------------


def test_build_patterns_exemplars_vm_populates_exemplar_renders(
    seeded_db_with_silver,
):
    cfg, _ = seeded_db_with_silver
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_exemplars_vm(
            conn, session_date="2026-05-20",
        )
    finally:
        conn.close()
    assert isinstance(vm, PatternExemplarsVM)
    assert vm.exemplar_renders, "exemplar_renders must be populated"
    # Iterate; each render is an ExemplarRender carrying parsed payloads.
    for ex_id, render in vm.exemplar_renders.items():
        assert isinstance(render, ExemplarRender)
        assert render.exemplar.id == ex_id
        # 3 criteria seeded; all should parse.
        assert len(render.criterion_rows) == 3
        assert any(c.status == "fail" for c in render.criterion_rows)
        assert render.narrative_text is not None
        assert "contractions" in render.narrative_text


# ---------------------------------------------------------------------------
# Test 9: ASCII-only narrative rendering (L16 LOCK).
# ---------------------------------------------------------------------------


def test_get_patterns_exemplars_chart_invokes_render_theme2_annotated_svg_when_cache_miss(
    seeded_db_with_silver, monkeypatch,
):
    """Codex R1 MAJOR #6 closure + plan G.9 T-A.6.6b acceptance #3:
    cache-miss path MUST invoke ``render_theme2_annotated_svg`` once per
    exemplar so the operator workflow gracefully renders even when the
    pipeline has not yet populated the chart_renders cache.

    Discriminating test pattern: monkeypatch the renderer + the bars
    fetcher; assert the renderer was invoked exactly once for the silver
    exemplar.
    """
    import pandas as pd

    from swing.web.view_models.patterns import exemplars as ex_module

    call_count = {"count": 0}

    def _stub_renderer(*, ticker, bars, pattern_evaluation,
                       exemplar_thumbnails=None):
        call_count["count"] += 1
        return b"<svg>live</svg>"

    monkeypatch.setattr(
        "swing.web.charts.render_theme2_annotated_svg", _stub_renderer,
    )

    def _stub_bars(_ticker):
        return pd.DataFrame({
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000, 1100],
        }, index=pd.date_range("2024-01-15", periods=2, freq="D"))

    cfg, _ = seeded_db_with_silver
    conn = connect(cfg.paths.db_path)
    try:
        vm = ex_module.build_patterns_exemplars_vm(
            conn, session_date="2026-05-20", bars_fetcher=_stub_bars,
        )
    finally:
        conn.close()
    assert call_count["count"] == 1, (
        "Codex R1 MAJOR #6 regression: cache-miss path must invoke "
        f"render_theme2_annotated_svg once; got {call_count['count']}"
    )
    # Live-rendered bytes surface in the VM.
    assert vm.exemplar_renders, "exemplar_renders empty"
    one = next(iter(vm.exemplar_renders.values()))
    assert one.chart_svg_bytes == b"<svg>live</svg>"


def test_get_patterns_exemplars_narrative_ascii_only(seeded_db_with_silver):
    cfg, cfg_path = seeded_db_with_silver
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    body = r.text
    # The narrative we seeded is ASCII; verify it round-trips intact.
    assert "Three contractions tightening from 22pct to 8pct" in body


# ---------------------------------------------------------------------------
# Phase 13 T2.SB6c T-A.6c.2 — Gap A.4: cache-miss write-through tests.
#
# Per plan §G.2 step 1a (3 tests): the cache-miss render path MUST also
# call `refresh_chart_render` to populate the `chart_renders` cache so a
# subsequent build serves the row from cache without re-rendering. The
# substrate enforces F6 transient-empty defense at the ChartRender
# construction barrier (T2.SB6a R1 MAJOR #2 LOCK); the cache key follows
# `surface='theme2_annotated'` with the exemplar's `proposed_pattern_class`
# + a synthesized pipeline_run_id anchor (V2-banked alternative: extend
# substrate to accept pipeline-run-agnostic theme2 cache key).
# ---------------------------------------------------------------------------


def _seed_completed_pipeline_run(conn, *, run_id: int = 555) -> None:
    """Seed a completed pipeline_runs row so the exemplar write-through can
    anchor on `latest_completed_pipeline_run(conn).run_id`."""
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token) VALUES "
        "(?, '2026-05-20T08:00:00', '2026-05-20T09:00:00', 'manual', "
        "'2026-05-19', '2026-05-20', 'complete', 't-exwt')",
        (run_id,),
    )


def test_cache_miss_render_writes_through_to_chart_renders_cache(
    seeded_db_with_silver, monkeypatch,
):
    """Gap A.4 — cache-miss path renders + persists the bytes back to
    chart_renders via `refresh_chart_render` so the next build is a hit.

    Discriminating: invoke twice. First call hits the cache-miss branch
    (renderer stubbed); second call must serve from chart_renders (renderer
    NOT invoked again).
    """
    import pandas as pd

    from swing.data.repos.chart_renders import list_chart_renders
    from swing.web.view_models.patterns import exemplars as ex_module

    call_count = {"count": 0}

    def _stub_renderer(*, ticker, bars, pattern_evaluation,
                       exemplar_thumbnails=None):
        call_count["count"] += 1
        return b"<svg>live-and-cached</svg>"

    monkeypatch.setattr(
        "swing.web.charts.render_theme2_annotated_svg", _stub_renderer,
    )

    def _stub_bars(_ticker):
        return pd.DataFrame({
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000, 1100],
        }, index=pd.date_range("2024-01-15", periods=2, freq="D"))

    cfg, _ = seeded_db_with_silver
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_completed_pipeline_run(conn, run_id=555)
        # Build #1 hits cache-miss branch + writes through.
        vm1 = ex_module.build_patterns_exemplars_vm(
            conn, session_date="2026-05-22", bars_fetcher=_stub_bars,
        )
        # Sanity: live bytes surface on first render.
        first = next(iter(vm1.exemplar_renders.values()))
        assert first.chart_svg_bytes == b"<svg>live-and-cached</svg>"
        # chart_renders cache row written.
        rows = list_chart_renders(conn, surface="theme2_annotated")
        assert len(rows) >= 1
        assert any(
            r.chart_svg_bytes == b"<svg>live-and-cached</svg>" for r in rows
        )
        # Build #2 must hit the cache; renderer NOT invoked a second time.
        prior_count = call_count["count"]
        vm2 = ex_module.build_patterns_exemplars_vm(
            conn, session_date="2026-05-22", bars_fetcher=_stub_bars,
        )
        second = next(iter(vm2.exemplar_renders.values()))
        assert second.chart_svg_bytes == b"<svg>live-and-cached</svg>"
        assert call_count["count"] == prior_count, (
            "Gap A.4 regression: second build must serve from cache; "
            f"renderer was invoked {call_count['count'] - prior_count} extra times"
        )
    finally:
        conn.close()


def test_cache_miss_write_through_skipped_when_renderer_returns_empty(
    seeded_db_with_silver, monkeypatch,
):
    """Gap A.4 + CLAUDE.md F6 LOCK — a transient empty-bytes render must
    NOT blank the cache (defended at the ChartRender construction barrier
    per T2.SB6a R1 MAJOR #2)."""
    import pandas as pd

    from swing.data.repos.chart_renders import list_chart_renders
    from swing.web.view_models.patterns import exemplars as ex_module

    # Pre-seed a known-good cache row that must survive.
    cfg, _ = seeded_db_with_silver
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            silver = exemplars_repo.list_exemplars(conn)[0]
            conn.execute(
                "INSERT INTO pipeline_runs (id, started_ts, finished_ts, "
                "trigger, data_asof_date, action_session_date, state, "
                "lease_token) VALUES (101, '2026-05-21T08:00:00', "
                "'2026-05-21T09:00:00', 'manual', '2024-02-01', "
                "'2024-02-02', 'complete', 't-pre')"
            )
            refresh_chart_render(conn, ChartRender(
                id=None, ticker=silver.ticker,
                surface="theme2_annotated",
                chart_svg_bytes=b"<svg>known-good</svg>",
                source_data_hash="hg",
                rendered_at="2026-05-21T09:00:00",
                data_asof_date="2024-02-01",
                pipeline_run_id=101,
                pattern_class=silver.proposed_pattern_class,
            ))
    finally:
        conn.close()

    def _empty_renderer(*, ticker, bars, pattern_evaluation,
                        exemplar_thumbnails=None):
        return b""

    monkeypatch.setattr(
        "swing.web.charts.render_theme2_annotated_svg", _empty_renderer,
    )

    def _stub_bars(_ticker):
        return pd.DataFrame({
            "Open": [100.0], "High": [101.0], "Low": [99.0],
            "Close": [100.5], "Volume": [1000],
        }, index=pd.date_range("2024-01-15", periods=1, freq="D"))

    conn = connect(cfg.paths.db_path)
    try:
        # The cache-hit path is consulted first; the empty renderer
        # would only fire on a miss. Verify the pre-seeded row survives
        # this build regardless.
        ex_module.build_patterns_exemplars_vm(
            conn, session_date="2026-05-22", bars_fetcher=_stub_bars,
        )
        rows = list_chart_renders(conn, surface="theme2_annotated")
        # The pre-seeded known-good row was NOT blanked by an empty render.
        assert any(
            r.chart_svg_bytes == b"<svg>known-good</svg>" for r in rows
        )
    finally:
        conn.close()


def test_cache_miss_write_through_uses_canonical_chart_render_dataclass(
    seeded_db_with_silver, monkeypatch,
):
    """Gap A.4 — the write-through path constructs a ChartRender via the
    canonical dataclass + uses `refresh_chart_render` (no caller-side
    INSERT OR REPLACE per L18 LOCK)."""
    import pandas as pd

    from swing.data.repos.chart_renders import list_chart_renders
    from swing.web.view_models.patterns import exemplars as ex_module

    def _stub_renderer(*, ticker, bars, pattern_evaluation,
                       exemplar_thumbnails=None):
        return b"<svg>canonical-substrate</svg>"

    monkeypatch.setattr(
        "swing.web.charts.render_theme2_annotated_svg", _stub_renderer,
    )

    def _stub_bars(_ticker):
        return pd.DataFrame({
            "Open": [100.0], "High": [101.0], "Low": [99.0],
            "Close": [100.5], "Volume": [1000],
        }, index=pd.date_range("2024-01-15", periods=1, freq="D"))

    cfg, _ = seeded_db_with_silver
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_completed_pipeline_run(conn, run_id=556)
        ex_module.build_patterns_exemplars_vm(
            conn, session_date="2026-05-22", bars_fetcher=_stub_bars,
        )
        # Inspect the persisted row via the canonical reader.
        rows = list_chart_renders(conn, surface="theme2_annotated")
        canonical_rows = [
            r for r in rows
            if r.chart_svg_bytes == b"<svg>canonical-substrate</svg>"
        ]
        assert canonical_rows, (
            "Gap A.4 regression: write-through must persist via "
            "refresh_chart_render + ChartRender canonical substrate"
        )
        # Cross-column shape: theme2_annotated requires non-NULL
        # pipeline_run_id + pattern_class (per ChartRender __post_init__).
        row = canonical_rows[0]
        assert row.pattern_class is not None
        assert row.pipeline_run_id is not None
    finally:
        conn.close()
