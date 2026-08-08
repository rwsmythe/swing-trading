"""POST /latches/intent -- the LOG-ONLY intent ledger write path (Task 7).

NOTHING is sent to the broker on any branch. The write path is 21-C, behind an
operator-signed L2 endpoint diff; Task 10 pins that BEHAVIOURALLY at the HTTP
transport rather than by grepping method names.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.latches.constants import LATCH_BROKER_SNAPSHOT_KEYS
from swing.latches.reader import build_latch_derivation
from swing.web.app import create_app

NOW = datetime(2026, 7, 25, 12, 0)      # Saturday -> action session 2026-07-27
ANCHOR = "2026-07-27"
DERIVATION_SESSION = "2026-07-24"
_HX = {"HX-Request": "true"}


def _write_archive_bars(cfg, rows, ticker="FTRE"):
    """Shape-A OHLCV archive bars for `ticker`, as `(iso_session, close)`.

    THE ARCHIVE IS THE ONLY READ-SIDE SOURCE THAT DATES A CLOSE PER ROW. Shape A
    (`{T}.yfinance.parquet`) is deliberate: the panel reads with `migrate=False`
    (the A4 no-write property), so a legacy `{T}.parquet` is invisible here
    exactly as it is in production.
    """
    import pandas as pd
    cache = Path(cfg.paths.prices_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{ticker.upper()}.yfinance.parquet"
    frame = pd.DataFrame([
        {"asof_date": session, "open": close, "high": close, "low": close,
         "close": close, "volume": 100.0}
        for session, close in rows
    ])
    # MERGES rather than clobbers, exactly as `write_window` does. A helper that
    # replaced the file would silently un-date bars an earlier seed proved.
    if path.exists():
        frame = pd.concat([pd.read_parquet(path), frame], ignore_index=True)
        frame = frame.drop_duplicates(subset="asof_date", keep="last")
    frame.to_parquet(path)


def _seed(cfg, *, regime_close=19.20):
    """FTRE's real geometry PLUS a close the archive DATES to the derivation
    session.

    THE CLOSE DATE IS STATED AND IT IS NOT THE DERIVATION SESSION BY ACCIDENT:
    only a close PROVEN to be the derivation session's may pick the mandate
    form, so without this the form is WITHHELD and there is nothing to accept. A
    fixture that quietly used the derivation session as the close date would be
    the run-level-stamp error (#30) planted in a test.

    The run stamp alone is NOT that proof -- it is an upper bound -- so the
    matching archive bar is seeded with it. That is the seed the pre-fix code
    did not need, and its absence is why no test covered a stamp the archive
    contradicts.
    """
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
        if regime_close is not None:
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) VALUES "
                "(900, ?, ?, ?, 1, 0, 1, 0, 0, 0)",
                (f"{DERIVATION_SESSION}T17:30:05", DERIVATION_SESSION, ANCHOR))
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(900, 'FTRE', 'watch', ?, 18.34, 14.88, 'universe')",
                (regime_close,))
    conn.close()
    if regime_close is not None:
        _write_archive_bars(cfg, [(DERIVATION_SESSION, regime_close)])
    return cid


@pytest.fixture
def frozen_clocks(monkeypatch):
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)


def _seed_extra_close(cfg, session, price, *, run_id):
    """Another close, DATED `session` -- stated explicitly, never derived from
    the render clock (#30)."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(?, ?, ?, ?, 1, 0, 1, 0, 0, 0)",
            (run_id, f"{session}T17:30:05", session, session))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(?, 'FTRE', 'watch', ?, 18.34, 14.88, 'universe')",
            (run_id, price))
    conn.close()
    # ...and the archive bar that PROVES that date. The stamp alone is an upper
    # bound (#30); without the bar the later render withholds its form.
    _write_archive_bars(cfg, [(session, price)])


def _anchor_form(cfg, cid, *, now=NOW):
    """The hidden anchor EXACTLY as the rendered form emits it."""
    from swing.web.view_models.latches import build_latch_panel_vm
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg, now=now)
    finally:
        conn.close()
    row = next(r for r in vm.rows if r.candidate_id == cid)
    assert row.prepared_order.offered, "the fixture must reach the OFFERED form"
    return dict(row.prepared_order.anchor_fields)


def _intents(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT intent_id, intent_kind, action_session_date, recorded_ts, "
            "framework_order_type, framework_limit_price, framework_quantity, "
            "decline_reason, validity_outcome, actual_quantity, "
            "actual_broker_order_id, validated_place_intent_id "
            "FROM latch_order_intents ORDER BY intent_id").fetchall()
    finally:
        conn.close()


def _schwab_calls(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0]
    finally:
        conn.close()


# --- the endpoint contract ------------------------------------------------
def test_get_on_the_intent_path_is_405(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.get("/latches/intent").status_code == 405


def test_a_place_intent_records_the_framework_order_verbatim(
        seeded_db, frozen_clocks):
    """The ledger's central claim: the recorded framework order is byte-
    identically what the operator was looking at."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 200
    (row,) = _intents(cfg)
    assert row[1] == "place"
    assert row[2] == ANCHOR
    assert row[3].startswith("2026-07-25")      # SERVER-stamped, not from form
    assert (row[4], row[5], row[6]) == ("LIMIT", 18.89, 9)


def test_a_close_the_archive_CONTRADICTS_writes_NOTHING_to_the_ledger(
        seeded_db, frozen_clocks):
    """`derivation_regime_close_session` is written as FACT into an APPEND-ONLY
    ledger, so an unproven date recorded there is not recoverable by fixing a
    render. This is the ledger half of the provenance gate.

    The form is captured against a CORROBORATED render and the true archive bar
    then lands -- the realistic GET->POST window. The POST re-derives through
    the SAME path the GET rendered through, finds the form now WITHHELD, and
    writes nothing at all.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)                        # rung A: 19.20, corroborated at S
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    assert form["derivation_regime_close_session"] == DERIVATION_SESSION
    # The archive lands FTRE's true 2026-07-24 bar: 17.76, BELOW the pivot, so
    # the recorded 19.20 is not merely undated -- it is contradicted, and it
    # picked the wrong instrument.
    _write_archive_bars(cfg, [(DERIVATION_SESSION, 17.76)])
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 409
    assert "WITHHELD" in r.text
    assert _intents(cfg) == []


def test_a_PROVEN_place_intent_STORES_the_close_and_its_proven_session(
        seeded_db, frozen_clocks):
    """The POSITIVE half of the ledger claim (codex-auto-review P3).

    Asserting only that an unproven close writes NOTHING leaves the stored
    provenance itself unasserted: those two columns could be NULL, or carry the
    wrong session, and the negative test would still pass. `_intents` does not
    select them, so this reads them directly.

    NOT a pre-fix/post-fix discriminator and not claimed as one -- this fixture
    is rung A, which both gates offer. It is coverage of WHAT gets stored on the
    one path that is allowed to store anything.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)                        # rung A: 19.20, corroborated at S
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 200
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT derivation_regime_close, derivation_regime_close_session "
            "FROM latch_order_intents ORDER BY intent_id").fetchall()
    finally:
        conn.close()
    assert rows == [(19.20, DERIVATION_SESSION)]


def test_the_response_fragment_root_is_not_a_table_row(seeded_db, frozen_clocks):
    """An HTMX response leading with `<tr>` triggers makeFragment's synthetic
    table wrap, which DROPS table content inside OOB section chunks. Browser
    only -- TestClient asserts bodies, not DOM -- so the shape is pinned here
    and the behaviour at the GUI witness."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.text.lstrip().startswith("<section")
    assert not r.text.lstrip().startswith("<tr")


def test_the_form_carries_hx_headers_and_its_own_hx_target(
        seeded_db, frozen_clocks):
    """Two browser-only failure surfaces at once: an embedded form inside an
    HTMX fragment needs HX-Request or OriginGuard strict mode 403s the submit,
    and `hx-target` INHERITS from ancestors, so a card inside `.latch-cards`
    must target itself."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert 'hx-post="/latches/intent"' in r.text
    assert 'hx-target="this"' in r.text
    assert "HX-Request" in r.text


def test_the_base_layout_still_carries_the_4xx_swap_override(
        seeded_db, frozen_clocks):
    """Without it the 400/409 fragments are INVISIBLE in a browser and the
    endpoint silently loses its entire error surface."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert "responseHandling" in r.text


