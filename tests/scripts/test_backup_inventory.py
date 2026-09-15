"""scripts/backup_inventory.py -- the read-only D32/F4 inventory, on a SYNTHETIC root.

Every fixture image is built the way production builds them: ``Connection.backup()``
from a WAL-mode source (so it carries the WAL header -- the shape on which a plain
``mode=ro`` open creates sidecars). The read-only property is asserted as a full
before/after snapshot of the tree: names, sizes and mtimes unchanged.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup_inventory.py"


def _load():
    spec = importlib.util.spec_from_file_location("backup_inventory", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["backup_inventory"] = mod
    spec.loader.exec_module(mod)
    return mod


inv = _load()


def _image(path: Path, version: int | None, *, marker: str = "") -> Path:
    """A WAL-header image of a DB at ``version`` (None = no schema_version table)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    src_path = path.parent / f".src-{path.name}"
    src = sqlite3.connect(src_path)
    src.execute("PRAGMA journal_mode=WAL")
    src.execute("PRAGMA user_version=0")
    src.execute("CREATE TABLE payload (m TEXT)")
    src.execute("INSERT INTO payload VALUES (?)", (marker or path.name,))
    if version is not None:
        src.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        src.execute("INSERT INTO schema_version VALUES (?)", (version,))
    src.commit()
    dst = sqlite3.connect(path)
    src.backup(dst)
    dst.close()
    src.close()
    for p in path.parent.glob(f".src-{path.name}*"):
        p.unlink()
    return path


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
    }


def _world(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / "swing data"  # a space: the URI must be encoded
    backups = root / "backups"
    w = {"root": root, "backups": backups}
    w["root_gate"] = _image(root / "swing-pre-22a4-migration-20260908T010203Z.db", 37,
                            marker="A")
    w["root_gate_old"] = _image(root / "swing-pre-phase8-migration-20260101T000000Z.db",
                                None, marker="pre-schema-version")
    # a CLI copy with the SAME bytes as root_gate -> its twin
    backups.mkdir(parents=True)
    w["cli_twin"] = backups / "swing-20260908T150203.db"
    shutil.copyfile(w["root_gate"], w["cli_twin"])
    w["cli_solo"] = _image(backups / "swing-20260801T101010.db", 36, marker="B")
    w["weekly"] = _image(backups / "swing-202636.db", 38, marker="W")
    w["gate_in_backups"] = _image(backups / "swing-pre-22a-migration-20260902T000000Z.db",
                                  36, marker="C")
    w["unclassified_db"] = _image(backups / "swing.db.manual-copy.db", 38, marker="U")
    w["garbage"] = backups / "swing-notadb.db"
    w["garbage"].write_bytes(b"this is not a sqlite file at all" * 10)
    w["moved"] = _image(backups / "pre-images" / "swing-pre-b7-migration-20260601T000000Z.db",
                        23, marker="D")
    # not in scope: root non-gate DB and a nested dir deeper than pre-images
    w["live"] = _image(root / "swing.db", 38, marker="LIVE")
    w["deep"] = _image(backups / "pre-images" / "nested" / "swing-pre-x-migration-1Z.db", 1)
    return w


def _rows(text: str) -> dict[str, list[str]]:
    out = {}
    for line in text.splitlines():
        if line.startswith("#") or line.startswith("location\t"):
            continue
        cols = line.split("\t")
        out[cols[8]] = cols
    return out


def test_every_file_is_listed_classified_versioned_hashed_and_twinned(tmp_path: Path) -> None:
    w = _world(tmp_path)
    text = inv.render(inv.inventory(w["root"], w["backups"]), w["root"], w["backups"])
    rows = _rows(text)
    expect = {
        "root_gate": ("root", "gate-image", "37"),
        "root_gate_old": ("root", "gate-image", "unknown"),
        "cli_twin": ("backups", "cli-copy", "37"),
        "cli_solo": ("backups", "cli-copy", "36"),
        "weekly": ("backups", "weekly-backup", "38"),
        "gate_in_backups": ("backups", "gate-image", "36"),
        "unclassified_db": ("backups", "unclassified", "38"),
        "moved": ("pre-images", "gate-image", "23"),
    }
    for key, (loc, cls, ver) in expect.items():
        cols = rows[str(w[key])]
        assert cols[0] == loc and cols[1] == cls and cols[4] == ver, (key, cols)
        assert cols[2] == str(w[key].stat().st_size)
        assert len(cols[5]) == 64
    g = rows[str(w["garbage"])]
    assert g[1] == "unclassified" and g[4].startswith("error:"), g
    # scope: the live DB and anything deeper than backups/pre-images/ are NOT listed
    assert str(w["live"]) not in rows and str(w["deep"]) not in rows
    assert len(rows) == 9
    # twins: by sha256, only for cli copies
    assert rows[str(w["cli_twin"])][7] == str(w["root_gate"])
    assert rows[str(w["cli_solo"])][7] == "none"
    assert rows[str(w["root_gate"])][7] == "-"
    assert rows[str(w["cli_twin"])][5] == rows[str(w["root_gate"])][5]
    assert "# cli-copy with a byte-identical gate twin: 1 of 2" in text
    assert "# unclassified: 2" in text


def test_the_version_is_the_schema_version_table_not_user_version(tmp_path: Path) -> None:
    p = _image(tmp_path / "swing-pre-demand-c-migration-1Z.db", 35)
    c = sqlite3.connect(p)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 0
    c.close()
    assert inv.read_schema_version(p) == "35"


def test_the_inventory_writes_nothing_on_wal_header_images(tmp_path: Path) -> None:
    w = _world(tmp_path)
    assert w["root_gate"].read_bytes()[18:20] == b"\x02\x02"  # the WAL header shape
    before = _snapshot(w["root"])
    inv.render(inv.inventory(w["root"], w["backups"]), w["root"], w["backups"])
    assert _snapshot(w["root"]) == before
    assert not list(w["root"].rglob("*-shm")) and not list(w["root"].rglob("*-wal"))


def test_a_present_wal_sidecar_is_reported(tmp_path: Path) -> None:
    root = tmp_path / "r"
    p = _image(root / "swing-pre-b7-migration-1Z.db", 23)
    Path(str(p) + "-wal").write_bytes(b"")
    text = inv.render(inv.inventory(root, root / "backups"), root, root / "backups")
    assert _rows(text)[str(p)][6] == "present"


def test_the_script_runs_as_a_program_ascii_only_and_refuses_a_missing_root(
        tmp_path: Path) -> None:
    w = _world(tmp_path)
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(w["root"])],
        capture_output=True, env=env, check=False,
    )
    assert r.returncode == 0, r.stderr
    r.stdout.decode("ascii")  # raises on any non-ASCII byte
    assert b"cli-copy" in r.stdout and b"weekly-backup" in r.stdout
    missing = subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(tmp_path / "nope")],
        capture_output=True, check=False,
    )
    assert missing.returncode == 2


