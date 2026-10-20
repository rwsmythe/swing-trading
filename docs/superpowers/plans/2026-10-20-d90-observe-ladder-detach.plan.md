# D90 (detach the Schwab ladder from observe's populate) -- implementation plan

**Ledger (rulings verbatim, census, intake corrections, kept claims, review history):** `docs/superpowers/plans/2026-10-20-d90-observe-ladder-detach.plan.ledger.md`. This plan cites ledger sections by number and restates none of their reasoning.
**Brief:** `docs/d90-observe-ladder-detach-plan-dispatch-brief.md` (@ `e7f91d80`), with the orchestrator's two resume directives (ledger 1.5).
**Base:** `main` @ `e7f91d80`. Every file:line below was re-read there. `git diff --stat e7f91d80 d81f35ba -- swing tests scripts` is empty, so the anchors hold at the main SHA the rulings were read at (`d81f35ba`).
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d90-detach\plan\` (`round0\` = the census probes p1-p5, the parquet copies, p20-p22; `round<N>\` = this plan's review rounds).

## Header

### Declared envelope

**IN**
- `swing/web/ohlcv_cache.py`, `OhlcvCache` only:
  - `get_or_fetch` (:175): one keyword-only parameter `use_ladder: bool = True`; the call at :235-237 passes it on; the docstring's Routing paragraph (:197-202) is replaced.
  - `_fetch_bars_window` (:253): the same keyword-only parameter `use_ladder: bool = True`; the branch at :270 becomes `if use_ladder and self._ladder_bars_fetcher is not None:`; one docstring sentence.
- `swing/pipeline/runner.py`:
  - `_bar_for_date`: the populate call (:3132) passes `use_ladder=False`; the docstring (:3080-3102) is replaced; the first line of the step-1 comment (:3118) is replaced.
  - `_step_pattern_observe`: the compute-pass comment (:3252-3255) is replaced.
  - `_install_pipeline_marketdata_caches`: the "Consumer surfaces" docstring paragraph (:365-369) is replaced. Code untouched.
- Tests: three NEW files; the by-name stub sweep S1-S9 (T1 table); ONE test function deleted, SUPERSEDED BY NAME (X1).

**OUT**
- Any schema, migration, dependency or new module.
- `swing/data/` (`resolve_ohlcv_window`, `read_or_fetch_archive`, `_backward_compat_rename`, `write_window`), `swing/integrations/` (the ladder, the wrapper), `swing/latches/`, `swing/web/app.py` (the web process's own bars hook).
- In `ohlcv_cache.py`: `_fetch_bundle_worker` (:470, the dashboard's read), `set_ladder_bars_fetcher`, the `_bars_store` key, the telemetry.
- In `runner.py`: the five other `get_or_fetch` callers (detect :2191, :2453; charts :3513, :3584, :3718), the bars hook and its install code, the L3 guard, `populate_ok`, the D89 memo, the `resolve_ohlcv_window` call (:3148-3151, byte-identical), the selection, the observe loop, `observe_load`.
- An explicit `endDate` (RD's measurement call forbids it). Branch B (declined, ledger 1.1). The uniform-source read (BANKED, owner RD, ledger 1.1). The 9,474 existing `schwab_api` rows (RD: nothing).
- Owner docs (listed at the end; this plan edits none).

### Accepted limitations (each WITH its reason; challenge invited)

- **L-1, carry nights change the provider LABEL (RD, ledger 1.1 (a)).** Admissibility (1), restated in RD's words: "neutral on non-carry nights by construction; on a carry night, observe-only tickers record yfinance where today they would record schwab_api, value-equivalent at the cent (measured), provenance label differs". Reason: the two providers agree on the observation date (carry dates p99 0.00% over 2,623 pairs, RD's measurement). The change is declared, pinned by the N-V carry pair, and recorded at merge as a VII.F boundary note.
- **L-2, mixing is narrowed, not removed (RD, 1.1 reason 2 and the BANKED item).** On a carry night a detect-pool ticker still records `schwab_api`, because detect's populate keeps the ladder. A ticker whose `schwab_api` parquet the web process refreshed also can. Reason: the uniform-source read needs a `swing/data` carve-out to remove a value-equivalent label mix on about two nights a year. BANKED, owner RD, with RD's trigger.
- **L-3, admissibility (2)'s residual (row, RD 20261020T054502Z).** An observe-only ticker's `{T}.schwab_api.parquet` stops advancing from the detach night. A latched, then rotated, never-viewed ticker carries a provider-mixed range. Reason: no reader asserts prior-date Schwab presence or freshness (RD's whole-`swing/` read). It is stated in the merge report.
- **L-4, the N-V hook patches the Schwab LEG, not the wrapper.** The N-V worlds run the REAL `fetch_window_via_ladder` and the REAL `resolve_full_archive_bars` in the production hook's composition (`runner.py:481-506`). Only `get_price_history` is replaced, by a fixture that returns a window or raises `SchwabApiError`. Reason: RD's (c) names a patched hook, with carry as a fixture parameter and no clock. The wrapper and its audit rows are pinned elsewhere (`tests/pipeline/test_bars_hook_schwab_success_returns_full_archive.py`, `tests/pipeline/test_bars_hook_requests_daily_frequency.py`).
- **L-5, stub-sweep scope (ledger 2.2, interpretations I-1 and I-2).**
  - The by-name roster is every cache class the runtime census (p20) saw reach `_bar_for_date`, plus the one instance `_fetch_bars_window` lambda broken by the threading (S7).
  - The shared `_StubOhlcvCache` is pinned ONCE, by T-stub, because the defect is per class signature. Its 15 users are not each edited.
  - Two class-level `OhlcvCache.get_or_fetch` patches in full-pipeline chart tests are MEASURED UNREACHED (p21: zero `_bar_for_date` calls over 19 tests) and stay unchanged.
  - Detect, charts, web and trades stubs never reach observe and stay unchanged.
  - Reason: the hazard is fixture-only (the production cache always accepts the keyword). T2 step 2 re-runs the census on the head as the closure check. No permanent meta-test is added.
- **L-6, witness attribution (I-3).** If D90 merges before a post-D89 nightly exists, the first post-merge night carries D89 and D90 together. The wall drop is then reported against run 195 as a combined figure, with the Schwab term isolated by the audit table. Sequencing is the orchestrator's call.

### Executing posture

- **Cell (recommendation; the orchestrator rules):** `implementer-opus-high`. The reason, named under recipe section 2A: measurement-chain code. `_bar_for_date` produces the bar that enters the append-only observation log.
- **TDD:** T1 is RED, then GREEN, then ONE commit: `feat(pipeline): T1 -- observe's populate never reaches the Schwab ladder (D90)`. No amend. `%(trailers)` empty. No final `-m` paragraph starting `Word:`.
- **The FULL fast suite** (`python -m pytest -m "not slow" -q`) runs to green BEFORE the executing review and again on the final head. `ruff check swing/` must be clean.
- **Executing review:** `strong`, with REPO ACCESS. If you use a stdin bundle, include the diff plus:
  - `runner.py:329-512`, `runner.py:3073-3370`;
  - `ohlcv_cache.py:117-311` and `470-518`;
  - `marketdata_ladder.py:166-221` and `386-555`;
  - `app.py:545-602`;
  - `ohlcv_archive.py:773-853`, `971-1056` and `1194-1351`;
  - `tests/pipeline/conftest_temporal.py`, and every test file the T1 table edits.
