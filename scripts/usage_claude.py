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
host (a redirect is refused, never followed), and never printed. An agent
session runs this ONLY under the standing
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
import math
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
WEEK_MINS = 7 * 24 * 60
# A bearer token's characters (RFC 6750 b64token). A stored value outside this shape is
# refused when read, by a message that does not show it (Codex R1-6).
TOKEN_SHAPE = re.compile(r"[A-Za-z0-9._~+/-]+=*")
TOKEN_PIECE = re.compile(r"[A-Za-z0-9._~+/=-]{4,}")


def read_token(credentials: pathlib.Path) -> str:
    """The stored OAuth access token; ``ValueError`` (value not shown) on a bad shape."""
    cred = json.loads(credentials.read_text("utf-8"))
    token = cred["claudeAiOauth"]["accessToken"]
    if not isinstance(token, str) or not TOKEN_SHAPE.fullmatch(token):
        raise ValueError("the stored access token has an invalid shape (its value is not shown)")
    return token


def redact(text: str, token: str | None) -> str:
    """``text`` with every 4+ character run of ``token`` replaced (Codex R1-6, second belt).

    A library error can quote a header value through ``repr``, which escapes control
    characters, so the token is matched piece by piece rather than whole.
    """
    for piece in TOKEN_PIECE.findall(token or ""):
        text = text.replace(piece, "<redacted>")
    return text


def pace_from(
    used_percent: float, window_mins: float, resets_at_epoch: float, now_epoch: float
) -> dict[str, Any]:
    """Return the elapsed fraction and pace for one lane's window.

    The same formula as ``scripts/usage_codex.py`` (kept inline so each readout
    stays a standalone stdlib script); 1.0 means on track to use exactly the
    allotment by the reset.
    """
    # A negative share would win the lane comparison, and a finite share can overflow the
    # division to inf: neither is a reading (Codex R2-3).
    if used_percent < 0:
        raise ValueError("a negative used percent")
    window_s = max(window_mins, 1.0) * 60.0
    remaining = max(0.0, min(window_s, resets_at_epoch - now_epoch))
    elapsed = max(1e-6, min(1.0, 1.0 - remaining / window_s))
    pace = round((used_percent / 100.0) / elapsed, 3)
    if not math.isfinite(pace):
        raise ValueError("the pace is not a finite number")
    return {
        "elapsed_fraction": round(elapsed, 6),
        "pace": pace,
    }


def parse_usage(body: dict[str, Any], now_epoch: float) -> dict[str, Any]:
    """Return the weekly lane reading from the endpoint's JSON body.

    Uses ``seven_day.utilization`` (percent) and ``seven_day.resets_at``
    (ISO 8601 with offset). Raises ``KeyError``/``ValueError`` on a body
    without them, and ``ValueError`` on a non-finite utilization (Codex R1-9) or a
    negative one, or a pace that is not finite (Codex R2-3).
    """
    week = body["seven_day"]
    used = float(week["utilization"])
    if not math.isfinite(used):
        raise ValueError("a non-finite utilization in seven_day")
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


class RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect (Codex R1-5): urllib copies ordinary headers onto a
    redirected request, so following one could send the token to another host or over
    plain HTTP. A 3xx is an error reading, never a second request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code, "redirect refused: the token goes only to USAGE_URL", headers, fp
        )


def build_opener(*handlers: urllib.request.BaseHandler) -> urllib.request.OpenerDirector:
    """The ONLY opener the token is sent through: redirects are refused."""
    return urllib.request.build_opener(RefuseRedirects, *handlers)


def fetch(
    token: str, timeout: float, opener: urllib.request.OpenerDirector | None = None
) -> dict[str, Any]:
    """GET the usage endpoint with the bearer token; return the JSON body.

    The Authorization header is UNREDIRECTED (never copied to a redirected request), and
    the request goes through :func:`build_opener`, which refuses redirects outright.
    """
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "harness-usage/0.1",
            "Accept": "application/json",
        },
    )
    req.add_unredirected_header("Authorization", "Bearer " + token)
    with (opener or build_opener()).open(req, timeout=timeout) as resp:
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
    token = None
    try:
        token = read_token(pathlib.Path(args.credentials))
        body = fetch(token, args.timeout)
        out = parse_usage(body, now)
        # Serialized inside the guard and strictly: a non-finite value is no reading.
        line = json.dumps(out, allow_nan=False)
    except (
        AttributeError,
        KeyError,
        OSError,
        OverflowError,
        TypeError,
        ValueError,
        urllib.error.URLError,
    ) as exc:
        error = redact(f"{type(exc).__name__}: {exc}", token)
        print(json.dumps({"lane": "claude", "error": error}))
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
