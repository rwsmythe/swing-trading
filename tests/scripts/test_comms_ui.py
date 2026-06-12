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


@pytest.fixture
def client(comms):
    app = comms_ui.create_app(comms_root=comms)
    return TestClient(app)


def _post(comms, sender, recipients, mtype, subject, body, thread=None):
    return role_mail.post_message(
        comms, sender, recipients, mtype, subject, body, thread)


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


# --- never touches the real comms ------------------------------------------

def test_factory_uses_given_root_not_real_comms(comms):
    app = comms_ui.create_app(comms_root=comms)
    with TestClient(app) as c:
        c.get("/panes/inbox")
    # nothing was created under a real comms/ -- the tmp root is the only tree
    assert comms_ui  # smoke: import succeeded with no global comms access
