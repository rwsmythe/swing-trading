from pathlib import Path
from types import SimpleNamespace

from swing.data.db import ensure_schema
from swing.pipeline import runner


class _FakeClient:
    """Minimal stand-in so _install_pipeline_marketdata_caches builds hooks.

    Never invoked at install time -- the install only constructs the caches,
    opens the shared audit connection, and registers the ladder hooks.
    """


def _make_cfg(db_path: Path, tmp_path: Path, *, busy_timeout_ms: int):
    paths_ns = SimpleNamespace(
        db_path=Path(db_path),
        prices_cache_dir=tmp_path / "prices-cache",
    )
    paths_ns.prices_cache_dir.mkdir(parents=True, exist_ok=True)
    schwab_ns = SimpleNamespace(environment="production", marketdata_ladder_enabled=True)
    web_ns = SimpleNamespace(
        ohlcv_cache_ttl_seconds=3600,
        max_concurrent_ohlcv_fetches=4,
        circuit_breaker_cooldown_seconds=60,
        db_busy_timeout_ms=busy_timeout_ms,
    )
    return SimpleNamespace(
        paths=paths_ns,
        integrations=SimpleNamespace(schwab=schwab_ns),
        web=web_ns,
        archive=SimpleNamespace(archive_history_days=1260),
    )


def test_install_returns_shared_audit_conn_with_knob_busy_timeout(tmp_path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    cfg = _make_cfg(db, tmp_path, busy_timeout_ms=21000)

    price_cache, ohlcv_cache, audit_conn = runner._install_pipeline_marketdata_caches(
        cfg, _FakeClient(), pipeline_run_id=None,
    )
    try:
        assert audit_conn is not None
        # OQ-A: the shared audit conn's busy_timeout comes from the cfg knob.
        assert audit_conn.execute("PRAGMA busy_timeout").fetchone()[0] == 21000
    finally:
        if audit_conn is not None:
            audit_conn.close()


def test_install_returns_none_triple_without_client(tmp_path):
    cfg = SimpleNamespace()  # not consulted when client is None
    price_cache, ohlcv_cache, audit_conn = runner._install_pipeline_marketdata_caches(
        cfg, None, pipeline_run_id=None,
    )
    assert (price_cache, ohlcv_cache, audit_conn) == (None, None, None)
