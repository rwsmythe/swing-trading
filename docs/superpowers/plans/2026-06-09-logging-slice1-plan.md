# Phase 16 / Arc 2 / Slice 1 — Logging disk-pain + safety core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Arc-1 logging seam into a centralized, redaction-by-construction, size-bounded logging system for the web + pipeline surfaces, plus an operator-gated one-time log-compression command and a suite-wide fix for the test leak into the operator's real log dir.

**Architecture:** Separate the **Schwab-agnostic seam** (`swing/logging_config.py:configure_logging`, extended with additive injection + size-based rotation) from a new **composition root** (`swing/logging_setup.py:install_logging`) that wires the redaction belts by construction. Config-driven rotation params arrive via a new `[logging]` section parsed into a `LoggingConfig` dataclass. The suite is stopped from leaking into the real `~/swing-data/logs` via an autouse home-redirect fixture. A pure `swing/logs_maintenance.py` module + a gated `swing logs cleanup` CLI command compress the pre-existing oversized legacy files content-preservingly.

**Tech Stack:** Python 3.14, stdlib `logging` (`RotatingFileHandler`), `gzip`/`hashlib`, click CLI, pytest, frozen dataclasses, SQLite (read-only pipeline-state check).

**Source spec (LOCKED, Codex-converged):** [`docs/superpowers/specs/2026-06-09-logging-overhaul-design.md`](../specs/2026-06-09-logging-overhaul-design.md). This plan implements **Slice 1 only** (§3 architecture for web+pipeline, §4, and the §6 tests for those). Slice 2 (§5: `cli.log`, correlation, the per-logger override table) is OUT.

**Schema:** NONE — v25 holds. Zero migrations.

---

## Plan-time decisions (resolving the dispatch brief §3)

These four decisions were left by the spec to writing-plans. They are LOCKED here and each is realized by a named task + acceptance below.

### D1 — Test-leak fix mechanism (brief §3.1; spec §4.3 / 2e) → Task 5

**Decision:** An **autouse function-scoped fixture in the root `tests/conftest.py`** that monkeypatches `swing.config._user_home` **and** the `USERPROFILE`/`HOME` env vars to a **session-stable** temp home dir (one dir per pytest session via a `session`-scoped helper fixture).

