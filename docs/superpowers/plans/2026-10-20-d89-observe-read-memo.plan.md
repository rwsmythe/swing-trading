# D89 (observe's per-step read memo) -- implementation plan

**Ledger (rulings verbatim, intake corrections, kept claims, review history):** `docs/superpowers/plans/2026-10-20-d89-observe-read-memo.plan.ledger.md`. This plan cites ledger sections by number and restates none of their reasoning.
**Briefs:** `docs/d89-observe-read-memo-plan-dispatch-brief.md` (@ `31a293b4`), its section 3 superseded by `docs/d89-observe-read-memo-plan-continuation-brief-cell2.md` (@ `eed4bb2d`).
**Base:** `main` @ `eed4bb2d`. Every file:line below was re-read at that commit. `git diff --stat 31a293b4 eed4bb2d -- swing tests scripts` is empty, so the census anchors hold (ledger section 2, C-5).
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d89-memo\plan\` (`round0\` = cell 1's census probes p00-p12; `round<N>\` = this plan's review rounds).

## Header

### Declared envelope

**IN**
- `swing/pipeline/runner.py`, and nothing else under `swing/`:
  - one new private helper `_observe_memo_key(ticker, observation_date)`, directly above `_bar_for_date`;
  - `_bar_for_date` (:3073-3140): a keyword-only `memo=None` parameter, the populate's `except` arm records that it raised, the memo branch around the `resolve_ohlcv_window` call (:3118-3122), the two step comments (:3099-3106, :3114-3117) and the docstring (:3074-3083, the #31 rewrite, AL-11);
  - `_step_pattern_observe` (:3161-3326): a local `memo = {}` and `_resolve_reads = 0` beside `_observed_count` (:3205-3206); the pre-check and the keyword pass at the call (:3255); the `resolve_reads` key at the END of the `observe_load` entry (:3320-3326) and its unit line in the comment above it (:3313-3317).
- Tests: two NEW files, `tests/pipeline/test_observe_read_memo.py` and `tests/pipeline/test_observe_read_memo_neutrality.py`. No existing test file is edited (ledger K-8).

**OUT**
- Any schema, migration, dependency or new module. Anything under `swing/data/` (including `resolve_ohlcv_window` and `_backward_compat_rename`), `swing/web/` (including `OhlcvCache`) or `swing/trades/`.
- D90 (detaching the ladder from observe's populate), D91 (detections that never get a bar), Fork G (declined by CHARC).
- `_advance_status`, `_sessions_since`, the watch shed, the non-finite skip, the per-detection no-bar warning, the write pass, `list_observable_detections`, `lease_data_asof`, `build_ohlc_today_json`.
- The in-function import of `resolve_ohlcv_window` at :3086 STAYS (24 test patch sites name the module path).
- `observe_load`'s existing keys and their values (D1).
- Owner docs (listed at the end, never edited here).

### Accepted limitations (each WITH its reason; challenge invited)

- **L-1, H3: a cache TTL expiry mid-step (RD, ledger 1.1).** After an expiry, a populate can re-fetch and write while the memo serves the earlier read. Reason (RD): TTL 3600 s against the oldest entry's 570 s at run 195's observe end, and the memo shrinks the step toward ~150 s. **Re-open trigger, stated in the merge report:** any observe wall above 1,800 s on the merged code.
- **L-2, H4: a concurrent prices-cache writer (RD, ledger 1.1), at its TRUE width.** Today the race is per DETECTION (one stale read). With the memo it is per TICKER PER STEP: every later detection of that ticker inherits the stale read. Measured incidence over 87 runs: zero tickers with two distinct bars in one run (p06). No mechanism is built.
- **L-3, T-E is a DECLARED DIFFERENCE inside H3 (orchestrator ruling E1, ledger 1.4).** When the key is already memoized and THIS detection's populate raises after writing, the detection selects the memoized pair. Today's code would re-read. The case is reachable only after a TTL expiry. T-E pins E1's behaviour; it is not a neutrality test.
- **L-4, W4 stays an UPPER bound.** The audited fetch term omits the post-fetch archive work, about 20 s on run 195 (live remainder 444,341 ms against the replay's 424,727 ms, p01/p07). The memo leaves the fetch term alone, so on a Schwab-ladder-ON night W2 is unchanged and W4 still carries that work (ledger 1.3, the Schwab-ladder-ON note).

### Executing posture

- **Cell (recommendation; the orchestrator rules):** `implementer-opus-high`. The reason, named under recipe section 2A: this is measurement-chain code. `_bar_for_date` produces the bar that enters the append-only observation log.
- **TDD:** T1 is RED then GREEN then ONE commit `feat(pipeline): T1 -- observe's per-step read memo after a non-raising populate (D89)`. No amend; empty `%(trailers)`; no final `-m` paragraph starting `Word:`.
- **The FULL fast suite** (`python -m pytest -m "not slow" -q`) runs to green BEFORE the executing review and again on the final head. `ruff check swing/` clean.
- **Executing review:** `strong`, with REPO ACCESS. If you use a stdin bundle, include the diff plus `runner.py:3060-3330` and `329-512`, `ohlcv_cache.py:118-311`, `ohlcv_archive.py:283-295`, `773-853`, `883-1056` and `1194-1351`, `pattern_detection_events.py:110-160`, `research_health.py:1118-1160`, and `tests/pipeline/conftest_temporal.py`.
- **Supersession is by REPLACEMENT.** The docstring and both step comments are rewritten in T1, the task that makes the new text true.