def test_a_withheld_card_renders_NO_accept_control_at_all(
        seeded_db, frozen_clocks):
    """A disabled-looking button that posts is worse than no button. The
    withheld state is TODAY's live state, so this is the normal render."""
    cfg, cfg_path = seeded_db
    _seed(cfg, regime_close=None)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert "PREPARED ORDER WITHHELD" in r.text
    assert "ACCEPT - log this order" not in r.text


# --- hazard (a): the idempotency key --------------------------------------
def test_a_double_post_yields_ONE_row_and_the_SAME_intent_id(
        seeded_db, frozen_clocks):
    """The key is CONTENT-derived, not a render-time nonce, so a refresh
    followed by an identical resubmit also collapses."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = client.post("/latches/intent", headers=_HX, data=form)
        second = client.post("/latches/intent", headers=_HX, data=form)
    assert first.status_code == second.status_code == 200
    rows = _intents(cfg)
    assert len(rows) == 1
    assert str(rows[0][0]) in first.text and str(rows[0][0]) in second.text
    assert "already recorded" in second.text


def test_a_replay_is_NEVER_409d_even_after_the_anchor_goes_stale(
        seeded_db, monkeypatch):
    """THE ORDERING TEST a naive handler fails. Step 4 precedes step 5, so a
    retry of an ALREADY-RECORDED intent succeeds even after the world has
    moved: recording the intent is the TERMINAL STATE, and the freshness gates
    exist to stop a stale view producing a NEW row -- not to punish a resubmit
    of a row already written."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.post(
            "/latches/intent", headers=_HX, data=form).status_code == 200
        # ...the clock rolls several sessions forward.
        monkeypatch.setattr(
            route_mod, "_now", lambda: datetime(2026, 7, 31, 12, 0))
        replay = client.post("/latches/intent", headers=_HX, data=form)
    assert replay.status_code == 200
    assert len(_intents(cfg)) == 1


def test_a_NEW_intent_on_that_same_stale_anchor_is_409d(seeded_db, monkeypatch):
    """The paired discriminator: step 5 STILL binds for a first insert. Without
    it the replay carve-out would have disabled the staleness gate entirely."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {
        "intent_kind": "decline", "decline_reason": "too extended"}
    monkeypatch.setattr(route_mod, "_now", lambda: datetime(2026, 7, 31, 12, 0))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 409
    assert "stale" in r.text.lower()
    assert _intents(cfg) == []


def test_the_lost_race_returns_the_winners_row_and_never_500s(
        seeded_db, frozen_clocks, monkeypatch):
    """Two requests can BOTH miss step 4. `ON CONFLICT DO NOTHING` plus the
    step-7 re-SELECT means the loser returns the WINNER's row rather than
    surfacing an IntegrityError -- and it is an INSERT-time no-op, NOT
    `INSERT OR REPLACE`, so no DELETE, no new PK and no cascade."""
    import swing.data.repos.latch_order_intents as repo
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        client.post("/latches/intent", headers=_HX, data=form)
        winner_id = _intents(cfg)[0][0]
        # Simulate the seam: the handler's step-4 SELECT misses even though the
        # row exists, so step 6 collides.
        real = repo.get_intent_by_key
        calls = {"n": 0}

        def _miss_once(conn, *, idempotency_key):
            calls["n"] += 1
            if calls["n"] == 1:
                return None
            return real(conn, idempotency_key=idempotency_key)

        monkeypatch.setattr(repo, "get_intent_by_key", _miss_once)
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 200
    assert len(_intents(cfg)) == 1
    assert str(winner_id) in r.text


# --- hazard (b): the hidden anchor ---------------------------------------
def test_a_mutated_framework_price_is_409d_with_ZERO_rows_written(
        seeded_db, frozen_clocks):
    """The handler NEVER substitutes the fresh computation for the anchored one.
    Re-deriving to VALIDATE is not substituting."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {
        "intent_kind": "place", "framework_limit_price": "17.00"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 409
    assert "framework_limit_price" in r.text
    assert _intents(cfg) == []


def test_a_mutated_anchor_CHANGES_the_key_so_step_5_actually_runs(
        seeded_db, frozen_clocks):
    """THE LAUNDERING DEFENCE. If the key covered only the session and the
    answer, a tampered form carrying a DIFFERENT framework order but the same
    session and answer would hit the replay SELECT and return 200 WITHOUT ever
    reaching the comparison -- straight through the hidden-anchor defence. So
    the mutated resubmit must MISS step 4 and be 409'd, not replayed as 200."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    good = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.post(
            "/latches/intent", headers=_HX, data=good).status_code == 200
        tampered = dict(good) | {"framework_quantity": "50"}
        r = client.post("/latches/intent", headers=_HX, data=tampered)
    assert r.status_code == 409
    assert len(_intents(cfg)) == 1


def test_a_derivation_only_mutation_is_also_caught(seeded_db, frozen_clocks):
    """SECTION A.4's closure in anger: `real_equity` can move while the floor
    still binds, so `sizing_equity` is UNCHANGED -- and under the pre-fix column
    set this POST SUCCEEDED, recording a derivation line the operator
    demonstrably did not see."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {
        "intent_kind": "place", "derivation_real_equity": "9999.00"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 409
    assert "derivation_real_equity" in r.text
    assert _intents(cfg) == []


def test_the_same_decision_in_two_sessions_writes_TWO_rows(
        seeded_db, monkeypatch):
    """The decision kinds are UNCHANGED by the validity kind-scoping: their
    session component still discriminates."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)
    cid = _seed(cfg)
    base = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.post(
            "/latches/intent", headers=_HX, data=base).status_code == 200
        # The NEXT session's render needs its OWN derivation-session close, and
        # it is seeded ONLY NOW: `load_last_closes` returns the GLOBALLY latest
        # close per ticker, so planting it up front would have made the FIRST
        # render's close newer than ITS derivation session and withheld that
        # form instead -- the session-gate working correctly, on the wrong side.
        _seed_extra_close(cfg, ANCHOR, 19.40, run_id=901)
        # 06:00 HST is 12:00 ET -- MID-SESSION, so the action session is that
        # same Tuesday. 12:00 HST would be post-close and roll to Wednesday,
        # whose derivation session has no seeded close.
        rolled = datetime(2026, 7, 28, 6, 0)
        monkeypatch.setattr(route_mod, "_now", lambda: rolled)
        monkeypatch.setattr(vm_mod, "_now", lambda: rolled)
        later = _anchor_form(cfg, cid, now=rolled) | {"intent_kind": "place"}
        assert later["view_session_date"] == "2026-07-28"
        r = client.post("/latches/intent", headers=_HX, data=later)
        assert r.status_code == 200, r.text
    assert len(_intents(cfg)) == 2


# --- the shape ladder ------------------------------------------------------
@pytest.mark.parametrize("overrides,field", [
    ({"intent_kind": "decline"}, "decline_reason"),
    ({"intent_kind": "decline", "decline_reason": "   "}, "decline_reason"),
    ({"intent_kind": "cancel"}, "actual_broker_order_id"),
    ({"intent_kind": "attest"}, "attested_disposition"),
    ({"intent_kind": "attest", "attested_disposition": "shrug"},
     "attested_disposition"),
    ({"intent_kind": "teleport"}, "intent_kind"),
    ({"intent_kind": "place", "candidate_id": "0"}, "candidate_id"),
    ({"intent_kind": "place", "view_session_date": "2026-7-27"},
     "view_session_date"),
    ({"intent_kind": "place", "view_session_date": "garbage"},
     "view_session_date"),
])
def test_the_400_names_the_offending_field_and_writes_nothing(
        seeded_db, frozen_clocks, overrides, field):
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | overrides
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 400, overrides
    assert field in r.text
    assert _intents(cfg) == []


def test_a_future_session_anchor_is_rejected(seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {
        "intent_kind": "place", "view_session_date": "2026-09-01"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 400
    assert "view_session_date" in r.text
    assert _intents(cfg) == []


def test_a_non_session_anchor_is_rejected(seeded_db, frozen_clocks):
    """Load-bearing and NOT implied by the proximity check: a weekend date can
    sit one session behind and would otherwise be written as a
    `view_session_date`, corrupting the session keyspace the ledger joins on."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {
        "intent_kind": "place", "view_session_date": "2026-07-26"}   # Sunday
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 400
    assert "session" in r.text
    assert _intents(cfg) == []


