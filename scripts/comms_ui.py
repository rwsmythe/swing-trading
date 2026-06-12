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
import json
import math
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from jinja2 import DictLoader, Environment, select_autoescape
from starlette.middleware.base import BaseHTTPMiddleware

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
# director-launch enums (L5): nothing user-typed reaches the command line
LAUNCH_ROLES = ("both", "charc", "rd")
LAUNCH_MODES = ("fresh", "resume")
LAUNCHER = "start_directors.ps1"  # in _SCRIPTS_DIR
BOOTSTRAP_FILE = "orchestrator_bootstrap.md"  # in _SCRIPTS_DIR, served verbatim


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


def _recorded_sessions(root: Path) -> dict[str, bool]:
    """Which director roles have an entry in comms/.sessions.json (presence).

    The launcher writes this map (role -> {session_name, ...}). Read-only here;
    a missing/unreadable/garbage file yields all-False (never raises).
    """
    path = root / ".sessions.json"
    result = {role: False for role in BUS_ROLES}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return result
    if isinstance(data, dict):
        for role in BUS_ROLES:
            result[role] = bool(data.get(role))
    return result


LOOPBACK_HOSTNAMES = ("127.0.0.1", "localhost", "::1")


def _loopback_host_ok(host: str) -> bool:
    """True only if the Host header's hostname is a loopback name.

    Defeats DNS rebinding: an attacker who rebinds attacker.example -> 127.0.0.1
    makes the victim's browser send Host: attacker.example (matching its own
    Origin), which would pass a naive same-origin check. The server binds
    loopback ONLY, so the sole legitimate Host hostnames are loopback names;
    anything else is refused before the Origin/Referer comparison. Port-agnostic
    (a non-listening port could never have connected).
    """
    if not host:
        return False
    if host.startswith("["):  # bracketed IPv6, e.g. [::1]:8765
        hostname = host[1:host.index("]")] if "]" in host else host
    else:
        hostname = host.split(":", 1)[0]
    return hostname in LOOPBACK_HOSTNAMES


