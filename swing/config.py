"""Config loader — reads swing.config.toml into dataclasses, resolves paths."""
from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


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
    # 3e.8 Bundle 2 (§4.B) — first-trim sell-into-strength advisory.
    # Operator locked R-multiple trigger (rationale: lowest-friction;
    # aligns with framework's existing R-multiple plumbing; DST D.2's
    # Day-3-5 calendar trigger banked for V2). Default 1.0R per §0.3 #1.
    trim_first_r_trigger: float = 1.0
    trim_first_pct_default: float = 0.25
    # 3e.8 Bundle 2 (§4.D) — parabolic-extension advisory; DST D.7 / Realsimpleariel
    # doctrine anchor. Fires when (current_price - sma50) / sma50 * 100 >=
    # parabolic_adr_multiple * adr_pct. Default 7.0× ADR per §0.3 #2.
    parabolic_adr_multiple: float = 7.0
    # 3e.8 Bundle 3 (§M.2) — R-multiple stop-tighten advisory; TLSMW Ch 13 p. 296
    # doctrine anchor ("when a stock advances 7-8% off the buy point — the
    # 20% scenario — the smart move is to lock in gains by raising the stop").
    # Fires when r_so_far(trade, current_price) >= tighten_at_r_multiple. Default
    # 2.0R is conservatively floored vs the 7%/20% example (=2.86R) per §0.3 #4.
    tighten_at_r_multiple: float = 2.0

    def __post_init__(self) -> None:
        # Codex R2 Major #1 + R3 Major #1 — validate Bundle 2 fields at
        # construction time. Pathological TOML overrides would otherwise emit
        # nonsensical advisories (negative-R trims, 150% trim percentages,
        # near-zero parabolic thresholds). R3 tightens: NaN/inf must also be
        # rejected — `nan <= 0` is False, so NaN sneaks past a bare `<= 0`
        # check and then `r < nan` is False, firing the advisory on every
        # untrimmed trade.
        import math as _math
        if not _math.isfinite(self.trim_first_r_trigger) or self.trim_first_r_trigger <= 0:
            raise ValueError(
                f"stop_advisory.trim_first_r_trigger must be a finite value > 0; got "
                f"{self.trim_first_r_trigger!r}"
            )
        if (
            not _math.isfinite(self.trim_first_pct_default)
            or not (0 < self.trim_first_pct_default <= 1)
        ):
            raise ValueError(
                f"stop_advisory.trim_first_pct_default must be a finite value in (0, 1]; got "
                f"{self.trim_first_pct_default!r}"
            )
        if not _math.isfinite(self.parabolic_adr_multiple) or self.parabolic_adr_multiple <= 0:
            raise ValueError(
                f"stop_advisory.parabolic_adr_multiple must be a finite value > 0; got "
                f"{self.parabolic_adr_multiple!r}"
            )
        # 3e.8 Bundle 3 (§M.2) — same NaN/inf/non-positive discipline as Bundle 2.
        # Pathological values would otherwise silently no-op the rule
        # (`r >= nan` is False) or fire spuriously (`r >= -1` is True at any R).
        if not _math.isfinite(self.tighten_at_r_multiple) or self.tighten_at_r_multiple <= 0:
            raise ValueError(
                f"stop_advisory.tighten_at_r_multiple must be a finite value > 0; got "
                f"{self.tighten_at_r_multiple!r}"
            )


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
    chart_top_n_watch: int = 10  # was 5; raised in chart-scope policy v2 (2026-04-27)
    # Phase 14 Sub-bundle 2 (OQ-18 LOCK): observe-step lifecycle windows
    # (trading sessions). Config-surfaced via [pipeline] in swing.config.toml
    # so they are tunable without a code change. A detection is tracked at
    # most ~(pending + post_trigger) = ~90 sessions.
    observe_max_pending_window_sessions: int = 30
    observe_max_post_trigger_window_sessions: int = 60
    # Pool-widening (2026-06-04) DORMANT relief levers (default None = OFF;
    # accept-and-measure -- a silent cap is forbidden, any drop emits a #27
    # audit). Lever 1: cap the watch detect pool (a future-growth limiter;
    # aplus is NEVER capped; >=1 when set). Lever 2: shorten the watch-origin
    # observe horizon (pending + post-trigger), falling back to the aplus
    # windows when None.
    detect_watch_pool_cap: int | None = None
    observe_max_pending_window_sessions_watch: int | None = None
    observe_max_post_trigger_window_sessions_watch: int | None = None

    def __post_init__(self) -> None:
        if (self.detect_watch_pool_cap is not None
                and self.detect_watch_pool_cap < 1):
            raise ValueError(
                "detect_watch_pool_cap must be >= 1 when set (None = uncapped)")


