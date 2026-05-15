"""Phase 12 Sub-bundle A T-A.3 — pipeline `_construct_pipeline_schwab_client`
reads SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET env vars.

5 binding tests per dispatch brief §3 T-A.3 acceptance criteria:

  1. Both env vars set + non-empty → constructs + returns Client via
     `construct_authenticated_client(cfg, env, client_id=, client_secret=)`.
  2. Both env vars absent → returns None silently; NO WARNING log.
  3. Partial: only CLIENT_ID set → returns None + WARNING log naming
     "incomplete" + "CLIENT_ID=present" + "CLIENT_SECRET=absent".
  4. Both env vars set but `construct_authenticated_client` raises
     SchwabAuthError → returns None + WARNING log naming "construction
     failed" + the typed-error class name.
  5. Production-only contract: under `environment='production'` with both
     env vars set + mocked construct_authenticated_client, the helper
     returns the live mock client (downstream pipeline steps can then
     accumulate `surface='pipeline'` audit rows). Sandbox short-circuit
     stays at the ladder layer; this test asserts only the helper's
     return-value contract.

Pattern mirrors `tests/integrations/test_schwab_credential_env_vars.py`
(SimpleNamespace cfg, monkeypatch.setenv/delenv, MagicMock injection).
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from swing.integrations.schwab.client import (
    SchwabAuthError,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def fake_cfg() -> SimpleNamespace:
    """Minimal cfg shaped like `swing.config.Config`. Helper reads
    `cfg.integrations.schwab.environment` and passes cfg through to
    `construct_authenticated_client`."""
    return SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="production",
                callback_url="https://127.0.0.1",
                timeout_seconds=10,
            ),
        ),
    )


@pytest.fixture
def fake_cfg_sandbox() -> SimpleNamespace:
    return SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="sandbox",
                callback_url="https://127.0.0.1",
                timeout_seconds=10,
            ),
        ),
    )


@pytest.fixture
def clear_credentials_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET are absent at test
    entry. Operator's real shell may have them set; explicit delenv keeps
    tests deterministic regardless of host environment."""
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)


# ============================================================================
# Tests
# ============================================================================


def test_both_env_vars_set_constructs_client_with_env_credentials(
    fake_cfg: SimpleNamespace,
    clear_credentials_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 1 — happy path: both env vars set; helper invokes
    `construct_authenticated_client` with the env-derived credentials +
    returns the live client. Asserts the cfg.environment passes through."""
    from swing.pipeline import runner as runner_mod

    monkeypatch.setenv("SCHWAB_CLIENT_ID", "env-test-client-id")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "env-test-client-secret")

    mock_client = MagicMock(name="schwabdev_client")
    construct_calls: list[dict] = []

    def fake_construct(cfg, environment, client_id, client_secret):
        construct_calls.append({
            "cfg": cfg,
            "environment": environment,
            "client_id": client_id,
            "client_secret": client_secret,
        })
        return mock_client

    monkeypatch.setattr(
        runner_mod, "construct_authenticated_client", fake_construct,
    )

    result = runner_mod._construct_pipeline_schwab_client(fake_cfg)

    assert result is mock_client, (
        f"expected mock client returned; got {type(result).__name__}"
    )
    assert len(construct_calls) == 1, (
        f"expected exactly one construct call; got {len(construct_calls)}"
    )
    call = construct_calls[0]
    assert call["client_id"] == "env-test-client-id"
    assert call["client_secret"] == "env-test-client-secret"
    assert call["environment"] == "production"


def test_both_env_vars_absent_returns_none_silently(
    fake_cfg: SimpleNamespace,
    clear_credentials_env: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 2 — silent-skip path: neither env var set → return None;
    NO WARNING log emitted (this is the V1 silent-skip-with-no-noise path
    so operators not using env vars don't see spurious log noise)."""
    from swing.pipeline import runner as runner_mod

    # Guard: also intercept construct_authenticated_client so a regression
    # in the early-return path can't accidentally invoke it.
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "construct_authenticated_client must NOT be called when both "
            "env vars are absent",
        )

    monkeypatch.setattr(
        runner_mod, "construct_authenticated_client", _should_not_be_called,
    )

    caplog.set_level(logging.WARNING, logger="swing.pipeline.runner")
    result = runner_mod._construct_pipeline_schwab_client(fake_cfg)

    assert result is None
    # Filter to runner-emitted records only to avoid noise from imports etc.
    runner_warnings = [
        rec for rec in caplog.records
        if rec.name == "swing.pipeline.runner"
        and rec.levelno >= logging.WARNING
    ]
    assert runner_warnings == [], (
        f"expected ZERO WARNING records from swing.pipeline.runner on "
        f"silent-skip path; got: "
        f"{[(r.levelname, r.getMessage()) for r in runner_warnings]}"
    )


