"""Wiring test for .claude/settings.json (G6 Arc A).

Asserts the SessionStart + UserPromptSubmit-heartbeat entries for
comms_session_hook.py are present, AND the existing comms_unread_hook.py
UserPromptSubmit + comms_stop_hook.py Stop entries are still present unchanged
(the Arc-A boundary: the unread + stop hooks are UNTOUCHED).
"""

from __future__ import annotations

import json
from pathlib import Path

_SETTINGS = Path(__file__).resolve().parents[2] / ".claude" / "settings.json"


def _commands_for(event: str) -> list[str]:
    data = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    out: list[str] = []
    for block in data.get("hooks", {}).get(event, []):
        for h in block.get("hooks", []):
            if h.get("type") == "command":
                out.append(h.get("command", ""))
    return out


def test_session_start_wires_session_hook_with_session_start_arg():
    cmds = _commands_for("SessionStart")
    assert any("comms_session_hook.py" in c and c.rstrip().endswith("session-start")
               for c in cmds), cmds


def test_user_prompt_submit_wires_heartbeat():
    cmds = _commands_for("UserPromptSubmit")
    assert any("comms_session_hook.py" in c and c.rstrip().endswith("heartbeat")
               for c in cmds), cmds


def test_existing_unread_hook_still_wired_unchanged():
    cmds = _commands_for("UserPromptSubmit")
    assert any("comms_unread_hook.py" in c for c in cmds), cmds


def test_existing_stop_hook_still_wired_unchanged():
    cmds = _commands_for("Stop")
    assert any("comms_stop_hook.py" in c for c in cmds), cmds


def test_session_hook_commands_use_absolute_quoted_python_form():
    for event, suffix in (("SessionStart", "session-start"),
                          ("UserPromptSubmit", "heartbeat")):
        for c in _commands_for(event):
            if "comms_session_hook.py" in c and c.rstrip().endswith(suffix):
                # python "C:/Users/rwsmy/swing-trading/scripts/...py" <mode>
                assert c.startswith("python "), c
                assert '"C:/Users/rwsmy/swing-trading/scripts/' in c, c
                return
    raise AssertionError("no comms_session_hook command found")
