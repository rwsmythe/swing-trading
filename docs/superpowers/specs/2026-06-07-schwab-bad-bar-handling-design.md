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

**Finding 5 — the bad candles are deep-historical, low-priced bars.** Values (lows 4.65 / 7.77 / 14.68 / 21.005; highs 17.19 / 22.74 / 32.24 / 37.79 / 66.797) sit well below the current trading ranges of the open-trade tickers driving the OHLCV fetch (e.g. `VIR, CC, VSAT, SGML, PTEN, PL…`). They are split/adjusted candles from years back in the 5-year window — far from the recent ~60–145-business-day slice every active consumer actually reads. **This is the linchpin of the consumer-gap-safety argument (§4).** (Symbol/date are not directly recoverable — see Finding 6 — so this rests on the price-level + window-shape evidence, not a per-row symbol join.)

**Finding 6 — the current audit is forensically blind (a fix-shaping defect).** `error_message` is truncated to **80 chars** (`_redacted_excerpt(max_chars=80)`); the cut lands **before** the comparison bound and the `date=` suffix, and the row has **no symbol column**. So today we cannot recover WHICH ticker, WHICH date, or the GAP magnitude from the audit. The exact malformation magnitude (cents/bps) is therefore **not measurable from the persisted DB** — a stated limitation of this characterization, and a direct motivation for the richer drop-audit in §5 (the mapper holds the full bar + the `ticker` arg; warnings_json has no 80-char cap).

### §2 verdict

**Irreducibly bad source data** at a small, stable set of deep-historical candles, re-fetched every run. **Response-side handling is required; request-side avoidance (c) is dead.** The fix should keep the good Schwab bars and isolate the bad ones — i.e. approach (a).

---

## §3 Candidate approaches (OQ-A — central operator decision)

- **(a) Drop-just-the-bad-bar — RECOMMENDED.** Per-bar isolation in the mapper: skip ONLY the invariant-violating candle(s), keep building the window from the good bars, and surface the drop (audit + warnings_json). Schwab stays primary for every good bar. Matches the established "bad-exemplar isolation" gotcha. **Honest** (no fabricated data). Safety proven in §4.
- **(b) Repair-clamp.** Widen the bad candle to satisfy the invariant (`high = max(high,o,c)`, `low = min(low,o,c)`). Keeps the row but **fabricates a price extreme** — violates V1 honesty norms; needs a strong rationale + a visible marker. **Not recommended.**
- **(c) Request-side avoid.** §2 Finding 4 rules this out — no param avoids the specific corrupt candles. **Not viable.**
- **(d) Accept-the-fallback.** No code; formalize "Schwab bad bar → whole-window yfinance is acceptable" + document. **Rejected on cost/benefit:** cheap, but forfeits Schwab-as-primary for ~2-4 tickers/run indefinitely and leaves the #24/#26 yfinance-freshness exposure. The incremental cost of (a) is small and the win (Schwab primary restored, zero gap in practice) is real.

**Recommendation: (a).** Rationale below; the §4 proof + the §2 deep-historical finding make the 1-bar gap provably safe, and the per-date merge (§4.2) makes it **invisible in practice** for these recurring tickers.

---

## §4 Consumer-gap-safety analysis (the binding proof for approach a)

### §4.1 The series is ALREADY non-contiguous

Trading-day OHLCV series omit weekends and exchange holidays. **Every** OHLCV consumer already tolerates calendar gaps; none can assume one-row-per-calendar-day. A dropped bad bar is **one additional missing trading day** — structurally identical to a holiday. The grounding:

- `resolve_ohlcv_window` (`ohlcv_archive.py:401-475`) builds a dict keyed by `asof_date`, sorts the keys, window-filters, and emits whatever rows exist (empty → empty DataFrame). **No count gate, no contiguity check, no reindex/asfreq.** A missing date is simply absent.
- `SchwabPriceHistoryWindow.to_dataframe` (`models.py:602-642`) builds a `DatetimeIndex` from whatever bars exist — gaps are normal; no `reindex`.
- **No `OhlcvCoverageError` / `sliced=0` gate exists in production** `swing/` (grep: only research/exemplar + test code). The #28/#29 coverage failures are the **exemplar-corpus harness**, not the production ladder→archive→consumer path. A dropped bar cannot trip a production coverage gate.
- Detector minimum-count guards (e.g. `swing/patterns/foundation.py:161` `len(bars) < 5`, `:225` `< 2`) are **floor** checks on a multi-year window; dropping one deep-historical bar cannot cross them.
- SMA / trend-template math is rolling over the **recent tail**; a dropped bar years back does not perturb a recent SMA (the window of the last N present bars is unchanged).
- `chart_scope.py` "insufficient-data" is a coarse "do we have a usable series at all" heuristic, not a per-bar contiguity assertion.

