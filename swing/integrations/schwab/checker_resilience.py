"""P14.N7 -- resilient wrap for the schwabdev background checker thread.

schwabdev's Client spawns a daemon checker that calls
``self.tokens.update_tokens()`` every 30s; an uncaught ConnectionError
(e.g. DNS loss after laptop sleep) kills that thread and silently degrades
token refresh until ``swing web`` restarts. This module wraps the bound
``update_tokens`` on a SINGLE client instance so the loop survives, records
a liveness signal, and surfaces it via an ephemeral sidecar.

Cleanly removable: the Phase-15 schwabdev v3 upgrade deletes the checker and
this module with it. Validated against schwabdev 2.5.1
(``client.py:50-56`` + ``tokens.py:160-198``).
"""
from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from swing.config_user import _user_home
from swing.integrations.schwab.auth import _redacted_excerpt

log = logging.getLogger(__name__)

# Timing constants (invariant: STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL;
# STARTUP_GRACE >= one 30s checker cadence + margin).
HEARTBEAT_WRITE_INTERVAL = 120.0   # write the sidecar every ~4th daemon tick
STALE_THRESHOLD = 300.0            # CLI/badge report DEGRADED past this
STARTUP_GRACE = 90.0              # STARTING expires to DEGRADED past this
CLOCK_SKEW_TOLERANCE = 5.0         # a heartbeat further in the future than this = corrupted/skewed
_HEARTBEAT_TICKS = 4               # 4 * 30s ~ HEARTBEAT_WRITE_INTERVAL


@dataclass
class CheckerLiveness:
    installed_ts: float
    sidecar_path: Path
    last_daemon_tick_ts: float | None = None
    last_seed_ts: float | None = None
    last_success_ts: float | None = None
    last_refresh_ts: float | None = None
    consecutive_failures: int = 0
    last_error_class: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _daemon_tick_count: int = field(default=0, repr=False)

    def record_tick(self, origin: str) -> None:
        with self._lock:
            if origin == "daemon":
                first = self.last_daemon_tick_ts is None
                self.last_daemon_tick_ts = time.time()
                self._daemon_tick_count += 1
                write = first or (self._daemon_tick_count % _HEARTBEAT_TICKS == 0)
            else:  # 'seed'
                self.last_seed_ts = time.time()
                write = True
        if write:
            self._write_sidecar()

    def record_failure(self, exc: BaseException) -> None:
        with self._lock:
            self.consecutive_failures += 1
            self.last_error_class = type(exc).__name__
        log.warning(
            "Schwab checker refresh failed (%s: %s); loop continues.",
            type(exc).__name__, _redacted_excerpt(exc),
        )
        self._write_sidecar()  # transition -> persist

    def record_success(self, *, refreshed: bool, access_present: bool, rotated: bool) -> None:
        with self._lock:
            had_failures = self.consecutive_failures > 0
            if refreshed and (not access_present or not rotated):
                # update_tokens() returns True after update_access_token(), but
                # update_access_token() LOGS errors on a non-OK response without
                # raising or clearing the OLD token (schwabdev 2.5.1
                # tokens.py:193-218, Major #5). So a claimed refresh that did
                # NOT actually rotate the access token (or left it empty) is a
                # DEGRADED auth failure, not a healthy refresh.
                self.consecutive_failures += 1
                self.last_error_class = "AuthRefreshNotRotated"
                transition = True
            else:
                self.consecutive_failures = 0
                self.last_error_class = None
                self.last_success_ts = time.time()
                if refreshed:
                    self.last_refresh_ts = time.time()
                # Persist on a transition OUT of failure OR whenever a real
                # rotation happened: otherwise last_refresh_ts updates in memory
                # but the sidecar only catches up at the next heartbeat, so the
                # ALIVE line could briefly say "no rotation yet".
                transition = had_failures or refreshed
        if transition:
            self._write_sidecar()

    def _write_sidecar(self) -> None:
        try:
            write_liveness_sidecar(self, self.sidecar_path)
        except Exception:  # noqa: BLE001 -- never let sidecar IO kill the daemon
            log.debug("checker liveness sidecar write skipped", exc_info=True)


def _access_token(client: object) -> object | None:
    return getattr(getattr(client, "tokens", None), "access_token", None)


