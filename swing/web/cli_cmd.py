"""`swing web` backing entry point. Populated in Task 8."""
from __future__ import annotations

from pathlib import Path

from swing.config import Config


def run_server(
    *, cfg: Config, cfg_path: Path | None = None,
    host: str | None = None, port: int | None = None,
    reload: bool | None = None,
) -> None:
    raise NotImplementedError("filled in by Task 8")