**Why this shape (against the brief's three candidates):**
- The leak's mechanism is precise: `swing.config.load()` resolves the relative `logs_dir = "swing-data/logs"` (and `sample_config` in `tests/conftest.py:389` does the same) against `_user_home()`, which reads the **un-monkeypatched real `$USERPROFILE`** → `~/swing-data/logs`. `create_app()` then calls the web-log wiring at construction time (`app.py:441`), attaching a **root-logger** file handler at that real path. Because the handler lives on the root logger and is never torn down between tests, a **single** leaking test poisons the whole process — every subsequent `httpx`/`swing.web.access`/traceback record across the suite is written to the operator's real `web.log` (the 33.6 K `httpx: testserver` lines + synthetic tracebacks the spec measured).
- Patching `swing.config._user_home` targets that exact resolution point with **minimal blast radius**: only swing's relative-path resolution shifts to the temp home. Tests that already pass **absolute** tmp paths (the `_minimal_config` family — `tests/cli/test_cli_eval.py:33`) are unaffected (absolute paths short-circuit `_resolve_path`). The redaction/rotation tests pass an explicit absolute `tmp_path` `logs_dir` and so still exercise the real production wiring (the fix does not mask it).
- It is **hard to forget**: autouse means every current and future test inherits it without opt-in. Function-scoped `monkeypatch` auto-restores, so it never bleeds past the suite.
- Env `USERPROFILE`/`HOME` are also redirected (belt-and-suspenders) for any code reading the env directly rather than via `_user_home()` — the same dual-patch discipline as the `write_user_overrides` gotcha family.
- Rejected: "make app/log init refuse the real logs dir under pytest" (branches production code on a test-only condition — exactly the masking the brief warns against). Rejected: per-test opt-in fixture (easy to forget for new tests; the leak recurs silently).

**Guard test:** `tests/test_logging_leak_guard.py::test_suite_does_not_resolve_logs_to_real_home` — asserts `_user_home()` during the suite is NOT the real operator home (captured at conftest import, before any monkeypatch), and a `sample_config`-built `create_app` + request writes `web.log` under the temp home, never under the real `~/swing-data/logs`.

### D2 — Cleanup command CLI surface (brief §3.2; spec §4.2) → Task 6

**Decision:** A new `swing logs` group with one subcommand `swing logs cleanup`.
- **Default scope:** legacy dated artifacts only — files matching `{surface}.log.<YYYY-MM-DD>` (the suffix the old `TimedRotatingFileHandler` produced and the new `RotatingFileHandler` never will). The selection predicate **excludes** every active managed name (`{surface}.log`) and the numeric rotation set (`{surface}.log.<int>`) for all three surfaces, and skips anything already `.gz`.
- **Flags:** `--yes` (skip the interactive confirm, for scripted use); `--include-current` (the app-stopped reclaim scope that also targets oversized **current/rotated managed** files — the pre-existing 58/83/97 MB); `--web-stopped` (operator attestation, **required** with `--include-current`).
- **Gating:** refuses while a `pipeline_runs` `state='running'` row exists; **fail-closed** if the DB cannot be opened/queried (refuse, never proceed blind). Confirms interactively before acting unless `--yes`.
- **Safety:** content-preserving gzip with verify-before-unlink (streamed SHA-256 byte-equality of the decompressed temp `.gz` vs the original); collision-free archive names reserved atomically via `O_EXCL`; a single-instance lock file in `logs_dir`; `os.replace` temp created **in** `logs_dir` (same-filesystem Windows gotcha); ASCII-only stdout (cp1252 footgun); writes nothing outside `logs_dir`; never auto-runs, never wired into startup.
- **Split of concerns:** all filesystem logic lives in a **pure, click-free, DB-free** `swing/logs_maintenance.py` (directly unit-testable); `swing/cli.py` owns the click wiring, the confirm prompt, and the DB pipeline-running refusal.
- **Slice-1 note:** the cleanup command installs **no** `cli.log` handler (CLI-surface centralization is Slice 2), so the R6-major-1 self-surface exclusion is a no-op in Slice 1 — but the predicate defensively excludes `cli.log` names anyway so it is correct once Slice 2 lands.

### D3 — `LoggingConfig` placement + cascade (brief §3.3; spec §4.5) → Task 2

**Decision:** `LoggingConfig` is a new frozen dataclass in `swing/config.py` (alongside the other Config sub-dataclasses), attached to `Config` as `logging: LoggingConfig`. Slice-1 fields: `level: int` (resolved from a level NAME at parse time), `max_bytes: int` (default 10 MB), `backup_count: int` (default 5), and `warnings: tuple[str, ...]` (the deferred-diagnostics carrier — parse-time diagnostics are COLLECTED here, never logged at parse time, then replayed by `install_logging` after the redacted handler is attached).
- **Cascade:** `load()` parses the tracked `swing.config.toml [logging]` into `LoggingConfig`; `apply_overrides()` overlays `user-config.toml [logging]` (`level`/`max_bytes`/`backup_count`) by re-running the same validation over a merged dict. `pipeline_run_cmd` already calls `apply_overrides()` before logging setup, so the pipeline surface honors the user-config overlay; the web surface reads the cfg `create_app` was given (config is read once per process per spec §3.1).
- **Malformed degrades, never crashes:** a junk `level` → `INFO` + a collected warning; a junk/`<=0` `max_bytes` or junk/`<1` `backup_count` → the default + a collected warning; a non-table `[logging]` value (e.g. `logging = "INFO"`) → all defaults + a warning. No exception escapes parse.

### D4 — Dedup-refresh semantics (brief §3.4; spec §3.1 R1-minor-1) → Task 1

**Decision:** On a second `configure_logging` call for an already-attached same-surface handler, the seam refreshes **`level`** (root level, set on every path), **`formatter`** (if supplied), **`record_filter`** (replace, not append — see below), and re-applies **`logger_levels`** — but it does **NOT** mutate the existing handler's `maxBytes`/`backupCount` (mutating those mid-process orphans the rotation invariant; a param change takes effect on the next process start). The swing correlation filter is tagged so re-install removes the prior swing-tagged filter before adding the fresh one (R5-minor-1 — `Handler.addFilter` appends; naive re-install would accumulate duplicates). Foreign filters are never touched. Handler threshold stays `NOTSET` (R4-major-1).

---

## File Map

**Production code (change loci):**
- `swing/logging_config.py` — **modify**. The seam: `TimedRotatingFileHandler` → `RotatingFileHandler`; additive params (`max_bytes`, `backup_count`, `install_record_factory`, `logger_levels`, `record_filter`); dedup-refresh; `_replace_swing_filter` helper; single-surface enforcement (`_swing_surface` tag + remove-and-close a prior different-surface swing handler, §3.4); `surface` allowlist widened to include `"cli"` (forward-compat). Stays Schwab-agnostic (imports nothing from `swing.integrations.schwab`).
- `swing/config.py` — **modify**. New `LoggingConfig` dataclass + `_parse_logging_config` + `_LEVEL_NAMES`; `Config.logging` field; `load()` parses `[logging]`.
- `swing/config_overrides.py` — **modify**. `apply_overrides()` overlays `user-config.toml [logging]`.
- `swing/logging_setup.py` — **create**. The Schwab-AWARE composition root `install_logging(cfg, *, surface)` + `_replay_logging_diagnostics`. The only place the schwab belts are imported into the logging path.
- `swing/web/middleware/request_id.py` — **modify**. `configure_web_logging` RETAINED as a back-compat shim gaining an optional `cfg=None`.
- `swing/web/app.py:441` — **modify**. Call site migrated to `install_logging(cfg, surface="web")`.
- `swing/cli.py` — **modify**. `pipeline_run_cmd` logging block collapses to `install_logging(cfg, surface="pipeline")`; new `swing logs cleanup` command + `logs` group.
- `swing/logs_maintenance.py` — **create**. Pure (click-free, DB-free) filesystem logic for the cleanup command.
- `swing.config.toml` — **modify**. Add a `[logging]` section (committed defaults).

**Tests (change/create):**
- `tests/test_logging_config.py` — **modify** (flip `TimedRotatingFileHandler` → `RotatingFileHandler`; new seam tests).
- `tests/integrations/test_pipeline_log_redaction.py` — **modify** (flip handler class in fixtures; web-surface redaction audit added in Task 4).
- `tests/web/test_error_handling.py` — **modify** (flip handler class in `test_configure_web_logging_is_idempotent`).
- `tests/test_logging_setup.py` — **create** (install_logging composition root + diagnostics replay).
- `tests/config/test_logging_config_section.py` — **create** (`[logging]` parse + cascade + malformed).
- `tests/test_logging_leak_guard.py` — **create** (the D1 guard test).
- `tests/test_logs_maintenance.py` — **create** (pure-module selection + compression + verify).
- `tests/cli/test_logs_cleanup_cmd.py` — **create** (CLI gating + confirm + ASCII/PowerShell).

**Pre-flight (executing agent does this FIRST, before Task 1):** grep the whole `tests/` tree for `TimedRotatingFileHandler` and record every hit — all must flip to `RotatingFileHandler` in Task 1 so the suite stays green after the switch:
```bash
grep -rn "TimedRotatingFileHandler" tests/ swing/
```
Known hits at planning time: `tests/test_logging_config.py`, `tests/integrations/test_pipeline_log_redaction.py`, `swing/logging_config.py`, `swing/cli.py`. Re-run the grep on the worktree HEAD to catch any new ones.

---

## Task 1: Extend the seam — size-based RotatingFileHandler + additive injection

**Files:**
- Modify: `swing/logging_config.py`
- Modify (test flips + new tests): `tests/test_logging_config.py`
- Modify (test flips): `tests/integrations/test_pipeline_log_redaction.py`, `tests/web/test_error_handling.py`

This is the load-bearing task. The handler-class flip and every test that pins `TimedRotatingFileHandler` MUST land together (behavior contract, not the class name, is the lock — spec §6).

- [ ] **Step 1: Write the failing retention-cap test (the discriminating §4.1 test)**

First apply the Step 3 import flip + assertion updates to `tests/test_logging_config.py` (so the file imports `RotatingFileHandler` cleanly and the failure is a real `TypeError` from the seam, not a collection-time `NameError`). Then add this test:

```python
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
```

Discriminating arithmetic ([[feedback_regression_test_arithmetic]]): two layers. (a) Against the CURRENT (Arc-1) seam, `configure_logging` does not accept `max_bytes`/`backup_count`, so the call raises `TypeError` — the test fails at the call. (b) The SIZE assertion is the genuine size-cap discriminator: even a hypothetical seam that accepted the new params but kept the unbounded `TimedRotatingFileHandler` (`when="D"`, no size ceiling) would write a single ~200 KB `pipeline.log` → `200_000 <= 4096` is **False** → FAIL. Only the size-based `RotatingFileHandler` (cap 2048, backup 2) yields ≤3 files each ≤ ~2 KB → PASS.

- [ ] **Step 2: Run it — verify it fails**

Run: `python -m pytest tests/test_logging_config.py::test_retention_caps_managed_file_set -v`
Expected: FAIL with `TypeError: configure_logging() got an unexpected keyword argument 'max_bytes'` (the Arc-1 seam signature). After Step 3 flips the file's import and Step 4 rewrites the seam, it passes; the size assertion is what proves the size cap (not merely the new signature).

- [ ] **Step 3: Flip the test file's handler class + update pinned assertions** (applied in Step 1; this is the authoritative full list — confirm every item)

In `tests/test_logging_config.py`:
- Change `from logging.handlers import TimedRotatingFileHandler` → `from logging.handlers import RotatingFileHandler`.
- In `clean_root` and `_file_handlers`, replace every `isinstance(h, TimedRotatingFileHandler)` → `isinstance(h, RotatingFileHandler)`.
- In `test_pipeline_surface_attaches_named_handler`: change `assert handlers[0].backupCount == 7` → `assert handlers[0].backupCount == 5` and add `assert handlers[0].maxBytes == 10 * 1024 * 1024`.
- In `test_pipeline_handler_is_utf8`: `isinstance(x, TimedRotatingFileHandler)` → `isinstance(x, RotatingFileHandler)`.

In `tests/integrations/test_pipeline_log_redaction.py`:
- Change the import to `from logging.handlers import RotatingFileHandler` (top-level and the local re-import inside `test_pipeline_run_cmd_writes_pipeline_log`).
- Replace every `isinstance(..., TimedRotatingFileHandler)` → `isinstance(..., RotatingFileHandler)` (the `pipeline_logging` fixture teardown, `_read`, and the CLI test's handler lookup).

In `tests/web/test_error_handling.py::test_configure_web_logging_is_idempotent`: if it references `TimedRotatingFileHandler`, flip to `RotatingFileHandler`; if it only counts handlers behaviorally, leave it.

- [ ] **Step 4: Rewrite the seam (`swing/logging_config.py`)**

Replace the file body with:

```python
"""Neutral logging seam shared by the web app and the pipeline CLI subprocess.

Top-level (not under swing.web or swing.cli) so neither importer pulls in the
other. Schwab-agnostic by construction: it imports nothing from
swing.integrations.schwab -- the secret-bearing composition root
(swing/logging_setup.py) injects the RedactingFormatter via `formatter` and the
record-factory installer via `install_record_factory`.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Slice-2 widens the live routing to all three; the seam accepts "cli" now so
# the signature is forward-stable (no Slice-2 seam re-touch).
_SWING_SURFACES = frozenset({"web", "pipeline", "cli"})


def _replace_swing_filter(
    handler: logging.Handler, record_filter: logging.Filter,
) -> None:
    """Install ``record_filter`` as the SINGLE swing-tagged filter on ``handler``.

    ``Handler.addFilter`` APPENDS, so a naive re-install on the dedup path would
    accumulate duplicate filters (R5-minor-1). Tag the swing filter, remove any
    prior swing-tagged filter, then add the fresh one. Foreign filters (a
    library's own) are never touched.
    """
    record_filter._swing_correlation = True  # type: ignore[attr-defined]
    for existing in list(handler.filters):
        if getattr(existing, "_swing_correlation", False):
            handler.removeFilter(existing)
    handler.addFilter(record_filter)


def configure_logging(
    logs_dir: Path,
    *,
    surface: str,
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    install_record_factory: Callable[[], None] | None = None,
    logger_levels: dict[str, int] | None = None,
    record_filter: logging.Filter | None = None,
) -> None:
    """Attach a size-based ``RotatingFileHandler`` writing ``{surface}.log`` to root.

    Idempotent (dedup by baseFilename). ``surface`` in {'web','pipeline','cli'}.
    Belt A (the process-global LogRecord factory) is INJECTED via
    ``install_record_factory`` and CALLED here -- the seam never imports it, so it
    stays Schwab-agnostic. ``formatter`` (Belt B) is set on the handler BEFORE it
    joins root (no unredacted window). The handler threshold stays NOTSET (0):
    thresholding is owned by the root logger + per-logger overrides, never the
    handler (R4-major-1). On the dedup path the supplied ``formatter`` /
    ``record_filter`` / ``logger_levels`` / ``level`` are refreshed, but the
    already-attached handler's maxBytes/backupCount are NOT mutated
    (R1-minor-1) -- a rotation-param change takes effect on the next process start.
    Single surface per process (§3.4): swing handlers are tagged ``_swing_surface``;
    attaching a NEW surface removes AND closes any prior swing handler so a process
    writes exactly one surface file (foreign handlers are never touched).
    """
    if surface not in _SWING_SURFACES:
        raise ValueError(
            f"surface must be one of {sorted(_SWING_SURFACES)}, got {surface!r}"
        )
    # Belt A first: install (idempotently) BEFORE any handler emits.
    if install_record_factory is not None:
        install_record_factory()
    logs_dir.mkdir(parents=True, exist_ok=True)
    # Absolutize to match FileHandler.baseFilename (which stores os.path.abspath),
    # so a relative logs_dir still dedups correctly (R2-major-4) rather than
    # close-and-recreating an "already attached" handler.
    target = os.path.abspath(Path(logs_dir) / f"{surface}.log")
    root = logging.getLogger()
    # Level is owned by the ROOT logger; set on EVERY path (incl. dedup).
    root.setLevel(level)
    if logger_levels:
        for name, lvl in logger_levels.items():
            logging.getLogger(name).setLevel(lvl)
    # Swing-managed handlers are TAGGED with `_swing_surface` so we find ours
    # without ever touching a foreign library's handler.
    swing_handlers = [
        h for h in root.handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) is not None
    ]
    for h in swing_handlers:
        if h.baseFilename == target:
            # Same surface+file: idempotent dedup-refresh (R1-minor-1). Refresh
            # formatter / filter only; NEVER mutate maxBytes / backupCount.
            if formatter is not None:
                h.setFormatter(formatter)
            if record_filter is not None:
                _replace_swing_filter(h, record_filter)
            return
    # A genuinely new surface (or a new logs_dir for the same surface): enforce
    # ONE swing handler per process (§3.4). Remove AND close every prior swing
    # handler -- removeHandler alone leaves the file descriptor open, which on
    # Windows blocks rotation/rename + the cleanup (R2-major-4). Foreign handlers
    # are never removed/closed.
    for h in swing_handlers:
        root.removeHandler(h)
        h.close()
    handler = RotatingFileHandler(
        filename=target,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,  # open on first emit -> smaller Windows rename-on-rollover window
    )
    handler._swing_surface = surface  # type: ignore[attr-defined]  # tag (§3.4)
    handler.setLevel(logging.NOTSET)  # R4-major-1: thresholding lives on root, not here
    # Formatter BEFORE addHandler -> no unredacted window.
    handler.setFormatter(
        formatter if formatter is not None else logging.Formatter(DEFAULT_LOG_FORMAT)
    )
    if record_filter is not None:
        _replace_swing_filter(handler, record_filter)
    root.addHandler(handler)
```

- [ ] **Step 5: Run the retention-cap test + the full logging-config file**

Run: `python -m pytest tests/test_logging_config.py tests/integrations/test_pipeline_log_redaction.py -q`
Expected: PASS (the existing redaction tests still pass — Belt B is still attached via the same `formatter=` path; the CLI test still wires it through `pipeline_run_cmd`, unchanged until Task 4).

- [ ] **Step 6: Add the remaining seam unit tests**

Add to `tests/test_logging_config.py`:

```python
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
```

- [ ] **Step 7: Run the full seam test file + redaction file**

Run: `python -m pytest tests/test_logging_config.py tests/integrations/test_pipeline_log_redaction.py tests/web/test_error_handling.py -q`
Expected: PASS (all green).

- [ ] **Step 8: ruff + commit**

Run: `ruff check swing/logging_config.py tests/test_logging_config.py`
```bash
git add swing/logging_config.py tests/test_logging_config.py tests/integrations/test_pipeline_log_redaction.py tests/web/test_error_handling.py
git commit -m "feat(logging): switch the seam to size-based RotatingFileHandler with additive injection"
```

---

## Task 2: `[logging]` config section + `LoggingConfig` cascade

**Files:**
- Modify: `swing/config.py`, `swing/config_overrides.py`, `swing.config.toml`
- Test: `tests/config/test_logging_config_section.py` (create)

Depends on nothing in Task 1; placed before Task 3 because `install_logging` reads `cfg.logging`.

- [ ] **Step 1: Write the failing config tests**

Create `tests/config/test_logging_config_section.py`:

```python
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
```

- [ ] **Step 2: Run — verify it fails**

Run: `python -m pytest tests/config/test_logging_config_section.py -v`
Expected: FAIL (`ImportError: cannot import name 'LoggingConfig'`).

- [ ] **Step 3: Add `LoggingConfig` + parser to `swing/config.py`**

At the top of `swing/config.py`, add `import logging` to the existing imports. Add (near the other sub-dataclasses, e.g. just before `class Config`):

```python
_LEVEL_NAMES = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


@dataclass(frozen=True)
class LoggingConfig:
    """Slice-1 logging knobs (spec §4.5). ``warnings`` carries parse-time
    diagnostics that install_logging replays AFTER the redacted handler attaches
    (the chicken-and-egg fix, R1-major-4) -- they are NEVER logged at parse time."""
    level: int = logging.INFO
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5
    warnings: tuple[str, ...] = ()


def _parse_logging_config(raw: object) -> LoggingConfig:
    """Parse a ``[logging]`` table; malformed values (incl. a non-table ``raw``)
    degrade to defaults + collect a diagnostic (never crash). ``raw`` is typed
    ``object`` because a malformed TOML section may not be a dict at all."""
    if not isinstance(raw, dict):
        # A non-table [logging] value (e.g. `logging = "INFO"`) must not crash load().
        return LoggingConfig(
            warnings=(
                f"[logging] section must be a table; got "
                f"{type(raw).__name__!r}; using all defaults",
            ),
        )
    warnings: list[str] = []

    level = logging.INFO
    raw_level = raw.get("level", "INFO")
    if isinstance(raw_level, str) and raw_level.upper() in _LEVEL_NAMES:
        level = _LEVEL_NAMES[raw_level.upper()]
    else:
        warnings.append(f"[logging] level {raw_level!r} invalid; using INFO")

    max_bytes = 10 * 1024 * 1024
    raw_mb = raw.get("max_bytes", max_bytes)
    if isinstance(raw_mb, int) and not isinstance(raw_mb, bool) and raw_mb > 0:
        max_bytes = raw_mb
    else:
        warnings.append(f"[logging] max_bytes {raw_mb!r} invalid; using {max_bytes}")

    backup_count = 5
    raw_bc = raw.get("backup_count", backup_count)
    # Require >= 1: with backupCount=0 RotatingFileHandler keeps NO rotated
    # backups and provides no (backup_count+1)*max_bytes retention set, defeating
    # the retention narrative -> treat <1 as invalid and degrade to the default.
    if isinstance(raw_bc, int) and not isinstance(raw_bc, bool) and raw_bc >= 1:
        backup_count = raw_bc
    else:
        warnings.append(
            f"[logging] backup_count {raw_bc!r} invalid; using {backup_count}"
        )

    return LoggingConfig(
        level=level, max_bytes=max_bytes, backup_count=backup_count,
        warnings=tuple(warnings),
    )
```

Add the field to `Config` (after `integrations`):
```python
    logging: LoggingConfig = field(default_factory=LoggingConfig)
```

In `load()`, in the `return Config(...)` call, add:
```python
        logging=_parse_logging_config(raw.get("logging", {})),
```

- [ ] **Step 4: Run the config tests**

Run: `python -m pytest tests/config/test_logging_config_section.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing user-config cascade test**

Append to `tests/config/test_logging_config_section.py`:

```python
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
```

- [ ] **Step 6: Run — verify it fails**

Run: `python -m pytest tests/config/test_logging_config_section.py::test_user_config_overlay_overrides_level -v`
Expected: FAIL (`eff.logging.level` still INFO — no overlay yet).

- [ ] **Step 7: Add the `[logging]` overlay to `apply_overrides`**

In `swing/config_overrides.py`, extend the existing `from swing.config import Config` line to:
```python
from swing.config import Config, _parse_logging_config
```
(Do NOT import `LoggingConfig` here — it is unused in this module and ruff would flag it.) Inside `apply_overrides`, after `overrides = load_user_overrides()` and before the final `return replace(...)`, add:

```python
    new_logging = base_cfg.logging
    raw_logging = _get(overrides, "logging")
    if isinstance(raw_logging, dict):
        # Re-validate via the same parser over a merged dict so malformed
        # overrides degrade identically (level name round-trips via getLevelName).
        merged = {
            "level": logging.getLevelName(base_cfg.logging.level),
            "max_bytes": base_cfg.logging.max_bytes,
            "backup_count": base_cfg.logging.backup_count,
        }
        merged.update(raw_logging)
        parsed = _parse_logging_config(merged)
        # Preserve tracked-parse warnings + append overlay warnings.
        new_logging = replace(
            parsed, warnings=base_cfg.logging.warnings + parsed.warnings,
        )
    elif not isinstance(raw_logging, _Missing):
        # Present but NOT a table (e.g. user-config `logging = "INFO"`): keep the
        # base values + collect a warning (symmetry with load()'s non-dict guard;
        # malformed-degrades-never-crashes applies to user-config too).
        new_logging = replace(
            base_cfg.logging,
            warnings=base_cfg.logging.warnings
            + (
                f"[logging] user-config section must be a table; got "
                f"{type(raw_logging).__name__!r}; ignored",
            ),
        )
```
Add `import logging` at the top of `config_overrides.py`. Add `logging=new_logging` to the final `return replace(base_cfg, ...)` call.

**Sentinel note (executing-ready):** `_Missing` and `_MISSING` already exist in `config_overrides.py` — `class _Missing:` plus `_MISSING = _Missing()`, and `_get(overrides, path)` returns the `_MISSING` instance when the path is absent. The `elif not isinstance(raw_logging, _Missing):` branch matches the module's existing idiom (e.g. the existing `if not isinstance(cf, _Missing):` checks). It is an instance check against the sentinel CLASS — do NOT change it to `is not _MISSING` or add a new import; both symbols are already in scope in this module.

- [ ] **Step 8: Run config tests + commit**

Run: `python -m pytest tests/config/test_logging_config_section.py -q`
Expected: PASS.

Add the committed defaults to `swing.config.toml` (anywhere top-level, e.g. after `[paths]`):
```toml
[logging]
level = "INFO"
max_bytes = 10485760   # 10 MB
backup_count = 5
# [logging.loggers]   # per-logger overrides -- Slice 2 (built empty by default)
```

Run: `ruff check swing/config.py swing/config_overrides.py`
```bash
git add swing/config.py swing/config_overrides.py swing.config.toml tests/config/test_logging_config_section.py
git commit -m "feat(config): add the [logging] section and LoggingConfig cascade"
```

---

## Task 3: The `install_logging` composition root + diagnostics replay

**Files:**
- Create: `swing/logging_setup.py`
- Test: `tests/test_logging_setup.py` (create)

Depends on Task 1 (seam) + Task 2 (`LoggingConfig`).

- [ ] **Step 1: Write the failing composition-root tests**

Create `tests/test_logging_setup.py`:

```python
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
```

- [ ] **Step 2: Run — verify it fails**

Run: `python -m pytest tests/test_logging_setup.py -v`
Expected: FAIL (`ModuleNotFoundError: swing.logging_setup`).

- [ ] **Step 3: Create `swing/logging_setup.py`**

```python
"""Composition root for swing logging.

Unlike the swing.logging_config SEAM (Schwab-agnostic by construction), THIS
module is Schwab-AWARE: it wires the redaction belts (Belt A factory + Belt B
RedactingFormatter) by construction, so every surface routed through
``install_logging`` is redacted -- adding a surface cannot omit redaction. The
schwab import lives ONLY here, preserving seam purity.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from swing.config import Config
from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging


def install_logging(cfg: Config, *, surface: str) -> None:
    from swing.integrations.schwab.client import (
        RedactingFormatter,
        ensure_schwab_log_redaction_factory_installed,
    )

    log_cfg = cfg.logging
    configure_logging(
        cfg.paths.logs_dir,
        surface=surface,
        level=log_cfg.level,
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT),     # Belt B, every surface
        max_bytes=log_cfg.max_bytes,
        backup_count=log_cfg.backup_count,
        install_record_factory=ensure_schwab_log_redaction_factory_installed,  # Belt A
    )
    # Slice 2 will add logger_levels=log_cfg.resolved_logger_levels() and
    # record_filter=_correlation_filter(surface) here; the seam already accepts both.
    _replay_logging_diagnostics(cfg, surface=surface)


def _replay_logging_diagnostics(cfg: Config, *, surface: str) -> None:
    """Replay COLLECTED config-parse diagnostics AFTER the redacted handler is
    attached (R1-major-4). Delivery bypasses the root level + any per-logger
    override by calling ``handler.handle`` DIRECTLY on the swing surface handler
    (the handler level is NOTSET, R4-major-1 / R2-major-2). The record still passes
    through Belt B (RedactingFormatter) on that handler, so diagnostics are redacted.
    """
    warnings = getattr(cfg.logging, "warnings", ())
    if not warnings:
        return
    target = os.path.abspath(cfg.paths.logs_dir / f"{surface}.log")  # match baseFilename
    handler = next(
        (
            h for h in logging.getLogger().handlers
            if isinstance(h, RotatingFileHandler) and h.baseFilename == target
        ),
        None,
    )
    if handler is None:
        return
    for msg in warnings:
        record = logging.LogRecord(
            name="swing.logging_config", level=logging.WARNING,
            pathname=__file__, lineno=0, msg="%s", args=(msg,), exc_info=None,
        )
        handler.handle(record)
```

- [ ] **Step 4: Run the composition-root tests**

Run: `python -m pytest tests/test_logging_setup.py -v`
Expected: PASS.

- [ ] **Step 5: ruff + commit**

Run: `ruff check swing/logging_setup.py tests/test_logging_setup.py`
```bash
git add swing/logging_setup.py tests/test_logging_setup.py
git commit -m "feat(logging): add the install_logging composition root with diagnostics replay"
```

---

## Task 4: Migrate the call sites + prove web.log redaction by construction

**Files:**
- Modify: `swing/web/middleware/request_id.py`, `swing/web/app.py`, `swing/cli.py`
- Test: `tests/web/test_error_handling.py` (extend), `tests/integrations/test_pipeline_log_redaction.py` (extend — the web-surface redaction audit + the CLI test already covers the pipeline path)

The web-redaction audit is the FAILING test that DRIVES this migration: against the current plain (no-formatter) `configure_web_logging` shim it fails (the secret survives in web.log), and the shim rewrite is what makes it pass. This keeps the strict TDD rhythm (failing test → impl → pass) — the redaction proof is not a vacuous after-the-fact assertion.

- [ ] **Step 1a: Write the failing web-surface redaction audit (the driving test)**

Add to `tests/integrations/test_pipeline_log_redaction.py`:

```python
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
```

- [ ] **Step 1b: Write the failing shim + app tests**

Add to `tests/web/test_error_handling.py`:

```python
def test_configure_web_logging_no_cfg_attaches_redacting_handler(tmp_path):
    # Back-compat shim (Arc-1 lock): legacy logs_dir-only callers still work AND
    # now get redaction (strictly additive). Discriminator: pre-Slice-1 the shim
    # attached a plain default formatter -> this isinstance check would FAIL.
    import logging
    import os
    from logging.handlers import RotatingFileHandler
    import swing.integrations.schwab.client as schwab_client
    from swing.integrations.schwab.client import RedactingFormatter
    from swing.web.middleware.request_id import configure_web_logging

    root = logging.getLogger()
    saved = list(root.handlers)
    # configure_web_logging now ALSO sets root level + installs the global Schwab
    # LogRecord factory + may register secrets -> snapshot/restore ALL of them so a
    # large suite is not contaminated (matches the pipeline_logging fixture).
    saved_level = root.level
    saved_factory = logging.getLogRecordFactory()
    saved_secrets = set(schwab_client._GLOBAL_KNOWN_SECRETS)
    for h in list(root.handlers):
        root.removeHandler(h)
    try:
        configure_web_logging(tmp_path)
        target = os.path.abspath(tmp_path / "web.log")
        handlers = [
            h for h in root.handlers
            if isinstance(h, RotatingFileHandler) and h.baseFilename == target
        ]
        assert len(handlers) == 1
        assert isinstance(handlers[0].formatter, RedactingFormatter)
        # Idempotent.
        configure_web_logging(tmp_path)
        assert len([
            h for h in root.handlers
            if isinstance(h, RotatingFileHandler) and h.baseFilename == target
        ]) == 1
    finally:
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


def test_configure_web_logging_with_cfg_delegates_to_install_logging(tmp_path, monkeypatch):
    import swing.web.middleware.request_id as rid
    captured = {}
    monkeypatch.setattr(
        rid, "install_logging",
        lambda cfg, *, surface: captured.update(surface=surface, cfg=cfg),
    )
    sentinel_cfg = object()
    rid.configure_web_logging(tmp_path, cfg=sentinel_cfg)
    assert captured == {"surface": "web", "cfg": sentinel_cfg}
```

- [ ] **Step 2: Run — verify they fail**

Run: `python -m pytest tests/integrations/test_pipeline_log_redaction.py -k web tests/web/test_error_handling.py::test_configure_web_logging_no_cfg_attaches_redacting_handler tests/web/test_error_handling.py::test_configure_web_logging_with_cfg_delegates_to_install_logging -v`
Expected: FAIL — the web-redaction audit fails because the current shim attaches a plain (no-formatter) handler so `SENTINEL` survives in web.log; the delegate test fails because `install_logging` is not yet a `request_id` attribute.

- [ ] **Step 3: Rewrite the shim (`swing/web/middleware/request_id.py`)**

Replace `configure_web_logging` with:

First add a **module-level** import near the top of `request_id.py`, alongside the existing `from swing.logging_config import configure_logging`:
```python
from swing.logging_setup import install_logging
```
This makes `request_id.install_logging` a module attribute the delegate test can monkeypatch. No import cycle: `request_id` ← `logging_setup` ← (`swing.config`, `swing.logging_config`); none of those import `request_id`, and `logging_setup`'s schwab import is lazy (inside the function). Keep `configure_logging` imported too (the legacy branch uses it).

Then replace `configure_web_logging` with — note the body references the **module-level** `install_logging` (NOT a local re-import, so the monkeypatch in `test_configure_web_logging_with_cfg_delegates_to_install_logging` takes effect):
```python
def configure_web_logging(logs_dir: Path, cfg=None) -> None:
    """Back-compat shim over the redacted/bounded web logging path (Arc-1 lock:
    RETAINED, not removed). With ``cfg`` it forwards to the composition root;
    without it (legacy logs_dir-only callers) it constructs a minimal default
    LoggingConfig and routes through the SAME redaction + rotation wiring.
    Either way web.log behavior is preserved AND redaction is now added
    (strictly additive)."""
    if cfg is not None:
        install_logging(cfg, surface="web")   # module-level symbol -> monkeypatchable
        return
    # Legacy path: default knobs + the same belts.
    from swing.config import LoggingConfig
    from swing.integrations.schwab.client import (
        RedactingFormatter,
        ensure_schwab_log_redaction_factory_installed,
    )

    default = LoggingConfig()
    configure_logging(
        logs_dir,
        surface="web",
        level=default.level,
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT),
        max_bytes=default.max_bytes,
        backup_count=default.backup_count,
        install_record_factory=ensure_schwab_log_redaction_factory_installed,
    )
```
This also requires `DEFAULT_LOG_FORMAT` in scope: extend the existing seam import to `from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging`.

- [ ] **Step 4: Migrate `app.py:441`**

In `swing/web/app.py`, replace the import of `configure_web_logging` (line 30) usage: keep the import (other code/tests may reference it) but change the call site at line 441:
```python
    from swing.logging_setup import install_logging
    install_logging(cfg, surface="web")
```
(Place the `install_logging` import at the top of `app.py` with the other imports rather than inline if the file's style prefers top-level imports; match surrounding convention.)

- [ ] **Step 5: Migrate `pipeline_run_cmd` (`swing/cli.py`)**

Replace the hand-wired Belt-A + Belt-B block (the `ensure_schwab_log_redaction_factory_installed()` + `configure_logging(... surface="pipeline" ...)` lines) with:
```python
    from swing.logging_setup import install_logging
    install_logging(cfg, surface="pipeline")
```
Keep the surrounding comment updated to: `# Pipeline observability (Arc-1/Arc-2): route through the install_logging composition root (Belt A + Belt B + bounded rotation by construction).`

- [ ] **Step 6: Run the migration + redaction + pipeline-path tests**

Run: `python -m pytest tests/web/test_error_handling.py tests/integrations/test_pipeline_log_redaction.py tests/web/test_app_smoke.py -q`
Expected: PASS — the web-redaction audit now passes (shim wires Belt B); `test_pipeline_run_cmd_writes_pipeline_log` proves the CLI still wires Belt B via `install_logging` (`SENTINEL not in text`); its handler-class lookup was already flipped to `RotatingFileHandler` in Task 1.

- [ ] **Step 7: ruff + commit**

Run: `ruff check swing/web/middleware/request_id.py swing/web/app.py swing/cli.py`
```bash
git add swing/web/middleware/request_id.py swing/web/app.py swing/cli.py tests/web/test_error_handling.py tests/integrations/test_pipeline_log_redaction.py
git commit -m "refactor(logging): route web and pipeline through install_logging with web.log redaction"
```

---

## Task 5: Stop the suite leaking into the operator's real swing-data logs (D1)

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_logging_leak_guard.py` (create)

- [ ] **Step 1: Write the failing guard test**

Create `tests/test_logging_leak_guard.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

# Captured at MODULE IMPORT, before any monkeypatch fixture applies -> the REAL
# operator home. (conftest fixtures are function-scoped and apply per-test.)
_REAL_HOME = Path(
    os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
)


def test_suite_does_not_resolve_logs_to_real_home():
    from swing.config import _user_home, _resolve_path

    # The autouse redirect fixture must be active: _user_home() is NOT the real
    # operator home. Discriminator: WITHOUT the fixture, _user_home() == _REAL_HOME
    # and this assertion FAILS.
    redirected = _user_home()
    assert redirected != _REAL_HOME

    # And a relative logs_dir resolves UNDER the redirected (tmp) home, never the
    # real ~/swing-data/logs.
    resolved = _resolve_path("swing-data/logs", redirected, Path("/proj"))
    real_logs = _REAL_HOME / "swing-data" / "logs"
    assert resolved != real_logs
    assert str(real_logs) not in str(resolved)


def test_create_app_writes_weblog_under_tmp_not_real_home(tmp_path, monkeypatch):
    # A cfg with a RELATIVE logs_dir (the leak shape) + create_app must write
    # web.log under the redirected home, never the operator's real logs dir.
    import logging
    from logging.handlers import RotatingFileHandler
    import swing.integrations.schwab.client as schwab_client
    from swing.config import _user_home
    from swing.web.app import create_app

    # Build a sample_config-style cfg with a relative logs_dir.
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_RELATIVE_LOGS_TOML, encoding="utf-8")
    from swing.config import load
    cfg = load(cfg_path)

    root = logging.getLogger()
    saved = list(root.handlers)
    # create_app routes through install_logging (sets root level + installs the
    # Schwab LogRecord factory) -> snapshot/restore ALL global logging state.
    saved_level = root.level
    saved_factory = logging.getLogRecordFactory()
    saved_secrets = set(schwab_client._GLOBAL_KNOWN_SECRETS)
    for h in list(root.handlers):
        root.removeHandler(h)
    try:
        create_app(cfg, cfg_path)
        real_weblog = _REAL_HOME / "swing-data" / "logs" / "web.log"
        # The handler target must be under the redirected home, not the real one.
        targets = [
            h.baseFilename for h in root.handlers if isinstance(h, RotatingFileHandler)
        ]
        assert targets, "create_app attached no web.log handler"
        for t in targets:
            assert str(real_weblog) != t
            assert str(_user_home()) in t
    finally:
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


_RELATIVE_LOGS_TOML = '''[paths]
db_path = "swing-data/swing.db"
data_dir = "swing-data"
logs_dir = "swing-data/logs"
charts_dir = "swing-data/charts"
backups_dir = "swing-data/backups"
prices_cache_dir = "swing-data/prices-cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8_rs_rank"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
'''
```

- [ ] **Step 2: Run — verify it fails**

Run: `python -m pytest tests/test_logging_leak_guard.py -v`
Expected: FAIL (`_user_home()` returns the real home — the autouse redirect doesn't exist yet).

- [ ] **Step 3: Add the autouse home-redirect fixture to `tests/conftest.py`**

Add near the top of `tests/conftest.py` (after the existing imports — add `import os` if absent):

```python
@pytest.fixture(scope="session")
def _suite_home(tmp_path_factory):
    """One stable temp home per pytest session (so relative-path resolution is
    consistent across tests within a session)."""
    return tmp_path_factory.mktemp("suite_home")


@pytest.fixture(autouse=True)
def _redirect_home_away_from_real_swing_data(_suite_home, monkeypatch):
    """Stop the suite leaking into the operator's REAL ~/swing-data/logs.

    The leak (spec §2.1 / OQ-7): swing.config.load() resolves the relative
    ``logs_dir = "swing-data/logs"`` against ``_user_home()`` (the real
    $USERPROFILE), and create_app() attaches a ROOT-logger web.log handler there
    at construction time -- so a single leaking test poisons the whole process
    (33.6 K httpx lines + synthetic tracebacks land in the real web.log).

    Fix (D1): redirect ``swing.config._user_home`` AND $USERPROFILE/$HOME to a
    session-stable temp home for every test. Tests passing ABSOLUTE tmp logs_dir
    (the _minimal_config family) are unaffected (absolute short-circuits
    _resolve_path); the redaction/rotation tests pass explicit absolute tmp paths
    too, so the production wiring stays exercised (not masked).
    """
    import swing.config as config_mod

    monkeypatch.setenv("USERPROFILE", str(_suite_home))
    monkeypatch.setenv("HOME", str(_suite_home))
    monkeypatch.setattr(config_mod, "_user_home", lambda: _suite_home)
    yield
```

- [ ] **Step 4: Run the guard test**

Run: `python -m pytest tests/test_logging_leak_guard.py -v`
Expected: PASS.

- [ ] **Step 5: Run a broad slice to catch blast radius**

Run: `python -m pytest tests/config tests/web tests/cli -q`
Expected: PASS. The redirect shifts only swing's relative-path resolution to the temp home; investigate any test that asserted against the real home (none expected — `_minimal_config` uses absolute paths). If a test legitimately needs the real home, it can set its own `USERPROFILE`/`HOME` (which overrides the autouse fixture for that test) — note any such adjustment in the commit body.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_logging_leak_guard.py
git commit -m "test(logging): stop the suite leaking into the operator real swing-data logs"
```

---

## Task 6: The operator-gated content-preserving `swing logs cleanup` command (D2)

**Files:**
- Create: `swing/logs_maintenance.py` (pure: no click, no DB)
- Modify: `swing/cli.py` (the `logs` group + `cleanup` command + DB refusal)
- Test: `tests/test_logs_maintenance.py` (create), `tests/cli/test_logs_cleanup_cmd.py` (create)

### Part A — the pure filesystem module

- [ ] **Step A1: Write the failing pure-module tests**

Create `tests/test_logs_maintenance.py`:

```python
from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from swing.logs_maintenance import (
    LogsCleanupLockHeld,
    acquire_single_instance_lock,
    compress_log_file,
    reserve_archive_name,
    select_legacy_dated_logs,
    select_oversized_current_logs,
)


def _touch(p: Path, data: bytes = b"x"):
    p.write_bytes(data)


def test_select_legacy_dated_logs_only_dated(tmp_path):
    _touch(tmp_path / "web.log")                  # active managed -> excluded
    _touch(tmp_path / "web.log.1")                # numeric rotation set -> excluded
    _touch(tmp_path / "web.log.2026-05-06")       # legacy dated -> SELECTED
    _touch(tmp_path / "web.log.2026-05-23")       # legacy dated -> SELECTED
    _touch(tmp_path / "web.log.2026-05-06.gz")    # already gz -> excluded
    _touch(tmp_path / "pipeline.log")             # active managed -> excluded
    _touch(tmp_path / "uvicorn.log.2026-05-06")   # NON-swing surface -> excluded
    _touch(tmp_path / "pipeline.log.2026-04-01")  # legacy dated (pipeline) -> SELECTED
    selected = {p.name for p in select_legacy_dated_logs(tmp_path)}
    assert selected == {
        "web.log.2026-05-06", "web.log.2026-05-23", "pipeline.log.2026-04-01",
    }


def test_compress_log_file_content_preserving(tmp_path):
    src = tmp_path / "web.log.2026-05-06"
    payload = ("line with token deadbeef\n" * 5000).encode("utf-8")
    _touch(src, payload)
    archive = compress_log_file(src, tmp_path)
    assert archive.name == "web.log.2026-05-06.gz"
    assert not src.exists()                                   # original removed AFTER verify
    assert gzip.decompress(archive.read_bytes()) == payload   # byte-for-byte preserved


def test_compress_verify_failure_keeps_original(tmp_path, monkeypatch):
    src = tmp_path / "web.log.2026-05-06"
    _touch(src, b"important content")
    # Make the decompressed-gz hash DIFFER from the original hash. NOTE: monkeypatching
    # the shared `_sha256_stream` would make BOTH sides equal (both "MISMATCH") and
    # verification would falsely PASS -- so corrupt the gz-read side only.
    import swing.logs_maintenance as lm
    monkeypatch.setattr(
        lm, "_gz_decompressed_chunks", lambda path: iter([b"CORRUPTED-DIFFERENT-BYTES"])
    )
    with pytest.raises(RuntimeError):
        compress_log_file(src, tmp_path)
    assert src.exists()                                   # original untouched
    assert src.read_bytes() == b"important content"
    assert not list(tmp_path.glob("*.gz"))                # no archive, no temp left


def test_reserve_archive_name_collision_free(tmp_path):
    _touch(tmp_path / "web.log.2026-05-06.gz")
    reserved = reserve_archive_name(tmp_path, "web.log.2026-05-06")
    assert reserved.name == "web.log.2026-05-06.1.gz"


def test_select_oversized_current_logs(tmp_path):
    _touch(tmp_path / "web.log", b"y" * 2048)              # current -> SELECTED (oversized)
    _touch(tmp_path / "web.log.1", b"y" * 2048)            # numeric rotation -> SELECTED
    _touch(tmp_path / "pipeline.log", b"y" * 10)           # under threshold -> excluded
    _touch(tmp_path / "web.log.123-not-rotation", b"y" * 2048)  # junk suffix -> EXCLUDED
    _touch(tmp_path / "uvicorn.log", b"y" * 2048)          # non-swing -> EXCLUDED
    big = {p.name for p in select_oversized_current_logs(tmp_path, size_threshold=1024)}
    assert big == {"web.log", "web.log.1"}


def test_single_instance_lock(tmp_path):
    lock = acquire_single_instance_lock(tmp_path)
    with pytest.raises(LogsCleanupLockHeld):
        acquire_single_instance_lock(tmp_path)
    lock.release()
    acquire_single_instance_lock(tmp_path).release()   # released -> reacquirable
```

- [ ] **Step A2: Run — verify it fails**

Run: `python -m pytest tests/test_logs_maintenance.py -v`
Expected: FAIL (`ModuleNotFoundError: swing.logs_maintenance`).

- [ ] **Step A3: Create `swing/logs_maintenance.py`**

```python
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


class LogsCleanupLockHeld(RuntimeError):
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
        with open(tmp, "rb") as tf:
            os.fsync(tf.fileno())
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
            try:
                self._path.unlink()
            except OSError:
                pass


def acquire_single_instance_lock(logs_dir: Path) -> _SingleInstanceLock:
    """Single-instance lock file in logs_dir (defense-in-depth so two cleanups
    never run concurrently). Raises LogsCleanupLockHeld if held."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    lock_path = logs_dir / ".logs-cleanup.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise LogsCleanupLockHeld(
            "another logs cleanup is in progress (lock held)"
        ) from exc
    return _SingleInstanceLock(lock_path, fd)
```

- [ ] **Step A4: Run + commit Part A**

Run: `python -m pytest tests/test_logs_maintenance.py -q && ruff check swing/logs_maintenance.py`
Expected: PASS.
```bash
git add swing/logs_maintenance.py tests/test_logs_maintenance.py
git commit -m "feat(logging): add the pure logs-maintenance compression module"
```

### Part B — the CLI command

- [ ] **Step B1: Write the failing CLI tests**

Create `tests/cli/test_logs_cleanup_cmd.py`:

```python
from __future__ import annotations

import gzip
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

import swing.cli as cli
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    from swing.data.db import ensure_schema
    cfg = load(cfg_path)
    cfg.paths.logs_dir.mkdir(parents=True, exist_ok=True)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def test_cleanup_compresses_dated_with_yes(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    dated = cfg.paths.logs_dir / "web.log.2026-05-06"
    dated.write_bytes(b"old log line\n" * 1000)
    (cfg.paths.logs_dir / "web.log").write_bytes(b"active\n")  # must NOT be touched
    res = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "logs", "cleanup", "--yes"]
    )
    assert res.exit_code == 0, res.output
    assert not dated.exists()
    archive = cfg.paths.logs_dir / "web.log.2026-05-06.gz"
    assert archive.exists()
    assert gzip.decompress(archive.read_bytes()) == b"old log line\n" * 1000
    assert (cfg.paths.logs_dir / "web.log").read_bytes() == b"active\n"  # untouched


def test_cleanup_refuses_when_pipeline_running(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    (cfg.paths.logs_dir / "web.log.2026-05-06").write_bytes(b"x")
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) VALUES "
            "('2026-06-09T00:00:00','manual','2026-06-08','2026-06-09','running','t')"
        )
    conn.close()
    res = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "logs", "cleanup", "--yes"]
    )
    assert res.exit_code != 0
    assert "pipeline" in res.output.lower()


