"""Phase 10 Sub-bundle E Task T-E.5 — account snapshot form VM.

Per electives amendment §2 + plan §A.18: form for manual
``account_equity_snapshots`` capture (web parallel to the existing
``swing account snapshot record`` CLI).

Per CLAUDE.md HTMX-form-driven gotcha family (Phase 5 R1 M1 + M2 + Phase 6
I3 lessons) + Phase 8 server-stamping discipline (R2/R3/R4):
- ``snapshot_date`` server-stamped at handler entry from
  ``last_completed_session(datetime.now())`` (lesson #24 + Phase 9 backward-
  looking writer pattern).
- Template renders the server-stamped value as ``<span class="muted">``
  display-only — operator sees what will persist; cannot tamper.
- Form action POSTs to /account/snapshot; success returns 204 +
  HX-Redirect /metrics/capital-friction (NOT 303 swap-target).
"""
from __future__ import annotations

from dataclasses import dataclass

from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class AccountSnapshotFormVM(BaseLayoutVM):
    """VM for ``GET /account/snapshot`` form-render."""

    # Display-only — server-stamped at handler entry; never accepted from POST.
    snapshot_date_display: str = ""
    # Optional error message rendered after a failed submit (e.g.,
    # malformed equity_dollars).
    error_message: str | None = None
    # Operator-supplied equity value retained for re-render on validation
    # error (so the operator doesn't have to re-type).
    equity_dollars_value: str = ""
    note_value: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.snapshot_date_display:
            raise ValueError(
                "AccountSnapshotFormVM.snapshot_date_display must be non-empty"
            )
