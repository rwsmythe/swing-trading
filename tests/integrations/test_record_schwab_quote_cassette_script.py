"""Tests for `scripts/record_schwab_quote_cassette.py` (Gate 4 enablement).

Phase 15 / data-integrity arc Slice-B Gate 4. The recorder produces the
sanitized VCR cassette `tests/integrations/schwab/cassettes/quote_regular_fields.yaml`
from one live `client.quotes(...)` call so the slow gate test
`tests/integrations/schwab/test_quote_fields_live.py` (a pure substring grep
for the 4 `regularMarket*` fields) passes after the operator's market-open
recording step.

These tests are MOCK-based: they NEVER make a live Schwab call. The full
`vcr.use_cassette` + `client.quotes` live recording is the operator's
market-open step. We test the seams: argparse surface, the reused fail-closed
sanitization loader, the 4-field validation, the leak-scan, the record
orchestration (with a fake vcr + a mock client that writes the cassette), and
that `main` resolves the EXACT gate-test cassette path.
"""
from __future__ import annotations

import contextlib
import importlib.util
import subprocess
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

# Exact gate-test path (mirror tests/integrations/schwab/test_quote_fields_live.py).
_GATE_RELPATH = Path("tests/integrations/schwab/cassettes/quote_regular_fields.yaml")
_REGULAR_FIELDS = (
    "regularMarketLastPrice",
    "regularMarketTradeTime",
    "regularMarketBidPrice",
    "regularMarketAskPrice",
)