def test_cleanup_fail_closed_on_db_unavailable(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    cfg.paths.db_path.unlink()  # remove the DB -> query must fail-closed (refuse)
    (cfg.paths.logs_dir / "web.log.2026-05-06").write_bytes(b"x")
    res = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "logs", "cleanup", "--yes"]
    )
    # ensure_schema would recreate on connect; to truly simulate unavailability,
    # point db at a directory path instead (see impl note). Assert refusal.
    assert res.exit_code != 0


def test_include_current_requires_web_stopped(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    res = CliRunner().invoke(
        cli.main,
        ["--config", str(cfg_path), "logs", "cleanup", "--yes", "--include-current"],
    )
    assert res.exit_code != 0
    assert "web-stopped" in res.output.lower() or "web server" in res.output.lower()


def test_include_current_compresses_oversized_current(tmp_path):
    # Proves the click wiring actually calls select_oversized_current_logs (not just
    # the dated-default scope). Oversized current web.log (> the 10 MB default
    # threshold) + the full app-stopped scope -> archived.
    cfg, cfg_path = _setup(tmp_path)
    payload = b"y" * (11 * 1024 * 1024)   # exceed the 10 MB oversize threshold
    (cfg.paths.logs_dir / "web.log").write_bytes(payload)
    res = CliRunner().invoke(
        cli.main,
        ["--config", str(cfg_path), "logs", "cleanup",
         "--yes", "--include-current", "--web-stopped"],
    )
    assert res.exit_code == 0, res.output
    assert not (cfg.paths.logs_dir / "web.log").exists()
    archive = cfg.paths.logs_dir / "web.log.gz"
    assert archive.exists()
    assert gzip.decompress(archive.read_bytes()) == payload


def test_cleanup_idempotent_no_candidates(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    res = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "logs", "cleanup", "--yes"]
    )
    assert res.exit_code == 0
    assert "no legacy" in res.output.lower()


@pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None,
    reason="cp1252 stdout footgun is Windows/PowerShell-specific",
)
def test_cleanup_stdout_is_ascii_through_powershell(tmp_path):
    # cp1252 footgun: the command's stdout must be ASCII so PowerShell's default
    # cp1252 encoder never raises UnicodeEncodeError in production.
    cfg, cfg_path = _setup(tmp_path)
    (cfg.paths.logs_dir / "web.log.2026-05-06").write_bytes(b"x" * 100)
    completed = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f'& "{sys.executable}" -m swing.cli --config "{cfg_path}" logs cleanup --yes',
        ],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    completed.stdout.encode("ascii")  # raises if any non-ASCII glyph slipped in
```

Note for the executing agent on `test_cleanup_fail_closed_on_db_unavailable`: `swing.data.db.connect`/`ensure_schema` may recreate a missing DB. To make the fail-closed path deterministic, the impl's DB check (Step B2) opens **read-only without creating** and the test points `db_path` at an un-openable target (e.g. create a directory at the db_path). Adjust the test to `cfg.paths.db_path.mkdir()` (a directory where a file is expected) if `unlink()` alone gets silently recreated — confirm which during execution and pick the variant that genuinely exercises the refuse-on-error branch.

- [ ] **Step B2: Run — verify it fails**

Run: `python -m pytest tests/cli/test_logs_cleanup_cmd.py -v`
Expected: FAIL (`No such command 'logs'`).

- [ ] **Step B3: Add the `logs` group + `cleanup` command to `swing/cli.py`**

Add (near the other `@main.group(...)` definitions):

```python
@main.group("logs")
def logs_group() -> None:
    """Operator log maintenance (one-time, gated)."""


