# Phase 18 Arc 18-D — research data-collection-health monitor (SCRIPT-FIRST) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure, read-only, aggregating **research data-collection-health monitor** — `compute_research_health(conn, ...) -> ResearchHealthStatus` in `swing/monitoring/` (sibling of 18-E's `compute_tool_health`) — emitting the CHARC §3 status envelope (`monitor="research_measurement"`, `overall=worst_of(checks)`, fresh `generated_ts`) with the **7 integrity checks** of the commissioning brief §6.2. Ships a thin `scripts/research_health.py` operator probe (mirrors `scripts/tool_health.py`): ASCII `ATTENTION (N)` / `all clear` report for RD spin-up + `--json` + **on every run writes the conformant envelope ATOMICALLY to `exports/research/health/latest.json`**, which lights 18-F's research stoplight (grey until 18-D writes a conformant fresh artifact there). This is the SCRIPT-FIRST half ONLY — the nightly pipeline-step half is a deferred fast-follow (out of scope).

**Architecture:** A new `swing/monitoring/research_health.py` houses the envelope dataclasses (`ResearchHealthCheck`, `ResearchHealthStatus` — both `frozen`, both with `__post_init__` frozenset validation of the status enum `{green,yellow,red}`, REJECTING `grey` which is 18-F render-only) and the aggregator `compute_research_health(conn, *, cfg=None, exports_root=None, manifest_dir=None, now=None) -> ResearchHealthStatus`. Seven pure per-check functions each return a list of `ResearchHealthCheck` and are tested in isolation against synthetic-but-production-shaped inputs derived from the REAL schema/manifest. The aggregator concatenates the checks, computes `overall = worst_of` (red > yellow > green), and returns the status with a fresh non-future `generated_ts`. `scripts/research_health.py` opens its OWN `mode=ro` connection (the `weekly_glance.py`/`tool_health.py` precedent), loads `Config.from_defaults()`, calls the aggregator, renders ASCII (default) or JSON (`--json`), AND atomically writes the envelope to `latest.json`. The 3 research-artifact contract constants (`RESEARCH_HEALTH_ARTIFACT_PATH`, `RESEARCH_MONITOR_ID`, `RESEARCH_ARTIFACT_MAX_AGE_DAYS`) are IMPORTED from `swing/monitoring/stoplights.py` (single-source LOCK C1 — never redeclared). NO nightly pipeline step, NO new schema, NO new signal source, NO new dependency, NO DB write.

