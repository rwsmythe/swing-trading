# Chart-Pattern Flag-V1 Chart-Access UX Dispatch — #2 + #3 Implementer Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Coupled Tier-2 dispatch addressing two related chart-access UX gaps surfaced in 2026-04-27 manual verification round 1:

- **#2** — Add an operator-friendly date-LESS chart URL `GET /charts/{ticker}.png` that resolves to the latest completed pipeline run's `data_asof_date` and either redirects to the existing date-prefixed StaticFiles URL or returns an informative 404. Today the only available URL is the date-prefixed `/charts/<data_asof_date>/<TICKER>.png` (already mounted as `StaticFiles` at `swing/web/app.py:234-238`); operators don't know the date offhand, hitting `/charts/AAPL.png` returns a generic 404 with no explanation.
- **#3** — Add an HTMX click-to-expand pattern on dashboard open-positions rows (mirroring the existing `/watchlist/{ticker}/expand` + `/row` pattern). When operator clicks an open-positions row, it expands inline to show the chart for that ticker. Close button collapses back. Reuses `swing/web/chart_scope.resolve_chart_status` for the "Chart unavailable" message when the ticker is out of the current pipeline's chart-scope set (which will be the COMMON case for held positions — open positions rotate out of chart-scope as the ticker drops out of A+ / near-trigger watchlist).

