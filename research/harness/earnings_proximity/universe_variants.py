"""Universe-variant loader for the candidate-sparsity diagnostic study.

Provides three universes the diagnostic compares against the Session 2c
SPX+NDX baseline:

- ``spx_ndx`` — the existing SPX+NASDAQ-100 universe sourced from
  ``reference/rs-universe.csv`` via ``swing.evaluation.rs.load_universe``.
  Read directly; no network fetch; no cache entry.
- ``russell_3000`` — broader small/mid-cap universe via the iShares IWV
  ETF holdings CSV (the most authoritative free source).
- ``sp_1500`` — fallback if Russell 3000 sourcing fails: union of iShares
  IVV (S&P 500) + IJH (S&P MidCap 400) + IJR (S&P SmallCap 600).

Caching
-------
``russell_3000`` and ``sp_1500`` cache to
``<cache_dir>/universe-snapshots/<name>_YYYY-MM-DD.csv`` with one snapshot
file per fetch date. The most recent snapshot is read; if older than
``max_age_days`` (default 30), a fresh fetch is performed and stored as a
new dated file.

The fetcher is dependency-injected so tests stay deterministic and offline;
the production default is :func:`_default_fetcher` (urllib + a permissive
``User-Agent`` header).

Phase isolation (CLAUDE.md)
---------------------------
This module imports READ-ONLY from ``swing.evaluation.rs``. It does NOT
mutate any production module and does NOT write to ``swing.db``. New
files live under ``research/`` per the diagnostic-brief scope discipline.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from swing.evaluation.rs import load_universe

# ---------------------------------------------------------------------------
# Source URLs
# ---------------------------------------------------------------------------

# iShares Russell 3000 ETF holdings (CSV).
RUSSELL_3000_URL = (
    "https://www.ishares.com/us/products/239714/"
    "ishares-russell-3000-etf/1467271812596.ajax?"
    "fileType=csv&fileName=IWV_holdings&dataType=fund"
)

# iShares Core S&P 500 ETF holdings.
SP_500_URL = (
    "https://www.ishares.com/us/products/239726/"
    "ishares-core-sp-500-etf/1467271812596.ajax?"
    "fileType=csv&fileName=IVV_holdings&dataType=fund"
)

# iShares Core S&P Mid-Cap ETF holdings.
SP_400_URL = (
    "https://www.ishares.com/us/products/239763/"
    "ishares-coresp-midcap-etf/1467271812596.ajax?"
    "fileType=csv&fileName=IJH_holdings&dataType=fund"
)

# iShares Core S&P Small-Cap ETF holdings.
SP_600_URL = (
    "https://www.ishares.com/us/products/239774/"
    "ishares-core-sp-smallcap-etf/1467271812596.ajax?"
    "fileType=csv&fileName=IJR_holdings&dataType=fund"
)


# Module-level path to the SPX+NDX RS universe (single source of truth).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_RS_UNIVERSE_CSV = _REPO_ROOT / "reference" / "rs-universe.csv"


@dataclass(frozen=True)
class UniverseVariant:
    """Loaded universe with provenance metadata.

    ``source_url`` is None for ``spx_ndx`` (read from a static file), set
    for fetched variants. ``fetched_date`` is None for ``spx_ndx``, set
    to the snapshot date (filename ``YYYY-MM-DD``) for fetched variants.
    """

    name: str
    tickers: tuple[str, ...]
    version: str
    source_url: str | None
    fetched_date: date | None


Fetcher = Callable[[str], bytes]


def _default_fetcher(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 — known iShares CDN
        return resp.read()


def _today_default() -> date:
    return date.today()


def _snapshots_dir(cache_dir: Path) -> Path:
    return cache_dir / "universe-snapshots"


def _snapshot_path(cache_dir: Path, name: str, snapshot_date: date) -> Path:
    return _snapshots_dir(cache_dir) / f"{name}_{snapshot_date.isoformat()}.csv"


def _latest_snapshot(cache_dir: Path, name: str) -> tuple[Path, date] | None:
    """Return the path + date of the most-recent ``<name>_YYYY-MM-DD.csv`` snapshot."""
    d = _snapshots_dir(cache_dir)
    if not d.exists():
        return None
    prefix = f"{name}_"
    candidates: list[tuple[Path, date]] = []
    for p in d.iterdir():
        if not p.is_file() or p.suffix != ".csv" or not p.name.startswith(prefix):
            continue
        stem_date = p.stem[len(prefix) :]
        try:
            d_iso = date.fromisoformat(stem_date)
        except ValueError:
            continue
        candidates.append((p, d_iso))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[1])
    return candidates[-1]


def _parse_ishares_csv(payload: bytes) -> list[str]:
    """Extract equity tickers from an iShares ETF holdings CSV payload.

    iShares CSVs prepend ~9 metadata rows before the actual ``Ticker,Name,...``
    header; we skip until that header is observed. Only rows with
    ``Asset Class == 'Equity'`` are kept; cash and derivative rows
    (``Cash``, ``Futures``, etc.) are excluded.

    Tickers are upper-cased and de-duplicated; ordering is preserved on
    first appearance for stable diffs.
    """
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header_idx: int | None = None
    rows: list[list[str]] = []
    for i, row in enumerate(reader):
        if not row:
            continue
        # Header row: starts with literal "Ticker" and includes Asset Class.
        if header_idx is None and row[0].strip().lower() == "ticker" and "Asset Class" in row:
            header_idx = i
            header = row
            continue
        if header_idx is not None:
            rows.append(row)

    if header_idx is None:
        raise ValueError("iShares CSV: did not find 'Ticker,...,Asset Class,...' header row")

    ticker_col = header.index("Ticker")
    asset_col = header.index("Asset Class")

    seen: set[str] = set()
    ordered: list[str] = []
    for row in rows:
        if len(row) <= max(ticker_col, asset_col):
            continue
        ticker_raw = row[ticker_col].strip().upper()
        asset = row[asset_col].strip()
        if asset != "Equity":
            continue
        if not ticker_raw or ticker_raw == "-":
            continue
        # iShares occasionally uses dashes for international class shares;
        # guard against any pathological non-printable garbage.
        if not all(c.isalnum() or c in {".", "-"} for c in ticker_raw):
            continue
        if ticker_raw in seen:
            continue
        seen.add(ticker_raw)
        ordered.append(ticker_raw)
    return ordered


def parse_ishares_csv_with_sector(payload: bytes) -> list[tuple[str, str]]:
    """Extract (ticker, sector) pairs from an iShares ETF holdings CSV payload.

    Parallel to :func:`_parse_ishares_csv` but additionally returns the
    iShares-reported ``Sector`` column. Used by D4 reporting on the
    S&P 1500 universe expansion study to characterize sector breakdown
    of A+ signals. Same row-filtering rules: equity rows only; tickers
    upper-cased, deduplicated (first appearance wins), pathological
    non-printable garbage skipped.

    Empty / missing sector values are kept as the empty string so the
    caller can decide how to label them (e.g., "Unknown" in reports).
    """
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header_idx: int | None = None
    rows: list[list[str]] = []
    header: list[str] = []
    for i, row in enumerate(reader):
        if not row:
            continue
        if header_idx is None and row[0].strip().lower() == "ticker" and "Asset Class" in row:
            header_idx = i
            header = row
            continue
        if header_idx is not None:
            rows.append(row)

    if header_idx is None:
        raise ValueError("iShares CSV: did not find 'Ticker,...,Asset Class,...' header row")

    ticker_col = header.index("Ticker")
    asset_col = header.index("Asset Class")
    if "Sector" not in header:
        raise ValueError("iShares CSV: header is missing 'Sector' column")
    sector_col = header.index("Sector")

    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []
    for row in rows:
        if len(row) <= max(ticker_col, asset_col, sector_col):
            continue
        ticker_raw = row[ticker_col].strip().upper()
        asset = row[asset_col].strip()
        sector = row[sector_col].strip()
        if asset != "Equity":
            continue
        if not ticker_raw or ticker_raw == "-":
            continue
        if not all(c.isalnum() or c in {".", "-"} for c in ticker_raw):
            continue
        if ticker_raw in seen:
            continue
        seen.add(ticker_raw)
        ordered.append((ticker_raw, sector))
    return ordered


def _sector_map_path(cache_dir: Path, name: str, snapshot_date: date) -> Path:
    return _snapshots_dir(cache_dir) / f"{name}_{snapshot_date.isoformat()}_sectors.json"


def _latest_sector_map(cache_dir: Path, name: str) -> tuple[Path, date] | None:
    d = _snapshots_dir(cache_dir)
    if not d.exists():
        return None
    suffix = "_sectors.json"
    prefix = f"{name}_"
    candidates: list[tuple[Path, date]] = []
    for p in d.iterdir():
        if not p.is_file() or not p.name.startswith(prefix) or not p.name.endswith(suffix):
            continue
        stem_date = p.name[len(prefix) : -len(suffix)]
        try:
            d_iso = date.fromisoformat(stem_date)
        except ValueError:
            continue
        candidates.append((p, d_iso))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[1])
    return candidates[-1]


def load_sp_1500_sector_map(
    *,
    cache_dir: Path | None = None,
    max_age_days: int = 30,
    fetcher: Fetcher | None = None,
    today: Callable[[], date] | None = None,
) -> dict[str, str]:
    """Return a {ticker: sector} mapping for the S&P 1500 universe.

    Fetches IVV + IJH + IJR holdings CSVs, extracts per-ticker sectors,
    and unions across the three lists. The first occurrence wins on
    duplicate tickers (IVV → IJH → IJR ordering). Caches the result as
    a JSON sidecar next to the universe snapshot:
    ``<cache_dir>/universe-snapshots/sp_1500_<YYYY-MM-DD>_sectors.json``.

    The signature mirrors :func:`load_universe_variant` for the sp_1500
    case: same cache_dir default, same fetcher dependency injection,
    same today() seam for tests.
    """
    if cache_dir is None:
        cache_dir = Path.home() / "swing-data" / "research-cache"
    fetcher = fetcher or _default_fetcher
    today = today or _today_default

    snapshots = _snapshots_dir(cache_dir)
    snapshots.mkdir(parents=True, exist_ok=True)

    today_d = today()
    latest = _latest_sector_map(cache_dir, "sp_1500")
    if latest is not None:
        sector_path, sector_date = latest
        age = (today_d - sector_date).days
        if age <= max_age_days:
            return json.loads(sector_path.read_text(encoding="utf-8"))

    urls = (SP_500_URL, SP_400_URL, SP_600_URL)
    mapping: dict[str, str] = {}
    for url in urls:
        payload = fetcher(url)
        for ticker, sector in parse_ishares_csv_with_sector(payload):
            if ticker not in mapping:
                mapping[ticker] = sector

    sector_path = _sector_map_path(cache_dir, "sp_1500", today_d)
    sector_path.write_text(
        json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8"
    )
    return mapping


def _load_or_fetch_ishares(
    *,
    name: str,
    urls: tuple[str, ...],
    cache_dir: Path,
    max_age_days: int,
    fetcher: Fetcher,
    today: Callable[[], date],
) -> UniverseVariant:
    """Cache-first; fetch+write a new snapshot if stale or absent.

    For multi-URL universes (``sp_1500`` = IVV + IJH + IJR), all URLs are
    fetched and their tickers unioned into a single snapshot CSV. The
    snapshot is one-row-per-ticker and includes a ``source_url`` column so
    the diagnostic report can trace each ticker back to its sub-ETF.
    """
    snapshots = _snapshots_dir(cache_dir)
    snapshots.mkdir(parents=True, exist_ok=True)

    today_d = today()
    latest = _latest_snapshot(cache_dir, name)
    if latest is not None:
        snapshot_path, snapshot_date = latest
        age = (today_d - snapshot_date).days
        if age <= max_age_days:
            tickers = _read_snapshot(snapshot_path)
            return UniverseVariant(
                name=name,
                tickers=tuple(sorted(set(tickers))),
                version=f"{name}_{snapshot_date.isoformat()}",
                source_url=urls[0] if len(urls) == 1 else None,
                fetched_date=snapshot_date,
            )

    # Fresh fetch.
    all_tickers: list[tuple[str, str]] = []  # (ticker, url)
    for url in urls:
        payload = fetcher(url)
        for t in _parse_ishares_csv(payload):
            all_tickers.append((t, url))

    snapshot_path = _snapshot_path(cache_dir, name, today_d)
    _write_snapshot(snapshot_path, all_tickers, header_date=today_d.isoformat())
    return UniverseVariant(
        name=name,
        tickers=tuple(sorted({t for t, _ in all_tickers})),
        version=f"{name}_{today_d.isoformat()}",
        source_url=urls[0] if len(urls) == 1 else None,
        fetched_date=today_d,
    )


def _write_snapshot(path: Path, rows: list[tuple[str, str]], *, header_date: str) -> None:
    """Write a per-ticker snapshot CSV with provenance.

    Schema: ``ticker,source_url`` plus a ``# fetched: YYYY-MM-DD`` comment.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(f"# fetched: {header_date}\n")
        writer = csv.writer(fh)
        writer.writerow(["ticker", "source_url"])
        for ticker, url in rows:
            writer.writerow([ticker, url])


