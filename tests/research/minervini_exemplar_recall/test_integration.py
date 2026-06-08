# tests/research/minervini_exemplar_recall/test_integration.py
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.slow


def _plant_tiingo(tiingo_dir: Path, symbol: str, n=400, start="2008-01-02", seed=0.0):
    idx = pd.bdate_range(start=start, periods=n)
    closes = []
    price = 20.0 + seed
    for i in range(n):
        # Use 0.994 for the down leg so each 9-bar down swing is ~-5.3%,
        # above the zigzag_pivot 3% threshold (0.997^9 = -2.7% which is below it).
        price *= 1.005 if (i // 9) % 2 == 0 else 0.994
        closes.append(round(price, 4))
    lines = ["date,close,high,low,open,volume,adjClose,adjHigh,adjLow,adjOpen,adjVolume"]
    for d, c in zip(idx, closes):
        lines.append(f"{d.date()},{c},{c*1.01:.4f},{c*0.99:.4f},{c:.4f},1000000,"
                     f"{c},{c*1.01:.4f},{c*0.99:.4f},{c:.4f},1000000")
    (tiingo_dir / f"{symbol}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_end_to_end_real_detectors_writes_quartet(tmp_path):
    from research.harness.minervini_exemplar_recall.run import run_harness

    tiingo = tmp_path / "tiingo"
    tiingo.mkdir()
    _plant_tiingo(tiingo, "AAA")
    _plant_tiingo(tiingo, "SPY", seed=5.0)

    ex = tmp_path / "ex.csv"
    header = ("exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
              "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes")
    ex.write_text(header + "\nid-a,AAA,VCP,vcp,2009-06-01,,,,,day,S,P,claude,yes,n\n", encoding="utf-8")

    results, per_session, summary, manifest = run_harness(
        exemplars_csv=ex, tiingo_dir=tiingo, output_dir=tmp_path / "out",
        bootstrap_b=50,  # keep the slow test fast
        h2_all_windows=True,  # also exercise the diagnostic over real windows
    )
    assert results.exists() and per_session.exists() and summary.exists() and manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True
    assert data["n_total"] == 1
    # The run drove the REAL 5 detectors against a synthetic stage DB (production-path coverage,
    # not a stubbed registry) -> the results.csv has both timing-mode rows.
    body = results.read_text(encoding="utf-8")
    assert "single_session" in body and "window_sweep" in body
    # The all-windows diagnostic covers BOTH timing modes (Codex R2/R3 -> not just the entry anchor).
    diag = (results.parent / "h2_all_windows_diagnostic.csv").read_text(encoding="utf-8")
    assert "single_session" in diag and "window_sweep" in diag