def test_a_decline_records_its_reason_and_the_framework_block_it_declined(
        seeded_db, frozen_clocks):
    """A decline carries the SAME framework + derivation block as a place.
    Erasing it would leave RD unable to audit WHAT was declined without
    recomputing it -- which is exactly what storing the framework side verbatim
    exists to prevent. Declines are excluded from execution-parity ORDER rows by
    `intent_kind`, never by erasing their subject."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {
        "intent_kind": "decline", "decline_reason": "gap risk into earnings"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 200
    (row,) = _intents(cfg)
    assert row[1] == "decline"
    assert row[7] == "gap risk into earnings"
    assert (row[4], row[5], row[6]) == ("LIMIT", 18.89, 9)


def test_a_cancel_targets_a_broker_order_id_and_never_a_ticker(
        seeded_db, frozen_clocks):
    """HAZARD (c), across all three layers. The form does not emit a blank one,
    the handler 400s it (above), and the schema CHECK makes the row unwritable.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "cancel", "actual_broker_order_id": "1002"})
    assert r.status_code == 200
    (row,) = _intents(cfg)
    assert row[1] == "cancel"
    assert row[10] == "1002"


def test_an_attestation_a_week_after_the_latch_went_terminal_is_ACCEPTED(
        seeded_db, monkeypatch):
    """The non-decision kinds submit NO framework block, so the handler MUST NOT
    invent a comparison -- it would 409 every attestation the moment the
    underlying derivation moved, which for an AGED PROMPT IS ALWAYS."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    later = datetime(2026, 8, 4, 12, 0)
    monkeypatch.setattr(route_mod, "_now", lambda: later)
    monkeypatch.setattr(vm_mod, "_now", lambda: later)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": "2026-08-05", "candidate_id": str(cid),
            "intent_kind": "attest", "attested_disposition": "was_away"})
    assert r.status_code == 200
    (row,) = _intents(cfg)
    assert row[1] == "attest"


# --- RULING 3: the SUBMISSION IN CONTEXT -----------------------------------
def _attest(client, cid, disposition, prior):
    return client.post("/latches/intent", headers=_HX, data={
        "view_session_date": ANCHOR, "candidate_id": str(cid),
        "intent_kind": "attest", "attested_disposition": disposition,
        "prior_intent_id": prior})


def test_an_A_to_B_to_A_CORRECTION_writes_a_THIRD_ROW_and_GOVERNS(
        seeded_db, frozen_clocks):
    """RD RULING 3 (2026-07-30). THE LEDGER'S UNIT IS THE EVENT, NOT THE VALUE.

    A content-derived key that collapses on VALUE cannot distinguish a REPLAY
    from a CORRECTION: the two are identical in value and differ only in
    context. So `chose_not_to_act` -> `was_away` -> `chose_not_to_act` reused the
    FIRST row's key, the third answer was discarded as a replay, and the
    governing row stayed on the flattering intermediate `was_away`. That is the
    instrument editing its subject's testimony in his favour, which this ledger
    may never do.

    THE GOVERNING ANSWER IS HIS LAST, NEVER HIS LAST DISTINCT. A correction back
    to a prior value is a new operator act at a new time and MUST produce a new
    row in an append-only ledger.

    PRE-FIX / POST-FIX ARITHMETIC: pre-fix the third POST returns the FIRST
    row's `intent_id` and the table holds 2 rows with `was_away` governing;
    post-fix it returns a NEW id, the table holds 3, and `chose_not_to_act`
    governs. The test distinguishes on all three.
    """
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.latches.classification import governing_intent

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = _attest(client, cid, "chose_not_to_act", "")
        assert first.status_code == 200
        id_a = _intents(cfg)[0][0]
        second = _attest(client, cid, "was_away", str(id_a))
        assert second.status_code == 200
        id_b = _intents(cfg)[1][0]
        assert id_b != id_a
        third = _attest(client, cid, "chose_not_to_act", str(id_b))
        assert third.status_code == 200
    rows = _intents(cfg)
    assert len(rows) == 3, (
        "a correction back to a prior VALUE is a new operator ACT; collapsing "
        "it onto the first row discards his actual final answer")
    conn = connect(cfg.paths.db_path)
    try:
        intents = list_intents_for_latch(conn, candidate_id=cid)
    finally:
        conn.close()
    assert governing_intent(intents, "attest").attested_disposition == (
        "chose_not_to_act")


def test_a_double_click_on_that_third_submission_STILL_collapses(
        seeded_db, frozen_clocks):
    """The mechanism keys on the SUBMISSION IN CONTEXT, not on the clock and not
    on a nonce: both clicks of a double-click carry the SAME rendered prior, so
    they still produce ONE row. Without this the A->B->A fix would have bought
    correction-fidelity at the cost of the double-click property."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        _attest(client, cid, "chose_not_to_act", "")
        id_a = _intents(cfg)[0][0]
        _attest(client, cid, "was_away", str(id_a))
        id_b = _intents(cfg)[1][0]
        first = _attest(client, cid, "chose_not_to_act", str(id_b))
        second = _attest(client, cid, "chose_not_to_act", str(id_b))
    assert first.status_code == second.status_code == 200
    rows = _intents(cfg)
    assert len(rows) == 3
    assert f"intent {rows[2][0]}" in first.text
    assert f"intent {rows[2][0]}" in second.text
    assert "already recorded" in second.text, (
        "the second click is a REPLAY of the same row, not a second answer")


def test_a_non_canonical_prior_spelling_is_REFUSED_not_silently_split(
        seeded_db, frozen_clocks):
    """The prior is KEY MATERIAL, so two spellings of one id would key as two
    rows -- the same hazard the canonical-session guard closes one field over.
    It is a shape rejection naming the field, never a silent normalisation."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = _attest(client, cid, "was_away", "007")
        assert r.status_code == 400
        assert "prior_intent_id" in r.text
        assert _attest(client, cid, "was_away", "-1").status_code == 400
        assert _attest(client, cid, "was_away", "abc").status_code == 400
    assert _intents(cfg) == []


def test_the_rendered_forms_CARRY_the_prior_intent_id(seeded_db, frozen_clocks):
    """The anchor has to be RENDERED or the mechanism is inert -- exactly the
    class of defect this dispatch was sent to close on the validity path. The
    prepared-order form emits it OUTSIDE the manifest-generated hidden anchor,
    so it never enters `anchor_digest` and the section A.4 manifest assertions
    are untouched."""
    import re
    pattern = re.compile(r'name="prior_intent_id"\s+value="([^"]*)"')
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        empty = pattern.findall(client.get("/latches").text)
        assert empty and set(empty) == {""}, (
            "a latch with NO ledger rows renders the anchor EMPTY, which is a "
            "distinct key component from any row id")
        _attest(client, cid, "was_away", "")
        first_id = _intents(cfg)[0][0]
        rendered = pattern.findall(client.get("/latches").text)
    assert rendered and set(rendered) == {str(first_id)}, (
        "the form must carry the row that GOVERNED the latch when it rendered")


# --- the validity branch ---------------------------------------------------
def _snapshot(*, branch="absence", attributable=0, exact=0, digest=None,
              ts=None, session=ANCHOR, indeterminate=False):
    return json.dumps({
        "broker_snapshot_ts": ts or "2026-07-25T11:58:00",
        "broker_snapshot_branch": branch,
        "broker_snapshot_digest": digest or ("a" * 64),
        "broker_snapshot_session": session,
        "attributable_order_count": attributable,
        "exact_framework_match_count": exact,
        "indeterminate": indeterminate,
    }, sort_keys=True)


def _place(client, cfg, cid):
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    assert client.post(
        "/latches/intent", headers=_HX, data=form).status_code == 200
    return _intents(cfg)[0][0]


def test_the_snapshot_envelope_key_set_is_the_ROSTER_and_nothing_else(
        seeded_db, frozen_clocks):
    """The fragment emits ONE hidden field whose key set EQUALS what
    `validity_detail` requires. Drift between the two makes the audit row
    UNWRITABLE, and the count is never stated anywhere -- an earlier round added
    a key to the CHECK while three other sites still said 'six'."""
    assert set(json.loads(_snapshot())) == set(LATCH_BROKER_SNAPSHOT_KEYS)


def test_a_validity_answer_records_the_observed_order_against_its_parent(
        seeded_db, frozen_clocks):
    """THE ARC'S OWN WORKED EXAMPLE. The framework said LIMIT 18.89 / 9 sh; the
    order actually resting is LIMIT 18.89 / 10 sh. That divergence carries
    `accepted_by_broker`, so it ENTERS the agreement DENOMINATOR while FAILING
    the numerator -- an `unknown` outcome would leave FTRE visible as a delta
    yet excluded from the very metric it exists to feed."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "accepted_by_broker",
            "actual_order_type": "LIMIT", "actual_duration": "GTC",
            "actual_limit_price": "18.89", "actual_quantity": "10",
            "actual_broker_order_id": "1001",
            "broker_snapshot_json": _snapshot(branch="presence", attributable=1),
        })
    assert r.status_code == 200, r.text
    rows = _intents(cfg)
    assert len(rows) == 2
    validity = rows[1]
    assert validity[1] == "validity"
    assert validity[8] == "accepted_by_broker"
    assert validity[9] == 10                    # the OBSERVED quantity
    assert validity[11] == place_id             # the PARENT link, not the latch


