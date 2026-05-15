"""T-B.1 — `resolve_credentials_env_or_prompt` cfg-cascade extension tests.

Phase 12 Sub-bundle B T-B.1 — the cfg-tier joins the SCHWAB credential
cascade between env vars (Tier-1, highest) and prompt (Tier-3, lowest).
T-B.2 added `cfg.integrations.schwab.client_id` + `.client_secret`; this
task wires them into the resolution path so operator can persist app
credentials in `~/swing-data/user-config.toml` once instead of needing
per-shell env-var setup.

Locks (per dispatch brief §3 T-B.1):
  * Tier-1 env-var resolution unchanged from Sub-bundle A:
    - Both set + non-empty → use them, skip cfg + prompt.
    - Partial env-tier (one set, the other absent OR either empty /
      whitespace-only when the other is present) → RAISES
      SchwabConfigMissingError (NOT falls through to cfg-tier — partial
      env-tier signals operator typo / shell-session error, not legitimate
      fallback intent).
  * Tier-2 cfg resolution (NEW):
    - Env vars absent → consult cfg.integrations.schwab.{client_id,
      client_secret}. If BOTH non-empty + non-whitespace → use them, skip
      prompt; register secrets in Layer-0 redactor BEFORE returning.
    - Partial cfg-tier (only one set, OR either empty / whitespace-only)
      FALLS THROUGH to next tier (differs from env-tier; cfg-tier is the
      file-tier where one field absent may signal "want to mix env-var for
      secret and file for id" — operator-friendly).
  * Tier-3 prompt fallback unchanged from Sub-bundle A.
  * Env wins over cfg unambiguously: if both env vars set AND cfg fields
    set → env wins; cfg ignored for THIS invocation (no on-disk mutation).
  * allow_prompt=False discipline:
    - env both set → returns env values.
    - env absent + cfg both set → returns cfg values (NEW behavior).
    - env absent + cfg absent → returns (None, None) (pipeline silent-skip
      contract preserved).
    - env absent + partial cfg → returns (None, None) (partial cfg falls
      through; with prompt disabled the lowest tier returns None pair).
  * Sentinel-leak guarantee: cfg-sourced credentials NEVER appear in audit
    error_message excerpts or log records — `register_schwab_secrets`
    fires BEFORE return.

Test catalogue (per brief §3 acceptance criteria):
  1. env both + cfg both → env wins; prompter NOT invoked.
  2. env absent + cfg both → cfg returned; prompter NOT invoked; registry
     contains cfg values.
  3. env absent + cfg partial (id only) + allow_prompt=True → prompt fires
     for BOTH; operator-typed values returned; cfg ignored.
  4. env absent + cfg both + allow_prompt=False → cfg returned (pipeline).
  5. env absent + cfg empty-string fields + allow_prompt=True → prompt
     fires (empty-string == ABSENT-FOR-RESOLUTION at cfg-tier).
  6. env partial (id only) + cfg both → RAISES (env-tier partial wins;
     cfg fallback does NOT apply when env-tier is partial — LOCK).
  7. Sentinel-leak — cfg-sourced short hyphenated sentinels (Layer-1
     bypass) scrubbed from Schwabdev log records via Layer-0 registry.
  8. (helpful add) cfg whitespace-only fields treated as ABSENT-FOR-
     RESOLUTION; prompt fires (mirrors env-tier whitespace handling).
  9. (helpful add) env absent + cfg partial + allow_prompt=False
     → returns (None, None) (criterion 6 bullet 4).
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest


# Sentinels — discriminating substrings that must NOT leak. Short
# hyphenated form bypasses Layer-1 heuristic (`[A-Za-z]{24+}` for
# base64-like, hex 32+); only Layer-0 registry exact-replace catches them,
# so a sentinel-leak test using these pins that `register_schwab_secrets`
# ran on the cfg-tier path.
_CFG_SENTINEL_CLIENT_ID = "cfg-app-id-9b2f"  # 16 chars; hyphens
_CFG_SENTINEL_CLIENT_SECRET = "cfg-sec-d4a1-77c8"  # 17 chars; hyphens
_ENV_SENTINEL_CLIENT_ID = "env-app-id-1a4e"  # 15 chars; hyphens
_ENV_SENTINEL_CLIENT_SECRET = "env-sec-e8c3-22f7"  # 17 chars; hyphens


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def clear_credentials_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET absent at test entry."""
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)