def install_resilient_checker(
    client: object, *, liveness: CheckerLiveness,
    retries: int = 2, backoff_base_s: float = 1.0,
) -> None:
    """Replace ``client.tokens.update_tokens`` with the resilient wrapper."""
    original = client.tokens.update_tokens
    startup_thread = threading.current_thread()

    def resilient_update_tokens(force_access_token=False, force_refresh_token=False):
        if force_access_token or force_refresh_token:
            return original(
                force_access_token=force_access_token,
                force_refresh_token=force_refresh_token,
            )
        origin = "seed" if threading.current_thread() is startup_thread else "daemon"
        liveness.record_tick(origin)
        attempt = 0
        while True:
            before_token = _access_token(client)
            try:
                refreshed = original()
            except Exception as exc:  # noqa: BLE001
                liveness.record_failure(exc)
                if attempt < retries:
                    attempt += 1
                    time.sleep(backoff_base_s * (2 ** (attempt - 1)))
                    continue
                return False
            after_token = _access_token(client)
            liveness.record_success(
                refreshed=bool(refreshed),
                access_present=bool(after_token),
                rotated=(after_token != before_token),  # Major #5: verify ACTUAL rotation
            )
            return refreshed

    client.tokens.update_tokens = resilient_update_tokens


def checker_liveness_sidecar_path(env: str) -> Path:
    return _user_home() / "swing-data" / f"schwab-checker-liveness.{env}.json"


def write_liveness_sidecar(record: CheckerLiveness, path: Path) -> None:
    payload = {
        "installed_ts": record.installed_ts,
        "last_daemon_tick_ts": record.last_daemon_tick_ts,
        "last_seed_ts": record.last_seed_ts,
        "last_success_ts": record.last_success_ts,
        "last_refresh_ts": record.last_refresh_ts,
        "consecutive_failures": record.consecutive_failures,
        "last_error_class": record.last_error_class,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)  # atomic; same filesystem (dest dir) -> Windows-safe
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def read_liveness_sidecar(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="ascii") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    # valid-but-non-object JSON ([] / "bad" / 42) must NOT crash the CLI or the
    # web badge (both call data.get(...)). Treat anything that is not a dict as
    # "no usable sidecar" -> caller renders UNKNOWN.
    if not isinstance(payload, dict):
        return None
    return payload


def _num(data: dict, key: str) -> float | None:
    """Coerce a sidecar field to a FINITE float, or None if absent / non-numeric
    / bool / non-finite -- a corrupted ephemeral sidecar must NOT crash the CLI
    or the web badge: a non-numeric type would raise a TypeError, and
    ``json.load`` parses ``NaN``/``Infinity``/``-Infinity`` which would crash
    ``int(...)`` with OverflowError OR report ALIVE forever via ``now_ts - inf``.
    ``math.isfinite`` rejects the non-finite cases."""
    v = data.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    if not math.isfinite(f):
        return None
    return f


def _ascii_safe(text: object) -> str:
    """ASCII-only coercion for sidecar text interpolated into a reason -- an
    ASCII-encoded sidecar can still carry escaped-unicode like \\u2603."""
    return str(text).encode("ascii", "replace").decode("ascii")


def evaluate_liveness_state(data: dict | None, *, now_ts: float) -> tuple[str, str]:
    """The ONE state machine (consumed by render_status AND the web badge).

    Precedence (explicit failure outranks STARTING):
      1 absent -> UNKNOWN | 2 failure -> DEGRADED | 3 fresh daemon tick -> ALIVE
      4 stale daemon tick -> DEGRADED | 5 seed-only within grace -> STARTING
      6 seed-only past grace -> DEGRADED.
    All numeric fields are coerced via _num so a type-corrupted sidecar cannot
    raise.
    """
    if data is None:
        return ("UNKNOWN", "web server not running, or pre-N7 build")
    failures_num = _num(data, "consecutive_failures")
    failures = int(failures_num) if failures_num is not None else 0
    if failures > 0 or data.get("last_error_class"):
        cls = _ascii_safe(data.get("last_error_class") or "refresh failure")
        return ("DEGRADED", f"{failures} consecutive failures ({cls})")
    last_tick = _num(data, "last_daemon_tick_ts")
    if last_tick is not None:
        age = now_ts - last_tick
        if age < -CLOCK_SKEW_TOLERANCE:
            # A finite heartbeat further in the future than the skew tolerance is
            # a corrupted/clock-skewed sidecar -- never report a false ALIVE.
            return ("DEGRADED", "heartbeat timestamp in the future (clock skew)")
        if age <= STALE_THRESHOLD:
            refresh_ts = _num(data, "last_refresh_ts")
            if refresh_ts is not None:
                refresh_txt = f"last refresh {int(now_ts - refresh_ts)}s ago"
            else:
                refresh_txt = "no rotation needed yet"
            return ("ALIVE", f"{refresh_txt}; {failures} consecutive failures")
        return ("DEGRADED", "stale heartbeat")
    anchor = _num(data, "last_seed_ts")
    if anchor is None:
        anchor = _num(data, "installed_ts") or 0.0
    if now_ts - anchor < STARTUP_GRACE:
        return ("STARTING", "awaiting first daemon heartbeat")
    return ("DEGRADED", "no daemon heartbeat since startup")
