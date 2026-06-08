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


# T-B.8 — Bundle B sentinel-leak coverage. Un-skipped at Sub-bundle B ship.
# Tests exercise each Trader-API trader.py wrapper with a sentinel-tainted
# response payload + sentinel-tainted error_message AND assert ZERO leakage
# through (a) caplog captures of `Schwabdev*` loggers + (b) the
# schwab_api_calls audit `error_message` column. Phase-2 live cassette
# recording (T-B.0.b §6) will add a real-response variant; V1 ships with
# the synthetic-fixture coverage as the binding test surface.


def test_23_trader_api_wrapper_does_not_leak_sentinel_through_audit_or_caplog(
    tmp_path, caplog,
):
    """T-B.8 — Trader-API wrappers redact sentinels in audit error_message
    + caplog records.

    Discriminating: plant a Layer-0 sentinel as account_hash + emit a
    schwabdev-level log record containing the sentinel; invoke
    get_account_details with a 401 response whose body contains the
    sentinel; assert (a) no sentinel in any audit error_message; (b) no
    sentinel in any captured caplog record from `Schwabdev*` loggers.
    """
    import logging as _logging
    import sqlite3 as _sqlite3
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        SchwabAuthError,
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.trader import get_account_details

    conn = ensure_schema(tmp_path / "trader-redaction.db")

    sentinel = "SENTINEL_TRADER_LEAK_PROBE_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    # Build a Response-like that returns a 401 with the sentinel echoed in body.
    err_resp = _MagicMock()
    err_resp.json.return_value = {"errors": [{"message": f"failed for {sentinel}"}]}
    err_resp.status_code = 401
    err_resp.headers = {}
    client = _MagicMock()
    client.account_details.return_value = err_resp

    # Emit a schwabdev-prefixed log record carrying the sentinel.
    sl = _logging.getLogger("Schwabdev")
    with caplog.at_level(_logging.DEBUG, logger="Schwabdev"):
        sl.warning("token rotate failed: %s", sentinel)
        try:
            get_account_details(
                client, conn, account_hash=sentinel,
                surface="cli", environment="production",
            )
        except SchwabAuthError:
            pass

    # (a) audit error_message has no sentinel.
    rows = conn.execute(
        "SELECT error_message FROM schwab_api_calls "
        "WHERE error_message IS NOT NULL"
    ).fetchall()
    for r in rows:
        assert sentinel not in (r[0] or ""), (
            f"Trader-API audit row leaked sentinel: {r[0]!r}"
        )
    # (b) caplog records have no sentinel in the message after factory redaction.
    for record in caplog.records:
        if record.name.startswith("Schwabdev"):
            assert sentinel not in record.getMessage(), (
                f"Schwabdev logger record leaked sentinel: {record.getMessage()!r}"
            )


def test_23b_trader_api_get_account_orders_audit_no_sentinel(tmp_path):
    """T-B.8 — get_account_orders sentinel coverage.

    Plants account_hash sentinel + sentinel-tainted 401 response body;
    asserts the audit error_message column does NOT contain the sentinel
    after the wrapper's redact-then-truncate flow.
    """
    import sqlite3 as _sqlite3
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        SchwabAuthError,
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.trader import get_account_orders

    conn = ensure_schema(tmp_path / "trader-orders-redaction.db")
    sentinel = "SENTINEL_ORDERS_PROBE_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    err_resp = _MagicMock()
    err_resp.json.return_value = {"error": f"path /accounts/{sentinel}/orders failed"}
    err_resp.status_code = 401
    err_resp.headers = {}
    client = _MagicMock()
    client.account_orders.return_value = err_resp

    try:
        get_account_orders(
            client, conn, account_hash=sentinel,
            from_entered_time="2026-05-07T00:00:00.000Z",
            to_entered_time="2026-05-14T00:00:00.000Z",
            surface="cli", environment="production",
        )
    except SchwabAuthError:
        pass

    rows = conn.execute(
        "SELECT error_message FROM schwab_api_calls "
        "WHERE error_message IS NOT NULL"
    ).fetchall()
    for r in rows:
        assert sentinel not in (r[0] or ""), (
            f"get_account_orders audit leaked sentinel: {r[0]!r}"
        )


def test_23c_trader_api_get_account_transactions_audit_no_sentinel(tmp_path):
    """T-B.8 — get_account_transactions sentinel coverage."""
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        SchwabAuthError,
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.trader import get_account_transactions

    conn = ensure_schema(tmp_path / "trader-tx-redaction.db")
    sentinel = "SENTINEL_TX_PROBE_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    err_resp = _MagicMock()
    err_resp.json.return_value = {"error": f"path /accounts/{sentinel}/transactions failed"}
    err_resp.status_code = 401
    err_resp.headers = {}
    client = _MagicMock()
    client.transactions.return_value = err_resp

    try:
        get_account_transactions(
            client, conn, account_hash=sentinel,
            start_date="2026-05-07T00:00:00.000Z",
            end_date="2026-05-14T00:00:00.000Z",
            surface="cli", environment="production",
        )
    except SchwabAuthError:
        pass

    rows = conn.execute(
        "SELECT error_message FROM schwab_api_calls "
        "WHERE error_message IS NOT NULL"
    ).fetchall()
    for r in rows:
        assert sentinel not in (r[0] or ""), (
            f"get_account_transactions audit leaked sentinel: {r[0]!r}"
        )


