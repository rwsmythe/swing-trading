"""Tests for Shape A persistence (parquet-per-(ticker, provider)) in
``swing.data.ohlcv_archive`` — Schwab API Sub-bundle C T-C.2.

Covers:
- ``write_window`` writes Schwab + yfinance parquet files independently.
- ``write_window`` empty-window guard (no clobber on empty df) — both
  file-absent and file-present pre-states.
- ``resolve_ohlcv_window`` merge per ``_SOURCE_PRECEDENCE_MARKET_DATA``
  (schwab_api beats yfinance on same-date conflict).
- ``resolve_ohlcv_window`` handles single-provider files.
- ``resolve_ohlcv_window`` window-filter (start <= asof_date <= end)
  applied AFTER reading both files BEFORE winner selection.
- ``_backward_compat_rename`` 4 cases: old-only / both / new-only /
  neither, with MERGE-AND-QUARANTINE preserving every row when both exist.
- ``_backward_compat_rename`` idempotency.
- Defense-in-depth ``os.replace`` same-volume invariant.
- Per-provider file independence (writing one does not touch the other).

References:
- Plan §H.6.3 (`docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md`
  pseudocode block).
- Plan §A.8 Shape A LOCK + ``_SOURCE_PRECEDENCE_MARKET_DATA``.
- Codex R1 Major #6 (merge-and-quarantine on both-files-exist) + Major #7
  (empty-write guard) + Minor #4 (window-filter step); R2 Minor #1 (orphan
  quarantine).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import pytest


def _mk_window(asof_dates: list[str], close: float = 100.0) -> pd.DataFrame:
    """Build a Shape A window DataFrame keyed on an `asof_date` column.

    Columns: asof_date (ISO YYYY-MM-DD str) + OHLCV. Mirrors the post-mapping
    shape consumed by ``write_window`` from
    ``swing.integrations.schwab.mappers.map_price_history_to_window``.
    """
    return pd.DataFrame(
        {
            "asof_date": list(asof_dates),
            "open": [close] * len(asof_dates),
            "high": [close + 1.0] * len(asof_dates),
            "low": [close - 1.0] * len(asof_dates),
            "close": [close] * len(asof_dates),
            "volume": [1000] * len(asof_dates),
        }
    )


# ---------- _SOURCE_PRECEDENCE_MARKET_DATA -----------------------------------


def test_source_precedence_lower_wins_schwab_beats_yfinance():
    """Discriminating: lower integer = higher priority; schwab_api=0 wins
    against yfinance=1 in `min()`-by-precedence selection."""
    from swing.data.ohlcv_archive import _SOURCE_PRECEDENCE_MARKET_DATA

    assert _SOURCE_PRECEDENCE_MARKET_DATA["schwab_api"] == 0
    assert _SOURCE_PRECEDENCE_MARKET_DATA["yfinance"] == 1
    winner = min(
        ("schwab_api", "yfinance"),
        key=lambda p: _SOURCE_PRECEDENCE_MARKET_DATA[p],
    )
    assert winner == "schwab_api"


# ---------- write_window: per-provider independence --------------------------


def test_write_window_creates_per_provider_files_independently(tmp_path):
    """Writing Schwab does not affect yfinance file; writing yfinance does
    not affect Schwab file. Discriminating against any shared-path bug."""
    from swing.data.ohlcv_archive import write_window

    schwab_df = _mk_window(["2026-01-02", "2026-01-03"], close=100.0)
    yf_df = _mk_window(["2026-01-02", "2026-01-03"], close=200.0)

    write_window("AAPL", schwab_df, "schwab_api", cache_dir=tmp_path)
    assert (tmp_path / "AAPL.schwab_api.parquet").exists()
    assert not (tmp_path / "AAPL.yfinance.parquet").exists()

    write_window("AAPL", yf_df, "yfinance", cache_dir=tmp_path)
    assert (tmp_path / "AAPL.yfinance.parquet").exists()

    schwab_back = pd.read_parquet(tmp_path / "AAPL.schwab_api.parquet")
    yf_back = pd.read_parquet(tmp_path / "AAPL.yfinance.parquet")
    assert schwab_back["close"].iloc[0] == 100.0, (
        "writing yfinance file mutated schwab_api file — per-provider "
        "independence violated"
    )
    assert yf_back["close"].iloc[0] == 200.0


def test_write_window_ticker_is_normalized_to_uppercase(tmp_path):
    """Lowercase ticker passed in should be uppercased on disk to match the
    existing helper's convention (avoids split-cache footgun)."""
    from swing.data.ohlcv_archive import write_window

    write_window(
        "aapl", _mk_window(["2026-01-02"]), "schwab_api", cache_dir=tmp_path
    )
    parquet_names = sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".parquet")
    assert parquet_names == ["AAPL.schwab_api.parquet"], (
        f"expected AAPL.schwab_api.parquet on disk; got {parquet_names}"
    )


