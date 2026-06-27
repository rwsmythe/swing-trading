# Phase 4.5 — Hypothesis-Label Web-Form Gap — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author an implementation plan that closes the web-form `hypothesis_label` gap. CLI captures `hypothesis_label` (matcher pre-fill + free-text override) since 2026-04-25; the web entry form has NEVER captured it. Every web-form trade entry persists `hypothesis_label = NULL`, so progress count never increments and tripwire never fires from web entries. Brainstorm is EXPLICITLY SKIPPED — operator locked all design decisions on 2026-04-30 (see §2).

**Expected duration:** ~30-60 min plan-authoring + 3-5 Codex rounds via `copowers:writing-plans` wrapper = ~1.5-3 hours total.

**Dispatch type:** `copowers:writing-plans` (NOT executing-plans; this dispatch produces a plan, NOT shipped code).

---

## §0 Read first

Read these in order before drafting:

1. **`CLAUDE.md`** at repo root — project conventions, gotchas, invariants. Note especially: HTMX `<tr>`-leading `makeFragment` pathology (2026-04-30); HTMX OOB-swap partial drift; base-layout 5-VM rule (only when `base.html.j2` actually dereferences the new field); Starlette TemplateResponse signature; TestClient lifespan rule.
2. **`docs/orchestrator-context.md`** — §"Currently in-flight work" (HEAD `f85c242` clean; 1366 fast tests; 13-phase ZERO-rogue track record); §"Binding conventions" (4-tier commit-message convention; subject-only ERE grep `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'`; ruff baseline 91; no-amend; no Claude footer); §"Anti-patterns to avoid"; §"Lessons captured" — read entire section. The most directly applicable lessons:
   - **Multi-path data ingestion needs full-path audit** (sector capture R2 M1, 2026-04-29). Brief specifies BOTH the route handler AND the soft-warn confirm round-trip; plan must verify both.
   - **Spec/plan silence on form-driven success-path response shape is a recurrent failure class** (hyp-recs trade-prep R1 M1, 2026-04-29). Specify success-path response behavior explicitly.
   - **JS-execution test harness gap matters** (hyp-recs success-path fix, 2026-04-29). Operator-witnessed verification is a binding done-criterion for the executing-plans dispatch that follows; this writing-plans dispatch only authors the plan.
   - **Snapshot-at-entry-surface ToCToU pattern** (chart-pattern flag-v1 spec §3.6, Phase 5 lesson). Resolve at form-render via the existing matcher; persist AS-IS. No re-resolve at submit.
   - **"Additive" dataclass field changes are NOT zero-cost** (Phase 4 Task 1, 2026-04-30). `TradeEntryFormVM` extension breaks hand-constructed test sites; enumerate via `grep -rn "TradeEntryFormVM(" tests/` BEFORE estimating refactor scope.
   - **Plan-text contracts must NOT over-state vs framework's effective behavior** (Phase 4 R1 M1, 2026-04-30). Verify the matcher's contract against the original CLI prefill code — including that empty-string vs None has different semantics in `canonicalize_hypothesis_label`.
