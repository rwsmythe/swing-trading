# Phase 16 / Arc 2 — Logging-System Overhaul: Design Spec

**Date:** 2026-06-09
**Cycle:** copowers:brainstorming (this doc = the LOCKED, Codex-converged design)
**Branch:** `arc2-logging-overhaul` (worktree from main HEAD `96750df2`)
**Schema:** **NONE — v25 holds.** No DB table is added (see §8).
**Scope:** All six Arc-2 sub-items (2a-2f) designed as one system; built across **two** writing-plans/executing cycles (§7 sequencing).

---

## 1. Mandate

Replace today's per-surface ad-hoc logging setup with one centralized, configurable, redaction-safe, retention-bounded logging system across **web + CLI + pipeline**, built on Arc 1's `swing/logging_config.py:configure_logging` seam. The system must:

- route every surface through a single composition root so redaction is **by construction** (2a, 2c);
- **bound** the logs dir by size (the 225 MB dir is the live disk pain) via size-based rotation + retention (2b);
- thread a **run/request correlation id** through the spawned pipeline subprocess (2d);
- expose a **config-driven level knob** + per-logger overrides (2f);
- **right-size volume** — primarily by stopping the pytest suite leaking into the operator's real log (2e).

This is the **completion** of the Arc-1 seam, not a rewrite of it.

---

## 2. Grounded current state (verified on HEAD `96750df2`)

- **Seam:** `swing/logging_config.py:configure_logging(logs_dir, *, surface, level=INFO, formatter=None)` attaches a `TimedRotatingFileHandler(when="D", interval=1, backupCount=7, encoding="utf-8")` writing `{surface}.log` to root. Idempotent (dedup by `baseFilename`). Sets `root.setLevel(level)` on **every** path (incl. dedup). Sets the formatter **before** adding the handler to root (no unredacted window). `surface in {web, pipeline}` today; `level` param exists but is wired to no config knob. Schwab-agnostic by construction (imports nothing from `swing.integrations.schwab`).
- **Web wiring:** `swing/web/middleware/request_id.py:configure_web_logging(logs_dir)` is a thin shim calling `configure_logging(surface="web")` with **no formatter** → web.log is **not** redaction-covered today. `app.py:441` calls it. `RequestIdMiddleware` stamps a `uuid4` `request.state.request_id`, sets `X-Request-ID`, and emits a `swing.web.access` INFO line per request.
- **Pipeline wiring:** `cli.py` `pipeline_run_cmd` (~3220) hand-wires Belt A (`ensure_schwab_log_redaction_factory_installed()`) + Belt B (`configure_logging(surface="pipeline", formatter=RedactingFormatter(DEFAULT_LOG_FORMAT))`).
- **Redaction belts** (`swing/integrations/schwab/client.py`): **Belt A** = process-global `logging.setLogRecordFactory` wrapper (`ensure_schwab_log_redaction_factory_installed`) that redacts records whose name starts with `"Schwabdev"` (capital S); **Belt B** = `RedactingFormatter` (full-line redactor, rebuilt from `_GLOBAL_KNOWN_SECRETS` on every `format()` call). Both read the global secret registry; Layer-0 exact-replace + Layer-1 hex32+/b64-24+ heuristics. Belt B is attached **only** to the pipeline.log handler today.
- **Subprocess spawn** (`swing/web/routes/pipeline.py`): `subprocess.Popen([sys.executable, "-m", "swing.cli", "--config", <path>, "pipeline", "run", "--manual"], stdout=DEVNULL, stderr=DEVNULL)`. **No correlation id** threaded to the subprocess. The web knows its `request_id`; the subprocess later acquires `pipeline_runs.id` via the lease.
- **finviz transport suppression** (`swing/integrations/finviz_api.py`): `_suppress_transport_debug_logs()` context manager forces `urllib3.connectionpool` + `requests.packages.urllib3.connectionpool` to WARNING during `fetch_screen()` because those loggers emit the full request URL (with `auth=<token>`) at DEBUG. This is a **security** belt (token-in-URL), not a noise control.
- **Config:** `[paths] logs_dir = "swing-data/logs"` resolved via `_resolve_path(p["logs_dir"], home, project_root)` against `$USERPROFILE`/`$HOME`. No `[logging]` section exists.

### 2.1 Live disk-state findings (orchestrator-measured 2026-06-09)

