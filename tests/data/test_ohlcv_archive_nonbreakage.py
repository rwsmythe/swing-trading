import inspect

import swing.data.ohlcv_archive as archive


def test_read_or_fetch_archive_signature_unchanged():
    """The shared fetch API is byte-identical (spec §5): the daily-management
    fetch-hoist must not change read_or_fetch_archive's parameters.

    Locks the FULL call shape — names, kinds (positional vs keyword-only),
    defaults, and order (Codex R1 MINOR) — so an appended parameter, a
    kind/default change, or a reorder after ``ticker`` would fail this lock,
    not just a missing-name change."""
    sig = inspect.signature(archive.read_or_fetch_archive)
    shape = [
        (p.name, p.kind.name, p.default is inspect.Parameter.empty)
        for p in sig.parameters.values()
    ]
    # The exact 4 call-shape params the warm + all 9 consumers rely on
    # (True == no default; all four are required):
    assert shape == [
        ("ticker", "POSITIONAL_OR_KEYWORD", True),
        ("end_date", "KEYWORD_ONLY", True),
        ("cache_dir", "KEYWORD_ONLY", True),
        ("archive_history_days", "KEYWORD_ONLY", True),
    ]


def test_no_new_public_symbol_added_to_ohlcv_archive():
    """OQ-2 pass-bars-in adds NO archive-API surface: SnapshotComputeResult lives
    in swing.trades.daily_management, not here."""
    assert not hasattr(archive, "SnapshotComputeResult")
    # The typed result is exported from the trades module instead:
    from swing.trades.daily_management import SnapshotComputeResult  # noqa: F401
