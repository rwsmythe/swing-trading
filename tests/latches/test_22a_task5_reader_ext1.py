"""22-A Task 5 -- EXT-1: the THREE additive keyword-only reader parameters.

**CHARC APPROVED EXT-1 AS SPECIFIED (2026-08-24)**, and approved the two
no-fallback parameters on a stated ground: *a fallback would silently
reintroduce the guessing this arc exists to kill.*  So each parameter here is
load-bearing rather than convenient:

* ``criteria_lapse_armed_override`` -- RD's bound says a latch NEVER dies of
  drift, and ``criteria_lapsed`` IS the drift rung (plan S2.3.4).  The
  recorded-but-not-taken fallback was ``dataclasses.replace(cfg, ...)``, which
  works today and is enforceable by NOTHING (#31).
* ``exclude_trade_ids`` -- on the CORRECTION path the subject trade already
  exists, and ``_match_fill``'s windowed rung admits any NULL-candidate,
  same-ticker, in-zone entry, so the probe sees the subject's OWN fill and
  returns ``clear_reason='fill'``.  Without the parameter the arc's live
  application is unreachable (plan S2.3, verified against the live DB).
* ``strict_decisions`` -- ``load_decision_intents`` returns ``{}`` on ANY read
  failure, and ``Latch`` exposes no decision-ledger status, so a LOST decline
  ledger is indistinguishable from NO decline.  Without it the resolver can
  admit a DECLINED mandate (plan S2.3.3b, review 22A-R15-03).

**THE DEFAULTS ARE THE CONTRACT.**  Every existing production caller passes
NONE of the three, so the default path must be byte-identical to what shipped.
``None`` is NOT ``False`` for the first parameter and the discriminator below
says so: an implementation writing ``criteria_lapse_armed = bool(override)``
reads a config-armed rung as disarmed and passes every other test in this file.

**THE CALL-SITE COUNT WAS WRONG AND IS NOW MECHANICAL (Codex R1 minor).**  This
docstring said FIVE.  There are SIX, and the sixth is a real production surface
-- the broker-order fragment at ``swing/web/view_models/latches.py:2138``.  The
number came from a grep whose seven lines were in front of me and were
miscounted, which is the project's most-repeated defect arriving in the
paragraph that names its own method.  So the roster below is ENUMERATED and a
test walks the tree and asserts it, rather than a count being asserted in
prose: a stated count is only as good as the read that produced it, and a read
can be re-done wrong.

FROZEN CLOCK.  Every derivation here is anchored by an explicit
``horizon_session_override`` or an explicit ``now``; nothing reads the wall
clock.
"""
from __future__ import annotations

import dataclasses
import re
import inspect
import sqlite3
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from swing.data.db import ensure_schema
from swing.latches.reader import build_latch_derivation, load_decision_intents

HORIZON = date(2026, 7, 27)


def _cfg(tmp_path):
    cache = tmp_path / "prices"
    cache.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        paths=SimpleNamespace(prices_cache_dir=cache, db_path=tmp_path / "t.db"),
        pipeline=SimpleNamespace(observe_max_pending_window_sessions=30),
    )


def _run(conn, rid, asof, action):
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) "
        "VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0)",
        (rid, f"{asof}T17:30:05", asof, action))


def _candidate(conn, rid, ticker, pivot, stop):
    cur = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) "
        "VALUES (?, ?, 'aplus', 17.76, ?, ?, 'universe')",
        (rid, ticker, pivot, stop))
    return int(cur.lastrowid)


def _trade(conn, trade_id, ticker, candidate_id, entry_date="2026-07-21"):
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, trade_origin, "
        "pre_trade_locked_at, candidate_id) VALUES "
        "(?, ?, ?, 18.40, 3, 14.88, 14.88, 'entered', 'pipeline_aplus', "
        "'2026-07-17T17:30:05', ?)",
        (trade_id, ticker, entry_date, candidate_id))


