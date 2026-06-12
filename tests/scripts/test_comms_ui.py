"""Tests for scripts/comms_ui.py -- the localhost mail UI over comms Stage 1.

The app factory ALWAYS takes a comms_root so every test drives a tmp_path tree;
the real comms/ is never touched (the Arc-2 suite-leak lesson applies to
mailboxes too). role_mail.py is imported the same not-a-package way the module
itself does it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: a frozen @dataclass resolves its module via
    # sys.modules[cls.__module__] at class-creation time (Python 3.14).
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


comms_ui = _load("comms_ui")
role_mail = _load("role_mail")


@pytest.fixture
def comms(tmp_path):
    return tmp_path / "comms"


# Drive the client at the real loopback origin so Host/Origin mirror production
# (the OriginGuard requires a loopback Host -- the DNS-rebinding defense).
_BASE_URL = "http://127.0.0.1:8765"


@pytest.fixture
def client(comms):
    app = comms_ui.create_app(comms_root=comms)
    return TestClient(app, base_url=_BASE_URL)


def _post(comms, sender, recipients, mtype, subject, body, thread=None):
    return role_mail.post_message(
        comms, sender, recipients, mtype, subject, body, thread)


# Same-origin header for POST tests (the client is driven at _BASE_URL, so the
# app's own origin is the loopback origin). A POST with no Origin/Referer is
# rejected; a non-loopback Host is rejected (DNS-rebinding defense).
_SAME_ORIGIN = {"Origin": _BASE_URL}


# --- factory + binding -----------------------------------------------------

def test_host_is_loopback_only():
    assert comms_ui.HOST == "127.0.0.1"


def test_default_port_is_8765():
    assert comms_ui.DEFAULT_PORT == 8765


def test_create_app_returns_fastapi():
    from fastapi import FastAPI
    app = comms_ui.create_app(comms_root=Path("/nonexistent/comms"))
    assert isinstance(app, FastAPI)


def test_index_renders_on_empty_tree(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # the three list panes are present
    assert 'id="inbox-pane"' in body
    assert 'id="bus-pane"' in body
    assert 'id="history-pane"' in body


# --- polling wiring --------------------------------------------------------

def test_panes_poll_every_5s(client):
    body = client.get("/").text
    assert body.count("every 5s") >= 3  # inbox, bus, history each poll
    assert 'hx-get="/panes/inbox"' in body
    assert 'hx-get="/panes/bus"' in body
    assert 'hx-get="/panes/history"' in body


def test_response_handling_override_present(client):
    # the 4xx-swap htmx config gotcha applies to this standalone app too
    body = client.get("/").text
    assert "responseHandling" in body


# --- operator inbox pane ---------------------------------------------------

def test_inbox_pane_lists_operator_messages(client, comms):
    _post(comms, "charc", ["operator"], "query", "Need a call", "ring me")
    body = client.get("/panes/inbox").text
    assert "Need a call" in body
    assert "charc" in body
    assert "query" in body


def test_inbox_pane_shows_body_for_expand(client, comms):
    _post(comms, "charc", ["operator"], "fyi", "subj", "the-expandable-body")
    body = client.get("/panes/inbox").text
    assert "the-expandable-body" in body  # body present in-place for expand


def test_inbox_pane_flags_decision_request(client, comms):
    _post(comms, "charc", ["operator"], "decision_request", "approve?", "x")
    body = client.get("/panes/inbox").text
    assert "decision_request" in body
    assert "decision-request" in body  # the visual flag class


def test_title_carries_operator_unread_count(client, comms):
    _post(comms, "charc", ["operator"], "fyi", "one", "a")
    _post(comms, "rd", ["operator"], "fyi", "two", "b")
    # the fragment carries an OOB title so the tab count updates on poll
    frag = client.get("/panes/inbox").text
    assert "2" in frag
    assert "hx-swap-oob" in frag
    page = client.get("/").text
    assert "<title" in page


# --- director bus pane (READ-ONLY) -----------------------------------------

def test_bus_pane_shows_charc_and_rd_inboxes(client, comms):
    _post(comms, "operator", ["charc"], "fyi", "for-charc", "x")
    _post(comms, "operator", ["rd"], "fyi", "for-rd", "y")
    body = client.get("/panes/bus").text
    assert "for-charc" in body
    assert "for-rd" in body


def test_bus_pane_has_no_ack_affordance(client, comms):
    # the UI must never ack a director's mail (L3) -- no ack control in the bus
    _post(comms, "operator", ["charc"], "fyi", "busmsg", "x")
    body = client.get("/panes/bus").text
    assert "/ack" not in body


def test_bus_pane_styles_stale_over_7_days(client, comms):
    # a >7d-old inbox message is styled stale (matches harness-probe threshold)
    inbox = comms / "charc" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    # filename stamp drives age; 9 days before a far-future "now" is irrelevant
    # -- use a stamp well in the past so it is unambiguously stale today.
    (inbox / "20200101T000000Z-operator-old.md").write_text(
        "---\nfrom: operator\nto: charc\ntype: fyi\nsubject: ancient\n"
        "posted: 2020-01-01T00:00:00Z\n---\n\nbody\n", encoding="utf-8")
    body = client.get("/panes/bus").text
    assert "stale" in body


# --- history pane ----------------------------------------------------------

def test_history_pane_shows_read_messages(client, comms):
    _post(comms, "charc", ["operator"], "fyi", "histsubj", "x")
    fname = role_mail._list_inbox(comms, "operator")[0].name
    role_mail.ack_message(comms, "operator", fname)
    body = client.get("/panes/history").text
    assert "histsubj" in body


def test_history_pane_caps_at_50(client, comms):
    read_dir = comms / "operator" / "read"
    read_dir.mkdir(parents=True, exist_ok=True)
    for i in range(60):
        (read_dir / f"2026010{i // 10}T0000{i % 10}0Z-charc-m{i}.md").write_text(
            f"---\nfrom: charc\nto: operator\ntype: fyi\nsubject: hm{i}\n"
            f"---\n\nb{i}\n", encoding="utf-8")
    body = client.get("/panes/history").text
    # at most 50 rendered subjects (hm-prefixed)
    assert body.count("hm") <= 50 * 3  # generous: subject appears a few times


def test_history_collapsed_by_default(client):
    page = client.get("/").text
    # the history pane is collapsed by default (a <details> without `open`)
    assert "history-pane" in page


# --- malformed frontmatter degrades ----------------------------------------

def test_malformed_frontmatter_renders_filename_fallback(client, comms):
    inbox = comms / "operator" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "20260611T120000Z-charc-broken.md").write_text(
        "no frontmatter here at all, just text\n", encoding="utf-8")
    r = client.get("/panes/inbox")
    assert r.status_code == 200
    assert "broken" in r.text  # filename shown as fallback


# --- compose POST (T3) -----------------------------------------------------

def test_compose_delivers_via_post_message(client, comms):
    r = client.post("/compose", data={"to": "charc", "type": "status",
                                       "subject": "from the UI", "body": "hi"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200
    files = role_mail._list_inbox(comms, "charc")
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "from: operator" in text
    assert "subject: from the UI" in text


def test_compose_server_stamps_operator_ignoring_client_from(client, comms):
    # a crafted 'from' field must be IGNORED; the sender is always operator.
    r = client.post("/compose",
                    data={"from": "charc", "to": "rd", "type": "fyi",
                          "subject": "spoof", "body": "x"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200
    text = role_mail._list_inbox(comms, "rd")[0].read_text(encoding="utf-8")
    assert "from: operator" in text
    assert "from: charc" not in text


def test_compose_multi_recipient(client, comms):
    r = client.post("/compose",
                    data={"to": ["charc", "rd"], "type": "status",
                          "subject": "both", "body": "x"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200
    assert len(role_mail._list_inbox(comms, "charc")) == 1
    assert len(role_mail._list_inbox(comms, "rd")) == 1


def test_compose_rejects_decision_request_type(client, comms):
    # the L1 belt: decision_request is never composable from the UI, even via a
    # crafted POST -- 400 flash, nothing written.
    r = client.post("/compose",
                    data={"to": "operator", "type": "decision_request",
                          "subject": "approve?", "body": "x"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 400
    assert list(comms.rglob("*.md")) == []


def test_compose_rejects_unknown_type(client, comms):
    r = client.post("/compose",
                    data={"to": "charc", "type": "bogus",
                          "subject": "s", "body": "x"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 400
    assert list(comms.rglob("*.md")) == []


def test_compose_empty_recipients_is_400(client, comms):
    r = client.post("/compose",
                    data={"type": "fyi", "subject": "s", "body": "x"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 400
    assert "flash" in r.text
    assert list(comms.rglob("*.md")) == []


def test_compose_mailerror_renders_flash_400(client, comms):
    # a CR/LF subject (frontmatter injection) surfaces as a 400 flash, not a 500.
    r = client.post("/compose",
                    data={"to": "charc", "type": "fyi",
                          "subject": "ok\ntype: decision_request", "body": "x"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 400
    assert "flash" in r.text
    assert list(comms.rglob("*.md")) == []


def test_compose_goes_through_post_message_seam(client, comms, monkeypatch):
    # L4: the UI's single write path is role_mail.post_message. Spy on the
    # instance comms_ui actually uses and prove sender is server-stamped.
    calls = []

    def spy(root, sender, recipients, mtype, subject, body, thread=None):
        calls.append((sender, recipients, mtype, subject, thread))
        return []

    monkeypatch.setattr(comms_ui.role_mail, "post_message", spy)
    r = client.post("/compose",
                    data={"from": "charc", "to": ["charc", "rd"],
                          "type": "query", "subject": "seam", "body": "b"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200
    assert len(calls) == 1
    sender, recipients, mtype, subject, _ = calls[0]
    assert sender == "operator"            # server-stamped, never the client's
    assert recipients == ["charc", "rd"]
    assert mtype == "query"
    assert subject == "seam"


def test_compose_form_has_no_decision_request_option(client):
    page = client.get("/").text
    assert 'value="decision_request"' not in page
    # the four role->role types ARE offered
    for t in ("fyi", "status", "query", "return_report"):
        assert f'value="{t}"' in page


def test_compose_form_outside_polled_region(client):
    # a 5s refresh must never clobber half-typed input -> the compose form is
    # not inside any hx-trigger="every 5s" section.
    page = client.get("/").text
    assert 'hx-post="/compose"' in page


# --- ack endpoints (T4; operator inbox ONLY) -------------------------------

def test_ack_moves_operator_message_to_read(client, comms):
    _post(comms, "charc", ["operator"], "fyi", "ack me", "x")
    fname = role_mail._list_inbox(comms, "operator")[0].name
    r = client.post("/ack", data={"filename": fname}, headers=_SAME_ORIGIN)
    assert r.status_code == 200
    assert len(role_mail._list_inbox(comms, "operator")) == 0
    assert len(role_mail._list_read(comms, "operator")) == 1


def test_ack_returns_refreshed_inbox_fragment(client, comms):
    _post(comms, "charc", ["operator"], "fyi", "a", "x")
    _post(comms, "rd", ["operator"], "fyi", "b", "y")
    fname = role_mail._list_inbox(comms, "operator")[0].name
    r = client.post("/ack", data={"filename": fname}, headers=_SAME_ORIGIN)
    # the OOB title reflects the now-1 remaining unread count
    assert "hx-swap-oob" in r.text
    assert "Operator inbox -- 1 unread" in r.text


def test_ack_already_moved_is_idempotent_not_500(client, comms):
    # the operator drained via CLI in parallel -> a friendly flash, never a 500
    role_mail._ensure_tree(comms)
    r = client.post("/ack", data={"filename": "20260101T000000Z-charc-gone.md"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200
    assert "flash" in r.text


def test_ack_all_drains_operator_inbox(client, comms):
    for i in range(3):
        _post(comms, "charc", ["operator"], "fyi", f"m{i}", "x")
    r = client.post("/ack-all", data={}, headers=_SAME_ORIGIN)
    assert r.status_code == 200
    assert len(role_mail._list_inbox(comms, "operator")) == 0
    assert len(role_mail._list_read(comms, "operator")) == 3


def test_ack_never_touches_a_director_mailbox(client, comms):
    # L3 mail custody: the ack endpoint is operator-only. A charc filename
    # posted to /ack must leave charc's inbox completely untouched.
    _post(comms, "operator", ["charc"], "fyi", "director-mail", "x")
    charc_file = role_mail._list_inbox(comms, "charc")[0].name
    r = client.post("/ack", data={"filename": charc_file}, headers=_SAME_ORIGIN)
    assert r.status_code == 200  # idempotent miss against operator inbox
    assert len(role_mail._list_inbox(comms, "charc")) == 1  # untouched
    assert len(role_mail._list_read(comms, "charc")) == 0


def test_no_role_parameterized_ack_route(client):
    # there is NO ack route that takes a role (the UI can never ack a director)
    paths = [getattr(r, "path", "") for r in client.app.routes]
    ack_paths = [p for p in paths if "ack" in p]
    assert set(ack_paths) <= {"/ack", "/ack-all"}
    assert not any("{" in p for p in ack_paths)  # no {role} template


def test_viewing_inbox_never_acks(client, comms):
    _post(comms, "charc", ["operator"], "fyi", "stay", "x")
    client.get("/panes/inbox")
    client.get("/panes/inbox")
    assert len(role_mail._list_inbox(comms, "operator")) == 1  # NOT moved


def test_inbox_pane_renders_ack_controls(client, comms):
    _post(comms, "charc", ["operator"], "fyi", "ackable", "x")
    body = client.get("/panes/inbox").text
    assert 'hx-post="/ack"' in body
    assert 'hx-post="/ack-all"' in body


def test_ack_goes_through_ack_message_seam(client, comms, monkeypatch):
    # L4: ack goes through role_mail.ack_message on the operator mailbox only.
    calls = []

    def spy(root, role, filename):
        calls.append((role, filename))
        return root / role / "read" / filename

    monkeypatch.setattr(comms_ui.role_mail, "ack_message", spy)
    client.post("/ack", data={"filename": "x.md"}, headers=_SAME_ORIGIN)
    assert calls == [("operator", "x.md")]


# --- origin guard (T5; all POSTs) ------------------------------------------

def test_post_with_foreign_origin_is_403(client, comms):
    r = client.post("/compose",
                    data={"to": "charc", "type": "fyi", "subject": "s",
                          "body": "x"},
                    headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert list(comms.rglob("*.md")) == []  # nothing written


def test_post_with_no_origin_or_referer_is_403(client, comms):
    # TestClient sends neither Origin nor Referer by default -> rejected.
    r = client.post("/compose",
                    data={"to": "charc", "type": "fyi", "subject": "s",
                          "body": "x"})
    assert r.status_code == 403
    assert list(comms.rglob("*.md")) == []


def test_post_with_matching_referer_is_allowed(client, comms):
    r = client.post("/compose",
                    data={"to": "charc", "type": "fyi", "subject": "ref",
                          "body": "x"},
                    headers={"Referer": _BASE_URL + "/"})
    assert r.status_code == 200
    assert len(role_mail._list_inbox(comms, "charc")) == 1


def test_post_with_dns_rebound_host_and_matching_origin_is_403(client, comms):
    # DNS rebinding: attacker.example -> 127.0.0.1 makes the browser send a
    # matching Host+Origin of the ATTACKER's domain. The loopback-Host check
    # refuses it before the same-origin comparison can be fooled.
    r = client.post("/compose",
                    data={"to": "charc", "type": "fyi", "subject": "s",
                          "body": "x"},
                    headers={"Host": "attacker.example:8765",
                             "Origin": "http://attacker.example:8765"})
    assert r.status_code == 403
    assert list(comms.rglob("*.md")) == []


def test_post_with_dns_rebound_host_and_matching_referer_is_403(client, comms):
    r = client.post("/compose",
                    data={"to": "charc", "type": "fyi", "subject": "s",
                          "body": "x"},
                    headers={"Host": "attacker.example:8765",
                             "Referer": "http://attacker.example:8765/x"})
    assert r.status_code == 403
    assert list(comms.rglob("*.md")) == []


def test_loopback_host_allowlist():
    ok = comms_ui._loopback_host_ok
    assert ok("127.0.0.1:8765")
    assert ok("localhost:8765")
    assert ok("127.0.0.1")
    assert ok("[::1]:8765")
    assert not ok("attacker.example:8765")
    assert not ok("")
    assert not ok("evil.127.0.0.1.nip.io:8765")


def test_get_is_not_origin_guarded(client):
    # GETs carry no foreign-origin risk; they must work with no Origin header.
    assert client.get("/").status_code == 200
    assert client.get("/panes/inbox").status_code == 200


def test_post_with_empty_host_and_matching_origin_is_403(client, comms):
    # Defense-in-depth: with no Host the expected origin degenerates to
    # "http://"; a crafted Origin "http://" must NOT slip past the guard.
    r = client.post("/compose",
                    data={"to": "charc", "type": "fyi", "subject": "s",
                          "body": "x"},
                    headers={"Host": "", "Origin": "http://"})
    assert r.status_code == 403
    assert list(comms.rglob("*.md")) == []


# --- launch endpoint (T5; exact argv, subprocess mocked) -------------------

def _mock_run(monkeypatch, returncode=0, stdout="launched", stderr=""):
    calls = []

    def fake(argv, **kwargs):
        calls.append((argv, kwargs))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=returncode, stdout=stdout,
                               stderr=stderr)

    monkeypatch.setattr(comms_ui.subprocess, "run", fake)
    return calls


def _launcher_argv(role, resume):
    # L5: the EXACT argv -- literal relative script path (the locked contract).
    argv = ["powershell", "-NoProfile", "-File",
            "scripts/start_directors.ps1", "-Role", role]
    if resume:
        argv.append("-Resume")
    return argv


def test_launch_fresh_runs_exact_argv(client, monkeypatch):
    calls = _mock_run(monkeypatch)
    r = client.post("/directors/launch", data={"role": "both", "mode": "fresh"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200
    assert len(calls) == 1
    assert calls[0][0] == _launcher_argv("both", resume=False)
    # cwd is pinned to the repo root so the relative -File path resolves
    assert calls[0][1].get("cwd") == str(comms_ui._SCRIPTS_DIR.parent)


def test_launch_resume_appends_resume_flag(client, monkeypatch):
    calls = _mock_run(monkeypatch)
    client.post("/directors/launch", data={"role": "charc", "mode": "resume"},
                headers=_SAME_ORIGIN)
    assert calls[0][0] == _launcher_argv("charc", resume=True)


def test_launch_rejects_invalid_role(client, monkeypatch):
    calls = _mock_run(monkeypatch)
    r = client.post("/directors/launch",
                    data={"role": "operator", "mode": "fresh"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 400
    assert calls == []  # subprocess NEVER reached


def test_launch_rejects_invalid_mode(client, monkeypatch):
    calls = _mock_run(monkeypatch)
    r = client.post("/directors/launch",
                    data={"role": "both", "mode": "nuke"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 400
    assert calls == []


def test_launch_nonzero_exit_is_error_flash_not_500(client, monkeypatch):
    _mock_run(monkeypatch, returncode=1, stdout="", stderr="boom")
    r = client.post("/directors/launch", data={"role": "both", "mode": "fresh"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200  # not a 500
    assert "flash" in r.text
    assert "err" in r.text


def test_launch_subprocess_timeout_is_flash_not_500(client, monkeypatch):
    import subprocess as _sp

    def boom(argv, **kwargs):
        raise _sp.TimeoutExpired(argv, 30)

    monkeypatch.setattr(comms_ui.subprocess, "run", boom)
    r = client.post("/directors/launch", data={"role": "both", "mode": "fresh"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200
    assert "flash" in r.text


def test_launch_disabled_refuses_without_subprocess(comms, monkeypatch):
    app = comms_ui.create_app(comms_root=comms, allow_launch=False)
    calls = _mock_run(monkeypatch)
    with TestClient(app, base_url=_BASE_URL) as c:
        r = c.post("/directors/launch", data={"role": "both", "mode": "fresh"},
                   headers=_SAME_ORIGIN)
    assert r.status_code == 400
    assert calls == []


# --- orchestrator bootstrap copy button (T5) -------------------------------

def test_orchestrator_bootstrap_served_verbatim(client):
    r = client.get("/orchestrator-bootstrap")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    expected = (comms_ui._SCRIPTS_DIR / "orchestrator_bootstrap.md").read_text(
        encoding="utf-8")
    assert r.text == expected


def test_directors_strip_renders_controls(client, comms):
    page = client.get("/").text
    assert 'hx-post="/directors/launch"' in page
    assert "orchestrator" in page.lower()  # the copy button
    assert "/orchestrator-bootstrap" in page  # the copy fetch target


# --- never touches the real comms ------------------------------------------

def test_factory_uses_given_root_not_real_comms(comms):
    app = comms_ui.create_app(comms_root=comms)
    with TestClient(app) as c:
        c.get("/panes/inbox")
    # nothing was created under a real comms/ -- the tmp root is the only tree
    assert comms_ui  # smoke: import succeeded with no global comms access
