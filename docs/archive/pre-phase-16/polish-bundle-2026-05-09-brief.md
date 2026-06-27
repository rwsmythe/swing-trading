# Polish bundle 2026-05-09 — combined dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Ship five small operator-surfaced UX/CLI improvements as a single TDD-disciplined dispatch on a worktree branch:

1. **3e.5** — Add a "updated today?" badge to each open-positions row on the dashboard (Phase 8 daily-management UX completion).
2. **3e.6** — Auto-return to dashboard after submitting a daily-management event on the trade-detail page (HX-Redirect to `/`).
3. **3e.11** — Strip "Phase 6" internal nomenclature from `swing review` CLI help text.
4. **3e.13** — Add a top-nav "Reviews" link to `/reviews/pending` so the Phase 6 review list view is reachable from the dashboard (V1: link only; count badge deferred to V1.5 follow-up).
5. **3e.14** — Add an inline "Complete review" link to each pending cadence card on the dashboard (per-card direct-action surface — complements 3e.13's top-nav reachability with workflow-friction reduction at the visible-status surface).

**Expected duration:** ~1.5-2 hr implementation + ~30-45 min dispatch overhead (worktree + TDD + adversarial review). Total ~2.5-3 hr.

**Skill posture:**
- Invoke `superpowers:subagent-driven-development` directly (NOT via the `copowers:executing-plans` wrapper, which bundles writing-plans + adversarial-critic without marker-file management between phases).
- DO NOT invoke `superpowers:writing-plans` or `copowers:brainstorming` — design is locked in §0.3 below; this dispatch is small enough to skip the formal plan-writing cycle.
- Adversarial review via `copowers:adversarial-critic` after all 3 task families land. Iterate to NO_NEW_CRITICAL_MAJOR. Expected 2-3 Codex rounds (small surface; converges fast).

---

## §0 Read first

### §0.1 Backlog entries (canonical context for each task)
- `docs/phase3e-todo.md` §3e.5 (daily management "updated today?" indicator)
- `docs/phase3e-todo.md` §3e.6 (auto-return to dashboard after daily-mgmt submit)
- `docs/phase3e-todo.md` §3e.11 (CLI Phase 6 leak)
- `docs/phase3e-todo.md` §3e.13 (top-nav Reviews link)
- `docs/phase3e-todo.md` §3e.14 (cadence card "Complete review" inline link)

### §0.2 Code surface

**For 3e.5 (badge):**
- `swing/web/view_models/dashboard.py` — `OpenPositionsRowVM` definition + `build_dashboard()` builder. The VM gets a new boolean field `has_update_today: bool = False` (default False for safety; populated by builder query).
- `swing/web/view_models/open_positions_row.py` — alternate constructor; verify it stays in sync.
- `swing/data/repos/daily_management.py` — repo functions; the `list_open_position_active_snapshots` function at line 246 is the closest existing pattern (same predicate family). Plan author may add a tiny new helper OR inline the query in the builder; choose whichever minimizes scope.
- `swing/web/templates/partials/open_positions_row.html.j2` — render the badge after the existing state badge (line 24 area); use a concise label like "✓ today" / "⚠ not yet".
- `swing/evaluation/dates.py` — `last_completed_session` is the writer-side session anchor (per Phase 8 §4.5; CORRECTED post-merge — the brief originally locked `action_session_for_run` here, but writers stamp `last_completed_session`; reader MUST mirror writer per CLAUDE.md "Session-anchor read/write mismatch" gotcha promoted 2026-05-09).

**For 3e.6 (HX-Redirect):**
- `swing/web/routes/trades.py` — locate the daily-management event POST handler (search for `daily-management/event` or `record_event_log`). Modify the success path to return `204 No Content` + `HX-Redirect: /` header.
- Existing precedent at the Phase 5 config page POST handler (search `HX-Redirect` in `swing/web/routes/`). Mirror exactly.
- CLAUDE.md gotchas:
  - "HTMX form-driven endpoints have two browser-only failure surfaces" (Phase 5 R1 M2)
  - "HX-Redirect target route must be verified to exist" (Phase 6 I3)

**For 3e.11 (CLI text):**
- `swing/cli.py:1174` — `"""Post-trade review (Phase 6).` (group docstring)
- `swing/cli.py:1303` — `"""Phase 6: cadence review (daily / weekly / monthly Review_Log completion)."""` (subcommand)

**For 3e.13 (Reviews nav link):**
- `swing/web/templates/base.html.j2` — nav bar location (current links: Dashboard / Watchlist / Journal / Pipeline / Config). Insert "Reviews" link between Journal and Pipeline (workflow-aligned position — review is journal-adjacent).
- `swing/web/routes/reviews.py` (or wherever the `/reviews/pending` route is registered) — verify route exists. Phase 6 R5 I3 fix established `/reviews/pending` as the canonical post-completion redirect target; route MUST be registered.

**For 3e.14 (cadence card link):**
- `swing/web/view_models/dashboard.py:292-306` — `CadenceCardVM` definition. Currently has 6 fields (cadence_type / scheduled_date / completed_date / period_start / period_end / is_pending). Needs `review_id: int` added.
- `swing/web/view_models/dashboard.py:1016-1023` — construction site. The `row` object passed in (a Review_Log row) has `id` available; populate `review_id=row.id`.
- `swing/web/templates/partials/cadence_cards.html.j2:9` — `{% if card.is_pending %}` block. Add `<a href="/reviews/{{ card.review_id }}/complete">Complete review</a>` inside this conditional.
- `/reviews/{id}/complete` route — verify registered (Phase 6 shipped this route; D.3-style assertion test pins the contract).

### §0.3 LOCKED DESIGN DECISIONS (DO NOT re-litigate)

Locked by orchestrator + operator in-thread design lock 2026-05-09. Plan implements them; does NOT brainstorm alternatives:

1. **3e.5 badge: TWO-state visual.** Show `✓ logged` (or visually similar positive marker) when a daily_management_record exists for this trade with `record_type IN ('daily_snapshot', 'event_log')` AND `is_superseded = 0` AND `review_date == last_completed_session(now()).isoformat()`. Show `⚠ pending` (or visually similar negative marker) otherwise. **POST-MERGE CORRECTION 2026-05-09:** brief originally locked `action_session_for_run(now())` for the predicate AND `✓ today / ⚠ not yet` for the labels. Both were corrected mid-dispatch by Codex R1 Major #1 + R2 Major #1: predicate must mirror writer's `last_completed_session` per Phase 8 §4.5; labels must not carry temporal claims that lie on weekends/holidays. Brief's "Plan author picks exact glyphs/labels" latitude language explicitly authorized the label change.

2. **3e.5 query placement:** plan author choice between (a) extending `list_open_position_active_snapshots` with a richer return shape OR (b) adding a tiny new helper `has_update_today_for_trades(conn, trade_ids: Iterable[int]) -> set[int]` that returns the set of trade IDs with an update today OR (c) inline subquery in `build_dashboard`. Recommendation: **(b) helper** — clean separation; reusable; testable in isolation. Plan author may override with rationale.

3. **3e.6 success-response shape:** `204 No Content` + `HX-Redirect: /` header. Mirror Phase 5 config-page POST exactly. NOT 303 + swap-target (browser swallows; per Phase 5 R1 M2 lesson). Test MUST verify (a) HX-Redirect header value AND (b) target `/` route is registered (per Phase 6 I3 lesson — TestClient verifies header but doesn't follow).

4. **3e.6 scope:** ONLY the `POST /trades/{id}/daily-management/event` handler. Do NOT touch the Phase 7 stop-adjust route (`POST /trades/{id}/stop`) or the Phase 6 review route (`POST /reviews/{id}/complete`) — those have their own success-path semantics already shipped.

5. **3e.11 replacement text:**
   - `swing/cli.py:1174` group docstring: replace with `"""Post-trade review surface — log mistakes, process grade, and outcome attribution."""`
   - `swing/cli.py:1303` subcommand docstring: replace with `"""Cadence review — complete daily / weekly / monthly Review_Log entries."""`

6. **3e.11 audit step:** run `grep -nE "Phase [0-9]|Tranche" swing/cli.py` and report any other phase-nomenclature leakage in CLI help/docstrings as a return-report finding (do NOT fix mid-dispatch unless trivial; flag for follow-up).

7. **No schema changes.** No migration. No new repo functions UNLESS plan-author choice §0.3#2(b) is taken (then ONE small helper added to `swing/data/repos/daily_management.py`).

8. **3e.13 V1 scope: link only.** Add `<a href="/reviews/pending">Reviews</a>` to base.html.j2 nav between Journal and Pipeline. NO count badge in this dispatch — V1.5 follow-up dispatch handles the badge IF operator confirms the V1 link is sufficient. Rationale: keeps the bundle scope tight; count badge would require base-layout VM extension audit (per the 5-VM rule + new-VM-inherits-fields lessons), which inflates scope beyond polish-bundle character.

9. **3e.13 nav-link position:** between Journal and Pipeline in the rendered nav. Workflow rationale: review is journal-adjacent; pipeline is data-ingest-side. Plan author MUST preserve this order — do NOT reorder existing nav links.

10. **3e.14 VM extension required.** The archived 2026-05-04 fix sketch assumed `card.review_id` existed on `CadenceCardVM` but it doesn't (verified empirically 2026-05-09 against `swing/web/view_models/dashboard.py:292-306`). Implementation MUST: (a) add `review_id: int` field to the dataclass; (b) populate `review_id=row.id` at the construction site (`:1016-1023`); (c) add the link in the template inside the existing `{% if card.is_pending %}` block. Pure VM extension + template edit — NO new repo function; NO route changes (Phase 6 shipped `/reviews/{id}/complete`).

11. **3e.14 link rendering scope:** ONLY when `card.is_pending`. Completed cadence cards do NOT render the link (no completion form needed for already-completed reviews). Mirror the existing `{% if card.is_pending %}` conditional shape.

---

## §1 Strategic context

This is the post-Phase-8-V1-polish "loose ends" bundle. Five operator-surfaced items: two from the operator-witnessed verification gate of Phase 8 ship (3e.5 + 3e.6); one from a CLI-help review (3e.11); two from review-surface reachability audits (3e.13 top-nav reachability + 3e.14 cadence-card direct-action — both lifted from operator workflow inspection during this bundle's design; 3e.14 was archived as a Phase 6 V1 follow-up 2026-05-04 and lifted back to active when surfaced again 2026-05-09). All small; all narrowly scoped; all testable via existing patterns. Bundling them avoids dispatch overhead × 5.

**Schema state (binding):** Production DB at schema_version 16 post-3e.12 ship at HEAD `c55a659`. No migration in scope. EXPECTED_SCHEMA_VERSION assertion stays at 16.

**What's NOT in scope:**
- Visual styling refinement beyond minimal badge CSS for 3e.5
- Server-side persistence of "did operator dismiss this badge?" (out of V1)
- HX-Redirect on Phase 7 stop-adjust route (different success-path semantics; see §0.3 #4)
- HX-Redirect on Phase 6 review route (already shipped per Phase 6)
- Other CLI nomenclature leaks beyond the audit step (audit findings are flagged, not fixed, per §0.3 #6)

---

## §2 Per-task specifications

### Task family A — 3e.5 daily management "updated today?" badge

**A.1** Discriminating test: with a trade that has NO daily_management_records row for today's session, the open-positions row's VM has `has_update_today == False`. Test fixture seeds an open trade + zero records; calls `build_dashboard`; asserts the row's VM field. RED before implementation.

**A.2** Discriminating test: with a trade that HAS a daily_management_records row for today's session (record_type='daily_snapshot', is_superseded=0, review_date=last_completed_session(now()).isoformat() — POST-MERGE CORRECTION 2026-05-09; brief originally said `action_session_for_run`), the VM has `has_update_today == True`. RED before implementation.

**A.3** Implementation: extend `OpenPositionsRowVM` with `has_update_today: bool = False`. Add helper per §0.3 #2 choice. Wire into `build_dashboard` (and the alternate constructor at `swing/web/view_models/open_positions_row.py` if it exists separately). Tests A.1 + A.2 → GREEN.

**A.4** Discriminating test: superseded snapshots (is_superseded=1) do NOT count as "updated today". Plan author seeds a superseded snapshot for today + nothing else; asserts `has_update_today == False`. RED-then-GREEN OR GREEN-from-A.3 if implementation already filters `is_superseded = 0`. Document which.

**A.5** Discriminating test: snapshots from yesterday's session do NOT count as "updated today". Plan author seeds a snapshot for `last_completed_session(now() - 1 day).isoformat()` + nothing else; asserts `has_update_today == False`. RED-then-GREEN OR GREEN-from-A.3 (predicate filters by today's session). POST-MERGE CORRECTION 2026-05-09: brief originally said `action_session_for_run`.

**A.6** Template change: render the badge in `partials/open_positions_row.html.j2` after the state badge (around line 24). Plan author picks exact glyphs/labels.

**A.7** Discriminating test: rendered HTML for a row with `has_update_today=True` contains the positive marker glyph/label; rendered HTML for `has_update_today=False` contains the negative marker. TestClient-based test against the dashboard route OR a direct render-the-row test if the template is independently testable.

**Acceptance:**
- Every open-positions row renders a two-state badge.
- Badge is correctly populated based on today's-session predicate filtering on `is_superseded=0` snapshots.
- All 5+ new tests pass; ~0 regressions.

### Task family B — 3e.6 auto-return to dashboard

**B.1** Discriminating test: POST `/trades/{id}/daily-management/event` with valid form data returns `204 No Content` AND `HX-Redirect: /` header. RED before implementation (current behavior is some-other-success-shape; the test asserts the new shape).

**B.2** Implementation: modify the daily-management event POST handler success path to return `Response(status_code=204, headers={"HX-Redirect": "/"})` (or whichever the existing FastAPI response idiom uses; mirror Phase 5 config-page POST exactly).

**B.3** Discriminating test: `/` route IS registered in the app's route table (programmatic verification per Phase 6 I3 lesson — `assert any(getattr(r, "path", None) == "/" for r in app.routes)` OR similar). RED-then-GREEN OR GREEN-from-existing (the dashboard route was registered by Phase 1; this test pins the contract for future).

**B.4** Discriminating test: error-path response is UNCHANGED. POST with invalid data should still re-render the form (or whatever the existing error response shape is) — NOT redirect to `/`. This guards against accidentally redirecting on validation errors.

**Acceptance:**
- Successful daily-management event POST returns 204 + HX-Redirect: /.
- Browser using htmx.js will navigate to dashboard after successful submit (operator-witnessed gate post-merge).
- Error-path behavior unchanged.

### Task family C — 3e.11 CLI Phase 6 leak

**C.1** Discriminating test: `python -m click swing/cli.py review --help` (or click's testing utility — `runner.invoke(main, ["review", "--help"])`) produces output that does NOT contain "Phase". RED before implementation.

**C.2** Discriminating test: `swing review complete --help` output does NOT contain "Phase". RED before implementation. (POST-MERGE CORRECTION 2026-05-09: brief originally said `swing review cadence --help`; actual subcommand is `complete`, not `cadence`. Implementer used the correct command name.)

**C.3** Implementation: edit the two docstrings per §0.3 #5. Tests C.1 + C.2 → GREEN.

**C.4** Audit step (NOT a fix): run `grep -nE "Phase [0-9]|Tranche" swing/cli.py` and capture findings in the return report. If findings are trivial (e.g., a comment saying "Phase 7 added X" with no operator-facing surface), flag for follow-up. If a finding IS operator-facing (another `--help` text leak), the implementer may add to scope IF the fix is also trivial; otherwise flag for follow-up.

**Acceptance:**
- `swing review --help` and `swing review complete --help` no longer leak "Phase" nomenclature. (POST-MERGE CORRECTION 2026-05-09: subcommand is `complete`, not `cadence`.)
- Audit step output captured in return report.

### Task family D — 3e.13 top-nav Reviews link

**D.1** Discriminating test: nav rendered HTML contains `<a href="/reviews/pending">Reviews</a>` (or equivalent — assert href value AND visible text). Test against any base-layout-rendered route (e.g., dashboard `/`). RED before implementation.

**D.2** Discriminating test: nav-link order preserved — Dashboard → Watchlist → Journal → **Reviews** → Pipeline → Config. Test asserts the rendered HTML's nav links appear in that exact order. RED before implementation.

**D.3** Discriminating test: `/reviews/pending` route IS registered in the app's route table — `assert any(getattr(r, "path", None) == "/reviews/pending" for r in app.routes)`. RED-then-GREEN OR GREEN-from-existing (Phase 6 R5 I3 fix established this route; this test pins the contract for future). Per Phase 6 I3 lesson — pre-empt nav-link-points-at-unrouted-target regression.

**D.4** Implementation: edit `swing/web/templates/base.html.j2` to insert the nav link between Journal and Pipeline per §0.3 #9. Tests D.1 + D.2 → GREEN.

**Acceptance:**
- Dashboard (and every base-layout-extending page) renders a "Reviews" nav link in the correct order position.
- Link href targets the registered `/reviews/pending` route.
- All 3 new tests pass; ~0 regressions in existing nav-rendering tests.

### Task family E — 3e.14 cadence card "Complete review" inline link

**E.1** Discriminating test: a pending cadence card (`is_pending == True`) renders an `<a href="/reviews/{review_id}/complete">Complete review</a>` link with the correct review_id. Test seeds a Review_Log row with `completed_date=NULL`; calls `build_dashboard`; asserts the cadence card's rendered HTML contains the link with the populated review_id. RED before implementation.

**E.2** Discriminating test: a completed cadence card (`is_pending == False`) does NOT render the "Complete review" link. RED-then-GREEN OR GREEN-from-implementation if the conditional is shipped correctly.

**E.3** Implementation: extend `CadenceCardVM` (`swing/web/view_models/dashboard.py:292-306`) with `review_id: int` field. Update construction site (`:1016-1023`) to populate `review_id=row.id`. Edit template `swing/web/templates/partials/cadence_cards.html.j2` to add the link inside the existing `{% if card.is_pending %}` block. Tests E.1 + E.2 → GREEN.

**E.4** Discriminating test: `/reviews/{id}/complete` route IS registered in the app's route table — `assert any(getattr(r, "path", None) == "/reviews/{id}/complete" for r in app.routes)` (with appropriate path-pattern matching for the `{id}` placeholder per FastAPI's route-discovery API). RED-then-GREEN OR GREEN-from-existing (Phase 6 shipped this route). Per Phase 6 I3 lesson — pre-empt link-points-at-unrouted-target regression.

**E.5** Discriminating test: existing cadence-card rendering tests (if any) STILL pass with the VM extension. Per the "additive dataclass changes are NOT zero-cost" archived lesson — `CadenceCardVM` extension may break hand-constructed test fixtures. Plan author audits via `grep -rn "CadenceCardVM(" tests/` BEFORE shipping to enumerate fixture sites that need updates.

**Acceptance:**
- Pending cadence cards render a "Complete review" link with the correct review_id.
- Completed cadence cards do NOT render the link.
- All 4-5 new E.x tests pass; existing CadenceCardVM-construction tests adjusted as needed; ~0 regressions.

### Task family Z — Final verification

**Z.1** Run `python -m pytest -m "not slow" -q` — assert 2099 → ~2113-2119 (N ≥ 13: 5 from family A + 1 from family B + 2 from family C + 3 from family D + 4-5 from family E + audit fixture-update offsets; total bias ~13-17 new tests, possibly with offsetting test adjustments to existing CadenceCardVM-construction fixtures).

**Z.2** Run `ruff check swing/` — assert baseline 78 preserved.

**Z.3** Operator-witnessed gate flagged PENDING (operator runs post-merge):
- Surface 1 (3e.5): visit dashboard; confirm every open-positions row shows the two-state badge with correct state per trade.
- Surface 2 (3e.6): submit a daily-management event on any open trade's detail page; confirm browser navigates back to dashboard.
- Surface 3 (3e.11): run `swing review --help`, `swing review complete --help`, `swing trade review --help`, `swing trade entry --help`, `swing trade exit --help`, `swing trade stop-adjust --help` from terminal; confirm no "Phase" or "Tranche" text appears in any. (POST-MERGE CORRECTION 2026-05-09: subcommand is `complete`, not `cadence`. Surface widened to cover the 4 audit-found additional commands fixed in C.3 in-scope expansion.)
- Surface 4 (3e.13): visit dashboard; confirm "Reviews" nav link appears between Journal and Pipeline; click "Reviews" → navigates to `/reviews/pending`; review list view renders.
- Surface 5 (3e.14): visit dashboard; for any pending cadence card, confirm "Complete review" link is rendered; click → navigates to `/reviews/{id}/complete`; completion form renders. For any completed cadence card, confirm NO "Complete review" link is rendered.

---

## §3 Binding conventions (project-wide; restated for this dispatch)

- **Worktree path:** `.worktrees/polish-bundle-2026-05-09/` at repo root (per the 2026-05-08 lesson on worktree directory path discipline). NOT under `.claude/worktrees/...`.
- **Worktree branch:** `polish-bundle-2026-05-09`.
- **Worktree verify-command:** `$env:PYTHONPATH = "."; python -m swing.cli web` from inside the worktree dir for any runtime checks. Pytest is cwd-based; doesn't need PYTHONPATH adjustment.
- **Commits:** conventional-commits with `Task X.Y` prefix per project precedent. Example: `feat(web): Task A.3 — extend OpenPositionsRowVM with has_update_today field`. Internal-Codex review fixes use `(internal)` qualifier per existing convention. Subject-only ERE grep: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task [A-C]\.[0-9]'`.
- **NO `git add -A`** per Phase 8 R1 Critical 1 lesson. Explicit `git add <file>` per task. The dispatch must NOT stage stray files (`.copowers-subagent-active`, pytest scratch, etc.).
- **TDD:** RED → GREEN → COMMIT per task. One red-green cycle per logical change.
- **Marker-file workflow:** orchestrator creates `.copowers-subagent-active` before subagent dispatch + removes before adversarial-critic. Subagents physically cannot invoke Codex per the global PreToolUse hook. Implementer does NOT touch the marker file.
- **Schema unchanged** at v16; no migration runs.

---

## §4 Adversarial review (target + watch items)

**Target:** NO_NEW_CRITICAL_MAJOR after 2-3 Codex rounds. Small surface; should converge fast.

**Watch items the brief should pass to adversarial-critic:**

1. **3e.5 predicate correctness.** Does the helper/query correctly filter `is_superseded = 0` AND `record_type IN ('daily_snapshot', 'event_log')` AND `review_date == today_session`? Discriminating tests A.4 (superseded) + A.5 (yesterday's session) cover the two failure modes; Codex should verify these tests would FAIL with a sloppy predicate.

2. **3e.5 base-layout VM rule.** Does `OpenPositionsRowVM` extension propagate cleanly through every consumer? Specifically: the alternate constructor at `swing/web/view_models/open_positions_row.py`. Per CLAUDE.md "base.html.j2 is shared" gotcha — though this VM doesn't extend the base layout directly, dual constructor patterns are the analogous risk surface.

3. **3e.6 HX-Redirect target route.** Per Phase 6 I3 lesson — does the test assert `/` route is registered? If only the header value is asserted (without route-existence verification), regression risk is real.

4. **3e.6 error-path preserved.** Does the implementation accidentally apply the HX-Redirect to error responses too? Discriminating test B.4 covers this.

5. **3e.11 audit findings.** Did the implementer run the audit AND report findings, even if no additional fixes were applied? Captured-but-deferred is acceptable; missed-and-not-reported is not.

6. **No `git add -A`.** Per Phase 8 R1 Critical 1 lesson.

7. **Test-fixture PRAGMA state.** For tests that touch the `daily_management_records` schema (Family A), fixture connections should set `foreign_keys=ON` per Phase 7 hotfix lesson. Verify the test fixtures use `ensure_schema(db_path)` (which sets PRAGMA correctly) rather than bare `connect(db_path)`.

8. **3e.13 nav-link target route resolves.** Per Phase 6 I3 lesson — D.3 test asserts `/reviews/pending` is registered in the app's route table. If the implementation adds the nav link without verifying route existence, regression risk is real (operator clicks Reviews → 404). The Phase 6 R5 I3 fix established this route; the test pins the contract.

9. **3e.13 nav-link order preservation.** D.2 asserts the nav links appear in `Dashboard → Watchlist → Journal → Reviews → Pipeline → Config` order. Verify the implementation does NOT accidentally reorder existing links during the insert.

10. **3e.13 base-layout scope discipline.** V1 = link only; NO count badge. If the implementation creeps toward adding a count badge (which would require base-layout VM extension audit per the 5-VM rule), halt + flag scope creep in return report.

11. **3e.14 VM extension regressions.** Per "Additive dataclass field changes are NOT zero-cost" archived lesson — extending `CadenceCardVM` with `review_id: int` may break hand-constructed test fixtures. Verify implementer ran `grep -rn "CadenceCardVM(" tests/` BEFORE shipping + updated all hand-constructed sites. If any test was missed, Z.1 fast-suite assertion catches it.

12. **3e.14 link conditional correctness.** Verify the link is ONLY rendered when `card.is_pending` is True. Discriminating tests E.1 + E.2 cover both paths; Codex should verify these tests would FAIL with a sloppy conditional (e.g., always-rendered link).

---

## §5 Done criteria

- [ ] All 5 task families' (A + B + C + D + E) acceptance criteria met (per §2).
- [ ] `python -m pytest -m "not slow" -q` shows ~2113-2119 passing (was 2099 pre-dispatch).
- [ ] `ruff check swing/` shows baseline 78 violations preserved.
- [ ] Adversarial review reaches NO_NEW_CRITICAL_MAJOR.
- [ ] §0.3 design locks honored exactly (no scope expansion without explicit operator authorization in return report).
- [ ] Audit step from §2 C.4 captured in return report.
- [ ] Operator-witnessed gate (Z.3 surfaces 1, 2, 3) flagged PENDING for orchestrator → operator post-merge walkthrough.
- [ ] Worktree branch ready for orchestrator merge.

---

## §6 Return report format

```markdown
# Polish bundle 2026-05-09 — return report

## HEAD
{worktree branch HEAD SHA + branch name}
BASELINE_SHA: c55a659

## Tests
{baseline 2099} → {final N + delta}
ruff baseline 78 preserved: {yes/no}

## Tasks landed
- Task A.1 / A.2 / A.3 / A.4 / A.5 / A.6 / A.7 — {commit SHAs + one-line per commit}
- Task B.1 / B.2 / B.3 / B.4 — {commit SHAs}
- Task C.1 / C.2 / C.3 — {commit SHAs}
- C.4 audit step findings: {captured findings; flag any operator-facing leaks for follow-up}
- Task D.1 / D.2 / D.3 / D.4 — {commit SHAs}
- Task E.1 / E.2 / E.3 / E.4 / E.5 — {commit SHAs}

## §0.3 design lock honored
- 3e.5 badge two-state: {confirmed / deviated with rationale}
- 3e.5 query placement choice: {a / b / c per §0.3 #2}
- 3e.6 response shape: 204 + HX-Redirect: / → {confirmed}
- 3e.11 replacement text: {confirmed}
- 3e.13 link-only V1 scope (no count badge): {confirmed}
- 3e.13 nav-link order Dashboard → Watchlist → Journal → Reviews → Pipeline → Config: {confirmed}
- 3e.14 CadenceCardVM extension (review_id field added; construction site updated; hand-constructed test fixtures audited): {confirmed}
- 3e.14 link conditional (rendered only when card.is_pending == True): {confirmed}

## Adversarial review chain
- R1: {N critical / N major / N minor} → {ACCEPTED-with-rationale or FIXED in commit SHA}
- R2 / R3 / ...
- R-final: NO_NEW_CRITICAL_MAJOR

## Deviations
{Plan-template fixture defects, scope adjustments, or any §0.3 lock deviation with explicit rationale}

## Open questions for orchestrator
{None blocking; or list}
```

---

## §7 If you get stuck

- **Plan-template fixture defects (per Phase 6/8 lesson):** ACCEPT-with-rationale + correct inline + flag in return report. DO NOT halt unless defect blocks an entire task family.
- **Adversarial-review round count exceeds 4:** look at chain-shape (convergent = healthy; thrash = halt + escalate). Per Phase 7 Sub-B + Phase 8 lesson family.
- **3e.5 base-layout VM gotcha surfaces:** if `OpenPositionsRowVM` extension breaks an unrelated route via the 5-VM rule, halt + escalate. Should not happen (this VM is consumer-scoped to dashboard) but flag if it does.
- **3e.6 HX-Redirect target route does NOT resolve:** halt + escalate. The dashboard `/` route should exist (Phase 1 + every phase since); if somehow it doesn't, that's a pre-existing bug.
- **3e.11 audit reveals MANY phase-nomenclature leaks:** if >5 findings, ship the locked 2 fixes only + flag the rest as a separate dispatch. Don't expand scope mid-dispatch.

---

## §8 Dispatch metadata

- **Project root:** `c:\Users\rwsmy\swing-trading`
- **Base SHA:** `c55a659` (current main HEAD; verify via `git rev-parse main`)
- **Worktree path:** `.worktrees/polish-bundle-2026-05-09/`
- **Worktree branch:** `polish-bundle-2026-05-09`
- **EXPECTED_SCHEMA_VERSION:** 16 (unchanged)
- **Pre-dispatch test baseline:** 2099 fast tests + 1 skipped
- **Pre-dispatch ruff baseline:** 78
- **Test delta projection:** +13 to +17 fast tests (5 from family A + 1 from family B + 2 from family C + 3 from family D + 4-5 from family E; possibly with offsetting fixture updates per the additive-dataclass-cost lesson)
