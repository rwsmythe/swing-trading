# Schwab API Sub-bundle C — executing-plans return report

**Status: READY FOR INTEGRATION** — adversarial Codex chain converged at Round 5 to NO_NEW_CRITICAL_MAJOR. Operator-witnessed verification surfaces S2-S5 PENDING orchestrator-driven gate; S1+S6-S9 inline PASS.

**Sub-bundle scope:** Market Data API (`/marketdata/quotes` + `/marketdata/pricehistory`) + Shape A market-data ladder (parquet-per-(ticker, provider)) + `PriceCache` / `OhlcvCache` integration + sandbox short-circuit + `swing schwab fetch --verify-marketdata` CLI subcommand + cross-bundle pin un-skips at T-C.5 + T-C.7.

**Format precedent:** `docs/schwab-bundle-B-return-report.md` (Sub-bundle B return report at `0124a76`).

---

## §1 Final HEAD + commit breakdown

- **Branch:** `schwab-bundle-C-marketdata-and-cache-ladder`
- **Worktree:** `.worktrees/schwab-bundle-C-marketdata-and-cache-ladder/`
- **BASELINE_SHA:** `8356b34` (main HEAD pre-dispatch)
- **Final HEAD:** `5f658d7`
- **Total commits since BASELINE_SHA:** **25** (1 recon + 7 task-impl + 17 Codex-fix)

**Commit chain (chronological):**

```
9d1e3e4 docs(schwab-api): T-C.0.b recon doc with Market Data API observations
7450c6f feat(schwab): Market Data API endpoint methods + mappers                            ← T-C.1
1db216a feat(schwab): OHLCV archive Shape A parquet-per-(ticker, provider) + ...           ← T-C.2
3844303 feat(schwab): market-data ladder fetcher with sandbox short-circuit + yfinance ... ← T-C.3
0207e26 feat(schwab): PriceCache + OhlcvCache integration with market-data ladder           ← T-C.4
4b261d4 feat(schwab): swing schwab fetch --verify-marketdata CLI subcommand                ← T-C.5
502c2cc feat(schwab): wire market-data ladder into _step_evaluate + _step_charts ...       ← T-C.6
13edfd7 test(schwab): un-skip sentinel-leak audit Bundle C coverage                        ← T-C.7
2e38416 fix(schwab-bundle-C): Codex R1 Major #2 — normalize legacy DatetimeIndex shape ...
1a5e099 fix(schwab-bundle-C): Codex R1 Major #1 — wire _backward_compat_rename into ...
d9e8c6f fix(schwab-bundle-C): Codex R1 Major #4 — add SchwabPriceHistoryWindow.to_dataframe()
700265c fix(schwab-bundle-C): Codex R1 Major #3 — persist ladder windows to Shape A archive
bfa3d81 fix(schwab-bundle-C): Codex R1 Major #5 — ACCEPT-WITH-RATIONALE: _step_charts ...
3663d2c fix(schwab-bundle-C): Codex R1 Major #6 — sentinels emitted INSIDE schwabdev call
0682292 fix(schwab-bundle-C): Codex R1 Minor #1 + #2 — pin Parameter.kind + ...
26efbae fix(schwab-bundle-C): Codex R2 Major #1 — copy-not-move legacy parquet migration
37faad1 fix(schwab-bundle-C): Codex R2 Major #2 — merge-by-asof_date write semantics
98ad9b7 fix(schwab-bundle-C): Codex R2 Minor #1 — promote _normalize_legacy_dataframe ...
ab25142 fix(schwab-bundle-C): Codex R2 Minor #2 — clarify sandbox persistence test docstring
c67ed29 fix(schwab-bundle-C): Codex R3 Major #1 — mtime-based freshness winner in ...
539c782 fix(schwab-bundle-C): Codex R3 Minor #1 — normalize OHLCV column casing on ...
9cf55f3 fix(schwab-bundle-C): Codex R3 Minor #2 — write_window type-guard non-DataFrame ...
eaf8fd7 fix(schwab-bundle-C): Codex R4 Major #1 — ACCEPT-WITH-RATIONALE: file-level mtime ...
9e15b09 fix(schwab-bundle-C): Codex R4 Minor #1 — restore case-insensitive OHLCV column ...
5f658d7 fix(schwab-bundle-C): Codex R4 Minor #2 — use st_mtime_ns for nanosecond-precision ...
```

**Breakdown by class:**
- **1 recon-doc commit** (T-C.0.b)
- **7 task-impl commits** (T-C.1..T-C.7; one commit per task)
- **17 Codex-fix commits** (7 R1 + 4 R2 + 3 R3 + 3 R4)
- **0 return-report commits** (this doc is the 26th when committed)

NO `--no-verify`; NO `--amend`; NO co-author footer used.

---

## §2 Codex round chain

