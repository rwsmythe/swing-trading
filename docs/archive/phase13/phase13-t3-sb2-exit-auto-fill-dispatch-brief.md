# Phase 13 T3.SB2 — Exit auto-fill via Schwab Trader API dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-20 PM post-T2.SB3 SHIPPED + housekeeping + orchestrator-handoff at main HEAD `cb88329`. Mid-sized sub-bundle (5 tasks; +40-70 fast tests + 1 slow Schwab E2E projected per plan §H). Per plan §G.5 lines 1736-1879.

**Branch:** `phase13-t3-sb2-exit-auto-fill` — branches from main HEAD `cb88329` at dispatch time (per plan §G.5 line 1740 + §A.1 sequence: T3.SB2 dispatches AFTER T2.SB3 merge to avoid Schwab Trader API consumer merge conflicts).

**Worktree:** create via `git worktree add .worktrees/phase13-t3-sb2-exit-auto-fill phase13-t3-sb2-exit-auto-fill`.

**Time estimate:** orchestrator wall-clock 5-8 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x for accuracy; T3.SB2 is mid-sized — symmetric to T3.SB1's 6-task entry-side scope but folded to 5 tasks because T-A.1.1's v20 prerequisite is now LANDED on main).

---

## §1 Scope summary

**SELL-side mirror of T3.SB1 entry auto-fill, with multi-partial-exit handling as the NEW architectural dimension.** Per spec §6.2 + plan §G.5. T3.SB2 pre-populates trade exit form fields from Schwab Trader API at form-render time (`GET /trades/{id}/exit/form`); `fill_origin` enum transitions + hidden audit anchors + Schwab audit-row emit with `surface='trade_exit'` (CHECK enum already widened at v20 per T-A.1.1 atomic landing; no migration in this dispatch).

| Task | Title | Tests target |
|---|---|---|
| T-B.2.1 | `swing/trades/exit_auto_fill.py` — Schwab fetch + value resolution (with multi-partial candidate list) | 7+ tests |
| T-B.2.2 | `exit_form` handler + ExitFormVM extension + template auto-fill rendering (single + multi-partial) | 7+ tests |
| T-B.2.3 | `exit_post` — fill_origin transition + audit row + soft-warn form_values round-trip | 7+ tests |
| T-B.2.4 | Cassette infrastructure extension for `trade_exit` surface + 1 slow Schwab E2E | 1 slow |
| T-B.2.5 | T3.SB2 closer — integration E2E + ruff sweep + cross-bundle pin un-skip | 1 fast E2E |

Per plan §G.5 dispatch sequence verbatim. Cross-bundle pin un-skip at `tests/data/test_v20_migration.py:907` (`test_fill_origin_enum_complete_after_v20`) per plan §H.3 row 4. T2.SB3's T-A.3.9 is the canonical un-skip precedent.

### §1.1 Inheritance from T2.SB3 + T3.SB1 + T2.SB1 forward-binding lessons

T3.SB2 is the SECOND Schwab-Trader-integrated web-form sub-bundle (after T3.SB1) + the FIRST sub-bundle dispatched after the post-T2.SB3 forward-binding lesson capture. Inherited disciplines:

