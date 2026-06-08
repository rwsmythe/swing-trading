# Schwab Malformed Regular-Session Bar Handling — Design Spec

**Date:** 2026-06-07
**Phase:** 15 (arc: OhlcvBar bad-bar fix)
**Status:** Brainstorm spec — LOCK candidate, pending Codex convergence + operator OQ triage
**Branch:** `bad-bar-fix-arc-brainstorm` (from main HEAD `216ae288`)
**Author:** brainstorming implementer (dispatched)
**Brief:** [`docs/bad-bar-fix-arc-brainstorming-dispatch-brief.md`](../../bad-bar-fix-arc-brainstorming-dispatch-brief.md)

---

## §0 Re-grounding (STEP-0, discipline #2) — file:line verified on `216ae288`

The data-integrity arc moved things; every cited site was re-grepped in this worktree:

| Surface | Location (verified) | Role |
| --- | --- | --- |
| `OhlcvBar.__post_init__` invariant | `swing/integrations/schwab/models.py:506-551` (`low > min(o,c)` raise @542-546; `high < max(o,c)` raise @547-551) | The STRICT per-bar invariant. **Do NOT relax.** |
| `SchwabBarConsistencyError` | `swing/integrations/schwab/client.py:395` (`class SchwabBarConsistencyError(SchwabApiError)`) | Typed error; **subclass of `SchwabApiError`**. |
| Mapper bar-construction loop | `swing/integrations/schwab/mappers.py:825-880` (`map_price_history_to_window`); `OhlcvBar(...)` @860-867; `except ValueError → raise SchwabBarConsistencyError(asof_date, str(exc))` @868-872 | **Per-window failure today**: first bad bar aborts the whole window. This is the single edit site for approach (a). |
| `_OHLC_ROUND_DP` | `swing/integrations/schwab/mappers.py:50` (`= 4`) | 4dp rounding of o/h/l/c before construction. |
| `SchwabPriceHistoryWindow` (frozen) | `swing/integrations/schwab/models.py:554-642`; sort-ascending invariant @586-600; `to_dataframe` @602-642 | The mapper's return type. Candidate carrier for dropped-bar metadata. |
| Audit harness `_call_endpoint` | `swing/integrations/schwab/marketdata.py:487-720`; mapper-exception arm @650-702; **`finish_hook` success-path** @704-708; final close @710+ | `SchwabBarConsistencyError` (a `SchwabApiError`, not status 204) → recorded `status='error'` @664-674 → re-raised. `finish_hook` is the idiomatic hook for a success-with-note disposition. |
| `get_price_history` (wires `finish_hook=None`) | `swing/integrations/schwab/marketdata.py:457-478` | price_history currently passes **`finish_hook=None`**; quotes use a finish_hook for partial-response messaging — precedent. |
| Ladder catch → yfinance | `swing/integrations/schwab/marketdata_ladder.py:434-474`; `except (SchwabAuthError, SchwabRateLimitError, SchwabApiError)` @449-457 → whole-window yfinance | Catches `SchwabApiError` (hence `SchwabBarConsistencyError`) → **whole-window** fallback + persist. |
| Per-date merge resolver | `swing/data/ohlcv_archive.py:401-475` (`resolve_ohlcv_window`); precedence `{schwab_api:0, yfinance:1}` @56-58, winner-select @460-469 | **No count/contiguity assertion.** Merges per `asof_date`; **schwab_api > yfinance**. |
| Audit `status` CHECK | `swing/data/migrations/0018_schwab_integration.sql:28-31` (`in_flight, success, error, auth_failed, rate_limited, concurrent_refresh`) | **No `partial` token.** Adding one = schema change → forbidden unless OQ-D forces it. |
| Run-level `warnings_json` | `swing/pipeline/runner.py:810-1022` (`run_warnings` list → `lease.release(warnings_json=...)`) | The #27 no-silent-skip surface (no 80-char cap). |
| Audit message truncation | `swing/integrations/schwab/marketdata.py:133` (`_redacted_excerpt(..., max_chars=80)`) | **80-char cap destroys forensic context** (see §2). |

