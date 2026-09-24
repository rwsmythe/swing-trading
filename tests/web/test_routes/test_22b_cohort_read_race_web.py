"""Arc 22-B R1-3 -- the WEB surfaces over the governed decision readers, by
execution: what each renders when a governed read refuses with
``CohortReadRacedError`` (RULING R1-3-SHAPE-EXEC: never the contradictory
row, never a partial row).

The refusal is planted at the ASSERT, in every namespace that binds it
(``tier.py`` and the card bind it at import; ``stats.py`` and
``hypothesis.py`` import it from ``swing.metrics.cohort`` at call time), so
every governed reader refuses through its REAL code path. The race itself is
planted by execution in ``tests/metrics/test_22b_cohort_read_race.py``.

What exists today, measured here and not invented: the metrics overview
isolates each card and shows it "unavailable"; the three standalone metric
routes have NO route-level degraded message, so the refusal reaches the
app-wide handler (the error page, status 500, carrying the ruled text).
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app

RACED_MESSAGE = "cohort read raced an intent write; re-run"
GOVERNED_CARDS = ("/metrics/hypothesis-progress", "/metrics/tier-comparison",
                  "/metrics/deviation-outcome")


def _refuse_every_governed_read(monkeypatch) -> None:
    import swing.metrics.cohort as cohort_mod
    import swing.metrics.tier as tier_mod
    import swing.web.view_models.metrics.hypothesis_progress_card as card_mod

    def raced(counted_ids, named):
        raise cohort_mod.CohortReadRacedError((3,))

    for mod in (cohort_mod, tier_mod, card_mod):
        monkeypatch.setattr(mod, "assert_intent_exclusion_disjoint", raced)


def _suppressed(cfg) -> dict[str, str | None]:
    from swing.web.view_models.metrics.index import build_metrics_index_vm

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        vm = build_metrics_index_vm(cfg, conn)
    finally:
        conn.close()
    return {s.path: s.headline_suppressed_text for s in vm.surfaces}


def test_metrics_overview_degrades_each_governed_card_b22_236(
        seeded_db, monkeypatch) -> None:
    cfg, _cfg_path = seeded_db
    before = _suppressed(cfg)
    for path in GOVERNED_CARDS:  # the counterfactual: not already degraded
        assert before[path] != "unavailable", (path, before[path])
    _refuse_every_governed_read(monkeypatch)
    after = _suppressed(cfg)
    for path in GOVERNED_CARDS:
        assert after[path] == "unavailable", (path, after[path])
    # Only the governed cards moved (per-card isolation, not a page failure).
    moved = {p for p in before if before[p] != after[p]}
    assert moved == set(GOVERNED_CARDS), moved


@pytest.mark.parametrize("path", GOVERNED_CARDS)
def test_standalone_governed_routes_reach_the_app_handler_b22_236(
        seeded_db, monkeypatch, path: str) -> None:
    """No route-level degraded message exists on these three routes; the
    refusal renders as the app-wide error page with the ruled text, never
    the card's rows."""
    cfg, cfg_path = seeded_db
    _refuse_every_governed_read(monkeypatch)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        resp = client.get(path)
    assert resp.status_code == 500, (path, resp.status_code)
    assert RACED_MESSAGE in resp.text
    assert "not counted" not in resp.text
