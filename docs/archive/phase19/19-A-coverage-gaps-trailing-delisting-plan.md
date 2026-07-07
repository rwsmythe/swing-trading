# Implementation Plan — 19-A: coverage_gaps CALIBRATION-C trailing-delisting fix

**Arc:** 19-A (Phase 19, first arc). **Spec:** [`docs/coverage-gaps-trailing-delisting-fix-commissioning-brief.md`](../coverage-gaps-trailing-delisting-fix-commissioning-brief.md).
**Design status:** SETTLED (RD-proposed, CHARC-verified, operator-approved). This plan is `copowers:writing-plans` output — it does NOT re-open brainstorming.
**Deliverable:** this plan only. A separate executing dispatch follows AFTER an RD plan-stage review gate.
**Worktree base:** `fbc7c3ce` (`.worktrees/19-A-coverage-gaps`, branched off `main`).

---

## 0. Scope + self-certification (brief §4)

- **Single production file:** `swing/monitoring/research_health.py` (one function restructure + 4 doc-block updates).
- **Test file:** `tests/monitoring/test_research_health_checks.py` (add discriminating tests; existing tests unchanged).
- **NO schema change** — v31 holds; no migration.
- **NO §3 tripwire** — no new module, no new dependency, no new standing process, no `swing/data`/`swing/trades` carve-out. The monitor stays read-only. **Self-certified: this change crosses no CHARC §3 tripwire.**
- **Out of scope (do NOT implement):** RD's alternative window-truncation approach (v2 only); any `runner.py`/observe-step change; CALIBRATION-A / grace-bound changes; conservative-degrade (`run_observed_sessions is None`, schema-unavailable) changes.
- **Conventions:** conventional commits, trailer-free (the 3774-`Co-Authored-By`-free streak), no `--no-verify`, no amend.

---

## 1. Re-grounded code anchors (verified on disk against `fbc7c3ce`)

Every brief anchor grepped + verified. **Actual current line numbers:**

| Element | Brief cited | ACTUAL (on disk) | Notes |
|---|---|---|---|
| `_calibration_c_partition` def | :1063-1105 | **:1063-1105** | matches |
| clause-1 gate (`if not clause1: continue`) | :1091-1093 | **:1091-1093** (1091 `clause1 =`, 1092 `if not clause1:`, 1093 `continue`) | matches |
| the acceptance loop body | — | **:1090-1104** | `for session in missing_set:` at 1090; `residual =` at 1104 |
| function docstring | :1071-1086 | **:1071-1086** | matches |
| `_observe_skip_index` | :934-996 | **:934-996** | matches |
| `_OBSERVE_SKIP_REASONS` | :916 | **:916** | matches |
| module comment block (CALIBRATION C acceptance formula) | :895-916 | **:894-916** (block opens `# CALIBRATION C ...` at line 894) | **1-line drift** — block starts at 894, not 895 |
| never-observed (zero-obs) call-site + comment | :1268-1295 (comment :1275-1279) | call `_calibration_c_partition(...)` at **:1280-1282**; comment **:1275-1279** | matches |
| observed-arm call-site + comment | (the call-site "immediately below") | call at **:1324-1326**; comment **:1315-1322** | second doc block that references the semantics |
| `_graced_missing_count` def / usages | usage :1289 | def **:854-875**; usages **:1289** (zero-obs) + **:1333** (observed-arm) | matches |
| skip-warning emitter (`runner.py`) | :3081 | dict at **runner.py:3078-3082**; `"reason": "no bar for observation_date"` at **:3081** | matches; `non_finite_ohlc` sibling emitter at :3095-3099 |

