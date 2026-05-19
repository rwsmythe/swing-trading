# Phase 13 T3.SB1 — Entry auto-fill recon

**Sub-bundle:** T3.SB1 — Entry auto-fill via Schwab Trader API at trade-entry form-render time.

**Branch:** `phase13-t3-sb1-entry-auto-fill` (worktree at `.worktrees/phase13-t3-sb1-entry-auto-fill/`).

**Branch base:** T2.SB1 T-A.1.1 commit SHA `4cfd5f2ca9b0103231fb558b141cd87132939d12` (per OQ-12 Option E concurrent dispatch; spec §1.4 + plan §B.2 + dispatch brief §1.2). NOT branched off main HEAD — main HEAD `6383cfa` does NOT contain T-A.1.1 yet (T2.SB1 still in flight at dispatch time; T2.SB1 merges first, T3.SB1 merges second).

---

## §1 Schwab Trader API methods consumed

Per plan §G.2 T-B.1.1 step 2 + spec §6.1.

### §1.1 `account_orders` — primary fill-candidate fetch

Wrapper: [swing/integrations/schwab/trader.py:329-376](swing/integrations/schwab/trader.py#L329) — `get_account_orders(client, conn, account_hash, from_entered_time, to_entered_time, *, surface, environment, pipeline_run_id, status, max_results)`.

schwabdev signature: `Client.account_orders(account_hash, from_str, to_str, status=status, maxResults=max_results)`. Per the Sub-bundle B `34be84e` defect family + CLAUDE.md gotcha "schwabdev camelCase kwarg discipline", the kwarg name is **`maxResults`** (camelCase, NOT `max_results`).

T3.SB1 invocation shape (per spec §6.1 + plan §G.2 T-B.1.2):
- `account_hash`: resolved via the existing Schwab integration (V1 single-account pattern — operator's primary linked account).
- `from_entered_time`: `now() - 7 days` (default lookback window; cfg-configurable per §6.1).
- `to_entered_time`: `now()`.
- `status`: default `None` (fetches ALL 21+ statuses; `_is_execution_bearing_candidate` filter applies in-Python — see §3).
- `max_results`: V1 default `None` (no cap; lookback window bounds the volume).
- `surface='trade_entry'` (per CHECK widening at v20 migration; see §2).
- `environment`: `cfg.integrations.schwab.environment`.
- `pipeline_run_id`: `None` (form-render fetch is NOT pipeline-bound).

### §1.2 `account_details` — `(positions, account_hash)` discovery (V2 candidate; V1 OUT-OF-SCOPE for T3.SB1)

V1 T3.SB1 does NOT call `account_details`. The account_hash is resolved via the existing `swing/integrations/schwab/auth.py` token-bound state — same way Phase 11 + Phase 12 surfaces resolve it. Brief mentions `account_details(account_hash, fields='positions')` as a forward-binding reference for T3.SB2's exit auto-fill (which may need fresh position quantities to validate partial-exit fill candidates) — V2 candidate dispatch, not T3.SB1 scope.

V1 fallback when account_hash cannot be resolved: short-circuit auto-fill (advisory "Schwab account not yet linked; please complete `swing schwab setup`") — mirrors the DEGRADED-state empty-state handling per spec §6.1.

---

## §2 Schema substrate already landed at v20 (T2.SB1 T-A.1.1)

Per migration `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql` §6 + §7:

### §2.1 `fills` widening (4 new columns)

- `fill_origin TEXT NOT NULL DEFAULT 'operator_typed' CHECK (fill_origin IN ('operator_typed', 'schwab_auto', 'schwab_auto_then_operator_corrected', 'tos_import', 'imported_legacy'))`.
- `schwab_source_value_json TEXT NULL`.
- `operator_corrected_value_json TEXT NULL`.
- `auto_fill_audit_at TEXT NULL`.

DEFAULT clause backfills all existing rows to `'operator_typed'` (faithful to pre-Phase-13 journal-typed-from-memory state; per spec §6.4 + OQ-7 V1 simple).

### §2.2 `schwab_api_calls.surface` CHECK widened 2 → 4 values

- Pre-v20: `('pipeline', 'cli')`.
- Post-v20: `('pipeline', 'cli', 'trade_entry', 'trade_exit')`.

Python-side constant at [swing/integrations/schwab/audit_service.py:48-53](swing/integrations/schwab/audit_service.py#L48) — `_SCHWAB_API_SURFACE_VALUES = ('pipeline', 'cli', 'trade_entry', 'trade_exit')`. Python + schema CHECK landed atomically per CLAUDE.md "Schema-CHECK + Python-constant + dataclass-validator MUST land in the same task for atomic consistency" gotcha.

### §2.3 `review_log` widening (1 new column; T3.SB3 consumes, not T3.SB1)

- `auto_populated_field_keys_json TEXT NULL`.

T3.SB1 does NOT consume this column (T3.SB3 review auto-fill territory).

---

## §3 Response-shape consumption via execution-grain helpers

Per post-Phase-12 Sub-bundle 1 mapper widening + plan §G.2 T-B.1.2 + spec §6.1.

### §3.1 `_compute_execution_price(so: SchwabOrderResponse) -> float | None`

Defined at [swing/trades/schwab_reconciliation.py:99-125](swing/trades/schwab_reconciliation.py#L99). Pure function (no DB, no logging).

Behavior:
- `so.executions is None` OR empty list → returns `None` (caller responsibility: Path B sentinel emit OR fall-through).
- Single leg → returns `executions[0].price`.
- Multi leg → returns VWAP: `sum(leg.price * leg.quantity) / sum(leg.quantity)`.

T3.SB1 consumption: form-render-time auto-fill resolves `entry_price` from this helper, choosing the most recent BUY-instruction execution-bearing order matching the ticker.

### §3.2 `_resolve_match_quantity(so: SchwabOrderResponse) -> float`

Defined at [swing/trades/schwab_reconciliation.py:174-195](swing/trades/schwab_reconciliation.py#L174). Pure function.

Behavior:
- `so.executions` populated (truthy) → returns `sum(leg.quantity for leg in executions)`.
- Else (`None` or empty list) → returns `so.quantity` (V1 fallback).

T3.SB1 consumption: form-render-time auto-fill resolves `initial_shares` (cast to int per existing entry form discipline) from this helper.

### §3.3 `_is_execution_bearing_candidate(o) -> bool`

Defined at [swing/trades/schwab_reconciliation.py:128-171](swing/trades/schwab_reconciliation.py#L128). Pure function.

Behavior:
- `status='FILLED'` AND (`price is not None` OR `executions` non-empty) → True.
- `status='CANCELED'` AND `executions` non-empty → True (partial-then-canceled).
- `status='REPLACED'` AND `executions` non-empty → True (partial-then-replaced).
- All other statuses → False.

T3.SB1 consumption: pre-filter for the order list before scoring by `enter_time` / instruction match. Matches the Sub-bundle 1 comparator pool selection precedent so T3.SB1 + Phase 12 reconciliation see the same fill universe.

### §3.4 BUY-side instruction filter

V1 entry auto-fill filters `instruction in ('BUY', 'BUY_TO_OPEN', 'BUY_TO_COVER')` from the execution-bearing candidate pool. SELL-side filters apply at T3.SB2 (exit auto-fill).

---

## §4 Schwab integration discipline (4-step chain BINDING)

Per CLAUDE.md gotchas + plan §A.11 + spec §6.1 + brief §4:

```python
def resolve_entry_auto_fill(*, ticker: str, cfg, conn) -> EntryAutoFillResult:
    cfg = apply_overrides(cfg)                                            # step 1
    environment = cfg.integrations.schwab.environment
    if environment == 'sandbox':
        return EntryAutoFillResult.sandbox_short_circuit(...)             # short-circuit
    client_id, client_secret = resolve_credentials_env_or_prompt(         # step 2
        cfg, environment, allow_prompt=False,                             # allow_prompt=False BINDING
    )
    if client_id is None or client_secret is None:
        return EntryAutoFillResult.degraded(...)                          # short-circuit
    client = construct_authenticated_client(                              # step 3 (4-arg signature)
        cfg, environment, client_id, client_secret,
    )
    orders = get_account_orders(                                          # step 4
        client, conn, account_hash, from_dt, to_dt,
        surface='trade_entry', environment=environment,
        pipeline_run_id=None, status=None, max_results=None,
    )
    # ... candidate selection + value extraction via _compute_execution_price /
    # _resolve_match_quantity ...
```

Each step is BINDING. `allow_prompt=False` is mandatory — form-render-time stdin prompts would block the HTTP request thread (per CLAUDE.md gotcha).

---

## §5 fill_origin state machine

Per spec §6.1 + §6.4 + plan §E.1 + brief §1.4:

| State | Condition | Persisted at |
|---|---|---|
| `schwab_auto` | Auto-populated AND operator submitted unchanged | `entry_post` |
| `schwab_auto_then_operator_corrected` | Auto-populated AND operator edited any of (entry_date, entry_price, shares) before submit | `entry_post` |
| `operator_typed` | No Schwab fills found OR sandbox short-circuit OR DEGRADED short-circuit OR auto_fill_audit_at IS NULL | `entry_post` |
| `tos_import` | (existing; written by ToS import path; not touched by T3.SB1) | (existing) |
| `imported_legacy` | (existing; backfill marker; not touched by T3.SB1) | (existing) |

T3.SB1 NEW transitions: only `schwab_auto`, `schwab_auto_then_operator_corrected`, `operator_typed`. The 2 legacy values (`tos_import`, `imported_legacy`) are preserved and tested for completeness but not actively written by T3.SB1 surface.

---

## §6 Hidden audit anchors — server-stamped at handler entry

Per CLAUDE.md "For any V1 single-operator form with hidden audit fields, default to SERVER-STAMPING at handler entry; hidden inputs are tampering surfaces" + spec §6.1 + plan §E.6 LOCK + brief §1.4:

- `schwab_source_value_json`: JSON-encoded original auto-populated values (`{"entry_price": 12.34, "shares": 100, "entry_date": "2026-05-19"}`). Server-stamped at form render; preserved verbatim in fills row at POST.
- `auto_fill_audit_at`: ISO timestamp at form-render time. Server-stamped at GET.

Render disposition: display-only `<span class="muted">` text alongside the auto-populated fields. Operator sees what is recorded; operator cannot tamper.

Soft-warn confirm `form_values` round-trip: per CLAUDE.md "Form-render hidden anchors driving POST-time validation MUST round-trip through soft-warn confirm `form_values` dict" + Phase 9 Sub-bundle D R3 Critical #1 + brief §5 watch item 9 — the hidden anchors `schwab_source_value_json` + `auto_fill_audit_at` MUST be included in the soft-warn confirm fragment's `form_values` dict so tampered `force=true` resubmits cannot strip them.

---

## §7 Audit-row emit shape

Per spec §6.1 + plan §G.2 T-B.1.4 + brief §5 watch item 11:

Each `resolve_entry_auto_fill` invocation that actually fires a Schwab API call (i.e., NOT sandbox short-circuit; NOT DEGRADED short-circuit) emits exactly one `schwab_api_calls` row via the existing `swing/integrations/schwab/audit_service.py` wrappers:

- `endpoint='accounts.orders.list'`.
- `surface='trade_entry'` (CHECK widened at v20).
- `status='success'` / `'error'` / `'auth_failed'` / `'rate_limited'` per `_classify_http_failure` outcome.
- `pipeline_run_id=None` (form-render fetch, not pipeline-bound).
- `linked_snapshot_id`, `linked_reconciliation_run_id`, `linked_correction_id` all NULL (entry auto-fill does NOT link to snapshots / reconciliation runs / corrections).
- `signature_hash`: computed via `_compute_signature_hash(payload, endpoint='accounts.orders.list')`.

---

## §8 Empty-state handling

Per spec §6.1:

| Scenario | `EntryAutoFillResult` shape | Audit row emitted? |
|---|---|---|
| Schwab returns ≥1 matching BUY fill | `populated` with values + `fill_origin='schwab_auto'` | Yes |
| Schwab returns ZERO matching fills | `empty` with `fill_origin='operator_typed'` + advisory text "No matching Schwab fills found; please enter manually." | Yes |
| Sandbox short-circuit | `sandbox_short_circuit` + advisory | NO (no Schwab call fired) |
| DEGRADED short-circuit (refresh_token expired / 7-day TTL exhausted) | `degraded` + advisory "Schwab integration degraded; auto-fill unavailable." | NO (no Schwab call fired) |
| `account_hash` unresolvable | `degraded` + advisory "Schwab account not yet linked; please complete `swing schwab setup`." | NO (no Schwab call fired) |

---

## §9 Files in scope

Per plan §G.2 T-B.1.* + brief §1.1:

- Create: `swing/trades/entry_auto_fill.py` (T-B.1.2) — `EntryAutoFillResult` dataclass + `resolve_entry_auto_fill(*, ticker, cfg, conn)` function.
- Modify: `swing/web/routes/trades.py` — `entry_form` (line 343) + `entry_post` (line 358) handlers.
- Modify: `swing/web/view_models/trades.py` — `TradeEntryFormVM` extends `BaseLayoutVM`; add auto_fill_* fields.
- Modify: `swing/web/templates/trades/entry_form.html.j2` (or partials/trade_entry_form.html.j2 — the actual template the entry_form route renders).
- Modify: `swing/data/repos/fills.py` — extend insert path to persist `fill_origin` + `schwab_source_value_json` + `operator_corrected_value_json` + `auto_fill_audit_at`.
- Modify: `swing/integrations/schwab/audit_service.py` — already supports `surface='trade_entry'` per `_SCHWAB_API_SURFACE_VALUES`; no changes needed.
- Create: `tests/trades/test_entry_auto_fill.py` (T-B.1.2).
- Create: `tests/web/test_routes/test_entry_form_auto_fill.py` (T-B.1.3).
- Create: `tests/web/test_routes/test_entry_post_audit_columns.py` (T-B.1.4).
- Create: `tests/integrations/test_schwab_entry_auto_fill_e2e.py` (T-B.1.5; 1 slow E2E).
- Create: `tests/integration/test_phase13_t3_sb1_entry_auto_fill_e2e.py` (T-B.1.6; fast E2E).
- Create: `tests/data/test_phase13_t3_sb1_prerequisite.py` (T-B.1.1; this task).

---

## §10 Cross-bundle pin actions

Per plan §H.3:

| Pin | Action at T3.SB1 |
|---|---|
| `test_schema_version_v20_invariant` (planted at T-A.1.1, currently skipped) | T-B.1.1 **un-skips** (per §H.3 row 2: "Un-skipped at T3.SB1 merge"). |
| `test_fill_origin_enum_complete_after_v20` (planted at T-A.1.1, currently skipped) | T3.SB1 does NOT un-skip (un-skips at T3.SB2 per §H.3 row 4). Test body already verifies the 5 V1 enum values at schema-level; T3.SB1 ensures Python emitter paths exercise the 3 NEW values (`schwab_auto` / `schwab_auto_then_operator_corrected` / `operator_typed`) via T-B.1.2 + T-B.1.4 discriminating tests. |
| `test_pattern_exemplars_schema_shape_invariant` | UNCHANGED (un-skips at T2.SB3 + T2.SB5). |
| `test_v20_atomic_landing_python_constants_validators_paired` | UNCHANGED (un-skips at T4.SB closer). |

---

## §11 18 watch items (per dispatch brief §5)

The dispatch brief enumerates 18 BINDING adversarial-review watch items. The plan §G.2 acceptance criteria pin each. Recapped here for orchestrator-side QA convenience:

1. Plan §G.2 6-task structure integrity (no bundling).
2. T3.SB1 branched off T-A.1.1 SHA (this doc + prerequisite test verify).
3. `construct_authenticated_client` 4-arg signature trace test at T-B.1.2.
4. `resolve_credentials_env_or_prompt(allow_prompt=False)` trace test at T-B.1.2.
5. `apply_overrides(cfg)` at T-B.1.3 entry_form + T-B.1.4 entry_post.
6. HTMX gotcha trinity at T-B.1.3 + T-B.1.4 (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted).
7. Base-layout VM banner pin — `TradeEntryFormVM` populates `unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count` at T-B.1.3.
8. Server-stamping hidden audit fields at T-B.1.3 (display-only `<span class="muted">` text).
9. Soft-warn confirm `form_values` round-trip at T-B.1.5 + T-B.1.4.
10. `fill_origin` enum transitions at T-B.1.4 (3 new values exercised).
11. Schwab audit-row emit `surface='trade_entry'` at T-B.1.4.
12. Synthetic-fixture-vs-production-emitter shape drift: discriminating tests use production response shape via `SchwabOrderResponse` dataclass.
13. No `input()` / `click.prompt` fires inside the HTTP handler at T-B.1.2 trace test.
14. Sandbox short-circuit honored at T-B.1.2.
15. DEGRADED state honored at T-B.1.2.
16. Phase 13 T1.SB0 NEW gotcha #1 — session-anchor inequality discipline (T-B.1.2 lookback window uses `now()`-based bounds; not session-anchor-dependent — N/A for T3.SB1 in practice but documented for completeness).
17. Cross-bundle pin `test_fill_origin_enum_complete_after_v20` planted at T-A.1.1 (NOT T-B.1.2 as the dispatch brief stated; see §10 above for nuance — body is already correct, T3.SB1 exercises the 3 NEW emitter paths).
18. Implementer self-report accuracy gate at return report.

---

## §12 Open-question dispositions inherited

- **OQ-12 (concurrent dispatch coordination)**: Option E — T3.SB1 branches off T2.SB1's T-A.1.1 commit SHA. Merge ordering: T2.SB1 first; T3.SB1 second.
- **OQ-7 (fill_origin V1 backfill)**: V1 simple — all existing rows get `'operator_typed'` via DEFAULT clause; historical reconciliation_corrections rows leave-as-is.
- **OQ-F (Pass-2 tier-1 lift)**: V2-deferred; T3.SB1 does NOT touch reconciliation_classifier.

---

## §13 Forward-binding pins for downstream sub-bundles

- **T3.SB2 inherits**: the same `resolve_credentials_env_or_prompt(allow_prompt=False)` + `construct_authenticated_client` 4-arg + `apply_overrides(cfg)` 4-step chain at every Schwab entry point. T3.SB2's exit auto-fill consumes SELL-side instructions (`'SELL', 'SELL_TO_OPEN', 'SELL_TO_CLOSE', 'SELL_SHORT'`) from the same execution-grain helpers.
- **T3.SB2 also un-skips** `test_fill_origin_enum_complete_after_v20`.
- **Phase 13 T1.SB0 NEW gotcha #1**: `client.price_history(...)` MUST pass explicit `period_type` / `period` / `frequency_type` / `frequency` kwargs. T3.SB1 does NOT consume `price_history` (consumes `account_orders` for fills) — but the discipline is forward-binding for any future Schwab Market Data API consumer.

---

*End of recon. Next: T-B.1.2 — `swing/trades/entry_auto_fill.py` Schwab fetch + value resolution.*
