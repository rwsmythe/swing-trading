"""Task 4.4 — `WatchlistRowVM` gains `pattern_tag`; `build_watchlist_row`
populates it from the same pipeline_run_id anchor as build_watchlist.

Spec §3.5 for the compact-row collapse path (`/watchlist/<ticker>/row`).
The compact row uses the same `partials/watchlist_row.html.j2` template
as the full /watchlist page, so for the template's flag-tag fragment to
render correctly when the row is swapped back from /expand, the row
context must carry the resolved pattern_tag.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from ._pattern_classification_seed import (
    delete_all_classifications,
    seed_pipeline_with_classification,
)


def test_watchlist_row_vm_has_pattern_tag_field():
    """Discriminating: pre-fix, WatchlistRowVM.pattern_tag does not
    exist; post-fix it is a `str | None` field with default None."""
    import dataclasses
    from swing.web.view_models.watchlist import WatchlistRowVM
    fields = {f.name for f in dataclasses.fields(WatchlistRowVM)}
    assert "pattern_tag" in fields


def test_watchlist_row_vm_pattern_tag_default_is_None():
    """Safe default: callers that don't pass pattern_tag get None
    (matches the template's `{% if pattern_tag %}` guard contract)."""
    from swing.web.view_models.watchlist import WatchlistRowVM
    from swing.data.models import WatchlistEntry
    w = WatchlistEntry(
        ticker="AAA", added_date="2026-04-01",
        last_qualified_date="2026-04-26", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-25",
        entry_target=110.0, initial_stop_target=None,
        last_close=100.0, last_pivot=None, last_stop=None,
        last_adr_pct=None, missing_criteria=None, notes=None,
    )
    vm = WatchlistRowVM(w=w, price=None, tags=())
    assert vm.pattern_tag is None


def test_build_watchlist_row_returns_pattern_tag_when_classification_exists(
    seeded_db,
):
    """Compact-row collapse path surfaces pattern_tag from the same
    pipeline_run_id anchor as build_watchlist."""
    from swing.web.view_models.watchlist import build_watchlist_row
    cfg, _ = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    cache = MagicMock()
    cache.get_many.return_value = {}
    row_vm = build_watchlist_row(
        cfg=cfg, cache=cache, ticker="AAPL", executor=MagicMock(),
    )
    assert row_vm is not None
    assert row_vm.pattern_tag == "flag (0.78)"


def test_build_watchlist_row_pattern_tag_is_None_when_no_classification(
    seeded_db,
):
    """With the classification deleted, pattern_tag is None — same anchor
    discipline (no MAX(run_ts) fallback). Discriminating: pre-fix the
    field doesn't exist (raises); post-fix without a classification it's
    None."""
    from swing.web.view_models.watchlist import build_watchlist_row
    cfg, _ = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    delete_all_classifications(cfg.paths.db_path)
    cache = MagicMock()
    cache.get_many.return_value = {}
    row_vm = build_watchlist_row(
        cfg=cfg, cache=cache, ticker="AAPL", executor=MagicMock(),
    )
    assert row_vm is not None
    assert row_vm.pattern_tag is None


def test_build_watchlist_row_pattern_tag_filters_below_threshold(seeded_db):
    """Threshold gate fires through build_watchlist_row, mirroring
    build_watchlist."""
    import dataclasses
    from swing.web.view_models.watchlist import build_watchlist_row
    cfg, _ = seeded_db
    bumped_web = dataclasses.replace(
        cfg.web, flag_pattern_display_threshold=0.50,
    )
    cfg = dataclasses.replace(cfg, web=bumped_web)
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.10,
    )
    cache = MagicMock()
    cache.get_many.return_value = {}
    row_vm = build_watchlist_row(
        cfg=cfg, cache=cache, ticker="AAPL", executor=MagicMock(),
    )
    assert row_vm is not None
    assert row_vm.pattern_tag is None
