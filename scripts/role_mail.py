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
import contextlib
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# Valid senders include orchestrator + the automated pipeline emitter.
VALID_FROM = ("charc", "rd", "operator", "orchestrator", "pipeline")
# Valid recipients. orchestrator is a ROTATING per-generation recipient (G6 Arc
# A): bare `--to orchestrator` resolves to the newest-live generation at send
# time; `--to orchestrator:<session_id>` addresses a specific generation
# (registry-independent). The other three are SINGULAR fixed-inbox roles.
VALID_TO = ("charc", "rd", "operator", "orchestrator")
# The fixed-inbox roles (comms/<role>/{inbox,read}); orchestrator is NOT here --
# it has a per-generation inbox owned by the registry module, not a singular one.
SINGULAR_INBOX_ROLES = ("charc", "rd", "operator")
VALID_TYPES = ("fyi", "status", "query", "return_report", "decision_request")
# AUTOMATED-EMITTER senders (non-human/agent) are constrained to a NARROW type
# allowlist -- transport-automation, NEVER authority (an automated emitter must
# not be able to post a decision_request, even to operator). `pipeline` (the
# nightly research-health RED notify, 18-H.7) posts `status` only. A human/agent
# role (charc/rd/operator/orchestrator) is NOT listed here and keeps the full
# VALID_TYPES. This is a TIGHTENING of the pipeline sender, not a loosening of L1.
_AUTOMATED_EMITTER_TYPES = {
    "pipeline": ("status",),
}

_SLUG_MAX = 40
_REPO_ROOT = Path(__file__).resolve().parent.parent


class MailError(Exception):
    """A validation / governance error to surface as exit 1 with a message."""


class NoLiveOrchestratorError(MailError):
    """No live orchestrator generation to receive a bare `--to orchestrator`.

    A CLEAR error (never a silent drop): the caller must address a specific
    generation with `--to orchestrator:<session_id>` or bring one up.
    """


# Lazy single-source registry loader (G6 Arc A). role_mail DELEGATES newest-live
# resolution + session_id safety + the per-generation path shape to
# comms_session_registry -- it NEVER re-implements them (lessons-learned guard
# #4). Imported lazily + ONLY on an orchestrator-path operation, so a broken /
# absent registry can never break singular (charc/rd/operator) mail.
_REGISTRY_MOD = None


