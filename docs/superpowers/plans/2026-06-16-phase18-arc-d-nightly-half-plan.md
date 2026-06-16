# Phase 18 Arc 18-D — nightly-half + 2 monitor calibrations — implementation plan

**Phase:** copowers writing-plans (plan-only; NO production code).
**Brief:** `docs/18-D-nightly-half-writing-plans-dispatch-brief.md`; binding spec
`docs/data-collection-health-monitor-commissioning-brief.md` §6.7 (CHARC sec-3
PASS 2026-06-16, conditions C-NH1-5). Parts 2-3 are monitor-internal calibrations
(FIX-1 precedent; RD gates at executing).
**Baseline:** `a3110895` (contains the brief). Worktree `.worktrees/18-d-nightly-plan`.
**Review tier:** `review-fast` (writing-plans). Run to `NO_NEW_CRITICAL_MAJOR`.

This is the DEFERRED 18-D nightly half (per C4/C5) plus the two post-build monitor
CALIBRATIONS the operator folded into one coordinated monitor-touching dispatch.
The shipped 18-D script-first monitor (`compute_research_health`,
`scripts/research_health.py`) is REUSED unchanged except where a task below names a
specific edit; the §3 envelope / frozenset enum validation / atomic-write stay
UNCHANGED (LOCK 2).

---

## 0. Grounding (every anchor confirmed against live code on `a3110895`)