def test_no_twin_is_claimed_across_a_wal_sidecar(tmp_path: Path) -> None:
    """Codex R1 R-2: equal main files are not equal databases when either side
    carries a -wal the immutable read and the main-file hash cannot see.
    Closing pass (CHARC stop rule): the twin column now routes through
    ``eligibility()`` exclusively. A wal sidecar on the CLI COPY's own side
    fails ITS clause directly (a named ``indeterminate-<clause>`` value); a
    wal sidecar on the GATE side makes the gate INELIGIBLE to be a match
    target, so the join simply finds nothing (the CLI copy itself is still
    eligible) -- rendered ``"none"``, the same as no byte match existing at
    all (a deliberate simplification: the gate's own row, with its own
    wal_sidecar=present column, remains fully visible in the inventory)."""
    root = tmp_path / "r"
    backups = root / "backups"
    gate = _image(root / "swing-pre-22a4-migration-20260908T010203Z.db", 37, marker="A")
    backups.mkdir(parents=True)
    cli_wal = backups / "swing-20260908T150203.db"
    shutil.copyfile(gate, cli_wal)
    Path(str(cli_wal) + "-wal").write_bytes(b"committed pages the gate lacks")
    text = inv.render(inv.inventory(root, backups), root, backups)
    assert _rows(text)[str(cli_wal)][7] == "indeterminate-wal-sidecar-not-definitively-absent"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text
    # Reviewer B (B2): a sidecar on the GATE side withholds the twin too --
    # the candidate pair has a hole on EITHER member, never just the CLI side.
    Path(str(cli_wal) + "-wal").unlink()
    Path(str(gate) + "-wal").write_bytes(b"x")
    text = inv.render(inv.inventory(root, backups), root, backups)
    assert _rows(text)[str(cli_wal)][7] == "none"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text


