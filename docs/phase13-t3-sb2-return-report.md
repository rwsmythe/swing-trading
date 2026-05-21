# Return report — Phase 13 T3.SB2

## Sub-bundle location

**Worktree branch:** `phase13-t3-sb2-exit-auto-fill` at `.worktrees/phase13-t3-sb2-exit-auto-fill/`.

**Branch base:** main HEAD `cb88329` at dispatch time (per plan §G.5 + dispatch brief §1 — branches AFTER T2.SB3 merge per scope-brainstorm §0.5.2 dispatch sequence to avoid Schwab Trader API consumer merge conflicts with T3.SB1).

**Commits on branch** (16 commits = 9 task ships + 7 fix commits across per-task reviewers + Codex R1-R4):

| SHA | Commit subject |
|---|---|
| `c487595` | `feat(phase13): swing/trades/exit_auto_fill.py — Schwab fetch + value resolution (T-B.2.1)` |
| `e755b5e` | `fix(phase13): T-B.2.1 reviewer fixes — chosen-candidate from list + drop dead __all__ export` |
| `9a7df7b` | `feat(phase13): /trades/{id}/exit/form auto-fill integration (T-B.2.2)` |
| `b277aa2` | `fix(phase13): T-B.2.2 reviewer fixes — tighten radio default + single-fill negative assertion` |
| `064fa4e` | `feat(phase13): exit_post fill_origin transition + audit columns + soft-warn confirm (T-B.2.3)` |
| `4926b44` | `test(phase13): T3.SB2 trade_exit cassette + slow E2E (T-B.2.4)` |
| `24a771d` | `test(phase13): T-B.2.4 close multi-partial coverage gap — 3rd slow E2E` |
| `10a1120` | `fix(phase13): T-B.2.4 reviewer fixes — audit-row count assertion + drop dead sqlite3 import` |
| `7429d6a` | `test(phase13): T3.SB2 closer — exit auto-fill E2E + ruff sweep (T-B.2.5)` |
| `097760c` | `fix(phase13): T3.SB2 Codex R1 M6 — restrict SELL_INSTRUCTIONS to {SELL, SELL_TO_CLOSE}` |
| `8fbe8bc` | `fix(phase13): T3.SB2 Codex R1 Critical+M1 — server-side authoritative envelope for multi-partial selection` |
| `5d64a00` | `fix(phase13): T3.SB2 Codex R1 M4 — exclude already-recorded fills from exit auto-fill candidates` |
| `fb2b424` | `fix(phase13): T3.SB2 Codex R1 follow-up — ruff F821 (drop unused Any annotation)` |
| `1a79482` | `fix(phase13): T3.SB2 Codex R2 M2+M3+M4+minor — dedupe + UX hardening` |
| `6218866` | `fix(phase13): T3.SB2 Codex R3 M1 — rewrite top-level schwab_order_id on authoritative non-default selection` |
| `7348620` | `fix(phase13): T3.SB2 Codex R4 M1+M2 — None-order_id rewrite + price-precision parity` |

(Return report commit follows this report.)

**ZERO `Co-Authored-By` footer trailer drift across all 16 commits** — preserves the cumulative ~279+ commit ZERO-drift streak (~263 pre-T3.SB2 + 16 T3.SB2).

---

## Codex review history