3. **`docs/phase3e-todo.md`** §"2026-04-30 hypothesis_label web-form gap" — **THE SCOPE-OF-WORK SOURCE OF TRUTH** for this dispatch. The entry mistakenly says `_lookup_active_recommendation_label` lives in `swing.web.view_models.dashboard`; it actually lives in `swing/cli.py:339-395` (verify via `grep -rn "_lookup_active_recommendation_label" swing/`). All other locked content in that entry is canonical.
4. **`swing/cli.py`** — read `_lookup_active_recommendation_label` definition at `:339-395` AND the call site + threading at `:483-526` (the canonical CLI prefill behavior; the web VM must produce identical pre-fill for the same ticker + DB state).
5. **`swing/trades/entry.py`** — note `EntryRequest.hypothesis_label: str | None = None` already exists (line 94). Note `canonicalize_hypothesis_label` at line 125-162 — empty-string-after-canonicalization → `None` semantics matter for the discriminating tests.
6. **`swing/data/repos/trades.py` + `swing/data/models.py`** — confirm `Trade.hypothesis_label` already persists. `record_entry` already calls `canonicalize_hypothesis_label(req.hypothesis_label)` at `swing/trades/entry.py:201`. **NO schema migration needed; NO repo change needed; NO dataclass change needed for `Trade` or `EntryRequest`.** The gap is purely web-side wiring.
7. **`swing/web/view_models/trades.py`** — `TradeEntryFormVM` (lines 38-93) and `build_entry_form_vm` (lines 96-283). This is the canonical precedent for snapshot-at-entry-surface resolution + sector/industry plumbing (Task 6/7 in sector-industry plan; landed 2026-04-29).
8. **`swing/web/templates/partials/trade_entry_form.html.j2`** — sector/industry hidden-input + read-only display rows pattern at lines 47-54. Hypothesis label rows mirror this pattern.
9. **`swing/web/templates/partials/soft_warn_confirm.html.j2`** — `form_values.items()` loop with banner-only exclusion. Adding `hypothesis_label` to `form_values` in the route handler auto-emits the hidden input on the force=true resubmit.
10. **`swing/web/routes/trades.py`** — `entry_post` (lines 228-669). Note all the re-render paths: rationale validation, stop-≥-entry validation, soft-warn (lines 393-457), duplicate-open-position (lines 458-489), hard-cap (lines 490-497), chart-pattern ValueError (lines 498-522), chart-pattern IntegrityError (lines 523-569).
11. **`tests/cli/test_cli_trade_entry_hypothesis_prefill.py`** — canonical CLI prefill test patterns. The web-side discriminating tests should mirror these (same fixtures and assertion pattern, swapped to TestClient).
12. **`docs/sector-industry-capture-writing-plans-brief.md`** — most-recent precedent brief for a similar small frontend-integration dispatch. Mirror its structure; the scope here is even smaller.

If any file path above doesn't resolve, verify via `Glob`/`Grep` before drafting plan tasks against it.

---

## §0 Skill posture

