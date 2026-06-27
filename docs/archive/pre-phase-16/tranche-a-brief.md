# Tranche A — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Ship a hotfix + strategy-adoption tranche on `main`. Four distinct commits.
**Expected duration:** One working session.
**Prepared:** 2026-04-23 by orchestrator instance.

---

## 0. Read first

Before starting any task:

1. Read `CLAUDE.md` in the project root. It is the authoritative current-state doc. The invariants, conventions, and gotchas there are binding. Note especially the Phase isolation rule and the conventional-commits rule with no Claude co-author footer.
2. Read `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.md` (proposal v2) and `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` (binding clarifications). These govern all strategic work.
3. Read `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2-addendum.md`. This is the source of three additions that Task 1 splices into V2.
4. Read `docs/Bugs.txt` for the original bug reports. Tranche A covers Bugs 1, 2, and part of 3.

You do **not** need to read the older critique/proposal/revised-proposal files in `reference/Future Work/`. Task 2 archives them.

**Skill posture for this tranche.** Do NOT invoke the `copowers:*` wrapper skills (`copowers:using-copowers`, `copowers:brainstorming`, `copowers:writing-plans`, `copowers:executing-plans`). The brainstorm and plan phases were completed by the orchestrator session that produced this brief; this brief IS the plan artifact, already adversarially reviewed through that conversation. Execute directly against it. Other skills — including the `superpowers` TDD, debugging, and verification-before-completion skills — remain available as normal; invoke whichever fit the moment. Tranche B will re-introduce the copowers wrapper for genuine new design work.

---

## 1. Strategic context (compressed)

The project is in a strategy-revision phase. The governing frame is a **bifurcated architecture**: a Research & Verification branch (for method validation) and an Operational Trader-Facing branch (for daily use), built on a minimum-viable shared foundation. V2 is the governing strategy document. The rebuttal-response adds binding clarifications (minimum viable governance, toleranced parity, bootstrap-first data strategy). An addendum proposes three optional additions that the orchestrator accepted. V2.1 merges those additions into V2 in place.

**Immediate posture:** do not overbuild. The rebuttal-response anti-pattern list (§Anti-patterns to avoid) is binding — strategy inflation, registry maximalism, infrastructure displacement, parity absolutism. Apply that posture to every decision in this session.

**This tranche is a hotfix + strategy-baseline commit.** It does NOT begin research-branch work, ops-branch feature work, or any new subsystems. Those are Tranche B.

---

## 2. Tranche A scope

### In scope (exactly six artifacts, four commits)

| # | Artifact | Kind |
|---|----------|------|
| T1 | V2.1 merge — splice three addendum additions into the V2 proposal | Docs |
| T2 | Archive superseded Future Work files | Docs |
| T3 | Minimal CLAUDE.md strategy pointer | Docs |
| T4 | Bug 2 fix — trail-MA precision (sub-cent threshold) | Code |
| T5 | Bug 1 fix — dashboard refresh-now layout regression | Code |
| T6 | Bug 3b — `StopAdjustRequest.notes` data-model gap | Code + migration |

### Explicitly out of scope — do NOT do these in this session

- **Bug 3a** (structured rationale dropdown taxonomy). This is Tranche B; it requires a design phase the orchestrator scopes separately. Leave the existing free-text rationale field intact.
- **Bug 4** (chart-unavailable reason). Tranche B alongside B2 trigger/setup UX work.
- **Bug 5** (A+ entry stop-limit showing stop but not limit). Tranche B B2 work.
- **Bug 6** (total risk exposure display). Tranche B B3 work.
- Any audit of current production evaluation code against `reference/methodology/minervini-trend-template.md`. Deferred — reference material only.
- Any research-branch scaffolding, method-record location, or earnings-proximity study artifacts. Tranche B-research.
- Any rewrite, restructure, or substantial expansion of CLAUDE.md beyond the one minimal pointer in T3.
- Any new subsystem, abstraction, utility, or refactor beyond what T4/T5/T6 strictly require.

If during investigation you find a tempting adjacent cleanup, **resist it and flag it in the return report**. Tranche A is a discipline exercise as much as a delivery exercise.

---

## 3. Binding conventions (from CLAUDE.md — re-stated for emphasis)

