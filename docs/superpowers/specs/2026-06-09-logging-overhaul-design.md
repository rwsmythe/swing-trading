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

**Scope decision (Callout B — explicit, R1-major-3).** This is a deliberate, operator-chosen scope boundary, not an oversight. **Arc 2's 2e bounds log *volume on disk* (via 2b retention) and removes the single largest contributor (the pytest leak); it does NOT right-size production signal/noise by default.** The only 2e *code action* this arc is the **test-leak fix** (item 1). Items 2-3 (`httpx` INFO, `yfinance` ERROR) are real production noise left to the operator via the Slice-2 per-logger override table (`[logging.loggers]`) — **the lever is built, the policy is not imposed**; the operator can demote them with a one-line config edit. The shipped *default* therefore remains as noisy as today's production behavior (minus the test leak), but **disk-bounded** by the retention cap. Item 5 (a reconciliation-backfill traceback demotion) would touch `swing/trades/` and was **explicitly not selected** — the read-only lock stays clean. (If the operator later wants quiet-by-default, shipping `httpx=WARNING`/`yfinance=WARNING` as committed `[logging.loggers]` defaults is a trivial follow-on — the mechanism already exists.)

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
- **Filter install is REPLACE, not append (R5-minor-1).** `Handler.addFilter()` appends, so a naive re-install on dedup would accumulate duplicate filters. The swing correlation filter is tagged (e.g. `filter._swing_correlation = True`); before adding the refreshed filter, any prior swing-tagged filter on the handler is removed (`removeFilter`) — so exactly one swing correlation filter is ever attached. Foreign filters are never touched.
- Handler is created with `delay=True` (the file opens on first emit, not at construction) — minimizes the open-handle window that aggravates Windows rename-on-rollover races (§3.4).
- **The handler level is left at `NOTSET` (0) by design (R4-major-1).** Thresholding is owned by the **root logger** (`level`) and **per-logger overrides** only — never the handler. This is what makes the §4.5 direct-`handler.handle()` diagnostics replay reliable (the handler never filters), and it is a locked invariant: the level knob sets root/logger levels, not handler levels.
- **Config is read once per process; rotation params (`max_bytes`/`backup_count`) are fixed for the process lifetime.** On dedup, the seam refreshes only `level`, `formatter`, `record_filter`, and `logger_levels` onto the existing handler — it does **not** mutate `maxBytes`/`backupCount` of an already-attached handler (changing those mid-process would orphan the rotation invariant). A param change takes effect on the next process start (R1-minor-1).

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

### 3.3 Call-site migration (LOCKED — R1-minor-3, corrected R2-major-1)

- **`configure_web_logging` is RETAINED** (Arc-1 lock honored — it is *not* removed). Its external signature `configure_web_logging(logs_dir)` is preserved; it becomes a thin back-compat shim that delegates to the redacted/bounded path. It gains an **optional** `cfg=None` param: with `cfg`, it forwards to `install_logging(cfg, surface="web")`; without `cfg` (legacy logs_dir-only callers), it constructs a minimal default `LoggingConfig` (INFO, 10 MB, 5) and routes through the same redaction+rotation wiring. Either way the web.log behavior contract (writes to web.log, idempotent) is preserved **and** redaction is now added (strictly additive, §4.4).
- **`app.py` is migrated to call `install_logging(cfg, surface="web")` directly** (the web app is config-file-backed at startup, so `cfg` is in hand) to get config-driven rotation params + correlation. `configure_web_logging` remains for any other/external/test caller. (Consistent with §8: the shim stays working.)
- `cli.py` `pipeline_run_cmd`'s hand-wired Belt-A + Belt-B block collapses to `install_logging(cfg, surface="pipeline")`.
- The CLI entrypoint installs **exactly one** surface per process (§3.4) — it does **not** unconditionally install `cli.log` for the pipeline command.

### 3.4 Single surface per process — routing (R1-major-1)

A process writes to **exactly one** swing-managed surface file. Two enforcement rules:

