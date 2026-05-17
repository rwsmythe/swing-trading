# Phase 12 Sub-sub-bundle C.D — Executing-plans return report

**Status:** SHIPPED on branch `phase12-bundle-C-D-tier2-cli-and-backfill`; awaiting 10-surface operator-witnessed gate per plan §G.4. **CLOSES Sub-bundle C.**

**Plan:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` §E (16 tasks T-D.1..T-D.14 + T-D.6.1).

**Spec:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` §6 / §8 / §15.5.

**Dispatch brief:** `docs/phase12-bundle-C-D-tier2-cli-and-backfill-executing-plans-dispatch-brief.md`.

**Baseline SHA:** `047e3db` (post-C.C-merge handoff brief commit).

---

## §1 Final HEAD + commit count breakdown

**Final HEAD on branch:** `fa3eca4`.

**Total commits on top of baseline:** 26.

| Class | Count | Commits |
|---|---|---|
| Task implementations (15 distinct tasks) | 15 | `7fcee8b` T-D.1 + `20f3482` T-D.2 + `420dca0` T-D.3 + `2c092fa` T-D.4 + `099d2f4` T-D.5 + `fbaeece` T-D.6 + `f91ced2` T-D.6.1 + `7ccf76f` T-D.7 + `0750322` T-D.8 + `aff1ebc` T-D.9 + `8ac2c0e` T-D.10 + `0b4f57d` T-D.11 + `81ed09a` T-D.12 + `e221000` T-D.13 + `65c0432` T-D.14 |
| Pre-Codex orchestrator-side review fix | 1 | `e53e8dc` (Item 2 overlap rendering + Item 6 terminal-state exclusion test) |
| Codex R1 fixes (3 Major + 2 Minor) | 4 | `38ee043` M#1 + `529b804` M#2 + `cc55cbf` M#3 + `e6f5d7e` Minors #1+#2 |
| Codex R2 fixes (3 Major + 1 Minor) | 4 | `5cc352f` M#1 + `c9eb9ef` M#2 + `20c4ee5` M#3 + `7188bf6` Minor #1 |
| Codex R3 fix (1 Minor) | 1 | `45b9726` Minor #1 |
| Codex R4 fix (1 Minor) | 1 | `fa3eca4` Minor #1 (stale-comment polish) |

**ZERO `Co-Authored-By` footers across all 26 commits** (verified via `git log --format="%B" 047e3db..HEAD \| grep -i co-author` → 0 matches). C.B forward-binding lesson #7 carry-forward worked end-to-end.

## §2 Codex round chain

| Round | Critical | Major | Minor | Disposition | Verdict |
|---|---|---|---|---|---|
| Pre-Codex orchestrator review | 0 | 1 | 1 (+3 banked Minor + 3 Observation for return report) | All resolved at `e53e8dc` | ABSORBED |
| R1 | 0 | 3 | 2 | All resolved in-tree at commits `38ee043` + `529b804` + `cc55cbf` + `e6f5d7e` | ISSUES_FOUND |
| R2 | 0 | 3 | 1 | All resolved in-tree at commits `5cc352f` + `c9eb9ef` + `20c4ee5` + `7188bf6` | ISSUES_FOUND |
| R3 | 0 | 0 | 1 | Resolved at `45b9726` (label narrowing) | NO_NEW_CRITICAL_MAJOR |
| R4 | 0 | 0 | 1 | Resolved at `fa3eca4` (stale-comment polish) | NO_NEW_CRITICAL_MAJOR |

**Convergent tapering:** R1 0C/3M/2m → R2 0C/3M/1m → R3 0C/0M/1m → R4 0C/0M/1m. **Within projected 4-6 substantive Codex rounds per brief §0.3.** Two NO_NEW_CRITICAL_MAJOR rounds back-to-back at R3+R4 confirm convergence.

**ZERO Critical findings** entire chain.

**ZERO ACCEPT-WITH-RATIONALE banked** — all 6 Critical+Major findings (3 R1 + 3 R2) + 5 Minor findings (2 R1 + 1 R2 + 1 R3 + 1 R4) + 1 Major + 1 Minor at pre-Codex review = **all 14 findings resolved with code-content fixes**. Matches Phase 12 C.A (1 banked) / C.B (0 banked) / C.C (0 banked) clean-record arc precedent; ties cleanest sub-sub-bundle in Phase 12 arc.

## §3 Test count + ruff + schema deltas

