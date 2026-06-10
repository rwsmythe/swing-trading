from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import pytest

from swing.logging_setup import install_logging


@pytest.fixture
def clean_root_and_secrets():
    import swing.integrations.schwab.client as sc
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    saved_factory = logging.getLogRecordFactory()
    saved_secrets = set(sc._GLOBAL_KNOWN_SECRETS)
    for h in list(root.handlers):
        root.removeHandler(h)
    yield root
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler):
            h.close()
        root.removeHandler(h)
    for h in saved:
        root.addHandler(h)
    root.setLevel(saved_level)
    logging.setLogRecordFactory(saved_factory)
    sc._GLOBAL_KNOWN_SECRETS.clear()
    sc._GLOBAL_KNOWN_SECRETS.update(saved_secrets)


def _cfg(tmp_path, **logging_kwargs):
    from dataclasses import replace

    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = load(_minimal_config(project, home))
    if logging_kwargs:
        cfg = replace(cfg, logging=replace(cfg.logging, **logging_kwargs))
    return cfg


def test_install_logging_attaches_redacting_rotating_handler(clean_root_and_secrets, tmp_path):
    # Resolve RedactingFormatter FRESHLY here (not the module-top import): a sibling
    # research L2-lock test on this xdist worker may `del sys.modules` + re-import
    # swing.integrations.schwab.client, replacing the class object. install_logging
    # resolves the class via a lazy import at call time, so the assertion must match
    # the CURRENT module attribute or isinstance falsely fails (reload-fragility gotcha).
    from swing.integrations.schwab.client import RedactingFormatter as _RedactingFormatter
    cfg = _cfg(tmp_path)
    install_logging(cfg, surface="web")
    target = str(cfg.paths.logs_dir / "web.log")
    handlers = [
        h for h in clean_root_and_secrets.handlers
        if isinstance(h, RotatingFileHandler) and h.baseFilename == target
    ]
    assert len(handlers) == 1
    assert isinstance(handlers[0].formatter, _RedactingFormatter)  # Belt B by construction
    assert handlers[0].maxBytes == cfg.logging.max_bytes
    assert handlers[0].backupCount == cfg.logging.backup_count


def test_install_logging_sets_root_level_from_config(clean_root_and_secrets, tmp_path):
    cfg = _cfg(tmp_path, level=logging.DEBUG)
    install_logging(cfg, surface="pipeline")
    assert clean_root_and_secrets.level == logging.DEBUG


def test_install_logging_installs_belt_a_factory(clean_root_and_secrets, tmp_path):
    # Belt A: install_logging must install the process-global Schwab LogRecord
    # factory (injected into the seam via install_record_factory). The schwab
    # factory carries the `_is_schwab_factory` tag (client.py).
    cfg = _cfg(tmp_path)
    install_logging(cfg, surface="pipeline")
    assert getattr(logging.getLogRecordFactory(), "_is_schwab_factory", False)


def test_diagnostics_replayed_after_handler_attaches(clean_root_and_secrets, tmp_path):
    # A collected parse warning must land in the surface log AFTER install.
    cfg = _cfg(tmp_path, warnings=("[logging] level 'LOUD' invalid; using INFO",))
    install_logging(cfg, surface="pipeline")
    target = cfg.paths.logs_dir / "pipeline.log"
    for h in clean_root_and_secrets.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    text = target.read_text(encoding="utf-8")
    assert "level 'LOUD' invalid" in text


def test_diagnostics_bypass_high_root_level(clean_root_and_secrets, tmp_path):
    # Threshold-guarantee (R2-major-2): with a VALID level=ERROR the WARNING-level
    # diagnostic must STILL land (it is replayed via handler.handle, bypassing the
    # root threshold). Discriminator: a naive logger.warning() call would be
    # swallowed by the ERROR root level and the assertion would FAIL.
    cfg = _cfg(tmp_path, level=logging.ERROR,
               warnings=("[logging] max_bytes 'huge' invalid; using 10485760",))
    install_logging(cfg, surface="pipeline")
    assert clean_root_and_secrets.level == logging.ERROR
    target = cfg.paths.logs_dir / "pipeline.log"
    for h in clean_root_and_secrets.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    text = target.read_text(encoding="utf-8")
    assert "max_bytes 'huge' invalid" in text


def test_diagnostics_replay_is_idempotent(clean_root_and_secrets, tmp_path):
    # Codex R1 MINOR: a second install_logging with the SAME warning-bearing cfg
    # hits the dedup-refresh path (same handler object) and must NOT re-emit the
    # diagnostics. Discriminator: without the replayed-tag guard the count is 2.
    cfg = _cfg(tmp_path, warnings=("[logging] level 'LOUD' invalid; using INFO",))
    install_logging(cfg, surface="pipeline")
    install_logging(cfg, surface="pipeline")
    target = cfg.paths.logs_dir / "pipeline.log"
    for h in clean_root_and_secrets.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    text = target.read_text(encoding="utf-8")
    assert text.count("level 'LOUD' invalid") == 1


def test_diagnostics_replay_ignores_foreign_same_path_handler(clean_root_and_secrets, tmp_path):
    # Codex R1 MAJOR: a foreign (non-swing-tagged) RotatingFileHandler sharing the
    # same baseFilename must NOT intercept the diagnostic replay -- only the
    # swing-tagged surface handler (with Belt B + NOTSET) may. Discriminator: the
    # foreign handler stamps a FOREIGN marker; routing through it would put FOREIGN
    # in the file. With the surface-tag predicate the swing handler handles it instead.
    import os

    cfg = _cfg(tmp_path, warnings=("[logging] level 'LOUD' invalid; using INFO",))
    target = os.path.abspath(cfg.paths.logs_dir / "pipeline.log")
    cfg.paths.logs_dir.mkdir(parents=True, exist_ok=True)
    foreign = RotatingFileHandler(target, delay=True)
    foreign.setFormatter(logging.Formatter("FOREIGN %(message)s"))  # NOT a RedactingFormatter
    clean_root_and_secrets.addHandler(foreign)
    try:
        install_logging(cfg, surface="pipeline")
        for h in clean_root_and_secrets.handlers:
            if isinstance(h, RotatingFileHandler):
                h.flush()
        text = (cfg.paths.logs_dir / "pipeline.log").read_text(encoding="utf-8")
        assert "level 'LOUD' invalid" in text
        assert "FOREIGN" not in text  # the foreign handler never received the replay
    finally:
        clean_root_and_secrets.removeHandler(foreign)
        foreign.close()