1. **Surface selection by command (CLI).** The `cli.py` entrypoint chooses the surface from the dispatched command: `pipeline run` → `surface="pipeline"`; every other command → `surface="cli"` (Slice 2). The pipeline subprocess therefore never installs `cli.log` — it is a pipeline-surface process. (The `cli.py` group callback inspects the invoked subcommand, or `pipeline_run_cmd` is the sole installer for the pipeline path while the generic `cli` install is skipped for it. Mechanism locked in writing-plans; the **contract** is: pipeline-surface processes emit only `pipeline.log`.)
2. **Single-handler enforcement (seam).** `install_logging`/`configure_logging` guarantee at most one swing-managed `RotatingFileHandler` on root per process: before adding a handler for a *different* surface, any previously-installed swing surface handler is **removed and closed** — `root.removeHandler(h)` **then `h.close()`** (R2-major-4: `removeHandler` alone does not release the file descriptor; on Windows an unclosed handle blocks rotation/rename and the cleanup). A swing handler is tagged (e.g. `handler._swing_surface = surface`) so it is identifiable and a foreign library's handler is never removed/closed. This makes a stray double-install of two different surfaces converge to the last surface rather than tee-ing every record into both files. (Same-surface re-install stays idempotent per §3.1 — the existing handler is kept, not closed-and-recreated.)

**Test:** a simulated `swing pipeline run` process ends with exactly one swing handler whose `baseFilename` is `pipeline.log` (not `cli.log`); records are not duplicated across surface files.

---

## 4. Slice 1 — disk-pain + safety core (built first)

### 4.1 (2b) Size-based rotation + retention

`RotatingFileHandler(maxBytes, backupCount, encoding="utf-8")` per surface; params from `[logging]` config (defaults `max_bytes=10MB`, `backup_count=5`). Bounded **by construction**: ≤ `(backup_count + 1)` files × `max_bytes` per surface ≈ ≤ 60 MB/surface; with web+pipeline (Slice 1) the active managed footprint is ≤ ~120 MB, and ≤ ~180 MB once cli.log lands (Slice 2) — all well under today's 230 MB, and the legacy oversized dated files are removed by the cleanup (§4.2).

**Test:** drive writes exceeding `max_bytes × (backup_count + 1)`; assert the managed file set is ≤ `backup_count + 1` files **and** each ≤ ~`max_bytes` (discriminating: the assertion fails under the old unbounded `TimedRotatingFileHandler` and passes only under the size cap). Idempotency + formatter-before-add + level-on-every-path regression tests retained green.

**Process-safety posture (R1-major-2, explicit single-writer-per-surface assumption).** `RotatingFileHandler` is not multi-process-safe (rollover does `os.rename`, which can fail on Windows if another process holds the file open). This design accepts that with a documented assumption rather than pulling in a process-safe handler dependency (YAGNI for a single-operator app):
- Surfaces are **distinct files** (`web.log`/`pipeline.log`/`cli.log`) — no cross-surface contention.
- `web.log` has a **single writer** (one uvicorn process).
- `pipeline.log` is **lease-fenced** — `pipeline_runs` lease prevents a second concurrent pipeline run, so its single daily rollover has one writer.
- `cli.log` is the only surface with a plausible concurrent-writer window (the operator running two `swing` commands at once). A rollover-rename collision there is **non-fatal**: stdlib `logging.handleError` swallows the `OSError` (a single record may be dropped or land in the pre-rollover file), with **no crash and no corruption of other surfaces**. `delay=True` (§3.1) shrinks the open-handle window. If concurrent CLI logging ever becomes routine, a `ConcurrentRotatingFileHandler`-style dependency is the V2 escape hatch (out of scope).

**Disk-budget accounting (R1-minor-4).** The ≤ ~180 MB ceiling counts only the **active `RotatingFileHandler` files** (`{surface}.log` + `.log.1..N`). The one-time cleanup's compressed archives (`.log.DATE.gz`, §4.2) are a **static one-time artifact** (~10-15 MB total after ~10-20× compression), **not** part of the ongoing rotation budget and not managed/pruned by the handler; the operator may delete them at any time. Total steady-state disk = managed rotation budget + (optional) residual `.gz` archives.