def test_no_twin_is_claimed_across_a_journal_sidecar(tmp_path: Path) -> None:
    """Reviewer B, B2 (major, FAIL CLOSED): a hot rollback journal is the same
    class of hole as a -wal sidecar -- an immutable read and a main-file hash
    cannot see its pending pages either, on EITHER member of the candidate
    pair. Discriminating: an otherwise byte-identical pair reads as a twin
    with no sidecar; planting an EMPTY -journal beside either member must
    flip it to indeterminate, never a positive twin. Closing pass: same
    routing/rendering note as the wal-sidecar sibling above -- the CLI
    copy's own journal sidecar renders its own clause name; the gate's
    renders "none" (no eligible match), not a cross-referenced reason."""
    root = tmp_path / "r"
    backups = root / "backups"
    gate = _image(root / "swing-pre-22a4-migration-20260908T010203Z.db", 37, marker="A")
    backups.mkdir(parents=True)
    cli_journal = backups / "swing-20260908T150203.db"
    shutil.copyfile(gate, cli_journal)

    # pre-sidecar: byte-identical pair, no sidecar anywhere -> a real twin
    text = inv.render(inv.inventory(root, backups), root, backups)
    assert _rows(text)[str(cli_journal)][7] == str(gate)

    # an EMPTY -journal beside the CLI copy withholds the twin
    Path(str(cli_journal) + "-journal").write_bytes(b"")
    text = inv.render(inv.inventory(root, backups), root, backups)
    assert (_rows(text)[str(cli_journal)][7]
            == "indeterminate-journal-sidecar-not-definitively-absent")
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text

    # and an EMPTY -journal beside the GATE side withholds it too (the CLI
    # copy is itself eligible, so this is now "none": no eligible match)
    Path(str(cli_journal) + "-journal").unlink()
    Path(str(gate) + "-journal").write_bytes(b"")
    text = inv.render(inv.inventory(root, backups), root, backups)
    assert _rows(text)[str(cli_journal)][7] == "none"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text


def test_a_per_file_stat_or_hash_error_does_not_abort_the_scan(
        tmp_path: Path, monkeypatch) -> None:
    """Reviewer B, B3 (major) + B2R-3 (minor, the bounded re-read's amendment):
    one unreadable/vanishing file must not abort the whole inventory -- it
    becomes its own error row and the scan continues; exit status stays 0;
    the summary line counts the error rows. B2R-3: metadata ALREADY obtained
    before the failing step (size, mtime, sidecar flags, and here the schema
    version, since only the HASH step failed) is preserved, not zeroed --
    only the hash and the derived twin go indeterminate, and the exception
    text lives in its own dedicated column."""
    root = tmp_path / "r"
    backups = root / "backups"
    _image(root / "swing-pre-22a4-migration-1Z.db", 37, marker="A")
    ok = _image(backups / "swing-20260801T101010.db", 36, marker="B")
    bad = _image(backups / "swing-20260802T101010.db", 36, marker="C")

    real_sha256_of = inv.sha256_of

    def _boom(path: Path) -> str:
        if path == bad:
            raise OSError("synthetic hash failure")
        return real_sha256_of(path)

    monkeypatch.setattr(inv, "sha256_of", _boom)
    text = inv.render(inv.inventory(root, backups), root, backups)
    rows = _rows(text)
    assert len(rows) == 3
    bad_row = rows[str(bad)]
    assert bad_row[4] == "36"  # schema_version WAS obtained before the hash step failed
    assert bad_row[2] == str(bad.stat().st_size)  # size preserved (B2R-3)
    assert bad_row[5] == "indeterminate"  # sha256 column: the word sentinel
    # closing pass: the twin column names the failed clause (eligibility())
    assert bad_row[7] == "indeterminate-hash-failed"
    assert bad_row[9] == "error:OSError:synthetic hash failure"  # the exception text
    # B3R-2: both sidecar flags -- already obtained before the hash step
    # failed -- survive onto the error row (neither goes back to "unknown").
    assert bad_row[6] == "absent"
    assert bad_row[10] == "absent"
    ok_row = rows[str(ok)]
    assert ok_row[4] == "36" and len(ok_row[5]) == 64  # the other file unaffected
    assert ok_row[9] == "-"
    assert "# errors: 1" in text


