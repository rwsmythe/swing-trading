"""CLI entrypoint + programmatic ``run_parity`` for the parity comparator.

Per the dispatch brief §5.4 / §6, this module:

1. Auto-selects the most-recent production ``evaluation_run`` whose Finviz
   CSV is still present (overridable with ``--evaluation-run-id N``).
2. Reads production candidates + criteria from the DB (read-only).
3. Reconstructs harness inputs to mirror ``_step_evaluate`` exactly.
4. Runs ``swing.evaluation.evaluator.evaluate_one`` per ticker on the
   harness side.
5. Compares per-ticker buckets and per-criterion results.
6. Writes ``parity_table.csv``, ``summary.csv``, ``run_manifest.json``.
7. Prints a short summary + tier classification to stdout.

D3 invokes this module via the bare ``python -m research.parity.run`` CLI.
The test_run_smoke suite drives ``run_parity`` directly with a mock
fetcher; no real production data needed for the smoke run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from research.parity.comparator import (
    ParitySummary,
    TickerParity,
    compare,
    summarize,
)
from research.parity.fetcher import (
    HarnessInputs,
    NoRunsWithCsvError,
    fetch_production,
    reconstruct_harness_inputs,
    select_default_evaluation_run,
)
from swing.config import Config
from swing.config import load as load_config
from swing.data.models import Candidate
from swing.evaluation.evaluator import evaluate_one

log = logging.getLogger(__name__)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def _read_finviz_tickers(csv_path: Path) -> tuple[str, ...]:
    """Read the Ticker column from a Finviz CSV. Mirrors runner.py:289-292."""
    df = pd.read_csv(csv_path)
    if "Ticker" not in df.columns:
        raise ValueError(f"Finviz CSV missing 'Ticker' column: {list(df.columns)}")
    return tuple(df["Ticker"].dropna().astype(str).str.upper().tolist())


def _format_disagreement(d) -> str:
    """One-line summary of a CriterionDisagreement for the parity_table CSV."""
    return f"{d.criterion_name}:prod={d.prod_result}/harn={d.harness_result}"


def _write_parity_table(parities: list[TickerParity], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "ticker", "prod_bucket", "harness_bucket", "bucket_match",
            "criterion_total_compared", "criterion_match_count",
            "criterion_disagreements_summary",
        ])
        for p in parities:
            writer.writerow([
                p.ticker,
                p.prod_bucket if p.prod_bucket is not None else "",
                p.harness_bucket if p.harness_bucket is not None else "",
                "true" if p.bucket_match else "false",
                p.criterion_total_compared,
                p.criterion_match_count,
                "; ".join(_format_disagreement(d) for d in p.criterion_disagreements),
            ])


def _write_summary(summary: ParitySummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "bucket_total", "bucket_matches", "bucket_agreement_rate",
            "criterion_total", "criterion_matches", "criterion_agreement_rate",
            "tier",
        ])
        writer.writerow([
            summary.bucket_total, summary.bucket_matches,
            f"{summary.bucket_agreement_rate:.6f}",
            summary.criterion_total, summary.criterion_matches,
            f"{summary.criterion_agreement_rate:.6f}",
            summary.tier,
        ])


def _build_manifest(
    *,
    inputs: HarnessInputs,
    summary: ParitySummary,
    finviz_csv_path: Path | None,
    finviz_csv_sha256: str | None,
    harness_git_sha: str,
    written_at: str,
) -> dict:
    return {
        "evaluation_run_id": inputs.evaluation_run_id,
        "data_asof_date": inputs.data_asof_date,
        "finviz_csv_path": str(finviz_csv_path) if finviz_csv_path else None,
        "finviz_csv_sha256": finviz_csv_sha256,
        "harness_git_sha": harness_git_sha,
        "harness_run_ts": written_at,
        "current_equity": inputs.current_equity,
        "equity_derivation": inputs.equity_derivation,
        "universe_version_recorded": inputs.universe_version_recorded,
        "universe_version_current": inputs.universe_version_current,
        "universe_hash_recorded": inputs.universe_hash_recorded,
        "universe_hash_current": inputs.universe_hash_current,
        "universe_match_with_production": inputs.universe_match_with_production,
        "universe_size": inputs.universe_size,
        "cache_hits": inputs.cache_hits,
        "cache_misses": inputs.cache_misses,
        "comparison_set_size": len(inputs.contexts_by_ticker),
        "skipped_tickers": dict(inputs.skipped_tickers),
        "bucket_total": summary.bucket_total,
        "bucket_matches": summary.bucket_matches,
        "bucket_agreement_rate": summary.bucket_agreement_rate,
        "criterion_total": summary.criterion_total,
        "criterion_matches": summary.criterion_matches,
        "criterion_agreement_rate": summary.criterion_agreement_rate,
        "tier": summary.tier,
    }


def _resolve_git_sha() -> str:
    """Best-effort harness git SHA for the manifest."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
        )
        return out.decode("ascii").strip()
    except Exception:
        return "unknown"


