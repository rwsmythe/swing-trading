"""Tests for `scripts/record_schwab_cassettes.py` recording script.

Sub-bundle 1 T-1.0. Per plan §A.1.0 acceptance criterion #7 + Codex R4 Major #1
+ Major #2 + R5 Major #1 + Major #2 + R6 Major #1. 7 focused tests using mocked
schwabdev + tmp_path cassette files; do NOT exercise live Schwab API.

The recording script ships in T-1.0 before T-1.1..T-1.13 exists. It is the
HARD PREREQ that lets the operator pause the dispatch + record Schwab cassettes
on the worktree branch BEFORE the V2 mapper code or T-1.13 test consume them.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest


def _load_script() -> Path:
    """Locate the recording script in the repo (worktree-aware)."""
    here = Path(__file__).resolve()
    # Walk up to find scripts/record_schwab_cassettes.py.
    for parent in here.parents:
        candidate = parent / "scripts" / "record_schwab_cassettes.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "scripts/record_schwab_cassettes.py not found from "
        f"{here}",
    )


def _invoke_help() -> subprocess.CompletedProcess:
    """Invoke the script with `--help` via subprocess for argparse smoke."""
    script = _load_script()
    return subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


# Test 1 — CLI argparse defaults (per AC#7.a).
def test_argparse_defaults_required_order_types_and_days() -> None:
    """`--help` text documents the 4 REQUIRED defaults + `--days` default 30
    + REQUIRED `--environment` flag."""
    result = _invoke_help()
    assert result.returncode == 0, (
        f"--help should exit 0; stderr: {result.stderr!r}"
    )
    help_text = result.stdout
    # 4 REQUIRED order types default set.
    assert "limit_buy" in help_text
    assert "limit_sell" in help_text
    assert "stop_fired" in help_text
    assert "market_buy" in help_text
    # `--days` documented with default.
    assert "--days" in help_text
    assert "30" in help_text
    # `--environment` REQUIRED (no default).
    assert "--environment" in help_text


# Test 2 — argparse rejects unknown order-type.
def test_argparse_rejects_unknown_order_type() -> None:
    """Unknown order-type yields friendly error + non-zero exit."""
    script = _load_script()
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--environment",
            "sandbox",
            "--order-types",
            "junk_type",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0, (
        "Unknown order-type should exit non-zero; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "junk_type" in combined or "invalid" in combined or "unknown" in combined


# Test 3 — shared-filter import via tests.conftest.vcr_config (smoke).
def test_shared_vcr_filter_dict_importable() -> None:
    """`tests/conftest.py:vcr_config` fixture can be unwrapped to its underlying
    callable + that callable returns the same dict-shape the script consumes.
    """
    import tests.conftest as conftest_mod

    # pytest fixture-decorated functions expose `.__wrapped__` (per Python
    # functools convention); use the indirection the script also uses.
    fixture = getattr(conftest_mod, "vcr_config", None)
    assert fixture is not None, "vcr_config fixture missing from tests.conftest"
    # Resolve to the underlying callable. pytest wraps fixtures via
    # `_pytest.fixtures._pytest.fixtures.fixture()` which preserves `__wrapped__`
    # on the marker, but on some pytest versions the attribute is on
    # `fixture.func`. Try both.
    underlying = getattr(fixture, "__wrapped__", None) or getattr(
        fixture, "func", None,
    )
    assert underlying is not None, (
        "vcr_config fixture has neither __wrapped__ nor .func; "
        "fixture-indirection API broken"
    )
    cfg = underlying()
    assert isinstance(cfg, dict)
    # Sub-bundle 1 T-1.0 acceptance — filter dict must carry the 3 Schwab
    # request/response sanitization hooks.
    assert "filter_headers" in cfg
    assert "filter_query_parameters" in cfg
    assert "before_record_response" in cfg
    # T-1.0 NEW: `before_record_request` covers URL/path sanitization (Codex R2 C#1).
    assert "before_record_request" in cfg, (
        "Sub-bundle 1 T-1.0 requires before_record_request hook (Codex R2 C#1) "
        "for Schwab Trader API URL accountHash path-segment scrubbing"
    )
    # Schwab-specific extensions (per plan §F.3).
    assert "accountHash" in cfg["filter_query_parameters"]
    assert "accountNumber" in cfg["filter_query_parameters"]


# Test 4 — post-record validation gate FAILURE (per AC#7 + Codex R4 M#2).
def test_post_record_validation_failure_deletes_cassette(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock Schwab response with ZERO orders of requested type → script exits
    non-zero + stderr contains 'FAILED' + cassette file deleted +
    operator-actionable remediation text present."""
    # Build a minimal mock cassette environment.
    import importlib
    import sys as _sys

    # Force-import the script as a module.
    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes_test_mod_4", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["record_schwab_cassettes_test_mod_4"] = mod

    # Pre-create a sentinel cassette file so we can verify post-failure delete.
    cassette_dir = tmp_path / "cassettes" / "schwab"
    cassette_dir.mkdir(parents=True)

    # Monkeypatch the validation helper to fail by returning False from the
    # parsed-cassette inspector.
    spec.loader.exec_module(mod)

    # Build a fake cassette + an empty Schwab response (no matching order_type).
    cassette_path = cassette_dir / "test_e2e_limit_buy.yaml"
    cassette_path.write_text(
        "interactions: []\nversion: 1\n", encoding="utf-8",
    )
    # Validate: no orders matching limit_buy → expect False + remediation msg.
    ok, msg = mod._validate_cassette_contains_order_type(
        cassette_path=cassette_path,
        order_type="limit_buy",
        recorded_orders=[],  # empty: zero matching.
    )
    assert ok is False, "validation should fail when no matching order present"
    assert "limit_buy" in msg
    assert "FAILED" in msg or "operator action" in msg.lower()
    # The cassette is deleted by the caller (script main) on validation failure;
    # verify the helper that does the delete exists + works.
    assert cassette_path.exists()
    mod._safe_delete_cassette(cassette_path)
    assert not cassette_path.exists()


