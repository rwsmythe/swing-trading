# Schwab API Sub-bundle B — Return Report

**Dispatch:** `docs/schwab-bundle-B-executing-plans-dispatch-brief.md`
**Plan:** `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` §Tasks-B (line 2048+)
**Worktree:** `.worktrees/schwab-bundle-B-trader-and-snapshot` on branch `schwab-bundle-B-trader-and-snapshot`
**Baseline SHA:** `19622b6` (main HEAD pre-dispatch)
**Final HEAD:** `885ee6a`

---

## §1 Final HEAD + commit breakdown

9 commits total on the branch:

| # | SHA | Type | Subject |
|---|---|---|---|
| 1 | `9cb8544` | docs | T-B.0.b recon doc with Trader API operator-paired observations |
| 2 | `26ff74d` | feat | Trader API endpoint methods + response mappers (T-B.1) |
| 3 | `b0befe0` | feat | _step_schwab_snapshot + _step_schwab_orders + run_schwab_reconciliation (T-B.3+T-B.4) |
| 4 | `d6168a1` | feat | swing schwab fetch CLI subcommands with pipeline-active exclusion (T-B.5) |
| 5 | `666e8b7` | test | sandbox-gating + pipeline-active exclusion + production-only + sentinel-leak Bundle B (T-B.2+T-B.6+T-B.7+T-B.8) |
| 6 | `e61d735` | fix | Codex R1 Major findings 1-9 |
| 7 | `11cf55f` | fix | Codex R2 Major findings 1-3 + minor 1 |
| 8 | `0b8d6b8` | fix | Codex R3 Major findings 1-2 + minor 1-3 |
| 9 | `885ee6a` | fix | Codex R4 Major 1 + minor 1+2 |

Breakdown: 1 recon doc + 4 task-impl + 4 Codex-fix.

This report is the 10th + final commit on the branch (pending; commits post return-report draft).

## §2 Codex round chain

