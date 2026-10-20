# D90 exec ledger -- detach the Schwab ladder from observe's populate

**Plan:** `docs/superpowers/plans/2026-10-20-d90-observe-ladder-detach.plan.md` (cleared at `d256bdfa`).
**Plan ledger:** `docs/superpowers/plans/2026-10-20-d90-observe-ladder-detach.plan.ledger.md`.
**Brief:** `docs/d90-observe-ladder-detach-exec-dispatch-brief.md` (main `3192a96f`).
**Worktree:** `.worktrees/d90-detach`, branch `d90-detach`. Diff base `e7f91d80` (the merge-base with main).
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d90-detach\exec\` (`t1\`, `t2\`, `round<N>\`).

## 0. How to read this ledger

Sections 1-4 are the record: the clearances, the additions they make, and the T1/T2 results with their outputs. Section 5 is the Reviewer A round table and the per-round adjudications. A reviewer's copy is CUT before section 5.

## 1. Clearances of record (verbatim)

### 1.1 RD -- plan-stage read, CLEARED on neutrality (`comms/orchestrator/read/20261020T075410Z-rd-d90-plan-rd-clears-neutrality-two-pair-t.md`). Author: RD.

> ---
> from: rd
> to: orchestrator
> type: status
> subject: D90 plan: RD CLEARS (neutrality, two-pair test, C-1); merge after a D89 night
> posted: 2026-10-20T07:54:10Z
> thread: d90
> ---
>
> RD PLAN-STAGE READ, D90 (orchestrator query 20261020T075234Z; plan d256bdfa, 384 lines, read in full via git show). PRIMARY: RD on neutrality, the two-pair test, C-1 and the boundary slot.
>
> VERDICT: CLEARED. The clearance attaches to T1 as written at d256bdfa (AL-1 to AL-9, T-NS, the two-pair N-V with its assertions, the S1-S9 sweep, X1 superseded by name, M1-M5); a code-bearing change beyond it re-opens the read.
>
> Verified:
> 1. NEUTRALITY CASE (L-1): admissibility (1) is restated in my words, conditional, with the carry-date measurement as its reason. AL-4 is a literal use_ladder=False on every observe call; AL-9 no carry predicate anywhere; AL-5 nothing else in _bar_for_date moves (populate_ok and the D89 memo rule byte-identical). That is Branch A as ruled.
> 2. THE TWO-PAIR TEST: it drives the REAL fetch_window_via_ladder and resolve_full_archive_bars in the production hook's composition with only get_price_history patched (L-4), carry as the schwab_end fixture parameter, no clock. The ordinary pair pins rows equal with every provider yfinance, the observe-phase Schwab calls [] under the detach (the in-fixture witness), the store miss for OOT and FBK before observe (CHARC's anti-vacuity, assertion 4), and the schwab_files residual {OOT,DPT} -> {DPT} (admissibility (2) in-fixture). The carry pair pins the difference EXACTLY on OOT's provider label with OHLC and volume equal, DPT schwab_api in both worlds (L-2), FBK yfinance in both. The "label only" pin rests on the fixture feeding identical bars to both legs; the live justification is my carry-date measurement, and L-1 says so. Exactly what I asked for in (c).
> 3. C-1 ACCEPTED, my hazard statement corrected: the superseded test seeded a FINITE extended-hours-inflated high, not a non-finite row, so the 18-B trailing trim was the wrong guard to cite. Verified at the code: get_price_history passes needExtendedHoursData=False (marketdata.py:403) and OhlcvBar.__post_init__ rejects non-finite OHLC (models.py:561-582). The X1 comment block names both guards and the replacement by name. Accepted as written.
> 4. W6, the VII.F boundary slot: the first post-merge pipeline_runs.id, RD writes the note; W8 carries my read caveat for the first carry night (Thanksgiving evening 2026-11-26 or a weekend run with a live token); W7 states L-3's residual in words. All three are what I required.
> 5. SEQUENCING (I-3): CONCUR. D90 executes on this clearance but does not merge until one post-D89 nightly has run on main, so D89's W1/W5 (my read) and D90's wall drop stay attributable to their own arcs. Tonight's 17:30 HST run is that D89-only night.
> 6. W0 is CHARC's; no objection to keeping it -- a dead-token night reads 0 Schwab calls for free and would witness nothing.
>
> OWED BY ME: at the D90 merge, the boundary note in the exec ledger and the watch-standard (first post-detach run id; observe-only rows yfinance by construction; detect-pool tickers may carry schwab_api on carry nights) and the read caveat (d) in the watch-standard; after the first post-D90 nightly, W1 (0 Schwab rows inside observe with the run-id filter) and W3 ($.provider yfinance on every row on a non-carry night) read before anyone quotes the drop.
>
> Executing tier implementer-opus-high: concur, the populate that feeds the append-only log.
>
> TRANSCRIPTION: block-quote into the D90 plan ledger with RD as author; landed when the path is posted back.

### 1.2 CHARC -- plan-stage read, CLEARED on form at `d256bdfa` (`comms/orchestrator/read/20261020T075500Z-charc-d90-plan-charc-clears-on-form-at-d256bdf.md`). Author: CHARC.

> ---
> from: charc
> to: orchestrator
> type: status
> subject: D90 plan: CHARC CLEARS on form at d256bdfa; W0 kept + fetch_window>0; I-1/I-2 ok
> posted: 2026-10-20T07:55:00Z
> thread: d90
> ---
>
> CHARC PLAN-STAGE READ, D90 (orchestrator query 20261020T075234Z; plan d256bdfa, 384 lines; ledger 343 lines; both read in full via git show). PRIMARY: CHARC on form, W0, I-1, I-2. Recorded at ebbc9158 (the D90 row).
>
> VERDICT: CLEARED ON FORM at d256bdfa. The clearance attaches to T1 as written (AL-1..AL-9, the three new files, S1-S9, X1 superseded by name, M1-M5, T2's closure checks); a code-bearing change beyond it re-opens the read.
>
> Read at this seat, against code on main at ebbc9158:
> 1. The keyword form is as ruled: keyword-only, additive, default True, threaded to _fetch_bars_window as `use_ladder and hook`, the _bars_store key unchanged (AL-1..AL-3). The five other pipeline callers take the default; T-D4 pins it statically and T-D1 dynamically.
> 2. The N-V composition is sound: fetch_window_via_ladder calls get_price_history by module global (marketdata_ladder.py:461, imported at :71), so the monkeypatch lands; conn=None and the dummy client reach only the fake; _is_ladder_active's two cfg attributes are set on the duck-typed cfg. The fallback leg for FBK goes through the real _persist_window_to_archive into the tmp cache dir. L-4 holds.
> 3. The store-miss anti-vacuity is encoded where it must be: T-NS asserts the store is empty before the drive; N-V (4) asserts store_before_observe == {("DPT", 400)} in both worlds, so OOT and FBK miss. This is the point I posted; it is in.
> 4. The cited guards exist at the cited lines: needExtendedHoursData=False at marketdata.py:403; OhlcvBar.__post_init__'s finite-OHLC check at models.py:561-582.
>
> W0: KEPT, and SHARPENED by one companion condition. A dead-token night reads 0 inside observe for free (W0 as the cell wrote it). A night whose observe tickers were ALL detect-stored also reads 0 for free, because the flag is reached only on a store miss. So the witness night must show BOTH: at least one marketdata.pricehistory row with the run id outside observe's window (W0), AND observe_load.fetch_window > 0 (W4 already reports it; W0 names it as a precondition). Run 195 satisfies both (35 outside; fetch_window 238).
>
> I-1: ACCEPTED. The defect is a per-class signature defect; _StubOhlcvCache is pinned once by T-stub. Editing its 15 users adds no discrimination.
> I-2: ACCEPTED on one condition the plan already carries: T2 step 2 re-runs the p20 census on the HEAD and QUOTES its output in the exec ledger. The two class-level chart stubs stay unchanged because they are measured unreached, and that measurement is repeated after the change, not inherited from the base.
> I-3: CONCUR with the orchestrator's sequencing (RD concurs too, 20261020T075410Z): execute now, merge only after one post-D89 nightly, for witness attribution. Tonight's 17:30 HST run is that night.
>
> ONE MINOR for the executing cell, no round (post-convergence minor-scope): X1's comment clause (ii) says "an observe-only ticker gets no schwab_api row at all after the boundary". The web process's own hook can still write one for a VIEWED observe-only ticker (plan L-2, admissibility (2)'s residual). Say "gets no schwab_api row FROM OBSERVE"; the suite on the final head covers it.
>
> Executing tier implementer-opus-high: concur (recipe 2A, measurement-chain code). Reviewer A strong with repo access; Reviewer B is the orchestrator's on the tree being merged; the B transcript is named in the merge request or there is no clearance.
>
> Merge gate owed by me at the merge report: the M1 quote with T-NS RED; the T2 closure outputs (the resolve_ohlcv_window callers unchanged, the AST single keyword, the diff stat naming two swing files, the text greps, the head census); W0 with its companion; the ladder-active night. Nothing of mine is in flight.

## 2. Additions the clearances make (no task changes)

- **W0, SHARPENED (CHARC).** A witness night must show BOTH (a) at least one `marketdata.pricehistory` row with the run id OUTSIDE observe's window and (b) `observe_load.fetch_window > 0`. Baseline, run 195, re-measured at this seat (live DB `mode=ro`, plain sqlite3; `exec\t2\w0_probe.py`, output `exec\t2\w0_run195.out`):
  ```
  marketdata.pricehistory rows with pipeline_run_id=195: 273
    inside observe window [2026-10-19T17:34:32.970, 2026-10-19T17:43:34.661]: 238
    OUTSIDE observe window: 35
    outside by surface: ('pipeline', '2026-10-19T17:34:05.050728', '2026-10-19T17:43:46.666059', 35)
  observe_load: {"step": "pattern_observe", "metric": "observe_load", "observed": 6934, "fetch_window": 238, "in_memory_hit": 6901}
    fetch_window > 0: True
  ```
  Both conditions hold for run 195 (35 outside; fetch_window 238), matching the plan's merge-report row and CHARC's figures.
- **I-2 (CHARC).** The p20 census is re-run on HEAD and quoted in section 4.3. The two class-level chart patches are re-measured there, not inherited.
- **C-1 (RD).** The X1 site comment cites both guards: `needExtendedHoursData=False` (`swing/integrations/schwab/marketdata.py:403`) and `OhlcvBar`'s finite-OHLC check (`swing/integrations/schwab/models.py:561-582`). Re-read at this seat: :403 carries `needExtendedHoursData=False`; :561-582 is `OhlcvBar.__post_init__` rejecting non-finite OHLC.
- **CHARC's one minor, applied without a round (post-convergence minor scope, CHARC's words).** X1's clause (ii) reads "an observe-only ticker gets no schwab_api row from observe after the boundary" (the plan's text said "at all"; the web process's own hook can still write one for a viewed ticker, plan L-2). Comment wording only.

## 3. T1 -- the keyword, observe's opt-out, the texts, the sweep, the supersession

### 3.1 RED (before the swing edits; `exec\t1\red.txt`, `exec\t1\red_tbline.txt`)

The three new files and every sweep edit were written first, then run at `-n 0`: **22 failed, 19 passed**. Every RED is the tabulated one:

| test | RED, read off `red_tbline.txt` |
|---|---|
| T-D1 `test_default_and_true_reach_the_ladder_hook` | `TypeError: OhlcvCache.get_or_fetch() got an unexpected keyword argument 'use_ladder'` |
| T-D2 `test_false_skips_the_hook_and_shares_the_store` | the same `TypeError` |
| T-D3 `test_bundle_worker_still_calls_the_hook` | PASSED (invariant pin, GREEN by design) |
| T-NS `test_observe_populate_never_reaches_the_ladder_hook` | `assert ['OOT'] == []` (the hook was reached) |
| T-stub | `assert [True, True] == [False, False]` |
| T-D4 | `assert [] == [('swing/pipeline/runner.py', '_bar_for_date', False)]` |
| N-V ordinary, N-V carry | `TypeError ... unexpected keyword argument 'use_ladder'` (the today-world wrapper) |
| S2 `test_observe_populate_uses_the_window_constant` | `assert [] == [(401, False)]` (the required keyword raised inside the best-effort except) |
| S3 (x2) | `assert [True] == [False]` |
| S4 `test_bar_for_date_allows_completed_day` | `{'ticker': 'AAPL', 'window_days': 400} != {..., 'use_ladder': False}` |
| S5 (x2) | `[True, True] == [False, False]`; `[True]*6 == [True]*5 + [False]` (index 5) |
| S6 | `assert [] == [False, False, ...]` |
| S7 `test_ohlcv_cache_telemetry_counts_hit_vs_fetch` | `_fbw() missing 1 required keyword-only argument: 'use_ladder'` |
| S8 (6 `_real_cache` tests via `_drive`) | `assert ([])` on `cache.use_ladder_seen` |
| S9 `test_failure_path_then_purge_falls_to_clean_yfinance` | `assert [] == [False, False]` |

### 3.2 GREEN (`exec\t1\green.txt`, `exec\t1\pipeline_integration.txt`)

- The T1 files: **41 passed** (`-n 0`).
- `python -m pytest tests/pipeline tests/integration -q -m "not slow" -n 8`: **539 passed** (base census run: 532; +8 new, -1 X1).

### 3.3 Commit

- `4e4cf8b5` `feat(pipeline): T1 -- observe's populate never reaches the Schwab ladder (D90)`; pathspec-only (2 swing files, 3 new test files, 7 edited test files); `%(trailers)` empty.

