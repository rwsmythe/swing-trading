# Tranche B-research session 2b — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Build the synthetic-replay harness for the earnings-proximity study under `research/harness/earnings_proximity/`, populate OHLCV + earnings caches, and verify end-to-end with a smoke test. No full parameter sweep (that is Session 2c). Run adversarial review on the code + tests before declaring done.
**Expected duration:** 3.5–4.5 hours. Split contingency pre-authorized (see §1).
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, Phase isolation rule, `yfinance` gotchas (especially `threads=False` ONLY on `yf.download()`; `Ticker.history()` does NOT accept `threads=`), MultiIndex column squeeze pattern, `os.replace` cross-device failure, Windows+gitbash path handling.
2. `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` — governing strategy. §IV.C (minimum provenance), §V.E (bootstrap-first), §V.F (research evidence standard), §VII.B (toleranced parity standard).
3. `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` — binding clarifications. Anti-patterns list — "strategy inflation," "registry maximalism," "infrastructure displacement" all applicable.
4. `research/method-records/earnings-proximity-exclusion.md` — the method this study validates. Note `blackout_trading_days` parameter and `absent-data → do NOT exclude, flag for review` rule.
5. `research/studies/earnings-proximity-exclusion.md` — study design. Variants X ∈ {0, 3, 5, 7, 10}; metrics (expectancy, gap-through rate, gap-through magnitude, signal volume); parity standard (fixture identity + toleranced vendor-backed equivalence).
6. `research/notes/earnings-calendar-sources.md` — Session 2a evaluation. Calendar source decision: **yfinance `Ticker.get_earnings_dates()`**.
7. `research/notes/historical-candidate-source-decision.md` — Session 2a decision memo. **Option B — synthetic replay**. Reuse sketch at ~77% of logic from `swing/`. Implications for Session 2b in §"Implications for Session 2b (harness build)" are binding — read that section carefully.
8. `docs/tranche-b-research-session-2a-brief.md` and prior briefs for precedent style.
9. Recent commit `957c3ee` on `main` for context on what Session 2a shipped.

**Skill posture.**

- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans`. This is execution of an already-decided design.
- Invoke `superpowers:test-driven-development` per CLAUDE.md for each logical module (replay driver, simulator, variant applicator, metrics).
- Invoke `superpowers:verification-before-completion` before declaring done.
- **After all code commits land,** invoke `copowers:adversarial-critic` (or equivalent per Session 2 / Session 3 precedent — run `git diff <base>..HEAD -- research/` through Codex MCP; iterate rounds until `NO_NEW_CRITICAL_MAJOR`). **Adversarial review is standing convention for code-shipping sessions.** This session ships code, so it applies.

---

## 1. Session scope — with pre-authorized split contingency

### Required deliverables

| # | Deliverable | Source |
|---|-------------|--------|
| D0 | Housekeeping — track uncommitted drift | §2.1 |
| D1 | Harness scaffold under `research/harness/earnings_proximity/` | §3.1 |
| D2 | OHLCV + earnings data-fetcher modules with disk caching | §3.2 |
| D3 | Replay driver (`evaluate_one` dispatcher across dates) | §3.3 |
| D4 | Trade-outcome simulator (entry trigger → stop/time-cap, R-multiple + gap-through) | §3.4 |
| D5 | Earnings-variant applicator + metrics aggregator | §3.5 |
| D6 | Provenance manifest schema + parity fixture test | §3.6 |
| D7 | End-to-end smoke test (1–2 tickers, 1–2 trading weeks) | §3.7 |
| D8 | Adversarial review on the combined code+test diff | §4 |

### Split contingency — pre-authorized

If the first-run data fetch (D2 cache warm-up) pushes total session wall-clock past 6 hours, **split the session after D2 into 2b-a (D0–D2) and 2b-b (D3–D8)**:

- **2b-a commits:** D0 (housekeeping) + D1 (scaffold) + D2 (data-fetcher modules + warm cache).
  - Warm cache is idempotent — tickers already fetched are served from disk; new requests extend the cache.
  - Final D2 commit message notes the split was invoked and records cache hit/miss counts.
- **2b-b session:** picks up with cache populated. Starts with D3 and runs through D8.
- **Commit semantics:** each commit in 2b-a must be clean and green (fast suite + ruff). No half-complete commits. A split is a deferred continuation, not a mid-task interruption.

Signals that trigger the split:
- yfinance rate-limit throttling extends individual-ticker fetch to >30 seconds sustained.
- Cache warm-up exceeds 60 minutes wall-clock.
- Implementer judgment that D3+ cannot complete before session fatigue compromises quality.

If the split is invoked, Session 2b return report goes under a `## Split — 2b-a return report` heading with a "Continuation required" marker; the orchestrator then dispatches 2b-b separately.

