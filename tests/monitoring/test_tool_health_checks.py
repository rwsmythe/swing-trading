"""Tasks 2/3/4 -- the three per-check helpers (boundary regression arithmetic).

Inputs derive from the REAL repo readers + real schema (anti-drift): a seeded
on-disk SQLite built via ensure_schema + the production repo inserts, so each
check exercises the production read path.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

import pytest

from swing.config import Config
from swing.data.db import connect, ensure_schema
from swing.data.repos.pipeline import (
    finalize_run,
    force_clear,
    insert_pipeline_run,
)
from swing.evaluation.dates import action_session_for_run
from swing.monitoring.tool_health import (
    _check_pipeline_run,
    _check_schwab_token,
)


def _seeded_conn(tmp_path):
    """A schema-current on-disk DB conn (rw)."""
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()
    return connect(db_path)


def _check_by_key(checks, key):
    for c in checks:
        if c.key == key:
            return c
    raise AssertionError(f"no check with key {key!r}; got {[c.key for c in checks]}")


def _insert_complete_run(conn, *, action_session_date, started_ts="2026-06-14T00:00:00"):
    run_id, token = insert_pipeline_run(
        conn,
        started_ts=started_ts,
        trigger="manual",
        data_asof_date=action_session_date,
        action_session_date=action_session_date,
        lease_heartbeat_ts=started_ts,
    )
    finalize_run(
        conn, run_id=run_id, lease_token=token,
        state="complete", finished_ts=started_ts,
    )
    return run_id


def _insert_running_run(conn, *, heartbeat_ts, step_ts, action_session_date="2026-06-15"):
    run_id, token = insert_pipeline_run(
        conn,
        started_ts="2026-06-14T00:00:00",
        trigger="manual",
        data_asof_date=action_session_date,
        action_session_date=action_session_date,
        lease_heartbeat_ts=heartbeat_ts,
    )
    # insert_pipeline_run stamps last_step_progress_ts = lease_heartbeat_ts; set
    # both explicitly so the staleness math is deterministic.
    conn.execute(
        "UPDATE pipeline_runs SET lease_heartbeat_ts = ?, last_step_progress_ts = ? "
        "WHERE id = ?",
        (heartbeat_ts, step_ts, run_id),
    )
    return run_id, token


# ----------------------------- pipeline checks -----------------------------


def test_pipeline_freshness_green_when_current(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)  # Wed post-close -> action_session = Thu 06-18
    anchor = action_session_for_run(now)
    conn = _seeded_conn(tmp_path)
    with conn:
        _insert_complete_run(conn, action_session_date=anchor.isoformat())
    checks = _check_pipeline_run(conn, cfg=None, now=now)
    assert _check_by_key(checks, "pipeline_freshness").status == "green"


def test_pipeline_freshness_yellow_one_behind(tmp_path):
    # Wed 21:00 HST post-close -> action_session = Thu 06-18; prior session = Wed
    # 06-17. sessions_behind(06-18, 06-17) == 1 -> yellow (not green, not red).
    now = datetime(2026, 6, 17, 21, 0)
    conn = _seeded_conn(tmp_path)
    with conn:
        _insert_complete_run(conn, action_session_date="2026-06-17")
    checks = _check_pipeline_run(conn, cfg=None, now=now)
    assert _check_by_key(checks, "pipeline_freshness").status == "yellow"


def test_pipeline_freshness_red_two_behind(tmp_path):
    # action_session = Thu 06-18; two sessions behind = Tue 06-16 -> red.
    now = datetime(2026, 6, 17, 21, 0)
    conn = _seeded_conn(tmp_path)
    with conn:
        _insert_complete_run(conn, action_session_date="2026-06-16")
    checks = _check_pipeline_run(conn, cfg=None, now=now)
    assert _check_by_key(checks, "pipeline_freshness").status == "red"


def test_pipeline_freshness_red_when_no_complete_run(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)
    conn = _seeded_conn(tmp_path)
    # only a running row, no complete run
    with conn:
        _insert_running_run(conn, heartbeat_ts="2026-06-17T20:59:50",
                            step_ts="2026-06-17T20:59:50")
    check = _check_by_key(_check_pipeline_run(conn, cfg=None, now=now),
                          "pipeline_freshness")
    assert check.status == "red"
    assert "no completed" in check.summary.lower()


def test_pipeline_wedged_red_when_stale(tmp_path):
    # heartbeat age 400s > 300 AND step age 1000s > 900 -> wedged red.
    now = datetime(2026, 6, 17, 21, 0)
    cfg = Config.from_defaults()
    conn = _seeded_conn(tmp_path)
    hb = (now - timedelta(seconds=400)).isoformat()
    step = (now - timedelta(seconds=1000)).isoformat()
    with conn:
        _insert_complete_run(conn, action_session_date=action_session_for_run(now).isoformat())
        _insert_running_run(conn, heartbeat_ts=hb, step_ts=step)
    check = _check_by_key(_check_pipeline_run(conn, cfg=cfg, now=now), "pipeline_wedged")
    assert check.status == "red"


def test_pipeline_wedged_green_when_running_fresh(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)
    cfg = Config.from_defaults()
    conn = _seeded_conn(tmp_path)
    hb = (now - timedelta(seconds=10)).isoformat()
    with conn:
        _insert_complete_run(conn, action_session_date=action_session_for_run(now).isoformat())
        _insert_running_run(conn, heartbeat_ts=hb, step_ts=hb)
    check = _check_by_key(_check_pipeline_run(conn, cfg=cfg, now=now), "pipeline_wedged")
    assert check.status == "green"


def test_pipeline_wedged_green_when_cfg_none(tmp_path):
    # running + stale heartbeat but cfg=None -> green (degraded skip; no false red).
    now = datetime(2026, 6, 17, 21, 0)
    conn = _seeded_conn(tmp_path)
    hb = (now - timedelta(seconds=400)).isoformat()
    step = (now - timedelta(seconds=1000)).isoformat()
    with conn:
        _insert_running_run(conn, heartbeat_ts=hb, step_ts=step)
    check = _check_by_key(_check_pipeline_run(conn, cfg=None, now=now), "pipeline_wedged")
    assert check.status == "green"


def test_pipeline_failures_yellow(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)
    conn = _seeded_conn(tmp_path)
    with conn:
        _insert_complete_run(conn, action_session_date=action_session_for_run(now).isoformat())
        # two failed runs in the recent window
        for _ in range(2):
            rid, tok = insert_pipeline_run(
                conn, started_ts="2026-06-14T00:00:00", trigger="manual",
                data_asof_date="2026-06-14", action_session_date="2026-06-14",
                lease_heartbeat_ts="2026-06-14T00:00:00",
            )
            finalize_run(conn, run_id=rid, lease_token=tok,
                         state="failed", finished_ts="2026-06-14T00:01:00")
    check = _check_by_key(_check_pipeline_run(conn, cfg=None, now=now), "pipeline_failures")
    assert check.status == "yellow"
    assert "2 recent pipeline failure" in check.summary


def test_pipeline_failures_green_when_none(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)
    conn = _seeded_conn(tmp_path)
    with conn:
        _insert_complete_run(conn, action_session_date=action_session_for_run(now).isoformat())
    check = _check_by_key(_check_pipeline_run(conn, cfg=None, now=now), "pipeline_failures")
    assert check.status == "green"


def test_pipeline_failures_counts_force_cleared(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)
    conn = _seeded_conn(tmp_path)
    with conn:
        _insert_complete_run(conn, action_session_date=action_session_for_run(now).isoformat())
        rid, _ = _insert_running_run(conn, heartbeat_ts="2026-06-14T00:00:00",
                                     step_ts="2026-06-14T00:00:00")
        force_clear(conn, run_id=rid, error_message="wedged")
    check = _check_by_key(_check_pipeline_run(conn, cfg=None, now=now), "pipeline_failures")
    assert check.status == "yellow"


def test_pipeline_freshness_yellow_across_weekend(tmp_path):
    # frozen_now = Sunday 06-14 (NON-session) -> action_session = Mon 06-15;
    # sessions_behind(Mon 06-15, Fri 06-12) == 1 across the weekend -> yellow.
    # A calendar-day >=2 impl sees Fri->Mon = 3 days -> red -> FAIL.
    now = datetime(2026, 6, 14, 12, 0)  # Sunday
    assert action_session_for_run(now) == date(2026, 6, 15)
    conn = _seeded_conn(tmp_path)
    with conn:
        _insert_complete_run(conn, action_session_date="2026-06-12")  # Friday
    check = _check_by_key(_check_pipeline_run(conn, cfg=None, now=now), "pipeline_freshness")
    assert check.status == "yellow"


def test_pipeline_freshness_yellow_across_holiday(tmp_path):
    # frozen_now = Sunday 07-05 after the July 4 (Sat, observed Fri 07-03) holiday
    # -> action_session = Mon 07-06; prior session = Thu 07-02 (Fri 07-03 closed).
    # sessions_behind(Mon 07-06, Thu 07-02) == 1 across 4 calendar days -> yellow.
    now = datetime(2026, 7, 5, 12, 0)
    assert action_session_for_run(now) == date(2026, 7, 6)
    conn = _seeded_conn(tmp_path)
    with conn:
        _insert_complete_run(conn, action_session_date="2026-07-02")
    check = _check_by_key(_check_pipeline_run(conn, cfg=None, now=now), "pipeline_freshness")
    assert check.status == "yellow"


def test_pipeline_missing_table_degrades_yellow_not_crash():
    # bare :memory: conn with NO pipeline_runs table -> yellow "schema unavailable",
    # does NOT raise.
    conn = sqlite3.connect(":memory:")
    now = datetime(2026, 6, 17, 21, 0)
    checks = _check_pipeline_run(conn, cfg=None, now=now)
    assert len(checks) == 1
    assert checks[0].status == "yellow"
    assert "schema unavailable" in checks[0].summary.lower()


def test_pipeline_non_schema_operational_error_reraises(tmp_path, monkeypatch):
    # A non-"no such table" OperationalError must NOT be masked as schema-unavailable.
    now = datetime(2026, 6, 17, 21, 0)
    conn = _seeded_conn(tmp_path)

    def boom(_conn):
        raise sqlite3.OperationalError("database is locked")

    # The check lazy-imports the reader from swing.web.chart_scope; patch at source.
    monkeypatch.setattr(
        "swing.web.chart_scope.latest_completed_pipeline_run", boom
    )
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        _check_pipeline_run(conn, cfg=None, now=now)


# ------------------------------ schwab check -------------------------------

from datetime import UTC  # noqa: E402

_TTL = 7 * 24 * 3600
_WARN = 24 * 3600
_ERROR = 2 * 3600


class _SchwabStub:
    """Minimal cfg exposing only integrations.schwab.{environment,client_id}."""

    class _Schwab:
        def __init__(self, environment, client_id):
            self.environment = environment
            self.client_id = client_id

    class _Integrations:
        def __init__(self, schwab):
            self.schwab = schwab

    def __init__(self, *, environment="production", client_id="abc123"):
        self.integrations = self._Integrations(self._Schwab(environment, client_id))


def _tokens_path(home, env):
    return home / "swing-data" / f"schwab-tokens.{env}.db"


def _write_tokens_db(home, env, *, refresh_token_issued, table=True):
    """Build a v3-shape schwabdev tokens DB the production _read_tokens_metadata
    SELECTs (access_token_issued, refresh_token_issued, expires_in, refresh_token)."""
    path = _tokens_path(home, env)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        if table:
            conn.execute(
                "CREATE TABLE schwabdev (access_token_issued TEXT, "
                "refresh_token_issued TEXT, expires_in INTEGER, refresh_token TEXT)"
            )
            conn.execute(
                "INSERT INTO schwabdev VALUES (?, ?, ?, ?)",
                ("2026-06-14T00:00:00+00:00", refresh_token_issued, 1800,
                 "enc:secret-bytes"),
            )
        else:
            # no schwabdev table -> _read_tokens_metadata returns (None, <msg>).
            conn.execute("CREATE TABLE other (x INTEGER)")
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def _home(tmp_path, monkeypatch):
    # Monkeypatch BOTH USERPROFILE and HOME (the write_user_overrides gotcha) so
    # _user_home() resolves to tmp_path; no leak to the operator's real home.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _now_local():
    # naive Hawaii-local now (the aggregator's contract); fixed for determinism.
    return datetime(2026, 6, 14, 9, 0, 0)


def _now_utc_of(now_local):
    from zoneinfo import ZoneInfo
    return now_local.replace(tzinfo=ZoneInfo("Pacific/Honolulu")).astimezone(UTC)


def test_schwab_green_when_cfg_none(_home):
    checks = _check_schwab_token(cfg=None, now=_now_local())
    assert len(checks) == 1
    assert checks[0].status == "green"
    assert "n/a" in checks[0].summary.lower()


def test_schwab_green_when_client_id_empty(_home):
    cfg = _SchwabStub(client_id="")
    check = _check_schwab_token(cfg=cfg, now=_now_local())[0]
    assert check.status == "green"
    assert "n/a" in check.summary.lower()


def test_schwab_green_when_tokens_absent(_home):
    cfg = _SchwabStub(client_id="abc")
    check = _check_schwab_token(cfg=cfg, now=_now_local())[0]
    assert check.status == "green"
    assert "n/a" in check.summary.lower()


def test_schwab_yellow_at_24h_boundary(_home):
    # delta == WARN == 86400 exactly -> yellow (inclusive upper bound).
    # issued_utc = now_utc + WARN - TTL = now_utc - 6 days.
    now_local = _now_local()
    now_utc = _now_utc_of(now_local)
    issued = (now_utc - timedelta(seconds=_TTL - _WARN)).isoformat()
    _write_tokens_db(_home, "production", refresh_token_issued=issued)
    check = _check_schwab_token(cfg=_SchwabStub(), now=now_local)[0]
    assert check.status == "yellow"


def test_schwab_red_at_2h_boundary(_home):
    # delta == ERROR == 7200 exactly -> red (inclusive).
    now_local = _now_local()
    now_utc = _now_utc_of(now_local)
    issued = (now_utc - timedelta(seconds=_TTL - _ERROR)).isoformat()
    _write_tokens_db(_home, "production", refresh_token_issued=issued)
    check = _check_schwab_token(cfg=_SchwabStub(), now=now_local)[0]
    assert check.status == "red"


def test_schwab_red_when_expired(_home):
    now_local = _now_local()
    now_utc = _now_utc_of(now_local)
    issued = (now_utc - timedelta(days=8)).isoformat()  # > 7d TTL -> expired
    _write_tokens_db(_home, "production", refresh_token_issued=issued)
    check = _check_schwab_token(cfg=_SchwabStub(), now=now_local)[0]
    assert check.status == "red"
    assert "expired" in check.summary.lower()


def test_schwab_green_when_healthy(_home):
    # issued = now - 1d -> delta = 6d -> int(delta//86400) == 6 -> "6 day(s)".
    now_local = _now_local()
    now_utc = _now_utc_of(now_local)
    issued = (now_utc - timedelta(days=1)).isoformat()
    _write_tokens_db(_home, "production", refresh_token_issued=issued)
    check = _check_schwab_token(cfg=_SchwabStub(), now=now_local)[0]
    assert check.status == "green"
    assert "6 day(s)" in check.summary


def test_schwab_yellow_when_unreadable(_home):
    now_local = _now_local()
    _write_tokens_db(_home, "production", refresh_token_issued="x", table=False)
    check = _check_schwab_token(cfg=_SchwabStub(), now=now_local)[0]
    assert check.status == "yellow"
    assert "unreadable" in check.summary.lower()


def test_schwab_aware_iso_timestamp(_home):
    # Codex R1 MAJOR #1: the LIVE tokens file writes aware-UTC timestamps; pass a
    # NAIVE now. A naive-subtract impl raises TypeError; normalize-both returns.
    now_local = _now_local()  # naive
    issued = (datetime.now(UTC) - timedelta(days=1)).isoformat()  # aware
    _write_tokens_db(_home, "production", refresh_token_issued=issued)
    check = _check_schwab_token(cfg=_SchwabStub(), now=now_local)[0]
    assert check.status in {"green", "yellow", "red"}  # did not raise


def test_schwab_now_uses_local_tz_not_utc(_home):
    # Codex R2 MAJOR #1 (~10h shift). HST is UTC-10. Choose issued so the true
    # delta (now treated Hawaii-local) is JUST over 24h, but if now were wrongly
    # treated as UTC the delta would drop ~10h under 24h and flip green->yellow.
    #   true:   delta = TTL - (TTL - WARN - 5h) = WARN + 5h = 29h  -> green (>24h)
    #   wrong:  now_as_utc is 10h LATER than the true now_utc, so delta = 29h-10h
    #           = 19h -> yellow (<=24h).
    now_local = _now_local()
    now_utc = _now_utc_of(now_local)
    issued = (now_utc - timedelta(seconds=_TTL - _WARN - 5 * 3600)).isoformat()
    _write_tokens_db(_home, "production", refresh_token_issued=issued)
    check = _check_schwab_token(cfg=_SchwabStub(), now=now_local)[0]
    assert check.status == "green"