# ---------- write_window: empty-window guard ---------------------------------


def test_write_window_empty_dataframe_does_not_create_file(tmp_path):
    """Codex R1 Major #7: empty-window write MUST be a no-op (no file created)."""
    from swing.data.ohlcv_archive import write_window

    write_window(
        "AAPL", pd.DataFrame(), "schwab_api", cache_dir=tmp_path
    )
    assert not (tmp_path / "AAPL.schwab_api.parquet").exists(), (
        "empty-window write created a file — empty-write guard absent"
    )
    assert list(tmp_path.glob("*.parquet")) == []


def test_write_window_none_window_does_not_create_file(tmp_path):
    """Defense-in-depth: passing None as window must be a no-op too."""
    from swing.data.ohlcv_archive import write_window

    write_window(
        "AAPL", None, "schwab_api", cache_dir=tmp_path
    )
    assert not (tmp_path / "AAPL.schwab_api.parquet").exists()


def test_write_window_empty_does_not_clobber_existing_file(tmp_path):
    """**HIGH-VALUE DISCRIMINATING TEST** (per dispatch brief plan §A.9 #11):
    File present (populated) + empty df invoked → file UNCHANGED on disk.

    Sub-binding: this is the empty-API-result-must-be-transient pattern
    applied at the ladder write layer. A Schwab transient empty must not
    blank the Schwab parquet; yfinance fallback resolves the data.
    """
    from swing.data.ohlcv_archive import write_window

    populated = _mk_window(["2026-01-02", "2026-01-03"], close=100.0)
    write_window("AAPL", populated, "schwab_api", cache_dir=tmp_path)

    path = tmp_path / "AAPL.schwab_api.parquet"
    assert path.exists()
    pre_mtime = path.stat().st_mtime_ns
    pre_content = pd.read_parquet(path)

    # Now invoke with empty df — file must remain UNCHANGED.
    time.sleep(0.01)  # ensure mtime would differ if a write actually fired
    write_window("AAPL", pd.DataFrame(), "schwab_api", cache_dir=tmp_path)

    assert path.exists(), "empty-write deleted existing file — clobber bug"
    post_content = pd.read_parquet(path)
    pd.testing.assert_frame_equal(
        pre_content.reset_index(drop=True),
        post_content.reset_index(drop=True),
    )
    # mtime stability is informational; the content-equality assertion above
    # is the binding criterion.
    assert path.stat().st_mtime_ns == pre_mtime, (
        "empty-write mutated the file mtime — likely a stealth re-write"
    )


# ---------- resolve_ohlcv_window: merge + window-filter ----------------------


def test_resolve_merges_schwab_wins_on_same_date_conflict(tmp_path):
    """Same `asof_date` present in both parquet files → Schwab row wins per
    `_SOURCE_PRECEDENCE_MARKET_DATA`."""
    from swing.data.ohlcv_archive import resolve_ohlcv_window, write_window

    schwab_df = _mk_window(["2026-01-02"], close=100.0)
    yf_df = _mk_window(["2026-01-02"], close=200.0)
    write_window("AAPL", schwab_df, "schwab_api", cache_dir=tmp_path)
    write_window("AAPL", yf_df, "yfinance", cache_dir=tmp_path)

    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path
    )

    assert len(df) == 1
    assert float(df.iloc[0]["close"]) == 100.0, (
        f"yfinance row won on same-date conflict (close=200.0); "
        f"got close={df.iloc[0]['close']} — precedence ordering inverted"
    )
    assert provenance == {"2026-01-02": "schwab_api"}


