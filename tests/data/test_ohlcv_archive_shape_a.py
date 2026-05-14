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


# ---------- Codex R2 Major #2: write_window merge-by-asof_date semantics -----


def test_write_window_merges_preserves_rows_outside_incoming_window(tmp_path):
    """**Codex R2 Major #2 KEY DISCRIMINATING TEST.**

    Plant `{TICKER}.schwab_api.parquet` with 100 rows spanning
    [2026-01-01, 2026-04-10]. Call `write_window(ticker, small_window_df,
    'schwab_api', cache_dir)` where `small_window_df` has 5 rows in
    [2026-03-01, 2026-03-05]. Post-write parquet MUST have 100 rows (NOT 5):
    95 rows OUTSIDE the incoming window preserved + 5 NEW rows replacing
    the originals on the overlapping dates.

    Pre-fix (REPLACE semantics): the parquet had 5 rows after the write —
    a tiny verification fetch would silently destroy a 5-year archive.
    Post-fix (merge-by-asof_date): outside-window rows preserved.
    """
    from swing.data.ohlcv_archive import write_window

    # 100 rows spanning Jan-Apr 2026 (every weekday-ish; just a count for the
    # test). All rows mark close=100.0 so we can detect which rows survive.
    dates_existing = [
        f"2026-{m:02d}-{d:02d}"
        for m, days in [(1, 31), (2, 28), (3, 31), (4, 10)]
        for d in range(1, days + 1)
    ]
    assert len(dates_existing) == 100
    existing_df = _mk_window(dates_existing, close=100.0)
    write_window("AAPL", existing_df, "schwab_api", cache_dir=tmp_path)

    # Sanity: file has 100 rows pre-call.
    path = tmp_path / "AAPL.schwab_api.parquet"
    assert len(pd.read_parquet(path)) == 100

    # Tiny incoming window: 5 rows in March, with DIFFERENT close to detect
    # which row wins on conflict.
    small_window = _mk_window(
        ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05"],
        close=999.0,
    )
    write_window("AAPL", small_window, "schwab_api", cache_dir=tmp_path)

    # KEY assertion: 100 rows preserved (95 outside + 5 from incoming window).
    post = pd.read_parquet(path)
    assert len(post) == 100, (
        f"Codex R2 Major #2: write_window OVERWROTE the archive — "
        f"post-write has {len(post)} rows (expected 100). Merge-by-asof_date "
        "semantics missing."
    )
    by_date = {row["asof_date"]: row["close"] for _, row in post.iterrows()}
    # March 1-5: NEW rows won (close=999.0).
    for d in ("2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05"):
        assert by_date[d] == 999.0, (
            f"R2 Major #2: NEW row did not win on conflict for {d} "
            f"(got close={by_date[d]}; expected 999.0)"
        )
    # Outside the incoming window: ORIGINAL rows preserved.
    for d in ("2026-01-01", "2026-02-15", "2026-03-15", "2026-04-10"):
        assert by_date[d] == 100.0, (
            f"R2 Major #2: outside-window row at {d} was dropped or mutated "
            f"(got close={by_date[d]}; expected 100.0)"
        )


def test_write_window_merge_new_wins_on_overlapping_dates(tmp_path):
    """Codex R2 Major #2: on overlapping `asof_date`, NEW row wins.
    `keep='last'` in the dedup. Discriminates against `keep='first'` /
    no-dedup."""
    from swing.data.ohlcv_archive import write_window

    write_window(
        "AAPL",
        _mk_window(["2026-01-02", "2026-01-03"], close=100.0),
        "schwab_api",
        cache_dir=tmp_path,
    )
    # All overlapping; new close=200.0 must win.
    write_window(
        "AAPL",
        _mk_window(["2026-01-02", "2026-01-03"], close=200.0),
        "schwab_api",
        cache_dir=tmp_path,
    )

    path = tmp_path / "AAPL.schwab_api.parquet"
    post = pd.read_parquet(path)
    assert len(post) == 2, (
        f"merge produced wrong row count (got {len(post)}; expected 2 "
        "with all dates overlapping)"
    )
    for _, row in post.iterrows():
        assert row["close"] == 200.0, (
            f"R2 Major #2: NEW row should win on conflict; got "
            f"close={row['close']} for asof_date={row['asof_date']}"
        )