def test_no_twin_is_claimed_when_the_schema_version_read_errors(tmp_path: Path) -> None:
    """Reviewer B, B2R-1 (critical, FAIL CLOSED): a member whose schema-version
    read errored (readable bytes, not a valid database) must never be named a
    positive twin on EITHER side of the pair -- byte identity alone does not
    prove two corrupt files are the same recoverable database. Discriminating:
    a byte-identical CLI-copy/gate-image pair of NON-sqlite bytes reads as a
    positive twin pre-fix (the schema-read failure was not an ``Entry.error``)
    and indeterminate post-fix."""
    root = tmp_path / "r"
    backups = root / "backups"
    backups.mkdir(parents=True)
    payload = b"this is not a sqlite file at all" * 10
    gate = root / "swing-pre-22a4-migration-20260908T010203Z.db"
    gate.write_bytes(payload)
    cli_corrupt = backups / "swing-20260908T150203.db"
    cli_corrupt.write_bytes(payload)
    text = inv.render(inv.inventory(root, backups), root, backups)
    rows = _rows(text)
    assert rows[str(gate)][4].startswith("error:")
    assert rows[str(cli_corrupt)][4].startswith("error:")
    # closing pass: the CLI copy's OWN clause failure is named directly
    assert rows[str(cli_corrupt)][7] == "indeterminate-schema-read-failed"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text


def test_a_stat_failure_on_a_matched_file_yields_an_error_row_not_a_silent_skip(
        tmp_path: Path, monkeypatch) -> None:
    """Reviewer B, B2R-2 (major): a bare ``Path.is_file()`` call BEFORE the
    per-file guard swallows ``OSError`` internally and returns False, so a
    candidate that raises on stat vanishes with NO row at all -- not even an
    error row. The existence/stat check must run INSIDE the guard.

    On this box/Python (3.14), ``Path.is_file()`` (default
    ``follow_symlinks=True``) resolves to ``os.path.isfile(self)`` -- a
    Windows C builtin that calls the OS-level stat syscall directly and
    bypasses the patchable ``Path.stat`` method entirely (measured: patching
    ``Path.stat`` alone leaves ``is_file()`` returning True). A REAL
    permission/vanish error hits that same C path and is caught INSIDE
    ``is_file()``, surfacing only as its documented False return -- which is
    exactly the swallow the ruling names and exactly what this test
    reproduces directly (rather than depending on Windows ACLs, which the
    brief rules out): ``Path.is_file`` is patched to return False for the
    bad path (the observable CONSEQUENCE of the real swallow), and
    ``Path.stat`` is patched to raise for it too (the real failure our own
    ``_scan_one`` hits when it calls ``.stat()`` directly, unguarded by any
    swallowing wrapper)."""
    root = tmp_path / "r"
    backups = root / "backups"
    _image(root / "swing-pre-22a4-migration-1Z.db", 37, marker="A")
    ok = _image(backups / "swing-20260801T101010.db", 36, marker="B")
    bad = _image(backups / "swing-20260802T101010.db", 36, marker="C")

    real_stat = Path.stat
    real_is_file = Path.is_file

    def _boom_stat(self, *a, **kw):
        if self == bad:
            raise OSError("synthetic stat failure")
        return real_stat(self, *a, **kw)

    def _swallowed_is_file(self, *a, **kw):
        if self == bad:
            return False
        return real_is_file(self, *a, **kw)

    monkeypatch.setattr(Path, "stat", _boom_stat)
    monkeypatch.setattr(Path, "is_file", _swallowed_is_file)
    text = inv.render(inv.inventory(root, backups), root, backups)
    rows = _rows(text)
    assert len(rows) == 3  # not 2 -- the bad file is a ROW, not a silent skip
    bad_row = rows[str(bad)]
    assert bad_row[9] == "error:OSError:synthetic stat failure"
    assert bad_row[5] == "indeterminate"  # nothing was obtained before stat failed
    # closing pass: the CLI copy's OWN clause failure is named directly
    assert bad_row[7] == "indeterminate-stat-failed"
    # neither sidecar was ever probed -- both stay the "unknown" default,
    # never the "absent" a probe never actually confirmed (B3R-2).
    assert bad_row[6] == "unknown"
    assert bad_row[10] == "unknown"
    ok_row = rows[str(ok)]
    assert ok_row[4] == "36" and len(ok_row[5]) == 64
    assert "# errors: 1" in text