**Consumers the executing phase MUST add a regression test for** (each must be shown gap-tolerant, not assumed): chart render (`web/chart_jit.py` / `routes/charts.py`), SMA/trend (`evaluation/criteria/trend_template.py`), the 5 detectors (`patterns/{vcp,flat_base,cup_with_handle,high_tight_flag,double_bottom_w}.py` via `patterns/foundation.py`), observe/temporal (`pipeline/temporal_metadata.py`), and `resolve_ohlcv_window`. The proof above says they are safe; the tests make it **binding**.

### §4.2 In practice the gap is auto-healed (the strong property)

The merge is **per-`asof_date` across BOTH providers** with `schwab_api > yfinance`. These recurring-bad-bar tickers **currently** fall back whole-window to yfinance **every run**, so their `{TICKER}.yfinance.parquet` is **already fully populated** for the bad dates. Post-fix, Schwab will SUCCEED (good bars kept) and persist its window **without** date D; `resolve_ohlcv_window` then picks the **yfinance** row for D (clean) and the Schwab rows for every other date. Net for the operator: Schwab restored as primary across the window, **with the dropped date silently backfilled from the already-present yfinance row — zero visible gap.**

A **true** 1-bar gap only occurs for a ticker whose **first-ever** Schwab fetch hits a bad bar with no prior yfinance parquet for that date. §4.1 proves even that bare gap is safe. **Non-goal:** approach (a) does **not** trigger an extra targeted yfinance fetch to fill a dropped date (avoids quota burn + complexity); it relies on (i) the existing yfinance parquet via the merge, else (ii) the proven-safe bare gap.

### §4.3 Edge cases the design must handle

- **All bars in the window are bad** (degenerate): dropping yields an empty window. Treat as the empty/transient signal — raise `SchwabApiError(204, ...)` (mirrors the existing empty-candles path at `mappers.py:822-823`) so the ladder falls back whole-window to yfinance. Never return an empty Schwab window as "success."
- **Systemic corruption guard (anti-regression):** if the dropped fraction exceeds a threshold (proposed default **> 5% of candles OR > an absolute floor**, e.g. 10 — tunable; see OQ-E), this signals a Schwab regression / wrong request params, NOT isolated candles. Do **not** silently drop hundreds of bars: raise (whole-window yfinance fallback) + a loud WARNING. Today's rate (~1-2 bad / ~1250-bar window, <0.2%) sits comfortably under any such threshold.
- **Sort invariant** (`models.py:586-600`): dropping preserves ascending order — no interaction.
- **`empty=true` / empty candles**: unchanged — still raises 204 before the per-bar loop.

---

## §5 Audit + visibility design (#27 no-silent-skip; the central non-OhlcvBar surface)

Dropping a bar must **never be silent**. Three layers, no schema change:

1. **Mapper carries the drop metadata.** `map_price_history_to_window` skips the bad candle(s) (`continue` instead of `raise`), accumulating a structured record per drop with the **full, untruncated** context the mapper already holds: `ticker` (the arg), `asof_date`, `open/high/low/close`, the violated bound, and the gap magnitude (`|value - bound|`). Carry these out via a new metadata field on the returned `SchwabPriceHistoryWindow` (e.g. `dropped_bars: tuple[DroppedBar, ...]`, default empty). This adds **metadata to the window dataclass** — it does NOT touch / relax `OhlcvBar`. (Design note / OQ-F: window-field vs a mapper return-tuple; the field is preferred because it threads cleanly through the existing `_mapper`/`finish_hook`/ladder return shapes.)

2. **Audit row = `success` with a terse marker (NO schema change).** A dropped-bar call **succeeded** and returned usable data; recording it as `status='error'` would inflate the error rate, risk breaker logic, and read as an outage. Wire a price_history **`finish_hook`** (the slot is `None` today at `marketdata.py:473`; quotes already use this pattern) that inspects `mapped.dropped_bars`: empty → `('success', None)` (unchanged); non-empty → `('success', '<terse: dropped N bad bar(s)>')`. `status` stays inside the existing CHECK (`success`) — **no `partial` token, no migration.** The terse note fits the 80-char `error_message` budget; full detail lives in layer 3. (The canonical disposition signal remains `status`, not `error_message` presence.)

3. **Run-level `warnings_json` entry (the forensic surface, no 80-char cap).** The OHLCV pipeline step reads the returned window's `dropped_bars` (provider `schwab_api`) and appends a `run_warnings` entry (`runner.py` `run_warnings` list → `lease.release(warnings_json=...)`) carrying the **full untruncated** per-drop context (ticker, date, o/h/l/c, bound, gap). This directly remedies §2 Finding 6 and satisfies #27 (expected-vs-actual + reason). A WARNING log line mirrors it.

**Audit-semantics decision (answers §4 of the brief):** dropped-bar window → audit `status='success'` (call succeeded) + terse `error_message` marker + a full `warnings_json` entry. Surfaced as **OQ-B** for operator ratification.

---

## §6 Locks / invariants (propagate)

