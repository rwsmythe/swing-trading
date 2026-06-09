# Pipeline-Run Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web-spawned pipeline subprocess produce a redacted `pipeline.log`, and capture+persist a per-step duration ledger across all 13 steps, so the next slow run answers "which step owns the time" outright.

**Architecture:** A new Schwab-agnostic `configure_logging` seam routes both `web.log` and `pipeline.log` through one rotating-file handler; the CLI subprocess entrypoint installs two redaction belts (process-global factory + a `RedactingFormatter` on the pipeline handler) before any emit. The `Lease` gains an in-memory monotonic step-timing ledger that closes/opens a boundary interval on each `lease.step()` call and is flushed exactly once — in one batch transaction on a fresh `connect()` — from `run_pipeline_internal`'s `finally`, into a new `pipeline_step_timings` child table (migration `0025`, schema v24→v25).

**Tech Stack:** Python 3.14, stdlib `logging` (`TimedRotatingFileHandler`), SQLite via the project `connect()`/migration runner, pytest + Click `CliRunner`.

> **ⓘ ONE FLAGGED SPEC CORRECTION FOR THE ORCHESTRATOR:** the spec's original §5.3 migration-transaction
> guidance ("pure DDL, no in-file `BEGIN/COMMIT`") was **factually wrong** — `_apply_migration` runs
> `executescript()` in autocommit and does NOT open a `BEGIN`, so a pure-DDL `0025` is NOT atomic and
> violates gotcha #9 (a CLAUDE.md hard rule); `0023`/`0024` both carry explicit `BEGIN; ... COMMIT;`.
> Per the implementer charter (flag spec errors, don't silently deviate) and the adversarial reviewer's
> explicit direction, **spec §5.3 has been AMENDED in this worktree** to require `BEGIN; ... COMMIT;`
> (dated note in the spec), and migration `0025` follows the amended spec. The orchestrator ratifies
> this spec correction at the main merge ([[feedback_orchestrator_performs_merge]]). This is the only
> spec change; everything else implements the spec as written.

---

## Resolved decisions (the brief §3 deferrals)

1. **Slow-step advisory soft-budget constant (spec §5.4).** A single module constant
   `STEP_SOFT_BUDGET_MS = 60_000` in `swing/pipeline/lease.py` (co-located with `step()` and the
   ledger emit), defaulting to the existing charts 60s shape. It drives a **`WARN` log line only** —
   never a control-flow gate, never an error. Rationale: the emitter lives in `lease.py`, so the
   budget belongs next to it; it is a constant (not persisted), so per-step budgets can be tuned later
   with zero schema churn. The existing charts-specific 60s/120s warning at
   [`runner.py:3214-3226`](../../../swing/pipeline/runner.py) is **left unchanged** (it carries
   charts-specific `scope=tickers` context); the generic per-step `WARN` is additive.

2. **Repo home (spec §5.5).** A **separate** new file
   `swing/data/repos/pipeline_step_timings.py` (NOT folded into `swing/data/repos/pipeline.py`).
   Rationale: a focused single-responsibility unit; matches the per-domain repo split the codebase
   already uses; keeps the lease/run CRUD in `pipeline.py` uncluttered. The frozen `StepTiming`
   dataclass + `_row_to_step_timing` mapper live in that same file (read-path/write-path together,
   per #11).

3. **Ledger-on-`Lease` + single flush entry (spec §10).** The ledger state lives on `Lease`
   (co-located with `step()`); `flush_step_timings()` is the **sole** public flush entry, called
   **exactly once** from the `finally` of **`run_pipeline_internal`** (the spec's "`run()`" shorthand;
   def at [`runner.py:531`](../../../swing/pipeline/runner.py), `finally` at
   [`runner.py:1034`](../../../swing/pipeline/runner.py)),
   guarded by `_timings_flushed` which is set `True` **only after** the batch INSERT commits. No other
   `lease.step` caller path bypasses that `finally`: the only `finally` that owns post-run teardown is
   at `runner.py:1034`, and `lease` is always bound there (the `ConcurrentRunBlockedError` early
   return at [`runner.py:572`](../../../swing/pipeline/runner.py) fires **before** the big
   `try`/`finally` at L586/L1034 is ever entered — verified on disk). Task 6 makes this an explicit
   acceptance.

4. **`complete`-boundary semantics (spec §5.2).** The final `lease.step("complete")` opens a pending
   ledger entry that is closed at flush; its `duration_ms` measures **genuine** post-`export`
   finalization (`_step_review_log_cadence` at [`runner.py:1014-1020`](../../../swing/pipeline/runner.py)
   + `lease.release()` + teardown up to flush). It is small but **real** — `export` gets its own real
   duration from the `export`→`complete` boundary. **Do NOT special-case or drop `complete`.** An
   executor must not "fix" a brief `complete` duration as a bug; this is documented here so the
   expectation is explicit.

---

## STEP-0 re-grounding (verified on worktree HEAD `00d94b2b`, 2026-06-09)

All spec/brief anchors re-confirmed on the worktree before line numbers were pinned:

- 14 `lease.step()` call sites / 13 distinct names confirmed in `runner.py`: `finviz_fetch`@**634**
  (inbox-empty branch) + `finviz_fetch`@**758** (unconditional), `weather`@**723** between them,
  then `evaluate`@817, `daily_management`@835, `watchlist`@855, `recommendations`@867,
  `pattern_detect`@885, `pattern_observe`@904, `schwab_snapshot`@931, `schwab_orders`@960,
  `charts`@982, `export`@999, `complete`@**1013**.
- `Lease` is a plain `@dataclass` (NOT frozen) with exactly 3 fields (`db_path, run_id, token`) at
  [`lease.py:36`](../../../swing/pipeline/lease.py); `step()`@53-62, `_now_iso()`@28-29.
- `run()`'s teardown `finally` is at [`runner.py:1034`](../../../swing/pipeline/runner.py)
  (currently `hb.stop()` + `audit_conn.close()`); `acquire_lease` runs in the outer try @560-572 (early
  return @572 before the big try @586) → **`lease` always bound at L1034**. `hb` also bound (created
  @574). `log` is module-level in `runner.py`.
- `pipeline_run_cmd` is at [`cli.py:3213`](../../../swing/cli.py) (def); the wiring point is between
  `cfg = apply_overrides(...)` (L3220) and `result = run_pipeline(...)` (L3221). `sys.stdout/stderr`
  already reconfigured to utf-8 `errors="replace"` at [`cli.py:22-23`](../../../swing/cli.py).
- Redaction: `ensure_schwab_log_redaction_factory_installed()`@201,
  `_make_redactor_from_global()`@106, `_schwab_record_factory`@~155 in
  [`swing/integrations/schwab/client.py`](../../../swing/integrations/schwab/client.py).
- `configure_web_logging`@[`request_id.py:32-50`](../../../swing/web/middleware/request_id.py)
  (`TimedRotatingFileHandler`, `when="D"`, `backupCount=7`, utf-8, dedup by `baseFilename`).
- DB: `connect`@[`db.py:1194`](../../../swing/data/db.py) (already imported by `lease.py`),
  `_apply_migration`@252-295 (explicit `executescript`+`commit`/`rollback`, FK toggled OFF),
  `EXPECTED_SCHEMA_VERSION = 24`@51, `_b7_backup_gate`@~1023-1066,
  `B7_PRE_MIGRATION_EXPECTED_TABLES`@217, `_create_pre_b7_migration_backup`@633,
  `_verify_backup_integrity`@372, `_resolve_main_db_path`@419,
  `run_migrations`@~1126 with the `if current >= target_version: return` early-return and the gate
  chain (`_phase7_backup_gate` → `_phase14_sb3_backup_gate` → `_b7_backup_gate`).
- **Latest migration is `0024`** → `0025` is the next number; v24→v25 is correct.

---

## File map

**Create:**
- `swing/logging_config.py` — the Schwab-agnostic `configure_logging` seam + `DEFAULT_LOG_FORMAT`.
- `swing/data/migrations/0025_phase16_pipeline_step_timings.sql` — child table in an explicit
  `BEGIN; ... COMMIT;` block + the mandatory `UPDATE schema_version SET version = 25;` (gotcha #9,
  mirroring `0023`/`0024`; per the AMENDED spec §5.3 — see Task 3 + the return-report spec-correction
  flag).
- `swing/data/migrations/__init__.py` is untouched; **`docs/superpowers/specs/2026-06-08-pipeline-observability-design.md`
  §5.3 is AMENDED** (the one spec change — corrects the migration-transaction guidance).
- `swing/data/repos/pipeline_step_timings.py` — `StepTiming` (frozen) + `_row_to_step_timing` +
  `insert_step_timings` + `list_step_timings` + `step_durations_by_name`.
- Tests: `tests/test_logging_config.py`, `tests/integrations/test_pipeline_log_redaction.py`,
  `tests/data/test_migration_0025_phase16.py`, `tests/data/test_repos_pipeline_step_timings.py`,
  `tests/pipeline/test_lease_timings.py`, `tests/pipeline/test_lease_flush.py`,
  `tests/pipeline/test_runner_step_timings.py`.

**Modify:**
- `swing/web/middleware/request_id.py` — `configure_web_logging` becomes a thin shim.
- `swing/integrations/schwab/client.py` — add `RedactingFormatter`.
- `swing/cli.py` — `pipeline_run_cmd` installs Belt A + `configure_logging(... surface="pipeline" ...)`.
- `swing/data/db.py` — `EXPECTED_SCHEMA_VERSION` 24→25; `PHASE16_PRE_MIGRATION_EXPECTED_TABLES`;
  `_create_pre_phase16_migration_backup`; `_phase16_backup_gate`; wire it into `run_migrations`.
- `swing/pipeline/lease.py` — ledger fields, `_monotonic()`, `STEP_SOFT_BUDGET_MS`, `_PendingStep`,
  `_record_step_boundary`, `_close_pending`, `_aggregate_by_name`, `_emit_step_line`,
  `_emit_totals_line`, `step()` boundary recording, `flush_step_timings()`.
- `swing/pipeline/runner.py` — call `lease.flush_step_timings()` in the `finally` at L1034.

**Out of scope (untouched):** `swing/web/routes/pipeline.py` (DEVNULL kept), `swing/trades/*`
(read-only).

---

## Task 1: The `configure_logging` seam (spec §4.1)

**Files:**
- Create: `swing/logging_config.py`
- Modify: `swing/web/middleware/request_id.py:32-50`
- Test: `tests/test_logging_config.py`

No schema, no redaction yet. This task only proves the seam produces `{surface}.log` identically to
today's `web.log`, is idempotent, and — the R2-Major-2 case — installs a supplied `formatter` onto a
pre-existing same-file handler.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_logging_config.py
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler

import pytest

from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging


@pytest.fixture
def clean_root():
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    for h in list(root.handlers):
        root.removeHandler(h)
    yield root
    for h in list(root.handlers):
        if isinstance(h, TimedRotatingFileHandler):
            h.close()
        root.removeHandler(h)
    for h in saved:
        root.addHandler(h)
    root.setLevel(saved_level)


def _file_handlers(root, target):
    return [
        h for h in root.handlers
        if isinstance(h, TimedRotatingFileHandler) and h.baseFilename == str(target)
    ]


def test_pipeline_surface_attaches_named_handler(clean_root, tmp_path):
    configure_logging(tmp_path, surface="pipeline")
    target = tmp_path / "pipeline.log"
    handlers = _file_handlers(clean_root, target)
    assert len(handlers) == 1
    assert handlers[0].backupCount == 7
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_logging_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'swing.logging_config'`.

- [ ] **Step 3: Write the seam module**

```python
# swing/logging_config.py
"""Neutral logging seam shared by the web app and the pipeline CLI subprocess.

Top-level (not under swing.web or swing.cli) so neither importer pulls in the
other. Schwab-agnostic by construction: it imports nothing from
swing.integrations.schwab — the secret-bearing CLI surface injects a
RedactingFormatter via the `formatter` parameter (see Arc-1 spec §4.2).
"""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging(
    logs_dir: Path,
    *,
    surface: str,
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
) -> None:
    """Attach a TimedRotatingFileHandler writing ``{surface}.log`` to the root logger.

    Idempotent (dedup by baseFilename). ``surface`` in {'web', 'pipeline'}.
    When ``formatter`` is supplied AND a same-file handler already exists, the
    formatter is installed onto that handler (R2-Major-2) — never silently
    skipped. The formatter is set on the handler BEFORE it is added to root, so
    there is no unredacted window. ``level`` exists for Arc-2a to wire a knob
    later without changing the signature; default stays INFO.
    """
    if surface not in {"web", "pipeline"}:
        raise ValueError(f"surface must be 'web' or 'pipeline', got {surface!r}")
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = str(Path(logs_dir) / f"{surface}.log")
    root = logging.getLogger()
    # Set the level on EVERY path (including dedup) — if a prior handler was
    # attached while root was at WARNING, the pipeline surface's INFO per-step lines
    # would otherwise stay suppressed.
    root.setLevel(level)
    for h in root.handlers:
        if isinstance(h, TimedRotatingFileHandler) and h.baseFilename == target:
            if formatter is not None:
                h.setFormatter(formatter)
            return
    handler = TimedRotatingFileHandler(
        filename=target, when="D", interval=1, backupCount=7, encoding="utf-8",
    )
    handler.setFormatter(
        formatter if formatter is not None else logging.Formatter(DEFAULT_LOG_FORMAT)
    )
    root.addHandler(handler)
```

- [ ] **Step 4: Convert `configure_web_logging` to a shim**

Replace the body at [`swing/web/middleware/request_id.py:32-50`](../../../swing/web/middleware/request_id.py):

```python
# swing/web/middleware/request_id.py  (top of file, with the other imports)
from swing.logging_config import configure_logging


def configure_web_logging(logs_dir: Path) -> None:
    """Thin shim over the shared seam (no formatter override → default formatter)."""
    configure_logging(logs_dir, surface="web")
```

Remove the now-dead local `TimedRotatingFileHandler` import if it is unused elsewhere in the file
(grep first; `app.py:441` keeps calling `configure_web_logging(cfg.paths.logs_dir)` unchanged).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_logging_config.py tests/web/test_error_handling.py -q`
Expected: PASS — the new seam tests pass AND the existing `web.log` tests in
`test_error_handling.py` stay green (seam regression, spec §6.7).

- [ ] **Step 6: Commit**

```bash
git add swing/logging_config.py swing/web/middleware/request_id.py tests/test_logging_config.py
git commit -m "feat(logging): add configure_logging seam with surface parameterization"
```

---

## Task 2: `RedactingFormatter` (Belt B) + subprocess entrypoint wiring (spec §4.2)

**Files:**
- Modify: `swing/integrations/schwab/client.py` (add `RedactingFormatter`)
- Modify: `swing/cli.py:3213-3221` (`pipeline_run_cmd` wiring)
- Test: `tests/integrations/test_pipeline_log_redaction.py`

Belt A = the process-global factory (existing, Schwabdev-prefix only). Belt B = a `RedactingFormatter`
on the `pipeline.log` handler that redacts the **fully rendered** line (message + args + traceback)
regardless of logger name, consulting the **live** redactor per record.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integrations/test_pipeline_log_redaction.py
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler

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
        if isinstance(h, TimedRotatingFileHandler):
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
        if isinstance(h, TimedRotatingFileHandler):
            h.flush()
    return path.read_text(encoding="utf-8")


def test_handler_carries_redacting_formatter_at_attach(pipeline_logging):
    handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, TimedRotatingFileHandler)
    ]
    assert any(isinstance(h.formatter, RedactingFormatter) for h in handlers)


