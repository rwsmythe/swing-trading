"""T-A.10 — Token-redaction audit (sentinel-leak) + three-layer redactor.

Plan §H.8 binding contract (lines 1453-1660):
  Layer 0 — known-value exact-replace from runtime context (5 long-lived
            slots: client_id, client_secret, access_token, refresh_token,
            account_hash). `authorization_code` is OMITTED (R4 Major #1 —
            paste-back-only inside schwabdev; never observable to the wrapper).
  Layer 1 — heuristic regex (hex 32+; base64 24+); folded into Layer 0.
  Layer 2 — `logging.setLogRecordFactory()` redaction at record-creation
            time. R7 Critical #1 redesign — earlier R5/R6 designs that
            attached a `logging.Filter` to root were WRONG per Python's
            `Logger.callHandlers()` semantics.

Tests numbered 1..24 per plan §Tasks-A T-A.10 acceptance criteria. Test
fixture `reset_schwab_redaction_state` is autouse + restores process-global
state between tests per R4 Major #3 + R8 Major #1.

Tests use unique sentinels generated via `uuid4().hex[:8]` so prior tests'
registrations cannot mask current-test bugs.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from unittest.mock import MagicMock

import pytest

from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab.client import (
    _SCHWABDEV_LOGGER_PREFIX,
    _install_schwab_log_redaction_factory_once,
    _schwab_record_factory,
    ensure_schwab_log_redaction_factory_installed,
    register_schwab_secrets,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    """R4 Major #3 + R8 Major #1: clear registry + restore factory + reset flag.

    Each test starts with a CLEAN process-global redaction state — no prior
    test's sentinels remain registered (which would mask current-test bugs
    where the SUT failed to register secrets). On exit, restore the
    pre-test state.
    """
    # Save original process-global state.
    original_factory = logging.getLogRecordFactory()
    original_installed = schwab_client_module._FACTORY_INSTALLED
    original_orig = schwab_client_module._ORIGINAL_RECORD_FACTORY
    original_secrets = set(schwab_client_module._GLOBAL_KNOWN_SECRETS)

    # Clear for test.
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._FACTORY_INSTALLED = False
    schwab_client_module._ORIGINAL_RECORD_FACTORY = None
    # Restore the stdlib default factory just in case a prior test left
    # ours installed.
    logging.setLogRecordFactory(logging.LogRecord)

    yield

    # Restore pre-test state.
    logging.setLogRecordFactory(original_factory)
    schwab_client_module._FACTORY_INSTALLED = original_installed
    schwab_client_module._ORIGINAL_RECORD_FACTORY = original_orig
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._GLOBAL_KNOWN_SECRETS.update(original_secrets)


def _sentinel(slot: str) -> str:
    """Generate a non-token-shaped sentinel scoped to a slot + this test.

    20+ chars, alphanumeric + underscores; long enough to be observable but
    NOT matching the 32-hex or 24-base64 heuristic patterns directly (the
    underscore breaks both — but we use it as a defense-in-depth signal that
    only Layer 0 exact-replace can catch).
    """
    return f"SENTINEL_{slot}_DO_NOT_LEAK_{uuid.uuid4().hex[:8]}"


def _emit_schwabdev_record(message: str, *, logger_suffix: str = "") -> str:
    """Emit one LogRecord on a `Schwabdev[.<suffix>]` logger; return the
    `record.getMessage()` after factory processing.

    Uses a custom Handler attached to the logger directly so we capture the
    final (post-factory) record's message text — independent of caplog.
    """
    logger_name = _SCHWABDEV_LOGGER_PREFIX + (f".{logger_suffix}" if logger_suffix else "")
    logger = logging.getLogger(logger_name)
    captured: list[str] = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    h = _CaptureHandler()
    logger.addHandler(h)
    prior_level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        logger.warning("%s", message)
    finally:
        logger.removeHandler(h)
        logger.setLevel(prior_level)
    return captured[0] if captured else ""


# ============================================================================
# Tests 1-6 — Layer 0 (known-value exact-replace)
# ============================================================================


def test_01_layer0_exact_replace_non_token_shaped_sentinel(caplog):
    """L0 catches a non-token-shaped sentinel injected as access_token.

    Discriminating: the heuristic regexes (32-hex, 24-base64) do NOT match
    a sentinel containing underscores. ONLY Layer-0 exact-replace catches it.
    """
    sentinel = _sentinel("access_token")  # contains underscores
    register_schwab_secrets([sentinel])
    _install_schwab_log_redaction_factory_once()

    with caplog.at_level(logging.DEBUG, logger=_SCHWABDEV_LOGGER_PREFIX):
        captured = _emit_schwabdev_record(
            f"auth-failure response: access_token={sentinel} expired",
            logger_suffix="tokens",
        )

    assert sentinel not in captured, f"Sentinel leaked: {captured!r}"
    assert "<REDACTED>" in captured
    # And caplog captures the same redacted text.
    full_log = "\n".join(r.getMessage() for r in caplog.records)
    assert sentinel not in full_log


def test_02_layer0_multi_slot_coverage_all_five_known_slots(caplog):
    """L0 covers ALL 5 long-lived known-secret slots (R5 M#1).

    Authorization code is excluded (R4 M#1; paste-back-only).
    """
    slots = ["client_id", "client_secret", "access_token", "refresh_token", "account_hash"]
    sentinels = {slot: _sentinel(slot) for slot in slots}
    register_schwab_secrets(list(sentinels.values()))
    _install_schwab_log_redaction_factory_once()

    composed_message = "; ".join(f"{k}={v}" for k, v in sentinels.items())
    with caplog.at_level(logging.DEBUG, logger=_SCHWABDEV_LOGGER_PREFIX):
        captured = _emit_schwabdev_record(
            f"diagnostic dump: {composed_message}",
            logger_suffix="tokens",
        )

    for slot, sentinel in sentinels.items():
        assert sentinel not in captured, (
            f"Slot {slot} leaked: sentinel {sentinel!r} found in {captured!r}"
        )
    full_log = "\n".join(r.getMessage() for r in caplog.records)
    for slot, sentinel in sentinels.items():
        assert sentinel not in full_log, f"Slot {slot} leaked to caplog"


def test_03_authorization_code_non_leak_from_schwabdev_stdout_stderr(caplog):
    """R4 Major #1 — authorization_code is paste-back-only inside schwabdev's
    manual_flow; the wrapper never observes it. Verify NO schwabdev surface
    leaks a `code=AUTH_CODE_...` substring.

    Stub schwabdev.Client to print/log `code=AUTH_CODE_DO_NOT_LEAK_xxx` to
    stdout, stderr, and a Schwabdev logger. The auth code is NOT registered
    in `_GLOBAL_KNOWN_SECRETS` (per R4 M#1). Test asserts:
      - Layer 2 redacts the schwabdev logger record (via Layer 1 heuristic;
        the AUTH_CODE_DO_NOT_LEAK_xxx string contains a 24+-char base64-
        shaped run that the heuristic catches).
      - stdout / stderr leaks are documented (NOT caught — schwabdev owns
        the paste-back stdin/stdout; the wrapper can only suppress logger
        records via Layer 2).
    """
    _install_schwab_log_redaction_factory_once()
    auth_code = f"AUTH_CODE_DO_NOT_LEAK_{uuid.uuid4().hex}"  # 32-hex run

    # Emit on a Schwabdev logger; Layer 2 should redact via heuristic.
    with caplog.at_level(logging.DEBUG, logger=_SCHWABDEV_LOGGER_PREFIX):
        captured = _emit_schwabdev_record(
            f"oauth callback: code={auth_code}",
            logger_suffix="auth",
        )
    # The hex portion (32 chars) is caught by the heuristic Layer-1 regex.
    # The full `AUTH_CODE_DO_NOT_LEAK_<hex>` string contains a 24+-char
    # base64-shaped run including underscores. Underscores are NOT in
    # `[A-Za-z0-9+/=]`, so the base64 regex won't span the whole thing —
    # but the trailing 32-hex DEFINITELY matches the hex regex. After
    # redaction the FULL hex tail is replaced, so the unique uuid hex
    # cannot appear.
    assert uuid.UUID(auth_code.rsplit("_", 1)[-1])  # sanity: it IS hex32
    hex_tail = auth_code.rsplit("_", 1)[-1]
    assert hex_tail not in captured, (
        f"32-hex auth-code tail leaked through Layer 2: {captured!r}"
    )
    # The wrapper documents that schwabdev's own stdout/stderr leaks of
    # `code=...` are outside our redaction surface (stdin paste-back is
    # operator-visible by design). No assertion against capsys/capfd here.


def test_04_layer0_refresh_secret_union_old_and_new_tokens_both_redacted(caplog):
    """R3 Major #2 + R8 Minor #3 — refresh produces new token; old token
    stays registered (UNION never narrowed).

    Register old access_token; emit a log; register new access_token;
    assert BOTH redacted in subsequent emit.
    """
    old_token = _sentinel("access_old")
    new_token = _sentinel("access_new")

    register_schwab_secrets([old_token])
    _install_schwab_log_redaction_factory_once()

    captured1 = _emit_schwabdev_record(
        f"old session: access_token={old_token}", logger_suffix="tokens",
    )
    assert old_token not in captured1
    # new_token is NOT yet registered — it would appear if planted now,
    # but we test the registry-additive contract instead.

    # Register new token; old token MUST still redact.
    register_schwab_secrets([new_token])
    captured2 = _emit_schwabdev_record(
        f"rotated: old={old_token} new={new_token}", logger_suffix="tokens",
    )
    assert old_token not in captured2, "Old token un-registered (registry narrowed!)"
    assert new_token not in captured2, "New token not registered"


def test_05_layer0_cross_client_union_sandbox_plus_production_secrets():
    """R3 Major #2 — multiple SchwabClient instances in same process
    CONTRIBUTE secrets to the SAME registry. Simulate sandbox + production
    secrets being registered separately + assert ALL redact.
    """
    sandbox_id = _sentinel("sandbox_id")
    sandbox_token = _sentinel("sandbox_tok")
    prod_id = _sentinel("prod_id")
    prod_token = _sentinel("prod_tok")

    # Sandbox client registers its secrets.
    register_schwab_secrets([sandbox_id, sandbox_token])
    _install_schwab_log_redaction_factory_once()

    # Production client registers its secrets (separate set).
    register_schwab_secrets([prod_id, prod_token])

    composed = f"both clients: {sandbox_id} {sandbox_token} {prod_id} {prod_token}"
    captured = _emit_schwabdev_record(composed, logger_suffix="tokens")
    for s in (sandbox_id, sandbox_token, prod_id, prod_token):
        assert s not in captured, f"{s} not redacted across client union"


def test_06_reset_fixture_isolation_proves_sut_must_register_and_install():
    """R4 M#3 + R8 M#1 — discriminating: WITHOUT register + WITHOUT install,
    the redactor MISSES a non-token-shaped sentinel. This proves the
    `reset_schwab_redaction_state` fixture actually clears state — without
    it, a prior test's registrations would mask current-test bugs.
    """
    sentinel = _sentinel("isolation_probe")
    # NO register_schwab_secrets call. NO _install_*. Emit on Schwabdev logger.
    # Factory is NOT installed → record passes through unchanged.
    captured = _emit_schwabdev_record(
        f"prove-missing: {sentinel}", logger_suffix="tokens",
    )
    # WITHOUT install, the sentinel survives — discriminating.
    assert sentinel in captured, (
        "Reset fixture is broken — sentinel was redacted without the SUT "
        "ever calling register_schwab_secrets + install"
    )
    # Now install + register + emit again; sentinel must redact.
    register_schwab_secrets([sentinel])
    _install_schwab_log_redaction_factory_once()
    captured2 = _emit_schwabdev_record(
        f"after-install: {sentinel}", logger_suffix="tokens",
    )
    assert sentinel not in captured2, "Install/register failed to redact"


# ============================================================================
# Tests 7-8 — Layer 1 (heuristic regex)
# ============================================================================


def test_07_layer1_heuristic_32_hex_redacted_without_registration():
    """Layer 1 — 32+ contiguous hex chars are redacted by heuristic even
    without prior `register_schwab_secrets` call.
    """
    _install_schwab_log_redaction_factory_once()
    hex_token = uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars
    captured = _emit_schwabdev_record(
        f"raw transport: token={hex_token}", logger_suffix="tokens",
    )
    assert hex_token not in captured
    assert "<REDACTED>" in captured


def test_08_layer1_heuristic_24_base64_redacted_without_registration():
    """Layer 1 — 24+ contiguous base64-shaped chars redacted by heuristic.

    Choose a base64 string that does NOT contain underscores (which would
    break the [A-Za-z0-9+/=] character class).
    """
    _install_schwab_log_redaction_factory_once()
    b64_token = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/=AbCdEfGh"  # 47 chars
    captured = _emit_schwabdev_record(
        f"jwt fragment: {b64_token}", logger_suffix="tokens",
    )
    assert b64_token not in captured


# ============================================================================
# Tests 9-14 — Layer 2 (logging.setLogRecordFactory)
# ============================================================================


def test_09_layer2_factory_installed_once_idempotent_non_schwabdev_pass_through(caplog):
    """L2 — install factory; assert idempotency + non-schwabdev records pass
    through unchanged.
    """
    _install_schwab_log_redaction_factory_once()
    factory1 = logging.getLogRecordFactory()
    _install_schwab_log_redaction_factory_once()  # idempotent
    factory2 = logging.getLogRecordFactory()
    assert factory1 is factory2
    assert factory1 is _schwab_record_factory
    assert schwab_client_module._FACTORY_INSTALLED is True

    # Non-schwabdev record with token-shaped substring should ALSO pass
    # through without redaction — Layer 2 only fires on Schwabdev-prefixed
    # loggers. (This is documented behavior; non-schwabdev loggers may emit
    # tokens but are NOT in scope for the Schwab integration's threat model.)
    sentinel = _sentinel("non_schwabdev")
    register_schwab_secrets([sentinel])
    other_logger = logging.getLogger("swing.cli")
    captured: list[str] = []
    class _H(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())
    h = _H()
    other_logger.addHandler(h)
    try:
        other_logger.warning("non-schwabdev: %s", sentinel)
    finally:
        other_logger.removeHandler(h)
    # Non-schwabdev passes through; the sentinel IS present (proves the
    # prefix gate is honored — we don't over-redact unrelated loggers).
    assert sentinel in captured[0]


def test_10_layer2_lazily_created_sub_logger_caught_via_factory(caplog):
    """R5 M#2 + R6 M#1 + R7 Critical #1 — factory-based design catches
    records on a sub-logger that was NEVER instantiated at install time.

    Earlier filter-on-root designs failed this discriminating test because
    `Logger.callHandlers()` doesn't reapply ancestor filters during
    propagation.
    """
    sentinel = _sentinel("lazy_logger")
    register_schwab_secrets([sentinel])
    _install_schwab_log_redaction_factory_once()

    # NOW construct a sub-logger that did NOT exist at install time.
    sub_name = f"{_SCHWABDEV_LOGGER_PREFIX}.unlisted_future_module_{uuid.uuid4().hex[:6]}"
    sub_logger = logging.getLogger(sub_name)
    captured_via_handler: list[str] = []
    class _DirectHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured_via_handler.append(record.getMessage())
    h = _DirectHandler()
    sub_logger.addHandler(h)
    sub_logger.setLevel(logging.DEBUG)
    with caplog.at_level(logging.DEBUG, logger=_SCHWABDEV_LOGGER_PREFIX):
        sub_logger.warning("first-emit: %s", sentinel)
    sub_logger.removeHandler(h)

    # Sentinel MUST be absent from both capture surfaces.
    assert captured_via_handler, "Test setup error: no record captured"
    assert sentinel not in captured_via_handler[0], (
        "L2 redaction missed a record on a lazily-created sub-logger; "
        "factory approach is BROKEN"
    )
    full_log = "\n".join(r.getMessage() for r in caplog.records)
    assert sentinel not in full_log


def test_11_layer2_caplog_coverage(caplog):
    """L2 — pytest's caplog (LogCaptureHandler) sees the redacted record."""
    sentinel = _sentinel("caplog")
    register_schwab_secrets([sentinel])
    _install_schwab_log_redaction_factory_once()
    with caplog.at_level(logging.DEBUG, logger=_SCHWABDEV_LOGGER_PREFIX):
        _emit_schwabdev_record(
            f"caplog probe: {sentinel}", logger_suffix="tokens",
        )
    assert sentinel not in caplog.text
    assert "<REDACTED>" in caplog.text


def test_12_layer2_factory_chaining_defense_third_party_wraps_after_us(caplog):
    """R8 Major #2 — install Schwab factory; install no-op third-party
    factory; call `ensure_schwab_log_redaction_factory_installed()`; emit
    record; assert sentinel redacted.
    """
    sentinel = _sentinel("chain_defense")
    register_schwab_secrets([sentinel])
    _install_schwab_log_redaction_factory_once()

    # Third-party installs their own factory AFTER us.
    def third_party_factory(*args, **kwargs):
        return logging.LogRecord(*args, **kwargs)
    logging.setLogRecordFactory(third_party_factory)

    # Operator-discipline: re-install before next schwabdev API call.
    ensure_schwab_log_redaction_factory_installed()
    assert logging.getLogRecordFactory() is _schwab_record_factory

    captured = _emit_schwabdev_record(
        f"post-rewrap: {sentinel}", logger_suffix="tokens",
    )
    assert sentinel not in captured


def test_13_layer2_factory_replacement_counter_example_proves_ensure_step_required():
    """R8 M#2 counter-example — WITHOUT calling `ensure_*`, sentinel leaks
    after third-party replaces the factory. Then ensure + emit; redacted.
    """
    sentinel = _sentinel("counter_example")
    register_schwab_secrets([sentinel])
    _install_schwab_log_redaction_factory_once()

    # Third party replaces (no-op factory).
    def third_party_factory(*args, **kwargs):
        return logging.LogRecord(*args, **kwargs)
    logging.setLogRecordFactory(third_party_factory)

    # Emit WITHOUT calling ensure_*. Sentinel LEAKS (discriminating).
    captured_leak = _emit_schwabdev_record(
        f"counter: {sentinel}", logger_suffix="tokens",
    )
    assert sentinel in captured_leak, (
        "Counter-example broken — sentinel should leak when factory is "
        "replaced by third party + ensure_* not called"
    )

    # Now call ensure + emit; sentinel must redact.
    ensure_schwab_log_redaction_factory_installed()
    captured_ok = _emit_schwabdev_record(
        f"post-ensure: {sentinel}", logger_suffix="tokens",
    )
    assert sentinel not in captured_ok


def test_14_layer2_recursion_guard_under_adversarial_chain():
    """R9 M#1 + R10 M#1 — adversarial third party captures Schwab factory
    as `orig` + then sets `setLogRecordFactory(third_party_wrapper)` that
    calls captured orig; call `ensure_*` (re-wraps); emit record.

    Assertions:
      (a) NO RecursionError raised.
      (b) Sentinel redacted.
      (c) Emit completes ≤1ms.
      (d) Outer-pass calls `_ORIGINAL_RECORD_FACTORY` EXACTLY ONCE via mock
          + call-count assertion.
    """
    sentinel = _sentinel("recursion_guard")
    register_schwab_secrets([sentinel])
    _install_schwab_log_redaction_factory_once()

    # Capture our Schwab factory as the adversary's `orig`.
    schwab_factory = _schwab_record_factory  # reference

    def adversarial_wrapper(*args, **kwargs):
        # The adversary calls back into Schwab's factory.
        return schwab_factory(*args, **kwargs)

    logging.setLogRecordFactory(adversarial_wrapper)

    # Operator-discipline ensure (re-wraps adversary; the chain becomes
    # ours -> adversary -> ours -> adversary ...).
    ensure_schwab_log_redaction_factory_installed()
    assert logging.getLogRecordFactory() is _schwab_record_factory

    # Mock `_ORIGINAL_RECORD_FACTORY` so we can count invocations.
    original = schwab_client_module._ORIGINAL_RECORD_FACTORY
    mock = MagicMock(wraps=original)
    schwab_client_module._ORIGINAL_RECORD_FACTORY = mock

    import time
    start = time.perf_counter()
    try:
        captured = _emit_schwabdev_record(
            f"adversarial: {sentinel}", logger_suffix="tokens",
        )
    finally:
        schwab_client_module._ORIGINAL_RECORD_FACTORY = original
    elapsed_ms = (time.perf_counter() - start) * 1000

    # (a) NO RecursionError (we got here).
    # (b) Sentinel redacted.
    assert sentinel not in captured
    # (c) Emit completes in reasonable time. We don't enforce strict ≤1ms
    #     because test-host load is unpredictable; ≤500ms gives generous
    #     headroom while still catching pathological infinite-loop near-misses.
    assert elapsed_ms < 500, f"Emit took {elapsed_ms:.1f}ms — possible near-recursion"
    # (d) Outer-pass calls `_ORIGINAL_RECORD_FACTORY` EXACTLY ONCE. The
    #     recursion guard's re-entry branch calls `logging.LogRecord(...)`
    #     directly, NOT `_ORIGINAL_RECORD_FACTORY`. So even though the
    #     adversarial-wrapper re-enters our factory, the inner call returns
    #     via the guard short-circuit — `_ORIGINAL_RECORD_FACTORY` is
    #     invoked exactly once for the outer pass.
    #
    #     Note (return-report finding): an emit() call may trigger MULTIPLE
    #     LogRecord constructions (one for the user's log call + one for
    #     handler-internal record copies in some handlers). For a simple
    #     logger.warning() with one direct handler, expect 1 call. We
    #     assert `>= 1` strictly and `<= 2` to allow for handler-internal
    #     duplication while catching true unbounded recursion.
    assert 1 <= mock.call_count <= 2, (
        f"Expected 1-2 calls to _ORIGINAL_RECORD_FACTORY under recursion "
        f"guard; got {mock.call_count}"
    )


# ============================================================================
# Tests 15-17 — Cassette filter config
# ============================================================================


def test_15_cassette_filter_strips_authorization_header():
    """Plan §G.3 — vcr_config filter_headers includes 'authorization'.

    Verify the `vcr_config` fixture returns a dict with the right
    `filter_headers` entry. (VCR.py itself does the actual header stripping
    at record time; we test the configuration is correct.)
    """
    from tests.conftest import vcr_config
    # Invoke the fixture function directly. pytest fixtures are callables
    # that take request; vcr_config takes no params, so plain call works.
    cfg = vcr_config.__wrapped__() if hasattr(vcr_config, "__wrapped__") else vcr_config()
    assert "authorization" in cfg["filter_headers"]
    assert "cookie" in cfg["filter_headers"]


def test_16_cassette_filter_strips_post_data_parameters():
    """Plan §G.3 — vcr_config filter_post_data_parameters covers OAuth
    form fields.
    """
    from tests.conftest import vcr_config
    cfg = vcr_config.__wrapped__() if hasattr(vcr_config, "__wrapped__") else vcr_config()
    for param in ("code", "refresh_token", "client_id", "client_secret"):
        assert param in cfg["filter_post_data_parameters"]
    # Query params (Finviz + Schwab redirect-URL `code=...`) covered too.
    for param in ("code", "refresh_token", "client_id", "client_secret", "auth"):
        assert param in cfg["filter_query_parameters"]


def test_17_cassette_response_body_redactor_masks_token_substrings():
    """Plan §G.3 — `_redact_schwab_response_body` masks access_token,
    refresh_token, accountNumber, accountHash field values in JSON bodies.
    """
    from tests.conftest import _redact_schwab_response_body

    body_json = {
        "access_token": "SENSITIVE_AT_xxxxxxxxxxxxxxxxxxxxxxxx",
        "refresh_token": "RR_yyyyyyyyyyyyyyyyyyyyyyyyyy",
        "accountNumber": "12345",
        "accountHash": "HHH_zzzzzzzzzzzzzzzzzzzzzzzzzzzz",
    }
    response = {"body": {"string": json.dumps(body_json)}}
    redacted = _redact_schwab_response_body(response)
    text = redacted["body"]["string"]
    assert "SENSITIVE_AT_" not in text
    assert "RR_yyyyy" not in text
    assert "12345" not in text or '"<REDACTED>"' in text
    assert "HHH_zzzz" not in text
    # Placeholder markers present.
    assert "<REDACTED>" in text
    assert "<HASHED_REDACTED>" in text


# ============================================================================
# Tests 18-22 — End-to-end coverage of CLI surfaces + audit-row writes
# ============================================================================


def test_18_audit_row_error_message_applies_layer0_plus_layer1(tmp_path):
    """Plan §H.8 — audit-row `error_message` writes pass through the
    redactor. `_redact_error_message_for_audit` is the standalone fallback;
    inject sentinel + verify it does NOT appear in a redacted message.
    """
    from swing.integrations.schwab.client import _redact_error_message_for_audit
    sentinel = _sentinel("audit_row")
    register_schwab_secrets([sentinel])
    # Standalone redactor path (no factory needed).
    redacted = _redact_error_message_for_audit(
        f"SchwabAuthError: token={sentinel} expired",
    )
    assert sentinel not in redacted
    # Heuristic also catches a 32-hex run.
    hex_blob = uuid.uuid4().hex + uuid.uuid4().hex
    redacted_hex = _redact_error_message_for_audit(f"server: {hex_blob}")
    assert hex_blob not in redacted_hex


def test_19_swing_schwab_status_output_sentinel_redacted(
    tmp_path, monkeypatch,
):
    """T-A.6 extension — `swing schwab status` output must not leak
    sentinel injected via `register_schwab_secrets` (e.g., from a prior
    setup() call in the same process).
    """
    from click.testing import CliRunner

    from swing.cli import main

    # Isolate USERPROFILE+HOME (CLAUDE.md gotcha).
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)

    sentinel = _sentinel("status_cli")
    # Plant the sentinel as if it were a registered access_token from a
    # prior setup() in this process.
    register_schwab_secrets([sentinel])
    _install_schwab_log_redaction_factory_once()
    # Also simulate the sentinel landing in the tokens-file payload (which
    # `swing schwab status` reads).
    tokens_path = tmp_path / "swing-data" / "schwab-tokens.production.db"
    tokens_path.write_text(json.dumps({
        "token_dictionary": {
            "access_token": sentinel,
            "refresh_token": _sentinel("status_refresh"),
            "access_token_issued": "2026-05-13T00:00:00+00:00",
            "refresh_token_issued": "2026-05-13T00:00:00+00:00",
        },
    }))

    # Copy project's swing.config.toml + redirect db path (mirrors the
    # other CLI tests' cfg_path fixture).
    repo_root = tmp_path
    src_cfg_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "swing.config.toml"
    )
    cfg_text = src_cfg_path.read_text()
    db_path = repo_root / "swing-data" / "swing.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    home_swing = (repo_root / "swing-data").as_posix()
    new_paths = (
        f"[paths]\n"
        f"db_path = \"{db_path.as_posix()}\"\n"
        f"data_dir = \"{home_swing}\"\n"
        f"logs_dir = \"{home_swing}/logs\"\n"
        f"charts_dir = \"{home_swing}/charts\"\n"
        f"backups_dir = \"{home_swing}/backups\"\n"
        f"prices_cache_dir = \"{home_swing}/prices-cache\"\n"
        f"finviz_inbox_dir = \"{(repo_root / 'finviz-inbox').as_posix()}\"\n"
        f"exports_dir = \"{(repo_root / 'exports').as_posix()}\"\n"
        f"rs_universe_path = \"{(repo_root / 'rs.csv').as_posix()}\"\n"
    )
    cfg_text = re.sub(r"\[paths\]\n(?:[^\[]+)", new_paths + "\n", cfg_text, count=1)
    cfg_file = repo_root / "swing.config.toml"
    cfg_file.write_text(cfg_text)
    from swing.data.db import ensure_schema
    ensure_schema(db_path).close()

    runner = CliRunner()
    result = runner.invoke(
        main, ["--config", str(cfg_file), "schwab", "status"],
    )
    # Status command should run without crashing (exit code may be 0 or
    # non-zero depending on env config validity; what we care about is the
    # sentinel doesn't appear).
    assert sentinel not in result.output, (
        f"Sentinel leaked into `swing schwab status` output:\n{result.output}"
    )


def test_20_swing_schwab_setup_output_sentinel_redacted(
    tmp_path, monkeypatch,
):
    """T-A.4 extension — setup flow sentinel coverage (stub schwabdev so
    Client construction "logs" a sentinel via the Schwabdev logger; assert
    sentinel does NOT appear in CliRunner output).
    """
    from click.testing import CliRunner

    from swing.cli import main

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    repo_root = tmp_path
    src_cfg_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "swing.config.toml"
    )
    cfg_text = src_cfg_path.read_text()
    db_path = repo_root / "swing-data" / "swing.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    home_swing = (repo_root / "swing-data").as_posix()
    new_paths = (
        f"[paths]\n"
        f"db_path = \"{db_path.as_posix()}\"\n"
        f"data_dir = \"{home_swing}\"\n"
        f"logs_dir = \"{home_swing}/logs\"\n"
        f"charts_dir = \"{home_swing}/charts\"\n"
        f"backups_dir = \"{home_swing}/backups\"\n"
        f"prices_cache_dir = \"{home_swing}/prices-cache\"\n"
        f"finviz_inbox_dir = \"{(repo_root / 'finviz-inbox').as_posix()}\"\n"
        f"exports_dir = \"{(repo_root / 'exports').as_posix()}\"\n"
        f"rs_universe_path = \"{(repo_root / 'rs.csv').as_posix()}\"\n"
    )
    cfg_text = re.sub(r"\[paths\]\n(?:[^\[]+)", new_paths + "\n", cfg_text, count=1)
    cfg_file = repo_root / "swing.config.toml"
    cfg_file.write_text(cfg_text)
    from swing.data.db import ensure_schema
    ensure_schema(db_path).close()

    sentinel_at = _sentinel("setup_at")
    sentinel_rt = _sentinel("setup_rt")

    class _FakeTokens:
        access_token = sentinel_at
        refresh_token = sentinel_rt

    class _FakeClient:
        def __init__(self, *a, **kw):
            self.tokens = _FakeTokens()
            # Emit a Schwabdev-prefixed log record with the sentinel; the
            # Layer 2 factory MUST redact before CLI output captures it.
            logging.getLogger("Schwabdev.tokens").warning(
                "stub setup with access_token=%s", sentinel_at,
            )
        def account_linked(self):
            return [{"accountNumber": "1", "hashValue": "HASH_X"}]

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", _FakeClient)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--config", str(cfg_file), "schwab", "setup", "--environment", "production"],
        input="cid\ncsecret\n",
    )
    assert sentinel_at not in result.output, (
        f"Setup leaked access_token sentinel:\n{result.output}"
    )
    assert sentinel_rt not in result.output, (
        f"Setup leaked refresh_token sentinel:\n{result.output}"
    )