def test_a_present_journal_sidecar_is_reported(tmp_path: Path) -> None:
    """B3R-2 (major): the journal-sidecar flag was obtained but never
    rendered, so an error row could not report it. Additive column,
    appended AFTER the existing ones so every existing column index --
    including ``path`` at [8] that ``_rows()`` keys off -- stays stable."""
    root = tmp_path / "r"
    p = _image(root / "swing-pre-b7-migration-1Z.db", 23)
    Path(str(p) + "-journal").write_bytes(b"")
    text = inv.render(inv.inventory(root, root / "backups"), root, root / "backups")
    row = _rows(text)[str(p)]
    assert row[10] == "present"
    assert row[6] == "absent"  # the existing wal-sidecar column is untouched


def test_no_twin_is_claimed_when_a_sidecar_probe_is_unknown(
        tmp_path: Path, monkeypatch) -> None:
    """The class fix (SS-3/SS-4): a sidecar probe hitting a REAL OSError
    (permission denied, a flaky mount) must never read the same as a
    genuinely ABSENT sidecar. Pre-fix, ``Path(...).exists()`` (default
    ``follow_symlinks=True``) resolves on this Windows/Python build to the
    NATIVE ``os.path._path_exists`` builtin (measured:
    ``os.path.exists is genericpath.exists`` is False) -- a C-level
    GetFileAttributes-style check that folds every failure, not-found or
    otherwise, into a bare False WITHOUT going through the patchable
    ``os.stat`` at all (the same bypass Reviewer B's B2R-2 measured for
    ``Path.is_file()``). The fix routes the probe through ``os.stat``
    directly instead -- the one primitive ``Path.stat()`` itself already
    calls (proven by B3's per-file guard) -- so this is BOTH the
    production fix and what makes the fault injectable at all: patching
    ``os.stat`` has no effect on the pre-fix code (it never reaches the
    patched primitive) and a full effect on the post-fix code."""
    root = tmp_path / "r"
    backups = root / "backups"
    gate = _image(root / "swing-pre-22a4-migration-20260908T010203Z.db", 37, marker="A")
    backups.mkdir(parents=True)
    cli_copy = backups / "swing-20260908T150203.db"
    shutil.copyfile(gate, cli_copy)
    wal_path = Path(str(cli_copy) + "-wal")

    real_stat = os.stat

    def _boom(path, *a, **kw):
        if Path(path) == wal_path:
            raise PermissionError(13, "synthetic permission failure")
        return real_stat(path, *a, **kw)

    monkeypatch.setattr(os, "stat", _boom)
    text = inv.render(inv.inventory(root, backups), root, backups)
    row = _rows(text)[str(cli_copy)]
    # closing pass: eligibility() clause (e) collapses "present" and
    # "unknown" into ONE requirement (DEFINITIVELY absent or nothing) --
    # same rendered value as a confirmed-present wal sidecar.
    assert row[7] == "indeterminate-wal-sidecar-not-definitively-absent"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text


def test_a_directory_probe_failure_is_a_visible_row_not_a_silent_empty_scan(
        tmp_path: Path, monkeypatch) -> None:
    """SS-1 class fix: ``directory.is_dir()`` resolves to the same NATIVE
    ``os.path._path_isdir`` builtin as the sidecar probes (measured:
    ``os.path.isdir is genericpath.isdir`` is False) -- it folds a
    permission-denied or unreadable-mount failure into a bare False, and a
    backups directory that genuinely EXISTS but cannot be examined then
    reads IDENTICALLY to one that was never created: every file inside it
    silently vanishes from the inventory with no trace at all.
    Discriminating: ``os.stat`` -- the primitive the fix routes the check
    through instead, and the same one ``Path.stat()`` already calls
    directly (B3) -- is patched to raise only for the backups directory
    path; pre-fix the native probe never reaches it (an empty scan of that
    location, indistinguishable from "not created"); post-fix it is one
    visible ``scan-error`` row and the other locations (root) still scan."""
    root = tmp_path / "r"
    backups = root / "backups"
    backups.mkdir(parents=True)
    _image(root / "swing-pre-22a4-migration-1Z.db", 37, marker="A")
    _image(backups / "swing-20260801T101010.db", 36, marker="B")

    real_stat = os.stat

    def _boom(path, *a, **kw):
        if Path(path) == backups:
            raise PermissionError(13, "synthetic permission failure")
        return real_stat(path, *a, **kw)

    monkeypatch.setattr(os, "stat", _boom)
    text = inv.render(inv.inventory(root, backups), root, backups)
    rows = _rows(text)
    assert any(cols[0] == "root" for cols in rows.values())  # root still scanned
    scan_error_rows = [cols for cols in rows.values() if cols[1] == "scan-error"]
    assert len(scan_error_rows) == 1
    assert scan_error_rows[0][8] == str(backups)
    assert scan_error_rows[0][9].startswith("error:")
    assert "# errors: 1" in text


