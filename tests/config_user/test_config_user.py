"""User-config file I/O — round-trip + atomic + missing/malformed."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from swing.config_user import (
    delete_user_override,
    get_user_config_path,
    load_user_overrides,
    write_user_overrides,
)


@pytest.fixture
def isolated_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate USERPROFILE so tests don't touch the operator's real file."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_dir = tmp_path / "swing-data"
    cfg_dir.mkdir()
    return cfg_dir / "user-config.toml"


def test_get_user_config_path_returns_userprofile_path(isolated_user_config: Path):
    assert get_user_config_path() == isolated_user_config


def test_load_returns_empty_dict_when_file_missing(isolated_user_config: Path):
    assert not isolated_user_config.exists()
    assert load_user_overrides() == {}


def test_load_returns_empty_dict_when_file_malformed(
    isolated_user_config: Path, caplog: pytest.LogCaptureFixture,
):
    isolated_user_config.write_text("this is not = valid toml [[[", encoding="utf-8")
    with caplog.at_level("WARNING"):
        result = load_user_overrides()
    assert result == {}
    assert any("malformed" in r.message.lower() or "parse" in r.message.lower()
               for r in caplog.records)
    # File must NOT be deleted (preserve operator's content for inspection).
    assert isolated_user_config.exists()


def test_round_trip_flat_field(isolated_user_config: Path):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    assert load_user_overrides() == {"web": {"chase_factor": 0.02}}


def test_round_trip_multiple_sections(isolated_user_config: Path):
    payload = {
        "account": {"risk_equity_floor": 10000.0},
        "pipeline": {"chart_top_n_watch": 15},
        "web": {"chase_factor": 0.02},
    }
    write_user_overrides(payload)
    assert load_user_overrides() == payload


def test_toml_text_repr_float_and_int(isolated_user_config: Path):
    """Text-level check: tomli_w must emit canonical float/int repr.

    Codex R1 Major 4: round-trip tests don't catch textual drift like
    '15.0' for int or '0.020' for float. Assert the raw file bytes directly.
    """
    write_user_overrides({
        "account": {"risk_equity_floor": 10000.0},
        "pipeline": {"chart_top_n_watch": 15},
        "web": {"chase_factor": 0.02},
    })
    raw = isolated_user_config.read_text(encoding="utf-8")
    assert "risk_equity_floor = 10000.0" in raw   # float stays float
    assert "chart_top_n_watch = 15" in raw         # int NOT 15.0
    assert "chase_factor = 0.02" in raw            # NOT 0.020

def test_toml_empty_section_omitted(isolated_user_config: Path):
    """Section tables emitted ONLY when at least one key is present."""
    write_user_overrides({"web": {"chase_factor": 0.02}})
    raw = isolated_user_config.read_text(encoding="utf-8")
    assert "[web]" in raw
    assert "[account]" not in raw
    assert "[pipeline]" not in raw


def test_write_creates_directory_if_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    # Note: swing-data dir does NOT exist yet.
    write_user_overrides({"web": {"chase_factor": 0.02}})
    assert (tmp_path / "swing-data" / "user-config.toml").exists()


def test_atomic_write_uses_same_directory_tempfile(
    isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch,
):
    """CLAUDE.md cross-device-link gotcha: tempfile MUST be in dest dir.

    Discriminating-test: monkeypatch tempfile.NamedTemporaryFile to capture
    the `dir=` argument. If the implementation passes dir=None or relies on
    $TMP, this test fails — proving the cross-device guard is in place.
    """
    import tempfile as _tempfile
    captured: dict = {}
    real = _tempfile.NamedTemporaryFile

    def spy(*args, **kwargs):
        captured["dir"] = kwargs.get("dir")
        return real(*args, **kwargs)

    monkeypatch.setattr(_tempfile, "NamedTemporaryFile", spy)
    write_user_overrides({"web": {"chase_factor": 0.02}})
    assert captured["dir"] is not None
    assert Path(captured["dir"]).resolve() == isolated_user_config.parent.resolve()


def test_write_failure_leaves_destination_unchanged(
    isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Simulate failure mid-write: existing file content must survive."""
    isolated_user_config.write_text(
        "[web]\nchase_factor = 0.015\n", encoding="utf-8",
    )
    original_content = isolated_user_config.read_text(encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError):
        write_user_overrides({"web": {"chase_factor": 0.99}})
    assert isolated_user_config.read_text(encoding="utf-8") == original_content


