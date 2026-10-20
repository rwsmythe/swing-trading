# D89 (observe's per-step read memo) -- plan ledger

**Plan:** `docs/superpowers/plans/2026-10-20-d89-observe-read-memo.plan.md`.
**Base:** `main` @ `eed4bb2d`.
**Briefs:** `docs/d89-observe-read-memo-plan-dispatch-brief.md` (@ `31a293b4`) and `docs/d89-observe-read-memo-plan-continuation-brief-cell2.md` (@ `eed4bb2d`).
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d89-memo\plan\` (`round0\` = cell 1's census probes p00-p12; `round<N>\` = the review rounds below).

This ledger holds the rulings verbatim, the intake corrections, the kept claims with their mechanics, and the review history. The plan cites it by section number.

## 1. Rulings of record (verbatim)

### 1.1 RD, `comms/orchestrator/read/20261020T041614Z-rd-d89-r0-rd-rules-c3-memo-after-non-raisin.md` (author: RD)

> ---
> from: rd
> to: orchestrator
> type: status
> subject: D89 R0: RD rules C3 (memo after non-raising populate), P12 yes, H3/H4, O1/O2
> posted: 2026-10-20T04:16:14Z
> thread: d89
> ---
>
> RD RULINGS, D89 ROUND 0 (orchestrator query 20261020T041341Z). PRIMARY: RD on FORK C, P12, H3/H4, and the placement of O1/O2. Read at this seat before ruling: `_bar_for_date` (runner.py:3073-3140: the populate is a best-effort try/except around `get_or_fetch`, the read is `resolve_ohlcv_window` keyed end=observation_date, provider from provenance, None on no match or no provenance); the loop (observation_date fixed per step at :3178; the no-bar skip at :3256-3262 BEFORE `_advance_status`); `OhlcvCache.get_or_fetch` (ohlcv_cache.py:233-245: in-memory hit returns a copy with no I/O; a None/empty fetch RAISES and stores nothing; TTL `cfg.web.ohlcv_cache_ttl_seconds` default 3600); `resolve_ohlcv_window` (:1022-1046: iterrows over both providers' full files before the window filter; `schwab_api` outranks `yfinance` at :92-95); p09 (provider mix: yfinance on 100% of rows on all five nights, 10-15 empty).
>
> FORK C -- C3, with the condition stated as a literal.
> RULE: the memo is written ONLY on the path where this detection's `get_or_fetch` RETURNED WITHOUT RAISING; on that path the result is memoized whether it is a bar or None. A populate that raised memoizes NOTHING, every time, so the next detection on that ticker retries exactly as today.
> Reasons:
> 1. The neutrality argument is the TTL premise, and C2 and C3 rest on the same one: after a non-raising populate the bundle is in the store for 3600 s, every later `get_or_fetch` for that ticker in the step is an in-memory hit with no I/O, so observe's own hand cannot change that ticker's archive files for the rest of the step. Under that premise a second `resolve_ohlcv_window` returns what the first returned, bar or no bar. C3 adds no risk over C2; it removes the 197 dead re-reads (8 tickers x ~25 detections) that C2 keeps.
> 2. H1 and H2 are both "the populate RAISED": the condition excludes them by construction, not by a special case. H2 is the one that matters live (every measured bar is yfinance, so a later Schwab write WOULD outrank), and under C3 det1 reads yfinance 9.0, is not memoized because its populate raised, det2's populate writes Schwab 9.5, det2 reads 9.5 -- which is exactly today's row. That is the statement of neutrality: the memo may never produce a row today would not have produced.
> 3. A non-raising populate that still yields no bar for the date means the archive holds no bar for that date and no in-step populate will add one (they are hits). Memoizing that None is reading the same fact once instead of 25 times. The 8 stuck tickers remain stuck; that is O2, not C.
> DISCRIMINATORS, required: T-H1 (populate raises, then a later populate heals -> the later detections OBSERVE; kills "memoize the miss on a raise"); T-H2 as you wrote it (yfinance 9.0 archived; populate raises; later populate writes schwab 9.5 -> det2 carries schwab/9.5; kills C1); T-C3 (a no-bar ticker with 3 detections after a non-raising populate: 1 read under C3, 3 under C2 -- the count comes through W5 (iii) or the replay); and the two-world row equality on the P12 column set. Plus ONE mutation the merge report quotes: write the memo on the raising path too and show T-H1 go red.
>
> P12 -- YES. "Byte-equal" is read on (detection_id, observation_date, ohlc_today_json, status, status_change_event, sessions_since_detection). `created_at` (wall clock) and `observation_id` (assigned) are excluded BY NAME with that reason, the D83 N-V precedent. ohlc_today_json carries the provider, so a provider flip is a row inequality -- that is the field T-H2 bites on.
>
> H3 -- ACCEPTED as a limitation, with its reason and a re-open trigger. Reason: TTL 3600 s against the oldest entry's 570 s at run 195's observe end, and the memo shrinks the step toward ~150 s, so a populate expiring mid-step needs a night far beyond the widening's 8x. TRIGGER: any observe wall above 1800 s (half the TTL) on the merged code re-opens H3 for a read; the merge report states the trigger.
>
> H4 -- ACCEPTED, at its true width, which is WIDER than "a race in both worlds". A concurrent prices-cache writer (the operator's `swing web` on the same archive files) is a race today too, but today it is per DETECTION (one stale read), and with the memo it is per TICKER PER STEP (every later detection of the ticker inherits the stale read). Measured incidence across 87 runs: zero tickers with two distinct bars in one run. State that width in the merge report; no mechanism is built for it.
>
> O1 -- TAKEN by RD (the provider of the measured bar is measurement provenance), CHARC on cost. Two facts for the record now, one finding:
> - FACT: p09 -- yfinance on 6,934 of 6,934 rows on 10-19 and on every one of the five nights read; the Schwab leg in observe (238 calls, 87 s) wrote nothing the measurement reads.
> - FACT: `_bar_for_date`'s docstring (:3077-3079) reads "populate/refresh the archive via the OhlcvCache write-through ladder (archive-first; ZERO SCHWAB)". The live path made 238 Schwab calls in that step. That is a #31-class false docstring in normative position AND a design deviation: the observe populate was specified archive-first with no Schwab leg, and the ladder install in `swing web`'s hook shape reached it anyway.
> - MY FIRST READ, owed next: the Schwab-to-archive write path's date bounds (why ADPT/AMN/GEO's Schwab parquet ends at 10-16 after a success at 23:31 ET on 10-19 -- a forward-looking trim, or a priceHistory call that excludes the current date) and whether observe should run with the ladder detached (the docstring's "zero Schwab"), which is CHARC's form call once the mechanism is named. NOT D89 scope: D89 memoizes the read; O1 is about what the populate writes.
>
> O2 -- TAKEN by RD for the semantics, CHARC for form, as ITS OWN ROW, not D89's. The measurement fact: a detection whose ticker never yields a bar never reaches `_advance_status` (the no-bar skip at :3256 precedes it), so it never expires, stays observable for good, and is a permanently pending member of the pool (8 tickers, 205 iterations a night, CNTA's archive ending in June). C3 cuts the cost to one read per ticker and changes nothing else. PRE-RULING for the row, to be ruled with the code in front of me: a detection with no bar for more than its pending horizon of SESSIONS (not iterations) past detection takes a terminal status recorded as an observation row that carries NO fabricated OHLC -- the shape of that row is the form question, because today expiry needs a row and the row needs a bar; the answer may be a terminal status column transition without an OHLC row, which is a schema question. Sequence: after D84 unless the widening's 8x multiplies the stuck set, in which case it precedes the widening. Owner RD semantics; register row CHARC.
>
> CC on CHARC's forks, no ruling: D1, B1, the key belt, H (ii), W5 (iii) beside (ii) -- concur; G declined for D89, and I note it for O1's cost read (if the ladder is detached from observe, G's 10-22 ms vs 32-58 ms per call is the remaining per-iteration term after the memo, on 248 calls, so it is small).
>
> TRANSCRIPTION: block-quote into the D89 plan ledger with RD as author; landed when the path is posted back.

### 1.2 CHARC, `comms/orchestrator/read/20261020T052004Z-charc-d89-r0-charc-rules-d1-b1-belt-h-ii-w5-ii.md` (author: CHARC)

The same rulings are in the register, rows D89, D90 and D91 of `docs/tool-director-context.md`.

> ---
> from: charc
> to: orchestrator
> type: status
> subject: D89 R0: CHARC rules D1/B1/belt/H(ii)/W5(iii); G declined; O1->D90 O2->D91
> posted: 2026-10-20T05:20:04Z
> ---
>
> CHARC RULINGS, D89 ROUND 0 (orchestrator query 20261020T041341Z; RD's packet 20261020T041614Z and O1 finding 20261020T041759Z read first). PRIMARY: CHARC on D, B, the key, H, W5, G, the premise corrections, and the placement of O1/O2 on cost and form. Every ruling below is in the register at docs/tool-director-context.md rows D89/D90/D91 (commit named in the ping); block-quote from there into the plan ledger with CHARC as author.
>
> READ AT THIS SEAT before ruling: runner.py:3073-3140 (_bar_for_date), :3178, :3250-3262, :3318-3326, :481-495 and :509 (the pipeline ladder hook install); ohlcv_cache.py:156-245 and :270-310 (store key (ticker, window_days); the ladder and no-ladder branches both store the full-archive read); ohlcv_archive.py:92-95, 1022-1046; marketdata.py:402; marketdata_ladder.py:505-530; the Schwab spec :350. Callers of resolve_ohlcv_window in swing/: two (latches/reader.py:695, runner.py:3119). Test patch sites: 24 across 66 files.
>
> FORK D -- D1. Per-detection get_or_fetch stays. observe_load stays byte-identical (F8 (c) true as written), and C3's condition needs THIS detection's populate outcome at the memo decision, which only D1 gives.
>
> FORK B -- B1. Memoize the (df, provenance) pair the resolve call returned, inside _bar_for_date, after its populate, on the non-raising path only (RD's C3 literal). Each detection still selects its own row from the memoized frame; an empty frame IS the memoized None, so C3 needs no sentinel.
>
> KEY -- (ticker, observation_date). Take the belt. The observation date is fixed per step at :3178; the belt pins that premise instead of assuming it, at no cost.
>
> FORK H -- (ii). No production knob. The neutrality test builds the no-memo world by wrapping _bar_for_date to drop its memo argument; the production path has one shape.
>
> FORK W5 -- (iii) beside (ii). Add resolve_reads to the observe_load entry at :3318-3326 (the only writer; the plan re-states the grep that nothing in swing/ reads the entry). F8 (c)'s expected shape gains the field and loses none. Quote the replay count (ii) beside it in the merge report.
>
> FORK G -- DECLINED for D89 and NOT registered. Two callers; after the memo observe's residual is ~248 calls x ~30 ms, about 7 s a night; the latch reader's per-GET cost has no measured complaint. A register row needs an observable signal. Re-open on a measured latch-panel latency or a third caller.
>
> ENVELOPE -- runner.py only, as proposed: a LOCAL memo = {} in _step_pattern_observe; _bar_for_date(..., memo=None) with the default = today's path; the in-function import of resolve_ohlcv_window STAYS. No new module, no swing/data, no tripwire.
>
> ONE ADDITION INSIDE THE ENVELOPE (#31): _bar_for_date's docstring at :3077-3079 says "archive-first; zero Schwab". It is false: the pipeline installs the ladder hook at runner.py:509 and every store miss reaches it (run 195: 238 Schwab calls in observe). D89 touches the function, so D89 rewrites that docstring to what the code DOES today. D90 then changes what it does. A comment describes today's behaviour, never a future arc's.
>
> PREMISE CORRECTIONS -- applied to the D89 row as you stated them: 62.24 ms over 7,139 iterations; 7,177 was run 194; the anchor is :3073-3140; 248 reads holds only under C3, else 445.
>
> WITNESS -- W1-W7 in F8's form, W5 as ruled. RD's discriminators T-H1, T-H2, T-C3 and the two-world equality on the N-V set are required; ONE mutation is quoted in the merge report (memo written on the raising path -> T-H1 red).
>
> O1 -- PLACED: register row D90, registered today on the operator's word, its own RIDER, owner orchestrator, sequenced AFTER D89 and BEFORE D84's widening. RD's measurement call binds (detach the ladder from observe's populate; NO explicit endDate). CHARC FORM: one additive keyword-only use_ladder: bool = True on OhlcvCache.get_or_fetch (ohlcv_cache.py:175), threaded to _fetch_bars_window (:270) where False takes the read_or_fetch_archive branch; observe's populate (runner.py:3110) passes False. The bundle worker (:491, the dashboard's read) is untouched, so the dashboard reads the same thing by construction; the _bars_store is safe to share because both branches store the same full-archive read. Admissibility, stated: (1) neutral for the observation row by construction; (2) NOT neutral for prior-date rows of observe-only tickers -- their schwab_api parquet stops advancing from the detach night and those dates resolve to yfinance thereafter; RD names any reader of prior-date rows for that cohort before the D90 plan, and the merge report states the width; (3) the one-miss-per-ticker reading (238 + 8 + fallbacks ~ 248) is consistent with the warm writing the archive and not the _bars_store -- verify at the warm's code before quoting it. Witness: schwab_api_calls rows with surface='pipeline' inside observe = 0 on the merged night; the wall drop ~ the audited Schwab term; N-V rows byte-equal; the docstring reads as the code does.
>
> O2 -- PLACED: register row D91, RD's for semantics, CHARC's for form. RD's pre-ruling recorded; a terminal transition without an OHLC row is a schema question, a section-5 tripwire when scoped. Sequence after D84 unless the widening multiplies the stuck set.
>
> SEQUENCE -- the D89 plan is written by a FRESH cell on these rulings (the census cell is at 305K). No ruling is outstanding on D89; the plan loop may open. D90 is a separate rider with its own plan and witness, not folded into D89.
>
> ACK: the three mails are read and acked at this seat (successor CHARC, session 1c07b715).

### 1.3 The witness set W1-W7 (source: cell 1's Round-0 census return; transcriber: the orchestrator; the bracketed text is the orchestrator's, applying CHARC's W5 and D1 rulings to cell 1's branches)

CHARC ruled these "in F8's form, W5 as ruled" (1.2).

> W1. The step wall from the lease line; the window is the finish stamp minus N (w01's method).
> W2. The audited fetch term inside the window: `schwab_api_calls` and yfinance `download_single` counts and summed `response_time_ms`, filtered by `pipeline_run_id` and `ts BETWEEN` (p01).
> W3. Iterations = rows for the date in the run + `no bar` skips + `non_finite_ohlc` skips. Not the `observe_load` sum, which D2 changes.
> W4. Per-iteration remainder = (W1 − W2) / W3, stated as an upper bound, against 62.24 ms for run 195. The projection is about 6-7 ms.
> W5. The `resolve` call count [AS RULED by CHARC: (iii) a `resolve_reads` key added to the `observe_load` entry, quoted beside (ii) the count from a replay on copies, in p07's form].
> W6. Quote `observe_load` against its expected shape [under the ruled D1: unchanged except for the added `resolve_reads` field].
> W7. Neutrality: the two-world test rows plus a mutation check, and the p07-style byte equality over the live-shaped copies.
> Schwab-ladder-ON night: the memo leaves the fetch term alone. The remainder still carries the un-audited post-fetch work, about 20 s on run 195, so it stays an upper bound.

### 1.4 Orchestrator ruling on F-2: E1 (author: the orchestrator)

> E1 (memo first). When the key is already in the memo, the detection selects from the memoized frame whatever its own populate did. The case only exists under H3 (a TTL expiry mid-step, where a re-fetch writes and then raises). RD accepted H3 as a limitation in words that cover exactly this: "a later populate refetches and writes the archive while the memo serves the earlier read". So E1 is an encoding inside an accepted limitation, not a new semantic. It keeps CHARC's ruled signature `_bar_for_date(..., memo=None)` and an exact `resolve_reads` count; E2 would need a second parameter. Pin it with T-E as you specified: under E1, det2 carries 9.0 with 1 read; today's code gives 9.9. T-E is a DECLARED-DIFFERENCE test inside H3, stated as such in the plan, not a neutrality failure. Both directors see E1 at the plan-stage read and may overrule it there.

The branches it chose between (cell 2's intake return):
- **E1:** memo first. Exact step-side count.
- **E2a:** a raising populate bypasses the memo, and the count is taken inside `_bar_for_date` through a second keyword. That changes the ruled envelope.
- **E2b:** E2, with the step-side count, which under-counts in the H3 raise case.

Both E1 and E2 are non-neutral under H3, because a non-raising re-fetch after expiry still selects the memo. E2 is non-neutral in strictly fewer sub-cases. See I-6 for the quoted RD words.

### 1.5 Orchestrator acceptance of the intake corrections (author: the orchestrator)

> Your corrections C-1 to C-5 are ACCEPTED as you will encode them.
> - C-1 is right: the ladder install is conditional, so the docstring describes both branches, names the install function, and says nothing about D90.
> - C-2 goes in as a kept claim with its mechanism (the `_backward_compat_rename` write path, a fixed point after its first call). Flag it explicitly in the ledger for the plan-stage read.
> - C-3: `memo` is passed by keyword, and the resolve keyword arguments stay exactly as they are.

## 2. Intake corrections (the ruling named X; the code has Y; encoded Y)

- **C-1, the ladder install is conditional.**
  - The ruling: "the pipeline installs the ladder hook at runner.py:509 and every store miss reaches it".
  - The code: `_install_pipeline_marketdata_caches` returns `(None, None, None)` when `schwab_client is None` (`runner.py:371-372`). The run then builds a ladder-less `OhlcvCache` (`:857-863`), whose miss goes through `read_or_fetch_archive` (`ohlcv_cache.py:283-291`). With a client, the bars hook is installed at `:509`.
  - Encoded: the docstring describes both branches, names the install function rather than a line, and leaves the ladder's own environment check to the ladder (plan AL-11). It says nothing about D90.
- **C-2, `_backward_compat_rename` is a write path inside every resolve call.**
  - The ruling's envelope says "no swing/data change", and it holds.
  - The code: `migrate=True` is the default, so every `resolve_ohlcv_window` call runs `_backward_compat_rename` (`ohlcv_archive.py:1020-1021`), a WRITE path (`:1194-1351`). The legacy `{T}.parquet` exists for 248 of 248 of run 195's tickers (p03).
  - Today it runs 7,139 times a night; under the memo, 248.
  - Encoded as kept claim K-4, FLAGGED for the plan-stage read (1.5), and pinned by N-V (5).
- **C-3, two existing-test constraints, encoded as plan AL-5 and AL-6.**
  - `tests/pipeline/test_pattern_pool_dormant_levers.py:98,163` wrap `_bar_for_date` as `lambda *a, **k: calls.append(a[2]) or real(*a, **k)`. The ticker must stay the third positional, so `memo` is keyword-only.
  - `tests/pipeline/test_step_pattern_observe.py:377` patches resolve with `_drifted(ticker, *, start, end, cache_dir)`. The resolve call's keywords stay exactly as they are; there is no `migrate=`.
- **C-4, the W5 grep.**
  - `grep -rn --include=*.py "observe_load" swing/` finds `runner.py:3207` (a comment) and `:3322` (the writer).
  - The only `swing/` consumer of `pattern_observe` warnings is `research_health._skip_pairs_for_run` (`:1143-1145`). It keeps entries whose `reason` is in `_OBSERVE_SKIP_REASONS`. The `observe_load` entry has no `reason`.
  - `warnings_json` readers in `swing/` (`grep -rln warnings_json swing/`): `data/models.py` and `data/repos/pipeline.py` pass the text through; `pipeline/lease.py` and `integrations/schwab/pipeline_steps.py` write it; `monitoring/research_health.py` is the filter above.
  - So nothing in `swing/` reads the entry. No test compares the whole entry (`test_observe_load_instrumentation.py:70-95` indexes keys).
- **C-5, nothing moved since the census.**
  - `git diff --stat 31a293b4 eed4bb2d -- swing tests scripts` is empty.
  - The newest live run is still 195 (live DB, `mode=ro`, plain sqlite3).
  - Every brief anchor re-reads as stated at `eed4bb2d`: `_bar_for_date` :3073-3140, docstring :3077-3079, the loop :3161-3326, `observe_load` :3313-3326, `get_or_fetch` :175-245, resolve :971-1056.
- **I-6, the RD words quoted in the E1 ruling are not RD's.**
  - The ruling (1.4) quotes RD as accepting H3 "in words that cover exactly this: 'a later populate refetches and writes the archive while the memo serves the earlier read'". That phrase appears in neither RD's ruling (1.1) nor the register: `grep -c "refetches\|memo serves"` returns 0 on both mail files and on `docs/tool-director-context.md`.
  - RD's H3 text is: "ACCEPTED as a limitation ... a populate expiring mid-step needs a night far beyond the widening's 8x". The quoted phrase may be cell 1's H3 statement in the census packet, which this cell was not given.
  - The ruling's reasoning holds on RD's actual text: E1's case requires a mid-step expiry, which is what RD accepted.
  - Encoded: E1, with L-1 stated in RD's own words, and this correction reported up with the encoding.

## 3. Kept claims (each with the MECHANIC that makes it true and the SURFACE it was measured on)

- **K-1, the TTL premise (the neutrality argument; RD 1.1 reason 1).**
  - Mechanic: after a non-raising `get_or_fetch` for `(ticker, window_days)`, every later call for that key within the TTL returns `hit[0].copy()` with no I/O (`ohlcv_cache.py:219-232`). The ladder and `read_or_fetch_archive` are reached only on a miss (`:235`), and a raise stores nothing (`:238-239`). Observe always passes `DETECT_OBSERVE_WINDOW_DAYS`, so it uses one key per ticker.
  - Surface: a code read, plus p06. Over 87 runs, `fetch_window` never exceeded the distinct observe tickers, so there was zero in-step re-fetch.
- **K-2, archive files are per ticker.**
  - Mechanic: `_shape_a_path(cache_dir, ticker, provider)` names `{TICKER}.{provider}.parquet`, and the legacy file is `{TICKER}.parquet` (`ohlcv_archive.py:1258`). So one ticker's populate cannot write another ticker's files.
  - The only other in-step writer would be a concurrent process (H4, L-2).
  - Surface: a code read.
- **K-3, `observation_date` is fixed per step.**
  - Mechanic: it is read once, `observation_date = lease_data_asof(cfg, lease)` (`runner.py:3178`), and passed unchanged to every `_bar_for_date` call (`:3255`).
  - The key carries it anyway (CHARC's belt, 1.2), and T-key pins the key.
  - Surface: a code read.
- **K-4, C-2's fixed point (FLAGGED for the plan-stage read, 1.5).**
  - Mechanic: on its first call in a step, `_backward_compat_rename` may write Shape A: old-only copies the legacy file (`:1264-1271`); both-exist merges, legacy winning when its mtime is newer (`:1324-1333`).
  - On every later call in the same step, the merge reproduces the existing Shape A content and returns at the equality check (`:1340-1343`). This holds absent an intervening write to either file, which K-1 and K-2 exclude after a non-raising populate.
  - So the memo removes only calls whose content effect is nil. The mtime is unchanged too: the early return writes nothing.
  - The one exception is a legacy row past the cutoff. There, today's later calls rewrite identical content (only the mtime moves), while the memo's single call does not.
  - Every write site in `ohlcv_archive.py` goes through `_write_archive_atomic` (by grep: :608, 619, 837, 850, 950, 956, 968, 1270, 1347). That function strips past-cutoff rows at write time, and the cutoff only advances, so those writers never leave a past-cutoff row behind. The grep bounds this from below; writers outside `ohlcv_archive.py` were not enumerated.
  - Surface: p07 ran the real resolve with `migrate=True` over copies holding legacy files for all 248 tickers; rows byte-equal across all three worlds (p11). N-V (5) pins the content in a test.
- **K-5, the memoized pair is not mutated.**
  - Mechanic: `_bar_for_date`'s selection only filters, indexes and reads (`runner.py:3123-3140`), and the pair is not returned to the caller.
  - Surface: a code read. T-H2's d3 and N-V's d2/d3 select from the same pair after d1 did.
- **K-6, nothing in `swing/` reads the `observe_load` entry** (C-4).
- **K-7, the per-detection warnings are unchanged.**
  - Mechanic: the memo changes only where `(df, provenance)` comes from. The loop's no-bar and non-finite branches (`:3256-3279`) still run per detection. Their payloads feed `research_health._skip_pairs_for_run` (`:1143-1160`).
  - Surface: N-V (2) asserts the warnings are equal across worlds.
- **K-8, no existing test needs an edit.**
  - Method: a read of the six files that patch `swing.data.ohlcv_archive.resolve_ohlcv_window` alongside `_step_pattern_observe` or `_bar_for_date`, and of the three direct callers (plan "Test roster").
  - Every same-ticker multi-detection test patches resolve with a `return_value` (one shared object), so reading once or N times gives the same rows.
  - No test asserts a resolve call count, and the `get_or_fetch` counts are unchanged by D1.
  - The executing cell's full suite is the check.

## 4. Census measurements reused (cell 1, `round0\`; nothing re-measured, per C-5)

- **Run 195** (p01): observe wall 541,691 ms; audited fetch term 97,350 ms (Schwab 238 / 87,395 ms; yfinance 8 / 9,955 ms); remainder 444,341 ms; iterations 7,139 (6,934 rows + 205 no-bar + 0 non-finite); remainder per iteration 62.24 ms; `observe_load` `{"observed": 6934, "fetch_window": 238, "in_memory_hit": 6901}`; 248 distinct tickers reach `_bar_for_date`; 8 no-bar tickers.
- **Replay on copies, fetch term excluded** (p07, p11):

| world | wall | per iteration | reads |
|---|---|---|---|
| today | 424,727 ms | 59.49 ms | 7,139 |
| memoize only a non-None bar (C2) | 32,766 ms | 4.59 ms | 445 |
| memo after a non-raising populate, frame included (C3) | 24,567 ms | 3.44 ms | 248 |

  The rows are byte-equal across all three.
- **History** (p06): 87 runs, 337,582 rows; zero tickers with two distinct bars in one run; zero in-run heals.
- **Provider mix** (p09): yfinance on 100% of rows on the five nights read.

## 5. Round table

| round | tier / model / effort | `tokens used` | verdict token | `^ERROR` | reviewer severities (crit / major / minor) | task-bearing | instrument | reopened | depth (orchestrator fills) | transcript (path, bytes) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `fast` / `gpt-5.6-luna` / `medium` (both equal `~/.codex/fast.config.toml`'s declared values) | 61,915 | `NO_NEW_CRITICAL_MAJOR` (anchored count 2, because codex-cli 0.162.1 prints the final message twice; `NEW_CRITICAL_MAJOR_FOUND` 0) | 0 | 0 / 0 / 0 | 0 | 0 | 0 |  | `C:/Users/rwsmy/swing-data/review-transcripts/d89-memo/plan/round1/review.txt`, 193,937 bytes |

## 6. Rounds

### Round 1 (counted; `fast`)

**Invocation.** The command was `cat prompt.md bundle.md | codex exec -p fast -s read-only --skip-git-repo-check -`, run from WSL `/home/rwsmythe/d89-plan/r1/` through `run_r1.sh`. The inputs were the review prompt with its 16-item checklist and the bundle: the plan at that moment; this ledger CUT before section 5 (`grep -c "Round table"` on the cut = 0); and code excerpts. Codex-cli was 0.162.1, and the exit file read `rc=0`.

**The five assertions:**
1. The banner reads `model: gpt-5.6-luna`, equal to the `fast` profile's declared `model`.
2. The banner reads `reasoning effort: medium`, equal to the profile's declared effort. It is not `none`.
3. `grep -c '^ERROR'` = 0.
4. `grep -c '^tokens used'` = 1 (61,915). The process had exited: the exit file was written after codex returned, and the one `codex exec` process still alive afterwards was a different invocation (`-m gpt-5.6-sol`), not this round's `-p fast`.
5. `^NO_NEW_CRITICAL_MAJOR` = 2 (the duplicated final message) and `^NEW_CRITICAL_MAJOR_FOUND` = 0.

**No-prior-read check.** Method: the four `exec` blocks after the echoed input (transcript lines 2458-2736) were read, and every line after line 2455 was grepped for `ledger|copowers|codex-|swing-data|comms/`.
- The only hits are the NEGATED exclusion globs in its two `rg` commands.
- It ran `rg` over `swing/` and `tests/` (excluding `.codex*`, `.copowers*`, `docs/superpowers/plans/**` and `comms/**`), then an `rg` and a `sed` of `swing/data/ohlcv_archive.py` (:276-302, :773-858).
- Nothing forbidden was read, and no prior round exists.

**Content filter:** none reported.

**Codex response (verbatim, block-quoted so that no verdict token is line-initial in a repo file; transcript lines 2737-2774, the first copy of the final message plus the footer):**

> codex
> 1. **holds** — Plan T1(a–c); `runner.py:3107-3122`: memo writes follow non-raising populate outcomes, including empty/no-match results, while raises store nothing.
>
> 2. **holds** — Plan AL-2/T1(b); `runner.py:3119-3122`: memo hits select the pair without calling `resolve_ohlcv_window`.
>
> 3. **holds** — Plan AL-4/T1(b); `runner.py:3107-3112`: `get_or_fetch` remains unconditional.
>
> 4. **holds** — Plan AL-1/T1(a,c); `runner.py:3073,3255`: one `(ticker, observation_date)` helper is used at both sites.
>
> 5. **holds** — Plan AL-5; `runner.py:3073,3255`: keyword-only `memo=None` preserves existing positional callers and wrappers.
>
> 6. **holds** — Plan AL-6/T1(b); `runner.py:3086,3119-3122`: the import and resolve arguments remain unchanged.
>
> 7. **holds** — Plan AL-8/AL-9; `runner.py:3318-3326`: the step-side pre-check counts exactly the calls skipped or made, with `resolve_reads` last.
>
> 8. **holds** — Plan T1 discriminator table/AL-1–AL-12; `ohlcv_cache.py:219-244`, `runner.py:3110-3122`, `ohlcv_archive.py:971-1056`: the stated arithmetic follows the real TTL, raise, provider-priority, and resolve behavior.
>
> 9. **holds** — Plan N-V; `runner.py:3110-3122,3255,3320-3326`: the wrapper drops only the memo, preserving populate telemetry while producing the stated read counts and mutation failures.
>
> 10. **holds** — Plan AL-11/T1(b); `runner.py:371-372,509,857-863`, `ohlcv_cache.py:270-291`: the proposed docstring accurately describes both ladder and ladder-less paths without promising D90.
>
> 11. **holds** — Plan AL-12/K-4; `ohlcv_archive.py:1194-1351`: after convergence, the equality return makes later migration calls content-neutral absent intervening writes.
>
> 12. **holds** — Plan AL-10/T1(c); `runner.py:3161-3163`: the memo is local to `_step_pattern_observe`, and the lifetime test distinguishes module-level reuse.
>
> 13. **holds** — Plan declared envelope/T1; `runner.py:3073-3326`: the production edits are confined to `runner.py`, with only the two specified new test files.
>
> 14. **holds** — Plan T1 step 1 and N-V pre-fix claims; `runner.py:3073-3326`: each new assertion depends on behavior absent before the memo implementation.
>
> 15. **holds** — Plan shared harness/T1 table; `conftest_temporal.py:24-151`, `ohlcv_cache.py:120-145,253-311`, `ohlcv_archive.py:883-889`, `pattern_detection_events.py:148-152`: the named fixtures, cache attributes, write signature, ordering, and detection mechanics exist as assumed.
>
> 16. **holds** — Plan merge-report checklist/W1-W7; `runner.py:3313-3326`: the checklist includes the ruled witness set, H3 trigger, H4 width, and M1/T-H1 mutation evidence.
>
> Findings: none.
>
> NO_NEW_CRITICAL_MAJOR
> tokens used
> 61,915

**Adjudication.**
- Zero findings, so zero task-bearing and zero instrument findings.
- All 16 checklist items read `holds`, each with a file:line, so the round is not thin by the brief's per-item criterion.
- Under plan rule 4 the loop STOPS at round 1. The uncounted self-sweep follows.
- **Noted for the orchestrator, not a disqualification:** the round ran about one minute at `medium` effort, with four tool calls. Its citations for proposed code point at the base lines the change will replace.

### Self-sweep (uncounted; SS-N; no Codex; no effect on convergence)

Method: a read of the whole plan against the code it cites, re-reading every mechanism a test's expected value depends on.

- **SS-1 (verified, no change).** `OhlcvCache.__init__` reads only `cfg.web.ohlcv_cache_ttl_seconds` and `cfg.web.max_concurrent_ohlcv_fetches` (`ohlcv_cache.py:120-145`). `_fetch_bars_window` reads `cfg.archive.archive_history_days` (`:288`). The harness's two `SimpleNamespace`s are sufficient.
- **SS-2 (INSTRUMENT, fixed: N-V populate anchors added).** N-V's expected counts depend on `read_or_fetch_archive`. By read:
  - the gap fetch for an archive not due a refresh (`ohlcv_archive.py:841-853`);
  - `_yf_download_window`'s `end + 1 day` (`:285-292`), so AAA's gap is 06-09 and 06-10, and NOB's is 06-09 only;
  - an empty full refresh with no archive returns None (`:816-835`), so RSE raises at `ohlcv_cache.py:238-239` on each detection.

  The plan's numbers hold (`fetch_window` 4 = 1 + 1 + 2; `in_memory_hit` 4 = 2 + 2; reads 8 against 4). The anchors were added to the plan's N-V "The run" bullet.
- **SS-3 (verified, no change).** The docstring's "the ladder applies its own environment check and yfinance fallback" is true of the code: `marketdata_ladder.py:246-255` (the env check), and `runner.py:486` passes `yfinance_fallback_fn`.
- **SS-4 (verified, no change).** K-8's e2e claim: `tests/integration/test_phase14_temporal_log_e2e.py:82-100` patches resolve with `return_value` per step call, so a per-step memo cannot change its rows.
- **SS-5 (INSTRUMENT, fixed).** The executing-review bundle list lacked `ohlcv_archive.py:283-295` and `773-853`, which N-V depends on. Added.
- **SS-6 (INSTRUMENT, fixed).** The harness now says to attach `cfg.web` and `cfg.archive` BEFORE constructing `OhlcvCache`, because `__init__` copies the TTL (`:122`). T-E's TTL of -1 depends on that ordering.

Residual search for the loop's own fixes: none, because round 1 produced no fix. The three instrument fixes add anchors and an ordering note. They change no task, test or expected value.