### Explicitly out of scope

- **Full parameter sweep.** D7 smoke test uses 1–2 tickers × 1–2 weeks. The full run across the 2-year window × full universe × 5 variants is Session 2c's job.
- **Evidence summary.** Session 2c.
- **Adversarial review on statistical conclusions.** The adversarial review in this session is on code quality only (per Session 2/3 precedent). Statistical-conclusion review is Session 2c.
- **Any mutation of `swing/*` or its database.** The harness imports from `swing.evaluation`, `swing.recommendations`, `swing.trades.equity` READ-ONLY. No writes to `swing.db`. No modifications to files under `swing/`.
- **Rebuilding the historical Finviz-filtered universe.** Fixed-universe concession accepted (Session 2a decision memo). Session 2c discloses it.
- **Migrating the `OhlcvCache` from `swing/web/` for reuse.** That cache is request-scoped and HTTP-wired; harness needs its own simpler disk cache.
- **Building any generic data-fetcher abstraction layer, vendor-agnostic adapter, or cache-manager framework.** A minimal per-module fetcher with disk caching is the target. "Infrastructure displacement" anti-pattern applicable.
- **Delistings/survivorship-bias pre-processing.** yfinance carries delisted tickers' historical bars; use as-is. Session 2c flags survivorship-bias concerns if evidence supports.
- **Any change to `research/method-records/earnings-proximity-exclusion.md` or `research/studies/earnings-proximity-exclusion.md`.** These are approved as-is.

---

## 2. Orchestrator rulings (from Session 2a's open questions)

These decisions are settled; do not re-litigate:

1. **OHLCV + earnings cache location:** `%USERPROFILE%/swing-data/research-cache/`. Outside Drive per CLAUDE.md invariant. Suggested subdirectory structure: `ohlcv/<ticker>.parquet` and `earnings/<ticker>.json`. On Windows/gitbash, resolve with `pathlib.Path.home() / "swing-data" / "research-cache"`.
2. **Script location:** `research/harness/earnings_proximity/` as a Python subpackage (`__init__.py` present). Inside this subpackage, break modules by role (fetchers, replay driver, simulator, variant applicator, metrics) rather than dumping into one file.
3. **Universe:** use repo's current RS universe CSV as the fixed replay universe. Record `universe_version_hash` in the provenance manifest.
4. **Window:** target 2 years (~504 trading days). Use `exchange_calendars` NYSE calendar to enumerate trading days (per existing `swing.evaluation.dates` helpers).
5. **Batching:** `yf.download()` multi-ticker mode with `threads=False` for OHLCV. Per-ticker `Ticker.get_earnings_dates(limit=30)` for earnings (no multi-ticker API exists). Cache aggressively — one fetch per (ticker, cache-age-24h window).
6. **Fixed-universe concession disclosure:** Session 2c discloses in evidence summary as a "Data-quality footnote." No method-record amendment.
7. **Sample-size (Session 2a calendar evaluation):** 5 primary-verified + 2 pattern-matched = 7 effective. Accepted. Session 2c discloses.

---

## 3. Task specifications

### D0 — Housekeeping