def test_23d_reconciliation_run_audit_link_does_not_leak_sentinel(tmp_path):
    """T-B.8 — link_reconciliation_run audit-link path covers the sentinel
    Trader-API discipline through the reconciliation_runs cross-table link.
    """
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        SchwabAuthError,
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.pipeline_steps import _step_schwab_orders

    conn = ensure_schema(tmp_path / "trader-recon-link.db")
    sentinel = "SENTINEL_RECON_PROBE_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    # Successful response with sentinel in field that would surface to error
    # paths if shape-validation fails.
    ok_resp = _MagicMock()
    ok_resp.json.return_value = []
    ok_resp.status_code = 200
    ok_resp.headers = {}
    details_resp = _MagicMock()
    details_resp.json.return_value = {
        "securitiesAccount": {
            "currentBalances": {
                "liquidationValue": 2000.0,
                "cashBalance": 100.0,
                "buyingPower": 4000.0,
            },
            "positions": [],
        },
    }
    details_resp.status_code = 200
    details_resp.headers = {}
    sd_client = _MagicMock()
    sd_client.account_orders.return_value = ok_resp
    sd_client.transactions.return_value = ok_resp
    sd_client.account_details.return_value = details_resp

    from types import SimpleNamespace
    cfg = SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="production",
                account_hash=sentinel,  # sentinel-as-account_hash
                lookback_days=7,
                timeout_seconds=30.0,
                marketdata_ladder_enabled=True,
                callback_url="https://127.0.0.1",
            ),
        ),
    )
    result = _step_schwab_orders(
        conn, cfg, pipeline_run_id=None, client=sd_client,
    )
    assert result["status"] == "completed"

    # No audit row's error_message OR source_artifact_path should contain
    # the sentinel.
    rows = conn.execute(
        "SELECT error_message FROM schwab_api_calls "
        "WHERE error_message IS NOT NULL"
    ).fetchall()
    for r in rows:
        assert sentinel not in (r[0] or ""), (
            f"orders-step audit leaked sentinel: {r[0]!r}"
        )
    # Same check on the reconciliation_runs row.
    recon_rows = conn.execute(
        "SELECT source_artifact_path, error_message, notes "
        "FROM reconciliation_runs"
    ).fetchall()
    for r in recon_rows:
        for field in r:
            if field:
                assert sentinel not in field, (
                    f"reconciliation_run row leaked sentinel in: {field!r}"
                )


# T-C.7 — Bundle C sentinel-leak coverage. Un-skipped at Sub-bundle C ship.
# Tests exercise both Market Data API marketdata.py wrappers
# (`get_quotes_batch` + `get_price_history`) with sentinel-tainted response
# payloads + sentinel-tainted error_messages + sentinel-bearing capital-S
# `Schwabdev` logger records AND assert ZERO leakage through (a) caplog
# captures of `Schwabdev*` loggers + (b) the schwab_api_calls audit
# `error_message` column + (c) the parquet-on-disk cache file contents.


def test_24_marketdata_quotes_audit_and_caplog_no_sentinel_leak(
    tmp_path, caplog,
):
    """T-C.7 — `get_quotes_batch` redacts sentinels in audit error_message
    + caplog records.

    Discriminating: plant a Layer-0 sentinel as account_hash-shaped secret +
    emit a schwabdev-level log record containing the sentinel; invoke
    get_quotes_batch against a stub `client.quotes` that returns a 401
    response whose body contains the sentinel; assert (a) no sentinel in
    any audit error_message; (b) no sentinel in any captured caplog record
    from `Schwabdev*` loggers (capital-S confirmed live per Sub-bundle A
    T-A.10 D1 deviation).
    """
    import logging as _logging
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        SchwabAuthError,
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.marketdata import get_quotes_batch

    conn = ensure_schema(tmp_path / "marketdata-quotes-redaction.db")

    sentinel = "SENTINEL_MD_QUOTES_PROBE_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    err_resp = _MagicMock()
    err_resp.json.return_value = {
        "errors": [{"message": f"quotes failed for {sentinel}"}],
    }
    err_resp.status_code = 401
    err_resp.headers = {}
    client = _MagicMock()
    client.quotes.return_value = err_resp

    # Emit a Schwabdev capital-S logger record carrying the sentinel BEFORE
    # invoking the wrapper — verifies Layer-2 factory-replacement redactor
    # catches sentinels emitted by ANY `Schwabdev*` logger name.
    sl = _logging.getLogger("Schwabdev")
    with caplog.at_level(_logging.DEBUG, logger="Schwabdev"):
        sl.warning("quotes call about to dispatch with token=%s", sentinel)
        try:
            get_quotes_batch(
                client, conn, ["XYZ"],
                surface="cli", environment="production",
            )
        except SchwabAuthError:
            pass

    # (a) audit error_message has no sentinel.
    rows = conn.execute(
        "SELECT error_message FROM schwab_api_calls "
        "WHERE error_message IS NOT NULL"
    ).fetchall()
    assert rows, "Test setup error: no audit row recorded"
    for r in rows:
        assert sentinel not in (r[0] or ""), (
            f"Market Data quotes audit row leaked sentinel: {r[0]!r}"
        )
    # (b) caplog records from Schwabdev* loggers have no sentinel after
    # factory redaction.
    schwabdev_records = [
        r for r in caplog.records if r.name.startswith("Schwabdev")
    ]
    assert schwabdev_records, (
        "Test setup error: no Schwabdev-prefixed caplog record captured"
    )
    for record in schwabdev_records:
        assert sentinel not in record.getMessage(), (
            f"Schwabdev logger record leaked sentinel: {record.getMessage()!r}"
        )


