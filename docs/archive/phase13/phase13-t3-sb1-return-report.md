# Return report — Phase 13 T3.SB1

## Sub-bundle location

**Worktree branch:** `phase13-t3-sb1-entry-auto-fill` at `.worktrees/phase13-t3-sb1-entry-auto-fill/`.

**Branch base:** T2.SB1's T-A.1.1 commit SHA = `4cfd5f2ca9b0103231fb558b141cd87132939d12` (per OQ-12 Option E concurrent dispatch; spec §1.4 + plan §B.2 + dispatch brief §1.2). NOT branched off main HEAD — `git merge-base --is-ancestor 4cfd5f2 HEAD` verified at T-B.1.1 prerequisite test `tests/data/test_phase13_t3_sb1_prerequisite.py:test_t_a_1_1_sha_is_branch_base`.

**Commits on branch** (10 commits):

| SHA | Commit subject |
|---|---|
| `2f987a9` | `docs(phase13): T3.SB1 recon + v20 prerequisite test (T-B.1.1)` |
| `9f77871` | `feat(phase13): swing/trades/entry_auto_fill.py — Schwab fetch + value resolution (T-B.1.2)` |
| `e86658b` | `feat(phase13): /trades/entry/form auto-fill integration (T-B.1.3)` |
| `b8de30e` | `feat(phase13): entry_post fill_origin transition + audit columns + soft-warn confirm (T-B.1.4)` |
| `cf16cea` | `test(phase13): T3.SB1 trade_entry slow E2E (T-B.1.5)` |
| `d20d801` | `test(phase13): T3.SB1 closer — entry auto-fill E2E + ruff sweep (T-B.1.6)` |
| `1908d7f` | `fix(phase13): T3.SB1 Codex R1 majors — anchor consistency check + re-render preservation` |
| `a966a57` | `fix(phase13): T3.SB1 Codex R2 majors — non-dict + missing-key anchor rejects + kind/advisory preservation on retry + early-validation anchor preservation` |
| `1ad24a1` | `fix(phase13): T3.SB1 Codex R3 majors+minor — value validation (NaN/non-int/bad-date) + clear-bad-anchor on rejection + whitespace normalization` |
| `ea067f7` | `fix(phase13): T3.SB1 Codex R4 majors+minor — require claim for schwab provenance + calendar-valid date + claim consistency in enum-coverage test` |

(Return report commit follows this report.)

ZERO `Co-Authored-By` footer trailer drift across all 10 commits (cumulative ~221+ commits CLEAN streak preserved).

---

## Codex review history