The working tree currently has untracked / uncommitted drift from the orchestrator session:

- `docs/Bugs.txt` — modified (Bug 7 added by orchestrator; uncommitted).
- `docs/tranche-b-research-session-2b-brief.md` — untracked (this brief).

Stage both in D0 alongside any other untracked files relevant to recent sessions. Do NOT modify `docs/Bugs.txt`'s content — it was edited by the orchestrator and should be tracked as-is.

```bash
git status
git add docs/Bugs.txt docs/tranche-b-research-session-2b-brief.md
# add any other untracked-but-session-relevant files
git commit -m "docs: track session-2b dispatch brief and bug 7 addition

- Track docs/tranche-b-research-session-2b-brief.md (dispatches this session).
- Track orchestrator-added Bug 7 in docs/Bugs.txt (dashboard Today's-Decisions
  vs chart-scope A+ disagreement; queued for pipeline-linkage bundle session).
"
```

Ship D0 first, before any harness code.

### D1 — Harness scaffold

Create:

```
research/harness/
├── __init__.py                 # empty or minimal
└── earnings_proximity/
    ├── __init__.py             # empty or minimal
    ├── README.md               # one-page how-to-run + module map
    └── (modules below — fill in as you go)
```

`README.md` format (brief, minimum viable):

```markdown
# Earnings-proximity replay harness

Synthetic-replay study harness for `research/studies/earnings-proximity-exclusion.md`.

## Run

```bash
python -m research.harness.earnings_proximity.run --window <years> --variants 0,3,5,7,10
```

(Full command and output format documented once the driver module is implemented.)

## Modules

- `fetchers.py` — OHLCV + earnings fetch with disk caching.
- `replay.py` — replay driver: iterates trading days, evaluates A+ per day.
- `simulator.py` — trade-outcome simulator: entry trigger → stop/time-cap.
- `variants.py` — earnings-proximity variant applicator.
- `metrics.py` — aggregator: expectancy, gap-through rate, signal count per variant.
- `provenance.py` — run manifest emission (git SHA, versions, hashes).
- `run.py` — CLI entrypoint + orchestration.

## Cache

OHLCV and earnings caches live OUTSIDE the repo at `%USERPROFILE%/swing-data/research-cache/` per CLAUDE.md Drive-sync invariant.
```

### D2 — Data-fetcher modules with disk caching

`fetchers.py` provides two functions minimum:

- `load_ohlcv(tickers: list[str], start: date, end: date, cache_dir: Path) -> dict[str, pd.DataFrame]`
  - Check cache first (per-ticker `.parquet` file keyed by ticker, content covers the union of prior requests).
  - For cache miss: `yf.download(tickers=missing, start=start, end=end, threads=False, group_by="ticker")`.
  - **MultiIndex column gotcha** (CLAUDE.md): `yf.download()` returns a MultiIndex (`Price × Ticker`). Squeeze per-ticker slices defensively: `close = df["Close"]; if hasattr(close, "ndim") and close.ndim == 2: close = close.iloc[:, 0]`.
  - Write back to cache on successful fetch.
  - Return dict: ticker → DataFrame (columns: Open/High/Low/Close/Volume; index: date).

- `load_earnings(tickers: list[str], cache_dir: Path, cache_max_age_hours: int = 24) -> dict[str, list[date]]`
  - Check cache per-ticker JSON. If fresh (mtime within max-age), return cached dates.
  - For cache miss or stale: `yf.Ticker(t).get_earnings_dates(limit=30)`. **Do NOT pass `threads=` to `Ticker` methods** (CLAUDE.md gotcha — TypeError on yfinance ≥1.2).
  - Extract dates (not datetimes) in **America/New_York timezone**, not UTC. Session 2a calendar eval notes this explicitly.
  - Serialize to JSON (`{"ticker": "...", "fetched_ts": "...", "earnings_dates": ["YYYY-MM-DD", ...]}`).
  - Return dict: ticker → list[date], sorted ascending.

