# tests/research/minervini_exemplar_recall/test_output.py
from __future__ import annotations

import csv
import json

from research.harness.minervini_exemplar_recall.output import (
    RESULTS_HEADER,
    write_manifest_json,
    write_results_csv,
)


def _row(**kw):
    base = {
        "exemplar_id": "a", "ticker": "CRUS", "timing_mode": "window_sweep",
        "h1_outcome": "surfaced_aplus", "best_bucket": "aplus", "first_rejecting_gate": "",
        "h2_fired_faithful": "True", "h2_fired_isolated": "True",
        "fired_classes_faithful": "vcp", "fired_classes_isolated": "vcp",
        "rs_path": "P0", "data_source": "tiingo", "n_bars": "250", "screenable": "True",
        "h2_anchor_mode_limited_possible": "False", "h2_anchor_mode_limited_reason": "",
    }
    base.update(kw)
    return base


def test_results_csv_header_and_ascii(tmp_path):
    path = tmp_path / "results.csv"
    write_results_csv([_row()], path)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
    assert header == list(RESULTS_HEADER)
    # ASCII / cp1252 round-trip must not raise.
    path.read_text(encoding="utf-8").encode("cp1252")


def test_manifest_has_l2_lock_and_config_snapshot(tmp_path):
    path = tmp_path / "manifest.json"
    write_manifest_json({"harness_version": "0.1.0", "config_snapshot": {"min_passes": 7}}, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True
    assert data["config_snapshot"]["min_passes"] == 7