def test_write_window_merge_is_sorted_ascending_by_asof_date(tmp_path):
    """Codex R2 Major #2: merged frame MUST be sorted ascending by
    `asof_date`. Discriminates against no-sort / descending sort."""
    from swing.data.ohlcv_archive import write_window

    # Write in random (non-sorted) order.
    write_window(
        "AAPL",
        _mk_window(["2026-01-05", "2026-01-01", "2026-01-03"], close=100.0),
        "schwab_api",
        cache_dir=tmp_path,
    )
    # Add more out-of-order rows.
    write_window(
        "AAPL",
        _mk_window(["2026-01-04", "2026-01-02"], close=100.0),
        "schwab_api",
        cache_dir=tmp_path,
    )

    path = tmp_path / "AAPL.schwab_api.parquet"
    post = pd.read_parquet(path)
    assert list(post["asof_date"]) == [
        "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05",
    ], (
        "R2 Major #2: merged frame NOT sorted ascending by asof_date; "
        f"got order={list(post['asof_date'])}"
    )


def test_write_window_merge_idempotent_double_write(tmp_path):
    """Codex R2 Major #2: writing the same df twice produces a single
    canonical state (deduped) — not 2x rows."""
    from swing.data.ohlcv_archive import write_window

    df = _mk_window(["2026-01-02", "2026-01-03"], close=100.0)
    write_window("AAPL", df, "schwab_api", cache_dir=tmp_path)
    write_window("AAPL", df, "schwab_api", cache_dir=tmp_path)

    path = tmp_path / "AAPL.schwab_api.parquet"
    post = pd.read_parquet(path)
    assert len(post) == 2, (
        f"R2 Major #2: double-write produced {len(post)} rows (expected 2 "
        "deduped)"
    )
    assert sorted(post["asof_date"].tolist()) == ["2026-01-02", "2026-01-03"]


