# Hypothesis Recommendation Engine — Frontend (Session 2) Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Build the UI consumption layer for the hypothesis recommendation engine. Dashboard surface for active recommendations (top-N candidates with hypothesis assignments + per-hypothesis progress); CLI `swing trade entry` pre-fills `--hypothesis` flag with the suggested label from the matcher when the operator names a ticker that has an active recommendation. **Depends on Session 1 (backend) landing first** — this brief assumes the registry, matcher, prioritizer, and tripwire computations exist as described in `docs/hypothesis-recommendation-backend-brief.md`. Phase 3 only — no Phase 2 carve-out needed.
**Expected duration:** ~1 session (3 hours).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions.
2. `docs/orchestrator-context.md` — particularly §"Recent decisions and framings" 2026-04-25 entries on operational-branch as evidence-generation (the active hypothesis-recommendation framing this UI exposes).
3. `docs/hypothesis-recommendation-backend-brief.md` — Session 1 brief that this depends on. Specifically: the matcher returns `HypothesisMatch` objects with `hypothesis_id` + `suggested_label_descriptive` + `priority_hint`; the prioritizer returns ordered `CandidateRecommendation` list; the registry contains the 4 frozen hypotheses; tripwire status is per-hypothesis.
4. `swing/web/view_models/dashboard.py` — current DashboardVM. You'll extend with active-recommendations section.
5. `swing/web/templates/dashboard.html.j2` (or whatever the dashboard template is named) — current dashboard layout. New section appears alongside existing today_decisions + watchlist sections.
6. `swing/cli.py` (or `swing/cli/trade.py`) — current `swing trade entry` command. You'll add pre-fill logic.
7. `swing/web/view_models/watchlist.py` — current WatchlistVM. May benefit from adjacent recommendation-aware classification.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after task commits land. Watch items in §5.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans`.

---

## 1. Strategic context (compressed)

Session 1 built the backend (registry, matcher, prioritizer, tripwire compute, journal extension, hypothesis CLI). This session exposes that backend in two operator-facing surfaces:

1. **Dashboard recommendations panel:** for the most recent pipeline run's candidates, show the top-N hypothesis-driven recommendations. Each recommendation displays: ticker, current price, suggested hypothesis (name + descriptive label), per-hypothesis progress (n/N), tripwire status if fired. Operator scans, decides which to act on.
2. **CLI entry pre-fill:** when operator runs `swing trade entry --ticker XYZ` AND XYZ has an active hypothesis match in the most recent evaluation_run, the CLI looks up the suggested label and pre-fills the `--hypothesis` value. Operator can override by passing `--hypothesis "..."` explicitly.

Both surfaces consume Session 1's `match_candidate_to_hypotheses` + `prioritize_recommendations` directly — no new compute logic in this session.

---

## 2. Scope

### In scope (Phase 3 only)

- **Dashboard VM extension:** new `HypothesisRecommendation` dataclass (subset of CandidateRecommendation for display); new `active_recommendations: tuple[HypothesisRecommendation, ...]` field on DashboardVM. Populated from Session 1's prioritizer applied to the latest pipeline run's candidates.
- **Dashboard template extension:** new section "Hypothesis-driven recommendations" rendered AFTER the existing today_decisions section. Renders the recommendations as a table with: ticker, price, hypothesis name, hypothesis progress bar (e.g., "1/5 samples"), tripwire indicator if fired, suggested label (truncated for table display, full on hover/expand).
- **Watchlist VM extension (optional, recommend):** WatchlistVM gains an analogous `active_recommendations` field so the standalone watchlist page can show the same surface (or a related one).
- **CLI entry pre-fill:** `swing trade entry --ticker XYZ` looks up XYZ in the latest pipeline run's recommendations; if found, pre-fills `--hypothesis` with the suggested label. If `--hypothesis` is explicitly passed, the explicit value wins (override). If XYZ has no recommendation, no pre-fill (operator types their own label).
- **Tests:** dashboard VM, watchlist VM (if extended), template rendering, CLI pre-fill behavior.

### Out of scope

- Modification of the Session 1 backend (matcher/prioritizer/tripwire/registry/journal extension).
- Modification of the doctrine-defensible miss set or hypothesis investigation plan v0.1 (frozen at Finviz-pool study D1 and hyp1 brief D1 respectively).
- HTMX OOB-swap for live updates of the recommendations panel (out of scope; full-page render is sufficient).
- Operator-facing hypothesis-creation UI (creating new hypotheses is via migration only, per the discipline).
- Modification of any existing dashboard panels beyond the new section.

---

## 3. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD throughout.**
- **Tests:** trust pytest output; baseline shifts with parallel work and especially with Session 1 landing.
- **Phase 3 only:** Touch `swing/web/`, `swing/cli/`, `tests/web/`, `tests/cli/`. NO `swing/data/`, `swing/trades/`, or `swing/recommendations/` modification.
- **Base-layout VM gotcha:** per CLAUDE.md, every base-layout VM must gain new fields together OR Jinja 500s unrelated routes. If `active_recommendations` is referenced in `base.html.j2`, every base-layout VM (DashboardVM, PipelineVM, JournalVM, WatchlistVM, PageErrorVM) must include it. Recommend: keep `active_recommendations` SCOPED to DashboardVM (and optionally WatchlistVM); render in a non-base-layout section.

---

## 4. Task specifications

### 4.1 Dashboard VM + recommendations population

Extend DashboardVM with `active_recommendations: tuple[HypothesisRecommendation, ...] = ()` (default empty so any temporary callers won't break).

In `build_dashboard`: after fetching `candidates_by_ticker` from `pipeline_runs.evaluation_run_id`, for each candidate also fetch its `candidate_criteria` results, then call `swing.recommendations.hypothesis.match_candidate_to_hypotheses` and `prioritize_recommendations`. Take top 10 (configurable constant). Map to display VM.

`HypothesisRecommendation` dataclass:
```python
@dataclass(frozen=True)
class HypothesisRecommendation:
    ticker: str
    current_price: float | None  # from prices cache
    hypothesis_id: int
    hypothesis_name: str
    hypothesis_progress_n: int
    hypothesis_progress_target: int
    tripwire_fired: bool
    tripwire_reason: str | None  # "3 consecutive -1R" etc., None if not fired
    suggested_label: str
