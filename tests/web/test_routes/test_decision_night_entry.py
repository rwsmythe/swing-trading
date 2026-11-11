"""D102 T2.2-2.3 -- the entry form names the decision night.

Tests 2b, 2c, 2d (every ladder rung, the label-changed gate, the forged
anchors, the window shift, the raced read), 2e, 2f, 2g, 2i and the GET/POST
halves of 2k. Seeded from trade 29's LIVE shape (`build_sg_case`, nights
192/193/194, all `watch`, the latest complete run eval 194) WITHOUT trade 29
itself, which would refuse the POST as a duplicate open position.

"CLEARED" on a refused decision anchor means the re-render carries the
SERVER's fresh offer and the default (newest) selection -- never the
submitted anchor string or the submitted choice.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot
from tests.trades._cohort_provenance_fixtures import (
    SG_BASELINE_LABEL,
    SG_FIRE_LABEL,
    build_sg_case,
)
from tests.web.conftest import full_phase7_entry_payload

NEWEST, FIRE, OLDER = 15980, 15901, 15811


def _patch_price_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=11.95, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _world(cfg, monkeypatch, **case) -> None:
    _patch_price_cache(monkeypatch)
    conn = connect(cfg.paths.db_path)
    try:
        build_sg_case(conn, with_trade=False, **case)
        conn.commit()
    finally:
        conn.close()


def _add_run(cfg, *, run_id: int, pr_id: int, sg_bucket: str | None,
             asof: str = "2026-11-06", action: str = "2026-11-09",
             run_ts: str = "2026-11-07T03:30:00") -> None:
    """A later COMPLETE run; ``sg_bucket=None`` holds no SG row (F6 edge)."""
    conn = connect(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, "
            "watch_count, skip_count, excluded_count, error_count) VALUES "
            "(?, ?, ?, ?, 1, 0, 0, 0, 0, 0)", (run_id, run_ts, asof, action))
        conn.execute(
            "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger,"
            " data_asof_date, action_session_date, state, lease_token, "
            "evaluation_run_id) VALUES (?, ?, ?, 'scheduled', ?, ?, "
            "'complete', ?, ?)",
            (pr_id, run_ts, run_ts.replace("03:30", "03:35"), asof, action,
             f"lease-{pr_id}", run_id))
        if sg_bucket is not None:
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(?, 'SG', ?, 11.9, 12.0, 9.0, 'fallback_spy')",
                (run_id, sg_bucket))
        conn.commit()
    finally:
        conn.close()


def _hidden(text: str, name: str) -> str | None:
    m = re.search(
        rf'<input\s+type="hidden"\s+name="{name}"\s+value="([^"]*)"', text)
    return None if m is None else html.unescape(m.group(1))


def _options(text: str) -> list[tuple[int, bool, str]]:
    m = re.search(
        r'<select[^>]*name="decision_candidate_id"[^>]*>(.*?)</select>',
        text, re.S)
    if m is None:
        return []
    return [(int(v), bool(sel), html.unescape(t).strip())
            for v, sel, t in re.findall(
                r'<option value="(\d+)"( selected)?>([^<]*)</option>',
                m.group(1))]


def _get_form(client: TestClient) -> tuple[str | None, list]:
    resp = client.get("/trades/entry/form?ticker=SG")
    assert resp.status_code == 200, resp.text
    return _hidden(resp.text, "decision_nights_anchor"), _options(resp.text)


def _payload(**over) -> dict:
    data = full_phase7_entry_payload(
        ticker="SG", entry_date="2026-11-06", entry_price="11.95",
        shares="11", initial_stop="8.98", rationale="aplus-setup", notes="",
        origin="watchlist")
    data.update({k: ("" if v is None else str(v)) for k, v in over.items()})
    return data


def _post(client: TestClient, **over):
    return client.post("/trades/entry", data=_payload(**over),
                       headers={"HX-Request": "true"})


def _written(cfg) -> list[tuple]:
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT ticker, trade_origin, candidate_id, hypothesis_label "
            "FROM trades WHERE ticker = 'SG' ORDER BY id").fetchall()
    finally:
        conn.close()


def _assert_cleared(resp, *, rejected_anchor: str | None,
                    expected_text: str) -> None:
    """400, the refusal text, zero trades, and the re-render carries the
    FRESH offer with the default selection -- the rejected anchor string
    never comes back."""
    assert resp.status_code == 400, resp.text
    assert html.escape(expected_text) in resp.text or expected_text in resp.text
    fresh = _hidden(resp.text, "decision_nights_anchor")
    if rejected_anchor is not None:
        assert fresh != rejected_anchor
        assert html.escape(rejected_anchor) not in resp.text
    opts = _options(resp.text)
    if opts:
        assert [o[0] for o in opts if o[1]] == [opts[0][0]], opts


# ---------------------------------------------------------------------------
# 2b -- the GET names three nights, newest selected
# ---------------------------------------------------------------------------
def test_2b_get_renders_three_nights_newest_selected(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, opts = _get_form(client)
    assert [o[0] for o in opts] == [NEWEST, FIRE, OLDER]
    assert [o[1] for o in opts] == [True, False, False]
    assert opts[0][2].startswith("2026-11-06 (eval 194, watch): ")
    assert opts[0][2].endswith(SG_BASELINE_LABEL)
    assert opts[1][2] == f"2026-11-05 (eval 193, watch): {SG_FIRE_LABEL}"
    assert opts[2][2].startswith("2026-11-04 (eval 192, watch): ")
    parsed = json.loads(anchor)
    assert [e["candidate_id"] for e in parsed] == [NEWEST, FIRE, OLDER]
    assert [e["evaluation_run_id"] for e in parsed] == [194, 193, 192]
    assert parsed[1]["label"] == SG_FIRE_LABEL


# ---------------------------------------------------------------------------
# 2c / 2e -- the named night persists; the default persists today's values
# ---------------------------------------------------------------------------
def test_2c_post_naming_the_middle_night_persists_it(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, _opts = _get_form(client)
        resp = _post(client, decision_nights_anchor=anchor,
                     decision_candidate_id=FIRE,
                     hypothesis_label=SG_BASELINE_LABEL)
    assert resp.status_code in (200, 204), resp.text
    assert _written(cfg) == [
        ("SG", "pipeline_watch_manual", FIRE, SG_FIRE_LABEL)]


def test_2e_the_default_night_persists_todays_values(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, opts = _get_form(client)
        selected = [o[0] for o in opts if o[1]][0]
        resp = _post(client, decision_nights_anchor=anchor,
                     decision_candidate_id=selected,
                     hypothesis_label=SG_BASELINE_LABEL)
    assert resp.status_code in (200, 204), resp.text
    assert _written(cfg) == [
        ("SG", "pipeline_watch_manual", NEWEST, SG_BASELINE_LABEL)]


# ---------------------------------------------------------------------------
# 2d -- the 4-tier ladder, the server-stamp, the forged anchors
# ---------------------------------------------------------------------------
_GOOD = object()


def _forged(entries) -> str:
    return json.dumps(entries)


@pytest.mark.parametrize(
    ("anchor", "chosen", "fragment"),
    [
        ("not json at all", FIRE, "is not valid JSON"),
        ('{"candidate_id": 15901}', FIRE, "is not a JSON list"),
        ('[{"candidate_id": 15901, "label": null}]', FIRE,
         "missing candidate_id, evaluation_run_id or label"),
        ('["15901"]', FIRE, "missing candidate_id, evaluation_run_id or label"),
        ('[{"candidate_id": "15901", "evaluation_run_id": 193, '
         '"label": null}]', FIRE, "carries an invalid value"),
        ('[{"candidate_id": true, "evaluation_run_id": 193, '
         '"label": null}]', FIRE, "carries an invalid value"),
        ('[{"candidate_id": 15901, "evaluation_run_id": 193, '
         '"label": 7}]', FIRE, "carries an invalid value"),
        (_GOOD, "abc", "is not an integer"),
        (_GOOD, 424242, "is not in the offered set"),
        ('[{"candidate_id": 424242, "evaluation_run_id": 193, '
         '"label": null}]', 424242, "is not a SG row of a complete run"),
    ],
    ids=["a-malformed", "b-not-a-list", "c-missing-key", "c-not-an-object",
         "d-string-id", "d-bool-id", "d-non-text-label", "d-choice-not-int",
         "d-choice-not-offered", "d-row-absent"])
def test_2d_each_ladder_rung_refuses_and_clears(
        seeded_db, monkeypatch, anchor, chosen, fragment):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        good, _ = _get_form(client)
        submitted = good if anchor is _GOOD else anchor
        resp = _post(client, decision_nights_anchor=submitted,
                     decision_candidate_id=chosen)
    assert resp.status_code == 400, resp.text
    assert fragment in html.unescape(resp.text)
    assert _written(cfg) == []
    assert _hidden(resp.text, "decision_nights_anchor") == good
    opts = _options(resp.text)
    assert [o[0] for o in opts if o[1]] == [NEWEST]


def test_2d_another_tickers_row_is_refused(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    conn = connect(cfg.paths.db_path)
    try:
        other = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close,"
            " pivot, initial_stop, rs_method) VALUES (193, 'ZZZ', 'watch', "
            "5.0, 5.1, 4.0, 'fallback_spy')").lastrowid
        conn.commit()
    finally:
        conn.close()
    forged = _forged([{"candidate_id": other, "evaluation_run_id": 193,
                       "label": None}])
    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = _post(client, decision_nights_anchor=forged,
                     decision_candidate_id=other)
    _assert_cleared(resp, rejected_anchor=forged,
                    expected_text="is not a SG row of a complete run")
    assert _written(cfg) == []


def test_2d_the_label_changed_gate(seeded_db, monkeypatch):
    """The submitted set names 15901 with a label the server does not derive
    for it: the operator would be recorded under a label he did not see."""
    from swing.web.routes.trades import _DECISION_NIGHT_LABEL_CHANGED_TEXT

    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        good, _ = _get_form(client)
        entries = json.loads(good)
        for e in entries:
            if e["candidate_id"] == FIRE:
                e["label"] = SG_BASELINE_LABEL
        forged = _forged(entries)
        resp = _post(client, decision_nights_anchor=forged,
                     decision_candidate_id=FIRE)
    _assert_cleared(
        resp, rejected_anchor=forged,
        expected_text=_DECISION_NIGHT_LABEL_CHANGED_TEXT.format(
            date="2026-11-05"))
    assert _written(cfg) == []


def test_2d_forged_other_bucket_row_is_refused(seeded_db, monkeypatch):
    """R2-01: anchor and choice altered CONSISTENTLY to name an older aplus
    row under a latest watch night -- the submitted set is a claim, never
    the authority on what is eligible."""
    from swing.web.routes.trades import _DECISION_NIGHT_NOT_OFFERED_TEXT

    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch, buckets={OLDER: "aplus"})
    with TestClient(create_app(cfg, cfg_path)) as client:
        good, opts = _get_form(client)
        assert [o[0] for o in opts] == [NEWEST, FIRE]
        entries = json.loads(good) + [
            {"candidate_id": OLDER, "evaluation_run_id": 192,
             "label": SG_BASELINE_LABEL}]
        forged = _forged(entries)
        resp = _post(client, decision_nights_anchor=forged,
                     decision_candidate_id=OLDER)
    _assert_cleared(resp, rejected_anchor=forged,
                    expected_text=_DECISION_NIGHT_NOT_OFFERED_TEXT)
    assert _written(cfg) == []


def test_2d_forged_row_outside_the_window_is_refused(seeded_db, monkeypatch):
    from swing.recommendations import hypothesis_prefill
    from swing.web.routes.trades import _DECISION_NIGHT_NOT_OFFERED_TEXT

    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    monkeypatch.setattr(hypothesis_prefill, "WATCH_FIRE_WINDOW_ROWS", 2)
    with TestClient(create_app(cfg, cfg_path)) as client:
        good, opts = _get_form(client)
        assert [o[0] for o in opts] == [NEWEST, FIRE]
        forged = _forged(json.loads(good) + [
            {"candidate_id": OLDER, "evaluation_run_id": 192,
             "label": SG_BASELINE_LABEL}])
        resp = _post(client, decision_nights_anchor=forged,
                     decision_candidate_id=OLDER)
    _assert_cleared(resp, rejected_anchor=forged,
                    expected_text=_DECISION_NIGHT_NOT_OFFERED_TEXT)
    assert _written(cfg) == []


def test_2d_a_window_shift_between_get_and_post_is_refused(
        seeded_db, monkeypatch):
    """An HONEST shift: a run completes between GET and POST and pushes the
    chosen last night out of the window."""
    from swing.recommendations import hypothesis_prefill
    from swing.web.routes.trades import _DECISION_NIGHT_NOT_OFFERED_TEXT

    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    monkeypatch.setattr(hypothesis_prefill, "WATCH_FIRE_WINDOW_ROWS", 3)
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, opts = _get_form(client)
        assert [o[0] for o in opts] == [NEWEST, FIRE, OLDER]
        _add_run(cfg, run_id=195, pr_id=209, sg_bucket="watch")
        resp = _post(client, decision_nights_anchor=anchor,
                     decision_candidate_id=OLDER)
    assert resp.status_code == 400, resp.text
    assert html.escape(_DECISION_NIGHT_NOT_OFFERED_TEXT) in resp.text
    assert _written(cfg) == []
    fresh = json.loads(_hidden(resp.text, "decision_nights_anchor"))
    assert OLDER not in [e["candidate_id"] for e in fresh]


def test_2d_a_raced_read_at_post_is_a_400_never_a_500(seeded_db, monkeypatch):
    """SS-1: the GET degrades on a raced cohort read; the POST cannot
    persist a night it could not validate, so it refuses."""
    from swing.metrics.cohort import CohortReadRacedError
    from swing.recommendations import hypothesis_prefill
    from swing.web.routes.trades import _DECISION_NIGHTS_UNAVAILABLE_TEXT

    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, _ = _get_form(client)

        def _raced(*_a, **_k):
            def read():
                raise CohortReadRacedError((29,))
            return read

        monkeypatch.setattr(hypothesis_prefill, "_progress_reader", _raced)
        resp = _post(client, decision_nights_anchor=anchor,
                     decision_candidate_id=FIRE)
    assert resp.status_code == 400, resp.text
    assert html.escape(_DECISION_NIGHTS_UNAVAILABLE_TEXT) in resp.text
    assert _written(cfg) == []


# ---------------------------------------------------------------------------
# 2g -- the soft-warn force resubmit carries the anchor
# ---------------------------------------------------------------------------
def _seed_open_trades(cfg, n: int) -> None:
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for t in ["MSFT", "NVDA", "AMD", "TSLA", "META"][:n]:
                insert_trade_with_event(
                    conn, Trade(
                        id=None, ticker=t, entry_date="2026-11-02",
                        entry_price=100.0, initial_shares=1,
                        initial_stop=90.0, current_stop=90.0,
                        state="entered", watchlist_entry_target=None,
                        watchlist_initial_stop=None, notes=None),
                    event_ts="2026-11-02T09:30:00")
    finally:
        conn.close()


def test_2g_soft_warn_resubmit_carries_the_chosen_night(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    _seed_open_trades(cfg, cfg.position_limits.soft_warn_open)
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, _ = _get_form(client)
        first = _post(client, decision_nights_anchor=anchor,
                      decision_candidate_id=FIRE)
        assert first.status_code == 200, first.text
        assert _written(cfg) == []
        assert _hidden(first.text, "decision_candidate_id") == str(FIRE)
        assert _hidden(first.text, "decision_nights_anchor") == anchor
        fragment = dict(re.findall(
            r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
            first.text))
        fragment = {k: html.unescape(v) for k, v in fragment.items()}
        fragment["force"] = "true"
        second = client.post("/trades/entry", data=fragment,
                             headers={"HX-Request": "true"})
    assert second.status_code in (200, 204), second.text
    assert _written(cfg) == [
        ("SG", "pipeline_watch_manual", FIRE, SG_FIRE_LABEL)]


# ---------------------------------------------------------------------------
# 2i -- ASCII
# ---------------------------------------------------------------------------
def test_2i_option_text_and_every_new_message_encode_cp1252(
        seeded_db, monkeypatch):
    from swing.web.routes import trades as routes

    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        _anchor, opts = _get_form(client)
    assert opts
    for _cid, _sel, text in opts:
        text.encode("ascii")
    texts = [getattr(routes, n) for n in dir(routes)
             if n.startswith("_DECISION_")
             and isinstance(getattr(routes, n), str)]
    assert len(texts) >= 5
    for text in texts:
        text.encode("ascii")
    # The composed rung texts too (every rung's detail is server-written).
    for raw, chosen in (("x", "1"), ("{}", "1"), ("[1]", "1"),
                        ('[{"candidate_id": "1", "evaluation_run_id": 1, '
                         '"label": null}]', "1"),
                        ('[]', "abc"), ('[]', "1")):
        refusal, _c, _o = routes._decision_anchor_refusal(
            raw, chosen, ticker="SG", conn=None)
        refusal.encode("ascii")


# ---------------------------------------------------------------------------
# 2k -- the F6 edge, both halves
# ---------------------------------------------------------------------------
def test_2k_no_row_in_the_latest_run_renders_no_chooser_and_posts_today(
        seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    _add_run(cfg, run_id=195, pr_id=209, sg_bucket=None)
    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get("/trades/entry/form?ticker=SG")
        assert resp.status_code == 200
        assert 'name="decision_candidate_id"' not in resp.text
        assert 'name="decision_nights_anchor"' not in resp.text
        label = _hidden(resp.text, "hypothesis_label")
        post = _post(client, hypothesis_label=label)
    assert post.status_code in (200, 204), post.text
    assert _written(cfg) == [("SG", "manual_off_pipeline", None, None)]


# ---------------------------------------------------------------------------
# 2f -- the latched entry: no chooser, and the latch wins at POST
# ---------------------------------------------------------------------------
def test_2f_latched_entry_has_no_chooser_and_the_latch_wins(
        seeded_db, monkeypatch):
    from swing.recommendations.hypothesis_prefill import list_decision_nights
    from swing.trades import entry_auto_fill
    from swing.trades.entry_auto_fill import EntryAutoFillResult
    from tests._latch_probe_world_22a import FILL_SESSION, TICKER
    from tests.web.test_routes.test_22a_task10_entry_route_ext2 import (
        _build_route_world,
        _envelope,
        _post_data,
    )

    cfg, cfg_path = seeded_db
    candidate_id, pipeline_run_id = _build_route_world(
        cfg, with_link=True, ticker_in_todays_run=True)
    envelope = _envelope()

    def _fake(*, ticker, cfg, conn):  # noqa: ARG001
        return EntryAutoFillResult(
            kind="populated", fill_origin="schwab_auto",
            entry_date=FILL_SESSION.isoformat(), entry_price=18.50, shares=2,
            schwab_source_value_json=envelope,
            auto_fill_audit_at=f"{FILL_SESSION.isoformat()}T09:00:00")

    monkeypatch.setattr(entry_auto_fill, "resolve_entry_auto_fill", _fake)
    _patch_price_cache(monkeypatch)

    conn = connect(cfg.paths.db_path)
    try:
        nights = list_decision_nights(
            conn, ticker=TICKER, starting_equity=cfg.account.starting_equity)
    finally:
        conn.close()
    assert nights, "the world must offer nights, or the omission is vacuous"
    drift = [n for n in nights if n.candidate_id != candidate_id][0]
    anchor = json.dumps([
        {"candidate_id": n.candidate_id,
         "evaluation_run_id": n.evaluation_run_id, "label": n.label}
        for n in nights])

    with TestClient(create_app(cfg, cfg_path)) as client:
        get = client.get(f"/trades/entry/form?ticker={TICKER}")
        assert get.status_code == 200
        assert 'name="decision_candidate_id"' not in get.text
        assert 'name="decision_nights_anchor"' not in get.text
        data = _post_data(pipeline_run_id=pipeline_run_id, envelope=envelope)
        data["decision_nights_anchor"] = anchor
        data["decision_candidate_id"] = str(drift.candidate_id)
        resp = client.post("/trades/entry", data=data,
                           headers={"HX-Request": "true"})
    assert resp.status_code == 200, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT ticker, trade_origin, candidate_id, hypothesis_label "
            "FROM trades ORDER BY id").fetchall()
    finally:
        conn.close()
    assert rows == [(TICKER, "pipeline_aplus", candidate_id,
                     "A+ baseline (aplus)")]
