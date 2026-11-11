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
import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path

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
    """Run usage_claude.main with urlopen replaced; return (rc, stdout+stderr, requests)."""
    mod = _load("usage_claude")
    seen: list = []

    def fake_urlopen(req, timeout):
        seen.append(req)
        return behaviour(req)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
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
    assert json.loads(out)["lane"] == "claude"


def test_the_token_is_never_printed_on_any_path(tmp_path, monkeypatch, capsys):
    for behaviour in (_ok, _http_401, _url_error, _bad_body):
        rc, out, _ = _run_claude(tmp_path, monkeypatch, capsys, behaviour)
        assert SENTINEL not in out, behaviour.__name__
        assert "Bearer" not in out, behaviour.__name__
        if behaviour is not _ok:
            assert rc == 1, behaviour.__name__
            assert json.loads(out)["lane"] == "claude"
            assert "error" in json.loads(out)


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
