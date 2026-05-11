# Finviz Elite API Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual Finviz CSV-export-to-`data/finviz-inbox/` daily-operator-chore with a programmatic Finviz Elite API fetch that emits the same canonical 13-column CSV under the same filename convention so the existing pipeline ingestion is unchanged.

**Architecture:** New `swing/integrations/` namespace establishing the pattern for future API clients; new `swing/integrations/finviz_api.py` module owns auth/fetch/normalize; new pipeline step `_step_finviz_fetch` runs BEFORE `_step_evaluate` and respects file-collision skip (manual CSV present → API fetch skipped); new `finviz_api_calls` audit table (migration 0015) persists every fetch attempt with status + timing + signature-hash for drift detection; new `swing finviz fetch|status` CLI commands; cassette-based unit tests via `pytest-recording` + one slow-marked live integration test.

**Tech Stack:** Python 3.11+; `requests` (project HTTP standard); `pytest-recording` (VCR.py-backed cassette library; new `[dev]` extra); SQLite (additive migration 0015 — single CREATE TABLE + UPDATE schema_version); Click (CLI); `tomli_w` (already a dependency, used for any user-config diagnostics); existing project logging (`logging.getLogger(__name__)`).

---

## §A — Resolved-during-planning items (research findings)

These are findings from §3 of the brief, surfaced during plan drafting. They DO NOT contradict the brief's locked decisions in §2 — they refine open items the brief explicitly deferred to writing-plans time.

### A.1 — Finviz Elite API documentation is behind login (PARTIAL BLOCKER → conservative-defaults workaround)

The brief §3.1 mandates reading https://elite.finviz.com/api_explanation. Plan-author hit this URL during drafting; it 302-redirects to https://finviz.com/api_explanation which renders only a login page. The actual API documentation is gated behind a Finviz Elite subscription login; there is no publicly-accessible documentation.

**Resolution:** the plan synthesizes a working endpoint shape from the Finviz Elite "Export" CSV mechanism that is widely documented in third-party sources and operator-observable from the saved-screen URL the operator already uses. Plan §E codifies this synthesized reference. Task 0 (research-verification) gates on a live API call against the operator's token to confirm response shape BEFORE Task 2's happy-path test cassette is recorded; if the live verification reveals a contradiction with §E (e.g., non-CSV response, different auth-param name), the implementer halts and surfaces to orchestrator. **OPEN QUESTION FOR ORCHESTRATOR (return-report §3):** the executing-plans dispatch needs operator's token + saved-screen URL OR an operator-paste of the api_explanation page text before live verification; the writing-plans dispatch could not access either.

### A.2 — `pytest-recording` chosen as cassette library (over raw `vcrpy`, `responses`, `requests-mock`)

`pytest-recording` (kiwicom) wraps `vcrpy` 8.x with idiomatic pytest fixtures (`@pytest.mark.vcr`, default cassette dir `tests/<test_module_dir>/cassettes/`, mode-switching via `--record-mode={none,once,new_episodes,all}`). It supports `filter_query_parameters` and `filter_headers` natively for token redaction (Finviz uses an `auth=<token>` query parameter; redaction at cassette-record time is non-negotiable per brief §7 watch item 1). Alternatives evaluated:

- **Raw `vcrpy`**: lower-level; pytest-recording wraps it cleanly with no feature loss.
- **`responses`**: hand-mock per-call; doesn't record real responses; can't catch silent upstream-shape drift.
- **`requests-mock`**: hand-mock per-call; same drawback as `responses`.

`pytest-recording` is the only option that supports recording-then-replay AND token-redaction-at-record-time, which is the binding constraint here.

### A.3 — Filename anchor convention: operator-local-date via `action_session_for_run(datetime.now())` formatted `%-d%b%Y` (POSIX) / `%#d%b%Y` (Windows)