**Acceptance:**
- Unit tests for cache hit, cache miss, cache stale.
- Unit tests for MultiIndex squeeze on single-ticker and multi-ticker return.
- Unit tests for absent-data: `get_earnings_dates()` returns empty → cached empty list → `load_earnings` returns `[]` (NOT None).
- Integration test (fast-suite eligible — `@pytest.mark.not_network` or equivalent; mock yfinance). Verify cache read/write round-trips.
- **No changes to `swing/web/price_cache.py` or `swing/web/ohlcv_cache.py`.** Those are operational caches; this is a separate replay cache.

### D3 — Replay driver (`replay.py`)

Shape:

```python
def replay(
    *,
    tickers: list[str],          # fixed RS universe
    trading_days: list[date],    # NYSE trading days in the window
    ohlcv: dict[str, pd.DataFrame],
    cfg: Config,                 # harness-constructed, NOT from swing.config.toml
) -> Iterator[AplusSignal]:
    """Iterate trading days. For each day:
       - Build BatchContext (universe-wide 12-week returns, regime indicators, etc.).
       - For each ticker: build CandidateContext from its OHLCV slice ending on this day.
       - Call swing.evaluation.evaluator.evaluate_one; filter bucket == 'aplus'.
       - For each A+ result: compute entry target, initial stop (via swing.recommendations.build helpers);
         yield an AplusSignal(ticker, date, entry_target, initial_stop, next_earnings_date).
    """
```

`AplusSignal` is a frozen dataclass under the harness subpackage. NOT under `swing/*`.

**Reuse pattern (per §2.1 of the 2a decision memo):**

- Import from `swing.evaluation.evaluator`, `swing.evaluation.context`, `swing.evaluation.scoring`, `swing.evaluation.rs`, `swing.evaluation.criteria.*`, `swing.evaluation.dates` — all read-only, functional calls.
- Import from `swing.recommendations.sizing` and `swing.recommendations.build` — thin adapter if needed for the replay's synthetic equity (e.g., fixed notional per signal rather than fetching live equity).
- Do NOT import from `swing.trades.entry`, `.exit`, `.stop_adjust` — those are DB-writing services. The trade-outcome logic is in D4 (simulator), which reimplements the numeric path without persistence.

**Acceptance:**
- Unit test: replay a 5-day window with 3 tickers against fixture OHLCV; assert the A+ signal set matches expected (fixture-identity test).
- Test that imports from `swing/` are genuinely read-only (no mocking of `swing.*.insert_*` functions — they should never be called).

### D4 — Trade-outcome simulator (`simulator.py`)

Shape:

```python
def simulate_trade(
    signal: AplusSignal,
    ohlcv: pd.DataFrame,        # full history for this ticker
    time_cap_days: int = 10,    # per method record / study design if specified
) -> TradeOutcome:
    """Simulate forward from signal.date:
       - Scan forward bars until high >= entry_target (trigger) OR time_cap reached without trigger.
       - If triggered: walk forward until low <= initial_stop (stopped) OR open < initial_stop (gap-stop)
         OR time_cap from trigger reached.
       - Emit R-multiple: (exit_price - entry_target) / (entry_target - initial_stop).
       - Flag gap_through if exit was a gap (open < initial_stop at bar t, so fill was at open, not stop).
       - Flag gap_magnitude_r: (initial_stop - actual_fill) / (entry_target - initial_stop) if gap_through.
    """
```

`TradeOutcome` is a frozen dataclass.

**Important behavioral rules:**

- **Trigger fill assumption:** fill at entry_target exactly if high ≥ entry_target (ignore slippage for MVP — study compares variants, so slippage is common-mode). Document in docstring.
- **Stop fill assumption:** fill at initial_stop exactly if intraday-low ≤ initial_stop AND open > initial_stop (no gap). If open ≤ initial_stop, that's a gap-through; fill at open (worse than stop).
- **No pyramiding, no scaling out.** One entry → one exit. Full position.
- **Time cap:** time_cap_days from TRIGGER, not from SIGNAL. If never triggered in time_cap_days after signal, the signal is dropped (not counted as a trade).
- **No earnings-based exit during the trade.** The study is about ENTRY-TIME earnings proximity, not mid-trade earnings. Hold through.