- **Branch:** all work on `main`. No feature branches.
- **Commits:** conventional-commits style (`fix(web): …`, `feat(data): …`, `docs(strategy): …`). **No Claude co-author footer.** **No `--no-verify`.** **No amending.** If a pre-commit hook fails, fix the underlying issue and create a new commit.
- **TDD:** write failing test → see it fail → minimal implementation → see it pass → commit. One test-then-impl cycle per logical change. Tranche A's code tasks each have specific regression-test requirements listed below.
- **Tests:** fast suite (`python -m pytest -m "not slow" -q`) must remain green. Current baseline is 504 passing tests; Tranche A will add tests, so the target after this session is ≥504 + new-test-count, with zero failures.
- **Ruff:** `ruff check swing/` must not introduce new violations. Do not spend time fixing pre-existing ones (CLAUDE.md notes 81 pre-existing errors; ignore).
- **Phase isolation carve-out:** CLAUDE.md's Phase isolation rule ("during Phase 3 work, `swing/trades/` and `swing/data/` are consumed read-only unless the current-phase spec explicitly scopes a carve-out") is hereby **carved out for this tranche** for: `swing/trades/advisory.py` (Bug 2), `swing/trades/stop_adjust.py` (Bug 3b), `swing/data/migrations/0005_*.sql` (Bug 3b), and `swing/data/repos/trades.py` (Bug 3b). The carve-out justification is "bugfix of existing operational defects + corresponding schema extension." Update CLAUDE.md's carve-out list in T3 if you like, but it is not required for Tranche A.

---

## 4. Task specifications

### T1 — V2.1 merge (docs)

**File to modify:** `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.md`

**Rename to:** `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`

(Use `git mv` for the rename. Update the `**Supersedes:**` frontmatter to add the addendum. Update header to `# Bifurcated Strategic Implementation Proposal for the Swing Trading Tool — V2.1`.)

**Three insertions, taken verbatim from the addendum. Do not reword.**

**Insertion 1 — Addendum Addition 3 (Time-budget anchor):** Insert as a new numbered principle in V2 §III ("Governing design principles") immediately after principle 6 ("Preserve operator explainability"):

```markdown
### 7. Calibrate scope to time-budget reality

This project is developed part-time by a single developer with significant competing commitments. Sustained developer attention should be assumed at **4–8 hours per week averaged over a year**, split roughly 70/30 production/research during near-term work.

Implications:

- Methods requiring more than a calendar month of evening work to validate should be questioned — they are likely either over-specified or better deferred.
- Registry discipline is leverage when time is short, not overhead. The minimum-viable posture (V2 §IV, §IX) is correct partly for this reason.
- A month with zero research progress is not a failure signal. A quarter with zero progress is.
```

**Insertion 2 — Addendum Addition 1 (Demotion pathway):** Insert as a new subsection in V2 §VII ("Interaction model between the branches") immediately after §VII.D ("Rejection is a first-class outcome"):

```markdown
### E. Demotion pathway

Demotion is symmetric to promotion and reuses the existing lifecycle states (V2 §IV.B). Three pathways:

- **Demotion to shadow** — a production method whose challenger outperforms in shadow mode for a defined evaluation window (default: ≥6 months and ≥30 trade signals) has its primary/shadow flag flipped. The challenger becomes primary; the incumbent continues running in shadow.
- **Deprecation** — a production method with a validated superior replacement is marked `deprecated` for a transition window (default 30 days), then `retired`.
- **Emergency demotion** — a production method that produces a defined-severity operational failure may have its primary/shadow flag flipped to shadow by direct action, with the method record updated in the same commit and a research-branch review queued.
```

**Insertion 3 — Addendum Addition 2 (Source-of-truth correction protocol):** Insert as a new subsection in V2 §VII immediately after the new §VII.E:

```markdown
### F. Source-of-truth corrections

When a primary source (a book, paper, or definitive publication) is acquired that corrects or refines a method currently implemented based on an approximation, the correction is handled as a standard research-to-promotion cycle, not as a hotfix:

1. The correction is filed as a new method-record version.
2. The corrected method enters research-branch validation against the same evidence standard as any new method (V2 §V.F).
3. If validated, it enters shadow mode in production alongside the approximation.
4. If shadow evidence supports the correction, the approximation is deprecated via the standard demotion pathway.

Source-of-truth corrections often turn out on investigation to be (a) misremembered, (b) ambiguously specified in the source, or (c) context-dependent in a way the approximation accidentally captures. Treating them as hotfixes imports that uncertainty directly into production.
```

**After these three insertions**, at the bottom of the V2.1 file (before the final instruction section), add a short **V2 → V2.1 changelog** block:

```markdown
---

## V2 → V2.1 changelog

- Added §III principle 7 (time-budget anchor) from addendum Addition 3.
- Added §VII.E (demotion pathway) from addendum Addition 1.
- Added §VII.F (source-of-truth correction protocol) from addendum Addition 2.
- No other semantic changes. Existing §III principles 1–6 and §VII.A–D preserved verbatim.
- First concrete source-of-truth correction artifact: `reference/methodology/minervini-trend-template.md` (Trend Template criteria 1–8 as printed on p. 79 of *Trade Like a Stock Market Wizard*, transcribed 2026-04-23).
```

### T2 — Archive superseded Future Work files

Move the following into `reference/Future Work/archive/` (create the subdirectory):

- `Extending methodological basis.md`
- `2026-04-22-bifurcated-strategic-implementation-proposal.md`
- `2026-04-22-formal-critique-extending-methodological-basis.md`
- `2026-04-23-bifurcated-strategic-implementation-proposal-revised.md`
- `2026-04-23-bifurcated-strategic-implementation-proposal-v2-addendum.md` (superseded by the in-place merge into V2.1)

**Keep in place (not archived):**

- `2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` (the newly renamed V2.1)
- `2026-04-23-rebuttal-response-for-implementors.md` (still-binding clarifications)
- `2026-04-22-rebuttal-critique-and-implementation-proposal.md` (still-useful historical record of the revision; per addendum §"On Decision 3", certain findings retain operational value)

Use `git mv` for each move (preserves history).

Add `reference/Future Work/archive/README.md` with a short note:

```markdown
# Archived strategy documents

Superseded by `../2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`.

Preserved for historical context. Do not use as governing documents. If a future session needs content from these files, extract it explicitly and file it in active strategy documents.
```

### T3 — Minimal CLAUDE.md strategy pointer

Add a single new section to CLAUDE.md titled `## Strategy`, placed immediately after the `## Quick Start` section (before `## Architecture`).

Content (exactly this; do not expand):

```markdown
## Strategy

The project follows a bifurcated architecture (research branch + operational trader-facing branch) per:

- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` — governing strategy.
- `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` — binding clarifications (minimum viable governance, toleranced parity, bootstrap-first data).

Source-of-truth methodology references live in `reference/methodology/`. These are reference-only; any production change driven by a methodology reference must route through the source-of-truth correction protocol (V2.1 §VII.F), not a direct patch.

Older strategy documents are archived at `reference/Future Work/archive/`.
```

Do not edit any other section of CLAUDE.md in this commit.

### Commit 1 (T1 + T2 + T3)

All three doc tasks ship as one commit.

Message: `docs(strategy): adopt V2.1 and archive superseded strategy documents`

Body:

```
Merge addendum additions 1, 2, 3 into V2 producing V2.1:
- §III principle 7 (time-budget anchor)
- §VII.E (demotion pathway)
- §VII.F (source-of-truth correction protocol)

Archive superseded critique/proposal/revised-proposal/addendum files
under reference/Future Work/archive/.

Add minimal Strategy section to CLAUDE.md pointing at V2.1 and the
rebuttal-response as governing documents.
```

### T4 — Bug 2: trail-MA precision fix (code)

**Bug description (from dashboard observation):** A user acts on a trail-MA advisory ("Trail stop up to $10.30 — 0.3% below 10MA ($10.33)"), adjusts `current_stop` to the displayed target ($10.30), and the advisory persists on next render.

**Root cause:** In [swing/trades/advisory.py:45-57](swing/trades/advisory.py#L45-L57), `suggest_trail_ma` computes `proposed = ma_value * (1 - buffer_pct / 100)` at full float precision but displays via `.2f`. The extinction check `proposed <= trade.current_stop` then compares the full-precision proposed (e.g. `10.303`) against a cent-precision stop (e.g. `10.30`). When `ma_value` falls in the window that rounds-down to its displayed `.2f` value, the actual threshold exceeds the displayed target — user sets stop to displayed target, rule correctly but unhelpfully continues to fire.

**Fix:** Ceiling-round `proposed` to the cent at computation time so the displayed target equals the actual extinction threshold.

```python
# at top of file
import math