def test_resolve_handles_only_schwab_present(tmp_path):
    """Only `{TICKER}.schwab_api.parquet` exists; yfinance file absent."""
    from swing.data.ohlcv_archive import resolve_ohlcv_window, write_window

    write_window(
        "AAPL",
        _mk_window(["2026-01-02", "2026-01-03"], close=100.0),
        "schwab_api",
        cache_dir=tmp_path,
    )

    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path
    )

    assert len(df) == 2
    assert set(provenance.values()) == {"schwab_api"}


def test_resolve_handles_only_yfinance_present(tmp_path):
    """Only `{TICKER}.yfinance.parquet` exists; Schwab file absent."""
    from swing.data.ohlcv_archive import resolve_ohlcv_window, write_window

    write_window(
        "AAPL",
        _mk_window(["2026-01-02", "2026-01-03"], close=200.0),
        "yfinance",
        cache_dir=tmp_path,
    )

    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path
    )

    assert len(df) == 2
    assert set(provenance.values()) == {"yfinance"}


def test_resolve_handles_missing_bars_in_one_provider(tmp_path):
    """Schwab has dates {01-02, 01-03}; yfinance has dates {01-03, 01-04}.
    Resolver union'd by date; Schwab wins 01-03; 01-02 from Schwab only;
    01-04 from yfinance only.
    """
    from swing.data.ohlcv_archive import resolve_ohlcv_window, write_window

    write_window(
        "AAPL",
        _mk_window(["2026-01-02", "2026-01-03"], close=100.0),
        "schwab_api",
        cache_dir=tmp_path,
    )
    write_window(
        "AAPL",
        _mk_window(["2026-01-03", "2026-01-04"], close=200.0),
        "yfinance",
        cache_dir=tmp_path,
    )

    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path
    )

    assert len(df) == 3
    assert provenance == {
        "2026-01-02": "schwab_api",
        "2026-01-03": "schwab_api",  # Schwab wins
        "2026-01-04": "yfinance",
    }
    # 01-03 row reflects the Schwab close, not the yfinance close.
    by_date = {row.asof_date: row.close for row in df.itertuples()}
    assert by_date["2026-01-03"] == 100.0


def test_resolve_returns_empty_for_unknown_ticker(tmp_path):
    """No parquet files for ticker → empty DataFrame, empty provenance."""
    from swing.data.ohlcv_archive import resolve_ohlcv_window

    df, provenance = resolve_ohlcv_window(
        "UNKNOWN", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path
    )
    assert len(df) == 0
    assert provenance == {}


def test_resolve_applies_window_filter_strictly(tmp_path):
    """Codex R1 Minor #4: plant 3 rows at [2026-01-01, 2026-01-15, 2026-02-01].
    Query window [2026-01-10, 2026-01-20]. Resolver returns ONLY 2026-01-15
    (the row inside the window). The filter MUST be applied AFTER reading
    both parquets BEFORE winner selection (so out-of-range rows don't pollute
    the merge decision, though that's vacuous when only one provider is
    present — kept as defense-in-depth for the both-providers case).
    """
    from swing.data.ohlcv_archive import resolve_ohlcv_window, write_window

    write_window(
        "AAPL",
        _mk_window(["2026-01-01", "2026-01-15", "2026-02-01"]),
        "yfinance",
        cache_dir=tmp_path,
    )

    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-10", end="2026-01-20", cache_dir=tmp_path
    )

    assert len(df) == 1, (
        f"window-filter not applied — expected 1 row in [2026-01-10, "
        f"2026-01-20]; got {len(df)} rows"
    )
    assert df.iloc[0]["asof_date"] == "2026-01-15"
    assert provenance == {"2026-01-15": "yfinance"}


