# Phase 16 — Watchlist Pin + Hypothesis-Labeling Effectiveness — Arc Commissioning Brief

**Audience:** The Phase 16 orchestrator instance (manages `docs/phase16-todo.md`; runs copowers cycles).
**Mission:** Commission a new Phase 16 arc (take the next free arc number — Arc 5 is closed; the perf arc is in
flight): make the hypothesis-labeling workflow EFFECTIVE end-to-end in the operator's web-first workflow, via two
coupled features — (1) a **watchlist pin** (keep a ticker on the watchlist until unpinned) and (2) the
**matcher-driven auto-label prefill amendment** (web-entered watch trades persist the `Broad-watch baseline` label
with zero manual action). Requirements below are operator-elicited and binding (R1–R6); implementation design is
yours via your normal copowers cycle.
**Prepared:** 2026-06-10 by the research-director/evaluator instance (operator-commissioned; tag-shape /
label-source / pin-semantics / arc-scope decisions confirmed by the operator this session).

> **AMENDMENT 2026-06-10 (supersedes parts of R2/R4 below; read BEFORE the Codex rounds).** The operator corrected a
> miscommunication in this brief and the research director has QA'd the Arc-7 pre-Codex spec's two flagged
> deviations. Binding rulings:
>
> 1. **R2's absent-from-candidates "stale-display" framing is SUPERSEDED.** The pin's purpose includes tracking
>    names that fall off the finviz screen entirely ("potential future companies to keep an eye on which may not,
>    currently, be tracked"). The corrected model (operator-authorized): **pinned tickers are unioned into the
>    `_step_evaluate` fetch universe** at the established held-ticker injection seam (`runner.py` ~L1389-1400) and —
>    unlike held tickers — flow through `evaluate_batch` to get REAL criteria/bucket/streak rows. The carve-out
>    expansion into `_step_evaluate` is **APPROVED** (deviation a).
> 2. **Deviation (b) — the R4 cohort hint computed via `match_candidate_to_hypotheses(..., include_baseline=True)`
>    at watchlist render — APPROVED**, with two required strengthenings: (i) the 0026-spec addendum (R3 governance)
>    must enumerate **BOTH** opt-in call sites (the entry-form/CLI prefill AND the watchlist cohort-hint builder) as
>    attribution surfaces — not just the prefill; (ii) add an **opt-in call-site inventory guard test** asserting
>    the ONLY `include_baseline=True` call sites are those two in `swing/` plus the engine's
>    `research/harness/shadow_expectancy/attribution.py` — so future opt-ins cannot creep in silently.
> 3. **Measurement-universe ruling (research-director lane; nobody had flagged it).** A pin-injected ticker that
>    evaluates to `bucket=watch` enters the #23 pattern detect/observe pool → the v22 temporal log → the
>    shadow-engine broad-watch measurement population. **ACCEPTED**: pins are part of the operator's intentional
>    universe, and the frozen hypothesis statement defines the cohort as "the population the temporal log contains
>    and the operator actually trades" — pinned names literally are that. Two REQUIRED riders: (i) the arc's spec +
>    the 0026 addendum document that the evaluated universe is **screen + pinned** (universe-composition note);
>    (ii) per-run auditability — when pin-injection occurs, emit a `warnings_json`/pipeline.log line listing the
>    injected tickers (count + symbols) so screen-vs-pin provenance is decomposable from run logs. No schema.
> 4. **Edge for Codex to probe:** a pinned ticker with no fetchable data (delisted/empty) must route through the
>    existing F6/error handling without blanking the watchlist row — the pin keeps the row; the run-warning
>    surfaces the degradation.

---

## 0. Read first

1. `CLAUDE.md` — conventions + gotchas. Directly load-bearing here: the **HTMX gotcha family** (4xx config override;
   `hx-target` inheritance; OOB swaps; embedded-form `hx-headers`; **operator-witnessed browser verification is
   BINDING for HTMX work**), the **web-form family** (server-stamp; hidden-anchor round-trip through the soft-warn
   confirm `form_values`), and the **migration family** (#9 BEGIN/COMMIT; backup-gate strict equality; #11 sweep —
   note the v26 pin family was just swept at 0026; whatever number this arc takes moves those pins again).
2. The current mechanics (verified 2026-06-10):
   - `watchlist` table (`swing/data/migrations/0003_…`): ticker PK, `status`, `qualification_count`,
     `not_qualified_streak`, `last_data_asof_date`, frozen `entry_target`/`initial_stop_target`, `missing_criteria`,
     `notes`. **No tag/pin columns exist.**
   - Lifecycle: nightly `_step_watchlist` (`swing/pipeline/runner.py:1503`) applies
     `compute_watchlist_changes` (`swing/watchlist/service.py:57`) — adds / requalifies / streak_increments /
     removes (→ `watchlist_archive`). NOTE `service.py:70-71`: a ticker ABSENT from today's candidates is skipped
     entirely (no streak movement) — read the full removal semantics before designing the pin veto.
   - The web entry form's `hypothesis_label` is **server-stamped**: resolved at form-render via
     `lookup_active_recommendation_label` (`swing/web/view_models/trades.py:542`), rendered as a display-only span +
     HIDDEN input (`trade_entry_form.html.j2:147-148`), round-tripped through the soft-warn confirm
     (`routes/trades.py:1504`). There is NO free-text hypothesis field and NO post-hoc label editor in the web.
   - The prefill helper (`swing/recommendations/hypothesis_prefill.py`) calls the matcher with the default
     `include_baseline=False` → it can NEVER produce `Broad-watch baseline` today → web-entered watch trades persist
     `hypothesis_label = NULL`. This is the effectiveness gap.
3. The broad-watch governance context: `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md`
   §3.2 + §5.1 (the containment design this arc partially amends — see R3 governance), and the matcher's two-phase
   fallback gate (`swing/recommendations/hypothesis.py:349-351` — narrow-first precedence is structural; the prefill
   inherits it for free).
4. Prior art pointer: `docs/watchlist-sort-by-tags-brief.md` (an earlier tags idea that never landed a tag store) —
   read for context, not as a constraint.
5. Coordination: the **P0 tuition-vs-error arc is in flight** (research-director lane; will add an `entry_intent`
   column + entry/review-form changes). Both arcs touch `trade_entry_form.html.j2` + `routes/trades.py` — land in
   either order, expect a small merge reconciliation. **Migration number: take the next free at branch time** (P0
   will likely take 0027).

---

## 1. Binding requirements (operator-confirmed)

**R1 — Watchlist pin (shape: pin flag + note).** Per-ticker `pinned` flag (0/1) + optional free-text `pin_note`
(+ a `pinned_at` audit timestamp if you judge it cheap), settable and clearable from the watchlist row in the web
GUI (HTMX action; the HTMX + form gotcha families apply in full). Additive migration on the `watchlist` table
(phase-isolation carve-out: `swing/data` schema + repo column plumbing scoped to this).

**R2 — Pin semantics: pin blocks removal ONLY.** Streak counting and requalification continue exactly as today;
the pin vetoes the remove/archive step for that ticker; on unpin, accumulated state takes effect at the next
nightly run (no retroactive removal mid-session). Pinned rows are visibly badged on the watchlist page (note
displayed/abbreviated). Design question for your brainstorm: the absent-from-candidates case (`service.py:70-71`)
— a pinned ticker that leaves the screen entirely goes stale; decide the stale-display treatment (e.g.
`last_data_asof_date` + a stale indicator), do not silently show stale numbers as fresh.

**R3 — Matcher-driven auto-label (the prefill amendment).** `lookup_active_recommendation_label` passes
`include_baseline=True` — that ONE call site only. Result: the server-stamped entry-form/CLI prefill yields the
narrow label when a narrow cohort matches (the fallback gate gives narrow-first structurally), else
`Broad-watch baseline (watch); failed: …` for watch-bucket candidates, `None` otherwise. Tags/pins do NOT drive
labels (operator decision: labels always mirror shadow attribution).
**GOVERNANCE (research-director authorization, granted here):** this amends the 0026 spec's §5.1 letter, which
listed `hypothesis_prefill.py` among the contained surfaces. The arc MUST include an addendum to that spec (a
dated section, not a rewrite) stating: the dashboard recommendation surfaces (`dashboard.py` ~L540 + ~L1061,
`prioritize_recommendations` consumers) remain contained (default `False` — verify with a regression test asserting
no broad-watch rows reach the hyp-recs panel); the single-ticker entry-form/CLI prefill is re-classified as an
**attribution surface** (it fires only for a ticker the operator already chose to enter and recommends nothing —
the flood rationale never applied to it). The frozen registry row itself is UNTOUCHED.

**R4 — Population visibility.** From the watchlist page the operator can tell what a name would attribute as on
entry: minimal V1 = a per-row cohort hint (narrow-hypothesis name when matched, else "broad-watch", else none).
The entry form already displays the resolved label, which post-R3 shows `Broad-watch baseline …` — your brainstorm
decides whether the watchlist hint reuses the matcher per row (candidates are already loaded) or a cheaper proxy.
Keep it small; this is an affordance, not a new metrics surface.

**R5 — Label round-trip integrity.** The soft-warn confirm path must round-trip the new prefill value (the
plumbing exists at `routes/trades.py:1504`; the amendment changes the VALUE, not the mechanism) — regression test:
a broad-watch entry submitted through the soft-warn confirm persists `Broad-watch baseline …`, and a `force=true`
resubmit does not drop it (the hidden-anchor gotcha family).

**R6 — Locks.** UNTOUCHED: the hypothesis registry rows; the matcher's two-phase gate + the dashboard call sites'
default; `swing/metrics/tier.py` + deviation (allowlist-locked); the shadow engine + temporal log + measurement
chain; the 16 historical trades' labels; `mistake_tags`/`process_grade`. The label-match prefix contract: the
descriptive suffix emitted by `_descriptive_label` is already name-first — add/keep a test that the persisted label
matches `Broad-watch baseline` under `swing/metrics/label_match.py`'s 3-rule contract.

---

## 2. Design questions for your brainstorm (not pre-decided)

1. Pin UI mechanics (row button vs detail view; HTMX swap shape — mind the `<tr>`-fragment and `hx-target`
   inheritance gotchas; embedded form needs `hx-headers HX-Request`).
2. The pin veto's exact seam in `compute_watchlist_changes` vs the write phase (`_step_watchlist`) — keep the
   service pure if you can; the delta object may grow a `suppressed_removes` lane for audit.
3. Whether `watchlist_archive` records a "pin prevented removal" trace or nothing (silent-skip-without-audit
   gotcha #27 leans toward a trace or a `warnings_json` line).
4. The R4 per-row cohort hint's data path (matcher per row at render vs precomputed at the nightly step).
5. Stale-pinned-row display (R2).
6. Migration number + the version-pin sweep interaction with P0's in-flight arc.

---

## 3. Done criteria

- The arc lands on `main` via your normal copowers cycle; fast suite green on the merged head; ruff clean; zero
  co-author trailers.
- The 0026 spec addendum (R3 governance) is part of the arc's deliverables — the research director will QA its
  language at the post-merge review.
- **Operator-witnessed browser gate (BINDING per the HTMX discipline):** pin → survives a nightly run that would
  have removed the row → unpin → ages off naturally; AND the entry form for a watch ticker renders
  `Broad-watch baseline (watch); failed: …` server-stamped (an actual trade entry is NOT required for the gate —
  form-render + a TestClient persist test suffice; the operator witnesses the render).
- Regression evidence: no broad-watch rows in the hyp-recs panel; dashboard matcher call sites still default-False.
- `docs/phase16-todo.md` updated (new arc entry + completion state). Report back to the operator; the research
  director QAs the spec addendum + the honesty surfaces at the next evaluation session.
