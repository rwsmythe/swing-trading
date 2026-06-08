import inspect

import swing.data.ohlcv_archive as archive


def test_read_or_fetch_archive_signature_unchanged():
    """The shared fetch API is byte-identical (spec §5): the daily-management
    fetch-hoist must not change read_or_fetch_archive's parameters."""
    sig = inspect.signature(archive.read_or_fetch_archive)
    params = list(sig.parameters)
    # The 4 call-shape params the warm + all 9 consumers rely on:
    assert params[0] == "ticker"
    assert "end_date" in params
    assert "cache_dir" in params
    assert "archive_history_days" in params


def test_no_new_public_symbol_added_to_ohlcv_archive():
    """OQ-2 pass-bars-in adds NO archive-API surface: SnapshotComputeResult lives
    in swing.trades.daily_management, not here."""
    assert not hasattr(archive, "SnapshotComputeResult")
    # The typed result is exported from the trades module instead:
    from swing.trades.daily_management import SnapshotComputeResult  # noqa: F401
