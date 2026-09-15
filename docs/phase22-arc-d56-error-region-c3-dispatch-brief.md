# Phase 22 — D56: the pattern-review and exemplars forms keep their controls on an error (+ C3, the DBW trough-1 pre-fill)

**Audience:** a dispatched implementer cell with no prior context. Read `docs/implementer-dispatch-recipe.md` and `CLAUDE.md` in full first; this brief is the task, the recipe is the protocol.
**Author:** orchestrator, 2026-09-15. **Commissioned:** CHARC register D56 (`637d12fc`, citation corrected `ac3f6a80`); the operator's "commence D56". **Design RULED:** CHARC round-0 ruling, block-quoted in [`docs/phase22-arc-d56-ledger.md`](phase22-arc-d56-ledger.md) §"Round-0 RULING" — that quote is binding; this brief encodes it and never overrides it.
**Cell:** `implementer-sonnet-high` (locked design; template + tests + one route helper). **Reviewer A:** you, `strong` tier, to convergence. **Reviewer B:** REQUIRED, run by the ORCHESTRATOR at its gate over your finished tree — not by you.
**Worktree:** `.worktrees/d56-exec`, branch `d56-exec`, base = the commit that carries this brief (the orchestrator creates it and names the SHA in the dispatch message).
**Tripwires (harness §5):** none crossed — no schema, no migration, no new module, no dependency, no `swing/data`/`swing/trades` touch.
**Expected size:** ~4-6 commits.

---

## §0 READ FIRST

