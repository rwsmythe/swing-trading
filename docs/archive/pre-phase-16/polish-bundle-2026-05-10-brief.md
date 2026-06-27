# Polish bundle 2026-05-10 — combined dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Ship two operator-surfaced UX improvements + one mechanical lint-cleanup batch as a single TDD-disciplined dispatch on a worktree branch:

1. **3e.4** — Add a current-price line at the top of the hyp-recs expanded row (mirrors open-positions price + stale-flag pattern; gives operator price-vs-pivot context when evaluating a hyp-rec entry).
2. **3e.7** — Add static example-aside panels beside the 5 textareas on the trade entry form (1 aside per textarea: 1 thesis + 4 premortem; generic prompt-style content, NOT trade-specific).
3. **Ruff N818** — Mechanical rename of 8 exception classes to add the `Error` suffix (single commit; ~79 references across `swing/` + `tests/`).

**Expected duration:** ~1.5-2 hr implementation + ~30-45 min dispatch overhead (worktree + TDD + adversarial review). Total ~2-2.75 hr.

**Skill posture:**
- Invoke `superpowers:subagent-driven-development` directly (NOT via the `copowers:executing-plans` wrapper, which bundles writing-plans + adversarial-critic without marker-file management between phases).
- DO NOT invoke `superpowers:writing-plans` or `copowers:brainstorming` — design is locked in §0.3 below; this dispatch is small enough to skip the formal plan-writing cycle (mirrors polish-bundle-2026-05-09 + tos-import-diagnostic precedent).
- Adversarial review via `copowers:adversarial-critic` after all 3 task families land. Iterate to NO_NEW_CRITICAL_MAJOR. Expected 2-3 Codex rounds (small surface; converges fast).

---

## §0 Read first

### §0.1 Backlog entries (canonical context for each task)

- `docs/phase3e-todo.md` §3e.4 (current price in hyp-rec expanded row)
- `docs/phase3e-todo.md` §3e.7 (example entries beside premortem + pre-trade thesis textareas)
- `docs/phase3e-todo.md` 2026-05-10 entry "Ruff residual cleanup" (N818 + E501 breakdown; THIS dispatch handles N818 only — E501 deferred)

### §0.2 Code surface

**For 3e.4 (current price):**

