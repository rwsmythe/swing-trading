"""Arc 22-B Task 8 -- clause (4) excluded in cohort CODE (N2 (a)) and named
per cohort (N3 (a)), with RD's UNATTESTED token (RD-PLAN-READ).

Clause (4) of ``docs/training-epoch-intent-contract.md``: an
``unintended_execution`` "counts toward NO hypothesis cohort". The FOUR
governed readers (journal progress, tier comparison, the tripwire behind
``swing hypothesis list``, the hypothesis-progress card) must not count it,
and each must NAME it under the cohort whose label it carries.

Fixture note (a consequence of the CHARC-S3 twins): a v40 DB refuses a raw
``unintended_execution`` write, so every synthetic one here is ATTESTED
through the real ``assign(...)`` on a deployment-leg shape (no envelope, an
``entry_date`` before 2026-08-03, no link/intent/telemetry for its ticker).
The one exception is b22_206, whose subject IS the unattested state: that
value is written by a raw UPDATE after the two unattested twins are DROPPED
in the test DB (the b22_127 technique -- the drop is the planting method).
"""
from __future__ import annotations

import ast
import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.config import load as load_config
from swing.data.db import ensure_schema, open_connection
from swing.metrics.label_match import label_matches_hypothesis

H1 = "A+ baseline"
H2 = "Near-A+ defensible: extension test"
UNINTENDED = "unintended_execution"
REPO_ROOT = Path(__file__).resolve().parents[2]
TWINS = ("trg_trades_entry_intent_unattested_update",
         "trg_trades_entry_intent_unattested_insert")


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "b22_cohort.db"
    ensure_schema(db_path).close()
    base = load_config(Path("swing.config.toml"))
    return dc_replace(base, paths=dc_replace(base.paths, db_path=db_path))


@pytest.fixture
def conn(cfg):
    c = sqlite3.connect(cfg.paths.db_path)
    yield c
    c.close()


def _seed(conn: sqlite3.Connection, *, trade_id: int, ticker: str,
          label: str | None, entry_intent: str | None, pnl: float = 100.0,
          entry_date: str = "2026-07-20", state: str = "closed") -> None:
    """entry=$10, stop=$9, 100 shares => R = pnl/100. The outcome fill lands
    the NEXT day (a same-session outcome refuses the assignment, b22_196),
    and the entry fill carries NO envelope (the deployment-leg shape)."""
    exit_date = entry_date[:8] + f"{int(entry_date[8:]) + 1:02d}"
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, entry_intent, risk_policy_id_at_lock, "
        "last_fill_at, notes, why_now) VALUES (?, ?, ?, 10.0, 100, 9.0, 9.0, "
        "?, 'S', 'I', 'manual_off_pipeline', ?, ?, ?, ?, 1, ?, ?, ?)",
        (trade_id, ticker, entry_date, state, entry_date + "T09:30:00",
         0 if state in ("closed", "reviewed") else 100, label, entry_intent,
         exit_date + "T15:30:00", f"the note of {ticker}",
         f"why {ticker} now"))
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, 'entry', 100, 10.0, "
        "'unreconciled')", (trade_id, entry_date + "T09:30:00"))
    if state in ("closed", "reviewed"):
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES (?, ?, 'exit', 100, ?, "
            "'unreconciled')",
            (trade_id, exit_date + "T15:30:00", 10.0 + pnl / 100.0))
    conn.commit()


def _attest(cfg, trade_id: int) -> int:
    """The value written by its ONE writer, with its evidence row."""
    from swing.trades.entry_intent_assignment import assign

    c = open_connection(cfg.paths.db_path)
    try:
        r = assign(c, None, trade_id=trade_id, cite=["notes", "why_now"],
                   reason="an execution nobody decided to make",
                   applied_by="operator")
    finally:
        c.close()
    assert r.admitted, r.message
    return int(r.attestation_id)