`~/swing-data/logs/` ≈ **230 MB**: `pipeline.log` (4 KB, Arc-1), `web.log` (**58 MB**, current), `web.log.2026-05-06` (**83 MB**), `web.log.2026-05-23` (**97 MB**), + 4 smaller dated files. **No `cli.log`.**

**OQ-2 resolved (why `backupCount=7` did NOT bound the dir):** `backupCount` bounds **file count, not size**. The dir holds 6 dated backups + current = *within* the cap of 7. Each daily file independently ballooned to 83-97 MB because `TimedRotatingFileHandler` has **no size ceiling**. Rollovers are also infrequent (the web server runs per-session, not as a midnight-spanning daemon), so calendar-day gaps appear and old large files linger until an 8th rollover would prune them. A count-only cap can never bound a single chatty day → a **size dimension is mandatory**.

**OQ-7 resolved (what fills `web.log` — 58 MB / 517 K lines, sampled):**
1. **Test-suite leakage into the operator's real `web.log`** — 33.6 K `httpx: HTTP Request: GET http://testserver/...` lines + synthetic tracebacks (`RuntimeError: synthetic boom`, `htmx boom`). The pytest suite writes to `~/swing-data/logs/` because the relative `logs_dir` resolves against the **un-monkeypatched real `$USERPROFILE`** (same family as the `write_user_overrides` USERPROFILE/HOME leak gotcha). **This is the dominant contributor and a genuine bug** — addressed by 2e in Slice 1.
2. **`httpx` INFO per-request** — the library logs every outbound HTTP call (yfinance/Schwab) at INFO.
3. **`yfinance` ERROR + "Failed download"** spam (~13 K lines).
4. **`swing.web.access`** INFO per request (34.5 K — legitimate access log; retained).
5. **Recurring multi-line tracebacks** from handled exceptions (reconciliation-backfill `SchwabAuthError` WARNINGs, etc.).

**Scope decision (Callout B):** the only 2e *action* in this arc is the **test-leak fix** (item 1). Items 2-3 are real production noise but are left to the operator via the Slice-2 per-logger override table (`[logging.loggers]`) — **the lever is built, the policy is not imposed**. The retention cap (2b) bounds disk regardless. Item 5 (a reconciliation-backfill traceback demotion) would touch `swing/trades/` and was **explicitly not selected** — the read-only lock stays clean.

---

## 3. Architecture — seam vs composition root

The central design move separates the **Schwab-agnostic seam** from a new **composition root** that does the wiring.

### 3.1 The seam — `swing/logging_config.py:configure_logging` (extended, still Schwab-agnostic)

Stays the low-level primitive. Changes are **additive injection** + the rotation-handler switch:

```python
def configure_logging(
    logs_dir: Path,
    *,
    surface: str,                                   # {"web","pipeline","cli"}
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    install_record_factory: Callable[[], None] | None = None,  # Belt A, injected
    logger_levels: dict[str, int] | None = None,    # per-logger overrides (2f)
    record_filter: logging.Filter | None = None,    # correlation stamping (2d)
) -> None:
```

- `surface` allowlist widens to `{"web", "pipeline", "cli"}`.
- Handler switches `TimedRotatingFileHandler` → `RotatingFileHandler(filename=target, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")`.
- If `install_record_factory` is provided, it is **called** (idempotent installer) — the seam never imports the factory; it is injected. This keeps the seam importing **nothing** from `swing.integrations.schwab` (Arc-1 invariant preserved).
- If `record_filter` is provided, it is attached to the handler.
- If `logger_levels` is provided, each `logging.getLogger(name).setLevel(lvl)` is applied after root setup.
- **Preserved invariants:** idempotency by `baseFilename`; `root.setLevel(level)` on every path (incl. dedup); formatter set on the handler **before** `addHandler` (no unredacted window); on dedup, a supplied `formatter`/`record_filter` is (re)installed onto the existing handler (never silently skipped).

### 3.2 The composition root — `swing/logging_setup.py:install_logging(cfg, *, surface)` (NEW)

The single entrypoint every surface calls. **May** import the schwab belts (it is the composition root, not the seam):