def _read_snapshot(path: Path) -> list[str]:
    tickers: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.lower().startswith("ticker,"):
                continue
            ticker = stripped.split(",", 1)[0].strip().strip('"').upper()
            if ticker and ticker != "TICKER":
                tickers.append(ticker)
    return tickers


def load_universe_variant(
    name: str,
    *,
    cache_dir: Path | None = None,
    max_age_days: int = 30,
    fetcher: Fetcher | None = None,
    today: Callable[[], date] | None = None,
) -> UniverseVariant:
    """Load a universe variant by name.

    Supported names: ``spx_ndx``, ``russell_3000``, ``sp_1500``.

    For ``spx_ndx``, ``cache_dir`` and ``fetcher`` are unused — the universe
    is read directly from ``reference/rs-universe.csv``.

    For ``russell_3000`` / ``sp_1500``, ``cache_dir`` is required at runtime
    (defaults to ``~/swing-data/research-cache/`` if the caller wants to
    parallel the OHLCV / earnings caches; tests pass ``tmp_path``).
    """
    if name == "spx_ndx":
        u = load_universe(_RS_UNIVERSE_CSV)
        return UniverseVariant(
            name="spx_ndx",
            tickers=u.tickers,
            version=u.version,
            source_url=None,
            fetched_date=None,
        )

    if cache_dir is None:
        cache_dir = Path.home() / "swing-data" / "research-cache"
    fetcher = fetcher or _default_fetcher
    today = today or _today_default

    if name == "russell_3000":
        return _load_or_fetch_ishares(
            name=name,
            urls=(RUSSELL_3000_URL,),
            cache_dir=cache_dir,
            max_age_days=max_age_days,
            fetcher=fetcher,
            today=today,
        )
    if name == "sp_1500":
        return _load_or_fetch_ishares(
            name=name,
            urls=(SP_500_URL, SP_400_URL, SP_600_URL),
            cache_dir=cache_dir,
            max_age_days=max_age_days,
            fetcher=fetcher,
            today=today,
        )

    raise ValueError(f"unknown universe variant: {name!r}")