**Locks confirmed intact and propagated:** typed `SchwabBarConsistencyError` + mapper float-normalization (data-integrity arc); fetch-vs-write reorder (fetch outside the fence); audit single-tx + ladder-fallback disciplines; #27 no-silent-skip; #28/#29 exemplar depth; F6 empty-result; ZERO `Co-Authored-By`; ASCII-only. **Schema v24 holds (NO schema change in the recommended approach — see §6 + OQ-D).**

---

## §1 Problem (grounded, not re-derived)

Schwab `price_history` daily windows occasionally contain a regular-session candle that violates the `OhlcvBar` invariant (`high < max(open,close)` or `low > min(open,close)`). The mapper raises `SchwabBarConsistencyError` on the **first** such candle (`mappers.py:868-872`), which the ladder catches (`marketdata_ladder.py:449`) and degrades the **entire** ticker window to yfinance. **One malformed bar discards every good Schwab bar for that ticker.** The end data is correct (yfinance is clean), but Schwab-as-primary is needlessly lost, and the yfinance-freshness / temporal-mutation concerns (#24/#26) apply to the fallback series.

The ext-hours hypothesis was **FALSIFIED** at the data-integrity arc live gate; these are bad **regular-session** bars.

---

## §2 CHARACTERIZATION (first deliverable — read-only, live DB `mode=ro`)

Queried `schwab_api_calls` on the operator's live DB (`%USERPROFILE%/swing-data/swing.db`, opened `file:...?mode=ro`). **51** rows carry the invariant `error_message`; **all** are `endpoint='marketdata.pricehistory'`, **all** `status='error'`, spanning **2026-05-19 → 2026-06-06** (pipeline runs **71–93**) — ≈2-3/run, matching the brief's "~2-4/run."

**Finding 1 — a SMALL set of SPECIFIC candles recur every run (the smoking gun).** Only **10 distinct** `(direction, value)` violations across the 51 rows:

| direction | violating value | occurrences |
| --- | --- | --- |
| low  | 4.65    | 23 |
| high | 32.24   | 8 |
| high | 37.79   | 6 |
| high | 17.1855 | 4 |
| high | 22.74   | 3 |
| high | 7.7699  | 2 |
| low  | 21.005  | 2 |
| high | 4.72    | 1 |
| low  | 14.6801 | 1 |
| high | 66.797  | 1 |

The same `low (4.65)` candle re-surfaces **23 times** across ~19 days. Because each nightly run re-fetches the same multi-year window, **the same handful of corrupt historical candles reappear every run.** A transient/random fault or a today's-partial-bar artifact would not recur identically for weeks. **Verdict: specific, stable, corrupt source candles — not transient.**

**Finding 2 — both violation directions occur** (`low` too high AND `high` too low). A systematic one-sided rounding/adjustment bias would skew one direction. Mixed directions on a tiny fixed set ⇒ isolated bad candles in Schwab's store, not a uniform transform error.

**Finding 3 — the 4dp-rounding hypothesis is RULED OUT.** `_OHLC_ROUND_DP = 4`; rounding can move a value at most 5e-5. That cannot flip a genuinely-valid candle except one already within 5e-5 of its bound (sub-tenth-of-a-cent), which the recurring multi-cent-class values (4.65, 32.24, 37.79…) are not consistent with. Our mapper's rounding is **not** the cause.

**Finding 4 — request-side avoidance (approach c) is NOT viable.** The violations are 10 specific candles, not a uniform artifact of `(periodType, frequencyType, frequency, period)`. The ext-hours param hypothesis already failed. There is no evidence any request param makes Schwab return different (clean) values for these specific historical dates. **Skeptical conclusion per the brief: do not pursue (c).**

**Finding 5 — the bad candles APPEAR to be deep-historical, low-priced bars (observed pattern, NOT a safety guarantee).** Values (lows 4.65 / 7.77 / 14.68 / 21.005; highs 17.19 / 22.74 / 32.24 / 37.79 / 66.797) sit well below the current trading ranges of the open-trade tickers driving the OHLCV fetch (e.g. `VIR, CC, VSAT, SGML, PTEN, PL…`), suggesting split/adjusted candles from years back in the 5-year window. **CAUTION (Codex R1 MAJOR-1):** symbol/date/gap are NOT recoverable from the DB (Finding 6), so this is a price-level *inference*, not proof. The design therefore does **NOT** rely on "deep-historical ⇒ outside every consumer lookback" for safety — a future *recent* bad bar is not excluded. Safety is instead guaranteed structurally by the coverage-guarantee in §4 (no bare gap ever reaches a consumer), independent of where the bad bar sits.

**Finding 6 — the current audit is forensically blind (a fix-shaping defect).** `error_message` is truncated to **80 chars** (`_redacted_excerpt(max_chars=80)`); the cut lands **before** the comparison bound and the `date=` suffix, and the row has **no symbol column**. So today we cannot recover WHICH ticker, WHICH date, or the GAP magnitude from the audit. The exact malformation magnitude (cents/bps) is therefore **not measurable from the persisted DB** — a stated limitation of this characterization, and a direct motivation for the richer drop-audit in §5 (the mapper holds the full bar + the `ticker` arg; warnings_json has no 80-char cap).

### §2 verdict

**Irreducibly bad source data** at a small, stable set of (apparently deep-historical) candles, re-fetched every run. **Response-side handling is required; request-side avoidance (c) is dead.** The fix should keep the good Schwab bars and isolate the bad ones — i.e. approach (a) — but, per §4, must **guarantee the dropped date is covered by a clean alternate row** so no bare gap reaches a session-arithmetic consumer.

---

## §3 Candidate approaches (OQ-A — central operator decision)

- **(a) Drop-just-the-bad-bar, with a coverage guarantee — RECOMMENDED.** Per-bar isolation in the mapper: skip ONLY the invariant-violating candle(s), keep building the window from the good bars, surface the drop (audit + log), AND (at the ladder, which is archive-aware) **require every dropped date to be covered by a clean alternate archive row — else fall back to the existing whole-window yfinance path for this run.** Schwab stays primary for every good bar whenever it is safe; no bare gap ever reaches a consumer. Matches the "bad-exemplar isolation" gotcha. **Honest** (no fabricated data). Safety made structural in §4 (no longer dependent on the unprovable "deep-historical" inference).
- **(b) Repair-clamp.** Widen the bad candle to satisfy the invariant (`high = max(high,o,c)`, `low = min(low,o,c)`). Keeps the row but **fabricates a price extreme** — violates V1 honesty norms; needs a strong rationale + a visible marker. **Not recommended.**
- **(c) Request-side avoid.** §2 Finding 4 rules this out — no param avoids the specific corrupt candles. **Not viable.**
- **(d) Accept-the-fallback.** No code; formalize "Schwab bad bar → whole-window yfinance is acceptable" + document. **Rejected on cost/benefit:** cheap, but forfeits Schwab-as-primary for ~2-4 tickers/run indefinitely and leaves the #24/#26 yfinance-freshness exposure. The incremental cost of (a) is small and the win (Schwab primary restored, zero gap in practice) is real.

**Recommendation: (a) with the §4 coverage guarantee.** The per-date merge (§4.2) heals the common recurring case to **zero visible gap**; the coverage-or-fallback rule (§4.2) makes safety **structural** for every other case, so the design does not rest on the unprovable "deep-historical ⇒ safe" inference (Codex R1 MAJOR-1/2/4).

---

## §4 Consumer-gap-safety analysis (the binding requirement for approach a)

### §4.1 A bare interior gap is NOT universally safe — so the design forbids one (Codex R1 MAJOR-2, verified)

The original "a dropped bar is structurally identical to a holiday" claim is **FALSE for session-arithmetic consumers** and was retracted. A holiday is absent from the canonical session sequence everywhere consistently; a dropped bar is a **hole inside an otherwise-present sequence**, so any consumer that does positional/row-count math is shifted by one session if the gap falls inside its lookback. Verified offenders:

- `swing/pipeline/temporal_metadata.py:81` — `compute_return_pct`: `then = close.iloc[-(lookback_sessions+1)]` (ret_90d uses lookback 90). A dropped bar within the last 90 sessions shifts `then` to the wrong session.
- `swing/pipeline/temporal_metadata.py:59-64` — `compute_atr_pct`: `close.shift(1)` + `tr.tail(period)`; a dropped recent bar makes one TR span two real sessions and distorts ATR(14).
- `swing/pipeline/temporal_metadata.py:95` — `compute_52w_high_proximity_pct`: `close.iloc[-252:]` positional window.
- `swing/evaluation/criteria/trend_template.py:46,54` — row-count gates + rolling windows.

**Critical substrate distinction (Codex R2 MAJOR — there are THREE Schwab-reachable read paths, NOT one merged series):**

1. **`OhlcvCache` ladder-hook RAW return (the HOT path)** — `runner.py:_bars_hook:343-345` and `web/app.py:334` convert a Schwab success via `window.to_dataframe()` and hand that **raw** frame to `OhlcvCache.get_or_fetch` (`web/ohlcv_cache.py:270-282`), which slices/caches it **directly, bypassing the merge**. The session-arithmetic consumers above (pattern detect `runner.py:1729`, `build_per_pattern_metadata`/temporal_metadata, chart classification, `get_many_bundles` SMA/ADR, market-weather trend) read THIS frame. **A dropped bar here is a true bare gap regardless of archive coverage.** ← the guarantee MUST hold here.
2. **`resolve_ohlcv_window`** (`ohlcv_archive.py:401-475`) — the per-date provider **merge** (`schwab_api(0) > yfinance(1)`), no count/contiguity gate. Used by the detect date-anchor read (`runner.py:2621`).
3. **Legacy `read_or_fetch_archive`** (`ohlcv_archive.py:204-283`) — reads the legacy `{TICKER}.parquet` (yfinance), **does NOT call `resolve_ohlcv_window`**. Used by chart/daily-mgmt/web (`web/trade_charts.py:57`, `trades/daily_management.py:510`, etc.).

**Conclusion:** "rely on the downstream merge to heal the gap" is INSUFFICIENT — substrate 1 (the hot path) never sees the merge. The design must make the **series the ladder returns to the hook itself contiguous** (§4.2), not just the archive merge. Robust facts that still hold: `resolve_ohlcv_window` has no count/contiguity gate; `to_dataframe` does not `reindex`; **no production `OhlcvCoverageError`/`sliced=0` gate** (grep: only research/exemplar + test — #28/#29 are the exemplar harness); detector floor guards (`patterns/foundation.py:161` `<5`, `:225` `<2`) are minima a single drop cannot cross.

### §4.2 The coverage guarantee — the ladder returns a CONTIGUOUS in-memory series, or falls back (Codex R1 MAJOR-4 + R2)

The mapper is pure (no archive access), so the **coverage decision lives at the ladder** (`fetch_window_via_ladder`, archive-aware via `cache_dir`). The binding rule: **whenever the ladder keeps a Schwab window that dropped ≥1 bar, the series it RETURNS to the hook must already be contiguous across every dropped date** — never the raw gapped `window.to_dataframe()` (which substrate 1, the hot path, would consume verbatim). Algorithm after a successful Schwab window with `dropped_bars`:

1. Persist the Schwab good bars to `{TICKER}.schwab_api.parquet` (provenance preserved; `_persist_window_to_archive`). For each dropped `asof_date`, obtain a **clean alternate row** from the archive (a `{TICKER}.yfinance.parquet` row for that date; `write_window` preserves rows outside the incoming window, `ohlcv_archive.py:327`).
2. **Every dropped date has a clean alternate row** → build the returned in-memory series by **splicing those clean rows into the Schwab good bars** (equivalently: return `resolve_ohlcv_window(...)`'s merged frame, which yields `schwab_api` for good dates + the clean `yfinance` row per dropped date). Return that **contiguous** frame (provider tag `schwab_api`; the hook's `hasattr(...,"to_dataframe")` branch is satisfied by returning a DataFrame directly, `runner.py:343-346`). **Result: Schwab primary, zero gap, on ALL three substrates** — substrate 1 gets the spliced frame, substrates 2/3 read the persisted archives.
3. **Any dropped date lacks a clean alternate row** → take the existing **whole-window yfinance fallback** for this run (`marketdata_ladder.py:455-457`): return `(yfinance_window, "yfinance")`. Contiguous, safe, identical to today. Self-healing: that run populates the yfinance parquet, so the *next* run reaches branch 2 and restores Schwab-primary.

**Why this closes R2 MAJOR (raw-hook path) AND MAJOR-B (swallowed persist):** the returned in-memory series is made contiguous **independently of whether persistence succeeds** — substrate 1's safety does not depend on the archive write. If the Schwab persist is swallowed (`marketdata_ladder.py:171,191`), substrate-1 consumers still get the contiguous in-memory frame; only substrates 2/3 (archive readers) see a freshness lag, which is the *pre-existing* best-effort-persist behavior, not a gap this fix introduces. **No new targeted yfinance fetch** is required — branch 2 reads the yfinance row already in the archive; branch 3 reuses the existing whole-window fallback. (OQ-H: if the operator wants the uncovered-recent case to also keep Schwab, a *targeted* single-date yfinance fetch to splice is the alternative to branch 3's whole-window fallback — deferred; the whole-window fallback is the simpler, no-new-call default.)

### §4.3 Edge cases the design must handle

- **All bars in the window are bad** (degenerate): dropping yields an empty window → raise `SchwabApiError(204, ...)` (mirror the empty-candles path at `mappers.py:822-823`) so the ladder whole-window-falls-back. Never return an empty Schwab window as "success."
- **Systemic-corruption guard (anti-regression), unambiguous predicate (Codex R1 MAJOR-5):** let `dropped_count` / `total_count` be the bad / total candle counts in the window. **Whole-window-fallback (raise) iff `dropped_count > 10 OR dropped_count / total_count > 0.05`.** I.e. tolerate at most 10 dropped bars AND at most 5% — beyond either bound signals a Schwab regression / wrong params, not isolated candles; do not silently drop hundreds of bars; emit a loud WARNING. Today's rate (~1-2 bad / ~1250-bar window, <0.2%) sits far under both bounds. (Numbers confirmable at OQ-E; the *predicate shape* `> A OR > B` is fixed.)
- **Sort invariant** (`models.py:586-600`): dropping preserves ascending order — no interaction.
- **`empty=true` / empty candles**: unchanged — still raises 204 before the per-bar loop.

---

## §5 Audit + visibility design (#27 no-silent-skip; the central non-OhlcvBar surface)

Dropping a bar must **never be silent.** The deterministic, in-call-path surfaces are the **WARNING log** (full context) + the **schwab_api_calls audit row** (terse marker); the run-level `warnings_json` rollup is desirable but requires an explicit side channel (the metadata-loss boundary below defeats the naive wiring) — so it is specified, not assumed (Codex R1 MAJOR-3). No schema change.

1. **Mapper carries the drop metadata.** `map_price_history_to_window` skips the bad candle(s) (`continue` instead of `raise`), accumulating a structured record per drop with the **full, untruncated** context the mapper already holds: `ticker` (the arg), `asof_date`, `open/high/low/close`, the violated bound, and the gap magnitude (`|value - bound|`). Carry these out via a new metadata field on the returned `SchwabPriceHistoryWindow` (e.g. `dropped_bars: tuple[DroppedBar, ...]`, default empty). This adds **metadata to the window dataclass** — it does NOT touch / relax `OhlcvBar`. (Design note / OQ-F: window-field vs a mapper return-tuple; the field is preferred because it threads cleanly through the existing `_mapper`/`finish_hook`/ladder return shapes.)

2. **Deterministic surface A — WARNING log (full context, no 80-char cap).** Emitted in the call path (mapper-adjacent or ladder) with the complete `DroppedBar` detail. Logs are already this project's degradation-diagnosis surface (the ladder logs class+message on degrade, `marketdata_ladder.py:461-465`). This is the primary remedy for §2 Finding 6 and the deterministic #27 record, independent of layer 4's wiring problem. Route through the schwabdev log-redaction factory for surface uniformity (OHLC numerics are not secrets).

3. **Deterministic surface B — audit row `status='success'` + terse marker (NO schema change).** A dropped-bar call **succeeded** and returned usable data; `status='error'` would inflate the error rate, risk breaker logic, and read as an outage. Wire a price_history **`finish_hook`** (slot is `None` today at `marketdata.py:473`; quotes already use this pattern) that inspects `mapped.dropped_bars`: empty → `('success', None)`; non-empty → `('success', '<terse: dropped N bad bar(s)>')`. `status` stays inside the existing CHECK (`success`) — **no `partial` token, no migration.** Terse note fits the 80-char budget; full detail is in surface A. Canonical disposition signal remains `status`.
   - **MINOR (Codex R1) — health-surface consequence, ACCEPTED:** `swing/data/repos/schwab_api_calls.py:253` treats any `status='success'` as not-degraded, so a dropped-bar success will **not** trip the Schwab "degraded" banner. Intentional (a dropped historical bar is not a Schwab outage); documented + folded into OQ-B. If the operator wants visibility, the executing phase adds a *separate* "success-with-dropped-bars" counter rather than abusing `status`.

4. **Run-level `warnings_json` rollup — REQUIRES an explicit side channel (do NOT assume; Codex R1 MAJOR-3).** The naive "OHLCV step reads `window.dropped_bars` → `run_warnings`" does **not** work: `_install_pipeline_marketdata_caches` installs `_bars_hook` *before* `run_warnings` exists (`runner.py:802` vs `810`); `_bars_hook` converts the window to a DataFrame and returns only `(bars, provider_tag)` (`runner.py:343-345`); `OhlcvCache` keeps only `result[0]` (`web/ohlcv_cache.py:280`); the web hook loses it the same way (`app.py:334`). `dropped_bars` is discarded at that boundary. **Executing-phase requirement:** add a side channel surviving the hook→cache→runner boundary — e.g. a thread-safe drop-collector on the cache / `SchwabRuntimeState` drained into `run_warnings` after the OHLCV step, OR have the ladder write the rollup directly (it holds `conn`). **Also verify:** `_bars_hook` passes `pipeline_run_id=None` to the ladder (`runner.py:337`), so this path's audit row may lack run linkage (even though §2's rows carried run ids via another path) — the side-channel design must reconcile this. **Until wired, #27 compliance rests on surfaces A+B (deterministic); warnings_json is an enhancement, not claimed "free."**

