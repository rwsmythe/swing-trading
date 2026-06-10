from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from swing.logs_maintenance import (
    LogsCleanupLockHeldError,
    acquire_single_instance_lock,
    compress_log_file,
    reserve_archive_name,
    select_legacy_dated_logs,
    select_oversized_current_logs,
)


def _touch(p: Path, data: bytes = b"x"):
    p.write_bytes(data)


def test_select_legacy_dated_logs_only_dated(tmp_path):
    _touch(tmp_path / "web.log")                  # active managed -> excluded
    _touch(tmp_path / "web.log.1")                # numeric rotation set -> excluded
    _touch(tmp_path / "web.log.2026-05-06")       # legacy dated -> SELECTED
    _touch(tmp_path / "web.log.2026-05-23")       # legacy dated -> SELECTED
    _touch(tmp_path / "web.log.2026-05-06.gz")    # already gz -> excluded
    _touch(tmp_path / "pipeline.log")             # active managed -> excluded
    _touch(tmp_path / "uvicorn.log.2026-05-06")   # NON-swing surface -> excluded
    _touch(tmp_path / "pipeline.log.2026-04-01")  # legacy dated (pipeline) -> SELECTED
    selected = {p.name for p in select_legacy_dated_logs(tmp_path)}
    assert selected == {
        "web.log.2026-05-06", "web.log.2026-05-23", "pipeline.log.2026-04-01",
    }


def test_compress_log_file_content_preserving(tmp_path):
    src = tmp_path / "web.log.2026-05-06"
    payload = ("line with token deadbeef\n" * 5000).encode("utf-8")
    _touch(src, payload)
    archive = compress_log_file(src, tmp_path)
    assert archive.name == "web.log.2026-05-06.gz"
    assert not src.exists()                                   # original removed AFTER verify
    assert gzip.decompress(archive.read_bytes()) == payload   # byte-for-byte preserved


def test_compress_verify_failure_keeps_original(tmp_path, monkeypatch):
    src = tmp_path / "web.log.2026-05-06"
    _touch(src, b"important content")
    # Make the decompressed-gz hash DIFFER from the original hash. NOTE: monkeypatching
    # the shared `_sha256_stream` would make BOTH sides equal (both "MISMATCH") and
    # verification would falsely PASS -- so corrupt the gz-read side only.
    import swing.logs_maintenance as lm
    monkeypatch.setattr(
        lm, "_gz_decompressed_chunks", lambda path: iter([b"CORRUPTED-DIFFERENT-BYTES"])
    )
    with pytest.raises(RuntimeError):
        compress_log_file(src, tmp_path)
    assert src.exists()                                   # original untouched
    assert src.read_bytes() == b"important content"
    assert not list(tmp_path.glob("*.gz"))                # no archive, no temp left


def test_reserve_archive_name_collision_free(tmp_path):
    _touch(tmp_path / "web.log.2026-05-06.gz")
    reserved = reserve_archive_name(tmp_path, "web.log.2026-05-06")
    assert reserved.name == "web.log.2026-05-06.1.gz"


def test_select_oversized_current_logs(tmp_path):
    _touch(tmp_path / "web.log", b"y" * 2048)              # current -> SELECTED (oversized)
    _touch(tmp_path / "web.log.1", b"y" * 2048)            # numeric rotation -> SELECTED
    _touch(tmp_path / "pipeline.log", b"y" * 10)           # under threshold -> excluded
    _touch(tmp_path / "web.log.123-not-rotation", b"y" * 2048)  # junk suffix -> EXCLUDED
    _touch(tmp_path / "uvicorn.log", b"y" * 2048)          # non-swing -> EXCLUDED
    big = {p.name for p in select_oversized_current_logs(tmp_path, size_threshold=1024)}
    assert big == {"web.log", "web.log.1"}


def test_single_instance_lock(tmp_path):
    lock = acquire_single_instance_lock(tmp_path)
    with pytest.raises(LogsCleanupLockHeldError):
        acquire_single_instance_lock(tmp_path)
    lock.release()
    acquire_single_instance_lock(tmp_path).release()   # released -> reacquirable
