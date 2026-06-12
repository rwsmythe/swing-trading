"""UserPromptSubmit hook: surface unread comms mail for a director session.

Stdlib-only. Wired via the tracked .claude/settings.json so a director CC
session (CHARC / RD) self-surfaces its unread file-mailbox on the operator's
next prompt -- the on-demand, activity-gated half of comms Stage 1.5 (NO
autonomous wake; that is Stage 3, explicitly held).

Contract:
  * Reads SWING_ROLE from the environment. If unset or not in {charc, rd} the
    hook is a SILENT no-op (exit 0) -- so it does nothing in any orchestrator,
    plain VS Code, or ad-hoc session (the seeded-gate-masks-default discipline:
    the quiet default is the common case and is witnessed at the gate).
  * Resolves the repo root from __file__ (NOT cwd), counts comms/<role>/inbox/
    *.md, and on a nonzero count prints ONE ASCII line naming the count, the
    decision_request subset, and the drain command.
  * ALWAYS exits 0. A hook failure must NEVER block the operator's prompt, so
    any internal exception is swallowed to a silent exit 0.

Output is ASCII (Windows cp1252 stdout); message files are read as UTF-8.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DIRECTOR_ROLES = ("charc", "rd")


def comms_root_default() -> Path:
    """The comms/ tree resolved from this file's location (NOT cwd)."""
    return Path(__file__).resolve().parent.parent / "comms"


def _is_decision_request(path: Path) -> bool:
    """True if the message's frontmatter type is decision_request.

    Reads only the leading frontmatter block; degrades to False on any error.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    rest = text.split("\n", 1)[1] if "\n" in text else ""
    for line in rest.split("\n"):
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.startswith("type:"):
            return stripped.split(":", 1)[1].strip() == "decision_request"
    return False


def unread_notice(role: str, comms_root: Path) -> str | None:
    """One ASCII notice line for role's unread inbox, or None if there is none.

    Pure (takes the root explicitly) so it is testable over a tmp tree.
    """
    inbox = comms_root / role / "inbox"
    if not inbox.is_dir():
        return None
    msgs = sorted(inbox.glob("*.md"))
    if not msgs:
        return None
    dr = sum(1 for m in msgs if _is_decision_request(m))
    dr_note = f" ({dr} decision_request)" if dr else ""
    return (
        f"[comms] {len(msgs)} unread for {role}{dr_note} -- run: "
        f"python scripts/role_mail.py read --role {role} --all"
    )


def main() -> int:
    try:
        role = os.environ.get("SWING_ROLE", "")
        if role not in DIRECTOR_ROLES:
            return 0  # no-op in every non-director session
        notice = unread_notice(role, comms_root_default())
        if notice:
            print(notice)
    except Exception:  # noqa: BLE001 -- a hook failure must never block a prompt
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
