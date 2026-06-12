# Writing-Plans Dispatch Brief — Phase 16 / Arc 2 / SLICE 1: Logging disk-pain + safety core

**Arc:** Phase 16 (Observability & Logging) / **Arc 2** (logging-system overhaul) / **SLICE 1 of 2**.
**Cycle stage:** `copowers:writing-plans` (produce an executing-ready implementation plan, Codex-converged). SECOND of the full copowers cycle; the brainstorm spec is LOCKED + merged.
**Source of truth (LOCKED, merged to main):** [`docs/superpowers/specs/2026-06-09-logging-overhaul-design.md`](superpowers/specs/2026-06-09-logging-overhaul-design.md) — **READ IT END-TO-END.** This plan implements **SLICE 1 ONLY** = spec §3 (architecture: seam extension + the `install_logging` composition root, for the two existing surfaces web+pipeline) + §4 (2b rotation+retention, the one-time cleanup command, 2e test-leak fix, 2c redaction-by-construction for web+pipeline, 2f config core) + the §6 tests for those. **Slice 2 (§5: CLI `cli.log`, 2d correlation, the per-logger override table) is OUT — a separate later cycle. Do NOT plan it.**
**Branch-from:** main HEAD at worktree creation (currently `eb91539d`; **re-verify with `git log --oneline -3`** — the operator commits research to main in parallel).
**Schema:** **NONE — v25 holds.** Zero migrations (confirmed in the spec §8; `pipeline_step_timings` already covers timing).
**Deliverable:** an executing-ready plan at `docs/superpowers/plans/2026-06-09-logging-slice1-plan.md` + Codex convergence (`NO_NEW_CRITICAL_MAJOR`) + `.copowers-findings.md` (prompts AND responses). Commit ONLY the plan doc.

---

## 1. Mandate (one line)

Turn the LOCKED Slice-1 design into an ordered, TDD-structured, executing-ready task plan: the `configure_logging` seam extension (size-based `RotatingFileHandler` + additive injection) + the new `swing/logging_setup.py:install_logging` composition root (redaction by construction) + the bounded rotation/retention + the operator-gated content-preserving cleanup command + the test-leak fix + the `[logging]` config core — each task with its failing-test-first ordering, exact files, discriminating acceptance, and commit message.

