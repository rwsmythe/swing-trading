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

UNIFORM SINGULAR ADDRESSING (21-D, 2026-07-27): every role has ONE fixed
inbox ``comms/<role>/inbox`` (+ ``comms/<role>/read``). ``--to charc`` /
``--to rd`` / ``--to operator`` / ``--to orchestrator`` each deliver to the
single named inbox -- there is no ambiguity and no per-generation resolution.
The orchestrator inbox is drained by whichever generation is live (a handoff
transfers the drain). The ``session_id`` survives ONLY as a role-presence /
recovery key in ``comms_session_registry`` -- NEVER as an addressing key.

The retired per-generation forms are REJECTED, never ignored: a
``--to orchestrator:<session_id>`` address and a ``--session <id>`` read flag
each fail with an actionable message naming the singular replacement. A stale
caller LEARNS instead of silently misrouting -- that rejection is what made the
convention change safe to land mid-flight.

VERIFIED POSTING (harness-template merge 2026-11-03, T3): ``post-verified``
takes exactly the ``post`` arguments and, in the same call, confirms the
message landed in the inbox it was addressed to under the mailbox root that was
actually resolved (``--expect-root`` asserts WHICH root that is, up front,
before anything is written). It confirms the SPECIFIC message it just wrote --
a per-message ``msg-id`` + ``posted`` discriminator, not the shared headers
alone -- so a header-twin (same from/to/type/subject) cannot answer for it. A
message a receiver already acked (inbox -> read) in the verify gap still
counts as landed. Anything else is a non-zero exit naming where the message
actually is, or that it is nowhere. When the root was DEFAULTED and this
checkout is a linked working copy (a worktree), a notice on stderr names the
primary copy's mailbox -- the 2026-06-21 worktree-misdelivery class.

