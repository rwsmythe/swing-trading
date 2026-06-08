# Executing Dispatch Brief — Slice-B Quote-Mapper Correction (OQ-3 A-lite; Gate 4 close)

**Arc:** Phase 15 / data-integrity arc Slice-B correction — fix `map_quotes_to_price_cache_entries` to Schwab's ACTUAL quote schema so the Schwab quote path works (it has been unconditionally dropping to yfinance since `b237412b`), then close Gate 4.
**Cycle stage:** **focused `copowers:executing-plans`** — the design is fully scoped below (orchestrator-investigated + operator-approved "A-lite", 2026-06-08). Implement TDD, then Codex on the diff to convergence. Not a brainstorm/writing-plans cycle.
**Branch-from:** main HEAD at worktree creation (re-verify with `git log --oneline -3`; main advances via operator research commits — branch from the live HEAD).
**Schema:** NONE — v24 holds. This is a `swing/integrations/schwab/` mapper+model fix + tests + the recorder/gate-test field corrections. Grounded in the captured source-of-truth schema [`reference/schwab-api/market-data-specification.md:102-104`](superpowers/../../reference/schwab-api/market-data-specification.md).
**Deliverable:** the code fix + corrected tests + the recorder/gate-test field updates + a CLAUDE.md gotcha, Codex-converged + `.copowers-findings.md`. Then STOP — do NOT merge. (The live cassette RE-recording is the operator's market-open step AFTER this merges; that closes the arc.)

---

## 1. Root cause (orchestrator-verified on disk + against the captured schema + a LIVE AAPL response 2026-06-08)

`map_quotes_to_price_cache_entries` ([mappers.py:700-765](../swing/integrations/schwab/mappers.py)) has TWO field-shape bugs that make it drop EVERY Schwab quote to yfinance:

1. **Wrong sub-block.** It sets `body = payload.get("quote")` (@702) then reads `body.get("regularMarketLastPrice")` (@715) + `regularMarketTradeTime` (@732). But Schwab's `regularMarket*` fields live in the **`regular` sub-block, a SIBLING of `quote`** in the per-symbol payload — NOT inside `quote`. So `regularMarketLastPrice` reads as `None` even when present.
2. **Phantom fields.** It reads `regularMarketBidPrice` (@718), `regularMarketAskPrice` (@721), `regularMarketMark` (@728) — **none of which exist in Schwab's API** (the `regular` block is exactly `{regularMarketLastPrice, regularMarketLastSize, regularMarketNetChange, regularMarketPercentChange, regularMarketTradeTime}` per the captured spec L102-104 + the live response). The gate `if last_price is None or bid is None or ask is None: continue` (@739) therefore ALWAYS drops (bid/ask are forever None).

**The captured live AAPL response shape (`fields=all`, 2026-06-08; use this to build fixtures):**
```json
{"AAPL": {
  "assetMainType":"EQUITY","symbol":"AAPL","quoteType":"NBBO","realtime":true,
  "extended":{"askPrice":0.0,"bidPrice":0.0,"lastPrice":308.72,"tradeTime":1780905565000, ...},
  "fundamental":{...}, "reference":{...},
  "quote":{"askPrice":313.97,"bidPrice":313.93,"lastPrice":313.955,"tradeTime":1780933219804,
           "closePrice":307.34,"mark":313.955,"securityStatus":"Normal", ...},
  "regular":{"regularMarketLastPrice":313.955,"regularMarketLastSize":50,
             "regularMarketNetChange":6.615,"regularMarketPercentChange":2.15233943,
             "regularMarketTradeTime":1780933219804}
}}
```
Note: under `fields="quote"` the response has the `quote` block but **NO `regular` block** — the `regular` block only ships under `fields="all"` (or a selection including `regular`). The recorder confirmed this live.

**Downstream consumption (decisive for A-lite):** only `last_price` is consumed — the ladder builds the price-cache entry via `price=float(quote.last_price)` ([marketdata_ladder.py:251](../swing/integrations/schwab/marketdata_ladder.py)). **Nothing reads `.bid`/`.ask`.** So requiring bid/ask kills the path for zero benefit.

**Why the unit tests didn't catch it:** `tests/integrations/schwab/test_quote_regular_session.py`'s `_resp(symbol, body)` builds `{symbol: {"symbol":symbol, "quote": body}}` — it puts the `regularMarket*` fields the test supplies INSIDE the `quote` block (the assumed-but-wrong shape), so the mapper's wrong-sub-block read matched the wrong-shape fixture → green against a fictional response. The live recorder is what exposed it (synthetic-fixture-vs-real-emitter drift).

---

## 2. The fix (A-lite — operator-approved 2026-06-08)

Require ONLY the regular-session fields that EXIST + are consumed; honor L1 (never surface ext-hours data); make bid/ask optional (unused; Schwab has no regular-session bid/ask).

### 2.1 `mappers.py` `map_quotes_to_price_cache_entries`
- **Source the regular fields from the `regular` sub-block:** read `regularMarketLastPrice` + `regularMarketTradeTime` from `payload.get("regular")` (a dict; sibling of `quote`), NOT from the `quote` `body`. Keep the snake_case fwd-compat fallbacks. Preserve the error-envelope + non-dict short-circuits.
- **Gate on `regularMarketLastPrice` only:** drop the bid/ask requirement. If `regularMarketLastPrice` is absent (e.g. a `fields="quote"`-only response with no `regular` block, or an ext-hours-only payload) → drop to yfinance (L1 preserved: no Schwab quote without regular-session provenance).
- **bid/ask/mark → `None`:** do NOT read the ext-hours-tainted bare `quote.bidPrice`/`askPrice`/`mark` (L1: "never surface the ext-hours book"). They're unused downstream; populate `None`. (Drop the `regularMarketBidPrice`/`AskPrice`/`Mark` phantom reads entirely.)
- `quote_time` from `regularMarketTradeTime` (in the `regular` block). Update the L1 comment block to describe the corrected sourcing.

### 2.2 `models.py` `SchwabQuoteResponse`
- `bid: float` → `bid: float | None = None`; `ask: float` → `ask: float | None = None`. Guard the `__post_init__` bid/ask numeric/finite validation with `if self.<f> is not None:` (mirror the existing `mark` guard @458). `last_price` validation unchanged. Update the docstring (bid/ask now optional; Schwab has no regular-session bid/ask).

### 2.3 `marketdata.py` `get_quotes_batch` + the recorder `--fields` default
- The `regular` block only ships under `fields="all"` (live-confirmed). Change `get_quotes_batch`'s `fields` default `"quote"` → `"all"` ([marketdata.py:289](../swing/integrations/schwab/marketdata.py)) so the regular block is returned. Verify no consumer breaks on the wider payload (it's additive — fundamental/reference/extended blocks; the mapper ignores them). Set the recorder `scripts/record_schwab_quote_cassette.py` `--fields` default to `"all"` too.

