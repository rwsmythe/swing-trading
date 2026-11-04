"""UserPromptSubmit hook: surface unread comms mail for a director session.

Stdlib-only. Wired via the tracked .claude/settings.json so a director CC
session (CHARC / RD) self-surfaces its unread file-mailbox on the operator's
next prompt -- the on-demand, activity-gated half of comms Stage 1.5 (NO
autonomous wake; that is Stage 3, explicitly held).

Contract:
  * Reads the role from the environment: HARNESS_ROLE first, SWING_ROLE second
    (role_from_env; the template's name is an ALIAS here, every SWING_ROLE pin
    stays). If unset or not in {charc, rd} the
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

# The role env vars, in precedence order. HARNESS_ROLE is the harness
# template's name (renamed there from SWING_ROLE); this instance reads it as an
# ALIAS ahead of SWING_ROLE, and the launcher sets BOTH, so a session carrying
# either is recognised (harness-template merge 2026-11-03, T2).
HARNESS_ROLE_ENV = "HARNESS_ROLE"
SWING_ROLE_ENV = "SWING_ROLE"


def role_from_env(env) -> str:  # noqa: ANN001 -- any Mapping[str, str]
    """The session's role: HARNESS_ROLE, else SWING_ROLE, else ''.

    An EMPTY HARNESS_ROLE counts as unset (falls through to SWING_ROLE).
    """
    return env.get(HARNESS_ROLE_ENV) or env.get(SWING_ROLE_ENV, "")


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
    # Absolute quoted path: the recovery command must work from ANY session
    # cwd (the 2026-06-12 blocked-prompt incident -- a persistent bash cd had
    # moved the session cwd and the relative form failed alongside the hook).
    role_mail = Path(__file__).resolve().parent / "role_mail.py"
    return (
        f"[comms] {len(msgs)} unread for {role}{dr_note} -- run: "
        f'python "{role_mail}" read --role {role} --all'
    )


def main() -> int:
    try:
        role = role_from_env(os.environ)
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
