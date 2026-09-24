"""Arc 22-B Reviewer A R1-3 -- one render is internally consistent on the
four governed decision readers (RD RULING R1-3; CHARC RULING
R1-3-SHAPE-EXEC, which WITHDREW the snapshot bracket: the disjointness
assert stands alone).

Each governed reader counts from one read and names clause-(4) trades
("not counted: trade N (unintended_execution)") from a SECOND read. An
``assign(...)`` committing between the two would render trade N COUNTED and
NAMED "not counted" in one row. ``assert_intent_exclusion_disjoint`` is
called by every governed reader after its naming read and before it
populates ``intent_excluded``; a non-empty intersection raises the typed
``CohortReadRacedError``, which each surface renders as its refusal.

The race is planted BY EXECUTION (RD's test shape): the naming read is
monkeypatched to first commit a REAL ``assign(...)`` on a counted trade over
a SECOND connection, then run the original. One case per reader shape --
in-memory (``journal/stats.py``) and SQL (``metrics/tier.py``); the other two
readers are covered by the shared helper plus b22_130's name closure.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.metrics.test_22b_cohort_exclusion import (  # noqa: F401 (fixtures)
    H1,
    H2,
    UNINTENDED,
    _attest,
    _seed,
    cfg,
    conn,
)

RACED_TID = 3            # the H2 trade the planted assign moves mid-render
RACED_MESSAGE = "cohort read raced an intent write; re-run"


# ---------------------------------------------------------------------------
# b22_229 -- the helper itself
# ---------------------------------------------------------------------------
def test_the_disjointness_assert_raises_typed_on_intersection_only_b22_229() -> None:
    from swing.metrics.cohort import (
        CohortReadRacedError,
        assert_intent_exclusion_disjoint,
    )

    assert issubclass(CohortReadRacedError, ValueError)
    named = ((3, UNINTENDED), (8, f"{UNINTENDED}, UNATTESTED"))
    # Disjoint -> no error (the consistent renders, both directions).
    assert assert_intent_exclusion_disjoint({1, 2}, named) is None
    assert assert_intent_exclusion_disjoint(set(), named) is None
    assert assert_intent_exclusion_disjoint({3, 8}, ()) is None
    assert assert_intent_exclusion_disjoint([None, 1], named) is None
    # Intersection -> the typed error, the ruled text, the ids carried.
    with pytest.raises(CohortReadRacedError) as exc:
        assert_intent_exclusion_disjoint([1, 3, None], named)
    assert str(exc.value) == RACED_MESSAGE
    assert str(exc.value).isascii()
    assert exc.value.trade_ids == (3,)
    with pytest.raises(CohortReadRacedError) as exc:
        assert_intent_exclusion_disjoint((8, 3), named)
    assert exc.value.trade_ids == (3, 8)


def test_the_assert_docstring_carries_the_sufficiency_argument_b22_230() -> None:
    """The ruling's sufficiency argument and its NAMED precondition live in
    the helper's docstring (RULING R1-3-SHAPE-EXEC point 2)."""
    from swing.metrics.cohort import assert_intent_exclusion_disjoint

    doc = " ".join((assert_intent_exclusion_disjoint.__doc__ or "").split())
    for trigger in ("trg_trades_entry_intent_attested_terminal",
                    "trg_trades_entry_intent_unattested_update",
                    "trg_trades_entry_intent_unattested_insert",
                    "trg_eia_no_delete", "trg_eia_no_replace"):
        assert trigger in doc, trigger
    assert "MONOTONE" in doc
    assert "no fourth state" in doc.lower()
    assert "reversal surface" in doc
    assert "re-opens" in doc or "re-rules" in doc


# ---------------------------------------------------------------------------
# The planted race (RD's test shape), and the world it runs in
# ---------------------------------------------------------------------------
def _seed_race_world(conn: sqlite3.Connection) -> None:
    """H1: trade 1 standard (counts). H2: trade 3 NULL intent (counts, and
    is the trade the planted assign moves mid-render)."""
    _seed(conn, trade_id=1, ticker="AAA", label=H1, entry_intent="standard")
    _seed(conn, trade_id=RACED_TID, ticker="CCC", label=H2, entry_intent=None)


class _PlantedAssign:
    """Wraps a naming read: its FIRST call commits a REAL ``assign(...)`` on
    ``RACED_TID`` over a SECOND connection, then runs the original read."""

    def __init__(self, cfg, original) -> None:
        self.cfg = cfg
        self.original = original
        self.fired = 0

    def __call__(self, *args, **kwargs):
        if not self.fired:
            self.fired += 1
            _attest(self.cfg, RACED_TID)
        return self.original(*args, **kwargs)


