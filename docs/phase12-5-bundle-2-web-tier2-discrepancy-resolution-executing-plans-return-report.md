# Phase 12.5 #2 — Web Tier-2 Discrepancy-Resolution Surface — Executing-Plans Return Report

**Branch:** `phase12-5-bundle-2-web-tier2-executing-plans`
**Worktree:** `.worktrees/phase12-5-bundle-2-web-tier2-executing-plans/`
**Baseline SHA:** `3416e1e710f72abcec01dffb8a215cfac8b6d54f` (main HEAD at dispatch)
**Final HEAD:** `4f0f32f`
**Dispatch:** docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-executing-plans-dispatch-brief.md
**Plan:** docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md (LOCKED at `9220dac`)
**Spec:** docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md (LOCKED at `ac6eb88`)

---

## §1 Final HEAD + commit count breakdown

**Final HEAD:** `4f0f32f`

**16 commits on branch** from baseline `3416e1e`:

| # | SHA | Type | Task / Round |
|---|---|---|---|
| 1  | `10e6a69` | task-impl | T-2.1 `_parse_parametric_pick_count` helper |
| 2  | `9aed9aa` | task-impl | T-2.2 `ReconcileDiscrepancyResolveVM` + sub-VMs + 10 render helpers |
| 3  | `0b88a28` | task-impl | T-2.3 `build_reconcile_discrepancy_resolve_vm` builder |
| 4  | `1ce0d06` | task-impl | T-2.4 `reconcile_discrepancy_resolve.html.j2` template |
| 5  | `52a1b58` | task-impl | T-2.5 GET route + 2-branch error template stub |
| 6  | `bc4ff2e` | task-impl | T-2.6 POST route + 3 inline error branches + L-W2 race fix |
| 7  | `d587571` | task-impl | T-2.7 `BaseLayoutVM.banner_resolve_link` + 13-VM Pass A retrofit |
| 8  | `1f5c4f0` | task-impl | T-2.8 `base.html.j2` banner-link + retrofit-completeness audit |
| 9  | `d6bbd30` | task-impl | T-2.9 first-pending helpers + 24-callsite Pass B retrofit |
| 10 | `3d1f6b8` | task-impl | T-2.10 error-template a11y polish + per-branch coverage |
| 11 | `8f65e0b` | task-impl | T-2.11 slow E2E + CLI/web parity + XSS/sentinel audit + cycle-checklist |
| 12 | `25f4554` | orchestrator-inline | `/dashboard` route alias (gate-fix; closes Phase 6 I3 HX-Redirect-target-unrouted gotcha pre-Codex) |
| 13 | `ae92f26` | Codex R1 fix | 2 Major (type-invalid payload fallback + OperationalError pre-flight scope) |
| 14 | `8610ef0` | Codex R2 fix | 2 Major (rerender OperationalError + race re-read cascade gap) |
| 15 | `c578231` | Codex R3 fix | 1 Major (`sqlite3.connect` OperationalError) + 1 Minor (builder `ValueError` classification) |
| 16 | `4f0f32f` | Codex R4 fix | 1 Major (GET handler builder `ValueError` classification) |

Aggregate: **11 task-impl + 1 orchestrator-inline gate-fix + 4 Codex-fix = 16 commits**. ZERO return-report commit yet (lands separately at integration-merge time).

---

## §2 Codex chain summary

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR at R5.** Convergent monotonic-Major taper.

| Round | Critical | Major | Minor | Verdict | Disposition |
|---|---|---|---|---|---|
| R1 | 0 | 2 | 1 | ISSUES_FOUND | Both Major RESOLVED in `ae92f26`; Minor #1 ACCEPTED-as-advisory (L-W5 LOCK forbids `error_kind` Literal tightening) |
| R2 | 0 | 2 | 0 | ISSUES_FOUND | Both NEW Major RESOLVED in `8610ef0` (concurrency-edge cases revealed by R1 expansion) |
| R3 | 0 | 1 | 1 | ISSUES_FOUND | Major + Minor BOTH RESOLVED in `c578231` |
| R4 | 0 | 1 | 0 | ISSUES_FOUND | Major RESOLVED in `4f0f32f` (with shared `_classify_builder_value_error` helper extraction) |
| R5 | 0 | 0 | 0 | NO_NEW_CRITICAL_MAJOR | Chain converged ✓ |