**Tech Stack:** Python 3.14. The monitor's OWN code (`research_health.py`, `scripts/research_health.py`) imports only stdlib (`sqlite3`, `json`, `dataclasses`, `pathlib`, `datetime`, `argparse`, `os`, `math`) — **NO pandas in the monitor's own code** (mirror 18-E's no-pandas-in-monitor mandate). It REUSES existing project helpers (`swing.evaluation.dates` → `sessions_behind`/`last_completed_session`/`action_session_for_run`; `swing.data.ohlcv_finiteness.is_finite_ohlc`; the repo readers + the engine manifest JSON) — already-present project deps, **lazy-imported inside the check functions** (matches 18-E + the schwabdev-import-hazard precedent). pytest (`monkeypatch`, `capsys`, `tmp_path`). No schema, no migration, no `swing/data`/`swing/trades`/`swing/pipeline` carve-out (new read-only `swing/monitoring/` module + a `scripts/` probe).

**Scope (brief §2) — SCRIPT-FIRST ONLY.** OUT OF SCOPE and NOT planned here: (1) the **nightly pipeline-step half** (deferred fast-follow; its own CHARC sec-3 pass + the 17-B `step_guard` B-shape); (2) **amending `docs/research-director-watch-standard.md`** (RD's deliberate post-build action); (3) any **DB write** (read-only `mode=ro`; the ONLY writes are `latest.json` + the ASCII report — artifact writes, same posture as the shadow-expectancy artifacts); (4) **forking the engine funnel/attribution** (read the manifest; never recompute — LOCK §4.2).

---

## Background — grounding (verified on disk at worktree base `main` HEAD `4ce55939`)

Every signal already exists; the monitor AGGREGATES. **Every check below was grounded against the LIVE schema/emitter/DB** (the operator's `~/swing-data/swing.db` + the real `exports/research/shadow-expectancy-*/manifest.json` artifacts) — live code wins over any paraphrase. Where a grounding finding diverges from the brief/spec wording, it is flagged here AND in the return report.

### The 18-F contract this plan writes FOR — `swing/monitoring/stoplights.py` (LIVE on main)
`read_validated_research_envelope()` (`stoplights.py:148`) is the SINGLE identity+staleness-validating reader the topbar stoplight + drill-down VM share. It greys (returns None) unless the artifact at `RESEARCH_HEALTH_ARTIFACT_PATH` satisfies ALL of:
1. **identity:** `env.get("monitor") == RESEARCH_MONITOR_ID` (`"research_measurement"`) — `stoplights.py:165`.
2. **valid overall:** `env.get("overall") in {"green","yellow","red"}` — `stoplights.py:171-176`.
3. **fresh `generated_ts`:** present + `datetime.fromisoformat`-parseable + NOT future-dated (`age < timedelta(0)` greys — `stoplights.py:200`) + `age <= RESEARCH_ARTIFACT_MAX_AGE_DAYS` (7d, EXACT-duration compare, not floored `.days` — `stoplights.py:205`).
4. **consistency:** `overall == _worst_check_severity(env["checks"])` — `stoplights.py:216-217`; mismatch or unverifiable greys.
5. **per-check render schema** (`_worst_check_severity`, `stoplights.py:52-85`): `checks` is a non-empty list; EACH check is a dict with a non-empty str `key`, `status in {green,yellow,red}`, a non-empty str `summary`, and `detail` that is `None`-or-`str`. ANY malformed check → the whole artifact greys.

**The build strategy:** the `__post_init__` frozenset validation (gate 5 per-check status + non-empty key/summary, gate 2 overall) + the NON-EMPTY-`checks` reject (gate 5 list-level, Codex R5 MAJOR #1) + the `overall = worst_of(checks)` invariant (gate 4) + an aware-UTC `generated_ts` from the normalized `now` (gate 3, host-tz-independent) + the imported `monitor` field (gate 1) make the emitter **structurally incapable of producing a non-conformant envelope** (brief §6.5(a)). Task 8 proves it with a real round-trip through the LIVE 18-F reader.

**No circular-import risk:** `stoplights.py` imports only stdlib at module top and LAZY-imports `tool_health` (`stoplights.py:124`); it does NOT import `research_health` at module top — so `research_health.py` importing the 3 constants from `stoplights` at module top is safe (verified `stoplights.py:13-19`).

### The precedent to mirror — `swing/monitoring/tool_health.py` + `scripts/tool_health.py` (18-E)
- `ToolHealthCheck` (`tool_health.py:69-94`): `frozen` dataclass `{key, status, summary, detail=None}` + `__post_init__` rejecting any status outside `_STATUS_VALUES = frozenset({"green","yellow","red"})` (and rejecting empty `key`/`summary`) + `to_dict()`. **Mirror this 1:1** for `ResearchHealthCheck`.
- `ToolHealthStatus` (`tool_health.py:101-134`): `frozen` `{overall, checks, generated_ts=default_factory(_now_iso)}` + `__post_init__` validating `overall`, coercing `checks` to a tuple (immutable), AND enforcing `overall == worst_of([c.status for c in checks])` (gate 4 by construction) + `to_dict()` emitting `{monitor, generated_ts, overall, checks:[...]}`. **Mirror this 1:1** for `ResearchHealthStatus`, except `monitor` = the imported `RESEARCH_MONITOR_ID` AND **`ResearchHealthStatus.__post_init__` ALSO REJECTS an EMPTY `checks` list (Codex R5 MAJOR #1)** — the 18-F reader greys any artifact whose `checks` is empty (`_worst_check_severity` returns None for `not checks`, `stoplights.py:65` → gate 5), and `worst_of([]) == "green"` would otherwise let `ResearchHealthStatus(overall="green", checks=[])` serialize a green-LOOKING envelope the reader then GREYS — defeating the "structurally incapable of a non-conformant envelope" claim. (18-E's `ToolHealthStatus` does NOT reject empty because its envelope is consumed in-process, not round-tripped through the 18-F empty-checks gate; 18-D MUST add this — a deliberate divergence.)
- `worst_of(statuses)` (`tool_health.py:49-66`): red > yellow > green; empty → green; validates each status (ValueError, not KeyError, on unknown). **Reuse the same logic** (a local copy in `research_health.py`, or import from `tool_health` — see Task 1).
- `_now_iso()` (`tool_health.py:97-98`): 18-E stamps `datetime.now().isoformat(timespec="seconds")` (NAIVE ISO). **18-D DIVERGES from 18-E here (Codex R1 MAJOR #1 — load-bearing): `generated_ts` is stamped as AWARE-UTC ISO-8601, NOT naive-local.** 18-E's envelope is consumed by `compute_tool_health` directly (same process, same clock); 18-D's envelope must ROUND-TRIP through the LIVE 18-F reader's staleness gate, which compares a naive `generated_ts` against the HOST wall clock (`datetime.now()`, `stoplights.py:719`) and an AWARE one against `datetime.now(parsed.tzinfo)` (`stoplights.py:716-718`). A naive-Hawaii-local stamp read by a non-Hawaii host (CI/UTC box) is mis-interpreted as future-dated/stale → greyed even when conformant. An AWARE-UTC stamp makes the 18-F staleness compare HOST-TZ-INDEPENDENT (verified: both sides aware-UTC → `age` is the true instant delta). So `_research_now_iso()` returns `now.astimezone(UTC).isoformat(timespec="seconds")` (an `...+00:00` suffix the reader's `datetime.fromisoformat` parses to an aware dt). The aggregator passes the normalized `now` converted to aware-UTC.
- `scripts/tool_health.py`: `argparse` `--db` (default `~/swing-data/swing.db`) + `--json`; `mode=ro` URI connection (`tool_health.py:73-74`); `Config.from_defaults()`; `_resolve_now()` clock seam (`tool_health.py:27-30`); `_render_ascii` (`tool_health.py:32-50`); exit 0 when green else 1 (ASCII path), `--json` always exits 0. **Mirror this** + add the atomic `latest.json` write.

### The integrity-superset precedent — `scripts/weekly_glance.py`
The newest-artifact-age idiom (`_DIR_TS_RE` regex on the `shadow-expectancy-YYYYMMDDTHHMMSSZ` dir name → `datetime.strptime(...).replace(tzinfo=UTC)` → `(datetime.now(UTC) - newest).days`, `weekly_glance.py:33,75-83`), `T1_MAX_AGE_DAYS = 4` (`weekly_glance.py:27`), the `total_unattributed` signal (`weekly_glance.py:84-90`), `EXPORTS = REPO_ROOT / "exports" / "research"` (`weekly_glance.py:23`), `mode=ro` connection (`weekly_glance.py:111`). The monitor is its integrity SUPERSET, not a replacement.

---

### Per-check data grounding (each cites the file:line / live-DB shape confirmed)

| # | check key | reads (table.column / manifest key / artifact) | confirmed at |
|---|---|---|---|
| 1 | `temporal_log_finiteness` | `pattern_forward_observations.ohlc_today_json` (JSON `{open,high,low,close,volume,provider}`); scan O/H/L/C for NaN/inf/None/missing | repo `swing/data/repos/pattern_forward_observations.py:13-16`; JSON shape `swing/pipeline/temporal_metadata.py:148,192`; predicate `swing/data/ohlcv_finiteness.py:27`. **LIVE DB: 103 non-finite obs (close=NaN, 2026-06-10 defect) of 1287** — the motivating defect, RED on live. |
| 2 | `excluded_reason_breakdown` | engine `manifest.json` → `funnel.per_hypothesis.<HYP>.excluded.{invalid_ohlc,insufficient_forward_depth,missing_observations}` (summed across hypotheses) as a % of `funnel.detection_level.unique_signals` | emitter `research/harness/shadow_expectancy/run.py:248-255`; funnel shape `funnel.py:98-112`; reason vocab `constants.py:40-43`. **LIVE manifest `20260613T091809Z`: `unique_signals=77`, `excluded={invalid_ohlc:23, insufficient_forward_depth:9, missing_observations:12}` under `per_hypothesis["Broad-watch baseline"]`.** |
| 3 | `coverage_gaps` | `pattern_detection_events` (detection_date, data_asof_date) JOIN `pattern_forward_observations.observation_date`; mature detections' observation-date holes vs the NYSE calendar | schema `0022_phase14_temporal_log.sql:27,45,69,85`; helpers `swing/evaluation/dates.py:40,66`. **LIVE DB: det#1 obs = 06-05,06-08,06-09,06-10,06-11,06-12 (weekend-contiguous, 0 gaps).** |
| 4 | `structural_integrity` | orphan observations (LEFT JOIN no parent detection); look-ahead (`MIN(observation_date) < detection_date`) | schema FK `0022_phase14_temporal_log.sql:66-67` (`ON DELETE RESTRICT`). **LIVE DB: 0 orphans, 0 look-ahead** (both clean → green). |
| 5 | `drumbeat_liveness` | newest `exports/research/shadow-expectancy-*` dir age + `sum(manifest.funnel.unattributed.values())` (`total_unattributed`) | `weekly_glance.py:33,45-90`; manifest `funnel.unattributed` `run.py:253` + `funnel.py:106`. **LIVE: newest age 1d, total_unattributed=0.** |
| 6 | `candidate_completeness` | `candidates` (bucket, pivot) latest `evaluation_run_id`: null pivots in ACTIONABLE buckets (`aplus`/`watch`) + error-bucket count (`evaluation_runs.error_count` or `candidates.bucket='error'`) | schema `0001_phase1_initial.sql:26,28,30`; repo `swing/data/repos/candidates.py:87`. **LIVE DB: null pivots occur ONLY in `error`(46)/`excluded`(209) — 0 in aplus/watch/skip; latest run #90 error_count=0.** |
| 7 | `fetch_transport_health` | `yfinance_calls` (status, ts): error+empty RATE over a recent window; `in_flight`=incomplete/unknown; TRANSPORT indicator ONLY | schema `0030_phase18_yfinance_call_audit.sql:27,36-38`; repo `swing/data/repos/yfinance_calls.py`. **LIVE DB: 4 rows all `success`, newest 2026-06-14** (tiny sample → never alarm on low count). |

---

## File Map

- **Create:** `swing/monitoring/research_health.py` — the envelope dataclasses (`ResearchHealthCheck`, `ResearchHealthStatus`) + `compute_research_health` + the 7 pure per-check helpers. Imports the 3 contract constants from `swing.monitoring.stoplights` at module top; lazy-imports the repo readers / `ohlcv_finiteness` / `dates` helpers INSIDE the check functions. **NO pandas. NO DB write.**
- **Create:** `scripts/research_health.py` — the operator probe (ASCII / `--json`) + the ATOMIC `latest.json` write; mirrors `scripts/tool_health.py`.
- **Create:** `tests/monitoring/test_research_health_envelope.py` — dataclass validation + `worst_of` + `overall==worst_of` invariant + JSON serialization + `monitor` field.
- **Create:** `tests/monitoring/test_research_health_checks.py` — the 7 per-check helpers (discriminating boundary arithmetic, grounded fixtures).
- **Create:** `tests/monitoring/test_research_health_aggregate.py` — `compute_research_health` end-to-end against a seeded `mode=rw`-built / `mode=ro`-read DB + tmp manifest/exports dirs; the read-only LOCK test.
- **Create:** `tests/monitoring/test_research_health_envelope_roundtrip.py` — write `latest.json` via the script → read it back through the LIVE 18-F `read_validated_research_envelope` → assert it validates (green/yellow/red, NOT grey). The all-5-gates-by-construction proof.
- **Create:** `tests/scripts/test_research_health_script.py` — the probe surface (ASCII report, `--json`, exit code, ATOMIC write, subprocess ASCII-bytes encoding guard).
- **Note (test packages):** `tests/monitoring/__init__.py` + `tests/scripts/__init__.py` already exist (18-E shipped them) — confirm before creating; do not duplicate.

**Executing worktree (for the executing-plans cycle that follows this plan): `<repo>/.worktrees/phase18-arc-d-exec`.**

---

## Task 1: The envelope dataclasses (`ResearchHealthCheck` + `ResearchHealthStatus`) + `to_dict` + the imported contract constants

**Files:**
- Create: `swing/monitoring/research_health.py` (dataclasses + serialization + the constant imports only)
- Create: `tests/monitoring/test_research_health_envelope.py`

The §3-locked contract, encoded 1:1, mirroring `tool_health.py:69-134`. Two `@dataclass(frozen=True)` types with `__post_init__` frozenset validation, a module-level `_STATUS_VALUES = frozenset({"green","yellow","red"})`, a `worst_of` helper, and a `to_dict()` that serializes the §3 envelope. The `monitor` field is the IMPORTED `RESEARCH_MONITOR_ID`, NOT a redeclared literal (LOCK C1).

**Module head (the constant import — LOCK C1, brief §3 / §6.1):**
```python
from swing.monitoring.stoplights import (
    RESEARCH_ARTIFACT_MAX_AGE_DAYS,
    RESEARCH_HEALTH_ARTIFACT_PATH,
    RESEARCH_MONITOR_ID,
)
```
**`worst_of` decision (Codex watch-item):** to avoid a second source of truth, IMPORT `worst_of` from `swing.monitoring.tool_health` (it is already the canonical red>yellow>green helper, `tool_health.py:49`). If the implementer prefers self-containment, a local copy is acceptable ONLY if it is byte-identical in behavior AND a test pins the same severity ordering — but importing is preferred (single source). State the choice in the executing return.

**The aware-UTC timestamp helper `_research_now_iso` is DEFINED IN TASK 1 (Codex R2 MAJOR #1 — sequencing).** Task 1 is the FIRST place a `generated_ts` is stamped (the `ResearchHealthStatus` default factory), so the helper must exist here, NOT be introduced late in Task 7. Define in `research_health.py`:
```python
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

def _research_now_iso(now_naive_local: datetime | None = None) -> str:
    """Aware-UTC ISO-8601 stamp (Codex R1 MAJOR #1). `now_naive_local` is the
    aggregator's normalized naive-Hawaii-local clock; None -> the Hawaii wall
    clock. Attach Pacific/Honolulu then convert to UTC (NOT replace(tzinfo=UTC),
    which mis-shifts a Hawaii instant by ~10h) -> a `...+00:00` string the 18-F
    reader parses as aware -> host-tz-independent staleness compare."""
    if now_naive_local is None:
        return datetime.now(UTC).isoformat(timespec="seconds")
    return (now_naive_local.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
            .astimezone(UTC).isoformat(timespec="seconds"))
```
`ResearchHealthStatus.generated_ts` uses `field(default_factory=_research_now_iso)`; Task 7's aggregator passes the explicit `now`.

- [ ] **Step 1: Write the failing tests** (`tests/monitoring/test_research_health_envelope.py`):

1. `test_check_rejects_grey` — `ResearchHealthCheck(key="x", status="grey", summary="s")` raises `ValueError` (grey is 18-F render-only, never monitor-emitted — brief §6.5(a)). PRE-fix (no `__post_init__` validation): constructs an object → `pytest.raises(ValueError)` FAILS. POST-fix: raises → PASSES. (Distinguishes: pre-fix returns an object; post-fix raises.)
2. `test_check_rejects_unknown_status` — `status="purple"` raises `ValueError`. Same distinguisher.
3. `test_check_rejects_empty_key_and_summary` — `key=""` raises; `summary=""` raises (the 18-F `_worst_check_severity` gate-5 requires non-empty `key`/`summary`, so the emitter must reject them at construction). Pre-fix constructs (FAIL); post-fix raises (PASS).
4. `test_status_rejects_unknown_overall` — `ResearchHealthStatus(overall="purple", checks=[ResearchHealthCheck(key="k", status="green", summary="s")])` raises `ValueError`. (NOTE: the `overall==worst_of` invariant below would ALSO reject `purple` since `worst_of(["green"])=="green" != "purple"`; this test pins the enum-validation message specifically — construct with `overall="purple"` and a single green check; assert ValueError.)
5. `test_status_enforces_overall_equals_worst_of` (gate 4 by construction — Codex R7 MAJOR #2: the VALID-but-INCONSISTENT discriminator) — `ResearchHealthStatus(overall="green", checks=[ResearchHealthCheck(key="k", status="red", summary="s")])` raises `ValueError`. **Both `overall="green"` AND the check status `"red"` are VALID enum values** — so an impl that ONLY validates the enum (test #4's path) does NOT raise here → this test FAILS it; only an impl that ALSO enforces `overall == worst_of(checks)` raises → PASSES. Arithmetic: `worst_of(["red"]) == "red" != "green"` → reject. **Assert the raised message specifically references the worst-of MISMATCH** (e.g. `"!= worst_of"` substring), NOT a generic enum-rejection, so the test pins the CONSISTENCY invariant, not enum validation (test #4 covers enum; this covers consistency — the two must not collapse). PRE-fix (enum-only): constructs the inconsistent false-green envelope → FAILS; POST-fix: raises with the mismatch message → PASSES.
5b. `test_status_rejects_empty_checks` (Codex R5 MAJOR #1 — gate 5 empty-list) — `ResearchHealthStatus(overall="green", checks=[])` raises `ValueError` ("checks must be non-empty"). The 18-F reader greys an empty-checks artifact (`stoplights.py:65`); `worst_of([]) == "green"` would otherwise let this construct a green-LOOKING envelope that the reader greys → a non-conformant envelope IS constructible. PRE-fix (no empty-reject): constructs → `pytest.raises(ValueError)` FAILS; POST-fix: raises → PASSES. (Distinguishes: the empty-checks envelope must be unconstructable — closes the residual by-construction gap. NOTE: this check must run regardless of the `overall == worst_of([])` arm, which would PASS for `overall="green"` — so the empty-reject is a SEPARATE guard, placed BEFORE the worst-of compare.)
6. `test_worst_of` — assert exact mapping: `worst_of([])`=="green"; `worst_of(["green","green"])`=="green"; `worst_of(["green","yellow"])`=="yellow"; `worst_of(["yellow","red","green"])`=="red". A naive `max()`-on-strings returns "yellow" for case 4 (lexically "red" < "yellow") → FAILS; the rank-based impl returns "red" → PASSES. (Distinguishes: red>yellow>green is NOT lexical order.)
7. `test_worst_of_rejects_unknown_status` — `worst_of(["grey"])` raises `ValueError` (NOT `KeyError`). Pre-fix bare `_SEVERITY_RANK[s]` raises `KeyError` → `pytest.raises(ValueError)` FAILS; post-fix raises `ValueError` → PASSES. (Distinguishes the exception TYPE.) (If `worst_of` is imported from `tool_health`, this is already guaranteed by `tool_health.py:58-62`; keep the test to pin behavior at the 18-D surface.)
8. `test_to_dict_matches_envelope` — build `ResearchHealthStatus(overall="yellow", checks=[ResearchHealthCheck(key="temporal_log_finiteness", status="yellow", summary="3 non-finite OHLC observations", detail="oldest 2026-06-10")], generated_ts="2026-06-14T20:31:00")`; assert `to_dict()` == `{"monitor":"research_measurement","generated_ts":"2026-06-14T20:31:00","overall":"yellow","checks":[{"key":"temporal_log_finiteness","status":"yellow","summary":"...","detail":"oldest 2026-06-10"}]}`; assert `json.dumps(status.to_dict())` round-trips. Assert `"detail" in d["checks"][0]` even when `detail` is None on a different check (envelope stability — gate 5 allows `detail=None`).
9. `test_monitor_field_is_research_measurement` — `to_dict()["monitor"] == "research_measurement"` AND assert it equals the IMPORTED `RESEARCH_MONITOR_ID` (proves it is sourced from the constant, not a redeclared literal). A redeclared `"research"` or `"research_health"` literal → FAILS.
10. `test_generated_ts_default_is_aware_utc` (Codex R1 MAJOR #1) — omit `generated_ts`; assert the stamped string parses via `datetime.fromisoformat` to an AWARE dt whose `utcoffset()` is `timedelta(0)` (i.e. `parsed.tzinfo is not None` AND `parsed.utcoffset() == timedelta(0)` — the `...+00:00` UTC suffix). A naive-local stamp (no offset) FAILS; the aware-UTC stamp PASSES. (Distinguishes the host-tz-stable timestamp — the fix for the 18-F staleness false-grey on a non-Hawaii host.) Additionally assert the LIVE 18-F reader, fed this exact timestamp in an otherwise-conformant envelope, does NOT grey it as future/stale REGARDLESS of host tz (the round-trip in Task 8 #9 is the full proof).

Run: `python -m pytest tests/monitoring/test_research_health_envelope.py -q` → all FAIL (module/classes do not exist).

- [ ] **Step 2: Implement the dataclasses + constant imports** in `swing/monitoring/research_health.py` (mirror `tool_health.py:69-134`; `_MONITOR_ID` replaced by the imported `RESEARCH_MONITOR_ID` in `to_dict`; `ResearchHealthStatus.__post_init__` enforces `overall == worst_of([c.status for c in checks])` and coerces `checks` to a tuple). Keep all strings ASCII.

**Acceptance:** all `test_research_health_envelope.py` tests pass; `ruff check swing/` clean. Commit: `feat(monitoring): Task 1 -- research-health envelope dataclasses + imported contract constants`.

---

## Task 2: `_check_temporal_log_finiteness` — the data-USABILITY authority (the 18-A defect detector)

**Files:**
- Modify: `swing/monitoring/research_health.py` (add `_check_temporal_log_finiteness`)
- Create: `tests/monitoring/test_research_health_checks.py` (finiteness section)

Emits ONE check, `key="temporal_log_finiteness"`. Scans `pattern_forward_observations.ohlc_today_json` for any non-finite OHLC. **This is the data-USABILITY authority (brief §6.2 #1) — RED on ANY non-finite hit.** It is the check that would have caught the 2026-06-10 NaN-Close defect on the day it entered.

**Grounding (verified on the LIVE DB):** `ohlc_today_json` is `{open,high,low,close,volume,provider}` (`temporal_metadata.py:148`). The 2026-06-10 defect rows carry `"close": NaN` (Python `json.dumps` emits literal `NaN`; `json.loads` parses it back to `float('nan')`) with O/H/L present — **103 such rows of 1287 on the live DB.** Volume is EXEMPT (Arc-8 — legit volume-less bars exist; the predicate is finiteness of OHLC only).

**Reuse the shared predicate — with a None/missing/non-numeric guard (LOAD-BEARING):** `swing/data/ohlcv_finiteness.is_finite_ohlc(*values)` (`ohlcv_finiteness.py:27`) returns False for NaN/inf but **RAISES `TypeError` on `None`** (verified: `is_finite_ohlc(None)` → `TypeError: must be real number, not NoneType`). The brief says "reuse the shared finiteness predicate rather than re-implementing NaN/None detection" — but the predicate handles NaN/inf ONLY. So the scan logic is: for each row, `json.loads` (a JSON error → count as non-finite, do not crash); for each of the 4 OHLC keys, if the value is **missing OR None OR not a number** → non-finite hit; ELSE call `is_finite_ohlc(open,high,low,close)` for the NaN/inf case. A None/missing/non-numeric value is treated as a non-finite hit WITHOUT calling the predicate (avoids the TypeError). State this guard explicitly in the implementation.

**Degradation contract:** missing `pattern_forward_observations` TABLE (`sqlite3.OperationalError` with `"no such table"`/`"no such column"` in `str(exc)`) → yellow "temporal-log schema unavailable" (mirror 18-E `_schema_unavailable`, `tool_health.py:41-46`; re-raise any OTHER OperationalError). EMPTY table (0 rows) → green "no temporal-log observations yet" (no data is not a defect here — the log legitimately starts empty). ANY non-finite hit → red.

- [ ] **Step 1: Write the failing tests** (finiteness section). Seed a `:memory:`/`tmp_path` DB with the real schema (`ensure_schema`) + real repo inserts (`insert_detection_event` + `insert_observation`) so the production read path is exercised (anti-drift). To plant a NaN row, write the `ohlc_today_json` text DIRECTLY (the production write barrier `build_ohlc_today_json` REJECTS NaN — `temporal_metadata.py:186`; the DEFECT rows predate that barrier, so the test must mimic the legacy on-disk shape by inserting the raw JSON string `'{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, "volume": 100.0, "provider": "yfinance"}'`). Confirm `json.loads` of that string yields `float('nan')` for close.

1. `test_finiteness_green_when_all_finite` — seed 3 observations all with finite OHLC → "green", summary mentions "0" / "no non-finite". A red-returning impl FAILS.
2. `test_finiteness_red_on_nan_close` — seed 2 finite + 1 with `close=NaN` (the REAL 2026-06-10 shape: O/H/L present, close NaN) → "red", summary count == 1, detail names the ticker (via JOIN to `pattern_detection_events.ticker`) + the observation_date. Arithmetic: 1 non-finite of 3. A green impl (NaN not detected) FAILS; a count-2 impl FAILS; only the count-1-red impl passes. (THE motivating-defect test.)
3. `test_finiteness_red_on_none_value` — seed 1 obs whose `close` is JSON `null` (`'{"...","close": null, ...}'` → `json.loads` → `None`) → "red" (NOT a crash). A bare `is_finite_ohlc(None)` impl raises `TypeError` → the test (asserting a returned red check) FAILS; the None-guarded impl returns red → PASSES. (Distinguishes the None-guard requirement — the predicate raises on None.)
4. `test_finiteness_red_on_inf` — seed 1 obs with `close=Infinity` (JSON `Infinity` → `float('inf')`) → "red". (A NaN-only check that misses inf FAILS; `is_finite_ohlc` rejects both.)
5. `test_finiteness_red_on_missing_key` — seed 1 obs whose JSON omits `close` entirely → "red" (missing key = non-finite hit). Distinguishes a `.get("close")`-without-guard impl that would pass None to the predicate and crash.
6. `test_finiteness_green_when_empty_table` — schema-present, 0 observations → "green" "no ... observations yet" (NOT red — empty log is not a defect). A red-on-empty impl FAILS.
7. `test_finiteness_yellow_when_missing_table` — conn to a DB with NO `pattern_forward_observations` table → "yellow" "schema unavailable" (NOT a crash, NOT red). An unwrapped-query impl raises → FAIL; the scoped-wrapped impl returns yellow → PASS.
8. `test_finiteness_volume_nan_is_exempt` — seed 1 obs with finite OHLC but `volume=NaN` → "green" (Volume is EXEMPT — Arc-8). An impl that scans volume FAILS (would red); the OHLC-only impl passes. (Distinguishes the volume-exemption boundary.)

Run → FAIL.

- [ ] **Step 2: Implement** `_check_temporal_log_finiteness(conn) -> list[ResearchHealthCheck]`: a single `SELECT o.observation_id, o.observation_date, o.ohlc_today_json, d.ticker FROM pattern_forward_observations o LEFT JOIN pattern_detection_events d ON d.detection_id = o.detection_id` wrapped in `try/except sqlite3.OperationalError`; per-row `json.loads` (JSON error → non-finite hit) → the None/missing/non-numeric guard → `is_finite_ohlc(o,h,l,c)`. Lazy-import `is_finite_ohlc`. Tally count + collect a small sample (≤3) of `(ticker, observation_date)` for the detail. ASCII strings only.

**Acceptance:** finiteness-section tests pass; `ruff check swing/` clean. Commit: `feat(monitoring): Task 2 -- temporal-log finiteness check (the 18-A usability authority)`.

---

## Task 3: `_check_excluded_reason_breakdown` — read the engine manifest (do NOT recompute — LOCK §4.2)

**Files:**
- Modify: `swing/monitoring/research_health.py` (add `_check_excluded_reason_breakdown` + a small `_read_newest_manifest(exports_root) -> dict | None` helper shared with Task 6)
- Modify: `tests/monitoring/test_research_health_checks.py` (excluded-breakdown section)

Emits ONE check, `key="excluded_reason_breakdown"`. Reads the NEWEST engine `manifest.json` and reports `invalid_ohlc`/`insufficient_forward_depth`/`missing_observations` each as a count + a % of `unique_signals`. **READ the manifest; do NOT recompute attribution (LOCK §4.2 — the synthetic-vs-production drift the program has been burned by — memory `feedback_adversarial_review_verify_data_shapes`).**

**Grounding (CRITICAL — the brief's paraphrase is imprecise; live shape wins):** the brief §6.2 #2 names `invalid_ohlc`/`insufficient_forward_depth`/`missing_observations` and ties them to `unique_signals`. The LIVE manifest (`run.py:248-255` + `funnel.py:98-112`, verified on `exports/research/shadow-expectancy-20260613T091809Z/manifest.json`) places these under **`funnel.per_hypothesis.<HYP>.excluded.<reason>`** (NOT a top-level `excluded_reason_breakdown` key, NOT in `unattributed`), and `unique_signals` under **`funnel.detection_level.unique_signals`**. There can be **multiple hypotheses** (one on disk now: "Broad-watch baseline") OR **zero** (older runs: `per_hypothesis == {}`). Per `constants.py:40-43` these 3 reasons are `ATTRIBUTED_EXCLUDED_REASONS` (per-hypothesis), distinct from the `UNATTRIBUTED_REASONS`. **So the check SUMS each reason across ALL hypotheses' `excluded` sub-dicts** and divides by `funnel.detection_level.unique_signals`. This is a brief-grounding refinement (flagged in the return report): the path is `per_hypothesis.*.excluded`, NOT a top-level breakdown.

**Manifest discovery (Codex R1 MAJOR #3 — distinguish ABSENT from CORRUPT):** the newest `exports/research/shadow-expectancy-*/manifest.json` by dir-name (the `weekly_glance.py` reverse-sort precedent, `weekly_glance.py:49-51`). `_read_newest_manifest(exports_root)` returns a **3-state result, NOT a bare dict-or-None**, so a malformed NEWEST manifest is NOT silently normalized to "n/a":
- **`("absent", None)`** — NO `shadow-expectancy-*` dir exists at all. (The engine has never produced an artifact → green/n-a is honest.) **This is the ONLY absent case (Codex R3 MAJOR #1).**
- **`("corrupt", None)`** — the newest dir EXISTS but: has NO `manifest.json` (a partially-written / crashed-mid-write latest run — Codex R3 MAJOR #1, NOT "absent"), OR its `manifest.json` is unparseable / not a dict / **shape-drifted** (a parsed dict missing the expected nested funnel schema). (A real degraded state → at least YELLOW; do NOT mask as n/a — a newest dir without a manifest is a broken latest run, NOT "engine never ran".)
- **`("ok", <dict>)`** — parsed successfully AND the nested funnel schema is present.
Implement as e.g. a small named-tuple / `(state, payload)` pair (do NOT crash on the read; `try/except (OSError, json.JSONDecodeError)` → `"corrupt"`). **Nested-schema validation (Codex R2 MAJOR #3 — shape-drift defense):** a parsed dict is `"ok"` ONLY when `funnel` is a dict AND `funnel["detection_level"]["unique_signals"]` exists and is an `int`/`float` (numeric) AND `funnel["per_hypothesis"]` is a dict. If `funnel`/`detection_level`/`unique_signals`/`per_hypothesis` is missing or the wrong type → `"corrupt"` (NOT `"ok"`-then-`.get(...)`-zeros, which would mask a broken latest run as healthy). This is the exact shape-drift the data-shape-vs-live-source discipline (memory `feedback_adversarial_review_verify_data_shapes`) mandates catching. `exports_root` defaults to `RESEARCH_HEALTH_ARTIFACT_PATH.parent.parent` (i.e. `exports/research/`) so the check finds the real artifacts; injectable for tests. **Rationale:** the NEWEST artifact being corrupt/shape-drifted is itself a research-health signal (a half-written or schema-broken latest run), exactly what the monitor exists to surface — collapsing it to green/n-a would hide a defect.

**Thresholds (module constants, calibrated against the live baseline — invalid_ohlc ~23/77 ≈ 30% currently, the KNOWN NaN-defect backlog):**
```python
# Excluded-reason rate (% of unique_signals) escalation. invalid_ohlc has run
# ~30% on the live manifest (the 06-10 NaN backlog the engine's belt rejects);
# these are CONSERVATIVE V1 floors -- the RD tunes them post-build.
_EXCL_YELLOW_PCT = 10.0   # any one reason >10% of unique_signals -> yellow
_EXCL_RED_PCT = 25.0      # any one reason >25% -> red
```
**Transport-vs-usability note:** `invalid_ohlc` here is the engine's OWN belt-side rejection (the SAME class check #1 catches at the usability authority). Check #1 stays the authority (RED on any non-finite); this check is the *rate/trend* lens on the engine's funnel — they are complementary, not redundant.

**Degradation contract:** manifest ABSENT (`"absent"`) → green "no engine manifest yet (n/a)" (a missing artifact is not a defect — the engine may not have run; mirror 18-E's missing-config→green). Newest manifest CORRUPT (`"corrupt"`, Codex R1 MAJOR #3) → **yellow** "newest engine manifest unreadable" (a malformed/partial latest run is a real degraded state, NOT n/a). `unique_signals == 0` or missing → green "n/a (zero signals)" (avoid div-by-zero; an empty funnel is not a defect). `per_hypothesis == {}` → green "no attributed hypotheses yet (n/a)". A present (`"ok"`) manifest with a reason over threshold → yellow/red.

- [ ] **Step 1: Write the failing tests** (excluded-breakdown section). Build manifest dicts in `tmp_path/shadow-expectancy-YYYYMMDDTHHMMSSZ/manifest.json` derived from the REAL shape (copy the structure from `exports/research/shadow-expectancy-20260613T091809Z/manifest.json` — `funnel.detection_level.unique_signals` + `funnel.per_hypothesis.<H>.excluded.<reason>`), NOT a hand-flattened dict.

1. `test_excluded_green_when_no_manifest` — empty `tmp_path` exports root (NO `shadow-expectancy-*` dir) → "green" "n/a" (the `"absent"` state). A red/yellow impl FAILS.
2. `test_excluded_green_when_under_threshold` — manifest with `unique_signals=100`, `per_hypothesis={"H": {"excluded": {"invalid_ohlc": 5}}}` → 5% < 10% → "green". Arithmetic: 5/100=5%. A yellow-at-5% impl FAILS.
3. `test_excluded_yellow_at_threshold` — `unique_signals=100`, `invalid_ohlc=15` → 15% (>10, <=25) → "yellow". Both-ways: a >25 red impl returns green here (wrong); a <=10 green impl returns green (wrong); only the 10<pct<=25→yellow impl passes.
4. `test_excluded_red_over_threshold` — `unique_signals=100`, `invalid_ohlc=30` → 30% > 25 → "red". A yellow impl FAILS at >25.
5. `test_excluded_sums_across_hypotheses` (the grounding-critical test) — `unique_signals=100`, `per_hypothesis={"H1":{"excluded":{"missing_observations":8}}, "H2":{"excluded":{"missing_observations":8}}}` → summed 16/100=16% → "yellow". An impl that reads only ONE hypothesis (or a top-level key) sees 8% → green → FAILS; the sum-across-hypotheses impl returns yellow → PASSES. (Distinguishes the per_hypothesis-sum requirement — the live shape.)
6. `test_excluded_green_when_zero_signals` — `unique_signals=0` → "green" "n/a (zero signals)" (no div-by-zero). A ZeroDivisionError impl crashes → FAIL.
7. `test_excluded_green_when_no_hypotheses` — `per_hypothesis={}` (the older-run shape), `unique_signals=42`, `unattributed={"matched_no_hypothesis":42}` → "green" "no attributed hypotheses yet (n/a)" (the 3 reasons live under per_hypothesis, which is empty → 0 excluded). A KeyError-on-empty impl FAILS; the defended impl passes. (Distinguishes the empty-per_hypothesis defense — the real older-manifest shape.)
8. `test_excluded_yellow_when_newest_manifest_corrupt` (Codex R1 MAJOR #3) — create a NEWEST `shadow-expectancy-*` dir whose `manifest.json` is malformed JSON (or a JSON list, not a dict) → `_read_newest_manifest` returns `("corrupt", None)` → "yellow" "newest engine manifest unreadable" (NOT green/n-a, NOT a crash). A return-None-then-green impl FAILS (masks corruption as healthy); the 3-state impl returns yellow → PASSES. (Distinguishes corrupt-newest from absent — the M3 fix.)
8b. `test_excluded_green_when_no_dir_at_all` — no `shadow-expectancy-*` dir → `("absent", None)` → "green" "n/a" (absent stays n-a; only CORRUPT escalates). Pairs with #8 to pin the absent-vs-corrupt distinction.
8c. `test_excluded_yellow_when_newest_manifest_shape_drifted` (Codex R2 MAJOR #3) — write a NEWEST `manifest.json` that is VALID JSON + a dict but MISSING the funnel schema (e.g. `{"harness_version": "0.1.0"}` with no `funnel` key, OR `{"funnel": {}}` with no `detection_level`/`per_hypothesis`) → `_read_newest_manifest` returns `("corrupt", None)` → "yellow" "newest engine manifest unreadable". An `"ok"`-then-`.get(...)`-defaults-to-zero impl returns green (masks the broken run) → FAILS; the nested-schema-validating impl returns yellow → PASSES. (Distinguishes shape-drift from a legitimately-shaped manifest — the data-shape-vs-live-source discipline.)
8d. `test_excluded_yellow_when_newest_dir_missing_manifest` (Codex R3 MAJOR #1) — create a NEWEST `shadow-expectancy-*` dir with NO `manifest.json` inside it (a crashed-mid-write run) → `_read_newest_manifest` returns `("corrupt", None)` → "yellow" (NOT green/n-a). An impl that treats a dir-without-manifest as `"absent"`→green FAILS (masks a broken latest run as "engine never ran"); the dir-present-but-no-manifest→corrupt impl returns yellow → PASSES. (Distinguishes the no-dir-at-all `absent` from the dir-without-manifest `corrupt` — the residual false-green Codex caught.)

Run → FAIL.

- [ ] **Step 2: Implement** `_read_newest_manifest(exports_root) -> tuple[str, dict | None]` (reverse-sort `shadow-expectancy-*` dirs; **if NONE → `("absent", None)` — the ONLY absent case, Codex R3 MAJOR #1; if the newest dir has NO `manifest.json` → `("corrupt", None)` (a crashed-mid-write latest run, NOT absent)**; read newest `manifest.json` with `try/except (OSError, json.JSONDecodeError)` → `("corrupt", None)`; a parsed non-dict → `("corrupt", None)`; **a parsed dict failing the nested-schema check (funnel dict / detection_level.unique_signals numeric / per_hypothesis dict) → `("corrupt", None)` — Codex R2 MAJOR #3**; else `("ok", dict)`) + `_check_excluded_reason_breakdown(*, exports_root) -> list[ResearchHealthCheck]` (branch on the 3-state result: absent→green/n-a, corrupt→yellow, ok→sum the 3 reasons across `funnel.per_hypothesis.*.excluded` / `funnel.detection_level.unique_signals`). Because the `"ok"` state now GUARANTEES the nested schema, the downstream sum can rely on those keys (still use `.get(reason, 0)` for the per-reason excluded counts, which legitimately vary). ASCII strings; the detail lists each reason's count + %.

**Acceptance:** excluded-breakdown tests pass; `ruff check swing/` clean. Commit: `feat(monitoring): Task 3 -- excluded-reason breakdown from the engine manifest (read, never recompute)`.

---

## Task 4: `_check_coverage_gaps` + `_check_structural_integrity` — observation-date holes + orphans/look-ahead

**Files:**
- Modify: `swing/monitoring/research_health.py` (add `_check_coverage_gaps`, `_check_structural_integrity`)
- Modify: `tests/monitoring/test_research_health_checks.py` (coverage + structural sections)

Two checks. Both reuse the NYSE calendar via `swing.evaluation.dates` (lazy-imported; NO pandas in the monitor module).

### `_check_coverage_gaps` (key=`coverage_gaps`, brief §6.2 #3)
A MATURE detection whose forward-observation date sequence has HOLES vs the trading calendar — INCLUDING a MISSING TAIL (the observe-step stopped early), not just interior gaps (Codex R4 MAJOR #2). **Grounding:** det#1 on the live DB has obs `06-05,06-08,06-09,06-10,06-11,06-12` — contiguous NYSE sessions (06-06/07 weekend correctly skipped → 0 gaps). **The weekend is NOT a gap** — the gap count must be calendar-aware (`_NYSE` session set, compare to the observed set).

**The expected window upper bound is the MATURITY boundary, NOT just `MAX(observation_date)` (Codex R4 MAJOR #2 — the missing-tail defect):** an interior-only check (`sessions_in_range(min_obs, max_obs) - observed`) scores green even when forward observation STOPPED EARLY (the worst observe-step failure: the series silently truncates). The upper bound must reflect "the latest session this detection SHOULD have an observation for." Scope (grounded against the live obs-status model):
- A detection's latest-observation STATUS determines whether it is still in the forward walk. **OPEN** = the most-recent observation status is `pending`/`triggered_open` (the `_OPEN_STATUSES`, `pattern_detection_events.py:110`); **TERMINAL** = `invalidated`/`expired`/`triggered_closed_*` (the walk legitimately stopped — NO missing-tail expected). **LIVE DB: 322 open (`pending`/`triggered_open`), 3 `invalidated`.**
- For an **OPEN** mature detection: expected sessions = `_NYSE.sessions_in_range(min_obs, last_completed_session(now))` (the upper bound is the last completed session — the detection SHOULD have an observation for every session up to now). Missing = expected − observed. This catches BOTH interior holes AND a missing tail (newest obs older than `last_completed_session`).
- For a **TERMINAL** detection: expected sessions = `_NYSE.sessions_in_range(min_obs, max_obs)` (the upper bound is its OWN last observation — it legitimately stopped at terminal status; no tail expected). Interior holes still count.
- Mature = `data_asof_date < last_completed_session(now).isoformat()` (it has had at least one tradable session since its cutoff). A detection with <2 observations and no expected-window gap is skipped (an immature/just-detected row is not a defect).

**Grounding the missing-tail discriminator (verified live):** ALL 322 open detections have their newest obs == `last_completed_session` (`2026-06-12` for a 2026-06-14 `now`) → 0 missing-tails → green on the healthy live DB. An open detection whose newest obs is BEFORE `last_completed_session` (observe-step stalled) → counted as a tail gap → escalates. (Confirmed: the live observe-step is current; the check greens correctly AND would fire if it stalled.)

Compute, per mature detection: expected NYSE sessions in the scoped window minus the observed dates = the missing sessions. Sum the missing across detections. Degradation: yellow if total missing > `_COVERAGE_YELLOW_GAPS`; red if > `_COVERAGE_RED_GAPS`; else green. Missing table → yellow schema-unavailable; empty/zero mature detections → green.

```python
_COVERAGE_YELLOW_GAPS = 1   # any hole -> yellow (a missing forward bar is a real signal)
_COVERAGE_RED_GAPS = 10      # a large hole count -> red (systemic observe-step failure)
```

### `_check_structural_integrity` (key=`structural_integrity`, brief §6.2 #4)
Two SQL probes, RED on ANY hit (a structural-integrity violation is never tolerable):
- **orphan observations:** `SELECT COUNT(*) FROM pattern_forward_observations o LEFT JOIN pattern_detection_events d ON d.detection_id=o.detection_id WHERE d.detection_id IS NULL`. (FK is `ON DELETE RESTRICT` so true orphans cannot arise via deletion — `0022:66-67` — but the defensive probe catches any future write-path bug.) **LIVE DB: 0.**
- **look-ahead violations:** detections whose FIRST observation precedes the detection's `detection_date`: `SELECT COUNT(*) FROM (SELECT o.detection_id, MIN(o.observation_date) first_obs, d.detection_date FROM pattern_forward_observations o JOIN pattern_detection_events d ON d.detection_id=o.detection_id GROUP BY o.detection_id) WHERE first_obs < detection_date`. **LIVE DB: 0** (confirmed the directionality — the spec §2.4 "first obs precedes detection_date").

Any orphan OR look-ahead count > 0 → red; both 0 → green. Missing table → yellow schema-unavailable.

- [ ] **Step 1: Write the failing tests** (coverage + structural sections). Seed via the real repos.

Coverage:
1. `test_coverage_green_when_contiguous` — seed a mature detection with obs on consecutive NYSE sessions spanning a weekend (e.g. Fri, Mon — NO weekend obs) → 0 gaps → "green". A calendar-day impl that counts Sat/Sun as gaps → FAILS (would yellow/red); the NYSE-aware impl passes. (Distinguishes the weekend-is-not-a-gap requirement.)
2. `test_coverage_yellow_on_one_hole` — seed a mature detection with obs on session N and N+2 (skipping the NYSE session N+1) → 1 missing → "yellow". Arithmetic: 1 hole, yellow at >=1. A green impl FAILS.
3. `test_coverage_red_on_many_holes` — seed missing > `_COVERAGE_RED_GAPS` sessions → "red".
4. `test_coverage_green_when_no_mature_detections` — only an immature detection (`data_asof_date == last_completed_session`) → "green" "n/a". A red impl FAILS.
4b. `test_coverage_yellow_on_missing_tail_for_open_detection` (Codex R4 MAJOR #2 — the worst class) — seed an OPEN mature detection (latest obs status `triggered_open`) whose observations are CONTIGUOUS but STOP 2 NYSE sessions BEFORE `last_completed_session(frozen_now)` (the observe-step stalled). Assert "yellow"/"red" (>=1 tail gap). An interior-only `sessions_in_range(min_obs, max_obs)` impl sees 0 holes → green → FAILS; the maturity-boundary impl counts the 2 missing tail sessions → escalates → PASSES. (THE missing-tail discriminator — distinguishes the interior-only bug.)
4c. `test_coverage_green_on_terminal_detection_stopped_early` (the TERMINAL boundary) — seed a detection whose latest obs status is `invalidated` (terminal) and whose newest obs is well before `last_completed_session` → "green" (a terminal detection legitimately stopped; NO tail expected). An impl that applies the maturity-boundary upper bound to TERMINAL detections too FAILS (false-reds a legitimately-closed detection); the status-scoped impl returns green → PASSES. (Distinguishes open-vs-terminal tail scoping — prevents the false-positive on closed detections.)
5. `test_coverage_yellow_when_missing_table` — no `pattern_forward_observations` table → "yellow" schema-unavailable (not crash).

Structural:
6. `test_structural_green_when_clean` — seed detections + observations all well-formed (first_obs >= detection_date, every obs has a parent) → "green". (The live-DB-clean baseline.)
7. `test_structural_red_on_look_ahead` — seed a detection `detection_date=2026-06-10` with an observation `observation_date=2026-06-09` (first_obs < detection_date) → "red", summary names the look-ahead count. A green impl (wrong inequality) FAILS; assert the EXACT inequality direction (`<`, not `<=`) so an obs ON detection_date stays green (the boundary).
8. `test_structural_green_on_obs_equal_detection_date` (the boundary) — first_obs == detection_date → "green" (NOT a violation; `<` is strict). A `<=` impl FAILS here. (Distinguishes strict-vs-inclusive.)
9. `test_structural_red_on_orphan` — insert an observation row whose `detection_id` has no parent. NOTE: the FK `ON DELETE RESTRICT` + NOT NULL blocks a normal orphan insert; to exercise the probe, seed with `PRAGMA foreign_keys=OFF` on the test connection (the migration runner runs FK-off — `db.py`), insert the orphan, then run the check → "red". A no-orphan-probe impl returns green → FAIL. (If FK-off seeding is too awkward, the implementer may instead assert the probe SQL returns the orphan count via a direct unit test of the query — document the choice.)
10. `test_structural_yellow_when_missing_table` — no observation table → "yellow" schema-unavailable.

Run → FAIL.

- [ ] **Step 2: Implement** both checks. `_check_coverage_gaps` lazy-imports `last_completed_session` AND the `_NYSE` calendar from `swing.evaluation.dates` (it owns `_NYSE = xcals.get_calendar("XNYS")`, `dates.py:11`) and computes the calendar-aware hole count INLINE — **SELF-CONTAINED in `swing/monitoring/research_health.py` (Codex R1 MAJOR #2): do NOT add a helper to `swing/evaluation/dates.py`.** Per mature detection, read its observations + its LATEST-observation status (reuse `_OPEN_STATUSES = ("pending","triggered_open")` from `pattern_detection_events.py:110`, or inline the same tuple): for an OPEN latest status the expected window is `_NYSE.sessions_in_range(min_obs, last_completed_session(now))` (catches the missing tail, Codex R4 MAJOR #2); for a TERMINAL latest status it is `_NYSE.sessions_in_range(min_obs, max_obs)` (no tail expected). Missing = expected − observed. Keeping the gap logic in the monitor module preserves the SCRIPT-FIRST scope fence; lazy-importing the EXISTING `_NYSE`/`last_completed_session` is reuse-not-fork. `_check_structural_integrity` runs the two COUNT probes. Both wrap DB reads in the scoped `OperationalError` degradation. ASCII strings.

**Acceptance:** coverage + structural tests pass; `ruff check swing/` clean. Commits: `feat(monitoring): Task 4a -- coverage-gaps check (NYSE-aware observation holes)` + `feat(monitoring): Task 4b -- structural-integrity check (orphans + look-ahead)`.

---

## Task 5: `_check_drumbeat_liveness` + `_check_candidate_completeness`

**Files:**
- Modify: `swing/monitoring/research_health.py` (add `_check_drumbeat_liveness`, `_check_candidate_completeness`)
- Modify: `tests/monitoring/test_research_health_checks.py` (drumbeat + candidate sections)

### `_check_drumbeat_liveness` (key=`drumbeat_liveness`, brief §6.2 #5)
Two signals from the engine artifacts: (a) **newest-artifact age** (the `weekly_glance.py` T1 idiom — `_DIR_TS_RE` on the `shadow-expectancy-YYYYMMDDTHHMMSSZ` dir name → UTC datetime → age in days vs `now`); (b) **`total_unattributed > 0`** in the NEWEST manifest (`sum(manifest.funnel.unattributed.values())`). **Grounding:** newest dir age 1d, total_unattributed=0 on disk (green). Older runs had 42 unattributed (would flag). Reuse `_read_newest_manifest` from Task 3.

- newest artifact age > `_DRUMBEAT_RED_AGE_DAYS` → red "drumbeat may be dead"; > `_DRUMBEAT_YELLOW_AGE_DAYS` → yellow; else green. No artifacts at all → red "drumbeat never ran" (the `weekly_glance.py:52-54` posture).
- `total_unattributed > 0` in the newest manifest → at LEAST yellow (the funnel-honesty signal; `weekly_glance.py:84-90` T2). The check returns the WORSE of the age-color and the unattributed-color.
- **Newest manifest CORRUPT (Codex R1 MAJOR #3):** consume `_read_newest_manifest`'s 3-state result. The AGE is read from the dir-name regex (still available even if the manifest is corrupt — a fresh-but-corrupt dir is NOT stale). The `total_unattributed` signal, when the newest manifest is `"corrupt"`, escalates to at-LEAST yellow "newest manifest unreadable (unattributed unknown)" (do NOT treat a corrupt newest as `total_unattributed==0`/green — that masks a broken latest run). When `"absent"` the unattributed signal is green (no manifest to read; the AGE signal alone drives — and with no dir at all, age → red "never ran"). The check returns the WORST of age-color and manifest-state-color.

```python
_DRUMBEAT_YELLOW_AGE_DAYS = 4   # mirrors weekly_glance.T1_MAX_AGE_DAYS (weekend-tolerant)
_DRUMBEAT_RED_AGE_DAYS = 8      # >1 week with no run -> red
```
**Clock contract:** the age compare uses an injected `now` (the aggregator's normalized clock) converted to UTC for the dir-timestamp compare. The dir timestamps are UTC (`...Z`); the `weekly_glance.py` idiom uses `datetime.now(UTC)`. Since the aggregator's `now` is naive-Hawaii-local (see Task 7), convert it: attach `Pacific/Honolulu` then `.astimezone(UTC)` (the 18-E `_now_to_utc` pattern, `tool_health.py:347-350`) before subtracting the UTC dir timestamp. **Frozen-clock (R2 rider):** every test injects `now`; NO live `datetime.now()`.

### `_check_candidate_completeness` (key=`candidate_completeness`, brief §6.2 #6)
Two signals from `candidates` at the latest `evaluation_run_id`: (a) **null pivots in ACTIONABLE buckets** (`aplus`/`watch`) — gotcha #25 sentinel-bucket discipline; (b) **error-bucket count** in the latest run.

**Grounding (CRITICAL — sentinel-bucket filtering, gotcha #25):** on the LIVE DB, null pivots occur ONLY in `error`(46)/`excluded`(209) buckets — a null pivot there is EXPECTED/legitimate (a skipped/errored candidate has no pivot). `aplus`/`watch`/`skip` ALL have non-null pivots. So a null-pivot check that does NOT filter to actionable buckets ALWAYS fires (false-positive). **The check scopes null pivots to `bucket IN ('aplus','watch')`** — a null there is the real defect.

**ONE canonical latest-run source + ONE join path (Codex R4 MAJOR #1 — no ambiguity):** the latest run is `SELECT MAX(id) FROM evaluation_runs` (`evaluation_runs.id` is the live PK that `candidates.evaluation_run_id` FKs to — `0001:26`). BOTH sub-signals read the ACTUAL `candidates` rows for that run (NOT the `evaluation_runs.error_count` pre-aggregate, which is removed as an alternative — read the rows being checked, not a denormalized mirror that could drift):
- **null pivot:** `SELECT COUNT(*) FROM candidates WHERE evaluation_run_id = :latest AND bucket IN ('aplus','watch') AND pivot IS NULL` > 0 → red ("N actionable candidates with null pivot"). 0 → green.
- **error bucket:** `SELECT COUNT(*) FROM candidates WHERE evaluation_run_id = :latest AND bucket = 'error'` > `_ERROR_BUCKET_YELLOW` → yellow; > `_ERROR_BUCKET_RED` → red.
The check returns the WORSE of the two sub-signals.

```python
_ERROR_BUCKET_YELLOW = 5    # a few error-bucket candidates -> yellow
_ERROR_BUCKET_RED = 25      # an error-bucket SPIKE -> red (systemic eval failure)
```
Latest run via `SELECT MAX(id) FROM evaluation_runs` (the ONE source). Missing `candidates`/`evaluation_runs` table → yellow schema-unavailable. No `evaluation_runs` row (MAX(id) is NULL) → green "n/a (no eval run yet)". **LIVE DB: latest run id=90 → 0 aplus/watch null pivots, 0 error-bucket → green.**

- [ ] **Step 1: Write the failing tests** (drumbeat + candidate sections).

Drumbeat (build `tmp_path` artifact dirs with controlled names + manifests; inject `now`):
1. `test_drumbeat_green_when_fresh_and_attributed` — newest dir 1 day before `now`, `total_unattributed=0` → "green". A red impl FAILS.
2. `test_drumbeat_yellow_when_stale` — newest dir 5 days before `now` (>4, <=8) → "yellow". A green impl FAILS; a red impl FAILS (5<=8).
3. `test_drumbeat_red_when_very_stale` — newest dir 9 days before `now` (>8) → "red".
4. `test_drumbeat_red_when_no_artifacts` — empty exports root → "red" "never ran". A green impl FAILS.
5. `test_drumbeat_yellow_when_unattributed_nonzero` — newest dir FRESH (1 day) but `total_unattributed=42` (older-run shape) → "yellow" (the funnel-honesty signal escalates a fresh-but-dishonest run). A green-because-fresh impl FAILS (ignores unattributed); the worse-of impl returns yellow → PASS. (Distinguishes the two-signal worst-of.)
6. `test_drumbeat_age_uses_injected_now` (frozen-clock R2) — assert two different injected `now` values produce different ages/colors deterministically (no live `datetime.now()`).
6b. `test_drumbeat_yellow_when_newest_manifest_corrupt` (Codex R1 MAJOR #3) — newest dir FRESH (1 day, so age→green) but its `manifest.json` is malformed → at-LEAST "yellow" "newest manifest unreadable". A treat-corrupt-as-unattributed-0 impl returns green → FAILS; the corrupt-escalates impl returns yellow → PASSES. (Distinguishes: a corrupt newest run is surfaced, not masked.) Note: the AGE is still read from the (valid) dir-name regex, so the dir-freshness signal stays green; only the manifest-content signal escalates.

Candidate:
7. `test_candidate_green_when_complete` — latest run: aplus/watch all non-null pivot, 0 error bucket → "green". (The live-baseline.)
8. `test_candidate_red_on_null_actionable_pivot` — seed a latest-run `watch` candidate with `pivot=NULL` → "red". A no-filter impl that also reds on the sentinel buckets is not distinguished here — so ALSO seed an `excluded` candidate with NULL pivot in the SAME run and assert it does NOT contribute (the check stays driven by the watch null). (Distinguishes the sentinel-bucket filter — gotcha #25.)
9. `test_candidate_green_when_null_pivot_only_in_sentinel_buckets` (THE gotcha-#25 test) — latest run: aplus/watch all non-null, but `error`/`excluded` candidates have NULL pivots (the LIVE-DB shape) → "green" (NOT red). An unfiltered-null-pivot impl returns red → FAILS; the actionable-scoped impl returns green → PASSES. (THE false-positive killer.)
10. `test_candidate_yellow_on_error_bucket` — latest run with 10 `error`-bucket candidates (>5, <=25) → "yellow". A green impl FAILS; a red impl FAILS.
11. `test_candidate_red_on_error_spike` — 30 error-bucket candidates (>25) → "red".
12. `test_candidate_yellow_when_missing_table` — no candidates table → "yellow" schema-unavailable.

**Shared 3-state manifest matrix (Codex R4 MAJOR #3) — assert BOTH manifest-consuming checks classify all 3 states consistently.** Add a parametrized test (in `test_research_health_checks.py`) over the 3 states × the 2 manifest-consuming checks:
13. `test_manifest_three_state_matrix_excluded_and_drumbeat` — for each of `{no_dir, dir_without_manifest, dir_with_malformed_manifest}`, build the exports root and assert BOTH `_check_excluded_reason_breakdown` AND `_check_drumbeat_liveness` classify it per the contract: `no_dir` → excluded green/n-a + drumbeat red ("never ran"); `dir_without_manifest` → excluded yellow ("corrupt") + drumbeat at-least-yellow (corrupt newest, even though the dir's AGE may be fresh — the manifest-content signal escalates); `dir_with_malformed_manifest` → excluded yellow + drumbeat at-least-yellow. A shallow impl that collapses `dir_without_manifest` into `absent` for ONE check but not the OTHER FAILS the matrix (the inconsistency Codex flagged); a consistent 3-state impl PASSES across both checks. (This forces the two checks to share `_read_newest_manifest`'s classification.)

Run → FAIL.

- [ ] **Step 2: Implement** both checks (lazy-import the `_NYSE`/`_now_to_utc` idiom for drumbeat; direct SQL for candidates with the actionable-bucket filter + the `MAX(id) FROM evaluation_runs` latest-run anchor). ASCII strings.

**Acceptance:** drumbeat + candidate tests pass; `ruff check swing/` clean. Commits: `feat(monitoring): Task 5a -- drumbeat-liveness check (artifact age + total_unattributed)` + `feat(monitoring): Task 5b -- candidate-completeness check (sentinel-filtered null pivots + error-bucket)`.

---

## Task 6: `_check_fetch_transport_health` — the yfinance_calls TRANSPORT indicator (NOT a usability check)

**Files:**
- Modify: `swing/monitoring/research_health.py` (add `_check_fetch_transport_health`)
- Modify: `tests/monitoring/test_research_health_checks.py` (transport section)

Emits ONE check, `key="fetch_transport_health"`. Reports the `yfinance_calls` error+empty RATE over a recent window. **TRANSPORT indicator ONLY (brief §6.2 #7, the 18-C boundary, LOAD-BEARING):**
- `status='success'` is TRANSPORT success, NOT data usability — **the all-NaN-Close ragged bar records `success`** (the 06-10 defect rows came through `success` transport). So this check NEVER substitutes for check #1; `temporal_log_finiteness` (Task 2) stays the usability authority. The two are complementary.
- A stale `in_flight` row = incomplete/unknown, NOT a hung call (`yfinance_calls.py` docstring: "treat a stale `in_flight` row as INCOMPLETE/unknown, NOT a hung call") — EXCLUDE `in_flight` from the rate denominator (count only terminal rows: success/empty/error).
- Treat row counts as a SAMPLE/indicator, NEVER a census (drops under finish-contention) — **NEVER alarm on a LOW row count (the brief §6.2 #7 LOCK — BINDING, not a tunable heuristic).** With < `_TRANSPORT_MIN_SAMPLE` terminal rows in the window → green, summary "n/a (insufficient sample)". **(Codex R6 MAJOR #2 — surface, don't suppress):** even on the low-sample green, the DETAIL carries the observed rate (`"N terminal rows: K error, M empty (below sample floor)"`) so the signal is VISIBLE to the RD without ALARMING (the color stays green per the LOCK; the data is not discarded). The LIVE DB has only 4 rows — green by sample-floor, with the 0% rate shown in detail. **Rationale for keeping the LOCK over Codex's "derive color from observed rows anyway":** the 18-C boundary is explicit that a low yfinance_calls count is unreliable (rows drop under finish-contention), so a rate computed on a tiny sample would FALSE-ALARM — exactly the failure the LOCK prevents. The brief's transport-vs-usability boundary makes #1 (`temporal_log_finiteness`) the authority that catches the actual data defect regardless of transport sample size; #7 alarming on sparse traffic would be the redundant-and-noisy failure mode. The detail-surfacing is the adopted half of R6-M2; overriding the color-on-low-sample is REJECTED as a brief-LOCK conflict (flagged in the return report).

**Grounding:** `yfinance_calls` status enum `{in_flight, success, empty, error}` (`0030:36-38`); `ts` ISO naive (`0030:22`). LIVE DB: 4 rows all success, newest 2026-06-14.

- error RATE (`error / terminal_count`) over the recent window > `_TRANSPORT_RED_ERROR_PCT` → red; > `_TRANSPORT_YELLOW_ERROR_PCT` → yellow.
- `empty` is a transient transport signal (rate-limit/weekend) — fold into a SEPARATE empty-rate at a looser threshold (empty is less alarming than error). Worst-of the error-color and empty-color.

```python
# Transport-health is a SAMPLE/indicator, never a census (18-C boundary). Never
# alarm on a low row count; a stale in_flight row is unknown, not hung.
_TRANSPORT_RECENT_WINDOW = 50       # most-recent N terminal rows by ts
_TRANSPORT_MIN_SAMPLE = 10          # < this many terminal rows -> green n/a (low-count guard)
_TRANSPORT_YELLOW_ERROR_PCT = 20.0
_TRANSPORT_RED_ERROR_PCT = 50.0
_TRANSPORT_YELLOW_EMPTY_PCT = 50.0  # empty is looser than error (transient/weekend)
```
Degradation: missing `yfinance_calls` table → yellow schema-unavailable (mirror; re-raise non-schema OperationalError). Empty table → green "n/a (no fetch audit yet)".

- [ ] **Step 1: Write the failing tests** (transport section). Seed `yfinance_calls` rows via the real repo (`insert_in_flight` + `update_call_outcome` — `yfinance_calls.py`) so the production shape is exercised; respect the SQL shape CHECK (batch carries `ticker_count`, single/intraday carry `ticker` — `0030:61-67`).

1. `test_transport_green_when_low_sample` — seed 4 success rows (the LIVE-DB shape) → "green", summary "n/a (insufficient sample)" (NOT red, NOT a rate-driven color on 4 rows — the brief §6.2 #7 LOCK). An impl that computes a rate-driven COLOR on a tiny sample, or that alarms on the low count, FAILS; the sample-floor impl passes. (THE never-alarm-on-low-count test — the 18-C boundary.) Additionally (Codex R6 MAJOR #2 — surface-don't-suppress): assert the DETAIL string carries the observed terminal count + error/empty tallies (e.g. contains "4" and "0 error") so the low-sample signal is VISIBLE without alarming. An impl that omits the rate from the detail FAILS this sub-assertion.
1b. `test_transport_sample_floor_boundary_activates_rate_logic` (Codex R7 MAJOR #3 — pair the low-sample green with the floor crossing) — seed a HIGH error fraction (e.g. 60% error) at TWO sample sizes straddling `_TRANSPORT_MIN_SAMPLE`: (a) `_TRANSPORT_MIN_SAMPLE - 1` terminal rows → "green" "n/a (insufficient sample)" (below floor — the LOCK suppresses the color); (b) `_TRANSPORT_MIN_SAMPLE` terminal rows at the SAME 60% error → "red" (at/above floor → the rate logic activates). This proves the impl ACTUALLY computes the rate once the floor is crossed (NOT a stub that is "always green on low sample" and never rate-aware). A stub-green impl returns green for BOTH → FAILS case (b); the real rate-aware impl flips to red at the floor → PASSES. (Distinguishes the never-computes-a-rate stub — Codex R7 MAJOR #3. State both sample sizes + the resulting colors in the docstring.)
2. `test_transport_green_when_all_success` — seed 20 success rows → 0% error → "green". A yellow/red impl FAILS.
3. `test_transport_yellow_on_error_rate` — seed 20 terminal rows, 5 error (25% > 20, <50) → "yellow". A green impl FAILS; a red impl FAILS.
4. `test_transport_red_on_high_error_rate` — 20 terminal rows, 12 error (60% > 50) → "red".
5. `test_transport_excludes_in_flight_from_rate` (the 18-C boundary) — seed 15 success + 5 in_flight (NO error/empty) → terminal_count = 15 (>= sample floor), error rate 0% → "green"; assert the in_flight rows are NOT counted in the denominator (an impl counting in_flight as a sample of 20 or as a non-success "problem" would mis-rate). Construct so that counting in_flight as errors would flip to yellow/red → distinguishes. (Stale in_flight = unknown, not hung.)
6. `test_transport_yellow_on_empty_rate` — 20 terminal rows, 12 empty, 0 error (60% empty > 50% empty floor, error 0%) → "yellow" (the empty signal). A green-because-no-errors impl FAILS; the worst-of(error,empty) impl returns yellow → PASS. (Distinguishes the empty-as-transient signal at its own looser floor.)
7. `test_transport_does_not_substitute_for_finiteness` (the complementarity LOCK) — seed `yfinance_calls` ALL success (transport green) WHILE seeding a NaN-Close observation in `pattern_forward_observations`; assert `_check_fetch_transport_health` returns GREEN and `_check_temporal_log_finiteness` returns RED on the SAME DB — proving #7 (success transport) does NOT mask the #1 usability defect (the all-NaN-Close-records-success boundary). This is the load-bearing #7-vs-#1 separation test.
8. `test_transport_yellow_when_missing_table` — no `yfinance_calls` table → "yellow" schema-unavailable.
9. `test_transport_green_when_empty_table` — schema-present, 0 rows → "green" "n/a (no fetch audit yet)".

Run → FAIL.

- [ ] **Step 2: Implement** `_check_fetch_transport_health(conn) -> list[ResearchHealthCheck]`: `SELECT status FROM yfinance_calls ORDER BY ts DESC LIMIT ?` (the recent window), filter terminal (success/empty/error), apply the sample floor, compute error% + empty%, worst-of. Wrap in the scoped OperationalError degradation. ASCII strings.

**Acceptance:** transport tests pass; `ruff check swing/` clean. Commit: `feat(monitoring): Task 6 -- fetch-transport-health check (yfinance_calls transport indicator; never substitutes for #1)`.

---

## Task 7: `compute_research_health` — the aggregator (worst-of + envelope + clock normalization)

**Files:**
- Modify: `swing/monitoring/research_health.py` (add `compute_research_health` + `_normalize_now_to_naive_local`)
- Create: `tests/monitoring/test_research_health_aggregate.py`

Mirror 18-E's `compute_tool_health` (`tool_health.py:508-531`) + `_normalize_now_to_naive_local` (`tool_health.py:485-505`):

```python
def compute_research_health(
    conn, *, cfg=None, exports_root=None, manifest_dir=None, now=None,
) -> ResearchHealthStatus:
    now = _normalize_now_to_naive_local(now)   # naive-Hawaii-local boundary (mirror 18-E)
    if exports_root is None:
        exports_root = RESEARCH_HEALTH_ARTIFACT_PATH.parent.parent  # exports/research/
    checks: list[ResearchHealthCheck] = []
    checks += _check_temporal_log_finiteness(conn)
    checks += _check_excluded_reason_breakdown(exports_root=exports_root)
    checks += _check_coverage_gaps(conn, now=now)
    checks += _check_structural_integrity(conn)
    checks += _check_drumbeat_liveness(exports_root=exports_root, now=now)
    checks += _check_candidate_completeness(conn)
    checks += _check_fetch_transport_health(conn)
    overall = worst_of([c.status for c in checks])
    # Codex R1 MAJOR #1: stamp generated_ts AWARE-UTC so the 18-F staleness gate
    # is host-tz-independent. `now` is naive-Hawaii-local (the session helpers'
    # frame); attach Pacific/Honolulu then convert to UTC (the 18-E _now_to_utc
    # idiom, tool_health.py:347-350) -- NOT replace(tzinfo=UTC), which mis-shifts
    # a Hawaii-local instant by ~10h.
    generated_ts = _research_now_iso(now)   # -> "...+00:00"
    return ResearchHealthStatus(
        overall=overall, checks=checks, generated_ts=generated_ts)
```
`_normalize_now_to_naive_local` is byte-identical to 18-E's (`tool_health.py:485-505`): None → `datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)`; aware → convert-to-Hawaii-then-strip; naive → pass through. (Import it from `tool_health` OR copy — implementer's call; importing is single-source.) `_research_now_iso` is REUSED from Task 1 (Codex R2 MAJOR #1 — it was already defined there as the default-factory; the aggregator calls it with the explicit normalized `now`). **`generated_ts` is gate-3-safe AND host-tz-independent by construction (Codex R1 MAJOR #1):** an aware-UTC stamp is compared by the 18-F reader against `datetime.now(UTC)` (both aware-UTC), so a freshly-written envelope reads green/not-future on ANY host — the round-trip test (Task 8 #9) proves it under a simulated non-Hawaii host clock.

The `cfg` arg is accepted for signature-parity with 18-E (and for the script to pass `Config.from_defaults()` if a future check needs `cfg.rs.benchmark_ticker` etc.) — V1 checks do not require it, so `cfg=None` is a fully valid bare call (`compute_research_health(conn)`).

- [ ] **Step 1: Write the failing tests** (`test_research_health_aggregate.py`):

1. `test_all_green_overall_green` — seed a DB + tmp exports where every check is green (finite obs, fresh manifest under threshold, contiguous coverage, clean structure, fresh drumbeat, complete candidates, low-sample transport) → `compute_research_health(...).overall == "green"` AND `len(checks) == 7` (one per check, NOTE: coverage+structural+candidate+transport each emit exactly one; finiteness one; excluded one; drumbeat one → 7). Assert all 7 keys present.
2. `test_one_red_makes_overall_red` — seed everything green EXCEPT a NaN-Close observation (finiteness red) → `overall == "red"`. A first-check-status or lexical-max impl would NOT return red → distinguishes.
3. `test_one_yellow_no_red_overall_yellow` — green except one yellow (e.g. a stale drumbeat) → `overall == "yellow"`.
4. `test_compute_research_health_bare_conn_call_shape` — `compute_research_health(conn)` (no cfg/exports_root — the bare shape) against a SCHEMA-PRESENT-but-EMPTY DB does NOT raise and returns a `ResearchHealthStatus`. Assert the n/a-vs-data-vs-schema distinction: with no manifest/artifacts the artifact checks are green/"n/a"; the structural/finiteness checks on an empty schema-present DB are green (empty is not a defect for these); NO check false-reds on absent optional inputs. (The bare-call LOCK-conformance.)
5. `test_compute_research_health_pre_schema_conn_degrades_not_crash` — `compute_research_health(conn)` against a bare `:memory:` conn (NO `ensure_schema`) returns a `ResearchHealthStatus` (does NOT raise) with the schema-dependent checks degraded to "yellow" "schema unavailable". An unwrapped impl raises → FAIL.
6. `test_compute_research_health_is_read_only` — open the seeded DB `mode=ro`, call `compute_research_health(ro_conn, ...)`; assert it returns normally (NO `sqlite3.OperationalError: attempt to write a readonly database`). THE read-only LOCK-conformance proof (LOCK §4.1) — any accidental DB write surfaces as an OperationalError on the ro connection.
7. `test_generated_ts_uses_injected_now_as_aware_utc` (Codex R1 MAJOR #1) — pass `now=datetime(2026,6,14,20,31,0)` (naive — interpreted as Hawaii-local HST = UTC-10). Assert `status.generated_ts == "2026-06-15T06:31:00+00:00"` (20:31 HST → 06:31 next-day UTC) and `to_dict()["generated_ts"]` matches. Arithmetic: 20:31 HST + 10h = 06:31 UTC (next calendar day). A naive-passthrough impl emits `"2026-06-14T20:31:00"` (no offset) → FAILS; the aware-UTC impl emits the `+00:00` next-day stamp → PASSES. (Distinguishes the naive-Hawaii-vs-aware-UTC conversion — state both values in the docstring per the regression-arithmetic discipline.)
8. `test_aggregate_normalizes_aware_now` — pass an AWARE-UTC `now` AND its equivalent naive-Hawaii-local; assert the same per-check statuses AND the same `generated_ts` (both normalize to the same instant → same aware-UTC stamp; the relabel-vs-convert proof; mirror 18-E `tool_health.py` test). Compute both anchor dates in the docstring (regression-arithmetic discipline).

Run → FAIL.

- [ ] **Step 2: Implement** `compute_research_health` + `_normalize_now_to_naive_local`. (`_research_now_iso` + the aware-UTC default-factory already shipped in Task 1 — Codex R2 MAJOR #1; Task 7 only wires the aggregator to call `_research_now_iso(now)` with the normalized clock.)

**Acceptance:** aggregate tests pass; the bare-conn + `mode=ro` LOCK tests pass; `ruff check swing/` clean. Commit: `feat(monitoring): Task 7 -- compute_research_health aggregator (worst-of + envelope + aware-UTC clock normalization)`.

---

## Task 8: `scripts/research_health.py` — the probe + ATOMIC `latest.json` write + the 18-F round-trip

**Files:**
- Create: `scripts/research_health.py`
- Create: `tests/scripts/test_research_health_script.py`
- Create: `tests/monitoring/test_research_health_envelope_roundtrip.py`

Mirrors `scripts/tool_health.py`: `argparse` `--db` (default `~/swing-data/swing.db`) + `--json`; opens its OWN `mode=ro` connection; loads `Config.from_defaults()`; `_resolve_now()` clock seam; calls `compute_research_health(conn, cfg=cfg)`; renders ASCII (default) / JSON (`--json`); **AND on every run writes the conformant envelope ATOMICALLY to `RESEARCH_HEALTH_ARTIFACT_PATH`** (brief §6.3 + §6.5(b)).

**The atomic write (brief §6.5(b) + the `os.replace`-same-filesystem gotcha):**
```python
def _write_latest_json_atomic(envelope: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)   # create exports/research/health/ if absent
    # tmp in the SAME directory (os.replace requires same filesystem -- the
    # Windows OSError 18 gotcha) then atomic replace.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, indent=2)
        os.replace(tmp, path)   # atomic on the same filesystem
    except BaseException:
        # best-effort cleanup of the tmp on any failure (do not leak tmp files)
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
```
**The write target resolution — accessor by DEFAULT; an EXPLICIT `--out` arg for the SUBPROCESS test (Codex R2 MAJOR #2 + R6 MAJOR #1 + R7 CRITICAL #1):** the script resolves the write destination as:
```python
def _resolve_out_path(args) -> Path:
    # PRODUCTION default = the shared accessor (the 18-F providers call the SAME
    # accessor; single source). --out is an EXPLICIT, operator-visible override
    # used ONLY by the subprocess ASCII test (a separate process cannot inherit
    # an in-process accessor monkeypatch). It is NOT a hidden runtime env var
    # (Codex R7 CRITICAL #1: a silent env override could decouple a production
    # run from the live stoplight path); --out defaults to None -> the accessor,
    # so an ordinary `python scripts/research_health.py` ALWAYS writes the
    # contract path exports/research/health/latest.json.
    if args.out is not None:
        return Path(args.out)
    from swing.monitoring import stoplights
    return stoplights.research_health_artifact_path()
```
So: PRODUCTION default (no `--out`) = `stoplights.research_health_artifact_path()` (the accessor — the 18-F providers call the same accessor, single source — the contract path is HARDWIRED for any real run, Codex R7 CRITICAL #1); IN-PROCESS tests monkeypatch `stoplights.research_health_artifact_path` (redirects BOTH writer + the 18-F reader for the round-trip, Task 8 #7); the SUBPROCESS test passes `--out <tmp_path>` (an EXPLICIT, visible cross-process redirect — NOT a silent env var). The script MUST NOT read the bare imported constant `RESEARCH_HEALTH_ARTIFACT_PATH` (a direct-constant write defeats the in-process monkeypatch). **The write happens in BOTH the ASCII and `--json` paths** (so the stoplight lights regardless of how the operator runs the probe). **There is exactly ONE production write path (the accessor); `--out` is an explicit test/operator override that defaults off — no silent runtime decoupling.**

ASCII render (mirror `tool_health.py:32-50`): `== research health ==`, `generated:`, `overall: [COLOR]`, per-check `  [{STATUS}] {key}: {summary}` + `      {detail}`; footer `ATTENTION (N): ...` or `RESEARCH HEALTH: all clear.`. Exit 0 when green else 1 (ASCII path); `--json` always exits 0.

- [ ] **Step 1: Write the failing tests.**

`tests/scripts/test_research_health_script.py`:
1. `test_script_all_clear_exit_zero` — seed a green DB on disk (`tmp_path/swing.db`); monkeypatch `swing.monitoring.stoplights.research_health_artifact_path` → `tmp_path/health/latest.json` (the SINGLE write+read hook, Codex R2 MAJOR #2) so the script writes there; run `main(["--db", str(db)])`; assert return 0 AND stdout contains "all clear".
2. `test_script_attention_exit_one` — seed a NaN-Close observation (red); assert `main(...)` returns 1 AND stdout contains "ATTENTION" AND the red check key.
3. `test_script_json_flag` — `main(["--db", str(db), "--json"])`: `json.loads` stdout; assert `parsed["monitor"]=="research_measurement"`, `parsed["overall"] in {green,yellow,red}`, `parsed["checks"]` is a list of length 7; assert exit 0 even when overall red.
4. `test_script_writes_latest_json_atomic_and_validates_through_reader` (Codex R3 MAJOR #2 — strengthened) — run `main([...])` for BOTH the default (ASCII) path AND the `--json` path (two invocations, same monkeypatched `stoplights.research_health_artifact_path`). For EACH path: (a) assert the `latest.json` file EXISTS at the monkeypatched path, parses as JSON, `parsed["monitor"]=="research_measurement"`; (b) assert NO `*.tmp` file remains in the dir (atomic cleanup); (c) **immediately call the LIVE `swing.monitoring.stoplights.read_validated_research_envelope()` and assert it returns a NON-None `(overall, env)` (i.e. the EXACT file the script just wrote VALIDATES through the real 18-F reader, not greys).** This closes the gap where `--json` could bypass the write or write to a different location while existence-only tests still pass: an impl whose `--json` path skips the write would leave the previous-path file (or none) → the reader validation on the `--json`-only run FAILS. Both output modes MUST write the same canonical target AND round-trip green.
5. `test_script_creates_health_dir_when_absent` — point the artifact path at a NON-existent `tmp_path/health/latest.json`; run `main`; assert the `health/` parent dir was created and the file written.
6. `test_script_output_is_ascii` — `subprocess.run([sys.executable, str(script_path), "--db", str(db), "--out", str(tmp_path / "health" / "latest.json")], capture_output=True, env={**os.environ, "PYTHONPATH": str(repo_root)})` against a seeded RED state (the string-heavy ATTENTION path); assert `result.stdout.decode("ascii")` does not raise. **The `--out` arg is MANDATORY here (Codex R6 MAJOR #1 + R7 CRITICAL #1): the subprocess cannot inherit the in-process accessor monkeypatch, so without it the script would write the LIVE `exports/research/health/latest.json` and flip the real GUI state during the test. `--out` is the EXPLICIT (non-silent) redirect — NOT a runtime env override of the production path.** Assert the written file landed at the tmp path (NOT the live path). `capsys` is INSUFFICIENT (bypasses the OS encoder) — the subprocess is mandatory (recipe §2 + the cp1252 gotcha).

`tests/monitoring/test_research_health_envelope_roundtrip.py` (THE all-5-gates-by-construction proof — brief §4 "envelope-conformance test"):
7. `test_envelope_roundtrips_through_18f_reader` (Codex R7 MAJOR #4 — SINGLE redirect, no stale-file masking) — start from a FRESH `tmp_path/health/` (assert `latest.json` does NOT exist yet — no stale file). Use **ONLY the in-process accessor monkeypatch** (`monkeypatch.setattr("swing.monitoring.stoplights.research_health_artifact_path", lambda: tmp_path/"health"/"latest.json")`) — do NOT use `--out` here (the round-trip must exercise the SAME path for writer and reader; `--out` is the subprocess-only redirect). Run `compute_research_health` on a seeded DB → write its `to_dict()` to the accessor path via the atomic writer (or invoke the script's `main` in-process so the write goes through `_resolve_out_path` → the monkeypatched accessor) → then call the LIVE `read_validated_research_envelope()`; assert it returns `(overall, env)` (NOT None — VALIDATES, does NOT grey) AND `overall in {"green","yellow","red"}` AND `overall == status.overall`. **Assert the file the reader validated is the EXACT file just written this invocation** (e.g. capture its mtime/content before the read; the fresh-dir precondition rules out a stale pre-existing file masking a non-write). This exercises ALL 5 false-green gates against the REAL 18-F reader: identity, valid overall, overall==worst_of, fresh non-future aware-UTC generated_ts, per-check render schema (incl. non-empty checks). A non-conformant envelope greys → FAILS; the by-construction-conformant envelope validates → PASSES. (Memory `feedback_adversarial_review_verify_data_shapes`: a data-shape-vs-live-reader round-trip, not a logic-vs-spec check.)
8. `test_envelope_roundtrips_green_yellow_red` — parametrize over a seeded green, a seeded yellow, and a seeded red DB; assert each round-trips and the 18-F reader returns the matching color (NOT grey). Proves the envelope is conformant across all 3 emitted colors.
8b. `test_written_envelope_roundtrips_for_manifest_absent_vs_corrupt` (Codex R6 MAJOR #3 — the writer-reader round-trip across manifest states) — drive `compute_research_health` (then write `latest.json` via the script/atomic writer) for TWO manifest states on an otherwise-green DB: (i) NO `shadow-expectancy-*` dir at all (`absent`) → the manifest checks are green/n-a → overall green → the LIVE reader validates GREEN; (ii) a newest dir with a CORRUPT manifest → `excluded` yellow + `drumbeat` at-least-yellow → overall at-least-yellow → the LIVE reader validates YELLOW (NOT grey, NOT green). Assert the WRITTEN file (not just the in-memory status) round-trips through `read_validated_research_envelope()` with the expected color for BOTH states. This proves the corrupt-vs-absent distinction propagates all the way to the artifact the 18-F reader consumes (an impl that treats corrupt-as-absent → writes green → the reader validates green → the test FAILS for state (ii)). Closes the writer-reader gap Codex flagged.
9. `test_envelope_generated_ts_is_not_future_for_reader_on_any_host` (Codex R1 MAJOR #1 — RESOLVED) — write an envelope whose `generated_ts` is the aware-UTC stamp from the aggregator; assert the LIVE 18-F reader does NOT grey it as future-dated (gate 3 — `age < timedelta(0)`, `stoplights.py:200`) NOR as stale, **and that this holds independent of the host timezone.** Because the stamp is aware-UTC, the reader takes the aware branch `now = datetime.now(parsed.tzinfo)` (`stoplights.py:716-718`) → both sides are aware-UTC → the `age` is the true instant delta on ANY host (verified: an aware-UTC ts ~0.5s old yields `age` ~0.5s, neither future nor stale). To prove host-independence without changing the actual OS tz, the test may additionally feed a deliberately-OLD aware-UTC stamp (8 days) and assert the reader greys it as STALE (proving the gate is live + frame-correct), and a FRESH one and assert it validates. This REPLACES the earlier naive-stamp cross-tz caveat (which the aware-UTC fix eliminates). No remaining cross-tz watch item.

Run → FAIL (script/module do not exist).

- [ ] **Step 2: Implement `scripts/research_health.py`** with `main(argv=None)`, the `argparse` `--db`/`--json`/`--out` args, `_resolve_out_path(args)` (explicit `--out` → else the accessor; Codex R6 MAJOR #1 + R7 CRITICAL #1 — `--out` defaults None so production always writes the contract path), the atomic writer (`_write_latest_json_atomic`), ASCII/JSON render, exit codes. Lazy/`sys.path`-insert the repo root (the `tool_health.py:22-24` precedent). `if __name__ == "__main__": sys.exit(main())`.

**Acceptance:** all script + round-trip tests pass; the subprocess ASCII test passes; running `PYTHONPATH=. python scripts/research_health.py --json` against the live DB emits a valid envelope AND writes `latest.json` (operator gate, §7). `ruff check swing/` clean. Commit: `feat(monitoring): Task 8 -- scripts/research_health.py probe + atomic latest.json write + 18-F round-trip`.

---

## Verification (whole-arc, before close)

- [ ] `python -m pytest tests/monitoring tests/scripts/test_research_health_script.py -q` — all green.
- [ ] `python -m pytest -m "not slow" -q` — full fast suite green on the merged head (the no-false-green discipline: read the actual tail).
- [ ] `ruff check swing/` — clean.
- [ ] **Read-only proof:** `test_compute_research_health_is_read_only` (Task 7 #6) drives the aggregator on a `mode=ro` connection; passing it IS the read-only proof (LOCK §4.1).
- [ ] **Envelope-conformance proof:** the Task 8 round-trip tests (#7-#8) write `latest.json` → read it back through the LIVE 18-F `read_validated_research_envelope` → assert it validates (not grey) across green/yellow/red. ALL 5 false-green gates exercised against the real reader.
- [ ] **Operator gate (§7):** `PYTHONPATH=. python scripts/research_health.py` and `... --json` against the live `~/swing-data/swing.db` — operator witnesses the ASCII report renders (no cp1252 crash), the JSON envelope shape, AND that `exports/research/health/latest.json` is written + the 18-F research stoplight LIGHTS (grey → green/yellow/red) on the dashboard. **On the live DB this arc should fire RED on `temporal_log_finiteness` (103 non-finite obs) — the motivating defect surfacing is the success criterion, not a test failure.** (Binding per §7.)
- [ ] **No measurement-chain touch:** confirm the diff touches ONLY `swing/monitoring/research_health.py`, `scripts/research_health.py`, `tests/monitoring/`, `tests/scripts/` — NO `swing/evaluation/dates.py` (Codex R1 MAJOR #2: the coverage-gap logic is self-contained in the monitor module; `dates.py`'s `_NYSE`/`last_completed_session` are lazy-IMPORTED read-only, never edited), NO `swing/data`, `swing/trades`, `swing/pipeline`, no migration, no `pyproject.toml`, no `swing.config.toml`, no DB write. The ONLY `swing/` file this arc creates is `swing/monitoring/research_health.py`.

---

## LOCKS — encoded in this plan (brief §3/§4 + the commissioning brief §4/§6.5)

1. **Read-only (LOCK §4.1)** — `compute_research_health` takes a caller's connection and only READS; the script opens its OWN `mode=ro` URI connection (Task 8); `test_compute_research_health_is_read_only` (Task 7 #6) proves no write fires. The ONLY writes are `latest.json` + the ASCII report (artifact writes, same posture as the shadow-expectancy artifacts — CHARC-confirmed §6.5 the artifact write does NOT violate the read-only-DB LOCK). NEVER writes the measurement DB.
2. **Single source of truth (LOCK §4.2)** — check #2 + #5 READ the engine `manifest.json` (Task 3 `_read_newest_manifest`); they do NOT fork the funnel/attribution logic. The check sums the manifest's `per_hypothesis.*.excluded` reasons + reads `funnel.detection_level.unique_signals` + `funnel.unattributed` — no recomputation of attribution.
3. **ASCII output only (LOCK §4.3)** — every `summary`/`detail`/`print` is ASCII; the Task 8 subprocess "stdout bytes decode as ASCII" test guards it (`capsys` is insufficient — the cp1252 gotcha).
4. **No new dependency (LOCK §4.4)** — the monitor's OWN code imports only stdlib (`sqlite3`/`json`/`dataclasses`/`pathlib`/`datetime`/`os`/`math`/`argparse`/`tempfile`/`contextlib`); NO pandas in the monitor module (mirror 18-E). It REUSES existing project helpers (`swing.evaluation.dates`, `swing.data.ohlcv_finiteness`, the repo readers, the engine manifest JSON) lazy-imported inside the check functions — reuse-not-fork, NOT a new dependency.
5. **Import the 3 contract constants (LOCK C1)** — `RESEARCH_HEALTH_ARTIFACT_PATH`, `RESEARCH_MONITOR_ID`, `RESEARCH_ARTIFACT_MAX_AGE_DAYS` are IMPORTED from `swing.monitoring.stoplights` (Task 1 module head); NEVER redeclared. `test_monitor_field_is_research_measurement` (Task 1 #9) asserts the `monitor` field equals the imported constant.
6. **Transport-vs-usability boundary (§6.2 #7)** — check #7 (`fetch_transport_health`) is a TRANSPORT indicator: it excludes `in_flight`, never alarms on a low/sampled row count, treats `success` as transport-not-usability, and NEVER substitutes for check #1. `test_transport_does_not_substitute_for_finiteness` (Task 6 #7) proves #7 green WHILE #1 red on the same NaN DB. Check #1 (`temporal_log_finiteness`) stays the usability authority.
7. **The 5 false-green gates by construction (brief §6.5(a))** — the `__post_init__` frozenset validation (rejecting grey + invalid overall + empty key/summary) + the NON-EMPTY-`checks` reject (Codex R5 MAJOR #1 — the 18-F empty-checks grey vector) + `ResearchHealthStatus.__post_init__` enforcing `overall == worst_of(checks)` + the aware-UTC non-future `generated_ts` + the imported `monitor` id make a non-conformant envelope STRUCTURALLY unconstructable. Task 8's round-trip through the LIVE 18-F reader is the proof.
8. **Frozen-clock (R2 rider)** — every test exercising date/session/staleness logic injects `now` (the `compute_research_health(now=)` seam + `scripts/research_health.py:_resolve_now`); NO live wall clock.

---

## V1 simplifications + brief-grounding refinements (with V2 dependency) — for the return report

- **NIGHTLY HALF DEFERRED (brief §2 scope).** This plan ships ONLY the script-first half (the 80% that lights the stoplight). The nightly pipeline-step half — `step_guard` B-shape best-effort, `warnings_json`, `role_mail`-fyi-to-`rd` on ATTENTION, keeping `latest.json` < 1 day fresh — is a SEPARATE fast-follow dispatch with its OWN CHARC sec-3 pass (CHARC-confirmed §6.5). **V2 dependency:** the nightly dispatch. (The script-first `latest.json` greys toward the 7-day edge between RD spin-ups — the honest "research-health last assessed N days ago"; the nightly half keeps it < 1 day fresh.)
- **check #2 reads `funnel.per_hypothesis.*.excluded`, SUMMED across hypotheses — NOT a top-level breakdown (grounding refinement).** The brief §6.2 #2 names the 3 reasons against `unique_signals`; the LIVE manifest places them under per-hypothesis `excluded` sub-dicts (`funnel.py:98-112`, verified on disk). The check sums each reason across all hypotheses and divides by `funnel.detection_level.unique_signals`. This is a brief-grounding refinement (the path was under-specified), not a deviation from intent. Defended against `per_hypothesis == {}` (the older-run shape).
- **check #1 None-guard around the shared predicate (grounding refinement).** The brief says "reuse the shared finiteness predicate rather than re-implementing NaN/None detection," but `is_finite_ohlc` handles NaN/inf ONLY and RAISES `TypeError` on `None`. The check guards None/missing/non-numeric BEFORE calling the predicate (treating them as non-finite hits). The predicate is reused for the NaN/inf case (single source for that definition); the None handling is a thin guard, not a re-implementation.
- **check #6 null-pivot scope = ACTIONABLE buckets only (gotcha #25).** A null pivot is EXPECTED in the sentinel buckets `error`/`excluded` (the LIVE-DB shape: 255 nulls, all in error/excluded). The check scopes null pivots to `aplus`/`watch` to avoid a permanent false-positive. This is a sentinel-bucket-discipline grounding, not a deviation.
- **check #5 / check #2 manifest discovery = newest `shadow-expectancy-*` dir (the `weekly_glance.py` idiom), 3-state ABSENT/CORRUPT/OK (Codex R1 MAJOR #3).** The brief refers to "the engine's manifest.json the engine already emits"; there is no central pointer to the newest manifest, so the check reverse-sorts the dated dirs (the established `weekly_glance.py:49-51` precedent). `_read_newest_manifest` returns a 3-state result so a CORRUPT newest manifest escalates to yellow (not silently n-a) — the M3 fix; absent stays green/n-a. **V2 dependency:** if a `latest`-pointer artifact is ever added the check can read it directly.
- **Thresholds are CONSERVATIVE V1 floors (commissioning §3.4 — "derive cutoffs from this audit's baselines").** The excluded-rate / coverage-gap / error-bucket / transport-rate cutoffs are first-pass floors calibrated against the current live baseline (invalid_ohlc ~30%, 0 gaps, 0 errors). **The RD tunes them post-build** (the watch-standard amendment, RD's deliberate action). Flagged so the executor does not treat them as locked contract.
- **Transport low-sample stays GREEN per the brief §6.2 #7 LOCK — R6-M2 partially adopted (detail-surfacing only).** Codex R6 MAJOR #2 argued a low-sample gate can mask a real transport regression and proposed deriving the color from the observed rows anyway. The COLOR-on-low-sample override is REJECTED (the brief LOCK "never alarm on a low row count" is BINDING — a yfinance_calls count drops under finish-contention, so a sparse-sample rate would false-alarm; check #1 is the usability authority that catches the actual defect regardless). The DETAIL-surfacing half IS adopted (the observed count + tallies appear in the detail so the signal is visible without alarming). **Executor note:** do NOT "fix" the low-sample green to a rate-driven color — that violates the brief LOCK.
- **Explicit `--out` arg for subprocess-test isolation — NOT a silent runtime override (Codex R6 MAJOR #1 + R7 CRITICAL #1).** The production write destination is ALWAYS `stoplights.research_health_artifact_path()` (the accessor — the contract path `exports/research/health/latest.json` the 18-F reader keys off). `--out` is an EXPLICIT, operator-visible CLI override defaulting to None (→ the accessor), used ONLY by the subprocess ASCII test to redirect the write to `tmp_path` (a separate process cannot inherit the in-process accessor monkeypatch). It is HARMLESS in production (no `--out` → the contract path), and being explicit it cannot silently decouple a real run from the live stoplight (the failure mode Codex R7 CRITICAL #1 flagged for a hidden env var — which was REMOVED in favor of `--out`). Flagged as a deliberate, minimal, visible test-isolation seam.
- **`generated_ts` is AWARE-UTC — host-tz-independent (Codex R1 MAJOR #1, RESOLVED — NOT a deferred caveat).** 18-D DIVERGES from 18-E's naive-local stamp: it emits aware-UTC (`...+00:00`). 18-E's envelope is consumed in-process by `compute_tool_health`; 18-D's envelope round-trips through the 18-F reader's staleness gate, which compares a naive ts against the HOST wall clock — so a naive-Hawaii stamp would false-grey on a non-Hawaii host (CI/UTC). The aware-UTC stamp makes the reader take its aware branch (`datetime.now(parsed.tzinfo)`, `stoplights.py:716-718`) → host-independent. Task 8 #9 proves it; no remaining cross-tz watch item. **Executor note:** this is a deliberate, tested divergence from the 18-E precedent — do NOT "consistency-fix" it back to naive-local (that re-opens the false-grey).
