# D90 plan ledger -- detach the Schwab ladder from observe's populate

**Plan:** `docs/superpowers/plans/2026-10-20-d90-observe-ladder-detach.plan.md`.
**Brief:** `docs/d90-observe-ladder-detach-plan-dispatch-brief.md` (@ `e7f91d80`).
**Worktree:** `.worktrees/d90-detach`, branch `d90-detach`, base `main` @ `e7f91d80`.
**Rulings read at:** `main` @ `d81f35ba`. `git diff --stat e7f91d80 d81f35ba -- swing tests scripts` is empty.
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d90-detach\plan\` (`round0\`, `round<N>\`).

## 0. How to read this ledger

Sections 1-5 are the record a plan reviewer reads: the rulings, the census, the intake corrections, the kept claims and the declared interpretations. Section 6 is the round table and the per-round adjudications. A reviewer's copy is CUT before section 6.

## 1. Rulings of record (verbatim)

### 1.1 RD -- F1 ruling, Branch A (`comms/orchestrator/read/20261020T072525Z-rd-d90-f1-rd-rules-branch-a-detach-always-j.md`). Author: RD.

> ---
> from: rd
> to: orchestrator
> type: status
> subject: D90 F1: RD rules BRANCH A (detach always); June = carry mechanism; O1 narrowed
> posted: 2026-10-20T07:25:25Z
> thread: d90
> ---
>
> RD RULING, D90 ROUND 0 FORK F1 (orchestrator query 20261020T072113Z). PRIMARY: RD on measurement. Read at this seat, live DB mode=ro and the live parquet (read only): the 12 carry dates' rows by provider with their created_at ranges, the June pipeline_runs rows, and a provider-divergence measurement over 230 tickers holding both parquet files.
>
> MY OWN CORRECTION FIRST. O1 said schwab_api "has never been exercised on an observation date" and "every measured bar is yfinance by construction". FALSE at its width: 9,474 of 337,582 rows (2.8%) carry schwab_api, on 12 observation dates. The five-night sample I generalised from was the four dead-token runs plus one weeknight, exactly the nights on which the mechanism cannot fire. A bounded sample reported as a total, my own section-6 entry. The O1 MECHANISM stands (end=None -> the vendor's previous-business-day default); its CONSEQUENCE was stated too wide.
>
> THE JUNE ROWS, EXPLAINED -- the same carry mechanism, by the clock. Each June carry date's schwab rows were written by a run that started AFTER 00:00 ET, so Schwab's "previous business day" was the observation session (created_at UTC -> HST -> the run): 06-05 <- run 90 (20:05 HST = 02:05 EDT); 06-08 <- run 96 (19:47 HST); 06-09 <- run 98 (23:44 HST); 06-11 <- run 100 (00:54 HST next day); 06-15 <- run 104 (19:02); 06-16 <- run 105 (20:56); 06-17 <- run 107 (22:11); 06-18 <- run 109 (18:25 HST = 00:25 EDT); 06-23 <- run 111 (21:13); 06-24 <- run 112 (20:06); 06-30 <- run 116 (07-01 06:30 HST = 12:30 EDT, data_asof 06-30). All twelve carry dates, June and 09-04, are ONE mechanism: observe ran while observation_date <= Schwab's previous business day. June's runs were hand-launched evenings before the 17:30 HST task existed. Nothing else needs explaining. NOTE ALSO: on every carry night the rows were MIXED within the night (06-30: 1,023 schwab / 305 yfinance; 09-04: 4,782 / 1,139) -- Schwab for tickers where the call succeeded, yfinance where it fell back. A uniform per-night source has NEVER held on a carry night.
>
> THE DIVERGENCE MEASUREMENT (does the provider matter in VALUE on an observation row?): 230 tickers with both files, 276,348 shared ticker-dates. Over ALL history, 1.85% of ticker-dates differ by more than 0.5% (max 75%): split-adjustment history, where yfinance back-adjusts and Schwab's stored rows do not (ABEO 102 dates, AGEN 452 dates -- pre-split spans). On the bars an observation row actually uses: the NEWEST shared bar per ticker, n=230, median 0, p99 0.06%, one ticker above 0.5% (a stale pair across a split); the TWELVE CARRY DATES, n=2,623, p99 0.00%, 7 of 2,623 above 0.5%; ALL dates since 2026-09-01, n=6,804, max 0.17%, none above 0.5%. CONCLUSION: on the observation date the two providers are value-equivalent to the cent in the overwhelming case; the provider on an observation row is a PROVENANCE label, not a value regime.
>
> F1 -- BRANCH A: detach always. Observe passes use_ladder=False on every call.
> Reasons:
> 1. Neutral where it can be measured (every non-carry night, which is every weeknight whose observe finishes before 00:00 ET: rows byte-equal on the six columns), and value-equivalent where it is not (carry nights: observe-only tickers' rows become yfinance; the close agrees with Schwab's to the cent at p99 on the measured carry dates). What changes on a carry night is the provenance LABEL on observe-only tickers, and the label is recorded per row, so nothing is lost.
> 2. Branch A makes the observation row's provider for an observe-only ticker DETERMINISTIC (always yfinance) and removes the midnight-split hazard that the widening makes likelier (observe lengthens; after DST the margin is about 76 min). Today's carry behaviour is a vendor-default accident that already yields MIXED providers within a night; A does not break a uniformity that exists, it narrows the mixing to detect-pool tickers on carry nights.
> 3. Branch B mirrors an unpinned vendor default in our own calendar code to preserve an accident. Declined.
> 4. A uniform-source alternative (observe's READ prefers yfinance for the observation date, so detect-pool tickers also record yfinance on carry nights) would need a provider-preference parameter on resolve_ohlcv_window -- a swing/data carve-out and a CHARC tripwire -- to remove a value-equivalent label mix on about two nights a year (the next carry night is Thanksgiving evening 2026-11-26, plus weekend runs with a live token). NOT WORTH A CARVE-OUT. BANKED, owner RD, trigger: a divergence read on a carry date showing more than 0.5% on more than 1% of that date's ticker pairs, OR a provider-conditioned analysis that needs one source.
>
> WHAT BRANCH A REQUIRES IN THE PLAN (measurement side; CHARC the form):
> (a) Admissibility (1) RESTATED as conditional: "neutral on non-carry nights by construction; on a carry night, observe-only tickers record yfinance where today they would record schwab_api, value-equivalent at the cent (measured), provenance label differs".
> (b) A VII.F BOUNDARY NOTE in the exec ledger and the watch-standard: the first post-detach pipeline_runs.id; from it, observe-only tickers' observation rows are yfinance by construction; detect-pool tickers may still carry schwab_api on carry nights. Written by RD at the merge, like the D82 note.
> (c) The neutrality test as TWO world pairs, as you proposed: the ordinary pair (rows equal) and the carry pair (rows differ EXACTLY on observe-only tickers' $.provider, with the OHLC values equal under the fixture -- the fixture feeds both providers the same bar so the test pins "label only"). The carry world is built by patching the ladder hook to return a window carrying the observation date; no clock predicate.
> (d) A READ CAVEAT for the watch-standard: $.provider is mixed on 12 historical carry dates and may mix on future carry nights for detect-pool tickers; any provider-sensitive analysis conditions on $.provider explicitly; value-level analyses need no conditioning (measured).
>
> THE 9,474 EXISTING ROWS: NOTHING. True bars from a real provider, provenance recorded per row, value-equivalent to the yfinance bar at the cent on the measured dates. No relabel, no correction row, no read change; the caveat in (d) is the whole treatment.
>
> THE PINNED TEST test_observe_remediation.py::test_success_path_overwrites_contaminated_before_lock: SUPERSEDED BY NAME under A, with the hazard it guarded stated so it is not silently dropped: a contaminated (non-finite) schwab_api row for the observation date, today healed by observe's own Schwab refetch. Under A: (i) no NEW contaminated row can be written -- the 18-B ladder write barrier trims trailing non-finite bars before write_window (marketdata_ladder.py:203-214); (ii) an observe-only ticker gets no schwab_api row at all after the boundary; (iii) a detect-pool ticker's row is refetched by detect's own ladder call on the next run. REPLACEMENT (CHARC's form): a test that observe under use_ladder=False never calls the ladder hook and reads the yfinance row; plus the existing interior-non-finite skip tests, untouched. The 34 stubs lacking **kw (six observe-facing) are the plan's: a stub that TypeErrors on use_ladder= would set populate_ok False and silently un-memoize -- the plan adds **kw or the keyword to every observe-facing stub BY NAME and pins one of them with a test that the populate path reports ok.
>
> CC on the row corrections (CHARC's): no dissent; the witness query's surface='pipeline' AND pipeline_run_id=<run> filter is right, the web hook writes surface='pipeline' with a NULL run id.
>
> TRANSCRIPTION: block-quote into the D90 plan ledger with RD as author; landed when the path is posted back.

### 1.2 CHARC -- Round 0 row corrections landed at `88b812a1` (`comms/orchestrator/read/20261020T072443Z-charc-d90-r0-row-corrections-landed-88b812a1-j.md`). Author: CHARC.

> ---
> from: charc
> to: orchestrator
> type: status
> subject: D90 R0: row corrections landed 88b812a1; June rows = after-midnight ET; B form
> posted: 2026-10-20T07:24:43Z
> thread: d90
> ---
>
> D90 ROUND 0 -- CHARC's items only. F1 is RD's; I hold on it. Landed at 88b812a1 (the D90 row, docs/tool-director-context.md).
>
> ONE RULER: PRIMARY RD for F1 and for whether the 9,474 rows need anything. This packet rules my two items and supplies one record fact for RD's June read.
>
> 1. ROW CORRECTIONS -- all four ACCEPTED, each re-run at this seat, landed in the row:
> - The populate is at runner.py:3132 (grep 2026-10-20 after D89).
> - No evaluate caller of get_or_fetch. The six pipeline callers are detect :2191/:2453, observe :3132, charts :3513/:3584/:3718 (grep -rn "get_or_fetch(" swing/). The row now says "the five other pipeline callers stay" and names them.
> - The witness query filters surface='pipeline' AND pipeline_run_id=<run>. Verified: the web bars hook writes surface="pipeline" with pipeline_run_id=None at app.py:579; 398 such rows live (mode=ro: 16,475 pipeline rows with a run id, 398 without). Run 195 has 277 pipeline rows with its run id, 238 of them in observe per your census.
> - Expected wall drop is AT LEAST the audited Schwab term (87,395 ms on run 195). Landed with your reason (189 parquet writes + audit rows also leave).
> - Census (2)-(4) recorded as the cell's findings; I did not re-read the warm's code myself and the row says so by method.
>
> 2. THE PREMISE -- I re-ran your probe on live mode=ro: schwab_api 9,474 / yfinance 328,108; the twelve dates and counts match yours exactly. Admissibility (1) is FALSIFIED as stated; the row now carries that with the mechanism.
>
> 3. RECORD FACT FOR RD's JUNE READ (a fact with its method, not a ruling): every June cluster of schwab_api observation rows was written AFTER 00:00 ET. Method: SELECT observation_date, min(created_at), max(created_at), count(*) FROM pattern_forward_observations WHERE provider='schwab_api' GROUP BY 1, mode=ro; created_at is UTC. Results, converted to EDT next-day: 06-05 at 02:16; 06-08 at 01:56; 06-09 at 05:53; 06-11 at 06:55; 06-15 at 01:05; 06-16 at 02:58; 06-17 at 04:13; 06-18 at 00:28; 06-23 at 03:15; 06-24 at 02:09; 06-30 at 12:32 (run 116 ran the next morning HST). The matching pipeline_runs.started_ts agree (run 90: 2026-06-05T20:05 HST = 02:05 EDT 06-06). So the June rows ARE your first candidate -- the nightly then ran 19:00-23:00 HST, which is after midnight Eastern. All 9,474 rows share ONE mechanism (observation_date <= Schwab's previous business day at call time); the 09-04 holiday night is the same rule from the other side. None is a designed regime. The condition your lean required ("if the June rows share the carry mechanism") is met on the record; the lean itself remains RD's to rule.
>
> 4. FORM OF BRANCH B, if RD rules it:
> - A pure additive helper in swing/evaluation/dates.py beside sessions_behind: schwab_default_window_carries(observation_date, now_local) -> bool, defined as observation_date <= _NYSE.previous_session(today in America/New_York). NOT last_completed_session: that counts today after the close and is a different quantity from the vendor's "previous business day".
> - _bar_for_date consults it per call to pick use_ladder; the clock is INJECTED (D9: no live-clock read inside the step), threaded from the step the way lease_data_asof is.
> - No tripwire: no module, no schema, no swing/data.
> - Costs, stated so the ruling carries them: it mirrors an UNPINNED vendor default (spec :350) from the NYSE calendar, so it is neutral only where the two calendars agree and that agreement is unverifiable except by execution; it PRESERVES the midnight-split hazard for observe-only tickers; it adds a second clock-coupled production predicate.
> - My lean on FORM only: A is the smaller change and removes the split; B is implementable but is the worse form. RD rules F1.
>
> 5. PLAN ITEMS UNDER EITHER BRANCH (for the plan, not for F1):
> - The stub sweep. I read four observe-facing stubs with (*, ticker, window_days) and no **kw: test_observe_load_instrumentation.py:20 and :110, test_observe_remediation.py:45 and :73. Your count of six stands as yours. The hazard is sharper than a TypeError: _bar_for_date's best-effort except swallows it, sets populate_ok=False, and the D89 memo silently un-memoizes, so a fixture defect reads as a populate miss. The plan asserts the kwarg REACHED the stub, not only that nothing raised.
> - test_observe_remediation.py::test_success_path_overwrites_contaminated_before_lock pins the behaviour branch A removes; it needs a named disposition in the plan, not a silent edit.
> - Branch A's neutrality test is two world pairs (ordinary night: rows equal; carry night: rows differ on exactly the observe-only tickers' provider), with the carry night built by injected clock, never by waiting for Thanksgiving.
>
> D90 HOLDS until RD rules F1. Nothing of mine is in flight.

### 1.3 CHARC -- CC on F1, no dissent; B moot; the store-miss form (`comms/orchestrator/read/20261020T072626Z-charc-d90-f1-charc-cc-no-dissent-b-form-moot-r.md`). Author: CHARC.

> ---
> from: charc
> to: orchestrator
> type: status
> subject: D90 F1: CHARC CC no dissent; B form moot; replacement test needs a store miss
> posted: 2026-10-20T07:26:26Z
> thread: d90
> ---
>
> CHARC, CC on RD's F1 ruling (20261020T072525Z): NO DISSENT. Branch A, detach always. My branch-B form in 88b812a1 is MOOT; recorded as such at d81f35ba.
>
> ONE FORM POINT, mine under RD's plan item (the replacement for test_observe_remediation.py::test_success_path_overwrites_contaminated_before_lock):
>
> - The replacement asserts that observe under use_ladder=False never calls the ladder hook and reads the yfinance row. That assertion is VACUOUS unless the fixture builds a _bars_store MISS for the observe-only ticker. A ticker already stored by a detect-time call is an in-memory hit under either posture, so the hook is never reached and the test passes with or without the flag (the fixture-routes-around-the-branch class). The plan states that the cache is fresh for that ticker, or that the store is cleared before the observe call, and verifies RED with the flag removed before GREEN.
> - Same requirement for the two-pair neutrality test's carry world: the patched hook is only reached on a store miss, so the carry pair must start from a cache that has not stored the observe-only ticker.
> - The stub sweep pins that the keyword REACHED the stub (a recording stub), not only that populate_ok stayed True.
>
> Everything else under A is as RD stated; the ledger transcription lands it. The plan-stage read on form is mine when the plan arrives.

### 1.4 The D90 register row (`docs/tool-director-context.md`, read at `main` @ `d81f35ba`). Author: CHARC (the row); RD's measurement call, the admissibility answer and the F1 ruling are quoted inside it.

> | D90 | **THE SCHWAB LEG OF OBSERVE'S POPULATE NEVER CARRIES THE OBSERVATION-DATE BAR — 238 Schwab round-trips a night (87 s, 16 % of run 195's wall) write nothing the measurement reads, and `_bar_for_date`'s docstring says the leg does not exist** | RD's O1 finding `20261020T041759Z`, CHARC-verified at code 2026-10-20: the pipeline bars hook calls `fetch_window_via_ladder(..., start=None, end=None, period_type="year", period=5, ...)` (`runner.py:481-495`); the wrapper passes `endDate=None` through (`marketdata.py:402`); Schwab's default for an absent `endDate` is the previous business day's market close (`reference/schwab-api/market-data-specification.md:350`); the nightly runs after that session's close, so the Schwab window ends at the PRIOR session by the vendor's default, not by a trim; the success path then re-reads the full archive through the yfinance window fn (`marketdata_ladder.py:505-530`), whose fetch runs through `last_completed_session(now())` and persists under `yfinance`. Live (RD's parquet read): ADPT/AMN/GEO `schwab_api` last 2026-10-16, `yfinance` last 2026-10-19; p09: yfinance on 6,934/6,934 rows on 10-19 and on all five nights read. `schwab_api` outranking `yfinance` (`ohlcv_archive.py:92-95`) has never been exercised on an observation date | Cost only, tonight (the temporal log's provider column IS the true series; nothing to correct); the design's assumed Schwab-first provider has never been the measured one | **OPEN — REGISTERED 2026-10-20 on the operator's word, then APPROVED BY NAME the same day (his words, via the orchestrator's courier record `20261020T054314Z`: "Yes, D90 after D89 and before soft-stop arc"); RIDER, owner ORCHESTRATOR; opens when D89 merges; before D84's widening (both shrink observe; the widening multiplies both).** RD's measurement call, binding: DETACH the ladder from observe's populate; do NOT pass an explicit `endDate` — that flips the observation bar's provider to `schwab_api` from that night, a measurement-regime change under VII.F with a boundary note, never a side effect of a cost fix. **CHARC FORM:** one additive keyword-only `use_ladder: bool = True` on `OhlcvCache.get_or_fetch` (`ohlcv_cache.py:175`), threaded to `_fetch_bars_window` (`:270`) where False takes the `read_or_fetch_archive` branch; observe's populate (`runner.py:3132`, re-grepped 2026-10-20 after D89) passes False; the bundle worker (`:491`, the dashboard's read) is untouched, so what the dashboard reads is unchanged BY CONSTRUCTION; the `_bars_store` is safe to share across postures because BOTH branches store the same full-archive read (the ladder hook returns `resolve_full_archive_bars`' archive re-read). No new module, no `swing/data`, no tripwire. **ADMISSIBILITY, stated:** (1) neutral for the OBSERVATION ROW by construction (the bar is never in the Schwab window today); (2) NOT neutral for prior-date rows of observe-only tickers — their `schwab_api` parquet stops advancing from the detach night; **ANSWERED by RD 2026-10-20 (`20261020T054502Z`, whole-`swing/` grep + read): `resolve_ohlcv_window` (`ohlcv_archive.py:1027-1028`) is the ONLY code that opens `{TICKER}.schwab_api.parquet`; its two callers are observe (selects the observation-date row only, yfinance by construction) and the latch reader (`latches/reader.py:695`, `close` only, provenance discarded, asserts no provider; the web process runs its OWN ladder, so a viewed latched ticker refreshes independently). NO reader asserts prior-date Schwab presence or freshness — ADMISSIBLE, on the condition the plan encodes: the detach is of the PIPELINE observe populate ONLY (`use_ladder=False` from `_bar_for_date`); the web cache's ladder and the five other pipeline callers stay -- detect `:2191`/`:2453` and charts `:3513`/`:3584`/`:3718`; THERE IS NO EVALUATE CALLER of `get_or_fetch` (the evaluate warm writes the legacy archive + meta, never `_bars_store`; `grep -rn "get_or_fetch(" swing/` 2026-10-20); the plan's closure grep names both callers and states neither changes; the residual (a latched-then-rotated, never-viewed ticker carries a provider-mixed range, today's shape whenever Schwab misses a day) stated in the merge report;** (3) the one-miss-per-ticker reading (238 Schwab + 8 singles + fallbacks ≈ 248 tickers) is consistent with the D83 warm writing the ARCHIVE and not the `_bars_store` — the cell verifies this at the warm's code before the plan quotes it. **WITNESS:** `schwab_api_calls` rows with `surface='pipeline' AND pipeline_run_id=<run>` inside the observe step = 0 on the merged night (the web bars hook ALSO writes `surface="pipeline"` with `pipeline_run_id=None`, `app.py:579`; 398 such rows live, so an unfiltered count is wrong by construction); the wall drop is AT LEAST the audited Schwab term (87,395 ms on run 195) because the detach also removes 189 parquet writes and the audit-row writes; observe wall drop ≈ the audited Schwab term; observation rows byte-equal on the N-V set; the docstring reads as the code does. **ROUND 0 (2026-10-20, the orchestrator's cell, CHARC re-ran the probe on live `mode=ro`): ADMISSIBILITY (1) IS FALSIFIED AS STATED** -- `pattern_forward_observations` carries 9,474 `schwab_api` rows (328,108 `yfinance`) over twelve observation dates: eleven in June 2026 (20..1,023 rows) and 2026-09-04 (4,782, run 170 on Labor Day evening). The carry mechanism: the observation bar IS in Schwab's default window whenever `observation_date <= the vendor's previous business day` at call time -- a weekday-holiday evening, a weekend run with a live token, or ANY populate after 00:00 ET. The June rows are the third form: every June cluster's `created_at` converts to 00:28..05:53 EDT the next day (run 90 started 2026-06-05T20:05 HST = 02:05 EDT; `SELECT observation_date, min(created_at) ... GROUP BY 1`, mode=ro), so ALL 9,474 share ONE mechanism and none is a designed regime. Run 195's last observe Schwab call was ~16 min before midnight ET (~76 min after DST ends 11-01), so today's code can SPLIT one night's rows between providers if observe crosses midnight; the widening lengthens observe. **FORK F1 is RD's (measurement): A = detach always (observe-only tickers become uniformly `yfinance`; carry-night rows differ on exactly those tickers; needs (1) restated as conditional, a VII.F boundary note, and the neutrality test as TWO world pairs) vs B = detach only where neutral (keep the ladder when the predicate says carry). CHARC's form of B if ruled:** a pure additive helper in `swing/evaluation/dates.py` beside `sessions_behind` (`schwab_default_window_carries(observation_date, now_local) -> bool`, = `observation_date <= _NYSE.previous_session(today_NY)`; NOT `last_completed_session`, which counts today after the close and is a different quantity), consulted per call in `_bar_for_date` to pick `use_ladder`, clock INJECTED (D9: never read the live clock inside the step); no tripwire. Its costs, stated: it mirrors an UNPINNED vendor default (spec `:350`) from the NYSE calendar, so it is neutral only where the two calendars agree and is unverifiable except by execution; it PRESERVES the midnight-split hazard; it adds a second clock-coupled production predicate. CHARC's lean on form: A is the smaller, cleaner change and removes the split; B is implementable but is the worse form. RD rules. **Plan items under either branch:** 34 `get_or_fetch` stubs in 26 test files, at least four observe-facing ones take `(*, ticker, window_days)` with no `**kw` (`test_observe_load_instrumentation.py:20,110`, `test_observe_remediation.py:45,73`), so `use_ladder=False` raises `TypeError` INSIDE `_bar_for_date`'s best-effort `except`, which sets `populate_ok=False` and silently un-memoizes (the D89 condition masking a fixture defect) -- sweep them, and assert the kwarg reached the stub; `test_observe_remediation.py::test_success_path_overwrites_contaminated_before_lock` pins observe refetching a `schwab_api` observation-date row, which branch A removes -- it needs a disposition. The 248 split is 238 observe misses (189 Schwab successes + 49 errors falling back) + 10 detect-stored; the 8 singles are inside the 238. **F1 RULED BY RD 2026-10-20 (`20261020T072525Z`): BRANCH A, detach always** -- providers value-equivalent at the cent on the observation date (230 tickers, carry dates p99 0.00%), so the row's provider is a provenance LABEL; B declined as mirroring an unpinned vendor default; a uniform-source read BANKED (owner RD; a `swing/data` carve-out if ever triggered); the 9,474 rows need NOTHING; admissibility (1) restated conditional, VII.F boundary note at the merge (RD), neutrality test as TWO world pairs with the carry world by PATCHED HOOK (no clock predicate). CHARC: no dissent; the B form above is MOOT. CHARC's form for the replacement of the superseded contaminated-row test: it must build a `_bars_store` MISS for the observe-only ticker (a fresh cache), or a detect-stored ticker is an in-memory hit under either posture and the assertion that the hook is never called passes vacuously. RD's ruling lands when block-quoted into the D90 plan ledger. |