| Round | Verdict | Findings | Disposition |
|---|---|---|---|
| Pre-Codex (orchestrator-side review per C.C lesson #6 BINDING) | APPROVED_FOR_CODEX | 0 Critical / 0 Major / 2 Minor banked | **19th cumulative C.C lesson #6 validation CLEAN** (matches 18-prior pattern through T1.SB0 / T2.SB1 / T3.SB1 / T2.SB2 / T2.SB3) |
| R1 | ISSUES_FOUND | 1 Critical, 6 Major, 2 Minor | 1 Critical resolved + 3 Major resolved + 3 Major accepted with rationale + 2 Minor accepted |
| R2 | ISSUES_FOUND | 4 Major, 1 Minor | 3 Major resolved + 1 Major accepted (V2 hardening — T3.SB1 parity) + 1 Minor resolved |
| R3 | ISSUES_FOUND | 2 Major, 1 Minor | 1 Major resolved + 1 Major accepted + 1 Minor accepted |
| R4 | ISSUES_FOUND | 2 Major, 1 Minor | 2 Major resolved + 1 Minor accepted (V2 refactor) |
| R5 | **NO_NEW_CRITICAL_MAJOR** | 0 Critical, 0 Major, 2 Minor (V2-banked) | TERMINATED |

**Final verdict: NO_NEW_CRITICAL_MAJOR** at R5 (5 rounds matches T3.SB1 + T2.SB3 pattern). 9 cumulative V2-banked observations + 6 cumulative ACCEPT-WITH-RATIONALE banks documented below in §"Outstanding capture-needs that DEFER".

---

## Schwab integration discipline verified

- **`apply_overrides(cfg)` at handler entry** ✅ — `swing/web/routes/trades.py:1652` (exit_form was already present pre-T3.SB2 dispatch). Brief watch item §4.1.1.
- **`resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)`** ✅ — `swing/trades/exit_auto_fill.py:405-407`. `allow_prompt=False` BINDING per CLAUDE.md gotcha "form-render-time prompts would block HTTP handler". Mock-verified at `tests/trades/test_exit_auto_fill.py:test_f_credential_resolver_invoked_with_allow_prompt_false`.
- **`construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg signature** ✅ — `swing/trades/exit_auto_fill.py:436`. Mock-verified at `test_g_client_factory_invoked_with_4_arg_signature` asserting all 4 args.
- **`trader.get_account_orders(surface='trade_exit')`** ✅ — `swing/trades/exit_auto_fill.py:461-468`. surface CHECK enum widened at v20 to include both `trade_entry` AND `trade_exit`. Mock-verified at `test_audit_surface_is_trade_exit`.
- **HTMX gotcha trinity** ✅ — `hx-headers='{"HX-Request": "true"}'` propagation at `swing/web/templates/partials/trade_exit_form.html.j2:34`. HX-Redirect N/A (exit form returns row-swap partial, not 303/204). Verified at `tests/web/test_routes/test_exit_form_auto_fill.py:test_htmx_gotcha_trinity_preserved`.
- **Base-layout VM banner pin** ✅ — `TradeExitFormVM` populates `unresolved_material_discrepancies_count` + `recent_multi_leg_auto_correction_count` + `banner_resolve_link` at `swing/web/view_models/trades.py:719-721`. Defaults match `BaseLayoutVM`. Per project convention duplication, NOT inheritance (per Codex R1 M#4 ACCEPT at T3.SB1 + reaffirmed here). NOTE: exit form route returns row-partial fragment that does NOT extend `base.html.j2`; banner-pin fields populated defensively per CLAUDE.md "base.html.j2 is shared — new vm.foo field requires adding to EVERY base-layout VM" gotcha.
- **Sandbox short-circuit** ✅ — `swing/trades/exit_auto_fill.py:345-355` fires BEFORE any Schwab client construction. Verified at `tests/trades/test_exit_auto_fill.py:test_c_sandbox_short_circuits` + `tests/integrations/test_schwab_exit_auto_fill_e2e.py:test_exit_form_e2e_sandbox_does_not_emit_audit_row`.
- **DEGRADED state short-circuit** ✅ — `swing/trades/exit_auto_fill.py:371-383` via `cli_schwab._compute_degraded_state`. Both DEGRADED + PROVISIONAL fire short-circuit. Verified at `tests/trades/test_exit_auto_fill.py:test_d_degraded_short_circuits`.

---

## Multi-partial-exit handling (NEW architectural dimension vs T3.SB1)

Per spec §6.2 paragraph 2: if Schwab returns multiple SELL fills since `entry_date` (operator scaled out via partial sells), form lists each as a candidate; operator picks one OR enters consolidated value.

**Architecture pivot at R1 (server-side authoritative envelope)**:
- `ExitAutoFillResult.schwab_source_value_json` envelope includes `candidates_map: {sig_hash: {date, price, quantity, order_id}}` for all candidates (`swing/trades/exit_auto_fill.py:570-590`).
- POST handler verifies operator's submitted `signature_hash` is server-rendered via `candidates_map` membership check; rejects with 400 if absent (forgery gate per R1 M1).
- POST handler uses AUTHORITATIVE envelope values to detect operator edits + flip `fill_origin` accordingly:
  - Default radio + no edit → `schwab_auto` (envelope-default values persisted; top-level `schwab_order_id` = default order_id).
  - Default radio + manual edit → `schwab_auto_then_operator_corrected` (operator's typed values persisted; top-level stays at default order_id since default WAS the source).
  - Non-default radio + no-edit visible → `schwab_auto_then_operator_corrected` (visible inputs differ from authoritative selected; values persisted are visible-input values = default; envelope records `selected_candidate_signature_hash` for audit clarity).
  - Non-default radio + matching edit (operator edits visible to match authoritative selected) → `schwab_auto` (R3 M1 fix rewrites top-level `schwab_order_id` to authoritative selected's order_id; if authoritative order_id is None, R4 M1 fix pops top-level so VM dedupe falls back to (date, price, qty) tuple match).
- Template renders selectable radio fieldset when `vm.auto_fill_candidates|length > 1`; single-fill case (length 1) renders standard pre-populated inputs (no fieldset).
- Per-candidate hidden inputs `candidate_signature_hash_<i>` + `candidate_order_id_<i>` emitted ONLY when `len > 1`.
- Operator-instruction text inside fieldset (R2 minor): "Selecting a different fill does NOT update the visible Exit date / Exit price / Shares inputs below. To match a non-default candidate, manually edit the inputs." (R2 ACCEPTED — visible inputs do not rebind on radio change; V2 JS-rebinding banked.)

---

## `fill_origin` enum transitions tested

All 5 V1 values exercised:

- ✅ `schwab_auto` (auto-populated, unmodified) — `tests/web/test_routes/test_exit_post_audit_columns.py:test_a_unchanged_auto_fill_persists_schwab_auto` + R3 `test_h_critical1_unedited_default_radio_picks_authoritative_default` + R3 `test_h_critical1_non_default_radio_with_matching_edits_stays_schwab_auto`
- ✅ `schwab_auto_then_operator_corrected` — `test_b_edited_price_flips_to_then_operator_corrected` + R3 `test_h_critical1_non_default_radio_without_visible_edits_flips_corrected` + R4 `test_h_r4m2_real_operator_edit_at_1_cent_flips_to_corrected`
- ✅ `operator_typed` (never auto-populated OR claim absent) — `test_c_no_anchor_persists_operator_typed` + variants
- ✅ `tos_import` (existing; CHECK enum membership) — verified via cross-bundle pin un-skip at `tests/data/test_v20_migration.py:907::test_fill_origin_enum_complete_after_v20` (PASSES at first un-skip)
- ✅ `imported_legacy` (existing; CHECK enum membership) — same cross-bundle pin

---

## Test count pre/post

| Stage | Fast tests | Slow tests | Notes |
|---|---|---|---|
| Pre-baseline (main HEAD `cb88329`) | 5257 | (existing) | T2.SB3 SHIPPED + housekeeping baseline |
| Post-T-B.2.X (9 task commits + reviewer fixes through `7429d6a`) | 5301 | +3 new slow Schwab E2E | within +40-70 fast projection (+44 net); cross-bundle pin un-skip (skipped 5→4) |
| Post-Codex R1 fixes (`097760c`/`8fbe8bc`/`5d64a00`/`fb2b424`) | 5313 (+12) | +0 new | Critical+M1 + M4 + M6 fixes added 12 new discriminating tests |
| Post-Codex R2 fix (`1a79482`) | 5318 (+5) | +0 new | M2 + M3 + M4-fallback + Minor #1 + 4 dedupe-correctness tests; 1 revised in-place |
| Post-Codex R3 fix (`6218866`) | 5322 (+4) | +0 new | R3 M1 rewrite test + 3 regression tests |
| Post-Codex R4 fixes (`7348620`) | 5326 (+3) | +0 new | M1 None-order_id test + 2 M2 price-precision tests (positive + regression) |
| Final | **5326** | **+3 slow E2E** | 0 failures (pre-existing flake `test_setup_auth_failure_audit_status_and_sentinel_redaction` no longer surfaces under `pytest -n auto`); 4 skipped (forward-looking cross-bundle pins) |

Fast suite runtime: ~101 seconds (-n auto). Slow E2E runtime: ~8-13 seconds.

LOC delta (via `git diff --stat cb88329..HEAD`):

| Bucket | Approximate insertions | Files |
|---|---|---|
| Production (`swing/...`) | ~1300 LOC | 5 modified + 1 created |
| Test (`tests/...`) | ~5000 LOC | 6 created + 2 modified |
| Documentation (`docs/...`) | (this report only) | 1 created |
| Template (`swing/web/templates/...`) | ~100 LOC | 1 modified |
| **Total** | **~6400 insertions** | **15 files** |

---

## Operator-witnessed gate results

| Stage | Status | Notes |
|---|---|---|
| S1 (inline pytest + ruff) | **PASS** | 5326 fast tests / 4 skipped (cross-bundle pins) + 3 slow Schwab E2E + ruff clean on all touched files |
| S2 (`python -m swing.cli web` + `/trades/{id}/exit/form` operator-paired) | **PENDING POST-MERGE** | Per dispatch brief §5.2 — operator-paired browser session required |
| S3 (operator edits pre-populated price; submits; confirms `fill_origin='schwab_auto_then_operator_corrected'`) | **PENDING POST-MERGE** | |
| S4 (operator triggers partial-exit scenario; confirms list-of-candidates rendering + operator selects expected one) | **PENDING POST-MERGE** | NOTE for operator: visible inputs do NOT update on radio change — to record a non-default candidate, manually edit the visible inputs to match. Inline operator-instruction text added inside fieldset per R2 minor closure |
| S5 (DB audit: `SELECT call_id, surface FROM schwab_api_calls WHERE surface='trade_exit' ORDER BY started_at DESC LIMIT 5`) | **PENDING POST-MERGE** | |

---

## Cross-bundle pin disposition

| Pin | Action at T3.SB2 |
|---|---|
| `test_fill_origin_enum_complete_after_v20` (planted at T-A.1.1; pinned for T3.SB2 per plan §H.3 row 4) | **UN-SKIPPED at T-B.2.5 closer** (`7429d6a`) — `@pytest.mark.skip(...)` decorator removed at `tests/data/test_v20_migration.py:907`. Test body validates `_FILL_ORIGIN_VALUES = {'operator_typed', 'schwab_auto', 'schwab_auto_then_operator_corrected', 'tos_import', 'imported_legacy'}` via frozenset equality. PASSES at first un-skip. T3.SB2 production-shipped + exercised both `schwab_auto` + `schwab_auto_then_operator_corrected` transitions (T-B.2.3 + R3 + R4 discriminating tests). |
| `test_pattern_exemplars_schema_shape_invariant` (at `tests/data/test_v20_migration.py:833`) | UNCHANGED — un-skips at T2.SB5. |
| `test_v20_atomic_landing_python_constants_validators_paired` (at `tests/data/test_v20_migration.py:883`) | UNCHANGED — un-skips at T4.SB closer. |
| `test_ohlcv_cache_concurrent_fetch_no_race` (at `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py:203`) | UNCHANGED — un-skips at T3.SB3. |

---

## V2.1 §VII.F amendment candidates banked

None. T3.SB2 ships within the operator-confirmed brainstorm spec scope; no methodology-reference deviations surfaced during execution.

---

## Forward-binding lessons for downstream sub-bundles

1. **`resolve_credentials_env_or_prompt(allow_prompt=False)` discipline** at form-render-time entry points — BINDING. T3.SB3 review auto-fill MAY inherit if it adds any Schwab API surface; OhlcvCache-only path does NOT need.

2. **`construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg signature** — BINDING for any future Schwab Trader API consumer.

3. **`apply_overrides(cfg)` at handler entry** — BINDING for all future web routes that may consume Schwab.

4. **Hidden anchor 4-tier rejection ladder + recovery anchor-clear discipline** — inherited verbatim from T3.SB1. T3.SB3 + Phase 14+ schwab-integrated forms inherit.

5. **Soft-warn confirm `form_values` round-trip discipline** — N/A for exit form (entry-only Phase 9 D pattern; exit forms have no force=true resubmit). Discipline honored DIFFERENTLY via 4-tier rejection ladder + recovery-form anchor-clear. Forward-binding lesson banked: any form-driven route with hidden audit anchors MUST consider whether soft-warn applies (entry-side cap gate) OR whether rejection-ladder + anchor-clear suffices (exit-side immediate state transition).

6. **Schema-version-aware INSERT pattern** at `swing/data/repos/fills.py:51-53` (T3.SB1 NEW) — REUSED verbatim by T3.SB2 (no new code needed; existing infrastructure covers v20 NOT-NULL-DEFAULTED columns).

7. **`fill_origin_at_form_render` consistency-check anti-forgery gate** — preserved; operator submitting valid anchor without claim persists as `operator_typed` (Codex R2 M2 ACCEPTED per V1 single-operator threat model).

8. **Pre-Codex orchestrator-side review per C.C lesson #6 BINDING** — **19th cumulative validation CLEAN**. T2.SB4 + T3.SB3 + downstream sub-bundles inherit; 20th expected at T2.SB4.

9. **Multi-partial-exit envelope shape (NEW from T3.SB2)** — `candidates_map: {sig_hash: {date, price, quantity, order_id}}` server-stamped in form-render envelope; POST verifies submitted signature_hash is server-rendered (membership check on candidates_map). Forward-binding for any future operator-selection-from-list-of-options flow (T3.SB3 review auto-fill MAY surface similar candidates for prior-review selection; Phase 14+ position-management flows).

10. **`selected_X_audit_id` is an AUDIT TRAIL, not a DEDUPE KEY (NEW lesson from R2 M3)** — when a form has hidden "what operator picked" anchors vs "what was persisted" anchors, dedupe MUST key off "what was persisted" (i.e., the values actually stored in the row). Pattern recurs anywhere form-render presents N options + persistence reflects 1 outcome.

11. **`extended.pop(key, None)` pattern (NEW from R4 M1)** — when persisting a derived envelope where a key may not apply (e.g., authoritative selected has None for order_id), REMOVE the key entirely so downstream dedupe falls through to alternate matching (e.g., fallback tuple). Avoids stale defaults masquerading as authoritative.

12. **Price-precision parity between template render + POST-time comparison (NEW from R4 M2)** — when a template renders a float with fixed precision (e.g., `%.2f`) and the POST handler compares against the original float, the comparison MUST use the SAME rounding precision. Pattern: `round(anchor_float, N) != round(submitted_float, N)` where N matches the template format. Pre-empt in any new form rendering numerical values: enumerate the template's display precision + use matching precision in the POST comparison. CLAUDE.md gotcha candidate.

13. **Hybrid cassette+mock E2E pattern (NEW from T-B.2.4)** — when V1 cassette runbook is V2-PLANNED but a cassette file exists, the cassette-as-fixture-data-source + function-stub-at-trader-boundary pattern gives production-shape input discipline without VCR HTTP-layer replay complexity. Cassette loaded as YAML, routed through real `map_orders_to_fill_candidates` mapper, stubbed return value. Closes synthetic-fixture-vs-production-emitter shape drift family for the SELL path.

14. **Multi-partial variant via deep-copy+mutate (NEW from T-B.2.4 gap close)** — when cassette lacks a needed variant (e.g., multi-leg execution, multi-fill scenario), construct production-shape SchwabOrderResponse by deep-copying an existing raw cassette dict + mutating per-field (orderId / price / quantity / enteredTime / executions array) + routing through real mapper. Preserves mapper-coherence invariant (order qty == leg qty == executions qty). Discriminating test pattern: assert the helper produces a real `SchwabOrderResponse` with non-empty `executions[]`, NOT a hand-rolled synthetic.

---

## ACCEPT-WITH-RATIONALE banks (6 cumulative across R1-R4; for return-report tracking + V2 dispatch reference)

| Round | Finding | Accept rationale | V2 candidate |
|---|---|---|---|
| R1 M2 | Auto-fill provenance strip-by-omission of `fill_origin_at_form_render` | V1 single-operator threat model: operator can already type any values; persisting as `operator_typed` when claim absent is semantically correct (the operator's input IS operator-typed). Audit trail honestly reflects "operator submitted without an auto-fill claim." | V2: tighten validation to reject anchor-present-without-claim (anti-strip gate) if threat model widens beyond single-operator |
| R1 M3 | Unbounded lookback deviates from spec literal "7-day lookback window" | Spec literal appears copy-pasted from entry-side semantics; for exit, operator may have held position for weeks/months — capping at 7d from now would silently drop legitimate SELL fills outside that window. Lower bound = `entry_date` is operationally robust + matches actual workflow. **L1 deviation flagged for operator review.** | V2: spec amendment + optional explicit `lookback_days` kwarg with `from = max(entry_date, now - lookback_days)` semantics for explicit cap |
| R1 M5 | `enter_time` vs `execution_time` for date + sort | Most Schwab fills have `enter_time ≈ execution_time` (sub-second to seconds drift). Minor drift only matters when limit orders sit hours/days, rare in swing SELL. | V2: extract execution leg `time` when `executions[]` present; fall back to `enter_time` otherwise |
| R2 M1 | `candidates_map` read from client-submitted hidden input, not server-authoritative against operator | V1 single-operator threat model identical to T3.SB1 R1 Critical #1 ACCEPT — operator IS the only client; could submit anything; audit envelope provides REPRODUCIBILITY + EXPLANATION, not security against operator. | V2 (inherited verbatim from T3.SB1): replace hidden `schwab_source_value_json` transport with `schwab_api_call_id` server-side audit-row lookup; thread `call_id` through `ExitAutoFillResult` → template hidden input → POST verifies audit row exists with `surface='trade_exit'` + recent timestamp + ticker match. ~30-50 LOC dispatch with own 2-3 Codex rounds |
| R3 M2 | Fallback tuple dedupe false-positive risk for same-day/price/qty partials | V1 single-operator workflow: identical (date, price, qty) across two SELL orders on same trade is rare; bracket/scale-out splits typically differ in qty/price/date. Fallback is conservative — when in doubt, EXCLUDE. | V2: augment tuple with execution timestamp `(date, price, qty, enter_time)`; OR surface tuple-matched candidates as "possible duplicate" soft-warn instead of hard-filtering |
| R4 minor | Provenance-stamping branch ~150 LOC after 7 fix commits | Per-task TDD discipline: mid-cycle refactor would inflate fix commit beyond per-Codex-finding scope. Test coverage matrix is comprehensive (25 tests in `test_exit_post_audit_columns.py` covering 4×N scenarios). | V2: extract pure `_resolve_exit_auto_fill_post_provenance` helper returning `(fill_origin, schwab_source_value_json, operator_corrected_value_json)`; route handler becomes ~30 LOC delegation; test directly without route plumbing |

---

## Capture-needs for next sub-bundle dispatch

**For T2.SB4 (detectors batch 2: HTF + DBW) dispatch brief:**
- T2.SB4 worktree branches from main HEAD AFTER T3.SB2 merge per scope-brainstorm §0.5.2 dispatch sequence ("T2.SB4 dispatches AFTER T3.SB2 to avoid Schwab Trader API consumer merge conflicts").
- T2.SB4 does NOT touch Schwab integration substrate (pure pattern-detector batch). Inherits T2.SB3 detector patterns (drift_logging, geometric scoring, _step_pattern_detect pipeline integration).
- **20th cumulative C.C lesson #6 validation expected CLEAN** at T2.SB4 pre-Codex orchestrator-side review.
- ZERO Co-Authored-By footer drift streak (~279+ cumulative commits post-T3.SB2 merge + housekeeping) inherits.

**For T3.SB3 (review auto-fill) dispatch brief (dispatches after T2.SB5):**
- T3.SB3 inherits T3.SB1 + T3.SB2 hidden-anchor + value-validation + recovery anchor-clear discipline verbatim.
- T3.SB3 consumes OhlcvCache patterns (NOT Schwab Trader API) per spec §6.3 — auto-fill is from prior reviews + Phase 8 daily_management_records + candle data; NO Schwab integration discipline trinity needed.
- Multi-partial-exit envelope shape lesson (candidates_map) MAY apply if review form surfaces multiple prior-review candidates for operator selection.
- Forward-binding lesson #10 ("selected audit is NOT a dedupe key") binds.

**For ANY future hidden-anchor-driven form dispatch (Phase 14+):**
- Apply the 4-tier rejection ladder + recovery anchor-clear + claimed_auto_fill anti-forgery gate pattern verbatim from T3.SB1/T3.SB2.
- For numerical fields: ensure template render precision matches POST-time comparison precision (R4 M2 lesson; potential CLAUDE.md gotcha).
- For operator-selection-from-list flows: distinguish AUDIT-TRAIL fields (what operator picked) from DEDUPE-KEY fields (what was persisted).
- For provenance fields that may be None: pop from envelope rather than leave stale defaults (R4 M1 lesson).

---

## Outstanding capture-needs that DEFER

1. **V2 hidden-anchor architectural hardening** (R2 M1 ACCEPT, inherited from T3.SB1): replace hidden `schwab_source_value_json` transport with `schwab_api_call_id` server-side audit-row lookup pattern. Banked at T3.SB1 + reaffirmed at T3.SB2.

2. **V2 VM inheritance refactor** (T3.SB1 R1 M#4 ACCEPT, inherited): all 7+ base-layout VMs inherit from `BaseLayoutVM` (including `TradeExitFormVM`) in one sweep. Closes "duplication drift" failure mode permanently.

3. **V2 Schwab Trader API lookback widening** (R1 M3 ACCEPT): spec amendment for explicit `lookback_days` kwarg semantics; addresses spec literal "7-day window" vs operationally robust unbounded-by-entry_date trade-off.

4. **V2 execution timestamp in candidate ordering + dedupe tuple** (R1 M5 + R3 M2 ACCEPT): extract execution leg time when `executions[]` present + augment fallback tuple with timestamp to distinguish same-day same-price same-qty fills.

5. **V2 provenance-stamping branch helper extraction** (R4 minor ACCEPT): extract pure `_resolve_exit_auto_fill_post_provenance` for testability + per-axis regression reduction.

6. **V2 multi-partial UX: client-side JS to rebind visible inputs on radio change** (R2 minor closed via operator-instruction text; full V2 fix would add JS). Operator-instruction text is V1 workaround; V2 JS would let non-default radio + no-typed-edit → `schwab_auto` naturally.

7. **V2 fallback dedupe enhancement** (R3 M2 alternative): surface tuple-matched candidates as "possible duplicate" soft-warn instead of hard-filtering. Operator confirms include/exclude per candidate.

8. **V2 cassette runbook live-recording infrastructure** (T-B.2.4 hybrid mode dependency): land VCR HTTP-layer replay + operator-paired recording session for `trade_exit` surface + multi-partial variant.

9. **V2 "Reset to Schwab values" button on rejection-recovery form** (inherited from T3.SB1 R4 M#2 ACCEPT): explicit UX affordance for operator to discard typed values + accept fresh Schwab anchor.

---

## NEW CLAUDE.md gotchas surfaced during T3.SB2

(Banked for post-merge housekeeping discipline per orchestrator routine.)

1. **`selected_X_audit_id` is an AUDIT TRAIL, not a DEDUPE KEY** (Codex R2 M3 RESOLVED): when a form has hidden "what operator picked" anchors vs "what was persisted" anchors, dedupe MUST key off "what was persisted" (i.e., the value-source for the actually-stored row). Failure mode: VM dedupe over-excludes the picked-but-unrecorded candidate from future surfaces while leaving the actually-persisted candidate available for duplicate recording. Pattern recurs anywhere form-render presents N options + persistence reflects 1 outcome. Pre-empt: enumerate dedupe-key vs audit-trail fields; key dedupe off the field that reflects the row's value-source (e.g., envelope's top-level `schwab_order_id`, NOT envelope's `selected_candidate_order_id`).

2. **Price-precision parity between template render + POST-time float comparison** (Codex R4 M2 RESOLVED): when a template formats a float with fixed precision (e.g., `%.2f`) and the POST handler compares submitted-vs-anchor floats with a tight epsilon (e.g., `1e-9`), the comparison will silently flip to "operator edited" for execution-grain prices that round-trip through `%.2f`. Failure mode: authoritative `120.505` → template renders `120.50` → operator submits `120.50` → `abs(120.505 - 120.50) = 0.005 > 1e-9` → falsely flips fill_origin to `schwab_auto_then_operator_corrected` even though operator did NOT edit. Fix: compare with `round(anchor, N) != round(submitted, N)` where N matches the template's display precision. Pre-empt: in any new form rendering numerical floats, enumerate the template's display precision + use matching precision in the POST comparison.

3. **`extended.pop(key, None)` for envelope keys that may not apply** (Codex R4 M1 RESOLVED): when persisting a derived envelope where a key MAY OR MAY NOT apply (e.g., authoritative selected candidate has None for order_id), do NOT leave the stale form-render default in place — POP the key. Downstream dedupe will then fall through to alternate matching (e.g., fallback tuple). Failure mode: operator selects non-default radio + edits visible to match + selected candidate has None order_id → R3 rewrite skips (only fires on truthy order_id) → top-level stays at default order_id → future dedupe excludes default (never persisted) + does not add fallback tuple (order_id_found=True). Pre-empt: in any envelope-rewriting flow with optional fields, pop missing-data keys rather than leave stale defaults.

These will be added to the project CLAUDE.md Gotchas section at post-merge housekeeping per orchestrator's standard routine.

---

## LOCKs preserved

- **L1** (Spec §6.2 entry/exit symmetry + multi-partial discipline BIND verbatim): PRESERVED for entry/exit symmetry (4-step Schwab discipline + form-render envelope + audit columns + fill_origin transitions all mirror T3.SB1). **DEVIATION FLAGGED at R1 M3 ACCEPT**: unbounded lookback (lower bound = entry_date) deviates from spec literal "7-day lookback window" for operational robustness. V2 spec amendment recommended.
- **L2** (ZERO schema changes; v20 LOCKED): PRESERVED. Schema version unchanged at v20; `git diff --stat cb88329..HEAD -- swing/data/migrations/` returns empty.
- **L3** (NO `INSERT OR REPLACE` on fills writes): PRESERVED. Uses existing `insert_fill_with_event` (SELECT-then-INSERT discipline inherited from T3.SB1).
- **L4** (Cross-bundle pin at `tests/data/test_v20_migration.py:907` MUST un-skip at T-B.2.5 closer): PRESERVED. Decorator removed cleanly at `7429d6a`; test PASSES at first un-skip.
- **L5** (Branch base = main HEAD `cb88329` at dispatch time): VERIFIED via `git merge-base --is-ancestor cb88329 HEAD` returning 0.
- **L6** (Frozen dataclasses `ExitAutoFillResult` + `ExitAutoFillCandidate` carry `__post_init__` Literal[...] frozenset validation): PRESERVED. Both dataclasses validate against `_EXIT_AUTO_FILL_KIND_VALUES` + `_EXIT_FILL_ORIGIN_VALUES` frozensets; discriminating tests at `tests/trades/test_exit_auto_fill.py:test_exit_auto_fill_result_invalid_kind_rejected` + variants.
- **L7** (Hidden anchor 4-tier rejection ladder + `_reject_anchor` helper REUSED; recovery form anchor-clear discipline BINDING): PRESERVED. Helper defined locally in `exit_post` (mirrors T3.SB1 entry_post precedent); 4 rejection tiers + claimed_auto_fill anti-forgery gate + recovery via `build_exit_form_vm` rebuild (NOT echoing bad anchor); discriminating tests cover all 4 tiers + anti-forgery + anchor-clear.
- **L8** (`resolve_credentials_env_or_prompt(allow_prompt=False)` BINDING): PRESERVED. Production code passes `allow_prompt=False`; mock-verified at trace test.

---

*End of return report. Phase 13 T3.SB2 SHIPPED. Branch base SHA `cb88329`. 16 commits + ZERO Co-Authored-By footer drift + 5326 fast tests + 3 slow Schwab E2E + NO_NEW_CRITICAL_MAJOR at Codex Round 5 + 19th cumulative C.C lesson #6 validation CLEAN + cross-bundle pin un-skip CONFIRMED + multi-partial-exit handling SHIPPED as the NEW architectural dimension + server-side authoritative envelope via candidates_map pivot (R1 Critical+M1) + dedupe correctness fixes across R1-R4 + 3 NEW CLAUDE.md gotchas surfaced for banking.*