# ---------- _backward_compat_rename ------------------------------------------


def test_backward_compat_rename_old_only_renames_to_yfinance(tmp_path):
    """Old `{TICKER}.parquet` exists; `{TICKER}.yfinance.parquet` absent →
    rename via `os.replace`. Discriminates against any plain-copy +
    leave-old or any creation of a new schwab_api file."""
    from swing.data.ohlcv_archive import _backward_compat_rename

    old_path = tmp_path / "AAPL.parquet"
    _mk_window(["2026-01-02"], close=100.0).to_parquet(old_path)

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    assert not old_path.exists(), "old AAPL.parquet still exists after rename"
    new_path = tmp_path / "AAPL.yfinance.parquet"
    assert new_path.exists(), "AAPL.yfinance.parquet not created"
    df = pd.read_parquet(new_path)
    assert float(df.iloc[0]["close"]) == 100.0


def test_backward_compat_rename_both_exist_merges_and_quarantines(tmp_path):
    """Codex R1 Major #6 + R2 Minor #1: both files exist → MERGE-AND-QUARANTINE.

    Plant:
      - Old `{TICKER}.parquet` with dates [01-02 close=100, 01-03 close=100].
      - New `{TICKER}.yfinance.parquet` with dates [01-03 close=200, 01-04 close=200].

    Expected post-state:
      - `{TICKER}.yfinance.parquet` contains merged content (3 unique dates;
        01-03 row carries new file's row, i.e. close=200 — `keep='last'`).
      - Orphan file `{TICKER}.parquet.orphan-<timestamp>.parquet` exists.
      - Old `{TICKER}.parquet` no longer exists.
      - NO data loss (every original row, modulo dedup, preserved).
    """
    from swing.data.ohlcv_archive import _backward_compat_rename

    old_path = tmp_path / "AAPL.parquet"
    new_path = tmp_path / "AAPL.yfinance.parquet"
    old_df = _mk_window(["2026-01-02", "2026-01-03"], close=100.0)
    new_df = _mk_window(["2026-01-03", "2026-01-04"], close=200.0)
    old_df.to_parquet(old_path)
    new_df.to_parquet(new_path)

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    # Old file is gone (renamed to orphan).
    assert not old_path.exists()
    # New file still exists, now with merged content.
    assert new_path.exists()
    merged = pd.read_parquet(new_path).set_index("asof_date")
    assert sorted(merged.index.tolist()) == ["2026-01-02", "2026-01-03", "2026-01-04"]
    # 01-03 conflict: new file's row wins under keep='last'.
    assert merged.loc["2026-01-03", "close"] == 200.0, (
        "merge `keep='last'` not honored — new yfinance.parquet's row should "
        f"win on conflict; got close={merged.loc['2026-01-03', 'close']}"
    )
    # 01-02 came from old; 01-04 came from new — neither dropped.
    assert merged.loc["2026-01-02", "close"] == 100.0
    assert merged.loc["2026-01-04", "close"] == 200.0

    # Orphan file present.
    orphans = sorted(tmp_path.glob("AAPL.parquet.orphan-*.parquet"))
    assert len(orphans) == 1, (
        f"expected exactly one orphan file; got {[p.name for p in orphans]}"
    )
    orphan_back = pd.read_parquet(orphans[0])
    # Orphan preserves the pre-merge old-file content verbatim.
    assert sorted(orphan_back["asof_date"].tolist()) == ["2026-01-02", "2026-01-03"]

    # Resolver MUST NOT read the orphan file.
    from swing.data.ohlcv_archive import resolve_ohlcv_window
    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path
    )
    assert len(df) == 3
    # All rows attributed to yfinance (orphan not consulted).
    assert set(provenance.values()) == {"yfinance"}