**Acceptance:**
- Fixture unit tests for: clean trigger → clean stop; trigger → gap-stop; trigger → time-cap no-stop; never-triggered signal (should return None or flag dropped).
- Unit test for R-multiple math (a few hand-computed cases).
- Gap-through magnitude calculation test.

### D5 — Earnings-variant applicator + metrics aggregator

Two modules, tightly paired.

**`variants.py`** — `apply_variant(signals: list[AplusSignal], blackout_trading_days: int, trading_calendar) -> list[AplusSignal]`:
- For each signal, check whether next_earnings_date is within `blackout_trading_days` TRADING days (not calendar days) of signal.date.
- If next_earnings_date is None (absent-data case): do NOT exclude; flag for review (per method record rule).
- Return filtered list.

**`metrics.py`** — `aggregate(outcomes: list[TradeOutcome]) -> MetricsRow`:
- Expectancy (mean R across all trades).
- Gap-through rate (fraction of stopped trades that gapped).
- Gap-through magnitude mean + max (in R).
- Signal volume (count of trades).
- Dropped signal count (signals that never triggered).
- Absent-data flagged count.

Output type: one `MetricsRow` dataclass per variant. For the full study, aggregator emits a list of MetricsRow (one per variant) plus a comparison table.

**Acceptance:**
- Unit test for variant filter: signal with earnings 3 days out → excluded at X=5, not excluded at X=3 (on boundary — spec this precisely: X trading days means strictly less than OR less-equal; pick one and document).
- Unit test for absent-data flag handling.
- Unit test for metrics math (hand-computed expectancy and gap-through rate on a small fixture).

### D6 — Provenance manifest + parity fixture test

**`provenance.py`** — emits `run_manifest.json` alongside the metrics output:

```json
{
  "git_sha": "...",
  "git_dirty": false,
  "run_ts": "2026-04-24T...Z",
  "yfinance_version": "...",
  "universe_version_hash": "...",
  "window_start": "YYYY-MM-DD",
  "window_end": "YYYY-MM-DD",
  "trading_days": 504,
  "tickers": 500,
  "variants": [0, 3, 5, 7, 10],
  "cache_stats": {"ohlcv_hits": 0, "ohlcv_misses": 0, "earnings_hits": 0, "earnings_misses": 0},
  "absent_data_count": 0,
  "dropped_signal_count": 0,
  "study_design_commit": "..."     // SHA of research/studies/... at run time
}
```

Per V2.1 §IV.C minimum provenance. Implementer may add fields if clearly useful; do not remove any listed above.

**Parity fixture test** — satisfies the study design's fixture-identity parity requirement:

```python
def test_earnings_proximity_fixture_identity():
    """Per study parity standard: excluded vs eligible must produce bit-identical classification."""
    # Fixture: two signals, one excluded (earnings within X days), one eligible.
    # Assert:
    #   apply_variant([excluded], X, cal) == []
    #   apply_variant([eligible], X, cal) == [eligible]
    #   Classification is purely a function of (signal.date, next_earnings_date, X, calendar) —
    #   no floating-point, no external state.
    ...
```

This test enforces the deterministic half of the parity standard. The toleranced half (vendor-backed equivalence on live data) was addressed by Session 2a's 5/5 spot-check.

### D7 — End-to-end smoke test

Not a unit test — an integration run via the harness CLI against a tiny slice:

- 2 tickers (pick representative: one high-liquidity like `AAPL`, one mid-cap with earnings events — `SOFI` or similar used in 2a eval).
- 2 trading weeks (10 trading days).
- All 5 variants.
- Writes to a `--output-dir` under `research/harness/earnings_proximity/smoke-out/` (git-ignored; add to `.gitignore`).