### 1.5 The orchestrator's resume directives (chat, 2026-10-20). Author: the orchestrator.

> RESUME directive (first message):
>
> RESUME, D90 writing-plans. Both directors have ruled. For this resume ONLY, you may read these two rulings of record in the main repo:
> - `comms/orchestrator/read/20261020T072525Z-rd-d90-f1-rd-rules-branch-a-detach-always-j.md` (RD: F1 = BRANCH A, plus the plan requirements);
> - `comms/orchestrator/read/20261020T072443Z-charc-d90-r0-row-corrections-landed-88b812a1-j.md` (CHARC: row corrections landed at 88b812a1, the June mechanism fact, and the plan items).
>
> Also re-read the D90 row on main as amended at 88b812a1. Read nothing else from comms/.
>
> Block-quote BOTH mails, in full, into the plan ledger with their authors named. Then write the plan encoding them:
> - BRANCH A: observe ALWAYS passes `use_ladder=False`, in CHARC's one-keyword form.
> - Admissibility (1) restated as CONDITIONAL, in RD's words.
> - A VII.F boundary note, which RD writes at merge. The plan carries the slot and names the first post-merge run as the boundary.
> - The two-pair neutrality test, in RD's form:
>   - ordinary pair: rows equal on the six columns;
>   - carry pair: rows differ on exactly the observe-only tickers' provider.
>   - Build the carry world by a PATCHED HOOK, never a clock predicate and never by waiting.
> - The watch-standard read caveat, as RD words it.
> - `test_observe_remediation.py::test_success_path_overwrites_contaminated_before_lock` SUPERSEDED BY NAME, with its hazard stated, not silently edited.
> - `**kw`, or an explicit `use_ladder`, added to EVERY observe-facing `get_or_fetch` stub, BY NAME. Each test must assert the kwarg REACHED the stub (CHARC 5): a fixture defect must not read as a populate miss that silently un-memoizes D89.
> - The witness filters `surface='pipeline' AND pipeline_run_id=<run>`. The expected wall drop is at least 87.4 s.
> - The closure grep names both `resolve_ohlcv_window` callers as unchanged, and the five other pipeline `get_or_fetch` callers as staying on the ladder.
> - The `_bar_for_date` docstring is rewritten by REPLACEMENT to what the code does after D90.
> - The uniform-source alternative is BANKED (RD), not D90's.
>
> Then run the plan-stage rounds, per your brief section 3:
> - fast tier, at most three counted rounds;
> - a per-item checklist;
> - the ledger cut or the rulings inlined;
> - STOP AND RETURN at EVERY counted round gate with its ledger row.
>
> You never post to a mailbox or run role_mail. If anything does not fit, STOP and return.
>
> ADDITION (second message):
>
> ADDITION to the D90 resume. CHARC posted a CC on RD's F1 ruling with NO DISSENT, and branch B's form is moot. It also raised one binding FORM point. Read `comms/orchestrator/read/20261020T072626Z-charc-d90-f1-charc-cc-no-dissent-b-form-moot-r.md` and block-quote it in the ledger with CHARC as author. In short:
> - The replacement for `test_success_path_overwrites_contaminated_before_lock` must build a `_bars_store` MISS for the observe-only ticker: a fresh cache, or the store cleared before the observe call. Otherwise the hook is never reached and the test is vacuous. Verify it RED with the flag removed before GREEN.
> - The carry world of the two-pair neutrality test must likewise start from a cache that has NOT stored the observe-only ticker.
> - The stub sweep uses RECORDING stubs that pin the keyword REACHED the stub, not only that `populate_ok` stayed True.
>
> Encode all three in the plan. Everything else is as already sent.