def test_GTC_and_GOOD_TILL_CANCEL_collapse_to_ONE_row(seeded_db, frozen_clocks):
    """Brokers render GTC where the framework stores GOOD_TILL_CANCEL. Comparing
    them raw would report a DURATION MISMATCH on a semantically identical order
    -- a false divergence in the one metric the ledger exists to compute -- and
    would write a duplicate row on a plain reload."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        base = {
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "accepted_by_broker",
            "actual_order_type": "LIMIT", "actual_limit_price": "18.89",
            "actual_quantity": "10", "actual_broker_order_id": "1001",
            "broker_snapshot_json": _snapshot(branch="presence", attributable=1),
        }
        client.post("/latches/intent", headers=_HX,
                    data=base | {"actual_duration": "GTC"})
        client.post("/latches/intent", headers=_HX,
                    data=base | {"actual_duration": "GOOD_TILL_CANCEL"})
    assert len(_intents(cfg)) == 2      # the place + ONE validity row


def test_two_DIFFERENT_answers_about_one_parent_write_TWO_rows(
        seeded_db, frozen_clocks):
    """The discrimination that must SURVIVE the kind-scoping. Without it the
    replay collapse would pass trivially against a key that had stopped
    discriminating at all, and the second answer would be silently lost."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        base = {
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "broker_snapshot_json": _snapshot(),
        }
        client.post("/latches/intent", headers=_HX,
                    data=base | {"validity_outcome": "rejected_by_broker"})
        client.post("/latches/intent", headers=_HX,
                    data=base | {"validity_outcome": "not_submitted"})
    assert len(_intents(cfg)) == 3


def test_a_validity_row_stores_the_PARENTS_mandate_session_not_the_anchor(
        seeded_db, monkeypatch):
    """SERVER-COPIED from the parent. A validity row answers for THAT order, and
    the aged prompt is the NORMAL case, so an anchor-derived value would file a
    July mandate under August -- and that is also what makes the monthly
    report's 'month N report, month N-1 mandate' case TRUE rather than merely
    asserted."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        later = datetime(2026, 8, 4, 12, 0)
        monkeypatch.setattr(route_mod, "_now", lambda: later)
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": "2026-08-05", "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": _snapshot(
                ts="2026-08-04T11:58:00", session="2026-08-05"),
        })
    assert r.status_code == 200, r.text
    validity = _intents(cfg)[1]
    assert validity[2] == ANCHOR                    # the PARENT's mandate session
    assert validity[3].startswith("2026-08-04")     # ...and TODAY's recorded_ts


def test_a_stale_broker_snapshot_is_409d_with_ZERO_rows_written(
        seeded_db, frozen_clocks):
    """The gate bounds the realistic failure -- an HONEST answer about a stale
    view. It does not defend against a forged local POST, and V1 does not
    pretend to."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        before = len(_intents(cfg))
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": _snapshot(ts="2026-07-25T09:00:00"),
        })
    assert r.status_code == 409
    assert len(_intents(cfg)) == before


def test_a_snapshot_from_a_PRIOR_action_session_is_409d(seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": _snapshot(session="2026-07-24"),
        })
    assert r.status_code == 409


def test_an_unavailable_book_may_NOT_answer_a_validity_prompt(
        seeded_db, frozen_clocks):
    """An UNKNOWN order book renders NO validity prompt in EITHER direction, so
    a persisted row whose own snapshot says the book was unavailable would be
    asserting an execution outcome it had no evidence for -- forever, on an
    append-only ledger. The render vocabulary is three-valued; the ANSWER
    vocabulary is two."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": _snapshot(branch="unavailable"),
        })
    assert r.status_code == 400
    assert "broker_snapshot_json" in r.text


def test_a_validity_row_WITHOUT_the_snapshot_envelope_is_REJECTED(
        seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted"})
    assert r.status_code == 400
    assert "broker_snapshot_json" in r.text


def test_an_envelope_carrying_an_EXTRA_key_is_rejected(seeded_db, frozen_clocks):
    """EXACTLY the roster, not AT LEAST it. `actual_digest` covers only the
    digest, so two envelopes differing ONLY by extra content would share an
    idempotency key -- the second replayed and its extra content silently
    dropped instead of rejected."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    envelope = json.loads(_snapshot())
    envelope["surprise"] = 1
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": json.dumps(envelope)})
    assert r.status_code == 400
    assert "broker_snapshot_json" in r.text


def test_a_validity_answer_about_ANOTHER_latchs_place_intent_is_rejected(
        seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid + 5000),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": _snapshot()})
    assert r.status_code == 400


# --- the LOG-ONLY guarantee, at this endpoint -----------------------------
@pytest.mark.parametrize("kind", ["place", "decline", "cancel", "attest"])
def test_no_schwab_row_is_written_on_any_intent_branch(
        seeded_db, frozen_clocks, kind):
    """The LEDGER leg of the no-write pin: `schwab_api_calls` is UNCHANGED
    across the POST. Task 10 adds the transport-level deny-by-default net that
    catches a renamed mutator regardless of what it is called."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": kind}
    if kind == "decline":
        form["decline_reason"] = "not today"
    if kind == "cancel":
        form["actual_broker_order_id"] = "1001"
    if kind == "attest":
        form["attested_disposition"] = "chose_not_to_act"
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        before = _schwab_calls(cfg)
        r = client.post("/latches/intent", headers=_HX, data=form)
        assert r.status_code == 200, (kind, r.text)
        assert _schwab_calls(cfg) == before


def test_the_intent_path_never_borrows_the_schwab_client(
        seeded_db, frozen_clocks, monkeypatch):
    """THE SEAM assertion: the intent flow does not borrow the client AT ALL, so
    there is no path from here to a broker write even in principle."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        holder = getattr(app.state, "schwab_client_holder", None)
        borrows = {"n": 0}
        if holder is not None and hasattr(holder, "borrow"):
            real = holder.borrow

            def _counted(*a, **k):
                borrows["n"] += 1
                return real(*a, **k)

            monkeypatch.setattr(holder, "borrow", _counted)
        assert client.post(
            "/latches/intent", headers=_HX, data=form).status_code == 200
        assert borrows["n"] == 0


# --- Codex exec R1 MAJOR 3: the key uses the DECLARED price encoding -------
def test_equivalent_price_spellings_produce_ONE_row(seeded_db, frozen_clocks):
    """CODEX EXEC R1 MAJOR 3. `18.9`, `18.90` and `18.900` are the SAME price at
    the declared display precision, so they must share an idempotency key. A key
    built by stringifying a float reasons at Python's `repr` precision instead
    of at the contract's, which is the price-precision-parity gotcha arriving
    through the KEY rather than through a comparison -- and it produces either a
    duplicate ledger row or a silent collapse, depending on which spelling
    arrives first."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        base = {
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "accepted_by_broker",
            "actual_order_type": "LIMIT", "actual_duration": "GTC",
            "actual_quantity": "10", "actual_broker_order_id": "1001",
            "broker_snapshot_json": _snapshot(branch="presence", attributable=1),
        }
        for spelling in ("18.9", "18.90", "18.900"):
            r = client.post("/latches/intent", headers=_HX,
                            data=base | {"actual_limit_price": spelling})
            assert r.status_code == 200, (spelling, r.text)
    assert len(_intents(cfg)) == 2      # the place + ONE validity row


def test_a_one_cent_different_price_produces_a_DIFFERENT_row(
        seeded_db, frozen_clocks):
    """The PAIRED discriminator: without it the collapse above is satisfied by a
    key that has stopped discriminating on price at all, and a genuinely
    different observed order would be silently lost as a replay."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        base = {
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "accepted_by_broker",
            "actual_order_type": "LIMIT", "actual_duration": "GTC",
            "actual_quantity": "10", "actual_broker_order_id": "1001",
            "broker_snapshot_json": _snapshot(branch="presence", attributable=1),
        }
        for spelling in ("18.89", "18.90"):
            assert client.post(
                "/latches/intent", headers=_HX,
                data=base | {"actual_limit_price": spelling}).status_code == 200
    assert len(_intents(cfg)) == 3      # the place + TWO distinct validity rows


