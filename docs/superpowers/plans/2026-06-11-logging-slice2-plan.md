# Phase 16 / Arc 2 / Slice 2 — CLI surface + run/request correlation + per-logger overrides — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Arc-2 logging system by routing `swing` CLI runs through a bounded/redacted `cli.log`, threading a web→pipeline run/request correlation id through every log record, and exposing the `[logging.loggers]` per-logger override table — all on the already-landed Slice-1 seam + composition root, with **no schema change** (v28 holds).

**Architecture:** A new neutral `swing/log_correlation.py` owns two **thread-safe process-global** ids (NOT contextvars — the pipeline subprocess emits from worker threads that would never inherit a `ContextVar`), guarded by a `threading.Lock`, with `get_/set_` accessors, strict env-token validation, reset-at-install, and a per-record `CorrelationFilter`. `install_logging` (the §3.2 composition root) resets correlation from `SWING_WEB_REQUEST_ID`, attaches the filter, applies `logger_levels`, and constructs the Belt-B `RedactingFormatter` with the new always-present correlation fields (`defaults=`). The web `Popen` passes the request id in the child env; the pipeline runner calls `set_pipeline_run_id(lease.run_id)` once the lease row is inserted. The CLI group callback installs `cli.log` for every command **except the `pipeline` subgroup** (whose `run` subcommand installs `pipeline.log` in `pipeline_run_cmd`) — so a pipeline-surface process never touches `cli.log`, unconditionally.

**Tech Stack:** Python 3.14, stdlib `logging` (`RotatingFileHandler`, `logging.Filter`, `Formatter(defaults=)`), `threading.Lock`, click CLI, FastAPI/Starlette web, pytest + `click.testing.CliRunner` + real `subprocess` for the end-to-end transport proof.

---

## Grounding (verified on HEAD `6f9db3c9`, the merged Arc-8 head — re-anchor before editing)

Slice 1 (merged `d809ace8`) + Arcs 6/7/8 left these landing pads. **Re-verify every line anchor at your HEAD before editing — earlier arcs shifted runner.py.**

- **Seam** `swing/logging_config.py` — `configure_logging` (lines 41-127) already accepts `record_filter` + `logger_levels` + `max_bytes`/`backup_count`; tags swing handlers `_swing_surface`; enforces §3.4 single-surface (removes **and** `close()`s a prior swing handler when a new surface installs); `_replace_swing_filter` (lines 24-38) installs the swing filter as a single tagged replace-not-append. `DEFAULT_LOG_FORMAT` is at line 17. The no-formatter fallback `logging.Formatter(DEFAULT_LOG_FORMAT)` is at line 122.
- **Composition root** `swing/logging_setup.py` — `install_logging(cfg, *, surface)` (lines 19-37) wires Belt A (factory) + Belt B (`RedactingFormatter(DEFAULT_LOG_FORMAT)`) + rotation; lines 35-36 are the **explicit Slice-2 TODO comment** (`logger_levels=...` + `record_filter=_correlation_filter(surface)`). `_replay_logging_diagnostics` (lines 40-78) replays parse warnings via `handler.handle` directly (bypasses thresholds), idempotent + swing-tagged-handler-only.
- **`LoggingConfig`** `swing/config.py:431-485` — frozen dataclass `level`/`max_bytes`/`backup_count`/`warnings`; `_parse_logging_config(raw)` collects diagnostics into `warnings` (never logs at parse time). Call site: `config.py:634` `logging=_parse_logging_config(raw.get("logging", {}))` — so `raw.get("loggers")` reaches the parser (the nested `[logging.loggers]` subtable). `_LEVEL_NAMES` (config.py:422-428) maps level-name → int.
- **`RedactingFormatter`** `swing/integrations/schwab/client.py:153-166` — overrides only `format()`; **defines no `__init__`**, so it inherits `logging.Formatter.__init__(fmt, datefmt, style, validate, *, defaults=None)`. `RedactingFormatter(fmt, defaults=...)` works with no client.py change.
- **Popen site** `swing/web/routes/pipeline.py:120-132` — `subprocess.Popen([... "pipeline", "run", "--manual"], close_fds=True, stdout=DEVNULL, stderr=DEVNULL, start_new_session=True)` with **no `env=`**. The route is `pipeline_run(request: Request)` (line 49); `request.state.request_id` is stamped by `RequestIdMiddleware` (`swing/web/middleware/request_id.py:18-31`).
- **Lease site** `swing/pipeline/runner.py` — `run_pipeline_internal` (line 534); `lease = acquire_lease(...)` (line 564); `ConcurrentRunBlockedError` except returns at line 575; `Heartbeat(...)` at line 577. `lease.run_id` is an `int`.
- **CLI group callback** `swing/cli.py:178-188` — `@click.group()` `main(ctx, config_path)`; loads `cfg = load_config(...)` at line 185; runs the divergence hook (which uses `click.echo(..., err=True)` — stderr, not logging) for non-skip subcommands. `pipeline_run_cmd` (lines 3306-3328) already calls `install_logging(cfg, surface="pipeline")` at line 3320.
- **finviz security belt** `swing/integrations/finviz_api.py:46-59` `_suppress_transport_debug_logs` — **STAYS as-is** (auth-token-in-URL belt; spec §5.1).
- **Test isolation already present** `tests/conftest.py:28-49` — autouse `_redirect_home_away_from_real_swing_data` monkeypatches `USERPROFILE`/`HOME`/`swing.config._user_home` to a session temp home for **every** test. This means a CLI group-callback `cli.log` install resolves `logs_dir` under tmp, **not** the real `~/swing-data/logs` — the Slice-1 leak fix protects Slice 2 by construction. `_minimal_config` (tests/cli/test_cli_eval.py:33) writes an **absolute** tmp `logs_dir`.
- **Blast radius:** ~373 `invoke(main)` calls across 56 test files. The group-callback `cli.log` install runs on **all** of them, mutating root handlers + the Belt-A factory + root level. Task 7 adds an autouse logging-state isolation fixture to contain this (the existing manual snapshot/restore pattern, applied suite-wide).
- Suite baseline: **7777** fast tests green on `main`.

### Locks / invariants (do not regress)
- Slice-1/Arc-1 non-regression: `pipeline.log` + both belts + redaction-by-construction; `cli.log` gets **≥** the same coverage. The seam stays Schwab-agnostic (`logging_setup` remains the sole schwab importer; `log_correlation.py` imports nothing from schwab). `configure_web_logging` retained. Rotation/retention params unchanged.
- The `Popen` touch is **env-ONLY** (`env={**os.environ, "SWING_WEB_REQUEST_ID": request_id}`; `DEVNULL` + `start_new_session=True` + `close_fds=True` stay).
- `set_pipeline_run_id` lives in `swing/pipeline/` (allowed area). `swing/trades/` + `swing/data/` **untouched**. **NO schema (v28).** `[logging.loggers]` ships **empty** (Callout B). Zero `Co-Authored-By`.

### Correlation design (LOCKED — Codex-converged in the spec; do NOT re-litigate)
Env-var transport (`SWING_WEB_REQUEST_ID`); STRICT token validation `^[A-Za-z0-9-]{1,64}$` → fallback `-`; thread-safe **process-global** carrier guarded by `threading.Lock` (NOT contextvars); reset-at-install; per-record `CorrelationFilter`; `Formatter(defaults=)` always-present fields.

> **Spec-faithful simplification (flag at review):** the spec §3.2 sketch shows `record_filter=_correlation_filter(surface)`. The `CorrelationFilter` reads both process-globals at `filter()` time and is **surface-independent** (reset-at-install seeds `web_request_id` from env in every process; the web process simply has no env → `-`). This plan therefore constructs `CorrelationFilter()` directly (no `surface` arg) — a deliberate YAGNI drop of an unused parameter, behavior identical to the spec. The locked contract ("a per-record CorrelationFilter") is honored.

---

## File Structure

**Create:**
- `swing/log_correlation.py` — correlation carrier: lock-guarded globals, `get_/set_` accessors, strict env validation, `reset_correlation_from_env`, `set_pipeline_run_id`, `CorrelationFilter`.
- `tests/test_log_correlation.py` — pure-unit tests for the carrier (validation, reset, worker-thread stamping).
- `tests/test_logging_correlation_e2e.py` — real-subprocess env-transport tests (+ the small driver script via `python -c`).
- `tests/test_cli_log_surface.py` — `cli.log` group install, §3.4 routing, sentinel-leak audit, leak guard extension.
- `tests/test_logging_loggers_override.py` — `[logging.loggers]` parse + `resolved_logger_levels()` + diagnostics replay.