def _cfg_with(client_id: str = "", client_secret: str = "") -> SimpleNamespace:
    """Construct a minimal cfg shaped like `Config` carrying the T-B.2
    cfg.integrations.schwab.{client_id,client_secret} fields.

    Uses SimpleNamespace (not real `Config`) to avoid pulling in the full
    validation chain; the helper only reads `cfg.integrations.schwab.client_id`
    + `.client_secret` so duck-typing is sufficient.
    """
    return SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="production",
                callback_url="https://127.0.0.1",
                timeout_seconds=10,
                client_id=client_id,
                client_secret=client_secret,
            ),
        ),
    )


# ============================================================================
# Tests
# ============================================================================


def test_env_wins_over_cfg_when_both_set(
    clear_credentials_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 1 (brief §3 AC4) — env vars override cfg unambiguously.

    Both env vars + both cfg fields set → env values returned; cfg ignored
    for THIS invocation; prompter MUST NOT fire.
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt

    monkeypatch.setenv("SCHWAB_CLIENT_ID", _ENV_SENTINEL_CLIENT_ID)
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", _ENV_SENTINEL_CLIENT_SECRET)
    cfg = _cfg_with(
        client_id=_CFG_SENTINEL_CLIENT_ID,
        client_secret=_CFG_SENTINEL_CLIENT_SECRET,
    )

    def _no_prompt(*args: Any, **kwargs: Any) -> str:
        raise AssertionError(
            "prompter must NOT fire when env-tier resolves (env wins over cfg)",
        )

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=True, prompter=_no_prompt,
    )
    assert client_id == _ENV_SENTINEL_CLIENT_ID
    assert client_secret == _ENV_SENTINEL_CLIENT_SECRET


def test_cfg_returned_when_env_absent_and_cfg_both_set(
    clear_credentials_env: None,
) -> None:
    """Test 2 (brief §3 AC2) — Tier-2 cfg resolution happy path.

    Env absent + cfg both set + non-whitespace → cfg values returned;
    prompter MUST NOT fire. Registry contains cfg values post-call so the
    Layer-2 redaction factory catches subsequent schwabdev log records.
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import _GLOBAL_KNOWN_SECRETS

    cfg = _cfg_with(
        client_id=_CFG_SENTINEL_CLIENT_ID,
        client_secret=_CFG_SENTINEL_CLIENT_SECRET,
    )

    def _no_prompt(*args: Any, **kwargs: Any) -> str:
        raise AssertionError(
            "prompter must NOT fire when cfg-tier resolves",
        )

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=True, prompter=_no_prompt,
    )
    assert client_id == _CFG_SENTINEL_CLIENT_ID
    assert client_secret == _CFG_SENTINEL_CLIENT_SECRET
    # Layer-0 known-secrets registry MUST contain both cfg values so any
    # subsequent schwabdev log record that interpolates them is scrubbed.
    assert _CFG_SENTINEL_CLIENT_ID in _GLOBAL_KNOWN_SECRETS
    assert _CFG_SENTINEL_CLIENT_SECRET in _GLOBAL_KNOWN_SECRETS


def test_cfg_partial_falls_through_to_prompt(
    clear_credentials_env: None,
) -> None:
    """Test 3 (brief §3 AC2 LOCK) — partial cfg-tier FALLS THROUGH (NOT raises).

    Env absent + cfg has CLIENT_ID only (CLIENT_SECRET empty) +
    allow_prompt=True → prompt fires for BOTH credentials; operator-typed
    values returned; cfg's partial id IGNORED.

    LOCK rationale: cfg-tier is the file-tier; one field absent may signal
    "want to use env-var for secret and file for id" — partial cfg
    treated as ABSENT-FOR-RESOLUTION, not error. This differs from env-tier
    which RAISES on partial (signals operator typo / shell-session error).
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt

    cfg = _cfg_with(
        client_id=_CFG_SENTINEL_CLIENT_ID,  # id only — partial
        client_secret="",
    )

    calls: list[str] = []

    def _stub_prompter(label: str, *args: Any, **kwargs: Any) -> str:
        calls.append(label)
        if "secret" in label.lower():
            return "prompted_secret"
        return "prompted_id"

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=True, prompter=_stub_prompter,
    )
    # Operator-typed values returned (partial cfg ignored entirely — NOT
    # blended with the prompted secret).
    assert client_id == "prompted_id"
    assert client_secret == "prompted_secret"
    # Prompter fired TWICE — once per credential — confirming cfg's
    # partial id was NOT consumed.
    assert len(calls) == 2


