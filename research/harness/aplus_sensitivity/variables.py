"""Variable enumeration for the A+ criteria sensitivity sweep.

Surveys ``swing.config.Config`` for all per-criterion thresholds gated by
``bucket_for`` (``swing/evaluation/scoring.py``) and emits one ``SweepVariable``
per dial. Sweep ranges follow first-order heuristics keyed off the
variable's kind (multiplicative for ratios/percentages; additive for counts).

Per Phase 13 T4.SB §B.1 spec + R2 LOCK: exactly 17 variables (2 gate + 15
threshold). The ``kind`` taxonomy is ``{"gate", "threshold_additive",
"threshold_multiplicative"}`` and propagates through ``SweepEntry``, the CSV
serializer header column list, the markdown matrix Kind column, and the
discriminating tests per Expansion #11 taxonomy-propagation discipline.
"""
from __future__ import annotations

from dataclasses import dataclass

from swing.config import Config

_ALLOWED_KINDS: frozenset[str] = frozenset(
    {"gate", "threshold_additive", "threshold_multiplicative"}
)


@dataclass(frozen=True)
class SweepVariable:
    """One dial in the sensitivity sweep.

    ``kind`` is one of {"gate", "threshold_additive", "threshold_multiplicative"}.
    Runtime-validated in ``__post_init__`` because ``Literal[...]`` type hints
    are not enforced at runtime (per cumulative CLAUDE.md gotcha).
    """

    name: str
    kind: str
    current_value: float | int
    sweep_points: tuple[float | int, ...]

    def __post_init__(self) -> None:
        if self.kind not in _ALLOWED_KINDS:
            raise ValueError(
                f"SweepVariable.kind must be one of {sorted(_ALLOWED_KINDS)}, "
                f"got {self.kind!r}"
            )


_MULTIPLICATIVE_FACTORS = (0.5, 0.75, 1.0, 1.25, 1.5)


def _multiplicative_sweep(current: float) -> tuple[float, ...]:
    return tuple(round(current * f, 6) for f in _MULTIPLICATIVE_FACTORS)


def _additive_sweep(current: int, delta: int = 2) -> tuple[int, ...]:
    return tuple(sorted({max(0, current + d) for d in range(-delta, delta + 1)}))