## 4. T2 -- suite, ruff, closure, census, mutations, the two-pair outputs

### 4.1 Suite and ruff

- Full fast suite on `4e4cf8b5`, `python -m pytest -m "not slow" -q -n 8 -p no:cacheprovider` (`exec\t2\suite_pre_review.txt`): **15525 passed, 13 skipped, 0 failed** in 817.63 s.
- `ruff check swing/`: All checks passed (`exec\t2\ruff.txt`).
- Touched test files, head vs base by `file:code:message` (line-agnostic; base read with `git show e7f91d80:<f> | ruff check --stdin-filename <f> -`): two NEW findings in new files (`I001` in `test_observe_ladder_detach.py`, `B905` in `test_observe_ladder_detach_neutrality.py`); every pre-existing file's count is unchanged (conftest_temporal 4/4, fetch_vs_write 9/9, load_instrumentation 7/7, others 0/0). Fixed in `71598097` `style(tests): T2 -- zero new ruff findings on the D90 test files (D90)` (import order; `zip(..., strict=True)`); both files re-run, 5 passed, ruff clean.

### 4.2 Closure checks (`exec\t2\closure.txt`, verbatim outputs)

```
$ git merge-base main HEAD
e7f91d80bd5db5a9eb89819076af3bd6de9f1ac8
$ grep -rn "resolve_ohlcv_window(" swing/
swing/data/ohlcv_archive.py:971:def resolve_ohlcv_window(
swing/latches/reader.py:695:        df, _provenance = resolve_ohlcv_window(
swing/pipeline/runner.py:3156:        df, provenance = resolve_ohlcv_window(
$ git diff e7f91d80..HEAD -- swing/latches swing/data | wc -c
0
$ git diff e7f91d80..HEAD -U0 -- swing/pipeline/runner.py | grep -n resolve_ohlcv_window
26:-    the date-anchored bar + provider provenance via resolve_ohlcv_window (keyed
33:+    date-anchored bar + provider provenance via resolve_ohlcv_window (keyed
```
Both hits are the docstring line re-wrapped by the replacement; the call at `runner.py:3156-3159` is in no hunk (byte-identical, K-1).

