# Phase 8 V1 polish — writing-plans brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author a writing-plans-grade plan for two operator-witnessed Phase 8 V1 follow-ups bundled into a single dispatch:

1. **Item #2 — Dashboard "Detail" button.** Add a "Detail" navigation button to each dashboard open-positions row at `partials/open_positions_row.html.j2`, mirroring the existing "Adjust stop" / "Exit" button pattern. Target: `/trades/{id}` (the existing trade-detail page where the Phase 8 daily-management event form lives).
2. **Item #1 — Phase 7 stop-adjust legacy path surfaces in Phase 8 timeline.** Phase 7's `/trades/{id}/stop` legacy route writes `trade_events` rows but no Phase 8 `event_log` row, so legacy stop changes don't appear in the per-trade `daily-management-timeline` view. Lock: **VM-level read-side union** in `build_daily_management_timeline_vm` — query Phase 7 `trade_events`; dedupe events that already have a Phase 8 `event_log` linkage via `linked_trade_event_id`; render orphans inline as a third `record_type` value with the label **"Stop adjustment (legacy quick-adjust)"**.

**Expected duration:** ~2-4 hours of writing-plans work, producing a plan implementable in ~3-5 hr executing-plans dispatch (~12-25 fast tests added; ~150-300 plan lines).

**Skill posture:**
- Invoke `superpowers:writing-plans` end-to-end.
- Adversarial review via `copowers:writing-plans` wrapper (writing-plans + adversarial-critic chained).
- DO NOT invoke `copowers:brainstorming` — design has been locked in-thread by orchestrator + operator (per §0.3 below).
- DO NOT invoke `superpowers:subagent-driven-development` — that skill fires at executing-plans, not at writing-plans.

---

## §0 Read first

Before drafting any plan, the implementer MUST read these:

### §0.1 Phase 8 spec + plan (canonical context)

- `docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md` — Phase 8 design spec (875 lines). Pay special attention to §7.2 (timeline composition) + §A.1 (single-transaction discipline; service-vs-repo distinction).
- `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md` — Phase 8 executing-plans plan (4140 lines; the precedent for plan rigor in this project). Skim for shape; binding green gates, discriminating-test discipline, plan task structure.

### §0.2 Phase 7 + Phase 8 code surface

