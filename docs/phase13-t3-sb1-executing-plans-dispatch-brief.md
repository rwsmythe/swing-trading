# Phase 13 T3.SB1 — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 13 T3.SB1 executing-plans implementer. No prior conversation context.

**Mission:** Execute the 6-task T3.SB1 plan (Theme 3 entry auto-fill via Schwab Trader API at trade-entry form-render time + `fill_origin` enum transitions + hidden audit anchors). T3.SB1 ships **CONCURRENT with T2.SB1** per OQ-12 Option E — T3.SB1's worktree branches off **T2.SB1's first-commit SHA** (the T-A.1.1 v20 migration-only commit), NOT from main HEAD.

**Brief:** `docs/phase13-t3-sb1-executing-plans-dispatch-brief.md` (this file).

**Plan (PRIMARY):** `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.2 (lines 1344-1507; 6 tasks T-B.1.1..T-B.1.6).

**Sequencing:** T2.SB1's T-A.1.1 (v20 migration atomic landing) MUST land first. T3.SB1's worktree branches off T-A.1.1's first-commit SHA; both proceed in parallel. Merge ordering: T2.SB1 first; T3.SB1 second.

**CRITICAL — T3.SB1 BRANCH BASE**: T3.SB1 worktree must branch from T2.SB1's T-A.1.1 commit SHA (NOT from main HEAD). Operator records the SHA when T2.SB1 implementer reports T-A.1.1 landed; relays to T3.SB1 implementer at dispatch time.

**Expected duration:** ~2-3 substantive Codex rounds (mid-sized sub-bundle; +200-300 prod + +300-500 test LOC; +40-70 fast tests + 1 slow Schwab E2E test).

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`** — PRIMARY SUBSTRATE. Read end-to-end at minimum: §0 top-matter + §A general architectural decisions (especially §A.11 Schwab integration discipline + §A.12 transactional discipline + §A.14 constant-placement LOCK) + §B v20 migration mechanics (just consume from T2.SB1's T-A.1.1) + §E Theme 3 architectural decisions (especially §E.1 fill_origin enum LOCK + §E.2 Schwab integration discipline + §E.6 hidden audit anchor LOCK) + **§G.2 T3.SB1 (lines 1344-1507; THE 6-TASK SPEC for this dispatch)** + §H.3 cross-bundle pin schedule + §L forward-binding lessons.

2. **`docs/phase13-t3-sb1-executing-plans-dispatch-brief.md`** (this file).

3. **`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`** — operator-confirmed brainstorm spec (1483 lines). Read §1 LOCKS L1-L11 + §6 Theme 3 (especially §6.1 entry auto-fill + §6.4 fill_origin enum widening) + §11 forward-binding lessons.

4. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured".

5. **`CLAUDE.md`** at repo root — project conventions + gotchas. **Especially**:
   - **`construct_authenticated_client` 4-arg signature** (Phase 12 Sub-bundle B + post-Phase-12 Sub-bundle 1 forward-binding lesson #10).
   - **`resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)`** BINDING per `allow_prompt=False` discipline (form-render-time prompts would block HTTP handler).
   - **`apply_overrides(cfg)`** at every Schwab entry point (Phase 12 Sub-bundle B cfg-cascade discipline).
   - **HTMX gotcha trinity** — HX-Request propagation on embedded forms + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted disciplines.
   - **Base-layout VM banner pin** — every new VM extending `base.html.j2` populates `unresolved_material_discrepancies_count` + `banner_resolve_link` (Phase 10 T-E.3 + Phase 12.5 #2 13-VM standalone retrofit precedent).
   - **Server-stamping at handler entry for hidden audit fields** — Phase 8 R2-R5 family; display-only `<span class="muted">` not hidden inputs (tampering surface).
   - **Form-render hidden anchor → POST-time validation must round-trip through soft-warn confirm form_values dict** — Phase 9 Sub-bundle D R3 Critical #1.
   - **Synthetic-fixture-vs-production-emitter shape drift** — Phase 12 C.D + Phase 12.5 #2 + Phase 12.5 Q2 family; discriminating regression tests use production-emitter shape.
   - **NEW Phase 13 T1.SB0 gotchas** (just landed at `dc0cfea`): session-anchor inequality discipline + hook fallback window-completeness.

6. **Existing Schwab Trader API consumers** at `swing/integrations/schwab/trader.py` + `swing/trades/schwab_reconciliation.py` (especially `_compute_execution_price` + `_resolve_match_quantity` at `swing/trades/schwab_reconciliation.py:99,174`). T3.SB1 reuses execution-grain comparator infrastructure from post-Phase-12 Sub-bundle 1.

7. **Existing entry form at `swing/web/routes/trades.py:entry_form` (line 343) + `entry_post` (line 358)** — T3.SB1 modifies these handlers.

8. **Existing Phase 12 Sub-bundle B `setup_paste_flow_with_callback_url` precedent** for `apply_overrides(cfg)` discipline at handler entry.

9. **Phase 12.5 #2 web Tier-2 surface precedent** (`docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md`) — Phase 12.5 #2 13-VM standalone retrofit pattern is the relevant precedent for base-layout VM banner pin discipline.

10. **Precedent executing-plans dispatch briefs**:
    - `docs/phase13-t1-sb0-executing-plans-dispatch-brief.md` (T1.SB0; cache wiring precedent).
    - `docs/phase12-5-bundle-2-web-tier2-executing-plans-dispatch-brief.md` (Phase 12.5 #2 web-route discipline precedent).

---

## §0.5 Skill posture

- Invoke **`copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- Plan §G.2 has per-task acceptance criteria + per-step instructions. Follow plan exactly.
- Use **`superpowers:test-driven-development`** for per-task work.

---

## §1 Strategic context

### §1.1 T3.SB1 scope (per plan §G.2)

- **Goal**: Pre-populate trade entry form fields from Schwab Trader API at form-render time. `fill_origin` enum transitions + audit columns + Schwab audit-row emit + soft-warn confirm.
- **Branch**: `phase13-t3-sb1-entry-auto-fill`. **Worktree branches FROM T2.SB1's first-commit SHA (T-A.1.1) — NOT from main HEAD** per OQ-12 Option E §B.2.
- **Files in scope** (per plan §G.2 lines 1350-1357): see plan; ~6 files create/modify.

### §1.2 OQ-12 Option E coordination (CRITICAL — branch base discipline)

**T3.SB1 worktree branches FROM T2.SB1's first-commit SHA, NOT from main HEAD**:
1. Wait for T2.SB1 implementer to commit T-A.1.1 (v20 migration atomic landing).
2. Operator records T-A.1.1's commit SHA + relays to T3.SB1 implementer at dispatch time.
3. T3.SB1 worktree command: `git worktree add .worktrees/phase13-t3-sb1-entry-auto-fill <T-A.1.1-SHA> -b phase13-t3-sb1-entry-auto-fill`.
4. T-B.1.1 first task verifies `EXPECTED_SCHEMA_VERSION == 20` at startup (no-op assert; migration already applied via T-A.1.1).
5. T3.SB1 proceeds in parallel with T2.SB1 remaining tasks.
6. Merge ordering: T2.SB1 merges first to main; T3.SB1 merges second.

### §1.3 Per-task structure (per plan §G.2)

- **T-B.1.1** — Schema-version-20 prerequisite + recon doc.
- **T-B.1.2** — `swing/trades/entry_auto_fill.py` — Schwab fetch + value resolution; `resolve_credentials_env_or_prompt(allow_prompt=False)` + `construct_authenticated_client` 4-arg signature traces.
- **T-B.1.3** — `entry_form` handler integration + EntryFormVM extension; HTMX + base-layout VM banner pin.
- **T-B.1.4** — `entry_post` handler audit columns persist + Schwab audit-row emit (`surface='trade_entry'`).
- **T-B.1.5** — Soft-warn confirm `form_values` round-trip (hidden anchors must round-trip per Phase 9 Sub-bundle D R3 Critical #1).
- **T-B.1.6** — Closer (slow E2E Schwab integration test + ruff sweep).

Each task has per-step instructions in plan §G.2 — follow them verbatim. Each task ends with a commit per the plan-provided commit message.

### §1.4 Inherited LOCKS + DROPS

- **L10**: Theme 3 absorbs original Phase 12.5 #2 fill auto-population at trade-entry scope. T3.SB1 implements this.
- **§A.11 Schwab integration discipline** BINDING: `apply_overrides(cfg)` + `resolve_credentials_env_or_prompt(allow_prompt=False)` + `construct_authenticated_client` 4-arg signature at every Schwab entry point.
- **§E.1 fill_origin enum LOCK**: 5 V1 values (`operator_typed` / `schwab_auto` / `schwab_auto_then_operator_corrected` / `tos_import` / `imported_legacy`); backfill at v20 migration via DEFAULT clause.
- **§E.6 hidden audit anchor LOCK**: `schwab_source_value_json` + `auto_fill_audit_at` as hidden inputs; server-stamp; round-trip through soft-warn confirm `form_values` dict.

### §1.5 Cross-bundle pins (per plan §H.3)

T-B.1.2 plants `test_fill_origin_enum_complete_after_v20` cross-bundle pin (un-skips at T3.SB2 exit auto-fill).

### §1.6 Forward-binding lessons inherited (most-load-bearing for T3.SB1)

1. **`construct_authenticated_client` 4-arg signature** (post-Phase-12 + Phase 12 Sub-bundle B forward-binding lesson #10).
2. **`resolve_credentials_env_or_prompt(allow_prompt=False)`** discipline (CLAUDE.md gotcha; prevents stdin-blocking inside HTTP handler).
3. **`apply_overrides(cfg)`** at every Schwab entry point (Phase 12 Sub-bundle B cfg-cascade).
4. **HTMX gotcha trinity** — HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted.
5. **Base-layout VM banner pin** — `EntryFormVM` populates `unresolved_material_discrepancies_count` + `banner_resolve_link`.
6. **Server-stamping at handler entry** — Phase 8 R2-R5 family; hidden audit fields display-only `<span class="muted">`.
7. **Form-render hidden anchor → POST-time round-trip through soft-warn confirm form_values** — Phase 9 Sub-bundle D R3 Critical #1.
8. **Phase 13 T1.SB0 NEW gotcha #1**: Session-anchor inequality discipline (forward-looking `>=`; backward-looking `>`).

---

## §2 Executing-plans scope

Execute plan §G.2 verbatim. Plan provides per-task acceptance criteria, per-step instructions with TDD pattern, per-task commit messages, and operator-witnessed gate definitions.

Plan §G.2 lines 1344-1507 are authoritative. Implementer follows exactly. Any deviation requires escalation to orchestrator.

---

## §3 OUT OF SCOPE

- **Schema changes** — v20 schema unchanged from T-A.1.1 atomic landing. If T-B.1.* surfaces a schema need, STOP + escalate.
- **Exit auto-fill code** — T3.SB2 ships exit auto-fill after T2.SB3.
- **Review auto-fill code** — T3.SB3 ships review auto-fill after T2.SB5.
- **Theme 2 detector code** — T2.SB3/SB4 territory.
- **Run-time AI inferencing** — L1 LOCK.

---

## §4 Binding conventions

- **Branch**: `phase13-t3-sb1-entry-auto-fill` (per plan §G.2 line 1348). Worktree at `.worktrees/phase13-t3-sb1-entry-auto-fill/`. **BRANCHES FROM T2.SB1's T-A.1.1 commit SHA** — NOT from main HEAD.
- **Commit messages**: per-task message per plan §G.2; do NOT bundle tasks.
- **NO Claude co-author footer.** ~204+ commits ZERO trailer drift; DO NOT regress.
- **`python -m swing.cli`** at worktree-side gates.
- **ASCII-only on runtime CLI paths** (Windows cp1252).
- **TDD discipline** per task.
- **Pre-Codex orchestrator-side review** per C.C lesson #6 BINDING — 13th cumulative validation expected (or 12th if dispatched before T2.SB1 closes).
- **Operator-witnessed gate**: S1 inline pytest+ruff; S2 `python -m swing.cli web` + visit `/trades/entry/form` operator-paired session; S3 entry POST operator-paired (form submission with Schwab auto-fill populated).

---

## §5 Adversarial review watch items

1. **Plan §G.2 per-task structure integrity** — 6 tasks executed verbatim; no bundling.
2. **T3.SB1 worktree branches off T2.SB1's T-A.1.1 SHA** (NOT main HEAD) — T-B.1.1 prerequisite test verifies.
3. **`construct_authenticated_client` 4-arg signature discipline** — T-B.1.2 trace tests verify (mock-verified per Codex R1 Major #5 closure pattern).
4. **`resolve_credentials_env_or_prompt(allow_prompt=False)` discipline** — T-B.1.2 trace test verifies; BINDING per CLAUDE.md gotcha.
5. **`apply_overrides(cfg)` at handler entry** — T-B.1.3 entry_form + T-B.1.4 entry_post both apply.
6. **HTMX gotcha trinity** — embedded form `hx-headers='{"HX-Request": "true"}'` + HX-Redirect not 303 swap-target + HX-Redirect target route registered.
7. **Base-layout VM banner pin** — `EntryFormVM` populates `unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count` (per Phase 12.5 #1 forward-binding lesson #12).
8. **Server-stamping hidden audit fields** — `schwab_source_value_json` + `auto_fill_audit_at` server-stamped at handler entry; rendered display-only `<span class="muted">` (NOT hidden inputs after Phase 8 R2-R5 discipline).
9. **Soft-warn confirm `form_values` round-trip** — every hidden form-render anchor present in confirm-fragment `form_values` dict (Phase 9 Sub-bundle D R3 Critical #1).
10. **`fill_origin` enum transitions** — `schwab_auto` (auto-populated, unmodified) → `schwab_auto_then_operator_corrected` (auto-populated then operator overrode) → `operator_typed` (never auto-populated OR operator cleared auto value).
11. **Schwab audit-row emit** — T-B.1.4 emits `surface='trade_entry'` audit row in `schwab_api_calls`.
12. **Synthetic-fixture-vs-production-emitter shape drift** — discriminating tests use production Schwab order response shape.
13. **No prompt fired at handler entry** — `allow_prompt=False` discipline; verify via stdin-not-touched assertion.
14. **Sandbox short-circuit honored** — under `cfg.integrations.schwab.environment == 'sandbox'`, auto-fill short-circuits + emits advisory + does NOT write Schwab audit row.
15. **DEGRADED state honored** — when refresh-token TTL expired, auto-fill short-circuits + emits advisory.
16. **Phase 13 T1.SB0 NEW gotcha #1 honored** — any session-keyed predicate uses correct inequality.
17. **Cross-bundle pin `test_fill_origin_enum_complete_after_v20` planted** at T-B.1.2.
18. **Implementer self-report accuracy gate** — return report cites file:line + test counts + commit SHAs verbatim.

---

## §6 Done criteria

1. Branch `phase13-t3-sb1-entry-auto-fill` at `.worktrees/phase13-t3-sb1-entry-auto-fill/`; branches off T2.SB1's T-A.1.1 SHA.
2. 6 tasks T-B.1.1..T-B.1.6 executed per plan §G.2 verbatim.
3. T-B.1.1 prerequisite test passes (schema_version == 20 + worktree correctly branched off T-A.1.1 SHA).
4. `swing/trades/entry_auto_fill.py` created with `EntryAutoFillResult` + `resolve_entry_auto_fill(*, ticker, cfg, conn)`.
5. `entry_form` handler integrated; EntryFormVM extends `BaseLayoutVM` with banner-pin fields.
6. Template renders auto_fill_* fields + display-only audit metadata + advisory banner + HTMX discipline.
7. `entry_post` handler persists audit columns + emits Schwab audit row.
8. Soft-warn confirm `form_values` round-trips all hidden anchors.
9. `fill_origin` enum transitions tested across all 5 V1 values.
10. ≥2 Codex rounds → NO_NEW_CRITICAL_MAJOR (2-3 rounds expected).
11. Cross-bundle pin `test_fill_origin_enum_complete_after_v20` planted at T-B.1.2.
12. Operator-witnessed gate: S1 PASS via implementer; S2 + S3 operator-paired post-merge.
13. Return report at `docs/phase13-t3-sb1-return-report.md` per §7.
14. ZERO Co-Authored-By footer trailer drift across all commits.

---

## §7 Return report format

```
## Return report — Phase 13 T3.SB1

### Sub-bundle location
Worktree branch: `phase13-t3-sb1-entry-auto-fill` at `.worktrees/phase13-t3-sb1-entry-auto-fill/`
Branch base: T2.SB1's T-A.1.1 SHA = {SHA recorded by operator from T2.SB1 dispatch}
Commits on branch:
- {sha} T-B.1.1 — Schema-version-20 prerequisite + recon
- {sha} T-B.1.2 — entry_auto_fill.py — Schwab fetch + value resolution
- {sha} T-B.1.3 — entry_form handler integration + EntryFormVM
- {sha} T-B.1.4 — entry_post audit columns persist + Schwab audit row
- {sha} T-B.1.5 — Soft-warn confirm form_values round-trip
- {sha} T-B.1.6 — Closer (slow E2E + ruff)
- (optional) {sha} Codex R<N> fix bundles
- {sha} Return report

### Codex review history
- Pre-Codex (orchestrator-side review per C.C lesson #6 BINDING): {N findings absorbed; Nth cumulative validation}
- R1..RN: ... (2-3 rounds expected)
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Schwab integration discipline verified
- `apply_overrides(cfg)` at handler entry: ✅ ({file:line})
- `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)`: ✅ ({file:line})
- `construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg signature: ✅ ({file:line})
- HTMX gotcha trinity: ✅ (HX-Request propagation + HX-Redirect-not-303 + HX-Redirect target registered)
- Base-layout VM banner pin: ✅ (EntryFormVM populates banner fields)

### fill_origin enum transitions tested
- `schwab_auto` (auto-populated, unmodified): ✅
- `schwab_auto_then_operator_corrected` (auto-populated then operator overrode): ✅
- `operator_typed` (never auto-populated OR operator cleared): ✅
- `tos_import` (existing): ✅
- `imported_legacy` (existing): ✅

### Test count pre/post
- Pre-baseline (T-A.1.1 SHA): ~4935 + T2.SB1 increments by T-A.1.1 commit time
- Post-T3.SB1: {fast count} (delta: +{N}; within +40-70 projection); +1 slow Schwab E2E

### Operator-witnessed gate results
- S1 (inline pytest+ruff): {PASS/FAIL}
- S2 (`python -m swing.cli web` + `/trades/entry/form` operator-paired): {PASS/FAIL post-merge}
- S3 (entry POST operator-paired with Schwab auto-fill): {PASS/FAIL post-merge}

### Cross-bundle pin planted
- `test_fill_origin_enum_complete_after_v20` at {file:line}; un-skips at T3.SB2.

### V2.1 §VII.F amendment candidates banked
### Forward-binding lessons for downstream sub-bundles
### Capture-needs for next sub-bundle dispatch
### Outstanding capture-needs that DEFER
```

---

## §8 If you get stuck

- If T2.SB1's T-A.1.1 SHA not provided at dispatch time, STOP + ask operator (cannot branch correctly without it).
- If T-B.1.1 prerequisite test fails (schema_version != 20), STOP + escalate (worktree branched off wrong SHA).
- If you find yourself proposing schema changes, STOP — §B.6 escalation rule.
- If `allow_prompt=False` discipline is violated by any test fixture (test invokes the production path with `allow_prompt=True`), STOP + correct (BINDING per CLAUDE.md gotcha).
- If HTMX gotcha trinity is regressed in any new form, STOP + correct (BINDING per Phase 5 forward-binding lesson #11).
- If you find yourself proposing run-time AI inferencing, STOP — L1 LOCK violated.

---

*End of brief. Phase 13 T3.SB1 executing-plans dispatch — 6 tasks per plan §G.2; entry auto-fill via Schwab Trader API at form-render; `fill_origin` enum transitions + hidden audit anchors; CONCURRENT with T2.SB1 (T3.SB1 branches off T2.SB1's T-A.1.1 first-commit SHA per OQ-12 Option E). Worktree branch `phase13-t3-sb1-entry-auto-fill` from T-A.1.1 SHA. Expected 2-3 Codex rounds; ZERO ACCEPT-WITH-RATIONALE preferred. Pre-Codex orchestrator-side review BINDING per C.C lesson #6.*
