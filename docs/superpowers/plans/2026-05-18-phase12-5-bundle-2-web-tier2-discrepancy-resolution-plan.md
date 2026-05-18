# Phase 12.5 #2 — Web Tier-2 Discrepancy-Resolution Surface — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`) to implement this plan task-by-task in a SINGLE executing-plans dispatch. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the operator-facing web counterpart to the existing `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` CLI — a dedicated `/reconcile/discrepancy/{id}/resolve` GET/POST page that renders the per-ambiguity-kind choice menu + a pre-resolution context section + invokes `apply_tier2_resolution(resolved_by_override='operator_web')` on submit + HX-Redirects back to `/dashboard` on success. CLI surface stays AS-IS; surface attribution via free-TEXT `reconciliation_discrepancies.resolved_by` (`'operator'` for CLI vs `'operator_web'` for web). Schema v19 UNCHANGED.

**Architecture:** Three layers, single sub-bundle. (1) View-model + builder + parametric-pick helper in NEW `swing/web/view_models/reconcile.py` (pure module — no DB writes, no I/O, no transaction management). (2) Route handlers in NEW `swing/web/routes/reconcile.py` (GET form-render + POST form-parse → `apply_tier2_resolution` → 204 + HX-Redirect; full error catch-ladder). (3) `BaseLayoutVM.banner_resolve_link: str | None = None` retrofit across `BaseLayoutVM` AND the 13 standalone-field base-layout VMs (Pass A field-declaration grep + Pass B builder/route population grep); new helpers `list_pending_ambiguities_in_banner_set` + `fetch_first_pending_ambiguity_resolve_link_path` in `swing/metrics/discrepancies.py`; `base.html.j2` wraps the banner count in an `<a>` link when populated.

**Tech Stack:** Python 3.14, SQLite, FastAPI + HTMX + Jinja2, Starlette `TemplateResponse(request, name, ctx, status_code=...)` signature, pytest + pytest-xdist. NO Schwab SDK consumption (web form does not call Schwab API). NO new third-party dependencies.

**Schema:** v19 **UNCHANGED LOCK** (spec §14 audit verified — `reconciliation_corrections` has NO `surface` column; surface attribution via existing free-TEXT `reconciliation_discrepancies.resolved_by` column with NEW value `'operator_web'`; ZERO CHECK enum widening; ZERO Python constant; ZERO dataclass validator). NO migration in this plan. NO `0020_*.sql`.

---

## Table of contents

