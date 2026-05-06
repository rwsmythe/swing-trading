import contextlib
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from swing.config import FinvizIntegrationConfig
from swing.data.db import ensure_schema
from swing.data.repos.finviz_api_calls import list_recent_calls


def _setup_cfg(tmp_path: Path, *, token: str = "tok", screen_query: str = "v=152", inbox=None):
    """Build a minimal cfg-shaped object for _step_finviz_fetch."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Stub:
        finviz: FinvizIntegrationConfig

    @dataclass(frozen=True)
    class _Paths:
        finviz_inbox_dir: Path
        db_path: Path

    @dataclass(frozen=True)
    class _Cfg:
        paths: _Paths
        integrations: _Stub

    return _Cfg(
        paths=_Paths(
            finviz_inbox_dir=inbox or (tmp_path / "finviz-inbox"),
            db_path=tmp_path / "swing.db",
        ),
        integrations=_Stub(finviz=FinvizIntegrationConfig(
            token=token, screen_query=screen_query, timeout_seconds=5,
        )),
    )


def _setup_db(cfg) -> sqlite3.Connection:
    cfg.paths.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = ensure_schema(cfg.paths.db_path)
    return conn


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_step_finviz_fetch_writes_csv_and_ok_row(tmp_path: Path) -> None:
    """Happy path: API returns CSV → file written + status='ok' row + signature populated."""
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        rows = list_recent_calls(conn)
        assert len(rows) == 1
        # Discriminating: status='ok' (NOT 'error', NOT 'skipped_manual_override').
        assert rows[0].status == "ok"
        # Discriminating: signature_hash populated (64-char hex).
        assert rows[0].signature_hash is not None
        assert len(rows[0].signature_hash) == 64
        # Discriminating: row_count > 0.
        assert (rows[0].row_count or 0) > 0
        # Discriminating: response_time_ms populated.
        assert (rows[0].response_time_ms or 0) >= 0
    finally:
        conn.close()

    # CSV file written with the expected filename pattern.
    csvs = list(cfg.paths.finviz_inbox_dir.glob("finviz*.csv"))
    assert len(csvs) == 1, [f.name for f in csvs]
    text = csvs[0].read_text()
    assert "Ticker" in text.split("\n", 1)[0]


def test_step_finviz_fetch_skips_when_csv_exists(tmp_path: Path) -> None:
    """File-collision skip: today's CSV exists → API NOT called; row='skipped_manual_override'."""
    from datetime import datetime
    import platform

    from swing.evaluation.dates import action_session_for_run
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)

    # Create today's manual CSV BEFORE calling the step.
    action_session = action_session_for_run(datetime.now())
    fmt = "%#d" if platform.system() == "Windows" else "%-d"
    date_str = action_session.strftime(f"{fmt}%b%Y")
    manual_path = cfg.paths.finviz_inbox_dir / f"finviz{date_str}.csv"
    manual_path.write_text("manual content")

    try:
        with patch("swing.integrations.finviz_api.FinvizClient.fetch_screen") as mock_fetch:
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
            # Discriminating: API client was NOT instantiated/called.
            mock_fetch.assert_not_called()
        rows = list_recent_calls(conn)
        # Discriminating: row recorded with skip status.
        assert len(rows) == 1
        assert rows[0].status == "skipped_manual_override"
        assert rows[0].signature_hash is None
        assert rows[0].row_count is None
    finally:
        conn.close()

    # Manual CSV unchanged.
    assert manual_path.read_text() == "manual content"