```
$ python p22_get_or_fetch_ast.py (HEAD)
swing/pipeline/runner.py:2456	_step_pattern_detect	{'ticker': 'ex_row.ticker', 'window_days': 'DETECT_OBSERVE_WINDOW_DAYS'}
swing/pipeline/runner.py:2194	_step_pattern_detect	{'ticker': 'ticker', 'window_days': 'DETECT_OBSERVE_WINDOW_DAYS'}
swing/pipeline/runner.py:3139	_bar_for_date	{'ticker': 'ticker', 'window_days': 'DETECT_OBSERVE_WINDOW_DAYS', 'use_ladder': 'False'}
swing/pipeline/runner.py:3727	_step_charts	{'ticker': 'benchmark_ticker', 'window_days': 'MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE'}
swing/pipeline/runner.py:3522	_step_charts	{'ticker': 'ticker', 'window_days': 'MIN_CALENDAR_DAYS_FOR_MA200'}
swing/pipeline/runner.py:3593	_step_charts	{'ticker': 'ticker', 'window_days': 'MIN_CALENDAR_DAYS_FOR_MA200'}
swing/trades/review_auto_fill.py:151	_ohlcv_mfe_mae	{'ticker': 'trade.ticker', 'window_days': 'days_since_entry'}
swing/web/chart_jit.py:119	get_or_render_surface	{'ticker': 'ticker', 'window_days': 'MIN_CALENDAR_DAYS_FOR_MA200'}
swing/web/routes/dashboard.py:103	dashboard_weather_chart_refresh	{'ticker': 'benchmark', 'window_days': 'MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE'}
swing/web/routes/recommendations.py:285	hyprec_thumbnail_fragment	{'ticker': 'ticker', 'window_days': 'MIN_CALENDAR_DAYS_FOR_MA200'}
TOTAL 10
```
Exactly one `use_ladder` keyword (`False`, `_bar_for_date`); the five other runner callers and the four web/trades callers carry none.