- **INVOKE** `copowers:writing-plans` — wraps `superpowers:writing-plans` with adversarial Codex review (3-5 rounds typical).
- **DO NOT INVOKE** `superpowers:brainstorming` or `copowers:brainstorming` — design decisions are pre-locked (see §2). Re-litigation is out of scope. If you find a locked decision is impossible to implement as written, STOP and surface it in the return report; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:writing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`.
- **Plan output target path:** `docs/superpowers/plans/2026-04-30-hypothesis-label-web-form-plan.md`. Commit the plan as part of the standard cycle.

---

## §1 Strategic context

**The CLI prefill exists and works.** Since 2026-04-25 (commits `b24506b` → `fe270a6`), `swing trade entry` for any ticker that matches an active hypothesis recommendation auto-fills `--hypothesis "<canonical-label>"` and emits `Pre-filled --hypothesis: <label>` to stderr. Operator approves the pre-fill simply by submitting. Manual override via `--hypothesis "..."` works.

**The web form silently drops it.** The web entry form has NO `hypothesis_label` field on its VM, NO hidden input, NO `Form(...)` param, NO threading into `EntryRequest`. Every web-form entry persists `hypothesis_label = NULL`. Concrete failure modes:
- Hypothesis 3 (Sub-A+ VCP-not-formed) progress count never increments from web entries.
- Per-hypothesis tripwire never fires from web entries.
- Per-hypothesis aggregation in `swing journal review` never groups web entries by hypothesis.
- VIR (id=1) and CC (id=3) both required SQL UPDATE backfills 2026-04-25 / 2026-04-30 to attribute correctly.

**This dispatch closes the gap.** Resolve the same matcher + prioritizer chain the CLI uses at form-render time; render the resolved label as a hidden input + read-only display row; thread it through the POST handler into `EntryRequest`; preserve it across the soft-warn confirm round-trip. Mirrors sector/industry capture Phase 1 (Task 6/7) pattern at smaller scope.

**Sequencing context.** This dispatch ships BEFORE Phase 5 (configuration page) per operator decision 2026-04-30. Phase 4 cleanup-remainder is fully shipped (HEAD `f85c242`); this dispatch is independent of all in-flight Phase 4.5+ work.

---

## §2 Locked decisions (DO NOT re-litigate)

Operator-locked 2026-04-30. The plan implements these as written; no re-design.

1. **Resolve at form-render via the existing CLI matcher logic.** Re-use the same chain as `swing/cli.py:_lookup_active_recommendation_label` — `latest_evaluation_run_id` → `fetch_candidates_for_run` → `match_candidate_to_hypotheses` → `prioritize_recommendations` → `prioritized[0].suggested_label_descriptive`. Cross-surface consistency is the point: if the operator sees a recommendation on the dashboard for ticker X, the web form for X must pre-fill the same label the CLI would.
2. **Helper extraction.** Move `_lookup_active_recommendation_label` from `swing/cli.py` to `swing/recommendations/hypothesis_prefill.py` (rename to `lookup_active_recommendation_label` — public). Both CLI and web VM import from there. Reasoning: this is the second non-CLI consumer; CLI as a leaf module shouldn't be imported from view-model code. Small refactor, no behavior change.
3. **Read-only display in V1; no override surface.** Mirror sector/industry pattern: hidden input + read-only display row, NOT an editable input. Operator's CLI `--hypothesis "<custom>"` override capability is NOT mirrored in the web form; that is V2 if/when operator wants it. V1 = "auto-attribute web entries to active recommendations."
4. **Snapshot-at-entry-surface (ToCToU fix).** Resolve at form-render only; persist AS-IS via `EntryRequest.hypothesis_label`. Do NOT re-resolve at submit. Re-render paths (rationale-fail / stop-≥-entry / duplicate / chart-pattern errors) rebuild the VM via `build_entry_form_vm` which re-resolves the matcher; that's the same behavior the existing chart-pattern + sector/industry fields use, and it's correct because the matcher's output is deterministic on (DB state, ticker) and the DB state hasn't changed mid-request.
5. **Soft-warn round-trip preserves the label AS-IS.** Add `hypothesis_label` to `form_values` so the auto-iterating `soft_warn_confirm.html.j2` emits a hidden `<input name="hypothesis_label">`. The `force=true` resubmit MUST persist the SAME label the operator saw at first submit (per multi-path-ingestion lesson 2026-04-29).
6. **Empty-string semantics.** `Form(default="")` for the new field. The route passes the form value through to `EntryRequest.hypothesis_label`; `record_entry` calls `canonicalize_hypothesis_label` which converts empty-or-whitespace-only to `None` and persists `NULL`. So a ticker with no matching recommendation persists `NULL` (current behavior preserved). A ticker with a matching recommendation persists the canonical label.
7. **Display row position.** Place the read-only "Hypothesis" row in the form between the sector/industry rows and the rationale block. Specifically: after `<input type="hidden" name="industry">` (`trade_entry_form.html.j2:53-54`) and before the `<label>Rationale ★</label>` block (`:55`). Keep adjacent to the other captured-snapshot read-only rows (sector/industry/chart-pattern).
8. **Display when unmatched.** When `vm.hypothesis_label` is `None` (no active recommendation matches the ticker), render `<span>(none)</span>` for the value. The hidden input value is empty string. No "auto-filled" or "pre-filled" decoration text — operator infers from the framework UX that any present label came from the matcher.

---

## §3 Scope

### V1 in-scope (this dispatch's plan covers ALL of these):

**A. Helper extraction.** Move `_lookup_active_recommendation_label` from `swing/cli.py` to `swing/recommendations/hypothesis_prefill.py`, renamed to `lookup_active_recommendation_label` (public). The function continues to import `latest_evaluation_run_id` and `build_recommendation_progress` from `swing.web.view_models.dashboard` (status quo; that's the deferred-3-cross-imports refactor noted in `docs/phase3e-todo.md` 2026-04-26 QoL bundle followups). CLI updated to import from new location. **Migrate the existing CLI test (`tests/cli/test_cli_trade_entry_hypothesis_prefill.py`) by updating imports if it imports the helper directly; if it only invokes the CLI, no change.** Add a focused unit test against `lookup_active_recommendation_label` directly (does not exist today; covered transitively only through CLI integration).

**B. VM extension.** `TradeEntryFormVM` gains `hypothesis_label: str | None = None`. `build_entry_form_vm` resolves it inside the existing `with conn:` block (mid-function; before the `return TradeEntryFormVM(...)` literal) by calling `lookup_active_recommendation_label(conn, ticker=ticker, starting_equity=cfg.account.starting_equity)`. The result feeds the new VM field directly. Performance: one additional DB pass per form render (the matcher reads candidates + registry + progress); same cost the CLI prefill already pays. Ordering: the new resolution must happen WHILE the connection is open AND BEFORE the connection is closed at line 177.

**C. Template rendering.** `trade_entry_form.html.j2` gains:
- A read-only display row between the industry block and the rationale block:
  ```jinja
  <div><label>Hypothesis:</label>
    <span>{{ vm.hypothesis_label or "(none)" }}</span>
    <input type="hidden" name="hypothesis_label" value="{{ vm.hypothesis_label or '' }}">
  </div>
  ```
- No edit affordance. No "pre-filled" decoration text.

**D. POST handler thread.** `entry_post` at `swing/web/routes/trades.py:228-263`:
- Add `hypothesis_label: str = Form("")` parameter (string-default, NOT `None` — mirrors `sector` / `industry` style at lines 254-255).
- Pass to `EntryRequest(... hypothesis_label=hypothesis_label or None, ...)`. Empty-string-to-None coercion at the route boundary is a defense-in-depth (record_entry's canonicalize_hypothesis_label already handles empty-string-→-None, but explicit coercion at the boundary documents the contract).
- Soft-warn confirm: add `"hypothesis_label": hypothesis_label,` to `form_values` dict (lines 413-453). Position in the dict next to `sector` / `industry` for readability.
- No additional validation (free-text per migration 0007 design; canonicalization is the only "validation").
- No new exception path. Existing `record_entry` call already canonicalizes via `canonicalize_hypothesis_label`.

**E. Tests.** Discriminating tests:
- `lookup_active_recommendation_label` returns expected label for matching ticker (unit test).
- `lookup_active_recommendation_label` returns `None` for non-matching ticker (unit test).
- `build_entry_form_vm` populates `hypothesis_label` from the matcher when ticker has an active recommendation (VM-level test).
- `build_entry_form_vm` returns `hypothesis_label = None` when ticker has no recommendation (off-pipeline / no candidate row).
- Form template renders the hidden input with the resolved label (template-level test via TestClient + html-string assertion).
- Form template renders `(none)` display when label is None (template-level test).
- POST `/trades/entry` persists `hypothesis_label = <canonical-label>` on the trades row when a matching ticker is submitted via the form (integration test via TestClient + DB inspection). **DISCRIMINATING:** with the bug present (no thread-through), this would persist NULL; with the fix, it persists the canonical label.
- POST `/trades/entry` persists `hypothesis_label = NULL` when a non-matching ticker is submitted (degenerate path; preserves current behavior for off-pipeline trades).
- POST `/trades/entry` soft-warn confirm round-trip preserves `hypothesis_label` AS-IS through `force=true` resubmit (integration test). **DISCRIMINATING:** with the bug present (form_values omits hypothesis_label), the second submit would persist NULL; with the fix, it persists the original label.
- Re-render preservation: rationale-validation-fail re-render preserves the resolved label (the rebuilt VM re-resolves the matcher, which is deterministic, so the label persists across re-renders). Test asserts the hidden input value in the re-render response body.

### V1 out-of-scope (DEFER; V2 candidates):

- **Manual override surface in the web form.** Editable input or "edit" toggle for the operator to type a custom label. V2 if/when operator wants parity with `--hypothesis "<custom>"` CLI capability.
- **Pre-fill notification banner / decoration.** "Pre-filled from active recommendation" text in the form. V2 polish.
- **Backfill of historical web-entered trades.** Existing trades persisted before this dispatch with `hypothesis_label = NULL` stay NULL. Operator handles via SQL UPDATE per existing precedent.
- **Helper extraction beyond `lookup_active_recommendation_label`.** `latest_evaluation_run_id` + `build_recommendation_progress` stay in `swing/web/view_models/dashboard.py`. Per the deferred-3-cross-imports refactor (`docs/phase3e-todo.md` 2026-04-26 QoL bundle followups), bundle this dispatch with the broader helper-extraction refactor only when 3+ cross-imports exist; today this dispatch creates the second consumer of `_lookup_active_recommendation_label` (CLI is first; web VM is second), but only the matcher itself moves.
- **Standalone `/watchlist` form preservation.** The standalone watchlist page reuses the same entry-form partial via `/trades/entry/form`, so it inherits the fix automatically. No additional surface work.
- **Performance optimization.** The matcher reads candidates + registry + progress on every form render. Same cost the CLI already pays per `swing trade entry` invocation. Defer optimization until measurable.

---

## §4 Plan acceptance criteria

The plan output (at `docs/superpowers/plans/2026-04-30-hypothesis-label-web-form-plan.md`) MUST satisfy:

1. **Per-task TDD discipline.** Each task: failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change.
2. **Discriminating-test discipline (per orchestrator-context lessons).** Every task with a discriminating test includes a "would this test fail if the implementation never actually called the new code?" sanity-check sentence in the task body. Failure to include = plan-quality miss.
3. **Compounding-confound class avoidance** (Phase 4 + chart-scope-policy-v2 + sort-coupling lessons). Tests that assert on the persisted `hypothesis_label` value must use a label distinct from any default/fallback that could mask the bug. Specifically: use a unique label string in the discriminating test (e.g., `"Sub-A+ VCP-not-formed test (proximity_20ma + tightness fails); inaugural trade test"` — the exact canonical hypothesis-3 label) rather than a generic `"test-label"` string. With the bug present (route doesn't thread the value), the persisted value is `NULL`; with the fix, the persisted value matches the canonical label exactly. No tiebreaker masking possible.
4. **Hand-constructed test-site enumeration** (Phase 4 Task 1 lesson). The plan MUST include a `grep -rn "TradeEntryFormVM(" tests/` enumeration in Task 2's body before the dataclass-extension task — even though the new field has a default value (`= None`) and is therefore NOT semantically required, the enumeration documents exposure surface for future plan reviewers.
5. **Sequential single-subagent execution discipline.** Plan tasks are SEQUENTIAL; no parallel-subagent collision risk at this scale. Plan task IDs follow the convention (Task X.Y format).
6. **Observable-verification subject-only grep pattern** per binding conventions: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` before each task implementation commit. ERE flag required (BRE chokes on `+`); POSIX `[0-9]` for digit class. Each task includes this verification step in its body.
7. **Commit-message convention (4-tier per binding conventions).**
   - Task implementations: `feat(area): Task X.Y — <description>`
   - Codex review-fix commits: `fix(area): Codex R1 Major 2 — <description>`
   - Internal-Codex within-task: `(internal)` qualifier
   - Internal code-review: `fix(area): code-review I1 — <description>`
   - Format-only cleanup: no task ID