def test_step_finviz_fetch_records_error_on_api_failure(tmp_path: Path) -> None:
    """Error path: API raises → row='error' inserted; pipeline does NOT raise."""
    from swing.integrations.finviz_api import FinvizApiError
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        with patch(
            "swing.integrations.finviz_api.FinvizClient.fetch_screen",
            side_effect=FinvizApiError(500, ""),
        ):
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        rows = list_recent_calls(conn)
        # Discriminating: status='error' (NOT 'ok' — the test would fail under
        # an implementation that swallows + records 'ok').
        assert rows[0].status == "error"
        assert rows[0].error_message is not None
        assert "FinvizApiError" in rows[0].error_message
        assert rows[0].signature_hash is None
    finally:
        conn.close()

    # No CSV emitted on error.
    csvs = list(cfg.paths.finviz_inbox_dir.glob("finviz*.csv"))
    assert csvs == []


def test_step_finviz_fetch_records_error_when_token_missing(tmp_path: Path) -> None:
    """Config-missing path: token empty → no API call; row='error'."""
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path, token="")
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        with patch("swing.integrations.finviz_api.FinvizClient.fetch_screen") as mock_fetch:
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
            mock_fetch.assert_not_called()
        rows = list_recent_calls(conn)
        assert rows[0].status == "error"
        assert "token" in (rows[0].error_message or "").lower()
        # Discriminating: token literal absent (it was empty here, but
        # discipline rules: error_message is short + names the field).
        assert len(rows[0].error_message or "") < 256
    finally:
        conn.close()


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_step_finviz_fetch_warns_on_signature_drift(tmp_path: Path, caplog) -> None:
    """Drift detection: prior call's signature differs from new fetch → WARNING log."""
    import logging

    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import insert_call
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        # Seed a prior signature DIFFERENT from what the cassette will produce.
        insert_call(conn, FinvizApiCall(
            call_id=None, ts="2026-05-04T12:00:00",
            screen_query="v=152", status="ok", row_count=10,
            response_time_ms=200, rate_limit_remaining=100,
            signature_hash="0" * 64,  # known wrong; cassette will produce real hash
            error_message=None,
        ))

        with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        # Discriminating: WARNING fires.
        drift_warnings = [
            r for r in caplog.records
            if "signature changed" in r.getMessage().lower()
        ]
        assert len(drift_warnings) == 1, [r.getMessage() for r in caplog.records]
    finally:
        conn.close()


def test_step_finviz_fetch_lease_revoke_during_signature_read_downgrades_to_error(
    tmp_path: Path,
) -> None:
    """Codex R3/R4 fix: LeaseRevoked from the FIRST fenced_write (the prior-sig
    read) is caught by the file-work try/except → result downgraded to error →
    final fenced audit insert records the error truthfully → no canonical CSV
    + no shadow leftover (file work never started).

    Discriminating pre-fix (status='ok' eagerly recorded): audit row says ok.
    Discriminating post-fix (downgrade-on-exception): audit row says error.
    """
    from unittest.mock import MagicMock
    from swing.data.repos.pipeline import LeaseRevoked
    from swing.pipeline.runner import _step_finviz_fetch

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    db_conn = _setup_db(cfg)

    # Fake lease: FIRST fenced_write raises LeaseRevoked (simulated revoke
    # during the prior-signature read). The downgrade-to-error path then
    # uses the SECOND fenced_write to insert the audit row.
    call_count = [0]

    @contextlib.contextmanager
    def _fenced_write_iter():
        call_count[0] += 1
        if call_count[0] == 1:
            raise LeaseRevoked("simulated revoke during prior-sig read")
        yield db_conn

    fake_lease = MagicMock()
    fake_lease.fenced_write = _fenced_write_iter

    with patch(
        "swing.integrations.finviz_api.requests.get",
        return_value=MagicMock(
            status_code=200, headers={},
            content=(
                b"No.,Ticker,Sector,Industry,Country,Price,Change,"
                b"Average Volume,Relative Volume,Average True Range,"
                b"52-Week High,52-Week Low,Market Cap\n"
                b"1,AAPL,Tech,Software,USA,100,1%,1000,1,1,200,50,1B\n"
            ),
        ),
    ):
        # Does NOT raise — _step_finviz_fetch's file-work try/except catches
        # the first LeaseRevoked + downgrades to error; second fenced_write
        # (audit insert) then succeeds.
        _step_finviz_fetch(cfg=cfg, lease=fake_lease)

    # Discriminating: NO canonical CSV (file-work never executed beyond the
    # caught exception); NO shadow leftover.
    canonical_glob = list(cfg.paths.finviz_inbox_dir.glob("finviz*.csv"))
    assert canonical_glob == [], (
        f"orphan canonical after first-fenced revoke: "
        f"{[f.name for f in canonical_glob]}"
    )
    shadow_glob = list(cfg.paths.finviz_inbox_dir.glob("*.api-pending"))
    assert shadow_glob == [], (
        f"orphan shadow after first-fenced revoke: "
        f"{[f.name for f in shadow_glob]}"
    )
    # Discriminating: audit row inserted with status='error'.
    rows = list_recent_calls(db_conn)
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert "LeaseRevoked" in (rows[0].error_message or "")
    db_conn.close()