def _plant_unattested(conn: sqlite3.Connection, trade_id: int) -> None:
    """The unattested state: unreachable through SQL on a v40 DB while the
    twins stand, so they are DROPPED here first (the planting method)."""
    for name in TWINS:
        conn.execute(f"DROP TRIGGER {name}")
    conn.execute("UPDATE trades SET entry_intent = ? WHERE id = ?",
                 (UNINTENDED, trade_id))
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM entry_intent_attestations WHERE trade_id = ?",
        (trade_id,)).fetchone() == (0,)


def _hid(conn: sqlite3.Connection, name: str) -> int:
    return int(conn.execute("SELECT id FROM hypothesis_registry WHERE name = ?",
                            (name,)).fetchone()[0])


# ---------------------------------------------------------------------------
# The four readers + `swing hypothesis list`, read the same way everywhere
# ---------------------------------------------------------------------------
def _readers(conn: sqlite3.Connection, cfg) -> dict[str, dict[str, tuple]]:
    """reader -> cohort -> (N counted, intent_excluded, rendered lines)."""
    from swing.journal.stats import (
        compute_hypothesis_progress_breakdown,
        render_hypothesis_progress,
    )
    from swing.metrics.cohort_intent import intent_exclusion_lines
    from swing.metrics.tier import compute_tier_comparison
    from swing.recommendations.hypothesis import compute_tripwire_status
    from swing.web.view_models.metrics.hypothesis_progress_card import (
        build_hypothesis_progress_card_vm,
    )

    out: dict[str, dict[str, tuple]] = {}
    rows = compute_hypothesis_progress_breakdown(conn, starting_equity=7500.0)
    rendered = render_hypothesis_progress(rows)
    out["journal"] = {
        r.name: (r.current_sample + r.in_flight_sample, r.intent_excluded,
                 _block(rendered, f"- {r.name} ("))
        for r in rows}
    tier = compute_tier_comparison(conn)
    out["tier"] = {c.cohort_name: (c.n_closed, c.intent_excluded, c.intent_lines)
                   for c in tier.cohorts}
    card = build_hypothesis_progress_card_vm(cfg=cfg, conn=conn)
    out["card"] = {c.cohort_name: (c.n_closed, c.intent_excluded, c.intent_lines)
                   for c in card.cohorts}
    trip = {}
    for name in (H1, H2):
        tw = compute_tripwire_status(conn, hypothesis_id=_hid(conn, name),
                                     starting_equity=7500.0)
        trip[name] = (tw.current_sample, tw.intent_excluded,
                      intent_exclusion_lines(tw.intent_excluded))
    out["tripwire"] = trip
    out["hypothesis list"] = _cli_list(cfg, conn)
    return out