def test_non_schwabdev_logger_line_is_redacted(pipeline_logging):
    # A swing.pipeline.* logger — Belt A (Schwabdev-prefix) would NOT cover it.
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
    # A NON-shape secret registered ONLY after handler attach — proves format()
    # consults the LIVE secret set per record (R2-Major-1). Discriminator: under a
    # snapshot-at-attach impl, NONSHAPE_LATE (not in the set at attach, not
    # shape-caught) would survive → "not in text" would FAIL. Under correct
    # per-record consultation it is redacted.
    register_schwab_secrets([NONSHAPE_LATE])  # registered AFTER handler attach
    logging.getLogger("swing.pipeline.lease").info("late=%s", NONSHAPE_LATE)
    text = _read(pipeline_logging)
    assert NONSHAPE_LATE not in text


def test_long_line_is_redacted_without_truncation(pipeline_logging):
    # A line > 500 chars with the secret early and a TAIL_MARKER past char 500.
    # CORRECT (full-line redactor): SENTINEL redacted AND TAIL_MARKER preserved.
    # NAIVE (the [:500]-truncating _make_redactor_from_global): the line is cut at
    # 500 chars → TAIL_MARKER is DROPPED → the marker assertion FAILS. Discriminates
    # truncating-vs-full redaction.
    tail_marker = "TAILMARKERPRESENT"
    padding = "x" * 600
    logging.getLogger("swing.pipeline.runner").info(
        "secret=%s pad=%s end=%s", SENTINEL, padding, tail_marker
    )
    text = _read(pipeline_logging)
    assert SENTINEL not in text
    assert tail_marker in text  # fails under the 500-char-truncating redactor
```

> **Note:** `register_schwab_secrets` mutates a process-global set (`_GLOBAL_KNOWN_SECRETS`). The
> `pipeline_logging` fixture should also clear/restore that set (or the test should `pop` its
> sentinel) so the late-registered secret does not leak into sibling tests; add a
> `_GLOBAL_KNOWN_SECRETS.discard(NONSHAPE_LATE)` in teardown, or snapshot/restore the set in the
> fixture.

> **Note on the sentinel shape:** the redactor's heuristic catches 32+hex / 24+b64 *shapes*, so a
> shape-valid sentinel is redacted even for a slot not registered in the global secret set. If a chosen
> sentinel is shorter/non-hex, register it first via the same mechanism the existing
> `test_schwab_client.py` leak tests use, or lengthen it to satisfy the heuristic. Verify the exact
> heuristic in `_make_redactor_from_global()` ([`client.py:106`](../../../swing/integrations/schwab/client.py))
> when picking the sentinel.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/integrations/test_pipeline_log_redaction.py -q`
Expected: FAIL — `ImportError: cannot import name 'RedactingFormatter'`.

- [ ] **Step 3: Add a full-line redactor + `RedactingFormatter` to the Schwab client**