@pytest.fixture
def two_filled_fires(tmp_path):
    """Two tickers, each with an A+ fire and a trade whose ``candidate_id``
    links it to that fire.  The EXACT fill rung recognises both, so the
    unexcluded derivation clears BOTH latches.

    Dimensions PINNED: each trade's ``candidate_id`` link (the EXACT rung, so
    no price band is in play) and each entry date (inside the horizon).
    Dimensions deliberately FREE: prices, share counts and the archive (there
    is none, so no bar can invalidate and confound the fill verdict).
    """
    conn = ensure_schema(tmp_path / "t.db")
    with conn:
        _run(conn, 121, "2026-07-17", "2026-07-20")
        first = _candidate(conn, 121, "FTRE", 18.34, 14.88)
        _run(conn, 122, "2026-07-17", "2026-07-20")
        second = _candidate(conn, 122, "VSTS", 16.90, 13.40)
        _trade(conn, 11, "FTRE", first)
        _trade(conn, 12, "VSTS", second)
    yield conn
    conn.close()


def _by_ticker(derivation):
    return {lat.identity.ticker: lat for lat in derivation.latches}


# ---------------------------------------------------------------------------
# The signature contract
# ---------------------------------------------------------------------------
def test_the_three_parameters_are_keyword_only_and_inert_by_default() -> None:
    """ADDITIVE means additive: keyword-only, defaulted, and no reordering of
    the two parameters that shipped before them."""
    sig = inspect.signature(build_latch_derivation)
    for name, default in (
        ("criteria_lapse_armed_override", None),
        ("exclude_trade_ids", None),
        ("strict_decisions", False),
    ):
        assert name in sig.parameters, f"EXT-1 parameter {name} is missing"
        parameter = sig.parameters[name]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, name
        assert parameter.default is default, name
    assert list(sig.parameters)[:2] == ["conn", "cfg"]
    assert sig.parameters["now"].default is None
    assert sig.parameters["horizon_session_override"].default is None


def test_explicit_defaults_equal_the_bare_call(two_filled_fires, tmp_path) -> None:
    """The five shipped call sites pass none of the three.  Passing them
    explicitly at their defaults must not move a single field."""
    cfg = _cfg(tmp_path)
    bare = build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON)
    explicit = build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON,
        criteria_lapse_armed_override=None,
        exclude_trade_ids=None,
        strict_decisions=False,
    )
    assert dataclasses.asdict(bare) == dataclasses.asdict(explicit)


def test_the_default_derivation_still_clears_both_latches_on_their_fills(
        two_filled_fires, tmp_path) -> None:
    """The characterisation half of "byte-for-byte": the shipped OUTCOME, named
    rather than compared to a second call of the same code."""
    latches = _by_ticker(build_latch_derivation(
        two_filled_fires, _cfg(tmp_path), horizon_session_override=HORIZON))
    assert latches["FTRE"].clear_reason == "fill"
    assert latches["FTRE"].clear_trade_id == 11
    assert latches["VSTS"].clear_reason == "fill"
    assert latches["VSTS"].clear_trade_id == 12


# ---------------------------------------------------------------------------
# exclude_trade_ids
# ---------------------------------------------------------------------------
def test_excluding_the_subject_trade_re_arms_its_own_latch(
        two_filled_fires, tmp_path) -> None:
    """The 22A-AR-04 defect, pinned.  PRE-fix (no parameter, or a parameter
    that does not filter) the probe returns ``clear_reason='fill'``; POST-fix
    it returns ``None`` and the mandate is judged as it was BEFORE the subject
    fill existed."""
    cfg = _cfg(tmp_path)
    before = _by_ticker(build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON))
    assert before["FTRE"].clear_reason == "fill"

    after = _by_ticker(build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON,
        exclude_trade_ids=frozenset({11})))
    assert after["FTRE"].clear_reason is None
    assert after["FTRE"].clear_trade_id is None
    assert after["FTRE"].state == "armed"


def test_the_exclusion_is_scoped_to_the_named_ids(
        two_filled_fires, tmp_path) -> None:
    """Blanking ALL entries would change other latches' answers -- the per-ticker
    fold uses other fills to resolve supersession and consumption across fires
    (plan S2.3).  Excluding trade 11 must leave trade 12's latch filled."""
    after = _by_ticker(build_latch_derivation(
        two_filled_fires, _cfg(tmp_path), horizon_session_override=HORIZON,
        exclude_trade_ids=frozenset({11})))
    assert after["FTRE"].clear_reason is None
    assert after["VSTS"].clear_reason == "fill"
    assert after["VSTS"].clear_trade_id == 12


