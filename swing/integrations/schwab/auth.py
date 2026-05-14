"""OAuth paste-back setup, force-refresh, and revocation for Schwab integration.

Per recon doc `docs/schwab-bundle-A-task-A0b-recon.md` §2.2: schwabdev does
NOT expose a separate `auth.manual_flow(...)` callable — OAuth interactive
paste-back is embedded in `schwabdev.Client(...)` construction itself. This
module's functions wrap that construction (`setup_paste_flow`) and surface
the force-refresh (`force_refresh`) + revocation (`revoke_and_delete`) paths.

Full implementations land in:
  * T-A.4 — `setup_paste_flow` (paste-back via `schwabdev.Client(...)`).
  * T-A.5 — `force_refresh` (via `client.update_tokens(force_refresh_token=True)`)
            + `revoke_and_delete` (manual `POST /v1/oauth/revoke` per recon §2.5).

T-A.3 ships function STUBS that raise `NotImplementedError` so importers fail
loudly until T-A.4/T-A.5 land.
"""
from __future__ import annotations

from typing import Any


def setup_paste_flow(*args: Any, **kwargs: Any) -> Any:
    """OAuth paste-back setup — implementation lands in T-A.4."""
    raise NotImplementedError("setup_paste_flow lands in T-A.4")


def force_refresh(*args: Any, **kwargs: Any) -> Any:
    """Force-rotate access + refresh tokens — implementation lands in T-A.5."""
    raise NotImplementedError("force_refresh lands in T-A.5")


def revoke_and_delete(*args: Any, **kwargs: Any) -> Any:
    """Revoke refresh_token + delete per-env tokens DB — implementation lands
    in T-A.5."""
    raise NotImplementedError("revoke_and_delete lands in T-A.5")
