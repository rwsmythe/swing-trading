"""Finviz inbox selector — date-from-filename → mtime fallback → ambiguity detection."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from swing.pipeline.finviz_select import (
    select_csv, NoFilesError, AmbiguousInboxError,
)


def test_no_files_raises(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    with pytest.raises(NoFilesError):
        select_csv(inbox)


def test_single_dated_file(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    f = inbox / "finviz17Apr2026.csv"
    f.write_text("x", encoding="utf-8")
    selected = select_csv(inbox)
    assert selected == f


def test_picks_newest_by_filename_date(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    older = inbox / "finviz14Apr2026.csv"
    newer = inbox / "finviz17Apr2026.csv"
    older.write_text("a", encoding="utf-8")
    newer.write_text("b", encoding="utf-8")
    assert select_csv(inbox) == newer


def test_falls_back_to_mtime_when_no_date(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    a = inbox / "screener.csv"
    b = inbox / "screen2.csv"
    a.write_text("x", encoding="utf-8")
    time.sleep(0.05)
    b.write_text("x", encoding="utf-8")
    assert select_csv(inbox) == b


def test_ambiguous_same_date_raises(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "finviz17Apr2026-a.csv").write_text("a", encoding="utf-8")
    (inbox / "finviz17Apr2026-b.csv").write_text("b", encoding="utf-8")
    with pytest.raises(AmbiguousInboxError, match="2026-04-17"):
        select_csv(inbox)


def test_skips_rejected_subdir(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    rejected = inbox / "rejected"
    rejected.mkdir()
    (rejected / "finviz17Apr2026.csv").write_text("x", encoding="utf-8")
    with pytest.raises(NoFilesError):
        select_csv(inbox)
