"""Structural-guard test: no inline `pipeline_runs WHERE state='complete'`
queries outside the two helpers.

Centralization invariant per the Bug-7-family durable-closure plan
(Phase 4 cleanup-remainder, 2026-04-30). Enforces:

  - `latest_completed_pipeline_run` (chart_scope.py) is the single source
    of truth for pipeline-bound reads of the latest completed run.
  - `latest_evaluation_run_id` (view_models/dashboard.py) is the single
    source of truth for with-fallback reads (pipeline-bound first,
    falling back to MAX(run_ts) FROM evaluation_runs).

A future contributor who adds an inline query against `pipeline_runs
WHERE state='complete'` outside these two files re-introduces the
mixed-anchor failure mode that this dispatch closed. This test fails
with a path-bearing error so the regression surfaces in CI.

EXCEPTIONS (deliberately allowed):
  - `state` query on dashboard.py (started_ts DESC, no state filter):
    the in-flight-pipeline-state surface; structurally distinct from
    the `state='complete'` family.
"""
from __future__ import annotations

import re
from pathlib import Path

# Pattern matches: FROM pipeline_runs <optional alias> WHERE state='complete'
# OR state = 'complete' (with optional whitespace). Captures the SQL invariant
# the centralization closes. The optional alias group (`pipeline_runs pr`,
# `pipeline_runs AS pr`) defends against the false-negative variant Codex R1
# Minor 3 flagged.
INLINE_QUERY_PATTERN = re.compile(
    r"FROM\s+pipeline_runs(?:\s+(?:AS\s+)?\w+)?\s+WHERE\s+state\s*=\s*'complete'",
    re.IGNORECASE,
)


def _strip_python_line_comments(text: str) -> str:
    """Strip Python `#`-prefixed end-of-line comment text so the regex
    cannot match `# WHERE state='complete'` style commentary.

    Per Codex R2 M3: this does NOT strip multi-line docstrings or
    triple-quoted string literals. The honest scope is line-comment
    stripping only. If a non-allowed file ever contains a triple-
    quoted string literal that quotes the inline SQL pattern (e.g.,
    a docstring describing the legacy code), this helper will NOT
    catch it; the structural-guard test could surface a spurious
    offender. AT HEAD `8c7049b` no such case exists; future
    regressions of this kind are caught by manual triage when the
    structural-guard fires.
    """
    lines = []
    for line in text.splitlines():
        in_string = False
        out_chars = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "'" or ch == '"':
                in_string = not in_string
                out_chars.append(ch)
            elif ch == "#" and not in_string:
                break  # rest of line is comment
            else:
                out_chars.append(ch)
            i += 1
        lines.append("".join(out_chars))
    return "\n".join(lines)


ALLOWED_FILES: set[str] = {
    # The two shared helpers.
    "swing/web/chart_scope.py",
    "swing/web/view_models/dashboard.py",  # houses latest_evaluation_run_id
}


def _scan_swing_tree() -> dict[Path, list[int]]:
    """Return {path: [line numbers]} for every match in production source.

    For non-allowed files, comments are stripped before matching to
    eliminate false positives from comment text that quotes the SQL
    pattern. Allowed files (the helpers themselves) are scanned without
    stripping so the sanity-guard test below can verify the helpers'
    SQL still matches the regex.
    """
    swing_root = Path(__file__).resolve().parents[2] / "swing"
    matches: dict[Path, list[int]] = {}
    for py_file in swing_root.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = str(py_file.relative_to(swing_root.parent)).replace("\\", "/")
        scan_text = (
            text
            if rel in ALLOWED_FILES
            else _strip_python_line_comments(text)
        )
        for match in INLINE_QUERY_PATTERN.finditer(scan_text):
            line_no = scan_text[: match.start()].count("\n") + 1
            matches.setdefault(py_file, []).append(line_no)
    return matches


def test_no_inline_pipeline_runs_state_complete_queries_outside_helpers():
    """Production source must contain `pipeline_runs WHERE state='complete'`
    ONLY in the two helper files (chart_scope.py + view_models/dashboard.py).
    """
    matches = _scan_swing_tree()
    swing_root = Path(__file__).resolve().parents[2] / "swing"
    offenders = {
        path: lines for path, lines in matches.items()
        if str(path.relative_to(swing_root.parent)).replace("\\", "/")
        not in ALLOWED_FILES
    }
    assert not offenders, (
        "Inline `pipeline_runs WHERE state='complete'` queries found "
        "outside the two centralized helpers. Migrate to "
        "`latest_completed_pipeline_run` (pipeline-bound) or "
        "`latest_evaluation_run_id` (with-fallback) per the Phase 4 "
        "cleanup-remainder plan. Offenders:\n"
        + "\n".join(
            f"  {path}:{','.join(str(L) for L in lines)}"
            for path, lines in sorted(offenders.items())
        )
    )


def test_inline_query_pattern_actually_matches_known_helper_implementation():
    """Sanity guard: ensure the regex actually matches the SQL the
    helpers use. Without this, a typo in INLINE_QUERY_PATTERN would
    let the structural-guard pass vacuously.
    """
    swing_root = Path(__file__).resolve().parents[2] / "swing"
    chart_scope_text = (swing_root / "web" / "chart_scope.py").read_text(
        encoding="utf-8",
    )
    dashboard_text = (swing_root / "web" / "view_models" / "dashboard.py").read_text(
        encoding="utf-8",
    )
    assert INLINE_QUERY_PATTERN.search(chart_scope_text), (
        "Pattern regression: INLINE_QUERY_PATTERN does not match the "
        "SQL inside latest_completed_pipeline_run. Fix the regex."
    )
    assert INLINE_QUERY_PATTERN.search(dashboard_text), (
        "Pattern regression: INLINE_QUERY_PATTERN does not match the "
        "SQL inside latest_evaluation_run_id. Fix the regex."
    )