> **Why a NEW redactor (Round-1 Codex CRITICAL-adjacent finding):** the existing
> `_make_redactor_from_global()` truncates its input to `message[:500]`
> ([`client.py:120`](../../../swing/integrations/schwab/client.py)) — it is designed for short audit
> excerpts. Using it in the formatter would **truncate every log line to 500 chars**, destroying
> tracebacks (and the spec §4.2 "fully rendered line" guarantee). So we add a sibling
> `_make_full_redactor_from_global()` that applies the SAME Layer-0 (exact-set) + Layer-1a (32+hex) +
> Layer-1b (24+b64) logic with **no `[:500]` excerpt**, leaving the audit-excerpt redactor untouched.

```python
# swing/integrations/schwab/client.py  (near _make_redactor_from_global, ~L106)
def _make_full_redactor_from_global() -> Callable[[str], str]:
    """Like _make_redactor_from_global but WITHOUT the 500-char excerpt — for
    full log lines (Belt B / RedactingFormatter). Reads _GLOBAL_KNOWN_SECRETS at
    each call so late-registered/rotated secrets are still redacted (R2-Major-1)."""
    def redact(message: str) -> str:
        if not message:
            return message
        with _GLOBAL_FILTER_LOCK:
            secrets = list(_GLOBAL_KNOWN_SECRETS)
        secrets.sort(key=len, reverse=True)  # longest-first; substring safety
        out = message
        for s in secrets:
            out = out.replace(s, "<REDACTED>")
        out = re.sub(r"[a-fA-F0-9]{32,}", "<REDACTED>", out)
        out = re.sub(r"[A-Za-z0-9+/=]{24,}", "<REDACTED>", out)
        return out
    return redact


class RedactingFormatter(logging.Formatter):
    """A logging.Formatter that redacts the FULLY RENDERED line (no truncation).

    Belt B for pipeline.log: super().format(record) renders message +
    interpolated args + traceback + stack-info into one string; the live full-line
    content-redactor then scrubs it regardless of logger name. The redactor is
    rebuilt from the global secret set on EVERY call (R2-Major-1), so a secret
    registered/rotated after handler attach is still redacted.
    """

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        redactor = _make_full_redactor_from_global()
        return redactor(rendered)
```

> **Implementer note:** confirm `_GLOBAL_FILTER_LOCK`, `_GLOBAL_KNOWN_SECRETS`, `re`, and `Callable`
> are already in scope at the insertion point (they are used by `_make_redactor_from_global` just
> above). Reuse them; do not re-import.

- [ ] **Step 4: Wire the CLI subprocess entrypoint**

In [`swing/cli.py`](../../../swing/cli.py) `pipeline_run_cmd` (the def at L3213), insert the two belts
between `cfg = apply_overrides(...)` and `result = run_pipeline(...)`:

```python
    cfg = apply_overrides(ctx.obj["config"])
    # Pipeline observability (Arc-1): make this subprocess self-contained.
    # Belt A FIRST (process-global factory, before any handler attach or emit),
    # then Belt B (RedactingFormatter on the pipeline.log handler). Works for
    # both the web-spawned (DEVNULL parent) and direct `swing pipeline run`.
    from swing.integrations.schwab.client import (
        RedactingFormatter,
        ensure_schwab_log_redaction_factory_installed,
    )
    from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging

    ensure_schwab_log_redaction_factory_installed()
    configure_logging(
        cfg.paths.logs_dir, surface="pipeline",
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT),
    )
    result = run_pipeline(cfg=cfg, trigger="manual" if manual else "scheduled")
```

- [ ] **Step 5: Add the subprocess-self-containment test (spec §6.5)**

```python
# tests/integrations/test_pipeline_log_redaction.py  (append)
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
    #  `from swing.pipeline import run_pipeline`) → patch the IMPORT SOURCES.
    # Identity apply_overrides keeps the test hermetic (no operator user-config read).
    monkeypatch.setattr(config_overrides, "apply_overrides", lambda cfg: cfg)

    # Emit a benign per-step line AND a secret SENTINEL through a swing.pipeline.*
    # (non-Schwabdev) logger. The benign line proves pipeline.log is written; the
    # SENTINEL proves the CLI wired Belt B (RedactingFormatter) — without it the
    # SENTINEL would survive (Belt A alone does not cover swing.pipeline.* loggers).
    def fake_run_pipeline(*, cfg, trigger):
        log = logging.getLogger("swing.pipeline.lease")
        log.info("step ordinal=0 name=evaluate took 5 ms")
        log.warning("leaked token=%s", SENTINEL)
        return RunResult(run_id=1, state="complete", error_message=None)

    monkeypatch.setattr(pipeline_pkg, "run_pipeline", fake_run_pipeline)

    # Snapshot/restore root handlers AND level so this test's pipeline.log handler
    # + the INFO level set by configure_logging do not bleed into sibling tests.
    from logging.handlers import TimedRotatingFileHandler
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
            if isinstance(h, TimedRotatingFileHandler)
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
        from logging.handlers import TimedRotatingFileHandler
        for h in list(root.handlers):
            if h not in saved and isinstance(h, TimedRotatingFileHandler):
                h.close()
                root.removeHandler(h)
        root.setLevel(saved_level)
```

> **Implementer notes (binding):**
> - Patch targets are the IMPORT SOURCES because `pipeline_run_cmd` imports both names *inside* the
>   function body: patch `swing.config_overrides.apply_overrides` and `swing.pipeline.run_pipeline`
>   (NOT attributes on `swing.cli`). Verified at plan time at [`cli.py:3216-3217`].
> - `_minimal_config(project, home)` is the canonical config helper at
>   [`tests/cli/test_cli_eval.py`](../../../tests/cli/test_cli_eval.py) (also used by
>   `tests/pipeline/test_runner_backup_integration.py`); `swing.config.load(cfg_path).paths.logs_dir`
>   is the real logs dir the wiring writes to.
> - Do NOT spawn a real OS subprocess in the fast suite (network/yfinance); the in-process `CliRunner`
>   path exercises the identical wiring lines added in Step 4.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/integrations/test_pipeline_log_redaction.py -q`
Expected: PASS — all four redaction cases + the self-containment test.

- [ ] **Step 7: Commit**

```bash
git add swing/integrations/schwab/client.py swing/cli.py tests/integrations/test_pipeline_log_redaction.py
git commit -m "feat(logging): redact pipeline.log via two-belt formatter and CLI wiring"
```

---

## Task 3: Migration `0025` + `_phase16_backup_gate` (spec §5.3)

**Files:**
- Create: `swing/data/migrations/0025_phase16_pipeline_step_timings.sql`
- Modify: `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION`, the new constant/helpers/gate + wiring)
- Test: `tests/data/test_migration_0025_phase16.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_migration_0025_phase16.py
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data import db as dbmod
from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    open_connection,
    run_migrations,
    _current_version,
    _phase16_backup_gate,
)


def _migrate_to(db_path: Path, version: int, backup_dir: Path | None = None):
    # open_connection is the canonical opener (busy_timeout + FK + WAL); it creates
    # the file if missing and does NOT enforce a schema-version gate, so it can build
    # a DB at any target version. (connect() also works but reaffirm_wal=True matches
    # ensure_schema's bootstrap; mirror the existing migration tests.)
    conn = open_connection(db_path, reaffirm_wal=True)
    run_migrations(conn, target_version=version, backup_dir=backup_dir)
    return conn


def test_expected_schema_version_is_25():
    assert EXPECTED_SCHEMA_VERSION == 25


def test_migrate_to_25_creates_table(tmp_path):
    db = tmp_path / "swing.db"
    conn = _migrate_to(db, 25)
    assert _current_version(conn) == 25
    # connect() sets NO row_factory → rows are tuples; PRAGMA table_info columns
    # are (cid, name, type, notnull, dflt_value, pk) → name is index 1.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(pipeline_step_timings)")}
    assert cols == {
        "id", "run_id", "ordinal", "step_name",
        "started_ts", "finished_ts", "duration_ms",
    }
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    db = tmp_path / "swing.db"
    _migrate_to(db, 25).close()
    conn = open_connection(db, reaffirm_wal=True)
    run_migrations(conn, target_version=25)  # current >= target → early return
    assert _current_version(conn) == 25
    conn.close()


def test_backup_gate_fires_strict_on_v24(tmp_path):
    # Each gate call uses its OWN backup_dir so a second-resolution timestamp
    # collision in the filename cannot mask a second backup (count per-dir is 0/1).
    db = tmp_path / "swing.db"
    conn = _migrate_to(db, 24)  # build a real v24 DB (no gate fires at 24)

    def _count(d):
        return len(list(d.glob("swing-pre-phase16-migration-*.db")))

    inert = tmp_path / "b_inert"      # current=25 → must NOT fire
    fire_25 = tmp_path / "b_25"       # current=24, target=25 → fires
    fire_26 = tmp_path / "b_26"       # current=24, target=26 → fires (crossing v25)
    naive_bug = tmp_path / "b_naive"  # current=23, target=25 → STRICT skips; a <=24 bug fires

    _phase16_backup_gate(conn, current_version=25, target_version=26, backup_dir=inert)
    _phase16_backup_gate(conn, current_version=24, target_version=25, backup_dir=fire_25)
    _phase16_backup_gate(conn, current_version=24, target_version=26, backup_dir=fire_26)
    _phase16_backup_gate(conn, current_version=23, target_version=25, backup_dir=naive_bug)

    assert _count(inert) == 0
    assert _count(fire_25) == 1
    assert _count(fire_26) == 1
    assert _count(naive_bug) == 0  # the discriminator: a `current_version <= 24` bug → 1 here
    conn.close()