# --- the key's field set is SCOPED BY KIND (Codex exec R2 MAJOR 2) ---------
def test_every_intent_kind_has_an_answer_field_roster(seeded_db):
    """The roster is indexed by kind with NO default, so a sixth kind added to
    the CHECK enum without a roster entry would `KeyError` the endpoint rather
    than key on the wrong fields. The coupling is pinned rather than left to a
    reader noticing, which is the #11 one-commit mirror discipline applied to a
    Python-side roster."""
    from swing.latches.constants import LATCH_INTENT_KINDS
    from swing.web.routes.latches import _ANSWER_FIELDS_BY_KIND
    assert set(_ANSWER_FIELDS_BY_KIND) == set(LATCH_INTENT_KINDS)


def test_a_field_the_kind_DISCARDS_does_not_fork_the_ledger_row(
        seeded_db, frozen_clocks):
    """CODEX EXEC R2 MAJOR 2. `place` persists no actual-side field -- the
    schema makes them unwritable on it -- so a stray `actual_duration` on a
    place POST is thrown away by the row. A key that digested it anyway keyed
    two IDENTICAL decisions differently, and an append-only ledger would carry
    the same decision twice: a duplicate the parity denominator would then
    count twice."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = client.post("/latches/intent", headers=_HX, data=form)
        second = client.post(
            "/latches/intent", headers=_HX,
            data=form | {"actual_duration": "DAY"})
    assert first.status_code == second.status_code == 200
    rows = _intents(cfg)
    assert len(rows) == 1
    assert "already recorded" in second.text
    assert rows[0][1] == "place"


def test_the_kind_scoping_does_NOT_stop_the_key_discriminating_its_OWN_fields(
        seeded_db, frozen_clocks):
    """The pair to the collapse above. Without it, scoping the roster would be
    satisfied by a key that had stopped reading answers at all -- and a SECOND
    decline reason would be silently lost. `decline_reason` IS in `decline`'s
    roster, so two different reasons must produce two different KEYS.

    ASSERTED ON THE KEY, NOT THROUGH TWO SEQUENTIAL POSTS, and the reason is a
    LIFECYCLE change rather than a weakening of this test. Item 3a makes a
    decline TERMINATE the mandate (RD OQ-4), so the second POST is now refused
    by the route's liveness re-derivation -- see
    `test_a_DECLINED_latch_REFUSES_a_further_decision_and_that_cost_is_pinned`,
    which pins that refusal and flags the missing correction affordance. The
    PROPERTY this test exists to protect is a property of the KEY, so it is
    asserted there, where it remains exactly as discriminating: a key that
    stopped digesting `decline_reason` collapses the two.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    base = _anchor_form(cfg, cid) | {"intent_kind": "decline"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = client.post("/latches/intent", headers=_HX,
                            data=base | {"decline_reason": "already_positioned"})
    assert first.status_code == 200
    assert [r[7] for r in _intents(cfg)] == ["already_positioned"]

    # `decline_reason` is an ANSWER field, so it enters the key through
    # `_actual_digest` -- NOT through the framework anchor digest, which carries
    # the hidden order block. (An earlier draft of this substitution reached for
    # `build_anchor_digest` and collapsed to ONE digest, which is the right
    # answer for that function and the wrong function for this property.)
    from swing.web.routes.latches import _actual_digest
    digests = {
        reason: _actual_digest(
            "decline", {"decline_reason": reason},
            parent_id=None, snapshot_digest=None)
        for reason in ("already_positioned", "risk_budget")
    }
    assert len(set(digests.values())) == 2, (
        "two different decline reasons must not collapse to one key")
    assert _actual_digest(
        "decline", {"decline_reason": "already_positioned"},
        parent_id=None, snapshot_digest=None) == digests["already_positioned"], (
        "and the same reason must reproduce its digest, or a plain refresh "
        "would duplicate the row instead of collapsing")


# --- the validity branch DEGRADES rather than 500s (R2 MAJOR 3) ------------
def test_an_offset_aware_snapshot_ts_is_REFUSED_not_a_500(
        seeded_db, frozen_clocks):
    """CODEX EXEC R2 MAJOR 3. `datetime.fromisoformat` happily accepts an
    OFFSET-AWARE stamp, and subtracting it from the naive server clock raises
    `TypeError` -- outside a guard that wrapped only the two parses. The render
    emits a naive stamp, so an aware one did not come from our own fragment.
    Any failure to ESTABLISH freshness is NOT-FRESH: the gate fails CLOSED,
    because an unverifiable snapshot is the thing it exists to refuse."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        before = len(_intents(cfg))
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": _snapshot(ts="2026-07-25T11:58:00+00:00"),
        })
    assert r.status_code == 409
    assert len(_intents(cfg)) == before


def test_a_model_contract_violation_is_a_400_not_a_500(
        seeded_db, frozen_clocks):
    """The other half of R2 MAJOR 3. `LatchOrderIntent.__post_init__` mirrors
    the migration's cross-column shape rules, and an `accepted_by_broker`
    validity row REQUIRES a complete actual side -- so this payload is
    refusable, not exceptional. Constructing the model OUTSIDE the guard turned
    it into an unhandled 500 with no visible reason; the dataclass validator and
    the schema CHECK are the SAME contract and must degrade the same way."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        before = len(_intents(cfg))
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "accepted_by_broker",
            "actual_order_type": "LIMIT", "actual_duration": "GTC",
            "actual_limit_price": "18.89", "actual_quantity": "10",
            # ...and NO actual_broker_order_id, which an accepted row requires.
            "broker_snapshot_json": _snapshot(branch="presence", attributable=1),
        })
    assert r.status_code == 400
    assert "ledger contract" in r.text
    assert len(_intents(cfg)) == before


# --- the session spelling must ROUND-TRIP (Codex exec R4 MAJOR 1) ----------
def test_an_ISO_WEEK_session_spelling_is_REFUSED(seeded_db, frozen_clocks):
    """CODEX EXEC R4 MAJOR 1. `date.fromisoformat` accepts the ISO WEEK form,
    and `2026-W31-1` both parses to 2026-07-27 AND measures exactly ten
    characters -- so the length check does not catch it. The RAW spelling feeds
    the idempotency key while the STORED session is canonicalised, and this
    field is deliberately exempt from the anchor comparison, so the canonical
    form and its week-date equivalent are ONE decision that keys as TWO. That is
    hazard (a) defeated by a spelling."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    assert date.fromisoformat("2026-W31-1").isoformat() == ANCHOR
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        good = client.post("/latches/intent", headers=_HX, data=form)
        weird = client.post(
            "/latches/intent", headers=_HX,
            data=form | {"view_session_date": "2026-W31-1"})
    assert good.status_code == 200
    assert weird.status_code == 400
    assert "view_session_date" in weird.text
    assert len(_intents(cfg)) == 1


def test_an_infinite_observed_price_is_REFUSED(seeded_db, frozen_clocks):
    """CODEX EXEC R4 MAJOR 4. `float('inf')` parses, satisfies `> 0`, survives
    `round(_, 2)`, and satisfies the model's and the schema's `> 0` CHECKs too
    -- so an infinite OBSERVED price would persist as authoritative broker
    evidence and the agreement report would compute a fabricated divergence off
    it. `> 0` is not a finiteness test."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        before = len(_intents(cfg))
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "accepted_by_broker",
            "actual_order_type": "LIMIT", "actual_duration": "GTC",
            "actual_limit_price": "inf", "actual_quantity": "10",
            "actual_broker_order_id": "1001",
            "broker_snapshot_json": _snapshot(branch="presence", attributable=1),
        })
    assert r.status_code == 400
    assert "finite" in r.text
    assert len(_intents(cfg)) == before


