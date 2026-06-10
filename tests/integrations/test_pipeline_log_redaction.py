# tests/integrations/test_pipeline_log_redaction.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import pytest

from swing.integrations.schwab import client as schwab_client
from swing.integrations.schwab.client import (
    RedactingFormatter,
    ensure_schwab_log_redaction_factory_installed,
    register_schwab_secrets,
)
from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging

# A token-shaped sentinel the 32+hex heuristic redactor will catch by shape.
SENTINEL = "deadbeef" * 8  # 64 hex chars
# A NON-shape sentinel: hyphens break the alnum runs (longest run < 24 b64 chars,
# no 32+hex run) so ONLY Layer-0 exact-match (the registered set) can catch it.
NONSHAPE_LATE = "late-secret-zz-value-001"


@pytest.fixture
def pipeline_logging(tmp_path):
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    # Snapshot the process-global secret set so a late-registered sentinel does not
    # leak into sibling tests / other files (e.g. the schwab redaction-audit grep).
    saved_secrets = set(schwab_client._GLOBAL_KNOWN_SECRETS)
    saved_factory = logging.getLogRecordFactory()  # restore Belt A's global mutation
    for h in list(root.handlers):
        root.removeHandler(h)
    ensure_schwab_log_redaction_factory_installed()  # Belt A first
    configure_logging(
        tmp_path, surface="pipeline",
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT),  # Belt B
    )
    yield tmp_path / "pipeline.log"
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler):
            h.close()
        root.removeHandler(h)
    for h in saved:
        root.addHandler(h)
    root.setLevel(saved_level)
    logging.setLogRecordFactory(saved_factory)
    schwab_client._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client._GLOBAL_KNOWN_SECRETS.update(saved_secrets)


def _read(path):
    for h in logging.getLogger().handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    return path.read_text(encoding="utf-8")


def test_handler_carries_redacting_formatter_at_attach(pipeline_logging):
    handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
    ]
    assert any(isinstance(h.formatter, RedactingFormatter) for h in handlers)


def test_non_schwabdev_logger_line_is_redacted(pipeline_logging):
    # A swing.pipeline.* logger -- Belt A (Schwabdev-prefix) would NOT cover it.
    logging.getLogger("swing.pipeline.lease").warning("leaked token=%s", SENTINEL)
    text = _read(pipeline_logging)
    assert SENTINEL not in text


def test_exception_traceback_is_redacted(pipeline_logging):
    try:
        raise RuntimeError(f"boom with {SENTINEL}")
    except RuntimeError:
        logging.getLogger("swing.pipeline.runner").error("step failed", exc_info=True)
    text = _read(pipeline_logging)
    assert SENTINEL not in text


def test_late_registered_secret_is_redacted(pipeline_logging):
    # A NON-shape secret registered ONLY after handler attach -- proves format()
    # consults the LIVE secret set per record (R2-Major-1). Discriminator: under a
    # snapshot-at-attach impl, NONSHAPE_LATE (not in the set at attach, not
    # shape-caught) would survive -> "not in text" would FAIL. Under correct
    # per-record consultation it is redacted.
    register_schwab_secrets([NONSHAPE_LATE])  # registered AFTER handler attach
    logging.getLogger("swing.pipeline.lease").info("late=%s", NONSHAPE_LATE)
    text = _read(pipeline_logging)
    assert NONSHAPE_LATE not in text


def test_long_line_is_redacted_without_truncation(pipeline_logging):
    # A line > 500 chars with the secret early and a TAIL_MARKER past char 500.
    # CORRECT (full-line redactor): SENTINEL redacted AND TAIL_MARKER preserved.
    # NAIVE (the [:500]-truncating _make_redactor_from_global): the line is cut at
    # 500 chars -> TAIL_MARKER is DROPPED -> the marker assertion FAILS. Discriminates
    # truncating-vs-full redaction.
    tail_marker = "TAILMARKERPRESENT"
    padding = "x" * 600
    logging.getLogger("swing.pipeline.runner").info(
        "secret=%s pad=%s end=%s", SENTINEL, padding, tail_marker
    )
    text = _read(pipeline_logging)
    assert SENTINEL not in text
    assert tail_marker in text  # fails under the 500-char-truncating redactor