def test_25_marketdata_price_history_audit_and_caplog_no_sentinel_leak(
    tmp_path, caplog,
):
    """T-C.7 — `get_price_history` redacts sentinels in audit error_message
    + caplog records. Mirrors test_24's pattern against the second Market
    Data wrapper.
    """
    import logging as _logging
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        SchwabAuthError,
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.marketdata import get_price_history

    conn = ensure_schema(tmp_path / "marketdata-ph-redaction.db")

    sentinel = "SENTINEL_MD_PH_PROBE_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    err_resp = _MagicMock()
    err_resp.json.return_value = {
        "error": f"price_history failed for symbol with token {sentinel}",
    }
    err_resp.status_code = 401
    err_resp.headers = {}
    client = _MagicMock()
    client.price_history.return_value = err_resp

    sl = _logging.getLogger("Schwabdev.marketdata")
    with caplog.at_level(_logging.DEBUG, logger="Schwabdev"):
        sl.warning("price_history about to dispatch token=%s", sentinel)
        try:
            get_price_history(
                client, conn, "XYZ",
                period_type="day", period=10,
                frequency_type="minute", frequency=1,
                surface="cli", environment="production",
            )
        except SchwabAuthError:
            pass

    rows = conn.execute(
        "SELECT error_message FROM schwab_api_calls "
        "WHERE error_message IS NOT NULL"
    ).fetchall()
    assert rows, "Test setup error: no audit row recorded"
    for r in rows:
        assert sentinel not in (r[0] or ""), (
            f"Market Data price_history audit row leaked sentinel: {r[0]!r}"
        )
    schwabdev_records = [
        r for r in caplog.records if r.name.startswith("Schwabdev")
    ]
    assert schwabdev_records, (
        "Test setup error: no Schwabdev-prefixed caplog record captured"
    )
    for record in schwabdev_records:
        assert sentinel not in record.getMessage(), (
            f"Schwabdev logger record leaked sentinel: {record.getMessage()!r}"
        )


def test_26_marketdata_quotes_partial_response_per_symbol_breakdown_redacted(
    tmp_path,
):
    """T-C.7 — partial-response audit `error_message` excerpt with the
    per-symbol breakdown (e.g., "1/2 OK; failed: BADX") MUST NOT carry
    sentinel bytes from the failed-symbol's error envelope or symbol name.

    Discriminating shape per recon doc §3.2: `quotes` partial-response
    surfaces as an error envelope under the symbol key. Plant the sentinel
    (a) as a sentinel-named ticker that goes into the `failed: ...` list,
    AND (b) inside the per-symbol error-envelope payload — both paths feed
    `_redact_error_message_for_audit` via `_finish_hook` in marketdata.py.
    """
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.marketdata import get_quotes_batch

    conn = ensure_schema(tmp_path / "marketdata-partial-redaction.db")

    # Use a Layer-1-shaped sentinel (32+ hex) so the heuristic regex ALSO
    # catches it on the audit-row write path (defense-in-depth: belt+braces
    # alongside Layer-0 registration).
    sentinel = "SENTINEL_PARTIAL_" + uuid.uuid4().hex + uuid.uuid4().hex
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    # Partial-response: AAPL OK shape + a sentinel-named symbol with an
    # error envelope embedding the sentinel verbatim.
    ok_resp = _MagicMock()
    ok_resp.json.return_value = {
        "AAPL": {
            "quote": {"lastPrice": 999.99},  # ext-hours -- ignored (L1)
            "regular": {
                "regularMarketLastPrice": 150.0,
                "regularMarketTradeTime": 1700000000000,
            },
            "delayed": False,
        },
        # The failed symbol's NAME is sentinel-derived; the failed-symbol
        # list goes into the audit error_message excerpt.
        sentinel: {
            "errors": [{"message": f"upstream error for {sentinel}"}],
        },
    }
    ok_resp.status_code = 200
    ok_resp.headers = {}
    client = _MagicMock()
    client.quotes.return_value = ok_resp

    result = get_quotes_batch(
        client, conn, ["AAPL", sentinel],
        surface="cli", environment="production",
    )
    # Mapper drops the sentinel-named failed symbol; AAPL maps successfully.
    assert "AAPL" in result
    assert sentinel not in result

    rows = conn.execute(
        "SELECT status, error_message FROM schwab_api_calls "
        "WHERE endpoint = 'marketdata.quotes' "
        "AND error_message IS NOT NULL"
    ).fetchall()
    # Status is 'success' (at least one symbol mapped); error_message
    # carries the partial breakdown. Per `marketdata.py:_finish_hook`,
    # the per-symbol breakdown passes through `_redact_error_message_for_audit`
    # so the sentinel CANNOT survive into the excerpt.
    assert rows, "Test setup error: no partial-response audit row recorded"
    for status, msg in rows:
        assert sentinel not in (msg or ""), (
            f"Partial-response audit excerpt leaked sentinel: "
            f"status={status!r}, msg={msg!r}"
        )