**5 rounds total → NO_NEW_CRITICAL_MAJOR convergent tapering:**

| Round | Critical | Major | Minor | Verdict |
|---|---:|---:|---:|---|
| R1 | 0 | 6 | 2 | ISSUES_FOUND |
| R2 | 0 | 2 | 2 | ISSUES_FOUND |
| R3 | 0 | 1 | 2 | ISSUES_FOUND |
| R4 | 0 | 1 | 2 | ISSUES_FOUND |
| **R5** | **0** | **0** | **2** | **NO_NEW_CRITICAL_MAJOR** |

**Monotonic Major decrease:** 6 → 2 → 1 → 1 → 0 (tapering convergent shape; matches Phase 9 + 10 + Sub-bundle A + B precedent for 4-5 round convergence on substantial-scope bundles).

**ZERO Critical findings entire chain.**

**ACCEPT-WITH-RATIONALE positions banked: 2**
- **R1 M#5:** `_step_charts` ladder wiring deferred to V2 (Schwab bars persist to `{TICKER}.schwab_api.parquet`; `read_or_fetch_archive` still on legacy path; explicit wiring requires `fetcher.get()` refactor + weekly-refresh semantic reconciliation).
- **R4 M#1:** File-level mtime as row-level conflict signal is V1 best-effort. The mtime-pick (R3 M#1 fix) solved stale-Shape-A under legacy refresh but introduces the inverse failure: partial legacy refresh rolls back newer Shape A values for untouched rows. V2 per-row `recorded_at` column closes BOTH directions.

**All other Critical+Major findings resolved with code-content fixes + discriminating regression tests** (5 R1 + 2 R2 + 1 R3 + 0 R4 = 8 Major fully resolved across 5 rounds).

**Minor findings: 11 total** (2 R1 + 2 R2 + 2 R3 + 2 R4 + 2 R5 + 1 R2 cross-bundle); 9 resolved in-tree; 2 R5 remain advisory (see §7 watch items).

---

## §3 Test count + ruff delta + schema delta

