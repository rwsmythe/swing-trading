"""Cross-bundle pin row 11 (plan H.3) — caller-tx contract invariant.

Phase 13 T2.SB1 T-A.1.1b plan H.3 row 11 planted the test name; cross-
bundle pin schedule said "un-skips at T2.SB6 + T4.SB Q4 service when
used". T2.SB6b T-A.6.7 closer un-skips per the plan precedent: plant +
un-skip (the test was not landed at T-A.1.1b; this is the planting +
the un-skip, paired).

Invariant: repo functions on the 4 Phase 13 NEW tables
(pattern_exemplars + pattern_evaluations + chart_renders +
watchlist_close_track) MUST honor the caller-tx contract — NO direct
``conn.commit()`` calls in the repo bodies. The caller wraps with
``with conn:`` (or explicit ``BEGIN IMMEDIATE``). Per Phase 9 Sub-bundle
A lesson family + plan A.15 + A.18 LOCK.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

# Repo files under audit. Each file's source MUST NOT contain a direct
# `conn.commit()` substring; the caller-tx contract is enforced by the
# absence of commit calls in production code paths.
_REPO_PATHS = (
    "swing/data/repos/pattern_exemplars.py",
    "swing/data/repos/pattern_evaluations.py",
    "swing/data/repos/chart_renders.py",
    "swing/data/repos/watchlist_close_track.py",
)


@pytest.mark.parametrize("repo_relpath", _REPO_PATHS)
def test_repo_caller_tx_contract_invariant(repo_relpath: str) -> None:
    """Audit each Phase 13 NEW repo module for caller-tx contract honoring.

    Per plan H.3 row 11 + Phase 9 Sub-bundle A lesson family: repo functions
    NEVER call ``conn.commit()`` — the caller owns the transaction. Any
    ``commit()`` call inside the repo module would prematurely commit
    composing services' atomic boundaries (per CLAUDE.md gotcha "Service-
    layer ``with conn:`` opens its own transaction").
    """
    # Walk from this file up to the project root (find pyproject.toml).
    test_path = pathlib.Path(__file__).resolve()
    project_root: pathlib.Path | None = None
    for parent in (test_path, *test_path.parents):
        if (parent / "pyproject.toml").exists():
            project_root = parent
            break
    assert project_root is not None, (
        "could not locate pyproject.toml ancestor; test layout broken"
    )
    repo_file = project_root / repo_relpath
    assert repo_file.exists(), (
        f"expected repo module {repo_relpath} to exist under {project_root}"
    )
    src = repo_file.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(repo_file))
    # AST-walk the module body looking for any `<expr>.commit(...)` Call
    # node. Docstring / comment mentions of "commit()" are NOT Call
    # nodes and pass the audit by construction.
    commit_calls: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "commit":
                # Reconstruct a rough text for the receiver (defensive —
                # only used in error message).
                receiver = getattr(func.value, "id", "<expr>")
                commit_calls.append((node.lineno, f"{receiver}.commit(...)"))
    assert not commit_calls, (
        f"caller-tx contract violation in {repo_relpath}: found "
        f"{len(commit_calls)} `.commit(...)` call(s) at lines "
        f"{[ln for ln, _ in commit_calls]}. Per plan H.3 row 11 + "
        "Phase 9 Sub-bundle A lesson family, repo functions on Phase 13 "
        "NEW tables MUST NOT call conn.commit() directly. The caller "
        "owns the transaction via `with conn:` or explicit BEGIN "
        f"IMMEDIATE. Calls found: {commit_calls!r}"
    )