def test_backward_compat_rename_new_only_is_noop(tmp_path):
    """Only `{TICKER}.yfinance.parquet` present (already migrated) → no-op."""
    from swing.data.ohlcv_archive import _backward_compat_rename

    new_path = tmp_path / "AAPL.yfinance.parquet"
    _mk_window(["2026-01-02"], close=100.0).to_parquet(new_path)
    pre_mtime = new_path.stat().st_mtime_ns
    pre_files = sorted(p.name for p in tmp_path.iterdir())

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    assert new_path.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == pre_files
    assert new_path.stat().st_mtime_ns == pre_mtime, (
        "new-only branch mutated file mtime — should have been a no-op"
    )


def test_backward_compat_rename_neither_exists_is_noop(tmp_path):
    """Neither file present (first-fetch case) → no-op; no files created."""
    from swing.data.ohlcv_archive import _backward_compat_rename

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_backward_compat_rename_is_idempotent(tmp_path):
    """Codex R1 Major #6: invoke twice; second invocation MUST be no-op
    because the first transitioned the state to new-only."""
    from swing.data.ohlcv_archive import _backward_compat_rename

    old_path = tmp_path / "AAPL.parquet"
    _mk_window(["2026-01-02"], close=100.0).to_parquet(old_path)

    _backward_compat_rename("AAPL", cache_dir=tmp_path)
    files_after_first = sorted(p.name for p in tmp_path.iterdir())
    new_path = tmp_path / "AAPL.yfinance.parquet"
    mtime_after_first = new_path.stat().st_mtime_ns

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    files_after_second = sorted(p.name for p in tmp_path.iterdir())
    assert files_after_second == files_after_first, (
        "second invocation changed the file set — idempotency violated"
    )
    assert new_path.stat().st_mtime_ns == mtime_after_first, (
        "second invocation rewrote the yfinance.parquet — idempotency violated"
    )


def test_backward_compat_rename_uses_same_volume_for_os_replace(tmp_path):
    """CLAUDE.md `os.replace` cross-device gotcha defense-in-depth:
    both source and destination MUST be inside the SAME `cache_dir`
    (same volume) so the rename never traverses filesystems."""
    from swing.data.ohlcv_archive import _backward_compat_rename

    old_path = tmp_path / "AAPL.parquet"
    _mk_window(["2026-01-02"]).to_parquet(old_path)

    # Sentinel: record the dir hosting the rename's destination.
    captured: dict = {}
    real_replace = os.replace

    def sentinel_replace(src, dst):
        captured["src_parent"] = Path(src).parent
        captured["dst_parent"] = Path(dst).parent
        return real_replace(src, dst)

    import swing.data.ohlcv_archive as mod
    orig = mod.os.replace
    mod.os.replace = sentinel_replace
    try:
        _backward_compat_rename("AAPL", cache_dir=tmp_path)
    finally:
        mod.os.replace = orig

    assert captured["src_parent"] == tmp_path
    assert captured["dst_parent"] == tmp_path, (
        "os.replace destination dir != cache_dir — cross-device link risk per "
        "CLAUDE.md gotcha"
    )


# ---------- High-value discriminating: empty-Schwab-does-not-clobber ---------


