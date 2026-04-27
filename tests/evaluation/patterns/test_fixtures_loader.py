"""Helper-module tests for `_fixtures.load_labeled_fixtures` (Task 7.2).

Synthetic CSV+JSON pairs in `tmp_path` only. Real fixture directory
(`tests/evaluation/patterns/fixtures/`) is operator-only (Task 7.3).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tests.evaluation.patterns._fixtures import (
    LabeledFixture,
    load_labeled_fixtures,
)


def _write_synthetic_pair(
    dir_path: Path,
    stem: str,
    *,
    label: str,
    notes: str = "",
    expected_confidence_min: float | None = None,
    rows: int = 60,
) -> None:
    """Write paired CSV (Date index + OHLCV) + JSON metadata under `dir_path`."""
    dates = pd.date_range("2026-01-02", periods=rows, freq="B")
    df = pd.DataFrame(
        {
            "Open": [10.0 + i for i in range(rows)],
            "High": [11.0 + i for i in range(rows)],
            "Low": [9.5 + i for i in range(rows)],
            "Close": [10.5 + i for i in range(rows)],
            "Volume": [1_000_000 + i for i in range(rows)],
        },
        index=pd.Index(dates, name="Date"),
    )
    df.to_csv(dir_path / f"{stem}.csv")
    meta: dict[str, object] = {"label": label, "notes": notes}
    if expected_confidence_min is not None:
        meta["expected_confidence_min"] = expected_confidence_min
    (dir_path / f"{stem}.json").write_text(json.dumps(meta))


def test_load_labeled_fixtures_empty_dir_returns_empty_list(tmp_path: Path) -> None:
    """Fresh empty directory must yield an empty list (deterministic baseline)."""
    assert load_labeled_fixtures(tmp_path) == []


def test_load_labeled_fixtures_missing_dir_returns_empty_list(tmp_path: Path) -> None:
    """Per brief §5: missing directory returns []."""
    nonexistent = tmp_path / "does_not_exist"
    assert not nonexistent.exists()
    assert load_labeled_fixtures(nonexistent) == []


def test_load_labeled_fixtures_skips_unpaired_json(tmp_path: Path) -> None:
    """Per brief §5: JSON without paired CSV is silently skipped (loop iterates *.csv only)."""
    # Write only the JSON, no matching CSV.
    (tmp_path / "ORPHAN_2026-04-26_flag.json").write_text(
        '{"label": "flag", "notes": "orphan"}'
    )
    result = load_labeled_fixtures(tmp_path)
    assert result == []


def test_load_labeled_fixtures_pairs_csv_and_json(tmp_path: Path) -> None:
    """Paired CSV + JSON yield one LabeledFixture; fields exact-match."""
    _write_synthetic_pair(
        tmp_path,
        "AAPL_2026-04-26_flag",
        label="flag",
        notes="textbook bull-flag continuation",
        expected_confidence_min=0.55,
        rows=60,
    )
    fixtures = load_labeled_fixtures(tmp_path)
    assert len(fixtures) == 1
    fx = fixtures[0]
    assert isinstance(fx, LabeledFixture)
    assert fx.name == "AAPL_2026-04-26_flag"
    assert fx.label == "flag"
    assert fx.notes == "textbook bull-flag continuation"
    assert fx.expected_confidence_min == 0.55
    # Per Codex R1 M3: loader trims to exactly 60 bars per spec §4.2 contract.
    assert len(fx.bars) == 60
    # Discriminating: confirm the DataFrame has the OHLCV columns we wrote.
    assert list(fx.bars.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_load_labeled_fixtures_skips_unpaired_csv(tmp_path: Path) -> None:
    """A CSV without a matching JSON sibling is silently skipped."""
    # Only the CSV, no .json sibling.
    pd.DataFrame(
        {
            "Open": [1.0],
            "High": [1.0],
            "Low": [1.0],
            "Close": [1.0],
            "Volume": [1],
        },
        index=pd.Index(pd.date_range("2026-01-02", periods=1), name="Date"),
    ).to_csv(tmp_path / "ORPHAN_2026-04-26_flag.csv")
    assert load_labeled_fixtures(tmp_path) == []


def test_load_labeled_fixtures_returns_sorted_by_name(tmp_path: Path) -> None:
    """Result is sorted by stem so pytest parametrize ids are deterministic."""
    _write_synthetic_pair(tmp_path, "BBB_2026-04-26_flag", label="flag")
    _write_synthetic_pair(tmp_path, "AAA_2026-04-26_none", label="none")
    names = [fx.name for fx in load_labeled_fixtures(tmp_path)]
    assert names == ["AAA_2026-04-26_none", "BBB_2026-04-26_flag"]


def test_load_labeled_fixtures_raises_clear_error_on_malformed_json(
    tmp_path: Path,
) -> None:
    """Malformed JSON raises JSONDecodeError with the file path in the message
    (operator-debuggability over silent skip)."""
    # Valid CSV.
    pd.DataFrame(
        {
            "Open": [1.0],
            "High": [1.0],
            "Low": [1.0],
            "Close": [1.0],
            "Volume": [1],
        },
        index=pd.Index(pd.date_range("2026-01-02", periods=1), name="Date"),
    ).to_csv(tmp_path / "BROKEN_2026-04-26_flag.csv")
    # Corrupt JSON sibling.
    (tmp_path / "BROKEN_2026-04-26_flag.json").write_text("{ not valid json")

    with pytest.raises(json.JSONDecodeError) as excinfo:
        load_labeled_fixtures(tmp_path)
    assert "BROKEN_2026-04-26_flag.json" in str(excinfo.value)


def test_load_labeled_fixtures_raises_clear_error_on_malformed_csv(
    tmp_path: Path,
) -> None:
    """Per brief §5: malformed CSV (empty / missing OHLCV columns) raises
    ValueError with the file path in the message (symmetric with malformed-JSON
    behavior)."""
    csv_path = tmp_path / "BROKEN_2026-04-26_flag.csv"
    csv_path.write_text("not,a,csv\nat all\n")  # parses as 1 row, no Date/OHLCV columns
    (tmp_path / "BROKEN_2026-04-26_flag.json").write_text(
        '{"label": "flag", "notes": "n/a"}'
    )
    with pytest.raises(ValueError) as excinfo:
        load_labeled_fixtures(tmp_path)
    msg = str(excinfo.value)
    assert "BROKEN_2026-04-26_flag.csv" in msg
    assert "Malformed CSV" in msg


def test_load_labeled_fixtures_raises_clear_error_on_csv_parser_failure(
    tmp_path: Path,
) -> None:
    """Per Codex R1 M1: real pandas parser failures (binary content, encoding
    errors) raise ValueError with the file path, not pandas internal exception
    types."""
    csv_path = tmp_path / "BINARY_2026-04-26_flag.csv"
    csv_path.write_bytes(
        b"\xff\xfe\xfd\xfc\xfb\xfa\x00\x01\x02\x03 totally not utf-8"
    )
    (tmp_path / "BINARY_2026-04-26_flag.json").write_text(
        '{"label": "flag", "notes": "binary garbage"}'
    )
    with pytest.raises(ValueError) as excinfo:
        load_labeled_fixtures(tmp_path)
    msg = str(excinfo.value)
    assert "BINARY_2026-04-26_flag.csv" in msg
    assert "parser error" in msg.lower()


def test_load_labeled_fixtures_raises_on_non_dict_json_root(tmp_path: Path) -> None:
    """Per Codex R3 M1: JSON root must be an object (not list/string/number)."""
    pd.DataFrame(
        {"Open": [1.0]*60, "High": [1.0]*60, "Low": [1.0]*60, "Close": [1.0]*60, "Volume": [1]*60},
        index=pd.Index(pd.date_range("2026-01-02", periods=60, freq="B"), name="Date"),
    ).to_csv(tmp_path / "BAD_2026-04-26_flag.csv")
    # Valid JSON, but root is a list, not an object.
    (tmp_path / "BAD_2026-04-26_flag.json").write_text("[]")
    with pytest.raises(ValueError, match="must be an object"):
        load_labeled_fixtures(tmp_path)


def test_load_labeled_fixtures_raises_on_invalid_label(tmp_path: Path) -> None:
    """Per Codex R1 M2: label outside {flag, none} raises ValueError with path."""
    _write_synthetic_pair(tmp_path, "BAD_2026-04-26_flag", label="pennant")
    with pytest.raises(ValueError, match="Invalid label"):
        load_labeled_fixtures(tmp_path)


def test_load_labeled_fixtures_raises_on_missing_notes(tmp_path: Path) -> None:
    """Per Codex R2 M2 + README §2: notes field is required (operator rationale)."""
    pd.DataFrame(
        {"Open": [1.0]*60, "High": [1.0]*60, "Low": [1.0]*60, "Close": [1.0]*60, "Volume": [1]*60},
        index=pd.Index(pd.date_range("2026-01-02", periods=60, freq="B"), name="Date"),
    ).to_csv(tmp_path / "BAD_2026-04-26_flag.csv")
    (tmp_path / "BAD_2026-04-26_flag.json").write_text(
        '{"label": "flag"}'
    )
    with pytest.raises(ValueError, match="Missing required 'notes' field"):
        load_labeled_fixtures(tmp_path)


def test_load_labeled_fixtures_raises_on_non_numeric_expected_confidence_min(
    tmp_path: Path,
) -> None:
    """Per Codex R1 M2: expected_confidence_min must be a number, not a string."""
    # Write a fixture with string expected_confidence_min via direct JSON write.
    pd.DataFrame(
        {
            "Open": [1.0] * 60,
            "High": [1.0] * 60,
            "Low": [1.0] * 60,
            "Close": [1.0] * 60,
            "Volume": [1] * 60,
        },
        index=pd.Index(
            pd.date_range("2026-01-02", periods=60, freq="B"), name="Date"
        ),
    ).to_csv(tmp_path / "BAD_2026-04-26_flag.csv")
    (tmp_path / "BAD_2026-04-26_flag.json").write_text(
        '{"label": "flag", "notes": "bad type", "expected_confidence_min": "0.7"}'
    )
    with pytest.raises(ValueError, match="expected_confidence_min"):
        load_labeled_fixtures(tmp_path)


def test_load_labeled_fixtures_raises_on_out_of_range_expected_confidence_min(
    tmp_path: Path,
) -> None:
    """Per Codex R1 M2: expected_confidence_min must be in [0.0, 1.0]."""
    pd.DataFrame(
        {
            "Open": [1.0] * 60,
            "High": [1.0] * 60,
            "Low": [1.0] * 60,
            "Close": [1.0] * 60,
            "Volume": [1] * 60,
        },
        index=pd.Index(
            pd.date_range("2026-01-02", periods=60, freq="B"), name="Date"
        ),
    ).to_csv(tmp_path / "BAD_2026-04-26_flag.csv")
    (tmp_path / "BAD_2026-04-26_flag.json").write_text(
        '{"label": "flag", "notes": "out of range", "expected_confidence_min": 1.5}'
    )
    with pytest.raises(ValueError, match="out of range"):
        load_labeled_fixtures(tmp_path)


def test_load_labeled_fixtures_raises_on_expected_confidence_min_on_none_fixture(
    tmp_path: Path,
) -> None:
    """Per Codex R1 M2 + README §2: expected_confidence_min only allowed on
    'flag' fixtures."""
    pd.DataFrame(
        {
            "Open": [1.0] * 60,
            "High": [1.0] * 60,
            "Low": [1.0] * 60,
            "Close": [1.0] * 60,
            "Volume": [1] * 60,
        },
        index=pd.Index(
            pd.date_range("2026-01-02", periods=60, freq="B"), name="Date"
        ),
    ).to_csv(tmp_path / "BAD_2026-04-26_none.csv")
    (tmp_path / "BAD_2026-04-26_none.json").write_text(
        '{"label": "none", "notes": "no floor allowed", "expected_confidence_min": 0.5}'
    )
    with pytest.raises(ValueError, match="not allowed on 'none' fixture"):
        load_labeled_fixtures(tmp_path)


def test_load_labeled_fixtures_trims_to_last_60_bars(tmp_path: Path) -> None:
    """Per Codex R1 M3 + R2 Minor 2 + spec §4.2: loader trims to last 60 rows
    (not first 60 or arbitrary slice)."""
    rows = 63  # 3 surplus rows
    dates = pd.date_range("2026-01-02", periods=rows, freq="B")
    # Per-row distinguishable Close values: first 3 rows have Close ∈ {0,1,2};
    # last 60 rows have Close ∈ {3..62}. Asserting Close[0] == 3 (not 0)
    # proves the last 60 were retained.
    df = pd.DataFrame(
        {
            "Open": [10.0 + i for i in range(rows)],
            "High": [11.0 + i for i in range(rows)],
            "Low": [9.5 + i for i in range(rows)],
            "Close": list(range(rows)),
            "Volume": [1_000_000 + i for i in range(rows)],
        },
        index=pd.Index(dates, name="Date"),
    )
    df.to_csv(tmp_path / "AAPL_2026-04-26_flag.csv")
    (tmp_path / "AAPL_2026-04-26_flag.json").write_text(
        '{"label": "flag", "notes": "trim test"}'
    )
    fixtures = load_labeled_fixtures(tmp_path)
    assert len(fixtures) == 1
    bars = fixtures[0].bars
    assert len(bars) == 60
    # Discriminating: confirm we got the LAST 60 rows (Close 3..62), not first 60 (0..59).
    assert bars["Close"].iloc[0] == 3
    assert bars["Close"].iloc[-1] == 62


def test_load_labeled_fixtures_raises_on_fewer_than_60_bars(tmp_path: Path) -> None:
    """Per Codex R1 M3 + spec §4.2: input <60 rows raises ValueError."""
    _write_synthetic_pair(
        tmp_path, "AAPL_2026-04-26_flag", label="flag", rows=59
    )
    with pytest.raises(ValueError, match="≥60 daily bars"):
        load_labeled_fixtures(tmp_path)


def test_load_labeled_fixtures_raises_on_non_utf8_json(tmp_path: Path) -> None:
    """Per Codex R4 M1: non-UTF-8 JSON file raises ValueError with path
    (not bare UnicodeDecodeError)."""
    pd.DataFrame(
        {"Open": [1.0]*60, "High": [1.0]*60, "Low": [1.0]*60, "Close": [1.0]*60, "Volume": [1]*60},
        index=pd.Index(pd.date_range("2026-01-02", periods=60, freq="B"), name="Date"),
    ).to_csv(tmp_path / "BAD_2026-04-26_flag.csv")
    # Bytes that are not valid UTF-8 (CP1252 with high-byte garbage).
    (tmp_path / "BAD_2026-04-26_flag.json").write_bytes(
        b"\xff\xfe { \"label\": \"flag\", \"notes\": \"latin1\" }"
    )
    with pytest.raises(ValueError, match="Invalid UTF-8 encoding"):
        load_labeled_fixtures(tmp_path)