The two are independent in their infrastructure (#3 can use the existing date-prefixed URL pattern; #2 is purely a routing convenience) but coupled in the user-story theme (chart access during trade management). Bundled into one dispatch for cohesion.

**Expected duration:** 2-3 hours including TDD + adversarial Codex round.

---

## §0 Read first

1. `docs/chart-pattern-flag-v1-manual-verification-results.md` §"#2 — No standalone chart-image route" (lines 65-72) and §"#3 — Open positions table rows don't expand to charts" (lines 74-84). The user-facing problem statements + verification-round-1 empirical evidence.
2. `docs/orchestrator-context.md` §"Currently in-flight work" (Tier-1 mathtext fix landed; this is the next Tier-2 dispatch in operator's priority list) + §"Lessons captured" (especially Phase 4+5+6+7 patterns on single-subagent dispatch + observable verification + 4-tier commit convention; HTMX OOB-swap drift; base-layout 5-VM rule per Phase 4 lesson).
3. `docs/orchestrator-context.md` §"Binding conventions (project-wide)" — commit-message convention (4-tier), no-amend / no-`--no-verify`.
4. `CLAUDE.md` gotchas — particularly **HTMX OOB-swap partials must go through the SAME `{% include %}` target** (do not hand-duplicate markup) and the **base-layout 5-VM rule** (per Phase 4 lesson, scope only to consumer VMs that base.html.j2 actually dereferences).
5. **Existing watchlist expand pattern (model to mirror):**
   - `swing/web/routes/watchlist.py:27-67` — both routes (`/expand` and `/row`).
   - `swing/web/view_models/watchlist.py:227-296` — `build_watchlist_expanded` builder + `WatchlistExpandedVM` shape.
   - `swing/web/templates/partials/watchlist_expanded.html.j2` — full partial; lines 33-40 show the chart `<img>` + chart-unavailable conditional.
6. **Existing open-positions surfaces:**
   - `swing/web/templates/partials/open_positions.html.j2` — table wrapper.
   - `swing/web/templates/partials/open_positions_row.html.j2` — single row partial (used in 4+ `routes/trades.py` round-trip render points).
   - `swing/web/view_models/open_positions_row.py` — `OpenPositionsRowVM` and `build_open_positions_row` builder.
7. **Chart-scope resolver to reuse:** `swing/web/chart_scope.py` — `resolve_chart_status(...)` returns `(chart_reason, chart_reason_message)` with reasons in `CHART_REASON_MESSAGES`. **Reuse this; do NOT add new reason types.**
8. **Existing /charts mount:** `swing/web/app.py:234-238` (`StaticFiles` from `cfg.paths.charts_dir`). Date-prefixed URL pattern `/charts/<date>/<ticker>.png` is the primary route; #2 adds a date-less convenience layer ON TOP, NOT replacing it.

Do NOT read the chart-pattern flag-v1 design spec or implementation plan — those documents pre-date this UX work and have no relevant content here.

---

## §0.1 Skill posture

- Standard `superpowers:using-superpowers` skill at session start.
- `superpowers:test-driven-development` — multiple red-green cycles (one per route + VM + template surface).
- `superpowers:verification-before-completion` — MANDATORY before final return report.
- `copowers:adversarial-critic` — invoke ONCE on the combined diff at end. Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:writing-plans`, `superpowers:executing-plans`, or any subagent-dispatching skill. Single implementer dispatch; brief is the plan.
- DO NOT dispatch sub-subagents.

---

## §1 Strategic context

The verification round 1 walkthrough confirmed both gaps empirically: operator entered DHC trade during the walkthrough, ticker moved from watchlist to open-positions, and the chart-view path disappeared. Tier-1 mathtext fix landed (`29c93f5`). Tier-4 verification-doc bundle landed (`84dac00`). This is the next Tier-2 dispatch.

The infrastructure is mostly already in place:
- StaticFiles mount for `/charts/<date>/<ticker>.png` exists.
- The chart_scope resolver returns rich operator-facing reasons.
- The watchlist row expand pattern is well-established and reusable.
- The open-positions row partial is single-source via `{% include %}` (used in dashboard + prices-refresh OOB swap).

This dispatch wires up small connecting routes + a new partial. **No new domain logic; no schema changes; no Phase 2 carve-outs.**

---

## §2 Scope

### In scope

| Surface | Change |
|---|---|
| `swing/web/routes/trades.py` (or a new `routes/charts.py` — implementer's call) | New route `GET /charts/{ticker}.png` (no date) — looks up latest `pipeline_runs.data_asof_date` for completed runs, returns HTTP 303 See Other redirect to `/charts/<date>/{ticker}.png` if PNG exists, else 404 with body using `chart_scope.resolve_chart_status` reason messages. |
| `swing/web/routes/trades.py` | New routes `GET /trades/open/{trade_id}/expand` and `GET /trades/open/{trade_id}/row` (mirroring watchlist's `/expand` + `/row` pattern). |
| `swing/web/view_models/open_positions_row.py` | New `OpenPositionsExpandedVM` dataclass + `build_open_positions_expanded(conn, trade_id)` builder. Returns `None` when trade not found / not open → routes surface 404. |
| `swing/web/templates/partials/open_positions_expanded.html.j2` | New partial — full-width expanded row with close button, ticker heading, chart `<img>` (date-prefixed URL since the VM has the date), and chart-unavailable graceful degradation. **Use `{% include %}` to share chart-display logic if practical; otherwise mirror watchlist_expanded's lines 33-40 verbatim, NOT hand-duplicate (per CLAUDE.md gotcha — go through include OR keep one canonical chart-display partial).** |
| `swing/web/templates/partials/open_positions_row.html.j2` | Add HTMX click-to-expand attributes on the row (`hx-get="/trades/open/{{ row.trade_id }}/expand"`, `hx-target="closest tr"`, `hx-swap="outerHTML"`). |
| `tests/web/` | New tests for both #2 and #3. Mirror watchlist-expand test patterns (look at any existing watchlist-expand test as precedent; if none exists, write greenfield following the project's TestClient + assert-on-rendered-HTML pattern). |
| `docs/chart-pattern-flag-v1-manual-verification.md` | Update §3 chart-access-path V1-known-limitations subsection to remove "no standalone chart-image route" and "open-positions rows don't expand to chart" — these will be RESOLVED by this dispatch. Keep #4 (chart-scope alignment) as a remaining known limitation. |

### Out of scope

- **#4 chart-scope set alignment** — separate substantive dispatch with operator-design discussion.
- **Other surfaces showing open positions** — verified at brief-drafting time: `open_positions.html.j2` is included only in `dashboard.html.j2` and `prices_refresh_container.html.j2` (the prices-refresh OOB swap path). Both surfaces share the same `{% include %}` so the row-partial change applies uniformly.
- **Modifying `chart_scope.resolve_chart_status`** — reuse as-is; do not add new chart_reason types or messages. If you find existing messages awkward for the open-positions context, flag it in Open follow-ups, do NOT modify in this dispatch.
- **Modifying the existing `/watchlist/{ticker}/expand` pattern** — the pattern is the model; do not change it.
- **Open-positions expanded row content beyond the chart** — V1 scope-limit. The expanded row contains: close button, ticker heading, chart `<img>` (or chart-unavailable message). NO P&L breakdown, NO advisories list, NO recent-events log. Operator can request additional fields as a post-V1 enhancement if useful.
- **External chart links (e.g., yfinance)** — not in V1 scope.
- **Schema / migration changes** — none required; both #2 and #3 are pure routing + presentation layer.
- **CLI / pipeline / advisories / classifier code** — not touched.

> **2026-05-30 (SB4) — L7 reversal note:** the open-positions row-expand now inlines the `position_detail` SVG (read from the `chart_renders` cache), reversing the §2 separate-page decision for this surface. The standalone date-less `GET /charts/{ticker}.png` route (§4.1) and the date-prefixed `<img>` previously rendered in the row-expand are no longer the chart-access path for open positions; the expand fragment now renders the SB3 candlestick+BULZ-zones SVG inline (with a terminal cache-miss fallback), per the Phase 14 SB4 Slice 1 plan.

---

## §3 Binding conventions

- **Branch:** `main`. Commit conventionally; no Claude co-author footer; no `--no-verify`; no amending.
- **Commit-message convention** (per orchestrator-context Binding conventions, 4-tier):
  - **Production task commits** (one per logical chunk; suggested split):
    - `feat(web): chart-access #2 — date-less /charts/{ticker}.png with chart_scope-aware 404`
    - `feat(web): chart-access #3 — open-positions row HTMX expand to chart`
    - (or as many TDD-discipline commits as you need; each task's red-green cycle is its own commit per project TDD discipline)
  - **Adversarial review-fix commits:** `fix(web): Codex R<N> Major <M> — <description>`. No `(internal)` qualifier — single end-of-task Codex round, not within-task internal-Codex.
  - **Subject-only ERE grep observable verification:** `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): chart-access'` — invoke before each task commit per the binding-conventions ERE refinement (Phase 7 lesson; `-E` flag is required, `+` is literal in BRE).
- **TDD discipline:** failing test → see fail → minimal implementation → pass → commit. Per logical change.
- **Fast suite must stay green:** `python -m pytest -m "not slow" -q`. Baseline as of HEAD `84dac00`: **1145 fast tests passing**. Post-dispatch: 1145 + N (new tests). **Trust pytest output over this number** per project gotcha.
- **Ruff baseline 81 errors;** do not introduce new violations.
- **Phase isolation:** `swing/trades/` and `swing/data/` are read-only. This dispatch is web-layer-only — should not touch either. If you find yourself needing to touch them, STOP and report; that's a scope boundary failure.
- **Base-layout 5-VM rule:** check whether `base.html.j2` dereferences any new field you might add (per Phase 4 lesson, scope only to consumer VMs). New `OpenPositionsExpandedVM` is a consumer-only VM (rendered in the expanded partial); base.html.j2 has no reason to reference it. Do NOT blanket-update all 5 base-layout VMs.
- **HTMX OOB-swap drift:** if you touch `prices_refresh_container.html.j2` (which `{% include %}`s `open_positions.html.j2`), preserve the include — do NOT hand-duplicate markup (per CLAUDE.md gotcha).

---

## §4 Per-task specifications

### §4.1 — #2: date-less chart URL route (TDD)

**Route signature:** `GET /charts/{ticker}.png` — note: this conflicts with the StaticFiles mount at `/charts/`. **Verify the FastAPI route registration order**: explicit `@router.get("/charts/{ticker}.png")` route MUST be registered BEFORE the StaticFiles mount, OR StaticFiles must be configured to NOT match patterns with embedded `.png`. Investigate empirically — write the test FIRST and confirm the route handler fires (not StaticFiles' 404 path).

**Behavior:**

1. Look up latest completed pipeline_run's `data_asof_date`:
   ```python
   row = conn.execute("""
       SELECT data_asof_date FROM pipeline_runs
       WHERE state = 'complete'
       ORDER BY finished_ts DESC LIMIT 1
   """).fetchone()
   ```
2. If no completed run → 404 with body using `CHART_REASON_MESSAGES["no-run"]`.
3. Else: call `chart_scope.resolve_chart_status(conn, ticker=ticker, data_asof_date=<date>, ...)`. Returns `(chart_reason, chart_reason_message)` tuple where `(None, None)` means available.
4. If available → return HTTP 303 See Other redirect to `/charts/<date>/<ticker>.png` (existing StaticFiles mount serves it).
5. Else → 404 with body containing the operator-facing `chart_reason_message`.

**Tests (greenfield; pattern after existing FastAPI TestClient tests in `tests/web/`):**
- Available case: insert a fixture pipeline_run + chart-scope target row + create a temp PNG file. Hit `/charts/AAPL.png`; assert HTTP 303 + `Location: /charts/<date>/AAPL.png`.
- No-run case: empty pipeline_runs table. Hit `/charts/AAPL.png`; assert 404 + body contains `CHART_REASON_MESSAGES["no-run"]`.
- Out-of-scope case: pipeline_run exists, ticker NOT in chart-scope. Hit `/charts/XYZ.png`; assert 404 + body contains the out-of-scope message.
- Insufficient-data case: optional, mirrors the chart_scope.resolver output paths.

**Acceptance:**
- Route handler defined, properly registered (route order vs StaticFiles confirmed via test).
- All 3 (or 4) test cases green.
- Operator can hit `http://127.0.0.1:8080/charts/AAPL.png` in browser and either see the chart (after 303 redirect) or get an informative 404.

### §4.2 — #3: open-positions row HTMX expand (TDD)

**Routes:**
- `GET /trades/open/{trade_id}/expand` — returns the expanded fragment.
- `GET /trades/open/{trade_id}/row` — returns the compact row fragment (close-button target).

**Mirror `swing/web/routes/watchlist.py:27-67` pattern.** `trade_id` (int) is the route key (more unambiguous than ticker — defends against future "could you have two open trades for the same ticker?" edge).

**View model:**

```python
@dataclass(frozen=True)
class OpenPositionsExpandedVM:
    trade_id: int
    ticker: str
    data_asof_date: str | None       # for /charts/<date>/<ticker>.png
    chart_reason: str | None         # None when chart available; else one of CHART_REASON_MESSAGES keys
    chart_reason_message: str | None # operator-facing message; mirrors WatchlistExpandedVM contract
```

`build_open_positions_expanded(conn, trade_id)` → `OpenPositionsExpandedVM | None`:
1. Look up trade; if not found OR not currently open → return None (route 404s).
2. Look up latest completed pipeline_run's data_asof_date.
3. Call `chart_scope.resolve_chart_status(...)` for the trade's ticker.
4. Return populated VM.

**Partial: `swing/web/templates/partials/open_positions_expanded.html.j2`** — mirror `watchlist_expanded.html.j2` chart-display logic (lines 33-40 there are the exact precedent). Skeleton:

```jinja
{#- Expects: expanded (OpenPositionsExpandedVM) -#}
<tr id="open-positions-row-{{ expanded.trade_id }}" class="expanded">
  <td colspan="<actual colspan from open_positions_row.html.j2>">
    <button class="close-expanded"
            type="button"
            onclick="event.stopPropagation()"
            hx-get="/trades/open/{{ expanded.trade_id }}/row"
            hx-target="closest tr"
            hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'
            aria-label="Close expanded row for {{ expanded.ticker }}"
            title="Close">✕</button>
    <h3>{{ expanded.ticker }}</h3>
    {% if expanded.chart_reason is none and expanded.data_asof_date %}
      <img src="/charts/{{ expanded.data_asof_date }}/{{ expanded.ticker }}.png"
           alt="Chart {{ expanded.ticker }}">
    {% elif expanded.chart_reason_message %}
      <div class="chart-unavailable" data-chart-reason="{{ expanded.chart_reason }}">
        {{ expanded.chart_reason_message }}
      </div>
    {% endif %}
  </td>
</tr>
```

(Verify the `colspan` value matches `open_positions_row.html.j2`'s actual cell count; mismatch breaks the table layout.)

**Modify `open_positions_row.html.j2`:** add HTMX click-to-expand on the `<tr>`. Pattern from watchlist (look at `swing/web/templates/partials/watchlist_row.html.j2` for the canonical click-target approach including the `hx-target="closest tr"` and `hx-swap="outerHTML"` attributes). Note the Bug-1 lesson from CLAUDE.md/orchestrator-context: any interactive child element (button, link) inside the row must `event.stopPropagation()` to prevent triggering the row expand.

**Tests:**
- Open trade exists, ticker in chart-scope: hit `/trades/open/<id>/expand`; assert HTML contains the chart `<img>` with the correct date-prefixed URL.
- Open trade exists, ticker out of chart-scope: hit `/trades/open/<id>/expand`; assert HTML contains the chart-unavailable div with the expected reason message.
- Trade closed (not open): hit `/trades/open/<id>/expand`; assert 404.
- Trade nonexistent: hit `/trades/open/<id>/expand`; assert 404.
- Close-button collapse: hit `/trades/open/<id>/row`; assert HTML matches the compact row partial output.

**Acceptance:**
- All test cases green.
- Operator can click an open-positions row in the browser, see chart inline (or "Chart unavailable" message), click X to collapse.
- Both dashboard and prices-refresh OOB-swap surfaces honor the new click-to-expand pattern (single-include guarantee).

### §4.3 — Verification doc update

In `docs/chart-pattern-flag-v1-manual-verification.md` §3 "Chart access path (V1 known limitations)":

- Remove the bullet about no standalone chart-image route at `/charts/<TICKER>.png`.
- Remove the bullet about open-positions rows not expanding to chart.
- Keep the bullet about chart-scope tickers NOT in watchlist needing on-disk inspection (Tier-2 #4 still pending, but the workaround now: hit `/charts/<TICKER>.png` for chart-scope tickers regardless of watchlist membership).
- Add a §3 verification check for the new date-less `/charts/<TICKER>.png` URL — operator can hit it in the browser and confirm 303 redirect + chart display OR informative 404.
- Add a §1.1 (or §1.5) verification check for the new open-positions row click-to-expand — analogous to §1.3 watchlist expand.

### §4.4 — Manual visual verification (BLOCKING)

Per the standing rendering-fix discipline (Phase 6 + Tier-1 mathtext-fix lesson). For UI changes, manual operator-witnessed verification is the actual confidence source — TestClient + asserted HTML strings verify structure, NOT the runtime DOM/HTMX behavior (per the existing JS-execution-test-harness gap noted in `docs/phase3e-todo.md`).

**Procedure:**

1. Start `swing web`.
2. Open `http://127.0.0.1:8080/` in a browser.
3. **#2 verification:**
   - Hit `http://127.0.0.1:8080/charts/<chart-scope-ticker>.png` (use a ticker known to be in latest pipeline's chart-scope set — see `docs/chart-pattern-flag-v1-manual-verification.md` §0 step 3 for SQL to find them).
   - Confirm: chart PNG renders in the browser (302/303 redirect happens silently; final URL bar may show date-prefixed URL).
   - Hit `http://127.0.0.1:8080/charts/XYZNOTINSCOPE.png` (a clearly-out-of-scope ticker).
   - Confirm: 404 page renders with the operator-facing reason message visible.
4. **#3 verification:**
   - On the dashboard, identify an open position (operator currently has DHC, trade #2).
   - Click the open-positions row.
   - Confirm: row expands inline with chart (if ticker in scope) OR "Chart unavailable" message (if ticker out of scope).
   - Click the close button (X).
   - Confirm: row collapses back to compact form.
   - Click the row again.
   - Confirm: re-expands cleanly (toggle works).
   - Hit `/prices/refresh` (the OOB-swap path).
   - Confirm: open-positions table re-renders after refresh; click-to-expand still works on the refreshed rows (single-include guarantee).
5. **Include browser screenshot OR explicit operator-witnessed-PASS confirmation in the return report** for both #2 and #3 paths.

**Acceptance:** all manual steps confirm visually; PNG rendering correct; HTMX swap behavior correct; close-button + re-expand toggle works; OOB-swap path doesn't break the click-to-expand binding.

### §4.5 — Adversarial Codex round

After all task commits land, invoke `copowers:adversarial-critic` on the diff between HEAD and `84dac00` (HEAD at brief-drafting time). Iterate to `NO_NEW_CRITICAL_MAJOR`.

**Watch items to specifically pass to the critic:**

- Does `/charts/{ticker}.png` route ordering correctly precede the StaticFiles mount (so the dynamic handler fires, not StaticFiles' built-in 404)?
- Does `OpenPositionsExpandedVM` introduce any field the base.html.j2 layout dereferences (per Phase 4 lesson — should be consumer-only, but verify)?
- Does the new partial use `{% include %}` to share chart-display logic with watchlist_expanded, OR if it duplicates the chart-display markup, is the duplication intentional and documented (per CLAUDE.md HTMX OOB-swap drift gotcha — same principle applies to non-OOB partials when they share visual elements)?
- Does the click-to-expand on `open_positions_row.html.j2` correctly stop propagation on existing interactive children (buttons in the Actions column, etc.) per the Bug-1 lesson?
- Are there other surfaces (besides dashboard + prices-refresh OOB) that render open_positions and would break or behave inconsistently with the new click-to-expand? (Brief asserts none; verify.)
- Does the trade_id route key correctly distinguish open trades, or could a closed trade's id collide with an open one and cause stale-data display?
- Does the `chart_scope.resolve_chart_status` reuse cover all expected reasons for open-positions tickers (the resolver was designed for watchlist context; might need open-positions-specific message)? Brief says reuse as-is — flag if the messages are actively misleading in the open-positions context.

**Fix-commits use `fix(web): Codex R<N> Major <M> — <description>` format** (no `(internal)` qualifier).

---

## §5 Done criteria

1. ✅ `/charts/{ticker}.png` route handler implemented; tests green for available + no-run + out-of-scope cases.
2. ✅ `/trades/open/{trade_id}/expand` and `/row` routes implemented; tests green for in-scope + out-of-scope + closed-trade + nonexistent-trade cases.
3. ✅ `OpenPositionsExpandedVM` + `build_open_positions_expanded` defined; new partial `open_positions_expanded.html.j2` created.
4. ✅ `open_positions_row.html.j2` updated with HTMX click-to-expand (with stopPropagation on interactive children).
5. ✅ `docs/chart-pattern-flag-v1-manual-verification.md` §3 updated to reflect post-fix state (#2 + #3 limitations resolved; #4 still listed).
6. ✅ Fast suite green: `python -m pytest -m "not slow" -q` — 1145 + N passed (N = new tests added).
7. ✅ Manual visual verification done (operator-witnessed OR screenshots in return report) — both #2 and #3 paths confirmed.
8. ✅ Adversarial Codex round → `NO_NEW_CRITICAL_MAJOR`; any review-fix commits landed.
9. ✅ Working tree clean (only `.tmp-*/` scratch dirs untracked).

---

## §6 Return report format

Produce as your final message:

```markdown
## Chart-Access UX (#2 + #3) Return Report

**Commits landed (HEAD = <SHA>):**
- <SHA1> <subject1>
- <SHA2> <subject2>
- ...

**Fast suite:** <baseline 1145> → <post-dispatch> (<delta> = N new tests)
**Adversarial Codex verdict:** <NO_NEW_CRITICAL_MAJOR after R<N>>

### TDD discipline evidence

For #2 and #3 separately, briefly note the red-then-green sequence per logical chunk.

### Visual verification

**#2 date-less /charts/{ticker}.png:**
- In-scope ticker (`<ticker>`): PASS / FAIL — <one sentence; URL bar showed redirect; chart displayed>
- Out-of-scope ticker (`XYZNOTINSCOPE`): PASS / FAIL — <one sentence; 404 page with message>

**#3 open-positions click-to-expand:**
- Click row → expands inline: PASS / FAIL — <one sentence>
- Close button collapses: PASS / FAIL — <one sentence>
- Re-expand toggle works: PASS / FAIL — <one sentence>
- Prices-refresh OOB-swap path preserves expand binding: PASS / FAIL — <one sentence>
- "Chart unavailable" path renders for out-of-scope ticker (operator's actual open positions are likely all out-of-scope): PASS / FAIL — <one sentence>

Screenshots attached at: `<path>` (or "operator witnessed live; no screenshots").

### Adversarial findings + dispositions

| Round | Finding | Severity | Disposition |
|---|---|---|---|
| R1 | <one line> | Critical/Major/Minor | FIXED in <SHA> / ACCEPTED <reason> |
| ... | ... | ... | ... |

### Open follow-ups

- V1 expanded-row content scope-limit: open-positions expanded row contains chart only. If operator finds value in additional fields (P&L breakdown, advisories list, recent events log), those are a separate post-V1 dispatch.
- <any other items deferred per scope or surfaced for future work>

### Out-of-scope items NOT touched (confirmation)

- Tier-2 #4 chart-scope alignment: NOT touched.
- Other open-positions surfaces (verified single-source): NOT applicable.
- `chart_scope.resolve_chart_status` modifications: NOT touched.
- Watchlist expand pattern: NOT modified.
- Schema / migrations / Phase 2 (`swing/trades/`, `swing/data/`): NOT touched.
- CLI / pipeline / advisories / classifier: NOT touched.
```

---

## §7 If you get stuck

- **`/charts/{ticker}.png` route doesn't fire (StaticFiles intercepts)** → investigate FastAPI route registration order in `swing/web/app.py`. The dynamic route MUST be registered BEFORE `app.mount("/charts", StaticFiles(...))`, OR you may need to add the route to a sub-router that's mounted before StaticFiles. Test-driven: write the test first, watch it fail in a way that tells you which handler fired.
- **`open_positions_row.html.j2` colspan unclear** → look at the actual template; count the `<td>` cells in the existing compact-row markup. Use that exact value in the expanded partial's `colspan`.
- **`chart_scope.resolve_chart_status` requires args you don't have** → look at how `build_watchlist_expanded` calls it (`swing/web/view_models/watchlist.py:227-296`) for the canonical invocation pattern.
- **HTMX click on row triggers other interactive elements** → per Bug-1 lesson + CLAUDE.md gotcha, use `event.stopPropagation()` on Actions-column buttons + any other interactive child. Also: use `hx-trigger="click from:closest tr"` if you need finer control over what fires the expand. Worst case, scope to a dedicated chevron cell per the open architectural item.
- **Test for trade_id route key fails because closed trades' ids collide** → expected behavior; the route should 404 on closed trades. If you need a fixture with both open and closed trades, look at existing `tests/web/` fixture-helpers for patterns.
- **Adversarial round surfaces issues outside this brief's scope** (e.g., other surfaces with stale chart-display markup) → flag in return report under "Open follow-ups." Do NOT expand scope mid-session per the orchestrator-context anti-pattern.
- **Manual visual verification reveals UX issues not anticipated by the brief** (e.g., expanded row jitters; chart loads slowly; OOB-swap timing race) → document in return report; defer fix unless it's a critical regression. Operator + orchestrator will triage.
- **Fast suite shows test count drift** (not 1145 baseline) → trust pytest output over this brief; report the actual delta.
- **Anything else** → produce the return report with what you have, mark the blocked item explicitly, and stop. Operator + orchestrator will triage.
