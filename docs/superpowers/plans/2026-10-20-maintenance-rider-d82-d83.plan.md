# Maintenance rider (D82 invalid_ohlc to rates, shadow timeout 900 s, D83 warm cohort) -- implementation plan

**Ledger (rulings verbatim, intake corrections, review history):** `docs/superpowers/plans/2026-10-20-maintenance-rider-d82-d83.plan.ledger.md`. This plan cites ledger sections by name and restates none of their reasoning.
**Briefs:** `docs/maintenance-rider-d82-d83-plan-dispatch-brief.md` (@ `4d6cea42`) as superseded by `docs/maintenance-rider-d82-d83-plan-continuation-brief-cell2.md` (@ `033d1053`).
**Base:** `main` @ `033d1053`. Every file:line below was re-read at that commit.
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\plan\` (`round0\` = cell 1's m01-m12; `cell2-probes\` = this cell's p01-p03 and the F8 witness script w01).

## Header

### Declared envelope

**IN**
- `swing/monitoring/research_health.py`: the `invalid_ohlc` arm of `_check_excluded_reason_breakdown` (:976-1007), `_INVALID_OHLC_BASELINE_COUNT` and the CALIBRATION B block (:771-780), and the comment above `_EXCL_*` (:766-768, TEXT ONLY; the values stay).
- `swing/pipeline/runner.py`:
  - `SHADOW_EXPECTANCY_TIMEOUT_S` (:1124);
  - `_prewarm_evaluate_archives` (:1457-1521) and one new private helper `_open_detection_warm_tickers`;
  - the caller line in `_step_evaluate`'s `_pre_fetch_hook` (:1596-1600);
  - the three `window_days=400` sites (:2136, :2398, :3054), the two comments AT those sites (:2395, :3052), and one new module constant.
- `swing/latches/service.py:393-394`: the docstring parenthetical only (F14).
- `swing/config.py:284` (`ArchiveConfig.archive_history_days`): one documentation line naming its unit, no rename, no value change (orchestrator ruling on I-4; ledger "Rulings on I-4 / R1-01").
- `tests/latches/test_criteria_lapse.py:1136-1138`: the `_envelope_case` docstring parenthetical only (orchestrator ruling I-1, branch A; ledger "Intake I-1").
- Tests under `tests/` for all of the above.

**OUT**
- Any schema, migration or dependency. Anything under `swing/data/` or `swing/trades/`.
- Observe's logic (`_bar_for_date`'s behaviour, `resolve_ohlcv_window`), `observe_load`, `lease_data_asof`, `list_observable_detections`.
- `warm_archives_batch` internals, `_yf_download_window` (condition (vi)).
- `swing/pipeline/staleness.py`; the step budget; `stale_step_threshold_seconds`.
- The coverage-gaps check, its constants, calibrations and tests (RD: DEFERRED; ledger "RD rulings").
- The 10 / 25 rules for `insufficient_forward_depth` and `missing_observations`.
- Any standing process. D89 (the per-detection term).
- Owner docs (listed under "Owner docs", never edited here).


### Accepted limitations (each WITH its reason; challenge invited)

- **L-1, the warm is moot for observe while the Schwab ladder is ON.** With the ladder installed, observe's `get_or_fetch` reads through the ladder, not the archive (`ohlcv_cache.py:270-282`). Runs 191-194 had it off (the 401). CHARC P4 (ledger). The merge report states the ladder state per quoted night.
- **L-2, the warm alone does not bring a run-194-sized night under 900 s.** The per-detection term (~88.6 ms per iteration, m06) is untouched; it is D89 (CHARC F7).
- **L-3, no test can tell the integer comparison from an unrounded float comparison.** Measured: 0 mismatches between `count*20 <= u` / `count*10 > u` and `100.0*count/u <= 5.0` / `> 10.0` for every `u` in 1..5000 and `c` in 0..u (p03). The 77/1535 pin kills the ROUNDED-comparison class (RD's stated target), not a float comparison. The integer form is held by READ (executing review, RD's post-merge read).
- **L-4, the 2-dp display can show "5.00%" beside "yellow".** For a rate in (5.000%, 5.005%), possible only at `unique_signals >= 20,001` (e.g. 1001/20001). The band word is the authority. The comparison never reads the display.
- **L-5, the warm adds one selector call per night.** Measured on the live DB, `mode=ro`: 1,855 ms cold, 669-787 ms warm, returning 7,074 detections over 245 tickers for run 194's date (p02).
- **L-6, the open set grows with the Finviz widening (D84's rider).** Today it adds 212 tickers, about 3 chunks of 75 (m09). BANKED for the widening rider's plan to re-measure; owner orchestrator.

### Executing posture

- **Cell (recommendation; the orchestrator rules):** `implementer-sonnet-high`, the phase default. The reason an orchestrator might move it to `implementer-opus-high`: the warm feeds the archive that observe's measurement reads, and condition (v) is a measurement-neutrality obligation.
- **TDD per task:** RED, then GREEN, then a commit carrying the task id (`feat(...)` / `fix(...)` / `test(...)` / `docs(...): T<n> -- ...`). No amend; empty `%(trailers)`.
- **The FULL fast suite** (`python -m pytest -m "not slow" -q`) runs to green BEFORE the executing review and again on the final head. `ruff check swing/` clean.
- **Executing review:** `strong`, with REPO ACCESS (production code). Bundle if stdin: the diff plus `runner.py:1100-1130, 1450-1640, 2120-2140, 2385-2405, 3015-3145`, `research_health.py:755-1012`, `config.py:266-286`, `ohlcv_archive.py:595-610, 623-720, 773-871`, `pattern_detection_events.py:110-155`, `orchestration.py:150-170, 315-330`.
- **Supersession is by REPLACEMENT.** Prose this arc makes false is rewritten in the task that makes the new text true (T1, T2, T4).

## Assumption locks (design choices; reasons in one line each, the argument in the ledger)

- **AL-1, the invalid_ohlc comparison** is RD's literal form with named divisors: `_INVALID_OHLC_GREEN_DIVISOR = 20`, `_INVALID_OHLC_RED_DIVISOR = 10`; green iff `count * 20 <= us`, red iff `count * 10 > us`, else yellow. The display thresholds are DERIVED from the same constants (`100 / 20` -> "5.00", `100 / 10` -> "10.00"), so the text and the comparison cannot diverge (the 21-B class).
- **AL-2, `us = int(unique_signals)` for the comparison only.** `_is_nonneg_count` (:783-800) admits only integer-valued values, so the cast is lossless. The summary f-string keeps `unique_signals` as today.
- **AL-3, display.** The invalid_ohlc segment becomes `invalid_ohlc=<n> (<pct:.2f>%, <band>; yellow above 5.00%, red above 10.00%)`, RD's form. The other two reasons keep `<reason>=<n> (<pct:.1f>%)`, unchanged.
- **AL-4, no count belt.** `_INVALID_OHLC_BASELINE_COUNT`, `over`, `excess_pct` and the "baseline" text are deleted (CHARC F6, RD concurs).
- **AL-5, the comment at :766-768** describes invalid_ohlc's old ~30% history as the reason for the 10 / 25 floors. After T1 those floors no longer govern invalid_ohlc, so the comment is rewritten to name the two reasons they govern. Values unchanged.
- **AL-6, the open-detection read is a SEPARATE try, BEFORE the existing wholesale try.** A reader failure never masquerades as "warm raised wholesale"; the wholesale path and its test are untouched.
- **AL-7, the helper's shape (CHARC F10 (1)).** `_open_detection_warm_tickers(cfg, lease) -> list[str]`:
  1. `observation_date = lease_data_asof(cfg, lease)`: observe's literal helper (:1111), resolved by its runner module name;
  2. `conn = connect(cfg.paths.db_path)`: runner's module-level `connect` (:22, which IS `swing.data.db.connect`);
  3. `try:` the selector, imported INSIDE the helper exactly as observe imports it (`from swing.data.repos.pattern_detection_events import list_observable_detections`, cf. :3112-3114), called `list_observable_detections(conn, source="pipeline", observation_date=observation_date)`; `finally: conn.close()`;
  4. return `sorted({d.ticker.upper() for d in dets})`.

  The inside-function import fixes the monkeypatch target for the tests at the repo module attribute.
- **AL-8, transaction posture.** A fresh connection, SELECT-only, closed in `finally`. It runs in the pre-fetch hook (`orchestration.py:162`), before `_persist`'s fenced write (`orchestration.py:323`), and it selects DETECTIONS, never candidates. So it never reads the run's own uncommitted rows (CHARC F10: "true but not load-bearing").
- **AL-9, the set read at evaluate time IS the set observe reads.**
  - `pipeline_runs.data_asof_date` is written ONCE, at lease acquisition (`runner.py:610-617`). By read, none of the seven `UPDATE pipeline_runs` statements sets it (`repos/pipeline.py:67, 82, 108` (allowlisted status columns), `127, 145, 218`; `runner.py:771`).
  - Detect's new rows carry `data_asof_date == observation_date`, which the selector's strict `<` excludes (`pattern_detection_events.py:118-120`, SQL at :154).
  - Observations are written only by observe, later in the run.
- **AL-10, cohort composition (CHARC F10 (3)).**
  - `base = [cfg.rs.benchmark_ticker, *candidate_tickers, *universe_tickers]` stays BYTE-IDENTICAL to today (:1473), including any duplicates inside it.
  - `added = [t for t in helper_result if t not in {b.upper() for b in base}]`, which is sorted, uppercase and distinct.
  - `warm_set = [*base, *added]`. "No duplicates" means the append introduces none.
  - The ruling's reason, "so the existing cohort's chunking does not shift", is false by mechanism: `warm_archives_batch` sorts the uppercased set (`ohlcv_archive.py:666`). It is encoded as ruled anyway (ledger "Intake I-2").
- **AL-11, telemetry (CHARC F11).** ` open_det=<a> open_det_added=<b>` is APPENDED to the end of the existing format string (:1493-1495). `a = len(helper_result)` and `b = len(added)`. Both are the string `n/a` when the read failed. An empty open set reads `0`/`0` with no warning; observe emits its own #27 "no observable detections" entry (:3139-3142).
- **AL-12, the reader-failure warning.** `log.warning(...)` and, when `run_warnings is not None`, `{"step": "evaluate_warm", "reason": "open-detection cohort read failed (warm proceeds with base cohort): " + " ".join(f"{type(exc).__name__}: {exc}".split())[:200]}`. It catches `Exception` (ANY exception, CHARC F10 (2)).
- **AL-13, the window constant (CHARC F12).** `DETECT_OBSERVE_WINDOW_DAYS = 400` at runner module level, used at :2136, :2398 and :3054. The comments at :2395 and :3052 are reworded so they describe today and carry no `window_days=400` literal. The closure grep counts comments: today it returns 5 lines (3 code, 2 comment).
- **AL-14, the depth relation is STRICT: `archive_history_days > DETECT_OBSERVE_WINDOW_DAYS`.** CHARC RULED strict `>` (I-4 / R1-01, RESOLVED; its F12 text is amended to read "`archive_history_days` > the constant"; ledger "Rulings on I-4 / R1-01").
  - The archive retains the last N trading rows (`ohlcv_archive.py:607, 836, 849`, each `.tail(archive_history_days)`), and N distinct trading dates span at least N-1 calendar days. So N > C guarantees a C-calendar-day window is covered.
  - `_calendar_window_for_trading_days` is the FETCH window: it adds a +30 buffer and is trimmed to N rows afterwards. It overstates retained depth and is not used.
  - It holds today: 1260 > 400.
- **AL-15, runtime site pins beyond the ruled grep.** Observe's and detect Pass-1's sites are pinned at runtime by patching the constant to a sentinel. The exemplar site (:2398) is covered by the closure grep only: its harness needs a seeded exemplar corpus, which is out of proportion here.
- **AL-16, the shadow pin is a LITERAL 900.** `== runner.SHADOW_EXPECTANCY_TIMEOUT_S` would be tautological. `tests/pipeline/test_step_shadow_expectancy.py:238`'s `TimeoutExpired(timeout=300)` is a synthetic exception attribute that nothing asserts on. It stays.
- **AL-17, the six existing warm unit tests stub the reader** through an autouse fixture in their own file (`_open_detection_warm_tickers -> []`). Their `_Cfg` has no `db_path`, so a real read would append the reader-failure warning that their `== []` / `len == 1` assertions exclude. The new warm tests live in a separate file so the stub cannot reach them.

## Task ladder

### T1 -- D82: invalid_ohlc is judged as a RATE (research_health.py; tests/monitoring/test_research_health_checks.py)

**Step 1, RED.** In `tests/monitoring/test_research_health_checks.py`:

(a) DELETE these six tests, each SUPERSEDED BY NAME (each encodes the retired count rule; replaced, never edited to pass), and the CALIBRATION B comment block at :418-422:

| superseded test (line) | fixture | asserted (pre) | new rule reads | replaced by |
|---|---|---|---|---|
| `test_excluded_yellow_at_threshold` (:391) | 15/100 | green (15 <= 23) | red | N1, N1b |
| `test_excluded_red_over_threshold` (:405) | 30/100 | yellow (excess 7%) | red | N1 |
| `test_excluded_invalid_ohlc_at_baseline_not_red` (:425) | 23/77 | green | red | N1, N3 |
| `test_excluded_invalid_ohlc_above_baseline_red` (:437) | 50/77 | red via excess 35.1% | red | N1 (the red arm at 154) |
| `test_excluded_invalid_ohlc_just_above_baseline_yellow` (:447) | 24/77 | yellow floor | red | N1 |
| `test_excluded_baseline_visible_in_detail` (:484) | 23/77 | "baseline 23" in detail | n/a (text retired) | N2, N3 |

(b) KEEP these three; their ASSERTIONS are unchanged and their COMMENTS are rewritten by replacement:
- `test_excluded_green_when_under_threshold` (:381): 5/100. The new comment says it pins the INCLUSIVE green bound at exactly 5.00% (`5*20 = 100 <= 100`).
- `test_excluded_other_reasons_keep_thresholds` (:459): invalid_ohlc=0. The new comment says the RATE rule applies only to invalid_ohlc. Its yellow leg (insufficient_forward_depth 20/100) still kills a mutant that applies 5/10 to every reason (20% would read red).
- `test_excluded_ok_when_unique_signals_is_integer_valued_float` (:652): 5/100.0 -> green. The new comment says `5*20 = 100 <= int(100.0)`.

The other 17 `test_excluded_*` functions (26 in the file, by `grep -n "^def test_excluded"`) are read and untouched. Each is absent / corrupt / zero-signal / no-hypothesis / other-reason only, or invalid_ohlc at 0 or 1 of 100.

(c) ADD, all on `_funnel(...)` + `_write_manifest(...)` (the file's existing real-shape builders):

| id | test | fixture | expected (post) | pre-fix reads (baseline 23) | RED pre-fix? |
|---|---|---|---|---|---|
| N1 | `test_excluded_invalid_ohlc_rate_bands_at_1535[76/77/153/154]` (parametrized) | `invalid_ohlc=c` of 1535, nothing else | 76 green; 77 yellow; 153 yellow; 154 red | 76: over 53, 3.45% -> yellow; 77: 3.52% -> yellow; 153: 8.47% -> yellow; 154: 8.53% -> yellow | 76 and 154 RED; 77 and 153 equal (their target is the rounding mutant) |
| N1b | `test_excluded_invalid_ohlc_exactly_ten_percent_is_yellow` | 10/100 | yellow (`100 > 100` is false) | over 0 -> green | RED |
| N2 | `test_excluded_invalid_ohlc_display_two_dp_and_band` | 77/1535 | detail starts with `invalid_ohlc=77 (5.02%, yellow; yellow above 5.00%, red above 10.00%)` | `invalid_ohlc=77 (5.0%, baseline 23)` | RED |
| N3 | `test_excluded_live_shape_71_of_1535_reads_green` | the live manifest's funnel (below) | status green; summary `excluded reasons vs 1535 signals`; detail EQUALS `invalid_ohlc=71 (4.63%, green; yellow above 5.00%, red above 10.00%); insufficient_forward_depth=26 (1.7%); missing_observations=20 (1.3%)`; `"baseline" not in detail` | yellow (over 48 -> 3.13%) | RED |

- **N3's fixture is the real emitter's shape**, copied from `exports/research/shadow-expectancy-20261018T234055Z/manifest.json` (p03): `unique_signals = 1535`; `per_hypothesis = {"A+ baseline": {"excluded": {"degenerate_risk": 1}}, "Broad-watch baseline": {"excluded": {"degenerate_risk": 30, "insufficient_forward_depth": 26, "invalid_ohlc": 71, "missing_observations": 20}}, "Near-A+ defensible: extension test": {"excluded": {}}}`; `unattributed = {}`. The terminal cards are omitted, because they are validated only when present (:855-857).
- **The mutants each new pin kills** (arithmetic in p02):
  - a rounded 1-dp comparison: N1[77] (5.0 <= 5 -> green) and N1[154] (10.0 > 10 is false -> yellow);
  - a strict-green `<`: the kept 5/100 test (100 < 100 is false -> yellow);
  - an inclusive-red `>=`: N1b (100 >= 100 -> red);
  - a surviving count belt: N3 (71 > 23 -> at least yellow);
  - a display read from a literal rather than the constants: N2 and N3, if the constants move.

  The comparator for the mirror family is N1 + N1b + N2. Each fails if a constant and its stated rule diverge.

Run: N1[76], N1[154], N1b, N2 and N3 FAIL; N1[77] and N1[153] pass (pre equals post, by the table).

**Step 2, GREEN.** In `research_health.py`:
- delete :771-780 (the CALIBRATION B block and `_INVALID_OHLC_BASELINE_COUNT`);
- add the two divisor constants with a D82 comment (AL-1);
- rewrite :766-768 (AL-5);
- replace :981-996 with:
  ```python
  if reason == "invalid_ohlc":
      # D82 (RD F5, CHARC F6; 2026-10-20): a RATE of unique_signals by INTEGER
      # cross-multiplication -- never a float ratio, never the rounded display.
      us = int(unique_signals)  # lossless: _is_nonneg_count admits integer values only
      if count * _INVALID_OHLC_GREEN_DIVISOR <= us:
          reason_status = "green"
      elif count * _INVALID_OHLC_RED_DIVISOR > us:
          reason_status = "red"
      else:
          reason_status = "yellow"
      parts.append(
          f"{reason}={count} ({pct:.2f}%, {reason_status}; yellow above "
          f"{100 / _INVALID_OHLC_GREEN_DIVISOR:.2f}%, red above "
          f"{100 / _INVALID_OHLC_RED_DIVISOR:.2f}%)")
  ```

  The `else:` arm for the other two reasons (:997-1006), the zero-signal branch (:955-969), the no-hypothesis branch (:971-974) and every corrupt / absent branch stay byte-identical. Run: all of T1's tests pass, and so does the rest of `tests/monitoring/`.

**Step 3, closure.** Each of these greps, over `swing/ tests/`, returns ZERO:
- `grep -rn --include=*.py "_INVALID_OHLC_BASELINE_COUNT" swing/ tests/`
- `grep -rn --include=*.py "excess_pct" swing/ tests/`
- `grep -rn --include=*.py "CALIBRATION B" swing/ tests/`
- `grep -rn --include=*.py "baseline 23" swing/ tests/`

The two remaining `23 of 77` / "baselines `invalid_ohlc`" hits, `swing/latches/service.py:393-394` and `tests/latches/test_criteria_lapse.py:1136-1138`, are T2's. Commit: `feat(monitoring): T1 -- invalid_ohlc judged as a rate of unique signals (D82)`.

### T2 -- F14 + I-1: both docstrings describe the rate rule (swing/latches/service.py:393-394; tests/latches/test_criteria_lapse.py:1136-1138)

**Step 1.** Replace the parenthetical `(the 18-D research monitor baselines \`invalid_ohlc\` at 23 of 77 unique signals)` with: `(the 18-D research monitor judges the engine's \`invalid_ohlc\` exclusions as a RATE of unique signals -- green at or below 5.00%, red above 10.00%)`. Change nothing else in the docstring. No test: it is prose. Its check is `grep -n "23 of 77" swing/latches/service.py` returning zero.

**Step 2 (orchestrator ruling I-1: widen).** Make the identical replacement at `tests/latches/test_criteria_lapse.py:1136-1138` (the `_envelope_case` docstring). Change nothing else in that docstring or file. No test: it is prose. Its closure checks are `grep -rn --include=*.py "baselines \`invalid_ohlc\`" swing/ tests/` and `grep -rn --include=*.py "23 of 77" swing/ tests/`, each returning zero after T1 and T2 (today: 2 and 4 lines; the other two `23 of 77` hits, `research_health.py:776` and `test_research_health_checks.py:426`, are deleted by T1).

Commit: `docs(latches): T2 -- the invalid-OHLC docstrings describe the rate rule (F14, I-1)`.

### T3 -- shadow timeout 300 -> 900 (runner.py:1124; tests/pipeline/test_step_shadow_expectancy.py:135-136)

**RED:** change `:136` to `assert rec["kwargs"]["timeout"] == 900` and rewrite the `:135` comment to "900 s timeout (maintenance rider; CHARC-ruled: 37 s today, ~5 min at 8x signals, 3x headroom)". Run: FAIL (300 != 900).
**GREEN:** `SHADOW_EXPECTANCY_TIMEOUT_S = 900`. Run: pass. The warning text at :1248-1249 interpolates the constant, so no text changes. `:238` is untouched (AL-16).
Commit: `fix(pipeline): T3 -- shadow-expectancy timeout 300 -> 900 s`.

### T4 -- F12: one named window constant at the three sites; depth relation (ii) (runner.py; config.py:284 comment; new tests/pipeline/test_detect_observe_window.py; tests/pipeline/test_step_pattern_detect.py)

**Step 1, RED.**
- **D1** `test_warm_depth_covers_observe_window_against_live_config` (new file). Load the LIVE tracked config `swing.config.load(Path(__file__).resolve().parents[2] / "swing.config.toml")` and assert `cfg.archive.archive_history_days > runner.DETECT_OBSERVE_WINDOW_DAYS` (AL-14). `swing.config.load` is the loader the CLI uses (`cli.py:35, 244`).
  - CHARC condition (1): the test's docstring states the unit mismatch and the bound in one sentence: "the config counts TRADING rows (`ohlcv_archive.py:607` keeps the last N), the constant is CALENDAR days; N rows span at least N-1 calendar days, so N > C". It may quote today's margin (1260 trading rows, ~1,857 calendar days, against 400).
  - CHARC condition (2): the left side is the value read through `Config`, never a literal 1260. The test pins the deployed value, not today's default.
  - Pre-fix: AttributeError (no constant) -> RED. Post: 1260 > 400.
  - Mechanic: `ArchiveConfig(**raw.get("archive", {}))` (`config.py:859`) reads the tracked toml only, which has no `[archive]` section today, so the dataclass default 1260 applies (`config.py:284`).
  - Null implementation killed: a constant set past the archive depth.
- **D2** `test_observe_populate_uses_the_window_constant` (new file). Monkeypatch `runner.DETECT_OBSERVE_WINDOW_DAYS` to 401 and `runner.last_completed_session` to `date(2026, 6, 4)` (the `test_observe_remediation.py` pattern). Call `runner._bar_for_date(cfg, rec_cache, "AAPL", "2026-06-04")` with a cache recording `window_days`, and assert it recorded `[401]`. Pre-fix: the monkeypatch raises AttributeError -> RED. With `raising=False` the cache would record 400 -> RED.
- **D3** `test_detect_pass1_uses_the_window_constant` (in `test_step_pattern_detect.py`, on its `seeded_env` + `_seed_aplus_candidate` harness, cf. :583-650). Use a `_RecordingCache` that records `window_days` and returns `seeded_env["bars"]`; patch the constant to 401; assert every recorded value is 401. RED as D2.
- **D4** `test_window_constant_value_is_400` (new file): `runner.DETECT_OBSERVE_WINDOW_DAYS == 400`, the behaviour-neutral guard. RED pre-fix (AttributeError).

**Step 2, GREEN.** In `swing/config.py`, add one comment line directly above `archive_history_days: int = 1260` (:284): `# a count of trading ROWS retained; see ohlcv_archive.py:607`. The field line, its name and its value are unchanged; the field moves to :285. No test: it is prose. Then add `DETECT_OBSERVE_WINDOW_DAYS = 400` near the other runner module constants, with a one-line comment saying detect Pass-1, the exemplar fetch and observe's populate share it. Replace the literal at :2136, :2398 and :3054. Reword :2395 to "the SAME window constant as the Pass-1 fetch (#28/#29 historical depth preserved)" and :3052 to "the detect-step Pass-1 window constant (~400 calendar days), so the archive refresh covers the same depth". Run: D1-D4 pass, and `tests/pipeline/` stays green.
**Step 3, closure:** `grep -rn --include=*.py "window_days=400" swing/` returns ZERO (5 lines before: 3 code, 2 comment).
Commit: `refactor(pipeline): T4 -- one named detect/observe window constant at the three sites; archive depth unit documented (F12, I-4)`.

### T5 -- D83: the open detection set joins the evaluate warm cohort (runner.py; tests)

**Step 1, RED.** Shared fixtures for the new file `tests/pipeline/test_step_evaluate_warm_open_detections.py`:
- `tmp_db_at_head`, `_plant_detection` and `_FakeLease`, imported from `tests/pipeline/conftest_temporal.py` (as `test_step_pattern_observe.py:7-15` does);
- a `pipeline_runs` row `(id=1, trigger='manual', data_asof_date='2026-06-10', action_session_date='2026-06-11', lease_token='tok', state='running')`;
- the lease is `_FakeLease(db_path, 1, "2026-06-10")` (`conftest_temporal.py:70`: `run_id`, `step()`, `fenced_write()`); the helper reads only `lease.run_id`, through `lease_data_asof` (`runner.py:1111-1118`);
- a duck-typed cfg exposing `paths.db_path`, `paths.prices_cache_dir`, `archive.archive_history_days = 1260` and `rs.benchmark_ticker = "SPY"`;
- `warm_archives_batch` patched at `rmod.warm_archives_batch` to a recorder returning `WarmReport(cache_hit=1)`.

A terminal observation is planted with `insert_observation`, exactly as `test_step_pattern_observe.py:342-349` does: finite `ohlc_today_json`, `status="expired"`, `status_change_event="observation_horizon_reached"`.

Pre-fix, every W1-W4 call passes `lease=`, which today's signature rejects (TypeError), so each is RED before any assertion runs. The "null impl" column states what each assertion reads under the NULL implementation instead: it accepts `lease` and warms today's set.

| id | test | setup | asserts (post) | null impl | other mutant killed |
|---|---|---|---|---|---|
| W1 | `test_cohort_is_observes_selector_at_the_lease_date` (condition (i), F9) | `run_now = datetime(2026, 6, 12, 20, 0)` (its last completed session is 06-12, p02). Detections: OBS asof 06-09, open; FUT asof 06-11; DONE asof 06-01 with an `expired` observation on 06-05; CAND asof 06-09. Candidates `["CAND", "AAA"]`, universe `["UUU"]`. The real selector is wrapped by a recording spy at `swing.data.repos.pattern_detection_events.list_observable_detections`. | warm list == `["SPY", "CAND", "AAA", "UUU", "OBS"]`; the spy was called exactly once, with `source="pipeline", observation_date="2026-06-10"` | list lacks OBS -> RED | R-run_now (06-12) admits FUT -> `[..., "FUT", "OBS"]` -> RED; a hand SQL over every detection admits DONE and FUT -> RED; a hand SQL that replicates the semantics fails the spy assertion |
| W2 | `test_cohort_appends_distinct_uppercase_after_the_untouched_base` (F10 (3), F11) | Candidates `["aapl", "msft"]`, universe `["AAPL", "NVDA"]`. Open detections on MSFT, ZZZ, BBB and AAPL (asof 06-09). caplog at INFO on `rmod.log`. | list == `["SPY", "aapl", "msft", "AAPL", "NVDA", "BBB", "ZZZ"]` (base byte-identical, its internal case-duplicate kept; appended sorted, uppercase, disjoint); the `evaluate warm:` line matches `r"wall=[0-9.]+s open_det=4 open_det_added=2$"` | no append, no fields -> RED | a raw-case dedupe appends MSFT -> RED; appending before the base breaks the base-prefix assertion -> RED |
| W3 | `test_reader_failure_warns_and_warms_the_base_set[selector, anchor]` (condition (iii), F10 (2)) | Case `selector`: the selector is patched to raise `RuntimeError("detections table locked")`. Case `anchor`: `rmod.lease_data_asof` is patched to raise `TypeError("no run row")`. | no raise; the warm got exactly the base list; `run_warnings` == ONE entry, `step == "evaluate_warm"` and reason containing `open-detection cohort read failed` and the exception text; the cohort line ends `open_det=n/a open_det_added=n/a`; one WARNING record | no warning, no n/a -> RED | a reader inside the wholesale try loses the warm (its stub is never called) -> RED |
| W4 | `test_reader_closes_its_connection_on_failure` (F10 (1)) | `rmod.lease_data_asof` returns `"2026-06-10"`; `rmod.connect` returns a fake connection whose `close()` sets a flag; the selector raises | the flag is set; the W3-shape warning is present | no read, no warning -> RED | no `finally` -> the flag stays unset -> RED |

In existing files:
- **W5** `tests/pipeline/test_step_evaluate_warm_scope.py::test_warm_and_prewarm_receive_exact_ticker_sets` (:36-79): bind `lease = _FakeLease(inputs.db_path, 1)`, pass it, and ADD `assert prewarm_calls[0]["lease"] is lease`. This pins the CALLER-SIDE obligation (gotcha #31). Pre-fix: KeyError -> RED.
- **W6** `tests/pipeline/test_step_evaluate_warm_scope.py::test_evaluate_runs_when_the_open_detection_read_raises` (new; condition (iii) at evaluate level). Use the same golden harness as W5:
  - `_warm_pipeline_marketdata` -> a recorder;
  - `rmod.warm_archives_batch` -> a recorder returning `WarmReport()`;
  - the selector patched to raise `RuntimeError("detections table locked")`;
  - the REAL `_prewarm_evaluate_archives`;
  - `run_warnings = []`.

  Assert: `_step_evaluate` returns an int run id; `run_warnings` contains exactly one reader-failure entry naming the read and the cause; the warm recorder got `[cfg.rs.benchmark_ticker, *SCREEN_TICKERS, HELD_TICKER, PINNED_TICKER, *universe.tickers]`. Pre-fix: no entry -> RED.
- **W7** `tests/pipeline/test_step_evaluate_warm.py`: the six tests that CALL the helper (:31, :48, :63, :76, :129, :147) pass `lease=_StubLease()`. The file imports only `runner` and `WarmReport`, so it DEFINES a module-local `class _StubLease` with `run_id = 1` (R2-01). The stub is never read: the autouse fixture replaces the helper. An autouse fixture in that file patches `rmod._open_detection_warm_tickers` to `lambda cfg, lease: []` (AL-17). The seventh test, `test_step_evaluate_wires_prewarm_before_fetch_loops`, is source-text and calls nothing; it is unchanged, and its regex `^\s*_prewarm_evaluate_archives\(` still matches after T5. Pre-fix, the autouse fixture's patch target does not exist, so all SEVEN error at setup (mechanical). They go green at GREEN.

Run: W1-W7 RED as tabulated.

**Step 2, GREEN** in `runner.py`:
- add `_open_detection_warm_tickers(cfg, lease)` directly above `_prewarm_evaluate_archives` (AL-7);
- give `_prewarm_evaluate_archives` a required keyword `lease` (`*, cfg, candidate_tickers, universe_tickers, run_now, run_warnings, lease`), with docstring additions naming the cohort, the anchor and the failure path. Its body:
  1. `base = [...]` (unchanged expression);
  2. a `try:` that reads the helper, computes `added` (AL-10) and sets `open_det, open_det_added = len(...), len(added)`; `except Exception as exc:` logs, appends the AL-12 entry, sets `added = []` and both fields to `"n/a"`;
  3. `warm_set = [*base, *added]`;
  4. the existing wholesale `try` UNCHANGED;
  5. the cohort log line with ` open_det=%s open_det_added=%s` appended at the END of the format string and its two arguments (AL-11);
  6. the trim and degraded blocks UNCHANGED.

  In `_pre_fetch_hook` add `lease=lease,` to the call (:1596-1600). Run: W1-W7 pass.

**Step 3, condition (v), NEUTRALITY** (new file `tests/pipeline/test_step_evaluate_warm_neutrality.py`; written in Step 1, listed here for readability):
- **N-V** `test_observation_rows_identical_with_and_without_the_warm`. A module helper `run_world(tmp_path, *, warm: bool) -> dict` applies its own patches with `pytest.MonkeyPatch.context()` so a scratch script can call it for the merge report. The helper:
  - creates a DB at head with `pipeline_runs` id=1 asof 06-10 and one open detection on ROT (asof 06-05);
  - seeds `ROT.parquet` (bars 06-04, 06-05, 06-08) and `ROT.meta.json` (`last_full_refresh_date` 06-08) in the world's own cache dir;
  - builds ONE deterministic per-(ticker, date) bar table for 06-04..06-10, with values that vary by date (`open = 10 + i`, `high = 11 + i`, `low = 9 + i`, `close = 10.5 + i`, `volume = 1000 + i`);
  - patches `swing.data.ohlcv_archive.yf.download` with a fake that HONOURS its `start` / `end` kwargs (`start <= d < end`). A `str` argument gets the flat single-ticker frame; a `list` argument gets the ticker-major MultiIndex frame in `_mk_batch_frame`'s shape (`tests/data/test_ohlcv_archive_warm.py:184-216`), built from the same table. Every call's argument type is recorded with a phase tag;
  - patches `swing.data.ohlcv_archive._last_completed_session_today`, `swing.web.ohlcv_cache.last_completed_session` and `swing.pipeline.runner.last_completed_session` to 06-10, and `_load_archive_config_for_stagger` to `False`, with `_full_refresh_stagger_enabled.cache_clear()` before and after;
  - if `warm`, calls `_prewarm_evaluate_archives(cfg=..., candidate_tickers=[], universe_tickers=[], run_now=datetime(2026, 6, 10, 20, 0), run_warnings=[], lease=lease)` with the REAL `warm_archives_batch`, where `lease = _FakeLease(db_path, 1, "2026-06-10")` from `conftest_temporal.py:70` (R2-01);
  - then calls `_step_pattern_observe(cfg=..., lease=lease, ohlcv_cache=OhlcvCache(cfg), run_warnings=[])` with that same `lease`. Observe writes its rows through `lease.fenced_write()` (`runner.py:3243`), so a bare `run_id` stub would fail here. The cfg is duck-typed with `web.ohlcv_cache_ttl_seconds`, `web.max_concurrent_ohlcv_fetches`, `archive.archive_history_days`, `rs.benchmark_ticker` and `pipeline.*`;
  - returns the rows `SELECT detection_id, observation_date, ohlc_today_json, status, status_change_event, sessions_since_detection FROM pattern_forward_observations ORDER BY detection_id, observation_date` and the observe-phase `str`-call count.

  Asserts:
  - (1) both worlds have exactly 1 row and `rows_A == rows_B`;
  - (2) world B's observe phase made ZERO single-ticker downloads, and world A's made exactly 1. That proves the warm took effect.

  Pre-fix, world B raises TypeError on `lease=`. Under the null implementation, (2) is RED: that warm never selects ROT, so world B's observe makes 1 single fetch. (1) is an invariant that holds pre and post. Its discriminating power is shown by the merge-report mutation check below.

Commit (Steps 1-3 together; one logical change): `feat(pipeline): T5 -- the open detection set joins the evaluate warm cohort (D83)`.

### T6 -- full suite, ruff, closure, then the executing review

1. Run `python -m pytest -m "not slow" -q` to green and read the tail. Run `ruff check swing/`.
2. Run the closure greps of T1 step 3, T2 and T4 step 3. Confirm `git diff --stat main...HEAD -- swing/data swing/trades` is EMPTY.
3. Run the condition (vi) mutation check (scratch, never committed):
   - set `threads=False` -> `threads=True` in `swing/data/ohlcv_archive.py:_yf_download_window`;
   - run `tests/data/test_ohlcv_archive.py::test_new_ticker_triggers_full_history_fetch` and `tests/data/test_ohlcv_archive_yfinance_audit.py::test_single_success_records` and see BOTH red;
   - `git checkout -- swing/data/ohlcv_archive.py`; `git diff --exit-code swing/data` returns 0.

   Quote all of it in the exec ledger.
4. Run the condition (v) mutation check (scratch): make N-V's fake return `close + 0.01` for `list` calls only, see assertion (1) red, revert. Quote it.
5. Then the executing Reviewer A loop (`strong`), per the recipe.

## Test roster (complete; method: every test named in T1-T5, and the existing files they touch, by read)

| file | added | edited (assertion) | edited (comment only) | deleted |
|---|---|---|---|---|
| `tests/monitoring/test_research_health_checks.py` | N1 (x4), N1b, N2, N3 | -- | 3 kept tests + section comment | 6 superseded + the CALIBRATION B block |
| `tests/latches/test_criteria_lapse.py` | -- | -- | :1136-1138 docstring (T2 step 2) | -- |
| `tests/pipeline/test_step_shadow_expectancy.py` | -- | :136 (300 -> 900) | :135 | -- |
| `tests/pipeline/test_detect_observe_window.py` (new) | D1, D2, D4 | -- | -- | -- |
| `swing/config.py:284` (production prose, listed so the roster is complete) | -- | -- | one comment line (T4 step 2; no test) | -- |
| `tests/pipeline/test_step_pattern_detect.py` | D3 | -- | -- | -- |
| `tests/pipeline/test_step_evaluate_warm_open_detections.py` (new) | W1, W2, W3 (x2), W4 | -- | -- | -- |
| `tests/pipeline/test_step_evaluate_warm_scope.py` | W6 | W5 (+1 assertion, lease bound) | -- | -- |
| `tests/pipeline/test_step_evaluate_warm.py` | autouse reader stub | 6 calls gain `lease=` (W7) | -- | -- |
| `tests/pipeline/test_step_evaluate_warm_neutrality.py` (new) | N-V | -- | -- | -- |

The other excluded-check consumers were checked by read and by cell 1's full-suite trace (m11). Every fixture in `test_research_health_aggregate.py` (:102, :168, :246), `test_research_health_envelope_roundtrip.py` (:57-64), `test_step_research_health.py` (:89-96), `test_research_health_artifact.py` (:62) and `test_research_health_script.py` uses invalid_ohlc 1 of 100, which is green under both rules. They are UNCHANGED.

## Not changed (explicit)

- `_EXCL_YELLOW_PCT = 10.0`, `_EXCL_RED_PCT = 25.0` and their arm (:997-1006); `_ATTRIBUTED_EXCLUDED_REASONS`; `_is_nonneg_count` (kept, CHARC F6); `_excluded_is_well_shaped`; `_manifest_is_well_shaped`; `_read_newest_manifest`; the zero-signal, inconsistent, no-hypothesis, absent and corrupt branches.
- Coverage gaps: `_COVERAGE_YELLOW_GAPS = 1`, `_COVERAGE_RED_GAPS = 10`, CALIBRATION A and C, and all ~40 coverage tests (RD: DEFERRED).
- `warm_archives_batch`, `_classify_warm_cohorts`, `_fetch_chunk`, `_yf_download_window` (`threads=False`), `read_or_fetch_archive`, `resolve_ohlcv_window`: nothing under `swing/data/`.
- `_step_pattern_observe`'s logic and `observe_load`; `lease_data_asof`; `list_observable_detections`.
- The warm's wholesale-failure path and its #27 entry; the trim and degraded #27 entries; `end_date` handling.
- `staleness.py`, `stale_step_threshold_seconds` (`config.py:217`), the 60 s soft step budget (`lease.py:31`).
- The research-health RD push, the artifact schema, the stoplight reader (`stoplights.py:189, 234` consume `overall` and `checks` only, CHARC F6).

## Owner docs that restate a changed constant (LISTED for their owners; this rider edits none)

| owner | site | what goes stale |
|---|---|---|
| RD | `docs/research-director-watch-standard.md:168` | "#2 invalid_ohlc is BASELINED at 23"; RD edits at merge. `:169` (coverage) is unchanged, because coverage is deferred |
| RD | `docs/rd-state.md:80` | "the stoplight cannot escalate it -- CALIBRATION B" |
| CHARC | `docs/tool-director-context.md:146-147` (D82, D83 rows), `docs/charc-state.md:13` | the closing dispositions at merge |
| orchestrator | `docs/orchestrator-context.md:94`, `CLAUDE.md:67` ("#2 `invalid_ohlc` baseline-23") | the orchestrator edits after merge |

Historical plans, specs and archives (`docs/superpowers/**`, `docs/archive/**`, `docs/phase18-todo.md`) are records and are not listed.

## Merge-report checklist

1. **F8 witness, exactly as CHARC defined it (items (a)-(d)).** Run `cell2-probes\w01_f8_witness.py <run_id>` for the LAST pre-merge night and the FIRST post-merge night and quote both side by side:
   - (a) `SELECT COUNT(*) FROM yfinance_calls WHERE call_type='download_single' AND pipeline_run_id=? AND ts BETWEEN <observe start> AND <observe finish>`, the bounds taken from the lease step line `step ordinal=7 name=pattern_observe took N ms` (finish stamp minus N);
   - (b) the step wall from that line;
   - (c) `observe_load`, written as EXPECTED UNCHANGED (fetch_window ~239), so nobody reads it as the warm failing;
   - (d) the F11 cohort fields.

   **Baseline, run 194, reproduced by w01 (`w01_f8_witness.out.txt`):** 229 singles for the run, 216 inside observe, wall 1,300,128 ms, `observe_load` `{"observed": 6972, "fetch_window": 239, "in_memory_hit": 6938}`, (d) ABSENT (pre-merge code). The expected post-merge shape (CHARC F8): observe singles near zero for the rotated-out set; evaluate's `download_batch` up by ~3 chunks of 75; the step wall down by the fetch term, not to 900. *Context line (this cell's addition, not a witness item; CHARC may strike it):* the Schwab ladder state on each quoted night (`schwab_api_calls` rows for the run; L-1).
2. **F7, in these words:** "the warm alone does not bring a run-194-sized night under 900 s; the per-detection term is D89."
3. **Condition (iv):** the first post-merge night's `evaluate warm:` line, quoted with its `open_det=` / `open_det_added=` fields.
4. **Condition (v):** quote N-V's two row sets (call `run_world(..., warm=False)` and `run_world(..., warm=True)` from a scratch script), equal in count and values, plus the T6 step 4 mutation check.
5. **Condition (vi):** the T6 step 3 mutation check and the empty `swing/data` diff.
6. **D82 live:** the first post-merge `exports/research/health/latest.json` `excluded_reason_breakdown` check, quoted. Expected GREEN with `invalid_ohlc=71 (4.63%, green; ...` if the manifest still reads 71/1535, otherwise its live values judged by the same bands.
7. **Closure greps** (T1, T2, T4) quoted with their outputs. The suite tail on the final head.
8. **Owner docs:** the table above, for routing.
