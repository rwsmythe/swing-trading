# Phase 10 plan — electives amendment (operator decisions 2026-05-13)

**Parent plan:** [`docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`](superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md) (HEAD `a34c00d`).
**Trigger:** orchestrator triage of 5 elective items flagged in plan §A.4 + return-report §5; operator decision relayed 2026-05-13 post-merge.
**Scope:** propagates 4 elections into Sub-bundles B, C, E (4 new tasks); banks §8.4 as standalone post-Phase-10 dispatch.

This amendment is a NORMATIVE supplement to the plan §A.4 dispositions + §E + §F + §H task lists. Sub-bundle dispatch briefs for B/C/E MUST consume this document alongside the parent plan. Sub-bundle A is UNAFFECTED — no electives touch A's scope.

---

## §1 Operator decisions

| # | Item | Default in plan §A.4 | **Operator decision 2026-05-13** | Implementation |
|---|---|---|---|---|
| 1 | §8.2 web-form manual `account_equity_snapshot` capture | NO (CLI-only) | **ELECTED** | New Task **E.5** in Sub-bundle E |
| 2 | §8.4 Corporate_Actions MVP | DEFER (Phase 10+ follow-up) | **DEFER AS STANDALONE POST-PHASE-10 DISPATCH** — see `docs/phase3e-todo.md` 2026-05-13 entry | Out of Phase 10 V1 scope; preserves §A.0 ZERO-new-schema lock |
| 3 | §8.6 surface `lucky_violation_R` on Phase 6 review form | DEFER (standalone follow-up) | **ELECTED** | New Task **B.7** in Sub-bundle B |
| 4 | §0.5 §11.2 (b) per-trade reconciliation discrepancy indicator on trade detail page | DEFER (Phase 10+ follow-up) | **ELECTED** | New Task **E.6** in Sub-bundle E |
| 5 | §0.5 §11.2 (c) per-cohort "exclude trades with unresolved discrepancies" filter | DEFER (Phase 10+ follow-up) | **ELECTED** | New Task **C.5** in Sub-bundle C |

**Items §8.1 / §8.3 / §8.5 / §8.7 / §11.2(a) / §11.3 V1 supersession / §11.4 dynamic PROVISIONAL contract** — plan §A.4 defaults preserved (no operator override).

**§A.0 ZERO-new-schema LOCK PRESERVED** across all 4 elections — every new task uses existing v17 tables. `EXPECTED_SCHEMA_VERSION` stays at 17.

---

## §2 New task specifications

### Task B.7 — `lucky_violation_R` on Phase 6 review form (§8.6 election)

**Sub-bundle:** B (Trade-process card + Hypothesis-progress card)
**Scope:** modifies existing route `GET /reviews/{id}/complete` + template (`swing/web/templates/review.html.j2`). NO new Phase 10 surface; touches the Phase 6 review surface.
**Est. impl:** ~1-2hr executing-plans.
**Schema impact:** ZERO — `lucky_violation_R` is already computed at `swing/trades/review.py:compute_lucky_violation_R` (Phase 6) + persisted on `review_log.total_lucky_violation_R`. Both per-trade derived + cohort-aggregate are available.

