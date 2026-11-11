"""Tests for the Codex-lane sandbox pytest plugin (`tests/codex_sandbox_tmp.py`).

The plugin exists for ONE seat: a Codex implementer cell running the suite inside the
Windows `unelevated` sandbox, where a 0o700 directory (Python >= 3.13 turns that mode into
an owner-only DACL) is unreadable even to the process that created it. The cell's test
command loads it explicitly with `-p tests.codex_sandbox_tmp`; the gate command at the
dispatcher's seat never does. Stage-0 evidence and the ruling (CHARC, 2026-11-11, D-c):
~/swing-data/review-transcripts/codex-lane/stage0-ledger.md, probe 3.
"""

from __future__ import annotations

import os
import types

PLUGIN = "tests.codex_sandbox_tmp"


def _explicit_dash_p(args: list[str], name: str) -> bool:
    """True when the RAW command line named the plugin with `-p` (never via addopts)."""
    for i, arg in enumerate(args):
        if arg == "-p" and i + 1 < len(args) and args[i + 1] == name:
            return True
        if arg == f"-p{name}":
            return True
    return False


def test_widen_mode_maps_only_0o700_to_the_default():
    from tests import codex_sandbox_tmp as plugin

    assert plugin.widen_mode(0o700) == 0o777
    assert plugin.widen_mode(0o777) == 0o777
    assert plugin.widen_mode(0o755) == 0o755
    assert plugin.widen_mode(0o600) == 0o600


def test_wrapped_mkdir_hands_the_original_a_widened_mode():
    from tests import codex_sandbox_tmp as plugin

    calls = []

    def original(path, mode=0o777, *, dir_fd=None):
        calls.append((path, mode, dir_fd))

    wrapped = plugin.wrap_mkdir(original)
    wrapped("a", 0o700)
    wrapped("b")
    wrapped("c", 0o755)
    wrapped("d", mode=0o700, dir_fd=7)
    assert calls == [
        ("a", 0o777, None),
        ("b", 0o777, None),
        ("c", 0o755, None),
        ("d", 0o777, 7),
    ]
    assert getattr(wrapped, plugin.MARKER) is True


def test_install_wraps_only_on_windows_and_only_once():
    from tests import codex_sandbox_tmp as plugin

    def original(path, mode=0o777, *, dir_fd=None):
        return None

    posix = types.SimpleNamespace(name="posix", mkdir=original)
    assert plugin.install(posix) is False
    assert posix.mkdir is original

    nt = types.SimpleNamespace(name="nt", mkdir=original)
    assert plugin.install(nt) is True
    first = nt.mkdir
    assert first is not original
    assert getattr(first, plugin.MARKER) is True
    assert plugin.install(nt) is False
    assert nt.mkdir is first


def test_plugin_loads_only_by_an_explicit_dash_p(request):
    """The ruled guard (D-c): the GATE command (no `-p`) leaves os.mkdir unwrapped.

    Both modes are asserted. Without an explicit `-p tests.codex_sandbox_tmp` on the raw
    command line, the plugin must NOT be registered and os.mkdir must be the builtin --
    so an addopts / PYTEST_ADDOPTS / conftest `pytest_plugins` / import-time edit that
    makes it autoload fails here (importing the module, as the tests above do, wraps
    nothing; only its `pytest_configure` hook installs). With the explicit `-p` (the Codex
    cell's command) the plugin is registered and, on Windows, os.mkdir carries the
    widening marker. xdist workers receive the controller's raw invocation args
    (xdist 3.8.0 `workermanage.WorkerController.setup`), so this holds in every worker.
    """
    from tests import codex_sandbox_tmp as plugin

    args = [str(a) for a in request.config.invocation_params.args]
    explicit = _explicit_dash_p(args, PLUGIN)
    loaded = request.config.pluginmanager.has_plugin(PLUGIN)
    widened = bool(getattr(os.mkdir, plugin.MARKER, False))
    if not explicit:
        assert not loaded, "the sandbox plugin is registered without an explicit -p"
        assert not widened, "os.mkdir is wrapped without an explicit -p"
        assert isinstance(os.mkdir, types.BuiltinFunctionType)
    else:
        assert loaded
        assert widened is (os.name == "nt")