# Test 5 — post-record validation gate SUCCESS (per AC#7).
def test_post_record_validation_success_keeps_cassette(tmp_path: Path) -> None:
    """Mock Schwab response with at least one matching order having non-empty
    `executionLegs[]` → validation returns True; cassette persists."""
    import importlib
    import sys as _sys

    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes_test_mod_5", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["record_schwab_cassettes_test_mod_5"] = mod
    spec.loader.exec_module(mod)

    cassette_dir = tmp_path / "cassettes" / "schwab"
    cassette_dir.mkdir(parents=True)
    cassette_path = cassette_dir / "test_e2e_limit_buy.yaml"
    cassette_path.write_text("interactions: []\n", encoding="utf-8")

    recorded_orders = [
        {
            "orderId": "12345",
            "status": "FILLED",
            "orderType": "LIMIT",
            "orderLegCollection": [
                {"instruction": "BUY", "quantity": 100,
                 "instrument": {"symbol": "AAA"}},
            ],
            "orderActivityCollection": [
                {
                    "activityType": "EXECUTION",
                    "executionLegs": [
                        {"legId": 1, "price": 5.2244, "quantity": 100,
                         "time": "2026-05-15T10:00:00.000Z"},
                    ],
                },
            ],
        },
    ]
    ok, msg = mod._validate_cassette_contains_order_type(
        cassette_path=cassette_path,
        order_type="limit_buy",
        recorded_orders=recorded_orders,
    )
    assert ok is True, f"validation should succeed; msg: {msg!r}"
    assert cassette_path.exists()


# Test 6 — sentinel-leak audit gating.
def test_sentinel_leak_audit_deletes_cassette_on_match(tmp_path: Path) -> None:
    """Plant non-sanitized accountHash substring in cassette → audit returns
    non-zero count + caller deletes cassette + stderr-style msg cites
    'sentinel-leak' or 'accountHash'."""
    import importlib
    import sys as _sys

    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes_test_mod_6", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["record_schwab_cassettes_test_mod_6"] = mod
    spec.loader.exec_module(mod)

    cassette_dir = tmp_path / "cassettes" / "schwab"
    cassette_dir.mkdir(parents=True)
    cassette_path = cassette_dir / "test_e2e_dirty.yaml"
    # Plant an unsanitized JSON field that the audit MUST catch.
    cassette_path.write_text(
        '"accountNumber": "12345678",\n'
        '"accountHash": "abcdef0123456789abcdef0123456789ab",\n'
        '"access_token": "untouched-token-value-foo-bar-baz-quux",\n',
        encoding="utf-8",
    )
    matches = mod._scan_cassette_for_sentinel_leak(cassette_path)
    assert matches, "audit should report at least one leak match"
    # Audit must mention at least one of the sensitive shapes.
    flat = "\n".join(matches).lower()
    assert "accountnumber" in flat or "accounthash" in flat or "access_token" in flat


