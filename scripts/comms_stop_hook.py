"""Stop hook: continue-on-unread for a director session (B-14 — continuous-ops bridge).

Stdlib-only. Wired via the tracked .claude/settings.json `Stop` hook so a director
CC session (CHARC / RD) that finishes a turn with UNREAD comms mail CONTINUES to
process it -- a message that arrived mid-turn surfaces at turn-close rather than
waiting for the operator's next prompt. This approximates continuous ops absent an
idle-wake feature (Stage 3, explicitly held). It stays operator-SESSION-bounded
(it only fires when a turn ends; it is NOT an autonomous timer wake) and is
consistent with the comms taxonomy (autonomously processing fyi/status/return_report
is in-lane; dispatch authority stays operator-hand-carried).

Contract:
  * Reads SWING_ROLE from env. If unset or not in {charc, rd} -> SILENT no-op
    (exit 0): does nothing in any orchestrator / plain / ad-hoc session.
  * Reads the Stop-hook JSON payload from stdin (RAW BYTES, decoded utf-8-sig so a
    leading BOM is stripped regardless of the console codepage) for
    `stop_hook_active`.
    LOOP-SAFETY (load-bearing): it blocks (continues) ONLY when there is unread AND
    `stop_hook_active` is false -- so a turn gets AT MOST ONE continuation, and a
    stuck/undrained inbox can NEVER run the agent in an unbounded loop. On ANY
    stdin read/decode/parse failure the active-flag DEFAULTS TRUE (allow stop) --
    the safe direction, never the loop direction. The agent drains via
    `role_mail read --all` each cycle, so the natural terminator is an empty inbox.
  * On block: prints {"decision":"block","reason":<notice>} to stdout (the
    Stop-hook block protocol) so the agent continues + sees the unread.
  * Otherwise exits 0 (allow stop / idle).
  * ALWAYS degrades to exit 0 on ANY error -- a hook failure must NEVER trap the
    agent in a non-stoppable state.

Output JSON is ASCII (Windows cp1252 stdout); message files read as UTF-8.
"""

from __future__ import annotations

import json
import os
import sys

# Sibling import: when run as `python scripts/comms_stop_hook.py`, sys.path[0] is
# this file's dir, so the shared role-gating + unread-notice logic resolves.
from comms_unread_hook import (
    DIRECTOR_ROLES,
    comms_root_default,
    unread_notice,
)


def _stop_hook_active_from_stdin() -> bool:
    """Parse `stop_hook_active` from the Stop-hook JSON on stdin.

    Reads RAW BYTES and decodes utf-8-sig so a leading UTF-8 BOM is stripped no
    matter how the spawning shell/console encodes the pipe. On ANY failure to read,
    decode, or parse, returns TRUE -- the SAFE default: treat the stop as already a
    continuation so the hook ALLOWS it, guaranteeing an unreadable/garbled payload
    can NEVER trap the agent in an unbounded continue loop (the dangerous
    direction). A clean payload with the key absent yields False -- a genuine first
    stop, so the single bounded continuation is allowed.
    """
    try:
        data = sys.stdin.buffer.read()
    except Exception:  # noqa: BLE001
        return True  # SAFE: cannot read stdin -> allow stop (no loop)
    try:
        cleaned = data.decode("utf-8-sig", errors="replace").strip()
    except Exception:  # noqa: BLE001
        return True  # SAFE: undecodable -> allow stop (no loop)
    if not cleaned:
        return True  # SAFE: empty payload -> allow stop (no loop)
    try:
        return bool(json.loads(cleaned).get("stop_hook_active", False))
    except Exception:  # noqa: BLE001
        return True  # SAFE: garbled payload -> allow stop (no loop)


def main() -> int:
    try:
        role = os.environ.get("SWING_ROLE", "")
        if role not in DIRECTOR_ROLES:
            return 0  # no-op in every non-director session

        # LOOP-SAFETY: continue AT MOST ONCE per stop-cycle. On the continuation's
        # own stop, stop_hook_active is true -> allow stop (the agent has had its
        # one turn to drain the inbox; anything still unread surfaces on the next
        # operator prompt via the UserPromptSubmit hook).
        if _stop_hook_active_from_stdin():
            return 0

        notice = unread_notice(role, comms_root_default())
        if not notice:
            return 0  # inbox empty -> allow stop (idle)

        reason = (
            f"{notice}\n"
            "(B-14 close-hook continue-on-unread): you finished a turn with comms "
            "mail that arrived mid-turn. DRAIN it now (the role_mail read command "
            "above) and process anything actionable, then stop. This fires at most "
            "ONCE per turn; if nothing is actionable after reading, just stop."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
    except Exception:  # noqa: BLE001 -- a hook failure must never trap the agent
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
