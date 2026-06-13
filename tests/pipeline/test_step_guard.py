"""Unit tests for swing.pipeline.step_guard -- the best-effort step wrapper."""
from __future__ import annotations

import logging

import pytest

from swing.data.repos.pipeline import LeaseRevokedError
from swing.pipeline.step_guard import step_guard


class FakeLease:
    def __init__(self):
        self.steps: list[str] = []
        self.statuses: dict[str, str] = {}

    def step(self, name: str) -> None:
        self.steps.append(name)

    def status(self, **cols: str) -> None:
        self.statuses.update(cols)


def test_enter_fires_lease_step_before_body():
    lease = FakeLease()
    seen_at_body = None
    with step_guard(lease, "weather", status_key="weather_status",
                    logger=logging.getLogger("t")):
        seen_at_body = list(lease.steps)
    assert seen_at_body == ["weather"]          # breadcrumb fired on __enter__
    assert lease.statuses == {"weather_status": "ok"}


def test_clean_exit_no_status_key_sets_nothing():
    lease = FakeLease()
    with step_guard(lease, "pattern_detect", logger=logging.getLogger("t")):
        pass
    assert lease.steps == ["pattern_detect"]
    assert lease.statuses == {}                 # B site: no status surface


def test_lease_revoked_propagates():
    lease = FakeLease()
    with (
        pytest.raises(LeaseRevokedError),
        step_guard(lease, "weather", status_key="weather_status",
                   logger=logging.getLogger("t")),
    ):
        raise LeaseRevokedError("revoked")
    assert lease.statuses == {}                 # no "ok", no "failed" on revoke


def test_other_exception_swallowed_status_failed(caplog):
    lease = FakeLease()
    log = logging.getLogger("swing.pipeline.runner")
    with (
        caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"),
        step_guard(lease, "watchlist", status_key="watchlist_status", logger=log),
    ):
        raise RuntimeError("boom")
    assert lease.statuses == {"watchlist_status": "failed"}
    assert "watchlist failed: boom" in caplog.text
    assert caplog.records[0].name == "swing.pipeline.runner"   # LOCK #5 logger name


def test_other_exception_swallowed_no_status_key(caplog):
    lease = FakeLease()
    log = logging.getLogger("swing.pipeline.runner")
    with (
        caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"),
        step_guard(lease, "pattern_detect", logger=log),
    ):
        raise RuntimeError("boom")
    assert lease.statuses == {}                 # B site: no status flip on failure
    assert "pattern_detect failed: boom" in caplog.text


def test_exception_from_ok_status_write_is_caught_not_propagated(caplog):
    """Byte-identical to the inline sites: the success ``lease.status(ok)`` is
    INSIDE the guarded try, so if it raises a non-revoke Exception the guard
    logs + writes 'failed' + swallows (does NOT propagate). (Codex R1 #1.)"""
    class OkRaisesLease(FakeLease):
        def status(self, **cols: str) -> None:
            if cols.get("weather_status") == "ok":
                raise RuntimeError("ok-write boom")
            super().status(**cols)

    lease = OkRaisesLease()
    log = logging.getLogger("swing.pipeline.runner")
    with (
        caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"),
        step_guard(lease, "weather", status_key="weather_status", logger=log),
    ):
        pass  # clean body; the failure comes from the ok-status write
    assert lease.statuses == {"weather_status": "failed"}
    assert "weather failed: ok-write boom" in caplog.text


def test_custom_log_failure_callable_preserves_exact_text():
    lease = FakeLease()
    captured = []
    with step_guard(
        lease, "schwab_snapshot",
        logger=logging.getLogger("t"),
        log_failure=lambda lg, name, exc: captured.append(
            f"{name} failed (continuing pipeline): {type(exc).__name__}"),
    ):
        raise KeyError("x")
    assert captured == ["schwab_snapshot failed (continuing pipeline): KeyError"]
    assert lease.statuses == {}