def _committed_intent(cfg, tid: int) -> tuple:
    """The row as a FRESH connection sees it: (entry_intent, attested)."""
    c = sqlite3.connect(cfg.paths.db_path)
    try:
        return c.execute(
            "SELECT t.entry_intent, COUNT(a.attestation_id) FROM trades t "
            "LEFT JOIN entry_intent_attestations a ON a.trade_id = t.id "
            "WHERE t.id = ? GROUP BY t.id", (tid,)).fetchone()
    finally:
        c.close()


def _journal_h2(conn) -> tuple[int, set[int], tuple[str, ...]]:
    """(N counted, named ids, the lines rendered under H2's row)."""
    from swing.journal.stats import (
        compute_hypothesis_progress_breakdown,
        render_hypothesis_progress,
    )
    from tests.metrics.test_22b_cohort_exclusion import _block

    rows = compute_hypothesis_progress_breakdown(conn, starting_equity=7500.0)
    (h2,) = [r for r in rows if r.name == H2]
    block = _block(render_hypothesis_progress(rows), f"- {H2} (")
    return (h2.current_sample + h2.in_flight_sample,
            {tid for tid, _ in h2.intent_excluded}, block)


def _tier_h2(conn) -> tuple[int, set[int], tuple[str, ...]]:
    from swing.metrics.tier import compute_tier_comparison

    (h2,) = [c for c in compute_tier_comparison(conn).cohorts
             if c.cohort_name == H2]
    return h2.n_closed, {tid for tid, _ in h2.intent_excluded}, h2.intent_lines


def _assert_race_refused(conn, cfg, read, planted: _PlantedAssign) -> None:
    """Pre-fix the render CONTRADICTS itself (RED on the disjointness check
    over the rendered row); post-fix the typed error, never the row."""
    from swing.metrics.cohort import CohortReadRacedError

    try:
        n, named, lines = read(conn)
    except CohortReadRacedError as exc:
        refused = exc
    else:
        # H2's ONLY labelled trade is RACED_TID, so N == 1 means it counted.
        counted = {RACED_TID} if n == 1 else set()
        assert not counted & named, (
            f"contradictory render: trade {RACED_TID} COUNTED (N={n}) and "
            f"NAMED not counted {sorted(named)}; lines {lines}")
        pytest.fail(f"no refusal and no contradiction (fired={planted.fired})")
    assert planted.fired == 1
    assert refused.trade_ids == (RACED_TID,)
    assert str(refused) == RACED_MESSAGE
    # The planted write is real and committed: seen by a FRESH connection.
    assert _committed_intent(cfg, RACED_TID) == (UNINTENDED, 1)


# ---------------------------------------------------------------------------
# b22_231 / b22_232 -- the planted race, one case per reader shape
# ---------------------------------------------------------------------------
def test_journal_progress_refuses_a_raced_render_in_memory_shape_b22_231(
        conn, cfg, monkeypatch) -> None:
    import swing.metrics.cohort as cohort_mod

    _seed_race_world(conn)
    planted = _PlantedAssign(cfg, cohort_mod.list_intent_excluded_for_cohort)
    # stats.py imports the naming read locally from the module at call time.
    monkeypatch.setattr(cohort_mod, "list_intent_excluded_for_cohort", planted)
    _assert_race_refused(conn, cfg, _journal_h2, planted)
    # The re-run reads clean: excluded AND named, consistent.
    monkeypatch.setattr(cohort_mod, "list_intent_excluded_for_cohort",
                        planted.original)
    assert _journal_h2(conn)[:2] == (0, {RACED_TID})


def test_tier_comparison_refuses_a_raced_render_sql_shape_b22_232(
        conn, cfg, monkeypatch) -> None:
    import swing.metrics.tier as tier_mod

    _seed_race_world(conn)
    planted = _PlantedAssign(cfg, tier_mod.list_intent_excluded_for_cohort)
    monkeypatch.setattr(tier_mod, "list_intent_excluded_for_cohort", planted)
    _assert_race_refused(conn, cfg, _tier_h2, planted)
    monkeypatch.setattr(tier_mod, "list_intent_excluded_for_cohort",
                        planted.original)
    assert _tier_h2(conn)[:2] == (0, {RACED_TID})


