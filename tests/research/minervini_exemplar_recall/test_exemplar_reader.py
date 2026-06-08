# tests/research/minervini_exemplar_recall/test_exemplar_reader.py
from __future__ import annotations

from datetime import date

import pytest

_HEADER = (
    "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
    "stop_price,base_start_date,base_end_date,date_precision,source,page,"
    "extracted_by,curated,notes"
)


def _write(path, rows):
    path.write_text(_HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_filters_curated_yes_only(tmp_path):
    from research.harness.minervini_exemplar_recall.exemplar_reader import read_exemplars

    csv = tmp_path / "ex.csv"
    _write(
        csv,
        [
            "id-a,CRUS,VCP,vcp,2010-03-30,8.09,,,,exact,TWoSMW,Fig 10.34,claude,yes,n",
            "id-b,FSII,cup,cup_with_handle,1995-02,,,,,month,TWoSMW,Fig 10.3,claude,no,excluded",
        ],
    )
    rows = read_exemplars(csv)
    # WRONG-PATH (no filter): 2 rows.  RIGHT-PATH (curated==yes): 1 row.
    assert len(rows) == 1
    assert rows[0].exemplar_id == "id-a"


def test_parses_entry_anchor_all_three_precisions(tmp_path):
    from research.harness.minervini_exemplar_recall.exemplar_reader import read_exemplars

    csv = tmp_path / "ex.csv"
    _write(
        csv,
        [
            "id-day,AAA,VCP,vcp,2010-03-30,,,,,day,S,P,claude,yes,n",
            "id-mon,BBB,VCP,vcp,1995-02,,,,,month,S,P,claude,yes,n",
            "id-yr,CCC,VCP,vcp,2001,,,,,year,S,P,claude,yes,n",
        ],
    )
    by_id = {r.exemplar_id: r for r in read_exemplars(csv)}
    assert by_id["id-day"].entry_anchor == date(2010, 3, 30)
    # missing day -> 1st; missing month -> July (mid-period defaults from tiingo_pull.entry_anchor)
    assert by_id["id-mon"].entry_anchor == date(1995, 2, 1)
    assert by_id["id-yr"].entry_anchor == date(2001, 7, 1)
    assert by_id["id-mon"].date_precision == "month"


def test_resolves_tiingo_symbol_and_price(tmp_path):
    from research.harness.minervini_exemplar_recall.exemplar_reader import read_exemplars

    csv = tmp_path / "ex.csv"
    _write(
        csv,
        [
            "id-emex,EMEX,HTF,high_tight_flag,2001,,,,,year,S,P,claude,yes,n",
            "id-crus,CRUS,VCP,vcp,2010-03-30,8.09,,,,exact,S,P,claude,yes,n",
        ],
    )
    by_id = {r.exemplar_id: r for r in read_exemplars(csv)}
    assert by_id["id-emex"].tiingo_symbol == "ELX"  # SYMBOL_OVERRIDE applied
    assert by_id["id-crus"].buy_point_price == pytest.approx(8.09)
    assert by_id["id-emex"].buy_point_price is None  # empty -> None


def test_malformed_entry_date_raises(tmp_path):
    from research.harness.minervini_exemplar_recall.exceptions import MalformedExemplarRowError
    from research.harness.minervini_exemplar_recall.exemplar_reader import read_exemplars

    csv = tmp_path / "ex.csv"
    _write(csv, ["id-bad,AAA,VCP,vcp,not-a-date,,,,,day,S,P,claude,yes,n"])
    with pytest.raises(MalformedExemplarRowError, match="id-bad"):
        read_exemplars(csv)
