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
  * Reads the Stop-hook JSON payload from stdin (RAW BYTES, decoded STRICT
    utf-8-sig so a leading BOM is stripped regardless of the console codepage)
    for `stop_hook_active`.
    LOOP-SAFETY (load-bearing, hardened 2026-07 -- back-port of the
    harness-template scaffold's Arc-C Codex-converged Stop hook, docs/reviews/
    comms-gui-resync-arc-c-executing-codex-findings.md): it blocks (continues)
    ONLY when there is unread AND `stop_hook_active` is EXACTLY the boolean
    `False` -- so a turn gets AT MOST ONE continuation, and a stuck/undrained
    inbox can NEVER run the agent in an unbounded loop. Every ambiguous case
    ALLOWS the stop (the safe, fail-open direction): a strict-decode failure
    (including invalid UTF-8, never salvaged via `errors="replace"`, which
    could resurrect a stale `false` from a byte-damaged payload), an empty/
    garbled/non-dict payload, a MISSING `stop_hook_active` key, and any
    present-but-non-boolean falsey value (`None`/`0`/`""`/`[]`) all allow the
    stop -- identity (`is not False`), never truthiness, so a substrate that
    ever drops, renames, or non-boolean-ifies the field can never loop on a
    stuck inbox. The agent drains via `role_mail read --all` each cycle, so
    the natural terminator (on a genuine first stop) is an empty inbox.
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
from pathlib import Path

# Sibling import: when run as `python scripts/comms_stop_hook.py`, sys.path[0] is
# this file's dir, so the shared role-gating + unread-notice logic resolves.
from comms_unread_hook import (
    DIRECTOR_ROLES,
    comms_root_default,
    unread_notice,
)


def _parse_stop_payload(raw: bytes) -> dict:
    """Parse the Stop-hook JSON payload bytes into a dict.

    Decodes STRICT utf-8-sig (a leading BOM is stripped no matter how the
    spawning shell/console encodes the pipe) -- deliberately NOT
    `errors="replace"`: salvaging a byte-corrupted payload could resurrect a
    stale `stop_hook_active: false` from a damaged body and wrongly block (the
    exact defect the Arc-C codex-auto-review caught). On ANY decode/parse
    failure, or a non-dict payload, returns {"stop_hook_active": True} -- the
    SAFE sentinel: treat the stop as already a continuation so the hook ALLOWS
    it, guaranteeing an unreadable/garbled payload can NEVER trap the agent in
    an unbounded continue loop. An empty/whitespace-only payload is likewise
    allow-stop. A clean dict payload is returned as-is; `_stop_hook_active`
    then defaults a MISSING key to allow-stop (the same safe direction) so a
    genuine first stop (the documented payload carries the flag explicitly
    `false`) still yields the one bounded continuation.
    """
    try:
        cleaned = raw.decode("utf-8-sig").strip()
    except Exception:  # noqa: BLE001
        return {"stop_hook_active": True}  # SAFE: undecodable -> allow stop
    if not cleaned:
        return {"stop_hook_active": True}  # SAFE: empty payload -> allow stop
    try:
        data = json.loads(cleaned)
    except Exception:  # noqa: BLE001
        return {"stop_hook_active": True}  # SAFE: garbled payload -> allow stop
    return data if isinstance(data, dict) else {"stop_hook_active": True}


def _stop_hook_active(payload: dict) -> bool:
    """True (allow stop) UNLESS `stop_hook_active` is EXACTLY boolean False.

    The documented Stop-hook contract carries an explicit boolean (false on a
    genuine first stop, true on the continuation's own stop). Block-once
    happens ONLY on an exact `false`; a MISSING key OR any present-but-non-
    boolean value (null/None, 0, "", a list) is ambiguous -- the hook cannot
    distinguish a first stop from an Nth continuation -- so it allow-stops
    (the safe, fail-open direction). Identity `is not False` -- not
    truthiness -- so the int 0 / empty string / None / [] never count as the
    boolean false.
    """
    return payload.get("stop_hook_active", True) is not False


def handle_stop(payload: dict, env: dict, root: Path) -> str | None:
    """Return the block-reason string for a gated session with unread mail, else None.

    Separated from main() for unit-testability over a tmp comms root. Pure
    (takes payload/env/root explicitly). Returns None whenever the stop should
    be ALLOWED (non-director role, the single-continuation guard, or an empty
    inbox); returns the drain-instruction reason ONLY on a first stop (exact
    `stop_hook_active: False`) with unread mail.
    """
    role = env.get("SWING_ROLE", "")
    if role not in DIRECTOR_ROLES:
        return None  # no-op in every non-director session

    # LOOP-SAFETY: continue AT MOST ONCE per stop-cycle. On the continuation's
    # own stop, stop_hook_active is true -> allow stop (the agent has had its
    # one turn to drain the inbox; anything still unread surfaces on the next
    # operator prompt via the UserPromptSubmit hook).
    if _stop_hook_active(payload):
        return None

    notice = unread_notice(role, root)
    if not notice:
        return None  # inbox empty -> allow stop (idle)

    return (
        f"{notice}\n"
        "(B-14 close-hook continue-on-unread): you finished a turn with comms "
        "mail that arrived mid-turn. DRAIN it now (the role_mail read command "
        "above) and process anything actionable, then stop. This fires at most "
        "ONCE per turn; if nothing is actionable after reading, just stop."
    )


def main() -> int:
    try:
        try:
            raw = sys.stdin.buffer.read()
        except Exception:  # noqa: BLE001 -- cannot read stdin -> allow stop
            raw = b""
        payload = _parse_stop_payload(raw)
        reason = handle_stop(payload, dict(os.environ), comms_root_default())
        if reason is not None:
            print(json.dumps({"decision": "block", "reason": reason}))
    except Exception:  # noqa: BLE001 -- a hook failure must never trap the agent
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
