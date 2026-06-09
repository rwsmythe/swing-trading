from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from research.harness.minervini_primary_base_recall.run import run_harness


def _body_firing_closes() -> list[float]:
    """A 57-close series that forms ONE clean primary base emerging on the LAST bar (the entry bar):
    rise to peak 100, a base oscillating below 100 (low ~89), then a developing recovery that
    freshly crosses 100 to 101 on the final bar. base_high stays 100 (the recovery never closes as a
    new pivot). Fires single-session at the last bar AND in the window-sweep."""
    rise = [50.0 + (100.0 - 50.0) * i / 11 for i in range(12)]  # 12 bars, peak 100 at idx 11
    pat = [92.0, 90.0, 93.0, 89.0, 94.0, 90.0, 95.0, 91.0]
    base = [pat[i % len(pat)] for i in range(43)]               # 43 bars, all below 100
    cross = [99.0, 101.0]                                       # fresh cross on the final bar
    return rise + base + cross                                  # 57 closes; emergence at idx 56


def _write_tiingo_csv(tiingo_dir: Path, symbol: str, closes: list[float], start: date) -> None:
    idx = pd.bdate_range(start=start, periods=len(closes))
    df = pd.DataFrame(
        {
            "date": idx,
            "adjOpen": closes, "adjHigh": [c * 1.001 for c in closes],
            "adjLow": [c * 0.999 for c in closes], "adjClose": closes,
            "adjVolume": [1_000_000] * len(closes),
        }
    )
    tiingo_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(tiingo_dir / f"{symbol}.csv", index=False)


def _exemplar_csv(path: Path, rows: list[str]) -> None:
    header = (
        "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
        "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,"
        "curated,notes"
    )
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_run_harness_writes_four_artifacts_and_manifest_fields(tmp_path):
    # Minimal real-shaped run with the 5 curated ids present but synthetic Tiingo bars.
    ex = tmp_path / "ex.csv"
    _exemplar_csv(
        ex,
        [
            "twosmw-fig11-1-amzn,AMZN,pb,unmapped,1997-09,,,,,month,T,p,claude,yes,n",
            "ttlc-fig10-1-body,BODY,pb,vcp,2011-01-05,,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-6-dks,DKS,pb,double_bottom_w,2003-04,,,,,month,T,p,claude,yes,n",
            "twosmw-fig11-7-jnpr,JNPR,pb,unmapped,1999-07-30,,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n",
        ],
    )
    tdir = tmp_path / "tiingo"
    _write_tiingo_csv(tdir, "AMZN", [10.0 + i * 0.01 for i in range(800)], date(1997, 1, 2))
    _write_tiingo_csv(tdir, "BODY", [10.0 + i * 0.01 for i in range(1500)], date(2010, 10, 15))
    _write_tiingo_csv(tdir, "DKS", [10.0 + i * 0.01 for i in range(900)], date(2002, 10, 16))
    _write_tiingo_csv(tdir, "JNPR", [10.0 + i * 0.01 for i in range(30)], date(1999, 6, 25))
    _write_tiingo_csv(tdir, "YHOO", [10.0 + i * 0.01 for i in range(900)], date(1996, 4, 12))

    results, per_session, summary, manifest = run_harness(
        exemplars_csv=ex, tiingo_dir=tdir, output_dir=tmp_path / "out", bootstrap_b=10
    )
    for p in (results, per_session, summary, manifest):
        assert Path(p).exists()
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True
    assert "n_evaluable" in data
    ids = {e["exemplar_id"] for e in data["per_exemplar"]}
    assert ids == {
        "twosmw-fig11-1-amzn", "ttlc-fig10-1-body", "twosmw-fig11-6-dks",
        "twosmw-fig11-7-jnpr", "twosmw-fig11-3-yhoo",
    }
    # JNPR is below the history floor -> history-excluded; manifest records its (short) bar count.
    # (Assert the load-bearing property < 40, not an exact count -- bars_through_anchor is the slice
    # <= entry, which is fewer than the 30-bar archive since it extends a few bars past the entry.)
    jnpr = next(e for e in data["per_exemplar"] if e["exemplar_id"] == "twosmw-fig11-7-jnpr")
    assert jnpr["bars_through_anchor"] < 40
    # Every per-exemplar record carries the eligible_control_count_before_sampling field (R3.m1).
    assert all("eligible_control_count_before_sampling" in e for e in data["per_exemplar"])

    # Codex WP-R1 M1: month-precision exemplars are SWEEP-ONLY -> NO single_session results row.
    rows = list(csv.DictReader(Path(results).read_text(encoding="utf-8").splitlines()))
    month_single = [
        r for r in rows
        if r["exemplar_id"] in {"twosmw-fig11-1-amzn", "twosmw-fig11-6-dks"}
        and r["timing_mode"] == "single_session"
    ]
    assert month_single == [], "month rows must not emit a single_session results row"
    # BODY (day) DOES get both modes.
    body_modes = {r["timing_mode"] for r in rows if r["exemplar_id"] == "ttlc-fig10-1-body"}
    assert body_modes == {"single_session", "window_sweep"}

    # Codex WP-R1 C1/M2/M6: summary carries Precision, Positive-control (YHOO), Below-minimum
    # (JNPR), and the EXPLORATORY bootstrap label.
    summary_text = Path(summary).read_text(encoding="utf-8")
    assert "## Precision" in summary_text
    assert "## Positive control" in summary_text and "twosmw-fig11-3-yhoo" in summary_text
    assert "## Below-minimum" in summary_text and "twosmw-fig11-7-jnpr" in summary_text
    assert "EXPLORATORY" in summary_text  # ticker-clustered bootstrap line