def test_high_value_empty_schwab_fallback_preserves_schwab_archive(tmp_path):
    """**HIGH-VALUE DISCRIMINATING TEST** per dispatch brief (plan §A.9 #11):

    Plant Schwab parquet with prior data. Simulate a subsequent ladder call
    where Schwab returned empty (mapper raises SchwabApiError → ladder
    routes to yfinance and would in a naive impl invoke
    ``write_window(ticker, empty_df, 'schwab_api')`` to "clear" Schwab —
    the empty-write guard MUST prevent that.

    Discriminates: assert Schwab parquet is NOT clobbered by the empty
    write; yfinance fallback content is independent and unaffected.
    """
    from swing.data.ohlcv_archive import resolve_ohlcv_window, write_window

    # Pre-state: Schwab archive populated with one row.
    write_window(
        "AAPL",
        _mk_window(["2026-01-02"], close=100.0),
        "schwab_api",
        cache_dir=tmp_path,
    )
    schwab_path = tmp_path / "AAPL.schwab_api.parquet"
    pre_content = pd.read_parquet(schwab_path)

    # Simulated empty Schwab response — guard must prevent clobber.
    write_window("AAPL", pd.DataFrame(), "schwab_api", cache_dir=tmp_path)

    # Schwab parquet UNCHANGED.
    assert schwab_path.exists()
    post_content = pd.read_parquet(schwab_path)
    pd.testing.assert_frame_equal(
        pre_content.reset_index(drop=True),
        post_content.reset_index(drop=True),
    )

    # yfinance fallback path: write yfinance content; resolver returns un-clobbered
    # Schwab data on overlapping dates + yfinance data otherwise.
    write_window(
        "AAPL",
        _mk_window(["2026-01-02", "2026-01-03"], close=200.0),
        "yfinance",
        cache_dir=tmp_path,
    )

    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path
    )
    # 01-02: Schwab present (close=100); 01-03: only yfinance (close=200).
    by_date = {row.asof_date: row.close for row in df.itertuples()}
    assert by_date["2026-01-02"] == 100.0, (
        "Schwab data was clobbered by empty-write — high-value discriminating "
        "test failed"
    )
    assert by_date["2026-01-03"] == 200.0
    assert provenance == {
        "2026-01-02": "schwab_api",
        "2026-01-03": "yfinance",
    }


# ---------- Codex R1 Major #2: legacy DatetimeIndex normalization ------------


def _mk_legacy_datetimeindex_window(
    dates: list[str], close: float = 100.0,
) -> pd.DataFrame:
    """Build a legacy-yfinance-archive-shaped DataFrame.

    Mirrors what ``_yf_download_window`` produces + ``_persist_archive_atomic``
    writes: DatetimeIndex (named ``Date`` after ``reset_index``) + CAPITALIZED
    OHLCV columns. NOT Shape A (no ``asof_date`` column, capitalized names).
    """
    idx = pd.to_datetime(dates)
    return pd.DataFrame(
        {
            "Open": [close] * len(dates),
            "High": [close + 1.0] * len(dates),
            "Low": [close - 1.0] * len(dates),
            "Close": [close] * len(dates),
            "Volume": [1000] * len(dates),
        },
        index=idx,
    )


def test_normalize_legacy_dataframe_converts_datetimeindex_to_shape_a():
    """Codex R1 Major #2 unit test: ``_normalize_legacy_dataframe`` converts
    a legacy DatetimeIndex archive (capitalized cols, no ``asof_date``) into
    Shape A (lowercase cols + ``asof_date`` ISO string column).
    """
    from swing.data.ohlcv_archive import _normalize_legacy_dataframe

    legacy = _mk_legacy_datetimeindex_window(["2026-01-02", "2026-01-03"], 100.0)
    # Pre-state: capitalized cols + DatetimeIndex; NO asof_date column.
    assert "asof_date" not in legacy.columns
    assert "Close" in legacy.columns
    assert pd.api.types.is_datetime64_any_dtype(legacy.index)

    normalized = _normalize_legacy_dataframe(legacy)

    # Post-state: Shape A — `asof_date` ISO-string column + lowercase OHLCV.
    assert "asof_date" in normalized.columns
    assert normalized["asof_date"].tolist() == ["2026-01-02", "2026-01-03"]
    assert all(
        col in normalized.columns
        for col in ("open", "high", "low", "close", "volume")
    )
    # Capitalized column names removed (renamed to lowercase).
    for cap in ("Open", "High", "Low", "Close", "Volume"):
        assert cap not in normalized.columns


def test_normalize_legacy_dataframe_is_idempotent_on_shape_a():
    """Re-invoking on a Shape A frame is a no-op (returns unchanged).
    Discriminates: post-call the frame has the same columns + values."""
    from swing.data.ohlcv_archive import _normalize_legacy_dataframe

    shape_a = _mk_window(["2026-01-02"], close=100.0)
    out = _normalize_legacy_dataframe(shape_a)
    pd.testing.assert_frame_equal(shape_a, out)


