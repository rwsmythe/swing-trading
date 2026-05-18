# Phase 12.5 #2 — Web Tier-2 Discrepancy-Resolution Surface — Design Spec

**Status:** brainstorm-locked (pending Codex chain).
**Author:** Phase 12.5 #2 brainstorm implementer.
**Date:** 2026-05-18.
**Branch:** `phase12-5-bundle-2-web-tier2-brainstorm` (worktree at `.worktrees/phase12-5-bundle-2-web-tier2-brainstorm/`).
**Brief:** `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-dispatch-brief.md` (commit `d642175`).

This spec mirrors the Phase 12.5 #1 spec format (sections §0-§16). It is consumer-side of the Phase 12 Sub-bundle C.A-C.D ship (classifier + validator-shim + auto-correction service + Tier-2 CLI) and Phase 12.5 #1 (OQ-F multi-leg tier-1 auto-redirect). **Schema v19 UNCHANGED** (see §14 for the surface-attribution analysis that supersedes the dispatch brief's §2.7 conjecture).

---

## §0 Glossary

| Term | Meaning |
| --- | --- |
| Tier-1 | Unambiguous auto-correct from Schwab (`apply_tier1_correction`; `correction_action='auto_applied'`; resolves `discrepancy.resolution='auto_corrected_from_schwab'`). |
| Tier-2 | Operator-resolved ambiguity (`apply_tier2_resolution`; `correction_action='operator_resolved_ambiguity'`; resolves `discrepancy.resolution='operator_resolved_ambiguity'`). **This spec's subject.** |
| Tier-3 | Operator override of an applied correction (`apply_tier3_override`; `correction_action='operator_overridden'`; chains via `reconciliation_corrections.superseded_by_correction_id`). |
| `ambiguity_kind` | Per-discrepancy classifier output enumerating which operator-decision menu applies (7 values per migration 0019: `multi_partial_vs_consolidated`, `multi_match_within_window`, `unknown_schwab_subtype`, `field_shape_incompatible`, `schwab_returned_no_match`, `validator_rejected`, `unsupported`). |
| Choice menu | `swing.trades.reconciliation_ambiguity_choices.get_choice_menu(ambiguity_kind)` returns `list[ChoiceMenuItem]` with `code`/`description`/`requires_custom_value`/`recommended`/`expected_payload_shape_description` per item. **PURE function** — no DB, no I/O. |
| Pending-ambiguity row | A `reconciliation_discrepancies` row in `resolution='pending_ambiguity_resolution'` with non-NULL `ambiguity_kind`. Surfaced by `swing journal discrepancy list-pending-ambiguities`. |
| Banner | Global header in `base.html.j2` that fires when `unresolved_material_discrepancies_count > 0` (Phase 10 Sub-bundle E T-E.3) AND/OR when `recent_multi_leg_auto_correction_count > 0` (Phase 12.5 #1 T-1.8). |
| OriginGuard | The strict-mode CORS/CSRF middleware in `swing/web/middleware/origin_guard.py`. Rejects non-HTMX form submits with 403 unless the form carries `hx-headers='{"HX-Request": "true"}'`. |
| BaseLayoutVM | `swing/web/view_models/metrics/shared.py:BaseLayoutVM` — the canonical mixin every base-layout page extends. Carries 7 fields (Phase 10 T-E.3 5 + Phase 12.5 #1 T-1.8 1 + the existing `session_date`). |

---

## §1 Architecture overview

Phase 12 Sub-bundle C.D shipped a CLI-only operator surface for Tier-2 resolution (`swing journal discrepancy show-ambiguity <id>` + `resolve-ambiguity <id> --choice <code> --reason <text> [--custom-value <json>]`). Operators routinely use the web app's `/dashboard` + `/trades/{id}` + `/metrics/*` surfaces and the dashboard banner already advertises unresolved-material discrepancy counts. Phase 12.5 #2 closes the loop with a **dedicated web form page** that mirrors the CLI 1:1 — same choice menu, same per-choice `requires_custom_value` contract, same `apply_tier2_resolution` service entry, same audit row shape — plus a **pre-resolution context section** above the form so operators arriving via banner click have the discrepancy detail they need to choose without first invoking the CLI.

**One page, one POST, one HX-Redirect.** The page lives at `GET /reconcile/discrepancy/{id}/resolve`. The form POSTs to the same path; success returns `204` + `HX-Redirect: /dashboard?reconcile_resolved={correction_id}` (see §1.2). All transactional discipline (BEGIN IMMEDIATE / COMMIT / ROLLBACK) lives at the service layer; the route handler is a thin form-parser + error-catch-ladder + base-layout-VM populator.

The CLI surface stays AS-IS (no deprecation, no removal). CLI and web share the same service-layer entry. Surface distinguishability in the audit trail is achieved by setting `resolved_by_override='operator_web'` on the existing `apply_tier2_resolution` kwarg, which persists to `reconciliation_discrepancies.resolved_by` (free TEXT — no CHECK constraint; no schema change required); CLI keeps the default `'operator'`.

---

## §2 Pre-locked operator decisions (operator-locked 2026-05-18; verbatim binding clauses)

These were locked by orchestrator-operator scope conversation post Phase 12.5 #1 merge; Codex chain MUST NOT re-litigate.

### §2.1 LOCK D1 — Dedicated form page at `GET /reconcile/discrepancy/{id}/resolve`

NOT inline HTMX swap on dashboard. NOT 2-step list-page → form. The route is `GET /reconcile/discrepancy/{id}/resolve` for form-render and `POST /reconcile/discrepancy/{id}/resolve` for submit. Banner-driven entry navigates directly to the resolve form for the FIRST pending-ambiguity discrepancy (§10.2). Dashboard does NOT add a per-discrepancy list V1; that is banked as V2 candidate §15.5.

### §2.2 LOCK D2 — Success path is `204 + HX-Redirect: /dashboard?reconcile_resolved={correction_id}`

NOT "stay on form with success banner". NOT HX-Redirect to `/reconcile/correction/{id}/show` (V2 candidate §15.4 — that surface does not yet exist). The query-string token `reconcile_resolved={correction_id}` is informational only; V1 dashboard does NOT consume it. The token exists so future V2 work (banked §15.6) can render a one-time success toast without re-shaping the redirect contract.

### §2.3 LOCK D3 — CLI counterpart preservation; surface attribution via `resolved_by`

`swing journal discrepancy show-ambiguity` + `resolve-ambiguity` CLI commands stay AS-IS. Both surfaces call the same `apply_tier2_resolution` entry. **CLI continues to pass NO `resolved_by_override`** → `effective_resolved_by` defaults to `'operator'` (per existing service-layer behavior). **Web passes `resolved_by_override='operator_web'`** → discrepancy `resolved_by='operator_web'`. The `reconciliation_corrections.applied_by` column stays `'operator'` on both paths (the schema CHECK is `applied_by IN ('auto', 'operator')`; web does NOT widen it). No schema migration required (see §14).

### §2.4 LOCK D4 — Pre-resolution context section ABOVE the choice menu

The form template renders a "Pre-resolution context" section ABOVE the choice menu showing: `discrepancy_type` / `ambiguity_kind` / `journal_side_value` / `schwab_side_value` / `delta_text` / `classifier_resolution_reason`. Same context the `swing journal discrepancy show-ambiguity <id>` CLI surfaces today. NOT minimal-form (no pre-context section). NOT full audit chain link to `/reconcile/correction/{id}/show` (V2 candidate §15.4). The renderer falls back gracefully when `actual_value_json` cannot be parsed or per-discrepancy-type fields are missing — see §7.

---

## §3 Module touch list

NEW files:

* `swing/web/routes/reconcile.py` — Tier-2 resolution route handlers (1 GET + 1 POST handler; ~250 LOC including error catch-ladder).
* `swing/web/view_models/reconcile.py` — `ReconcileDiscrepancyResolveVM` + `ReconcileChoiceFormItem` + `ReconcilePreResolutionContext` + `ReconcileDiscrepancyErrorVM` frozen dataclasses + `build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id)` builder (~200 LOC).
* `swing/web/templates/reconcile_discrepancy_resolve.html.j2` — pre-resolution context section + form section + error-message bands (~150 LOC).
* `swing/web/templates/reconcile_discrepancy_resolve_error.html.j2` — full-page error template for 404/409/500 paths (~50 LOC).

EDITED files:

* `swing/web/app.py` — register the new `reconcile` router after the existing `schwab` router.
* `swing/web/view_models/metrics/shared.py` — **add `banner_resolve_link: str | None = None` to `BaseLayoutVM`** (NOT to `DashboardVM` alone). Per CLAUDE.md "base.html.j2 is shared" gotcha: every base-layout page extends this template, so `base.html.j2` must be able to dereference `vm.banner_resolve_link` on EVERY VM without `UndefinedError`. Inheritance via `BaseLayoutVM` propagates the default `None` to every existing base-layout VM (Phase 10 T-E.3 retrofitted 10 VMs to extend BaseLayoutVM; Phase 12.5 #1 T-1.8 used the same pattern). New `__post_init__` clause is not required (None is valid; no range check).
* `swing/web/routes/dashboard.py` — populate `vm.banner_resolve_link` with the FIRST pending-ambiguity discrepancy's resolve-form URL when one exists (§10.2). For every OTHER base-layout-rendering route (schwab status, account snapshot, metrics, trades detail, etc.), the field stays at its `BaseLayoutVM` default `None` — they do NOT need to populate it because the banner is dashboard-centric (the link is only "actionable from the page that surfaces the unresolved count to the operator"). Defense-in-depth: the `base.html.j2` template renders the link with a Jinja truthiness check (`{% if vm.banner_resolve_link %}`), so a None value (defaulted from BaseLayoutVM) renders as a count-without-link banner exactly like the pre-Phase-12.5-#2 behavior.
* `swing/web/templates/base.html.j2` — when the unresolved-material banner fires (`vm.unresolved_material_discrepancies_count > 0`) AND `vm.banner_resolve_link` truthy, wrap the count text in an `<a href="{{ vm.banner_resolve_link }}">` link. The banner text stays ASCII-only.

No service-layer changes. No schema changes.

---

## §4 Route handler design (GET + POST)

### §4.1 `GET /reconcile/discrepancy/{id}/resolve`

**Responsibility:** render the form for an existing pending-ambiguity discrepancy.

Flow:

1. `cfg = apply_overrides(request.app.state.cfg)` (Phase 12 Sub-bundle B Codex R1 Critical #1 inheritance — required at every web entry point that consumes user-config.toml).
2. `conn = sqlite3.connect(cfg.paths.db_path)`. NO transaction opened by route — read-only consumer.
3. `disc = get_discrepancy(conn, id)`. If `disc is None` → 404 + `reconcile_discrepancy_resolve_error.html.j2` (`error_kind='not_found'`).
4. If `disc.resolution != 'pending_ambiguity_resolution'` OR `disc.ambiguity_kind is None` → 409 + error template (`error_kind='already_resolved'` with `disc.resolution` + `disc.resolved_by` echoed).
5. `vm = build_reconcile_discrepancy_resolve_vm(conn, id)` — populates pre-resolution context + choices + base-layout fields.
6. Render `reconcile_discrepancy_resolve.html.j2` with the VM.

**HTTP responses:** 200 happy path; 404 not-found; 409 already-resolved. ZERO Schwab API calls; ZERO DB writes.

### §4.2 `POST /reconcile/discrepancy/{id}/resolve`

**Responsibility:** parse form, call service, redirect on success or re-render with error band on failure.

Flow:

1. `cfg = apply_overrides(request.app.state.cfg)` (same as GET).
2. `form = await request.form()`. Extract:
   * `choice_code: str = (form.get('choice_code') or '').strip()` — required; rejected as 400 when empty.
   * `custom_value_raw: str | None = form.get('custom_value') or None` — note `... or None` per Phase 6 I3 gotcha (nullable text columns; do NOT coerce empty to `""`).
   * `resolution_reason: str = (form.get('resolution_reason') or '').strip()` — required; rejected as 400 when empty.
   * `ambiguity_kind_at_render: str = (form.get('ambiguity_kind_at_render') or '').strip()` — **form-render hidden anchor** per CLAUDE.md "POST-time recompute of latest-of-something creates GET/POST TOCTOU window" gotcha + Phase 9 Sub-bundle D R2 M#1 precedent. Captured by the form-render at the URL value the operator saw; POST validates it against current `disc.ambiguity_kind`. Missing → 400 (tampered or stale browser form); mismatch → 409 (mid-flight reclassification — exceptionally rare but possible if a future hot-fix re-runs the classifier on a stale row).
3. `conn = sqlite3.connect(cfg.paths.db_path)`. Pre-flight checks (read-only):
   a. `disc = get_discrepancy(conn, id)`. None → 404 error template.
   b. `disc.resolution != 'pending_ambiguity_resolution'` OR `disc.ambiguity_kind is None` → 409 error template (TOCTOU: a concurrent CLI resolve landed between GET and POST).
   c. **Form-render anchor check** — `disc.ambiguity_kind != ambiguity_kind_at_render` → 409 error template (anchor drift; clear explanatory text). Empty anchor → 400 (tampered POST). This anchor is the tier-2 analog of Phase 9 Sub-bundle D's `sector_industry_evaluation_run_id` hidden form anchor.
   d. `choice_code in {item.code for item in get_choice_menu(disc.ambiguity_kind)}` OR (for `multi_match_within_window`) `choice_code.startswith('pick_schwab_record_')` → else 400 + re-render form with error band (preserve filled values).
   e. The chosen menu item's `requires_custom_value` is True AND `custom_value_raw is None` → 400 + re-render form with error band (preserve filled values).
   f. When `custom_value_raw is not None`: `try: custom_payload = json.loads(custom_value_raw); except json.JSONDecodeError as exc:` → 400 + re-render form with error band citing `exc.msg`.
4. Service call:
   ```python
   from swing.config_overrides import get_environment_for_reconciliation
   environment = get_environment_for_reconciliation(cfg)  # 'production' or 'sandbox'
   result = apply_tier2_resolution(
       conn,
       discrepancy_id=id,
       choice_code=choice_code,
       operator_custom_payload=custom_payload,  # may be None
       operator_reason=resolution_reason,
       resolved_by_override='operator_web',     # §2.3 LOCK D3 surface attribution
       environment=environment,
   )
   ```
   * Sandbox short-circuit is internal to the service for the auto-redirect path only (Phase 12.5 #1 T-1.6); manual Tier-2 paths still execute under sandbox per existing service contract — web V1 inherits that posture verbatim.
5. Exception catch-ladder (each maps to a distinct HTTP response; mirrors Sub-bundle B's 5-path pattern):
   * `CallerHeldTransactionError` → 500 (developer-bug class; redacted excerpt; should never fire because step 3 does not open a transaction).
   * `InvalidOverrideComboError` → 500 (developer-bug class; should never fire because web passes only `resolved_by_override='operator_web'` which is unrelated to the auto-redirect triple). Treated as defense-in-depth.
   * `ValidatorRejectedError` → 400 + re-render form with error band citing the validator's rejection text.
   * `AlreadySupersededError` → 409 + error template (tier-2 resolution should not encounter this; defense-in-depth for race against a concurrent tier-3 override of an earlier correction in the chain).
   * `ValueError` raised from service (e.g., terminal-state, ambiguity_kind NULL, incompatible (kind, code), payload-shape rejection from a handler) → 400 + re-render form with error band citing `str(exc)`.
   * `sqlite3.OperationalError` (e.g., DB locked) → 503 + error template "DB temporarily unavailable; retry".
   * Bare `Exception` → 500 + error template "Unexpected error; check `swing journal discrepancy show <id>` for state".
6. Success path:
   * `correction_id = result.correction_id` (non-None for manual tier-2 paths under both production and sandbox; sandbox short-circuit applies only to auto-redirect, which web does NOT trigger).
   * Response: `Response(status_code=204, headers={'HX-Redirect': f'/dashboard?reconcile_resolved={correction_id}'})`.
   * Non-HTMX clients receive `RedirectResponse('/dashboard?reconcile_resolved={correction_id}', status_code=303)` (defense in depth; the form always carries `hx-headers` so this branch is reached only when an operator submits without the JS).

**Closing the connection:** `conn.close()` in a `finally` block; the service owns transaction lifecycle. **No `with conn:` wrapper at the route** — service-layer `with conn:` gotcha avoidance.

---

## §5 View-model design + builder function

### §5.1 `ReconcileDiscrepancyResolveVM` (frozen dataclass)

Fields:

| Field | Type | Source / notes |
| --- | --- | --- |
| `session_date` | `str` | BaseLayoutVM. `action_session_for_run(datetime.now()).isoformat()`. |
| `stale_banner` | `str \| None` | BaseLayoutVM. `None`. |
| `price_source_degraded` | `bool` | BaseLayoutVM. `False`. |
| `price_source_degraded_until` | `str \| None` | BaseLayoutVM. `None`. |
| `ohlcv_source_degraded` | `bool` | BaseLayoutVM. `False`. |
| `unresolved_material_discrepancies_count` | `int` | BaseLayoutVM. `count_unresolved_material(conn)`. |
| `recent_multi_leg_auto_correction_count` | `int` | BaseLayoutVM. `count_recent_multi_leg_auto_corrections(conn)`. |
| `discrepancy_id` | `int` | The route argument. |
| `form_action` | `str` | Literal `f"/reconcile/discrepancy/{discrepancy_id}/resolve"`. Server-derived to keep the form-render and POST in sync; never operator-supplied. |
| `pre_resolution_context` | `ReconcilePreResolutionContext` | §5.2. |
| `choices` | `tuple[ReconcileChoiceFormItem, ...]` | §5.3. |
| `prior_choice_code` | `str` | Filled by error re-render path; empty string on first render. |
| `prior_custom_value_raw` | `str` | Filled by error re-render path; empty string on first render. |
| `prior_resolution_reason` | `str` | Filled by error re-render path; empty string on first render. |
| `prior_ambiguity_kind_at_render` | `str` | Filled by error re-render path with the hidden-anchor value the operator's previous submit carried; empty string on first render. Mirrors §4.2 step 2's `ambiguity_kind_at_render` form field so the re-render stamps the SAME anchor value that the failed submit carried — preventing a re-render from silently "fixing" a stale anchor on the operator's behalf. |
| `error_band_message` | `str \| None` | Set to the validator-rejection / JSON-parse / shape-mismatch error text when re-rendering after 400; `None` on first render. |
| `error_band_field_hint` | `str \| None` | Optional `'choice_code'` / `'custom_value'` / `'resolution_reason'` hint so the template can highlight the offending input. |

The VM is **frozen** so test fixtures can compare structurally. The `prior_*` fields exist so the 400 re-render preserves the operator's typed input (Phase 5 R1 M1 + Phase 8 daily-management server-stamping family — operator-supplied fields stay operator-supplied on rerender; nothing is server-stamped here because all three inputs are operator content).

### §5.2 `ReconcilePreResolutionContext` (frozen dataclass)

| Field | Type | Source |
| --- | --- | --- |
| `discrepancy_type` | `str` | `disc.discrepancy_type`. |
| `ambiguity_kind` | `str` | `disc.ambiguity_kind` (non-None precondition enforced at the route). |
| `ticker` | `str` | `disc.ticker` or `'-'`. |
| `field_name` | `str` | `disc.field_name`. |
| `journal_side_label` | `str` | Per-discrepancy-type render-helper output (§7). |
| `journal_side_value` | `str` | Same. |
| `schwab_side_label` | `str` | Same. |
| `schwab_side_value` | `str` | Same. |
| `delta_label` | `str` | Same; `'Delta'` for numeric types; type-specific phrase otherwise (e.g., `'Schwab record count'` for `multi_match_within_window`). |
| `delta_value` | `str` | Per spec §7; numeric types render with `:.2f` (Phase 12 Sub-sub-bundle C.B Codex M#3 LOCK precedent). |
| `classifier_resolution_reason` | `str` | `disc.resolution_reason` verbatim (the classifier emit text). |
| `material` | `bool` | `bool(disc.material_to_review)`. Used for a small "material" badge in the template. |
| `created_at` | `str` | `disc.created_at`. |
| `run_id` | `int` | `disc.run_id`. |
| `parse_warning` | `str \| None` | Non-None when the per-discrepancy-type helper hit a JSON parse failure OR missing-key fallback; the template renders a small muted note "(context fields rendered with degraded parsing; see CLI `show-ambiguity` for raw JSON)". |

All values are rendered as strings to keep the template free of formatting logic (CLAUDE.md OOB-swap drift gotcha analog — single source of truth for rendering).

### §5.3 `ReconcileChoiceFormItem` (frozen dataclass)

| Field | Type | Source |
| --- | --- | --- |
| `code` | `str` | `ChoiceMenuItem.code` OR parametric `f'pick_schwab_record_{N}'`. |
| `description` | `str` | `ChoiceMenuItem.description`. |
| `requires_custom_value` | `bool` | Same. |
| `recommended` | `bool` | Same. |
| `expected_payload_shape_description` | `str \| None` | Same. |
| `is_parametric_pick` | `bool` | True iff `code.startswith('pick_schwab_record_')`. |

### §5.4 Builder function

```
build_reconcile_discrepancy_resolve_vm(
    conn: sqlite3.Connection,
    discrepancy_id: int,
    *,
    prior_choice_code: str = '',
    prior_custom_value_raw: str = '',
    prior_resolution_reason: str = '',
    error_band_message: str | None = None,
    error_band_field_hint: str | None = None,
) -> ReconcileDiscrepancyResolveVM
```

* Reads `disc = get_discrepancy(conn, id)`; raises `ValueError('discrepancy not found')` if None (the route catches this BEFORE calling the builder; the builder's precondition is "non-None disc + non-None ambiguity_kind + resolution = pending_ambiguity_resolution").
* Calls `get_choice_menu(disc.ambiguity_kind)`. For `multi_match_within_window`, prepends parametric `pick_schwab_record_<N>` entries derived from a regex pattern that mirrors the CLI's at `cli.py:2291` BYTE-FOR-BYTE. The pattern lives in a NEW private module-level function in `swing/web/view_models/reconcile.py` named `_parse_parametric_pick_count(resolution_reason: str) -> int` (NOT a CLI refactor — the CLI surface stays AS-IS per brief §4 OUT-OF-SCOPE preservation lock). A discriminating regression test plants the same `resolution_reason` text in both code paths and asserts byte-identical N — pinning that the duplicated regex stays synchronized. If the CLI's pattern ever drifts, the test fails loudly and the operator can choose to consolidate via a separate post-Phase-12.5-#2 dispatch.
* Computes pre-resolution context via the per-discrepancy-type render helpers in §7.
* Reads `count_unresolved_material(conn)` + `count_recent_multi_leg_auto_corrections(conn)` for the base-layout banner fields.

The builder does NOT call `apply_overrides`; the route does. The builder does NOT open a transaction. The builder is **pure modulo `conn` reads**.

---

## §6 Template design (`reconcile_discrepancy_resolve.html.j2`)

Skeleton (200-ish lines including comments):

```html
{% extends "base.html.j2" %}
{% block title %}Resolve Tier-2 Discrepancy #{{ vm.discrepancy_id }}{% endblock %}
{% block content %}
<section class="reconcile-discrepancy-resolve">
  <h1>Resolve Tier-2 discrepancy #{{ vm.discrepancy_id }}</h1>

  {# Pre-resolution context block (§1.4 LOCK D4). #}
  <section class="pre-resolution-context" data-pre-context="true">
    <h2>Pre-resolution context</h2>
    <dl class="context-pairs">
      <dt>Discrepancy type</dt><dd>{{ vm.pre_resolution_context.discrepancy_type }}</dd>
      <dt>Ambiguity kind</dt><dd>{{ vm.pre_resolution_context.ambiguity_kind }}</dd>
      <dt>Ticker</dt><dd>{{ vm.pre_resolution_context.ticker }}</dd>
      <dt>Field</dt><dd>{{ vm.pre_resolution_context.field_name }}</dd>
      <dt>{{ vm.pre_resolution_context.journal_side_label }}</dt>
        <dd>{{ vm.pre_resolution_context.journal_side_value }}</dd>
      <dt>{{ vm.pre_resolution_context.schwab_side_label }}</dt>
        <dd>{{ vm.pre_resolution_context.schwab_side_value }}</dd>
      <dt>{{ vm.pre_resolution_context.delta_label }}</dt>
        <dd>{{ vm.pre_resolution_context.delta_value }}</dd>
      <dt>Material</dt>
        <dd>{% if vm.pre_resolution_context.material %}yes{% else %}no{% endif %}</dd>
      <dt>Created at</dt><dd>{{ vm.pre_resolution_context.created_at }}</dd>
      <dt>Reconciliation run</dt><dd>#{{ vm.pre_resolution_context.run_id }}</dd>
    </dl>
    <p class="muted">Classifier reason:
      {{ vm.pre_resolution_context.classifier_resolution_reason }}</p>
    {% if vm.pre_resolution_context.parse_warning %}
    <p class="muted parse-warning">
      ({{ vm.pre_resolution_context.parse_warning }})
    </p>
    {% endif %}
    <p class="muted">CLI parity: <code>swing journal discrepancy
      show-ambiguity {{ vm.discrepancy_id }}</code></p>
  </section>

  {# Error band (re-render path). #}
  {% if vm.error_band_message %}
  <section class="error-band" data-error-field="{{ vm.error_band_field_hint or '' }}">
    <p>{{ vm.error_band_message }}</p>
  </section>
  {% endif %}

  {# Form section. #}
  <form
    method="post"
    action="{{ vm.form_action }}"
    hx-post="{{ vm.form_action }}"
    hx-headers='{"HX-Request": "true"}'
    hx-target="body"
    data-resolve-form="true">

    <input type="hidden" name="ambiguity_kind_at_render"
      value="{{ vm.pre_resolution_context.ambiguity_kind }}">

    <fieldset>
      <legend>Choose a resolution</legend>
      {% for choice in vm.choices %}
      <label class="choice-row">
        <input type="radio" name="choice_code" value="{{ choice.code }}"
          {% if vm.prior_choice_code == choice.code %}checked{% endif %}
          data-requires-custom-value="{{ choice.requires_custom_value|tojson }}">
        <span class="choice-code">{{ choice.code }}</span>
        {% if choice.recommended %}
        <span class="badge badge-recommended">recommended</span>
        {% endif %}
        {% if choice.requires_custom_value %}
        <span class="badge badge-payload">payload required</span>
        {% endif %}
        <span class="choice-description">{{ choice.description }}</span>
        {% if choice.requires_custom_value
              and choice.expected_payload_shape_description %}
        <p class="muted shape-hint">
          Expected payload shape:
          <code>{{ choice.expected_payload_shape_description }}</code>
        </p>
        {% endif %}
      </label>
      {% endfor %}
    </fieldset>

    <fieldset class="custom-value-fieldset">
      <legend>Custom value (JSON, when required)</legend>
      <textarea
        name="custom_value"
        rows="4"
        placeholder="{}"
        data-custom-value-input="true">{{ vm.prior_custom_value_raw }}</textarea>
      <p class="muted">
        Required for the choices marked "payload required". Parsed as JSON
        via <code>json.loads</code>; deeper shape validation runs at the
        service layer.
      </p>
    </fieldset>

    <fieldset>
      <legend>Resolution reason (required)</legend>
      <textarea name="resolution_reason" rows="3" required
        >{{ vm.prior_resolution_reason }}</textarea>
      <p class="muted">
        Free-text rationale persisted as
        <code>reconciliation_corrections.correction_reason</code>.
      </p>
    </fieldset>

    <button type="submit" class="primary">Apply resolution</button>
  </form>
</section>
{% endblock %}
```

**ASCII-only.** No `→`, `§`, em-dashes, fractions, etc. Phase 12 Sub-sub-bundle C.D gate-fix #1 + #3 inheritance (Windows cp1252 stdout gotcha applies to ANY rendered text that could flow back through stdout via PowerShell-served curl; defense-in-depth).

**JS posture (per §3 OQ #7):** the choice radios carry `data-requires-custom-value` attributes; a 12-line inline `<script>` (mounted in `base.html.j2` extra-scripts block OR inlined in this template) toggles the custom-value fieldset's `display` based on the focused radio. Falling back gracefully when JS is disabled: the custom-value fieldset is ALWAYS rendered; operator can paste JSON regardless. The server enforces the per-choice `requires_custom_value` contract — JS is purely a UX nicety, not a security boundary.

**No hidden audit fields** (Phase 8 R2.M2 + R3.M2 + R4.M2 LOCK family) — `surface='operator_web'` is server-stamped in the route handler (not a form input), `discrepancy_id` flows through the URL (Path parameter; server-derived from the URL pattern), `form_action` is server-rendered into the template. The form has THREE operator inputs: `choice_code`, `custom_value`, `resolution_reason`. Nothing else.

---

## §7 Per-discrepancy-type pre-resolution context render helpers

Spec §6.2.1 enumerates 7 `ambiguity_kind` values but Phase 12.5 #2 must render context for ALL `discrepancy_type` values that emit a pending-ambiguity row. The classifier emits pending-ambiguity for some discrepancy_types under specific input shapes; the cross-product is bounded.

**Strategy:** a single render helper `_render_pre_resolution_context(disc) -> ReconcilePreResolutionContext` switches on `disc.discrepancy_type` and falls back to a generic JSON renderer when the type is unrecognized.

### §7.1 Concrete renderers

| `discrepancy_type` | `journal_side_label` / `value` | `schwab_side_label` / `value` | `delta_label` / `value` |
| --- | --- | --- | --- |
| `entry_price_mismatch` | "Journal entry price" / `expected_value_json['price']:.2f` | "Schwab entry price" / `actual_value_json['price']:.2f` (or `'-'` when missing) | "Price delta" / signed `(schwab - journal):.2f` |
| `close_price_mismatch` | "Journal close price" / `expected['price']:.2f` | "Schwab close price" / `actual['price']:.2f` | "Price delta" / signed `(schwab - journal):.2f` |
| `stop_mismatch` | "Journal stop" / `expected['stop_price']:.2f` | "Schwab stop trigger" / `actual['stop_price']:.2f` | "Stop delta" / signed delta |
| `position_qty_mismatch` | "Journal quantity" / `expected['quantity']` | "Schwab quantity" / `actual['quantity']` | "Quantity delta" / signed delta |
| `cash_movement_mismatch` | "Journal amount" / `expected['amount']:.2f` | "Schwab amount" / `actual['amount']:.2f` | "Amount delta" / signed delta |
| `snapshot_mismatch` | "Journal NLV" / `expected['equity_dollars']:.2f` | "Schwab NLV" / `actual['equity_dollars']:.2f` | "NLV delta" / signed delta |
| `unmatched_open_fill` / `unmatched_close_fill` | "Journal fill" / `f"{quantity} @ {price:.2f} on {fill_datetime}"` | "Schwab match" / `'(none)'` when `actual['matched'] is None`; otherwise `f"{N} candidates within window"` parsed from `disc.resolution_reason` | "Schwab record count" / `f"{N}"` for `multi_match_within_window`; `'(none)'` for `schwab_returned_no_match` |
| `equity_delta` | "Journal NLV" / `expected['journal']:.2f` | "Schwab NLV" / `expected['source']:.2f` | "Equity delta" / `expected['delta']:.2f` |
| `sector_tamper` | "Form-rendered sector/industry" / `expected['sector'] + '/' + expected['industry']` | "Operator-submitted" / `actual['sector'] + '/' + actual['industry']` | "Field" / `disc.field_name` |

**Generic fallback** (unknown discrepancy_type OR JSON parse failure OR missing-key on the expected path): journal_side rendered as raw `disc.expected_value_json` truncated to 80 chars; schwab_side rendered as raw `disc.actual_value_json` truncated; delta rendered as `disc.delta_text or '-'`; `parse_warning` set to a short explanatory note. The form is still functional; operator can still submit; the CLI `show-ambiguity` command stays the authoritative deep-inspect surface (linked verbatim in the template).

### §7.2 Implementation location

The render helpers live in `swing/web/view_models/reconcile.py` as module-level functions prefixed `_render_pre_resolution_context_*`. The dispatch dict + generic fallback live alongside `build_reconcile_discrepancy_resolve_vm`. All helpers are **pure** (no DB; no I/O); inputs are `disc` (the dataclass-shaped row from `get_discrepancy`) plus the parsed `expected_value_json` / `actual_value_json` dicts (parsed via `json.loads` with `try/except` per CLAUDE.md "External-API empty-result must be treated as transient" family — graceful degradation, never raise from a pure renderer).

### §7.3 Discriminating-test pattern

Per-discrepancy-type renderer tests (T-2.5 + T-2.6 — see §12) parametrize across all 11 enumerated types + a "garbage JSON" case + a "missing keys" case. Each assertion checks the exact rendered label + the exact rendered value substring. The shape-helper extraction (`parse_parametric_pick_count`) gets its own 3-case test: matching reason → N; non-matching reason → 0; empty reason → 0.

---

## §8 Error handling + edge cases

### §8.1 Cataloged error paths (mirrors Sub-bundle B's 5-path pattern)

| Condition | HTTP | Template / response |
| --- | --- | --- |
| Discrepancy not found | 404 | `reconcile_discrepancy_resolve_error.html.j2` (`error_kind='not_found'`) |
| Discrepancy in terminal state OR `ambiguity_kind is None` | 409 | error template (`error_kind='already_resolved'`; echoes `resolution` + `resolved_by` + `created_at` + a "this discrepancy was already resolved" message + link to `swing journal discrepancy show {id}` CLI) |
| `choice_code` missing or empty | 400 | re-render form with `error_band_message='Please select a resolution choice.'` + `error_band_field_hint='choice_code'` |
| `choice_code` not in menu (and not a `pick_schwab_record_<N>`) | 400 | re-render form with explanatory text citing valid codes |
| `requires_custom_value=True` but no `custom_value` | 400 | re-render form with shape-hint citing the expected payload |
| `custom_value` provided but `json.loads` fails | 400 | re-render with parse-error message + the operator's typed input preserved |
| `resolution_reason` missing or empty | 400 | re-render with `error_band_field_hint='resolution_reason'` |
| `ambiguity_kind_at_render` hidden anchor missing | 400 | error template ("Form is stale or tampered; please re-open the resolve form") |
| `ambiguity_kind_at_render` mismatches current `disc.ambiguity_kind` | 409 | error template ("Discrepancy state changed since form was rendered; please re-open") |
| `ValidatorRejectedError` from service | 400 | re-render with the validator-error text in the error band |
| `ValueError` from service (handler payload-shape rejection / unknown handler / etc.) | 400 | re-render with the ValueError message |
| `AlreadySupersededError` (tier-3 collision on a concurrent path) | 409 | error template (defense-in-depth; should not fire on tier-2 path) |
| Pipeline-active exclusion | 409 | error template + retry hint (current service-layer does NOT enforce this for tier-2; web V1 does NOT add it; banked V2 §15.7) |
| `sqlite3.OperationalError` (DB busy / lock timeout) | 503 | error template + retry hint |
| `CallerHeldTransactionError` | 500 | error template (developer-bug class) |
| `InvalidOverrideComboError` | 500 | error template (developer-bug class — web should never set the auto-redirect triple) |
| Bare `Exception` | 500 | error template + redacted excerpt + log warning |

### §8.2 TOCTOU and concurrency

* **GET-then-POST drift:** an operator opens the form at time T₁; another operator (or the CLI) resolves the same discrepancy at T₂ < T₃ when the original operator submits. The POST handler's step 3b re-reads the discrepancy AFTER form-parse + BEFORE service call. If `disc.resolution != 'pending_ambiguity_resolution'`, the 409 fires. **There is still a residual race** between step 3 and step 4 (the service call) where a concurrent writer could land between the read and the BEGIN IMMEDIATE; the service-layer's own `_apply_tier2_resolution_inner` step 3 (verify resolution precondition) catches that and raises `ValueError` which is mapped to 400 → re-render with explanatory text. Defense-in-depth.

* **Stale form caching:** because the form-render reads the discrepancy state and the POST validates the operator's choice against the current menu, a long-lived browser tab cannot persist a choice from one resolution into a later, possibly-different, discrepancy. The POST also re-reads `disc.ambiguity_kind` and re-runs `get_choice_menu`; if the operator's `choice_code` is not in the current menu (which could happen if the discrepancy somehow flipped ambiguity_kind between GET and POST — exceptionally rare in V1 because the classifier is invoked once and the stamp is terminal until resolved), 400 + re-render fires.

* **Concurrent banner-target drift:** banner click navigates to the FIRST pending discrepancy URL captured at dashboard-render time. If the targeted discrepancy is resolved between dashboard-render and banner-click, the resolve form's GET returns 409 with the "already resolved" template + link back to `/dashboard`. The operator sees a clean explanation; the banner re-fires on the next dashboard render against the new first-pending discrepancy.

### §8.3 Validation re-render: shape preservation

The error path passes the operator's typed values back to the builder via `prior_choice_code` / `prior_custom_value_raw` / `prior_resolution_reason`. The template re-renders the form with those values pre-filled. The `error_band_field_hint` lets the template highlight the relevant input (via CSS / aria-invalid). All three operator-supplied fields are preserved BYTE-FOR-BYTE.

### §8.4 Sentinel-leak / XSS posture

The pre-resolution context renderers render values via `:.2f` formatting OR raw stringification + Jinja autoescape. The `classifier_resolution_reason` field is a classifier-emitted string from the database (not operator-supplied, but historically classifier text contained `§` glyphs — Phase 12 C.D gate-fix #3 swapped them to ASCII). Jinja's default autoescape (already enabled in `swing/web/app.py` per project convention) handles any residual HTML metacharacters. The 4-sentinel audit pattern (Phase 12 Sub-bundle B + Sub-bundle 2 T-2.5 precedents) gets a discriminating regression test (§12.7): plant a benign sentinel string `X-RECONCILE-SENTINEL-DO-NOT-LEAK` in a discrepancy's `resolution_reason` and assert the form-render escapes it as `X-RECONCILE-SENTINEL-DO-NOT-LEAK` (literal substring) AND the response body contains ZERO `<script>` injection.

The `custom_value_raw` echo on the re-render path is the most direct injection surface. Jinja autoescape handles it; a discriminating test plants `<script>alert(1)</script>` in `custom_value` + asserts the rendered HTML contains the escaped form (`&lt;script&gt;...`).

---

## §9 Surface attribution (`resolved_by_override` wiring)

### §9.1 Service-layer wiring

The route handler passes `resolved_by_override='operator_web'` to `apply_tier2_resolution`. The service-layer flow (verified in `swing/trades/reconciliation_auto_correct.py:1692-1717`):

```python
effective_resolved_by = (
    resolved_by_override if resolved_by_override is not None else "operator"
)
# ... handler runs ...
_flip_discrepancy_to_resolved_ambiguity(
    conn,
    discrepancy_id=disc.discrepancy_id,
    resolution_reason=operator_reason,
    resolved_by=effective_resolved_by,
)
```

Result: `reconciliation_discrepancies.resolved_by = 'operator_web'` on the web path; `'operator'` on the CLI path. The `reconciliation_corrections.applied_by` column stays `'operator'` on both paths (the schema CHECK enforces `('auto', 'operator')`).

### §9.2 `_validate_override_combo` interaction

`apply_tier2_resolution` calls `_validate_override_combo` at step 0. The validator's three invariants (auto_applied_by ↔ auto_correction_action XOR; auto_resolved_by requires the pair; auto-redirect triple only valid under `split_into_partials`) **all fire only when the `auto`-flavored values are present**. Web passes `resolved_by_override='operator_web'` (NOT `'auto_tier1_multi_leg'`); `auto_resolved_by = False`; none of the three invariants trigger. Verified via discriminating test (§12.8).

### §9.3 No schema change required

* `reconciliation_corrections` has NO `surface` column. The dispatch brief §1.3 + §2.7 misframed this as a CHECK widening question; the corrected analysis is in §14 — **schema v19 UNCHANGED**.
* `schwab_api_calls.surface` CHECK is `('pipeline', 'cli')` and is UNAFFECTED — the web Tier-2 form does NOT call Schwab API. The web POST consumes pre-stored discrepancy state; no new `schwab_api_calls` row is written. Pre-existing `reconciliation_corrections.schwab_api_call_id` back-link (from a prior reconciliation run's audit row) is preserved if `apply_tier2_resolution` receives a `schwab_api_call_id` kwarg — but V1 web does NOT pass one (the operator-friendly web surface does not surface the call_id; banked V2 §15.8 if needed).

---

## §10 Banner + dashboard entry-point integration

### §10.1 Banner navigation target — operator decision item §16.1

Three candidates surfaced in the brief §3 #1:

(a) First pending-ambiguity discrepancy's resolve form (RECOMMENDED — matches "fix-the-thing-the-banner-says-needs-fixing" flow and parallels the CLI workflow where operators run `list-pending-ambiguities` → pick one → `resolve-ambiguity`).
(b) A list page enumerating pending discrepancies (V2 candidate §15.5; broader scope; introduces a new VM + template).
(c) Documentation link (clearly worse UX; rejected at brainstorm).

**Brainstorm RECOMMENDS (a)** as V1 default. The banner-rendering template already has `vm.unresolved_material_discrepancies_count`. We add a NEW field `vm.banner_resolve_link: str | None` populated as:

* `None` when `count == 0` (banner suppressed).
* `f'/reconcile/discrepancy/{first_pending_id}/resolve'` when `count > 0` AND a `pending_ambiguity_resolution` discrepancy exists in the unresolved-material set.
* `None` when the unresolved-material count is non-zero but contains ZERO `pending_ambiguity_resolution` rows (e.g., only `'unresolved'`-state material discrepancies; pre-Phase-12-Sub-bundle-C state). In that case, the banner renders the count text WITHOUT a clickable link — the operator's path is still CLI for those rows.

The "first pending" selector is `SELECT discrepancy_id FROM reconciliation_discrepancies WHERE resolution = 'pending_ambiguity_resolution' AND material_to_review = 1 ORDER BY discrepancy_id ASC LIMIT 1` (oldest first; matches the operator's natural FIFO inclination + the `list-pending-ambiguities` ORDER BY DESC is intentional for CLI scan but oldest-first is more natural for "what needs my attention next"). **The selector's ORDER BY is a brainstorm decision; Codex may push back; document as §16.2.**

### §10.2 Dashboard per-discrepancy entry-point — operator decision item §16.3

Brief §3 #2 raises whether the dashboard surfaces a list of pending discrepancies with per-row "Resolve" buttons. **Brainstorm RECOMMENDS NOT in V1.** Justification:

* The banner link to the first pending is enough for the common case (single unresolved discrepancy).
* The CLI `list-pending-ambiguities` is the authoritative multi-row enumerator and already exists.
* Adding a dashboard table introduces a new VM field on DashboardVM + a new partial template + a new builder helper + a new test surface — scope creep.

Banked as V2 candidate §15.5 (along with the dedicated `/reconcile/pending` list-page surface).

### §10.3 HX-Redirect query-string token — operator decision item §16.4

Per §1.2 LOCK D2, success redirects to `/dashboard?reconcile_resolved={correction_id}`. V1 dashboard does NOT consume the param; it is informational only. **Brainstorm RECOMMENDS leaving it in** so a future V2 toast renderer (banked §15.6) can read it without re-shaping the redirect contract. Adding the param is +3 LOC at the route; removing it later if V2 decides otherwise is +0 LOC change.

### §10.4 HX-Redirect alternate target — operator decision item §16.5

Brief §3 #4 raises whether some discrepancy types should redirect to `/metrics/discrepancies` (which does not exist V1) or `/metrics/capital-friction` or similar instead of `/dashboard`. **Brainstorm RECOMMENDS uniform `/dashboard` redirect** for V1 — matches §1.2 LOCK D2 verbatim, avoids per-type redirect logic, and the dashboard already surfaces the post-resolution state (banner count drops, correction visible via `/trades/{id}` and `/metrics/capital-friction`). V2 candidate §15.9.

---

## §11 Discriminating-example walkthroughs

### §11.1 Happy path — `multi_partial_vs_consolidated` + `keep_journal_as_is`

CVGI fill 9 is in `pending_ambiguity_resolution` with `ambiguity_kind='multi_partial_vs_consolidated'`. Operator clicks banner → `GET /reconcile/discrepancy/{id}/resolve` renders with `keep_journal_as_is [RECOMMENDED]` as the first choice. Operator selects it, types reason "acknowledge Schwab partial-fill aggregation per V1 policy", submits. Service runs the no-mutation handler (per §6.2.1 LOCK), inserts `reconciliation_corrections(action='operator_resolved_ambiguity', applied_by='operator')`, flips `reconciliation_discrepancies.resolution='operator_resolved_ambiguity'` with `resolved_by='operator_web'`. Response: `204 + HX-Redirect: /dashboard?reconcile_resolved=99`. Dashboard re-renders; banner count drops by 1.

### §11.2 Happy path with `--custom-value` — `unsupported` + `operator_truth`

Operator opens a discrepancy with `ambiguity_kind='unsupported'`, selects `operator_truth`, pastes `{"price": 5.23, "quantity": 100, "trade_date": "2026-05-15"}` into the custom-value textarea, types reason. Service handler validates the payload shape, mutates the journal `fills` row, inserts the audit row, flips resolution. Same success response as §11.1.

### §11.3 Validator rejection

Operator picks `consolidate_using_operator_vwap` with `{"price": -1.0}` (negative). Service's `validate_fill_correction` rejects on `math.isfinite` + range check; `ValidatorRejectedError` raised. Route catches → 400 → re-render with `error_band_message='Validator rejected: price must be > 0; received -1.0'`. The operator's typed values are preserved. The operator corrects and resubmits.

### §11.4 JSON parse failure

Operator pastes malformed JSON `{"price": 5.30,}` (trailing comma). `json.loads` raises `JSONDecodeError`. Route catches → 400 → re-render with `error_band_message='Custom value is not valid JSON: Expecting property name enclosed in double quotes: line 1 column 16 (char 15)'`. Operator's typed values are preserved.

### §11.5 Discrepancy already resolved

Operator opens the form at T₁; CLI resolves the same discrepancy at T₂ < T₃ when operator submits. POST handler reads disc → `resolution='operator_resolved_ambiguity'` (terminal) → 409 + error template. Operator returns to dashboard via the template's link.

### §11.6 Choice not in menu (parametric mismatch)

Operator manipulates the form (or browser back-button caching) and submits `choice_code='pick_schwab_record_5'` against a `multi_match_within_window` discrepancy whose `resolution_reason` parses to N=3. Route checks `startswith('pick_schwab_record_')` → True; service dispatch rejects `_resolve_handler_key('multi_match_within_window', 'pick_schwab_record_5')` → returns None → service raises `ValueError('incompatible (ambiguity_kind=...)')` → route 400 → re-render.

### §11.7 Banner click with no pending-ambiguity discrepancies

Banner count is non-zero but reflects only `'unresolved'`-state material discrepancies (pre-Phase-12 reconciliation surface). `vm.banner_resolve_link` is None → banner text renders without a link. Operator's workflow stays CLI. Discriminating test asserts banner DOM contains the count text but NO `<a href>` element.

### §11.8 Sandbox interaction (by-design journal writes)

Under `environment='sandbox'`, manual Tier-2 paths PROCEED normally per the service-layer contract (Phase 12 Sub-sub-bundle C.C lesson: sandbox short-circuit applies to AUTO-redirect paths only — `_apply_tier2_resolution_inner:780` gates the short-circuit on `applied_by_override == "auto"`; web V1 never passes the auto triple, so the gate never fires for web). **The web POST under sandbox WRITES a `reconciliation_corrections` row + WRITES the journal mutation per the chosen handler + flips `reconciliation_discrepancies.resolution`.** This matches the existing CLI `resolve-ambiguity` behavior under sandbox verbatim and is by design — operators run sandbox to test the menu against real journal state.

The discriminating test for this case mocks `cfg.integrations.schwab.environment = 'sandbox'` and asserts the response body + DB shape match production-path behavior (`reconciliation_corrections.applied_by='operator'`, `reconciliation_discrepancies.resolved_by='operator_web'`, journal mutated per the handler). Operator-witnessed gate covers production env only; sandbox covered by test.

### §11.9 Hidden-anchor tamper / drift

Operator opens the form at T₁ (form embeds `ambiguity_kind_at_render='multi_partial_vs_consolidated'`). Hypothetical mid-flight scenario: a future hot-fix re-runs the classifier and the discrepancy's `ambiguity_kind` flips to `'unsupported'` (in V1 this is not a code path the service can reach against an in-flight discrepancy, but the anchor defends defense-in-depth). Operator submits → POST step 3c sees `disc.ambiguity_kind ('unsupported') != ambiguity_kind_at_render ('multi_partial_vs_consolidated')` → 409 with explanatory template. Operator re-opens the form; fresh anchor matches; proceeds. Discriminating tests cover (a) missing anchor → 400; (b) tampered anchor → 409; (c) matching anchor → service flow proceeds.

### §11.10 OriginGuard rejection (defense-in-depth)

A third party sends `POST /reconcile/discrepancy/1/resolve` without the `HX-Request` header. OriginGuard rejects with 403 BEFORE the route handler runs. Discriminating test asserts the form's rendered HTML contains the `hx-headers='{"HX-Request": "true"}'` attribute verbatim (Phase 5 R1 M1 LOCK).

### §11.11 HX-Redirect target unrouted (defense-in-depth)

Discriminating test asserts `/dashboard` is a registered route on `app.routes` (Phase 6 I3 LOCK). The `?reconcile_resolved={correction_id}` query param is informational; the route accepts arbitrary query strings.

---

## §12 Sub-bundle decomposition

**Recommended:** SINGLE sub-bundle. Total scope ≈ 11 tasks; ~+45-75 fast tests; 1 slow E2E.

| Task | Description | Tests |
| --- | --- | --- |
| T-2.1 | New `swing/web/view_models/reconcile.py` with `ReconcileDiscrepancyResolveVM` + sub-VMs + `parse_parametric_pick_count` helper. | +4 |
| T-2.2 | `build_reconcile_discrepancy_resolve_vm` builder + per-type render helpers (§7). | +12 |
| T-2.3 | `swing/web/templates/reconcile_discrepancy_resolve.html.j2` + `..._error.html.j2`. | +0 (template covered via route tests). |
| T-2.4 | New `swing/web/routes/reconcile.py` GET handler. Mount in `swing/web/app.py`. | +6 |
| T-2.5 | POST handler — form-parse + pre-flight checks + service call + error catch-ladder. | +12 |
| T-2.6 | Error templates + 404/409/400/500/503 paths. | +6 |
| T-2.7 | DashboardVM `banner_resolve_link` field + route population + `base.html.j2` banner link + first-pending selector helper. | +5 |
| T-2.8 | Sentinel-leak + XSS-escape audit test + HX-Request propagation regression test + HX-Redirect target route-registration test + form-render hidden anchor tamper/drift regression test (3-case: missing / mismatched / matching). | +6 |
| T-2.9 | `_validate_override_combo` regression test asserting `resolved_by_override='operator_web'` passes validation + audit-row shape parity test (CLI vs web produce same `reconciliation_corrections` row modulo `resolved_by`). | +4 |
| T-2.10 | Slow E2E `test_phase12_5_bundle_2_web_tier2_happy_path.py` — TestClient submits real form, asserts 204 + HX-Redirect, DB state mutated end-to-end. | +1 slow |
| T-2.11 | Cycle-checklist additions + brief deviations / V2 candidates banking + return report. | +0 |

**Estimated worktree time:** 6-10 hours operator-paced including 3-5 Codex rounds.

---

## §13 Test fixture strategy

### §13.1 TestClient discipline

`with TestClient(app) as client:` (enters lifespan; required for any route touching `app.state.cfg` / `app.state.templates`; Phase 5+ project convention).

### §13.2 No Schwab cassettes; pure TestClient + DB seeding

The web Tier-2 form does NOT call Schwab API. Tests seed the database with a `reconciliation_discrepancies` row in `pending_ambiguity_resolution` state plus the upstream rows (`reconciliation_runs`, `fills`, `trades`) needed by the service handler. The fixture-builder helper lives in `tests/web/test_reconcile/conftest.py` with parametrized factory functions per `ambiguity_kind`. No cassette infrastructure needed.

### §13.3 Discriminating-test patterns

| Pattern | Discriminating value |
| --- | --- |
| CLI/web audit-row parity | Plant 2 identical discrepancies; resolve one via CLI runner + one via TestClient. Assert correction rows are byte-identical EXCEPT for the `reconciliation_discrepancies.resolved_by` column (`'operator'` vs `'operator_web'`). |
| HX-Request propagation | Render the form; grep response body for `'hx-headers=\'{"HX-Request": "true"}\''`; assert present. |
| HX-Redirect target route registration | `assert any(r.path == '/dashboard' for r in app.routes)`. |
| `... or None` discipline | Submit with empty `custom_value` form field; if the chosen choice does NOT require custom value, assert service receives `operator_custom_payload=None` (not `""`). |
| Sentinel leak audit | Plant `'X-RECONCILE-SENTINEL'` in `resolution_reason`; assert form-render escapes it as literal text (no `<script>` injection); separately, plant `<script>alert(1)</script>` in `custom_value_raw` re-render path; assert escaped output. |
| Base-layout VM retrofit | Construct `ReconcileDiscrepancyResolveVM` with `session_date='2026-05-18'`; verify it inherits all 7 BaseLayoutVM fields with valid defaults (introspection test pattern from Phase 10 T-A.7). |
| OriginGuard 403 | TestClient POST without `HX-Request` header → 403. With header → service flow proceeds. |
| TOCTOU 409 | Two test threads: thread A opens the form (read disc state); thread B resolves via CLI runner; thread A submits POST → 409. |
| Hidden-anchor tamper / drift | Render form, capture rendered `<input type="hidden" name="ambiguity_kind_at_render" value="...">`. (a) POST with missing anchor → 400. (b) POST with mismatched anchor (manually substitute another kind) → 409. (c) POST with matching anchor → service flow proceeds. Mirrors Phase 9 D R2/R3 hidden-anchor regression-test family verbatim. |
| Parametric-pick regex byte-equivalence | Plant `resolution_reason = "Schwab returned 3 orders within the match window"`; assert web `_parse_parametric_pick_count` returns 3 AND CLI's regex at `cli.py:2291` returns 3; assert byte-identical regex pattern source. Pins drift between the two code paths. |

### §13.4 Pre-existing test-baseline preservation

Worktree baseline: ~4712 fast tests + 3 pre-existing phase8 walkthrough failures + 5 skipped. Phase 12.5 #2 keeps the failures + skipped count UNCHANGED. New tests add to the green count.

---

## §14 Schema impact analysis

### §14.1 Brief §2.7 reconsideration

The dispatch brief §2.7 conjectured that `reconciliation_corrections.surface` might require CHECK widening to admit `'web'`. **The conjecture is unfounded:** `reconciliation_corrections` has NO `surface` column (verified by reading `swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql:39-70`). The column-set is: `correction_id`, `discrepancy_id`, `correction_action`, `correction_choice`, `affected_table`, `affected_row_id`, `field_name`, `pre_correction_value_json`, `source_canonical_value_json`, `applied_value_json`, `operator_truth_value_json`, `applied_at`, `applied_by` (`'auto'`/`'operator'`), `correction_set_id`, `superseded_by_correction_id`, `risk_policy_id_at_correction`, `schwab_api_call_id`, `reconciliation_run_id`, `correction_reason`, `notes`. No surface column.

### §14.2 `schwab_api_calls.surface` is unrelated

The `surface IN ('pipeline', 'cli')` CHECK lives on `schwab_api_calls` (migration `0018_schwab_integration.sql:32`). The web Tier-2 form does NOT write to `schwab_api_calls` — it consumes pre-existing audit rows via the optional `apply_tier2_resolution(schwab_api_call_id=...)` kwarg, which web V1 does NOT pass. **Untouched.**

### §14.3 Surface attribution via existing free-TEXT column

`reconciliation_discrepancies.resolved_by` is free TEXT with no CHECK constraint. CLI's `resolve-ambiguity` leaves `resolved_by_override` unset → `effective_resolved_by` defaults to `'operator'`. Web V1 passes `resolved_by_override='operator_web'` → `'operator_web'` persists. Audit-trail forensic distinguishability is achieved with ZERO schema change.

### §14.4 Verdict

**Schema v19 UNCHANGED.** No new migration. No new `_SURFACE_VALUES` constant. No new dataclass validator. The schema-CHECK + Python-constant + dataclass-validator paired discipline gotcha (CLAUDE.md) does NOT apply — nothing widens.

### §14.5 V2 considerations (banked)

If a future dispatch needs an explicit `surface` column on `reconciliation_corrections` (e.g., to surface "applied via web" in audit listings without parsing `resolved_by`), see V2 candidate §15.10. That would be a v19 → v20 migration adding a single column with CHECK `('cli', 'web')` and would require the full paired-discipline (schema CHECK + dataclass validator + dataclass field) in one atomic task. Not in scope for Phase 12.5 #2.

---

## §15 V2 candidates banked

1. **`/reconcile/correction/{id}/show` audit-chain page** — read-only renderer for an applied correction's full chain (tier-1 → tier-3 supersession). Brief §1.4 V2 candidate. Would unlock HX-Redirect to the show page on resolve success.
2. **One-time success toast on `/dashboard?reconcile_resolved={id}`** — dashboard reads the query param and renders a green band "Correction #{id} applied" then clears via HTMX OOB swap.
3. **Web Tier-3 override surface** — counterpart to `swing journal discrepancy override-correction`. Significantly more scope (override-of-override semantics; chain head detection; operator-truth payload validation).
4. **Web Tier-1 auto-correct undo surface** — quick-undo button for tier-1 corrections. Probably routes through `apply_tier3_override` with `operator_truth_value` set to the prior journal value.
5. **`/reconcile/pending` list page** — multi-row enumerator with per-row Resolve buttons. Replaces banner-link-to-first behavior with a more general list-then-pick flow.
6. **`reconcile_resolved` toast renderer** — see #2 above.
7. **Pipeline-active exclusion on web Tier-2 path** — mirror of the `SchwabPipelineActiveError` discipline. Out of scope V1 because the service-layer does NOT currently enforce pipeline-active exclusion on `apply_tier2_resolution` (only on tier-1 + the Schwab fetch path). If V2 changes service-layer, web inherits automatically.
8. **`schwab_api_call_id` form input on web** — surface the optional back-link in the UI. Operator would need to know the call_id (currently surfaced only in CLI dry-run output). V2 work.
9. **Per-discrepancy-type HX-Redirect targets** — redirect to `/metrics/capital-friction` after a `snapshot_mismatch` resolution, `/trades/{id}` after a fill-related resolution, etc.
10. **Explicit `surface` column on `reconciliation_corrections`** — v19 → v20 migration. Avoids parsing `resolved_by` to distinguish cli/web in audit listings.
11. **Inline HTMX swap UX** — partial-swap dashboard with per-discrepancy resolve panels. Rejected V1 (operator §1.1 LOCK); banked as V2 candidate for operator-driven reconsideration if dedicated-page UX proves friction-inducing.
12. **JS for conditional custom-value input** — currently the spec lands a minimal 12-line inline `<script>` that toggles visibility based on the focused radio's `data-requires-custom-value`. V2 could move this to a shared `static/reconcile.js` if other reconcile surfaces ship.
13. **DRY `_parse_parametric_pick_count` helper** — consolidate the duplicated regex (web VM + CLI) into a single `swing.trades.reconciliation_ambiguity_choices.parse_parametric_pick_count(reason: str) -> int` public function. Deferred V1 to preserve brief §4 OUT-OF-SCOPE preservation of the CLI surface (no behavioral change required but a refactor still touches CLI). V2 dispatch can land both the helper move + the CLI refactor + the existing web import together with byte-equivalence regression.

---

## §16 Operator decision items pending

These surfaced during brainstorm. Brainstorm RECOMMENDS the indicated default for each; operator may countermand via Codex chain or post-brainstorm orchestrator review.

1. **Banner navigation target** (§10.1) — DEFAULT: link to FIRST pending-ambiguity discrepancy resolve form when one exists; render count text WITHOUT link when count > 0 but ZERO pending-ambiguity rows exist.
2. **First-pending selector ORDER BY** (§10.1) — DEFAULT: `discrepancy_id ASC` (oldest first). Diverges from `list-pending-ambiguities` CLI which uses `DESC`. Rationale: "oldest needs attention next" matches operator's FIFO inclination on banner-driven workflow.
3. **Dashboard per-discrepancy list** (§10.2) — DEFAULT: NOT in V1; banked as §15.5.
4. **HX-Redirect query-string token** (§10.3) — DEFAULT: include `?reconcile_resolved={correction_id}`; dashboard does NOT consume V1.
5. **HX-Redirect alternate target** (§10.4) — DEFAULT: uniform `/dashboard`; per-type targets banked §15.9.
6. **JS posture for custom-value toggle** (§6) — DEFAULT: 12-line inline `<script>` in the template; custom-value fieldset always rendered; JS is UX nicety only. Server enforces requirement.
7. **`_parse_parametric_pick_count` helper location** (§5.4) — DEFAULT: NEW private module-level function in `swing/web/view_models/reconcile.py` that DUPLICATES the regex byte-for-byte from `cli.py:2291`. CLI surface stays AS-IS per brief §4 OUT-OF-SCOPE preservation lock. Discriminating regression test plants the same `resolution_reason` text in both code paths and asserts byte-identical N. DRY consolidation (move helper into `swing/trades/reconciliation_ambiguity_choices.py` + refactor CLI to consume it) is banked as V2 candidate §15.13.
8. **Operator-witnessed gate surface count** (§17.1) — DEFAULT: 6 surfaces (S1 inline pytest + ruff; S2 banner-link navigation; S3 form-render with context; S4 successful POST + HX-Redirect; S5 banner-clears post-resolve; S6 CLI/web parity end-to-end). S7 (error path) covered by tests; can be promoted to operator gate if any concerns surface.

---

## §17 Operator-witnessed gate plan

Default 6 surfaces (per §16.8). Plan:

* **S1** — inline pytest `-m "not slow" -n auto` (expect ~4757 green: 4712 baseline + ~45 new) + `ruff check swing/` (expect 18 E501 unchanged) + 1 slow E2E `test_phase12_5_bundle_2_web_tier2_happy_path.py` GREEN.
* **S2** — start `swing web --port 8081` from worktree; visit `/dashboard` with at least one pending-ambiguity discrepancy seeded; assert banner text contains an `<a>` link to the resolve form for the seeded discrepancy.
* **S3** — navigate to the resolve form; assert pre-resolution context section renders correctly per §7 mapping for the seeded discrepancy_type; assert all menu items render with `requires_custom_value` markers + recommended badge where applicable; assert ZERO console errors.
* **S4** — submit a `keep_journal_as_is` resolution (no payload required); assert 204 response + HX-Redirect to `/dashboard?reconcile_resolved={id}`; assert browser navigates; assert `reconciliation_corrections` row inserted with `applied_by='operator'` + `correction_action='operator_resolved_ambiguity'`; assert `reconciliation_discrepancies.resolved_by='operator_web'`.
* **S5** — confirm dashboard banner count drops by 1; if no other pending-ambiguity rows exist, banner suppressed entirely.
* **S6** — separately resolve a second seeded discrepancy via CLI `swing journal discrepancy resolve-ambiguity <id> --choice keep_journal_as_is --reason 'test'`; query `SELECT resolved_by FROM reconciliation_discrepancies WHERE discrepancy_id=...`; assert `'operator'` (CLI) vs `'operator_web'` (web) distinguishable.

ASCII-only banner text on S5 + S6 verification (Phase 12 C.D gate-fix #3 inheritance).

---

*End of spec. Phase 12.5 #2 brainstorm-locked architectural surface: 1 GET + 1 POST route + 1 VM module + 2 templates + 1 base-layout retrofit + 1 helper extraction. Schema v19 UNCHANGED. CLI preserved AS-IS. Surface attribution via existing `resolved_by_override` kwarg. ~+45-75 fast tests + 1 slow E2E. 3-5 Codex rounds projected.*