**ZERO Critical findings entire chain.** **ZERO ACCEPT-WITH-RATIONALE** on Major findings — all 6 cumulative Major findings RESOLVED with code-content fixes (matches Phase 12.5 #2 brainstorm + writing-plans + Phase 12 Sub-bundle C arc + Phase 12.5 #1 clean-record streak).

**1 Minor ACCEPTED-with-rationale**: R1 Minor #1 (`error_kind` Literal validation) — accepted per plan §A T-2.10 acceptance + L-W5 LOCK (Codex R3 M#1 fix at writing-plans explicitly forbids tightening the validator).

**Convergent shape:** monotonic-Major taper 2→2→1→1→0; Minor 1→0→1→0→0. R2 had NEW Majors that surfaced FROM the R1 fix expansion (not pre-existing latent — the R1 OperationalError pre-flight wrap revealed adjacent un-covered code paths). R3-R4 progressively tightened the OperationalError scope (connect itself + GET builder ValueError).

---

## §3 Test count delta + ruff baseline + schema version delta

**Fast tests:** 4712 baseline → **4847 fast tests** post-implementation (+135 net).

Above plan §K projection of +81. Driver: T-2.7 parametrize granularity (21 introspection tests instead of 6) + T-2.9 per-route population tests (21 parametrize entries) + Codex chain regression-test additions (+5 R1 + +3 R2 + +4 R3 + +3 R4 = +15 net Codex-driven tests + +3 inline `/dashboard` alias tests). Matches Sub-bundle A+B+C+D Phase 10 overshoot precedent.

**Slow tests:** +1 NEW slow E2E `tests/integration/test_phase12_5_bundle_2_web_tier2_happy_path.py` PASSES in 8.44s (along with the pre-existing Phase 12.5 #1 slow E2E).

**Pre-existing failures:** 3 `tests/integration/test_phase8_pipeline_walkthrough.py` failures unchanged (CLAUDE.md banked baseline; Phase 12.5 #3 triage scope).

**Skipped tests:** 5 unchanged (1 evaluation-patterns; 4 Schwab CSV fixture-gated).

**Ruff:** 18 E501 baseline preserved (`ruff check swing/ --statistics` returns same 18 line-too-long warnings; ZERO new E501 introduced).

**Schema:** **v19 UNCHANGED** (F1 LOCK + F20 escalation rule preserved through entire dispatch; no `0020_*.sql`; no CHECK enum widening; no Python constant; no dataclass validator on `resolved_by`; `resolved_by_override='operator_web'` flows through existing free-TEXT column).

---

## §4 Operator-witnessed verification surfaces (PENDING)

**Status:** PENDING orchestrator-driven gate post-integration-merge. 6 surfaces per plan §H / brief §3.

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline pytest + ruff + slow E2E | TARGET: ~4847 fast + ruff 18 + slow E2E PASS. **Inline run verified GREEN at return-report-drafting time.** |
| **S2** | Banner-link navigation | Operator drives via `python -m swing.cli web --port 8081` worktree-side; visit `/dashboard` (or `/`); verify banner `<a href="/reconcile/discrepancy/{id}/resolve" data-banner-resolve-link="true">` wraps count text; click → resolve form. Pre-condition: at least one pending-ambiguity discrepancy seeded. |
| **S3** | Form render with context | `/reconcile/discrepancy/{id}/resolve` renders pre-resolution context section + 10 context pairs + choice menu + hidden `ambiguity_kind_at_render` anchor + custom-value textarea + resolution-reason textarea; ZERO console errors. |
| **S4** | Successful POST + HX-Redirect | Pick `keep_journal_as_is`, type reason, submit → 204 + `HX-Redirect: /dashboard?reconcile_resolved={correction_id}`; browser navigates. DB inspection: `reconciliation_corrections` row with `applied_by='operator'` + `correction_action='operator_resolved_ambiguity'`; `reconciliation_discrepancies.resolved_by='operator_web'`. **PRODUCTION WRITE** — operator pre-authorizes per-invocation. |
| **S5** | Banner-clears post-resolve | Dashboard re-renders post-S4: banner count drops by 1; if no other pending-ambiguity rows, banner suppressed entirely. |
| **S6** | CLI/web parity | Resolve a second seeded discrepancy via `python -m swing.cli journal discrepancy resolve-ambiguity ...`; assert `resolved_by='operator'` (CLI) vs `'operator_web'` (web from S4) distinguishability + semantic-shape projection of `reconciliation_corrections` rows matches verbatim (excluding identity/time/source-row fields per spec §13.3 R2 LOCK). |

**Production state:** 6 pending-ambiguity discrepancies in production at dispatch time (DHC #52 + VSAT #53 + 4 from runs #67 + #68); gate consumes these as natural fixtures. Post-gate: banner count expected 6 → 4 (S4 + S6 each resolve one).

---

## §5 Per-task deviations from plan (if any)

**Plan-vs-implementation deviations** (none required V2.1 §VII.F amendment; all minor refinements):

1. **T-2.2 `ReconcilePreResolutionContext` field count** — plan §A acceptance said "14 fields"; spec §5.2 enumerates **15 fields** (counted `parse_warning`). Implementation followed spec; plan-author undercount banked as benign.

2. **T-2.5/T-2.6 cross-column CHECK in test seed** — `test_get_returns_409_for_terminal_resolution` seeds with `resolution='operator_resolved_ambiguity'` AND non-null `ambiguity_kind` together to satisfy migration 0019's cross-column CHECK; route's OR-shaped 409 predicate still fires on the non-pending resolution. Test docstring documents this nuance.

3. **T-2.7 plan class-name drift** — plan §C.1 listed `TradesPageVM/TradeEntryFormVM/TradeEntryReviewVM/TradeDetailVM` for `trades.py` and `SchwabStatusVM` at `schwab.py:558`; actual classes via AST scan are `ReviewVM/CadenceCompleteVM/ReviewsPendingVM/TradeDetailVM` (trades) and `SchwabSetupErrorVM` (`schwab.py:558`). Implementer used actual class names. Field line-numbers were correct. **Banked as V2.1 §VII.F amendment candidate** (plan-author class-label drift; line-numbers OK).

4. **T-2.8 retrofit-completeness audit `rg` → `pathlib.rglob`** — `ripgrep` not on PATH in this Windows shell. Test uses `pathlib.Path.rglob` + `re.compile` with the identical regex. Functionally equivalent + more portable; the discriminating contract holds.

5. **T-2.9 Pass B grep count 21 → 24** — plan §C.5 grep at drafting time enumerated 21 callsites; re-running grep at task time found 3 ADDITIONAL callsites (added by T-2.5/T-2.6 reconcile route + T-2.3 builder which now consumes the helper). Per F11/F21 LOCK ("every match site retrofitted; not the listed N sites only"), all 24 retrofitted. Banker as expected drift, NOT a deviation.

6. **T-2.10 ASCII audit source-scan not rendered-HTML scan** — `base.html.j2` carries pre-existing non-ASCII glyphs (em-dashes/`§`/`→` in `<script>` comments + theme-toggle emoji); rendered-HTML scan would require allowlisting unrelated chars. Source-scan of NEW template content is exact + matches T-2.4 precedent.

7. **T-2.11 `CLAUDE.md` edit DEFERRED** to Phase 12.5 #3 maintenance pass per dispatch brief; only `docs/cycle-checklist.md` modified.

**Codex-chain implementation refinements** (rounds 1-4 fixes):

- **R3 Minor #1 builder `ValueError` classification** — branched on substring match (`"not found"` / `"is not pending_ambiguity_resolution"` / `"is no longer in pending"` / else) rather than restructuring the builder to use typed exceptions. Minimal change; documenting comment cites builder's 3 exception causes for forward-binding.
- **R4 Major #1 helper extraction** — `_classify_builder_value_error` private helper centralizes the 3-case 404/409/500 dispatch in ONE place; both GET handler and `_render_form_with_error` delegate.

---

## §6 Codex Major findings ACCEPTED with rationale

**ZERO** Major findings ACCEPTED-with-rationale. All 6 cumulative Major findings RESOLVED with code-content fixes.

**1 Minor ACCEPTED-with-rationale** (R1 Minor #1):

- `ReconcileDiscrepancyErrorVM.error_kind` accepts any non-empty string + template has generic fallback branch.
- **Rationale:** plan §A T-2.10 acceptance + L-W5 LOCK (Codex R3 M#1 fix at writing-plans) explicitly forbid tightening the validator with a `Literal` type — late `__post_init__` tightening would risk breaking T-2.5/T-2.6 already-green paths whose call sites don't contract for a non-empty `error_message` on every error_kind. Banked as advisory.

---

## §7 Watch items for orchestrator

**Phase 12.5 #3 dispatch readiness:**

- V2.1 §VII.F amendment candidates banked from this dispatch:
  - **A1**: Plan §C.1 class-name drift in `trades.py` + `schwab.py` (4 names mis-labeled; line numbers correct).
  - **A2**: Plan §K projection (+81 fast tests) ran +135 actual; matches Sub-bundle precedent for parametrize-granularity overshoot.
  - **A3**: Plan §A T-2.2 acceptance count "14 fields" for `ReconcilePreResolutionContext` vs spec §5.2 actual 15 (plan undercount).
- The pre-Codex orchestrator-side review (NEW C.C lesson #6 BINDING) caught the `/dashboard` HX-Redirect target-unrouted issue. Pattern: **inline gate-fix BEFORE Codex** when a plan-level LOCK references an unrouted path; saves a Codex round.
- Worktree husk at `.worktrees/phase12-5-bundle-2-web-tier2-executing-plans/` pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass (branch matches `phase\d+[-_]` regex).

**V2 candidates banked from Codex chain** (deferred to future dispatches):

1. R1 Minor #1 → V2: `Literal['not_found', 'already_resolved', 'anchor_mismatch', 'service_error', 'db_unavailable']` typing for `ReconcileDiscrepancyErrorVM.error_kind` once Phase 12.5 #2 has shipped + stabilized in production.
2. R3 Minor #1 follow-up → V2: replace substring-match ValueError classification with typed builder exceptions (`DiscrepancyNotFoundError` / `DiscrepancyTerminalStateError` / `DiscrepancyInvariantError`) for cleaner dispatch.

---

## §8 Worktree teardown status

- Worktree branch `phase12-5-bundle-2-web-tier2-executing-plans` is intact + ready for integration merge.
- Marker file `c:\Users\rwsmy\swing-trading\.copowers-subagent-active` REMOVED at return-report-drafting time.
- On-disk worktree at `.worktrees/phase12-5-bundle-2-web-tier2-executing-plans/` pending operator's cleanup-script post-merge.

---

## §9 Per-task disposition LOCKS

All 11 plan tasks (T-2.1 → T-2.11) SHIPPED. Each ships green standalone (verified by per-task pytest sweep at commit time).

L-W1 stub-then-extend ordering preserved verbatim: T-2.5 stubbed 2 error-template branches; T-2.6 extended 3 more inline with route wiring; T-2.10 polish-only.

L-W2 race fix preserved verbatim: POST `ValueError` catch in `swing/web/routes/reconcile.py` re-reads via FRESH `sqlite3.connect` (NOT the same conn); routes 14a (400 if re-read confirms pending) vs 14b (409 if re-read shows terminal); discriminating test pins via separate-connection + commit semantics.

L-W4 plan-supersedes-spec preserved: spec §J2 (ValueError 14a/14b split) + J3 (parametric valid_choices) treated as binding; the spec text itself was NOT amended at this dispatch (Phase 12.5 #3 channel).

L-W5 additive validator preserved: BaseLayoutVM + 13 standalone-VM `banner_resolve_link` field default `None`; ZERO regressions on existing callers.

---

## §10 Forward-binding lessons for future bundles

**5 NEW lessons banked from Phase 12.5 #2 executing-plans** (extending plan §M's L-W1..L-W5 from writing-plans):

- **L-E1: Pre-Codex orchestrator-side review absorbed 1 Major-class finding pre-chain.** The `/dashboard` HX-Redirect target-unrouted issue (Phase 6 I3 family) was caught + closed inline before R1, saving a likely Codex Major. **NEW C.C lesson #6 validated for the 3rd time** (post Sub-bundles C.C + C.D + Phase 12.5 #1 + #2).

- **L-E2: OperationalError pre-flight scope cascades.** R1 fix wrapped the service call; R2 surfaced 2 NEW Majors as the wrap revealed adjacent un-covered paths (`_render_form_with_error` builder call + sibling-except cascade gap on race re-read); R3 surfaced the connect() itself; R4 surfaced the GET-side builder ValueError. **Pattern:** when adding exception handling, audit EVERY adjacent code path that can raise the same exception class — Python sibling-except clauses do not cascade, and each newly-uncovered helper/builder call is a new failure surface. Discriminating-test pattern per finding: patch the specific raising target + assert the intended status_code + body discriminator.

- **L-E3: Builder `ValueError` cause classification belongs in a SHARED helper.** R4 fix extracted `_classify_builder_value_error` so both the GET handler + the POST `_render_form_with_error` re-render path use the SAME 3-case dispatch (404/409/500). **Pattern:** when more than one route call-site catches the same exception class with the same disposition logic, extract to a private helper BEFORE Codex catches the second mis-mapping. **V2 candidate:** replace substring-match with typed builder exceptions when project tolerance for new exception classes increases.

- **L-E4: Plan-class-name drift surfaces via Pass A grep at task time.** T-2.7 plan §C.1 listed wrong VM class names for `trades.py` + `schwab.py:558`; implementer used actual classes via AST scan. **Pattern:** when plan-author enumerates target classes by `<file>:<line>`, the line numbers are authoritative but class names should be re-derived at task time. Plan-author check: AST-grep at plan-drafting time (not just file:line manual enumeration).

- **L-E5: Pass B grep count drifts during dispatch.** Plan-drafting grep enumerated 21 callsites; task-time grep found 24 (T-2.5/T-2.6 + builder added 3 more). F11/F21 LOCK ("every match site retrofitted") handled this gracefully. **Pattern:** plan §K projections (test counts, LOC) are first-order; Pass B grep counts can drift +N as the dispatch's own NEW code lands. Per-callsite acceptance contract MUST be "every match" not "the N listed".

---

## §11 CLAUDE.md status-line refresh draft text (orchestrator paste-in)

For orchestrator paste-in at integration-merge time, after the existing 2026-05-18 Phase 12.5 #2 writing-plans entry:

> **Phase 12.5 #2 (Web Tier-2 Discrepancy-Resolution Surface — CLOSES Phase 12.5 #2 arc) SHIPPED 2026-05-18** at `<MERGE-SHA>` (integration merge of `phase12-5-bundle-2-web-tier2-executing-plans` via `--no-ff`; 16 task-branch commits = 11 task-impl (T-2.1..T-2.11) + 1 orchestrator-inline `/dashboard` route-alias gate-fix at `25f4554` (Phase 6 I3 HX-Redirect-target-unrouted gotcha pre-Codex; **NOW 4 inline gate-fix instances cumulatively** — 12A `e2c0384`, 12B `7b75d4a`, 11B `34be84e`, 12.5 #2 `25f4554`) + 4 Codex-fix bundles (R1+R2+R3+R4); **5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent monotonic-Major taper (R1 0C/2M/1m → R2 0C/2M/0m → R3 0C/1M/1m → R4 0C/1M/0m → R5 0C/0M/0m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 6 cumulative Major findings resolved with code-content fixes; ZERO Co-Authored-By footer drift across 16 commits (~163+ project-cumulative streak preserved); **+135 fast tests** (4712 → 4847 main HEAD post-merge; above plan §K projection +81 driven by T-2.7 parametrize granularity + T-2.9 Pass B 24-callsite-not-21 + Codex chain regression pins); ruff 18 E501 unchanged; schema v19 UNCHANGED (F1 LOCK preserved entire dispatch). **First operator-visible web Tier-2 surface** — `GET /reconcile/discrepancy/{id}/resolve` renders dedicated form page with pre-resolution context section above choice menu (operator-LOCK §2.4); `POST /reconcile/discrepancy/{id}/resolve` consumes existing `apply_tier2_resolution(resolved_by_override='operator_web')` service entry; HX-Redirect to `/dashboard?reconcile_resolved={correction_id}` (operator-LOCK §D #2/#8/#9 verbatim; `/dashboard` alias added at `25f4554` closing Phase 6 I3 gotcha). NEW `swing/web/view_models/reconcile.py` (~860 LOC) + NEW `swing/web/routes/reconcile.py` (~720 LOC) + NEW `reconcile_discrepancy_resolve.html.j2` + `reconcile_discrepancy_resolve_error.html.j2` (5-branch error template; L-W1 stub-then-extend pattern preserved verbatim — T-2.5 stubs 2 branches, T-2.6 extends 3 more inline, T-2.10 polish-only); `BaseLayoutVM.banner_resolve_link: str | None = None` + 13-VM Pass A retrofit + `swing/metrics/discrepancies.py` 2 new helpers (`list_pending_ambiguities_in_banner_set` + `fetch_first_pending_ambiguity_resolve_link_path`) + 24-callsite Pass B retrofit (3 more than plan grep's 21 — F11/F21 every-match-not-N-listed contract handled). Codex R1-R4 progressively tightened defensive exception handling: type-invalid payload graceful degradation (`KeyError|ValueError|TypeError` catch); `sqlite3.OperationalError` 503 mapping at connect() + pre-flight reads + service call + re-render builder + race re-read (sibling-except cascade gap closed at R2); builder `ValueError` 3-cause classification (`not_found` 404 / `already_resolved` 409 / `service_error` 500) extracted as shared `_classify_builder_value_error` helper at R4. **6-surface operator-witnessed gate PENDING orchestrator-driven post-merge** (S1 inline pytest+ruff+slow E2E; S2 banner-link nav; S3 form-render with pre-resolution context; S4 successful POST + HX-Redirect + `resolved_by='operator_web'` write; S5 banner-clears; S6 CLI/web parity). **5 NEW forward-binding lessons L-E1..L-E5** banked at return-report §10 — pre-Codex review absorbs Major-class findings; OperationalError pre-flight scope cascades through adjacent paths; builder ValueError classification belongs in shared helper; plan-author class-name drift catches via AST-grep; Pass B grep count drifts +N during dispatch. **Sub-bundle B T-B.7 PROMISE FULFILLED separately** — Phase 12 Sub-bundle B deferred T-B.7 (web counterpart to CLI Tier-2 surface) is now SHIPPED via this dispatch. **Phase 12.5 #3 dispatch UNBLOCKED** (project-hygiene maintenance pass: CLAUDE.md+orchestrator-context archive-split + V2.1 §VII.F amendment batch including 3 new A1/A2/A3 from this dispatch + Phase 8 walkthrough failing-test triage + Ruff 18 E501 cleanup). Worktree husk at `.worktrees/phase12-5-bundle-2-web-tier2-executing-plans/` pending cleanup-script `-DeregisterFirst` pass.

---

## §12 Composition-surface verification (`^def ` grep on touched modules)

```
$ grep -n '^def \|^async def \|^class ' swing/web/view_models/reconcile.py
```

Verified at return-report time: 3 frozen dataclasses (`ReconcileChoiceFormItem`, `ReconcilePreResolutionContext`, `ReconcileDiscrepancyResolveVM`, `ReconcileDiscrepancyErrorVM`) + 10 per-discrepancy-type render helpers + dispatch + builder + generic fallback + `_parse_parametric_pick_count` helper.

```
$ grep -n '^def \|^async def \|^class ' swing/web/routes/reconcile.py
```

Verified: APIRouter + GET handler `reconcile_discrepancy_resolve_form` + POST handler `reconcile_discrepancy_resolve_post` + 4 private helpers (`_render_error`, `_render_form_with_error`, `_reread_discrepancy_resolution`, `_classify_builder_value_error`).

```
$ grep -n '^def \|^class ' swing/metrics/discrepancies.py | tail -8
```

Verified: 2 NEW helpers (`list_pending_ambiguities_in_banner_set`, `fetch_first_pending_ambiguity_resolve_link_path`); existing `count_unresolved_material` + `count_recent_multi_leg_auto_corrections` UNCHANGED.

---

## §13 Pre-existing LOCK regression evidence

- **`apply_tier2_resolution` external surface UNCHANGED** — `git diff 3416e1e..HEAD -- swing/trades/reconciliation_auto_correct.py` shows ZERO changes to the service-entry signature (verified at return-report time). Web POST consumes the existing `resolved_by_override` kwarg shipped at Phase 12.5 #1 T-1.4.
- **CLI surface UNCHANGED** — `git diff 3416e1e..HEAD -- swing/cli.py` shows ZERO changes (LOCK #11 + F12).
- **Phase 12.5 #1 banner UNCHANGED** — `base.html.j2` banner block edit is ADDITIVE (wraps existing count text in conditional `<a>`); pre-existing `⚠` glyph + Phase 12.5 #1 `recent_multi_leg_auto_correction_count` block + Phase 10 `unresolved_material_discrepancies_count` predicate UNCHANGED.
- **Sub-bundle B routes UNCHANGED** — `swing/web/routes/schwab.py` only gained the `_fetch_banner_resolve_link(db_path)` sibling helper + Pass B callsite kwargs (additive); no behavioral change to existing schwab routes.
- **Schema v19 UNCHANGED** — `git diff 3416e1e..HEAD -- swing/data/migrations/` empty.

---

## §14 F1-F21 invariants verification matrix

| # | Invariant | Status | Evidence |
|---|---|---|---|
| F1 | ZERO new schema | PASS | `git diff -- swing/data/migrations/` empty; v19 unchanged |
| F2 | `resolved_by_override='operator_web'`; CLI `'operator'` unchanged | PASS | `swing/web/routes/reconcile.py:584` POST handler; CLI body unchanged |
| F3 | ZERO change to `apply_tier2_resolution` legacy default | PASS | service-entry signature unchanged; web is new caller only |
| F4 | `hx-headers='{"HX-Request": "true"}'` on form | PASS | `reconcile_discrepancy_resolve.html.j2:54` |
| F5 | 204 + HX-Redirect on success (NOT 303) | PASS | `swing/web/routes/reconcile.py:724-728` |
| F6 | `... or None` for nullable text columns | PASS | POST handler form parsing |
| F7 | NO `with conn:` at route | PASS | route uses `try: ... finally: conn.close()`; service-layer owns BEGIN IMMEDIATE |
| F8 | `ambiguity_kind_at_render` hidden anchor + POST validation | PASS | template:67 + POST handler checks |
| F9 | Custom-value fieldset ALWAYS rendered | PASS | template:82-94 |
| F10 | Parametric picks ALWAYS require custom_value | PASS | POST handler step 3g |
| F11/F21 | Pass A grep retrofit completeness audit at TEST TIME | PASS | `tests/web/test_base_layout_banner_resolve_link.py:test_retrofit_completeness_audit_via_pass_a_grep` |
| F12 | ASCII-only NEW template text; `⚠` carve-out | PASS | F12 audit tests in T-2.4 + T-2.8 + T-2.10 |
| F13 | try/finally conn.close() on all paths | PASS | route handlers + `_reread_discrepancy_resolution` helper |
| F14 | `apply_overrides(cfg)` at every web route entry | PASS | both handlers; `test_get_calls_apply_overrides` + `test_post_calls_apply_overrides` pin |
| F15 | HX-Redirect target route registered | PASS | `/dashboard` alias added at `25f4554`; `tests/web/test_dashboard_route_aliases.py` pins |
| F16 | Sandbox short-circuit applies ONLY to auto-redirect | PASS | web V1 never triggers auto-redirect triple |
| F17 | `InvalidOverrideComboError` should never fire from web POST | PASS | catch-ladder maps to 500 service_error as defense-in-depth |
| F18 | Audit-row parity via semantic-shape projection | PASS | `tests/integration/test_phase12_5_bundle_2_cli_web_parity.py` |
| F19 | NO Co-Authored-By footer | PASS | `git log 3416e1e..HEAD | grep -i co-authored` returns 0 matches across 16 commits |
| F20 | Plan-author schema escalation rule | PASS | F20 NOT triggered; no schema additions surfaced |

**All 21 invariants PASS.**

---

## §15 13 forward-binding lessons consumption verification

Plan §M's 13 forward-binding lessons (8 inherited + 5 NEW L-W1..L-W5):

1. Brief-conjecture-vs-actual-schema gap → grep verify — **CONSUMED** at task time (T-2.9 re-ran Pass B grep; found 24 not 21).
2. BaseLayoutVM-inheritance asymmetric — **CONSUMED** at T-2.7 (13 standalone VM retrofit, not via inheritance).
3. Hidden state anchors distinct from hidden audit fields — **CONSUMED** at T-2.4/T-2.6 (`ambiguity_kind_at_render` is anchor; `resolved_by` is server-stamped audit).
4. OriginGuard strict-vs-non-strict 303-fallback shapes — **CONSUMED** at T-2.6 (POST handler emits 204 + HX-Redirect under HTMX; 303 RedirectResponse under non-HTMX fallback).
5. Banner-link targets derive from canonical helper — **CONSUMED** at T-2.9 (`fetch_first_pending_ambiguity_resolve_link_path` consumes the same trade-set as `count_unresolved_material`).
6. Audit-row parity via semantic-shape projection — **CONSUMED** at T-2.11 (`test_cli_web_audit_row_semantic_shape_parity`).
7. Grep-driven audits split by intent — **CONSUMED** at T-2.7/T-2.9 (Pass A field-declaration vs Pass B call-site population grep).
8. Retrofit completeness as discriminating test — **CONSUMED** at T-2.8 (`test_retrofit_completeness_audit_via_pass_a_grep` runs grep at test time + asserts via `dataclasses.fields` introspection).
9. **L-W1 stub-then-extend ordering** — **CONSUMED** at T-2.5/T-2.6/T-2.10 (T-2.5 stubs 2 branches, T-2.6 extends 3 more inline, T-2.10 polish-only).
10. **L-W2 service `ValueError` re-read disambiguation** — **CONSUMED** at T-2.6 (`_reread_discrepancy_resolution` opens FRESH `sqlite3.connect`; 14a/14b 400/409 split; discriminating test pinned via separate-connection + commit semantics).
11. **L-W3 F# cross-reference accuracy audit** — **CONSUMED** at plan-drafting; ZERO cross-reference drift surfaced in implementation.
12. **L-W4 Spec-out-of-sync → plan supersedes** — **CONSUMED** at T-2.3 (builder kwarg J1 amendment) + T-2.6 (J2 + J3 amendments) treated as binding without spec rewrite.
13. **L-W5 Late VM-validator additions additive** — **CONSUMED** at T-2.7 (`banner_resolve_link: str | None = None` default-None-pass; ZERO regressions on existing callers).

**All 13 lessons consumed and verified in implementation.**

---

*End of return report. Phase 12.5 #2 executing-plans dispatch SHIPPED. Operator-witnessed gate PENDING orchestrator-driven post-integration-merge. 16 commits / 5 Codex rounds / ZERO ACCEPT-WITH-RATIONALE / ZERO Co-Authored-By footer drift. 4847 fast tests green. Ruff 18 unchanged. Schema v19 unchanged. Slow E2E PASS.*