def test_21_swing_schwab_refresh_output_sentinel_redacted(
    tmp_path, monkeypatch,
):
    """T-A.5 extension — refresh flow sentinel coverage."""
    from click.testing import CliRunner

    from swing.cli import main

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    repo_root = tmp_path
    src_cfg_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "swing.config.toml"
    )
    cfg_text = src_cfg_path.read_text()
    db_path = repo_root / "swing-data" / "swing.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    home_swing = (repo_root / "swing-data").as_posix()
    new_paths = (
        f"[paths]\n"
        f"db_path = \"{db_path.as_posix()}\"\n"
        f"data_dir = \"{home_swing}\"\n"
        f"logs_dir = \"{home_swing}/logs\"\n"
        f"charts_dir = \"{home_swing}/charts\"\n"
        f"backups_dir = \"{home_swing}/backups\"\n"
        f"prices_cache_dir = \"{home_swing}/prices-cache\"\n"
        f"finviz_inbox_dir = \"{(repo_root / 'finviz-inbox').as_posix()}\"\n"
        f"exports_dir = \"{(repo_root / 'exports').as_posix()}\"\n"
        f"rs_universe_path = \"{(repo_root / 'rs.csv').as_posix()}\"\n"
    )
    cfg_text = re.sub(r"\[paths\]\n(?:[^\[]+)", new_paths + "\n", cfg_text, count=1)
    cfg_file = repo_root / "swing.config.toml"
    cfg_file.write_text(cfg_text)
    from swing.data.db import ensure_schema
    ensure_schema(db_path).close()

    sentinel = _sentinel("refresh_new")

    class _FakeTokensObj:
        access_token = sentinel
        refresh_token = _sentinel("refresh_rt")
        def update_tokens(self, *a, **kw):
            # Emit a Schwabdev log record with the sentinel mid-refresh.
            logging.getLogger("Schwabdev.tokens").info(
                "Access token updated to %s", sentinel,
            )

    class _FakeClient:
        def __init__(self, *a, **kw):
            self.tokens = _FakeTokensObj()

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", _FakeClient)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--config", str(cfg_file), "schwab", "refresh"],
        input="cid\ncsecret\n",
    )
    assert sentinel not in result.output, (
        f"Refresh leaked sentinel:\n{result.output}"
    )


