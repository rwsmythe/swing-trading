from __future__ import annotations

import json

import pytest

from research.harness.minervini_primary_base_recall import output


def test_results_csv_has_spec_header_and_rows(tmp_path):
    path = tmp_path / "results.csv"
    output.write_results_csv(
        [
            {
                "exemplar_id": "twosmw-fig11-1-amzn", "ticker": "AMZN", "role": "sub_floor",
                "timing_mode": "window_sweep", "fired": "True", "first_rejecting_criterion": "",
                "base_start_date": "1997-07-01", "base_high": "5.1",
                "correction_depth_pct": "0.23", "base_duration_bars": "30",
                "emergence_close": "5.2", "data_source": "tiingo",
                "bars_through_anchor": "75", "date_precision": "month",
            }
        ],
        path,
    )
    head = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head == list(output.RESULTS_HEADER)
    assert "first_rejecting_criterion" in head


def test_manifest_has_spec_required_fields(tmp_path):
    path = tmp_path / "manifest.json"
    output.write_manifest_json(
        {
            "n_evaluable": 3,
            "per_exemplar": [
                {"exemplar_id": "twosmw-fig11-1-amzn", "bars_through_anchor": 75,
                 "date_precision": "month", "role": "sub_floor",
                 "eligible_control_count_before_sampling": 309},
            ],
            "thresholds": {"MIN_HISTORY_BARS": 40},
            "control_params": {"control_k": 5, "control_seed": 20260608, "max_control_age_bars": 504},
            "started_iso_utc": "20260609T000000Z", "finished_iso_utc": "20260609T000100Z",
        },
        path,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True   # write_manifest_json sets the default
    assert data["per_exemplar"][0]["eligible_control_count_before_sampling"] == 309
    assert data["n_evaluable"] == 3


def test_ascii_guard_rejects_non_ascii(tmp_path):
    # spec section 8 is ASCII-only -- STRICTER than cp1252. An em dash (U+2014) is VALID cp1252 but
    # NOT ASCII; the guard MUST reject it. WRONG-PATH (cp1252 guard) would ACCEPT it and write the
    # file; RIGHT-PATH (ascii guard) raises UnicodeEncodeError. The U+2014 char is built via
    # chr(0x2014) so THIS test source stays ASCII-only too (Codex WP-R2 M3) -- do NOT paste a
    # literal em dash here.
    bad_line = "recall " + chr(0x2014) + " ok"  # contains U+2014 at runtime; ASCII in source
    with pytest.raises(UnicodeEncodeError):
        output.write_summary_md([bad_line], tmp_path / "summary.md")
