# Post-QoL-Bundles Housekeeping Brief

**Audience:** Fresh Claude Code instance with no prior conversation context. You are the implementer; the orchestrator drafted this brief and will receive your return report.

**Mission:** Capture the documentation, backlog, lesson, and state-tracking debt that accumulated across the QoL UI-polish bundle (Session 1) and the watchlist sort-by-tags session (Session 2). One small commit (or a small handful) updates `docs/phase3e-todo.md`, `docs/orchestrator-context.md`, and the memory file `feedback_regression_test_arithmetic.md`. No code changes; no adversarial review.

**Expected duration:** ~30–60 minutes.

---

## §0 — Read first

1. **`docs/orchestrator-context.md`** in full — you'll be appending to multiple sections. Notice the existing date-stamped pattern `(2026-04-25) ...` for the Recent-decisions and Lessons sections; mirror it.
2. **`docs/phase3e-todo.md`** in full — particularly the existing follow-up sections grouped by date/source. You'll be adding a new section for 2026-04-26.
3. **`C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\feedback_regression_test_arithmetic.md`** — read to understand the current scope of the lesson; you'll be extending it.
4. **The two source briefs** for this string (already on `main`):
   - `docs/qol-ui-polish-bundle-brief.md` — what Session 1 did
   - `docs/watchlist-sort-by-tags-brief.md` — what Session 2 did

## §0 — Skill posture

- **No skills to invoke.** This is pure documentation housekeeping.
- No TDD; no adversarial review; no copowers; no superpowers.
- Single small commit (or up to 3 if it makes the diff cleaner) per conventional-commits style.

---

## What landed during this string (factual record for orientation)

**Session 1 — QoL UI-polish bundle** (commits `4c264b2..d9603c9` + adversarial fixes `61424f2`, `20ecc70`, `d9ab7ff`):
- T1: alternating row backgrounds CSS
- T2: removed stale "Log entry (CLI — 3b adds button)" placeholder
- T3: pivot price column in hypothesis-recommendations table
- T4: unrealized P&L line on Account card
- T5: `POST /prices/refresh` also resets OHLCV breaker
- T6: close button to collapse expanded watchlist row
- T7: `_handle_any` HX-Target-aware fragment selection (Bug 2 defense-in-depth — SHIPPED)

Adversarial review reached `NO_NEW_CRITICAL_MAJOR` after R3. Manual verification by operator: T1, T2, T6 all pass.

**Session 2 — Watchlist sort-by-tags** (commits `1d6ed42..e613f39`):
- 4-key composite sort: tag count DESC → tag precedence DESC → abs(% to pivot) ASC → ticker ASC
- Tag precedence: `{"A+": 4, "VCP✓": 2, "TT✓": 1}` summed across row tags
- Applied to `build_dashboard` top-5, `build_watchlist`, AND `/prices/refresh` cache-prewarm top-5
- **`/prices/refresh` anchor fix as side benefit:** route was using `MAX(run_ts) FROM evaluation_runs` (pre-Tranche-C mixed-anchor behavior); now uses pipeline-eval-first like `build_watchlist`. Closes an additional Bug-7-class surface incidentally.
- R4 caught a vacuous test the implementer's R3 fix had introduced — discipline lesson recorded below.

Adversarial review reached `NO_NEW_CRITICAL_MAJOR` after R5.

**Final state:** 1002 fast tests passing (974 baseline + 14 Session 1 + 14 Session 2). Working tree clean. 16 unpushed commits on `main`.

---

## Tasks

### T1 — Update `docs/phase3e-todo.md`

Add a new section for 2026-04-26 follow-ups. Use the existing per-date section pattern (e.g., the `## 2026-04-25 Bug 1 follow-ups` and `## 2026-04-25 hypothesis-engine + analyze + backup follow-ups` sections as templates).

**Section title:** `## 2026-04-26 QoL bundle + watchlist sort follow-ups`

**Items to capture (7 total, plus 1 closure):**

1. **Bug 2 `_handle_any` HX-Target-awareness — SHIPPED 2026-04-26.** Add a strikethrough or "DONE" annotation to the existing 2026-04-25 Bug 2 follow-up entry that listed this as backlog. Cross-reference commit `d9603c9`.

2. **Target-family-aware error fragments (Session 1 R1 Major 2 — accepted, not fixed).** `partials/trade_form_error.html.j2` hardcodes `colspan="8"`; watchlist row tables use 7 cells. Affects both `_handle_any` (T7 just shipped) and `_handle_http_exc` (pre-existing) symmetrically. Browsers tolerate `colspan` greater than column count, so functionally non-blocking; structural correctness would pick a fragment per `_ROW_TARGET_PREFIXES` family.

