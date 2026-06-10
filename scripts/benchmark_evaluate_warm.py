# scripts/benchmark_evaluate_warm.py
"""Arc 6 benchmark: measure warm_archives_batch wall over the REAL universe.

NOT a pytest test — hits live yfinance. Run manually before the operator gate:

    python scripts/benchmark_evaluate_warm.py

Sweeps chunk_size in {50, 75, 100}, threads=False first. Measures the dominant
near-current gap band and the deep-gap band separately (spec §8 R3 Minor #3).
Prints a table; pins DEFAULT_CHUNK_SIZE for the executing phase. The ACCEPTANCE
number (<=90s) is read from pipeline_step_timings on the gate nightly, NOT here.

To avoid mutating the operator's live archive, point it at a COPY of the cache
dir via --cache-dir, or accept that it warms the real archive (idempotent — it
only fills today's gap, same as the nightly would).
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from swing.config import Config
from swing.data.ohlcv_archive import (
    _classify_warm_cohorts,
    _full_refresh_stagger_enabled,
    _last_completed_session_today,
    warm_archives_batch,
)

# Matches swing/pipeline/runner.py:61 + :560 exactly (verified):
from swing.evaluation.rs import load_universe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default=None,
                    help="archive dir (default: cfg.paths.prices_cache_dir)")
    ap.add_argument("--chunk-sizes", default="50,75,100")
    ap.add_argument("--dry-run-only", action="store_true",
                    help="just print cohort sizes (zero fetches)")
    args = ap.parse_args()

    cfg = Config.from_defaults()
    cache_dir = Path(args.cache_dir) if args.cache_dir else cfg.paths.prices_cache_dir
    universe = load_universe(cfg.paths.rs_universe_path)  # mirrors runner.py:560
    today = _last_completed_session_today()
    tickers = [cfg.rs.benchmark_ticker, *universe.tickers]

    cohorts = _classify_warm_cohorts(
        sorted({t.upper() for t in tickers}), cache_dir=cache_dir,
        today_session=today, archive_history_days=cfg.archive.archive_history_days,
        stagger_enabled=_full_refresh_stagger_enabled(),
    )
    gap_count = sum(len(v) for v in cohorts["gap_bands"].values())
    print(f"universe={len(tickers)} cache_hit={len(cohorts['cache_hit'])} "
          f"gap={gap_count} deep_gap={len(cohorts['deep_gap'])} "
          f"full_refresh={len(cohorts['full_refresh'])} "
          f"gap_bands={len(cohorts['gap_bands'])}")
    if args.dry_run_only:
        return

    for cs in (int(x) for x in args.chunk_sizes.split(",")):
        t0 = time.monotonic()
        report = warm_archives_batch(
            tickers, cache_dir=cache_dir,
            archive_history_days=cfg.archive.archive_history_days,
            end_date=today, chunk_size=cs,
        )
        wall = time.monotonic() - t0
        print(f"chunk_size={cs:3d} wall={wall:6.1f}s chunks={report.chunks_attempted} "
              f"chunk_failures={report.chunk_failures} fallback={len(report.fallback)}")


if __name__ == "__main__":
    main()
