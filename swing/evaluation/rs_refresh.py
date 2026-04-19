"""Manual quarterly RS universe refresh (spec §4.1)."""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path


_HTTP_TIMEOUT_SECONDS = 30
# Filename-safe version characters per spec §4.1 (`YYYY-MM-DD-<n>`) plus the
# Phase 1 scaffold form (`test-v1`). Enforced when deriving the snapshot path
# so a corrupted/edited header cannot create a path-traversing filename
# (adversarial review Batch 5 Round 1 Major 2).
_SAFE_VERSION_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def fetch_source_tickers(source: str) -> list[str]:
    """Default source: 'spx_ndx' = union of S&P 500 + NASDAQ-100 from Wikipedia."""
    if source == "spx_ndx":
        return _fetch_spx_ndx()
    raise ValueError(f"unknown source: {source}")


def _fetch_spx_ndx() -> list[str]:
    """Fetch S&P 500 + NASDAQ-100 from Wikipedia (mimics Phase 1 task 12)."""
    import urllib.request
    from io import StringIO

    import pandas as pd

    headers = {"User-Agent": "Mozilla/5.0"}
    spx_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    ndx_url = "https://en.wikipedia.org/wiki/Nasdaq-100"

    req = urllib.request.Request(spx_url, headers=headers)
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as r:
        spx_html = r.read().decode("utf-8")
    spx_tables = pd.read_html(StringIO(spx_html))
    try:
        spx_table = next(
            t for t in spx_tables if "Symbol" in t.columns or "Ticker" in t.columns
        )
    except StopIteration as exc:
        raise RuntimeError(
            "S&P 500 Wikipedia page layout changed — no table with 'Symbol' "
            "or 'Ticker' column found. Refresh rs_refresh._fetch_spx_ndx when "
            "this happens."
        ) from exc
    spx_col = "Symbol" if "Symbol" in spx_table.columns else "Ticker"
    spx = spx_table[spx_col].astype(str).str.replace(".", "-").tolist()

    req = urllib.request.Request(ndx_url, headers=headers)
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as r:
        ndx_html = r.read().decode("utf-8")
    ndx_tables = pd.read_html(StringIO(ndx_html))
    try:
        ndx_table = next(
            t for t in ndx_tables if "Ticker" in t.columns or "Symbol" in t.columns
        )
    except StopIteration as exc:
        raise RuntimeError(
            "NASDAQ-100 Wikipedia page layout changed — no table with "
            "'Ticker' or 'Symbol' column found."
        ) from exc
    col = "Ticker" if "Ticker" in ndx_table.columns else "Symbol"
    ndx = ndx_table[col].astype(str).str.replace(".", "-").tolist()

    return sorted(set(spx) | set(ndx))


def _next_version_for(today: date, dest: Path) -> str:
    """Date-based version with -N suffix incremented if today already exists."""
    n = 1
    if dest.exists():
        head = dest.read_text(encoding="utf-8").splitlines()[0]
        if head.startswith("# version:") and today.isoformat() in head:
            try:
                old_n = int(head.rsplit("-", 1)[-1])
                n = old_n + 1
            except ValueError:
                n = 2
    return f"{today.isoformat()}-{n}"


def refresh_rs_universe(
    *, dest: Path, source: str = "spx_ndx", today: date | None = None,
) -> str:
    """Regenerate dest from source. Snapshots prior file. Returns the new version string."""
    today = today or date.today()
    tickers = fetch_source_tickers(source)
    new_version = _next_version_for(today, dest)

    if dest.exists():
        prior_head = dest.read_text(encoding="utf-8").splitlines()[0]
        if prior_head.startswith("# version: "):
            prior_version = prior_head.split(":", 1)[1].strip()
            if not _SAFE_VERSION_RE.match(prior_version):
                raise ValueError(
                    f"Prior {dest.name} has an unsafe version string "
                    f"{prior_version!r}. Expected characters [a-zA-Z0-9._-] "
                    f"(e.g., '2026-04-17-1' per spec §4.1). Refusing to snapshot "
                    f"with a filename-unsafe component."
                )
            # Derive the snapshot prefix from dest.stem so callers who rename
            # the universe file keep snapshots alongside (Round 1 Minor 2).
            snapshot = dest.parent / f"{dest.stem}-{prior_version}.csv"
            shutil.copy2(dest, snapshot)

    dest.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join([
        f"# version: {new_version}",
        f"# source: {source}",
        "# columns: ticker",
        "ticker",
        *tickers,
        "",
    ])
    dest.write_text(body, encoding="utf-8")
    return new_version
