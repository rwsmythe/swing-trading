"""risk_policy service layer — supersession + cfg-cascade + TOML divergence detection.

Phase 9 spec §3.1.3 + §4.1; plan §A.5.1 (post-schema-validation hook).

Transactional contract (per dispatch brief §0.3 #5 + Phase 8 R3→R4 lesson —
"reject + simple contract over auto-detect + complicate"; CLAUDE.md gotcha
"in_transaction auto-detect re-introduces the very race the explicit lock
was meant to close"): caller MUST NOT hold an open transaction; function
ALWAYS owns ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``; rejects (does
NOT auto-detect) caller-held transactions.

Public API:
  - ``supersede_active_policy(conn, *, field_updates, notes, source) -> int``
    — 6-step transactional sequence per spec §4.1; rejects caller-held tx;
    returns new policy_id.
  - ``read_active_policy(conn) -> RiskPolicy`` — read-only delegate.
  - ``check_and_reconcile_toml_divergence(conn, cfg) -> tuple[Config, dict | None]``
    — startup hook called AFTER ``ensure_schema``; returns corrected immutable
    Config via ``dataclasses.replace`` + divergence dict when divergent;
    returns ``(cfg, None)`` for pre-v17 / no-active-policy fixtures (per
    Codex R3 M#1 architectural fix in plan §A.5.1).
  - ``seed_initial_policy(conn, cfg) -> int`` — idempotent fall-back when
    the migration seed is missing (test fixture wipes / fresh DBs).
"""
from __future__ import annotations

import dataclasses
import logging
import sqlite3
from typing import Any, Literal

from swing.data.datetime_helpers import now_ms
from swing.data.models import RiskPolicy
from swing.data.repos import risk_policy as repo

logger = logging.getLogger(__name__)


# Whitelist of fields a service caller may pass through ``field_updates``.
# Excludes the 6 metadata + supersession columns that are server-stamped at
# supersession time per dispatch brief §0.3 #9 + spec §A.10:
# policy_id (auto-PK), effective_from (now_ms), effective_to (None on
# successor), is_active (1 on successor), superseded_by_policy_id (None on
# successor; set in step 5 of §4.1), created_at (now_ms).
# ``policy_notes`` IS allowed because it's the operator-supplied rationale
# free-text. (Test ``test_supersede_rejects_pk_or_metadata_field`` pins
# this whitelist boundary.)
_VALID_FIELDS: frozenset[str] = frozenset({
    "max_account_risk_per_trade_pct", "max_concurrent_positions",
    "max_portfolio_heat_pct", "max_sector_concentration_positions",
    "consecutive_losses_pause_threshold", "consecutive_losses_pause_action",
    "consecutive_losses_streak_reset", "drawdown_circuit_breaker_enabled",
    "drawdown_pause_threshold_R", "drawdown_pause_action",
    "drawdown_size_reduction_pct", "drawdown_recovery_threshold_R",
    "capital_floor_constant_dollars", "scratch_epsilon_R",
    "review_lag_threshold_days",
    "low_sample_size_threshold_class_a_n",
    "low_sample_size_threshold_class_b_n",
    "low_sample_size_threshold_class_c_n",
    "low_sample_size_threshold_class_d_n",
    "global_confidence_floor_n", "bootstrap_resample_count",
    "process_grade_weight_entry", "process_grade_weight_management",
    "process_grade_weight_exit", "mfe_mae_default_precision_level",
    "trail_MA_period_days", "trail_MA_post_2R_period_days",
    "policy_notes",
})


class CallerHeldTransactionError(RuntimeError):
    """Raised when a caller invokes a single-transaction service while
    holding an open transaction.

    Phase 8 R3→R4 lesson + CLAUDE.md gotcha "in_transaction auto-detect
    outer transaction guards re-introduce the very race the explicit lock
    was meant to close": single-transaction services own BEGIN IMMEDIATE /
    COMMIT / ROLLBACK; they REJECT caller-held transactions rather than
    silently auto-detecting (auto-detect is the failure mode).
    """