**Test count delta:** **+87 fast tests from task-impl + +33 from Codex chain = +120 cumulative** (worktree-side baseline pre-dispatch 3593 → final 3713; matches A/B overshoot precedent vs brief's +68 projection).

- T-C.1: +15 (12 body + 3 signature pins)
- T-C.2: +19 (+1 above plan; sanity-check on `_SOURCE_PRECEDENCE_MARKET_DATA`)
- T-C.3: +15 (+1 above plan; defense-in-depth `schwab_client=None`)
- T-C.4: +13 (+3 above plan; OhlcvBundle.provider validator + dataclass defaults regression)
- T-C.5: +12 + 1 un-skipped cross-bundle pin = +13 effective
- T-C.6: +8 (+4 above plan; step-signature regression + None-client + None-cache + step-ordering grep)
- T-C.7: +4 (matches plan)
- Codex R1 fixes: +16
- Codex R2 fixes: +6
- Codex R3 fixes: +6
- Codex R4 fixes: +6

**Final fast-suite state:** **3713 passed, 5 skipped, 3 failed** (~77s wall-clock under `-n auto`).

**Pre-existing failures (4 confirmed pre-existing on main `8356b34`; NOT regressions):**
1. `tests/integration/test_phase8_pipeline_walkthrough.py::test_phase8_pipeline_emits_snapshots_for_open_trades_only` — "archive returned None"; banked at CLAUDE.md Bundle 3 entry.
2. `tests/integration/test_phase8_pipeline_walkthrough.py::test_phase8_pipeline_second_same_day_run_upserts` — same family.
3. `tests/integration/test_phase8_pipeline_walkthrough.py::test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id` — same family.
4. `tests/integrations/test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction` — verified pre-existing on `8356b34` via baseline stash check (xdist-flaky behavior; intermittent under `-n auto`; deterministic-fails serial). Dispatch brief §0.7 stated "3 pre-existing failures" — actual baseline is **4**. Brief-data correction; not a regression.

**Ruff baseline:** 18 E501 errors **unchanged** (matches CLAUDE.md `Ruff baseline 18` invariant). No new E501; no new violations of any other class introduced.

**Schema version:** **v17 unchanged** (Sub-bundle C is consumer-side only per dispatch brief §0.7).

---

## §4 Operator-witnessed verification surfaces

Per dispatch brief §3 surface table. **Total: 9 surfaces** (4 operator-driven + 5 inline). **Operator-driven gate budget: 4 — within 6-surface budget.**

| # | Surface | Type | Status |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | **PASS** — 3713 passed; 3 pre-existing Phase 8 failures unchanged; 5 skipped; 1 xdist-flaky setup test (pre-existing). 0 cross-bundle pins remaining (T-C.5 + T-C.7 un-skipped). |
| **S2** | `swing schwab fetch --verify-marketdata` against production | **PENDING — operator-driven** | Verify: pipeline-active check passes; ladder issues `quotes` + `price_history` calls against live Schwab; `schwab_api_calls` audit rows INSERTED (endpoints `marketdata.quotes` + `marketdata.price_history`); `linked_snapshot_id=NULL` + `linked_reconciliation_run_id=NULL`; ZERO rows added to `account_equity_snapshots` / `reconciliation_runs`. |
| **S3** | `swing schwab fetch --verify-marketdata --environment sandbox` | **PENDING — operator-driven** | Per implementer disposition (T-C.5 D1 banked): `--verify-marketdata` invokes schwabdev under BOTH envs; sandbox-vs-prod difference is "which tokens DB to load." Sandbox produces ordinary `success`/`error` audit rows; no cache writes. Cache-writes-SKIPPED-regardless-of-env contract holds. |
| **S4** | Pipeline run with ladder enabled (production env) | **PENDING — operator-driven** | Run `swing pipeline run` against production; verify ladder fires through `_step_evaluate` (via `_warm_pipeline_marketdata`); cache hit rate observable; `schwab_api_calls` audit rows accumulate with `surface='pipeline'`; on-disk parquet at `swing-data/ohlcv-archive/{TICKER}.schwab_api.parquet` + `{TICKER}.yfinance.parquet` present + non-empty for at least one open-trade ticker. **NOTE:** `_step_charts` does NOT consume the ladder (M#5 R1 ACCEPT-WITH-RATIONALE). |
| **S5** | Backward-compat copy-not-move (operator's actual archive dir) | **PENDING — operator-driven** | Verify: post-merge first cache read for any historical ticker triggers `_backward_compat_rename` (one-shot per ticker; idempotent); pre-existing `{TICKER}.parquet` **STAYS IN PLACE** (copy-not-move per R2 M#1 fix); `{TICKER}.yfinance.parquet` created alongside with Shape A normalization. No data loss; both files coexist during V1. |
| **S6** | Sentinel-token-leak audit Bundle C coverage | Inline | **PASS** — `pytest tests/integrations/test_schwab_token_redaction_audit.py -v` green; un-skipped Market Data API portions covered + 2 new tests using `MagicMock.side_effect` emitting Schwabdev-logger sentinels FROM INSIDE actual `quotes`/`price_history` calls (R1 M#6 fix discriminating against pre-fix BEFORE-the-call pattern). |
| **S7** | `SchwabPipelineActiveError` exclusion (un-skipped --verify-marketdata) | Inline | **PASS** — `pytest tests/integrations/test_schwab_pipeline_active_exclusion.py::test_b6_10_fetch_verify_marketdata_NOT_protected -v` green; un-skipped at T-C.5; verifies `--verify-marketdata` is in the 3-safe-subcommands list (does NOT raise SchwabPipelineActiveError even when a pipeline is running). |
| **S8** | E2E pipeline run with ladder | Inline | **PASS** — `pytest tests/integration/test_schwab_pipeline_production_only_gate.py -v` green; Bundle B-shipped suite unchanged by Sub-bundle C (cache-layer integration does NOT regress). Ladder injection via `_install_pipeline_marketdata_caches` + `_warm_pipeline_marketdata` integration tests in `tests/integration/test_pipeline_marketdata_ladder_integration.py` (T-C.6; +8 tests). |
| **S9** | ruff baseline | Inline | **PASS** — `ruff check swing/ --statistics` reports **18 E501 unchanged**. |

**Production state post-gate:** S2-S5 add fresh `schwab_api_calls` audit rows for `marketdata.quotes` + `marketdata.price_history` endpoints + ladder activity through `_step_evaluate`. Cache files at `swing-data/ohlcv-archive/{TICKER}.schwab_api.parquet` + `{TICKER}.yfinance.parquet` populated. ZERO domain rows added (no `account_equity_snapshots`/`reconciliation_runs` writes from C).

**Production-write classifier soft-block awareness:** S2-S4 issue calls that WRITE to `schwab_api_calls`. Operator pre-authorizes via gate-path; production-write classifier may surface as soft-block — operator says "yes" in plain chat to proceed.

---

## §5 Per-task deviations from plan

**18 banked deviations total across T-C.1..T-C.7 (8 cosmetic + 6 architectural + 4 scope).**

### T-C.1 (3 deviations)
- **D1 (cosmetic):** `get_quotes_batch(fields: str | None = None)` accepts an explicit `fields` kwarg (plan §E.3 omitted it). Forward-compat for V2 callers wanting `fields="quote"` or `"fundamental"`. Passing `None` matches schwabdev's default per `api-calls.md` L309.
- **D2 (cosmetic):** New `OhlcvBar` dataclass added at `swing/integrations/schwab/models.py` (plan §H.7 implied existence; recon doc §3.3 anticipated). Validators enforce per-bar invariants (low ≤ min(open,close); high ≥ max(open,close); volume ≥ 0).
- **D3 (architectural):** `_finish_hook` parameter on `_call_endpoint` is marketdata-local (Trader's `_call_endpoint` doesn't have this seam). Supports quotes partial-response audit messaging (success path with partial-failure-detail).

### T-C.2 (3 deviations)
- **D1 (cosmetic):** `cache_dir` kwarg threaded through `write_window` / `resolve_ohlcv_window` / `_backward_compat_rename` instead of module-level `ARCHIVE_DIR` const (plan §H.6.3 pseudocode). Matches existing `read_or_fetch_archive` API + project pattern of plumbing `cfg.paths.prices_cache_dir`.
- **D2 (cosmetic):** `write_window` accepts `pd.DataFrame | None` directly (plan pseudocode had `.to_dataframe()` call). M#4 R1 fix later added `SchwabPriceHistoryWindow.to_dataframe()` for the cache hook surface; persistence path receives DataFrames directly from helpers.
- **D3 (cosmetic):** `resolve_ohlcv_window` uses keyword-only `start` / `end` / `cache_dir` params for clarity at call sites (plan pseudocode positional).

### T-C.3 (5 deviations)
- **D1 (scope; affects T-C.4):** `PriceSnapshot.provider` field added in T-C.3 via Option A (plan put it under T-C.4). T-C.4 scope reduced; T-C.4 D1 architectural deviation (injectable fetcher hook) lands on top.
- **D2 (architectural):** Ladder signatures take `conn` + `surface` kwargs (plan §H.6.1+§H.6.2 pseudocode omits them; T-C.1 wrappers require them for audit-lifecycle bookkeeping).
- **D3 (architectural):** 401 (auth failure) treated as plain failure → yfinance fallback (no auto-refresh retry). Simpler interpretation; schwabdev handles 401 auto-refresh internally if it can; ladder does NOT double-handle.
- **D4 (cosmetic):** Ticker validation BEFORE env/ladder branching (defense-in-depth; rejects empty/None/non-string tickers with ValueError before any other logic).
- **D5 (cosmetic):** 15th defense-in-depth test beyond plan's +14 for `schwab_client=None` production fall-through.

### T-C.4 (2 deviations)
- **D1 (architectural):** Cache layer uses INJECTABLE FETCHER HOOK pattern (`PriceCache.set_ladder_fetcher` + `OhlcvCache.set_ladder_bars_fetcher`) instead of plan's direct wrapping. Rationale: cache doesn't need to know about `conn`/`surface`/`schwab_client`; threading those through every test fixture would force every existing test to construct stubs. The hook pattern keeps callers responsible for ladder composition + lets the cache stay env-agnostic. T-C.5 (CLI) + T-C.6 (pipeline) install the fetcher.
- **D2 (cosmetic):** `OhlcvBundle.provider` validator additionally surfaced (mirrors `PriceSnapshot.provider` defense-in-depth per Sub-bundle A + B __post_init__ discipline).

### T-C.5 (3 deviations)
- **D1 (scope; orchestrator-decision):** Sandbox-vs-production disposition interpretation (b) — `--verify-marketdata` invokes schwabdev endpoints under BOTH envs; sandbox-vs-prod difference is "which tokens DB is loaded." Document for orchestrator to lock in Sub-bundle D.
- **D2 (cosmetic):** `price_history` invoked on FIRST symbol only (default AAPL when omitted). Matches schwabdev's one-symbol-per-call contract; verification scope is the endpoint surface, not multi-symbol price-history coverage.
- **D3 (cosmetic):** Added 2 defense-in-depth tests beyond the 6 listed (c5_06b 429 rate-limit + c5_07 empty-symbols rejection).

### T-C.6 (3 deviations)
- **D1 (architectural; V1 limitation):** `_construct_pipeline_schwab_client(cfg)` returns `None` by default. `construct_authenticated_client(cfg, environment)` requires `client_id` + `client_secret` arguments which are NOT stored in cfg (sensitive — only operator-prompt in CLI). V1 design: pipeline can't prompt; gracefully degrades to yfinance-only. Tests inject mock client directly. **V2 enhancement banked:** read from env vars (`SWING_SCHWAB_CLIENT_ID`) or operator-supplied path.
- **D2 (cosmetic; V2 wiring point):** OhlcvCache hook constructed-but-unused by `_step_evaluate` warm path. OhlcvCache hook exercised by unit tests via direct invocation; V2 wiring of the pipeline's bars path through the ladder is a one-line addition.
- **D3 (architectural):** `_warm_pipeline_marketdata` is a NEW helper (not "minimal adjustment to existing call boundary"). Helper-extraction for testability + clarity; the call site in `_step_evaluate` is one line.

---

## §6 Codex Major findings ACCEPTED with rationale

**2 ACCEPT-WITH-RATIONALE positions across the chain (vs Sub-bundle A: 1; Sub-bundle B: 1; Phase 10 arc: 0 — matches arc precedent).**

### §6.1 R1 M#5 — `_step_charts` ladder wiring deferred to V2

**Commit:** `bfa3d81`

**Codex finding:** `_step_charts` is not wired through the OhlcvCache market-data ladder. The runner constructs `_ohlcv_cache` but discards it; `_step_charts` retains the old `read_or_fetch_archive` legacy path.

**Rationale for ACCEPT:**
- `_step_charts` consumes OHLCV via `fetcher.get()` → `read_or_fetch_archive` (legacy path).
- Post R1 M#3 fix (Schwab bars persist to `{TICKER}.schwab_api.parquet`), the Shape A archive is now populated by the ladder, but `read_or_fetch_archive` doesn't consult Shape A files.
- Full wiring requires refactor of `fetcher.get()` weekly-refresh + `archive_history_days` semantics + in-memory shape reconciliation + OhlcvCache lifecycle threading.
- V1 behavior unchanged for chart-step downstream consumers; Sub-bundle C ships the Schwab archive infrastructure + V2 read-path extension closes the chart-step ladder integration.
- Banked V2 candidate (§7 #1): "`read_or_fetch_archive` Shape A read-path extension — transparent Schwab provenance to chart step."

**Documentation-only commit; no production behavior change.**

### §6.2 R4 M#1 — File-level mtime as row-level conflict signal is V1 best-effort

**Commit:** `eaf8fd7`

**Codex finding:** `_backward_compat_rename` both-exist merge uses FILE-LEVEL mtime to choose the winner for EVERY overlapping `asof_date`. If legacy file is touched by a partial refresh, file-level mtime becomes newer + ALL date conflicts let legacy win — rolling back newer Shape A values for rows the partial refresh didn't actually update.

**Rationale for ACCEPT:**
- The R3 M#1 fix (mtime-based winner) solved the inverse failure (stale-Shape-A under legacy refresh) reported in R3.
- R4 M#1 surfaces that file-level mtime is fundamentally a coarse signal for a row-level conflict question.
- Under V1, the impact is BOUNDED:
  - `read_or_fetch_archive` consumers read legacy directly — Shape A merge state does NOT affect their reads.
  - Shape A consumers (Sub-bundle C ladder + Phase 10 metrics if any) see a deterministic merge state that may diverge from per-row truth.
- V2 resolves BOTH directions by adding a per-row `recorded_at` column to both archives; merge picks per-row winner by `recorded_at` not file-mtime.
- Banked V2 candidate (§7 #7): "Per-row `recorded_at` column as freshness signal alternative to filesystem mtime — closes both staleness + rollback."

**Documentation comment added inline at `swing/data/ohlcv_archive.py:_backward_compat_rename` both-exist branch acknowledging the V1 trade-off + inverse-rollback failure mode explicitly.**

---

## §7 Watch items for orchestrator (cross-bundle pins; V2 candidates)

### §7.1 Cross-bundle pins UN-SKIPPED at Sub-bundle C ship

- `tests/integrations/test_schwab_pipeline_active_exclusion.py:test_b6_10_fetch_verify_marketdata_NOT_protected` — un-skipped at T-C.5 (`4b261d4`). Verifies `--verify-marketdata` does NOT raise `SchwabPipelineActiveError` when a pipeline is running. **GREEN.**
- `tests/integrations/test_schwab_token_redaction_audit.py` cross-bundle pin at line 1161 region — un-skipped at T-C.7 (`13edfd7`); pre-existing skipped test replaced with 4 new Market Data API sentinel-coverage tests + 2 R1 M#6 fix tests using `MagicMock.side_effect`. **GREEN.**

**0 cross-bundle pins remaining for Sub-bundle D.**

### §7.2 V2 candidates banked (7 total)

1. **`_step_charts` ladder wiring** (R1 M#5 follow-up) — explicit `_step_charts` consumption of `OhlcvCache.get_window(...)` or `resolve_ohlcv_window` directly; would close the chart-step Schwab-provenance gap.
2. **`read_or_fetch_archive` Shape A read-path extension** — extend the legacy reader to consult `{TICKER}.schwab_api.parquet` via `resolve_ohlcv_window` semantics; transparent Schwab provenance for chart step. Closes M#5 R1 path A.
3. **`empty_flag is True` pattern review** across other JSON-boolean Schwab response flags — defense-in-depth pattern; grep `bool(response.get(` across `mappers.py` for similar coercion sites (R1 m#2).
4. **`_yfinance_window_to_shape_a_df` heuristic conversion** → explicit fallback contract — current best-effort returns None on ambiguous shapes; V2 could narrow with explicit type-hint contracts. The yfinance fallback callable type annotation surface bears reviewing.
5. **Legacy parquet cleanup pass** (R2 M#1 docstring) — when all consumers of `read_or_fetch_archive` (`swing/prices.py`, `swing/pipeline/ohlcv.py`, `swing/trades/daily_management.py`) are refactored to consume the Shape A resolver, V2 can drop the legacy parquet via `os.remove(old_path)` in a one-shot cleanup pass.
6. **REPLACE-mode `write_window`** for explicit archive reset (R2 M#2 docstring) — operator-driven "reset archive" path; would need a `force_replace: bool = False` flag or new function. Current merge semantics intentionally never blank existing content.
7. **Per-row `recorded_at` column** as freshness signal alternative to filesystem mtime (R3 M#1 + R4 M#1) — closes BOTH directions of failure: (a) staleness-on-Shape-A and (b) rollback-on-partial-legacy. Filesystem-mtime-precision-independent. Replaces file-level mtime pick with per-row freshness comparison.

### §7.3 Operator-decision items pending for Sub-bundle D dispatch

- **Sandbox-vs-production disposition for `--verify-marketdata`** (T-C.5 D1) — interpretation (b) shipped: both envs invoke schwabdev; only tokens DB differs. Orchestrator may want to revisit at Sub-bundle D `swing schwab status` full-surface scope (per dispatch brief §8).
- **Pipeline schwab_client construction** (T-C.6 D1) — V1 returns `None` because cfg doesn't carry `client_id`/`client_secret`. V2 enhancement: env var (`SWING_SCHWAB_CLIENT_ID`) or operator-supplied path; banked at Sub-bundle D triage.

### §7.4 R5 Minor advisory (2 items not addressed inline)

1. **`normalize_legacy_dataframe` duplicate-canonical column collision** — when a frame contains both canonical and noncanonical variants (e.g., `close` and `CLOSE`), the rename `CLOSE -> close` would produce duplicate `close` columns. Could make parquet writes fail or downstream row access ambiguous. **Mitigation:** Real-world Sub-bundle C consumers don't construct such mixed-case frames; defense-in-depth banking for future broker-API mappers that may emit mixed-case responses. V2 hardening or Sub-bundle D code-review absorb point.
2. **Nanosecond-precision probe test could falsely accept whole-second-rounding filesystem** — `_filesystem_supports_ns_mtime` stamps `...500_000_000` ns + accepts any delta `< 1_000_000_000`; a filesystem rounding to either adjacent whole second can differ by `500_000_000` ns and still report as nanosecond-capable. Test-only; tighten with `actual_ns % 1_000_000_000 != 0` assertion. Sub-bundle D code-review absorb point.

---

## §8 Worktree teardown status

**Expected ACL-locked husk per Phase 6/7/8/9/10/Sub-A/Sub-B precedent.** Branch `schwab-bundle-C-marketdata-and-cache-ladder` will be DELETED post-integration-merge by the orchestrator. The on-disk worktree directory `.worktrees/schwab-bundle-C-marketdata-and-cache-ladder/` becomes a still-registered husk until cleared by `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (post-Phase-10 infrastructure bundle SHIPPED 2026-05-13 at `27ce96f` introduced the `-DeregisterFirst` switch).

**Marker file** `c:\Users\rwsmy\swing-trading\.copowers-subagent-active` will be REMOVED by the orchestrator before final integration merge per dispatch brief §1.2.

---

## §9 Sub-bundle D forward-binding lessons (BINDING for Sub-bundle D dispatch)

**5 lessons newly surfaced during Sub-bundle C executing-plans for Sub-bundle D inheritance:**

1. **camelCase kwarg signature pinning DISCRIMINATING-test pattern is BINDING for any future schwabdev call surface.** The pre-emption (R1 #1) caught zero defects on `price_history` thanks to `inspect.signature` test landing before code; pin `Parameter.kind ∈ {POSITIONAL_OR_KEYWORD, KEYWORD_ONLY}` + assert NO `VAR_KEYWORD` parameter (R4 m#1 fix added the kind check). Sub-bundle D's `swing schwab status` consumes Sub-bundle A's `account_linked` + Sub-bundle B's `account_details` — both already signature-pinned, but ANY new schwabdev call surface MUST add a similar signature-pin test FIRST per task.

2. **Dual empty-signal check (`len(...)==0` OR `body.get(field) is True`) defense-in-depth pattern.** `price_history` empty-bars mapper consults BOTH `len(candles)==0` AND `empty=True` per spec §E.5 + §H.6.4. R1 m#2 caught `bool(response.get("empty", False))` would treat string `"false"` as empty; fix uses `is True`. Sub-bundle D briefing.md degraded-banner emission predicate (per spec §3.4.4) should mirror this pattern when reading the latest `schwab_api_calls.status` row.

3. **Injectable fetcher hook architectural pattern** (T-C.4 D1) — when an integration adds a NEW dimension (provider, source, status) to an EXISTING cache/service, prefer hook injection over direct wrapping. Keeps the cache env-agnostic; threading auth/conn/surface through callers avoids fixture-rewrite cascades. Sub-bundle D may need to surface ladder-call counts in `swing schwab status` — read from `schwab_api_calls` audit table (NOT from cache hooks; status is per-call audit metadata).

4. **Mtime-based freshness winner is V1 BEST-EFFORT for cross-source merge conflicts; per-row recorded_at column closes both directions for V2.** Banked as V2 candidate #7. Sub-bundle D may not touch this surface, but ANY future cross-source merge (e.g., reconciliation between Schwab API account_orders + TOS CSV imports) should pre-empt with explicit per-row freshness metadata.

5. **`construct_authenticated_client(cfg, environment, client_id, client_secret)` requires sensitive secrets NOT in cfg** (T-C.6 D1). V1 pipeline cannot prompt; gracefully degrades. Sub-bundle D `swing schwab status` runs in CLI surface where prompting is possible; status surface MUST handle the "tokens-present, no-secrets-available" case (e.g., display `<auth: tokens-only>` vs `<auth: full-creds>`).

---

## §10 Composition-surface verification

Per dispatch brief §4.1 / §5 + Phase 9-10 forward-binding lesson on `^def` grep enumeration.

**`grep -rn "^def" swing/integrations/schwab/marketdata.py`** (T-C.1 new file):

- `_call_endpoint` (line ~108) — shared wrapper
- `get_quotes_batch` (line ~263) — public API
- `get_price_history` (line ~365) — public API
- Plus 4 helpers (`_compute_quotes_signature_hash`, `_compute_price_history_signature_hash`, `_redacted_excerpt`, `_resolve_marketdata_logger`)

**`grep -rn "^def" swing/integrations/schwab/marketdata_ladder.py`** (T-C.3 new file):

- `fetch_quote_via_ladder` (public API)
- `fetch_window_via_ladder` (public API)
- Plus 7 helpers (`_resolve_cache_dir`, `_schwab_window_to_shape_a_df`, `_yfinance_window_to_shape_a_df`, `_persist_window_to_archive`, `_is_ladder_active`, `_log`, etc.)

**`grep -rn "^def" swing/data/ohlcv_archive.py` (extended by T-C.2 + R1+R2+R3+R4 fixes):**

- `write_window` (extended; M#2 R2 merge semantics + R3 m#2 type-guard)
- `resolve_ohlcv_window` (NEW; window-filter step per R1 #4)
- `_backward_compat_rename` (NEW; copy-not-move per R2 M#1 + mtime winner per R3 M#1 + nanosecond precision per R4 m#2)
- `normalize_legacy_dataframe` (PROMOTED from `_normalize_legacy_dataframe` per R2 m#1; case-insensitive OHLCV per R4 m#1)
- `_normalize_ohlcv_column_case` (NEW helper; R3 m#1 + R4 m#1)
- `_file_mtime_ns` (NEW; R4 m#2)
- Plus pre-existing: `read_or_fetch_archive`, `_archive_paths`, `_atomic_parquet_write`, `_persist_archive_atomic`, etc.

**Single-Client-instance discipline (NO `schwabdev.Client(` instantiation):** verified at §13 below.

---

## §11 T-C.0.b operator-paired session observations

**Phase 1 = COMPLETE** at `9d1e3e4` (recon doc `docs/schwab-bundle-C-task-C0b-recon.md`).

**Phase 2 = DEFERRED** to operator-paired post-merge session per dispatch brief §2 fallback path. Operator unavailable during this dispatch; T-C.1 + T-C.2 + T-C.4 + T-C.7 ship on Phase-1 pre-check authority. T-C.3 + T-C.5 + T-C.6 ship with mocked schwabdev test fixtures; cassette-driven LIVE acceptance criteria fold in at operator-paired gate post-merge.

**Phase 1 pre-check observations (recon doc §1-§4):**

1. **`quotes` kwargs are ALL snake_case** (`symbols`, `fields`, `indicative`) — SAFE from Sub-bundle-B camelCase trap family.
2. **`price_history` kwargs are CAMELCASE on EVERY non-positional param** — same defect family as Sub-bundle B `34be84e` gate-catch. Pre-empted via `inspect.signature` discriminating test at T-C.1.
3. **`startDate`/`endDate` accept `datetime | int | None` (epoch ms)** — NOT ISO-string. `_schwab_iso` helper from Sub-bundle B `trader.py` is NOT applicable; pass `datetime` directly.
4. **`price_history` response shape** `{"candles": [...], "symbol": ..., "empty": bool}` — Schwab explicitly returns `empty: bool` field. Mapper consults BOTH `len(candles)==0` AND `empty=True` per spec §E.5.
5. **`quotes` partial-response** surfaces as error envelope under symbol key. Mapper splits per spec §E.4: emit `SchwabQuoteResponse` per OK symbol; mark failed for yfinance fallback.

**Plan §E.3 amendments banked at recon doc §5 (5 items; routed for V2.1 §VII.F amendment channel):**

- §5.A: `price_history` camelCase kwarg surface — CRITICAL (same family as B `34be84e`).
- §5.B: `price_history` datetime datatype permissiveness — cosmetic.
- §5.C: `PriceCacheEntry` → actual `PriceSnapshot` class name — CRITICAL plan-implementation drift.
- §5.D: `swing/data/ohlcv_cache.py` → actual `swing/web/ohlcv_cache.py` — path-binding drift.
- §5.E: `OhlcvCacheEntry` dataclass existence not verifiable at recon — implementer at T-C.4 determined extends-or-creates per actual code shape.

**Phase 2 LIVE observations still pending (recon doc §6):** 8 items requiring operator-paired live Market Data API calls — `quotes` per-symbol field names + delayed flag presence + quote-time field shape + `price_history` candle datetime + `empty=true` triggering + partial-response envelope shape + `X-RateLimit-Remaining` header + Q12 default-tier delay magnitude. Folded into operator-paired post-merge cassette-recording session.

---

## §12 `reference/schwab-api/` + `reference/schwabdev/` distilled refs consumed during T-C.0.b

**Consumed verbatim during Phase 1 recon:**

- `reference/schwabdev/api-calls.md` L296-440 — verbatim signatures + response shapes for `quotes` (L296-314) + `price_history` (L407-440). Rate limits L314 + L439 (120 req/min for both).
- `reference/schwabdev/client.md` — threading model + rate-limit doctrine + verbatim "Do NOT use in loops — use streaming instead" warnings on both methods at L255-265.
- `reference/schwab-api/market-data-{documentation,specification}.md` — these describe Schwab's **streaming** services (WebSocket LEVELONE, BOOK, CHART, SCREENER, ACCOUNT) — out-of-scope for Sub-bundle C REST consumption per spec §1.4 + Q4 V2-fence on streaming. Consulted only for cross-reference of symbol semantics + rate-limit conventions.

**Pre-checked from refs (no live verification needed):**
- `quotes` signature + return shape + rate limits.
- `price_history` signature + return shape + rate limits.
- Both methods return `requests.Response`; wrapper calls `.json()` + verifies HTTP status.
- 120 req/min for both.

---

## §13 Single-Client-instance discipline verification

Per dispatch brief §0.6 + pre-emption #4 + Sub-bundle B forward-binding lesson #3.

**`grep -rn "schwabdev.Client(" swing/integrations/schwab/marketdata.py swing/integrations/schwab/marketdata_ladder.py`** returns **0 matches** (verified at every Codex round).

**Centralized instantiation site:** `swing/integrations/schwab/auth.py:construct_authenticated_client(cfg, environment)` (extracted in Sub-bundle B `e61d735`). Sub-bundle C consumes the SchwabClient from callers (CLI surface via T-C.5; pipeline via T-C.6 `_construct_pipeline_schwab_client(cfg)` which returns `None` per V1 design — see T-C.6 D1 banked).

**Discipline lock satisfied across both new files.**

---

## §14 Cross-bundle pin un-skip status

**Both cross-bundle pins UN-SKIPPED at Sub-bundle C ship; both tests PASSING.**

| Pin | Source | Un-skip task | Status |
|---|---|---|---|
| `tests/integrations/test_schwab_pipeline_active_exclusion.py:257` (`test_b6_10_fetch_verify_marketdata_NOT_protected`) | Sub-bundle B left SKIPPED stub awaiting T-C.5 | T-C.5 (`4b261d4`) | **GREEN** |
| `tests/integrations/test_schwab_token_redaction_audit.py:1161` region (cross-bundle Market Data sentinel-coverage) | Sub-bundle A T-A.10 left SKIPPED awaiting Market Data API cassettes | T-C.7 (`13edfd7`) + R1 M#6 fix at `3663d2c` | **GREEN** |

**0 cross-bundle pins remaining for Sub-bundle D.**

---

**End of return report.** Implementer hands off to orchestrator for:
1. Integration merge to main (no `--ff` per Sub-bundle B precedent → preserves Codex-fix chain visibility).
2. Operator-driven gate surfaces S2-S5 (4 surfaces; production-write classifier soft-block awareness; ~6-surface budget consumed at 4).
3. Sub-bundle D dispatch commissioning post-Sub-bundle-C-ship (CLOSES the arc; per dispatch brief §8 + §9 + plan §Tasks-D).

**Sub-bundle D dispatch UNBLOCKED post-Sub-bundle-C-ship.** D closes the arc (Phase 11 hand-off + briefing.md banner + cycle-checklist + CLAUDE.md gotchas + E2E happy-path).
