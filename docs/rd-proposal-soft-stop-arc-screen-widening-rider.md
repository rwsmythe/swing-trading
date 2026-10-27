# Proposal (registered) — the capital soft-stop ARC, with the Finviz screen widening as its RIDER

**From:** RD (Research Director), session `swing-rd-20261018-1519`.
**To:** the operator (owner of the decision), CHARC (composition + architecture), the orchestrator (sequencing).
**Status:** REGISTERED 2026-10-19 and **APPROVED by the operator the same day** ("maintenance rider and registered proposal is approved. Work on both may begin as conditions support."). Not yet planned. The stop-engineering posture is lifted for THIS arc and the maintenance rider by name; it stands everywhere else.
**Consult record:** RD <-> CHARC, `comms/charc/read/20261019T083701Z-*` (five items (a)-(e)), `...084359Z-*` (addendum (f)), CHARC's answers `comms/rd/read/20261019T084324Z-*`, `...084843Z-*`, `...085043Z-*`, `...085302Z-*`.

---

## 1. The premise, in the operator's framing (2026-10-19, to RD)

> Risk at the current low capitalization is a SOFT stop. We keep the calculations, but if I decide to take a $600 stock at a higher risk, that is something I can accept and should not be a programmatic 'no' decision.

Context he gave with it: the attention deficit of September/October was tool development slowed by a parallel project and weekly caps; he expects it to ease over the next few weeks. He concurs with widening the Finviz screen (RD recommendation, §4) and asked for CHARC's implementation view; a negative was acceptable. CHARC returned a staged yes with conditions.

## 2. Facts the proposal rests on (each read at the code or the live DB, `mode=ro`, 2026-10-19)

1. **The risk criterion is a HARD pre-gate skip.** `swing/evaluation/scoring.py:102-104`: `bucket_for` returns `skip` the moment any risk-layer result is not `pass`, BEFORE the trend template is consulted. `criteria/risk_feasibility.py`: pass iff one share's 20-bar high-low range fits inside `current_equity * max_risk_pct` = $7,500 floor x 0.5% = **$37.50**. The criterion already computes and persists `shares` and `risk_dollars` on pass AND fail.
2. **A skip row is invisible to measurement.** `skip` is not `watch`, so it never enters the broad-watch pool, the shadow engine, or the forward-observation log. Live: 309 risk-fail rows, all `skip`; 258 priced $50-100; zero rows to date where risk was the ONLY miss. A $300 name with a $40 20-bar range fails structurally. **Lifting the price cap without the soft stop routes the added names into `skip` and measures nothing** (CHARC confirmed at the code).
3. **One surface is already soft.** `swing/web/view_models/latches/reader.py:340` drops the risk layer at L4 as "a fact about the operator's capital, not about the setup's structure." The evaluator and the latch gate are two spellings of one rule, divergent today; the soft stop aligns them.
4. **The operator's idea is already pre-registered as H4.** `hypothesis_registry` id 4, "Capital-blocked: smaller-position test" — *"Candidates A+ except risk_feasibility, taken with smaller-than-standard position size, produce positive expectancy"* — registered 2026-05, 0/10, never live-fired because the hard filter keeps its members out of the latch. **This arc is H4's live enabling, not a new idea.**
5. **The cohort hole, read at `swing/recommendations/hypothesis.py:237-288`.** `_aplus_baseline_match` is `bucket == "aplus"`; `_capital_blocked_match` requires `bucket in ("watch","skip")` AND only-miss == risk. Under the soft stop a risk-fail name is bucketed `aplus`, so it matches H1 ONLY and fails H4's bucket check: **H1 absorbs the capital-blocked names and H4 empties silently at 0/10.** The cohort amendment is part of the arc, not a follow-up (CHARC concurred, error on the earlier "multi_match" reading owned on the record).
6. **The screen, measured live** (read-only `FinvizClient.fetch_screen` with substituted queries, nothing written to the inbox):

| screen variant (each on top of the lifted cap) | names 2026-10-19 | the tool's own check |
|---|---:|---|
| current (`sh_price_5to100`, 52w high within 10%, 13w perf > 30%, vol > 1M, SMA20 > SMA50, price > SMA50) | 35 | |
| price cap lifted (`sh_price_o5`) | 54 | sizing per name |
| + 52-week high within 25% (`ta_highlow52w_b0to25h`) | 109 | TT7 `high_52w_margin_pct = 25.0` |
| + 13-week perf > 10% (`ta_perf_13w10o`) | 121 | `prior_trend_min_pct = 25.0`, TT6 |
| + avg volume 1M -> 500K | 73 | **nothing** (no liquidity criterion exists) |
| SMA filters removed | 56 / 54 | TT4, TT5, MA stack |
| all of cap + 25% + perf 10% (vol at 500K in that run) | 299 | |

