"""The weekly-usage readouts (scripts/usage_codex.py, scripts/usage_claude.py).

PORTED 2026-11-11 from harness-template 4335ff6 tests/harness/test_usage_readouts.py (the
Codex-lane arc, P2). The pace formula is the dispatch tiebreak's input, so it is pinned with
the template's first live readings of 2026-10-27 as the fixtures. Edits from the template:

- the loader no longer inserts scripts/ into sys.path (neither readout imports the other; a
  path insert would let a script shadow a module for every later test in the worker);
- the credential discipline CHARC ruled for P2 is pinned: the token is never printed on any
  path, and it is sent only to https://api.anthropic.com;
- the Codex readout's weekly-window selection and its no-reading path are pinned;
- the settings grant is pinned: the EXACT allow rule, no wildcard, and its _comment_usage.

No network, no real credential file and no real app-server: urlopen and the app-server read
are replaced, and the credentials are a tmp file holding a sentinel.
"""

from __future__ import annotations

import datetime as dt
import http.client
import importlib.util
import io
import json
import sys
import time
import unittest
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"

SENTINEL = "sk-ant-oat01-SENTINEL-never-print-me-7f3a"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class PaceFormula(unittest.TestCase):
    def setUp(self) -> None:
        self.codex = _load("usage_codex")

    def test_codex_first_reading(self) -> None:
        # 2026-10-27 02:41Z (epoch 1793068860): 22 % used, resets 2026-11-02 08:03Z
        # (epoch 1793606580) -> 11.1 % of the window elapsed, pace about 2.0.
        out = self.codex.pace_from(22, 10080, 1793606580, 1793068860)
        self.assertAlmostEqual(out["elapsed_fraction"], 0.111, places=2)
        self.assertAlmostEqual(out["pace"], 1.98, places=1)

    def test_claude_first_reading(self) -> None:
        # 21 % used at ~10 % of the window -> pace about 2.1.
        resets = 1_800_000_000.0
        now = resets - 0.9 * 7 * 86400
        out = self.codex.pace_from(21, 10080, resets, now)
        self.assertAlmostEqual(out["elapsed_fraction"], 0.1, places=3)
        self.assertAlmostEqual(out["pace"], 2.1, places=1)

    def test_fresh_window_does_not_divide_by_zero(self) -> None:
        out = self.codex.pace_from(0, 10080, 1_800_000_000.0, 1_800_000_000.0 - 7 * 86400)
        self.assertEqual(out["pace"], 0.0)
        self.assertGreater(out["elapsed_fraction"], 0.0)

    def test_past_reset_clamps_to_full_window(self) -> None:
        out = self.codex.pace_from(50, 10080, 1_000.0, 2_000.0)
        self.assertEqual(out["elapsed_fraction"], 1.0)
        self.assertEqual(out["pace"], 0.5)

    def test_both_readouts_share_one_formula(self) -> None:
        claude = _load("usage_claude")
        for args in ((22, 10080, 1793606580, 1793068860), (50, 10080, 1_000.0, 2_000.0)):
            self.assertEqual(claude.pace_from(*args), self.codex.pace_from(*args))


class ClaudeParse(unittest.TestCase):
    def setUp(self) -> None:
        self.claude = _load("usage_claude")

    def test_parses_seven_day_block(self) -> None:
        body = {
            "five_hour": {"utilization": 10.0, "resets_at": "2026-10-27T04:30:00+00:00"},
            "seven_day": {"utilization": 21.0, "resets_at": "2026-11-02T10:00:00.248465+00:00"},
        }
        now = dt.datetime(2026, 10, 27, 2, 41, tzinfo=dt.UTC).timestamp()
        out = self.claude.parse_usage(body, now)
        self.assertEqual(out["lane"], "claude")
        self.assertEqual(out["used_percent"], 21.0)
        self.assertEqual(out["resets_at"], "2026-11-02T10:00:00Z")
        self.assertAlmostEqual(out["elapsed_fraction"], 0.099, places=2)
        self.assertAlmostEqual(out["pace"], 2.1, places=1)

    def test_missing_block_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.claude.parse_usage({"five_hour": {}}, 0.0)