**From T2.SB3 return report §7 (banked at `368784f` housekeeping + handoff brief §2.2):**
1. **`EvalRunResolutionError` typed-exception precedent** — any code path that derives a session-anchor date from a pipeline-run anchor (NOT wall-clock) inherits the typed-exception + defensive best-effort wrapper pattern. **T3.SB2 likely N/A** at the auto-fill layer (exit form-render uses the trade's `entry_date` ISO string + `last_completed_session(now())` per spec §6.2; NOT pipeline-run anchor); BUT if any audit-row stamping or session-anchor lookup is added, honor the pattern. Verify at T-B.2.1 recon.
2. **Bar-clipping discipline at detector entry** — applies to any exit-time bar-consuming logic (clip `bars` to `bars.index <= exit_anchor_date` BEFORE downstream extraction). **T3.SB2 likely N/A** (exit auto-fill doesn't consume OHLCV bars; consumes Schwab order responses + persists fill rows); BUT if any future code path adds bar consumption (e.g., for an exit-time MFE/MAE recompute), honor the discipline. Verify at T-B.2.1 recon.
3. **Two-pass-then-reconcile-then-serialize architectural pattern** — applies if a step emits multiple rows with cross-row dependencies. **T3.SB2 likely N/A** (exit is per-fill; no cross-row recompute); verify at T-B.2.1 recon if multi-partial path appears to need it.

**From T3.SB1 return report (entry-side precedent; T3.SB2 inherits Schwab integration discipline verbatim):**
4. **`apply_overrides(cfg)` at handler entry** — both `exit_form` (now at `swing/web/routes/trades.py:1651`) and `exit_post` (`:1665`) MUST call FIRST per §A.11. Pattern from T3.SB1: `cfg = apply_overrides(base_cfg)` BEFORE any Schwab path. Verified at T3.SB1's `swing/web/routes/trades.py:344` (entry_form) + `:451` (entry_post).
5. **`resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)`** BINDING per CLAUDE.md gotcha "form-render-time prompts would block HTTP handler". `allow_prompt=False` form REQUIRED. T3.SB1 precedent at `swing/trades/entry_auto_fill.py:313`.
6. **`construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg signature** — post-Phase-12 Sub-bundle 1 + Phase 12 Sub-bundle B locked. T3.SB1 precedent at `swing/trades/entry_auto_fill.py:344`.
7. **`trader.get_account_orders(surface='trade_exit')`** — surface CHECK enum widened at v20 to include both `trade_entry` AND `trade_exit` per T-A.1.1; no further migration. T3.SB1 emits `surface='trade_entry'` at `swing/trades/entry_auto_fill.py:368`; T3.SB2 emits `surface='trade_exit'` symmetric.
8. **HTMX gotcha trinity** preserved on any new embedded form/HTMX response: `hx-headers='{"HX-Request": "true"}'` propagation + HX-Redirect-not-303-swap + HX-Redirect target route registered. T3.SB1 precedent at `swing/web/templates/partials/trade_entry_form.html.j2:40`.
9. **Base-layout VM banner pin** — `ExitFormVM` populates `unresolved_material_discrepancies_count` + `recent_multi_leg_auto_correction_count` + `banner_resolve_link` (per project convention duplication, NOT inheritance — Codex R1 Major #4 ACCEPT at T3.SB1; banked V2 for inheritance refactor). T3.SB1 precedent at `swing/web/view_models/trades.py:357-360`.
10. **Sandbox + DEGRADED + PROVISIONAL short-circuits BEFORE Schwab client construction** — auto-fill returns empty + advisory; audit row STILL written; domain rows NOT (per §A.11). T3.SB1 precedent at `swing/trades/entry_auto_fill.py:245-253` (sandbox) + `:275-288` (DEGRADED via `cli_schwab._compute_degraded_state`).
11. **Hidden anchor 4-tier rejection ladder** + `_reject_anchor` helper — NEW from T3.SB1 Codex R1-R4 hardening; CLAUDE.md gotcha BANKED. Pattern: (a) malformed JSON → 400 + clear anchor; (b) non-dict JSON → 400 + clear; (c) dict missing required keys → 400 + clear; (d) dict with invalid values (NaN/non-int/calendar-invalid) → 400 + clear. Plus `claimed_auto_fill` anti-forgery gate (valid anchor without claim must NOT stamp provenance). T3.SB1 precedent at `swing/web/routes/trades.py:896` (`_reject_anchor` helper).
12. **Recovery form anchor-clear discipline** — on 400 rejection, pass `submitted_*=None` to re-render helper (NOT raw rejected anchor) — otherwise operator gets trapped in repeated 400s on tampered/replayed bad anchor. NEW CLAUDE.md gotcha from T3.SB1 Codex R3 Major #2.
13. **Schema-version-aware INSERT pattern** at `swing/data/repos/fills.py:51-53` — already covers fills inserts via `PRAGMA table_info` branching for backward-compat with pre-v20 fixtures. T3.SB2 fills writes inherit verbatim (no new code needed); discriminating test asserts existing-fixtures unaffected.

**From T2.SB1 forward-binding lesson #8 + CLAUDE.md gotcha:**
14. **`Literal[...]` not runtime-enforced** — `ExitAutoFillResult` + `ExitAutoFillCandidate` frozen dataclasses with `Literal[...]` fields (e.g., `fill_origin` Literal-typed) MUST add `__post_init__` runtime validation against an explicit frozenset.

### §1.2 NEW dimension: multi-partial-exit handling (vs T3.SB1 single-fill entry)

T3.SB1 ENTRY-side: Schwab returns 0 or 1 matching BUY fill since some lookback window; populate single set of auto_fill values OR empty advisory.

T3.SB2 EXIT-side: Schwab can return MULTIPLE matching SELL fills since `entry_date` (operator may have scaled out via multiple partial sells). Per spec §6.2 paragraph 2 + plan §G.5 T-B.2.1 step 1(e): if Schwab returns >1 SELL fill matching ticker since `entry_date`, return `candidates: list[ExitAutoFillCandidate]` (each with date / price / quantity / signature_hash); operator picks one OR enters a consolidated value at form submit.

**Per-task discipline at T-B.2.1**: `ExitAutoFillResult` frozen dataclass has `candidates: list[ExitAutoFillCandidate] | None` field; single-fill case populates length-1 list (template still renders selection UI for UX consistency) OR direct-fill convenience field (operator decision at recon).

**Per-task discipline at T-B.2.2**: template renders candidate list as selectable radio-button group when len ≥ 2; renders auto-populated input values when len == 1; advisory banner when len == 0 OR sandbox/DEGRADED short-circuit.

**Per-task discipline at T-B.2.3**: POST handler resolves operator's selection (radio-button value); persists selected candidate's values + records other candidates' `signature_hash` in `schwab_source_value_json` envelope for audit history (so subsequent reconciliation can see what other candidates were available at form-render time).

---

## §2 Per-task acceptance criteria (per plan §G.5 verbatim)

| Task | Title | Acceptance |
|---|---|---|
| T-B.2.1 | `swing/trades/exit_auto_fill.py` — Schwab fetch + value resolution | 7 discriminating tests: matching fill / no fills / sandbox / DEGRADED / multi-partial list / `resolve_credentials` trace / `construct_authenticated_client` trace. Multi-partial returns list of candidates. §A.11 4-step Schwab discipline followed. `ExitAutoFillResult` + `ExitAutoFillCandidate` frozen dataclasses with `__post_init__` Literal[...] frozenset validation. |
| T-B.2.2 | `exit_form` handler + ExitFormVM extension + template | 7 discriminating tests: auto-fill populated / advisory when no match / sandbox short-circuit / hidden anchors present / multi-partial list rendering / VM extends BaseLayoutVM (or duplicates banner-pin fields per project convention) / VM populates banner-pin helpers. HTMX trinity preserved (`hx-headers='{"HX-Request": "true"}'`). |
| T-B.2.3 | `exit_post` — fill_origin transition + audit row + soft-warn | 7 discriminating tests: persists `schwab_auto` when no edits / flips to `schwab_auto_then_operator_corrected` when edited / persists `operator_typed` when no auto-fill OR claim absent / emits `surface='trade_exit'` audit row / soft-warn confirm round-trips hidden anchors via `form_values` dict / `... or None` (NOT `... or ''`) for nullable audit fields / multi-partial selection persists chosen candidate + preserves other candidates' `signature_hash` in envelope. Hidden anchor 4-tier rejection ladder + `_reject_anchor` helper reused (or mirrored). |
| T-B.2.4 | Cassette infrastructure extension for `trade_exit` surface + slow E2E | 1 slow Schwab E2E test PASSES via cassette replay; cassette covers single-fill + multi-partial response variants; sanitization filters cover `trade_exit` surface (URI + body per §A.10). |
| T-B.2.5 | T3.SB2 closer — integration E2E + ruff sweep + cross-bundle pin un-skip | 1 fast E2E PASSES end-to-end (open trade fixture → mock Schwab SELL fill → GET form → POST → fill row created with correct `fill_origin` + audit columns + audit row `surface='trade_exit'`; trade state transitioned). Full fast-suite + ruff sweep PASS. Cross-bundle pin un-skipped at `tests/data/test_v20_migration.py:907`. |

**Recommended ordering**: T-B.2.1 (service layer; pure function, no DB writes) → T-B.2.2 (form handler + VM + template) → T-B.2.3 (POST handler + audit row + soft-warn) → T-B.2.4 (cassette + slow E2E) → T-B.2.5 (closer + cross-bundle pin un-skip).

**Note on plan-cited line numbers**: plan §G.5 line 1743 cites `exit_form at line 1229 + exit_post at line 1243`. These are STALE post-T3.SB1 + T2.SB3 merges; current main HEAD `cb88329` puts `exit_form` at `swing/web/routes/trades.py:1651` and `exit_post` at `:1665`. Implementer SHOULD cite current symbol locations in commit messages + test refs; plan-cited line numbers are advisory only.

---

## §3 Files in scope

**Create** (1 production module + 3 test files):
- `swing/trades/exit_auto_fill.py` (mirror `swing/trades/entry_auto_fill.py` shape; ~300-400 LOC including multi-partial handling)
- `tests/trades/test_exit_auto_fill.py`
- `tests/web/test_routes/test_exit_form_auto_fill.py`
- `tests/web/test_routes/test_exit_post_audit_columns.py`
- `tests/integrations/test_schwab_exit_auto_fill_e2e.py` (1 slow E2E)
- `tests/integration/test_phase13_t3_sb2_exit_auto_fill_e2e.py` (1 fast E2E at closer)

**Modify**:
- `swing/web/routes/trades.py` (`exit_form` at `:1651` + `exit_post` at `:1665`; integrate auto-fill + audit + soft-warn round-trip + 4-tier rejection ladder)
- `swing/web/view_models/trades.py` (extend `ExitFormVM` with auto-fill fields + banner-pin fields per T3.SB1 precedent at `:357-360`)
- `swing/web/templates/trades/exit_form.html.j2` (and/or `partials/trade_exit_form.html.j2` — verify at T-B.2.1 recon which path the GET handler templates against; T3.SB1 used the partial)
- `swing/integrations/schwab/audit_service.py` (verify `surface='trade_exit'` accepted by `_SCHWAB_API_SURFACE_VALUES` constant; the v20 CHECK widening should have paired the constant per §A.14 atomic-landing LOCK — if not, add)
- `tests/integrations/cassettes/schwab/` (NEW cassette files for `trade_exit` surface)
- `scripts/record_schwab_cassettes.py` (extend with `trade_exit` recording targets per §A.10)
- `tests/data/test_v20_migration.py:907` (un-skip cross-bundle pin at T-B.2.5 closer)

**NOT in scope (V2 / future sub-bundles)**:
- Schema changes (v20 LOCKED; if any test surfaces a schema need, STOP + escalate per dispatch §B.6 precedent from T3.SB1)
- Review auto-fill (T3.SB3 territory)
- Detectors batch 2 (T2.SB4 territory)
- Template matching DTW (T2.SB5)
- VM inheritance refactor (T3.SB1 R1 Major #4 banked V2)
- Hidden-anchor V2 architectural hardening (T3.SB1 R1 Critical #1 banked V2: `schwab_api_call_id` server-side audit-row lookup pattern)
- Fractional-share support (T3.SB1 R1 Minor #1 banked V2)
- "Reset to Schwab values" button on rejection-recovery form (T3.SB1 R4 Major #2 banked V2)

---

## §4 Watch items (cumulative discipline; banked across Phase 12 + 12.5 + 13)

### §4.1 T3.SB2-specific watch items

1. **§A.11 Schwab integration discipline trinity** at both `exit_form` + `exit_post`: `apply_overrides(cfg)` → `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` → `construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg. Mirror T3.SB1 verbatim. Mock-verify each callsite via trace test.
2. **Multi-partial-exit handling** per §1.2: `ExitAutoFillResult.candidates: list[ExitAutoFillCandidate] | None` field; len ≥ 2 renders selectable radio group; operator-selected candidate persisted at POST; non-selected candidates' `signature_hash` preserved in `schwab_source_value_json` envelope for audit history.
3. **HTMX gotcha trinity** preserved on any new embedded form/HTMX response: `hx-headers='{"HX-Request": "true"}'` propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted disciplines (T3.SB1 verified at `swing/web/templates/partials/trade_entry_form.html.j2:40`; mirror for trade_exit_form).
4. **Hidden anchor 4-tier rejection ladder** per CLAUDE.md gotcha + T3.SB1 R1-R4 hardening: `_reject_anchor` helper at `swing/web/routes/trades.py:896` is the reusable template — REUSE if possible (extract to module-level helper); else mirror inside `exit_post`. 4 tiers: malformed JSON → 400 + clear; non-dict JSON → 400 + clear; missing required keys → 400 + clear; invalid value shapes (NaN/non-int/calendar-invalid date) → 400 + clear. Plus `claimed_auto_fill` anti-forgery gate.
5. **Recovery form anchor-clear discipline** per CLAUDE.md gotcha + T3.SB1 R3 Major #2: on 400 rejection, pass `submitted_*=None` to re-render helper (NOT raw rejected anchor).
6. **Server-stamping at handler entry for hidden audit fields** per Phase 8 R2-R5 family: render display-only `<span class="muted">` for `auto_fill_audit_at` + `fill_origin_at_form_render`; hidden inputs only for the JSON envelope (`schwab_source_value_json`) that the POST handler needs to verify.
7. **Soft-warn confirm `form_values` round-trip** per Phase 9 Sub-bundle D R3 Critical #1: every hidden form-render anchor present in the soft-warn confirm fragment's `form_values` dict (so tampered `force=true` resubmit can't bypass validation).
8. **`... or None` (NOT `... or ''`)** for nullable enum-CHECK columns per Phase 6 CLAUDE.md gotcha.
9. **Base-layout VM banner pin** on `ExitFormVM` per §A.18 (`unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count`). Mirror T3.SB1 duplication convention (NOT inheritance) per Codex R1 Major #4 ACCEPT at T3.SB1 unless implementer + operator agree to lead the V2 inheritance refactor here (escalate first).
10. **`fill_origin` enum transitions** for SELL side: `schwab_auto` (auto-populated, unmodified) → `schwab_auto_then_operator_corrected` (operator overrode) → `operator_typed` (never auto-populated OR cleared OR claim absent). Tested across the 5 V1 values; cross-bundle pin verifies enum coverage.
11. **Sandbox + DEGRADED + PROVISIONAL short-circuits BEFORE Schwab client construction** per §A.11 + T3.SB1 precedent. Audit row STILL written; domain rows NOT. Discriminating tests for both sandbox AND DEGRADED.
12. **Schwab `account_orders` API kwargs**: `Client.account_orders(account_hash, maxResults=..., fromEnteredTime=..., toEnteredTime=..., status='FILLED')` — camelCase kwarg discipline per existing CLAUDE.md gotcha "schwabdev camelCase kwarg discipline" + Sub-bundle B `34be84e` defect family. **NOT** `price_history` — T3.SB2 consumes `account_orders` only (per spec §6.2). If implementer needs price_history for any reason, the daily-vs-minute-default footgun CLAUDE.md gotcha BINDS (explicit `period_type='month', period=1, frequency_type='daily', frequency=1` kwargs).
13. **Execution-grain price + quantity resolution** per post-Phase-12 Sub-bundle 1 LIFT: REUSE `_compute_execution_price(SchwabOrderResponse)` + `_resolve_match_quantity(SchwabOrderResponse)` from `swing/trades/schwab_reconciliation.py:99,174` — do NOT duplicate; do NOT use raw `so.price`. Plan §G.5 T-B.2.1 step 2 explicit.
14. **Cross-bundle pin un-skip at T-B.2.5** BINDING per plan §H.3 row 4: remove `@pytest.mark.skip(...)` decorator at `tests/data/test_v20_migration.py:907`. Test body is pure schema-CHECK-shape assertion; should PASS immediately at un-skip (T-A.1.1 v20 atomic landing already widened the enum). Leaving skipped extends pin window silently (CLAUDE.md gotcha "Cross-bundle pin fixture-shape mismatch").

### §4.2 Cumulative process discipline

15. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 19th cumulative validation expected)** — implementer dispatches a focused reviewer subagent with this brief's §3 file-scope + §4 watch items + §5 done criteria as anchors BEFORE invoking Codex MCP. Verdict captured in return report. 18 prior cumulative validations CLEAN.
16. **NO `Co-Authored-By` footer** — cumulative ~263+ commit streak ZERO trailer drift through T2.SB3 housekeeping; do NOT regress. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): explicit citation in commit messages required.
17. **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (memory `feedback_worktree_cli_invocation`).
18. **ASCII-only on any new CLI/print path** — runtime CLI paths bind (Windows cp1252 footgun); banner / advisory text rendered in template is fine.
19. **Edit tool for per-file edits** when fixing E501 / type / import-order issues — do NOT bulk-rewrite (Phase 12.5 #3 L-W4 precedent).
20. **Cite the discipline in commit messages** (matches all prior T1.SB0 + T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 commit-message precedent).
21. **TDD discipline per task** via `superpowers:test-driven-development` (write failing test → see fail → minimal implementation → see pass → commit).

---

## §5 Done criteria

### §5.1 S1 (inline; implementer self-verifies before invoking Codex)

- [ ] All 5 T-B.2.X tasks committed per plan §G.5 acceptance criteria.
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post-merge. **Expected**: 5257 + ~40-70 new fast tests + 1 fast E2E from closer = ~5300-5330 total; 0 failures; ≤4 skipped (T-B.2.5 un-skips `test_fill_origin_enum_complete_after_v20`, bringing skipped from 5 → 4).
- [ ] `python -m pytest -m slow tests/integrations/test_schwab_exit_auto_fill_e2e.py -q` PASS for the 1 NEW slow E2E.
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20 (`python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"` returns `20`).
- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured (19th cumulative C.C lesson #6 validation expected CLEAN).
- [ ] All commits on branch `phase13-t3-sb2-exit-auto-fill` have empty `Co-Authored-By` trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t3-sb2-exit-auto-fill --not main | grep -c .` returning 0).
- [ ] Codex MCP adversarial-critic chain converges to `NO_NEW_CRITICAL_MAJOR` (expected 2-4 rounds based on mid-sized scope + Schwab-integration symmetric inheritance from T3.SB1).

### §5.2 S2-S5 (operator-paired post-merge per plan §G.5 lines 1870-1876)

- **S2 (browser)**: `/trades/{id}/exit/form` against operator's open position → confirm auto-fill values populate from a recent Schwab SELL fill.
- **S3 (browser edit)**: operator edits pre-populated price; submits; confirms `fill_origin='schwab_auto_then_operator_corrected'` in resulting fill row.
- **S4 (multi-partial)**: operator triggers (or replays) a partial-exit scenario; confirms list-of-candidates rendering; operator selects expected one; resulting fill row carries selected values + envelope preserves other candidates' signature_hash.
- **S5 (DB audit)**: `SELECT call_id, surface, ... FROM schwab_api_calls WHERE surface='trade_exit' ORDER BY started_at DESC LIMIT 5;` returns recent rows from the S2/S3/S4 exercise.

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Spec §6.2 entry/exit symmetry + multi-partial handling discipline BIND verbatim. Implementer reads spec §6.2; does NOT paraphrase.
- **L2**: ZERO schema changes (v20 LOCKED). Surface CHECK enum already widened at T-A.1.1 to include `trade_entry` + `trade_exit`. If any test surfaces a schema need, STOP + escalate per dispatch §B.6 precedent.
- **L3**: NO `INSERT OR REPLACE` on `fills` writes. SELECT-then-INSERT (or repo-layer `insert_fill_with_event` which already handles schema-version-aware INSERT at `swing/data/repos/fills.py:51-53`).
- **L4**: Cross-bundle pin at `tests/data/test_v20_migration.py:907` MUST un-skip at T-B.2.5 closer. Skipping it (leaving as-is) violates plan §H.3 row 4 schedule + extends the pin window silently.
- **L5**: Branch base = main HEAD `cb88329` at dispatch time. Verify at T-B.2.1 Step 0: `git merge-base --is-ancestor cb88329 HEAD` returns 0.
- **L6**: Frozen dataclasses (`ExitAutoFillResult`, `ExitAutoFillCandidate`) carry `__post_init__` Literal[...] frozenset validation honoring T-A.1.5b R3 M#1 CLAUDE.md gotcha.
- **L7**: Hidden anchor 4-tier rejection ladder + `_reject_anchor` helper REUSED (extract to module-level if not already) — do NOT inline-duplicate inside `exit_post`. Recovery form anchor-clear discipline per T3.SB1 R3 Major #2 CLAUDE.md gotcha BINDING.
- **L8**: `resolve_credentials_env_or_prompt(allow_prompt=False)` BINDING — `allow_prompt=True` form would block HTTP handler; CLAUDE.md gotcha. Mock-verified at T-B.2.1 trace test.

---

## §7 Reference materials (read before dispatching)

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.5 lines 1736-1879 (T3.SB2 verbatim 5-task spec).
- **Plan**: §A.10 cassette infrastructure LOCK (line 202) + §A.11 Schwab integration discipline LOCK (line 211) + §A.14 schema-CHECK+Python-constant paired LOCK (line 247) + §A.15 no `INSERT OR REPLACE` on audit-trail tables LOCK (line 270) + §A.18 discrepancies helper hand-off LOCK (line 287).
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` §6.2 exit auto-fill + §6.4 fill_origin enum + §11 forward-binding lessons.
- **T3.SB1 dispatch brief** at `docs/phase13-t3-sb1-executing-plans-dispatch-brief.md` — mirror Schwab integration discipline + HTMX trinity + base-layout VM banner pin + hidden anchor 4-tier rejection precedents.
- **T3.SB1 return report** at `docs/phase13-t3-sb1-return-report.md` — concrete file:line refs verified above; 8 forward-binding lessons banked for T3.SB2 inheritance.
- **T2.SB3 return report** at `docs/phase13-t2-sb3-return-report.md` §4 + §7 — 3 forward-binding lessons (likely N/A but verify at T-B.2.1 recon).
- **CLAUDE.md gotchas relevant to T3.SB2**:
  - `Literal[...]` not runtime-enforced (T-A.1.5b R3 M#1 inherited)
  - HTMX gotcha trinity (Phase 5 R1 M1 + M2 + Phase 6 I3 — three browser-only failure surfaces)
  - Server-stamping at handler entry for hidden audit fields (Phase 8 R2-R5)
  - Form-render hidden anchors round-trip through soft-warn confirm form_values (Phase 9 Sub-bundle D R3 Critical #1)
  - `... or None` not `... or ''` for nullable enum-CHECK columns (Phase 6)
  - SELECT-first idempotency precedes payload validation (Phase 12 C.C R1 Major #2)
  - schwabdev camelCase kwarg discipline (Sub-bundle B `34be84e` defect family)
  - Schwab `price_history` defaults to MINUTE bars (NEW 2026-05-19; N/A for T3.SB2 if `account_orders` only; verify at recon)
  - Schema-version-aware INSERT (T3.SB1 NEW)
  - Hidden anchor 4-tier rejection ladder (T3.SB1 NEW)
  - Recovery form anchor-clear discipline (T3.SB1 NEW)
  - ASCII-only on runtime CLI paths (cp1252 footgun)
  - Cross-bundle pin fixture-shape mismatch silently extends pin window (T2.SB1 T-A.1.8)
- **Existing entry-side prod modules** at `swing/trades/entry_auto_fill.py` (300+ LOC; mirror shape) + `swing/web/routes/trades.py:exit_form (:1651)` + `:exit_post (:1665)` + `swing/web/view_models/trades.py:TradeEntryFormVM (:357-360 banner pin)`.

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T3.SB2 merge ships:

1. **CLAUDE.md line 3 refresh** — update HEAD reference + mention T3.SB2 SHIPPED + 19th cumulative C.C lesson #6 validation; mention any NEW gotchas surfaced (likely none if implementer mirrors T3.SB1 verbatim, but Codex may surface fresh).
2. **phase3e-todo.md** — new top entry for T3.SB2 SHIPPED with: Codex chain shape + any ACCEPT-WITH-RATIONALE banks + forward-binding lessons for T2.SB4 / T3.SB3 / T2.SB5 / T2.SB6 inheritance + multi-partial empirical observations (operator-witnessed gate findings); cross-bundle pin un-skip confirmation at `tests/data/test_v20_migration.py:907`.
3. **orchestrator-context.md** — refresh current state; demote former current to Prior. **SIZE-CHECK TRIGGER WILL FIRE** — Prior state count is 10 at cap pre-housekeeping per handoff brief §0; demote pushes to 11; archive oldest Prior to `orchestrator-context-archive.md` "Appended 2026-05-2X" section per retention discipline.
4. **orchestrator-context-archive.md** — new "Appended 2026-05-2X" section with archived Prior verbatim.
5. **Streaks update** — bank the 19th cumulative C.C lesson #6 validation (if CLEAN); bank ~273+ cumulative ZERO Co-Authored-By streak (T3.SB2 expected ~8-12 commits).
6. **CLAUDE.md gotchas section** — append any NEW gotchas surfaced by Codex (likely candidates: multi-partial-exit envelope-preservation discipline; trade_exit cassette sanitization edge cases; SELL-side reconciliation drift if operator's broker statement diverges from Schwab's API response).

---

## §9 Forward-binding to T2.SB4 + T3.SB3 + T2.SB5 + T2.SB6

T2.SB4 = Detectors batch 2 (HTF + DBW) (7 tasks; plan §G.6). Inherits ALL T2.SB3 detector patterns. T3.SB2 does NOT touch detector substrate; no direct binding.

T3.SB3 = Review auto-fill consuming OhlcvCache (per spec §6.3). Inherits T3.SB1 + T3.SB2 hidden-anchor + value-validation discipline VERBATIM. Cross-bundle pin schedule continues; review-side may extend `fill_origin` semantics (TBD).

T2.SB5 = Template matching DTW + 120s benchmark. Inherits T2.SB3 + T2.SB4 detector substrate; T3.SB2 no direct binding.

T2.SB6 = Closed-loop surface + Theme 1 annotated charts. Inherits ALL Phase 13 substrate. T3.SB2's multi-partial-exit envelope semantics MAY surface as cohort-analysis filter (e.g., partial-exit fills routed to a different outcome metric vs single-exit fills); banked for T2.SB6 brainstorming.

**Forward-binding lessons expected from T3.SB2 to T3.SB3 + future arc:**
- Multi-partial-exit envelope-preservation discipline (NEW; SELL-side specific; review auto-fill may or may not inherit depending on whether review-time MFE/MAE recompute touches per-fill data).
- `_reject_anchor` helper extraction precedent (if implementer extracts to module-level shared helper, T3.SB3 inherits + Phase 14+ schwab-integrated forms inherit).
- 19th cumulative C.C lesson #6 validation (expected CLEAN; banked at T3.SB2 housekeeping).
- ZERO `Co-Authored-By` trailer streak (~273+ cumulative commits expected post-T3.SB2 merge + housekeeping).

---

*End of dispatch brief. Phase 13 T3.SB2 (5 tasks; +40-70 fast tests + 1 slow Schwab E2E + 1 fast E2E projected) — SELL-side mirror of T3.SB1 entry auto-fill with multi-partial-exit handling as the NEW architectural dimension. Inherits Schwab integration discipline + HTMX trinity + base-layout VM banner pin + hidden anchor 4-tier rejection + recovery anchor-clear + schema-version-aware INSERT from T3.SB1 VERBATIM. 2-4 Codex rounds expected for mid-sized scope. 19th cumulative C.C lesson #6 validation expected CLEAN. ZERO Co-Authored-By footer drift streak (~263+ commits at handoff) preserved.*
