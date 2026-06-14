# Phase 18 Arc 18-E — operational tool-health monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an aggregating, read-only roll-up of EXISTING data-collection-enabling signals — pipeline-run health, Schwab token TTL, OHLCV + weather data-freshness — so the health of the collection apparatus is one glance. Ships a new `swing/monitoring/` package with `compute_tool_health(...) -> ToolHealthStatus` (pure, read-only, returns the §3-locked JSON envelope) plus a thin `scripts/tool_health.py` operator probe (ASCII `ATTENTION (N)` / `all clear` + `--json`). The function is the consumption point for the follow-on 18-F GUI stoplight.

**Architecture:** A new `swing/monitoring/tool_health.py` houses the envelope dataclasses (`ToolHealthCheck`, `ToolHealthStatus` — both `frozen`, both with `__post_init__` frozenset validation of the status enum) and the aggregator `compute_tool_health(conn, *, cfg=None, prices_cache_dir=None, now=None) -> ToolHealthStatus`. Three pure per-check functions (`_check_pipeline_run`, `_check_schwab_token`, `_check_data_freshness`) each return a list of `ToolHealthCheck` and are tested in isolation against synthetic-but-production-shaped inputs. The aggregator concatenates the checks, computes `overall = worst-of` (red > yellow > green), and returns the status. `scripts/tool_health.py` opens its OWN `mode=ro` connection (the `weekly_glance.py` precedent), loads `Config.from_defaults()`, calls the aggregator with `cfg` + `prices_cache_dir`, and renders ASCII (default) or JSON (`--json`). NO nightly pipeline step, NO new schema, NO new signal source, NO new dependency.

