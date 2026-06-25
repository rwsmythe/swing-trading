# Implementation plan — `coverage_gaps` current-vs-historical calibration (CALIBRATION C)

**Arc:** research-health monitor #3 (`_check_coverage_gaps`) current-vs-historical calibration.
**Brief:** `docs/coverage-gaps-calibration-commissioning-brief.md` (committed `c2d7b3ac`; RD-authored).
**Tripwire:** SUB-tripwire — a calibration WITHIN `_check_coverage_gaps` (read-only monitor; NO schema, NO new module, NO `swing/{trades,data}` carve-out, NO measurement-VALUE change). CHARC self-certs. Same class as the shipped 18-D FIX-1 / CALIBRATION-A / CALIBRATION-B.
**Worktree:** `.worktrees/coverage-gaps-calibration` (branched from `main` @ `4bf71c9a`).
**Sole production file touched:** `swing/monitoring/research_health.py` (`_check_coverage_gaps` + four new private helpers: `_observe_skip_index`, `_global_observed_sessions`, `_run_observed_sessions`, `_calibration_c_partition`). Tests in `tests/monitoring/test_research_health_checks.py`. Reads ONE additional existing table read-only: `pipeline_runs` (`warnings_json` + `data_asof_date`/`state`).

---

## §0 Live-DB grounding (read-only, captured 2026-06-24)

All numbers below were captured READ-ONLY from `%USERPROFILE%/swing-data/swing.db` (`mode=ro`). They are the REAL shapes the test fixtures MUST mirror (the verify-vs-live discipline; never premise-constructed).

### The live RED (brief §1, reproduced)
Running the LIVE `_check_coverage_gaps(conn, now=<Hawaii-naive wall clock>)` against the live DB returns:
```
status:  red
summary: 842 observation-coverage gap(s)
detail:  det1: 1 missing; det2: 1 missing; det3: 1 missing
```
`last_completed_session(now) == 2026-06-24`. `_COVERAGE_RED_GAPS = 10`, so 842 >> 10 → RED.

### Decomposition of the 842 gaps (the binding live shape)
Of 955 mature detections, the 842 raw missing-session hits decompose EXACTLY as:

| missing session | count | class |
|---|---|---|
| `2026-06-22` | **837** | WHOLE-SESSION miss (a missed manual run; ZERO observations exist anywhere for 06-22) |
| `2026-06-15` | **5** | PER-DETECTION skip (DINO detections 186–190; explained by a recorded `pattern_observe` skip-warning) |

- **never-observed mature detections: 0**
- **detections with a trailing-tail ≥ 2 lag: 0**
- ALL 842 gaps are INTERIOR — the latest expected sessions (06-23 = 837 obs, 06-24 = 945 obs) ARE observed → the drumbeat is healthy and has provably moved PAST both holes.

### Global per-session observation histogram (06-05 .. 06-24)
```
06-05:55  06-08:164  06-09:209  06-10:253  06-11:283  06-12:323
06-15:377  06-16:457  06-17:585  06-18:738  06-22:0(!)  06-23:837  06-24:945
```
06-19 (Juneteenth) + 06-20/06-21 (weekend) are correctly NOT NYSE sessions (no holiday bug). `2026-06-22` is the SOLE session in the window with ZERO observations — a missed RUN.

### The 06-22 whole-missed-run shape (BINDING test source)
- A whole-session miss has ZERO observations globally for that session. Detectable from `SELECT DISTINCT observation_date` alone — `2026-06-22 ∉ {observed sessions}`.
- It carries NO `pattern_observe` skip-warning (confirmed: zero `no bar` / `non_finite_ohlc` warnings name 06-22 — a missed RUN never reached the observe step).
- Representative detection 1 (BULZ, `data_asof_date=2026-06-04`): observed `06-05,06-08,06-09,06-10,06-11,06-12,06-15,06-16,06-17,06-18,06-23,06-24` — clean interior hole at 06-22; later sessions observed.

### The DINO no-bar shape (per-detection, skip-warning-explained)
- DINO detections 186–190 (`data_asof_date=2026-06-08`): observed `06-09,06-10,06-11,06-12,06-16,06-17,06-18,06-23,06-24` — interior hole at 06-15 (and at 06-22).
- `2026-06-15 ∈ {observed sessions}` (377 obs that session) — the run RAN; only DINO was per-ticker skipped.
- The skip is recorded: `pipeline_runs` row 104 (`action_session_date=2026-06-16`) `warnings_json` contains 5 entries `{"step":"pattern_observe","ticker":"DINO","observation_date":"2026-06-15","reason":"no bar for observation_date"}`.

### (b)-FEASIBILITY FINDING (the load-bearing answer)
**Discriminator (b) IS FEASIBLE.** All THREE signals it needs are queryable READ-ONLY from the same `mode=ro` connection:

1. **Whole-session miss** (the 06-22 class) — corroborated by BOTH the global-observation set AND the run ledger (MAJOR-R1-4 + MAJOR-R2-1), NOT inferred from either alone. A session `S` is a benign missed RUN iff **`S` has ZERO observations globally** (`S ∉ SELECT DISTINCT observation_date`) **AND NO completed `pipeline_runs` row has `data_asof_date == S`**. The observe step writes `observation_date = lease_data_asof(cfg, lease)` (`swing/pipeline/runner.py:2999`) — i.e. each run observes exactly the session named by its `data_asof_date`. Live-verified: run 111 `data_asof_date=2026-06-23` wrote 06-23; run 112 `data_asof_date=2026-06-24` wrote 06-24; and `2026-06-22 ∉ {completed-run data_asof_dates}` AND `2026-06-22` has zero observations — confirming a true whole-session missed run. The BOTH-signals AND closes both false-green directions: (i) a session a run NAMED but left zero rows (zero-obs observe failure) is caught by the run-ledger half (it stays RED); (ii) a session another detection WAS observed but lacking a run-ledger row is caught by the global-observation half.