3. **Alternating-row CSS scoping (Session 1 R1 Minor 2 — accepted with rationale).** Global `tbody tr:nth-child(even) td` rule may bleed striping into future tables that don't want it. Currently relies on source-order vs `tr.tripwire-fired`. If a future class needs to override, increase its specificity (e.g., `tr.expanded > td`) or scope the alternating rule to specific tables (`#open-positions tbody tr:nth-child(even) td`). Operator manually verified that `tr.expanded` rows currently inherit the underlying stripe color naturally — no awkward mid-table jump.

4. **`build_watchlist_row` single-ticker performance (Session 1 R2 Minor 1 — accepted with rationale).** `swing/web/view_models/watchlist.py:build_watchlist_row` scans the full active watchlist and full candidates list to render one row. Acceptable today; **trigger threshold: watchlist > ~100 rows**, at which point add a single-ticker variant of `list_active_watchlist`.

5. **Close-button server-round-trip failure model (Session 1 R2 Major 1 — accepted with rationale per Option-A spec).** A transient backend failure on `/watchlist/<ticker>/row` (collapse) can leave the row temporarily stuck expanded or replaced with an error fragment. Identical failure model to `/expand`. If operator-visible failures occur, evaluate Option B (client-side stash + collapse via cached compact-row HTML).

6. **Centralize eval-anchor resolver (Session 2 R2 Minor 3 — accepted, out of scope).** The same ~10-line `pipeline_runs.evaluation_run_id`-with-fallback block now lives in three places: `swing/web/view_models/dashboard.py:73-86` (already factored as `latest_evaluation_run_id`), `swing/web/view_models/watchlist.py:59-66`, and `swing/web/routes/pipeline.py` `/prices/refresh` route. The dashboard module already exports `latest_evaluation_run_id`; the other two sites should consume it. ~30-min DRY refactor.

7. **Extract `swing/web/watchlist_ranking.py` module (Session 2 R1 Minor 1 — accepted, out of scope).** `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, and `_flag_tags` currently live in `swing/web/view_models/dashboard.py` and are imported from `watchlist.py` and `routes/pipeline.py`. Module extraction would clarify ownership; minor cleanup.

8. **Decouple `_TAG_PRECEDENCE` from UI label strings (Session 2 R1 Minor 3 — accepted, out of scope).** `_TAG_PRECEDENCE` is keyed on the same presentation strings (`"TT✓"`, `"VCP✓"`, `"A+"`) that templates render. A future label rename would silently zero out precedence (unknown keys score 0). Decoupling: introduce a tag-id enum or constants like `TAG_TT_PASS = "TT✓"` referenced from both the precedence map and the templates. Not urgent; current state is correct.

### T2 — Update `docs/orchestrator-context.md`

Make four updates, all small. Mirror the existing date-stamped pattern (`(2026-04-25) ...`).

**Update A — "Currently in-flight work" section:** Replace the existing block with:

> **As of 2026-04-26 (post-QoL bundles + watchlist sort):**
>
> The QoL UI-polish bundle (Session 1, 2026-04-25) and watchlist sort-by-tags (Session 2, 2026-04-26) shipped. Cumulative test count: **1002 passing, 0 failing** as of `e613f39`.
>
> **Session 1 highlights:** alternating row backgrounds; pivot column in hyp-recs; unrealized P&L on Account card; OHLCV breaker reset on `/prices/refresh`; watchlist row collapse via close button; Bug 2 `_handle_any` defense-in-depth.
>
> **Session 2 highlights:** four-key composite watchlist sort (count → precedence → proximity → ticker) replaces pure-proximity; tag precedence `A+ > VCP✓ > TT✓`. Applied uniformly to dashboard top-5, standalone `/watchlist`, and `/prices/refresh` cache-prewarm top-5. Incidentally closed a Bug-7-class mixed-anchor inconsistency on `/prices/refresh` that was using `MAX(run_ts) FROM evaluation_runs` while siblings used pipeline-eval-first.
>
> **No work currently in flight.** Plugin update for claude-mem to v12.4.7 is queued (operator-deferred until current work string finished). All queued follow-ups in `docs/phase3e-todo.md`.

**Update B — "Recent decisions and framings" section:** Append two bullets at the end (preserve existing chronological-ish order; just add to the bottom).

> - **(2026-04-26) Watchlist sort uses four-key composite ordering.** Sort key: tag count DESC → tag precedence DESC (`A+`=4, `VCP✓`=2, `TT✓`=1, summed) → abs(% to pivot) ASC → ticker ASC for determinism. Hypothesis-recommendations table sort untouched per scope discipline (its existing prioritizer is hypothesis-aware: progress, target distance, tripwire). Operator decision recorded; revisit hyp-recs sort separately if needed.
> - **(2026-04-26) `/prices/refresh` anchor consistency closed Bug-7 family in this layer.** The route's cache-prewarm path was using `MAX(run_ts) FROM evaluation_runs` (the pre-Tranche-C mixed-anchor pattern) while `build_dashboard` and `build_watchlist` use pipeline-eval-first via `latest_evaluation_run_id`. Session 2 R1 caught the divergence as part of sort-anchor consistency review; the route now consumes the same pipeline-eval-first anchor. Survey query (`grep -rn 'MAX(run_ts) FROM evaluation_runs' swing/web/`) confirms no remaining occurrences in the web layer. Class durably closed.

**Update C — "Lessons captured" section:** Append one new bullet at the end.

> - **Compounding-confound test fixtures can pass despite a vacuous primary discriminator.** Session 2 R4 caught a precedence-surface test that arithmetic-on-paper distinguished pre-fix from post-fix on the precedence key, but two independent confounds masked the bug: (a) `monkeypatch` targeted `dashboard._flag_tags` instead of `watchlist._flag_tags` (the bound reference imported transitively into watchlist module), and (b) ticker names were alphabetically aligned with precedence ordering, so the alphabetical tiebreaker re-ordered the result back into pre-fix-equivalent shape. Generalization beyond the existing `feedback_regression_test_arithmetic.md` discipline: when a test asserts on a primary key, **empirically verify the discriminator by temporarily disabling the keyed-on element and re-running the test** — if it still passes, the test is vacuous despite arithmetic that "should" distinguish. Verified-empirically supplements asserted-arithmetic. Memory file extended in this housekeeping commit.

**Update D — "Last updated" line at top:** Change the date string to:

> **Last updated:** 2026-04-26 (post-QoL bundles + watchlist sort housekeeping)

### T3 — Extend `feedback_regression_test_arithmetic.md`

Read the current memory file first. Then append a section (preserve the existing front-matter and primary discipline; just add a new section below it) titled "Compounding-confound failure mode" or similar. Capture:

- The failure mode: a test's primary discriminator can be re-masked by a secondary sort/ordering element in the same fixture, producing a vacuous test that arithmetic-on-paper still claims to distinguish.
- The compounding multiplier: bound-reference confusion (monkeypatching a name imported transitively into a different module) makes the failure mode harder to spot, because the test "runs without error" but the patched function is never the one actually called.
- The discipline: **empirically verify the keyed-on element**. Temporarily disable the element under test (e.g., comment out the precedence sort key, set the tag-precedence map to all-zero, etc.) and re-run the test. If it still passes, it's vacuous.
- The canonical example: Session 2 R4 (2026-04-26) caught a precedence-surface test in commit `c7da628` whose monkeypatch targeted `dashboard._flag_tags` instead of `watchlist._flag_tags`, and whose ticker names were alphabetically aligned with precedence ordering. Fixed in `e613f39` with patched bound name + anti-aligned tickers (`ZHIGH` score 5 vs `AAALOW` score 3).

Update the front-matter `description` to reflect the broader scope. Don't change `name` or `type`.

### T4 — Single commit (or up to 3 small ones)

Conventional commits, no Claude footer, no `--no-verify`, no amends. Suggested message:

```
docs: post-QoL-bundles housekeeping — backlog capture, decisions, lessons