## Assumption locks (design choices; one-line reasons; the argument is in the ledger)

- **AL-1, the key** is `_observe_memo_key(ticker, observation_date) -> (ticker, observation_date)`, with the ticker exactly as passed and NOT uppercased.
  - CHARC KEY ruling, ledger 1.2.
  - One helper is used by both `_bar_for_date` and the step's pre-check, so the two cannot drift.
  - Raw case can only ADD a read (two keys for one file set). It never merges two reads.
  - Live: zero non-uppercase tickers among run 195's rows (p01).
- **AL-2, E1, memo first (orchestrator ruling F-2, ledger 1.4).** If `memo is not None and key in memo`, the detection selects from `memo[key]`, whatever this call's populate did. The archive is not read.
- **AL-3, the write rule is RD's C3 literal (ledger 1.1).** `memo[key] = (df, provenance)` is written only when BOTH hold:
  - `memo is not None`;
  - THIS call's `get_or_fetch` returned without raising.

  It is written for every result, including an empty frame, a frame without the date's row, and a row without provenance. A raising populate writes nothing, every time. No sentinel is needed (CHARC B1).
- **AL-4, D1 (CHARC, ledger 1.2).** The populate runs on EVERY call, including memo hits. So `observe_load`'s `fetch_window` and `in_memory_hit` are byte-identical to today (pinned by N-V assertion (2) and T-load).
- **AL-5, the signature** is `_bar_for_date(cfg, ohlcv_cache, ticker: str, observation_date: str, *, memo: dict | None = None)`.
  - The parameter is KEYWORD-ONLY (C-3, ledger section 2): the wrappers at `tests/pipeline/test_pattern_pool_dormant_levers.py:98,163` read `a[2]` as the ticker.
  - `memo=None` is today's path. It reads on every call and stores nothing. The direct 4-positional callers (`test_observe_remediation.py:51,76,80`, `test_lock_guard_completed_day.py:31,44`, `test_detect_observe_window.py:50`) reach it unchanged.
- **AL-6, the resolve call is byte-identical:** `resolve_ohlcv_window(ticker, start=start, end=observation_date, cache_dir=cfg.paths.prices_cache_dir)`. There is no `migrate=` keyword. `test_step_pattern_observe.py:377`'s side-effect signature `(ticker, *, start, end, cache_dir)` depends on it (C-3).
- **AL-7, the memoized pair is never mutated and never copied.** By read of `runner.py:3123-3140`:
  - `df[df["asof_date"] == observation_date]` builds a new frame;
  - `match.iloc[-1]` and `float(r[...])` only read;
  - `provenance.get(...)` only reads.

  Ledger K-5.
- **AL-8, `resolve_reads` is counted in the step.** `_resolve_reads += 1` runs immediately before each `_bar_for_date` call, iff `_observe_memo_key(det.ticker, observation_date) not in memo`.
  - Under E1 that is EXACT: a call reads iff the key was absent, because the memo branch is the only way a read is skipped.
  - In the no-memo world (`memo` dropped by the wrapper) the dict stays empty, so the count equals today's call count.
  - Every test checks it against an independent counter wrapped around the REAL `resolve_ohlcv_window` (a closure check, not a mirror).