## 2. Census

### 2.1 Round 0 (the first pass of this cell, 2026-10-20; no Codex)

Evidence: `round0\probe1.out`-`probe5.out`, `probe_parquet.out`, `pipeline_log_step_lines_runs_170_195.txt`. Live DB `mode=ro`, plain sqlite3; the parquet probe read COPIES only.

- **Premise 1, CHARC's form is implementable: HOLDS, with two precisions (K-2, K-5).**
- **Premise 2, one miss per ticker, the warm writes the archive only: HOLDS.**
  - `warm_archives_batch` (`ohlcv_archive.py:623`) writes the legacy `{T}.parquet` and meta through `_merge_gap_subframe` (:579, :608) and `_write_full_refresh_subframe` (:617-620). It takes no cache argument.
  - The run 195 decomposition: 248 open-detection tickers = 238 observe misses (189 Schwab successes + 49 errors falling back to yfinance) + 10 tickers detect had already stored. The 8 yfinance singles are inside the 238.
- **Premise 3, the ordering hazard: HOLDS (K-4).**
- **Premise 4, the baselines (run 195):**
  - observe window 17:34:32.970 to 17:43:34.661 HST; observe wall 541,691 ms;
  - `surface='pipeline' AND pipeline_run_id=195` rows in that window: 238, summed 87,395 ms; NULL-run-id rows in the window: 0;
  - 6,934 rows, all `yfinance`;
  - `observe_load` `{6934, 238, 6901}`;
  - no post-D89 nightly exists: D89 merged at 2026-10-19 20:53:54 HST, and run 195 finished at 17:44:13.
