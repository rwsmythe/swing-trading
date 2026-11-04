"""UserPromptSubmit hook: the unread comms notice + the [ctx] depth gauge.

Stdlib-only. Wired via the tracked .claude/settings.json so a role CC session
self-surfaces its unread file-mailbox on the operator's next prompt -- the
on-demand, activity-gated half of comms Stage 1.5 (NO autonomous wake; that is
Stage 3, explicitly held) -- and sees its own context depth.

Contract:
  * Reads the role from the environment: HARNESS_ROLE first, SWING_ROLE second
    (role_from_env; the template's name is an ALIAS here, every SWING_ROLE pin
    stays).
  * UNREAD LINE: for any role in COMMS_ROLES (single-sourced from
    role_mail.VALID_TO -- charc, rd, operator, orchestrator; harness-template
    merge 2026-11-03, T1 widened it from {charc, rd}) resolves the repo root
    from __file__ (NOT cwd), counts comms/<role>/inbox/*.md, and on a nonzero
    count prints ONE ASCII line naming the count, the decision_request subset,
    and the drain command. Any other role (or none) prints no unread line (the
    seeded-gate-masks-default discipline: the quiet default is the common case
    and is witnessed at the gate). DIRECTOR_ROLES stays {charc, rd}: it is the
    Stop hook's gate, which is NOT widened.
  * [ctx] GAUGE (T1, ported from the template's user_prompt_submit.py): for
    ANY session whose stdin hook payload names a transcript_path, role known
    or not, prints one ASCII line AFTER the unread line with the current
    context depth (the last message.usage in the transcript's tail) against
    the window, plus a roll-over warning at or past the cap.
  * The stdin payload is read as RAW BYTES decoded utf-8-sig (a leading BOM is
    stripped whatever the console codepage), never from a TTY (so it never
    blocks), and degrades to {} on any problem.
  * ALWAYS exits 0. A hook failure must NEVER block the operator's prompt, so
    any internal exception is swallowed to a silent exit 0; the two lines are
    guarded separately, so a failure in one never suppresses the other.

Output is ASCII (Windows cp1252 stdout); message files are read as UTF-8.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# The Stop hook's gate (comms_stop_hook imports it). NOT widened by T1.
DIRECTOR_ROLES = ("charc", "rd")

# The roles whose unread line this hook prints: SINGLE-SOURCED from
# role_mail.VALID_TO (the recipient set), loaded by file path the way
# comms_ui.py does (scripts/ is not a package), under a PRIVATE module name so
# it can never collide with or reuse a "role_mail" already on sys.modules.
# GUARDED: a missing/broken role_mail must never block a prompt, so any failure
# degrades to the frozen tuple below (keep it equal to VALID_TO).
_FALLBACK_COMMS_ROLES = ("charc", "rd", "operator", "orchestrator")
try:
    import importlib.util as _ilu

    _rm_spec = _ilu.spec_from_file_location(
        "_role_mail_unread_hook", Path(__file__).resolve().parent / "role_mail.py")
    _rm = _ilu.module_from_spec(_rm_spec)
    _rm_spec.loader.exec_module(_rm)
    COMMS_ROLES = tuple(_rm.VALID_TO)
except Exception:  # noqa: BLE001 -- never block a prompt; degrade to the default
    COMMS_ROLES = _FALLBACK_COMMS_ROLES

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


# --- the stdin hook payload ---------------------------------------------------

def _read_hook_payload() -> dict:
    """The hook JSON payload from stdin, or {} on any problem.

    Read as RAW BYTES and decoded utf-8-sig (a leading BOM is stripped however
    the spawning shell encodes the pipe -- the Stop hook's reader shape). A
    missing stdin or a TTY is never read, so the hook can never block waiting
    for input. Empty, undecodable, unparseable and non-dict payloads all
    degrade to {}.
    """
    try:
        stdin = sys.stdin
        if stdin is None or stdin.isatty():
            return {}
        raw = stdin.buffer.read()
        text = raw.decode("utf-8-sig").strip()
        if not text:
            return {}
        data = json.loads(text)
    except Exception:  # noqa: BLE001 -- degrade-gracefully, never block a prompt
        return {}
    return data if isinstance(data, dict) else {}


# --- the [ctx] context-depth gauge ---------------------------------------------
# The session's transcript (a .jsonl, one JSON object per line) carries each
# assistant turn's token usage on message.usage. The CURRENT CONTEXT DEPTH is
# input_tokens + cache_creation_input_tokens + cache_read_input_tokens on the
# LAST such line -- printed on every prompt as a one-line ASCII gauge, with a
# roll-over warning once depth reaches the cap. Transcripts run tens of MB and
# this hook fires on EVERY prompt, so only the TAIL of the file is read.
# (Ported from the harness template's .claude/hooks/user_prompt_submit.py,
# master 4335ff6; harness-template merge 2026-11-03, T1.)

_DEFAULT_CTX_WINDOW = 1_000_000
_DEFAULT_CTX_CAP = 400_000
_CTX_TAIL_BYTES = 512 * 1024
CTX_WINDOW_ENV = "HARNESS_CTX_WINDOW"
CTX_CAP_ENV = "HARNESS_CTX_CAP"

# Where each role writes its roll-over state. This instance's orchestrator
# rolls into a dated handoff doc; every other role into docs/<role>-state.md.
_ROLLOVER_DOC = {"orchestrator": "docs/orchestrator-handoff-<date>.md"}


def _int_env(env, name: str, default: int) -> int:  # noqa: ANN001
    """default, unless env[name] parses as an int (bad/missing -> default)."""
    raw = env.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _fmt_k(n: int) -> str:
    """n rendered as whole thousands, e.g. 449_000 -> '449K'."""
    return f"{round(n / 1000)}K"


def _last_usage_dict(transcript_path: Path) -> dict | None:
    """The last message.usage dict in transcript_path, or None on any problem.

    Reads only the tail (_CTX_TAIL_BYTES) of the file and scans lines backwards
    for the last one that both contains "usage" and parses to a JSON object
    with a dict message.usage -- best-effort, never raises.
    """
    try:
        size = transcript_path.stat().st_size
    except OSError:
        return None
    try:
        with open(transcript_path, "rb") as fh:
            if size > _CTX_TAIL_BYTES:
                fh.seek(-_CTX_TAIL_BYTES, os.SEEK_END)
            data = fh.read()
    except OSError:
        return None
    for raw in reversed(data.split(b"\n")):
        raw = raw.strip()
        if not raw or b"usage" not in raw:
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if isinstance(usage, dict):
            return usage
    return None


def context_depth_notice(transcript_path, env, role: str | None) -> str | None:  # noqa: ANN001
    """The one-line ASCII [ctx] gauge for transcript_path, or None.

    Best-effort + silent: a missing/non-string transcript_path, an unreadable
    file, no usage line, or malformed JSON all return None -- never raises.
    window/cap default to 1_000_000 / 400_000, overridable via
    HARNESS_CTX_WINDOW / HARNESS_CTX_CAP (bad values ignored, default kept).
    """
    if not transcript_path or not isinstance(transcript_path, (str, os.PathLike)):
        return None
    usage = _last_usage_dict(Path(transcript_path))
    if usage is None:
        return None
    try:
        depth = (int(usage.get("input_tokens") or 0)
                 + int(usage.get("cache_creation_input_tokens") or 0)
                 + int(usage.get("cache_read_input_tokens") or 0))
    except (TypeError, ValueError):
        return None

    window = _int_env(env, CTX_WINDOW_ENV, _DEFAULT_CTX_WINDOW)
    cap = _int_env(env, CTX_CAP_ENV, _DEFAULT_CTX_CAP)
    pct = round(depth * 100 / window) if window else 0
    line = f"[ctx] {_fmt_k(depth)} of {_fmt_k(window)} ({pct}%)"
    if depth >= cap:
        # Only a KNOWN comms role names its own state doc; anything else (unset,
        # unknown, non-ASCII) gets the generic label, so the line stays ASCII
        # (Reviewer A R1 F8).
        role_label = role if role in COMMS_ROLES else "role"
        doc = _ROLLOVER_DOC.get(role_label, f"docs/{role_label}-state.md")
        line += (f" -- DEPTH CAP {_fmt_k(cap)} REACHED: roll over at the next "
                 f"boundary (write {doc}, announce, stop draining)")
    return line


def handle_user_prompt_submit(payload: dict, env, root: Path) -> None:  # noqa: ANN001
    """The UserPromptSubmit action (separated from main() for testability).

    Prints the unread line for a comms role, THEN the [ctx] gauge for any
    session with a transcript. Each is guarded on its own, so a failure in
    one never suppresses the other; never raises.
    """
    role = ""
    try:
        role = role_from_env(env)
        if role in COMMS_ROLES:
            notice = unread_notice(role, root)
            if notice:
                print(notice)
    except Exception:  # noqa: BLE001 -- a hook failure must never block a prompt
        pass
    try:
        ctx = context_depth_notice(payload.get("transcript_path"), env, role)
        if ctx:
            print(ctx)
    except Exception:  # noqa: BLE001 -- a hook failure must never block a prompt
        pass


def main() -> int:
    try:
        payload = _read_hook_payload()
        handle_user_prompt_submit(payload, dict(os.environ), comms_root_default())
    except Exception:  # noqa: BLE001 -- a hook failure must never block a prompt
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
