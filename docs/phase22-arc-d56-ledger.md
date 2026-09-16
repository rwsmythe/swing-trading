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

---

## Round-0 RULING (CHARC, PRIMARY on all four) -- literal block quote

**Ruling seat:** CHARC. **Courier:** orchestrator (transcription only). **Source:** role-mail `20260915T182237Z-charc-d56-round-0-ruling-f-a-in-f-b-c-d-a-with.md`, posted 2026-09-15T18:22:37Z. CHARC corrected the D56 register row's citation at `ac3f6a80`.

> RULING PACKET -- D56 round 0 (ledger 81e5be74). CHARC, PRIMARY on all four.
> One pass. Block-quote into the ledger; dispatch off that commit. Verified
> before ruling: review.html.j2:155-159 (no hx-target), exemplars.html.j2
> :125/:137/:147/:157 (four hx-post forms, no hx-target anywhere in the file),
> _dbw_recovery_text (:728-737). P2 is right and the mis-citation is MINE:
> the D56 register row cited the EXEMPLARS route's lines as the review route's;
> corrected on the row in the commit that carries this ruling.
>
> F-A -- RULED (a), IN, with the bound stated. Same class, same one-attribute
>   fix, and my own citation already pointed at that route. Bound: the
>   exemplars page gets ONE page-level error region and the four inline forms
>   get hx-target to it; nothing else on that page changes (its other D35-class
>   items stay banked). Page-level, never per-row: a per-row region reintroduces
>   the <tr>-fragment wrap gotcha and the colspan path for no gain.
>
> F-B -- RULED (a), with one condition that makes the text safe under C3. Drop
>   step (1), renumber. The clause "a date different from the pre-filled X"
>   stays -- but X must be what the form SHOWS, and after C3 that differs by
>   row kind (trough_1_date for a parseable non-zero row; window_start_date for
>   an unparseable row; no change for a zero row). So the refusal text derives
>   X from the SAME helper the form's pre-fill uses (F-C's one helper), never
>   from evaluation.window_start_date directly -- or it is the #31 class again,
>   one arc later. Pin it: for each of the three row kinds, the refusal's named
>   pre-fill equals the form's rendered pre-fill (a TestClient test can read
>   both from the same response).
>
> F-C -- RULED (a). Rule (i) keeps comparing to window_start_date; ONE trough-1
>   helper feeds both C3's pre-fill and (iii)'s extraction; rule (i)'s docstring
>   amended by replacement (it currently promises the form pre-fills
>   window_start_date -- the #31 sentence). The pin: an untouched non-zero
>   submit under pattern_present_outside_window stores the SAME start as before
>   C3, asserted on all three row kinds (parseable non-zero, unparseable,
>   zero). (b) is more code for an identical stored value; refused.
>
> F-D -- RULED (a), LIVE for GET and refusal paths only, with two additions.
>   (1) The zero-write proof is MEASURED, not assumed: SELECT COUNT(*) FROM
>   pattern_exemplars on the live DB (plain sqlite3, mode=ro) before and after
>   the witness, equal, into the ledger. A witness must not mint an exemplar
>   (the 09-14 rule); the count is what proves it did not. (2) Because F-A
>   brings the exemplars page in, the witness drives ONE refusal on that page
>   too (an invalid action is enough) and sees its region take the fragment
>   with every row's controls intact. The success path stays TestClient-only;
>   eval 7835 showing 2026-07-29 pre-filled is the C3 witness step.
>
> Reviewer B -- REQUIRED, not waived. The D53.1 gate called D56 a "tests +
>   template rider", but C3 and the one-helper change land in
>   swing/web/routes/patterns.py, which is production code; charter 2.9 binds.
>   B runs once at your gate over the finished tree, the usual five assertions,
>   introduced-vs-banked disposition; the stop rule from D32+D50 applies if it
>   starts enumerating routes to one failure. Cell: implementer-sonnet-high is
>   fine for the locked design.
>
> Register D56 citation corrected at ac3f6a80.

---

## Dispatch (orchestrator)

**Brief:** [`docs/phase22-arc-d56-error-region-c3-dispatch-brief.md`](phase22-arc-d56-error-region-c3-dispatch-brief.md), encoding the ruling above. One placement decision made at encoding, not a design fork: the E3 helper lives in `swing/web/view_models/patterns/review_form.py`, because `routes/patterns.py` already imports that module and the VM needs the helper for the pre-fill; putting it in the route would make the VM import the route. The pre-fill reaches the template through a NEW VM field — `window_start_date` stays literal (the header renders it; rule (i) compares to it). **Cell:** `implementer-sonnet-high` (the executing default; locked design, CHARC concurred). **Worktree / base SHA:** recorded in the next entry.

**Dispatched 2026-09-15:** `implementer-sonnet-high`, worktree `.worktrees/d56-exec`, branch `d56-exec`, **base `9567459f`** (the commit carrying the ruling transcription and the brief). Base verified to carry the rules the brief depends on (recipe: the plan-stage protocol, copy-per-round preservation, Reviewer B relocated to the orchestrator). Durable transcript dir created: `~/swing-data/review-transcripts/d56-exec/`.

---

## Executing return + orchestrator QA (2026-09-15)

**Return:** `d56-exec` head `469296ea` (5 commits over `9567459f`: `4c175faf` E1+E2 · `1552a876` E3+E4+C3 · `7ba9cb14` E5 · `932596c7` Codex R1 major · `469296ea` R2 nit). Diff touches only `routes/patterns.py`, the two templates, `view_models/patterns/review_form.py` and three test files (one new). Cell-seat suite on `469296ea`: 12,469 passed / 13 skipped (base 12,456; +13 = the new tests). Ruff clean.

**QA on disk (orchestrator):** trailers empty on all 5 commits; working tree clean; production diff read in full: one parser `extract_dbw_trough_1_date` + `dbw_corrected_start_prefill` in the VM module, rule (iii) calls the parser, rule (i) still compares to `window_start_date`, refusal text names `dbw_corrected_start_prefill(evaluation)`, exemplars page = one region + four `hx-target` (no `hx-swap`), review form = sibling region + `hx-target` + `hx-swap="innerHTML"` (the default, explicit), new VM field `corrected_window_start_date_prefill`, no `app.py` change. Codex's `geometric_score` NOT NULL citation verified: `0020_phase13_charts_patterns_autofill_usability.sql:240`.

**Reviewer A (the cell's), verified from the transcripts:**

| Round | Model / effort | `^ERROR` | footer | verdict tokens | counted | findings |
|---|---|---|---|---|---|---|
| R1 | gpt-5.6-sol / high | 0 | 1 (210,367) | NNCM 1 (prompt echo) / NCMF 3 | **NO** — the prompt wrote both tokens line-initially (the recipe's prompt-design hazard) | 1 major (redundant `hx-swap` on the exemplars forms, outside F-A's bound) + 1 minor (fragment tests lacked the real `HX-Target` header, 400 only) — both fixed `932596c7` |
| R2 | gpt-5.6-sol / high | 0 | 1 (212,208) | NNCM 2 (0.152.1 double-emit) / NCMF 0 | yes — **CONVERGED** | 1 nit (stale test-module docstring), fixed `469296ea` without a round |

The R2 prompt carries zero line-initial tokens (orchestrator grep). Transcript sha256 identical worktree vs durable (`1909dd50…`). A spend: 422,575 (R1 210,367 disqualified + R2 212,208).

**Reviewer B (orchestrator's, charter §2.9, ruled REQUIRED):** cold audit, `codex exec -p strong -s read-only --skip-git-repo-check`, CLAIMS-FIRST over E1-E5 + F-A/F-B/F-C, launched from PowerShell via an LF runner with pre-created output/exit files. Assertions: model `gpt-5.6-sol`, effort `high`, `^ERROR` 0, footer 1 (191,332), `^NO_NEW_CRITICAL_MAJOR` 2 / `^NEW_CRITICAL_MAJOR_FOUND` 0, measured exit 0, transcript 626,189 bytes, no codex process left running. The 3 hits on A's scratch filenames are the prompt's own prohibition echoed plus two lines of `orchestrator-context.md` content, not reads of A's files. **Verdict: CLEAN.** Claims: E1-E5 PASS, F-A PASS, F-C PASS, **F-B FAIL on the TEST, not the code.** Findings:
- **B-1 minor, INTRODUCED:** T4 pins only the unparseable and zero kinds, where old and new pre-fill are equal, so reverting the refusal text to `evaluation.window_start_date` stays green; CHARC's pin names all three kinds. **ACCEPTED, fix authorized** (a parseable-kind case calling `_dbw_recovery_text` directly against the rendered pre-fill, red shown by temporary revert).
- **B-2 nit:** the new test module's docstring claims 422/500 coverage it does not directly exercise. **ACCEPTED, fix authorized** (docstring by replacement).
Both are post-convergence test-only corrections: no further Codex round, verified by the suite. **Authority granted by cell message:** this fix leg (B-1, B-2), sent to the same cell. Evidence: `~/swing-data/review-transcripts/d56-exec/codex-b-*`. B spend 191,332.

---

## Live browser witness (F-D: GET + refusal paths only, nothing written) -- 2026-09-15, operator driving, one step per result

**Setup:** the branch code (`d56-exec` @ `528b083b`) served on 127.0.0.1:8081 from the worktree (`PYTHONPATH=. python -m swing.cli web --port 8081`), against the LIVE DB. Confirmed branch code by the served markup: `id="patterns-review-error"` present and the form carrying `hx-target="#patterns-review-error"`. The operator's own 8080 server was down for the duration. **Baseline, plain `sqlite3` `mode=ro`, 15:43:25: `pattern_exemplars` 35 rows, max id 35.**

**W1 -- DBW zero-score refusal on the review form (eval 7820, DK; decision `confirm`, nothing else touched). PASS.** Operator-reported banner, verbatim: *"Cannot record double_bottom_w evaluation 7820 as a pattern: its geometric_score is 0 (the detector found no W), and the window start 2026-09-02 is the detector anchor, not the start of the W. To record it: (1) choose the decision pattern_present_outside_window; (2) type the first-trough start date into the window-correction start field (a date different from the pre-filled 2026-09-02)."* -- no RELOAD step, steps contiguous from (1), the named pre-fill is the value the form rendered. **Operator confirmed the form SURVIVED: the six decision radios, both window-correction date fields and the Submit button all still present, and the banner sits BELOW the form.** That is the defect this arc fixes, witnessed in a real browser (TestClient cannot see it). Count after W1, 15:45:05: 35 rows, max id 35 -- unchanged.

**W2 -- C3 pre-fill on the one live differential row (eval 7835, NESR; GET only, nothing submitted). PASS.** The window-correction START field renders **2026-07-29** (the evidence `trough_1_date`), not the `window_start_date` 2026-08-20 the page header still shows as the detector anchor -- the only row in the live DB where the two differ today (P6). Operator confirmed the date. Count after W2: 35 rows, max id 35 -- unchanged.

**W3 -- exemplars page refusal (row id 2, NVDA, proposed `vcp`; Relabel to `vcp`, the one value the route refuses before any write). PASS.** Operator: all pass -- the banner renders in the ONE page-level region above the table and every row's controls survive. Count after W3, 15:48:25: 35 rows, max id 35 -- unchanged; **row 2 re-read and byte-identical** (`final_decision='rejected'`, `final_pattern_class` NULL, `label_source='claude_silver'`), so the refusal wrote nothing to the row it named either.

**WITNESS RESULT: 3 of 3 PASS, ZERO rows written.** `pattern_exemplars` 35 / max id 35 at the baseline (15:43:25) and after every step (15:45:05, 15:47:05, 15:48:25) -- the measured zero-write proof CHARC's F-D (1) required, on a plain `sqlite3` `mode=ro` connection, never through `swing`'s `connect`. The success path stays TestClient-only, as ruled.

---

## Merge

**`d12aa7b6`**, `git merge --no-ff d56-exec` (parents `333cec8b` + `528b083b`). **`--no-ff`, never rebase:** this ledger and the witness section cite branch SHAs, so a rebase would falsify every citation while leaving it reading true (recipe §1). Diff as merged: 7 files, +720/-28 -- `swing/web/routes/patterns.py`, the two pattern templates, `swing/web/view_models/patterns/review_form.py`, and three test files (one new). **Merged-head suite on `d12aa7b6` (this seat, `-n 4` per D52): 12,469 passed / 13 skipped / 0 failed, 837.84s. `ruff check swing/`: All checks passed.** Trailer audit over `origin/main..HEAD`: zero `Co-Authored-By`. Witness server stopped before the merge; port 8081 free, no straggler `swing web` process.

**Spend:** Reviewer A 422,575 (R2 counted 212,208 + R1 disqualified 210,367); Reviewer B 191,332; cell 355,019 + 411,423 across its two dispatches. **Arc total (review footers): 613,907.**

**Still open at merge (dispositioned):** (1) the exemplars-route 500 path (`routes/patterns.py:264,273`, corrupt `labeler_evidence_json` on `promote_to_gold`) has NO test exercising it -- found by the cell's own grep while correcting a docstring, **BANKED for CHARC's register**, not this arc's scope (F-A bound). (2) The other D35-class items on the exemplars page stay banked, as ruled.

## Teardown (orchestrator, 2026-09-15)

CHARC ACCEPTED the return at `dde335c2` and CLOSED the register row (the untested 500 path banked on it). **Evidence reconciled by sha256 BEFORE anything was removed, `ls -a` (dotfiles) both sides:** 10 files in the worktree vs `~/swing-data/review-transcripts/d56-exec/` — 8 matched, and **2 existed ONLY in the worktree** (`.codex-bundle-r2.txt`, `.codex-diff.txt` — the bundle and diff actually fed to Reviewer A), copied in and hash-verified; the durable dir also holds the r1 DISQUALIFIED pair the cell had relocated. 12 files, zero content mismatches. **Then:** branch proven fully contained in `main` (`git log main..d56-exec` = 0), `git worktree remove` de-registered it but left the directory (Windows permission-denied on the delete), so `git worktree prune` + `rmdir` on the now-EMPTY husk; `git branch -d d56-exec` (not `-D`) deleted the branch at `528b083b`. Verified after: `git worktree list` shows `main` only, no `d56*` branch, `.worktrees/` empty. `main` pushed — `origin/main` == `dde335c2`, 0 ahead / 0 behind, zero `Co-Authored-By` by trailer KEY in the pushed range.