- **The premise that FAILED: admissibility (1) and "never exercised".**
  - 9,474 `schwab_api` observation rows sit on 12 dates.
  - Run 170 (Labor Day evening 2026-09-07) wrote 4,782 of 5,921 rows (183 of 223 tickers) as `schwab_api`.
  - There is one mechanism: `observation_date <=` Schwab's previous business day at call time. The June rows were all written after 00:00 ET (1.1, 1.2 item 3).
  - This opened fork F1. RD RULED Branch A (1.1). CHARC: no dissent (1.3).

### 2.2 Resume census (2026-10-20): every cache on `_bar_for_date`'s path

- **p20 (runtime; `round0\p20_reach_probe_plugin.py`, `round0\p20_reach_all.tsv`).** A scratch pytest plugin wrapped `swing.pipeline.runner._bar_for_date` and recorded each call's cache class and `get_or_fetch` qualname. It ran over `tests/pipeline tests/integration` at the base, `-m "not slow"`: 532 passed. 33 tests reach `_bar_for_date`, through these cache classes (tests):
  - the real `OhlcvCache` (8): 6 through `test_observe_read_memo.py::_real_cache`, whose instance `_fetch_bars_window` is replaced; 2 no-hook N-V worlds;
  - `_StubOhlcvCache` (15);
  - `_TeleStub` (2);
  - `_DeadlockProbeCache` (2);
  - `test_bar_for_date_allows_completed_day.<locals>._Cache` (1);
  - `test_bar_for_date_rejects_current_day.<locals>._Cache` (1; entered, but the L3 guard raises before the populate);
  - `test_success_path_overwrites_contaminated_before_lock.<locals>._Cache` (1; X1);
  - `test_failure_path_then_purge_falls_to_clean_yfinance.<locals>._NoOpCache` (1);
  - `test_observe_populate_uses_the_window_constant.<locals>._RecCache` (1);
  - `test_observe_scaling_one_obs_per_open_detection.<locals>._Stub` (1).
