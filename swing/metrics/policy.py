"""Risk_policy LIVE vs AT-TRADE-TIME read split (plan §A.5 + §I.3).

Phase 10 dashboards read ``risk_policy`` at TWO different scopes per metric:

- **LIVE policy** via :func:`read_live_policy` — wraps
  :func:`swing.data.repos.risk_policy.get_active_policy`. Used for
  ``low_sample_size_threshold_class_*_n``, ``global_confidence_floor_n``,
  ``bootstrap_resample_count``, ``process_grade_weight_*``.
- **AT-TRADE-TIME policy** via :func:`read_at_trade_time_policy` — resolves
  ``trades.risk_policy_id_at_lock`` to the corresponding policy snapshot.
  Used for ``capital_floor_constant_dollars``, ``scratch_epsilon_R``, and
  any trade-grain metric needing policy-as-of-trade-time semantics.

Legacy trades with NULL stamp (pre-Phase-9) fall back to LIVE policy + a
``[legacy: pre-Phase-9 trade]`` annotation flag returned alongside the
policy via ``tuple[RiskPolicy, bool]`` where ``bool=True`` means
"fallback applied". Defensive fallback also covers orphaned ids (FK
should prevent in V1; still handled).

**Plan §A.5 signature deviation (banked in return report §5):** plan §A.5
spec'd the resolver signature as ``read_at_trade_time_policy(conn, *,
trade: Trade)``, but Phase 9 Sub-bundle A added ``risk_policy_id_at_lock``
as a *column* on ``trades`` without extending the :class:`Trade` dataclass
(``_TRADE_SELECT_COLS`` does not include the column). The Phase 10 V1
read-side stays decoupled from the dataclass shape by taking the stamp
``int | None`` directly; consumers fetch it via
:func:`get_trade_policy_id_stamp` or :func:`get_review_policy_id_stamp`.
Behavior parity preserved.
"""

from __future__ import annotations

import sqlite3

from swing.data.models import RiskPolicy
from swing.data.repos.risk_policy import get_active_policy, get_policy_by_id


def read_live_policy(conn: sqlite3.Connection) -> RiskPolicy:
    """Return the currently-active ``risk_policy`` row (``is_active=1``).

    Thin wrapper over
    :func:`swing.data.repos.risk_policy.get_active_policy` to provide a
    Phase-10-scoped name (per plan §A.5 split-policy lock).
    """
    return get_active_policy(conn)


def read_at_trade_time_policy(
    conn: sqlite3.Connection, *, policy_id_stamp: int | None,
) -> tuple[RiskPolicy, bool]:
    """Resolve a trade's at-lock policy stamp; fall back to LIVE on
    NULL or orphan.

    Returns ``(policy, fallback_applied)`` where ``fallback_applied=True``
    indicates the LIVE policy was used (either because the stamp was NULL
    — legacy pre-Phase-9 trade — or because the stamp pointed at a
    non-existent ``policy_id``). Downstream surfaces render the
    ``[legacy: pre-Phase-9 trade]`` annotation when ``fallback_applied``.

    Spec §A.5 edge case: legacy trades with ``risk_policy_id_at_lock IS
    NULL``. Phase 9 Sub-bundle A migration 0017 added the column NULLABLE
    so the resolution must handle NULL without crashing.
    """
    if policy_id_stamp is not None:
        resolved = get_policy_by_id(conn, policy_id_stamp)
        if resolved is not None:
            return (resolved, False)
        # Orphan: stamp present but row missing. Defensive fallback per
        # plan §A.5 (FK SHOULD prevent in V1; still handled for production
        # data integrity edges).
    return (read_live_policy(conn), True)


def read_at_review_time_policy(
    conn: sqlite3.Connection, *, policy_id_stamp: int | None,
) -> tuple[RiskPolicy, bool]:
    """Resolve a ``review_log.risk_policy_id_at_review_completion`` stamp;
    fall back to LIVE on NULL or orphan.

    Same contract as :func:`read_at_trade_time_policy` — used by Phase 6
    review-driven metrics that need the policy in effect at review
    completion (e.g., process_grade weights as of the review timestamp).
    """
    return read_at_trade_time_policy(conn, policy_id_stamp=policy_id_stamp)


def get_trade_policy_id_stamp(
    conn: sqlite3.Connection, *, trade_id: int,
) -> int | None:
    """Read the ``risk_policy_id_at_lock`` column for a single trade.

    Convenience accessor for Sub-bundle B consumers that need to feed
    :func:`read_at_trade_time_policy` from a ``trades.id`` (since the
    :class:`Trade` dataclass does not carry the stamp — plan §A.5
    signature deviation, see module docstring).

    Returns ``None`` when:
      - the trade row does not exist (unusual; caller should pre-validate);
      - the trade row exists but ``risk_policy_id_at_lock IS NULL``
        (legacy pre-Phase-9 trade).
    """
    row = conn.execute(
        "SELECT risk_policy_id_at_lock FROM trades WHERE id = ?",
        (trade_id,),
    ).fetchone()
    if row is None:
        return None
    return row[0]


def get_review_policy_id_stamp(
    conn: sqlite3.Connection, *, review_id: int,
) -> int | None:
    """Read ``review_log.risk_policy_id_at_review_completion`` for a
    single review row.

    Mirror of :func:`get_trade_policy_id_stamp` for the review_log table.
    """
    row = conn.execute(
        "SELECT risk_policy_id_at_review_completion FROM review_log "
        "WHERE review_id = ?",
        (review_id,),
    ).fetchone()
    if row is None:
        return None
    return row[0]