def test_run_planted_body_primary_base_fires_and_wires_recall_precision(tmp_path):
    # Codex WP-R1 minor-3: a planted REAL fire (monotone bars cannot fire). BODY forms a primary
    # base emerging on its entry bar -> fires single-session AND window-sweep; recall picks it up.
    body_closes = _body_firing_closes()
    body_start = date(2010, 10, 15)
    body_idx = pd.bdate_range(start=body_start, periods=len(body_closes))
    body_entry = body_idx[-1].date()  # entry == the emergence bar (the last bar of the archive)

    ex = tmp_path / "ex.csv"
    _exemplar_csv(
        ex,
        [
            "twosmw-fig11-1-amzn,AMZN,pb,unmapped,1997-09,,,,,month,T,p,claude,yes,n",
            f"ttlc-fig10-1-body,BODY,pb,vcp,{body_entry.isoformat()},,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-6-dks,DKS,pb,double_bottom_w,2003-04,,,,,month,T,p,claude,yes,n",
            "twosmw-fig11-7-jnpr,JNPR,pb,unmapped,1999-07-30,,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n",
        ],
    )
    tdir = tmp_path / "tiingo"
    _write_tiingo_csv(tdir, "AMZN", [10.0 + i * 0.01 for i in range(800)], date(1997, 1, 2))
    _write_tiingo_csv(tdir, "BODY", body_closes, body_start)
    _write_tiingo_csv(tdir, "DKS", [10.0 + i * 0.01 for i in range(900)], date(2002, 10, 16))
    _write_tiingo_csv(tdir, "JNPR", [10.0 + i * 0.01 for i in range(30)], date(1999, 6, 25))
    _write_tiingo_csv(tdir, "YHOO", [10.0 + i * 0.01 for i in range(900)], date(1996, 4, 12))

    results, _ps, summary, _m = run_harness(
        exemplars_csv=ex, tiingo_dir=tdir, output_dir=tmp_path / "out", bootstrap_b=10
    )
    rows = list(csv.DictReader(Path(results).read_text(encoding="utf-8").splitlines()))
    body = {r["timing_mode"]: r for r in rows if r["exemplar_id"] == "ttlc-fig10-1-body"}
    assert body["window_sweep"]["fired"] == "True"
    assert body["single_session"]["fired"] == "True"
    # BODY shows up in the sub-floor sweep recall fired list.
    assert "ttlc-fig10-1-body" in Path(summary).read_text(encoding="utf-8")


