# tests/test_logging_config.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import pytest

from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging
from swing.pipeline import lease as lease_mod


@pytest.fixture
def clean_root():
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
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


def _file_handlers(root, target):
    return [
        h for h in root.handlers
        if isinstance(h, RotatingFileHandler) and h.baseFilename == str(target)
    ]


def test_pipeline_surface_attaches_named_handler(clean_root, tmp_path):
    configure_logging(tmp_path, surface="pipeline")
    target = tmp_path / "pipeline.log"
    handlers = _file_handlers(clean_root, target)
    assert len(handlers) == 1
    assert handlers[0].backupCount == 5
    assert handlers[0].maxBytes == 10 * 1024 * 1024
    assert clean_root.level == logging.INFO


def test_web_surface_matches_legacy_filename(clean_root, tmp_path):
    configure_logging(tmp_path, surface="web")
    assert _file_handlers(clean_root, tmp_path / "web.log")


def test_invalid_surface_rejected(clean_root, tmp_path):
    with pytest.raises(ValueError):
        configure_logging(tmp_path, surface="bogus")


def test_idempotent_dedup_by_basefilename(clean_root, tmp_path):
    configure_logging(tmp_path, surface="pipeline")
    configure_logging(tmp_path, surface="pipeline")
    assert len(_file_handlers(clean_root, tmp_path / "pipeline.log")) == 1


def test_dedup_path_still_sets_root_level(clean_root, tmp_path):
    # A same-file handler already exists AND root is at WARNING (e.g. attached by a
    # prior call / another lib). The dedup early-return MUST still lower root to INFO,
    # else pipeline INFO per-step lines stay suppressed.
    configure_logging(tmp_path, surface="pipeline")
    clean_root.setLevel(logging.WARNING)  # simulate a stale/raised level
    configure_logging(tmp_path, surface="pipeline")  # hits the dedup path
    assert clean_root.level == logging.INFO


def test_supplied_formatter_installs_on_preexisting_handler(clean_root, tmp_path):
    # First call: default formatter, no override.
    configure_logging(tmp_path, surface="pipeline")
    target = tmp_path / "pipeline.log"
    handler = _file_handlers(clean_root, target)[0]
    assert handler.formatter._fmt == DEFAULT_LOG_FORMAT

    # Second call supplies a distinct formatter: R2-Major-2 — must setFormatter,
    # not silently return with the old default in place.
    marker = logging.Formatter("REDACTED %(message)s")
    configure_logging(tmp_path, surface="pipeline", formatter=marker)
    assert len(_file_handlers(clean_root, target)) == 1  # still deduped
    assert handler.formatter is marker


def test_new_log_strings_are_ascii():
    # New operator-facing log strings must be ASCII (cp1252 stdout footgun).
    from swing.data.repos.pipeline_step_timings import StepTiming
    t = StepTiming(2, "finviz_fetch", "2026-06-09T00:00:00", "2026-06-09T00:00:01", 70000)
    import io
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(logging.Formatter("%(message)s"))
    lg = logging.getLogger("swing.pipeline.lease")
    saved_level = lg.level
    lg.addHandler(h)
    lg.setLevel(logging.INFO)  # else INFO _emit_step_line/_emit_totals_line are suppressed
    try:
        lease_mod._emit_step_line(t)          # INFO + WARN (70000 > 60000)
        lease_mod._emit_totals_line({"finviz_fetch": 70000})
    finally:
        lg.removeHandler(h)
        lg.setLevel(saved_level)
    out = buf.getvalue()
    assert "took" in out and "totals" in out  # confirm INFO lines were captured
    out.encode("ascii")  # raises UnicodeEncodeError if any non-ASCII slipped in


def test_pipeline_handler_is_utf8(clean_root, tmp_path):
    from swing.logging_config import configure_logging
    configure_logging(tmp_path, surface="pipeline")
    h = next(
        x for x in logging.getLogger().handlers
        if isinstance(x, RotatingFileHandler)
        and x.baseFilename == str(tmp_path / "pipeline.log")
    )
    assert h.encoding == "utf-8"


def test_retention_caps_managed_file_set(clean_root, tmp_path):
    # Drive writes FAR exceeding max_bytes * (backup_count + 1) = 2048 * 3 = 6144 B.
    configure_logging(tmp_path, surface="pipeline", max_bytes=2048, backup_count=2)
    log = logging.getLogger("swing.pipeline.cap_test")
    log.setLevel(logging.INFO)
    for _ in range(2000):
        log.info("x" * 100)            # ~200 KB total -> forces many rollovers
    for h in clean_root.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    managed = sorted(tmp_path.glob("pipeline.log*"))
    # Bounded BY CONSTRUCTION: at most backup_count + 1 files...
    assert len(managed) <= 3
    # ...and each <= ~max_bytes. THIS is the discriminator: under the old
    # unbounded TimedRotatingFileHandler the single pipeline.log balloons to
    # ~200 KB and this assertion FAILS; only the size cap makes it pass.
    for f in managed:
        assert f.stat().st_size <= 2048 * 2


def test_handler_is_rotating_file_handler(clean_root, tmp_path):
    configure_logging(tmp_path, surface="pipeline")
    h = _file_handlers(clean_root, tmp_path / "pipeline.log")[0]
    assert isinstance(h, RotatingFileHandler)
    assert h.maxBytes == 10 * 1024 * 1024
    assert h.backupCount == 5