def test_pipeline_run_cmd_writes_pipeline_log(tmp_path, monkeypatch):
    """Direct `swing pipeline run` wires the pipeline.log handler in-process (the
    same wiring the web subprocess uses). Proves self-containment without a real
    run: a stub run_pipeline emits a per-step line that lands in pipeline.log."""
    import swing.cli as cli
    import swing.config_overrides as config_overrides
    import swing.pipeline as pipeline_pkg
    from click.testing import CliRunner
    from swing.config import load
    from swing.pipeline.runner import RunResult
    from tests.cli.test_cli_eval import _minimal_config

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    logs_dir = load(cfg_path).paths.logs_dir  # the real cfg logs dir

    # apply_overrides + run_pipeline are imported INSIDE pipeline_run_cmd
    # (`from swing.config_overrides import apply_overrides`,
    #  `from swing.pipeline import run_pipeline`) -> patch the IMPORT SOURCES.
    # Identity apply_overrides keeps the test hermetic (no operator user-config read).
    monkeypatch.setattr(config_overrides, "apply_overrides", lambda cfg: cfg)

    # Emit a benign per-step line AND a secret SENTINEL through a swing.pipeline.*
    # (non-Schwabdev) logger. The benign line proves pipeline.log is written; the
    # SENTINEL proves the CLI wired Belt B (RedactingFormatter) -- without it the
    # SENTINEL would survive (Belt A alone does not cover swing.pipeline.* loggers).
    def fake_run_pipeline(*, cfg, trigger):
        log = logging.getLogger("swing.pipeline.lease")
        log.info("step ordinal=0 name=evaluate took 5 ms")
        log.warning("leaked token=%s", SENTINEL)
        return RunResult(run_id=1, state="complete", error_message=None)

    monkeypatch.setattr(pipeline_pkg, "run_pipeline", fake_run_pipeline)

    # Snapshot/restore root handlers AND level so this test's pipeline.log handler
    # + the INFO level set by configure_logging do not bleed into sibling tests.
    from logging.handlers import RotatingFileHandler
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    try:
        result = CliRunner().invoke(
            cli.main, ["--config", str(cfg_path), "pipeline", "run", "--manual"]
        )
        assert result.exit_code == 0, result.output
        # The CLI-installed pipeline.log handler must carry Belt B at attach time.
        cli_handlers = [
            h for h in root.handlers
            if isinstance(h, RotatingFileHandler)
            and h.baseFilename == str(logs_dir / "pipeline.log")
        ]
        assert cli_handlers, "CLI did not attach a pipeline.log handler"
        assert isinstance(cli_handlers[0].formatter, RedactingFormatter)
        for h in cli_handlers:
            h.flush()
        text = (logs_dir / "pipeline.log").read_text(encoding="utf-8")
        assert "name=evaluate took 5 ms" in text  # pipeline.log written
        assert SENTINEL not in text                # Belt B wired by the CLI
    finally:
        for h in list(root.handlers):
            if h not in saved and isinstance(h, RotatingFileHandler):
                h.close()
                root.removeHandler(h)
        root.setLevel(saved_level)


@pytest.fixture
def web_logging(tmp_path):
    """Same shape as ``pipeline_logging`` but for the web surface, via the shim."""
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    saved_secrets = set(schwab_client._GLOBAL_KNOWN_SECRETS)
    saved_factory = logging.getLogRecordFactory()
    for h in list(root.handlers):
        root.removeHandler(h)
    from swing.web.middleware.request_id import configure_web_logging
    configure_web_logging(tmp_path)  # no-cfg shim -> Belt A + Belt B by construction
    yield tmp_path / "web.log"
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler):
            h.close()
        root.removeHandler(h)
    for h in saved:
        root.addHandler(h)
    root.setLevel(saved_level)
    logging.setLogRecordFactory(saved_factory)
    schwab_client._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client._GLOBAL_KNOWN_SECRETS.update(saved_secrets)


def test_web_handler_carries_redacting_formatter_at_attach(web_logging):
    handlers = [
        h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)
    ]
    # No unredacted window: the formatter is a RedactingFormatter at attach time.
    assert any(isinstance(h.formatter, RedactingFormatter) for h in handlers)


def test_web_non_schwabdev_logger_line_is_redacted(web_logging):
    # A non-Schwabdev logger -- Belt A's prefix check would NOT cover it; only
    # Belt B (now wired into web.log) redacts it. Discriminator: against the CURRENT
    # plain shim (no formatter) the SENTINEL SURVIVES -> assertion FAILS; the shim
    # rewrite (Step 3) attaches RedactingFormatter -> SENTINEL redacted -> PASS.
    logging.getLogger("swing.web.access").warning("leaked token=%s", SENTINEL)
    text = _read(web_logging)
    assert SENTINEL not in text