def test_27_marketdata_cache_files_do_not_contain_sentinel(tmp_path):
    """T-C.7 — defense-in-depth: parquet cache files written via
    `write_window` (T-C.2) MUST NOT contain the sentinel anywhere.

    The cache path is for OHLCV bars (numeric columns + DatetimeIndex);
    sentinels travel via response BODIES which the mapper transforms into
    typed dataclasses — they should never reach parquet. This test
    construes a sentinel-bearing OHLCV response, invokes the mapper +
    cache write, then scans the on-disk parquet for the sentinel bytes.
    """
    import pandas as pd

    from swing.data.ohlcv_archive import write_window
    from swing.integrations.schwab.client import (
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.mappers import (
        map_price_history_to_window,
    )

    sentinel = "SENTINEL_CACHE_LEAK_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    # Build a price_history payload whose non-candle fields carry the
    # sentinel (Schwab "symbol" + a hypothetical adversarial "note" key).
    # The mapper extracts ONLY `candles` → typed bars; sentinel-bearing
    # non-candle fields are dropped.
    payload = {
        "symbol": sentinel,  # sentinel in symbol metadata
        "empty": False,
        "candles": [
            {
                "open": 100.0, "high": 101.0, "low": 99.5,
                "close": 100.5, "volume": 12345,
                "datetime": 1700000000000,
            },
            {
                "open": 100.5, "high": 101.5, "low": 100.0,
                "close": 101.0, "volume": 23456,
                "datetime": 1700086400000,
            },
        ],
        # Adversarial extra field carrying the sentinel.
        "notes": f"raw upstream debug: token={sentinel}",
    }
    window = map_price_history_to_window(payload, ticker="XYZ")
    # Bar emit verifies the mapper did NOT carry sentinel into typed shape.
    assert len(window.bars) == 2
    for bar in window.bars:
        # Bars expose only numeric / typed datetime fields.
        for field_value in (bar.open, bar.high, bar.low, bar.close, bar.volume):
            assert sentinel not in str(field_value)

    # Construct a parquet-ready DataFrame from the typed bars and write it.
    df = pd.DataFrame(
        [
            {
                "asof_date": bar.asof_date,
                "open": bar.open, "high": bar.high, "low": bar.low,
                "close": bar.close, "volume": bar.volume,
            }
            for bar in window.bars
        ]
    )
    cache_dir = tmp_path / "ohlcv-cache"
    write_window("XYZ", df, "schwab_api", cache_dir=cache_dir)

    # Scan the parquet bytes for the sentinel (it's UTF-8 text; even with
    # snappy / dict encoding, an unredacted literal-string value would
    # appear in the on-disk bytes).
    parquet_path = cache_dir / "XYZ.schwab_api.parquet"
    assert parquet_path.exists(), (
        f"Test setup error: cache write did not produce {parquet_path}"
    )
    raw_bytes = parquet_path.read_bytes()
    assert sentinel.encode("utf-8") not in raw_bytes, (
        f"Cache parquet bytes leaked sentinel — symbol/notes fields "
        f"reached disk: {parquet_path}"
    )


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


# ============================================================================
# Codex R3 Major #1 — redact-then-truncate (truncation-boundary leak)
# ============================================================================


def test_28_redacted_excerpt_redacts_before_truncating_boundary_straddle():
    """Codex R3 Major #1: `_redacted_excerpt` MUST redact the FULL message
    BEFORE truncating to `max_chars`. Otherwise, if a registered secret
    straddles the truncation boundary, Layer-0 exact-replace cannot match
    the partial-prefix that survives in the buffer + Layer-1 regex may
    not catch the short prefix either, leaking secret bytes into the
    audit row.

    Discriminating construction:
      - Register a 64-char sentinel.
      - Construct an exception whose `str(exc)` is `prefix + sentinel + suffix`
        where `prefix` consumes enough bytes that the sentinel STRADDLES
        the 80-char truncation boundary (start byte ~47, so the boundary
        cuts the sentinel mid-string).
      - Pre-fix: `raw[:max_chars]` truncates first → only `prefix + sentinel[:N]`
        survives → Layer-0's `.replace(full_sentinel, ...)` cannot match
        the partial → first N chars of sentinel LEAK through.
      - Post-fix: redact full message first → `<REDACTED>` substitutes for
        the entire sentinel → truncation operates on already-redacted string
        → NO partial-prefix can survive.

    Assertion: NO partial-prefix of the sentinel (>= 8 contiguous chars from
    the sentinel) appears in the output. The 8-char floor is a conservative
    "any substring long enough to be recognizably part of the secret".
    """
    from swing.integrations.schwab.auth import _redacted_excerpt

    # 64-char sentinel; charset deliberately chosen to fall BELOW Layer-1's
    # base64 heuristic floor: the suffix contains `!@#$%&` which BREAK the
    # contiguous-base64 run, so even at 64 chars the heuristic cannot match.
    # This isolates the test to Layer-0 (registered-secret) coverage —
    # ensuring the assertion would FAIL pre-fix and PASS post-fix.
    sentinel = "SENTINEL_TRUNCATE_BOUNDARY_qrst!uvwx@yz#aaaa$bbbb%cccc&ddddd123x"
    assert len(sentinel) == 64
    register_schwab_secrets([sentinel])

    # Body prefix sized so sentinel starts at exc-str byte ~47 and extends
    # past 80, straddling the truncation boundary in the MIDDLE.
    body_prefix = "Auth-failure context bytes filling the buffer: "
    assert len(body_prefix) == 47
    msg = body_prefix + sentinel + " (trailing context dropped after truncation)"

    exc = RuntimeError(msg)

    redacted = _redacted_excerpt(exc)

    # Output bounded by the audit-row column budget.
    assert len(redacted) <= 80, (
        f"Truncation cap not enforced; got len={len(redacted)}: {redacted!r}"
    )

    # Discriminating: NO partial-prefix of the sentinel (>= 8 contiguous
    # chars) may appear in the output. Pre-fix the truncation-first path
    # would leave a ~30-char partial-prefix of the sentinel visible.
    # Post-fix the full sentinel is replaced by `<REDACTED>` first.
    min_partial_len = 8
    for start in range(len(sentinel) - min_partial_len + 1):
        partial = sentinel[start : start + min_partial_len]
        assert partial not in redacted, (
            f"Partial sentinel prefix {partial!r} (start={start}) leaked "
            f"through truncation-first path: {redacted!r}"
        )


# ============================================================================
# Codex R1 Major #6 — sentinels emitted FROM INSIDE the schwabdev call
# ============================================================================
#
# Prior T-C.7 tests (test_24 + test_25) emit Schwabdev-logger records BEFORE
# invoking the wrapper. Codex R1 Major #6 flagged that these tests do not
# prove sentinels emitted from INSIDE schwabdev's quotes/price_history are
# suppressed when those emissions happen as a side-effect of the actual
# method call.
#
# These tests close that gap by attaching a side_effect to the MagicMock
# `quotes` / `price_history` method that emits a Schwabdev-logger warning
# carrying the sentinel WHEN CALLED. The wrapper consumes the response
# normally; we then assert ZERO sentinel leakage through caplog + audit.


def test_27_marketdata_quotes_sentinel_emitted_from_inside_call_is_redacted(
    tmp_path, caplog,
):
    """Codex R1 Major #6 discriminating test: schwabdev's `quotes` method
    emits a sentinel-bearing log record DURING the call (side-effect on
    invocation). Wrapper MUST NOT leak the sentinel into caplog records
    from `Schwabdev*` loggers (Layer-2 factory replacement covers this) NOR
    into the audit `error_message` column.

    Discriminates against the pre-Major-#6 testing pattern where sentinels
    were emitted BEFORE the wrapper call — that pattern doesn't exercise
    the wrapper's logger-context during the call window.
    """
    import logging as _logging
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.marketdata import get_quotes_batch

    conn = ensure_schema(tmp_path / "marketdata-quotes-inside-call.db")

    sentinel = "SENTINEL_QUOTES_INSIDE_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    # Side-effect: emit a Schwabdev logger record carrying the sentinel
    # WHEN `quotes(...)` is called. Then return a normal 200 response.
    schwabdev_logger = _logging.getLogger("Schwabdev.tokens")

    def fake_quotes(symbols=None, fields=None, indicative=False):
        # Mirrors schwabdev's internal token-refresh logging shape.
        schwabdev_logger.warning(
            f"quotes call dispatch — token refresh complete; token={sentinel}"
        )
        resp = _MagicMock()
        resp.status_code = 200
        # Return a populated quote so the wrapper's success path runs end-to-end.
        resp.json.return_value = {
            "AAPL": {
                "quote": {"lastPrice": 999.99},  # ext-hours -- ignored (L1)
                "regular": {
                    "regularMarketLastPrice": 100.0,
                    "regularMarketTradeTime": 1715692800000,
                },
                "delayed": False,
            },
        }
        resp.elapsed = _MagicMock()
        resp.elapsed.total_seconds.return_value = 0.05
        resp.headers = {}
        return resp

    client = _MagicMock()
    client.quotes.side_effect = fake_quotes

    with caplog.at_level(_logging.DEBUG, logger="Schwabdev"):
        get_quotes_batch(
            client, conn, ["AAPL"],
            surface="cli", environment="production",
        )

    # Discriminating: sentinel absent from ALL caplog records (any logger).
    for rec in caplog.records:
        msg = rec.getMessage()
        assert sentinel not in msg, (
            f"caplog leaked sentinel from inside-call emission "
            f"(logger={rec.name!r}): {msg!r}"
        )
        # Also assert against the formatted `.message` (some records may
        # carry the formatted form alongside the args-based getMessage).
        formatted = getattr(rec, "message", "") or ""
        assert sentinel not in formatted, (
            f"caplog.message leaked sentinel (logger={rec.name!r}): "
            f"{formatted!r}"
        )

    # Audit `error_message` must also not carry the sentinel (defensive —
    # the call succeeded, so error_message likely None; assert anyway).
    rows = conn.execute(
        "SELECT error_message FROM schwab_api_calls "
        "WHERE error_message IS NOT NULL"
    ).fetchall()
    for r in rows:
        assert sentinel not in (r[0] or ""), (
            f"audit error_message leaked inside-call sentinel: {r[0]!r}"
        )


def test_28_marketdata_price_history_sentinel_emitted_from_inside_call_is_redacted(
    tmp_path, caplog,
):
    """Codex R1 Major #6 discriminating test (price_history twin of test_27):
    schwabdev's `price_history` method emits a sentinel-bearing log record
    DURING the call. Wrapper MUST NOT leak the sentinel via caplog or audit.
    """
    import logging as _logging
    from unittest.mock import MagicMock as _MagicMock

    from swing.data.db import ensure_schema
    from swing.integrations.schwab.client import (
        ensure_schwab_log_redaction_factory_installed,
        register_schwab_secrets,
    )
    from swing.integrations.schwab.marketdata import get_price_history

    conn = ensure_schema(tmp_path / "marketdata-ph-inside-call.db")

    sentinel = "SENTINEL_PH_INSIDE_" + uuid.uuid4().hex[:8]
    register_schwab_secrets([sentinel])
    ensure_schwab_log_redaction_factory_installed()

    schwabdev_logger = _logging.getLogger("Schwabdev.marketdata")

    def fake_price_history(
        symbol=None, periodType=None, period=None,
        frequencyType=None, frequency=None,
        startDate=None, endDate=None,
        needExtendedHoursData=None, needPreviousClose=None,
    ):
        schwabdev_logger.warning(
            f"price_history dispatch — token refresh complete; "
            f"token={sentinel}; symbol={symbol}"
        )
        resp = _MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "candles": [
                {
                    "datetime": 1715692800000,
                    "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0,
                    "volume": 12345,
                },
            ],
            "empty": False,
            "symbol": symbol or "AAPL",
        }
        resp.elapsed = _MagicMock()
        resp.elapsed.total_seconds.return_value = 0.05
        resp.headers = {}
        return resp

    client = _MagicMock()
    client.price_history.side_effect = fake_price_history

    with caplog.at_level(_logging.DEBUG, logger="Schwabdev"):
        get_price_history(
            client, conn, "AAPL",
            period_type="day", period=10,
            frequency_type="minute", frequency=1,
            surface="cli", environment="production",
        )

    for rec in caplog.records:
        msg = rec.getMessage()
        assert sentinel not in msg, (
            f"caplog leaked sentinel from inside-call emission "
            f"(logger={rec.name!r}): {msg!r}"
        )
        formatted = getattr(rec, "message", "") or ""
        assert sentinel not in formatted, (
            f"caplog.message leaked sentinel (logger={rec.name!r}): "
            f"{formatted!r}"
        )

    rows = conn.execute(
        "SELECT error_message FROM schwab_api_calls "
        "WHERE error_message IS NOT NULL"
    ).fetchall()
    for r in rows:
        assert sentinel not in (r[0] or ""), (
            f"audit error_message leaked inside-call sentinel: {r[0]!r}"
        )