def test_run_migrations_wires_phase16_gate(tmp_path):
    # Proves _phase16_backup_gate is actually WIRED into run_migrations (a direct
    # gate call cannot catch a missing wire). A real v24->v25 walk through the runner
    # must produce a backup; a fresh 0->25 build must NOT (current=0 != 24, strict).
    fresh_backups = tmp_path / "fresh"
    fresh = tmp_path / "fresh.db"
    _migrate_to(fresh, 25, backup_dir=fresh_backups).close()  # 0->25, gate inert
    assert not list(fresh_backups.glob("swing-pre-phase16-migration-*.db"))

    v24_backups = tmp_path / "v24b"
    db = tmp_path / "swing.db"
    _migrate_to(db, 24).close()  # build v24
    conn = open_connection(db, reaffirm_wal=True)
    run_migrations(conn, target_version=25, backup_dir=v24_backups)  # v24->v25 via runner
    assert _current_version(conn) == 25
    assert {r[1] for r in conn.execute("PRAGMA table_info(pipeline_step_timings)")}
    assert len(list(v24_backups.glob("swing-pre-phase16-migration-*.db"))) == 1
    conn.close()

    # v24 -> v26 through the REAL runner: gate fires (crossing v25); apply_ceiling =
    # min(26, EXPECTED_SCHEMA_VERSION=25) = 25, so it advances to 25 and backs up.
    v26_backups = tmp_path / "v26b"
    db26 = tmp_path / "swing26.db"
    _migrate_to(db26, 24).close()
    conn26 = open_connection(db26, reaffirm_wal=True)
    run_migrations(conn26, target_version=26, backup_dir=v26_backups)
    assert _current_version(conn26) == 25  # ceiling-clamped to EXPECTED_SCHEMA_VERSION
    assert len(list(v26_backups.glob("swing-pre-phase16-migration-*.db"))) == 1
    conn26.close()
```

> **Discriminating arithmetic** ([[feedback_regression_test_arithmetic]]): the `naive_bug` line
> (`current=23, target=25`) is the one that distinguishes the **correct** STRICT
> `current_version == 24` gate (count **0** — 23 != 24) from a **naive `current_version <= 24`** gate
> (count **1** — 23 <= 24 fires). The `inert` line (`current=25`) skips under BOTH (25 > 24 and
> 25 != 24), so it alone does not catch the `<=` bug — `naive_bug` does. Per-dir counts also dodge the
> second-resolution `strftime` filename collision (two backups in the same wall-clock second would
> share a filename in one shared dir; separate dirs make the count unambiguous).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/data/test_migration_0025_phase16.py -q`
Expected: FAIL — `ImportError: cannot import name '_phase16_backup_gate'` (and the version assert
fails at 24).

- [ ] **Step 3: Write the migration (explicit `BEGIN/COMMIT` + version bump, per gotcha #9 / amended §5.3)**

```sql
-- swing/data/migrations/0025_phase16_pipeline_step_timings.sql
-- Explicit BEGIN; ... COMMIT; per gotcha #9 (executescript implicit-COMMIT discipline),
-- mirroring 0023/0024. _apply_migration runs executescript in autocommit and does NOT
-- open its own BEGIN, so the in-file BEGIN/COMMIT is what makes a mid-script failure
-- atomically roll back. The runner additionally toggles foreign_keys OFF for the
-- duration + wraps the call in try/except rollback().
BEGIN;
CREATE TABLE pipeline_step_timings (
  id          INTEGER PRIMARY KEY,
  run_id      INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  ordinal     INTEGER NOT NULL,          -- 0-based monotonic open-order within the run
  step_name   TEXT    NOT NULL,          -- free-text; no CHECK enum (future steps need no schema change)
  started_ts  TEXT    NOT NULL,          -- wall-clock ISO seconds (_now_iso) at step open
  finished_ts TEXT    NOT NULL,          -- wall-clock ISO seconds at step close (flush closes before insert)
  duration_ms INTEGER NOT NULL,          -- monotonic-sourced, integer-truncated ms
  UNIQUE(run_id, ordinal)
);
-- No separate run_id index: UNIQUE(run_id, ordinal) already indexes run_id as the leading column.
UPDATE schema_version SET version = 25;
COMMIT;
```

> **This matches the AMENDED spec §5.3 (corrected 2026-06-09) — it is NOT a deviation.** The spec's
> original §5.3 said "pure DDL, no in-file `BEGIN/COMMIT`" on the (incorrect) premise that
> `_apply_migration` opens the transaction. It does not: `_apply_migration`
> ([`db.py:252-295`](../../../swing/data/db.py)) runs `executescript()` in **autocommit** + `commit()`,
> with NO `BEGIN`. Without an in-file `BEGIN`, a mid-script failure (e.g. the version bump failing after
> the `CREATE TABLE` already auto-committed) cannot be rolled back — the gotcha #9 hazard. `0023`/`0024`
> both carry `BEGIN; ... COMMIT;` for this reason. **The spec §5.3 was amended (in this worktree) to
> require `BEGIN; ... COMMIT;`; this plan follows the amended spec.** (Surfaced in the return report —
> the orchestrator ratifies the spec correction at the main merge.) The `UPDATE schema_version SET
> version = 25;` is also mandatory: `run_migrations` verifies `final_version == target_version` and
> **raises** otherwise ([`db.py:~1160`](../../../swing/data/db.py)).

- [ ] **Step 4: Bump the version + add the constant/helpers/gate in `db.py`**

```python
# swing/data/db.py
EXPECTED_SCHEMA_VERSION = 25  # was 24
```

```python
# Near B7_PRE_MIGRATION_EXPECTED_TABLES (~L217). Migration 0024 added only the
# nullable failure_mode COLUMN (no new tables), so the v24 table set == the B7 set.
PHASE16_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    B7_PRE_MIGRATION_EXPECTED_TABLES
)
```

```python
# Mirror _create_pre_b7_migration_backup (~L633) with the phase16 filename prefix.
def _create_pre_phase16_migration_backup(src_path: Path, *, dest_dir: Path) -> Path:
    """Phase 16 mirror. SQLite-native Connection.backup() before the 0025 migration.
    Backup file pattern ``swing-pre-phase16-migration-<ISO>.db``."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-phase16-migration-{timestamp}.db"
    src_conn = open_connection(src_path, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path
```

```python
# Mirror _b7_backup_gate (~L1023). STRICT current_version == 24.
def _phase16_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 16 backup-before-migrate gate (spec §5.3).

    Fires ONLY when ``current_version == 24 AND target_version >= 25`` -- a real
    production v24 DB about to cross v25 (migration 0025, pipeline_step_timings).
    STRICT EQUALITY on pre_version per the ``pre_version == (target - 1)`` gotcha
    (NOT ``<=``). Snapshots; does not BLOCK.
    """
    if target_version < 25 or current_version != 24:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-phase16 backup gate requires a file-backed source DB; in-memory "
            "connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase16_migration_backup(src_path, dest_dir=backup_dir)
        _verify_backup_integrity(
            backup_path, expected_tables=PHASE16_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-phase16 backup failed: {exc}"
        ) from exc
```

Wire it into `run_migrations`, immediately **after** the `_b7_backup_gate(...)` call:

```python
    _b7_backup_gate(
        conn, current_version=current,
        target_version=target_version, backup_dir=backup_dir,
    )
    _phase16_backup_gate(
        conn, current_version=current,
        target_version=target_version, backup_dir=backup_dir,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/data/test_migration_0025_phase16.py -q`
Expected: PASS.

- [ ] **Step 6: Run the broader migration/schema suite (regression)**

Run: `python -m pytest tests/data/ -q -k "migration or schema or backup"`
Expected: PASS — existing migration round-trip + backup-gate tests still green with v25 as the new
ceiling. The migrate-twice no-op and the runner's `executescript` + `commit`/`rollback` path (with FK
toggled OFF) are exercised through the real `run_migrations`/`_apply_migration` runner (spec §6.6).

- [ ] **Step 7: Commit**

```bash
git add swing/data/migrations/0025_phase16_pipeline_step_timings.sql swing/data/db.py tests/data/test_migration_0025_phase16.py
git commit -m "feat(data): add migration 0025 pipeline_step_timings with phase16 backup gate"
```

---

## Task 4: `StepTiming` dataclass + repo + mapper (ONE task, #11 atomicity, spec §5.5)

**Files:**
- Create: `swing/data/repos/pipeline_step_timings.py`
- Test: `tests/data/test_repos_pipeline_step_timings.py`

Read-path (`StepTiming` + `_row_to_step_timing` + `list_step_timings` + `step_durations_by_name`) and
write-path (`insert_step_timings`) land together. Depends on Task 3's table.

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_repos_pipeline_step_timings.py
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema
from swing.data.repos.pipeline_step_timings import (
    StepTiming,
    insert_step_timings,
    list_step_timings,
    step_durations_by_name,
)
from swing.pipeline.lease import acquire_lease


@pytest.fixture
def db_path(tmp_path):
    # ensure_schema migrates to EXPECTED_SCHEMA_VERSION (25).
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


@pytest.fixture
def conn(db_path):
    c = connect(db_path)  # same tmp_path → same DB file as db_path
    yield c
    c.close()


