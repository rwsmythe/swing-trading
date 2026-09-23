"""22-A2 Task 6 -- the rung-9 escape seam in ``latched_origin.py`` (A2-61..A2-66).

Rung 9 is RD's refuse-by-default for a pre-barrier fire.  22-A2 ESCAPES it --
never removes it -- for exactly one shape (R0.10 encoding 2): the barrier is
installed (checked FIRST, unchanged), the STORED tier and the READ-TIME tier
BOTH say ``pre_barrier_reconstructed``, and a supplied ``tier2`` request's
preflight passed and its four-part conjunction admits THIS link's fire.  Every
other combination behaves exactly as 22-A shipped, and evidence supplied where
there is no escape to take REFUSES and names why (encoding 3).

The escape world is trade 25's REAL row shape (``tests/_tier2_world_22a2.py``:
candidate 12284 / OII / pivot 53.97999954223633 / stop 41.41999816894531, fire
run 136 with its pipeline row 150, fill 48 on 2026-08-17, the pre-barrier link
minted the production way).  The archive closes for the probe window
[2026-08-10, 2026-08-14] are SYNTHETIC -- above the stop and below the pivot,
the probe world's own convention (``t25_cfg``) -- because
the probe is not this task's subject and the live OII bars are Task 11's.  The
post-barrier controls (A2-64 reverse, A2-66) reuse 22-A's FTRE probe world.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import inspect
import json
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from swing.data.models import (
    FREEZE_TIER_LIVE_AT_ACCEPTANCE,
    FREEZE_TIER_PRE_BARRIER,
)
from swing.trades import frozen_value_evidence as fve
from swing.trades import latched_origin as lo
from tests._tier2_world_22a2 import (
    LINE57_FIXTURE,
    T25_AUTHOR_INSTANT,
    T25_CANDIDATE_ID,
    T25_ENVELOPE,
    T25_FILL_PRICE,
    T25_FILL_QTY,
    T25_FILL_SESSION,
    T25_ORDER_ID,
    T25_TICKER,
    T25_TRADE_ID,
    base_last_word_payload,
    build_pre_barrier_world,
    insert_payload,
    t25_cfg,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LINE57_TEXT = LINE57_FIXTURE.read_bytes().decode("utf-8")
READ_AT = "2026-09-23T12:00:00.000"
SHA_9F315CC6 = "9f315cc64a8f171049b510021e6418bc261c50b7"
ORIGIN_MAIN_348F126B = "348f126bb463519999ae7b183de98af448112557"


def _facts(*, quoted: str = LINE57_TEXT, is_ancestor: bool = True) -> fve.ArtifactFacts:
    """The preflight's facts for 9f315cc6 as measured (P24/P36)."""
    author = datetime.fromisoformat(T25_AUTHOR_INSTANT)
    return fve.ArtifactFacts(
        selection=fve.EvidenceSelection(
            artifact_path="docs/rd-state.md", artifact_commit_sha=SHA_9F315CC6,
            quoted_text=quoted),
        author_instant=author, committer_instant=author,
        is_ancestor=is_ancestor, resolved_remote_ref_sha=ORIGIN_MAIN_348F126B,
        descendant_count=684 if is_ancestor else None,
        remote_ref_updated_at=None, remote_ref_age_seconds=None)


def _tier2(facts: fve.ArtifactFacts | None = None, *,
           failure: str | None = None, detail: str = "") -> fve.Tier2Request:
    if failure is not None:
        pre = fve.PreflightResult(facts=None, failure=failure, detail=detail)
    else:
        pre = fve.PreflightResult(facts=facts or _facts(), failure=None, detail="")
    return fve.Tier2Request(preflight=pre, applied_at=READ_AT)


def _t25_world(tmp_path: Path, name: str = "t25"):
    conn, ids = build_pre_barrier_world(tmp_path, name)
    return conn, t25_cfg(tmp_path / name), ids


def _t25_req() -> SimpleNamespace:
    """The correction path's request shape (``_resolve_latch_citation``)."""
    return SimpleNamespace(
        ticker=T25_TICKER, entry_date=T25_FILL_SESSION,
        entry_price=T25_FILL_PRICE, shares=float(T25_FILL_QTY),
        fill_origin="schwab_auto", schwab_source_value_json=T25_ENVELOPE,
        hypothesis_label=None)


def _resolve_t25(conn, cfg, **kw) -> lo.LatchedProvenance:
    return lo.resolve_latched_provenance(
        conn, cfg, _t25_req(), trade_id=T25_TRADE_ID,
        exclude_trade_ids=frozenset({T25_TRADE_ID}), **kw)