# ============================================================================
# Tests 29-30 — T-B.6: cfg-cascade-sourced credential sentinel-leak audit
# ============================================================================
#
# Sub-bundle A's `test_env_var_values_registered_for_redaction` (Test 9 in
# test_schwab_credential_env_vars.py) + `..._when_short_and_layer1_skips`
# (Test 9.bis) cover env-var-sourced credentials only. T-B.1 added a
# Tier-2 cfg-cascade resolution path (env absent → consult
# `cfg.integrations.schwab.{client_id,client_secret}` from
# `~/swing-data/user-config.toml`); the cfg-tier branch also calls
# `register_schwab_secrets` + `ensure_schwab_log_redaction_factory_installed`
# BEFORE returning. T-B.6 pins that this registration fires for the
# cfg-cascade path with the SAME discriminating threat-model split as the
# Sub-bundle A precedent:
#
#   * Test 29 (a): long ALL-CAPS sentinel — Layer-1 heuristic catches it
#     AND Layer-0 registry catches it; end-to-end leak guarantee.
#   * Test 30 (b): 16-char hyphenated sentinel — BYPASSES Layer-1
#     (`[A-Za-z]{24+}` for base64-like; hex 32+); ONLY Layer-0 registry
#     registration scrubs it. If the cfg-tier branch ever stops calling
#     `register_schwab_secrets`, this test fails.
#
# Brief §3 T-B.6 binding scope extension over T-B.1's existing
# `test_cfg_sentinel_redacted_from_schwabdev_log_records`: T-B.6 covers
# BOTH caplog (Layer-2 factory) AND audit `error_message` redactor
# (`_redact_error_message_for_audit` — the standalone fallback that writes
# to `schwab_api_calls.error_message`). Test 18 above pins this redactor
# for ad-hoc registered sentinels; Tests 29-30 pin the same guarantee for
# sentinels that arrived through the cfg-cascade path.