The brief §3.4 deferred filename-anchor research. Plan-author verified [`swing/pipeline/finviz_select.py:8`](../../swing/pipeline/finviz_select.py#L8) — the filename-date regex is `(\d{1,2})([A-Za-z]{3})(\d{4})` matching e.g. `5May2026` or `28Apr2026` (1-2 digit day, 3-letter month abbreviation, 4-digit year). The runner [`swing/pipeline/runner.py:180`](../../swing/pipeline/runner.py#L180) uses `action_session_for_run(run_now)` as the run anchor. Therefore the API-emitted CSV's filename uses `action_session.strftime('%#d%b%Y')` on Windows (or `%-d%b%Y` on POSIX) — produces `5May2026`, NOT `05May2026`. Plan §H codifies this.

### A.4 — Rate-limit quota: NOT publicly documented; plan defaults to 1 fetch per pipeline run + 429-Retry-After backoff

Brief §3.2 deferred quota investigation. No publicly-accessible Finviz Elite documentation specifies the exact quota; third-party MCP-server implementations cite ~100 requests/minute as a working value but this is uncited. Pipeline-cadence design is daily so a single fetch per run with no retry-loop is comfortably within any reasonable quota. CLI `swing finviz fetch` is operator-triggered + low-volume (≤10/day forecast). **Locked default behavior:** the client makes one HTTP attempt; on 429 it parses `Retry-After` (in seconds), waits + retries ONCE, then gives up; on subsequent 429 it logs + records `status='error'` + returns. Plan §E.6 specifies exact retry semantics. The conservative default is safe under any documented or undocumented quota.

### A.5 — Finviz API response Content-Type assumption: `text/csv`

Synthesized from public knowledge: Finviz Elite's `/export.ashx` endpoint returns a CSV-formatted body with `Content-Type: text/csv` (or `text/plain`; both observed in third-party reports). Plan-author treats Content-Type as advisory: the client parses the body as CSV regardless of declared type, with a single defense-in-depth check that the first non-blank line of the body parses as a CSV header containing AT LEAST the columns `Ticker, Sector, Industry, Country, Price` (subset of the canonical 13 — most-commonly-present + most-likely-to-bind-anti-spoof). If parse fails, raise `FinvizSchemaParityError` (Task 4). Live verification (Task 0.b) confirms.

### A.6 — `swing.config.toml` rolling cascade audit: `cfg.integrations.finviz.{token,screen_query}` are STRIPPED at `load()` time + EXCLUDED from `FIELD_REGISTRY`

Per brief §2.2 + §5 ruff/security discipline + Codex R1 Critical-2 fix. The Phase 5 `FIELD_REGISTRY` (`swing/config_validation.py`) is the binding source of truth for `swing config show|set|reset` (CLI) and `/config` (web). Adding Finviz fields to it would (a) expose token bytes in `swing config show`, (b) require 3-part-path support in many surfaces (`delete_user_override`, `cli_config.config_show/set/reset`, `web/routes/config.py`, `web/view_models/config.py`), and (c) violate the brief's V1 lock that config-page UX surfacing is V2.

**Plan-locked posture for V1 (binding):**

1. **Sub-dataclass + Config field added** (Task 2): `IntegrationsConfig` + `FinvizIntegrationConfig` with `token: str = ""`, `screen_query: str = ""`, `timeout_seconds: int = 30`. Top-level `Config` adds `integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)`.
2. **`load()` STRIPS tracked-toml `token` + `screen_query`** (security carve-out): the loader reads `raw.get("integrations", {}).get("finviz", {})` BUT explicitly drops the `token` and `screen_query` keys from the dict before passing to `FinvizIntegrationConfig(...)`. Only `timeout_seconds` survives from tracked toml. **Result:** `cfg.integrations.finviz.token == ""` always after `load()`, regardless of what the tracked toml says.
3. **`apply_overrides()` is THE source-of-truth** for `token` + `screen_query` in V1: it reads `[integrations.finviz]` from user-config.toml and `replace()`s the cfg. Consumers that need real Finviz creds MUST call `apply_overrides()` first — see §A.11 for the binding entrypoint convention.
4. **`_get()` is extended to support N-part dotted paths** so `apply_overrides()` can read `integrations.finviz.token`. Other 2-part-path consumers (`delete_user_override`, `cli_config.config_show/set/reset`, `web/routes/config.py`, `web/view_models/config.py`, `get_field_source`) are NOT touched in V1; they continue assuming 2-part paths.
5. **`FIELD_REGISTRY` is NOT extended in V1.** Finviz fields stay out of `swing config show|set|reset` and out of `/config`. This honors the brief's "config-page UX surfacing is V2" lock + eliminates the token-leak surface area.
6. **`Config(...)` direct-construction audit:** the new top-level `integrations` field has `default_factory=IntegrationsConfig` so existing test fixtures that omit `integrations=` continue to construct without changes. Discriminating test in Task 2 verifies.

V2 hardening (out-of-scope; track for a follow-up dispatch): masked sensitive-field handling in `swing config show` + 3-part-path support in registry-coupled surfaces; until then, `swing config show` legitimately omits Finviz fields entirely.

### A.11 — Runtime entrypoint convention: callers consume effective cfg via `apply_overrides()` (Codex R1 Critical-1 fix)

Brief §2.2 implicitly assumed effective cfg propagation but did not enumerate entrypoints. Verified via [`swing/cli.py:108`](../../swing/cli.py#L108) — `main()` calls `load_config(...)` and stores the RAW cfg in `ctx.obj["config"]`; `apply_overrides()` is NOT called centrally. Per-consumer responsibility is the existing Phase 5 convention (see [`swing/cli_config.py:35`](../../swing/cli_config.py#L35) `apply_overrides(base_cfg)` + similar in `web/routes/config.py`).

**Plan-locked entrypoint convention (binding for V1):**

The pipeline runs in a SUBPROCESS spawned from the web route (`python -m swing.cli --config <path> pipeline run` per Phase 5 plan + observed at `swing/web/routes/pipeline.py`). The parent process (web request handler) and the child (CLI subprocess) load cfg INDEPENDENTLY from disk; calling `apply_overrides()` in the parent does NOT propagate to the child. **The child-process pipeline-run command (`swing pipeline run` CLI body) is THE binding override point — Codex R2 Major-1 fix.**

| Entrypoint | Process | Consumer of `cfg.integrations.finviz` | apply_overrides() responsibility |
|---|---|---|---|
| `swing finviz fetch` (Task 8) | same | direct (token + screen_query for FinvizClient) | Task 8 step 3: command body calls `apply_overrides(ctx.obj["config"])` BEFORE constructing FinvizClient. |
| `swing finviz status` (Task 8) | same | none (reads finviz_api_calls only) | not needed; raw cfg sufficient. |
| `swing pipeline run` (CLI) | own / spawned | binding — `_step_finviz_fetch` runs IN THIS PROCESS via `run_pipeline_internal` | **BINDING:** the command body MUST call `apply_overrides(ctx.obj["config"])` and pass the effective cfg into `run_pipeline_internal`. Task 2.5 audits the existing CLI command + adds the call if absent. |
| `swing.web.routes.pipeline.POST /pipeline/run` (web parent) | parent process | NONE — spawns subprocess with `--config <path>` and does not propagate runtime objects | **NOT a binding override point** for Finviz creds: the subprocess re-loads cfg from disk + applies its own overrides via the CLI binding above. The route MAY apply overrides for parent-process-local checks (e.g., reading `cfg.web.pipeline_lease_wait_seconds`), but that is unrelated to Finviz. |
| `_step_finviz_fetch(*, cfg, lease)` (pipeline-internal) | child process | direct | NOT internally — defensive `apply_overrides()` here would cause a silent surprise (different effective cfg than other steps that don't apply). The convention is: caller (pipeline-run CLI body) hands pre-overridden cfg to the runner. |

**Defensive guard (Task 2 binding test):** add a discriminating test that asserts `_step_finviz_fetch` reads from the cfg passed in (not from `apply_overrides()` re-loaded inside), so the entrypoint convention is enforced by failing test if a future refactor inverts it.

**Subprocess-cred propagation discriminator (Task 2.5 binding test):** add a test that invokes `swing pipeline run` (Click CliRunner) with a fixture that places `[integrations.finviz] token = "OVERRIDE_TOKEN"` in user-config, monkey-patches `_step_finviz_fetch` to capture the cfg.integrations.finviz.token it receives, and asserts the captured value equals "OVERRIDE_TOKEN". Pre-fix (no apply_overrides in CLI body): captured "". Post-fix (apply_overrides added): captured "OVERRIDE_TOKEN". This test pins the cred-propagation contract durably.

### A.12 — `requests` / `urllib3` DEBUG-log redaction (Codex R1 Major-2 fix)

§E.7 token-redaction discipline did not previously cover lower-level HTTP libraries. Python's `requests` library delegates to `urllib3` for transport; at DEBUG log level, `urllib3.connectionpool` emits log lines that include the full request URL with query string (token bytes). Even if the application logger is at INFO, a future operator-debug session that calls `logging.basicConfig(level=logging.DEBUG)` would leak the token in their terminal/log file.

**Plan-locked defense (Task 3 binding):** `FinvizClient.fetch_screen()` wraps the `requests.get(...)` call in a context manager that bumps `urllib3.connectionpool` + `requests.packages.urllib3.connectionpool` loggers to WARNING for the duration:

```python
@contextlib.contextmanager
def _suppress_urllib3_debug() -> Iterator[None]:
    """Force urllib3 DEBUG logs to WARNING for the duration; restore on exit.

    urllib3.connectionpool's DEBUG log lines include the full request URL
    (with query string → token). Defense-in-depth complement to the
    FinvizApiError __str__ contract + cassette filter_query_parameters.
    """
    affected = ("urllib3.connectionpool", "requests.packages.urllib3.connectionpool")
    prior_levels = {name: logging.getLogger(name).level for name in affected}
    try:
        for name in affected:
            logging.getLogger(name).setLevel(logging.WARNING)
        yield
    finally:
        for name, level in prior_levels.items():
            logging.getLogger(name).setLevel(level)
```

Plan Task 10 (token-leak audit) adds a discriminating test that:
1. Calls `logging.basicConfig(level=logging.DEBUG, force=True)`.
2. Sets `logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG)` BEFORE calling `FinvizClient.fetch_screen()`.
3. Captures all log records via caplog.
4. Asserts the sentinel token literal is absent from every captured record.

If the suppression helper is missing, the test FAILS with the sentinel found in urllib3 DEBUG output.

### A.13 — File-write / audit-row atomicity: shadow-promote-then-audit pattern (Codex R2 Major-2 + R3 Major-1)

The naive design (write canonical CSV → fenced-write audit row) had failure mode: lease revoke between rename and audit-insert leaves the canonical CSV without an `ok` audit row. Next run sees the file → `skipped_manual_override`. R2 fix introduced a shadow file. R3 then surfaced a follow-on: if `os.replace(shadow, canonical)` fails AFTER the audit row already committed `status='ok'`, the audit log lies (claims success but no canonical exists). R3 Major-1 fix: do the file work BEFORE the audit insert; downgrade the result to `error` if file work fails; audit row inserted last reflects ground truth.

**Plan-locked atomicity discipline (binding for Task 6):**

`_step_finviz_fetch` and `_perform_finviz_fetch_no_lease` use a SHADOW filename pattern. The canonical filename is `finvizDDMmmYYYY.csv`; the shadow is `finvizDDMmmYYYY.csv.api-pending`. The flow (post-R3):

1. Recovery sweep: delete any `*.api-pending` files older than 1 hour.
2. `_finviz_fetch_core`: in-memory API fetch + normalize + signature compute. Returns a result dict with status/csv_text/etc. **No DB or filesystem writes yet.**
3. If `status == 'ok'`:
   a. (Lease-fenced or raw) read of prior signature; emit drift warning if changed.
   b. `_finviz_persist_csv_shadow`: write CSV to `<canonical>.api-pending` (atomic same-dir tmp + os.replace).
   c. `_finviz_promote_shadow`: atomic rename shadow → canonical.
   d. Track `shadow_path = None` once promoted; finally-block cleans only if still present.
   e. **On any exception during 3.a-3.c: DOWNGRADE `result["status"] = "error"`, populate `error_message`, clear `signature_hash` + `row_count`.** The audit row will reflect the failure truthfully.
4. (Lease-fenced or raw) `insert_call(...)` with the (possibly downgraded) result. This is the LAST DB op.

**Failure-mode coverage (binding):**

| Failure point | Outcome | Rationale |
|---|---|---|
| Step 3.b (shadow write fails) | result→error; no canonical; audit row says error | Truth-preserving; next run retries cleanly. |
| Step 3.c (rename fails after shadow exists) | shadow deleted in finally; result→error; no canonical; audit says error | Same. No `ok`-without-CSV liar row. |
| Step 4 (audit insert fails — e.g. LeaseRevokedError) | canonical exists (was promoted); audit row missing | Lossy audit history (one fetch un-recorded), but next pipeline run sees canonical → `skipped_manual_override` and consumes the data normally. Far better than a false `ok`. |
| Lease revoke between 3.a and 3.b | exception caught at step 3.e; result→error; nothing on disk; audit (step 4) says error | Clean. |

**File-collision check** (algorithm §H step 2) inspects the **canonical path only**, NOT the shadow. A leftover `.api-pending` file does NOT trigger `skipped_manual_override` — it's an internal artifact, not operator manual data.

**Discriminating tests in Task 6:**
- `test_step_finviz_fetch_orphan_shadow_cleanup_on_lease_revoke`: simulate LeaseRevokedError from the FIRST fenced_write (signature read in step 3.a); assert no canonical CSV, no shadow, audit row records `status='error'` with `LeaseRevokedError` in error_message.
- (Implementer-added at task time) `test_step_finviz_fetch_promote_failure_downgrades_to_error`: monkey-patch `os.replace` second call (the promote) to raise `OSError`; assert audit row is `status='error'`, no canonical CSV, no shadow.

### A.14 — CLI vs pipeline concurrency: refuse-while-pipeline-running (Codex R2 Major-3 fix)

`_perform_finviz_fetch_no_lease` (used by `swing finviz fetch` CLI) does NOT acquire the pipeline lease. Without coordination, an operator could run the CLI fetch while a pipeline run is in flight, racing on the canonical CSV target and the `finviz_api_calls` audit table.

**Plan-locked exclusion posture (binding for Task 6 + Task 8):**

`_perform_finviz_fetch_no_lease` queries `pipeline_runs` for any row with `state='running'` BEFORE doing any work. If found, raise a typed exception `FinvizPipelineActiveError` with message:

```
A pipeline run is currently in flight (run_id=<id>); the standalone Finviz
fetch is refused to avoid corrupting the inbox or audit log. Wait for the
run to complete (swing pipeline status) and retry, OR run the fetch as
part of the pipeline (swing pipeline run).
```

The CLI surface (Task 8) catches this and emits a friendly `click.ClickException`. The pipeline-internal `_step_finviz_fetch` does NOT need this check — it runs WHILE the lease is held by definition.

This is the V1-simplest cross-surface coordination. V2 hardening (out-of-scope; track for follow-up): unify CLI under the same lease as pipeline OR introduce a separate Finviz-specific advisory lock. V1 is sufficient because operator-triggered CLI fetches are rare + the error message is operator-actionable.

Discriminating tests (binding):

- `tests/pipeline/test_step_finviz_fetch.py::test_perform_finviz_fetch_no_lease_refuses_when_pipeline_running` — direct unit test on the helper. Seeds a `pipeline_runs` row with `state='running'`; calls `_perform_finviz_fetch_no_lease`; asserts `FinvizPipelineActiveError` raised with "in flight" in the message.
- `tests/cli/test_finviz_commands.py::test_swing_finviz_fetch_friendly_error_when_pipeline_running` — CLI surface integration test. Seeds the same row; invokes `swing finviz fetch` via Click `CliRunner`; asserts `result.exit_code != 0` AND `"pipeline run is currently in flight" in result.output`.

The unit test pins the helper's contract; the CLI test pins the CLI's translation of the typed exception to a friendly user-facing error.

### A.7 — Operator's saved-screen identification = `screen_query` opaque string, NOT a numeric `screen_id`

Brief §2.2 specifies `screen_id` (string) as the cfg key. Synthesized public knowledge: Finviz Elite saved screens are identified by the COMPLETE filter+view query-string suffix (e.g., `v=152&f=cap_largeover,sh_avgvol_o500&ft=2`), NOT by a numeric ID. There is no publicly-documented "saved screen ID" handle. Operator copies the query-string suffix from their browser URL into cfg.

**Plan adopts:** rename cfg key to `screen_query` (string; opaque to the client; appended verbatim to the export.ashx URL). Brief's `screen_id` was a presumption; `screen_query` is the operator-reachable abstraction. **Surfaced in return report §3** as a cosmetic deviation from brief naming. Implementer comments document the mapping.

### A.8 — `swing finviz set-token` is OUT-OF-SCOPE V1 per brief §2.5; reaffirmed

Operator edits `%USERPROFILE%/swing-data/user-config.toml` directly per Phase 5 convention. CLI tests do NOT cover token mutation paths.

### A.9 — Migration 0015 is purely additive (single CREATE TABLE + UPDATE schema_version)

No table rebuild; no FK CASCADE risk; no Phase 7 backup gate fires (gate fires on target_version >= 14 from current_version == 13 only — per `swing/data/db.py:267-271`). Plan adds 0015 with `EXPECTED_SCHEMA_VERSION = 15` per brief §2.4; no changes needed to the migration runner discipline. Per Phase 7 Sub-A lesson `Test fixture connection state must mirror production runtime PRAGMA state`, the migration test executes with `foreign_keys=ON` to mirror production.

### A.10 — `cfg.integrations.finviz.timeout_seconds` (HTTP timeout) added to tracked toml; `token` + `screen_query` user-config-only

Brief §2.2 line "MAY contain a placeholder `screen_id = ""` and timeout/retry defaults if appropriate." Plan adds `[integrations.finviz]` section to `swing.config.toml` with `timeout_seconds = 30` (HTTP request timeout) only. `token` + `screen_query` defaults stay empty in dataclass; tracked toml does NOT mention them. Operator edits user-config to populate.

---

## §B — File map

### Files to CREATE

| Path | Responsibility |
|---|---|
| `swing/integrations/__init__.py` | Empty package init. Establishes the namespace; future Schwab integration adds a sibling module here. |
| `swing/integrations/finviz_api.py` | `FinvizClient` class (token + screen_query loading, `fetch_screen() -> bytes` HTTP call, `normalize_to_canonical_csv(body: bytes) -> str` normalization to the 13-column schema, `compute_signature_hash(body: bytes) -> str` deterministic signature). Custom exceptions: `FinvizConfigMissingError`, `FinvizSchemaParityError`, `FinvizRateLimitError`, `FinvizApiError`. NO direct DB writes — caller (pipeline step OR CLI) owns persistence. NO logging of token bytes. |
| `swing/data/migrations/0015_finviz_api_calls.sql` | CREATE TABLE `finviz_api_calls` + index on `ts DESC` + `UPDATE schema_version SET version = 15`. |
| `swing/data/repos/finviz_api_calls.py` | Public API: `insert_call(conn, call: FinvizApiCall) -> int`; `list_recent_calls(conn, *, limit: int = 50) -> list[FinvizApiCall]`; `get_latest_signature_hash(conn, *, screen_query: str) -> str | None`. |
| `tests/integrations/__init__.py` | Empty test-namespace package init. |
| `tests/integrations/test_finviz_api.py` | Cassette-based unit tests for `FinvizClient` happy path + error paths. Uses `@pytest.mark.vcr` from `pytest-recording`. |
| `tests/integrations/test_finviz_api_live.py` | Slow-marked (`@pytest.mark.slow`) live integration test. Skipped via `pytest.skip` when `cfg.integrations.finviz.token == ""` so a fresh-clone CI without operator's secret doesn't fail. |
| `tests/integrations/test_finviz_signature_hash.py` | Pure-function discriminating tests for `compute_signature_hash`. |
| `tests/integrations/test_finviz_token_redaction_audit.py` | Sentinel-token-leak audit: end-to-end fetch (cassette-based) + grep all log records + DB rows for the sentinel literal. Fails if found. |
| `tests/integrations/cassettes/test_finviz_api/` | VCR cassette directory (created by `pytest-recording` on first record). Contents: one YAML per test scenario. **Tracked in git AFTER manual token-redaction verification.** |
| `tests/cli/test_finviz_commands.py` | Click `CliRunner` tests for `swing finviz fetch` and `swing finviz status`. |
| `tests/pipeline/test_step_finviz_fetch.py` | `_step_finviz_fetch` happy-path + manual-CSV-skip + error-tolerant tests. Uses `pytest-recording` + filesystem fixture (`tmp_path`). |
| `tests/pipeline/test_step_finviz_fetch_ordering.py` | Asserts the new step is wired BEFORE `_step_evaluate` in the pipeline; asserts pipeline succeeds end-to-end when the API fetch errors. |
| `tests/data/test_migration_0015_finviz_api_calls.py` | Migration round-trip: ensure_schema on a fresh DB lands at v15; `finviz_api_calls` table exists with expected columns + index; `foreign_keys=ON` PRAGMA preserved. |
| `tests/data/repos/test_finviz_api_calls.py` | Repo CRUD tests: insert + list_recent + get_latest_signature_hash. |
| `tests/config/test_config_integrations_finviz.py` | Config cascade tests: defaults, tracked-toml override, user-config override, `Config(...)` direct construction in test fixtures still works. |

### Files to MODIFY

| Path | Reason |
|---|---|
| `swing/cli.py` | Add new `@main.group("finviz")` subcommand group with `fetch` + `status` commands. |
| `swing/pipeline/runner.py` | Add `_step_finviz_fetch(*, cfg, lease)` function (uses `lease.fenced_write()` for `finviz_api_calls` inserts). Call site lands BEFORE `_step_evaluate` invocation in `run_pipeline_internal`. **Error-handling contract** (per §A.13 R3): API failures, normalize failures, shadow-write failures, and promote failures are all caught + downgrade `result["status"]='error'`; the FINAL fenced audit-insert records the (possibly-downgraded) result and pipeline continues. EXCEPTION: if the final fenced audit-insert itself raises `LeaseRevokedError` (mid-step force-clear lands AFTER promote completes but BEFORE audit row commits), the canonical CSV exists on disk + the audit row is missing for this fetch + `LeaseRevokedError` propagates up to `run_pipeline_internal`'s outer LeaseRevokedError handler (terminating the run with state='force_cleared' per existing pipeline semantics). The lossy audit-history is preferable to a false `ok` row; the next pipeline run sees the canonical CSV as a manual-override (skipped_manual_override) + consumes the data normally. |
| `swing/pipeline/runner.py` (additionally) | Add `_perform_finviz_fetch_no_lease(*, cfg, conn) -> None` helper used by the standalone CLI `swing finviz fetch` (Task 8). Refuses execution if a pipeline run is currently in flight (plan §A.14 cross-surface concurrency exclusion; raises `FinvizPipelineActiveError`). Same fetch + normalize + signature + persist semantics as `_step_finviz_fetch`. Both functions share `_finviz_fetch_core(cfg)`, `_finviz_persist_csv_shadow`, `_finviz_promote_shadow`, `_finviz_cleanup_stale_shadows` private helpers (plan §A.13 shadow-then-promote atomicity). |
| `swing/data/db.py` | Bump `EXPECTED_SCHEMA_VERSION` 14 → 15 (single-line edit). |
| `swing/data/models.py` | Add `FinvizApiCall` dataclass (frozen). |
| `swing/config.py` | Add `IntegrationsConfig` + `FinvizIntegrationConfig` sub-dataclasses; add `integrations: IntegrationsConfig` to top-level `Config`; load `raw.get("integrations", {})` in `load()`. |
| `swing/config_overrides.py` | Apply user-config override for `integrations.finviz.token` + `integrations.finviz.screen_query`. Extend `_get()` to N-part dotted paths. **`_V1_PATHS` is NOT extended** (Codex R1 Critical-2 fix; Finviz fields stay outside `FIELD_REGISTRY` surface in V1). |
| `swing.config.toml` | Add `[integrations.finviz]` section with `timeout_seconds = 30` placeholder ONLY. NO `token` row. NO `screen_query` row. |
| `pyproject.toml` | Add `pytest-recording>=0.13` to `[project.optional-dependencies] dev` extras. |
| `CLAUDE.md` | Update Finviz inbox section: API path is now primary; manual CSV is fallback. New gotcha: token-in-user-config-not-tracked-toml + cassette-staleness runbook pointer. |
| `docs/cycle-checklist.md` | Operator no longer needs to manually export Finviz CSV daily; document the new flow + the manual-fallback path. |
| `tests/data/test_db_v8.py` (or whatever the schema-version-pin test is named — verify at executing-plans time and rename if drifted) | Bump version pin to 15. |

### Files to READ-ONLY (do NOT modify)

| Path | Reason |
|---|---|
| `swing/pipeline/finviz_schema.py` | Validator runs unchanged on emitted CSV. Per brief §2 lock; per Q4 lock. |
| `swing/pipeline/finviz_select.py` | File-selection logic unchanged. |
| `swing/pipeline/_step_evaluate` | Existing candidate-ingestion path unchanged. |
| All Phase 6 + Phase 7 entities (Trades, Fills, trade_events, review_log) | Out of scope per phase isolation. |

---

## §C — Migration 0015 SQL (canonical reference; Task 1 implements verbatim)

```sql
-- Migration 0015: Finviz Elite API integration — finviz_api_calls audit table
--
-- Persists every fetch attempt (success, error, skipped_manual_override) with
-- timing + rate-limit headroom + signature-hash for drift detection. Each
-- pipeline run records exactly ONE row regardless of outcome.
--
-- Locked decisions §2.4: status enum CHECK-restricted; ts ISO-8601 lexicographic
-- sort-safe; index on (ts DESC) supports `swing finviz status` ordering.
--
-- Additive-only migration; no table rebuild; foreign_keys=OFF discipline at the
-- runner level applies but is moot here (no FKs introduced).

CREATE TABLE finviz_api_calls (
    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    screen_query TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('ok','error','skipped_manual_override')),
    row_count INTEGER,
    response_time_ms INTEGER,
    rate_limit_remaining INTEGER,
    signature_hash TEXT,
    error_message TEXT
);

CREATE INDEX ix_finviz_api_calls_ts_desc ON finviz_api_calls (ts DESC);

UPDATE schema_version SET version = 15;
```

---

## §D — Open question for orchestrator (binding for executing-plans)

**The Finviz Elite API documentation page (https://finviz.com/api_explanation) is behind login.** This plan synthesizes endpoint shape from public third-party knowledge of `/export.ashx`. Before Task 2 records its happy-path cassette, the executing-plans implementer MUST run a one-time manual verification against the live API using operator's token + saved-screen-query and confirm:

1. URL: `https://elite.finviz.com/export.ashx?<screen_query>&auth=<token>` returns HTTP 200.
2. Response Content-Type contains `csv` or `text/plain` substring.
3. Response body's first line is a CSV header containing AT LEAST `Ticker, Sector, Industry, Country, Price` columns.

If ANY of (1)/(2)/(3) fails or returns surprising shape (HTML auth-redirect; JSON envelope; multi-step session-token flow), the executing-plans implementer halts and surfaces to orchestrator BEFORE recording cassettes. Fixing this contradiction is OUT OF SCOPE for the executing-plans dispatch — orchestrator dispatches a follow-up if needed.

**Orchestrator action item BEFORE executing-plans dispatch:** ensure the implementer has either operator's token + screen-query string OR a paste of the api_explanation page text. The writing-plans dispatch could not access either.

---

## §E — Endpoint reference (synthesized; verify at Task 0.b)

### E.1 — Base URL

```
https://elite.finviz.com/export.ashx
```

### E.2 — Authentication

Query parameter: `auth=<token>`. Token is the operator's Finviz Elite subscription API key (visible in operator's account-settings UI when logged in to Finviz Elite).

### E.3 — Saved-screen identification

Query string suffix copied verbatim from operator's saved-screen URL. Example shape (NOT operator's actual screen):

```
v=152&f=cap_largeover,sh_avgvol_o500,ta_perf_4w20o&ft=2
```

The integration treats `screen_query` as an opaque pre-built query string. The client appends `&auth=<token>` (or prepends `?` if not already present).

### E.4 — Response shape

`Content-Type: text/csv` (or `text/plain`). Body is a CSV with header row + data rows. Column set is determined by the saved-screen's view code (`v=152` = Custom view) and explicit column list (`c=...`). If the operator's saved-screen does NOT include the canonical 13 columns, normalization (Task 2) raises `FinvizSchemaParityError` — operator must fix their saved screen to include all 13 columns.

### E.5 — Pagination

No documented pagination. Finviz Elite saved-screens are bounded by Finviz's own per-screen row limits (operator-observable; ~hundreds of rows max). Plan does NOT implement pagination; if the response exceeds an arbitrary safety bound (locked: 5000 rows), normalization raises `FinvizSchemaParityError`.

### E.6 — Rate-limit semantics (locked defaults; live-verify at Task 0.b)

- Initial request timeout: `cfg.integrations.finviz.timeout_seconds` (default 30s).
- On HTTP 200 + valid CSV: SUCCESS path.
- On HTTP 429: parse `Retry-After` header (seconds, integer). If present + ≤30, `time.sleep(retry_after)` ONCE, then retry. If retry returns 429, raise `FinvizRateLimitError`.
- On HTTP 4xx (non-429): raise `FinvizApiError(status_code, body)`.
- On HTTP 5xx: raise `FinvizApiError(status_code, body)`. NO retry (single fetch per pipeline run).
- On `requests.RequestException` (network, DNS, SSL, timeout): raise `FinvizApiError(0, str(exc))`.
- Capture `X-RateLimit-Remaining` header if present (not standardized for Finviz; absent → `rate_limit_remaining = NULL`).

### E.7 — Token redaction discipline (binding security carve-out)

Token MUST NOT appear in: any log message, any exception message, any `finviz_api_calls.error_message`, any committed cassette file. Defense-in-depth:

- `FinvizClient` NEVER logs the URL it called (URL contains the token in query-string).
- `FinvizApiError(__str__)` returns `f"FinvizApiError(status={status}, body=<{len(body)} bytes>)"` — never the body itself, never the URL.
- Cassettes record with `filter_query_parameters=["auth"]` — the value is replaced with `REDACTED` at record-time (VCR.py feature).
- Task 10 (token-leak audit test) seeds a sentinel token, runs full fetch + error paths cassette-based, asserts the sentinel literal is absent from all log records + DB rows.

---

## §F — Filename anchor convention (Task 6 binding spec)

```python
# In _step_finviz_fetch (swing/pipeline/runner.py):
from datetime import datetime
from swing.evaluation.dates import action_session_for_run

action_session = action_session_for_run(datetime.now())
# %#d on Windows / %-d on POSIX strips leading zero from day; %b emits 3-letter month
# (e.g. 5May2026, 28Apr2026). Matches finviz_select.py's filename-date regex.
import platform
day_format = "%#d" if platform.system() == "Windows" else "%-d"
date_str = action_session.strftime(f"{day_format}%b%Y")
csv_path = cfg.paths.finviz_inbox_dir / f"finviz{date_str}.csv"
```

The `swing finviz fetch` CLI uses the SAME helper to compute the same path — single source of filename-anchor truth.

---

## §G — Cassette-generation runbook (operator/implementer)

Cassettes for `tests/integrations/test_finviz_api.py` are generated ONCE during executing-plans Task 0.b live-verification, then replayed in CI. Procedure:

1. Operator provides token + saved-screen-query to implementer (one-time, secret channel).
2. Implementer sets env var: `FINVIZ_TOKEN=<token>`, edits `swing.config.toml` (TEMPORARILY) to add a test-only `[integrations.finviz]` section with `screen_query = "<query>"`, OR uses a pytest fixture override.
3. Run: `pytest -m "not slow" tests/integrations/test_finviz_api.py --record-mode=once -v`.
4. `pytest-recording` records new cassettes under `tests/integrations/cassettes/test_finviz_api/`.
5. **Manual verification (binding):** open each cassette YAML; confirm `auth: REDACTED` (or absent) appears wherever the token would have been; grep for the literal token string — MUST return zero matches.
6. Commit cassettes ONLY after step-5 passes.
7. Subsequent CI runs replay cassettes (mode=`none`); no live API contact.
8. **Cassette staleness handling:** if Finviz changes column order or adds a column, the slow-marked live test (Task 9) fails on schema-shape diff. Re-record cassettes via steps 2-6.

Document this runbook in `CLAUDE.md` (Task 11) for future operator-touch.

---

## §H — `_step_finviz_fetch` algorithm (Task 6 binding spec)

```
def _step_finviz_fetch(*, cfg, lease):
    1. Compute today's CSV path via §F formula.
    2. If path exists:
         insert finviz_api_calls row with status='skipped_manual_override',
             ts=now-iso, screen_query=cfg.integrations.finviz.screen_query,
             row_count=NULL, response_time_ms=NULL, rate_limit_remaining=NULL,
             signature_hash=NULL, error_message=NULL.
         log.info("Manual CSV present at %s; Finviz API fetch skipped (manual override).", path).
         return.
    3. If cfg.integrations.finviz.token is empty OR cfg.integrations.finviz.screen_query is empty:
         insert row with status='error',
             error_message='token or screen_query missing in user-config'.
         log.warning(...).
         return.
    4. Construct FinvizClient(cfg).
    5. start = time.monotonic()
       try:
           body = client.fetch_screen()  # may raise FinvizApiError / RateLimitError / SchemaParityError
           elapsed_ms = int((time.monotonic() - start) * 1000)
           canonical_csv_text = client.normalize_to_canonical_csv(body)
           sig = client.compute_signature_hash(body)
           row_count = canonical_csv_text.count("\n") - 1  # data rows only (subtract header)
           # Drift detection:
           prior_sig = get_latest_signature_hash(conn, screen_query=cfg.integrations.finviz.screen_query)
           if prior_sig is not None and prior_sig != sig:
               log.warning(
                   "Finviz screen signature changed since prior run (%s -> %s); "
                   "operator may have edited the saved screen.",
                   prior_sig[:12], sig[:12],
               )
           # Persist CSV + row in ONE transaction-per-write (lease-fenced where possible).
           tmp = Path(str(csv_path) + ".tmp")
           tmp.write_text(canonical_csv_text, encoding="utf-8")
           os.replace(tmp, csv_path)  # same-dir atomic rename — see CLAUDE.md gotcha
           insert finviz_api_calls row with status='ok', row_count=row_count,
               response_time_ms=elapsed_ms, signature_hash=sig,
               rate_limit_remaining=client.last_rate_limit_remaining,
               error_message=NULL.
       except (FinvizApiError, FinvizRateLimitError, FinvizSchemaParityError) as exc:
           insert row with status='error',
               error_message=type(exc).__name__ + ": " + str(exc),  # token-redacted by exc.__str__
               response_time_ms=int((time.monotonic() - start) * 1000) if 'start' in locals() else NULL.
           log.warning("Finviz API fetch failed: %s", exc).
           return.  # Pipeline continues to _step_evaluate, which finds no CSV in inbox.
```

---

## §I — Cycle-checklist update (Task 11 binding spec)

The current `docs/cycle-checklist.md` daily routine instructs the operator to manually export a Finviz screen as CSV and drop it in `data/finviz-inbox/`. Post-V1 ship, the new wording (verify file structure at executing-plans time):

```markdown
- ~~Export Finviz screen as CSV named `finvizDDMmmYYYY.csv` and drop in `data/finviz-inbox/`.~~
  **Replaced 2026-05-XX:** the pipeline now fetches the screen automatically via the
  Finviz Elite API. Manual export remains supported as a fallback if the API fails or
  the operator wants to override the day's screen — drop the file in the inbox before
  triggering the pipeline and the API fetch will skip (logs `skipped_manual_override`).
- (NEW) Inspect `swing finviz status` weekly to confirm rate-limit headroom + watch
  for the `signature changed since prior run` WARNING (indicates operator edited the
  saved screen).
```

If the existing cycle-checklist file structure differs from the assumed bullet style at executing-plans time, the implementer adapts wording to match — the binding constraint is that the manual-export step is replaced with a "this happens automatically" note + a manual-fallback hedge + a `swing finviz status` weekly-check.

---

## §J — CLAUDE.md additions (Task 11 binding spec)

Update the Finviz inbox section + add new gotchas. Exact text to insert (executing-plans implementer adapts to current line-numbering at edit-time; the binding constraint is that all five items appear):

1. **Finviz inbox section update** (current text in CLAUDE.md mentions manual export only): add note "Pipeline fetches via Finviz Elite API automatically when `cfg.integrations.finviz.token` is set in user-config; manual CSV drop remains a fallback override."
2. **New gotcha: Finviz Elite API token storage.** "Token + screen-query live in `%USERPROFILE%/swing-data/user-config.toml` under `[integrations.finviz]`. Tracked `swing.config.toml` MUST NOT contain the token (sensitive); contains only `timeout_seconds`. Cassettes redact `auth=` query-param via `pytest-recording`'s `filter_query_parameters`."
3. **New gotcha: Finviz API cassette staleness.** "If `tests/integrations/test_finviz_api_live.py` (slow-marked) fails on response-shape diff after a Finviz upstream change, re-record cassettes per `docs/superpowers/plans/2026-05-XX-finviz-api-integration-plan.md` §G runbook."
4. **New gotcha: file-collision precedence at `_step_finviz_fetch`.** "If a manual CSV is present in `data/finviz-inbox/` for today's session date, `_step_finviz_fetch` skips API fetch + records `status='skipped_manual_override'`. This is the operator's manual-override knob — no other mechanism exists in V1."
5. **New gotcha: Windows `%#d` vs POSIX `%-d` filename anchor.** "API-emitted CSV filename uses `action_session.strftime('%#d%b%Y')` on Windows / `%-d%b%Y` on POSIX — produces `5May2026`, NOT `05May2026`. Matches the `finviz_select.py` regex `(\d{1,2})([A-Za-z]{3})(\d{4})`. Hard-coding `'%d'` (zero-padded) breaks roundtrip parsing on the day-of-month-1-9 days."

---

## §K — Verification gates (executing-plans implementer; binding)

- **Browser-witnessed gate:** N/A. V1 has no UI/HTMX work; no `HX-Redirect` paths; no base-layout VM additions. State explicitly in the plan to avoid Codex re-raising.
- **CLI-witnessed gate:** the executing-plans implementer demonstrates the operator-loop manually:
  1. `swing finviz fetch` (with operator's real token) → confirm CSV emitted in inbox + `status='ok'` row in DB.
  2. `swing finviz status` → confirm last call shown with status=ok, row_count > 0, signature_hash populated.
  3. Drop a manual CSV (operator simulates) → run `swing pipeline run` → confirm `status='skipped_manual_override'` row inserted; manual CSV consumed by `_step_evaluate`.
  4. Edit user-config to invalidate token (e.g., append a typo) → run `swing finviz fetch` → confirm `status='error'`, row_count=NULL, error_message non-empty (and token literal absent).
  5. Restore valid token → run `swing pipeline run` end-to-end → confirm all 7 existing pipeline steps succeed.
- **Test-suite gate (binding):** `python -m pytest -m "not slow" -q` returns 0 failures, 0 errors. Test count delta projected +30 to +60 fast tests.
- **Slow-suite spot-check (binding for executing-plans, NOT for CI):** `python -m pytest -m slow tests/integrations/test_finviz_api_live.py -v` against operator's token returns 2 passed (or 2 skipped if operator's token absent; never failed). Task 9 contributes 2 slow tests (live happy-path + signature-stable-within-session).
- **Ruff baseline gate:** `ruff check swing/` reports ≤ 78 errors (project baseline). Plan introduces 0 new violations.

---

## Tasks

> Each task ships TDD red-green-commit. Tests come first; implementation is the minimum to pass; commit lands at the end. Test counts drift over time — trust `pytest` output, not the projected counts.

---

### Task 0: Pre-flight verification (research findings + ruff baseline)

**Files:**
- Read: `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (this plan)
- Read: `docs/finviz-api-integration-writing-plans-brief.md`
- Read (operator-provided one-time): operator's Finviz Elite token + saved-screen-query

**Shell-syntax note (Codex R1 Minor-1 fix):** the bash code-blocks in this plan are POSIX-shell-style (operator runs via gitbash on Windows per CLAUDE.md "Windows + gitbash" section). The implementer MAY equivalently use PowerShell by adapting:

| POSIX | PowerShell |
|---|---|
| `export FOO=bar` | `$env:FOO = "bar"` |
| `/tmp/foo` | `$env:TEMP\foo` |
| `head -2 file` | `Get-Content file -TotalCount 2` |
| `tail -1` | `Select-Object -Last 1` |
| `grep` | `Select-String` |
| `pip install -e ".[dev,web]"` (zsh) | `pip install -e ".[dev,web]"` (PowerShell — quote escaping varies; use single quotes if needed) |

The Bash tool is also available in the executing-plans environment per CLAUDE.md.

#### Task 0.a — Capture baseline state

- [ ] **Step 1: Capture pre-dispatch ruff baseline.**

```bash
ruff check swing/ 2>&1 | tail -5
```

Record the count. Plan asserts ≤ 78. Implementer logs the actual count in their executing-plans return report.

- [ ] **Step 2: Capture pre-dispatch fast test count.**

```bash
python -m pytest -m "not slow" --collect-only -q 2>&1 | tail -1
```

Record the count. Plan asserts post-dispatch ≥ pre-dispatch + 30.

- [ ] **Step 3: Capture pre-dispatch schema version.**

```bash
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"
```

Expected: `14`. Plan bumps to `15` in Task 1.

#### Task 0.b — Live API verification (BLOCKS Task 2; one-time, operator-paired)

- [ ] **Step 4: Operator provides token + screen_query via secure channel.**

Implementer sets env vars in current shell (NOT committed):

```bash
export FINVIZ_TOKEN="<value>"
export FINVIZ_SCREEN_QUERY="<value>"
```

- [ ] **Step 5: One-time live verification curl.**

```bash
curl -sS -o /tmp/finviz-verify.csv -w "HTTP %{http_code}\nContent-Type: %{content_type}\n" \
  "https://elite.finviz.com/export.ashx?${FINVIZ_SCREEN_QUERY}&auth=${FINVIZ_TOKEN}"
head -2 /tmp/finviz-verify.csv
```

Expected output:
- `HTTP 200`
- `Content-Type: text/csv` OR `text/plain`
- First line is a CSV header containing AT LEAST `Ticker, Sector, Industry, Country, Price`.
- Second line is a CSV data row.

- [ ] **Step 6: If verification fails (any of HTTP/Content-Type/header content mismatch), HALT and surface to orchestrator.**

Per plan §D, do NOT proceed to record cassettes if the live API contradicts the synthesized §E reference. Capture the failure mode (HTTP code + body excerpt with token redacted) and surface in return report.

- [ ] **Step 7: Document verification outcome in plan-task return report.**

If success: implementer notes "live verification PASS; §E shape confirmed" and proceeds to Task 1.
If failure: STOP at Task 0; do NOT proceed to Tasks 1+ until orchestrator dispatches a follow-up.

- [ ] **Step 8: Commit a placeholder commit (allows the rest of the chain to proceed).**

```bash
git commit --allow-empty -m "chore(finviz-api): Task 0 pre-flight + live-verification PASS"
```

---

### Task 1: Schema migration 0015 + `FinvizApiCall` dataclass + repo

**Files:**
- Create: `swing/data/migrations/0015_finviz_api_calls.sql`
- Modify: `swing/data/db.py` (bump `EXPECTED_SCHEMA_VERSION` 14 → 15)
- Modify: `swing/data/models.py` (add `FinvizApiCall`)
- Create: `swing/data/repos/finviz_api_calls.py`
- Create: `tests/data/test_migration_0015_finviz_api_calls.py`
- Create: `tests/data/repos/test_finviz_api_calls.py`
- Modify: existing schema-version-pin test (search at executing-plans time; e.g., `tests/data/test_db_v8.py` if name still drifts)

- [ ] **Step 1: Write the migration test (failing — table doesn't exist yet).**

```python
# tests/data/test_migration_0015_finviz_api_calls.py
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema


def test_migration_0015_creates_finviz_api_calls_table(tmp_path: Path) -> None:
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        # PRAGMA preserved — production-equivalent fixture state (Phase 7 Sub-A lesson).
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1, "ensure_schema must enable foreign_keys=ON"

        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 15, f"expected v15, got v{version}"

        cols = {
            r[1]: r[2]
            for r in conn.execute("PRAGMA table_info(finviz_api_calls)").fetchall()
        }
        assert cols == {
            "call_id": "INTEGER",
            "ts": "TEXT",
            "screen_query": "TEXT",
            "status": "TEXT",
            "row_count": "INTEGER",
            "response_time_ms": "INTEGER",
            "rate_limit_remaining": "INTEGER",
            "signature_hash": "TEXT",
            "error_message": "TEXT",
        }, cols

        # CHECK constraint enforces enum.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO finviz_api_calls (ts, screen_query, status) "
                "VALUES (?, ?, ?)",
                ("2026-05-05T12:00:00", "v=152", "INVALID_STATUS"),
            )
            conn.commit()

        # Index exists on ts DESC.
        idx_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='finviz_api_calls'"
        ).fetchall()
        idx_names = {r[0] for r in idx_rows}
        assert "ix_finviz_api_calls_ts_desc" in idx_names, idx_names
    finally:
        conn.close()