def test_step_finviz_fetch_lease_revoke_during_final_audit_propagates(
    tmp_path: Path,
) -> None:
    """Codex R4 fix (matching §A.13's lossy-audit-history failure case):
    LeaseRevoked from the FINAL fenced_write (the audit insert AFTER promote)
    propagates up — the canonical CSV is already on disk; the audit row is
    missing for this fetch.

    Discriminating: caller observes LeaseRevoked; canonical CSV exists;
    no shadow leftover. Next pipeline run will see the canonical as a
    manual-override (skipped_manual_override).
    """
    from unittest.mock import MagicMock
    from swing.data.repos.pipeline import LeaseRevoked
    from swing.pipeline.runner import _step_finviz_fetch

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    db_conn = _setup_db(cfg)

    # FIRST fenced_write succeeds (yields conn for prior-sig read);
    # SECOND fenced_write raises LeaseRevoked (audit insert blocked).
    call_count = [0]

    @contextlib.contextmanager
    def _fenced_write_iter():
        call_count[0] += 1
        if call_count[0] == 2:
            raise LeaseRevoked("simulated revoke at final audit insert")
        yield db_conn

    fake_lease = MagicMock()
    fake_lease.fenced_write = _fenced_write_iter

    with patch(
        "swing.integrations.finviz_api.requests.get",
        return_value=MagicMock(
            status_code=200, headers={},
            content=(
                b"No.,Ticker,Sector,Industry,Country,Price,Change,"
                b"Average Volume,Relative Volume,Average True Range,"
                b"52-Week High,52-Week Low,Market Cap\n"
                b"1,AAPL,Tech,Software,USA,100,1%,1000,1,1,200,50,1B\n"
            ),
        ),
    ):
        with pytest.raises(LeaseRevoked):
            _step_finviz_fetch(cfg=cfg, lease=fake_lease)

    # Discriminating: canonical EXISTS (promoted before audit insert tried);
    # no shadow leftover.
    canonical_glob = list(cfg.paths.finviz_inbox_dir.glob("finviz*.csv"))
    assert len(canonical_glob) == 1, (
        f"expected exactly one canonical CSV (promote happened before audit "
        f"raised); got {[f.name for f in canonical_glob]}"
    )
    shadow_glob = list(cfg.paths.finviz_inbox_dir.glob("*.api-pending"))
    assert shadow_glob == [], (
        f"orphan shadow after final-fenced revoke: "
        f"{[f.name for f in shadow_glob]}"
    )
    # Discriminating: NO audit row was inserted (the final fenced_write blocked).
    rows = list_recent_calls(db_conn)
    assert rows == [], (
        f"unexpected audit row after final-fenced revoke: {rows}"
    )
    db_conn.close()