### 2.4 `test_quote_regular_session.py` — rebuild fixtures to the REAL shape (gotcha discipline)
- Fix `_resp` (and all B2 tests) to the real nested shape: the `regular` block as a **sibling** of `quote` (not inside it), derived from the §1 captured response. Add/adjust tests:
  - a quote WITH a `regular` block (regularMarketLastPrice + regularMarketTradeTime) maps successfully — `last_price` populated, `bid`/`ask` == `None`;
  - a `fields="quote"`-only payload (a `quote` block, NO `regular` block) → DROPPED to yfinance (no regular-session provenance);
  - an ext-hours-only / `extended`-only payload → DROPPED (L1);
  - the existing error-envelope + non-dict drops stay green.
- Per `feedback_regression_test_arithmetic`, the "maps successfully" test must FAIL on the pre-fix mapper (wrong sub-block → last_price None → drop) and PASS post-fix.

### 2.5 `test_quote_fields_live.py` (the Gate 4 slow test) + the recorder validation
- The cassette can only ever carry the fields that EXIST. Update BOTH to grep/validate `regularMarketLastPrice` + `regularMarketTradeTime` ONLY (drop the phantom `regularMarketBidPrice`/`AskPrice`). In the recorder: `REGULAR_SESSION_FIELDS` → those 2; update the OQ-3 message (now: "missing regularMarketLastPrice/TradeTime → re-run; under fields=quote the regular block is absent, use --fields all" — the bid/ask language is obsolete). Keep the single-interaction guard + leak-scan + fail-closed sanitization UNCHANGED.