```

TDD: dashboard test that with synthetic candidates + criteria, the active_recommendations field is populated correctly + ordered correctly + truncated to top-N.

Commit: `feat(web): dashboard active hypothesis recommendations`.

### 4.2 Dashboard template extension

In `dashboard.html.j2`, add a new section AFTER today_decisions section:

```jinja
{% if vm.active_recommendations %}
<section class="hypothesis-recommendations">
  <h2>Hypothesis-driven recommendations</h2>
  <table>
    <thead><tr>
      <th>Ticker</th><th>Price</th><th>Hypothesis</th><th>Progress</th><th>Tripwire</th><th>Suggested label</th>
    </tr></thead>
    <tbody>
      {% for rec in vm.active_recommendations %}
      <tr {% if rec.tripwire_fired %}class="tripwire-fired"{% endif %}>
        <td>{{ rec.ticker }}</td>
        <td>${{ "%.2f"|format(rec.current_price) if rec.current_price else "—" }}</td>
        <td>{{ rec.hypothesis_name }}</td>
        <td>{{ rec.hypothesis_progress_n }} / {{ rec.hypothesis_progress_target }}</td>
        <td>{% if rec.tripwire_fired %}<strong>FIRED</strong>: {{ rec.tripwire_reason }}{% else %}—{% endif %}</td>
        <td title="{{ rec.suggested_label }}">{{ rec.suggested_label[:60] }}{% if rec.suggested_label|length > 60 %}…{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}
