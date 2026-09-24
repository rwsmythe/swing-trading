"""Arc 22-B R1-3 -- the WEB surfaces over the governed decision readers, by
execution: what each renders when a governed read refuses with
``CohortReadRacedError`` (RULING R1-3-SHAPE-EXEC: never the contradictory
row, never a partial row).

The refusal is planted at the ASSERT, in every namespace that binds it
(``tier.py`` and the card bind it at import; ``stats.py`` and
``hypothesis.py`` import it from ``swing.metrics.cohort`` at call time), so
every governed reader refuses through its REAL code path. The race itself is
planted by execution in ``tests/metrics/test_22b_cohort_read_race.py``.

Per RULING R1-3-SURFACES item 1 (ii): the metrics overview isolates each
card and shows it "unavailable"; the three standalone metric routes now
degrade the GOVERNED REGION and render at 200 (the /metrics overview's
card-suppression idiom) -- never the app-wide 500 (D34).
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app

GOVERNED_CARDS = ("/metrics/hypothesis-progress", "/metrics/tier-comparison",
                  "/metrics/deviation-outcome")


def _raced_message() -> str:
    """Read the CURRENT ruled text off the real type, not a copy -- the
    text is item 4's to own (this file only asserts it renders)."""
    from swing.metrics.cohort import CohortReadRacedError
    return str(CohortReadRacedError((3,)))


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
def test_standalone_governed_routes_degrade_the_governed_region_b22_236(
        seeded_db, monkeypatch, path: str) -> None:
    """RULING R1-3-SURFACES item 1 (ii): each of the three routes IS the
    governed read -- it renders its page at 200 with the refusal text in
    the governed region, never the app-wide 500 (D34), never a partial /
    contradictory row."""
    cfg, cfg_path = seeded_db
    _refuse_every_governed_read(monkeypatch)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        resp = client.get(path)
    assert resp.status_code == 200, (path, resp.status_code, resp.text)
    assert _raced_message() in resp.text, (path, resp.text)
    assert "not counted" not in resp.text
    assert "governed-region-unavailable" in resp.text, resp.text
