"""Slice 3 — `swing schwab status` checker-liveness line."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from swing.cli_schwab import render_status
from swing.integrations.schwab import checker_resilience as cr


def _make_cfg(tmp_path: Path):
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    cfg_path = _minimal_config(tmp_path / "p", tmp_path / "h")
    return load(cfg_path)


def _schema_conn(tmp_path: Path) -> sqlite3.Connection:
    from swing.data.db import ensure_schema
    return ensure_schema(tmp_path / "swing.db")


def _render_with_sidecar(tmp_path, monkeypatch, payload):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    sidecar = cr.checker_liveness_sidecar_path("sandbox")
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    if payload is not None:
        sidecar.write_text(json.dumps(payload), encoding="ascii")
    cfg = _make_cfg(tmp_path)
    conn = _schema_conn(tmp_path)
    try:
        return render_status(
            cfg=cfg, env="sandbox", tokens_path=sidecar.parent / "x.db",
            now=datetime.now(UTC), conn=conn,
        )
    finally:
        conn.close()


def test_status_reports_alive(tmp_path, monkeypatch):
    out = _render_with_sidecar(
        tmp_path, monkeypatch,
        {"installed_ts": 0.0, "last_daemon_tick_ts": time.time(),
         "consecutive_failures": 0},
    )
    assert "Checker:" in out
    assert "ALIVE" in out


def test_status_reports_unknown_when_absent(tmp_path, monkeypatch):
    out = _render_with_sidecar(tmp_path, monkeypatch, None)
    assert "Checker:" in out and "unknown" in out.lower()


def test_checker_line_is_ascii(tmp_path, monkeypatch):
    out = _render_with_sidecar(
        tmp_path, monkeypatch,
        {"installed_ts": 0.0, "consecutive_failures": 2,
         "last_error_class": "ConnectionError"},
    )
    line = next(ln for ln in out.splitlines() if ln.startswith("Checker:"))
    assert line.isascii()  # ASCII scoped to the NEW line (render_status uses em dash elsewhere)
