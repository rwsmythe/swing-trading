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

import logging
from dataclasses import dataclass
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
