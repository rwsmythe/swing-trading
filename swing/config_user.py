"""User-config file I/O. Atomic write per CLAUDE.md cross-device-link gotcha."""
from __future__ import annotations

import contextlib
import logging
import os
import tempfile
import tomllib
from datetime import datetime as _dt  # module-level so tests can monkeypatch (Codex R4 M1)
from pathlib import Path
from typing import Any

import tomli_w

log = logging.getLogger(__name__)


def _user_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def get_user_config_path() -> Path:
    return _user_home() / "swing-data" / "user-config.toml"


def load_user_overrides() -> dict[str, Any]:
    path = get_user_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        log.warning("user-config malformed/unreadable at %s: %s — treating as empty", path, exc)
        return {}


def _existing_file_is_malformed(path: Path) -> bool:
    """True iff the file exists but cannot be parsed as TOML."""
    if not path.exists():
        return False
    try:
        with open(path, "rb") as f:
            tomllib.load(f)
        return False
    except (tomllib.TOMLDecodeError, OSError):
        return True


def write_user_overrides(overrides: dict[str, Any]) -> None:
    path = get_user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if _existing_file_is_malformed(path):
        ts = _dt.now().strftime("%Y%m%dT%H%M%S_%f")
        backup = path.with_name(f"user-config.malformed-{ts}.toml")
        counter = 0
        while backup.exists():
            counter += 1
            backup = path.with_name(
                f"user-config.malformed-{ts}_{counter}.toml"
            )
        os.replace(path, backup)  # atomic same-dir rename
        log.warning(
            "user-config malformed; backed up to %s before overwrite", backup,
        )
    fd = tempfile.NamedTemporaryFile(  # noqa: SIM115 — atomic-replace pattern manages fd lifetime via os.replace; close+rename in try, cleanup in except
        mode="wb", dir=path.parent, delete=False, suffix=".tmp",
    )
    try:
        tomli_w.dump(overrides, fd)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        os.replace(fd.name, path)
    except Exception:
        with contextlib.suppress(Exception):
            fd.close()
        with contextlib.suppress(Exception):
            Path(fd.name).unlink(missing_ok=True)
        raise


def delete_user_override(field_path: str) -> None:
    """Delete one dotted field. No-op if absent. Empties trailing sections.

    Supports N-part dotted paths (e.g. ``integrations.schwab.client_id``).
    After leaf deletion, prunes empty parent tables bottom-up so the resulting
    TOML stays clean (matches the existing 2-part semantics).

    Phase 12 Sub-bundle B T-B.3 — generalized from 2-part-only (which raised
    `ValueError("field_path must be 'section.key'")`) to N-part to support
    `swing config reset integrations.schwab.client_id`.
    """
    parts = field_path.split(".")
    if len(parts) < 2:
        raise ValueError(
            f"field_path must be 'section.key[.subkey...]'; got {field_path!r}"
        )
    overrides = load_user_overrides()
    # Walk down to the leaf parent table, recording the chain so we can prune
    # empty intermediate tables bottom-up on the way out. No-op if any link
    # in the chain is missing or not a dict.
    chain: list[tuple[dict, str]] = []
    cursor: object = overrides
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            return
        chain.append((cursor, part))
        cursor = cursor[part]
    if not isinstance(cursor, dict) or parts[-1] not in cursor:
        return
    del cursor[parts[-1]]
    # Bottom-up prune of empty parents (chain is parent→key tuples).
    for parent, key in reversed(chain):
        if not parent[key]:
            del parent[key]
        else:
            break
    write_user_overrides(overrides)