def _t25_order(conn) -> lo.AcceptedLatchOrder:
    orders = lo.find_accepted_latch_order(conn, broker_order_id=T25_ORDER_ID)
    assert len(orders) == 1, orders
    return orders[0]


def _authorize_t25(conn, cfg, order, **kw) -> lo.LatchedProvenance:
    return lo.authorize_accepted_order(
        conn, cfg, order=order, ticker=T25_TICKER,
        fill_session=date.fromisoformat(T25_FILL_SESSION),
        price=T25_FILL_PRICE, shares=float(T25_FILL_QTY),
        fill_origin="schwab_auto", envelope_symbol=T25_TICKER,
        exclude_trade_ids=frozenset({T25_TRADE_ID}), trade_id=T25_TRADE_ID,
        competitor_rung=lo.competitor_liveness_rung, **kw)


# --------------------------------------------------------------------------- A2-61

def test_a2_61_pre_barrier_link_with_a_passing_tier2_escapes_rung_nine(
    tmp_path: Path,
) -> None:
    """PRE: ``pre_barrier_unproven`` (the refuse-by-default).  POST: admitted,
    rung 9 recorded in its OWN voice, the probe blob on the tier-2 version and
    the seventh-column blob carried."""
    conn, cfg, ids = _t25_world(tmp_path)
    try:
        verdict = _resolve_t25(conn, cfg, tier2=_tier2())
        assert verdict.admitted is True, (verdict.decline_reason, verdict.tier2_refusal)
        assert verdict.freeze_tier == FREEZE_TIER_PRE_BARRIER
        assert verdict.candidate_id == T25_CANDIDATE_ID
        assert verdict.trade_origin == "pipeline_aplus"
        assert verdict.tier2_refusal is None

        probe = verdict.probe_evidence
        assert probe is not None
        assert probe["evidence_version"] == lo.LATCH_PROBE_TIER2_EVIDENCE_VERSION == "2026-09-23.1"
        assert set(probe) == set(lo.PROBE_EVIDENCE_KEYS)
        auth = probe["authorization"]
        assert set(auth) == set(lo.AUTHORIZATION_KEYS)
        assert auth["rung9_stored_freeze_tier"] == {
            "input": "pre_barrier_reconstructed", "verdict": "escaped_by_tier2"}
        # Every OTHER entry still reads pass: the escape changes one verdict.
        others = {k: v["verdict"] for k, v in auth.items()
                  if k != "rung9_stored_freeze_tier"}
        assert set(others.values()) == {lo.AUTHORIZATION_VERDICT_PASS}, others
        assert {v["verdict"] for v in auth.values()} <= lo.AUTHORIZATION_VERDICTS

        seventh = verdict.frozen_value_evidence
        assert seventh is not None
        assert set(seventh) == set(fve.FROZEN_VALUE_BLOB_KEYS)
        assert seventh["evidence_version"] == fve.FROZEN_VALUE_EVIDENCE_VERSION
        assert seventh["evaluated_at"] == READ_AT
        assert seventh["fill_session_date"] == T25_FILL_SESSION
        assert (seventh["quoted_ticker_text"], seventh["quoted_pivot_text"],
                seventh["quoted_invalidation_text"]) == ("OII", "53.98", "41.42")
        # The blobs are JSON-serialisable as the service will store them.
        json.dumps(probe)
        json.dumps(seventh)

        # AUTHORIZE-THEN-ABORT, at the rung's grain: the two blobs the escape
        # produced, on the production service's own base row for trade 25,
        # are ADMITTED raw by the HEAD citation trigger (the service writing
        # them is Task 7's; this pins that rung 9 emits what the trigger binds).
        payload = copy.deepcopy(base_last_word_payload(tmp_path))
        assert payload["applied_at"] == READ_AT
        payload.update(
            provenance_correction_id=None, admission_tier="latch_ladder_tier2",
            cited_latch_link_id=ids["link_id"],
            cited_latch_validity_intent_id=ids["validity_id"],
            cited_latch_place_intent_id=ids["place_id"],
            cited_latch_broker_order_id=T25_ORDER_ID,
            cited_latch_probe_json=json.dumps(probe),
            cited_frozen_value_evidence_json=json.dumps(seventh))
        insert_payload(conn, payload)
        assert conn.execute(
            "SELECT admission_tier FROM provenance_corrections").fetchone() == (
            "latch_ladder_tier2",)
        conn.rollback()

        # The counterfactual, on the SAME world: no tier2 -> 22-A's refusal.
        assert _resolve_t25(conn, cfg).decline_reason == "pre_barrier_unproven"
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-62

