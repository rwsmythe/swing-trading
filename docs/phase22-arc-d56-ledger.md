# Phase 22 — Arc D56 ledger: the pattern-review form's error region (+ C3)

**Register:** CHARC D56 (`docs/tool-director-context.md` row D56, commissioned `637d12fc` by the D53.1 B-gate ruling as a tests+template rider, sequenced after D32+D50, with C3 riding).
**Commissioned by:** the operator's "commence D56", 2026-09-15.
**Base at census:** `main` @ `62da7933` (pushed; origin/main equal).

---

## Round 0 — premise + fork census (orchestrator, no Codex, 2026-09-15)

Every fact below was read from code on `62da7933` or from the live DB opened `mode=ro` with plain `sqlite3`.

### Premises

**P1 — CONFIRMED.** `swing/web/templates/patterns/review.html.j2:155-159`: the review `<form>` carries `hx-post` + `hx-headers` and NO `hx-target`, so HTMX's target is the form itself with the default `innerHTML` swap. `base.html.j2:60-64` enables swapping on `[45]..`. `app.py:666-683` (`_handle_http_exc`) returns `partials/http_error_fragment.html.j2` (a bare `<div class="banner banner-degraded" role="alert">`) for any HX-Request error whose `HX-Target` is not a row prefix. So every error response replaces the radios, the correction fields and the submit button.

**P2 — PARTLY MIS-SOURCED (the register's line citations).** The register row cites `routes/patterns.py:141/:152/:207` as the review route's 400s. Those lines (`:141`/`:152` are 400s; `:207` is a 404) are in **`patterns_exemplars_action` / `_apply_action`** — the EXEMPLARS page's per-row action route — not the review route. The review route's own error raisers are:
- `:424` 400 — decision not in the enum;
- `:437` 404 — candidate gone between GET and POST;
- `:450` / `:459` 400 — relabel target missing / equal to the proposed class;
- `_dbw_refuse` (`:626`) 400, reached from `:640` (typed date unparseable), `:707` (non-zero row, no parseable `trough_1_date`), `:712` (zero score), `:721` (start after end);
- the generic `Exception` handler (`app.py:149-178`) 500 via `partials/error_fragment.html.j2`, e.g. a `PatternExemplar.__post_init__` `ValueError`.

**P3 — the exemplars page has the SAME defect.** `templates/patterns/exemplars.html.j2:123-160`: four inline forms per table row (`promote_to_gold`, `watch`, `reject`, `relabel`), each `hx-post` + `hx-headers` with NO `hx-target`. An error from `:141`/`:152` (400), `:207` (404 — note the register calls it a 400), `:261`/`:270` (500), `:346`/`:361` (400) replaces that inline form's contents inside its table cell.

**P4 — `hx-target` is status-agnostic.** Pointing the form at a sibling region routes EVERY swapping response there (400, 404, 422, 500); the 204 success path is `swap: false` + `HX-Redirect`, unaffected. The fix covers every error on the route by construction, not just the 400s.

**P5 — the D53.1 refusal text becomes FALSE the moment D56 lands.** `_dbw_recovery_text` (`:728-737`) says *"(1) RELOAD this page (this message has replaced the review form)"*. And `_dbw_exemplar_window`'s docstring rule (i) says *"the review form pre-fills that value"* (`window_start_date`), which C3 changes for non-zero DBW rows. Both are text about the form's state written by another arc (the #31 class); both must change in this arc.

**P6 — C3's live footprint, measured.** `pattern_evaluations` holds 1,569 `double_bottom_w` rows; **1** has `geometric_score > 0`: **id 7835, NESR, run 176, `window_start_date` 2026-08-20, evidence `trough_1_date` 2026-07-29** — the one row where C3's pre-fill differs from today's. No `pattern_exemplars` row exists for NESR DBW. Run 176 predates D53.1 F2's first production run (177, tonight 17:30 HST); from 177 the runner writes trough 1 into `window_start_date` for non-zero rows, so **C3 is a no-op for every future non-zero row** and matters only for pre-177 rows (today: one). Not re-litigating the commission — recording the number.

**P7 — C3 composes with rule (i) with an IDENTICAL outcome, under one condition.** With C3, an untouched submit of a non-zero row under `pattern_present_outside_window` carries `trough_1_date`, which differs from `window_start_date`, so rule (i) no longer calls it "not a correction" and (ii) takes it as typed. The stored start equals what (iii) produces anyway. For a row whose evidence is unparseable C3 must fall back to `window_start_date` (rule (i) applies as today, and the refusal text's "a date different from the pre-filled X" stays true); for a zero row C3 does not pre-fill (its `trough_1_date` is the window END). **The condition: C3's pre-fill predicate and (iii)'s extraction must be ONE helper**, or the refusal text can name a pre-fill the form does not show.

### Forks — PRIMARY: charc (one ruler for every item; rd CC)

**F-A — scope: does D56 cover the exemplars page (P3)?**
- (a) **IN** — same class, same one-attribute fix plus one page-level error region; the register's own citations already point at that route. *Recommended.* One region at page level, not per row, which avoids the `<tr>`-fragment wrap gotcha and the row-colspan path.
- (b) OUT — bank as D56.1.

**F-B — the D53.1 refusal text (P5), which was ruled text (the D53.1 B-gate "reload-first refusal text in-arc").**
- (a) drop step (1) and renumber; keep the remaining steps and the "different from the pre-filled X" clause. *Recommended.*
- (b) other wording of your choice.

**F-C — rule (i) under C3 (P7).**
- (a) leave rule (i) comparing to `window_start_date`; extract one trough-1 helper used by both C3's pre-fill and (iii); amend the rule (i) docstring; pin with a test that an untouched non-zero submit stores the same start as before C3. *Recommended* — the stored value is identical on all three row kinds.
- (b) widen rule (i) to also treat the C3 pre-fill as not-a-correction (more code for an identical stored value).

**F-D — the browser witness and the live DB.** A successful review submit writes a `pattern_exemplars` row (a measurement input).
- (a) witness on LIVE with GET and refusal paths only (nothing is written on a refusal): the error region survives a DBW zero-score refusal with the form intact; eval 7835's form shows `2026-07-29` pre-filled; the success path is TestClient-only. *Recommended.*
- (b) witness on a COPY DB via a worktree `swing web`, including one successful submit.

**No other fork found.** Cell after the ruling: `implementer-sonnet-high` (tests + template + one helper; locked design once F-A..F-D are ruled).
