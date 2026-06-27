# Phase 9 Sub-bundle D — executing-plans return report

**Branch:** `phase9-bundle-D-sector-tamper-hardening`
**Final HEAD:** `59c4dcb`
**Worktree:** `.worktrees/phase9-bundle-D-sector-tamper-hardening/`
**Baseline:** `26e1854` (BASELINE_SHA per dispatch brief §1.1; post-Sub-bundle-C-merge + housekeeping)
**Worktree branching point:** `2ecda00` (dispatch brief commit on main)
**Spec:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
**Plan:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` §G (T-D.0..T-D.3)
**Dispatch brief:** `docs/phase9-bundle-D-executing-plans-dispatch-brief.md`

---

## §1 Commit chain

| Seq | Commit | Title |
|---|---|---|
| 1 | `a9a4e9d` | docs(web): Task D.0 — chart_pattern hardening recon note for sector/industry tamper extension |
| 2 | `99bf70f` | feat(web): Task D.1 — sector/industry tamper rejection at /trades/entry POST |
| 3 | `a612002` | feat(web): Task D.2 — emit sector_tamper discrepancy in ad-hoc system_audit reconciliation_run on rejection |
| 4 | `c861643` | test(integration): Task D.3 — E2E for sector/industry tamper hardening |
| 5 | `921b712` | fix(web): Codex R1 Critical #1 + Major #1 — close blank-field tamper bypass + align POST anchor to form-render |
| 6 | `13f07aa` | fix(web): Codex R2 Critical #1 + Major #1 + #2 — explicit form anchor closes blank-bypass + GET/POST drift |
| 7 | `34e5504` | fix(web): Codex R3 Critical #1 — round-trip sector_industry anchor through soft-warn confirm |
| 8 | `59c4dcb` | docs(web): Codex R4 Minor #1 — sync recon doc §8 with post-R2/R3 _emit_sector_tamper_audit signature |

**Total: 8 commits on top of the dispatch-brief commit = 4 task-impl (T-D.0..T-D.3) + 3 Codex-Critical-or-Major-fix + 1 Codex-Minor-doc-sync.** Zero `--no-verify`, zero `--amend`, zero Claude co-author footers. Stage-by-specific-file convention preserved (no `git add -A` / `git add .`).

---

## §2 Codex adversarial-review chain

4-round convergent shape with concentrated security findings on the route-layer hardening surface — slightly OVER the dispatch-brief §2.1 expected 2-3 round budget. Each round exposed a real attack-vector that a less-rigorous review would have missed; the final design is meaningfully stronger than the original implementation.

| Round | New Critical | New Major | New Minor | Verdict | Disposition |
|---|---|---|---|---|---|
| **R1** | 1 | 1 | 1 | ISSUES_FOUND | C#1 RESOLVED (blank-field tamper bypass → strict `!=` predicate). M#1 RESOLVED (anchor alignment between form-render + POST; re-anchored POST lookup to `latest_evaluation_run_id` mirror). m#1 RESOLVED (added 3 adversarial regression tests for the tightened predicate). |
| **R2** | 1 | 2 | 1 | ISSUES_FOUND | C#1 RESOLVED (HTMX both-blank tamper still bypassed under R1 outer-guard; replaced with explicit `sector_industry_evaluation_run_id` hidden form anchor mirroring chart_pattern). M#1 RESOLVED (GET/POST TOCTOU drift; hidden anchor stable across submit). M#2 RESOLVED (contract drift — updated docs/phase9-bundle-D-task-D0-recon.md §4 with binding post-R2 design). m#1 RESOLVED (stale comment in test helper docstring). |
| **R3** | 1 | 0 | 1 | ISSUES_FOUND | C#1 RESOLVED (soft-warn confirm dropped the new anchor; tampered `force=true` resubmit silently passed. Added anchor to `form_values` dict + added discriminating regression test asserting the confirm fragment carries the hidden input AND that a tampered force=true submit is rejected). m#1 RESOLVED (recon doc §3 table row + test-helper docstring sync). |
| **R4** | 0 | 0 | 1 | **NO_NEW_CRITICAL_MAJOR** | m#1 RESOLVED (recon doc §8 helper-signature drift — synced with post-R2/R3 `cand_session_iso` + `run_session_iso` shape). Convergence reached. |

**Convergent shape:** R1 (1C/1M/1m) → R2 (1C/2M/1m) → R3 (1C/0M/1m) → R4 (0C/0M/1m). The pattern is "each round closes the previous round's primary attack-vector AND uncovers a deeper but narrower one" — characteristic of route-layer security work where defenses compound through layers. The R3 soft-warn-confirm finding could ONLY surface after R2's hidden-anchor design landed (the anchor didn't exist before R2).

**ZERO Critical findings remain. ZERO Major findings remain. ZERO ACCEPT-WITH-RATIONALE positions on any of 8 Critical+Major findings raised across all rounds — every Critical and Major was RESOLVED in-tree with a discriminating regression test pinning the fix.**

### §2.1 Codex thread

- **Thread ID:** `019e1e2e-0006-7442-92a0-d850ed2b2e52` (preserved through R4).

---

## §3 Test count delta + ruff baseline delta

**Test count:**
- Pre-Bundle-D baseline (per dispatch brief §0.3, verified at fixture-run pre-implementation): **2741 fast passing** (5 skipped — 4 implementer SKIP-on-absent for `thinkorswim/*.csv` + 1 prior; 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions).
- Post-Bundle-D: **2757 fast passing** (5 skipped; same 3 pre-existing failures excluded).
- **Delta: +16 fast tests** (matches the dispatch brief §0.4 +15 to +35 projection; near the lower bound because Bundle D is consumer-side only with a narrow route-layer focus).

Per-task / per-round breakdown:
- T-D.0 recon note: +0 (docs-only)
- T-D.1 sector/industry rejection: +5 (matching, sector reject, industry reject, empty bare-cURL skip, no-cached skip)
- T-D.2 ad-hoc audit emit: +4 (sector audit JSON shape, industry field_name, both-mismatch short-circuit, persistence-across-conn)
- T-D.3 E2E integration: +1 (full route emit → CLI list → filter combinations loop)
- Codex R1 fix adversarial tests: +3 (blank-sector tamper, blank-industry tamper, stale-pipeline anchor alignment)
- Codex R2 fix adversarial tests: +2 (tampered anchor wrong-ticker, tampered anchor non-existent eval_id)
- Codex R3 fix adversarial test: +1 (soft-warn confirm round-trip + tamper rejection)
- Codex R4 fix: +0 (docs-only sync)

**Ruff baseline:** **18 (E501 only) — UNCHANGED** from pre-Bundle-D baseline. Bundle D introduced zero new lint violations.

---

## §4 Files changed

### Created
- `docs/phase9-bundle-D-task-D0-recon.md` — T-D.0 recon note documenting the chart_pattern hardening pattern mirror + the §4 + §8 amendments capturing the post-R2/R3 binding design.
- `tests/web/test_routes/test_trade_entry_sector_industry_tamper.py` — 16 tests covering match-path, sector/industry rejection, audit emit JSON shape, anchor backward-compat, blank-field tamper coverage, tampered-anchor rejection, stale-pipeline anchor alignment, soft-warn confirm round-trip + tamper rejection.
- `docs/phase9-bundle-D-return-report.md` — this report.

### Modified
- `swing/web/routes/trades.py` — `_emit_sector_tamper_audit` private helper + sector/industry tamper-check block in `entry_post`; new `sector_industry_evaluation_run_id` Form() param; soft-warn confirm `form_values` dict gains the anchor entry.
- `swing/web/view_models/trades.py` — `TradeEntryFormVM` gains `sector_industry_evaluation_run_id: int | None` field; `build_entry_form_vm` populates it from the same `sector_eval_id` used for the form's sector/industry lookup.
- `swing/web/templates/partials/trade_entry_form.html.j2` — hidden input `sector_industry_evaluation_run_id` emitted alongside `sector` + `industry`.
- `tests/integration/test_phase9_end_to_end.py` — new `test_phase9_bundle_d_e2e_sector_tamper_audit_surfaces_in_cli_list` end-to-end test; threaded anchor through the tamper-attempt POST payload.

### NOT modified (Bundle D scope discipline)
- Migration `swing/data/migrations/0017_*.sql` — UNCHANGED. `EXPECTED_SCHEMA_VERSION = 17` unchanged.
- Bundle B's `swing/trades/reconciliation.py:run_tos_reconciliation` service — UNCHANGED. Bundle D uses repo-level entry points directly per plan §A.4 + Bundle B return report §10 #1.
- `MATERIAL_BY_TYPE` / `DISCREPANCY_TYPES` / `RESOLUTION_TYPES` constants — UNCHANGED. Bundle D consumes via import only.
- Bundle B / Bundle C / Sub-bundle A code — UNCHANGED. Bundle D is consumer-side only.

---

## §5 Operator-witnessed gate readiness

Sub-bundle D ships 3 operator-witnessed gate surfaces per plan §G + dispatch brief §3. After integration merge, the orchestrator drives:

- **S1 — Post-C-merge baseline + ruff sanity.** `python -m pytest -m "not slow" -q` from worktree returns 2757 pass / 5 skip / 3 pre-existing failures. `ruff check swing/ --statistics` shows 18 (E501 only). `swing config policy show` returns active policy_id (4) with 34 fields.
- **S2 — Form sector matches cached → entry proceeds.** Operator opens `http://127.0.0.1:8080/trades/entry?ticker=<X>` against the worktree web server via Chrome MCP. Fills form with the cached sector/industry. Verify (a) the new trade row inserts, (b) NO reconciliation_runs row is emitted on the happy path.
- **S3 — Form sector mismatch → reject 400 + audit row.** Operator hand-edits the sector hidden input to a different value (browser DevTools). Submits. Expected: HTMX-friendly 4xx error fragment renders inline; `reconciliation_runs` has +1 row with `source='system_audit'`, `state='completed'`; `reconciliation_discrepancies` has +1 `sector_tamper` row with `expected.session` matching the cached eval's `action_session_date`. Verify via `swing journal discrepancy list`.
- **S4 — Form industry mismatch → same shape as S3 but with `field_name='industry'`.**
- **S5 — Pytest + ruff.** From the worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows 18 (E501 only).

**Browser-only failure surfaces covered by automated tests:**
- HTMX 4xx swap behavior — `base.html.j2` `responseHandling` override preserved; rejection responses use HTTP 400 status with HTML body for OOB-swap rendering.
- `<tr>`-leading fragment makeFragment-wrap (CLAUDE.md gotcha entry_post Bug B): the rejection path uses `_rerender_entry_form_with_error` which returns a `<form>` (not `<tr>`)-rooted fragment, identical to chart_pattern hardening's response shape. No regression.
- HX-Request propagation: existing form template already emits forms with the required HX setup; Bundle D adds only a hidden input, no form-element changes.

**Production-write classifier note:** S2 (legitimate entry) and S3/S4 (rejection paths emitting audit rows) are both production-write surfaces under the operator's actual `swing.db`. If the orchestrator-driven invocation is classifier-blocked, the orchestrator surfaces back to the operator with a plain-chat confirmation request before executing.

---

## §6 Per-task deviations from the plan

### §6.1 R2 architectural pivot: explicit hidden anchor (mirrors chart_pattern)

The plan §A.4 + spec §7 + the D0 recon note initially described the cached-candidate lookup at POST time as keyed on `(ticker, action_session_for_run(now()))`. Codex R1 + R2 found this design admits two attack vectors:

1. **Form-render anchor drift.** The form-render's anchor (`latest_evaluation_run_id` for watchlist origin; `latest_completed_pipeline_run.evaluation_run_id` for hyp-recs) is NOT today's action_session. A stale-pipeline scenario (no pipeline ran today yet) populates the form with stale-eval values; the POST-time lookup keyed on today's session yields no row; tamper check is silently skipped.
2. **GET/POST TOCTOU drift.** Even when today's eval exists at form-render time, a fresh pipeline landing between GET + POST changes the authoritative "latest" candidate. A POST-time recompute compares against the NEW row, not the one the operator saw.

Resolution: mirror chart_pattern's `chart_pattern_classification_pipeline_run_id` hidden anchor pattern. Form-render emits `sector_industry_evaluation_run_id`; POST validates `(eval_run_id, ticker)`. This deviates from the plan's literal wording ("keyed on action_session") but matches the plan's binding intent ("mirror the chart_pattern hardening pattern" — plan §A.4) and the operator-facing behavior is equivalent under normal pipeline cadence (today's pipeline run anchors today's form's anchor).

The deviation is documented in `docs/phase9-bundle-D-task-D0-recon.md` §3 + §4 with explicit supersession notes pointing at the Codex R2 round.

### §6.2 R3 soft-warn confirm round-trip — necessary integration with Phase 4-7 lessons

The soft-warn confirm fragment iterates a `form_values` dict to emit hidden inputs that the `force=true` resubmit replays. Phase 4 added `sector` + `industry`; Phase 5 added the chart_pattern snapshot fields; Phase 4.5 added `hypothesis_label`; Phase 7 added the 18 pre-trade fields; Phase 8 added origin. Bundle D inherits this compounding-round-trip discipline: every form-render-time hidden anchor that drives a POST-time validation MUST also flow through soft-warn confirm.

The plan did not enumerate this dependency. Codex R3 caught it. Resolution: add `sector_industry_evaluation_run_id` to `form_values` + discriminating regression test asserting the confirm fragment carries the anchor + a tampered `force=true` resubmit is rejected.

### §6.3 No code change in spec §7 step 2 wording

The spec §7 step 2 wording ("Route handler: lookup cached candidate by `(ticker, action_session_for_run(now))`") was NOT amended in this dispatch. The recon doc (`docs/phase9-bundle-D-task-D0-recon.md`) carries the binding post-R2/R3 amendments + supersession notes. A spec amendment per V2.1 §VII.F source-of-truth correction protocol may follow at integration-merge or as a Sub-bundle E polish item; this is the orchestrator-context capture surface for the discrepancy.

---

## §7 Codex Major findings ACCEPTED with rationale

**ZERO.** All 8 raised Critical+Major findings across 4 rounds were RESOLVED in-tree with discriminating regression tests. Trend across the Phase 9 arc:

- Sub-bundle A: 2 ACCEPT-WITH-RATIONALE
- Sub-bundle B: 1 ACCEPT-WITH-RATIONALE (later resolved via C cross-bundle wiring)
- Sub-bundle C: 1 ACCEPT-WITH-RATIONALE
- **Sub-bundle D: 0 ACCEPT-WITH-RATIONALE.**

This is the first phase in the Phase 9 arc with zero ACCEPT-WITH-RATIONALE positions.

---

## §8 Watch items surfaced but not acted on

(For Sub-bundle E to absorb OR orchestrator-context capture.)

1. **Spec §7 wording amendment.** The post-R2 chart_pattern-mirror anchor design is documented in the recon doc, but the spec text ("keyed on `(ticker, action_session_for_run(now))`") still names the original today-anchored design. V2.1 §VII.F source-of-truth correction protocol is the right channel for the spec text update. Sub-bundle E or orchestrator-context capture.

2. **CLAUDE.md gotcha promotion candidate — "Form-driven hidden-anchor patterns must round-trip through soft-warn confirm `form_values`."** Codex R3 Critical #1 surfaced a recurring pattern: any time a form-render-time hidden anchor drives a POST-time validation (chart_pattern's `pipeline_run_id`; sector/industry's `evaluation_run_id`; future cases yet to land), the anchor MUST be added to the soft-warn confirm `form_values` dict OR the `force=true` resubmit silently bypasses the validation. Pattern complement to the existing "Phase 5 HTMX failure surfaces" gotcha family. Orchestrator triage at integration merge.

3. **CLAUDE.md gotcha promotion candidate — "POST-time recompute of 'latest evaluation_run_id' creates a TOCTOU window."** Codex R2 Major #1 was a real attack: a fresh pipeline landing between GET and POST shifts the comparison. Same pattern would re-appear in any future "latest-of-something" POST-time recompute. Pattern: prefer form-render-emitted hidden anchors over POST-time recomputes for any value the operator saw at form-render time. Orchestrator triage at integration merge.

4. **The two adversarial tests covering tampered anchor (`test_post_entry_with_tampered_anchor_rejects_without_audit_emit` + `test_post_entry_with_bogus_anchor_pointing_at_nonexistent_eval_rejects`) intentionally do NOT emit an audit row** on rejection (no cached values to attribute against). This is a deliberate V1 choice: the tampered anchor IS the tamper signal; we can't form a meaningful `sector_tamper` discrepancy without cached values. V2 could emit a separate `anchor_tamper` discrepancy type if the operator wants forensic visibility on this surface. Banked for Phase 10 or a future polish bundle. NOT a Bundle D / E scope.

5. **V2 hardening note: `__post_init__` validator on `TradeEntryFormVM`.** The new field `sector_industry_evaluation_run_id: int | None` accepts any int. Defensive coding could constrain to non-negative ints + validate against `swing/data/repos/candidates.py` schema at construction time. V1 accepts any int because the route-layer query is the validation boundary. V2 candidate.

---

## §9 Worktree teardown status

Expected ACL-locked husk per Phase 8/Sub-bundle A/B/C precedent. Operator runs the cleanup script post-merge.

---

## §10 Composition-surface verification (`^def` grep enumeration)

Per dispatch brief §0.7 + plan §I item 11:

```bash
grep -rn "^def _emit_sector_tamper_audit" swing/
# → swing/web/routes/trades.py:125  (1 match — definition only; no cross-module duplication)
```

No call sites reach the helper from outside `swing/web/routes/trades.py:entry_post`. The helper is private (leading underscore) and intentionally scoped to the route-layer rejection branch.

---

## §11 Hand-off notes for Sub-bundle E dispatch

(Forward-binding contracts Sub-bundle E should mirror / consume.)

1. **Migration 0017 schema is at v17 + UNCHANGED.** Sub-bundle D is consumer-side only. `EXPECTED_SCHEMA_VERSION = 17`. Sub-bundle E ships polish + Phase 10 hand-off on top of the same v17 schema; no migration.

2. **`_emit_sector_tamper_audit` is the canonical helper for the route-layer sector_tamper audit emit.** Sub-bundle E + future surfaces that need to emit a sector_tamper audit (e.g., a hypothesis-driven entry-form variant in Phase 10) MUST route through it OR justify a divergence in a discriminating test.

3. **`sector_industry_evaluation_run_id` hidden form anchor is the binding pattern.** Future route-layer hardening (e.g., chart_pattern variant for chart_pattern_evaluation drift) should mirror it: form-render emits hidden anchor → POST validates against that exact eval_id → tampered/stale anchor rejected with descriptive error → no audit row when anchor is forged.

4. **Soft-warn confirm `form_values` dict requires ALL form-render hidden anchors.** Future additions should be added to the dict alongside `sector_industry_evaluation_run_id` + `chart_pattern_classification_pipeline_run_id` + `hypothesis_label` + `origin` + sector/industry. Failure to do so silently bypasses the corresponding POST-time validation on `force=true` resubmit.

5. **Sub-bundle E E2E expansion candidate.** Plan §H T-E.0 names a "combined E2E happy path" — Sub-bundle D's `test_phase9_bundle_d_e2e_sector_tamper_audit_surfaces_in_cli_list` is the route-emit + CLI-list path; the E E2E should additionally chain (a) a pipeline run to populate today's candidates, (b) form-render via TestClient GET, (c) operator-tamper POST simulated by browser DOM modification of the hidden anchor (Sub-bundle D's tests simulate this via the helper API), (d) audit row resolution via CLI.

6. **CLAUDE.md gotcha promotion candidates (§8 above) are E scope.** Orchestrator triages at integration merge OR Sub-bundle E inlines them into a `docs/E1` CLAUDE.md gotcha promotion task (per plan §H T-E.1).

7. **Spec §7 wording update (§6.3 + §8 #1).** V2.1 §VII.F source-of-truth correction protocol channel. Sub-bundle E may carry an amendment OR orchestrator-context capture defers to Phase 10's spec review.

8. **The 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures** remain unchanged from Sub-bundle A baseline; triage out of scope for Bundle D. Sub-bundle E or a separate polish bundle.

---

## §12 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-12 (post-Sub-bundle-C-merge + housekeeping).
- **Brief commit:** `2ecda00` on main.
- **Implementer-spawn:** 2026-05-12.
- **Total wall-clock:** ~6 hr implementation + ~2 hr Codex convergence (4 rounds at MCP-driven cycle). Total **~8 hr**. Within dispatch brief §0 expected duration of "5-9 hr" — at the upper bound because Codex took 4 rounds vs the expected 2-3, and each round required a meaningful architectural pivot (R2 hidden anchor was a substantive design change, not just a tightening).
- **Marker file:** removed before R1 invocation per dispatch brief §2.1 step 1.
- **Codex thread:** `019e1e2e-0006-7442-92a0-d850ed2b2e52` (preserved through R4).
- **Final HEAD:** `59c4dcb` on `phase9-bundle-D-sector-tamper-hardening`.
- **Sub-bundle E dispatch dependency:** D's tamper-hardening + audit emit + soft-warn confirm round-trip must merge to main + orchestrator-witnessed gate PASS before E can dispatch. Sub-bundle E consumes all prior bundle surfaces for combined E2E + final polish + Phase 10 hand-off prep.
- **Phase 9 arc remaining:** A ✓ → B ✓ → C ✓ → D ✓ (this dispatch) → E. Then Phase 10 writing-plans.

---

*End of return report. Standing by for orchestrator integration merge + Sub-bundle E dispatch.*