8. **Task ordering.**
   - Task 1: Helper extraction (`_lookup_active_recommendation_label` → `swing/recommendations/hypothesis_prefill.py`).
   - Task 2: `TradeEntryFormVM` field addition + `build_entry_form_vm` resolution.
   - Task 3: Template render (hidden input + read-only display row).
   - Task 4: `entry_post` Form-param + `EntryRequest` thread + soft-warn round-trip.
   - Task 5: Integration tests (POST persistence + soft-warn round-trip).
9. **Test count baseline pinned at plan-time:** plan should run `python -m pytest -m "not slow" -q` to capture the current fast-test count and project per-task test additions. Expected total addition: ~6-10 tests.
10. **Plan passes copowers:writing-plans Codex review cycle:** iterate to `NO_NEW_CRITICAL_MAJOR`. Major findings are RESOLVED-by-fix (not ACCEPTED-with-rationale unless genuinely out-of-scope).
11. **Effective-contract verification (Phase 4 R1 M1 lesson 2026-04-30).** Plan tasks asserting the matcher's behavior must verify the contract via test-or-trace, not against the plan-author's stated contract. Specifically: empty-string vs `None` semantics in `canonicalize_hypothesis_label` must be empirically tested, not assumed. The plan should include a one-line trace showing that empty-string `""` flowing through the route → `EntryRequest.hypothesis_label = ""` → `canonicalize_hypothesis_label("") = None` → `Trade.hypothesis_label = NULL`. This trace is load-bearing for the "no-match → NULL" guarantee.