def test_perform_finviz_fetch_no_lease_refuses_when_pipeline_running(tmp_path: Path) -> None:
    """Codex R2 Major-3 fix: standalone CLI fetch refuses if a pipeline run
    is in flight. Pre-fix (no check): proceeds, races on inbox + audit log.
    Post-fix (check): raises FinvizPipelineActiveError.

    Codex R3 Major-2 fix: column names match swing/data/migrations/0003 schema:
    `lease_heartbeat_ts` (NOT `heartbeat_ts`); `data_asof_date` and
    `action_session_date` are NOT NULL — fixture provides them.
    """
    from swing.integrations.finviz_api import FinvizPipelineActiveError
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        # Seed an active pipeline run (state='running'). Column names match
        # swing/data/migrations/0003_phase2_pipeline_trades.sql verbatim.
        conn.execute(
            "INSERT INTO pipeline_runs ("
            "  started_ts, trigger, data_asof_date, action_session_date,"
            "  state, lease_token, lease_heartbeat_ts"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-05-05T12:00:00", "manual",
                "2026-05-04", "2026-05-05",
                "running", "tok-test", "2026-05-05T12:00:00",
            ),
        )
        conn.commit()

        with pytest.raises(FinvizPipelineActiveError) as ei:
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        assert "in flight" in str(ei.value)
    finally:
        conn.close()


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_step_finviz_fetch_no_warn_when_signature_unchanged(tmp_path: Path, caplog) -> None:
    """No drift: prior signature matches → no WARNING."""
    import logging

    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        # First call to seed; then second call.
        _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        # Remove the emitted CSV so the second call goes through API path.
        for f in cfg.paths.finviz_inbox_dir.glob("finviz*.csv"):
            f.unlink()
        with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        # Discriminating: no signature-change warning.
        drift_warnings = [
            r for r in caplog.records
            if "signature changed" in r.getMessage().lower()
        ]
        assert len(drift_warnings) == 0
    finally:
        conn.close()


def test_perform_finviz_fetch_no_lease_records_error_on_mkdir_failure(
    tmp_path: Path,
) -> None:
    """Codex R1 Major-2: inbox-dir creation failure (PermissionError, OSError)
    MUST downgrade to status='error' with an audit row inserted, NOT escape
    as a generic exception that the outer wrapper logs as a programming error.

    Plan §A.13 / §H requires file-write failures to be downgraded; the audit
    row is the ground-truth signal. Discriminating pre-fix: mkdir(...) raises
    OSError → escape → no audit row inserted. Post-fix: caught at the top of
    `_finviz_fetch_core`; result downgraded; audit row inserted with
    status='error' and the OSError message in error_message.
    """
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    # DB exists; inbox dir does NOT exist; we'll patch mkdir to raise.
    cfg.paths.finviz_inbox_dir.parent.mkdir(parents=True, exist_ok=True)
    conn = ensure_schema(cfg.paths.db_path)
    try:
        # Patch Path.mkdir at the module level so the mkdir call inside
        # _finviz_fetch_core raises (the only mkdir reached during the test
        # run after this patch fires).
        original_mkdir = Path.mkdir

        def _failing_mkdir(self, *args, **kwargs):
            if self == cfg.paths.finviz_inbox_dir:
                raise PermissionError("simulated locked filesystem")
            return original_mkdir(self, *args, **kwargs)

        with patch.object(Path, "mkdir", _failing_mkdir):
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        rows = list_recent_calls(conn)
        # Discriminating: audit row exists, status='error', error_message names
        # PermissionError. Pre-fix: no rows (the helper escaped via OSError
        # before reaching insert_call).
        assert len(rows) == 1, rows
        assert rows[0].status == "error"
        assert "PermissionError" in (rows[0].error_message or "")
        assert "simulated locked filesystem" in (rows[0].error_message or "")
        # Discriminating: no canonical CSV emitted (mkdir failed).
        # finviz_inbox_dir doesn't exist, so we skip the glob check.
        assert not cfg.paths.finviz_inbox_dir.exists()
    finally:
        conn.close()