@dataclass(frozen=True)
class ExportConfig:
    size_cap_kb: int = 500
    retain_markdown_sibling: bool = True
    retention_days: int = 90
    archive_compression_format: str = "zip"


@dataclass(frozen=True)
class ClassifierConfig:
    """Tunable algorithm thresholds for chart-pattern classifiers.
    Spec §3.1.4 — V1 bias false-positive cost > false-negative cost. After
    Phase 7 labeled-example calibration, defaults migrate per FP/FN tally."""
    flag_pole_gain_min: float = 0.30
    flag_pullback_depth_max: float = 0.15
    flag_tightness_ratio_max: float = 0.6
    flag_volume_ratio_max: float = 0.7


@dataclass(frozen=True)
class ArchiveConfig:
    """Disk-archive retained-history depth for the OHLCV archive
    (`swing/data/ohlcv_archive.py`). 1260 = 5y trading days; bounds the
    full-history fetch window invoked by weekly refresh + new-ticker paths.

    `stagger_full_refresh` (Arc 6 §5): when True (default), the weekly
    full-refresh trigger is spread across the week via a stateless
    crc32 hash-bucket (≤13-day hard ceiling) instead of a bare `>= 7`
    cliff, preventing the weekly-storm where large batches of the
    universe re-download deep history on the same night. Setting it
    False restores the exact legacy `>= 7` cadence with no code change.

    Toml-shadowing audit (per locked decision §2.5 of the OHLCV archive
    consolidation plan): no override should appear in `swing.config.toml`
    unless the operator explicitly wants a different retention. The
    `aeb2084` 2026-04-28 lesson is in scope — Python defaults shadow at
    runtime if a tracked toml override exists.
    """
    archive_history_days: int = 1260
    stagger_full_refresh: bool = True


@dataclass(frozen=True)
class ReviewConfig:
    """Phase 6 post-trade review tunables. V1 surfaces only the cadence
    review window. V2 may add cadence calendar policy, etc.

    Toml-shadowing rule: section is OPTIONAL in swing.config.toml — when
    absent, dataclass defaults apply (matches the `archive` / `classifier`
    pattern; opposite of `paths` / `account` which are REQUIRED sections).
    """
    review_window_days: int = 7


@dataclass(frozen=True)
class FinvizIntegrationConfig:
    """Finviz Elite API integration config (Phase 7e — finviz-api-integration plan).

    `token` + `screen_query` are sensitive/operator-specific; live in user-config
    only. `timeout_seconds` is non-sensitive default; tracked toml may override.
    """
    token: str = ""
    screen_query: str = ""
    timeout_seconds: int = 30