def _block(text: str, row_prefix: str) -> tuple[str, ...]:
    """The indented lines rendered UNDER the row starting with row_prefix,
    up to the next row -- 'under ITS cohort only'."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(row_prefix))
    block = []
    for ln in lines[start + 1:]:
        if not ln.startswith("  "):
            break
        block.append(ln.strip())
    return tuple(block)


def _cli_list(cfg, conn: sqlite3.Connection) -> dict[str, tuple]:
    from swing.cli import hypothesis_list_cmd

    r = CliRunner().invoke(hypothesis_list_cmd, obj={"config": cfg})
    assert r.exit_code == 0, r.output
    assert r.output.isascii()
    out = {}
    for name in (H1, H2):
        row = next(ln for ln in r.output.splitlines() if ln.endswith(f" {name}"))
        n = int(row.split()[2].split("/")[0])
        out[name] = (n, None, _block(r.output, row))
    return out


def _line(tid: int, reason: str = UNINTENDED) -> str:
    return f"not counted: trade {tid} ({reason})"


# ---------------------------------------------------------------------------
# b22_131 -- the authority is pinned to the committed doc
# ---------------------------------------------------------------------------
def test_contract_exclusion_clause_is_in_the_committed_doc_b22_131() -> None:
    from swing.metrics.cohort_intent import (
        CONTRACT_EXCLUDED_ENTRY_INTENTS,
        CONTRACT_EXCLUSION_CLAUSE,
    )
    from tests.docs._contract_reader import CONTRACT_DOC, clause4_body

    body = clause4_body(CONTRACT_DOC.read_bytes()).decode("utf-8")
    assert CONTRACT_EXCLUSION_CLAUSE == "It counts toward NO hypothesis cohort."
    assert CONTRACT_EXCLUSION_CLAUSE in body
    assert CONTRACT_EXCLUDED_ENTRY_INTENTS == (UNINTENDED,)
    # The pin bites: the doc line with the sentence dropped no longer holds it.
    assert CONTRACT_EXCLUSION_CLAUSE not in body.replace(CONTRACT_EXCLUSION_CLAUSE, "")


# ---------------------------------------------------------------------------
# b22_132 -- every cohort, every registration state
# ---------------------------------------------------------------------------
_REGISTERED = (H1, H2, "Sub-A+ VCP-not-formed",
               "Capital-blocked: smaller-position test", "Broad-watch baseline")


@pytest.mark.parametrize("name", [*_REGISTERED, "an orphan label"])
@pytest.mark.parametrize("registered", [None, _REGISTERED])
def test_trade_counts_toward_cohort_false_for_every_cohort_b22_132(
        name: str, registered) -> None:
    from swing.metrics.cohort_intent import (
        cohort_excluded_entry_intents,
        cohort_intent_authority,
        trade_counts_toward_cohort,
    )

    assert trade_counts_toward_cohort(
        entry_intent=UNINTENDED, hypothesis_name=name,
        registered_names=registered) is False
    assert cohort_excluded_entry_intents(
        name, registered_names=registered) == (UNINTENDED,)
    # Non-vacuous: the same cohort still counts what it counted before.
    counted = "standard" if (name == H1 and (registered is None
                                             or name in registered)) else None
    assert trade_counts_toward_cohort(
        entry_intent=counted, hypothesis_name=name,
        registered_names=registered) is True
    # The authority did not change; its text did (N2 (a)).
    if name in _REGISTERED and name != H1:
        assert cohort_intent_authority(name) == "epoch_contract"


# ---------------------------------------------------------------------------
# b22_133 -- the SQL and in-memory halves select the same trades
# ---------------------------------------------------------------------------
def test_sql_and_memory_halves_agree_b22_133(conn, cfg) -> None:
    from swing.metrics.cohort import list_closed_trades_for_cohort
    from swing.metrics.cohort_intent import (
        cohort_entry_intent,
        cohort_excluded_entry_intents,
        trade_counts_toward_cohort,
    )

    tid = 0
    unintended = set()
    for label in (H1, H2):
        for intent in (None, "standard", "hypothesis_test_by_design", UNINTENDED):
            tid += 1
            _seed(conn, trade_id=tid, ticker=f"T{tid}", label=label,
                  entry_intent=None if intent == UNINTENDED else intent)
            if intent == UNINTENDED:
                _attest(cfg, tid)
                unintended.add(tid)
    everything = list_closed_trades_for_cohort(conn, hypothesis_label=None)
    assert {t.id for t in everything if t.entry_intent == UNINTENDED} == unintended
    for name in (H1, H2):
        sql = {t.id for t in list_closed_trades_for_cohort(
            conn, hypothesis_label=name, entry_intent=cohort_entry_intent(name),
            exclude_entry_intents=cohort_excluded_entry_intents(name))}
        memory = {t.id for t in everything
                  if label_matches_hypothesis(t.hypothesis_label, name)
                  and trade_counts_toward_cohort(entry_intent=t.entry_intent,
                                                 hypothesis_name=name)}
        assert sql == memory, name
        assert not sql & unintended, name
    # Exact sets (both halves could agree while both being wrong): H1 counts
    # its standard trade only; H2 counts NULL, standard and by_design.
    assert {t.id for t in list_closed_trades_for_cohort(
        conn, hypothesis_label=H2,
        exclude_entry_intents=cohort_excluded_entry_intents(H2))} == {5, 6, 7}


# ---------------------------------------------------------------------------
# b22_134 / b22_135 / b22_136 -- not counted, and named under ITS cohort
# ---------------------------------------------------------------------------
def _seed_named_world(conn, cfg) -> None:
    """H1: 1 standard (counts), 2 unintended. H2: 3 NULL intent (counts), 4
    unintended. Both unintended trades attested through the real writer."""
    _seed(conn, trade_id=1, ticker="AAA", label=H1, entry_intent="standard")
    _seed(conn, trade_id=2, ticker="BBB", label=H1, entry_intent=None)
    _seed(conn, trade_id=3, ticker="CCC", label=H2, entry_intent=None)
    _seed(conn, trade_id=4, ticker="DDD", label=f"{H2} extension probe",
          entry_intent=None)
    _attest(cfg, 2)
    _attest(cfg, 4)


def _assert_excluded_and_named(conn, cfg) -> None:
    got = _readers(conn, cfg)
    for reader, cohorts in got.items():
        n1, ex1, lines1 = cohorts[H1]
        n2, ex2, lines2 = cohorts[H2]
        assert (n1, n2) == (1, 1), reader
        if ex1 is not None:  # the CLI renders; it has no field of its own
            assert (ex1, ex2) == (((2, UNINTENDED),), ((4, UNINTENDED),)), reader
        assert _line(2) in lines1 and _line(4) not in lines1, (reader, lines1)
        assert _line(4) in lines2 and _line(2) not in lines2, (reader, lines2)


def test_h1_and_h2_labelled_unintended_trades_are_excluded_and_named_b22_134(
        conn, cfg) -> None:
    _seed_named_world(conn, cfg)
    _assert_excluded_and_named(conn, cfg)


def test_null_intent_h2_trade_still_counts_b22_135(conn, cfg) -> None:
    """N2's NULL twin: NULL is unclassified, not excluded (``IS NOT``)."""
    _seed(conn, trade_id=3, ticker="CCC", label=H2, entry_intent=None)
    for reader, cohorts in _readers(conn, cfg).items():
        n2, ex2, lines2 = cohorts[H2]
        assert n2 == 1, reader
        assert not ex2 and not any("not counted" in ln for ln in lines2), reader


