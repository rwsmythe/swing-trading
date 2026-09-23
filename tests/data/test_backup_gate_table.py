"""D50 -- the pre-migration backup gates as ONE table + ONE parameterised body.

The roster below is NOT read from the table under test. It was enumerated from
the pre-refactor source, ``git show eface268:swing/data/db.py`` (the arc's base,
the last commit carrying the 23 hand-copied gate functions), by parsing each
``def _*_backup_gate`` body for its pre-version predicate, the creator it called,
the expected-tables constant it verified against and its error-message label,
then reading the creator's filename f-string for the stem. The call order in
that file's ``run_migrations`` equals this order. Ungated pre-versions: 14, 17.

    pre  stem                    wrapper                             constant                                          label
    13   phase7                  _phase7_backup_gate                 PHASE7_EXPECTED_TABLES                            pre-Phase-7
    15   phase8                  _phase8_backup_gate                 PHASE8_PRE_MIGRATION_EXPECTED_TABLES              pre-Phase-8
    16   phase9                  _phase9_backup_gate                 PHASE9_PRE_MIGRATION_EXPECTED_TABLES              pre-Phase-9
    18   phase12-bundle-c        _phase12_bundle_c_backup_gate       PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES    pre-Phase-12-Sub-bundle-C
    19   phase13                 _phase13_backup_gate                PHASE13_PRE_MIGRATION_EXPECTED_TABLES             pre-Phase-13
    20   phase13-sb6c            _phase13_sb6c_backup_gate           PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES        pre-Phase-13-SB6c
    21   phase14                 _phase14_backup_gate                PHASE14_PRE_MIGRATION_EXPECTED_TABLES             pre-Phase-14
    22   phase14-sb3             _phase14_sb3_backup_gate            PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES         pre-Phase-14-SB3
    23   b7                      _b7_backup_gate                     B7_PRE_MIGRATION_EXPECTED_TABLES                  pre-B7
    24   phase16                 _phase16_backup_gate                PHASE16_PRE_MIGRATION_EXPECTED_TABLES             pre-phase16
    25   broad-watch-baseline    _broad_watch_baseline_backup_gate   BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES         pre-broad-watch
    26   entry-intent            _entry_intent_backup_gate           ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES        pre-entry-intent
    27   watchlist-pin           _watchlist_pin_backup_gate          WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES       pre-watchlist-pin
    28   cash-recon              _cash_recon_backup_gate             CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES          pre-cash-recon
    29   phase18-arc-c           _phase18_arc_c_backup_gate          PHASE18_ARC_C_PRE_MIGRATION_EXPECTED_TABLES       pre-phase18-arc-c
    30   phase18-arc-h6          _phase18_arc_h6_backup_gate         PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES      pre-phase18-arc-h6
    31   phase21-arc-a           _phase21_arc_a_backup_gate          PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES       pre-phase21-arc-a
    32   phase21-arc-b           _phase21_arc_b_backup_gate          PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES       pre-phase21-arc-b
    33   h1-amendment            _h1_amendment_backup_gate           H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES        pre-h1-amendment
    34   a4-taxonomy             _a4_taxonomy_backup_gate            A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES         pre-a4-taxonomy
    35   demand-c                _demand_c_backup_gate               DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES            pre-demand-c
    36   22a                     _phase22_arc_a_backup_gate          PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES       pre-22-A
    37   22a4                    _phase22_arc_a4_backup_gate         PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES      pre-22-A4

Every stem is preserved BYTE-FOR-BYTE: the D32 move-then-retain sweep and the
0038 witness record name the files by them.
"""
from __future__ import annotations

import re
import sqlite3
import subprocess
import types
from pathlib import Path

import pytest

from swing.data import db as db_mod
from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _current_version,
    _verify_backup_integrity,
    open_connection,
    run_migrations,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "eface268"