- **p21 (runtime; `round0\p21_reach_chart_fullpipeline.tsv`).** `test_runner_chart_targets.py` and `test_step_charts_classification.py` run the full pipeline under class-level `OhlcvCache.get_or_fetch` patches (:221/:229 and :157). Across their 19 tests, `_bar_for_date` is called ZERO times: no detection reaches observe.
- **Static.**
  - `grep -rn "def get_or_fetch" tests/` finds 34 defs in 26 files. That is a lower bound for stubs.
  - Class-level `setattr` patches: `test_runner_chart_targets.py:229`, `test_step_charts_classification.py:157`, and the web-only `tests/web/test_routes/test_hyp_recs_expand_route.py:481` and `tests/web/test_view_models/test_watchlist.py:315,507`.
  - Instance `_fetch_bars_window` replacements: `test_observe_load_instrumentation.py:50` (direct calls, not observe) and `test_observe_read_memo.py:87`.
  - The seven files that patch `_install_pipeline_marketdata_caches` do not drive observe. Method: each was grepped for `_step_pattern_observe`, `_bar_for_date` and detections; the only hits are source-inspection tests.
- **p22 (static AST; `round0\p22_get_or_fetch_ast.py` and `.out`).** 10 `.get_or_fetch(` calls in `swing/`, none with `use_ladder`:
  - `runner.py`: `_step_pattern_detect` :2191 and :2453; `_bar_for_date` :3132; `_step_charts` :3513, :3584 and :3718;
  - `swing/trades/review_auto_fill.py:151`;
  - `swing/web/chart_jit.py:119`, `swing/web/routes/dashboard.py:103` and `swing/web/routes/recommendations.py:285`.
