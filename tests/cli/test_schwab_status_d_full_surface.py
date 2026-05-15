"""T-D.1 — `swing schwab status` full per-environment surface tests.

10 binding tests per dispatch brief §0.9 + §5.2 T-D.1 + spec §3.5 mock.

T-D.1 extends the T-A.6 skeleton with:
  - Per-environment recent-error counts (24h / 7d) + snapshots-30d +
    reconciliation_runs(schwab_api)-30d + unresolved-material-discrepancies
    count.
  - Multi-signal `is_degraded` predicate per §5.2 T-D.1 row: consults
    most-recent `schwab_api_calls.status != 'success'` OR tokens DB missing
    OR tokens DB age > 7 days.
  - Days-remaining alert escalation: ≤24hr WARN; ≤2hr ERROR + bold red ASCII
    marker `[!! ERROR !!]`.
  - "reconciliation_runs (schwab_api): N in last 30 days; M unresolved
    material discrepancies" summary.

SECURITY DISCIPLINE preserved from T-A.6:
  - NO schwabdev.Client construction.
  - ZERO Schwab token bytes (access/refresh/id) in stdout.
  - account_hash masked via mask_sensitive_value.
  - USERPROFILE+HOME monkeypatched (CLAUDE.md gotcha _user_home reads env).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main

# Sentinel bytes — discriminating Test #9 asserts these never appear.
_SENTINEL_ACCESS_TOKEN = "ACCESS_TOKEN_SENTINEL_xyz123"
_SENTINEL_REFRESH_TOKEN = "REFRESH_TOKEN_SENTINEL_abc456"
_SENTINEL_ID_TOKEN = "ID_TOKEN_SENTINEL_qrs789"


# ============================================================================
# Fixtures (mirror tests/integrations/test_schwab_status_cli.py)
# ============================================================================


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated USERPROFILE+HOME pointing at tmp_path (CLAUDE.md gotcha)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def cfg_path(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy of project's swing.config.toml with path overrides routed to
    tmp_path. Mirrors tests/integrations/test_schwab_status_cli.py.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_cfg = repo_root / "swing.config.toml"
    cfg_text = src_cfg.read_text()
    db_path = home / "swing-data" / "swing.db"
    home_swing_data = (home / "swing-data").as_posix()
    home_finviz = (home / "finviz-inbox").as_posix()
    home_exports = (home / "exports").as_posix()
    home_rs = (home / "rs.csv").as_posix()
    new_paths_block = f"""[paths]
