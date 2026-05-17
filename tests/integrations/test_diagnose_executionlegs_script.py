"""Tests for `scripts/diagnose_schwab_executionlegs.py`.

Sub-bundle 1.5 T-1.5.1. Per dispatch brief Section 0.4 + Section 0.5 #5 sentinel-leak audit
BINDING contract. The script is invoked operator-paired against live Schwab
production; these tests use mocked schwabdev + tmp_path + planted-sentinel
payloads to verify:

  1. `--help` exits 0 and documents expected flags.
  2. Redaction scrubs all 5 long-lived sensitive slots (sentinel-leak audit).
  3. Leg-shape comparator correctly identifies missing / unexpected / wrong-
     type keys + None-on-required values.
  4. Defensive parsing -- comparator does not raise on malformed leg shapes;
     iterate_orders_with_legs handles non-dict orders + non-list activities.
  5. Bootstrap helper is mock-patchable (test runs without live network).
  6. Output file path is computed deterministically + scrubbed for timestamp.

The 5-sentinel audit is the BINDING test per the brief -- plants non-token-
shaped sentinels at all 5 slots in a mock response payload + asserts ZERO
matches in the rendered output text.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

import pytest


def _load_script_path() -> Path:
    """Locate the diagnostic script (worktree-aware)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "scripts" / "diagnose_schwab_executionlegs.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"scripts/diagnose_schwab_executionlegs.py not found from {here}"
    )