**Migration window (R5-major-1 — the ≤ `max_bytes` per-file claim is STEADY-STATE, not instantaneous).** A pre-existing oversized **current** file (today's `web.log` at 58 MB) is opened by the new `RotatingFileHandler` in append mode (`delay=True`); the first emit that crosses `max_bytes` (immediately, since the stream is already at 58 MB) rolls it to `web.log.1` **at its full 58 MB** — one `.log.N` slot will exceed `max_bytes` until it ages out across `backup_count` subsequent rollovers. So: the per-file cap and the ≤ ~180 MB ceiling are **steady-state guarantees** (they hold once the pre-existing carryover has aged out), and there is a bounded **one-time migration window** where a single rotated backup per migrated surface may exceed `max_bytes`. The cap **tests assert steady-state** (drive rollovers from an empty start), not the migration instant. The operator can collapse the migration window to zero by running the cleanup's **app-stopped reclaim scope** (§4.2) on the oversized *current* files before/at first start under the new handler.

### 4.2 One-time cleanup (operator-gated, design-only auto-behavior)

A new CLI command (working name `swing logs cleanup`) that:

1. Scans `cfg.paths.logs_dir` and selects **only legacy dated artifacts** — files matching `{surface}.log.<DATE>` (e.g. `web.log.2026-05-06`), the suffix shape the *old* `TimedRotatingFileHandler` produced and the *new* `RotatingFileHandler` will never produce. **Selection predicate (R3-major-1 — no live-writer race):** the predicate is the dated-suffix pattern ONLY; it **explicitly excludes every currently-managed name for all three surfaces** — `web.log`/`pipeline.log`/`cli.log` and their numeric rotation set `{surface}.log.<int>` — so the command can never touch a file an active process is writing. Already-`.gz` files are skipped (idempotent). As an operational guard, the command (a) **refuses while a `pipeline_runs` `state='running'` row exists** (mirrors the existing CLI concurrency-exclusion discipline — `SchwabPipelineActiveError`/`FinvizPipelineActiveError` family), **fail-closed** (R4-minor-1): if the DB cannot be opened/queried (unavailable or locked), the command **refuses** with a clear operator message rather than proceeding blind. (b) Emits an **advisory** note (R4-minor-2) that stopping the web server first is *recommended* — phrased as advice, **not** a hard prerequisite, because the dated-suffix-only predicate already never selects an active managed file; the command does not refuse merely because the web server is up.
2. Prints the candidate files + bytes that will be reclaimed.
3. **Prompts for explicit operator confirmation** (`--yes` to skip the prompt for scripted use; default is interactive confirm).
4. **Compresses each file content-preservingly** (`{name} → {name}.gz`) with **verify-before-unlink** semantics: write the `.gz` to a temp file in `logs_dir`, `fsync`, **verify by streamed equality** — stream-decompress the temp `.gz` and compare against the original via a chunked hash (e.g. equal SHA-256 over the byte streams) so verification is **byte-for-byte**, not merely byte-count (R2-minor-2) — then atomically `os.replace` the temp into `{name}.gz`, and only **then** unlink the original. If verification fails, the original is left untouched and the temp is removed. ~10-20× reduction on text → reclaims ~160 MB while preserving the content. Reversible (`gunzip`).

**App-stopped reclaim scope (R5-major-1).** A second, more privileged scope (e.g. `swing logs cleanup --include-current`) also targets the **oversized current/rotated managed files** (`{surface}.log` and `{surface}.log.<int>` above a size threshold) so the operator can reclaim the pre-existing 58/83/97 MB immediately rather than waiting for the migration window to age out. Because this scope touches active managed names, it is **app-stopped-required, not advisory**: it **refuses if a `pipeline_runs` `state='running'` row exists** (fail-closed on DB-unavailable per R4-minor-1) **and requires an explicit operator attestation that the web server is stopped** (a confirm/flag) — the dated-suffix default scope (§4.2 step 1) remains the safe, always-available path. Each file is handled with the same verified content-preserving compression (below); a current `{surface}.log` is compressed and then truncated/removed so the new handler starts clean.

- **Self-surface exclusion (R6-major-1).** The cleanup command is itself a CLI process (Slice 2) and therefore holds an open `cli.log`. `--include-current` **explicitly excludes the invoking process's own active surface log** (`cli.log` for this command) — it must never compress/remove the file it is actively writing. This loses nothing: `cli.log` is created fresh under the bounded handler (Slice 2), so it is never a pre-existing oversized *legacy* carryover; only `web.log`/`pipeline.log` (the pre-existing oversized surfaces) need this scope, and neither is the cleanup command's own surface.
- **Collision-free archive names (R6-major-2), race-free reservation (R7-minor-1).** The archive target is **never overwritten**. The unique name is **reserved by exclusive creation** — `os.open(target, O_CREAT | O_EXCL)` (atomic) claims the first free slot (`{base}.gz`, then `{base}.1.gz`, `{base}.2.gz`, ...); the compressed bytes are written into that reserved path (or an adjacent temp `os.replace`d onto it). This closes the check-then-replace window where two concurrent cleanups could pick the same "first free" name. As defence-in-depth, the cleanup command also takes a **single-instance lock file in `logs_dir`** (refuse if held) so two cleanups never run concurrently in the first place. Together: no prior archive's content is ever lost, across repeated runs, both scopes, and concurrent invocations.

**Terminology (R1-major-6):** this is **content-preserving compression**, not "non-destructive" in the literal sense — the original `.log` file *is* removed after a verified `.gz` replaces it. The guarantee is: **no log content is lost**, the operation is gated behind an explicit confirm, and a verification step precedes any unlink. (It does not preserve the original file's mtime/permissions on the `.gz`; that is acceptable for archived logs.)

**Constraints:** idempotent (skips files already `.gz`); **never auto-runs**; **never wired into normal startup**; ASCII-only output (cp1252 stdout footgun — add a subprocess-through-PowerShell encoding test); writes nothing outside `logs_dir`; `os.replace` temp is created in `logs_dir` (same-filesystem, per the Windows `os.replace` gotcha). This is the OQ-4 disposition: **compress in place (content-preserving)**.

### 4.3 (2e) Test-leak fix

The web/app TestClient fixtures must not write to the real `~/swing-data/logs`. Fix: the fixtures monkeypatch `USERPROFILE` **and** `HOME` (per the `write_user_overrides` gotcha) **or** pin an absolute `tmp_path` `logs_dir`, so `configure_*`/`install_logging` resolve to a temp dir. Add a **guard test** asserting no test writes the real logs dir (e.g. assert the real `logs_dir` is untouched / assert resolved logs_dir is under tmp during the suite).

### 4.4 (2c) Redaction by construction — existing surfaces

Promoted into `install_logging` (§3.2): **web + pipeline** both receive Belt A (factory) + Belt B (`RedactingFormatter`) by construction. **Strictly additive** — web.log goes from *unredacted* to *redacted*; pipeline.log keeps its existing coverage. **Sentinel-leak audit extended** (`tests/integrations/test_pipeline_log_redaction.py` family + `test_*_token_redaction_audit.py`): a planted secret-shaped sentinel emitted through a **non-Schwabdev** logger is redacted on `web.log` (new assertion) as well as `pipeline.log`. The promotion must not create an unredacted window — assert formatter is set before the handler joins root.

### 4.5 (2f core) Config plumbing + level knob

`[logging]` section, cascade `swing.config.toml` (committed defaults) → `user-config.toml` (operator overrides), parsed into a new `LoggingConfig` dataclass on `Config`. Slice-1 fields: `level` (root default INFO), `max_bytes`, `backup_count`. `level` accepts a level name (`"DEBUG"`/`"INFO"`/...) resolved to the int; **malformed `level` degrades to INFO, never a crash** (test: a junk level value → INFO).

**Deferred-diagnostics carrier (R1-major-4 — the chicken-and-egg fix).** Config is parsed *before* `install_logging` runs, so a warning logged at parse time would go to an unconfigured (and unredacted) root. Instead, `LoggingConfig` **collects** parse diagnostics into a `warnings: list[str]` field (e.g. `"[logging] level 'LOUD' invalid; using INFO"`) rather than logging them. `install_logging` **replays** those collected warnings **after** the redacted handler is attached — so every config diagnostic lands in the surface log, redacted, never silently dropped. (The same mechanism carries malformed per-logger-override diagnostics, §5.3.)

**Threshold-guarantee (R2-major-2, hardened R3-minor-1).** The diagnostics must not be swallowed by a high configured root level (a *valid* `level = "ERROR"`) **nor** by a per-logger override targeting the diagnostics logger itself (e.g. `[logging.loggers] swing.logging_config = "CRITICAL"`, applied before replay). To bypass **both** the root level and any logger-level filter, `install_logging` replays each diagnostic by **constructing a `LogRecord` (at WARNING) and calling `handler.handle(record)` directly on the installed swing surface handler** — `Handler.handle` checks only the *handler's* level (left at `NOTSET`/0), not any logger threshold, so delivery is guaranteed regardless of root level or overrides. The record still passes through Belt B (`RedactingFormatter`) on that handler, so diagnostics are redacted. (Diagnostics are replayed *after* the handler — including its formatter/filter — is attached.) Test: with `[logging] level = "ERROR"` **and** `[logging.loggers] swing.logging_config = "CRITICAL"` **and** a junk override, the override diagnostic still appears in the surface log (proves it bypasses both thresholds), and the root effective level is ERROR.

This rides Slice 1 because 2b's `max_bytes`/`backup_count` are config-driven (dependency, see §7 Callout A).

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
- **State carrier + lifecycle (R1-major-5, carrier corrected R2-major-3).** A new neutral module (e.g. `swing/log_correlation.py`) owns the two ids as **thread-safe process-global state** (module-level values guarded by a `threading.Lock`, with `get_/set_` accessors) — **not** `contextvars`. Rationale (R2-major-3): these ids are **process/run-scoped, not task-local** — the pipeline subprocess emits records from worker threads (e.g. the price-fetch executor, threaded steps) that would *not* inherit a `ContextVar` set on the main thread, so a contextvar would silently drop the id on those records. A process-global is single-writer (set once from env at install; once at lease) / many-reader and correct across all threads. **Reset + validation at install (R3-minor-3, R3-minor-2).** `install_logging` **resets both globals to known defaults at start** before seeding — `pipeline_run_id = None`, `web_request_id` = the validated env value or `-` — so a stale `pipeline_run_id` from an earlier run in the same process (a long-lived command, or a test running multiple pipelines) cannot bleed into later records. The `SWING_WEB_REQUEST_ID` env value is **validated, not trusted**: it must match a strict token shape (e.g. `^[A-Za-z0-9-]{1,64}$`, covering the uuid4 the web emits); any value with whitespace/newlines or otherwise non-conforming → `web_request_id` falls back to `-` (defends against an inherited/forged env var injecting newlines or misleading content into log lines). `set_pipeline_run_id(run_id)` updates the run id after lease acquisition. `CorrelationFilter` (a `logging.Filter`) runs **per record** and reads **both globals at `filter()` time**, stamping `record.web_request_id` / `record.pipeline_run_id` — so a value set *after* handler install is picked up on the next record from any thread. **Exact call site:** the pipeline runner's lease-acquisition step (where `pipeline_runs.id` is created — `swing/pipeline/`, the current-phase area, an allowed touch) calls `set_pipeline_run_id(run_id)` immediately after the lease row is inserted. In the web process, `pipeline_run_id` stays `None` (`-`); in the CLI/pipeline process, `web_request_id` comes from the env and `pipeline_run_id` fills in once the lease is held.
- **Join chain:** `web.log`(request_id) ↔ `pipeline.log`(web_request_id + run_id) ↔ `pipeline_runs` / `pipeline_step_timings`(run_id).
- **Format (concrete — R1-minor-2).** The correlation fields are made always-present via a `logging.Formatter(fmt, defaults={"web_request_id": "-", "pipeline_run_id": "-"})` (the stdlib `defaults=` kwarg, Python ≥3.10 — this box is 3.14), so a record that never passed through `CorrelationFilter` (e.g. a third-party logger before the filter attaches) renders `-` instead of `KeyError`. `CorrelationFilter` overrides those defaults when context is present. The single shared format string is used on all surfaces; the `RedactingFormatter` (Belt B) is the concrete `Formatter` subclass and carries the same `defaults=`. The format-string change touches existing web.log line-shape assertions → update those tests in the same task.

**Test:** a subprocess launched with `SWING_WEB_REQUEST_ID=<sentinel>` produces `pipeline.log` records carrying the sentinel; after `set_pipeline_run_id(<id>)` the subsequent records also carry the run id; a record emitted with no correlation context renders `-`/`-` (no `KeyError`).

### 5.3 (2f overrides) Per-logger override table

`[logging.loggers]` table applied after root setup via `logger_levels` (§3.1). **Shipped empty by default** (Callout B). `LoggingConfig.resolved_logger_levels()` parses name→level, skipping malformed entries and collecting a diagnostic into `LoggingConfig.warnings` (replayed after install per the §4.5 deferred-diagnostics carrier — never crash, never silently dropped). This is the operator's lever to demote `httpx`/`yfinance`/etc. without code edits.

---

## 6. Testing (each "thing to nail" → a test)

- **Redaction by construction proven on every surface** — extended sentinel-leak audit: a planted non-Schwabdev sentinel is redacted on `web.log` (Slice 1) and `cli.log` (Slice 2), in addition to `pipeline.log`. Assert no unredacted window (formatter before add-to-root).
- **Retention actually bounds the dir** — discriminating cap test (§4.1): passes only under the size cap, fails under unbounded dated rotation.
- **Seam idempotent + web.log behavior preserved** — existing web.log tests stay green (behavioral: writes to web.log, dedup, level). Handler-class assertions that pin `TimedRotatingFileHandler` are updated to `RotatingFileHandler` in the same task (behavior contract, not the class name, is the lock).
- **Single surface per process** (§3.4) — a simulated `swing pipeline run` ends with exactly one swing handler → `pipeline.log`, no record duplication into `cli.log`.
- **Deferred config diagnostics** (§4.5) — a junk `level` → warning lands in the configured (redacted) surface log after install + `level` falls back to INFO; and the threshold-guarantee case: a *valid* `level="ERROR"` + a junk per-logger override → the override diagnostic still lands (proves it bypasses the ERROR threshold).
- **Correlation id round-trips** — §5.2 test (env sentinel in `pipeline.log`; run id appears after `set_pipeline_run_id`; no-context record renders `-`/`-`).
- **Level knob honored** — `[logging] level=DEBUG` → **root logger** at DEBUG (the handler stays `NOTSET`, §3.1); default INFO; malformed → INFO + warning, no crash. Per-logger override applies the named level to that logger. Assert root/logger effective levels, **not** handler level (R4-major-1).
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
- **The one-time 225 MB cleanup is operator-gated + content-preserving** (verified gzip with verify-before-unlink + explicit confirm, §4.2) — no log content lost, never an auto-delete, never wired into normal operation.
- **Redaction is never weakened** — promotion to the seam is strictly additive (every surface ≥ today's coverage); the sentinel-leak audit is extended, never narrowed.
- **Minimal flagged touches (Slice 2):** (a) the `Popen` `env` dict in `swing/web/routes/pipeline.py` — justified by the correlation transport (OQ-5); the DEVNULL spawn is otherwise unchanged. (b) one call to `set_pipeline_run_id(run_id)` in the pipeline runner's lease-acquisition step (`swing/pipeline/`, the current-phase area — not `swing/trades/`/`swing/data/`); read/write of `pipeline_runs` is unchanged (correlation reads the existing id, adds no column).

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
