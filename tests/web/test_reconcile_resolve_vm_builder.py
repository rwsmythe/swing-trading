"""Phase 12.5 #2 T-2.3 — `build_reconcile_discrepancy_resolve_vm` builder.

Tests the VM builder for the web Tier-2 discrepancy-resolution surface
(``GET /reconcile/discrepancy/{id}/resolve``). Builder is read-only on
``conn``; assembles the VM from:

  - ``get_discrepancy`` (data layer)
  - ``_render_pre_resolution_context`` (T-2.2)
  - ``get_choice_menu`` + parametric pick_schwab_record_<N> entries
  - ``count_unresolved_material`` + ``count_recent_multi_leg_auto_corrections``
  - ``action_session_for_run`` (session date stamp)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.web.view_models.reconcile import (
    ReconcileChoiceFormItem,
    ReconcileDiscrepancyResolveVM,
    ReconcilePreResolutionContext,
    build_reconcile_discrepancy_resolve_vm,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_discrepancy(
    conn: sqlite3.Connection,
    *,
    resolution: str = "pending_ambiguity_resolution",
    ambiguity_kind: str | None = "multi_partial_vs_consolidated",
    resolution_reason: str | None = None,
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    expected_value_json: str | None = '{"price": 10.0}',
    actual_value_json: str | None = '{"price": 10.10}',
) -> int:
    """Plant a minimal discrepancy row + its supporting rows.

    Mirrors ``tests/trades/test_stamp_pending_ambiguity.py:_seed_discrepancy``.
    """
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "AAA", "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
            "manual_off_pipeline", "2026-04-27T16:00:00",
        ),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (trade_id, fill_datetime, action, quantity, price)
        VALUES (?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 10.0),
    )
    fill_id = int(fcur.lastrowid)
    rcur = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES (?, ?, ?)
        """,
        ("schwab_api", "2026-05-18T12:00:00", "running"),
    )
    run_id = int(rcur.lastrowid)
    dcur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, discrepancy_type, trade_id, fill_id, "AAA", field_name,
            expected_value_json, actual_value_json, "+$0.10", 1,
            resolution, ambiguity_kind, resolution_reason,
            "2026-05-18T12:00:00",
        ),
    )
    discrepancy_id = int(dcur.lastrowid)
    conn.commit()
    return discrepancy_id


def test_builder_returns_vm_for_pending_ambiguity_discrepancy(
    conn: sqlite3.Connection,
) -> None:
    did = _seed_discrepancy(conn)
    vm = build_reconcile_discrepancy_resolve_vm(conn, did)
    assert isinstance(vm, ReconcileDiscrepancyResolveVM)
    assert vm.discrepancy_id == did
    assert vm.form_action == f"/reconcile/discrepancy/{did}/resolve"
    assert isinstance(vm.pre_resolution_context, ReconcilePreResolutionContext)
    assert vm.pre_resolution_context.ticker == "AAA"
    # T-2.9 retrofit: builder now calls
    # ``fetch_first_pending_ambiguity_resolve_link_path`` directly so the
    # banner link is populated. With this seed (a single pending-ambiguity
    # discrepancy attributed to an active trade), the link points at
    # the same discrepancy the operator is currently viewing — the
    # self-referential case is acknowledged as informational per plan
    # §A T-2.9 acceptance.
    assert vm.banner_resolve_link == f"/reconcile/discrepancy/{did}/resolve"
    # session_date is a date isoformat string.
    assert len(vm.session_date) == 10 and vm.session_date.count("-") == 2


def test_builder_raises_when_discrepancy_id_not_found(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="discrepancy not found"):
        build_reconcile_discrepancy_resolve_vm(conn, 9999)


def test_builder_raises_when_discrepancy_in_terminal_state(
    conn: sqlite3.Connection,
) -> None:
    did = _seed_discrepancy(
        conn,
        resolution="operator_resolved_ambiguity",
        ambiguity_kind="multi_partial_vs_consolidated",
    )
    with pytest.raises(ValueError):
        build_reconcile_discrepancy_resolve_vm(conn, did)