**Audit-semantics decision (answers §4 of the brief):** dropped-bar window → audit `status='success'` (call succeeded) + terse `error_message` marker + WARNING log (full context, deterministic) + best-effort `warnings_json` rollup via the layer-4 side channel. Surfaced as **OQ-B** for operator ratification.

---

## §6 Locks / invariants (propagate)

- `OhlcvBar.__post_init__` stays **STRICT** — handled at the mapper, never by weakening the model.
- **NO schema change** (v24 holds). The audit `status` stays within the existing CHECK via the `success`+marker design (§5.3). If review insists a dropped bar must be a first-class **distinct** audit status (a new `partial`/`degraded` token), that is a CHECK widening = schema bump → **OQ-D, surfaced as CRITICAL** (the brief flags any forced schema change as critical). The recommended design **avoids** it.
- Data-integrity arc (typed `SchwabBarConsistencyError`, float-normalization) intact; `SchwabBarConsistencyError` retained for the all-bad / threshold-exceeded whole-window fallback (§4.3).
- Fetch-vs-write reorder (fetch outside the fence) intact — this arc touches the mapper/audit, not the lease ordering.
- F6 empty-result-is-transient intact (all-bad / empty → 204 → yfinance).
- #27 no-silent-skip satisfied deterministically by §5 surfaces A+B (WARNING log + audit-row marker); the warnings_json rollup (§5.4) is an enhancement pending the side channel. #28/#29 exemplar depth untouched (exemplar harness is a separate path).
- ZERO `Co-Authored-By`; ASCII-only user-facing strings (Windows cp1252 gotcha).