# inside suggest_trail_ma, replacing the proposed line:
proposed = math.ceil(ma_value * (1 - buffer_pct / 100) * 100) / 100
```

Use `math.ceil` (not `round` — banker's rounding can round *down* and create the same bug in the other direction).

No change needed to `suggest_breakeven` — `trade.entry_price` is stored at cent precision from entry, so its comparison is already exact. No change needed to `suggest_exit_close_below_ma` — it doesn't produce a user-actionable stop target.

**Required regression test** (new test in `tests/trades/test_advisory.py` or wherever the existing advisory tests live):

```python
def test_trail_ma_extinguishes_when_stop_meets_displayed_target():
    """Bug 2 regression: displayed target must equal actual extinction threshold."""
    # ma_value chosen so that raw proposed = 10.334 * 0.997 = 10.302998,
    # which .2f-displays as "$10.30" pre-fix and as "$10.31" post-fix (ceiling).
    # Pre-fix: user sets stop to displayed "$10.30", advisory persists (proposed=10.303 > 10.30).
    # Post-fix: user sets stop to displayed "$10.31", advisory extinguishes (proposed=10.31 <= 10.31).
    trade = _make_trade(current_stop=10.31, entry_price=9.50)
    ctx = _make_ctx(current_price=11.00, sma10=10.334, ...)
    result = suggest_trail_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA", buffer_pct=0.3)
    assert result is None, "advisory should extinguish when stop meets displayed target"
```

You will need to look at existing advisory test fixtures (`tests/trades/test_advisory.py` or similar) to match the existing helper patterns. Use whatever constructor helpers the existing tests use; do not invent a new fixture harness.

Also add a test covering the original-bug direction: stop at `10.30`, same ma_value, advisory **does** fire — documenting that the pre-fix bug scenario is correctly handled by the new threshold.

**Verify with full-suite run** after the fix:

```bash
python -m pytest -m "not slow" -q
```

Must be all green.

### Commit 2 (T4)

Message: `fix(trades): ceiling trail-MA proposed to cent so displayed target extinguishes advisory`

### T5 — Bug 1: dashboard refresh-now layout regression (code)

**Bug description:** Clicking "Refresh now" on the dashboard causes the "Watchlist — near trigger" label to disappear; the watchlist table then butts up against the Open Positions table above it. A hard browser refresh restores the layout.

**Hypothesis (not verified — investigate):** the refresh-now endpoint returns an HTMX partial that omits a wrapper element carrying the label. The full-page render includes the label inside that wrapper; the partial substitutes only the table contents, losing the label.

**Investigation steps:**

1. Find the refresh-now route handler (likely in `swing/web/routes/` — grep for `refresh` or `"/refresh"`).
2. Identify what partial it returns.
3. Compare the partial template against the full-page template's structure around the "Watchlist — near trigger" heading.
4. Identify whether the label lives inside the swapped target or outside it.

**Likely fix shapes:**

- If the label is outside the HTMX swap target: change the `hx-target` or `hx-swap` to include the label element, OR expand the returned partial to include the label.
- If the partial template is missing the label entirely: add it back.

**Required regression test:** look at `tests/web/` for an existing dashboard-test pattern. Add a test asserting the refresh-now endpoint's response body contains the "Watchlist — near trigger" (or equivalent) label text when the watchlist has near-trigger entries. Use whatever `TestClient` pattern the existing tests use (note CLAUDE.md: `with TestClient(app) as client:` context manager is required when `app.state.price_fetch_executor` is touched).

**Important:** the brief's hypothesis may be wrong. If investigation reveals a different root cause, **fix the actual cause, not the hypothesis**. Flag any divergence in the return report.

### Commit 3 (T5)

Message: `fix(web): preserve "Watchlist — near trigger" label on refresh-now partial`

(adjust wording if the root cause is different)

### T6 — Bug 3b: stop-adjust `notes` field (code + migration)

**Gap:** `EntryRequest` and `ExitRequest` both carry a `notes: str | None` field; `StopAdjustRequest` does not. Users currently have no way to attach free-form context to a stop adjustment. The `trade_events` audit table also lacks a `notes` column; it has only `payload_json` and `rationale`.

**Scope:**

1. **New migration** `swing/data/migrations/0005_trade_events_notes.sql`:
   ```sql
   ALTER TABLE trade_events ADD COLUMN notes TEXT;
   ```
   Follow the style of existing migration files (look at `0004`). Ensure the migration runner picks it up.

2. **Update** `swing/trades/stop_adjust.py`:
   - Add `notes: str | None = None` to `StopAdjustRequest` (keep default `None` so existing callers don't break).
   - Pass `notes` through to `update_stop_with_event`.

3. **Update** `swing/data/repos/trades.py`:
   - `update_stop_with_event` signature gains `notes: str | None = None`.
   - Insert the notes value into `trade_events.notes`.
   - Check whether `insert_trade_with_event` and `insert_exit_with_event` also take a `notes` parameter and whether they should write to the new column. **If they currently store notes on the entity row only (trades.notes / exits.notes), do NOT change them** — that asymmetry is pre-existing and out of scope. Only stop-adjust gains event-level notes.

4. **Update** `swing/cli.py`:
   - Add `--notes` option to `trade_stop_adjust_cmd` (mirroring how `--notes` exists on `trade_entry` and `trade_exit` — copy that pattern exactly).
   - Pass through to `StopAdjustRequest`.

5. **Update** `swing/web/templates/partials/trade_stop_form.html.j2`:
   - Add a `<textarea name="notes">` input, styled consistently with the entry/exit forms' notes fields.

6. **Update** `swing/web/routes/trades.py`:
   - Wherever the stop-adjust POST handler builds `StopAdjustRequest`, pull `notes` from the form payload.

7. **Update** `swing/web/view_models/trades.py` if the stop-adjust form VM currently doesn't carry a notes field (check first; add only if needed).

**Required tests:**

- **Migration test** or repo-layer test: insert a trade_event with `notes="test note"`, read it back, assert round-trip.
- **`adjust_stop` service test**: pass `notes="foo"` through `StopAdjustRequest`, assert `trade_events.notes == "foo"` after the call.
- **CLI test**: `trade stop-adjust --rationale "..." --notes "..."` writes both fields.
- **Web route test**: POST to stop-adjust endpoint with notes field in form payload, assert persistence.

Follow existing test file organization — do not invent new directories.

**Test-suite check:** `python -m pytest -m "not slow" -q` must stay green.

### Commit 4 (T6)

Message: `feat(trades): add notes field to stop-adjust (parity with entry/exit)`

(Even though originally reported as a bug, this is adding a new capability — `feat` is correct per conventional commits.)

---

## 5. Commit sequencing and expected order

1. `docs(strategy): …` — T1 + T2 + T3 together. Pure documentation. No test impact.
2. `fix(trades): ceiling trail-MA proposed to cent …` — T4. One file change in `swing/trades/advisory.py` + regression tests.
3. `fix(web): preserve "Watchlist — near trigger" label …` — T5. Web layer only. Message wording depends on investigation outcome.
4. `feat(trades): add notes field to stop-adjust …` — T6. Cross-layer change: migration + service + repo + CLI + template + route.

Run `python -m pytest -m "not slow" -q` and `ruff check swing/` after each commit. Fast suite must stay green throughout.

---

## 6. Done criteria

A Tranche A session is complete when:

- All four commits are on `main`.
- Fast test suite passes with no failures.
- No new ruff violations introduced in `swing/`.
- Each commit follows the message convention (no Claude co-author, no `--no-verify`, no amending).
- The return report (next section) is produced.

---

## 7. Return report format

At the end of the session, produce a short report in this form:

```
## Tranche A return report