**Supporting facts verified on disk:**
- `_OBSERVE_SKIP_REASONS = ("no bar for observation_date", "non_finite_ohlc")` (:916).
- `_observe_skip_index` (:934-996) admits a `(ticker, observation_date)` pair ONLY from a `state='complete'` `pipeline_runs` row whose `warnings_json` entry has `step=='pattern_observe'`, `reason in _OBSERVE_SKIP_REASONS`, both dates canonicalize, AND `observation_date == data_asof_date` (:993-994). **This is the fixture-tie mechanism** — a warning not tied to a completed run with `data_asof_date == observation_date` is DROPPED.
- Emitter shape (runner.py:3078-3082, verbatim): `{"step": "pattern_observe", "ticker": det.ticker, "observation_date": observation_date, "reason": "no bar for observation_date"}`. Fixtures mirror this exactly. Cross-checked against the live run 116/117 CNTA rows per the brief.
- `_graced_missing_count` (:854-875) graces (returns 0) ONLY when `len(missing) <= _COVERAGE_TRAILING_GRACE_SESSIONS (==1)` AND `missing == {max(expected)}` — i.e. a lone newest-session trailing hole. **A single trailing session is masked by this grace → every discriminating fixture uses ≥2 trailing sessions.**
- Thresholds: `_COVERAGE_YELLOW_GAPS = 1`, `_COVERAGE_RED_GAPS = 10` (:842-843). `total_missing == 0 → green`; `1..10 → yellow`; `> 10 → red`.
- Test harness (`tests/monitoring/test_research_health_checks.py`): `_NOW = datetime(2026, 6, 14, 12, 0, 0)` (:780) → `last_completed_session(_NOW) == 2026-06-12`. NYSE sessions in `[2026-06-05, 2026-06-12]` = `{06-05, 06-08, 06-09, 06-10, 06-11, 06-12}` (weekends 06-06/07 excluded). Helpers: `_seed_detection` (:41), `_seed_observation` (RAW insert, :66), `_seed_pipeline_run` (RAW insert, `warnings` → `warnings_json`, :89), `_only` (:114). `_C_BEFORE`/`_C_AFTER`/`_C_OBSERVED` (:1077-1079).

**No brief premise contradicted by live code.** Only drift: the module comment block starts at line 894 (brief said 895). Proceeding.

---

## 2. The fix (brief §2)

### 2.1 Current `_calibration_c_partition` loop (:1087-1105, verbatim)

```python
    accepted: set[str] = set()
    has_later = bool(observed)
    latest_observed = max(observed) if observed else None
    for session in missing_set:
        clause1 = has_later and latest_observed is not None and latest_observed > session
        if not clause1:
            continue
        is_whole_session_miss = (
            session not in global_observed_sessions
            and run_observed_sessions is not None
            and session not in run_observed_sessions
        )
        skip_explained = (
            isinstance(ticker, str) and (ticker, session) in skip_index
        )
        if is_whole_session_miss or skip_explained:
            accepted.add(session)
    residual = missing_set - accepted
    return accepted, residual
```

Today clause-1 (`if not clause1: continue`, :1092-1093) gates BOTH clause-2a (`is_whole_session_miss`) and clause-2b (`skip_explained`). A delisted ticker's holes are TRAILING → clause-1 is false → 2b never fires → the holes COUNT → false-RED.

### 2.2 Restructured loop (the fix)

Evaluate clause-2b INDEPENDENT of clause-1; keep clause-2a clause-1-gated:

```python
    accepted: set[str] = set()
    has_later = bool(observed)
    latest_observed = max(observed) if observed else None
    for session in missing_set:
        # clause-2b (skip-warning-explained): DIRECT per-(ticker, session)
        # evidence of a benign no-bar (delisting / no-quote), legitimate whether
        # the hole is interior, leading, OR trailing -> evaluated INDEPENDENT of
        # clause-1. (19-A: a delisted ticker's holes are trailing, so clause-1 is
        # False and 2b must not be gated behind it.)
        skip_explained = (
            isinstance(ticker, str) and (ticker, session) in skip_index
        )
        if skip_explained:
            accepted.add(session)
            continue
        # clause-2a (whole-session missed run) STAYS clause-1-gated: a trailing
        # whole-session miss (no later observation) is a real drumbeat-behind
        # failure and must stay COUNTED (RED). clause1 = the drumbeat moved PAST
        # this hole (a later session for THIS detection is observed).
        clause1 = has_later and latest_observed is not None and latest_observed > session
        if not clause1:
            continue
        is_whole_session_miss = (
            session not in global_observed_sessions
            and run_observed_sessions is not None
            and session not in run_observed_sessions
        )
        if is_whole_session_miss:
            accepted.add(session)
    residual = missing_set - accepted
    return accepted, residual
```

