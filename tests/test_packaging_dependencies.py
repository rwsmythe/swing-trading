"""R1: pyproject must DECLARE every runtime import, not rely on a transitive pin.

`requests` is imported directly (swing/integrations/finviz_api.py +
schwab/auth.py) but historically arrived only transitively. Declare it
explicitly so a future transitive-dependency drop cannot silently break the
runtime. This is a declaration-correctness guard (NOT a new dependency).
"""
from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - project runs on 3.11+
    import tomli as tomllib

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _declared_dependency_names() -> set[str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]
    names: set[str] = set()
    for spec in deps:
        # Strip any version/marker suffix: "requests>=2.31; python_version..."
        name = spec.split(";")[0].strip()
        for sep in ("<", ">", "=", "!", "~", "["):
            idx = name.find(sep)
            if idx != -1:
                name = name[:idx]
        names.add(name.strip().lower().replace("_", "-"))
    return names


def test_requests_is_declared_in_project_dependencies():
    assert "requests" in _declared_dependency_names(), (
        "requests is imported directly in swing/ but not declared in "
        "[project.dependencies]; add it (transitive presence is not a "
        "guaranteed pin)"
    )
