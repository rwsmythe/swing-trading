"""Phase 10 verification suite — cross-platform executing-plans acceptance gate.

Per plan §J.2 (Codex R1 Major #7 fix — rewritten from Bash-only to Python
so the script runs on Windows PowerShell, gitbash, or POSIX). Invoke from
worktree root via ``python verify_phase10.py``.

Sub-bundle A lands this script; subsequent sub-bundles inherit + extend
with their own sanity grep checks.
"""

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent

# 1. ZERO new migration
unexpected = list((ROOT / "swing/data/migrations").glob("0018_*.sql"))
assert not unexpected, f"FAIL: unexpected migration {unexpected}"

# 2. EXPECTED_SCHEMA_VERSION still 17
sys.path.insert(0, str(ROOT))
from swing.data.db import EXPECTED_SCHEMA_VERSION  # noqa: E402
assert EXPECTED_SCHEMA_VERSION == 17, EXPECTED_SCHEMA_VERSION

# 3. Module placement
required = [
    "swing/metrics/__init__.py",
    "swing/web/view_models/metrics/__init__.py",
    "swing/web/routes/metrics.py",
    "swing/web/templates/metrics/index.html.j2",
]
for p in required:
    assert (ROOT / p).exists(), f"FAIL: missing {p}"

# 4. NO INSERT OR REPLACE — broad scope across ALL Phase 10 modified + created files
PHASE10_SCOPE = [
    "swing/metrics",
    "swing/web/view_models/metrics",
    "swing/web/routes/metrics.py",
    "swing/web/templates/metrics",
    # MODIFIED shared files per §B (broaden per Codex R1 Major #7):
    "swing/web/view_models/dashboard.py",
    "swing/web/view_models/pipeline.py",
    "swing/web/view_models/journal.py",
    "swing/web/view_models/watchlist.py",
    "swing/web/view_models/config.py",
    "swing/web/view_models/error.py",
    "swing/web/templates/base.html.j2",
]
pattern = re.compile(r"INSERT\s+OR\s+REPLACE|\bREPLACE\s+INTO\b", re.IGNORECASE)
violations = []
for scope in PHASE10_SCOPE:
    target = ROOT / scope
    paths = [target] if target.is_file() else target.rglob("*")
    for p in paths:
        if not p.is_file() or p.suffix not in (".py", ".sql", ".j2"):
            continue
        text = p.read_text(encoding="utf-8")
        if pattern.search(text):
            violations.append(str(p.relative_to(ROOT)))
assert not violations, f"FAIL: INSERT OR REPLACE found in: {violations}"

# 5. base-layout VM coverage regression test
result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "tests/web/test_view_models/test_base_layout_vm_coverage.py",
     "-v", "--tb=short"],
    cwd=ROOT, capture_output=True, text=True,
)
assert result.returncode == 0, (
    f"FAIL: base-layout VM coverage regression\n"
    f"{result.stdout}\n{result.stderr}"
)

# 6. Per-bundle integration tests
for bundle in ("a", "b", "c", "d", "e"):
    test_file = ROOT / f"tests/integration/test_phase10_bundle_{bundle}_e2e.py"
    if test_file.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file),
             "-v", "--tb=short"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"FAIL: bundle {bundle} E2E\n{result.stdout}\n{result.stderr}"
        )

# 7. Combined Phase 10 E2E
combined = ROOT / "tests/integration/test_phase10_metrics_e2e.py"
if combined.exists():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(combined),
         "-v", "--tb=short"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"FAIL: combined E2E\n{result.stdout}\n{result.stderr}"
    )

# 8. Ruff baseline still 18 (E501 only)
result = subprocess.run(
    ["ruff", "check", "swing/"], cwd=ROOT, capture_output=True, text=True,
)
# ruff exits 1 when issues found; that's expected at baseline 18
match = re.search(r"Found (\d+) errors?\.", result.stdout + result.stderr)
assert match is not None, (
    f"FAIL: ruff output not parseable: {result.stdout}\n{result.stderr}"
)
count = int(match.group(1))
assert count == 18, f"FAIL: ruff baseline drift {count} != 18"

print("OK: Phase 10 verification suite passed")
