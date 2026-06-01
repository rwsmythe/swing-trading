"""Slice 3 — shared liveness state machine (6-step precedence)."""
from __future__ import annotations

from swing.integrations.schwab.checker_resilience import (
    CLOCK_SKEW_TOLERANCE,
    HEARTBEAT_WRITE_INTERVAL,
    STALE_THRESHOLD,
    STARTUP_GRACE,
    evaluate_liveness_state,
)


def test_invariant_stale_exceeds_heartbeat():
    assert STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL


def test_absent_is_unknown():
    state, _ = evaluate_liveness_state(None, now_ts=1000.0)
    assert state == "UNKNOWN"


def test_explicit_failure_outranks_starting():
    data = {"installed_ts": 1000.0, "last_seed_ts": 1000.0,
            "consecutive_failures": 1, "last_error_class": "ConnectionError"}
    state, _ = evaluate_liveness_state(data, now_ts=1001.0)  # within grace, but failed
    assert state == "DEGRADED"


def test_alive_within_stale_threshold():
    data = {"installed_ts": 0.0, "last_daemon_tick_ts": 1000.0,
            "consecutive_failures": 0}
    state, _ = evaluate_liveness_state(data, now_ts=1000.0 + STALE_THRESHOLD - 1)
    assert state == "ALIVE"


def test_stale_daemon_tick_is_degraded():
    data = {"installed_ts": 0.0, "last_daemon_tick_ts": 1000.0,
            "consecutive_failures": 0}
    state, reason = evaluate_liveness_state(data, now_ts=1000.0 + STALE_THRESHOLD + 1)
    assert state == "DEGRADED" and "stale" in reason


def test_future_heartbeat_beyond_skew_is_degraded_not_alive():
    # A finite but future heartbeat (clock skew / corrupted sidecar) must NOT
    # report a false ALIVE via a large negative age. Pre-fix this returned ALIVE
    # because now_ts - last_tick = -9000 <= STALE_THRESHOLD.
    data = {"installed_ts": 0.0, "last_daemon_tick_ts": 10000.0,
            "consecutive_failures": 0}
    state, reason = evaluate_liveness_state(data, now_ts=1000.0)
    assert state == "DEGRADED"
    assert "future" in reason and reason.isascii()


def test_small_future_skew_within_tolerance_stays_alive():
    # A heartbeat slightly in the future (within CLOCK_SKEW_TOLERANCE) is benign.
    data = {"installed_ts": 0.0,
            "last_daemon_tick_ts": 1000.0 + CLOCK_SKEW_TOLERANCE - 1,
            "consecutive_failures": 0}
    state, _ = evaluate_liveness_state(data, now_ts=1000.0)
    assert state == "ALIVE"


def test_seed_only_within_grace_is_starting():
    data = {"installed_ts": 1000.0, "last_seed_ts": 1000.0, "consecutive_failures": 0}
    state, _ = evaluate_liveness_state(data, now_ts=1000.0 + STARTUP_GRACE - 1)
    assert state == "STARTING"


def test_seed_only_past_grace_expires_to_degraded():
    data = {"installed_ts": 1000.0, "last_seed_ts": 1000.0, "consecutive_failures": 0}
    state, reason = evaluate_liveness_state(data, now_ts=1000.0 + STARTUP_GRACE + 1)
    assert state == "DEGRADED" and "no daemon heartbeat" in reason


def test_non_dict_sidecar_does_not_crash_reader(tmp_path):
    # valid-but-non-object JSON must not crash the consumers.
    from swing.integrations.schwab.checker_resilience import read_liveness_sidecar
    for bad in ("[]", '"bad"', "42"):
        p = tmp_path / f"lv_{abs(hash(bad))}.json"
        p.write_text(bad, encoding="ascii")
        assert read_liveness_sidecar(p) is None        # -> caller renders UNKNOWN
        # and the state machine tolerates the None it gets back
        assert evaluate_liveness_state(read_liveness_sidecar(p), now_ts=1.0)[0] == "UNKNOWN"


def test_typed_garbage_fields_do_not_crash_state_machine():
    # non-numeric AND non-finite typed fields must NOT raise (no TypeError/
    # OverflowError; no ALIVE-forever via inf). An escaped-unicode
    # last_error_class must not leak non-ASCII.
    for data in (
        {"consecutive_failures": "x"},
        {"last_daemon_tick_ts": "bad"},
        {"installed_ts": "bad", "last_seed_ts": None},
        {"last_refresh_ts": "bad", "last_daemon_tick_ts": 0.0},
        {"consecutive_failures": float("nan")},
        {"last_daemon_tick_ts": float("inf")},      # must NOT report ALIVE-forever
        {"last_refresh_ts": float("inf"), "last_daemon_tick_ts": 1000.0},
        {"consecutive_failures": 1, "last_error_class": "☃"},  # non-ASCII escape
    ):
        state, reason = evaluate_liveness_state(data, now_ts=1000.0)
        assert state in {"ALIVE", "STARTING", "DEGRADED", "UNKNOWN"}
        assert reason.isascii()
    # inf daemon tick must NOT be treated as a fresh heartbeat
    s, _ = evaluate_liveness_state({"last_daemon_tick_ts": float("inf")}, now_ts=1000.0)
    assert s != "ALIVE"


def test_all_reasons_ascii():
    for data, now in [
        (None, 0.0),
        ({"installed_ts": 0.0, "consecutive_failures": 2, "last_error_class": "X"}, 1.0),
        ({"installed_ts": 0.0, "last_daemon_tick_ts": 0.0, "consecutive_failures": 0}, 1.0),
    ]:
        _state, reason = evaluate_liveness_state(data, now_ts=now)
        assert reason.isascii()