def _run_id(db_path) -> int:
    """Create a real pipeline_runs row via the production lease path (satisfies all
    NOT-NULL columns: data_asof_date, action_session_date, lease_token, ...)."""
    lease = acquire_lease(
        db_path=db_path, trigger="manual",
        data_asof_date="2026-06-08", action_session_date="2026-06-09",
        block_threshold_seconds=120,
    )
    return lease.run_id


def test_round_trip_preserves_order(conn, db_path):
    rid = _run_id(db_path)
    rows = [
        StepTiming(0, "finviz_fetch", "2026-06-09T00:00:00", "2026-06-09T00:00:01", 500),
        StepTiming(1, "weather", "2026-06-09T00:00:01", "2026-06-09T00:00:01", 200),
        StepTiming(2, "finviz_fetch", "2026-06-09T00:00:01", "2026-06-09T00:00:01", 30),
    ]
    with conn:
        insert_step_timings(conn, rid, rows)
    back = list_step_timings(conn, rid)
    assert [r.ordinal for r in back] == [0, 1, 2]
    assert back == rows


def test_durations_by_name_sums_repeated_step(conn, db_path):
    rid = _run_id(db_path)
    with conn:
        insert_step_timings(conn, rid, [
            StepTiming(0, "finviz_fetch", "t", "t", 500),
            StepTiming(1, "weather", "t", "t", 200),
            StepTiming(2, "finviz_fetch", "t", "t", 30),
        ])
    totals = step_durations_by_name(conn, rid)
    # CORRECT (SUM GROUP BY): finviz_fetch = 500 + 30 = 530.
    # NAIVE (one-row-per-name / last-wins): finviz_fetch = 30.  530 != 30 distinguishes.
    assert totals["finviz_fetch"] == 530
    assert totals["weather"] == 200
    assert list(totals) == ["finviz_fetch", "weather"]  # chronological by MIN(ordinal)


def test_idempotent_reinsert_on_conflict(conn, db_path):
    rid = _run_id(db_path)
    rows = [StepTiming(0, "evaluate", "t", "t", 10)]
    with conn:
        insert_step_timings(conn, rid, rows)
    with conn:
        insert_step_timings(conn, rid, rows)  # ON CONFLICT(run_id, ordinal) DO NOTHING
    assert len(list_step_timings(conn, rid)) == 1