def test_a2_62_pre_barrier_link_without_tier2_is_unchanged(tmp_path: Path) -> None:
    conn, cfg, _ids = _t25_world(tmp_path)
    try:
        default = _resolve_t25(conn, cfg)
        explicit_none = _resolve_t25(conn, cfg, tier2=None)
        for verdict in (default, explicit_none):
            assert verdict.admitted is False
            assert verdict.decline_reason == "pre_barrier_unproven"
            # Rung 9 refused BEFORE the probe, exactly as 22-A shipped.
            assert verdict.probe_evidence is None
            assert verdict.clear_reason is None
            assert verdict.frozen_value_evidence is None
            assert verdict.tier2_refusal is None
        assert default == explicit_none
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-63

def test_a2_63_barrier_absent_refuses_before_any_escape(tmp_path: Path) -> None:
    """An escape-before-barrier implementation ADMITS here."""
    conn, cfg, _ids = _t25_world(tmp_path)
    try:
        # Control: with the barrier standing, the same tier2 escapes.
        assert _resolve_t25(conn, cfg, tier2=_tier2()).admitted is True
        conn.execute("DROP TRIGGER trg_candidates_no_update")
        conn.commit()
        verdict = _resolve_t25(conn, cfg, tier2=_tier2())
        assert verdict.admitted is False
        assert verdict.decline_reason == "barrier_not_installed"
        assert verdict.frozen_value_evidence is None
        assert verdict.probe_evidence is None
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-64

def test_a2_64_stored_and_read_time_tiers_disagreeing_never_escape(
    tmp_path: Path,
) -> None:
    """Both directions of the disagreement refuse ``pre_barrier_unproven``.

    (a) STORED live, read-time pre (a forged stored tier on trade 25's
    pre-barrier fire): a stored-tier-only rung takes the live path and answers
    ``tier2_evidence_refused``/``no_escape_to_take``.  (b) STORED pre,
    read-time live (22-A's post-barrier FTRE fire with its stored tier forged
    pre): a stored-tier-only rung would run the conjunction.
    """
    conn, cfg, _ids = _t25_world(tmp_path, "a")
    try:
        order = _t25_order(conn)
        assert order.freeze_tier == FREEZE_TIER_PRE_BARRIER
        forged = dataclasses.replace(order, freeze_tier=FREEZE_TIER_LIVE_AT_ACCEPTANCE)
        verdict = _authorize_t25(conn, cfg, forged, tier2=_tier2())
        assert verdict.decline_reason == "pre_barrier_unproven"
        assert verdict.tier2_refusal is None
        assert verdict.frozen_value_evidence is None
    finally:
        conn.close()

    from tests._latch_probe_world_22a import (
        BROKER_ORDER_ID,
        FILL_SESSION,
        TICKER,
    )
    from tests.trades.test_22a_task9_entry_wiring import (
        ACCEPT_SESSION,
        accept_and_link,
        build_world,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "b")
    try:
        accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
        conn.commit()
        [order] = lo.find_accepted_latch_order(conn, broker_order_id=BROKER_ORDER_ID)
        assert order.freeze_tier == FREEZE_TIER_LIVE_AT_ACCEPTANCE
        forged = dataclasses.replace(order, freeze_tier=FREEZE_TIER_PRE_BARRIER)
        verdict = lo.authorize_accepted_order(
            conn, cfg, order=forged, ticker=TICKER, fill_session=FILL_SESSION,
            price=18.50, shares=2.0, fill_origin="schwab_auto",
            envelope_symbol=TICKER, exclude_trade_ids=frozenset(),
            tier2=_tier2())
        assert verdict.decline_reason == "pre_barrier_unproven"
        assert verdict.tier2_refusal is None
        assert verdict.frozen_value_evidence is None
    finally:
        conn.close()


# --------------------------------------------------------------------------- A2-65

def _calls_to(tree: ast.AST, names: set[str]) -> list[ast.Call]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        callee = (fn.id if isinstance(fn, ast.Name)
                  else fn.attr if isinstance(fn, ast.Attribute) else None)
        if callee in names:
            found.append(node)
    return found


