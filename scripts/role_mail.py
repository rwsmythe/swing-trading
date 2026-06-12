"""Inter-role file mailbox CLI (comms Stage 1).

A durable, stdlib-only message bus between the project's human/AI roles.
One file per message under a gitignored ``comms/`` tree; ``read`` MOVES a
message inbox -> read (an ack), nothing is ever deleted by this tool.

Governance lock (L1, information-vs-authority): role->role traffic is
limited to ``fyi|status|query|return_report``. ``decision_request`` is
valid ONLY when EVERY recipient is the operator -- this tool refuses to
write a decision_request addressed to any other role (hard error, exit 1).
That is the load-bearing protection: transport is automated, authority is
not. Do not soften it.

ASCII-only console output (Windows cp1252 stdout gotcha); message files
are written/read as UTF-8.

Usage (from the repo root):
    python scripts/role_mail.py post --from charc --to rd --type status \\
        --subject "Arc 1 shipped" --body "All green."
    python scripts/role_mail.py list --role charc
    python scripts/role_mail.py read --role charc --all
    python scripts/role_mail.py peek --role rd

Layout (auto-created on first use):
    comms/<role>/inbox/   comms/<role>/read/      for role in charc|rd|operator
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# Valid senders include orchestrator (which has no inbox in V1 -- directors
# hand-carry dispatch-direction traffic by design).
VALID_FROM = ("charc", "rd", "operator", "orchestrator")
# Valid recipients are only the three inbox-holding roles.
VALID_TO = ("charc", "rd", "operator")
VALID_TYPES = ("fyi", "status", "query", "return_report", "decision_request")

_SLUG_MAX = 40
_REPO_ROOT = Path(__file__).resolve().parent.parent


class MailError(Exception):
    """A validation / governance error to surface as exit 1 with a message."""


def _now() -> datetime:
    """UTC clock seam (monkeypatched in tests for deterministic stamps)."""
    return datetime.now(UTC)


def _slugify(subject: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")
    if len(slug) > _SLUG_MAX:
        slug = slug[:_SLUG_MAX].rstrip("-")
    return slug or "msg"


def _comms_root(args: argparse.Namespace) -> Path:
    if args.comms_root:
        return Path(args.comms_root)
    return _REPO_ROOT / "comms"


def _ensure_tree(root: Path) -> None:
    for role in VALID_TO:
        (root / role / "inbox").mkdir(parents=True, exist_ok=True)
        (root / role / "read").mkdir(parents=True, exist_ok=True)


def _parse_recipients(raw: str) -> list[str]:
    recips = [r.strip() for r in raw.split(",") if r.strip()]
    if not recips:
        raise MailError("--to is empty; give one or more of: " + "|".join(VALID_TO))
    bad = [r for r in recips if r not in VALID_TO]
    if bad:
        raise MailError(
            "invalid recipient(s) " + ",".join(bad)
            + "; valid --to roles: " + "|".join(VALID_TO)
        )
    # de-dupe, preserve order
    seen: list[str] = []
    for r in recips:
        if r not in seen:
            seen.append(r)
    return seen


def _resolve_body(args: argparse.Namespace) -> str:
    if args.body is not None:
        return args.body
    if args.body_file is not None:
        return Path(args.body_file).read_text(encoding="utf-8")
    # stdin fallback
    return sys.stdin.read()


def _unique_path(inbox: Path, stamp: str, sender: str, slug: str) -> Path:
    base = f"{stamp}-{sender}-{slug}"
    candidate = inbox / f"{base}.md"
    suffix = 2
    while candidate.exists():
        candidate = inbox / f"{base}-{suffix}.md"
        suffix += 1
    return candidate


def _compose(sender: str, recipient: str, mtype: str, subject: str,
             posted: str, thread: str | None, body: str) -> str:
    lines = [
        "---",
        f"from: {sender}",
        f"to: {recipient}",
        f"type: {mtype}",
        f"subject: {subject}",
        f"posted: {posted}",
    ]
    if thread:
        lines.append(f"thread: {thread}")
    lines.append("---")
    text = "\n".join(lines) + "\n\n" + body.rstrip("\n") + "\n"
    return text


def _read_frontmatter(path: Path) -> dict[str, str]:
    fm: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return fm
    if not text.startswith("---"):
        return fm
    body = text.split("\n", 1)[1] if "\n" in text else ""
    for line in body.split("\n"):
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


# --- subcommands -----------------------------------------------------------

def cmd_post(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    sender = args.__dict__["from"]
    if sender not in VALID_FROM:
        raise MailError(
            "invalid --from " + repr(sender)
            + "; valid senders: " + "|".join(VALID_FROM)
        )
    if args.type not in VALID_TYPES:
        raise MailError(
            "invalid --type " + repr(args.type)
            + "; valid types: " + "|".join(VALID_TYPES)
        )
    recipients = _parse_recipients(args.to)
    # L1 governance lock: decision_request must address ONLY the operator.
    if args.type == "decision_request" and any(r != "operator" for r in recipients):
        raise MailError(
            "L1: type 'decision_request' may be addressed ONLY to operator "
            "(role->role traffic is fyi|status|query|return_report). "
            "Nothing was written."
        )
    body = _resolve_body(args)
    _ensure_tree(root)

    now = _now()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    posted = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = _slugify(args.subject)

    written: list[Path] = []
    for recipient in recipients:
        inbox = root / recipient / "inbox"
        path = _unique_path(inbox, stamp, sender, slug)
        content = _compose(sender, recipient, args.type, args.subject,
                           posted, args.thread, body)
        path.write_text(content, encoding="utf-8")
        written.append(path)

    for path in written:
        print(f"posted -> {path.parent.parent.name}/inbox/{path.name}")
    return 0


def _list_inbox(root: Path, role: str) -> list[Path]:
    inbox = root / role / "inbox"
    return sorted(inbox.glob("*.md")) if inbox.is_dir() else []


def _list_read(root: Path, role: str) -> list[Path]:
    rd = root / role / "read"
    return sorted(rd.glob("*.md")) if rd.is_dir() else []


def cmd_list(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    if args.role not in VALID_TO:
        raise MailError(
            "invalid --role " + repr(args.role)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    inbox = _list_inbox(root, args.role)
    read_count = len(_list_read(root, args.role))
    print(f"inbox for {args.role}: {len(inbox)} unread, {read_count} read")
    if not inbox:
        print("  (inbox empty)")
        return 0
    print(f"  {'posted':20} {'from':12} {'type':15} subject")
    print("  " + "-" * 70)
    for path in inbox:
        fm = _read_frontmatter(path)
        print("  {:20} {:12} {:15} {}".format(
            fm.get("posted", "?"), fm.get("from", "?"),
            fm.get("type", "?"), fm.get("subject", path.name)))
    return 0


def _print_message(path: Path) -> None:
    print("=" * 72)
    print(f"file: {path.name}")
    print("-" * 72)
    print(path.read_text(encoding="utf-8").rstrip("\n"))
    print()


def cmd_read(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    if args.role not in VALID_TO:
        raise MailError(
            "invalid --role " + repr(args.role)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    inbox = _list_inbox(root, args.role)
    if args.id:
        targets = [p for p in inbox if p.name == args.id]
        if not targets:
            raise MailError(
                f"no inbox message named {args.id!r} for role {args.role}")
    else:
        targets = inbox  # --all (or default): drain the whole inbox
    if not targets:
        print(f"inbox for {args.role} is empty; nothing to read.")
        return 0
    read_dir = root / args.role / "read"
    read_dir.mkdir(parents=True, exist_ok=True)
    for path in targets:
        _print_message(path)
        path.rename(read_dir / path.name)
    print(f"acked {len(targets)} message(s); moved inbox -> read.")
    return 0


def cmd_peek(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    if args.role not in VALID_TO:
        raise MailError(
            "invalid --role " + repr(args.role)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    inbox = _list_inbox(root, args.role)
    if not inbox:
        print(f"inbox for {args.role} is empty.")
        return 0
    print(f"PEEK (no ack): {len(inbox)} unread for {args.role}")
    for path in inbox:
        _print_message(path)
    return 0


def _add_comms_root(p: argparse.ArgumentParser) -> None:
    # Accepted in both positions (before OR after the subcommand). The
    # subcommand-level copy uses SUPPRESS so omitting it does not clobber a
    # value already parsed at the top level.
    p.add_argument(
        "--comms-root", default=argparse.SUPPRESS,
        help="mailbox root (default: <repo>/comms; tests pass tmp_path)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inter-role file mailbox (comms Stage 1).")
    parser.add_argument(
        "--comms-root", default=None,
        help="mailbox root (default: <repo>/comms; tests pass tmp_path)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_post = sub.add_parser("post", help="post a message to recipient inbox(es)")
    _add_comms_root(p_post)
    p_post.add_argument("--from", required=True, dest="from",
                        help="sender: " + "|".join(VALID_FROM))
    p_post.add_argument("--to", required=True,
                        help="recipient(s), comma-separated: " + "|".join(VALID_TO))
    p_post.add_argument("--type", required=True,
                        help="message type: " + "|".join(VALID_TYPES))
    p_post.add_argument("--subject", required=True)
    p_post.add_argument("--body", default=None, help="inline body text")
    p_post.add_argument("--body-file", dest="body_file", default=None,
                        help="read body from this file")
    p_post.add_argument("--thread", default=None, help="optional thread slug")
    p_post.set_defaults(func=cmd_post)

    p_list = sub.add_parser("list", help="list a role's inbox")
    _add_comms_root(p_list)
    p_list.add_argument("--role", required=True, help="|".join(VALID_TO))
    p_list.add_argument("--unread-only", action="store_true",
                        help="(default already lists only the inbox)")
    p_list.set_defaults(func=cmd_list)

    p_read = sub.add_parser("read", help="print + ack message(s) (inbox -> read)")
    _add_comms_root(p_read)
    p_read.add_argument("--role", required=True, help="|".join(VALID_TO))
    g = p_read.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="read+ack the whole inbox")
    g.add_argument("--id", default=None, help="read+ack one message by filename")
    p_read.set_defaults(func=cmd_read)

    p_peek = sub.add_parser("peek", help="print unread WITHOUT acking")
    _add_comms_root(p_peek)
    p_peek.add_argument("--role", required=True, help="|".join(VALID_TO))
    p_peek.set_defaults(func=cmd_peek)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MailError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
