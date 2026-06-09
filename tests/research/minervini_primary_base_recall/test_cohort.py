from __future__ import annotations

from pathlib import Path

import pytest

from research.harness.minervini_primary_base_recall.cohort import (
    CURATED_COHORT,
    resolve_cohort,
)
from research.harness.minervini_primary_base_recall.exceptions import UnknownExemplarIdError

_REAL_CSV = Path("research/data/minervini-exemplars.csv")


def test_curated_cohort_is_the_five_documented_ids_with_roles():
    by_id = {m.exemplar_id: m for m in CURATED_COHORT}
    assert set(by_id) == {
        "twosmw-fig11-1-amzn", "ttlc-fig10-1-body", "twosmw-fig11-6-dks",
        "twosmw-fig11-7-jnpr", "twosmw-fig11-3-yhoo",
    }
    # MELI is deliberately absent (young-VCP, R1.M4).
    assert "twosmw-fig10-33-meli" not in by_id
    assert by_id["twosmw-fig11-3-yhoo"].role == "positive_control"
    assert by_id["twosmw-fig11-1-amzn"].role == "sub_floor"
    assert by_id["ttlc-fig10-1-body"].role == "sub_floor"
    assert all(m.book_citation for m in CURATED_COHORT)


@pytest.mark.skipif(not _REAL_CSV.exists(), reason="real exemplar CSV not present")
def test_resolve_cohort_pairs_each_member_with_its_exemplar_row():
    resolved = resolve_cohort(_REAL_CSV)
    assert {r.member.exemplar_id for r in resolved} == {m.exemplar_id for m in CURATED_COHORT}
    amzn = next(r for r in resolved if r.member.exemplar_id == "twosmw-fig11-1-amzn")
    assert amzn.row.ticker == "AMZN"
    assert amzn.row.date_precision == "month"   # drives sweep-only timing
    body = next(r for r in resolved if r.member.exemplar_id == "ttlc-fig10-1-body")
    assert body.row.date_precision == "day"


def test_resolve_rejects_unknown_id(tmp_path):
    # A CSV missing one curated id -> UnknownExemplarIdError (not a silent drop).
    csv = tmp_path / "ex.csv"
    header = (
        "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
        "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes"
    )
    # Only one of the five curated ids present.
    csv.write_text(
        header + "\ntwosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n\n",
        encoding="utf-8",
    )
    with pytest.raises(UnknownExemplarIdError):
        resolve_cohort(csv)
