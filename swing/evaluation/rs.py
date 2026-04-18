"""RS universe loader + rs_rank computation."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Universe:
    tickers: tuple[str, ...]
    version: str


@dataclass(frozen=True)
class RSResult:
    method: str  # 'universe' | 'fallback_spy' | 'unavailable'
    rank: int | None  # 0-99, only when method == 'universe'
    return_vs_spy: float | None  # populated when method in ('universe','fallback_spy')


def load_universe(path: Path) -> Universe:
    """Parse an RS universe CSV. First non-comment line is the header 'ticker'."""
    lines = path.read_text(encoding="utf-8").splitlines()
    version = "unknown"
    tickers: list[str] = []
    saw_header = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if "version:" in stripped:
                version = stripped.split("version:", 1)[1].strip()
            continue
        if not saw_header:
            if stripped.lower() != "ticker":
                raise ValueError(f"Expected 'ticker' header, got {stripped!r}")
            saw_header = True
            continue
        tickers.append(stripped.upper())
    return Universe(tickers=tuple(sorted(set(tickers))), version=version)


def universe_version_hash(path: Path) -> str:
    """SHA256 of file bytes. Stored per pipeline run for traceability."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def compute_rs(
    ticker: str,
    returns_12w_by_ticker: dict[str, float],
    universe_tickers: tuple[str, ...],
    *,
    spy_return: float,
) -> RSResult:
    """Compute RS for one ticker.

    - If ticker in universe AND has a return: method='universe', rank = percentile within universe.
    - If ticker NOT in universe but has a return: method='fallback_spy', rank=None, excess vs SPY.
    - Otherwise: method='unavailable'.
    """
    if ticker not in returns_12w_by_ticker:
        return RSResult(method="unavailable", rank=None, return_vs_spy=None)

    ret = returns_12w_by_ticker[ticker]
    excess = ret - spy_return

    if ticker in universe_tickers:
        universe_returns = [
            returns_12w_by_ticker[t]
            for t in universe_tickers
            if t in returns_12w_by_ticker
        ]
        if not universe_returns:
            return RSResult(method="fallback_spy", rank=None, return_vs_spy=excess)
        sorted_returns = sorted(universe_returns)
        leq = sum(1 for r in sorted_returns if r <= ret)
        rank = max(
            0,
            min(99, int((leq - 1) / max(1, len(sorted_returns) - 1) * 99)),
        )
        return RSResult(method="universe", rank=rank, return_vs_spy=excess)

    return RSResult(method="fallback_spy", rank=None, return_vs_spy=excess)