def test_a2_65_the_entry_path_never_passes_the_escape() -> None:
    """The CALLER-SIDE obligation (gotcha #31): ``record_entry``'s wiring
    passes no ``tier2``.  Pinned together with the parameter's EXISTENCE, so
    the pin cannot pass vacuously on a module where the keyword was never
    added."""
    for fn in (lo.resolve_latched_provenance, lo.authorize_accepted_order):
        param = inspect.signature(fn).parameters.get("tier2")
        assert param is not None, fn.__name__
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        assert param.default is None

    entry = REPO_ROOT / "swing" / "trades" / "entry.py"
    tree = ast.parse(entry.read_text(encoding="utf-8"))
    calls = _calls_to(tree, {"resolve_latched_provenance", "authorize_accepted_order"})
    assert calls, "the entry wiring's call to the resolver was not found"
    for call in calls:
        kws = {k.arg for k in call.keywords}
        assert "tier2" not in kws, ast.unparse(call)
        assert None not in kws, f"a **kwargs splat could smuggle tier2: {ast.unparse(call)}"


# --------------------------------------------------------------------------- A2-66

def test_a2_66_evidence_with_no_escape_to_take_refuses_and_names_why(
    tmp_path: Path,
) -> None:
    """A post-barrier admission + ``tier2`` -> ``tier2_evidence_refused`` /
    ``no_escape_to_take``.  A silent-ignore implementation ADMITS (and the
    service would write a ``latch_ladder`` row, discarding the input)."""
    from tests.trades.test_22a_task9_entry_wiring import (
        ACCEPT_SESSION,
        accept_and_link,
        build_world,
        req,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "post")
    try:
        accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
        conn.commit()
        control = lo.resolve_latched_provenance(conn, cfg, req())
        assert control.admitted is True, control.decline_reason
        assert control.freeze_tier == FREEZE_TIER_LIVE_AT_ACCEPTANCE

        verdict = lo.resolve_latched_provenance(conn, cfg, req(), tier2=_tier2())
        assert verdict.admitted is False
        assert verdict.recognised_but_underivable is True
        assert verdict.decline_reason == "tier2_evidence_refused"
        assert verdict.tier2_refusal == "no_escape_to_take"
        assert verdict.frozen_value_evidence is None
    finally:
        conn.close()


# ------------------------------------------------ refusal legibility (no roster id)

def test_rung_nine_names_the_failing_criterion_of_a_refused_conjunction(
    tmp_path: Path,
) -> None:
    conn, cfg, _ids = _t25_world(tmp_path)
    try:
        wrong_pivot = LINE57_TEXT.replace("53.98", "53.93")
        verdict = _resolve_t25(conn, cfg, tier2=_tier2(_facts(quoted=wrong_pivot)))
        assert verdict.decline_reason == "tier2_evidence_refused"
        assert verdict.tier2_refusal == "criterion 3: pivot"
        assert verdict.probe_evidence is None
        assert verdict.frozen_value_evidence is None

        not_ancestor = _resolve_t25(conn, cfg, tier2=_tier2(_facts(is_ancestor=False)))
        assert not_ancestor.decline_reason == "tier2_evidence_refused"
        assert not_ancestor.tier2_refusal == "criterion 1: not_ancestor_of_origin_main"
    finally:
        conn.close()


def test_rung_nine_carries_a_failed_preflight_as_the_refusal_detail(
    tmp_path: Path,
) -> None:
    conn, cfg, _ids = _t25_world(tmp_path)
    try:
        verdict = _resolve_t25(conn, cfg, tier2=_tier2(
            failure=fve.FAILURE_EVIDENCE_FILE_MALFORMED, detail="not a JSON object"))
        assert verdict.decline_reason == "tier2_evidence_refused"
        assert verdict.tier2_refusal == "evidence_file_malformed: not a JSON object"
        assert verdict.probe_evidence is None
    finally:
        conn.close()


def test_rung_nine_contains_a_raising_conjunction_as_a_refusal(
    tmp_path: Path, monkeypatch,
) -> None:
    """Ignorance is a refusal naming the escape, never an escaped exception
    and never the broad handler's ``aliveness_unverifiable``."""
    conn, cfg, _ids = _t25_world(tmp_path)

    def _boom(*_a, **_k):
        raise LookupError("candidate row vanished")

    monkeypatch.setattr(fve, "evaluate_conjunction", _boom)
    try:
        verdict = _resolve_t25(conn, cfg, tier2=_tier2())
        assert verdict.decline_reason == "tier2_evidence_refused"
        assert verdict.tier2_refusal is not None
        assert verdict.tier2_refusal.startswith("tier2_unverifiable: LookupError")
    finally:
        conn.close()


def test_the_decline_roster_gains_exactly_the_one_tier2_reason() -> None:
    assert "tier2_evidence_refused" in lo.DECLINE_REASONS
    assert len(lo.DECLINE_REASONS) == 37