# ------------------------------------------------ the credential discipline (P2) --
def _credentials(tmp_path: Path) -> Path:
    cred = tmp_path / "credentials.json"
    cred.write_text(json.dumps({"claudeAiOauth": {"accessToken": SENTINEL}}), encoding="utf-8")
    return cred


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _run_claude(tmp_path, monkeypatch, capsys, behaviour):
    """Run usage_claude.main with its opener replaced; return (rc, stdout+stderr, requests).

    The readout sends the token ONLY through ``build_opener()`` (Codex R1-5), so that is the
    seam replaced here; no socket is opened."""
    mod = _load("usage_claude")
    seen: list = []

    class _FakeOpener:
        def open(self, req, timeout):
            seen.append(req)
            return behaviour(req)

    monkeypatch.setattr(mod, "build_opener", lambda *handlers: _FakeOpener())
    rc = mod.main(["--credentials", str(_credentials(tmp_path)), "--timeout", "1"])
    cap = capsys.readouterr()
    return rc, cap.out + cap.err, seen


def _ok(req):
    body = {"seven_day": {"utilization": 21.0, "resets_at": "2026-11-02T10:00:00+00:00"}}
    return _Resp(json.dumps(body).encode("utf-8"))


def _http_401(req):
    raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)


def _url_error(req):
    raise urllib.error.URLError("no route")


def _bad_body(req):
    return _Resp(b"not json")


def test_the_token_goes_only_to_the_vendor_host_over_tls(tmp_path, monkeypatch, capsys):
    rc, out, seen = _run_claude(tmp_path, monkeypatch, capsys, _ok)
    assert rc == 0
    assert len(seen) == 1
    assert seen[0].full_url == "https://api.anthropic.com/api/oauth/usage"
    assert seen[0].get_header("Authorization") == "Bearer " + SENTINEL
    # Unredirected: urllib never copies it onto a redirected request (R1-5, second belt).
    assert "Authorization" not in seen[0].headers
    assert json.loads(out)["lane"] == "claude"


class _RedirectingHTTPS(urllib.request.HTTPSHandler):
    """An in-process HTTPS transport (no socket): every URL but ``target`` answers 302 to
    ``target``; each request opened is recorded with the Authorization it carried."""

    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target
        self.opened: list[tuple[str, str | None]] = []

    def https_open(self, req):
        self.opened.append((req.full_url, req.get_header("Authorization")))
        hdrs = http.client.HTTPMessage()
        hdrs["Location"] = self.target
        code = 200 if req.full_url == self.target else 302
        resp = urllib.response.addinfourl(io.BytesIO(b"{}"), hdrs, req.full_url, code)
        resp.msg = "OK" if code == 200 else "Found"
        return resp


def test_a_redirect_is_refused_and_the_token_is_never_resent(tmp_path):
    """Codex R1-5: urllib's redirect handler copies ordinary headers to the redirected
    request. The positive control shows this transport reproduces the leak with a plain
    opener; the readout's own opener refuses the redirect and opens nothing else."""
    mod = _load("usage_claude")
    other = "https://other.invalid/usage"
    control = _RedirectingHTTPS(other)
    req = urllib.request.Request(mod.USAGE_URL, headers={"Authorization": "Bearer " + SENTINEL})
    urllib.request.build_opener(control).open(req, timeout=1).close()
    assert control.opened[-1] == (other, "Bearer " + SENTINEL)

    transport = _RedirectingHTTPS(other)
    try:
        mod.fetch(SENTINEL, 1, opener=mod.build_opener(transport))
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        assert SENTINEL not in str(exc)
    else:
        raise AssertionError("a redirect was followed")
    assert [url for url, _ in transport.opened] == [mod.USAGE_URL]