def test_run_harness_raises_value_error_for_missing_csv(tmp_path):
    with pytest.raises(ValueError):
        run_harness(
            exemplars_csv=tmp_path / "nope.csv", tiingo_dir=tmp_path, output_dir=tmp_path / "o"
        )


def _section(summary_text: str, heading: str) -> str:
    """The block of lines under `heading` up to the next `## ` heading (heading-exclusive)."""
    lines = summary_text.splitlines()
    out: list[str] = []
    grabbing = False
    for ln in lines:
        if ln.startswith("## "):
            if grabbing:
                break
            grabbing = ln.startswith(heading)
            continue
        if grabbing:
            out.append(ln)
    return "\n".join(out)


def test_missing_sub_floor_archive_is_data_unavailable_not_history_excluded(tmp_path):
    # Codex EP-R1 M1: a sub_floor name whose Tiingo archive is MISSING (full=None,
    # bars_through_anchor=0) must be reported as DATA-UNAVAILABLE, NOT as below Minervini's history
    # floor -- otherwise a data-availability failure masquerades as a substantive Ch.11 finding and
    # corrupts the stratified denominator. WRONG-PATH (gate only on bars < MIN_HISTORY_BARS) lists
    # the missing name under "## Below-minimum"; RIGHT-PATH (also gate on full is not None) lists it
    # under "## Data unavailable" and NOT under "## Below-minimum".
    ex = tmp_path / "ex.csv"
    _exemplar_csv(
        ex,
        [
            "twosmw-fig11-1-amzn,AMZN,pb,unmapped,1997-09,,,,,month,T,p,claude,yes,n",
            "ttlc-fig10-1-body,BODY,pb,vcp,2011-01-05,,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-6-dks,DKS,pb,double_bottom_w,2003-04,,,,,month,T,p,claude,yes,n",
            "twosmw-fig11-7-jnpr,JNPR,pb,unmapped,1999-07-30,,,,,day,T,p,claude,yes,n",
            "twosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n",
        ],
    )
    tdir = tmp_path / "tiingo"
    # DKS (sub_floor, month) archive DELIBERATELY OMITTED -> data_source == "no_data".
    _write_tiingo_csv(tdir, "AMZN", [10.0 + i * 0.01 for i in range(800)], date(1997, 1, 2))
    _write_tiingo_csv(tdir, "BODY", [10.0 + i * 0.01 for i in range(1500)], date(2010, 10, 15))
    _write_tiingo_csv(tdir, "JNPR", [10.0 + i * 0.01 for i in range(30)], date(1999, 6, 25))
    _write_tiingo_csv(tdir, "YHOO", [10.0 + i * 0.01 for i in range(900)], date(1996, 4, 12))

    _r, _ps, summary, manifest = run_harness(
        exemplars_csv=ex, tiingo_dir=tdir, output_dir=tmp_path / "out", bootstrap_b=10
    )
    summary_text = Path(summary).read_text(encoding="utf-8")
    assert "## Data unavailable" in summary_text
    data_unavail = _section(summary_text, "## Data unavailable")
    below_min = _section(summary_text, "## Below-minimum")
    assert "twosmw-fig11-6-dks" in data_unavail
    assert "twosmw-fig11-6-dks" not in below_min
    # JNPR (present, 30 bars < 40) stays a genuine history-exclusion (NOT data-unavailable).
    assert "twosmw-fig11-7-jnpr" in below_min
    assert "twosmw-fig11-7-jnpr" not in data_unavail
    # Manifest still records the missing name with data_source == "no_data".
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    dks = next(e for e in data["per_exemplar"] if e["exemplar_id"] == "twosmw-fig11-6-dks")
    assert dks["data_source"] == "no_data"