def _refuse_if_pipeline_running(cfg) -> None:
    """Refuse while a pipeline run is active; FAIL-CLOSED if the DB cannot be
    opened/queried (R4-minor-1). Mirrors the existing CLI concurrency-exclusion
    discipline (SchwabPipelineActiveError / FinvizPipelineActiveError family)."""
    import sqlite3
    db_path = cfg.paths.db_path
    if not db_path.exists() or db_path.is_dir():
        raise click.ClickException(
            f"Cannot open the DB at {db_path} to check pipeline state; refusing."
        )
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT 1 FROM pipeline_runs WHERE state = 'running' LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise click.ClickException(
            f"Cannot query pipeline state ({exc}); refusing."
        ) from exc
    if row:
        raise click.ClickException(
            "A pipeline run is active (state='running'); refusing. "
            "Try again after it finishes."
        )


@logs_group.command("cleanup")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt (scripted use).")
@click.option(
    "--include-current", is_flag=True,
    help="Also reclaim oversized CURRENT/rotated managed files (app-stopped scope).",
)
@click.option(
    "--web-stopped", is_flag=True,
    help="Attest the web server is stopped (REQUIRED with --include-current).",
)
@click.pass_context
def logs_cleanup_cmd(ctx, yes, include_current, web_stopped) -> None:
    """Compress legacy dated log files content-preservingly (one-time, gated).

    Default scope: legacy dated artifacts ({surface}.log.<DATE>) only. With
    --include-current (+ --web-stopped) it also reclaims oversized current/rotated
    managed files. Verified gzip; verify-before-unlink; never auto-runs.
    """
    from swing.logs_maintenance import (
        LogsCleanupLockHeld,
        acquire_single_instance_lock,
        compress_log_file,
        select_legacy_dated_logs,
        select_oversized_current_logs,
    )

    cfg = ctx.obj["config"]
    logs_dir = cfg.paths.logs_dir
    if not logs_dir.exists():
        click.echo("No logs directory; nothing to do.")
        return

    _refuse_if_pipeline_running(cfg)

    try:
        lock = acquire_single_instance_lock(logs_dir)
    except LogsCleanupLockHeld as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        candidates = select_legacy_dated_logs(logs_dir)
        if include_current:
            if not web_stopped:
                raise click.ClickException(
                    "--include-current requires --web-stopped "
                    "(attest the web server is stopped)."
                )
            candidates = candidates + select_oversized_current_logs(logs_dir)

        if not candidates:
            click.echo("No legacy log files to compress.")
            return

        total = sum(p.stat().st_size for p in candidates)
        click.echo("Files to compress (content-preserving gzip):")
        for p in candidates:
            click.echo(f"  {p.name} ({p.stat().st_size} bytes)")
        click.echo(f"Total to reclaim: {total} bytes")

        if not yes:
            click.confirm("Proceed?", abort=True)

        for p in candidates:
            target = compress_log_file(p, logs_dir)
            click.echo(f"Compressed {p.name} -> {target.name}")
        click.echo("Done.")
    finally:
        lock.release()