---

## §5 Adversarial review watch items (for Codex during writing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check:

1. **Discriminating-test vacuousness on `hypothesis_label` persistence.** Cross-reference Phase 4 + chart-scope-policy-v2 lessons. Tests asserting "the persisted trade row has hypothesis_label = X" must use a unique label that doesn't coincide with any matcher-fallback, default, or tiebreaker output. The persisted value must be UNIQUE to "the route correctly threaded the value" — not "the test fixture happens to produce X via a different path."
2. **Soft-warn round-trip vacuousness.** The discriminating test for soft-warn must verify the SECOND submit's POST body carries the hypothesis_label, not just that the first submit response contains it. With the bug present (`form_values` omits `hypothesis_label`), the soft-warn confirm partial would emit no `<input name="hypothesis_label">`, the force=true resubmit would have no hypothesis_label, and the persisted trade row would have NULL. The test must verify the persisted value, not just the first response. **"Would this test fail if the implementation never actually called the new code?"** = "If `form_values["hypothesis_label"] = ...` is missing, does this test fail?" Yes if the test asserts on the post-force-submit DB row, NO if the test only asserts the first response shape.
3. **Snapshot-at-entry-surface ToCToU pattern compliance.** Per spec §3.6 / Phase 5 lesson. The matcher's output at form-render time is what gets persisted; do NOT re-resolve at submit-time. Mirror the `chart_pattern_*` + `sector` / `industry` precedents. Re-render paths rebuild the VM via `build_entry_form_vm`, which re-resolves; that's correct (deterministic on DB state).
4. **Multi-path data ingestion full-path audit** (sector capture R2 M1 lesson 2026-04-29). The web form is one ingestion path; the CLI is another; future surfaces (e.g., `/watchlist/<ticker>/enter` shortcut if it ever exists) are additional paths. The plan must verify the CLI's behavior is preserved post-helper-extraction (CLI prefill test still passes) AND the web form is the only currently-broken path. Audit-document any other writers to `trades.hypothesis_label`.
5. **Helper extraction breaks no existing CLI behavior.** Task 1 must include a TDD step that runs the existing CLI prefill test (`tests/cli/test_cli_trade_entry_hypothesis_prefill.py`) BEFORE and AFTER the helper move, asserting identical behavior. Specifically: re-run the existing tests after the move; if any test fails, the move is incorrect.
6. **Plan task partitioning is sequential.** Per Phase 2 self-collision lesson + 5-phase ZERO-rogue track record. Each plan task assigned to exactly one notional subagent (this dispatch is single-subagent so the partitioning is trivial; verify the partitioning is documented).
7. **Base-layout 5-VM rule application.** Is `base.html.j2` going to dereference `hypothesis_label`? Almost certainly NOT — this is consumer-scoped to the entry-form partial. Verify explicitly via `grep -rn "hypothesis_label" swing/web/templates/base.html.j2`; if confirmed empty, plan should NOT require all 5 base-layout VMs to gain the field.
8. **Form param default contract.** Plan must specify `hypothesis_label: str = Form("")` (NOT `Form(None)`) — mirrors the `sector` / `industry` pattern at lines 254-255 of `swing/web/routes/trades.py`. The route then converts `"" → None` at the boundary before passing to `EntryRequest`. Empty-string contract through the route layer; None contract through `EntryRequest` and below.
9. **Effective-contract verification of `canonicalize_hypothesis_label`.** Plan should include an empirical trace (one-line code trace + test) showing that empty-string `""` → `None` → `NULL` is the correct semantic chain. With the bug present, NULL is the persisted value; with the fix on a non-matching ticker, NULL is also the persisted value. So the discriminating test for "no-match" path is degenerate (passes regardless); the discriminating test for "matching ticker" path is the load-bearing test.
10. **Post-helper-extraction CLI import path stability.** Codex should verify the CLI's `swing/cli.py` import statement updates correctly (`from swing.recommendations.hypothesis_prefill import lookup_active_recommendation_label`), the function call site at the new location passes the same arguments, and no other module imports `_lookup_active_recommendation_label` from `swing.cli` (the underscore prefix made this unlikely; verify via `grep -rn "_lookup_active_recommendation_label" .` AND `grep -rn "from swing.cli import" .`).

