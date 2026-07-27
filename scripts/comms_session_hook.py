"""Session lifecycle hook: register + heartbeat the session registry (G6 A).

Stdlib-only. Two modes via argv[1], wired in .claude/settings.json:
  * ``session-start``  (SessionStart hook): register the session (role presence
    / recovery) + opportunistically prune stale registry entries.
  * ``heartbeat``      (a SECOND UserPromptSubmit hook, alongside the existing
    comms_unread_hook): refresh the live session's last_seen. GATE-FREE -- it
    runs for any REGISTRABLE role (so an orchestrator's last_seen DOES refresh;
    there is no {charc,rd}-only gate to thread, the brief section-4 SEAM).

session_id source: PRIMARY = the hook JSON payload's ``session_id`` (the
documented Claude Code hook stdin field); degraded fallback =
``CLAUDE_CODE_SESSION_ID`` (grounded against a live Claude Code session env),
used with a logged stderr WARNING -- never silently mis-keyed.

ALWAYS exits 0: a hook must NEVER block a session / prompt. main() swallows all
exceptions to exit 0; the registry sibling-import is guarded at module load too
(a broken/missing registry degrades to a logged exit-0 no-op, never a crash).

Output is ASCII (Windows cp1252 stderr); registry files are written as UTF-8.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Sibling-hook import resilience: the import runs at module load, BEFORE main()'s
# try/except can catch anything. A broken/missing registry module would
# otherwise crash the hook process (nonzero exit -> a blocked prompt/session). So
# scripts/ is put on sys.path explicitly and the import is guarded; on failure
# the module still loads and main() degrades to a logged exit-0 no-op.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import comms_session_registry as _reg  # noqa: E402

    _REGISTRY_IMPORT_OK = True
except Exception as _import_exc:  # noqa: BLE001 -- never block a session/prompt
    _REGISTRY_IMPORT_OK = False
    _REGISTRY_IMPORT_ERR = _import_exc


def _read_payload() -> dict:
    """Parse the hook JSON from stdin; {} on any problem (degrade-gracefully).

    Defensive against pytest's no-stdin DontReadFromInput (which raises on
    .read()) and any decode/parse failure.
    """
    import json

    try:
        raw = sys.stdin.read()
    except Exception:  # noqa: BLE001
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_session_id(payload: dict, env: dict) -> str | None:
    """Resolve + validate the session_id; None (with a logged warning) if absent
    or unsafe. PRIMARY = payload['session_id']; degraded fallback = the env id.
    """
    session_id = payload.get("session_id")
    if not session_id:
        session_id = env.get("CLAUDE_CODE_SESSION_ID") or None
        if not session_id:
            return None
        print(
            "[registry] WARNING: hook payload had no session_id; DEGRADED to "
            f"the fallback env id {session_id!r}.", file=sys.stderr)
    if not _reg.is_valid_session_id(session_id):
        print(
            "[registry] WARNING: refusing unsafe session_id "
            f"{session_id!r}; not registering this generation.", file=sys.stderr)
        return None
    return session_id


def handle_session_start(payload: dict, env: dict, root: Path,
                         now: datetime) -> None:
    """The SessionStart action (separated from main() for testability).

    ALWAYS prune (reader-as-cleaner / new-session-on-entry, regardless of role);
    then, for a REGISTRABLE role, write/refresh the entry (preserving started_ts
    on resume). NO mailbox directory is created here (21-D): every role is a
    singular inbox owned by role_mail, so registration is presence-only.
    """
    _reg.prune_stale(root, now)  # ALWAYS, regardless of role

    role = env.get(_reg.ROLE_ENV, "")
    if role not in _reg.REGISTRABLE_ROLES:
        return

    session_id = _resolve_session_id(payload, env)
    if session_id is None:
        return

    transcript = payload.get("transcript_path", "")
    existing = _reg.read_entry(root, session_id)
    started = existing.get("started_ts") if existing else None
    _reg.write_entry(root, session_id, role, transcript, now,
                     started_ts=started)


def handle_heartbeat(payload: dict, env: dict, root: Path,
                     now: datetime) -> None:
    """The UserPromptSubmit heartbeat (the SEAM -- gate-free).

    Refresh last_seen for any REGISTRABLE role (recreate-if-missing self-heal).
    Presence-only: no mailbox directory is touched (21-D).
    """
    role = env.get(_reg.ROLE_ENV, "")
    if role not in _reg.REGISTRABLE_ROLES:
        return

    session_id = _resolve_session_id(payload, env)
    if session_id is None:
        return

    _reg.touch_last_seen(root, session_id, now, role=role,
                         transcript_path=payload.get("transcript_path", ""))


def main(argv: list[str] | None = None) -> int:
    if not _REGISTRY_IMPORT_OK:
        print(
            "[registry] WARNING: could not import comms_session_registry "
            f"({_REGISTRY_IMPORT_ERR!r}); skipping registration. Not blocked.",
            file=sys.stderr)
        return 0
    argv = list(sys.argv[1:]) if argv is None else argv
    mode = argv[0] if argv else ""
    try:
        payload = _read_payload()
        env = dict(os.environ)
        root = _reg.comms_root_from_file()
        now = datetime.now(UTC)
        if mode == "session-start":
            handle_session_start(payload, env, root, now)
        elif mode == "heartbeat":
            handle_heartbeat(payload, env, root, now)
        else:
            print(
                f"[registry] WARNING: unknown mode {mode!r} (expected "
                "session-start|heartbeat); no-op.", file=sys.stderr)
    except Exception:  # noqa: BLE001 -- a hook failure must never block a prompt
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
