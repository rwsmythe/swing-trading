"""Localhost mail UI over the comms Stage 1 file mailbox (comms Stage 1.5).

A single-file FastAPI + HTMX app that is BOTH the operator's mail client and a
whole-bus observability view over scripts/role_mail.py's file mailbox. On-demand
only: run it while you are at the computer, close it when you are done -- the
durable file mailbox absorbs everything in between. The server holds NO state.

Hard locks (see docs/comms-mail-ui-dispatch-brief.md section 2):
  L1  compose never offers decision_request and server-stamps from=operator.
  L2  nothing under swing/ is touched (this lives in scripts/).
  L3  the UI acks ONLY comms/operator/inbox/; never moves/acks/deletes any
      director mailbox file; nothing here deletes a message ever.
  L4  every mail write goes through role_mail.post_message / ack_message.
  L5  the launch endpoint runs exactly one fixed argv (enum-validated).

Run it (from the repo root):
    python scripts/comms_ui.py [--port 8765] [--comms-root PATH] [--no-browser]
Binds 127.0.0.1 only. Page content is UTF-8; server console prints stay ASCII
(the Windows cp1252 stdout gotcha).
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
import threading
import webbrowser
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from jinja2 import DictLoader, Environment, select_autoescape

# Import role_mail the not-a-package way the tests do (scripts/ is not a
# package); role_mail.post_message / ack_message are the single write path (L4).
_SCRIPTS_DIR = Path(__file__).resolve().parent
_RM_SPEC = importlib.util.spec_from_file_location(
    "role_mail", _SCRIPTS_DIR / "role_mail.py")
role_mail = importlib.util.module_from_spec(_RM_SPEC)
_RM_SPEC.loader.exec_module(role_mail)

# --- constants -------------------------------------------------------------

HOST = "127.0.0.1"  # loopback ONLY (hardcoded; never bind a routable address)
DEFAULT_PORT = 8765  # swing web owns 8080
STALE_DAYS = 7  # matches harness_probe COMMS_UNREAD_AGE_DAYS_MAX
BUS_ROLES = ("charc", "rd")  # the director bus (read-only)
HISTORY_CAP = 50
# compose type allowlist -- decision_request is DELIBERATELY ABSENT (L1 belt)
COMPOSE_TYPES = ("fyi", "status", "query", "return_report")


# --- message model ---------------------------------------------------------

@dataclass(frozen=True)
class Message:
    role: str            # mailbox owner (charc/rd/operator)
    filename: str
    frm: str
    to: str
    mtype: str
    subject: str
    posted: str          # frontmatter 'posted' (display) or '?'
    thread: str
    body: str
    age_days: int        # ceil days since posted (from filename stamp)
    stale: bool          # strictly older than STALE_DAYS
    is_decision_request: bool


def _split_message(text: str) -> tuple[dict[str, str], str]:
    """Frontmatter dict + body from a message file's text.

    Degrades gracefully: a file with no leading '---' yields ({}, whole-text)
    so a malformed message still renders (filename + raw fallback upstream).
    """
    if not text.startswith("---"):
        return {}, text
    rest = text.split("\n", 1)[1] if "\n" in text else ""
    fm: dict[str, str] = {}
    body_lines: list[str] = []
    in_fm = True
    for line in rest.split("\n"):
        if in_fm and line.strip() == "---":
            in_fm = False
            continue
        if in_fm:
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                if key not in fm:  # first occurrence wins (injected dupes ignored)
                    fm[key] = val.strip()
        else:
            body_lines.append(line)
    return fm, "\n".join(body_lines).strip("\n")


def _posted_dt(filename: str, path: Path) -> datetime | None:
    """Posted time from the leading UTC stamp in a role_mail filename.

    Filenames are '<yyyymmddTHHMMSSZ>-<from>-<slug>.md'; falls back to mtime.
    """
    stamp = filename.split("-", 1)[0]
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError:
            return None


def _message_from_path(path: Path, role: str, now: datetime) -> Message:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    fm, body = _split_message(text)
    posted_dt = _posted_dt(path.name, path)
    if posted_dt is not None:
        delta = now - posted_dt
        age_days = max(0, math.ceil(delta.total_seconds() / 86_400))
        stale = delta.total_seconds() > STALE_DAYS * 86_400
    else:
        age_days = 0
        stale = False
    return Message(
        role=role,
        filename=path.name,
        frm=fm.get("from", "?"),
        to=fm.get("to", role),
        mtype=fm.get("type", "?"),
        # fall back to the filename so a malformed message still shows something
        subject=fm.get("subject") or path.name,
        posted=fm.get("posted", "?"),
        thread=fm.get("thread", ""),
        body=body,
        age_days=age_days,
        stale=stale,
        is_decision_request=fm.get("type") == "decision_request",
    )


def _inbox_messages(root: Path, role: str, now: datetime) -> list[Message]:
    inbox = root / role / "inbox"
    paths = sorted(inbox.glob("*.md")) if inbox.is_dir() else []
    return [_message_from_path(p, role, now) for p in paths]


def _read_messages(root: Path, role: str, now: datetime) -> list[Message]:
    rd = root / role / "read"
    paths = sorted(rd.glob("*.md")) if rd.is_dir() else []
    return [_message_from_path(p, role, now) for p in paths]


# --- templates (embedded; one reviewable file, no template dir) ------------

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title id="page-title">comms{% if operator_unread %} ({{ operator_unread }}){% endif %}</title>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script>
  // 4xx fragments must swap (the known htmx gotcha) -- validation errors render
  // as fragments in this standalone app too.
  htmx.config.responseHandling = [
    {code: "204", swap: false},
    {code: "[23].*", swap: true},
    {code: "[45].*", swap: true, error: true},
  ];
</script>
<style>
  body { font-family: system-ui, sans-serif; margin: 1rem; max-width: 70rem; }
  h2 { margin: 1.2rem 0 0.4rem; font-size: 1.05rem; }
  details.msg { border: 1px solid #ddd; border-radius: 4px; margin: 0.25rem 0;
                padding: 0.3rem 0.5rem; }
  details.msg summary { cursor: pointer; display: flex; gap: 0.8rem;
                        flex-wrap: wrap; align-items: baseline; }
  details.msg .posted { color: #666; font-variant-numeric: tabular-nums; }
  details.msg .from { font-weight: 600; }
  details.msg .type { color: #555; font-size: 0.85rem; }
  details.msg .subject { flex: 1; }
  details.msg.decision-request { border-color: #c0392b; background: #fdecea; }
  details.msg.decision-request .type { color: #c0392b; font-weight: 700; }
  details.msg.stale { border-color: #e67e22; }
  details.msg .age { color: #e67e22; font-size: 0.8rem; }
  pre.body { white-space: pre-wrap; background: #f7f7f7; padding: 0.5rem;
             border-radius: 4px; margin: 0.4rem 0 0.1rem; }
  .flash { padding: 0.4rem 0.6rem; border-radius: 4px; margin: 0.3rem 0; }
  .flash.ok { background: #eafaf1; border: 1px solid #2ecc71; }
  .flash.err { background: #fdecea; border: 1px solid #c0392b; }
  form.compose label { display: block; margin: 0.3rem 0; }
  .empty { color: #888; font-style: italic; }
  .strip { border: 1px solid #ccc; border-radius: 4px; padding: 0.6rem;
           margin: 0.6rem 0; }
</style>
</head>
<body>
<h1>comms</h1>

<section id="inbox-pane" hx-get="/panes/inbox" hx-trigger="every 5s"
         hx-swap="innerHTML">
  {% include "inbox_pane.html" %}
</section>

{% block compose %}{% endblock %}

<section id="bus-pane" hx-get="/panes/bus" hx-trigger="every 5s"
         hx-swap="innerHTML">
  {% include "bus_pane.html" %}
</section>

<details id="history-pane-wrap">
  <summary><h2 style="display:inline">History (read)</h2></summary>
  <section id="history-pane" hx-get="/panes/history" hx-trigger="every 5s"
           hx-swap="innerHTML">
    {% include "history_pane.html" %}
  </section>
</details>

{% block directors %}{% endblock %}
</body>
</html>
"""