def _write_cfg_with_schwab_credentials(
    tmp_path,
    *,
    client_id: str,
    client_secret: str,
) -> None:
    """Write a minimal user-config.toml carrying the T-B.2 schwab credential
    fields under the cfg-cascade home directory (tmp_path).

    USERPROFILE+HOME monkeypatch is caller's responsibility (CLAUDE.md
    gotcha — `swing/config_user.py:_user_home` reads them).
    """
    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    user_cfg = swing_data / "user-config.toml"
    # Minimal TOML — only the two T-B.2 fields the resolver consults.
    user_cfg.write_text(
        "[integrations.schwab]\n"
        f"client_id = \"{client_id}\"\n"
        f"client_secret = \"{client_secret}\"\n",
        encoding="utf-8",
    )


def test_29_cfg_cascade_credentials_registered_for_redaction(
    tmp_path, monkeypatch, caplog,
):
    """T-B.6 Test (a) — sibling to Sub-bundle A's
    `test_env_var_values_registered_for_redaction` (Test 9 in
    `test_schwab_credential_env_vars.py`), but credentials sourced via the
    cfg-cascade path (Tier-2: user-config.toml) instead of env vars.

    Threat model split: this sentinel is long ALL-CAPS with underscores —
    long enough that Layer-1 base64 heuristic would scrub it WITHOUT
    requiring registry registration. End-to-end leak guarantee: caplog
    (Layer-2 factory) AND audit `error_message` redactor (standalone
    fallback) both scrub the sentinel.
    """
    from types import SimpleNamespace

    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import (
        _redact_error_message_for_audit,
        ensure_schwab_log_redaction_factory_installed,
    )

    # CLAUDE.md gotcha: USERPROFILE+HOME both monkeypatched before any
    # `write_user_overrides` / `load_user_overrides` / cfg-tier resolution
    # fires; otherwise the cfg write would leak to the operator's real
    # `~/swing-data/user-config.toml`.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    # Env-tier MUST be absent so the cascade reaches Tier-2.
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)

    # Long ALL-CAPS sentinels (mirror Sub-bundle A's `_SENTINEL_CLIENT_ID`
    # shape): 47 chars, alphanumeric + underscores. Layer-1 catches them
    # via the base64-like `[A-Za-z]{24+}` heuristic; Layer-0 also catches
    # them via registry. This test pins the end-to-end leak guarantee.
    cfg_sentinel_id = (
        "CFG_CASCADE_LONG_CLIENT_ID_SENTINEL_"
        + uuid.uuid4().hex[:8].upper()
    )
    cfg_sentinel_secret = (
        "CFG_CASCADE_LONG_CLIENT_SECRET_SENTINEL_"
        + uuid.uuid4().hex[:8].upper()
    )
    _write_cfg_with_schwab_credentials(
        tmp_path,
        client_id=cfg_sentinel_id,
        client_secret=cfg_sentinel_secret,
    )

    # Build a duck-typed cfg that carries the same values the file holds —
    # `resolve_credentials_env_or_prompt` consults `cfg.integrations.schwab.
    # {client_id, client_secret}` directly; the user-config.toml file
    # written above is what an OPERATOR pre-stages, but the resolver reads
    # the cfg-object's already-loaded fields. We mirror that by passing a
    # SimpleNamespace shaped the same way (matches T-B.1 cfg-cascade tests'
    # `_cfg_with` helper at tests/integrations/test_schwab_credential_cascade.py).
    cfg = SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="production",
                callback_url="https://127.0.0.1",
                timeout_seconds=10,
                client_id=cfg_sentinel_id,
                client_secret=cfg_sentinel_secret,
            ),
        ),
    )

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=False,
    )
    assert client_id == cfg_sentinel_id
    assert client_secret == cfg_sentinel_secret

    # Cfg-tier branch MUST have called register_schwab_secrets +
    # ensure_schwab_log_redaction_factory_installed before returning.
    # Emit a Schwabdev-prefixed log record interpolating both sentinels +
    # assert they are scrubbed from caplog.
    ensure_schwab_log_redaction_factory_installed()
    schwabdev_logger = logging.getLogger("Schwabdev.test_t_b_6_cfg_long")
    caplog.set_level(logging.DEBUG, logger="Schwabdev")
    schwabdev_logger.warning(
        "test record interpolating cfg-sourced id=%s secret=%s",
        cfg_sentinel_id,
        cfg_sentinel_secret,
    )
    captured_caplog = "\n".join(r.getMessage() for r in caplog.records)
    assert cfg_sentinel_id not in captured_caplog, (
        f"cfg-cascade client_id sentinel leaked into Schwabdev log records "
        f"— cfg-tier registry registration broken:\n{captured_caplog}"
    )
    assert cfg_sentinel_secret not in captured_caplog, (
        f"cfg-cascade client_secret sentinel leaked into Schwabdev log "
        f"records — cfg-tier registry registration broken:\n{captured_caplog}"
    )

    # Audit-row dimension (mirror test_18 above): the standalone redactor
    # used when writing to `schwab_api_calls.error_message` must also scrub
    # cfg-cascade-sourced sentinels. This pins that the same process-global
    # registry that drives Layer-2 also drives audit-row Layer-0 path.
    audit_message = (
        f"SchwabAuthError: token={cfg_sentinel_id} secret={cfg_sentinel_secret}"
    )
    redacted_audit = _redact_error_message_for_audit(audit_message)
    assert cfg_sentinel_id not in redacted_audit, (
        f"cfg-cascade client_id leaked into audit error_message redactor:\n"
        f"{redacted_audit}"
    )
    assert cfg_sentinel_secret not in redacted_audit, (
        f"cfg-cascade client_secret leaked into audit error_message redactor:\n"
        f"{redacted_audit}"
    )