**Acceptance:**
- Harness completes without error on the smoke slice.
- Produces the expected output files: `metrics.csv` (one row per variant) and `run_manifest.json`.
- Metrics values are plausible (e.g., signal counts are nonnegative integers, expectancy is a finite float, gap-through rate ∈ [0, 1]).
- The smoke-out directory is gitignored; no smoke-run artifacts land in the commit.

**Do NOT run the full study** — this is a shape check, not a real run.

### D8 — Adversarial review

After D0–D7 are committed, run adversarial review on the code+test diff:

```bash
# base = HEAD before D1 (the D0 housekeeping SHA)
git diff <D0-SHA>..HEAD -- research/ .gitignore
```

Invoke `copowers:adversarial-critic` or follow Session 2/3 precedent. Iterate until `NO_NEW_CRITICAL_MAJOR`. Fix findings in a new commit (no amending — CLAUDE.md rule).

**Watch items the reviewer is likely to probe:**

- `yfinance` API misuse — `Ticker.history()` with `threads=` kwarg, MultiIndex-column single-ticker mishandling, timezone-naive datetime comparisons.
- Cache staleness semantics (what happens when yfinance rate-limits mid-fetch? partial-write risk?).
- Trade-simulator boundary conditions — signal on last trading day of data, open-gap-through exactly at stop, time-cap rounding.
- Variant applicator's boundary (X=0 must equal baseline; X trading days vs. calendar days).
- Provenance manifest completeness (V2.1 §IV.C).
- Absent-earnings-data handling (method record rule: do NOT exclude + flag; test it).
- Reuse patterns: does the harness actually avoid all `swing.*` writes? Grep for any `insert_*` or `update_*` symbol imports.

Accepted-with-rationale findings stay accepted — re-scoping the study mid-session is out of bounds.

---

## 4. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits (`feat(research):`, `test(research):`, `docs:`). No Claude co-author footer. No `--no-verify`. No amending.
- **TDD:** red-green-refactor per logical module.
- **Tests:** fast suite green after every commit. Baseline: 568. New tests add to that count.
- **Ruff:** no new violations beyond baseline 81. Exception: `research/` is a new package; ruff may flag patterns that don't apply under `swing/` (e.g., broader exception catches in data-fetcher retry paths). If so, apply narrow `# noqa: <code>` comments with a reason, and flag them in the return report so the orchestrator can decide whether to lift/document the pattern globally.
- **Phase isolation:** `swing/*` is consumed READ-ONLY. No mutations. No new files under `swing/`. No DB writes to `swing.db`. `swing-data/research-cache/` is allowed (outside `swing/`).
- **yfinance gotchas (CLAUDE.md):** `threads=False` ONLY on `yf.download()`; `Ticker.history()` does NOT accept `threads=`; MultiIndex column squeeze pattern; broad-except-around-yfinance ≠ silent-return (log or let propagate).

---

## 5. Commit sequencing

Suggested granularity (implementer may adjust within reason):

1. **C0** — D0 housekeeping.
2. **C1** — D1 scaffold + D2 fetcher modules + fetcher unit tests.
3. **C2** — D3 replay driver + D4 simulator + their unit tests.
4. **C3** — D5 variant applicator + metrics aggregator + D6 provenance + parity fixture test.
5. **C4** — D7 smoke test (runs manifest + .gitignore entry; no study output committed).
6. **Adversarial review.**
7. **C5** (if needed) — review fixes.

If the split contingency is invoked: commits 1 and 2 land in 2b-a; 2b-b resumes with commit 3.

Run `python -m pytest -m "not slow" -q` and `ruff check swing/ research/` after each code commit.

---

## 6. Done criteria

