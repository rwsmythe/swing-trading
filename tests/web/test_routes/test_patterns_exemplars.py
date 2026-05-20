"""Phase 13 T2.SB1 T-A.1.6 — `/patterns/exemplars` web surface tests.

Per plan §G.1 T-A.1.6 Step 1: 7+ discriminating tests covering:
  (a) GET lists silver rows.
  (b) POST action promote_to_gold flips row.
  (c) POST action reject flips row.
  (d) POST action relabel with corrected_pattern_class form field.
  (e) POST action watch.
  (f) PatternExemplarsVM extends BaseLayoutVM.
  (g) PatternExemplarsVM populates banner pin fields per forward-binding
      lesson #12 (unresolved_material_discrepancies_count +
      banner_resolve_link + recent_multi_leg_auto_correction_count).

HTMX failure-surface coverage (CLAUDE.md gotcha family):
  - HX-Request propagation on embedded form (Phase 5 R1 M1).
  - HX-Redirect success path 204 + /patterns/exemplars (Phase 5 R1 M2).
  - HX-Redirect target /patterns/exemplars registered in app.routes
    (Phase 6 I3 lesson).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import PatternExemplar
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.web.app import create_app
from swing.web.view_models.metrics.shared import BaseLayoutVM
from swing.web.view_models.patterns.exemplars import (
    PatternExemplarsVM,
    build_patterns_exemplars_vm,
)

# ---------------------------------------------------------------------------
# Fixtures (seed silver-tier + gold-tier rows)
# ---------------------------------------------------------------------------


def _make_silver(ticker: str, pattern_class: str = "vcp") -> PatternExemplar:
    return PatternExemplar(
        id=None,
        ticker=ticker,
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        proposed_pattern_class=pattern_class,
        final_decision="confirmed",
        label_source="claude_silver",
        structural_evidence_json="{}",
        created_at="2024-02-02T00:00:00.000",
        created_by="claude_dispatch",
        labeler_evidence_json="{}",
        geometric_score_json=None,
    )


def _make_gold(ticker: str, pattern_class: str = "flat_base") -> PatternExemplar:
    return PatternExemplar(
        id=None,
        ticker=ticker,
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        proposed_pattern_class=pattern_class,
        final_decision="confirmed",
        label_source="curated_gold",
        structural_evidence_json="{}",
        created_at="2024-02-02T00:00:00.000",
        created_by="operator",
        geometric_score_json="{\"score\": 0.95}",
        labeler_evidence_json="{}",
        gold_validated_at="2024-02-03T00:00:00.000",
    )


@pytest.fixture
def seeded_db_with_exemplars(seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            exemplars_repo.insert_exemplar(conn, _make_silver("ABC", "vcp"))
            exemplars_repo.insert_exemplar(conn, _make_silver("XYZ", "flat_base"))
            exemplars_repo.insert_exemplar(
                conn, _make_gold("MMM", "cup_with_handle"),
            )
    finally:
        conn.close()
    return cfg, cfg_path


# ---------------------------------------------------------------------------
# Test (a): GET lists silver rows.
# ---------------------------------------------------------------------------


def test_get_patterns_exemplars_lists_silver_rows(seeded_db_with_exemplars):
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    # Silver-tier section + both planted silver tickers.
    assert "Silver tier (awaiting operator review)" in r.text
    assert "ABC" in r.text
    assert "XYZ" in r.text
    # Gold-tier section + planted gold ticker.
    assert "Gold tier (operator-validated)" in r.text
    assert "MMM" in r.text


def test_get_patterns_exemplars_empty_advisory_when_no_rows(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    assert "No exemplars yet" in r.text


# ---------------------------------------------------------------------------
# Test (b): POST promote_to_gold flips row.
# ---------------------------------------------------------------------------


def test_post_action_promote_to_gold_flips_label_source(
    seeded_db_with_exemplars,
):
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Find a silver row id.
        r = client.get("/patterns/exemplars")
        assert r.status_code == 200
    conn = connect(cfg.paths.db_path)
    silver_rows = [
        e for e in exemplars_repo.list_exemplars(conn)
        if e.label_source == "claude_silver"
    ]
    conn.close()
    assert silver_rows
    silver_id = silver_rows[0].id

    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "promote_to_gold"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/patterns/exemplars"

    # Row label_source flipped to curated_gold + gold_validated_at non-NULL.
    conn = connect(cfg.paths.db_path)
    persisted = exemplars_repo.get_exemplar_by_id(conn, silver_id)
    conn.close()
    assert persisted is not None
    assert persisted.label_source == "curated_gold"
    assert persisted.final_decision == "confirmed"
    assert persisted.gold_validated_at is not None


# ---------------------------------------------------------------------------
# T-A.1.8 Deficiency 2 fix: relabel-then-promote-to-gold preserves the
# operator's relabel (final_pattern_class STAYS non-NULL through the gold
# promotion). The previous SQL unconditionally stamped
# final_pattern_class = NULL on promote-to-gold, blocking operator workflow
# where they first relabel a silver row + then promote it to gold under
# the corrected class.
# ---------------------------------------------------------------------------


def test_relabel_then_promote_to_gold_preserves_operator_relabel_intent(
    seeded_db_with_exemplars,
):
    """Plant relabeled row (proposed='vcp', final_pattern_class='flat_base');
    promote to gold; assert the operator's relabel target SURVIVES gold
    promotion (proposed_pattern_class absorbs the relabel target;
    final_pattern_class NULL to satisfy Invariant #1).

    Deficiency 2 closure: the operator's intent is "promote this row to
    gold under the corrected class", which the pre-fix UPDATE blocked by
    unconditionally stamping final_pattern_class=NULL while leaving
    proposed_pattern_class at the original (now-rejected) class. The
    schema-faithful fix COALESCEs the relabel target into
    proposed_pattern_class + nulls final_pattern_class, satisfying both
    operator intent + Invariant #1 of pattern_exemplars schema.
    """
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)

    conn = connect(cfg.paths.db_path)
    # Pick the VCP-proposed silver row + relabel it via the SQL UPDATE
    # path the relabel handler uses (single-tx; mirrors the route handler).
    silver_id = [
        e for e in exemplars_repo.list_exemplars(conn)
        if e.label_source == "claude_silver"
        and e.proposed_pattern_class == "vcp"
    ][0].id
    with conn:
        conn.execute(
            "UPDATE pattern_exemplars SET final_decision = 'relabeled', "
            "final_pattern_class = 'flat_base' WHERE id = ?",
            (silver_id,),
        )
    pre = exemplars_repo.get_exemplar_by_id(conn, silver_id)
    conn.close()
    assert pre is not None
    assert pre.proposed_pattern_class == "vcp"
    assert pre.final_pattern_class == "flat_base"
    assert pre.final_decision == "relabeled"

    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "promote_to_gold"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204

    conn = connect(cfg.paths.db_path)
    persisted = exemplars_repo.get_exemplar_by_id(conn, silver_id)
    conn.close()
    assert persisted is not None
    assert persisted.label_source == "curated_gold"
    assert persisted.final_decision == "confirmed"
    assert persisted.gold_validated_at is not None
    # Deficiency 2 closure: relabel target absorbed into proposed +
    # final_pattern_class nulled to satisfy Invariant #1.
    assert persisted.proposed_pattern_class == "flat_base", (
        "Deficiency 2 regression: relabel target 'flat_base' was NOT "
        "absorbed into proposed_pattern_class at gold promotion; "
        "operator's corrected class lost."
    )
    assert persisted.final_pattern_class is None, (
        "Deficiency 2 fix violated Invariant #1: final_pattern_class MUST "
        "be NULL when final_decision != 'relabeled'."
    )


def test_unmodified_silver_then_promote_to_gold_preserves_proposed_class(
    seeded_db_with_exemplars,
):
    """Plant unmodified silver row (final_pattern_class=NULL,
    proposed='vcp'); promote to gold; assert proposed_pattern_class
    STAYS 'vcp' + final_pattern_class STAYS NULL. Confirms the COALESCE
    branch doesn't accidentally clobber proposed_pattern_class when there's
    no relabel to absorb.
    """
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)

    conn = connect(cfg.paths.db_path)
    silver = [
        e for e in exemplars_repo.list_exemplars(conn)
        if e.label_source == "claude_silver"
        and e.proposed_pattern_class == "vcp"
        and e.final_pattern_class is None
    ][0]
    silver_id = silver.id
    conn.close()

    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "promote_to_gold"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204

    conn = connect(cfg.paths.db_path)
    persisted = exemplars_repo.get_exemplar_by_id(conn, silver_id)
    conn.close()
    assert persisted is not None
    assert persisted.label_source == "curated_gold"
    assert persisted.final_decision == "confirmed"
    assert persisted.proposed_pattern_class == "vcp", (
        "Unmodified silver promotion must not perturb proposed_pattern_class "
        "(the operator confirmed the proposed class; no relabel to absorb)."
    )
    assert persisted.final_pattern_class is None, (
        "Unmodified silver promotion should keep final_pattern_class=NULL "
        "(no relabel; Invariant #1 satisfied)."
    )


# ---------------------------------------------------------------------------
# Test (c): POST action reject.
# ---------------------------------------------------------------------------


def test_post_action_reject_flips_final_decision(seeded_db_with_exemplars):
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)

    conn = connect(cfg.paths.db_path)
    silver_rows = [
        e for e in exemplars_repo.list_exemplars(conn)
        if e.label_source == "claude_silver"
    ]
    conn.close()
    silver_id = silver_rows[0].id

    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "reject"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/patterns/exemplars"

    conn = connect(cfg.paths.db_path)
    persisted = exemplars_repo.get_exemplar_by_id(conn, silver_id)
    conn.close()
    assert persisted is not None
    assert persisted.final_decision == "rejected"
    assert persisted.label_source == "claude_silver"  # source unchanged


# ---------------------------------------------------------------------------
# Test (d): POST action relabel.
# ---------------------------------------------------------------------------


def test_post_action_relabel_with_corrected_class(seeded_db_with_exemplars):
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)

    conn = connect(cfg.paths.db_path)
    # Pick the VCP-proposed silver row so we can relabel to flat_base.
    silver_rows = [
        e for e in exemplars_repo.list_exemplars(conn)
        if e.label_source == "claude_silver"
        and e.proposed_pattern_class == "vcp"
    ]
    conn.close()
    assert silver_rows
    silver_id = silver_rows[0].id

    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={
                "action": "relabel",
                "corrected_pattern_class": "flat_base",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/patterns/exemplars"

    conn = connect(cfg.paths.db_path)
    persisted = exemplars_repo.get_exemplar_by_id(conn, silver_id)
    conn.close()
    assert persisted is not None
    assert persisted.final_decision == "relabeled"
    assert persisted.final_pattern_class == "flat_base"
    assert persisted.proposed_pattern_class == "vcp"


def test_post_relabel_rejects_missing_corrected_class(seeded_db_with_exemplars):
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)
    conn = connect(cfg.paths.db_path)
    silver_id = exemplars_repo.list_exemplars(conn)[0].id
    conn.close()

    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "relabel"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Test (e): POST action watch.
# ---------------------------------------------------------------------------


def test_post_action_watch_flips_final_decision(seeded_db_with_exemplars):
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)
    conn = connect(cfg.paths.db_path)
    silver_id = [
        e for e in exemplars_repo.list_exemplars(conn)
        if e.label_source == "claude_silver"
    ][0].id
    conn.close()

    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "watch"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/patterns/exemplars"

    conn = connect(cfg.paths.db_path)
    persisted = exemplars_repo.get_exemplar_by_id(conn, silver_id)
    conn.close()
    assert persisted is not None
    assert persisted.final_decision == "watch"


# ---------------------------------------------------------------------------
# Test (f): VM extends BaseLayoutVM.
# ---------------------------------------------------------------------------


def test_pattern_exemplars_vm_extends_base_layout_vm():
    assert issubclass(PatternExemplarsVM, BaseLayoutVM), (
        "PatternExemplarsVM MUST extend BaseLayoutVM so base.html.j2 "
        "banner block renders without UndefinedError (forward-binding "
        "lesson #12)."
    )


# ---------------------------------------------------------------------------
# Test (g): VM populates banner pin fields per forward-binding lesson #12.
# ---------------------------------------------------------------------------


def test_pattern_exemplars_vm_populates_banner_pin_fields(
    seeded_db_with_exemplars,
):
    """Per Codex R1 Major #3 closure + forward-binding lesson #12:
    PatternExemplarsVM populates unresolved_material_discrepancies_count
    + recent_multi_leg_auto_correction_count + banner_resolve_link.
    """
    cfg, _ = seeded_db_with_exemplars
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_exemplars_vm(
            conn, session_date="2024-02-02",
        )
    finally:
        conn.close()

    # All three banner fields exist on the VM dataclass.
    assert hasattr(vm, "unresolved_material_discrepancies_count")
    assert hasattr(vm, "recent_multi_leg_auto_correction_count")
    assert hasattr(vm, "banner_resolve_link")

    # Default values are well-formed (>= 0 + None or string).
    assert vm.unresolved_material_discrepancies_count >= 0
    assert vm.recent_multi_leg_auto_correction_count >= 0
    assert vm.banner_resolve_link is None or isinstance(
        vm.banner_resolve_link, str,
    )


# ---------------------------------------------------------------------------
# HTMX failure-surface defenses (CLAUDE.md gotcha family).
# ---------------------------------------------------------------------------


def test_template_includes_hx_headers_propagation(seeded_db_with_exemplars):
    """Phase 5 R1 M1: embedded forms MUST carry
    hx-headers='{"HX-Request": "true"}' so OriginGuard strict-mode accepts.
    """
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/exemplars")
    assert r.status_code == 200
    # Every action <form> in the template carries the propagation hint.
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text


def test_hx_redirect_target_route_registered_in_app_routes(
    seeded_db_with_exemplars,
):
    """Phase 6 I3 lesson: HX-Redirect target MUST be a registered route.

    Asserts via ``app.routes`` membership rather than following the
    redirect — guards against the failure mode where TestClient verifies
    the header value but not target resolution.
    """
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)
    target = "/patterns/exemplars"
    registered_paths = {
        getattr(r, "path", None) for r in app.routes
    }
    assert target in registered_paths, (
        f"HX-Redirect target {target!r} not in app.routes; "
        f"registered: {sorted(p for p in registered_paths if p)}"
    )


def test_post_rejects_invalid_action(seeded_db_with_exemplars):
    """Unknown actions are rejected with 400 (defense vs malformed POSTs)."""
    cfg, cfg_path = seeded_db_with_exemplars
    app = create_app(cfg, cfg_path)
    conn = connect(cfg.paths.db_path)
    silver_id = exemplars_repo.list_exemplars(conn)[0].id
    conn.close()

    with TestClient(app) as client:
        r = client.post(
            f"/patterns/exemplars/{silver_id}/action",
            data={"action": "bogus_action_not_allowed"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400


def test_post_action_missing_exemplar_returns_404(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/patterns/exemplars/9999999/action",
            data={"action": "watch"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 404