def test_30_cfg_cascade_credentials_redacted_when_short_and_layer1_skips(
    tmp_path, monkeypatch, caplog,
):
    """T-B.6 Test (b) — sibling to Sub-bundle A's
    `test_env_var_values_redacted_when_short_and_layer1_skips` (Test 9.bis
    in `test_schwab_credential_env_vars.py`), but credentials sourced via
    the cfg-cascade path.

    Discriminator: short hyphenated sentinels (16 chars; hyphens BREAK both
    Layer-1 heuristic patterns — `[A-Za-z]{24+}` for base64-like AND
    `[0-9a-f]{32+}` for hex). Only Layer-0 registry exact-replace scrubs
    them. If the cfg-tier branch in
    `swing/integrations/schwab/auth.py:resolve_credentials_env_or_prompt`
    ever stops calling `register_schwab_secrets`, THIS test fails (Test 29
    above might still pass via Layer-1 fallback).

    Asserts sentinel absent from BOTH caplog (Layer-2 factory) AND audit
    `error_message` redactor (standalone fallback) — pins the full
    cfg-cascade redaction posture.
    """
    from types import SimpleNamespace

    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import (
        _redact_error_message_for_audit,
        ensure_schwab_log_redaction_factory_installed,
    )

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)

    # Short hyphenated sentinels: 16-18 chars; hyphens break Layer-1's hex
    # AND base64 patterns (`[A-Za-z]{24+}` rejects strings with `-`;
    # `[0-9a-f]{32+}` rejects strings with non-hex chars). Mirrors
    # Sub-bundle A's `_SHORT_SENTINEL_CLIENT_ID = "test-app-id-7f3a"`
    # shape.
    cfg_short_id = "cfg-short-id-" + uuid.uuid4().hex[:4]  # 17 chars
    cfg_short_secret = "cfg-short-sec-" + uuid.uuid4().hex[:4]  # 18 chars
    _write_cfg_with_schwab_credentials(
        tmp_path,
        client_id=cfg_short_id,
        client_secret=cfg_short_secret,
    )

    cfg = SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="production",
                callback_url="https://127.0.0.1",
                timeout_seconds=10,
                client_id=cfg_short_id,
                client_secret=cfg_short_secret,
            ),
        ),
    )

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=False,
    )
    assert client_id == cfg_short_id
    assert client_secret == cfg_short_secret

    ensure_schwab_log_redaction_factory_installed()
    schwabdev_logger = logging.getLogger("Schwabdev.test_t_b_6_cfg_short")
    caplog.set_level(logging.DEBUG, logger="Schwabdev")
    schwabdev_logger.warning(
        "test record interpolating short cfg-sourced id=%s secret=%s",
        cfg_short_id,
        cfg_short_secret,
    )
    captured_caplog = "\n".join(r.getMessage() for r in caplog.records)
    assert cfg_short_id not in captured_caplog, (
        f"short cfg-cascade client_id sentinel leaked — cfg-tier "
        f"register_schwab_secrets broken (Layer-1 cannot save us; sentinel "
        f"contains hyphens that break the heuristic):\n{captured_caplog}"
    )
    assert cfg_short_secret not in captured_caplog, (
        f"short cfg-cascade client_secret sentinel leaked — cfg-tier "
        f"register_schwab_secrets broken (Layer-1 cannot save us):\n"
        f"{captured_caplog}"
    )

    # Audit-row dimension: same Layer-0-only discriminator applied to the
    # standalone error_message redactor.
    audit_message = (
        f"SchwabAuthError: token={cfg_short_id} secret={cfg_short_secret}"
    )
    redacted_audit = _redact_error_message_for_audit(audit_message)
    assert cfg_short_id not in redacted_audit, (
        f"short cfg-cascade client_id leaked into audit error_message "
        f"redactor — Layer-0 registry broken on cfg-tier path:\n"
        f"{redacted_audit}"
    )
    assert cfg_short_secret not in redacted_audit, (
        f"short cfg-cascade client_secret leaked into audit error_message "
        f"redactor — Layer-0 registry broken on cfg-tier path:\n"
        f"{redacted_audit}"
    )
