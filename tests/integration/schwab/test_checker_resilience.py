"""Slice 2 — P14.N7 resilient checker wrap + liveness (DNS-failure sim)."""
from __future__ import annotations

import importlib.metadata
import threading
import time

import pytest

from swing.integrations.schwab.checker_resilience import (
    CheckerLiveness,
    install_resilient_checker,
)


class _FakeTokens:
    def __init__(self, raises_n=0, access_token="acc", rotate=True):
        self._raises_left = raises_n
        self.access_token = access_token
        self._rotate = rotate          # whether a successful refresh ROTATES the token
        self._rot = 0
        self.calls = []

    def update_tokens(self, force_access_token=False, force_refresh_token=False):
        self.calls.append((force_access_token, force_refresh_token))
        if force_access_token or force_refresh_token:
            raise ConnectionError("forced path must propagate")
        if self._raises_left > 0:
            self._raises_left -= 1
            raise ConnectionError("Failed to resolve api.schwabapi.com")
        # A real successful refresh ROTATES the access token; a non-rotating
        # "success" simulates the schwabdev auth-fail-without-raise path (M5).
        if self._rotate:
            self._rot += 1
            self.access_token = f"acc{self._rot}"
        return True


class _FakeClient:
    def __init__(self, tokens):
        self.tokens = tokens


def _liveness(tmp_path):
    return CheckerLiveness(installed_ts=time.time(), sidecar_path=tmp_path / "lv.json")


def test_wrap_replaces_update_tokens(tmp_path):
    tokens = _FakeTokens()
    client = _FakeClient(tokens)
    original = client.tokens.update_tokens
    install_resilient_checker(client, liveness=_liveness(tmp_path))
    assert client.tokens.update_tokens is not original


def test_background_failure_is_isolated_then_recovers(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "swing.integrations.schwab.checker_resilience.time.sleep", sleeps.append,
    )
    tokens = _FakeTokens(raises_n=5)  # exceeds retries -> give up THIS cycle
    client = _FakeClient(tokens)
    lv = _liveness(tmp_path)
    install_resilient_checker(client, liveness=lv, retries=2, backoff_base_s=1.0)
    # daemon-origin call: simulate from a worker thread (not the startup thread)
    out = {}
    th = threading.Thread(target=lambda: out.setdefault("r", client.tokens.update_tokens()))
    th.start()
    th.join()
    assert out["r"] is False                       # gave up, did NOT raise
    assert lv.consecutive_failures > 0             # degraded
    assert sleeps == [1.0, 2.0]                    # bounded backoff 2^0, 2^1
    # next cycle succeeds -> alive
    th2 = threading.Thread(target=lambda: client.tokens.update_tokens())
    th2.start()
    th2.join()
    assert lv.consecutive_failures == 0            # recovered


def test_forced_call_propagates(tmp_path):
    tokens = _FakeTokens()
    client = _FakeClient(tokens)
    install_resilient_checker(client, liveness=_liveness(tmp_path))
    with pytest.raises(ConnectionError):
        client.tokens.update_tokens(force_access_token=True)


def test_seed_origin_does_not_advance_daemon_heartbeat(tmp_path):
    tokens = _FakeTokens()
    client = _FakeClient(tokens)
    lv = _liveness(tmp_path)
    install_resilient_checker(client, liveness=lv)  # installed on THIS (startup) thread
    client.tokens.update_tokens()                    # SEED (same thread) -> origin 'seed'
    assert lv.last_seed_ts is not None
    assert lv.last_daemon_tick_ts is None            # the seed must NOT look like a heartbeat


def test_schwabdev_version_guard_without_constructing_client():
    # OQ-4: NEVER construct a Client; assert via package metadata.
    assert importlib.metadata.version("schwabdev") == "2.5.1"


def test_refresh_without_rotation_is_degraded(tmp_path):
    # M5: update_tokens() can return True yet leave the OLD (stale) access
    # token in place (schwabdev logs the auth error without raising). The wrap
    # must record DEGRADED, not a false ALIVE.
    tokens = _FakeTokens(rotate=False)   # "success" that does NOT rotate the token
    client = _FakeClient(tokens)
    lv = _liveness(tmp_path)
    install_resilient_checker(client, liveness=lv)
    th = threading.Thread(target=lambda: client.tokens.update_tokens())  # daemon-origin
    th.start()
    th.join()
    assert lv.consecutive_failures > 0           # non-rotating refresh = degraded
    assert lv.last_error_class == "AuthRefreshNotRotated"
