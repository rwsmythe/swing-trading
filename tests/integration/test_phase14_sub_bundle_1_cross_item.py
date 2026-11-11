"""Phase 14 Sub-bundle 1 cumulative ASCII discipline sweep + cross-item
audit (closer surface per plan section G.T-4.2).

The cross-item TestClient integration test is OPTIONAL per plan
section G.T-4.2 Step 1 -- operator-witnessed gate at section I is the
primary verification surface for S3+S4+S5a/b/c coexistence. This module
ships the cumulative ASCII discipline sweep (gotcha #32) which IS a
required closer artifact + a programmatic sub-bundle file enumeration
audit.

The branch Co-Authored-By trailer pin that also lived here was retired on
2026-11-11 by the Codex-lane arc (P6): the operator retired the trailer
prohibition on 2026-11-03.
"""

from __future__ import annotations

from pathlib import Path


def test_cumulative_ascii_discipline_across_subbundle_1_surface() -> None:
    """Per gotcha #32 + spec section 15.2: programmatic ASCII verification
    across all NEW + MODIFIED Sub-bundle 1 surfaces that are operator-
    facing render paths OR pure NEW production code.

    Scope rationale (gotcha #16 ASCII-scope-clarity discipline): the
    sweep covers files whose CONTENT renders to operator-facing
    surfaces (templates emit to browser; CLI helper emits to stdout;
    NEW test modules) PLUS the NEW production helper module which
    has no pre-existing non-ASCII baggage. Files like
    ``swing/web/view_models/dashboard.py`` + ``swing/web/view_models/trades.py``
    + ``swing/cli.py`` are excluded from the full-file ASCII assertion
    because they carry pre-existing non-ASCII docstring glyphs from
    earlier phases (Phase 7-13); the per-task ASCII discipline tests
    in T-1.2 + T-2.1 + T-3.1 scope-narrow to the NEW regions of those
    files (verified ASCII at the per-task commit).
    """
    repo_root = Path(__file__).resolve().parents[2]
    files_in_scope = [
        # NEW production files
        "swing/diagnostics/__init__.py",
        "swing/diagnostics/backfill_trades_sector_industry.py",
        # Operator-facing render surface (template)
        "swing/web/templates/partials/daily_management_tile.html.j2",
        # NEW test files
        "tests/data/repos/test_candidates_sector_industry_helper.py",
        "tests/cli/test_diagnose_backfill_trades_sector_industry.py",
        "tests/web/view_models/__init__.py",
        "tests/web/view_models/test_dashboard_view_model.py",
        "tests/integration/test_l2_lock_source_grep.py",
        "tests/integration/test_phase14_sub_bundle_1_cross_item.py",
    ]
    failures: list[str] = []
    for rel in files_in_scope:
        path = repo_root / rel
        if not path.exists():
            failures.append(f"{rel}: file not found")
            continue
        try:
            path.read_text(encoding="utf-8").encode("ascii")
        except UnicodeEncodeError as exc:
            failures.append(f"{rel}: {exc}")
    assert not failures, "ASCII discipline violations:\n" + "\n".join(failures)