def supersede_active_policy(
    conn: sqlite3.Connection,
    *,
    field_updates: dict[str, Any],
    notes: str | None = None,
    source: Literal["cli", "cfg_cascade", "import_from_toml"] = "cli",
) -> int:
    """6-step supersession sequence per spec §4.1.

    Args:
        conn: SQLite connection. Caller MUST NOT hold an open transaction.
        field_updates: dict of risk_policy column -> new value. Unspecified
            fields are copied from the predecessor row. Metadata + PK
            columns are NOT allowed (see ``_VALID_FIELDS``).
        notes: optional operator free-text rationale stored in
            ``policy_notes``. Overrides any ``policy_notes`` in
            ``field_updates``.
        source: provenance tag. When ``cfg_cascade`` and ``notes`` is None,
            ``policy_notes`` defaults to "auto-cascade from
            cfg.account.risk_equity_floor edit" (spec §3.1.3 R3 Minor #2
            audit-trail discoverability).

    Returns:
        Newly-inserted policy_id.

    Raises:
        CallerHeldTransactionError: caller holds an open transaction.
        ValueError: ``field_updates`` contains a non-whitelisted column,
            OR the constructed ``RiskPolicy.__post_init__`` validator
            rejects the merged values.
        RuntimeError: no active policy row found (schema corrupted or seed
            missing — the migration normally guarantees seed presence).
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "supersede_active_policy owns its own transaction; caller MUST "
            "NOT hold an open transaction. See dispatch-brief §0.3 #5 + "
            "CLAUDE.md gotcha 'Service-layer with conn:' + 'in_transaction "
            "auto-detect outer transaction guards re-introduce the very "
            "race the explicit lock was meant to close'."
        )

    invalid = set(field_updates) - _VALID_FIELDS
    if invalid:
        raise ValueError(
            "field_updates contains key(s) not a risk_policy field "
            f"(or PK/metadata field server-stamped at supersession): "
            f"{sorted(invalid)}"
        )

    try:
        conn.execute("BEGIN IMMEDIATE")
        # Step 1: identify predecessor by exact PK (Phase 8 R3 M3 lesson —
        # capture PK rather than relying on uniqueness slot at later steps).
        cur = conn.execute(
            "SELECT policy_id FROM risk_policy WHERE is_active = 1"
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(
                "No active risk_policy row — schema corrupted or seed missing"
            )
        predecessor_id = row[0]
        predecessor = repo.get_policy_by_id(conn, policy_id=predecessor_id)
        # Repo returned a Policy because we just selected it — guard for
        # type-checkers; data integrity ensures non-None.
        assert predecessor is not None

        # Bind once: timestamps for both rows must match the same instant
        # (spec §3.1.3 R4 Minor #1 — single utcnow bind avoids second-
        # boundary skew). now_ms() already does the single bind internally.
        ts = now_ms()

        # Step 2: flag predecessor is_active=0 + effective_to=ts (frees the
        # ux_risk_policy_active partial-unique slot BEFORE successor INSERT;
        # superseded_by_policy_id stays None — set in step 5 once successor
        # PK is known per spec §4.1 6-step sequence + Phase 8 R2 dual-column
        # lesson).
        repo.update_policy_active_flag(
            conn,
            policy_id=predecessor_id,
            is_active=0,
            effective_to=ts,
            superseded_by_policy_id=None,
        )

        # Step 3: build successor field set (copy predecessor, apply
        # field_updates overlay, set timeline + activity columns).
        successor_fields = predecessor.field_copy_excluding_pk_and_timeline()
        successor_fields.update(field_updates)
        successor_fields["effective_from"] = ts
        successor_fields["effective_to"] = None
        successor_fields["is_active"] = 1
        successor_fields["superseded_by_policy_id"] = None
        successor_fields["created_at"] = ts
        if notes is not None:
            successor_fields["policy_notes"] = notes
        elif source == "cfg_cascade" and (
            successor_fields.get("policy_notes") is None
            or successor_fields.get("policy_notes")
            == predecessor.policy_notes
        ):
            successor_fields["policy_notes"] = (
                "auto-cascade from cfg.account.risk_equity_floor edit"
            )

        # Step 4 (validation): construct RiskPolicy to fire __post_init__
        # validator (NaN/inf, enum, drawdown sign convention, sum-to-1.0
        # cross-field). policy_id is a placeholder — discarded; the actual
        # PK is auto-assigned by INSERT. Validator failure rolls back via
        # the outer try/except.
        RiskPolicy(policy_id=0, **successor_fields)

        # Step 4 (write): INSERT successor; capture new policy_id.
        successor_id = repo.insert_policy(conn, **successor_fields)

        # Step 5: UPDATE predecessor.superseded_by_policy_id = successor_id
        # (audit-chain pointer; the partial-unique slot is already free
        # from step 2 so this UPDATE doesn't violate ux_risk_policy_active).
        repo.update_policy_active_flag(
            conn,
            policy_id=predecessor_id,
            is_active=0,
            effective_to=ts,
            superseded_by_policy_id=successor_id,
        )

        # Step 6: COMMIT.
        conn.commit()
        return successor_id
    except Exception:
        conn.rollback()
        raise


def read_active_policy(conn: sqlite3.Connection) -> RiskPolicy:
    """Read-only delegate to ``repo.get_active_policy``.

    Service-layer indirection lets future callers route every read through
    the service (e.g., for caching, instrumentation, divergence-warning
    surface) without touching repo callers.
    """
    return repo.get_active_policy(conn)


def check_and_reconcile_toml_divergence(
    conn: sqlite3.Connection, cfg, *, silent: bool = False,
) -> tuple[object, dict | None]:
    """Post-schema-validation startup hook (plan §A.5.1; Codex R3 M#1).

    Called from CLI command handlers + web app lifespan AFTER
    ``ensure_schema(conn)`` has brought the DB to v17.

    Behavior:
      - Reads ``schema_version`` first; if pre-v17, returns ``(cfg, None)``
        silently (db-migrate path that brings DB to v17 must NOT trigger a
        check that depends on the very table the migration creates).
      - Reads the active risk_policy row; if absent (test fixture wipe,
        fresh DB pre-seed), returns ``(cfg, None)`` silently.
      - Compares ``cfg.account.risk_equity_floor`` to
        ``risk_policy.capital_floor_constant_dollars`` (the ONE field with
        a Phase-5-surfaced cfg counterpart per spec §3.1.3).
      - If equal within ±1e-9, returns ``(cfg, None)``.
      - If divergent: logs WARNING, builds a corrected immutable Config
        via ``dataclasses.replace`` (Config + Account are frozen so
        in-place mutation would raise ``FrozenInstanceError``), returns
        ``(new_cfg, divergence_dict)``. Original ``cfg`` is unchanged.

    The TOML file on disk is NEVER modified by this helper. To make a
    hand-edited TOML edit canonical, the operator runs the explicit CLI
    ``swing config policy import-from-toml --field <name>`` (T-A.6).

    The ``swing db-migrate`` CLI command explicitly SKIPS this helper (it's
    the path that brings DB to v17; running divergence check before v17 is
    reached is the failure mode the schema-version check above guards
    against, but the CLI handler ALSO skips defensively).

    Returns:
        ``(new_cfg, divergence_or_None)``. ``new_cfg is cfg`` (identity)
        when no divergence; a fresh Config when divergent.
    """
    # Schema-version gate — only proceed past v17. Codex R5 Minor #1 fix
    # (inherited from plan §A.5.1): narrow exception catch + explicit gate
    # rather than blanket ``sqlite3.OperationalError`` catch (which would
    # mask legitimate post-v17 failures like a DB lock or missing column).
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='schema_version'"
        )
        if cur.fetchone() is None:
            return cfg, None
        row = conn.execute("SELECT version FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        # Concurrency or transient I/O — skip silently rather than block
        # startup. The next startup attempt runs the check again.
        return cfg, None
    if row is None or row[0] < 17:
        return cfg, None

    # Active-policy read; absent (test fixture pre-seed) → silent skip.
    try:
        active = repo.get_active_policy(conn)
    except repo.NoActivePolicyError:
        return cfg, None

    toml_v = cfg.account.risk_equity_floor
    policy_v = active.capital_floor_constant_dollars
    if abs(toml_v - policy_v) < 1e-9:
        return cfg, None

    if not silent:
        # Codex R2 Minor #1: ``silent=True`` is used by the per-render
        # /config-page divergence probe so persistent hand-edit divergence
        # doesn't spam logs on every refresh. Startup hooks (CLI / web
        # lifespan) keep the default ``silent=False`` so the warning fires
        # exactly once at process start.
        logger.warning(
            "TOML diverges from risk_policy: "
            "cfg.account.risk_equity_floor=%s vs "
            "risk_policy.capital_floor_constant_dollars=%s; risk_policy is "
            "authoritative. To make TOML canonical, run: "
            "swing config policy import-from-toml --field capital_floor_constant_dollars",
            toml_v, policy_v,
        )
    new_account = dataclasses.replace(
        cfg.account, risk_equity_floor=policy_v,
    )
    new_cfg = dataclasses.replace(cfg, account=new_account)
    divergence = {
        "field": "capital_floor_constant_dollars",
        "toml_value": toml_v,
        "policy_value": policy_v,
    }
    return new_cfg, divergence


def ratify_seed_from_cfg_on_v17_landing(
    conn: sqlite3.Connection, cfg,
) -> int | None:
    """Codex R1 Major #1 fix — ratify the migration's hard-coded seed
    against the operator's actual cfg values immediately after the
    v16 → v17 transition.

    Spec §3.1.3 SEED MAP requires four fields to come from cfg:
      - max_account_risk_per_trade_pct = cfg.risk.max_risk_pct × 100
      - max_concurrent_positions      = cfg.position_limits.hard_cap_open
      - capital_floor_constant_dollars = cfg.account.risk_equity_floor
      - review_lag_threshold_days     = cfg.review.review_window_days

    The migration's executescript path cannot Python-eval cfg, so the
    initial INSERT uses conservative hard-coded defaults that match the
    SHIPPED swing.config.toml values. This helper fires once at the
    v16→v17 landing to overwrite those defaults with the operator's
    actual values via supersede_active_policy.

    Idempotent within a single migration run — only fires when the
    db_migrate CLI handler detects pre_version <= 16 AND post_version >= 17.

    Returns:
        New policy_id (after supersession) when at least one mirrored
        field differs from the migration's hard-coded seed; ``None``
        when all 4 fields already agree (no supersession needed).
    """
    try:
        active = repo.get_active_policy(conn)
    except repo.NoActivePolicyError:
        # Defensive — migration should have seeded policy_id=1.
        return None

    cfg_derived = {
        "max_account_risk_per_trade_pct": cfg.risk.max_risk_pct * 100.0,
        "max_concurrent_positions": cfg.position_limits.hard_cap_open,
        "capital_floor_constant_dollars": cfg.account.risk_equity_floor,
    }
    if hasattr(cfg, "review"):
        cfg_derived["review_lag_threshold_days"] = (
            cfg.review.review_window_days
        )

    field_updates: dict[str, object] = {}
    for field, cfg_value in cfg_derived.items():
        active_value = getattr(active, field)
        if isinstance(cfg_value, float):
            if abs(active_value - cfg_value) >= 1e-9:
                field_updates[field] = cfg_value
        elif active_value != cfg_value:
            field_updates[field] = cfg_value

    if not field_updates:
        return None

    field_updates["policy_notes"] = (
        "auto-ratified from swing.config.toml at Phase 9 v16→v17 "
        "db-migrate landing (per spec §3.1.3 SEED MAP)"
    )
    return supersede_active_policy(
        conn,
        field_updates=field_updates,
        source="cfg_cascade",
    )


def seed_initial_policy(conn: sqlite3.Connection, cfg) -> int:
    """Idempotent seed fall-back. Called from test fixtures or repair
    paths when the migration seed is missing (post-wipe, fresh fixture).

    Returns:
        ``policy_id`` of the existing active row OR the freshly inserted
        seed row.
    """
    try:
        active = repo.get_active_policy(conn)
        return active.policy_id
    except repo.NoActivePolicyError:
        pass

    # No active row; insert from cfg defaults. Use the same constants the
    # migration 0017 seed uses so production + fall-back parity holds.
    # (Spec §3.1.3 seed map.)
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "seed_initial_policy owns its own transaction; caller MUST NOT "
            "hold an open transaction."
        )
    try:
        conn.execute("BEGIN IMMEDIATE")
        ts = now_ms()
        new_id = repo.insert_policy(
            conn,
            effective_from=ts,
            effective_to=None,
            is_active=1,
            superseded_by_policy_id=None,
            created_at=ts,
            policy_notes=(
                "Phase 9 seed via seed_initial_policy fall-back from "
                "swing.config.toml defaults"
            ),
            max_account_risk_per_trade_pct=0.50,
            max_concurrent_positions=cfg.position_limits.hard_cap_open,
            max_portfolio_heat_pct=3.0,
            max_sector_concentration_positions=3,
            consecutive_losses_pause_threshold=3,
            consecutive_losses_pause_action="review_required",
            consecutive_losses_streak_reset="review_completed",
            drawdown_circuit_breaker_enabled=0,
            drawdown_pause_threshold_R=None,
            drawdown_pause_action=None,
            drawdown_size_reduction_pct=None,
            drawdown_recovery_threshold_R=None,
            capital_floor_constant_dollars=cfg.account.risk_equity_floor,
            scratch_epsilon_R=0.10,
            review_lag_threshold_days=cfg.review.review_window_days
            if hasattr(cfg, "review") else 7,
            low_sample_size_threshold_class_a_n=3,
            low_sample_size_threshold_class_b_n=5,
            low_sample_size_threshold_class_c_n=5,
            low_sample_size_threshold_class_d_n=10,
            global_confidence_floor_n=20,
            bootstrap_resample_count=1000,
            process_grade_weight_entry=0.40,
            process_grade_weight_management=0.35,
            process_grade_weight_exit=0.25,
            mfe_mae_default_precision_level="daily_approximate",
            trail_MA_period_days=21,
            trail_MA_post_2R_period_days=None,
        )
        conn.commit()
        return new_id
    except Exception:
        conn.rollback()
        raise