class _CountingPriceFetcher:
    """Wraps :class:`swing.prices.PriceFetcher` to expose ``hits``/``misses``
    counters the manifest reports. Phase 3 (2026-04-29) replaced the
    legacy ``_cache_path``-based counter with the per-ticker archive shape:
    ``{TICKER}.parquet`` + ``{TICKER}.meta.json`` sidecar in
    ``cfg.paths.prices_cache_dir``.

    Hit semantics: parquet exists AND meta-staleness predicate (matches
    ``swing.data.ohlcv_archive``'s weekly-refresh threshold) is fresh.
    Miss semantics: parquet missing OR meta absent OR meta stale.

    Phase isolation preserved: research-branch code reads ``swing/data/``
    public symbols only (the staleness predicate, not internal state).
    """
    # Phase 4 Task 7: 7-day threshold mirrors the inlined predicate at
    # `swing/data/ohlcv_archive.py:205-210` (current HEAD has no public
    # constant; see plan Step 1 + phase3e-todo.md follow-up). If that
    # threshold ever changes, this constant MUST be updated in lockstep.
    _STALENESS_THRESHOLD_DAYS = 7

    def __init__(self, inner, *, prices_cache_dir) -> None:
        self.inner = inner
        self.prices_cache_dir = Path(prices_cache_dir)
        self.hits = 0
        self.misses = 0

    def _archive_is_fresh(self, ticker: str) -> bool:
        """Hit only when the helper would NOT call yfinance.

        Mirrors `swing.data.ohlcv_archive.read_or_fetch_archive`'s two-branch
        decision (ohlcv_archive.py:205-241):
          - weekly-refresh predicate: meta `last_full_refresh_date` is within
            7 days of the helper's session anchor AND parquet exists.
          - incremental-gap predicate: parquet's max index date >= helper's
            session anchor (else the helper fetches the gap from yfinance).

        Both predicates use the SAME session anchor as the production helper
        (`_last_completed_session_today`), NOT wall-clock `date.today()` —
        on weekends, holidays, or pre-market-close they differ, and using
        the wrong anchor mis-counts hits/misses (Codex executing-plans R3
        Major 1). Cross-package import is the cleanest mirror; the symbol
        is leading-underscore but the alternative — replicating the NYSE
        calendar logic in research/ — is strictly worse for drift safety.
        """
        from datetime import timedelta

        import pandas as pd

        from swing.data.ohlcv_archive import _last_completed_session_today
        anchor = _last_completed_session_today()
        parquet_path = self.prices_cache_dir / f"{ticker}.parquet"
        meta_path = self.prices_cache_dir / f"{ticker}.meta.json"
        if not parquet_path.exists() or not meta_path.exists():
            return False
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False
        try:
            from datetime import date
            refresh_date = date.fromisoformat(meta.get("last_full_refresh_date", ""))
        except (TypeError, ValueError):
            return False
        if (anchor - refresh_date) >= timedelta(
            days=self._STALENESS_THRESHOLD_DAYS,
        ):
            return False  # weekly-refresh would fire → full fetch
        try:
            df = pd.read_parquet(parquet_path)
        except Exception:
            return False
        if df.empty:
            return False
        try:
            latest_stored = df.index.max().date()
        except Exception:
            return False
        # Helper fetches the gap whenever latest_stored < anchor.
        return latest_stored >= anchor

    def get(self, ticker: str, lookback_days: int, *, as_of_date=None):
        if self._archive_is_fresh(ticker):
            self.hits += 1
        else:
            self.misses += 1
        return self.inner.get(ticker, lookback_days, as_of_date=as_of_date)