_INBOX_PANE = """
{%- if oob -%}
<title id="page-title" hx-swap-oob="true">comms
{%- if operator_unread %} ({{ operator_unread }}){% endif -%}
</title>
{%- endif %}
<h2>Operator inbox -- {{ inbox_messages|length }} unread</h2>
{% if not inbox_messages %}<p class="empty">(inbox empty)</p>{% endif %}
{% for m in inbox_messages %}
<details class="msg
  {%- if m.is_decision_request %} decision-request{% endif %}">
  <summary>
    <span class="posted">{{ m.posted }}</span>
    <span class="from">{{ m.frm }}</span>
    <span class="type">{{ m.mtype }}</span>
    <span class="subject">{{ m.subject }}</span>
  </summary>
  <pre class="body">{{ m.body }}</pre>
</details>
{% endfor %}
"""

_BUS_PANE = """<h2>Director bus (read-only)</h2>
{% for role in bus_roles %}
<h3 style="font-size:0.95rem;margin:0.5rem 0 0.2rem">{{ role }} inbox
  -- {{ bus[role]|length }} unread</h3>
{% if not bus[role] %}<p class="empty">(empty)</p>{% endif %}
{% for m in bus[role] %}
<details class="msg
  {%- if m.is_decision_request %} decision-request{% endif %}
  {%- if m.stale %} stale{% endif %}">
  <summary>
    <span class="posted">{{ m.posted }}</span>
    <span class="from">{{ m.frm }}</span>
    <span class="type">{{ m.mtype }}</span>
    <span class="subject">{{ m.subject }}</span>
    {% if m.stale %}<span class="age">{{ m.age_days }}d stale</span>{% endif %}
  </summary>
  <pre class="body">{{ m.body }}</pre>
</details>
{% endfor %}
{% endfor %}
"""

