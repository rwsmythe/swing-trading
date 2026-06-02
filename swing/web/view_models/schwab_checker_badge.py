"""Web checker-health badge -- reads the SAME sidecar via the SAME state
machine as `swing schwab status` (no forked liveness logic). ASCII-only."""
from __future__ import annotations

from dataclasses import dataclass

from swing.integrations.schwab.checker_resilience import (
    checker_liveness_sidecar_path,
    evaluate_liveness_state,
    read_liveness_sidecar,
)
from swing.integrations.schwab.marketdata_ladder import _is_ladder_active


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
    """Return the badge VM, or None when the badge must be hidden.

    Hidden when cfg is None (cfg-less callers) OR when the Schwab checker is
    not EXPECTED to be running -- i.e. NOT (production AND ladder enabled).
    When the checker IS expected, render the state from the SAME state machine
    as ``swing schwab status``: a missing/unreadable sidecar maps to UNKNOWN
    (Schwab?, warn) rather than vanishing, so a silent checker failure is
    visible in the topbar (A-7). Pure config read + file read; no Schwab API
    call. ASCII-only.
    """
    import time
    if cfg is None:
        return None
    if not _is_ladder_active(cfg):
        return None
    env = cfg.integrations.schwab.environment
    data = read_liveness_sidecar(checker_liveness_sidecar_path(env))
    state, reason = evaluate_liveness_state(data, now_ts=time.time())
    if data is None:
        # The state machine's hardcoded UNKNOWN reason ("web server not
        # running, or pre-N7 build") is misleading here: the checker is
        # EXPECTED (production + ladder) but no sidecar exists, which means
        # the client could not be constructed (degraded/missing creds).
        reason = (
            "Schwab client unavailable - no checker running; "
            "check credentials/tokens"
        )
    label, css = _BADGE_MAP[state]
    return SchwabCheckerBadgeVM(
        state=state, label=label,
        title=f"Schwab checker: {state.lower()} ({reason})", css_class=css,
    )
