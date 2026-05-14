"""Schwab sub-package skeleton (T-A.3) — exception hierarchy + SchwabClient
__init__ + transport-debug-log suppression context manager.

Covers plan §A.2 + §H.3 + recon doc §2.2 lazy-construction binding.

Key contracts under test:
  * Each exception's `__str__` MUST NOT echo URL bytes (account_hash segments)
    or response body bytes. Discriminating sentinel per class.
  * `SchwabClient.__init__` resolves per-env tokens DB path via `_user_home()`;
    USERPROFILE+HOME monkeypatch required per CLAUDE.md gotcha.
  * `_suppress_transport_debug_logs` mutes every configured logger name to
    WARNING for the duration; pre-context levels restored on exit.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.config import Config, load
from tests.web.test_config_web import _write_cfg  # reuse helper


# ---------- Fixtures ----------

@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate USERPROFILE + HOME so SchwabClient.__init__ resolves to tmp,
    not the operator's real path.

    Per CLAUDE.md gotcha: tests touching `_user_home()` MUST monkeypatch BOTH
    env vars; `_user_home()` in swing/config.py + swing/config_user.py reads
    them directly. Forgetting one leaks to operator's real ~/swing-data/.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def base_cfg(tmp_path: Path, tmp_home: Path) -> Config:
    """Build a minimal Config from a swing.config.toml including the tracked
    [integrations.schwab] section."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    extra = """