def _load_script() -> Path:
    """Locate the quote recorder script in the repo (worktree-aware)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "scripts" / "record_schwab_quote_cassette.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"scripts/record_schwab_quote_cassette.py not found from {here}",
    )


_MOD_COUNTER = 0


def _load_module() -> types.ModuleType:
    """Import the quote recorder as a fresh module (unique name per load)."""
    global _MOD_COUNTER
    _MOD_COUNTER += 1
    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        f"record_schwab_quote_cassette_test_mod_{_MOD_COUNTER}", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_QUOTES_URI = (
    "https://api.schwabapi.com/marketdata/v1/quotes?symbols=AAPL&fields=quote"
)


def _yaml_cassette_with_fields(
    fields: tuple[str, ...], *, extra_body: str = "", uri: str = _QUOTES_URI,
) -> str:
    """Build a minimal single-interaction vcrpy cassette text.

    One interaction whose request targets the quotes endpoint + whose response
    body carries the given quote fields. `extra_body` injects extra JSON into
    the outer object (used to plant an unsanitized token for the leak test)."""
    quote_fields = ", ".join(f'"{f}": 1' for f in fields)
    body = '{"AAPL": {"quote": {' + quote_fields + "}}" + extra_body + "}"
    return (
        "interactions:\n"
        "- request:\n"
        "    method: GET\n"
        f"    uri: {uri}\n"
        "  response:\n"
        "    body:\n"
        f"      string: '{body}'\n"
        "version: 1\n"
    )


# --- Test 1: argparse --help surface ---------------------------------------
def test_argparse_help_documents_surface() -> None:
    script = _load_script()
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode == 0, f"--help should exit 0; stderr: {result.stderr!r}"
    help_text = result.stdout
    assert "--environment" in help_text
    assert "--symbols" in help_text
    assert "AAPL" in help_text
    assert "--fields" in help_text
    assert "quote" in help_text


# --- Test 2: argparse rejects an unknown environment -----------------------
def test_argparse_rejects_unknown_environment() -> None:
    script = _load_script()
    result = subprocess.run(
        [sys.executable, str(script), "--environment", "junk"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode != 0, (
        f"unknown environment should exit non-zero; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "junk" in combined or "invalid" in combined or "choose from" in combined


# --- Test 3: reused fail-closed sanitization loader ------------------------
def test_shared_vcr_filter_dict_is_reused_canonical() -> None:
    """`_load_shared_vcr_kwargs()` delegates to the order recorder's
    fail-closed loader (single source of truth = tests/conftest.py:vcr_config).
    Proves the recorder reuses the canonical sanitization hooks, not an inline
    fallback dict."""
    mod = _load_module()
    cfg = mod._load_shared_vcr_kwargs()
    assert isinstance(cfg, dict)
    assert "before_record_request" in cfg
    assert "before_record_response" in cfg
    assert "filter_headers" in cfg
    assert "filter_query_parameters" in cfg
    assert "accountHash" in cfg["filter_query_parameters"]
    assert "accountNumber" in cfg["filter_query_parameters"]


# --- Test 4 & 5: 4-field validation (discriminating pair) ------------------
def test_validate_all_four_fields_present_passes(tmp_path: Path) -> None:
    mod = _load_module()
    cassette = tmp_path / "quote_regular_fields.yaml"
    cassette.write_text(_yaml_cassette_with_fields(_REGULAR_FIELDS), encoding="utf-8")
    ok, msg = mod._validate_quote_cassette_has_regular_fields(cassette)
    assert ok is True, f"all 4 fields present should pass; msg={msg!r}"
    assert msg == ""


def test_validate_missing_bid_field_fails_with_oq3_message(tmp_path: Path) -> None:
    """One missing field -> (False, actionable OQ-3 message naming the field +
    the fields=all / yfinance-drop decision). Distinguishes from the all-present
    pass above (feedback_regression_test_arithmetic)."""
    mod = _load_module()
    present = tuple(f for f in _REGULAR_FIELDS if f != "regularMarketBidPrice")
    cassette = tmp_path / "quote_regular_fields.yaml"
    cassette.write_text(_yaml_cassette_with_fields(present), encoding="utf-8")
    ok, msg = mod._validate_quote_cassette_has_regular_fields(cassette)
    assert ok is False
    assert "regularMarketBidPrice" in msg
    assert "OQ-3" in msg
    assert "all" in msg and "fields" in msg.lower()


def test_validate_absent_cassette_fails(tmp_path: Path) -> None:
    mod = _load_module()
    ok, msg = mod._validate_quote_cassette_has_regular_fields(
        tmp_path / "nonexistent.yaml",
    )
    assert ok is False
    assert "FAILED" in msg


# --- single-interaction guard (Codex R1 MAJOR fix) -------------------------
def test_single_interaction_guard_passes_for_one_quote_interaction(
    tmp_path: Path,
) -> None:
    mod = _load_module()
    cassette = tmp_path / "quote_regular_fields.yaml"
    cassette.write_text(_yaml_cassette_with_fields(_REGULAR_FIELDS), encoding="utf-8")
    ok, msg = mod._validate_quote_cassette_single_interaction(cassette)
    assert ok is True, f"single quotes interaction should pass; msg={msg!r}"
    assert msg == ""


def test_single_interaction_guard_fails_on_multiple_interactions(
    tmp_path: Path,
) -> None:
    """A stale-token OAuth refresh captured alongside the quote -> 2 interactions
    -> reject with an actionable 'refresh' message (distinguishes from the
    single-interaction pass above)."""
    mod = _load_module()
    cassette = tmp_path / "quote_regular_fields.yaml"
    # Quote interaction + a second (refresh-like) interaction, both under the
    # interactions: list (well-formed vcrpy shape).
    quote_fields = ", ".join(f'"{f}": 1' for f in _REGULAR_FIELDS)
    quote_body = '{"AAPL": {"quote": {' + quote_fields + "}}}"
    cassette.write_text(
        "interactions:\n"
        "- request:\n"
        "    method: GET\n"
        f"    uri: {_QUOTES_URI}\n"
        "  response:\n"
        "    body:\n"
        f"      string: '{quote_body}'\n"
        "- request:\n"
        "    method: POST\n"
        "    uri: https://api.schwabapi.com/v1/oauth/token\n"
        "  response:\n"
        "    body:\n"
        "      string: '{\"access_token\": \"x\"}'\n"
        "version: 1\n",
        encoding="utf-8",
    )
    ok, msg = mod._validate_quote_cassette_single_interaction(cassette)
    assert ok is False
    assert "2 interaction" in msg
    assert "refresh" in msg.lower()


def test_single_interaction_guard_rejects_non_quotes_path(tmp_path: Path) -> None:
    """Codex R2 MINOR: a single interaction whose request PATH is not the quotes
    endpoint (but whose query string happens to carry `fields=quote`) must be
    rejected -- the predicate parses the URI path, not a loose substring."""
    mod = _load_module()
    cassette = tmp_path / "quote_regular_fields.yaml"
    bad_uri = (
        "https://api.schwabapi.com/marketdata/v1/chains?symbols=AAPL&fields=quote"
    )
    cassette.write_text(
        _yaml_cassette_with_fields(_REGULAR_FIELDS, uri=bad_uri), encoding="utf-8",
    )
    ok, msg = mod._validate_quote_cassette_single_interaction(cassette)
    assert ok is False
    assert "quotes endpoint" in msg


# --- Test 6: leak-scan reuses the canonical catalog ------------------------
def test_leak_scan_flags_unsanitized_token(tmp_path: Path) -> None:
    mod = _load_module()
    cassette = tmp_path / "dirty.yaml"
    cassette.write_text(
        '"access_token": "untouched-token-value-foo-bar-baz-quux",\n'
        '"accountHash": "abcdef0123456789abcdef0123456789ab",\n',
        encoding="utf-8",
    )
    matches = mod._scan_cassette_for_sentinel_leak(cassette)
    assert matches, "leak audit should report at least one finding"
    flat = "\n".join(matches).lower()
    assert "access_token" in flat or "accounthash" in flat


# --- Test 7/8/9: record orchestration (fake vcr + mock client) -------------
def _install_fake_vcr(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_vcr = types.SimpleNamespace(
        use_cassette=lambda *a, **k: contextlib.nullcontext(),
    )
    monkeypatch.setitem(sys.modules, "vcr", fake_vcr)


def test_record_keeps_cassette_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    _install_fake_vcr(monkeypatch)
    cassette = tmp_path / "quote_regular_fields.yaml"
    text = _yaml_cassette_with_fields(_REGULAR_FIELDS)

    def _quotes(**kwargs):
        cassette.write_text(text, encoding="utf-8")
        return {"AAPL": {"quote": {}}}

    client = mock.MagicMock()
    client.quotes.side_effect = _quotes
    rc = mod._record_quote_cassette(
        client=client, symbols=["AAPL"], fields="quote",
        cassette_path=cassette, vcr_kwargs={},
    )
    assert rc == 0
    assert cassette.exists()
    client.quotes.assert_called_once_with(symbols=["AAPL"], fields="quote")


def test_record_deletes_cassette_when_field_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    _install_fake_vcr(monkeypatch)
    cassette = tmp_path / "quote_regular_fields.yaml"
    present = tuple(f for f in _REGULAR_FIELDS if f != "regularMarketAskPrice")
    text = _yaml_cassette_with_fields(present)

    def _quotes(**kwargs):
        cassette.write_text(text, encoding="utf-8")
        return {}

    client = mock.MagicMock()
    client.quotes.side_effect = _quotes
    rc = mod._record_quote_cassette(
        client=client, symbols=["AAPL"], fields="quote",
        cassette_path=cassette, vcr_kwargs={},
    )
    assert rc != 0
    assert not cassette.exists(), "missing-field cassette must be deleted, not committed"


def test_record_deletes_cassette_on_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    _install_fake_vcr(monkeypatch)
    cassette = tmp_path / "quote_regular_fields.yaml"
    # A valid single quotes interaction with all 4 fields BUT an unsanitized
    # token leaked in the (double-quoted JSON) response body -- the shape a real
    # cassette leak takes. Field + single-interaction checks pass; the leak-scan
    # must still delete the cassette.
    leaked = _yaml_cassette_with_fields(
        _REGULAR_FIELDS,
        extra_body=', "access_token": "untouched-token-value-foo-bar-baz-quux"',
    )

    def _quotes(**kwargs):
        cassette.write_text(leaked, encoding="utf-8")
        return {}

    client = mock.MagicMock()
    client.quotes.side_effect = _quotes
    rc = mod._record_quote_cassette(
        client=client, symbols=["AAPL"], fields="quote",
        cassette_path=cassette, vcr_kwargs={},
    )
    assert rc != 0
    assert not cassette.exists(), "leaking cassette must be deleted, not committed"


def test_record_reports_delete_failure_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """Codex R2 MAJOR: if a failing cassette cannot be deleted (delegated delete
    swallows OSError / file locked), the recorder must NOT claim success -- it
    returns the distinct DELETE_FAILED_CODE + prints 'DELETE FAILED' + the file
    remains for the operator to remove by hand."""
    mod = _load_module()
    _install_fake_vcr(monkeypatch)
    # Make every delete a no-op so the leaking cassette survives the attempt.
    monkeypatch.setattr(mod, "_safe_delete_cassette", lambda p: None, raising=True)
    cassette = tmp_path / "quote_regular_fields.yaml"
    leaked = _yaml_cassette_with_fields(
        _REGULAR_FIELDS,
        extra_body=', "access_token": "untouched-token-value-foo-bar-baz-quux"',
    )

    def _quotes(**kwargs):
        cassette.write_text(leaked, encoding="utf-8")
        return {}

    client = mock.MagicMock()
    client.quotes.side_effect = _quotes
    rc = mod._record_quote_cassette(
        client=client, symbols=["AAPL"], fields="quote",
        cassette_path=cassette, vcr_kwargs={},
    )
    assert rc == mod.DELETE_FAILED_CODE
    assert "DELETE FAILED" in capsys.readouterr().err
    assert cassette.exists(), "no-op delete leaves the file; operator must remove it"


def test_record_reraises_baseexception_and_deletes_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex R2 MAJOR: a KeyboardInterrupt/SystemExit during the vcr block (VCR
    may flush a partial cassette on __exit__) must delete the partial cassette
    and RE-RAISE, never silently swallow the interruption."""
    mod = _load_module()
    _install_fake_vcr(monkeypatch)
    cassette = tmp_path / "quote_regular_fields.yaml"

    def _quotes(**kwargs):
        cassette.write_text("partial-unvalidated-content\n", encoding="utf-8")
        raise KeyboardInterrupt

    client = mock.MagicMock()
    client.quotes.side_effect = _quotes
    with pytest.raises(KeyboardInterrupt):
        mod._record_quote_cassette(
            client=client, symbols=["AAPL"], fields="quote",
            cassette_path=cassette, vcr_kwargs={},
        )
    assert not cassette.exists(), "partial cassette must be deleted on interruption"