```python
def install_logging(cfg: Config, *, surface: str) -> None:
    from swing.integrations.schwab.client import (
        RedactingFormatter, ensure_schwab_log_redaction_factory_installed,
    )
    log_cfg = cfg.logging                       # LoggingConfig (§5)
    configure_logging(
        cfg.paths.logs_dir, surface=surface,
        level=log_cfg.level,
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT),     # Belt B, every surface
        max_bytes=log_cfg.max_bytes, backup_count=log_cfg.backup_count,
        install_record_factory=ensure_schwab_log_redaction_factory_installed,  # Belt A
        logger_levels=log_cfg.resolved_logger_levels(),       # 2f overrides
        record_filter=_correlation_filter(surface),           # 2d (Slice 2)
    )
```

Because **all three surfaces route through `install_logging`, redaction is by construction** — adding a surface cannot omit it. Seam purity is preserved: the schwab import lives only here.

### 3.3 Call-site migration

- `configure_web_logging(logs_dir)` becomes a thin shim that resolves `cfg` and delegates to `install_logging(cfg, surface="web")` — **external behavior preserved** (web.log still written, idempotent). (If `cfg` is not reachable from the existing shim signature, the `app.py` call site moves to `install_logging(cfg, surface="web")` directly; the shim is retained for back-compat or removed if unused — decided in writing-plans. Either way the web.log behavior contract is unchanged.)
- `cli.py` `pipeline_run_cmd`'s hand-wired Belt-A + Belt-B block collapses to `install_logging(cfg, surface="pipeline")`.
- `cli.py` top-level (every CLI invocation) calls `install_logging(cfg, surface="cli")` (Slice 2).

---

## 4. Slice 1 — disk-pain + safety core (built first)

### 4.1 (2b) Size-based rotation + retention

`RotatingFileHandler(maxBytes, backupCount, encoding="utf-8")` per surface; params from `[logging]` config (defaults `max_bytes=10MB`, `backup_count=5`). Bounded **by construction**: ≤ `(backup_count + 1)` files × `max_bytes` per surface ≈ ≤ 60 MB/surface; with web+pipeline (Slice 1) the active managed footprint is ≤ ~120 MB, and ≤ ~180 MB once cli.log lands (Slice 2) — all well under today's 230 MB, and the legacy oversized dated files are removed by the cleanup (§4.2).

**Test:** drive writes exceeding `max_bytes × (backup_count + 1)`; assert the managed file set is ≤ `backup_count + 1` files **and** each ≤ ~`max_bytes` (discriminating: the assertion fails under the old unbounded `TimedRotatingFileHandler` and passes only under the size cap). Idempotency + formatter-before-add + level-on-every-path regression tests retained green.

### 4.2 One-time cleanup (operator-gated, design-only auto-behavior)

A new CLI command (working name `swing logs cleanup`) that:

1. Scans `cfg.paths.logs_dir` for **oversized / legacy** artifacts — including the legacy **dated** `web.log.2026-05-06`-style files that the new `RotatingFileHandler` will *not* manage (it uses `.log.1`/`.log.2` numeric suffixes). Selection predicate: dated-suffix legacy files **or** any non-active file above a size threshold.
2. Prints the candidate files + bytes that will be reclaimed.
3. **Prompts for explicit operator confirmation** (`--yes` to skip the prompt for scripted use; default is interactive confirm).
4. **gzips in place** (`{name} → {name}.gz`), then removes the original. ~10-20× reduction on text → reclaims ~160 MB while preserving the forensic record. Reversible (`gunzip`).

**Constraints:** idempotent (skips files already `.gz`); **never auto-runs**; **never wired into normal startup**; ASCII-only output (cp1252 stdout footgun — add a subprocess-through-PowerShell encoding test); writes nothing outside `logs_dir`. This is the OQ-4 disposition: **compress in place**.

### 4.3 (2e) Test-leak fix

The web/app TestClient fixtures must not write to the real `~/swing-data/logs`. Fix: the fixtures monkeypatch `USERPROFILE` **and** `HOME` (per the `write_user_overrides` gotcha) **or** pin an absolute `tmp_path` `logs_dir`, so `configure_*`/`install_logging` resolve to a temp dir. Add a **guard test** asserting no test writes the real logs dir (e.g. assert the real `logs_dir` is untouched / assert resolved logs_dir is under tmp during the suite).

### 4.4 (2c) Redaction by construction — existing surfaces