def test_a_non_string_snapshot_branch_is_REFUSED_not_a_500(
        seeded_db, frozen_clocks):
    """CODEX EXEC R5. The roster check validates KEYS, so a roster-conformant
    envelope carrying a LIST for `broker_snapshot_branch` reaches the membership
    test, and `[] in frozenset(...)` raises `TypeError: unhashable type` outside
    the guard -- a reachable payload 500ing instead of being named and refused.
    Membership-testing a client-controlled value requires first knowing it is
    hashable."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    envelope = json.loads(_snapshot())
    envelope["broker_snapshot_branch"] = []
    with TestClient(app) as client:
        place_id = _place(client, cfg, cid)
        before = len(_intents(cfg))
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(place_id),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": json.dumps(envelope, sort_keys=True),
        })
    assert r.status_code == 400
    assert "broker_snapshot_branch" in r.text
    assert len(_intents(cfg)) == before


# --- Codex exec R6: the correction paths must be REACHABLE, not just handled ---
def test_the_ATTEST_form_survives_the_first_attestation_as_a_CORRECTION_control(
        seeded_db, frozen_clocks, monkeypatch):
    """CODEX EXEC R6 MAJOR, and it is this dispatch's signature class turned on
    its own ruling-3 fix: the attestation form rides on `discipline_lapse`, so
    the instant an attestation is recorded the disposition MOVES and the only
    browser control DISAPPEARS. `was_away` could then never be corrected to
    `chose_not_to_act` -- and those two land in DIFFERENT R buckets, so the
    A -> B -> A capability the handler now has was one the operator could not use.

    It renders as a CORRECTION rather than as the prompt again: a recurring
    question on a settled cell is what trains the dismissal reflex.
    """
    import re
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        _attest(client, cid, "was_away", "")
        html = client.get("/latches").text
    assert "latch-attest-correction" in html
    assert "Recorded:" in html and "was_away" in html
    assert re.search(r'name="attested_disposition" value="chose_not_to_act"',
                     html), "every attestation option stays offered"
    assert re.search(r'name="prior_intent_id"\s+value="1"', html), (
        "the correction carries the row that now governs, which is what keys "
        "it apart from the answer it corrects")


def test_the_ATTEST_form_can_capture_the_broker_order_id_for_exact_linkage(
        seeded_db, frozen_clocks):
    """CODEX EXEC R6 MAJOR. The observed-order query was widened to include
    `attest` rows -- `acted_manually` is the ONE path that exists for an order
    the framework did not prepare -- but the attestation UI emitted only the
    disposition, so the browser could never supply one and the widening reached
    nothing. Section G.4's linkage is EXACT only where a broker order id was
    CAPTURED; without the field it can only ever be inferred from params.

    Optional, deliberately: refusing the attestation for want of an id he may not
    have to hand would lose the attestation, which is worth more.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "attest", "attested_disposition": "acted_manually",
            "actual_broker_order_id": "778899", "prior_intent_id": ""})
        # The lapse PROMPT and the correction CONTROL are ONE form in the
        # template, so asserting the field on the reachable branch pins it for
        # both -- the lapse branch needs a terminal latch plus an actionable view
        # row and is covered by the classification suite.
        rendered = client.get("/latches").text
    assert r.status_code == 200, r.text
    assert 'name="actual_broker_order_id"' in rendered
    (row,) = _intents(cfg)
    assert (row[1], row[10]) == ("attest", "778899")


def test_a_STALE_TAB_replay_of_a_SUPERSEDED_answer_is_REFUSED_not_returned(
        seeded_db, frozen_clocks):
    """CODEX EXEC R6 MAJOR. Two tabs render the same prior; tab one records A
    then corrects to B; the stale tab later submits A. Its key equals the FIRST
    A, so an unconditional replay returned that OLD row and left the flattering B
    governing -- a genuine later correction silently discarded, which is the one
    direction ruling 3 forbids.

    REFUSED rather than silently re-keyed: re-deriving the key against the
    current governor would make the second click of a double-click on THAT
    submission key differently again and write a duplicate, trading the collapse
    property for the correction property. A 409 loses NO testimony -- he reloads
    and answers against what actually governs.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        _attest(client, cid, "chose_not_to_act", "")      # A, from both tabs
        id_a = _intents(cfg)[0][0]
        _attest(client, cid, "was_away", str(id_a))       # B, from tab one
        stale = _attest(client, cid, "chose_not_to_act", "")   # the stale tab
    assert stale.status_code == 409
    assert "Reload" in stale.text
    assert len(_intents(cfg)) == 2, "the refusal writes NOTHING"


def test_a_double_click_is_STILL_a_replay_because_its_row_IS_the_governor(
        seeded_db, frozen_clocks):
    """The pair for the test above -- without it, "refuse a superseded key" is
    satisfied by an implementation that has stopped collapsing double-clicks at
    all, which is the property the whole idempotency key exists for."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = _attest(client, cid, "was_away", "")
        second = _attest(client, cid, "was_away", "")
    assert first.status_code == second.status_code == 200
    assert len(_intents(cfg)) == 1
    assert "already recorded" in second.text


def test_a_UNICODE_DIGIT_prior_id_is_a_named_400_and_never_a_500(
        seeded_db, frozen_clocks):
    """CODEX EXEC R7 MAJOR, and the THIRD instance of one class: never assume a
    client-controlled string is the shape a predicate implies.

    `str.isdigit()` is TRUE for `\u00b2`, and `int('\u00b2')` then RAISES -- outside the
    rejection path, so a reachable payload 500s instead of being named. A long
    enough ASCII digit string trips Python's own integer-conversion limit for the
    same reason. Both are now refused BY NAME.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        for bad in ("\u00b2", "\u0660\u0661", "9" * 5000):
            r = _attest(client, cid, "was_away", bad)
            assert r.status_code == 400, bad
            assert "prior_intent_id" in r.text
    assert _intents(cfg) == []


def test_EVERY_integer_field_refuses_a_unicode_digit_by_name(
        seeded_db, frozen_clocks):
    """CODEX EXEC R8 MAJOR -- THE CLASS, NOT THE INSTANCE. R7 fixed the
    `str.isdigit()`-then-`int()` hole on `prior_intent_id` ALONE, and R8 found
    `candidate_id`, `validated_place_intent_id` and `actual_quantity` still
    holding it. Every integer field now routes through ONE guarded parser, so a
    new integer field cannot reintroduce it by being written the obvious way."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": "\u00b2",
            "intent_kind": "attest", "attested_disposition": "was_away"})
        assert r.status_code == 400 and "candidate_id" in r.text
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity", "validated_place_intent_id": "\u0661",
            "validity_outcome": "unknown"})
        assert r.status_code == 400 and "validated_place_intent_id" in r.text
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity", "validated_place_intent_id": "1",
            "validity_outcome": "accepted_by_broker",
            "actual_quantity": "9" * 5000})
        assert r.status_code == 400 and "actual_quantity" in r.text
    assert _intents(cfg) == []


def test_an_UNREADABLE_ledger_REFUSES_the_replay_rather_than_waving_it_through(
        seeded_db, frozen_clocks, monkeypatch):
    """CODEX EXEC R8 MAJOR. The superseded-key safeguard FAILED OPEN: a read
    failure returned `None` and the caller replayed the old row as though it
    still governed, restoring the flattering lost-correction defect the
    safeguard exists to close. A guard that cannot establish its fact must
    REFUSE, not wave through -- and `None` legitimately means "no rows yet", so
    the failure needed its own signal rather than sharing that one."""
    import sqlite3

    import swing.web.routes.latches as route_mod

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        _attest(client, cid, "was_away", "")
        monkeypatch.setattr(
            route_mod, "_governing_intent_id",
            lambda *a, **k: (_ for _ in ()).throw(
                route_mod._GovernanceUnknownError()))
        r = _attest(client, cid, "was_away", "")
    assert r.status_code == 409
    assert "could not be read" in r.text
    assert len(_intents(cfg)) == 1, "the refusal writes NOTHING"


