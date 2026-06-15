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


# Severity ordering for the overall-vs-checks consistency gate (worst wins).
_SEVERITY_RANK = {"green": 0, "yellow": 1, "red": 2}


def research_health_artifact_path() -> Path:
    """Return the shared research health-artifact path.

    An accessor (not a bare constant read) so tests can monkeypatch the function
    without rebinding a module constant; the providers call THIS.
    """
    return RESEARCH_HEALTH_ARTIFACT_PATH


def _worst_check_severity(checks) -> str | None:
    """Return the worst (most severe) status across `checks`, or None when the
    artifact is unverifiable.

    Validates the FULL render-contract schema each check must satisfy (NOT just
    `status`): the list is non-empty, and every check is a dict with a non-empty
    string `key`, a `status` in {green,yellow,red}, a non-empty string `summary`,
    and a `detail` that is None or a string. A None result (absent/empty/non-list,
    or ANY malformed check) means the caller cannot trust the artifact -> greys.
    This closes the residual false-green where a severity-only check (e.g.
    `{"status":"green"}`) would light the topbar green while the drill-down VM
    silently drops the shapeless check (Codex R3 MAJOR).
    """
    if not isinstance(checks, list) or not checks:
        return None
    worst = "green"
    for c in checks:
        if not isinstance(c, dict):
            return None
        status = c.get("status")
        if status not in _SEVERITY_RANK:
            return None
        key = c.get("key")
        summary = c.get("summary")
        if not isinstance(key, str) or not key:
            return None
        if not isinstance(summary, str) or not summary:
            return None
        detail = c.get("detail")
        if detail is not None and not isinstance(detail, str):
            return None
        if _SEVERITY_RANK[status] > _SEVERITY_RANK[worst]:
            worst = status
    return worst


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
        age = now - parsed
        # A FUTURE generated_ts (bad clock / tampered same-monitor artifact)
        # yields a negative age -> the `age > 7d` stale check is False, so it
        # would false-green up to 7d past that future time (Codex R1 MAJOR).
        # Treat a future timestamp as untrusted (like stale) -> grey.
        if age < timedelta(0):
            log.warning(
                "research artifact future-dated/untrusted (%r); grey", raw_ts,
            )
            return None
        if age > timedelta(days=RESEARCH_ARTIFACT_MAX_AGE_DAYS):
            log.warning(
                "research artifact stale/undated (%r); grey", raw_ts,
            )
            return None
        # CONSISTENCY gate (Codex R2 MAJOR): the research path ingests raw JSON
        # (the tool path is protected by ToolHealthStatus.__post_init__). A
        # same-monitor, fresh, valid-overall envelope whose `overall` is BETTER
        # than its worst check would false-green the topbar while the drill-down
        # lists a worse check. Cross-check `overall` against the worst check
        # severity; reject (grey) any inconsistent or unverifiable artifact.
        worst = _worst_check_severity(env.get("checks"))
        if worst is None or worst != overall:
            log.warning(
                "research artifact overall (%r) inconsistent with worst check "
                "(%r); grey", overall, worst,
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