CONTAINMENT BOUNDARY (what the _within guard is + is NOT): THIS tool's mailbox
OPERATIONS are ``_within``-guarded fail-closed against a junctioned /
symlinked inbox or role dir -- post delivery (recipient-tree creation + each
delivery target, checked BEFORE any temp is staged), list/read/peek
ENUMERATION (``_list_inbox`` / ``_list_read`` refuse an EXISTING-but-escaping
dir BEFORE any glob/read/print), and ack (SOURCE inbox + DEST read/ dir).
Create + enumerate paths route through ``_guarded_mkdir`` /
``_guarded_enum_dir`` (both resolve symlinks + junctions via ``_within``); a
MISSING dir stays empty (a not-yet-created singular inbox is normal). A post
creates ONLY its addressed recipients' trees, never an unaddressed role's. It
is NOT a claim that every write under ``comms/`` is guarded, and it is
deliberately NOT a defense against an active attacker. OUT-OF-MODEL: the
session registry (``comms/sessions/``, comms_session_registry.py), the
launcher's ``comms/.sessions.json``, and the mail UI's own code (separate
modules; the UI's mail writes come through post_message / ack_message here); a
TOCTOU race (a dir swapped for a junction BETWEEN check and use); and a
DELIBERATELY junctioned tree. A junctioned comms tree is a SETUP
MISCONFIGURATION -- an actor who can create the junction already has the
filesystem access any read would grant.

ASCII-only console output (Windows cp1252 stdout gotcha); message files
are written/read as UTF-8.

A subject over SUBJECT_MAX_CHARS (120; operator-directed 2026-11-03, was 80)
characters is REJECTED by post and post-verified (nothing is written) -- a
subject names the message; the body carries it.

Usage (from the repo root):
    python scripts/role_mail.py post --from charc --to rd --type status \\
        --subject "Arc 1 shipped" --body "All green."
    python scripts/role_mail.py post-verified --from charc --to rd \\
        --type status --subject "Arc 1 shipped" --body "All green." \\
        --expect-root /path/to/the/main/repo/comms
    python scripts/role_mail.py list --role charc
    python scripts/role_mail.py read --role charc --all
    python scripts/role_mail.py read --role orchestrator --all
    python scripts/role_mail.py peek --role rd

Layout (auto-created on first use):
    comms/<role>/inbox/   comms/<role>/read/
        for role in charc|rd|operator|orchestrator
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import secrets
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# Valid senders include orchestrator + the automated pipeline emitter.
VALID_FROM = ("charc", "rd", "operator", "orchestrator", "pipeline")
# Valid recipients. EVERY role is a singular fixed-inbox role (21-D): a bare
# `--to <role>` is the ONLY address form; the per-generation
# `--to orchestrator:<session_id>` form is retired and REJECTED.
VALID_TO = ("charc", "rd", "operator", "orchestrator")
# The fixed-inbox roles (comms/<role>/{inbox,read}). Every role is singular, so
# SINGULAR_INBOX_ROLES == VALID_TO; kept as its own name because the addressing
# helpers read it as "the roles whose inbox is comms/<role>/inbox".
SINGULAR_INBOX_ROLES = ("charc", "rd", "operator", "orchestrator")
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
# Hard cap on `--subject`, enforced in `post` (and so `post-verified`) before
# anything is written. See the guard for the reasoning. The name is the
# harness template's.
SUBJECT_MAX_CHARS = 120  # operator-directed 2026-11-03 (was 80)
_REPO_ROOT = Path(__file__).resolve().parent.parent


class MailError(Exception):
    """A validation / governance error to surface as exit 1 with a message."""


class VerificationError(MailError):
    """A posted message did not land where it was addressed (post-verified)."""


# The one message every retired per-generation form points at (single-sourced so
# the send side, the read side, and their tests can never drift apart).
_RETIRED_PREFIX = "per-generation addressing was removed"
_SINGULAR_HINT = ("Every role is a singular inbox -- address it by bare name "
                  "(e.g. 'orchestrator').")


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


def _within(parent: Path, child: Path) -> bool:
    """True iff `child` resolves to a path CONTAINED in `parent` (both resolved).

    ``resolve()`` follows symlinks AND Windows junctions, so this catches a
    reparse point that escapes the mailbox tree even though the LEXICAL path
    still reads as contained. Any resolve/comparison error is treated as NOT
    contained (fail-closed).
    """
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def _guarded_mkdir(root: Path, target: Path) -> None:
    """Create `target` (mkdir -p) ONLY if it resolves INSIDE `root`.

    The containment choke point for THIS tool's mailbox directory creation
    (post's recipient trees, ack's read/ dir). Resolves symlinks AND junctions
    first (via _within), so a reparse-point dir that escapes the mailbox tree
    while its lexical path reads as inside is REFUSED fail-closed.
    """
    if not _within(root, target):
        raise MailError(
            f"refusing to create {target}: it resolves OUTSIDE the mailbox "
            f"root {root} (symlink/junction escape); nothing was written.")
    target.mkdir(parents=True, exist_ok=True)


def _guarded_enum_dir(root: Path, d: Path) -> Path:
    """Return `d` for enumeration, REFUSING an existing-but-escaping dir.

    The read-side sibling of _guarded_mkdir: list / read / peek (all through
    _list_inbox/_list_read) must not glob/read/print the content of a
    junctioned/symlinked inbox that resolves OUTSIDE the mailbox root. A
    MISSING dir is fine and returned as-is (the caller treats absence as
    empty); only an EXISTING dir that escapes once resolved is refused.
    """
    if d.exists() and not _within(root, d):
        raise MailError(
            f"refusing to enumerate {d}: it resolves OUTSIDE the mailbox root "
            f"{root} (symlink/junction escape); nothing was read.")
    return d


def _ensure_tree(root: Path) -> None:
    """Bootstrap EVERY role's {inbox,read} (a test/setup helper; guarded).

    No longer on the post path: post_message creates only its addressed
    recipients' trees (_ensure_recipient_trees), so a junctioned UNADDRESSED
    role can never be mkdir'd through on a post that never names it.
    """
    for role in SINGULAR_INBOX_ROLES:
        _guarded_mkdir(root, root / role / "inbox")
        _guarded_mkdir(root, root / role / "read")


def _ensure_recipient_trees(root: Path, inboxes: list[Path]) -> None:
    """Create the inbox/read dirs for ONLY this post's validated recipients.

    Every dir goes through the _within-guarded choke point (_guarded_mkdir).
    The recipients' delivery targets were already containment-checked in
    post_message BEFORE this runs, so a refusal there left the root untouched.
    """
    for inbox in inboxes:
        _guarded_mkdir(root, inbox)
        _guarded_mkdir(root, inbox.parent / "read")


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


# --- addressing: every role is a singular inbox (21-D) ---------------------

def _split_target(token: str) -> tuple[str, str | None]:
    """Parse one recipient token into (role, session_id_or_None).

    Every role is a singular inbox now, so the returned session_id is ALWAYS
    None (the tuple shape is kept so the delivery helpers stay unchanged). A
    ``:<session_id>`` suffix on ANY role is REJECTED with an actionable message
    -- never silently ignored, never silently misrouted (D2). The rejection is
    checked BEFORE the role-validity check so a stale `orchestrator:<sid>`
    address gets the specific retirement message rather than a generic
    "invalid recipient".
    """
    if ":" in token:
        raise MailError(
            f"{_RETIRED_PREFIX}; {token!r} carries a ':<session_id>' suffix. "
            + _SINGULAR_HINT)
    if token in VALID_TO:
        return (token, None)
    raise MailError(
        "invalid recipient " + repr(token)
        + "; valid roles: " + "|".join(VALID_TO))


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


def _recipient_label(role: str) -> str:
    """The `to:` frontmatter label -- always the bare role (21-D)."""
    return role


def _inbox_for_target(root: Path, role: str) -> Path:
    """The concrete inbox dir for a role (singular for every role).

    Takes NO session parameter (Codex R3 Minor 1): an address-capable helper
    that accepted a session selector and ignored it would be an accept-and-
    ignore surface even though the public paths reject upstream -- and the one
    rule this arc enforces everywhere is reject, never ignore.
    """
    if role in SINGULAR_INBOX_ROLES:
        return root / role / "inbox"
    raise MailError(
        "invalid recipient " + repr(role) + "; valid roles: " + "|".join(VALID_TO))


def _reject_retired_session_selector(sid: str | None, form: str) -> None:
    """REJECT a stale session selector on ANY read/ack path (D2, read side).

    The read-side twin of _split_target's `:<sid>` rejection, shared by the CLI
    flag AND the `ack_message` library argument: a caller carrying the retired
    per-generation selector must LEARN, not be silently ignored. Accept-and-
    ignore is the exact silent misroute D2 exists to prevent -- the caller would
    believe it addressed one generation while the singular inbox was read or
    acked. Nothing is listed, printed, moved, or acked before this fires.
    """
    if sid is None:
        return
    raise MailError(
        f"{_RETIRED_PREFIX}; the session selector {sid!r} ({form}) no longer "
        "selects an orchestrator generation. Every role is a singular inbox -- "
        "address it by bare role with no session. Nothing was read or acked.")


def _role_inbox_dir(root: Path, role: str) -> Path:
    """The inbox dir for a read/list/peek/ack op (singular for every role)."""
    if role in SINGULAR_INBOX_ROLES:
        return root / role / "inbox"
    raise MailError(
        "invalid role " + repr(role) + "; valid roles: " + "|".join(VALID_TO))


def _role_read_dir(root: Path, role: str) -> Path:
    """The read (ack archive) dir for a role (singular for every role)."""
    if role in SINGULAR_INBOX_ROLES:
        return root / role / "read"
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
             posted: str, msg_id: str, thread: str | None, body: str) -> str:
    # msg-id: a per-message nonce (one per delivery) -- post-verified's D1
    # discriminator, so a header-twin cannot answer for THIS message.
    lines = [
        "---",
        f"from: {sender}",
        f"to: {recipient}",
        f"type: {mtype}",
        f"subject: {subject}",
        f"posted: {posted}",
        f"msg-id: {msg_id}",
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
    except (OSError, UnicodeDecodeError):
        # Unreadable OR not UTF-8: no frontmatter. A corrupt unrelated file
        # among the read/ candidates must not abort a verify (Reviewer A R2 F2).
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
    posted_ids: list[tuple[Path, str, str, str]] | None = None,
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

    CONTAINMENT (T3): every delivery target is checked with _within BEFORE any
    directory is created or temp staged, so a junctioned/symlinked recipient
    inbox is refused with the mailbox root untouched; only the ADDRESSED
    recipients' trees are then created (_ensure_recipient_trees, guarded).

    ``posted_ids`` (optional out-param): if a list is passed it is EXTENDED with
    one ``(final_path, to_label, posted, msg_id)`` record per committed
    delivery -- the WRITE-side discriminators post-verified uses to confirm THE
    specific message it wrote. Every other caller leaves it None.
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
    # Subject length cap (operator-directed 2026-08-12). Subjects had drifted
    # into abstracts -- the worst observed was 839 chars, and ALL THREE roles
    # (both directors + the orchestrator) drifted the same way, which is the
    # signature of a norm that needs a mechanical guard rather than a firmer
    # convention. Two concrete costs: `_slugify` truncates the filename to
    # `_SLUG_MAX` (40), so everything past that is invisible in a listing and reaches no
    # reader; and a subject carrying the argument duplicates the body it sits
    # on top of. The cap was 80 from 2026-08-12; the operator raised it to 120
    # on 2026-11-03, the figure the harness template's lineage uses. Either is
    # well past git's own 50-char convention, so anything tripping this is an
    # abstract, not a tight subject.
    if len(subject) > SUBJECT_MAX_CHARS:
        raise MailError(
            f"subject is {len(subject)} chars; the cap is {SUBJECT_MAX_CHARS}. "
            "A subject NAMES the message; the body CARRIES it. Put the finding, "
            "the evidence and the reasoning in the body -- they are why the "
            "body exists. Nothing was written."
        )
    # Parse recipients to (role, None) pairs. A retired `:<session_id>` suffix
    # is REJECTED here (21-D), before anything is written.
    pairs = _parse_recipient_pairs(recipients)
    # L1 governance lock: decision_request must address ONLY the operator. Fires
    # on the PARSED role BEFORE any inbox resolution, so a decision_request to
    # orchestrator is refused here regardless of anything downstream.
    if mtype == "decision_request" and any(role != "operator" for role, _ in pairs):
        raise MailError(
            "L1: type 'decision_request' may be addressed ONLY to operator "
            "(role->role traffic is fyi|status|query|return_report). "
            "Nothing was written."
        )

    now = _now()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    posted = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = _slugify(subject)

    # Resolve each pair to its concrete inbox and de-dupe by the RESOLVED inbox
    # path, so a repeated recipient collapses to ONE delivery. Every role is
    # singular, so the label is always the bare role.
    resolved: list[tuple[Path, str]] = []
    seen_inboxes: set[str] = set()
    for role, _sid in pairs:
        inbox = _inbox_for_target(root, role)
        key = str(inbox)
        if key in seen_inboxes:
            continue
        seen_inboxes.add(key)
        resolved.append((inbox, _recipient_label(role)))

    # Precompute every (final path, content) BEFORE writing anything so a
    # multi-recipient post delivers all-or-nothing (atomicity): stage temps in
    # each destination dir, then os.replace each into place only once every
    # temp wrote cleanly. A failure mid-stage removes the temps -> no partial.
    # THE PRE-WRITE CONTAINMENT GUARD (T3): each delivery TARGET is resolved
    # and refused if it escapes the mailbox root through a symlink/junction --
    # here, before any dir is created or temp staged, so a refusal leaves the
    # root byte-for-byte untouched.
    targets: list[tuple[Path, str]] = []
    records: list[tuple[Path, str, str, str]] = []
    for inbox, label in resolved:
        final = _unique_path(inbox, stamp, sender, slug)
        if not _within(root, final):
            raise MailError(
                f"post refused: delivery target {final} resolves OUTSIDE the "
                f"mailbox root {root} (symlink/junction escape); nothing was "
                "written.")
        msg_id = secrets.token_hex(8)
        targets.append(
            (final, _compose(sender, label, mtype, subject, posted, msg_id,
                             thread, body)))
        records.append((final, label, posted, msg_id))

    # All targets contained: NOW create the trees for THIS post's recipients
    # ONLY (never an unaddressed role's -- a junctioned unaddressed role dir
    # must not be mkdir'd through on a post that never names it).
    _ensure_recipient_trees(root, [inbox for inbox, _label in resolved])

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

    if posted_ids is not None:
        committed_set = set(committed)
        posted_ids.extend(r for r in records if r[0] in committed_set)
    return committed


def ack_message(root: Path, role: str, filename: str,
                session_id: str | None = None) -> Path:
    """Ack one message: move <inbox>/<filename> -> <read>/ (returns the dest).

    The single ack path (the CLI's cmd_read and the UI both call THIS). Uses
    _unique_dest so an archived message of the same name is never overwritten
    (ack must never delete history). filename MUST be a bare basename --
    traversal attempts are rejected (L3 mail custody: the ack can never reach
    outside the role's own inbox). `session_id` is RETIRED (21-D: every role is
    a singular inbox): the parameter survives only so a stale in-process caller
    gets the actionable MailError instead of a TypeError -- passing anything but
    None is REFUSED before any move (D2 on the library entry point; an ignored
    selector would silently ack the singular inbox while the caller believed it
    addressed a generation). BOTH ends of the move are containment-guarded
    (T3): the SOURCE inbox (a junctioned inbox cannot make ack read/remove an
    EXTERNAL file) and the DEST read/ dir (via _guarded_mkdir). Raises MailError
    on an invalid role, a retired session_id, a traversal attempt, a missing
    file, or a containment escape.
    """
    if role not in VALID_TO:
        raise MailError(
            "invalid role " + repr(role) + "; valid roles: " + "|".join(VALID_TO))
    _reject_retired_session_selector(session_id, "ack_message session_id=")
    if filename != Path(filename).name or "/" in filename or "\\" in filename:
        raise MailError(f"refusing non-basename filename {filename!r}")
    inbox_dir = _role_inbox_dir(root, role)
    read_dir = _role_read_dir(root, role)
    if not _within(root, inbox_dir):
        raise MailError(
            f"refusing to ack from {inbox_dir}: it resolves OUTSIDE the mailbox "
            f"root {root} (symlink/junction escape); nothing was moved.")
    src = inbox_dir / filename
    if not src.is_file():
        raise MailError(
            f"no inbox message named {filename!r} for role {role}")
    if not _within(root, src):
        # A message FILE that is itself a link out of the tree (Reviewer A R1
        # F2): refused like an escaping dir. Nothing is moved.
        raise MailError(
            f"refusing to ack {src}: it resolves OUTSIDE the mailbox root "
            f"{root} (symlink/junction escape); nothing was moved.")
    _guarded_mkdir(root, read_dir)  # guard the DEST side
    dest = _unique_dest(read_dir, src.name)
    src.rename(dest)
    return dest


# --- subcommands -----------------------------------------------------------

def _read_session_map(root: Path) -> dict[str, str]:
    """Best-effort {role: session_name} from <comms_root>/.sessions.json.

    D57 C2 (the wake-on-mail cross-session cue, harness-architecture section
    3): read-only support for the `ping ->` line cmd_post prints after a
    successful post. The launcher (scripts/start_directors.ps1
    Save-SessionMap) writes this file WITHOUT a BOM, but decode with
    'utf-8-sig' defensively (a BOM-prefixed file must not look "malformed").
    A missing file, empty file, malformed JSON, a non-dict root, or a
    per-role entry with a missing/non-string/empty session_name are ALL
    treated as "no session recorded" for that role -- this function must
    NEVER raise (the post it supports has already succeeded by the time this
    runs) and never change cmd_post's exit code.
    """
    path = root / ".sessions.json"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):  # not UTF-8 -> no map (R3 F4)
        return {}
    try:
        obj = json.loads(text)
    except ValueError:
        return {}
    if not isinstance(obj, dict):
        return {}
    out: dict[str, str] = {}
    for role, entry in obj.items():
        if isinstance(entry, dict):
            name = entry.get("session_name")
            if isinstance(name, str) and name:
                out[role] = name
    return out


