#!/usr/bin/env python
"""Tiingo EOD puller for the Minervini correct-entry exemplar-recall arc.

Pulls daily OHLCV history for each exemplar ticker from Tiingo into a
**gitignored** archive (``research/data/tiingo/<symbol>.csv``). Tiingo's license
is "Internal Use Only" -- the raw bars are for our internal research only and
MUST NOT be committed or redistributed (the archive dir is in ``.gitignore``).

The free tier is sufficient: ~31 unique symbols, one request each, vs the free
limits of 50 requests/hour, 1000/day, 1 GB/month.

Usage::

    # one-time: get a free key at tiingo.com, then (never commit it):
    #   PowerShell:  $env:TIINGO_API_KEY = "...."
    #   bash:        export TIINGO_API_KEY=....
    python research/harness/minervini_exemplar_recall/tiingo_pull.py --dry-run
    python research/harness/minervini_exemplar_recall/tiingo_pull.py

Output: ``research/data/tiingo/<symbol>.csv`` per symbol + ``_manifest.csv``
(status / bars / date-range / whether the entry era is usable per exemplar).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

DEFAULT_CSV = Path("research/data/minervini-exemplars.csv")
DEFAULT_ARCHIVE = Path("research/data/tiingo")

# CSV book-ticker -> Tiingo symbol, only where they differ (renamed/wrong ticker).
# (TASR is already stored as AXON in the CSV; QSII/YHOO resolve under their own symbol.)
SYMBOL_OVERRIDE = {"EMEX": "ELX", "HOOK": "BREW"}

# Calendar-day lookback required before the entry so the harness has enough bars
# for the 200-day MAs + 52-week high/low (~200 trading days ~= 300 calendar days).
LOOKBACK_DAYS = 300


def tiingo_symbol(book_ticker: str) -> str:
    return SYMBOL_OVERRIDE.get(book_ticker.upper(), book_ticker.upper())


def unique_symbols(rows) -> list[str]:
    """Deduped, sorted Tiingo symbol set for the fetch loop. ALWAYS includes SPY
    (the fallback_spy RS benchmark) even though no exemplar row carries it."""
    syms = {tiingo_symbol(r["ticker"]) for r in rows}
    syms.add("SPY")
    return sorted(syms)


def entry_anchor(entry: str) -> date:
    """Parse YYYY / YYYY-MM / YYYY-MM-DD to a concrete date (mid-period defaults)."""
    p = entry.split("-")
    y = int(p[0])
    m = int(p[1]) if len(p) > 1 else 7
    d = int(p[2]) if len(p) > 2 else 1
    return date(y, m, d)


def fetch_csv(symbol: str, token: str, start: str, timeout: int = 60,
              retries: int = 3) -> tuple[str | None, str | None]:
    """Return (csv_text, None) on success or (None, error_str). Token goes in the
    header (never the URL) so it can't leak into logs."""
    url = (f"https://api.tiingo.com/tiingo/daily/{symbol}/prices"
           f"?startDate={start}&format=csv")
    req = urllib.request.Request(
        url, headers={"Authorization": f"Token {token}",
                      "Content-Type": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8"), None
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return None, f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 - record + continue per ticker
            if attempt < retries - 1:
                time.sleep(2)
                continue
            return None, type(exc).__name__
    return None, "retries_exhausted"


def csv_date_range(text: str) -> tuple[int, str | None, str | None]:
    """(n_bars, first_date, last_date) from a Tiingo prices CSV (date is col 0)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    body = [ln for ln in lines[1:] if ln[:4].isdigit()]
    if not body:
        return 0, None, None
    dates = sorted(ln.split(",")[0] for ln in body)
    return len(body), dates[0], dates[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull Tiingo EOD bars for the exemplar set.")
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    ap.add_argument("--start", default="1985-01-01", help="earliest startDate to request")
    ap.add_argument("--force", action="store_true", help="re-fetch even if cached")
    ap.add_argument("--dry-run", action="store_true", help="show the plan; no network")
    ap.add_argument("--sleep", type=float, default=0.6, help="seconds between requests")
    args = ap.parse_args()

    token = os.environ.get("TIINGO_API_KEY", "").strip()
    if not token and not args.dry_run:
        print("ERROR: set TIINGO_API_KEY (free key from tiingo.com). Never commit it.",
              file=sys.stderr)
        return 2

    with open(args.csv, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    plan = [(r["exemplar_id"], r["ticker"], tiingo_symbol(r["ticker"]), r["entry_date"])
            for r in rows]
    uniq = unique_symbols(rows)
    archive = Path(args.archive)
    print(f"{len(rows)} exemplars -> {len(uniq)} unique Tiingo symbols; archive={archive}")

    if args.dry_run:
        print(f"DRY RUN (no fetch). TIINGO_API_KEY set: {bool(token)}")
        for eid, bt, sym, e in plan:
            arrow = f"{bt}->{sym}" if bt.upper() != sym else sym
            print(f"  {eid:24} {arrow:14} {e:10} -> {archive / (sym + '.csv')}")
        return 0

    archive.mkdir(parents=True, exist_ok=True)
    results: dict[str, tuple[str, int, str | None, str | None]] = {}
    for sym in uniq:
        target = archive / f"{sym}.csv"
        if target.exists() and not args.force:
            n, lo, hi = csv_date_range(target.read_text(encoding="utf-8"))
            results[sym] = ("cached", n, lo, hi)
            print(f"  [skip]  {sym}: cached {n} bars {lo}..{hi}")
            continue
        text, err = fetch_csv(sym, token, args.start)
        time.sleep(args.sleep)
        if err:
            results[sym] = (err, 0, None, None)
            hint = "  (check TIINGO_API_KEY)" if err == "HTTP 401" else ""
            print(f"  [FAIL]  {sym}: {err}{hint}")
            continue
        n, lo, hi = csv_date_range(text or "")
        if n == 0:
            results[sym] = ("empty", 0, None, None)
            print(f"  [empty] {sym}: no bars")
            continue
        target.write_text(text, encoding="utf-8")
        results[sym] = ("ok", n, lo, hi)
        print(f"  [ok]    {sym}: {n} bars {lo}..{hi}")

    manifest = archive / "_manifest.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["exemplar_id", "csv_ticker", "tiingo_symbol", "entry_date",
                    "status", "bars", "first_date", "last_date", "entry_usable"])
        for eid, bt, sym, e in plan:
            st, n, lo, hi = results.get(sym, ("?", 0, None, None))
            usable = bool(
                lo and hi
                and lo <= (entry_anchor(e) - timedelta(days=LOOKBACK_DAYS)).isoformat()
                and hi >= entry_anchor(e).isoformat())
            w.writerow([eid, bt, sym, e, st, n, lo or "", hi or "", usable])

    ok = sum(1 for v in results.values() if v[0] in ("ok", "cached"))
    print(f"\n{ok}/{len(uniq)} symbols archived. manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
