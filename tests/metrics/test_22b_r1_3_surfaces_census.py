"""Arc 22-B RULING R1-3-SURFACES -- the ONE-HOP CONSUMER CENSUS, BY METHOD.

"each surface renders its refusal" (the R1-3 rulings) named the four
governed readers' OWN pages, not the pages that CONSUME them -- existence
is not completeness (CHARC, owning the miss, RULING R1-3-SURFACES). This
file is the census cell 12 was routed to state and cell 13 to record: every
ONE-HOP caller of the four governed readers, plus ``lookup_active_
recommendation_label`` (the prefill's own governed dependency), each
classified by how this arc leaves it.

METHOD: ``grep -rn "<name>(" swing/ | grep -v ".pyc"`` per governed
function, read by hand for the calling line + its containing function/
route. The walk below RE-DERIVES that grep as a static AST-lite regex scan
over ``swing/**/*.py`` so a NEW one-hop caller FAILS this test until it is
added to the roster with its classification -- the census does not stay
inherited, per CHARC's own closure-check instruction (recipe §3, "a
hand-enumerated roster is the same instrument as the count it replaced").
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The four governed readers (R1-3) plus the prefill's own governed
# dependency, and the one INTERMEDIATE hop this arc's item 1 (i) contains
# (build_recommendation_progress -- itself a direct caller of
# compute_hypothesis_progress_breakdown, and itself called by 3 sites this
# arc isolates/degrades).
_GOVERNED_NAMES: tuple[str, ...] = (
    "compute_hypothesis_progress_breakdown",
    "compute_tier_comparison",
    "compute_deviation_outcome",
    "compute_tripwire_status",
    "build_hypothesis_progress_card_vm",
    "lookup_active_recommendation_label",
    "build_recommendation_progress",
)

# One-hop caller -> classification, by (path, line-content substring).
# "GOVERNED_CLI" / "GOVERNED_PAGE": item 1 (ii) -- refuses (CLI
# ClickException) or degrades-at-200 (the 3 metrics pages), unchanged /
# fixed by this arc's own commits. "SECONDARY_CONTAINED": item 1 (i) --
# contains CohortReadRacedError, degrades a panel, page renders.
# "PREFILL_DEGRADED": item 2. "DEFINITION": the function's own `def` line
# (not a call site; present in the source so the grep count is exact).
_ONE_HOP_CALLERS: dict[str, dict[str, str]] = {
    "compute_hypothesis_progress_breakdown": {
        "swing/journal/stats.py:344": "DEFINITION",
        "swing/cli.py:2169": "GOVERNED_CLI (journal review)",
        "swing/web/view_models/dashboard.py:248": (
            "the DEFINITION of build_recommendation_progress -- its own "
            "one-hop dependency, not a second call site"
        ),
    },
    "compute_tier_comparison": {
        "swing/metrics/tier.py:664": "DEFINITION",
        "swing/metrics/tier.py:865": (
            "the DEFINITION of compute_deviation_outcome -- delegates, "
            "not a second call site"
        ),
        "swing/web/view_models/metrics/tier_comparison.py:109": (
            "GOVERNED_PAGE (/metrics/tier-comparison)"
        ),
    },
    "compute_deviation_outcome": {
        "swing/metrics/tier.py:836": "DEFINITION",
        "swing/web/view_models/metrics/deviation_outcome.py:108": (
            "GOVERNED_PAGE (/metrics/deviation-outcome)"
        ),
    },
    "compute_tripwire_status": {
        "swing/recommendations/hypothesis.py:489": "DEFINITION",
        "swing/cli.py:5229": "GOVERNED_CLI (hypothesis list)",
        "swing/cli.py:5277": "GOVERNED_CLI (hypothesis status)",
        "swing/journal/stats.py:453": (
            "inside compute_hypothesis_progress_breakdown itself -- "
            "already a governed reader (per-hypothesis tripwire compute)"
        ),
    },
    "build_hypothesis_progress_card_vm": {
        "swing/web/view_models/metrics/hypothesis_progress_card.py:483": (
            "DEFINITION"
        ),
        "swing/web/routes/metrics.py:295": (
            "GOVERNED_PAGE (/metrics/hypothesis-progress)"
        ),
        "swing/web/view_models/metrics/index.py:254": (
            "SECONDARY_CONTAINED (/metrics overview card; the pre-existing "
            "broad except plus this arc's cohort_read_raced_message check)"
        ),
    },
    "lookup_active_recommendation_label": {
        "swing/recommendations/hypothesis_prefill.py:40": "DEFINITION",
        "swing/cli.py:835": "PREFILL_DEGRADED (CLI swing trade entry)",
        "swing/web/view_models/trades.py:594": (
            "PREFILL_DEGRADED (web entry-form GET)"
        ),
    },
    "build_recommendation_progress": {
        "swing/web/view_models/dashboard.py:211": "DEFINITION",
        "swing/web/view_models/dashboard.py:609": (
            "SECONDARY_CONTAINED (build_hyp_recs_section -- "
            "GET /hyp-recs/refresh)"
        ),
        "swing/web/view_models/dashboard.py:1277": (
            "SECONDARY_CONTAINED (build_dashboard -- GET /, "
            "POST /prices/refresh)"
        ),
        "swing/recommendations/hypothesis_prefill.py:77": (
            "the DEFINITION of lookup_active_recommendation_label -- its "
            "own one-hop dependency, not a second call site"
        ),
    },
}


def _grep_call_sites(name: str) -> set[str]:
    """``grep -rn "<name>(" swing/`` re-derived as a static walk -- every
    line under ``swing/**/*.py`` containing ``name(``, as ``path:lineno``.
    Includes the function's own ``def`` line (the grep pattern matches
    ``def name(`` too), matching the METHOD stated in the module docstring
    exactly."""
    pat = re.compile(rf"\b{re.escape(name)}\(")
    found: set[str] = set()
    for path in (REPO_ROOT / "swing").rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for i, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if pat.search(line):
                found.add(f"{rel}:{i}")
    return found


def test_census_roster_matches_the_grep_for_each_governed_name() -> None:
    for name in _GOVERNED_NAMES:
        found = _grep_call_sites(name)
        rostered = set(_ONE_HOP_CALLERS[name])
        assert found == rostered, (
            name, sorted(found ^ rostered),
        )


def test_every_classification_is_one_of_the_named_dispositions() -> None:
    allowed_prefixes = (
        "DEFINITION",
        "GOVERNED_CLI",
        "GOVERNED_PAGE",
        "SECONDARY_CONTAINED",
        "PREFILL_DEGRADED",
        "the DEFINITION of",
        "inside compute_hypothesis_progress_breakdown",
    )
    for name, sites in _ONE_HOP_CALLERS.items():
        for site, disposition in sites.items():
            assert disposition.startswith(allowed_prefixes), (
                name, site, disposition,
            )