- **AL-9, `resolve_reads` is the LAST key of the `observe_load` entry.** Nothing in `swing/` reads the entry (W5 grep, ledger K-6). F8 (c)'s shape gains the field and loses none.
- **AL-10, lifetime.**
  - `memo` is a local of `_step_pattern_observe`, created beside `_observed_count`. It dies with the call.
  - There is no module-level, default-argument or cache-attached state. The rule "per-run, never outlives the step" holds by construction.
  - T-lifetime pins it, and `test_observe_remediation.py:76-80` already kills a mutable-default memo.
- **AL-11, the #31 docstring (C-1, ledger section 2).** `_bar_for_date`'s docstring is rewritten to what the code does today:
  - a TTL hit does no I/O;
  - on a miss, the pipeline cache fetches through the Schwab market-data ladder when the run has a Schwab client. `_install_pipeline_marketdata_caches` installs the bars hook (runner.py:509), and the ladder applies its own environment check and yfinance fallback;
  - with no client, the miss goes through `read_or_fetch_archive` (runner.py:371-372, 857-863).

  It also describes the memo rule. It says nothing about D90. The text is fixed in T1 step 2.
- **AL-12, `_backward_compat_rename` (C-2, FLAGGED for the plan-stage read, ledger K-4).**
  - `resolve_ohlcv_window` runs this write path on every call, because `migrate` defaults to True (`ohlcv_archive.py:1020-1021`). Legacy files exist for 248 of 248 tickers (p03).
  - Under the memo it runs once per ticker per step instead of once per detection.
  - Its content is a fixed point after the first call: the equality early-return at `:1340-1343`, given no intervening write (K-1, K-2).
  - Pinned by N-V assertion (5) on the Shape-A content, and by p07's replay over live-shaped copies (p11, byte-equal).

## Task ladder

### T1 -- the memo, its write rule, its key, the read count, the docstring (runner.py; two new test files)

**Step 1, RED.** Write both new files.

**Shared harness (`tests/pipeline/test_observe_read_memo.py`):**
- **Fixtures, from `tests/pipeline/conftest_temporal.py`:** `tmp_db_at_head`, `_cfg`, `_FakeLease`, `_plant_detection`, `_build_bars`, `_StubOhlcvCache`, imported as `test_step_pattern_observe.py:8-16` does.
- **The test cfg:** `cfg = _cfg(tmp_path, db_path)`, plus `cfg.web = SimpleNamespace(ohlcv_cache_ttl_seconds=3600, max_concurrent_ohlcv_fetches=4)` and `cfg.archive = SimpleNamespace(archive_history_days=1260)`. Those are the attributes `OhlcvCache.__init__` and `_fetch_bars_window` read (`ohlcv_cache.py:122-123, 288`). Attach them BEFORE constructing `OhlcvCache(cfg)`, because `__init__` copies the TTL (`:122`); T-E's TTL of -1 is set the same way.
- **Dates:** `_OBS = "2026-05-29"`. Each detection is `_plant_detection(conn, ticker=T, data_asof_date="2026-05-25", detection_date=D)`, with D drawn in order from `("2026-05-26", "2026-05-27", "2026-05-28")`.
  - Distinct `detection_date`s are needed because `UNIQUE (source, ticker, detection_date, pattern_class)` (`swing/data/migrations/0022_phase14_temporal_log.sql:50-51`).
  - Detections iterate in `detection_id` order (`pattern_detection_events.py:152`), so d1 < d2 < d3.
  - Default pivot 10 and invalidation 8, so every bar below is `pending`.
- **`_put(cache_dir, ticker, provider, rows)`:** calls `write_window(ticker, pd.DataFrame(rows, columns=["asof_date","open","high","low","close","volume"]), provider, cache_dir=cache_dir)`, as in `test_observe_remediation.py:47-49`. Each row is `(date, c, c, c, c, 1e6)` for a stated close `c`.
- **`_real_cache(cfg, monkeypatch, script)`:** a REAL `OhlcvCache(cfg)` whose instance `_fetch_bars_window` is replaced (precedent `test_observe_load_instrumentation.py:50-51`) by a callable that pops the next action from `script[ticker]`:
  - `"frame"` returns `_build_bars()`;
  - `None` returns None, so the REAL `get_or_fetch` raises `ValueError` and stores nothing (`ohlcv_cache.py:238-239`);
  - `("write", provider, rows, then)` runs `_put` and then returns `_build_bars()` if `then == "frame"`, or None if `then is None`.

  Running past the end of a script fails the test.