Promoted into `install_logging` (§3.2): **web + pipeline** both receive Belt A (factory) + Belt B (`RedactingFormatter`) by construction. **Strictly additive** — web.log goes from *unredacted* to *redacted*; pipeline.log keeps its existing coverage. **Sentinel-leak audit extended** (`tests/integrations/test_pipeline_log_redaction.py` family + `test_*_token_redaction_audit.py`): a planted secret-shaped sentinel emitted through a **non-Schwabdev** logger is redacted on `web.log` (new assertion) as well as `pipeline.log`. The promotion must not create an unredacted window — assert formatter is set before the handler joins root.

### 4.5 (2f core) Config plumbing + level knob

`[logging]` section, cascade `swing.config.toml` (committed defaults) → `user-config.toml` (operator overrides), parsed into a new `LoggingConfig` dataclass on `Config`. Slice-1 fields: `level` (root default INFO), `max_bytes`, `backup_count`. `level` accepts a level name (`"DEBUG"`/`"INFO"`/...) resolved to the int; **malformed `level` degrades to INFO + a logged warning, never a crash** (test: a junk level value → INFO). This rides Slice 1 because 2b's `max_bytes`/`backup_count` are config-driven (dependency, see §7 Callout A).

```toml
[logging]
level = "INFO"
max_bytes = 10485760   # 10 MB
backup_count = 5
# [logging.loggers]      # per-logger overrides — Slice 2 (built empty by default)
# httpx = "WARNING"
# yfinance = "WARNING"
```

---

## 5. Slice 2 — CLI surface + correlation + overrides

### 5.1 (2a) CLI centralization → `cli.log`

`cli.py` calls `install_logging(cfg, surface="cli")` at command entry → a bounded, redacted `cli.log`. Sentinel-leak audit extended to `cli.log`. finviz's `_suppress_transport_debug_logs()` security suppression **stays as-is** (auth-token-in-URL safety belt); the general per-logger pattern is now *also* expressible via the override table, but the targeted security belt is not removed.

### 5.2 (2d) Run/request correlation