**Modify:**
- `swing/logging_config.py` — change `DEFAULT_LOG_FORMAT` to carry correlation fields; add `CORRELATION_LOG_DEFAULTS`; pass `defaults=` to the no-formatter fallback formatter.
- `swing/web/middleware/request_id.py` — the legacy `configure_web_logging(cfg=None)` shim's `RedactingFormatter` also gets `defaults=CORRELATION_LOG_DEFAULTS` (Task 2; the third formatter site).
- `swing/logging_setup.py` — reset correlation from env, attach `CorrelationFilter()`, pass `logger_levels=log_cfg.resolved_logger_levels()`, construct `RedactingFormatter(..., defaults=CORRELATION_LOG_DEFAULTS)`.
- `swing/config.py` — `LoggingConfig` gains a resolved `logger_levels` field + `resolved_logger_levels()`; `_parse_logging_config` parses `[logging.loggers]` (malformed → skip + diagnostic into `warnings`).
- `swing/web/routes/pipeline.py` — add `env=` to `Popen`; log `request_id` at spawn.
- `swing/pipeline/runner.py` — import + call `set_pipeline_run_id(lease.run_id)` after lease acquisition.
- `swing/cli.py` — group callback installs `cli.log` (surface="cli") after config load.
- `tests/conftest.py` — autouse root-logging-state isolation fixture (blast-radius containment).
- `tests/test_logging_leak_guard.py` — extend with a `cli.log` group-install guard.

---

## Task 1: Correlation carrier module (`swing/log_correlation.py`)

**Files:**
- Create: `swing/log_correlation.py`
- Test: `tests/test_log_correlation.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_log_correlation.py
from __future__ import annotations

import logging
import threading

import pytest

import swing.log_correlation as lc


@pytest.fixture(autouse=True)
def _reset_correlation_state():
    # Each test starts from a clean carrier; restore env-independence afterward.
    lc._set_for_test(web_request_id="-", pipeline_run_id=None)
    yield
    lc._set_for_test(web_request_id="-", pipeline_run_id=None)


def test_valid_env_token_accepted(monkeypatch):
    monkeypatch.setenv("SWING_WEB_REQUEST_ID", "abc-123-DEF")
    lc.reset_correlation_from_env()
    assert lc.get_web_request_id() == "abc-123-DEF"
    # reset always clears the run id (no run yet) -> renders the placeholder.
    assert lc.get_pipeline_run_id() == "-"


def test_missing_env_falls_back_to_placeholder(monkeypatch):
    monkeypatch.delenv("SWING_WEB_REQUEST_ID", raising=False)
    lc.reset_correlation_from_env()
    assert lc.get_web_request_id() == "-"


@pytest.mark.parametrize("forged", [
    "has space", "new\nline", "tab\tchar", "x" * 65, "", "semi;colon", "slash/y",
])
def test_forged_env_token_rejected(monkeypatch, forged):
    monkeypatch.setenv("SWING_WEB_REQUEST_ID", forged)
    lc.reset_correlation_from_env()
    assert lc.get_web_request_id() == "-"


def test_set_pipeline_run_id_stringifies():
    lc.set_pipeline_run_id(42)
    assert lc.get_pipeline_run_id() == "42"
    lc.set_pipeline_run_id(None)
    assert lc.get_pipeline_run_id() == "-"


def test_reset_clears_stale_run_id(monkeypatch):
    # A stale run id from a prior in-process run MUST NOT bleed past a reset.
    lc.set_pipeline_run_id(99)
    assert lc.get_pipeline_run_id() == "99"
    monkeypatch.delenv("SWING_WEB_REQUEST_ID", raising=False)
    lc.reset_correlation_from_env()
    assert lc.get_pipeline_run_id() == "-"


def test_filter_stamps_both_ids():
    lc._set_for_test(web_request_id="rid-7", pipeline_run_id="55")
    f = lc.CorrelationFilter()
    rec = logging.LogRecord("n", logging.INFO, __file__, 1, "m", None, None)
    assert f.filter(rec) is True
    assert rec.web_request_id == "rid-7"
    assert rec.pipeline_run_id == "55"


def test_filter_stamps_in_worker_thread():
    # The discriminating test a contextvars impl FAILS: a worker thread that did
    # not inherit a ContextVar set on the main thread would render "-"; the
    # process-global carrier is visible from every thread.
    lc._set_for_test(web_request_id="rid-thread", pipeline_run_id="77")
    f = lc.CorrelationFilter()
    captured = {}

    def worker():
        rec = logging.LogRecord("n", logging.INFO, __file__, 1, "m", None, None)
        f.filter(rec)
        captured["web"] = rec.web_request_id
        captured["run"] = rec.pipeline_run_id

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert captured == {"web": "rid-thread", "run": "77"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_log_correlation.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'swing.log_correlation'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swing/log_correlation.py
"""Process-global run/request correlation ids for log records (Arc-2 Slice-2).

NEUTRAL by construction: imports nothing from swing.integrations.schwab and
nothing from swing.config -- so the composition root (swing/logging_setup.py)
can import it without re-introducing a cycle, and the seam stays untouched.

WHY process-globals, not contextvars (spec R2-major-3): the ids are
process/run-scoped, not task-local. The pipeline subprocess emits records from
worker threads (the price-fetch executor, threaded steps) that would NOT inherit
a ``ContextVar`` set on the main thread -- a contextvar would silently drop the
id on those records. A lock-guarded module global is single-writer (env at
install; lease once) / many-reader and correct across all threads.
"""
from __future__ import annotations

import logging
import os
import re
import threading

ENV_VAR = "SWING_WEB_REQUEST_ID"
PLACEHOLDER = "-"
# Strict token shape: the uuid4 the web emits is [0-9a-f-]; we allow the broader
# alnum+hyphen set, length 1..64. Anything with whitespace/newlines/punctuation
# or over-length is REJECTED to a placeholder (defends against an inherited or
# forged env var injecting newlines / misleading content into log lines).
_VALID_TOKEN = re.compile(r"^[A-Za-z0-9-]{1,64}$")

_lock = threading.Lock()
_web_request_id: str = PLACEHOLDER          # validated env value or "-"
_pipeline_run_id: str | None = None         # None until the lease is held


def _validate_token(raw: str | None) -> str:
    if raw is not None and _VALID_TOKEN.match(raw):
        return raw
    return PLACEHOLDER


def reset_correlation_from_env() -> None:
    """Reset BOTH globals at install (spec R3-minor-3): pipeline_run_id -> None
    (no run yet), web_request_id -> validated SWING_WEB_REQUEST_ID or "-". Called
    at the START of install_logging, before seeding, so a stale pipeline_run_id
    from an earlier run in the same process cannot bleed into later records."""
    global _web_request_id, _pipeline_run_id
    with _lock:
        _web_request_id = _validate_token(os.environ.get(ENV_VAR))
        _pipeline_run_id = None


def set_pipeline_run_id(run_id: int | str | None) -> None:
    """Set the run id after the pipeline lease row is inserted. None -> placeholder."""
    global _pipeline_run_id
    with _lock:
        _pipeline_run_id = None if run_id is None else str(run_id)


def get_web_request_id() -> str:
    with _lock:
        return _web_request_id


def get_pipeline_run_id() -> str:
    with _lock:
        return _pipeline_run_id if _pipeline_run_id is not None else PLACEHOLDER


def _set_for_test(*, web_request_id: str, pipeline_run_id: str | None) -> None:
    """Test-only direct seam (no env round-trip). Not used in production paths."""
    global _web_request_id, _pipeline_run_id
    with _lock:
        _web_request_id = web_request_id
        _pipeline_run_id = pipeline_run_id


class CorrelationFilter(logging.Filter):
    """Stamps record.web_request_id / record.pipeline_run_id from the process
    globals at filter() time (per record, any thread). Always returns True.

    Reading at filter() time -- not at construction -- means a value set AFTER
    the handler is installed (e.g. set_pipeline_run_id at lease acquisition) is
    picked up on the next record from any thread."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.web_request_id = get_web_request_id()
        record.pipeline_run_id = get_pipeline_run_id()
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_log_correlation.py -q`
Expected: PASS (all parametrized cases + worker-thread).

- [ ] **Step 5: ruff**

Run: `ruff check swing/log_correlation.py tests/test_log_correlation.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add swing/log_correlation.py tests/test_log_correlation.py
git commit -m "feat(logging): process-global run/request correlation carrier"
```

---

## Task 2: Always-present correlation fields on the shared format (`defaults=`)

The correlation fields join the single shared format string; **EVERY `(Redacting)Formatter(DEFAULT_LOG_FORMAT)` construction site** must supply `defaults=` so a record that never passed through `CorrelationFilter` renders `-`/`-` instead of raising `KeyError` (which `logging` would swallow via `handleError`, silently dropping the line — a masked breakage). A repo-wide grep (`grep -rn "Formatter(DEFAULT_LOG_FORMAT" swing tests`) enumerates **exactly four** sites — fix all four in this slice (sites 1, 3, 4 in THIS task; site 2 in Task 3):
1. `swing/logging_config.py:122` — the no-formatter fallback (this task).
2. `swing/logging_setup.py:30` — the Belt-B `RedactingFormatter` in `install_logging` (Task 3).
3. `swing/web/middleware/request_id.py:56` — the legacy `configure_web_logging(cfg=None)` shim (this task; Codex R3-major-1). The no-cfg shim is called directly by `tests/web/test_error_handling.py` + the `web_logging` fixture.
4. `tests/integrations/test_pipeline_log_redaction.py:38` — the **`pipeline_logging` test fixture** (this task; Codex R4-major-1). Task 2 Step 4 runs this file, and `test_long_line_is_redacted_without_truncation` asserts a tail marker IS present — it would FAIL on a KeyError-drop. Substring "secret not in text" asserts would *mask* the drop, but the tail-marker test won't.