def _registry():
    """Import + cache comms_session_registry; MailError if unavailable.

    Robust to BOTH the script-run path (scripts/ on sys.path) AND the test
    loader (role_mail loaded via spec_from_file_location, scripts/ NOT on path).
    """
    global _REGISTRY_MOD
    if _REGISTRY_MOD is not None:
        return _REGISTRY_MOD
    try:
        import comms_session_registry as mod
    except Exception:  # noqa: BLE001 -- fall back to a by-path load
        try:
            import importlib.util
            path = _REPO_ROOT / "scripts" / "comms_session_registry.py"
            spec = importlib.util.spec_from_file_location(
                "comms_session_registry", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as exc:  # noqa: BLE001
            raise MailError(f"registry module unavailable: {exc}") from exc
    _REGISTRY_MOD = mod
    return mod


class _AsciiArgumentParser(argparse.ArgumentParser):
    """ArgumentParser whose own usage/error output is cp1252-safe.

    argparse writes its messages (which can echo raw non-ASCII argv) directly
    to stderr before main()'s handler runs; sanitize them here so a bad value
    cannot UnicodeEncodeError on a Windows cp1252 console. Subparsers inherit
    this class via add_subparsers' default parser_class.
    """

    def _print_message(self, message, file=None):  # noqa: ANN001
        if message:
            super()._print_message(_ascii(message), file)


def _now() -> datetime:
    """UTC clock seam (monkeypatched in tests for deterministic stamps)."""
    return datetime.now(UTC)


def _ascii(text: str) -> str:
    """Make text safe for Windows cp1252 stdout (backslash-escape non-ASCII).

    Console output ONLY -- message files stay UTF-8. A subject or body with
    emoji / CJK must never crash list/read/peek on a cp1252 console.
    """
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _write_temp(final: Path, content: str) -> Path:
    """Write content to a temp file in final's directory; return the temp path.

    Same-directory temp keeps the later os.replace on one filesystem (the
    Windows os.replace cross-volume gotcha). Cleans up on write failure.

    INTENTIONAL COPY -- keep in sync; twin in
    comms_session_registry.py:_atomic_write_text (same same-dir mkstemp +
    os.replace pattern). The registry keeps a LOCAL copy (not a cross-import) to
    preserve THIS core-mail path's isolation from the registry module.
    """
    final.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(final.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
    return Path(tmp_name)


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
    # Iterate the SINGULAR roles only -- orchestrator's per-generation inboxes
    # are bootstrapped lazily by _write_temp (send) / ensure_per_generation_inbox
    # (the hook), so we must NOT auto-create a singular comms/orchestrator/inbox.
    for role in SINGULAR_INBOX_ROLES:
        (root / role / "inbox").mkdir(parents=True, exist_ok=True)
        (root / role / "read").mkdir(parents=True, exist_ok=True)


def _validate_recipients(recipients: list[str]) -> list[str]:
    """Validate + de-dupe a recipient list (shared by the CLI and the UI seam).

    Strips blanks, rejects an empty result and any role not in VALID_TO, and
    de-dupes preserving order. Raises MailError on the first problem.
    """
    recips = [r.strip() for r in recipients if r and r.strip()]
    if not recips:
        raise MailError(
            "no recipients given; valid roles: " + "|".join(VALID_TO))
    bad = [r for r in recips if r not in VALID_TO]
    if bad:
        raise MailError(
            "invalid recipient(s) " + ",".join(bad)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    # de-dupe, preserve order
    seen: list[str] = []
    for r in recips:
        if r not in seen:
            seen.append(r)
    return seen


def _parse_recipients(raw: str) -> list[str]:
    return _validate_recipients(raw.split(","))


# --- orchestrator addressing (G6 Arc A) ------------------------------------

def _split_target(token: str) -> tuple[str, str | None]:
    """Parse one recipient token into (role, session_id_or_None).

    No ':' -> (role, None) if role is a valid recipient, else MailError. With a
    ':' -> only `orchestrator` may carry a `:<session_id>` suffix; the session_id
    must be non-empty and pass the registry's safety rule (fail-LOUD, never a
    silent accept). The singular roles reject any suffix.
    """
    if ":" not in token:
        if token in VALID_TO:
            return (token, None)
        raise MailError(
            "invalid recipient " + repr(token)
            + "; valid roles: " + "|".join(VALID_TO))
    role, _, sid = token.partition(":")
    if role != "orchestrator":
        raise MailError(
            "only 'orchestrator' may carry a :<session_id> suffix; the singular "
            "roles are " + "|".join(SINGULAR_INBOX_ROLES) + " (got " + repr(token)
            + ")")
    if not sid:
        raise MailError("empty session_id in recipient " + repr(token))
    if not _registry().is_valid_session_id(sid):
        raise MailError("refusing unsafe session_id " + repr(sid))
    return ("orchestrator", sid)


def _parse_recipient_pairs(recipients: list[str]) -> list[tuple[str, str | None]]:
    """Validate + de-dupe recipient tokens into (role, sid) pairs (order kept)."""
    toks = [r.strip() for r in recipients if r and r.strip()]
    if not toks:
        raise MailError(
            "no recipients given; valid roles: " + "|".join(VALID_TO))
    pairs: list[tuple[str, str | None]] = []
    for tok in toks:
        pair = _split_target(tok)
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def _recipient_label(role: str, sid: str | None) -> str:
    """The `to:` frontmatter label: orchestrator:<sid> for a resolved gen."""
    if role == "orchestrator" and sid:
        return f"orchestrator:{sid}"
    return role


def _inbox_for_target(root: Path, role: str, sid: str | None,
                      now: datetime | None = None) -> Path:
    """The concrete inbox dir for (role, sid). DELEGATES the per-gen path shape.

    Singular roles -> root/<role>/inbox (role_mail owns the singular shape only).
    orchestrator -> resolve sid (bare = newest_live at send; None -> a CLEAR
    NoLiveOrchestratorError, never a silent drop), re-validate the resolved sid
    (belt -- never trust a resolved value into a path), then return the
    registry's per_generation_inbox (the single owner of the per-gen path).
    """
    if role in SINGULAR_INBOX_ROLES:
        return root / role / "inbox"
    if role == "orchestrator":
        eff = sid
        if eff is None:
            entry = _registry().newest_live(root, now if now is not None else _now())
            if not entry:
                raise NoLiveOrchestratorError(
                    "no live orchestrator generation to receive a bare "
                    "'--to orchestrator'. Address a specific generation with "
                    "'--to orchestrator:<session_id>', or bring an orchestrator "
                    "generation up first. Nothing was written.")
            eff = entry.get("session_id")
        if not _registry().is_valid_session_id(eff):
            raise MailError("refusing unsafe session_id " + repr(eff))
        return _registry().per_generation_inbox(root, eff)
    raise MailError(
        "invalid recipient " + repr(role) + "; valid roles: " + "|".join(VALID_TO))


def _role_inbox_dir(root: Path, role: str, sid: str | None) -> Path:
    """The inbox dir for a read/list/peek/ack op (singular or per-generation)."""
    if role in SINGULAR_INBOX_ROLES:
        return root / role / "inbox"
    if role == "orchestrator":
        if not sid:
            raise MailError(
                "reading an orchestrator inbox requires --session <session_id>")
        if not _registry().is_valid_session_id(sid):
            raise MailError("refusing unsafe session_id " + repr(sid))
        return _registry().per_generation_inbox(root, sid)
    raise MailError(
        "invalid role " + repr(role) + "; valid roles: " + "|".join(VALID_TO))


def _role_read_dir(root: Path, role: str, sid: str | None) -> Path:
    """The read (ack archive) dir for a role (singular or per-generation)."""
    if role in SINGULAR_INBOX_ROLES:
        return root / role / "read"
    if role == "orchestrator":
        if not sid:
            raise MailError(
                "an orchestrator ack requires --session <session_id>")
        if not _registry().is_valid_session_id(sid):
            raise MailError("refusing unsafe session_id " + repr(sid))
        return _registry().per_generation_read(root, sid)
    raise MailError(
        "invalid role " + repr(role) + "; valid roles: " + "|".join(VALID_TO))


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


def _unique_dest(dest_dir: Path, filename: str) -> Path:
    """A non-colliding path in dest_dir for filename (suffix -2, -3, ...).

    Used when acking inbox -> read so an archived message with the same name
    (same stamp+sender+slug posted twice across an empty inbox) is never
    overwritten -- ack must never delete history.
    """
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem = filename[:-3] if filename.endswith(".md") else filename
    suffix = 2
    while True:
        candidate = dest_dir / f"{stem}-{suffix}.md"
        if not candidate.exists():
            return candidate
        suffix += 1


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
            key = key.strip()
            if key not in fm:  # first occurrence wins; ignore injected dupes
                fm[key] = val.strip()
    return fm


# --- pure mail operations (the single write path; CLI + UI both go here) ----

def post_message(
    root: Path,
    sender: str,
    recipients: list[str],
    mtype: str,
    subject: str,
    body: str,
    thread: str | None = None,
) -> list[Path]:
    """Validate, governance-lock, and atomically deliver one message.

    The single write path for posting mail: the CLI (cmd_post) and the mail UI
    both call THIS. Validation order is preserved from the original cmd_post
    (sender -> type -> CR/LF guard -> recipients -> L1 lock) so CLI behavior is
    byte-identical. Multi-recipient delivery is all-or-nothing (stage temps in
    each destination dir, then os.replace each into place only once every temp
    wrote cleanly; a failure rolls back). Raises MailError on any
    validation/governance/IO failure; nothing partial is left behind. Returns
    the list of committed final Paths (recipient order).
    """
    if sender not in VALID_FROM:
        raise MailError(
            "invalid --from " + repr(sender)
            + "; valid senders: " + "|".join(VALID_FROM)
        )
    if mtype not in VALID_TYPES:
        raise MailError(
            "invalid --type " + repr(mtype)
            + "; valid types: " + "|".join(VALID_TYPES)
        )
    # Automated-emitter type allowlist: a non-human/agent sender (e.g. pipeline)
    # is constrained to its narrow type set so it can never post a
    # decision_request (authority) -- transport-automation only. Checked BEFORE
    # delivery so nothing is written on a rejection.
    allowed_types = _AUTOMATED_EMITTER_TYPES.get(sender)
    if allowed_types is not None and mtype not in allowed_types:
        raise MailError(
            "automated emitter " + repr(sender) + " may post only "
            + "|".join(allowed_types) + " (transport-automation, not authority);"
            + " got " + repr(mtype) + ". Nothing was written."
        )
    # Reject CR/LF in line-oriented frontmatter fields (frontmatter injection).
    for label, value in (("subject", subject), ("thread", thread)):
        if value is not None and ("\n" in value or "\r" in value):
            raise MailError(
                f"{label} may not contain newlines (frontmatter injection). "
                "Nothing was written."
            )
    # Parse recipients to (role, sid) pairs (orchestrator may carry :<sid>).
    pairs = _parse_recipient_pairs(recipients)
    # L1 governance lock: decision_request must address ONLY the operator. Fires
    # on the PARSED role BEFORE any inbox resolution, so decision_request to
    # orchestrator / orchestrator:<sid> is refused here regardless of liveness.
    if mtype == "decision_request" and any(role != "operator" for role, _ in pairs):
        raise MailError(
            "L1: type 'decision_request' may be addressed ONLY to operator "
            "(role->role traffic is fyi|status|query|return_report). "
            "Nothing was written."
        )
    _ensure_tree(root)

    now = _now()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    posted = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = _slugify(subject)

    # Resolve each pair to its concrete inbox (a NoLiveOrchestratorError fires
    # HERE, before any temp is staged -> all-or-nothing). De-dupe by the RESOLVED
    # inbox path so bare `orchestrator` + `orchestrator:<newest_sid>` collapse to
    # one delivery. The orchestrator label records the concrete generation.
    resolved: list[tuple[Path, str]] = []
    seen_inboxes: set[str] = set()
    for role, sid in pairs:
        inbox = _inbox_for_target(root, role, sid, now=now)
        key = str(inbox)
        if key in seen_inboxes:
            continue
        seen_inboxes.add(key)
        if role == "orchestrator":
            label = _recipient_label(role, inbox.parent.name)
        else:
            label = role
        resolved.append((inbox, label))

    # Precompute every (final path, content) BEFORE writing anything so a
    # multi-recipient post delivers all-or-nothing (atomicity): stage temps in
    # each destination dir, then os.replace each into place only once every
    # temp wrote cleanly. A failure mid-stage removes the temps -> no partial.
    targets = [
        (
            _unique_path(inbox, stamp, sender, slug),
            _compose(sender, label, mtype, subject, posted, thread, body),
        )
        for inbox, label in resolved
    ]
    staged: list[tuple[Path, Path]] = []  # (temp, final)
    try:
        for final, content in targets:
            staged.append((_write_temp(final, content), final))
    except Exception as exc:
        for tmp, _ in staged:
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise MailError(
            f"post failed while staging ({exc}); nothing was delivered."
        ) from exc
    committed: list[Path] = []
    try:
        for tmp, final in staged:
            os.replace(str(tmp), str(final))
            committed.append(final)
    except OSError as exc:
        # Partial delivery: roll back the finals we already committed and drop
        # any temps not yet replaced, so the post stays all-or-nothing. Report
        # honestly if a committed final could not be removed (don't claim a
        # clean rollback when one isn't).
        unremoved: list[Path] = []
        for final in committed:
            try:
                final.unlink()
            except OSError:
                unremoved.append(final)
        for tmp, _ in staged:
            with contextlib.suppress(OSError):
                tmp.unlink()
        if unremoved:
            raise MailError(
                f"post failed during delivery ({exc}); rollback INCOMPLETE -- "
                "these were delivered and could not be removed: "
                + ", ".join(p.name for p in unremoved)
            ) from exc
        raise MailError(
            f"post failed during delivery ({exc}); rolled back, nothing delivered."
        ) from exc

    return committed


def ack_message(root: Path, role: str, filename: str,
                session_id: str | None = None) -> Path:
    """Ack one message: move <inbox>/<filename> -> <read>/ (returns the dest).

    The single ack path (the CLI's cmd_read and the UI both call THIS). Uses
    _unique_dest so an archived message of the same name is never overwritten
    (ack must never delete history). filename MUST be a bare basename --
    traversal attempts are rejected (L3 mail custody: the ack can never reach
    outside the role's own inbox). `session_id` (default None, back-compat for
    the GUI + singular reads) is REQUIRED for orchestrator and selects the
    per-generation inbox/read dirs (delegated to the registry). The per-gen
    read/ dir is created lazily here, so an explicit-:<sid> round-trip works even
    for a generation that never ran session-start. Raises MailError on invalid
    role, traversal, a missing session for orchestrator, or a missing file.
    """
    if role not in VALID_TO:
        raise MailError(
            "invalid role " + repr(role) + "; valid roles: " + "|".join(VALID_TO))
    if filename != Path(filename).name or "/" in filename or "\\" in filename:
        raise MailError(f"refusing non-basename filename {filename!r}")
    inbox_dir = _role_inbox_dir(root, role, session_id)
    read_dir = _role_read_dir(root, role, session_id)
    src = inbox_dir / filename
    if not src.is_file():
        raise MailError(
            f"no inbox message named {filename!r} for role {role}")
    read_dir.mkdir(parents=True, exist_ok=True)
    dest = _unique_dest(read_dir, src.name)
    src.rename(dest)
    return dest


# --- subcommands -----------------------------------------------------------

def cmd_post(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    sender = args.__dict__["from"]
    body = _resolve_body(args)
    # Split here; post_message validates (the single write path owns the rules).
    recipients = [r.strip() for r in args.to.split(",") if r.strip()]
    finals = post_message(
        root, sender, recipients, args.type, args.subject, body, args.thread)
    for final in finals:
        print(f"posted -> {final.parent.parent.name}/inbox/{final.name}")
    return 0


def _list_inbox(root: Path, role: str, sid: str | None = None) -> list[Path]:
    inbox = _role_inbox_dir(root, role, sid)
    return sorted(inbox.glob("*.md")) if inbox.is_dir() else []


def _list_read(root: Path, role: str, sid: str | None = None) -> list[Path]:
    rd = _role_read_dir(root, role, sid)
    return sorted(rd.glob("*.md")) if rd.is_dir() else []


def cmd_list(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    if args.role not in VALID_TO:
        raise MailError(
            "invalid --role " + repr(args.role)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    sid = getattr(args, "session", None)
    inbox = _list_inbox(root, args.role, sid)
    read_count = len(_list_read(root, args.role, sid))
    print(f"inbox for {args.role}: {len(inbox)} unread, {read_count} read")
    if not inbox:
        print("  (inbox empty)")
        return 0
    print(f"  {'posted':20} {'from':12} {'type':15} subject")
    print("  " + "-" * 70)
    for path in inbox:
        fm = _read_frontmatter(path)
        print("  {:20} {:12} {:15} {}".format(
            _ascii(fm.get("posted", "?")), _ascii(fm.get("from", "?")),
            _ascii(fm.get("type", "?")), _ascii(fm.get("subject", path.name))))
    return 0


def _print_message(path: Path) -> None:
    print("=" * 72)
    print(f"file: {_ascii(path.name)}")
    print("-" * 72)
    print(_ascii(path.read_text(encoding="utf-8").rstrip("\n")))
    print()


def cmd_read(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    if args.role not in VALID_TO:
        raise MailError(
            "invalid --role " + repr(args.role)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    sid = getattr(args, "session", None)
    inbox = _list_inbox(root, args.role, sid)
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
    for path in targets:
        _print_message(path)
        ack_message(root, args.role, path.name, session_id=sid)
    print(f"acked {len(targets)} message(s); moved inbox -> read.")
    return 0


def cmd_peek(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    if args.role not in VALID_TO:
        raise MailError(
            "invalid --role " + repr(args.role)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    sid = getattr(args, "session", None)
    inbox = _list_inbox(root, args.role, sid)
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
    parser = _AsciiArgumentParser(
        description="Inter-role file mailbox (comms Stage 1).")
    parser.add_argument(
        "--comms-root", default=None,
        help="mailbox root (default: <repo>/comms; tests pass tmp_path)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_post = sub.add_parser("post", help="post a message to recipient inbox(es)")
    _add_comms_root(p_post)
    p_post.add_argument("--from", required=True, dest="from",
                        help="sender: " + "|".join(VALID_FROM))
    p_post.add_argument(
        "--to", required=True,
        help="recipient(s), comma-separated: " + "|".join(VALID_TO)
        + " (orchestrator = newest-live; orchestrator:<session_id> = a gen)")
    p_post.add_argument("--type", required=True,
                        help="message type: " + "|".join(VALID_TYPES))
    p_post.add_argument("--subject", required=True)
    p_post.add_argument("--body", default=None, help="inline body text")
    p_post.add_argument("--body-file", dest="body_file", default=None,
                        help="read body from this file")
    p_post.add_argument("--thread", default=None, help="optional thread slug")
    p_post.set_defaults(func=cmd_post)

    _SESSION_HELP = "orchestrator generation session_id (required for --role orchestrator)"

    p_list = sub.add_parser("list", help="list a role's inbox")
    _add_comms_root(p_list)
    p_list.add_argument("--role", required=True, help="|".join(VALID_TO))
    p_list.add_argument("--session", default=None, help=_SESSION_HELP)
    p_list.add_argument("--unread-only", action="store_true",
                        help="(default already lists only the inbox)")
    p_list.set_defaults(func=cmd_list)

    p_read = sub.add_parser("read", help="print + ack message(s) (inbox -> read)")
    _add_comms_root(p_read)
    p_read.add_argument("--role", required=True, help="|".join(VALID_TO))
    p_read.add_argument("--session", default=None, help=_SESSION_HELP)
    g = p_read.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="read+ack the whole inbox")
    g.add_argument("--id", default=None, help="read+ack one message by filename")
    p_read.set_defaults(func=cmd_read)

    p_peek = sub.add_parser("peek", help="print unread WITHOUT acking")
    _add_comms_root(p_peek)
    p_peek.add_argument("--role", required=True, help="|".join(VALID_TO))
    p_peek.add_argument("--session", default=None, help=_SESSION_HELP)
    p_peek.set_defaults(func=cmd_peek)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MailError as exc:
        # Sanitize: the message can echo raw user input (sender/role values).
        print(f"error: {_ascii(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