def test_an_empty_exclusion_set_is_the_same_as_no_exclusion(
        two_filled_fires, tmp_path) -> None:
    """``frozenset()`` is not ``None`` but must behave as one; a truthiness
    test on the parameter would be indistinguishable here and wrong elsewhere."""
    cfg = _cfg(tmp_path)
    bare = build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON)
    empty = build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON,
        exclude_trade_ids=frozenset())
    assert dataclasses.asdict(bare) == dataclasses.asdict(empty)


def test_excluding_an_absent_trade_id_changes_nothing(
        two_filled_fires, tmp_path) -> None:
    cfg = _cfg(tmp_path)
    bare = build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON)
    stray = build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON,
        exclude_trade_ids=frozenset({4242}))
    assert dataclasses.asdict(bare) == dataclasses.asdict(stray)


# ---------------------------------------------------------------------------
# criteria_lapse_armed_override
# ---------------------------------------------------------------------------
@pytest.fixture
def lapse_world(tmp_path, monkeypatch):
    """The shipped T5.6 geometry, reused rather than re-invented: an A+ fire
    then five structurally FAILING evaluated sessions whose closes decay past
    the materiality floor, so ``criteria_lapsed`` fires under an ARMED config
    and does not under an unarmed one."""
    from pathlib import Path

    from tests.latches.test_structural_verdicts import (
        _bars_frame,
        _seed_lapse_geometry,
    )

    from swing.config import load

    conn = ensure_schema(tmp_path / "lapse.db")
    days, _ = _seed_lapse_geometry(conn)
    conn.commit()
    frame = _bars_frame(days, [16.50, 16.20, 15.90, 15.60, 15.30, 15.00])

    import swing.data.ohlcv_archive as archive
    monkeypatch.setattr(
        archive, "resolve_ohlcv_window",
        lambda ticker, **kw: (frame, {"provider": "test"}))

    base = load(Path(__file__).resolve().parents[2] / "swing.config.toml")
    base = dataclasses.replace(
        base, paths=dataclasses.replace(base.paths, prices_cache_dir=tmp_path))
    armed = dataclasses.replace(
        base, latches=dataclasses.replace(base.latches, criteria_lapse_armed=True))
    unarmed = dataclasses.replace(
        base, latches=dataclasses.replace(base.latches, criteria_lapse_armed=False))
    try:
        yield conn, armed, unarmed, datetime(2026, 8, 5, 18, 0, 0)
    finally:
        conn.close()


def test_the_override_forces_the_drift_rung_OFF_against_an_armed_config(
        lapse_world) -> None:
    """RD's bound: a latch NEVER dies of drift.  The probe must be able to say
    so even when production config has armed the rung."""
    conn, armed_cfg, _unarmed_cfg, now = lapse_world
    armed = build_latch_derivation(conn, armed_cfg, now=now).latches[0]
    assert armed.clear_reason == "criteria_lapsed"

    forced = build_latch_derivation(
        conn, armed_cfg, now=now, criteria_lapse_armed_override=False).latches[0]
    assert forced.clear_reason is None


def test_None_READS_the_config_and_is_not_a_synonym_for_False(
        lapse_world) -> None:
    """The discriminator for ``bool(override)``: under ``None`` an ARMED config
    must STILL lapse.  An implementation coercing the tri-state to a bool reads
    the shipped default as disarmed and silently changes production."""
    conn, armed_cfg, _unarmed_cfg, now = lapse_world
    explicit_none = build_latch_derivation(
        conn, armed_cfg, now=now, criteria_lapse_armed_override=None).latches[0]
    assert explicit_none.clear_reason == "criteria_lapsed"


def test_the_override_can_also_force_the_rung_ON_against_an_unarmed_config(
        lapse_world) -> None:
    """The parameter is an OVERRIDE, not a one-way kill switch -- its declared
    type is ``bool | None``, and a ``False``-only implementation would leave the
    ``True`` branch untested and free to mean anything later."""
    conn, _armed_cfg, unarmed_cfg, now = lapse_world
    unarmed = build_latch_derivation(conn, unarmed_cfg, now=now).latches[0]
    assert unarmed.clear_reason is None

    forced = build_latch_derivation(
        conn, unarmed_cfg, now=now, criteria_lapse_armed_override=True).latches[0]
    assert forced.clear_reason == "criteria_lapsed"