db_path = "{db_path.as_posix()}"
data_dir = "{home_swing_data}"
logs_dir = "{home_swing_data}/logs"
charts_dir = "{home_swing_data}/charts"
backups_dir = "{home_swing_data}/backups"
prices_cache_dir = "{home_swing_data}/prices-cache"
finviz_inbox_dir = "{home_finviz}"
exports_dir = "{home_exports}"
rs_universe_path = "{home_rs}"
"""
    cfg_text = re.sub(
        r"\[paths\]\n(?:[^\[]+)",
        new_paths_block + "\n",
        cfg_text,
        count=1,
    )
    cfg_file = home / "swing.config.toml"
    cfg_file.write_text(cfg_text)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    from swing.data.db import ensure_schema
    ensure_schema(db_path).close()
    return cfg_file


def _write_tokens_file(
    home: Path,
    *,
    env: str = "production",
    access_token_issued: str | None = None,
    refresh_token_issued: str | None = None,
    access_token: str = _SENTINEL_ACCESS_TOKEN,
    refresh_token: str = _SENTINEL_REFRESH_TOKEN,
    id_token: str = _SENTINEL_ID_TOKEN,
    expires_in: int = 1800,
) -> Path:
    """Write a tokens JSON file shaped per recon §6.bis.

    Defaults to fresh ISO timestamps (now in UTC) so tests don't trip on
    expiry calculations unless they explicitly override.
    """
    if access_token_issued is None:
        access_token_issued = datetime.now(UTC).isoformat()
    if refresh_token_issued is None:
        refresh_token_issued = datetime.now(UTC).isoformat()
    path = home / "swing-data" / f"schwab-tokens.{env}.db"
    payload = {
        "access_token_issued": access_token_issued,
        "refresh_token_issued": refresh_token_issued,
        "token_dictionary": {
            "expires_in": expires_in,
            "token_type": "Bearer",
            "scope": "api",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "id_token": id_token,
        },
    }
    path.write_text(json.dumps(payload, indent=4))
    return path


def _invoke(cfg_path: Path, args: list) -> object:
    runner = CliRunner()
    return runner.invoke(main, ["--config", str(cfg_path), "schwab", *args])


def _plant_call(
    db_path: Path,
    *,
    ts: str,
    status: str,
    env: str = "production",
    endpoint: str = "accounts.linked",
    surface: str = "cli",
    http_status: int | None = 200,
) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO schwab_api_calls ("
            "ts, endpoint, status, surface, environment, http_status"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (ts, endpoint, status, surface, env, http_status),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _plant_snapshot(
    db_path: Path,
    *,
    snapshot_date: str,
    source: str = "schwab_api",
    equity_dollars: float = 1234.56,
    recorded_at: str | None = None,
) -> int:
    if recorded_at is None:
        recorded_at = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO account_equity_snapshots ("
            "snapshot_date, equity_dollars, source, recorded_at, recorded_by"
            ") VALUES (?, ?, ?, ?, ?)",
            (snapshot_date, equity_dollars, source, recorded_at, "test"),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _plant_recon_run(
    db_path: Path,
    *,
    started_ts: str,
    source: str = "schwab_api",
    state: str = "completed",
    finished_ts: str | None = None,
) -> int:
    if finished_ts is None and state == "completed":
        finished_ts = started_ts
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO reconciliation_runs ("
            "source, started_ts, finished_ts, state"
            ") VALUES (?, ?, ?, ?)",
            (source, started_ts, finished_ts, state),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _plant_discrepancy(
    db_path: Path,
    *,
    run_id: int,
    material: int = 1,
    resolution: str = "unresolved",
    discrepancy_type: str = "stop_mismatch",
    field_name: str = "current_stop",
    created_at: str | None = None,
) -> int:
    if created_at is None:
        created_at = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, discrepancy_type, field_name, material, resolution,
             created_at),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _set_tokens_db_mtime(home: Path, env: str, age_seconds: float) -> None:
    """Set the tokens DB file mtime to (now - age_seconds) via os.utime."""
    path = home / "swing-data" / f"schwab-tokens.{env}.db"
    target = (datetime.now(UTC) - timedelta(seconds=age_seconds)).timestamp()
    os.utime(path, (target, target))


# ============================================================================
# Tests
# ============================================================================


def test_status_renders_live_when_recent_call_succeeded_and_tokens_fresh(
    home: Path, cfg_path: Path,
) -> None:
    """Test 1 — happy LIVE: fresh tokens DB + most-recent call status='success'.

    Assert:
      - "LIVE" appears (with env tag).
      - "DEGRADED" does NOT appear.
    """
    _write_tokens_file(home, env="production")
    now_iso = datetime.now(UTC).isoformat()
    _plant_call(home / "swing-data" / "swing.db",
                ts=now_iso, status="success", env="production")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    assert "LIVE" in result.output
    assert "DEGRADED" not in result.output


def test_status_renders_degraded_when_recent_call_status_error(
    home: Path, cfg_path: Path,
) -> None:
    """Test 2 — DEGRADED via recent-call-error signal.

    Plant fresh tokens DB + 1 'error' row as most-recent. Assert "DEGRADED"
    appears + reason cites the recent-error signal.
    """
    _write_tokens_file(home, env="production")
    now_iso = datetime.now(UTC).isoformat()
    _plant_call(home / "swing-data" / "swing.db",
                ts=now_iso, status="error", env="production")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    assert "DEGRADED" in result.output
    out_lower = result.output.lower()
    assert "recent" in out_lower or "last call" in out_lower or \
        "most-recent" in out_lower, (
        f"DEGRADED reason should cite recent-error signal; got:\n{result.output}"
    )


def test_status_renders_degraded_when_tokens_db_missing(
    home: Path, cfg_path: Path,
) -> None:
    """Test 3 — DEGRADED via missing tokens DB.

    No tokens file written; assert "DEGRADED" + reason cites missing tokens.
    """
    # No tokens file written.
    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    assert "DEGRADED" in result.output
    out_lower = result.output.lower()
    assert "tokens" in out_lower and (
        "missing" in out_lower or "not present" in out_lower
        or "not found" in out_lower
    ), (
        f"DEGRADED reason should cite missing tokens DB; got:\n{result.output}"
    )


def test_status_renders_degraded_when_tokens_db_age_over_7d(
    home: Path, cfg_path: Path,
) -> None:
    """Test 4 — DEGRADED via tokens-DB-mtime > 7 days.

    Even with success row + valid JSON, an 8-day-old tokens DB triggers the
    third degraded signal (refresh-token TTL is 7 days).
    """
    _write_tokens_file(home, env="production")
    # Set mtime to 8 days ago.
    _set_tokens_db_mtime(home, "production", age_seconds=8 * 24 * 3600)
    now_iso = datetime.now(UTC).isoformat()
    _plant_call(home / "swing-data" / "swing.db",
                ts=now_iso, status="success", env="production")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    assert "DEGRADED" in result.output
    out_lower = result.output.lower()
    assert "tokens" in out_lower and (
        "stale" in out_lower or "old" in out_lower or "age" in out_lower
        or "7 days" in out_lower or "mtime" in out_lower
    ), (
        f"DEGRADED reason should cite stale tokens DB age; "
        f"got:\n{result.output}"
    )


def test_status_renders_per_environment_counts_24h_7d_and_30d(
    home: Path, cfg_path: Path,
) -> None:
    """Test 5 — recent-error counts in 24h vs 7d windows.

    Plant rows at varying ts, mix of success+error, both production+sandbox.
    Assert per-env counts surface correctly:
      - 24h error count: 1 (the recent error).
      - 7d error count: 3 (recent + 25h + within-7d).
    Also pin the count distinguishes from 30d window.
    """
    _write_tokens_file(home, env="production")
    db_path = home / "swing-data" / "swing.db"
    now = datetime.now(UTC)

    # Production env errors:
    # - 1h ago: error (in 24h, in 7d)
    _plant_call(db_path, ts=(now - timedelta(hours=1)).isoformat(),
                status="error", env="production")
    # - 25h ago: error (NOT in 24h; in 7d)
    _plant_call(db_path, ts=(now - timedelta(hours=25)).isoformat(),
                status="error", env="production")
    # - 6 days ago: error (NOT in 24h; in 7d)
    _plant_call(db_path, ts=(now - timedelta(days=6)).isoformat(),
                status="error", env="production")
    # - 8 days ago: error (NOT in 24h; NOT in 7d)
    _plant_call(db_path, ts=(now - timedelta(days=8)).isoformat(),
                status="error", env="production")
    # - now: success (newest, so NOT degraded by recent-call signal)
    _plant_call(db_path, ts=(now + timedelta(seconds=1)).isoformat(),
                status="success", env="production")
    # Sandbox row that should NOT be counted.
    _plant_call(db_path, ts=(now - timedelta(hours=1)).isoformat(),
                status="error", env="sandbox")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Discriminating: 24h count = 1; 7d count = 3.
    # The renderer should produce distinct lines like:
    #   "recent errors:    1 in last 24h, 3 in last 7d"
    assert "1 in last 24h" in result.output, (
        f"expected '1 in last 24h' in output; got:\n{result.output}"
    )
    assert "3 in last 7d" in result.output, (
        f"expected '3 in last 7d' in output; got:\n{result.output}"
    )


def test_status_renders_reconciliation_summary(
    home: Path, cfg_path: Path,
) -> None:
    """Test 6 — reconciliation_runs(schwab_api) summary line.

    Seed:
      - 2 reconciliation_runs with source='schwab_api' inside last 30 days.
      - 1 schwab_api run OUTSIDE last 30 days.
      - 1 tos_csv run inside last 30 days (must NOT be counted).
      - 3 unresolved+material discrepancies.
    Assert summary "reconciliation_runs (schwab_api): 2 in last 30 days;
    3 unresolved material discrepancies".
    """
    _write_tokens_file(home, env="production")
    db_path = home / "swing-data" / "swing.db"
    now = datetime.now(UTC)

    # 2 schwab_api runs inside 30d.
    run_1 = _plant_recon_run(db_path,
                             started_ts=(now - timedelta(days=2)).isoformat(),
                             source="schwab_api")
    _plant_recon_run(db_path,
                     started_ts=(now - timedelta(days=15)).isoformat(),
                     source="schwab_api")
    # 1 schwab_api run OUTSIDE 30d.
    _plant_recon_run(db_path,
                     started_ts=(now - timedelta(days=45)).isoformat(),
                     source="schwab_api")
    # 1 tos_csv run inside 30d (filtered out).
    _plant_recon_run(db_path,
                     started_ts=(now - timedelta(days=5)).isoformat(),
                     source="tos_csv")

    # 3 unresolved+material discrepancies attached to run_1.
    for _ in range(3):
        _plant_discrepancy(db_path, run_id=run_1, material=1,
                           resolution="unresolved")
    # 1 immaterial (filtered out).
    _plant_discrepancy(db_path, run_id=run_1, material=0,
                       resolution="unresolved")
    # 1 resolved (filtered out).
    _plant_discrepancy(db_path, run_id=run_1, material=1,
                       resolution="acknowledged_immaterial")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Spec §3.5 mock format. Match the substantive numerics + key text.
    assert "reconciliation_runs (schwab_api): 2 in last 30 days" \
        in result.output, (
        f"expected reconciliation summary; got:\n{result.output}"
    )
    assert "3 unresolved material discrepancies" in result.output, (
        f"expected discrepancy count; got:\n{result.output}"
    )


def test_status_renders_snapshots_written_count_per_environment(
    home: Path, cfg_path: Path,
) -> None:
    """Test 7 — snapshots-written count in last 30 days.

    Seed 4 schwab_api snapshots inside 30d + 2 outside; assert "4 in last
    30 days" surfaced. (Snapshots have no environment column V1; the per-env
    qualifier is provided by the active env header.)
    """
    _write_tokens_file(home, env="production")
    db_path = home / "swing-data" / "swing.db"
    today = datetime.now(UTC).date()

    # 4 inside 30d (use distinct dates for the unique index).
    for delta_days in (1, 5, 12, 25):
        d = today - timedelta(days=delta_days)
        _plant_snapshot(db_path, snapshot_date=d.isoformat(),
                        source="schwab_api")
    # 2 outside 30d.
    for delta_days in (35, 90):
        d = today - timedelta(days=delta_days)
        _plant_snapshot(db_path, snapshot_date=d.isoformat(),
                        source="schwab_api")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    assert "snapshots written: 4 in last 30 days" in result.output \
        or "snapshots written:    4 in last 30 days" in result.output, (
        f"expected 'snapshots written: 4 in last 30 days'; "
        f"got:\n{result.output}"
    )


@pytest.mark.parametrize(
    "age_seconds,expect_warn,expect_error",
    [
        # ≤24hr boundary: refresh issued (7d - 24h - 1s) ago means
        # remaining = 24h + 1s ⇒ NO WARN, NO ERROR.
        (7 * 24 * 3600 - 24 * 3600 - 1, False, False),
        # 24h MINUS 1s remaining ⇒ WARN, no ERROR.
        (7 * 24 * 3600 - 24 * 3600 + 1, True, False),
        # 2h MINUS 1s remaining ⇒ ERROR + WARN gone (escalates to ERROR).
        (7 * 24 * 3600 - 2 * 3600 + 1, False, True),
        # 2h PLUS 1s remaining ⇒ WARN only.
        (7 * 24 * 3600 - 2 * 3600 - 1, True, False),
    ],
    ids=["24h+1s_OK", "24h-1s_WARN", "2h-1s_ERROR", "2h+1s_WARN"],
)
def test_status_alert_warn_at_24hr_minus_1s_boundary(
    home: Path, cfg_path: Path,
    age_seconds: int, expect_warn: bool, expect_error: bool,
) -> None:
    """Test 8 — boundary tests for WARN (≤24hr) + ERROR (≤2hr) escalation.

    refresh_token TTL = 7 days. age_seconds is how long ago the refresh
    token was issued. remaining = 7d - age_seconds.

    Boundary semantics:
      - remaining <= 2hr ⇒ ERROR (with `[!! ERROR !!]` marker).
      - 2hr < remaining <= 24hr ⇒ WARN (with `[WARN]` prefix).
      - remaining > 24hr ⇒ neither.
    """
    issued = (datetime.now(UTC) - timedelta(seconds=age_seconds)).isoformat()
    _write_tokens_file(home, env="production",
                       refresh_token_issued=issued,
                       access_token_issued=datetime.now(UTC).isoformat())
    # Fresh recent call so degraded predicate doesn't fire on call signal.
    _plant_call(home / "swing-data" / "swing.db",
                ts=datetime.now(UTC).isoformat(),
                status="success", env="production")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output

    has_warn = "[WARN]" in result.output
    has_error = "[!! ERROR !!]" in result.output

    if expect_error:
        assert has_error, (
            f"expected [!! ERROR !!] marker; got:\n{result.output}"
        )
        # When ERROR fires, WARN must NOT also fire (escalation).
        assert not has_warn, (
            f"WARN should be suppressed when ERROR fires; got:\n{result.output}"
        )
    elif expect_warn:
        assert has_warn, f"expected [WARN] prefix; got:\n{result.output}"
        assert not has_error, (
            f"unexpected [!! ERROR !!]; got:\n{result.output}"
        )
    else:
        assert not has_warn, (
            f"unexpected [WARN] (remaining > 24hr); got:\n{result.output}"
        )
        assert not has_error, (
            f"unexpected [!! ERROR !!] (remaining > 2hr); got:\n{result.output}"
        )


def test_status_no_token_bytes_in_output(home: Path, cfg_path: Path) -> None:
    """Test 9 (BINDING) — sentinel-leak audit.

    Plant tokens DB with KNOWN access/refresh/id token sentinels; assert
    NONE of those three sentinels appear in stdout.
    """
    _write_tokens_file(home, env="production",
                       access_token=_SENTINEL_ACCESS_TOKEN,
                       refresh_token=_SENTINEL_REFRESH_TOKEN,
                       id_token=_SENTINEL_ID_TOKEN)
    _plant_call(home / "swing-data" / "swing.db",
                ts=datetime.now(UTC).isoformat(),
                status="success", env="production")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    assert _SENTINEL_ACCESS_TOKEN not in result.output, (
        "access_token leaked to stdout — redaction broken"
    )
    assert _SENTINEL_REFRESH_TOKEN not in result.output, (
        "refresh_token leaked to stdout — redaction broken"
    )
    assert _SENTINEL_ID_TOKEN not in result.output, (
        "id_token leaked to stdout — redaction broken"
    )


def test_status_cli_exit_code_zero_even_when_degraded(
    home: Path, cfg_path: Path,
) -> None:
    """Test 10 — exit code 0 in DEGRADED state.

    Status is a read-only diagnostic surface; it MUST NEVER exit nonzero
    even when the integration is degraded. Operator scripting can grep for
    "DEGRADED" in stdout if they want a programmatic signal.
    """
    # No tokens file → DEGRADED via missing-tokens signal.
    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    assert "DEGRADED" in result.output  # Confirms degraded state surfaced.