> **Discriminating-test note** ([[feedback_regression_test_arithmetic]]): a substring `assert SENTINEL not in text` is satisfied by a dropped (empty) line — it does NOT distinguish "redacted" from "never written". The tail-marker test (asserting a positive marker IS present) is the one that genuinely catches the KeyError-drop; that is why fixing site 4 is load-bearing for executability, not cosmetic.

**Files:**
- Modify: `swing/logging_config.py:17` (the `DEFAULT_LOG_FORMAT` constant) + `:122` (the no-formatter fallback)
- Modify: `swing/web/middleware/request_id.py:56` (the legacy `configure_web_logging(cfg=None)` shim's `RedactingFormatter`)
- Modify: `tests/integrations/test_pipeline_log_redaction.py:9-15,38` (the `pipeline_logging` fixture's `RedactingFormatter` + import)
- Test: `tests/test_logging_config.py` + `tests/integrations/test_pipeline_log_redaction.py` (add cases; existing `_fmt == DEFAULT_LOG_FORMAT` at line 78 stays green — it compares against the constant)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_logging_config.py`:

```python
def test_default_format_carries_correlation_fields():
    from swing.logging_config import DEFAULT_LOG_FORMAT
    assert "%(web_request_id)s" in DEFAULT_LOG_FORMAT
    assert "%(pipeline_run_id)s" in DEFAULT_LOG_FORMAT


def test_no_formatter_fallback_renders_placeholders_no_keyerror(clean_root, tmp_path):
    # A record with NO correlation context, formatted by the no-formatter fallback,
    # must render "-"/"-" via defaults= -- NOT raise/swallow a KeyError. Discriminator:
    # without defaults= on the fallback Formatter, super().format() raises KeyError on
    # %(web_request_id)s, logging calls handleError, and the line is DROPPED -> the
    # file would not contain the message and this assertion FAILS.
    import logging
    configure_logging(tmp_path, surface="pipeline")  # no formatter supplied -> fallback
    h = _file_handlers(clean_root, tmp_path / "pipeline.log")[0]
    rendered = h.formatter.format(
        logging.LogRecord("n", logging.INFO, __file__, 1, "hello-msg", None, None)
    )
    assert "hello-msg" in rendered
    assert "-" in rendered  # the placeholder fields rendered, no KeyError
```

Append to `tests/integrations/test_pipeline_log_redaction.py` (exercises the no-cfg shim — site 3):

```python
def test_web_logging_shim_renders_correlation_placeholders(web_logging):
    # R3-major-1: the legacy configure_web_logging(cfg=None) shim must construct its
    # RedactingFormatter with defaults= so a no-context record renders req=-/run=-
    # instead of KeyError-dropping (the substring redaction tests would MASK that).
    import logging
    logging.getLogger("swing.web.access").info("shim line present")
    text = _read(web_logging)
    assert "shim line present" in text
    assert "req=- run=-" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest "tests/test_logging_config.py::test_default_format_carries_correlation_fields" "tests/test_logging_config.py::test_no_formatter_fallback_renders_placeholders_no_keyerror" "tests/integrations/test_pipeline_log_redaction.py::test_web_logging_shim_renders_correlation_placeholders" -q`
Expected: FAIL — the format lacks the fields; the fallback + the shim raise/swallow `KeyError` (no `req=- run=-` rendered).

- [ ] **Step 3: Implement the format change**

In `swing/logging_config.py`, replace line 17 and add the defaults constant:

```python
# Correlation fields (Arc-2 Slice-2) are made ALWAYS-PRESENT via Formatter
# defaults= so a record that never passed through CorrelationFilter renders the
# placeholder instead of KeyError. CorrelationFilter overrides these when context
# is present. EVERY formatter construction site that uses DEFAULT_LOG_FORMAT MUST
# pass defaults=CORRELATION_LOG_DEFAULTS (see the 4-site enumeration in this task).
CORRELATION_LOG_DEFAULTS = {"web_request_id": "-", "pipeline_run_id": "-"}
DEFAULT_LOG_FORMAT = (
    "%(asctime)s [%(levelname)s] %(name)s "
    "[req=%(web_request_id)s run=%(pipeline_run_id)s]: %(message)s"
)
```

Change the no-formatter fallback (currently line ~122) from:

```python
    handler.setFormatter(
        formatter if formatter is not None else logging.Formatter(DEFAULT_LOG_FORMAT)
    )
```

to:

```python
    handler.setFormatter(
        formatter if formatter is not None
        else logging.Formatter(DEFAULT_LOG_FORMAT, defaults=CORRELATION_LOG_DEFAULTS)
    )
```

Then fix site (3) — the legacy `configure_web_logging(cfg=None)` shim in `swing/web/middleware/request_id.py`. Update its import and the `RedactingFormatter` construction:

```python
# in the imports near the top:
from swing.logging_config import (
    CORRELATION_LOG_DEFAULTS,
    DEFAULT_LOG_FORMAT,
    configure_logging,
)
```

and in the legacy (`cfg is None`) branch change:

```python
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT),
```

to:

```python
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT, defaults=CORRELATION_LOG_DEFAULTS),
```

(The `cfg is not None` branch delegates to `install_logging`, which already gets `defaults=` via Task 3 — no change there.)

Then fix site (4) — the `pipeline_logging` test fixture in `tests/integrations/test_pipeline_log_redaction.py`. Add `CORRELATION_LOG_DEFAULTS` to its import and pass `defaults=` to the fixture's `RedactingFormatter`. Change the import (line ~15):

```python
from swing.logging_config import CORRELATION_LOG_DEFAULTS, DEFAULT_LOG_FORMAT, configure_logging
```

and the fixture's formatter (line ~38):

```python
    configure_logging(
        tmp_path, surface="pipeline",
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT, defaults=CORRELATION_LOG_DEFAULTS),  # Belt B
    )
```

(The `web_logging` fixture in the same file routes through the no-cfg `configure_web_logging` shim — site 3 — so it is covered once site 3 is fixed; no separate change there.)

- [ ] **Step 4: Run to verify pass + the existing format/redaction tests stay green**

Run: `python -m pytest tests/test_logging_config.py tests/integrations/test_pipeline_log_redaction.py tests/web/test_error_handling.py -q`
Expected: PASS — incl. `test_supplied_formatter_installs_on_preexisting_handler` (line 78, `_fmt == DEFAULT_LOG_FORMAT`, robust against the constant change), `test_retention_caps_managed_file_set` (emits through the no-formatter fallback — would have KeyError-masked into empty files without `defaults=`), and the new shim render test.

- [ ] **Step 5: ruff**

Run: `ruff check swing/logging_config.py swing/web/middleware/request_id.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add swing/logging_config.py swing/web/middleware/request_id.py tests/test_logging_config.py tests/integrations/test_pipeline_log_redaction.py
git commit -m "feat(logging): always-present correlation fields on the shared format"
```

---

## Task 3: Wire correlation + overrides into `install_logging`

**Files:**
- Modify: `swing/logging_setup.py:19-37` (the body + imports)
- Test: `tests/test_logging_setup.py` (append)

> NOTE: this task references `cfg.logging.resolved_logger_levels()`. Task 8 adds it to `LoggingConfig`. The current `LoggingConfig` has no such method, so add a **minimal forward-stub** here to keep this task self-contained and green, then Task 8 fleshes out the parse + diagnostics. The stub: `resolved_logger_levels(self) -> dict[str, int]: return {}`. (Task 8 replaces the body; the signature is stable.)

- [ ] **Step 1: Add the forward-stub method to `LoggingConfig`**

In `swing/config.py`, inside `class LoggingConfig` (after `warnings`), add:

```python
    def resolved_logger_levels(self) -> dict[str, int]:
        """Per-logger override map (name -> level int). Task 8 wires the parse;
        the Slice-1 default is an empty map (no overrides)."""
        return {}
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_logging_setup.py`:

```python
def test_install_attaches_correlation_filter(clean_root_and_secrets, tmp_path, monkeypatch):
    import swing.log_correlation as lc
    from logging.handlers import RotatingFileHandler
    monkeypatch.setenv("SWING_WEB_REQUEST_ID", "rid-install")
    cfg = _cfg(tmp_path)
    install_logging(cfg, surface="pipeline")
    target = str(cfg.paths.logs_dir / "pipeline.log")
    handler = next(
        h for h in clean_root_and_secrets.handlers
        if isinstance(h, RotatingFileHandler) and h.baseFilename == target
    )
    swing_filters = [
        f for f in handler.filters if isinstance(f, lc.CorrelationFilter)
    ]
    assert len(swing_filters) == 1
    # reset-at-install seeded web_request_id from the env.
    assert lc.get_web_request_id() == "rid-install"
    assert lc.get_pipeline_run_id() == "-"