| Anchor | Live confirmation |
| --- | --- |
| `_step_shadow_expectancy` wrap | `swing/pipeline/runner.py:1036-1051` — hand-rolled `lease.step("shadow_expectancy")` + try/except (NOT `step_guard`; deliberately inline per `step_guard.py` docstring because of the gotcha-#27 `run_warnings` append in its failure side). `lease.step("complete")` follows at `:1053`. The new `research_health` step inserts **between :1051 and :1053** (C-NH3). |
| `step_guard` signature | `swing/pipeline/step_guard.py:37-45` — `step_guard(lease, name, *, logger, status_key=None, log_failure=None)`. `lease.step(name)` fires in `__enter__` (`:60`); `LeaseRevokedError` re-raises (`:72-73`); all other `Exception` swallowed + `logger.warning` + (if `status_key`) `lease.status(**{status_key:"failed"})` (`:74-80`); clean exit sets `<status_key>="ok"` (`:70-71`). |
| `mode=ro` conn pattern | `scripts/research_health.py:129-132` — `ro_uri = db_path.as_uri() + "?mode=ro"; sqlite3.connect(ro_uri, uri=True, timeout=2.0)`. This is the exact C-NH2 idiom the step mirrors (NOT the runner's read-write `connect(cfg.paths.db_path)` at `db.py:1626`). |
| `cfg.paths.db_path` in scope at the step site | `Path`; used by the runner at `runner.py:389,560`. Available where the new step lands. |
| Atomic `latest.json` writer | `scripts/research_health.py:58-70` (`_write_latest_json_atomic`) + `:117` (`_resolve_out_path` → `stoplights.research_health_artifact_path()` when no `--out`). C-NH4 extracts this into `write_research_health_artifact` in `swing/monitoring/research_health.py`; the script refactors to call it. |
| `research_health_artifact_path()` accessor | `swing/monitoring/stoplights.py:43-49` → `RESEARCH_HEALTH_ARTIFACT_PATH` (`:27-30`, `exports/research/health/latest.json`). |
| `ResearchHealthStatus.to_dict()` | `swing/monitoring/research_health.py:210-216` → the §3 envelope (`monitor`/`generated_ts`/`overall`/`checks`). |
| #2 `invalid_ohlc` baseline value | **23** — see §0.1 (live-manifest grounding). |
| #3 trailing-grace boundary | trailing-≤1 → not-red; trailing-≥2 OR any interior → escalate — see §0.2 (live coverage grounding). |
| 18-B.1 write-barrier interaction | `insert_observation` (`swing/data/repos/pattern_forward_observations.py`) RAISES on non-finite OHLC (`8022d45d`). Monitor tests plant defect/edge rows via **raw `conn.execute` INSERT** — already the established pattern (`tests/monitoring/test_research_health_checks.py:75-86` `_seed_observation`; `tests/scripts/test_research_health_script.py:66-73`). The two calibration tests plant only FINITE OHLC + manifest JSON, so this does not bite them; called out so a future edit does not regress. |

### 0.1 #2 `invalid_ohlc` baseline grounding (live manifests)

The shadow-expectancy engine emits per-hypothesis `funnel.per_hypothesis.<H>.excluded.invalid_ohlc`
(summed across hypotheses by `_check_excluded_reason_breakdown`) against
`funnel.detection_level.unique_signals`. Read off the live untracked manifests under
`exports/research/` (newest-by-name wins, the monitor's selection):

| manifest dir | `unique_signals` | `invalid_ohlc` | pct | `insufficient_forward_depth` | `missing_observations` |
| --- | --- | --- | --- | --- | --- |
| `…20260612T105643Z` | 65 | 22 | 33.8% | 4 | 8 |
| `…20260613T004956Z` | 76 | 23 | 30.3% | 9 | 11 |
| `…20260613T033450Z` | 77 | 23 | 29.9% | 9 | 12 |
| `…20260613T091809Z` (newest) | 77 | **23** | **29.9%** | 9 | 12 |

- `invalid_ohlc` has **plateaued at 23** across the last three runs (06-13). The
  engine's `validate_bars` (`research/harness/shadow_expectancy/validate.py:32-48`,
  reason `invalid_ohlc`) rejects signals whose frozen bars fail finiteness /
  OHLC-consistency — i.e. **the same 06-10 non-finite cohort FIX 1 baselined in
  check #1**. The immutable temporal log + the 18-B.1 write-barrier mean NO new
  non-finite can enter → this count is a **permanent ceiling** that only DILUTES as
  `unique_signals` grows (29.9% today, falling).
- **Aging behavior:** the count crept 22→23 (06-12→06-13) as the matcher's window
  caught slightly more of the SAME immutable cohort, then stabilized at 23. It is
  bounded above by the fixed cohort size; a value of **24 or more is NOT explainable
  by the known cohort → a new event (a write-barrier regression).**
- **Chosen constant:** `_INVALID_OHLC_BASELINE_COUNT = 23` (the current plateau /
  newest-manifest value). At-or-below 23 → not-red for the `invalid_ohlc` arm;
  strictly above 23 → escalate.
- Live check today: `_check_excluded_reason_breakdown` returns **RED**
  (`invalid_ohlc=23 (29.9%)` > `_EXCL_RED_PCT=25.0`). Post-calibration the
  `invalid_ohlc` arm at 23 → green; the other two reasons keep their existing pct
  thresholds (`insufficient_forward_depth=11.7%` and `missing_observations=15.6%`
  are both > `_EXCL_YELLOW_PCT=10.0` → yellow), so the check goes **RED → YELLOW**
  (driven by the un-baselined reasons, as designed — SCOPE LOCK).

### 0.2 #3 `coverage_gaps` trailing-grace grounding (live DB + monitor run)

Ran the shipped `_check_coverage_gaps(conn, now=datetime.now())` against the live DB
(`~/swing-data/swing.db`, 385 detections / 1287 observations) on 2026-06-15:

- Result today: **RED, 382 coverage gaps**, detail `det1: 1 missing; det2: 1 missing; …`.
- Per-detection gap classification (`last_completed_session = 2026-06-15`):
  - **383** detections: a TRAILING-EXACTLY-1 gap (only the newest expected session
    `2026-06-15` unobserved — the post-close→pre-nightly benign window).
  - **2** detections: a trailing-≥2 gap (a real ≥2-session observe lag).
  - **0** detections: an INTERIOR gap.
- The spec cites "382 1-missing"; the live figure is 383 today (the benign window
  shifts by one each session) — same phenomenon. The current monitor sums every
  missing session and reds; the 383 trailing-1 detections are exactly the recurring
  nightly false-red.
- **Calibration:** tolerate a TRAILING-≤1-session lag (the newest expected session
  unobserved = expected pre-nightly) → that detection contributes NO gap signal;
  RED/escalate only on (i) a trailing-≥2 lag OR (ii) ANY interior gap. Post-calibration
  the live check goes **RED → GREEN** (the 2 trailing-≥2 detections contribute 2
  remaining gaps → yellow at most via the existing `_COVERAGE_YELLOW_GAPS`/`RED_GAPS`
  thresholds; with only those 2 it is yellow — an honest, non-spurious signal, not
  the 382-driven false-red). [Exact post-calibration color depends on the residual
  count; the point is the 383 trailing-1 detections stop driving it.]

---

## 1. LOCKS carried into every task (RD merge-blocking)

1. **READ-ONLY DB (C-NH2).** The nightly step opens a SEPARATE `mode=ro` URI conn;
   ONLY `latest.json` is ever written; NEVER the measurement DB.
2. **Reuse, don't re-implement.** The shipped `compute_research_health` + the
   single-sourced `write_research_health_artifact` (C-NH4) + the 3 contract constants
   (`RESEARCH_HEALTH_ARTIFACT_PATH`/`RESEARCH_MONITOR_ID`/`RESEARCH_ARTIFACT_MAX_AGE_DAYS`).
   The §3 envelope, the `__post_init__` frozenset enum validation, and the atomic-write
   mechanics stay UNCHANGED.
3. **Best-effort step (C-NH1/C-NH5).** `step_guard` BARE B-shape (NO `status_key` — the
   O1 resolution: `status_key="research_health_status"` would force a forbidden schema
   change; see Task 2); never perturbs the run — no exception escapes except
   `LeaseRevokedError`; on ANY failure write NOTHING (retain the prior `latest.json`;
   never a partial artifact).
4. **Calibrations are monitor-internal.** NO schema, NO dependency, NO new tripwire;
   ONLY the #3 / #2 logic changes. SCOPE LOCK for #2: baseline ONLY `invalid_ohlc`;
   `insufficient_forward_depth` + `missing_observations` keep their existing thresholds.
5. **NO `role_mail`-on-ATTENTION** (deferred to arc 18-H.7).

---

## 2. Task slices (TDD: red → green → commit per task; one logical change each)

> NOTE for the executing implementer: per recipe §2, this writing-plans dispatch
> commits the PLAN once at convergence. The tasks below are for the EXECUTING
> dispatch (a later arc). Each is a single red→green cycle.

### Task 1 — extract `write_research_health_artifact` (C-NH4 single-source)

**Goal:** one writer function in `swing/monitoring/research_health.py`; the script
refactors to call it; the nightly step (Task 2) calls the SAME fn — NO second copy.

**Production change (`swing/monitoring/research_health.py`):**
- Add `write_research_health_artifact(status: ResearchHealthStatus, out_path: Path | None = None) -> Path`:
  - `out_path = out_path if out_path is not None else research_health_artifact_path()`
    (lazy `from swing.monitoring.stoplights import research_health_artifact_path` —
    the accessor, NOT the bare constant, so a test monkeypatch of the accessor is
    honored; mirrors the script's `_resolve_out_path` at `scripts/research_health.py:54-55`).
  - `out_path.parent.mkdir(parents=True, exist_ok=True)`.
  - Atomic write: `tempfile.mkstemp(dir=str(out_path.parent), suffix=".tmp")` →
    `os.fdopen(fd, "w", encoding="utf-8")` → `json.dump(status.to_dict(), fh, indent=2)`
    → `os.replace(tmp, out_path)`; on any `BaseException`, `contextlib.suppress(OSError)`
    + `os.unlink(tmp)` then re-raise. This is `scripts/research_health.py:58-70`
    relocated VERBATIM (same `os.replace`-same-filesystem gotcha; tmp in the DEST dir).
  - Returns the resolved `out_path` (so callers/tests can assert the path).
- The function consumes `status.to_dict()` — it does NOT recompute or re-validate the
  envelope (the dataclass `__post_init__` already enforced conformance at construction;
  LOCK 2).

**Refactor (`scripts/research_health.py`):**
- DELETE the local `_write_latest_json_atomic` (`:58-70`).
- At the write site (`:152`) call
  `write_research_health_artifact(status, out_path=out_path)` (import lazily, same
  module). `_resolve_out_path` stays (it resolves the `--out` override / accessor for
  BOTH the writer AND `exports_root`); pass its result as `out_path`. The script's
  observable surface (ASCII, `--json`, exit codes, `--out`) is UNCHANGED.

**Tests (`tests/monitoring/test_research_health_artifact.py` — new file):**
- `test_write_research_health_artifact_atomic_no_tmp_leftover`: build a green
  `ResearchHealthStatus`, call `write_research_health_artifact(status, out_path=tmp/…)`,
  assert the file exists, parses, `monitor == "research_measurement"`, and NO `*.tmp`
  remains in the dir.
- `test_write_research_health_artifact_default_path_uses_accessor`: monkeypatch
  `swing.monitoring.stoplights.research_health_artifact_path` → a tmp path; call with
  `out_path=None`; assert the artifact lands at the monkeypatched path (proves the
  accessor is the default, not a hardcoded constant).
- `test_write_research_health_artifact_creates_parent_dir`: `out_path` under a
  non-existent nested dir; assert the parent is created and the file lands.
- `test_script_invokes_shared_writer` (the C-NH4 single-source proof, per brief §3 — R1
  MAJOR #1: the test must OBSERVE the script calling the shared writer, NOT merely compare
  two artifacts): seed a green DB + a fresh manifest (reuse the
  `tests/scripts/test_research_health_script.py` helpers' shape); monkeypatch
  **`swing.monitoring.research_health.write_research_health_artifact`** (the SHARED symbol)
  with a recording spy that captures `(status, out_path)` and forwards to the real impl;
  run the SCRIPT (`mod.main([...])`); assert the spy was invoked **exactly once** with a
  `ResearchHealthStatus` whose `to_dict()["monitor"] == "research_measurement"` and the
  resolved `out_path`. **Distinguishing (this is the load-bearing point):** a script that
  kept its OWN private copy of the atomic write would NOT invoke the shared symbol → the
  spy would record zero calls → the test FAILS. An artifact-equality comparison cannot
  detect that (both copies emit the same bytes); a spy on the shared symbol can. The
  script must reference the writer such that the monkeypatch of the
  `swing.monitoring.research_health` attribute is honored (lazy `from
  swing.monitoring.research_health import write_research_health_artifact` inside `main`, or
  reference it as `research_health.write_research_health_artifact` — the test's monkeypatch
  target and the call site must agree; the spy firing exactly once asserts they do).

**Distinguishing note:** the atomic/no-leftover test fails against a non-atomic
`open().write()` impl (leftover-`.tmp` / partial-file assertions). The
`..._default_path_uses_accessor` test fails against a hardcoded-constant impl. The
`..._invokes_shared_writer` spy fails against a private-duplicate-copy script (the R1
MAJOR #1 vector).

### Task 2 — the nightly pipeline step (C-NH1/2/3/5)

**Goal:** a best-effort pipeline step running the SAME `compute_research_health` +
`write_research_health_artifact`, placed immediately after `_step_shadow_expectancy`,
on a `mode=ro` conn, writing nothing on failure.

**Production change (`swing/pipeline/runner.py`):**
- Add a private helper `_step_research_health(*, cfg) -> None`:
  ```
  def _step_research_health(*, cfg) -> None:
      from swing.monitoring.research_health import (
          compute_research_health, write_research_health_artifact)
      ro_uri = cfg.paths.db_path.as_uri() + "?mode=ro"      # C-NH2 (mirror scripts/research_health.py:129)
      conn = sqlite3.connect(ro_uri, uri=True, timeout=2.0)
      try:
          status = compute_research_health(conn, cfg=cfg)    # default exports_root -> the contract path's parent
      finally:
          conn.close()
      write_research_health_artifact(status)                 # C-NH4 default = the contract latest.json
  ```
  - C-NH5 is structural: `compute_research_health` is computed FIRST and only on
    SUCCESS does `write_research_health_artifact` run; any exception inside compute (or
    the `mode=ro` connect) propagates to the `step_guard` BEFORE any write → the prior
    `latest.json` is untouched. A failure NEVER produces a partial artifact (the atomic
    `tmp + os.replace` means a write-time crash also leaves the prior file intact — but
    the compute-before-write ordering is the primary C-NH5 guarantee).
  - `sqlite3` is already imported at `runner.py:10`. `compute_research_health` runs with
    the DEFAULT `exports_root` (None → `RESEARCH_HEALTH_ARTIFACT_PATH.parent.parent` =
    `exports/research/`), the SAME root the script + the 18-F providers use — so the
    manifest-consuming checks (#2/#5) read the live engine artifacts. (No `manifest_dir`
    override in production.)
- Insert the step at the C-NH3 placement — between `runner.py:1051` (end of the
  `_step_shadow_expectancy` try/except) and `:1053` (`lease.step("complete")`):
  ```
  with step_guard(lease, "research_health", logger=log):
      _step_research_health(cfg=cfg)
  ```
  - C-NH1: `step_guard` **bare B-shape (NO `status_key`)** — see the O1 resolution
    below; `LeaseRevokedError` propagates, all other `Exception` swallowed + logged
    (default `logger.warning("research_health failed: %s", exc)`); the step NEVER fails
    the run. Do NOT hand-roll the wrapper.
  - The step does NOT append to `run_warnings` (unlike shadow_expectancy) — the gotcha-#27
    `run_warnings` posture that forces shadow_expectancy inline does NOT apply here; the
    `step_guard` log + the `lease.step("research_health")` breadcrumb is the audit,
    consistent with weather/watchlist/etc.

**O1 RESOLVED — no `status_key` (the spec's literal `status_key="research_health_status"`
is NOT achievable in this no-schema arc; GROUNDED, BINDING):** `lease.status(**cols)`
(`swing/pipeline/lease.py:156-164`) routes to `update_status_columns`
(`swing/data/repos/pipeline.py:90-112`). That function:
1. has a fixed `allowed` set = `{weather_status, evaluation_status, watchlist_status,
   recommendations_status, charts_status, export_status}` (`:96-99`) and **RAISES
   `ValueError("unknown status columns: …")` on any key outside it** (`:100-102`); AND
2. does a dynamic `UPDATE pipeline_runs SET <key> = ?` (`:105-109`) — so the key must also
   be a real `pipeline_runs` COLUMN.

`research_health_status` is neither in `allowed` NOR a `pipeline_runs` column. So
`status_key="research_health_status"` would: on the clean-exit
`lease.status(research_health_status="ok")` inside `step_guard`'s `try`, raise
`ValueError`; that is caught by `step_guard`'s `except Exception` as a failure; the guard
then attempts `lease.status(research_health_status="failed")` which **raises `ValueError`
AGAIN** — and that second raise is NOT re-caught, so it **escapes the guard and FAILS the
run** — a direct C-NH1 violation. Making `status_key` work requires BOTH a new
`pipeline_runs.research_health_status` column (a migration) AND widening the `allowed` set
— **a schema change that crosses LOCK 4 / the C-NH carve-out (this arc is monitor-internal,
NO schema).** Therefore the plan uses the **bare B-shape (omit `status_key`)**, which
`step_guard` fully supports (the `status_key=None` B variant, `step_guard.py:9,70,79`) and
which satisfies all three BINDING C-NH1 properties (revoke propagates / all else
swallowed+logged / never fails the run). The `lease.step("research_health")` breadcrumb
(fired in `step_guard.__enter__`) still records the step + its timing.
**Flagged for the orchestrator/RD:** if a `research_health_status` column IS wanted, it is
a SEPARATE schema decision (its own migration + `allowed`-set widening), explicitly NOT
folded into this monitor-internal arc.

**Tests (`tests/pipeline/test_step_research_health.py` — new file):**
- `test_step_runs_after_shadow_expectancy_and_writes_latest_json`: drive
  `_step_research_health(cfg=cfg)` with a `cfg` whose `db_path` points at a seeded green
  DB and whose artifact path is monkeypatched to a tmp; assert `latest.json` is written +
  validates through the 18-F reader (`stoplights.read_validated_research_envelope()` is
  not None). [The ordering-after-shadow_expectancy is asserted via the runner-level test
  below, OR by inspection of the placement; the unit test proves the step's own contract.]
- `test_step_uses_readonly_conn` (C-NH2): monkeypatch/spy
  `compute_research_health` to capture its `conn`; assert the conn was opened from a
  `?mode=ro` URI (e.g. assert a write through that conn RAISES
  `sqlite3.OperationalError` "readonly database"). Distinguishing: a read-write
  `connect()` would let the write succeed.
- `test_failing_compute_does_not_write_and_leaves_prior_artifact_intact` (C-NH5):
  pre-write a SENTINEL `latest.json` at the (monkeypatched) artifact path; monkeypatch
  `compute_research_health` to RAISE; run the step UNDER `step_guard` (build a fake
  lease, or call the runner-level wrapper); assert (a) the step does NOT raise out of the
  guard, (b) the sentinel `latest.json` is BYTE-IDENTICAL afterwards (no partial / no
  overwrite), (c) NO `*.tmp` leftover. Distinguishing: a write-before-compute or a
  non-atomic write would clobber/partial the sentinel.
- `test_step_does_not_fail_the_run_on_arbitrary_error` (C-NH1 swallow): monkeypatch
  `_step_research_health` to raise a generic `RuntimeError`; run it inside the BARE
  B-shape `with step_guard(lease, "research_health", logger=log):` (NO `status_key` — the
  O1 resolution) against a fake lease; assert no exception escapes the guard.
- `test_step_writes_no_status_column` (the O1 / no-schema LOCK proof, R1 MAJOR #2): the
  fake lease records every `lease.status(**cols)` call; run the step BOTH on the
  success path AND with a forced `RuntimeError`; assert `lease.status` is **NEVER called**
  (the bare B-shape writes no `*_status` column → no `update_status_columns` →
  no `pipeline_runs.research_health_status` dependency). **Distinguishing:** a B-shape that
  passed `status_key="research_health_status"` WOULD call `lease.status(...)` (and, against
  the real `update_status_columns`, raise `ValueError` on the unknown key) — this test
  fails such an impl, locking the no-schema contract the plan actually chose.
- `test_step_propagates_lease_revoked` (C-NH1 revoke): inside the same BARE-B-shape
  `step_guard`, raise `LeaseRevokedError`; assert it PROPAGATES (does not get swallowed).
  [The swallow/propagate split is already covered by `step_guard`'s own tests; the
  load-bearing NEW assertion here is that the `research_health` SITE is wrapped by
  `step_guard` (not a hand-rolled try/except) — assert it via a runner-level test that a
  revoke during the `research_health` step bubbles to the `force_cleared` path, OR an
  AST/source assertion that the site uses `step_guard`. Do not duplicate step_guard's own
  suite.]
- `test_step_placement_after_shadow_expectancy` (C-NH3): a source/AST or
  runner-call-order assertion that `research_health` is invoked AFTER `shadow_expectancy`
  and BEFORE `complete`. Simplest robust form: a runner-level integration test that spies
  on `lease.step` call order and asserts the sequence `… "shadow_expectancy",
  "research_health", "complete"`. (Mirror how existing runner tests assert step order, if
  any; else a focused order spy.)

### Task 3 — CALIBRATION A: #3 `coverage_gaps` trailing-≤1 grace

**Goal:** a TRAILING-≤1-session lag (newest expected session unobserved) → not-red;
RED/escalate only on a trailing-≥2 lag OR any INTERIOR gap. Monitor-internal; NO schema /
dep / new tripwire (LOCK 4).

**Production change (`swing/monitoring/research_health.py` `_check_coverage_gaps`):**
- Today the per-detection block computes `missing = len(expected - observed)` and sums
  into `total_missing` (`:824-835`). The calibration must classify each detection's
  missing set as **pure-trailing-tail-of-length-≤1** vs **everything else**, and EXCLUDE
  the pure-trailing-≤1 case from the gap count.
- Precise definition (compute from the already-built `expected` set + `observed` set +
  the sorted expected sessions):
  - `missing_set = expected - observed`.
  - The **trailing tail** = the maximal suffix of `sorted(expected)` whose sessions are
    ALL in `missing_set` (walk `sorted(expected)` from the newest backward while each is
    missing; stop at the first observed session).
  - A detection's gap is **graced (contributes 0)** iff `missing_set == trailing_tail`
    AND `len(missing_set) <= 1` (the ONLY missing session is the single newest expected
    session — a pure trailing-1).
  - Otherwise the detection contributes its `len(missing_set)` to `total_missing` (an
    interior gap, a leading gap, OR a trailing-≥2 tail — all real signals).
  - Equivalent / simpler implementation the executing dev may choose: a missing session
    is "graced" iff it is the NEWEST expected session (`== max(expected)`) AND it is the
    ONLY missing session for that detection. Both formulations yield the same result; the
    plan fixes the SEMANTICS (trailing-≤1 = the single newest-expected hole), the dev
    picks the cleanest expression. The constant boundary (`<= 1`) is a named module
    constant `_COVERAGE_TRAILING_GRACE_SESSIONS = 1` so the threshold is explicit + tunable.
- Apply the grace to BOTH the OPEN-detection tail path and the never-observed /
  zero-observation path (a mature detection whose ONLY missing session is the single
  newest expected one is equally benign pre-nightly). The terminal-status path already
  expects no tail (`upper = max_obs`) so it is unaffected.
- The existing `_COVERAGE_YELLOW_GAPS` / `_COVERAGE_RED_GAPS` escalation on
  `total_missing` is UNCHANGED — the calibration only changes what COUNTS as a gap, not
  the count→color mapping. The malformed-date / out-of-calendar / duplicate-date defect
  handling is UNCHANGED (those remain yellow regardless of grace — they are not
  trailing-grace-eligible).

**Tests (add to `tests/monitoring/test_research_health_checks.py`, Task-4a section) —
the brief's required BOTH-WAYS distinguishing test:**
- `test_coverage_grace_trailing_one_session_not_red` (the NOT-red half): an OPEN mature
  detection (`data_asof=2026-06-04`) observed CONTIGUOUSLY through the
  second-newest expected session, missing ONLY the single newest expected session
  (`last_completed_session(_NOW)=2026-06-12`). With `_SESSIONS` minus `2026-06-12`
  observed, the only hole is the trailing newest → assert `check.status == "green"`.
  **Distinguishing arithmetic:** pre-calibration this is `total_missing=1` → YELLOW
  (`>= _COVERAGE_YELLOW_GAPS`); post-calibration the trailing-1 is graced →
  `total_missing=0` → GREEN. (Confirms the test fails on the OLD code and passes on the
  NEW.)
- `test_coverage_trailing_two_and_interior_gap_red` (the RED half, both vectors in one
  detection-set per the brief): seed TWO detections —
  (a) an OPEN mature detection missing the TWO newest expected sessions (a trailing-2
  lag, e.g. observed through 06-10, missing 06-11 + 06-12); and
  (b) a TERMINAL detection with an INTERIOR hole (observed 06-05, 06-08, 06-10, status
  invalidated → 06-09 interior missing). Combined `total_missing` = 2 (trailing-2) + 1
  (interior) = 3 → assert `check.status in ("yellow","red")` AND that the grace did NOT
  swallow either (assert the trailing-2 detection's id and the interior detection's id
  appear in `check.detail`, i.e. neither was graced). **Distinguishing:** an
  over-eager grace that swallowed the trailing-2 (or the interior) would drop the count
  and could green the check → this asserts both survive.
- A REGRESSION guard: confirm the existing trailing-2 missing-tail test
  (`test_coverage_yellow_on_missing_tail_for_open_detection`, trailing-2) STILL yields
  yellow/red (it is not graced), and `test_coverage_yellow_on_one_hole` (interior) STILL
  yields yellow. These existing tests already encode "trailing-2 and interior are not
  graced"; the executing implementer runs the FULL coverage-test class and confirms zero
  regressions. (No existing test asserts yellow on a trailing-EXACTLY-1, so none flips —
  confirmed by inspection of the Task-4a suite on `a3110895`.)

### Task 4 — CALIBRATION B: #2 `invalid_ohlc` baseline

**Goal:** the `invalid_ohlc` arm reds only ABOVE a named baseline count; the other two
reasons keep their existing pct thresholds (SCOPE LOCK). Monitor-internal; NO schema /
dep / new tripwire.

**Production change (`swing/monitoring/research_health.py` `_check_excluded_reason_breakdown`):**
- Add a named module constant:
  ```
  # CALIBRATION B (18-D §6.7): invalid_ohlc reflects the engine rejecting the
  # SAME 06-10 non-finite cohort FIX 1 baselined in check #1 -- a known, accepted,
  # PERMANENT ceiling (immutable log + the 18-B.1 write-barrier => no NEW non-finite
  # can enter; it only dilutes). GROUNDED against the newest live manifest
  # (shadow-expectancy-20260613T091809Z: invalid_ohlc=23 of 77 unique_signals;
  # plateaued 22->23->23->23 across 06-12..06-13). Red ONLY on a count STRICTLY
  # ABOVE this baseline (a new event = a write-barrier regression).
  _INVALID_OHLC_BASELINE_COUNT = 23
  ```
- In the per-reason loop (`:614-624`), special-case `invalid_ohlc` with the FOLLOWING
  EXACT escalation curve (R1 MINOR: the curve is now PINNED — no open alternative, so a
  given above-baseline input maps to exactly one color):
  - Compute `over = max(0, count - _INVALID_OHLC_BASELINE_COUNT)`.
  - `over == 0` (count ≤ baseline) → the `invalid_ohlc` arm is **GREEN**.
  - `over > 0` → compute `excess_pct = 100.0 * over / unique_signals` and map it through
    the SAME existing thresholds applied to the EXCESS (not the raw count):
    - `excess_pct > _EXCL_RED_PCT` (25.0) → **RED**;
    - `excess_pct > _EXCL_YELLOW_PCT` (10.0) → **YELLOW**;
    - else (`0 < excess_pct <= 10.0`) → **YELLOW** (any excess above a PERMANENT ceiling
      is a real new event → never green when `over > 0`; the yellow-at-minimum floor).
  - This is the SINGLE binding curve (the "simpler absolute-floor alternative" considered
    in an earlier draft is REJECTED — it left the color under-determined). It mirrors FIX
    1's percentage style and the existing `insufficient_forward_depth`/`missing_observations`
    pct mapping, only applied to the EXCESS for `invalid_ohlc`.
  - For `insufficient_forward_depth` and `missing_observations`: UNCHANGED — the existing
    `pct > _EXCL_RED_PCT / _EXCL_YELLOW_PCT` mapping on the RAW count (SCOPE LOCK — do NOT
    baseline them).
  - The `detail` string still surfaces ALL three reasons with their counts + raw pct (so
    the baselined-out 23 stays VISIBLE in the detail without driving red — mirror FIX 1's
    "surface the accepted cohort in detail" posture). Add a note in the `invalid_ohlc`
    detail segment like `invalid_ohlc=23 (29.9%, baseline 23)`.
- The 0-signals / no-hypotheses / corrupt / absent manifest branches are UNCHANGED.

**Tests (add to `tests/monitoring/test_research_health_checks.py`, Task-3 section) — the
brief's required BOTH-WAYS distinguishing test:**
- `test_excluded_invalid_ohlc_at_baseline_not_red` (the NOT-red half): a manifest with
  `_funnel(77, {"H": {"excluded": {"invalid_ohlc": 23}}})` — the EXACT live shape — and
  the other two reasons absent/zero → assert the `invalid_ohlc` arm does NOT drive red,
  i.e. `check.status != "red"` (and, with only invalid_ohlc=23 and no other reason, the
  check is GREEN). **Distinguishing arithmetic:** pre-calibration `23/77 = 29.9% >
  _EXCL_RED_PCT=25.0` → RED; post-calibration `23 <= _INVALID_OHLC_BASELINE_COUNT=23` →
  the arm is green → check green. (Fails on OLD, passes on NEW.)
- `test_excluded_invalid_ohlc_above_baseline_red` (the RED half, the PINNED curve): a
  manifest with `_funnel(77, {"H": {"excluded": {"invalid_ohlc": 50}}})` → `over = 50-23 =
  27`; `excess_pct = 100*27/77 = 35.1% > _EXCL_RED_PCT=25.0` → assert `check.status ==
  "red"`.
- `test_excluded_invalid_ohlc_just_above_baseline_yellow` (the yellow-floor half of the
  pinned curve): a manifest with `_funnel(77, {"H": {"excluded": {"invalid_ohlc": 24}}})` →
  `over = 1`; `excess_pct = 100*1/77 = 1.3%` → falls in the `0 < excess_pct <= 10` band →
  assert `check.status == "yellow"` (NOT green — any excess above the permanent ceiling is
  a real event). **Distinguishing:** proves "strictly above baseline → never green" AND
  that the yellow-floor (not the raw-pct path) governs a tiny excess.
- `test_excluded_other_reasons_keep_thresholds` (SCOPE LOCK proof): a manifest with
  `invalid_ohlc=0` but `insufficient_forward_depth=20` of `unique_signals=100` (20% >
  `_EXCL_YELLOW_PCT`) → assert the check is YELLOW (driven by `insufficient_forward_depth`,
  whose threshold is UNCHANGED). And a sibling with `missing_observations=30` of 100 (30%
  > `_EXCL_RED_PCT`) → RED. **Distinguishing:** proves the baseline was NOT applied to the
  other two reasons (if it had been, these would not escalate the same way).
- A REGRESSION guard (the pinned-curve flips are DETERMINISTIC):
  - `test_excluded_red_over_threshold` (invalid_ohlc=30 of 100 = 30%) on `a3110895`
    asserts RED. Under the pinned curve: `over = 30-23 = 7`; `excess_pct = 100*7/100 =
    7.0%` → `0 < 7 <= 10` → **YELLOW**. The test FLIPS red→yellow and MUST be re-asserted
    to yellow (comment citing CALIBRATION B).
  - `test_excluded_yellow_at_threshold` (invalid_ohlc=15 of 100 = 15%) asserts YELLOW.
    Under the pinned curve: `15 <= 23` → `over = 0` → **GREEN**. The test FLIPS
    yellow→green and MUST be re-asserted to green (or re-pointed at an un-baselined reason
    to preserve its "yellow-at-threshold" intent for those reasons).
  - `test_excluded_green_when_under_threshold` (invalid_ohlc=5 of 100): `5 <= 23` → GREEN
    — UNCHANGED (already green; no flip).
  - `test_excluded_sums_across_hypotheses` (check the seeded invalid_ohlc sum vs 23): the
    executing implementer re-grounds its expected color to the pinned curve.
  - **The executing implementer greps the full Task-3 excluded suite for EVERY
    `invalid_ohlc`-driven assertion, recomputes the expected color under the pinned curve
    (over→excess_pct→threshold), re-asserts each, and reports the flip count + the
    re-asserted values in the executing return report.** [Per memory
    `feedback_regression_test_arithmetic` — compute under both pre- and post-fix paths.]

---

## 3. Before-review full-suite gate (recipe §2, the 18-F lesson)

The EXECUTING dispatch (not this writing-plans dispatch) runs the FULL fast suite
(`python -m pytest -m "not slow" -q`) to GREEN before the Codex loop — Task 4 in
particular FLIPS pre-existing excluded-reason tests, and the cross-VM / global-invariant
tests are not exercised per-task. Catch the flips BEFORE the review converges on a green
diff. (This plan-dispatch's own Codex review is over the PLAN doc; no production code.)

---

## 4. V1-simplification ledger (deferred / out-of-scope)

| Item | Status | Dependency |
| --- | --- | --- |
| `role_mail`-on-ATTENTION (C5 fyi-to-`rd`) | DEFERRED to arc **18-H.7** | the sender-taxonomy (`VALID_FROM` enum) + importable-post + edge-trigger design surface. Explicitly NOT added here (LOCK 5; brief §6.7 part-1). |
| `research_health_status` column / `lease.status` key | RESOLVED — bare B-shape (NO `status_key`); a column would need a migration + `allowed`-set widening (LOCK 4 forbids) | a SEPARATE schema decision if RD wants the status column; explicitly not in this arc. |
| Watch-standard amendment (RD cites the FINAL thresholds) | sequences AFTER this lands | RD post-build action; `docs/research-director-watch-standard.md` §3.1. |
| #2 escalation curve above baseline | PINNED (R1 MINOR): `over=max(0,count-23)`; `over==0`→green; else `excess_pct=100*over/unique_signals` mapped through `_EXCL_RED_PCT`/`_EXCL_YELLOW_PCT` with a yellow floor when `over>0`. No open alternative. | — |
| #3 grace formulation | SEMANTICS fixed (trailing-≤1 newest-expected hole graced) + a named `_COVERAGE_TRAILING_GRACE_SESSIONS=1`; the dev picks the cleanest EXPRESSION of that exact semantic (both formulations in Task 3 are provably equivalent) | — |

---

## 5. Open questions (live-code-wins flags; route up before executing)

- **O1 — RESOLVED in-plan (a deviation from the spec's literal C-NH1, grounded +
  flagged).** The spec names `status_key="research_health_status"`, but `lease.status`
  → `update_status_columns` RAISES on that unknown key AND needs a non-existent
  `pipeline_runs` column (full grounding in Task 2). Honoring the literal `status_key`
  would either FAIL the run (C-NH1 violation) or force a schema migration (LOCK 4
  violation). **Resolution: the bare B-shape (no `status_key`)**, which satisfies all
  three BINDING C-NH1 properties. **This is the single spec-vs-live deviation in the plan
  — surfaced for the orchestrator/RD ruling** (accept the bare B-shape, OR commission a
  separate `research_health_status` schema arc). Recipe §7 / brief §7: a part that would
  need a schema change crosses the C-NH carve-out → flag, don't fold it in.
- **O2 — RESOLVED in-plan (no longer open).** The #2 above-baseline escalation curve is
  now PINNED to the excess-pct mapping (Task 4 / §4 ledger) and the #3 grace SEMANTIC is
  fixed (Task 3) with a named `_COVERAGE_TRAILING_GRACE_SESSIONS=1`; the executing dev
  picks only the cleanest EXPRESSION of the already-fixed #3 semantic (the two formulations
  are provably equivalent). If RD wants a different #2 curve, say so at the executing brief
  — but the plan no longer leaves it under-determined.

---

## 6. Done criteria (for THIS writing-plans dispatch)

- The plan covers all three parts: the nightly step (C-NH1-5), CALIBRATION A (#3), and
  CALIBRATION B (#2), each with GROUNDED data-notes (the runner placement line, the
  `step_guard` signature, the `mode=ro` pattern, the live `invalid_ohlc=23` manifest
  value + aging, the live trailing-1 coverage state) and DISTINGUISHING both-ways test
  specs with pre/post arithmetic.
- The LOCKS (§1) are reflected in every task; the calibrations are monitor-internal (no
  schema / dep / new tripwire); `role_mail` is deferred (§4).
- The Codex `review-fast` chain reached `NO_NEW_CRITICAL_MAJOR` (each round persisted to
  `.copowers-findings.md`).
- NO production code written (plan-only).