2. **Per-detection skip-warning** (the DINO class) — the `pattern_observe` skip-warnings ARE persisted to **`pipeline_runs.warnings_json`** (a `TEXT` JSON column; `swing/data/migrations/0003_phase2_pipeline_trades.sql:142`), written at run completion (`swing/pipeline/runner.py:1075` — `json.dumps(run_warnings)`). Each entry is `{"step":"pattern_observe","ticker":<T>,"observation_date":<YYYY-MM-DD>,"reason":"no bar for observation_date"|"non_finite_ohlc"}` (runner.py:3081, :3098). The read-only check CAN `SELECT warnings_json FROM pipeline_runs`, parse, and index `(ticker, observation_date)`. Scan volume is trivial: 31 runs, ~42 KB total `warnings_json`.

3. **Run-observed-session set** (the MAJOR-R1-4 corroboration) — `SELECT DISTINCT data_asof_date FROM pipeline_runs WHERE state = 'complete'`. A session in this set HAD a completed run observe it. Used to distinguish a benign missed run (S NOT in the set) from a zero-obs observe failure (S IN the set but with zero observations). Same read-only `pipeline_runs` read as signal #2.

**The one (b) limitation to document (V1):** the skip-warning carries `(ticker, observation_date)`, NOT `detection_id`. Many tickers have many detections (AMN=50, FROG=40, ...). So an explained hole for `(ticker, S)` is attributed to EVERY detection of that ticker missing `S`. This is conservative TOWARD ACCEPT — a `(ticker, S)` skip-warning could accept a sibling detection's hole that was not literally the row the warning named. The exposure is bounded: a skip-warning means the *bar itself was unavailable for that ticker on that session*, which applies identically to every detection of that ticker (they all read the same per-ticker bar), so the coarse attribution is in fact semantically correct for the `no bar` / `non_finite_ohlc` classes (the bar is a per-ticker fact, not per-detection). We document it as a V1 note; no `detection_id` exists in the warning to do better, and adding one would touch the writer (out of scope). This does NOT weaken the still-RED locks (an UNEXPLAINED hole has no matching `(ticker, S)` warning at all).

---

## §1 Discriminator decision — (b)-variant, JUSTIFIED

