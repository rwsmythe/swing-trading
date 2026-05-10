"""User-config file I/O. Atomic write per CLAUDE.md cross-device-link gotcha."""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import datetime as _dt  # module-level so tests can monkeypatch (Codex R4 M1)
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib
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
    fd = tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, delete=False, suffix=".tmp",
    )
    try:
        tomli_w.dump(overrides, fd)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        os.replace(fd.name, path)
    except Exception:
        try:
            fd.close()
        except Exception:
            pass
        try:
            Path(fd.name).unlink(missing_ok=True)
        except Exception:
            pass
        raise


def delete_user_override(field_path: str) -> None:
    """Delete one dotted field. No-op if absent. Empties trailing sections."""
    overrides = load_user_overrides()
    parts = field_path.split(".")
    if len(parts) != 2:
        raise ValueError(f"field_path must be 'section.key'; got {field_path!r}")
    section, key = parts
    if section not in overrides or key not in overrides[section]:
        return
    del overrides[section][key]
    if not overrides[section]:
        del overrides[section]
    write_user_overrides(overrides)