def test_record_bails_if_preexisting_cassette_cannot_be_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """Codex R3 MAJOR: the pre-record delete is verified. If a stale cassette
    survives a swallowed delete, recording against it (record_mode=new_episodes)
    could be mistaken for a fresh recording. The recorder must bail with code 6
    + 'DELETE FAILED' BEFORE making the live call."""
    mod = _load_module()
    _install_fake_vcr(monkeypatch)
    monkeypatch.setattr(mod, "_safe_delete_cassette", lambda p: None, raising=True)
    cassette = tmp_path / "quote_regular_fields.yaml"
    # A pre-existing, superficially-valid cassette that the no-op delete leaves.
    cassette.write_text(_yaml_cassette_with_fields(_REGULAR_FIELDS), encoding="utf-8")

    client = mock.MagicMock()
    rc = mod._record_quote_cassette(
        client=client, symbols=["AAPL"], fields="quote",
        cassette_path=cassette, vcr_kwargs={},
    )
    assert rc == mod.DELETE_FAILED_CODE
    assert "DELETE FAILED" in capsys.readouterr().err
    client.quotes.assert_not_called()  # never reach the live call against stale data


def test_record_baseexception_delete_failure_warns_and_reraises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """Codex R3 MAJOR: the BaseException cleanup arm also verifies removal. If
    the partial cassette cannot be deleted on interruption, emit 'DELETE FAILED'
    + still re-raise."""
    mod = _load_module()
    _install_fake_vcr(monkeypatch)
    cassette = tmp_path / "quote_regular_fields.yaml"
    # The pre-record delete must succeed (file absent), but the post-interrupt
    # delete must be a no-op. Swap the helper to no-op only after the first call.
    real_delete = mod._safe_delete_cassette
    calls = {"n": 0}

    def _delete(path):
        calls["n"] += 1
        if calls["n"] == 1:
            real_delete(path)  # pre-record delete works (file absent anyway)

    monkeypatch.setattr(mod, "_safe_delete_cassette", _delete, raising=True)

    def _quotes(**kwargs):
        cassette.write_text("partial-unvalidated-content\n", encoding="utf-8")
        raise KeyboardInterrupt

    client = mock.MagicMock()
    client.quotes.side_effect = _quotes
    with pytest.raises(KeyboardInterrupt):
        mod._record_quote_cassette(
            client=client, symbols=["AAPL"], fields="quote",
            cassette_path=cassette, vcr_kwargs={},
        )
    assert "DELETE FAILED" in capsys.readouterr().err
    assert cassette.exists(), "no-op post-interrupt delete leaves the partial file"