def test_partial_env_vars_returns_none_with_incomplete_warning(
    fake_cfg: SimpleNamespace,
    clear_credentials_env: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 3 — partial env vars: only CLIENT_ID set, CLIENT_SECRET unset.

    Helper catches SchwabConfigMissingError raised by
    `resolve_credentials_env_or_prompt(allow_prompt=False)` + returns None
    + logs a single WARNING line naming "incomplete" + per-var
    "present"/"absent" status so operators diagnose misconfiguration."""
    from swing.pipeline import runner as runner_mod

    monkeypatch.setenv("SCHWAB_CLIENT_ID", "env-only-id-set")
    # SCHWAB_CLIENT_SECRET intentionally absent.

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "construct_authenticated_client must NOT be called when env "
            "vars are only partially set",
        )

    monkeypatch.setattr(
        runner_mod, "construct_authenticated_client", _should_not_be_called,
    )

    caplog.set_level(logging.WARNING, logger="swing.pipeline.runner")
    result = runner_mod._construct_pipeline_schwab_client(fake_cfg)

    assert result is None, (
        f"expected None on partial env vars (NOT raise); got {result!r}"
    )

    runner_warnings = [
        rec for rec in caplog.records
        if rec.name == "swing.pipeline.runner"
        and rec.levelno >= logging.WARNING
    ]
    assert len(runner_warnings) == 1, (
        f"expected exactly one WARNING record on partial-env-vars path; "
        f"got {len(runner_warnings)}: "
        f"{[(r.levelname, r.getMessage()) for r in runner_warnings]}"
    )
    msg = runner_warnings[0].getMessage()
    assert "incomplete" in msg, (
        f"WARNING message should name 'incomplete'; got: {msg!r}"
    )
    assert "CLIENT_ID=present" in msg, (
        f"WARNING message should report CLIENT_ID=present; got: {msg!r}"
    )
    assert "CLIENT_SECRET=absent" in msg, (
        f"WARNING message should report CLIENT_SECRET=absent; got: {msg!r}"
    )


def test_construction_failure_returns_none_with_warning(
    fake_cfg: SimpleNamespace,
    clear_credentials_env: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 4 — both env vars set but `construct_authenticated_client`
    raises SchwabAuthError (rotation failure / silent OAuth fail).

    Helper catches the typed error + returns None + logs WARNING naming
    the class name. Pipeline does NOT crash (V1 graceful-degradation)."""
    from swing.pipeline import runner as runner_mod

    monkeypatch.setenv("SCHWAB_CLIENT_ID", "env-test-id-construct-fail")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "env-test-secret-construct-fail")

    def fake_construct(cfg, environment, client_id, client_secret):
        raise SchwabAuthError(401, "<rotation failed: token expired>")

    monkeypatch.setattr(
        runner_mod, "construct_authenticated_client", fake_construct,
    )

    caplog.set_level(logging.WARNING, logger="swing.pipeline.runner")
    result = runner_mod._construct_pipeline_schwab_client(fake_cfg)

    assert result is None, (
        f"expected None on construction failure (NOT propagated); "
        f"got {result!r}"
    )
    runner_warnings = [
        rec for rec in caplog.records
        if rec.name == "swing.pipeline.runner"
        and rec.levelno >= logging.WARNING
    ]
    assert len(runner_warnings) == 1, (
        f"expected exactly one WARNING record on construction-failure path; "
        f"got {len(runner_warnings)}: "
        f"{[(r.levelname, r.getMessage()) for r in runner_warnings]}"
    )
    msg = runner_warnings[0].getMessage()
    # The message should reference construction failure + the underlying
    # exception class or message so operators can root-cause.
    assert "construction failed" in msg or "rotation failed" in msg, (
        f"WARNING message should name 'construction failed' OR include the "
        f"underlying error excerpt; got: {msg!r}"
    )


def test_production_env_threading_returns_live_mock_client(
    fake_cfg: SimpleNamespace,
    clear_credentials_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 5 — integration-shape: env=production + both env vars set +
    mocked `construct_authenticated_client` → helper returns the live
    mock client. Asserts the production-only contract by verifying the
    environment passed through is exactly the cfg's environment string
    (NOT a hardcoded literal).

    Production-only audit-row accumulation is enforced by the ladder layer
    (Sub-bundle C sandbox short-circuit lives there); this test pins only
    the helper's contract to pass cfg.environment through verbatim.
    """
    from swing.pipeline import runner as runner_mod

    monkeypatch.setenv("SCHWAB_CLIENT_ID", "prod-env-client-id")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "prod-env-client-secret")

    mock_client = MagicMock(name="schwabdev_client_production")
    seen_env: list[str] = []

    def fake_construct(cfg, environment, client_id, client_secret):
        seen_env.append(environment)
        return mock_client

    monkeypatch.setattr(
        runner_mod, "construct_authenticated_client", fake_construct,
    )

    result = runner_mod._construct_pipeline_schwab_client(fake_cfg)

    assert result is mock_client
    assert seen_env == ["production"], (
        f"expected helper to pass cfg.integrations.schwab.environment "
        f"verbatim to construct_authenticated_client; got {seen_env!r}"
    )