# Test 6b — R3 Critical #1 regression: bare numeric accountNumber
# (Schwab Trader API shape: `"accountNumber":27097300` NOT quoted) caught
# by sentinel-leak audit.
def test_sentinel_leak_audit_catches_bare_numeric_account_number(
    tmp_path: Path,
) -> None:
    """Schwab Trader API returns `accountNumber` as a BARE JSON NUMBER
    (NOT a quoted string). The pre-R3 quoted-only pattern missed this,
    leaking the operator's actual 27097300 account number into 3 committed
    cassettes (scrubbed in-place at the R3 fix commit). Regression pin: a
    cassette containing `\"accountNumber\":27097300` MUST surface in the
    audit findings."""
    import importlib
    import sys as _sys
    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes_test_mod_6b", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["record_schwab_cassettes_test_mod_6b"] = mod
    spec.loader.exec_module(mod)
    cassette_dir = tmp_path / "cassettes" / "schwab"
    cassette_dir.mkdir(parents=True)
    cassette_path = cassette_dir / "test_e2e_bare_num.yaml"
    cassette_path.write_text(
        '{"orderId": "X", "accountNumber":27097300, "status":"FILLED"}',
        encoding="utf-8",
    )
    matches = mod._scan_cassette_for_sentinel_leak(cassette_path)
    assert matches, "audit should catch bare-numeric accountNumber"
    flat = "\n".join(matches).lower()
    assert "bare numeric" in flat or "accountnumber" in flat


# Test 6c — bare-numeric accountNumber sanitization scrubber via
# `_redact_schwab_response_body` (the recording-time scrub path).
def test_response_body_scrubber_redacts_bare_numeric_account_number() -> None:
    """`tests/conftest.py:_redact_schwab_response_body` MUST scrub bare-
    numeric accountNumber values (Schwab Trader API shape) at recording
    time so they NEVER hit disk. Regression pin for the R3 Critical #1
    fix."""
    from tests.conftest import _redact_schwab_response_body
    response = {
        "body": {
            "string": (
                b'[{"orderId":"X","accountNumber":27097300,'
                b'"account_number":987654321,"status":"FILLED"}]'
            ),
        },
    }
    out = _redact_schwab_response_body(response)
    body = out["body"]["string"]
    if isinstance(body, str):
        body = body.encode("utf-8")
    # Both bare-numeric forms scrubbed.
    assert b"27097300" not in body
    assert b"987654321" not in body
    # Placeholder present.
    assert b"<REDACTED>" in body