```

Add minimal CSS for `.tripwire-fired` (e.g., red background or red left-border) so the operator can't miss tripwire status.

TDD: template snapshot or rendered-content assertions.

Commit: `feat(web): dashboard template renders hypothesis recommendations`.

### 4.3 CLI entry pre-fill

Modify `swing trade entry` to accept the existing flags PLUS a pre-fill behavior:

- If `--ticker XYZ` is provided AND `--hypothesis` is NOT provided: query the latest completed pipeline_run's evaluation_run; if XYZ is in candidates AND matches an active hypothesis (via the matcher), pre-fill `--hypothesis` with the suggested label. Print "Pre-filled --hypothesis: <label>" so the operator sees what was selected.
- If `--ticker XYZ` is provided AND `--hypothesis` IS provided: explicit value wins; no pre-fill.
- If XYZ has no active recommendation: proceed without pre-fill (current behavior preserved).

TDD: CLI tests for each branch (pre-fill happens; explicit override; no recommendation).

Commit: `feat(cli): trade entry pre-fills hypothesis from active recommendation`.

### 4.4 Watchlist VM extension (optional, recommended)

Optional: extend WatchlistVM analogously so the standalone `/watchlist` page can also surface active recommendations relevant to watchlist tickers. If you do this, update the watchlist template too; if you don't, document why (e.g., scope discipline) in the return report.

If included: TDD per the dashboard pattern. Commit: `feat(web): watchlist active hypothesis recommendations`.

---

## 5. Adversarial review

After task commits land, `copowers:adversarial-critic` on combined diff. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items:**

- **Pre-fill default vs explicit override.** Verify the CLI gracefully handles all combinations: no --ticker (interactive ticker prompt or error per existing flow); --ticker but no recommendation; --ticker with recommendation (pre-fill); --ticker + --hypothesis (override).
- **Pre-fill stability across re-runs.** If the operator runs `swing trade entry --ticker XYZ` twice in a row, the pre-filled hypothesis should be consistent (deterministic). Verify the prioritizer + matcher are deterministic for the same input.
- **Dashboard render with empty recommendations.** Verify the `{% if %}` guard prevents an empty section block from rendering. Verify no Jinja errors when active_recommendations is empty.
- **Tripwire visual alarm.** Verify the `tripwire-fired` CSS class produces a visually obvious indicator. The whole point is the operator can't miss it.
- **Suggested label truncation.** 60 chars is a starting point. If hypothesis names plus context routinely exceed this, adjust upward. Verify tooltip-on-hover preserves full text.
- **Watchlist VM extension (if included).** Verify the watchlist template renders correctly when active_recommendations is empty (existing behavior preserved).
- **Base-layout VM gotcha avoidance.** Verify `active_recommendations` is NOT referenced in `base.html.j2`; it's a section-specific field, not a base-layout field.

---

## 6. Done criteria

- All task commits landed.
- Dashboard renders the new "Hypothesis-driven recommendations" section when candidates have active hypothesis matches.
- Tripwire-fired hypothesis is visually distinguished.
- `swing trade entry --ticker XYZ` pre-fills `--hypothesis` for tickers with active recommendations; explicit `--hypothesis` overrides; no recommendation = no pre-fill.
- Adversarial review verdict `NO_NEW_CRITICAL_MAJOR`.
- Fast suite green; trust pytest output.
- Return report per §7.

---

## 7. Return report format

```
## Hypothesis recommendation frontend (Session 2) — return report

### Commits landed
- <SHA1> feat(web): dashboard active hypothesis recommendations
- <SHA2> feat(web): dashboard template renders hypothesis recommendations
- <SHA3> feat(cli): trade entry pre-fills hypothesis from active recommendation
- <SHA4> (if included) feat(web): watchlist active hypothesis recommendations
- <SHA5+> (if any) adversarial review fixes

### Tests
- Before: <baseline>
- After: <N>, 0 failing. New tests: <count>.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary>

### Verification
- Dashboard rendered with active recommendations section: <description; or "no recommendations on current data" if applicable>
- CLI pre-fill behavior verified: <description of test runs>
- Tripwire visual indication verified: <description>

### Deviations from brief
- <Empty if none. Includes whether watchlist VM was extended.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 8. If you get stuck

- **If the dashboard's existing structure makes inserting a new section difficult** (e.g., HTMX partials are involved per CLAUDE.md HTMX OOB-swap gotcha): place the new section at the bottom of the main content area, full-page-rendered only. Don't try to do OOB-swap for the recommendations panel in this brief — defer that to a future session if needed.
- **If `swing trade entry` is highly interactive (prompts for many fields)**: pre-fill the hypothesis as one of those interactive prompts' default values; the operator can accept or edit. Match the existing prompt pattern.
- **If the latest pipeline_run's evaluation_run has zero recommendations** (no candidate matches any active hypothesis): the dashboard section gracefully renders empty (or the `{% if %}` guard hides it entirely). Document the choice in the return report.
- **If Session 1 (backend) is not yet landed when this brief's session is starting**: STOP. Verify that `swing/recommendations/hypothesis.py` exists and exports `match_candidate_to_hypotheses` + `prioritize_recommendations`; verify migration 0008 has been applied (`SELECT version FROM schema_version` returns ≥ 8). If either is missing, this brief is being dispatched out of order — return immediately.
