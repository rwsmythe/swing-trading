"""Phase 13 T2.SB6b T-A.6.5 — pattern_outcomes metric helper.

Per spec section 5.10 item 8 + plan G.9 T-A.6.5 + OQ-10 LOCK: 9th metric
tile composes with the Phase 10 cohort architecture + honesty.py
confidence-floor + Wilson-CI badge helpers. ADDITIVE on top of the
shipped 8 Phase 10 metric tiles + 1 umbrella `/metrics` navigator.

V1 outcome shape (per spec section 5.10 item 8):
  "of the last N similar-score candidates, X% triggered, Y% reached 1R,
   Z% hit stop"

Triggering proxy: pattern_exemplars rows with label_source in
(closed_loop_review, organic_trade_history, curated_gold) + final_decision
in (confirmed). All other final_decision rows count toward n but NOT k
(rejected/watch/relabeled are NOT "triggered").

1R + stop bucketing: defers to the trades table join. V2 candidate when
candidate-to-trade backlink semantics resolve (per spec section 5.10
forward-binding); V1 leaves the columns None when no trade pairing
exists for the pattern class.

Honesty: Wilson CI at n>=5 (class A threshold); suppressed at n<5.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from swing.data.models import DETECTOR_PATTERN_CLASSES, RiskPolicy
from swing.metrics.honesty import (
    HonestyClass,
    WilsonCI,
    suppress_for_n,
    wilson_ci,
)


@dataclass(frozen=True)
class PatternOutcomeRow:
    """One row of the 9th metric tile per spec section 5.10 item 8.

    Per-pattern-class outcome bucket; honesty.suppress_for_n suppression
    handled at builder boundary so the template renders a placeholder
    SuppressionRowVM at n<5 (per Phase 10 spec §5.6 + §A.7).
    """

    pattern_class: str
    n: int
    triggered_n: int
    triggered_ci: WilsonCI | None  # None when suppressed (n<5)
    triggered_pct_text: str  # rendered with Wilson CI bounds at n>=5
    reached_1r_n: int | None = None  # V1: None until trades backlink
    reached_1r_ci: WilsonCI | None = None
    hit_stop_n: int | None = None  # V1: None until trades backlink
    hit_stop_ci: WilsonCI | None = None
    suppressed_text: str | None = None  # populated at n<5 per spec §5.6


_TRIGGERING_LABEL_SOURCES: tuple[str, ...] = (
    "closed_loop_review",
    "organic_trade_history",
    "curated_gold",
)


def _count_triggering_n_k(
    conn: sqlite3.Connection, *, pattern_class: str,
) -> tuple[int, int]:
    """Return (n, k) where:
    - n = count of rows in TRIGGERING_LABEL_SOURCES for the class.
    - k = count of those rows with final_decision='confirmed'.
    """
    n_row = conn.execute(
        f"SELECT COUNT(*) FROM pattern_exemplars "
        f"WHERE proposed_pattern_class = ? "
        f"  AND label_source IN ({','.join('?' * len(_TRIGGERING_LABEL_SOURCES))})",
        (pattern_class, *_TRIGGERING_LABEL_SOURCES),
    ).fetchone()
    n = int(n_row[0]) if n_row else 0
    if n == 0:
        return (0, 0)
    k_row = conn.execute(
        f"SELECT COUNT(*) FROM pattern_exemplars "
        f"WHERE proposed_pattern_class = ? "
        f"  AND label_source IN ({','.join('?' * len(_TRIGGERING_LABEL_SOURCES))}) "
        f"  AND final_decision = 'confirmed'",
        (pattern_class, *_TRIGGERING_LABEL_SOURCES),
    ).fetchone()
    k = int(k_row[0]) if k_row else 0
    return (n, k)


def build_pattern_outcome_rows(
    conn: sqlite3.Connection, *, policy: RiskPolicy,
) -> list[PatternOutcomeRow]:
    """Build one row per detector pattern class per spec section 5.10 + OQ-10.

    Wilson CI populated at n>=class-A threshold (default 5); suppressed
    below.
    """
    rows: list[PatternOutcomeRow] = []
    for cls in DETECTOR_PATTERN_CLASSES:
        n, k = _count_triggering_n_k(conn, pattern_class=cls)
        suppressed = suppress_for_n(
            klass=HonestyClass.A, n=n, policy=policy,
            metric_name=f"pattern_outcomes_{cls}_triggered",
        )
        if suppressed is not None:
            rows.append(PatternOutcomeRow(
                pattern_class=cls,
                n=n,
                triggered_n=k,
                triggered_ci=None,
                triggered_pct_text="",
                suppressed_text=suppressed.placeholder_text,
            ))
            continue
        ci = wilson_ci(k=k, n=n)
        pct_text = (
            f"{ci.point * 100.0:.1f}pct triggered "
            f"(95pct CI {ci.lower * 100.0:.1f}-{ci.upper * 100.0:.1f}pct; "
            f"n={n})"
        )
        rows.append(PatternOutcomeRow(
            pattern_class=cls,
            n=n,
            triggered_n=k,
            triggered_ci=ci,
            triggered_pct_text=pct_text,
        ))
    return rows