def test_the_token_is_never_printed_on_any_path(tmp_path, monkeypatch, capsys):
    for behaviour in (_ok, _http_401, _url_error, _bad_body):
        rc, out, _ = _run_claude(tmp_path, monkeypatch, capsys, behaviour)
        assert SENTINEL not in out, behaviour.__name__
        assert "Bearer" not in out, behaviour.__name__
        if behaviour is not _ok:
            assert rc == 1, behaviour.__name__
            assert json.loads(out)["lane"] == "claude"
            assert "error" in json.loads(out)


class _TruncatedResp(_Resp):
    """``Content-Length: 20`` with only ``{}`` delivered: ``read()`` raises."""

    def read(self, *a):
        raise http.client.IncompleteRead(b"{}", 18)


def _truncated(req):
    return _TruncatedResp(b"")


def _bad_status_line(req):
    raise http.client.BadStatusLine("HTTP/9 ???")


def _deeply_nested_body(req):
    return _Resp(b"[" * 100_000)


@pytest.mark.parametrize("behaviour", [_truncated, _bad_status_line, _deeply_nested_body])
def test_a_failed_transfer_or_parse_is_an_error_reading(tmp_path, monkeypatch, capsys, behaviour):
    """Codex R2-4 and its class: ``http.client.HTTPException`` (a truncated body, a bad status
    line) is no ``OSError``, and a body nested past the recursion limit raises
    ``RecursionError`` (a ``RuntimeError``) from ``json.loads``; each escaped the JSON error
    reading as a traceback."""
    rc, out, _ = _run_claude(tmp_path, monkeypatch, capsys, behaviour)
    assert rc == 1
    assert SENTINEL not in out
    parsed = json.loads(out)
    assert parsed["lane"] == "claude" and "error" in parsed


def _no_network(monkeypatch) -> None:
    def refuse(self):
        raise OSError("no network in tests")

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", refuse)


def _bad_credentials(tmp_path: Path) -> Path:
    cred = tmp_path / "bad.json"
    payload = {"claudeAiOauth": {"accessToken": SENTINEL + "\nX"}}
    cred.write_text(json.dumps(payload), encoding="utf-8")
    return cred


def test_the_real_header_failure_carries_the_token(tmp_path, monkeypatch):
    """Positive control for R1-6: http.client rejects a header value with a line break,
    BEFORE any connect, with a ValueError whose text holds the whole value."""
    mod = _load("usage_claude")
    _no_network(monkeypatch)
    try:
        mod.fetch(SENTINEL + "\nX", 1)
    except ValueError as exc:
        assert SENTINEL in str(exc)
    else:
        raise AssertionError("the header validation did not fire")


def test_a_malformed_token_is_refused_before_any_request(tmp_path, monkeypatch, capsys):
    """Codex R1-6, first belt: a token that is empty or carries whitespace or a control
    character is refused when it is read, by a message that does not show it."""
    mod = _load("usage_claude")
    _no_network(monkeypatch)
    rc = mod.main(["--credentials", str(_bad_credentials(tmp_path)), "--timeout", "1"])
    cap = capsys.readouterr()
    assert rc == 1
    assert SENTINEL not in cap.out + cap.err and "Bearer" not in cap.out + cap.err
    assert "error" in json.loads(cap.out)


def test_every_error_text_is_redacted_of_the_token(tmp_path, monkeypatch, capsys):
    """Codex R1-6, second belt: with the shape check bypassed, the REAL header-validation
    ValueError reaches main, and main prints it with the token removed."""
    mod = _load("usage_claude")
    _no_network(monkeypatch)
    monkeypatch.setattr(mod, "read_token", lambda path: SENTINEL + "\nX")
    rc = mod.main(["--credentials", str(_bad_credentials(tmp_path)), "--timeout", "1"])
    cap = capsys.readouterr()
    assert rc == 1
    assert SENTINEL not in cap.out + cap.err
    assert json.loads(cap.out)["error"].startswith("ValueError")


