from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import pytest

from swing.integrations.schwab.client import RedactingFormatter
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
    from tests.cli.test_cli_eval import _minimal_config
    from swing.config import load
    from dataclasses import replace
    from swing.config import LoggingConfig
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = load(_minimal_config(project, home))
    if logging_kwargs:
        cfg = replace(cfg, logging=replace(cfg.logging, **logging_kwargs))
    return cfg


def test_install_logging_attaches_redacting_rotating_handler(clean_root_and_secrets, tmp_path):
    cfg = _cfg(tmp_path)
    install_logging(cfg, surface="web")
    target = str(cfg.paths.logs_dir / "web.log")
    handlers = [
        h for h in clean_root_and_secrets.handlers
        if isinstance(h, RotatingFileHandler) and h.baseFilename == target
    ]
    assert len(handlers) == 1
    assert isinstance(handlers[0].formatter, RedactingFormatter)  # Belt B by construction
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