```

Confirm `click` is already imported at the top of `cli.py` (it is — the file is click-based). Use only ASCII in every echoed string (`->`, not an arrow glyph).

- [ ] **Step B4: Run the CLI tests**

Run: `python -m pytest tests/cli/test_logs_cleanup_cmd.py -v`
Expected: PASS. (If `test_cleanup_fail_closed_on_db_unavailable` is flaky because the DB is recreated, switch it to the directory-at-db_path variant per the Step B1 note.)

- [ ] **Step B5: ruff + commit Part B**

Run: `ruff check swing/cli.py tests/cli/test_logs_cleanup_cmd.py`
```bash
git add swing/cli.py tests/cli/test_logs_cleanup_cmd.py
git commit -m "feat(cli): add the operator-gated content-preserving logs cleanup command"
```

---

## Task 7: Full fast suite + ruff green

**Files:** none (verification task).

- [ ] **Step 1: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: PASS. Baseline ~7408 fast tests + the new tests added by this slice.

Known non-this-arc noise to recognize (do NOT "fix" them as part of this arc): the pre-existing `tests/research/.../test_study_doc.py` em-dash failure (Phase-16 line-3 note) and the 3 xdist-order-fragile research L2 tests (`pattern_cohort`/`double_bottom_w`/`w_bottom`). If any of the three appear, re-run that file with `-n0` to confirm it is the known ordering flake, not a regression from this slice.

- [ ] **Step 2: ruff the whole package**

Run: `ruff check swing/`
Expected: clean.

- [ ] **Step 3: Verify the Arc-1 locks did not regress**

Confirm by grep + targeted tests:
```bash
# Seam stays Schwab-agnostic -- grep IMPORTS ONLY (the docstring legitimately
# contains the phrase "Schwab-agnostic", so a bare `grep schwab` would false-match):
grep -nE "^[[:space:]]*(from|import)[[:space:]]+.*schwab" swing/logging_config.py \
  && echo "FAIL: seam imports schwab" || echo "OK: seam has no schwab import"