def test_backward_compat_rename_normalizes_real_legacy_datetimeindex_shape(
    tmp_path,
):
    """**Codex R1 Major #2 discriminating test:** plant a REAL legacy
    DatetimeIndex parquet (no ``asof_date`` column; capitalized OHLCV cols);
    invoke ``_backward_compat_rename``; assert the resulting
    ``{TICKER}.yfinance.parquet`` is READABLE by ``resolve_ohlcv_window``
    + returns the rows (under the prior broken behavior, the post-rename
    file lacks an ``asof_date`` column and ``resolve_ohlcv_window`` skips
    it at lines 360-362, returning empty).

    Pre-fix behavior: ``resolve_ohlcv_window(...)`` returns empty DataFrame.
    Post-fix behavior: returns 2 rows attributed to ``'yfinance'`` provider.
    """
    from swing.data.ohlcv_archive import (
        _backward_compat_rename,
        resolve_ohlcv_window,
    )

    legacy = _mk_legacy_datetimeindex_window(
        ["2026-01-02", "2026-01-03"], close=100.0,
    )
    old_path = tmp_path / "AAPL.parquet"
    legacy.to_parquet(old_path)
    # Sanity: planted file is legacy-shaped (no asof_date column).
    planted = pd.read_parquet(old_path)
    assert "asof_date" not in planted.columns

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    new_path = tmp_path / "AAPL.yfinance.parquet"
    assert new_path.exists(), "rename failed to produce yfinance parquet"
    assert not old_path.exists(), "legacy parquet not unlinked post-rename"

    # The KEY discriminating assertion: resolver returns the rows.
    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path,
    )
    assert len(df) == 2, (
        "_backward_compat_rename did not normalize legacy DatetimeIndex → "
        "Shape A; resolver sees the file as missing asof_date column and "
        f"returns 0 rows (post-fix expected 2). Codex R1 Major #2 regression."
    )
    assert sorted(df["asof_date"].tolist()) == ["2026-01-02", "2026-01-03"]
    assert set(provenance.values()) == {"yfinance"}
    # Lowercase OHLCV columns post-normalization.
    assert "close" in df.columns
    assert float(df.iloc[0]["close"]) == 100.0


def test_backward_compat_rename_merges_legacy_datetimeindex_with_shape_a(
    tmp_path,
):
    """Both-exist branch when OLD is legacy DatetimeIndex + NEW is Shape A.

    Plant:
      - Old ``AAPL.parquet`` legacy DatetimeIndex with [01-02 close=100,
        01-03 close=100].
      - New ``AAPL.yfinance.parquet`` Shape A with [01-03 close=200,
        01-04 close=200].

    Post-rename:
      - Merge: 3 unique dates; 01-03 conflict won by NEW (close=200).
      - Resolver returns 3 rows attributed to ``'yfinance'``.
    """
    from swing.data.ohlcv_archive import (
        _backward_compat_rename,
        resolve_ohlcv_window,
    )

    legacy = _mk_legacy_datetimeindex_window(
        ["2026-01-02", "2026-01-03"], close=100.0,
    )
    shape_a = _mk_window(["2026-01-03", "2026-01-04"], close=200.0)
    (tmp_path / "AAPL.parquet").write_bytes(b"")  # placeholder for clarity
    legacy.to_parquet(tmp_path / "AAPL.parquet")
    shape_a.to_parquet(tmp_path / "AAPL.yfinance.parquet")

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path,
    )
    assert sorted(df["asof_date"].tolist()) == [
        "2026-01-02", "2026-01-03", "2026-01-04",
    ]
    by_date = {row.asof_date: row.close for row in df.itertuples()}
    # 01-03 conflict: new file wins (keep='last' in pd.concat dedup).
    assert by_date["2026-01-03"] == 200.0
    assert by_date["2026-01-02"] == 100.0
    assert by_date["2026-01-04"] == 200.0
    assert set(provenance.values()) == {"yfinance"}