# ---------------------------------------------------------------------------
# strict_decisions
# ---------------------------------------------------------------------------
def test_strict_decisions_raises_where_the_default_degrades_to_empty(
        tmp_path) -> None:
    """A bare DB has no ``latch_order_intents`` table, so the repo read RAISES
    inside the loader.  Default: ``{}`` (the shipped A6 degrade).  Strict: a
    TYPED error, so ``clear_reason is None`` can never mean "the decline ledger
    could not be read"."""
    from swing.latches.reader import DecisionIntentsUnavailableError

    conn = sqlite3.connect(tmp_path / "bare.db")
    try:
        assert load_decision_intents(conn, [1, 2]) == {}
        with pytest.raises(DecisionIntentsUnavailableError):
            load_decision_intents(conn, [1, 2], strict=True)
    finally:
        conn.close()


def test_strict_decisions_does_not_raise_on_a_SUCCESSFUL_empty_read(
        two_filled_fires) -> None:
    """Empty is a FACT, not a failure.  A strict mode that raised on "no
    decisions recorded" would refuse every ordinary mandate in the system."""
    fire_ids = [
        int(r[0]) for r in
        two_filled_fires.execute("SELECT id FROM candidates").fetchall()
    ]
    assert load_decision_intents(two_filled_fires, fire_ids, strict=True) == {}


def test_strict_decisions_propagates_out_of_build_latch_derivation(
        tmp_path) -> None:
    """The parameter has to reach the LOADER, not merely be accepted by the
    signature.  A pass-through that never threaded it would leave the resolver
    unable to distinguish an unread ledger from an absent one -- which is the
    whole clause."""
    from swing.latches.reader import DecisionIntentsUnavailableError

    cfg = _cfg(tmp_path)
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 121, "2026-07-17", "2026-07-20")
            _candidate(conn, 121, "FTRE", 18.34, 14.88)
            conn.execute("DROP TABLE latch_order_intents")

        # DEFAULT: degrades, no raise.
        assert build_latch_derivation(
            conn, cfg, horizon_session_override=HORIZON).latches

        with pytest.raises(DecisionIntentsUnavailableError):
            build_latch_derivation(
                conn, cfg, horizon_session_override=HORIZON,
                strict_decisions=True)
    finally:
        conn.close()


def test_strict_decisions_leaves_a_healthy_derivation_untouched(
        two_filled_fires, tmp_path) -> None:
    """Strict mode changes the FAILURE path only; on a readable ledger the
    derivation is identical."""
    cfg = _cfg(tmp_path)
    lenient = build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON)
    strict = build_latch_derivation(
        two_filled_fires, cfg, horizon_session_override=HORIZON,
        strict_decisions=True)
    assert dataclasses.asdict(lenient) == dataclasses.asdict(strict)


_CALL_RE = re.compile("[A-Za-z_]*build_latch_derivation[(]")

PRODUCTION_CALL_SITES: tuple[str, ...] = (
    "swing/cli_latches.py",
    "swing/web/routes/latches.py",
    "swing/web/routes/latches.py",
    "swing/web/view_models/latches.py",
    "swing/web/view_models/latches.py",
    "swing/web/view_models/latches.py",
)


def test_every_production_call_site_still_passes_none_of_the_three() -> None:
    """SIX shipped callers, ENUMERATED by walking the tree rather than counted.

    The count in this module's docstring was wrong on its first writing, and a
    prose count cannot fail.  This walks ``swing/`` for every
    ``build_latch_derivation(`` call, excludes the definition and this arc's own
    new caller in ``swing/trades/latched_origin.py``, and asserts BOTH that the
    roster matches AND that not one of them mentions any of the three new
    parameter names -- so "the defaults preserve behaviour" is checked against
    the tree instead of asserted about it.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "swing"
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root.parent).as_posix()
        if rel == "swing/latches/reader.py":
            continue                       # the definition, not a call site
        for match in re.finditer(_CALL_RE, text):
            # The call's full argument text, up to its closing paren.
            depth, i = 0, match.end() - 1
            while i < len(text):
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            call = text[match.end():i]
            if rel == "swing/trades/latched_origin.py":
                continue                   # THIS arc's caller; it passes all three
            found.append(rel)
            for name in ("criteria_lapse_armed_override", "exclude_trade_ids",
                         "strict_decisions"):
                assert name not in call, (
                    f"{rel} now passes {name}; the byte-for-byte default claim "
                    f"in this module no longer covers it"
                )
    assert tuple(found) == PRODUCTION_CALL_SITES, (
        f"the production call-site roster moved: {found}"
    )