```
$ git diff --stat e7f91d80..HEAD -- swing
 swing/pipeline/runner.py | 47 ++++++++++++++++++++++++++++-------------------
 swing/web/ohlcv_cache.py | 21 +++++++++++++++------
 2 files changed, 43 insertions(+), 25 deletions(-)
$ git diff e7f91d80..HEAD -- swing/web/app.py swing/integrations | wc -c
0
$ git diff --stat e7f91d80..HEAD -- swing/data swing/trades scripts research
(end)
$ grep -n "when the run has a" swing/pipeline/runner.py
(rc=1)
$ grep -n "identical Schwab quota" swing/pipeline/runner.py
(rc=1)
$ grep -n "the same call detect makes" swing/pipeline/runner.py
(rc=1)
$ grep -rn "use_ladder" swing/   (the two .pyc "Binary file" lines omitted)
swing/pipeline/runner.py:370:    hook; ``_step_pattern_observe``'s populate passes ``use_ladder=False`` and
swing/pipeline/runner.py:3088:    ``ohlcv_cache.get_or_fetch(..., use_ladder=False)`` (best-effort: a raise
swing/pipeline/runner.py:3125:    #    Schwab ladder: use_ladder=False, D90).
swing/pipeline/runner.py:3140:                                 use_ladder=False)
swing/web/ohlcv_cache.py:176:        self, *, ticker: str, window_days: int = 180, use_ladder: bool = True,
swing/web/ohlcv_cache.py:199:        Routing: when ``set_ladder_bars_fetcher`` is installed AND ``use_ladder``
swing/web/ohlcv_cache.py:201:        the calendar-day window. Otherwise (no hook, or ``use_ladder=False``)
swing/web/ohlcv_cache.py:205:        method is env-agnostic. ``use_ladder`` is keyword-only: the pipeline's
swing/web/ohlcv_cache.py:243:            use_ladder=use_ladder,
swing/web/ohlcv_cache.py:261:        self, *, ticker: str, window_days: int, use_ladder: bool = True,
swing/web/ohlcv_cache.py:273:        ``use_ladder=False`` skips an installed ladder hook and takes the
swing/web/ohlcv_cache.py:279:        if use_ladder and self._ladder_bars_fetcher is not None:
$ grep -rn "def get_or_fetch" tests/ | wc -l
33
```
The `use_ladder` grep, read hit by hit (12): AL-1 `ohlcv_cache.py:176`; AL-2 `:243`, `:261`, `:279`; AL-4 `runner.py:3140`; and seven text hits, every one plan-specified replacement text: the `get_or_fetch` Routing paragraph (:199, :201, :205), the `_fetch_bars_window` docstring sentence (:273), `_bar_for_date`'s docstring (:3088), the step-1 comment (:3125) and the install docstring's consumer paragraph (:370). The plan's wording "the AL sites and the two docstrings" undercounts the text hits by the last two, which T1 itself specifies; no unplanned site.