- **Compatibility.**
  - `test_ohlcv_cache_concurrent_fetch_no_race.py::test_ohlcv_cache_get_or_fetch_invariant` asserts only the presence and KEYWORD_ONLY kind of `ticker` and `window_days` (:233-238), so an added keyword-only parameter passes.
  - The Protocol at `swing/trades/review_auto_fill.py:44-50` is structural, so it is unaffected at runtime.
- **Prototypes (scratch, run while round 1 ran; NOT deliverables; `round0\p23_nv_proto.py` and `p23.out`, `round0\p24_tns_proto.py` and `p24.out`).** The plan's N-V world and T-NS fixture were built on the BASE code. The detach was EMULATED by clearing the hook for observe-phase calls, which is the branch `use_ladder=False` takes. Every value the plan claims was reproduced:
  - **ordinary:** rows equal, all `yfinance`;
  - **carry:** the only difference is the LABEL on OOT's two rows (`schwab_api` today, `yfinance` with the detach); DPT is `schwab_api` and FBK `yfinance` in both worlds;
  - **calls and state:** the Schwab calls `[detect DPT]` plus observe `[OOT, FBK]` today, versus `[detect DPT]` with the detach; store `{("DPT", 400)}`; `schwab_files` `{OOT, DPT}` versus `{DPT}`; downloads equal; `observe_load` 6/2/4/3;
  - **T-NS:** today, the hook is called once and the row is 9.5 / `schwab_api`; with the detach, there is no hook call and the row is 9.0 / `yfinance`, with zero downloads and `fetch_window` 1.
- **Codex.** `codex-cli 0.162.1` (WSL). The fast profile `~/.codex/fast.config.toml` declares `model = "gpt-5.6-luna"` and `model_reasoning_effort = "medium"`, and every plan-round banner is asserted against those.

## 3. Intake corrections (a ruling's incidental FACTS checked against the code; the reasoning stays binding)

- **C-1, the superseded test's hazard (RD 1.1).** RD names "a contaminated (non-finite) schwab_api row". The test seeds an ext-hours-INFLATED, FINITE row instead (`tests/pipeline/test_observe_remediation.py:22-26`: high=99, "a pre-fix ext-hours-inflated"). BOTH closures are encoded in X1's comment:
  - L1 `needExtendedHoursData=False` (`swing/integrations/schwab/marketdata.py:390-403`, `_build_price_history_client_method`) for the inflated class;
  - for the non-finite class, `OhlcvBar.__post_init__` (`swing/integrations/schwab/models.py:561-582`), which rejects any non-finite OHLC at construction, so no Schwab bar can be non-finite.
  - RD cited the 18-B trim at `marketdata_ladder.py:203-214`; the code confirms it at :202-214. It trims TRAILING non-finite bars only and keeps interior ones by design (`ohlcv_archive.py:235-282`), so it is a belt, not the closure. Codex R1-01 made the point, and the X1 comment was corrected (section 6, round 1).
- **C-2, how the carry world is built.** CHARC 1.2 item 5 reads "with the carry night built by injected clock". RD 1.1 (c), CHARC's later 1.3 and the orchestrator (1.5) say PATCHED HOOK, with no clock predicate. Encoded: the production hook's composition, with its Schwab leg (`get_price_history`) patched, and carry as the fixture parameter `schwab_end` (plan AL-9, L-4).
- **C-3, the stub counts.**
  - RD says "34 stubs lacking **kw (six observe-facing)"; CHARC 1.2 says "at least four". Measured (2.2): 34 defs in 26 files.
  - Not all 34 lack `**kw`: `test_lock_guard_completed_day.py:26,42` take `**k`.
  - On observe's path there are nine stub sites (S1-S6, S8, S9 and X1's `_Cache`). S7 is broken by AL-2's threading, but it is not on observe's path.