def run_parity(
    *,
    cfg: Config,
    evaluation_run_id: int,
    fetcher,
    finviz_tickers: tuple[str, ...],
    output_dir: Path,
    harness_git_sha: str | None = None,
    db_path: Path | None = None,
) -> ParitySummary:
    """Programmatic entry — D3 calls this from the CLI; tests call it
    directly with a mock fetcher.

    Connects to ``db_path`` (defaulting to ``cfg.paths.db_path``), reads
    production candidates, reconstructs harness inputs, runs ``evaluate_one``
    per ticker, compares, writes outputs, returns the ParitySummary.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db = Path(db_path) if db_path is not None else cfg.paths.db_path
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        prod_by_ticker = fetch_production(conn, evaluation_run_id)
        inputs = reconstruct_harness_inputs(
            conn=conn, evaluation_run_id=evaluation_run_id,
            fetcher=fetcher, cfg=cfg, finviz_tickers=finviz_tickers,
        )
    finally:
        conn.close()

    harness_by_ticker: dict[str, Candidate] = {}
    for ticker, ctx in inputs.contexts_by_ticker.items():
        try:
            harness_by_ticker[ticker] = evaluate_one(ctx)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("evaluate_one failed for %s: %s", ticker, exc)
            inputs.skipped_tickers[ticker] = f"harness evaluate_one raised: {exc}"

    # Comparison set: production-evaluated tickers (criteria populated).
    eval_tickers = sorted(
        t for t, c in prod_by_ticker.items() if c.bucket in {"aplus", "watch", "skip"}
    )
    parities: list[TickerParity] = []
    for t in eval_tickers:
        parities.append(compare(prod_by_ticker.get(t), harness_by_ticker.get(t)))

    summary = summarize(parities) if parities else ParitySummary(
        bucket_total=0, bucket_matches=0, criterion_total=0, criterion_matches=0,
        bucket_agreement_rate=0.0, criterion_agreement_rate=0.0, tier=3,
    )

    finviz_csv_path: Path | None = None
    finviz_csv_sha256: str | None = None
    if inputs.finviz_csv_path:
        candidate = Path(inputs.finviz_csv_path)
        if not candidate.exists():
            alt = cfg.paths.finviz_inbox_dir / candidate.name
            if alt.exists():
                candidate = alt
        if candidate.exists():
            finviz_csv_path = candidate
            finviz_csv_sha256 = _sha256_file(candidate)

    git_sha = harness_git_sha if harness_git_sha is not None else _resolve_git_sha()
    written_at = datetime.now().isoformat(timespec="seconds")
    manifest = _build_manifest(
        inputs=inputs, summary=summary,
        finviz_csv_path=finviz_csv_path, finviz_csv_sha256=finviz_csv_sha256,
        harness_git_sha=git_sha, written_at=written_at,
    )

    _write_parity_table(parities, output_dir / "parity_table.csv")
    _write_summary(summary, output_dir / "summary.csv")
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="research.parity.run",
        description="Harness-vs-production parity comparator (Hypothesis 5).",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--evaluation-run-id", type=int, default=None)
    parser.add_argument(
        "--config", type=Path, default=Path("swing.config.toml"),
        help="Path to swing.config.toml (defaults to ./swing.config.toml).",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=None,
        help="PriceFetcher cache dir (defaults to cfg.paths.prices_cache_dir).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=os.environ.get("PARITY_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cfg = load_config(args.config)

    db_path = cfg.paths.db_path
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        if args.evaluation_run_id is not None:
            run_id = int(args.evaluation_run_id)
        else:
            try:
                run_id = select_default_evaluation_run(
                    conn, cfg.paths.finviz_inbox_dir,
                )
            except NoRunsWithCsvError as exc:
                log.error("No production runs have a present Finviz CSV: %s", exc)
                return 2
        # Read finviz_csv_path off the eval row.
        row = conn.execute(
            "SELECT finviz_csv_path FROM evaluation_runs WHERE id = ?", (run_id,),
        ).fetchone()
        if row is None or row[0] is None:
            log.error("evaluation_run_id=%s missing or has no finviz_csv_path", run_id)
            return 2
        csv_path = Path(row[0])
        if not csv_path.exists():
            alt = cfg.paths.finviz_inbox_dir / csv_path.name
            if alt.exists():
                csv_path = alt
            else:
                log.error("Finviz CSV not found: %s", csv_path)
                return 2
    finally:
        conn.close()

    finviz_tickers = _read_finviz_tickers(csv_path)

    from swing.prices import PriceFetcher
    cache_dir = args.cache_dir if args.cache_dir is not None else cfg.paths.prices_cache_dir
    fetcher = _CountingPriceFetcher(
        PriceFetcher(cache_dir=cache_dir),
        prices_cache_dir=cache_dir,
    )

    summary = run_parity(
        cfg=cfg, evaluation_run_id=run_id, fetcher=fetcher,
        finviz_tickers=finviz_tickers, output_dir=args.output_dir,
        harness_git_sha=_resolve_git_sha(), db_path=db_path,
    )
    msg = (
        f"evaluation_run_id={run_id} bucket={summary.bucket_matches}/"
        f"{summary.bucket_total}={summary.bucket_agreement_rate:.4%} "
        f"criterion={summary.criterion_matches}/{summary.criterion_total}="
        f"{summary.criterion_agreement_rate:.4%} -> Tier {summary.tier}"
    )
    sys.stdout.buffer.write(msg.encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