**CHOSEN: discriminator (b) (RD's lean), implemented as the "interior + (whole-session OR skip-warning-explained)" accept rule.** Rationale weighed against the §3 locks:

- **(b) is feasible** (§0): both signals are queryable read-only. The feasibility blocker RD flagged (can the read-only check see the skip-warning?) is RESOLVED — they live in `pipeline_runs.warnings_json`.
- **(b) preserves the real-bug signal that (a) blinds.** (a) trailing-vs-interior accepts EVERY interior hole, including a genuine interior observe-step bug (the run ran, the bar existed, but the observe step dropped the row with no skip-warning). The §3 lock "(if b) an UNEXPLAINED per-detection interior hole → STILL RED" is satisfiable ONLY by (b). Picking (a) would forfeit that lock (documented as a limitation under (a) — but we are NOT forced to accept that loss because (b) is feasible).
- Both discriminators correctly accept the entire live 842 (837 whole-session + 5 explained DINO), so (b) is no worse than (a) on the live RED while strictly stronger on the unexplained-interior case.

### The accept rule (CALIBRATION C)
For each MATURE detection, after computing its `expected` session set and its `missing = expected - observed` set (unchanged from today), partition `missing` into ACCEPTED vs COUNTED:

A missing session `S` is **ACCEPTED** (surfaced in detail, does NOT drive red) iff BOTH:
1. **It is INTERIOR/leading for this detection** — there exists an observed session strictly AFTER `S` for this detection (`observed and max(observed) > S`). This proves the drumbeat moved PAST the hole. (A TRAILING hole — no later observation — is NEVER accepted by this clause; it falls through to the CALIBRATION-A trailing grace which forgives only a pure trailing-1 newest-session tail. A never-observed detection has empty `observed` → this clause is FALSE for every `S` → it accepts nothing.) **AND**
2. **It is benign-explained** by EITHER:
   - (2a) **whole-session missed RUN — requires BOTH signals (MAJOR-R2-1):** `S ∉ global_observed_sessions` (ZERO observations exist for `S` anywhere — the live §0 definition) **AND** `run_observed_sessions is not None AND S ∉ run_observed_sessions` (no completed run named `S`). `global_observed_sessions = {observation_date of pattern_forward_observations}`; `run_observed_sessions = {data_asof_date of completed pipeline_runs}` (or `None` when `pipeline_runs` is UNAVAILABLE / has zero completed runs — §2 helper #3). BOTH are required to close BOTH false-green directions: (i) without the run-ledger half, a run that ran for `S` but wrote zero rows (zero-obs observe failure) would be wrongly accepted (MAJOR-R1-4); (ii) without the global-observation half, an UNEXPLAINED per-detection hole at a session another detection WAS observed (so `S ∈ global_observed_sessions`) but which happens to lack a completed-run-ledger row would be wrongly accepted (MAJOR-R2-1 — the source shows no constraint guaranteeing every observed `observation_date` has a matching completed run row, so this is a real reachable vector, NOT schema-prevented). A true whole-session missed run has ZERO observations globally AND no completed-run ledger entry. When `run_observed_sessions is None` (degraded run-ledger), 2a is FALSE for every S — the conservative degrade that never false-greens; OR
   - (2b) **skip-warning-explained:** `(detection.ticker, S)` is present in the `pattern_observe` skip-warning index built from `pipeline_runs.warnings_json` (`reason ∈ {"no bar for observation_date","non_finite_ohlc"}`).

Otherwise `S` is **COUNTED** toward `total_missing` (the existing red/yellow thresholding is unchanged): this covers (i) any TRAILING hole beyond CALIBRATION-A's grace (clause 1 fails), (ii) an UNEXPLAINED interior hole — a completed run observed `S` (`S ∈ run_observed_sessions` so not 2a) AND no skip-warning names `(ticker,S)` (not 2b) — a real observe-step bug, and (iii) a zero-obs observe failure (a run named `S` but wrote zero rows: `S ∈ run_observed_sessions` so not 2a).

### Interaction with CALIBRATION A (trailing grace) — C-THEN-A ON THE RESIDUAL (MAJOR-R1-2 fix)
CALIBRATION A's CONSTANT + helper (`_COVERAGE_TRAILING_GRACE_SESSIONS=1`, the pure-trailing-1 newest-session-tail grace) is preserved UNCHANGED, but the ORDER vs CALIBRATION C is **C-FIRST, A-on-the-residual** — NOT A-then-C. Running A FIRST is WRONG: A graces only when `missing == {max(expected)}`; a detection with one accepted-historical interior hole PLUS the benign trailing-1 newest-session hole has `missing = {interior_S, newest_S}` (size 2, not `{max(expected)}`) → A returns `len=2`, then C removes only `interior_S`, leaving the benign trailing-1 wrongly COUNTED. So:
1. Compute `missing_set = expected - observed`.
2. **CALIBRATION C first:** compute `accepted = {S in missing_set : clause-1 AND clause-2}`; `residual = missing_set - accepted`.
3. **CALIBRATION A on the residual:** apply `_graced_missing_count(residual, expected)` (the trailing-1-newest grace) — so the benign pre-nightly trailing-1 tail is STILL graced after the historical holes are removed.
4. `counted = _graced_missing_count(residual, expected)`; add to `total_missing`; record `len(accepted)` + a sample for the detail.

This composition makes A + C truly independent filters and preserves BOTH grace guarantees:
- A trailing-≥2 lag: clause-1 fails for those trailing sessions (no later observation) → C does NOT accept them → they stay in `residual` → A graces only the single newest if it is alone (it is not, for a ≥2 tail) → COUNTED → RED preserved.
- A never-observed recent mature detection: empty `observed` → clause-1 vacuously false for every `S` → C accepts NOTHING → `residual == missing_set` → A graces only a lone-newest (a never-observed detection with >1 expected session is not lone-newest) → the existing never-observed COUNT + red threshold preserved.
- The benign 1-newest pre-nightly tail PLUS an accepted historical interior hole: C removes the historical hole → `residual = {newest_S}` → A graces it → 0 counted (correct).

### overall/envelope contract — UNCHANGED
`compute_research_health` still emits exactly one `coverage_gaps` check; `worst_of` unchanged; `write_research_health_artifact` value-shape unchanged. Only the `coverage_gaps` SEVERITY (and its summary/detail text) is recalibrated. No new check key, no schema, no measurement-value change.

---

## §2 Mechanics / where the code lands

All changes are inside `swing/monitoring/research_health.py`, additive to the `_check_coverage_gaps` neighborhood:

1. **A new module constant** documenting the accepted skip-warning reasons:
   ```python
   _OBSERVE_SKIP_REASONS = ("no bar for observation_date", "non_finite_ohlc")
   ```
   (grounded against runner.py:3081/:3098 — the exact persisted reason strings).

2. **A new private helper `_observe_skip_index(conn) -> set[tuple[str, str]]`** — `SELECT data_asof_date, warnings_json FROM pipeline_runs WHERE state = 'complete'` (MAJOR-R2-2: ONLY completed runs — a failed/non-complete/stale row's warnings must NOT explain a hole), parses each `warnings_json`, and returns the set of `(ticker, observation_date)` pairs whose `step=="pattern_observe"` AND `reason ∈ _OBSERVE_SKIP_REASONS` **AND `observation_date == that row's data_asof_date`** (MAJOR-R2-2: tie the skip-warning to the session the run actually observed — `warnings_json` is free text, so a date-mismatched warning attached to the wrong run must not explain a hole at an arbitrary session). DEFENSIVE (read-only monitor — the schema-boundary discipline applies): wrapped in the same `_schema_unavailable` degrade pattern; a missing `pipeline_runs` table → return an EMPTY set (degrades to "no explanations available" → unexplained holes COUNT, never crash, never false-green). A row with NULL/non-JSON/non-list/non-dict `warnings_json` is skipped gracefully (iterate only list-of-dict entries; ignore non-`pattern_observe` steps and non-`_OBSERVE_SKIP_REASONS` reasons; ignore entries missing/mismatched `ticker`/`observation_date`). NOTE per the recipe's schema-boundary adjudication: `pipeline_runs` is a real table written by the runner; we do NOT add per-value-shape branches beyond a general parse-guard.

2b. **A new private helper `_global_observed_sessions(conn) -> set[str]`** — `SELECT DISTINCT observation_date FROM pattern_forward_observations` (the set of sessions that have AT LEAST ONE observation anywhere). Used as the FIRST half of the whole-session-miss AND (MAJOR-R2-1): a benign whole-session miss requires `S ∉ global_observed_sessions` (zero observations exist) on top of `S ∉ run_observed_sessions`. The parent already opened the observations table successfully (its own `_schema_unavailable` guard precedes this), so this read is inside the existing try; on an empty table → empty set (no session has observations → every session is "globally unobserved", which only matters when paired with the run-ledger half, so it never accepts on its own).

3. **A new private helper `_run_observed_sessions(conn) -> set[str] | None`** — `SELECT DISTINCT data_asof_date FROM pipeline_runs WHERE state = 'complete'` (the set of sessions a COMPLETED run actually observed; the observe step writes `observation_date == data_asof_date`, runner.py:2999). This is the AUTHORITATIVE missed-run signal (MAJOR-R1-4): a benign whole-session miss is `S NOT IN` this set. **Returns `None` (NOT an empty set) when the `pipeline_runs` table is UNAVAILABLE (`_schema_unavailable`) OR when there are zero completed runs** — the CONSERVATIVE-DEGRADE sentinel: with no proven run ledger, clause 2a is treated as FALSE for every S (a missed run cannot be proven, so an interior hole must be skip-warning-explained or it COUNTS). Returning an empty set instead would make `S ∉ {}` TRUE for every S → accept-everything FALSE-GREEN (the Task 6 trap). NOTE (MAJOR-R1-4 / MINOR-R1-6): this is DELIBERATELY NOT the weaker `SELECT DISTINCT observation_date FROM pattern_forward_observations`. The weaker predicate would false-green a genuine zero-observation observe failure (a run that ran for `S` but wrote zero rows) the moment any later session is observed. Keying the missed-run test on the RUN LEDGER (`data_asof_date` of completed runs), not on the presence of observations, closes that false-green.

4. **A new private classification helper `_calibration_c_partition(missing_set, observed, ticker, global_observed_sessions, run_observed_sessions, skip_index) -> tuple[set[str], set[str]]`** (or inline within the per-detection loop — implementer's call at execute time; a helper is cleaner + unit-testable). Given a detection's `missing_set = expected - observed`, its `observed` dates, its `ticker`, the global `global_observed_sessions` (`set[str]`), the global `run_observed_sessions` (`set[str]` or `None`), and the `skip_index`, return `(accepted, residual)` where a session `S in missing_set` is **accepted** iff `clause1 AND clause2` with:
   - `clause1 = bool(observed) and max(observed) > S` (interior/leading — drumbeat moved past); and
   - `clause2 = is_whole_session_miss OR ((ticker, S) in skip_index)` where `is_whole_session_miss = (S not in global_observed_sessions) and (run_observed_sessions is not None) and (S not in run_observed_sessions)` (MAJOR-R2-1: BOTH the zero-global-observations AND the no-completed-run-ledger conditions).

   `residual = missing_set - accepted`. The caller then applies `_graced_missing_count(residual, expected)` (CALIBRATION A on the residual) to get the COUNTED count, and uses `accepted` for the detail audit. (The `run_observed_sessions is not None` guard is the conservative-degrade from §2 helper #3 — a degraded run-ledger never accepts a missed-run hole.)

5. **`_check_coverage_gaps` edits:**
   - **Add `d.ticker` to the SELECT and preserve it per-detection (MAJOR-R1-1).** The current SELECT (`d.detection_id, d.data_asof_date, o.observation_date, o.status, o.observation_id`) does NOT carry `ticker`; without it the `(ticker, S)` skip-warning join is impossible. Add `d.ticker` to the column list and store it in `per_det[det_id]["ticker"]` (set when the detection row is first seen; `ticker` is a NOT NULL column on `pattern_detection_events`, but defensively treat a non-str ticker as never-matching the skip index — it simply fails the 2b lookup and the hole COUNTS).
   - Compute `global_observed_sessions = _global_observed_sessions(conn)`, `run_observed_sessions = _run_observed_sessions(conn)`, and `skip_index = _observe_skip_index(conn)` ONCE, before the per-detection loop (not per detection — they are global).
   - In BOTH the `if not observed:` (never-observed) arm AND the normal arm, compute `missing_set = expected - observed`, then run **CALIBRATION C first** (`_calibration_c_partition` → `accepted, residual`), then **CALIBRATION A on the residual** (`counted = _graced_missing_count(residual, expected)`). Add `counted` to `total_missing`; add `len(accepted)` to a running `accepted_historical` counter and a sample to `accepted_sample`.
     - For the never-observed arm specifically: `observed` is empty → C's clause-1 is FALSE for every S → `accepted` is empty → `residual == missing_set` → A graces only a lone-newest → the never-observed count is preserved (the still-RED lock).
   - Maintain a running `accepted_historical` count + `accepted_sample` list (mirror the #1 check's `accepted_historical` + `accepted_note` pattern) and FOLD it into the detail in EVERY return path INCLUDING the early `if malformed:` branch (MINOR-R1-5: the malformed branch must also surface the accepted-historical note so a mixed malformed+accepted case never silently hides the accepted gaps; the existing malformed branch's `worst_of([gap_status, "yellow"])` severity is unchanged).
   - The red/yellow thresholding on `total_missing` is UNCHANGED. The summary gains an accepted-count note (e.g. `"N observation-coverage gap(s); M accepted historical (missed-run/skip)"`), and the detail lists a sample of accepted gaps (count + sample) per the §3 auditability lock + #27. The accepted-sample MUST be order-stable enough to assert in a test (e.g. sort the accepted samples, or build them in detection-id order) so the auditability assertions are not flaky (the detail-cap-at-3 must not drop the asserted entry — see Task 5).

6. **A `CALIBRATION C` comment block** in `_check_coverage_gaps`, mirroring the CALIBRATION-A/B comment style + the §6.7 citation form (`CALIBRATION C (coverage-gaps current-vs-historical, brief §1/§2; watch-standard §3.1): ...`). Plus a short note for RD to fold into watch-standard §3.1 (delivered in the return report, not committed code).

ASCII-only in all added strings (the cp1252 gotcha — no em-dash/section-glyph/arrow in any summary/detail). `ruff check swing/` must stay clean.

---

## §3 TDD task sequence (red → green → commit)

Each task: write the failing test, SEE it fail the RIGHT way, minimal impl, SEE green, commit. Conventional commit messages carrying the task id. Run the FULL fast suite to green BEFORE the Codex review (recipe §2). Fixtures are built from the §0 live shapes (real-derived). The existing `_seed_detection` / `_seed_observation` (RAW-insert) helpers are reused; a new `_seed_pipeline_run_warnings` test helper is added for the skip-warning index.

The frozen clock for the new tests mirrors the live shape on a SMALL synthetic calendar. Use the existing module clock pattern but extend it so the calendar has a clean INTERIOR missed session with LATER observed sessions. Reuse `_NOW = datetime(2026, 6, 14, 12, 0, 0)` (Sun → `last_completed_session == 2026-06-12`) where a window inside 06-05..06-12 suffices; the interior missed session is e.g. `2026-06-10` with later sessions `06-11, 06-12` observed.

### Test helper (added in Task 0)
The helper takes an EXPLICIT `data_asof_date` (MINOR-R2 — the run-ledger predicate keys on `data_asof_date`, so tests must state it directly rather than aliasing it to `action_session_date`), plus a `state` so the non-complete-run-ignored unit test can seed a `state='failed'` row, and optional `warnings`.
```python
def _seed_pipeline_run(conn, *, data_asof_date: str,
                       action_session_date: str | None = None,
                       state: str = "complete",
                       warnings: list[dict] | None = None,
                       lease_token: str = "tok-test") -> None:
    # RAW insert a pipeline_runs row. Required NOT NULL cols: started_ts,
    # trigger(scheduled|manual), data_asof_date, action_session_date,
    # state(CHECK in running/complete/failed/blocked/force_cleared), lease_token.
    # lease_token must be UNIQUE across seeded rows (the partial unique index is on
    # state='running' only, but distinct tokens avoid any collision) -- pass a
    # distinct token per row when seeding several.
    asd = action_session_date or data_asof_date
    wj = json.dumps(warnings) if warnings is not None else None
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date,"
        " action_session_date, state, lease_token, warnings_json)"
        " VALUES (?, 'manual', ?, ?, ?, ?, ?)",
        ("2026-06-12T20:00:00", data_asof_date, asd, state, lease_token, wj))
    conn.commit()
```
References to `_seed_pipeline_run_warnings` in the tasks below mean this helper (seed a completed run for a session, optionally with `warnings`). Seed a DISTINCT `lease_token` per row.

### Task 1 — BINDING: the 06-22 whole-missed-run shape flips RED → green/accepted
**File:** `tests/monitoring/test_research_health_checks.py`.
**Fixture (real-derived from the 06-22 shape):** seed ENOUGH mature detections (each ticker distinct, e.g. `T000..T014`) each observed on every NYSE session in 06-05..06-12 EXCEPT a single interior session `2026-06-10`, which has ZERO observations across ALL of them (the whole-session miss), with `06-11` and `06-12` observed (the drumbeat moved past). Seed > `_COVERAGE_RED_GAPS` (=10) such detections so the PRE-fix path crosses the red threshold. **Seed completed `pipeline_runs` rows for the OBSERVED sessions but NOT for 06-10** — i.e. `_seed_pipeline_run_warnings(... data_asof_date in {06-05,06-08,06-09,06-11,06-12} ...)` (no warnings needed; the row's `data_asof_date` is what `_run_observed_sessions` reads) and crucially NO completed run with `data_asof_date=2026-06-10` (the missed run). NO `pipeline_runs` skip-warning for 06-10 (a missed run leaves no skip-warning). This MIRRORS the live shape: 06-22 ∉ completed-run data_asof_dates.
**Pre-fix arithmetic:** each of the 15 detections has 1 missing interior session (06-10) → `total_missing = 15`. 15 > 10 → `status == "red"`. (Matches the live 837 → RED mechanism at small scale.)
**Post-fix arithmetic:** 06-10 ∉ `run_observed_sessions` (no completed run named it) AND each detection has a later observed session (06-11/06-12) → clause 1 + clause 2a satisfied → all 15 ACCEPTED → `total_missing = 0` → `status == "green"`.
**Assertions:** the committed test asserts `check.status == "green"` and FAILS on current code (red) → PASSES post-fix. This is the binding test; document the pre/post arithmetic in the test docstring. NOTE: a helper that seeds the run rows is needed; extend `_seed_pipeline_run_warnings` to seed a bare completed run with no warnings (pass `warnings=[]` → `warnings_json` is `"[]"` or NULL — either is fine for `_run_observed_sessions`, which reads `data_asof_date`, not `warnings_json`).

### Task 2a — STILL-RED: trailing-lag ≥ 2 (drumbeat behind) → RED (ISOLATED)
**Fixture (MAJOR-R1-3 — isolated, exact count):** ONE mature detection observed contiguously through `2026-06-08` then STOPPING (status `triggered_open`) → expected window 06-05..06-12; observed 06-05,06-08 (06-06/07 weekend); missing `06-09,06-10,06-11,06-12` = a trailing tail of length 4 (no later observation). Seed completed `pipeline_runs` rows for ALL sessions 06-05..06-12 (so the missed sessions are NOT whole-session-miss-accepted — the run RAN, the detection simply stopped being observed = a real lag). To make the RED unambiguous seed enough such detections (e.g. 4 detections × trailing-4 = 16 > 10) OR assert the exact `total_missing` in the summary. Choose: 4 detections, exact `total_missing == 16`.
**Pre-fix arithmetic:** 4 detections × 4 trailing missing = 16 → RED.
**Post-fix arithmetic:** each trailing session has NO later observation → clause-1 fails → C accepts nothing → residual == missing → A graces only a lone-newest (a 4-tail is not lone-newest) → `counted == 4` per detection → `total_missing == 16` → still RED.
**Assertion:** `check.status == "red"` BOTH pre AND post AND the summary's gap count is `16` (exact-count negative control — an over-broad impl that wrongly accepted the trailing sessions would drop the count below 16 and FAIL).

### Task 2b — STILL-RED: recent never-observed mature detection → RED (ISOLATED)
**Fixture (MAJOR-R1-3 — isolated):** ONE mature detection (`data_asof_date=2026-05-01`) with ZERO observation rows (never observed). Seed completed `pipeline_runs` rows for the expected sessions (05-04..06-12) so they are not whole-session-miss-accepted. Its expected window 05-04..06-12 has > 10 sessions all missing.
**Pre-fix arithmetic:** never-observed = all expected sessions (> 10) missing → RED.
**Post-fix arithmetic:** empty `observed` → C's clause-1 vacuously false for every S → `accepted` empty → residual == missing → A graces only a lone-newest (not lone here) → `counted == len(expected) > 10` → still RED.
**Assertion:** `check.status == "red"` BOTH pre AND post AND the summary names the never-observed count (assert `total_missing` equals the exact expected-session count). An over-broad impl that wrongly accepted the never-observed sessions would turn this green → FAILS.

### Task 3 — DINO no-bar: per-detection skip-warning-explained interior hole → accepted
**Fixture (real-derived from the DINO shape):** one mature detection ticker `DINO`, observed on 06-05,06-08,06-09 then MISSING 06-10 then observed 06-11,06-12 (an INTERIOR hole at 06-10 with later observation). 06-10 HAS observations from a sibling ticker `OTH` (seed `OTH` observed on 06-10) AND seed a completed `pipeline_runs` row with `data_asof_date=2026-06-10` so `06-10 ∈ run_observed_sessions` (the run RAN — NOT a whole-session miss). Seed that run's `warnings_json` = `[{"step":"pattern_observe","ticker":"DINO","observation_date":"2026-06-10","reason":"no bar for observation_date"}]` (so `(DINO, 06-10) ∈ skip_index`). NOTE: `OTH` must ALSO be observed contiguously (06-05..06-12 minus its own holes) so OTH itself contributes 0 gaps and does not muddy the count.
**Pre-fix arithmetic:** DINO has 1 interior missing (06-10) → `total_missing == 1` → `status == "yellow"` (>= `_COVERAGE_YELLOW_GAPS=1`).
**Post-fix arithmetic:** 06-10 ∈ run_observed_sessions (run named it) so NOT 2a; BUT `(DINO, 2026-06-10) ∈ skip_index` AND clause-1 (06-11/06-12 observed later) → 2b accepted → DINO's hole removed → `total_missing == 0` → `status == "green"`.
**Assertion:** `check.status == "green"` (FAILS pre-fix = yellow; PASSES post-fix). Also assert the accepted DINO gap is named in the detail (the #27 audit).

### Task 4 — (b)-DISTINGUISHER: UNEXPLAINED interior hole (run ran, no skip-warning) → STILL RED
**Fixture:** identical to Task 3 BUT with NO `pattern_observe` skip-warning for `(ticker, 2026-06-10)`. Seed 15 distinct tickers each observed 06-05,06-08,06-09 then MISSING 06-10 then observed 06-11,06-12, with a SIBLING `OTH` observed on 06-10 AND a completed `pipeline_runs` row `data_asof_date=2026-06-10` (so the run RAN — `06-10 ∈ run_observed_sessions`) but the run's `warnings_json` does NOT name any of the 15 tickers at 06-10 (the rows were dropped with no recorded skip = a real observe-step bug).
**Pre-fix arithmetic:** 15 unexplained interior holes → `total_missing == 15` → RED.
**Post-fix arithmetic:** 06-10 ∈ run_observed_sessions (run named it) so NOT 2a; NO skip-warning names `(ticker,06-10)` so NOT 2b → clause 2 fails → NOT accepted → `total_missing == 15` → still RED.
**Assertion:** `check.status == "red"` BOTH pre AND post AND the summary gap count is `15` (exact-count). This is the test that DISTINGUISHES (b) from (a): under (a) (accept-all-interior) these 15 would turn GREEN; under (b) they stay RED. The test FAILS an (a)-style impl (which would drop the count below 15 / flip to green) and PASSES the (b) impl.

### Task 4b — FALSE-GREEN GUARD: zero-observation observe FAILURE (run ran for S, wrote zero rows) → STILL RED (MAJOR-R1-4)
**Fixture:** seed > 10 mature detections each observed on 06-05,06-08,06-09 then MISSING 06-10 then observed 06-11,06-12 — BUT with NO sibling observed 06-10 (so `06-10 ∉ global_observed_sessions`, ZERO observations exist for 06-10) WHILE a completed `pipeline_runs` row HAS `data_asof_date=2026-06-10` (the run RAN for 06-10 but produced zero observation rows = an observe-step failure). NO skip-warning for any `(ticker, 06-10)`.
**Pre-fix arithmetic:** each detection has 1 missing interior 06-10 → `total_missing > 10` → RED.
**Post-fix arithmetic:** `is_whole_session_miss` requires `06-10 ∉ run_observed_sessions`, but `06-10 ∈ run_observed_sessions` (a completed run named it) → 2a FALSE; no skip-warning → 2b FALSE → NOT accepted → still RED. (Under the WEAKER `S ∉ observation_dates`-only predicate this would FALSE-GREEN.)
**Assertion:** `check.status == "red"` BOTH pre AND post. This is the FALSE-GREEN GUARD distinguishing the run-ledger half from a bare zero-observations predicate (MAJOR-R1-4). An impl that omitted the run-ledger condition would FALSE-GREEN here → FAILS.

### Task 4c — FALSE-GREEN GUARD: hole at a session another detection WAS observed, but no run-ledger row → STILL RED (MAJOR-R2-1)
**Fixture:** seed > 10 mature detections each observed on 06-05,06-08,06-09 then MISSING 06-10 then observed 06-11,06-12, with a SIBLING `OTH` OBSERVED on 06-10 (so `06-10 ∈ global_observed_sessions` — the session is NOT globally unobserved) BUT NO completed `pipeline_runs` row with `data_asof_date=2026-06-10` (the run ledger lacks 06-10) AND no skip-warning. **IMPORTANT (MINOR-R3): seed completed `pipeline_runs` rows for the OTHER observed sessions (06-05,06-08,06-09,06-11,06-12) — omit ONLY 06-10 — so `_run_observed_sessions` is a NON-empty set (not `None`).** Otherwise an empty completed-run ledger → `_run_observed_sessions` returns `None` → 2a never applies for ANY session → the test would pass even against a (wrong) run-ledger-ALONE impl, defeating its purpose. This is the MAJOR-R2-1 quadrant: a session that HAS observations (so not a whole-session miss) yet happens to lack a run-ledger entry.
**Pre-fix arithmetic:** > 10 unexplained interior holes → RED.
**Post-fix arithmetic:** `is_whole_session_miss` requires BOTH `06-10 ∉ global_observed_sessions` (FALSE — OTH observed it) AND `06-10 ∉ run_observed_sessions` → 2a FALSE (the global-observations half fails); no skip-warning → 2b FALSE → NOT accepted → still RED.
**Assertion:** `check.status == "red"` BOTH pre AND post. An impl that keyed 2a on the RUN LEDGER ALONE (run-ledger-absence sufficient, without the zero-global-observations AND) would FALSE-GREEN here → FAILS. This is the test that forces the BOTH-signals AND (MAJOR-R2-1).

### Task 5 — DETAIL auditability (#27): accepted gaps surface in the check detail
**Fixture:** the Task 1 whole-missed-run fixture (15 detections, interior 06-10 missed-run, accepted).
**Assertion:** post-fix, `check.status == "green"` AND the accepted count appears in the summary (assert the literal accepted count, e.g. `"15 accepted"`) AND the detail names a sample of the accepted gaps (at least one `detNNN`/session reference). The accepted-sample must be order-stable (see §2.5: sort or detection-id order) so the assertion is not flaky against the detail-cap-at-3. Asserts the accepted gaps are NEVER silently dropped (the §3 auditability lock + the #27 silent-skip discipline). Reason both paths in the docstring (pre-fix: red, detail lists counted gaps; post-fix: green, summary+detail list accepted gaps).

### Task 5b — auditability in the MALFORMED branch (MINOR-R1-5)
**Fixture:** the Task 1 accepted-missed-run fixture PLUS one detection with a malformed `data_asof_date` (raw insert, mirroring the existing `test_coverage_yellow_on_malformed_date_does_not_crash`).
**Assertion:** post-fix the early `if malformed:` return path STILL includes the accepted-historical note in its summary/detail (the accepted count is not silently hidden when malformed rows coexist) AND its severity is `worst_of([gap_status, "yellow"])` (unchanged). Reason: pre-fix the malformed branch has no accepted note; post-fix it carries it.

### Task 6 — degradation: missing `pipeline_runs` table → no crash, unexplained holes COUNT
**Fixture (MINOR-R3 — exercise the None-trap):** use the **Task 4b ZERO-GLOBAL-observation shape** (> 10 detections missing 06-10, NO sibling observed 06-10 → `06-10 ∉ global_observed_sessions`) and DROP the `pipeline_runs` table (`conn.execute("DROP TABLE pipeline_runs")`) before the check. This is the shape that ACTUALLY exercises the `_run_observed_sessions is None` conservative-degrade: with `06-10 ∉ global_observed_sessions`, a BAD `None → empty-set` degrade would make 2a's run-ledger half (`06-10 ∉ {}`) TRUE and — combined with the now-true global-observations half — ACCEPT every hole → FALSE-GREEN. The correct `None` sentinel keeps 2a FALSE → still RED. (The Task-4 OTH-observed-06-10 shape would NOT exercise this, since `06-10 ∈ global_observed_sessions` blocks 2a regardless.) The two `pipeline_runs`-reading helpers degrade with DIFFERENT sentinels (MINOR-R2 wording): `_observe_skip_index` → EMPTY SET (nothing is skip-explained); `_run_observed_sessions` → `None` (the run-ledger is unknown). `_global_observed_sessions` reads the still-present observations table normally. ALSO add a direct unit: `_calibration_c_partition(missing_set={"2026-06-10"}, observed={"2026-06-11"}, ticker="X", global_observed_sessions=set(), run_observed_sessions=None, skip_index=set())` returns `accepted == set()` (the None sentinel blocks 2a even with zero global observations).
**CRITICAL degradation-semantics note:** if `_run_observed_sessions` returned an EMPTY SET, `S ∉ {}` would be TRUE for EVERY S → clause-2a's run-ledger half would be satisfied for every session → combined with the global-observations half this could accept interior holes that should count. The conservative-degrade is the `None` sentinel: `run_observed_sessions is None` → 2a is FALSE for every S (a missed run cannot be proven), so every interior hole must be skip-warning-explained or it COUNTS. A present-but-empty `pipeline_runs` (no completed runs) ALSO returns `None` (same conservative treatment). This is the load-bearing conservative-degrade decision — TEST it.
**Assertion:** `check.status == "red"` (the unexplained holes still count; degraded run-ledger → NOTHING is missed-run-accepted → conservative, never false-green). Plus a variant: a present `pipeline_runs` with a NULL / non-JSON / non-list `warnings_json` row is skipped gracefully by `_observe_skip_index` (no crash).

### Task 7 (unit) — direct unit tests of the three new helpers
Small direct tests:
- `_observe_skip_index`: returns exactly the `(ticker, observation_date)` pairs for `state='complete'` runs whose `pattern_observe` warning's `reason ∈ _OBSERVE_SKIP_REASONS` AND `observation_date == that row's data_asof_date`. MUST assert it IGNORES: (i) a warning on a NON-complete run (MAJOR-R2-2); (ii) a date-MISMATCHED warning (`observation_date != data_asof_date`, MAJOR-R2-2); (iii) other steps/reasons; (iv) NULL/non-JSON/non-list `warnings_json`.
- `_run_observed_sessions`: returns the `data_asof_date` set of `state='complete'` runs ONLY (a non-complete run's `data_asof_date` is EXCLUDED), and returns `None` on a missing table AND on zero completed runs.
- `_global_observed_sessions`: returns the global DISTINCT `observation_date` set.
Keeps the helpers independently anchored.

### Final task — full fast suite to green + the CALIBRATION C comment + RD note
Run `python -m pytest -m "not slow" -q` (the WHOLE fast suite) — fix any cross-cutting break to green BEFORE the Codex review. Confirm the existing coverage_gaps tests (the §0 test list: contiguous-green, one-hole-yellow, many-holes-red, missing-tail, leading-gap, never-observed, malformed-date, terminal-stopped) all STILL pass unchanged — the recalibration must not regress the genuine-failure detections (none of those fixtures involve a whole-session miss or a recorded skip-warning, so CALIBRATION C accepts nothing in them and they are byte-unchanged in severity). Add the `CALIBRATION C` comment block. Verify `ruff check swing/` clean.

---

## §4 Self-certification (against the §3 locks)

- **STILL reds on a genuine CURRENT/ongoing failure** (trailing lag ≥2 → RED; recent never-observed mature detection → RED): Task 2a + Task 2b (ISOLATED, exact-count) — red both pre and post.
- **The 06-22 whole-missed-run class flips RED → green/accepted** (THE BINDING live-DB test): Task 1 — green post-fix on the real-derived shape (keyed on the run ledger).
- **The DINO no-bar class → accepted**: Task 3 — green post-fix; skip-warning-explained.
- **An UNEXPLAINED per-detection interior hole → STILL RED** (distinguishes (b) from (a)): Task 4 — red both pre and post (exact count 15); an (a)-impl FAILS it.
- **A zero-observation observe FAILURE (run ran for S, wrote zero rows) → STILL RED** (MAJOR-R1-4 false-green guard): Task 4b — red both pre and post; a run-ledger-omitting impl FAILS it.
- **A hole at a session another detection WAS observed but lacking a run-ledger row → STILL RED** (MAJOR-R2-1 false-green guard): Task 4c — red both pre and post; a run-ledger-ALONE impl FAILS it (forces the zero-global-observations AND no-run-ledger BOTH-signals AND).
- **Accepted historical gaps STILL surface in the check DETAIL (count + sample), never silently dropped (#27)** — including the malformed-branch return path: Task 5 + Task 5b.
- **The overall research-health VALUE/envelope contract is unchanged**: only `coverage_gaps` severity recalibrated; `compute_research_health` emits one `coverage_gaps` check; `worst_of`/`write_research_health_artifact` untouched. Verified by the unchanged aggregate/envelope tests staying green (final task).
- **NO schema / NO migration**: no `*.sql` added; `pipeline_runs.warnings_json` is read-only (existing column 0003).
- **NO new module**: additive helpers inside `swing/monitoring/research_health.py`.
- **NO new dependency**: stdlib `json` only (already imported).
- **NO `swing/{trades,data}` carve-out**: only `swing/monitoring/research_health.py` (the read-only monitor) is edited.
- **Read-only w.r.t. the DB**: only SELECTs; no INSERT/UPDATE/DELETE; the check signature `(conn, *, now)` is unchanged.
- **NO measurement-VALUE change**: the engine funnel / shadow-expectancy / observation values are untouched; this changes only a monitor SEVERITY mapping.
- **Real-derived tests**: all fixtures mirror the §0 live shapes (06-22 whole-session miss, DINO skip-warning, trailing/never-observed), not premise-constructed.
- **Calibration semantics documented IN the check** (`CALIBRATION C` comment) + handed to RD for watch-standard §3.1.

---

## §5 V1 limitations / notes for RD

- **Coarse `(ticker, observation_date)` skip-warning attribution** (§0): the warning has no `detection_id`, so an explained hole is attributed to every detection of that ticker missing that session. Argued semantically correct for `no bar` / `non_finite_ohlc` (the bar is a per-ticker fact). V2 (only if ever needed) would require the writer to stamp `detection_id` into the warning — out of scope (touches the runner write path).
- **Whole-session-miss is RUN-LEDGER-derived (MAJOR-R1-4), not observation-derived**: the benign missed-run signal is `S ∉ {data_asof_date of completed pipeline_runs}` — NOT the weaker `S ∉ observation_dates`. The observe step writes `observation_date == data_asof_date` (runner.py:2999), so a completed run's `data_asof_date` is exactly the session it observed. This closes the false-green where a run RAN for `S` but wrote zero observation rows (a genuine observe-step failure): the weaker observation-derived predicate would accept it once any later session is observed; the run-ledger predicate keeps it COUNTED (Task 4b). It correctly does NOT accept a session that HAS observations but is missing for one detection (that routes to the skip-warning/unexplained branch). The run-ledger read degrades CONSERVATIVELY: an unavailable/empty `pipeline_runs` → `None` → no hole is missed-run-accepted (never false-green; Task 6).
- **watch-standard §3.1 amendment** (RD to fold): "coverage_gaps reds ONLY on a CURRENT/ongoing coverage failure — a trailing lag beyond the pre-nightly grace, an UNEXPLAINED interior observe hole, or a zero-observation observe failure (a completed run named the session but wrote no observation for the detection). It ACCEPTS (surfaces in detail, does not red) historical holes the drumbeat has provably moved past (a later session for that detection IS observed): a WHOLE-SESSION MISSED RUN (no completed pipeline run observed that session — keyed on `pipeline_runs.data_asof_date`, not on the mere absence of observations) and a per-detection hole explained by a recorded `pattern_observe` skip-warning (`no bar for observation_date` / `non_finite_ohlc`)."
