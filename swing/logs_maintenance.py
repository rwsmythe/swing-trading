"""One-time, operator-gated, content-preserving log compression.

Pure filesystem logic (no click, no DB) so it is directly unit-testable. The CLI
wiring + the pipeline-running refusal + the confirm prompt live in swing/cli.py.

Never auto-runs; never wired into startup. Compresses LEGACY dated rotation
artifacts ({surface}.log.<DATE>) the old TimedRotatingFileHandler produced and the
new RotatingFileHandler never will. Verify-before-unlink: the .gz is verified
byte-for-byte (streamed SHA-256 of the decompressed bytes vs the original) before
the original is removed. Writes nothing outside ``logs_dir``.
"""
from __future__ import annotations

import contextlib
import gzip
import hashlib
import os
import re
from collections.abc import Iterator
from pathlib import Path

_DATED_SUFFIX = re.compile(r"\.log\.\d{4}-\d{2}-\d{2}$")
_NUMERIC_SUFFIX = re.compile(r"\.log\.\d+$")
# Only swing-managed surfaces are ever selected -- never an unrelated foo.log.<DATE>
# a third-party tool may have dropped in logs_dir (R3-major-1 scope tightening).
_MANAGED_SURFACES = ("web", "pipeline", "cli")
# Defensive self-surface exclusion: cli.log is the cleanup process's own surface
# once Slice 2 lands. In Slice 1 no cli.log handler exists, so this is a no-op,
# but excluding the name keeps --include-current correct under Slice 2.
_SELF_SURFACE_NAMES = ("cli.log",)
_CHUNK = 1024 * 1024
_DEFAULT_OVERSIZE_THRESHOLD = 10 * 1024 * 1024


class LogsCleanupLockHeldError(RuntimeError):
    """Another logs-cleanup instance holds the single-instance lock."""


def _is_managed_surface_file(name: str) -> bool:
    """True iff ``name`` is {surface}.log or {surface}.log.<suffix> for a KNOWN
    swing surface -- so selection never touches a non-swing log file."""
    return any(
        name == f"{s}.log" or name.startswith(f"{s}.log.")
        for s in _MANAGED_SURFACES
    )


def select_legacy_dated_logs(logs_dir: Path) -> list[Path]:
    """Legacy dated artifacts ONLY ({surface}.log.<DATE>) for KNOWN swing surfaces.
    Excludes active managed names ({surface}.log), the numeric rotation set
    ({surface}.log.<int>), non-swing files, and anything already .gz."""
    out: list[Path] = []
    for p in sorted(logs_dir.glob("*.log.*")):
        name = p.name
        if name.endswith(".gz"):
            continue
        if not _is_managed_surface_file(name):   # only swing surfaces
            continue
        if _NUMERIC_SUFFIX.search(name):
            continue
        if _DATED_SUFFIX.search(name):
            out.append(p)
    return out


def select_oversized_current_logs(
    logs_dir: Path,
    *,
    size_threshold: int = _DEFAULT_OVERSIZE_THRESHOLD,
    exclude_names: tuple[str, ...] = _SELF_SURFACE_NAMES,
) -> list[Path]:
    """Oversized CURRENT/rotated managed files ({surface}.log + {surface}.log.<int>)
    above ``size_threshold``, for KNOWN swing surfaces only -- the app-stopped
    reclaim scope. Excludes the invoking process's own surface (cli.log), dated
    files (those belong to the default scope), non-swing files, and any .gz."""
    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in ("*.log", "*.log.[0-9]*"):
        for p in sorted(logs_dir.glob(pattern)):
            if p in seen or p.name.endswith(".gz") or p.name in exclude_names:
                continue
            if not _is_managed_surface_file(p.name):   # only swing surfaces
                continue
            if _DATED_SUFFIX.search(p.name):   # dated files belong to the default scope
                continue
            # Only the CURRENT file ({surface}.log) or the numeric rotation set
            # ({surface}.log.<int>) -- never an arbitrary {surface}.log.<junk>
            # the glob "*.log.[0-9]*" can still match (e.g. web.log.123-not-rotation).
            if not (p.name.endswith(".log") or _NUMERIC_SUFFIX.search(p.name)):
                continue
            seen.add(p)
            if p.stat().st_size > size_threshold:
                out.append(p)
    return out


