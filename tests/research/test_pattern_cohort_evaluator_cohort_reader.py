"""Tests for pattern cohort harness cohort_reader (Mode (a) inline + Mode (b) CSV)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from research.harness.pattern_cohort_evaluator.cohort_reader import (
    CohortEntry,
    parse_asof_date,
    parse_inline_cohort,
    read_cohort_csv,
)
from research.harness.pattern_cohort_evaluator.exceptions import (
    CohortInputSchemaError,
    MalformedAsofDateError,
)

# ---------------------------------------------------------------------------
# parse_inline_cohort
# ---------------------------------------------------------------------------

def test_parse_inline_cohort_returns_entries():
    entries = parse_inline_cohort("RLMD:2026-04-15,DNTH:2026-04-15")
    assert len(entries) == 2
    assert entries[0].ticker == "RLMD"
    assert entries[0].asof_date == date(2026, 4, 15)
    assert entries[1].ticker == "DNTH"


def test_parse_inline_cohort_uppercases_ticker():
    entries = parse_inline_cohort("rlmd:2026-04-15")
    assert entries[0].ticker == "RLMD"


def test_parse_inline_cohort_skips_empty_pairs():
    entries = parse_inline_cohort("RLMD:2026-04-15,,DNTH:2026-04-15,")
    assert len(entries) == 2


def test_parse_inline_cohort_rejects_missing_colon():
    with pytest.raises(CohortInputSchemaError, match="exactly one ':' separator"):
        parse_inline_cohort("RLMD2026-04-15")


def test_parse_inline_cohort_rejects_multiple_colons():
    with pytest.raises(CohortInputSchemaError, match="exactly one ':' separator"):
        parse_inline_cohort("RLMD:2026:04-15")


def test_parse_inline_cohort_rejects_empty_string():
    with pytest.raises(CohortInputSchemaError, match="zero entries"):
        parse_inline_cohort("")


def test_parse_inline_cohort_malformed_date_raises_typed():
    with pytest.raises(MalformedAsofDateError, match="malformed"):
        parse_inline_cohort("RLMD:2026-13-99")


# ---------------------------------------------------------------------------
# parse_asof_date
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["", "2026-13-01", "April 15 2026", "not-a-date"])
def test_parse_asof_date_typed_raise(bad):
    with pytest.raises(MalformedAsofDateError):
        parse_asof_date(bad)


# ---------------------------------------------------------------------------
# read_cohort_csv
# ---------------------------------------------------------------------------

def _write_csv(path: Path, header: str, *rows: str) -> Path:
    path.write_text(header + "\n" + "\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return path


def test_read_cohort_csv_minimal(tmp_path):
    p = _write_csv(
        tmp_path / "cohort.csv",
        "ticker,asof_date",
        "RLMD,2026-04-15",
        "DNTH,2026-04-15",
    )
    entries = read_cohort_csv(p)
    assert len(entries) == 2
    assert entries[0] == CohortEntry(ticker="RLMD", asof_date=date(2026, 4, 15))


def test_read_cohort_csv_full_schema(tmp_path):
    p = _write_csv(
        tmp_path / "cohort.csv",
        "ticker,asof_date,candidate_id,eval_run_id,bucket,pivot,initial_stop,pattern_class_filter,cohort_label",
        "RLMD,2026-04-15,1234,67,watch,10.5,9.5,vcp,tightness_1.005",
    )
    entries = read_cohort_csv(p)
    assert len(entries) == 1
    e = entries[0]
    assert e.candidate_id == 1234
    assert e.eval_run_id == 67
    assert e.bucket == "watch"
    assert e.pivot == 10.5
    assert e.initial_stop == 9.5
    assert e.pattern_class_filter == "vcp"
    assert e.cohort_label == "tightness_1.005"


def test_read_cohort_csv_empty_strings_coerce_to_none(tmp_path):
    p = _write_csv(
        tmp_path / "cohort.csv",
        "ticker,asof_date,candidate_id,bucket,pivot",
        "RLMD,2026-04-15,,,",
    )
    entries = read_cohort_csv(p)
    assert entries[0].candidate_id is None
    assert entries[0].bucket is None
    assert entries[0].pivot is None


def test_read_cohort_csv_missing_required_column(tmp_path):
    p = _write_csv(tmp_path / "cohort.csv", "ticker", "RLMD")
    with pytest.raises(CohortInputSchemaError, match="missing required columns"):
        read_cohort_csv(p)


def test_read_cohort_csv_unrecognized_column(tmp_path):
    p = _write_csv(
        tmp_path / "cohort.csv",
        "ticker,asof_date,bogus_field",
        "RLMD,2026-04-15,xyz",
    )
    with pytest.raises(CohortInputSchemaError, match="unrecognized columns"):
        read_cohort_csv(p)


def test_read_cohort_csv_header_only_returns_empty_tuple(tmp_path):
    """Per gotcha #18 (Expansion #4 sub-refinement): empty input must NOT raise."""
    p = tmp_path / "cohort.csv"
    p.write_text("ticker,asof_date\n", encoding="utf-8")
    entries = read_cohort_csv(p)
    assert entries == ()


def test_read_cohort_csv_bad_pattern_class_filter_raises(tmp_path):
    p = _write_csv(
        tmp_path / "cohort.csv",
        "ticker,asof_date,pattern_class_filter",
        "RLMD,2026-04-15,not_a_real_class",
    )
    with pytest.raises(CohortInputSchemaError, match="pattern_class_filter"):
        read_cohort_csv(p)


def test_read_cohort_csv_bad_int_field_raises(tmp_path):
    p = _write_csv(
        tmp_path / "cohort.csv",
        "ticker,asof_date,candidate_id",
        "RLMD,2026-04-15,not_an_int",
    )
    with pytest.raises(CohortInputSchemaError, match="int field malformed"):
        read_cohort_csv(p)


def test_cohort_entry_post_init_rejects_empty_ticker():
    with pytest.raises(CohortInputSchemaError, match="non-empty str"):
        CohortEntry(ticker="", asof_date=date(2026, 4, 15))


def test_cohort_entry_post_init_rejects_non_date_asof():
    with pytest.raises(CohortInputSchemaError, match="datetime.date"):
        CohortEntry(ticker="RLMD", asof_date="2026-04-15")  # type: ignore[arg-type]


def test_cohort_entry_post_init_rejects_unknown_pattern_class_filter():
    with pytest.raises(CohortInputSchemaError, match="pattern_class_filter"):
        CohortEntry(
            ticker="RLMD",
            asof_date=date(2026, 4, 15),
            pattern_class_filter="not_a_real_class",
        )