class OriginGuard(BaseHTTPMiddleware):
    """Reject cross-origin POSTs (localhost servers are CSRF-able).

    Any webpage can blind-POST to 127.0.0.1:<port>; the launch endpoint spawns
    token-burning Claude windows. Every POST must (a) carry a loopback Host (so
    a DNS-rebound attacker hostname can't masquerade as same-origin) and (b)
    carry an Origin (or, failing that, a Referer) whose origin matches this
    app's own; a POST with NEITHER header is also refused. GETs are unguarded.
    """

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        if request.method == "POST":
            host = request.headers.get("host", "")
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            if not _loopback_host_ok(host):
                ok = False  # missing/non-loopback Host (DNS-rebinding defense)
            else:
                expected = f"{request.url.scheme}://{host}"
                if origin is not None:
                    ok = origin == expected
                elif referer is not None:
                    parts = urlsplit(referer)
                    ok = bool(parts.netloc) and (
                        f"{parts.scheme}://{parts.netloc}" == expected)
                else:
                    ok = False  # neither header -> refuse
            if not ok:
                return PlainTextResponse(
                    "403 cross-origin POST refused", status_code=403)
        return await call_next(request)


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
<script>
  // Copy the orchestrator spin-up prompt to the clipboard (localhost is a
  // secure context). On clipboard denial, reveal the text for manual copy
  // instead of failing silently.
  function copyOrchestratorBootstrap() {
    var flash = document.getElementById('directors-flash');
    fetch('/orchestrator-bootstrap').then(function (r) { return r.text(); })
      .then(function (text) {
        navigator.clipboard.writeText(text).then(
          function () { flash.innerHTML = '<div class="flash ok">copied</div>'; },
          function () {
            var pre = document.getElementById('bootstrap-fallback');
            pre.textContent = text; pre.style.display = 'block';
            flash.innerHTML =
              '<div class="flash err">copy denied -- copy manually below</div>';
          });
      })
      .catch(function () {
        flash.innerHTML =
          '<div class="flash err">could not fetch bootstrap text</div>';
      });
  }
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
  .msg-row.decision-request details.msg,
  details.msg.decision-request { border-color: #c0392b; background: #fdecea; }
  .msg-row.decision-request .type,
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

{% include "compose_form.html" %}

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

{% include "directors_strip.html" %}
</body>
</html>
"""

_INBOX_PANE = """
{%- if oob -%}
<title id="page-title" hx-swap-oob="true">comms
{%- if operator_unread %} ({{ operator_unread }}){% endif -%}
</title>
{%- endif %}
{% if flash %}<div class="flash {{ flash.cls }}">{{ flash.msg }}</div>{% endif %}
<h2>Operator inbox -- {{ inbox_messages|length }} unread
  {% if inbox_messages %}
  <form hx-post="/ack-all" hx-target="#inbox-pane" hx-swap="innerHTML"
        style="display:inline">
    <button type="submit">Ack all</button>
  </form>
  {% endif %}
</h2>
{% if not inbox_messages %}<p class="empty">(inbox empty)</p>{% endif %}
{% for m in inbox_messages %}
<div class="msg-row
  {%- if m.is_decision_request %} decision-request{% endif %}">
  <details class="msg">
    <summary>
      <span class="posted">{{ m.posted }}</span>
      <span class="from">{{ m.frm }}</span>
      <span class="type">{{ m.mtype }}</span>
      <span class="subject">{{ m.subject }}</span>
      <form hx-post="/ack" hx-target="#inbox-pane" hx-swap="innerHTML"
            style="display:inline" hx-on:click="event.stopPropagation()">
        <input type="hidden" name="filename" value="{{ m.filename }}">
        <button type="submit">Ack</button>
      </form>
    </summary>
    <pre class="body">{{ m.body }}</pre>
  </details>
</div>
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

# Compose is operator-identity ONLY (no sender field rendered; the server stamps
# from=operator). decision_request is NOT offered (L1 belt). The form sits
# OUTSIDE every polled region so a 5s refresh never clobbers half-typed input.
_COMPOSE_FORM = """<section class="strip" id="compose">
<h2>Compose (from operator)</h2>
<form class="compose" hx-post="/compose" hx-target="#compose-flash"
      hx-swap="innerHTML"
      hx-on::after-request="if(event.detail.successful) this.reset()">
  <div id="compose-flash"></div>
  <fieldset>
    <legend>to (one or more)</legend>
    <label><input type="checkbox" name="to" value="charc"> charc</label>
    <label><input type="checkbox" name="to" value="rd"> rd</label>
  </fieldset>
  <label>type
    <select name="type">
      {% for t in compose_types %}<option value="{{ t }}">{{ t }}</option>
      {% endfor %}
    </select>
  </label>
  <label>subject <input type="text" name="subject" required></label>
  <label>thread (optional) <input type="text" name="thread"></label>
  <label>body<br><textarea name="body" rows="4" cols="60"></textarea></label>
  <button type="submit">Send</button>
</form>
</section>
"""

_FLASH = """<div class="flash {{ cls }}">{{ msg }}</div>"""

# The directors strip sits OUTSIDE every polled region (like compose). It shows
# per-role unread + recorded-session presence, the launch controls, and the
# orchestrator spin-up copy button. Launch is L5-fixed-argv; copy is read-only.
_DIRECTORS_STRIP = """<section class="strip" id="directors">
<h2>Directors</h2>
<ul>
{% for role in director_roles %}
  <li>{{ role }}: {{ director_counts[role] }} unread --
    session {{ "recorded" if director_sessions[role] else "none" }}</li>
{% endfor %}
</ul>
<div id="directors-flash"></div>
{% if allow_launch %}
<form hx-post="/directors/launch" hx-target="#directors-flash"
      hx-swap="innerHTML">
  <label>role
    <select name="role">
      {% for r in launch_roles %}<option value="{{ r }}">{{ r }}</option>
      {% endfor %}
    </select>
  </label>
  <button type="submit" name="mode" value="fresh">Start fresh</button>
  <button type="submit" name="mode" value="resume">Resume</button>
</form>
{% else %}<p class="empty">(launch disabled)</p>{% endif %}
<hr>
<button type="button" onclick="copyOrchestratorBootstrap()">
  Copy orchestrator spin-up</button>
<pre id="bootstrap-fallback" style="display:none"></pre>
</section>
"""


def _make_env() -> Environment:
    return Environment(
        loader=DictLoader({
            "page.html": _PAGE,
            "inbox_pane.html": _INBOX_PANE,
            "bus_pane.html": _BUS_PANE,
            "history_pane.html": _HISTORY_PANE,
            "compose_form.html": _COMPOSE_FORM,
            "directors_strip.html": _DIRECTORS_STRIP,
            "flash.html": _FLASH,
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
    # OriginGuard is the only middleware, so it wraps every route (the
    # add-middleware-LAST-to-wrap-everything discipline holds trivially here).
    app.add_middleware(OriginGuard)

    def _now() -> datetime:
        return datetime.now(UTC)

    def _directors_ctx() -> dict:
        now = _now()
        counts = {r: len(_inbox_messages(comms_root, r, now)) for r in BUS_ROLES}
        return {
            "director_counts": counts,
            "director_sessions": _recorded_sessions(comms_root),
            "director_roles": list(BUS_ROLES),
            "launch_roles": list(LAUNCH_ROLES),
            "allow_launch": allow_launch,
        }

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

    def _flash(cls: str, msg: str, status: int) -> HTMLResponse:
        html = env.get_template("flash.html").render(cls=cls, msg=msg)
        return HTMLResponse(html, status_code=status)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        ctx = {
            **_inbox_ctx(), **_bus_ctx(), **_history_ctx(), **_directors_ctx(),
            "compose_types": list(COMPOSE_TYPES), "oob": False,
        }
        return HTMLResponse(env.get_template("page.html").render(**ctx))

    @app.post("/compose", response_class=HTMLResponse)
    def compose(
        to: list[str] = Form(default=[]),  # noqa: B008
        mtype: str = Form(alias="type"),
        subject: str = Form(...),
        body: str = Form(default=""),
        thread: str = Form(default=""),
    ) -> HTMLResponse:
        # L1 belt: only the four role->role types compose from the UI;
        # decision_request (or any other value) is refused before the write
        # path -- the sender can NEVER manufacture an authority message here.
        if mtype not in COMPOSE_TYPES:
            return _flash("err", f"type {mtype!r} is not allowed from the UI", 400)
        try:
            # Sender is ALWAYS operator (server-stamped); a client-supplied
            # 'from' field, if present in the POST, is never read (L1).
            finals = role_mail.post_message(
                comms_root, "operator", to, mtype, subject, body,
                thread or None)
        except role_mail.MailError as exc:
            return _flash("err", str(exc), 400)
        names = ", ".join(p.parent.parent.name for p in finals)
        return _flash("ok", f"posted to {names}" if names else "posted", 200)

    def _inbox_fragment(flash: dict | None) -> HTMLResponse:
        ctx = {**_inbox_ctx(), "oob": True, "flash": flash}
        return HTMLResponse(env.get_template("inbox_pane.html").render(**ctx))

    @app.post("/ack", response_class=HTMLResponse)
    def ack(filename: str = Form(...)) -> HTMLResponse:
        # Operator inbox ONLY (role hardcoded) -- the UI can never ack a
        # director's mail (L3). An already-moved file (drained via CLI in
        # parallel) is idempotent: a friendly flash + refreshed pane, never 500.
        try:
            role_mail.ack_message(comms_root, "operator", filename)
            flash = {"cls": "ok", "msg": f"acked {filename}"}
        except role_mail.MailError as exc:
            flash = {"cls": "err", "msg": f"already acked or missing ({exc})"}
        return _inbox_fragment(flash)

    @app.post("/ack-all", response_class=HTMLResponse)
    def ack_all() -> HTMLResponse:
        acked = 0
        for m in _inbox_messages(comms_root, "operator", _now()):
            try:
                role_mail.ack_message(comms_root, "operator", m.filename)
                acked += 1
            except role_mail.MailError:
                continue  # a concurrent drain is fine; keep going
        return _inbox_fragment({"cls": "ok", "msg": f"acked {acked} message(s)"})

    @app.post("/directors/launch", response_class=HTMLResponse)
    def directors_launch(
        role: str = Form(...),
        mode: str = Form(...),
    ) -> HTMLResponse:
        if not allow_launch:
            return _flash("err", "launch is disabled for this server", 400)
        # L5: enum-validate BEFORE building argv so nothing user-typed can ever
        # reach the command line; reject invalid input as a 400 flash.
        if role not in LAUNCH_ROLES:
            return _flash("err", f"invalid role {role!r}", 400)
        if mode not in LAUNCH_MODES:
            return _flash("err", f"invalid mode {mode!r}", 400)
        # L5: the EXACT argv from the brief (literal relative script path); cwd
        # is pinned to the repo root so the relative -File resolves regardless
        # of where the operator launched the UI process.
        argv = ["powershell", "-NoProfile", "-File",
                f"scripts/{LAUNCHER}", "-Role", role]
        if mode == "resume":
            argv.append("-Resume")
        try:
            result = subprocess.run(  # noqa: S603 (fixed argv, enum-validated)
                argv, capture_output=True, text=True, timeout=30,
                cwd=str(_SCRIPTS_DIR.parent))
        except (subprocess.SubprocessError, OSError) as exc:
            return _flash("err", f"launcher failed to run: {role_mail._ascii(str(exc))}", 200)
        out = role_mail._ascii(((result.stdout or "") + (result.stderr or "")).strip())
        if result.returncode != 0:
            return _flash(
                "err", f"launcher exit {result.returncode}: {out}"[:800], 200)
        return _flash("ok", f"launched ({role}/{mode}): {out}"[:800] or "launched", 200)

    @app.get("/orchestrator-bootstrap", response_class=PlainTextResponse)
    def orchestrator_bootstrap() -> Response:
        # Served verbatim for the copy button (read-only repo file, no guard).
        text = (_SCRIPTS_DIR / BOOTSTRAP_FILE).read_text(encoding="utf-8")
        return PlainTextResponse(text)

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
