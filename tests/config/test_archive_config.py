"""ArchiveConfig.stagger_full_refresh round-trips from TOML (Arc 6 §5 kill-switch)."""
from __future__ import annotations

from swing.config import ArchiveConfig


def test_stagger_full_refresh_defaults_true():
    """Absent from TOML -> dataclass default True (legacy stagger ON)."""
    cfg = ArchiveConfig()
    assert cfg.stagger_full_refresh is True


def test_stagger_full_refresh_round_trips_from_raw_archive_section():
    """The loader builds ArchiveConfig(**raw['archive']); a false override sticks."""
    cfg = ArchiveConfig(**{"archive_history_days": 1260, "stagger_full_refresh": False})
    assert cfg.stagger_full_refresh is False
    assert cfg.archive_history_days == 1260