def test_a_RELOAD_then_the_SAME_answer_is_a_REPLAY_not_a_second_row(
        seeded_db, frozen_clocks):
    """CODEX EXEC R9 MAJOR. The ruling-3 context anchor made the key depend on
    the RENDER, which broke the property the content-derived key exists for: a
    refresh followed by an identical resubmit collapses. After recording A, a
    reload renders `prior=A`, so the same answer keyed differently and wrote a
    duplicate.

    BOTH properties hold now, because they are about different things: an answer
    IDENTICAL TO THE CURRENT GOVERNOR is a repeat and collapses; an answer that
    DIFFERS from it is a correction and writes. The A -> B -> A test above is the
    other half of this pair -- neither passes against an implementation that
    satisfies only the other.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = _attest(client, cid, "was_away", "")
        id_a = _intents(cfg)[0][0]
        # The RELOAD: the form now renders carrying the row it just wrote.
        again = _attest(client, cid, "was_away", str(id_a))
    assert first.status_code == again.status_code == 200
    assert len(_intents(cfg)) == 1, (
        "the same answer twice is ONE event, however many times the page was "
        "rendered in between")
    assert "already recorded" in again.text


def test_an_integer_ABOVE_sqlites_maximum_is_a_named_400_not_an_OverflowError(
        seeded_db, frozen_clocks):
    """CODEX EXEC R10 MAJOR. The DIGIT bound is not the VALUE bound:
    `9999999999999999999` is nineteen digits and still exceeds SQLite's signed
    64-bit maximum, so BINDING it raises an uncaught `OverflowError` -- a
    client-reachable 500 through the very parser added to stop client-reachable
    500s."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": "9" * 19,
            "intent_kind": "attest", "attested_disposition": "was_away"})
        assert r.status_code == 400 and "candidate_id" in r.text
        assert _attest(client, cid, "was_away", "9" * 19).status_code == 400
    assert _intents(cfg) == []


def test_only_an_ACTED_MANUALLY_attestation_may_carry_a_broker_order_id(
        seeded_db, frozen_clocks):
    """CODEX EXEC R10 MAJOR. A row saying `was_away` while carrying an observed
    broker order asserts two incompatible things at once: the classifier counts
    the attestation that keeps the fire OUT of the discipline signal, and the
    origin query simultaneously reports the order he says he did not place. An
    outcome and its evidence must not be able to disagree -- the same rule the
    validity row's observed side already obeys."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        for disposition in ("was_away", "chose_not_to_act"):
            r = client.post("/latches/intent", headers=_HX, data={
                "view_session_date": ANCHOR, "candidate_id": str(cid),
                "intent_kind": "attest",
                "attested_disposition": disposition,
                "actual_broker_order_id": "4242"})
            assert r.status_code == 400, disposition
            assert "actual_broker_order_id" in r.text
        ok = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "attest", "attested_disposition": "acted_manually",
            "actual_broker_order_id": "4242"})
    assert ok.status_code == 200, ok.text
    assert [(r[1], r[10]) for r in _intents(cfg)] == [("attest", "4242")]


def test_a_MALFORMED_numeric_anchor_is_a_named_400_not_a_500(
        seeded_db, frozen_clocks):
    """CODEX-AUTO-REVIEW MINOR. The hidden anchor is ENCODED, and encoding
    PARSES: `framework_quantity=abc` reaches `int()` inside
    `encode_derivation_value`, so a malformed anchor 500'd instead of being
    named -- the shape-validation step skipped exactly the fields the manifest
    generates."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        form = _anchor_form(cfg, cid) | {
            "intent_kind": "place", "framework_quantity": "abc"}
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 400
    assert "anchor" in r.text
    assert _intents(cfg) == []


def test_the_BEACON_id_parser_refuses_a_unicode_digit_by_name(
        seeded_db, frozen_clocks):
    """CODEX-AUTO-REVIEW MINOR -- the OTHER door into the same integer keyspace.
    `POST /latches/view` still held the bare `isdigit()`-then-`int()` hole after
    the intent route was fixed, so the same payload 500'd there. Fixing one door
    and leaving the other is how the next reader concludes the guard exists."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        for bad in ("\u00b2", "9" * 5000):
            r = client.post("/latches/view", headers=_HX, data={
                "view_session_date": ANCHOR,
                "actionable_candidate_ids": bad,
                "withheld_candidate_ids": ""})
            assert r.status_code == 400, bad
            assert "actionable_candidate_ids" in r.text


def test_a_RECONFIRMATION_candidate_id_is_never_what_gets_persisted(
        seeded_db, frozen_clocks):
    """Codex R2 CRITICAL 2's reachability, pinned DISCRIMINATINGLY (R3 MAJOR 6).

    The round-2 form submitted the opening-fire id and then asserted that same id
    came back, which an implementation echoing the submitted `candidate_id`
    passes unchanged -- it never offered the distinguishing input. This one
    builds a latch that HAS a re-confirmation and POSTs against the
    RE-CONFIRMATION id.

    WHY IT MATTERS: several route-side reads are keyed on a single
    `candidate_id` -- the replay guard, the prior-intent anchor, the unattached
    audit -- and they are correct exactly while every persisted intent carries
    the latch's OPENING FIRE id. That is a CONSTRAINED WRITER, not a schema
    CHECK (`latch_order_intents` has an FK to `candidates` and nothing
    narrower), which is why it needs a test rather than a comment.

    Either outcome is a pass: the route REFUSES the re-confirmation id (it does
    not identify a latch the panel renders), or it persists the FIRE id. What
    must never happen is a row carrying the re-confirmation id -- and if this
    ever fails, the fire-id-keyed route reads must widen to the candidate family
    (the lifecycle resolver and both classifiers already read the family and
    would be unaffected).
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        # a SECOND aplus row on the SAME action session -> clause (i) collapses
        # it into the first latch as a RE-CONFIRMATION.
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(122, '2026-07-17T18:30:05', '2026-07-17', '2026-07-20', 1, 1, 0, "
            "0, 0, 0)")
        reconf = int(conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(122, 'FTRE', 'aplus', 17.76, 18.34, 14.88, 'universe')"
        ).lastrowid)
    conn.close()

    conn = connect(cfg.paths.db_path)
    try:
        latch = next(
            lat for lat in build_latch_derivation(conn, cfg).latches
            if lat.identity.candidate_id == cid)
    finally:
        conn.close()
    assert reconf in latch.candidate_set, "the fixture must build a re-confirmation"
    assert latch.identity.candidate_id == cid != reconf

    form = _anchor_form(cfg, cid) | {
        "intent_kind": "place", "candidate_id": str(reconf)}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        client.post("/latches/intent", headers=_HX, data=form)

    conn = connect(cfg.paths.db_path)
    try:
        persisted = {
            int(r[0]) for r in conn.execute(
                "SELECT candidate_id FROM latch_order_intents").fetchall()}
    finally:
        conn.close()
    assert reconf not in persisted, (
        "a re-confirmation candidate id reached latch_order_intents -- the "
        "fire-id-keyed route reads (replay guard, prior anchor, unattached "
        "audit) must now widen to the candidate family")