def test_cfg_returned_with_allow_prompt_false_when_env_absent(
    clear_credentials_env: None,
) -> None:
    """Test 4 (brief §3 AC6 bullet 2) — pipeline path picks up cfg values.

    Env absent + cfg both set + allow_prompt=False → cfg values returned.
    NEW V1 behavior: pipeline (T-A.3 path) now also benefits from
    file-tier credentials, not just env vars.
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt

    cfg = _cfg_with(
        client_id=_CFG_SENTINEL_CLIENT_ID,
        client_secret=_CFG_SENTINEL_CLIENT_SECRET,
    )

    def _no_prompt(*args: Any, **kwargs: Any) -> str:
        raise AssertionError(
            "prompter must NOT fire when allow_prompt=False",
        )

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=False, prompter=_no_prompt,
    )
    assert client_id == _CFG_SENTINEL_CLIENT_ID
    assert client_secret == _CFG_SENTINEL_CLIENT_SECRET


def test_cfg_empty_strings_fall_through_to_prompt(
    clear_credentials_env: None,
) -> None:
    """Test 5 (brief §3 AC2 + AC5 empty == absent) — empty-string cfg fields
    treated as ABSENT-FOR-RESOLUTION.

    Env absent + cfg fields are both empty strings (which is the T-B.2
    default; an operator who hasn't filled in user-config.toml at all has
    `client_id=""` and `client_secret=""` after `apply_overrides`) +
    allow_prompt=True → prompt fires. This is the most-common operational
    state pre-T-B.4 (operator hasn't run any persist path yet).
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt

    cfg = _cfg_with(client_id="", client_secret="")

    def _stub_prompter(label: str, *args: Any, **kwargs: Any) -> str:
        if "secret" in label.lower():
            return "prompted_secret_v"
        return "prompted_id_v"

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=True, prompter=_stub_prompter,
    )
    assert client_id == "prompted_id_v"
    assert client_secret == "prompted_secret_v"


def test_env_partial_raises_even_when_cfg_both_set(
    clear_credentials_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 6 (brief §3 AC1 LOCK) — env-tier partial RAISES even when cfg
    could provide a fallback.

    Env partial (only CLIENT_ID set) + cfg both set + allow_prompt=True →
    SchwabConfigMissingError. Cfg fallback does NOT apply when env-tier
    is partial.

    LOCK rationale: env-tier partial signals operator typo or
    shell-session error (e.g., operator set CLIENT_ID in PowerShell
    profile but forgot the SECRET). Falling through to cfg silently
    would HIDE the misconfiguration — operator's stated intent (env
    vars) failed, so we surface that explicitly rather than papering
    over it with the file-tier values.
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import SchwabConfigMissingError

    monkeypatch.setenv("SCHWAB_CLIENT_ID", _ENV_SENTINEL_CLIENT_ID)
    # CLIENT_SECRET absent → env-tier partial.
    cfg = _cfg_with(
        client_id=_CFG_SENTINEL_CLIENT_ID,
        client_secret=_CFG_SENTINEL_CLIENT_SECRET,
    )

    with pytest.raises(SchwabConfigMissingError) as excinfo:
        resolve_credentials_env_or_prompt(
            cfg, "production", allow_prompt=True,
        )
    msg = str(excinfo.value)
    # Mentions both env-var names (operator-actionable).
    assert "SCHWAB_CLIENT_ID" in msg
    assert "SCHWAB_CLIENT_SECRET" in msg
    # Raw env-var sentinel MUST NOT leak.
    assert _ENV_SENTINEL_CLIENT_ID not in msg