- **Supersession is by REPLACEMENT.** Every docstring and comment is rewritten in T1, the task that makes the new text true.

## Assumption locks (design choices; one-line reasons; the argument is in the ledger)

- **AL-1, the keyword (CHARC FORM, ledger 1.4).** `get_or_fetch(self, *, ticker: str, window_days: int = 180, use_ladder: bool = True)`. Keyword-only and additive. The default keeps every other caller on today's path (pinned by T-D1 and T-D4).
- **AL-2, the threading.**
  - `get_or_fetch` ALWAYS calls `self._fetch_bars_window(ticker=ticker_upper, window_days=int(window_days), use_ladder=use_ladder)`.
  - `_fetch_bars_window(self, *, ticker: str, window_days: int, use_ladder: bool = True)` branches on `use_ladder and self._ladder_bars_fetcher is not None`; the `else` arm is today's `read_or_fetch_archive` arm, unchanged.
  - Consequence: every instance replacement of `_fetch_bars_window` must accept the keyword (S7, S8).
- **AL-3, the store (CHARC FORM; kept claim K-2).** The `_bars_store` key stays `(ticker_upper, window_days)` and is shared across both settings. A TTL hit serves either setting. Pinned by T-D2.
- **AL-4, observe's call (RD, Branch A).** It is `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=DETECT_OBSERVE_WINDOW_DAYS, use_ladder=False)`: a literal `False`, on every call. There is no clock read and no predicate.
- **AL-5, nothing else in `_bar_for_date` moves.** The L3 guard, `populate_ok`, the memo rule, the `resolve_ohlcv_window` call and the selection are byte-identical.
- **AL-6, the bundle worker is untouched.** `_fetch_bundle_worker` reads `self._ladder_bars_fetcher` directly (`ohlcv_cache.py:491`) and never sees `use_ladder`. Pinned by T-D3.
- **AL-7, the five other pipeline callers stay on the ladder.** They are detect :2191 and :2453, and charts :3513, :3584 and :3718 (p22). None passes the keyword, so each takes the default. Pinned by T-D4 (static) and T-D1 (default reaches the hook).
- **AL-8, the superseded test (RD + CHARC, ledger 1.1, 1.3).** `test_observe_remediation.py::test_success_path_overwrites_contaminated_before_lock` is DELETED. A by-name comment block at its site states the hazard, what closes it now, and its replacement, T-NS. It is not edited into something else.
- **AL-9, no carry predicate anywhere.** The carry world exists only in the N-V fixture, as `schwab_end` on the patched Schwab leg.

## Task ladder

### T1 -- the keyword, observe's opt-out, the texts, the sweep, the supersession (two swing files; three new test files; by-name test edits)

**Step 1, RED.** Write the three new files and make every edit in the sweep table. Then run them.

**Shared harness notes:**
- **Dates:** `_OBS = "2026-05-29"` in the observe unit tests, as in `test_observe_read_memo.py`. The N-V uses D89's `_DATES` / `_SESSION = 2026-06-10`.
- **The D89 test cfg** (`_test_cfg`, `test_observe_read_memo.py:43-50`): `cfg = _cfg(tmp_path, db_path)`. Attach `cfg.web = SimpleNamespace(ohlcv_cache_ttl_seconds=3600, max_concurrent_ohlcv_fetches=4)` and `cfg.archive = SimpleNamespace(archive_history_days=1260)` BEFORE `OhlcvCache(cfg)` is built.
- **Clock patches** (every observe unit test that builds a real cache): `arch._last_completed_session_today`, `swing.web.ohlcv_cache.last_completed_session` and `swing.pipeline.runner.last_completed_session`, all to the test's session. Also `arch._load_archive_config_for_stagger -> False`, with `arch._full_refresh_stagger_enabled.cache_clear()` before and after (D89 N-V :130-135).