_HISTORY_PANE = """
{%- if not history_messages %}<p class="empty">(no archived messages)</p>{% endif %}
{% for m in history_messages %}
<details class="msg">
  <summary>
    <span class="posted">{{ m.posted }}</span>
    <span class="from">{{ m.frm }}</span>
    <span class="type">{{ m.role }}&larr;{{ m.frm }}</span>
    <span class="subject">{{ m.subject }}</span>
  </summary>
  <pre class="body">{{ m.body }}</pre>
</details>
{% endfor %}
"""


def _make_env() -> Environment:
    return Environment(
        loader=DictLoader({
            "page.html": _PAGE,
            "inbox_pane.html": _INBOX_PANE,
            "bus_pane.html": _BUS_PANE,
            "history_pane.html": _HISTORY_PANE,
        }),
        autoescape=select_autoescape(["html"], default_for_string=True),
    )


# --- app factory -----------------------------------------------------------

def create_app(comms_root: Path, allow_launch: bool = True) -> FastAPI:
    """Build the mail-UI app over comms_root.

    The root is ALWAYS injected (tests pass tmp_path; never the real comms/).
    allow_launch gates the director-launch subprocess surface (T5).
    """
    comms_root = Path(comms_root)
    env = _make_env()
    app = FastAPI(title="comms mail UI")
    app.state.comms_root = comms_root
    app.state.allow_launch = allow_launch

    def _now() -> datetime:
        return datetime.now(UTC)

    def _inbox_ctx() -> dict:
        msgs = _inbox_messages(comms_root, "operator", _now())
        return {"inbox_messages": msgs, "operator_unread": len(msgs)}

    def _bus_ctx() -> dict:
        now = _now()
        bus = {role: _inbox_messages(comms_root, role, now) for role in BUS_ROLES}
        return {"bus": bus, "bus_roles": list(BUS_ROLES)}

    def _history_ctx() -> dict:
        now = _now()
        msgs: list[Message] = []
        for role in ("charc", "rd", "operator"):
            msgs.extend(_read_messages(comms_root, role, now))
        # newest first by filename stamp (the filename leads with the UTC stamp)
        msgs.sort(key=lambda m: m.filename, reverse=True)
        return {"history_messages": msgs[:HISTORY_CAP]}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        ctx = {**_inbox_ctx(), **_bus_ctx(), **_history_ctx(), "oob": False}
        return HTMLResponse(env.get_template("page.html").render(**ctx))

    @app.get("/panes/inbox", response_class=HTMLResponse)
    def pane_inbox() -> HTMLResponse:
        ctx = {**_inbox_ctx(), "oob": True}
        return HTMLResponse(env.get_template("inbox_pane.html").render(**ctx))

    @app.get("/panes/bus", response_class=HTMLResponse)
    def pane_bus() -> HTMLResponse:
        return HTMLResponse(env.get_template("bus_pane.html").render(**_bus_ctx()))

    @app.get("/panes/history", response_class=HTMLResponse)
    def pane_history() -> HTMLResponse:
        return HTMLResponse(
            env.get_template("history_pane.html").render(**_history_ctx()))

    return app


# --- __main__ entry --------------------------------------------------------

def _open_browser_later(url: str) -> None:
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Localhost mail UI over the comms Stage 1 file mailbox.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--comms-root", default=None,
                        help="mailbox root (default: <repo>/comms)")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open the default browser on start")
    args = parser.parse_args(argv)

    root = (Path(args.comms_root) if args.comms_root
            else _SCRIPTS_DIR.parent / "comms")
    app = create_app(comms_root=root)

    import uvicorn  # local import: only needed when actually serving
    url = f"http://{HOST}:{args.port}/"
    print(f"[comms-ui] serving {url} (comms-root: {root})")
    print("[comms-ui] Ctrl+C to stop.")
    if not args.no_browser:
        _open_browser_later(url)
    uvicorn.run(app, host=HOST, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