### Commits landed
- <SHA> docs(strategy): ...
- <SHA> fix(trades): ...
- <SHA> fix(web): ...
- <SHA> feat(trades): ...

### Tests
- Before: 504 passing, 0 failing (fast suite).
- After: <N> passing, 0 failing. New tests: <M>.

### Deviations from brief
<Anything you did differently from the brief, and why. Empty if none.>

### Bug 1 root cause (actual, not hypothesis)
<What the refresh-now regression turned out to be.>

### Items flagged but not done (scope discipline)
<Any adjacent cleanup, refactor, or fix you noticed but deliberately did not touch. Orchestrator triages these into Tranche B or backlog.>

### Open questions for orchestrator
<Anything the brief under-specified or where you had to make a judgment call. Empty if none.>
```

---

## 8. If you get stuck

- If a test fixture helper you need doesn't exist, use the same patterns existing tests use. Do not invent new harness infrastructure.
- If Bug 1's root cause is genuinely different from the hypothesis, fix the actual cause and document the divergence in the return report.
- If the Phase isolation carve-out for T6 feels over-broad (e.g., you need to touch an additional file in `swing/trades/` or `swing/data/`), note it in the return report and proceed — the spirit of the carve-out is "Bug 3b implementation minimum," not "exactly this file list."
- If the fast suite breaks in a way your change doesn't obviously cause, stop and investigate before committing. Do not work around it with skips or broad excepts.
- If you find yourself considering work outside the six scoped artifacts, stop and flag it in the return report. That is the scope-discipline test this tranche is designed to exercise.