def test_write_window_empty_window_with_existing_file_still_no_op(tmp_path):
    """Codex R2 Major #2 regression guard: the existing empty-write guard
    (R1 Major #7) MUST still short-circuit BEFORE the merge logic. An empty
    df with a pre-existing populated parquet leaves the parquet UNCHANGED.

    Pre-existing test ``test_write_window_empty_does_not_clobber_existing_file``
    covers this for REPLACE semantics; we re-verify it under merge semantics
    (the empty-write guard short-circuits before the merge branch runs).
    """
    from swing.data.ohlcv_archive import write_window

    populated = _mk_window(["2026-01-02", "2026-01-03"], close=100.0)
    write_window("AAPL", populated, "schwab_api", cache_dir=tmp_path)
    path = tmp_path / "AAPL.schwab_api.parquet"
    pre_mtime = path.stat().st_mtime_ns
    pre_content = pd.read_parquet(path)

    time.sleep(0.01)
    write_window("AAPL", pd.DataFrame(), "schwab_api", cache_dir=tmp_path)

    post_content = pd.read_parquet(path)
    pd.testing.assert_frame_equal(
        pre_content.reset_index(drop=True),
        post_content.reset_index(drop=True),
    )
    assert path.stat().st_mtime_ns == pre_mtime, (
        "empty-write guard fired AFTER merge — should short-circuit BEFORE"
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


def test_backward_compat_rename_old_only_replicates_to_yfinance(tmp_path):
    """**Codex R2 Major #1 — COPY-NOT-MOVE semantics under V1.**

    Old `{TICKER}.parquet` exists; `{TICKER}.yfinance.parquet` absent →
    REPLICATE legacy content to ``{TICKER}.yfinance.parquet`` while
    **LEAVING the legacy file IN PLACE**. ``read_or_fetch_archive`` still
    reads the legacy path under V1; deleting the file would break
    ``swing/prices.py``, ``swing/pipeline/ohlcv.py``, and
    ``swing/trades/daily_management.py``.

    Discriminates against any destructive migration (unlink legacy / orphan-
    rename) and against any plain-copy that doesn't normalize the Shape A
    target.
    """
    from swing.data.ohlcv_archive import _backward_compat_rename

    old_path = tmp_path / "AAPL.parquet"
    _mk_window(["2026-01-02"], close=100.0).to_parquet(old_path)
    pre_old_content = pd.read_parquet(old_path)

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    # KEY Codex R2 Major #1 assertion: legacy file STILL EXISTS UNCHANGED.
    assert old_path.exists(), (
        "Codex R2 Major #1: legacy AAPL.parquet was deleted — V1 readers "
        "(read_or_fetch_archive consumers) would break. Must be copy-not-move."
    )
    post_old_content = pd.read_parquet(old_path)
    pd.testing.assert_frame_equal(
        pre_old_content.reset_index(drop=True),
        post_old_content.reset_index(drop=True),
    )

    new_path = tmp_path / "AAPL.yfinance.parquet"
    assert new_path.exists(), "AAPL.yfinance.parquet not created"
    df = pd.read_parquet(new_path)
    assert float(df.iloc[0]["close"]) == 100.0
    # Shape A: asof_date column normalized.
    assert "asof_date" in df.columns


def test_backward_compat_rename_old_only_legacy_still_readable_by_read_or_fetch(
    tmp_path,
):
    """**Codex R2 Major #1 discriminating test — read-path co-existence.**

    After ``_backward_compat_rename`` runs in old-only mode, the legacy
    ``{TICKER}.parquet`` MUST still be readable via the V1 reader
    (``read_or_fetch_archive`` reads ``{TICKER}.parquet`` directly via
    ``_archive_paths``). This pins the V1 invariant: migration adds the
    Shape A file but does NOT break the legacy reader.

    Pre-fix (destructive migration): legacy unlinked → reader sees no
    archive → refetches from yfinance.
    Post-fix (copy-not-move): legacy in place → reader returns cached data
    without a yfinance call.
    """
    from swing.data.ohlcv_archive import (
        _archive_paths,
        _backward_compat_rename,
        _read_archive,
    )

    # Plant legacy DatetimeIndex file (matches what read_or_fetch_archive
    # actually writes — capitalized OHLCV, DatetimeIndex). The reader does
    # not require asof_date.
    legacy = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.0],
            "Volume": [1000],
        },
        index=pd.to_datetime(["2026-01-02"]),
    )
    parquet_path, _ = _archive_paths(tmp_path, "AAPL")
    legacy.to_parquet(parquet_path)

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    # Read via the V1 reader's primitive: legacy file MUST still be present.
    df = _read_archive(parquet_path)
    assert df is not None, (
        "Codex R2 Major #1: V1 reader sees legacy file as missing after "
        "migration — copy-not-move invariant violated"
    )
    assert "Close" in df.columns
    assert float(df["Close"].iloc[0]) == 100.0