**Behavioral delta:** a session is now accepted iff `skip_explained` OR (`clause1` AND `is_whole_session_miss`). Previously: `clause1` AND (`is_whole_session_miss` OR `skip_explained`). The ONLY changed outcomes are sessions where `skip_explained` is true AND `clause1` is false (trailing / never-observed skip-explained holes) — precisely the delisting class. Every other quadrant is unchanged (see §2.4 truth table).

### 2.3 Documentation updates (SAME change — brief §2)

The current comments document the OLD contract. Update all four in the same commit:

1. **Module comment block (:894-916)** — the acceptance formula. Currently frames BOTH 2a and 2b under "a HISTORICAL hole the drumbeat has provably moved PAST -- a later session for THAT detection IS observed -- when it is benign-explained" (:897-899) and the 2b bullet (:908-910). **Becomes:** clause-2b (a per-(ticker, session) `pattern_observe` skip-warning) is accepted whether the hole is interior, leading, OR trailing — it is DIRECT evidence of a benign no-bar (e.g. a delisted/acquired ticker with no further bars); only clause-2a (whole-session missed run) requires the drumbeat to have provably moved PAST the hole. Add a one-line note that the trailing-skip-explained case is the 19-A delisting fix.

2. **`_calibration_c_partition` docstring (:1071-1086)** — currently: "A session S in `missing_set` is ACCEPTED iff clause1 AND clause2" with clause1's "a TRAILING hole has no later observation and is never accepted here; a never-observed detection has empty observed -> clause1 False for every S" (:1074-1077). **Becomes:** ACCEPTED iff `skip_explained` (clause-2b, INDEPENDENT of clause1) OR (`clause1` AND `is_whole_session_miss` (clause-2a)). Rewrite the clause1 parenthetical: clause1 still gates ONLY clause-2a; a trailing OR never-observed hole is accepted when (and only when) it is skip-warning-explained; a trailing whole-session miss with NO skip-warning stays counted.