- `swing/web/view_models/dashboard.py:540-559` — `HypRecsExpandedVM` dataclass. Add `current_price: PriceSnapshot | None = None` (default None for safety; compatible with all existing call sites that don't pass it).
- `swing/web/view_models/dashboard.py:561-640` — `build_hyp_recs_expanded` builder. Extend signature to optionally accept PriceCache + executor; when provided, fetch ticker price + populate VM field.
- `swing/web/routes/recommendations.py:160-205` — `hyp_recs_expand` route. Currently does NOT pass `price_cache` / `price_fetch_executor` into the builder. Extend to thread them in. Pattern reference: same file, `:133-134` (the `/hyp-recs/refresh` route).
- `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` — template. Insert `<p class="current-price">Current: ${X.XX}</p>` directly under the `<h3>{ticker}</h3>` (lines 17-19 area), ABOVE the existing `<h4>Order parameters</h4>` section. Render-shape mirrors `partials/open_positions_row.html.j2:32-35`:
  ```jinja
  {% if expanded.current_price %}
    Current: ${{ '%.2f' | format(expanded.current_price.price) }}
    {% if expanded.current_price.is_stale %}<span class="stale">(stale)</span>{% endif %}
  {% else %}
    Current: —
  {% endif %}
  ```
- `swing/web/price_cache.py` — `PriceCache` + `PriceSnapshot` definitions. `PriceSnapshot` has `.price: float` + `.is_stale: bool` fields. Read-only reference; do NOT modify.

**For 3e.7 (example asides):**

- `swing/web/templates/partials/trade_entry_form.html.j2` — entry form template. Five textareas to wrap with side-panel asides:
  - Line 99-103 area: `<textarea name="thesis">` (1 textarea inside Pre-trade thesis fieldset)
  - Line 113-122 area: 4 textareas inside Premortem fieldset (`premortem_technical`, `premortem_market_sector`, `premortem_execution`, `premortem_additional`)
- `swing/web/static/style.css` — minimal CSS for `.entry-textarea-row` flex container + `.entry-example-aside` sidebar layout. Operator preference: examples visible always (NOT toggle-shown).
- Aside content is hard-coded STATIC text (locked in §0.3 #6 below; do NOT improvise).

**For Ruff N818 (8 mechanical renames):**

8 exception class definitions to rename, all in `swing/`:

| File | Old name | New name |
|---|---|---|
| `swing/data/db.py:49` | `SchemaVersionMismatch` | `SchemaVersionMismatchError` |
| `swing/data/repos/pipeline.py:15` | `LeaseRevoked` | `LeaseRevokedError` |
| `swing/data/repos/watchlist.py:67` | `WatchlistEntryNotFound` | `WatchlistEntryNotFoundError` |
| `swing/pipeline/lease.py:24` | `ConcurrentRunBlocked` | `ConcurrentRunBlockedError` |
| `swing/rendering/charts.py:15` | `ChartingUnavailable` | `ChartingUnavailableError` |
| `swing/trades/entry.py:85` | `SoftWarnException` | `SoftWarnError` |
| `swing/trades/entry.py:89` | `HardCapException` | `HardCapError` |
| `swing/trades/entry.py:93` | `DuplicateOpenPositionException` | `DuplicateOpenPositionError` |

Per-class reference counts (per phase3e-todo §"Ruff residual cleanup" 2026-05-10 entry): combined ~79 references across `swing/` + `tests/`. Mechanical replace; names are distinctive enough that no substring false-positives expected.

### §0.3 LOCKED DESIGN DECISIONS (DO NOT re-litigate)

Locked by orchestrator + operator in-thread design lock 2026-05-10. Implementer executes them; does NOT brainstorm alternatives:

1. **3e.4 placement: top of expanded panel.** New `<p class="current-price">Current: $X.XX</p>` directly under the `<h3>{ticker}</h3>` heading, ABOVE the existing `<h4>Order parameters</h4>` section. Operator-locked layout choice (vs. inside Order parameters list, vs. own h4 mini-section). Rationale: price is the primary context for evaluating buy_stop / buy_limit / sell_stop, so it earns top-of-panel real estate.

2. **3e.4 stale-flag pattern: mirror open-positions exactly.** Use the existing `partials/open_positions_row.html.j2:32-35` rendering pattern verbatim (`{% if price_snapshot %} ... ${{ price }} ... {% if is_stale %}<span class="stale">(stale)</span>{% endif %} {% else %}—{% endif %}`). Do NOT invent a new stale-rendering convention.

3. **3e.4 VM field default: None.** `HypRecsExpandedVM.current_price: PriceSnapshot | None = None`. Default is None for backward-compat with any existing constructor calls or tests that build the VM without a cache. The route is responsible for fetching + populating; if route doesn't (or fetch fails), VM defaults gracefully → template renders `—`.

4. **3e.4 cache wiring: optional kwargs in builder.** `build_hyp_recs_expanded(conn, cfg, *, ticker, current_balance, cache=None, executor=None)`. When `cache is not None`, fetch the ticker price via the existing PriceCache+executor pattern (mirror `swing/web/view_models/dashboard.py` open-positions price-fetch path; do NOT invent a new fetcher). When `cache is None`, leave `current_price=None`. Route MUST always pass them in production; tests MAY skip them when exercising other code paths.

5. **3e.7 aside scope: 5 asides total, one per textarea.** One `<aside>` per textarea: thesis + premortem_technical + premortem_market_sector + premortem_execution + premortem_additional. Operator-locked granularity choice (vs. per-fieldset 2 asides, vs. per-fieldset with 4 sub-asides for premortem). Rationale: per-textarea matches the granularity of the writing prompt — each textarea has its own scope, each aside guides that scope.

6. **3e.7 aside content: locked verbatim.** Do NOT improvise. Aside content is generic prompt-style (NOT trade-specific; NOT fake-realistic with fake tickers/prices). 2-3 hint bullets per aside. Rendered as a `<ul>` inside the aside. **Locked content per textarea:**

   **Pre-trade thesis aside:**
   - `Setup type + base structure (e.g., VCP with N contractions; cup-with-handle; flat base of length L weeks; depth %).`
   - `Setup grade + binding criteria passed (A+ vs A vs sub-A; which trend-template + VCP criteria are met or relaxed and why the relaxation is acceptable).`
   - `Catalyst + RS context (sector strength + group leaders confirming; earnings driver; macro thesis).`

   **Premortem: technical aside:**
   - `What invalidates the setup (close below pivot; close below 50MA; base breakdown on volume).`
   - `Where the framework would call you wrong (extended above 20MA; tightness floor not met; volume profile thin).`
   - `Failure modes for the specific pattern (VCP final contraction blow-out; cup-with-handle handle too deep; flat-base inside-day reversal).`

   **Premortem: market/sector aside:**
   - `Market weather state + your sizing response (bullish / caution / bearish; full / half / skip).`
   - `Sector strength vs market (RS rank; leadership concentration; mean-reversion risk).`
   - `Macro/news risk specific to the trade window (scheduled FOMC / CPI / earnings; sector-specific catalysts pending).`

   **Premortem: execution aside:**
   - `Personal entry biases (chase tendency; premature add; sizing inconsistency).`
   - `Stop discipline (no tightening before +1.5R; trail-MA selection per trade-maturity stage).`
   - `Position management (drawdown to half-stop response; breakout-and-fade response).`

   **Premortem: additional aside:**
   - `Earnings proximity + hold-through policy (distance in sessions; sizing / exit policy).`
   - `Personal availability (travel; workload conflicts; ability to manage in-flight).`
   - `Catch-all for pattern-specific or ticker-specific risks not covered above.`

7. **3e.7 layout: side-by-side flex/grid.** Add `<div class="entry-textarea-row">` wrapper around each `<div><label>...</label><textarea>...</textarea></div>` + adjacent `<aside class="entry-example-aside">`. CSS: `.entry-textarea-row { display: flex; gap: 1rem; align-items: flex-start; }` + `.entry-example-aside { flex: 0 0 auto; max-width: 320px; font-size: 0.875rem; color: var(--muted, #666); }` (or similar; minimal additions). Plan author may refine specific values; binding constraint is **examples visible always to the right of the textarea, no toggle**.

8. **3e.7 aside markup pattern (canonical):**
   ```jinja
   <div class="entry-textarea-row">
     <div class="entry-textarea">
       <label>Thesis text:</label>
       <textarea name="thesis"{{ err_class('thesis') }}>{{ vm.draft_thesis }}</textarea>
     </div>
     <aside class="entry-example-aside" aria-label="Examples for pre-trade thesis">
       <strong>Examples:</strong>
       <ul>
         <li>Setup type + base structure ...</li>
         ...
       </ul>
     </aside>
   </div>
   ```

9. **No schema changes.** No migration. No new repo functions. No new VM fields beyond `HypRecsExpandedVM.current_price` (3e.4 only).

10. **Ruff N818 commit shape: SINGLE mechanical commit.** All 8 renames + their ~79 references in one commit `chore(ruff): N818 — rename exceptions for Error suffix`. Operator-locked (vs. one-commit-per-class, vs. grouped-by-domain). Rationale: mechanical batch; cleanest history; the renames are too small individually to warrant separate commits.

11. **Ruff N818 implementation procedure:**
    1. For each of the 8 renames: `git grep -l <OldName> | xargs sed -i 's/<OldName>/<NewName>/g'` (Bash) or PowerShell equivalent.
    2. After all 8 renames, run `python -m pytest -m "not slow" -q` — must stay GREEN.
    3. Run `ruff check swing/ | grep N818` — must return zero matches.
    4. Single commit with the rename batch.
    5. **Watch-item:** verify no test asserts on the OLD class name as a string literal (e.g., `pytest.raises(ValueError, match="WatchlistEntryNotFound")`). Sed handles uniformly when the match string contains the class name; surface any cases where the assertion uses a regex anchor or escape that requires manual fixup.

12. **Ruff baseline post-bundle:** expected to drop from 26 to 18 (N818=0 + E501=18 remaining). Verify at end-of-dispatch via `ruff check swing/ | wc -l` — report the actual count in the return report. Do NOT attempt E501 cleanup in this dispatch (out of scope; phase3e-todo entry banks them for separate bundling).

---

## §1 Strategic context

This is the second post-Phase-8 polish bundle. Three operator-surfaced items: two UX-polish items (3e.4 + 3e.7) lifted from operator workflow inspection 2026-05-08; one tooling-cleanup item (N818 batch) bundled out-of-band per the phase3e-todo "Bundling guidance" suggestion ("good candidates to fold into ANY future small-scope dispatch as out-of-band cleanup").

All three items are small + narrowly scoped + testable via existing patterns. Bundling them avoids dispatch overhead × 3.

**Schema state (binding):** Production DB at schema_version 16 post-polish-bundle-2026-05-09 ship at HEAD `794c51c`. No migration in scope.

**What's NOT in scope:**

- E501 line-too-long cleanup (banked separately per phase3e-todo "Ruff residual cleanup" entry).
- 3e.16 trade-summary section in cadence review pages (separate dispatch; queued).
- 3e.15 badge-utility investigation (separate dispatch; queued).
- Any 3e.4 design beyond top-of-panel placement (operator-locked).
- Any 3e.7 aside content beyond the locked text in §0.3 #6 (operator-locked).
- Mobile-friendly layout for the entry form aside (out of V1; desktop-only operator surface today).
- Theming integration (3e.10 dark theme is a separate dispatch).

---

## §2 Worktree + binding conventions

### §2.1 Worktree

- **Branch:** `polish-bundle-2026-05-10`
- **Worktree directory:** `.worktrees/polish-bundle-2026-05-10/` at repo root (canonical project-precedent path; cleanup-script-aligned per binding convention 2026-05-09; do NOT use `superpowers:using-git-worktrees`'s `.claude/worktrees/` default).
- **BASELINE_SHA:** `794c51c` (HEAD of `main` at dispatch time; the housekeeping commit refreshing the orchestrator-context Ruff baseline).

Use `superpowers:using-git-worktrees` to create. Specify the `.worktrees/<branch>/` path explicitly when invoking the skill.

### §2.2 Marker-file workflow (Codex blocking during subagents)

- After worktree creation: `touch .copowers-subagent-active` at repo root (NOT inside worktree). Activates the global PreToolUse hook at `~/.claude/hooks/block-copowers-during-subagent.sh` (registered in `~/.claude/settings.json`) — physically prevents subagents from invoking `copowers:adversarial-critic` / `copowers:review` / `mcp__plugin_copowers_codex__codex*`.
- After all task families land + before invoking adversarial-critic: `rm .copowers-subagent-active` at repo root.

### §2.3 Commits

- Conventional prefix per `docs/orchestrator-context.md` Conventions section. For this dispatch:
  - `feat(web): Task A.X — <description>` for VM/route/template additions
  - `feat(templates): Task B.X — <description>` for template-only changes (the asides)
  - `style(web): Task B.X — <description>` for the CSS-only commit
  - `test(web): Task A.X / Task B.X — <description>` for test-only commits
  - `chore(ruff): N818 — rename exceptions for Error suffix` for Task C (single commit)
  - `fix(area): Codex RN Major #X — <description>` for Codex-driven fixes
- **NO Claude co-author footer** (project convention).
- **NO `--no-verify`** (no skipping pre-commit hooks; if any hook fails, fix root cause).
- **NO `--amend`** (always create new commits; CLAUDE.md hook-failure rule).
- **TDD discipline per task family:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change OR cluster cycles when tests are essentially discriminators of one feature (implementer's judgment; document in return report).

### §2.4 Branch isolation + ownership of the dispatch lifecycle

- Commits land ONLY on `polish-bundle-2026-05-10` branch. Do NOT push to `origin` from inside the worktree.
- **Implementer owns:** task-family TDD commits (§3) → marker-file removal (§4.1) → adversarial-critic invocation + round iteration + Codex-fix commits (§4) → return report drafting (§6).
- **Operator owns:** witnessed verification gate (§5) — implementer signals readiness via return report; operator drives the browser walkthrough.
- **Orchestrator owns:** integration merge to main (post-gate-pass) + post-merge housekeeping (orchestrator-context updates, phase3e-todo entry archival, etc.). Implementer does NOT merge.

### §2.5 Verify command (worktree + editable install)

When running CLI / `swing web` from inside the worktree, the editable install resolves to the main project path, NOT the worktree. Use:

```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```

(PowerShell; from inside `.worktrees/polish-bundle-2026-05-10/`)

For pytest: works without override (cwd-based discovery).

---

## §3 Per-task implementation breakdown

### §3.1 Task family A — 3e.4 current price in hyp-rec expanded row

**Acceptance criteria:**

- (A.AC.1) `HypRecsExpandedVM` has new `current_price: PriceSnapshot | None = None` field with default None.
- (A.AC.2) `build_hyp_recs_expanded` accepts optional `cache=None, executor=None` kwargs; when `cache is not None`, fetches the ticker price via PriceCache+executor pattern (mirror existing dashboard open-positions path) and populates `VM.current_price`.
- (A.AC.3) `hyp_recs_expand` route always passes `request.app.state.price_cache` + `request.app.state.price_fetch_executor` into the builder.
- (A.AC.4) Template renders `Current: $X.XX` directly under the `<h3>` ticker heading, above `<h4>Order parameters</h4>`.
- (A.AC.5) When `VM.current_price.is_stale`, template renders `<span class="stale">(stale)</span>` after the price.
- (A.AC.6) When `VM.current_price is None` (cache absent or fetch returned None), template renders `Current: —`.

**Suggested test names + assertions:**

- `test_hyp_recs_expanded_vm_has_current_price_field` — instantiate VM with `current_price=PriceSnapshot(...)`; assert field accessible.
- `test_build_hyp_recs_expanded_populates_current_price_when_cache_provided` — pass a stub PriceCache that returns a known snapshot; assert `vm.current_price.price == expected_value`.
- `test_build_hyp_recs_expanded_leaves_current_price_none_without_cache` — call without cache kwarg; assert `vm.current_price is None`.
- `test_hyp_recs_expand_route_renders_current_price_in_response_body` — `with TestClient(app) as client:` (lifespan-required for `app.state.price_fetch_executor`); GET `/hyp-recs/{ticker}/expand`; assert response body contains `Current: $` substring.
- `test_hyp_recs_expand_route_renders_stale_indicator` — stub PriceCache returning a stale snapshot; assert response body contains `(stale)`.
- `test_hyp_recs_expand_route_renders_dash_when_price_unavailable` — stub PriceCache returning None; assert response body contains `Current: —`.

**Suggested commit shape (TDD cycles):**

- A.1: 3 RED VM/builder tests + GREEN VM extension + builder kwargs + cache fetch path → commit (`feat(web): Task A.1 — extend HypRecsExpandedVM + builder for current price`)
- A.2: 3 RED route tests + GREEN route wiring + template change → commit (`feat(web): Task A.2 — wire price cache into hyp-recs expand route + template render`)

Implementer may split further OR cluster differently — judgment call; document in return report. Total 6 new tests expected for Task A.

**Watch items:**

- `PriceCache.get_or_fetch(ticker, executor=...)` is the typical entry point (verify exact API in `swing/web/price_cache.py`); do NOT invent a new fetcher.
- TestClient tests touching `app.state.price_fetch_executor` MUST use `with TestClient(app) as client:` — the lifespan handler creates the executor (CLAUDE.md gotcha "TestClient lifespan").
- Template variable name MUST be `expanded.current_price` (not `expanded.price` or `expanded.snapshot`) — keeps template grep'able alongside open-positions `row.price_snapshot`.

### §3.2 Task family B — 3e.7 example asides on entry form

**Acceptance criteria:**

- (B.AC.1) Five `<aside class="entry-example-aside">` elements rendered, one per each of the 5 textareas (thesis + 4 premortem subs).
- (B.AC.2) Each aside contains the verbatim hint bullets locked in §0.3 #6 (rendered as `<ul>` inside the aside).
- (B.AC.3) Each textarea is wrapped in a flex container (`<div class="entry-textarea-row">`) alongside its aside.
- (B.AC.4) CSS in `swing/web/static/style.css` provides side-by-side layout (`display: flex` or grid; aside to right of textarea; aside max-width ~320px; muted color).
- (B.AC.5) Asides are visible by default — NO `<details>` / `<summary>` / toggle / hidden state.
- (B.AC.6) Existing form fields (name attributes, validation classes, hidden inputs) are unchanged — wrapper div is the only structural addition.

**Suggested test names + assertions:**

- `test_trade_entry_form_renders_thesis_aside` — render entry form via TestClient; assert response contains `Setup type + base structure` (anchor on a unique substring from the locked thesis aside content).
- `test_trade_entry_form_renders_premortem_technical_aside` — assert response contains `What invalidates the setup`.
- `test_trade_entry_form_renders_premortem_market_sector_aside` — assert response contains `Market weather state + your sizing response`.
- `test_trade_entry_form_renders_premortem_execution_aside` — assert response contains `Personal entry biases`.
- `test_trade_entry_form_renders_premortem_additional_aside` — assert response contains `Earnings proximity + hold-through policy`.
- `test_trade_entry_form_aside_layout_class_present` — assert response contains `entry-textarea-row` (CSS class anchor; pins the structural wrapper).

**Suggested commit shape (TDD cycles):**

- B.1: 5 RED aside-content tests + GREEN template extension (5 asides, locked content) → commit (`feat(templates): Task B.1 — add example asides to entry-form textareas`)
- B.2: 1 RED layout-class test + GREEN CSS addition → commit (`style(web): Task B.2 — add flex layout for entry-form example asides`)

Total 6 new tests expected for Task B.

**Watch items:**

- The 5 textareas are NOT all in the same fieldset — thesis is in `<fieldset class="entry-section entry-section-thesis">` and the 4 premortem are in `<fieldset class="entry-section entry-section-premortem">`. The wrapper div pattern applies to each individual `<div><label>...</label><textarea>...</textarea></div>` block, not to the fieldset.
- Entry form is rendered both via `GET /trades/entry/form` (route) AND via the hyp-recs "Take this trade" button (which targets `closest tr` and swaps the form into the table). Verify aside renders correctly in BOTH paths if the test surface easily covers both; otherwise pin the route-rendered path explicitly.
- Aside content should be plain prose with parenthetical examples — NOT styled as form labels or hints that look interactive. Static `<ul>` inside `<aside>` with a `<strong>Examples:</strong>` lead-in.
- Per CLAUDE.md gotcha "`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM": this dispatch does NOT add new VM fields, but the TestClient template-render tests must NOT trip the base-layout-VM-field-missing error inadvertently (use the existing entry-form fixture pattern).

### §3.3 Task family C — Ruff N818 mechanical rename batch

**Acceptance criteria:**

- (C.AC.1) All 8 exception classes renamed with `Error` suffix per the table in §0.2.
- (C.AC.2) All ~79 references across `swing/` + `tests/` updated to use new names.
- (C.AC.3) `python -m pytest -m "not slow" -q` GREEN (test count unchanged; no behavioral regression).
- (C.AC.4) `ruff check swing/ | grep N818` returns zero matches.
- (C.AC.5) Single commit `chore(ruff): N818 — rename exceptions for Error suffix`.

**Implementation procedure (per §0.3 #11):**

```bash
# For each old → new name pair:
git grep -l SchemaVersionMismatch | xargs sed -i 's/SchemaVersionMismatch\b/SchemaVersionMismatchError/g'
git grep -l LeaseRevoked | xargs sed -i 's/LeaseRevoked\b/LeaseRevokedError/g'
# ... etc for all 8

# Verify:
python -m pytest -m "not slow" -q
ruff check swing/ | grep N818  # expect zero output
ruff check swing/ | wc -l       # expect 18 (down from 26; only E501 remains)
```

(PowerShell equivalent uses `Get-ChildItem -Recurse | Select-String <Old> | ForEach-Object { ... }` or use Bash via Git Bash on Windows.)

**Important:** use the `\b` word-boundary anchor in the sed pattern to prevent accidental substring matches (e.g., a hypothetical `SchemaVersionMismatchAlternate` would NOT be matched).

**Watch items:**

- Some tests may use `pytest.raises(SoftWarnException, match="...")` pattern. The class-name reference (first arg) is sed-handled. The `match=` regex (string literal) does NOT contain the class name and does NOT need updating.
- However if a test contains `pytest.raises(ValueError, match="WatchlistEntryNotFound")` (asserting on the exception STRING representation), the match string DOES need updating. Sed handles uniformly because the match string contains the class name. Surface any cases where:
  - The match string contains the class name escaped (e.g., `\bWatchlistEntryNotFound\b` as a regex anchor) — sed pattern with `\b` will still match.
  - The class name is referenced inside a longer regex with surrounding regex syntax — likely safe, but spot-check.
- Documentation strings in docstrings that mention the exception class by name: sed handles.
- `__all__` exports in module-level definitions: sed handles.

**Single-commit rationale (per §0.3 #10):** all 8 renames are mechanical and low-risk; one commit keeps history clean. If a regression surfaces post-merge, a single revert undoes the batch cleanly.

---

## §4 Adversarial review (Codex)

### §4.1 Setup (IMPLEMENTER runs this — convention per orchestrator-context "Executing-plans dispatch convention" 2026-05-02)

After ALL task-family commits land + tests are GREEN at branch HEAD, the implementer (this top-level Claude Code instance — NOT a subagent of the orchestrator) performs:

1. **Remove the marker file** so the implementer's own Codex invocation isn't blocked by the global PreToolUse hook:
   ```powershell
   Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
   ```
   (Path is at the MAIN project root, NOT inside the worktree. The hook only blocks Codex calls coming from subagents the implementer dispatches via the Task tool — the top-level implementer instance itself becomes free to invoke Codex once the marker is removed.)
2. Invoke `copowers:adversarial-critic` directly (NOT via the `copowers:executing-plans` wrapper).
3. Pass these args:
   - `PHASE`: `polish-bundle-2026-05-10`
   - `SPEC_PATH`: `docs/polish-bundle-2026-05-10-brief.md` (this brief)
   - `PLAN_PATH`: `docs/polish-bundle-2026-05-10-brief.md` (same — no separate plan file)
   - `BASELINE_SHA`: `794c51c`

### §4.2 Iteration (IMPLEMENTER drives)

- Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
- Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>` (or `Codex RN Critical #X (internal)` for Critical findings). The `(internal)` tag flags the commit as Codex-driven (vs operator-gate-driven `operator-gate I<N>`); convention from prior ship history.
- For each finding: FIX it OR ACCEPT-with-rationale (state explicitly in the response). ACCEPTED-with-rationale findings should be cited in the return report.
- Expected convergence: **2-3 rounds** (small surface; mechanical rename + UX-polish; precedent: polish-bundle-2026-05-09 converged in 3 rounds).
- After NO_NEW_CRITICAL_MAJOR, the implementer signals readiness for the operator-witnessed verification gate (§5) via the return report (§6). Operator drives the gate from there.

### §4.3 Pre-empt list (issues that have surfaced in similar prior dispatches)

These are NOT bugs — they're patterns Codex has flagged in similar dispatches. Pre-empt by making sure the implementation does not exhibit them:

- **Stale read predicates after pipeline auto-snapshots** — does NOT apply to this dispatch (no daily-management surface touched).
- **HX-Redirect target-route-unrouted gap** — does NOT apply to this dispatch (no new HX-Redirect endpoints).
- **Hidden form-field tampering surface** — does NOT apply to this dispatch (no form POST handlers added; entry form is rendered, not POST-handled here).
- **VM-field added without base-layout-VM audit** — does NOT apply (`HypRecsExpandedVM` is page-level, not base-layout-VM; no base-layout VM gains a new field).
- **Sed false-positive substring matches** — applies to Task C; mitigated by `\b` word-boundary anchor in sed pattern.
- **Cache + executor lifespan teardown race** — does NOT apply (no new executor; reuses existing app.state.price_fetch_executor).
- **Template duplication between OOB-swap and full-page render** — DOES apply to Task A; verify the current-price line renders in the same partial as the full hyp-recs expand response (no OOB-swap variant for hyp-recs expand currently exists; if one is added later, template logic must stay in single canonical partial per CLAUDE.md gotcha "HTMX OOB-swap partials that hand-duplicate full-page markup").
- **Empty API response treated as authoritative for write-through cache** — does NOT apply (this dispatch reads from cache; does not write to it; and the cache layer already implements the append-or-fall-back pattern per CLAUDE.md gotcha).

---

## §5 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR, prepare for operator-witnessed browser verification. Operator will exercise these surfaces; do NOT skip ahead — present each surface one at a time and pause for operator response per orchestrator-context "Visual-verification protocol."

**Surfaces to present:**

- **Surface 1 — Hyp-rec expanded current price (happy path).** Operator opens dashboard, expands a hyp-rec row (chevron click on a ticker that has live price data); verifies `Current: $X.XX` appears at top of expanded panel above Order parameters. Note any visual artifacts (line spacing, alignment, font size mismatch with neighboring elements).
- **Surface 2 — Hyp-rec expanded stale flag.** Operator finds (or temporarily induces) a stale-cache state; verifies `(stale)` indicator appears next to the price. May require manually clearing PriceCache OR running expand on a ticker whose price hasn't refreshed recently. If hard to induce in operator's actual flow, skip this gate AND note in the return report.
- **Surface 3 — Hyp-rec expanded missing-price fallback.** Operator finds a ticker where PriceCache returns None; verifies `Current: —` renders. Same induce-difficulty caveat as Surface 2.
- **Surface 4 — Trade entry form aside layout.** Operator navigates to `/trades/entry/form` (or via "Take this trade" from a hyp-rec); verifies all 5 asides render to the right of their respective textareas. Verify text content matches the locked aside content from §0.3 #6. Note any layout breakage at narrow viewport widths (operator will use their normal viewport width; mobile not in scope).
- **Surface 5 — Existing form behavior intact.** Operator submits a test entry (or aborts mid-fill); verifies form validation, hypothesis_label hidden input, chart-pattern section, soft-warn handling all still work. Pin no regressions from the wrapper div + aside additions.
- **Surface 6 — Ruff N818 silent regression check.** Operator runs `python -m pytest -m "not slow" -q` from the worktree; verifies test count + pass status. Optionally runs `ruff check swing/ | wc -l` and verifies count is 18.

**Pause-points for operator to flag visual artifacts:**

- After Surface 1 (hyp-rec expansion).
- After Surface 4 (entry form layout).

### §5.1 If a surface fails

- Hotfix on the same `polish-bundle-2026-05-10` branch with `fix(area): operator-gate I<N> — <description>` commit prefix.
- Re-run pytest; re-present the surface; do NOT skip ahead until operator confirms PASS.
- After all surfaces PASS, return to orchestrator with the return report (§7).

---

## §6 Return report shape

After operator-gate PASS, draft a return report with:

1. **Final HEAD on branch** — `git rev-parse polish-bundle-2026-05-10`.
2. **Commit count breakdown** — task-impl / Codex-fix / operator-gate-fix.
3. **Codex round chain** — rounds run + (Critical / Major / Minor) per round + convergence shape (e.g., R1 0/2/2 → R2 0/0/3 → R3 0/0/0 NO_NEW_CRITICAL_MAJOR).
4. **Test count delta** — pre-bundle baseline → post-bundle final (expected +12: A=6 + B=6).
5. **Ruff baseline delta** — 26 → 18 (expected; report actual).
6. **Operator-gate surface results** — per-surface PASS/FAIL/SKIPPED with notes.
7. **Per-task-family deviations from the brief** — anything the implementer chose differently and why.
8. **Codex Major findings ACCEPTED with rationale** — list each (e.g., "R2 Major #1 ACCEPTED: <rationale>").
9. **Watch items surfaced during dispatch but NOT acted on** — orchestrator-attention items (e.g., "noted that `swing/web/price_cache.py:142` has a TODO comment about cache invalidation; out of scope for this dispatch").
10. **Worktree teardown status** — clean teardown vs. ACL-locked husk (Phase 6/7/8 husk pattern is a known recurrence; cleanup-script handles).

---

## §7 First-step paste-ready prompt for the implementer

(Copy the block below verbatim into a fresh Claude Code instance after creating the worktree + activating the marker file.)

```
You are taking over as implementer for the swing-trading polish-bundle-2026-05-10 dispatch.

WORKING DIRECTORY: c:\Users\rwsmy\swing-trading\.worktrees\polish-bundle-2026-05-10
BRANCH: polish-bundle-2026-05-10
BASELINE_SHA: 794c51c

Step 1 — Read the dispatch brief end-to-end:
  docs/polish-bundle-2026-05-10-brief.md

It locks 11 design decisions (§0.3) that you do NOT re-litigate. Three task families:
  - Task A (3e.4): current price in hyp-rec expanded row
  - Task B (3e.7): example asides on 5 entry-form textareas
  - Task C (Ruff N818): mechanical rename of 8 exception classes

Step 2 — Read CLAUDE.md + docs/orchestrator-context.md (binding conventions).

Step 3 — Verify worktree state:
  git rev-parse HEAD                  # expect 794c51c
  git status                          # expect clean
  ls .copowers-subagent-active        # expect present (marker file at parent repo root, not in worktree — do NOT touch from inside worktree)
  python -m pytest -m "not slow" -q   # expect baseline GREEN

Step 4 — Execute the brief via superpowers:subagent-driven-development. Each task family commits via TDD discipline (red-green-commit cycles). Keep commits small + per the prefix conventions in §2.3.

Step 5 — After ALL task families land + GREEN, run the adversarial review YOURSELF (per §4.1):
  - Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
    (this top-level instance is then free to invoke copowers — the marker only blocked subagents you dispatched via Task tool)
  - Invoke copowers:adversarial-critic with PHASE=polish-bundle-2026-05-10,
    SPEC_PATH=docs/polish-bundle-2026-05-10-brief.md,
    PLAN_PATH=docs/polish-bundle-2026-05-10-brief.md,
    BASELINE_SHA=794c51c
  - Iterate rounds + land Codex-fix commits per §4.2 until NO_NEW_CRITICAL_MAJOR.

Step 6 — Draft return report per §6 + signal orchestrator. Orchestrator triages the report; operator drives the witnessed verification gate (§5); orchestrator handles integration merge to main after gate PASS.

DO NOT:
  - Push to origin from inside the worktree (orchestrator handles after gate PASS)
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers (the hook will block your invocation otherwise)
```

---

## §8 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-10 (post-handoff bootstrap).
- **Brief commit:** TBD (committed as final orchestrator action before dispatch).
- **Brief HEAD context:** `794c51c` on main.
- **Worktree path (binding):** `.worktrees/polish-bundle-2026-05-10/`.
- **Baseline test count:** 2121 fast (1 skipped).
- **Baseline ruff count:** 26 (8 N818 + 18 E501).
- **Expected post-dispatch test count:** ~2133 (+12: A=6 tests + B=6 tests).
- **Expected post-dispatch ruff count:** 18 (E501 only).
- **Sequence relative to other queued items:** independent — does not unblock or block 3e.15 / 3e.16 / 3e.10 / Phase 9 writing-plans.
