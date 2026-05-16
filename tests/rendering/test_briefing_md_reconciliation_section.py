"""T-C.9 — briefing_md.py "Reconciliation status" section tests.

Per plan §D.9 — emit only when counters > 0; cover no-render +
pending-only + tier1-only + both + high-count cases.
"""
from __future__ import annotations

from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.view_models import (
    AccountTileVM,
    BriefingViewModel,
    PipelineTileVM,
    StatusStripVM,
    WeatherTileVM,
)


def _make_vm(
    *,
    reconciliation_pending_count: int = 0,
    reconciliation_tier1_recent_count: int = 0,
) -> BriefingViewModel:
    return BriefingViewModel(
        action_session_date="2026-05-16",
        data_asof_date="2026-05-15",
        generated_at="2026-05-16T08:00:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(
                status="Bullish", rationale="clear",
                sizing_implication="full sizing OK",
            ),
            account=AccountTileVM(
                equity=2000.0, open_count=0, soft_warn=4, hard_cap=6,
            ),
            pipeline=PipelineTileVM(
                last_run_ts="2026-05-15T17:00:00",
                is_stale=False,
                current_session_match=True,
            ),
        ),
        reconciliation_pending_count=reconciliation_pending_count,
        reconciliation_tier1_recent_count=reconciliation_tier1_recent_count,
    )


def test_no_render_when_both_counters_zero() -> None:
    md = render_briefing_md(_make_vm())
    assert "## Reconciliation status" not in md


def test_renders_when_pending_count_nonzero() -> None:
    md = render_briefing_md(_make_vm(reconciliation_pending_count=3))
    assert "## Reconciliation status" in md
    assert "Tier-2 pending operator review: 3" in md
    assert "Tier-1 auto-corrected (last 7 days): 0" in md
    assert "list-pending-ambiguities" in md
    assert "resolve-ambiguity" in md


def test_renders_when_tier1_recent_count_nonzero() -> None:
    md = render_briefing_md(_make_vm(reconciliation_tier1_recent_count=7))
    assert "## Reconciliation status" in md
    assert "Tier-1 auto-corrected (last 7 days): 7" in md
    assert "Tier-2 pending operator review: 0" in md


def test_renders_when_both_counters_set() -> None:
    md = render_briefing_md(
        _make_vm(
            reconciliation_pending_count=2,
            reconciliation_tier1_recent_count=5,
        )
    )
    assert "## Reconciliation status" in md
    assert "Tier-1 auto-corrected (last 7 days): 5" in md
    assert "Tier-2 pending operator review: 2" in md


def test_renders_when_high_count() -> None:
    md = render_briefing_md(
        _make_vm(
            reconciliation_pending_count=42,
            reconciliation_tier1_recent_count=100,
        )
    )
    assert "Tier-1 auto-corrected (last 7 days): 100" in md
    assert "Tier-2 pending operator review: 42" in md