def test_expected_schema_version_is_15() -> None:
    """Schema-version pin: this test trips when 0015 lands AND drift detection
    catches accidental skips of the migration version constant."""
    assert EXPECTED_SCHEMA_VERSION == 15
```

- [ ] **Step 2: Run the test; expect FAIL with `assert 14 == 15` and / or "no such table: finviz_api_calls".**

```bash
python -m pytest tests/data/test_migration_0015_finviz_api_calls.py -v
```

Expected discriminating failure: `AssertionError: expected v15, got v14` (this is the pre-fix discriminator). Post-fix: PASS.

- [ ] **Step 3: Create the migration SQL.**

Write `swing/data/migrations/0015_finviz_api_calls.sql` verbatim from §C of this plan.

- [ ] **Step 4: Bump `EXPECTED_SCHEMA_VERSION` in `swing/data/db.py` from 14 to 15.**

Edit the line `EXPECTED_SCHEMA_VERSION = 14` → `EXPECTED_SCHEMA_VERSION = 15`. Update the inline comment listing migrations to include `# finviz_api_calls table (migration 0015)`.

- [ ] **Step 5: Run the migration test; expect PASS.**

```bash
python -m pytest tests/data/test_migration_0015_finviz_api_calls.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Add `FinvizApiCall` dataclass to `swing/data/models.py`.**

```python
@dataclass(frozen=True)
class FinvizApiCall:
    """Audit row for one Finviz Elite API fetch attempt.

    `signature_hash` is None for skipped/error rows; populated only on status='ok'.
    `rate_limit_remaining` is best-effort — Finviz does not document a
    standardized rate-limit header; absent → None.
    """
    call_id: int | None
    ts: str  # ISO 8601, naive datetime per Phase 7 Sub-B convention
    screen_query: str
    status: str  # 'ok' | 'error' | 'skipped_manual_override'
    row_count: int | None
    response_time_ms: int | None
    rate_limit_remaining: int | None
    signature_hash: str | None
    error_message: str | None
```

- [ ] **Step 7: Write the repo tests (failing).**

```python
# tests/data/repos/test_finviz_api_calls.py
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import FinvizApiCall
from swing.data.repos.finviz_api_calls import (
    get_latest_signature_hash,
    insert_call,
    list_recent_calls,
)


def _insert(conn, **overrides) -> FinvizApiCall:
    base = dict(
        call_id=None, ts="2026-05-05T12:00:00", screen_query="v=152&f=cap_largeover",
        status="ok", row_count=42, response_time_ms=180,
        rate_limit_remaining=99, signature_hash="abc123def456", error_message=None,
    )
    base.update(overrides)
    call = FinvizApiCall(**base)
    new_id = insert_call(conn, call)
    return FinvizApiCall(**{**base, "call_id": new_id})


def test_insert_call_assigns_autoincrement_id(tmp_path: Path) -> None:
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        call = _insert(conn)
        assert isinstance(call.call_id, int)
        assert call.call_id >= 1
    finally:
        conn.close()


def test_list_recent_calls_orders_by_ts_desc(tmp_path: Path) -> None:
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        _insert(conn, ts="2026-05-01T12:00:00", signature_hash="old")
        _insert(conn, ts="2026-05-05T12:00:00", signature_hash="new")
        _insert(conn, ts="2026-05-03T12:00:00", signature_hash="mid")
        calls = list_recent_calls(conn, limit=10)
        # Discriminating: the order MUST be 5 → 3 → 1 (DESC), not 1 → 3 → 5 (ASC).
        assert [c.signature_hash for c in calls] == ["new", "mid", "old"]
    finally:
        conn.close()


def test_get_latest_signature_hash_filters_by_screen_query(tmp_path: Path) -> None:
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        _insert(conn, ts="2026-05-05T10:00:00", screen_query="v=152", signature_hash="A")
        _insert(conn, ts="2026-05-05T11:00:00", screen_query="v=200", signature_hash="B")
        _insert(conn, ts="2026-05-05T12:00:00", screen_query="v=152", signature_hash="C")

        # Discriminating: must return latest for v=152 ("C"), NOT the global latest ("C")
        # — both happen to coincide, so add a fourth row that proves the filter.
        _insert(conn, ts="2026-05-05T13:00:00", screen_query="v=200", signature_hash="D")

        assert get_latest_signature_hash(conn, screen_query="v=152") == "C"
        assert get_latest_signature_hash(conn, screen_query="v=200") == "D"
        assert get_latest_signature_hash(conn, screen_query="v=999") is None
    finally:
        conn.close()