def _file_chunks(path: Path) -> Iterator[bytes]:
    with open(path, "rb") as f:
        while True:
            b = f.read(_CHUNK)
            if not b:
                break
            yield b


def _gz_decompressed_chunks(path: Path) -> Iterator[bytes]:
    with gzip.open(path, "rb") as f:
        while True:
            b = f.read(_CHUNK)
            if not b:
                break
            yield b


def _sha256_stream(chunks: Iterator[bytes]) -> str:
    h = hashlib.sha256()
    for chunk in chunks:
        h.update(chunk)
    return h.hexdigest()


def reserve_archive_name(logs_dir: Path, base_name: str) -> Path:
    """Atomically reserve the first free {base}.gz / {base}.<N>.gz via O_EXCL
    (R6-major-2 / R7-minor-1: no check-then-replace window)."""
    candidates = [f"{base_name}.gz"] + [f"{base_name}.{i}.gz" for i in range(1, 100000)]
    for cand in candidates:
        target = logs_dir / cand
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        os.close(fd)
        return target
    raise RuntimeError(f"could not reserve an archive name for {base_name!r}")


def compress_log_file(path: Path, logs_dir: Path) -> Path:
    """Content-preserving compress: temp .gz in logs_dir -> fsync -> verify
    byte-for-byte (streamed SHA-256) -> reserve via O_EXCL -> os.replace ->
    unlink original. On any failure the original is left untouched and the temp
    is removed. ``os.replace`` temp lives in logs_dir (same-filesystem Windows
    gotcha)."""
    # Defensive: never read/unlink a file outside logs_dir (the CLI selects from
    # logs_dir, but harden the public helper against misuse).
    if path.resolve().parent != logs_dir.resolve():
        raise ValueError(f"{path} is not directly inside {logs_dir}")
    tmp = logs_dir / (path.name + ".cleanup.tmp.gz")
    if tmp.exists():
        tmp.unlink()
    try:
        with open(path, "rb") as src, gzip.open(tmp, "wb") as dst:
            while True:
                b = src.read(_CHUNK)
                if not b:
                    break
                dst.write(b)
        # fsync requires a WRITABLE descriptor (on Windows fsync on a read-only
        # fd raises EBADF). Re-open the just-closed temp O_RDWR purely to flush
        # the gzip bytes to disk before the verify-before-unlink readback.
        fd = os.open(tmp, os.O_RDWR)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        orig_hash = _sha256_stream(_file_chunks(path))
        gz_hash = _sha256_stream(_gz_decompressed_chunks(tmp))
        if orig_hash != gz_hash:
            raise RuntimeError(f"verification failed for {path.name}; original kept")
        target = reserve_archive_name(logs_dir, path.name)
        try:
            os.replace(tmp, target)   # overwrites the reserved empty slot atomically
        except OSError:
            # Replace failed after reservation -> remove the zero-byte reserved slot
            # so a stale empty .gz never lingers/confuses a later run. The original
            # is still intact (not yet unlinked).
            if target.exists() and target.stat().st_size == 0:
                target.unlink()
            raise
        path.unlink()
        return target
    finally:
        if tmp.exists():
            tmp.unlink()


class _SingleInstanceLock:
    def __init__(self, path: Path, fd: int) -> None:
        self._path = path
        self._fd = fd

    def release(self) -> None:
        try:
            os.close(self._fd)
        finally:
            with contextlib.suppress(OSError):
                self._path.unlink()


def acquire_single_instance_lock(logs_dir: Path) -> _SingleInstanceLock:
    """Single-instance lock file in logs_dir (defense-in-depth so two cleanups
    never run concurrently). Raises LogsCleanupLockHeld if held."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    lock_path = logs_dir / ".logs-cleanup.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise LogsCleanupLockHeldError(
            "another logs cleanup is in progress (lock held)"
        ) from exc
    return _SingleInstanceLock(lock_path, fd)