---

## §6 Done criteria

- Plan committed to `docs/superpowers/plans/2026-04-30-hypothesis-label-web-form-plan.md`.
- Plan passes `copowers:writing-plans` Codex review cycle: 3-5 rounds, terminating at `NO_NEW_CRITICAL_MAJOR`.
- All Major findings RESOLVED-by-fix; ACCEPTED-with-rationale only if genuinely out-of-scope per §3.
- Test count baseline pinned in plan body.
- Per-task observable-verification step included in each task body.
- Per-task discriminating-test sanity-check sentence included in each task body where applicable.

---

## §7 Return report format

Post as final message:

```
## Hypothesis-Label Web-Form Gap Plan — Writing-Plans Return Report

**Plan committed at:** docs/superpowers/plans/2026-04-30-hypothesis-label-web-form-plan.md (commit <SHA>)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR
**Test baseline pinned:** <count> fast tests at HEAD <SHA>
**Plan task count:** <N tasks>
**Helper-extraction target:** swing/recommendations/hypothesis_prefill.py

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — all RESOLVED / <N> ACCEPTED with rationale
- R2: <count> Critical, <count> Major, <count> Minor — all RESOLVED / <N> ACCEPTED with rationale
- ... (per round)

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision before executing-plans dispatch>

**Recommended next dispatch:** copowers:executing-plans on this plan, OR <alternative if implementer surfaces a concern>
```