- `OhlcvBar.__post_init__` stays **STRICT** — handled at the mapper, never by weakening the model.
- **NO schema change** (v24 holds). The audit `status` stays within the existing CHECK via the `success`+marker design (§5.2). If review insists a dropped bar must be a first-class **distinct** audit status (a new `partial`/`degraded` token), that is a CHECK widening = schema bump → **OQ-D, surfaced as CRITICAL** (the brief flags any forced schema change as critical). The recommended design **avoids** it.
- Data-integrity arc (typed `SchwabBarConsistencyError`, float-normalization) intact; `SchwabBarConsistencyError` retained for the all-bad / threshold-exceeded whole-window fallback (§4.3).
- Fetch-vs-write reorder (fetch outside the fence) intact — this arc touches the mapper/audit, not the lease ordering.
- F6 empty-result-is-transient intact (all-bad / empty → 204 → yfinance).
- #27 no-silent-skip satisfied by §5.3. #28/#29 exemplar depth untouched (exemplar harness is a separate path).
- ZERO `Co-Authored-By`; ASCII-only user-facing strings (Windows cp1252 gotcha).

---

## §7 Out of scope

The deadlock fix (CLOSED); daily-management yfinance-under-fence #16 (banked); B-1..B-8; any `OhlcvBar` relaxation; any request-param redesign (§2 Finding 4); any new targeted yfinance backfill call (§4.2 non-goal); any schema change (unless OQ-D forces it).

---

## §8 Open questions (operator triage)

- **OQ-A (central):** Approach a/b/c/d. **Recommended: (a) drop-just-the-bad-bar.** §2 + §4 support it; (c) ruled out, (b) dishonest, (d) forfeits Schwab-primary.
- **OQ-B:** Audit visibility of dropped bars. **Recommended:** `status='success'` + terse `error_message` marker + full `warnings_json` entry (+ WARNING log). Accept this audit semantics?
- **OQ-C:** Scope — full code arc, or accept-and-document (d)? **Recommended: full code arc (a)** — small, well-bounded (one mapper edit + one finish_hook + one warnings_json emit + regression tests), high value. (If the operator prefers minimal footprint, (d) is the no-code fallback — but the team gains nothing and the exposure persists.)
- **OQ-D (CRITICAL if triggered):** Must a dropped-bar call be a **distinct** audit status (new token) rather than `success`+marker? If yes → schema CHECK widening + migration (v24→v25). **Recommended: NO** — keep `success`+marker, no schema change.
- **OQ-E:** Systemic-corruption drop threshold (the §4.3 anti-regression guard). **Recommended default:** drop up to `max(absolute_floor=10, 5% of candles)`; beyond → whole-window yfinance fallback + loud WARNING. Confirm the numbers.
- **OQ-F (minor / implementer-decidable):** Carry drop metadata as a `dropped_bars` field on `SchwabPriceHistoryWindow` vs a mapper return-tuple. **Recommended:** the window field (threads cleanly through existing return shapes).

---

## §9 Writing-plans readiness

**READY for `copowers:writing-plans`, conditional on operator ratifying OQ-A=(a), OQ-B, OQ-C=full-arc, OQ-D=no-schema.** The change is small and well-bounded:

1. Mapper per-bar isolation: in `map_price_history_to_window` replace the `raise SchwabBarConsistencyError` (mappers.py:868-872) with a per-bar skip that records a `DroppedBar`; raise 204 if all bars drop; raise (whole-window fallback) if the OQ-E threshold is exceeded. (TDD: a window fixture with 1 bad + N good candles → window has N bars + 1 `dropped_bars` entry; an all-bad fixture → 204; an over-threshold fixture → raises.)
2. `DroppedBar` record + `dropped_bars` field on `SchwabPriceHistoryWindow` (no `OhlcvBar` change).
3. price_history `finish_hook` (marketdata.py:473) → `success` + terse marker when `dropped_bars` non-empty. (TDD: audit row asserts `status='success'` + populated `error_message`; clean window asserts `error_message IS NULL`.)
4. OHLCV pipeline step → `run_warnings` entry with full untruncated drop context. (TDD: run with a dropped-bar window asserts a `warnings_json` entry carrying ticker/date/o-h-l-c/bound/gap.)
5. Consumer gap-tolerance regression tests (§4.1 list): chart, SMA/trend, the 5 detectors, observe/temporal, `resolve_ohlcv_window` — each fed a 1-interior-gap window and asserted to produce a sensible result (no crash, no count-gate trip).

**Estimated footprint:** ~2 files of production change (`mappers.py`, `marketdata.py`/`models.py`) + 1 pipeline-step emit (`runner.py`) + regression tests across the consumer surfaces. NO schema. NO `OhlcvBar` relaxation.

**Fallback if the operator chooses OQ-C=(d):** no executing phase — close the arc with a recorded decision ("Schwab bad bar → whole-window yfinance is acceptable") appended to the data-integrity arc notes. This spec then stands as the accept-and-document rationale.
