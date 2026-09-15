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
import subprocess
import sys
from pathlib import Path

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
    carries a -wal the immutable read and the main-file hash cannot see."""
    root = tmp_path / "r"
    backups = root / "backups"
    gate = _image(root / "swing-pre-22a4-migration-20260908T010203Z.db", 37, marker="A")
    backups.mkdir(parents=True)
    cli_wal = backups / "swing-20260908T150203.db"
    shutil.copyfile(gate, cli_wal)
    Path(str(cli_wal) + "-wal").write_bytes(b"committed pages the gate lacks")
    text = inv.render(inv.inventory(root, backups), root, backups)
    assert _rows(text)[str(cli_wal)][7] == "indeterminate-wal-sidecar"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text
    # Reviewer B (B2): a sidecar on the GATE side withholds the twin too --
    # the candidate pair has a hole on EITHER member, never just the CLI side.
    Path(str(cli_wal) + "-wal").unlink()
    Path(str(gate) + "-wal").write_bytes(b"x")
    text = inv.render(inv.inventory(root, backups), root, backups)
    assert _rows(text)[str(cli_wal)][7] == "indeterminate-wal-sidecar"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text


def test_no_twin_is_claimed_across_a_journal_sidecar(tmp_path: Path) -> None:
    """Reviewer B, B2 (major, FAIL CLOSED): a hot rollback journal is the same
    class of hole as a -wal sidecar -- an immutable read and a main-file hash
    cannot see its pending pages either, on EITHER member of the candidate
    pair. Discriminating: an otherwise byte-identical pair reads as a twin
    with no sidecar; planting an EMPTY -journal beside either member must
    flip it to indeterminate, never a positive twin."""
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
    assert _rows(text)[str(cli_journal)][7] == "indeterminate-journal-sidecar"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text

    # and an EMPTY -journal beside the GATE side withholds it too
    Path(str(cli_journal) + "-journal").unlink()
    Path(str(gate) + "-journal").write_bytes(b"")
    text = inv.render(inv.inventory(root, backups), root, backups)
    assert _rows(text)[str(cli_journal)][7] == "indeterminate-journal-sidecar"
    assert "# cli-copy with a byte-identical gate twin: 0 of 1" in text


def test_a_per_file_stat_or_hash_error_does_not_abort_the_scan(
        tmp_path: Path, monkeypatch) -> None:
    """Reviewer B, B3 (major): one unreadable/vanishing file must not abort
    the whole inventory -- it becomes its own error row (path + exception
    text, hash and twin both indeterminate) and the scan continues; exit
    status stays 0; the summary line counts the error rows."""
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
    assert bad_row[4].startswith("error:OSError:")  # schema_version column
    assert bad_row[5] == "indeterminate"  # sha256 column
    assert bad_row[7] == "indeterminate"  # twin column
    ok_row = rows[str(ok)]
    assert ok_row[4] == "36" and len(ok_row[5]) == 64  # the other file unaffected
    assert "# errors: 1" in text


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