def test_a_DECLINED_latch_REFUSES_a_further_decision_and_that_cost_is_pinned(
        seeded_db, frozen_clocks):
    """The lifecycle change's operator-facing COST, asserted so it is a recorded
    decision rather than a surprise.

    A decline now TERMINATES the mandate (RD OQ-4), and the route's
    re-derivation admits LIVE latches only -- so the operator cannot correct a
    decline through this surface. The resolver handles `decline -> place`
    correctly; only the recording surface cannot produce the sequence.

    The correction affordance is a RENDER-plus-ROUTE change (the panel builds
    prepared-order blocks from LIVE latches alone, so a declined card shows no
    form at all) and is flagged to the wave item that owns the ruled principle:
    the affordance to record must not be gated on the alarm that detects. When
    it ships, this test flips to asserting 200 and a second row.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    base = _anchor_form(cfg, cid)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        declined = client.post(
            "/latches/intent", headers=_HX,
            data=base | {"intent_kind": "decline",
                         "decline_reason": "already_positioned"})
        second = client.post(
            "/latches/intent", headers=_HX, data=base | {"intent_kind": "place"})
    assert declined.status_code == 200, declined.text
    assert second.status_code == 400
    assert "live latch" in second.text
    assert [r[1] for r in _intents(cfg)] == ["decline"]

    conn = connect(cfg.paths.db_path)
    try:
        latch = next(
            lat for lat in build_latch_derivation(conn, cfg).latches
            if lat.identity.candidate_id == cid)
    finally:
        conn.close()
    assert latch.clear_reason == "declined"


# ---------------------------------------------------------------------------
# FLAG B -- A DECLINE'S EFFECTIVE SESSION IS SERVER-COMPUTED AT POST, AND
# BACKDATING IS IMPOSSIBLE BY CONSTRUCTION (RD, `docs/rd-state.md`).
#
# The defect is not cosmetic. `_resolve_decline` reads `action_session_date`
# DIRECTLY as the `declined` terminal's session and `_Terminal.order_key` is
# `(session, rank)`, so a backdated decline can PRE-EMPT a terminal dated
# between the render and the submit -- including a FILL. That is the
# orphaned-fill vector.
# ---------------------------------------------------------------------------
_S_PLUS_ONE_CLOCK = datetime(2026, 7, 27, 18, 0)   # -> action session 07-28


def test_a_DECLINE_with_a_STALE_anchor_is_REFUSED_and_writes_NOTHING(
        seeded_db, monkeypatch):
    """DISCRIMINATOR, computed under BOTH paths.

    THE OBVIOUS CONSTRUCTION IS VACUOUS AND IS REJECTED HERE RATHER THAN
    RE-DERIVED LATER: freeze the clock ON the anchor's own session and the
    stored session is that session PRE-fix (from the anchor) and POST-fix (from
    the clock) alike, proving nothing.

    The discriminating construction is the STALE-BUT-TOLERATED anchor: anchor
    S, clock S+1, one session behind, which `_classify_anchor` returns `ok` for
    today.

        |                          | pre-fix          | post-fix |
        | HTTP status              | 200              | 409      |
        | latch_order_intents rows | 1, dated S       | 0        |

    Both are asserted, so it cannot pass vacuously in either direction.

    THE PREPARED ORDER MUST BE *OFFERED* AT S OR THIS PROVES NOTHING. `decline`
    is a DECISION kind, so step 5 re-derives the block and 409s when it is
    WITHHELD -- and withheld is the default on today's substrate, so a careless
    fixture returns 409 + zero rows PRE-fix too, for an unrelated reason, and
    the table above collapses into agreement. `_anchor_form` asserts
    `prepared_order.offered` as an INLINE PREMISE, and `_seed` dates the close,
    the run and the corroborating archive bar at the derivation session the
    anchor S actually resolves to.

    THE LEDGER STARTS EMPTY, deliberately: with no rows neither replay gate can
    hit, so this measures the freshness gate and nothing else. The replay
    interaction is pinned separately below.
    """
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {
        "intent_kind": "decline", "decline_reason": "too extended"}
    assert form["view_session_date"] == ANCHOR
    assert _intents(cfg) == [], "the premise: the ledger starts EMPTY"

    monkeypatch.setattr(route_mod, "_now", lambda: _S_PLUS_ONE_CLOCK)
    monkeypatch.setattr(vm_mod, "_now", lambda: _S_PLUS_ONE_CLOCK)
    from swing.evaluation.dates import action_session_for_run, sessions_behind
    current = action_session_for_run(_S_PLUS_ONE_CLOCK)
    assert current.isoformat() == "2026-07-28", current
    assert sessions_behind(current, date(2026, 7, 27)) == 1, (
        "the premise: ONE session behind, which the anchor classifier "
        "TOLERATES today -- a 2-session gap would 409 for the old reason")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 409, r.text
    assert "stale" in r.text.lower()
    assert _intents(cfg) == []


def test_a_DECLINE_stores_a_SESSION_EQUAL_to_BOTH_the_clock_and_the_anchor(
        seeded_db, frozen_clocks):
    """INVARIANT, NOT A DISCRIMINATOR, and it is labelled so (Codex R4 MINOR).

    It was named "stores the SERVER session" and counted as flag B's other
    half. It is not: the strict gate makes `anchor == current`, so the stored
    value is identical whether it came from the form or from the clock, and the
    row is the same on the pre-fix and post-fix trees. Presenting it as evidence
    of the server-computed half would have been the vacuous-acceptance-test
    class in the arc that spends three sections warning about it.

    What it DOES pin is the EQUALITY the two halves produce together -- and that
    equality is load-bearing rather than decorative, because `build_idempotency
    _key` folds in the form's RAW session spelling while the row stores the
    server's. If they could differ, the key and the row would describe different
    sessions. The DISCRIMINATOR for flag B is the stale-anchor test above."""
    from swing.evaluation.dates import action_session_for_run
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {
        "intent_kind": "decline", "decline_reason": "gap risk"}
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 200, r.text
    (row,) = _intents(cfg)
    assert row[2] == action_session_for_run(NOW).isoformat() == ANCHOR, (
        "the stored session, the server clock's session and the form's anchor "
        "are ONE value -- which is exactly why this test cannot distinguish "
        "which of them it came from")


@pytest.mark.parametrize("kind,extra", [
    ("cancel", {"actual_broker_order_id": "4242"}),
    ("attest", {"attested_disposition": "chose_not_to_act"}),
])
def test_a_NON_DECLINE_KIND_with_a_STALE_anchor_is_STILL_ACCEPTED_today(
        seeded_db, monkeypatch, kind, extra):
    """COST MARKER -- EXPLICITLY NOT A DISCRIMINATOR and not acceptance
    evidence for anything. A current-anchor cancel stores the form anchor
    before and after this change, so that shape passes on both trees; this one
    has a real failing condition instead.

    RD ruled `decline` and ONLY `decline`: a session field is server-computed
    WHEREVER IT IS CONSUMED AS A DECISION OR ORDERING DATE, and `cancel` /
    `attest` sessions are provenance/display only (the ledger's time axis is
    `recorded_ts`), so flag B does not reach them. This test FAILS the moment
    anyone extends flag B to either kind, which is precisely the moment to go
    back to RD -- and it is PARAMETERISED over both, because an accidental
    extension to `attest` alone would otherwise ship with no failing test, on
    the kind whose prompt is DESIGNED to be answered long after the fact.

    EACH KIND CARRIES ITS REQUIRED FIELD or the test never reaches the session
    logic: step 2 rejects an `attest` with no disposition and a `cancel` with
    no broker order id, both BEFORE step 5. `chose_not_to_act` is chosen
    because `acted_manually` is the only disposition permitted to carry a
    broker order id, and this row carries none.
    """
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)
    cid = _seed(cfg)
    monkeypatch.setattr(route_mod, "_now", lambda: _S_PLUS_ONE_CLOCK)
    monkeypatch.setattr(vm_mod, "_now", lambda: _S_PLUS_ONE_CLOCK)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": kind} | extra)
    assert r.status_code == 200, r.text
    (row,) = _intents(cfg)
    assert row[1] == kind
    assert row[2] == ANCHOR, (
        "today's behaviour: the FORM's anchor, not the server session")


@pytest.mark.parametrize("kind,extra", [
    ("decline", {"decline_reason": "not today"}),
    ("place", {}),
])
def test_the_REPLAY_ORDERING_is_UNCHANGED_by_the_decline_freshness_gate(
        seeded_db, monkeypatch, kind, extra):
    """GUARD. It kills the one wrong implementation of flag B: moving the
    freshness gate AHEAD of the replay lookups.

    SELECT-first idempotency requires the terminal-state read to precede
    validation, and this route's own docstring argues the ordering explicitly.
    Move the gate and a double-click on a page that went stale between clicks
    FAILS instead of collapsing onto its existing row.

    `decline` IS THE LOAD-BEARING PARAMETER AND `place` IS THE COMPANION
    (Codex R1 MINOR). The new gate is decline-ONLY, so a `place`-only test
    stays green against exactly the implementation it claims to kill -- moving
    the DECLINE gate ahead of the replay lookups. `place` is kept beside it
    because it proves the ordering was not disturbed for the kind that has no
    gate at all."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)
    cid = _seed(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": kind} | extra
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = client.post("/latches/intent", headers=_HX, data=form)
        assert first.status_code == 200, first.text
        monkeypatch.setattr(route_mod, "_now", lambda: _S_PLUS_ONE_CLOCK)
        monkeypatch.setattr(vm_mod, "_now", lambda: _S_PLUS_ONE_CLOCK)
        replay = client.post("/latches/intent", headers=_HX, data=form)
    assert replay.status_code == 200, replay.text
    assert len(_intents(cfg)) == 1