---

## §7 Out of scope

The deadlock fix (CLOSED); daily-management yfinance-under-fence #16 (banked); B-1..B-8; any `OhlcvBar` relaxation; any request-param redesign (§2 Finding 4); any NEW targeted single-date yfinance backfill call (the §4.2 uncovered case reuses the EXISTING whole-window fallback, not a new fetch); any schema change (unless OQ-D forces it).

---

## §8 Open questions (operator triage)

- **OQ-A (central):** Approach a/b/c/d. **Recommended: (a) drop-just-the-bad-bar WITH the §4.2 coverage guarantee** (drop the bad Schwab bar; require each dropped date to be covered by a clean archive row, else whole-window yfinance fallback this run). §2 + §4 support it; (c) ruled out, (b) dishonest, (d) forfeits Schwab-primary.
- **OQ-B:** Audit visibility of dropped bars. **Recommended:** `status='success'` + terse `error_message` marker + a deterministic full-context WARNING log + a best-effort `warnings_json` rollup (via the §5.4 side channel). Accept this audit semantics, including that dropped-bar successes will NOT trip the Schwab "degraded" banner (§5.3 MINOR)?
- **OQ-C:** Scope — full code arc, or accept-and-document (d)? **Recommended: full code arc (a)** — well-bounded (mapper per-bar skip + ladder coverage-guard + finish_hook + WARNING log + the warnings_json side channel + regression tests), high value. (If the operator prefers minimal footprint, (d) is the no-code fallback — but the team gains nothing and the exposure persists.)
- **OQ-D (CRITICAL if triggered):** Must a dropped-bar call be a **distinct** audit status (new token) rather than `success`+marker? If yes → schema CHECK widening + migration (v24→v25). **Recommended: NO** — keep `success`+marker, no schema change.
- **OQ-E:** Systemic-corruption drop threshold (the §4.3 anti-regression guard). The **predicate shape is fixed**: whole-window-fallback iff `dropped_count > A OR dropped_count/total_count > B`. **Recommended A=10, B=0.05.** Confirm the constants.
- **OQ-F (minor / implementer-decidable):** Carry drop metadata as a `dropped_bars` field on `SchwabPriceHistoryWindow` vs a mapper return-tuple. **Recommended:** the window field (threads cleanly through existing return shapes).
- **OQ-G (raised by Codex R1 MAJOR-3):** The `warnings_json` rollup needs a side channel across the `_bars_hook`→`OhlcvCache`→runner boundary (which discards `dropped_bars` today), and the `pipeline_run_id=None` path (`runner.py:337`) must be reconciled. Is a best-effort rollup (deferred to the executing phase, gated on this wiring) acceptable, with surfaces A+B carrying deterministic #27 compliance in the meantime?
- **OQ-H (raised by Codex R2):** For the uncovered-dropped-date case (no clean yfinance row in the archive), the default is whole-window yfinance fallback for that run (§4.2 branch 3; self-heals next run). The alternative — a *targeted single-date* yfinance fetch to splice just the dropped date and keep Schwab-primary immediately — costs one extra yfinance call and is currently OUT OF SCOPE (§7). Accept the whole-window-fallback default, or fund the targeted-fetch variant?