### 4.3 The stub census on HEAD (I-2; `exec\t2\p20_reach_head.tsv`, `p20_reach_head_hits.tsv`, `p20_head_classes.txt`, `p20_head_pytest.txt`)

The p20 plugin (copied unchanged to `exec\t2\p20_reach_probe_plugin.py`) over `tests/pipeline tests/integration -m "not slow" -n 8`: **539 passed**; **36** tests reach `_bar_for_date` (base 33: +4 new, -1 X1). Cache classes (tests):
```
      2 [('OhlcvCache', 'OhlcvCache.get_or_fetch'), ('OhlcvCache', 'run_world.<locals>.<lambda>')]
      9 [('OhlcvCache', 'OhlcvCache.get_or_fetch')]
      1 [('_Cache', 'test_bar_for_date_allows_completed_day.<locals>._Cache.get_or_fetch')]
      1 [('_Cache', 'test_bar_for_date_rejects_current_day.<locals>._Cache.get_or_fetch')]
      2 [('_DeadlockProbeCache', '_DeadlockProbeCache.get_or_fetch')]
      1 [('_NoOpCache', 'test_failure_path_then_purge_falls_to_clean_yfinance.<locals>._NoOpCache.get_or_fetch')]
      1 [('_RecCache', 'test_observe_populate_uses_the_window_constant.<locals>._RecCache.get_or_fetch')]
      1 [('_Stub', 'test_observe_scaling_one_obs_per_open_detection.<locals>._Stub.get_or_fetch')]
     16 [('_StubOhlcvCache', '_StubOhlcvCache.get_or_fetch')]
      2 [('_TeleStub', '_TeleStub.get_or_fetch')]
```
Every class is the real `OhlcvCache` or one of S1-S6, S8, S9; nothing new. The `run_world.<locals>.<lambda>` qualname is the N-V today-world's own class-level wrapper over the real `OhlcvCache.get_or_fetch` (by design, plan file C). The `rejects_current_day` `_Cache` is entered but the L3 guard raises before the populate (unchanged, plan roster). **The two class-level chart patches, re-measured on HEAD:** `test_runner_chart_targets.py` + `test_step_charts_classification.py`, 19 tests, **0** `_bar_for_date` calls (base p21: 19 tests, 0 calls). `grep -rn "def get_or_fetch" tests/ | wc -l` = 33 (34 less X1's `_Cache`).

### 4.4 Mutations (`exec\t2\mutations\M<N>.{diff,pytest,summary}.txt`; scratch edit, the nine T1 test files at `-n 0`, then `git checkout -- swing/`)

`git diff --exit-code swing/` returned **0** after each of M1-M5, and after the run.

| id | edit | result | plan's must-go-RED | measured |
|---|---|---|---|---|
| **M1** | `_bar_for_date` passes `use_ladder=True` | 19 failed / 22 passed | T-NS, T-stub, T-D4, N-V ord (3)(5), N-V carry (2), S2-S6, S8, S9 | ALL RED: T-NS, T-stub, T-D4, N-V ordinary (at (3), `:240`), N-V carry (at (2), `:283`), S2, S3 x2, S4, S5 x2, S6, S8 x6, S9 |
| M2 | `get_or_fetch` stops passing `use_ladder` on | 11 failed | T-NS, T-D2, N-V (3) | RED: T-D2, T-NS, N-V x2 at (3); also S7 and S8 x6 (their fakes REQUIRE the keyword) |
| M3 | branch on `self._ladder_bars_fetcher is not None` only | 4 failed | T-NS, T-D2, N-V (3) | RED: T-D2, T-NS, N-V x2 at (3) |
| M4 | `get_or_fetch`'s default becomes `False` | 5 failed | T-D1, N-V (3) (detect-phase), S5 (`[True]*5`) | RED: T-D1, T-D2 (reverse order), N-V x2 (ordinary at (3)'s detect-phase list `:236`; carry at (2)), S7 (`[False] == [True]`). **S5 did NOT go RED** -- see D-1 |
| M5 | `_bars_store` key gains `use_ladder` | 3 failed | T-D2 | RED: T-D2 (`:96`), N-V x2 (warnings / `observe_load` counts differ) |

