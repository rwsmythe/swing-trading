"""Phase 13 T3.SB2 T-B.2.3 — exit_post audit columns + fill_origin transitions.

SELL-side mirror of test_entry_post_audit_columns.py. Per plan §G.5 T-B.2.3
+ dispatch brief §5 watch items:

  (a) persists fill_origin='schwab_auto' when no operator edits vs anchor.
  (b) flips to fill_origin='schwab_auto_then_operator_corrected' when
      operator edited any of (exit_date, exit_price, shares).
  (c) persists fill_origin='operator_typed' when no auto-fill anchor.
  (d) emits no DUPLICATE schwab_api_calls audit row — the form-render path
      (T-B.2.2 resolve_exit_auto_fill) already emitted surface='trade_exit';
      POST handler MUST NOT re-fetch. The POST just persists the envelope
      from the form-render audit row.
  (e) soft-warn-style hidden anchor round-trip discipline: every form-render
      hidden anchor flows back into POST handler intact (Phase 9 D R3
      Critical #1 + brief watch item 9 LOCK). Exit form has NO soft-warn
      surface (only entries do, since soft-warn is the position-count gate
      at trade entry); we instead exercise the recovery-form-re-render path:
      on validation 400, the bad anchor is CLEARED (not echoed back) per
      Recovery form anchor-clear discipline (T3.SB1 R3 M#2).
  (f) `... or None` (NOT `... or ''`) for nullable audit fields (Phase 6
      CLAUDE.md `... or ""` vs CHECK enum gotcha).
  (g) multi-partial case — operator selects one candidate; post handler
      persists chosen candidate's signature_hash in
      schwab_source_value_json envelope + records other candidates'
      signature_hashes in 'other_candidate_signature_hashes' for audit.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos import trades as trades_repo
from swing.data.repos.trades import list_open_trades
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=110.0, asof=datetime.now(),
                is_stale=False, source="live",
            )
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _seed_open_trade(cfg, ticker: str = "NVDA") -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Call via the module reference so the autouse
            # `_auto_entry_fill_after_insert_trade` monkeypatch is honored
            # (otherwise current_size stays 0 + record_exit's
            # `shares > current_size` guard rejects).
            trades_repo.insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=100.0, initial_shares=10, initial_stop=95.0,
                current_stop=95.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
        return int(trade.id)
    finally:
        conn.close()


def _make_anchor(
    *, exit_date: str = "2026-05-19",
    exit_price: float = 120.50,
    closed_shares: int = 10,
    schwab_order_id: str | None = "order-xyz",
    candidate_count: int = 1,
) -> str:
    """Production-shape envelope mirroring resolve_exit_auto_fill output."""
    return json.dumps(
        {
            "exit_date": exit_date,
            "exit_price": exit_price,
            "closed_shares": closed_shares,
            "schwab_order_id": schwab_order_id,
            "schwab_instrument_symbol": "NVDA",
            "candidate_count": candidate_count,
        },
        sort_keys=True,
    )


def _post_exit(client: TestClient, trade_id: int, **fields: Any):
    """POST /trades/{id}/exit with minimum-valid form merged with overrides."""
    base = {
        "exit_date": "2026-05-19",
        "exit_price": "120.50",
        "shares": "10",
        "reason": "manual",
        "notes": "",
    }
    base.update({k: ("" if v is None else str(v)) for k, v in fields.items()})
    return client.post(
        f"/trades/{trade_id}/exit", data=base,
        headers={"HX-Request": "true"},
    )


# ============================================================================
# (a) Unchanged auto-populated values -> fill_origin='schwab_auto'.
# ============================================================================


def test_a_unchanged_auto_fill_persists_schwab_auto(seeded_db, monkeypatch):
    """POST with anchor matching submitted values -> schwab_auto.

    schwab_source_value_json persisted verbatim; operator_corrected_value_json
    is NULL; auto_fill_audit_at persisted.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    anchor = _make_anchor(
        exit_date="2026-05-19", exit_price=120.50, closed_shares=10,
    )
    audit_at = "2026-05-19T14:30:00.000000+00:00"
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            schwab_source_value_json=anchor,
            auto_fill_audit_at=audit_at,
            fill_origin_at_form_render="schwab_auto",
            candidate_signature_hash_0="sig-cand-0",
            candidate_order_id_0="order-xyz",
            candidate_index="0",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at "
            "FROM fills WHERE action != 'entry' "
            "ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "exit fill should be persisted"
    assert row[0] == "schwab_auto"
    # Envelope is RE-STAMPED with operator-selection provenance per dispatch
    # brief (single-fill case: candidate_index defaults to 0; chosen
    # candidate's signature_hash + order_id are added; other_candidate_*
    # is an empty list).
    persisted = json.loads(row[1])
    original = json.loads(anchor)
    for k, v in original.items():
        assert persisted[k] == v, (
            f"original envelope key {k!r} must round-trip verbatim"
        )
    assert persisted["selected_candidate_signature_hash"] == "sig-cand-0"
    assert persisted["selected_candidate_order_id"] == "order-xyz"
    assert persisted["other_candidate_signature_hashes"] == []
    assert row[2] is None, (
        "operator_corrected_value_json must be NULL when no edits "
        "(per `... or None` CLAUDE.md gotcha)"
    )
    assert row[3] == audit_at