def test_handler_level_is_notset(clean_root, tmp_path):
    # R4-major-1: thresholding is owned by root, never the handler.
    configure_logging(tmp_path, surface="pipeline", level=logging.DEBUG)
    h = _file_handlers(clean_root, tmp_path / "pipeline.log")[0]
    assert h.level == logging.NOTSET  # 0
    assert clean_root.level == logging.DEBUG


def test_dedup_does_not_mutate_rotation_params(clean_root, tmp_path):
    # D4 / R1-minor-1: a second call with DIFFERENT max_bytes must NOT change the
    # already-attached handler's maxBytes (mutating it mid-process orphans rotation).
    configure_logging(tmp_path, surface="pipeline", max_bytes=4096, backup_count=3)
    h = _file_handlers(clean_root, tmp_path / "pipeline.log")[0]
    configure_logging(tmp_path, surface="pipeline", max_bytes=999, backup_count=99)
    assert h.maxBytes == 4096      # unchanged
    assert h.backupCount == 3      # unchanged
    assert len(_file_handlers(clean_root, tmp_path / "pipeline.log")) == 1  # still deduped


def test_install_record_factory_is_called(clean_root, tmp_path):
    calls = []
    configure_logging(
        tmp_path, surface="pipeline",
        install_record_factory=lambda: calls.append(1),
    )
    assert calls == [1]


def test_logger_levels_applied(clean_root, tmp_path):
    configure_logging(
        tmp_path, surface="pipeline",
        logger_levels={"some.noisy.lib": logging.WARNING},
    )
    assert logging.getLogger("some.noisy.lib").level == logging.WARNING


def test_record_filter_replace_not_append(clean_root, tmp_path):
    # R5-minor-1: two configure calls with two distinct swing filters leave
    # EXACTLY ONE swing-tagged filter on the handler (replace, not append).
    f1 = logging.Filter()
    f2 = logging.Filter()
    configure_logging(tmp_path, surface="pipeline", record_filter=f1)
    configure_logging(tmp_path, surface="pipeline", record_filter=f2)
    h = _file_handlers(clean_root, tmp_path / "pipeline.log")[0]
    swing_filters = [x for x in h.filters if getattr(x, "_swing_correlation", False)]
    assert len(swing_filters) == 1
    assert swing_filters[0] is f2


def test_cli_surface_accepted(clean_root, tmp_path):
    # Forward-compat: the seam accepts "cli" now (live cli routing is Slice 2).
    configure_logging(tmp_path, surface="cli")
    assert _file_handlers(clean_root, tmp_path / "cli.log")


def test_handler_uses_delay_open(clean_root, tmp_path):
    configure_logging(tmp_path, surface="pipeline")
    h = _file_handlers(clean_root, tmp_path / "pipeline.log")[0]
    assert h.delay is True


def test_single_surface_per_process(clean_root, tmp_path):
    # §3.4: installing a DIFFERENT surface in the same process removes AND closes
    # the prior swing handler -> exactly one swing handler, no record tee-ing.
    import os
    configure_logging(tmp_path, surface="web")
    web_handler = next(
        h for h in clean_root.handlers
        if getattr(h, "_swing_surface", None) == "web"
    )
    logging.getLogger("swing.web.access").warning("open the web stream")  # force stream open
    assert web_handler.stream is not None
    configure_logging(tmp_path, surface="pipeline")
    swing = [
        h for h in clean_root.handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) is not None
    ]
    assert len(swing) == 1
    assert swing[0].baseFilename == os.path.abspath(tmp_path / "pipeline.log")
    assert swing[0]._swing_surface == "pipeline"
    # close() sets FileHandler.stream to None -> proves the old fd was released
    # (Windows rename/rotation requirement), not merely detached from root.
    assert web_handler.stream is None


def test_foreign_handler_is_not_removed(clean_root, tmp_path):
    # The single-surface sweep must never touch a non-swing-tagged handler.
    foreign = RotatingFileHandler(str(tmp_path / "foreign.log"), delay=True)
    clean_root.addHandler(foreign)
    try:
        configure_logging(tmp_path, surface="web")
        configure_logging(tmp_path, surface="pipeline")
        assert foreign in clean_root.handlers  # untouched
    finally:
        clean_root.removeHandler(foreign)
        foreign.close()


def test_formatter_is_set_before_add_to_root(clean_root, tmp_path, monkeypatch):
    # "No unredacted window" -- the handler must already carry the supplied
    # formatter AT addHandler time, not set afterward. Discriminator: an impl that
    # addHandler()s first and setFormatter()s after would record formatter=None here.
    marker = logging.Formatter("MARKER %(message)s")
    seen = {}
    real_add = clean_root.addHandler

    def spy_add(h):
        if isinstance(h, RotatingFileHandler) and getattr(h, "_swing_surface", None):
            seen["fmt_at_add"] = h.formatter
        return real_add(h)

    monkeypatch.setattr(clean_root, "addHandler", spy_add)
    configure_logging(tmp_path, surface="pipeline", formatter=marker)
    assert seen.get("fmt_at_add") is marker