**M1, quoted for the merge report** (`exec\t2\mutations\M1.pytest.txt`): `tests\pipeline\test_observe_ladder_detach.py:125: AssertionError: assert ['OOT'] == []` -- with observe passing `use_ladder=True`, T-NS's fresh-cache populate reaches the ladder hook, and goes RED.

### 4.5 The two-pair neutrality outputs on HEAD (`exec\t2\nv_quote.py`, `exec\t2\nv_quote.out`)

```
=== ordinary pair (carry=False)
today: nrows=6 providers=[(1, 'yfinance'), (2, 'yfinance'), (3, 'yfinance'), (4, 'yfinance'), (5, 'yfinance'), (6, 'yfinance')]
today: schwab_calls=[('detect', 'DPT'), ('observe', 'OOT'), ('observe', 'FBK')]
today: store_before_observe=[('DPT', 400)]  (store-miss pre-assertion: OOT/FBK absent = True)
today: schwab_files=['DPT', 'OOT'] observe_downloads=['OOT', 'FBK']
today: observe_load={'step': 'pattern_observe', 'metric': 'observe_load', 'observed': 6, 'fetch_window': 2, 'in_memory_hit': 4, 'resolve_reads': 3}
detach: nrows=6 providers=[(1, 'yfinance'), (2, 'yfinance'), (3, 'yfinance'), (4, 'yfinance'), (5, 'yfinance'), (6, 'yfinance')]
detach: schwab_calls=[('detect', 'DPT')]
detach: store_before_observe=[('DPT', 400)]  (store-miss pre-assertion: OOT/FBK absent = True)
detach: schwab_files=['DPT'] observe_downloads=['OOT', 'FBK']
detach: observe_load={'step': 'pattern_observe', 'metric': 'observe_load', 'observed': 6, 'fetch_window': 2, 'in_memory_hit': 4, 'resolve_reads': 3}
rows equal: True
differences: []
OOT det_ids: [1, 2]
warnings equal: True; downloads equal: True
=== carry pair (carry=True)
today: nrows=6 providers=[(1, 'schwab_api'), (2, 'schwab_api'), (3, 'schwab_api'), (4, 'schwab_api'), (5, 'yfinance'), (6, 'yfinance')]
today: schwab_calls=[('detect', 'DPT'), ('observe', 'OOT'), ('observe', 'FBK')]
today: store_before_observe=[('DPT', 400)]  (store-miss pre-assertion: OOT/FBK absent = True)
today: schwab_files=['DPT', 'OOT'] observe_downloads=['OOT', 'FBK']
today: observe_load={'step': 'pattern_observe', 'metric': 'observe_load', 'observed': 6, 'fetch_window': 2, 'in_memory_hit': 4, 'resolve_reads': 3}
detach: nrows=6 providers=[(1, 'yfinance'), (2, 'yfinance'), (3, 'schwab_api'), (4, 'schwab_api'), (5, 'yfinance'), (6, 'yfinance')]
detach: schwab_calls=[('detect', 'DPT')]
detach: store_before_observe=[('DPT', 400)]  (store-miss pre-assertion: OOT/FBK absent = True)
detach: schwab_files=['DPT'] observe_downloads=['OOT', 'FBK']
detach: observe_load={'step': 'pattern_observe', 'metric': 'observe_load', 'observed': 6, 'fetch_window': 2, 'in_memory_hit': 4, 'resolve_reads': 3}
rows equal: False
differences: [('LABEL', 1, 'schwab_api', 'yfinance'), ('LABEL', 2, 'schwab_api', 'yfinance')]
OOT det_ids: [1, 2]
warnings equal: True; downloads equal: True
```
Ordinary: rows equal. Carry: the rows differ EXACTLY on OOT's two rows' provider label (`schwab_api` -> `yfinance`), with no non-label difference; DPT `schwab_api` in both (L-2), FBK `yfinance` in both. The store-miss pre-assertion holds in all four worlds.

### 4.6 Deviations from the plan's letter (none code-bearing)

- **D-1, the plan's M4 row is mis-stated for S5.** M4 changes the REAL `OhlcvCache.get_or_fetch` default; S5's `_TeleStub` carries its OWN default (`use_ladder=True`, plan S5), so its five prior-step calls are unaffected and `[True]*5 + [False]` still holds. M4 is still killed, by T-D1, T-D2, both N-V tests and S7. No code or test moves; recorded for the orchestrator.
- **D-2, the step-1 comment is wrapped.** The plan's one-line text for `runner.py:3118` is 115 columns, over the repo's 100-column E501 limit, so it is two comment lines with the same words (`runner.py:3124-3125`).
- **D-3, two signatures are wrapped.** `get_or_fetch`'s signature and `_bar_for_date`'s populate call are wrapped as three and two lines; the tokens are the plan's.
- **D-4, CHARC's minor in X1 clause (ii)** ("from observe"), section 2.
- **D-5, a style commit after the pre-review suite.** `71598097` changes only the import order in one new test file and adds `strict=True` to one `zip` in another; both files were re-run (5 passed). The final-head suite after the review covers it.