**Tech Stack:** Python 3.14. The monitor's OWN code imports only stdlib (`sqlite3`, `json`, `dataclasses`, `pathlib`, `datetime`, `argparse`, `os`) — NO pandas in `tool_health.py`/`scripts/tool_health.py`. It REUSES existing project helpers (`swing.evaluation.dates`, `swing.cli_schwab`, the repo readers) that ALREADY depend on the project's pandas / exchange_calendars / schwabdev — this is the reuse-not-fork mandate, NOT a new dependency (LOCK #4 is "no NEW dependency", see the reframe below). Those helpers are LAZY-imported inside the check functions (keeps the module-import graph light + matches the schwabdev-import-hazard precedent). pytest (`monkeypatch`, `capsys`, `tmp_path`). No schema, no migration, no `swing/data`/`swing/trades` carve-out (new read-only `swing/monitoring/` package importing repos + helpers read-only).

**Codex R1+R2+R3+R4+R5 dispositions baked in (R1: 4 MAJOR + 3 MINOR; R2: 3 MAJOR + 1 MINOR; R3: 1 MAJOR; R4: 1 MAJOR; R5: 1 MAJOR; full transcript + adjudication in `.copowers-findings.md`):** (R5-M1) the OHLCV mtime age mixed an absolute POSIX `st_mtime` with the naive-Hawaii `now` via a host-local interpretation (flips the 4d/7d boundary on a non-Hawaii box) -> pin `datetime.fromtimestamp(st_mtime, ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)` then subtract + a host-tz-independence test (Task 4); (R4-M1) the normalizer's `None`-default used host-local `datetime.now()` (mis-anchors on a non-Hawaii box) -> `datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)` (Task 5); (R3-M1) an aware `now` flowed unmodified into the session helpers (which RELABEL, not convert) -> a single boundary normalizer `_normalize_now_to_naive_local` at the `compute_tool_health` entry converts any aware `now` to naive-Hawaii-local before ANY consumer (Task 5) + `test_compute_tool_health_normalizes_aware_now`; and the R1/R2 set: (R1-M1/R2-M1) Schwab TTL naive/aware crash AND the ~10h naive-local-vs-UTC shift -> SPLIT `_now_to_utc` (attach Hawaii-local then convert) / `_issued_to_utc` (VM precedent) + a crash test + a boundary-shift test (Task 3); (R1-M2/R2-M3) "stdlib-only" reframed to "no NEW dependency" AND the no-pandas-in-monitor-code contradiction -> the session helper moved to a new pure `sessions_behind` in `swing/evaluation/dates.py`, so `tool_health.py` imports NO pandas (Tech Stack + LOCK #4 + Task 2); (R1-M3/R2-M2) session-behind calendar-day fallback REMOVED -> NYSE `sessions_behind` + weekend/holiday tests with the anchor off-by-one FIXED (Tasks 2/4); (R1-M4) bare-conn / missing-table three-way disambiguation (missing config->green; missing table->yellow; missing data->red) + narrowed tests (Tasks 2/4/5); (R2-m1) the missing-table `OperationalError` SCOPED to `"no such table"`/`"no such column"` (else re-raise); (R1-m1) `worst_of` validates unknown status (Task 1); (R1-m2) OHLCV tests assert WRITE-recency only (Task 4); (R1-m3) ASCII test reframed to platform-agnostic "stdout bytes decode as ASCII" (Task 6).

---

## Background — grounding (verified on disk at branch base `main` HEAD `2ac70521`)

Every signal already exists. The monitor AGGREGATES; it adds no new instrumentation. The grounded reuse anchors (the brief deferred the exact locations to writing-plans):

### Pipeline-run health (brief §4.1) — the two-read pattern + heartbeat-staleness convention
- **`swing/data/repos/pipeline.py` does NOT define a `pipeline_runs` repo module named as the brief warned** — the real reader is `swing/data/repos/pipeline.py` (the lease-fenced repo). The brief's warning that `swing/data/repos/pipeline_runs.py` does not exist is CORRECT; `pipeline.py` is the actual module.
- **Most-recent COMPLETED run** (data-freshness side of the two-read): `latest_completed_pipeline_run(conn)` at `swing/web/chart_scope.py:82` — `WHERE state = 'complete' ORDER BY finished_ts DESC, id DESC LIMIT 1`, returns a `PipelineRunBinding` (`chart_scope.py:61`) carrying `finished_ts`, `data_asof_date`, `action_session_date`, `charts_status`. This is the project's canonical "which run does this bind to" reader — REUSE it.
- **Most-recent RUNNING run** (the what's-happening-now side): `find_active_run(conn)` at `swing/data/repos/pipeline.py:152` — `WHERE state='running' LIMIT 1`, returns a `PipelineRun` model carrying `lease_heartbeat_ts`, `last_step_progress_ts`, `state`, `current_step`.
- **The `ORDER BY started_ts DESC` gotcha**: the canonical two-read note is `swing/web/view_models/dashboard.py:963-979` ("two independent reads so an in-flight run (finished_ts IS NULL) doesn't mask the last-known-good completion"). We REUSE the structured readers (`latest_completed_pipeline_run` + `find_active_run`) rather than re-issuing the raw `started_ts DESC` query, which is strictly better than the inline dashboard query.
- **Heartbeat-staleness convention**: `is_stale_eligible(run, cfg, *, now=None)` at `swing/pipeline/staleness.py:25` — a run is wedged-eligible only when state=='running' AND BOTH `lease_heartbeat_ts` and `last_step_progress_ts` are present AND BOTH ages exceed their thresholds (`cfg.pipeline.stale_lease_threshold_seconds`=300, `cfg.pipeline.stale_step_threshold_seconds`=900 — `swing/config.py:160-161`). Missing timestamps → NOT eligible (conservative). REUSE this function for the wedged-run check; it requires `cfg`, which the monitor threads through (see "The cfg dependency" below).
- **`data_asof_date` / `action_session_date` directionality** (the session-anchor gotcha): `action_session_date` is forward-looking; `data_asof_date` is the last completed data session. For freshness comparisons use the BACKWARD anchor `last_completed_session(now)` (`swing/evaluation/dates.py:40`), and compare with the writer's anchor (the completed run's `action_session_date` is the writer's forward anchor, so the "last good session refreshed?" check compares `binding.action_session_date` against `action_session_for_run(now)` — the EXACT comparison the dashboard stale-banner makes at `dashboard.py:982-985`). REUSE the dashboard stale-banner inequality shape.

### Schwab token TTL (brief §4.2) — reuse, do NOT re-derive the math
- **TTL + severity constants** (`swing/cli_schwab.py`): `_REFRESH_TOKEN_TTL_SECONDS = 7*24*3600` (L46); `_REFRESH_TOKEN_WARN_THRESHOLD_SECONDS = 24*3600` (L54); `_REFRESH_TOKEN_ERROR_THRESHOLD_SECONDS = 2*3600` (L55). These are the SINGLE source of TTL + severity-tier truth — import them; do NOT re-define.
- **Tokens-DB metadata reader**: `_read_tokens_metadata(tokens_path)` at `swing/cli_schwab.py:475` — opens the v3 schwabdev SQLite tokens DB `mode=ro`, returns `(meta, error_message)` where `meta` carries ONLY the non-secret `refresh_token_issued` ISO string (never token bytes). REUSE it.
- **ISO parse**: `_parse_iso_datetime(s)` at `swing/cli_schwab.py:396`.
- **The canonical severity-mapping precedent**: `swing/web/view_models/schwab.py:516-560` (`build_schwab_status_vm`) reuses EXACTLY these constituents — `_read_tokens_metadata` → `refresh_token_issued` → `_parse_iso_datetime` → `expires_dt = issued + _REFRESH_TOKEN_TTL_SECONDS` → `delta_seconds`; then maps `delta <= 0` → "error", `delta <= ERROR_THRESHOLD` → "error", `delta <= WARN_THRESHOLD` → "warn", else "ok". The monitor MIRRORS this severity-mapping precedent (it does not call the heavyweight CLI render path). The `{ok,warn,error}` severity → `{green,yellow,red}` color map.
- **Tokens path**: `~/swing-data/schwab-tokens.{env}.db` where `env = cfg.integrations.schwab.environment` (`swing/config.py:273`), home = `_user_home()` (`swing/config.py:551`). Same construction as `schwab.py:431-432`.
- **"No Schwab configured" → green/"n/a"**: when `cfg` is None, OR `cfg.integrations.schwab.client_id` is empty (`swing/config.py:286`), OR the tokens DB file does not exist (`_read_tokens_metadata` returns `(None, None)` on a missing file — `cli_schwab.py:488-489`) → emit green with summary "Schwab not configured (n/a)" — absence of Schwab is NOT a tool-health failure (brief §4.2).
- **schwabdev import hazard**: importing `swing.cli_schwab` at module top pulls schwabdev (heavyweight). The web VM uses a LOCAL import inside the function (`schwab.py:416-423`) to avoid eager schwabdev load. The monitor MUST do the same — import `_read_tokens_metadata` / `_parse_iso_datetime` / the constants lazily INSIDE `_check_schwab_token`, never at `swing/monitoring/tool_health.py` module top.

### Data freshness (brief §4.3)
- **(a) OHLCV archive**: the archive is per-ticker `{TICKER}.parquet` + `{TICKER}.meta.json` sidecars under `cfg.paths.prices_cache_dir` (`swing/data/ohlcv_archive.py:9-10, 125-126`). The meta sidecar carries ONLY `{"last_full_refresh_date": "YYYY-MM-DD"}` (`ohlcv_archive.py:620`) — NOT the newest bar date; the newest bar lives inside the parquet, which requires pandas to read (the monitor's own code stays no-pandas per LOCK #4, so it does NOT crack the parquet open). **V1 freshness signal = the most-recent `.parquet` file mtime in `prices_cache_dir`** (stdlib `os.stat`), i.e. "when was the archive last WRITTEN by any path". This is the truest no-pandas "is the collection apparatus alive" signal — 18-E's mandate is collection HEALTH, not per-bar correctness (see "V1 simplification" below; known limitation: mtime can be bumped by a non-collection touch). The session-anchor helper is `last_completed_session(now)` (`swing/evaluation/dates.py:40`).
- **(b) Weather**: `swing.data.repos.weather.get_latest(conn)` (`swing/data/repos/weather.py:65`) returns the most-recent `WeatherRun` by `run_ts DESC`, carrying `run_ts` (wall-clock) AND `asof_date` (the DATA session date — the gotcha: weather is keyed by `data_asof_date`). The freshness comparison uses `asof_date` (a session-date string, directly comparable to `last_completed_session(now).isoformat()`) — `asof_date` is the data-collection signal; `run_ts` is merely when the pipeline ran. The brief says "run_ts vs last session"; grounding shows `asof_date` is the correct session-comparable field (run_ts is a timestamp, not a session date), so the check compares `asof_date` for the session-staleness color AND reports `run_ts` in the detail. This is a brief-grounding refinement, flagged in the return report.

### The cfg dependency (architecture finding — the locked signature is preserved)
Two of three checks need filesystem inputs derived from cfg (Schwab: `env` + `_user_home()`; OHLCV: `prices_cache_dir`; the wedged-run check: `cfg.pipeline.*_threshold_seconds`). The §3-locked call shape is `compute_tool_health(conn)`. RESOLUTION: keyword-only OPTIONAL args with safe-degrade defaults —

```python
def compute_tool_health(
    conn: sqlite3.Connection,
    *,
    cfg=None,                    # Config; None -> schwab + wedged-run checks degrade
    prices_cache_dir=None,       # Path; None -> ohlcv freshness check degrades
    now: datetime | None = None, # injectable clock; default datetime.now()
) -> ToolHealthStatus: ...
```

`compute_tool_health(conn)` (the locked shape) stays a VALID call — 18-F may call it bare; the `scripts/tool_health.py` probe and 18-F's render path supply `cfg` + `prices_cache_dir` from `Config.from_defaults()` / `app.state.cfg` + `cfg.paths.prices_cache_dir`. When a CFG/CACHE-DIR input is absent the dependent check emits **green** with a `(config unavailable)` summary — a monitor never emits a false red for a missing CONFIG input. The pipeline-run-DATA checks (a) and (c) need only `conn`; only the wedged-run heartbeat check (b) needs `cfg` (it degrades to skipped-green without it). This is the architecture finding surfaced in the return report; it does NOT change the §3 envelope nor cross a tripwire.

**MISSING-CONFIG (n/a -> green) vs MISSING-DATA (-> red) vs MISSING-SCHEMA (-> yellow) — three distinct degradations (Codex R1 MAJOR #4).** They are NOT the same: (1) a missing CFG/CACHE input is an absent OPTIONAL config -> green/"n/a" (the brief's "absence of Schwab is not a failure" generalized); (2) missing operational DATA on a schema-present DB (no completed pipeline run, no weather row) is a REAL collection failure -> red (intended — that is the monitor's job); (3) a pre-schema / missing-TABLE connection (`sqlite3.OperationalError: no such table`) must NOT crash the monitor — each check WRAPS its DB reads and degrades a missing table to **yellow** "schema unavailable" (a monitor must survive a degraded DB). The bare-`conn` LOCK test (Task 5 #4) therefore runs against a SCHEMA-PRESENT-but-empty DB and asserts the n/a-vs-data-vs-schema distinction explicitly.

**The `now`-handling contract (Codex R1 MAJOR #1 crash + Codex R2 MAJOR #1 tz-correctness + Codex R3 MAJOR #1 boundary normalization).** The monitor's top-level `now` is normalized to a **NAIVE HAWAII-LOCAL** `datetime` at the `compute_tool_health` boundary by `_normalize_now_to_naive_local` (Task 5): `None` → `datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)` (Hawaii wall clock — Codex R4 MAJOR #1; NOT bare `datetime.now()`, which is host-local and mis-anchors on a non-Hawaii box); an AWARE `now` → `.astimezone(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)` (CONVERT the instant to Hawaii-local then strip tzinfo); a naive `now` passes through. This is REQUIRED because the reused session helpers `last_completed_session(now)` / `action_session_for_run(now)` do `now_local.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))` (`dates.py:45,68`) — which RELABELS (not converts) an aware datetime → mis-anchored sessions (Codex R3 MAJOR #1: an aware `19:00+00:00` would be relabeled `19:00 HST` instead of converted to `09:00 HST`). After this single boundary normalization, EVERY downstream consumer (the session helpers AND the schwab `_now_to_utc`) receives a naive-Hawaii-local `now`. The Schwab check, however, must do UTC-aware arithmetic (the tokens file writes `datetime.now(timezone.utc).isoformat()` → `_parse_iso_datetime` returns an AWARE dt; subtracting a naive `now` raises `TypeError`). Critically, a naive `now` is HAWAII-LOCAL, NOT UTC — so `_check_schwab_token` uses TWO distinct normalize rules (Task 3): `_now_to_utc(now)` attaches `Pacific/Honolulu` to a naive `now` then converts to UTC (`.astimezone(UTC)` if already aware) — NOT a bare `replace(tzinfo=UTC)`, which would mis-shift by ~10h and flip the 24h/2h boundary; `_issued_to_utc(issued)` follows the VM precedent (`schwab.py:752-754`: `replace(tzinfo=UTC)` for naive token timestamps, which ARE UTC-origin). Task 3 adds `test_schwab_aware_iso_timestamp` (crash test) AND `test_schwab_now_uses_local_tz_not_utc` (the ~10h-shift boundary test).

### Surface decision — `scripts/tool_health.py` probe (NOT a `swing` CLI subcommand)
Per the brief's lean (§2) and the operator-probe family precedent: a `scripts/tool_health.py` that imports `swing.monitoring.tool_health`, mirroring `scripts/weekly_glance.py` + `scripts/harness_probe.py` (read-only, `mode=ro`, ASCII, `argparse`, `sys.exit`). Rationale: (1) keeps the operator-probe family consistent (three single-purpose probes over distinct domains — hygiene/research/tool-health); (2) avoids growing `swing/cli.py`, the largest module (CLAUDE.md note); (3) the aggregating LOGIC lives in the importable `swing/monitoring/` package so 18-F's web render reuses it without going through the CLI. **Decision: `scripts/tool_health.py`.**

### Disciplines preserved (CLAUDE.md §Gotchas / dispatch recipe §5)
- **no-new-dependency + read-only (LOCK #1, #4)**: `mode=ro` URI connection in the script (`weekly_glance.py:111` precedent); no DB write anywhere; no pandas IN THE MONITOR'S OWN CODE (parquet mtime via `os.stat`, not `pd.read_parquet`); reuse of `swing.evaluation.dates`/`swing.cli_schwab` (existing project deps) is lazy-imported and is reuse-not-fork, not a new dependency (Codex R1 MAJOR #2).
- **ASCII-only (LOCK #4, the cp1252 gotcha)**: every `summary`/`detail`/`print` is ASCII; a subprocess-through-PowerShell encoding test guards it (the gotcha: `capsys` bypasses the OS encoder, so a pure-`capsys` test is insufficient — Task 6 adds the subprocess test).
- **`Literal`-not-runtime-enforced gotcha (LOCK #5)**: `ToolHealthCheck`/`ToolHealthStatus` validate the status enum against a module frozenset in `__post_init__` (the `SchwabStatusVM` precedent at `schwab.py:165-176, 260-286`).
- **Synthetic-vs-production drift (recipe §5)**: per-check tests derive inputs from the REAL repo readers' return types (`PipelineRunBinding`, `PipelineRun`, `WeatherRun`) and the REAL meta-sidecar shape, not hand-rolled dicts.
- **Session-anchor directionality**: backward anchor `last_completed_session` for "is the data fresh"; the dashboard stale-banner forward-anchor inequality for "did the last good run cover the current action session".

---

## File Map

- **Create:** `swing/monitoring/__init__.py` — new package marker (empty or a one-line docstring).
- **Create:** `swing/monitoring/tool_health.py` — the envelope dataclasses + `compute_tool_health` + the three pure per-check helpers. The ONLY new production module of substance. Pure, read-only; lazy-imports `swing.cli_schwab` + `swing.evaluation.dates` helpers inside the check functions. **NO pandas import here (Codex R2 MAJOR #3) — session arithmetic goes through the new `dates.py` helper below.**
- **Modify:** `swing/evaluation/dates.py` — ADD one pure read-only helper `sessions_behind(reference: date, candidate: date) -> int` (stdlib `date` in/out; internally uses the module's existing `_NYSE`/pandas — the canonical session-arithmetic home). This keeps pandas OUT of monitor-owned code (Codex R2 MAJOR #3 resolution). Purely additive; NO existing function changed; NOT a `swing/data`/`swing/trades` carve-out; NO schema, NO measurement-chain touch. Flagged in the return report as a benign session-helper addition. (Task 2 ships it with its own unit test.)
- **Create:** `scripts/tool_health.py` — the operator probe (ASCII / `--json`), mirrors `scripts/weekly_glance.py`.
- **Create:** `tests/monitoring/__init__.py` — test package marker.
- **Create:** `tests/monitoring/test_tool_health_envelope.py` — dataclass validation + `overall` worst-of + JSON serialization.
- **Create:** `tests/monitoring/test_tool_health_checks.py` — the three per-check helpers (boundary regression arithmetic).
- **Create:** `tests/monitoring/test_tool_health_aggregate.py` — `compute_tool_health` end-to-end against a seeded `mode=rw`-built / `mode=ro`-read DB + tmp cache_dir.
- **Create:** `tests/scripts/test_tool_health_script.py` — the probe surface (ASCII report, `--json`, exit code, subprocess-through-PowerShell encoding guard).

**Executing worktree (for the executing-plans cycle that follows this plan): `<repo>/.worktrees/phase18-arc-e-exec`.**

---

## Task 1: The envelope dataclasses (`ToolHealthCheck` + `ToolHealthStatus`) + `to_dict` JSON serialization

**Files:**
- Create: `swing/monitoring/__init__.py`, `swing/monitoring/tool_health.py` (dataclasses + serialization only)
- Create: `tests/monitoring/__init__.py`, `tests/monitoring/test_tool_health_envelope.py`

The §3-locked contract, encoded 1:1. Two `@dataclass(frozen=True)` types with `__post_init__` frozenset validation (the `Literal`-not-runtime-enforced gotcha), a module-level `_STATUS_VALUES = frozenset({"green", "yellow", "red"})`, an `overall` computed by a `worst_of` helper, and a `to_dict()` that serializes the §3 envelope (`monitor`, `generated_ts`, `overall`, `checks[]`).

- [ ] **Step 1: Write the failing tests**

`tests/monitoring/test_tool_health_envelope.py`:

1. `test_check_rejects_unknown_status` — `ToolHealthCheck(key="x", status="grey", summary="s")` raises `ValueError` (grey is render-only per §3, NOT monitor-emitted). Under the PRE-fix path (no `__post_init__` validation) the constructor SUCCEEDS (no error) — test FAILS. Under POST-fix it raises `ValueError` — test PASSES. (Distinguishes: pre-fix returns an object; post-fix raises.)
2. `test_status_rejects_unknown_overall` — `ToolHealthStatus(overall="purple", checks=[])` raises `ValueError`. Pre-fix: constructs fine (FAIL). Post-fix: raises (PASS).
3. `test_worst_of` — assert exact mapping: `worst_of([])` == "green"; `worst_of(["green","green"])` == "green"; `worst_of(["green","yellow"])` == "yellow"; `worst_of(["yellow","red","green"])` == "red". Computed both ways: a naive `max()` on the strings would give `"yellow"` for `["green","yellow"]` (lexical: yellow > green > red? no — lexically "red" < "yellow", so `max(["yellow","red","green"])` == "yellow" NOT "red"). So a wrong `max()`-on-strings impl returns "yellow" for case 4; the correct severity-rank impl returns "red". Test FAILS on the naive impl, PASSES on the rank-based impl. (Distinguishes: the rank ordering red>yellow>green is NOT the lexical order.)
4. `test_to_dict_matches_envelope` — build a `ToolHealthStatus(overall="yellow", checks=[ToolHealthCheck(key="schwab_token_ttl", status="yellow", summary="Schwab token expires in 2 days", detail="refresh by ...")], generated_ts="2026-06-14T20:31:00")`; assert `to_dict()` == the exact §3 dict: `{"monitor":"tool_health","generated_ts":"2026-06-14T20:31:00","overall":"yellow","checks":[{"key":"schwab_token_ttl","status":"yellow","summary":"...","detail":"..."}]}`; and assert `json.dumps(status.to_dict())` round-trips (no exception, parses back equal). A check with `detail=None` serializes with `"detail": None` (or omits it — pin: INCLUDE the key with `null` for envelope stability; assert `"detail" in d["checks"][0]`).
5. `test_monitor_field_is_tool_health` — `to_dict()["monitor"] == "tool_health"` (the §3 identifier; 18-D emits "research").
6. `test_generated_ts_default_is_naive_iso` — when `generated_ts` is omitted, `ToolHealthStatus(overall="green", checks=[])` stamps a naive ISO-8601 `datetime.now().isoformat(timespec="seconds")`-shaped string (assert it parses via `datetime.fromisoformat` AND has no `+00:00`/`Z` suffix — project convention "ISO 8601 naive"). Pin: the field has a `default_factory`; test asserts `"T" in ts and "+" not in ts and not ts.endswith("Z")`.
7. `test_worst_of_rejects_unknown_status` (Codex R1 MINOR #1) — `worst_of(["grey"])` raises `ValueError` (NOT `KeyError`). Pre-fix (bare `_SEVERITY_RANK[s]`): raises `KeyError` → `pytest.raises(ValueError)` FAILS. Post-fix (validation): raises `ValueError` → PASSES. (Distinguishes the exception TYPE.)

Run: `python -m pytest tests/monitoring/test_tool_health_envelope.py -q` → all FAIL (module/classes do not exist).

- [ ] **Step 2: Implement the dataclasses**

In `swing/monitoring/tool_health.py`:

```python
"""Operational tool-health monitor (Phase 18 Arc 18-E).

Read-only roll-up of EXISTING data-collection-enabling signals -- pipeline-run
health, Schwab token TTL, OHLCV + weather freshness. Aggregates; instruments
nothing. Returns the CHARC-owned monitor-status envelope (the contract 18-F's
stoplight + 18-D's research monitor consume). stdlib only; ASCII only; never
writes the DB.
"""
from __future__ import annotations

import sqlite3  # noqa: F401  (used in compute_tool_health signature later)
from dataclasses import dataclass, field
from datetime import datetime

_STATUS_VALUES = frozenset({"green", "yellow", "red"})
_SEVERITY_RANK = {"green": 0, "yellow": 1, "red": 2}
_MONITOR_ID = "tool_health"


def worst_of(statuses: list[str]) -> str:
    """red > yellow > green; empty -> green. NOT lexical order.

    Codex R1 MINOR #1: validate each status against _STATUS_VALUES so an
    unknown value raises a contract-shaped ValueError (not a bare KeyError
    from the rank lookup) -- belt-and-suspenders since ToolHealthCheck
    already validates at construction.
    """
    worst = "green"
    for s in statuses:
        if s not in _STATUS_VALUES:
            raise ValueError(
                f"worst_of: unknown status {s!r}; must be one of"
                f" {sorted(_STATUS_VALUES)}"
            )
        if _SEVERITY_RANK[s] > _SEVERITY_RANK[worst]:
            worst = s
    return worst


@dataclass(frozen=True)
class ToolHealthCheck:
    key: str
    status: str
    summary: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _STATUS_VALUES:
            raise ValueError(
                f"ToolHealthCheck.status must be one of {sorted(_STATUS_VALUES)};"
                f" got {self.status!r} (grey is an 18-F render-only state, not"
                " monitor-emitted)"
            )
        if not self.key:
            raise ValueError("ToolHealthCheck.key must be non-empty")
        if not self.summary:
            raise ValueError("ToolHealthCheck.summary must be non-empty")

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "status": self.status,
            "summary": self.summary,
            "detail": self.detail,
        }


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class ToolHealthStatus:
    overall: str
    checks: list[ToolHealthCheck]
    generated_ts: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        if self.overall not in _STATUS_VALUES:
            raise ValueError(
                f"ToolHealthStatus.overall must be one of {sorted(_STATUS_VALUES)};"
                f" got {self.overall!r}"
            )

    def to_dict(self) -> dict:
        return {
            "monitor": _MONITOR_ID,
            "generated_ts": self.generated_ts,
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
        }
```

**Acceptance:** all `test_tool_health_envelope.py` tests pass. `ruff check swing/` clean. Commit: `feat(monitoring): Task 1 -- tool-health envelope dataclasses + JSON serialization`.

---

## Task 2: `_check_pipeline_run` — the two-read pattern (data-freshness + wedged + recent failures) + the `sessions_behind` helper

**Files:**
- Modify: `swing/evaluation/dates.py` (ADD the pure `sessions_behind(reference, candidate) -> int` helper — Codex R2 MAJOR #3, keeps pandas out of monitor code)
- Modify: `swing/monitoring/tool_health.py` (add `_check_pipeline_run`)
- Modify: `tests/monitoring/test_tool_health_checks.py` (new file; pipeline section)
- Modify: `tests/evaluation/test_dates.py` (the `sessions_behind` standalone test — or co-locate in the monitor test if `test_dates.py` is awkward)

Reuses `latest_completed_pipeline_run(conn)` (`chart_scope.py:82`) + `find_active_run(conn)` (`pipeline.py:152`) + `is_stale_eligible(run, cfg, now=)` (`staleness.py:25`) + `action_session_for_run`/`last_completed_session` (`dates.py`). Emits up to three `ToolHealthCheck` rows, all with `key` prefix `pipeline_`:

- `pipeline_freshness` — compares the most-recent COMPLETED run's `action_session_date` vs `action_session_for_run(now)` (the dashboard stale-banner inequality, `dashboard.py:982-985`). Fresh (`>=` current action session) → green. One session behind → yellow. Two+ behind → red. NO completed run ever → red ("no completed pipeline run").
- `pipeline_wedged` — if `find_active_run(conn)` returns a running row AND `cfg` is provided AND `is_stale_eligible(run, cfg, now=now)` → red ("pipeline run wedged: heartbeat + step-progress stale"). Running-but-not-stale → green ("pipeline running"). No running row → green ("no active run"). `cfg is None` → green (skipped; degrade — the heartbeat thresholds need cfg).
- `pipeline_failures` — count `state` in `('failed','force_cleared')` among the most-recent N runs (use `list_recent_runs(conn, limit=...)` at `pipeline.py:168`); >=1 recent failure → yellow ("N recent pipeline failure(s)"); 0 → green.

**Module thresholds** (the `weekly_glance.py` `T1_MAX_AGE_DAYS` precedent — pinned constants near the top of `tool_health.py`):
```python
# Pipeline freshness: how many action-sessions behind the last COMPLETE run may
# be before escalating. Calibrated against the dashboard stale-banner (which
# flags at >=1 session behind). 1 session behind -> yellow; >=2 -> red.
_PIPELINE_FRESH_YELLOW_SESSIONS = 1
_PIPELINE_FRESH_RED_SESSIONS = 2
# Recent-runs window for the failure tally.
_PIPELINE_RECENT_RUNS_WINDOW = 5
```
**The "sessions behind" count MUST use NYSE-session arithmetic — NO calendar-day fallback (Codex R1 MAJOR #3), via the new `dates.py` helper, NO pandas in monitor code (Codex R2 MAJOR #3).** A calendar-day fallback false-reds across weekends/holidays. **Grounding note for the executor:** `dates.py:11` holds `_NYSE = xcals.get_calendar("XNYS")` and uses `_NYSE.previous_session(pd.Timestamp(d))` (`dates.py:55`). `dates.py` exposes NO "sessions between two dates" helper, so **Task 2 ADDS `sessions_behind(reference: date, candidate: date) -> int` to `swing/evaluation/dates.py`** (the module that already owns `_NYSE`/pandas) — pure, stdlib `date` in/out, returns 0 if `candidate >= reference`, else the count of NYSE sessions from `candidate` up to `reference` (walk `_NYSE.previous_session` from `reference` until reaching `candidate`, bounded). The monitor imports THIS helper (NO pandas in `tool_health.py`). The pipeline-freshness check computes: `anchor = action_session_for_run(now)` (a `date`); `behind = sessions_behind(anchor, date.fromisoformat(binding.action_session_date))`; `behind == 0` → green, `behind == 1` → yellow, `behind >= 2` → red. (Parse the ISO `action_session_date` string to a `date` at the callsite — the `date.fromisoformat` TEXT-boundary gotcha.) Pin the NYSE-precise rule in the tests below (weekend + holiday boundaries), NOT a calendar-day approximation.

- [ ] **Step 1: Write the failing tests** (`tests/monitoring/test_tool_health_checks.py`, pipeline section)

Inputs are constructed from the REAL return types (`PipelineRunBinding`, `PipelineRun`) via thin fakes OR a seeded DB; prefer a seeded in-memory `sqlite3` with the real schema (`ensure_schema`) + real repo inserts (`insert_pipeline_run` + `finalize_run`) so the test exercises the production read path (anti-drift discipline).

1. `test_pipeline_freshness_green_when_current` — seed a `complete` run whose `action_session_date == action_session_for_run(frozen_now).isoformat()`; assert the `pipeline_freshness` check status == "green". Both-ways: pre-fix (no check) → KeyError/empty; the assertion targets the post-fix emitted row.
2. `test_pipeline_freshness_yellow_one_behind` — seed a `complete` run whose `action_session_date` is the PRIOR action session (one NYSE session before `action_session_for_run(frozen_now)`); assert status == "yellow". Arithmetic: with `frozen_now` = a Wednesday post-close, `action_session_for_run` = Thursday; prior session = Wednesday → 1 behind → yellow (NOT green: green requires `>=` current; NOT red: red requires `>=2` behind). A green-returning impl FAILS here; a red-returning impl FAILS here; only the 1-behind→yellow impl passes.
3. `test_pipeline_freshness_red_two_behind` — `action_session_date` two sessions behind → status == "red". (1-behind impl returns yellow here → FAIL; correct impl returns red.)
4. `test_pipeline_freshness_red_when_no_complete_run` — empty `pipeline_runs` (only a `running` row, or none) → "red", summary mentions "no completed".
5. `test_pipeline_wedged_red_when_stale` — seed a `running` run with `lease_heartbeat_ts` + `last_step_progress_ts` both > thresholds old (relative to `frozen_now`); pass a real `cfg` (`Config.from_defaults()`); assert `pipeline_wedged` == "red". Arithmetic: heartbeat age = 400s > 300 (`stale_lease_threshold_seconds`) AND step age = 1000s > 900 (`stale_step_threshold_seconds`) → `is_stale_eligible` True → red. A fresh-heartbeat seed (age 10s) returns green → the test distinguishes (seed both: one red, one green assertion).
6. `test_pipeline_wedged_green_when_running_fresh` — `running` run, heartbeat age 10s → "green" ("pipeline running").
7. `test_pipeline_wedged_green_when_cfg_none` — `running` + stale heartbeat but `cfg=None` → "green" (degraded-skip), summary mentions "running" or "n/a" (NOT red — a missing cfg must not false-red).
8. `test_pipeline_failures_yellow` — seed 2 `failed` runs in the recent window → `pipeline_failures` == "yellow", summary "2 recent pipeline failure(s)". Zero-failure seed → green (distinguishes).
9. `test_pipeline_freshness_yellow_across_weekend` (Codex R1 MAJOR #3, anchor FIXED per Codex R2 MAJOR #2) — pick `frozen_now` = a WEEKEND day (e.g. Sunday, a NON-session) so `action_session_for_run(frozen_now)` = the upcoming Monday and `sessions_behind(Monday, Friday) == 1` (Friday is the prior session across the weekend); seed `action_session_date` = that Friday. Assert "yellow" (1 behind), NOT "red". A calendar-day-`>=`-2 impl sees Friday→Monday = 3 calendar days → red → FAIL; the `sessions_behind` impl returns yellow → PASS. (This is the test that kills the calendar-day fallback. NOTE: the R1 draft used Monday-post-close → anchor=Tuesday → Friday is 2-behind=red — a self-contradiction Codex R2 caught; the WEEKEND anchor makes Friday genuinely 1-behind.)
10. `test_pipeline_freshness_yellow_across_holiday` (Codex R1 MAJOR #3) — pick a `frozen_now` (a non-session day immediately after a market HOLIDAY weekend) so `action_session_for_run` = the first session after the holiday and `sessions_behind(anchor, prior_session) == 1` across >2 calendar days; seed `action_session_date` = that single prior session. Assert "yellow". A calendar-day impl false-reds → FAIL; the `sessions_behind` impl → yellow PASS. (Choose a concrete real holiday from the NYSE calendar, e.g. a Memorial Day or July 4th weekend in 2026, and verify `sessions_behind` returns 1 in the test setup.)
11. `test_pipeline_missing_table_degrades_yellow_not_crash` (Codex R1 MAJOR #4) — pass a connection to a DB with NO `pipeline_runs` table (an empty `:memory:` conn, no `ensure_schema`); assert `_check_pipeline_run` returns a `ToolHealthCheck` with status "yellow" + summary containing "schema unavailable" and does NOT raise. A naive impl (unwrapped query) raises → FAIL; the wrapped impl returns yellow → PASS.
12. `test_sessions_behind_helper` (Codex R2 MAJOR #3 — the new `dates.py` helper, tested standalone in `tests/evaluation/test_dates.py` or the monitor test) — assert `sessions_behind(ref, cand)` == 0 when `cand >= ref`; == 1 for a session and its immediate predecessor (incl. a Monday/Friday weekend pair); == 2 for two sessions apart; correctly skips a market holiday (a session and the session two calendar-weeks-but-1-session earlier). A calendar-day `(ref-cand).days` impl FAILS the weekend + holiday cases; the `_NYSE.previous_session`-walk impl PASSES.

Run → FAIL (`_check_pipeline_run` / `sessions_behind` undefined).

**Missing-table handling (Codex R2 MINOR #1 — scoped):** `_check_pipeline_run` wraps its `pipeline_runs` reads in `try/except sqlite3.OperationalError as exc` and degrades to a single yellow "pipeline schema unavailable" check ONLY when `"no such table"` (or `"no such column"`) is in `str(exc)`; ANY OTHER `OperationalError` is RE-RAISED (do NOT mask non-schema defects as "schema unavailable"). This crash-survival is for a degraded/pre-schema DB, not a blanket swallow. All other (schema-present) paths behave per the bullets above.

- [ ] **Step 2: Implement** (a) `sessions_behind(reference: date, candidate: date) -> int` in `swing/evaluation/dates.py` (pure; uses the module's existing `_NYSE`/`pd`; returns 0 when `candidate >= reference`, else walks `_NYSE.previous_session` from `reference` counting steps to reach `candidate`, with a sane bound so a far-past candidate returns a large int rather than looping forever); then (b) `_check_pipeline_run(conn, *, cfg, now) -> list[ToolHealthCheck]` in `tool_health.py` reusing the grounded readers + `sessions_behind` (NO pandas imported in `tool_health.py`). Keep all strings ASCII. Two commits if cleaner (the `dates.py` helper, then the check), or one — implementer's call per the TDD cycle.

**Acceptance:** pipeline-section tests + the `sessions_behind` test pass; `ruff check swing/` clean (the `dates.py` addition is inside the lint gate — keep it clean). Commit: `feat(evaluation): Task 2a -- sessions_behind NYSE helper` + `feat(monitoring): Task 2b -- pipeline-run health check (two-read + wedged + failures)`.

---

## Task 3: `_check_schwab_token` — reuse the TTL + severity logic

**Files:**
- Modify: `swing/monitoring/tool_health.py` (add `_check_schwab_token`)
- Modify: `tests/monitoring/test_tool_health_checks.py` (schwab section)

Emits ONE check, `key="schwab_token_ttl"`. LAZY-imports (inside the function) `_REFRESH_TOKEN_TTL_SECONDS`, `_REFRESH_TOKEN_WARN_THRESHOLD_SECONDS`, `_REFRESH_TOKEN_ERROR_THRESHOLD_SECONDS`, `_read_tokens_metadata`, `_parse_iso_datetime` from `swing.cli_schwab` (the schwabdev-import hazard — `schwab.py:416` precedent). Mirrors the `build_schwab_status_vm` severity mapping (`schwab.py:516-560`).

**The naive/aware datetime contract (Codex R1 MAJOR #1, tz-correctness FIXED per Codex R2 MAJOR #1) — BINDING.** The tokens file writes aware UTC timestamps (`datetime.now(timezone.utc).isoformat()`), so `_parse_iso_datetime(issued_iso)` returns an AWARE dt. The monitor's top-level `now` is naive HAWAII-LOCAL (the session-helpers' tz, `dates.py:40,62` default `Pacific/Honolulu`). The two operands need DIFFERENT normalize rules (a naive `now` is NOT UTC — treating it as UTC shifts the TTL by ~10h and can flip the 24h/2h boundary, Codex R2 MAJOR #1):
- **`now` → UTC:** `_now_to_utc(now)` = `now.astimezone(UTC)` if `now.tzinfo is not None` else `now.replace(tzinfo=ZoneInfo("Pacific/Honolulu")).astimezone(UTC)` (attach the LOCAL tz, then convert — NOT `replace(tzinfo=UTC)`).
- **issued → UTC:** `_issued_to_utc(issued)` = `issued.astimezone(UTC)` if aware else `issued.replace(tzinfo=UTC)` (the VM precedent `schwab.py:752-754` — token timestamps ARE UTC-origin).

Then `issued_utc = _issued_to_utc(issued_dt)`, `now_utc = _now_to_utc(now)`, `expires_utc = issued_utc + timedelta(seconds=_REFRESH_TOKEN_TTL_SECONDS)`, `delta_seconds = (expires_utc - now_utc).total_seconds()`. Both operands aware → no `TypeError`; the local→UTC conversion is correct → no boundary misclassification. The severity mapping consumes `delta_seconds`:

- `cfg is None` OR `cfg.integrations.schwab.client_id == ""` → green, summary "Schwab not configured (n/a)".
- tokens DB does not exist (`_read_tokens_metadata` returns `(None, None)`) → green, "Schwab tokens not present (n/a)".
- tokens DB unreadable (`_read_tokens_metadata` returns `(None, <msg>)`) → yellow, summary "Schwab tokens unreadable" + detail = the (already-ASCII, already-redacted) message.
- `refresh_token_issued` missing/unparseable → yellow, "Schwab token issue date unknown; run swing schwab status".
- `delta_seconds <= 0` (expired) → red, "Schwab token EXPIRED N days ago; swing schwab setup".
- `delta_seconds <= ERROR_THRESHOLD` (<=2h) → red, "Schwab token expires in <2h; swing schwab setup".
- `delta_seconds <= WARN_THRESHOLD` (<=24h) → yellow, "Schwab token expires in <1 day; swing schwab setup".
- else → green, "Schwab token valid for N day(s)".

(Days remaining displayed via integer floor `int(delta_seconds // 86400)`, the `schwab.py:543-545` convention.)

- [ ] **Step 1: Write the failing tests** (schwab section). Use a `tmp_path` v3-shape tokens DB built with the REAL `schwabdev` column shape that `_read_tokens_metadata` SELECTs (`access_token_issued, refresh_token_issued, expires_in, refresh_token` in a `schwabdev` table — `cli_schwab.py:496-499`), seeded via raw `sqlite3` so the production reader is exercised. Monkeypatch `_user_home` (and the env-var `USERPROFILE`/`HOME` per the `write_user_overrides` gotcha) so the tokens path resolves to `tmp_path`. Build a `cfg` via `Config.from_defaults()` (or a minimal stub exposing `integrations.schwab.environment`/`client_id`).

1. `test_schwab_green_when_cfg_none` — `_check_schwab_token(cfg=None, now=...)` → "green", summary contains "n/a". (A red/yellow-returning impl FAILS — absence is not failure.)
2. `test_schwab_green_when_client_id_empty` — cfg with `client_id=""` → "green"/"n/a".
3. `test_schwab_green_when_tokens_absent` — cfg configured, NO tokens DB file → "green"/"n/a".
4. `test_schwab_yellow_at_24h_boundary` — seed `refresh_token_issued` = `now - (TTL - WARN_THRESHOLD)` so `delta == WARN_THRESHOLD == 86400`s exactly → "yellow" (inclusive upper bound: `delta <= 24h` ⇒ warn, per `cli_schwab.py:807`). Arithmetic: issued = now - (7d - 24h) = now - 6d → delta = 24h exactly → yellow. A strict-`<` impl returns green at the boundary → FAIL; the `<=` impl returns yellow → PASS. (Distinguishes the boundary.)
5. `test_schwab_red_at_2h_boundary` — delta == ERROR_THRESHOLD == 7200s exactly → "red" (inclusive: `delta <= 2h` ⇒ error, `cli_schwab.py:805`). issued = now - (7d - 2h). Yellow-returning impl FAILS; red PASSES.
6. `test_schwab_red_when_expired` — issued = now - 8d → delta < 0 → "red", summary "EXPIRED".
7. `test_schwab_green_when_healthy` — issued = now - 1d → delta = 6d → "green", summary "valid for 5 day(s)" or "6 day(s)" (pin: `int(delta//86400)` = `int(6d//1d)` = 6 → assert "6 day(s)"). A wrong off-by-one (e.g. rounding up) returns 7 → FAIL.
8. `test_schwab_yellow_when_unreadable` — write a tokens DB file with NO `schwabdev` table (so `_read_tokens_metadata` returns `(None, "<...pre-v3...>")`) → "yellow", summary "unreadable".
9. `test_schwab_aware_iso_timestamp` (Codex R1 MAJOR #1) — seed `refresh_token_issued` as an AWARE ISO string (`"...+00:00"`, i.e. `datetime.now(UTC) - timedelta(days=1)` then `.isoformat()`) AND pass a NAIVE `now=datetime(...)` (no tzinfo). Assert the check returns a `ToolHealthCheck` (does NOT raise `TypeError: can't subtract offset-naive and offset-aware datetimes`). A naive-subtract impl raises TypeError → the test FAILS; the normalize-both-operands impl returns → PASSES. (Distinguishes the tz-mixing CRASH — the LIVE tokens file always writes aware timestamps.)
10. `test_schwab_now_uses_local_tz_not_utc` (Codex R2 MAJOR #1 — the ~10h shift) — construct a scenario where treating a naive-local `now` as UTC vs as Hawaii-local flips the severity tier. E.g. set issued so that `delta_seconds` is ~24h+5h when `now` is correctly Hawaii-local (→ green, >24h) but would be ~24h-5h if `now` were wrongly treated as UTC (→ yellow, <=24h) — i.e. place the true delta and the mis-shifted delta on OPPOSITE sides of the 24h boundary (the 10h HST↔UTC offset is ample). Pass the naive-local `now`; assert "green". A `replace(tzinfo=UTC)`-on-now impl returns "yellow" (mis-shifted) → FAIL; the `_now_to_utc` (attach-local-then-convert) impl returns "green" → PASS. (Distinguishes the tz-CORRECTNESS bug, not just the crash. Compute both deltas explicitly in the test docstring per the regression-arithmetic discipline.)

Run → FAIL.

- [ ] **Step 2: Implement** `_check_schwab_token(*, cfg, now) -> list[ToolHealthCheck]` with the lazy import + the SPLIT `_now_to_utc` / `_issued_to_utc` tz contract + the mirrored severity mapping. All summaries ASCII (NO em-dash; use `; ` separators).

**Acceptance:** schwab-section tests pass; `ruff check swing/` clean. Commit: `feat(monitoring): Task 3 -- Schwab token TTL check (reuse cli_schwab severity tiers)`.

---

## Task 4: `_check_data_freshness` — OHLCV archive mtime + weather asof_date

**Files:**
- Modify: `swing/monitoring/tool_health.py` (add `_check_data_freshness`)
- Modify: `tests/monitoring/test_tool_health_checks.py` (freshness section)

Emits up to TWO checks: `key="ohlcv_freshness"` and `key="weather_freshness"`.

**OHLCV** (`prices_cache_dir` keyword; `now` is the normalized naive-Hawaii-local from the aggregator):
- `prices_cache_dir is None` OR the dir does not exist OR no `*.parquet` present → green, "OHLCV archive freshness n/a (cache dir unavailable)" (degrade — never false-red on a missing input).
- **mtime age math — host-tz-independent (Codex R5 MAJOR #1):** `st_mtime` is an absolute POSIX timestamp; convert it to naive-Hawaii-local BEFORE subtracting from the (naive-Hawaii-local) `now`: `mtime_dt = datetime.fromtimestamp(st_mtime, ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)`; `age_days = (now - mtime_dt).total_seconds() / 86400`. Do NOT use `now.timestamp()` (interprets a naive `now` as HOST-local) or bare `datetime.fromtimestamp(mtime)` (host-local) — either shifts the age by the host-vs-HST offset on a non-Hawaii box and can flip a boundary.
- `age_days <= _OHLCV_FRESH_YELLOW_DAYS` → green.
- `_OHLCV_FRESH_YELLOW_DAYS < age_days <= _OHLCV_FRESH_RED_DAYS` → yellow.
- `age_days > _OHLCV_FRESH_RED_DAYS` → red.

**Weather** (`conn` only, via `get_latest`):
- `get_latest(conn)` is None → red, "no weather run recorded".
- `asof_date >= last_completed_session(now).isoformat()` → green ("weather current as of <asof>").
- one NYSE session behind `last_completed_session(now)` → yellow; two+ behind → red. **Uses the SAME `_sessions_behind` NYSE-`previous_session` helper as Task 2 (Codex R1 MAJOR #3) — NO calendar-day fallback.** Here the anchor is the BACKWARD `last_completed_session(now)` (weather's `asof_date` is a data-session date), not the forward `action_session_for_run`. Detail carries `run_ts` ("pipeline ran <run_ts>").
- Missing `weather_runs` TABLE (`sqlite3.OperationalError` whose `str(exc)` contains `"no such table"`/`"no such column"` on a pre-schema conn) → yellow "weather schema unavailable" (degrade-not-crash, Codex R1 MAJOR #4); any OTHER `OperationalError` re-raises (Codex R2 MINOR #1) — distinct from an EMPTY table (no rows) which is red "no weather run recorded".

**Module thresholds** (the weekend-tolerance precedent is `weekly_glance.py:27` `T1_MAX_AGE_DAYS = 4`):
```python
# OHLCV archive write recency (calendar days; 4 tolerates a normal weekend,
# matching weekly_glance.T1_MAX_AGE_DAYS). >4 -> yellow; >7 -> red.
_OHLCV_FRESH_YELLOW_DAYS = 4
_OHLCV_FRESH_RED_DAYS = 7
# Weather freshness in NYSE sessions behind last_completed_session.
_WEATHER_FRESH_YELLOW_SESSIONS = 1
_WEATHER_FRESH_RED_SESSIONS = 2
```

- [ ] **Step 1: Write the failing tests** (freshness section).

OHLCV (these tests assert ARCHIVE-WRITE-RECENCY only — NOT bar freshness; Codex R1 MINOR #2 — no test names/asserts claim "the newest bar is fresh"):
1. `test_ohlcv_green_when_cache_dir_none` — `prices_cache_dir=None` → "green"/"n/a". (A red impl FAILS.)
2. `test_ohlcv_green_when_no_parquet` — empty `tmp_path` cache dir → "green"/"n/a".
3. `test_ohlcv_green_when_recently_written` — write `tmp_path/AAPL.parquet` (any bytes; we only stat mtime), set its mtime to `now - 1 day` via `os.utime`; `_OHLCV_FRESH_YELLOW_DAYS=4` → age 1d <= 4 → "green". Arithmetic: age 1d, yellow at >4d → green. (Name says "written", not "fresh bars".)
4. `test_ohlcv_yellow_when_write_stale` — mtime `now - 5 days` → 5 > 4 (yellow) AND 5 <= 7 (not red) → "yellow". A green impl (threshold-too-loose) FAILS; a red impl (threshold-too-tight) FAILS; only the 4<age<=7 → yellow impl passes.
5. `test_ohlcv_red_when_write_very_stale` — mtime `now - 9 days` → 9 > 7 → "red". (Yellow impl FAILS at >7.)
5b. `test_ohlcv_mtime_age_is_host_tz_independent` (Codex R5 MAJOR #1) — set a parquet mtime a few HOURS from the yellow boundary (e.g. `_OHLCV_FRESH_YELLOW_DAYS` days minus 3h old) and assert the color does NOT depend on the host timezone. Construct the assertion so a host-local interpretation (`datetime.fromtimestamp(mtime)` without an explicit tz, or `now.timestamp()`) on a non-Hawaii host would shift the age across the 4d boundary and flip green↔yellow, while the explicit-Hawaii `datetime.fromtimestamp(st_mtime, ZoneInfo("Pacific/Honolulu"))` math stays green. Practically: compute `age_days` both ways in the test (explicit-Hawaii vs a simulated host-local at, say, UTC) and assert the impl matches the explicit-Hawaii result. A host-local impl FAILS (different color under the simulated offset); the pinned impl PASSES. (Boundary-arithmetic discipline: state both `age_days` values in the docstring.)

Weather (seed `weather_runs` via the real `upsert_weather_run` / `insert_weather_run` repo so the production read path is exercised):
6. `test_weather_red_when_absent` — schema-present but EMPTY `weather_runs` → "red", "no weather run".
7. `test_weather_green_when_current` — `asof_date == last_completed_session(frozen_now).isoformat()` → "green".
8. `test_weather_yellow_one_behind` — `asof_date` = `sessions_behind(last_completed_session(frozen_now), asof) == 1` (the prior NYSE session) → "yellow".
9. `test_weather_red_two_behind` — `asof_date` two NYSE sessions behind `last_completed_session(frozen_now)` → "red".
10. `test_weather_yellow_one_behind_across_weekend` (Codex R1 MAJOR #3; anchor verified per Codex R2 MAJOR #2) — `frozen_now` = a Monday POST-close → `last_completed_session(frozen_now)` = Monday (the BACKWARD helper is correct here — Monday's close has passed); seed `asof_date` = the prior Friday so `sessions_behind(Monday, Friday) == 1` across the weekend → "yellow", NOT "red". (NOTE: this anchor is correct because `last_completed_session` is BACKWARD-looking — unlike the pipeline test #9 which uses the FORWARD `action_session_for_run` and therefore needs a weekend `frozen_now`. Verify `sessions_behind` returns 1 in the test setup.) A calendar-day impl false-reds (Friday→Monday = 3 days) → FAIL.
11. `test_weather_missing_table_degrades_yellow_not_crash` (Codex R1 MAJOR #4; scoped per Codex R2 MINOR #1) — conn to a DB with NO `weather_runs` table → the weather check is "yellow" "weather schema unavailable" (NOT red, NOT a crash); only `"no such table"`/`"no such column"` OperationalErrors degrade — any other OperationalError re-raises. Distinguishes the unwrapped-query impl (raises) from the scoped-wrapped impl.

Run → FAIL.

- [ ] **Step 2: Implement** `_check_data_freshness(conn, *, prices_cache_dir, now) -> list[ToolHealthCheck]`. Parquet mtime via `max(p.stat().st_mtime for p in prices_cache_dir.glob("*.parquet"))` — NO pandas. Weather session-gap via the `sessions_behind` helper added to `dates.py` (Task 2) — NO pandas in `tool_health.py`. Weather DB read wrapped in `try/except sqlite3.OperationalError as exc` → yellow "weather schema unavailable" ONLY when `"no such table"`/`"no such column"` in `str(exc)`, else re-raise (Codex R2 MINOR #1). ASCII strings.

**Acceptance:** freshness-section tests pass; `ruff check swing/` clean. Commit: `feat(monitoring): Task 4 -- OHLCV + weather data-freshness checks`.

---

## Task 5: `compute_tool_health` — the aggregator (worst-of + envelope)

**Files:**
- Modify: `swing/monitoring/tool_health.py` (add `compute_tool_health`)
- Create: `tests/monitoring/test_tool_health_aggregate.py`

```python
def _normalize_now_to_naive_local(now: datetime | None) -> datetime:
    """Codex R3 MAJOR #1: the session helpers (action_session_for_run /
    last_completed_session) do now_local.replace(tzinfo=Pacific/Honolulu),
    which RELABELS (not converts) an aware datetime -> mis-anchored sessions.
    Normalize ONCE here: None -> datetime.now() (naive local); aware ->
    convert the instant to Hawaii-local THEN strip tzinfo (naive-local). After
    this, `now` is ALWAYS naive-Hawaii-local -- the contract both the session
    helpers AND _check_schwab_token's _now_to_utc consume correctly."""
    from zoneinfo import ZoneInfo
    if now is None:
        # Codex R4 MAJOR #1: Hawaii-local wall clock, NOT bare datetime.now()
        # (host-local). Identical on the operator's Hawaii box; correct on CI /
        # a non-Hawaii dev box, where bare datetime.now() would be relabeled as
        # Hawaii by the session helpers and mis-anchor by the host-vs-HST offset.
        return datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
    if now.tzinfo is not None:
        return now.astimezone(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
    return now

def compute_tool_health(conn, *, cfg=None, prices_cache_dir=None, now=None) -> ToolHealthStatus:
    now = _normalize_now_to_naive_local(now)   # Codex R3 MAJOR #1 -- single boundary normalization
    checks: list[ToolHealthCheck] = []
    checks += _check_pipeline_run(conn, cfg=cfg, now=now)
    checks += _check_schwab_token(cfg=cfg, now=now)
    checks += _check_data_freshness(conn, prices_cache_dir=prices_cache_dir, now=now)
    overall = worst_of([c.status for c in checks])
    return ToolHealthStatus(overall=overall, checks=checks, generated_ts=now.isoformat(timespec="seconds"))
```

- [ ] **Step 1: Write the failing tests** (`test_tool_health_aggregate.py`).

1. `test_all_green_overall_green` — seed a DB + cache_dir where every check is green (current complete run, fresh weather + parquet, Schwab n/a) → `compute_tool_health(...).overall == "green"`, AND `len(checks) >= 5` (freshness x2 + pipeline x2-3 + schwab x1). Pre-fix: function undefined → FAIL.
2. `test_one_red_makes_overall_red` — seed everything green EXCEPT a wedged running run (red) → `overall == "red"` (the worst-of). A bug that returns the FIRST check's status, or that lexically-`max`es, would NOT return red here (red sorts lexically below green/yellow) → distinguishes.
3. `test_one_yellow_no_red_overall_yellow` — green except one yellow (e.g. 5-day-stale parquet) → `overall == "yellow"`.
4. `test_compute_tool_health_bare_conn_call_shape` (narrowed per Codex R1 MAJOR #4) — `compute_tool_health(conn)` (no cfg/cache_dir — the §3-locked shape) against a **SCHEMA-PRESENT-but-EMPTY** DB (via `ensure_schema`) does NOT raise and returns a `ToolHealthStatus`. Assert the distinction EXPLICITLY: the CFG/CACHE-dependent checks (`schwab_token_ttl`, `ohlcv_freshness`) are green/"n/a"; the operational-DATA checks correctly fire (`pipeline_freshness` == "red" "no completed run", `weather_freshness` == "red" "no weather run") — proving "missing config = n/a green" is DISTINCT from "missing data = red". This is the LOCK-conformance test for the locked signature AND the n/a-vs-data disambiguation.
5. `test_compute_tool_health_pre_schema_conn_degrades_not_crash` (Codex R1 MAJOR #4) — `compute_tool_health(conn)` against a bare `:memory:` conn (NO `ensure_schema` → no tables); assert it returns a `ToolHealthStatus` (does NOT raise `sqlite3.OperationalError`) with the schema-dependent checks degraded to "yellow" "schema unavailable". (An unwrapped impl raises → FAIL; the degrade-not-crash impl returns → PASS.)
6. `test_compute_tool_health_is_read_only` — open the seeded DB `mode=ro`, call `compute_tool_health(ro_conn, cfg=..., prices_cache_dir=...)`; assert it returns normally (NO `sqlite3.OperationalError: attempt to write a readonly database`). This is the read-only LOCK-conformance test — any accidental write surfaces as an OperationalError on the ro connection.
7. `test_generated_ts_uses_injected_now` — pass `now=datetime(2026,6,14,20,31,0)`; assert `status.generated_ts == "2026-06-14T20:31:00"` and `status.to_dict()["generated_ts"] == "2026-06-14T20:31:00"`. (NOTE: this naive `now` is used as-is — the normalizer is identity on a naive `now`.)
8. `test_compute_tool_health_normalizes_aware_now` (Codex R3 MAJOR #1) — pick an AWARE-UTC `now` near NYSE close (e.g. `datetime(2026,6,15,19,0,0, tzinfo=UTC)` = `2026-06-15 09:00 HST`, before close) AND its EQUIVALENT naive-Hawaii-local datetime (`datetime(2026,6,15,9,0,0)`); seed a DB so the session-anchored checks (pipeline_freshness, weather_freshness) are color-sensitive to the anchor. Call `compute_tool_health(conn, cfg=..., prices_cache_dir=..., now=aware)` AND `now=equivalent_naive`; assert the two produce the SAME per-check statuses (the aware instant is CONVERTED to Hawaii-local, not relabeled). A no-normalization impl (aware `now` flows into the session helpers, which `.replace(tzinfo=...)` relabels `19:00` as HST → anchors shift forward) produces DIFFERENT statuses → FAIL; the boundary-normalized impl matches → PASS. (Distinguishes the relabel-vs-convert bug; compute both anchor dates in the test docstring per the regression-arithmetic discipline.)

Run → FAIL.

- [ ] **Step 2: Implement `compute_tool_health`.**

**Acceptance:** aggregate tests pass; the bare-`conn` + `mode=ro` LOCK tests pass; `ruff check swing/` clean. Commit: `feat(monitoring): Task 5 -- compute_tool_health aggregator (worst-of + envelope)`.

---

## Task 6: `scripts/tool_health.py` — the operator probe (ASCII + `--json`)

**Files:**
- Create: `scripts/tool_health.py`
- Create: `tests/scripts/__init__.py` (if absent), `tests/scripts/test_tool_health_script.py`

Mirrors `scripts/weekly_glance.py`: `argparse` with `--db` (default `~/swing-data/swing.db`) + `--json`; opens its OWN `mode=ro` connection (`file:{db}?mode=ro`, `uri=True` — `weekly_glance.py:111`); loads `Config.from_defaults()` for `cfg` + `cfg.paths.prices_cache_dir`; calls `compute_tool_health(conn, cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir)`; then:
- default: ASCII report. Per check: `  [{STATUS}] {key}: {summary}` (+ a `      {detail}` line when detail present). Footer: if `overall != "green"`, `ATTENTION (N): ...` listing the non-green checks (mirroring `weekly_glance.py:176-183`); else `TOOL HEALTH: all clear.` Exit code: 0 when overall green, 1 otherwise (the `harness_probe.py` exit-1-on-attention precedent).
- `--json`: `print(json.dumps(status.to_dict(), indent=2))`; exit 0 (machine surface; non-zero exit reserved for the human ATTENTION signal — pin: `--json` ALWAYS exits 0 so a consumer parses cleanly; document this choice).

ASCII discipline: NO non-ASCII glyphs anywhere (status markers are bracketed words `[RED]`/`[YELLOW]`/`[GREEN]`, NOT colored dots/emoji).

**Editable-install gotcha** (recipe §1): the script imports `swing.monitoring.tool_health`; run it from the worktree as `PYTHONPATH=. python scripts/tool_health.py` for worktree-local verification (the `swing.exe` entry resolves the MAIN tree). Pytest is unaffected.

- [ ] **Step 1: Write the failing tests** (`test_tool_health_script.py`).

1. `test_script_all_clear_exit_zero` — build a seeded DB on disk (`tmp_path/swing.db`) where every check is green; monkeypatch `Config.from_defaults` (or pass `--db` + monkeypatch cache dir) so the script resolves the tmp paths; run `main(["--db", str(db)])` (import the module's `main`); assert return code 0 AND stdout contains "all clear". (Distinguishes: a non-green seed returns 1 + "ATTENTION".)
2. `test_script_attention_exit_one` — seed a wedged run (red); assert `main(...)` returns 1 AND stdout contains "ATTENTION (1)" (or the right count) AND the red check's key.
3. `test_script_json_flag` — `main(["--db", str(db), "--json"])`: capture stdout, `json.loads` it, assert `parsed["monitor"] == "tool_health"`, `parsed["overall"] in {green,yellow,red}`, `parsed["checks"]` is a list; AND assert exit 0 even when overall is red (the machine-surface choice). (A `--json` that still exits 1 on red FAILS this.)
4. `test_script_output_is_ascii` (reframed per Codex R1 MINOR #3 — platform-AGNOSTIC) — the portable invariant is "the subprocess stdout BYTES decode as pure ASCII" (which guarantees ANY cp1252 encoder is safe — the root of the gotcha). Run `subprocess.run([sys.executable, str(script_path), "--db", str(db)], capture_output=True, env={**os.environ, "PYTHONPATH": str(repo_root)})` (`sys.executable`, NOT PowerShell — runs on any OS) and assert `result.stdout.decode("ascii")` does not raise (every byte is ASCII). Seed a RED state so the ATTENTION path (the most string-heavy) is exercised. A non-ASCII glyph in any summary → the bytes won't decode as ASCII → `UnicodeDecodeError` → FAIL. (OPTIONAL, Windows-only, `@pytest.mark.skipif(platform != "win32")`: a second assertion forcing `PYTHONIOENCODING=cp1252` on the subprocess to prove the real-encoder path — but the ASCII-byte invariant above is the binding, portable guard.) `capsys` is INSUFFICIENT here (it bypasses the OS encoder) — the subprocess is mandatory (recipe §2 + the CLAUDE.md Windows cp1252 gotcha).

Run → FAIL (script does not exist).

- [ ] **Step 2: Implement `scripts/tool_health.py`** with a `main(argv=None)` that `argparse`-parses, opens `mode=ro`, aggregates, renders, returns the exit code; `if __name__ == "__main__": sys.exit(main())`.

**Acceptance:** all script tests pass; the subprocess ASCII test passes; running `PYTHONPATH=. python scripts/tool_health.py --json` against the live DB emits a valid envelope (operator gate, §7). `ruff check swing/` clean (the script is under `scripts/`, not `swing/` — the lint gate is `swing/` only, but keep it clean anyway). Commit: `feat(monitoring): Task 6 -- scripts/tool_health.py operator probe (ASCII + --json)`.

---

## Verification (whole-arc, before close)

- [ ] `python -m pytest tests/monitoring tests/scripts/test_tool_health_script.py -q` — all green.
- [ ] `python -m pytest -m "not slow" -q` — full fast suite green on the merged head (the no-false-green discipline: read the actual tail).
- [ ] `ruff check swing/` — clean.
- [ ] **Read-only proof**: `test_compute_tool_health_is_read_only` (Task 5 #5) drives the aggregator on a `mode=ro` connection; passing it IS the read-only proof.
- [ ] **Operator gate (§7)**: `PYTHONPATH=. python scripts/tool_health.py` and `... --json` against the live `~/swing-data/swing.db` — operator witnesses the ASCII report renders (no cp1252 crash) + the JSON envelope shape. (Binding per §7.)
- [ ] **No measurement-chain touch**: confirm the diff touches ONLY `swing/monitoring/`, `scripts/tool_health.py`, the ONE additive pure helper in `swing/evaluation/dates.py` (`sessions_behind` — Codex R2 MAJOR #3; NO existing function changed), `tests/monitoring/`, `tests/scripts/`, `tests/evaluation/test_dates.py` — NO `swing/data`, `swing/trades`, `swing/pipeline`, no migration, no `pyproject.toml`, no `swing.config.toml`. (The `dates.py` addition is a benign session-helper — pure, read-only, no schema/measurement-chain change — flagged in the return report.)

---

## LOCKS — encoded in this plan (brief §5 + operator commission)

1. **Read-only** — `compute_tool_health` takes a caller's connection; the script opens its OWN `mode=ro` URI connection (Task 6); the `test_compute_tool_health_is_read_only` test (Task 5 #5) proves no write ever fires. NEVER writes the DB.
2. **Aggregate, don't instrument** — every datum reads an EXISTING table/artifact (`pipeline_runs` via `latest_completed_pipeline_run`/`find_active_run`/`list_recent_runs`; `weather_runs` via `get_latest`; the on-disk `*.parquet` mtimes; the schwabdev tokens DB via `_read_tokens_metadata`). NO new schema, NO migration, NO new signal source. Verification step confirms the diff scope.
3. **Reuse, don't fork** — pipeline two-read (`chart_scope.py:82` + `pipeline.py:152`), heartbeat-staleness (`staleness.py:25`), Schwab TTL + severity (`cli_schwab.py:46/54/55` + `_read_tokens_metadata`/`_parse_iso_datetime`, mirroring `schwab.py:516-560`), session anchors (`dates.py:40/62`) — all REUSED with cited file:line; none reimplemented. The ONE new helper (`sessions_behind` in `dates.py`, Codex R2 MAJOR #3) is added to the CANONICAL session module (which owns `_NYSE`), not forked into the monitor — reuse-not-fork in the proper home, and it keeps pandas out of `tool_health.py`. Per-check tests derive inputs from the real readers' types (anti-drift).
4. **No NEW dependency** (Codex R1 MAJOR #2 reframe of the brief's "stdlib only") — the monitor's OWN code (`tool_health.py`, `scripts/tool_health.py`) imports only stdlib (`sqlite3`/`json`/`dataclasses`/`pathlib`/`datetime`/`argparse`/`os`); NO pandas in the monitor's own code (parquet freshness via `os.stat` mtime, never `pd.read_parquet`). It REUSES the project's existing helpers (`swing.evaluation.dates` → pandas/exchange_calendars; `swing.cli_schwab` → schwabdev) — already-present deps, lazy-imported inside the check functions — which is reuse-not-fork, NOT a new dependency. The brief's literal "stdlib only" is honored for the monitor's authored code; the transitive reuse of existing project deps is the intended posture. **ASCII-only** every `summary`/`detail`/`print`; the Task 6 platform-agnostic "stdout bytes decode as ASCII" subprocess test guards it (Codex R1 MINOR #3).
5. **The §3 JSON envelope is the locked contract** — `ToolHealthCheck`/`ToolHealthStatus` mirror it 1:1; `__post_init__` frozenset validates `status`/`overall in {green,yellow,red}` (the `Literal`-not-runtime-enforced gotcha); `to_dict()`/`--json` serializes it; `overall = worst_of` (red>yellow>green, NOT lexical); `grey` is NEVER monitor-emitted (Task 1 #1 rejects it); `monitor == "tool_health"`. `compute_tool_health(conn)` is the 18-F consumption point (Task 5 #4 proves the bare-conn call shape).
6. **Three check families only** — pipeline-run health (Task 2), Schwab token TTL (Task 3), data freshness OHLCV+weather (Task 4). Broader operational coverage is Phase 19+.
7. **No measurement-chain touch** — the aggregator only READS; the diff-scope verification step confirms no measurement-write path is imported or changed. The one `swing/evaluation/dates.py` addition (`sessions_behind`) is a PURE read-only helper (no DB, no schema, no write) — it does NOT touch any measurement-write path; flagged in the return report for transparency.

---

## V1 simplifications + brief-grounding refinements (with V2 dependency) — for the return report

- **OHLCV freshness = newest `*.parquet` mtime (archive WRITE-recency, NOT bar freshness)** (Codex R1 MINOR #2). The brief §4.3(a) says "newest archived bar / meta vs the last completed session", but the newest bar lives inside the parquet (pandas-only read, which the no-pandas-in-monitor-code LOCK forbids) and the meta sidecar carries only `last_full_refresh_date` (legitimately up to 13 days stale under the staggered-refresh scheme — `ohlcv_archive.py:355`), so it is a poor bar-level proxy. mtime is the truest stdlib-only "is the archive being WRITTEN" signal, which matches 18-E's collection-HEALTH mandate (not per-bar correctness). KNOWN LIMITATION (per Codex): any process that merely touches/rewrites an old archive bumps mtime → the check can go green without fresh BARS; the Task 4 tests therefore assert WRITE-recency only and never claim bar freshness. **V2 dependency:** a DB-backed newest-bar signal, or a meta-sidecar `last_bar_date` field, would let the check compare the actual newest bar — both are NEW instrumentation (out of 18-E's aggregate-don't-instrument LOCK), so they belong to a future arc.
- **Weather freshness keyed on `asof_date`, not `run_ts`.** The brief §4.3(b) says "run_ts vs last session", but `run_ts` is a wall-clock timestamp, not a session date; the session-comparable field is `asof_date` (the data session — the weather-keyed-by-`data_asof_date` gotcha). The check compares `asof_date` for the staleness color and reports `run_ts` in the detail. This is a grounding-driven refinement of the brief, not a deviation from intent.
- **The cfg dependency** — `compute_tool_health` gains keyword-only OPTIONAL `cfg` + `prices_cache_dir` + `now` because two checks (Schwab, OHLCV) and the wedged-run heartbeat sub-check need filesystem/config inputs the bare `conn` cannot supply. The §3-locked `compute_tool_health(conn)` call shape is preserved (Task 5 #4); a missing CONFIG input degrades to green/"n/a", a missing-TABLE schema degrades to yellow "schema unavailable", and missing operational DATA correctly fires red (the three-way disambiguation, Codex R1 MAJOR #4). This is an architecture finding, not a tripwire crossing (no schema/dependency/pipeline-step change).
- **Session-arithmetic — NYSE-precise, NOT a calendar-day simplification (Codex R1 MAJOR #3 corrected).** The yellow/red "sessions behind" split uses NYSE `previous_session` arithmetic via the shared `_sessions_behind` helper (lazy-imports the project's `_NYSE` calendar, `dates.py:11`), with weekend + holiday boundary tests proving Friday-vs-Monday is 1-behind (not 3-calendar-days→red) and holiday gaps are counted by sessions. The earlier draft's calendar-day fallback was REMOVED — it false-redded across weekends/holidays. No V2 dependency remains here; the implementation is calendar-precise from V1.