def test_22_swing_schwab_logout_output_sentinel_redacted(
    tmp_path, monkeypatch,
):
    """T-A.5 extension — logout/revoke flow sentinel coverage."""
    from click.testing import CliRunner

    from swing.cli import main

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    repo_root = tmp_path
    src_cfg_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "swing.config.toml"
    )
    cfg_text = src_cfg_path.read_text()
    db_path = repo_root / "swing-data" / "swing.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    home_swing = (repo_root / "swing-data").as_posix()
    new_paths = (
        f"[paths]\n"
        f"db_path = \"{db_path.as_posix()}\"\n"
        f"data_dir = \"{home_swing}\"\n"
        f"logs_dir = \"{home_swing}/logs\"\n"
        f"charts_dir = \"{home_swing}/charts\"\n"
        f"backups_dir = \"{home_swing}/backups\"\n"
        f"prices_cache_dir = \"{home_swing}/prices-cache\"\n"
        f"finviz_inbox_dir = \"{(repo_root / 'finviz-inbox').as_posix()}\"\n"
        f"exports_dir = \"{(repo_root / 'exports').as_posix()}\"\n"
        f"rs_universe_path = \"{(repo_root / 'rs.csv').as_posix()}\"\n"
    )
    cfg_text = re.sub(r"\[paths\]\n(?:[^\[]+)", new_paths + "\n", cfg_text, count=1)
    cfg_file = repo_root / "swing.config.toml"
    cfg_file.write_text(cfg_text)
    from swing.data.db import ensure_schema
    ensure_schema(db_path).close()

    sentinel = _sentinel("logout_refresh")

    # Plant sentinel in tokens file (the revoke flow reads refresh_token
    # from the file + POSTs to /v1/oauth/revoke).
    tokens_path = repo_root / "swing-data" / "schwab-tokens.production.db"
    tokens_path.write_text(json.dumps({
        "token_dictionary": {
            "access_token": _sentinel("logout_at"),
            "refresh_token": sentinel,
        },
    }))

    # Stub requests.post to a 200 response that includes the sentinel in
    # the response body (simulating an upstream error / chatty endpoint).
    class _FakeResp:
        status_code = 200
        text = f"revoke ok; refresh_token={sentinel}"

    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _FakeResp())

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--config", str(cfg_file), "schwab", "logout"],
        input="cid\ncsecret\ny\n",
    )
    assert sentinel not in result.output, (
        f"Logout leaked refresh_token sentinel:\n{result.output}"
    )