## 5. Reviewer A round table and rounds

| round | tier / model / effort (banner) | footer | verdict token | `^ERROR` | crit | major | minor | new / reopened | reverts | tokens used | context depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | strong / `gpt-5.6-sol` / `high` (equal to `~/.codex/strong.config.toml`'s `model` and `model_reasoning_effort`) | present (1) | the clean token, 2 anchored occurrences (the CLI's double emission); the findings token 0 | 0 | 0 | 0 | 2 | 2 new / 0 reopened | 0 | 205,725 | |

**Loop status: CONVERGED AT ROUND 1** (the first clean verdict; zero new critical/major). The two post-verdict minors were ruled by the orchestrator at the round gate and fixed without a new round (section 6).

**Spend (executing phase, Reviewer A):** 205,725 tokens (round 1).

### Round 1

**Invocation.** `wsl.exe bash -lc 'bash <scratchpad>/d90exec/codex/run_round.sh 1'`. The runner (LF; `file`: "Bourne-Again shell script, ASCII text executable") runs, from the worktree as cwd (repo access, `-s read-only`), `cat prompt-r1.md ledger-cut-r1.md <plan> diff-r1.txt | codex exec -p strong -s read-only --skip-git-repo-check -`. The output and exit files were pre-created Windows-side. The diff is `git diff -U8 e7f91d80..HEAD -- swing tests` at `4ebd433f` (59,865 bytes), generated on Windows.

**Inputs.** The prompt states the declared envelope, the accepted limitations L-1..L-6 with their reasons, the brief's nine-item checklist, the do-not-read list (both ledgers, `.codex-*`, `.copowers-*`, `comms/`), Codex is told not to run git, and the verdict tokens are DESCRIBED, never written line-initially. The ledger cut is the plan ledger sections 0-5 (cut before section 6) plus the two clearances verbatim. An anchored grep of the prompt, the cut, the plan and the diff for either token: 0 each. The plan-round scratch (`.codex-*`, `.copowers-findings.md`) was relocated out of the worktree to the session scratchpad for the loop (`find . -maxdepth 4` after the move: none left).

**Assertions.**