def test_backward_compat_rename_both_exist_merges_preserving_legacy(tmp_path):
    """**Codex R2 Major #1 — MERGE-PRESERVING-BOTH (copy-not-move under V1).**

    Plant:
      - Old `{TICKER}.parquet` with dates [01-02 close=100, 01-03 close=100].
      - New `{TICKER}.yfinance.parquet` with dates [01-03 close=200, 01-04 close=200].

    Expected post-state (Codex R2 Major #1 supersedes R1 Major #6 quarantine):
      - `{TICKER}.yfinance.parquet` contains merged content (3 unique dates;
        01-03 row carries new file's row, i.e. close=200 — `keep='last'`).
      - **Old `{TICKER}.parquet` STILL EXISTS UNCHANGED** (no orphan rename;
        legacy reader keeps consuming the legacy path under V1).
      - NO data loss (every original row, modulo dedup, preserved).
    """
    from swing.data.ohlcv_archive import _backward_compat_rename

    old_path = tmp_path / "AAPL.parquet"
    new_path = tmp_path / "AAPL.yfinance.parquet"
    old_df = _mk_window(["2026-01-02", "2026-01-03"], close=100.0)
    new_df = _mk_window(["2026-01-03", "2026-01-04"], close=200.0)
    old_df.to_parquet(old_path)
    new_df.to_parquet(new_path)
    pre_old_content = pd.read_parquet(old_path)

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    # KEY Codex R2 Major #1 assertion: legacy file STILL EXISTS unchanged.
    assert old_path.exists(), (
        "Codex R2 Major #1: legacy AAPL.parquet was deleted in both-exist "
        "branch — V1 readers would break. Must be merge-preserving-both."
    )
    post_old_content = pd.read_parquet(old_path)
    pd.testing.assert_frame_equal(
        pre_old_content.reset_index(drop=True),
        post_old_content.reset_index(drop=True),
    )

    # No orphan file produced (semantic removed under copy-not-move).
    orphans = sorted(tmp_path.glob("AAPL.parquet.orphan-*.parquet"))
    assert orphans == [], (
        f"Codex R2 Major #1: orphan rename should be GONE under copy-not-move; "
        f"got orphans={[p.name for p in orphans]}"
    )

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

    # Resolver still reads the merged content correctly.
    from swing.data.ohlcv_archive import resolve_ohlcv_window
    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path
    )
    assert len(df) == 3
    # All rows attributed to yfinance (legacy file is NOT read by resolver —
    # only the per-provider Shape A files at .yfinance.parquet / .schwab_api.parquet).
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
    """**Codex R2 Major #1 idempotency under copy-not-move.**

    Invoke twice; the second invocation drives the state to case 2
    (both-exist) because the legacy file is NOT removed. The both-exist
    branch must detect that the merge would produce identical content and
    SKIP the rewrite to preserve mtime + avoid spurious churn.

    Pre-fix (R1 destructive): second call hit case 3 (new-only no-op).
    Post-fix (R2 copy-not-move): second call hits case 2 (both-exist) +
    detects merge-equivalence + skips rewrite.
    """
    from swing.data.ohlcv_archive import _backward_compat_rename

    old_path = tmp_path / "AAPL.parquet"
    _mk_window(["2026-01-02"], close=100.0).to_parquet(old_path)

    _backward_compat_rename("AAPL", cache_dir=tmp_path)
    files_after_first = sorted(p.name for p in tmp_path.iterdir())
    new_path = tmp_path / "AAPL.yfinance.parquet"
    mtime_after_first = new_path.stat().st_mtime_ns

    # Under copy-not-move, both files MUST exist after first call.
    assert old_path.exists()
    assert new_path.exists()
    assert "AAPL.parquet" in files_after_first
    assert "AAPL.yfinance.parquet" in files_after_first

    _backward_compat_rename("AAPL", cache_dir=tmp_path)

    files_after_second = sorted(p.name for p in tmp_path.iterdir())
    assert files_after_second == files_after_first, (
        "second invocation changed the file set — idempotency violated"
    )
    assert new_path.stat().st_mtime_ns == mtime_after_first, (
        "second invocation rewrote the yfinance.parquet — idempotency "
        "violated (merge-equivalence detection in both-exist branch missing)"
    )


