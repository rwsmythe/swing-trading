#!/usr/bin/env python
"""Stitch each curated exemplar's book figure + our data plot into one image.

Produces research/data/qa/_pairs/<exemplar_id>.png (book figure on the left, our
data plot on the right) for the operator visual gate -- one folder to flip
through instead of opening two files per exemplar. Uses the Tiingo plot from
qa_compare; where Tiingo lacks the entry era (e.g. VICR) it regenerates the plot
from yfinance.

Run qa_compare.py first (to produce the Tiingo plots), then::

    python research/harness/minervini_exemplar_recall/qa_montage.py
"""

from __future__ import annotations

import csv
import re
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path("research/data/qa")
PAIRS = OUT / "_pairs"
BOOK = {
    "TWoSMW": Path("reference/Books/trade-like-a-stock-market-wizard-2013/"
                   "trade-like-a-stock-market-wizard-2013.md"),
    "THINK_TRADE": Path("reference/Books/mark-minervini-think-trade-like-a-champion-"
                        "access-publishing-group-2017/"
                        "mark-minervini-think-trade-like-a-champion-access-publishing-group-2017.md"),
}
TT_FIGDIR = ("reference/Books/mark-minervini-think-trade-like-a-champion-"
             "access-publishing-group-2017/figures/")


def entry_anchor(entry: str) -> date:
    p = entry.split("-")
    return date(int(p[0]), int(p[1]) if len(p) > 1 else 7, int(p[2]) if len(p) > 2 else 1)


def first_fig_token(page: str) -> str | None:
    m = re.search(r"(\d+[.\-]\d+)", page or "")
    return m.group(1) if m else None


def find_fig_png(md_path: Path, tok: str | None) -> str | None:
    if not tok or not md_path.exists():
        return None
    lines = md_path.read_text(encoding="utf-8").splitlines()
    cap = re.compile(r"Figure\s+" + re.escape(tok) + r"(?!\d)")
    img = re.compile(r"!\[\]\(([^)]+\.png)\)")
    for i, line in enumerate(lines):
        if not cap.search(line):
            continue
        for j in range(i, max(-1, i - 9), -1):
            m = img.search(lines[j])
            if m:
                p = m.group(1)
                if p.startswith("reference/minervini/figures/"):
                    return TT_FIGDIR + Path(p).name
                return p
    return None


def ensure_data_plot(eid: str, ticker: str, row: dict) -> Path | None:
    """Existing Tiingo plot, or a yfinance-regenerated one if Tiingo lacks the era."""
    p = OUT / f"{eid}.png"
    if p.exists():
        return p
    import logging
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    import mplfinance as mpf
    import pandas as pd
    import yfinance as yf
    a = entry_anchor(row["entry_date"])
    df = yf.Ticker(ticker).history(
        start=(a - timedelta(days=220)).isoformat(),
        end=(a + timedelta(days=180)).isoformat(), auto_adjust=True)
    if df.empty:
        return None
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.index = df.index.tz_localize(None)
    mpf.plot(df, type="candle", volume=True, style="yahoo",
             title=f"{ticker} {row['entry_date']} ({row['date_precision']}) "
                   f"{row['detector_class']} | yfinance | {row['page']}",
             vlines=dict(vlines=[pd.Timestamp(a)], colors="red", linewidths=0.9),
             savefig=dict(fname=str(p), dpi=100))
    return p


def main() -> int:
    PAIRS.mkdir(parents=True, exist_ok=True)
    with open("research/data/minervini-exemplars.csv", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["curated"] == "yes"]
    made = 0
    for r in rows:
        eid = r["exemplar_id"]
        book = find_fig_png(BOOK.get(r["source"], BOOK["TWoSMW"]), first_fig_token(r["page"]))
        plot = ensure_data_plot(eid, r["ticker"], r)
        book_ok = bool(book) and Path(book).exists()
        if not plot or not book_ok:
            print(f"  [skip] {eid}: plot={bool(plot)} book_ok={book_ok}")
            continue
        fig, ax = plt.subplots(1, 2, figsize=(16, 6))
        ax[0].imshow(mpimg.imread(book))
        ax[0].axis("off")
        ax[0].set_title("BOOK FIGURE", fontsize=11)
        ax[1].imshow(mpimg.imread(str(plot)))
        ax[1].axis("off")
        ax[1].set_title("OUR DATA (red line = entry)", fontsize=11)
        fig.suptitle(f"{eid}   |   {r['ticker']}  {r['entry_date']}  "
                     f"{r['detector_class']}   |   {r['page']}", fontsize=12)
        fig.tight_layout()
        fig.savefig(PAIRS / f"{eid}.png", dpi=90, bbox_inches="tight")
        plt.close(fig)
        made += 1
        print(f"  [ok]   {eid}")
    print(f"\n{made}/{len(rows)} pairs -> {PAIRS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