| assertion | result |
|---|---|
| exit code, MEASURED | 0 (the exit file; the WSL wrapper also exited 0) |
| transcript | 921,186 bytes, non-empty |
| `model:` banner | `gpt-5.6-sol` = the strong profile's declared model |
| `reasoning effort:` | `high` = the strong profile's declared effort |
| `^ERROR` | 0 |
| `^tokens used` | 1 (205,725) |
| verdict | the clean token, anchored, 2 occurrences (the CLI's double emission); the findings token 0 |
| codex process | exited: the exit file was written before the transcript was read |

**Prior-round / scratch reads:** none. Every `exec` command in the transcript was listed: CLAUDE.md and `docs/orchestrator-context.md` reads, `rg`/`nl`/`sed` over `swing/` and `tests/`, one `rg` that excluded `*.exec-ledger.md`, and failed pytest attempts (WSL python3 has no pytest). No read of either ledger, of `.codex-*`/`.copowers-*`, or of `comms/`. The transcript's ledger/comms path hits are the prompt and the ledger-cut echo, and CLAUDE.md / orchestrator-context prose naming other arcs' ledgers. Content filter: none reported.

**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d90-detach\exec\round1\`: `codex-review-r1.txt` (921,186 bytes), `prompt-r1.md`, `ledger-cut-r1.md`, `diff-r1.txt`, `run_round.sh`, `codex-exit-r1.txt`, `final-r1.txt` (the final-message region) and `copowers-findings.md`.

**Codex's checklist (verbatim summary of the final message; full text in `final-r1.txt`):** 1 HOLDS (`runner.py:3139`); 2 HOLDS; 3 HOLDS (`ohlcv_cache.py:500`); 4 HOLDS; 5 HOLDS; 6 HOLDS; 7 HOLDS; 8 FAILS (R1-01 below); 9 HOLDS. "I could not execute pytest because the available `python3` environment lacks pytest; all 12 changed files parsed successfully with `ast`, and the production/static caller censuses were inspected directly."

**Adjudication (proposed at the gate; RULED in section 6).**

| id | reviewer severity | finding | verified at the code | proposed disposition |
|---|---|---|---|---|
| R1-01 | minor, OUT-OF-ENVELOPE | `get_or_fetch`'s Concurrency paragraph (`ohlcv_cache.py:215-221`) says two racing fetches "see the same archive-source so values are identical"; with opposite `use_ladder` settings one goes through the hook and one direct. | Partly. In production the hook's return is `resolve_full_archive_bars`' re-read of the same `read_or_fetch_archive` archive (`marketdata_ladder.py:549-551`), so the values ARE identical except ledger K-2's one exception (an empty archive with a Schwab success returns the Schwab window, `:552-555`). The sentence is unqualified, and the paragraph sits inside `get_or_fetch`, an IN function, but outside the plan's listed replacement (the Routing paragraph). | ACCEPT as a docstring-only qualification, no round: name the K-2 exception in the Concurrency sentence. It is text, not code, but it is a `swing/` text edit the plan did not list, so the cell asks the orchestrator to rule before applying it. Alternative: DECLINE, citing K-2 (no production caller races the two settings: observe runs sequentially in the nightly and nothing in the web process passes False). |
| R1-02 | minor | T-D4 (`test_observe_ladder_detach.py:175`) records an absent `use_ladder` and an explicit `use_ladder=None` the same way; `None` is falsy in the production branch, so a future caller passing `None` would bypass the ladder unseen. | Yes: the walk maps a missing keyword to `None`, and `ast.literal_eval` of a literal `None` is also `None`. | ACCEPT, test-only, no round: record keyword PRESENCE separately (a sentinel for "absent"), so the closure asserts the only call carrying the keyword at all is `_bar_for_date`'s `False`. |

All nine checklist items: 8 HOLD, 1 FAILS (R1-01, minor).

## 6. Orchestrator rulings at the round-1 gate, the fixes, and the final head

### 6.1 The rulings (verbatim). Author: the orchestrator.

> R1-01: ACCEPTED as a docstring-only qualification, with no new round. The Concurrency paragraph at `swing/web/ohlcv_cache.py:215-220` sits in a file D90 already edits, and D90 creates the two postures that make "the same archive-source" partly false. That makes it a #31 docstring describing what the code does today, not a code-bearing change, so it does not re-open the clearance. Qualify the sentence in place, by replacement: two racing fetches on the same key see the same archive, so their values agree, EXCEPT ledger K-2's case (an empty archive with a Schwab success under `use_ladder=True`, where the ladder stores its Schwab sub-window). Name K-2. Add nothing else.
> R1-02: ACCEPTED, test-only, with no new round. T-D4 records keyword PRESENCE with a sentinel for "absent", so an explicit `use_ladder=None` is distinguishable from an omitted keyword.
> D-1 (the plan's M4 row wrong about S5): ACCEPTED as recorded. M4 is still caught by T-D1, T-D2, both N-V tests and S7.
> Round 1 counts as CONVERGED: the first clean verdict, with post-verdict minors fixed and no new round.

### 6.2 The fixes (separate commits, pathspec-only, `%(trailers)` empty)

- **R1-01, `a2bee0f6`** `docs(web): R1-01 -- get_or_fetch's concurrency sentence names the K-2 exception (D90)`. The sentence "Both fetches see the same archive-source so values are identical; no data corruption." is replaced by "Both fetches see the same archive, so their values agree, EXCEPT the D90 ledger's K-2 case: an empty archive with a Schwab success under ``use_ladder=True``, where the ladder stores its Schwab sub-window. No data corruption." (`swing/web/ohlcv_cache.py:218-222`). Nothing else changes; `ruff check swing/` clean.
- **R1-02, `f71467dc`** `test(pipeline): R1-02 -- T-D4 records use_ladder presence with a sentinel (D90)`. A module `_ABSENT = object()` marks an omitted keyword; a present keyword records its literal value, so `use_ladder=None` counts as carrying the keyword. Discrimination, measured (`exec\t2\r1-02\`): a scratch `use_ladder=None` added to detect's call at `runner.py:2195` (`none_mutant.diff`) leaves the PRE-fix T-D4 PASSING (`none_mutant_prefix_test.txt`: 1 passed) and turns the fixed T-D4 RED (`none_mutant.txt`: `AssertionError` at `test_observe_ladder_detach.py:188`); `git diff --exit-code swing/` returned 0 after each.
- **Touched files re-run:** `test_observe_ladder_detach.py`, `test_ohlcv_cache_use_ladder.py`, `test_observe_ladder_detach_neutrality.py`: 8 passed (`exec\t2\r1-02\touched_rerun.txt`).

### 6.3 The final head

- **Full fast suite** on `f71467dc` (the final code head; this ledger commit is docs-only), `python -m pytest -m "not slow" -q -n 8 -p no:cacheprovider`, saved with the head sha on its first line and a clean `git status --short` (`exec\t2\suite_final_head.txt`): **15525 passed, 13 skipped, 0 failed** in 717.28 s.
- **`ruff check swing/`:** All checks passed. **Touched test files, NEW findings vs base:** 0 in every file (conftest_temporal 4/4, fetch_vs_write 9/9, load_instrumentation 7/7, the other seven 0/0; `exec\t2\ruff_final.txt`).

### 6.4 Outcome

**CONVERGED at round 1.** Reviewer A spend: 205,725 tokens (one counted round). Reviewer B is the orchestrator's.