- All D0–D8 shipped (unless split invoked, in which case 2b-a's D0–D2 shipped and a 2b-b continuation is clearly flagged).
- Fast suite green; no new ruff violations (or narrowly-scoped `# noqa` with reasons).
- Smoke test produces plausible output.
- Adversarial review: `NO_NEW_CRITICAL_MAJOR` verdict.
- Return report produced.

---

## 7. Return report format

```
## Tranche B-research session 2b return report

### Split status
<"Not invoked — full D0–D8 shipped." OR "Invoked — 2b-a shipped D0–D2; 2b-b continuation required for D3–D8. Rationale: <brief>.">

### Commits landed
- <SHA> docs: track session-2b dispatch brief and bug 7 addition
- <SHA> feat(research): harness scaffold + data-fetcher modules with disk caching (D1 + D2)
- <SHA> feat(research): replay driver + trade-outcome simulator (D3 + D4)
- <SHA> feat(research): earnings-variant applicator + metrics + provenance + parity fixture (D5 + D6)
- <SHA> test(research): end-to-end smoke test on 2-ticker 2-week slice (D7)
- <SHA> fix(research): address session-2b adversarial-review findings  [if C5 was needed]

### Tests
- Before: 568 passing, 0 failing (fast suite).
- After: <N> passing, 0 failing. New tests: <M>.
  - Fetchers: <N>
  - Replay driver: <N>
  - Simulator: <N>
  - Variant applicator + metrics: <N>
  - Parity fixture: 1
  - Review fixes: <N>

### Ruff
- No new violations, OR: <list of narrowly-scoped `# noqa` additions with reasons>.

### Adversarial review — summary
- Rounds: <N>
- Base SHA: <D0 SHA>
- Thread ID: <from Codex MCP>
- Findings: <N> critical / <N> major / <N> minor
- FIXED: <short summary per fix>
- ACCEPTED-with-rationale: <short summary per acceptance>
- Verdict: NO_NEW_CRITICAL_MAJOR at Round <N>

### Smoke-test evidence
- Universe size for smoke: <N> tickers × <N> trading days × 5 variants.
- Output files: <paths>.
- Plausibility check: <one or two sentences confirming metrics values look sane>.
- Cache stats: <hits/misses for ohlcv and earnings>.
- Total wall-clock for smoke: <M:SS>.

### Cache state after session
- `%USERPROFILE%/swing-data/research-cache/ohlcv/`: <N> parquet files, <MB> total.
- `%USERPROFILE%/swing-data/research-cache/earnings/`: <N> json files, <MB> total.

### Deviations from brief / spec
<Anything different, why. Empty if none.>

### Items flagged but not done (scope discipline)
<Adjacent observations, out of scope for 2b, deferred for 2c or later.>

### Open questions for orchestrator
<Anything ambiguous; judgment calls made. Empty if none.>
```

---

## 8. If you get stuck

- If yfinance rate-limits bite mid-fetch, the correct response is NOT to build retry infrastructure. It's to let it fail, wait, and resume — the cache is idempotent. If sustained, invoke the split contingency per §1.
- If a `swing.evaluation.*` function you want to reuse requires a live DB connection, either (a) construct an in-memory SQLite with the right schema for the harness (acceptable if <50 LOC), or (b) skip the reuse and reimplement the pure-functional subset in the harness (acceptable if <100 LOC). Do NOT connect to `swing.db` (would violate read-only invariant on writes, and would couple replay to operator state).
- If a test you write passes under both the pre-change and post-change code, it's vacuous — see `memory/feedback_regression_test_arithmetic.md`. Rewrite.
- If the trade-simulator produces a negative expectancy on the smoke slice, that may just mean the 2-ticker 2-week slice isn't representative. Smoke checks SHAPE, not CONCLUSIONS. Flag only if the output is structurally wrong (NaN expectancy, negative signal counts, etc.), not if the numbers are surprising.
- If the harness takes substantially longer than the 3.5–4.5h estimate even without rate-limit throttling, invoke the split contingency and return the partial session honestly. Better a clean 2b-a + 2b-b than a rushed single session with shaky tests.