- §0 Plan overview + cross-references
- §A Task list (T-2.1 … T-2.11) — per-task scope + acceptance + tests + commit
- §B Pre-conditions + worktree state
- §C Files touched (canonical roster + grep anchors)
- §D Locked decisions roll-up (12 binding clauses, verbatim attribution)
- §E Test patterns + discriminating-test naming convention
- §F Invariants (non-negotiable contracts spanning multiple tasks)
- §G Per-task acceptance-criteria narrative (deeper-than-§A treatment for tasks spanning multiple files)
- §H Operator-witnessed gate plan (6 surfaces)
- §I Cross-bundle pins (single-bundle dispatch; consumer of shipped Sub-bundle C.D + Phase 12.5 #1 + Sub-bundle B surfaces)
- §J V2.1 §VII.F amendment candidates banked during planning (scaffold)
- §K Test + LOC projections (refined per-task)
- §L Dispatch brief skeleton (orchestrator hand-off for executing-plans)
- §M Forward-binding lessons for executing-plans (scaffold; populated post-Codex)
- §N Open questions for orchestrator triage (scaffold; default empty)
- §Z V2 candidates banked (13 from spec §15)

---

## §0 Plan overview + cross-references

| Anchor | Location |
|---|---|
| Locked spec (721 lines; 6 Codex rounds NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked R1 M#4) | `docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md` |
| Writing-plans dispatch brief (this plan's instructions) | `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-writing-plans-dispatch-brief.md` (commit `b4d08a6`) |
| Brainstorm return report (8 forward-binding lessons) | `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-return-report.md` |
| Brainstorm dispatch brief | `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-dispatch-brief.md` (commit `d642175`) |
| Phase 12.5 #1 plan (format reference; closest scope precedent) | `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` |
| Phase 12 Sub-bundle B `/schwab/setup` route (1:1 route format reference) | `swing/web/routes/schwab.py:220-451` |
| Phase 12 Sub-bundle B Schwab setup VM (base-layout-fields-on-non-inheriting-VM reference) | `swing/web/view_models/schwab.py:29-110` |
| Phase 12 Sub-sub-bundle C.B classifier (read-only consumer of `get_choice_menu`) | `swing/trades/reconciliation_classifier.py` |
| Phase 12 Sub-sub-bundle C.C service entry (web POST calls this) | `swing/trades/reconciliation_auto_correct.py:328-390 (apply_tier2_resolution)` |
| Phase 12 Sub-sub-bundle C.D choice-menu helper (web GET consumes this) | `swing/trades/reconciliation_ambiguity_choices.py:254` (`get_choice_menu`) |
| Phase 12 Sub-sub-bundle C.D CLI parametric-pick regex (DUPLICATED into web VM per §1.2 #11 LOCK) | `swing/cli.py:2291` |

**Scope intent:** the brainstorm consumed 6 Codex rounds with ZERO Critical findings + 1 ACCEPT-WITH-RATIONALE banked → the spec is exhaustively locked. The plan's job is **to operationalize the locked design**, NOT to re-derive it. Codex review on this plan should converge in 3-5 rounds because most architectural decisions are spec-locked + 12 operator decisions are pre-baked.

**Cross-bundle position:** Phase 12.5 #2 is bracketed by Phase 12.5 #1 (SHIPPED 2026-05-18 at `6109261` — multi-leg tier-1 auto-redirect; supplies `BaseLayoutVM.recent_multi_leg_auto_correction_count` retrofit precedent) and Phase 12.5 #3 (project-hygiene maintenance pass — separate dispatch). Phase 12 Sub-sub-bundles C.A → C.D shipped the auto-correct reconciliation architecture; this plan is a pure read-only consumer of `apply_tier2_resolution`, `get_choice_menu`, and `get_discrepancy`.

---

## §A Task list

**Decomposition** — 11 tasks (T-2.1 … T-2.11) for a single executing-plans dispatch. Ordering is dependency-driven with one minor deviation: T-2.7 (BaseLayoutVM field DECLARATION) lands BEFORE T-2.9 (banner helper + per-route POPULATION) so the field default `None` is valid everywhere from the first commit of the retrofit pass. Each task ends with a tiny commit; do not batch.

### Task T-2.1 — `_parse_parametric_pick_count` helper (pure)

**Files:**
- Create: `swing/web/view_models/reconcile.py` (NEW module — placeholder skeleton with module docstring + the helper only; subsequent tasks add VMs + builder).
- Test: `tests/web/test_reconcile_parametric_pick_count.py` (NEW).

**Acceptance:**

- New private module-level function `_parse_parametric_pick_count(resolution_reason: str | None) -> int` returns the integer N parsed from `"Schwab returned (\d+) orders within the match window"` regex, else 0.
- Regex pattern is BYTE-FOR-BYTE the same compiled pattern as `swing/cli.py:2291` (operator §1.2 #11 LOCK; DRY consolidation V2-deferred per §15.13).
- Behavior on edge inputs:
  - `None` → 0.
  - Empty string → 0.
  - Non-matching text (no "Schwab returned" substring) → 0.
  - Matching text with N=0 (`"Schwab returned 0 orders within the match window"`) → 0.
  - Matching text with N=1 → 1.
  - Matching text with N=3 → 3.
- The function is **PURE** — no DB, no I/O, no logging, no side-effects per CLAUDE.md "Classifier is a PURE function" precedent applied here to a parser helper.
- Module docstring cites spec §5.4 + §16.7 LOCK + V2 candidate §15.13 verbatim so a maintainer reading the helper understands why the regex is duplicated rather than imported from `swing/cli.py`.

**Tests added (~5):**

- `test_parse_parametric_pick_count_none_returns_0`
- `test_parse_parametric_pick_count_empty_returns_0`
- `test_parse_parametric_pick_count_no_match_returns_0`
- `test_parse_parametric_pick_count_match_returns_n` (parametrized over N ∈ {1, 3, 7}).
- `test_parse_parametric_pick_count_byte_identical_to_cli_parser` — behavioral-parity regression test (LOCK §1.2 #11): plant a shared list of `resolution_reason` strings; assert `_parse_parametric_pick_count(s) == _cli_parametric_count(s)` for every input. `_cli_parametric_count` is a small helper inside the test file that replicates `cli.py:2288-2316`'s parametric construction logic (count `len(parametric)` entries built) — NOT a source-equality assertion. Test fails loudly if either side drifts in behavior.

**Commit message stem:** `feat(web): add _parse_parametric_pick_count helper for web Tier-2 form (Phase 12.5 #2 T-2.1)`

**Dependencies:** none (pure helper).

---

### Task T-2.2 — `ReconcileDiscrepancyResolveVM` + sub-VMs + per-discrepancy-type render helpers

**Files:**
- Modify: `swing/web/view_models/reconcile.py` — add three frozen dataclasses (`ReconcilePreResolutionContext`, `ReconcileChoiceFormItem`, `ReconcileDiscrepancyResolveVM`) + 10 per-discrepancy-type render helpers + generic fallback.
- Test: `tests/web/test_reconcile_resolve_vm.py` (NEW) — VM construction tests + per-type render helper tests.

**Acceptance:**

- `ReconcileDiscrepancyResolveVM` is a `@dataclass(frozen=True)` with the **18 fields** enumerated in spec §5.1 verbatim:
  - 8 BaseLayoutVM-shaped fields: `session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded`, `unresolved_material_discrepancies_count`, `recent_multi_leg_auto_correction_count`, `banner_resolve_link`. Declared as standalone fields (NOT inherited via `BaseLayoutVM`) to match the existing non-metrics-package convention documented at `swing/web/view_models/schwab.py:29-37`.
  - 10 page-specific fields: `discrepancy_id`, `form_action`, `pre_resolution_context`, `choices`, `prior_choice_code`, `prior_custom_value_raw`, `prior_resolution_reason`, `prior_ambiguity_kind_at_render`, `error_band_message`, `error_band_field_hint`. Each typed per spec §5.1.
- `ReconcilePreResolutionContext` is a `@dataclass(frozen=True)` with the 14 fields per spec §5.2.
- `ReconcileChoiceFormItem` is a `@dataclass(frozen=True)` with the 6 fields per spec §5.3 (`code`, `description`, `requires_custom_value`, `recommended`, `expected_payload_shape_description`, `is_parametric_pick`).
- All three dataclasses have `__post_init__` validation:
  - `session_date` non-empty (mirror of `SchwabSetupVM.__post_init__`).
  - `unresolved_material_discrepancies_count >= 0` and `recent_multi_leg_auto_correction_count >= 0` (mirror).
  - `banner_resolve_link` is `None` OR non-empty string starting with `/` (defensive).
  - `discrepancy_id > 0`.
  - `form_action` matches `f"/reconcile/discrepancy/{discrepancy_id}/resolve"` byte-for-byte (server-derived; prevents form-action drift).
- **10 per-discrepancy-type render helpers** as PRIVATE module-level functions `_render_pre_resolution_context_<discrepancy_type>(disc, expected, actual) -> ReconcilePreResolutionContext` covering every discrepancy_type enumerated across spec §7.1's table (9 rows; row 7 groups `unmatched_open_fill` + `unmatched_close_fill` under a shared specification, but the plan implements them as separate helpers for type-safety + per-side label clarity — `journal_side_label='Journal fill'` is identical but the per-side semantics around the `actual['matched']` payload differ between open + close in the audit shape):
  - `entry_price_mismatch`, `close_price_mismatch`, `stop_mismatch`, `position_qty_mismatch`, `cash_movement_mismatch`, `snapshot_mismatch`, `unmatched_open_fill`, `unmatched_close_fill`, `equity_delta`, `sector_tamper`.
  - Each helper is PURE; consumes `disc` (the `ReconciliationDiscrepancy` dataclass) + the parsed `expected_value_json` dict + the parsed `actual_value_json` dict (parsed by the calling dispatch function; helpers do NOT re-parse JSON).
  - Numeric fields render with `:.2f` formatting (spec §7.1 + Phase 12 Sub-sub-bundle C.B Codex M#3 LOCK precedent).
- Dispatch function `_render_pre_resolution_context(disc) -> ReconcilePreResolutionContext`:
  - Parses `expected_value_json` + `actual_value_json` via `json.loads` inside `try/except (json.JSONDecodeError, TypeError)` (graceful degradation per CLAUDE.md "External-API empty-result must be treated as transient" family — NEVER raise from a pure renderer).
  - Looks up the per-type helper in a module-level dict `_RENDER_HELPERS_BY_DISCREPANCY_TYPE`.
  - Falls back to a generic renderer when (a) the type is not in the dispatch dict, OR (b) JSON parse failed, OR (c) the per-type helper raised a `KeyError` (missing-key on the expected path). Generic renderer renders `expected_value_json` + `actual_value_json` truncated to 80 chars + sets `parse_warning='<reason>'`.

**Tests added (~12):**

- `test_reconcile_discrepancy_resolve_vm_construction` — happy path with all fields populated.
- `test_reconcile_discrepancy_resolve_vm_post_init_rejects_negative_unresolved_count`.
- `test_reconcile_discrepancy_resolve_vm_post_init_rejects_zero_discrepancy_id`.
- `test_reconcile_discrepancy_resolve_vm_post_init_rejects_form_action_mismatch` — pass `discrepancy_id=99` + `form_action="/reconcile/discrepancy/100/resolve"`; assert raises.
- `test_reconcile_pre_resolution_context_renders_entry_price_mismatch` — plant `expected_value_json='{"price": 5.30}'` + `actual_value_json='{"price": 5.23}'`; assert `journal_side_value == "5.30"` + `schwab_side_value == "5.23"` + `delta_value == "-0.07"` (signed, formatted to 2 decimals).
- `test_reconcile_pre_resolution_context_renders_unmatched_open_fill_n_eq_3` — plant `disc.resolution_reason="Schwab returned 3 orders within the match window"`, `actual_value_json='{"matched": null}'`; assert `schwab_side_value == "3 candidates within window"`, `delta_value == "3"`, `delta_label == "Schwab record count"`.
- `test_reconcile_pre_resolution_context_renders_unmatched_open_fill_matched_null_zero_count` — `resolution_reason` does NOT match the regex; assert `schwab_side_value == "(none)"`.
- `test_reconcile_pre_resolution_context_generic_fallback_on_unknown_discrepancy_type` — assert `parse_warning is not None` + `journal_side_value` includes truncated raw JSON.
- `test_reconcile_pre_resolution_context_generic_fallback_on_malformed_json` — `expected_value_json='{invalid'`; assert `parse_warning` cites parse failure; helper does NOT raise.
- `test_reconcile_pre_resolution_context_generic_fallback_on_missing_key` — per-type helper raises `KeyError`; dispatch catches + falls back; `parse_warning` non-None.
- `test_reconcile_choice_form_item_is_parametric_pick_true_for_pick_schwab_record_prefix` — code `pick_schwab_record_3` → `is_parametric_pick is True`.
- `test_reconcile_choice_form_item_is_parametric_pick_false_for_static_codes` — code `keep_journal_as_is` → `is_parametric_pick is False`.

**Commit message stem:** `feat(web): add ReconcileDiscrepancyResolveVM + sub-VMs + per-discrepancy-type render helpers (Phase 12.5 #2 T-2.2)`

**Dependencies:** T-2.1.

---

### Task T-2.3 — `build_reconcile_discrepancy_resolve_vm` builder

**Files:**
- Modify: `swing/web/view_models/reconcile.py` — add `build_reconcile_discrepancy_resolve_vm` per spec §5.4 signature.
- Test: `tests/web/test_reconcile_resolve_vm_builder.py` (NEW).

**Acceptance:**

- Builder signature matches spec §5.4 verbatim:
  ```python
  def build_reconcile_discrepancy_resolve_vm(
      conn: sqlite3.Connection,
      discrepancy_id: int,
      *,
      prior_choice_code: str = "",
      prior_custom_value_raw: str = "",
      prior_resolution_reason: str = "",
      prior_ambiguity_kind_at_render: str = "",
      error_band_message: str | None = None,
      error_band_field_hint: str | None = None,
  ) -> ReconcileDiscrepancyResolveVM
  ```
- Builder flow:
  1. Calls `get_discrepancy(conn, discrepancy_id)`. Raises `ValueError('discrepancy not found')` when None (route catches BEFORE calling builder; documented precondition).
  2. Asserts `disc.ambiguity_kind is not None` and `disc.resolution == 'pending_ambiguity_resolution'` (precondition; raises `ValueError` otherwise).
  3. Calls `_render_pre_resolution_context(disc)` per T-2.2.
  4. Calls `get_choice_menu(disc.ambiguity_kind)` and builds the static `ReconcileChoiceFormItem` tuple — one per `ChoiceMenuItem`, with `is_parametric_pick=False`.
  5. For `disc.ambiguity_kind == 'multi_match_within_window'`, calls `_parse_parametric_pick_count(disc.resolution_reason)`. For N > 0, PREPENDS N parametric `ReconcileChoiceFormItem` entries with `code=f'pick_schwab_record_{i+1}'`, `description='Pick Schwab candidate #...'` (mirrors `cli.py:2300-2315` verbatim text), `requires_custom_value=True`, `is_parametric_pick=True`, `expected_payload_shape_description='{"price": X.XX, "quantity": Q, "fill_datetime": "..."}'`.
  6. Calls `count_unresolved_material(conn)` for the BaseLayoutVM field.
  7. Calls `count_recent_multi_leg_auto_corrections(conn)` for the BaseLayoutVM field.
  8. Calls `fetch_first_pending_ambiguity_resolve_link_path(conn)` (T-2.9; resolves to None until that task lands — see T-2.9 note for the ordering rationale; until T-2.9 ships the builder MAY pass `None` directly so this T-2.3 commit ships green).
  9. Computes `session_date = action_session_for_run(datetime.now()).isoformat()`.
  10. Returns the assembled VM with `form_action=f"/reconcile/discrepancy/{discrepancy_id}/resolve"`.
- The builder does NOT call `apply_overrides` (route owns cfg-cascade per F14).
- The builder does NOT open a transaction; it is read-only on `conn`.

**Tests added (~8):**

- `test_builder_returns_vm_for_pending_ambiguity_discrepancy` — happy path with seeded discrepancy (pending_ambiguity_resolution + multi_partial_vs_consolidated).
- `test_builder_raises_when_discrepancy_id_not_found` — `discrepancy_id=9999` → raises `ValueError('discrepancy not found')`.
- `test_builder_raises_when_discrepancy_in_terminal_state` — seeded discrepancy with `resolution='operator_resolved_ambiguity'` → raises `ValueError`.
- `test_builder_raises_when_ambiguity_kind_is_null` — seeded discrepancy with `ambiguity_kind=None` → raises `ValueError`.
- `test_builder_static_menu_renders_choices_for_multi_partial_vs_consolidated` — assert `vm.choices` length == 4 + first item `code='keep_journal_as_is'` + `recommended=True`.
- `test_builder_prepends_parametric_pick_choices_for_multi_match_within_window_n_eq_3` — seeded `multi_match_within_window` with `resolution_reason='Schwab returned 3 orders within the match window'`; assert `vm.choices` length == 3 (parametric) + N (static); first 3 codes are `pick_schwab_record_1` / `_2` / `_3`; each has `is_parametric_pick=True` + `requires_custom_value=True`.
- `test_builder_emits_no_parametric_choices_when_resolution_reason_does_not_match` — seeded `multi_match_within_window` + `resolution_reason='garbage'`; assert ZERO parametric entries; static menu intact.
- `test_builder_assembles_form_action_url_from_discrepancy_id` — assert `vm.form_action == f"/reconcile/discrepancy/{discrepancy_id}/resolve"` (server-derived; not operator-supplied).

**Commit message stem:** `feat(web): add build_reconcile_discrepancy_resolve_vm builder (Phase 12.5 #2 T-2.3)`

**Dependencies:** T-2.1 + T-2.2.

---

### Task T-2.4 — `reconcile_discrepancy_resolve.html.j2` template

**Files:**
- Create: `swing/web/templates/reconcile_discrepancy_resolve.html.j2` (NEW; per spec §6 skeleton).
- Test: `tests/web/test_reconcile_resolve_template.py` (NEW) — TestClient renders form against a seeded discrepancy and asserts DOM substrings.

**Acceptance:**

- Template extends `base.html.j2` (inherits the global banner + nav + theme toggle for free).
- Template renders the pre-resolution context section ABOVE the form (operator-locked §1.2 #4 / spec §2.4):
  - `<section class="pre-resolution-context" data-pre-context="true">` containing a `<dl>` with the 10 context pairs from spec §6 + the classifier-reason paragraph + the parse-warning paragraph (only when populated) + CLI-parity hint `<code>swing journal discrepancy show-ambiguity {{ vm.discrepancy_id }}</code>`.
- Template renders the error-band section (`<section class="error-band">`) ONLY when `vm.error_band_message` is truthy, with `data-error-field="{{ vm.error_band_field_hint or '' }}"`.
- Template renders the form section:
  - `<form method="post" action="{{ vm.form_action }}" hx-post="{{ vm.form_action }}" hx-headers='{"HX-Request": "true"}' hx-target="body" data-resolve-form="true">` — the `hx-headers` attribute is BINDING per F4 (OriginGuard strict-mode HX-Request propagation; Phase 5 R1 M1 LOCK).
  - `<input type="hidden" name="ambiguity_kind_at_render" value="{{ vm.pre_resolution_context.ambiguity_kind }}">` — TOCTOU hidden anchor per F8.
  - Choice radio fieldset iterating `vm.choices`. Each radio carries `data-requires-custom-value="{{ choice.requires_custom_value|tojson }}"` (the inline `<script>` consumes this).
  - Recommended badge + payload-required badge + shape-hint paragraph rendered per spec §6 verbatim.
  - `prior_choice_code` is `{% if vm.prior_choice_code == choice.code %}checked{% endif %}` per spec §6 (re-render preserves operator's prior selection byte-for-byte).
  - Custom-value textarea ALWAYS rendered (per §1.2 #10 LOCK — JS is UX nicety only; server enforces `requires_custom_value` contract). Initial value `{{ vm.prior_custom_value_raw }}`.
  - Resolution-reason textarea (`required` HTML5 attribute) with initial value `{{ vm.prior_resolution_reason }}`.
  - Submit button.
- 12-line inline `<script>` block toggling the `custom-value-fieldset` visibility based on the focused radio's `data-requires-custom-value` attribute. Attached via `addEventListener` (CSP-clean per Phase 12 Sub-bundle B precedent — NO inline `onclick=`). Falls back gracefully when JS is disabled (fieldset always rendered).
- All template text is **ASCII-ONLY** per F12 (Windows cp1252 stdout gotcha + Phase 12 C.D gate-fix #3 inheritance). Plan §A T-2.4 ban list: `§` (use the literal word "section"), `→` (use `->`), em-dash, en-dash, fractions, arrows, quote-glyphs, fancy bullets. The plan-author has scanned spec §6's skeleton for these chars and confirmed ASCII-only.

**Tests added (~6):**

- `test_resolve_template_extends_base_layout` — assert the rendered HTML contains the `data-banner=` discriminator from `base.html.j2` (the dashboard banner DOM).
- `test_resolve_template_renders_pre_resolution_context_for_entry_price_mismatch` — assert `data-pre-context="true"` substring + `Journal entry price` + `Schwab entry price` + the `:.2f` rendered numeric.
- `test_resolve_template_renders_hx_headers_attribute_semantically` — parse rendered HTML via the test's BeautifulSoup helper (or `html.parser` stdlib equivalent) + extract the `hx-headers` attribute on the form element + assert `json.loads(value) == {"HX-Request": "true"}` (Codex R1 m#4 fix: semantic equality is robust against harmless Jinja/HTML quote normalization; the prior exact-substring approach would have flaked on `&quot;` HTML-entity encoding). Complement: keep an additional `test_resolve_template_renders_hx_headers_attribute_present` substring assertion `'hx-headers='` (presence only; no quote-style coupling) to catch the regression where the attribute is silently dropped. F4 LOCK; Phase 5 R1 M1 regression pin.
- `test_resolve_template_renders_ambiguity_kind_at_render_hidden_input` — assert `<input type="hidden" name="ambiguity_kind_at_render" value="multi_partial_vs_consolidated">` substring (F8 hidden-anchor regression pin).
- `test_resolve_template_renders_custom_value_textarea_always` — even when no choice currently selected, the textarea is in the DOM (JS-disabled fallback; F9).
- `test_resolve_template_ascii_only_codepoints` — iterate rendered HTML; assert `max(ord(c) for c in body) < 128` (F12).

**Commit message stem:** `feat(web): add reconcile_discrepancy_resolve.html.j2 template (Phase 12.5 #2 T-2.4)`

**Dependencies:** T-2.2 + T-2.3 (template rendering tests construct VMs via the builder).

---

### Task T-2.5 — `GET /reconcile/discrepancy/{id}/resolve` route handler

**Files:**
- Create: `swing/web/routes/reconcile.py` (NEW module; GET handler + helper imports + router).
- Modify: `swing/web/app.py` — import + `app.include_router(reconcile_router)` after the existing `schwab_router` mount.
- Test: `tests/web/test_reconcile_resolve_get_route.py` (NEW).

**Acceptance:**

- New `router = APIRouter()` at module level (matches Phase 12 Sub-bundle B precedent at `swing/web/routes/schwab.py:68`).
- `@router.get("/reconcile/discrepancy/{discrepancy_id}/resolve", response_class=HTMLResponse)` decorator on `def reconcile_discrepancy_resolve_form(request: Request, discrepancy_id: int) -> Response`.
- Handler flow per spec §4.1:
  1. `cfg = apply_overrides(request.app.state.cfg)` (Phase 12 Sub-bundle B Codex R1 Critical #1 inheritance at every web entry; F14 LOCK).
  2. `conn = sqlite3.connect(cfg.paths.db_path)` followed by `try: ... finally: conn.close()` (Codex R3 M#3 LOCK — connection closure guaranteed on ALL paths including 404 / 409 early-returns).
  3. `disc = get_discrepancy(conn, discrepancy_id)`. None → render `reconcile_discrepancy_resolve_error.html.j2` with `error_kind='not_found'` + status_code=404.
  4. `disc.resolution != 'pending_ambiguity_resolution' OR disc.ambiguity_kind is None` → error template with `error_kind='already_resolved'` + status_code=409 + echo `disc.resolution`, `disc.resolved_by`, `disc.created_at`.
  5. `vm = build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id)`.
  6. Return `request.app.state.templates.TemplateResponse(request, "reconcile_discrepancy_resolve.html.j2", {"vm": vm})`.
- ZERO Schwab API calls. ZERO DB writes. ZERO transaction openings.
- **Error-template VM + template stub lands at T-2.5 (per Codex R1 M#1 task-ordering fix; ensures T-2.5 ships green).** T-2.5 acceptance covers BOTH (a) the GET handler AND (b) a MINIMAL stub of `swing/web/templates/reconcile_discrepancy_resolve_error.html.j2` (handles `error_kind in {'not_found', 'already_resolved'}` only) PLUS the `ReconcileDiscrepancyErrorVM` dataclass in `swing/web/view_models/reconcile.py` (full 8-base-layout-field + `error_kind` + `error_message` + `discrepancy_id` + `disc_resolution` + `disc_resolved_by` + `disc_created_at` shape; the 3 disc_* fields are Optional and unused by the 2 stub branches). T-2.10 then EXPANDS the template to add the 3 remaining branches (`anchor_mismatch` / `service_error` / `db_unavailable`) — used by T-2.6's 400/409/500/503 paths. This stub-then-expand pattern parallels Phase 12 Sub-bundle B's `swing/web/templates/schwab_setup_error.html.j2` precedent (initial stub + later widening).

**Tests added (~7):**

- `test_get_returns_200_for_pending_ambiguity_discrepancy` — seeded discrepancy in pending_ambiguity_resolution state; assert 200 + body contains `data-resolve-form="true"`.
- `test_get_returns_404_for_unknown_discrepancy_id` — assert status_code 404 + body contains `error_kind` substring `not_found`.
- `test_get_returns_409_for_terminal_resolution` — seed `resolution='operator_resolved_ambiguity'`; assert 409 + body cites the terminal resolution value.
- `test_get_returns_409_for_null_ambiguity_kind` — seed `pending_ambiguity_resolution` but `ambiguity_kind=NULL` (defensive — shouldn't normally happen); assert 409.
- `test_get_closes_db_connection_on_404_path` — patch `sqlite3.connect` to return a `Mock`; assert `conn.close()` called even on early-return 404 (F13).
- `test_get_calls_apply_overrides` — patch `apply_overrides` and assert it was called with `request.app.state.cfg` (F14 regression pin).
- `test_get_route_registered_on_app_routes` — `assert any(r.path == "/reconcile/discrepancy/{discrepancy_id}/resolve" and r.methods == {"GET"} for r in app.routes)` (defense-in-depth; Phase 6 I3 lesson family).

**Commit message stem:** `feat(web): add GET /reconcile/discrepancy/{id}/resolve route handler (Phase 12.5 #2 T-2.5)`

**Dependencies:** T-2.3 + T-2.4 (template-rendering happy-path test exercises the full pipeline).

---

### Task T-2.6 — `POST /reconcile/discrepancy/{id}/resolve` route handler

**Files:**
- Modify: `swing/web/routes/reconcile.py` — add the POST handler + the error catch-ladder helpers.
- Test: `tests/web/test_reconcile_resolve_post_route.py` (NEW).

**Acceptance:**

- `@router.post("/reconcile/discrepancy/{discrepancy_id}/resolve")` decorator on `async def reconcile_discrepancy_resolve_post(request: Request, discrepancy_id: int) -> Response`.
- Handler flow per spec §4.2 verbatim:
  1. `cfg = apply_overrides(request.app.state.cfg)`.
  2. `form = await request.form()`. Extract:
     - `choice_code = (form.get("choice_code") or "").strip()` — required; empty → 400 + re-render.
     - `custom_value_raw = form.get("custom_value") or None` — note `... or None` per F6 (CLAUDE.md `... or None` gotcha; nullable text columns must not coerce empty to `""`).
     - `resolution_reason = (form.get("resolution_reason") or "").strip()` — required; empty → 400.
     - `ambiguity_kind_at_render = (form.get("ambiguity_kind_at_render") or "").strip()` — hidden anchor (F8).
  3. `conn = sqlite3.connect(cfg.paths.db_path)` with `try/finally: conn.close()`.
  4. Pre-flight checks (read-only on `conn`; route does NOT open a transaction):
     a. `disc = get_discrepancy(conn, discrepancy_id)`. None → 404 error template.
     b. `disc.resolution != 'pending_ambiguity_resolution' OR disc.ambiguity_kind is None` → 409 error template.
     c. Hidden-anchor check (F8):
        - `ambiguity_kind_at_render == ""` → 400 error template "Form is stale or tampered; please re-open the resolve form".
        - `disc.ambiguity_kind != ambiguity_kind_at_render` → 409 error template "Discrepancy state changed since form was rendered; please re-open".
     d. `choice_code == ""` → 400 + re-render (NOT error template) with `error_band_field_hint='choice_code'`.
     e. `resolution_reason == ""` → 400 + re-render with `error_band_field_hint='resolution_reason'`.
     f. Static-menu validation: `menu = get_choice_menu(disc.ambiguity_kind)`; `static_codes = {item.code for item in menu}`.
        - If `choice_code in static_codes`: `menu_item = next(item for item in menu if item.code == choice_code)`. If `menu_item.requires_custom_value AND custom_value_raw is None` → 400 + re-render with shape-hint citing `menu_item.expected_payload_shape_description`.
     g. Parametric-pick validation (only when `disc.ambiguity_kind == 'multi_match_within_window'` AND `choice_code.startswith('pick_schwab_record_')`):
        - Parse N via `int(choice_code.removeprefix('pick_schwab_record_'))`; catch `ValueError` → 400 + re-render "Choice 'pick_schwab_record_X' has non-integer suffix".
        - N < 1 → 400 + re-render "Pick index must be >= 1".
        - `parsed_count = _parse_parametric_pick_count(disc.resolution_reason)`; `N > parsed_count` → 400 + re-render "Choice 'pick_schwab_record_{N}' is out of range; Schwab returned {parsed_count} candidates within the match window. Valid range: pick_schwab_record_1 .. pick_schwab_record_{parsed_count}.".
        - Parametric picks always require `custom_value_raw` (F10 LOCK; mirrors CLI `cli.py:2538`). Missing → 400 + re-render with shape-hint `'{"price": X.XX, "quantity": Q, "fill_datetime": "..."}'`.
     h. No-match branch: `choice_code` neither in `static_codes` nor a valid parametric pick → 400 + re-render with `valid_choices` echoed. When `disc.ambiguity_kind == 'multi_match_within_window'`, `valid_choices = sorted(static_codes) + [f'pick_schwab_record_{i+1}' for i in range(_parse_parametric_pick_count(disc.resolution_reason))]` so the error text presents the full operator-visible menu (Codex R1 m#3 fix; mirrors the form-render menu that surfaced these codes in the GET response). When ambiguity_kind is NOT multi_match_within_window, `valid_choices = sorted(static_codes)` only.
     i. `custom_value_raw is not None` AND `len(custom_value_raw.strip()) > 0`: parse via `json.loads`; `JSONDecodeError` → 400 + re-render citing `exc.msg` + preserving operator's typed value byte-for-byte.
  5. Service call:
     ```python
     environment = getattr(
         getattr(getattr(cfg, "integrations", None), "schwab", None),
         "environment",
         "production",
     )
     result = apply_tier2_resolution(
         conn,
         discrepancy_id=discrepancy_id,
         choice_code=choice_code,
         operator_custom_payload=custom_payload,
         operator_reason=resolution_reason,
         resolved_by_override="operator_web",  # F2 LOCK (surface attribution)
         environment=environment,
     )
     ```
     - `applied_by_override` + `correction_action_override` are NOT passed (default-None preserves manual-operator legacy shape per F3 LOCK).
  6. Service-exception catch-ladder per spec §4.2 step 5 verbatim (each maps to a distinct HTTP response):
     - `CallerHeldTransactionError` → 500 (developer-bug class; should not fire — defense-in-depth).
     - `InvalidOverrideComboError` → 500 (developer-bug class; should not fire — web passes only `resolved_by_override='operator_web'` which is unrelated to the auto-redirect triple per F17).
     - `ValidatorRejectedError` → 400 + re-render with validator's rejection text in error band.
     - `AlreadySupersededError` → 409 + error template (defense-in-depth for race against tier-3 override of earlier chain entry).
     - `ValueError` → **split disposition** (Codex R1 M#2 fix; spec §8.2 race semantics): catch the `ValueError` from `apply_tier2_resolution`, then **re-read** the discrepancy via `get_discrepancy(conn, discrepancy_id)`. If the re-read shows `disc.resolution != 'pending_ambiguity_resolution'` (i.e., a concurrent writer landed between the route's pre-flight check and the service call — the inner's "verify precondition" raised `ValueError` because the discrepancy concurrently moved to a terminal state), respond with **409 + error template** (`error_kind='already_resolved'`) — NOT 400 + re-render (re-rendering would loop the operator through a builder that asserts `resolution='pending_ambiguity_resolution'` precondition + raise). Otherwise (re-read still shows pending; the `ValueError` originated from handler payload-shape rejection or unknown handler), respond with **400 + re-render** citing `str(exc)`. Discriminating test pattern: plant a concurrent-resolve race via two TestClient threads (or simulate via a `monkeypatch.setattr(apply_tier2_resolution, ...)` that mutates the discrepancy + re-raises `ValueError`); assert the 409 branch fires + the operator sees a clean explanation rather than an internal-error loop.
     - `sqlite3.OperationalError` (DB locked) → 503 + error template + retry hint.
     - Bare `Exception` → 500 + error template + redacted excerpt + `log.warning(type(exc).__name__)`.
  7. Success path:
     - `correction_id = result.correction_id` (non-None on manual tier-2 paths; sandbox short-circuit applies ONLY to auto-redirect per F16 — web V1 never triggers).
     - HTMX submit (request carries `HX-Request: true` header — guaranteed under OriginGuard strict-mode because the form template carries `hx-headers`): `Response(status_code=204, headers={"HX-Redirect": f"/dashboard?reconcile_resolved={correction_id}"})`.
     - Non-HTMX submit (only reachable under OriginGuard non-strict): `RedirectResponse(url=f"/dashboard?reconcile_resolved={correction_id}", status_code=303)` per Phase 12 Sub-bundle B `swing/web/routes/schwab.py:451` byte-for-byte mirror.
- The handler does NOT open its own transaction (F7 LOCK; service-layer owns BEGIN IMMEDIATE / COMMIT / ROLLBACK per Phase 8 R3-R4 + CLAUDE.md `Service-layer with conn:` gotcha).

**Tests added (~8):**

- `test_post_happy_path_returns_204_with_hx_redirect_to_dashboard` — seeded discrepancy; submit `keep_journal_as_is` + valid reason + matching hidden anchor; assert 204 + `HX-Redirect: /dashboard?reconcile_resolved={correction_id}` header.
- `test_post_writes_reconciliation_corrections_row_with_applied_by_operator` — assert `reconciliation_corrections.applied_by = 'operator'` (CHECK constraint LOCK; web does NOT widen to 'web') + `correction_action = 'operator_resolved_ambiguity'`.
- `test_post_flips_discrepancy_resolved_by_to_operator_web` — assert `reconciliation_discrepancies.resolved_by = 'operator_web'` (F2 LOCK; distinguishability from CLI).
- `test_post_returns_400_on_empty_choice_code` — assert status_code 400 + body contains `error_band_field_hint` substring.
- `test_post_returns_409_on_hidden_anchor_mismatch` — submit `ambiguity_kind_at_render='unsupported'` against a `multi_partial_vs_consolidated` discrepancy; assert 409 + body cites "state changed".
- `test_post_returns_400_on_pick_schwab_record_out_of_range` — seeded `multi_match_within_window` with `resolution_reason="Schwab returned 3 ..."`; submit `choice_code=pick_schwab_record_5`; assert 400 + body cites "out of range" + `Valid range: pick_schwab_record_1 .. pick_schwab_record_3`.
- `test_post_returns_400_on_malformed_custom_value_json` — submit `custom_value='{invalid'`; assert 400 + body cites `json.loads` error + `prior_custom_value_raw` preserved byte-for-byte in re-render.
- `test_post_returns_400_when_validator_rejected_error_raised` — patch `apply_tier2_resolution` to raise `ValidatorRejectedError("price must be > 0")`; assert 400 + body cites rejection text.
- `test_post_value_error_concurrent_race_returns_409_not_400` — NEW (Codex R1 M#2 acceptance pin): patch `apply_tier2_resolution` to (a) mutate `disc.resolution` to `'operator_resolved_ambiguity'` via direct UPDATE, then (b) raise `ValueError("discrepancy is no longer pending")`. Submit POST; assert response is **409 + error template** (NOT 400 + re-render). Asserts the re-read disambiguation logic in branch 14b is wired correctly.

**Commit message stem:** `feat(web): add POST /reconcile/discrepancy/{id}/resolve route handler (Phase 12.5 #2 T-2.6)`

**Dependencies:** T-2.1 + T-2.5.

---

### Task T-2.7 — `BaseLayoutVM.banner_resolve_link` field + 13-VM standalone retrofit

**Files:**
- Modify: `swing/web/view_models/metrics/shared.py` — add `banner_resolve_link: str | None = None` to `BaseLayoutVM` dataclass + `__post_init__` range check.
- Modify: 13 standalone-field VMs across 9 files per the Pass A grep audit (see §C.1).
- Test: `tests/web/test_base_layout_vm_banner_resolve_link.py` (NEW).

**Acceptance:**

- `BaseLayoutVM` gains the field declared adjacent to `recent_multi_leg_auto_correction_count` (Phase 12.5 #1 sibling pattern):
  ```python
  # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity
  # discrepancy resolve form. None when no pending-ambiguity row in the
  # banner-count set; URL when one exists. Per spec §10.1 + §1.2 #5 LOCK.
  banner_resolve_link: str | None = None
  ```
- `BaseLayoutVM.__post_init__` extends the existing validation chain with a check rejecting non-`None`/non-string OR empty-string values (defensive — must be either None or a non-empty URL starting with `/`).
- All 13 standalone-field VMs gain `banner_resolve_link: str | None = None` declaration adjacent to the existing `unresolved_material_discrepancies_count` field declaration. Pass A grep at task start enumerates the exact set; the 13 anchors documented in §C.1 are the CURRENT baseline (will be re-verified by the implementer at task start; new VMs landing after this plan are caught by the T-2.8 grep-driven introspection test).
- Every VM's `__post_init__` (where one exists) extends the validation chain with a parallel range check. VMs without a `__post_init__` MUST gain one (per CLAUDE.md Codex R5 m#2 LOCK — defense-in-depth against future construction with invalid values).
- Each modified file commits separately is NOT required — T-2.7 is one task = one commit covering all 13 sites + `BaseLayoutVM` itself. The plan-author chose this packing because retrofit is mechanical + the test in T-2.8 audits completeness across all sites in one shot.

**Tests added (~10):**

- `test_base_layout_vm_banner_resolve_link_defaults_to_none` — `BaseLayoutVM(session_date='2026-05-18')` → `banner_resolve_link is None`.
- `test_base_layout_vm_banner_resolve_link_post_init_rejects_empty_string` — `BaseLayoutVM(session_date='2026-05-18', banner_resolve_link='')` → raises.
- `test_base_layout_vm_banner_resolve_link_post_init_accepts_url` — `banner_resolve_link='/reconcile/discrepancy/99/resolve'` → no raise.
- `test_base_layout_vm_banner_resolve_link_post_init_rejects_non_slash_prefix` — `banner_resolve_link='reconcile/discrepancy/99/resolve'` (missing leading `/`) → raises.
- 6 introspection tests parametrized over the 13 retrofit sites: `test_<vm_name>_has_banner_resolve_link_field_with_default_none` (one parametrize entry per VM class). Implementer uses `dataclasses.fields(VMClass)` to enumerate.

**Commit message stem:** `feat(web): add BaseLayoutVM.banner_resolve_link + retrofit 13 standalone-field VMs (Phase 12.5 #2 T-2.7)`

**Dependencies:** none (purely additive; no consumer of the field exists yet).

---

### Task T-2.8 — `base.html.j2` banner-link integration + retrofit completeness audit

**Files:**
- Modify: `swing/web/templates/base.html.j2` — wrap the banner count text in an `<a>` link when `vm.banner_resolve_link` is truthy.
- Test: `tests/web/test_base_layout_banner_resolve_link.py` (NEW) — retrofit completeness audit + DOM-shape regression tests.

**Acceptance:**

- Banner block at `base.html.j2:95-108` is amended so the count text becomes a link when `vm.banner_resolve_link` is non-None:
  ```html
  {% if (vm.unresolved_material_discrepancies_count|default(0)) > 0 %}
  <aside class="banner banner-warn"
         data-banner="unresolved-material-discrepancies"
         data-count="{{ vm.unresolved_material_discrepancies_count }}">
    <span class="banner-glyph" aria-hidden="true">!</span>
    <strong>
      {% if vm.banner_resolve_link %}
      <a href="{{ vm.banner_resolve_link }}" data-banner-resolve-link="true">
        {{ vm.unresolved_material_discrepancies_count }} unresolved material reconciliation
        {%- if vm.unresolved_material_discrepancies_count == 1 %} discrepancy
        {%- else %} discrepancies{%- endif %}.
      </a>
      {% else %}
      {{ vm.unresolved_material_discrepancies_count }} unresolved material reconciliation
        {%- if vm.unresolved_material_discrepancies_count == 1 %} discrepancy
        {%- else %} discrepancies{%- endif %}.
      {% endif %}
    </strong>
    Resolve via <code>swing journal discrepancy</code> CLI.
  </aside>
  {% endif %}
  ```
- **Pre-existing `⚠` (U+26A0) banner-glyph is PRESERVED.** F12 ASCII-only LOCK applies to NEW substrings landing in this task (the `data-banner-resolve-link="true"` attribute + the `<a href=...>` markup + any new wrapper text). The operator-witnessed gate for Phase 10 T-E.3 + Phase 12.5 #1 T-1.9 already accepted the existing `⚠` glyph in the banner-glyph span; touching it would be an out-of-scope regression. Discriminating test asserts NEW substrings are ASCII-only; the `<span class="banner-glyph">⚠</span>` literal is character-class-allowlisted (U+26A0 exempted explicitly).
- ALL OTHER new template text (the `data-banner-resolve-link="true"` attribute + the `<a href=` markup + any new wrapper substrings) MUST be ASCII-only.
- The retrofit completeness audit test:
  - Runs Pass A grep at test time: `subprocess.check_output(["rg", "-l", "unresolved_material_discrepancies_count\\s*:\\s*int\\s*=", "swing/web/view_models/"])` → list of files.
  - For each file, imports the module + iterates `inspect.getmembers(module, inspect.isclass)` filtering for dataclasses with the `unresolved_material_discrepancies_count` field.
  - Asserts EVERY such dataclass ALSO has a `banner_resolve_link` field with default `None`.
  - Fails loudly with the offending class name when a future VM lands carrying `unresolved_material_discrepancies_count` but not `banner_resolve_link` (Codex R5 M#1 LOCK; mirrors Phase 10 T-A.7 cross-bundle pin discriminating-test pattern).

**Tests added (~8):**

- `test_banner_template_renders_anchor_when_banner_resolve_link_populated` — VM with `banner_resolve_link='/reconcile/discrepancy/99/resolve'` + count=2; assert rendered HTML contains `<a href="/reconcile/discrepancy/99/resolve" data-banner-resolve-link="true">`.
- `test_banner_template_renders_plain_text_when_banner_resolve_link_none` — VM with `banner_resolve_link=None` + count=2; assert NO `<a href=` in the banner block + the count text is intact.
- `test_banner_template_suppresses_banner_when_count_zero` — VM with count=0 + banner_resolve_link=None; assert NO `data-banner=` substring (banner suppressed entirely).
- `test_banner_template_suppresses_banner_when_count_zero_and_link_populated` — VM with count=0 + banner_resolve_link='/...' (anomalous state — should never happen in production, defense-in-depth); assert NO banner rendered (count predicate dominates).
- `test_retrofit_completeness_audit_via_pass_a_grep` — Pass A grep + introspection assert; runs at test time; pins F11.
- `test_banner_new_text_ascii_only` — strip the pre-existing `⚠` glyph from the rendered HTML; assert remaining codepoints all `< 128`.
- `test_banner_link_target_route_registered_on_app_routes` — assert any `/reconcile/discrepancy/{discrepancy_id}/resolve` GET route exists on `app.routes` (defense-in-depth; Phase 6 I3 LOCK).
- `test_banner_link_text_singular_when_count_eq_1` — VM with count=1 + link populated; assert text `"1 unresolved material reconciliation discrepancy."` (singular "discrepancy") + the entire string wrapped in `<a>`.

**Commit message stem:** `feat(web): wire banner_resolve_link into base.html.j2 + add retrofit completeness audit (Phase 12.5 #2 T-2.8)`

**Dependencies:** T-2.7.

---

### Task T-2.9 — Banner first-pending helper + builder/route population sites (Pass B retrofit)

**Files:**
- Modify: `swing/metrics/discrepancies.py` — add `list_pending_ambiguities_in_banner_set(conn) -> list[ReconciliationDiscrepancy]` + `fetch_first_pending_ambiguity_resolve_link_path(conn) -> str | None`.
- Modify: Pass B grep targets — every site that calls `count_unresolved_material(conn)` gains an adjacent call to `fetch_first_pending_ambiguity_resolve_link_path(conn)` + threads the result into the VM constructor's `banner_resolve_link=` kwarg (or per-callsite db_path-shape helper where the existing pattern uses one — see §G.1 narrative for the per-callsite call-shape decision matrix).
- Test: `tests/metrics/test_discrepancies_first_pending_ambiguity.py` (NEW).
- Test: `tests/web/test_banner_resolve_link_population_per_route.py` (NEW).

**Acceptance:**

- New `list_pending_ambiguities_in_banner_set(conn) -> list[ReconciliationDiscrepancy]`:
  - Unions `list_unresolved_material_for_active_trades(conn) + list_unresolved_material_for_closed_trades(conn)` (mirror of `count_unresolved_material` per R1 LOCK — same trade-set used by the banner count).
  - Filters to `resolution == 'pending_ambiguity_resolution'` (the existing helpers already filter `resolution IN ('unresolved', 'pending_ambiguity_resolution')` per `swing/data/repos/reconciliation.py:475+503`).
  - Sorts oldest-first via `sorted(..., key=lambda d: d.discrepancy_id)` (§1.2 #6 LOCK: `discrepancy_id ASC`).
  - Returns the full list. Caller may take `[0]` for the first-pending or iterate for the V2 `/reconcile/pending` list page.
- New `fetch_first_pending_ambiguity_resolve_link_path(conn) -> str | None`:
  - Calls `list_pending_ambiguities_in_banner_set(conn)`. Returns None when empty; else returns `f"/reconcile/discrepancy/{result[0].discrepancy_id}/resolve"`.
- Pass B retrofit per spec §3 "Builder/route population sites":
  - At every site that currently calls `count_unresolved_material(conn)`, add an adjacent call to `fetch_first_pending_ambiguity_resolve_link_path(conn)` AND thread the result into the VM constructor's `banner_resolve_link=` kwarg.
  - For sites using the db_path-shape helper pattern (e.g., `swing/web/routes/schwab.py:_fetch_unresolved_material_count`), add a SIBLING helper `_fetch_banner_resolve_link(db_path) -> str | None` that opens a short-lived `sqlite3.connect` + invokes `fetch_first_pending_ambiguity_resolve_link_path`. Sibling helpers MUST mirror the existing pattern's name + docstring shape (per Phase 12.5 #1 T-1.8 retrofit precedent at `_fetch_recent_multi_leg_auto_correction_count`).
  - **CRITICAL**: per spec §3 R3 LOCK the implementer audits via `rg 'count_unresolved_material\(' swing/web/ swing/cli.py` at task start; the enumeration in §C.1 is the BASELINE but plan §A T-2.9 acceptance is "every match site retrofitted" (NOT "the listed N sites only"). New call sites landing between plan-drafting and executing-plans implementation are caught by this acceptance contract.
- The `_render_pre_resolution_context` (T-2.2) + `build_reconcile_discrepancy_resolve_vm` (T-2.3) build paths ALSO consume `fetch_first_pending_ambiguity_resolve_link_path` so the resolve-form page itself shows a banner link (which MAY point at the same discrepancy the operator is currently viewing — informational, not load-bearing).

**Tests added (~6):**

- `test_list_pending_ambiguities_in_banner_set_returns_oldest_first` — seed 3 discrepancies (A id=10, B id=5, C id=20) all in pending_ambiguity_resolution + material + attributed to active trades; assert helper returns `[B, A, C]` (id ASC).
- `test_list_pending_ambiguities_in_banner_set_excludes_orphan_trade_id_null` — seed pending_ambiguity_resolution + material with `trade_id=NULL`; assert excluded (mirrors banner count semantics).
- `test_list_pending_ambiguities_in_banner_set_excludes_immaterial` — seed pending_ambiguity_resolution + `material_to_review=0`; assert excluded.
- `test_list_pending_ambiguities_in_banner_set_excludes_unresolved_resolution` — seed `resolution='unresolved'` + material; assert excluded (the broader banner-count helper includes 'unresolved' for non-ambiguity banner; THIS helper is narrower).
- `test_fetch_first_pending_ambiguity_resolve_link_path_returns_none_when_empty` — DB with zero pending discrepancies → returns None.
- `test_fetch_first_pending_ambiguity_resolve_link_path_returns_oldest_url` — DB with 2 pending (id=5, id=10) → returns `/reconcile/discrepancy/5/resolve`.

**Commit message stem:** `feat(metrics): add banner first-pending-ambiguity helper + thread banner_resolve_link across base-layout routes (Phase 12.5 #2 T-2.9)`

**Dependencies:** T-2.7 (field declarations must exist before population).

---

### Task T-2.10 — Error path template EXPANSION (anchor_mismatch / service_error / db_unavailable branches)

**Files:**
- Modify: `swing/web/templates/reconcile_discrepancy_resolve_error.html.j2` — T-2.5 landed the stub with 2 branches (`not_found` + `already_resolved`); T-2.10 EXPANDS to the full 5-branch shape per spec §8.1.
- Modify: `swing/web/view_models/reconcile.py` — `ReconcileDiscrepancyErrorVM` already defined at T-2.5; T-2.10 only widens the template's branch coverage (no new dataclass; no signature change).
- Modify: `swing/web/routes/reconcile.py` — T-2.6 lands the route-side wiring for the 3 new branches; T-2.10 verifies template-side coverage. (T-2.6 already lands the route-side calls to `_render_error(error_kind='anchor_mismatch'|'service_error'|'db_unavailable', ...)` per its acceptance criterion #6; T-2.10's scope is template-branch addition.)
- Test: `tests/web/test_reconcile_resolve_error_paths.py` (NEW).

**Acceptance:**

- `ReconcileDiscrepancyErrorVM` is a `@dataclass(frozen=True)` with the 8 BaseLayoutVM-shaped fields + `error_kind: Literal['not_found', 'already_resolved', 'anchor_mismatch', 'service_error', 'db_unavailable']` + `error_message: str` + `discrepancy_id: int | None` + `disc_resolution: str | None` (for `already_resolved` template branch) + `disc_resolved_by: str | None` + `disc_created_at: str | None`.
- Template skeleton (single file, branches on `vm.error_kind`):
  - `not_found` branch: H1 "Discrepancy not found", paragraph explaining the path's `{discrepancy_id}` did not match any row, link back to `/dashboard`, CLI-parity hint `swing journal discrepancy show {{ vm.discrepancy_id }}`.
  - `already_resolved` branch: H1 "Discrepancy already resolved", echo `resolution` + `resolved_by` + `created_at`, link back to `/dashboard`, CLI hint.
  - `anchor_mismatch` branch: H1 "Form state changed", explain mid-flight reclassification, link back to `/reconcile/discrepancy/{{ vm.discrepancy_id }}/resolve` to re-open.
  - `service_error` branch: H1 "Unexpected error", redacted error message, link back to `/dashboard`, CLI hint to investigate via `swing journal discrepancy show {{ vm.discrepancy_id }}`.
  - `db_unavailable` branch: H1 "Database temporarily unavailable", link back to `/dashboard` + retry hint.
- All error template text is ASCII-only (F12).
- `error_kind` is rendered as a `data-error-kind="{{ vm.error_kind }}"` attribute on the outer `<section>` for test-discriminator stability.

**Tests added (~6):**

- `test_error_template_not_found_branch` — VM with `error_kind='not_found'` + `discrepancy_id=9999`; assert `data-error-kind="not_found"` + `9999` substring + link to `/dashboard`.
- `test_error_template_already_resolved_branch` — VM with `error_kind='already_resolved'` + `disc_resolution='operator_resolved_ambiguity'`; assert resolution string echoed + CLI hint substring.
- `test_error_template_anchor_mismatch_branch` — VM with `error_kind='anchor_mismatch'`; assert link to re-open form.
- `test_error_template_service_error_branch` — VM with `error_kind='service_error'` + `error_message='ValueError: terminal state'`; assert message echoed.
- `test_error_template_db_unavailable_branch` — VM with `error_kind='db_unavailable'`; assert retry hint substring.
- `test_error_template_ascii_only_codepoints` — iterate rendered HTML; assert `max(ord(c) for c in body) < 128` (F12; minus pre-existing base-layout glyphs per T-2.8 carve-out).

**Commit message stem:** `feat(web): add reconcile_discrepancy_resolve_error.html.j2 + ReconcileDiscrepancyErrorVM (Phase 12.5 #2 T-2.10)`

**Dependencies:** T-2.5 + T-2.6 (route handlers consume the new VM + template).

---

### Task T-2.11 — Slow E2E + integration tests + sentinel/XSS audits + cycle-checklist + return report

**Files:**
- Create: `tests/integration/test_phase12_5_bundle_2_web_tier2_happy_path.py` (NEW; SLOW-MARKED).
- Create: `tests/integration/test_phase12_5_bundle_2_cli_web_parity.py` (NEW).
- Create: `tests/web/test_reconcile_resolve_xss_and_sentinel_audit.py` (NEW).
- Modify: `docs/cycle-checklist.md` — add a "Resolve a Tier-2 ambiguity via web" line under the daily-review section + a reference to the operator-witnessed gate plan.
- Modify: `CLAUDE.md` — extend the existing HTMX gotcha family with a one-line entry citing Phase 12.5 #2 T-2.6 hidden-anchor + `'operator_web'` server-stamping precedent (where appropriate; defer to Phase 12.5 #3 maintenance pass if `CLAUDE.md` becomes a merge-conflict surface).

**Acceptance:**

- Slow E2E `test_phase12_5_bundle_2_web_tier2_happy_path`:
  - Marks `@pytest.mark.slow`.
  - Seeds full DB state (trade → fill → reconciliation_run → reconciliation_discrepancies row in pending_ambiguity_resolution).
  - Uses `with TestClient(app) as client:` (Phase 5+ lifespan discipline).
  - Step 1: `client.get("/dashboard")` → 200, body contains the banner with `data-banner-resolve-link="true"` and the URL pointing at the seeded discrepancy.
  - Step 2: `client.get(f"/reconcile/discrepancy/{disc_id}/resolve", headers={"HX-Request": "true"})` → 200, body contains the pre-resolution context + the choice menu + the hidden anchor.
  - Step 3: `client.post(f"/reconcile/discrepancy/{disc_id}/resolve", data={"choice_code": "keep_journal_as_is", "resolution_reason": "operator-acked", "ambiguity_kind_at_render": "multi_partial_vs_consolidated"}, headers={"HX-Request": "true"})` → 204 + `HX-Redirect` header.
  - Step 4: Query DB; assert `reconciliation_corrections` row with `applied_by='operator'` + `correction_action='operator_resolved_ambiguity'` + the operator-typed `correction_reason`.
  - Step 5: Assert `reconciliation_discrepancies.resolved_by='operator_web'`.
  - Step 6: `client.get("/dashboard")` → banner cleared (count drops by 1; for last pending, banner suppressed entirely).
- CLI/web parity test `test_phase12_5_bundle_2_cli_web_parity`:
  - Seeds 2 structurally-identical pending-ambiguity discrepancies (same `ambiguity_kind='multi_partial_vs_consolidated'`, same `expected_value_json`, same `actual_value_json`, same `field_name`, same `discrepancy_type`).
  - Resolves disc #1 via `CliRunner` invoking `swing journal discrepancy resolve-ambiguity` with `--choice keep_journal_as_is --reason 'cli-acked'`.
  - Resolves disc #2 via `TestClient` POST with the equivalent form payload.
  - Builds the semantic-shape projection per spec §13.3 R2 LOCK on each `reconciliation_corrections` row: includes `{correction_action, correction_choice, affected_table, field_name, pre_correction_value_json, source_canonical_value_json, applied_value_json, operator_truth_value_json, applied_by, correction_reason, notes, risk_policy_id_at_correction}`; excludes `{correction_id, discrepancy_id, affected_row_id, applied_at, correction_set_id, reconciliation_run_id, schwab_api_call_id, superseded_by_correction_id}`. The two operator-typed `correction_reason` strings differ by construction, so the projection comparison MUST normalize them (substitute both `correction_reason` slots to a sentinel before equality) OR the test asserts the projections are equal IGNORING `correction_reason`.
  - Asserts projection equality; asserts `reconciliation_discrepancies.resolved_by` differs (`'operator'` for CLI vs `'operator_web'` for web).
- XSS + sentinel-leak audit `test_reconcile_resolve_xss_and_sentinel_audit`:
  - **XSS-escape assertion**: plant `'<script>alert(1)</script>'` in `disc.resolution_reason` AND submit it as `custom_value`. Render the form page (both happy path + 400 re-render path). Assert rendered HTML contains `&lt;script&gt;alert(1)&lt;/script&gt;` (literal escaped substring) AND ZERO `<script>` raw substring in the response body.
  - **Forbidden-sentinel absence assertion**: plant `'COPOWERS-FORBIDDEN-RECONCILE-SENTINEL-XYZ'` in NO surface (i.e., never inject it). Render a discrepancy form + submit a no-op resolution. Assert the sentinel does NOT appear in (a) the form-render response body, (b) the POST response body, (c) the new `reconciliation_corrections.correction_reason` column, (d) the `reconciliation_discrepancies.resolution_reason` column, (e) the `reconciliation_discrepancies.resolved_by` column. Defense-in-depth.
- Cycle-checklist additions:
  - Under the "Resolve unresolved-material discrepancies" section, add a new bullet: "Web alternative: click the dashboard banner link to open the resolve form for the oldest pending-ambiguity row; pick a choice from the menu; type a reason; submit. CLI `swing journal discrepancy resolve-ambiguity` remains available for power-user / scripted flows." ASCII-only.

**Tests added (~5 + 1 slow):**

- (slow) `test_phase12_5_bundle_2_web_tier2_happy_path` — full E2E.
- `test_cli_web_audit_row_semantic_shape_parity` — CLI/web semantic projection equality.
- `test_cli_web_resolved_by_distinguishability` — `'operator'` vs `'operator_web'`.
- `test_resolve_form_xss_escape_via_resolution_reason` — XSS escape regression pin.
- `test_resolve_form_no_forbidden_sentinel_emit` — sentinel absence regression pin.
- `test_resolve_form_xss_escape_via_custom_value_rerender` — XSS escape on the 400 re-render path with `prior_custom_value_raw`.

**Commit message stem:** `test(web): slow E2E + CLI/web parity + XSS/sentinel audit + cycle-checklist (Phase 12.5 #2 T-2.11)`

**Dependencies:** T-2.5 + T-2.6 + T-2.7 + T-2.8 + T-2.9 + T-2.10 (all preceding tasks).

---

## §B Pre-conditions + worktree state

**Branch:** `phase12-5-bundle-2-web-tier2-executing-plans` (NEW; worktree branched from `main` at executing-plans dispatch time; matches cleanup-script regex `phase\d+[-_]`). Each task creates a single commit; orchestrator integrates via `git merge --no-ff` per Phase 12 / Phase 12.5 #1 precedent.

**Baseline (verified at this plan's drafting against worktree HEAD `b4d08a6`):**
- 4712 fast tests pass under `pytest -m "not slow" -n auto`.
- 3 pre-existing phase8 walkthrough failures unchanged.
- 5 skipped tests unchanged.
- 1 slow E2E `test_phase12_5_bundle_1_oqf_multi_leg_auto_redirect_happy_path` PASS.
- Ruff: 18 E501 issues; Phase 12.5 #3 will clear this.
- Schema v19.

**Expected post-ship baseline (per §K projection):**
- ~4793 fast tests pass (4712 + ~81 new).
- 3 pre-existing phase8 failures unchanged.
- 5 skipped + 0 NEW skips (no `@pytest.mark.skip` planned for any T-2.X test).
- 2 slow E2E tests PASS (T-2.11 adds one).
- Ruff 18 unchanged.
- Schema v19 unchanged.

**Worktree setup (executing-plans implementer):**

```powershell
git fetch origin main
git worktree add -b phase12-5-bundle-2-web-tier2-executing-plans .worktrees/phase12-5-bundle-2-web-tier2-executing-plans origin/main
cd .worktrees/phase12-5-bundle-2-web-tier2-executing-plans
New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active
```

---

## §C Files touched (canonical roster)

### §C.1 Production code (touched by tasks; grep anchors verified at plan-drafting time)

| File | Lines | Tasks | Touched-by-task description |
|---|---|---|---|
| `swing/web/view_models/reconcile.py` | NEW (~360 LOC projected) | T-2.1, T-2.2, T-2.3, T-2.10 | NEW module. Holds `_parse_parametric_pick_count`, 3 frozen dataclasses (VM + sub-VMs), 11 per-type render helpers + generic fallback, `build_reconcile_discrepancy_resolve_vm`, `ReconcileDiscrepancyErrorVM`. |
| `swing/web/routes/reconcile.py` | NEW (~280 LOC projected) | T-2.5, T-2.6, T-2.10 | NEW module. Holds GET + POST handlers + per-callsite db_path-shape helpers + error-path renderers. |
| `swing/web/app.py` | MODIFY +2 LOC | T-2.5 | `from swing.web.routes.reconcile import router as reconcile_router` + `app.include_router(reconcile_router)` after the existing schwab router include. |
| `swing/web/templates/reconcile_discrepancy_resolve.html.j2` | NEW (~150 LOC) | T-2.4 | Pre-resolution context section + form + 12-line inline `<script>`. |
| `swing/web/templates/reconcile_discrepancy_resolve_error.html.j2` | NEW (~80 LOC) | T-2.10 | 5-branch error template. |
| `swing/web/templates/base.html.j2` | MODIFY ~10 LOC | T-2.8 | Wrap banner count text in `<a href>` link when `vm.banner_resolve_link` truthy. |
| `swing/web/view_models/metrics/shared.py:BaseLayoutVM` | MODIFY +1 field +1 validation | T-2.7 | `banner_resolve_link: str | None = None`. |
| `swing/web/view_models/dashboard.py` | MODIFY +1 field (line 354 anchor) | T-2.7 | DashboardVM standalone-field retrofit. |
| `swing/web/view_models/pipeline.py` | MODIFY +1 field (line 26 anchor) | T-2.7 | PipelineVM standalone-field retrofit. |
| `swing/web/view_models/journal.py` | MODIFY +1 field (line 112 anchor) | T-2.7 | JournalVM standalone-field retrofit. |
| `swing/web/view_models/watchlist.py` | MODIFY +1 field (line 45 anchor) | T-2.7 | WatchlistVM standalone-field retrofit. |
| `swing/web/view_models/config.py` | MODIFY +1 field (line 51 anchor) | T-2.7 | ConfigPageVM standalone-field retrofit. |
| `swing/web/view_models/error.py` | MODIFY +1 field (line 25 anchor) | T-2.7 | PageErrorVM standalone-field retrofit. |
| `swing/web/view_models/trades.py` | MODIFY +1 field × 4 (lines 663, 765, 781, 935 anchors) | T-2.7 | 4 trades-VM standalone-field retrofits. |
| `swing/web/view_models/schwab.py` | MODIFY +1 field × 3 (lines 78, 230, 559 anchors) | T-2.7 | SchwabSetupVM + SchwabSetupErrorVM + SchwabStatusVM standalone-field retrofits. |
| `swing/metrics/discrepancies.py` | MODIFY +2 functions (~35 LOC) | T-2.9 | Add `list_pending_ambiguities_in_banner_set` + `fetch_first_pending_ambiguity_resolve_link_path`. |
| `swing/web/routes/account.py` | MODIFY +2-3 LOC × 2 callsites (line 87 + 114) | T-2.9 | Thread `banner_resolve_link` into VM constructors. |
| `swing/web/routes/schwab.py` | MODIFY +1 sibling helper + +3 LOC × N callsites | T-2.9 | New `_fetch_banner_resolve_link(db_path)` helper + thread into VM constructors. |
| `swing/web/view_models/metrics/*.py` (8 metrics-module files) | MODIFY +2-3 LOC each | T-2.9 | Thread `banner_resolve_link` into per-metrics-page VM constructors. |
| `swing/web/view_models/dashboard.py` (line 909 builder anchor) | MODIFY +2-3 LOC | T-2.9 | Thread into DashboardVM constructor in the build function. |
| `swing/web/view_models/journal.py` (line 136 builder anchor) | MODIFY +2-3 LOC | T-2.9 | Thread into JournalVM constructor. |
| `swing/web/view_models/pipeline.py` (line 42 builder anchor) | MODIFY +2-3 LOC | T-2.9 | Thread into PipelineVM constructor. |
| `swing/web/view_models/watchlist.py` (line 130 builder anchor) | MODIFY +2-3 LOC | T-2.9 | Thread into WatchlistVM constructor. |
| `swing/web/view_models/config.py` (line 130 builder anchor) | MODIFY +2-3 LOC | T-2.9 | Thread into ConfigPageVM constructor. |
| `swing/web/view_models/trades.py` (4 builder anchors at lines 703, 799, 848, 1042) | MODIFY +2-3 LOC × 4 | T-2.9 | Thread into 4 trades-VM constructors. |
| `docs/cycle-checklist.md` | MODIFY +5-10 LOC | T-2.11 | Add "Resolve a Tier-2 ambiguity via web" bullet. |

### §C.2 New test files

- `tests/web/test_reconcile_parametric_pick_count.py` — T-2.1 (~5 tests)
- `tests/web/test_reconcile_resolve_vm.py` — T-2.2 (~12 tests)
- `tests/web/test_reconcile_resolve_vm_builder.py` — T-2.3 (~8 tests)
- `tests/web/test_reconcile_resolve_template.py` — T-2.4 (~6 tests)
- `tests/web/test_reconcile_resolve_get_route.py` — T-2.5 (~7 tests)
- `tests/web/test_reconcile_resolve_post_route.py` — T-2.6 (~8 tests)
- `tests/web/test_base_layout_vm_banner_resolve_link.py` — T-2.7 (~10 tests)
- `tests/web/test_base_layout_banner_resolve_link.py` — T-2.8 (~8 tests)
- `tests/metrics/test_discrepancies_first_pending_ambiguity.py` — T-2.9 (~6 tests)
- `tests/web/test_banner_resolve_link_population_per_route.py` — T-2.9 (route population regression)
- `tests/web/test_reconcile_resolve_error_paths.py` — T-2.10 (~6 tests)
- `tests/integration/test_phase12_5_bundle_2_web_tier2_happy_path.py` — T-2.11 (1 slow)
- `tests/integration/test_phase12_5_bundle_2_cli_web_parity.py` — T-2.11 (~2 tests)
- `tests/web/test_reconcile_resolve_xss_and_sentinel_audit.py` — T-2.11 (~3 tests)

### §C.3 Surfaces explicitly NOT touched (UNCHANGED LOCK per spec §3 + brief §5)

- `swing/trades/reconciliation_auto_correct.py` — service-layer UNCHANGED; web POST consumes the existing `apply_tier2_resolution` signature including the `resolved_by_override` kwarg shipped at Phase 12.5 #1 T-1.4.
- `swing/trades/reconciliation_ambiguity_choices.py` — `get_choice_menu` + `ChoiceMenuItem` UNCHANGED.
- `swing/trades/reconciliation_classifier.py` — UNCHANGED.
- `swing/trades/reconciliation_backfill.py` — UNCHANGED.
- `swing/cli.py` — `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` UNCHANGED (operator-LOCK §1.1 #3 / spec §2.3).
- `swing/cli.py:2291` parametric-pick regex UNCHANGED (operator-LOCK §1.2 #11 — web duplicates).
- `swing/data/migrations/*.sql` — schema v19 UNCHANGED (operator-LOCK §1.1 + spec §14; F1 LOCK).
- `swing/data/repos/reconciliation.py` — UNCHANGED (consumer-only).
- `swing/data/models.py:ReconciliationDiscrepancy` — UNCHANGED.

### §C.4 Pass A grep anchor (verified 2026-05-18 at HEAD `b4d08a6`)

```
$ rg 'unresolved_material_discrepancies_count\s*:\s*int\s*=' swing/web/view_models/ -n
swing/web/view_models/metrics/shared.py:47   # BaseLayoutVM (inheriting)
swing/web/view_models/watchlist.py:44        # WatchlistVM
swing/web/view_models/config.py:50           # ConfigPageVM
swing/web/view_models/trades.py:662          # TradesPageVM
swing/web/view_models/trades.py:764          # TradeEntryFormVM
swing/web/view_models/trades.py:780          # TradeEntryReviewVM
swing/web/view_models/trades.py:934          # TradeDetailVM
swing/web/view_models/journal.py:111         # JournalVM
swing/web/view_models/dashboard.py:353       # DashboardVM
swing/web/view_models/error.py:24            # PageErrorVM
swing/web/view_models/pipeline.py:25         # PipelineVM
swing/web/view_models/schwab.py:77           # SchwabSetupVM
swing/web/view_models/schwab.py:229          # SchwabSetupErrorVM
swing/web/view_models/schwab.py:558          # SchwabStatusVM
```

Total: 14 declaration sites. 1 (BaseLayoutVM at `metrics/shared.py:47`) is the inheriting parent; the OTHER 13 are STANDALONE-field VMs. T-2.7 retrofit count = **13**.

### §C.5 Pass B grep anchor (verified 2026-05-18 at HEAD `b4d08a6`)

```
$ rg 'count_unresolved_material\(' swing/web/ swing/cli.py
swing/web/view_models/dashboard.py:909
swing/web/view_models/config.py:130
swing/web/view_models/journal.py:136
swing/web/view_models/pipeline.py:42
swing/web/view_models/trades.py:703
swing/web/view_models/trades.py:799
swing/web/view_models/trades.py:848
swing/web/view_models/trades.py:1042
swing/web/view_models/watchlist.py:130
swing/web/view_models/metrics/capital_friction.py:93
swing/web/view_models/metrics/hypothesis_progress_card.py:413
swing/web/view_models/metrics/deviation_outcome.py:87
swing/web/view_models/metrics/index.py:97
swing/web/view_models/metrics/identification_funnel.py:71
swing/web/routes/account.py:87
swing/web/routes/account.py:114
swing/web/view_models/metrics/trade_process_card.py:138
swing/web/view_models/metrics/process_grade_trend.py:458
swing/web/view_models/metrics/tier_comparison.py:89
swing/web/view_models/metrics/maturity_stage.py:67
swing/web/routes/schwab.py:92
```

Total: 21 call sites. T-2.9 retrofit count = **21**. The schwab.py call site at line 92 is inside the `_fetch_unresolved_material_count(db_path)` sibling helper — the new `_fetch_banner_resolve_link(db_path)` helper lands adjacent + per-route call adds a `banner_resolve_link` kwarg pair.

---

## §D Locked decisions roll-up (12 binding clauses, verbatim attribution)

### §D.1 Operator-locks from spec §2 (4 binding clauses; baked verbatim by brainstorm)

1. **Dedicated form page** at `GET /reconcile/discrepancy/{id}/resolve` + `POST /reconcile/discrepancy/{id}/resolve` (spec §2.1). NOT inline HTMX swap; NOT 2-step list-page. Plan §A T-2.5 + T-2.6 inherit.
2. **HX-Redirect to `/dashboard?reconcile_resolved={correction_id}`** on successful POST (spec §2.2). 204 + HX-Redirect header per Phase 5 R1 M2 LOCK. Plan §A T-2.6 step 7 inherits.
3. **CLI preservation AS-IS** (spec §2.3). `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` UNCHANGED. Plan §C.3 inherits.
4. **Pre-resolution context section** ABOVE choice menu (spec §2.4). Plan §A T-2.2 + T-2.4 inherit.

### §D.2 Operator-locks from spec §16 (8 binding clauses; all ACCEPTED at brainstorm defaults per operator-orchestrator scope conversation 2026-05-18 post-merge)

5. **Banner navigation target** = link to FIRST pending-ambiguity discrepancy resolve form when one exists; count-text-only when count > 0 but ZERO pending-ambiguity rows exist (spec §10.1). Plan §A T-2.8 + T-2.9 inherit.
6. **First-pending selector ORDER BY** = `discrepancy_id ASC` (oldest first). Diverges from CLI `list-pending-ambiguities` DESC. Plan §A T-2.9 inherits.
7. **Dashboard per-discrepancy list** = NOT in V1 (V2-banked §15.5). Plan §A omits.
8. **HX-Redirect query-string token** = include `?reconcile_resolved={correction_id}`; dashboard does NOT consume V1. Plan §A T-2.6 inherits.
9. **HX-Redirect alternate target** = uniform `/dashboard` (V2 candidate §15.9 for per-type targets). Plan §A T-2.6 inherits.
10. **JS posture for custom-value toggle** = 12-line inline `<script>` in the template; custom-value fieldset always rendered; JS is UX nicety only. Plan §A T-2.4 inherits.
11. **`_parse_parametric_pick_count` helper location** = NEW private module-level function in `swing/web/view_models/reconcile.py` that DUPLICATES the regex byte-for-byte from `cli.py:2291`. CLI surface UNCHANGED. Plan §A T-2.1 inherits.
12. **Operator-witnessed gate surface count** = 6 surfaces. Plan §H enumerates.

### §D.3 Brainstorm-locks from spec §15.A (Codex chain resolved; verbatim consumed)

- Surface attribution via existing free-TEXT `reconciliation_discrepancies.resolved_by` column with NEW value `'operator_web'` (spec §9.1 + §14). Schema v19 UNCHANGED. F1 + F2 LOCKs.
- BaseLayoutVM-inheritance asymmetry: 13 existing VMs DO NOT inherit `BaseLayoutVM`; carry standalone fields (spec §3 R3 LOCK). Plan §A T-2.7 + T-2.8 + §C.4 inherit.
- Hidden state anchor for TOCTOU defense: `ambiguity_kind_at_render` hidden form input (spec §4.2 step 2 + §6 + §8.2). Plan §A T-2.4 + T-2.6 inherit. F8 LOCK.
- Pass A grep at test time = discriminating retrofit completeness audit (spec §3 + §13.3 R5 LOCK). Plan §A T-2.8 inherits. F11 LOCK.

---

## §E Test patterns + discriminating-test naming convention

### §E.1 Naming convention

- Unit tests use `test_<subject>_<behavior>` (snake_case; subject = function or VM-class; behavior = the discriminating condition under test).
- Discriminating regression tests for project invariants use `test_<F#>_<short_name>` (e.g., `test_F11_pass_a_grep_audit_every_vm_has_banner_resolve_link`).
- End-to-end happy-path tests use `test_phase12_5_bundle_2_<scenario>_happy_path` (matches Phase 12.5 #1 + Phase 12 Sub-bundle C precedents).
- CLI/web parity tests use `test_cli_web_<parity_dimension>_parity`.

### §E.2 Discriminating-test discipline (lifted from Sub-bundle C plan + Phase 10 lessons inherited from Phase 12.5 #1 plan §E.2)

- **No source-text comparison; behavioral parity instead.** T-2.1's CLI/web parametric-parser parity test compares the parsed N (behavior), NOT the regex source string (source-equality would pass trivially as long as both sides happen to import the same string literal even after a divergent refactor).
- **No body-wide substring assertion when the seed text contains the same substring.** Phase 10 Sub-bundle C lesson #20. Use exact rendered numeric+unit substring (`"5.30"` not `"5"`) per worked example.
- **Round-trip integration tests for session-anchor read/write predicates.** Not applicable here (no session-anchored writes), but the form-anchor-vs-current-state TOCTOU pattern is the same family — T-2.6's `test_post_returns_409_on_hidden_anchor_mismatch` IS the round-trip test.
- **Audit-row parity uses semantic-shape projection, NOT byte-identical comparison.** T-2.11's CLI/web parity test follows spec §13.3 R2 LOCK.
- **Retrofit completeness as discriminating test.** T-2.8 runs Pass A grep at test time + asserts every matching VM has the new field. F11 LOCK.
- **Pass-A-grep-driven retrofit OR introspection.** F11.

---

## §F Invariants (non-negotiable contracts spanning multiple tasks)

These are LOCK invariants that survive across T-2.1 through T-2.11. Codex review MUST validate every task respects all of them.

| # | Invariant | Source | Discriminating regression test pattern |
|---|---|---|---|
| F1 | **ZERO new schema.** Schema v19 unchanged; no `0020_*.sql`; no CHECK enum widening; no Python constant; no dataclass validator on `resolved_by`. | Spec §14 + operator-LOCK §1.1 #3 + plan-author schema escalation rule | `grep -rn "0020" swing/data/migrations/` returns 0 matches; `grep -rn "_RESOLVED_BY_VALUES" swing/` returns 0 matches. |
| F2 | **Surface attribution via `resolved_by_override='operator_web'`.** Web stamps `'operator_web'`; CLI default unchanged at `'operator'`. NO `applied_by` widening. | Spec §9.1 + operator-LOCK §1.1 #3 | T-2.6 includes `test_post_flips_discrepancy_resolved_by_to_operator_web` + `test_post_writes_reconciliation_corrections_row_with_applied_by_operator`. |
| F3 | **ZERO change to existing `apply_tier2_resolution` legacy default behavior.** All pre-existing call sites (CLI; Phase 12.5 #1 auto-redirect) work identically; web is a NEW caller that opts into `resolved_by_override='operator_web'`. | Spec §3 + Phase 12.5 #1 F3 carry-forward | T-2.11 CLI/web parity test asserts CLI path produces `resolved_by='operator'` unchanged. |
| F4 | **HX-Request propagation on embedded form.** `hx-headers='{"HX-Request": "true"}'` on the resolve form (Phase 5 R1 M1 LOCK). | CLAUDE.md HTMX trinity | T-2.4 `test_resolve_template_renders_hx_headers_attribute_verbatim`. |
| F5 | **HX-Redirect on success (204 + header), NOT 303 swap-target.** Phase 5 R1 M2 LOCK. | CLAUDE.md HTMX trinity | T-2.6 `test_post_happy_path_returns_204_with_hx_redirect_to_dashboard`. |
| F6 | **`... or None` for nullable text columns.** Empty form input → None (not `""`) for fields that may flow into a nullable CHECK-constrained column. | Phase 6 I3 + CLAUDE.md gotcha | T-2.6 `test_post_handles_empty_custom_value_as_none` (parametrized over no-payload choices). |
| F7 | **No `with conn:` wrapper at the route; service-layer owns BEGIN IMMEDIATE / COMMIT / ROLLBACK.** | Phase 8 R3-R4 + CLAUDE.md `Service-layer with conn:` gotcha | T-2.6 includes `test_post_does_not_open_transaction_at_route_layer` (mocks `conn.execute` + asserts NO `BEGIN` call from the handler). |
| F8 | **`ambiguity_kind_at_render` hidden form anchor + POST-time validation against current state.** Mismatch → 409; missing → 400. | Phase 9 D R2 M#1 LOCK + spec §4.2 step 2 / step 3c | T-2.4 `test_resolve_template_renders_ambiguity_kind_at_render_hidden_input` + T-2.6 `test_post_returns_409_on_hidden_anchor_mismatch` + `test_post_returns_400_on_missing_hidden_anchor`. |
| F9 | **Custom-value fieldset ALWAYS rendered (JS-disabled fallback).** Server enforces `requires_custom_value` contract; JS is UX nicety. | Operator-LOCK §1.2 #10 + spec §6 | T-2.4 `test_resolve_template_renders_custom_value_textarea_always`. |
| F10 | **Parametric picks ALWAYS require `custom_value_raw`** (mirrors CLI `cli.py:2538`). | Spec §4.2 step 3e + spec §6.2.1 LOCK | T-2.6 `test_post_returns_400_when_parametric_pick_missing_custom_value`. |
| F11 | **Pass A grep retrofit completeness audit.** Every VM with `unresolved_material_discrepancies_count` field also has `banner_resolve_link` field with default None. Discriminating test runs Pass A grep at test time (NOT hard-coded class list). | Spec §3 R3 + Codex R5 M#1 LOCK + Phase 10 T-A.7 precedent | T-2.8 `test_retrofit_completeness_audit_via_pass_a_grep`. |
| F12 | **Template text NEW additions are ASCII-only.** Windows cp1252 gotcha. Pre-existing `⚠` in the base layout is carve-out (preserved by no-regression posture); NEW text MUST be ASCII. | CLAUDE.md cp1252 gotcha + Phase 12 C.D gate-fix #1+#3 | T-2.4 `test_resolve_template_ascii_only_codepoints` + T-2.8 `test_banner_new_text_ascii_only` + T-2.10 `test_error_template_ascii_only_codepoints`. |
| F13 | **DB connection closure guaranteed via `try/finally`.** All early-return branches (404 / 409) close `conn` before returning. | Spec §4.1 + Codex R3 M#3 LOCK | T-2.5 `test_get_closes_db_connection_on_404_path` + T-2.6 `test_post_closes_db_connection_on_error_path`. |
| F14 | **`apply_overrides(cfg)` at every web route entry.** Phase 12 Sub-bundle B Codex R1 Critical #1 inheritance — required at every Schwab + reconcile + cfg-consuming entry. | Phase 12 Sub-bundle B `e418d56` precedent | T-2.5 `test_get_calls_apply_overrides` + T-2.6 `test_post_calls_apply_overrides`. |
| F15 | **HX-Redirect target route registered on `app.routes`.** Defense-in-depth per Phase 6 I3 LOCK. | CLAUDE.md HTMX trinity #3 | T-2.6 `test_dashboard_route_registered_on_app_routes` (assert `/dashboard` GET handler exists). |
| F16 | **Sandbox short-circuit applies ONLY to auto-redirect; manual tier-2 paths PROCEED under sandbox.** Web V1 inherits this verbatim (web never triggers auto-redirect triple). | Spec §11.8 + Phase 12 C.C sandbox-in-inner LOCK | T-2.6 `test_post_happy_path_under_sandbox_environment_proceeds_to_journal_mutation` (mocks environment='sandbox'; asserts service call + DB write). |
| F17 | **`InvalidOverrideComboError` should NEVER fire from web POST** (web does not pass the auto-redirect triple). Maps to 500 defense-in-depth in the catch ladder. | Phase 12.5 #1 F15 + spec §9.2 | T-2.6 catch-ladder regression — fault-inject the exception + assert 500 response (developer-bug class). |
| F18 | **Audit-row parity uses semantic-shape projection, NOT byte-identical comparison.** | Spec §13.3 R2 LOCK | T-2.11 `test_cli_web_audit_row_semantic_shape_parity`. |
| F19 | **No `Co-Authored-By` footer on ANY commit.** Per project invariant + ~140+ cumulative ZERO drift streak. | CLAUDE.md "No Claude co-author footer" + brainstorm chain ZERO drift | Brief explicit prompt suppression at executing-plans dispatch + pre-merge orchestrator-rebase check. |
| F20 | **Plan-author schema escalation rule.** If executing-plans implementer surfaces a need for schema addition, STOP + escalate to orchestrator BEFORE coding. | Phase 9 Sub-bundle A return report lesson #7 + brief §6 | Plan author cites this lock at F20; Codex chain verifies via plan inspection. |
| F21 | **Codex R3 LOCK + Phase 12.5 #1 F23 carry-forward**: VM retrofit scope is via grep audit (Pass A field declarations) — NOT hard-coded class list. If a new VM lands between plan-drafting and executing-plans implementation, the test pattern catches the regression via the grep-at-test-time pattern. | Spec §3 + Codex R5 M#1 | T-2.8 retrofit completeness audit. |

---

## §G Per-task acceptance-criteria narrative

Most acceptance criteria are encoded inline in §A. This section deepens the criteria for the 2 tasks that span multiple files OR multiple architectural layers:

### §G.1 T-2.9 narrative (Pass B retrofit; per-callsite call-shape decision matrix)

The Pass B retrofit touches 21 call sites across 12 files (per §C.5 grep). Two patterns coexist in the current code base:

**Pattern A (conn-shape — 20 sites)**: the route or builder function opens `conn = sqlite3.connect(...)` directly (or accepts a `conn` argument from its caller) + calls `count_unresolved_material(conn)` on the open connection. T-2.9 acceptance: at each such site, add an adjacent call `banner_resolve_link = fetch_first_pending_ambiguity_resolve_link_path(conn)` then thread `banner_resolve_link=banner_resolve_link` into the VM constructor.

Worked example for `swing/web/view_models/dashboard.py:909` (preserving the EXISTING `with sqlite3.connect(db_path) as conn:` context-manager idiom at the surrounding site; T-2.9 only adds the adjacent helper call + the new VM kwarg pair — NOT a connection-management rewrite):

```python
# BEFORE:
with sqlite3.connect(db_path) as conn:
    unresolved_material_count = count_unresolved_material(conn)
    # ... other reads ...
    vm = DashboardVM(
        session_date=...,
        unresolved_material_discrepancies_count=unresolved_material_count,
        recent_multi_leg_auto_correction_count=...,
        # other fields
    )

# AFTER:
with sqlite3.connect(db_path) as conn:
    unresolved_material_count = count_unresolved_material(conn)
    banner_resolve_link = fetch_first_pending_ambiguity_resolve_link_path(conn)
    # ... other reads ...
    vm = DashboardVM(
        session_date=...,
        unresolved_material_discrepancies_count=unresolved_material_count,
        banner_resolve_link=banner_resolve_link,  # NEW
        recent_multi_leg_auto_correction_count=...,
        # other fields
    )
```

**Note on T-2.5 / T-2.6 vs T-2.9 connection-management asymmetry.** T-2.5 + T-2.6 (the NEW `/reconcile/discrepancy/{id}/resolve` route handlers) use **explicit `try: ... finally: conn.close()`** rather than `with sqlite3.connect(...) as conn:` per spec §4.1 Codex R3 M#3 LOCK + spec §4.2 LOCK. The rationale: spec §4 explicitly requires connection closure on ALL early-return branches (404 / 409 / 400) where a `with` block would still close correctly but the spec author chose the explicit `try/finally` form to make the closure-guarantee discriminating-test-easy (mock `sqlite3.connect`, assert `conn.close()` invoked exactly once even on early-return). T-2.9 retrofit at pre-existing callsites does NOT rewrite the existing `with` blocks (would be out-of-scope churn). The two patterns coexist; both are correct.

**Pattern B (db_path-shape — 1 site at `swing/web/routes/schwab.py:92`)**: a module-level helper `_fetch_unresolved_material_count(db_path) -> int` opens a short-lived connection internally. T-2.9 acceptance: add a SIBLING helper `_fetch_banner_resolve_link(db_path) -> str | None` adjacent to it (mirrors the Phase 12.5 #1 T-1.8 sibling helper `_fetch_recent_multi_leg_auto_correction_count`); thread the result through the same VM-constructor call sites (the schwab GET + POST + status handlers each call _fetch_unresolved_material_count today and gain a parallel call to _fetch_banner_resolve_link).

**Per-callsite acceptance checklist** (executing-plans implementer MUST verify each call site is retrofitted; T-2.9 test pattern at the end audits programmatically):
- `swing/web/view_models/dashboard.py:909` — DashboardVM build
- `swing/web/view_models/journal.py:136` — JournalVM build
- `swing/web/view_models/pipeline.py:42` — PipelineVM build
- `swing/web/view_models/watchlist.py:130` — WatchlistVM build
- `swing/web/view_models/config.py:130` — ConfigPageVM build
- `swing/web/view_models/trades.py:703, 799, 848, 1042` — 4 trades-VM builds
- `swing/web/view_models/metrics/{capital_friction,hypothesis_progress_card,deviation_outcome,index,identification_funnel,trade_process_card,process_grade_trend,tier_comparison,maturity_stage}.py` — 9 metrics-page VMs (counted via grep; index.py at line 97 uses the kwarg style — direct constructor call)
- `swing/web/routes/account.py:87, 114` — POST account snapshot success path + error path
- `swing/web/routes/schwab.py:92` — `_fetch_unresolved_material_count` helper (Pattern B sibling-helper retrofit)

**Test pattern per site** is the populated-route regression test: `client.get("<route>")` → response body contains the `data-banner-resolve-link="true"` substring when the planted DB state has at least one pending-ambiguity discrepancy in the banner set. T-2.9's `tests/web/test_banner_resolve_link_population_per_route.py` parametrizes over the route URLs.

### §G.2 T-2.6 narrative (POST handler — full error catch-ladder)

T-2.6 is the most complex single task. The handler has **18 distinct response branches** (per spec §8.1; branch 14 splits into 14a/14b per Codex R1 M#2 fix — `ValueError` post-service requires re-read to disambiguate concurrent-resolve race vs handler-payload rejection):

1. 200 success (HTMX) → 204 + HX-Redirect
2. 200 success (non-HTMX) → 303 RedirectResponse
3. 404 discrepancy not found
4. 409 terminal-state resolution
5. 409 null ambiguity_kind
6. 400 empty `choice_code`
7. 400 invalid `choice_code` (not in static menu + not parametric)
8. 400 `requires_custom_value=True` but missing custom_value
9. 400 `custom_value` JSON parse failure
10. 400 empty `resolution_reason`
11. 400 missing `ambiguity_kind_at_render` anchor
12. 409 `ambiguity_kind_at_render` mismatch
13. 400 `ValidatorRejectedError`
14a. 400 `ValueError` from service after re-read confirms discrepancy still pending (handler payload-shape rejection / unknown handler)
14b. 409 `ValueError` from service after re-read shows discrepancy concurrently moved to terminal state (concurrent-resolve race; Codex R1 M#2 fix)
15. 409 `AlreadySupersededError` (defense-in-depth)
16. 500 `CallerHeldTransactionError` / `InvalidOverrideComboError` / bare `Exception`
17. 503 `sqlite3.OperationalError`

T-2.6's test suite covers branches 1, 3, 6, 11/12, 7/14a, 9, 13 explicitly (8 tests per §A) PLUS a NEW dedicated test for branch 14b — `test_post_value_error_concurrent_race_returns_409_not_400` (planted via mock or two-TestClient-thread setup; Codex R1 M#2 acceptance pin); branches 2, 4, 5, 8, 10, 15, 16, 17 covered by additional parametrize entries OR centralized in the T-2.10 error-template test suite.

**Field-discipline contract per spec §6 + Phase 8 R2-R4 LOCK**: the form submits FOUR named values. Three are operator-supplied (`choice_code`, `custom_value`, `resolution_reason`); one is server-stamped state-anchor (`ambiguity_kind_at_render` — set in the form-render by the template; verified at POST). The handler also server-stamps `resolved_by_override='operator_web'` at handler entry (per F2 LOCK; NOT operator-supplied; NOT a hidden form input). The `discrepancy_id` flows through the URL path parameter. `form_action` is server-rendered into the template. Nothing else.

**Discriminating tampered-input regression test**: T-2.11's slow E2E + a T-2.6 unit test simulate a hand-crafted POST with `resolved_by` field as a form-submitted value (e.g., operator tries `resolved_by='operator'` via `curl -d 'resolved_by=operator'`). The handler MUST IGNORE this field (it is not in the `form.get(...)` extraction list) + still stamp `'operator_web'`. Assert `reconciliation_discrepancies.resolved_by` post-resolve is `'operator_web'`.

---

## §H Operator-witnessed gate plan (6 surfaces per LOCK §1.2 #12 / spec §17)

### §H.1 S1 — Inline pytest + ruff + slow E2E

```powershell
cd .worktrees/phase12-5-bundle-2-web-tier2-executing-plans
python -m pytest -m "not slow" -q -n auto
ruff check swing/ --statistics
python -m pytest -m slow tests/integration/test_phase12_5_bundle_2_web_tier2_happy_path.py -v
```

**Acceptance:** ~4793 fast tests green (4712 baseline + ~78 new); 3 pre-existing phase8 failures unchanged; 5 skipped unchanged; ruff 18 E501 unchanged; 1 slow E2E PASS.

### §H.2 S2 — Banner-link navigation

Start the web app from worktree (per operator's `feedback_worktree_cli_invocation.md`):

```powershell
$env:SCHWAB_CLIENT_ID = "<value>"  # if Schwab env vars normally set; not strictly required
$env:SCHWAB_CLIENT_SECRET = "<value>"
python -m swing.cli web --port 8081
```

Open `http://127.0.0.1:8081/dashboard` in a browser with at least one pending-ambiguity discrepancy seeded (operator may need to plant one via `swing journal discrepancy resolve` workflow if production has no pending rows at gate time). **Acceptance:** banner renders with a `<a href="/reconcile/discrepancy/{id}/resolve">` link wrapping the count text; clicking the link navigates to the resolve form for the oldest-id pending discrepancy.

### §H.3 S3 — Form render with pre-resolution context

Navigate to `/reconcile/discrepancy/{id}/resolve` (via S2 banner click OR direct URL). **Acceptance:**
- Pre-resolution context section renders above the form with the 10 context pairs from spec §6.
- Choice menu renders one row per `get_choice_menu(disc.ambiguity_kind)` entry with `recommended` badge + `payload required` badge where applicable + shape-hint paragraph for parametric-pick choices.
- Hidden anchor `<input type="hidden" name="ambiguity_kind_at_render" value="...">` visible in browser dev-tools.
- Custom-value textarea rendered (toggles visibility based on focused radio's `data-requires-custom-value` attribute).
- Resolution-reason textarea rendered (required).
- ZERO console errors.

### §H.4 S4 — Submit + HX-Redirect

In S3 form: pick a recommended choice (e.g., `keep_journal_as_is` for a `multi_partial_vs_consolidated` discrepancy), type a resolution reason, submit. **Acceptance:**
- Browser navigates to `/dashboard?reconcile_resolved={correction_id}` (HX-Redirect mechanic verified).
- DB inspection: `reconciliation_corrections` row inserted with `applied_by='operator'` + `correction_action='operator_resolved_ambiguity'` + the operator-typed `correction_reason`.
- DB inspection: `reconciliation_discrepancies.resolved_by='operator_web'` (distinguishability from CLI verified).

### §H.5 S5 — Banner-clears post-resolve

After S4 redirect, dashboard re-renders. **Acceptance:** banner count drops by 1; if no other pending-ambiguity rows exist, banner suppressed entirely (`<aside data-banner=...>` absent from DOM).

### §H.6 S6 — CLI/web parity end-to-end

Plant a second pending-ambiguity discrepancy (structurally identical to the S4 target). Resolve it via:

```powershell
python -m swing.cli journal discrepancy resolve-ambiguity <id> --choice keep_journal_as_is --reason "gate-test"
```

Query DB:

```sql
SELECT resolved_by FROM reconciliation_discrepancies WHERE discrepancy_id = <id>;
-- Expected: operator
SELECT applied_by, correction_action FROM reconciliation_corrections WHERE discrepancy_id = <id>;
-- Expected: operator, operator_resolved_ambiguity
```

**Acceptance:** CLI path persists `resolved_by='operator'` (distinguishable from S4's `'operator_web'`); `applied_by` + `correction_action` match the S4 row (parity); the semantic-shape projection (excluding identity/time/source-row fields) matches verbatim between the two paths.

---

## §I Cross-bundle pins (single-bundle dispatch; pure read-only consumer)

Phase 12.5 #2 is a CONSUMER of:

1. **Phase 12 Sub-sub-bundle C.D shipped** — `swing journal discrepancy resolve-ambiguity` CLI + `apply_tier2_resolution(resolved_by_override=...)` kwarg path. Plan §A T-2.1 + T-2.6 + T-2.11 cross-reference this shipped surface (NOT modified).
2. **Phase 12.5 #1 SHIPPED at `6109261`** — `BaseLayoutVM.recent_multi_leg_auto_correction_count` field (already retrofitted across 13 standalone VMs). Plan §A T-2.7 mirrors the retrofit pattern verbatim; the new `banner_resolve_link` field lands ADJACENT to `recent_multi_leg_auto_correction_count` at every site.
3. **Phase 12 Sub-bundle B SHIPPED at `b09eb06`** — `/schwab/setup` route + HX-Redirect + atomic-mutation discipline + `apply_overrides(cfg)` at entry. Plan §A T-2.5 + T-2.6 mirror this 1:1 (route format reference).
4. **Phase 9 Sub-bundle B SHIPPED at `e96834a`** — `list_unresolved_material_for_active_trades` + `list_unresolved_material_for_closed_trades` repo helpers. Plan §A T-2.9's new `list_pending_ambiguities_in_banner_set` is a thin filter over the union of these two.
5. **Phase 10 Sub-bundle E T-E.3 SHIPPED** — `count_unresolved_material` helper + `BaseLayoutVM.unresolved_material_discrepancies_count` retrofit pattern. Plan §A T-2.7 + T-2.8 + T-2.9 inherit the retrofit-pattern + grep-driven completeness audit.
6. **Phase 12 Sub-sub-bundle C.D SHIPPED** — `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` allowlist discipline. Plan §A T-2.6 inherits implicitly: the web POST does NOT widen the manual-resolution allowlist; the route only invokes `apply_tier2_resolution` (which is the canonical service path) and never bypasses to the legacy `resolve_discrepancy` CLI surface.

No cross-bundle pins SKIP unskipped (T-2.x has no `@pytest.mark.skip` decorators planned).

---

## §J V2.1 §VII.F amendment candidates banked during planning (scaffold)

Codex chain rounds MAY surface additional candidates.

| # | Candidate | Source | Disposition |
|---|---|---|---|
| J1 | Spec §5.4 builder signature adds `prior_ambiguity_kind_at_render: str = ''` kwarg (between `prior_resolution_reason` and `error_band_message`) to match the spec §5.1 VM field `prior_ambiguity_kind_at_render`. The spec §5.4 signature as written omits this kwarg even though the corresponding VM field exists for error re-render shape preservation per spec §6 + §11.9 hidden-anchor tamper/drift walkthrough. | Pre-Codex review 2026-05-18 (plan-vs-spec delta); plan T-2.3 keeps the kwarg per VM-field requirement | Banked for V2.1 §VII.F amendment; spec §5.4 signature should be amended to enumerate the kwarg explicitly. Plan T-2.3 acceptance documents the addition + rationale. Codex chain may ratify by either path (amend spec OR drop builder kwarg + reconstruct from session). |

---

## §K Test + LOC projections (refined per-task)

| Task | LOC (production) | LOC (tests) | Fast tests | Slow tests |
|---|---|---|---|---|
| T-2.1 | ~30 | ~50 | 5 | 0 |
| T-2.2 | ~180 | ~150 | 12 | 0 |
| T-2.3 | ~80 | ~100 | 8 | 0 |
| T-2.4 | ~150 (template) | ~80 | 6 | 0 |
| T-2.5 | ~120 | ~90 | 7 | 0 |
| T-2.6 | ~185 | ~135 | 9 | 0 |
| T-2.7 | ~40 (field decls + post_init) | ~70 | 10 | 0 |
| T-2.8 | ~15 (template diff) | ~80 | 8 | 0 |
| T-2.9 | ~80 (helper + retrofit) | ~120 | 6 + N (per-route) | 0 |
| T-2.10 | ~80 (template + VM) | ~70 | 6 | 0 |
| T-2.11 | ~10 (cycle-checklist + CLAUDE.md) | ~200 (3 test files) | 5 | 1 |
| **Totals** | **~970 production LOC** | **~1145 test LOC** | **~81 fast tests** | **1 slow** |

**Net fast-test delta**: +81 (4712 baseline → ~4793 post-merge).
**Net production LOC delta**: ~+965.
**Net test LOC delta**: ~+1140.
**Schema delta**: ZERO (F1 LOCK).
**Ruff delta**: 18 E501 baseline preserved (Phase 12.5 #3 clears).

Spec §12 projected ~+45-75 fast tests; plan refinement lands at +81 (matches the overshoot precedent across Phase 9 / 10 / 12 dispatches; +1 from Codex R1 M#2 ValueError-race regression pin). Slightly above the spec's upper band; matches the brief's `~+80 fast tests + 1 slow E2E + ~+450 LOC` projection within rounding. Production LOC is ~+520 above brief projection because the retrofit footprint (T-2.7 + T-2.9 across ~30 files) is mechanical but additive across the row count.

---

## §L Dispatch brief skeleton (orchestrator hand-off for executing-plans)

```
# Phase 12.5 #2 — Web Tier-2 Discrepancy-Resolution Surface — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 12.5 #2 executing-plans implementer.

**Plan:** docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md (~800 lines; Codex-converged at <N> rounds NO_NEW_CRITICAL_MAJOR)

**Spec:** docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md (721 lines; brainstorm-locked + 6 Codex rounds)

**Skill:** copowers:executing-plans (wraps superpowers:subagent-driven-development + adversarial Codex review).

**Scope:** single sub-bundle ship; 11 tasks T-2.1..T-2.11; ~+81 fast tests + 1 slow E2E + ~+965 LOC; schema v19 UNCHANGED.

**Worktree:** branch `phase12-5-bundle-2-web-tier2-executing-plans` (matches cleanup-script regex). Worktree dir `.worktrees/phase12-5-bundle-2-web-tier2-executing-plans/`.

**Hard locks (§D + §F):**
- 4 spec §2 operator-locks + 8 §16 operator-locks (12 total)
- 21 invariants F1-F21
- ZERO Co-Authored-By footer on ANY commit (F19; ~140+ project-cumulative streak)
- NO --no-verify; NO --amend
- Schema escalation rule (F20)

**Adversarial review:** copowers:adversarial-critic invokes Codex on every commit batch. Expected 3-5 Codex rounds.

**Operator-witnessed gate:** 6 surfaces per §H. Orchestrator-driven post-Codex.

**Pre-Codex orchestrator-side review (BINDING per brief §6):** before invoking Codex, dispatch focused reviewer subagent with §A acceptance + §D locks + §F invariants as anchors. Cheap; absorbed LOCK divergences pre-Codex on Phase 12 C.C + C.D + Sub-bundle 1 + Phase 12.5 #1.
```

---

## §M Forward-binding lessons for executing-plans (scaffold; populated post-Codex)

Inherited from brainstorm return report §8 (8 lessons):

1. Brief-conjecture-vs-actual-schema gap → grep verify at brainstorm/plan time (R3 catch: brief §2.7 surface-column conjecture wrong; verified by reading migration 0019 directly).
2. BaseLayoutVM-inheritance is asymmetric (13 existing VMs DO NOT inherit; carry standalone fields). Pass A grep at retrofit time.
3. Hidden state anchors are DISTINCT from hidden audit fields. Server-stamp audit fields (Phase 8 R2-R4); use form-render hidden anchors for TOCTOU defense (Phase 9 D R2).
4. OriginGuard strict-vs-non-strict 303-fallback shapes: 204 + HX-Redirect under HTMX; 303 RedirectResponse under non-HTMX same-origin.
5. Banner-link targets derive from the canonical helper used by the banner count (NOT a separate query). R1 LOCK.
6. Audit-row parity tests use semantic-shape projection (excludes identity/time/source-row fields).
7. Grep-driven audits split by intent (Pass A field-declaration grep, Pass B call-site population grep). Avoid broad grep matching comments + tests + template reads.
8. Retrofit completeness is a discriminating test, NOT a static class list — runs the grep at test time + fails loudly when a future VM drifts.

NEW writing-plans-surfaced lessons (populated post-Codex if any):

- (scaffold) — Codex chain may surface additional pre-execution lessons.

---

## §N Open questions for orchestrator triage (scaffold; default empty)

| # | Question | Status |
|---|---|---|
| (none) | — | All 12 operator-locks pre-baked; no scope ambiguity surfaced at plan-drafting time. |

---

## §Z V2 candidates banked (mirrored from spec §15)

1. `/reconcile/correction/{id}/show` audit-chain page — V2.
2. One-time success toast on `/dashboard?reconcile_resolved={id}` — V2.
3. Web Tier-3 override surface — V2.
4. Web Tier-1 auto-correct undo surface — V2.
5. `/reconcile/pending` list page — V2 (replaces banner-link-to-first with list-then-pick).
6. `reconcile_resolved` toast renderer — V2.
7. Pipeline-active exclusion on web Tier-2 path — V2 (mirror of `SchwabPipelineActiveError`; out-of-scope V1 because service-layer does not currently enforce on `apply_tier2_resolution`).
8. `schwab_api_call_id` form input on web — V2.
9. Per-discrepancy-type HX-Redirect targets — V2 (e.g., `/metrics/capital-friction` after `snapshot_mismatch`).
10. Explicit `surface` column on `reconciliation_corrections` — V2 (v19 → v20 migration; avoids parsing `resolved_by`).
11. Inline HTMX swap UX — V2 (rejected V1 per operator-LOCK §1.1 #1; banked for operator-driven reconsideration).
12. JS for conditional custom-value input → move to `static/reconcile.js` — V2 (currently 12-line inline `<script>` per §1.2 #10 LOCK).
13. DRY `_parse_parametric_pick_count` helper — V2 (consolidate into `swing/trades/reconciliation_ambiguity_choices.parse_parametric_pick_count` + refactor CLI; brief §4 OUT-OF-SCOPE preservation lock V1).

---

*End of plan. Phase 12.5 #2 executing-plans target: 1 GET + 1 POST route + 1 VM module + 2 templates + base-layout retrofit across 13 VMs + Pass B population across 21 sites. Schema v19 UNCHANGED. ~+81 fast tests + 1 slow E2E + ~+965 LOC. 3-5 Codex rounds projected.*