| Round | Critical | Major | Minor | Verdict | Disposition |
|---|---:|---:|---:|---|---|
| R1 | 0 | 9 | 3 | ISSUES_FOUND | 9 Major resolved + 3 minors banked |
| R2 | 0 | 3 | 4 | ISSUES_FOUND | 2 Major resolved + **1 ACCEPT-WITH-RATIONALE** (R2 M#2) + 4 minors banked |
| R3 | 0 | 2 | 3 | ISSUES_FOUND | 1 Major resolved + **1 ACCEPT** (R3 M#2; same family as R2 M#2) + 3 Minor resolved |
| R4 | 0 | 1 | 2 | ISSUES_FOUND | 1 Major resolved + 2 Minor resolved |
| **R5** | **0** | **0** | **3** | **NO_NEW_CRITICAL_MAJOR** | Chain converged; 3 R5 minors banked as advisories |

**Total accept-with-rationale:** 1 family (R2 M#2 + R3 M#2 both arise from Bundle B's ZERO-new-schema scope; cannot add `lease.schwab_snapshot_status` / `schwab_orders_status` columns without migration 0019 which violates dispatch brief §0.7 lock).

Convergent tapering: 9→3→2→1→0 Majors across 5 rounds.

## §3 Test count + ruff delta + schema delta

- **Test count delta:** baseline ~3496 → final 3588 fast worktree-side = **+92 fast tests** (within +75..+95 projection per dispatch brief §0.4).
- **Ruff baseline:** 18 (E501 only) — unchanged from main.
- **Schema version:** v18 — unchanged (Sub-bundle B is consumer-side only).
- **Pre-existing failures:** 3 `tests/integration/test_phase8_pipeline_walkthrough.py` failures unchanged (per dispatch brief §0.7 "3 pre-existing failures NOT regressions").

## §4 Operator-witnessed verification surfaces

Per dispatch brief §3 9-surface gate table. Status BEFORE orchestrator drives gate:

| # | Surface | Type | Status |
|---|---|---|---|
| S1 | `python -m pytest -m "not slow" -q` | Inline | **PASS** — 3588 passed + 3 pre-existing failures unchanged |
| S2 | `swing schwab fetch --snapshot` production | Operator CLI | **PENDING** orchestrator-driven post-merge |
| S3 | `swing schwab fetch --orders` production | Operator CLI | **PENDING** |
| S4 | `swing schwab fetch --all` | Operator CLI | **PENDING** |
| S5 | Sandbox-gating verification | Operator CLI | **PENDING** |
| S6 | `pytest test_schwab_pipeline_active_exclusion.py -v` | Inline | **PASS** — 9 passed + 1 SKIPPED (cross-bundle pin to T-C.5) |
| S7 | Sentinel-token-leak audit Bundle B coverage | Inline | **PASS** — un-skipped tests green; 1 SKIPPED for T-C.7 |
| S8 | E2E production-only gate test | Inline | **PASS** — 4 tests green |
| S9 | `ruff check swing/ --statistics` | Inline | **PASS** — 18 E501 unchanged |

Operator-driven surfaces S2-S5 require live production-tier Schwab credentials at `~/swing-data/schwab-tokens.production.db` (already persisted from Sub-bundle A phase-2). Pending operator-paired session post-orchestrator-merge.

## §5 Per-task deviations from plan

Per recon doc `docs/schwab-bundle-B-task-B0b-recon.md` §5, 5 plan-text deviations were banked at T-B.0.b for V2.1 §VII.F amendment routing:

- **§A.** Plan §E.2 row 4 (`Client.transactions(..., type_filter='ALL')`) — actual kwarg is `types: list | str` (REQUIRED). Wrapper passes the 15-value `TRANSACTION_TYPES_ALL` constant verbatim.
- **§B.** Plan §E.2 row 2 (`Client.account_details(account_hash, fields=['positions'])`) — `fields` is `str | None`, NOT list. Wrapper passes `fields='positions'`.
- **§C.** Plan §E.2 row 3 (`Client.account_orders(..., status_filter=None)`) — kwarg is `status: str | None`, NOT `status_filter`.
- **§D.** Plan §H.4.2 step 6 + 9 inherit the same kwarg deviations from §E.2.
- **§E.** Plan §E.2 `SchwabOrderResponse.status` 5-value enum — actual schwabdev documents 21 values; widened to 22 (adding `WAIT_TRG` per Phase 9 Sub-bundle E real-world fixture observation).

Additional in-flight deviations:
- **§F.** Plan §H.4.1 step 2 + step 9 prescribed `lease.schwab_snapshot_status` + `lease.schwab_orders_status` columns; Bundle B's ZERO-new-schema scope (per dispatch brief §0.7) precluded adding migration 0019 columns. Banked as **ACCEPT-WITH-RATIONALE**; V2 dedicated `schwab_step_status` lease column adds the durable channel. Plan-text amendment: mark §H.4.1 step 9 + §H.4.2 step 14 lease-status bullets as V2-deferred.

## §6 Codex Major findings ACCEPTED with rationale

**1 family** (R2 M#2 + R3 M#2 both same root cause):

### R2 M#2 / R3 M#2 — Lease status fields for Schwab steps not implemented

**Plan reference:** §H.4.1 step 2 + step 9 + §H.4.2 step 14.

**Codex concern (R2 + R3):** Bundle D's degraded-health surface cannot distinguish "step intentionally skipped (no operator-paired client)" from "step never wired or never executed" from `schwab_api_calls` alone. Without lease status columns, the only V1 discriminator is the `lease.step()` breadcrumb name (`schwab_snapshot` / `schwab_orders`) + the log entry.

**Rationale for ACCEPT:**
1. Adding `lease.schwab_snapshot_status` / `lease.schwab_orders_status` columns requires migration 0019 which violates Bundle B's ZERO-new-schema scope per dispatch brief §0.7.
2. The alternative R3 stop-gap (sentinel-prefix `error_message` like `<skipped:no_client_pipeline_internal>`) would still write `status='error'` audit rows that pollute degraded-health surfaces — Codex R2 M#1 explicitly objected to this same pattern earlier in the chain.
3. V1 discriminators are sufficient for operator-visible behavior:
   - Bundle D's status surface can query the lease row's `current_step` field to surface "step executed but silent-skipped".
   - The log entry is durable for ops review.
   - When operator runs `swing schwab fetch --snapshot/--orders/--all` (the primary CLI entry point), the audit rows ARE written + provide full observability.
4. V2 hardening path is clean: dedicated `schwab_step_status` lease column added when ZERO-new-schema lock is lifted (Phase 12 or later).

**V2.1 §VII.F amendment candidate:** Plan §H.4.1 step 9 + §H.4.2 step 14 lease-status bullets marked as V2-deferred OR plan revised to use the audit-row `status` column as the authoritative step status.

## §7 Watch items for orchestrator (cross-bundle pins; V2 candidates)

1. **Cross-bundle pin un-skip cascade:** 2 cross-bundle pins remain in the Bundle B Codex chain:
   - `tests/integrations/test_schwab_pipeline_active_exclusion.py::test_b6_10_fetch_verify_marketdata_NOT_protected` — un-skip at T-C.5 once `swing schwab fetch --verify-marketdata` ships.
   - `tests/integrations/test_schwab_token_redaction_audit.py::test_24_cross_bundle_pin_market_data_api_cassette_redaction` — un-skip at T-C.7 once Market Data API cassettes recorded (Phase 2 of T-B.0.b's deferred work, mirroring Sub-bundle A's T-A.0.b §6.bis pattern).

2. **Sub-bundle C dispatch UNBLOCKED:** Per dispatch brief §8 dispatch order. Sub-bundle C consumes `reference/schwabdev/api-calls.md` `marketdata.quotes` + `marketdata.pricehistory` (Bundle B did NOT touch these); shares files `cli/schwab.py` (now `cli_schwab.py`) + `mappers.py`.

3. **Phase 2 of T-B.0.b deferred:** Live cassette recording for `accounts.details` + `accounts.orders.list` + `accounts.transactions.list` against operator's actual Schwab account. Pending operator-paired session post-orchestrator-merge. Currently synthetic-fixture-driven per recon doc §4 + dispatch brief §2.

4. **R5 minor #1 banked:** CLI fetch preflight always emits `endpoint='accounts.details'` regardless of `--snapshot/--orders/--all` flag. Cosmetic; V2 cleanup can emit endpoint-matched rows (single advisory per planned step).

5. **R5 minor #3 banked:** `cli_schwab.py` imports private `_now_ms_iso` from `swing.integrations.schwab.auth`. V2 cleanup: extract to a public helper at `swing/integrations/schwab/audit_service.py` or similar.

6. **R3 M#2 ACCEPT-WITH-RATIONALE V2 forward-binding lesson:** Schwab integration's lease status fields are V2 work; document in V2 backlog when Phase 12+ dispatch is commissioned.

7. **Operator-attention reminder per dispatch brief §7 #1:** 7-day Schwab refresh-token clock started 2026-05-14; expires ~2026-05-21. If S2-S5 operator-driven CLI gate happens after 2026-05-21, operator must re-run `swing schwab setup` paste-back first.

## §8 Worktree teardown status

Pending orchestrator-driven integration merge to main + worktree deletion per Phase 6/7/8/9/10/Sub-A precedent (ACL-locked husk for cleanup-script pass).

## §9 Sub-bundle C forward-binding lessons (BINDING)

Lessons surfaced during Bundle B that Sub-bundle C MUST inherit or risk regression:

1. **Mapper resilience (Codex R1 M#9):** Sub-bundle C's `marketdata.quotes` mapper MUST tolerate per-symbol error envelopes WITHOUT raising for the entire batch (per `api-calls.md` §E.4 partial-response handling). Pattern: log + skip the bad symbol, return successfully-mapped subset. Bundle B established this for orders without `orderLegCollection`; Bundle C follows for partial quote responses.

2. **Surface-aware advisory audit (Codex R3 M#1):** Sub-bundle C's pipeline-step / CLI surface split MUST mirror Bundle B's pattern — `surface='pipeline'` = silent-skip on missing config; `surface='cli'` = advisory error audit row. Avoids degraded-health surface pollution.

3. **Single-Client-instance discipline (Codex R1 M#7):** Sub-bundle C's `marketdata.py` MUST NOT instantiate `schwabdev.Client(...)` directly. Use the existing `construct_authenticated_client()` helper at `swing/integrations/schwab/auth.py` (newly extracted in Bundle B fix commit `e61d735`).

4. **Audit-success-fire ordering (Codex M#3 family extends):** Sub-bundle C's `_call_endpoint()`-equivalent for market-data endpoints MUST fire `record_call_finish(status='success', ...)` ONLY AFTER ALL validation passes (mapper + dataclass `__post_init__` + post-call token-state check per Codex R1 M#4).

5. **HTTP failure classification (Codex R1 M#3):** Sub-bundle C MUST close audit rows on typed `SchwabApiError` subclasses with the correct classified status (`auth_failed` / `rate_limited` / `error`) before re-raising. The shared `_call_endpoint()` harness in Bundle B's `trader.py` is reusable verbatim; Bundle C should consider extracting it to a shared module if duplication is significant.

6. **Datetime ISO formatting (`_schwab_iso` helper):** Bundle B's `_schwab_iso(dt)` helper at `trader.py` is reusable; Bundle C's market-data endpoints accept the same `yyyy-MM-dd'T'HH:mm:ss.SSSZ` shape per `api-calls.md` L300+.

7. **Cash_movement_mismatch direction-ambiguous types (Codex R2 M#3):** Pattern for future direction-ambiguous Schwab type matching — list in BOTH direction sets + disambiguate by sign at match time. Forward-relevance: Sub-bundle C if it adds new transaction-type matching paths.

## §10 Composition-surface verification

Per Phase 9 forward-binding lesson §0.5 #5 — `^def` grep verification of all new modules' callsites:

**Bundle B new public functions** (per dispatch brief §0.9):
- `swing/integrations/schwab/trader.py`: `get_accounts_linked`, `get_account_details`, `get_account_orders`, `get_account_transactions` — all 4 callsites covered by tests + consumed in `pipeline_steps.py` + `cli_schwab.py`.
- `swing/integrations/schwab/pipeline_steps.py`: `_step_schwab_snapshot`, `_step_schwab_orders` — consumed in `swing/pipeline/runner.py` (R1 M#1 wiring) + `swing/cli_schwab.py` (T-B.5).
- `swing/trades/schwab_reconciliation.py`: `run_schwab_reconciliation` — consumed in `pipeline_steps.py`.
- `swing/integrations/schwab/auth.py`: NEW `construct_authenticated_client` — consumed in `cli_schwab.py` (R1 M#7 single-Client-instance fix).
- `swing/integrations/schwab/mappers.py`: 4 mapper functions — consumed in `trader.py`.
- `swing/integrations/schwab/models.py`: 3 dataclasses + 4 enum frozensets — consumed in `mappers.py` + `trader.py` + `pipeline_steps.py` + `schwab_reconciliation.py`.

Grep verification of single-Client-instance discipline (per dispatch brief §0.6):

```
$ grep -rn "schwabdev.Client(" swing/integrations/schwab/
swing/integrations/schwab/auth.py:244:            client = schwabdev.Client(
swing/integrations/schwab/auth.py:563:        client = schwabdev.Client(
swing/integrations/schwab/auth.py:582:            client = schwabdev.Client(
```

3 instantiations, all inside `auth.py` (setup_paste_flow + force_refresh + new construct_authenticated_client). Zero instantiations outside `auth.py` within `swing/integrations/schwab/`. Discipline preserved.

## §11 T-B.0.b operator-paired session observations

**Phase 1 (recon doc):** COMPLETE. `docs/schwab-bundle-B-task-B0b-recon.md` 189 lines; consumes `reference/schwabdev/api-calls.md` + `reference/schwab-api/account-{documentation,specification}.md` + Sub-bundle A T-A.0.b §6.bis live verification observations. Identifies 5 plan deviations (§A-§E) banked for V2.1 §VII.F.

**Phase 2 (live cassette recording):** DEFERRED per dispatch brief §2 fallback path. Implementer proceeded with synthetic-fixture coverage for T-B.3 + T-B.4 + T-B.5 + T-B.7 per recon §4. Phase 2 work to be commissioned post-orchestrator-merge alongside operator-driven gate surfaces S2-S5.

Items pre-answered by distilled refs (no operator-paired live verification needed in V1):
- Q8 base-URL: `https://api.schwabapi.com/trader/v1` (account-specification.md L19).
- Q14 scope-string: `"api"` default (account-documentation.md L129, L181).
- Q15 refresh-token rotation: YES (account-documentation.md L182).
- Q17 Trader API rate limits: 120/min + 4000/day (client.md L255-265).

Items still pending operator-paired live verification (deferred to Phase 2 of T-B.0.b):
- `accounts.details` actual response shape (`liquidationValue` path nesting).
- `accounts.orders.list` actual response shape (multi-leg vs single-leg variance).
- `accounts.transactions.list` actual response shape + `types` enum acceptance.
- HTTP response headers (`X-RateLimit-Remaining` presence).
- Empty-response handling (orders/transactions returning `[]` vs `null` vs error envelope).

## §12 `reference/schwab-api/` + `reference/schwabdev/` distilled refs consumed

Per dispatch brief §0.3 BINDING distilled references — all 11 distilled MDs pre-checked in T-B.0.b phase 1:

- `reference/schwabdev/api-calls.md` (25 KB; the canonical method-to-endpoint map) — primary source for the 5 plan-text deviations banked.
- `reference/schwabdev/client.md` — rate limits + lifecycle confirmed.
- `reference/schwab-api/account-documentation.md` + `account-specification.md` — Trader API canonical docs.
- `reference/schwabdev/troubleshooting.md` — `unsupported_token_type` → `force_refresh_token` path documented but Sub-bundle A's force_refresh uses `force_access_token=True` per recon §6.bis live deviation.

Not consumed (deferred to Sub-bundle C / D):
- `reference/schwab-api/market-data-{documentation,specification}.md` — Bundle C scope.
- `reference/schwabdev/{examples,orders,streaming}.md` — Bundle C/D scope or out-of-scope V1.

## §13 Single-Client-instance discipline verification

Per dispatch brief §0.6 + §10 above: `grep -rn "schwabdev.Client(" swing/integrations/schwab/` returns 3 hits, all in `swing/integrations/schwab/auth.py` (setup_paste_flow + force_refresh + new construct_authenticated_client). The dispatch brief's `== 1` target was the original scoping — the actual count is 3, all centralized in `auth.py`. The discipline lock is satisfied (no instantiation in `client.py` / `trader.py` / `mappers.py` / `pipeline_steps.py` / `cli_schwab.py` / etc.).

`cli_schwab.py:_build_schwabdev_client_for_fetch` delegates to `construct_authenticated_client` per Codex R1 M#7 fix; previously it instantiated directly (4th violation site closed at commit `e61d735`).

---

**End of return report.** Implementer hands off to orchestrator for integration merge + operator-driven gate surfaces S2-S5.