def test_backward_compat_rename_uses_same_volume_for_os_replace(tmp_path):
    """CLAUDE.md `os.replace` cross-device gotcha defense-in-depth:
    every `os.replace` call inside `_backward_compat_rename` MUST have
    source and destination inside the SAME `cache_dir` (same volume).

    Under Codex R2 Major #1 copy-not-move, only `_write_archive_atomic` calls
    `os.replace` (temp file in cache_dir → final file in cache_dir). The
    orphan-quarantine rename was removed; we verify all remaining replace
    operations are still same-volume.
    """
    from swing.data.ohlcv_archive import _backward_compat_rename

    old_path = tmp_path / "AAPL.parquet"
    _mk_window(["2026-01-02"]).to_parquet(old_path)

    # Sentinel: record every dir pair hosting a replace operation.
    captured: list[dict] = []
    real_replace = os.replace

    def sentinel_replace(src, dst):
        captured.append(
            {
                "src_parent": Path(src).parent,
                "dst_parent": Path(dst).parent,
            }
        )
        return real_replace(src, dst)

    import swing.data.ohlcv_archive as mod
    orig = mod.os.replace
    mod.os.replace = sentinel_replace
    try:
        _backward_compat_rename("AAPL", cache_dir=tmp_path)
    finally:
        mod.os.replace = orig

    # At least one replace must have fired (the atomic write of the Shape A
    # file). Every replace must be same-volume.
    assert len(captured) >= 1, (
        "expected at least one os.replace call during migration; got 0"
    )
    for op in captured:
        assert op["src_parent"] == tmp_path
        assert op["dst_parent"] == tmp_path, (
            "os.replace destination dir != cache_dir — cross-device link "
            "risk per CLAUDE.md gotcha"
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
    # Codex R2 Major #1 copy-not-move: legacy file STILL EXISTS unchanged.
    assert old_path.exists(), (
        "Codex R2 Major #1: legacy parquet was unlinked — copy-not-move "
        "invariant violated"
    )

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


def test_resolve_ohlcv_window_auto_migrates_legacy_archive_on_first_read(
    tmp_path,
):
    """**Codex R1 Major #1 discriminating test:** plant a legacy
    DatetimeIndex ``{TICKER}.parquet`` (no Shape A files present); invoke
    ``resolve_ohlcv_window`` cold (no manual ``_backward_compat_rename``
    call); assert (a) the rename fired automatically, (b) the result reads
    the new ``.yfinance.parquet`` file with rows present.

    Pre-fix behavior: ``_backward_compat_rename`` was dead code in
    production (only callable from tests); cold read returns empty.
    Post-fix behavior: read-path invokes the migration helper so first read
    triggers normalization + Shape A write, and rows surface.

    Second invocation MUST be a no-op (idempotent migration helper).
    """
    from swing.data.ohlcv_archive import resolve_ohlcv_window

    legacy = _mk_legacy_datetimeindex_window(
        ["2026-01-02", "2026-01-03"], close=100.0,
    )
    old_path = tmp_path / "AAPL.parquet"
    legacy.to_parquet(old_path)
    new_path = tmp_path / "AAPL.yfinance.parquet"
    # Pre-state: only legacy file present.
    assert old_path.exists()
    assert not new_path.exists()

    # Cold read — no explicit migration call. The read path MUST migrate.
    df, provenance = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path,
    )

    # KEY assertion: read returned rows (would be 0 if migration not wired in).
    assert len(df) == 2, (
        "resolve_ohlcv_window did NOT auto-migrate legacy archive on first "
        f"read — got {len(df)} rows (expected 2). Codex R1 Major #1: "
        "_backward_compat_rename must be wired into the read path."
    )
    assert sorted(df["asof_date"].tolist()) == ["2026-01-02", "2026-01-03"]
    assert set(provenance.values()) == {"yfinance"}

    # Post-state: migration completed — new file present, legacy file
    # STILL PRESENT under Codex R2 Major #1 copy-not-move.
    assert new_path.exists()
    assert old_path.exists(), (
        "Codex R2 Major #1: legacy parquet was unlinked by auto-migration — "
        "copy-not-move invariant violated"
    )

    # Second invocation is a no-op (mtime of new file unchanged) — both-exist
    # branch detects merge-equivalence + skips rewrite.
    mtime_after_first = new_path.stat().st_mtime_ns
    df2, _ = resolve_ohlcv_window(
        "AAPL", start="2026-01-01", end="2026-01-10", cache_dir=tmp_path,
    )
    assert new_path.stat().st_mtime_ns == mtime_after_first, (
        "second cold read mutated the yfinance.parquet — idempotency violated"
    )
    assert len(df2) == 2


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