3. **Never-observed (zero-obs) call-site comment (:1275-1279)** — currently: "observed is EMPTY -> clause-1 is FALSE for every session -> nothing accepted -> residual == expected". **Becomes:** observed is EMPTY → clause-1 is false for every session, so clause-2a accepts nothing, BUT clause-2b can still fire per-session (a never-observed detection whose expected sessions are skip-warning-explained — the immediate-delisting-after-detection case, consequence #2). Residual == expected only when NO expected session is skip-explained.

4. **Observed-arm call-site comment (:1315-1322)** — currently: "accept interior holes the drumbeat moved past that are whole-session-missed-runs or skip-warning-explained". **Becomes:** accept interior/leading holes the drumbeat moved past that are whole-session missed-runs (clause-2a, clause-1-gated) OR any skip-warning-explained hole (clause-2b, interior/leading/trailing). Keep the C-first-A-on-residual rationale intact (unchanged).

### 2.4 Quadrant truth table (proves the delta is confined)

For a session S in `missing_set`, `A = clause1`, `B = is_whole_session_miss`, `C = skip_explained`:

| A (clause1) | B (2a) | C (2b) | PRE accept | POST accept | changed? |
|---|---|---|---|---|---|
| T | T | T | yes (A∧(B∨C)) | yes (C) | no |
| T | T | F | yes | yes (A∧B) | no |
| T | F | T | yes | yes (C) | no |
| T | F | F | no | no | no |
| F | T | T | no (A false) | **yes (C)** | **YES** |
| F | T | F | no | no | no (2a stays gated) |
| F | F | T | no (A false) | **yes (C)** | **YES** |
| F | F | F | no | no | no |

Only the two `A=F, C=T` rows flip (trailing/never-observed AND skip-explained). The `A=F, B=T, C=F` row (trailing whole-session miss, no skip) stays `no` — this is the T3 over-eager-fix lock.

---

## 3. Task decomposition (TDD, red→green→commit)

Order: discriminating red→green tests first (T1, T5), then the locks (T2, T3), then the code+docs, then the full-suite regression gate (T4). Each test lands with its own commit; the production change lands as one commit that flips the red tests green.

> **Note on TDD sequencing.** T1 and T5 FAIL pre-fix and pass post-fix (true red→green discriminators). T2 and T3 pass under BOTH the pre-fix baseline AND the correct post-fix code — they are *mutation locks*: each is engineered to FAIL a specific WRONG implementation (a mutant), demonstrated by the pre/post arithmetic below. Because a lock cannot "fail first" against the pre-fix code, the executing implementer will (a) commit the lock tests and confirm green pre-fix, then (b) after the fix, transiently apply the named mutant locally to SEE each lock go red (proving it discriminates), revert the mutant, and confirm green. The mutant demonstration is a verification step, not a committed change.

### Task 1 — T1: trailing delisting (the fix) — RED→GREEN

**File:** `tests/monitoring/test_research_health_checks.py`. **Name:** `test_coverage_calib_c_trailing_delisting_skip_accepted`.

**Fixture (mirrors CNTA's real 2-session trailing shape):**
- One detection `CNTA`, `data_asof_date="2026-06-04"`, observed contiguously `06-05, 06-08, 06-09, 06-10` with `status="pending"` (NON-terminal → upper bound = `last_completed = 06-12`, so `06-11`/`06-12` are expected). Trailing holes: `06-11, 06-12`.
- Two `state='complete'` `_seed_pipeline_run` rows, `data_asof_date="2026-06-11"` and `"2026-06-12"`, **each carrying the emitter-shape skip-warning** `{"step": "pattern_observe", "ticker": "CNTA", "observation_date": <that session>, "reason": "no bar for observation_date"}` (satisfies the `observation_date == data_asof_date` index tie).

**Arithmetic (both paths):**
- `expected = {06-05,06-08,06-09,06-10,06-11,06-12}`; `observed = {06-05,06-08,06-09,06-10}`; `missing_set = {06-11, 06-12}`.
- For `06-11`/`06-12`: `clause1 = max(observed)=06-10 > 06-11 → False` (trailing); `skip_explained = True` (in skip_index); `is_whole_session_miss`: `06-11` IS in `run_observed_sessions` (a completed run named it) → run-half false → `is_whole_session_miss = False`.
- **PRE-fix:** `if not clause1: continue` → both counted. `residual = {06-11, 06-12}`. `_graced_missing_count({06-11,06-12}, expected)`: `len==2 > grace(1)` → 2. `total_missing = 2` → **YELLOW**.
- **POST-fix:** `skip_explained` accepts both (independent of clause1). `residual = {}`. `total_missing = 0` → **GREEN**, `accepted_historical == 2`.
- **Discriminates:** YELLOW/2 → GREEN/0.

**Assertions:** `check.status == "green"`; `"0 observation-coverage gap(s)" in check.summary` (with the `2 accepted historical (missed-run/skip)` note); `"CNTA".. det<id>` accepted-sample present in detail; `"accepted"` in detail.

**≥2-trailing honored:** 06-11 + 06-12 (a 1-session fixture would grace to 0 pre-fix and fail to discriminate).

**Commit:** `test(monitoring): 19-A T1 — trailing delisting skip-warning accept (red)`.

### Task 2 — T5: never-observed + fully-skip-explained (consequence #2) — RED→GREEN

**Name:** `test_coverage_calib_c_never_observed_fully_skip_explained_accepted`.

**Fixture (immediate-delisting-after-detection):**
- One detection `NEWCO`, `data_asof_date="2026-06-04"`, **ZERO observations** (mature, never observed).
- Expected window = `{06-05,08,09,10,11,12}` (6 sessions). For EACH, a `state='complete'` run with `data_asof_date == that session` carrying a `CNTA`-style skip-warning for `(NEWCO, that session)`.

**Arithmetic (both paths):**
- `observed = {}` → `has_later = False`, `latest_observed = None` → `clause1 = False` for every session.
- **PRE-fix:** `if not clause1: continue` → nothing accepted → `residual = expected` (6). `_graced_missing_count`: `missing != {max(expected)}` (6 sessions) → 6. `total_missing = 6` → **YELLOW** (1..10).
- **POST-fix:** each session `skip_explained = True` → all 6 accepted → `residual = {}` → `total_missing = 0` → **GREEN**, `accepted_historical == 6`.
- **Discriminates:** YELLOW/6 → GREEN/0. Also proves it is clause-2b (skip) doing the accept: `is_whole_session_miss` is False for every session (each is in `run_observed_sessions`), so a wrong "un-gate 2a only" fix would leave these counted.

**Assertions:** `check.status == "green"`; `"0 observation-coverage gap(s)" in check.summary`; `"6 accepted historical" in check.summary`; `det<NEWCO>` in accepted detail.

**≥2-trailing honored:** 6 expected sessions, all skip-explained (well past the lone-newest grace).

**Commit:** `test(monitoring): 19-A T5 — never-observed fully skip-explained accept (red)`.

### Task 3 — T2: trailing drumbeat-behind (safety lock) — GREEN both, catches the "accept-all-trailing" mutant

**Name:** `test_coverage_calib_c_trailing_drumbeat_behind_still_counted`.

**Fixture:**
- One detection `LAGG`, `data_asof_date="2026-06-04"`, observed `06-05,06-08,06-09,06-10` (`status="pending"`), trailing holes `06-11, 06-12`.
- `state='complete'` runs for the OBSERVED sessions ONLY (`06-05,06-08,06-09,06-10`) — **NO runs for 06-11/06-12** (the drumbeat fell behind) and **NO skip-warnings**.

**Arithmetic (both paths + mutant):**
- `missing_set = {06-11, 06-12}`. For each: `clause1 = False` (trailing); `skip_explained = False` (no warning); `is_whole_session_miss = True` (not in global, `run_observed` non-None `{06-05,08,09,10}`, not in run) but **gated by clause1**.
- **PRE-fix:** counted → `total_missing = 2` → **YELLOW**.
- **POST-fix (correct):** `skip_explained` false → fall through; `clause1` false → 2a gated → not accepted → counted → `total_missing = 2` → **YELLOW** (unchanged — safety lock holds).
- **"accept-all-trailing" mutant** (accept any hole with no later observation): would accept both → 0 → GREEN → **test FAILS**. Lock discriminates.

**Assertions:** `check.status == "yellow"`; `"2 observation-coverage gap(s)" in check.summary`; assert NO `"accepted historical"` note (nothing accepted).

**Commit:** `test(monitoring): 19-A T2 — trailing drumbeat-behind stays counted (lock)`.

### Task 4 — T3: clause-2a stays clause-1-gated (over-eager-fix lock) — direct unit test, catches the "un-gate both clauses" mutant

**Name:** `test_calibration_c_partition_trailing_whole_session_miss_stays_gated`. Direct unit test of `_calibration_c_partition` (mirrors the existing `test_coverage_calib_c_partition_none_ledger_blocks_2a`, :1365).

**Inputs (calendar-independent):**
```python
accepted, residual = _calibration_c_partition(
    missing_set={"2026-06-15"},
    observed={"2026-06-05"},                       # max < missing -> clause1 False
    ticker="X",
    global_observed_sessions={"2026-06-05"},       # 06-15 NOT observed anywhere
    run_observed_sessions={"2026-06-05"},          # non-None, WITHOUT 06-15
    skip_index=set(),                              # no skip-warning
)
```

**Arithmetic (both paths + mutant):**
- `06-15`: `clause1 = 06-05 > 06-15 → False`; `skip_explained = False`; `is_whole_session_miss = (06-15 not in global True) and (run not None) and (06-15 not in run True) = True`.
- **PRE-fix:** `if not clause1: continue` → `accepted == set()`.
- **POST-fix (correct):** 2b false → fall through; clause1 false → 2a gated → `accepted == set()`.
- **"un-gate both clauses" mutant** (move `is_whole_session_miss` check before the clause-1 gate): `is_whole_session_miss` true → `accepted == {"2026-06-15"}` → **test FAILS**. Lock discriminates.

**Assertions:** `accepted == set()`; `residual == {"2026-06-15"}`.

**Note on ≥2-trailing:** exempt — this is a UNIT test of the partition function (no `_graced_missing_count` grace in the path), so a single session is a valid discriminator here.

**Commit:** `test(monitoring): 19-A T3 — clause-2a stays clause-1-gated (lock)`.

### Task 5 — the fix: restructure `_calibration_c_partition` + the 4 doc updates — flips T1/T5 GREEN

Apply §2.2 loop restructure + §2.3 doc updates 1-4 in `swing/monitoring/research_health.py`. Run T1 + T5 → GREEN; run T2 + T3 → GREEN; run the mutant-demonstration (§3 note) for T2/T3 → each RED, then revert.

**Verify locks against mutants** (transient, not committed):
- Mutant M1 "accept-all-trailing" → T2 goes RED.
- Mutant M2 "un-gate both clauses" (move the `is_whole_session_miss` acceptance ahead of the clause-1 gate) → T3 goes RED (and T2 goes RED too — both catch it, honest overlap noted).

**Commit:** `fix(monitoring): 19-A — accept trailing skip-explained coverage holes (CALIBRATION C)`.

### Task 6 — T4: existing-suite regression gate (no new test)

Run the FULL fast suite BEFORE the Codex review (recipe §2): `python -m pytest -m "not slow" -q` from the worktree. Specifically confirm every existing `coverage_gaps` / CALIBRATION-C test is GREEN UNCHANGED — in particular:
- `test_coverage_calib_c_dino_skip_warning_accepted` (:1165) — the INTERIOR skip case: clause-1 TRUE, 2b TRUE under both old and new → still GREEN. **No edit.**
- `test_coverage_calib_c_trailing_lag_two_still_red` (:1113) — trailing-2, NO skip → 2b false → still RED. Unchanged.
- `test_coverage_calib_c_never_observed_still_red` (:1140) — never-observed, NO skip → 2b false → still RED. Unchanged.
- `test_coverage_calib_c_whole_missed_run_flips_red_to_green` (:1082), `_unexplained_interior_hole_still_red` (:1202), `_zero_obs_observe_failure_still_red` (:1231), `_hole_at_observed_session_no_run_row_still_red` (:1257), `_dropped_pipeline_runs_conservative_red` (:1345), `_partition_none_ledger_blocks_2a` (:1365), the `_observe_skip_index` unit tests (:1408-1455).

**Why they stay green (verified by the §2.4 truth table):** the only outcome delta is `A=F ∧ C=T`. No existing test has a trailing/never-observed hole WITH a matching skip-warning (the never-observed and trailing-lag tests deliberately seed NO skip-warnings; the DINO test is interior with `clause1=True`). So no existing assertion changes. This is a reasoning claim to be CONFIRMED by the actual green run — never asserted from analysis alone.

No commit (verification gate). If any existing test unexpectedly changes, STOP and report (do not edit an existing test to accommodate).

---

## 4. Three explicit semantic consequences (brief §2 — for RD's plan-stage review)

**This section is what RD reviews at the plan-stage gate. It is stated here explicitly, not buried.**

1. **Trailing skip-explained holes are now accepted (the intended fix).** A hole at a trailing session (no later observation for that detection) that carries a recorded `pattern_observe` skip-warning (`no bar for observation_date` / `non_finite_ohlc`) is now ACCEPTED (surfaced in the accepted-historical count/detail, does NOT drive RED). This is the CNTA-delisting cry-wolf class CALIBRATION C exists to kill. Locked by T1.

2. **A NEVER-observed detection whose expected sessions are FULLY skip-explained is now accepted.** Empty `observed` → clause-1 is false for every session, so clause-2a accepts nothing — but clause-2b can now fire per-session. The immediate-delisting-after-detection case (a ticker acquired/delisted right after it was detected, so it was never observed and every expected session has a no-bar skip-warning) flips from counted to accepted. **>>> This consequence needs RD's EXPLICIT bless. <<<** CHARC reads it as CORRECT (each hole is individually evidence-explained by a real recorded skip-warning tied to a completed run), but it is the sharpest semantic widening in this change and is why the plan-stage RD gate is REQUIRED before executing. Locked by T5.

3. **The clause-2b-trust caveat (RD's own).** A FALSE "no bar" skip-warning on a ticker that ACTUALLY HAS bars would now be masked as an accepted hole (previously a trailing such hole would have counted). This is an accepted low-probability observe-integrity concern — the observe step only emits `no bar for observation_date` when `_bar_for_date` genuinely returns no bar for that session — and is OUT OF SCOPE here (an observe-step integrity question, not a monitor question). No mitigation planned in 19-A.

**Not implemented (held for v2 if evidence demands, per brief):** RD's alternative — truncate a delisted detection's expected-session window at its last-bar session. Only ONE approach ships; this plan implements the clause-2b-un-gate, not the window-truncation.

---

## 5. Fixture discipline (brief §3 — the synthetic-vs-production-emitter gotcha family)

- **Emitter-shape fidelity:** every seeded skip-warning is exactly `{"step": "pattern_observe", "ticker": <ticker>, "observation_date": <session>, "reason": "no bar for observation_date"}` — verbatim the `runner.py:3078-3082` shape, cross-checked against the live run-116/117 CNTA rows. (The `non_finite_ohlc` reason is an accepted equivalent per `_OBSERVE_SKIP_REASONS`; T1/T5 use the delisting-canonical `no bar for observation_date`.)
- **The index tie (:940-994):** every skip-warning is seeded on a `state='complete'` `pipeline_runs` row whose `data_asof_date` EQUALS the warning's `observation_date`. A warning not satisfying that tie is DROPPED by `_observe_skip_index` → the fixture would silently test nothing. T1 seeds runs at 06-11/06-12 with matching-date warnings; T5 seeds a run per expected session with a matching-date warning. **Verified against the mechanism, not assumed.**
- **≥2 trailing sessions:** T1 (06-11+06-12), T2 (06-11+06-12), T5 (6 sessions). T3 is a direct partition unit test (grace not in path) → single session is a valid discriminator there.
- **Real repos / real schema:** fixtures use the existing `_seed_detection` (real `insert_detection_event`), `_seed_observation` (RAW insert — bypasses the 18-B.1 finiteness write-barrier so legacy/observed rows plant cleanly, the established monitor-test technique), `_seed_pipeline_run` (RAW insert, `warnings` → `warnings_json`). No new helper needed.

---

## 6. Gates + review (brief §5; recipe §2-§4)

1. **Full fast suite to GREEN before Codex** (recipe §2): `python -m pytest -m "not slow" -q` from the worktree — fix-to-green first so the review converges on a green diff.
2. **This is a WRITING-PLANS dispatch:** the plan is committed ONCE at Codex convergence (recipe §33). The Codex review at THIS stage is `review-fast` (a plan/doc review — a plan defect is caught downstream by the executing `review-strong` + the RD gate). Persist every round's verbatim response + adjudication to `.copowers-findings.md`; converge on `NO_NEW_CRITICAL_MAJOR`.
3. **Downstream (executing dispatch, NOT this plan):** `review-strong` + `codex-auto-review` on the production diff; merged-head no-false-green fast suite; ruff `ruff check swing/`; the binding **live-DB gate** (run the monitor against the live DB; `coverage_gaps` must flip GREEN with the CNTA holes 2b-accepted and T2-class behavior preserved); RD merge-blocking QA. **Plan-stage RD review is REQUIRED before executing** (consequence #2 needs an explicit bless) — the orchestrator posts the plan pointer to RD.

---

## 7. Acceptance criteria (executing dispatch will verify)

- `_calibration_c_partition` accepts a session iff `skip_explained` OR (`clause1` AND `is_whole_session_miss`); the `is_whole_session_miss` acceptance remains AFTER the `if not clause1: continue` gate.
- All 4 doc blocks (§2.3) updated in the same commit; no comment still claims trailing/never-observed is "never accepted".
- T1 + T5 GREEN post-fix, RED pre-fix. T2 + T3 GREEN, each demonstrably RED under its named mutant.
- Full fast suite green; every existing `coverage_gaps` test unchanged + green; `ruff check swing/` clean.
- No schema change, no new module/dep/carve-out, monitor still read-only.
- Commits conventional + trailer-free.