---

## §8 If you get stuck

- **If a locked decision (§2) appears impossible to implement as written:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. Pre-dispatch survey may have stale references.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If the discriminating-test sanity check reveals a vacuousness pattern across multiple plan tasks:** STOP, restructure the plan to eliminate the pattern, then resume Codex cycle. This is a plan-quality issue worth investing extra time in.
- **If `_lookup_active_recommendation_label` turns out to NOT be in `swing/cli.py` after Glob/Grep:** the phase3e-todo entry's location citation may be wrong in either direction; trust the actual codebase. Helper extraction proceeds from wherever the function actually lives.

---

## Appendix A: Why brainstorm is skipped

Standard pattern is brainstorm → writing-plans → executing-plans. Per the 2026-04-27 brainstorm-pattern decision (orchestrator-context line 198), brainstorm dispatch is appropriate when ≥3 medium-complexity decisions OR spec ≥500 lines OR orchestrator context approaching 60%+. This dispatch hits zero of those conditions:

- All 8 design decisions pre-locked by operator (resolve-via-existing-matcher, helper-extraction-target, read-only-display, snapshot-at-entry, soft-warn-round-trip-discipline, empty-string semantics, display-row position, no-decoration-on-unmatched).
- Spec content fits in §3 above (~80 lines); writing-plans phase will expand into per-task plan content but that's not a "spec" in the brainstorm-output sense.
- Orchestrator context at dispatch time was ~10-15% (fresh handoff).

Adversarial review at writing-plans + executing-plans phases still applies; the brainstorm phase contributes nothing the locked decisions don't already provide.

If during plan-drafting the implementer discovers a design dimension the operator did NOT lock, surface in return report rather than deciding unilaterally.

---

## Appendix B: Pre-dispatch baseline verification (run in your shell at dispatch time)

```bash
# Verify HEAD + clean tree
git log --oneline -1
git status -uno

# Verify scope-of-work source-of-truth
grep -n "hypothesis_label web-form gap" docs/phase3e-todo.md

# Verify the helper actually lives in swing/cli.py (phase3e-todo says swing.web.view_models.dashboard — incorrect)
grep -rn "_lookup_active_recommendation_label" swing/

# Verify no other importers from swing.cli
grep -rn "from swing.cli import" .
grep -rn "_lookup_active_recommendation_label" tests/

# Verify base-layout doesn't reference hypothesis_label (5-VM rule check)
grep -rn "hypothesis_label" swing/web/templates/base.html.j2

# Verify EntryRequest already has the field (no dataclass change needed)
grep -n "hypothesis_label" swing/trades/entry.py
grep -n "hypothesis_label" swing/data/models.py
grep -n "hypothesis_label" swing/data/repos/trades.py

# Verify canonicalize_hypothesis_label semantics
grep -n "canonicalize_hypothesis_label" swing/trades/entry.py

# Capture fast-suite baseline
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected output sketch:
- HEAD = `f85c242` (or later commit on main; clean tree).
- `_lookup_active_recommendation_label` defined at `swing/cli.py:339`; called at `swing/cli.py:491`. NOT in `swing/web/`.
- No external importers of the helper (underscore prefix).
- `base.html.j2` does not reference `hypothesis_label` (5-VM rule does NOT apply).
- `EntryRequest.hypothesis_label: str | None = None` exists at `swing/trades/entry.py:94`.
- `Trade.hypothesis_label` exists in `swing/data/models.py`.
- `record_entry` calls `canonicalize_hypothesis_label(req.hypothesis_label)` at `swing/trades/entry.py:201`.
- Fast suite: 1366 passed, 1 skipped (or higher if subsequent dispatches landed first).

If any of these don't match, surface in return report — the brief was drafted against a specific repo snapshot.