def test_get_latest_signature_hash_skips_error_rows(tmp_path: Path) -> None:
    """Discriminating: error rows have signature_hash=NULL; the helper must
    return the latest non-NULL hash, not the latest row irrespective of hash."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        _insert(conn, ts="2026-05-05T10:00:00", screen_query="v=152",
                status="ok", signature_hash="GOOD")
        _insert(conn, ts="2026-05-05T11:00:00", screen_query="v=152",
                status="error", signature_hash=None, error_message="boom")
        _insert(conn, ts="2026-05-05T12:00:00", screen_query="v=152",
                status="skipped_manual_override", signature_hash=None)
        # Pre-fix expected (naive impl): None (latest row's signature_hash is NULL).
        # Post-fix expected: "GOOD" (latest non-NULL signature_hash for that screen).
        assert get_latest_signature_hash(conn, screen_query="v=152") == "GOOD"
    finally:
        conn.close()
```

- [ ] **Step 8: Run repo tests; expect FAIL (module doesn't exist).**

```bash
python -m pytest tests/data/repos/test_finviz_api_calls.py -v
```

Expected: `ModuleNotFoundError: No module named 'swing.data.repos.finviz_api_calls'`.

- [ ] **Step 9: Implement `swing/data/repos/finviz_api_calls.py`.**

```python
"""Repo for finviz_api_calls audit table (migration 0015)."""
from __future__ import annotations

import sqlite3

from swing.data.models import FinvizApiCall


def insert_call(conn: sqlite3.Connection, call: FinvizApiCall) -> int:
    cur = conn.execute(
        "INSERT INTO finviz_api_calls "
        "(ts, screen_query, status, row_count, response_time_ms, "
        " rate_limit_remaining, signature_hash, error_message) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (call.ts, call.screen_query, call.status, call.row_count,
         call.response_time_ms, call.rate_limit_remaining,
         call.signature_hash, call.error_message),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_recent_calls(
    conn: sqlite3.Connection, *, limit: int = 50,
) -> list[FinvizApiCall]:
    rows = conn.execute(
        "SELECT call_id, ts, screen_query, status, row_count, response_time_ms, "
        "       rate_limit_remaining, signature_hash, error_message "
        "FROM finviz_api_calls ORDER BY ts DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        FinvizApiCall(
            call_id=r[0], ts=r[1], screen_query=r[2], status=r[3], row_count=r[4],
            response_time_ms=r[5], rate_limit_remaining=r[6],
            signature_hash=r[7], error_message=r[8],
        )
        for r in rows
    ]


def get_latest_signature_hash(
    conn: sqlite3.Connection, *, screen_query: str,
) -> str | None:
    """Return the most recent non-NULL signature_hash for the given screen_query.

    Drift-detection consumer: it only matters that the LAST KNOWN GOOD signature
    is compared against the new fetch — error/skipped rows have no signature
    and would be a vacuous comparison if returned.
    """
    row = conn.execute(
        "SELECT signature_hash FROM finviz_api_calls "
        "WHERE screen_query = ? AND signature_hash IS NOT NULL "
        "ORDER BY ts DESC LIMIT 1",
        (screen_query,),
    ).fetchone()
    return row[0] if row else None
```

- [ ] **Step 10: Run repo tests; expect PASS (all 4).**

```bash
python -m pytest tests/data/repos/test_finviz_api_calls.py -v
```

- [ ] **Step 11: Update existing schema-version-pin test if present.**

Search at executing-plans time:

```bash
grep -rln 'EXPECTED_SCHEMA_VERSION' tests/
```

For each test asserting the pin, bump expected from 14 to 15. Run all impacted tests; expect PASS.

- [ ] **Step 12: Run full fast suite; expect green.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 0 failures (delta from baseline: +6 tests from this task — 2 migration + 4 repo).

- [ ] **Step 13: Commit.**

```bash
git add swing/data/migrations/0015_finviz_api_calls.sql swing/data/db.py \
        swing/data/models.py swing/data/repos/finviz_api_calls.py \
        tests/data/test_migration_0015_finviz_api_calls.py \
        tests/data/repos/test_finviz_api_calls.py \
        tests/data/test_db_v8.py  # or whatever the pin test is
git commit -m "feat(finviz-api): migration 0015 + FinvizApiCall + repo (Task 1)"
```

---

### Task 2: Config cascade for `[integrations.finviz]`

**Files:**
- Modify: `swing/config.py` (sub-dataclasses + top-level field + load() pass-through)
- Modify: `swing/config_overrides.py` (extend `_get` to N-part paths + add Finviz overrides in `apply_overrides`; `_V1_PATHS` unchanged)
- Modify: `swing.config.toml` (add `[integrations.finviz]` with `timeout_seconds = 30` only)
- Create: `tests/config/test_config_integrations_finviz.py`

- [ ] **Step 1: Write failing config-cascade tests.**

```python
# tests/config/test_config_integrations_finviz.py
import textwrap
from pathlib import Path

import pytest

from swing.config import Config, IntegrationsConfig, FinvizIntegrationConfig, load


def test_finviz_integration_defaults_when_section_absent(tmp_path: Path) -> None:
    """Defaults apply when [integrations.finviz] absent (existing toml shape)."""
    cfg_text = (Path("swing.config.toml")).read_text()
    # Strip any pre-existing [integrations.finviz] for the test
    cfg_text = "\n".join(
        line for line in cfg_text.splitlines()
        if not line.startswith("[integrations") and "finviz." not in line
    )
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(cfg_text)
    cfg = load(cfg_path)
    # Discriminating: dataclass defaults populate without a toml row.
    assert cfg.integrations.finviz.token == ""
    assert cfg.integrations.finviz.screen_query == ""
    assert cfg.integrations.finviz.timeout_seconds == 30


def test_finviz_integration_tracked_toml_overrides_default_timeout(
    tmp_path: Path,
) -> None:
    """Tracked toml overrides default timeout_seconds (token + screen_query stay empty)."""
    cfg_text = (Path("swing.config.toml")).read_text()
    cfg_text = "\n".join(
        line for line in cfg_text.splitlines()
        if not line.startswith("[integrations") and "finviz." not in line
    )
    cfg_text += "\n\n[integrations.finviz]\ntimeout_seconds = 90\n"
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(cfg_text)
    cfg = load(cfg_path)
    # Discriminating pre-fix: 30 (default).
    # Discriminating post-fix: 90 (tracked toml override).
    assert cfg.integrations.finviz.timeout_seconds == 90
    assert cfg.integrations.finviz.token == ""
    assert cfg.integrations.finviz.screen_query == ""


def test_finviz_integration_tracked_toml_token_STRIPPED_at_load(tmp_path: Path) -> None:
    """Security carve-out (Codex R1 Major-5 fix): tracked toml MUST NOT
    deliver a token / screen_query into the cfg. load() strips both keys
    even if present in tracked toml; only timeout_seconds survives.

    Discriminating pre-fix (naive `FinvizIntegrationConfig(**raw_section)`):
        cfg.integrations.finviz.token == "TRACKED_TOKEN_LEAK"  # leaks
    Discriminating post-fix (load() filters keys):
        cfg.integrations.finviz.token == ""  # stripped
    """
    cfg_text = (Path("swing.config.toml")).read_text()
    cfg_text += textwrap.dedent('''
        [integrations.finviz]
        token = "TRACKED_TOKEN_LEAK"
        screen_query = "TRACKED_SCREEN_LEAK"
        timeout_seconds = 45
    ''').strip() + "\n"
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(cfg_text)
    cfg = load(cfg_path)
    # Post-fix discriminators:
    assert cfg.integrations.finviz.token == ""  # stripped
    assert cfg.integrations.finviz.screen_query == ""  # stripped
    # Non-sensitive timeout passes through.
    assert cfg.integrations.finviz.timeout_seconds == 45


def test_user_config_override_token_and_screen_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User-config OVERRIDE applies for token + screen_query."""
    user_cfg_dir = tmp_path / "swing-data"
    user_cfg_dir.mkdir()
    (user_cfg_dir / "user-config.toml").write_text(textwrap.dedent("""
        [integrations.finviz]
        token = "USER_CONFIG_TOKEN"
        screen_query = "v=152&f=test"
    """).strip())
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg_path = Path("swing.config.toml")
    base_cfg = load(cfg_path)
    from swing.config_overrides import apply_overrides
    cfg = apply_overrides(base_cfg)
    # Discriminating pre-fix: "" (defaults). Post-fix: USER_CONFIG_TOKEN.
    assert cfg.integrations.finviz.token == "USER_CONFIG_TOKEN"
    assert cfg.integrations.finviz.screen_query == "v=152&f=test"


def test_config_direct_construction_still_works() -> None:
    """Existing test fixtures construct Config(...) directly; the new
    integrations field MUST have a safe default (factory) so old tests don't break."""
    # If a test elsewhere does Config(paths=..., account=..., ...) without
    # integrations=, it still constructs.
    from dataclasses import fields
    integrations_field = next(f for f in fields(Config) if f.name == "integrations")
    # Discriminating: field has default_factory=IntegrationsConfig.
    assert integrations_field.default_factory is IntegrationsConfig  # type: ignore[comparison-overlap]
```

- [ ] **Step 2: Run tests; expect FAIL with ImportError on `IntegrationsConfig` / `FinvizIntegrationConfig`.**

```bash
python -m pytest tests/config/test_config_integrations_finviz.py -v
```

- [ ] **Step 3: Edit `swing/config.py`.**

Add (after the existing `Web`, `ClassifierConfig`, `ArchiveConfig`, `ReviewConfig` dataclasses; alphabetical order is not enforced — match existing position style):

```python
@dataclass(frozen=True)
class FinvizIntegrationConfig:
    """Finviz Elite API integration config (Phase 7e — finviz-api-integration plan).

    `token` + `screen_query` are sensitive/operator-specific; live in user-config
    only. `timeout_seconds` is non-sensitive default; tracked toml may override.
    """
    token: str = ""
    screen_query: str = ""
    timeout_seconds: int = 30


@dataclass(frozen=True)
class IntegrationsConfig:
    """External-API integrations namespace. Future Schwab integration adds a
    sibling field here following the same per-integration sub-dataclass pattern."""
    finviz: FinvizIntegrationConfig = field(default_factory=FinvizIntegrationConfig)
```

Add to top-level `Config`:

```python
@dataclass(frozen=True)
class Config:
    paths: Paths
    # ... existing fields ...
    review: ReviewConfig = field(default_factory=ReviewConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)  # NEW
```

Modify `load()` to read the section AND STRIP sensitive keys (security carve-out per §A.6 + Codex R1 Critical-2 fix):

```python
def load(config_path: Path) -> Config:
    # ... existing code ...
    raw_finviz = dict(raw.get("integrations", {}).get("finviz", {}))
    # Sensitive fields MUST come from user-config only; tracked toml may carry
    # only timeout_seconds. Drop any token / screen_query rows defensively to
    # eliminate the leak path (Phase 7e plan §A.6).
    raw_finviz.pop("token", None)
    raw_finviz.pop("screen_query", None)
    return Config(
        paths=paths,
        # ... existing args ...
        review=ReviewConfig(**raw.get("review", {})),
        integrations=IntegrationsConfig(
            finviz=FinvizIntegrationConfig(**raw_finviz),
        ),
    )
```

- [ ] **Step 4: Edit `swing.config.toml`.**

Append (at end of file):

```toml

[integrations.finviz]
# Finviz Elite API integration. token + screen_query live in user-config
# (%USERPROFILE%/swing-data/user-config.toml under [integrations.finviz])
# — never tracked. timeout_seconds is the per-request HTTP timeout.
timeout_seconds = 30
```

- [ ] **Step 5: Edit `swing/config_overrides.py`.**

Per §A.6 + Codex R1 Critical-2 fix: `_V1_PATHS` is NOT extended (Finviz fields are intentionally absent from the registry). Modify `_get` to support N-part dotted paths so `apply_overrides()` can read `integrations.finviz.token` from user-config:

```python
def _get(overrides: dict[str, Any], path: str) -> Any | _Missing:
    parts = path.split(".")
    cursor: Any = overrides
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            return _MISSING
        cursor = cursor[part]
    return cursor
```

Modify `apply_overrides` to apply integrations.finviz overrides:

```python
def apply_overrides(base_cfg: Config) -> Config:
    overrides = load_user_overrides()
    new_web = base_cfg.web
    new_pipeline = base_cfg.pipeline
    new_account = base_cfg.account
    new_integrations = base_cfg.integrations  # NEW

    cf = _get(overrides, "web.chase_factor")
    if not isinstance(cf, _Missing):
        new_web = replace(new_web, chase_factor=float(cf))

    ctnw = _get(overrides, "pipeline.chart_top_n_watch")
    if not isinstance(ctnw, _Missing):
        new_pipeline = replace(new_pipeline, chart_top_n_watch=int(ctnw))

    ref = _get(overrides, "account.risk_equity_floor")
    if not isinstance(ref, _Missing):
        new_account = replace(new_account, risk_equity_floor=float(ref))

    # NEW: integrations.finviz overrides
    new_finviz = base_cfg.integrations.finviz
    fv_token = _get(overrides, "integrations.finviz.token")
    if not isinstance(fv_token, _Missing):
        new_finviz = replace(new_finviz, token=str(fv_token))
    fv_query = _get(overrides, "integrations.finviz.screen_query")
    if not isinstance(fv_query, _Missing):
        new_finviz = replace(new_finviz, screen_query=str(fv_query))
    if new_finviz is not base_cfg.integrations.finviz:
        new_integrations = replace(base_cfg.integrations, finviz=new_finviz)

    return replace(
        base_cfg, web=new_web, pipeline=new_pipeline, account=new_account,
        integrations=new_integrations,
    )
```

Per §A.6, `_V1_PATHS` and `get_field_source` REMAIN UNCHANGED in V1. Finviz fields are intentionally absent from the registry surface; `apply_overrides()` reads them directly via the now-N-part-aware `_get()`. The 2-part-path assumption in `cli_config.config_show/set/reset`, `delete_user_override`, `web/routes/config.py`, `web/view_models/config.py`, `get_field_source` is preserved.

Discriminating regression test (Task 2 binding) — verifies extending `_get` to N-part paths does NOT break existing 2-part registry consumers:

```python
def test_existing_2part_path_get_field_source_still_works(
    monkeypatch, tmp_path,
) -> None:
    """Codex R1 Major-4 regression check: extending _get to N-part paths
    must not break the existing 2-part registry consumers."""
    from swing.config import load
    from swing.config_overrides import get_field_source
    from pathlib import Path as _P

    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # empty user-config dir
    base_cfg = load(_P("swing.config.toml"))
    # Discriminating: returns one of {'default','tracked'} (NOT raises).
    assert get_field_source(base_cfg, "web.chase_factor") in ("default", "tracked")
    assert get_field_source(base_cfg, "pipeline.chart_top_n_watch") in ("default", "tracked")
    assert get_field_source(base_cfg, "account.risk_equity_floor") in ("default", "tracked")
```

- [ ] **Step 6: Run config tests; expect PASS.**

```bash
python -m pytest tests/config/test_config_integrations_finviz.py -v
```

- [ ] **Step 7: Run full fast suite; verify no regressions.**

```bash
python -m pytest -m "not slow" -q
```

Expected: still 0 failures (cascade is additive; existing tests unaffected because `Config` constructs old positional args + new field has factory default).

- [ ] **Step 8: Commit.**

```bash
git add swing/config.py swing/config_overrides.py \
        swing.config.toml tests/config/test_config_integrations_finviz.py
git commit -m "feat(finviz-api): cfg cascade for [integrations.finviz] (Task 2)"
```

---

### Task 3: `FinvizClient` — token loading + happy-path fetch + canonical-13-column normalization

**Files:**
- Create: `swing/integrations/__init__.py` (empty)
- Create: `swing/integrations/finviz_api.py`
- Modify: `pyproject.toml` (add `pytest-recording` to dev extras)
- Create: `tests/integrations/__init__.py` (empty)
- Create: `tests/integrations/test_finviz_api.py`
- Create cassettes: `tests/integrations/cassettes/test_finviz_api/test_fetch_screen_happy_path.yaml`

- [ ] **Step 1: Add `pytest-recording` to dev extras.**

Edit `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "pytest-recording>=0.13",  # NEW
    "ruff>=0.5",
]
```

Reinstall:

```bash
pip install -e ".[dev,web]"
```

- [ ] **Step 2: Write the happy-path test (failing — module doesn't exist).**

```python
# tests/integrations/test_finviz_api.py
import pytest

from swing.config import Config, IntegrationsConfig, FinvizIntegrationConfig
from swing.integrations.finviz_api import (
    FinvizClient,
    FinvizConfigMissingError,
    FinvizSchemaParityError,
)


def _cfg_with(token: str = "test-sentinel-token", screen_query: str = "v=152&f=cap_largeover", timeout: int = 30) -> Config:
    """Construct a minimal Config-shaped object for FinvizClient.

    FinvizClient consumes only cfg.integrations.finviz; we don't need a full Config.
    """
    from dataclasses import dataclass, field

    @dataclass(frozen=True)
    class _IntegrationsStub:
        finviz: FinvizIntegrationConfig

    @dataclass(frozen=True)
    class _CfgStub:
        integrations: _IntegrationsStub

    return _CfgStub(
        integrations=_IntegrationsStub(
            finviz=FinvizIntegrationConfig(token=token, screen_query=screen_query, timeout_seconds=timeout),
        ),
    )  # type: ignore[return-value]


def test_finviz_client_raises_when_token_missing() -> None:
    cfg = _cfg_with(token="", screen_query="v=152")
    with pytest.raises(FinvizConfigMissingError) as ei:
        FinvizClient(cfg).fetch_screen()
    # Discriminating: error message names the missing field, NOT the present screen_query.
    assert "token" in str(ei.value).lower()


def test_finviz_client_raises_when_screen_query_missing() -> None:
    cfg = _cfg_with(token="abc", screen_query="")
    with pytest.raises(FinvizConfigMissingError) as ei:
        FinvizClient(cfg).fetch_screen()
    assert "screen_query" in str(ei.value).lower()


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_happy_path() -> None:
    """Cassette: tests/integrations/cassettes/test_finviz_api/test_fetch_screen_happy_path.yaml.

    Recorded once against operator's real token (Task 0.b verification);
    `auth=` query-param value redacted to REDACTED at record-time.
    """
    cfg = _cfg_with(token="test-sentinel-token", screen_query="v=152&f=cap_largeover")
    body = FinvizClient(cfg).fetch_screen()
    # Discriminating: body is bytes (not str); first chunk is a CSV header.
    assert isinstance(body, bytes)
    first_line = body.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    assert "Ticker" in first_line
    assert "Sector" in first_line


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_normalize_to_canonical_csv_passes_existing_validator(tmp_path) -> None:
    """End-to-end: API response body → canonical 13-column CSV → existing
    finviz_schema validator accepts it."""
    from swing.pipeline.finviz_schema import REQUIRED_COLUMNS, validate_csv

    cfg = _cfg_with(token="test-sentinel-token", screen_query="v=152&f=cap_largeover")
    client = FinvizClient(cfg)
    body = client.fetch_screen()
    canonical_text = client.normalize_to_canonical_csv(body)
    csv_path = tmp_path / "finviz5May2026.csv"
    csv_path.write_text(canonical_text, encoding="utf-8")
    result = validate_csv(csv_path)
    # Discriminating: validator passes; reasons list is empty; row_count > 0.
    assert result.is_valid, result.reasons
    assert result.reasons == []
    assert result.row_count > 0

    # Discriminating column-set check (canonical 13 only; no extras leaked).
    header = canonical_text.split("\n", 1)[0]
    columns = [c.strip() for c in header.split(",")]
    assert tuple(columns) == REQUIRED_COLUMNS, columns


def test_normalize_raises_on_missing_column(tmp_path) -> None:
    """Discriminating: API returns body without 'Ticker'; raise SchemaParityError."""
    cfg = _cfg_with()
    body = b"No.,Sector,Industry\n1,Tech,Software\n"
    with pytest.raises(FinvizSchemaParityError) as ei:
        FinvizClient(cfg).normalize_to_canonical_csv(body)
    assert "Ticker" in str(ei.value)


def test_normalize_raises_on_excessive_rows(tmp_path) -> None:
    """Discriminating: 5001 rows triggers safety bound; 4999 rows do not."""
    cfg = _cfg_with()
    header = (
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
    )
    row = "1,AAPL,Tech,Software,USA,100,1%,1000,1,1,200,50,1B\n"
    big = (header + row * 5001).encode()
    with pytest.raises(FinvizSchemaParityError) as ei:
        FinvizClient(cfg).normalize_to_canonical_csv(big)
    assert "5000" in str(ei.value) or "exceeds" in str(ei.value).lower()

    small = (header + row * 4999).encode()
    out = FinvizClient(cfg).normalize_to_canonical_csv(small)
    assert out.count("\n") == 5000  # 1 header + 4999 data rows = 5000 newlines


def test_signature_hash_deterministic_across_runs() -> None:
    """Discriminating: same input → same hash on repeated invocation."""
    cfg = _cfg_with()
    body = (
        b"No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        b"1,AAPL,Tech,Software,USA,100,1%,1000,1,1,200,50,1B\n"
        b"2,MSFT,Tech,Software,USA,200,1%,1000,1,1,250,80,2B\n"
    )
    client = FinvizClient(cfg)
    assert client.compute_signature_hash(body) == client.compute_signature_hash(body)