```

> **Implementer note:** `_run_id` uses `acquire_lease` (the production path) to create the FK-parent
> `pipeline_runs` row, because that table has multiple NOT-NULL columns (`started_ts`, `trigger`,
> `data_asof_date`, `action_session_date`, `state`, `lease_token`) — a bare 3-column INSERT is
> rejected. Tests use `connect()` and the repo uses **positional** row access (`row[N]`), because
> `connect()`/`open_connection()` set **no** `row_factory` (rows are plain tuples) — matching the
> existing `swing/data/repos/pipeline.py` convention. Do NOT use `row["col"]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/data/test_repos_pipeline_step_timings.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'swing.data.repos.pipeline_step_timings'`.

- [ ] **Step 3: Write the repo module**

```python
# swing/data/repos/pipeline_step_timings.py
"""Repo for the pipeline_step_timings child table (Arc-1 spec §5.5).

(run_id, step_name) is NOT unique: finviz_fetch yields two rows. Consumers MUST
sum duration_ms grouped by step_name — step_durations_by_name does this so no
caller hand-rolls (and forgets) the aggregation.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class StepTiming:
    ordinal: int
    step_name: str
    started_ts: str
    finished_ts: str
    duration_ms: int


def _row_to_step_timing(row: tuple) -> StepTiming:
    # connect() sets NO row_factory → rows are tuples; positional access matches
    # the existing repo convention (swing/data/repos/pipeline.py uses row[N]).
    # Column order matches the SELECT in list_step_timings.
    return StepTiming(
        ordinal=row[0],
        step_name=row[1],
        started_ts=row[2],
        finished_ts=row[3],
        duration_ms=row[4],
    )


def insert_step_timings(
    conn: sqlite3.Connection, run_id: int, timings: Sequence[StepTiming],
) -> None:
    """Batch insert. ON CONFLICT(run_id, ordinal) DO NOTHING keeps the table
    append-only against a re-flush by a separate Lease/process for the same run."""
    conn.executemany(
        "INSERT INTO pipeline_step_timings "
        "(run_id, ordinal, step_name, started_ts, finished_ts, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, ordinal) DO NOTHING",
        [
            (run_id, t.ordinal, t.step_name, t.started_ts, t.finished_ts, t.duration_ms)
            for t in timings
        ],
    )


def list_step_timings(conn: sqlite3.Connection, run_id: int) -> list[StepTiming]:
    """Raw per-ordinal rows, chronological. Preserves the two finviz_fetch rows
    for forensic ordering. ORDER BY ordinal ASC is explicit (SQLite does not
    guarantee row order otherwise)."""
    cur = conn.execute(
        "SELECT ordinal, step_name, started_ts, finished_ts, duration_ms "
        "FROM pipeline_step_timings WHERE run_id = ? ORDER BY ordinal ASC",
        (run_id,),
    )
    return [_row_to_step_timing(r) for r in cur.fetchall()]


def step_durations_by_name(conn: sqlite3.Connection, run_id: int) -> dict[str, int]:
    """SUM(duration_ms) GROUP BY step_name, ordered by first appearance. The
    mandatory aggregator — do NOT assume one row per step_name."""
    cur = conn.execute(
        "SELECT step_name, SUM(duration_ms) AS total_ms "
        "FROM pipeline_step_timings WHERE run_id = ? "
        "GROUP BY step_name ORDER BY MIN(ordinal) ASC",
        (run_id,),
    )
    # Tuple rows (no row_factory): step_name=r[0], total_ms=r[1].
    return {r[0]: int(r[1]) for r in cur.fetchall()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/data/test_repos_pipeline_step_timings.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/pipeline_step_timings.py tests/data/test_repos_pipeline_step_timings.py
git commit -m "feat(data): add StepTiming repo with by-name duration aggregation"
```

---

## Task 5: `Lease` ledger + `lease.step()` close/open + log lines (spec §5.1/§5.4)

**Files:**
- Modify: `swing/pipeline/lease.py`
- Test: `tests/pipeline/test_lease_timings.py`

The ledger fields + `step()` boundary recording + the per-step `INFO` / `WARN` lines land here.
`flush_step_timings()` lands in Task 6 — so this task's tests inspect the ledger state
(`lease._timings`, `lease._pending`) directly (white-box) and assert the per-step log lines.

- [ ] **Step 1: Write the failing tests**

```python
# tests/pipeline/test_lease_timings.py
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.pipeline import lease as lease_mod
from swing.pipeline.lease import STEP_SOFT_BUDGET_MS, acquire_lease


@pytest.fixture
def fresh_lease(tmp_path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lz = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-06-08", action_session_date="2026-06-09",
        block_threshold_seconds=120,
    )
    yield lz


@pytest.fixture
def fake_clock(monkeypatch):
    ticks = iter([])

    def install(values):
        nonlocal ticks
        ticks = iter(values)
        monkeypatch.setattr(lease_mod, "_monotonic", lambda: next(ticks))

    return install


def test_durations_distinguish_fast_and_slow(fresh_lease, fake_clock):
    # One _monotonic() call per step(). t0=1000.0, t1=1000.5, t2=1003.5.
    fake_clock([1000.0, 1000.5, 1003.5])
    fresh_lease.step("fast")   # opens fast @ t0
    fresh_lease.step("slow")   # closes fast (dur=(t1-t0)*1000=500), opens slow @ t1
    fresh_lease.step("end")    # closes slow (dur=(t2-t1)*1000=3000), opens end @ t2
    closed = fresh_lease._timings
    assert [t.step_name for t in closed] == ["fast", "slow"]
    assert closed[0].duration_ms == 500
    assert closed[1].duration_ms == 3000
    # Discriminator: a naive last-wins/overwrite impl records no closed list →
    # closed == [] → the slice assertion fails. CORRECT keeps both intervals.
    assert closed[1].duration_ms > closed[0].duration_ms


def test_inbox_empty_sequence_ordinals_and_aggregation(fresh_lease, fake_clock):
    # The REAL inbox-empty order from runner.py: finviz_fetch(634) -> weather(723)
    # -> finviz_fetch(758, skip) -> evaluate(817). weather sits BETWEEN the two
    # finviz_fetch calls — NOT a synthetic two-in-a-row.
    fake_clock([0.0, 0.5, 0.7, 0.73])  # 4 step() calls
    for name in ["finviz_fetch", "weather", "finviz_fetch", "evaluate"]:
        fresh_lease.step(name)
    closed = fresh_lease._timings  # evaluate still pending → 3 closed
    assert [(t.ordinal, t.step_name) for t in closed] == [
        (0, "finviz_fetch"), (1, "weather"), (2, "finviz_fetch"),
    ]
    totals = lease_mod._aggregate_by_name(closed)
    # finviz_fetch = (500) + (30) = 530; weather = 200.
    assert totals["finviz_fetch"] == closed[0].duration_ms + closed[2].duration_ms
    assert set(totals) == {"finviz_fetch", "weather"}


def test_inbox_nonempty_sequence_single_finviz(fresh_lease, fake_clock):
    # Non-empty path: site-1 never fires → weather(723, ord 0) -> finviz_fetch(758,
    # ord 1) -> evaluate. Proves ordinals are path-dependent.
    fake_clock([0.0, 0.5, 0.7])
    for name in ["weather", "finviz_fetch", "evaluate"]:
        fresh_lease.step(name)
    closed = fresh_lease._timings
    assert [(t.ordinal, t.step_name) for t in closed] == [
        (0, "weather"), (1, "finviz_fetch"),
    ]
    assert sum(1 for t in closed if t.step_name == "finviz_fetch") == 1


def test_soft_budget_warns_only_over_threshold(fresh_lease, fake_clock, caplog):
    over = STEP_SOFT_BUDGET_MS / 1000.0 + 1.0  # seconds; > budget
    fake_clock([0.0, over, over + 0.001])
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.lease"):
        fresh_lease.step("charts")   # opens
        fresh_lease.step("export")   # closes charts (over budget) -> WARN
        fresh_lease.step("complete")  # closes export (~1ms) -> no WARN
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("name=charts" in r.getMessage() for r in warns)
    assert not any("name=export" in r.getMessage() for r in warns)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/pipeline/test_lease_timings.py -q`
Expected: FAIL — `ImportError: cannot import name 'STEP_SOFT_BUDGET_MS'` /
`AttributeError: 'Lease' object has no attribute '_timings'`.

- [ ] **Step 3: Add ledger state, clock, constants, and helpers to `lease.py`**

`lease.py` already has `from __future__ import annotations` (line 2) and `from dataclasses import
dataclass` (line 6) — change that to `from dataclasses import dataclass, field` and add `import
logging`, `import time`, `import contextlib` to the import block. Add `from
swing.data.repos.pipeline_step_timings import StepTiming, insert_step_timings` (no import cycle:
`pipeline_step_timings` imports nothing from `swing.pipeline`). Define the module-level helpers and
`_PendingStep` **above** the `Lease` class (line 36) so they are in scope; the `field(...)`
annotations resolve lazily via the future-import regardless.

Add imports + module-level helpers near the top of [`swing/pipeline/lease.py`](../../../swing/pipeline/lease.py):

```python
import logging
import time
from dataclasses import dataclass, field

from swing.data.repos.pipeline_step_timings import StepTiming

log = logging.getLogger(__name__)

# Advisory soft budget (spec §5.4) — WARN only, never a control-flow gate.
# Defaults to the existing charts 60s shape; a constant, so per-step budgets can
# be tuned later without schema churn.
STEP_SOFT_BUDGET_MS = 60_000


def _monotonic() -> float:
    """Indirection so tests can stub a deterministic clock (mirrors _now_iso)."""
    return time.monotonic()


@dataclass(frozen=True)
class _PendingStep:
    ordinal: int
    step_name: str
    started_ts: str
    monotonic_start: float


def _aggregate_by_name(timings) -> dict[str, int]:
    """In-memory SUM(duration_ms) GROUP BY step_name, first-appearance order.
    Mirrors the repo's step_durations_by_name for the flush summary line (the
    ledger is summarized BEFORE the DB write)."""
    totals: dict[str, int] = {}
    for t in timings:
        totals[t.step_name] = totals.get(t.step_name, 0) + t.duration_ms
    return totals


def _emit_step_line(t: StepTiming) -> None:
    log.info("step ordinal=%d name=%s took %d ms", t.ordinal, t.step_name, t.duration_ms)
    if t.duration_ms > STEP_SOFT_BUDGET_MS:
        log.warning(
            "step ordinal=%d name=%s exceeded soft budget: %d ms > %d ms",
            t.ordinal, t.step_name, t.duration_ms, STEP_SOFT_BUDGET_MS,
        )


def _emit_totals_line(totals: dict[str, int]) -> None:
    parts = " ".join(f"{name}={ms}ms" for name, ms in totals.items())
    log.info("step totals: %s", parts)
```

Add the ledger fields to the `Lease` dataclass (after the existing `token` field). `init=False`
keeps every `Lease(...)` construction site unchanged and guarantees the ledger always exists:

```python
@dataclass
class Lease:
    db_path: Path
    run_id: int
    token: str
    _timings: list[StepTiming] = field(default_factory=list, init=False, repr=False)
    _pending: _PendingStep | None = field(default=None, init=False, repr=False)
    _next_ordinal: int = field(default=0, init=False, repr=False)
    _timings_flushed: bool = field(default=False, init=False, repr=False)
```

Extend `step()` to record the boundary AFTER its existing (unchanged) `update_step` write:

```python
    def step(self, name: str) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                update_step(
                    conn, run_id=self.run_id, lease_token=self.token,
                    step=name, progress_ts=_now_iso(),
                )
        finally:
            conn.close()
        self._record_step_boundary(name)

    def _record_step_boundary(self, name: str) -> None:
        now_mono = _monotonic()
        if self._pending is not None:
            closed = self._close_pending(now_mono)
            _emit_step_line(closed)
        self._pending = _PendingStep(
            ordinal=self._next_ordinal, step_name=name,
            started_ts=_now_iso(), monotonic_start=now_mono,
        )
        self._next_ordinal += 1

    def _close_pending(self, now_mono: float) -> StepTiming:
        p = self._pending
        timing = StepTiming(
            ordinal=p.ordinal, step_name=p.step_name,
            started_ts=p.started_ts, finished_ts=_now_iso(),
            duration_ms=int((now_mono - p.monotonic_start) * 1000),  # truncate, not round
        )
        self._timings.append(timing)
        self._pending = None
        return timing
```

> **Boundary-recording order (binding):** the ledger op runs **after** `update_step`. If a revoked
> `step()` raises `LeaseRevokedError` from `update_step`, the prior `_pending` stays open and is closed
> at flush (its duration then runs to flush) — the prior step is still recorded; the new (never-run)
> step opens no entry. This is the correct boundary-interval semantic; do not move the ledger op before
> `update_step` (that would open a spurious entry for a step whose work never ran).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_lease_timings.py -q`
Expected: PASS.

- [ ] **Step 5: Run the existing lease suite (regression)**

Run: `python -m pytest tests/pipeline/test_lease.py -q`
Expected: PASS — acquire/release/concurrent behavior unchanged (ledger is additive, `init=False`).

- [ ] **Step 6: Commit**

```bash
git add swing/pipeline/lease.py tests/pipeline/test_lease_timings.py
git commit -m "feat(pipeline): record per-step monotonic timings on the Lease ledger"
```

---

## Task 6: `flush_step_timings()` + the `run_pipeline_internal` finally call (spec §5.2/§5.4)

> Note: the spec/brief say "`run()`'s finally"; the actual function is **`run_pipeline_internal`**
> (def [`runner.py:531`](../../../swing/pipeline/runner.py), finally [`runner.py:1034`]). `run_pipeline`
> (the CLI/web entry) wraps it; the lease + flush live in `run_pipeline_internal`.

**Files:**
- Modify: `swing/pipeline/lease.py` (add `flush_step_timings`)
- Modify: `swing/pipeline/runner.py:1034` (call it in `run_pipeline_internal`'s `finally`)
- Test: `tests/pipeline/test_lease_flush.py`, `tests/pipeline/test_runner_step_timings.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pipeline/test_lease_flush.py
from __future__ import annotations

import contextlib
import logging
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema
from swing.data.repos.pipeline import force_clear
from swing.data.repos.pipeline_step_timings import (
    list_step_timings, step_durations_by_name,
)
from swing.pipeline import lease as lease_mod
from swing.pipeline.lease import acquire_lease


@pytest.fixture
def fake_clock(monkeypatch):
    def install(values):
        it = iter(values)
        monkeypatch.setattr(lease_mod, "_monotonic", lambda: next(it))
    return install


def _lease(tmp_path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db, acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-06-08", action_session_date="2026-06-09",
        block_threshold_seconds=120,
    )


def test_flush_persists_all_rows_and_closes_final_pending(tmp_path, fake_clock):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 0.7, 0.73, 1.0])  # 4 step()s + 1 flush close
    for name in ["finviz_fetch", "weather", "finviz_fetch", "evaluate"]:
        lz.step(name)
    lz.flush_step_timings()  # closes evaluate (ordinal 3), persists all 4
    with contextlib.closing(connect(db)) as conn:
        rows = list_step_timings(conn, lz.run_id)
        assert [r.ordinal for r in rows] == [0, 1, 2, 3]
        assert step_durations_by_name(conn, lz.run_id)["finviz_fetch"] == (
            rows[0].duration_ms + rows[2].duration_ms
        )


def test_persisted_durations_distinguish_fast_and_slow(tmp_path, fake_clock):
    # spec §6.2: the PERSISTED duration_ms must distinguish fast vs slow — not just
    # the in-memory ledger (Task 5). Monotonic stub: fast=500ms, slow=3000ms.
    db, lz = _lease(tmp_path)
    fake_clock([1000.0, 1000.5, 1003.5, 1003.6])  # 3 step()s + 1 flush close
    lz.step("fast")   # opens fast @1000.0
    lz.step("slow")   # closes fast (500ms), opens slow @1000.5
    lz.step("end")    # closes slow (3000ms), opens end @1003.5
    lz.flush_step_timings()  # closes end (100ms), persists all 3
    with contextlib.closing(connect(db)) as conn:
        rows = {r.step_name: r.duration_ms for r in list_step_timings(conn, lz.run_id)}
    # CORRECT: fast=500, slow=3000 persisted distinctly. NAIVE (last-wins/overwrite
    # at persist): would collapse to one row → KeyError or equal values. 3000 > 500.
    assert rows["fast"] == 500
    assert rows["slow"] == 3000
    assert rows["slow"] > rows["fast"]


def test_flush_emits_summary_and_per_step_lines(tmp_path, fake_clock, caplog):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 1.0])
    # caplog MUST wrap the step() calls too: the `evaluate` per-step line is
    # emitted DURING step("charts") (which closes evaluate), before flush. Only
    # the final `charts` line + the summary are emitted inside flush.
    with caplog.at_level(logging.INFO, logger="swing.pipeline.lease"):
        for name in ["evaluate", "charts"]:
            lz.step(name)
        lz.flush_step_timings()
    msgs = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("step totals:") for m in msgs)  # summary present
    assert any("name=evaluate" in m for m in msgs)          # per-step line (during step)
    assert any("name=charts" in m for m in msgs)            # per-step line (during flush)


def test_flush_failure_degrades_cleanly(tmp_path, fake_clock, caplog, monkeypatch):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 1.0])

    def boom(*a, **k):
        raise RuntimeError("db locked")

    monkeypatch.setattr(lease_mod, "insert_step_timings", boom)
    runner_log = logging.getLogger("swing.pipeline.runner")
    # caplog MUST wrap the step() calls: the `evaluate` per-step line is emitted
    # during step("charts"); the `charts` line + summary are emitted inside flush
    # BEFORE the failing insert. All must survive (spec §6.4b: per-step lines AND
    # the aggregate summary are the durable fallback when the DB write fails).
    with caplog.at_level(logging.INFO):
        for name in ["evaluate", "charts"]:
            lz.step(name)
        try:
            lz.flush_step_timings()
        except Exception as exc:  # mirror the runner finally's swallow + log
            runner_log.error("step-timing flush failed: %s", exc)
    msgs = [r.getMessage() for r in caplog.records]
    # (b) error logged
    assert any("flush failed" in m for m in msgs)
    # (d) per-step lines survive (already-closed `evaluate` + final-pending `charts`)
    assert any("name=evaluate" in m for m in msgs)
    assert any("name=charts" in m for m in msgs)
    # (e) the aggregate summary survives (emitted before the fallible DB write)
    assert any(m.startswith("step totals:") for m in msgs)
    # (a) outcome unaffected; _timings_flushed stays False (set only AFTER commit) →
    # a later retry is still possible (the in-memory ledger still holds the rows).
    assert lz._timings_flushed is False


def test_flush_idempotent_after_success(tmp_path, fake_clock):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 1.0])
    for name in ["evaluate", "charts"]:
        lz.step(name)
    lz.flush_step_timings()
    assert lz._timings_flushed is True
    lz.flush_step_timings()  # second call: guard short-circuits, no dup rows
    with contextlib.closing(connect(db)) as conn:
        assert len(list_step_timings(conn, lz.run_id)) == 2


def test_flush_after_force_clear_uses_fresh_connection(tmp_path, fake_clock):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 1.0])
    lz.step("evaluate")
    lz.step("charts")
    # Revoke the lease (sets state='force_cleared'; row survives). force_clear does
    # NOT self-commit → wrap in `with conn:` (transaction); closing() ensures the
    # connection is also closed (sqlite3's CM commits but does not close).
    with contextlib.closing(connect(db)) as conn:
        with conn:
            force_clear(conn, run_id=lz.run_id, error_message="operator force-clear")
    lz.flush_step_timings()  # fresh connect(), no token needed
    with contextlib.closing(connect(db)) as conn:
        assert len(list_step_timings(conn, lz.run_id)) >= 1
```

> **Implementer notes:** `force_clear(conn, *, run_id, error_message)` (verified at plan time at
> [`pipeline.py:137`](../../../swing/data/repos/pipeline.py)) sets `state='force_cleared'` without
> deleting the row and does NOT take a `lease_token` (the lease is being revoked); it does not
> self-commit, so wrap the call in `with conn:`. The empty-inbox **end-to-end** persistence assertion
> (two
> `finviz_fetch` rows at ordinals 0/2) is best added by extending
> `tests/pipeline/test_run_pipeline_internal_empty_finviz_inbox_auto_fetch.py` to read
> `list_step_timings(conn, run_id)` after the run — add that assertion if the existing harness drives
> `run()` to completion; otherwise the Task-5 Lease-replay + this flush round-trip are the binding
> production-shaped coverage.

**Also add runner-shaped terminal-state tests (spec §6.4 — the REAL `run_pipeline_internal` finally
path, not a direct `flush_step_timings()` call).** These prove the `finally` wiring (Step 4) persists
timings end-to-end on the complete / failed / force_cleared paths. Model them on the existing
harnesses in [`tests/pipeline/test_runner.py`](../../../tests/pipeline/test_runner.py):
`test_runner_completes_all_steps`, `test_runner_aborts_on_evaluation_fail`, and
`test_runner_detects_mid_run_lease_revocation`.

```python
# tests/pipeline/test_runner_step_timings.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from swing.config import load
from swing.data.db import ensure_schema
from swing.data.repos.pipeline_step_timings import list_step_timings, step_durations_by_name
from swing.pipeline.runner import run_pipeline_internal
from tests.cli.test_cli_eval import _minimal_config


def _ohlcv(end="2026-04-15"):
    closes = [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def _setup_cfg(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = load(_minimal_config(project, home))
    ensure_schema(cfg.paths.db_path).close()
    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    cols = ("No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
            "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap")
    (inbox / "finviz15Apr2026.csv").write_text(
        cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
        encoding="utf-8",
    )
    return cfg


def test_run_persists_timings_on_complete(tmp_path, monkeypatch):
    cfg = _setup_cfg(tmp_path)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"
    conn = sqlite3.connect(cfg.paths.db_path)  # tuple rows → positional repo OK
    try:
        rows = list_step_timings(conn, result.run_id)
        assert len(rows) >= 2  # the finally flushed the real ledger
        # ordinals are unique + monotonic from 0
        assert [r.ordinal for r in rows] == list(range(len(rows)))
        # _setup_cfg writes a CSV → this is the NON-empty path: site-1 never fires,
        # so finviz_fetch appears EXACTLY once (weather then finviz_fetch). Discriminating:
        # a naive last-wins persist or a dropped-row bug breaks the count/sum equality.
        names = [r.step_name for r in rows]
        assert names.count("finviz_fetch") == 1
        assert "weather" in names
        totals = step_durations_by_name(conn, result.run_id)
        assert totals["finviz_fetch"] == sum(
            r.duration_ms for r in rows if r.step_name == "finviz_fetch"
        )
    finally:
        conn.close()


def test_run_persists_partial_timings_on_failed(tmp_path, monkeypatch):
    cfg = _setup_cfg(tmp_path)

    def fail_get(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "QQQ":
            return _ohlcv()
        raise RuntimeError("simulated yfinance outage")  # evaluation aborts

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fail_get)
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "failed"
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rows = list_step_timings(conn, result.run_id)
        assert len(rows) >= 1  # partial timings persisted via the finally flush
    finally:
        conn.close()
```

```python
# tests/pipeline/test_runner_step_timings.py  (continued — MANDATORY, not optional)
def test_run_persists_timings_on_force_clear(tmp_path, monkeypatch):
    """spec §6.4 force_cleared mid-step: timings persist via the flush's fresh
    connect() despite the revoked lease. Mirrors test_runner.py's
    test_runner_detects_mid_run_lease_revocation revocation mechanism."""
    import sqlite3
    from swing.data.repos.pipeline import force_clear

    cfg = _setup_cfg(tmp_path)
    cleared = {"done": False}

    def fetcher_get(self, ticker, lookback_days, *, as_of_date=None):
        # First OHLCV fetch → force-clear the running lease (admin revoke between
        # step boundaries), then return normally so the step body proceeds toward
        # the LeaseRevokedError on its next write.
        if not cleared["done"]:
            conn = sqlite3.connect(cfg.paths.db_path)
            try:
                row = conn.execute(
                    "SELECT id FROM pipeline_runs WHERE state='running'"
                ).fetchone()
                if row is not None:
                    with conn:
                        force_clear(conn, run_id=row[0], error_message="test-revoke")
                    cleared["done"] = True
            finally:
                conn.close()
        return _ohlcv()

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fetcher_get)
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "force_cleared"
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        # Partial timings persisted by the finally flush via a FRESH connect()
        # (no lease token needed); the force_cleared pipeline_runs row survives.
        assert len(list_step_timings(conn, result.run_id)) >= 1
    finally:
        conn.close()


def test_run_survives_flush_failure(tmp_path, monkeypatch, caplog):
    """spec §6.4b at the REAL finally boundary: if flush raises, run_pipeline_internal
    swallows + logs it and the RunResult is unchanged. This catches a runner that
    forgot the try/except (the lease-level test cannot — it mirrors the wrapper by
    hand)."""
    import logging as _logging

    from swing.pipeline.lease import Lease

    cfg = _setup_cfg(tmp_path)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    def boom(self):
        raise RuntimeError("flush exploded")

    monkeypatch.setattr(Lease, "flush_step_timings", boom)
    with caplog.at_level(_logging.ERROR, logger="swing.pipeline.runner"):
        result = run_pipeline_internal(cfg=cfg, trigger="manual")
    # (a) outcome unchanged — flush failure does not flip a complete run to failed.
    assert result.state == "complete"
    # (b) the runner's finally logged the flush error (proves the try/except exists).
    assert any("flush failed" in r.getMessage() for r in caplog.records)
```

> **Why the runner-level flush-failure test is required (R3 Codex):** the lease-level
> `test_flush_failure_degrades_cleanly` hand-mirrors the runner's `try/except`, so it would pass even
> if `run_pipeline_internal`'s `finally` forgot to wrap the flush. This test monkeypatches
> `Lease.flush_step_timings` to raise and drives the REAL finally — if the wrapper is missing, the
> exception masks the `complete` outcome (or propagates) and the test fails. Keep BOTH tests.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/pipeline/test_lease_flush.py tests/pipeline/test_runner_step_timings.py -q`
Expected: FAIL — `AttributeError: 'Lease' object has no attribute 'flush_step_timings'` (lease-level)
and the runner-shaped tests find zero persisted timing rows (the `finally` flush call is not wired yet).

- [ ] **Step 3: Add `flush_step_timings()` to `Lease`**

Add the `insert_step_timings` import to `lease.py`'s top imports
(`from swing.data.repos.pipeline_step_timings import StepTiming, insert_step_timings`) and `import
contextlib`. Then:

```python
    def flush_step_timings(self) -> None:
        """Flush the ledger ONCE, from run()'s finally. Sequence is load-bearing:
        (1) close the final pending; (2) emit the final per-step line + the
        aggregate-by-name summary BEFORE any DB write (so both survive a DB
        failure); (3) one batch transaction on a fresh connect(). The flush-once
        guard is set True ONLY after commit, so a transient failure does not
        disable a later retry while the in-memory ledger still holds the data."""
        if self._timings_flushed:
            return
        if self._pending is not None:
            _emit_step_line(self._close_pending(_monotonic()))
        if not self._timings:
            return  # empty ledger (run never called step()) → no-op
        _emit_totals_line(_aggregate_by_name(self._timings))
        with contextlib.closing(connect(self.db_path)) as conn:
            with conn:
                insert_step_timings(conn, self.run_id, self._timings)
        self._timings_flushed = True
```

- [ ] **Step 4: Call it from `run_pipeline_internal`'s `finally`**

Modify the `finally` at [`swing/pipeline/runner.py:1034`](../../../swing/pipeline/runner.py) (inside
`run_pipeline_internal`, def at L531). `lease` is always bound here (see Resolved decision #3). Wrap so
a flush failure never re-raises from the `finally` (cannot mask an in-flight exception) and never
blocks finalization:

```python
    finally:
        hb.stop()
        try:
            lease.flush_step_timings()
        except Exception as exc:
            log.error("step-timing flush failed: %s", exc)
        # OQ-C: close the single shared serialized audit-writer connection.
        if audit_conn is not None:
            audit_conn.close()
```

> **Invariant to preserve (spec §5.2):** `lease` is bound because `acquire_lease`'s
> `ConcurrentRunBlockedError` early-returns at L572 — before the big `try`/`finally` (L586/L1034). If
> any future refactor moves `acquire_lease` inside the big `try`, add a `lease = None` sentinel before
> the `try` and guard the flush with `if lease is not None:`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_lease_flush.py tests/pipeline/test_runner_step_timings.py tests/pipeline/test_lease.py tests/pipeline/test_lease_timings.py -q`
Expected: PASS.

- [ ] **Step 6: Run the terminal-state / recovery suite (regression, spec §6.4)**

Run: `python -m pytest tests/pipeline/test_recovery.py tests/pipeline/test_runner.py -q`
Expected: PASS — `failed` / `force_cleared` / exception runs still finalize correctly; the flush in
the `finally` does not alter `RunResult`.

- [ ] **Step 7: Commit**

```bash
git add swing/pipeline/lease.py swing/pipeline/runner.py tests/pipeline/test_lease_flush.py tests/pipeline/test_runner_step_timings.py
git commit -m "feat(pipeline): flush step timings once at run finalize"
```

---

## Task 7: Full suite + ruff + Windows encoding (spec §6.8)

**Files:**
- Test: `tests/test_logging_config.py` (append an encoding assertion)

- [ ] **Step 1: Add the ASCII / utf-8 guard test**

> **Imports:** `tests/test_logging_config.py` already imports `logging` and
> `from logging.handlers import TimedRotatingFileHandler` at the top (added in Task 1). Add ONLY the new
> top-level import `from swing.pipeline import lease as lease_mod` — do NOT re-import `logging` /
> `TimedRotatingFileHandler` (ruff F811/F401).

```python
# tests/test_logging_config.py  (append — new top import: `from swing.pipeline import lease as lease_mod`)
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
        if isinstance(x, TimedRotatingFileHandler)
        and x.baseFilename == str(tmp_path / "pipeline.log")
    )
    assert h.encoding == "utf-8"
```

- [ ] **Step 2: Run the new guards**

Run: `python -m pytest tests/test_logging_config.py -q`
Expected: PASS.

- [ ] **Step 3: Run ruff**

Run: `ruff check swing/`
Expected: clean (no new findings). Fix any import-order / unused-import issues in the touched files.

- [ ] **Step 4: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: green. **If any of the 3 known xdist co-residency flakes appear** (the
`pattern_cohort` / `double_bottom_w` / `w_bottom` L2-reinforcement identity tests — CLAUDE.md
§Windows/tooling), re-run the affected file(s) with `-n0` to confirm they pass in isolation; they are
pre-existing and unrelated to this arc.

- [ ] **Step 5: Commit**

```bash
git add tests/test_logging_config.py
git commit -m "test(pipeline): full-suite plus ruff and encoding verification for observability arc"
```

---

## Locks / invariants (propagate; do not regress)

- **Schema v24 → v25** — the single schema touch; `0025` carries explicit `BEGIN; ... COMMIT;` +
  `UPDATE schema_version SET version = 25;` (gotcha #9 / `0023`-`0024` convention; per the AMENDED spec
  §5.3 — `_apply_migration` runs `executescript` in autocommit and supplies only the FK toggle +
  `rollback()`); backup
  gate STRICT `current_version == 24`; migrate-twice no-op. DB stays OUTSIDE the Drive dir;
  `busy_timeout` unchanged.
- **Phase isolation** — change loci exactly as the file map. `swing/web/routes/pipeline.py`
  UNCHANGED (DEVNULL kept). **`swing/trades/` stays read-only.**
- **Redaction is two belts** — Belt A (factory) installed in `pipeline_run_cmd` BEFORE any handler
  attach/emit; Belt B (`RedactingFormatter`) set on the handler BEFORE it joins root (no unredacted
  window). `configure_logging` imports nothing from `swing.integrations.schwab`.
- **No new per-step lock-contention point** — timing persistence is ONE batch transaction at finalize
  on a fresh `connect()` (respects the `database is locked` deadlock scars + the single-transaction
  `BEGIN IMMEDIATE` contract). The per-`step()` ledger op is in-memory only.
- **Corrected timing semantic** — `ordinal` = unique monotonic ordering key; `step_name` = non-unique
  aggregation key (`finviz_fetch` yields two rows); consumers `SUM(duration_ms) GROUP BY step_name`
  (`step_durations_by_name`). No "strictly linear" assumption; no consecutive-collapse rule.
- **`complete` is a real boundary** — its duration measures genuine post-`export` finalization; do NOT
  special-case or drop it.

## Out of scope / banked

- **Arc 2** — centralized config beyond the seam, retention/cleanup of the logs dir, the `level` knob
  beyond the existing param, log-volume right-sizing, web↔subprocess correlation. `level` exists but
  is NOT wired to a knob here.
- **1c** (yfinance call-timing audit) and the **performance fix** (cap/parallelize/cache yfinance) —
  deferred; gated on the data THIS arc produces.
- **Arc 3** (XMAX thumbnail), **Arc 4** (equity reconciliation). No change to Schwab call LOGIC —
  only its log-surface coverage.

## Self-review (against the spec)

- **Spec coverage:** §4.1 seam → Task 1; §4.2 two-belt redaction + CLI wiring → Task 2; §5.3
  migration + backup gate → Task 3; §5.5 repo/dataclass/aggregator → Task 4; §5.1/§5.4 ledger +
  per-step/WARN lines → Task 5; §5.2 single flush + finally + summary-before-write + terminal/force-
  clear/flush-failure → Task 6; §4.3/§6.8 encoding + ruff + full suite → Task 7. §6 test contracts:
  6.1→T2, 6.2→T5, 6.3/6.3b→T5 (+T6 e2e), 6.4/6.4b/6.4c→T6 (6.4c also T4), 6.5→T2, 6.6→T3, 6.7→T1,
  6.8→T7.
- **Deferred decisions (§3):** soft-budget constant (T5), repo home (T4), single-flush-entry +
  ledger-on-Lease (T6 + Resolved #3), `complete`-boundary note (Resolved #4) — all resolved above.
- **Type consistency:** `StepTiming(ordinal, step_name, started_ts, finished_ts, duration_ms)` (no
  `run_id`; supplied to `insert_step_timings(conn, run_id, timings)`) is used identically in T4/T5/T6;
  `_PendingStep`, `_monotonic`, `STEP_SOFT_BUDGET_MS`, `_aggregate_by_name`, `_emit_step_line`,
  `_emit_totals_line`, `flush_step_timings`, `_close_pending`, `_record_step_boundary` names match
  across tasks; `configure_logging(logs_dir, *, surface, level, formatter)` + `DEFAULT_LOG_FORMAT`
  consistent T1/T2/T7.