def _ping_line(role: str, session_map: dict[str, str]) -> str:
    """The one `ping ->` line for `role` (D57 C2; the mechanical wake nudge).

    `operator` is ALWAYS the GUI/relay form -- the operator role has no
    session to SendMessage (never look it up, even if the map carries a
    stray entry for it). Every other role: the recorded session_name if
    present, else "no session recorded" (missing role, missing/malformed
    map -- indistinguishable to the sender, and that is fine: read-only,
    never fails the post).
    """
    if role == "operator":
        return "ping -> operator: no session (GUI/relay)"
    name = session_map.get(role)
    if name:
        return f'ping -> SendMessage to="{name}"'
    return f"ping -> {role}: no session recorded"


def cmd_post(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    sender = args.__dict__["from"]
    body = _resolve_body(args)
    # Split here; post_message validates (the single write path owns the rules).
    recipients = [r.strip() for r in args.to.split(",") if r.strip()]
    finals = post_message(
        root, sender, recipients, args.type, args.subject, body, args.thread)
    _print_posted(root, finals)
    return 0


def _print_posted(root: Path, finals: list[Path],
                  verified_at: dict[Path, Path] | None = None) -> None:
    """The per-delivery console lines shared by post and post-verified.

    ``posted ->`` then ``ping ->`` per delivery. post-verified passes
    ``verified_at`` (final -> where the message ACTUALLY is now -- the inbox,
    or the read/ file a receiver acked it into) and gets a third line,
    ``verified -> <absolute path>``. The ping line is READ-ONLY output
    computed AFTER the post already succeeded: a missing/malformed session map
    must never fail the post or change its exit code (D57 C2).
    """
    session_map = _read_session_map(root)
    for final in finals:
        role = final.parent.parent.name
        print(f"posted -> {role}/inbox/{_ascii(final.name)}")
        print(_ascii(_ping_line(role, session_map)))  # R4 F3
        if verified_at is not None:
            where = verified_at.get(final) or final
            print(_ascii(f"verified -> {where.absolute()}"))


# --- post-verified: post + confirm the landing in ONE call ------------------
# (harness-template merge 2026-11-03, T3; ported from the template's
# role_mail.py at master 4335ff6.) The manual discipline this mechanizes is
# "post, then go look whether the file is really where you meant it" --
# skipped exactly when it matters, and the failure it catches is silent by
# nature (the post reports success either way): the 2026-06-21 incident, where
# a post from a worktree cwd landed in the worktree's gitignored comms/.

def _same_dir(a: Path, b: Path) -> bool:
    """True iff two paths name the same directory (existing or not).

    samefile when both exist; otherwise the RESOLVED paths are compared, so a
    not-yet-created child reached through a symlinked/junctioned parent still
    matches its real spelling (Reviewer A R1 F5).
    """
    with contextlib.suppress(OSError, ValueError):
        if a.exists() and b.exists():
            return os.path.samefile(str(a), str(b))

    def _norm(p: Path) -> str:
        try:
            resolved = Path(p).resolve()
        except (OSError, RuntimeError, ValueError):
            resolved = Path(os.path.abspath(str(p)))
        return os.path.normcase(str(resolved))

    return _norm(a) == _norm(b)


def _linked_checkout_primary(repo_root: Path) -> Path | None:
    """The PRIMARY checkout behind a linked working copy, or None.

    A linked working copy (a git worktree) carries a ``.git`` FILE (a
    ``gitdir:`` pointer) where a primary checkout has a ``.git`` directory.
    Used only to NOTICE that a DEFAULTED mailbox root belongs to the linked
    copy -- posting into one on purpose is legitimate, so this never fails a
    post. Any problem reading the pointer yields None (advisory, never raises).
    """
    try:
        marker = repo_root / ".git"
        if not marker.is_file():
            return None
        text = marker.read_text(encoding="utf-8", errors="replace").strip()
        prefix = "gitdir:"
        if not text.lower().startswith(prefix):
            return None
        pointer = Path(text[len(prefix):].strip())
        if not pointer.is_absolute():
            # A relative pointer is relative to the CHECKOUT, never the
            # process cwd (Reviewer A R1 F6).
            pointer = Path(os.path.normpath(str(repo_root / pointer)))
        # Only the linked-worktree shape <primary>/.git/worktrees/<name>
        # names a primary checkout. A submodule pointer (.git/modules/<name>,
        # and any worktree of one) does not, so it gets no notice rather
        # than a wrong one (Reviewer A R4 F4).
        admin = pointer.parent
        if admin.name == "worktrees" and admin.parent.name == ".git":
            return admin.parent.parent
    except (OSError, ValueError):
        return None
    return None


def _read_sibling(inbox_path: Path) -> Path | None:
    """For an ``.../inbox/<file>`` path, its ``.../read/<file>`` sibling.

    None when the path is not directly under an ``inbox/`` directory.
    """
    if inbox_path.parent.name != "inbox":
        return None
    return inbox_path.parent.parent / "read" / inbox_path.name


def _landing_candidates(inbox_final: Path, by_nonce: bool) -> list[Path]:
    """Where a delivered message may legitimately be now, in search order.

    The addressed inbox path, then its ``read/`` sibling (a receiver acked it
    in the verify gap). When searching BY NONCE, also the ``read/<stem>-N.md``
    names ``_unique_dest`` gives an ack whose plain name was already taken --
    e.g. a same-second, same-subject twin acked earlier (Reviewer A R1 F1).
    """
    out = [inbox_final]
    sibling = _read_sibling(inbox_final)
    if sibling is None:
        return out
    out.append(sibling)
    if by_nonce and sibling.parent.is_dir():
        pat = re.compile(re.escape(sibling.stem) + r"-(\d+)\.md")
        suffixed = []
        for cand in sibling.parent.glob(sibling.stem + "-*.md"):
            m = pat.fullmatch(cand.name)
            if m:
                suffixed.append((int(m.group(1)), cand))
        out.extend(c for _n, c in sorted(suffixed))
    return out


def _locate_landing(inbox_final: Path, want_msg_id: str | None = None,
                    root: Path | None = None
                    ) -> tuple[Path | None, dict[str, str]]:
    """(where the message REALLY is now, its frontmatter), or (None, {}).

    With ``want_msg_id`` the message is located by its nonce among the
    candidates (falling back to the first readable candidate, so a mismatch
    is REPORTED as a header-twin rather than as "did not land"). A candidate
    that vanishes between its existence check and its read was acked in that
    instant: the search moves on to the read/ candidates instead of reporting
    it unreadable (Reviewer A R1 F3). Two passes cover an ack landing between
    passes: the second re-globs, so an ack archived as ``read/<stem>-N.md``
    after the first pass listed its candidates is found there. A nonce match
    from EITHER pass wins; the fallback is returned only after BOTH passes
    miss, never at the end of the first (an older archived twin would
    otherwise pre-empt the retry -- Reviewer A R2 F1).

    With ``root``, a candidate that resolves OUTSIDE it is never READ (a
    symlinked archive twin must not be opened while searching -- Reviewer A
    R3 F2); it can still become the fallback, with empty frontmatter, so a
    landing that only exists outside is reported as such by the caller.
    """
    fallback: tuple[Path, dict[str, str]] | None = None
    for _attempt in range(2):
        for cand in _landing_candidates(inbox_final, want_msg_id is not None):
            if not cand.is_file():
                continue
            if root is not None and not _within(root, cand):
                if fallback is None:
                    fallback = (cand, {})
                continue
            fm = _read_frontmatter(cand)
            if not fm and not cand.is_file():
                continue  # moved (acked) between the check and the read
            if want_msg_id is None or fm.get("msg-id") == want_msg_id:
                return cand, fm
            if fallback is None:
                fallback = (cand, fm)
    if fallback is not None:
        return fallback
    return None, {}


def _actual_landing(inbox_final: Path) -> Path | None:
    """Where the message REALLY is now, or None if it is nowhere.

    The addressed inbox path, or -- if a receiver acked it in the verify gap --
    the ``read/`` sibling (an ack is normal traffic, not a delivery failure).
    """
    return _locate_landing(inbox_final)[0]


def _landed_in_expected(landed_dir: Path, expected_inbox: Path) -> bool:
    """True iff landed_dir is the addressed inbox OR its ``read/`` sibling."""
    if _same_dir(landed_dir, expected_inbox):
        return True
    if expected_inbox.name == "inbox":
        return _same_dir(landed_dir, expected_inbox.parent / "read")
    return False


def _verify_landing(root: Path, final: Path, sender: str, mtype: str,
                    subject: str, want_posted: str | None = None,
                    want_msg_id: str | None = None) -> str | None:
    """Why `final` is NOT a valid landing under `root`, or None if it is.

    The problem string of _check_landing (which also returns where the message
    was found and its frontmatter, for the caller's accounting).
    """
    return _check_landing(root, final, sender, mtype, subject, want_posted,
                          want_msg_id)[0]


def _check_landing(root: Path, final: Path, sender: str, mtype: str,
                   subject: str, want_posted: str | None = None,
                   want_msg_id: str | None = None
                   ) -> tuple[str | None, Path | None, dict[str, str]]:
    """(problem-or-None, where it landed, its frontmatter) for one delivery.

    Checks the message is really on disk (in its addressed ``inbox/`` OR the
    ``read/`` sibling a receiver may have acked it into), really CONTAINED in
    the mailbox root once symlinks/junctions are RESOLVED, really in the inbox
    its own ``to:`` header names, really carries what was asked for, AND --
    when the write-side discriminators are supplied (``want_posted`` /
    ``want_msg_id``) -- really is THE specific message just composed rather
    than a header-twin sharing from/to/type/subject.
    """
    landed, fm = _locate_landing(final, want_msg_id, root)
    if landed is None:
        return f"did not land at all: {final} is not there", None, {}
    if not _within(root, landed):
        return f"landed OUTSIDE the mailbox root: {landed}", landed, fm
    if not fm:
        return f"landed unreadable (no frontmatter): {landed}", landed, fm
    label = fm.get("to", "")
    try:
        role, _sid = _split_target(label)
        expected = _inbox_for_target(root, role)
    except MailError as exc:
        return (f"landed carrying an unusable 'to: {label}' ({exc}): {landed}",
                landed, fm)
    if not _landed_in_expected(landed.parent, expected):
        return (f"landed in the WRONG inbox: {landed} -- addressed to "
                f"{label!r}, whose inbox is {expected}"), landed, fm
    # The frontmatter reader strips each value, so compare against the
    # stripped request (a subject with surrounding spaces delivers fine and
    # must verify fine -- Reviewer A R1 F4).
    for field, want in (("from", sender), ("type", mtype),
                        ("subject", subject)):
        if fm.get(field) != str(want).strip():
            return (f"landed with {field}={fm.get(field)!r}, expected "
                    f"{want!r}: {landed}"), landed, fm
    # D1 per-message discriminator: a landing matching the shared headers but
    # carrying a DIFFERENT stamp/nonce is a header-twin, not our message.
    # Skipped when the discriminators are absent (a mocked post / a legacy
    # file), degrading to the header-only check.
    if want_posted is not None and fm.get("posted") != want_posted:
        return (f"landed with posted={fm.get('posted')!r}, expected "
                f"{want_posted!r} (header-twin, not the message just posted): "
                f"{landed}"), landed, fm
    if want_msg_id is not None and fm.get("msg-id") != want_msg_id:
        return (f"landed with msg-id={fm.get('msg-id')!r}, expected "
                f"{want_msg_id!r} (header-twin, not the message just posted): "
                f"{landed}"), landed, fm
    return None, landed, fm


def _landing_matches_request(token: str, landed: list[tuple[str, str]],
                             posted_msg_ids: set[str] | None = None) -> bool:
    """True iff a requested --to token is answered by one of the landed files.

    ``landed`` is ``(to_label, msg_id)`` read off the files that really landed.
    A token matches when some landed file carries its role label AND -- when
    the write-side msg-id set is known and the landed file carries a msg-id --
    that msg-id belongs to THIS post. When the posted set is unknown (a mocked
    post) or the landed file has no msg-id, the match degrades to label-only.
    """
    role, _ = _split_target(token)
    for lbl, mid in landed:
        if lbl != role:
            continue
        if posted_msg_ids and mid and mid not in posted_msg_ids:
            continue  # right label, but not one of THIS post's messages
        return True
    return False


def cmd_post_verified(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    # The same predicate _comms_root uses: an EMPTY --comms-root also selects
    # the default, so it gets the default's notice (Reviewer A R3 F3).
    defaulted = not getattr(args, "comms_root", None)
    expect = getattr(args, "expect_root", None)
    mismatch = expect is not None and not _same_dir(root, Path(expect))
    # The notice goes out FIRST, so when the root is also wrong it stands next
    # to the error explaining how the root got that way. Suppressed when
    # --expect-root was given and MATCHED: the caller stated this exact intent.
    if defaulted and (expect is None or mismatch):
        primary = _linked_checkout_primary(_REPO_ROOT)
        if primary is not None:
            print(
                _ascii(
                    f"notice: mailbox root defaulted to {Path(root).absolute()},"
                    f" which belongs to a linked working copy. The primary "
                    f"copy's mailbox is {(primary / 'comms').absolute()}. Pass "
                    "--comms-root if you meant that one."),
                file=sys.stderr)
    if mismatch:
        # Checked BEFORE the write: a root mismatch means the message would
        # land in a mailbox nobody is reading, so do not write it at all.
        raise MailError(
            f"mailbox root mismatch: resolved {Path(root).absolute()} but "
            f"--expect-root named {Path(expect).absolute()}. Nothing was "
            "written. Pass --comms-root to choose the root explicitly.")

    sender = args.__dict__["from"]
    body = _resolve_body(args)
    recipients = [r.strip() for r in args.to.split(",") if r.strip()]
    posted_ids: list[tuple[Path, str, str, str]] = []
    finals = post_message(
        root, sender, recipients, args.type, args.subject, body, args.thread,
        posted_ids=posted_ids)

    # The WRITE-side per-message discriminators, keyed by the exact final path
    # this post returned (independent of what is read back -- that is what
    # makes them a discriminator rather than a self-consistency tautology).
    want_by_final = {f: (posted, mid) for f, _lbl, posted, mid in posted_ids}
    posted_msg_ids = {mid for _f, _lbl, _p, mid in posted_ids}

    # ONE locate+read per delivery: the same (path, frontmatter) feeds the
    # landing check, the per-recipient accounting and the verified -> line,
    # so an ack between two separate reads cannot make them disagree
    # (Reviewer A R1 F3/F7). The read follows the message to the read/ file
    # a receiver may have acked it into.
    problems: list[str] = []
    landed: list[tuple[str, str]] = []
    verified_at: dict[Path, Path] = {}
    for f in finals:
        want_posted, want_msg_id = want_by_final.get(f, (None, None))
        problem, where, lfm = _check_landing(
            root, f, sender, args.type, args.subject, want_posted, want_msg_id)
        if problem is not None:
            problems.append(problem)
        if where is not None:
            verified_at[f] = where
            landed.append((lfm.get("to", ""), lfm.get("msg-id", "")))
    # Tie each requested recipient to THIS post's messages, not the shared
    # label alone.
    for token in dict.fromkeys(recipients):
        if not _landing_matches_request(token, landed, posted_msg_ids):
            landed_labels = [lbl for lbl, _ in landed]
            problems.append(
                f"nothing landed for requested recipient {token!r} "
                f"(landed: {', '.join(landed_labels) or 'nothing'})")
    if problems:
        raise VerificationError(
            "post could NOT be verified -- "
            + "; ".join(problems)
            + ". The write path reported success, so treat the message as "
              "NOT delivered until this is resolved.")
    _print_posted(root, finals, verified_at=verified_at)
    return 0


def _contained_files(root: Path, d: Path) -> list[Path]:
    """The *.md files of `d`, REFUSING the lot if any resolves outside `root`.

    The per-FILE half of the enumeration guard (Reviewer A R1 F2): a contained
    inbox holding a message file that is itself a link out of the tree is
    refused BEFORE any path is returned, so nothing is listed, read or printed.
    """
    paths = sorted(d.glob("*.md")) if d.is_dir() else []
    for path in paths:
        if not _within(root, path):
            raise MailError(
                f"refusing to enumerate {path}: it resolves OUTSIDE the mailbox "
                f"root {root} (symlink/junction escape); nothing was read.")
    return paths


def _list_inbox(root: Path, role: str) -> list[Path]:
    # The enumeration choke shared by read/list/peek -- guarded FIRST so a
    # junctioned inbox (or an escaping message file) is refused BEFORE any
    # glob result is read or printed (T3).
    inbox = _guarded_enum_dir(root, _role_inbox_dir(root, role))
    return _contained_files(root, inbox)


def _list_read(root: Path, role: str) -> list[Path]:
    rd = _guarded_enum_dir(root, _role_read_dir(root, role))
    return _contained_files(root, rd)


def cmd_list(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    if args.role not in VALID_TO:
        raise MailError(
            "invalid --role " + repr(args.role)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    _reject_retired_session_selector(getattr(args, "session", None), "--session")
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
    _reject_retired_session_selector(getattr(args, "session", None), "--session")
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
    for path in targets:
        _print_message(path)
        ack_message(root, args.role, path.name)
    print(f"acked {len(targets)} message(s); moved inbox -> read.")
    return 0


def cmd_peek(args: argparse.Namespace) -> int:
    root = _comms_root(args)
    if args.role not in VALID_TO:
        raise MailError(
            "invalid --role " + repr(args.role)
            + "; valid roles: " + "|".join(VALID_TO)
        )
    _reject_retired_session_selector(getattr(args, "session", None), "--session")
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


def _add_post_arguments(p: argparse.ArgumentParser) -> None:
    """The message arguments shared by `post` and `post-verified`.

    Single-sourced so `post-verified` is a drop-in for `post` -- swapping the
    subcommand word can never silently change how the message is addressed.
    """
    _add_comms_root(p)
    p.add_argument("--from", required=True, dest="from",
                   help="sender: " + "|".join(VALID_FROM))
    p.add_argument(
        "--to", required=True,
        help="recipient(s), comma-separated: " + "|".join(VALID_TO)
        + " (every role is a singular inbox; a :<session_id> suffix is retired"
          " and refused)")
    p.add_argument("--type", required=True,
                   help="message type: " + "|".join(VALID_TYPES))
    p.add_argument("--subject", required=True)
    p.add_argument("--body", default=None, help="inline body text")
    p.add_argument("--body-file", dest="body_file", default=None,
                   help="read body from this file")
    p.add_argument("--thread", default=None, help="optional thread slug")


def build_parser() -> argparse.ArgumentParser:
    parser = _AsciiArgumentParser(
        description="Inter-role file mailbox (comms Stage 1).")
    parser.add_argument(
        "--comms-root", default=None,
        help="mailbox root (default: <repo>/comms; tests pass tmp_path)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_post = sub.add_parser("post", help="post a message to recipient inbox(es)")
    _add_post_arguments(p_post)
    p_post.set_defaults(func=cmd_post)

    p_verified = sub.add_parser(
        "post-verified",
        help="post AND confirm the message landed where it was addressed")
    _add_post_arguments(p_verified)
    p_verified.add_argument(
        "--expect-root", dest="expect_root", default=None,
        help="fail BEFORE writing unless the resolved mailbox root is this "
             "directory (guards against posting into the wrong checkout)")
    p_verified.set_defaults(func=cmd_post_verified)

    # The flag is KEPT (not deleted) purely so a stale caller gets the actionable
    # retirement message instead of argparse's bare "unrecognized arguments".
    session_help = ("retired (21-D): per-generation orchestrator addressing is "
                    "gone; every role is a singular inbox. Passing this fails "
                    "with an actionable message instead of being ignored.")

    p_list = sub.add_parser("list", help="list a role's inbox")
    _add_comms_root(p_list)
    p_list.add_argument("--role", required=True, help="|".join(VALID_TO))
    p_list.add_argument("--session", default=None, help=session_help)
    p_list.add_argument("--unread-only", action="store_true",
                        help="(default already lists only the inbox)")
    p_list.set_defaults(func=cmd_list)

    p_read = sub.add_parser("read", help="print + ack message(s) (inbox -> read)")
    _add_comms_root(p_read)
    p_read.add_argument("--role", required=True, help="|".join(VALID_TO))
    p_read.add_argument("--session", default=None, help=session_help)
    g = p_read.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="read+ack the whole inbox")
    g.add_argument("--id", default=None, help="read+ack one message by filename")
    p_read.set_defaults(func=cmd_read)

    p_peek = sub.add_parser("peek", help="print unread WITHOUT acking")
    _add_comms_root(p_peek)
    p_peek.add_argument("--role", required=True, help="|".join(VALID_TO))
    p_peek.add_argument("--session", default=None, help=session_help)
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
