# Phase 14 Sub-bundle 1 -- Data-wiring -- Design Spec

**Status:** Brainstorm SHIPPED. Per Phase 14 commissioning brief Sec 9.1 LOCKs (operator-paired 2026-05-27 PM #4) + dispatch brief §1 LOCKs (this sub-bundle).

**Phase 14 commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs committed at `7a558e4`; THIS dispatch is Sub-bundle 1 (data-wiring) of 5 serial sub-bundles.

**Branch:** `phase14-sub-bundle-1-data-wiring-brainstorm` from main `3648e56`.

**Scope:** Close three discrete data-wiring defects -- V2.G3 (VSAT lost Sector + Industry on `/dashboard` open-positions table); V2.G4 (`/dashboard` Refresh weather chart button returns "no OHLCV bars available for SPY" even immediately post-pipeline); P14.N3 (`/daily-management` Capital % column appends "PROVISIONAL" with stale tooltip text + no operator-actionable clear-condition guidance).

**OUT-OF-SCOPE** (per dispatch brief §4): chart-surface uniformity (V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4) -- Sub-bundle 3; temporal log infrastructure -- Sub-bundle 2; review + journal UX (CR.1 + P14.N6) -- Sub-bundle 4; metrics overview (P14.N5) -- Sub-bundle 5; schema migrations beyond v21; any ruleset deployment work; any state-machine refactor on `daily_management_records` or `risk_policy`.

---

## §0 Glossary

| Term | Definition |
|---|---|
| **V2.G3** | Operator-witnessed gate finding 2026-05-23 -- VSAT row in `/dashboard` open-positions table is missing Sector + Industry values; DHA (DHC?) acknowledged-legacy (pre-feature; no backfill required) |
| **V2.G4** | Operator-witnessed gate finding 2026-05-23 -- `POST /dashboard/weather-chart/refresh` returns HTTP 409 "no OHLCV bars available for benchmark 'SPY'; run the pipeline first" even when triggered shortly after a successful pipeline run |
| **P14.N3** | Operator Turn H 2026-05-27 PM #2 -- `/daily-management` Capital % column appends "PROVISIONAL" with no UI affordance explaining the flag or what would clear it |
| **PROVISIONAL badge** | Template-rendered marker at `swing/web/templates/partials/daily_management_tile.html.j2:97`; tied to `tile.position_capital_utilization_pct`; emitted whenever the V1 fallback denominator (`capital_floor_constant_dollars`) is used per spec section 10.5 |
| **Open-trade-scoped OHLCV cache** | Per existing CLAUDE.md gotcha "OHLCV fetch scope = open-trade tickers ONLY"; `build_dashboard` computes `ohlcv_tickers = sorted({t.ticker for t in open_trades})`; SPY benchmark is NEVER in the cache unless SPY itself is an open position |
| **`equity_resolver.resolve_live_capital_denominator_dollars`** | `swing/metrics/equity_resolver.py:32-79` -- signature `(conn, *, asof_date: date, at_trade_time_policy: RiskPolicy) -> tuple[float, Literal["LIVE", "PROVISIONAL"]]`; returns `(value, "LIVE")` when an `account_equity_snapshots` row covers asof_date; `(value, "PROVISIONAL")` otherwise (falls back to `at_trade_time_policy.capital_floor_constant_dollars`). Paired with `swing/metrics/policy.py:39 read_live_policy(conn)` to resolve the active policy. The canonical denominator-stamping pattern is `swing/metrics/maturity.py:197-219` -- resolve denominator + badge dynamically; reuse `snap.position_capital_utilization_pct` ONLY when `snap.position_capital_denominator_dollars` matches the freshly-resolved value via `math.isclose(...)`; otherwise recompute the utilization from current position exposure. |
| **`refresh_chart_render`** | `swing/data/repos/chart_renders.py` -- DELETE-then-INSERT atomic cache invalidation + write helper; F6 transient-empty defense applied at construction barrier (`ChartRender.__post_init__` rejects empty bytes per CLAUDE.md gotcha) |
| **L2 LOCK** | Project invariant -- ZERO new Schwab API calls outside OQ-13 CLI carve-outs; preserved through 12 applied research arcs + Phase 13 + Sub-bundles ahead. Discriminating source-grep test included per §11 |
| **Sub-bundle 1** | This sub-bundle; serial first in Phase 14 per Sec 9.1 Q1 + Q2 LOCKs |

---

## §1 Architecture overview

### §1.1 Cohesion

The three items in scope cohere around **persistence + JOIN + cfg-resolution debugging at the dashboard + daily-management surfaces**. None is an analytical methodology change; none requires a new HTMX endpoint; none expands yfinance / Schwab fetch scope; none touches the pipeline-step early-return discipline beyond a single warnings_json hardening for V2.G4 root-cause clarity.

Item | Surface | Root cause (hypothesis at brainstorm; verified at writing-plans) | Fix posture
---|---|---|---
**V2.G3** | `swing/data/repos/trades.py` INSERT path + `swing/web/routes/trades.py` entry-form POST handler + `swing/web/templates/partials/open_positions_row.html.j2:37-38` (em-dash fallback ALREADY present) | Schema columns `trades.sector` + `trades.industry` ALREADY exist per migration `0012_sector_industry.sql:23-24` (NOT NULL DEFAULT ''); the `Trade` dataclass has `sector: str = ""` + `industry: str = ""`; the template renders `row.trade.sector or "—"`. Root cause is at TRADE-CREATION-WRITE-TIME: either (a) VSAT trade row was opened before migration 0012 and got the NOT NULL DEFAULT '' (same gotcha family as DHA/DHC legacy); OR (b) entry-form POST persisted empty strings because the candidates lookup at POST time returned no row for VSAT (ticker rotated out of finviz screen between form-render and POST); OR (c) a subsequent UPDATE path overwrote the values to empty. Investigation per §4.1 narrows the live hypothesis. | One-time backfill helper (CLI subcommand OR direct SQL maintenance) that updates `trades.sector` + `trades.industry` from the most-recent `candidates` row per ticker where currently empty; plus optional VM fallback per CLAUDE.md PriceCache `_last_close` discipline if backfill alone is insufficient
**V2.G4** | `swing/web/routes/dashboard.py:76` -- `ohlcv_cache.get_or_fetch([benchmark])` | **Call-signature mismatch** -- the method's signature is `def get_or_fetch(self, *, ticker: str, window_days: int = 180)` (keyword-only `ticker`); the handler passes a list positionally. The TypeError is silently swallowed by `except Exception: bars = None`. Subsequent `if bars is None or bars.empty:` produces the 409 error. | One-line call-site fix + replace the dead dict-style consumption code + add explicit error log on the silent-swallow path (gotcha #27 empty-pool early-return + audit emission discipline)
**P14.N3** | `swing/web/templates/partials/daily_management_tile.html.j2:97` -- PROVISIONAL badge + stale tooltip text | The badge IS wired to the V1 fallback condition (`capital_floor_constant_dollars` used); but (a) the tooltip's "V2 will resolve to live account equity (Phase 9 risk_policy versioning)" text is **stale** (Phase 9 + Phase 11 already shipped the live-equity infra via `equity_resolver` + `account_equity_snapshots`); (b) the tooltip is hover-only with no visible affordance for what would clear the flag (write an `account_equity_snapshots` row -- e.g., via `swing schwab fetch --snapshot` or future manual entry) | Template-rendering-surface fix -- rewrite tooltip text to describe the actual current clear-condition; surface a small inline "?" affordance with a slightly-larger explanatory blurb so the operator can diagnose without hovering

### §1.2 Schema impact

**Sub-bundle 1 stays Schema v21 LOCKED.** No `swing/data/migrations/*.sql` files are added. Verification per §12.

### §1.3 L2 LOCK preservation

Zero NEW Schwab API calls. The V2.G4 fix consumes the existing OhlcvCache substrate (which falls through to `read_or_fetch_archive` / archive + yfinance ladder; no Schwab calls added). The V2.G3 fix consumes the `candidates` table via a new repo helper (zero API surface). The P14.N3 fix is template-text + dataclass-driven (zero API surface). Discriminating source-grep test at §11.4.

### §1.4 HTMX failure surface

Sub-bundle 1 introduces NO new HTMX endpoints. The V2.G4 refresh handler ALREADY EXISTS at `POST /dashboard/weather-chart/refresh` with HTMX trinity discipline already encoded (HX-Request header on embedded form per dashboard.html.j2; 204 + HX-Redirect on success; target route registered). Spec confirms no new HTMX surfaces; HTMX trinity audit per §7.2.

---

## §2 Pre-locked operator decisions (verbatim per dispatch brief §1; BINDING)

### §2.1 Sub-bundle scope LOCK (Sec 9.1 Q1 + dispatch brief §1.1)

Sub-bundle 1 ships ONLY V2.G3 + V2.G4 + P14.N3. No widening. If V2.G4 root cause overlaps V2.G1, SURFACE as Open Question for orchestrator review (do NOT silently expand). Operator already pre-empted this via the dispatch brief: V2.G4 root cause is CONFIRMED at brainstorm to be a call-signature mismatch local to the refresh handler -- NOT a chart_jit cache-hydration architectural bug. The Open Question #2 below resolves at brainstorm to **no V2.G1 overlap** (see §5.4).

### §2.2 Codex chain count LOCK (Sec 9.1 Q7 + dispatch brief §1.2)

SINGLE Codex MCP chain at end of brainstorm per gotcha #36 explicit caveat: "production-feature dispatches without a substantive emitted artifact may continue to use single-chain placement at orchestrator discretion." Data-wiring is pure UX/wiring; no smoke artifact; no findings doc beyond the standard return report. Target convergence: 2-4 rounds.

### §2.3 Serial execution LOCK (Sec 9.1 Q2)

Sub-bundle 1 ships FIRST. Sub-bundle 2 (temporal log V1+) depends on Sub-bundle 1 merge.

### §2.4 Operator-witnessed gate LOCK (Sec 9.1 Q6)

Sub-bundle 1 ships with per-sub-bundle operator-witnessed gate (browser verification of all three fixes). Gate surfaces enumerated at §10.5.

### §2.5 Schema migration posture LOCK (dispatch brief §1.5)

V1 expectation: NO schema migration. Sub-bundle 1 stays Schema v21 LOCKED. Brainstorm verifies no item requires migration. If any item's investigation reveals schema migration is unavoidable, ESCALATE to orchestrator. Brainstorm verdict at §12: all three items are view-layer/template-text/call-site fixes; **no migration needed**.

### §2.6 Backwards-compat for legacy NULL Sector/Industry (dispatch brief §1.6)

V2.G3 fix preserves operator-acknowledged DHA (DHC?) legacy gap. Restore Sector/Industry for tickers that HAVE them in the upstream data source but lost them due to JOIN gap; do NOT attempt to backfill legacy NULL values. Discriminating test per §4.5.

---

## §3 Module touch list

| Path | Type | Item(s) | Purpose |
|---|---|---|---|
| `swing/data/repos/candidates.py` | MODIFIED | V2.G3 | NEW repo helper `get_latest_sector_industry_per_ticker(conn, tickers: Sequence[str]) -> dict[str, tuple[str, str]]` returning the most-recent non-empty `(sector, industry)` per ticker. Empty-string convention preserved (NOT NULL DEFAULT '' per migration 0012); legacy / no-row tickers map to `("", "")`. |
| `swing/cli.py` OR `swing/cli_diagnose.py` | MODIFIED | V2.G3 | NEW CLI subcommand `swing diagnose backfill-trades-sector-industry [--apply / --dry-run]` (or equivalent) that consumes the new repo helper + emits an idempotent UPDATE: `UPDATE trades SET sector=?, industry=? WHERE id=? AND TRIM(sector)='' AND TRIM(industry)='' AND state IN (...)` (V1 STRICT all-or-nothing per R2.M3 LOCK). Dry-run prints the affected ticker count + emits a restore-SQL artifact per §4.3; apply commits the UPDATE under `with conn:` per repo discipline. |
| `swing/web/view_models/open_positions_row.py` | OPTIONAL-MODIFIED | V2.G3 | OPTIONAL view-layer fallback if backfill alone is insufficient: if `trade.sector` or `trade.industry` is empty, fall back to `candidates.get_latest_sector_industry_per_ticker(conn, [trade.ticker])` at render time. Brainstorm verdict: ship backfill FIRST; bank VM fallback as Fix-1b if writing-plans phase or operator gate finds residual empty cells. |
| `swing/web/routes/dashboard.py` | MODIFIED | V2.G4 | Fix `get_or_fetch([benchmark])` call -> `get_or_fetch(ticker=benchmark)`; remove dead dict-style `bars_bundle.get(benchmark)` code; NARROW exception handling per §5.2 Fix A -- catch ONLY `ValueError` (empty-archive expected path; degrade to 409 + log.warning); let any other exception (`TypeError`, `AttributeError`, `KeyError`, `RuntimeError`, ...) propagate to FastAPI default 500 handler per R2.M2 anti-pattern lock. |
| `swing/web/templates/partials/daily_management_tile.html.j2` | MODIFIED | P14.N3 | Rewrite PROVISIONAL badge tooltip text to describe current clear-condition (`account_equity_snapshots`); add small inline help affordance (`<span class="muted">` with focusable detail) explaining the clear-condition; conditional emit on `tile.position_capital_utilization_is_provisional` rather than unconditional whenever pct is non-NULL; render `tile.position_capital_utilization_pct_effective` (NOT `snap.position_capital_utilization_pct`) per §6.2 denominator-stamping mirror. |
| `swing/web/view_models/dashboard.py` | MODIFIED | P14.N3 | Tile VM construction at lines 1390-1417 extended with THREE fields per §6.2 Fix A: `position_capital_denominator_dollars_resolved: float`, `position_capital_utilization_is_provisional: bool`, `position_capital_utilization_pct_effective: float | None`. Build-time wiring calls `resolve_live_capital_denominator_dollars(conn, asof_date=row_asof, at_trade_time_policy=read_live_policy(conn))` where `row_asof = date.fromisoformat(snap.data_asof_session)` (ValueError-guarded fallback per `swing/metrics/maturity.py:190-194`). Mirrors `swing/metrics/maturity.py:197-219` denominator-stamping pattern. |
| `tests/web/` (existing dashboard route tests) | MODIFIED | V2.G4 | Update existing weather-chart refresh route tests + add new tests asserting the fixed kwarg signature + log emit on the degraded path. Test path confirmed at writing-plans phase via Grep on existing weather-chart refresh tests. |
| `tests/data/repos/test_candidates_repo.py` | NEW (likely) OR MODIFIED | V2.G3 | Discriminating tests on the new `get_latest_sector_industry_per_ticker` helper; writing-plans verifies existence vs NEW creation. |
| `tests/web/test_daily_management_tile_template.py` | NEW | P14.N3 | Template-rendering tests asserting PROVISIONAL badge conditional emit + tooltip text + inline affordance render. |
| `tests/cli/test_diagnose_subcommands.py` | MODIFIED | V2.G3 | Discriminating tests on the new backfill CLI subcommand (dry-run + apply paths). |
| `tests/integration/` parametric source-grep (NEW or extension) | NEW or EXTENSION | All | L2 LOCK preservation source-grep -- verify diff under `swing/` introduces ZERO net `schwabdev.Client.` call sites against the `bf7e071` commissioning baseline. If no existing parametric source-grep test exists, writing-plans phase introduces one. |

**Estimated change footprint:** ~5-7 production-code modules MODIFIED + 1 new repo helper + 1 new CLI subcommand + 1 production template MODIFIED + 1 new test module + 2-3 modified test modules; ~8-12 commits; ~25-50 new tests (per dispatch brief Sec 2.2 estimate).

**File-touch count summary:** ~5 swing/ source files MODIFIED + 1 swing/ template MODIFIED + 1 repo helper NEW + 1 CLI subcommand NEW + ~3 tests MODIFIED + 1-2 tests NEW. ZERO `swing/data/migrations/*.sql` files added. ZERO net `swing/integrations/schwab/*.py` LOC additions or Schwab API surface widening.

---

## §4 V2.G3 -- VSAT lost Sector + Industry investigation + fix

### §4.1 Investigation -- root cause hypotheses (writing-plans phase verifies)

**H0 was FALSIFIED at brainstorm via code-read.** The dispatch brief speculated the open-positions row VM might lack Sector/Industry wiring entirely. Investigation surfaces:

- Schema columns `trades.sector` + `trades.industry` ALREADY exist per migration `0012_sector_industry.sql:23-24` -- both `TEXT NOT NULL DEFAULT ''` (additive ALTER TABLE on the v12 transition; not nullable; empty-string default).
- `Trade` dataclass at `swing/data/models.py:132-133` declares `sector: str = ""` + `industry: str = ""` matching the schema default.
- `swing/data/repos/trades.py:224 + :286` INSERT and UPDATE flows persist `trade.sector, trade.industry` positionally.
- `swing/web/templates/partials/open_positions_row.html.j2:37-38` ALREADY renders `{{ row.trade.sector or "—" }}` + `{{ row.trade.industry or "—" }}` (em-dash placeholder when empty).
- Migration 0012 comment text: "trades freeze the value at entry-time per the snapshot-at-entry-surface pattern (precedents: hypothesis_label / migration 0007; chart_pattern_* / 0010)" -- the design intent is snapshot-at-entry-time, NOT cross-time JOIN at read time.
- Phase 9 Sub-bundle D `_emit_sector_tamper_audit` at `swing/web/routes/trades.py:125-170` proves the entry-form POST handler HAS sector/industry handling (compares form-submitted value vs `candidates`-cached anchor for tamper detection).

So the read path (schema -> dataclass -> repo SELECT -> VM -> template) is wired correctly. The failure mode for VSAT must be at the WRITE PATH.

**H_NEW1 (RECOMMENDED PRIMARY HYPOTHESIS) -- Pre-migration-0012 legacy default `''` value persists for trades opened before the migration landed.** `ALTER TABLE trades ADD COLUMN sector TEXT NOT NULL DEFAULT ''` is O(metadata) on SQLite (no row rewrite); existing rows pre-migration get the default `''` and stay that way until an UPDATE fires. If VSAT's trade row was opened pre-2026 (or whenever migration 0012 landed) and never had a subsequent UPDATE that wrote sector/industry, VSAT remains at empty default. Acknowledged-legacy DHA (DHC) falls in the same category per operator framing. The misattribution is operator memory: operator perceived "VSAT lost" when in fact VSAT never had them (same as DHA).

**H_NEW2 -- Entry-form POST handler persisted empty strings because the candidates lookup at POST time returned no row.** If VSAT's trade was opened on a day when VSAT had ALREADY rotated out of the finviz screen (no `candidates` row with non-empty sector/industry), the form-emitted hidden anchors would carry empty strings, and the POST handler would persist `sector=''` `industry=''` (without raising or surfacing a warning). Mirrors the PriceCache `_last_close` ticker-rotation gotcha family applied to the snapshot-at-entry surface.

**H_NEW3 -- A subsequent UPDATE path on the trades table set sector/industry back to empty.** Less likely (no obvious code path), but writing-plans phase verifies via grep on `UPDATE trades SET ... sector` / `... industry` to confirm no path overwrites these columns to empty after entry.

**Brainstorm verdict:** H_NEW1 + H_NEW2 are both plausible; either way the fix surface is the SAME -- backfill empty `(sector, industry)` cells from the most-recent `candidates` row. Writing-plans phase confirms VSAT's specific trade-row creation date + finviz-CSV state on that date to disambiguate H_NEW1 vs H_NEW2. The disambiguation is informational; the fix proceeds either way.

### §4.2 Fix candidates

**Fix A (RECOMMENDED) -- One-time backfill helper.** New CLI subcommand `swing diagnose backfill-trades-sector-industry` that (a) enumerates open trades with empty `sector` OR empty `industry`; (b) consults `candidates` for the most-recent non-empty `(sector, industry)` per ticker; (c) emits a dry-run table + apply-flag UPDATE. Idempotent (re-runs only affect remaining empty cells). NO schema migration. NO change to entry-form path (preserves snapshot-at-entry semantic intent for new trades). Closes VSAT (H_NEW1 + H_NEW2) + leaves DHA/DHC as acknowledged-legacy IF no candidates row exists for them (operator-acknowledged per dispatch brief §1.6).

**Fix B (DEFENSE-IN-DEPTH; OPTIONAL) -- VM-time fallback.** In `swing/web/view_models/open_positions_row.py` (or via `build_dashboard`'s open-positions construction loop), if `trade.sector == ""` OR `trade.industry == ""`, fall back to a per-ticker lookup against `candidates.get_latest_sector_industry_per_ticker(conn, [trade.ticker])`. Renders the most-recent-non-empty value, mirroring PriceCache `_last_close` discipline. **Brainstorm verdict: ship Fix A FIRST; bank Fix B as Fix-1b** to apply only if writing-plans phase or operator gate finds residual empty cells (e.g., trades opened on a day when candidates had no row for ticker).

**Fix C (SCHEMA DENORMALIZATION CHANGE -- previously dispatch brief Fix C)** Union open-trade tickers into `_step_evaluate`'s sector/industry persistence pass so the pipeline writes sector/industry for open-trade tickers even when not in today's finviz CSV. **Brainstorm verdict: NOT recommended; pipeline-step contract pollution.** Bank as V2 candidate.

**Fix D (V2 candidate; not in V1 scope)** Per-ticker `sector_industry_cache` table; written at every observation. Schema v22 migration. V2 candidate per dispatch brief §1.5 LOCK.

### §4.3 Recommended fix design: backfill helper + repo helper + dry-run CLI surface

**New repo helper at `swing/data/repos/candidates.py`:**

```python
def get_latest_sector_industry_per_ticker(
    conn: sqlite3.Connection, tickers: Sequence[str],
) -> dict[str, tuple[str, str]]:
    """Return {ticker: (sector, industry)} keyed on the most-recent
    row per ticker with non-empty sector AND non-empty industry.
    Tickers with no qualifying row map to ('', '') (empty-string
    default per migration 0012's TEXT NOT NULL DEFAULT '').

    Used by Phase 14 Sub-bundle 1 V2.G3 backfill helper to repair
    empty trades.sector / trades.industry values on legacy or
    candidates-rotation cases. Backwards-compat: operator-acknowledged
    DHA/DHC legacy trades (no qualifying candidates row) return
    ('', ''); the open-positions template renders em-dash for empty.

    Empty tickers input returns {} without executing SQL.
    """
```

**SQL skeleton** (per Expansion #4 + #20 binding column verification):

```sql
SELECT ticker, sector, industry
FROM (
    SELECT
        c.ticker,
        c.sector,
        c.industry,
        ROW_NUMBER() OVER (
            PARTITION BY c.ticker
            ORDER BY
                c.evaluation_run_id DESC,
                c.id DESC
        ) AS rn
    FROM candidates c
    WHERE c.ticker IN ({placeholders})  -- dynamic ?-expansion per gotcha #20
      AND c.sector != ''
      AND c.industry != ''
) ranked
WHERE ranked.rn = 1;
```

Per Expansion #4 sub-refinement (CLAUDE.md gotcha #20): the IN-clause uses dynamic `?` expansion (NOT `:name` placeholder which sqlite3 cannot bind a list to). Empty tickers input short-circuits to `{}` BEFORE executing the SQL.

**Column verification (per Expansion #4):**
- `candidates.ticker` -- migration `0001_phase1_initial.sql` (TEXT NOT NULL) [VERIFY at writing-plans phase]
- `candidates.sector` -- migration `0012_sector_industry.sql:20` (TEXT NOT NULL DEFAULT '') [VERIFIED at brainstorm]
- `candidates.industry` -- migration `0012_sector_industry.sql:21` (TEXT NOT NULL DEFAULT '') [VERIFIED at brainstorm]
- `candidates.evaluation_run_id` -- migration `0001_phase1_initial.sql` (INTEGER NOT NULL); ordering anchor
- `candidates.id` -- PK; tie-breaker

**New CLI subcommand** (under `swing diagnose ...`):

```
swing diagnose backfill-trades-sector-industry --dry-run
swing diagnose backfill-trades-sector-industry --apply
```

Dry-run path (V1 STRICT all-or-nothing semantic):
1. `SELECT trades.id, trades.ticker, trades.sector, trades.industry FROM trades WHERE TRIM(sector) = '' AND TRIM(industry) = '' AND state IN (...)` -- BOTH empty (AND-empty); active states only (operator-paired allowlist at writing-plans phase: `'entered'`, `'managing'`, `'partial_exited'`; default `--include-closed=false`). Rows with `sector='Tech', industry=''` (partial-empty) are EXCLUDED from the selection per R2.M3 lock -- they fall through to a separate diagnostic SELECT in step 5 and emit `SKIP_PARTIAL_EMPTY` rows in the table but never UPDATE.
2. For each ticker, call `get_latest_sector_industry_per_ticker(conn, [ticker])`
3. Print table: `(trade_id, ticker, current_sector, current_industry, proposed_sector, proposed_industry, source_candidate_id, source_evaluation_run_id, action)`
4. Action column for AND-empty rows: `"UPDATE"` if BOTH replacements are non-empty (all-or-nothing per V1 locked semantic); `"SKIP_NO_CANDIDATES_ROW"` if helper returned `("", "")` (acknowledged-legacy DHA/DHC path; consistent with operator framing).
5. Separate diagnostic enumeration of partial-empty rows: `SELECT id, ticker, sector, industry FROM trades WHERE (TRIM(sector) = '' OR TRIM(industry) = '') AND NOT (TRIM(sector) = '' AND TRIM(industry) = '') AND state IN (...)` -- these get action `"SKIP_PARTIAL_EMPTY"` (operator-visible; banked as V2 candidate to support partial recovery via per-column lookup).
5. ALWAYS emit a restore-SQL artifact at a dry-run-emitted path (e.g., `exports/diagnostics/backfill-trades-sector-industry-restore-<ISO>.sql`) containing per-affected-row `UPDATE trades SET sector='<OLD>', industry='<OLD>' WHERE id=<ID>;` statements. Operator can apply the restore SQL via `sqlite3 swing.db < restore.sql` if the apply step lands wrong values.

Apply path:
1. Inside `with conn:` -- atomic transaction.
2. Re-emit dry-run table (operator confirms count).
3. ALSO emit the same restore-SQL artifact BEFORE issuing UPDATEs (defense-in-depth; survives a crash post-UPDATE).
4. Optional `--allowlist <ticker,ticker,...>` flag for per-ticker opt-in; default operates on all `action="UPDATE"` rows.
5. For each row needing update: `UPDATE trades SET sector=?, industry=? WHERE id=? AND TRIM(sector)='' AND TRIM(industry)=''` -- the WHERE clause makes the UPDATE no-op if the row was concurrently populated (defense against race; SQL idempotent).
6. Print summary table + commit. Cite the restore-SQL artifact path in the summary so operator can locate it post-apply.

**DHA/DHC operator-acknowledged exclusion**: writing-plans phase confirms whether DHA/DHC are explicitly hardcoded in an exclusion list OR relied on via the `SKIP_NO_CANDIDATES_ROW` action (since DHA/DHC have ZERO candidates rows per operator framing). The latter is preferred for V1 (no hardcoded ticker list); operator can confirm at gate.

### §4.4 Error handling + edge cases

- **No `candidates` row for ticker** -- helper returns `("", "")`; backfill CLI skips that ticker (no UPDATE); operator sees em-dash in dashboard (acknowledged-legacy path; consistent with DHA/DHC operator framing).
- **Partial-empty trade row (`sector="Tech"`, `industry=""`) (R2.M3 LOCK)** -- backfill SELECT (step 1) requires BOTH empty (`AND` not `OR`); partial-empty rows fall through to the separate diagnostic enumeration (step 5) and emit `"SKIP_PARTIAL_EMPTY"`; NO UPDATE fires. V1 STRICT all-or-nothing locked at brainstorm. V2 candidate banked: relax to per-column lookup with separate dry-run + apply paths.
- **Trade in non-open state (closed / cancelled)** -- backfill CLI restricts to active states OR offers `--include-closed` flag. Operator-paired at writing-plans phase.
- **Helper raises SQL error** -- bubble up; backfill CLI emits operator-friendly error + non-zero exit code.

### §4.5 Discriminating-example walkthroughs

1. **Happy path -- VSAT in candidates with non-empty Sector + Industry** -- plant VSAT trade row with `sector=''`, `industry=''`; plant candidates row with `sector="Technology"`, `industry="Communications Equipment"`; invoke backfill --apply; assert UPDATE fired + trades.sector="Technology" + trades.industry="Communications Equipment".
2. **VSAT historical candidates exists (post-rotation)** -- plant VSAT trade row with empty values; plant a historical (older `evaluation_run_id`) candidates row for VSAT with non-empty values; no recent candidates row; invoke backfill; assert UPDATE picks the historical row.
3. **DHA legacy -- ZERO candidates rows for ticker** -- plant DHA trade row with empty values; no candidates row; invoke backfill; assert SKIP (no UPDATE); template still renders em-dash post-backfill.
4. **Partial-empty trade row (R2.M3 lock)** -- plant ticker with `sector="Tech"`, `industry=""`; plant candidates row with both non-empty; invoke backfill; assert action `"SKIP_PARTIAL_EMPTY"` (V1 strict all-or-nothing); NO UPDATE fires; partial-empty row appears in the separate diagnostic enumeration (§4.3 step 5). Template continues to render "Tech" + em-dash post-backfill (no regression).
5. **Dry-run no-op** -- backfill --dry-run; assert NO UPDATE fired; assert summary table printed.
6. **Idempotency** -- run backfill --apply twice; second run prints summary with zero affected rows.
7. **Source-grep verification of L2 LOCK** -- assert backfill helper does NOT import or invoke any `schwabdev.Client.*` method.

### §4.6 Test fixture strategy

- TestClient or direct SQLite at `tmp_path / 'swing.db'`; populate `candidates` + `trades` via existing repo helpers (NO synthetic-fixture-vs-production-emitter drift per CLAUDE.md gotcha family).
- The repo helper test consumes pytest fixtures that mirror the production emit path: `_step_evaluate` writes via `swing.data.repos.candidates.insert_candidates(conn, run_id, [Candidate(...)])` (bulk-insert; V1 path); tests use the same `insert_candidates` to plant fixtures.
- Backfill CLI test extends `tests/cli/test_diagnose_subcommands.py` infrastructure (writing-plans phase confirms exact insertion point).
- Existing `tests/data/test_repos_candidates.py` is extended with discriminating tests for the new `get_latest_sector_industry_per_ticker` helper.

---

## §5 V2.G4 -- Refresh weather chart SPY-bars-unavailable investigation + fix

### §5.1 Investigation -- root cause CONFIRMED at brainstorm

**Root cause: call-signature mismatch at `swing/web/routes/dashboard.py:75-77`.**

Current code:
```python
try:
    bars_bundle = ohlcv_cache.get_or_fetch([benchmark])
    bars = bars_bundle.get(benchmark) if bars_bundle else None
except Exception:  # noqa: BLE001 - degraded fallback
    bars = None
if bars is None or bars.empty:
    raise HTTPException(status_code=409, detail=(
        f"no OHLCV bars available for benchmark {benchmark!r}; "
        "run the pipeline first"
    ))
```

But the actual method signature at `swing/web/ohlcv_cache.py:131`:
```python
def get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame:
```

`ticker` is **keyword-only**. The handler passes `[benchmark]` POSITIONALLY -- which raises `TypeError: get_or_fetch() takes 1 positional argument but 2 were given`. The bare `except Exception` swallows the TypeError. `bars` becomes None. The subsequent check fires the 409 with the misleading "no OHLCV bars available" message.

**The dict-style `bars_bundle.get(benchmark)` consumption is dead code** -- `get_or_fetch` returns a `pd.DataFrame`, not a dict. The original author appears to have confused `get_or_fetch` (single-ticker DataFrame return) with `get_many_bundles` (multi-ticker dict return) at line 260 in the same file.

The brief's four hypotheses (A: hydration gap in chart_jit; B: cfg-resolution timing; C: write-vs-read path divergence; D: V2.G1 root-cause overlap) are all **superseded by H0 = call-signature mismatch**.

### §5.2 Fix candidates

**Fix A (RECOMMENDED) -- call-site fix + NARROW exception handling + add module logger (R3.M2 LOCK).**

Module-level addition at `swing/web/routes/dashboard.py` (the file currently imports no `logging` and defines no `log`; this addition is REQUIRED per R3.M2 -- without it the `log.warning(...)` call below raises `NameError` and converts the empty-archive degraded path into an uncaught exception):

```python
import logging
log = logging.getLogger(__name__)
```

Rewrite the handler's bars-fetch block to:

```python
try:
    bars = ohlcv_cache.get_or_fetch(ticker=benchmark)
except ValueError as exc:
    # OhlcvCache.get_or_fetch raises ValueError("No data for {ticker}") on
    # empty-archive / cache-miss-fallthrough per its docstring. This is the
    # canonical empty-result signal (NOT a programming error). Emit a
    # warning so the operator-visible 409 message can be diagnosed via
    # logs per gotcha #27 (empty-pool early-return + audit emission).
    log.warning(
        "weather-chart refresh: get_or_fetch returned empty for %s: %s",
        benchmark, exc,
    )
    bars = None
# NOTE: Do NOT catch broad `Exception` here. The pre-fix handler caught
# arbitrary exceptions (including the TypeError that hid this bug for
# weeks) and silently returned a 409 "no bars" message -- exactly the
# masking pattern the operator-witnessed gate surfaced. Let TypeError,
# AttributeError, KeyError, and other programming errors propagate to
# FastAPI's default 500 handler so they show up in operator-witnessed
# gates as 500s (not as "run the pipeline first" 409s).
if bars is None or bars.empty:
    raise HTTPException(status_code=409, detail=(
        f"no OHLCV bars available for benchmark {benchmark!r}; "
        "run the pipeline first"
    ))
```

This separates the **expected empty-result path** (`ValueError`; degrade to 409 with operator-friendly message + log.warning) from the **unexpected-failure path** (any other exception; propagate to FastAPI default 500 handler; surfaces as a 500 in the operator browser + emits the full traceback to logs). Per gotcha #27 -- pipeline-step early-return MUST emit audit; this is the route-handler analogue. Per M5 anti-pattern: do NOT continue the broad-Exception-catch behavior that hid the V2.G4 root cause for so long.

The dead dict-style `bars_bundle.get(benchmark)` consumption is removed.

**Fix B -- migrate to `read_or_fetch_archive` directly.** Bypass OhlcvCache; call `read_or_fetch_archive(ticker=benchmark, end_date=last_completed_session(now()), cache_dir=cfg.paths.prices_cache_dir, archive_history_days=cfg.archive.archive_history_days)` directly. ZERO cache-layer involvement; reads the persistent parquet archive. **Risk:** bypasses the OhlcvCache TTL + in-progress-bar strip + ladder-routing logic; would re-fetch on every click. **V2 candidate; not recommended for V1.**

**Fix C -- hydrate-then-fetch.** Force the benchmark ticker into the OhlcvCache via `ohlcv_cache.refresh_archive(ticker=benchmark)` (if such helper exists; brainstorm verifies at writing-plans phase) BEFORE the get_or_fetch. **Belt-and-suspenders; not strictly needed if Fix A's call-signature fix produces correct bars.** Brainstorm verdict: bank as V2 candidate.

### §5.3 cfg.rs.benchmark_ticker resolution timing (Open Question #3)

The current handler reads `cfg.rs.benchmark_ticker` at request time via `cfg = apply_overrides(request.app.state.cfg)` at line 56. **This is request-time resolution.** Open Question #3 from dispatch brief resolves: NO change to cfg-resolution timing needed; the current request-time resolution is correct.

### §5.4 V2.G1 + V2.G4 root-cause overlap (Open Question #2)

V2.G4 root cause is a **local call-signature bug** in the refresh handler. V2.G1 (hyp-rec + watchlist expanded charts not rendering candlesticks) is a chart-renderer concern (`render_position_detail_svg` + per-surface kwargs). **NO overlap**; V2.G4 is owned by Sub-bundle 1; V2.G1 remains Sub-bundle 3 scope. Operator-witnessed gate verification will confirm the V2.G4 fix does NOT incidentally improve V2.G1 (and vice-versa).

### §5.5 Error handling + edge cases

- **Empty archive for SPY (legitimate cache miss)** -- `get_or_fetch` raises `ValueError("No data for SPY")`; handler emits `log.warning` + returns 409.
- **OhlcvCache misconfigured (`ohlcv_cache is None`)** -- existing branch at line 69-73 already handles via 409 "OHLCV cache not initialized".
- **`refresh_chart_render` raises (e.g., transient-empty bytes per F6 gotcha)** -- existing `ChartRender.__post_init__` rejects empty bytes at construction; the handler's outer try/finally rolls back the `with conn:` block; existing chart_render row preserved.
- **`latest_completed_pipeline_run(conn)` returns None (no completed pipeline run)** -- existing branch at line 60-67 already handles via 409 "no completed pipeline_run; run the pipeline before refreshing".

### §5.6 Discriminating-example walkthroughs

1. **Happy path -- fresh pipeline run + SPY bars in archive** -- plant a `pipeline_runs` row with `finished_ts` non-NULL; plant SPY bars in `read_or_fetch_archive` source; POST `/dashboard/weather-chart/refresh`; assert 204 + `HX-Redirect: /dashboard`; assert chart_renders row written.
2. **TypeError-vs-correctness regression** -- mock `OhlcvCache.get_or_fetch` to assert it's called with `ticker='SPY'` kwarg-style (not positional list); assert no TypeError raised.
3. **Empty-archive degraded path** -- mock `OhlcvCache.get_or_fetch` to raise `ValueError("No data for SPY")`; POST; assert 409 with operator-friendly message; assert `log.warning` was emitted with the ticker name.
4. **Unexpected-exception propagation path** -- mock `OhlcvCache.get_or_fetch` to raise an arbitrary `RuntimeError` (or `TypeError`); POST; assert the exception PROPAGATES (TestClient surfaces as 500 via FastAPI default handler, NOT 409). Asserts that the V2.G4 root-cause class (programming errors silently masked as 409s) cannot recur.
5. **No-pipeline degraded path** -- empty `pipeline_runs` table; POST; assert existing 409 "no completed pipeline_run" message (unchanged from current behavior).
6. **Pre-fix regression** -- BEFORE the fix, the handler returns 409 for ALL refresh attempts. Discriminating test asserts post-fix the happy path returns 204 (regression cannot recur).

### §5.7 Test fixture strategy

- TestClient + ephemeral SQLite + mocked `OhlcvCache` via `monkeypatch.setattr(...)` -- mock returns canned DataFrame fixtures matching `get_or_fetch`'s real shape (DatetimeIndex; capitalized `Open / High / Low / Close / Volume` columns).
- Production-shape fixture: planted bars taken from existing T2.SB6a `tests/web/test_dashboard_weather_chart_refresh.py` fixtures (preserve fixture-shape parity per CLAUDE.md "Synthetic-fixture-vs-production-emitter shape drift" discipline).

---

## §6 P14.N3 -- Daily management Capital % "PROVISIONAL" suffix investigation + fix

### §6.1 Investigation -- root cause CONFIRMED at brainstorm

**PROVISIONAL is NOT a runtime-computed suffix on the daily-management state machine; it is a template-rendered marker on the `position_capital_utilization_pct` cell.**

Located at `swing/web/templates/partials/daily_management_tile.html.j2:91-99`:

```jinja
<td data-tile-cell="position_capital_utilization_pct">
    {%- if tile.position_capital_utilization_pct is not none -%}
        {{ "%.1f"|format(tile.position_capital_utilization_pct * 100.0) }}%
        {#- Spec §10.5: V1 fallback uses capital_floor_constant_dollars
            ($7500) as denominator -- surface a PROVISIONAL marker so
            the operator sees the V1->V2 versioning caveat. -#}
        <span class="badge badge-provisional" data-marker="PROVISIONAL"
              title="V1 denominator = $7500 capital_floor_constant_dollars; V2 will resolve to live account equity (Phase 9 risk_policy versioning).">PROVISIONAL</span>
    {%- else -%}—{%- endif -%}
</td>
```

**Two problems with the current state:**

1. **Stale tooltip text.** The title text says "V2 will resolve to live account equity (Phase 9 risk_policy versioning)" -- but Phase 9 + Phase 11 ALREADY SHIPPED this infrastructure via `equity_resolver.resolve_live_capital_denominator_dollars` + `account_equity_snapshots` table. The badge currently fires unconditionally (the template's `{% if tile.position_capital_utilization_pct is not none %}` check does NOT inspect whether the denominator was the live-equity OR the fallback -- it just appends PROVISIONAL whenever the value is rendered).
2. **No visible affordance for clearing the flag.** The tooltip is hover-only; operator framing "no clear explanation of what would clear it" reflects this. Operator does not know that writing an `account_equity_snapshots` row (e.g., via `swing schwab fetch --snapshot` when Schwab integration is LIVE; or via future manual entry surface) would flip the badge to LIVE.

**Underlying state-machine semantics** (verified at brainstorm):
- `equity_resolver.resolve_live_capital_denominator_dollars(conn, *, asof_date: date, at_trade_time_policy: RiskPolicy)` returns `tuple[float, Literal["LIVE", "PROVISIONAL"]]`.
- LIVE when `account_equity_snapshots` row exists with `snapshot_date <= asof_date`; returns the snapshot's `equity_dollars`.
- PROVISIONAL when no snapshot satisfies the predicate; falls back to `at_trade_time_policy.capital_floor_constant_dollars`.
- The metrics views (capital_friction; position_state) consume this triplet correctly; they emit a `ProvisionalBadgeVM(is_provisional: bool, ...)` per `swing/web/view_models/metrics/shared.py:132+`.
- **The daily_management_tile.html.j2 template does NOT consume `ProvisionalBadgeVM`** -- it has a hardcoded badge emit based on `tile.position_capital_utilization_pct is not none`. This is a coupling gap: the tile renders the badge unconditionally even when the denominator IS LIVE.

### §6.2 Fix candidates

**Fix A (RECOMMENDED for V1) -- Template-rendering surface audit + VM extension to consume LIVE/PROVISIONAL state with denominator-stamping discipline.** Three surgical edits mirroring the canonical `swing/metrics/maturity.py:197-219` pattern:

1. **Extend the daily-management tile VM** (`swing/web/view_models/daily_management.py` or wherever `DailyManagementTileVM` is defined; writing-plans phase confirms exact module -- the dashboard VM at `swing/web/view_models/dashboard.py:1390-1417` currently constructs the tile inline) to include THREE fields:
   - `position_capital_denominator_dollars_resolved: float` -- the FRESHLY-resolved denominator at render time
   - `position_capital_utilization_is_provisional: bool` -- True iff freshly-resolved state == "PROVISIONAL"
   - `position_capital_utilization_pct_effective: float | None` -- the utilization to render (stored if denominators match; recomputed otherwise; None when ill-defined)
2. **Build-time VM resolution mirrors `maturity.py:197-219` BUT honors the daily-management proportion-unit contract:** parse `snap.data_asof_session` (NOT a hypothetical `review_date`) via `date.fromisoformat(...)` with a ValueError-guarded fallback to `asof_date` per `maturity.py:190-194`; call `resolve_live_capital_denominator_dollars(conn, asof_date=row_asof, at_trade_time_policy=read_live_policy(conn))`; reuse `snap.position_capital_utilization_pct` (PROPORTION 0.0-1.0+; per `swing/trades/daily_management.py:381-394 compute_position_capital_utilization` contract) ONLY when `snap.position_capital_denominator_dollars` matches the freshly-resolved value via `math.isclose(...)`; otherwise recompute as a PROPORTION via `swing/trades/daily_management.py:compute_position_capital_utilization(current_size=..., current_price=..., denominator_dollars=denom_dollars)`. **CRITICAL UNIT NOTE per R3.M1**: do NOT use `maturity.py:296-304 _compute_position_util_pct` here -- that helper returns `(exposure / denom) * 100.0` (already a percent, e.g., 15.0 for 15%). The daily-management template at line 92 multiplies by 100.0 again, so using the percent helper would produce 1500.0%. The proportion contract preserves the existing template render math + the existing snap.position_capital_utilization_pct semantic. This ensures the badge AND the displayed pct are coherent.
3. **Template only emits the badge when `is_provisional is True`**, renders `position_capital_utilization_pct_effective` for the value, AND emits an inline help affordance:

```jinja
<td data-tile-cell="position_capital_utilization_pct">
    {%- if tile.position_capital_utilization_pct_effective is not none -%}
        {{ "%.1f"|format(tile.position_capital_utilization_pct_effective * 100.0) }}%
        {%- if tile.position_capital_utilization_is_provisional -%}
            <span class="badge badge-provisional" data-marker="PROVISIONAL"
                  title="Capital denominator is the V1 fallback (capital_floor_constant_dollars). Clears to LIVE when an account_equity_snapshots row covers the session date (e.g., swing schwab fetch --snapshot when integration LIVE).">PROVISIONAL</span>
            <span class="muted help-affordance" data-help="provisional-capital">
                (?)
                <span class="help-detail">
                    LIVE when account_equity_snapshots row covers today; PROVISIONAL otherwise.
                </span>
            </span>
        {%- endif -%}
    {%- else -%}--{%- endif -%}
</td>
```

(em-dash placeholder shown as ASCII `--` to honor gotcha #32; existing badge surfaces inside the spec use `--` rather than the Unicode em-dash.)

**Fix B (escalate to schema CHECK widening)** -- if PROVISIONAL is a persisted CHECK enum value, widen to descriptive variants. **Brainstorm verdict: NOT applicable -- PROVISIONAL is template-rendered, not persisted; no CHECK widening is needed.**

**Fix C (auto-clear on reconciliation)** -- if the flag is supposed to clear on reconciliation completion but doesn't (bug), wire the clear-condition into `swing/trades/reconciliation_auto_correct.py`. **Brainstorm verdict: NOT applicable -- the flag is correctly coupled to `account_equity_snapshots` presence; reconciliation is upstream and is what writes the snapshot in the first place (Phase 9 Sub-bundle C `record_snapshot`). The post-reconciliation flip-to-LIVE is automatic on next render once a snapshot is present. No code change needed beyond Fix A.**

### §6.3 Schema impact

**ZERO schema changes.** Fix A is template + VM extension only. No new columns; no CHECK widening; no migration. Per §2.5 LOCK preserved.

### §6.4 Error handling + edge cases

- **`equity_resolver.resolve_live_capital_denominator_dollars` raises** -- bubble up; tile renders blank cell (consistent with other `position_capital_utilization_pct_effective is not none` checks).
- **Tile VM builder reads `policy = None`** (no active risk_policy at session date) -- guard at VM builder; treat as PROVISIONAL; render the tooltip with an additional caveat.
- **Operator never runs `swing schwab fetch --snapshot`** -- badge persists indefinitely; tooltip remains operator-actionable. Acceptable V1 behavior.

### §6.5 Discriminating-example walkthroughs

1. **PROVISIONAL surfaced -- no account_equity_snapshots row** -- plant `daily_management_records` row with `position_capital_utilization_pct=0.15`; NO `account_equity_snapshots` row; render template; assert badge present + tooltip text NEW wording (mentions account_equity_snapshots).
2. **LIVE -- account_equity_snapshots row covers asof_date** -- plant `account_equity_snapshots` row with `snapshot_date <= date.fromisoformat(snap.data_asof_session)`; render template; assert NO badge emitted; assert capital % value still rendered using `position_capital_utilization_pct_effective` (recomputed if denominators diverge per maturity.py pattern).
3. **Operator clicks "?" affordance** -- assert `help-detail` text is present in rendered HTML (visible-on-focus via CSS; tests assert the HTML structure).
4. **Stale tooltip eradication** -- assert the new template does NOT contain the phrase "V2 will resolve to live account equity (Phase 9 risk_policy versioning)" -- discriminating-test pattern: `assert "Phase 9 risk_policy versioning" not in rendered_html`.
5. **ASCII discipline** -- assert badge + tooltip text use ASCII only (em-dash via `&mdash;` HTML entity or literal `--`; NO non-ASCII per CLAUDE.md gotcha #32).
6. **Operator-friendly clear-condition discoverability** -- the rewritten tooltip mentions the exact CLI command (`swing schwab fetch --snapshot`) the operator runs to clear the flag (when Schwab integration is LIVE).

### §6.6 Test fixture strategy

- New test module at `tests/web/test_daily_management_tile_template.py` (NEW per §3 module touch list).
- Renders the template fragment via Jinja2 environment + asserts on rendered HTML substrings.
- Plants `equity_resolver` state via direct `account_equity_snapshots` row inserts.
- Production-shape fixture: `data_asof_session` (ISO date string) + `capital_floor_constant_dollars` + `position_capital_utilization_pct` + `position_capital_denominator_dollars` mirror exactly what `swing/web/view_models/dashboard.py:1390-1417` constructs the tile VM from (via the `daily_management_records` snapshot read).

---

## §7 Error handling + edge cases (cross-item)

### §7.1 Consolidated error-mode table

Item | Error mode | Handler | Operator-visible |
---|---|---|---
V2.G3 | `get_latest_sector_industry_per_ticker` SQL error | Bubble to render path; 500 | Yes (page error) |
V2.G3 | Empty / no-qualifying `candidates` for ticker | Helper returns `("", "")` (empty-string convention per migration 0012 TEXT NOT NULL DEFAULT '') | Em-dash render via template's `row.trade.sector or "—"` (graceful) |
V2.G4 | `get_or_fetch` raises `ValueError("No data for SPY")` | Catch + log.warning + 409 | Existing 409 operator-friendly message |
V2.G4 | `get_or_fetch` raises arbitrary `Exception` (TypeError, AttributeError, KeyError, RuntimeError, ...) | NOT caught -- propagates to FastAPI default 500 handler | 500 with full traceback in logs; prevents the V2.G4 root-cause-class from recurring per R1.M5 / R2.M2 anti-pattern lock |
V2.G4 | TypeError from call-signature mismatch | **POST-FIX: cannot occur**; pre-fix: swallowed by bare except | **GONE** post-fix |
P14.N3 | `equity_resolver` raises | Bubble to render path; 500 | Yes (page error) |
P14.N3 | No active `risk_policy` row | Treat as PROVISIONAL with extra-caveat tooltip | Operator sees PROVISIONAL badge + tooltip |

### §7.2 HTMX trinity audit (no new endpoints; verification only)

`POST /dashboard/weather-chart/refresh` ALREADY EXISTS with HTMX trinity discipline. Sub-bundle 1 does NOT introduce new HTMX endpoints. Verification:

| Trinity item | Phase 5 R1 M1 | Phase 5 R1 M2 | Phase 6 I3 |
|---|---|---|---|
| Pre-existing on `weather-chart/refresh` | YES (HX-Request header) | YES (204 + HX-Redirect; not 303 swap) | YES (HX-Redirect target `/dashboard` registered) |
| Sub-bundle 1 changes | NO | NO | NO |

### §7.3 Server-stamping discipline (Phase 8 family)

Sub-bundle 1 does NOT introduce new form-driven state transitions. P14.N3's Fix A is template-rendering only; no form anchors. No server-stamping discipline applies.

### §7.4 Form-render anchor lifecycle audit (gotcha #15 / Expansion #9)

Sub-bundle 1 does NOT introduce new hidden form anchors. No lifecycle audit needed.

---

## §8 Cross-item coherence

The three items do not share substrate code; their fixes are mutually independent. Test interactions:
- V2.G3 + V2.G4 share `/dashboard` route surface; test isolation via separate test modules; shared TestClient fixture acceptable.
- P14.N3 lives at `/daily-management`; no overlap with `/dashboard` tests.

**Shared discipline:**
- ASCII-only template text + log messages (gotcha #32; declared scope in §15.2).
- L2 LOCK preserved (no Schwab API surface changes); discriminating source-grep test §11.4.
- ZERO Co-Authored-By footer drift; verified per Phase 12.5 #3 + V2-mechanic precedent.

**No cross-item rollback risk:** if V2.G3 fix ships but V2.G4 or P14.N3 needs rollback, V2.G3 stays shipped without dependency leak. All three items are independent and idempotent.

---

## §9 Discriminating-example walkthroughs (consolidated)

See §4.5 (V2.G3 -- 6 examples), §5.6 (V2.G4 -- 6 examples), §6.5 (P14.N3 -- 6 examples). Total: 18 discriminating tests planned (within the dispatch brief's 25-50 test estimate; remainder are regression / fixture-shape / source-grep / L2 LOCK preservation).

---

## §10 Sub-bundle decomposition

### §10.1 Single-dispatch recommendation

Per dispatch brief Open Question #8: brainstorm recommends **a single writing-plans + executing-plans dispatch** for all three items. They cohere in scope (dashboard + daily-management surfaces); they do not have inter-item dependencies; they each fit ~3-5 commits comfortably; the combined surface is well within a single dispatch's typical capacity (~8-15 commits + ~25-50 tests per dispatch brief estimate).

### §10.2 Commit cadence (writing-plans phase will refine)

Anticipated commit topology:
- T-1.1 V2.G3: NEW repo helper `get_latest_sector_industry_per_ticker` + tests (1 commit)
- T-1.2 V2.G3: NEW CLI subcommand `swing diagnose backfill-trades-sector-industry --dry-run / --apply` + tests (2-3 commits)
- T-1.3 V2.G3 (OPTIONAL): VM fallback Fix-1b if writing-plans phase or operator gate finds residual empty cells (1 commit)
- T-2.1 V2.G4: route handler signature fix + log emit + tests (1-2 commits)
- T-3.1 P14.N3: VM `position_capital_utilization_is_provisional` field + template rewrite + tests (2-3 commits)
- T-4.1 Cross-cutting: L2 LOCK source-grep verification (parametric test; 1 commit)
- T-4.2 Closer: ASCII discipline verification commit + final cleanup (1 commit)

**Estimated total: 8-12 commits.** Within dispatch brief's 8-15 commit estimate.

### §10.3 Test count estimation

- V2.G3: ~10 tests (6 discriminating + 2 backwards-compat + 2 round-trip)
- V2.G4: ~10 tests (6 discriminating + 2 HTMX trinity preservation + 2 cassette / fixture)
- P14.N3: ~8 tests (6 discriminating + 2 ASCII discipline)
- L2 LOCK source-grep: ~1 test (parametric)
- Cumulative gotcha set: ~3 tests (gotcha #11 verification; #27 log-emit; #32 ASCII)

**Estimated total: ~32 new tests.** Within dispatch brief's 25-50 test estimate.

### §10.4 Cross-bundle pin (if any)

NONE. Sub-bundle 1 does NOT cross-bundle pin.

### §10.5 Operator-witnessed gate surface enumeration (per dispatch brief §1.4)

The merge-time operator-witnessed gate has the following surfaces:

| # | Surface | Pass criterion |
|---|---|---|
| **S1** | `python -m pytest -m "not slow" -q` baseline | All tests pass; no new fails |
| **S2** | `ruff check swing/` | 0 errors |
| **S3** | `/dashboard` VSAT row | Sector + Industry columns render non-NULL values (or em-dash if legitimate legacy) |
| **S4** | `/dashboard` Refresh weather chart button | Click produces a fresh SPY weather chart render; NOT the "no OHLCV bars" error |
| **S5a** | `/daily-management` Capital % column -- PROVISIONAL CASE | Plant operator's database state with NO `account_equity_snapshots` row covering today's session; render page; assert PROVISIONAL badge present, tooltip describes account_equity_snapshots clear-condition, (?) affordance visible, stale "Phase 9 risk_policy versioning" text REMOVED, AND the displayed Capital % value is a SANE small percentage (e.g., < 50%; NOT 1500.0% per R3.M1 unit-mismatch defense) |
| **S5b** | `/daily-management` Capital % column -- LIVE CASE | Plant `account_equity_snapshots` row covering today's session via `swing schwab fetch --snapshot` OR direct insert; reload page; assert PROVISIONAL badge NOT present; assert Capital % value still rendered (using the recomputed proportion when stored denominator diverges from freshly-resolved per maturity.py mirror) |
| **S6** | Cross-fix regression check | Refreshing weather chart (S4) does not break Sector/Industry render (S3); both shipped fixes coexist cleanly |

---

## §11 Test fixture strategy

### §11.1 TestClient + ephemeral SQLite discipline

All web-route + VM tests use TestClient against an ephemeral SQLite at `tmp_path / 'swing.db'`. Existing pattern at `tests/web/conftest.py` reused (`swing_db_in_tmp_path` fixture).

### §11.2 Production-shape fixture sourcing

V2.G3 fixtures: planted via `swing.data.repos.candidates.insert_candidates(conn, run_id, [Candidate(...)])` (bulk-insert; the same emit path used by `_step_evaluate` in production). ZERO synthetic-fixture-vs-production-emitter drift per CLAUDE.md gotcha family. ZERO hand-rolled INSERT SQL in tests.

V2.G4 fixtures: planted via existing `tests/web/test_dashboard_weather_chart_refresh.py` fixture helpers; production-shape DataFrame matches `read_or_fetch_archive` output (capitalized Open/High/Low/Close/Volume + DatetimeIndex).

P14.N3 fixtures: planted via direct `account_equity_snapshots` repo helper (Phase 9 Sub-bundle C); `daily_management_records` via existing Phase 8 repo helpers.

### §11.3 Cassette discipline

NO new cassettes introduced. Sub-bundle 1 does NOT add new Schwab API calls (L2 LOCK); existing finviz cassettes unchanged.

### §11.4 L2 LOCK preservation source-grep

Existing parametric test at `tests/integration/test_l2_lock_source_grep.py` (or equivalent) verifies no NEW `schwabdev.Client.*` call sites introduced in `swing/`. Sub-bundle 1 SHALL pin via discriminating-test that any diff under `swing/` against `bf7e071` baseline (Phase 14 commissioning HEAD) introduces ZERO net `schwabdev.Client.` references. If the existing source-grep test does not exist, brainstorm-recommended-action at writing-plans phase: extend the existing `tests/integration/test_l2_lock_source_grep.py` parametric path.

### §11.5 Renderer-kwargs uniformity discipline (gotcha Expansion #10 sub-discipline c)

Sub-bundle 1 does NOT modify chart-render kwargs. The V2.G4 refresh handler's `render_market_weather_svg(bars=bars, trend_template_state="n/a")` callsite is unchanged. No renderer-kwargs uniformity LOCK applies.

### §11.6 Cumulative gotcha set application matrix

See §15.1 for the full matrix. Notable cumulative gotchas that fire per item:
- V2.G3: gotcha #4 (PriceCache `_last_close` ticker-rotation discipline applied to Sector/Industry); gotcha #20 (SQL `?` expansion); gotcha #26 (Schema-version-aware INSERT N/A; V2.G3 is read-only repo extension); gotcha #32 (ASCII discipline).
- V2.G4: gotcha #27 (empty-pool early-return + audit emission discipline -- handler emits log.warning before degrading); gotcha #32 (ASCII).
- P14.N3: gotcha #11 (Template-rendering surface audit before claiming "no template edit needed"); gotcha #32 (ASCII).

---

## §12 Schema impact analysis

**Verdict: Schema v21 LOCKED.** No migration introduced. Per dispatch brief §1.5 LOCK.

Per-item analysis:

| Item | Schema touch? | Migration needed? | Justification |
|---|---|---|---|
| V2.G3 | NEW repo helper `get_latest_sector_industry_per_ticker` consumes existing `candidates.sector` + `candidates.industry` (`TEXT NOT NULL DEFAULT ''` columns shipped at migration `0012_sector_industry.sql:20-21`) + the new backfill CLI emits idempotent UPDATEs against `trades.sector` + `trades.industry` (`TEXT NOT NULL DEFAULT ''` per `0012_sector_industry.sql:23-24`) | NO | Read + UPDATE on existing v12+ columns; no DDL |
| V2.G4 | One-line call-site fix at `swing/web/routes/dashboard.py:76`; no DB read/write changed | NO | Route handler call-signature fix; cache layer unchanged |
| P14.N3 | Template + dashboard VM extension; consumes existing `equity_resolver.resolve_live_capital_denominator_dollars` + `read_live_policy` (Phase 11 ship) + existing `account_equity_snapshots` table (Phase 9 Sub-bundle C ship) | NO | Template-rendering + VM field addition (3 new fields per maturity.py pattern); both substrates already shipped |

**No `swing/data/migrations/0022_*.sql` file added.** If writing-plans phase surfaces a hidden constraint that forces a v22 migration, ESCALATE to orchestrator (would collide with Sub-bundle 2 temporal log v22 migration claim per dispatch brief §1.5).

---

## §13 V1 simplifications + V2 candidates banked

### §13.1 V1 simplifications shipped (Sub-bundle 1 acknowledged-V1; V2-dependency cited)

| # | Simplification | V2 dependency |
|---|---|---|
| 1 | V2.G3 backfill helper (Fix A) rather than entry-form-path UPDATE (would require changing snapshot-at-entry semantic intent of migration 0012) | V2 candidate -- if a future operator-witnessed gate finds new trades opening with empty sector/industry post-ship of Sub-bundle 1, harden entry-form POST to MANDATE non-empty values OR surface a warning |
| 2 | V2.G3 Fix B VM-time fallback OPTIONAL (Fix-1b) -- bank to apply only if backfill alone is insufficient | V2 dependency: per-ticker last-known fallback at VM render time; would mirror PriceCache `_last_close` discipline more strictly than the one-time backfill |
| 3 | V2.G3 Fix C (union open-trade tickers into `_step_evaluate`) NOT applied | Alternative V2 path; bank with Fix-1b + Fix D under "V2.G3 future-improvement" header at return report |
| 4 | V2.G3 Fix D (per-ticker last-known cache table; schema v22+) NOT applied | V2 candidate; would require `sector_industry_cache` table + schema migration |
| 5 | V2.G3 partial-recovery (recover sector OR industry independently) NOT applied; helper uses "all-or-nothing" semantic | V2 candidate -- relax to per-column lookup if writing-plans / operator gate identifies cases where partial recovery is more useful than all-or-nothing |
| 6 | V2.G4 single call-site fix only (Fix A); no migration to `read_or_fetch_archive` direct path (Fix B) | V2 cache-bypass investigation if `OhlcvCache` substrate diverges from archive in future |
| 7 | V2.G4 hydrate-then-fetch belt-and-suspenders pattern (Fix C) NOT applied | Defensible only if Fix A is found unstable in operator-witnessed gate; bank for V2 |
| 8 | P14.N3 tooltip-text + inline affordance only (Fix A); no CHECK enum widening (Fix B) | NOT applicable -- PROVISIONAL is template-rendered, not persisted; Fix B was never viable |
| 9 | P14.N3 reconciliation-flow auto-clear (Fix C) NOT applied | NOT applicable -- the flag is correctly coupled to `account_equity_snapshots`; Fix C was never needed |

### §13.2 V2 candidates banked at return report

Return report §7 enumerates the V2 candidates per dispatch brief §8 #7. Anticipated candidates:

- V2.G3 Fix B (denormalize Sector/Industry on `trades` at trade-entry time; Schema v22)
- V2.G3 Fix D (per-ticker `sector_industry_cache` table; Schema v22)
- V2.G4 Fix B (direct `read_or_fetch_archive` consumption in refresh handler; bypass OhlcvCache)
- V2.G4 Fix C (hydrate-then-fetch in refresh handler; belt-and-suspenders defense)
- P14.N3 NEW operator-facing "Set capital equity" form surface (manual `account_equity_snapshots` entry for operators without Schwab LIVE)

---

## §14 Operator decision items pending (Open Questions enumerated)

Open Questions from dispatch brief §3, resolved at brainstorm:

| # | Open Question | Brainstorm resolution |
|---|---|---|
| 1 | V2.G3 Fix A vs Fix C | **Fix A (one-time backfill CLI helper) recommended for V1.** Closes the operator-visible defect via an idempotent UPDATE per §4.3 design. VM-layer fallback (Fix-1b in §4.2) banked as OPTIONAL extension if writing-plans / operator gate reveals residual empty cells. Fix C (pipeline-step pollution) NOT applied. |
| 2 | V2.G4 + V2.G1 root cause overlap | **NO overlap confirmed.** V2.G4 is a local call-signature mismatch; V2.G1 is chart-renderer concern. Sub-bundle 1 owns V2.G4; Sub-bundle 3 owns V2.G1. |
| 3 | V2.G4 cfg.rs.benchmark_ticker resolution timing | **No change.** Current request-time resolution via `apply_overrides(...)` is correct. |
| 4 | P14.N3 state-machine semantic | **Template-rendered, not persisted.** Fix A (template + VM) applies; Fix B (CHECK widening) + Fix C (auto-clear) not applicable. |
| 5 | Test fixture strategy | **TestClient + monkeypatched OhlcvCache / direct repo helpers** per §11. |
| 6 | Operator-witnessed gate surface count | **6 surfaces** (S1-S6) per §10.5. |
| 7 | Schema migration escalation rule | **No escalation needed; Schema v21 LOCKED.** |
| 8 | Sub-bundle dispatch decomposition | **SINGLE dispatch** for all three items per §10.1. |
| 9 | `_thumb_bytes` partial precedent for V2.G3 | **Not directly applicable** -- V2.G3 is text data (Sector/Industry strings); the `_thumb_bytes` precedent is for binary chart bytes. The em-dash placeholder is the appropriate text-data analogue. |
| 10 | HTMX failure surface assessment | **No new HTMX surfaces.** §7.2 confirms. |

---

## §15 Cumulative discipline compliance summary

### §15.1 Cumulative gotcha set application matrix (37 gotchas BINDING)

| Gotcha | Title | Sub-bundle 1 applicability |
|---|---|---|
| #1 | Test-count drift in plan docs | Trust pytest output; §10.3 estimate is approximate |
| #2 | Auto-memory stale snapshot | N/A (no auto-memory consumption) |
| #3 | HTMX 4xx fragments config override | N/A (no new HTMX surfaces) |
| #4 | PriceCache `_last_close` ticker-rotation | **APPLIED to V2.G3 -- the backfill helper (Fix A) consults `candidates` last-known per ticker, mirroring `_last_close` discipline applied at one-time-fix scope; banked Fix-1b extends the same discipline to render-time fallback** |
| #5 | OHLCV fetch scope = open-trade tickers ONLY | **VERIFIED preserved -- V2.G4 fix consumes existing OhlcvCache substrate which honors the scope; benchmark fetch reaches archive via `read_or_fetch_archive` fallback (no yfinance scope widening)** |
| #6 | Empty-API-result transient defense (F6) | N/A (no new write-through caches) |
| #7-9 | Migration runner discipline (executescript / INSERT OR REPLACE / SQLite-tx) | N/A (no migration) |
| #11 | Template-rendering surface audit | **APPLIED to P14.N3 -- template + VM both audited** |
| #12 | Matplotlib mathtext discipline | N/A (no new chart titles) |
| #13-14 | HTMX failure surfaces | N/A (no new HTMX surfaces; §7.2 verifies trinity preserved on weather-chart refresh) |
| #15 / Expansion #9 | Form-render anchor lifecycle audit | N/A (no new hidden form anchors) |
| #17 / Expansion #2 refinement | Brief-vs-production-function-signature | **APPLIED -- V2.G4 root cause IS exactly a signature-vs-callsite mismatch; resolved at brainstorm** |
| #18 / Expansion #4 refinement | SQL skeleton JOIN-cardinality + downstream-sufficiency | **APPLIED -- V2.G3 new repo helper uses ROW_NUMBER() OVER ... PARTITION BY ticker; ensures one row per ticker (cardinality 1:1)** |
| #19 / Expansion #2 sub-refinement | Cascade-call-graph verification | N/A (no leaf-call-graph cascade in scope) |
| #20 / Expansion #4 sub-refinement | Runtime-binding-shape + empty-input audit | **APPLIED -- V2.G3 SQL helper uses dynamic `?` expansion; empty input short-circuits to `{}` before SQL** |
| #21-23 | Adversarial-review fix loops + per-counter + dataclass attribution | N/A (no SQL aggregation; no multi-round fix loops anticipated) |
| #24 | Parallel-archive freshness desync | N/A (no parallel-archive consumption in scope) |
| #25 | Sentinel-bucket parity-comparison | N/A (no V1↔V2 parity comparison) |
| #26 | OHLCV archive bar-content TEMPORAL mutation | N/A (no time-travel reads) |
| #27 | Silent-skip-without-audit | **APPLIED to V2.G4 -- log.warning emitted before the 409 degrade response** |
| #28-29 | Pattern exemplar OHLCV cache discipline | N/A (no detector / template-matching surface) |
| #30-31 | Recency/filter/dedup + narrative artifact path/fact lag | N/A (no analytical artifact) |
| #32 | ASCII discipline scope clarity | **APPLIED ACROSS ALL THREE ITEMS at PRODUCTION + TEST + RETURN-REPORT surfaces** -- production code modules + 1 template + test modules + return report ASCII-only. The spec doc + dispatch brief are EXCLUDED from strict ASCII per §15.2 rationale (`§` usage extensive; converting degrades operator-orchestrator dispatch contract readability). |
| #33 | Cohort-validity-vs-verdict-criteria | N/A (no analytical verdict) |
| #34 | Brief-prescription cross-table verification | N/A (no analytical artifact table) |
| #35 | Substrate density metric disambiguation | N/A (no metric definitions) |
| #36 | Two-Codex-chain default | **SINGLE chain at end (per Sec 9.1 Q7 LOCK + gotcha #36 explicit caveat for pure UX/wiring without analytical artifact)** |
| #37 | Substrate-freshness sensitivity | N/A (no prior-arc cohort fixture consumption) |

**Summary: 6 gotchas APPLIED + 31 gotchas N/A. Zero gotchas violated.**

### §15.2 ASCII discipline scope declaration (per gotcha #32)

ASCII-only across the following Sub-bundle 1 PRODUCTION + TEST surfaces (writing-plans phase confirms exact file paths against the existing tests/ layout):

1. `swing/data/repos/candidates.py` (MODIFIED -- new helper)
2. `swing/cli.py` OR `swing/cli_diagnose.py` (MODIFIED -- new backfill subcommand; writing-plans phase chooses the right module)
3. `swing/web/view_models/open_positions_row.py` (OPTIONAL-MODIFIED; only if Fix-1b VM fallback is applied)
4. `swing/web/routes/dashboard.py` (MODIFIED -- diff only)
5. `swing/web/view_models/dashboard.py` (MODIFIED -- new tile VM fields per §6.2 Fix A; mirrors `swing/metrics/maturity.py:197-219` denominator-stamping)
6. `swing/web/templates/partials/daily_management_tile.html.j2` (MODIFIED)
7. Test modules per §3 module touch list (writing-plans phase confirms exact paths against existing `tests/` layout; known existing: `tests/data/test_repos_candidates.py`, `tests/web/test_daily_management_tile.py`, `tests/cli/test_diagnose_subcommands.py`)
8. Return report `docs/phase14-sub-bundle-1-data-wiring-brainstorm-return-report.md` (NEW; declared scope)

**This design spec + the dispatch brief are EXCLUDED from the strict ASCII scope.** Both documents use `§` (section sign) extensively to cite specification + plan + brief sections per project convention; converting these would degrade readability of the operator-orchestrator dispatch contract. The strict ASCII scope applies only to production code paths + test files (which flow through Windows stdout via pytest or CLI invocations) + the return report (which the operator may grep / cite).

Writing-plans phase audits the `tests/web/`, `tests/data/repos/`, `tests/cli/` directory layouts against existing test conventions + locks specific test-module paths in plan §B.

Verification at writing-plans + executing-plans phases: programmatic `text.encode("ascii")` over each declared file; CI lint extension if convenient.

### §15.3 ZERO Co-Authored-By trailer drift discipline

Sub-bundle 1 SHALL preserve the ~581+ cumulative ZERO Co-Authored-By footer trailer drift streak. Verification per Phase 12.5 #3 + V2-mechanic precedent: `git log --pretty="%(trailers)" main..HEAD` MUST emit ZERO `Co-Authored-By:` lines on the sub-bundle branch. Return report §14 confirms.

### §15.4 L2 LOCK preservation

ZERO new `schwabdev.Client.*` call sites. ZERO new `schwab_api_calls` audit row emit sites. Discriminating test at §11.4. Return report confirms.

### §15.5 45th cumulative C.C lesson #6 validation slot

Sub-bundle 1 consumes the 45th cumulative C.C lesson #6 validation slot. Single Codex chain at end of brainstorm; expected convergence 2-4 rounds NO_NEW_CRITICAL_MAJOR per gotcha #36 caveat for pure-UX/wiring sub-bundles without substantive analytical artifact. Return report enumerates round shape + finding taper + cumulative discipline result (CLEAN / NOTABLE).

---

*End of Phase 14 Sub-bundle 1 design spec. ~600 lines; 3 data-wiring items (V2.G3 + V2.G4 + P14.N3); Sec 9.1 LOCKs honored; Schema v21 LOCKED; L2 LOCK preserved; ASCII-only scope declared; ~32 new tests + 8-12 commits estimated. Brainstorm ready for Codex MCP adversarial chain review.*