def enumerate_variables(cfg: Config) -> tuple[SweepVariable, ...]:
    """Enumerate all 17 sweep variables against the cfg shape at
    ``swing/config.py`` (TrendTemplate, VCP, Risk, RS dataclasses).

    Includes 2 gate variables (``trend_template.min_passes``;
    ``vcp.watch_max_fails``) + 15 threshold variables:

      - 3 trend_template numerics (rising_ma_period_days +
        high_52w_margin_pct + low_52w_min_pct)
      - 8 vcp numerics
      - 1 risk numeric
      - 3 rs numerics

    NOT enumerated (V1):

      - ``cfg.trend_template.allowed_miss_names`` (tuple-set; sweeping over
        set-membership is V2 because it's not a numeric/additive grid)
      - ``cfg.rs.benchmark_ticker`` (string identifier, not a threshold)

    For threshold variables under V1, sweep_points are ENUMERATED but
    ``_bucket_for_substituted`` returns ``persisted_bucket`` for them
    (parity-preserving). The output formatter MUST surface this distinction
    explicitly via the ``kind`` column + per-row notes.
    """
    variables: list[SweepVariable] = [
        # Two gate variables (V1 full bucket-level resimulation supported).
        SweepVariable(
            name="trend_template.min_passes",
            kind="gate",
            current_value=cfg.trend_template.min_passes,
            sweep_points=_additive_sweep(cfg.trend_template.min_passes),
        ),
        SweepVariable(
            name="vcp.watch_max_fails",
            kind="gate",
            # bucket_for at swing/evaluation/scoring.py:35 hardcodes watch_max_fails=2.
            current_value=2,
            sweep_points=_additive_sweep(2, delta=2),
        ),
        # Trend-template numeric thresholds (3; not 4 -- min_passes is a
        # gate var above; allowed_miss_names is V2 set-sweep).
        SweepVariable(
            name="trend_template.rising_ma_period_days",
            kind="threshold_additive",
            current_value=cfg.trend_template.rising_ma_period_days,
            sweep_points=_additive_sweep(
                cfg.trend_template.rising_ma_period_days, delta=10,
            ),
        ),
        SweepVariable(
            name="trend_template.high_52w_margin_pct",
            kind="threshold_multiplicative",
            current_value=cfg.trend_template.high_52w_margin_pct,
            sweep_points=_multiplicative_sweep(
                cfg.trend_template.high_52w_margin_pct,
            ),
        ),
        SweepVariable(
            name="trend_template.low_52w_min_pct",
            kind="threshold_multiplicative",
            current_value=cfg.trend_template.low_52w_min_pct,
            sweep_points=_multiplicative_sweep(
                cfg.trend_template.low_52w_min_pct,
            ),
        ),
        # VCP numeric thresholds (8).
        SweepVariable(
            name="vcp.prior_trend_min_pct",
            kind="threshold_multiplicative",
            current_value=cfg.vcp.prior_trend_min_pct,
            sweep_points=_multiplicative_sweep(cfg.vcp.prior_trend_min_pct),
        ),
        SweepVariable(
            name="vcp.adr_min_pct",
            kind="threshold_multiplicative",
            current_value=cfg.vcp.adr_min_pct,
            sweep_points=_multiplicative_sweep(cfg.vcp.adr_min_pct),
        ),
        SweepVariable(
            name="vcp.pullback_max_pct",
            kind="threshold_multiplicative",
            current_value=cfg.vcp.pullback_max_pct,
            sweep_points=_multiplicative_sweep(cfg.vcp.pullback_max_pct),
        ),
        SweepVariable(
            name="vcp.proximity_max_pct",
            kind="threshold_multiplicative",
            current_value=cfg.vcp.proximity_max_pct,
            sweep_points=_multiplicative_sweep(cfg.vcp.proximity_max_pct),
        ),
        SweepVariable(
            name="vcp.tightness_days_required",
            kind="threshold_additive",
            current_value=cfg.vcp.tightness_days_required,
            sweep_points=_additive_sweep(cfg.vcp.tightness_days_required),
        ),
        SweepVariable(
            name="vcp.tightness_range_factor",
            kind="threshold_multiplicative",
            current_value=cfg.vcp.tightness_range_factor,
            sweep_points=_multiplicative_sweep(cfg.vcp.tightness_range_factor),
        ),
        SweepVariable(
            name="vcp.orderliness_max_bar_ratio",
            kind="threshold_multiplicative",
            current_value=cfg.vcp.orderliness_max_bar_ratio,
            sweep_points=_multiplicative_sweep(cfg.vcp.orderliness_max_bar_ratio),
        ),
        SweepVariable(
            name="vcp.orderliness_max_range_cv",
            kind="threshold_multiplicative",
            current_value=cfg.vcp.orderliness_max_range_cv,
            sweep_points=_multiplicative_sweep(cfg.vcp.orderliness_max_range_cv),
        ),
        # Risk numeric threshold (1).
        SweepVariable(
            name="risk.max_risk_pct",
            kind="threshold_multiplicative",
            current_value=cfg.risk.max_risk_pct,
            sweep_points=_multiplicative_sweep(cfg.risk.max_risk_pct),
        ),
        # RS numeric thresholds (3).
        SweepVariable(
            name="rs.horizon_weeks",
            kind="threshold_additive",
            current_value=cfg.rs.horizon_weeks,
            sweep_points=_additive_sweep(cfg.rs.horizon_weeks),
        ),
        SweepVariable(
            name="rs.rs_rank_min_pass",
            kind="threshold_additive",
            current_value=cfg.rs.rs_rank_min_pass,
            sweep_points=_additive_sweep(cfg.rs.rs_rank_min_pass, delta=10),
        ),
        SweepVariable(
            name="rs.fallback_extreme_pct",
            kind="threshold_multiplicative",
            current_value=cfg.rs.fallback_extreme_pct,
            sweep_points=_multiplicative_sweep(cfg.rs.fallback_extreme_pct),
        ),
    ]
    return tuple(variables)