**New file A: `tests/pipeline/test_ohlcv_cache_use_ladder.py` (the cache surface).**
- **Harness:**
  - `cfg = _make_cfg(tmp_path)` from `tests.pipeline.test_ohlcv_cache_shape_parity` (import precedent: `test_observe_load_instrumentation.py:43`).
  - Patch `swing.web.ohlcv_cache.last_completed_session` to `date(2026, 6, 10)`.
  - `frame_l = _fixture_daily_bars(end=pd.Timestamp("2026-06-10"), n_rows=240)` and `frame_a = frame_l + 1.0`, two distinguishable sources. 240 business days span fewer than 400 calendar days, so a 400-day slice keeps every row.
  - `hook(t)` appends `t` to `hook_calls` and returns `(frame_l, "yfinance")`.
  - `swing.web.ohlcv_cache.read_or_fetch_archive` is patched with a recorder that appends `(ticker, end_date, cache_dir, archive_history_days)` and returns `frame_a`.
  - Frames are compared with `pd.testing.assert_frame_equal(..., check_freq=False)`: a boolean-mask slice drops the `B` freq.

| id | test | asserts (post-fix) | pre-fix | mutants killed |
|---|---|---|---|---|
| T-D1 | `test_default_and_true_reach_the_ladder_hook` | Fresh cache 1: `get_or_fetch(ticker="aaa", window_days=400)` gives `hook_calls == ["AAA"]`, archive recorder empty, result equals `frame_l`. Fresh cache 2: the same with `use_ladder=True`. `inspect.signature(OhlcvCache.get_or_fetch).parameters["use_ladder"]` is KEYWORD_ONLY with default `True` | `KeyError` on the parameter, and `TypeError` on `use_ladder=`: RED | M4 (default `False`): the hook is not called: RED |
| T-D2 | `test_false_skips_the_hook_and_shares_the_store` | Fresh cache with the hook: `get_or_fetch(ticker="AAA", window_days=400, use_ladder=False)` gives `hook_calls == []`, and the recorder holds exactly `[("AAA", date(2026,6,10), cfg.paths.prices_cache_dir, cfg.archive.archive_history_days)]`; the result equals `frame_a`. Then a default call on the same cache is a TTL hit: still `hook_calls == []`, result `frame_a`, `drain_telemetry() == {"in_memory_hit": 1, "fetch_window": 1}`. Reverse order on a fresh cache: default first (hook once), then `use_ladder=False` is a hit, the recorder stays empty, telemetry 1/1 | `TypeError`: RED | M2 (keyword not passed on), M3 (branch ignores it): the hook is called: RED. M5 (key gains `use_ladder`): the second call misses: RED |
| T-D3 | `test_bundle_worker_still_calls_the_hook` | `bundle, healthy = cache._fetch_bundle_worker("AAA")` with the hook installed gives `hook_calls == ["AAA"]`, `bundle.provider == "yfinance"` and `healthy is True` | GREEN (an invariant pin, AL-6) | a future routing of the worker through `_fetch_bars_window` |

