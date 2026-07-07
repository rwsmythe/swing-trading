"""Tests for the research-output size-ceiling section of scripts/harness_probe.py.

Rider R2 (Phase-19 close housekeeping H2, docs/archive/phase18/
harness-probe-size-check-commissioning-brief.md): reports the total size of
exports/research/ and research/harness/ each run and fires ATTENTION above a
v1 ceiling (500 MB / 200 MB) -- a forward regrowth guard, quiet at the current
~MB-scale baseline. Exercises the pure _research_size_checks() helper over a
tmp_path root (never the real repo tree).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "harness_probe.py"
_spec = importlib.util.spec_from_file_location("harness_probe", _MODULE_PATH)
harness_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness_probe)


def _write_bytes(path: Path, n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\0" * n)


@pytest.fixture
def root(tmp_path):
    return tmp_path


def test_missing_dirs_report_zero_no_raise(root):
    rows = harness_probe._research_size_checks(root)
    assert len(rows) == 2
    assert all(level == "OK" for level, _ in rows)
    joined = " ".join(line for _, line in rows)
    assert "exports/research" in joined
    assert "research/harness" in joined
    assert "0.0 MB" in joined


def test_under_ceiling_is_ok(root):
    _write_bytes(root / "exports" / "research" / "a" / "small.bin", 1_048_576)  # 1 MB
    _write_bytes(root / "research" / "harness" / "b" / "small.bin", 1_048_576)
    rows = harness_probe._research_size_checks(root)
    assert all(level == "OK" for level, _ in rows)


def test_exports_research_over_ceiling_fires_attention(root):
    # 501 MB > the 500 MB v1 ceiling.
    _write_bytes(root / "exports" / "research" / "big.bin", 501 * 1_048_576)
    attention = [line for level, line in harness_probe._research_size_checks(root)
                 if level == "ATTENTION"]
    assert any("exports/research" in line for line in attention)
    assert not any("research/harness" in line for line in attention)


def test_research_harness_over_ceiling_fires_attention(root):
    # 201 MB > the 200 MB v1 ceiling.
    _write_bytes(root / "research" / "harness" / "big.bin", 201 * 1_048_576)
    attention = [line for level, line in harness_probe._research_size_checks(root)
                 if level == "ATTENTION"]
    assert any("research/harness" in line for line in attention)
    assert not any(
        line.startswith("exports/research") for line in attention)


def test_boundary_exactly_at_ceiling_is_not_attention(root):
    # exactly at the ceiling must NOT fire (strictly-over is the rule).
    _write_bytes(root / "exports" / "research" / "exact.bin", 500 * 1_048_576)
    rows = harness_probe._research_size_checks(root)
    assert all(level == "OK" for level, _ in rows)


def test_output_is_ascii(root):
    _write_bytes(root / "exports" / "research" / "big.bin", 501 * 1_048_576)
    for _level, line in harness_probe._research_size_checks(root):
        line.encode("cp1252")  # must not raise


def test_dir_size_bytes_skips_unreadable_entry(root, monkeypatch):
    # A per-entry OSError (e.g. a permission error, a broken symlink) must not
    # raise -- the probe stays defensive.
    target = root / "exports" / "research"
    _write_bytes(target / "ok.bin", 10)

    real_walk = harness_probe.os.walk

    def _boom_walk(path, *a, **k):
        for dirpath, dirnames, filenames in real_walk(path, *a, **k):
            yield dirpath, dirnames, [*filenames, "ghost-does-not-exist.bin"]

    monkeypatch.setattr(harness_probe.os, "walk", _boom_walk)
    # Must not raise even though the ghost file's stat() will fail.
    size = harness_probe._dir_size_bytes(target)
    assert size >= 10


def test_dir_size_bytes_zero_for_missing_dir(root):
    assert harness_probe._dir_size_bytes(root / "nope" / "nope") == 0