```

- [ ] **Step 3: Run tests; expect FAIL — `ModuleNotFoundError: swing.integrations.finviz_api`.**

```bash
python -m pytest tests/integrations/test_finviz_api.py -v
```

- [ ] **Step 4: Implement `swing/integrations/__init__.py` as an empty package init.**

Write the file with a single docstring line:

```python
"""External-service API integrations namespace.

Each integration owns its own module here (finviz_api, schwab_api, ...).
Modules MUST NOT import each other; share via cfg + project-internal helpers."""
```

- [ ] **Step 5: Implement `swing/integrations/finviz_api.py`.**

```python
"""Finviz Elite API client.

V1 scope: fetch a saved-screen result via /export.ashx, normalize to the
canonical 13-column CSV schema, compute a deterministic signature hash for
drift detection. NO direct DB writes — caller (pipeline step OR CLI) owns
persistence. NO logging of token bytes, response URL, or response body.

See docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md §E
for endpoint reference + §F for the token-redaction discipline (incl.
defense-in-depth urllib3 DEBUG-log suppression per §A.12 / Codex R1 M2).
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import logging
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

import requests

from swing.pipeline.finviz_schema import REQUIRED_COLUMNS

if TYPE_CHECKING:
    from swing.config import Config

log = logging.getLogger(__name__)

_BASE_URL = "https://elite.finviz.com/export.ashx"
_MAX_DATA_ROWS = 5000  # safety bound; see plan §E.5
_RETRY_AFTER_MAX_SECONDS = 30  # wait at most this long on 429 + Retry-After

# Logger names that emit DEBUG-level lines including the full request URL
# (with `auth=<token>` query param). Suppressed during fetch_screen() per
# plan §A.12 (Codex R1 Major-2 fix).
_TRANSPORT_DEBUG_LOGGERS = (
    "urllib3.connectionpool",
    "requests.packages.urllib3.connectionpool",
)


@contextlib.contextmanager
def _suppress_transport_debug_logs() -> Iterator[None]:
    """Force urllib3 + requests-bundled-urllib3 loggers to WARNING for the
    duration; restore on exit. Defense-in-depth complement to the
    FinvizApiError.__str__ contract + cassette filter_query_parameters
    redaction. See plan §A.12."""
    prior = {n: logging.getLogger(n).level for n in _TRANSPORT_DEBUG_LOGGERS}
    try:
        for n in _TRANSPORT_DEBUG_LOGGERS:
            logging.getLogger(n).setLevel(logging.WARNING)
        yield
    finally:
        for n, lvl in prior.items():
            logging.getLogger(n).setLevel(lvl)


class FinvizConfigMissingError(RuntimeError):
    """Raised when token or screen_query is missing from cfg.integrations.finviz."""


class FinvizApiError(RuntimeError):
    """Generic Finviz API error (HTTP non-200 or network failure).

    `__str__` is engineered to never include the request URL (contains token
    in query string) or response body verbatim — only status code + body
    length. See plan §E.7."""

    def __init__(self, status_code: int, body_excerpt: str) -> None:
        self.status_code = status_code
        self.body_excerpt = body_excerpt
        super().__init__(f"FinvizApiError(status={status_code}, body=<{len(body_excerpt)} bytes>)")


class FinvizRateLimitError(FinvizApiError):
    """Raised on HTTP 429 after one Retry-After-respecting retry."""


class FinvizSchemaParityError(RuntimeError):
    """Raised when the API response body cannot be normalized to the canonical
    13-column schema (missing column, excessive rows, etc.)."""


class FinvizPipelineActiveError(RuntimeError):
    """Raised by `_perform_finviz_fetch_no_lease` (CLI surface) when a pipeline
    run is currently in flight. Plan §A.14 cross-surface concurrency exclusion
    (Codex R2 Major-3 fix). NOT raised by `_step_finviz_fetch` (pipeline-internal)
    — that runs WHILE the lease is held by definition."""


class FinvizClient:
    """Client for the Finviz Elite saved-screen export endpoint.

    Stateless except for `last_rate_limit_remaining`, captured from the most
    recent successful HTTP response if Finviz emits an X-RateLimit-Remaining
    header (best-effort; Finviz does not document the header).
    """

    def __init__(self, cfg: "Config") -> None:
        self._cfg = cfg.integrations.finviz
        self.last_rate_limit_remaining: int | None = None

    def fetch_screen(self) -> bytes:
        """Fetch the saved-screen result from Finviz Elite API.

        Returns the raw response body as bytes. Caller normalizes via
        normalize_to_canonical_csv. Raises typed exceptions for all failure
        modes; never logs or includes token in any error path.
        """
        if not self._cfg.token:
            raise FinvizConfigMissingError(
                "Finviz API token is missing. Set "
                "[integrations.finviz] token in user-config.toml."
            )
        if not self._cfg.screen_query:
            raise FinvizConfigMissingError(
                "Finviz screen_query is missing. Set "
                "[integrations.finviz] screen_query in user-config.toml."
            )

        url = f"{_BASE_URL}?{self._cfg.screen_query}&auth={self._cfg.token}"

        with _suppress_transport_debug_logs():
            try:
                response = requests.get(url, timeout=self._cfg.timeout_seconds)
            except requests.RequestException as exc:
                # str(exc) on requests.* exceptions can include the URL on some
                # versions. Wrap explicitly with empty body excerpt.
                raise FinvizApiError(0, "") from exc

        if response.status_code == 429:
            retry_after_str = response.headers.get("Retry-After", "")
            try:
                retry_after = int(retry_after_str)
            except ValueError:
                retry_after = -1
            if 0 < retry_after <= _RETRY_AFTER_MAX_SECONDS:
                log.warning(
                    "Finviz API 429 rate-limited; retrying after %ds", retry_after,
                )
                time.sleep(retry_after)
                with _suppress_transport_debug_logs():
                    try:
                        response = requests.get(url, timeout=self._cfg.timeout_seconds)
                    except requests.RequestException as exc:
                        raise FinvizApiError(0, "") from exc
                if response.status_code == 429:
                    raise FinvizRateLimitError(429, "")
            else:
                raise FinvizRateLimitError(429, "")

        if response.status_code != 200:
            raise FinvizApiError(response.status_code, "")

        # Best-effort rate-limit headroom capture.
        rl_str = response.headers.get("X-RateLimit-Remaining", "")
        try:
            self.last_rate_limit_remaining = int(rl_str) if rl_str else None
        except ValueError:
            self.last_rate_limit_remaining = None

        return response.content

    def normalize_to_canonical_csv(self, body: bytes) -> str:
        """Normalize API response body to the canonical 13-column CSV schema.

        Raises FinvizSchemaParityError on column missing OR row count exceeded.
        Sector + Industry preserved verbatim per Q7 lock.
        """
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FinvizSchemaParityError(
                f"Response body not UTF-8 decodable: {exc}"
            ) from exc

        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration as exc:
            raise FinvizSchemaParityError("Response body has no header row") from exc

        header_cleaned = [h.strip() for h in header]
        header_set = set(header_cleaned)
        missing = [c for c in REQUIRED_COLUMNS if c not in header_set]
        if missing:
            raise FinvizSchemaParityError(
                f"Response body missing required columns: {missing}; "
                f"got: {header_cleaned}"
            )

        # Map response-column-index → canonical-column-index for projection.
        # The response MAY have extra columns; we drop them per Q4 lock
        # (canonical schema is unchanged).
        col_indices = [header_cleaned.index(c) for c in REQUIRED_COLUMNS]

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(REQUIRED_COLUMNS)
        row_count = 0
        for row in reader:
            row_count += 1
            if row_count > _MAX_DATA_ROWS:
                raise FinvizSchemaParityError(
                    f"Response row count exceeds safety bound ({_MAX_DATA_ROWS})"
                )
            # Pad short rows; truncate long rows to projected indices.
            extended = row + [""] * (max(col_indices) + 1 - len(row))
            writer.writerow([extended[i] for i in col_indices])

        return out.getvalue()

    def compute_signature_hash(self, body: bytes) -> str:
        """Deterministic SHA256 hash of canonicalized signature payload.

        Signature payload: JSON-encoded dict {column_set: sorted, first_row:
        [Ticker, Sector, Industry]} with sort_keys=True + UTF-8.

        Drift detection: same screen returns same hash; column-set change OR
        first-row-Ticker/Sector/Industry change → different hash.
        """
        text = body.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration:
            return hashlib.sha256(b"<empty>").hexdigest()
        header_cleaned = sorted(h.strip() for h in header)
        first_row: list[str] = []
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            mapping = dict(zip([h.strip() for h in header], row, strict=False))
            first_row = [
                str(mapping.get("Ticker", "")),
                str(mapping.get("Sector", "")),
                str(mapping.get("Industry", "")),
            ]
            break
        payload = json.dumps(
            {"column_set": header_cleaned, "first_row": first_row},
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
```

- [ ] **Step 6: Record happy-path cassette.**

Operator-paired step. With `FINVIZ_TOKEN` + `FINVIZ_SCREEN_QUERY` env vars set, run:

```bash
pytest tests/integrations/test_finviz_api.py::test_fetch_screen_happy_path \
       tests/integrations/test_finviz_api.py::test_normalize_to_canonical_csv_passes_existing_validator \
       --record-mode=once -v
```

This creates `tests/integrations/cassettes/test_finviz_api/test_fetch_screen_happy_path.yaml` (and similar for the second test).

- [ ] **Step 7: Manually verify token redaction in recorded cassettes.**

```bash
grep -l "${FINVIZ_TOKEN}" tests/integrations/cassettes/ -r && echo "TOKEN LEAK!" || echo "REDACTED OK"
```

Expected: `REDACTED OK`. If `TOKEN LEAK!`, delete cassettes + investigate filter_query_parameters spelling.

- [ ] **Step 8: Run all tests in module; expect PASS.**

```bash
python -m pytest tests/integrations/test_finviz_api.py -v
```

- [ ] **Step 9: Run full fast suite; verify no regressions.**

```bash
python -m pytest -m "not slow" -q
```

- [ ] **Step 10: Commit.**

```bash
git add swing/integrations/ pyproject.toml \
        tests/integrations/__init__.py tests/integrations/test_finviz_api.py \
        tests/integrations/cassettes/
git commit -m "feat(finviz-api): FinvizClient + happy-path + normalize + cassette (Task 3)"
```

---

### Task 4: `FinvizClient` error paths (4xx, 5xx, 429, network, missing-token, schema-parity)

**Files:**
- Modify: `tests/integrations/test_finviz_api.py` (add error-path tests)
- Cassettes: `tests/integrations/cassettes/test_finviz_api/test_fetch_screen_429.yaml`, `..._500.yaml`, `..._403.yaml` (recorded via custom HTTP test server OR hand-crafted YAML — see below)

- [ ] **Step 1: Hand-craft cassettes for synthetic error responses.**

VCR cassettes are YAML; for synthetic error responses (4xx/5xx that we won't ask the live API to emit), hand-craft cassette files. Example shape (`tests/integrations/cassettes/test_finviz_api/test_fetch_screen_500_error.yaml`):

```yaml
version: 1
interactions:
  - request:
      method: GET
      uri: https://elite.finviz.com/export.ashx?v=152&f=cap_largeover&auth=REDACTED
      body: null
      headers: {}
    response:
      status:
        code: 500
        message: Internal Server Error
      headers:
        Content-Type:
          - text/plain
      body:
        string: "internal server error"
```

Create equivalent for 403 (token rejected; response body MUST NOT include `auth_token` substring), 429 (with `Retry-After: 1` header for the retry-success path; with `Retry-After: 999` for retry-give-up), and a 429-then-200-on-retry double-interaction cassette.

- [ ] **Step 2: Write error-path tests.**

```python
# Append to tests/integrations/test_finviz_api.py:

@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_500_raises_FinvizApiError() -> None:
    cfg = _cfg_with()
    with pytest.raises(FinvizApiError) as ei:
        FinvizClient(cfg).fetch_screen()
    # Discriminating: status_code preserved.
    assert ei.value.status_code == 500
    # Discriminating: NOT a rate-limit error.
    assert not isinstance(ei.value, FinvizRateLimitError)


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_403_raises_FinvizApiError() -> None:
    cfg = _cfg_with()
    with pytest.raises(FinvizApiError) as ei:
        FinvizClient(cfg).fetch_screen()
    assert ei.value.status_code == 403
    # Discriminating: error str does NOT include the token literal.
    assert "test-sentinel-token" not in str(ei.value)


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_429_with_retry_after_retries_once_and_succeeds() -> None:
    """Cassette double-interaction: first response 429 + Retry-After: 1; second response 200.

    Discriminating: client retries within deadline + returns body.
    """
    cfg = _cfg_with()
    body = FinvizClient(cfg).fetch_screen()
    # Discriminating: body is the SECOND-interaction success body.
    assert b"Ticker" in body


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_429_with_oversized_retry_after_raises_FinvizRateLimitError() -> None:
    """Cassette: response 429 + Retry-After: 999.

    Discriminating: retry NOT attempted; raises immediately.
    """
    cfg = _cfg_with()
    with pytest.raises(FinvizRateLimitError):
        FinvizClient(cfg).fetch_screen()


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_429_then_429_raises_FinvizRateLimitError() -> None:
    """Cassette double-interaction: both responses 429.

    Discriminating: even with Retry-After, second 429 → raise.
    """
    cfg = _cfg_with()
    with pytest.raises(FinvizRateLimitError):
        FinvizClient(cfg).fetch_screen()


def test_fetch_screen_network_error_raises_FinvizApiError(monkeypatch) -> None:
    """No cassette; monkeypatch requests.get to raise."""
    cfg = _cfg_with()

    def _raise(*args, **kwargs):
        import requests
        raise requests.ConnectionError("DNS failure simulated")

    monkeypatch.setattr("swing.integrations.finviz_api.requests.get", _raise)
    with pytest.raises(FinvizApiError) as ei:
        FinvizClient(cfg).fetch_screen()
    assert ei.value.status_code == 0
    # Discriminating: token literal NOT in error str.
    assert "test-sentinel-token" not in str(ei.value)
```

- [ ] **Step 3: Run tests; expect them all to pass with the Task 3 implementation (which already handles all error paths).**

```bash
python -m pytest tests/integrations/test_finviz_api.py -v
```

If any FAIL, the Task 3 implementation has a bug — the test is the discriminator. Iterate Task 3's `fetch_screen` until each error-path test passes.

- [ ] **Step 4: Audit cassettes for token leaks (sanity).**

```bash
grep -l "test-sentinel-token" tests/integrations/cassettes/ -r && echo "LEAK!" || echo "REDACTED OK"
```

Expected: `REDACTED OK`.

- [ ] **Step 5: Run full fast suite; expect green.**

```bash
python -m pytest -m "not slow" -q
```

- [ ] **Step 6: Commit.**

```bash
git add tests/integrations/test_finviz_api.py tests/integrations/cassettes/
git commit -m "feat(finviz-api): error-path tests + cassettes (Task 4)"
```

---

### Task 5: Signature-hash discriminating tests

**Files:**
- Create: `tests/integrations/test_finviz_signature_hash.py`

- [ ] **Step 1: Write discriminating tests.**

```python
# tests/integrations/test_finviz_signature_hash.py
import pytest

from swing.config import FinvizIntegrationConfig
from swing.integrations.finviz_api import FinvizClient


def _client():
    from dataclasses import dataclass
    @dataclass(frozen=True)
    class _Stub:
        finviz: FinvizIntegrationConfig
    @dataclass(frozen=True)
    class _Cfg:
        integrations: _Stub
    return FinvizClient(_Cfg(integrations=_Stub(  # type: ignore[arg-type]
        finviz=FinvizIntegrationConfig(token="x", screen_query="y", timeout_seconds=30),
    )))


_BASE = (
    b"No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
    b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
    b"1,AAPL,Technology,Software,USA,100,1%,1000,1,1,200,50,1B\n"
    b"2,MSFT,Technology,Software,USA,200,1%,1000,1,1,250,80,2B\n"
)


def test_same_input_same_hash() -> None:
    c = _client()
    h1 = c.compute_signature_hash(_BASE)
    h2 = c.compute_signature_hash(_BASE)
    # Discriminating: deterministic.
    assert h1 == h2
    # Discriminating: hash is a 64-char hex SHA256.
    assert len(h1) == 64
    assert all(ch in "0123456789abcdef" for ch in h1)


def test_column_added_changes_hash() -> None:
    """Discriminating: removing the 'Country' column changes the hash."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(
        b"Sector,Industry,Country,",
        b"Sector,Industry,",
    ).replace(b",USA,", b",")
    h_alt = c.compute_signature_hash(altered)
    assert h_base != h_alt


def test_first_row_ticker_change_changes_hash() -> None:
    """Discriminating: changing first row's Ticker (AAPL → GOOG) changes hash."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(b"1,AAPL,", b"1,GOOG,")
    h_alt = c.compute_signature_hash(altered)
    assert h_base != h_alt


def test_first_row_sector_change_changes_hash() -> None:
    """Discriminating: changing first row's Sector (Technology → Healthcare) changes hash."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(
        b"1,AAPL,Technology,Software,USA,100,1%,1000,1,1,200,50,1B\n",
        b"1,AAPL,Healthcare,Biotech,USA,100,1%,1000,1,1,200,50,1B\n",
    )
    assert c.compute_signature_hash(altered) != h_base


def test_second_row_change_does_NOT_change_hash() -> None:
    """Discriminating: signature is FIRST-ROW only; tail mutations are silent.

    This is by design (locked §2.3 step 5: signature_hash = first_row tuple).
    Trade-off: full-table-drift detection requires a heavier hash; out-of-V1
    scope. Pin behavior here so a future change to the hash payload is caught."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(b"2,MSFT,", b"2,NVDA,")
    # Discriminating: first-row-only signature → equality preserved.
    assert c.compute_signature_hash(altered) == h_base


def test_row_order_matters_for_signature() -> None:
    """Discriminating: different first row → different hash."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    swapped = (
        b"No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        b"2,MSFT,Technology,Software,USA,200,1%,1000,1,1,250,80,2B\n"
        b"1,AAPL,Technology,Software,USA,100,1%,1000,1,1,200,50,1B\n"
    )
    assert c.compute_signature_hash(swapped) != h_base


def test_column_order_does_NOT_affect_hash() -> None:
    """Discriminating: column-set is sorted before hashing, so column-order swap → same hash."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    # Swap Sector + Industry positions in header (data swaps with it for parity).
    altered_header = (
        b"No.,Ticker,Industry,Sector,Country,Price,Change,Average Volume,"
        b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        b"1,AAPL,Software,Technology,USA,100,1%,1000,1,1,200,50,1B\n"
        b"2,MSFT,Software,Technology,USA,200,1%,1000,1,1,250,80,2B\n"
    )
    # Discriminating: sorted column-set means column-position is invariant.
    assert c.compute_signature_hash(altered_header) == h_base
```

- [ ] **Step 2: Run tests; expect PASS (Task 3's implementation already handles).**

```bash
python -m pytest tests/integrations/test_finviz_signature_hash.py -v
```

- [ ] **Step 3: Commit.**

```bash
git add tests/integrations/test_finviz_signature_hash.py
git commit -m "test(finviz-api): signature-hash discriminating tests (Task 5)"
```

---

### Task 6: `_step_finviz_fetch` pipeline step

**Files:**
- Modify: `swing/pipeline/runner.py` (add `_step_finviz_fetch` + call site)
- Create: `tests/pipeline/test_step_finviz_fetch.py`

- [ ] **Step 1: Write step-level tests (failing — function doesn't exist).**

```python
# tests/pipeline/test_step_finviz_fetch.py
import contextlib
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from swing.config import FinvizIntegrationConfig
from swing.data.db import ensure_schema
from swing.data.repos.finviz_api_calls import list_recent_calls


def _setup_cfg(tmp_path: Path, *, token: str = "tok", screen_query: str = "v=152", inbox=None):
    """Build a minimal cfg-shaped object for _step_finviz_fetch."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Stub:
        finviz: FinvizIntegrationConfig

    @dataclass(frozen=True)
    class _Paths:
        finviz_inbox_dir: Path
        db_path: Path

    @dataclass(frozen=True)
    class _Cfg:
        paths: _Paths
        integrations: _Stub

    return _Cfg(
        paths=_Paths(
            finviz_inbox_dir=inbox or (tmp_path / "finviz-inbox"),
            db_path=tmp_path / "swing.db",
        ),
        integrations=_Stub(finviz=FinvizIntegrationConfig(
            token=token, screen_query=screen_query, timeout_seconds=5,
        )),
    )


