"""Frozen doctrine-defensible miss set membership (pre-registered at D1).

The membership of ``DEFENSIBLE_MISS_SET`` is locked by D1 of the study
(``research/studies/finviz-pool-binding-constraints.md``). It must not be
modified post-data; D5 adversarial-review fixes can clarify framing but
cannot move set membership.

If any future study revisits this set, it should do so in its OWN D1
pre-registration, not by mutating the constant here.
"""
from __future__ import annotations

#: Criteria designated "doctrine-defensible" — failing one of these alone
#: does NOT necessarily mean "the setup doesn't exist"; it may instead
#: represent an operationally-tractable circumstance with a doctrine-
#: aligned response. See D1 §"Doctrine-defensible miss set" for full
#: rationale per criterion.
DEFENSIBLE_MISS_SET: frozenset[str] = frozenset(
    {
        "TT8_rs_rank",        # production allowed_miss; listed for completeness
        "risk_feasibility",   # capital-blocked; not bindable on watch bucket
        "proximity_20ma",     # timing/extension miss; stage-for-re-entry
    }
)

#: Criteria designated "doctrine-incompatible" — failing them means the
#: setup is not present. Listed verbatim from D1.
DOCTRINE_INCOMPATIBLE_SET: frozenset[str] = frozenset(
    {
        "TT1_above_150_200",
        "TT2_150_above_200",
        "TT3_200_rising",
        "TT4_50_above_150_200",
        "TT5_above_50",
        "TT6_above_52w_low_30pct",
        "TT7_within_52w_high_25pct",
        "ma_stack_10_20_50",
        "ma_short_rising",
        "prior_trend",
        "adr",
        "pullback",
        "tightness",
        "vcp_volume_contraction",
        "orderliness",
    }
)