- **C-4, the "evaluate" caller.** The brief's "evaluate" caller of `get_or_fetch` does not exist; the row was corrected at `88b812a1`.
- **C-5, the wall witness.** The row's WITNESS says both "≈ the audited Schwab term" and "AT LEAST". Encoded AT LEAST, per CHARC 1.2 item 1 and the orchestrator (1.5).
- **C-6, "the same bar" (RD 1.1 (c)).** `OhlcvBar.volume` is an `int` (`swing/integrations/schwab/models.py:559`). The fixture passes `1000+i`. `_bar_for_date` floats `volume` (`runner.py:3169`), so the observation JSON is equal across providers.

## 4. Kept claims (each with the MECHANIC that makes it true and the SURFACE it was measured on)

- **K-1, the `resolve_ohlcv_window` call is byte-identical.** Mechanic: no edit at `runner.py:3148-3151` (D89 AL-6). Surface: the T2 diff.
- **K-2, the `_bars_store` is safe to share across settings (CHARC FORM).**
  - Mechanic: both branches end in `read_or_fetch_archive(ticker, end_date=last_completed_session(now), cache_dir=cfg.paths.prices_cache_dir, archive_history_days=cfg.archive.archive_history_days)`: the hook through `resolve_full_archive_bars` (`marketdata_ladder.py:549`, `runner.py:449-454`), and the no-ladder arm directly (`ohlcv_cache.py:284-289`). The same `cfg` builds the cache (`runner.py:383`). Both then share the strip and slice (:302-311).
  - The one exception: an EMPTY archive with a Schwab success. The ladder stores the Schwab window (`marketdata_ladder.py:552-553`); `use_ladder=False` raises and stores nothing.
  - Why it is still safe: the observe key `(T, 400)` is shared only with detect (:2191, :2453), which runs BEFORE observe. Charts use 300 and 390. `_bar_for_date` discards the populate's return.
  - Surface: a code read at `e7f91d80`.
- **K-3, one miss per ticker (2.1, premise 2).**
- **K-4, a detect-stored ticker is a TTL hit in observe under either setting.** Mechanic: the shared key (AL-3); TTL 3600 s (`config.py:582`); on run 195 detect's calls (from 17:34:05) precede observe's last call (17:43:34) by under 10 minutes. Rows depend only on disk, which detect's ladder call wrote identically in both worlds. Surface: code; pinned by N-V (4) and carry (2) for DPT.
- **K-5, the observation row on the ladder's FALLBACK path equals the no-ladder row.**
  - Mechanic: the fallback writes `{T}.yfinance.parquet` from the `read_or_fetch_archive` frame through `normalize_legacy_dataframe` (`marketdata_ladder.py:161`, :484). The no-ladder read reaches the same rows through `_backward_compat_rename`'s copy of the legacy file (`ohlcv_archive.py:1020-1021`, the same normalizer).
  - Surface: code; pinned by FBK in the N-V.
- **K-6, D89's T-H2 (`test_raise_over_archived_yfinance_then_schwab_write_outranks`) writes `schwab_api` in a scripted populate.** After D90, production observe never writes `schwab_api`. T-H2's provider is a fixture choice that exercises the memo's write rule, not a production path. It is kept, with only S8 applied.
- **K-7, `observe_load` is unchanged.** Mechanic: `fetch_window` and `in_memory_hit` count `get_or_fetch` misses and hits, which are independent of the branch (`ohlcv_cache.py:219-234`). Surface: code; pinned by N-V (2).
- **K-8, the web hook (`app.py:557-601`) and the bundle worker (`ohlcv_cache.py:470-518`) are untouched.** Mechanic: neither is in the diff; the worker reads `_ladder_bars_fetcher` directly (:491). Surface: the T2 diff and T-D3.

## 5. Interpretations declared (open to challenge at any round)

- **I-1, "each test asserts the kwarg reached the stub".** Read as: every swept stub records `use_ladder`, and every swept stub is pinned by at least one test that asserts the recorded value.
  - For a file-local stub, that is its owning test or tests.
  - For the shared `_StubOhlcvCache` (15 users), it is T-stub once, because the defect is a per-class signature defect.
  - The alternative is to add the assertion to all 15 users: four more files and about 15 edits, for no extra discrimination.
- **I-2, class-level patches measured unreached (p21) stay unchanged.** The alternative is to widen them defensively with `use_ladder=True` and no assertion.
- **I-3, witness attribution (plan L-6).** If no post-D89 night precedes the D90 merge, the first post-merge night is a combined D89+D90 night. Sequencing is the orchestrator's.

## 6. Round table and rounds

| round | tier / model / effort (banner) | footer | verdict token | `^ERROR` | crit | major | minor | task-bearing | new / reopened | reverts | tokens used | context depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | fast / `gpt-5.6-luna` / `medium` (equal to `~/.codex/fast.config.toml`'s `model` and `model_reasoning_effort`) | present | the clean token, 2 anchored occurrences (the CLI's double emission); the findings token 0 | 0 | 0 | 0 | 1 | 0 | 1 new / 0 reopened | 0 | 102,838 | |

**Loop status: CONVERGED AT ROUND 1** (plan-stage rule 4: the first round with zero task-bearing findings ends the loop). The uncounted self-sweep is below. The plan is committed once, with this ledger.

**Spend (plan phase):** 102,838 tokens (round 1 only).

### Round 1

**Invocation.** `wsl.exe bash -lc 'bash <scratchpad>/codex/run_round.sh 1'`. The runner (LF, checked with `file`) runs, from the worktree as cwd, `cat prompt-r1.md ledger-cut-r1.md <plan> | codex exec -p fast -s read-only --skip-git-repo-check -`. The output and exit files were pre-created Windows-side.