**Acceptance criteria:**
- `ReviewVM` (existing at `swing/web/view_models/trades.py:651`) gains a derived `lucky_violation_R_display: float | None` field surfacing the per-trade computed value (NOT the review_log aggregate — that's already on the cohort surfaces). Field is computed from the trade's `realized_R_if_plan_followed` + `actual_realized_R_effective` at VM build time via the existing helper.
- `review.html.j2` template renders the field symmetrically alongside the existing `mistake_cost_R` display: same label-row + numeric-cell pattern; field labeled "Lucky violation (R)" with the same precision (2 decimal places) as `mistake_cost_R`.
- Suppression: when both `mistake_cost_R` and `lucky_violation_R` are 0 (plan-followed-exactly), render "—" placeholder for both (current Phase 6 behavior for the mistake field; symmetric for lucky).
- TestClient regression: `tests/web/test_routes/test_review_complete_form.py` extends existing test fixture with a trade that has `realized_R_if_plan_followed > actual_realized_R_effective` (mistake-cost positive) + a separate trade with `actual_realized_R_effective > realized_R_if_plan_followed` (lucky-violation positive); assert template rendering surfaces both values.

**Watch items:**
- Existing review form is operator-witnessed-gate-validated as of Phase 6 ship (`51c79ed`). Task B.7's gate surface = re-verify the review form still loads + the new field renders + the existing mistake-cost field is unaffected. Add as gate surface S3 in Sub-bundle B operator-witnessed gate (Sub-bundle B already has 2 gate surfaces per return-report §4; this brings to 3 — still under the ≤6 budget).
- The Phase 10 spec §7.4 + §8.6 open question framed this as a small standalone follow-up; bundling into Sub-bundle B is operator's election, NOT a spec deviation.

**Cross-bundle pin:** none (purely additive to a pre-Phase-10 surface).

---

### Task C.5 — Per-cohort "exclude trades with unresolved discrepancies" filter (§11.2(c) election)

**Sub-bundle:** C (Tier-comparison + Deviation-outcome)
**Scope:** adds a per-cohort filter toggle that excludes trades with unresolved material reconciliation discrepancies from cohort aggregates. Surface lives on the tier-comparison + deviation-outcome views (Sub-bundle C scope); helper is reusable in Sub-bundle B's trade-process card + Sub-bundle D's surfaces (V2 candidate per plan §A.11.1 paused-interval analog).
**Est. impl:** ~1-2hr executing-plans.
**Schema impact:** ZERO — `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + closed-trade companion are already shipped (Phase 9 Sub-bundle B). Task adds a filter helper consuming these.

**Acceptance criteria:**
- New helper `swing/metrics/cohort.py:filter_trades_without_unresolved_material_discrepancies(conn, trades) -> list[Trade]` returns the subset of trades that have ZERO unresolved material discrepancies. Single-query: SELECT `trade_id` from `reconciliation_discrepancies` WHERE `material_to_review=1 AND resolution IS NULL`; exclude those `trade_id`s.
- `CohortFilter` enum extended (or new bool param) in tier + deviation VMs: `exclude_unresolved_discrepancies: bool = False` (default OFF; operator opts in via query string `?exclude_discrepancies=1`).
- Route handlers for `GET /metrics/tier-comparison` + `GET /metrics/deviation-outcome` accept the query parameter + thread it through to VM construction.
- Template renders a toggle link/checkbox: `<a href="/metrics/tier-comparison?exclude_discrepancies=1">Hide trades with unresolved discrepancies</a>` (or HTMX-OOB toggle if cleaner; static-render is acceptable per spec §4.9 "No client-side compute").
- TestClient regression: `tests/metrics/test_cohort_filter.py` covers (a) helper returns full list when no discrepancies; (b) helper excludes trades with unresolved material discrepancies; (c) helper INCLUDES trades whose discrepancies are resolved (resolution NOT NULL); (d) helper INCLUDES trades whose discrepancies are non-material (material_to_review=0); (e) route handler with `?exclude_discrepancies=1` produces a smaller cohort denominator than without; (f) suppression-text formatting includes "(excluded N trades with unresolved discrepancies)" when filter is active.

**Watch items:**
- When filter is active and reduces cohort sample size below the §5 suppression threshold, the metric must re-suppress per the smaller `n`. Discriminating test: seed cohort with 5 closed trades + 3 of them have unresolved material discrepancies → filter brings cohort to n=2 → assert suppression (n<3 per Class A).
- Operator-witnessed gate surface: add to Sub-bundle C's gate as S3 (covers the toggle UI working in browser + filter reduces cohort visibly). Sub-bundle C goes from 2 to 3 gate surfaces.
- V2 candidate banked at end of this amendment: extend the helper to support the spec §A.11.1 "exclude trades stamped during paused intervals" filter family — same UI shape, same VM pattern.

**Cross-bundle pin:** none in V1 (helper is shared but each VM constructs independently).

---

### Task E.5 — Web-form manual `account_equity_snapshot` capture (§8.2 election)

**Sub-bundle:** E (Process-grade-trend + Reconciliation badge + Phase 11 hand-off)
**Scope:** adds a web-form surface at `GET /account/snapshot` + `POST /account/snapshot` for manual snapshot capture. Complements the existing `swing account snapshot record` CLI (Phase 9 Sub-bundle C).
**Est. impl:** ~1-2hr executing-plans (revised from plan §A.4's ~30min — server-stamping discipline + transactional service + HTMX failure-surface testing surface area justifies the bump).
**Schema impact:** ZERO — `account_equity_snapshots` table + `swing/trades/account_equity_snapshots.py` service (Phase 9 Sub-bundle C) are shipped.

**Acceptance criteria:**
- New `GET /account/snapshot` route renders form template (`swing/web/templates/account_snapshot_form.html.j2`) with fields: `equity_dollars` (numeric input), `snapshot_date` (display-only — server-computed `last_completed_session(datetime.now())` per Phase 8 hidden-field server-stamping discipline; rendered as `<span class="muted">`), optional `note` field. Form action POSTs to `/account/snapshot`.
- POST handler at `/account/snapshot`:
  - Server-stamps `snapshot_date = last_completed_session(datetime.now())` + `recorded_at = datetime.now(timezone.utc)` at handler entry (per Phase 8 R2/R3/R4 + Phase 9 forward-binding lesson §0.3 #4).
  - Calls `swing/trades/account_equity_snapshots.py:record_snapshot_with_audit` (Phase 9 Sub-bundle C; existing service that owns BEGIN IMMEDIATE / COMMIT / ROLLBACK per Phase 9 transactional discipline + reject-caller-held-tx).
  - Per Phase 9 Sub-bundle D R3 lesson: NO hidden form anchors required (this form has no POST-time validation against form-render-time state; the snapshot_date is server-stamped at POST not form-render).
  - Returns `204 No Content` with `HX-Redirect: /metrics/capital-friction` header (per Phase 5 R1 M2 HX-Redirect-vs-303-swap lesson + Phase 6 I3 HX-Redirect-target-unrouted lesson — target route `/metrics/capital-friction` MUST be registered by Sub-bundle D landing).
- TestClient regression coverage:
  - `tests/web/test_routes/test_account_snapshot_form.py` covers (a) GET renders form with display-only snapshot_date; (b) POST with valid `equity_dollars` server-stamps snapshot_date + recorded_at + returns 204 + HX-Redirect; (c) POST with caller-supplied snapshot_date is IGNORED (server-stamp wins; tampering surface closed); (d) POST with malformed `equity_dollars` returns 400 + form re-renders with error; (e) HX-Redirect target route resolves to 200 (assert via second TestClient call or route-table check per Phase 6 I3 lesson).
- USERPROFILE+HOME monkeypatch NOT required (this form does not exercise `swing/config_user.py:write_user_overrides` — it writes to `account_equity_snapshots` table directly).

**Watch items:**
- Operator-witnessed gate surface S4 in Sub-bundle E (in addition to the existing 1 surface + 1 banner integration; Sub-bundle E goes from 1 surface + 1 banner to 3 surfaces + 1 banner). Per dispatch brief §1.3 ≤6-surface budget — still under.
- HTMX browser-only failure modes per CLAUDE.md gotcha family — operator-witnessed gate is BINDING. Pre-empt: (a) `hx-headers='{"HX-Request": "true"}'` on form element if rendered inside OriginGuard strict-mode context; (b) HX-Redirect target route `/metrics/capital-friction` registered by Sub-bundle D landing; (c) no `<tr>`-leading response (form returns 204 with no body).
- Snapshot source defaults to `'manual'` per Phase 9 spec source-ladder semantics.

**Cross-bundle pin:** depends on Sub-bundle D landing the `/metrics/capital-friction` route (HX-Redirect target). Sub-bundle E ordering MUST follow D per the plan's locked A→B→C→D→E ordering — already satisfied.

---

### Task E.6 — Per-trade reconciliation discrepancy indicator on trade detail page (§11.2(b) election)

**Sub-bundle:** E (Process-grade-trend + Reconciliation badge + Phase 11 hand-off)
**Scope:** adds a per-trade reconciliation discrepancy indicator to the existing trade detail page (`GET /trades/{id}/detail`, shipped in Phase 8 V1 polish at `24b3e9a`).
**Est. impl:** ~1-2hr executing-plans.
**Schema impact:** ZERO — `reconciliation_discrepancies` table + `swing/data/repos/reconciliation.py` helpers (Phase 9 Sub-bundle B) are shipped.

**Acceptance criteria:**
- New helper `swing/metrics/discrepancies.py:list_unresolved_material_for_trade(conn, trade_id) -> list[Discrepancy]` returns discrepancies WHERE `trade_id=? AND material_to_review=1 AND resolution IS NULL`. Reuses Phase 9 Sub-bundle B repo helpers — does NOT duplicate query.
- Existing `TradeDetailVM` (or equivalent at `swing/web/view_models/trades.py`) gains `unresolved_material_discrepancies: list[DiscrepancyDisplay]` field. Field type is a frozen dataclass with `type`, `field_name`, `expected`, `actual`, `period_end`, `material` for display.
- Trade detail template (`swing/web/templates/trades/detail.html.j2` or equivalent) renders a discrepancy indicator section when the field is non-empty: ⚠ badge alongside trade header + collapsible section listing the discrepancies (using HTML5 `<details>`/`<summary>` per Phase 3e.7 precedent at `44ac760`).
- Indicator hides entirely when no unresolved material discrepancies exist for the trade (cleanest no-op rendering).
- TestClient regression coverage:
  - `tests/web/test_routes/test_trade_detail_discrepancy_indicator.py` covers (a) trade with zero discrepancies → no indicator section in response; (b) trade with 1 unresolved material discrepancy → indicator renders with type/field/expected/actual; (c) trade with 1 RESOLVED material discrepancy → no indicator (resolution clears it); (d) trade with 1 NON-material discrepancy → no indicator (material_to_review=0 clears it).

**Watch items:**
- Operator-witnessed gate surface S5 in Sub-bundle E (Sub-bundle E now has 3 surfaces + 1 banner: T-E.5 snapshot form, T-E.6 trade detail indicator, existing T-E.2 process-grade-trend; banner is T-E.3 global discrepancy badge). Still under ≤6 budget.
- Composition with the global discrepancy badge (Task E.3): the global badge counts ALL unresolved material discrepancies; the per-trade indicator counts only trade-specific ones. Sum of per-trade counts ≤ global count (any unresolved discrepancies NOT attributed to a trade — orphan emit per Phase 9 Sub-bundle B + E — are in global but not per-trade).

**Cross-bundle pin:** none.

---

## §3 Updated decomposition shape

| Sub-bundle | Task count (was) | Task count (now) | New tasks | Gate surfaces (was) | Gate surfaces (now) | Est. dispatch hr |
|---|---:|---:|---|---:|---:|---|
| A | 10 | 10 | — | 1 | 1 | 6-9 |
| B | 7 | **8** | + T-B.7 | 2 | **3** | 8-12 + ~1-2hr |
| C | 5 | **6** | + T-C.5 | 2 | **3** | 6-10 + ~1-2hr |
| D | 8 | 8 | — | 3 + 1 flip | 3 + 1 flip | 8-12 |
| E | 5 | **7** | + T-E.5 + T-E.6 | 1 + 1 banner | **3 + 1 banner** | 6-9 + ~2-4hr |
| **Total** | **33** | **39** | **+4** | **9 + 1 banner** | **13 + 1 banner** | **34-52 + ~4-8hr** |

**Test projection updated:** plan §1.2 projected +180..+285 fast tests; electives add ~18-31 tests (B.7: +3-5; C.5: +5-8; E.5: +5-10; E.6: +5-8). **New projection: +198..+316 fast tests** across the arc; final ~2965..~3083.

**Per-bundle gate session ≤ 6 surfaces budget** (dispatch brief §1.3): all 5 bundles still fit one operator gate session each; Sub-bundle E moves from 1 surface + 1 banner to 3 surfaces + 1 banner — closest to the ceiling but well under.

---

## §4 §A.0 ZERO-new-schema lock preserved

All 4 electives use existing v17 tables + helpers:
- T-B.7: existing `swing/trades/review.py:compute_lucky_violation_R` + `review_log.total_lucky_violation_R`.
- T-C.5: existing `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + closed-trade companion.
- T-E.5: existing `account_equity_snapshots` table + `swing/trades/account_equity_snapshots.py:record_snapshot_with_audit`.
- T-E.6: existing `reconciliation_discrepancies` table + Sub-bundle B repo helpers.

**`EXPECTED_SCHEMA_VERSION` stays at 17.** **No `0018_*.sql` migration in Phase 10 V1.** Plan §A.0 LOCK preserved.

---

## §5 §8.4 Corporate_Actions deferral — banked as standalone post-Phase-10 dispatch

Operator decision 2026-05-13: §8.4 Corporate_Actions MVP DEFERS to standalone post-Phase-10 dispatch. Preserves §A.0 ZERO-new-schema lock + Phase 10 arc shape (5 sub-bundles A→B→C→D→E, 39 tasks).

Banked at `docs/phase3e-todo.md` 2026-05-13 entry. Standalone dispatch will use its own brainstorm + writing-plans + executing-plans cycle since the schema work (new `corporate_actions` table + `0018_*.sql` migration + CLI surface + manual reconcile flow) merits independent Codex rigor. Phase 9 Sub-bundle A precedent: schema-introducing bundles get their own scoped review.

Sequencing post-Phase-10: §8.4 standalone is ONE of several Phase 11 candidates surfaced in plan §10 hand-off + return-report §10. Orchestrator + operator triage Phase 11 scope after Phase 10 V1 ships.

---

## §6 §A.4 disposition table — amended

Replaces the corresponding rows in plan §A.4 (line 152-165). Other dispositions UNCHANGED:

| Question | Plan §A.4 default | **Amended 2026-05-13** | Implementation |
|---|---|---|---|
| §8.2 web-form manual snapshot capture | NO — CLI-only | **YES — ELECTED** | Task **E.5** |
| §8.4 Corporate_Actions MVP | DEFER (Phase 10+ follow-up) | **DEFER AS STANDALONE POST-PHASE-10 DISPATCH** | Out of scope; see `phase3e-todo.md` 2026-05-13 |
| §8.6 surface `lucky_violation_R` on Phase 6 review form | DEFER (standalone follow-up) | **YES — ELECTED** | Task **B.7** |
| §11.2(b) per-trade discrepancy indicator | DEFER (Phase 10+ follow-up) | **YES — ELECTED** | Task **E.6** |
| §11.2(c) per-cohort "exclude trades with unresolved discrepancies" filter | DEFER (Phase 10+ follow-up) | **YES — ELECTED** | Task **C.5** |

---

## §7 Watch items + V2 candidates

1. **§A.11.1 paused-interval filter family** — T-C.5 establishes the "per-cohort exclusion toggle" UI pattern. The same pattern is needed for the spec §A.11.1 V2 candidate "Exclude trades stamped during paused intervals" filter. Future dispatch may reuse T-C.5's helper signature + UI shape. Banked.

2. **T-E.5 source-ladder default** — Phase 9 Sub-bundle C spec §A.9 source ladder is `schwab_api > tos_csv > manual`. T-E.5 web-form writes `source='manual'`. Future Schwab API integration (Phase 11 candidate) would write `source='schwab_api'` and outrank manual snapshots at the source-ladder. Operator-paced.

3. **T-E.6 orphan-discrepancy attribution** — Phase 9 Sub-bundle B's per-run dedup allows orphan emits (discrepancies not attributed to a specific trade_id). Global discrepancy badge (T-E.3) counts these; per-trade indicator (T-E.6) does NOT (orphans have no trade_id). The sum of per-trade indicator counts ≤ global badge count when orphans exist. Banked as V2 candidate: "orphan discrepancy detail page" surfacing trade-less discrepancies.

4. **T-B.7 vs spec §8.6 standalone-dispatch suggestion** — Phase 10 spec §8.6 framed `lucky_violation_R` surface as a standalone-follow-up dispatch. Bundling into Sub-bundle B is operator's election; if scope creep emerges (e.g., a "review_log surface refactor" pulls in more than the single-field add), Sub-bundle B implementer should flag back to orchestrator rather than expand scope inline. Watch item.

5. **Sub-bundle E gate-surface ceiling** — Sub-bundle E now has 3 surfaces + 1 banner = closest to the ≤6-surface budget. If operator elects further additions during integration triage of Sub-bundle E's dispatch brief, consider splitting Sub-bundle E into E.1 (process-grade-trend + reconciliation badge) + E.2 (web-form snapshot + per-trade indicator + Phase 11 hand-off). Not a current concern.

---

## §8 Forward-binding lessons re-application checklist

The 4 elective tasks each MUST respect the Phase 9 arc forward-binding lessons (dispatch brief §0.3 + §7). Per-task applicability:

| Lesson | T-B.7 | T-C.5 | T-E.5 | T-E.6 |
|---|---|---|---|---|
| `__post_init__` validators | N/A (no new dataclass) | N/A | YES (`DiscrepancyDisplay` if introduced) | YES (`DiscrepancyDisplay`) |
| Service-layer transaction discipline | N/A (read-only) | N/A (read-only) | **YES** (uses existing `record_snapshot_with_audit`) | N/A (read-only) |
| NO `INSERT OR REPLACE` | N/A | N/A | N/A (service uses INSERT) | N/A |
| Server-stamping discipline at handler entry | N/A (no form) | N/A (no form) | **YES** (`snapshot_date` + `recorded_at`) | N/A |
| Composition-surface enumeration via `^def` grep | N/A | YES (helper signature) | YES (route handler + service surfaces) | YES (helper signature) |
| Empirical-verification of brief assertions | YES (verify `lucky_violation_R` already in Phase 6 code) | YES (verify Phase 9 helpers) | YES (verify service contract) | YES (verify Phase 9 helpers) |
| Form-render hidden anchors round-trip | N/A | N/A | N/A (no hidden anchors) | N/A |
| POST-time recompute TOCTOU | N/A | N/A | N/A (server-stamps at handler entry) | N/A |
| Test fixtures USERPROFILE+HOME monkeypatch | N/A | N/A | N/A (writes to DB not user-config) | N/A |
| HTMX browser-only failure surfaces | YES (existing form regression check) | YES (toggle UI gate) | **YES** (HX-Redirect target route + form propagation) | YES (page render gate) |
| `<tr>`-leading HTMX response | N/A | N/A | N/A (204 no body) | N/A |
| matplotlib mathtext | N/A | N/A | N/A | N/A |
| Migration filename collision | N/A | N/A | N/A | N/A |

T-E.5 is the highest-risk task in this amendment (form-driven write path; HTMX failure-surface budget hit); the other 3 are read-side / template-only modifications with lower failure-surface budget.

---

## §9 Dispatch order — UNCHANGED

A → B → C → D → E. Sub-bundle A executing-plans dispatch UNBLOCKED + the next orchestrator action. Electives propagate at Sub-bundle B/C/E dispatch brief drafting time.

---

*End of electives amendment. Parent plan at `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` REMAINS NORMATIVE; this amendment SUPPLEMENTS §A.4 + §E + §F + §H. Sub-bundle A dispatch brief draws from parent plan only (no elective tasks in A).*
