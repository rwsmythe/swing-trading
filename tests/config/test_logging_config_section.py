from __future__ import annotations

import logging

from swing.config import LoggingConfig, _parse_logging_config


def test_defaults_when_section_absent():
    lc = _parse_logging_config({})
    assert lc.level == logging.INFO
    assert lc.max_bytes == 10 * 1024 * 1024
    assert lc.backup_count == 5
    assert lc.warnings == ()


def test_parses_tracked_values():
    lc = _parse_logging_config({"level": "DEBUG", "max_bytes": 2048, "backup_count": 3})
    assert lc.level == logging.DEBUG
    assert lc.max_bytes == 2048
    assert lc.backup_count == 3
    assert lc.warnings == ()


def test_malformed_level_degrades_to_info_without_crash():
    # Discriminator: a naive getattr(logging, "LOUD") would raise AttributeError
    # (crash). Correct: map-lookup miss -> INFO + a collected warning.
    lc = _parse_logging_config({"level": "LOUD"})
    assert lc.level == logging.INFO
    assert any("level" in w and "LOUD" in w for w in lc.warnings)


def test_malformed_max_bytes_degrades_to_default():
    lc = _parse_logging_config({"max_bytes": "huge"})
    assert lc.max_bytes == 10 * 1024 * 1024
    assert any("max_bytes" in w for w in lc.warnings)


def test_bool_is_not_accepted_as_int():
    # bool is an int subclass; True must not be silently accepted as max_bytes.
    lc = _parse_logging_config({"max_bytes": True, "backup_count": False})
    assert lc.max_bytes == 10 * 1024 * 1024
    assert lc.backup_count == 5


def test_backup_count_zero_rejected():
    # backupCount=0 defeats the retention narrative -> degrade to default + warn.
    lc = _parse_logging_config({"backup_count": 0})
    assert lc.backup_count == 5
    assert any("backup_count" in w for w in lc.warnings)


def test_non_dict_logging_section_degrades_without_crash():
    # `logging = "INFO"` in TOML yields a non-dict -> must not raise AttributeError.
    lc = _parse_logging_config("INFO")
    assert lc.level == logging.INFO
    assert lc.max_bytes == 10 * 1024 * 1024
    assert lc.backup_count == 5
    assert any("table" in w for w in lc.warnings)


def test_load_attaches_logging_to_config(tmp_path):
    from tests.cli.test_cli_eval import _minimal_config
    from swing.config import load
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = load(_minimal_config(project, home))
    assert isinstance(cfg.logging, LoggingConfig)
    assert cfg.logging.level == logging.INFO  # _minimal_config has no [logging] -> default


def test_user_config_overlay_overrides_level(tmp_path, monkeypatch):
    from tests.cli.test_cli_eval import _minimal_config
    from swing.config import load
    import swing.config_overrides as overrides_mod

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = load(_minimal_config(project, home))
    assert cfg.logging.level == logging.INFO  # tracked default

    # Simulate user-config.toml [logging] override.
    monkeypatch.setattr(
        overrides_mod, "load_user_overrides",
        lambda: {"logging": {"level": "DEBUG", "backup_count": 9}},
    )
    eff = overrides_mod.apply_overrides(cfg)
    assert eff.logging.level == logging.DEBUG
    assert eff.logging.backup_count == 9
    assert eff.logging.max_bytes == cfg.logging.max_bytes  # untouched key preserved


def test_user_config_non_dict_logging_degrades(tmp_path, monkeypatch):
    # A non-table user-config [logging] (e.g. `logging = "INFO"`) must keep the base
    # values + append a warning, never crash (symmetry with load()'s guard).
    from tests.cli.test_cli_eval import _minimal_config
    from swing.config import load
    import swing.config_overrides as overrides_mod

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = load(_minimal_config(project, home))
    monkeypatch.setattr(
        overrides_mod, "load_user_overrides", lambda: {"logging": "INFO"},
    )
    eff = overrides_mod.apply_overrides(cfg)
    assert eff.logging.level == cfg.logging.level          # base preserved
    assert eff.logging.max_bytes == cfg.logging.max_bytes
    assert any("must be a table" in w for w in eff.logging.warnings)
