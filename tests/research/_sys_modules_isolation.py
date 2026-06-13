"""sys.modules snapshot/restore helpers for the research-suite isolation fixture.

Kept in a plain module (not ``conftest.py``) so tests can import the helpers
without importing the conftest module object directly -- pytest loads conftest
through its own plugin machinery, and a second normal import of it can create a
distinct module identity under some import modes (Codex 17-D.4 review R2 minor).

See ``tests/research/conftest.py`` for the autouse fixture and the full 17-D.4
rationale. Summary: research L2-LOCK tests RAW-delete ``swing.*`` modules from
``sys.modules`` (``del`` / ``pop``) without restoring; the next import rebuilds
them as NEW objects with NEW class identities, breaking ``except``/``isinstance``
in web routes that bound the OLD classes earlier -> nondeterministic ``-n auto``
web-route failures. These helpers restore the ``swing.*`` graph at each research
test's teardown.
"""
from __future__ import annotations

import contextlib
import sys
from types import ModuleType


def _swing_module_snapshot() -> dict[str, ModuleType]:
    """Snapshot the current ``swing.*`` entries in ``sys.modules`` (incl. the
    top-level ``swing`` package)."""
    return {
        name: mod
        for name, mod in sys.modules.items()
        if name == "swing" or name.startswith("swing.")
    }


def _restore_swing_modules(snapshot: dict[str, ModuleType]) -> None:
    """Restore ``swing.*`` ``sys.modules`` entries (and parent-package attributes)
    to the snapshot objects.

    Two passes:

      1. For every snapshot key whose current value is no longer the original
         object (deleted -> absent, or replaced -> different object), put the
         original object back into ``sys.modules``.
      2. For EVERY snapshot key (not only those restored in pass 1), if the parent
         package's child attribute no longer points at the original module, reset
         it. Iterating the full snapshot -- rather than only pass-1 restorations --
         repairs a stale parent attribute even when ``sys.modules[name]`` was
         already restored to the original by another teardown (e.g.
         ``monkeypatch.delitem``) that ran before this helper, where a re-import
         left ``getattr(parent, child)`` pointing at the now-discarded new module
         (Codex 17-D.4 review R2 major). The parent attribute is repaired so
         attribute-style access agrees with ``sys.modules``.

    Keys added during the test, and all non-``swing.*`` keys, are left untouched.
    """
    # Pass 1: sys.modules entries.
    for name, original in snapshot.items():
        if sys.modules.get(name) is not original:
            sys.modules[name] = original
    # Pass 2: parent-package attributes (across the full snapshot).
    for name, original in snapshot.items():
        parent_name, _, child = name.rpartition(".")
        if not parent_name:
            continue
        parent = sys.modules.get(parent_name)
        if parent is not None and getattr(parent, child, None) is not original:
            # A non-package parent (or read-only attribute) cannot carry the
            # submodule attribute; the sys.modules restore in pass 1 is the
            # load-bearing repair, so the attribute fix is best-effort.
            with contextlib.suppress(AttributeError, TypeError):
                setattr(parent, child, original)
