# Schwab API Sub-bundle C — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance dispatched as the Schwab API Sub-bundle C executing-plans implementer. No prior conversation context.

**Mission:** Execute Sub-bundle C of the Schwab API integration plan via `copowers:executing-plans`. Sub-bundle C wires **Market Data API consumption** + **Shape A market-data ladder** (parquet-per-(ticker, provider)) + **`PriceCache` / `OhlcvCache` integration** + **sandbox short-circuit** + **`swing schwab fetch --verify-marketdata` CLI subcommand** + **un-skip the last cross-bundle pin** for Market Data audit coverage. Lands on a worktree branch; orchestrator owns integration merge to main post-operator-witnessed-gate.

**Expected duration:** ~8-12 hr including ~4-5 Codex rounds. Per plan §0.4 estimate (largest novel scope of the arc — cache architecture rewrite + new resolver + new ladder + backward-compat migration). 8 tasks (T-C.0.b..T-C.7); +68 fast tests projected.

---

## §0 Inputs

### §0.1 Plan (canonical scope source)

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- **SUB_BUNDLE:** `C` (Tasks T-C.0.b..T-C.7 inclusive).
- **Plan Sub-bundle C section:** §Tasks-C at line 2130+ (per-task scope + acceptance criteria + discriminating-test patterns + commit message stems).
- **Algorithmic anchors:** §A.8 Shape A LOCK (parquet-per-(ticker, provider)) + §E.3-§E.5 (Market Data API endpoints + partial-response + empty-bars transient) + §H.6.1-§H.6.4 (ladder algorithms + Shape A persistence + empty-response transient) + §H.7 (dataclass `__post_init__` validators).

### §0.2 Sub-bundle A + B SHIPPED context (BINDING)

- **A merged at `5b6e5ba`** (2026-05-14; --no-ff preserved Codex-fix chain). 4 Codex rounds; 1 ACCEPT-WITH-RATIONALE banked.
- **B merged at `df29232`** (2026-05-14; --no-ff). 5 Codex rounds + 1 orchestrator-inline gate-caught fix at `34be84e` (camelCase kwarg defect on `Client.account_orders` — see §0.5 below). 1 ACCEPT-WITH-RATIONALE family banked (lease status fields V2-deferred).
- **Sub-bundle A return report:** `docs/schwab-bundle-A-return-report.md` (`6550494`) — READ §6 + §8 (5 forward-binding lessons) + §12.
- **Sub-bundle A T-A.0.b recon:** `docs/schwab-bundle-A-task-A0b-recon.md` — READ §6 + §6.bis as LOCKED inputs.
- **Sub-bundle B return report:** `docs/schwab-bundle-B-return-report.md` (`0124a76`) — READ §7 (orchestrator watch items) + §9 (7 forward-binding lessons specifically for Sub-bundle C).
- **Sub-bundle B T-B.0.b recon:** `docs/schwab-bundle-B-task-B0b-recon.md` — READ §2 + §5 (5 plan deviations banked V2.1 §VII.F).
- **Sub-bundle B executing-plans dispatch brief:** `docs/schwab-bundle-B-executing-plans-dispatch-brief.md` (`19622b6`) — format precedent for this brief.

### §0.3 BINDING distilled references (HARD §0 reads)

Both reference dirs are BINDING §0 reads:

- `reference/schwabdev/{setup-guide,examples,client,api-calls,streaming,orders,troubleshooting}.md` — schwabdev library docs (7 distilled MDs).
- `reference/schwab-api/{account,market-data}-{documentation,specification}.md` — Schwab Developer Portal canonical docs (4 distilled MDs).

**For Sub-bundle C specifically — pre-check FIRST before scheduling any operator-paired Task 0.b session:**

1. **`reference/schwabdev/api-calls.md`** — verbatim signatures for the 2 Market Data methods Sub-bundle C consumes:
   - `quotes(symbols=None, fields=None, indicative=False)` at L296-314 — **`symbols` is `list | str | None`; `fields` is `str | None` allowed values `"all"` (default) / `"quote"` / `"fundamental"`; `indicative: bool = False`. ALL snake_case kwargs — SAFE.**
   - `price_history(symbol, periodType=None, period=None, frequencyType=None, frequency=None, startDate=None, endDate=None, needExtendedHoursData=None, needPreviousClose=None)` at L407-440 — **`symbol` is positional snake_case; ALL OTHER KWARGS ARE camelCase: `periodType`, `period`, `frequencyType`, `frequency`, `startDate`, `endDate`, `needExtendedHoursData`, `needPreviousClose`. `startDate`/`endDate` accept `datetime` OR `int` (UNIX epoch ms). Returns `{"candles": [...], "symbol": ..., "empty": bool}` — **NOTE: Schwab explicitly returns `empty: bool` flag** (per plan §E.5 + §H.6.4 transient-empty handling, the `empty=True` path raises synthetic `SchwabApiError(204, "empty bars")` for ladder fallback).**
2. **`reference/schwabdev/client.md`** — rate limits 120 req/min for both `quotes` + `price_history` (verbatim "Do NOT use in loops — use streaming instead" warnings on both); 30-min access + 7-day refresh lifecycle.
3. **`reference/schwab-api/market-data-documentation.md` + `market-data-specification.md`** — Schwab's published Market Data API canonical docs. Higher fidelity than synthesized §E.3.
4. **`reference/schwabdev/troubleshooting.md`** — `unsupported_token_type` → `update_tokens(force_refresh_token=True)`. **Threading reminder for Sub-bundle D status alerts.**