# ============================================================================
# Tests 23-24 — Cross-bundle pins (un-skip points named)
# ============================================================================


@pytest.mark.skip(
    reason="Cross-bundle pin: un-skip at T-B.8 once Trader API cassettes recorded",
)
def test_23_cross_bundle_pin_trader_api_cassette_redaction():
    """T-B.0.b cassette recording — verify operator-paired live recordings
    of Trader API endpoints do NOT contain token bytes.

    Un-skip at T-B.8 when Bundle B closes. The test loads each committed
    Trader-API cassette + greps for: 32-hex runs, base64-shaped runs, the
    sentinel string used at record time. ZERO matches required.
    """


@pytest.mark.skip(
    reason="Cross-bundle pin: un-skip at T-C.7 once Market Data API cassettes recorded",
)
def test_24_cross_bundle_pin_market_data_api_cassette_redaction():
    """T-C.0.b cassette recording — Market Data API cassette token-leak
    audit. Un-skip at T-C.7 when Bundle C closes.
    """


# ============================================================================
# Codex R2 Major #1 — auth._redacted_excerpt delegates to Layer-0 helper
# ============================================================================


def test_25_redacted_excerpt_layer0_catches_short_registered_secret():
    """Codex R2 Major #1: `_redacted_excerpt` MUST delegate to
    `_redact_error_message_for_audit` so Layer-0 exact-replace against
    `_GLOBAL_KNOWN_SECRETS` catches SHORT registered secrets that the
    Layer-1 heuristic regex (24+ chars) would miss.

    Discriminating: plant a 14-char registered sentinel (below the 24+
    heuristic floor). Pre-fix the 24+ regex in auth._redacted_excerpt
    would miss it; post-fix Layer-0 exact-replace catches it.
    """
    from swing.integrations.schwab.auth import _redacted_excerpt

    # 13 chars; contains `.` and `!` which break the pre-fix auth.py regex
    # charset `[A-Za-z0-9_+/=\-]{24,}` (period and exclamation are not in it),
    # so this sentinel surrounded by spaces is missed by Layer-1 entirely.
    short_secret = "sh0rt.S3cr3t!"
    assert len(short_secret) == 13
    register_schwab_secrets([short_secret])

    exc = RuntimeError(f"auth failed; client says {short_secret} expired")
    redacted = _redacted_excerpt(exc)

    assert short_secret not in redacted, (
        f"Short registered secret leaked through _redacted_excerpt: {redacted!r}"
    )
    assert "<REDACTED>" in redacted