---

## §9 Writing-plans readiness

**READY for `copowers:writing-plans`, conditional on operator ratifying OQ-A=(a)+coverage-guarantee, OQ-B, OQ-C=full-arc, OQ-D=no-schema, OQ-G=best-effort-warnings.** The change is well-bounded:

1. `DroppedBar` record + `dropped_bars` field on `SchwabPriceHistoryWindow` (no `OhlcvBar` change).
2. Mapper per-bar isolation: in `map_price_history_to_window` replace the `raise SchwabBarConsistencyError` (mappers.py:868-872) with a per-bar skip that records a `DroppedBar`; raise 204 if **all** bars drop; raise (→ whole-window fallback) if the OQ-E predicate (`dropped>10 OR dropped/total>0.05`) trips. (TDD: 1-bad + N-good fixture → N bars + 1 `dropped_bars` entry; all-bad → 204; over-threshold → raises. Compute the threshold both sides of the boundary per `feedback_regression_test_arithmetic`.)
3. **Ladder coverage-guard returning a CONTIGUOUS in-memory series (the §4.2 safety core):** in `fetch_window_via_ladder`, after a Schwab window with `dropped_bars`: persist the Schwab good bars; obtain the clean alternate row per dropped date; all covered → **return a spliced/merged contiguous DataFrame** (NOT the raw `window.to_dataframe()`); any uncovered → existing whole-window yfinance fallback. (TDD: covered → returned frame has the dropped date present from yfinance; uncovered → whole-window fallback; **swallowed-Schwab-persist + covered → returned frame still contiguous**.)
4. price_history `finish_hook` (marketdata.py:473) → `('success', terse marker)` when `dropped_bars` non-empty. (TDD: audit row asserts `status='success'` + populated `error_message`; clean window asserts `error_message IS NULL`.)
5. WARNING log (full untruncated drop context) in the call path — the deterministic #27 surface. (TDD: caplog asserts ticker/date/o-h-l-c/bound/gap present.)
6. `warnings_json` side channel (OQ-G): collector across `_bars_hook`→`OhlcvCache`→runner (or ladder-direct write), drained into `run_warnings`; reconcile the `pipeline_run_id=None` path. (TDD: a run with a dropped-bar window asserts a `warnings_json` entry.)
7. Consumer-safety regression tests across **all three substrates (Codex R2 MAJOR-D)** — the primary one is the **hot path**: drive `OhlcvCache.get_or_fetch` through BOTH installed hooks (pipeline `_install_pipeline_marketdata_caches` + web `_install_web_marketdata_caches`) AND `get_many_bundles` with a Schwab dropped-bar window whose dropped date the yfinance parquet covers → assert the cached/returned frame has NO missing session and the dependent metric equals the all-clean baseline. Then assert the same for: `temporal_metadata.compute_return_pct`/`compute_atr_pct`/`compute_52w_high_proximity_pct`, `trend_template`, the 5 detectors via `patterns/foundation.py`, chart classification, `resolve_ohlcv_window` (substrate 2), and `read_or_fetch_archive` callers (substrate 3). Do NOT assert safety only through `resolve_ohlcv_window` — that misses the hot path.

**Estimated footprint:** ~3 files of production change (`mappers.py`, `models.py`, `marketdata_ladder.py`) + the `finish_hook` wiring (`marketdata.py`) + the warnings_json side channel (`runner.py`/`ohlcv_cache.py`/state) + regression tests across the three substrates. NO schema. NO `OhlcvBar` relaxation.

**Fallback if the operator chooses OQ-C=(d):** no executing phase — close the arc with a recorded decision ("Schwab bad bar → whole-window yfinance is acceptable") appended to the data-integrity arc notes. This spec then stands as the accept-and-document rationale.