@dataclass(frozen=True)
class SchwabIntegrationConfig:
    """Schwab API integration config (Sub-bundle A — schwab-api-integration plan).

    Per plan §A.6 + recon doc `docs/schwab-bundle-A-task-A0b-recon.md` §2.9 +1
    deviation (6 fields total; `callback_url` added with trailing-slash + HTTPS
    + localhost validators per schwabdev `setup-guide.md` L23-26 +
    `troubleshooting.md` L72-78 gotchas).

    Sensitive/operator-specific fields (`environment`, `account_hash`,
    `lookback_days`, `callback_url`) live in user-config.toml; tracked
    defaults (`timeout_seconds`, `marketdata_ladder_enabled`) live in
    swing.config.toml.

    `account_hash` is masked in CLI `swing config show` rendering (first 3 +
    asterisks + last 2 chars) via FIELD_REGISTRY `masked=True`.
    """
    environment: str = "production"
    account_hash: str | None = None
    lookback_days: int = 7
    timeout_seconds: float = 30.0
    marketdata_ladder_enabled: bool = True
    callback_url: str = "https://127.0.0.1"
    # Phase 12 Sub-bundle B T-B.2 — Schwab app credentials cfg-cascade fields.
    # Empty-string default mirrors Finviz `token` precedent (L221); T-B.1 wires
    # the env-var → user-config.toml → prompt cascade in
    # `resolve_credentials_env_or_prompt`. Sensitive (live in user-config only);
    # defensively dropped from tracked swing.config.toml at `load()` (L426-438
    # pattern). FIELD_REGISTRY surfaces both as `masked=True` so CLI `swing
    # config show` masks them (first-3 + `***` + last-2).
    client_id: str = ""
    client_secret: str = ""
    # Phase 15 schwabdev v3 upgrade (OQ-1) — optional Fernet token-at-rest key.
    # Sensitive (lives in user-config only); generated at `swing schwab setup` when
    # absent; FIELD_REGISTRY surfaces it `masked=True` in `swing config show`.
    encryption_key: str | None = None

    def __post_init__(self) -> None:
        import math as _math
        # environment: enum constraint (no Literal — dataclass + __post_init__).
        if self.environment not in ("sandbox", "production"):
            raise ValueError(
                "integrations.schwab.environment must be 'sandbox' or "
                f"'production'; got {self.environment!r}"
            )
        # account_hash: None | non-empty str. Empty string explicitly rejected
        # (operator should clear via `swing config reset` not by setting "").
        if self.account_hash is not None and not isinstance(self.account_hash, str):
            raise TypeError(
                "integrations.schwab.account_hash must be str or None; got "
                f"{type(self.account_hash).__name__}"
            )
        if self.account_hash == "":
            raise ValueError(
                "integrations.schwab.account_hash must be None or non-empty "
                "string; got empty string"
            )
        # lookback_days: positive int.
        if not isinstance(self.lookback_days, int) or self.lookback_days < 1:
            raise ValueError(
                "integrations.schwab.lookback_days must be int >= 1; got "
                f"{self.lookback_days!r}"
            )
        # timeout_seconds: positive finite float.
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or not _math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError(
                "integrations.schwab.timeout_seconds must be a positive "
                f"finite number; got {self.timeout_seconds!r}"
            )
        # callback_url: non-empty, https://, no trailing slash, localhost host
        # (schwabdev setup-guide.md L23-26 + troubleshooting.md L72-78 gotcha).
        if not self.callback_url:
            raise ValueError(
                "integrations.schwab.callback_url must not be empty"
            )
        if not self.callback_url.startswith("https://"):
            raise ValueError(
                "integrations.schwab.callback_url must start with 'https://'; "
                f"got {self.callback_url!r}"
            )
        if self.callback_url.endswith("/"):
            raise ValueError(
                "integrations.schwab.callback_url must not have trailing "
                f"slash (schwabdev gotcha); got {self.callback_url!r}"
            )
        rest = self.callback_url[len("https://"):]
        host = rest.split(":")[0].split("/")[0]
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(
                "integrations.schwab.callback_url host must be 127.0.0.1 or "
                f"localhost (Schwab callback gotcha); got {host!r}"
            )
        # T-B.2 — client_id + client_secret: must be `str` type. No length
        # constraint (operator's actual Schwab Developer Portal credentials
        # vary in length). Empty string is the LEGITIMATE V1 default per
        # Finviz `token` precedent; env-var fallback handles the active path.
        if not isinstance(self.client_id, str):
            raise TypeError(
                "integrations.schwab.client_id must be str; got "
                f"{type(self.client_id).__name__}"
            )
        if not isinstance(self.client_secret, str):
            raise TypeError(
                "integrations.schwab.client_secret must be str; got "
                f"{type(self.client_secret).__name__}"
            )
        # Phase 15 (OQ-1) — encryption_key: str | None (a Fernet url-safe base64 key).
        if self.encryption_key is not None and not isinstance(self.encryption_key, str):
            raise TypeError(
                "integrations.schwab.encryption_key must be str or None; got "
                f"{type(self.encryption_key).__name__}"
            )