| Metric | Pre-baseline (047e3db) | Post-C.D (fa3eca4) | Delta |
|---|---|---|---|
| Fast tests passing | 4204 | 4360 | **+156** |
| Pre-existing failures (phase8 walkthrough) | 3 | 3 | unchanged |
| Skipped | 5 | 5 | unchanged |
| Ruff E501 | 18 | 18 | unchanged |
| Schema version | 19 | 19 | unchanged |

**+156 fast tests** above projection +55-80 (upper bound +120 per overshoot precedent); matches Phase 9/10/12 arc-cumulative overshoot pattern.

**Schema v19 unchanged** — C.D adds NO schema (per brief §0.4 + C.A lesson #7 + spec §A.0). All new functionality is consumer-side over C.A's v18→v19 schema.

## §4 Operator-witnessed verification surfaces (PENDING orchestrator-driven gate)

10 surfaces per plan §G.4 + spec §15.5 LOCKED revised mechanic. Pending operator's session. Pre-gate operator check: **verify Schwab refresh-token TTL > 1hr** (production token expires ~2026-05-22T17:05:00+00:00 per Phase 12 Sub-bundle B ship date).

- **S1** inline `pytest -m "not slow" -q -n auto` GREEN at 4360 fast tests; 3 pre-existing phase8 walkthrough failures unchanged. T-D.11 slow-marked PASS under `-m slow` (18 cases — 11 payload-required + 7 no-payload).
- **S2** `swing journal reconcile-backfill --dry-run` against production. Expects: classification matrix with disc 41 CVGI projected tier-1 + disc 39 DHC + disc 40 VSAT projected Pass-2-required + per-discrepancy `call_id` printout.
- **S3** `swing journal reconcile-backfill --apply --ticker CVGI` against production. PRODUCTION WRITE; expects disc 41 → tier-1 auto-correct with `fills.price=$5.30` + `reconciliation_corrections` row + `trade_events` row.
- **S4** `swing journal reconcile-backfill --apply --ticker DHC` + `--ticker VSAT` (separate OR single invocation). PRODUCTION WRITE; expects tier-2 stamps with `resolution='pending_ambiguity_resolution'` + Phase 10 banner count=2.
- **S5** `swing journal discrepancy show-ambiguity 39` — verifies menu output + `[RECOMMENDED]` tag.
- **S6** S6a synthetic-fixture acceptance test (T-D.11 `@pytest.mark.slow` table-driven 18 cases) + S6b operator real-disposition of DHC 39 per actual data.
- **S7** `show-ambiguity 40` + `resolve-ambiguity 40` for VSAT 40.
- **S8** Phase 10 dashboard banner clears to ZERO via `swing web --port 8081`.
- **S9** `ruff check swing/ --statistics` reports 18 E501 unchanged.
- **S10** Cycle-checklist + CLAUDE.md gotcha additions verified.

## §5 Per-task deviations from plan (with rationale)

1. **T-D.1** plan example used `planted_3_pending_ambiguities` fixture name; implementer used local helpers (`_seed_three_pending`). Defensible (no global fixture exists pre-T-D.1). Banked as Observation.
2. **T-D.1** `reconciliation_runs.source='manual_tos'` in plan example; v17 CHECK enum is `('tos_csv', 'schwab_api', 'manual', 'system_audit')`. Used `'tos_csv'`. Test-local choice; no V2.1 §VII.F amendment.
3. **T-D.2** Parametric `pick_schwab_record_<N>` derived best-effort via regex on classifier's `resolution_reason` text. Fragile if classifier wording drifts; spec §I.13 already banks `candidate_choices_json` column as V2 candidate.
4. **T-D.3** Back-link asymmetry: shipped C.C tier-2 handlers stamp the forward FK (`reconciliation_corrections.schwab_api_call_id`) but do NOT invoke `_back_link_schwab_api_call`. CLI now back-links via `update_call_linked_correction` in separate immediate transaction AFTER service returns. **V2.1 §VII.F amendment candidate** — cleaner long-term placement at service layer.
5. **T-D.4** Cross-CLI exit-code asymmetry: `AlreadySupersededError` → exit 2 (`UsageError`) at override-correction; → exit 1 (`ClickException`) at resolve-ambiguity. Intentional per brief criterion #6. **V2.1 §VII.F amendment candidate** if operator prefers uniformity.
6. **T-D.10** plan §A.5 said "14 base-layout VMs across 9 files"; actual count per grep is **13 across 9 files** (`config.py` + `journal.py` + `error.py` + `watchlist.py` + `pipeline.py` + `dashboard.py` + `schwab.py` ×2 + `trades.py` ×4 + `metrics/shared.py`). Test suite covers 13. **V2.1 §VII.F amendment candidate** — plan-text correction.
7. **T-D.11** plan example `pick_schwab_record_1` payload key was `qty`; CLI documentation + classifier dispatch use `quantity` (matching `fills` schema column). Test uses `quantity`. **V2.1 §VII.F amendment candidate** — plan-text correction.
8. **T-D.11** Audit-only assertion compares applied_value_json bytewise including the `field_name`-keyed wrapper (`{"price": <value>}`); plan didn't enumerate wrapper shape. Defensible (matches C.C handler implementation). Banked as Observation.
9. **R1 M#1 fix** Dry-run mode WITHOUT `--no-pass-2-on-dry-run` soft-fails (advisory) when credentials/account_hash missing rather than hard-failing — defensible UX (operator should preview against pre-Phase-11 DBs without configuring Schwab); `--apply` hard-fails. Banked as Observation in pre-Codex review; Codex R2 M#1 caught the wrong-exception-type bug (resolved at `5cc352f`).
10. **R1 M#3 fix** Per-iteration `_check_pipeline_not_running` (lightest defensive); R2 M#2 added per-service-write recheck closing the in-row window. Stronger than brief's alternative ACCEPT-WITH-RATIONALE path.

## §6 Codex Major findings ACCEPTED with rationale (if any)

**NONE.** All 6 Major findings (3 R1 + 3 R2) resolved in-tree with code fixes and discriminating tests. Matches arc-cumulative ZERO ACCEPT-WITH-RATIONALE record entering this dispatch.

## §7 Watch items for orchestrator (V2 candidates + Sub-bundle C arc-closer readiness)

**V2 candidates banked (pending phase3e-todo entries):**
- Service-layer placement of `schwab_api_call_id` back-link FK (currently CLI does it post-service); cleaner at service layer (deviation #4 above).
- Cross-CLI exit-code uniformity for `AlreadySupersededError` (deviation #5).
- `surface='backfill'` enum widening if/when operator wants to distinguish backfill-CLI from interactive-CLI invocations in `schwab_api_calls` audit rows.
- `candidate_choices_json` column on `reconciliation_discrepancies` (already banked at spec §I.13).
- `ClassificationResult.pass_2_required: bool` dedicated field replacing the free-form `_pass_2_required=True` substring in `correction_reason` (cleaner C.B → C.D interface; current convention works but is fragile).
- `pass_2_failed` overlap-rendering future evolution: consider explicit `apply_mode_pass2_failed` field name distinguishing from dry-run failure modes.

**Sub-bundle C arc-closer aggregate readiness:** see §11 below.

## §8 Worktree teardown status

- Branch `phase12-bundle-C-D-tier2-cli-and-backfill` ready for `--no-ff` integration merge to main.
- Marker file `.copowers-subagent-active` REMOVED at session end.
- On-disk worktree at `.worktrees/phase12-bundle-C-D-tier2-cli-and-backfill/` will be ACL-locked post-merge; operator's cleanup-script `-DeregisterFirst` pass handles teardown. Branch name `phase12-bundle-C-D-*` matches `(phase\d+[-_]|schwab(?:-\w+)?-bundle-)` regex per Phase 12 Sub-bundle A T-A.4 ship.

## §9 Per-task disposition LOCKs

- **T-D.6 autocommit LOCK preserved** — `BEGIN IMMEDIATE` absent from `swing/trades/reconciliation_backfill.py`. Verified via grep + Codex R1+R2 review. Service helpers (C.C `apply_*` + `stamp_pending_ambiguity`) own their own txs.
- **T-D.8 Pass-2-tier-1-FORBIDDEN LOCK preserved** — `tests/trades/test_reconciliation_backfill_pass2.py::test_pass_2_tier_1_forbidden_even_when_qty_and_price_match` (matching qty AND price → still tier-2) pins the LOCK.
- **T-D.11 synthetic-fixture-only LOCK preserved** — runs against isolated `tmp_path` DBs; production DB untouched.
- **NO schema additions** — schema v19 unchanged. Migration directory unchanged. `EXPECTED_SCHEMA_VERSION == 19`.
- **R1 M#3 in-row race closure** at R2 M#2 — per-service-write rechecks at 3 callsites (`apply_tier1_correction` + Pass-1 `stamp_pending_ambiguity` + Pass-2 `stamp_pending_ambiguity`).
- **R2 M#3 partial-summary contract LOCKED** — `BackfillPipelineActiveError.partial_summary: BackfillSummary | None` carries committed-row state; `BackfillSummary.aborted_mid_iteration: bool` + `abort_reason: str | None` surface in summary block.

## §10 Forward-binding lessons for future bundles (especially V2 mapper widening)

1. **Plan example payload-key drift requires implementation alignment with downstream schema.** T-D.11 caught `qty` vs `quantity` mismatch only because the integration test exercised the service-layer dispatch. Pre-empt: writing-plans phase should grep payload-shape examples against actual schema column names.
2. **CLI entry points constructing Schwab clients MUST follow the `apply_overrides(cfg)` + `_resolve_credentials_for_cli` + `_build_schwabdev_client_for_fetch` recipe** (Phase 12 Sub-bundle B forward-binding lesson #6). R1 M#1 caught this — backfill CLI initially had `schwab_client = None` hardcoded.
3. **Per-iteration pipeline-exclusion recheck closes cross-row window; per-service-write recheck closes in-row window.** Both needed for autocommit backfill orchestrators. Per-write cost is one SELECT (~50 production discrepancies).
4. **Partial-progress summary attribute on raised exceptions** — when a flow may abort mid-iteration with committed work, the exception MUST carry the partial accumulator (`BackfillPipelineActiveError.partial_summary` pattern). Pre-empt in any new mid-iteration-abort design.
5. **Counter labels must match counter semantics exactly.** Codex R3+R4 caught label drift twice on `pass_2_projection_unavailable`. Pattern: render-time label SHOULD be derived from the same docstring/constant that documents the counter's increment conditions; OR add a discriminating test asserting label+counter semantics align.
6. **V2 mapper widening dispatch** (operator-locked next-architectural-dispatch slot) unblocks Pass-2-tier-1-FORBIDDEN by exposing execution-grain data; T-D.8 gates this by design. Implementation seam: extend `SchwabOrderResponse` mapper to surface `orderActivityCollection[].executionLegs[]`; classifier's `unmatched_open_fill` sub-classifier currently locks tier-2-always; future redirect to tier-1 `entry_price_mismatch` on execution-grain data.
7. **`get_account_orders_audited` race-free contract** depends on backfill's pipeline-exclusion guard. Any future audited wrapper at other Schwab endpoints (e.g., `get_transactions_audited`) MUST be gated similarly OR use a different concurrency mechanism (e.g., `BEGIN IMMEDIATE` around the audit-row INSERT).

## §11 CLAUDE.md status-line refresh draft + Sub-bundle C arc-closer aggregate

### CLAUDE.md status-line refresh draft (orchestrator paste-in at integration merge time)

```
**Phase 12 Sub-bundle C Sub-sub-bundle C.D (Tier-2 CLI + backfill + Phase 10 banner widening — CLOSES Sub-bundle C) SHIPPED 2026-05-16** at `<merge_sha>` (integration merge of `phase12-bundle-C-D-tier2-cli-and-backfill` via `--no-ff`; 26 commits = 15 task-impl T-D.1..T-D.14 + T-D.6.1 + 1 pre-Codex orchestrator review fix + 10 Codex-fix across 4 rounds + 1 R4 polish; **4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/3M/2m → R2 0C/3M/1m → R3 0C/0M/1m → R4 0C/0M/1m); **ZERO Critical findings**; **ZERO ACCEPT-WITH-RATIONALE banked** — all 6 Major + 5 Minor + 1 pre-Codex Major + 1 pre-Codex Minor resolved with code-content fixes (ties cleanest sub-sub-bundle in Phase 12 arc); **+156 fast tests** (4204 → 4360 worktree-side); ruff 18 unchanged; schema v19 unchanged. Tier-2 CLI surface (`swing journal discrepancy {list-pending-ambiguities,show-ambiguity,resolve-ambiguity,override-correction}`) + `swing journal reconcile-backfill` CLI + Pass 1 / Pass 2 backfill mechanic + `_audited_get_account_orders` race-free audit-chain wrapper + Phase 10 banner predicate widening to include `pending_ambiguity_resolution` (3 SQL predicates; 13-VM regression suite across 9 files — plan said 14 banked as V2.1 §VII.F amendment) + synthetic-fixture payload-contract acceptance test (T-D.11 table-driven across 11 payload-required + 7 no-payload choices; @pytest.mark.slow). **Pre-Codex orchestrator-side review absorbed 1 Major + 1 Minor** (pass_2_failed double-count rendering + retry-pass-2-failures terminal-state exclusion test) saving an estimated 1 Codex round per NEW C.C lesson #6 — pattern validated for the 2nd time. **R1 M#1 fix** caught backfill CLI shipped with `schwab_client = None` hardcoded — would have hard-failed production Pass-2 against real Schwab API; fix wires `apply_overrides(cfg)` + Phase 12 Sub-bundle B credentials-cascade recipe. **R1 M#2 + M#3 fix** closed sandbox-Pass-2 journal-mutation gap + per-iteration pipeline-exclusion race window; R2 M#2 follow-up closed in-row race via per-service-write recheck at 3 callsites. **R2 M#3 fix** added `BackfillPipelineActiveError.partial_summary` for mid-iteration abort transparency. **3 unresolved material discrepancies (39 DHC + 40 VSAT + 41 CVGI) AWAITING operator's 10-surface gate** via `swing journal reconcile-backfill --apply` against production. Worktree teardown: branch `phase12-bundle-C-D-tier2-cli-and-backfill` deleted; on-disk husk ACL-locked at `.worktrees/phase12-bundle-C-D-tier2-cli-and-backfill/` (4th phase12-bundle-c-* husk pending: C-A + C-B + C-C + C-D).
```

### Sub-bundle C arc-closer aggregate (per Phase 9 / Phase 10 / Phase 11 precedent)

**4 sub-sub-bundles A+B+C+D ALL SHIPPED 2026-05-15 → 2026-05-16:**

| Sub-sub-bundle | Ship date | Merge SHA | Commits | Codex rounds | Critical | ACCEPT-WITH-RATIONALE | Fast tests delta | Schema |
|---|---|---|---|---|---|---|---|---|
| C.A (Foundation — v18→v19 schema) | 2026-05-15 | `354b6c0` | 16 | 2 | 0 | 1 | +104 | v18 → v19 |
| C.B (Classifier + validator-shim) | 2026-05-15 | `aacd1cd` | 26 | 5 | 0 (1-Critical-resolved) | 0 | +139 | unchanged |
| C.C (Auto-correction service + flow pivot) | 2026-05-16 | `0b9d253` | 23 | 3 | 0 | 0 | +95 | unchanged |
| C.D (Tier-2 CLI + backfill — CLOSER) | 2026-05-16 | `<merge_sha>` | 26 | 4 | 0 | 0 | +156 | unchanged |
| **Total** | | | **~91** | **14** | **0 (1 resolved)** | **1** | **+494** | v18 → v19 (single migration at C.A) |

**Sub-bundle C arc cumulative:**
- **~91 commits** across A+B+C+D.
- **14 Codex rounds total** (A: 2 + B: 5 + C: 3 + D: 4).
- **ZERO Critical findings entire arc** (1 surfaced + resolved in-tree at C.B R1).
- **1 ACCEPT-WITH-RATIONALE banked** (C.A R1 M#1 backup-gate narrowness; documented + extended docstring).
- **+494 cumulative fast tests** (3858 baseline at start of C.A → 4360 final at C.D worktree-side).
- **Schema v18 → v19 in single migration** at C.A T-A.1 (consumer-side only through B+C+D).
- **6 NEW CLAUDE.md gotchas promoted at C.D T-D.13** (sandbox short-circuit at inner; APPEND-ONLY reconciliation_corrections; Pass-2-tier-1-FORBIDDEN; SAVEPOINT-per-discrepancy; classifier purity; per-choice `--custom-value`).
- **5 V2.1 §VII.F amendments pending** for Sub-bundle C arc routing (in addition to ~12 from C.A+C.B+C.C); see deviation list §5 above.
- **6+ V2 candidates banked** for phase3e-todo (service-layer back-link FK; cross-CLI exit uniformity; `surface='backfill'` enum; `candidate_choices_json` column; `ClassificationResult.pass_2_required` field; V2 mapper widening dispatch slot is operator-locked).

**The architectural pivot to auto-correction reconciliation (Sub-bundle C scope) is end-to-end operational** — 3 unresolved discrepancies (CVGI 41 tier-1 + DHC 39/VSAT 40 tier-2) awaiting operator's gate disposition. Production state remains clean post-gate per spec §15.5.

## §12 Composition-surface verification

`^def ` grep on the two new modules confirms public surface matches plan §E acceptance criteria:

**`swing/trades/reconciliation_ambiguity_choices.py`** (helper module — PURE; no DB; no I/O):
- `ChoiceMenuItem` dataclass with `code` + `description` + `requires_custom_value` + `recommended` + `expected_payload_shape_description`.
- `get_choice_menu(ambiguity_kind: str) -> list[ChoiceMenuItem]` returns helper-module member list; covers all 7 ambiguity_kinds + parametric `pick_schwab_record_<N>` for `multi_match_within_window`.

**`swing/trades/reconciliation_backfill.py`** (orchestrator module — autocommit):
- `BackfillOutcome` dataclass (12 fields including `pass_2_call_id`).
- `BackfillSummary` dataclass (8 counters + `per_discrepancy_outcomes` + `aborted_mid_iteration` + `abort_reason`).
- `BackfillPipelineActiveError(Exception)` with `.partial_summary` attribute.
- `run_backfill(conn, *, dry_run, schwab_client, environment, account_hash, ticker=None, limit=None, no_pass_2_on_dry_run=False, retry_pass_2_failures=False) -> BackfillSummary`.

## §13 Pipeline-exclusion guard verification evidence

- **Entry-time check:** `_check_pipeline_not_running(conn)` at `run_backfill:1001` (entry) — `tests/cli/test_reconcile_backfill_cli.py` discriminating test plants `pipeline_runs.state='running'` row + asserts `BackfillPipelineActiveError` raised.
- **Per-iteration check:** added at R1 M#3 (`cc55cbf`) — `tests/cli/test_reconcile_backfill_cli.py` includes mid-iteration test where pipeline starts after first row + asserts abort raises cleanly + partial summary contains row 1.
- **Per-service-write check:** added at R2 M#2 (`c9eb9ef`) — 3 callsites (tier-1 apply + Pass-1 tier-2 stamp + Pass-2 tier-2 stamp); each has discriminating test.

## §14 Backward-compat verification evidence

- **T-D.6.1 `get_account_orders` shipped signature unchanged** — `tests/integrations/test_schwab_trader_audited_wrapper.py::test_get_account_orders_signature_unchanged` uses `inspect.signature` to pin the parameter list + return annotation; verifies no `return_call_id` kwarg leak.
- **Existing pipeline + flow-pivot callsites compile + pass tests** — full Schwab regression sweep `pytest tests/integrations/ tests/pipeline/ tests/trades/ -k schwab` passes (the 1 pre-existing `test_setup_auth_failure_audit_status_and_sentinel_redaction` failure is unrelated; CLAUDE.md baseline).

## §15 Phase 10 banner regression verification evidence

- **3 SQL predicates widened** at `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + `:list_unresolved_material_for_closed_trades` + `swing/metrics/discrepancies.py:list_unresolved_material_for_trade`.
- **13 base-layout VMs across 9 files** carry the `unresolved_material_discrepancies_count: int = 0` field; widening picks up transitively. `tests/web/test_routes/test_base_layout_vm_banner_with_pending_ambiguity.py` parametrized across all surfaces.
- **Per-trade indicator** (Phase 10 T-E.6) picks up tier-2-pending discrepancies via widened `list_unresolved_material_for_trade`.
- **Banner-text content unchanged** — wording "N unresolved material discrepancies"; predicate change is invisible at banner-text level except via count.

## §16 Synthetic-fixture acceptance test verification evidence

- **`tests/integration/test_phase12_bundle_c_payload_contract_acceptance.py`** — `@pytest.mark.slow` module-level; table-driven across **11 payload-required + 7 no-payload = 18 cases**.
- **All 18 cases PASS under `pytest -m slow`**.
- **Per-class assertions:** mutation-class (4 entries; applied != pre); split-class (1 entry; N+1 audit rows in one `correction_set_id` + original fill DELETEd + N new fills present); audit-only-class (3 entries; `applied == pre` no-mutation marker + `operator_intent` in `correction_reason`); no-payload-class (7 entries; no `--custom-value` required).
- **Isolated tmp DBs per case** via `_make_workspace` fixture mirroring T-C.11 verbatim.

---

**End of return report.**

**Awaiting orchestrator-driven 10-surface operator-witnessed gate per plan §G.4 + spec §15.5 LOCKED revised mechanic.**