The design is settled (Codex-converged, 7 rounds). Your job is the **plan**: task decomposition, the TDD ordering, exact per-task acceptance, and resolving the §3 plan-time decisions below. **Do NOT redesign** — if you believe the spec is wrong, STOP and flag it (don't silently deviate). The spec already corrected one Arc-1 lock violation (it RETAINS `configure_web_logging`); honor that.

---

## 2. STEP 0 — re-ground (the spec grounded on `96750df2`; only docs since — re-confirm)

On your worktree HEAD, re-confirm the spec's §2/§3 anchors before pinning task line numbers:
- The Arc-1 seam `swing/logging_config.py:configure_logging(logs_dir, *, surface, level=INFO, formatter=None)` (the `TimedRotatingFileHandler` Arc 1 shipped — Slice 1 switches it to `RotatingFileHandler`); `configure_web_logging` @[middleware/request_id.py:32](../swing/web/middleware/request_id.py) (the RETAINED shim); `app.py:441` call; the Belt-A factory + Belt-B `RedactingFormatter` in [client.py](../swing/integrations/schwab/client.py); `pipeline_run_cmd` @[cli.py](../swing/cli.py) (installs the belts).
- **The test-leak source (§2.1/§4.3):** confirm WHERE the pytest suite's web.log writes originate — the relative `logs_dir` resolving against the un-monkeypatched real `$USERPROFILE` (the `write_user_overrides` USERPROFILE/HOME leak gotcha family — [[feedback_tests_monkeypatch_userprofile_and_home]]). Identify the exact fixture/app-init path that writes `~/swing-data/logs/web.log` during tests (the 33.6K `httpx: testserver` lines + synthetic tracebacks).
- The `Config` dataclass + the config load/cascade (`swing.config.load` + the user-config overlay) where the new `[logging]` `LoggingConfig` lands.

---

## 3. Plan-time decisions to resolve (the spec leaves these to writing-plans)

1. **The test-leak fix mechanism (§4.3, 2e).** The dominant web.log contributor is the suite writing to the operator's REAL `~/swing-data/logs/`. Resolve the fix shape: a session/autouse conftest fixture that redirects `logs_dir` to a tmp path (and/or monkeypatches `USERPROFILE`+`HOME` suite-wide), vs making app/log init refuse the real logs dir under pytest, vs a per-test fixture. Pick the one that (a) stops ALL leak paths (TestClient app-startup logging + any direct `configure_*` call), (b) is hard to forget for future tests, (c) does not mask the production wiring the redaction/rotation tests need. Add the **guard test** (§6: "no test writes the real `~/swing-data/logs`").
2. **The cleanup command's CLI surface (§4.2).** Decide the command name/shape (e.g. `swing logs compress` / a `logs` group) + its confirm-prompt + flags. It MUST: be operator-gated (explicit confirm, never auto-run, never wired into startup), content-preserving (verify the `.gz` before unlinking the `.log`), idempotent (skip already-`.gz`), ASCII-only output (cp1252 gotcha — add a PowerShell-stdout encoding test), `os.replace` temp in `logs_dir` (same-filesystem Windows gotcha), write nothing outside `logs_dir`.
3. **`LoggingConfig` placement + cascade (§4.5).** Where the dataclass lives + how the `[logging]` section parses through the `swing.config.toml` → `user-config.toml` cascade; malformed `level` → INFO (not crash); the Slice-1 fields (`level`, `max_bytes` default 10MB, `backup_count` default 5).
4. **Dedup-refresh semantics (§3.1, R1-minor-1):** on a second `configure_logging` call for an already-attached handler, refresh `level`/`formatter`/`record_filter`/`logger_levels` but NOT `maxBytes`/`backupCount` (mutating those mid-process orphans the rotation invariant). Make this an explicit task acceptance.

---

## 4. Plan shape (guidance — you own the final decomposition; map each task to spec §6 tests)

TDD tasks (failing test → fail → minimal impl → pass → commit). A natural ordering:

- **Task 1 — seam extension (§3.1).** `configure_logging`: switch `TimedRotatingFileHandler` → `RotatingFileHandler(maxBytes, backupCount, encoding="utf-8")`; add the additive-injection params (`record_filter`, `logger_levels`, `max_bytes`, `backup_count`); dedup-refresh semantics (decision §3.4). **Update the existing web.log tests that pin `TimedRotatingFileHandler` → `RotatingFileHandler` IN THIS TASK** (behavior contract, not class name, is the lock — spec §6); keep idempotency/formatter-before-add/level-on-every-path green. Discriminating retention test: writes exceeding `max_bytes×(backup_count+1)` → managed set ≤ `backup_count+1` files each ≤ ~`max_bytes` (fails under the old unbounded handler).
- **Task 2 — the `install_logging` composition root (§3.2/§3.3).** New `swing/logging_setup.py:install_logging(cfg, *, surface)` — the Schwab-AWARE root that wires redaction (Belt A factory + Belt B `RedactingFormatter`) by construction for the surface, reading `LoggingConfig`. Migrate `app.py` to call `install_logging(cfg, surface="web")`; **RETAIN `configure_web_logging`** as the back-compat shim (Arc-1 lock — gains the optional `cfg=None` per §3.3). Migrate `pipeline_run_cmd` to route through `install_logging(cfg, surface="pipeline")` (preserving Arc-1's two-belt behavior). The seam (`configure_logging`) stays Schwab-agnostic — the schwab import lives ONLY in `logging_setup`.
- **Task 3 — redaction by construction for web+pipeline (§4.4, 2c).** Extend the sentinel-leak audit: a planted non-Schwabdev sentinel is redacted on `web.log` (now) + `pipeline.log` (Arc-1, still). Assert no unredacted window (formatter before add-to-root). Strictly ADDITIVE — never narrows Arc-1 coverage.
- **Task 4 — the `[logging]` config core (§4.5, 2f core).** `LoggingConfig` dataclass on `Config`; `[logging]` cascade parse (decision §3.3); `level`/`max_bytes`/`backup_count`; malformed-level→INFO test. (Rides Slice 1 because 2b's params are config-driven.)
- **Task 5 — test-leak fix (§4.3, 2e).** The decision-§3.1 mechanism + the guard test (no test writes the real `~/swing-data/logs`). This is the dominant volume fix.
- **Task 6 — the one-time cleanup command (§4.2).** The decision-§3.2 CLI command: content-preserving gzip, operator-gated confirm, idempotent, ASCII-only (+ PowerShell-stdout test), `os.replace` temp in `logs_dir`. Never auto-runs.
- **Task 7 — full suite + ruff.** `python -m pytest -m "not slow" -q` green (isolate the 3 known xdist flakes with `-n0` if they appear; note the pre-existing `test_study_doc.py` em-dash failure is NOT this arc); `ruff check swing/`.

Pin each task's exact files, the discriminating assertion ([[feedback_regression_test_arithmetic]]), and the commit message.

---

## 5. Locks / invariants (from spec §8 — do not regress)

- **Schema NONE (v25).** DB-outside-Drive.
- **Do NOT regress Arc 1:** `configure_logging` stays the low-level Schwab-AGNOSTIC seam (belts injected via `install_logging`, never imported into the seam module); `configure_web_logging` RETAINED (external signature preserved; back-compat shim); `pipeline.log` + the two-belt pipeline redaction + `pipeline_step_timings` all stay working. The handler-class test-assertion updates (`TimedRotatingFileHandler`→`RotatingFileHandler`) land in the SAME task as the switch.
- **Redaction strictly ADDITIVE** — every surface gets ≥ today's coverage; the sentinel-leak audit is extended, never narrowed; no unredacted window (formatter before add-to-root).
- **The one-time cleanup is OPERATOR-GATED + content-preserving** — explicit confirm, verify-`.gz`-before-unlink, never auto-runs, never wired into startup, writes nothing outside `logs_dir`. Honor the Windows `os.replace` same-filesystem + the cp1252 stdout gotchas.
- **Phase isolation:** change loci = `swing/logging_config.py`, new `swing/logging_setup.py`, `swing/web/middleware/request_id.py` (shim), `swing/web/app.py` (call-site), `swing/cli.py` (pipeline_run_cmd route + the cleanup command), `swing/config*.py` (`LoggingConfig`), tests + conftest. **`swing/trades/` + `swing/data/` read-only.**

---

## 6. Out of scope / banked (carry to the plan's out-of-scope §)

- **Slice 2** (§5): the CLI `cli.log` centralization (2a), run/request correlation (2d), the per-logger override table (2f overrides). A SEPARATE writing-plans→executing cycle after Slice 1 ships.
- **Callout B (operator-deferred):** shipping WARNING defaults for httpx/yfinance is NOT in Slice 1 — the demotion lever is the Slice-2 override table; Slice 1's test-leak fix already removes the DOMINANT volume. (The operator may revisit; one-line follow-on.)
- NOT Arc 3 (XMAX), NOT Arc 4 (equity reconciliation), NOT the perf follow-on. NO schema.

---

## 7. copowers process (binding)

- **Run `copowers:writing-plans`** — wraps `superpowers:writing-plans` then the adversarial Codex loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED). Do not stop early; do not pad after convergence.
- **Codex transport (WSL CLI; the MCP `codex` tool is DEAD in the VS Code extension):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows + tell Codex not to run git.
- **Persist BOTH prompts AND responses** of every Codex round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md`.
- **No `Co-Authored-By`; no `--no-verify`; conventional commits; final `-m` paragraph plain prose** (no `Word:`-leading line → trailer-parse hazard). Commit ONLY the plan doc.
- **Return a report:** the plan path; how you resolved the §3 decisions; the Codex convergence verdict (round count + final line); anything flagged for executing. Then STOP — do NOT execute. Executing is a separate commission after the orchestrator QAs the plan.