# (pre_version, filename_stem, wrapper name, expected-tables constant, label)
ROSTER: tuple[tuple[int, str, str, str, str], ...] = (
    (13, "phase7", "_phase7_backup_gate", "PHASE7_EXPECTED_TABLES", "pre-Phase-7"),
    (15, "phase8", "_phase8_backup_gate",
     "PHASE8_PRE_MIGRATION_EXPECTED_TABLES", "pre-Phase-8"),
    (16, "phase9", "_phase9_backup_gate",
     "PHASE9_PRE_MIGRATION_EXPECTED_TABLES", "pre-Phase-9"),
    (18, "phase12-bundle-c", "_phase12_bundle_c_backup_gate",
     "PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES", "pre-Phase-12-Sub-bundle-C"),
    (19, "phase13", "_phase13_backup_gate",
     "PHASE13_PRE_MIGRATION_EXPECTED_TABLES", "pre-Phase-13"),
    (20, "phase13-sb6c", "_phase13_sb6c_backup_gate",
     "PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES", "pre-Phase-13-SB6c"),
    (21, "phase14", "_phase14_backup_gate",
     "PHASE14_PRE_MIGRATION_EXPECTED_TABLES", "pre-Phase-14"),
    (22, "phase14-sb3", "_phase14_sb3_backup_gate",
     "PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES", "pre-Phase-14-SB3"),
    (23, "b7", "_b7_backup_gate", "B7_PRE_MIGRATION_EXPECTED_TABLES", "pre-B7"),
    (24, "phase16", "_phase16_backup_gate",
     "PHASE16_PRE_MIGRATION_EXPECTED_TABLES", "pre-phase16"),
    (25, "broad-watch-baseline", "_broad_watch_baseline_backup_gate",
     "BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES", "pre-broad-watch"),
    (26, "entry-intent", "_entry_intent_backup_gate",
     "ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES", "pre-entry-intent"),
    (27, "watchlist-pin", "_watchlist_pin_backup_gate",
     "WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES", "pre-watchlist-pin"),
    (28, "cash-recon", "_cash_recon_backup_gate",
     "CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES", "pre-cash-recon"),
    (29, "phase18-arc-c", "_phase18_arc_c_backup_gate",
     "PHASE18_ARC_C_PRE_MIGRATION_EXPECTED_TABLES", "pre-phase18-arc-c"),
    (30, "phase18-arc-h6", "_phase18_arc_h6_backup_gate",
     "PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES", "pre-phase18-arc-h6"),
    (31, "phase21-arc-a", "_phase21_arc_a_backup_gate",
     "PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES", "pre-phase21-arc-a"),
    (32, "phase21-arc-b", "_phase21_arc_b_backup_gate",
     "PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES", "pre-phase21-arc-b"),
    (33, "h1-amendment", "_h1_amendment_backup_gate",
     "H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES", "pre-h1-amendment"),
    (34, "a4-taxonomy", "_a4_taxonomy_backup_gate",
     "A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES", "pre-a4-taxonomy"),
    (35, "demand-c", "_demand_c_backup_gate",
     "DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES", "pre-demand-c"),
    (36, "22a", "_phase22_arc_a_backup_gate",
     "PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES", "pre-22-A"),
    (37, "22a4", "_phase22_arc_a4_backup_gate",
     "PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES", "pre-22-A4"),
)

# POST-BASE rows (P33, 22-A2): gates added AFTER the D50 base. A row here
# cannot be cross-checked against ``eface268``'s source -- it did not exist
# there -- so it is asserted against the LIVE table only, and the table must
# equal ``ROSTER + POST_BASE_ROSTER`` in order. The base roster stays exactly
# the 23 rows the base re-derives.
POST_BASE_ROSTER: tuple[tuple[int, str, str, str, str], ...] = (
    (38, "22a2", "_phase22_arc_a2_backup_gate",
     "PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES", "pre-22-A2"),
)
ALL_ROSTER = ROSTER + POST_BASE_ROSTER
UNGATED_PRE_VERSIONS = (14, 17)