def test_a_directory_listing_failure_is_a_visible_row_not_a_crash(
        tmp_path: Path, monkeypatch) -> None:
    """SS-2/B4-2 class fix (closing pass): the CONTESTED fact about whether
    ``Path.glob()`` swallows or propagates a scandir ``OSError`` on this
    interpreter is why production no longer calls ``Path.glob()`` at all --
    ``_list_directory`` lists with ``os.scandir()`` directly, the raw
    primitive both readings agree is the one that actually raises.
    Discriminating: ``os.scandir`` is patched to raise only for the backups
    directory; pre-fix (still calling ``Path.glob``, unaffected by this
    patch) the directory scans normally with zero trace of the simulated
    failure; post-fix it is one visible ``scan-error`` row and root still
    scans."""
    root = tmp_path / "r"
    backups = root / "backups"
    backups.mkdir(parents=True)
    _image(root / "swing-pre-22a4-migration-1Z.db", 37, marker="A")

    real_scandir = os.scandir

    def _boom(path=None, *a, **kw):
        if path is not None and Path(path) == backups:
            raise PermissionError(13, "synthetic listing failure")
        return real_scandir(path, *a, **kw)

    monkeypatch.setattr(os, "scandir", _boom)
    text = inv.render(inv.inventory(root, backups), root, backups)
    rows = _rows(text)
    assert any(cols[0] == "root" for cols in rows.values())
    scan_error_rows = [cols for cols in rows.values() if cols[1] == "scan-error"]
    assert len(scan_error_rows) == 1
    assert scan_error_rows[0][8] == str(backups)
    assert "# errors: 1" in text