def test_an_else_branch_coercing_unknown_to_standard_fails_b22_136(
        conn, cfg, monkeypatch) -> None:
    """The discriminator, by execution: a trade_counts_toward_cohort that
    coerces an intent it does not know to 'standard' counts the H1
    unintended trade, and b22_134's assertion goes RED."""
    import swing.metrics.cohort_intent as ci

    original = ci.trade_counts_toward_cohort

    def coercing(*, entry_intent, hypothesis_name, registered_names=None):
        known = (None, "standard", "hypothesis_test_by_design")
        intent = entry_intent if entry_intent in known else "standard"
        required = ci.cohort_entry_intent(hypothesis_name,
                                          registered_names=registered_names)
        return required is None or intent == required

    _seed_named_world(conn, cfg)
    assert original(entry_intent=UNINTENDED, hypothesis_name=H1) is False
    monkeypatch.setattr(ci, "trade_counts_toward_cohort", coercing)
    from swing.metrics.cohort import CohortReadRacedError
    from swing.recommendations.hypothesis import compute_tripwire_status

    # Since R1-3 (RULING R1-3-SHAPE-EXEC) the coerced count meets the naming
    # read, which still names trade 2, so the disjointness assert refuses the
    # render (typed) instead of emitting it: the coerced trade IS counted
    # (it is the id the refusal carries) and b22_134 still goes RED.
    with pytest.raises(CohortReadRacedError) as exc:
        compute_tripwire_status(conn, hypothesis_id=_hid(conn, H1),
                                starting_equity=7500.0)
    assert exc.value.trade_ids == (2,)  # the coerced trade is counted
    with pytest.raises((AssertionError, CohortReadRacedError)):
        _assert_excluded_and_named(conn, cfg)