# Test 7a — Codex R2 Major #2 fix: fail-closed behavior when conftest import
# fails (previously emitted unsafe minimal fallback dict).
def test_shared_filter_load_fails_closed_on_conftest_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_load_shared_vcr_kwargs()` MUST raise SystemExit when conftest import
    fails (NOT emit a minimal fallback dict that omits
    before_record_request + before_record_response — which would silently
    leak accountHash + tokens into committed cassettes)."""
    import importlib
    import sys as _sys

    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes_test_mod_7a", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["record_schwab_cassettes_test_mod_7a"] = mod
    spec.loader.exec_module(mod)

    # Force tests.conftest import to fail by patching its `vcr_config`
    # attribute to None — that triggers the AttributeError path inside
    # _load_shared_vcr_kwargs.
    import tests.conftest as conftest_mod
    monkeypatch.setattr(conftest_mod, "vcr_config", None, raising=False)
    with pytest.raises(SystemExit) as excinfo:
        mod._load_shared_vcr_kwargs()
    err_text = str(excinfo.value)
    assert "REFUSES to fall back" in err_text or "FAILED" in err_text


# Test 7b — Codex R2 Major #1 fix: cassette reload + parse helper.
def test_read_cassette_response_orders_parses_persisted_yaml(
    tmp_path: Path,
) -> None:
    """`_read_cassette_response_orders()` re-loads the cassette FROM DISK +
    parses the response body for post-record validation (NOT the in-memory
    live response). Discriminating test plants a minimal vcrpy-shape YAML
    + asserts the orders list extracts correctly."""
    import importlib
    import sys as _sys

    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes_test_mod_7b", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["record_schwab_cassettes_test_mod_7b"] = mod
    spec.loader.exec_module(mod)

    cassette_path = tmp_path / "test_e2e_x.yaml"
    cassette_path.write_text(
        "interactions:\n"
        "- response:\n"
        "    body:\n"
        '      string: \'[{"orderId": "X", "status": "FILLED"}]\'\n'
        "version: 1\n",
        encoding="utf-8",
    )
    persisted = mod._read_cassette_response_orders(cassette_path)
    assert isinstance(persisted, list)
    assert len(persisted) == 1
    assert persisted[0]["orderId"] == "X"


# Test 7c — cassette reload returns empty list on absent cassette.
def test_read_cassette_response_orders_absent_returns_empty(
    tmp_path: Path,
) -> None:
    import importlib
    import sys as _sys
    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes_test_mod_7c", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["record_schwab_cassettes_test_mod_7c"] = mod
    spec.loader.exec_module(mod)
    assert mod._read_cassette_response_orders(tmp_path / "nonexistent.yaml") == []


# Test 7 — auth + config bootstrap smoke (Codex R5 M#2 + R6 M#1 BINDING).
def test_auth_config_bootstrap_invokes_apply_overrides_and_construct_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock `construct_authenticated_client` AND `resolve_credentials_env_or_prompt`
    AND `apply_overrides`. Invoke script with `--environment sandbox` AND
    `--no-record` (smoke mode that exercises the bootstrap path without
    actually opening a vcr cassette). Assert:
        (a) `apply_overrides(cfg)` was invoked at script entry.
        (b) `resolve_credentials_env_or_prompt` invoked with
            `(cfg, 'sandbox', allow_prompt=False)`.
        (c) `construct_authenticated_client` invoked with ALL 4 named args
            (`cfg=`, `environment='sandbox'`, `client_id=<resolved>`,
            `client_secret=<resolved>`).
    """
    import importlib
    import sys as _sys

    script_path = _load_script()
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes_test_mod_7", str(script_path),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["record_schwab_cassettes_test_mod_7"] = mod
    spec.loader.exec_module(mod)

    # Mock the three dependencies the bootstrap path touches.
    fake_cfg_pre = mock.MagicMock(name="pre_overrides_cfg")
    fake_cfg_post = mock.MagicMock(name="post_overrides_cfg")
    fake_cfg_post.integrations.schwab.account_hash = "<account>"
    fake_client = mock.MagicMock(name="schwab_client")
    fake_client.account_orders.return_value = []

    apply_overrides_spy = mock.MagicMock(return_value=fake_cfg_post)
    resolve_creds_spy = mock.MagicMock(return_value=("CID", "CSECRET"))
    construct_client_spy = mock.MagicMock(return_value=fake_client)
    load_cfg_spy = mock.MagicMock(return_value=fake_cfg_pre)

    monkeypatch.setattr(mod, "_load_cfg", load_cfg_spy, raising=False)
    monkeypatch.setattr(
        mod, "_apply_overrides_thin", apply_overrides_spy, raising=False,
    )
    monkeypatch.setattr(
        mod, "_resolve_credentials_thin", resolve_creds_spy, raising=False,
    )
    monkeypatch.setattr(
        mod, "_construct_client_thin", construct_client_spy, raising=False,
    )

    # Bootstrap path only — skip the actual vcr cassette recording loop.
    result_client, result_cfg = mod._bootstrap_authenticated_client(
        environment="sandbox",
    )
    # Returned client is the fake; returned cfg is the post-overrides cfg.
    assert result_client is fake_client
    assert result_cfg is fake_cfg_post

    # (a) apply_overrides invoked with the loaded cfg.
    apply_overrides_spy.assert_called_once_with(fake_cfg_pre)

    # (b) resolve_credentials called with the post-overrides cfg + environment
    # + allow_prompt=False.
    resolve_creds_spy.assert_called_once()
    args, kwargs = resolve_creds_spy.call_args
    # Accept either positional or kwarg form.
    if args:
        assert args[0] is fake_cfg_post
        # environment may be positional or kwarg.
        if len(args) >= 2:
            assert args[1] == "sandbox"
        else:
            assert kwargs.get("environment") == "sandbox"
    else:
        assert kwargs.get("cfg") is fake_cfg_post
        assert kwargs.get("environment") == "sandbox"
    assert kwargs.get("allow_prompt") is False, (
        "must pass allow_prompt=False per Phase 12 Sub-bundle B precedent"
    )

    # (c) construct_authenticated_client invoked with ALL 4 named args.
    construct_client_spy.assert_called_once()
    cargs, ckwargs = construct_client_spy.call_args
    assert not cargs, (
        f"construct_authenticated_client must be called with kwargs only; "
        f"got positional: {cargs!r}"
    )
    assert ckwargs.get("cfg") is fake_cfg_post
    assert ckwargs.get("environment") == "sandbox"
    assert ckwargs.get("client_id") == "CID"
    assert ckwargs.get("client_secret") == "CSECRET"