# ============================================================================
# (b) Edited auto-populated values -> schwab_auto_then_operator_corrected.
# ============================================================================


def test_b_edited_price_flips_to_then_operator_corrected(
    seeded_db, monkeypatch,
):
    """Operator edits exit_price from 120.50 -> 121.00. fill_origin flips
    + operator_corrected_value_json carries submitted values.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    anchor = _make_anchor(
        exit_date="2026-05-19", exit_price=120.50, closed_shares=10,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            exit_price="121.00",  # edited
            schwab_source_value_json=anchor,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
            candidate_signature_hash_0="sig-0",
            candidate_order_id_0="order-xyz",
            candidate_index="0",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at "
            "FROM fills WHERE action != 'entry' "
            "ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "schwab_auto_then_operator_corrected"
    # Re-stamped envelope carries original keys + provenance fields.
    persisted = json.loads(row[1])
    original = json.loads(anchor)
    for k, v in original.items():
        assert persisted[k] == v
    assert row[2] is not None
    corrected = json.loads(row[2])
    assert corrected["exit_price"] == 121.00
    assert corrected["closed_shares"] == 10
    assert corrected["exit_date"] == "2026-05-19"


# ============================================================================
# (c) No anchor -> operator_typed.
# ============================================================================


def test_c_no_anchor_persists_operator_typed(seeded_db, monkeypatch):
    """POST without auto-fill hidden anchors -> fill_origin='operator_typed';
    all audit columns NULL (legacy / bare-cURL backward-compat).
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(client, trade_id)
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at "
            "FROM fills WHERE action != 'entry' "
            "ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "operator_typed"
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None


# ============================================================================
# (d) POST handler does NOT emit a NEW schwab_api_calls audit row.
# The form-render path (T-B.2.2 resolve_exit_auto_fill) already emitted
# surface='trade_exit'. POST handler MUST NOT re-fetch.
# ============================================================================


