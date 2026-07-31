"""ITEM 2 -- a CHILDLESS displaced cycle MAY NOT VANISH (RD ruling, 2026-07-30).

THE BIAS IS THE DANGEROUS KIND: a failed first attempt goes permanently
unmeasured while its accepted retry supplies the scored agreement. That is not a
null -- it is A SUBSTITUTION OF A SUCCESS FOR A FAILURE, which is worse than
silence.

RULED: the displaced cycle must be REPRESENTED. Either an affordance can answer
it, OR -- if genuinely unanswerable by construction -- it is counted in a
VISIBLE, NAMED category (`displaced_unanswerable`) that appears in the report,
and the agreement rate discloses how many cycles it excluded. FORBIDDEN: the
retry silently standing in for it.

BOTH ARE IMPLEMENTED, deliberately. The affordance closes it while the latch is
still on the panel; the named category closes it for every cycle the operator
never answers -- and an affordance nobody uses is exactly the silence the ruling
forbids.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from swing.latches.constants import DISPLACED_UNANSWERABLE

NOW = datetime(2026, 7, 25, 12, 0)


@pytest.fixture
def seeded_db(tmp_path):
    from swing.config import load
    from swing.data.db import ensure_schema
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def _seed(cfg):
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T17:30:05', '2026-07-17', '2026-07-20', 1, 1, 0, "
            "0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'FTRE', 'aplus', 17.76, 18.34, 14.88, 'universe')")
        cid = int(cur.lastrowid)
    conn.close()
    return cid


def _run(cfg_path, *args):
    return CliRunner().invoke(
        main, ["--config", str(cfg_path), "latches", "parity", *args])


def test_the_report_NAMES_the_unanswerable_category_and_counts_it(seeded_db):
    """A first place with NO validity child, displaced by a retry.

    PRE-FIX the earlier cycle printed as free prose ("unknown (never
    answered)") with no NAMED category and no count, so a reader could not tell
    from the agreement block that anything had been left out of it.
    """
    from tests.cli.test_cli_latches_parity import _PLACE_BLOCK, _intent

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        first = _intent(conn, cid, "plc1", "place", **_PLACE_BLOCK)
        _intent(conn, cid, "plc3", "place", **_PLACE_BLOCK)
    conn.close()
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert f"{DISPLACED_UNANSWERABLE}:" in r.output
    assert f"place intent {first}: {DISPLACED_UNANSWERABLE}" in r.output


def test_the_agreement_rate_DISCLOSES_how_many_cycles_it_excluded(seeded_db):
    """RD, verbatim: "the agreement rate discloses how many cycles it
    excluded." The disclosure must sit WITH the rate -- a count printed twenty
    lines below it is not a disclosure of the rate, it is a separate fact the
    reader has to think to connect.
    """
    from tests.cli.test_cli_latches_parity import _PLACE_BLOCK, _intent

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        _intent(conn, cid, "plc1", "place", **_PLACE_BLOCK)
        _intent(conn, cid, "plc3", "place", **_PLACE_BLOCK)
    conn.close()
    r = _run(cfg_path)
    lines = r.output.splitlines()
    rate_at = next(i for i, ln in enumerate(lines) if ln.startswith("  rate:"))
    window = "\n".join(lines[rate_at:rate_at + 4])
    assert DISPLACED_UNANSWERABLE in window, (
        "the exclusion must be disclosed WITH the rate it was excluded from")
    assert "1" in window


def test_an_ANSWERED_displaced_cycle_is_NOT_in_the_unanswerable_count(seeded_db):
    """THE DISCRIMINATOR AGAINST OVER-COUNTING. A displaced cycle that WAS
    answered is measured -- it is disclosed beside the numbers with its outcome
    and its delta, and it must not also be reported as unanswerable."""
    from tests.cli.test_cli_latches_parity import (
        _PLACE_BLOCK,
        _SNAPSHOT,
        _intent,
    )

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        first = _intent(conn, cid, "plc1", "place", **_PLACE_BLOCK)
        _intent(conn, cid, "val2", "validity",
                validity_outcome="rejected_by_broker",
                validated_place_intent_id=first, validity_detail=_SNAPSHOT)
        _intent(conn, cid, "plc3", "place", **_PLACE_BLOCK)
    conn.close()
    r = _run(cfg_path)
    assert r.exit_code == 0, r.output
    assert f"place intent {first}: rejected_by_broker" in r.output
    assert f"{DISPLACED_UNANSWERABLE}:".ljust(1) in r.output
    line = next(ln for ln in r.output.splitlines()
                if ln.strip().startswith(f"{DISPLACED_UNANSWERABLE}:"))
    assert line.strip().endswith("0")


def test_a_clean_report_prints_the_named_ZERO_but_not_the_CAVEAT(seeded_db):
    """TWO DIFFERENT THINGS, and they are conditional differently.

    The COUNT is unconditional: a named zero is a measurement ("nothing was
    excluded"), it is greppable, and every other block in this report prints its
    zeros for exactly that reason.

    The multi-line CAVEAT is conditional: a permanent caveat on a clean report
    is noise the reader learns to skip, which is how a real one gets missed.
    """
    cfg, cfg_path = seeded_db
    _seed(cfg)
    r = _run(cfg_path)
    line = next(ln for ln in r.output.splitlines()
                if ln.strip().startswith(f"{DISPLACED_UNANSWERABLE}:"))
    assert line.strip().endswith("0")
    assert "the rate above EXCLUDES" not in r.output
