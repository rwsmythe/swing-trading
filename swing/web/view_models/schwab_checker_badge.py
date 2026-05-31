"""Web checker-health badge -- reads the SAME sidecar via the SAME state
machine as `swing schwab status` (no forked liveness logic). ASCII-only."""
from __future__ import annotations

from dataclasses import dataclass

from swing.integrations.schwab.checker_resilience import (
    checker_liveness_sidecar_path,
    evaluate_liveness_state,
    read_liveness_sidecar,
)


@dataclass(frozen=True)
class SchwabCheckerBadgeVM:
    state: str       # ALIVE | STARTING | DEGRADED | UNKNOWN
    label: str       # short ASCII glyph-free label
    title: str       # hover text (ASCII)
    css_class: str   # ok | info | warn


_BADGE_MAP = {
    "ALIVE":    ("Schwab", "ok"),
    "STARTING": ("Schwab", "info"),
    "DEGRADED": ("Schwab!", "warn"),
    "UNKNOWN":  ("Schwab?", "warn"),
}


def build_schwab_checker_badge(cfg) -> SchwabCheckerBadgeVM | None:
    """Return the badge VM, or None when no sidecar exists (badge hidden:
    sandbox / no Schwab client / tests)."""
    import time
    env = cfg.integrations.schwab.environment
    data = read_liveness_sidecar(checker_liveness_sidecar_path(env))
    if data is None:
        return None
    state, reason = evaluate_liveness_state(data, now_ts=time.time())
    label, css = _BADGE_MAP[state]
    return SchwabCheckerBadgeVM(
        state=state, label=label,
        title=f"Schwab checker: {state.lower()} ({reason})", css_class=css,
    )