def test_d_post_does_not_emit_new_schwab_api_call_audit_row(
    seeded_db, monkeypatch,
):
    """POST persists fill columns but does NOT re-invoke Schwab.

    Discriminating: count schwab_api_calls rows before and after POST;
    POST must add ZERO new rows. (The form-render T-B.2.2 path may emit
    one row; we count BEFORE the POST so this test is independent.)
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    anchor = _make_anchor()
    audit_at = "2026-05-19T14:30:00.000000+00:00"

    conn = connect(cfg.paths.db_path)
    try:
        n_before = conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls"
        ).fetchone()[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            schwab_source_value_json=anchor,
            auto_fill_audit_at=audit_at,
            fill_origin_at_form_render="schwab_auto",
            candidate_signature_hash_0="sig-0",
            candidate_order_id_0="order-xyz",
            candidate_index="0",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        n_after = conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n_after == n_before, (
        "exit_post MUST NOT emit a new schwab_api_calls row "
        "(form-render path emits the surface='trade_exit' row)"
    )


# ============================================================================
# (e) Hidden-anchor 4-tier rejection ladder + recovery-form anchor-clear.
# ============================================================================


def test_e_malformed_anchor_with_claim_rejects_with_400_and_clears_anchor(
    seeded_db, monkeypatch,
):
    """4-tier rejection (a): malformed JSON + claim -> 400.

    Recovery form anchor-clear discipline (T3.SB1 R3 M#2 BINDING): the
    rejected anchor must NOT be echoed back into the recovery form, so
    the operator's next retry sees a FRESH anchor (or no anchor) - not
    the bad one re-replayed.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            schwab_source_value_json="not a json envelope",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 400, resp.text
    # The bad anchor must NOT be echoed back into the recovery form's
    # hidden inputs. The recovery form may render WITHOUT the anchor or
    # with a fresh resolver-emitted one; the literal bad value must not
    # be present in the response.
    assert "not a json envelope" not in resp.text, (
        "Recovery form must NOT echo the rejected anchor back "
        "(T3.SB1 R3 M#2 anchor-clear discipline)"
    )
    # No exit fill should have been written.
    conn = connect(cfg.paths.db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM fills WHERE action != 'entry'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_e_non_dict_json_anchor_with_claim_rejects(seeded_db, monkeypatch):
    """4-tier rejection (b): non-dict JSON (e.g. '[]') + claim -> 400."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            schwab_source_value_json="[]",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 400, resp.text


def test_e_dict_anchor_missing_keys_with_claim_rejects(seeded_db, monkeypatch):
    """4-tier rejection (c): dict missing required keys + claim -> 400."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            schwab_source_value_json="{}",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 400, resp.text


def test_e_dict_anchor_invalid_value_shapes_with_claim_rejects(
    seeded_db, monkeypatch,
):
    """4-tier rejection (d): invalid value shapes (NaN price, calendar-
    invalid date, non-int shares) + claim -> 400.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    # NaN price.
    nan_anchor = (
        '{"exit_date": "2026-05-19", "exit_price": NaN, "closed_shares": 10}'
    )
    with TestClient(app) as client:
        resp_nan = _post_exit(
            client, trade_id,
            schwab_source_value_json=nan_anchor,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
        assert resp_nan.status_code == 400, resp_nan.text
        # Calendar-invalid date.
        bad_date = json.dumps(
            {"exit_date": "2026-99-99", "exit_price": 120.50,
             "closed_shares": 10},
        )
        resp_date = _post_exit(
            client, trade_id,
            schwab_source_value_json=bad_date,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
        assert resp_date.status_code == 400, resp_date.text
        # Non-int shares.
        bad_shares = json.dumps(
            {"exit_date": "2026-05-19", "exit_price": 120.50,
             "closed_shares": 10.5},
        )
        resp_shares = _post_exit(
            client, trade_id,
            schwab_source_value_json=bad_shares,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
        assert resp_shares.status_code == 400, resp_shares.text


def test_e_valid_anchor_without_claim_persists_operator_typed(
    seeded_db, monkeypatch,
):
    """Anti-forgery gate: valid anchor without
    fill_origin_at_form_render='schwab_auto' claim MUST NOT stamp Schwab
    provenance. Persists as operator_typed.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    anchor = _make_anchor()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            schwab_source_value_json=anchor,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="",  # empty claim
        )
    assert resp.status_code == 200, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, auto_fill_audit_at "
            "FROM fills WHERE action != 'entry' "
            "ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "operator_typed"
    assert row[1] is None
    assert row[2] is None


# ============================================================================
# (f) `... or None` (NOT `... or ''`) for nullable audit fields.
# ============================================================================


def test_f_empty_audit_at_form_field_persists_null_not_empty_string(
    seeded_db, monkeypatch,
):
    """When auto_fill_audit_at form field is empty BUT
    schwab_source_value_json + claim present (partial/tampered POST),
    auto_fill_audit_at column persists NULL via `... or None`.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    anchor = _make_anchor()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            schwab_source_value_json=anchor,
            auto_fill_audit_at="",  # empty -> NULL via `or None`
            fill_origin_at_form_render="schwab_auto",
            candidate_signature_hash_0="sig-0",
            candidate_order_id_0="order-xyz",
            candidate_index="0",
        )
    assert resp.status_code == 200, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT auto_fill_audit_at FROM fills "
            "WHERE action != 'entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is None, (
        "empty form field must coerce to NULL via `... or None` "
        "(CLAUDE.md gotcha 2026-05-04)"
    )


# ============================================================================
# (g) Multi-partial — operator selects non-default candidate; persisted
# envelope reflects chosen candidate + other candidates' signature_hashes
# preserved for audit history.
# ============================================================================


def test_g_multi_partial_selects_non_default_candidate_and_preserves_others(
    seeded_db, monkeypatch,
):
    """Form rendered with 3 candidates (chronological c0, c1, c2; default
    chosen is c2 most-recent). Operator selects c1 instead (candidate_index=1).

    POST handler:
      * persists exit_date/exit_price/shares per the submitted form
        (which the form pre-populated from c1's selection).
      * the persisted ``schwab_source_value_json`` envelope's
        ``signature_hash`` field maps to c1's hash (operator-selected).
      * ``other_candidate_signature_hashes`` field carries [c0.sig, c2.sig]
        (the non-selected candidates) for audit history.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    # The form-render envelope (from T-B.2.2) - per-fill candidate identities
    # in candidate_signature_hash_<i> + candidate_order_id_<i> hidden inputs.
    # We submit c1's values (selected = candidate_index=1) and the chosen
    # candidate's signature_hash must be embedded in the persisted envelope.
    form_render_envelope = json.dumps(
        {
            "exit_date": "2026-05-19",
            "exit_price": 120.00,
            "closed_shares": 3,
            "candidate_count": 3,
            "schwab_order_id": "order-2",
            "schwab_instrument_symbol": "NVDA",
        },
        sort_keys=True,
    )
    audit_at = "2026-05-19T14:30:00.000000+00:00"
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_exit(
            client, trade_id,
            exit_date="2026-05-17",   # c1's date
            exit_price="115.50",      # c1's price
            shares="4",               # c1's quantity
            schwab_source_value_json=form_render_envelope,
            auto_fill_audit_at=audit_at,
            fill_origin_at_form_render="schwab_auto",
            candidate_index="1",      # operator picked c1
            candidate_signature_hash_0="sig-cand-0",
            candidate_order_id_0="order-0",
            candidate_signature_hash_1="sig-cand-1",
            candidate_order_id_1="order-1",
            candidate_signature_hash_2="sig-cand-2",
            candidate_order_id_2="order-2",
        )
    assert resp.status_code == 200, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, quantity, price, fill_datetime "
            "FROM fills WHERE action != 'entry' "
            "ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    # Architectural decision (V1): the template emits per-candidate
    # signature_hash + order_id but NOT per-candidate price/date/quantity,
    # so the POST-handler comparison is against the form-render envelope's
    # defaults (the chosen=most-recent candidate's values, i.e. c2). The
    # operator selecting c1 + submitting c1's values DIFFERS from those
    # defaults -> flip to schwab_auto_then_operator_corrected. The
    # selected_candidate_signature_hash field documents which candidate
    # the operator actually picked, providing full audit clarity.
    assert row[0] == "schwab_auto_then_operator_corrected", (
        f"non-default candidate selection differs from anchor envelope "
        f"defaults; expected then_operator_corrected, got {row[0]!r}"
    )
    persisted = json.loads(row[1])
    assert persisted.get("selected_candidate_signature_hash") == "sig-cand-1"
    assert persisted.get("selected_candidate_order_id") == "order-1"
    others = persisted.get("other_candidate_signature_hashes")
    assert others is not None
    assert sorted(others) == sorted(["sig-cand-0", "sig-cand-2"])
    # Operator-corrected envelope carries submitted values.
    assert row[2] is not None
    corrected = json.loads(row[2])
    assert corrected["exit_date"] == "2026-05-17"
    assert corrected["exit_price"] == 115.50
    assert corrected["closed_shares"] == 4
    # Persisted exit fill carries c1's values (rounded to fill-row precision).
    assert float(row[4]) == 115.50
    assert float(row[3]) == 4.0


def test_g_multi_partial_invalid_candidate_index_rejects_with_400(
    seeded_db, monkeypatch,
):
    """Operator's candidate_index must map to a server-rendered candidate.
    Out-of-range index OR non-int index -> 400 (tamper / stale form).
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    envelope = json.dumps(
        {
            "exit_date": "2026-05-19",
            "exit_price": 120.00,
            "closed_shares": 3,
            "candidate_count": 3,
        },
        sort_keys=True,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Out-of-range: only 2 candidate rows but candidate_index=5.
        resp_oor = _post_exit(
            client, trade_id,
            schwab_source_value_json=envelope,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
            candidate_index="5",  # NO candidate_signature_hash_5 -> out of range
            candidate_signature_hash_0="sig-0",
            candidate_order_id_0="ord-0",
            candidate_signature_hash_1="sig-1",
            candidate_order_id_1="ord-1",
        )
        assert resp_oor.status_code == 400, resp_oor.text
        # Non-int.
        resp_bad = _post_exit(
            client, trade_id,
            schwab_source_value_json=envelope,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
            candidate_index="not-an-int",
            candidate_signature_hash_0="sig-0",
            candidate_order_id_0="ord-0",
        )
        assert resp_bad.status_code == 400, resp_bad.text
