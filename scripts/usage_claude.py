"""Read the Claude subscription's weekly usage window (stdlib only).

Calls the endpoint Claude Code's own ``/usage`` command uses,
``GET https://api.anthropic.com/api/oauth/usage``, with the OAuth access token
Claude Code stores in ``~/.claude/.credentials.json``. Prints one JSON object::

    {"lane": "claude", "used_percent": 21.0, "window_mins": 10080,
     "resets_at": "2026-11-02T10:00:00Z", "elapsed_fraction": 0.10,
     "pace": 2.1, "read_at": "..."}

``pace`` is the projected end-of-window utilization as a multiple of the
allotment (see ``scripts/usage_codex.py``; the same formula, so the two lanes
compare directly). The token is read, sent once over TLS to the vendor's own
host, and never printed. An agent session runs this ONLY under the standing
project permission rule the operator granted by commissioning the Codex-lane
arc on 2026-11-03 (re-confirmed 2026-11-11), recorded as ``_comment_usage``
beside the exact allow rule in ``.claude/settings.json``; any other use of the
credential file is out of bounds. A failure prints ``{"lane": "claude",
"error": "..."}`` and exits 1; the caller treats that as "no reading".
Ported 2026-11-11 from harness-template 4335ff6 (the Codex-lane arc, P2).

Usage: ``python scripts/usage_claude.py [--credentials PATH] [--timeout S]``.
``parse_usage`` is the pure function the harness test covers.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
from typing import Any

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
WEEK_MINS = 7 * 24 * 60


def pace_from(
    used_percent: float, window_mins: float, resets_at_epoch: float, now_epoch: float
) -> dict[str, Any]:
    """Return the elapsed fraction and pace for one lane's window.

    The same formula as ``scripts/usage_codex.py`` (kept inline so each readout
    stays a standalone stdlib script); 1.0 means on track to use exactly the
    allotment by the reset.
    """
    window_s = max(window_mins, 1.0) * 60.0
    remaining = max(0.0, min(window_s, resets_at_epoch - now_epoch))
    elapsed = max(1e-6, min(1.0, 1.0 - remaining / window_s))
    return {
        "elapsed_fraction": round(elapsed, 6),
        "pace": round((used_percent / 100.0) / elapsed, 3),
    }


def parse_usage(body: dict[str, Any], now_epoch: float) -> dict[str, Any]:
    """Return the weekly lane reading from the endpoint's JSON body.

    Uses ``seven_day.utilization`` (percent) and ``seven_day.resets_at``
    (ISO 8601 with offset). Raises ``KeyError``/``ValueError`` on a body
    without them.
    """
    week = body["seven_day"]
    used = float(week["utilization"])
    resets_iso = str(week["resets_at"])
    resets = dt.datetime.fromisoformat(resets_iso).timestamp()
    out = {
        "lane": "claude",
        "used_percent": used,
        "window_mins": WEEK_MINS,
        "resets_at": dt.datetime.fromtimestamp(resets, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "read_at": dt.datetime.fromtimestamp(now_epoch, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out.update(pace_from(used, WEEK_MINS, resets, now_epoch))
    return out


def fetch(credentials: pathlib.Path, timeout: float) -> dict[str, Any]:
    """GET the usage endpoint with the stored bearer token; return the JSON body."""
    cred = json.loads(credentials.read_text("utf-8"))
    token = cred["claudeAiOauth"]["accessToken"]
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": "Bearer " + token,
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "harness-usage/0.1",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    return body


def main(argv: list[str] | None = None) -> int:
    """Command-line entry: print the lane reading as one JSON line."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--credentials", default=str(pathlib.Path.home() / ".claude" / ".credentials.json")
    )
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args(argv)
    now = time.time()
    try:
        body = fetch(pathlib.Path(args.credentials), args.timeout)
        out = parse_usage(body, now)
    except (OSError, KeyError, TypeError, ValueError, urllib.error.URLError) as exc:
        print(json.dumps({"lane": "claude", "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
