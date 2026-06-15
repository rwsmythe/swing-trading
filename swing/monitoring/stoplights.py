"""Phase 18 Arc 18-F: the GUI health-stoplight framework.

Surfaces at-a-glance system health on every web page via two top-row
stoplights — tool-health (18-E) + research-measurement (18-D). Each provider
is INDEPENDENT and DEFENSIVE: any failure degrades that one stoplight to grey;
the aggregator never raises (LOCK #2 — it runs on EVERY render including the
error page). `grey` is RENDER-ONLY (LOCK #3) — the monitors' own envelopes emit
only {green,yellow,red}; grey is produced solely here (no-data / not-deployed /
error). 18-E's `compute_tool_health` is REUSED (lazy-imported), NOT forked
(LOCK #4); the research read consumes 18-D's §3 status envelope at the SINGLE
shared artifact path.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

_COLORS = frozenset({"green", "yellow", "red", "grey"})

# The shared research-artifact contract (LOCK #4 — defined ONCE so BOTH 18-F
# (reader) and 18-D (writer) reference the same path/id/threshold).
RESEARCH_HEALTH_ARTIFACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "exports" / "research" / "health" / "latest.json"
)
# The envelope `monitor` id 18-D stamps; the research validator gates on it so a
# wrong JSON object at the shared path cannot false-green the stoplight.
RESEARCH_MONITOR_ID = "research_measurement"
# Conservative V1 staleness threshold: a same-monitor artifact older than this
# (by EXACT timedelta) greys — closing the same-monitor-stale false-green vector.
RESEARCH_ARTIFACT_MAX_AGE_DAYS = 7


def research_health_artifact_path() -> Path:
    """Return the shared research health-artifact path.

    An accessor (not a bare constant read) so tests can monkeypatch the function
    without rebinding a module constant; the providers call THIS.
    """
    return RESEARCH_HEALTH_ARTIFACT_PATH


@dataclass(frozen=True)
class Stoplight:
    """A single rendered topbar stoplight.

    `color` admits grey (the render-only no-data/error state, LOCK #3); the
    monitors never emit grey themselves.
    """

    id: str
    label: str
    color: str
    drilldown_path: str

    def __post_init__(self) -> None:
        if self.color not in _COLORS:
            raise ValueError(
                f"Stoplight.color must be one of {sorted(_COLORS)}; "
                f"got {self.color!r}"
            )
        if not self.drilldown_path:
            raise ValueError("Stoplight.drilldown_path must be non-empty")


def _tool_stoplight(conn, cfg) -> Stoplight:
    """The tool-health provider: REUSE 18-E's `compute_tool_health` (lazy import,
    LOCK #4) and map `.overall` -> the stoplight color. DEFENSIVE: ANY exception
    (or a missing cfg from which `prices_cache_dir` can't be derived) degrades to
    grey + a WARNING; NEVER raises (LOCK #2).
    """
    grey = Stoplight(
        id="tool", label="Tool health", color="grey",
        drilldown_path="/health/tool",
    )
    try:
        if cfg is None:
            return grey
        from swing.monitoring.tool_health import compute_tool_health
        status = compute_tool_health(
            conn, cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir,
        )
        return Stoplight(
            id="tool", label="Tool health", color=status.overall,
            drilldown_path="/health/tool",
        )
    except Exception as exc:  # noqa: BLE001 (defensive — must never 500 a page)
        log.warning("tool-health stoplight degraded to grey: %s", exc)
        return grey


def _read_research_envelope() -> dict | None:
    """Read + parse the raw research envelope JSON. Returns None when the file is
    absent (the expected pre-18-D state); lets JSON errors propagate to the
    validating caller's except. Identity/staleness validation lives in
    `read_validated_research_envelope`."""
    path = research_health_artifact_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_validated_research_envelope() -> tuple[str, dict] | None:
    """The SINGLE identity+staleness-validating reader, shared by both
    `_research_stoplight` and the drill-down VM (so the false-green gates are
    defined ONCE — Codex R1 MAJOR #1). Returns `(overall, env)` for a valid,
    fresh, correctly-identified artifact, else None.

    None when: absent (expected pre-18-D — NO warning); malformed JSON; non-dict;
    wrong/missing `monitor` id (identity gate); missing/invalid `overall`;
    absent/unparseable/stale `generated_ts` (staleness gate). Present-but-invalid
    artifacts log a WARNING. NEVER raises (LOCK #2) and NEVER false-greens.
    """
    try:
        env = _read_research_envelope()
        if env is None:
            return None  # absent — expected pre-18-D; no warning
        # IDENTITY gate (Codex R1 MAJOR #1): a wrong JSON object at the shared
        # path must not false-green even if it carries a valid `overall`.
        if not isinstance(env, dict) or env.get("monitor") != RESEARCH_MONITOR_ID:
            log.warning(
                "research artifact monitor id mismatch/absent (%r); grey",
                env.get("monitor") if isinstance(env, dict) else type(env).__name__,
            )
            return None
        overall = env.get("overall")
        if overall not in {"green", "yellow", "red"}:
            log.warning(
                "research artifact overall invalid/absent (%r); grey", overall,
            )
            return None
        # STALENESS gate (Codex R2 + R3 MAJOR): EXACT-duration compare, not
        # floored `.days`. Normalize BOTH sides to the same frame before
        # subtracting (host-tz-independent: aware-vs-aware, else naive-vs-naive).
        raw_ts = env.get("generated_ts")
        try:
            parsed = datetime.fromisoformat(raw_ts) if raw_ts else None
        except (TypeError, ValueError):
            parsed = None
        if parsed is None:
            log.warning(
                "research artifact stale/undated (%r); grey", raw_ts,
            )
            return None
        now = (
            datetime.now(parsed.tzinfo)
            if parsed.tzinfo is not None
            else datetime.now()
        )
        if now - parsed > timedelta(days=RESEARCH_ARTIFACT_MAX_AGE_DAYS):
            log.warning(
                "research artifact stale/undated (%r); grey", raw_ts,
            )
            return None
        return (overall, env)
    except Exception as exc:  # noqa: BLE001 (defensive — never raise to a render)
        log.warning("research artifact unreadable; grey: %s", exc)
        return None


def _research_stoplight() -> Stoplight:
    """The research-measurement provider: read 18-D's §3 envelope at the shared
    path via the validating reader; grey until 18-D writes a conformant fresh
    artifact (then auto-lights, NO 18-F change — provider-driven, LOCK #3)."""
    grey = Stoplight(
        id="research", label="Research monitor", color="grey",
        drilldown_path="/health/research",
    )
    validated = read_validated_research_envelope()
    if validated is None:
        return grey
    overall, _env = validated
    return Stoplight(
        id="research", label="Research monitor", color=overall,
        drilldown_path="/health/research",
    )


def _safe(provider, fallback_id, fallback_label, fallback_path) -> Stoplight:
    """Belt-and-suspenders wrapper: even a non-defensive provider can't 500 a
    page — any exception degrades that slot to grey (LOCK #2)."""
    try:
        return provider()
    except Exception as exc:  # noqa: BLE001 (defensive — never raise to a render)
        log.warning(
            "%s stoplight degraded to grey at the aggregator: %s",
            fallback_id, exc,
        )
        return Stoplight(
            id=fallback_id, label=fallback_label, color="grey",
            drilldown_path=fallback_path,
        )


def health_stoplights(conn, cfg) -> tuple[Stoplight, ...]:
    """Aggregate the two independent providers into the ordered render tuple
    (tool, research). NEVER raises — each provider call is wrapped (LOCK #2 core;
    the context processor adds one more outer guard)."""
    tool = _safe(
        lambda: _tool_stoplight(conn, cfg),
        "tool", "Tool health", "/health/tool",
    )
    research = _safe(
        lambda: _research_stoplight(),
        "research", "Research monitor", "/health/research",
    )
    return (tool, research)