def _import_script_module():
    """Import the script as a Python module without invoking main."""
    path = _load_script_path()
    spec = importlib.util.spec_from_file_location(
        "_diagnose_schwab_executionlegs_under_test", str(path)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Test 1 -- argparse `--help` smoke (subprocess; ensures the file is a valid
# standalone Python script).
# ---------------------------------------------------------------------------

def test_help_exits_zero_and_documents_flags() -> None:
    """`--help` exits 0 and documents the expected flags."""
    script = _load_script_path()
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode == 0, (
        f"--help should exit 0; stderr: {result.stderr!r}"
    )
    out = result.stdout
    assert "--environment" in out
    assert "--max-orders" in out
    assert "--lookback-days" in out
    assert "--max-legs-per-order" in out
    assert "production" in out
    assert "sandbox" in out


# ---------------------------------------------------------------------------
# Test 2 -- sentinel-leak audit. The BINDING contract per brief Section 0.5 #5.
# ---------------------------------------------------------------------------

# Non-token-shaped sentinels (so they don't accidentally trigger Layer 1
# hex32+ / base64-40+ heuristic redaction; we want to confirm the per-slot
# JSON-key regex AND the explicit known_secrets exact-replace fire).
_SENTINEL_CLIENT_ID = "DIAG_SENTINEL_CLIENT_ID_xyz123"
_SENTINEL_CLIENT_SECRET = "DIAG_SENTINEL_CLIENT_SECRET_xyz456"
_SENTINEL_ACCESS_TOKEN = "DIAG_SENTINEL_ACCESS_TOKEN_xyz789"
_SENTINEL_REFRESH_TOKEN = "DIAG_SENTINEL_REFRESH_TOKEN_xyz000"
_SENTINEL_ACCOUNT_HASH = "DIAG_SENTINEL_ACCOUNT_HASH_xyz111"
_SENTINEL_ACCOUNT_NUMBER_QUOTED = "DIAG_SENTINEL_ACCT_NO_QUOTED"


def test_redact_text_scrubs_all_five_long_lived_sentinels() -> None:
    """Layer 0 (known_secrets) scrubs the 5 long-lived sensitive slots."""
    mod = _import_script_module()
    # Compose a string with all 5 sentinels in plain prose AND JSON-key form
    # (the latter is what raw Schwab responses look like after pretty-print).
    blob = (
        f"client_id was {_SENTINEL_CLIENT_ID} "
        f"and client_secret={_SENTINEL_CLIENT_SECRET}; "
        f"access_token: {_SENTINEL_ACCESS_TOKEN}; "
        f"refresh_token: {_SENTINEL_REFRESH_TOKEN}; "
        f"account_hash: {_SENTINEL_ACCOUNT_HASH}; "
        f'"accountNumber": "{_SENTINEL_ACCOUNT_NUMBER_QUOTED}"; '
        f'"accountHash": "{_SENTINEL_ACCOUNT_HASH}"; '
        f'"access_token": "{_SENTINEL_ACCESS_TOKEN}"; '
        f'"refresh_token": "{_SENTINEL_REFRESH_TOKEN}"'
    )
    redacted = mod.redact_text(
        blob,
        known_secrets=[
            _SENTINEL_CLIENT_ID,
            _SENTINEL_CLIENT_SECRET,
            _SENTINEL_ACCESS_TOKEN,
            _SENTINEL_REFRESH_TOKEN,
            _SENTINEL_ACCOUNT_HASH,
        ],
    )
    # The BINDING assertion -- zero sentinel substrings remain.
    for sentinel in (
        _SENTINEL_CLIENT_ID,
        _SENTINEL_CLIENT_SECRET,
        _SENTINEL_ACCESS_TOKEN,
        _SENTINEL_REFRESH_TOKEN,
        _SENTINEL_ACCOUNT_HASH,
    ):
        assert sentinel not in redacted, (
            f"Sentinel {sentinel!r} leaked through redaction. Output: "
            f"{redacted!r}"
        )
    # The accountNumber JSON-key form should also be scrubbed by Layer 1a.
    assert _SENTINEL_ACCOUNT_NUMBER_QUOTED not in redacted, (
        f"accountNumber JSON-key sentinel "
        f"{_SENTINEL_ACCOUNT_NUMBER_QUOTED!r} leaked. Output: {redacted!r}"
    )


def test_redact_text_scrubs_long_hex_and_base64_sequences() -> None:
    """Layer 1b + 1c scrub bare 32+ hex and 40+ base64 sequences."""
    mod = _import_script_module()
    hex_blob = "a" * 32 + "b" * 16
    b64_blob = "Z" * 40 + "Y" * 8
    out = mod.redact_text(hex_blob + " --- " + b64_blob)
    assert "a" * 32 not in out
    assert "Z" * 40 not in out
    assert "<REDACTED:hex32+>" in out
    assert "<REDACTED:b64-40+>" in out


def test_redact_text_is_safe_on_empty_input() -> None:
    """Redactor returns empty input unchanged (no exception)."""
    mod = _import_script_module()
    assert mod.redact_text("") == ""
    assert mod.redact_text("", known_secrets=["whatever"]) == ""


# ---------------------------------------------------------------------------
# Test 3 -- comparator correctness on known-good + known-divergent shapes.
# ---------------------------------------------------------------------------

def _well_formed_leg() -> dict:
    return {
        "legId": 1,
        "price": 5.23,
        "quantity": 100.0,
        "mismarkedQuantity": 0.0,
        "instrumentId": 12345,
        "time": "2026-05-15T13:30:00.000Z",
    }


def test_compare_leg_well_formed_passes_validator() -> None:
    mod = _import_script_module()
    leg = _well_formed_leg()
    report = mod.compare_leg_to_expected(leg)
    assert report["is_dict"] is True
    assert report["missing_keys"] == []
    assert report["unexpected_keys"] == []
    assert report["wrong_type"] == {}
    assert report["none_values"] == []
    assert report["would_pass_type_shape_only"] is True


def test_compare_leg_missing_time_flagged() -> None:
    mod = _import_script_module()
    leg = _well_formed_leg()
    del leg["time"]
    report = mod.compare_leg_to_expected(leg)
    assert "time" in report["missing_keys"]
    assert report["would_pass_type_shape_only"] is False


def test_compare_leg_unexpected_orderid_key_flagged() -> None:
    """If Schwab sends an extra key like `orderId`, comparator reports it."""
    mod = _import_script_module()
    leg = _well_formed_leg()
    leg["orderId"] = "some-order-id"
    report = mod.compare_leg_to_expected(leg)
    assert "orderId" in report["unexpected_keys"]
    # Unexpected keys do NOT fail the validator (it uses .get()), so this
    # would still pass.
    assert report["would_pass_type_shape_only"] is True


def test_compare_leg_wrong_type_for_price_flagged() -> None:
    mod = _import_script_module()
    leg = _well_formed_leg()
    leg["price"] = "5.23"  # str, not number
    report = mod.compare_leg_to_expected(leg)
    assert "price" in report["wrong_type"]
    assert "str" in report["wrong_type"]["price"]
    assert report["would_pass_type_shape_only"] is False


def test_compare_leg_bool_as_number_for_quantity_flagged() -> None:
    """Python bool is a subclass of int; mapper rejects bool defensively."""
    mod = _import_script_module()
    leg = _well_formed_leg()
    leg["quantity"] = True
    report = mod.compare_leg_to_expected(leg)
    assert "quantity" in report["wrong_type"]
    assert "bool" in report["wrong_type"]["quantity"]


def test_compare_leg_none_required_field_flagged() -> None:
    mod = _import_script_module()
    leg = _well_formed_leg()
    leg["time"] = None
    report = mod.compare_leg_to_expected(leg)
    # `time` is required + non-empty str; None is wrong type, so it lands
    # in wrong_type (not none_values).
    assert "time" in report["wrong_type"]
    assert report["would_pass_type_shape_only"] is False


def test_compare_leg_optional_none_acceptable() -> None:
    """mismarkedQuantity + instrumentId legitimately accept None."""
    mod = _import_script_module()
    leg = _well_formed_leg()
    leg["mismarkedQuantity"] = None
    leg["instrumentId"] = None
    report = mod.compare_leg_to_expected(leg)
    assert report["would_pass_type_shape_only"] is True


# ---------------------------------------------------------------------------
# Test 4 -- defensive parsing (never raise on malformed shapes).
# ---------------------------------------------------------------------------

def test_compare_leg_handles_non_dict_input() -> None:
    """Comparator does NOT raise on str / None / list / int inputs."""
    mod = _import_script_module()
    for bad_input in ("not a dict", None, [], 42, 3.14):
        report = mod.compare_leg_to_expected(bad_input)
        assert report["is_dict"] is False
        assert report["would_pass_type_shape_only"] is False


def test_iterate_orders_with_legs_handles_non_dict_order() -> None:
    """Non-dict orders are skipped with a 'note' but do not raise."""
    mod = _import_script_module()
    orders = [
        "not a dict",
        None,
        {"orderId": "abc", "orderActivityCollection": [
            {"activityType": "EXECUTION", "executionLegs": [_well_formed_leg()]},
        ]},
    ]
    captures = mod.iterate_orders_with_legs(orders)
    assert len(captures) == 3
    assert captures[0].get("note") == "skipped: order not a dict"
    assert captures[1].get("note") == "skipped: order not a dict"
    assert captures[2].get("order_id") == "abc"
    assert len(captures[2]["legs_captured"]) == 1


def test_iterate_orders_with_legs_handles_non_list_activities() -> None:
    """Order with non-list orderActivityCollection: skip silently."""
    mod = _import_script_module()
    orders = [
        {"orderId": "abc", "orderActivityCollection": "not a list"},
    ]
    captures = mod.iterate_orders_with_legs(orders)
    assert len(captures) == 1
    assert captures[0]["legs_captured"] == []
    assert captures[0]["activity_count"] == 0


def test_iterate_orders_with_legs_handles_non_dict_leg() -> None:
    """Non-dict legs are captured but flagged is_dict=False."""
    mod = _import_script_module()
    orders = [
        {
            "orderId": "abc",
            "orderActivityCollection": [
                {
                    "activityType": "EXECUTION",
                    "executionLegs": ["not a dict", None, _well_formed_leg()],
                },
            ],
        },
    ]
    captures = mod.iterate_orders_with_legs(
        orders, max_legs_per_order=10,
    )
    legs = captures[0]["legs_captured"]
    assert len(legs) == 3
    # First leg is the str -- comparator marks is_dict=False.
    assert legs[0]["comparator_report"]["is_dict"] is False
    assert legs[1]["comparator_report"]["is_dict"] is False
    assert legs[2]["comparator_report"]["is_dict"] is True


def test_iterate_orders_caps_max_legs_per_order() -> None:
    """max_legs_per_order bounds output verbosity."""
    mod = _import_script_module()
    legs = [_well_formed_leg() for _ in range(10)]
    orders = [{
        "orderId": "abc",
        "orderActivityCollection": [
            {"activityType": "EXECUTION", "executionLegs": legs},
        ],
    }]
    captures = mod.iterate_orders_with_legs(orders, max_legs_per_order=2)
    assert len(captures[0]["legs_captured"]) == 2


# ---------------------------------------------------------------------------
# Test 5 -- output file path computation (deterministic, timestamp-scrubbed).
# ---------------------------------------------------------------------------

def test_compute_output_path_uses_provided_output_dir(tmp_path: Path) -> None:
    mod = _import_script_module()
    fixed_now = datetime(2026, 5, 17, 12, 34, 56, tzinfo=UTC)
    out = mod.compute_output_path(output_dir=tmp_path, now=fixed_now)
    assert out.parent == tmp_path
    assert out.name == "diagnose-schwab-executionlegs-20260517T123456Z.txt"


def test_compute_output_path_default_is_under_swing_data(tmp_path: Path, monkeypatch) -> None:
    """Default path is under ~/swing-data (operator-local; gitignored)."""
    mod = _import_script_module()
    # Monkeypatch HOME / USERPROFILE so the test does NOT write to operator's
    # real home directory (per CLAUDE.md gotcha for write_user_overrides
    # family -- same discipline applies to any Path.home() consumer).
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    out = mod.compute_output_path(
        now=datetime(2026, 5, 17, 8, 0, 0, tzinfo=UTC),
    )
    # Path.home() resolves via $HOME on POSIX and $USERPROFILE on Windows.
    assert "swing-data" in out.parts
    assert out.name == "diagnose-schwab-executionlegs-20260517T080000Z.txt"


# ---------------------------------------------------------------------------
# Test 6 -- bootstrap helper is mock-patchable (no live network required).
# ---------------------------------------------------------------------------

def test_bootstrap_authenticated_client_is_mockable() -> None:
    """Thin seams allow tests to bypass live cfg load + schwabdev construction."""
    mod = _import_script_module()
    fake_cfg = mock.MagicMock()
    fake_cfg.integrations.schwab.account_hash = _SENTINEL_ACCOUNT_HASH
    fake_client = mock.MagicMock()
    fake_client.tokens.access_token = _SENTINEL_ACCESS_TOKEN
    fake_client.tokens.refresh_token = _SENTINEL_REFRESH_TOKEN
    with (
        mock.patch.object(mod, "_load_cfg", return_value=fake_cfg),
        mock.patch.object(mod, "_apply_overrides_thin", return_value=fake_cfg),
        mock.patch.object(
            mod, "_resolve_credentials_thin",
            return_value=(_SENTINEL_CLIENT_ID, _SENTINEL_CLIENT_SECRET),
        ),
        mock.patch.object(
            mod, "_construct_client_thin", return_value=fake_client,
        ),
    ):
        client, cfg, known_secrets = mod._bootstrap_authenticated_client(
            environment="production",
            config_path=Path("dummy.toml"),
        )
    assert client is fake_client
    assert cfg is fake_cfg
    # All 5 sensitive slots gathered into known_secrets.
    for sentinel in (
        _SENTINEL_CLIENT_ID, _SENTINEL_CLIENT_SECRET,
        _SENTINEL_ACCESS_TOKEN, _SENTINEL_REFRESH_TOKEN,
        _SENTINEL_ACCOUNT_HASH,
    ):
        assert sentinel in known_secrets


def test_bootstrap_raises_on_silent_failure_mode() -> None:
    """Defense against schwabdev silent-failure-mode -- empty access_token
    triggers SystemExit with operator-actionable message."""
    mod = _import_script_module()
    fake_cfg = mock.MagicMock()
    fake_client = mock.MagicMock()
    fake_client.tokens.access_token = None  # silent-failure-mode shape
    with (
        mock.patch.object(mod, "_load_cfg", return_value=fake_cfg),
        mock.patch.object(mod, "_apply_overrides_thin", return_value=fake_cfg),
        mock.patch.object(
            mod, "_resolve_credentials_thin",
            return_value=("cid", "csec"),
        ),
        mock.patch.object(
            mod, "_construct_client_thin", return_value=fake_client,
        ),
        pytest.raises(SystemExit) as exc_info,
    ):
        mod._bootstrap_authenticated_client(
            environment="production",
            config_path=Path("dummy.toml"),
        )
    msg = str(exc_info.value)
    assert "silent-failure-mode" in msg or "access_token" in msg


def test_bootstrap_raises_on_unresolved_credentials() -> None:
    """Missing credentials raise SystemExit (not prompt; allow_prompt=False)."""
    mod = _import_script_module()
    fake_cfg = mock.MagicMock()
    with (
        mock.patch.object(mod, "_load_cfg", return_value=fake_cfg),
        mock.patch.object(mod, "_apply_overrides_thin", return_value=fake_cfg),
        mock.patch.object(
            mod, "_resolve_credentials_thin", return_value=(None, None),
        ),
        pytest.raises(SystemExit) as exc_info,
    ):
        mod._bootstrap_authenticated_client(
            environment="production",
            config_path=Path("dummy.toml"),
        )
    msg = str(exc_info.value)
    assert "credentials" in msg.lower()


# ---------------------------------------------------------------------------
# Test 7 -- end-to-end render_report sentinel-leak audit.
# ---------------------------------------------------------------------------

def test_render_report_redacts_all_sentinels_end_to_end() -> None:
    """End-to-end: planted sentinels in captures + metadata are scrubbed."""
    mod = _import_script_module()
    # Plant sentinels in a representative leg + leg_raw_values_repr.
    leg_with_sentinel = {
        "legId": 1,
        "price": 5.23,
        "quantity": 100.0,
        "mismarkedQuantity": 0.0,
        "instrumentId": 12345,
        "time": "2026-05-15T13:30:00.000Z",
        # Unexpected extra key carrying a sentinel -- surfaces in
        # leg_raw_values_repr because comparator captures all keys.
        "secret_extra": _SENTINEL_ACCESS_TOKEN,
    }
    orders = [{
        "orderId": _SENTINEL_ACCOUNT_HASH,  # planted in order id field too
        "status": "FILLED",
        "orderActivityCollection": [{
            "activityType": "EXECUTION",
            "executionLegs": [leg_with_sentinel],
        }],
    }]
    captures = mod.iterate_orders_with_legs(orders)
    summary = mod.summarize_captures(captures)
    metadata = {
        "generated_utc": "2026-05-17T12:34:56Z",
        "environment": "production",
        "lookback_days": 30,
        "max_orders": 30,
        "from_time": "2026-04-17T12:34:56.000Z",
        "to_time": "2026-05-17T12:34:56.000Z",
    }
    text = mod.render_report(
        captures=captures, summary=summary, metadata=metadata,
        known_secrets=[
            _SENTINEL_CLIENT_ID, _SENTINEL_CLIENT_SECRET,
            _SENTINEL_ACCESS_TOKEN, _SENTINEL_REFRESH_TOKEN,
            _SENTINEL_ACCOUNT_HASH,
        ],
    )
    # All 5 sentinels MUST be absent from the rendered output.
    for sentinel in (
        _SENTINEL_CLIENT_ID, _SENTINEL_CLIENT_SECRET,
        _SENTINEL_ACCESS_TOKEN, _SENTINEL_REFRESH_TOKEN,
        _SENTINEL_ACCOUNT_HASH,
    ):
        assert sentinel not in text, (
            f"Sentinel {sentinel!r} leaked end-to-end through render_report. "
            f"Output excerpt: {text[:500]!r}"
        )


def test_render_report_is_ascii_only() -> None:
    """Output must be ASCII-only (CLAUDE.md Windows cp1252 stdout gotcha)."""
    mod = _import_script_module()
    captures = mod.iterate_orders_with_legs([{
        "orderId": "abc",
        "status": "FILLED",
        "orderActivityCollection": [{
            "activityType": "EXECUTION",
            "executionLegs": [_well_formed_leg()],
        }],
    }])
    summary = mod.summarize_captures(captures)
    text = mod.render_report(
        captures=captures, summary=summary,
        metadata={
            "generated_utc": "2026-05-17T12:34:56Z",
            "environment": "production",
            "lookback_days": 30,
            "max_orders": 30,
            "from_time": "x", "to_time": "y",
        },
        known_secrets=[],
    )
    # ASCII-only assertion.
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        pytest.fail(
            f"render_report emitted non-ASCII byte at position {exc.start}: "
            f"{text[max(0, exc.start - 20):exc.start + 20]!r}"
        )


# ---------------------------------------------------------------------------
# Test 8 -- summarize_captures aggregates correctly.
# ---------------------------------------------------------------------------

def test_summarize_captures_aggregates_frequencies() -> None:
    mod = _import_script_module()
    leg_missing_time = {
        "legId": 1, "price": 5.23, "quantity": 100.0,
        "mismarkedQuantity": 0.0, "instrumentId": 1,
        # `time` missing
    }
    leg_wrong_price_type = {
        "legId": 2, "price": "5.23", "quantity": 100.0,
        "mismarkedQuantity": 0.0, "instrumentId": 1,
        "time": "2026-05-17T12:34:56.000Z",
    }
    leg_good = _well_formed_leg()
    orders = [{
        "orderId": "o1", "status": "FILLED",
        "orderActivityCollection": [{
            "activityType": "EXECUTION",
            "executionLegs": [leg_missing_time, leg_wrong_price_type, leg_good],
        }],
    }]
    captures = mod.iterate_orders_with_legs(orders, max_legs_per_order=10)
    summary = mod.summarize_captures(captures)
    assert summary["total_orders_inspected"] == 1
    assert summary["orders_with_executions"] == 1
    assert summary["total_legs_captured"] == 3
    assert summary["legs_would_pass_type_shape_only"] == 1
    assert summary["missing_key_frequency"].get("time") == 1
    assert summary["wrong_type_frequency"].get("price") == 1


# ---------------------------------------------------------------------------
# Test 9 -- argparse rejects unknown --environment value.
# ---------------------------------------------------------------------------

def test_argparse_rejects_unknown_environment() -> None:
    script = _load_script_path()
    result = subprocess.run(
        [sys.executable, str(script), "--environment", "junk"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr.lower() or "junk" in result.stderr