- `swing/web/view_models/trades.py:1077-1144` — `DailyManagementTimelineVM` + `_record_to_timeline_row` + `build_daily_management_timeline_vm`. The function the plan extends.
- `swing/data/repos/daily_management.py:208-243` — `list_for_trade_timeline`. Currently returns only `daily_management_records`; plan does NOT modify this function (per locked design, union happens at VM layer).
- `swing/data/repos/trades.py:282-294` — `list_events_for_trade`. Existing repo function returning `trade_events` for a trade ordered by `(ts, id)`. The VM-side helper to query Phase 7 events.
- `swing/web/templates/partials/daily_management_timeline.html.j2` — current timeline rendering. Template branches on `record_type`; plan adds a third branch for `trade_event_legacy`.
- `swing/web/templates/partials/open_positions_row.html.j2` — current dashboard row. Plan adds a "Detail" button alongside Exit / Adjust stop in `<td class="row-actions">`.
- `swing/web/routes/trades.py` — search for `build_daily_management_timeline_vm` consumers to confirm route plumbing remains unchanged (the function's signature stays the same; only its return-shape extends).

### §0.3 Locked design (DO NOT re-litigate)

The following decisions are LOCKED by orchestrator + operator in-thread design lock 2026-05-07. The plan implements them; it does NOT brainstorm alternatives:

1. **Item #2 button label:** "Detail". Element: `<button>` with `hx-get="/trades/{id}"` + `hx-push-url="true"` + `hx-target="body"` + `hx-swap="outerHTML"` OR a plain `<a class="button" href="/trades/{id}" onclick="event.stopPropagation()">Detail</a>`. Plan author picks the cleaner option after verifying which pattern matches existing dashboard buttons (Exit + Adjust stop both use HTMX). **Recommendation: plain `<a>` because the destination is a full-page navigation, NOT an HTMX swap into the row** — but plan author may override after checking.
2. **Item #1 union approach:** VM-level (option B from design QA). Repo functions stay atomic. Composition + dedup happens in `build_daily_management_timeline_vm`.
3. **Item #1 dedup rule:** A `trade_events` row is an "orphan" iff its `id` does NOT appear in `daily_management_records.linked_trade_event_id` (event_log rows only) for the same trade. Orphans render in the timeline; non-orphans are the responsibility of the existing `event_log` rendering (no double-display).
4. **Item #1 event-type filter:** ONLY `event_type = 'stop_adjust'` orphan trade_events surface in the timeline. Entry / exit / partial / review_complete events have their own existing surfaces (dashboard, exit form, review form); do NOT re-surface them in the timeline. Rationale: focused fix matching operator's reported gap; narrower test surface; no UX regression on entry/exit trade_events.
5. **Item #1 display label for orphan Phase 7 trade_events:** "Stop adjustment (legacy quick-adjust)". Render in template (not in VM); VM carries the `record_type` discriminator value `trade_event_legacy` + raw `event_type` + decoded payload fields needed for display.
6. **Item #1 row-VM shape:** Plan author chooses between (i) extending `DailyManagementTimelineRowVM` with optional Phase 7 fields (single dataclass; template branches on `record_type`) OR (ii) creating a sibling `LegacyStopAdjustTimelineRowVM` and changing the timeline VM's `rows` to a heterogeneous tuple. Recommendation: **(i) extend the existing dataclass** — fewer template changes, parallel to existing `daily_snapshot`/`event_log` pattern. New required-on-`trade_event_legacy` fields: `trade_event_id` (PK from trade_events) + `event_type` (TEXT) + payload-decoded `prior_stop` + `new_stop` + `rationale` + `notes`. Existing daily_snapshot/event_log fields stay nullable on `trade_event_legacy` rows.
7. **Item #1 sort key:** Same canonical ORDER BY as existing timeline — `(review_date ASC, created_at ASC, management_record_id ASC)`. Trade_events DON'T have `review_date` or `created_at` columns; map: `review_date := DATE(trade_events.ts)`, `created_at := trade_events.ts`, `management_record_id := -trade_events.id` (negative to ensure trade_events PKs don't collide with daily_management_records PKs in the tiebreak; or use a sentinel column-set). Plan author finalizes the exact mapping but the key constraint is **stable chronological ordering with deterministic tiebreaks**.
8. **Brainstorm-skip:** Per Phase 5 + Phase 6 precedent for small-scope follow-ups. Plan goes through writing-plans → executing-plans only. No brainstorm dispatch.

---

## §1 Strategic context

### Why these two items together

Both surface from Phase 8's operator-witnessed verification gate (2026-05-07). Both touch the trade-detail page UX. Item #2 makes the detail page reachable from the dashboard (currently only via direct URL); Item #1 makes the detail page's timeline complete (currently misses legacy stop-adjust events). Bundled because:
- Both share the operator-witnessed verification gate (visit detail page from dashboard → see Phase 7 stop-adjust event in timeline).
- Both are bounded by the existing schema; no migration needed.
- Both are pure web-layer changes (routes/templates/VMs); no service-layer or repo-layer changes.

### Schema state (binding)

Production DB at schema_version 16 post-Phase-8 ship (`ddfdfcb`). Tables in scope:
- `daily_management_records` — Phase 8 (`record_type IN ('daily_snapshot', 'event_log')`).
- `trade_events` — Phase 7 (event_type values include `stop_adjust`, `entry`, `exit`, `partial_exit`, `review_complete`, etc.).
- `daily_management_records.linked_trade_event_id` — Phase 8 column (NULLABLE FK to `trade_events.id`); set by Phase 8 form's `record_event_log` for stop_change events; NULL otherwise.

**No schema changes in this dispatch.** Plan §0 acceptance criteria asserts `EXPECTED_SCHEMA_VERSION == 16` — same as current. Migration runner not exercised.

### What's NOT in scope

- Changing the legacy `/trades/{id}/stop` route. (That's option B from design QA — explicitly NOT chosen. Future dispatch may revisit if operator wants audit-chain symmetry; not orchestrator-blocking.)
- Surfacing entry/exit/partial trade_events in the timeline. (Per §0.3 #4; entries/exits have their own surfaces.)
- Extending event_log to non-stop-change event types. (Phase 8 V2 territory.)
- Extending `record_event_log` service. (Phase 8 V2 territory.)
- Backfilling existing orphan trade_events into event_log. (The orphans render via the new union; backfill would be redundant.)
- Visual-styling polish beyond minimal "Detail" button + "(legacy quick-adjust)" label rendering.
- emotional_state form stale checkbox state (Phase 8 V1 follow-up #3 — separate dispatch if operator confirms confusion).
- Spec wording GAP-FLAGGED vs gap-by-absence (Phase 8 V1 follow-up #4 — cosmetic deferred).

---

## §2 Per-task specifications (plan author elaborates)

The plan should partition into N tasks (plan author decides N; recommend 6-9 tasks). Each task includes per-Phase-6/7/8 plan precedent: red phase test → minimal implementation → green verification → discriminating-test cycle.

### Task family A — Detail button (Item #2)

**A.1** Discriminating test for "Detail" button presence + target.
**A.2** Template change: add `<a>` (or HTMX button) to row-actions cell, mirror Exit/Adjust pattern with `event.stopPropagation()`.
**A.3** Discriminating test for click-through navigation to `/trades/{id}` (TestClient `follow_redirects=False`; assert href OR HX-Redirect target; if plain `<a>`, simpler — assert anchor href; no follow needed).
**A.4** Verify the existing `/trades/{id}` route resolves (assert route registered: `assert any(getattr(r, 'path', None) == f"/trades/{id}" or matches pattern r in app.routes)`). Per Phase 6 lesson — HX-Redirect target route must be verified to exist.

**Acceptance:**
- Dashboard renders "Detail" button on every open-positions row.
- Clicking the button navigates to `/trades/{id}` (full-page nav, not HTMX swap into the row).
- Click does NOT trigger row-expand (`event.stopPropagation()` works).
- All ~3 new tests pass; ~0 regressions.

### Task family B — Timeline union (Item #1)

**B.0** Survey + verification: read Phase 7 `trade_events` schema (CHECK constraint on `event_type`; rows present in production DB); confirm `daily_management_records.linked_trade_event_id` semantics (NULLABLE FK, set by Phase 8 record_event_log only for stop_change events); confirm `_record_to_timeline_row` shape.

**B.1** Discriminating test: timeline VM does NOT currently surface Phase 7 stop_adjust orphans. Construct fixture: insert trade + insert orphan trade_event with event_type='stop_adjust' + (no event_log row) → call build_daily_management_timeline_vm → assert the orphan does NOT appear (RED for this test BEFORE implementation; will flip GREEN after B.3).

**B.2** Extend `DailyManagementTimelineRowVM` with optional Phase 7 fields per §0.3 #6: `trade_event_id: int | None`, `event_type: str | None` (raw trade_events.event_type), `legacy_prior_stop: float | None`, `legacy_new_stop: float | None`, `legacy_rationale: str | None`, `legacy_notes: str | None`. Existing fields stay; defaults `None` for non-`trade_event_legacy` rows.

**B.3** Extend `build_daily_management_timeline_vm`:
- After fetching `records = list_for_trade_timeline(...)`, additionally fetch `events = list_events_for_trade(conn, trade_id=trade_id)`.
- Compute `linked_event_ids = {r.linked_trade_event_id for r in records if r.record_type == 'event_log' and r.linked_trade_event_id is not None}`.
- Filter `events` to `orphan_stop_adjusts = [e for e in events if e.event_type == 'stop_adjust' and e.id not in linked_event_ids]`.
- Construct `DailyManagementTimelineRowVM` for each orphan with `record_type='trade_event_legacy'`, decoded fields per §0.3 #6, sort key per §0.3 #7.
- Merge `[record_to_row(r) for r in records] + [orphan_to_row(e) for e in orphans]`; sort by `(review_date, created_at, management_record_id)` tiebreak.
- Return the unified `DailyManagementTimelineVM`.

**B.4** Helper function: `_orphan_stop_adjust_to_timeline_row(event: TradeEvent) -> DailyManagementTimelineRowVM`. Decode `payload_json` (JSON-text) for `prior_stop` + `new_stop` (per Phase 7 stop_adjust payload shape — implementer verifies the actual payload field names from `swing/trades/stop_adjust.py` or the `trade_events.payload_json` shape in production DB). Map per §0.3 #7.

**B.5** Update template `daily_management_timeline.html.j2` to branch on `record_type == 'trade_event_legacy'` and render the row label "Stop adjustment (legacy quick-adjust)" + show prior_stop → new_stop transition + rationale + notes.

**B.6** Discriminating test (B.1's flip): orphan stop_adjust now appears in timeline; non-orphan (linked to event_log) stop_adjust does NOT (event_log version is canonical).

**B.7** Discriminating test for non-stop_adjust filtering: insert orphan trade_event with event_type='exit' → does NOT appear in timeline (per §0.3 #4).

**B.8** Discriminating test for sort order: insert mix of daily_snapshots + event_logs + orphan trade_events; assert the unified timeline orders chronologically.

**B.9** Discriminating test for dedup: insert a stop_adjust trade_event AND a corresponding event_log row referencing it via `linked_trade_event_id`; assert the trade_event does NOT double-appear; only the event_log row surfaces.

**Acceptance:**
- Phase 7 orphan stop_adjust trade_events surface in `/trades/{id}` timeline labeled "Stop adjustment (legacy quick-adjust)".
- Phase 8 event_log stop changes (with linked_trade_event_id) continue to surface as-is; the trade_event they reference does NOT double-appear.
- Non-stop_adjust trade_events (entry / exit / partial / review_complete) do NOT surface in timeline.
- Sort order is stable + chronological.
- All ~7-8 new B.x tests pass; ~0 regressions in existing timeline tests.

### Task family Z — Final verification

**Z.1** Run fast suite; assert pre-dispatch baseline (1940 → 2079 post-Phase-8) + ~10-15 new tests = ~2089-2094 expected.
**Z.2** Run `ruff check swing/`; assert ruff baseline 78 preserved.
**Z.3** Mark all tasks complete in plan; produce return report per §6 below.

---

## §3 Binding conventions (project-wide; restated for this dispatch)

- **Branch:** worktree-isolated branch off `main` HEAD (`c88b83f`+ at dispatch start). Branch name suggested: `phase8-v1-polish`. Per `superpowers:using-git-worktrees`.
- **Worktree verify-command:** if any task needs runtime verification via CLI entry point (likely none for this dispatch — pure pytest suffices), use `$env:PYTHONPATH = "."; python -m swing.cli web` from inside the worktree dir.
- **Commits:** conventional-commits per `Task X.Y` prefix. Per orchestrator-context.md "commit message convention." Example: `feat(web): Task A.2 — add Detail button to dashboard open-positions row`. Internal-Codex review fixes use `(internal)` qualifier per existing convention. Subject-only ERE grep for observable verification: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task [A-Z]\.[0-9]'`.
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task discipline.
- **Phase isolation:** `swing/data/repos/` consumed read-only (no new repo functions; the existing `list_events_for_trade` is the consumer). `swing/web/view_models/trades.py` + `swing/web/templates/partials/daily_management_timeline.html.j2` + `swing/web/templates/partials/open_positions_row.html.j2` are in-scope for modification. `swing/trades/` consumed read-only.
- **No schema changes.** No migration. No new repo functions. No new service-layer functions.
- **Tests:** `python -m pytest -m "not slow" -q` MUST stay green throughout. Slow suite not exercised.
- **Ruff baseline:** 78 errors. Plan must NOT introduce new violations; must NOT incidentally fix baseline (per binding conventions on baseline preservation).
- **`git add -A` is FORBIDDEN.** Per Phase 8 R1 Critical 1 lesson — use explicit `git add <file>` per task. The dispatch must NOT stage stray files (e.g., `.copowers-subagent-active` marker; pytest scratch dirs).
- **Marker-file workflow:** orchestrator creates `.copowers-subagent-active` before subagent-driven-development invocation; removes it before adversarial-critic invocation. Subagents physically cannot invoke Codex per the global PreToolUse hook.

---

## §4 Adversarial review (target + watch items)

**Target:** `NO_NEW_CRITICAL_MAJOR` after 2-5 Codex rounds. Expected convergent shape per Phase 7 Sub-B + Phase 8 brainstorm + Phase 8 writing-plans precedent — each round catches a real follow-on issue triggered by the prior round's fix; finding count tapers; chain converges with R-final 0/0/0 confirmation.

**Watch items the plan should pass to adversarial-critic at writing-plans phase:**

1. **Dedup correctness.** Does the dedup logic (`linked_event_ids` set) correctly identify all event_log → trade_event linkages? Edge case: multiple event_log rows referencing the same trade_event (shouldn't happen per Phase 8 design but verify the set-based dedup handles it). Edge case: orphan trade_event has the same id as a daily_management_records.management_record_id (PKs are independent table autoincrements — verify the sort tiebreaker doesn't assume cross-table PK uniqueness).
2. **Sort key stability.** Does the canonical ORDER BY tiebreak `(review_date, created_at, management_record_id)` preserve deterministic ordering when daily_management_records and trade_events PKs are mixed? Per §0.3 #7's negative-id-on-trade_events suggestion OR plan author's alternative.
3. **Template branch correctness.** Does the template's `record_type == 'trade_event_legacy'` branch render all required fields (label + prior_stop → new_stop + rationale + notes + timestamp)? Does it gracefully handle missing payload fields (e.g., trade_event with malformed payload_json)?
4. **Per-page fields (5-VM rule).** Does the trade-detail page's VM (the page that renders the timeline section) inherit all `base.html.j2` dereferenced fields with safe defaults? Per existing CLAUDE.md gotcha. (Detail page should already be compliant per Phase 8 ship; verify no regression.)
5. **HX-Redirect target route resolves.** Per Phase 6 lesson — Item #2's "Detail" button targets `/trades/{id}`. If the plan uses a plain `<a href>`, this is moot (browser navigates directly; no HX-Redirect involved). If the plan uses HTMX, verify the route is registered + add a programmatic test.
6. **Event_type filter narrowness.** Does the implementation strictly filter to `event_type = 'stop_adjust'`? Discriminating test pattern: insert orphan trade_event with event_type='exit' AND with event_type='entry' AND with event_type='review_complete' → assert NONE appear in timeline. Per §0.3 #4.
7. **Discriminating-test arithmetic.** Per `feedback_regression_test_arithmetic.md` — every test must distinguish pre-fix from post-fix path. Hand-wave labels ("illustrative", "TODO discriminator") DO NOT satisfy the gate.
8. **Test fixture PRAGMA state.** Per Phase 7 hotfix lesson — fixture connections must set `foreign_keys=ON` to mirror production. Even though no migration runs in this dispatch, FK behavior on cross-table queries (`linked_trade_event_id` FK) needs PRAGMA state parity OR the fixture's behavior diverges from production.

---

## §5 Done criteria

- [ ] `python -m pytest -m "not slow" -q` passes; expected count ~2089-2094 (was 2079 pre-dispatch + ~10-15 new tests).
- [ ] `ruff check swing/` shows baseline 78 violations preserved.
- [ ] All Task A.x + B.x + Z.x acceptance criteria met (per per-task spec).
- [ ] Adversarial review reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Operator-witnessed verification gate PASS at:
  - **Surface 1:** Dashboard → "Detail" button visible on each open-positions row → click navigates to `/trades/{id}` → trade-detail page renders.
  - **Surface 2:** On trade-detail page, the daily-management-timeline section shows ALL of: Phase 8 daily_snapshots, Phase 8 event_log entries, Phase 7 orphan stop_adjust events labeled "Stop adjustment (legacy quick-adjust)" — interleaved chronologically.
  - **Surface 3:** A Phase 7 stop_adjust event that has a corresponding Phase 8 event_log row (linked_trade_event_id populated) does NOT double-appear in the timeline (only the event_log row renders).

Per Phase 5/6/7/8 precedent: operator-witnessed gate is BINDING for HTMX-driven UX work (per JS-test-harness gap lesson family).

---

## §6 Return report format

After all tasks land, all tests green, adversarial review NO_NEW_CRITICAL_MAJOR, return-report ONLY (no further commits without explicit operator authorization). Format mirrors Phase 7 Sub-A/Sub-B/Sub-C return reports:

```markdown
# Phase 8 V1 polish — return report

## HEAD
{commit SHA + branch}

## Tests
{baseline test count} → {final count} (+{delta})
ruff baseline preserved: {yes/no}

## Tasks landed
- Task A.1 — {commit SHA} — {one-line summary}
- Task A.2 — {commit SHA} — {one-line summary}
- ...

## Adversarial review chain
- R1: {N critical / N major / N minor} → {ACCEPTED-with-rationale / FIXED in commit SHA}
- R2: ...
- R-final: 0/0/0 confirmation

## Deviations
{Any plan-template fixture defects or task scope expansions; explicit rationale per orchestrator-context.md "Plan-template fixture defects are normal" lesson.}

## Open questions for orchestrator
{Operator-decision items surfaced during dispatch; not orchestrator-blocking.}
```

---

## §7 If you get stuck

- **Plan-template fixture defects.** Per Phase 6 + Phase 8 lessons — these are NORMAL at executing-plans phase. Implementer should ACCEPT-with-rationale + correct inline + flag in return report. DO NOT halt the dispatch unless the defect blocks an entire task family (e.g., a fundamental design bug, not a fixture-API misunderstanding).
- **Adversarial-review round count exceeds 5.** Per Phase 7 Sub-B + Phase 8 brainstorm + Phase 8 writing-plans precedent, 4-9 rounds is healthy if chain converges (each round catches fix-introduced regressions, finding count tapers). DO halt + escalate to orchestrator if R5+ has unrelated findings (thrash, not convergence).
- **Schema migration accidentally triggered.** Should not happen — no migration in scope. If it does, halt + escalate.
- **Cross-cutting predicate rewrite needed.** Should not happen — design lock §0.3 keeps repo functions read-only. If implementation discovers a cross-cutting need, halt + escalate (per Phase 7 Sub-A binding-green-gate lesson).

---

## §8 Dispatch metadata

- **Project root:** `c:\Users\rwsmy\swing-trading`
- **Base SHA:** `c88b83f` (or later main HEAD at dispatch start; verify via `git rev-parse main`)
- **Worktree branch:** `phase8-v1-polish` (suggested; plan author may rename if collision)
- **EXPECTED_SCHEMA_VERSION:** 16 (unchanged)
- **Pre-dispatch test baseline:** 2079 fast tests + 1 skipped
- **Pre-dispatch ruff baseline:** 78
- **Plan target line range:** 200-450 lines
- **Plan target test delta:** +10-15 fast tests