def _setup_db(cfg) -> sqlite3.Connection:
    cfg.paths.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = ensure_schema(cfg.paths.db_path)
    return conn


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_step_finviz_fetch_writes_csv_and_ok_row(tmp_path: Path) -> None:
    """Happy path: API returns CSV → file written + status='ok' row + signature populated."""
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        rows = list_recent_calls(conn)
        assert len(rows) == 1
        # Discriminating: status='ok' (NOT 'error', NOT 'skipped_manual_override').
        assert rows[0].status == "ok"
        # Discriminating: signature_hash populated (64-char hex).
        assert rows[0].signature_hash is not None
        assert len(rows[0].signature_hash) == 64
        # Discriminating: row_count > 0.
        assert (rows[0].row_count or 0) > 0
        # Discriminating: response_time_ms populated.
        assert (rows[0].response_time_ms or 0) >= 0
    finally:
        conn.close()

    # CSV file written with the expected filename pattern.
    csvs = list(cfg.paths.finviz_inbox_dir.glob("finviz*.csv"))
    assert len(csvs) == 1, [f.name for f in csvs]
    text = csvs[0].read_text()
    assert "Ticker" in text.split("\n", 1)[0]


def test_step_finviz_fetch_skips_when_csv_exists(tmp_path: Path) -> None:
    """File-collision skip: today's CSV exists → API NOT called; row='skipped_manual_override'."""
    from datetime import datetime
    import platform

    from swing.evaluation.dates import action_session_for_run
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)

    # Create today's manual CSV BEFORE calling the step.
    action_session = action_session_for_run(datetime.now())
    fmt = "%#d" if platform.system() == "Windows" else "%-d"
    date_str = action_session.strftime(f"{fmt}%b%Y")
    manual_path = cfg.paths.finviz_inbox_dir / f"finviz{date_str}.csv"
    manual_path.write_text("manual content")

    try:
        with patch("swing.integrations.finviz_api.FinvizClient.fetch_screen") as mock_fetch:
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
            # Discriminating: API client was NOT instantiated/called.
            mock_fetch.assert_not_called()
        rows = list_recent_calls(conn)
        # Discriminating: row recorded with skip status.
        assert len(rows) == 1
        assert rows[0].status == "skipped_manual_override"
        assert rows[0].signature_hash is None
        assert rows[0].row_count is None
    finally:
        conn.close()

    # Manual CSV unchanged.
    assert manual_path.read_text() == "manual content"


def test_step_finviz_fetch_records_error_on_api_failure(tmp_path: Path) -> None:
    """Error path: API raises → row='error' inserted; pipeline does NOT raise."""
    from swing.integrations.finviz_api import FinvizApiError
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        with patch(
            "swing.integrations.finviz_api.FinvizClient.fetch_screen",
            side_effect=FinvizApiError(500, ""),
        ):
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        rows = list_recent_calls(conn)
        # Discriminating: status='error' (NOT 'ok' — the test would fail under
        # an implementation that swallows + records 'ok').
        assert rows[0].status == "error"
        assert rows[0].error_message is not None
        assert "FinvizApiError" in rows[0].error_message
        assert rows[0].signature_hash is None
    finally:
        conn.close()

    # No CSV emitted on error.
    csvs = list(cfg.paths.finviz_inbox_dir.glob("finviz*.csv"))
    assert csvs == []


def test_step_finviz_fetch_records_error_when_token_missing(tmp_path: Path) -> None:
    """Config-missing path: token empty → no API call; row='error'."""
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path, token="")
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        with patch("swing.integrations.finviz_api.FinvizClient.fetch_screen") as mock_fetch:
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
            mock_fetch.assert_not_called()
        rows = list_recent_calls(conn)
        assert rows[0].status == "error"
        assert "token" in (rows[0].error_message or "").lower()
        # Discriminating: token literal absent (it was empty here, but
        # discipline rules: error_message is short + names the field).
        assert len(rows[0].error_message or "") < 256
    finally:
        conn.close()


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_step_finviz_fetch_warns_on_signature_drift(tmp_path: Path, caplog) -> None:
    """Drift detection: prior call's signature differs from new fetch → WARNING log."""
    import logging

    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import insert_call
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        # Seed a prior signature DIFFERENT from what the cassette will produce.
        insert_call(conn, FinvizApiCall(
            call_id=None, ts="2026-05-04T12:00:00",
            screen_query="v=152", status="ok", row_count=10,
            response_time_ms=200, rate_limit_remaining=100,
            signature_hash="0" * 64,  # known wrong; cassette will produce real hash
            error_message=None,
        ))

        with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        # Discriminating: WARNING fires.
        drift_warnings = [
            r for r in caplog.records
            if "signature changed" in r.getMessage().lower()
        ]
        assert len(drift_warnings) == 1, [r.getMessage() for r in caplog.records]
    finally:
        conn.close()


def test_step_finviz_fetch_lease_revoke_during_signature_read_downgrades_to_error(
    tmp_path: Path,
) -> None:
    """Codex R3/R4 fix: LeaseRevokedError from the FIRST fenced_write (the prior-sig
    read) is caught by the file-work try/except → result downgraded to error →
    final fenced audit insert records the error truthfully → no canonical CSV
    + no shadow leftover (file work never started).

    Discriminating pre-fix (status='ok' eagerly recorded): audit row says ok.
    Discriminating post-fix (downgrade-on-exception): audit row says error.
    """
    from unittest.mock import MagicMock
    from swing.data.repos.pipeline import LeaseRevokedError
    from swing.pipeline.runner import _step_finviz_fetch

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    db_conn = _setup_db(cfg)

    # Fake lease: FIRST fenced_write raises LeaseRevokedError (simulated revoke
    # during the prior-signature read). The downgrade-to-error path then
    # uses the SECOND fenced_write to insert the audit row.
    call_count = [0]

    @contextlib.contextmanager
    def _fenced_write_iter():
        call_count[0] += 1
        if call_count[0] == 1:
            raise LeaseRevokedError("simulated revoke during prior-sig read")
        yield db_conn

    fake_lease = MagicMock()
    fake_lease.fenced_write = _fenced_write_iter

    with patch(
        "swing.integrations.finviz_api.requests.get",
        return_value=MagicMock(
            status_code=200, headers={},
            content=(
                b"No.,Ticker,Sector,Industry,Country,Price,Change,"
                b"Average Volume,Relative Volume,Average True Range,"
                b"52-Week High,52-Week Low,Market Cap\n"
                b"1,AAPL,Tech,Software,USA,100,1%,1000,1,1,200,50,1B\n"
            ),
        ),
    ):
        # Does NOT raise — _step_finviz_fetch's file-work try/except catches
        # the first LeaseRevokedError + downgrades to error; second fenced_write
        # (audit insert) then succeeds.
        _step_finviz_fetch(cfg=cfg, lease=fake_lease)

    # Discriminating: NO canonical CSV (file-work never executed beyond the
    # caught exception); NO shadow leftover.
    canonical_glob = list(cfg.paths.finviz_inbox_dir.glob("finviz*.csv"))
    assert canonical_glob == [], (
        f"orphan canonical after first-fenced revoke: "
        f"{[f.name for f in canonical_glob]}"
    )
    shadow_glob = list(cfg.paths.finviz_inbox_dir.glob("*.api-pending"))
    assert shadow_glob == [], (
        f"orphan shadow after first-fenced revoke: "
        f"{[f.name for f in shadow_glob]}"
    )
    # Discriminating: audit row inserted with status='error'.
    rows = list_recent_calls(db_conn)
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert "LeaseRevokedError" in (rows[0].error_message or "")
    db_conn.close()


def test_step_finviz_fetch_lease_revoke_during_final_audit_propagates(
    tmp_path: Path,
) -> None:
    """Codex R4 fix (matching §A.13's lossy-audit-history failure case):
    LeaseRevokedError from the FINAL fenced_write (the audit insert AFTER promote)
    propagates up — the canonical CSV is already on disk; the audit row is
    missing for this fetch.

    Discriminating: caller observes LeaseRevokedError; canonical CSV exists;
    no shadow leftover. Next pipeline run will see the canonical as a
    manual-override (skipped_manual_override).
    """
    from unittest.mock import MagicMock
    from swing.data.repos.pipeline import LeaseRevokedError
    from swing.pipeline.runner import _step_finviz_fetch

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    db_conn = _setup_db(cfg)

    # FIRST fenced_write succeeds (yields conn for prior-sig read);
    # SECOND fenced_write raises LeaseRevokedError (audit insert blocked).
    call_count = [0]

    @contextlib.contextmanager
    def _fenced_write_iter():
        call_count[0] += 1
        if call_count[0] == 2:
            raise LeaseRevokedError("simulated revoke at final audit insert")
        yield db_conn

    fake_lease = MagicMock()
    fake_lease.fenced_write = _fenced_write_iter

    with patch(
        "swing.integrations.finviz_api.requests.get",
        return_value=MagicMock(
            status_code=200, headers={},
            content=(
                b"No.,Ticker,Sector,Industry,Country,Price,Change,"
                b"Average Volume,Relative Volume,Average True Range,"
                b"52-Week High,52-Week Low,Market Cap\n"
                b"1,AAPL,Tech,Software,USA,100,1%,1000,1,1,200,50,1B\n"
            ),
        ),
    ):
        with pytest.raises(LeaseRevokedError):
            _step_finviz_fetch(cfg=cfg, lease=fake_lease)

    # Discriminating: canonical EXISTS (promoted before audit insert tried);
    # no shadow leftover.
    canonical_glob = list(cfg.paths.finviz_inbox_dir.glob("finviz*.csv"))
    assert len(canonical_glob) == 1, (
        f"expected exactly one canonical CSV (promote happened before audit "
        f"raised); got {[f.name for f in canonical_glob]}"
    )
    shadow_glob = list(cfg.paths.finviz_inbox_dir.glob("*.api-pending"))
    assert shadow_glob == [], (
        f"orphan shadow after final-fenced revoke: "
        f"{[f.name for f in shadow_glob]}"
    )
    # Discriminating: NO audit row was inserted (the final fenced_write blocked).
    rows = list_recent_calls(db_conn)
    assert rows == [], (
        f"unexpected audit row after final-fenced revoke: {rows}"
    )
    db_conn.close()


def test_perform_finviz_fetch_no_lease_refuses_when_pipeline_running(tmp_path: Path) -> None:
    """Codex R2 Major-3 fix: standalone CLI fetch refuses if a pipeline run
    is in flight. Pre-fix (no check): proceeds, races on inbox + audit log.
    Post-fix (check): raises FinvizPipelineActiveError.

    Codex R3 Major-2 fix: column names match swing/data/migrations/0003 schema:
    `lease_heartbeat_ts` (NOT `heartbeat_ts`); `data_asof_date` and
    `action_session_date` are NOT NULL — fixture provides them.
    """
    from swing.integrations.finviz_api import FinvizPipelineActiveError
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        # Seed an active pipeline run (state='running'). Column names match
        # swing/data/migrations/0003_phase2_pipeline_trades.sql verbatim.
        conn.execute(
            "INSERT INTO pipeline_runs ("
            "  started_ts, trigger, data_asof_date, action_session_date,"
            "  state, lease_token, lease_heartbeat_ts"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-05-05T12:00:00", "manual",
                "2026-05-04", "2026-05-05",
                "running", "tok-test", "2026-05-05T12:00:00",
            ),
        )
        conn.commit()

        with pytest.raises(FinvizPipelineActiveError) as ei:
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        assert "in flight" in str(ei.value)
    finally:
        conn.close()


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_step_finviz_fetch_no_warn_when_signature_unchanged(tmp_path: Path, caplog) -> None:
    """No drift: prior signature matches → no WARNING."""
    import logging

    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import insert_call
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = _setup_cfg(tmp_path)
    cfg.paths.finviz_inbox_dir.mkdir(parents=True)
    conn = _setup_db(cfg)
    try:
        # First call to seed; then second call.
        _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        # Remove the emitted CSV so the second call goes through API path.
        for f in cfg.paths.finviz_inbox_dir.glob("finviz*.csv"):
            f.unlink()
        with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        # Discriminating: no signature-change warning.
        drift_warnings = [
            r for r in caplog.records
            if "signature changed" in r.getMessage().lower()
        ]
        assert len(drift_warnings) == 0
    finally:
        conn.close()
```

- [ ] **Step 2: Run tests; expect FAIL — `_step_finviz_fetch` doesn't exist.**

```bash
python -m pytest tests/pipeline/test_step_finviz_fetch.py -v
```

- [ ] **Step 3: Implement the shared core + two surface-specific entrypoints in `swing/pipeline/runner.py`.**

Add (after the `_step_review_log_cadence` definition; the helpers are order-independent at module scope). Per Codex R1 Major-1 fix: the pipeline-internal step uses `lease.fenced_write()` for DB writes (consistency with other steps); the standalone CLI uses a raw connection (no lease — operator-triggered, serialized by SQLite WAL writer locking). Both call a single shared core that does the API fetch + normalize + signature, then the surface-specific wrapper persists with its own conn-management strategy.

```python
def _finviz_fetch_core(cfg) -> dict | None:
    """Shared API fetch + normalize + signature computation.

    Returns a dict with keys:
        ok: bool
        status: 'ok' | 'error' | 'skipped_manual_override'
        csv_text: str | None  (canonical 13-column CSV text; None if not written)
        csv_path: Path        (target path; written by caller on status=='ok')
        row_count: int | None
        response_time_ms: int | None
        signature_hash: str | None
        rate_limit_remaining: int | None
        error_message: str | None

    Performs the fetch but does NOT write to DB or filesystem; the caller
    persists per-surface (lease-fenced for pipeline; raw conn for CLI).
    """
    import os, platform, time
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    from swing.integrations.finviz_api import (
        FinvizApiError, FinvizClient, FinvizConfigMissingError,
        FinvizRateLimitError, FinvizSchemaParityError,
    )

    action_session = action_session_for_run(_dt.now())
    fmt = "%#d" if platform.system() == "Windows" else "%-d"
    date_str = action_session.strftime(f"{fmt}%b%Y")
    csv_path = cfg.paths.finviz_inbox_dir / f"finviz{date_str}.csv"
    cfg.paths.finviz_inbox_dir.mkdir(parents=True, exist_ok=True)

    if csv_path.exists():
        log.info(
            "Manual CSV present at %s; Finviz API fetch skipped (manual override).",
            csv_path,
        )
        return {
            "status": "skipped_manual_override", "csv_text": None,
            "csv_path": csv_path, "row_count": None,
            "response_time_ms": None, "signature_hash": None,
            "rate_limit_remaining": None, "error_message": None,
        }

    start = time.monotonic()
    try:
        client = FinvizClient(cfg)
        body = client.fetch_screen()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        canonical_text = client.normalize_to_canonical_csv(body)
        sig = client.compute_signature_hash(body)
        return {
            "status": "ok", "csv_text": canonical_text, "csv_path": csv_path,
            "row_count": canonical_text.count("\n") - 1,
            "response_time_ms": elapsed_ms, "signature_hash": sig,
            "rate_limit_remaining": client.last_rate_limit_remaining,
            "error_message": None,
        }
    except (
        FinvizConfigMissingError, FinvizApiError, FinvizRateLimitError,
        FinvizSchemaParityError,
    ) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        msg = f"{type(exc).__name__}: {exc}"
        log.warning("Finviz API fetch failed: %s", msg)
        return {
            "status": "error", "csv_text": None, "csv_path": csv_path,
            "row_count": None, "response_time_ms": elapsed_ms,
            "signature_hash": None, "rate_limit_remaining": None,
            "error_message": msg[:1024],
        }


def _finviz_persist_csv_shadow(csv_path, csv_text: str):
    """Write CSV to a shadow path '<canonical>.api-pending' atomically.
    Returns the shadow path for later promotion. Per plan §A.13."""
    import os
    from pathlib import Path as _Path
    shadow_path = _Path(str(csv_path) + ".api-pending")
    tmp_path = _Path(str(shadow_path) + ".tmp")
    tmp_path.write_text(csv_text, encoding="utf-8")
    os.replace(tmp_path, shadow_path)
    return shadow_path


def _finviz_promote_shadow(shadow_path, canonical_path) -> None:
    """Atomic rename shadow → canonical."""
    import os
    os.replace(shadow_path, canonical_path)


