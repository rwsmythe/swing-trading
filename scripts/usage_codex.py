"""Read the Codex subscription's weekly rate-limit window (stdlib only).

Spawns the NATIVE Codex executable's ``app-server`` (never the npm ``codex.cmd``
shim, which hangs under pipes) and runs three JSON-RPC calls over stdio:
``initialize`` -> ``initialized`` -> ``account/rateLimits/read``. Prints one JSON
object::

    {"lane": "codex", "used_percent": 22, "window_mins": 10080,
     "resets_at": "2026-11-01T13:23:00Z", "elapsed_fraction": 0.22,
     "pace": 1.0, "read_at": "..."}

``pace`` is the projected end-of-window utilization as a multiple of the
allotment (``used_percent / 100 / elapsed_fraction``); the dispatch tiebreak
compares the two lanes' pace, never their raw percent (the windows reset at
different times). A missing or unreadable figure prints ``{"lane": "codex",
"error": "..."}`` and exits 1; the caller treats that as "no reading".

Usage: ``python scripts/usage_codex.py [--exe PATH] [--timeout SECONDS]``.
The executable defaults to the npm-installed Windows binary; set ``--exe`` on
another substrate. ``pace_from`` is the pure function the harness test covers.
Ported 2026-11-11 from harness-template 4335ff6 (the Codex-lane arc, P2).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Any

DEFAULT_EXE = os.path.join(
    os.environ.get("APPDATA", ""),
    "npm",
    "node_modules",
    "@openai",
    "codex",
    "node_modules",
    "@openai",
    "codex-win32-x64",
    "vendor",
    "x86_64-pc-windows-msvc",
    "bin",
    "codex.exe",
)


def pace_from(
    used_percent: float, window_mins: float, resets_at_epoch: float, now_epoch: float
) -> dict[str, Any]:
    """Return the elapsed fraction and pace for one lane's window.

    ``elapsed_fraction`` is clamped to [1e-6, 1]; ``pace`` is the used share
    divided by the elapsed share, so 1.0 means "on track to use exactly the
    allotment by the reset".
    """
    window_s = max(window_mins, 1.0) * 60.0
    remaining = max(0.0, min(window_s, resets_at_epoch - now_epoch))
    elapsed = max(1e-6, min(1.0, 1.0 - remaining / window_s))
    return {
        "elapsed_fraction": round(elapsed, 6),
        "pace": round((used_percent / 100.0) / elapsed, 3),
    }


def read_rate_limits(exe: str, timeout: float) -> dict[str, Any]:
    """Run the three JSON-RPC calls and return the ``account/rateLimits/read`` result."""
    proc = subprocess.Popen(
        [exe, "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    lines: queue.Queue[str] = queue.Queue()

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)

    threading.Thread(target=pump, daemon=True).start()

    def send(obj: dict[str, Any]) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "harness-usage", "title": "harness", "version": "0.1"},
                    "capabilities": {},
                },
            }
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = lines.get(timeout=1)
            except queue.Empty:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == 1:
                send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
                send({"jsonrpc": "2.0", "id": 2, "method": "account/rateLimits/read", "params": {}})
            elif msg.get("id") == 2:
                if "error" in msg:
                    raise RuntimeError(str(msg["error"]))
                result: dict[str, Any] = msg["result"]
                return result
        raise TimeoutError(f"no rateLimits response within {timeout:.0f} s")
    finally:
        proc.kill()


def main(argv: list[str] | None = None) -> int:
    """Command-line entry: print the lane reading as one JSON line."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args(argv)
    now = time.time()
    try:
        result = read_rate_limits(args.exe, args.timeout)
        limits = result["rateLimits"]
        # The weekly window is the one whose duration is 7 days; the app-server may report it
        # as primary or secondary (the other is the 5-hour window). With no weekly window the
        # weekly budget is UNKNOWN: an error reading, never the 5-hour figure (Codex R1-7,
        # CHARC N2 routes an unknown budget to the other lane).
        windows = [limits[k] for k in ("primary", "secondary") if isinstance(limits.get(k), dict)]
        weekly = [w for w in windows if float(w.get("windowDurationMins", 0)) == 10080]
        if not weekly:
            raise ValueError("no 10080-minute (weekly) window in rateLimits")
        primary = weekly[0]
        used = float(primary["usedPercent"])
        window = float(primary["windowDurationMins"])
        resets = float(primary["resetsAt"])
        # The reading is built INSIDE the guard, and a non-finite number is no reading
        # (Codex R1-9): a malformed body prints the JSON error, never a traceback or NaN.
        if not all(math.isfinite(x) for x in (used, window, resets)):
            raise ValueError("a non-finite number in the weekly window")
        out = {
            "lane": "codex",
            "used_percent": used,
            "window_mins": window,
            "resets_at": dt.datetime.fromtimestamp(resets, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "read_at": dt.datetime.fromtimestamp(now, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        out.update(pace_from(used, window, resets, now))
    except (
        AttributeError,
        KeyError,
        OSError,
        OverflowError,
        RuntimeError,
        TimeoutError,
        TypeError,
        ValueError,
    ) as exc:
        print(json.dumps({"lane": "codex", "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