@dataclass(frozen=True)
class IntegrationsConfig:
    """External-API integrations namespace. Each integration is a sibling
    sub-dataclass following the same pattern (Finviz Phase 7e; Schwab Sub-bundle A)."""
    finviz: FinvizIntegrationConfig = field(default_factory=FinvizIntegrationConfig)
    schwab: SchwabIntegrationConfig = field(default_factory=SchwabIntegrationConfig)


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
    csv_upload_max_bytes: int = 10 * 1024 * 1024
    ohlcv_cache_ttl_seconds: int = 3600              # NEW: 1h default (§3.7)
    max_concurrent_ohlcv_fetches: int = 8            # NEW: full executor (§3.2)
    # How long POST /pipeline/run waits for the spawned subprocess to insert
    # its pipeline_runs row (acquire its lease). Python 3.14 + heavy imports
    # on Windows regularly exceed 2s cold-start; 5s gives comfortable headroom.
    pipeline_lease_wait_seconds: float = 5.0
    # SQLite lock-contention arc (OQ-A): per-connection busy_timeout (ms) for
    # all swing.db opens. 30 s default; runtime-tunable WITHOUT importing cfg
    # into swing/data/db.py (db.py owns the module-level DEFAULT_BUSY_TIMEOUT_MS;
    # this knob feeds open_connection's keyword override at the pipeline/web
    # callsites). Raising it helps the no-deadline OHLCV path; it cannot exceed
    # the 6 s quote-path caller deadline usefully.
    db_busy_timeout_ms: int = 30000
    # Spec §3.8: filters watchlist flag-tag rendering. Default 0.0 = show every
    # detected flag (V1 — no labeled-example calibration data exists yet).
    # Operator dials up after operational experience reveals which confidence
    # bands map to chart-validated flags.
    flag_pattern_display_threshold: float = 0.0
    # Spec §3.1 (hyp-recs trade-prep expansion 2026-04-29): chase factor
    # used by HypRecsExpandedVM.buy_limit = pivot × (1 + chase_factor).
    # Operator's pure-trigger discipline (2026-04-25): wait for pivot,
    # don't chase >1% above pivot. Phase 5 surfaces an editor; this
    # dispatch ships the storage + read path. Toml-shadowing audit
    # (Q-F resolution): no row in swing.config.toml — the field is
    # CODE-ONLY in V1.
    chase_factor: float = 0.01


_LEVEL_NAMES = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