**New file B: `tests/pipeline/test_observe_ladder_detach.py` (observe's opt-out).**
- **T-NS** `test_observe_populate_never_reaches_the_ladder_hook`: the brief's discriminating test, and the REPLACEMENT for X1 (RD's form, CHARC's store-miss form).
  - **Setup:**
    - `conn, db_path = tmp_db_at_head`, with one detection: `_plant_detection(conn, ticker="OOT", data_asof_date="2026-05-25", detection_date="2026-05-26")`.
    - The D89 test cfg and the clock patches at `_OBS`.
    - A legacy `OOT.parquet` written with `arch._write_archive_atomic`: a DatetimeIndex frame with capitalized OHLCV and rows 05-27, 05-28 and 05-29. Each row has O=H=L=C, at 8.7, 8.8 and 9.0, and `Volume` 1e6. Plus `OOT.meta.json` `{"last_full_refresh_date": "2026-05-29"}` via `arch._write_meta_atomic`. The archive is then current and no refresh is due, so the populate downloads nothing.
    - `arch.yf.download` is patched to record any call; the test asserts that list stays empty.
    - A FRESH real `OhlcvCache(cfg)` with a recording hook installed by `set_ladder_bars_fetcher`. The hook appends the ticker, then writes a carry-shaped `schwab_api` row for 05-29 with close 9.5 through `write_window` (as `test_observe_remediation.py:47-49` does), then returns `(_build_bars(), "yfinance")`.
    - The instance `_fetch_bars_window` is wrapped by a spy that appends its kwargs to `seen` and delegates to the real bound method.
  - **Anti-vacuity (CHARC 1.3):** `assert cache._bars_store == {}` immediately before the drive. A store miss is the only road to the hook.
  - **Drive:** `_step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 1, _OBS), ohlcv_cache=cache, run_warnings=w)` under `patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS)`.
  - **Asserts:**
    - `hook_calls == []`;
    - `seen == [{"ticker": "OOT", "window_days": 400, "use_ladder": False}]`;
    - the row's close is 9.0 and its `provider` is `"yfinance"`;
    - `load(w)["fetch_window"] == 1` (the miss happened);
    - `(cache_dir / "OOT.schwab_api.parquet")` does not exist;
    - no `yf.download` call.
  - **Pre-fix (the flag absent, which is CHARC's "RED with the flag removed"):** the hook is called once, the row is 9.5 / `schwab_api`, and `seen` lacks the key: RED. **M1** (the flag set `True`): RED.
- **T-stub** `test_shared_stub_records_use_ladder_false_and_the_populate_reports_ok`: pins S1, in RD's form plus CHARC's.
  - **Setup:** `_StubOhlcvCache({"AAA": _build_bars()})`, and two AAA detections: `data_asof_date="2026-05-25"`, `detection_date`s 05-26 and 05-27. File B defines `load(w)` as `test_observe_read_memo.py` does.
  - **Drive:** observe with `resolve_ohlcv_window` patched to `_stub_window(9.0, date_=_OBS)` and `lease_data_asof` patched, as `test_observe_load_instrumentation.py:30-35` does.
  - **Asserts:** `[c["use_ladder"] for c in cache.calls] == [False, False]` (the populate runs on every call, D89 D1). `load(w)["resolve_reads"] == 1`: the first populate did not raise, so the memo stored it, which a swallowed `TypeError` would have prevented (that world reads 2).
  - **Pre-fix:** the stub records `True` (observe passes nothing): RED.
- **T-D4** `test_only_observes_populate_passes_use_ladder` (static closure; prototype `round0\p22_get_or_fetch_ast.py`).
  - **Walk:** `ast.parse` every `swing/**/*.py`, with `encoding="utf-8"`. For every `ast.Call` whose `func` is an `ast.Attribute` named `get_or_fetch`, record `(posix path, outermost top-level def name, value of a use_ladder keyword if present)`.
  - **Assert:** the calls carrying the keyword are exactly `[("swing/pipeline/runner.py", "_bar_for_date", False)]`. Also assert that at least 10 calls are found, so a broken walk fails instead of passing empty (p22: 10).
  - **Pre-fix:** none carry it: RED.

**New file C: `tests/pipeline/test_observe_ladder_detach_neutrality.py` (the N-V two pairs, RD (c)).**

Its shape is D89's N-V (`test_observe_read_memo_neutrality.py`): `run_world(tmp_path, *, detach: bool, carry: bool) -> dict` applies its own patches inside `pytest.MonkeyPatch.context()`, so a scratch script can call it for the merge report.

**The world:**
- **Dates and archives:** D89's `_DATES`, `_SESSION = 06-10`, `_bar(i)`, `_table_frame` and `_window_dates`, plus the clock and stagger patches (D89 N-V :130-135).
- **The local duck-typed `_Cfg`:** D89's, plus `integrations.schwab.environment = "production"` and `integrations.schwab.marketdata_ladder_enabled = True`. Those are the attributes `_is_ladder_active` reads (`marketdata_ladder.py:242-257`).
- **DB:** at head, with a `pipeline_runs` row `id=1` (data_asof 06-10), as D89's :111-116. Three tickers, two detections each, `data_asof_date="2026-06-05"`, `detection_date`s 06-05 and 06-08:
  - **OOT**, observe-only; its Schwab leg succeeds;
  - **DPT**, the detect pool; stored by a detect-shaped call before observe;
  - **FBK**, observe-only; its Schwab leg raises, so the ladder's yfinance fallback runs (census kept claim K-5).
- **Legacy archives** for all three: 06-04, 06-05 and 06-08, plus `.meta.json` `{"last_full_refresh_date": "2026-06-08"}`.
- **The fake `yf.download`:** honours `start <= d < end` as D89's does, serves `_DATES` to every ticker, and records `(phase, ticker)`.

**The patched hook (RD (c); L-4):**
- `schwab_end = date(2026, 6, 10) if carry else date(2026, 6, 9)`.
- `mp.setattr(swing.integrations.schwab.marketdata_ladder, "get_price_history", fake)`. The fake records `(phase, ticker)`, which is the in-fixture Schwab call count:
  - for FBK it raises `SchwabApiError(503, "")`;
  - for any other ticker it returns `SchwabPriceHistoryWindow(ticker=t, bars=[OhlcvBar(asof_date=d.isoformat(), open=10.0+i, high=11.0+i, low=9.0+i, close=10.5+i, volume=1000+i) for i, d in enumerate(_DATES) if d <= schwab_end])`.

  These are the same bars as `_bar(i)`, so the test pins a LABEL only.
- The hook mirrors `runner.py:481-506`:
  ```python
  def _yf_window(t, start, end):
      return arch.read_or_fetch_archive(t, end_date=_SESSION, cache_dir=cache,
                                        archive_history_days=1260)

  def _hook(t):
      window, tag = ladder.fetch_window_via_ladder(
          t, start=None, end=None, cfg=cfg, schwab_client=object(),
          yfinance_fallback_fn=_yf_window, conn=None, surface="pipeline",
          pipeline_run_id=1, period_type="year", period=5,
          frequency_type="daily", frequency=1)
      return ladder.resolve_full_archive_bars(t, window, tag,
                                              yfinance_window_fn=_yf_window)
  ```
- The cache: `oc = OhlcvCache(cfg)` and `oc.set_ladder_bars_fetcher(_hook)`.

**The two worlds:**
- **detach=False, today's world:** `real = OhlcvCache.get_or_fetch`, then `mp.setattr(OhlcvCache, "get_or_fetch", lambda self, *, use_ladder=True, **k: real(self, use_ladder=True, **k))`. This is the pre-D90 populate, which reached the ladder on every miss; the wrapper form is D89's H (ii) precedent.
- **detach=True:** production as merged.

**The run:**
- `phase = "detect"`, then `oc.get_or_fetch(ticker="DPT", window_days=rmod.DETECT_OBSERVE_WINDOW_DAYS)`, the call detect makes at :2191.
- Then `store_before_observe = set(oc._bars_store)`.
- Then `phase = "observe"` and `rmod._step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 1, "2026-06-10"), ohlcv_cache=oc, run_warnings=w)`.

**Return value:**
- `rows`: D89's six-column SELECT, ordered by `detection_id, observation_date`; `created_at` and `observation_id` are excluded by name;
- `warnings`;
- `schwab_calls`;
- `downloads` (observe phase);
- `store_before_observe`;
- `det_ids`, a dict from ticker to detection ids;
- `schwab_files`: `{t for t in ("OOT","DPT","FBK") if (cache / f"{t}.schwab_api.parquet").exists()}`.

**`test_ordinary_night_rows_equal_with_and_without_the_detach`** (`carry=False`) asserts:
1. Six rows in each world, `today["rows"] == detach["rows"]`, and every row's `json.loads(ohlc_today_json)["provider"] == "yfinance"`.
2. `today["warnings"] == detach["warnings"]`. In `observe_load`, `observed` 6, `fetch_window` 2 (the OOT and FBK misses) and `in_memory_hit` 4. `resolve_reads` is 3, one per ticker after a non-raising populate (D89).
3. In both worlds, the detect-phase Schwab calls are `[("detect","DPT")]`. The observe-phase Schwab calls are `[("observe","OOT"), ("observe","FBK")]` today and `[]` with the detach. That `[]` is the witness, in-fixture.
4. `store_before_observe == {("DPT", 400)}` in both worlds. This is CHARC's anti-vacuity: OOT and FBK miss the store.
5. `today["schwab_files"] == {"OOT","DPT"}` and `detach["schwab_files"] == {"DPT"}`. This is admissibility (2)'s residual, in-fixture.
6. `today["downloads"] == detach["downloads"]`: the archive refresh is the same, D90 removes only the Schwab leg.

**`test_carry_night_rows_differ_only_on_the_observe_only_provider_label`** (`carry=True`) asserts:
1. Six rows in each world, in the same `(detection_id, observation_date)` order. For every pair, `detection_id`, `observation_date`, `status`, `status_change_event` and `sessions_since_detection` are equal. The parsed `ohlc_today_json` dicts are equal once `provider` is popped from each: OHLC and volume are equal, so it is a label only.
2. The detection ids whose `provider` differs are EXACTLY `set(det_ids["OOT"])`. OOT is `schwab_api` today and `yfinance` with the detach. DPT is `schwab_api` in both worlds (L-2). FBK is `yfinance` in both.
3. Assertions (2)-(6) of the ordinary test hold here as well. The warnings are equal.

**N-V pre-fix behaviour:** the today-world wrapper passes `use_ladder=True`, which `get_or_fetch` does not accept, so the run raises `TypeError`: RED. The teeth after GREEN come from M1: the detach world becomes the today world, so ordinary (3) and (5) and carry (2) go RED.

**The by-name sweep (edits to existing files).** Every swept stub becomes a RECORDING stub, and its test asserts the keyword REACHED it (CHARC 1.3), not only that `populate_ok` stayed True. Method: the census in ledger 2.2 (p20 runtime census plus a static read).

| id | stub (file:line) | edit | assertion (test) |
|---|---|---|---|
| S1 | `tests/pipeline/conftest_temporal.py:64` `_StubOhlcvCache.get_or_fetch` | add `use_ladder: bool = True`. `__init__` sets `self.calls = []`. Append `{"ticker": ticker, "window_days": window_days, "use_ladder": use_ladder}` BEFORE the `KeyError` branch | T-stub (new). The 15 users (p20) are unchanged (L-5, I-1) |
| S2 | `tests/pipeline/test_detect_observe_window.py:46` `_RecCache.get_or_fetch` | signature `(self, *, ticker, window_days, use_ladder)`, a REQUIRED keyword; append `(window_days, use_ladder)` | `test_observe_populate_uses_the_window_constant`: `recorded == [(401, False)]` (was `[401]`) |
| S3 | `tests/pipeline/test_fetch_vs_write_ordering.py:53` `_DeadlockProbeCache.get_or_fetch` | add `use_ladder: bool = True` (the detect tests also use it). `__init__` sets `self.use_ladder_seen = []`, appended as the call's first statement | `test_observe_bar_fetch_runs_outside_fence_no_deadlock` and `test_observe_split_preserves_idempotency_and_observed_count`: after the first drive, `cache.use_ladder_seen == [False]` |
| S4 | `tests/pipeline/test_lock_guard_completed_day.py:42` `_Cache.get_or_fetch(self, **k)` | record `k` into a test-local `seen` | `test_bar_for_date_allows_completed_day`: `seen == [{"ticker": "AAPL", "window_days": runner.DETECT_OBSERVE_WINDOW_DAYS, "use_ladder": False}]` |
| S5 | `tests/pipeline/test_observe_load_instrumentation.py:20` `_TeleStub.get_or_fetch` | add `use_ladder: bool = True`; `self.use_ladder_seen` recorded | `test_observe_emits_fetch_telemetry_metrics_entry`: `== [False, False]`. `test_observe_load_excludes_prior_step_fetches`: `== [True]*5 + [False]` (the five prior-step calls take the default) |
| S6 | `tests/pipeline/test_observe_load_instrumentation.py:110` `_Stub.get_or_fetch` (in `test_observe_scaling_one_obs_per_open_detection`) | REQUIRED `use_ladder` keyword; append to a test-local `seen` | after the first drive: `seen == [False]*5` |
| S7 | `tests/pipeline/test_observe_load_instrumentation.py:50`, the `_fetch_bars_window` lambda in `test_ohlcv_cache_telemetry_counts_hit_vs_fetch` | a local `def _fbw(*, ticker, window_days, use_ladder)` that appends `use_ladder` and returns `frame`. AL-2 makes the real `get_or_fetch` pass the keyword, so the old lambda would `TypeError` | `fbw_seen == [True]` (one miss on the default; the second call is a hit) |
| S8 | `tests/pipeline/test_observe_read_memo.py:74` `_real_cache._fetch` | signature `(*, ticker, window_days, use_ladder)`, REQUIRED; `cache.use_ladder_seen = []`; append as the first statement | `_drive` (:104-111), after the `overruns` assertion: `if hasattr(cache, "use_ladder_seen"): assert cache.use_ladder_seen and set(cache.use_ladder_seen) == {False}`. Every `_real_cache` test (T-H1, T-H2, T-C3, T-E, T-lifetime, T-load) goes through `_drive` |
| S9 | `tests/pipeline/test_observe_remediation.py:73` `_NoOpCache.get_or_fetch` | REQUIRED `use_ladder`; append to a test-local `seen`. The stub's comment is replaced by `# observe's populate never writes schwab_api (D90) -> no overwrite`. The test's docstring first sentence becomes `The populate does NOT overwrite the schwab_api row (D90: observe never reaches the ladder); the stale contaminated row wins on precedence -> _bar_for_date returns it (the residual gap).` | `test_failure_path_then_purge_falls_to_clean_yfinance`: after both calls, `seen == [False, False]` |
| X1 | `tests/pipeline/test_observe_remediation.py:33-53` `test_success_path_overwrites_contaminated_before_lock` (and its `_Cache` at :45) | DELETED, SUPERSEDED BY NAME. The comment block below is put in its place | replaced by T-NS |

**X1's comment block, verbatim:**
```python
# SUPERSEDED BY NAME (D90; RD ruling 20261020T072525Z, CHARC 20261020T072626Z):
# test_success_path_overwrites_contaminated_before_lock pinned observe's populate
# re-fetching a clean schwab_api row for the observation date through the Schwab
# ladder, healing a contaminated one (the seeded case is an ext-hours-inflated
# high). D90 detaches the ladder from observe's populate, so that path is gone.
# The hazard, and what closes it now: (i) the ladder cannot write a NEW
# contaminated schwab_api row -- it requests regular-session candles only
# (needExtendedHoursData=False in swing/integrations/schwab/marketdata.py), and
# every Schwab bar passes OhlcvBar's finite-OHLC check
# (swing/integrations/schwab/models.py) before it reaches the archive;
# (ii) an observe-only ticker gets no schwab_api row at all after the boundary;
# (iii) a detect-pool ticker's row is refetched by detect's own ladder call on
# the next run. Replacement: tests/pipeline/test_observe_ladder_detach.py::
# test_observe_populate_never_reaches_the_ladder_hook.
```

Run: every new test, and every assertion the sweep adds, is RED as tabulated. The one exception is T-D3, an invariant pin that is GREEN by design. S2, S6, S7, S8 and S9 make `use_ladder` a REQUIRED keyword, so under the old code their stub raises `TypeError`, and their assertions fail. Record each RED in the exec ledger.

**Step 2, GREEN.**

(a) `swing/web/ohlcv_cache.py`:
- **Signature (:175):** `def get_or_fetch(self, *, ticker: str, window_days: int = 180, use_ladder: bool = True) -> pd.DataFrame:`.
- **The Routing paragraph (:197-202) is replaced entirely by:**
  ```
  Routing: when ``set_ladder_bars_fetcher`` is installed AND ``use_ladder``
  is True (the default), the ladder hook is invoked + its DataFrame sliced to
  the calendar-day window. Otherwise (no hook, or ``use_ladder=False``)
  ``read_or_fetch_archive`` is consulted directly + sliced. Either path
  inherits the ``read_or_fetch_archive`` shape (capitalized OHLCV +
  DatetimeIndex). Sandbox short-circuit lives inside the ladder; this
  method is env-agnostic. ``use_ladder`` is keyword-only: the pipeline's
  observe populate passes False (D90) and every other caller takes the
  default. The ``_bars_store`` key does not include it, so a TTL hit returns
  whatever an earlier call stored under either setting.
  ```
- **The call (:235-237):** `bars = self._fetch_bars_window(ticker=ticker_upper, window_days=int(window_days), use_ladder=use_ladder,)`.
- **`_fetch_bars_window` (:253):**
  - the signature is `def _fetch_bars_window(self, *, ticker: str, window_days: int, use_ladder: bool = True) -> pd.DataFrame | None:`;
  - append to its docstring: `` ``use_ladder=False`` skips an installed ladder hook and takes the ``read_or_fetch_archive`` branch (D90). ``;
  - :270 becomes `if use_ladder and self._ladder_bars_fetcher is not None:`.

(b) `swing/pipeline/runner.py`:
- **`_bar_for_date`'s docstring (:3080-3102) is replaced entirely.** The `memo` paragraph is carried over unchanged:
  ```
  Return an ohlc dict (with provider) for exactly ``observation_date``, or
  None if the archive has no bar for that session.

  OQ-17 read path: (1) populate/refresh the archive via
  ``ohlcv_cache.get_or_fetch(..., use_ladder=False)`` (best-effort: a raise
  is logged and step 2's read stays authoritative). A TTL hit does no I/O. On
  a miss the populate refreshes the legacy archive through
  ``read_or_fetch_archive`` and NEVER through the Schwab market-data ladder,
  even when the run installed the ladder's bars hook (D90): observe makes no
  Schwab call and writes no ``schwab_api`` archive rows. (2) read the
  date-anchored bar + provider provenance via resolve_ohlcv_window (keyed
  end=observation_date). Selects the row whose asof_date == observation_date
  (NOT iloc[-1]); freezes it; never re-reads it later (#26 elimination
  honest). The provider is that date's precedence winner across the archive
  files (``schwab_api`` over ``yfinance``), so a ``schwab_api`` row that
  another caller's ladder fetch wrote (detect's, or the web process's) can
  still be the one selected.

  ``memo`` (D89): the observe step passes one dict per step call, keyed by
  ``_observe_memo_key``. When the key is present, step 2 selects from the
  memoized ``(df, provenance)`` pair and does not read the archive, whatever
  this call's populate did. When it is absent, step 2 reads the archive and
  stores the pair ONLY if this call's populate returned without raising (bar
  or no bar). ``memo=None`` reads on every call and stores nothing.
  ```
- **:3118** becomes `# 1. Populate the archive (write-through; detect's window, but never the Schwab ladder: use_ladder=False, D90).` The rest of that comment block is unchanged.
- **:3132** becomes `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=DETECT_OBSERVE_WINDOW_DAYS, use_ladder=False)`, wrapped to 88 columns. The comment above it is unchanged.
- **:3252-3255** (from `needs the lease.` to the end of the block) is replaced by:
  ```
  # needs the lease. Running _bar_for_date (-> get_or_fetch -> the
  # read_or_fetch_archive refresh, whose yfinance downloads can write audit
  # rows; never the Schwab ladder since D90) here means it never executes under
  # a held write lock (Run-92 deadlock removed). Shed is evaluated BEFORE
  # _bar_for_date, so shed tickers are still never fetched (OQ-A).
  ```
- **:365-369 ("Consumer surfaces ...") is replaced entirely by:**
  ```
  Consumer surfaces: PriceCache is consumed by ``_step_evaluate``
  (open-trade-ticker warm). OhlcvCache is consumed through
  ``ohlcv_cache.get_or_fetch(...)`` by ``_step_pattern_detect`` (Pass-1 and
  the exemplar fetch) and ``_step_charts`` (chart targets, the chart_renders
  write-through, the market-weather benchmark), all through the ladder
  hook; ``_step_pattern_observe``'s populate passes ``use_ladder=False`` and
  never reaches it (D90). Both caches share the same ``schwab_client`` via
  captured closures.
  ```

Run: every T1 test passes. Then run `python -m pytest tests/pipeline tests/integration -q -m "not slow"`.

Commit (pathspec-only; the two swing files and every test file named in T1): `feat(pipeline): T1 -- observe's populate never reaches the Schwab ladder (D90)`.

### T2 -- suite, ruff, closure, mutations, then the executing review

1. Run `python -m pytest -m "not slow" -q` to green and read the tail. Run `ruff check swing/`.
2. **Closure checks.** Quote each one with its output in the exec ledger:
   - **`grep -rn "resolve_ohlcv_window(" swing/`** returns the def (`ohlcv_archive.py:971`), `_bar_for_date` (runner) and `swing/latches/reader.py:695`. NEITHER caller changes: `git diff main...HEAD -- swing/latches swing/data` is EMPTY, and the runner diff does not touch the resolve call lines.
   - **The p22 AST script, re-run on the head:** exactly one `use_ladder` keyword (`False`, in `_bar_for_date`). The five other runner callers carry none and stay on the ladder: `_step_pattern_detect` x2 and `_step_charts` x3. Neither do the four web/trades callers.
   - **`git diff --stat main...HEAD -- swing`** names `swing/pipeline/runner.py` and `swing/web/ohlcv_cache.py` only. `git diff main...HEAD -- swing/web/app.py swing/integrations` is EMPTY.
   - **Text:**
     - `grep -n "when the run has a" swing/pipeline/runner.py`, `grep -n "identical Schwab quota" swing/pipeline/runner.py` and `grep -n "the same call detect makes" swing/pipeline/runner.py` each return nothing;
     - `grep -rn "use_ladder" swing/` returns only the AL-1, AL-2 and AL-4 sites and the two docstrings.
   - **The stub census, re-run on the head:** run the p20 plugin over `tests/pipeline tests/integration`. Every cache class reaching `_bar_for_date` must be the real `OhlcvCache` or one of S1-S6, S8 or S9; anything new is a finding. `grep -rn "def get_or_fetch" tests/ | wc -l` must read 33 (34 less X1's `_Cache`).
3. **Mutation checks.** Each one is a scratch edit to a swing file: run it, see it red, then `git checkout -- swing/` and confirm `git diff --exit-code swing` returns 0. Quote each in the exec ledger.

| id | scratch edit | tests that must go RED |
|---|---|---|
| M1 (quoted in the merge report) | `_bar_for_date` passes `use_ladder=True` | T-NS, T-stub, T-D4, N-V ordinary (3)(5), N-V carry (2), S2-S6, S8, S9 |
| M2 | `get_or_fetch` stops passing `use_ladder` on | T-NS, T-D2, N-V (3) |
| M3 | `_fetch_bars_window` branches on `self._ladder_bars_fetcher is not None` only | T-NS, T-D2, N-V (3) |
| M4 | `get_or_fetch`'s default becomes `False` | T-D1, N-V (3) (detect-phase call), S5 (`[True]*5`) |
| M5 | the `_bars_store` key becomes `(ticker_upper, window_days, use_ladder)` | T-D2 |

4. **The executing Reviewer A loop (`strong`),** per the recipe. The envelope and the limitations above go into its prompt.

## Test roster (complete; method: every test named in T1, plus every existing file the p20 census or the static read places on `_bar_for_date`'s cache path)

| file | added | edited | deleted |
|---|---|---|---|
| `tests/pipeline/test_ohlcv_cache_use_ladder.py` (new) | T-D1, T-D2, T-D3 | -- | -- |
| `tests/pipeline/test_observe_ladder_detach.py` (new) | T-NS, T-stub, T-D4 | -- | -- |
| `tests/pipeline/test_observe_ladder_detach_neutrality.py` (new) | N-V ordinary, N-V carry | -- | -- |
| `tests/pipeline/conftest_temporal.py` | -- | S1 | -- |
| `tests/pipeline/test_detect_observe_window.py` | -- | S2 | -- |
| `tests/pipeline/test_fetch_vs_write_ordering.py` | -- | S3 | -- |
| `tests/pipeline/test_lock_guard_completed_day.py` | -- | S4 (:42 only; the stub at :26 is never reached, because the L3 guard raises first) | -- |
| `tests/pipeline/test_observe_load_instrumentation.py` | -- | S5, S6, S7 | -- |
| `tests/pipeline/test_observe_read_memo.py` | -- | S8 (`_real_cache`, `_drive`) | -- |
| `tests/pipeline/test_observe_remediation.py` | -- | S9 | X1 |

Existing files UNCHANGED, each with its reason (ledger 2.2):
- `test_observe_read_memo_neutrality.py` and `test_step_evaluate_warm_neutrality.py`: a real cache with NO hook. `use_ladder=False` takes the branch "no hook" already takes.
- `test_step_pattern_observe.py`, `test_phase14_temporal_log_e2e.py`, `test_pattern_pool_dormant_levers.py` and `test_observe_read_memo.py::T-key`: through `_StubOhlcvCache` (S1, pinned by T-stub).
- `test_runner_chart_targets.py:221` and `test_step_charts_classification.py:157`: class-level patches measured UNREACHED (p21).
- Every detect, charts, web, trades and integration-detector stub: not on observe's path (p20).

## Not changed (explicit)

- `resolve_ohlcv_window`, `_backward_compat_rename`, `write_window`, `read_or_fetch_archive` and the warm (nothing under `swing/data/`).
- `fetch_window_via_ladder`, `resolve_full_archive_bars`, `_persist_window_to_archive` and the wrapper (nothing under `swing/integrations/`).
- `swing/web/app.py` (the web process's own ladder hook), `_fetch_bundle_worker`, `set_ladder_bars_fetcher`, the `_bars_store` key, the telemetry.
- The pipeline bars hook and its install code. Detect's two calls and charts' three. The L3 guard, `populate_ok`, the memo, the resolve call, the selection, the observe loop, the warnings, `observe_load`'s keys and meaning.

## Owner docs that restate a changed fact (LISTED for their owners; this plan edits none)

| owner | site | what goes stale or is owed |
|---|---|---|
| RD | the watch-standard | the VII.F boundary note (RD 1.1 (b)) and the read caveat, RD's words (1.1 (d)): "$.provider is mixed on 12 historical carry dates and may mix on future carry nights for detect-pool tickers; any provider-sensitive analysis conditions on $.provider explicitly; value-level analyses need no conditioning (measured)." |
| CHARC | `docs/tool-director-context.md`, row D90 | the disposition at merge |
| orchestrator | the D84 widening brief, when written | the observe cost model: observe pays no Schwab term after D90 |

## Merge-report checklist (the row's WITNESS; baseline run 195 from `round0\probe4.out`)

| item | run 195 (baseline, pre-merge) | first post-merge night |
|---|---|---|
| W0, the token is live (anti-vacuity) | 273 `marketdata.pricehistory` rows with the run id; 35 of them outside observe | at least one `marketdata.pricehistory` row with the run id OUTSIDE observe's window (detect or charts). Otherwise the night cannot witness D90: a tokenless night is 0 by construction |
| W1, Schwab inside observe | `surface='pipeline' AND pipeline_run_id=195` in observe's window: 238 rows, 87,395 ms. NULL-run-id rows in the window: 0 | **0** with the same filter. The NULL-run-id count is reported separately (the web hook writes `surface="pipeline"` with no run id, `app.py:579`) |
| W2, the observe wall (from the lease lines) | 541,691 ms | the drop is AT LEAST 87,395 ms attributable to D90 (the parquet and audit writes also leave). If it is also the first post-D89 night, report the combined figure with D89's share from its own W-items (L-6) |
| W3, the rows | `$.provider`: yfinance on 6,934 of 6,934 | on a non-carry night, yfinance on every row. The byte-equality evidence is the N-V ordinary pair, plus M1 |
| W4, `observe_load` | `{"observed": 6934, "fetch_window": 238, "in_memory_hit": 6901}` | the same keys and meaning, plus D89's `resolve_reads` |
| W5, the texts | -- | T2 step 2's text greps, with their outputs |
| W6, the VII.F boundary slot (RD writes the note) | -- | the first post-merge `pipeline_runs.id` = ____. From it, observe-only tickers' rows are yfinance by construction; detect-pool tickers may still carry `schwab_api` on carry nights |
| W7, the residual (L-3) | -- | stated in these words: "a ticker latched, then rotated out of the screen and never viewed, carries a provider-mixed range" |
| W8, the first carry night after merge | -- | Thanksgiving evening 2026-11-26 (data_asof 11-25), or a weekend run with a live token. Observe-only tickers record yfinance; detect-pool tickers may record `schwab_api`. RD's read caveat (d) |

Also quoted: M1 with T-NS RED; the closure checks (T2 step 2) with their outputs; and the suite tail on the final head.
