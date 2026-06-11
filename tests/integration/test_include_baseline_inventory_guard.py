from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

EXPECTED_OPT_IN_FILES = {
    "swing/recommendations/hypothesis_prefill.py",
    "swing/web/view_models/watchlist.py",
    "research/harness/shadow_expectancy/attribution.py",
}


def test_include_baseline_true_call_sites_are_exactly_three():
    hits = set()
    for base in ("swing", "research"):
        for p in (REPO / base).rglob("*.py"):
            if "include_baseline=True" in p.read_text(encoding="utf-8"):
                hits.add(p.relative_to(REPO).as_posix())
    assert hits == EXPECTED_OPT_IN_FILES, (
        f"include_baseline=True opt-in set drifted. Found: {sorted(hits)}. "
        f"Add a 0026 ADDENDUM governance amendment before adding a new opt-in."
    )