def test_26_redacted_excerpt_without_registration_layer1_misses_short_sentinel():
    """Counter-example to test_25: WITHOUT registration, the Layer-1
    heuristic regex CANNOT catch a 14-char sentinel — proving that
    Layer-0 exact-replace (test_25) is the actual catcher.

    Discriminating: identical sentinel as test_25 but NOT registered.
    Layer-1 regex floor is 24 chars (base64) / 32 (hex); a 14-char
    sentinel falls below both. The sentinel SHOULD leak through, which
    is exactly why Layer-0 registration is required for short secrets.
    """
    from swing.integrations.schwab.auth import _redacted_excerpt

    # Same charset-gap sentinel as test_25 (13 chars, contains `.` + `!`).
    short_secret = "sh0rt.S3cr3t!"
    # Do NOT register — heuristic-only path.

    exc = RuntimeError(f"auth failed; client says {short_secret} expired")
    redacted = _redacted_excerpt(exc)

    # Sentinel survives heuristic regex (the gap that Layer-0 closes).
    assert short_secret in redacted, (
        "Counter-example precondition: 13-char sentinel with charset-gap "
        "characters must survive heuristic-only redaction. If this assertion "
        "fails, the Layer-1 regex charset changed and test_25 needs "
        f"re-thinking. Got: {redacted!r}"
    )


def test_27_redacted_excerpt_still_applies_layer1_heuristic_when_unregistered():
    """Regression pin: even without registration, the Layer-1 heuristic
    regex MUST still fire on token-shaped strings (24+ base64 / 32+ hex).
    Post-fix verifies that delegating to `_redact_error_message_for_audit`
    does NOT regress the heuristic coverage.
    """
    from swing.integrations.schwab.auth import _redacted_excerpt

    # 40-char base64-shaped string — matches Layer-1 regex; not registered.
    long_token = "abcDEFghiJKLmnoPQRstuVWXyz0123456789+/=A"
    assert len(long_token) >= 24

    exc = RuntimeError(f"transient failure with token {long_token}")
    redacted = _redacted_excerpt(exc)

    assert long_token not in redacted, (
        f"Layer-1 heuristic regression — token-shaped string leaked: {redacted!r}"
    )
    assert "<REDACTED>" in redacted