def test_install_resets_stale_run_id(clean_root_and_secrets, tmp_path, monkeypatch):
    import swing.log_correlation as lc
    monkeypatch.delenv("SWING_WEB_REQUEST_ID", raising=False)
    lc.set_pipeline_run_id(123)  # stale run id from a prior in-process run
    cfg = _cfg(tmp_path)
    install_logging(cfg, surface="pipeline")
    assert lc.get_pipeline_run_id() == "-"  # reset-at-install cleared it


def test_install_emits_correlated_record_to_file(clean_root_and_secrets, tmp_path, monkeypatch):
    import logging
    from logging.handlers import RotatingFileHandler
    monkeypatch.setenv("SWING_WEB_REQUEST_ID", "rid-emit")
    cfg = _cfg(tmp_path)
    install_logging(cfg, surface="pipeline")
    import swing.log_correlation as lc
    lc.set_pipeline_run_id(7)
    logging.getLogger("swing.pipeline.lease").info("a step happened")
    for h in clean_root_and_secrets.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    text = (cfg.paths.logs_dir / "pipeline.log").read_text(encoding="utf-8")
    assert "req=rid-emit" in text
    assert "run=7" in text
    assert "a step happened" in text
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_logging_setup.py -q`
Expected: FAIL — no `CorrelationFilter` attached; no reset; records lack `req=`/`run=`.

- [ ] **Step 4: Implement the wiring**

Replace the body of `swing/logging_setup.py` (`install_logging` + imports) so it reads:

```python
from swing.config import Config
from swing.log_correlation import CorrelationFilter, reset_correlation_from_env
from swing.logging_config import (
    CORRELATION_LOG_DEFAULTS,
    DEFAULT_LOG_FORMAT,
    configure_logging,
)


def install_logging(cfg: Config, *, surface: str) -> None:
    from swing.integrations.schwab.client import (
        RedactingFormatter,
        ensure_schwab_log_redaction_factory_installed,
    )

    # Reset BEFORE seeding (spec R3-minor-3): clears any stale pipeline_run_id and
    # re-reads + validates SWING_WEB_REQUEST_ID for this process.
    reset_correlation_from_env()
    log_cfg = cfg.logging
    configure_logging(
        cfg.paths.logs_dir,
        surface=surface,
        level=log_cfg.level,
        # Belt B carries the SAME defaults= so the correlation fields are always
        # present even on a record that bypasses the filter.
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT, defaults=CORRELATION_LOG_DEFAULTS),
        max_bytes=log_cfg.max_bytes,
        backup_count=log_cfg.backup_count,
        install_record_factory=ensure_schwab_log_redaction_factory_installed,  # Belt A
        logger_levels=log_cfg.resolved_logger_levels(),                        # 2f overrides
        record_filter=CorrelationFilter(),                                     # 2d correlation
    )
    _replay_logging_diagnostics(cfg, surface=surface)
```

(Keep `_replay_logging_diagnostics` unchanged. Remove the stale Slice-2 TODO comment lines 35-36.)

- [ ] **Step 5: Run to verify pass + Slice-1 install tests stay green**

Run: `python -m pytest tests/test_logging_setup.py tests/integrations/test_pipeline_log_redaction.py -q`
Expected: PASS — incl. the existing redaction-by-construction tests (`defaults=` does not weaken redaction; `RedactingFormatter.format` still scrubs the rendered line, and the placeholder `-` contains no sentinel).

- [ ] **Step 6: ruff + commit**

```bash
ruff check swing/logging_setup.py swing/config.py
git add swing/logging_setup.py swing/config.py tests/test_logging_setup.py
git commit -m "feat(logging): wire correlation filter + reset into install_logging"
```

---

## Task 4: Thread the request id into the pipeline subprocess (Popen env)

**Files:**
- Modify: `swing/web/routes/pipeline.py:120-132`
- Test: `tests/web/test_routes/test_pipeline_run_correlation_env.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_routes/test_pipeline_run_correlation_env.py
from __future__ import annotations

import subprocess
from datetime import datetime

from fastapi.testclient import TestClient

import swing.web.routes.pipeline as pipeline_route
from swing.data.db import connect
from swing.web.app import create_app


def test_route_popen_receives_request_id_env(seeded_db, monkeypatch):
    # ROUTE-LEVEL discriminator (R1-major-2): POST /pipeline/run and assert the
    # kwargs the route hands to subprocess.Popen carry env["SWING_WEB_REQUEST_ID"]
    # AND preserve DEVNULL/close_fds/start_new_session. Modeled on the existing
    # test_post_pipeline_run_spawns_subprocess. Discriminator: if the production
    # spawn omits env=_build_subprocess_env(request_id), "env" is absent and this
    # FAILS -- a helper-only test would not catch that.
    cfg, cfg_path = seeded_db
    captured = {}

    class FakeProc:
        pid = 4242
        def poll(self):
            return None  # still running -> route polls for the lease row

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        # Simulate the child acquiring the lease so the route returns 200.
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                conn.execute(
                    """INSERT INTO pipeline_runs
                       (started_ts, trigger, data_asof_date, action_session_date,
                        state, lease_token, lease_heartbeat_ts)
                       VALUES (?, 'manual', '2026-04-17', '2026-04-20',
                               'running', 'subprocess-tok', ?)""",
                    (datetime.now().isoformat(timespec="seconds"),
                     datetime.now().isoformat(timespec="seconds")),
                )
        finally:
            conn.close()
        return FakeProc()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    kw = captured["kwargs"]
    rid = kw["env"]["SWING_WEB_REQUEST_ID"]
    # STRONG discriminator (R2-major-2): the child env id must equal the ACTUAL web
    # request id for this request -- the web.log <-> pipeline.log join chain. The
    # RequestIdMiddleware echoes that id in the X-Request-ID response header, so
    # equality here proves the route passed the real per-request id (not a hardcoded
    # or stale token that would still match the regex shape).
    assert rid == r.headers["X-Request-ID"]
    import re
    assert re.match(r"^[A-Za-z0-9-]{1,64}$", rid)  # also conforms to the token shape
    # The spawn contract is otherwise preserved.
    assert kw["stdout"] is subprocess.DEVNULL
    assert kw["stderr"] is subprocess.DEVNULL
    assert kw["close_fds"] is True
    assert kw["start_new_session"] is True


def test_build_subprocess_env_is_copy(monkeypatch):
    # Unit: the helper returns a COPY (mutating it must not touch os.environ) and
    # stamps the request id.
    import os
    monkeypatch.setenv("SOME_EXISTING", "1")
    env = pipeline_route._build_subprocess_env("rid-x")
    assert env["SWING_WEB_REQUEST_ID"] == "rid-x"
    assert env["SOME_EXISTING"] == "1"
    env["SOME_EXISTING"] = "2"
    assert os.environ["SOME_EXISTING"] == "1"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/web/test_routes/test_pipeline_run_correlation_env.py -q`
Expected: FAIL — `_build_subprocess_env` does not exist; the route passes no `env=` so `captured["kwargs"]["env"]` raises `KeyError`.

- [ ] **Step 3: Implement**

In `swing/web/routes/pipeline.py`, add a module-level helper near the top (after `log = logging.getLogger(__name__)`):

```python
def _build_subprocess_env(request_id: str) -> dict[str, str]:
    """Child env for the pipeline subprocess: inherit the parent env + the one
    justified correlation touch (SWING_WEB_REQUEST_ID). A COPY -- never mutate
    os.environ. The child's install_logging validates the value and falls back
    to "-" if it is malformed (defence-in-depth at the read side)."""
    env = dict(os.environ)
    env["SWING_WEB_REQUEST_ID"] = request_id
    return env