def test_an_unreadable_credentials_file_is_no_reading(tmp_path, capsys):
    mod = _load("usage_claude")
    rc = mod.main(["--credentials", str(tmp_path / "absent.json"), "--timeout", "1"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["lane"] == "claude" and "error" in out


# ----------------------------------------------------- the Codex readout's main --
def _limits(primary: dict, secondary: dict) -> dict:
    return {"rateLimits": {"primary": primary, "secondary": secondary}}


def test_codex_reads_the_seven_day_window_whichever_slot_holds_it(monkeypatch, capsys):
    mod = _load("usage_codex")
    five_hour = {"usedPercent": 80, "windowDurationMins": 300, "resetsAt": 1793080000}
    weekly = {"usedPercent": 22, "windowDurationMins": 10080, "resetsAt": 1793606580}
    for result in (_limits(five_hour, weekly), _limits(weekly, five_hour)):
        monkeypatch.setattr(mod, "read_rate_limits", lambda exe, timeout, r=result: r)
        assert mod.main(["--exe", "codex.exe"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["lane"] == "codex"
        assert out["used_percent"] == 22.0
        assert out["window_mins"] == 10080.0


def test_codex_without_a_weekly_window_is_no_reading(monkeypatch, capsys):
    """Codex R1-7 + CHARC N2: the tiebreak compares WEEKLY pace. With no 10080-minute window
    the readout used to report the 5-hour window and exit 0; the weekly budget is UNKNOWN,
    so it is an error reading (the build then goes to the other lane)."""
    mod = _load("usage_codex")
    five_hour = {"usedPercent": 1, "windowDurationMins": 300, "resetsAt": 1793080000}
    for result in (_limits(five_hour, None), {"rateLimits": {"primary": five_hour}}):
        monkeypatch.setattr(mod, "read_rate_limits", lambda exe, timeout, r=result: r)
        assert mod.main(["--exe", "codex.exe"]) == 1
        out = json.loads(capsys.readouterr().out)
        assert out["lane"] == "codex" and "error" in out
        assert "pace" not in out


def _weekly(**over) -> dict:
    return {"usedPercent": 22, "windowDurationMins": 10080, "resetsAt": 1793606580, **over}


def test_a_malformed_codex_response_is_an_error_reading(monkeypatch, capsys):
    """Codex R1-9: a malformed body used to escape the JSON error contract (an uncaught
    AttributeError, an OverflowError raised outside the guard) or print a NaN reading."""
    mod = _load("usage_codex")
    cases = (
        {"rateLimits": []},
        {"rateLimits": None},
        _limits(_weekly(resetsAt=1e300), None),
        _limits(_weekly(usedPercent="NaN"), None),
        _limits(_weekly(usedPercent=float("inf")), None),
    )
    for result in cases:
        monkeypatch.setattr(mod, "read_rate_limits", lambda exe, timeout, r=result: r)
        assert mod.main(["--exe", "codex.exe"]) == 1, result
        out = capsys.readouterr().out
        assert "NaN" not in out and "Infinity" not in out, result
        parsed = json.loads(out)
        assert parsed["lane"] == "codex" and "error" in parsed and "pace" not in parsed


def test_a_malformed_claude_body_is_an_error_reading(tmp_path, monkeypatch, capsys):
    """Codex R1-9: ``utilization: "NaN"`` printed a NaN reading with exit 0."""
    for util in ("NaN", "inf", float("nan")):
        def body(req, u=util):
            b = {"seven_day": {"utilization": u, "resets_at": "2026-11-02T10:00:00+00:00"}}
            return _Resp(json.dumps(b).encode("utf-8"))

        rc, out, _ = _run_claude(tmp_path, monkeypatch, capsys, body)
        assert rc == 1, util
        assert "pace" not in out and "error" in json.loads(out), util


def _week_ahead() -> float:
    """A reset seven days from now: the elapsed fraction clamps to its 1e-6 floor."""
    return time.time() + 7 * 24 * 3600 - 1


def test_codex_utilization_whose_pace_is_no_number_is_an_error_reading(monkeypatch, capsys):
    """Codex R2-3: a FINITE ``usedPercent`` of 1e308 overflows the pace to inf (printed as
    ``Infinity`` at exit 0), and a negative one gives a negative pace that wins the lane
    comparison. Both are no reading."""
    mod = _load("usage_codex")
    for used in (1e308, -5):
        result = _limits(_weekly(usedPercent=used, resetsAt=_week_ahead()), None)
        monkeypatch.setattr(mod, "read_rate_limits", lambda exe, timeout, r=result: r)
        assert mod.main(["--exe", "codex.exe"]) == 1, used
        out = capsys.readouterr().out
        assert "Infinity" not in out, used
        parsed = json.loads(out)
        assert parsed["lane"] == "codex" and "error" in parsed and "pace" not in parsed


def test_claude_utilization_whose_pace_is_no_number_is_an_error_reading(
    tmp_path, monkeypatch, capsys
):
    """Codex R2-3, the Claude readout: the same two inputs."""
    resets = dt.datetime.fromtimestamp(_week_ahead(), dt.UTC).isoformat()
    for util in (1e308, -5):
        def body(req, u=util):
            b = {"seven_day": {"utilization": u, "resets_at": resets}}
            return _Resp(json.dumps(b).encode("utf-8"))

        rc, out, _ = _run_claude(tmp_path, monkeypatch, capsys, body)
        assert rc == 1, util
        assert "Infinity" not in out, util
        parsed = json.loads(out)
        assert "error" in parsed and "pace" not in parsed, util


def test_codex_without_an_executable_is_no_reading(tmp_path, capsys):
    mod = _load("usage_codex")
    rc = mod.main(["--exe", str(tmp_path / "no-such-codex.exe"), "--timeout", "1"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["lane"] == "codex" and "error" in out


# ---------------------------------------------------------- the settings grant (P2) --
def test_settings_grant_is_the_exact_rule_and_records_the_operators_word():
    """The grant sits INSIDE ``permissions``: Claude Code's settings validator refuses an
    unrecognized TOP-LEVEL key (it rejected ``_comment_usage`` there, 2026-11-11), while
    ``permissions`` admits extra properties. The top level is otherwise unchanged."""
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert set(data) == {"hooks", "attribution", "permissions"}
    allow = data["permissions"]["allow"]
    assert "Bash(python scripts/usage_claude.py)" in allow
    assert [r for r in allow if "usage_claude" in r] == ["Bash(python scripts/usage_claude.py)"]
    assert not any("credentials" in r for r in allow)
    note = data["permissions"]["_comment_usage"]
    assert "scripts/usage_claude.py" in note
    assert "2026-11-03" in note and "2026-11-11" in note


# ------------------------------------------- the tiebreak with an unknown budget (N2) --
RECIPE = REPO_ROOT / "docs" / "implementer-dispatch-recipe.md"


def test_recipe_lane_row_routes_an_unknown_budget():
    """CHARC N2 (2026-11-11): a readout that prints ``error`` is an UNKNOWN budget, not a
    reading, so the tiebreak has nothing to compare. The recipe's section-2A Codex-lane row
    says where the build goes and that the operator hears of the error in the same turn."""
    rows = [
        ln
        for ln in RECIPE.read_text(encoding="utf-8").splitlines()
        if ln.startswith("| **Codex implementer lane**")
    ]
    assert len(rows) == 1
    for phrase in (
        "prints `error`",
        "UNKNOWN",
        "goes to the OTHER lane",
        "if both are unknown it goes to the Claude lane (the default)",
        "reports the error to the operator in the same turn",
    ):
        assert phrase in rows[0], phrase