| Round | Verdict | Findings | Disposition |
|---|---|---|---|
| Pre-Codex (orchestrator-side review per C.C lesson #6 BINDING) | CLEAN | 0 Critical / 0 Major / 0 Minor (1 V2-bankable observation) | **14th cumulative C.C lesson #6 validation CLEAN** (matches 13-prior pattern) |
| R1 | ISSUES_FOUND | 1 Critical, 5 Major, 2 Minor | 1 Accepted (V1 threat model) + 3 Resolved + 2 Accepted (project convention) + 2 Minor banked |
| R2 | ISSUES_FOUND | 3 Major, 1 Minor | 3 Resolved + 1 Resolved |
| R3 | ISSUES_FOUND | 2 Major, 1 Minor | 2 Resolved + 1 Resolved |
| R4 | ISSUES_FOUND | 2 Major, 1 Minor | 1 Resolved + 1 Accepted + 1 Resolved |
| R5 | **NO_NEW_CRITICAL_MAJOR** | 0 Critical, 0 Major, 2 Minor (V2-banked) | TERMINATED |

**Final verdict: NO_NEW_CRITICAL_MAJOR** at R5. All Critical + Major issues resolved or accepted. 5 Minors banked (2 from R5 + 2 from R1 + 1 from R3) as V2 candidates.

---

## Schwab integration discipline verified

- **`apply_overrides(cfg)` at handler entry** ✅ — `swing/web/routes/trades.py:344` (entry_form) + `swing/web/routes/trades.py:451` (entry_post). Brief watch item 5.
- **`resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)`** ✅ — `swing/trades/entry_auto_fill.py:307`. `allow_prompt=False` BINDING per CLAUDE.md gotcha "form-render-time prompts would block HTTP handler". Mock-verified at `tests/trades/test_entry_auto_fill.py:test_e_credential_resolver_invoked_with_allow_prompt_false`. Brief watch items 4 + 13.
- **`construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg signature** ✅ — `swing/trades/entry_auto_fill.py:340`. Per post-Phase-12 Sub-bundle 1 + forward-binding lesson #10. Mock-verified at `tests/trades/test_entry_auto_fill.py:test_f_client_factory_invoked_with_4_arg_signature`. Brief watch item 3.
- **`trader.get_account_orders(surface='trade_entry')`** ✅ — `swing/trades/entry_auto_fill.py:368`. surface CHECK enum widened at v20 migration to include `trade_entry` + `trade_exit`. Mock-verified at `tests/trades/test_entry_auto_fill.py:test_f_audit_surface_is_trade_entry`. Brief watch item 11.
- **HTMX gotcha trinity** ✅ — `hx-headers='{"HX-Request": "true"}'` propagation at `swing/web/templates/partials/trade_entry_form.html.j2:40`. HX-Redirect N/A (route returns row-swap partial, not 303/204). Verified at `tests/web/test_routes/test_entry_form_auto_fill.py:test_htmx_gotcha_trinity_preserved`. Brief watch item 6.
- **Base-layout VM banner pin** ✅ — `TradeEntryFormVM` populates `unresolved_material_discrepancies_count` + `recent_multi_leg_auto_correction_count` + `banner_resolve_link` at `swing/web/view_models/trades.py:357-360`. Defaults match `BaseLayoutVM`. Verified at `tests/web/test_routes/test_entry_form_auto_fill.py:test_e_vm_has_banner_pin_field_defaults` + `test_f_vm_populates_banner_pin_fields_from_helpers`. Brief watch item 7. **NOTE:** VM does NOT inherit `BaseLayoutVM` — project convention is field-duplication (per CLAUDE.md "base.html.j2 is shared — new vm.foo field requires adding to EVERY base-layout VM"). Codex R1 Major #4 flagged the divergence from plan §G.2 line 1405 wording; ACCEPTED with rationale that project convention is duplication (5 prior base-layout VMs all duplicate, none inherit).
- **Sandbox short-circuit** ✅ — `swing/trades/entry_auto_fill.py:245-253`. Fires BEFORE any Schwab client construction; verified at `tests/trades/test_entry_auto_fill.py:test_c_sandbox_short_circuits` + `tests/integrations/test_schwab_entry_auto_fill_e2e.py:test_entry_form_e2e_sandbox_does_not_emit_audit_row`. Brief watch item 14.
- **DEGRADED state short-circuit** ✅ — `swing/trades/entry_auto_fill.py:275-288` via `cli_schwab._compute_degraded_state`. Both DEGRADED + PROVISIONAL fire short-circuit. Verified at `tests/trades/test_entry_auto_fill.py:test_d_degraded_short_circuits` + `test_d_provisional_treated_as_degraded`. Brief watch item 15.

---

## `fill_origin` enum transitions tested

All 5 V1 values exercised:

- ✅ `schwab_auto` (auto-populated, unmodified) — `tests/web/test_routes/test_entry_post_audit_columns.py:test_a_unchanged_auto_fill_persists_schwab_auto`
- ✅ `schwab_auto_then_operator_corrected` (auto-populated then operator overrode) — `test_b_edited_price_flips_to_then_operator_corrected` + `test_b_edited_shares_flips_to_then_operator_corrected` + `test_b_edited_entry_date_flips_to_then_operator_corrected`
- ✅ `operator_typed` (never auto-populated OR operator cleared OR claim absent) — `test_c_no_anchor_persists_operator_typed` + `test_c_empty_anchor_string_persists_operator_typed` + `test_c_valid_anchor_without_claim_persists_operator_typed`
- ✅ `tos_import` (existing; CHECK enum membership verified in schema)
- ✅ `imported_legacy` (existing; CHECK enum membership verified in schema)

All-3-new-values end-to-end coverage: `test_fill_origin_enum_all_three_new_values_persistable_via_route`.

---

## Test count pre/post

| Stage | Fast tests | Slow tests | Notes |
|---|---|---|---|
| Pre-baseline (T-A.1.1 SHA `4cfd5f2`) | ~4939 | (existing) | Phase 13 brainstorm + writing-plans baseline |
| Post-T3.SB1 (`ea067f7`) | **5006** (+67) | **3 new** (+2 slow E2E + 1 fast E2E covered by 5006) | within +40-70 fast projection |
| Delta | +67 fast tests + 2 slow Schwab E2E tests + 5 skipped (cross-bundle pins) | +1 calendar-day | ZERO regressions on pre-existing tests |

Fast suite runtime: ~90 seconds. Slow E2E runtime: ~8 seconds.

LOC delta (per `git diff --stat 4cfd5f2..HEAD`):

| Bucket | Insertions | Files |
|---|---|---|
| Production (`swing/...`) | ~700 LOC | 5 modified + 1 created |
| Test (`tests/...`) | ~2500 LOC | 6 created |
| Documentation (`docs/...`) | ~500 LOC | 2 created (recon + return report) |
| Template (`swing/web/templates/...`) | ~50 LOC | 1 modified |
| **Total** | **+4208 / -25** | **14 files** |

---

## Operator-witnessed gate results

| Stage | Status | Notes |
|---|---|---|
| S1 (inline pytest + ruff) | **PASS** | 5006 fast tests / 5 skipped (cross-bundle pins) + 3 slow E2E + ruff clean on all 14 changed files. |
| S2 (`python -m swing.cli web` + `/trades/entry/form` operator-paired) | **PENDING POST-MERGE** | Brief §1.4 — operator-paired browser session required for S2 after T2.SB1 merges first. |
| S3 (entry POST operator-paired with Schwab auto-fill) | **PENDING POST-MERGE** | Brief §1.4 — operator-paired browser session required for S3 after T2.SB1 merges first. |

---

## Cross-bundle pin disposition

| Pin | Action at T3.SB1 |
|---|---|
| `test_schema_version_v20_invariant` (planted at T-A.1.1) | **UN-SKIPPED** at T-B.1.1 — per plan §H.3 row 2 ("Un-skipped at T3.SB1 merge"). Test body verifies `schema_version == 20` end-to-end. |
| `test_fill_origin_enum_complete_after_v20` (planted at T-A.1.1) | **STAYS SKIPPED** — un-skips at T3.SB2 merge per plan §H.3 row 4. T3.SB1 exercises the 3 NEW enum emitter paths via T-B.1.4 discriminating tests; T3.SB2 will exercise the SELL-side complement. |
| `test_pattern_exemplars_schema_shape_invariant` | UNCHANGED — un-skips at T2.SB3 + T2.SB5. |
| `test_v20_atomic_landing_python_constants_validators_paired` | UNCHANGED — un-skips at T4.SB closer. |

---

## V2.1 §VII.F amendment candidates banked

None. T3.SB1 ships within the operator-confirmed brainstorm spec scope; no methodology-reference deviations surfaced during execution.

---

## Forward-binding lessons for downstream sub-bundles

1. **`resolve_credentials_env_or_prompt(allow_prompt=False)` discipline** at form-render-time entry points BINDING. T3.SB2 exit auto-fill inherits verbatim.
2. **`construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg signature** BINDING. T3.SB2 inherits.
3. **`apply_overrides(cfg)` at handler entry** BINDING. Web counterparts of all future Schwab routes inherit.
4. **Hidden anchor consistency check + value validation pattern** (NEW for T3.SB1; Codex R1-R4 hardening): when any web form has hidden audit anchors driving POST-time validation, the 4-tier rejection ladder is REQUIRED — (a) malformed/non-dict JSON when claim present, (b) dict missing required keys when claim present, (c) dict with invalid values (NaN, non-int, calendar-invalid) when claim present, (d) empty anchor when claim present. The `_reject_anchor` helper pattern clears the bad anchor on recovery form so operator gets fresh state. T3.SB2 + T3.SB3 + future Schwab-integrated forms inherit.
5. **Soft-warn confirm `form_values` round-trip** — all 3 hidden anchors (schwab_source_value_json + auto_fill_audit_at + fill_origin_at_form_render) added to `swing/web/routes/trades.py` soft-warn fragment per Phase 9 Sub-bundle D R3 Critical #1 LOCK. T3.SB2 exit-side soft-warn (if introduced) inherits.
6. **Schema-version-aware INSERT pattern** at `swing/data/repos/fills.py:insert_fill_with_event` via PRAGMA table_info — preserves backward-compat with pre-v20 test fixtures. Pattern recurs at any future fills-column-widening migration.
7. **`fill_origin_at_form_render` consistency-check anti-forgery gate** (Codex R4 Major #1 RESOLVED): require `claimed_auto_fill` before any non-operator_typed fill_origin stamping. T3.SB2 + T3.SB3 inherit verbatim.
8. **Pre-Codex orchestrator-side review** per C.C lesson #6 BINDING — 14th cumulative validation CLEAN. T2.SB1 + T3.SB2 + downstream sub-bundles inherit.

---

## Capture-needs for next sub-bundle dispatch

**For T3.SB2 (exit auto-fill) dispatch brief:**
- T3.SB2 worktree branches from main HEAD AFTER T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 merge per scope-brainstorm §0.5.2 dispatch sequence ("T3.SB2 dispatches AFTER T2.SB3 to avoid Schwab Trader API consumer merge conflicts").
- T3.SB2 inherits T3.SB1's hidden-anchor + value-validation discipline verbatim; the 4-tier rejection ladder + `_reject_anchor` helper pattern is forward-binding.
- T3.SB2 un-skips `test_fill_origin_enum_complete_after_v20` cross-bundle pin per plan §H.3 row 4.
- T3.SB2 spec §6.2 hand-off: SELL-side instruction filter (`SELL`, `SELL_TO_OPEN`, `SELL_TO_CLOSE`, `SELL_SHORT`) symmetric to T3.SB1's BUY-side. Partial-exit handling per spec §6.2 paragraph 2.
- T3.SB2 audit row: `surface='trade_exit'` (CHECK enum already widened at v20).

**For ANY future Schwab API consumer dispatch:**
- explicit `period_type` / `period` / `frequency_type` / `frequency` kwargs on `client.price_history(...)` per CLAUDE.md gotcha "Schwab `price_history` API defaults to minute bars" (2026-05-19 NEW). T3.SB1 consumes `account_orders` (not price_history) so this didn't apply directly, but T3.SB2 / T3.SB3 / T2.SB6 may.

---

## Outstanding capture-needs that DEFER

1. **V2 hidden-anchor architectural hardening** (Codex R1 Critical #1 ACCEPTED rationale): replace hidden `schwab_source_value_json` transport with `schwab_api_call_id` server-side audit-row lookup. Use `get_account_orders_audited` (Phase 12 Sub-bundle C.D precedent) to thread the call_id through `EntryAutoFillResult.schwab_api_call_id` → template hidden input → POST verifies the audit row exists with `surface='trade_entry'` + recent timestamp + ticker match. Approximate scope: 30-50 LOC dispatch with its own 2-3 Codex rounds. Banked for V2.
2. **VM inheritance refactor** (Codex R1 Major #4 ACCEPTED): all 6 base-layout VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`, `TradeEntryFormVM`) inherit from `BaseLayoutVM` in a single sweep. Closes the "duplication drift" failure mode permanently. Banked for V2.
3. **Schwab Trader API lookback widening** (Codex R1 Major #5 ACCEPTED): expand lookback to cover GTC / staged orders + select by execution leg time. Banked for V2 dispatch.
4. **Fractional-share support** (Codex R1 Minor #1 BANKED): replace `int(quantity)` truncation in 6+ adapters across the codebase per CLAUDE.md Phase 7 Sub-C Codex R1 Major 3 disposition. Banked for V2.
5. **PRAGMA table_info → connection-level capability cache** (Codex R1 Minor #2 BANKED): replace per-insert PRAGMA with connection-cached schema-version detection. Banked for V2; required only if performance profiling shows the PRAGMA call is a hot-path bottleneck (unlikely on V1 single-operator workload).
6. **R5 Minor #1**: empty-anchor-with-claim recovery route through `_reject_anchor` for UX consistency. Banked for V2.
7. **R5 Minor #2**: combine length-check + `date.fromisoformat` for strict `YYYY-MM-DD` validation on Python 3.11+. Banked for V2 defense-in-depth.
8. **V2 candidate: "Reset to Schwab values" button on rejection-recovery form** (Codex R4 Major #2 ACCEPTED rationale): explicit UX affordance for operator to discard their typed values + accept the fresh Schwab anchor. Banked for V2.

---

## NEW CLAUDE.md gotchas surfaced during T3.SB1

(Banked for post-merge housekeeping discipline per orchestrator routine.)

1. **Schema-version-aware INSERT for newly-widened columns** — when a migration widens a table with new NOT-NULL-DEFAULTED columns, the repo INSERT path must detect schema version via `PRAGMA table_info` AND branch between legacy-column-list and new-column-list INSERTs OR all pre-current-version test fixtures must migrate up. T3.SB1 chose the runtime branch at `swing/data/repos/fills.py:51-53` to preserve ~30 pre-v20 fixtures unchanged. Forward-binding lesson: any future migration that adds NOT-NULL-DEFAULTED columns inherits this pattern OR commits to a fixture-update sweep.

2. **Hidden anchor 4-tier rejection ladder** (NEW; Codex R1-R4 hardening): when a web form has hidden audit anchors driving POST-time provenance stamping, the canonical pattern is the 4-tier rejection: (a) malformed JSON → 400 + clear anchor on recovery; (b) non-dict JSON → 400 + clear; (c) dict missing required keys → 400 + clear; (d) dict with invalid value shapes (NaN, non-int, calendar-invalid date) → 400 + clear. The `_reject_anchor` helper pattern at `swing/web/routes/trades.py:880-901` is the reusable template. Plus a `claimed_auto_fill` consistency-check gate prevents anti-forgery (valid anchor without claim must NOT stamp provenance).

3. **Recovery form anchor-clear discipline** (NEW; Codex R3 Major #2 RESOLVED): on anchor-rejection 400 responses, the recovery form MUST clear the bad anchor (pass `submitted_*=None` to the re-render helper, NOT the raw rejected anchor) — otherwise the operator gets trapped in repeated 400s when their next submit replays the same bad anchor. Forward-binding for any form-rejection path that emits a recovery form.

These will be added to the project CLAUDE.md Gotchas section at post-merge housekeeping per orchestrator's standard routine.

---

*End of return report. Phase 13 T3.SB1 SHIPPED. Branch base SHA `4cfd5f2ca9b0103231fb558b141cd87132939d12`. 10 commits + ZERO Co-Authored-By footer drift + 5006 fast tests + NO_NEW_CRITICAL_MAJOR at Codex Round 5 + 14th cumulative C.C lesson #6 validation CLEAN.*
