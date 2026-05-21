# Phase 13 T3.SB3 — Review auto-fill (priors + MFE/MAE from OhlcvCache) dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-21 PM post-T2.SB5 SHIPPED + housekeeping at main HEAD `6d7cc3c`. Mid-sized sub-bundle (5 tasks; +40-70 fast tests projected per plan §H). Per plan §G.8 lines 2049-2106.

**Branch:** `phase13-t3-sb3-review-auto-fill` — branches from main HEAD `6d7cc3c` at dispatch time (per plan §G.8 line 2053 + dispatch sequence §H.1: T3.SB3 branches AFTER T2.SB5 merge per spec §6.5 — consumes OhlcvCache patterns + candidate-window primitives that T2.SB5 cements).

**Worktree:** create via `git worktree add .worktrees/phase13-t3-sb3-review-auto-fill phase13-t3-sb3-review-auto-fill`.

**Time estimate:** orchestrator wall-clock 4-7 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x for accuracy; T3.SB3 is smaller than T2.SB5 — 5 tasks vs 6; no benchmark gate; pure persistence-layer dispatch; v20 schema UNCHANGED).

---

## §1 Scope summary

**Trade review form pre-populates priors from previous reviews + MFE/MAE from candles per spec §6.3. Period review section text auto-fill. Persistence-layer only (v20 schema UNCHANGED; `review_log.auto_populated_field_keys_json` column already landed at T-A.1.1).** Per OQ-8 BINDING: OhlcvCache (post-T1.SB0) for MFE/MAE candle data; yfinance V2-fallback only; ZERO new Schwab API consumption.

| Task | Title | Tests target |
|---|---|---|
| T-B.3.1 | Priors helpers per spec §E.4 (`get_priors_for_ticker` + `ReviewPriors` frozen dataclass) | 4+ tests |
| T-B.3.2 | MFE/MAE from OhlcvCache per OQ-8 (Phase 8 source-ladder) | 4+ tests |
| T-B.3.3 | `review_form_page` handler + `ReviewFormVM` extension (priors + MFE/MAE + auto_populated field tracking) | 7+ tests |
| T-B.3.4 | `review_post` persist `auto_populated_field_keys_json` + period review section text helpers | 5+ tests |
| T-B.3.5 | T3.SB3 closer — integration E2E + ruff sweep | 1 fast E2E |

Per plan §G.8 verbatim. Cross-bundle pin work at T-B.3.5 closer: per plan §H.3 row 1 `test_ohlcv_cache_get_or_fetch_invariant` un-skips at T2.SB2 + T2.SB3 + **T3.SB3** (verify status; un-skip if still skipped). Status check at T-B.3.5 Step 1.

### §1.1 Inheritance from T2.SB5 forward-binding lessons (per T2.SB5 return report §8)

T3.SB3 is the THIRD Theme 3 auto-fill sub-bundle (after T3.SB1 entry + T3.SB2 exit) but the FIRST to consume the OhlcvCache + Phase 13 detector substrate completed at T2.SB5. Inherited disciplines:

1. **`compute_composite_score` clamp discipline LOCKED** (T2.SB5 L5 LOCK preserved; T2.SB4 R2 Critical #1 lineage) — NOT directly applicable to T3.SB3 (no scoring formula introduced) but informs the broader "score-clamp on BOTH paths" architectural principle: any function that consumes `(primary, secondary | None)` and computes a derived value MUST honor identical clamp/bound discipline on the None fallback path.
2. **Bad-exemplar isolation in retrieval functions** (T2.SB5 R1 M#1 RESOLVED at `5534cc6`) — T3.SB3's MFE/MAE helper consumes the Phase 8 `daily_management_records` source-ladder + falls through to OhlcvCache. If ANY individual `daily_management_records` row is malformed OR OhlcvCache returns malformed bars, the helper MUST isolate the per-trade failure (skip + continue with cohort) rather than letting the exception bubble up and suppress the whole form-render. Pattern: per-row try/except around the helper's per-trade computation.
3. **Pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches** (T2.SB4 R1 M1 lesson; T2.SB5 21st validation BANKED CLEAN) — **BINDING for T3.SB3 pre-Codex review**. Spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 are the source-of-truth; this brief's sketches MUST be cross-checked verbatim.

### §1.2 Inheritance from T3.SB1 + T3.SB2 form-driven discipline (BINDING)

T3.SB3 is the third HTMX form-driven auto-fill sub-bundle. Inherited disciplines (BINDING):

4. **Hidden anchor 4-tier rejection ladder** per T3.SB1 CLAUDE.md gotcha — when a web form has hidden audit anchors driving POST-time provenance stamping, the canonical pattern is the 4-tier rejection: (a) malformed JSON → 400 + clear anchor on recovery; (b) non-dict JSON → 400 + clear; (c) dict missing required keys → 400 + clear; (d) dict with invalid value shapes → 400 + clear. For T3.SB3, the `auto_populated_field_keys_json` hidden anchor at form-render → POST is the primary candidate. The `_reject_anchor` helper at `swing/web/routes/trades.py:899-910` (planted at T3.SB1) is the reusable template.
5. **Recovery form anchor-clear discipline** per T3.SB1 R3 M#2 — on anchor-rejection 400 responses, the recovery form MUST clear the bad anchor (pass `submitted_*=None` to the re-render helper, NOT the raw rejected anchor). Otherwise operator gets trapped in repeated 400s.
6. **For any form with hidden audit fields, default to SERVER-STAMPING at handler entry** per Phase 8 R2-R5 family + T2.SB5 housekeeping recap — `auto_populated_field_keys_json` is COMPUTED at form-render handler entry from the priors/MFE/MAE helpers' return shape, NOT submitted by operator. Hidden inputs are tampering surfaces.
7. **`selected_X_audit_id` is AUDIT TRAIL, not DEDUPE KEY** per T3.SB2 R2 M3 — if T3.SB3 introduces any "operator selected X from N options" pattern, dedupe MUST key off "what was persisted" (value-source), not "what operator picked" (audit-trail label).
8. **Price-precision parity between template render + POST-time float comparison** per T3.SB2 R4 M2 — if MFE/MAE values are rendered with fixed precision (e.g., `%.2f`) and the POST handler compares for "operator edited the auto-fill", use `round(anchor, N) != round(submitted, N)` where N matches template's display precision.
9. **`extended.pop(key, None)` for envelope keys that may not apply** per T3.SB2 R4 M1 — when persisting a derived envelope where a key MAY OR MAY NOT apply (e.g., MFE/MAE values when entry_date is unknown), POP the key rather than leave stale defaults.

### §1.3 Inheritance from broader Phase 13 + cumulative arc disciplines

10. **Session-anchor read/write mismatch** (recurring gotcha family; plan T-B.3.3 explicitly mentions `last_completed_session(now())` alignment) — review form is operator-facing; the session-anchor for "what trades to surface for review" + "what daily_management_records to consume for MFE/MAE" MUST be the writer's session-anchor function. Read the writer's code to verify; do NOT lock the read predicate from orchestrator mental model alone. Add a discriminating round-trip integration test that writes a row + immediately reads via the UI predicate.
11. **HTMX form-driven endpoints have 3 browser-only failure surfaces TestClient cannot detect** per Phase 5 R1 M1+M2 + Phase 6 I3 inheritance:
    - (a) Embedded forms must include `hx-headers='{"HX-Request": "true"}'` under OriginGuard strict-mode
    - (b) Success-path response MUST be `204 + HX-Redirect: <url>` (NOT `303 + swap-target`)
    - (c) HX-Redirect target route MUST be registered in app's route table (verify via `assert any(r.path == target for r in app.routes)` OR follow the redirect with a second TestClient call asserting 200)
12. **Python `... or ""` collides with SQL CHECK-constraint nullability** per Phase 6 deviation #3 — explicitly called out in plan §G.8 T-B.3.4 watch item. For T3.SB3's `auto_populated_field_keys_json` nullable column: use `... or None` (NOT `... or ""`). The column accepts JSON strings or NULL; empty-string would fail JSON validation downstream.
13. **`Literal[...]` type hints are NOT runtime-enforced** per T-A.1.5b R3 M#1 — `ReviewPriors.process_grade_baseline: float | None` and any other typed fields need explicit `__post_init__` runtime validation against an explicit range/frozenset (numeric encoding A=4..F=0 per plan T-B.3.1 step 1 (c) → process_grade_baseline ∈ [0.0, 4.0]).
14. **Service-layer `ValueError`s must be wrapped at CLI boundary** per T-A.1.5b R4 M#1 — N/A for T3.SB3 web boundary (the form handler wraps via Starlette/FastAPI's exception handlers) but BINDING if T3.SB3 introduces any CLI subcommand.
15. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 22nd cumulative validation expected with BOTH SCOPE EXPANSIONS BINDING)**:
    - **Expansion #1** (T3.SB2 hotfix `cf3c489`): grep `swing/` for hardcoded duplicates of any new constant T3.SB3 introduces (e.g., `_AUTO_POPULATED_FIELD_KEYS` allow-list if planted; `_PROCESS_GRADE_NUMERIC` encoding constant) + verify each downstream consumer is widened consistently.
    - **Expansion #2** (T2.SB4 R1 M1): cross-check brief prescriptions against spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 BINDING text byte-for-byte. Verify `n=5` default for `get_priors_for_ticker` (§E.4 LOCK); verify source-ladder ordering (`daily_management_records` first; OhlcvCache fallback) per §E.3 LOCK; verify period helpers signature exactness (`period_start: date, period_end: date`) per §E.5 LOCK.

---

## §2 Per-task acceptance criteria (per plan §G.8 verbatim)

| Task | Title | Acceptance |
|---|---|---|
| T-B.3.1 | Priors helpers per spec §E.4 | 4+ tests pass per plan §G.8 step 1: (a) `get_priors_for_ticker(conn, ticker, n=5)` returns `ReviewPriors` with `mistake_tag_candidates` + `process_grade_baseline` + `lesson_learned_candidates`; (b) edge case zero prior reviews returns empty priors (no advisory text per §A.16 graceful at n=0); (c) numeric grade encoding A=4..F=0 for process_grade_baseline (mean of recent N); (d) lesson_learned_candidates ordered most-recent-first. `ReviewPriors` is `@dataclass(frozen=True)` with `__post_init__` runtime validation (process_grade_baseline ∈ [0.0, 4.0] OR None; lists are tuples for frozen-dataclass immutability). |
| T-B.3.2 | MFE/MAE from OhlcvCache per OQ-8 | 4+ tests pass: (a) when `daily_management_records.open_MFE_R_to_date` exists for trade, prefer Phase 8 source; (b) when Phase 8 record missing, fall through to OhlcvCache daily-bar synthesis; (c) `mfe_pct = max(daily highs since entry) / entry_price - 1` correct; (d) `mae_pct = min(daily lows since entry) / entry_price - 1` correct. Implements `compute_mfe_mae_from_ohlcv_cache(conn, trade, ohlcv_cache) -> tuple[float, float]` with the source-ladder per §E.3 LOCK. **Per-row failure isolation** (per §1.1 #2 inherited from T2.SB5): if a malformed `daily_management_records` row OR malformed OhlcvCache bars surface, skip + continue rather than raising. |
| T-B.3.3 | `review_form_page` handler + `ReviewFormVM` extension | 7+ tests pass (banner field population explicit per plan step 1 (g) + forward-binding lesson #12): (a) form renders with priors populated as DEFAULT input values; (b) MFE/MAE auto-populated; (c) hidden `auto_populated_field_keys_json` field present + server-stamped at handler entry; (d) session-anchor `last_completed_session(now())` aligned per §1.3 #10 + plan step 1 (d); (e) `ReviewFormVM` extends `BaseLayoutVM`; (f) form renders gracefully at zero priors; (g) `ReviewFormVM` populates `unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count` per forward-binding lesson #12 + Phase 10 §A.18 helper. **HX-Request + HX-Redirect surfaces respected** per §1.3 #11. **Operator-editable defaults; server-stamped hidden audit fields** per §1.2 #6 — operator can edit MFE/MAE if Phase 8 source is stale; the auto-populated tracking is server-determined. |
| T-B.3.4 | `review_post` persist `auto_populated_field_keys_json` + period review helpers | 5+ tests pass: (a) review POST persists `auto_populated_field_keys_json` correctly (uses `... or None` per §1.3 #12); (b) `get_period_lessons_summary(conn, period_start, period_end)` auto-extracts concatenated lessons from `review_log` rows in prior period; (c) `get_period_mistake_tag_aggregate(conn, period_start, period_end)` returns dict[str, int] of tag→count over period; (d) `get_period_cohort_health_deltas(...)` returns dict[str, float] of cohort→delta vs prior period; (e) discriminating `... or None` test: submits empty `auto_populated_field_keys_json` form field + asserts NULL persisted (not empty-string CHECK violation). Three new helpers per §E.5 LOCK with exact signature fidelity. **Soft-warn confirm fragment** rendering if operator edits a pre-populated field MUST round-trip the `auto_populated_field_keys_json` hidden anchor through the confirm's `form_values` dict per Phase 9 R3 Critical #1 (if soft-warn pattern applies to review form — verify at recon). |
| T-B.3.5 | T3.SB3 closer — integration E2E + ruff sweep | Fast E2E PASS: seeds trade + 5 prior reviews + open-trade OhlcvCache fixture; invokes GET `/reviews/{id}/complete` (or `/trades/{id}/review/complete` — verify route path at recon against shipped Phase 6); asserts form renders with priors + MFE/MAE; POST submit; asserts `auto_populated_field_keys_json` persisted. **Cross-bundle pin status check**: `test_ohlcv_cache_get_or_fetch_invariant` un-skip status per plan §H.3 row 1 (un-skips at T2.SB2 + T2.SB3 + T3.SB3). Verify pin status at Step 1 (may already be un-skipped at T2.SB2 or T2.SB3); if still skipped, un-skip here. |

**Recommended ordering**: T-B.3.1 (priors; pure SQL + dataclass) → T-B.3.2 (MFE/MAE; pure function over OhlcvCache + Phase 8 source-ladder) → T-B.3.3 (handler + VM; consumes T-B.3.1 + T-B.3.2 helpers) → T-B.3.4 (POST + period helpers; consumes T-B.3.3 form's hidden anchor) → T-B.3.5 (closer + cross-bundle pin status check).

---

## §3 Files in scope

**Create**:
- `swing/trades/review_auto_fill.py` — `compute_mfe_mae_from_ohlcv_cache` + any helper functions specific to auto-fill orchestration; per-row failure isolation pattern from §1.1 #2.
- `tests/trades/test_review_auto_fill.py` — unit tests for MFE/MAE helper (T-B.3.2).
- `tests/web/test_routes/test_review_form_auto_fill.py` — handler + VM tests (T-B.3.3 + T-B.3.4).

**Modify**:
- `swing/trades/review.py` — add `get_priors_for_ticker(conn, ticker, n=5) -> ReviewPriors` + `ReviewPriors` frozen dataclass + 3 period helpers (`get_period_lessons_summary` + `get_period_mistake_tag_aggregate` + `get_period_cohort_health_deltas`) per §E.4 + §E.5 LOCKs.
- `swing/web/routes/trades.py` — extend `review_form_page` (line ~1508 per plan §G.8 line 2056; verify at recon) to invoke priors + MFE/MAE helpers + populate ReviewFormVM fields. Extend review POST handler to persist `auto_populated_field_keys_json` (use `... or None`).
- `swing/web/templates/trades/review_form.html.j2` — render priors as DEFAULT input values; render hidden `auto_populated_field_keys_json` field; render banner fields per Phase 10 §A.18 helper.
- `swing/web/view_models/trades.py` — `ReviewFormVM` extension with priors + MFE/MAE + auto_populated tracking fields + Phase 10 `BaseLayoutVM` banner mixin (`unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count`).

**Verify at T-B.3.5 cross-bundle pin status check**:
- `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py` line ~203 — un-skip per plan §H.3 row 1 (T2.SB2 + T2.SB3 + T3.SB3). Per `git grep` audit on main HEAD `6d7cc3c`, this pin is still `@pytest.mark.skip` with reason "un-skips at T2.SB2 + T2.SB3 + T3.SB3" (was not un-skipped at T2.SB2 OR T2.SB3 closer; T3.SB3 closes the lag — same pattern as T2.SB5's `test_pattern_exemplars_schema_shape_invariant` closure).

**NOT in scope (V2 / future sub-bundles)**:
- Closed-loop / charts surface (T2.SB6 territory; per plan §H.1 next after T3.SB3)
- Theme 1 annotated charts (T2.SB6 territory)
- Schema changes (v20 LOCKED per spec §B.4; `review_log.auto_populated_field_keys_json` ALREADY landed at T-A.1.1 migration 0020 line 410)
- yfinance fallback path (V2 only per OQ-8 LOCK; OhlcvCache is V1 source-of-truth)
- New Schwab API consumption (spec §6.3 LOCKs ZERO Schwab API calls for review auto-fill)
- TOS CSV import auto-fill (V2 candidate per spec §E.1)
- Realized R-if-plan-followed recompute at form render (per spec §6.3 item 3) is OPTIONAL for V1 — verify at recon whether Phase 7 derived_metrics helper already exists for invocation; if requires new code, BANK as V2 candidate

---

## §4 Watch items (cumulative discipline; banked across Phase 12 + 12.5 + 13)

### §4.1 T3.SB3-specific watch items

1. **Spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 LOCK fidelity**: every helper signature + source-ladder ordering + numeric encoding + audit column shape MUST match spec verbatim. Implementer SHOULD grep spec; do NOT paraphrase. **Cross-check spec source-of-truth against this brief's prescriptions per C.C lesson #6 Expansion #2 BINDING** (§1.3 #15).
2. **§E.3 source-ladder ordering LOCK**: `daily_management_records` FIRST; OhlcvCache FALLBACK. If Phase 8 record exists for trade, USE IT (do not recompute via OhlcvCache). Operator may have edited the Phase 8 record manually; honor the operator's adjustment.
3. **§E.4 `ReviewPriors` dataclass LOCK**: 3 fields (`mistake_tag_candidates` + `process_grade_baseline` + `lesson_learned_candidates`). Frozen + tuples-not-lists for immutability per `Literal[...]` runtime-enforcement gotcha. `process_grade_baseline ∈ [0.0, 4.0] | None` validated at `__post_init__`.
4. **§E.5 period helpers LOCK**: 3 helpers with exact signatures `(conn, *, period_start: date, period_end: date) -> str | dict[str, int] | dict[str, float]`. Cohort_health_deltas takes BOTH current + prior period boundaries (4 date params).
5. **§E.6 hidden audit anchor LOCK** is for T3.SB1/T3.SB2 entry/exit fill_origin (NOT directly applicable to T3.SB3 review form); review form has DIFFERENT audit semantic (`auto_populated_field_keys_json`). Verify at recon: review form may have NO hidden anchors at all (just default-populated visible fields + server-stamped tracking). If so, §1.2 #4 + #5 inherited disciplines are inert; document.
6. **§E.7 `auto_populated_field_keys_json` LOCK**: stores JSON array of field keys auto-populated at form render. Server-stamped at form-render handler entry from priors/MFE/MAE helpers' return shape. Persisted at POST. Use `... or None` per §1.3 #12.
7. **OhlcvCache get_or_fetch invariant**: review auto-fill consumes the SAME OhlcvCache infrastructure that T2.SB2/T2.SB3 detectors consume + that T2.SB5 template matching consumes. Per `test_ohlcv_cache_get_or_fetch_invariant` (cross-bundle pin), the cache returns enough history for the MAX consumer window (per shared-infrastructure cache-hook gotcha from T1.SB0 R3 M#1).
8. **Per-row failure isolation in MFE/MAE helper** per §1.1 #2 — if a malformed `daily_management_records` row OR malformed OhlcvCache bars surface, skip + continue rather than raising. Discriminating test: plant 2 trades; 1 has malformed Phase 8 row; helper returns valid MFE/MAE for the other trade + None for the malformed one.
9. **`ReviewPriors` graceful-at-n=0 contract** per §A.16 — when no prior reviews exist for the ticker, helper returns empty priors (empty tuples + None process_grade_baseline); does NOT raise; form render shows empty defaults (operator types fresh).

### §4.2 Form-driven discipline watch items (T-B.3.3 + T-B.3.4)

10. **HTMX HX-Request header propagation** on embedded forms under OriginGuard strict-mode (Phase 5 R1 M1). Discriminating test: TestClient + simulated browser submit without explicit HX-Request header header; assert 403 → fix via `hx-headers='{"HX-Request": "true"}'`.
11. **HTMX success-path `204 + HX-Redirect` (NOT `303 + swap-target`)** per Phase 5 R1 M2.
12. **HX-Redirect target route verified to exist** per Phase 6 I3 — `assert any(r.path == target for r in app.routes)` OR follow redirect via second TestClient call asserting 200.
13. **Server-stamping for `auto_populated_field_keys_json` hidden audit field** per Phase 8 + §1.2 #6 — computed at handler entry from priors/MFE/MAE return shape; operator cannot tamper.
14. **`... or None` (NOT `... or ""`) for `auto_populated_field_keys_json` nullable JSON column** per §1.3 #12 + plan §G.8 T-B.3.4 watch item. Discriminating test asserts NULL persisted (not empty-string CHECK violation).
15. **Session-anchor read/write mismatch** per §1.3 #10 — `last_completed_session(now())` MUST be the read predicate for period helpers (which session boundary do they consume?). Verify writer's session-anchor function (per Phase 8 daily-management `cfacbc5` precedent); add round-trip integration test.
16. **Synthetic-fixture-vs-production-emitter shape drift** per Phase 11 Sub-bundle C family — tests against MFE/MAE production-shape responses MUST exercise actual `daily_management_records` schema fields (not paraphrase). Plant Phase 8 record fixture from real shape; assert helper round-trips.
17. **Banner-pin field VM duplication discipline** per T3.SB2 + Phase 10 §A.18 — `ReviewFormVM` extends `BaseLayoutVM`; banner fields auto-populate via the shared helper. Discriminating test #7 in T-B.3.3.

### §4.3 Cross-bundle pin watch items (T-B.3.5)

18. **`test_ohlcv_cache_get_or_fetch_invariant` un-skip per plan §H.3 row 1** — was scheduled for T2.SB2 + T2.SB3 + T3.SB3 un-skip; **still skipped on main HEAD `6d7cc3c`** per `git grep` audit (same lag pattern as T2.SB5 closer's `test_pattern_exemplars_schema_shape_invariant` closure). T-B.3.5 closes the lag.

### §4.4 Cumulative process discipline

19. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 22nd cumulative validation expected with BOTH SCOPE EXPANSIONS BINDING)** — implementer dispatches a focused reviewer subagent with this brief's §3 file-scope + §4 watch items + §5 done criteria + §6 LOCKs as anchors BEFORE invoking Codex MCP. Reference: 21st cumulative validation BANKED CLEAN at T2.SB5 with both expansions applied; Codex chain converged at R2 (faster than T2.SB4's R5). **Expansion #1 (T3.SB2 hotfix `cf3c489`)**: grep `swing/` for hardcoded duplicates of any new T3.SB3 constants (e.g., `_PROCESS_GRADE_NUMERIC_ENCODING` if planted; `_REVIEW_PRIORS_DEFAULT_N=5` if planted). **Expansion #2 (T2.SB4 R1 M1)**: cross-check spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 BINDING text byte-for-byte vs brief sketches.
20. **NO `Co-Authored-By` footer** — cumulative ~312+ commit streak ZERO trailer drift through T2.SB5 + housekeeping; do NOT regress. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): explicit citation in commit messages required.
21. **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (memory `feedback_worktree_cli_invocation`).
22. **ASCII-only on any new CLI/print path** — runtime CLI paths bind (Windows cp1252 footgun); detector/auto-fill internal logging via stdlib logger handles encoding.
23. **Edit tool for per-file edits** when fixing E501 / type / import-order issues — do NOT bulk-rewrite.
24. **Cite the discipline in commit messages** (matches all prior T1.SB0 + T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 + T3.SB2 + T2.SB4 + T2.SB5 commit-message precedent).
25. **TDD discipline per task** via `superpowers:test-driven-development` (write failing test → see fail → minimal implementation → see pass → commit).

---

## §5 Done criteria

### §5.1 S1 (inline; implementer self-verifies before invoking Codex)

- [ ] All 5 T-B.3.X tasks committed per plan §G.8 acceptance criteria.
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post-merge. **Expected**: 5412 + ~40-70 new fast tests = ~5452-5482 total + 1 un-skip from T-B.3.5 cross-bundle pin = ~5453-5483; 0 failures; ≤2 skipped (T-B.3.5 un-skip of `test_ohlcv_cache_get_or_fetch_invariant` brings skipped from 3 → 2 OR adjusts net based on actual cross-bundle pin status at HEAD).
- [ ] `python -m pytest -m slow tests/integration/test_phase13_t3_sb3_*.py -q` PASS if T-B.3.5 includes any slow E2E (verify at recon; likely fast-only per plan §G.8 T-B.3.5 step 1).
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20 (no migrations; `auto_populated_field_keys_json` column already landed at T-A.1.1).
- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured (22nd cumulative C.C lesson #6 validation expected CLEAN with BOTH scope expansions applied).
- [ ] All commits on branch `phase13-t3-sb3-review-auto-fill` have empty `Co-Authored-By` trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t3-sb3-review-auto-fill --not main | grep -c .` returning 0).
- [ ] Codex MCP adversarial-critic chain converges to `NO_NEW_CRITICAL_MAJOR` (expected 2-4 rounds based on small-mid scope; T2.SB5 converged at R2 with inherited cumulative discipline — T3.SB3 may converge similarly).

### §5.2 S2-S4 (operator-paired post-merge per plan §G.8 lines 2101-2105)

- **S2 (browser)**: open `/reviews/{id}/complete` for an open trade → confirm MFE/MAE values match operator's expectation; priors populated from prior reviews.
- **S3 (round-trip)**: operator submits review; confirms `auto_populated_field_keys_json` audit trail persisted (visible via DB inspection or audit query).
- **S4 (period review)**: operator triggers period review form; confirms section text auto-populated from `get_period_lessons_summary` + `get_period_mistake_tag_aggregate` + `get_period_cohort_health_deltas` helpers.

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 BINDING text verbatim. Helper signatures + source-ladder ordering + numeric encoding A=4..F=0 + audit column shape + period helper signatures. Implementer reads spec; does NOT paraphrase.
- **L2**: ZERO new Schwab API calls (spec §6.3 LOCKs ZERO Schwab consumption for review auto-fill; OhlcvCache + Phase 8 + existing review_log only).
- **L3**: `daily_management_records` source FIRST in MFE/MAE source-ladder; OhlcvCache FALLBACK. Do NOT recompute via OhlcvCache if Phase 8 record exists.
- **L4**: ZERO schema changes (v20 LOCKED; `review_log.auto_populated_field_keys_json` already landed at T-A.1.1 migration 0020 line 410).
- **L5**: `... or None` (NOT `... or ""`) for `auto_populated_field_keys_json` nullable column persistence.
- **L6**: Branch base = main HEAD `6d7cc3c` at dispatch time. Verify at T-B.3.1 Step 0: `git merge-base --is-ancestor 6d7cc3c HEAD` returns 0.
- **L7**: Frozen dataclasses (`ReviewPriors`) carry `__post_init__` runtime validation honoring T-A.1.5b R3 M#1 `Literal[...]` not-runtime-enforced gotcha. process_grade_baseline ∈ [0.0, 4.0] | None.
- **L8**: Cross-bundle pin un-skip at T-B.3.5 closer per plan §H.3 row 1. Leaving stale (skipped state) violates plan §H.3 schedule.
- **L9**: yfinance is V2-FALLBACK ONLY per OQ-8. T3.SB3 V1 implementation does NOT consume yfinance directly (OhlcvCache routes to yfinance internally if other sources unavailable, but T3.SB3 is OhlcvCache consumer-side only).
- **L10**: Server-stamping at handler entry for `auto_populated_field_keys_json` per Phase 8 R2-R5 family — operator cannot tamper.
- **L11**: `n=5` default for `get_priors_for_ticker` per §E.4 LOCK. Helper signature: `(conn, ticker, n=5) -> ReviewPriors`.
- **L12**: HTMX 3-surface discipline (HX-Request propagation + HX-Redirect-success + HX-Redirect-target-registered) per cumulative form-driven inheritance from Phase 5 + 6 + 9 + T3.SB1 + T3.SB2.

---

## §7 Reference materials (read before dispatching)

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.8 lines 2049-2106 (T3.SB3 verbatim 5-task spec) + §E.3-§E.7 (helper architecture LOCKs at lines 686-755) + §H.3 row 1 (cross-bundle pin schedule).
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`:
  - §6.3 Review auto-fill (lines 868-893; auto-fill fields enumeration + audit trail + ZERO Schwab gate)
  - §6.6 Forward-binding lessons referenced (lines 913-921; 6 inherited discipline families)
  - §E.7 `review_log.auto_populated_field_keys_json` LOCK (lines 745-751; column shape + persist contract + discriminating test)
- **Migration**: `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql` line 410 (`ALTER TABLE review_log ADD COLUMN auto_populated_field_keys_json TEXT;`) — verify column exists on prod DB via `PRAGMA table_info(review_log)` before T-B.3.4 wires up persistence.
- **T2.SB5 return report** at `docs/phase13-t2-sb5-return-report.md` §8 — forward-binding lessons banked for T3.SB3 + T2.SB6 + T4.SB inheritance (verbatim sources for §1.1 above).
- **T3.SB1 + T3.SB2 dispatch briefs + return reports** at `docs/phase13-t3-sb1-*.md` + `docs/phase13-t3-sb2-*.md` — hidden-anchor 4-tier rejection + recovery anchor-clear + server-stamping precedents (verbatim sources for §1.2 above).
- **Phase 6 review POST handler** at `swing/web/routes/trades.py` review_form_page (line ~1508 per plan §G.8 line 2056; verify at recon) + Phase 7 review service at `swing/trades/review.py` — extension sites.
- **Phase 8 daily-management** at `swing/trades/daily_management.py` — `daily_management_records` row shape + `open_MFE_R_to_date` + `open_MAE_R_to_date` columns + session-anchor read predicate (informs §1.3 #10 round-trip integration test).
- **Phase 10 `BaseLayoutVM` banner mixin** at `swing/web/view_models/base.py` (or equivalent) — `unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count` populator helper.
- **OhlcvCache** at `swing/web/ohlcv_cache.py` — `get_or_fetch(ticker, lookback_days=N, as_of_date=date)` contract.
- **CLAUDE.md gotchas relevant to T3.SB3**:
  - `Literal[...]` not runtime-enforced (T-A.1.5b R3 M#1)
  - Service-layer ValueErrors must be wrapped at CLI boundary (T-A.1.5b R4 M#1; N/A for web boundary)
  - Hidden anchor 4-tier rejection ladder (T3.SB1)
  - Recovery form anchor-clear discipline (T3.SB1 R3 M#2)
  - Session-anchor read/write mismatch family
  - For any V1 single-operator form with hidden audit fields, default to SERVER-STAMPING (Phase 8 R2-R5)
  - HTMX form-driven endpoints have 3 browser-only failure surfaces TestClient cannot detect (Phase 5 R1 M1+M2 + Phase 6 I3)
  - Python `... or ""` collides with SQL CHECK-constraint nullability (Phase 6 deviation #3)
  - `selected_X_audit_id` is AUDIT TRAIL not DEDUPE KEY (T3.SB2 R2 M3)
  - Price-precision parity template-vs-POST float comparison (T3.SB2 R4 M2)
  - `extended.pop(key, None)` for envelope keys that may not apply (T3.SB2 R4 M1)
  - Bad-exemplar isolation in retrieval functions (T2.SB5 R1 M#1)
  - Pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches (T2.SB4 R1 M1)

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T3.SB3 merge ships:

1. **CLAUDE.md line 3 refresh** — update HEAD reference + mention T3.SB3 SHIPPED + 22nd cumulative C.C lesson #6 validation (if CLEAN); mention any NEW gotchas surfaced.
2. **phase3e-todo.md** — new top entry for T3.SB3 SHIPPED with Codex chain shape + ACCEPT-WITH-RATIONALE banks + forward-binding lessons for T2.SB6 + T4.SB inheritance + cross-bundle pin closure note + any new V2 candidates.
3. **orchestrator-context.md** — refresh current state; demote former current (T2.SB5) to Prior #1; archive-split per size-check trigger (Prior count post-this-demote will be 11 — over cap; archive oldest at line ~148+ post-T2.SB5-housekeeping — verify exact line + container at housekeeping time).
4. **orchestrator-context-archive.md** — new "Appended 2026-05-2X" section with archived Prior verbatim.
5. **Streaks update** — bank 22nd cumulative C.C lesson #6 validation (if CLEAN); bank ~318+ cumulative ZERO Co-Authored-By streak (T3.SB3 expected ~6-10 commits including Codex fix bundles).
6. **Phase 13 dispatch sequence forward state** — T3.SB3 SHIPPED; T2.SB6 NEXT per plan §H.1 (closed-loop surface + Theme 1 annotated charts; 8 tasks per plan §G.9). **SURFACE THE PAUSE-FOR-LIST-ADDITIONS** at the T2.SB6 SHIPPED + housekeeping boundary per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory.

---

## §9 Forward-binding to T2.SB6 + T4.SB

T2.SB6 = Closed-loop surface + Theme 1 annotated charts + T-A.6.6b Deficiency 1 fold-in (8 tasks per plan §G.9). Branches from main HEAD AFTER T3.SB3 merge. Consumes:
- `pattern_evaluations` rows (T2.SB3 + T2.SB4 substrate)
- `template_match_nearest_exemplar_ids_json` for top-3 thumbnail rendering per spec §5.10 page content #3 (T2.SB5 substrate)
- `auto_populated_field_keys_json` audit trail (T3.SB3 substrate) — informs the closed-loop UI rendering of "what was auto-populated vs operator-typed"
- OhlcvCache for chart rendering (T1.SB0 + T2.SB5 substrate)

T4.SB = Usability triage + Q4 close-tracking + T-D.6b metrics-audit (8 tasks + operator-added items). **PAUSE FOR OPERATOR LIST ADDITIONS** BINDING per `project_phase13_t4_sb_pause_for_list_additions` memory — orchestrator MUST surface the pause at T2.SB6 SHIPPED + housekeeping boundary; do NOT proceed past T2.SB6 housekeeping without operator's added items.

**Forward-binding lessons expected from T3.SB3 to T2.SB6 + T4.SB:**
- `auto_populated_field_keys_json` audit trail rendering pattern (T2.SB6 closed-loop UI may surface this).
- Phase 8 source-ladder pattern (Phase 8 → OhlcvCache fallback) — sets precedent for other helpers consuming hybrid data sources.
- Per-row failure isolation in cohort iteration (inherited from T2.SB5; extended in T3.SB3; sets precedent for any future cohort-iterating helper).
- 22nd cumulative C.C lesson #6 validation with BOTH scope expansions applied (sets precedent for all future dispatches).
- ZERO `Co-Authored-By` trailer streak (~318+ cumulative commits expected post-T3.SB3 merge + housekeeping).

---

*End of dispatch brief. Phase 13 T3.SB3 (5 tasks; +40-70 fast tests + 1 fast E2E + 1 cross-bundle pin un-skip projected; v20 schema UNCHANGED) — review auto-fill (priors + MFE/MAE) consuming OhlcvCache + Phase 8 substrate + existing review_log. Inherits T2.SB5 forward-binding lessons (composite clamp discipline + bad-exemplar isolation + pre-Codex spec source-of-truth cross-check) + T3.SB1 + T3.SB2 form-driven discipline (hidden anchor 4-tier rejection + recovery anchor-clear + server-stamping + price-precision parity + envelope.pop optional keys) + cumulative Phase 13 disciplines (HTMX 3-surface + session-anchor + Python `... or None` SQL nullability + Literal runtime-enforcement). 2-4 Codex rounds expected for small-mid scope. **22nd cumulative C.C lesson #6 validation expected with BOTH SCOPE EXPANSIONS BINDING** (grep `swing/` for hardcoded duplicates of any new T3.SB3 constants + cross-check spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 BINDING text byte-for-byte vs brief sketches). ZERO Co-Authored-By footer drift streak (~312+ commits at handoff) preserved.*
