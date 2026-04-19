"""OpenPositionsRowVM + pure assembler + single-row convenience wrapper.

The pure assembler `_open_positions_row_vm` has NO I/O and is called by
`build_dashboard` in its batched path. The convenience wrapper
`build_open_positions_row` does the per-row I/O and is used by POST-success
handlers that need exactly one row (spec §3.4).
"""
from __future__ import annotations

from dataclasses import dataclass

from swing.data.models import Trade
from swing.web.price_cache import PriceSnapshot
from swing.web.view_models.dashboard import AdvisorySuggestionVM


@dataclass(frozen=True)
class OpenPositionsRowVM:
    trade: Trade
    price_snapshot: PriceSnapshot | None
    remaining_shares: int
    advisories: tuple[AdvisorySuggestionVM, ...]


def _open_positions_row_vm(
    *, trade: Trade,
    price_snapshot: PriceSnapshot | None,
    remaining_shares: int,
    advisories: tuple[AdvisorySuggestionVM, ...],
) -> OpenPositionsRowVM:
    """Pure render-input assembler. NO I/O. Single source of truth for the
    fields an open-positions row consumes from Jinja."""
    return OpenPositionsRowVM(
        trade=trade,
        price_snapshot=price_snapshot,
        remaining_shares=remaining_shares,
        advisories=advisories,
    )