@dataclass(frozen=True)
class LoggingConfig:
    """Logging knobs (spec §4.5 + §5.3). ``warnings`` carries parse-time
    diagnostics that install_logging replays AFTER the redacted handler attaches
    (R1-major-4) -- they are NEVER logged at parse time. ``logger_levels`` is the
    resolved [logging.loggers] override map (name -> level int), parsed at load
    time so malformed entries flow through ``warnings``."""
    level: int = logging.INFO
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5
    logger_levels: dict[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def resolved_logger_levels(self) -> dict[str, int]:
        """Return a COPY of the per-logger override map (defensive against caller
        mutation)."""
        return dict(self.logger_levels)


def _parse_logging_config(raw: object) -> LoggingConfig:
    """Parse a ``[logging]`` table; malformed values (incl. a non-table ``raw``)
    degrade to defaults + collect a diagnostic (never crash). ``raw`` is typed
    ``object`` because a malformed TOML section may not be a dict at all."""
    if not isinstance(raw, dict):
        # A non-table [logging] value (e.g. `logging = "INFO"`) must not crash load().
        return LoggingConfig(
            warnings=(
                f"[logging] section must be a table; got "
                f"{type(raw).__name__!r}; using all defaults",
            ),
        )
    warnings: list[str] = []

    level = logging.INFO
    raw_level = raw.get("level", "INFO")
    if isinstance(raw_level, str) and raw_level.upper() in _LEVEL_NAMES:
        level = _LEVEL_NAMES[raw_level.upper()]
    else:
        warnings.append(f"[logging] level {raw_level!r} invalid; using INFO")

    max_bytes = 10 * 1024 * 1024
    raw_mb = raw.get("max_bytes", max_bytes)
    if isinstance(raw_mb, int) and not isinstance(raw_mb, bool) and raw_mb > 0:
        max_bytes = raw_mb
    else:
        warnings.append(f"[logging] max_bytes {raw_mb!r} invalid; using {max_bytes}")

    backup_count = 5
    raw_bc = raw.get("backup_count", backup_count)
    # Require >= 1: with backupCount=0 RotatingFileHandler keeps NO rotated
    # backups and provides no (backup_count+1)*max_bytes retention set, defeating
    # the retention narrative -> treat <1 as invalid and degrade to the default.
    if isinstance(raw_bc, int) and not isinstance(raw_bc, bool) and raw_bc >= 1:
        backup_count = raw_bc
    else:
        warnings.append(
            f"[logging] backup_count {raw_bc!r} invalid; using {backup_count}"
        )

    logger_levels: dict[str, int] = {}
    raw_loggers = raw.get("loggers", {})
    if isinstance(raw_loggers, dict):
        for name, lvl in raw_loggers.items():
            if isinstance(lvl, str) and lvl.upper() in _LEVEL_NAMES:
                logger_levels[name] = _LEVEL_NAMES[lvl.upper()]
            else:
                warnings.append(
                    f"[logging.loggers] {name!r} level {lvl!r} invalid; skipping"
                )
    elif "loggers" in raw:
        warnings.append(
            f"[logging.loggers] must be a table; got "
            f"{type(raw_loggers).__name__!r}; ignoring"
        )

    return LoggingConfig(
        level=level, max_bytes=max_bytes, backup_count=backup_count,
        logger_levels=logger_levels, warnings=tuple(warnings),
    )


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
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    archive: ArchiveConfig = field(default_factory=ArchiveConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_defaults(cls) -> Config:
        """Load the project's tracked ``swing.config.toml`` from the repo root.

        Resolves the project root as the parent of this module's package
        directory (i.e., ``Path(__file__).resolve().parent.parent``). Used by
        the A+ sensitivity sweep harness + diagnostic CLIs that want the
        production defaults without requiring the caller to thread a path.
        """
        project_root = Path(__file__).resolve().parent.parent
        return load(project_root / "swing.config.toml")


_PROJECT_INTERNAL_PREFIXES = ("data/", "exports/", "reference/")


def _user_home() -> Path:
    """Windows USERPROFILE, fallback to HOME."""
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _resolve_path(raw: str, home: Path, project_root: Path) -> Path:
    """Absolute paths pass through; project-internal paths resolve against
    project_root; else home.
    """
    p = Path(raw)
    if p.is_absolute():
        return p
    normalized = raw.replace("\\", "/")
    if (
        normalized.startswith(_PROJECT_INTERNAL_PREFIXES)
        or normalized in ("exports", "data", "reference")
    ):
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

    raw_finviz = dict(raw.get("integrations", {}).get("finviz", {}))
    # Sensitive fields MUST come from user-config only; tracked toml may carry
    # only timeout_seconds. Drop any token / screen_query rows defensively to
    # eliminate the leak path (Phase 7e plan §A.6).
    raw_finviz.pop("token", None)
    raw_finviz.pop("screen_query", None)

    raw_schwab = dict(raw.get("integrations", {}).get("schwab", {}))
    # Schwab cfg cascade is split: user-config.toml carries operator-edited
    # fields (environment, account_hash, lookback_days, callback_url);
    # swing.config.toml carries tracked defaults (timeout_seconds,
    # marketdata_ladder_enabled). Drop user-config-only fields defensively if
    # they appear in the tracked TOML (mirror Finviz token defense).
    raw_schwab.pop("environment", None)
    raw_schwab.pop("account_hash", None)
    raw_schwab.pop("lookback_days", None)
    raw_schwab.pop("callback_url", None)
    # T-B.2 — Schwab app credentials are sensitive; mirror Finviz token drop
    # (L426-427). Tracked swing.config.toml MUST NOT carry these; they live
    # in user-config.toml only (or env vars via T-A.1 / T-B.1 cascade).
    raw_schwab.pop("client_id", None)
    raw_schwab.pop("client_secret", None)
    # Phase 15 (OQ-1) — the Fernet key is sensitive; user-config.toml only.
    raw_schwab.pop("encryption_key", None)

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
        classifier=ClassifierConfig(**raw.get("classifier", {})),
        archive=ArchiveConfig(**raw.get("archive", {})),
        review=ReviewConfig(**raw.get("review", {})),
        integrations=IntegrationsConfig(
            finviz=FinvizIntegrationConfig(**raw_finviz),
            schwab=SchwabIntegrationConfig(**raw_schwab),
        ),
        logging=_parse_logging_config(raw.get("logging", {})),
    )