### 2.6 CLAUDE.md gotcha (Schwab section)
Add: **Schwab `/quotes` `regularMarket*` fields live in the `regular` sub-block (sibling of `quote`), returned ONLY under `fields="all"`; the set is `regularMarketLastPrice/LastSize/NetChange/PercentChange/TradeTime` — there is NO `regularMarketBidPrice`/`AskPrice`/`Mark` (bid/ask/mark are bare fields in the `quote`/`extended` blocks). A B2-mapper that reads `regularMarketBid/AskPrice` from the `quote` body drops every quote to yfinance. Synthetic quote fixtures MUST mirror the real nested shape (regular block as a sibling); a fixture that nests `regularMarket*` inside `quote` masks both the wrong-sub-block read and the phantom-field bug (only the live recorder caught it).**

---

## 3. Locks / invariants

- **Schema NONE** (v24). Change locus: `swing/integrations/schwab/mappers.py` + `models.py` + `marketdata.py` + the two test files + the recorder + CLAUDE.md. This is a sanctioned Slice-B carve-out into `swing/integrations/` (the data-integrity arc's domain), NOT `swing/trades/` or `swing/data/`.
- **L1 preserved:** never surface ext-hours data — `last_price` comes from the regular-session `regularMarketLastPrice`; bid/ask are NOT sourced from the ext-hours-tainted bare `quote` block (left `None`). A quote lacking regular-session provenance still drops to yfinance.
- **Grounded in the captured spec** (`market-data-specification.md:102-104`) — cite it in the mapper comment + commit message.
- The recorder's fail-closed `vcr_config` sanitization + leak-scan + single-interaction guard are UNCHANGED (only the validated field-name SET changes).
- ASCII-only user-facing strings. NO `Co-Authored-By`; NO `--no-verify`; conventional commits; final `-m` paragraph plain prose.

## 4. Process (binding)

- **TDD:** the §2.4 "maps successfully" + "drops without regular block" tests are the discriminators (fail pre-fix / pass post-fix). Each task: failing test → see fail → minimal impl → see pass → `ruff check swing/ scripts/` → commit.
- **Full fast suite + ruff** at the end: `python -m pytest -m "not slow" -q` (baseline ≈7265 — report the ACTUAL count + net delta; isolate the 3 known xdist flakes with `-n0` if they appear) + `ruff check swing/ scripts/`. (The slow `test_quote_fields_live.py` stays skipped-by-absence — the cassette is the operator's post-merge step.)
- **Codex review to convergence** on the diff (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED). **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (liveness `codex --version` → `codex-cli 0.135.0`); pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`) + tell Codex not to run git. **Persist BOTH prompts AND responses** to gitignored `.copowers-findings.md`. (Adversarial focus: the regular-sub-block sourcing correctness; the L1 no-ext-hours-leak guarantee with bid/ask=None; the fixtures matching the real nested shape; no consumer breakage from `fields="all"`.)
- **Degraded-harness guard** (`feedback_degraded_harness_sequential_tool_calls`): single sequential calls + re-Read before each Edit if cancellations occur.

## 5. Return report (then STOP — do NOT merge)

Return: the commit SHA(s) + messages; the full-suite result (ACTUAL count + delta + any isolated flakes); `ruff` clean; the Codex convergence verdict (round count + final line); confirmation the mapper now sources from the `regular` sub-block + gates on `regularMarketLastPrice` only + bid/ask optional/None + fixtures match the real shape + `fields="all"` default + the gate-test/recorder field set corrected + the gotcha added; any deviation. Then STOP — merge is the orchestrator's action after QA, and the live cassette RE-recording (`python scripts/record_schwab_quote_cassette.py --environment production`) is the operator's post-merge market-open step that closes the arc.

## 6. What this is NOT

NOT a schema change. NOT a `swing/trades/`/`swing/data/` change. NOT sourcing bid/ask from the ext-hours-tainted bare `quote` block (left `None` — L1). NOT the live recording (operator's post-merge step). NOT (a) #16 / (b) Issue #3 (closed). The recorder's sanitization/guard machinery is untouched.