- docs/phase3e-todo.md: 7 new backlog items + Bug 2 _handle_any closure
- docs/orchestrator-context.md: in-flight reset, two new framings,
  compounding-confound test lesson, last-updated bump
- memory/feedback_regression_test_arithmetic.md: extend with
  compounding-confound failure mode + empirical-verification discipline
```

If you prefer one commit per file (3 commits), that's also acceptable — operator readability over commit count.

---

## Done criteria

- `docs/phase3e-todo.md` has the new 2026-04-26 section with 7 items and the Bug 2 `_handle_any` closure annotation.
- `docs/orchestrator-context.md` has updates A, B, C, D applied.
- `feedback_regression_test_arithmetic.md` extended with the compounding-confound section + updated description.
- Working tree clean after commit(s).
- Fast suite still passes (1002 expected) — sanity-check with `python -m pytest -m "not slow" -q | tail -3`.

---

## Return report format

```
## Post-QoL-Bundles Housekeeping Return Report

### Commits
- <sha>: <conventional commit title>

### Files updated
- docs/phase3e-todo.md: [summary]
- docs/orchestrator-context.md: [summary]
- ~/.claude/projects/.../memory/feedback_regression_test_arithmetic.md: [summary]

### Test count
1002 passing, 0 failing (no code changes; sanity-checked).

### Anything noticed but not fixed
[Anything outside the brief's scope you noticed.]
```

---

## If you get stuck

- **Existing section in `phase3e-todo.md` doesn't follow the pattern you expected:** mirror the most recent existing section's structure rather than the brief's prescription. The brief is the intent; existing structure is the format.
- **Memory file front-matter is unfamiliar:** the auto-memory system uses a `name`/`description`/`type` triplet. Read the existing front-matter and preserve `name` + `type`; only update `description` if you broaden the scope.
- **Unsure whether something is housekeeping or a new lesson:** if it's a new framing or rule the operator hasn't yet endorsed, flag in return report rather than capture. The lessons section is for things that have been demonstrated, not aspirations.
