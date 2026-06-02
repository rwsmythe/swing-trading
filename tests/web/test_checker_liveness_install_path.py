"""F-1 production-path test: the REAL install+wrap+seed path writes a STARTING
liveness sidecar (NOT a hand-seeded one). Corrects the SB5.5 seeded-gate miss
(feedback_seeded_gate_masks_default_state)."""
from __future__ import annotations

import logging
import threading
import time

import swing.web.app as web_app
from swing.integrations.schwab import checker_resilience as cr


class _FakeTokens:
    def __init__(self) -> None:
        self.access_token = "fake-access-token-not-a-secret"
        self.update_tokens_calls = 0

    def update_tokens(self, force_access_token=False, force_refresh_token=False):
        self.update_tokens_calls += 1
        return False  # no rotation needed (healthy token)


class _FakeClient:
    def __init__(self) -> None:
        self.tokens = _FakeTokens()


class _DummyCache:
    """Stand-in OHLCV/price cache: the only methods touched by the install path
    (after the STARTING write) are the ladder-fetcher setters."""

    def set_ladder_fetcher(self, fn) -> None:
        self._ladder_fetcher = fn

    def set_ladder_bars_fetcher(self, fn) -> None:
        self._ladder_bars_fetcher = fn


class _Cfg:
    class integrations:
        class schwab:
            environment = "production"
            marketdata_ladder_enabled = True

    class paths:
        db_path = ":memory:"

    class web:
        circuit_breaker_cooldown_seconds = 60.0


def test_install_writes_starting_sidecar_via_real_seed_path(tmp_path, monkeypatch):
    sidecar = tmp_path / "schwab-checker-liveness.production.json"
    # Point the checker module's path helper at tmp so the install path writes
    # there (no real ~/swing-data touch).
    monkeypatch.setattr(
        cr, "checker_liveness_sidecar_path", lambda env: sidecar,
    )
    # Force construction to succeed with the fake client (bypass real Schwab).
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", lambda cfg: _FakeClient(),
    )

    client = web_app._install_web_marketdata_caches(
        _Cfg(), _DummyCache(), _DummyCache(),
    )

    assert client is not None
    assert sidecar.exists()  # the REAL seed wiring wrote it -- NOT hand-seeded
    data = cr.read_liveness_sidecar(sidecar)
    assert data is not None
    state, _reason = cr.evaluate_liveness_state(data, now_ts=time.time())
    assert state == "STARTING"


def test_daemon_origin_tick_advances_to_alive(tmp_path, monkeypatch):
    sidecar = tmp_path / "schwab-checker-liveness.production.json"
    monkeypatch.setattr(
        cr, "checker_liveness_sidecar_path", lambda env: sidecar,
    )
    fake = _FakeClient()
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", lambda cfg: fake,
    )

    web_app._install_web_marketdata_caches(_Cfg(), _DummyCache(), _DummyCache())

    # Simulate a daemon tick from a NON-startup thread (origin='daemon').
    def _daemon_tick():
        fake.tokens.update_tokens()  # wrapped -> origin='daemon' -> record_tick

    t = threading.Thread(target=_daemon_tick)
    t.start()
    t.join(timeout=5)

    data = cr.read_liveness_sidecar(sidecar)
    assert data is not None
    state, _reason = cr.evaluate_liveness_state(data, now_ts=time.time())
    assert state == "ALIVE"


def test_stale_sidecar_with_failed_write_reports_readback_false(
    tmp_path, monkeypatch, caplog,
):
    """Codex R1 Major (DISCRIMINATING): when THIS install's STARTING write fails
    silently but a STALE sidecar from a prior run is already present, the
    install-summary readback MUST report False (and a WARNING fire) -- a bare
    `is not None` readback would falsely pass (reading the stale sidecar) and
    mask Class B. The install-identity check (installed_ts match) catches it."""
    sidecar = tmp_path / "schwab-checker-liveness.production.json"
    monkeypatch.setattr(
        cr, "checker_liveness_sidecar_path", lambda env: sidecar,
    )
    # Pre-populate a STALE sidecar from a prior run (distinct installed_ts).
    stale = cr.CheckerLiveness(installed_ts=1.0, sidecar_path=sidecar)
    cr.write_liveness_sidecar(stale, sidecar)
    assert sidecar.exists()

    # Force THIS install's STARTING write to fail silently (the debug-only
    # swallow in CheckerLiveness._write_sidecar): the stale sidecar remains.
    def _boom(record, path):
        raise OSError("synthetic sidecar write failure")

    monkeypatch.setattr(cr, "write_liveness_sidecar", _boom)
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", lambda cfg: _FakeClient(),
    )

    with caplog.at_level(logging.INFO, logger="swing.web.app"):
        web_app._install_web_marketdata_caches(_Cfg(), _DummyCache(), _DummyCache())

    # The summary reports readback FALSE (stale sidecar did NOT mask the failure).
    assert any(
        "starting_write_readback=False" in r.getMessage() for r in caplog.records
    ), "install summary must report readback False for a stale/failed write"
    # And the WARNING fired.
    assert any(
        r.levelno == logging.WARNING and "readback FAILED" in r.getMessage()
        for r in caplog.records
    ), "expected a WARNING that the readback failed"
