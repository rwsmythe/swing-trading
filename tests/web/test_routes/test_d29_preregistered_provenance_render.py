"""D29 rider -- the preserved ORIGINAL criterion reaches the three
criterion-rendering SURFACES as PROVENANCE DETAIL (route half).

The VM half lives at tests/metrics/test_d29_preregistered_provenance_render.py;
these need the web ``seeded_db`` fixture, which is scoped to tests/web/.

RD ruling 2026-08-04: a secondary render (detail row / title attribute /
expandable), NOT inline prose beside the live 577-char amendment.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from swing.web.app import create_app
from tests.data.test_migration_0034_h1_criteria_amendment import (
    PREREGISTERED_H1_DECISION_CRITERIA,
)

_PROVENANCE_CLASS = "preregistered-criterion"


# ---------------------------------------------------------------------------
# The three surfaces render it as SECONDARY detail, not inline prose
# ---------------------------------------------------------------------------

_SURFACES = (
    "/metrics/tier-comparison",
    "/metrics/deviation-outcome",
    "/metrics/hypothesis-progress",
)


def _fetch(seeded_db, path: str) -> str:
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code == 200
    return r.text


@pytest.mark.parametrize("path", _SURFACES)
def test_surface_exposes_the_original_behind_a_collapsed_affordance(
    seeded_db, path: str,
):
    html = _fetch(seeded_db, path)
    assert _PROVENANCE_CLASS in html, (
        f"{path} does not expose the preserved original at all"
    )
    # The affordance is a <details> (collapsed by default -- no `open`
    # attribute), so the original is REACHABLE without being read at a
    # glance beside the 577-char amendment.
    block = re.search(
        r"<details class=\"" + _PROVENANCE_CLASS + r"\"[^>]*>(.*?)</details>",
        html,
        re.DOTALL,
    )
    assert block is not None, f"{path}: provenance block is not a <details>"
    assert "open" not in (
        re.search(
            r"<details class=\"" + _PROVENANCE_CLASS + r"\"([^>]*)>", html,
        ).group(1)
    )
    # Compare against the PRODUCTION escaper's output (markupsafe is what
    # Jinja autoescaping uses), not the raw text -- '>' renders as '&gt;'.
    assert str(escape(PREREGISTERED_H1_DECISION_CRITERIA)) in block.group(1)


@pytest.mark.parametrize("path", _SURFACES)
def test_surface_renders_exactly_one_provenance_block(seeded_db, path: str):
    """Only the AMENDED cohort gets one. Three of the four registered
    cohorts have never been amended, and a block reading "(none)" would
    be noise on every one of them."""
    html = _fetch(seeded_db, path)
    assert html.count(f'class="{_PROVENANCE_CLASS}"') == 1