# ---------------------------------------------------------------------------
# b22_137 -- the observational surfaces are unchanged
# ---------------------------------------------------------------------------
def test_process_card_and_count_per_cohort_are_unchanged_b22_137(conn, cfg) -> None:
    from swing.metrics.cohort import count_per_cohort, list_closed_trades_for_cohort
    from swing.metrics.process import compute_trade_process_metrics

    _seed_named_world(conn, cfg)
    counts = count_per_cohort(conn)
    assert (counts[H1], counts[H2]) == (2, 2)
    assert {t.id for t in list_closed_trades_for_cohort(
        conn, hypothesis_label=H1)} == {1, 2}
    assert compute_trade_process_metrics(conn, hypothesis_label=H1).n_closed == 2
    assert compute_trade_process_metrics(
        conn, hypothesis_label=H1, entry_intent=UNINTENDED).n_closed == 1


# ---------------------------------------------------------------------------
# b22_206 -- RD-PLAN-READ: the UNATTESTED token on every reader
# ---------------------------------------------------------------------------
def test_an_unattested_value_is_named_unattested_on_every_reader_b22_206(
        conn, cfg) -> None:
    _seed(conn, trade_id=1, ticker="AAA", label=H1, entry_intent="standard")
    _seed(conn, trade_id=7, ticker="ATT", label=H1, entry_intent=None)
    _seed(conn, trade_id=8, ticker="RAW", label=H1, entry_intent=None)
    _attest(cfg, 7)
    _plant_unattested(conn, 8)
    got = _readers(conn, cfg)
    for reader, cohorts in got.items():
        n1, ex1, lines1 = cohorts[H1]
        assert n1 == 1, reader
        if ex1 is not None:
            assert ex1 == ((7, UNINTENDED), (8, f"{UNINTENDED}, UNATTESTED")), reader
        assert _line(8, f"{UNINTENDED}, UNATTESTED") in lines1, (reader, lines1)
        assert _line(7) in lines1, (reader, lines1)
        assert not any("7 (" in ln and "UNATTESTED" in ln for ln in lines1), reader


# ---------------------------------------------------------------------------
# b22_130 -- every cohort-membership reader is governed or reasoned
# ---------------------------------------------------------------------------
_MEMBERSHIP_CALLS = frozenset({
    "_label_matches_hypothesis", "label_matches_hypothesis_sql",
    "list_trades_for_cohort", "list_closed_trades_for_cohort", "count_per_cohort",
})
GOVERNED = frozenset({
    "swing/journal/stats.py",
    "swing/metrics/tier.py",
    "swing/recommendations/hypothesis.py",
    "swing/web/view_models/metrics/hypothesis_progress_card.py",
})
REASONED_EXCLUSION = {
    "swing/metrics/process.py": "observational: the intent-faceted trade-"
                                "process card, where clause (4) routes the result",
    "swing/metrics/cohort.py": "the helpers themselves; count_per_cohort feeds "
                               "the D29 observational tabs",
    "swing/web/view_models/metrics/trade_process_card.py": "calls "
                               "count_per_cohort for the D29 observational tabs",
    "swing/diagnostics/metrics_wiring_audit.py": "string mentions only",
    "swing/metrics/label_match.py": "the matcher itself",
}


def _membership_call_sites(text: str) -> list[int]:
    hits = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Call):
            fn = node.func
            name = (fn.id if isinstance(fn, ast.Name)
                    else fn.attr if isinstance(fn, ast.Attribute) else None)
            if name in _MEMBERSHIP_CALLS:
                hits.append(node.lineno)
    return hits


def test_every_cohort_membership_reader_is_governed_or_reasoned_b22_130() -> None:
    found = {}
    for path in sorted((REPO_ROOT / "swing").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        hits = _membership_call_sites(path.read_text(encoding="utf-8"))
        if hits:
            found[rel] = hits
    unclassified = {p: h for p, h in found.items()
                    if p not in GOVERNED and p not in REASONED_EXCLUSION}
    assert not unclassified, unclassified
    # Every governed reader is actually found by the walk (a stale list fails).
    assert GOVERNED <= set(found), GOVERNED - set(found)
    # The walk's own discriminator: a planted call in a new module is a hit.
    assert _membership_call_sites("from x import y\ny.list_trades_for_cohort(c)\n") == [2]