1. The D56 ledger in full: the round-0 premises P1-P7 (every line number is from `62da7933`; re-ground them) and CHARC's ruling (F-A..F-D, Reviewer B).
2. `swing/web/templates/patterns/review.html.j2` (the decision form, `:155-228`) and `swing/web/templates/patterns/exemplars.html.j2` (the four inline per-row forms, `:123-160`).
3. `swing/web/view_models/patterns/review_form.py` (`build_patterns_review_form_vm`, the VM's `window_start_date` field) — where the E3 helper lives.
3b. `swing/web/routes/patterns.py`: `patterns_review_page`, `patterns_review_post`, `_dbw_exemplar_window` (rules (i)-(iv) in its docstring), `_dbw_recovery_text`, `_DBW_START_GUARDED_DECISIONS`; and `patterns_exemplars_action` / `_apply_action` for the exemplars page's error raisers.
5. `swing/web/app.py` `_handle_http_exc` (`:666+`) and the generic `Exception` handler (`:149+`); `base.html.j2`'s `htmx.config.responseHandling` (4xx swap on).
6. Existing tests: `tests/web/test_routes/test_patterns_review.py`, `test_patterns_review_dbw_start.py`, `test_patterns_review_data_completeness.py`, and any exemplars-route tests (find them by grep; state how you found them).
7. CLAUDE.md §Gotchas "Web / HTMX / templates / forms" — especially: `hx-target` inheritance, the `<tr>`-leading fragment wrap, HTMX form endpoints' browser-only failure surfaces, and gotcha #31 (a comment may not promise what another change will do).

## §1 THE DEFECT

Both forms post with `hx-post` + `hx-headers` and NO `hx-target`, so HTMX's target is the form itself and every error response (400, 404, 422, 500 — `hx-target` does not care about status) is swapped into the form's `innerHTML`: the radios, fields and submit button vanish, including on the D53.1 DBW refusal whose own text names a recovery that needs those controls. TestClient cannot see the swap. Nothing is written on a refusal (no data risk).

## §2 REQUIRED END STATE (the claim list Reviewer B will measure first)

**E1 — review form error region (F-A's review half).** `review.html.j2` gets one error region element beside the form (a sibling, NOT inside it), and the form gets `hx-target` pointing at it. Every error response on `POST /patterns/{id}/review` lands in the region; the form and all its controls survive. The 204 + `HX-Redirect: /patterns/queue` success path is unchanged. Choose the swap so a second error REPLACES the first (no stacking).

**E2 — exemplars page error region (F-A, bounded).** `exemplars.html.j2` gets exactly ONE page-level error region (NOT per row, NOT inside a `<table>`/`<tr>`), and each of the four inline forms gets `hx-target` to it. **Nothing else on that page changes** (CHARC's bound: its other D35-class items stay banked). Success path unchanged.

**E3 — ONE trough-1 helper (F-C).** Extract a single helper in `swing/web/view_models/patterns/review_form.py` (an EXISTING module that `routes/patterns.py` already imports from — placing it in the route would make the VM import the route, inverting the dependency; name it; no new module) that, given an evaluation, returns the DBW form pre-fill start by row kind:
- `double_bottom_w`, `geometric_score > 0`, parseable `structural_evidence_json["trough_1_date"]` → that date;
- `double_bottom_w`, `geometric_score > 0`, unparseable/missing trough 1 → `window_start_date`;
- `double_bottom_w`, `geometric_score == 0` → `window_start_date` (its `trough_1_date` is the window END, not a trough — never pre-fill it);
- every other class → `window_start_date` (UNCHANGED).
`_dbw_exemplar_window`'s step (iii) uses the SAME helper's trough-1 extraction (one parse, one set of caught exceptions), so the pre-fill and the stored start cannot diverge. **Rule (i) keeps comparing to `evaluation.window_start_date`** (ruled; do not widen it).

**E4 — C3, the pre-fill.** The review form's `corrected_window_start_date` input renders the E3 helper's value through a NEW VM field (with a safe default) — **do NOT repurpose `window_start_date`**, which the page header also renders (`review.html.j2:8`) and which rule (i) still means literally. For eval-7835-shaped rows (non-zero, parseable) the form shows trough 1.

**E5 — refusal text (F-B).** In `_dbw_recovery_text`: drop step (1) (the RELOAD step — false once E1 lands), renumber the rest, keep "a date different from the pre-filled X", and **derive X from the E3 helper, never from `evaluation.window_start_date` directly.** Any other sentence in the text or in `_dbw_exemplar_window`'s docstring that describes what the form shows or pre-fills is amended by REPLACEMENT to be true after E1+E4 (rule (i)'s "the review form pre-fills that value" is the named instance). No comment may promise future behavior (gotcha #31).

## §3 TESTS (red first; each asserts a value that DIFFERS pre- vs post-fix — show that arithmetic in the commit message or ledger)

- **T1** review form renders an error region OUTSIDE the `<form>` and the form carries `hx-target` naming it (assert the exact attribute and that the target id exists once, outside the form).
- **T2** exemplars page: exactly one page-level region, not inside `<table>`; all four inline forms per row carry `hx-target` to it; the page otherwise renders the same rows/controls as before (discriminate against an over-wide change).
- **T3** (F-C pin, three row kinds: parseable non-zero, unparseable non-zero, zero) — an UNTOUCHED submit under `pattern_present_outside_window` (built from the value the form ACTUALLY RENDERS, read from the GET response — not a hand-typed constant) stores the SAME `start_date` as the pre-C3 code stores for that row kind (zero kind: still refuses). Parseable non-zero → trough 1; unparseable → refuses as today; zero → refuses.
- **T4** (F-B pin, CHARC's): for each of the three row kinds that can refuse or pre-fill, the pre-fill value named in the refusal text EQUALS the value rendered in the form's `corrected_window_start_date` input — read BOTH from real responses (GET the form; POST the refusal).
- **T5** refusal text no longer contains the RELOAD step; the numbered steps are contiguous.
- **T6** non-DBW class: form pre-fill is `window_start_date`, unchanged.
- **T7** success path on both routes still returns 204 + the same `HX-Redirect`.
- Existing D53.1 tests (`test_patterns_review_dbw_start.py`) stay green; if one encodes the old text or the old pre-fill, amend it by replacement and say which assertion changed and why.
- Full fast suite green BEFORE the review and on the final head (`python -m pytest -m "not slow" -q -n 4`; `-n auto` is memory-killed on this box). `ruff check swing/` introduces no new violation.

## §4 LOCKS

- No schema, no migration, no new module, no dependency. No `swing/data`, `swing/trades`, `swing/pipeline`, detector or `app.py` handler change (the fix is `hx-target` + regions, not a handler change — if you conclude a handler change is needed, STOP and return).
- Historical `pattern_evaluations` / `pattern_exemplars` rows are never rewritten.
- Rule (i) compares to `window_start_date` (ruled). `reject`/`relabel` behavior unchanged. `_DBW_START_GUARDED_DECISIONS` unchanged.
- Exemplars page: only the region + the four `hx-target` attributes.
- ASCII in any new user-facing string.
- **Do NOT run the app against the live DB and do NOT submit any review.** The browser witness is the orchestrator's with the operator after your return (F-D: live, GET + refusal paths only, `pattern_exemplars` count measured before and after).

## §5 REVIEW (Reviewer A — yours)

Per the recipe §3: `strong` tier, the five per-round assertions recorded per round, copy-per-round preservation to `~/swing-data/review-transcripts/d56-exec/`, review scratch relocated out of the worktree during the loop, stop at the first clean verdict. **Repo access is required** (production code whose correctness depends on the unchanged handler in `app.py` and the VM builder): either the cold-audit form reading the changed files, or the stdin bundle PLUS `app.py`'s two handlers, `base.html.j2`'s `responseHandling` block, and the VM builder.

**Declared envelope for the prompt:** the two forms' error routing (E1, E2), the one helper and its three row kinds (E3), the pre-fill (E4), the refusal text (E5). Tag findings reachable only outside it.

**Accepted limitations, each with its reason (declare them; invite challenge):**
- *The other D35-class items on the exemplars page are not fixed* — CHARC bounded F-A to the region + `hx-target`; they stay on the register.
- *Browser behavior is not TestClient-provable* — the HTMX swap target is verified by the operator witness after return (binding for HTMX work); the tests pin the attributes and the server responses.
- *C3 is a no-op for rows written from run 177 on* — the runner already writes trough 1 to `window_start_date` for non-zero DBW rows (D53.1 F2); C3 is kept, as ruled, for pre-177 rows (one live row today).
- *Rule (i) is not widened* — ruled F-C (a); the stored value is identical on all three row kinds (T3 proves it).

## §6 RETURN (your final chat message, to the orchestrator only — never role_mail)

Per the recipe §4: commits in order (SHA + subject); the E1-E5 sites as changed (file:symbol); tests added/amended with the pre/post arithmetic; the suite tail read off the final head with SHA; ruff result; A's round ledger (per round: model, effort, `^ERROR` count, footer, verdict token, severity counts) + the findings path + the durable transcript path; the SPEND LINE (summed `tokens used`); every §4 lock as honored-on-disk; how you found the exemplars tests (the search); deviations and anything flagged-not-fixed with a proposed disposition.
