"""Pytest plugin for the Codex implementer lane's Windows sandbox -- loaded ONLY by `-p`.

The Codex cell runs the suite inside `codex exec -s workspace-write` with
`windows.sandbox="unelevated"`: a RESTRICTED token of the real user. Python >= 3.13 on
Windows turns `os.mkdir(path, 0o700)` into a protected owner-only DACL (SYSTEM,
Administrators, OWNER RIGHTS; no inheritance) that omits the sandbox's restricting SIDs, so
the sandbox can neither list nor write a 0o700 directory -- not even one it just created.
pytest makes every temp root at 0o700 (`pytest-of-<user>`, `--basetemp`, numbered dirs,
xdist per-worker dirs), and stdlib `tempfile.mkdtemp` does the same.

This plugin maps a mode of exactly 0o700 to the default 0o777 in `os.mkdir`, so a new
directory inherits its parent's ACL, which already carries the sandbox's grants. Wrapping
`os.mkdir` covers `Path.mkdir`, `os.makedirs` and `tempfile.mkdtemp`, which all resolve
`os.mkdir` at call time. It does not repair a 0o700 root created earlier outside the
sandbox, so the cell's command also passes a fresh `--basetemp` under `%TEMP%`.

Loading rule (CHARC ruling D-c, 2026-11-11): ONLY the Codex cell's test command loads this,
with `-p tests.codex_sandbox_tmp`. Never addopts, never a conftest `pytest_plugins`, never an
import-time side effect: importing this module wraps nothing; only `pytest_configure`
installs. `tests/test_codex_sandbox_tmp.py::test_plugin_loads_only_by_an_explicit_dash_p`
fails the gate run if that ever changes. Stage-0 evidence:
~/swing-data/review-transcripts/codex-lane/stage0-ledger.md, probe 3.
"""

from __future__ import annotations

import functools
import os
from typing import Any

MARKER = "_codex_sandbox_widened"
RESTRICTED_MODE = 0o700
DEFAULT_MODE = 0o777


def widen_mode(mode: int) -> int:
    """Return the default mode for exactly 0o700; any other mode is unchanged."""
    return DEFAULT_MODE if mode == RESTRICTED_MODE else mode


def wrap_mkdir(original: Any) -> Any:
    """Wrap an `os.mkdir`-shaped callable so a 0o700 mode reaches it as 0o777."""

    @functools.wraps(original)
    def mkdir(path: Any, mode: int = DEFAULT_MODE, *, dir_fd: Any = None) -> Any:
        return original(path, widen_mode(mode), dir_fd=dir_fd)

    setattr(mkdir, MARKER, True)
    return mkdir


def install(os_module: Any = os) -> bool:
    """Wrap `os_module.mkdir` on Windows, once. Returns True only when it installed."""
    if os_module.name != "nt":
        return False
    if getattr(os_module.mkdir, MARKER, False):
        return False
    os_module.mkdir = wrap_mkdir(os_module.mkdir)
    return True


def pytest_configure(config: Any) -> None:
    """Install before any temp directory exists (controller and every xdist worker)."""
    install()
