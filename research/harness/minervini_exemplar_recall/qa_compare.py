#!/usr/bin/env python
"""Visual QA: plot archived Tiingo bars against the book figure, per exemplar.

For each exemplar with archived Tiingo data, render a split-adjusted
candlestick+volume chart over a window around the documented entry (red line)
and pair it with the book's figure PNG. The operator eyeballs each pair to
confirm: same company / era / base shape / entry spot. This is the visual catch
for ticker-reuse / wrong-era data that numeric checks miss.

Reads ``research/data/tiingo/<symbol>.csv`` (produced by tiingo_pull.py).

Usage::

    python research/harness/minervini_exemplar_recall/qa_compare.py
    python research/harness/minervini_exemplar_recall/qa_compare.py \
        --only twosmw-gra-2004,twosmw-fig11-3-yhoo

Outputs ``research/data/qa/<exemplar_id>.png`` + ``research/data/qa/README.md``
(the tracked pairing manifest).
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date, timedelta
from pathlib import Path

import mplfinance as mpf
import pandas as pd

ARCHIVE = Path("research/data/tiingo")
OUT = Path("research/data/qa")
BOOK = {
    "TWoSMW": Path("reference/Books/trade-like-a-stock-market-wizard-2013/"
                   "trade-like-a-stock-market-wizard-2013.md"),
    "THINK_TRADE": Path("reference/Books/mark-minervini-think-trade-like-a-champion-"
                        "access-publishing-group-2017/"
                        "mark-minervini-think-trade-like-a-champion-access-publishing-group-2017.md"),
}
TT_FIGDIR = ("reference/Books/mark-minervini-think-trade-like-a-champion-"
             "access-publishing-group-2017/figures/")
SYMBOL_OVERRIDE = {"EMEX": "ELX", "HOOK": "BREW"}


def tiingo_symbol(book_ticker: str) -> str:
    return SYMBOL_OVERRIDE.get(book_ticker.upper(), book_ticker.upper())


def entry_anchor(entry: str) -> date:
    p = entry.split("-")
    return date(int(p[0]), int(p[1]) if len(p) > 1 else 7, int(p[2]) if len(p) > 2 else 1)


def first_fig_token(page: str) -> str | None:
    m = re.search(r"(\d+[.\-]\d+)", page or "")
    return m.group(1) if m else None


def find_fig_png(md_path: Path, tok: str | None) -> str | None:
    """Locate a figure's image: the FIRST 'Figure <tok>' occurrence that has an
    image link within the 8 lines above it (a caption; skips in-text references,
    whose image sits below them)."""
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


def load_tiingo(symbol: str) -> pd.DataFrame | None:
    f = ARCHIVE / f"{symbol}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
    return pd.DataFrame({  # split-adjusted OHLCV (matches yfinance auto_adjust)
        "Open": df["adjOpen"], "High": df["adjHigh"], "Low": df["adjLow"],
        "Close": df["adjClose"], "Volume": df["adjVolume"]})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated exemplar_ids")
    ap.add_argument("--csv", default="research/data/minervini-exemplars.csv")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    only = {s for s in args.only.split(",") if s}

    with open(args.csv, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    manifest = []
    for r in rows:
        eid = r["exemplar_id"]
        if only and eid not in only:
            continue
        sym = tiingo_symbol(r["ticker"])
        fig = find_fig_png(BOOK.get(r["source"], BOOK["TWoSMW"]), first_fig_token(r["page"]))
        df = load_tiingo(sym)
        if df is None or df.empty:
            manifest.append((eid, sym, r["entry_date"], r["detector_class"], 0,
                             "(no Tiingo data)", fig or "?"))
            continue
        a = entry_anchor(r["entry_date"])
        lo, hi = pd.Timestamp(a - timedelta(days=220)), pd.Timestamp(a + timedelta(days=180))
        win = df.loc[(df.index >= lo) & (df.index <= hi)]
        if win.empty:
            manifest.append((eid, sym, r["entry_date"], r["detector_class"], 0,
                             "(entry window empty -> era miss)", fig or "?"))
            continue
        out = OUT / f"{eid}.png"
        try:
            mpf.plot(win, type="candle", volume=True, style="yahoo",
                     title=f"{sym} {r['entry_date']} ({r['date_precision']}) "
                           f"{r['detector_class']} | Tiingo | {r['page']}",
                     vlines=dict(vlines=[pd.Timestamp(a)], colors="red", linewidths=0.9),
                     savefig=dict(fname=str(out), dpi=100))
            manifest.append((eid, sym, r["entry_date"], r["detector_class"], len(win),
                             str(out), fig or "(figure not located)"))
        except Exception as exc:  # noqa: BLE001
            manifest.append((eid, sym, r["entry_date"], r["detector_class"], len(win),
                             f"PLOT FAIL: {exc}", fig or "?"))

    with open(OUT / "README.md", "w", encoding="utf-8") as fh:
        fh.write("# Minervini exemplar QA -- Tiingo plot vs book figure\n\n")
        fh.write("Open each pair and confirm: same company / era / base shape / entry spot.\n")
        fh.write("Plots are split-adjusted Tiingo bars; the red line is the documented entry.\n\n")
        fh.write("| exemplar | tiingo | entry | detector | bars | plot | book figure |\n")
        fh.write("|---|---|---|---|---|---|---|\n")
        for row in manifest:
            fh.write("| " + " | ".join(str(x) for x in row) + " |\n")

    ok = sum(1 for m in manifest if m[4] > 0 and str(m[5]).endswith(".png"))
    print(f"QA: {ok}/{len(manifest)} plots generated -> {OUT}")
    for m in manifest:
        flag = "OK" if (m[4] > 0 and str(m[5]).endswith(".png")) else "CHECK"
        print(f"  {m[0]:24} {m[1]:5} bars={m[4]:>4} {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