[integrations.schwab]
timeout_seconds = 30.0
marketdata_ladder_enabled = true
"""
    cfg_path = _write_cfg(project_dir, tmp_home, extra=extra)
    return load(cfg_path)


@pytest.fixture
def mem_conn() -> sqlite3.Connection:
    """In-memory sqlite connection — SchwabClient.__init__ stores it for
    audit-row writes in later tasks (T-A.8+); T-A.3 just receives it."""
    return sqlite3.connect(":memory:")


# ---------- (1-8) Exception __str__ redaction discriminating tests ----------

# Per task brief: each exception instantiated with an account_hash-bearing
# sample arg; assert `str(exc)` does NOT contain the hash. Unique sentinels.

def test_schwab_config_missing_error_does_not_leak_account_hash() -> None:
    from swing.integrations.schwab import SchwabConfigMissingError

    sentinel = "EXCSENT_CFGMISSING_HASH_A1B2C3D4"
    exc = SchwabConfigMissingError(
        f"environment missing; tried URL https://api.schwabapi.com/trader/v1/"
        f"accounts/{sentinel}/details"
    )
    rendered = str(exc)
    assert sentinel not in rendered


def test_schwab_api_error_does_not_leak_account_hash() -> None:
    from swing.integrations.schwab import SchwabApiError

    sentinel = "EXCSENT_APIERROR_HASH_E5F6G7H8"
    body = (
        f'{{"errors":[{{"detail":"refresh failed for accountHash={sentinel}"}}]}}'
    )
    exc = SchwabApiError(500, body)
    rendered = str(exc)
    assert sentinel not in rendered
    # Defense-in-depth: rendered form names the status + body size only.
    assert "500" in rendered
    assert "bytes" in rendered


def test_schwab_rate_limit_error_does_not_leak_account_hash() -> None:
    from swing.integrations.schwab import SchwabRateLimitError

    sentinel = "EXCSENT_RATELIMIT_HASH_I9J0K1L2"
    body = f"Rate limited at accountHash={sentinel}"
    exc = SchwabRateLimitError(429, body)
    rendered = str(exc)
    assert sentinel not in rendered
    assert "429" in rendered


def test_schwab_auth_error_does_not_leak_account_hash() -> None:
    from swing.integrations.schwab import SchwabAuthError

    sentinel = "EXCSENT_AUTH_HASH_M3N4O5P6"
    body = f'{{"error":"invalid_token","accountHash":"{sentinel}"}}'
    exc = SchwabAuthError(401, body)
    rendered = str(exc)
    assert sentinel not in rendered
    assert "401" in rendered


def test_schwab_refresh_token_expired_error_does_not_leak_account_hash() -> None:
    from swing.integrations.schwab import SchwabRefreshTokenExpiredError

    sentinel = "EXCSENT_REFRESHEXPIRED_HASH_Q7R8S9T0"
    body = (
        f'{{"error":"unsupported_token_type","accountHash":"{sentinel}"}}'
    )
    exc = SchwabRefreshTokenExpiredError(401, body)
    rendered = str(exc)
    assert sentinel not in rendered


def test_schwab_schema_parity_error_does_not_leak_account_hash() -> None:
    from swing.integrations.schwab import SchwabSchemaParityError

    sentinel = "EXCSENT_SCHEMAPARITY_HASH_U1V2W3X4"
    exc = SchwabSchemaParityError(
        f"unexpected response shape from /accounts/{sentinel}: missing 'cash'"
    )
    rendered = str(exc)
    assert sentinel not in rendered


def test_schwab_concurrent_refresh_error_does_not_leak_account_hash() -> None:
    from swing.integrations.schwab import SchwabConcurrentRefreshError

    sentinel = "EXCSENT_CONCURRENT_HASH_Y5Z6A7B8"
    body = f"concurrent refresh blocked on accountHash={sentinel}"
    exc = SchwabConcurrentRefreshError(409, body)
    rendered = str(exc)
    assert sentinel not in rendered


def test_schwab_pipeline_active_error_does_not_leak_account_hash() -> None:
    from swing.integrations.schwab import SchwabPipelineActiveError

    sentinel = "EXCSENT_PIPELINEACTIVE_HASH_C9D0E1F2"
    exc = SchwabPipelineActiveError(
        f"pipeline run is in flight; refusing operation on /{sentinel}"
    )
    rendered = str(exc)
    assert sentinel not in rendered


# ---------- (9-10) SchwabClient.__init__ tokens DB path resolution ----------

def test_schwab_client_init_production_env_tokens_db_path(
    base_cfg: Config, tmp_home: Path, mem_conn: sqlite3.Connection,
) -> None:
    """Production env resolves to ~/swing-data/schwab-tokens.production.db."""
    from swing.integrations.schwab import SchwabClient

    client = SchwabClient(base_cfg, "production", mem_conn)
    expected = tmp_home / "swing-data" / "schwab-tokens.production.db"
    assert client._tokens_db_path == expected


def test_schwab_client_init_sandbox_env_tokens_db_path(
    base_cfg: Config, tmp_home: Path, mem_conn: sqlite3.Connection,
) -> None:
    """Sandbox env resolves to ~/swing-data/schwab-tokens.sandbox.db (distinct
    file from production — V1 separation per plan §F.1)."""
    from swing.integrations.schwab import SchwabClient

    client = SchwabClient(base_cfg, "sandbox", mem_conn)
    expected = tmp_home / "swing-data" / "schwab-tokens.sandbox.db"
    assert client._tokens_db_path == expected


# ---------- (11) Invalid environment ----------

def test_schwab_client_init_rejects_invalid_environment(
    base_cfg: Config, tmp_home: Path, mem_conn: sqlite3.Connection,
) -> None:
    """environment must be 'sandbox' or 'production'; anything else raises
    SchwabConfigMissingError."""
    from swing.integrations.schwab import (
        SchwabClient,
        SchwabConfigMissingError,
    )

    with pytest.raises(SchwabConfigMissingError):
        SchwabClient(base_cfg, "invalid", mem_conn)


def test_schwab_client_init_does_not_construct_schwabdev_client(
    base_cfg: Config, tmp_home: Path, mem_conn: sqlite3.Connection,
) -> None:
    """Per recon doc §2.2 + plan §H.3: SchwabClient.__init__ MUST NOT trigger
    schwabdev.Client construction (which would block on stdin OAuth paste-back
    when no tokens DB exists). Lazy-construction defers to first API method
    call. T-A.3 ships the hook; T-A.4/T-A.5 fill in the call paths."""
    from swing.integrations.schwab import SchwabClient

    client = SchwabClient(base_cfg, "production", mem_conn)
    assert client._schwabdev_client is None


# ---------- (12) _suppress_transport_debug_logs mutes loggers ----------

def test_suppress_transport_debug_logs_mutes_all_configured_loggers() -> None:
    """Verify every logger named in _TRANSPORT_DEBUG_LOGGERS is forced to
    WARNING for the duration of the context, then restored to its pre-context
    level on exit."""
    from swing.integrations.schwab.client import (
        _TRANSPORT_DEBUG_LOGGERS,
        _suppress_transport_debug_logs,
    )

    # Plant DEBUG on every targeted logger so we can detect the bump-then-restore.
    for name in _TRANSPORT_DEBUG_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG)

    try:
        with _suppress_transport_debug_logs():
            for name in _TRANSPORT_DEBUG_LOGGERS:
                assert logging.getLogger(name).level == logging.WARNING, (
                    f"logger {name!r} not muted inside context"
                )
        # After exit, every logger restored to DEBUG.
        for name in _TRANSPORT_DEBUG_LOGGERS:
            assert logging.getLogger(name).level == logging.DEBUG, (
                f"logger {name!r} not restored to DEBUG after context exit"
            )
    finally:
        # Best-effort cleanup so we don't leave DEBUG levels set for other tests.
        for name in _TRANSPORT_DEBUG_LOGGERS:
            logging.getLogger(name).setLevel(logging.NOTSET)


# ---------- (13) __init__.py re-exports + transport-logger count smoke ----------

def test_subpackage_reexports_all_public_names() -> None:
    """All 9 public names (SchwabClient + 8 exceptions) importable from the
    package root via `from swing.integrations.schwab import X`."""
    from swing.integrations import schwab as pkg

    expected_names = {
        "SchwabClient",
        "SchwabConfigMissingError",
        "SchwabApiError",
        "SchwabRateLimitError",
        "SchwabAuthError",
        "SchwabRefreshTokenExpiredError",
        "SchwabSchemaParityError",
        "SchwabConcurrentRefreshError",
        "SchwabPipelineActiveError",
    }
    for name in expected_names:
        assert hasattr(pkg, name), f"swing.integrations.schwab missing {name}"
    assert set(pkg.__all__) == expected_names


def test_transport_debug_loggers_includes_urllib3_and_schwabdev() -> None:
    """Spot-check that the muted-logger tuple at least covers urllib3
    (transport) and Schwabdev (library-internal). Defense-in-depth against
    a future refactor accidentally dropping one of the two families.

    Note: plan §Tasks-A T-A.3 enumerated '5 logger names' as a target; actual
    count derived from `pip show schwabdev` source inspection (T-A.0.b recon
    §2 confirms schwabdev only ships ONE logger `Schwabdev` shared across
    Client/Tokens/Stream). Banked deviation in return report.
    """
    from swing.integrations.schwab.client import _TRANSPORT_DEBUG_LOGGERS

    assert "urllib3.connectionpool" in _TRANSPORT_DEBUG_LOGGERS
    assert "Schwabdev" in _TRANSPORT_DEBUG_LOGGERS
