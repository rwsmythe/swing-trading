"""Governance tripwire (Arc-7 spec §10.3): the COMPLETE set of
``include_baseline=True`` opt-in call sites must stay EXACTLY the three the
0026 §ADDENDUM enumerates. Any new opt-in fails this test and forces a
governance amendment.

Codex R1 (executing-plans adversarial review) hardened this from a
file-substring scan to an AST CALL-SITE scan: the spec §10.3 wording is
"asserts the set of CALL SITES is EXACTLY [3]". A file-substring set would
not trip on (a) a FOURTH literal added inside an already-approved file, nor
(b) the syntactically-equivalent ``include_baseline = True`` (spacing). The
AST scan counts every ``match_candidate_to_hypotheses(..., include_baseline=
<constant True>)`` call site by (path, lineno), so both gaps are closed.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# The three sanctioned opt-in files (0026 §ADDENDUM bounded set). Each holds
# EXACTLY ONE opt-in call site → the total call-site count must be 3.
EXPECTED_OPT_IN_FILES = {
    "swing/recommendations/hypothesis_prefill.py",
    "swing/web/view_models/watchlist.py",
    "research/harness/shadow_expectancy/attribution.py",
}


def _opt_in_call_sites() -> list[tuple[str, int]]:
    """Every ``match_candidate_to_hypotheses(...)`` call (by name or attribute)
    that passes ``include_baseline`` as a constant ``True`` keyword. Returns
    (relative_posix_path, lineno) tuples across swing/ + research/."""
    sites: list[tuple[str, int]] = []
    for base in ("swing", "research"):
        for p in (REPO / base).rglob("*.py"):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name != "match_candidate_to_hypotheses":
                    continue
                for kw in node.keywords:
                    if (
                        kw.arg == "include_baseline"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        sites.append((p.relative_to(REPO).as_posix(), node.lineno))
    return sites


def test_include_baseline_true_call_sites_are_exactly_three():
    sites = _opt_in_call_sites()
    files = {path for path, _ in sites}
    assert files == EXPECTED_OPT_IN_FILES, (
        f"include_baseline=True opt-in FILE set drifted. Found call sites: "
        f"{sorted(sites)}. Add a 0026 §ADDENDUM governance amendment before "
        f"adding a new opt-in."
    )
    # Call-site count (not just file set): a FOURTH literal added inside an
    # already-approved file trips this even though the file set is unchanged.
    assert len(sites) == 3, (
        f"expected exactly 3 include_baseline=True call sites (one per "
        f"sanctioned file); found {len(sites)}: {sorted(sites)}. A new opt-in "
        f"call site requires a 0026 §ADDENDUM governance amendment."
    )
