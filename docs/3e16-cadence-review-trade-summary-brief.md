# 3e.16 — Cadence-review trade summary dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Add a "Trades during this review period" section to the cadence completion form (`/reviews/{review_id}/complete`). The Phase 6 cadence completion surface today renders the period dates + a count of closed trades; operators have to context-switch to the journal / dashboard / trades list to see what actually happened. This dispatch surfaces the per-trade activity inline so the cadence-review workflow has the relevant context in front of it.

**Expected duration:** ~1.5-2 hr implementation + ~30-45 min dispatch overhead (worktree + TDD + adversarial review). Total ~2-2.75 hr.

**Skill posture:**
- Invoke `superpowers:subagent-driven-development` directly (NOT via the `copowers:executing-plans` wrapper).
- DO NOT invoke `superpowers:writing-plans` or `copowers:brainstorming` — design is locked in §0.3 below; this dispatch is small enough to skip the formal plan-writing cycle.
- Adversarial review via `copowers:adversarial-critic` after task families land. Iterate to NO_NEW_CRITICAL_MAJOR. Expected 2-3 Codex rounds (the new repo helper has the most adversarial-review value: date-range overlap correctness + dedup logic + multi-source union).

---

## §0 Read first

### §0.1 Backlog entry
- `docs/phase3e-todo.md` §3e.16 (Trade summary section in daily/weekly/monthly review pages — design questions answered; locked decisions in §0.3 below)

### §0.2 Code surface

**Existing surfaces (read-only context):**

- `swing/web/view_models/trades.py:667-737` — `CadenceCompleteVM` dataclass + `build_cadence_complete_vm` builder. Currently has `n_closed_trades_in_period: int` field; builder iterates `list_closed_trades` + `_list_all_exitshape_via_fills` to compute the count.
- `swing/web/templates/cadence_complete.html.j2` — current template (10 lines; renders period + count + form-include).
- `swing/web/routes/trades.py:1418` — `GET /reviews/{review_id}/complete` route handler.
- `swing/data/models.py:61` — `Trade` dataclass (~50 fields including `entry_date`, `entry_price`, `hypothesis_label`).
- `swing/data/models.py:361-385` — `ReviewLog` dataclass; `period_start: str` + `period_end: str` are ISO date strings.
- `swing/data/repos/trades.py:245-` — `list_open_trades` + `list_closed_trades` (existing query helpers).
- `swing/data/repos/fills.py` — fills repo + `_list_all_exitshape_via_fills` adapter (used by Phase 7 to surface exit dates from fills table).
- `swing/data/migrations/0014_phase7_state_machine_and_fills.sql:234-243` — `trade_events` schema: `(id, trade_id FK trades, ts TEXT NOT NULL, event_type CHECK (event_type IN ('entry','stop_adjust','note','exit','flag','pre_trade_edit')), payload_json, rationale, notes)`. `ts` column carries activity timestamp; format is ISO datetime (e.g., `2026-05-04T15:30:00`).
- `swing/data/migrations/0013_phase6_post_trade_review.sql:44+` — review_log schema for cross-reference.

**New surfaces this dispatch creates:**