# --- Test 10: bootstrap delegation forwards args ---------------------------
def test_bootstrap_delegation_forwards_args(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_module()
    order = mod._order_module()
    spy = mock.MagicMock(return_value=("CLIENT", "CFG"))
    monkeypatch.setattr(order, "_bootstrap_authenticated_client", spy, raising=True)
    out = mod._bootstrap_authenticated_client(
        environment="sandbox", config_path=Path("swing.config.toml"),
    )
    assert out == ("CLIENT", "CFG")
    spy.assert_called_once_with(
        environment="sandbox", config_path=Path("swing.config.toml"),
    )


# --- Test 11: main writes the EXACT gate-test path -------------------------
def test_main_writes_exact_gate_cassette_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`main` must resolve the cassette to EXACTLY
    <repo_root>/tests/integrations/schwab/cassettes/quote_regular_fields.yaml
    (the gate test's path). Patch repo-root to tmp_path + the auth/filter seams
    + a fake vcr that writes the 4-field cassette; assert the file lands at the
    exact relative path under tmp_path."""
    mod = _load_module()
    _install_fake_vcr(monkeypatch)
    expected = tmp_path / _GATE_RELPATH
    text = _yaml_cassette_with_fields(_REGULAR_FIELDS)

    def _quotes(**kwargs):
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_text(text, encoding="utf-8")
        return {"AAPL": {"quote": {}}}

    fake_client = mock.MagicMock()
    fake_client.quotes.side_effect = _quotes

    monkeypatch.setattr(
        mod, "_bootstrap_authenticated_client",
        mock.MagicMock(return_value=(fake_client, mock.MagicMock())), raising=True,
    )
    monkeypatch.setattr(
        mod, "_load_shared_vcr_kwargs", mock.MagicMock(return_value={}), raising=True,
    )
    monkeypatch.setattr(
        mod, "_resolve_repo_root", mock.MagicMock(return_value=tmp_path), raising=True,
    )

    rc = mod.main(["--environment", "sandbox"])
    assert rc == 0
    assert expected.exists(), (
        f"main must write the cassette to the exact gate path {expected}"
    )