def test_delete_field_removes_section_when_empty(isolated_user_config: Path):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    delete_user_override("web.chase_factor")
    assert load_user_overrides() == {}


def test_delete_field_preserves_other_section_keys(isolated_user_config: Path):
    write_user_overrides({
        "web": {"chase_factor": 0.02},
        "pipeline": {"chart_top_n_watch": 15},
    })
    delete_user_override("web.chase_factor")
    assert load_user_overrides() == {"pipeline": {"chart_top_n_watch": 15}}


def test_delete_field_no_op_when_absent(isolated_user_config: Path):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    delete_user_override("account.risk_equity_floor")  # not present
    assert load_user_overrides() == {"web": {"chase_factor": 0.02}}


def test_write_backs_up_malformed_existing_file(
    isolated_user_config: Path, caplog: pytest.LogCaptureFixture,
):
    """Codex R3 Major 1 — auto-backup malformed file before overwrite.

    Discriminating-test: pre-populate user-config with broken TOML, write
    a valid override, then assert:
      (a) the new payload is at user-config.toml,
      (b) the broken content is preserved at user-config.malformed-*.toml,
      (c) a WARNING was logged.

    Pre-fix behavior (no guard): the malformed file is silently replaced
    with no recovery path; this test fails.
    Post-fix behavior: backup file exists with original broken content;
    this test passes.
    """
    isolated_user_config.write_text(
        "this is = not valid [[[ toml", encoding="utf-8",
    )
    original_broken = isolated_user_config.read_text(encoding="utf-8")
    with caplog.at_level("WARNING"):
        write_user_overrides({"web": {"chase_factor": 0.02}})
    assert load_user_overrides() == {"web": {"chase_factor": 0.02}}
    backups = list(isolated_user_config.parent.glob("user-config.malformed-*.toml"))
    assert len(backups) == 1, f"expected 1 backup, got {backups}"
    assert backups[0].read_text(encoding="utf-8") == original_broken
    assert any(
        "malformed" in r.message.lower() and "backed up" in r.message.lower()
        for r in caplog.records
    )


def test_write_backs_up_malformed_twice_without_collision(
    isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Codex R4 Major 1 — two malformed-recovery saves at the same
    timestamp must each preserve their backup. Without the collision
    counter, the second os.replace would clobber the first backup,
    silently losing the earlier malformed snapshot.

    Discriminating-test: monkeypatch datetime.now() to return a fixed
    value, then perform two malformed-recovery saves with DIFFERENT
    broken contents. Assert two distinct backup files survive (one with
    the counter suffix), each holding its respective broken content.
    """
    from datetime import datetime as _dt
    import swing.config_user as cu

    fixed_moment = _dt(2026, 5, 1, 12, 0, 0)

    class _FrozenClock:
        @staticmethod
        def now():
            return fixed_moment

    monkeypatch.setattr(cu, "_dt", _FrozenClock)

    # First malformed-recovery
    isolated_user_config.write_text("first broken [[[", encoding="utf-8")
    write_user_overrides({"web": {"chase_factor": 0.02}})
    # Second malformed-recovery (same fixed moment)
    isolated_user_config.write_text("second broken ]]]", encoding="utf-8")
    write_user_overrides({"web": {"chase_factor": 0.03}})

    backups = sorted(
        isolated_user_config.parent.glob("user-config.malformed-*.toml")
    )
    assert len(backups) == 2, f"expected 2 distinct backups, got {backups}"
    contents = {b.read_text(encoding="utf-8") for b in backups}
    assert contents == {"first broken [[[", "second broken ]]]"}


def test_write_does_not_back_up_well_formed_existing_file(
    isolated_user_config: Path,
):
    """Codex R3 Major 1 — backup only fires for malformed files.

    Negative-discriminator: a well-formed existing file is replaced via
    the normal atomic-replace path (no .malformed-* artifact). Without
    this guard, every save would generate a backup file, polluting the
    config dir.
    """
    write_user_overrides({"web": {"chase_factor": 0.015}})  # well-formed
    write_user_overrides({"web": {"chase_factor": 0.025}})  # overwrite
    backups = list(isolated_user_config.parent.glob("user-config.malformed-*.toml"))
    assert backups == []
    assert load_user_overrides() == {"web": {"chase_factor": 0.025}}
