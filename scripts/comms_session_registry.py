"""Single-sourced orchestrator session registry (G6 Arc A).

Pure, stdlib-only, clock-injected. The ONE owner of the registry read/write/
prune + newest-live resolution + the per-generation path shape + the
``session_id`` safety rule. Imported by the lifecycle hook
(``comms_session_hook.py``) and by ``role_mail.py``; imports NOTHING from
role_mail (one-way dependency -- no import cycle).

Registry layout (ONE FILE PER SESSION -- no shared-map write contention):
    comms/sessions/<session_id>.json   {session_id, role, transcript_path,
                                        started_ts, last_seen}
Per-generation orchestrator inbox (the rotating role gets a per-gen box, never
a singular one):
    comms/orchestrator/<session_id>/{inbox,read}

Liveness = the hook-written ``last_seen`` heartbeat (refreshed each
UserPromptSubmit). Staleness = ``last_seen`` age past ``STALE_SECONDS``. NO pure
function calls ``datetime.now()`` -- every time-comparing function takes an
injectable ``now`` (debt D9: freezable staleness, no wall-clock test flake).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# Staleness threshold (single named, operator/CHARC-tunable constant). The
# Stage-2 design suggests 30-60 min; default 45 min.
STALE_SECONDS = 45 * 60

# Sessions whose SWING_ROLE is registered (brief section 4: register the
# directors too so the future GUI bus + newest-live both work).
REGISTRABLE_ROLES = ("charc", "rd", "orchestrator")

# Only orchestrator entries are newest_live-eligible -- the orchestrator is the
# SOLE rotating/per-gen role; charc/rd are singular and need no liveness target.
NEWEST_LIVE_ROLE = "orchestrator"

# The launch-time role env var (swing's existing name, used by the unread hook).
ROLE_ENV = "SWING_ROLE"

# A session_id becomes a directory name under comms/orchestrator/ AND a filename
# under comms/sessions/, so it MUST be a safe single path segment. This is THE
# shared validation rule for the whole registry layer; every path-building site
# (entry_path, per_generation_inbox/read, the hook) and every consumer of a
# registry-JSON session_id (read_entries, newest_live) AND role_mail's
# :<session_id> form go through is_valid_session_id -- one rule, no second copy.
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9._-]+")


def is_valid_session_id(session_id) -> bool:  # noqa: ANN001
    """True iff session_id is a safe single path segment (no traversal/seps)."""
    if not isinstance(session_id, str) or not session_id:
        return False
    if session_id in (".", ".."):
        return False
    if "/" in session_id or "\\" in session_id:
        return False
    if session_id != Path(session_id).name:
        return False
    return bool(_SESSION_ID_RE.fullmatch(session_id))


# --- path helpers (each validates session_id before building a path) --------

def comms_root_from_file() -> Path:
    """The comms/ tree resolved from THIS file's location (NOT cwd).

    scripts/comms_session_registry.py -> the repo root is one parent up from
    scripts/. Resolving from __file__ makes the registry correct from any cwd.
    """
    return Path(__file__).resolve().parent.parent / "comms"


def sessions_dir(root: Path) -> Path:
    return root / "sessions"


def entry_path(root: Path, session_id: str) -> Path:
    if not is_valid_session_id(session_id):
        raise ValueError(f"unsafe session_id {session_id!r}")
    return sessions_dir(root) / f"{session_id}.json"


def per_generation_inbox(root: Path, session_id: str) -> Path:
    """The per-generation orchestrator inbox dir for a session_id."""
    if not is_valid_session_id(session_id):
        raise ValueError(f"unsafe session_id {session_id!r}")
    return root / "orchestrator" / session_id / "inbox"


def per_generation_read(root: Path, session_id: str) -> Path:
    """The per-generation orchestrator read (ack archive) dir for a session_id."""
    if not is_valid_session_id(session_id):
        raise ValueError(f"unsafe session_id {session_id!r}")
    return root / "orchestrator" / session_id / "read"


def ensure_per_generation_inbox(root: Path, session_id: str) -> Path:
    """Idempotently create comms/orchestrator/<session_id>/{inbox,read}."""
    inbox = per_generation_inbox(root, session_id)
    inbox.mkdir(parents=True, exist_ok=True)
    per_generation_read(root, session_id).mkdir(parents=True, exist_ok=True)
    return inbox


def _atomic_write_text(path: Path, content: str) -> None:
    """Write content to `path` atomically (stage a same-dir temp + os.replace).

    INTENTIONAL COPY -- keep in sync; twin in scripts/role_mail.py:_write_temp.
    Kept local (NOT a cross-import) to preserve role_mail's core-mail path from a
    load dependency on the registry module (the singular-mail-never-depends-on-
    registry blast-radius principle). The temp is staged in `path`'s OWN
    directory so the os.replace is same-filesystem-atomic (the Windows
    os.replace cross-volume gotcha). A reader never observes a torn intermediate
    at `path`; a staging/replace failure cleans up the temp and leaves any prior
    file at `path` intact (os.replace is the single atomic commit point).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
    try:
        os.replace(tmp_name, str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


# --- registry read/write/prune (pure, clock-injected) ----------------------

def write_entry(root: Path, session_id: str, role: str, transcript_path: str,
                now: datetime, started_ts: str | None = None) -> Path:
    """Create / overwrite the full registry entry for a session.

    Writes all five fields. ``started_ts`` is preserved across refreshes if the
    caller passes it (else stamped from ``now``). The full-entry write is what
    makes recreate-if-missing self-healing: the hook owns every field (role from
    env, ids from the payload), so a rebuilt file is complete.
    """
    started = started_ts if started_ts is not None else now.isoformat()
    payload = {
        "session_id": session_id,
        "role": role,
        "transcript_path": transcript_path,
        "started_ts": started,
        "last_seen": now.isoformat(),
    }
    path = entry_path(root, session_id)  # validates session_id
    _atomic_write_text(path, json.dumps(payload))
    return path


def read_entry(root: Path, session_id: str) -> dict | None:
    """One entry by session_id, or None (malformed -> None, never raises)."""
    path = entry_path(root, session_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_entries(root: Path) -> list[dict]:
    """All well-formed registry entries (malformed files are SKIPPED).

    The degrade-gracefully posture: a garbage sessions/<id>.json never breaks a
    read -- it is skipped, and the good entries are returned. Enforces the
    registry identity invariant (filename == embedded-id): an entry is included
    ONLY if its embedded session_id is well-formed/safe AND equals the file stem
    -- so a crafted / inconsistent file can never mis-route a bare
    `--to orchestrator` to a wrong per-generation inbox.
    """
    sessions = sessions_dir(root)
    if not sessions.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(sessions.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (isinstance(data, dict)
                and is_valid_session_id(data.get("session_id"))
                and data.get("session_id") == path.stem):
            out.append(data)
    return out


def touch_last_seen(root: Path, session_id: str, now: datetime, *,
                    role: str | None = None,
                    transcript_path: str | None = None) -> Path:
    """Refresh last_seen (the heartbeat); recreate-if-missing self-heal.

    If the entry exists, only last_seen changes (started_ts + role preserved).
    If it was pruned away, the entry is REBUILT in full -- which needs the role
    (and a transcript_path); the caller supplies them from env + payload. A bare
    touch with no role on a missing entry cannot rebuild and raises (the caller
    must pass role for self-heal).
    """
    existing = read_entry(root, session_id)
    if existing is not None:
        existing["last_seen"] = now.isoformat()
        path = entry_path(root, session_id)
        _atomic_write_text(path, json.dumps(existing))
        return path
    if role is None:
        raise ValueError(
            "touch_last_seen cannot recreate a pruned entry without role")
    return write_entry(root, session_id, role, transcript_path or "", now)


def _age_seconds(entry: dict, now: datetime) -> float | None:
    raw = entry.get("last_seen")
    if not raw:
        return None
    try:
        seen = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    return (now - seen).total_seconds()


def prune_stale(root: Path, now: datetime,
                stale_seconds: int = STALE_SECONDS) -> list[str]:
    """Delete entries whose last_seen age exceeds the threshold; return ids.

    A malformed entry (unparseable last_seen) is treated as stale and pruned (it
    cannot prove liveness). Best-effort: an unremovable file is skipped.
    """
    pruned: list[str] = []
    sessions = sessions_dir(root)
    if not sessions.is_dir():
        return pruned
    for path in sorted(sessions.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        age = _age_seconds(data, now) if isinstance(data, dict) else None
        if age is None or age > stale_seconds:
            try:
                path.unlink()
                pruned.append(path.stem)
            except OSError:
                continue
    return pruned


def live_entries(root: Path, now: datetime,
                 stale_seconds: int = STALE_SECONDS) -> list[dict]:
    """Non-stale newest_live-eligible (orchestrator) entries; does NOT mutate."""
    out: list[dict] = []
    for entry in read_entries(root):
        if entry.get("role") != NEWEST_LIVE_ROLE:
            continue
        age = _age_seconds(entry, now)
        if age is not None and age <= stale_seconds:
            out.append(entry)
    return out


def _started_sort_key(entry: dict) -> tuple[int, datetime, str]:
    """Sort key for newest_live: (valid-flag, parsed started_ts, session_id).

    A malformed/unparseable started_ts is DEPRIORITIZED (flag=0, datetime.min)
    so a garbage string can never win "newest" by raw lexicographic comparison.
    The trailing session_id is a DETERMINISTIC final tiebreaker: an exact
    started_ts tie (or the all-malformed case) resolves to the lexically
    GREATEST session_id -- a single stable entry, never a max()-order flake.
    This lexical-greatest tie policy is pinned by the newest_live tie test; do
    NOT change it without updating that oracle.
    """
    sid = entry.get("session_id")
    sid = sid if isinstance(sid, str) else ""
    raw = entry.get("started_ts")
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return (0, datetime.min.replace(tzinfo=UTC), sid)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return (1, parsed, sid)
    return (0, datetime.min.replace(tzinfo=UTC), sid)


def newest_live(root: Path, now: datetime,
                stale_seconds: int = STALE_SECONDS) -> dict | None:
    """The newest-live orchestrator entry (max started_ts), or None.

    "Newest" = the max started_ts among non-stale orchestrator entries (the
    target a bare `--to orchestrator` resolves to). None when none are live. A
    malformed started_ts is deprioritized (datetime-parsed, never raw-sorted),
    so a single garbage entry cannot hijack the resolution.
    """
    live = live_entries(root, now, stale_seconds)
    if not live:
        return None
    return max(live, key=_started_sort_key)