**Inputs.** The prompt states the declared envelope, the accepted limitations with their reasons, the 14-item checklist, the do-not-read list, and the verdict tokens DESCRIBED rather than written. A grep of the prompt, the cut and the plan for either token gives 0 each. Then the LEDGER CUT (sections 0-5, cut before section 6) and the plan.

**Assertions.**

| assertion | result |
|---|---|
| exit code, MEASURED | 0 |
| transcript | 412,850 bytes, non-empty |
| `model:` banner | `gpt-5.6-luna` = the fast profile's declared model |
| `reasoning effort:` | `medium` = the fast profile's declared effort |
| `^ERROR` | 0 |
| `^tokens used` | 1 (102,838) |
| verdict | the clean token, anchored, 2 occurrences (the CLI's double emission); the findings token 0 |
| codex process | exited: the exit file was written. The `codex exec -m gpt-5.6-sol` processes still alive were another seat's run |

**Prior-round / scratch reads:** none.
- Grep of the transcript for the ledger path: 3 hits. One is the prompt's do-not-read line (transcript :18). One is the plan echoed on stdin (:313). One is Codex reading the PLAN file's line 3 (:4538). None is a read of the ledger.
- Grep for `.codex-` / `.copowers-`: the prompt echo (:19) and `CLAUDE.md` (:773) only.
- Content filter: none reported ("No provider safety layer refused or rewrote any part of the prompt or response").

**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d90-detach\plan\round1\`: `codex-review-r1.txt` (412,850 bytes), `prompt-r1.md`, `ledger-cut-r1.md`, `run_round.sh`, `codex-exit-r1.txt` and `copowers-findings.md`.

**Codex's final message (verbatim):**

> 1. **HOLDS** — AL-1/AL-2/AL-3 are encoded at plan lines 60–65; source behavior is governed by `swing/web/ohlcv_cache.py:175,235-237,253-270`.
>
> 2. **HOLDS** — Literal `False`, no clock/carry predicate: plan lines 66, 284–285; source call is `swing/pipeline/runner.py:3132`.
>
> 3. **HOLDS** — Conditional admissibility, W6 boundary, and read caveat appear at plan lines 32, 361–367, and 379–381.
>
> 4. **HOLDS** — The ordinary/carry pair definitions, exact provider-difference requirement, patched Schwab leg, fixture `schwab_end`, and store-miss assertions are specified at plan lines 115–195.
>
> 5. **HOLDS** — The specified fixture and expected mechanics are consistent with `marketdata_ladder.py:430-555`, `ohlcv_archive.py:773-853,971-1056,1194-1351`, and `runner.py:3132-3155`; the expected fetch/hit/read/file/download outcomes follow.
>
> 6. **HOLDS** — T-NS uses a fresh cache, explicitly asserts the miss, specifies RED with the flag removed, and seeds a current legacy archive that avoids download: plan lines 103–143; archive behavior is `ohlcv_archive.py:773-853`.
>
> 7. **HOLDS** — S1–S9/X1 cover the runtime census, including the instance `_fetch_bars_window` replacement; recording assertions pin the keyword. Plan lines 199–212 and 333–352.
>
> 8. **HOLDS** — X1 is deleted by name and replaced with the required hazard comment and T-NS reference: plan lines 212–229. The cited closures exist at `marketdata.py:390-403` and `marketdata_ladder.py:202-214`.
>
> 9. **HOLDS** — The witness filter, ≥87,395 ms threshold, and W0 anti-vacuity condition are explicit at plan lines 373–375.
>
> 10. **HOLDS** — Both `resolve_ohlcv_window` callers and the five unchanged ladder callers are named at plan lines 26, 314–316.
>
> 11. **FAILS** — **minor, INSTRUMENT finding:** X1’s replacement comment says “no NEW contaminated row can be written” (plan lines 221–224), but the cited barrier only trims trailing non-finite bars; interior non-finite rows remain preservable by design (`swing/data/ohlcv_archive.py:286-307`). Narrow the wording to the seeded finite ext-hours Schwab case and trailing non-finite writes.
>
> 12. **HOLDS** — Each M1–M5 has discriminating tests listed at plan lines 323–329, and the branch/store mutations are covered by the stated assertions.
>
> 13. **HOLDS** — T1’s RED claims are consistent with the current signatures and behavior: source `ohlcv_cache.py:175,235-237,270`, and the stub sites listed at plan lines 203–212.
>
> 14. **HOLDS** — No production task enters an OUT item or contradicts the binding Branch-A ruling. The explicit `git` commands are implementation-time closure instructions, not review actions.
>
> No provider safety layer refused or rewrote any part of the prompt or response.
>
> NO_NEW_CRITICAL_MAJOR

**Adjudication.**

| id | item | reviewer severity | task-bearing? | disposition |
|---|---|---|---|---|
| R1-01 | 11 | minor, INSTRUMENT | no: a comment's wording; no task, test or envelope moves | ACCEPTED, fixed without a round. X1's comment claimed "no NEW contaminated row can be written", citing the 18-B trim, which is TRAILING-only (`ohlcv_archive.py:235-282` keeps interior bars). The comment now cites, for the non-finite class, `OhlcvBar`'s finite-OHLC construction check (`swing/integrations/schwab/models.py:561-582`; no Schwab bar can be non-finite) and, for the inflated class, L1 `needExtendedHoursData=False`. Ledger C-1 corrected to match. |

All 14 checklist items: 13 HOLD, 1 FAILS (R1-01, minor).

### Self-sweep (uncounted; no Codex; no effect on convergence)

- **SS-1.** Ledger C-1 carried the same overclaim as R1-01: the trailing trim presented as the closure for the non-finite class. Corrected in C-1, in the same class as R1-01.
- **SS-2.** A residual grep of the plan for `trailing non-finite`, `non-finite`, `injected clock`, `evaluate`, `:3080-3101` and `:44-50` found no stale claim. The two anchors had been corrected before round 1: the docstring at :3080-3102, and `_test_cfg` at :43-50.
- **SS-3.** Scratch prototypes p23 and p24 (section 2.2) reproduced every value the plan's N-V and T-NS claim, on the base code with the detach emulated. A wrong claimed value would have been task-bearing; none was found.
- **SS-4.** A Python scan of the plan found no non-ASCII character (`ord(c) > 127`: 0). The ledger keeps the rulings' own characters verbatim.