def test_cfg_sentinel_redacted_from_schwabdev_log_records(
    clear_credentials_env: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test 7 (brief §3 AC5) — cfg-sourced credentials NEVER appear in
    log records.

    Short hyphenated sentinels (16+ chars with hyphens) bypass Layer-1
    heuristic (`[A-Za-z]{24+}` for base64-like, hex 32+) — only Layer-0
    exact-replace registry catches them. This pins that the cfg-tier
    code path called `register_schwab_secrets` BEFORE returning, just
    like the env-tier path. If the cfg-tier wiring ever stops registering,
    this test fails.

    Threat-model split mirrors Sub-bundle A precedent in
    test_schwab_credential_env_vars.py: real-world Schwab credentials are
    long enough that Layer-1 would catch them, but the LOCK guarantee is
    the registry path, not the heuristic fallback.
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import (
        ensure_schwab_log_redaction_factory_installed,
    )

    cfg = _cfg_with(
        client_id=_CFG_SENTINEL_CLIENT_ID,
        client_secret=_CFG_SENTINEL_CLIENT_SECRET,
    )

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=False,
    )
    assert client_id == _CFG_SENTINEL_CLIENT_ID
    assert client_secret == _CFG_SENTINEL_CLIENT_SECRET

    # Emit a Schwabdev-named log record interpolating both sentinels; the
    # Layer-2 redaction factory MUST scrub them via the Layer-0 registry
    # registered by the cfg-tier code path.
    ensure_schwab_log_redaction_factory_installed()
    schwabdev_logger = logging.getLogger("Schwabdev.test_t_b_1_cfg")
    caplog.set_level(logging.DEBUG, logger="Schwabdev")
    schwabdev_logger.warning(
        "test record interpolating id=%s secret=%s",
        _CFG_SENTINEL_CLIENT_ID,
        _CFG_SENTINEL_CLIENT_SECRET,
    )
    captured = "\n".join(r.getMessage() for r in caplog.records)
    assert _CFG_SENTINEL_CLIENT_ID not in captured, (
        f"cfg client_id sentinel leaked into Schwabdev log records — "
        f"registry registration broken on cfg-tier path:\n{captured}"
    )
    assert _CFG_SENTINEL_CLIENT_SECRET not in captured, (
        f"cfg client_secret sentinel leaked into Schwabdev log records — "
        f"registry registration broken on cfg-tier path:\n{captured}"
    )


def test_cfg_whitespace_only_falls_through_to_prompt(
    clear_credentials_env: None,
) -> None:
    """Test 8 (helpful add — brief §3 'Additional helpful test') —
    whitespace-only cfg values treated as ABSENT-FOR-RESOLUTION.

    Mirrors env-tier empty-string handling. Prevents an accidental
    `client_id = "   "` in user-config.toml from short-circuiting to a
    non-usable value.
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt

    cfg = _cfg_with(client_id="   ", client_secret="\t\n  ")

    def _stub_prompter(label: str, *args: Any, **kwargs: Any) -> str:
        if "secret" in label.lower():
            return "prompted_secret_ws"
        return "prompted_id_ws"

    client_id, client_secret = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=True, prompter=_stub_prompter,
    )
    assert client_id == "prompted_id_ws"
    assert client_secret == "prompted_secret_ws"


def test_cfg_partial_with_allow_prompt_false_returns_none_pair(
    clear_credentials_env: None,
) -> None:
    """Test 9 (helpful add — brief §3 AC6 bullet 4) — pipeline path with
    partial cfg-tier returns (None, None).

    Env absent + cfg partial (id only) + allow_prompt=False → partial cfg
    falls through; with prompt disabled the lowest tier returns the None
    pair. Distinguishes "incomplete cfg-tier" (falls through) from "would
    raise" (which is env-tier-partial-only).
    """
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt

    cfg = _cfg_with(client_id=_CFG_SENTINEL_CLIENT_ID, client_secret="")

    def _no_prompt(*args: Any, **kwargs: Any) -> str:
        raise AssertionError(
            "prompter must NOT fire when allow_prompt=False",
        )

    result = resolve_credentials_env_or_prompt(
        cfg, "production", allow_prompt=False, prompter=_no_prompt,
    )
    assert result == (None, None)
