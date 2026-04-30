"""One-time consolidation of `~/swing-data/prices-cache/` from per-as-of-date
parquet keying to per-ticker parquet keying.

Operator runs once via `python -m swing.tools.migrate_prices_cache` BEFORE
pulling the consumer-refactor commits (Task 4-6 of the OHLCV archive
consolidation plan). After this script completes, `cfg.paths.prices_cache_dir`
holds `{TICKER}.parquet` + `{TICKER}.meta.json` per ticker; legacy
`*_*d_asof-*.parquet` files have been deleted.

Idempotent: safe to re-run after interruption or on an already-migrated
cache. Atomic per-ticker: each ticker's consolidated archive is written to
a temp file in the same directory, then `os.replace`-d into place; legacy
files are deleted only after atomic-replace succeeds. If the rename crashes
mid-ticker, that ticker rolls back (legacy files survive; prior archive
unchanged) and a re-run will converge.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import sys
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_LEGACY_RE = re.compile(
    r"^(?P<ticker>[A-Za-z0-9.\-]+)_(?P<lookback>\d+)d_asof-(?P<asof>\d{4}-\d{2}-\d{2})\.parquet$"
)


def _scan_legacy_files(cache_dir: Path) -> dict[str, list[tuple[Path, date]]]:
    by_ticker: dict[str, list[tuple[Path, date]]] = defaultdict(list)
    for entry in cache_dir.iterdir():
        if not entry.is_file():
            continue
        m = _LEGACY_RE.match(entry.name)
        if m is None:
            continue
        ticker = m.group("ticker").upper()
        as_of = date.fromisoformat(m.group("asof"))
        by_ticker[ticker].append((entry, as_of))
    return by_ticker


def _consolidate_ticker(
    ticker: str,
    legacy_files: list[tuple[Path, date]],
    cache_dir: Path,
) -> None:
    archive_path = cache_dir / f"{ticker}.parquet"
    meta_path = cache_dir / f"{ticker}.meta.json"

    legacy_files = sorted(legacy_files, key=lambda t: t[1])
    max_asof = legacy_files[-1][1] if legacy_files else None

    frames: list[pd.DataFrame] = []
    for path, _as_of in legacy_files:
        df = pd.read_parquet(path)
        frames.append(df)
    if archive_path.exists():
        frames.append(pd.read_parquet(archive_path))

    if not frames:
        return

    combined = pd.concat(frames)
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()

    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=str(cache_dir), prefix=f"{ticker}.", suffix=".parquet.tmp"
    )
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        combined.to_parquet(tmp_path)
        os.replace(tmp_path, archive_path)
    except Exception:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise

    if max_asof is not None:
        existing_meta_date: date | None = None
        if meta_path.exists():
            try:
                existing_meta = json.loads(meta_path.read_text())
                existing_meta_date = date.fromisoformat(existing_meta["last_full_refresh_date"])
            except (json.JSONDecodeError, KeyError, ValueError):
                existing_meta_date = None
        effective_meta_date = max(max_asof, existing_meta_date) if existing_meta_date else max_asof
        meta_tmp_fd, meta_tmp_name = tempfile.mkstemp(
            dir=str(cache_dir), prefix=f"{ticker}.", suffix=".meta.json.tmp"
        )
        os.close(meta_tmp_fd)
        meta_tmp_path = Path(meta_tmp_name)
        try:
            meta_tmp_path.write_text(
                json.dumps({"last_full_refresh_date": effective_meta_date.isoformat()})
            )
            os.replace(meta_tmp_path, meta_path)
        except Exception:
            if meta_tmp_path.exists():
                with contextlib.suppress(OSError):
                    meta_tmp_path.unlink()
            raise

    for path, _as_of in legacy_files:
        try:
            path.unlink()
        except OSError as exc:
            log.warning("failed to unlink legacy file %s: %s", path, exc)


def run(*, cache_dir: Path) -> None:
    """Consolidate every ticker found in `cache_dir`. Idempotent."""
    cache_dir = Path(cache_dir)
    if not cache_dir.exists():
        log.info("cache dir %s does not exist; nothing to migrate", cache_dir)
        return
    legacy_by_ticker = _scan_legacy_files(cache_dir)
    if not legacy_by_ticker:
        log.info("no legacy files found in %s; migration is a no-op", cache_dir)
        return
    log.info(
        "consolidating %d ticker(s) from %d legacy file(s) in %s",
        len(legacy_by_ticker),
        sum(len(v) for v in legacy_by_ticker.values()),
        cache_dir,
    )
    for ticker, files in legacy_by_ticker.items():
        _consolidate_ticker(ticker, files, cache_dir)
    log.info("migration complete")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate per-as-of-date prices-cache files into per-ticker archives."
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Override cache directory (defaults to swing.config.toml's prices_cache_dir).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("swing.config.toml"),
        help="Path to swing.config.toml (used when --cache-dir is omitted).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.cache_dir is not None:
        cache_dir = args.cache_dir
    else:
        from swing.config import load
        cfg = load(args.config)
        cache_dir = cfg.paths.prices_cache_dir

    run(cache_dir=cache_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