- **`_count_resolve(monkeypatch)`:** wraps the REAL `swing.data.ohlcv_archive.resolve_ohlcv_window` with a counter and patches it at that module path, the name `_bar_for_date` resolves at call time (:3086). Returns the counter.
- **`_drive(cfg, db_path, cache, run_id=1)`:** runs `_step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, run_id, _OBS), ohlcv_cache=cache, run_warnings=w)` under `patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS)`, and returns `w`. `load(w)` is the `observe_load` entry.
- **Rows** are read with `get_observations_for_detection(conn, det_id)`, and each `ohlc_today_json` is parsed for `close` and `provider`.

**Notation in the table below:**
- "reads" is the independent counter.
- "rr" is `load(w)["resolve_reads"]`.
- **M1** writes the memo on the raising path too (RD's quoted mutation).
- **C1** memoizes the first read whatever the populate did (killed by the same test as M1).
- **C2** memoizes only a non-None bar.
- **M2** moves `memo` to module level (cross-step).
- **M3** skips the populate on a memo hit (D2, the collapse).
- **M5** keys on the ticker only.

| id | test | setup | asserts (post-fix, E1/C3) | today (pre-fix) | mutants killed |
|---|---|---|---|---|---|
| T-H1 | `test_raise_then_heal_later_detections_observe` | AAA x3; no archive files; script AAA = `[None, ("write","yfinance",[("2026-05-28",8.8),("2026-05-29",9.0)],"frame")]` | d1 no row; d2, d3 rows close 9.0 / yfinance; exactly one `no bar for observation_date` warning (ticker AAA); `fetch_window` 2, `in_memory_hit` 1; reads 2 == rr 2 | same rows; reads 3; `load(w)["resolve_reads"]` KeyError: RED | M1: d1's empty pair is memoized, so d2 and d3 hit it and get no row; reads 1: RED |
| T-H2 | `test_raise_over_archived_yfinance_then_schwab_write_outranks` | AAA x3; `_put(yfinance, [("2026-05-28",8.8),("2026-05-29",9.0)])`; script AAA = `[None, ("write","schwab_api",[("2026-05-29",9.5)],"frame")]` | d1 close 9.0 / yfinance; d2, d3 close 9.5 / schwab_api (schwab_api outranks yfinance, `ohlcv_archive.py:92-95`); reads 2 == rr 2 | same rows; reads 3; KeyError: RED | M1 and C1: d1's yfinance 9.0 pair is memoized, so d2 and d3 carry 9.0 / yfinance: RED |
| T-C3 | `test_no_bar_ticker_is_read_once_after_a_non_raising_populate` | NOB x3; `_put(yfinance, [("2026-05-27",8.7),("2026-05-28",8.8)])` (no 05-29); script NOB = `["frame"]` | no rows; three no-bar warnings, each `ticker == "NOB"`, `observation_date == _OBS`; `fetch_window` 1, `in_memory_hit` 2; reads 1 == rr 1 | reads 3; KeyError: RED | C2: reads 3, rr 3, so `== 1` fails: RED |
| T-E | `test_memo_first_when_a_later_populate_raises_declared_h3_difference` (docstring: a DECLARED DIFFERENCE inside H3, L-3; not a neutrality test) | `cfg.web.ohlcv_cache_ttl_seconds = -1`, so every lookup misses (`(now - t) <= -1` is never true; this models H3); AAA x2; `_put(yfinance, [("2026-05-29",9.0)])`; script AAA = `["frame", ("write","yfinance",[("2026-05-29",9.9)],None)]` | d1 close 9.0; d2 close 9.0 (memo, though the archive now holds 9.9); `fetch_window` 2, `in_memory_hit` 0; reads 1 == rr 1 | d2 close 9.9, reads 2, KeyError: RED (the declared difference) | E2 (a raise bypasses the memo): d2 9.9, reads 2: RED |
| T-key | `test_memo_key_carries_the_observation_date` | Direct calls. `_put(yfinance, [("2026-05-28",8.0),("2026-05-29",9.0)])`; cache `_StubOhlcvCache({"AAA": _build_bars()})`; one `memo = {}`; call `_bar_for_date(cfg, cache, "AAA", "2026-05-28", memo=memo)` then `(..., "2026-05-29", memo=memo)` | closes 8.0 then 9.0; `set(memo) == {("AAA","2026-05-28"), ("AAA","2026-05-29")}` | TypeError on `memo=`: RED | M5: the second call hits the 05-28 pair, whose window `[05-18, 05-28]` has no 05-29 row, so it returns None: RED |
| T-lifetime | `test_memo_does_not_outlive_the_step_call` | AAA x2; `_put(yfinance, [("2026-05-27",8.7),("2026-05-28",8.8)])`; ONE real cache, script AAA = `["frame"]` (later lookups are TTL hits). Call 1 (`run_id=1`); then `_put(yfinance, [("2026-05-29",9.0)])`; call 2 (`run_id=2`) | call 1: no rows, two no-bar warnings, rr 1. Call 2: d1, d2 rows close 9.0, rr 1. reads 2 in total | rows same; KeyError: RED | M2: call 2 hits call 1's no-bar pair, so it writes no rows and rr is 0: RED |
| T-load | `test_observe_load_gains_resolve_reads_and_loses_nothing` (W6) | AAA x2, BBB x1; `_put(yfinance, [("2026-05-29",9.0)])` for both; script AAA = BBB = `["frame"]` | `set(load(w)) == {"step","metric","observed","fetch_window","in_memory_hit","resolve_reads"}`; `observed` 3, `fetch_window` 2, `in_memory_hit` 1, `resolve_reads` 2, and it is the LAST key | the key set lacks `resolve_reads`: RED | M3: `in_memory_hit` 0: RED |

**N-V (`tests/pipeline/test_observe_read_memo_neutrality.py`), the two-world equality (H (ii), P12).**

The precedent is `tests/pipeline/test_step_evaluate_warm_neutrality.py`, and its shape is copied: `run_world(tmp_path, *, memo: bool) -> dict` applies its own patches inside `pytest.MonkeyPatch.context()`, so a scratch script can call it for the merge report. It has a local duck-typed `_Cfg` (paths, web, archive, rs, pipeline, as in the precedent's :49-77).

The world:
- **Dates:** `_DATES = [06-04, 06-05, 06-08, 06-09, 06-10]` and `_SESSION = 06-10`. Patch `arch._last_completed_session_today`, `swing.web.ohlcv_cache.last_completed_session` and `rmod.last_completed_session` to `_SESSION`. Patch `arch._load_archive_config_for_stagger` to `False`, calling `_full_refresh_stagger_enabled.cache_clear()` before and after.
- **DB:** at head, with a `pipeline_runs` row `id=1` (data_asof 06-10). Detections, all with `data_asof_date="2026-06-05"` and distinct `detection_date`s 06-05/06-08/06-09:
  - AAA x3, a bar on 06-10;
  - NOB x3, the populate does not raise but there is no 06-10 bar;
  - RSE x2, every populate raises.
- **Legacy archives:** `AAA.parquet` and `NOB.parquet` are seeded with 06-04, 06-05 and 06-08, plus `.meta.json` `{"last_full_refresh_date": "2026-06-08"}` (the precedent's ROT shape, :118-123). RSE has none.
- **The fake `yf.download`:** it honours `start <= d < end` like the precedent (:125-138) and records `(phase, ticker)`. Per ticker:
  - AAA serves all `_DATES`;
  - NOB serves `_DATES` without 06-10;
  - RSE serves an empty frame.
- **The run:** `rmod._step_pattern_observe(cfg=..., lease=_FakeLease(db_path, 1, "2026-06-10"), ohlcv_cache=OhlcvCache(cfg), run_warnings=w)`, the REAL cache with no ladder. So the populate is the real `read_or_fetch_archive` gap fetch, and the read is the real `resolve_ohlcv_window` with `migrate=True` over legacy files (the C-2 path). The populate mechanics, by read:
  - AAA and NOB are not due a full refresh (meta 06-08, stagger off), so each takes the gap fetch `[06-09, 06-10]` (`ohlcv_archive.py:841-853`). `_yf_download_window` passes `end + 1 day` (`:285-292`), so AAA gains 06-09 and 06-10, and NOB gains 06-09 only;
  - RSE has no archive, so it takes the full refresh. The fetch is empty and there is no archive, so it returns None (`:816-835`); `_fetch_bars_window` returns None and `get_or_fetch` raises, on each of its two detections.
- **The no-memo world (`memo=False`):** the H (ii) wrapper, `real = rmod._bar_for_date; mp.setattr(rmod, "_bar_for_date", lambda *a, memo=None, **k: real(*a, **k))`.
- **Both worlds** count the real resolve as `_count_resolve` does.
- **Return value:** `rows` (`SELECT detection_id, observation_date, ohlc_today_json, status, status_change_event, sessions_since_detection FROM pattern_forward_observations ORDER BY detection_id, observation_date`; `created_at` and `observation_id` are excluded by name, P12), `warnings` (`w`), `reads`, `downloads` (the observe-phase `(ticker)` list), and `shape_a`, the frames `pd.read_parquet` returns for `AAA.yfinance.parquet` and `NOB.yfinance.parquet`.

`test_observation_rows_identical_with_and_without_the_memo` asserts:
1. `len(rows) == 3` (the AAA detections) in both worlds, and `rows_nomemo == rows_memo`.
2. The warnings are equal once the `resolve_reads` key is popped from each `observe_load` entry. That covers five no-bar entries (NOB x3, RSE x2) in detection order, and `fetch_window == 4` and `in_memory_hit == 4` in both worlds. The arithmetic: AAA and NOB each miss once, then hit twice; RSE misses and raises twice.
3. In the no-memo world reads 8 == rr 8; in the memo world reads 4 == rr 4 (AAA 1 + NOB 1 + RSE 2).
4. `downloads_nomemo == downloads_memo`: the populate is identical by D1.
5. `shape_a` is equal frame for frame across the worlds (`pd.testing.assert_frame_equal`). This pins C-2's content side.

Pre-fix: (1), (2), (4) and (5) hold (they are invariants), and (3) raises KeyError, so RED. Their teeth are the T2 step 3 mutations:
- M1 makes the memo world's reads 3 (RSE det2 hits RSE det1's empty pair), so (3) is RED.
- M3 makes the memo world's `in_memory_hit` 0, so (2) is RED.
- M4 memoizes `(df, {})`, so AAA d2 and d3 return None, and (1) reads 1 row against 3: RED.

Run: every T1 test RED as tabulated.

**Step 2, GREEN** in `runner.py`.

(a) Directly above `_bar_for_date`:
```python
def _observe_memo_key(ticker: str, observation_date: str) -> tuple[str, str]:
    """The observe step's per-step read-memo key (D89): the ticker exactly as
    the caller passed it, and the observation date."""
    return (ticker, observation_date)
```

(b) `_bar_for_date`:
- **Signature:** `def _bar_for_date(cfg, ohlcv_cache, ticker: str, observation_date: str, *, memo: dict | None = None):`.
- **Docstring (replaces :3074-3083 entirely):**
  ```
  Return an ohlc dict (with provider) for exactly ``observation_date``, or
  None if the archive has no bar for that session.

  OQ-17 read path: (1) populate/refresh the archive via
  ``ohlcv_cache.get_or_fetch`` (best-effort: a raise is logged and step 2's
  read stays authoritative). A TTL hit does no I/O. On a miss, the pipeline's
  cache fetches through the Schwab market-data ladder when the run has a
  Schwab client (``_install_pipeline_marketdata_caches`` installs the ladder's
  bars hook; the ladder applies its own environment check and yfinance
  fallback), and through ``read_or_fetch_archive`` when it has none. (2) read
  the date-anchored bar + provider provenance via resolve_ohlcv_window (keyed
  end=observation_date). Selects the row whose asof_date == observation_date
  (NOT iloc[-1]); freezes it; never re-reads it later (#26 elimination
  honest).

  ``memo`` (D89): the observe step passes one dict per step call, keyed by
  ``_observe_memo_key``. When the key is present, step 2 selects from the
  memoized ``(df, provenance)`` pair and does not read the archive, whatever
  this call's populate did. When it is absent, step 2 reads the archive and
  stores the pair ONLY if this call's populate returned without raising (bar
  or no bar). ``memo=None`` reads on every call and stores nothing.
  ```
- **The populate:** set `populate_ok = True` before the `try`. The `except` arm sets `populate_ok = False`, then logs as today.
- **Comment (:3099-3106):** keep its text and add one line: `populate_ok records whether THIS call's get_or_fetch returned without raising (the D89 memo write condition).`
- **Comment (:3114-3117):** keep its text and add: `With a memo (D89): a present key is selected from, never re-read; an absent key is read and stored only when populate_ok.`
- **Around the resolve call:** keep `start` exactly as computed today, then:
  ```python
  key = _observe_memo_key(ticker, observation_date)
  if memo is not None and key in memo:
      df, provenance = memo[key]
  else:
      df, provenance = resolve_ohlcv_window(
          ticker, start=start, end=observation_date,
          cache_dir=cfg.paths.prices_cache_dir,
      )
      if memo is not None and populate_ok:
          memo[key] = (df, provenance)
  ```
- **Selection (:3123-3140):** UNCHANGED.

(c) `_step_pattern_observe`:
- After `_observed_count = 0`:
  ```python
  # D89 per-step read memo: _observe_memo_key -> the (df, provenance) pair
  # resolve_ohlcv_window returned. A local; it never outlives this call.
  memo: dict = {}
  _resolve_reads = 0
  ```
- Replace :3255 with:
  ```python
  if _observe_memo_key(det.ticker, observation_date) not in memo:
      _resolve_reads += 1  # a memo miss: this call reads the archive
  bar = _bar_for_date(cfg, ohlcv_cache, det.ticker, observation_date,
                      memo=memo)
  ```
- In the `observe_load` entry, add `"resolve_reads": _resolve_reads,` after `"in_memory_hit"`. Append to the comment above it: `resolve_reads = resolve_ohlcv_window calls this step made (memo misses, D89).`

Run: every T1 test passes, then `python -m pytest tests/pipeline -q -m "not slow"`.

Commit: `feat(pipeline): T1 -- observe's per-step read memo after a non-raising populate (D89)`.

### T2 -- suite, ruff, closure, mutations, then the executing review

1. Run `python -m pytest -m "not slow" -q` to green and read the tail. Run `ruff check swing/`.
2. **Closure, each quoted with its output in the exec ledger:**
   - `grep -n -i "zero schwab" swing/pipeline/runner.py` returns nothing. Today it returns `:3078` only.
   - `grep -rn --include=*.py "observe_load" swing/` returns `runner.py`'s entry line and its entry-reset comment only (K-6).
   - `grep -n "memo" swing/pipeline/runner.py`: every hit is inside `_observe_memo_key`, `_bar_for_date` or `_step_pattern_observe`.
   - `git diff --stat main...HEAD -- swing/data swing/web swing/trades` is EMPTY. `git diff --stat main...HEAD -- swing` names `swing/pipeline/runner.py` only.
3. **Mutation checks.** Each is a scratch edit to `runner.py`, run, seen red, then `git checkout -- swing/pipeline/runner.py` and `git diff --exit-code swing` returning 0. Quote each in the exec ledger.

| id | scratch edit | tests that must go RED |
|---|---|---|
| M1 (RD's, quoted in the merge report) | the memo write drops `and populate_ok` | T-H1, T-H2, N-V (3) |
| M2 | `memo` becomes a module-level dict that `_step_pattern_observe` reuses | T-lifetime |
| M3 | the populate runs only when `memo is None or key not in memo` | T-load, N-V (2) |
| M4 | the memo stores `(df, {})` | N-V (1) |
| M5 | `_observe_memo_key` returns `(ticker,)` | T-key |

4. **The W5 (ii) replay and the W7 byte-equality** over live-shaped copies (scratch, evidence dir `exec\`):
   - copy `round0\p07_replay.py` to `exec\w07_replay.py` and add two modes:
     - `merged_nomemo` calls `R._bar_for_date(cfg, oc, t, OBS)`;
     - `merged_memo` calls `R._bar_for_date(cfg, oc, t, OBS, memo=memo)` with ONE dict for the whole replay;
   - run both over `round0\iters195.json` and the p03 snapshot, then compare the two jsonl files with `round0\p11_compare_rows.py`;
   - expected: byte-equal, and resolve calls 7,139 against 248 (p07 `memo_frame` measured 248 on the prototype).
5. **Then the executing Reviewer A loop (`strong`),** per the recipe.

## Test roster (complete; method: every test named in T1, plus the existing files that patch `resolve_ohlcv_window` or call or wrap `_bar_for_date`, by read)

| file | added | edited | deleted |
|---|---|---|---|
| `tests/pipeline/test_observe_read_memo.py` (new) | T-H1, T-H2, T-C3, T-E, T-key, T-lifetime, T-load | -- | -- |
| `tests/pipeline/test_observe_read_memo_neutrality.py` (new) | N-V | -- | -- |

Existing files UNCHANGED, each read for whether the memo moves its assertions (ledger K-8):
- **The six files that patch `resolve_ohlcv_window`:**
  - `test_step_pattern_observe.py`: single-detection tests. `_drifted` relies on AL-6.
  - `test_observe_load_instrumentation.py`: distinct tickers; asserts single keys only.
  - `test_pattern_pool_dormant_levers.py`: the wrappers use `*a, **k` and AL-5's keyword.
  - `test_fetch_vs_write_ordering.py`: counts `get_or_fetch` calls, which D1 keeps per detection.
  - `test_phase14_temporal_log_e2e.py`: a `return_value` patch, so every read returns the same value.
  - `test_step_evaluate_warm_neutrality.py`: one detection.
- **The direct 4-positional callers** of `_bar_for_date` (the memo=None path): `test_observe_remediation.py`, `test_lock_guard_completed_day.py`, `test_detect_observe_window.py`.

The full suite in T2 step 1 is the check.

## Not changed (explicit)

- `resolve_ohlcv_window`, `_backward_compat_rename`, `write_window`, `read_or_fetch_archive` (nothing under `swing/data/`).
- `OhlcvCache.get_or_fetch` and `_fetch_bars_window`, the ladder hook and its install (D90's).
- The populate's call (`window_days=DETECT_OBSERVE_WINDOW_DAYS`), the L3 completed-day guard, the in-function import, and the selection lines (:3123-3140).
- The observe loop's order, the idempotency skip, the watch shed, the no-bar and non-finite warnings (their payloads feed `research_health._skip_pairs_for_run`, :1143-1160, unchanged), `_advance_status`, the row build, the write pass.
- `observe_load`'s `step`, `metric`, `observed`, `fetch_window` and `in_memory_hit`.

## Owner docs that restate a changed fact (LISTED for their owners; this plan edits none)

| owner | site | what goes stale |
|---|---|---|
| CHARC | `docs/tool-director-context.md`, row D89 | the closing disposition at merge; "~248 reads" becomes the measured `resolve_reads` |
| orchestrator | the D84 widening brief, when written | the observe cost model (per-ticker reads, not per-detection) |

## Merge-report checklist (W1-W7 in F8's form, as ruled; ledger 1.3)

The baseline is run 195, from `round0\p01_run195.out.txt`. The post-merge night is measured by `round0\p01_run195.py <run_id>` (the script takes the run id).

| item | run 195 (baseline, pre-merge) | first post-merge night (expected shape) |
|---|---|---|
| W1 step wall (the lease line; window = finish stamp minus N) | 541,691 ms | lower by about the remainder saved |
| W2 audited fetch term | Schwab 238 calls / 87,395 ms; yfinance 8 / 9,955 ms; total 97,350 ms | unchanged in kind (the memo leaves the fetch term alone) |
| W3 iterations = rows + no-bar + non-finite | 6,934 + 205 + 0 = 7,139 | the night's own count |
| W4 (W1 - W2) / W3, an UPPER bound (L-4) | 62.24 ms | about 6-7 ms |
| W5 (iii) `resolve_reads`, beside (ii) the T2 step 4 replay count | the field is absent; replay 7,139 to 248 | about the distinct tickers reaching `_bar_for_date` (248 on run 195) plus any re-reads after a raise |
| W6 `observe_load` against its shape | `{"observed": 6934, "fetch_window": 238, "in_memory_hit": 6901}` | the same three keys, unchanged in meaning, plus `resolve_reads` last |
| W7 neutrality | -- | N-V's two row sets from `run_world(..., memo=False/True)` (scratch script), M1 with T-H1 red, and the T2 step 4 byte-equality |

Also quoted:
1. **The Schwab-ladder state of each quoted night.** These are the `schwab_api_calls` rows for the run. On a ladder-ON night W2 carries the Schwab term and W4 stays an upper bound (L-4).
2. **H3's re-open trigger, in these words:** "any observe wall above 1,800 s on the merged code re-opens H3 for a read."
3. **H4's width, in these words:** "today the race is per detection; with the memo it is per ticker per step; zero incidence over 87 runs."
4. **T-E,** stated as the declared difference inside H3 (L-3), with E1 named as the orchestrator's ruling, open to either director at the plan-stage read.
5. **The closure greps** (T2 step 2) with their outputs, and the suite tail on the final head.
6. **C-2 (AL-12),** restated for the directors with N-V (5).