- **Transport (OQ-5): env var + LogRecord filter.** The web's `Popen` passes `SWING_WEB_REQUEST_ID=<request.state.request_id>` in the subprocess `env` (the one minimal, justified touch to the DEVNULL spawn in `swing/web/routes/pipeline.py` — flagged per the lock). The web also logs the request_id at spawn time in `web.log`.
- The CLI installs a `logging.Filter` (`record_filter` in §3.1) that stamps every record with `web_request_id` (read once from env at install) and `pipeline_run_id` (set once the subprocess acquires its lease / `pipeline_runs.id`). Records carry safe defaults (`-`) when an id is absent so web/cli lines stay clean.
- **Join chain:** `web.log`(request_id) ↔ `pipeline.log`(web_request_id + run_id) ↔ `pipeline_runs` / `pipeline_step_timings`(run_id).
- **Format:** `DEFAULT_LOG_FORMAT` extended to carry the correlation fields only where present, with `-` defaults (LogRecord attributes injected by the filter; the filter must run on records that never pass through it too — use a `logging.Filter` on the handler that sets missing attrs, or a `defaults=` formatter so absent attrs don't `KeyError`). Note the format-string change touches existing web.log line-shape assertions → update those tests in the same task.

**Test:** a subprocess launched with `SWING_WEB_REQUEST_ID=<sentinel>` produces `pipeline.log` records carrying the sentinel; the run's `pipeline_run_id` appears once the lease is acquired.

### 5.3 (2f overrides) Per-logger override table

`[logging.loggers]` table applied after root setup via `logger_levels` (§3.1). **Shipped empty by default** (Callout B). `LoggingConfig.resolved_logger_levels()` parses name→level, skipping/Warning-logging malformed entries (never crash). This is the operator's lever to demote `httpx`/`yfinance`/etc. without code edits.

---

## 6. Testing (each "thing to nail" → a test)

- **Redaction by construction proven on every surface** — extended sentinel-leak audit: a planted non-Schwabdev sentinel is redacted on `web.log` (Slice 1) and `cli.log` (Slice 2), in addition to `pipeline.log`. Assert no unredacted window (formatter before add-to-root).
- **Retention actually bounds the dir** — discriminating cap test (§4.1): passes only under the size cap, fails under unbounded dated rotation.
- **Seam idempotent + web.log behavior preserved** — existing web.log tests stay green (behavioral: writes to web.log, dedup, level). Handler-class assertions that pin `TimedRotatingFileHandler` are updated to `RotatingFileHandler` in the same task (behavior contract, not the class name, is the lock).
- **Correlation id round-trips** — §5.2 test.
- **Level knob honored** — `[logging] level=DEBUG` → root/handlers at DEBUG; default INFO; malformed → INFO + warning, no crash. Per-logger override applies the named level.
- **Test-leak guard** — no test writes the real `~/swing-data/logs`.
- **Windows/encoding** — utf-8 handlers; ASCII in new operator-facing strings (cleanup command); a subprocess-through-PowerShell test for cleanup stdout (cp1252 footgun).
- **Discriminating-test discipline** ([[feedback_regression_test_arithmetic]]) — compute the asserted values under both pre-fix and post-fix paths so the cap/redaction tests genuinely distinguish.

---

## 7. Sequencing (OQ-1)

**Two slices, one spec, two writing-plans/executing cycles.**

- **Slice 1 — disk-pain + safety core:** §3 architecture (seam extension + composition root for the two existing surfaces) + §4 (2b rotation+retention, the one-time cleanup command, 2e test-leak fix, 2c redaction-by-construction for web+pipeline, 2f config core: `level`/`max_bytes`/`backup_count`).
- **Slice 2 — CLI surface + correlation:** §5 (2a `cli.log` centralization, 2d correlation, 2f per-logger override table).

**Callout A (sequencing refinement, operator-acknowledged):** size-based rotation (2b) needs `max_bytes`/`backup_count` from the `[logging]` section, so the **config section + level knob (the cheap core of 2f) ride in Slice 1** with 2b — a hard dependency. Only the richer `[logging.loggers]` override table, CLI centralization (2a), and correlation (2d) defer to Slice 2.

**Spec splits into 2 cycles.** Each slice gets its own copowers writing-plans → executing-plans cycle, each Codex-converged, each operator-gated at merge. Flag for writing-plans: produce **two** plans (or one plan with a clean Slice-1/Slice-2 boundary the orchestrator can dispatch independently).

---

## 8. Schema & locks

- **Schema: NONE (v25 holds).** Correlation is a log-record stamp (not a column); per-step timing already lives in `pipeline_step_timings`. **No logging table is warranted** — no STOP-flag raised.
- **Do NOT regress Arc 1:** `configure_logging` seam stays Schwab-agnostic (belts injected, never imported into the seam module); `pipeline.log`, the two-belt pipeline redaction, the `configure_web_logging` external behavior, and `pipeline_step_timings` all stay working.
- **`swing/trades/` + `swing/data/` read-only** — no carve-out (the reconciliation-backfill traceback demotion was not selected).
- **The one-time 225 MB cleanup is operator-gated + non-destructive** (gzip in place; explicit confirm) — never an auto-delete, never wired into normal operation.
- **Redaction is never weakened** — promotion to the seam is strictly additive (every surface ≥ today's coverage); the sentinel-leak audit is extended, never narrowed.
- **One minimal flagged touch:** the `Popen` `env` dict in `swing/web/routes/pipeline.py` (2d, Slice 2) — justified by the correlation transport (OQ-5); the DEVNULL spawn is otherwise unchanged.

---

## 9. Resolved open questions (§6 of the dispatch brief)

| OQ | Resolution |
|----|-----------|
| **OQ-1** sequencing | Two slices (Slice 1 disk-pain+safety core; Slice 2 CLI+correlation). Spec splits into 2 writing-plans/executing cycles. |
| **OQ-2** rotation trigger / why backupCount=7 failed | Size-based `RotatingFileHandler`. `backupCount` bounds count not size; daily files hit 83-97 MB with no size ceiling, rollovers infrequent (per-session server). |
| **OQ-3** retention params | `max_bytes=10 MB`, `backup_count=5` per surface (config-driven). |
| **OQ-4** one-time cleanup | Compress in place (gzip), operator-gated + confirm. |
| **OQ-5** correlation transport | Env var (`SWING_WEB_REQUEST_ID`) + LogRecord filter; `pipeline_run_id` from the lease. |
| **OQ-6** level-knob shape | `[logging]` in both configs (cascade); `level` + `max_bytes` + `backup_count` (Slice 1) + `[logging.loggers]` override table (Slice 2, empty by default). finviz security suppression retained. |
| **OQ-7** volume right-sizing | Dominant source = pytest leak into real web.log (+ httpx/yfinance). Arc action = test-leak fix only (Slice 1); httpx/yfinance demotion deferred to the operator-driven override table. |