# The four legacy creator names tests monkeypatch or call; each stays as an
# alias of the one parameterised creator, bound to its row's stem.
CREATOR_ALIASES = {
    13: "_create_pre_migration_backup",
    31: "_create_pre_phase21_arc_a_migration_backup",
    32: "_create_pre_phase21_arc_b_migration_backup",
    33: "_create_pre_h1_amendment_migration_backup",
}

_GATE_NAME_RE = re.compile(r"^_\w+_backup_gate$")


def _gate_images(d: Path) -> list[Path]:
    return sorted(d.glob("swing-pre-*.db")) if d.exists() else []


# ---------------------------------------------------------------------------
# (i) the table covers exactly the 23 gated pre-versions, row for row
# ---------------------------------------------------------------------------
def test_i_the_table_is_exactly_the_roster_enumerated_from_the_base() -> None:
    table = db_mod._PRE_MIGRATION_BACKUP_GATES
    assert len(ROSTER) == 23
    assert len(table) == len(ALL_ROSTER)
    for spec, (pre, stem, gate_name, const, label) in zip(
            table, ALL_ROSTER, strict=True):
        assert spec.pre_version == pre
        assert spec.filename_stem == stem
        assert spec.gate_name == gate_name
        assert spec.label == label
        # the table CITES the constant -- the same object, not a copy
        assert spec.expected_tables is getattr(db_mod, const), (pre, const)
        assert spec.filename_glob == f"swing-pre-{stem}-migration-*.db"
    assert [s.pre_version for s in table] == sorted({s.pre_version for s in table})


def test_i_the_ungated_pre_versions_have_no_row_and_the_lookup_says_so() -> None:
    gated = {r[0] for r in ALL_ROSTER}
    for v in range(0, EXPECTED_SCHEMA_VERSION + 2):
        spec = db_mod.backup_gate_for_pre_version(v)
        if v in gated:
            assert spec is not None and spec.pre_version == v
        else:
            assert spec is None, v
    for v in UNGATED_PRE_VERSIONS:
        assert db_mod.backup_gate_for_pre_version(v) is None