### §0.4 Sub-bundle A + B forward-binding lessons (BINDING for Sub-bundle C)

**Sub-bundle A (5; per A return report §8 — still BINDING):**

1. **schwabdev silent-failure-mode discipline.** `Client.__init__` + `update_tokens()` do NOT raise on auth failure. Wrappers MUST verify post-call state. **Discriminating-test pattern:** stub schwabdev call to NOT mutate `tokens.access_token`; assert wrapper raises `SchwabAuthError` + audit row `status='auth_failed'`.
2. **Audit-success-fire ordering.** `record_call_finish(status='success', ...)` MUST fire ONLY after all validation passes. Pattern: validate response shape → validate response content → validate operator-pickable state → fire success audit.
3. **Pre-call factory-replacement defense.** `ensure_schwab_log_redaction_factory_installed()` (NOT `_install_*`) before every schwabdev API call.
4. **Redact-then-truncate audit-error ordering.** `_redacted_excerpt` MUST redact on FULL `str(exc)` THEN truncate to audit-column-budget.
5. **schwabdev 2.5.1 actual surfaces** (banked phase-2 live verification): 8-param `Client` ctor; JSON Tokens DB; `client.account_linked()` returns list-of-dicts on success / dict-error-envelope on failure; **logger name `"Schwabdev"` (capital S — live deviation from plan §H.8 lowercase)**; force-refresh kwarg is `force_access_token=True` (NOT `force_refresh_token`).

**Sub-bundle B (7 NEW; per B return report §9 — BINDING for Sub-bundle C):**