def test_root_probe_unknown_is_reported_distinctly_from_absent(
        tmp_path: Path, monkeypatch, capsys) -> None:
    """SS-5 class fix: ``main()``'s ``root.is_dir()`` check resolves to the
    same native builtin as the other probes, printing "root not found" for
    a root that actually EXISTS but could not be examined (permission
    denied) -- an operator cannot tell "create the directory" from "fix the
    permission" from that message. Does not change the exit code (no scan
    ran either way, since the fixed code also refuses to scan an UNKNOWN
    root); discriminates on the message content. ``os.stat`` -- routed
    through post-fix, never reached pre-fix (the native probe bypasses
    it) -- is patched to raise only for the root path."""
    root = tmp_path / "r"
    root.mkdir()
    real_stat = os.stat

    def _boom(path, *a, **kw):
        if Path(path) == root:
            raise PermissionError(13, "synthetic permission failure")
        return real_stat(path, *a, **kw)

    monkeypatch.setattr(os, "stat", _boom)
    rc = inv.main(["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "not found" not in captured.err


# --- CHARC stop-rule closing pass: the ALLOWLIST eligibility predicate ---
#
# One mutator per clause (a)-(f). Each starts from a REAL eligible
# byte-identical CLI-copy/gate-image pair (the pre-mutation state IS a
# positive twin) and mutates exactly ONE input at the boundary the
# production code actually calls, so only that one clause fails. The
# symlink mutator (a) fakes the lstat result rather than creating a real
# OS symlink -- Windows symlinks need elevated privilege (Reviewer B,
# B4-1), and every other mutator in this file already uses this same
# "patch the boundary the code calls" technique rather than depending on
# real OS/ACL mechanics.

def _mutate_not_a_plain_regular_file(monkeypatch, cli_copy: Path, gate: Path) -> None:
    real_lstat = os.lstat

    def _boom(path, *a, **kw):
        if Path(path) == cli_copy:
            return SimpleNamespace(st_mode=stat.S_IFLNK)
        return real_lstat(path, *a, **kw)

    monkeypatch.setattr(os, "lstat", _boom)


def _mutate_stat_failed(monkeypatch, cli_copy: Path, gate: Path) -> None:
    real_stat = os.stat

    def _boom(path, *a, **kw):
        if Path(path) == cli_copy:
            raise OSError("synthetic stat failure")
        return real_stat(path, *a, **kw)

    monkeypatch.setattr(os, "stat", _boom)


def _mutate_schema_read_failed(monkeypatch, cli_copy: Path, gate: Path) -> None:
    real_read = inv.read_schema_version

    def _boom(path):
        if path == cli_copy:
            return "error:Synthetic:schema read failed"
        return real_read(path)

    monkeypatch.setattr(inv, "read_schema_version", _boom)


def _mutate_hash_failed(monkeypatch, cli_copy: Path, gate: Path) -> None:
    real_hash = inv.sha256_of

    def _boom(path):
        if path == cli_copy:
            raise OSError("synthetic hash failure")
        return real_hash(path)

    monkeypatch.setattr(inv, "sha256_of", _boom)


def _mutate_wal_sidecar(monkeypatch, cli_copy: Path, gate: Path) -> None:
    Path(str(cli_copy) + "-wal").write_bytes(b"")


def _mutate_journal_sidecar(monkeypatch, cli_copy: Path, gate: Path) -> None:
    Path(str(cli_copy) + "-journal").write_bytes(b"")


_ELIGIBILITY_CLAUSE_TABLE = {
    "not-a-plain-regular-file": _mutate_not_a_plain_regular_file,
    "stat-failed": _mutate_stat_failed,
    "schema-read-failed": _mutate_schema_read_failed,
    "hash-failed": _mutate_hash_failed,
    "wal-sidecar-not-definitively-absent": _mutate_wal_sidecar,
    "journal-sidecar-not-definitively-absent": _mutate_journal_sidecar,
}


def _eligible_pair(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """A real, otherwise-fully-eligible byte-identical CLI-copy/gate-image
    pair -- unmutated, this IS a positive twin (the control row)."""
    root = tmp_path / "r"
    backups = root / "backups"
    gate = _image(root / "swing-pre-22a4-migration-20260908T010203Z.db", 37, marker="A")
    backups.mkdir(parents=True)
    cli_copy = backups / "swing-20260908T150203.db"
    shutil.copyfile(gate, cli_copy)
    return root, backups, cli_copy, gate


def test_eligibility_predicate_table_covers_every_declared_clause() -> None:
    """The CLOSURE GUARD (CHARC stop rule, Sharpening A): a clause added to
    ``eligibility()`` without a matching table row goes red HERE, not
    silently uncovered -- the same D51 comparator shape (the object SET,
    not the value set) already used elsewhere in this codebase."""
    assert set(_ELIGIBILITY_CLAUSE_TABLE) == set(inv._ELIGIBILITY_CLAUSES)


@pytest.mark.parametrize("clause_name", sorted(_ELIGIBILITY_CLAUSE_TABLE))
def test_a_single_failed_clause_withholds_the_positive_twin(
        tmp_path: Path, monkeypatch, clause_name: str) -> None:
    """One row per clause (a)-(f): mutate exactly that ONE input on an
    otherwise-eligible byte-identical pair; the twin must NOT be positive.
    Honest red-first note (recorded in the ledger, not re-derived here):
    against the pre-closing-pass head, clauses (b)/(c)/(d)/(e)/(f) ALREADY
    withheld the positive twin via the prior ad hoc error/sidecar checks --
    only clause (a) (the symlink route, B4-1) was a genuinely NEW route
    this table closes. The table stands as the closure instrument
    regardless of which rows were already green: it is what makes a FUTURE
    clause additions provably covered, not what makes this one red."""
    root, backups, cli_copy, gate = _eligible_pair(tmp_path)
    _ELIGIBILITY_CLAUSE_TABLE[clause_name](monkeypatch, cli_copy, gate)
    text = inv.render(inv.inventory(root, backups), root, backups)
    row = _rows(text)[str(cli_copy)]
    assert not inv._is_positive_twin(row[7]), (clause_name, row)


def test_a_fully_eligible_pair_is_the_positive_twin_control(tmp_path: Path) -> None:
    """The positive control: an unmutated, fully-eligible byte-identical
    pair IS a positive twin -- proves the table's mutators are each
    removing something load-bearing, not asserting a permanently-negative
    predicate."""
    root, backups, cli_copy, gate = _eligible_pair(tmp_path)
    text = inv.render(inv.inventory(root, backups), root, backups)
    row = _rows(text)[str(cli_copy)]
    assert row[7] == str(gate)
    assert inv._is_positive_twin(row[7])


def test_a_scandir_listing_failure_yields_a_scan_error_row(
        tmp_path: Path, monkeypatch) -> None:
    """The scandir listing-failure discriminator, restated at the closing
    pass alongside the clause table (the production mechanism it exercises
    -- ``_list_directory`` -- is the same one ``_scan`` calls; see
    ``test_a_directory_listing_failure_is_a_visible_row_not_a_crash`` above
    for the full B4-2 CONTESTED-fact writeup)."""
    root = tmp_path / "r"
    backups = root / "backups"
    backups.mkdir(parents=True)
    _image(root / "swing-pre-22a4-migration-1Z.db", 37, marker="A")

    real_scandir = os.scandir

    def _boom(path=None, *a, **kw):
        if path is not None and Path(path) == backups:
            raise PermissionError(13, "synthetic listing failure")
        return real_scandir(path, *a, **kw)

    monkeypatch.setattr(os, "scandir", _boom)
    text = inv.render(inv.inventory(root, backups), root, backups)
    rows = _rows(text)
    scan_error_rows = [cols for cols in rows.values() if cols[1] == "scan-error"]
    assert len(scan_error_rows) == 1
    assert scan_error_rows[0][8] == str(backups)


def test_summary_twin_count_uses_exact_sentinels_not_a_string_prefix() -> None:
    """Reviewer B, B2R-4 (minor): the summary classifies twin values by EXACT
    sentinel membership, not by the string prefix ``indeterminate-`` -- a
    matched gate path that legitimately starts with that same text (e.g.
    under a directory literally named ``indeterminate-something``, which the
    absolute-path twin value would carry verbatim) is a real positive twin,
    not a sidecar/error-tainted one. A `render()`-level fixture cannot
    reproduce this on Windows (the drive letter always leads an absolute
    path), so this pins the extracted classifier directly. Closing pass:
    ``_TWIN_SENTINELS`` is now GENERATED from ``_ELIGIBILITY_CLAUSES`` (the
    structural close) rather than hand-maintained, so this test also pins
    that generation -- a clause renamed in ``eligibility()`` without a
    matching sentinel is a drift this test would catch."""
    assert inv._is_positive_twin("indeterminate-decoy/swing-pre-x-migration-1Z.db")
    assert inv._is_positive_twin(r"C:\swing-data\indeterminate-branch\swing-pre-a-migration-1Z.db")
    for clause in inv._ELIGIBILITY_CLAUSES:
        assert not inv._is_positive_twin(f"indeterminate-{clause}")
    assert not inv._is_positive_twin("none")


def test_main_exits_0_with_an_error_row_present(
        tmp_path: Path, monkeypatch, capsys) -> None:
    """Reviewer B, B2R-5: the CLI entry point (not just render()) exits 0
    even when a per-file error is present -- an inventory is evidence, not
    a gate -- and the error row and summary reach real stdout."""
    root = tmp_path / "r"
    backups = root / "backups"
    ok = _image(backups / "swing-20260801T101010.db", 36, marker="B")
    bad = _image(backups / "swing-20260802T101010.db", 36, marker="C")

    real_sha256_of = inv.sha256_of

    def _boom(path: Path) -> str:
        if path == bad:
            raise OSError("synthetic hash failure")
        return real_sha256_of(path)

    monkeypatch.setattr(inv, "sha256_of", _boom)
    rc = inv.main(["--root", str(root), "--backups-dir", str(backups)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "# errors: 1" in captured.out
    assert str(ok) in captured.out
    assert str(bad) in captured.out


def test_a_missing_non_ascii_root_exits_2_on_a_cp1252_console(tmp_path: Path) -> None:
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(tmp_path / "café-→-nope")],
        capture_output=True, env=env, check=False,
    )
    assert r.returncode == 2, r.stderr
    r.stderr.decode("ascii")


def test_the_script_imports_nothing_from_swing() -> None:
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "import swing" not in text and "from swing" not in text
