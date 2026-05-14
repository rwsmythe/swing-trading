"""T-A.1: assert installed schwabdev version satisfies the pyproject.toml pin.

Phase 11 Schwab API integration Sub-bundle A. The plan pins
``schwabdev>=2.4.0,<3.0.0`` in ``pyproject.toml`` so synthesized signatures in
the reconciliation doc (``docs/schwab-bundle-A-task-A0b-recon.md``) stay
aligned with the runtime library surface. This test guards against silent
drift if a future ``pip install`` resolves to a version outside the pin.

schwabdev 2.5.x does NOT expose ``schwabdev.__version__`` as a module
attribute, so we read the installed-distribution version via
``importlib.metadata.version`` (PEP 566; stdlib since Python 3.8).
"""

from __future__ import annotations

from importlib import metadata


_LOWER_INCLUSIVE = (2, 4, 0)
_UPPER_EXCLUSIVE = (3, 0, 0)


def _parse_version(raw: str) -> tuple[int, int, int]:
    """Parse a dotted version string into a 3-tuple of integers.

    Tolerates extra components (e.g. ``2.5.1.dev0``) by truncating to the
    first three numeric segments. Raises ``ValueError`` if the first three
    segments are not all integers.
    """

    parts = raw.split(".")
    if len(parts) < 3:
        raise ValueError(f"version string {raw!r} has fewer than 3 segments")
    # Strip any pre/post/dev suffix from the third segment (e.g. "1rc2" → "1").
    third = parts[2]
    numeric_third = ""
    for ch in third:
        if ch.isdigit():
            numeric_third += ch
        else:
            break
    if not numeric_third:
        raise ValueError(f"version string {raw!r} third segment not numeric")
    return (int(parts[0]), int(parts[1]), int(numeric_third))


def test_schwabdev_installed_and_importable() -> None:
    """schwabdev must be importable; this catches a missing install outright."""

    import schwabdev  # noqa: F401  — import-only smoke check


def test_schwabdev_version_within_pin_range() -> None:
    """Installed schwabdev version must satisfy ``>=2.4.0,<3.0.0``."""

    raw = metadata.version("schwabdev")
    assert isinstance(raw, str) and raw, f"unexpected version value: {raw!r}"
    parsed = _parse_version(raw)
    assert _LOWER_INCLUSIVE <= parsed < _UPPER_EXCLUSIVE, (
        f"schwabdev=={raw} (parsed={parsed}) is outside the pyproject pin "
        f">={_LOWER_INCLUSIVE}, <{_UPPER_EXCLUSIVE}; re-record the §E "
        "signature reconciliation doc if intentionally bumping the pin."
    )