1. **Mapper resilience (Codex R1 M#9 in B).** Sub-bundle C's `marketdata.quotes` mapper MUST tolerate per-symbol error envelopes WITHOUT raising for the entire batch (per `api-calls.md` §E.4 partial-response handling). Pattern: log + skip the bad symbol, return successfully-mapped subset. Audit row records the per-symbol breakdown in `error_message` excerpt (no token bytes; no client_secret).
2. **Surface-aware advisory audit (Codex R3 M#1 in B).** Sub-bundle C's pipeline-step / CLI surface split MUST mirror Bundle B's pattern — `surface='pipeline'` = silent-skip on missing config (log only; NO audit row); `surface='cli'` = advisory audit row written. Avoids degraded-health surface pollution. Apply specifically to T-C.6 pipeline integration vs T-C.5 CLI.
3. **Single-Client-instance discipline (Codex R1 M#7 in B).** Sub-bundle C's `marketdata.py` MUST NOT instantiate `schwabdev.Client(...)` directly. Use the existing `construct_authenticated_client()` helper at `swing/integrations/schwab/auth.py` (extracted in Bundle B fix `e61d735`). **Discriminating-test pattern:** `grep -rn "schwabdev.Client(" swing/integrations/schwab/marketdata.py swing/integrations/schwab/marketdata_ladder.py` returns ZERO matches.
4. **Audit-success-fire ordering (M#3 family extends).** Sub-bundle C's `_call_endpoint()`-equivalent for market-data endpoints MUST fire `record_call_finish(status='success', ...)` ONLY AFTER ALL validation passes (mapper + dataclass `__post_init__` + post-call token-state check per Codex R1 M#4 in B).
5. **HTTP failure classification (Codex R1 M#3 in B).** Sub-bundle C MUST close audit rows on typed `SchwabApiError` subclasses with the correctly-classified status (`auth_failed` / `rate_limited` / `error`) BEFORE re-raising. The shared `_call_endpoint()` harness in Bundle B's `trader.py` is reusable verbatim; **Bundle C SHOULD consider extracting it to a shared module (e.g., `swing/integrations/schwab/_endpoint_call.py`) if duplication is significant** — leave the decision to the implementer based on actual code-shape after T-C.1.
6. **Datetime ISO formatting (`_schwab_iso` helper).** Bundle B's `_schwab_iso(dt)` helper at `trader.py` is reusable. **HOWEVER for `price_history`, schwabdev accepts `datetime` OR `int` (UNIX epoch ms)** — see §0.5 below for the camelCase + datatype trap. The `_schwab_iso` ISO-string form is NOT what `startDate`/`endDate` consume; pass `datetime` directly OR convert to `int(dt.timestamp() * 1000)`.
7. **Cash_movement_mismatch direction-ambiguous types (Codex R2 M#3 in B).** Pattern for future direction-ambiguous Schwab type matching — list in BOTH direction sets + disambiguate by sign at match time. **Forward-relevance to Sub-bundle C:** none expected (market-data is read-only; no transaction-type matching path).

### §0.5 Codex chain pre-emption table (extended for Sub-bundle C)

Sub-bundle A's 4 + Sub-bundle B's 5 Codex rounds caught these patterns; pre-empt in Sub-bundle C implementation BEFORE writing tests:

| Pattern family | A/B surface | Sub-bundle C applicability + pre-emption |
|---|---|---|
| **Silent-failure post-call validation** (A M#1 family) | `setup` + `force_refresh` + `accounts.linked` empty-list ordering | EVERY schwabdev call in `marketdata.py` (`quotes`, `price_history`) — wrap + verify post-call state. |
| **Audit-success-fire ordering** (A M#3 / B M#3 family) | `accounts.linked` empty-list logged success-then-error | EVERY `record_call_finish('success', ...)` MUST follow ALL validation passes (mapper output + dataclass `__post_init__` + token-state check). |
| **Factory-replacement defense** (A M#2 family) | `ensure_*` (not `_install_*`) on hot paths | EVERY schwabdev API call in `marketdata.py` calls `ensure_schwab_log_redaction_factory_installed()` first. |
| **Redact-then-truncate audit-error** (A R3 M#1 family) | `_redacted_excerpt` boundary-straddle leak | `_redacted_excerpt` (already shipped in A) is consumed VERBATIM; do NOT re-implement. |
| **camelCase kwarg trap** (B operator-paired-gate-caught defect at `34be84e`) | `Client.account_orders(maxResults=...)` — snake_case `max_results=` raised `TypeError` at runtime | **`Client.price_history(symbol, periodType=..., period=..., frequencyType=..., frequency=..., startDate=..., endDate=..., needExtendedHoursData=..., needPreviousClose=...)` — ALL kwargs except `symbol` are camelCase. PIN via `inspect.signature(schwabdev.Client.price_history)` discriminating test (mirror B's `tests/integrations/test_schwab_trader_kwarg_signatures.py` pattern; replicate for `marketdata.quotes` + `marketdata.price_history`).** Mechanical regression-defense; cassette tests will NOT catch this. |
| **Empty-response transient handling** (CLAUDE.md gotcha "External-API empty-result must be treated as transient") | Phase 9/10 OHLCV archive helper | T-C.2 `write_window` empty-window guard MUST fire BEFORE any disk write (Codex R1 M#7 in plan §H.6.3). T-C.3 ladder MUST treat Schwab `empty=true` flag as transient → fall back to yfinance + DO NOT clobber existing `{TICKER}.schwab_api.parquet`. |
| **Surface-aware advisory audit** (B M#1 family) | pipeline-internal silent-skip vs CLI advisory | T-C.5 CLI `--verify-marketdata` writes audit advisory rows; T-C.6 pipeline integration silent-skips on missing-Client (log only). |
| **`os.replace` cross-device-link** (CLAUDE.md gotcha) | Phase 6/7 atomic-write pattern | T-C.2 backward-compat rename uses `os.replace(old_path, new_path)` ONLY when both paths share the same volume (per CLAUDE.md gotcha + Phase 9 Sub-bundle E precedent). Archive dir is operator-local; Drive-syncing not in play. Discriminating test still asserts the paths share volume. |
| **Backward-compat both-files-exist merge-and-quarantine** (Codex R1 M#6 in plan §H.6.3) | T-C.2 fresh requirement | When both `{TICKER}.parquet` AND `{TICKER}.yfinance.parquet` exist (partial prior-run state): MERGE-AND-QUARANTINE (concat-dedupe by asof_date keeping the .yfinance.parquet row on conflict; rename old to `{TICKER}.parquet.orphan-{timestamp}.parquet`). NO data loss path. Discriminating test asserts merged content + orphan file present. |

### §0.6 Inter-bundle dependencies (verify before commit)

- **`SchwabClient` instance:** Sub-bundle C's `marketdata.py` MUST consume the SAME `SchwabClient` instance (constructed via `construct_authenticated_client()` in `swing/integrations/schwab/auth.py`). Sub-bundle B already satisfies this for trader.py + cli_schwab.py + pipeline_steps.py. Sub-bundle C extends — `marketdata_ladder.py` accepts `schwab_client: SchwabClient | None` parameter; ladder's `_step_evaluate` / `_step_charts` callsite passes the same instance constructed at pipeline entry.
- **Audit service-layer wrappers** (`record_call_start`, `record_call_finish` from A T-A.9; `link_snapshot_and_stamp_account_hash` not applicable here; `link_reconciliation_run` not applicable here) consumed VERBATIM from `swing/integrations/schwab/audit_service.py`. Market Data has NO domain-write linkage equivalent — `linked_snapshot_id` and `linked_reconciliation_run_id` stay NULL on market-data rows.
- **Source-ladder write path NOT applicable to C.** Market data is READ-side cache, NOT source-ladder write. The `account_equity_snapshots` source-ladder pattern is Sub-bundle B's territory; C's "ladder" is the cache-fill ladder (Schwab → yfinance fallback) per spec §3.8.
- **`PriceCache` existing class is `PriceSnapshot`, not `PriceCacheEntry`.** Plan §A.8 + §H.7 refer to `PriceCacheEntry`; the actual class at `swing/web/price_cache.py:24` is `PriceSnapshot`. **Implementer MUST grep + verify the actual class name; extend the actual class** (NOT create a new dataclass with the plan's hypothetical name). Bank as V2.1 §VII.F amendment candidate (plan-text rename).
- **`OhlcvCache` exists at `swing/data/ohlcv_cache.py`** — read its current shape before extending. NEW `provider` field on the cache entry per plan §A.8. Existing `source` TTL-state field UNCHANGED (per plan §A.8 LOCK).
- **Cross-bundle pin un-skip targets:**
  - `tests/integrations/test_schwab_pipeline_active_exclusion.py:257` — currently SKIPPED `Cross-bundle pin: un-skip at T-C.5 once 'fetch --verify-marketdata' ships`. **Un-skip in T-C.5.**
  - `tests/integrations/test_schwab_token_redaction_audit.py:1161` — currently SKIPPED `Cross-bundle pin: un-skip at T-C.7 once Market Data API cassettes recorded`. **Un-skip in T-C.7.**

### §0.7 Project state at dispatch time

- **HEAD on `main`:** `72af8e6` (post-Sub-bundle-B-merge handoff brief commit).
- **Test count baseline:** **3597 fast passing on main** (verified inline; +101 net from pre-B baseline 3496 per B return report). 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures (NOT regressions). 3 SKIPPED (1 flag-classifier operator-only + 2 cross-bundle pins T-C.5 + T-C.7 for Sub-bundle C to un-skip).
- **Test runtime:** ~78s wall-clock at `-n auto` default.
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v18 (Sub-bundle A T-A.7 landed; Sub-bundle B + C consumer-side only).
- **Production tokens DB:** `~/swing-data/schwab-tokens.production.db` exists with valid 30-min access + 7-day refresh tokens. **7-day refresh-token clock started 2026-05-14 — expires ~2026-05-21.** Sub-bundle C work + integrate before then OR operator re-runs `swing schwab setup` paste-back to extend the 7-day clock.
- **Production-state delta from B's gate** (per phase3e-todo Sub-bundle B SHIPPED entry): 17 `schwab_api_calls` rows; 5 `account_equity_snapshots` (3 manual + 2 schwab_api); 9 `reconciliation_runs` (7 TOS-CSV + 2 schwab_api); 38 `reconciliation_discrepancies` (30 resolved + 8 unresolved material from B's gate — operator-actionable per phase3e-todo, not Sub-bundle C scope). Sub-bundle C's `--verify-marketdata` will add fresh `schwab_api_calls` rows under endpoints `marketdata.quotes` + `marketdata.price_history`; ZERO domain rows added (verification-only per spec §3.6.3).

### §0.8 Q1-Q18 dispositions still LOCKED (DO NOT re-litigate)

Per writing-plans dispatch brief §0.3 + §0.3a + Sub-bundle A + B return reports. All Q-dispositions remain BINDING for Sub-bundle C:

- Q1 production-tier (Schwab Developer Portal app already approved + tokens persisted via A; Sub-bundle B verified live).
- Q3 V1 single-primary-account (Market Data is symbol-driven; account-hash not applicable to quotes/price_history paths).
- Q11 V1 INCLUDE market-data ladder — **Sub-bundle C is THIS scope.** Shape A LOCKED at §A.8.
- Q12 default tier acceptable (delayed quotes flagged informationally; not blocking V1).
- Q17 Market Data rate limits: 120 req/min per `client.md` L255-265 (same as Trader; verbatim).
- Q18 COA B (`schwabdev` library).
- Q8/Q13-residual/Q14/Q15 deferred to per-bundle Task 0.b (most pre-answered by `reference/schwab-api/market-data-*` + `reference/schwabdev/api-calls.md` — implementer pre-checks at T-C.0.b phase 1).

### §0.9 Sub-bundle C scope-summary (per plan §Tasks-C)

8 tasks; **+68 fast tests projected** (range +60..+85; matches A/B precedent for overshoot via parametrize + defense-in-depth). **Per-task summary** (full per-task content in plan §Tasks-C line 2130+):

| Task | Scope | Tests | Files touched |
|---|---|---:|---|
| **T-C.0.b** | **Operator-paired live verification (BLOCKING — see §2 below)** | 0 | recon doc |
| **T-C.1** | Market Data API endpoint methods + mappers (`marketdata.py`) | +12 | `swing/integrations/schwab/marketdata.py` (NEW) + `mappers.py` (extend) + `models.py` (extend with `SchwabQuoteResponse` + `SchwabPriceHistoryWindow`) |
| **T-C.2** | OHLCV archive Shape A persistence + backward-compat rename + window-filter + empty-write-guard (LARGEST task) | +18 | `swing/data/ohlcv_archive.py` |
| **T-C.3** | Market-data ladder fetcher (`marketdata_ladder.py`) | +14 | `swing/integrations/schwab/marketdata_ladder.py` (NEW) |
| **T-C.4** | `PriceCache` + `OhlcvCache` integration (verify actual class names — see §0.6) | +10 | `swing/web/price_cache.py` + `swing/data/ohlcv_cache.py` |
| **T-C.5** | `swing schwab fetch --verify-marketdata` CLI subcommand | +6 | `swing/cli_schwab.py` (extend) — un-skips cross-bundle pin at `tests/integrations/test_schwab_pipeline_active_exclusion.py:257` |
| **T-C.6** | Pipeline integration — `_step_evaluate` + `_step_charts` ladder injection (NO new pipeline step) | +4 | `swing/pipeline/runner.py` (verify ladder consumption through existing cache-call boundaries; minor adjustments only) |
| **T-C.7** | Sentinel-leak audit Bundle C coverage — un-skip cross-bundle pin at `tests/integrations/test_schwab_token_redaction_audit.py:1161` | +4 | `tests/integrations/test_schwab_token_redaction_audit.py` (un-skip) |

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `schwab-bundle-C-marketdata-and-cache-ladder`
- **Worktree directory:** `.worktrees/schwab-bundle-C-marketdata-and-cache-ladder/`
- **BASELINE_SHA:** `72af8e6` (current main HEAD).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`).

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes per plan §Tasks-C suggested commit shapes (`feat(schwab): ...`, `test(schwab): ...`, `docs(schwab-api): ...`).
- One commit per task per plan §Tasks-C pattern; Codex-fix commits as `fix(schwab-bundle-C): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **DEFER the FINAL return-report commit until adversarial Codex review converges to NO_NEW_CRITICAL_MAJOR** (per writing-plans dispatch brief §4 + Sub-bundle A + B precedent).

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → operator-paired T-C.0.b coordination → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Sub-bundle D dispatch commissioning post-C-ship.
- **Operator owns:** T-C.0.b operator-paired live verification (provides production-tier credentials already persisted; runs paired Market Data API cassette recording).

### §1.5 Verify command (basic; copowers:executing-plans handles full task execution + Codex review)

```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~12..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; assert EXPECTED_SCHEMA_VERSION == 18"
# Cross-bundle pins UN-SKIPPED:
python -m pytest tests/integrations/test_schwab_pipeline_active_exclusion.py::test_b6_10_fetch_verify_marketdata_NOT_protected -v
python -m pytest tests/integrations/test_schwab_token_redaction_audit.py -v -k 'cross_bundle_pin_market_data'
```

---

## §2 Operator-paired T-C.0.b verification gate (HARD BLOCKER for cassette recording)

Per plan §G.3 + §E.3 + §K.6. T-C.0.b requires operator participation for Market Data API cassette recording (mirrors Sub-bundle A T-A.0.b + Sub-bundle B T-B.0.b pattern).

**T-C.0.b requires:**
1. Operator's existing production-tier Schwab credentials (already persisted at `~/swing-data/schwab-tokens.production.db` from Sub-bundle A phase-2; **7-day refresh-token clock expires ~2026-05-21** — operator may need to re-run `swing schwab setup` paste-back if T-C.0.b session lands past then).
2. Operator runs `swing schwab fetch --verify-marketdata --symbols AAPL` (or implementer triggers per cassette-recording flow) against operator's actual Schwab account.
3. Implementer + operator together observe + record:
   - `marketdata.quotes` actual response shape (dict keyed by symbol; `last_price`/`bid`/`ask` field names; `delayed: bool` flag presence; partial-response error envelope shape per §E.4).
   - `marketdata.price_history` actual response shape (`{"candles": [...], "symbol": ..., "empty": bool}`; per-bar field names — verify `open`/`high`/`low`/`close`/`volume`/`datetime`).
   - **Verify Schwab's `empty=true` flag fires correctly** (e.g., request a future date range) — drives §H.6.4 transient-handling test.
   - Q12 default-tier-acceptable observation (delayed quotes flag value).
   - Q17 Market Data rate-limit headroom verification under back-to-back calls.
   - HTTP response headers (`X-RateLimit-Remaining` presence; same as Trader).

**Output of T-C.0.b:** recon doc at `docs/schwab-bundle-C-task-C0b-recon.md` (mirroring Sub-bundle B recon doc shape) + commit `docs(schwab-api): T-C.0.b recon doc with Market Data API operator-paired observations`.

**Pre-check `reference/schwabdev/api-calls.md` (L296-440 quotes + price_history) + `reference/schwab-api/market-data-{documentation,specification}.md` FIRST** to determine which T-C.0.b observations are already documented vs still need live API verification. Reduces operator-paired session burden. The `quotes` + `price_history` signatures are FULLY documented in api-calls.md including the camelCase kwarg surface — phase-1 recon doc should bank ALL deviations from plan §E.3 BEFORE implementer writes any T-C.1 code.

**If operator not immediately available:** implementer can proceed with T-C.1 + T-C.2 + T-C.4 + T-C.7 using stubbed schwabdev calls (cassette-dependent acceptance criteria for T-C.3 + T-C.5 + T-C.6 DEFERRED until T-C.0.b completes; document deferred items in return report for orchestrator triage). T-C.2 specifically is fully Schwab-independent (parquet persistence layer; no live calls) — implementer can ship T-C.2 standalone without T-C.0.b.

---

## §3 Operator-witnessed verification gate (Sub-bundle C integration)

Per plan §K.C. Surfaces enumerated below; orchestrator drives operator-witnessed gate post-Codex-convergence + pre-merge-to-main.

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3660..3680 fast tests (worktree-side); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; **0 cross-bundle pins remaining** (T-C.5 + T-C.7 un-skipped). |
| **S2** | `swing schwab fetch --verify-marketdata` against production | **Operator-driven (CLI)** | Verify: pipeline-active check passes (no concurrent run); ladder issues `quotes` + `price_history` calls against live Schwab; `schwab_api_calls` audit rows INSERTED with `endpoint='marketdata.quotes'` + `endpoint='marketdata.price_history'`; `linked_snapshot_id=NULL` + `linked_reconciliation_run_id=NULL` (verification-only; no domain writes); ZERO rows added to `account_equity_snapshots` / `reconciliation_runs` / `ohlcv_cache_persistent`-equivalent. |
| **S3** | `swing schwab fetch --verify-marketdata --environment sandbox` | **Operator-driven (CLI; switch env)** | Verify: ladder SKIPS schwabdev call entirely under sandbox (per spec §3.6.3 + §H.6.1 sandbox short-circuit); falls back to yfinance; audit row STILL writes for the schwabdev call NOT MADE? (See §0.5 surface-aware advisory audit lesson — under sandbox, T-C.5 may write a single advisory audit row noting "sandbox short-circuit; ladder used yfinance" OR may write nothing, mirroring B's `surface='cli'` advisory pattern; implementer locks the disposition at T-C.5 acceptance + return report.) |
| **S4** | Pipeline run with ladder enabled (production env) | **Operator-driven (CLI)** | Run `swing pipeline run` against production env; verify ladder fires through `_step_evaluate` + `_step_charts`; cache hit rate observable; `schwab_api_calls` audit rows accumulate with `surface='pipeline'`; on-disk parquet files at `swing-data/ohlcv-archive/{TICKER}.schwab_api.parquet` + `{TICKER}.yfinance.parquet` present + non-empty for at least one open-trade ticker. |
| **S5** | Backward-compat rename (operator's actual archive dir) | **Operator-driven (filesystem inspection)** | Verify: post-merge first cache read for any historical ticker triggers `_backward_compat_rename` (one-shot per ticker); pre-existing `{TICKER}.parquet` files renamed to `{TICKER}.yfinance.parquet`; idempotent on re-run; no data loss in archive. **NOTE:** if operator's archive dir already has only post-shape-A files (after some prior run), this surface is SKIP-WITH-INSPECTION-ONLY. |
| **S6** | Sentinel-token-leak audit Bundle C coverage | Inline | `pytest tests/integrations/test_schwab_token_redaction_audit.py -v` GREEN — un-skipped Market Data API portions covered. |
| **S7** | `SchwabPipelineActiveError` exclusion (un-skipped --verify-marketdata) | Inline | `pytest tests/integrations/test_schwab_pipeline_active_exclusion.py::test_b6_10_fetch_verify_marketdata_NOT_protected -v` GREEN. |
| **S8** | E2E pipeline run with ladder | Inline | `pytest tests/integration/test_schwab_pipeline_production_only_gate.py -v` GREEN (unchanged from B; cache layer integration does NOT regress). |
| **S9** | ruff baseline | Inline | `ruff check swing/ --statistics` reports 18 E501 unchanged. |

**Gate session ≤ 6 surfaces budget:** S1+S6+S7+S8+S9 are inline (5 surfaces). S2+S3+S4+S5 are operator-driven CLI/filesystem (4 surfaces). **Total operator-driven: 4 — within 6-surface budget.**

**Production state post-gate:** S2-S5 add fresh `schwab_api_calls` audit rows for `marketdata.quotes` + `marketdata.price_history` endpoints + ladder activity through `_step_evaluate` / `_step_charts`. Cache files at `swing-data/ohlcv-archive/{TICKER}.schwab_api.parquet` + `{TICKER}.yfinance.parquet` populated. ZERO domain rows added (no `account_equity_snapshots` writes; no `reconciliation_runs` writes; no `reconciliation_discrepancies` writes — Market Data is read-side only).

**Production-write classifier soft-block awareness:** S2-S4 issue calls that WRITE to `schwab_api_calls`. Operator pre-authorizes via gate-path; production-write classifier may surface as soft-block — operator says "yes" in plain chat to proceed.

---

## §4 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** via the Skill tool. The copowers wrapper handles Codex review automatically after task commits land.
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md`
  - `SUB_BUNDLE=C` (Tasks T-C.0.b..T-C.7)
  - `BASELINE_SHA=72af8e6`
- **Expected Codex chain:** 4-5 rounds (per plan §0.4 estimate; **largest novel scope of the arc** — cache architecture rewrite + Shape A persistence + new ladder + new resolver + backward-compat migration).
- Iterate per-round fixes as `fix(schwab-bundle-C): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §4.1 Codex value-add concentration (Sub-bundle C specific)

Adversarial review for Sub-bundle C typically catches:

- **camelCase kwarg trap on `price_history`** — exactly the same defect family as Sub-bundle B's `account_orders(maxResults=...)` (orchestrator-inline fix `34be84e`). Pre-empt by writing the `inspect.signature(schwabdev.Client.price_history)` discriminating test FIRST per task; pin `{periodType, period, frequencyType, frequency, startDate, endDate, needExtendedHoursData, needPreviousClose}` set verbatim. Also pin `quotes` signature for completeness even though it's snake_case.
- **Empty-bars vs Schwab `empty=true` flag handling.** Plan §E.5 + §H.6.4 prescribe synthetic `SchwabApiError(204, "empty bars")` raise — verify the mapper consults Schwab's explicit `"empty": bool` field IN ADDITION to `len(candles) == 0` check (defense-in-depth; Schwab may return both `empty=true AND candles=[]` OR `empty=false AND candles=[...]`). Discriminating test plants both shapes.
- **Backward-compat rename idempotency.** T-C.2 must handle 4 cases (old-only / both-exist / new-only / neither). Codex will probe with both-exist case; pre-empt with the merge-and-quarantine implementation per §H.6.3 + Codex R1 M#6 disposition in the plan.
- **Window-filter step in `resolve_ohlcv_window`.** Codex R1 M#4 in the plan banked the `start <= asof_date <= end` filter requirement explicitly — pre-empt by writing the discriminating test from §H.6.3 verbatim (plant rows at `[2026-01-01, 2026-01-15, 2026-02-01]`; query `start='2026-01-10', end='2026-01-20'`; assert ONLY 2026-01-15 returned).
- **Empty-window-write guard.** T-C.2 `write_window` MUST guard `if window is None or len(window) == 0: return` BEFORE any disk I/O — defense-in-depth against ladder caller bugs (the ladder catches empty-bars and falls back, but a caller bug bypassing the ladder must not clobber). Discriminating test asserts existing parquet UNCHANGED when `write_window(ticker, empty_df, 'schwab_api')` invoked.
- **PriceCacheEntry vs PriceSnapshot naming drift.** Plan §A.8 + §H.7 say `PriceCacheEntry`; actual class at `swing/web/price_cache.py:24` is `PriceSnapshot`. Implementer uses ACTUAL class name; banks plan-text rename as V2.1 §VII.F amendment candidate. Codex will flag if implementer creates a new dataclass unnecessarily.
- **Sandbox short-circuit precedence.** Per spec §3.6.3 + §H.6.1: `env != 'production'` short-circuits the schwabdev call BEFORE any audit row insert — UNLESS the surface is CLI `--verify-marketdata` which writes an advisory audit row noting the sandbox skip (mirror B's surface-aware pattern). Pipeline-internal silently uses yfinance.
- **`_call_endpoint()` shared harness extraction (B forward-binding lesson #5).** If T-C.1 implementer finds `marketdata.py` duplicating large blocks of `trader.py`'s call wrapper, extract to `swing/integrations/schwab/_endpoint_call.py` shared module. Codex will flag DRY violations across the two files.
- **`Schwabdev` capital-S logger prefix** (per Sub-bundle A T-A.10 D1). Any new logger filtering/inspection in marketdata.py MUST use the live capital-S form.
- **Single-Client-instance discipline.** `grep -rn "schwabdev.Client(" swing/integrations/schwab/marketdata.py swing/integrations/schwab/marketdata_ladder.py` returns ZERO matches.
- **Source-ladder vs cache-ladder terminology discipline.** "Source-ladder" = `account_equity_snapshots.source` precedence (Phase 9 Sub-bundle C; Sub-bundle B's territory). "Cache-ladder" = market-data Schwab→yfinance fetch fallback (Sub-bundle C's territory). Plan + brief use both; do NOT conflate.

### §4.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-C.0.b | None expected (verification-only); recon doc must include all observations + bank ALL plan deviations | Operator-paired session checklist; recon doc template; pre-check distilled refs FIRST. |
| T-C.1 | Silent-failure on each of 2 marketdata methods; **camelCase kwarg drift on `price_history`**; `Schwabdev` logger filter wrong-case; missing `ensure_*` pre-call; partial-response handling on `quotes` mapper missing | Per-method discriminating test; `inspect.signature(schwabdev.Client.price_history)` pin; capital-S logger; `ensure_*` first line of every wrapper; mapper test plants `{symbol1: {OK shape}, symbol2: {error envelope}}` and asserts subset return + audit `error_message` redacted. |
| T-C.2 | Empty-window-write guard missing; backward-compat rename loses data on both-exist; window-filter step missing in `resolve_ohlcv_window` | All 3 discriminating tests written FIRST per plan §H.6.3; merge-and-quarantine implementation handles both-exist explicitly. |
| T-C.3 | Sandbox short-circuit precedence wrong (write-then-rollback vs short-circuit-before-write); empty-bars vs `empty=true` flag handling missing; ladder doesn't pass through `provider` tag to caller | Discriminating tests assert sandbox path = ZERO schwabdev call attempted; empty-bars test plants Schwab response with `{"candles":[], "empty": true}` + asserts ladder returns yfinance result + parquet UNCHANGED + audit row `error_message="empty bars (transient)"`. |
| T-C.4 | `provider` field added to actual class (not hypothetical `PriceCacheEntry`); existing TTL `source` field unchanged; cache-fill via ladder routes correctly | Read actual class names FIRST; preserve existing test fixtures; discriminating test asserts `source` value unchanged for any existing test fixture. |
| T-C.5 | Cross-bundle pin un-skip leaves test broken; partial-response surfaces in CLI output; --symbols flag parsing edge cases | Un-skip + verify pin already passes (Sub-bundle B left a SKIPPED stub; the test body is already there); --symbols `"AAPL,AMD"` parse + `"AAPL ,AMD"` (trim whitespace) + `""` (default to AAPL); 401/429 handled via existing `SchwabApiError` subclasses. |
| T-C.6 | New pipeline step accidentally introduced (plan forbids); ladder consumed but `_step_evaluate` callsite passes WRONG cfg field; sandbox short-circuit verified at pipeline level | Plan §H.6 explicitly says "NO new pipeline step (per spec §3.4.1). NO step ordering change" — verify diff to `swing/pipeline/runner.py` is minimal (cache-call-boundary adjustments only). |
| T-C.7 | Un-skip leaves test broken because marketdata.py loggers don't propagate sentinel; partial-response error_message redacts symbol-level breakdown but leaks token bytes | Market Data API cassettes drive sentinel through schwabdev's `Schwabdev` logger; assert sentinel absent from caplog + audit `error_message`; per-symbol breakdown excerpt redacts via `_redacted_excerpt` (already shipped). |

---

## §5 Watch items for Sub-bundle C implementer (per-task assertion targets)

Per plan §L watch items — Sub-bundle C's binding subset:

1. **§A.4 source-ladder consumer inheritance verbatim** — N/A direct (market-data is cache, not source-ladder); preserve `account_equity_snapshots`/`reconciliation_runs` UNCHANGED at the source-ladder API.
2. **§A.3 production-only domain writes** — N/A direct (market data writes audit rows + cache files; NO `account_equity_snapshots`/`reconciliation_runs` writes from C).
3. **§A.8 Shape A persistence** — T-C.2 + T-C.4 + downstream cache impact. THIS is C's primary attack surface.
4. **§E.5 empty-API-response transient handling** — T-C.3 + T-C.5 + plan §H.6.4 verbatim.
5. **§H.4.1 audit-row lifecycle** — T-C.1 mirrors B's trader.py pattern (INSERT-then-UPDATE; service-layer wrappers).
6. **§J.4 token redaction inheritance** — T-C.7 sentinel-leak audit Market Data coverage.
7. **§Q11 V1 INCLUDE market-data ladder** — T-C.3 ladder.
8. **`_step_schwab_*` audit-write surface boundary** per spec §3.6.2 — pipeline-internal silent-skip vs CLI advisory audit (B forward-binding lesson #2).
9. **Test fixture USERPROFILE+HOME monkeypatch** per CLAUDE.md gotcha — applies to any test invoking `_user_home()` resolution paths in cache code.
10. **Phase isolation preserved** — `swing/data/repos/account_equity_snapshots.py` + `swing/data/repos/reconciliation.py` + `swing/trades/account_equity_snapshots.py` + `swing/trades/reconciliation.py` are READ-ONLY for C.

---

## §6 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/schwab-bundle-C-return-report.md` (mirroring `docs/schwab-bundle-B-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (task-impl + Codex-fix + return-report).
2. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
3. Test count delta + ruff baseline delta + schema version delta (unchanged at v18; consumer-side only).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1+S6-S9 inline OK; S2-S5 PENDING operator-driven session).
5. Per-task deviations from the plan (if any) with rationale (e.g., `PriceCacheEntry` vs actual `PriceSnapshot`).
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (cross-bundle pins; Sub-bundle D un-skip targets if any new ones surfaced; V2 candidates banked).
8. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8/9/10/Sub-A/Sub-B precedent).
9. Sub-bundle D forward-binding lessons (if any new ones surfaced during executing-plans).
10. Composition-surface verification via `^def` grep.
11. T-C.0.b operator-paired session observations (recon doc summary + which §D items got pre-answered + which still need operator-paired live verification at Sub-bundle D dispatch).
12. `reference/schwab-api/` + `reference/schwabdev/` distilled refs consumed during T-C.0.b (`market-data-{documentation,specification}.md` + `api-calls.md` L296-440 + `client.md` rate limits).
13. Single-Client-instance discipline verification (`grep -rn "schwabdev.Client(" swing/integrations/schwab/marketdata.py swing/integrations/schwab/marketdata_ladder.py` count = 0).
14. Cross-bundle pin un-skip status (T-C.5 + T-C.7 BOTH un-skipped; tests passing).

---

## §7 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed: Skill, Bash for git + worktree, MCP for Codex, Read/Edit/Write for code + tests).
- **Foreground vs background:** foreground (default). Sub-bundle output dictates next-step decisions; parallelism gives little value.
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 8-12 hr including 4-5 Codex rounds.

---

## §8 Watch items for orchestrator (post-Sub-bundle-C-ship)

1. **Operator-witnessed gate driving** — orchestrator drives S2-S5 via operator-paired CLI + filesystem-inspection session. **7-day refresh-token clock started 2026-05-14, expires ~2026-05-21** — operator may need to re-run `swing schwab setup` paste-back if Sub-bundle C integration runs past 2026-05-21. Production-write classifier soft-block awareness for S2-S4 (operator pre-authorizes via gate-path).
2. **Sub-bundle D dispatch readiness** — post-C-ship, D is unblocked. D closes the arc. Brief drafting MUST consume:
   - **Review-form polish task** (drop stale "(Phase 7 will auto-derive this from Fills.)" parenthetical at `swing/web/templates/partials/review_form.html.j2:66-67` per phase3e-todo 2026-05-13 entry; operator-locked into Sub-bundle D last-bundle disposition).
   - **7-day refresh-token expiry alert design** (`swing schwab status` full surface MUST surface days-remaining alert per spec §3.5; ≤24hr WARN; ≤2hr ERROR + bold red); briefing.md banner; cycle-checklist weekly re-auth reminder.
   - **`unsupported_token_type` → `update_tokens(force_refresh_token=True)` remediation surface design** per schwabdev `troubleshooting.md`.
   - **3 CLAUDE.md gotcha promotions at T-D.4:**
     - schwabdev camelCase kwarg discipline (Sub-bundle B SHIPPED entry banked; Sub-bundle C `price_history` will reinforce if any defect leaks past gate).
     - R1 M#3 typed-SchwabApiError audit-row close discipline (Sub-bundle B SHIPPED entry banked).
     - Sub-bundle C if any new gotcha surfaces (e.g., `PriceSnapshot` vs `PriceCacheEntry` plan-text drift; backward-compat rename pattern; etc.).
3. **Cross-bundle pin un-skip cascade COMPLETE post-C-ship** — both T-C.5 + T-C.7 un-skipped during this dispatch; ZERO cross-bundle pins remaining for Sub-bundle D.
4. **Plan-text V2.1 §VII.F amendment candidates** likely banked at T-C.0.b recon doc + return report:
   - `PriceCacheEntry` (plan §A.8 + §H.7) → `PriceSnapshot` (actual class name).
   - `start_datetime`/`end_datetime` (plan §E.3 row 2) → `startDate`/`endDate` (camelCase per schwabdev surface).
   - `period_type`/`frequency_type` (plan §E.3 row 2) → `periodType`/`frequencyType` (camelCase per schwabdev surface).
   - Any others surfaced during operator-paired phase 2.

---

## §9 Dispatch order — UNCHANGED from plan §0.3

A → B → **C** → D (strict). A SHIPPED at `5b6e5ba`. B SHIPPED at `df29232`. **C in flight per this brief.** D is BLOCKING on all three (closes the arc with E2E + briefing banner + cycle-checklist + CLAUDE.md gotchas + Phase 11 hand-off).

Sub-bundle D dispatch UNBLOCKED post-Sub-bundle-C-ship. Operator-paced.
