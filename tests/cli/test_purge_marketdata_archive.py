# tests/cli/test_purge_marketdata_archive.py
from types import SimpleNamespace

import swing.config_overrides as _config_overrides
from click.testing import CliRunner

from swing.cli import main as cli  # the root click group
from swing.data.db import ensure_schema


def test_purge_deletes_only_schwab_api_parquets(tmp_path, monkeypatch):
    """Deterministic belt: deletes *.schwab_api.parquet so a later access
    re-fetches clean; leaves yfinance parquets untouched. L3-safe (archive is
    re-fetchable cache, not locked facts)."""
    cache = tmp_path / "prices"
    cache.mkdir()
    (cache / "AAPL.schwab_api.parquet").write_bytes(b"x")
    (cache / "MSFT.schwab_api.parquet").write_bytes(b"x")
    (cache / "AAPL.yfinance.parquet").write_bytes(b"y")

    # A real migrated DB so the command's pipeline-active guard (connect +
    # _check_pipeline_not_running) works without touching the operator's DB.
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()

    stub_cfg = SimpleNamespace(
        paths=SimpleNamespace(prices_cache_dir=cache, db_path=db_path))
    # The command does `from swing.config_overrides import apply_overrides`
    # at call time, so patching the source module's attribute injects our cfg
    # (mirrors tests/cli/test_reconcile_backfill_cli.py).
    monkeypatch.setattr(_config_overrides, "apply_overrides",
                        lambda _cfg: stub_cfg)

    runner = CliRunner()
    result = runner.invoke(cli, ["schwab", "purge-marketdata-archive", "--yes"])
    assert result.exit_code == 0, result.output
    assert not (cache / "AAPL.schwab_api.parquet").exists()
    assert not (cache / "MSFT.schwab_api.parquet").exists()
    assert (cache / "AAPL.yfinance.parquet").exists()  # yfinance preserved
    assert "2" in result.output  # reports the count deleted