# ---------------------------------------------------------------------------
# b22_233 (one case per reader shape) -- the boundary twin: the SAME assign committed BEFORE
# the first cohort read -> the consistent excluded-and-named row, NO error
# (the assert is pinned to the intersection, not to the write's existence)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("read", [_journal_h2, _tier_h2],
                         ids=["journal_in_memory", "tier_sql"])
def test_an_assign_before_the_first_cohort_read_renders_consistent_b22_233(
        conn, cfg, read) -> None:
    _seed_race_world(conn)
    _attest(cfg, RACED_TID)
    n, named, lines = read(conn)
    assert (n, named) == (0, {RACED_TID})
    assert f"not counted: trade {RACED_TID} ({UNINTENDED})" in lines, lines


# ---------------------------------------------------------------------------
# b22_235 -- every CLI surface over the governed readers renders the refusal
# as a ClickException at its boundary: the ruled text, no traceback, and no
# row at all (never the contradictory row, never a partial table)
# ---------------------------------------------------------------------------
def _raise_raced(*_args, **_kwargs):
    from swing.metrics.cohort import CohortReadRacedError

    raise CohortReadRacedError((RACED_TID,))


def _assert_cli_refused(result) -> None:
    assert result.exit_code == 1, result.output
    # A ClickException exits via SystemExit; a leaked CohortReadRacedError
    # is the traceback the CLI boundary rule forbids.
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert f"Error: {RACED_MESSAGE}" in result.output, result.output
    assert "not counted" not in result.output
    assert result.output.isascii()


def test_journal_review_renders_the_refusal_b22_235(cfg, monkeypatch) -> None:
    import swing.journal.stats as stats_mod
    from click.testing import CliRunner

    from swing.cli import journal_review_cmd

    monkeypatch.setattr(stats_mod, "compute_hypothesis_progress_breakdown",
                        _raise_raced)
    result = CliRunner().invoke(journal_review_cmd, obj={"config": cfg})
    _assert_cli_refused(result)
    assert "Hypothesis investigation progress" not in result.output


@pytest.mark.parametrize("raced_hypothesis_id", [1, 3])
def test_hypothesis_list_renders_the_refusal_and_no_partial_table_b22_235(
        cfg, monkeypatch, raced_hypothesis_id: int) -> None:
    """A race on a LATER hypothesis must not leave the earlier rows printed:
    the command refuses whole (the partial-table direction)."""
    import swing.recommendations.hypothesis as hyp_mod
    from click.testing import CliRunner

    from swing.cli import hypothesis_list_cmd

    original = hyp_mod.compute_tripwire_status

    def raced_on_one(conn, *, hypothesis_id, **kwargs):
        if hypothesis_id == raced_hypothesis_id:
            _raise_raced()
        return original(conn, hypothesis_id=hypothesis_id, **kwargs)

    monkeypatch.setattr(hyp_mod, "compute_tripwire_status", raced_on_one)
    result = CliRunner().invoke(hypothesis_list_cmd, obj={"config": cfg})
    _assert_cli_refused(result)
    assert "N/TARGET" not in result.output, result.output
    assert H1 not in result.output


def test_hypothesis_status_renders_the_refusal_b22_235(cfg, monkeypatch) -> None:
    import swing.recommendations.hypothesis as hyp_mod
    from click.testing import CliRunner

    from swing.cli import hypothesis_status_cmd

    monkeypatch.setattr(hyp_mod, "compute_tripwire_status", _raise_raced)
    result = CliRunner().invoke(hypothesis_status_cmd, ["1"], obj={"config": cfg})
    _assert_cli_refused(result)
    assert "Current sample" not in result.output


def test_trade_entry_prefill_renders_the_refusal_nothing_written_b22_235(
        cfg, conn, monkeypatch) -> None:
    """The prefill consumes the governed breakdown's N; a raced read there
    refuses the command BEFORE the entry is written (result is None), as a
    ClickException -- never a traceback."""
    import swing.cli as cli_mod
    from click.testing import CliRunner

    from tests.cli.test_cli_trade import _PRE_TRADE_OK_FLAGS

    monkeypatch.setattr(cli_mod, "lookup_active_recommendation_label", _raise_raced)
    result = CliRunner().invoke(cli_mod.trade_entry_cmd, [
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "vcp-breakout",
        *_PRE_TRADE_OK_FLAGS,
    ], obj={"config": cfg})
    _assert_cli_refused(result)
    assert conn.execute("SELECT COUNT(*) FROM trades").fetchone() == (0,)