# install_logging is the ONLY logging-path schwab importer:
grep -rn "from swing.integrations.schwab" swing/logging_setup.py
# pipeline.log + two-belt redaction + pipeline_step_timings still pass:
python -m pytest tests/integrations/test_pipeline_log_redaction.py tests/test_logging_config.py -q
```
Expected: seam has no schwab import; `logging_setup` imports the belts; redaction + seam tests green.

- [ ] **Step 4: Final commit (if any incidental fixes were needed)**

```bash
git add -A
git commit -m "test(logging): full fast suite and ruff green for the Slice-1 logging overhaul"
```
(If Steps 1-3 required no edits, skip this commit.)

---

## Spec coverage map (§6 tests → tasks)

| Spec §6 "thing to nail" | Task / test |
|---|---|
| Redaction by construction on web.log (no unredacted window) | Task 4 (`test_web_handler_carries_redacting_formatter_at_attach`, `test_web_non_schwabdev_logger_line_is_redacted`) + Task 1 (`test_formatter_is_set_before_add_to_root`); pipeline retained (Task 1/4) |
| Retention actually bounds the dir (discriminating cap) | Task 1 (`test_retention_caps_managed_file_set`) |
| Seam idempotent + web.log behavior preserved; handler-class assertions flipped in the same task | Task 1 (all seam tests; `TimedRotatingFileHandler`→`RotatingFileHandler` flips) |
| Deferred config diagnostics (junk level → INFO + warning lands; level=ERROR bypass) | Task 2 (`test_malformed_level_degrades_to_info_without_crash`) + Task 3 (`test_diagnostics_replayed_after_handler_attaches`, `test_diagnostics_bypass_high_root_level`) |
| Level knob honored on the ROOT logger (handler stays NOTSET) | Task 1 (`test_handler_level_is_notset`) + Task 3 (`test_install_logging_sets_root_level_from_config`) |
| Test-leak guard (no test writes the real `~/swing-data/logs`) | Task 5 (`tests/test_logging_leak_guard.py`) |
| Windows/encoding (utf-8 handlers; ASCII cleanup stdout; PowerShell subprocess) | Task 1 (`test_pipeline_handler_is_utf8` retained) + Task 6 (`test_cleanup_stdout_is_ascii_through_powershell`) |
| Discriminating-test discipline | Task 1 cap test, Task 2 malformed-level, Task 3 ERROR-bypass, Task 4 web redaction, Task 6 verify-before-unlink — each computes the asserted value under both pre/post paths |
| Single surface per process (§3.4 enforcement) | Task 1 (`test_single_surface_per_process`, `test_foreign_handler_is_not_removed`). The CLI per-command surface ROUTING (pipeline vs cli) defers to Slice 2 |
| Correlation id round-trips (§5.2) | **Slice 2** — Out of Scope |

---

## Locks / invariants preserved (spec §8 — do not regress)

- **Schema NONE (v25).** Zero migrations in this plan. DB read is read-only (`mode=ro`).
- **Arc-1 not regressed:** `swing/logging_config.py` stays Schwab-agnostic (Belt A injected via `install_record_factory`, never imported into the seam — verified Task 7 Step 3); `swing/logging_setup.py` is the only logging-path schwab importer; `configure_web_logging` RETAINED (external signature `configure_web_logging(logs_dir)` preserved, gains optional `cfg=None`); `pipeline.log` + the two-belt pipeline redaction + `pipeline_step_timings` all stay working. The `TimedRotatingFileHandler`→`RotatingFileHandler` test-assertion flips land in the SAME task as the switch (Task 1).
- **Redaction strictly ADDITIVE:** web.log goes unredacted→redacted; pipeline.log unchanged; the sentinel-leak audit is EXTENDED (web added), never narrowed; formatter set before `addHandler` (no unredacted window).
- **Cleanup is OPERATOR-GATED + content-preserving:** explicit confirm (or `--yes`), verify-`.gz`-before-unlink (streamed SHA-256 byte-equality), never auto-runs, never wired into startup, `os.replace` temp in `logs_dir`, ASCII-only output, writes nothing outside `logs_dir`, refuses while pipeline running (fail-closed), single-instance lock, collision-free O_EXCL archive names.
- **Phase isolation:** change loci exactly as the File Map. **`swing/trades/` + `swing/data/` are read-only** — the cleanup's pipeline-running check opens the DB **read-only** and modifies nothing under `swing/data/`.

---

## Out of scope (Slice 2 / banked — carry forward, do NOT build here)

- **Slice 2 (§5):** `cli.log` centralization (2a); run/request correlation (2d — env-var transport, `CorrelationFilter`, `swing/log_correlation.py`, the `Popen env` touch, `set_pipeline_run_id` at lease); the per-logger override table (`[logging.loggers]`, `resolved_logger_levels()`).
- **§3.4 CLI per-command surface ROUTING** (the `cli.py` entrypoint choosing `pipeline` vs `cli` surface per dispatched command) — deferred to Slice 2, where `cli.log` first exists. NOTE: the §3.4 **single-handler enforcement** (tag `_swing_surface`; remove-and-close a prior different-surface swing handler) IS built in Slice 1 (Task 1) per the locked spec — only the surface-selection routing waits for the `cli.log` surface.
- **Callout B (operator-deferred):** shipping `httpx=WARNING`/`yfinance=WARNING` as committed `[logging.loggers]` defaults — the lever (override table) is Slice 2; the policy is the operator's. Slice 1's test-leak fix already removes the dominant volume.
- **NOT** Arc 3 (XMAX thumbnail), **NOT** Arc 4 (equity reconciliation), **NOT** the perf follow-on. **NO schema.**
