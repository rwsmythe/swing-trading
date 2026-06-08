# tests/research/minervini_exemplar_recall/test_stage_db.py
from __future__ import annotations

from datetime import date

import pytest

from swing.data.models import CriterionResult

TT_NAMES = ["TT1", "TT2", "TT3", "TT4", "TT5", "TT6", "TT7", "TT8"]


def _tt(results):  # list of 8 result strings
    return tuple(CriterionResult(TT_NAMES[i], "trend_template", results[i]) for i in range(8))


def test_faithful_stage2_iff_eight_passes(tmp_path):
    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db, seed_session, stage_at

    conn = build_stage_db(tmp_path / "faithful.db")
    session = date(2010, 3, 30)
    # 8/8 pass -> stage_2.
    seed_session(conn, ticker="AAA", session=session, tt_results=_tt(["pass"] * 8), mode="faithful")
    assert stage_at(conn, "AAA", session) == "stage_2"


def test_faithful_seven_passes_is_not_stage2(tmp_path):
    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db, seed_session, stage_at

    conn = build_stage_db(tmp_path / "faithful.db")
    session = date(2010, 3, 30)
    # 7 pass + 1 fail -> pass_count 7 != 8 -> undefined.
    # WRONG-PATH (count any rows): stage_2.  RIGHT-PATH (count result='pass' == 8): undefined.
    seed_session(conn, ticker="BBB", session=session, tt_results=_tt(["pass"] * 7 + ["fail"]), mode="faithful")
    assert stage_at(conn, "BBB", session) == "undefined"


def test_isolated_always_stage2(tmp_path):
    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db, seed_session, stage_at

    conn = build_stage_db(tmp_path / "isolated.db")
    session = date(2010, 3, 30)
    # isolated ignores tt_results and forces 8 pass.
    seed_session(conn, ticker="CCC", session=session, tt_results=_tt(["fail"] * 8), mode="isolated")
    assert stage_at(conn, "CCC", session) == "stage_2"


def test_schema_built_at_expected_version(tmp_path):
    from swing.data.db import EXPECTED_SCHEMA_VERSION
    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db

    conn = build_stage_db(tmp_path / "x.db")
    # swing tracks schema version in the schema_version TABLE, not PRAGMA user_version.
    # WRONG-PATH (PRAGMA user_version): returns 0 -> test fails on a correctly-built v24 DB.
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row[0] == EXPECTED_SCHEMA_VERSION


def test_faithful_rejects_wrong_count_or_duplicate_tt_rows(tmp_path):
    import pytest

    from research.harness.minervini_exemplar_recall.stage_db import build_stage_db, seed_session

    conn = build_stage_db(tmp_path / "faithful.db")
    session = date(2010, 3, 30)
    # 7 rows -> rejected.
    with pytest.raises(ValueError, match="8"):
        seed_session(conn, ticker="AAA", session=session,
                     tt_results=tuple(CriterionResult(TT_NAMES[i], "trend_template", "pass") for i in range(7)),
                     mode="faithful")
    # 8 rows but a DUPLICATE name (TT1 twice, TT8 missing) -> rejected, because current_stage counts
    # result='pass' rows blindly and 8 duplicate passes would falsely seed stage_2 (spec section 6.1).
    dup = tuple(CriterionResult("TT1", "trend_template", "pass") for _ in range(8))
    with pytest.raises(ValueError, match="UNIQUE"):
        seed_session(conn, ticker="BBB", session=session, tt_results=dup, mode="faithful")