7. **Why the screen and not the universe.** The S&P 1500 study (`research/studies/sp1500-universe-expansion.md`, Tier 2 — Mixed) measured A+ at 0.0046% per ticker-day on an index universe against ~0.5% on the Finviz-filtered production pool: the screen concentrates A+ by two orders of magnitude. Widening the screen keeps that mechanism; switching universes discards it. The April binding-constraint study (`finviz-pool-binding-constraints.md`) had `risk_feasibility` at 2.3% of production-gated blockers on the then-pool, i.e. the soft stop is cheap today and binds only once the cap lifts.
8. **The banked T4 negative (read #4) is NOT touched.** It is a result about the watch COMPLEMENT under the mechanical ruleset on the pre-boundary population; this proposal changes who the gate SEES, not what the gate passes. The gate's criteria stay frozen except the one named here.

## 3. The ARC — capital risk as a flag, not a gate

**Routing:** V2.1 §VII.F source-of-truth correction protocol. `bucket_for` IS the A+ definition; A+ is the population of H1, H2 and H4; the H1 amendment is sha256-pinned in migration 0034. A change to what A+ means is a methodology-driven production change, whatever its diff size. **Stated plainly: this unfreezes the gate on exactly one criterion, `risk_feasibility`, and on nothing else.**

**Scope:**
- `bucket_for` no longer skips on the risk layer. The criterion keeps evaluating and persisting `shares` / `risk_dollars`; the result is carried as a displayed FLAG on every surface that renders an A+ (card, mandate, prepared-order form): shares at the budget, risk dollars, and the plain statement that the operator is above budget if he proceeds. No surface refuses.
- **Cohort amendment, same change:** H1 = `aplus` AND risk pass; H4 = `aplus` AND risk fail, post-boundary. The pre-boundary form of H4 (`watch`/`skip` with risk the only miss) is RETAINED so shadow history before the boundary still attributes. Both forms dated at the boundary in `hypothesis_status_history` (`change_reason` carries the boundary). A live fill on a risk-flagged A+ labels H4, never H1.
- **Composition read, not grep** (CHARC's list): the 21-B prepared-order form, the mandate shape check and the parity ledger all consume `compute_shares` (`position_pct_cap` 0.15 -> $1,125 notional; `shares_by_risk` from the same $37.50) — what a ZERO-share mandate renders and how the ledger scores an operator who takes one share anyway is the 21-B class (the panel ceiled, the mandate floored, the ledger scored him deviating); `swing/watchlist/service.py:28` carries risk in a criteria roster; `swing/metrics/capital.py`'s `risk_feasibility_blocked_rate` keeps computing but its meaning moves from blocked to flagged (prose in a metric tile); the bucket-enum mirrors (SQL CHECK + Python + any trigger) are unchanged in VALUE but every reader of the risk layer is listed by READ.
- The 19-D `degenerate_risk` floor in the shadow engine (rps < 0.15 x ADR) is a DIFFERENT rule about tight stops and is NOT touched.

**Tripwires:** none of CHARC's five formally (no schema, module, dependency, standing process, no `swing/data`/`swing/trades` carve-out). `swing/evaluation/` is not a carve-out but it is the measured instrument, which is stricter. **Plan-stage director review binds:** RD on the population and the H1/H4 amendment; CHARC on the 21-B composition and the enum mirrors.

**Acceptance (RD, measurement):** (i) a seeded risk-fail A+ is bucketed `aplus`, renders the flag with the computed shares and risk dollars, and latches; (ii) its fill labels H4 and the H1 matcher returns False for it (the discriminator that kills a bucket-only amendment); (iii) a risk-pass A+ is H1 and not H4; (iv) the pre-boundary H4 form still matches a pre-boundary `skip` row; (v) `compute_shares` on a zero-share mandate renders a stated zero, never a ceiled one, and the parity ledger scores the operator's one-share take as DEVIATING-BY-DECLARATION, not as a deviation from a framework order of zero — the exact shape is CHARC's to rule at plan stage.

## 4. The RIDER — Finviz screen widening (config value; reverts by the same value)

**Change (user-config `screen_query`, operator edit; the query is defensively dropped from the tracked TOML by `config.py:809-812` and MUST stay in user-config):**
- `sh_price_5to100` -> `sh_price_o5` (cap lifted; the $5 floor stays — it removes one name and the corpus argues against the sub-$5 population).
- `ta_highlow52w_b0to10h` -> `ta_highlow52w_b0to25h` (the screen was stricter than TT7).
- `ta_perf_13w30o` -> `ta_perf_13w10o` (the evaluator's prior-trend criterion does the real check).
- UNCHANGED: `sh_avgvol_o1000` (the one filter the gate does not re-check; it stays at 1M for the first epoch), `ta_sma20_sa50`, `ta_sma50_pa`.

**Staging (CHARC's sequence, RD accepted):** stage 1 = cap + near-high 25% only (35 -> ~109, about 3x); one nightly; two weeks of reads of the observe wall and the stoplights as the pending window fills; stage 2 = perf 10%. All three at once is the operator's option; the cost is a month of ramp with the levers as the brake, and the boundary note says so.

**Measurement decisions, ruled (RD):**
- **Lever 1, cap:** `detect_watch_pool_cap = 15` (today's watch-origin detect size is 10-13 per run). aplus is never capped. The pattern-outcome population is a separate instrument and is NOT widened; the T9 pattern reads stay comparable. The cap's #27 audit row on every drop is the receipt. Lever 2 (watch-origin horizon shed) NOT pulled: it changes the forward-walk length the maturity gate depends on.
- **Monitor re-baseline:** rates, not counts (see §5).

**The epoch boundary is DB-readable:** `finviz_api_calls.screen_query` + `signature_hash` are persisted per fetch (migration 0015). The committed artifact is a NOTE, never the query: a dated entry in this document's successor record naming the three filter changes, the first widened `finviz_api_calls.call_id` and its `signature_hash`, the first post-boundary `pipeline_runs.id` / `evaluation_run_id`, and NO `hypothesis_status_history` row (SUPERSEDED 2026-10-27: the D84 plan ruled S2 = (a), so the boundary's homes are the `DERIVATION_RULE_HISTORY` version string and the VII.F boundary note in `docs/research-director-watch-standard.md`; every registry row's n and criteria stay defined on the screen population, and the boundary is that dated note, not a status-history row).

**Expectation, stated so it is read and not inferred:** a few times the A+ fire rate, not eight — names 10-25% off their highs mostly die at tightness and proximity, where the watch bucket already dies. H1 stays bound by the live take rate. The regime (zero A+ fires since 09-02) is not fixed by any screen. The near-miss stratification study (expectancy by failed-criterion stratum within the watch pool) is a SEPARATE, pre-registered read and is not commissioned here.

## 5. The MAINTENANCE RIDER (approved separately, same word; instrument repair owed regardless of §3-§4; orchestrator sequences after D79)

1. `_INVALID_OHLC_BASELINE_COUNT = 23` (`research_health.py:780`) -> a RATE of unique signals: green <= 5.0%, yellow above, red > 10% (live: 71 / 1535 = 4.6%, flat since 09-24). **The stoplight has sat at its yellow floor since 2026-09-24 — a dead instrument for a month (D21 class, twice: the ceiling decayed, and the yellow decayed into wallpaper).**
2. `_COVERAGE_YELLOW_GAPS = 1` / `_COVERAGE_RED_GAPS = 10` (`:1022-1023`) -> holes per 1,000 forward observations, measured from the live artifact: green at today's rounded up, yellow 2x, red 5x. **RD reads the proposed constants against the live artifact before the rider merges.**
3. `SHADOW_EXPECTANCY_TIMEOUT_S` 300 -> 900 (`runner.py:1124`; CHARC ruled).
4. **Observe warm cohort:** the open detection set's distinct tickers join `warm_set` in `_prewarm_evaluate_archives` (`runner.py:1455-1475`) before `warm_archives_batch` (the Arc-6 batch, threads=True, operator-authorized 2026-06-10). Evidence: run 194 observe = 1,300 s (fetch_window=239, serial single-ticker); run 193, archives warm, 31 s for the same 6,972 rows. CHARC's six cell conditions bind (`comms/rd/read/20261019T085302Z-*`): one anchor for the observation date; warm depth covers observe's 400-day window (asserted against the live config); best-effort preserved; the open-detection count in the cohort telemetry and `observe_load.fetch_window` as the before/after witness in the merge report; neutrality (observation rows equal in count and values with and without the warm); the single-ticker path stays `threads=False`.

**Round-0 corrections to §5 (RD, 2026-10-20; the ruling text is in the maint-rider thread, `comms/orchestrator/read/20261020T*-rd-maint-rider-*`):** §5.2 is DEFERRED -- the live coverage rate is 0 per 1,000 (0 holes at the artifact's date and at today's, recomputed through the check's own code path), so "green at today's rounded up" has no measured anchor and the count rule (yellow at 1, red above 10; one-hole sensitive) STANDS until a population change yields a non-zero rate to rate against. §5.4's evidence line "run 193, archives warm, 31 s for the same 6,972 rows" is FALSE (run 193 wrote zero rows); the warm is a partial win (~270 s typical), not the whole cost. §5.1 proceeds as ruled, with the comparison by integer cross-multiplication and the display at 2 dp plus the band.

## 6. Sequence and what RD owes

1. Maintenance rider (§5) — orchestrator sequences after D79 merges; RD reads the rate constants before merge; CHARC registers the two D-rows.
2. The arc (§3) — brainstorm/plan under the correction protocol; plan-stage director review (RD + CHARC); executing when the operator says go.
3. Stage 1 of the rider (§4) — operator config edit the night after the arc merges; RD writes the boundary note (watch-standard v2.5) that day, and NO status-history row (superseded 2026-10-27, see the boundary paragraph above); CHARC's register row carries the operator's disposition.
4. Two weeks of reads; stage 2.
5. RD reads: the first risk-flagged A+ that fires is witnessed against the ruled shape (flagged, latched, H4-labelled on fill, H1 untouched); the first widened manifest's stoplights against the new rates; `degenerate_risk` and `invalid_ohlc` at the November read (#5) on both sides of the boundary.
