"""`swing web` backing entry point."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from swing.config import Config
from swing.data.db import SchemaVersionMismatch, connect
from swing.web.app import create_app

log = logging.getLogger(__name__)

_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def run_server(
    *, cfg: Config, cfg_path: Path | None = None,
    host: str | None = None, port: int | None = None,
    reload: bool | None = None,
) -> None:
    """Resolve effective host/port/reload and start uvicorn.

    Precedence: CLI flag > [web] config > dataclass default. The
    resolved host MUST be a loopback name; non-loopback values are
    refused even when set via config.
    """
    effective_host = host or cfg.web.host
    effective_port = port if port is not None else cfg.web.port
    effective_reload = reload if reload is not None else cfg.web.reload

    if effective_host not in _ALLOWED_HOSTS:
        click.echo(
            f"ERROR: dashboard must bind a loopback host (got {effective_host!r}). "
            f"Allowed: {sorted(_ALLOWED_HOSTS)}.",
            err=True,
        )
        sys.exit(1)

    # Spec §4.1 / §5: verify DB schema version before starting the server.
    # Fail fast with a clear remediation hint rather than surfacing the error
    # lazily on the first request.
    try:
        connect(cfg.paths.db_path).close()
    except SchemaVersionMismatch as exc:
        click.echo(
            f"ERROR: {exc}\n"
            f"Run: swing --config {cfg_path or 'swing.config.toml'} db-migrate",
            err=True,
        )
        sys.exit(1)
    except Exception as exc:  # Unhappy IO path, not a schema issue.
        click.echo(
            f"ERROR: cannot open database at {cfg.paths.db_path}: {exc}",
            err=True,
        )
        sys.exit(1)

    app = create_app(cfg, cfg_path)

    import uvicorn
    try:
        uvicorn.run(
            app, host=effective_host, port=effective_port,
            reload=effective_reload, log_level="info",
            access_log=False,  # Disabled — replaced by RequestIdMiddleware (spec §5.2)
        )
    except OSError as exc:
        click.echo(
            f"ERROR: could not bind {effective_host}:{effective_port} ({exc}). "
            f"Set [web].port in swing.config.toml or pass --port.",
            err=True,
        )
        sys.exit(1)
