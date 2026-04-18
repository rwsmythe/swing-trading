"""Manual quarterly RS universe refresh (spec §4.1)."""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path


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
    with urllib.request.urlopen(req) as r:
        spx_html = r.read().decode("utf-8")
    spx_tables = pd.read_html(StringIO(spx_html))
    spx = spx_tables[0]["Symbol"].astype(str).str.replace(".", "-").tolist()

    req = urllib.request.Request(ndx_url, headers=headers)
    with urllib.request.urlopen(req) as r:
        ndx_html = r.read().decode("utf-8")
    ndx_tables = pd.read_html(StringIO(ndx_html))
    ndx_table = next(
        t for t in ndx_tables if "Ticker" in t.columns or "Symbol" in t.columns
    )
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
            snapshot = dest.parent / f"rs-universe-{prior_version}.csv"
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