def test_builder_raises_when_ambiguity_kind_is_null(
    conn: sqlite3.Connection,
) -> None:
    # Seed a valid pending row, then bypass the cross-column CHECK via
    # PRAGMA toggle so the test exercises the builder's defensive guard
    # for a state the C.A CHECK normally prevents. The guard exists as
    # defense-in-depth in case the CHECK is altered V2 or seeded via a
    # path that doesn't go through standard INSERT.
    did = _seed_discrepancy(
        conn,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="multi_partial_vs_consolidated",
    )
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute(
        "UPDATE reconciliation_discrepancies SET ambiguity_kind = NULL "
        "WHERE discrepancy_id = ?",
        (did,),
    )
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")
    with pytest.raises(ValueError):
        build_reconcile_discrepancy_resolve_vm(conn, did)


def test_builder_static_menu_renders_choices_for_multi_partial_vs_consolidated(
    conn: sqlite3.Connection,
) -> None:
    did = _seed_discrepancy(
        conn,
        ambiguity_kind="multi_partial_vs_consolidated",
    )
    vm = build_reconcile_discrepancy_resolve_vm(conn, did)
    # multi_partial_vs_consolidated has 4 static choices.
    assert len(vm.choices) == 4
    assert all(isinstance(c, ReconcileChoiceFormItem) for c in vm.choices)
    # First static choice is keep_journal_as_is (RECOMMENDED).
    first = vm.choices[0]
    assert first.code == "keep_journal_as_is"
    assert first.recommended is True
    assert first.is_parametric_pick is False


def test_builder_prepends_parametric_pick_choices_for_multi_match_within_window_n_eq_3(
    conn: sqlite3.Connection,
) -> None:
    did = _seed_discrepancy(
        conn,
        ambiguity_kind="multi_match_within_window",
        resolution_reason="Schwab returned 3 orders within the match window",
        discrepancy_type="unmatched_open_fill",
        field_name="fill_match",
        expected_value_json=(
            '{"quantity": 100, "price": 10.0, '
            '"fill_datetime": "2026-04-27T14:23:00"}'
        ),
        actual_value_json='{"matched": null}',
    )
    vm = build_reconcile_discrepancy_resolve_vm(conn, did)
    # multi_match_within_window static menu = 2; +3 parametric = 5 total.
    assert len(vm.choices) == 5
    # First 3 entries are parametric picks (prepended).
    for i in range(3):
        c = vm.choices[i]
        assert c.code == f"pick_schwab_record_{i + 1}"
        assert c.is_parametric_pick is True
        assert c.requires_custom_value is True
        assert c.description.startswith(f"Pick Schwab candidate #{i + 1}")
    # Remaining 2 entries are the static menu (mark_unmatched, custom).
    assert vm.choices[3].code == "mark_unmatched"
    assert vm.choices[3].is_parametric_pick is False
    assert vm.choices[4].code == "custom"
    assert vm.choices[4].is_parametric_pick is False


def test_builder_emits_no_parametric_choices_when_resolution_reason_does_not_match(
    conn: sqlite3.Connection,
) -> None:
    did = _seed_discrepancy(
        conn,
        ambiguity_kind="multi_match_within_window",
        resolution_reason="garbage",
        discrepancy_type="unmatched_open_fill",
        field_name="fill_match",
        expected_value_json=(
            '{"quantity": 100, "price": 10.0, '
            '"fill_datetime": "2026-04-27T14:23:00"}'
        ),
        actual_value_json='{"matched": null}',
    )
    vm = build_reconcile_discrepancy_resolve_vm(conn, did)
    # Zero parametric entries; static menu intact (2 entries).
    assert len(vm.choices) == 2
    assert all(c.is_parametric_pick is False for c in vm.choices)
    assert vm.choices[0].code == "mark_unmatched"
    assert vm.choices[1].code == "custom"


def test_builder_assembles_form_action_url_from_discrepancy_id(
    conn: sqlite3.Connection,
) -> None:
    did = _seed_discrepancy(conn)
    vm = build_reconcile_discrepancy_resolve_vm(conn, did)
    assert vm.form_action == f"/reconcile/discrepancy/{did}/resolve"
