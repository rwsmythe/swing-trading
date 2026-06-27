# Phase 9 Sub-bundle D — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-bundle D (sector/industry tamper hardening) of the Phase 9 implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` §G (4 tasks T-D.0 … T-D.3). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper informed by Sub-bundle A + B + C landings, NOT a duplicate spec.

**Expected duration:** ~4-7 hr implementation + ~1-2 hr Codex convergence. Total ~5-9 hr. Sub-bundle D is the smallest of the consumer-side bundles — 4 tasks against route-layer extension + ad-hoc reconciliation emit; no new schema, no new service module.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-bundle D (`PLAN_PATH=docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`, `SCOPE=Sub-bundle D (T-D.0..T-D.3 only)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 4 tasks land. Expected **2-3 Codex rounds** (smaller scope than B's 5 + C's 3; route-layer + audit-emit only).

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (2257 lines; Codex R5 confirmation; LOCKED at `a0c7223`).
- **Sub-bundle D section:** §G (lines 1952-2046). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §A resolved-during-planning items:** lines 13-216 — several BINDING for Sub-bundle D (§A.4 sector/industry tamper hardening route-layer integration; §A.4.1 ad-hoc reconciliation_run emission semantics; §A.8 NO `INSERT OR REPLACE`; §A.10 server-stamping discipline).
- **Plan §B file-map:** lines 218-282. Sub-bundle D's file map: MODIFY `swing/web/routes/trades.py` + add `tests/web/test_trade_entry_sector_industry_tamper.py`.
- **Plan §C decomposition (line 293):** Sub-bundle D depends on Sub-bundle A (migration landed; `risk_policy` seed + CHECK enum on `reconciliation_discrepancies.discrepancy_type` includes `sector_tamper`) + Sub-bundle B (`reconciliation_runs.source='system_audit'` CHECK enum value + `swing/data/repos/reconciliation.py:insert_run` + `insert_discrepancy` repo entry points + `MATERIAL_BY_TYPE['sector_tamper'] = 0` constant). NO migration edits.
- **Plan §I watch items (lines 2116-2140):** cross-bundle invariants the executing-plans dispatcher MUST verify (items 1-13 all apply; items 3, 6, 7, 8, 9, 10, 11 are Bundle-D-specific bindings).

### §0.2 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; LOCKED at `31ee51c`).
- **Read §7 sector/industry tamper hardening (BINDING — Phase 9 extends chart_pattern hardening pattern from `swing/web/routes/trades.py` commits `117dc97` + `2b9d6f3`).**
- **Read §3.3.1 expected_value/actual_value JSON shape for `sector_tamper` discrepancy type (BINDING — emitter must produce this shape).**
- **Read §3.2 reconciliation_runs `source` enum (BINDING — includes `'system_audit'` for ad-hoc audit runs).**

### §0.3 Project state at dispatch time
- **HEAD on `main`:** `26e1854` at brief-commit time (post-Sub-bundle-C-merge `e5d5892` + housekeeping). After this brief commits, the worktree-branching-point is the brief commit SHA.
- **Test count:** **2741 fast (5 skipped — 4 implementer SKIP-on-absent for `thinkorswim/*.csv` in worktree; 1 prior); 3 pre-existing failures** on `tests/integration/test_phase8_pipeline_walkthrough.py` ("archive returned None"). NOT regressions; NOT Bundle-D-introduced. Banked for separate triage.
- **Ruff baseline:** **18 (E501 only).** Unchanged from Sub-bundle A + B + C baseline.
- **Schema version:** **v17 (Phase 9 Sub-bundle A migration; consumer-side at v17 since 2026-05-12).** Production DB at `%USERPROFILE%/swing-data/swing.db` already has all Phase 9 tables. **Sub-bundle D does NOT bump the schema_version.**
- **Active risk_policy:** `policy_id=4`. Sub-bundle D tests SHOULD NOT depend on a specific policy_id; instead query `read_active_policy(conn)` from `swing/trades/risk_policy.py`.
- **Production reconciliation state:** 2 reconciliation_runs (run #1 from Bundle B gate; run #2 from Bundle C gate); 11 reconciliation_discrepancies all resolved as `acknowledged_immaterial`. NOT touched by Bundle D.
- **Production account_equity_snapshots:** 2 rows (snapshot #1 $2000 manual 2026-05-11; snapshot #2 $1800 manual 2026-04-01). NOT touched by Bundle D.
- **Production hypothesis_status_history:** 4 seed rows + history from Sub-bundle C gate's id=2 (Near-A+) 3-transition cycle (active → paused → active → identity). NOT touched by Bundle D.
- **Worktree husks pending operator cleanup-script:** 6 (3e8-bundle-3 + phase9-bundle-A + phase9-bundle-B + phase9-bundle-C + phase9-writing-plans + polish-2026-05-10). Does NOT block dispatch.

### §0.4 Sub-bundle D scope (4 tasks)

Per plan §G + plan §C decomposition table:

| Task | Title | Key files |
|---|---|---|
| **T-D.0** | Existing chart_pattern hardening recon (read + summarize commits `117dc97` + `2b9d6f3` at `swing/web/routes/trades.py`); NO code change | (recon-only commit; in-plan documentation note) |
| **T-D.1** | Route-layer sector/industry rejection + tamper test fixtures (mirror chart_pattern hardening pattern at entry POST handler; HTMX-friendly error fragment on mismatch) | MODIFY `swing/web/routes/trades.py`; NEW `tests/web/test_trade_entry_sector_industry_tamper.py` |
| **T-D.2** | Ad-hoc `system_audit` reconciliation_run emission on rejection (SEPARATE transaction from rejected entry POST; INSERT run + INSERT sector_tamper discrepancy) | MODIFY `swing/web/routes/trades.py`; extend `tests/web/test_trade_entry_sector_industry_tamper.py` |
| **T-D.3** | E2E integration test for sub-bundle D scope (tamper-attempt entry → HTMX rejection → audit row persists → discrepancy visible via `swing journal discrepancy list`) | MODIFY `tests/integration/test_phase9_end_to_end.py` |

**Cross-bundle dependencies:** depends on Sub-bundle A (migration; `reconciliation_runs.source='system_audit'` + `reconciliation_discrepancies.discrepancy_type='sector_tamper'` CHECK enums in place) + Sub-bundle B (`swing/data/repos/reconciliation.py:insert_run` + `insert_discrepancy` repo functions + `MATERIAL_BY_TYPE['sector_tamper'] = 0` constant). Independent of Sub-bundle C/E. **NO migration edits.**

### §0.5 BINDING contracts from plan §A + Sub-bundle A/B/C landings (DO NOT re-litigate)

1. **Migration 0017 is LOCKED + FROZEN.** Sub-bundle D DOES NOT modify it. `EXPECTED_SCHEMA_VERSION = 17` is in `swing/data/db.py`. Sub-bundle D ships route-layer extension + tests on top. Discriminating watch item: `grep -E "^EXPECTED_SCHEMA_VERSION" swing/data/db.py` returns `17` post-Bundle-D.

2. **Mirror the chart_pattern hardening pattern.** Per plan §A.4 + spec §7: Phase 9 extends the same entry POST handler at `swing/web/routes/trades.py` with sector + industry rejection. Implementer MUST grep + summarize the chart_pattern hardening at commits `117dc97` + `2b9d6f3` in T-D.0 BEFORE writing the extension. The shape: (a) lookup cached candidate by `(ticker, action_session)`; (b) reject the POST if form-submitted field doesn't match cached; (c) return HTMX-friendly error fragment. Sector + industry follow the same pattern, with TWO discrete tests (sector mismatch + industry mismatch as separate code paths).

3. **Ad-hoc reconciliation_run emission semantics** per plan §A.4.1: on tamper rejection, open a **SEPARATE TRANSACTION** (NOT the rejected entry's transaction — entry POST is rejected, its transaction does NOT commit; the audit row commits separately). INSERT reconciliation_run row with `source='system_audit'`, `state='completed'`, `period_start=period_end=action_session_for_run(now())`. INSERT `sector_tamper` discrepancy with `expected_value_json` + `actual_value_json` per spec §3.3.1, `material_to_review=0` V1 (advisory per spec §3.3.2 + plan §A.4). **Discriminating regression test (T-D.2 step 5):** after rejection, assert `reconciliation_runs` has +1 row AND `reconciliation_discrepancies` has +1 row of type `sector_tamper`.

4. **Bundle B's `swing/trades/reconciliation.py:run_tos_reconciliation` is NOT called by Bundle D.** Bundle D uses the REPO-level entry points directly (`insert_run` + `insert_discrepancy`) per Bundle B return report §10 #1 + Bundle C return report §10 #6. Bundle B's service is `source='tos_csv'` only; Bundle D's ad-hoc audit run is `source='system_audit'`.

5. **`material_to_review = 0` for `sector_tamper`** per spec §3.3.2 + `MATERIAL_BY_TYPE['sector_tamper'] = 0` constant in `swing/trades/reconciliation.py` (Bundle B). Operator override path exists via `swing journal discrepancy resolve <id> --material 1` if needed; V1 default is advisory-only. Bundle D's emitter MUST use the `MATERIAL_BY_TYPE` lookup (NOT hand-set 0 inline) — Bundle B's Codex R1 M#2 hardening discipline.

6. **The rejection itself is the operator-facing signal, NOT a permanent block.** Spec §7 + plan §A.4 are explicit: V1 V1 V1 advisory hard-gate (rejection prevents the entry creation) — but the operator can resubmit with the corrected sector/industry. Bundle D does NOT add a CLI override path; operator's recourse is to update the cached candidate's sector/industry via the existing pipeline OR re-submit with the original cached value. V2 may add a CLI-override path.

7. **No `INSERT OR REPLACE` anywhere in Bundle D.** Plan §A.8 baseline. Audit-run INSERT uses pure `insert_run` (Bundle B repo). Discriminating watch item: `grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/` post-Bundle-D returns zero matches.

8. **Bundle B's `MATERIAL_BY_TYPE` + `DISCREPANCY_TYPES` + `RESOLUTION_TYPES` constants are LOCKED** — Bundle D MUST NOT modify them. `sector_tamper` is already in `DISCREPANCY_TYPES` + `MATERIAL_BY_TYPE['sector_tamper'] = 0` per Bundle B's existing setup.

9. **No new HTMX form-driven SUCCESS paths in Bundle D** (the entry POST already has its success path; tamper is a NEW REJECTION path). The rejection response is an HTMX error fragment (HTML), not an `HX-Redirect` — same shape as the existing chart_pattern rejection (operator stays on the form; sees inline error). **Phase 5 HTMX gotchas APPLY to the rejection fragment:** (a) embedded forms inside HTMX-rendered fragments must include `hx-headers='{"HX-Request": "true"}'` propagation if the operator can re-submit from the fragment; (b) HX-Request header for OriginGuard strict-mode propagation. (c) HX-Redirect-vs-303-swap NOT applicable for the rejection path itself (it's a 4xx fragment, not a 2xx success).

10. **HTMX 4xx response handling** per CLAUDE.md gotcha: `base.html.j2` has a `htmx.config.responseHandling` override that enables 4xx swapping; tamper rejection MUST use a 4xx status code (e.g., 422 Unprocessable Entity per spec §7 implicit). TestClient verifies response body; operator-witnessed gate verifies the browser-side swap.

11. **`<tr>`-leading HTMX response gotcha** per CLAUDE.md gotcha + entry_post Bug B 2026-04-29 (commit `398483d`+): if the rejection fragment is destined for a `<table>` swap target, the response MUST NOT lead with `<tr>` at fragment root (would trigger htmx.js `makeFragment` synthetic-table-wrap + drop OOB chunks). Use `<div>` or `<section>` at root. Bundle D's rejection fragment shape MUST be operator-witnessed for browser-side correctness.

12. **Server-stamping discipline** per plan §A.10: `reconciliation_runs.started_ts` / `finished_ts` / `created_at` server-stamped at handler entry; `reconciliation_discrepancies.created_at` server-stamped via Bundle B's `insert_discrepancy`. Operator-supplied values from the rejected form (sector, industry) feed the `actual_value_json`; cached candidate values feed `expected_value_json`. No hidden form inputs (operator can't tamper with audit-row fields — they're all server-stamped or pulled from cached candidates).

13. **The rejected entry's transaction does NOT commit.** This is the architectural foundation of the audit-row-persists-even-on-rejection semantic. Per plan §A.4.1: the rejection raises before the entry's transaction commits; the audit row commits in a SEPARATE transaction. Discriminating regression test: assert `trades` table has no new row after rejection AND `reconciliation_runs` has +1 row AND `reconciliation_discrepancies` has +1 row.

### §0.6 Sub-bundle A + B + C landed surfaces (FORWARD-BOUND)

Sub-bundle A merged at `6c8f3a9`. Sub-bundle B merged at `e96834a`. Sub-bundle C merged at `e5d5892` + housekeeping at `26e1854`. Sub-bundle D builds on:

- **Sub-bundle A's `swing/trades/risk_policy.py`** canonical service-layer entry points (not directly invoked by D; available if needed for policy-aware audit row contextualization).
- **Sub-bundle A's `swing/data/datetime_helpers.py:now_ms` + `validate_ms_iso`** — used for all server-stamped TEXT datetime columns.
- **Sub-bundle A's `CallerHeldTransactionError`** exception type — Bundle D's ad-hoc audit emit is a SEPARATE TRANSACTION (per plan §A.4.1); does NOT call services that own transactions. Just pure repo CRUD.
- **Sub-bundle B's `swing/data/repos/reconciliation.py:insert_run` + `insert_discrepancy`** — Bundle D's audit emit uses these directly.
- **Sub-bundle B's `swing/trades/reconciliation.py:MATERIAL_BY_TYPE`** — `MATERIAL_BY_TYPE['sector_tamper'] = 0` (material=0 per spec §3.3.2 V1).
- **Sub-bundle B's `swing/trades/reconciliation.py:DISCREPANCY_TYPES`** — `sector_tamper` is in the tuple (Sub-bundle A's CHECK enum on `reconciliation_discrepancies.discrepancy_type` + Bundle B's constant).
- **Sub-bundle B's CLI `swing journal discrepancy {list,show,resolve}`** — Bundle D's audit rows surface here; operator can list / show / resolve.
- **Sub-bundle C's `swing account snapshot` CLI + `swing hypothesis update`** — UNTOUCHED by Bundle D.
- **`tests/conftest.py` test fixtures** establishing a v17 DB + A + B + C fixtures. Bundle D tests inherit.
- **Existing chart_pattern hardening at `swing/web/routes/trades.py`** (commits `117dc97` + `2b9d6f3`) — Bundle D's pattern template; the recon step (T-D.0) summarizes this before extending.

### §0.7 Sub-bundle A + B + C lessons FORWARD-BINDING

Per Sub-bundle A return report §7 + B return report §7 + C return report §7 + CLAUDE.md gotcha promotions at `de10601`:

- **CLAUDE.md gotchas banked 2026-05-12** (Phase 9 ratification single-fire; cascade emitter no-op-skip; USERPROFILE+HOME monkeypatch). NONE are directly invoked in Bundle D (no migration, no cascade emitter, no test fixture for `write_user_overrides`).
- **Sub-bundle B lesson: `MATERIAL_BY_TYPE` is authoritative at INSERT time.** Bundle D's sector_tamper emit MUST use the lookup (NOT hand-set inline 0). Codex R1 M#2 hardening pattern.
- **Sub-bundle B lesson: within-run dedup tuple shape** `(trade_id, type, field_name, ticker, fill_id, cash_movement_id, payload_disambiguator)`. Bundle D's sector_tamper emit has `trade_id=None` (the entry was rejected; no trade was created), `fill_id=None`, `cash_movement_id=None`, `field_name='sector'` OR `'industry'` (the disagreeing field), `ticker=<form ticker>`. Within-run dedup naturally guarantees one row per (run, field, ticker) — but since each audit run is freshly created per rejection, dedup is trivially single-row.
- **Sub-bundle C lesson: spec is canonical over brief on cosmetic typos.** Bundle D's brief reviewer should compare any wording in §0.5 against spec text; if conflict surfaces, spec wins. Codex will catch any divergence.
- **HTMX form-driven endpoints have two browser-only failure surfaces TestClient cannot detect** (CLAUDE.md gotcha 2026-05-02): HX-Request propagation on embedded forms + HX-Redirect for success-path. **Bundle D's rejection fragment is a 4xx response with no HX-Redirect** — but if the rejection fragment includes a re-submit form (operator can edit + retry), that form MUST include `hx-headers='{"HX-Request": "true"}'`.
- **HTMX 4xx fragments need explicit config override** (CLAUDE.md gotcha): `base.html.j2`'s `htmx.config.responseHandling` override enables 4xx swapping; preserve it if Bundle D touches base layout (likely NOT — Bundle D modifies route handler + tests only).
- **HX-Redirect target route must be verified to exist** (CLAUDE.md gotcha 2026-05-04 Phase 6 review POST): NOT applicable to Bundle D (no HX-Redirect from the rejection fragment).
- **`<tr>`-leading HTMX response triggers `makeFragment` synthetic-table-wrap** (CLAUDE.md gotcha entry_post Bug B 2026-04-29): if Bundle D's rejection fragment is destined for any `<table>` context, response root MUST NOT be `<tr>`. Use `<div>` or `<section>`.

### §0.8 Sub-bundle B Account Order History parser-gap + Sub-bundle C/D inception-CSV ingestion (BOTH NOT Bundle D scope)

Operator-witnessed gates on Sub-bundle B + C surfaced 3 V2/Bundle-E/D candidates banked in `docs/phase3e-todo.md` 2026-05-12:

1. **Account Order History multi-line parser gap** (Bundle E polish task; Sub-bundle B finding).
2. **Schwab inception-CSV ingestion** (Bundle D/E candidate; Sub-bundle C finding).
3. **account_equity_snapshots semantic formalization** (V2 candidate sequencing behind #2).

**Bundle D action on these:** NONE. All three are operator-paced + sequenced post-Sub-bundle-D ship. The operator may elect to address #2 (inception-CSV ingestion) within Bundle D's window if they have spare capacity, but it's NOT part of the binding T-D.0..T-D.3 scope. Bundle D's brief explicitly carves them out so the implementer doesn't conflate.

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase9-bundle-D-sector-tamper-hardening`
- **Worktree directory:** `.worktrees/phase9-bundle-D-sector-tamper-hardening/` (project convention per CLAUDE.md + Sub-bundle A/B/C precedent).
- **BASELINE_SHA:** `26e1854` (post-Sub-bundle-C-merge + housekeeping; HEAD of main BEFORE this brief commits).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the dispatch-brief commit SHA after this brief lands).
- The Codex diff (`26e1854` → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle D.

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 4 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefix:
  - `docs(web): T-D.0 — chart_pattern hardening recon note` (recon-only commit; in-plan documentation per plan §G)
  - `feat(web): T-D.1 — sector/industry tamper rejection at /trades/entry POST`
  - `feat(web): T-D.2 — emit sector_tamper discrepancy in ad-hoc system_audit reconciliation_run on rejection`
  - `test(integration): T-D.3 — E2E for tamper hardening`
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §G mark per-step boundaries.
- **Prefer `git add <specific-files>` over `git add -A`** — Phase 8 R1 Critical 1 lesson banked 2026-05-07. Never use `git add -A` or `git add .`.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below) — Chrome MCP browser-side verification is BINDING for this bundle (HTMX rejection fragment + 4xx swap + audit-row-persists semantics).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-bundle E dispatch commissioning.

### §1.5 Verify command
PowerShell from inside worktree (per Phase 5 editable-install lesson 2026-05-02 + Sub-bundle A/B/C precedent):
```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```
**Bundle D HAS a web surface** — the verify command IS needed for operator-witnessed gate browser verification. Operator opens `http://127.0.0.1:8080/trades/entry` against the worktree's running web server + drives the gate via Chrome MCP.

---

## §2 Adversarial review (Codex)

### §2.1 Setup (IMPLEMENTER runs this)

After ALL 4 task-family commits land + tests GREEN at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `phase9-bundle-D-sector-tamper-hardening`
   - `SPEC_PATH`: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
   - `PLAN_PATH`: `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (Codex scopes to §G Sub-bundle D)
   - `BASELINE_SHA`: `26e1854`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **2-3 rounds**. Bundle D scope is the narrowest of A/B/C/D (4 tasks; single route handler extension + audit emit; no schema; no service module). Bundle C converged in 3 rounds at 6+1 tasks; Bundle D should converge in 2-3.

### §2.2 Codex value-add concentration

Adversarial review for Sub-bundle D typically catches:
- **Audit-row-persists-on-rejection semantic** — if the audit INSERT is wrapped inside the entry POST's transaction (which rolls back on rejection), the audit row is lost. Codex will flag.
- **`MATERIAL_BY_TYPE['sector_tamper'] = 0` lookup bypass** — if the implementer hand-sets `material_to_review=0` inline instead of using the lookup, Codex will flag (Bundle B R1 M#2 precedent).
- **HTMX rejection fragment shape** — `<tr>`-leading response with `<table>` swap target (CLAUDE.md gotcha entry_post Bug B); 4xx without 4xx-swap-enabled config override (CLAUDE.md gotcha).
- **Sector vs industry test asymmetry** — two distinct code paths must each have a discriminating test; one-test-covers-both is insufficient (plan T-D.1 acceptance criteria).
- **Cached candidate lookup race** — if the candidate's sector/industry was updated mid-POST (e.g., concurrent pipeline run), the comparison may flag a false positive. Bundle D's `(ticker, action_session)` lookup matches the chart_pattern hardening pattern; Codex will verify the same race-safety.
- **OriginGuard strict-mode interaction** — the rejection POST must not bypass OriginGuard; the response must not include a redirect that leaks origin info.
- **Audit row's `actual_value_json` schema drift from spec §3.3.1** — Codex cross-checks JSON shape.
- **Within-run dedup gap** — even though each audit run is per-rejection (single-row), Codex may flag if the implementer adds unnecessary multi-row emit logic.

---

## §3 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR. Per plan §G intro (3 surfaces) + baseline:

- **S1 — Post-C-merge baseline.** Operator confirms current main HEAD includes Sub-bundle C's merge + housekeeping + brief commits. Runs `python -m pytest -m "not slow" -q` from worktree; verifies baseline GREEN (2741 fast + Bundle D test additions). Runs `swing config policy show` from worktree; verifies active policy_id (4) prints with 34 fields.
- **S2 — Form sector matches cached → entry proceeds.** Operator opens `http://127.0.0.1:8080/trades/entry` against worktree web server via Chrome MCP. Fills entry form with a ticker from the latest pipeline candidates list + sector/industry that MATCHES the cached candidate. Submits. Entry should proceed normally (regression-clean — chart_pattern hardening still works AND sector/industry match path doesn't reject). Verify the new `trades` row was inserted.
- **S3 — Form sector mismatches → reject + audit row.** Operator opens entry form for same ticker. Hand-edits the sector field to a different sector (e.g., "Technology" if cached is "Healthcare"). Submits. Expected behavior: HTMX-friendly error fragment renders inline (operator stays on the form); browser network tab shows 4xx response; reconciliation_runs has +1 row with `source='system_audit'`, `state='completed'`; reconciliation_discrepancies has +1 `sector_tamper` row with `expected_value_json={"sector": "Healthcare"}` + `actual_value_json={"sector": "Technology"}` + `material_to_review=0`. Verify via `swing journal discrepancy list` from worktree.
- **S4 — Form industry mismatches → reject + audit row** (same shape as S3 but for industry field). Mirror behavior.
- **S5 — pytest + ruff.** From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows 18 (E501 only).

**Expected test count delta:** +15 to +35 fast tests (T-D.0..T-D.3; plan §J.3 projection for D was 15-25; T-D.2's audit-emit discriminating tests may push toward upper bound).

**Expected ruff baseline:** 18 (no change).

**Production-write classifier soft-block awareness:** S2-S4 are production writes (new trade row in S2; audit rows in S3 + S4). If the orchestrator-driven invocation is classifier-blocked, the orchestrator will surface back to the operator with a plain-chat confirmation request. This does NOT affect the implementer; it's an orchestrator-side gating concern.

**Operator-witnessed browser verification is BINDING for this bundle** — the HTMX rejection fragment + 4xx swap + inline-rendering behavior is invisible to TestClient (per CLAUDE.md HTMX gotcha family). Chrome MCP walkthrough required.

---

## §4 Return report shape

After operator-gate PASS, draft return report at `docs/phase9-bundle-D-return-report.md` (mirroring `docs/phase9-bundle-C-return-report.md` shape):

1. Final HEAD on branch.
2. Commit count breakdown (task-impl per T-D.X + Codex-fix + operator-gate-fix).
3. Codex round chain.
4. Test count delta + ruff baseline delta.
5. Operator-gate surface results (S1-S5).
6. Per-task deviations from the plan (if any).
7. Codex Major findings ACCEPTED with rationale (target: zero or one; trend across A=2, B=1, C=1; Bundle D smaller scope should be zero).
8. Watch items surfaced but not acted on (for Sub-bundle E to absorb OR for orchestrator-context capture).
9. Worktree teardown status (expected ACL-locked husk).
10. Composition-surface verification: `^def` enumeration of any new audit-emit helpers in `swing/web/routes/trades.py` (likely a small private helper for the ad-hoc audit emit; verify single definition + no hand-duplication).
11. Hand-off notes for Sub-bundle E dispatch (Bundle D → E enables E's combined E2E + final polish + CLAUDE.md gotcha promotion candidates + Phase 10 hand-off prep).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading phase9-bundle-D-sector-tamper-hardening dispatch.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-D-sector-tamper-hardening
BRANCH: phase9-bundle-D-sector-tamper-hardening
BASELINE_SHA: 26e1854  (per dispatch brief §1.1; HEAD of main BEFORE the brief commit; post-Sub-bundle-C-merge + housekeeping)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (26e1854 → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle D.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase9-bundle-D-sector-tamper-hardening -b phase9-bundle-D-sector-tamper-hardening $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase9-bundle-D-executing-plans-dispatch-brief.md

Step 2 — Read the plan §A (resolved-during-planning, lines 13-216) + §B (file map, lines 218-282) + §C (decomposition, lines 284-302) + §G (Sub-bundle D, lines 1952-2046) end-to-end:
  docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  Skim §I (cross-bundle invariants, lines 2116-2140) + §J.2 (grep-verification commands).

Step 3 — Read the spec (focus on §7 sector/industry tamper hardening; §3.3.1 sector_tamper expected_value/actual_value JSON shape; §3.2 reconciliation_runs source enum):
  docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md

Step 4 — Read binding conventions + Sub-bundle A + B + C landings:
  - CLAUDE.md (gotchas; project conventions; HTMX failure surfaces are BINDING; 3 NEW gotchas from Sub-bundle A landing at de10601)
  - docs/orchestrator-context.md (orchestrator-role framing; 2 NEW lessons from Sub-bundle A landing at de10601)
  - docs/phase9-bundle-A-return-report.md (§7 + §10 hand-off)
  - docs/phase9-bundle-B-return-report.md (§10 hand-off #1+#2 — MATERIAL_BY_TYPE + DISCREPANCY_TYPES already in place; Bundle D consumes via insert_run + insert_discrepancy directly)
  - docs/phase9-bundle-C-return-report.md (§10 hand-off; equity_delta now wired)
  - docs/phase3e-todo.md (3 V2/E candidates banked 2026-05-12 — none are Bundle D scope; explicit carve-out per brief §0.8)
  - docs/phase9-writing-plans-dispatch-brief.md §0.3 + §7 (9-lesson catalog FORWARD-BINDING)

Step 5 — Verify worktree state:
  git rev-parse HEAD                                          # expect current main HEAD (typically the dispatch brief commit)
  git status                                                  # expect clean
  python -m pytest -m "not slow" -q                           # expect baseline GREEN (2741 passed, 5 skipped; 3 pre-existing fails NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 17

Step 6 — Pre-implementation grep recon (Bundle 2+3 + Sub-bundle A + B + C lesson applied):
  grep -rn "^def " swing/data/repos/reconciliation.py        # locate Bundle B's insert_run + insert_discrepancy entry points
  grep -rn "chart_pattern" swing/web/routes/trades.py        # locate chart_pattern hardening pattern to mirror
  git log --oneline -- swing/web/routes/trades.py | head -10  # commit history for the file
  git show 117dc97 -- swing/web/routes/trades.py             # chart_pattern hardening commit #1 (per plan §A.4 + T-D.0 recon)
  git show 2b9d6f3 -- swing/web/routes/trades.py             # chart_pattern hardening commit #2 (per plan §A.4 + T-D.0 recon)
  grep -rn "MATERIAL_BY_TYPE\|DISCREPANCY_TYPES" swing/trades/reconciliation.py    # confirm sector_tamper material=0 + in enum
  grep -A 50 "CREATE TABLE reconciliation_discrepancies" swing/data/migrations/0017_*.sql   # verify CHECK enum includes sector_tamper
  grep -A 50 "CREATE TABLE reconciliation_runs" swing/data/migrations/0017_*.sql            # verify source CHECK enum includes 'system_audit'
  ls swing/data/migrations/                                   # confirm 0017 is the only Phase 9 migration + no 0018 attempt during dispatch (BINDING — Bundle D does NOT modify migrations)
  Capture divergences from plan assumptions; surface in return report §6.

Step 7 — Invoke copowers:executing-plans (the skill wraps superpowers:subagent-driven-development + adversarial Codex review):
  - PHASE: phase9-bundle-D-sector-tamper-hardening
  - SPEC_PATH: docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  - PLAN_PATH: docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  - BASELINE_SHA: 26e1854
  - SCOPE: Sub-bundle D only (tasks T-D.0 through T-D.3 in plan §G).

Step 8 — TDD per task: failing test → minimal implementation → pass → commit. Per-task `- [ ]` checkboxes in plan §G mark per-step boundaries.

Step 9 — After ALL 4 tasks land + GREEN, run adversarial review per dispatch brief §2.1. Iterate Codex rounds until NO_NEW_CRITICAL_MAJOR. Expected 2-3 rounds.

Step 10 — Draft return report at docs/phase9-bundle-D-return-report.md per dispatch brief §4. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives §3 witnessed verification gate (Chrome MCP browser-side BINDING); orchestrator handles integration merge; orchestrator dispatches Sub-bundle E next.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Skip the Step 6 pre-implementation grep recon
  - Modify migration 0017 in any way (Bundle D is consumer-side only; atomicity BINDING per Sub-bundle A landing)
  - Bump EXPECTED_SCHEMA_VERSION beyond 17 (Bundle D does NOT advance the schema)
  - Add cross-bundle code (no Bundle E polish work; no hypothesis_status_history work; no Schwab inception-CSV ingestion; no account_equity_snapshots semantic formalization — all banked at docs/phase3e-todo.md as separate items)
  - Add UPDATE schema_version statements
  - Use INSERT OR REPLACE or REPLACE INTO anywhere
  - Call conn.commit() inside new helpers (caller controls transaction scope; Bundle D's audit emit owns its own transaction OR routes through the existing repo functions)
  - Modify Bundle B's MATERIAL_BY_TYPE / DISCREPANCY_TYPES / RESOLUTION_TYPES constants (LOCKED)
  - Modify Bundle B's `run_tos_reconciliation` service (Bundle D uses repo-level insert_run + insert_discrepancy directly per plan §A.4 + brief §0.5 #4)
  - Wrap the audit-row INSERT inside the rejected entry's transaction (audit row MUST persist on rejection per plan §A.4.1)
  - Touch Bundle B's parser code for stop_mismatch / Account Order History (banked as Bundle E polish per phase3e-todo.md 2026-05-12 entry)
  - Diverge from plan §A locked decisions without explicit Codex justification
  - Use `git add -A` or `git add .` (per Phase 8 R1 Critical 1 lesson; stage specific files)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-12 (post-Sub-bundle-C-merge + housekeeping).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `26e1854` on main (post-Sub-bundle-C-merge + housekeeping).
- **Worktree path (binding):** `.worktrees/phase9-bundle-D-sector-tamper-hardening/`.
- **Baseline test count:** 2741 fast (5 skipped — 4 implementer SKIP-on-absent + 1 prior); 3 pre-existing failures NOT regressions.
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** SHIPPED 2026-05-11 at `a0c7223`; 2257 lines; 30 tasks; Codex R5 confirmation.
- **Sub-bundle A status:** SHIPPED 2026-05-12 at `6c8f3a9`.
- **Sub-bundle B status:** SHIPPED 2026-05-12 at `e96834a`.
- **Sub-bundle C status:** SHIPPED 2026-05-12 at `e5d5892`; 7-surface operator-witnessed gate ALL PASS; 1 ACCEPT-WITH-RATIONALE (equity_delta sign convention spec-vs-brief cosmetic).
- **Expected post-dispatch test count:** ~2756-2776 (+15-35; T-D.0..T-D.3).
- **Expected post-dispatch ruff count:** 18 (no change).
- **Expected schema version post-Bundle-D:** 17 (UNCHANGED; Bundle D is consumer-side only).
- **Sub-bundle E dispatch dependency:** D's sector_tamper rejection + audit emit must merge to main + orchestrator-witnessed gate PASS before E can dispatch. Sub-bundle E consumes all prior bundle surfaces for combined E2E + final polish + Phase 10 hand-off prep.
- **Phase 9 arc remaining:** A ✓ → B ✓ → C ✓ → D (this dispatch) → E. Then Phase 10 writing-plans.