def _load_base_module() -> types.ModuleType:
    proc = subprocess.run(
        ["git", "show", f"{BASE_SHA}:swing/data/db.py"],
        cwd=REPO_ROOT, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        # FAIL, never skip: a skipped equivalence proof reads green while proving
        # nothing. The base is an ancestor of every tree this arc merges into.
        pytest.fail(f"git object {BASE_SHA} not resolvable here: {proc.stderr!r}")
    # BYTES decoded as UTF-8 explicitly: the file carries non-ASCII prose and
    # this box's default text decoding is cp1252.
    src = proc.stdout.decode("utf-8")
    mod = types.ModuleType("_d50_base_db")
    mod.__file__ = str(REPO_ROOT / "swing" / "data" / "db.py")
    exec(compile(src, "_d50_base_db", "exec"), mod.__dict__)  # noqa: S102
    mod.__dict__["__source__"] = src
    return mod


def test_i_the_roster_re_derives_from_the_base_source_and_behaves_identically() -> None:
    """Cross-check the literal roster against ``git show eface268`` (never the
    table), then run OLD vs NEW wrappers on an in-memory connection over every
    (current, target) in a window: a firing gate raises its file-backed-source
    refusal before touching the filesystem, so identical raise/no-raise and
    identical message text is identical predicate + label."""
    base = _load_base_module()
    src = base.__source__
    names = re.findall(r"^def (_\w+_backup_gate)\(", src, re.M)
    assert names == [r[2] for r in ROSTER]
    assert re.findall(r"^    (_\w+_backup_gate)\(", src, re.M) == names  # call order
    for pre, stem, gate_name, const, _label in ROSTER:
        body = src[src.index(f"def {gate_name}("):]
        body = body[: body.index("\ndef ", 1)]
        creator = re.search(r"backup_path = (_create_pre_\w+)\(", body).group(1)
        cbody = src[src.index(f"def {creator}("):]
        cbody = cbody[: cbody.index("\ndef ", 1)]
        assert f'f"swing-pre-{stem}-migration-{{timestamp}}.db"' in cbody, gate_name
        assert re.search(rf"expected_tables\s*=\s*{const}\b", body), gate_name
    for _pre, _stem, gate_name, _const, _label in ROSTER:
        old = getattr(base, gate_name)
        new = getattr(db_mod, gate_name)
        for current in range(0, EXPECTED_SCHEMA_VERSION + 2):
            for target in (current, current + 1, current + 2, EXPECTED_SCHEMA_VERSION):
                outcomes = []
                for fn in (old, new):
                    try:
                        fn(sqlite3.connect(":memory:"), current_version=current,
                           target_version=target, backup_dir=None)
                        outcomes.append(None)
                    except Exception as exc:  # noqa: BLE001
                        outcomes.append((type(exc).__name__, str(exc)))
                assert outcomes[0] == outcomes[1], (gate_name, current, target, outcomes)


# ---------------------------------------------------------------------------
# closure, both directions (the object set, not the value set)
# ---------------------------------------------------------------------------
def test_closure_every_gate_name_has_one_row_and_every_row_has_its_wrapper() -> None:
    module_gate_names = {
        n for n, obj in vars(db_mod).items()
        if _GATE_NAME_RE.match(n) and callable(obj)
    }
    row_names = [s.gate_name for s in db_mod._PRE_MIGRATION_BACKUP_GATES]
    assert len(row_names) == len(set(row_names)), "a wrapper named by two rows"
    assert module_gate_names == set(row_names), (
        f"wrapper without row: {sorted(module_gate_names - set(row_names))}; "
        f"row without wrapper: {sorted(set(row_names) - module_gate_names)}")
    for spec in db_mod._PRE_MIGRATION_BACKUP_GATES:
        wrapper = getattr(db_mod, spec.gate_name)
        # bound to ITS row, not merely to some row
        assert wrapper.backup_gate_spec is spec, spec.gate_name


def test_closure_every_creator_alias_is_bound_to_its_rows_stem(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    c = sqlite3.connect(src)
    c.execute("CREATE TABLE t (x)")
    c.commit()
    c.close()
    by_pre = {s.pre_version: s for s in db_mod._PRE_MIGRATION_BACKUP_GATES}
    assert {s.pre_version for s in by_pre.values() if s.creator_alias} == set(CREATOR_ALIASES)
    for pre, alias in CREATOR_ALIASES.items():
        spec = by_pre[pre]
        assert spec.creator_alias == alias
        dest = tmp_path / f"d{pre}"
        made = getattr(db_mod, alias)(src, dest_dir=dest)
        assert made.parent == dest
        assert made.match(spec.filename_glob), (alias, made.name)


# ---------------------------------------------------------------------------
# (ii) + (iii-gated): each row, walked from its pre_version to HEAD through the
# REAL runner, writes exactly ONE image -- its own stem, integrity-verified --
# and NOT its successor's.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("row", ALL_ROSTER, ids=[f"v{r[0]}" for r in ALL_ROSTER])
def test_ii_each_gate_fires_exactly_once_walking_its_pre_version_to_head(
        tmp_path: Path, row) -> None:
    pre, stem, _gate_name, const, _label = row
    build_bak = tmp_path / "build_bak"
    c = open_connection(tmp_path / "fixture.db", reaffirm_wal=True)
    try:
        run_migrations(c, target_version=pre, backup_dir=build_bak)
        assert _current_version(c) == pre
        assert _gate_images(build_bak) == []  # a fresh 0 -> pre build fires nothing
        bak = tmp_path / "bak"
        run_migrations(c, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=bak)
        assert _current_version(c) == EXPECTED_SCHEMA_VERSION
    finally:
        c.close()
    images = _gate_images(bak)
    assert len(images) == 1, images
    assert images[0].match(f"swing-pre-{stem}-migration-*.db")
    _verify_backup_integrity(images[0], expected_tables=getattr(db_mod, const))
    successor = db_mod.backup_gate_for_pre_version(pre + 1)
    if successor is not None:
        assert not list(bak.glob(successor.filename_glob))
    assert _gate_images(tmp_path) == []  # nothing fell back to the DB's parent


# ---------------------------------------------------------------------------
# (iii-ungated): the sharper `<=` discriminator. A `current_version <= N` body
# fires every gate at or above the start (from 17: twenty images).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pre", UNGATED_PRE_VERSIONS)
def test_iii_an_ungated_pre_version_walked_to_head_writes_zero_images(
        tmp_path: Path, pre: int) -> None:
    c = open_connection(tmp_path / "fixture.db", reaffirm_wal=True)
    try:
        run_migrations(c, target_version=pre, backup_dir=tmp_path / "build_bak")
        assert _current_version(c) == pre
        bak = tmp_path / "bak"
        run_migrations(c, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=bak)
        assert _current_version(c) == EXPECTED_SCHEMA_VERSION
    finally:
        c.close()
    assert _gate_images(bak) == []
    assert _gate_images(tmp_path) == []


def test_the_runner_resolves_wrappers_at_call_time_not_from_a_bound_list(
        tmp_path: Path, monkeypatch) -> None:
    """Every row's wrapper is looked up by module attribute when the runner
    runs: patching ANY of them intercepts (here the first and a middle row)."""
    for spec in (db_mod._PRE_MIGRATION_BACKUP_GATES[0], db_mod._PRE_MIGRATION_BACKUP_GATES[11]):
        seen = []

        def _spy(conn, *, current_version, target_version, backup_dir, _s=spec, _seen=seen):
            _seen.append((current_version, target_version))

        monkeypatch.setattr(db_mod, spec.gate_name, _spy)
        c = open_connection(tmp_path / f"spy{spec.pre_version}.db")
        try:
            run_migrations(c, target_version=12)
        finally:
            c.close()
        assert seen == [(0, 12)], spec.gate_name
        monkeypatch.undo()


def test_a_failing_creator_is_wrapped_with_the_rows_label(tmp_path: Path, monkeypatch) -> None:
    c = open_connection(tmp_path / "v26.db")
    try:
        run_migrations(c, target_version=26)

        def _boom(*_a, **_k):
            raise OSError("disk says no")

        monkeypatch.setattr(db_mod, "_create_gate_backup", _boom)
        with pytest.raises(MigrationBackupRequiredException,
                           match=r"^pre-entry-intent backup failed: disk says no$"):
            run_migrations(c, target_version=27, backup_dir=tmp_path / "bak")
        assert _current_version(c) == 26
    finally:
        c.close()


# ---------------------------------------------------------------------------
# F1 -- ensure_schema threads backup_dir; the default is preserved
# ---------------------------------------------------------------------------
def _build(path: Path, version: int) -> None:
    c = open_connection(path, reaffirm_wal=True)
    try:
        run_migrations(c, target_version=version, backup_dir=path.parent / "build_bak")
    finally:
        c.close()


def test_ensure_schema_writes_the_gate_image_into_the_given_backup_dir(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    db = home / "swing.db"
    _build(db, 37)
    bak = tmp_path / "configured_backups"
    conn = db_mod.ensure_schema(db, backup_dir=bak)
    conn.close()
    assert len(list(bak.glob("swing-pre-22a4-migration-*.db"))) == 1
    assert _gate_images(home) == []


def test_ensure_schema_without_backup_dir_keeps_the_parent_default(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    db = home / "swing.db"
    _build(db, 37)
    conn = db_mod.ensure_schema(db)
    conn.close()
    assert len(list(home.glob("swing-pre-22a4-migration-*.db"))) == 1


def test_ensure_schema_backup_dir_is_keyword_only() -> None:
    import inspect

    p = inspect.signature(db_mod.ensure_schema).parameters["backup_dir"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is None


# ---------------------------------------------------------------------------
# Codex R1 R-1: the one creator never overwrites an existing image
# ---------------------------------------------------------------------------
def _frozen_db_clock(monkeypatch, fixed) -> None:
    from datetime import datetime as _dt

    class _Frozen(_dt):
        @classmethod
        def now(cls, tz=None):
            return fixed.replace(tzinfo=tz)

    monkeypatch.setattr(db_mod, "datetime", _Frozen)


def test_an_occupied_image_name_refuses_the_migration_and_is_not_touched(
        tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime as _dt

    c = open_connection(tmp_path / "v26.db")
    try:
        run_migrations(c, target_version=26)
        _frozen_db_clock(monkeypatch, _dt(2030, 1, 2, 3, 4, 5))
        bak = tmp_path / "bak"
        bak.mkdir()
        occupied = bak / "swing-pre-entry-intent-migration-20300102T030405Z.db"
        # A REAL database: a garbage-bytes file would make backup() fail on its
        # own and pass this test without any no-clobber protection.
        o = sqlite3.connect(occupied)
        o.execute("CREATE TABLE the_only_v26_pre_image (x)")
        o.commit()
        o.close()
        original = occupied.read_bytes()
        with pytest.raises(MigrationBackupRequiredException,
                           match=r"^pre-entry-intent backup failed: "):
            run_migrations(c, target_version=27, backup_dir=bak)
        assert occupied.read_bytes() == original
        assert sorted(p.name for p in bak.iterdir()) == [occupied.name]
        assert _current_version(c) == 26
    finally:
        c.close()


def test_a_failed_snapshot_removes_only_its_own_reserved_file(
        tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src.db"
    sqlite3.connect(src).close()
    bak = tmp_path / "bak"
    bak.mkdir()
    bystander = bak / "swing-pre-b7-migration-20200101T000000Z.db"
    bystander.write_bytes(b"older image")

    class _SrcThatFailsMidBackup:
        # the failure lands AFTER the destination file exists -- the case that
        # leaves a partial image behind unless the creator cleans up its own
        def backup(self, dest):
            dest.execute("CREATE TABLE partial (x)")
            dest.commit()
            raise sqlite3.OperationalError("source unreadable")

        def close(self):
            pass

    monkeypatch.setattr(db_mod, "open_connection",
                        lambda *_a, **_k: _SrcThatFailsMidBackup())
    with pytest.raises(sqlite3.OperationalError):
        db_mod._create_gate_backup(src, dest_dir=bak, filename_stem="b7")
    assert sorted(p.name for p in bak.iterdir()) == [bystander.name]
    assert bystander.read_bytes() == b"older image"


def test_a2_22_the_post_base_roster_is_one_22a2_row_after_the_base_23(
        tmp_path: Path) -> None:
    """22-A2 P33, re-scoped by Arc 22-B (R0.I): the base-derived roster stays
    23 rows; 0039's OWN gate is the 22a2 row for pre-version 38, and a
    38 -> target 39 run writes EXACTLY ONE gate image, the 22a2 one (never a
    HEAD run, which a later gate row would change)."""
    assert len(ROSTER) == 23
    spec = db_mod.backup_gate_for_pre_version(38)
    assert spec is not None and spec.filename_stem == "22a2"
    assert (spec.pre_version, spec.filename_stem, spec.gate_name, spec.label) == (
        38, "22a2", "_phase22_arc_a2_backup_gate", "pre-22-A2")
    assert spec.expected_tables is db_mod.PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES
    c = open_connection(tmp_path / "fixture.db", reaffirm_wal=True)
    try:
        run_migrations(c, target_version=38, backup_dir=tmp_path / "build_bak")
        bak = tmp_path / "bak"
        run_migrations(c, target_version=39, backup_dir=bak)
        assert _current_version(c) == 39
    finally:
        c.close()
    images = _gate_images(bak)
    assert len(images) == 1, images
    assert images[0].match("swing-pre-22a2-migration-*.db")