- New repo helper: `swing/data/repos/trades.py` — `list_trades_with_activity_in_period(conn, *, period_start, period_end) -> list[TradeActivitySummary]` (or similar; final naming implementer's call).
- New VM dataclass: `swing/web/view_models/trades.py` — `TradeSummaryVM` (or similar) with the locked field set from §0.3 #3.
- VM extension: `CadenceCompleteVM.trades_during_period: tuple[TradeSummaryVM, ...]` field added.
- Builder extension: `build_cadence_complete_vm` populates the new field.
- Template extension: `cadence_complete.html.j2` renders the trade list section above the form-include.

### §0.3 LOCKED DESIGN DECISIONS (DO NOT re-litigate)

Locked by orchestrator + operator in-thread design lock 2026-05-10:

1. **Ordering:** flat chronological list ordered by activity-timestamp ASC. Not grouped by activity type. Each row prefixed with a state tag (`[OPENED]` / `[CLOSED]` / `[EVENT]`) — see §0.3 #2 for tag derivation. Operator-locked vs three-section-grouped + vs grouped-by-trade.

2. **State tag derivation:** booleans on each trade row, evaluated against the period:
   - `was_opened_in_period`: `trades.entry_date >= period_start AND trades.entry_date <= period_end`
   - `was_closed_in_period`: any fill with `exit_date >= period_start AND exit_date <= period_end` (use `_list_all_exitshape_via_fills` adapter — Phase 7 source-of-truth for exit dates)
   - `had_event_in_period`: any `trade_events` row with `ts >= period_start AND ts < (period_end + 1 day)` — `ts` is an ISO datetime, comparison must respect that period_end is the LAST day fully included; the simplest correct comparison is `ts >= period_start AND ts <= period_end || 'T23:59:59'` (string-comparison-safe for ISO 8601) OR convert to `date(ts)` via SQLite's `date()` function.
   
   **Rendering rule:** prefix with the FIRST applicable tag in priority `OPENED > CLOSED > EVENT`. A trade that was both opened AND closed in the same period (same-day round trip) renders as `[OPENED+CLOSED]` (concatenated). A trade that was already open before the period AND had events during the period renders as `[EVENT]`. A trade that was open before AND closed in period renders as `[CLOSED]`.

3. **Per-trade summary fields (locked):**
   - `ticker: str`
   - `entry_date: str` (ISO date)
   - `exit_date: str | None` (ISO date; None if still open)
   - `entry_price: float`
   - `exit_price: float | None` (None if still open)
   - `realized_R: float | None` (None if still open; for closed trades, the share-weighted realized R per Phase 6 `_share_weighted_r` semantics)
   - `hypothesis_label: str | None`
   - PLUS: `state_tag: str` (the rendered `[OPENED]`, `[CLOSED]`, etc. tag from §0.3 #2)
   - PLUS: `activity_ts: str` (ISO datetime; the timestamp used for chronological ordering — typically the LATEST relevant activity in the period)
   - PLUS: `trade_id: int` (for the `<a href="/trades/{id}">` deep-link)
   
   **NOT included** (operator-locked out of scope): sector / industry / chart_pattern / emotional_state aggregations / premortem text excerpts / R-multiple distribution stats. These would inflate the row beyond cadence-review-context grain. V2 expansion if operator requests.

4. **Activity-timestamp for ordering:** use the LATEST relevant activity inside the period:
   - If `was_closed_in_period`: use the latest `exit_date`+'T23:59:59' (operator's mental model: closes are the period's "headline" events)
   - Else if `had_event_in_period`: use the latest `trade_events.ts` inside the period
   - Else if `was_opened_in_period`: use `entry_date`+'T00:00:00'
   
   **Rationale:** for cadence reviews, operator scans bottom-up to "what closed most recently" first. Sort ASC means the most-recent-activity trade renders LAST (which appears bottom-of-list = visually first scanned in long-form review reading). If operator finds this counter-intuitive at gate, V1.5 flips to DESC + adjusts the rationale comment.

5. **Read-only completed-view scope:** V1 adds the section ONLY to `/reviews/{id}/complete` (the form view). Already-completed Review_Logs continue to 404 per the archived Phase 6 follow-up. V1.5 (separate dispatch) adds `/reviews/{id}/view` read-only render of completed Review_Logs.

6. **Repo helper signature:**
   ```python
   def list_trades_with_activity_in_period(
       conn: sqlite3.Connection,
       *,
       period_start: str,  # ISO date YYYY-MM-DD
       period_end: str,    # ISO date YYYY-MM-DD (inclusive)
   ) -> list[TradeActivitySummary]:
       """Return distinct trades with at least one activity (entry, exit,
       or trade_event) inside [period_start, period_end] inclusive,
       ordered by activity_ts ASC."""
   ```
   Final naming + return-type shape is implementer's call; the surface above is the locked contract. Define `TradeActivitySummary` as a dataclass in either `swing/data/repos/trades.py` (alongside the helper) OR `swing/web/view_models/trades.py` (alongside `TradeSummaryVM`); whichever keeps imports cleaner.

7. **Empty-period rendering:** when the helper returns an empty list, the template renders `<p>No trade activity in this period.</p>` (or equivalent muted-text indicator). Do NOT omit the section heading — operator should see the heading + empty-state message together so the absence is interpretable.

8. **Section heading:** `<h2>Trade activity during this period</h2>` (or equivalent semantic h2 inside the form's content area). Position: above the form-include in `cadence_complete.html.j2`.

9. **Per-row rendering pattern:**
   ```jinja
   <li>
     <span class="trade-summary-tag">{{ row.state_tag }}</span>
     <a href="/trades/{{ row.trade_id }}">{{ row.ticker }}</a>
     {{ row.entry_date }}{% if row.exit_date %} → {{ row.exit_date }}{% endif %}
     ${{ '%.2f' | format(row.entry_price) }}{% if row.exit_price %} → ${{ '%.2f' | format(row.exit_price) }}{% endif %}
     {% if row.realized_R is not none %}{{ '%+.2f' | format(row.realized_R) }}R{% endif %}
     {% if row.hypothesis_label %}<span class="muted">{{ row.hypothesis_label }}</span>{% endif %}
   </li>
   ```
   Container: `<ul class="cadence-trade-summary-list">` (or similar). Keep markup minimal; CSS scoping is a follow-up. Plan author may refine the exact attribute structure.

10. **No schema changes.** No migration. Schema stays at v16. New helper queries existing tables only.

11. **No new tests for already-completed Review_Log 404 path** (existing Phase 6 behavior; out of scope here).

---

## §1 Strategic context

This is a Phase 6 follow-up — the cadence completion form was the V1 ship surface for review_log entry, but operator workflow surfaced that "complete this review" without "see what happened in this period" forces context-switch friction. 3e.16 closes that gap minimally.

**Schema state (binding):** Production DB at schema_version 16 post-3e.15 ship at HEAD `6b65bed`. No migration in scope.

**What's NOT in scope:**
- Read-only completed-view at `/reviews/{id}/view` (V1.5 separate dispatch).
- Aggregation rollups (R-multiple distribution, sector counts, hypothesis-label rollup) — V2 if operator surfaces the need.
- Daily-management `record_type='event_log'` rows that don't have a paired `trade_events` row (Phase 8 service may emit paired or not depending on whether the event changed state). For V1, the helper queries `trade_events` only; daily-management event_logs without paired trade_events rows will not surface as `[EVENT]`. Banking as a V2 follow-up if operator confirms missed events.
- CSS styling refinement beyond minimal markup.
- Mobile-friendly layout.

---

## §2 Worktree + binding conventions

### §2.1 Worktree
- **Branch:** `3e16-cadence-review-trade-summary`
- **Worktree directory:** `.worktrees/3e16-cadence-review-trade-summary/` at repo root (canonical project-precedent path; cleanup-script-aligned per binding convention 2026-05-09).
- **BASELINE_SHA:** `6b65bed` (HEAD of `main` post-3e.15 housekeeping).

### §2.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active` (PowerShell). Activates global PreToolUse hook.
- After all task families land + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`.

### §2.3 Commits
- Conventional prefix per `docs/orchestrator-context.md` Conventions:
  - `feat(data): Task A.X — <description>` for repo helper additions
  - `feat(web): Task B.X — <description>` for VM/route extensions
  - `feat(templates): Task C.X — <description>` for template additions
  - `test(...)` for test-only commits
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes (the `(internal)` tag flags Codex-source vs operator-gate-source)
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`** (CLAUDE.md hook-failure rule).
- **TDD:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change OR cluster cycles when tests are essentially discriminators of one feature.

### §2.4 Branch isolation + ownership
- Commits land ONLY on `3e16-cadence-review-trade-summary` branch. Do NOT push to `origin` from inside the worktree.
- **Implementer owns:** task-family TDD commits (§3) → marker-file removal (§4.1) → adversarial-critic invocation + Codex-fix commits → return report drafting (§6).
- **Operator owns:** witnessed verification gate (§5).
- **Orchestrator owns:** integration merge to main (post-gate-pass) + post-merge housekeeping.

### §2.5 Verify command
PowerShell from inside worktree:
```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```
Pytest works without override (cwd-based discovery).

---

## §3 Per-task implementation breakdown

### §3.1 Task family A — repo helper

**Acceptance criteria:**

- (A.AC.1) New helper `list_trades_with_activity_in_period(conn, *, period_start, period_end)` per §0.3 #6 contract.
- (A.AC.2) Returns trades that satisfy ANY of three predicates (per §0.3 #2): entered in period / exited in period / had a trade_events row in period.
- (A.AC.3) Each returned row carries the three boolean flags + computed `state_tag` per §0.3 #2 priority + `activity_ts` per §0.3 #4 derivation rule + the locked field set from §0.3 #3.
- (A.AC.4) Result is ordered by `activity_ts` ASC.
- (A.AC.5) Distinct on `trade_id` — no duplicates.
- (A.AC.6) `realized_R` for closed trades uses the share-weighted formula (mirror or reuse `swing/trades/review.py:_trade_r` per Phase 6 §A.1 pattern; if cross-module-private import is uncomfortable, re-paste per Phase 6 §A.1 lesson — both helpers private-prefixed, byte-identical).

**Suggested test names (in `tests/data/test_repos_trades.py` or new `tests/data/test_trades_with_activity.py`):**

- `test_includes_trade_entered_in_period`
- `test_includes_trade_exited_in_period`
- `test_includes_trade_with_event_in_period`
- `test_excludes_trade_entirely_outside_period` (entered + exited before period; entered + still open after period — both excluded)
- `test_dedups_trade_with_multiple_activities` (one trade with entry IN period AND multiple trade_events IN period appears once)
- `test_orders_by_activity_ts_asc` (multi-trade fixture; assert order)
- `test_state_tag_priority` (trade with both entry AND exit in period → `[OPENED+CLOSED]`; trade with prior entry + exit in period → `[CLOSED]`; trade with prior entry + only events in period → `[EVENT]`)
- `test_realized_r_for_closed_trade` (assert share-weighted R correctly computed)

**Suggested commit shape:** A.1 RED tests + GREEN helper → commit (`feat(data): Task A.1 — list_trades_with_activity_in_period helper`). Implementer may split if test count grows beyond ~6.

**Watch items:**
- Period bounds are INCLUSIVE on both ends. `period_end` is the LAST day fully included (e.g., monthly review for May 2026 has `period_end = '2026-05-31'`). When comparing against `trade_events.ts` (ISO datetime), respect this — use `date(ts) <= period_end` via SQLite's date() function OR string-compare against `period_end || 'T23:59:59'`.
- `trade_events` table has an index `ix_trade_events_trade ON trade_events(trade_id, ts)` — query plan should leverage it.
- The Phase 7 `trade_events` event_type set is `('entry','stop_adjust','note','exit','flag','pre_trade_edit')`. ALL types count as "activity" for §0.3 #2's `had_event_in_period` flag — do NOT filter to specific event_types. Operator wants to see "this trade was touched during the period" regardless of touch type.
- `_list_all_exitshape_via_fills` adapter is the Phase 7 source-of-truth for exit dates (fills table → derived shape). Do NOT query an `exits` table — it was dropped in Phase 7.

### §3.2 Task family B — VM extension + builder

**Acceptance criteria:**

- (B.AC.1) New `TradeSummaryVM` dataclass in `swing/web/view_models/trades.py` with the §0.3 #3 field set (frozen=True per project precedent).
- (B.AC.2) `CadenceCompleteVM.trades_during_period: tuple[TradeSummaryVM, ...]` field added with `field(default_factory=tuple)` so existing constructors don't break.
- (B.AC.3) `build_cadence_complete_vm` calls the new helper from Task A + populates `trades_during_period`.
- (B.AC.4) The existing `n_closed_trades_in_period` count remains correct (was-closed branch of state-tag math is the same predicate; can either keep the existing computation OR derive from the new helper output — implementer's choice; pin both via existing `n_closed_trades_in_period` test + new tests).

**Suggested test names (in `tests/web/test_view_models/` or `tests/web/test_routes/test_trades_route.py`):**

- `test_build_cadence_complete_vm_populates_trades_during_period`
- `test_build_cadence_complete_vm_empty_when_no_activity`
- `test_build_cadence_complete_vm_n_closed_trades_count_consistent` (the existing count + new list agree on the closed-trade subset)

**Suggested commit shape:** B.1 RED VM-extension tests + GREEN extension → commit (`feat(web): Task B.1 — TradeSummaryVM + CadenceCompleteVM extension for trade activity list`).

### §3.3 Task family C — template extension

**Acceptance criteria:**

- (C.AC.1) New `<h2>Trade activity during this period</h2>` section above the form-include in `cadence_complete.html.j2`.
- (C.AC.2) When `vm.trades_during_period` is non-empty: render `<ul>` with one `<li>` per trade per the §0.3 #9 markup pattern.
- (C.AC.3) When `vm.trades_during_period` is empty: render the muted "No trade activity in this period." message.
- (C.AC.4) Each row's ticker is wrapped in `<a href="/trades/{trade_id}">{ticker}</a>` for deep-link navigation.

**Suggested test names (in `tests/web/test_routes/test_trades_route.py` or similar):**

- `test_cadence_complete_renders_trade_activity_section_when_populated` (assert response body contains the heading + locked content snippets)
- `test_cadence_complete_renders_empty_state_when_no_activity` (assert empty-state message renders)
- `test_cadence_complete_state_tag_appears_in_response` (assert `[OPENED]` or `[CLOSED]` substring present on a fixture with known state)

**Suggested commit shape:** C.1 RED template-render tests + GREEN template addition → commit (`feat(templates): Task C.1 — render trade activity section in cadence completion form`).

---

## §4 Adversarial review (Codex)

### §4.1 Setup (IMPLEMENTER runs this — convention per orchestrator-context "Executing-plans dispatch convention" 2026-05-02)

After ALL task-family commits land + tests are GREEN at branch HEAD, the implementer (this top-level Claude Code instance — NOT a subagent) performs:

1. **Remove the marker file:**
   ```powershell
   Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
   ```
2. Invoke `copowers:adversarial-critic` directly with:
   - `PHASE`: `3e16-cadence-review-trade-summary`
   - `SPEC_PATH`: `docs/3e16-cadence-review-trade-summary-brief.md`
   - `PLAN_PATH`: `docs/3e16-cadence-review-trade-summary-brief.md`
   - `BASELINE_SHA`: `6b65bed`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **2-3 rounds**.

### §4.2 Pre-empt list

Adversarial-review value-add concentrates on Task A (the new repo helper). Pre-empt likely findings by verifying:

- **Date-range overlap correctness.** Inclusive on both ends. Same-day round trip (entry_date == exit_date == period boundary day) MUST be included on both branches.
- **`trade_events.ts` comparison handles ISO datetime vs ISO date.** `period_end` is YYYY-MM-DD; `ts` is YYYY-MM-DDTHH:MM:SS. Bare string comparison `ts <= period_end` would WRONGLY exclude any event on `period_end` (since `'2026-05-31T15:30:00' > '2026-05-31'`). Use `date(ts) <= ?` SQLite function OR concat `period_end || 'T23:59:59'`.
- **Dedup correctness.** A trade with entry IN period + exit IN period + 5 trade_events rows IN period must appear EXACTLY ONCE.
- **State-tag priority semantics.** A trade with entry OR exit in period gets `[OPENED]` / `[CLOSED]` / `[OPENED+CLOSED]`. A trade with only trade_events in period gets `[EVENT]`. If a trade is opened in period AND has events in period, it's `[OPENED]` (not `[OPENED+EVENT]`) — the entry IS the event.
- **`realized_R` computation for closed trades.** Mirror Phase 6 `_share_weighted_r` formula (`swing/trades/review.py:_trade_r`) — share-weighted across multiple exit fills, NOT averaged.
- **Activity-timestamp for ordering across the three branches.** §0.3 #4's "latest relevant activity in period" is a 3-way priority — exits > events > entry. A trade with entry in period AND multiple events in period should sort by the LATEST event's ts, not the entry_date.
- **Empty trade_events query.** Trade with entry + exit in period but ZERO trade_events rows in period (legacy data, or pure entry-then-exit-without-events) MUST still appear (the entry/exit date branches catch it).

---

## §5 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR:

- **Surface 1 — Cadence completion form renders trade list (happy path).** Operator navigates to a `/reviews/{id}/complete` URL for a pending Review_Log that has trade activity in its period. Verify the new section renders above the form with one row per active trade. Confirm state tags are correct + ordering is chronological. Note any visual artifacts.
- **Surface 2 — Empty-state message.** If a pending Review_Log exists for a period with NO trade activity, verify the empty-state message renders. (May require manually picking such a Review_Log; if no such Review_Log exists in operator's actual data, induce by creating a future-dated daily Review_Log via SQL OR skip with test-coverage note.)
- **Surface 3 — Trade-detail link works.** Click a ticker link in a row; verify navigation to `/trades/{id}` resolves correctly.
- **Surface 4 — Existing form behavior intact.** Submit the cadence completion form (with notes / lesson populated); verify the existing review-completion flow still works and the trade list section doesn't interfere.
- **Surface 5 — pytest + ruff.** Run `python -m pytest -m "not slow" -q` from the worktree; verify all GREEN. Run `ruff check swing/ --statistics`; verify no new violations introduced.

**Expected test count delta:** +10-14 (Task A: ~6-8, Task B: ~3, Task C: ~3).
**Expected ruff baseline:** 18 (E501 only) — no change.

---

## §6 Return report shape

After operator-gate PASS, draft a return report with:

1. Final HEAD on branch — `git rev-parse 3e16-cadence-review-trade-summary`
2. Commit count breakdown — task-impl / Codex-fix / operator-gate-fix
3. Codex round chain — rounds + (Critical / Major / Minor) per round + convergence shape
4. Test count delta — pre-bundle baseline → post-bundle final
5. Ruff baseline delta (expected: no change)
6. Operator-gate surface results — per-surface PASS/FAIL/SKIPPED with notes
7. Per-task-family deviations from the brief — anything chosen differently and why
8. Codex Major findings ACCEPTED with rationale — list each
9. Watch items surfaced during dispatch but NOT acted on
10. Worktree teardown status — clean vs ACL-locked husk

---

## §7 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading 3e16-cadence-review-trade-summary dispatch.

WORKING DIRECTORY: c:\Users\rwsmy\swing-trading\.worktrees\3e16-cadence-review-trade-summary
BRANCH: 3e16-cadence-review-trade-summary
BASELINE_SHA: 6b65bed

Step 1 — Read the dispatch brief end-to-end:
  docs/3e16-cadence-review-trade-summary-brief.md

It locks 11 design decisions (§0.3) that you do NOT re-litigate. Three task families:
  - Task A: list_trades_with_activity_in_period repo helper + TradeActivitySummary dataclass
  - Task B: TradeSummaryVM + CadenceCompleteVM extension
  - Task C: cadence_complete.html.j2 template extension

Step 2 — Read CLAUDE.md + docs/orchestrator-context.md (binding conventions).

Step 3 — Verify worktree state:
  git rev-parse HEAD                  # expect 6b65bed
  git status                          # expect clean
  python -m pytest -m "not slow" -q   # expect baseline GREEN (2142 passed)

Step 4 — Execute the brief via superpowers:subagent-driven-development. TDD discipline per task family. Keep commits small + per the prefix conventions in §2.3.

Step 5 — After ALL task families land + GREEN, run the adversarial review YOURSELF (per §4.1):
  - Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
  - Invoke copowers:adversarial-critic with PHASE=3e16-cadence-review-trade-summary,
    SPEC_PATH=docs/3e16-cadence-review-trade-summary-brief.md,
    PLAN_PATH=docs/3e16-cadence-review-trade-summary-brief.md,
    BASELINE_SHA=6b65bed
  - Iterate rounds + land Codex-fix commits until NO_NEW_CRITICAL_MAJOR.

Step 6 — Draft return report per §6 + signal orchestrator. Orchestrator triages; operator drives the §5 witnessed verification gate; orchestrator handles integration merge after gate PASS.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers (the hook will block your invocation otherwise)
```

---

## §8 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-10 (post-3e.15-ship).
- **Brief commit:** TBD (committed as final orchestrator action before dispatch).
- **Brief HEAD context:** `6b65bed` on main.
- **Worktree path (binding):** `.worktrees/3e16-cadence-review-trade-summary/`.
- **Baseline test count:** 2142 fast (1 skipped).
- **Baseline ruff count:** 18 (E501 only).
- **Expected post-dispatch test count:** ~2152-2156 (+10-14).
- **Expected post-dispatch ruff count:** 18 (no change).
