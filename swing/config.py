"""Config loader — reads swing.config.toml into dataclasses, resolves paths."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


@dataclass(frozen=True)
class Paths:
    db_path: Path
    data_dir: Path
    logs_dir: Path
    charts_dir: Path
    backups_dir: Path
    prices_cache_dir: Path
    finviz_inbox_dir: Path
    exports_dir: Path
    rs_universe_path: Path


@dataclass(frozen=True)
class Account:
    starting_equity: float
    starting_date: str
    risk_equity_floor: float


@dataclass(frozen=True)
class PositionLimits:
    soft_warn_open: int
    hard_cap_open: int


@dataclass(frozen=True)
class Risk:
    max_risk_pct: float


@dataclass(frozen=True)
class VCP:
    prior_trend_min_pct: float
    adr_min_pct: float
    pullback_max_pct: float
    proximity_max_pct: float
    tightness_days_required: int
    tightness_range_factor: float
    orderliness_max_bar_ratio: float
    orderliness_max_range_cv: float


@dataclass(frozen=True)
class TrendTemplate:
    min_passes: int
    allowed_miss_names: tuple[str, ...]
    rising_ma_period_days: int
    high_52w_margin_pct: float
    low_52w_min_pct: float


@dataclass(frozen=True)
class RS:
    horizon_weeks: int
    benchmark_ticker: str
    rs_rank_min_pass: int
    fallback_extreme_pct: float


@dataclass(frozen=True)
class ETFExclusion:
    exclude_etfs: bool
    manual_block: tuple[str, ...]
    manual_allow: tuple[str, ...]


@dataclass(frozen=True)
class FocusRanking:
    closeness_to_pivot: float
    adr: float
    prior_trend: float


@dataclass(frozen=True)
class NearTriggerConfig:
    above_pct: float = 0.5
    below_pct: float = 1.0


@dataclass(frozen=True)
class StopAdvisoryConfig:
    breakeven_r_trigger: float = 1.0
    trail_10ma_buffer_pct: float = 0.3
    trail_20ma_buffer_pct: float = 0.3
    time_stop_days: int = 10
    time_stop_min_r: float = 0.5


@dataclass(frozen=True)
class SizingConfig:
    """Position-sizing caps (spec §4, legacy parity)."""
    position_pct_cap: float = 0.15


@dataclass(frozen=True)
class PipelineConfig:
    stale_lease_threshold_seconds: int = 300
    stale_step_threshold_seconds: int = 900
    heartbeat_interval_seconds: int = 30
    block_if_running_within_seconds: int = 120
    staging_orphan_age_seconds: int = 3600
    prev_dir_retention_days: int = 7
    chart_top_n_watch: int = 5


@dataclass(frozen=True)
class ExportConfig:
    size_cap_kb: int = 500
    retain_markdown_sibling: bool = True
    retention_days: int = 90
    archive_compression_format: str = "zip"


@dataclass(frozen=True)
class Web:
    host: str = "127.0.0.1"
    port: int = 8080
    reload: bool = False
    price_cache_ttl_seconds: int = 120
    price_fetch_timeout_seconds: int = 3
    price_fetch_deadline_seconds: int = 6
    max_concurrent_price_fetches: int = 8
    circuit_breaker_cooldown_seconds: int = 60
    polling_interval_seconds: int = 2


@dataclass(frozen=True)
class Config:
    paths: Paths
    account: Account
    position_limits: PositionLimits
    risk: Risk
    vcp: VCP
    trend_template: TrendTemplate
    rs: RS
    etf_exclusion: ETFExclusion
    focus_ranking: FocusRanking
    near_trigger: NearTriggerConfig
    stop_advisory: StopAdvisoryConfig
    sizing: SizingConfig
    pipeline: PipelineConfig
    export: ExportConfig
    web: Web = field(default_factory=Web)


_PROJECT_INTERNAL_PREFIXES = ("data/", "exports/", "reference/")


def _user_home() -> Path:
    """Windows USERPROFILE, fallback to HOME."""
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _resolve_path(raw: str, home: Path, project_root: Path) -> Path:
    """Absolute paths pass through; project-internal paths resolve against project_root; else home."""
    p = Path(raw)
    if p.is_absolute():
        return p
    normalized = raw.replace("\\", "/")
    if normalized.startswith(_PROJECT_INTERNAL_PREFIXES) or normalized in ("exports", "data", "reference"):
        return project_root / p
    return home / p


def load(config_path: Path) -> Config:
    """Load and validate a swing.config.toml file."""
    project_root = config_path.parent.resolve()
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    required_sections = (
        "paths", "account", "position_limits", "risk", "vcp",
        "trend_template", "rs", "etf_exclusion", "focus_ranking",
    )
    for section in required_sections:
        if section not in raw:
            raise KeyError(f"swing.config.toml missing required section: [{section}]")

    home = _user_home()
    p = raw["paths"]
    paths = Paths(
        db_path=_resolve_path(p["db_path"], home, project_root),
        data_dir=_resolve_path(p["data_dir"], home, project_root),
        logs_dir=_resolve_path(p["logs_dir"], home, project_root),
        charts_dir=_resolve_path(p["charts_dir"], home, project_root),
        backups_dir=_resolve_path(p["backups_dir"], home, project_root),
        prices_cache_dir=_resolve_path(p["prices_cache_dir"], home, project_root),
        finviz_inbox_dir=_resolve_path(p["finviz_inbox_dir"], home, project_root),
        exports_dir=_resolve_path(p["exports_dir"], home, project_root),
        rs_universe_path=_resolve_path(p["rs_universe_path"], home, project_root),
    )

    return Config(
        paths=paths,
        account=Account(**raw["account"]),
        position_limits=PositionLimits(**raw["position_limits"]),
        risk=Risk(**raw["risk"]),
        vcp=VCP(**raw["vcp"]),
        trend_template=TrendTemplate(
            min_passes=raw["trend_template"]["min_passes"],
            allowed_miss_names=tuple(raw["trend_template"]["allowed_miss_names"]),
            rising_ma_period_days=raw["trend_template"]["rising_ma_period_days"],
            high_52w_margin_pct=raw["trend_template"]["high_52w_margin_pct"],
            low_52w_min_pct=raw["trend_template"]["low_52w_min_pct"],
        ),
        rs=RS(**raw["rs"]),
        etf_exclusion=ETFExclusion(
            exclude_etfs=raw["etf_exclusion"]["exclude_etfs"],
            manual_block=tuple(raw["etf_exclusion"]["manual_block"]),
            manual_allow=tuple(raw["etf_exclusion"]["manual_allow"]),
        ),
        focus_ranking=FocusRanking(**raw["focus_ranking"]),
        near_trigger=NearTriggerConfig(**raw.get("near_trigger", {})),
        stop_advisory=StopAdvisoryConfig(**raw.get("stop_advisory", {})),
        sizing=SizingConfig(**raw.get("sizing", {})),
        pipeline=PipelineConfig(**raw.get("pipeline", {})),
        export=ExportConfig(**raw.get("export", {})),
        web=Web(**raw.get("web", {})),
    )