```

Then change the spawn block (currently lines 121-132) from:

```python
    log.info("spawning pipeline subprocess: %s", cmd)
    proc = subprocess.Popen(
        cmd, close_fds=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log.info("pipeline subprocess started: pid=%d", proc.pid)
```

to:

```python
    request_id = getattr(request.state, "request_id", "-")
    # The ONE justified touch to the DEVNULL spawn (spec OQ-5): carry the web's
    # request id into the child env so pipeline.log records correlate back to
    # this web.log line. DEVNULL + start_new_session + close_fds are unchanged.
    log.info("spawning pipeline subprocess request_id=%s: %s", request_id, cmd)
    proc = subprocess.Popen(
        cmd, close_fds=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=_build_subprocess_env(request_id),
    )
    log.info("pipeline subprocess started: pid=%d request_id=%s", proc.pid, request_id)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/web/test_routes/test_pipeline_run_correlation_env.py -q`
Expected: PASS.

- [ ] **Step 5: ruff + commit**

```bash
ruff check swing/web/routes/pipeline.py
git add swing/web/routes/pipeline.py tests/web/test_routes/test_pipeline_run_correlation_env.py
git commit -m "feat(web): thread request id into pipeline subprocess env + spawn log line"
```

---

## Task 5: Set the run id at lease acquisition (`runner.py`)

**Files:**
- Modify: `swing/pipeline/runner.py` (import near the other `swing.pipeline` imports; call after the `acquire_lease` except block, currently line 575)
- Test: `tests/pipeline/test_runner_sets_correlation_run_id.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_runner_sets_correlation_run_id.py
from __future__ import annotations

import pytest

import swing.log_correlation as lc
import swing.pipeline.runner as runner
from swing.config import load
from tests.cli.test_cli_eval import _minimal_config


def _runner_cfg(tmp_path):
    # Build the cfg FIRST (real mkdir), BEFORE any monkeypatching -- so the cfg
    # construction is never affected by the stubs below (R1-major-3: do NOT patch
    # Path.mkdir, which would break this helper's own project/home mkdir).
    project = tmp_path / "p"; project.mkdir()
    home = tmp_path / "h"; home.mkdir()
    return load(_minimal_config(project, home))


def test_set_pipeline_run_id_called_after_lease(tmp_path, monkeypatch):
    # set_pipeline_run_id(lease.run_id) must run immediately after lease acquisition.
    # Stub acquire_lease -> a fake lease, spy on set_pipeline_run_id, and make the
    # NEXT call after it (Heartbeat(), constructed right after the set and OUTSIDE
    # the post-lease try) raise -- so run_pipeline_internal aborts with the run id
    # already stamped. No network/DB beyond the lease.
    cfg = _runner_cfg(tmp_path)
    seen = {}

    class _FakeLease:
        run_id = 909
        token = "tok"
        def release(self, **kw):  # noqa: ARG002
            pass

    monkeypatch.setattr(runner, "acquire_lease", lambda **kw: _FakeLease())

    real_set = lc.set_pipeline_run_id
    def spy(rid):
        seen["rid"] = rid
        return real_set(rid)
    monkeypatch.setattr(runner, "set_pipeline_run_id", spy)

    class _Stop(RuntimeError):
        pass
    def boom(**kw):  # noqa: ARG001
        raise _Stop("stop after set_pipeline_run_id")
    monkeypatch.setattr(runner, "Heartbeat", boom)

    with pytest.raises(_Stop):
        runner.run_pipeline_internal(cfg=cfg, trigger="manual")
    assert seen["rid"] == 909
    assert lc.get_pipeline_run_id() == "909"
```

> NOTE for the implementer: verify the exact symbols the test stubs (`runner.acquire_lease`, `runner.Heartbeat`, `runner.set_pipeline_run_id`) are module-level names in `runner.py` at your HEAD, and that `Heartbeat(...)` is constructed AFTER `set_pipeline_run_id` and OUTSIDE the post-lease `try` (verified at HEAD `6f9db3c9`: lease 564, set after 575, `Heartbeat(...)` 577, the `try` opens at 589). The behavioral contract — `set_pipeline_run_id(lease.run_id)` runs immediately after lease acquisition — is the lock; adjust the "next call raises" target if an arc reorders those lines.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/pipeline/test_runner_sets_correlation_run_id.py -q`
Expected: FAIL — `runner.set_pipeline_run_id` does not exist (AttributeError on the monkeypatch) / the run id is never stamped.

- [ ] **Step 3: Implement**

In `swing/pipeline/runner.py`, add to the imports (near the existing `from swing.pipeline...` / lease imports):

```python
from swing.log_correlation import set_pipeline_run_id
```

Then, immediately after the `acquire_lease` try/except (after the `ConcurrentRunBlockedError` block that returns at line 575, before `hb = Heartbeat(...)`), insert:

```python
    # Correlation (Arc-2 Slice-2): stamp the run id on every subsequent log record
    # in this process. CorrelationFilter reads it at filter() time from any thread
    # (incl. the price-fetch executor + threaded steps). The lease row is already
    # inserted at this point (acquire_lease returned).
    set_pipeline_run_id(lease.run_id)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/pipeline/test_runner_sets_correlation_run_id.py -q`
Expected: PASS.

- [ ] **Step 5: ruff + commit**

```bash
ruff check swing/pipeline/runner.py tests/pipeline/test_runner_sets_correlation_run_id.py
git add swing/pipeline/runner.py tests/pipeline/test_runner_sets_correlation_run_id.py
git commit -m "feat(pipeline): stamp correlation run id at lease acquisition"
```

---

## Task 6: End-to-end subprocess correlation transport

Proves the real cross-process chain hermetically (no real pipeline run): a child process started with `SWING_WEB_REQUEST_ID=<sentinel>` produces `pipeline.log` records carrying the sentinel; after `set_pipeline_run_id` the records carry the run id; a worker-thread record carries both; a forged env value falls back to `-`; a no-context child renders `-`/`-` with no crash.

**Files:**
- Test: `tests/test_logging_correlation_e2e.py` (create)

> This task is a **regression-proof test addition, not a TDD red step**: the production behavior it asserts was already built in Tasks 1-5, so it is expected to PASS on first run. It is its own task because it is the binding spec §5.2/§6 cross-process transport proof and must exist as a committed guard.

- [ ] **Step 1: Add the regression-proof test (expected to PASS after Tasks 1-5)**

```python
# tests/test_logging_correlation_e2e.py
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

# A driver run in a CHILD process. It installs the pipeline surface, emits records
# from the main thread + a worker thread, sets the run id, and exits. The parent
# reads the resulting pipeline.log. Kept tiny + hermetic (no real pipeline run).
_DRIVER = textwrap.dedent(
    """
    import logging, sys, threading
    from dataclasses import replace
    from swing.config import load
    from swing.logging_setup import install_logging
    import swing.log_correlation as lc

    cfg = load(sys.argv[1])
    install_logging(cfg, surface="pipeline")
    log = logging.getLogger("swing.pipeline.lease")
    log.info("before-lease line")
    lc.set_pipeline_run_id(int(sys.argv[2]))
    log.info("after-lease line")

    def worker():
        logging.getLogger("swing.pipeline.worker").info("worker-thread line")
    t = threading.Thread(target=worker); t.start(); t.join()

    for h in logging.getLogger().handlers:
        try: h.flush()
        except Exception: pass
    """
)


def _write_cfg(tmp_path: Path) -> Path:
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    return _minimal_config(project, home)


def _logs_dir(cfg_path: Path) -> Path:
    from swing.config import load
    return load(cfg_path).paths.logs_dir


def _run_driver(tmp_path, env_overrides, run_id=42):
    cfg_path = _write_cfg(tmp_path)
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    env = dict(os.environ)
    env.pop("SWING_WEB_REQUEST_ID", None)
    env.update(env_overrides)
    # Ensure the child imports the in-tree swing package (repo root on sys.path).
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, str(driver), str(cfg_path), str(run_id)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return (_logs_dir(cfg_path) / "pipeline.log").read_text(encoding="utf-8")


def test_subprocess_carries_request_id_and_run_id(tmp_path):
    text = _run_driver(tmp_path, {"SWING_WEB_REQUEST_ID": "uuid-sentinel-001"}, run_id=42)
    # The env sentinel is on every line (main + worker thread).
    assert text.count("req=uuid-sentinel-001") >= 3
    # Before the lease the run id is the placeholder; after, it is 42.
    before = [ln for ln in text.splitlines() if "before-lease line" in ln][0]
    after = [ln for ln in text.splitlines() if "after-lease line" in ln][0]
    worker = [ln for ln in text.splitlines() if "worker-thread line" in ln][0]
    assert "run=-" in before
    assert "run=42" in after
    # The worker-thread line carries BOTH ids -- the discriminator a contextvars
    # impl would FAIL (the thread would render req=-/run=-).
    assert "req=uuid-sentinel-001" in worker and "run=42" in worker


def test_subprocess_forged_env_falls_back(tmp_path):
    text = _run_driver(tmp_path, {"SWING_WEB_REQUEST_ID": "bad value\nwith newline"})
    assert "req=-" in text
    assert "bad value" not in text  # the forged value never reaches a log line


def test_subprocess_no_context_renders_placeholders(tmp_path):
    text = _run_driver(tmp_path, {})  # no SWING_WEB_REQUEST_ID at all
    assert "req=-" in text
    # No KeyError / "Logging error" leaked to the file or stderr.
    assert "--- Logging error ---" not in text
```

- [ ] **Step 2: Run to verify it PASSES (regression proof, not a red step)**

Run: `python -m pytest tests/test_logging_correlation_e2e.py -q`
Expected: PASS — the production behavior was already built in Tasks 1-5; this is the committed cross-process regression guard. (If it fails, a prior task regressed — debug there, not here.)

- [ ] **Step 3: ruff + commit**

```bash
ruff check tests/test_logging_correlation_e2e.py
git add tests/test_logging_correlation_e2e.py
git commit -m "test(logging): end-to-end subprocess correlation transport proof"
```

---

## Task 7: `cli.log` surface + §3.4 routing + isolation + sentinel audit

Routes every non-pipeline `swing` command through a bounded/redacted `cli.log` via the group callback.

**Routing resolution (brief item a) — TWO-LEVEL skip-install (after Codex R1-major-1 + R2-major-1).** The brief's lean was "rely-on-replacement" (group installs `cli.log`, then `pipeline_run_cmd` installs `pipeline.log` and the §3.4 seam removes+closes the `cli.log` handler). Codex correctly showed this is **unsound**: `install_logging(surface="cli")` calls `_replay_logging_diagnostics` immediately after attaching the handler, so a **malformed `[logging]` value** writes a diagnostic record to `cli.log` in the window *before* `pipeline_run_cmd` installs `pipeline.log` — violating the locked "a pipeline-surface process emits only `pipeline.log`" invariant. The robust fix is **skip-install only for `pipeline run`** (the spec §5.1 contract is `pipeline run` → `pipeline.log`; *every other* command, incl. `pipeline list` / `pipeline force-clear`, → `cli.log`). Click dispatches group callbacks top-down (`main` → `pipeline_group` → subcommand), so:
- The `main` group callback installs `cli.log` for every top-level command **except** the `pipeline` subgroup (`ctx.invoked_subcommand != "pipeline"`).
- The `pipeline_group` callback installs `cli.log` for its non-`run` subcommands (`ctx.invoked_subcommand != "run"`) — so `pipeline list` / `force-clear` get `cli.log`.
- `pipeline_run_cmd` remains the **sole** installer for `pipeline run` (surface="pipeline").

This holds the invariant **unconditionally** for the `pipeline run` process (no cli install fires anywhere on that path, even with malformed config) AND honors the spec's "every other command → cli.log". `pipeline.log` content is byte-identical to today (the pipeline-run process installs exactly one surface, exactly as in Slice 1). The §3.4 seam logic stays as defence-in-depth for any stray double-install.

**Blast-radius containment:** ~373 `invoke(main)` tests now trigger the group install (root handlers + Belt-A factory + root level mutated). An autouse `tests/conftest.py` fixture snapshots/restores root logging state around every test (the manual snapshot/restore pattern the logging tests already use, applied suite-wide). Combined with the existing autouse home-redirect (logs_dir → tmp), the install is safe and leak-free.

**Files:**
- Modify: `swing/cli.py:182-188` (group callback)
- Modify: `tests/conftest.py` (add autouse logging-isolation fixture)
- Modify: `tests/test_logging_leak_guard.py` (add cli.log group-install guard)
- Test: `tests/test_cli_log_surface.py` (create)

- [ ] **Step 1: Add the autouse logging-state isolation fixture FIRST (containment before behavior)**

Append to `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _isolate_root_logging_state():
    """Snapshot/restore root logging handlers, root level, the LogRecord factory,
    the Schwab secret set, AND every existing logger's level around each test.

    Slice 2 makes the CLI group callback install a cli.log handler (+ Belt A
    factory + root level) on EVERY `swing` invocation, AND the [logging.loggers]
    override path mutates named loggers' levels (httpx/yfinance/swing.logging_config).
    The ~373 CliRunner(main) tests + the override tests would otherwise leak that
    state into sibling tests (xdist-order-fragile per the research-L2 gotcha
    family). This contains it: any handler a test adds is closed + removed
    afterward, the root state is restored, and every logger level is restored
    (newly-created loggers reset to NOTSET). (The home-redirect autouse fixture
    already routes logs_dir to tmp, so no real-home write occurs.)"""
    import logging
    from logging.handlers import RotatingFileHandler

    import swing.integrations.schwab.client as sc

    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_factory = logging.getLogRecordFactory()
    saved_secrets = set(sc._GLOBAL_KNOWN_SECRETS)
    # Snapshot the level of every logger that currently exists (R1-major-4).
    saved_logger_levels = {
        name: lg.level
        for name, lg in logging.Logger.manager.loggerDict.items()
        if isinstance(lg, logging.Logger)
    }
    yield
    for h in list(root.handlers):
        if h not in saved_handlers:
            if isinstance(h, RotatingFileHandler):
                h.close()
            root.removeHandler(h)
    for h in saved_handlers:
        if h not in root.handlers:
            root.addHandler(h)
    root.setLevel(saved_level)
    logging.setLogRecordFactory(saved_factory)
    sc._GLOBAL_KNOWN_SECRETS.clear()
    sc._GLOBAL_KNOWN_SECRETS.update(saved_secrets)
    # Restore pre-existing logger levels; reset loggers created during the test.
    for name, lg in logging.Logger.manager.loggerDict.items():
        if isinstance(lg, logging.Logger):
            lg.setLevel(saved_logger_levels.get(name, logging.NOTSET))
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_cli_log_surface.py
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from click.testing import CliRunner

import swing.cli as cli
from swing.config import load
from tests.cli.test_cli_eval import _minimal_config


def _cfg_path(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    return _minimal_config(project, home)


def test_non_pipeline_command_installs_cli_log(tmp_path):
    cfg_path = _cfg_path(tmp_path)
    logs_dir = load(cfg_path).paths.logs_dir
    # `config show` is a benign read-only command that goes through the group cb.
    result = CliRunner().invoke(cli.main, ["--config", str(cfg_path), "config", "show"])
    assert result.exit_code == 0, result.output
    root = logging.getLogger()
    cli_handlers = [
        h for h in root.handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) == "cli"
        and h.baseFilename == os.path.abspath(logs_dir / "cli.log")
    ]
    assert len(cli_handlers) == 1


def test_cli_log_is_redacted(tmp_path):
    # Belt B on cli.log: a non-Schwabdev sentinel emitted while the cli surface is
    # installed must be redacted. Discriminator: with no formatter wired the
    # SENTINEL would survive.
    sentinel = "deadbeef" * 8  # 64 hex chars -> caught by the shape heuristic
    cfg_path = _cfg_path(tmp_path)
    logs_dir = load(cfg_path).paths.logs_dir
    result = CliRunner().invoke(cli.main, ["--config", str(cfg_path), "config", "show"])
    assert result.exit_code == 0, result.output
    logging.getLogger("swing.cli.audit").warning("leaked token=%s", sentinel)
    for h in logging.getLogger().handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    text = (logs_dir / "cli.log").read_text(encoding="utf-8")
    assert sentinel not in text


def test_pipeline_run_converges_to_pipeline_log(tmp_path, monkeypatch):
    # Routing: `swing pipeline run` ends with EXACTLY ONE swing handler whose
    # surface is "pipeline". Under skip-install the group callback never installs
    # cli.log for the pipeline subgroup, so pipeline.log is the only swing handler.
    import swing.config_overrides as config_overrides
    import swing.pipeline as pipeline_pkg
    from swing.pipeline.runner import RunResult

    cfg_path = _cfg_path(tmp_path)
    logs_dir = load(cfg_path).paths.logs_dir
    monkeypatch.setattr(config_overrides, "apply_overrides", lambda cfg: cfg)
    monkeypatch.setattr(
        pipeline_pkg, "run_pipeline",
        lambda *, cfg, trigger: RunResult(run_id=1, state="complete", error_message=None),
    )
    result = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "pipeline", "run", "--manual"]
    )
    assert result.exit_code == 0, result.output
    swing_handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) is not None
    ]
    assert len(swing_handlers) == 1
    assert swing_handlers[0]._swing_surface == "pipeline"
    assert swing_handlers[0].baseFilename == os.path.abspath(logs_dir / "pipeline.log")


def test_pipeline_list_subcommand_installs_cli_log(tmp_path):
    # R2-major-1: `pipeline list` (a NON-run pipeline subcommand) must get cli.log
    # per spec §5.1 ("every command except `pipeline run` -> cli.log"). The
    # pipeline_group callback installs it for non-run subcommands.
    from swing.data.db import ensure_schema

    cfg_path = _cfg_path(tmp_path)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()  # `pipeline list` reads pipeline_runs
    logs_dir = cfg.paths.logs_dir
    result = CliRunner().invoke(cli.main, ["--config", str(cfg_path), "pipeline", "list"])
    assert result.exit_code == 0, result.output
    cli_handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) == "cli"
        and h.baseFilename == os.path.abspath(logs_dir / "cli.log")
    ]
    assert len(cli_handlers) == 1
    # And no pipeline.log handler (list is a cli-surface command).
    assert not any(
        getattr(h, "_swing_surface", None) == "pipeline"
        for h in logging.getLogger().handlers
    )


def test_pipeline_run_with_malformed_logging_never_writes_cli_log(tmp_path, monkeypatch):
    # R1-major-1 discriminator: a MALFORMED [logging] value makes install_logging
    # replay a parse diagnostic immediately after attaching a handler. Under the OLD
    # rely-on-replacement design the group's cli.log handler would receive that
    # diagnostic BEFORE pipeline.log installs -> cli.log gets content in a pipeline
    # process (invariant violated). Under skip-install the pipeline subgroup never
    # installs cli.log, so cli.log is never even created.
    import swing.config_overrides as config_overrides
    import swing.pipeline as pipeline_pkg
    from swing.config import load
    from swing.pipeline.runner import RunResult

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    # Append a malformed [logging] level so a parse diagnostic is collected.
    with open(cfg_path, "a", encoding="utf-8") as fh:
        fh.write('\n[logging]\nlevel = "LOUD"\n')
    logs_dir = load(cfg_path).paths.logs_dir
    monkeypatch.setattr(config_overrides, "apply_overrides", lambda cfg: cfg)
    monkeypatch.setattr(
        pipeline_pkg, "run_pipeline",
        lambda *, cfg, trigger: RunResult(run_id=1, state="complete", error_message=None),
    )
    result = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "pipeline", "run", "--manual"]
    )
    assert result.exit_code == 0, result.output
    # The diagnostic landed in pipeline.log (proves it was emitted), and cli.log
    # was NEVER created in this pipeline process.
    for h in logging.getLogger().handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    assert (logs_dir / "pipeline.log").exists()
    assert "LOUD" in (logs_dir / "pipeline.log").read_text(encoding="utf-8")
    assert not (logs_dir / "cli.log").exists()
```

> NOTE: the malformed test imports `CliRunner`, `logging`, `RotatingFileHandler`, `cli`, `_minimal_config` already imported at the top of `tests/test_cli_log_surface.py`.

Append to `tests/test_logging_leak_guard.py` (use a RELATIVE logs_dir so it genuinely discriminates the home-redirect, mirroring the existing web leak-guard `_RELATIVE_LOGS_TOML`):

```python
def test_cli_group_install_writes_cli_log_under_tmp_not_real_home(tmp_path):
    # The Slice-2 group-callback cli.log install must resolve under the redirected
    # (tmp) home, never the operator's real ~/swing-data/logs. Uses a RELATIVE
    # logs_dir (the real leak shape) so it discriminates the redirect -- an absolute
    # tmp logs_dir would short-circuit _resolve_path and prove nothing.
    import logging
    from logging.handlers import RotatingFileHandler

    from click.testing import CliRunner

    import swing.cli as cli
    from swing.config import _user_home

    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_RELATIVE_LOGS_TOML, encoding="utf-8")
    result = CliRunner().invoke(cli.main, ["--config", str(cfg_path), "config", "show"])
    assert result.exit_code == 0, result.output
    real_cli_log = _REAL_HOME / "swing-data" / "logs" / "cli.log"
    targets = [
        h.baseFilename for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler) and getattr(h, "_swing_surface", None) == "cli"
    ]
    assert targets, "no cli.log handler attached by the group callback"
    for t in targets:
        assert str(real_cli_log) != t
        assert str(_user_home()) in t  # resolved under the redirected (tmp) home
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_cli_log_surface.py tests/test_logging_leak_guard.py -q`
Expected: FAIL — the group callback installs no `cli.log` yet (`_swing_surface == "cli"` handler absent).

- [ ] **Step 4: Implement the group-callback install**

In `swing/cli.py`, change the `main` group callback (lines 182-188) to install `cli.log` right after config load, before the divergence hook:

```python
@click.group()
@click.option("--config", "config_path", default="swing.config.toml",
              help="Path to swing.config.toml")
@click.pass_context
def main(ctx: click.Context, config_path: str) -> None:
    """Swing trading CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(Path(config_path))
    ctx.obj["config_path"] = Path(config_path)
    # CLI observability (Arc-2 Slice-2): route every command through cli.log
    # (Belt A + Belt B + bounded rotation + correlation, by construction) EXCEPT
    # the `pipeline` subgroup. `pipeline_run_cmd` is the sole installer for the
    # pipeline path (surface="pipeline"); skipping the generic cli install here
    # guarantees a pipeline-surface process NEVER writes cli.log -- even when a
    # malformed [logging] value would make install_logging replay a diagnostic
    # the instant the handler attaches (the rely-on-replacement hazard, R1-major-1).
    if ctx.invoked_subcommand != "pipeline":
        from swing.logging_setup import install_logging
        install_logging(ctx.obj["config"], surface="cli")
    if ctx.invoked_subcommand not in _DIVERGENCE_HOOK_SKIP_SUBCOMMANDS:
        _apply_toml_divergence_check(ctx)
```

Also give the `pipeline_group` callback (currently a bare docstring at `cli.py:3301-3303`) a body so `pipeline list` / `pipeline force-clear` get `cli.log` while `pipeline run` stays pipeline-only (spec §5.1: every command except `pipeline run` → `cli.log`). Change:

```python
@main.group("pipeline")
def pipeline_group() -> None:
    """Nightly orchestrator: run, list, force-clear."""
```

to:

```python
@main.group("pipeline")
@click.pass_context
def pipeline_group(ctx: click.Context) -> None:
    """Nightly orchestrator: run, list, force-clear."""
    # `main` skipped the generic cli.log install for the whole pipeline subgroup
    # (so `pipeline run` never touches cli.log). Re-add it here for the NON-run
    # subcommands so `pipeline list` / `force-clear` log to cli.log per spec §5.1.
    # `pipeline run` is the sole pipeline.log installer (pipeline_run_cmd).
    if ctx.invoked_subcommand != "run":
        from swing.logging_setup import install_logging
        install_logging(ctx.obj["config"], surface="cli")
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_cli_log_surface.py tests/test_logging_leak_guard.py tests/integrations/test_pipeline_log_redaction.py -q`
Expected: PASS — incl. the existing `test_pipeline_run_cmd_writes_pipeline_log` (under skip-install the pipeline-run process installs only `pipeline.log`, with Belt B; no cli.log handler is created on that path).

- [ ] **Step 6: Run the full CLI + web test families to triage blast radius**

Run: `python -m pytest tests/cli tests/integrations tests/web -q -n0`
Expected: PASS. The autouse isolation fixture (Step 1) contains the handler/factory/level leakage. If any test fails on a handler-count / factory / root-level assertion, the correct fix is to confirm it now snapshots/restores via the autouse fixture (it should) — do NOT weaken the group install. Run `-n0` first (deterministic) before trusting `-n auto`.

- [ ] **Step 7: ruff + commit**

```bash
ruff check swing/cli.py tests/conftest.py tests/test_cli_log_surface.py tests/test_logging_leak_guard.py
git add swing/cli.py tests/conftest.py tests/test_cli_log_surface.py tests/test_logging_leak_guard.py
git commit -m "feat(cli): route swing commands through bounded redacted cli.log"
```

---

## Task 8: `[logging.loggers]` per-logger override table

Parse `[logging.loggers]` at config-load time into a resolved `dict[str, int]` (so malformed-entry diagnostics flow through the existing `warnings` carrier and are replayed after the redacted handler attaches — the frozen `LoggingConfig` cannot collect warnings lazily). `resolved_logger_levels()` returns the stored map. Shipped **empty** (the toml `[logging.loggers]` placeholder stays commented).

> **Design lock (brief flag):** the spec §5.3 wording "`resolved_logger_levels()` parses ... collecting a diagnostic into `LoggingConfig.warnings`" cannot literally hold for a frozen dataclass whose `warnings` is set at construction and whose `resolved_logger_levels()` is called from inside `install_logging` (before the diagnostics replay). Resolution: **parse at load time** in `_parse_logging_config` (collect into `warnings`), store the resolved dict in a new frozen `logger_levels` field, and have `resolved_logger_levels()` return a copy. Behavior is identical to the spec's intent; the carrier contract is honored.

**Files:**
- Modify: `swing/config.py` (`LoggingConfig` field + `resolved_logger_levels` body; `_parse_logging_config` parse block)
- Test: `tests/test_logging_loggers_override.py` (create); extend `tests/test_logging_setup.py` for the threshold-bypass replay.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_logging_loggers_override.py
from __future__ import annotations

import logging

from swing.config import _parse_logging_config


def test_happy_path_resolves_logger_levels():
    cfg = _parse_logging_config({
        "level": "INFO",
        "loggers": {"httpx": "WARNING", "yfinance": "ERROR"},
    })
    levels = cfg.resolved_logger_levels()
    assert levels == {"httpx": logging.WARNING, "yfinance": logging.ERROR}
    assert cfg.warnings == ()  # no diagnostics on a clean table


def test_malformed_entry_skipped_with_diagnostic():
    cfg = _parse_logging_config({
        "loggers": {"httpx": "WARNING", "bad": "LOUD", "alsobad": 5},
    })
    levels = cfg.resolved_logger_levels()
    assert levels == {"httpx": logging.WARNING}  # bad entries skipped
    joined = " ".join(cfg.warnings)
    assert "'bad'" in joined and "LOUD" in joined
    assert "'alsobad'" in joined


def test_non_table_loggers_value_diagnostic():
    cfg = _parse_logging_config({"loggers": "not-a-table"})
    assert cfg.resolved_logger_levels() == {}
    assert any("loggers" in w and "table" in w for w in cfg.warnings)


def test_absent_loggers_table_is_empty_no_warning():
    cfg = _parse_logging_config({"level": "INFO"})
    assert cfg.resolved_logger_levels() == {}
    assert cfg.warnings == ()


def test_resolved_logger_levels_returns_copy():
    cfg = _parse_logging_config({"loggers": {"httpx": "WARNING"}})
    m = cfg.resolved_logger_levels()
    m["httpx"] = logging.DEBUG  # mutate the returned dict
    assert cfg.resolved_logger_levels() == {"httpx": logging.WARNING}  # source intact
```

Append to `tests/test_logging_setup.py` (the threshold-bypass replay through `install_logging`, spec §6):

```python
def test_override_diagnostic_replayed_bypassing_thresholds(clean_root_and_secrets, tmp_path):
    # A junk per-logger override + a VALID high root level + an override that
    # silences the diagnostics logger itself: the diagnostic STILL lands (replayed
    # via handler.handle, bypassing root level + any per-logger filter).
    from dataclasses import replace
    from logging.handlers import RotatingFileHandler

    from swing.config import _parse_logging_config, load
    from tests.cli.test_cli_eval import _minimal_config

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    base = load(_minimal_config(project, home))
    parsed = _parse_logging_config({
        "level": "ERROR",
        "loggers": {"swing.logging_config": "CRITICAL", "httpx": "NOPE"},
    })
    cfg = replace(base, logging=parsed)
    install_logging(cfg, surface="pipeline")
    assert clean_root_and_secrets.level == logging.ERROR
    for h in clean_root_and_secrets.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    text = (cfg.paths.logs_dir / "pipeline.log").read_text(encoding="utf-8")
    assert "httpx" in text and "NOPE" in text  # the override diagnostic landed
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_logging_loggers_override.py "tests/test_logging_setup.py::test_override_diagnostic_replayed_bypassing_thresholds" -q`
Expected: FAIL — `resolved_logger_levels()` returns `{}` (the Task-3 stub) and no override diagnostics are collected.

- [ ] **Step 3: Implement the parse + field**

In `swing/config.py`, add the `logger_levels` field to `LoggingConfig` and replace the Task-3 stub body:

```python
@dataclass(frozen=True)
class LoggingConfig:
    """Logging knobs (spec §4.5 + §5.3). ``warnings`` carries parse-time
    diagnostics that install_logging replays AFTER the redacted handler attaches
    (R1-major-4) -- they are NEVER logged at parse time. ``logger_levels`` is the
    resolved [logging.loggers] override map (name -> level int), parsed at load
    time so malformed entries flow through ``warnings``."""
    level: int = logging.INFO
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5
    logger_levels: dict[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def resolved_logger_levels(self) -> dict[str, int]:
        """Return a COPY of the per-logger override map (defensive against caller
        mutation)."""
        return dict(self.logger_levels)
```

(Ensure `field` is imported — `from dataclasses import dataclass, field`; it already is for other dataclasses in this module. Verify at HEAD.)

In `_parse_logging_config`, after the `backup_count` block and before the `return LoggingConfig(...)`, add the loggers parse:

```python
    logger_levels: dict[str, int] = {}
    raw_loggers = raw.get("loggers", {})
    if isinstance(raw_loggers, dict):
        for name, lvl in raw_loggers.items():
            if isinstance(lvl, str) and lvl.upper() in _LEVEL_NAMES:
                logger_levels[name] = _LEVEL_NAMES[lvl.upper()]
            else:
                warnings.append(
                    f"[logging.loggers] {name!r} level {lvl!r} invalid; skipping"
                )
    elif "loggers" in raw:
        warnings.append(
            f"[logging.loggers] must be a table; got "
            f"{type(raw_loggers).__name__!r}; ignoring"
        )
```

and thread it into the constructor:

```python
    return LoggingConfig(
        level=level, max_bytes=max_bytes, backup_count=backup_count,
        logger_levels=logger_levels, warnings=tuple(warnings),
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_logging_loggers_override.py tests/test_logging_setup.py -q`
Expected: PASS — incl. the threshold-bypass replay and the existing diagnostics tests.

- [ ] **Step 5: Confirm the override actually sets the logger level end-to-end**

Add to `tests/test_logging_setup.py`:

```python
def test_logger_override_applied_to_named_logger(clean_root_and_secrets, tmp_path):
    from dataclasses import replace
    cfg = _cfg(tmp_path)
    cfg = replace(cfg, logging=replace(cfg.logging, logger_levels={"httpx": logging.WARNING}))
    install_logging(cfg, surface="cli")
    assert logging.getLogger("httpx").level == logging.WARNING
```

Run: `python -m pytest "tests/test_logging_setup.py::test_logger_override_applied_to_named_logger" -q`
Expected: PASS.

- [ ] **Step 6: ruff + commit**

```bash
ruff check swing/config.py tests/test_logging_loggers_override.py tests/test_logging_setup.py
git add swing/config.py tests/test_logging_loggers_override.py tests/test_logging_setup.py
git commit -m "feat(logging): per-logger override table via [logging.loggers]"
```

---

## Task 9: Full-suite regression + ruff sweep

**Files:** none (verification only).

- [ ] **Step 1: Full fast suite, deterministic first**

Run: `python -m pytest -m "not slow" -q -n0`
Expected: all green. Baseline 7777 + the new Slice-2 tests; **no pre-existing test regressed**. Read the actual tail of the output — do not infer green ([[feedback_no_false_green_claim]]).

- [ ] **Step 2: Full fast suite under xdist (worker-balance perturbation check)**

Run: `python -m pytest -m "not slow" -q`
Expected: same green count. If a research-L2 identity test flakes under `-n auto`, reproduce with `-n0` + explicit ordering (the xdist-order gotcha) — it is not a Slice-2 regression.

- [ ] **Step 3: ruff**

Run: `ruff check swing/`
Expected: clean.

- [ ] **Step 4: Confirm no schema touch + no forbidden-area touch**

Run:
```bash
git diff --stat main -- swing/data swing/trades
git grep -n "schema_version" swing/data/migrations | tail -1
```
Expected: empty `swing/data` + `swing/trades` diff; schema unchanged at v28 (no new migration).

- [ ] **Step 5: Commit (only if any incidental triage edits were needed; otherwise skip)**

```bash
git add -A
git commit -m "test(logging): Slice-2 full-suite regression sweep green"
```

---

## Self-Review (run before handing off)

**Spec coverage:**
- §5.1 cli.log centralization → Task 7 (group install + redaction + §3.4 routing). finviz security belt untouched (grounding lock).
- §5.2 correlation → Tasks 1 (carrier), 3 (install wiring + reset), 4 (Popen env + spawn line), 5 (lease set), 6 (E2E proof). `defaults=` always-present fields → Task 2.
- §5.3 override table → Task 8.
- §3.1/§3.2 seam/composition-root contract → Tasks 2-3 (no seam re-touch; the seam already accepts `record_filter`/`logger_levels`).
- §6 tests: env-sentinel subprocess + run-id + no-context (Task 6); worker-thread (Tasks 1, 6); forged env (Tasks 1, 6); reset-at-install (Tasks 1, 3); cli.log sentinel audit (Task 7); override happy/malformed/threshold-bypass (Task 8); single-surface (Task 7).
- §8 locks: no schema (Task 9 §4); Popen env-only (Task 4); set_pipeline_run_id in swing/pipeline (Task 5); trades/data untouched (Task 9).

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `reset_correlation_from_env()`, `set_pipeline_run_id(int|str|None)`, `get_web_request_id()->str`, `get_pipeline_run_id()->str`, `CorrelationFilter` (no args), `CORRELATION_LOG_DEFAULTS`, `_build_subprocess_env(str)->dict`, `resolved_logger_levels()->dict[str,int]`, `logger_levels` field — names consistent across Tasks 1-8.

**Open flags for executing/QA:**
1. `CorrelationFilter()` constructed without the spec's `(surface)` arg (documented YAGNI; behavior identical).
2. Task 5 monkeypatch targets (`runner.acquire_lease`/`Heartbeat`/`set_pipeline_run_id`) must be verified as module-level names at HEAD, and `Heartbeat(...)` must still be the first call after `set_pipeline_run_id` and outside the post-lease `try`.
3. Task 7's autouse isolation fixture is a suite-wide behavior change; deterministic `-n0` triage is mandated before trusting `-n auto`.
4. **Routing deviates from the brief's lean (Codex R1-major-1):** Task 7 uses **skip-install for the `pipeline` subgroup**, not rely-on-replacement — the brief's lean was unsound under a malformed `[logging]` config (diagnostics-replay would write to `cli.log` in a pipeline process). Side effect: `pipeline list`/`force-clear` get no swing log surface (unchanged from today). Flag for the orchestrator.
