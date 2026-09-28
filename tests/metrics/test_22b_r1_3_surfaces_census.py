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
inherited, per CHARC's own closure-check instruction (recipe Sec 3, "a
hand-enumerated roster is the same instrument as the count it replaced").

RIDER R-1 (2026-09-28): the roster used to key each site as ``path:lineno``,
which broke on ANY edit above a pinned line (four consecutive re-derivations
with no new caller: D67/D69, the 22-I branch and merge, 22-F several times).
The roster now keys each site by ``(path, the stripped source-line TEXT)``,
compared to the grep's find-set as a MULTISET (``collections.Counter``) --
never a ``dict``, because a real governed name (``build_recommendation_
progress``, ``swing/web/view_models/dashboard.py`` lines 609 and 1277) has
TWO one-hop call sites whose stripped text is IDENTICAL in the SAME file; a
dict keyed on (path, text) would collapse them to one entry and silently
under-count. The test still FAILS when a NEW one-hop caller appears, when a
rostered caller disappears, or when a call line's text changes; it PASSES
when an unrelated edit merely moves a rostered line.
"""
from __future__ import annotations

import re
from collections import Counter
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

# One-hop caller -> classification, by (path, stripped call-line TEXT). A
# LIST of (path, text, classification) -- never a dict -- because two
# rostered sites in one file can carry IDENTICAL stripped text (see the
# build_recommendation_progress entries below); the roster and the grep's
# find-set are compared as MULTISETS, not as a set of unique keys.
# "GOVERNED_CLI" / "GOVERNED_PAGE": item 1 (ii) -- refuses (CLI
# ClickException) or degrades-at-200 (the 3 metrics pages), unchanged /
# fixed by this arc's own commits. "SECONDARY_CONTAINED": item 1 (i) --
# contains CohortReadRacedError, degrades a panel, page renders.
# "PREFILL_DEGRADED": item 2. "DEFINITION": the function's own `def` line
# (not a call site; present in the source so the grep count is exact).
_ONE_HOP_CALLERS: dict[str, list[tuple[str, str, str]]] = {
    "compute_hypothesis_progress_breakdown": [
        (
            "swing/journal/stats.py",
            "def compute_hypothesis_progress_breakdown(",
            "DEFINITION",
        ),
        (
            "swing/cli.py",
            "progress_rows = compute_hypothesis_progress_breakdown(",
            "GOVERNED_CLI (journal review)",
        ),
        (
            "swing/web/view_models/dashboard.py",
            "progress_rows = compute_hypothesis_progress_breakdown(",
            "the DEFINITION of build_recommendation_progress -- its own "
            "one-hop dependency, not a second call site",
        ),
    ],
    "compute_tier_comparison": [
        ("swing/metrics/tier.py", "def compute_tier_comparison(", "DEFINITION"),
        (
            "swing/metrics/tier.py",
            "tier = compute_tier_comparison(",
            "the DEFINITION of compute_deviation_outcome -- delegates, "
            "not a second call site",
        ),
        (
            "swing/web/view_models/metrics/tier_comparison.py",
            "result = compute_tier_comparison(",
            "GOVERNED_PAGE (/metrics/tier-comparison)",
        ),
    ],
    "compute_deviation_outcome": [
        ("swing/metrics/tier.py", "def compute_deviation_outcome(", "DEFINITION"),
        (
            "swing/web/view_models/metrics/deviation_outcome.py",
            "result = compute_deviation_outcome(",
            "GOVERNED_PAGE (/metrics/deviation-outcome)",
        ),
    ],
    "compute_tripwire_status": [
        (
            "swing/recommendations/hypothesis.py",
            "def compute_tripwire_status(",
            "DEFINITION",
        ),
        (
            "swing/cli.py",
            "(h, compute_tripwire_status(",
            "GOVERNED_CLI (hypothesis list)",
        ),
        (
            "swing/cli.py",
            "tw = compute_tripwire_status(",
            "GOVERNED_CLI (hypothesis status)",
        ),
        (
            "swing/journal/stats.py",
            "tw = compute_tripwire_status(",
            "inside compute_hypothesis_progress_breakdown itself -- "
            "already a governed reader (per-hypothesis tripwire compute)",
        ),
    ],
    "build_hypothesis_progress_card_vm": [
        (
            "swing/web/view_models/metrics/hypothesis_progress_card.py",
            "def build_hypothesis_progress_card_vm(",
            "DEFINITION",
        ),
        (
            "swing/web/routes/metrics.py",
            "vm = build_hypothesis_progress_card_vm(",
            "GOVERNED_PAGE (/metrics/hypothesis-progress)",
        ),
        (
            "swing/web/view_models/metrics/index.py",
            "vm = build_hypothesis_progress_card_vm(",
            "SECONDARY_CONTAINED (/metrics overview card; the pre-existing "
            "broad except plus this arc's cohort_read_raced_message check)",
        ),
    ],
    "lookup_active_recommendation_label": [
        (
            "swing/recommendations/hypothesis_prefill.py",
            "def lookup_active_recommendation_label(",
            "DEFINITION",
        ),
        (
            "swing/cli.py",
            "prefilled = lookup_active_recommendation_label(",
            "PREFILL_DEGRADED (CLI swing trade entry)",
        ),
        (
            "swing/web/view_models/trades.py",
            "resolved_hypothesis_label = lookup_active_recommendation_label(",
            "PREFILL_DEGRADED (web entry-form GET)",
        ),
    ],
    "build_recommendation_progress": [
        (
            "swing/web/view_models/dashboard.py",
            "def build_recommendation_progress(",
            "DEFINITION",
        ),
        (
            "swing/web/view_models/dashboard.py",
            "build_recommendation_progress(",
            "SECONDARY_CONTAINED (build_hyp_recs_section -- "
            "GET /hyp-recs/refresh)",
        ),
        (
            "swing/web/view_models/dashboard.py",
            "build_recommendation_progress(",
            "SECONDARY_CONTAINED (build_dashboard -- GET /, "
            "POST /prices/refresh)",
        ),
        (
            "swing/recommendations/hypothesis_prefill.py",
            "_, progress_summaries = build_recommendation_progress(",
            "the DEFINITION of lookup_active_recommendation_label -- its "
            "own one-hop dependency, not a second call site",
        ),
    ],
}


def _grep_call_sites(name: str, *, root: Path | None = None) -> Counter[tuple[str, str]]:
    """``grep -rn "<name>(" swing/`` re-derived as a static walk -- every
    line under ``swing/**/*.py`` containing ``name(``, as a MULTISET of
    ``(path, stripped-line-text)``. Includes the function's own ``def``
    line (the grep pattern matches ``def name(`` too), matching the METHOD
    stated in the module docstring exactly. ``root`` defaults to the repo
    root; the meta-tests below pass a ``tmp_path`` fake tree."""
    base = root if root is not None else REPO_ROOT
    pat = re.compile(rf"\b{re.escape(name)}\(")
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted((base / "swing").rglob("*.py")):
        rel = path.relative_to(base).as_posix()
        for line in path.read_text(encoding="utf-8").splitlines():
            if pat.search(line):
                found[(rel, line.strip())] += 1
    return found


def _rostered_multiset(roster: list[tuple[str, str, str]]) -> Counter[tuple[str, str]]:
    return Counter((path, text) for path, text, _classification in roster)


def test_census_roster_matches_the_grep_for_each_governed_name() -> None:
    for name in _GOVERNED_NAMES:
        found = _grep_call_sites(name)
        rostered = _rostered_multiset(_ONE_HOP_CALLERS[name])
        assert found == rostered, (
            name, "extra_in_found=" + repr(found - rostered),
            "missing_from_found=" + repr(rostered - found),
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
        for path, text, disposition in sites:
            assert disposition.startswith(allowed_prefixes), (
                name, path, text, disposition,
            )


# ---------------------------------------------------------------------------
# R-1 meta-tests: the census's own mechanism, over a tmp_path fake tree.
# ---------------------------------------------------------------------------

def _write_swing_module(root: Path, relpath: str, text: str) -> None:
    path = root / "swing" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_line_number_keying_would_have_failed_this_case(tmp_path: Path) -> None:
    """Pins the REGRESSION this rider fixes. A path:lineno-keyed roster
    (the pre-R-1 shape) breaks under a no-op edit that shifts line numbers
    -- exactly the D67/D69/22-I/22-F re-derivation churn. The TEXT-keyed
    walk (``_grep_call_sites``) is unaffected by the same edit."""
    _write_swing_module(tmp_path, "mod.py", "helper_fn(\n")
    old_style_roster = {"swing/mod.py:1": "DEFINITION"}

    # an unrelated edit: 3 blank lines inserted above the rostered call
    _write_swing_module(tmp_path, "mod.py", "\n\n\nhelper_fn(\n")

    pat = re.compile(r"\bhelper_fn\(")
    found_old_style: set[str] = set()
    for path in sorted((tmp_path / "swing").rglob("*.py")):
        rel = path.relative_to(tmp_path).as_posix()
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pat.search(line):
                found_old_style.add(f"{rel}:{i}")
    # RED (the old keying): the unrelated edit alone breaks the roster.
    assert found_old_style != set(old_style_roster)

    # GREEN (the new keying): the same edit does not disturb it.
    found_new = _grep_call_sites("helper_fn", root=tmp_path)
    assert found_new == Counter({("swing/mod.py", "helper_fn("): 1})


def test_a_unrelated_edit_moving_a_rostered_line_passes(tmp_path: Path) -> None:
    # (a) blank lines inserted ABOVE a rostered call line must not disturb
    # the TEXT-keyed multiset.
    _write_swing_module(tmp_path, "mod.py", "x = 1\n" * 5 + "helper_fn(\n")
    found = _grep_call_sites("helper_fn", root=tmp_path)
    roster = [("swing/mod.py", "helper_fn(", "DEFINITION")]
    assert found == _rostered_multiset(roster)


def test_b_new_caller_line_fails_naming_it(tmp_path: Path) -> None:
    # (b) a NEW one-hop caller line the roster does not know about must
    # FAIL, and the failure names it.
    _write_swing_module(
        tmp_path, "mod.py",
        "def helper_fn():\n    pass\n\n\ndef caller():\n    helper_fn(\n",
    )
    roster = [("swing/mod.py", "def helper_fn():", "DEFINITION")]
    found = _grep_call_sites("helper_fn", root=tmp_path)
    rostered = _rostered_multiset(roster)
    assert found != rostered
    extra = found - rostered
    assert extra[("swing/mod.py", "helper_fn(")] == 1


def test_c_deleted_rostered_caller_fails(tmp_path: Path) -> None:
    # (c) a rostered call site that no longer exists must FAIL.
    _write_swing_module(tmp_path, "mod.py", "def helper_fn():\n    pass\n")
    roster = [
        ("swing/mod.py", "def helper_fn():", "DEFINITION"),
        ("swing/mod.py", "helper_fn(", "GOVERNED_CLI (gone)"),
    ]
    found = _grep_call_sites("helper_fn", root=tmp_path)
    rostered = _rostered_multiset(roster)
    assert found != rostered
    missing = rostered - found
    assert missing[("swing/mod.py", "helper_fn(")] == 1


def test_duplicate_identical_call_line_in_one_file_is_counted_not_collapsed(
    tmp_path: Path,
) -> None:
    # The multiset-vs-dict discriminator: two identical call lines in one
    # file must both be present in the grep's find-set (count 2), and a
    # roster with only ONE such entry must FAIL to match.
    _write_swing_module(
        tmp_path, "mod.py",
        "def a():\n    helper_fn(\n\n\ndef b():\n    helper_fn(\n",
    )
    found = _grep_call_sites("helper_fn", root=tmp_path)
    assert found[("swing/mod.py", "helper_fn(")] == 2
    under_rostered = _rostered_multiset(
        [("swing/mod.py", "helper_fn(", "GOVERNED_CLI (only one)")]
    )
    assert found != under_rostered