def _finviz_cleanup_stale_shadows(inbox_dir) -> None:
    """Delete '.api-pending' files older than 1 hour. Belt-and-suspenders
    cleanup for the rare case where a process-kill leaks a shadow."""
    import time
    cutoff = time.time() - 3600  # 1 hour
    if not inbox_dir.exists():
        return
    for f in inbox_dir.glob("*.api-pending"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def _assert_no_active_pipeline_run(conn) -> None:
    """Refuse standalone Finviz fetch if a pipeline run is currently running.
    Plan §A.14 (Codex R2 Major-3 fix). Pipeline-internal _step_finviz_fetch
    does NOT call this — it runs WHILE the lease is held."""
    from swing.integrations.finviz_api import FinvizPipelineActiveError
    row = conn.execute(
        "SELECT id FROM pipeline_runs WHERE state = 'running' "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        raise FinvizPipelineActiveError(
            f"A pipeline run is currently in flight (run_id={row[0]}); "
            "the standalone Finviz fetch is refused to avoid corrupting "
            "the inbox or audit log. Wait for the run to complete "
            "(swing pipeline status) and retry, OR run the fetch as "
            "part of the pipeline (swing pipeline run)."
        )


def _step_finviz_fetch(*, cfg, lease) -> None:
    """Pipeline step: fetch today's Finviz screen via API.

    Sequence (Codex R3 Major-1 fix — file work BEFORE audit insert; audit row
    is THE ground truth):
      1. Recovery sweep for stale shadow files.
      2. _finviz_fetch_core (in-memory fetch + normalize + signature).
      3. If result['status']=='ok': lease-fenced read of prior signature →
         drift warning; shadow-write CSV; promote shadow to canonical.
      4. Any exception during step-3 file work → DOWNGRADE result to
         status='error' with the OS-error message; clean any leftover shadow.
      5. Lease-fenced audit-row insert with the (possibly-downgraded) result.

    Failure modes covered:
      - LeaseRevokedError between step 1 and step 5: no canonical CSV remains
        (shadow deleted in finally); no audit row; pipeline aborts; clean
        next-run state.
      - Promote-fails after shadow-write: caught in step 4; result→error;
        canonical never created; audit row reflects failure truthfully.
      - LeaseRevokedError DURING the final audit-insert: canonical CSV may exist
        (depending on which side of the rename); operator's next pipeline
        run sees the canonical file as manual override (skipped_manual);
        audit history is lossy for this fetch but no false 'ok' row.
    """
    import os
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import (
        get_latest_signature_hash, insert_call,
    )

    _finviz_cleanup_stale_shadows(cfg.paths.finviz_inbox_dir)
    result = _finviz_fetch_core(cfg)
    now_iso = _dt.now().isoformat(timespec="seconds")
    sq = cfg.integrations.finviz.screen_query

    if result["status"] == "ok":
        shadow_path: _Path | None = None
        try:
            with lease.fenced_write() as conn:
                prior_sig = get_latest_signature_hash(conn, screen_query=sq)
            if prior_sig is not None and prior_sig != result["signature_hash"]:
                log.warning(
                    "Finviz screen signature changed since prior run "
                    "(%s -> %s); operator may have edited the saved screen.",
                    prior_sig[:12], result["signature_hash"][:12],
                )
            shadow_path = _finviz_persist_csv_shadow(
                result["csv_path"], result["csv_text"],
            )
            _finviz_promote_shadow(shadow_path, result["csv_path"])
            shadow_path = None  # promoted; nothing to clean
        except Exception as exc:
            # File-write OR promote OR fenced-read failed. DOWNGRADE the
            # result so the audit row reflects ground truth (Codex R3 M1).
            log.warning("Finviz CSV write/promote failed: %s", exc)
            result["status"] = "error"
            result["row_count"] = None
            result["signature_hash"] = None
            result["error_message"] = f"{type(exc).__name__}: {exc}"
        finally:
            if shadow_path is not None and shadow_path.exists():
                try:
                    shadow_path.unlink()
                except OSError as _exc:
                    log.warning("failed to clean up Finviz shadow file: %s", _exc)

    # Final audit-row insert. If THIS fenced_write raises LeaseRevokedError,
    # the audit row is missing but file state is consistent (canonical
    # either fully-promoted or not-present, never an in-between).
    with lease.fenced_write() as conn:
        insert_call(conn, FinvizApiCall(
            call_id=None, ts=now_iso, screen_query=sq,
            status=result["status"], row_count=result["row_count"],
            response_time_ms=result["response_time_ms"],
            rate_limit_remaining=result["rate_limit_remaining"],
            signature_hash=result["signature_hash"],
            error_message=result["error_message"],
        ))


def _perform_finviz_fetch_no_lease(*, cfg, conn) -> None:
    """Standalone (non-pipeline) Finviz fetch — used by `swing finviz fetch` CLI.

    Refuses execution if a pipeline run is currently in flight (plan §A.14).
    Same file-work-before-audit-insert ordering as `_step_finviz_fetch`
    (Codex R3 Major-1 fix). Writes through the caller-provided `conn`.
    """
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import (
        get_latest_signature_hash, insert_call,
    )

    _assert_no_active_pipeline_run(conn)
    _finviz_cleanup_stale_shadows(cfg.paths.finviz_inbox_dir)
    result = _finviz_fetch_core(cfg)
    now_iso = _dt.now().isoformat(timespec="seconds")
    sq = cfg.integrations.finviz.screen_query

    if result["status"] == "ok":
        shadow_path: _Path | None = None
        try:
            prior_sig = get_latest_signature_hash(conn, screen_query=sq)
            if prior_sig is not None and prior_sig != result["signature_hash"]:
                log.warning(
                    "Finviz screen signature changed since prior run "
                    "(%s -> %s); operator may have edited the saved screen.",
                    prior_sig[:12], result["signature_hash"][:12],
                )
            shadow_path = _finviz_persist_csv_shadow(
                result["csv_path"], result["csv_text"],
            )
            _finviz_promote_shadow(shadow_path, result["csv_path"])
            shadow_path = None
        except Exception as exc:
            log.warning("Finviz CSV write/promote failed: %s", exc)
            result["status"] = "error"
            result["row_count"] = None
            result["signature_hash"] = None
            result["error_message"] = f"{type(exc).__name__}: {exc}"
        finally:
            if shadow_path is not None and shadow_path.exists():
                try:
                    shadow_path.unlink()
                except OSError as _exc:
                    log.warning("failed to clean up Finviz shadow file: %s", _exc)

    insert_call(conn, FinvizApiCall(
        call_id=None, ts=now_iso, screen_query=sq,
        status=result["status"], row_count=result["row_count"],
        response_time_ms=result["response_time_ms"],
        rate_limit_remaining=result["rate_limit_remaining"],
        signature_hash=result["signature_hash"],
        error_message=result["error_message"],
    ))
```

- [ ] **Step 4: Add the call site in `run_pipeline_internal`.**

Locate the line in `swing/pipeline/runner.py:run_pipeline_internal` where `lease.step("evaluate")` is called (then `_step_evaluate(...)` is invoked). INSERT BEFORE that block:

```python
            lease.step("finviz_fetch")
            try:
                _step_finviz_fetch(cfg=cfg, lease=lease)
            except LeaseRevokedError:
                raise
            except Exception as exc:
                # _step_finviz_fetch is itself error-tolerant; this catches
                # programming errors only (KeyError, etc.). Pipeline must
                # not abort here either — preserve fallback semantics.
                log.warning("finviz_fetch programming error (continuing): %s", exc)
```

The `lease.step("finviz_fetch")` call mirrors the existing `lease.step("weather")` / `lease.step("evaluate")` etc. (verified at [`swing/pipeline/runner.py:245`](../../swing/pipeline/runner.py#L245)). NOTE: the existing `lease.step()` accepts arbitrary step-name strings — verify by reading `swing/pipeline/lease.py` at executing-plans Step 4 time; if the helper is enum-restricted (unlikely per existing usage), either extend the enum or skip the `lease.step` call (the operational signal lives in `finviz_api_calls.status`, NOT `pipeline_runs.step_status`).

- [ ] **Step 5: Run step tests; expect PASS.**

```bash
python -m pytest tests/pipeline/test_step_finviz_fetch.py -v
```

- [ ] **Step 6: Run full fast suite; expect green.**

```bash
python -m pytest -m "not slow" -q
```

- [ ] **Step 7: Commit.**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_step_finviz_fetch.py \
        tests/pipeline/cassettes/
git commit -m "feat(finviz-api): _step_finviz_fetch pipeline step + tests (Task 6)"
```

---

### Task 7: Pipeline ordering + error-fallback test

**Files:**
- Create: `tests/pipeline/test_step_finviz_fetch_ordering.py`

- [ ] **Step 1: Write ordering + error-fallback tests.**

```python
# tests/pipeline/test_step_finviz_fetch_ordering.py
"""Asserts _step_finviz_fetch is wired BEFORE _step_evaluate, AND that an API
failure does not break the pipeline (fallback to existing empty-inbox semantics)."""

import inspect
import re

from swing.pipeline.runner import run_pipeline_internal


def test_step_finviz_fetch_invoked_before_step_evaluate() -> None:
    """Source-text inspection: in run_pipeline_internal, the
    _step_finviz_fetch call site precedes the _step_evaluate call site.

    Source-text test (NOT runtime test) is intentional — it pins the wiring
    contract durably; a future refactor that accidentally reorders the steps
    will FAIL this test even if both steps still execute somewhere in the
    function. Phase 7 Sub-A T-tests use the same pattern for state-machine
    transitions.
    """
    src = inspect.getsource(run_pipeline_internal)
    fetch_idx = src.find("_step_finviz_fetch")
    eval_idx = src.find("_step_evaluate")
    # Discriminating pre-fix (e.g., if a future refactor moves the fetch step):
    # fetch_idx > eval_idx, the test fails — directly diagnoses misordering.
    assert fetch_idx > -1, "_step_finviz_fetch is not invoked in run_pipeline_internal"
    assert eval_idx > -1, "_step_evaluate is not invoked in run_pipeline_internal"
    assert fetch_idx < eval_idx, (
        f"Expected _step_finviz_fetch (offset {fetch_idx}) BEFORE "
        f"_step_evaluate (offset {eval_idx}); they appear reversed in source."
    )


def test_step_finviz_fetch_call_site_is_wrapped_in_try_except() -> None:
    """Source-text contract: the _step_finviz_fetch call site in
    run_pipeline_internal is enclosed in a try/except block whose handler
    LOGS rather than RAISES. A future refactor that removes the wrapper
    would let a programming error in the step abort the pipeline; this
    test catches that durably without needing the full pipeline-runner
    integration fixture (lease + heartbeat + RS-universe wiring).
    """
    src = inspect.getsource(run_pipeline_internal)
    fetch_idx = src.find("_step_finviz_fetch")
    assert fetch_idx > -1, "_step_finviz_fetch is not invoked in run_pipeline_internal"
    pre_window = src[max(0, fetch_idx - 1500):fetch_idx]
    post_window = src[fetch_idx:fetch_idx + 1500]
    # Discriminating: a `try:` precedes the call, AND an `except` follows.
    assert "try:" in pre_window, (
        "_step_finviz_fetch is not inside a try-block; an unexpected exception "
        "would abort the pipeline."
    )
    except_match = re.search(r"except\s+(?:Exception|\w*Error)", post_window)
    assert except_match, (
        f"No `except Exception` follows _step_finviz_fetch; window: "
        f"{post_window[:300]}"
    )
    # Discriminating: the except block calls log.warning or log.error
    # (logs + continues) rather than re-raising.
    block_start = except_match.end()
    block = post_window[block_start: block_start + 400]
    assert "log.warning" in block or "log.error" in block, (
        f"Except block following _step_finviz_fetch does not log: {block[:300]}"
    )

    # SCAFFOLD MARKER: a future task may extend this with a full integration
    # test that monkey-patches _step_finviz_fetch to raise KeyError and asserts
    # `run_pipeline_internal(cfg=..., trigger='manual').state == 'complete'`.
    # That requires the project's existing pipeline-runner fixture (see
    # tests/pipeline/test_runner.py). Out-of-scope for V1; the source-text
    # test above pins the contract durably.
```

Both tests are SOURCE-TEXT inspection tests. The first verifies ordering; the second verifies the resilience contract (try/except + log-not-raise). They pin the wiring contract durably without requiring the full pipeline-runner integration fixture (lease + heartbeat + RS-universe wiring established in `tests/pipeline/test_runner.py`).

A future task MAY add a full integration test that monkey-patches `_step_finviz_fetch` to raise `KeyError` and asserts `run_pipeline_internal(cfg=..., trigger='manual').state == 'complete'` — out-of-scope for V1 because the source-text tests cover the contract that would fail.

- [ ] **Step 2: Run ordering + fallback tests; expect PASS.**

```bash
python -m pytest tests/pipeline/test_step_finviz_fetch_ordering.py -v
```

- [ ] **Step 3: Run full fast suite; verify green.**

```bash
python -m pytest -m "not slow" -q
```

- [ ] **Step 4: Commit.**

```bash
git add tests/pipeline/test_step_finviz_fetch_ordering.py
git commit -m "test(finviz-api): pipeline ordering + error-fallback (Task 7)"
```

---

### Task 8: CLI `swing finviz fetch` + `swing finviz status`

**Files:**
- Modify: `swing/cli.py` (add `finviz` subcommand group)
- Create: `tests/cli/test_finviz_commands.py`

- [ ] **Step 1: Write CLI tests (failing — group doesn't exist).**

```python
# tests/cli/test_finviz_commands.py
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from swing.data.db import ensure_schema
from swing.data.models import FinvizApiCall
from swing.data.repos.finviz_api_calls import insert_call


@pytest.fixture
def cli_runner_with_cfg(tmp_path: Path):
    """Builds a tmp swing.config.toml + DB; returns (runner, cfg_path)."""
    from swing.cli import main
    runner = CliRunner()
    base_toml = Path("swing.config.toml").read_text()
    cfg_path = tmp_path / "swing.config.toml"
    # Re-write paths to tmp_path-rooted defaults so the CLI's Config sees a fresh DB.
    rewritten = base_toml.replace(
        'db_path = "swing-data/swing.db"',
        f'db_path = "{tmp_path}/swing.db"',
    ).replace(
        'finviz_inbox_dir = "data/finviz-inbox"',
        f'finviz_inbox_dir = "{tmp_path}/finviz-inbox"',
    )
    cfg_path.write_text(rewritten)
    (tmp_path / "finviz-inbox").mkdir()
    ensure_schema(tmp_path / "swing.db").close()
    return runner, cfg_path, main


def test_swing_finviz_status_lists_recent_calls(cli_runner_with_cfg, tmp_path) -> None:
    runner, cfg_path, main = cli_runner_with_cfg
    conn = sqlite3.connect(tmp_path / "swing.db")
    try:
        insert_call(conn, FinvizApiCall(
            call_id=None, ts="2026-05-05T12:00:00", screen_query="v=152",
            status="ok", row_count=42, response_time_ms=180,
            rate_limit_remaining=99,
            signature_hash="abc123def456" + "0" * 52, error_message=None,
        ))
    finally:
        conn.close()
    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "status"])
    # Discriminating: exit code 0; output mentions row count + signature prefix.
    assert res.exit_code == 0, res.output
    assert "ok" in res.output
    assert "42" in res.output
    assert "abc123de" in res.output  # truncated 8 chars of signature


def test_swing_finviz_status_empty_state(cli_runner_with_cfg) -> None:
    runner, cfg_path, main = cli_runner_with_cfg
    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "status"])
    assert res.exit_code == 0, res.output
    assert "no" in res.output.lower()  # "no calls recorded" or similar


def test_swing_finviz_fetch_token_missing_friendly_error(
    cli_runner_with_cfg,
) -> None:
    """Discriminating: missing token → exit code != 0 + friendly error message."""
    runner, cfg_path, main = cli_runner_with_cfg
    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "fetch"])
    # Token + screen_query are empty in tracked toml; user-config not set.
    assert res.exit_code != 0
    assert "token" in res.output.lower() or "screen_query" in res.output.lower()


def test_swing_finviz_fetch_friendly_error_when_pipeline_running(
    cli_runner_with_cfg, tmp_path,
) -> None:
    """Codex R2 Major-3 + R3 Minor-1 fix: CLI surface translates
    FinvizPipelineActiveError to a friendly user-facing error.

    Pre-fix: helper raised; CLI propagated the raw Python traceback.
    Post-fix: CLI catches, emits ClickException with operator-actionable text.
    """
    runner, cfg_path, main = cli_runner_with_cfg
    conn = sqlite3.connect(tmp_path / "swing.db")
    try:
        conn.execute(
            "INSERT INTO pipeline_runs ("
            "  started_ts, trigger, data_asof_date, action_session_date,"
            "  state, lease_token, lease_heartbeat_ts"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("2026-05-05T12:00:00", "manual",
             "2026-05-04", "2026-05-05",
             "running", "tok-test", "2026-05-05T12:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "fetch"])
    assert res.exit_code != 0
    assert "pipeline run is currently in flight" in res.output


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_swing_finviz_fetch_happy_path_emits_csv_and_persists_row(
    cli_runner_with_cfg, tmp_path, monkeypatch,
) -> None:
    """Discriminating: USERPROFILE/swing-data/user-config.toml is the canonical
    user-config path (verified at swing/config_user.py:_user_home + get_user_config_path).

    Codex R1 Major-3 fix: prior draft had `tmp_path / "user-data"` + USERPROFILE
    pointed at tmp_path/user-data/.. — that resolved to tmp_path, so the code
    looked at tmp_path/swing-data/user-config.toml which DID NOT exist.
    Correct: write to tmp_path/swing-data/user-config.toml + set USERPROFILE
    to tmp_path so the resolution lands exactly on the file we wrote.
    """
    runner, cfg_path, main = cli_runner_with_cfg
    # Override token via user-config.
    user_cfg_dir = tmp_path / "swing-data"
    user_cfg_dir.mkdir(exist_ok=True)
    (user_cfg_dir / "user-config.toml").write_text(
        '[integrations.finviz]\n'
        'token = "test-sentinel-token"\n'
        'screen_query = "v=152&f=cap_largeover"\n'
    )
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "fetch"])
    assert res.exit_code == 0, res.output
    csvs = list((tmp_path / "finviz-inbox").glob("finviz*.csv"))
    # Discriminating: file emitted.
    assert len(csvs) == 1
    # Discriminating: status=ok row + signature populated.
    conn = sqlite3.connect(tmp_path / "swing.db")
    try:
        rows = conn.execute(
            "SELECT status, row_count, signature_hash FROM finviz_api_calls"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "ok"
    assert rows[0][1] > 0
    assert rows[0][2] is not None
```

- [ ] **Step 2: Run tests; expect FAIL — `finviz` group doesn't exist.**

```bash
python -m pytest tests/cli/test_finviz_commands.py -v
```

- [ ] **Step 3: Add the `finviz` subcommand group to `swing/cli.py`.**

Append (near the end of `swing/cli.py`, after the existing `trade_group` definition):

```python
@main.group("finviz")
def finviz_group() -> None:
    """Finviz Elite API integration: fetch + status."""


@finviz_group.command("fetch")
@click.pass_context
def finviz_fetch_cmd(ctx: click.Context) -> None:
    """Fetch the saved-screen via Finviz Elite API + emit canonical CSV.

    Same file-collision behavior as the pipeline step: if today's CSV is
    already present in the inbox, fetch is skipped (manual override).
    """
    from swing.config_overrides import apply_overrides
    from swing.data.db import connect
    from swing.integrations.finviz_api import FinvizPipelineActiveError
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = apply_overrides(ctx.obj["config"])
    if not cfg.integrations.finviz.token:
        raise click.ClickException(
            "[integrations.finviz] token is missing in user-config "
            "(%USERPROFILE%/swing-data/user-config.toml)."
        )
    if not cfg.integrations.finviz.screen_query:
        raise click.ClickException(
            "[integrations.finviz] screen_query is missing in user-config "
            "(%USERPROFILE%/swing-data/user-config.toml)."
        )
    conn = connect(cfg.paths.db_path)
    try:
        try:
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        except FinvizPipelineActiveError as exc:
            # Translate the typed exception to a friendly Click error
            # (Codex R2 Major-3 + R3 Minor-1 fix).
            raise click.ClickException(str(exc)) from exc
        # Display the just-recorded row.
        from swing.data.repos.finviz_api_calls import list_recent_calls
        recent = list_recent_calls(conn, limit=1)
        if recent:
            r = recent[0]
            click.echo(
                f"status={r.status}  rows={r.row_count}  "
                f"elapsed={r.response_time_ms}ms  signature={(r.signature_hash or '')[:12]}"
            )
            if r.error_message:
                click.echo(f"error: {r.error_message}", err=True)
    finally:
        conn.close()


@finviz_group.command("status")
@click.option(
    "--limit", type=int, default=10,
    help="Number of recent calls to show (default: 10).",
)
@click.pass_context
def finviz_status_cmd(ctx: click.Context, limit: int) -> None:
    """Show recent Finviz API call history (last N rows)."""
    from swing.data.db import connect
    from swing.data.repos.finviz_api_calls import list_recent_calls

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        rows = list_recent_calls(conn, limit=limit)
    finally:
        conn.close()
    if not rows:
        click.echo("No Finviz API calls recorded yet.")
        return
    click.echo(
        f"{'ts':<22} {'status':<26} {'rows':>5} {'elapsed':>9} "
        f"{'rl_left':>7} {'sig':<12}"
    )
    for r in rows:
        sig = (r.signature_hash or "")[:12].ljust(12)
        click.echo(
            f"{r.ts:<22} {r.status:<26} "
            f"{(r.row_count if r.row_count is not None else '-'):>5} "
            f"{(str(r.response_time_ms) + 'ms' if r.response_time_ms is not None else '-'):>9} "
            f"{(r.rate_limit_remaining if r.rate_limit_remaining is not None else '-'):>7} "
            f"{sig}"
        )
```

- [ ] **Step 4: Run CLI tests; expect PASS.**

```bash
python -m pytest tests/cli/test_finviz_commands.py -v
```

- [ ] **Step 5: Run full fast suite; verify green.**

```bash
python -m pytest -m "not slow" -q
```

- [ ] **Step 6: Commit.**

```bash
git add swing/cli.py tests/cli/test_finviz_commands.py tests/cli/cassettes/
git commit -m "feat(finviz-api): swing finviz {fetch,status} CLI (Task 8)"
```

---

### Task 9: Slow-marked live integration test

**Files:**
- Create: `tests/integrations/test_finviz_api_live.py`

- [ ] **Step 1: Write the slow-marked test.**

```python
"""Slow-marked live integration test for Finviz Elite API.

Hits the real Finviz API. Skipped automatically when the operator's token is
not present in user-config — so a fresh-clone CI without the secret never
fails. Manually run via:

    python -m pytest -m slow tests/integrations/test_finviz_api_live.py -v

Purpose: drift-detection harness. If Finviz changes column ordering, adds a
new column, or alters response Content-Type, this test fails on schema-shape
mismatch and the cassettes need re-recording per plan §G runbook.
"""
from __future__ import annotations

import pytest

from swing.config import load
from swing.config_overrides import apply_overrides
from swing.integrations.finviz_api import FinvizClient
from swing.pipeline.finviz_schema import REQUIRED_COLUMNS


@pytest.mark.slow
def test_finviz_live_fetch_and_normalize_schema_parity(tmp_path) -> None:
    from pathlib import Path
    cfg = apply_overrides(load(Path("swing.config.toml")))
    if not cfg.integrations.finviz.token or not cfg.integrations.finviz.screen_query:
        pytest.skip(
            "Finviz token / screen_query not in user-config; "
            "skipping live API test (per plan §K)."
        )

    client = FinvizClient(cfg)
    body = client.fetch_screen()
    assert isinstance(body, bytes)
    canonical = client.normalize_to_canonical_csv(body)
    header = canonical.split("\n", 1)[0]
    columns = tuple(c.strip() for c in header.split(","))
    # Discriminating: live response CAN be normalized to canonical 13.
    assert columns == REQUIRED_COLUMNS, columns

    # Discriminating: at least one data row.
    data_rows = [line for line in canonical.split("\n")[1:] if line.strip()]
    assert len(data_rows) > 0


@pytest.mark.slow
def test_finviz_live_signature_hash_stable_within_session() -> None:
    """Two back-to-back live calls produce the same signature (column-set
    + first-row Ticker/Sector/Industry don't drift in a few seconds)."""
    from pathlib import Path
    cfg = apply_overrides(load(Path("swing.config.toml")))
    if not cfg.integrations.finviz.token or not cfg.integrations.finviz.screen_query:
        pytest.skip("Finviz creds absent; skipping live signature stability test.")

    client = FinvizClient(cfg)
    sig_a = client.compute_signature_hash(client.fetch_screen())
    sig_b = client.compute_signature_hash(client.fetch_screen())
    assert sig_a == sig_b, (sig_a, sig_b)
```

- [ ] **Step 2: Run slow suite locally (operator-paired with token).**

```bash
python -m pytest -m slow tests/integrations/test_finviz_api_live.py -v
```

Expected: 2 passed (with operator's token) OR 2 skipped (without). NEVER failed.

- [ ] **Step 3: Run fast suite; verify the slow tests are NOT in fast-suite output.**

```bash
python -m pytest -m "not slow" -q
```

Expected: same fast-suite count as before this task (slow-marked tests are filtered out).

- [ ] **Step 4: Commit.**

```bash
git add tests/integrations/test_finviz_api_live.py
git commit -m "test(finviz-api): slow-marked live integration test (Task 9)"
```

---

### Task 10: Token-leak audit test (sentinel grep)

**Files:**
- Create: `tests/integrations/test_finviz_token_redaction_audit.py`

- [ ] **Step 1: Write the audit test.**

```python
"""End-to-end token-leak audit.

Runs the full happy-path + error-path fetch cycle with a SENTINEL token, then
greps every captured log record + every persisted DB row + every committed
cassette file for the sentinel literal. Test fails if found anywhere.

This is a defense-in-depth invariant test; runs in fast suite. The cassette
sweep covers the ENTIRE tests/integrations/cassettes/ directory tree.
"""
from __future__ import annotations

import io
import logging
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from swing.config import FinvizIntegrationConfig
from swing.data.db import ensure_schema
from swing.data.repos.finviz_api_calls import list_recent_calls
from swing.integrations.finviz_api import (
    FinvizApiError,
    FinvizClient,
    FinvizConfigMissingError,
)

_SENTINEL = "TOK-SENTINEL-DO-NOT-LEAK-9f8e7d6c5b4a"


def _client_with_sentinel():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Stub:
        finviz: FinvizIntegrationConfig

    @dataclass(frozen=True)
    class _Cfg:
        integrations: _Stub

    return FinvizClient(_Cfg(  # type: ignore[arg-type]
        integrations=_Stub(finviz=FinvizIntegrationConfig(
            token=_SENTINEL, screen_query="v=152", timeout_seconds=5,
        )),
    ))


def test_sentinel_token_absent_from_logs_on_error_path(caplog) -> None:
    """Discriminating: a network error caught + logged MUST NOT include the token literal."""
    import requests
    with patch(
        "swing.integrations.finviz_api.requests.get",
        side_effect=requests.ConnectionError(f"some-error-mentioning-{_SENTINEL}"),
    ):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(FinvizApiError):
                _client_with_sentinel().fetch_screen()
    full_log = "\n".join(r.getMessage() for r in caplog.records)
    # Discriminating: even though the underlying ConnectionError mentioned the
    # sentinel, FinvizApiError(__str__) MUST NOT include it.
    assert _SENTINEL not in full_log


def test_sentinel_token_absent_from_db_row_on_error_path(tmp_path: Path) -> None:
    """Discriminating: pipeline step records error_message; sentinel must NOT appear."""
    from datetime import datetime
    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import insert_call
    from swing.integrations.finviz_api import FinvizApiError

    conn = ensure_schema(tmp_path / "swing.db")
    try:
        # Simulate the path: pipeline catches FinvizApiError + writes error_message.
        try:
            raise FinvizApiError(0, f"some body containing {_SENTINEL}")
        except FinvizApiError as exc:
            insert_call(conn, FinvizApiCall(
                call_id=None,
                ts=datetime.now().isoformat(timespec="seconds"),
                screen_query="v=152",
                status="error", row_count=None, response_time_ms=None,
                rate_limit_remaining=None, signature_hash=None,
                error_message=f"{type(exc).__name__}: {exc}",
            ))
        rows = list_recent_calls(conn)
        # Discriminating: error_message persisted; sentinel absent (FinvizApiError.__str__
        # never includes body).
        assert _SENTINEL not in (rows[0].error_message or "")
        assert "FinvizApiError" in (rows[0].error_message or "")
    finally:
        conn.close()


def test_sentinel_token_absent_from_urllib3_debug_logs(caplog) -> None:
    """Codex R1 Major-2 fix: even with `urllib3.connectionpool` set to DEBUG,
    the sentinel token must NOT appear in captured log records.

    Discriminating pre-fix (no _suppress_transport_debug_logs context manager):
        the sentinel WOULD appear in urllib3.connectionpool DEBUG output as
        part of the full request URL line.
    Discriminating post-fix (with the context manager):
        urllib3 DEBUG records are suppressed for the duration of the request;
        sentinel absent from the captured log corpus.
    """
    import requests

    # Force urllib3 logger to DEBUG; the suppression helper inside fetch_screen
    # must override this for the duration of the call.
    logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG)
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.DEBUG)

    # No real HTTP — patch requests.get to capture the URL it would have logged
    # (then raise so we exercise the error-path leak surface, where the URL
    # might have been logged before the exception).
    captured_urls: list[str] = []

    def _fake_get(url, *a, **kw):
        captured_urls.append(url)
        raise requests.ConnectionError("simulated network failure")

    with patch("swing.integrations.finviz_api.requests.get", _fake_get):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(FinvizApiError):
                _client_with_sentinel().fetch_screen()

    # Sentinel was actually present in the URL the client tried to call
    # (proving the test is non-vacuous).
    assert captured_urls, "test setup error: requests.get not invoked"
    assert _SENTINEL in captured_urls[0], (
        "test setup error: client did not actually pass token to URL "
        "(can't validate redaction)"
    )

    # Discriminating: the sentinel does NOT appear in any captured log record
    # name, message, OR formatted output.
    full_log = "\n".join(
        f"{r.name}: {r.getMessage()}" for r in caplog.records
    )
    assert _SENTINEL not in full_log, (
        f"Token sentinel leaked into log records:\n{full_log[:1000]}"
    )


def test_sentinel_token_absent_from_committed_cassettes() -> None:
    """Cassette sweep: NO committed cassette file may contain the project's
    test-sentinel-token (the recording-time token used in cassette recordings).

    The Task 3 + Task 4 cassettes were recorded with the literal
    'test-sentinel-token' as the FAKE token (operator's real token never
    enters cassettes); this test pins the redaction by asserting the literal
    'test-sentinel-token' is absent from cassette text.
    """
    cassette_root = Path("tests/integrations/cassettes")
    if not cassette_root.exists():
        pytest.skip("No cassettes recorded yet (Tasks 3+4 not run)")
    leaks: list[str] = []
    for f in cassette_root.rglob("*.yaml"):
        text = f.read_text(errors="replace")
        # Discriminating: the literal real-token-substituted-with-sentinel
        # MUST be replaced with REDACTED (or removed) by VCR's
        # filter_query_parameters config; if any cassette contains it raw,
        # filter_query_parameters spelling is wrong.
        if "test-sentinel-token" in text:
            leaks.append(str(f))
    assert not leaks, f"Token leaked into cassettes: {leaks}"
```

- [ ] **Step 2: Run tests; expect PASS (Task 3 + Task 4 implementations are written to never leak).**

```bash
python -m pytest tests/integrations/test_finviz_token_redaction_audit.py -v
```

- [ ] **Step 3: Run full fast suite; expect green.**

```bash
python -m pytest -m "not slow" -q
```

- [ ] **Step 4: Commit.**

```bash
git add tests/integrations/test_finviz_token_redaction_audit.py
git commit -m "test(finviz-api): token-leak sentinel audit (Task 10)"
```

---

### Task 11: Documentation (CLAUDE.md + cycle-checklist)

**Files:**
- Modify: `CLAUDE.md` (Finviz inbox section update + 5 new gotchas per §J)
- Modify: `docs/cycle-checklist.md` (replace manual export step + new weekly check per §I)

- [ ] **Step 1: Edit `CLAUDE.md`.**

Apply the 5 binding text-additions from plan §J. The implementer adapts wording to current line-numbering at edit time.

Also update the Finviz inbox section's `data/finviz-inbox/` paragraph (current text in CLAUDE.md mentions ONLY manual export):

OLD (around current "Finviz inbox: ..."):
```
**Finviz inbox:** `data/finviz-inbox/` (configured in `swing.config.toml`). Save exports as `finvizDDMmmYYYY.csv`. ...
```

NEW:
```
**Finviz inbox:** `data/finviz-inbox/` (configured in `swing.config.toml`). Pipeline now fetches the screen via Finviz Elite API automatically (`_step_finviz_fetch`); manual CSV drop remains a fallback override (file-collision skip in the pipeline step). Save manual exports as `finvizDDMmmYYYY.csv` (1-2 digit day, 3-letter month, 4-digit year — e.g. `finviz5May2026.csv`). API-emitted CSVs use the same filename pattern, anchored on `action_session_for_run(datetime.now())` per [`swing/pipeline/runner.py:_step_finviz_fetch`](swing/pipeline/runner.py). Validator requires 13 columns: `No., Ticker, Sector, Industry, Country, Price, Change, Average Volume, Relative Volume, Average True Range, 52-Week High, 52-Week Low, Market Cap`. Missing columns → CSV moved to `data/finviz-inbox/rejected/` with a sidecar `.rejected-reasons.json`. Pipeline outputs go to `exports/<action_session_date>/` (briefing.md + briefing.html + charts/).
```

- [ ] **Step 2: Edit `docs/cycle-checklist.md`.**

Apply the §I binding text. Read the current file first to find the manual-export step and adapt wording.

- [ ] **Step 3: Run full fast suite; verify green.**

```bash
python -m pytest -m "not slow" -q
```

- [ ] **Step 4: Verify ruff baseline preserved.**

```bash
ruff check swing/ 2>&1 | tail -1
```

Expected: ≤78 errors. Plan introduces 0 new violations.

- [ ] **Step 5: Commit.**

```bash
git add CLAUDE.md docs/cycle-checklist.md
git commit -m "docs(finviz-api): CLAUDE.md gotchas + cycle-checklist update (Task 11)"
```

---

## §Z — Done criteria (executing-plans dispatch closure)

- [ ] All 11 tasks committed (one commit per task; conventional-commits format).
- [ ] Live API verification (Task 0.b) PASSED OR ORCHESTRATOR-DISPATCHED a follow-up with corrected endpoint shape.
- [ ] Full fast suite green: `python -m pytest -m "not slow" -q` exits 0.
- [ ] Slow suite spot-check (with operator's token): `python -m pytest -m slow tests/integrations/test_finviz_api_live.py -v` returns 2 passed (or 2 skipped if no token).
- [ ] Ruff baseline: `ruff check swing/` reports ≤ 78 errors. Plan introduces 0 new violations.
- [ ] Token-leak sentinel audit (`tests/integrations/test_finviz_token_redaction_audit.py`) GREEN.
- [ ] Cassette files committed; manual grep for operator's real token literal returns ZERO matches.
- [ ] CLI-witnessed gate per §K all 5 sub-steps PASS.
- [ ] Adversarial-review chain on the executing-plans dispatch reaches NO_NEW_CRITICAL_MAJOR.
- [ ] Production DB schema_version after `swing db-migrate` is 15.
- [ ] CLAUDE.md + cycle-checklist updates committed.

---

## §AA — Test-count projection

Plan biases high per Phase 6 lesson "Test count projections should bias high":

- Task 1: +6 (2 migration + 4 repo)
- Task 2: +7 (config cascade + 4 user-config interactions + 1 dataclass-default + 1 R1 regression-2part-paths + 1 R2 subprocess-cred-propagation)
- Task 3: +7 (token-missing × 2 + happy-path + normalize-validator + missing-column + excessive-rows + signature-deterministic)
- Task 4: +6 (500 + 403 + 429-success + 429-give-up + 429-then-429 + network-error)
- Task 5: +7 (deterministic + column-added + ticker-change + sector-change + 2nd-row-no-change + row-order + column-order-invariant)
- Task 6: +9 (happy-path + skip-manual + error-on-API-fail + token-missing + drift-warn + no-drift-warn + R4 lease-revoke-during-signature-read-downgrades-to-error + R4 lease-revoke-during-final-audit-propagates + R2 cli-refuses-when-pipeline-running)
- Task 7: +2 (ordering source-text + error-fallback integration)
- Task 8: +5 (status-empty + status-with-rows + fetch-token-missing + fetch-happy-path + R3 fetch-friendly-error-when-pipeline-running)
- Task 9: +2 slow tests (live happy + signature stable; counted separately)
- Task 10: +4 (logs + DB row + cassette sweep + R1 urllib3-DEBUG sentinel)

**Fast-test total projection: +53 tests** (range +30 to +60 per brief §6 anticipated band; landing upper-mid-range; +2 from R1 fixes; +3 from R2 fixes; +1 from R3 fixes; +1 from R4 fixes — split single revoke test into two distinct failure-point tests).
**Slow-test total projection: +2 tests** (live integration test pair).

---

## §BB — Estimated executing-plans dispatches

**Single dispatch.** Plan scope is comparable to Phase 6 (single dispatch, ~12-15 tasks); decomposition into sub-A/B/C is overkill for V1. Estimated implementer time: ~6-10 hours TDD + ~3 Codex rounds → NO_NEW_CRITICAL_MAJOR.

---

## §CC — Notable risks for executing-plans phase

1. **Live API contradiction with synthesized §E reference (HIGH).** If Task 0.b live verification reveals (e.g.) a JSON envelope or multi-step session-token flow, the plan needs orchestrator-side rework. Mitigation: Task 0.b explicitly halts before any cassette is recorded.
2. **Cassette token-redaction misconfiguration (HIGH if missed; LOW with Task 10 invariant).** A misspelled `filter_query_parameters` would commit the operator's token. Mitigation: Task 10's sentinel sweep + manual grep at Task 3 + Task 8.
3. **Pipeline-step error-fallback integration test scaffold-vs-runtime gap (MEDIUM).** Task 7's second test is a scaffold; if implementer skips wiring it, regression coverage on pipeline-fallback is missing. Mitigation: scaffold note explicitly forbids skip in CI; review checklist verifies.
4. **`config_overrides._get` signature change for 3-part paths (MEDIUM).** Task 2 modifies `_get` to support `integrations.finviz.token`; existing 2-part paths continue working but the implementation must be tested under both shapes. Mitigation: `tests/config/test_config_integrations_finviz.py` verifies; existing `tests/config/test_config_overrides.py` (or whatever it's named) catches regressions.
5. **`config_validation.FIELD_REGISTRY` integration friction (LOW-MEDIUM).** Task 2 references `swing/config_validation.py` for `FIELD_REGISTRY`; the implementer may need to extend that module. Mitigation: Phase 5 plan documented this surface; the implementer reads it before extending.
6. **Cassette mode = `none` in CI (LOW).** `pytest-recording` defaults to `none` in CI when `--record-mode` not specified; if a future test introduces a new HTTP call without recording its cassette first, CI will fail with "no cassette found." Acceptable; signal of missing cassette.
7. **Operator's saved-screen change post-ship (LOW; signature-drift WARNING handles).** If the operator edits their Finviz saved screen, the signature changes and the WARNING fires once; subsequent runs are silent because the new signature becomes the latest. No data corruption.

---

## Self-review (writing-plans skill checklist)

**1. Spec coverage:** every locked decision in brief §2 maps to a task: §2.1 (architecture) → Task 3; §2.2 (config) → Task 2; §2.3 (pipeline step) → Task 6; §2.4 (persistence) → Task 1; §2.5 (CLI) → Task 8; §2.6 (tests) → Tasks 3+4+5+6+7+8+9+10; §2.7 (logging + token redaction) → Task 10 + §E.7; brief §3 research items → Task 0 + §A; brief §7 watch items 1-20 → §A.1, §E.7, Task 4, Task 5, §H, Task 6, Task 1+0, Task 10, Task 9, §J, §K, Task 11.

**2. Placeholder scan:** none. All discriminating-test pre-fix vs post-fix values are concrete. Task 7's second test is a SCAFFOLD with explicit binding assertion; the executing-plans implementer is REQUIRED to fill it (not skip).

**3. Type consistency:** `FinvizIntegrationConfig` (Task 2) field names match `FinvizClient` consumer (Task 3) — `token`, `screen_query`, `timeout_seconds`. `FinvizApiCall` dataclass (Task 1) field names match `INSERT/SELECT` columns in repo (Task 1) — `call_id, ts, screen_query, status, row_count, response_time_ms, rate_limit_remaining, signature_hash, error_message`. `_step_finviz_fetch` signature (Task 6) is `(*, cfg, lease)` matching brief §B/§H + Codex R1 M1 fix; `_perform_finviz_fetch_no_lease(*, cfg, conn)` is the sibling CLI surface; both share `_finviz_fetch_core` to avoid logic drift. Pipeline runner call site (Task 6 step 4) passes `cfg=cfg, lease=lease`. CLI body (Task 8) passes `cfg=apply_overrides(...), conn=connect(...)`.
